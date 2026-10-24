"""The rest of the server, the full Fable review of 2026-10-23 (fix batch 5): S3-B6, S4-B6, S4-B9, S4-B10, S4-B12."""
import threading
import time
import types
import unittest
import unittest.mock

from support import ed_outrider
import outrider.notices  # noqa: E402
import outrider.target  # noqa: E402


class ServerFixes(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_an_unchanged_notice_keeps_its_place(self):
        """S4-B12: setting a notice again as it was moved it to the end of the banner."""
        b = outrider.notices.Board()
        b.set("a", "first")
        b.set("b", "second")
        self.assertFalse(b.set("a", "first"))
        self.assertEqual([n["key"] for n in b.active()], ["a", "b"])

    def test_search_keeps_only_what_it_shows(self):
        """S4-B10: every match of every search was kept for the life of the server."""
        s = ed_outrider.Searcher(self.state)
        with unittest.mock.patch.object(ed_outrider, "SEARCH_MAX_RESULTS", 3):
            for run in range(5):
                found = {run * 10 + i: (f"S{run}-{i}", 0, 0, 0) for i in range(6)}
                results = [{"id": str(k), "distance": i} for i, k in enumerate(found)]
                s.keep_found(found, results)
            self.assertLessEqual(len(s.found), 6)
            self.assertIn(40, s.found)                                   # the last search's shown rows
            self.assertNotIn(45, s.found)                                # past the rows shown

    def test_the_danger_wait_judges_the_runs_own_reading(self):
        """S4-B6: start_autotarget_run's guard read Status.json itself, the danger-wait the watcher's (older) copy."""
        T = outrider.target
        now = time.time()
        self.j.pos = {"id64": 7, "ts": ed_outrider.iso_ts(now - 5)}
        self.j.jump_arrival = {"id64": 7, "ts": ed_outrider.iso_ts(now - 5)}
        self.j.status_json = {"flags": 0}                               # the watcher's copy: not in danger yet
        fresh = {"flags": T.FLAG_IN_DANGER}
        self.assertIsNone(self.state.arrival_danger_until(now))
        self.assertIsNotNone(self.state.arrival_danger_until(now, st=fresh))

    def test_skip_known_is_named_as_the_reason(self):
        """S3-B6: with Skip known passing the rest over, the reason said every system was visited."""
        ed_outrider.meta_set(self.db, "boxel_skip_known", True)
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(time.time() - 60), "StarSystem": "Drojau TF-H c13-0",
                       "SystemAddress": 2870515095985, "StarPos": [-4179.0, -64.0, 3339.0]})
        real = ed_outrider.boxel_next_number
        with unittest.mock.patch.object(ed_outrider, "boxel_next_number",
                                        lambda v, s, e, skip=False: None if skip else real(v, s, e)):
            tgt, why = self.state.boxel_target()
        self.assertIsNone(tgt)
        self.assertIn("Skip known is on", why)

    def test_the_boxels_run_has_its_own_token(self):
        """S4-B9: the boxel's automatic run took the Highway run's cancel token: the Highway's switch or a cleared route
        stopped it, and its own switch did not."""
        tok = threading.Event()
        self.state._boxel_cancel, self.state._autotarget_cancel = tok, None
        self.state.cancel_autotarget(route=True)                        # the Highway's route cleared
        self.assertFalse(tok.is_set())
        self.state.set_boxel_auto(False)                                 # its own switch
        self.assertTrue(tok.is_set())
        self.assertFalse(ed_outrider.meta_get(self.db, "boxel_auto"))
        honker = types.SimpleNamespace(available=True, opened=[], closed=[])
        honker.open, honker.close = honker.opened.append, honker.closed.append
        self.state.honker = honker
        self.state.set_boxel_auto(True)
        self.state.set_boxel_auto(False)
        self.assertEqual((honker.opened, honker.closed), (["boxel"], ["boxel"]))   # it holds the keyboard while on


    def test_a_journal_folder_that_goes_away_is_said(self):
        """Review 2026-10-23 S9-S21: a share that dropped while Outrider ran showed "linked · no game" with nothing saying
        why. Two looks missing: a card; back: gone. A folder never seen is the start-up's to say."""
        import contextlib
        import io
        there = {"/srv/j": True, "/never": False}
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", list(there)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            look = lambda: self.state.journals_reachable(isdir=lambda d: there[d])
            look()
            there["/srv/j"] = False
            look()
            self.assertEqual(self.state.notices.active(), [])           # one look: not yet
            look()
            self.assertEqual([n["key"] for n in self.state.notices.active()], ["journals_gone:/srv/j"])
            there["/srv/j"] = True
            look()
            self.assertEqual(self.state.notices.active(), [])

    def test_a_plot_behind_another_says_it_is_waiting(self):
        """Review 2026-10-23 S1-S2: Spansh's plots go one at a time; the second sat on "Asking Spansh…" for the whole of
        the first. Its record says waiting while the other holds the turn."""
        import asyncio
        from support import _HwSession
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(200, {"job": "j1", "status": "ok", "result": {"system_jumps": []}})])
        rec = {"state": "running"}

        async def go():
            await sp.sem_plot.acquire()   # another plot holds the turn
            task = asyncio.ensure_future(sp.plot("https://spansh.co.uk/api/route", {}, poll=0.01, waiting=rec))
            await asyncio.sleep(0.05)
            seen = rec.get("waiting")
            sp.sem_plot.release()
            await task
            return seen
        self.assertTrue(asyncio.run(go()))
        self.assertFalse(rec["waiting"])

    def test_a_cancelled_search_stops_its_worker(self):
        """Review 2026-10-23 S4-S6: start() cancelled the task, but the worker thread matching every cached system went
        on to the end; a newer search sets the older one's stop event, and the matching stops."""
        import asyncio
        s = ed_outrider.Searcher(self.state)
        stop = threading.Event()
        stop.set()
        crit = {"bio": None, "mining": None}
        systems = {i: (f"S{i}", 0.0, 0.0, 0.0, []) for i in range(10)}
        with self.assertRaises(ed_outrider.SearchStopped):
            s.match(self.db, {"x": 0, "y": 0, "z": 0}, "online", 10, crit, [], systems, 10, None, stop=stop)
        with unittest.mock.patch.object(ed_outrider, "match_system", lambda name, records, crit: {}):
            self.assertEqual(len(s.match(self.db, {"x": 0, "y": 0, "z": 0}, "online", 10, crit, [], systems, 10, None)[0]), 10)

        async def go():
            with unittest.mock.patch.object(s, "_run", lambda seq, params, stop: asyncio.sleep(1)):
                s.start({})
                first = s.stop
                s.start({})
                s.task.cancel()
                return first.is_set(), s.stop.is_set()
        self.assertEqual(asyncio.run(go()), (True, False))


class SuitLow(unittest.TestCase):
    """S9-S7: the suit's oxygen or health running low on foot on a planet, with data aboard: one danger moment per rise."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.unsold = {"total": 412_000_000}

    def look(self, flags2):
        self.state.suit_watch({"live": True, "flags2": flags2}, None, 1000)
        return [(m["what"], m["value"], m["dist"]) for m in self.j.moments if m["kind"] == "suit"]

    def test_once_per_rise_on_a_planet_with_data_aboard(self):
        planet, oxygen, health = 1 | 1 << 4, 1 << 6, 1 << 7
        self.assertEqual(self.look(planet), [])
        self.assertEqual(self.look(planet | oxygen), [("oxygen", 412_000_000, None)])
        self.assertEqual(len(self.look(planet | oxygen)), 1)                 # the same rise: said once
        self.assertEqual(len(self.look(planet | oxygen | health)), 2)        # health too now
        self.look(planet)
        self.assertEqual(len(self.look(planet | oxygen)), 3)                 # low again later: said again

    def test_quiet_in_a_station_and_with_nothing_aboard(self):
        self.assertEqual(self.look(1 | 1 << 3 | 1 << 6), [])                 # on foot in a station
        self.look(0)
        self.state.unsold = {"total": 0}
        self.assertEqual(self.look(1 | 1 << 4 | 1 << 6), [])


if __name__ == "__main__":
    unittest.main()
