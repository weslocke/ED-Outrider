"""The tick and its long-lived tasks must never stop silently (the full Fable review of 2026-10-23: S1x-B1, S1x-S1,
S4-B11, S4-B14, S4-S5, S7-S7)."""
import asyncio
import contextlib
import io
import time
import types
import unittest
import unittest.mock

from support import ed_outrider


class TickGuards(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def tick(self):
        # (maybe_unsold starts a worker on the running loop: none here, and nothing of it is tested)
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), contextlib.redirect_stderr(io.StringIO()), \
                unittest.mock.patch.object(self.state, "maybe_unsold", lambda: None):
            self.state.tick({})

    def test_curious_said_survives_a_later_rollback(self):
        """S1x-B1: maybe_curious ran after the tick's commit and left its write open; the next failure's rollback took
        it while memory kept it, and the curiosities were said again after a restart."""
        now = time.time()
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(now - 30), "StarSystem": "Odd", "SystemAddress": 12,
                       "StarPos": [0, 0, 0]})
        self.j.handle({"event": "Scan", "timestamp": ed_outrider.iso_ts(now - 20), "ScanType": "Detailed", "StarSystem": "Odd",
                       "SystemAddress": 12, "BodyID": 3, "BodyName": "Odd 3", "PlanetClass": "Water giant",
                       "DistanceFromArrivalLS": 400.0, "WasDiscovered": False, "WasMapped": False})
        self.db.commit()
        self.j.status_json = {"live": True}
        self.state.maybe_curious()
        self.db.rollback()
        self.assertEqual(ed_outrider.meta_get(self.db, "curious_said"), [12])

    def test_a_follow_up_write_is_kept_when_a_later_one_fails(self):
        """S1x-B1: each follow-up's writes are committed when it ends, so a later one's failure rolls back only its own."""
        def writes():
            ed_outrider.meta_set(self.db, "probe", 1)

        def fails():
            raise RuntimeError("boom")
        with unittest.mock.patch.object(self.state, "maybe_refresh", writes), \
                unittest.mock.patch.object(self.state, "apply_own_changes", fails):
            self.tick()
        self.assertEqual(ed_outrider.meta_get(self.db, "probe"), 1)
        self.assertIn("apply_own_changes", self.state.tail_error)

    def test_a_follow_up_that_wrote_nothing_does_not_reload_the_reader(self):
        """S4-B14: one that kept raising rolled back and reloaded the whole reader every second."""
        def fails():
            raise RuntimeError("boom")
        with unittest.mock.patch.object(self.state, "maybe_refresh", fails), \
                unittest.mock.patch.object(self.j, "reload") as reload:
            self.tick()
            self.tick()
        reload.assert_not_called()
        self.assertIn("maybe_refresh", self.state.tail_error)

    def test_a_step_before_the_commit_does_not_hold_the_lines_back(self):
        """S1x-S1: a step before the commit that raises (not a database error) is reported, and the tick still commits
        what it read."""
        def fails():
            raise KeyError("legs")
        with unittest.mock.patch.object(self.state, "carrier_trip_follow", fails):
            ed_outrider.meta_set(self.db, "probe", 2)   # what the tick's lines wrote
            self.tick()
        self.db.rollback()
        self.assertEqual(ed_outrider.meta_get(self.db, "probe"), 2)
        self.assertIn("carrier_trip_follow", self.state.tail_error)

    def test_watch_survives_an_error_out_of_tick(self):
        """S4-S5: an error raised by tick() itself (its own handler failing) ended watch(), silently."""
        calls = []

        def tick(_):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("a meta value that does not parse")

        async def go():
            with unittest.mock.patch.object(self.state, "tick", tick), \
                    unittest.mock.patch.object(ed_outrider, "POLL_SECONDS", 0):
                task = asyncio.ensure_future(self.state.watch())
                for _ in range(1000):   # bounded: a watch() that died must fail the test, not hang it
                    if len(calls) >= 3 or task.done():
                        break
                    await asyncio.sleep(0)
                bad = [n["key"] for n in self.state.notices.active()]
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, ValueError):
                    await task
                return bad
        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(go())
        self.assertGreaterEqual(len(calls), 3)                            # kept going
        self.assertNotIn("tick_failed", [n["key"] for n in self.state.notices.active()])   # cleared once it worked

    def test_a_task_that_dies_says_so(self):
        """S4-B11 / S7-B1: a long-lived task ending with an error prints it and raises a notice; a cancelled one does not."""
        async def dies():
            raise RuntimeError("database is locked")

        async def cancelled():
            await asyncio.sleep(10)

        async def go():
            t = self.state.watch_task(asyncio.ensure_future(dies()), "upload:eddn")
            with contextlib.suppress(RuntimeError):
                await t
            c = self.state.watch_task(asyncio.ensure_future(cancelled()), "watch")
            await asyncio.sleep(0)
            c.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await c
            await asyncio.sleep(0)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            asyncio.run(go())
        keys = [n["key"] for n in self.state.notices.active()]
        self.assertEqual(keys, ["task_died:upload:eddn"])
        self.assertIn("EDDN sending stopped", self.state.notices.active()[0]["text"])
        self.assertIn("database is locked", err.getvalue())

    def test_the_overlay_watcher_survives_an_error(self):
        """S7-S7: one exception in overlay_window_tick ended the watcher for the session."""
        calls = []

        def tick(last):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return last

        async def go():
            with unittest.mock.patch.object(self.state, "overlay_window_tick", tick), \
                    unittest.mock.patch.object(ed_outrider, "OVERLAY_TICK_S", 0):
                task = asyncio.ensure_future(self.state.watch_overlay_window())
                for _ in range(1000):
                    if len(calls) >= 3 or task.done():
                        break
                    await asyncio.sleep(0)
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, RuntimeError):
                    await task
        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(go())
        self.assertGreaterEqual(len(calls), 3)


class DiskWontWrite(unittest.TestCase):
    """Round 10's S18: a database the disk will not take writes for (full, read-only) failed every tick with a
    traceback a second and a bare "OperationalError" on the page. Now the traceback is printed once and a card says
    what is wrong in words, with the database's folder and its free space; both are cleared only by a tick that really
    wrote, so an idle tick (nothing to write, so nothing fails) cannot make the card flicker."""

    def setUp(self):
        import os
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name
        path = os.path.join(tmp.name, "ed_outrider.sqlite")
        self.db = ed_outrider.open_db(path)
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.db_path = path
        self.size = 0   # what each tick's "journal line" writes (0: an idle tick)

    def write(self):
        if self.size:
            ed_outrider.meta_set(self.db, "probe", "x" * self.size)
            self.size += 1   # a new value each tick: a real write each time

    def tick(self):
        err = io.StringIO()
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), contextlib.redirect_stderr(err), \
                unittest.mock.patch.object(self.state, "maybe_unsold", lambda: None), \
                unittest.mock.patch.object(self.state, "journals_reachable", self.write):
            self.state.tick({})
        return err.getvalue()

    def card(self):
        return next((n for n in self.state.notices.active() if n["key"] == "db_write"), None)

    def test_a_full_disk_one_traceback_and_a_card(self):
        self.size = 200000
        self.assertEqual(self.tick(), "")   # room enough: it writes
        pages = self.db.execute("PRAGMA page_count").fetchone()[0]
        self.db.execute(f"PRAGMA max_page_count = {pages}")   # SQLite's own SQLITE_FULL from here on
        self.size = 400000
        out = "".join(self.tick() for _ in range(3))
        self.assertEqual(out.count("Traceback"), 1, out)
        self.assertIn("database or disk is full", out)
        card = self.card()
        self.assertIsNotNone(card)
        self.assertEqual((card["level"], card["action"]), ("bad", "open:server"))
        self.assertIn("is full", card["text"])
        self.assertIn(self.folder, card["text"])
        self.assertIn("MB free", card["text"])
        self.assertIn("OperationalError", self.state.tail_error)
        # an idle tick writes nothing: the card stays
        size, self.size = self.size, 0
        self.tick()
        self.assertIsNotNone(self.card())
        # room again and a tick that writes: the card goes, and a new failure prints its traceback again
        self.db.execute("PRAGMA max_page_count = 1073741823")
        self.size = size
        self.assertEqual(self.tick(), "")
        self.assertIsNone(self.card())
        self.db.execute(f"PRAGMA max_page_count = {self.db.execute('PRAGMA page_count').fetchone()[0]}")
        self.size = 900000
        self.assertEqual(self.tick().count("Traceback"), 1)

    def test_a_read_only_database(self):
        self.size = 10
        self.db.execute("PRAGMA query_only = 1")   # SQLite's own SQLITE_READONLY
        out = self.tick() + self.tick()
        self.assertEqual(out.count("Traceback"), 1, out)
        self.assertIn("read-only", self.card()["text"])
        self.db.execute("PRAGMA query_only = 0")
        self.tick()
        self.assertIsNone(self.card())

    def test_another_error_gets_no_card(self):
        self.assertEqual([ed_outrider.db_write_kind(e) for e in (
            sqlite3_error("database is locked"), sqlite3_error("disk I/O error"), RuntimeError("disk is full"))],
            [None, "ioerr", None])


def sqlite3_error(msg):
    import sqlite3
    return sqlite3.OperationalError(msg)   # no sqlite_errorcode: matched by its message


if __name__ == "__main__":
    unittest.main()
