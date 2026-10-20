"""Unit tests: the uploaders' foundation (outrider/uploads.py; PLAN-edmc-functionality part A): the session, the live
gate through the journal reader, priming a file met part way through, and the outbox. Nothing is sent anywhere.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import glob
import json
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock
import zlib

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts  # noqa: E402


def addr(name):
    """A made-up system's SystemAddress from its name: the same in every run (hash() of a str is seeded per process,
    and two names once shared hash % 1000, so a jump's signals counted as the system you were in)."""
    return zlib.crc32(name.encode())


def now_ts(ago=0):
    return iso_ts(time.time() - ago)


def header(ts, version="4.2.0.100", build="r312345/r0 "):
    return {"timestamp": ts, "event": "Fileheader", "part": 1, "language": "English/UK", "Odyssey": True,
            "gameversion": version, "build": build}


def loadgame(ts, cmdr="Briadin", **kw):
    return dict({"timestamp": ts, "event": "LoadGame", "FID": "F123", "Commander": cmdr, "Horizons": True,
                 "Odyssey": True, "Ship": "Mandalay", "ShipID": 7}, **kw)


def location(ts, addr=10, name="Sol", pos=(0.0, 0.0, 0.0), **kw):
    return dict({"timestamp": ts, "event": "Location", "StarSystem": name, "SystemAddress": addr, "StarPos": list(pos)}, **kw)


class SessionTests(unittest.TestCase):

    def test_follows_the_journal(self):
        s = U.Session()
        s.feed(header("2026-10-08T10:00:00Z"), "Journal.2026-10-08T100000.01.log")
        self.assertEqual((s.gameversion, s.gamebuild, s.blocked()), ("4.2.0.100", "r312345/r0 ", "commander"))
        s.feed(loadgame("2026-10-08T10:00:01Z", Horizons=True))
        self.assertEqual((s.cmdr, s.fid, s.horizons, s.odyssey, s.ship_id, s.blocked()), ("Briadin", "F123", True, True, 7, None))
        s.feed(location("2026-10-08T10:00:02Z", Docked=True, MarketID=99, StationName="Abraham Lincoln", Body="Earth", BodyID=3, BodyType="Planet"))
        self.assertEqual((s.addr, s.system, s.pos, s.market_id, s.station, s.body_id), (10, "Sol", [0.0, 0.0, 0.0], 99, "Abraham Lincoln", 3))
        self.assertTrue(s.located(10) and not s.located(11))
        s.feed({"event": "Undocked", "timestamp": "2026-10-08T10:01:00Z"})
        s.feed({"event": "FSDJump", "timestamp": "2026-10-08T10:02:00Z", "StarSystem": "B", "SystemAddress": 11, "StarPos": [1, 2, 3]})
        self.assertEqual((s.addr, s.market_id, s.body), (11, None, None))
        s.feed({"event": "JoinACrew", "timestamp": "2026-10-08T10:03:00Z", "Captain": "Someone"})
        self.assertEqual((s.blocked(), s.addr), ("crew", None))
        s.feed({"event": "QuitACrew", "timestamp": "2026-10-08T10:04:00Z", "Captain": "Someone"})
        self.assertIsNone(s.blocked())

    def test_flags_left_out_and_blocked_sessions(self):
        s = U.Session()
        s.feed(header("2026-10-08T10:00:00Z", version="3.8.0.404"), "Journal.x.log")
        s.feed({"timestamp": "2026-10-08T10:00:01Z", "event": "LoadGame", "Commander": "B", "Horizons": True})
        self.assertEqual((s.horizons, s.odyssey, s.blocked()), (True, None, "legacy"))   # no Odyssey key: left out
        s.feed(header("2026-10-08T11:00:00Z", version="4.0.0.1500 beta"), "Journal.y.log")
        s.feed(loadgame("2026-10-08T11:00:01Z"))
        self.assertEqual(s.blocked(), "beta")
        s.feed(header("2026-10-08T12:00:00Z"), "JournalBeta.z.log")
        s.feed(loadgame("2026-10-08T12:00:01Z"))
        self.assertEqual(s.blocked(), "beta")
        s.feed(header("2026-10-08T13:00:00Z", version=""), "Journal.w.log")
        s.feed(loadgame("2026-10-08T13:00:01Z"))
        self.assertEqual(s.blocked(), "version")

    def test_live_gate(self):
        now = time.time()
        self.assertTrue(U.live_line(iso_ts(now - 10), now))
        self.assertFalse(U.live_line(iso_ts(now - U.MAX_AGE_S - 5), now))   # an old line (a catch-up through NFS...)
        self.assertTrue(U.live_line(iso_ts(now + 60), now))                 # the game PC's clock a minute ahead
        self.assertFalse(U.live_line("not a time", now))


class HubThroughTheReader(unittest.TestCase):
    """The hub sees lines only from the live folders, queues only from the running tail."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, "Journal.2026-10-08T100000.01.log")
        echo = lambda ev, session: [("echo/1", {"event": ev["event"], "system": session.system})]
        self.on = True
        self.hub = U.UploadHub(self.db, {"test": echo}, enabled=lambda s: self.on)
        self.j.uploads = self.hub

    def write(self, *events):
        with open(self.path, "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def rows(self):
        return [(r["schema"], json.loads(r["message"])["event"]) for r in self.db.execute("SELECT * FROM upload_queue ORDER BY id")]

    def test_catchup_then_live(self):
        self.write(header(now_ts(30)), loadgame(now_ts(29)), location(now_ts(28)))
        self.j.scan_dir(self.dir, upload="catchup")          # the start-up scan: state only
        self.assertEqual(self.rows(), [])
        self.assertEqual((self.hub.session.cmdr, self.hub.session.system), ("Briadin", "Sol"))
        self.write({"timestamp": now_ts(5), "event": "FSDJump", "StarSystem": "B", "SystemAddress": 11, "StarPos": [1, 2, 3]})
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.rows(), [("echo/1", "FSDJump")])
        r = self.db.execute("SELECT cmdr, gameversion, gamebuild, source FROM upload_queue").fetchone()
        self.assertEqual(tuple(r)[:3], ("Briadin", "4.2.0.100", "r312345/r0 "))
        self.assertTrue(r["source"].startswith("Journal.2026-10-08T100000.01.log:"))

    def test_old_lines_legacy_folders_and_off(self):
        week = 8 * 86400
        self.write(header(now_ts(week)), loadgame(now_ts(week - 1)), location(now_ts(week - 2)))
        self.j.scan_dir(self.dir, upload="live")                # live, but over a week old: nothing (the cap)
        self.assertEqual(self.rows(), [])
        self.write({"timestamp": now_ts(1), "event": "Music", "MusicTrack": "Exploration"})
        self.j.scan_dir(self.dir)                               # a legacy folder: the hub never sees it
        self.assertEqual(self.rows(), [])
        self.on = False
        self.write({"timestamp": now_ts(1), "event": "Music", "MusicTrack": "Combat"})
        self.j.scan_dir(self.dir, upload="live")                # uploads off: nothing either
        self.assertEqual(self.rows(), [])

    def test_restart_mid_file_primes_the_session(self):
        self.write(header(now_ts(60)), loadgame(now_ts(59)), location(now_ts(58), addr=42, name="Here"))
        size = os.path.getsize(self.path)
        self.db.execute("INSERT INTO journal_files (path, offset) VALUES (?, ?)", (self.path, size))
        self.j.reload()                                          # Outrider stopped here; a new start
        self.write({"timestamp": now_ts(2), "event": "Scan", "BodyName": "Here 1", "BodyID": 1, "SystemAddress": 42,
                    "StarSystem": "Here", "ScanType": "Detailed"})
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.rows(), [("echo/1", "Scan")])
        self.assertEqual((self.hub.session.gameversion, self.hub.session.cmdr, self.hub.session.addr), ("4.2.0.100", "Briadin", 42))

    def test_once_per_line_and_rolled_back_with_the_tick(self):
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        self.assertTrue(U.enqueue(self.db, "test", "echo/1", "J.log:100", now_ts(5), s, {"a": 1}))
        self.assertFalse(U.enqueue(self.db, "test", "echo/1", "J.log:100", now_ts(5), s, {"a": 1}))   # the same line again
        self.assertTrue(U.enqueue(self.db, "other", "echo/1", "J.log:100", now_ts(5), s, {"a": 1}))   # another service
        self.db.commit()
        U.enqueue(self.db, "test", "echo/1", "J.log:200", now_ts(5), s, {"a": 2})
        self.db.rollback()                                        # a failed tick
        self.assertEqual(self.db.execute("SELECT count(*) FROM upload_queue").fetchone()[0], 2)

    def test_outbox_settle_and_prune(self):
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        for i in range(3):
            U.enqueue(self.db, "test", "x/1", f"J.log:{i}", now_ts(5), s, {"i": i})
        now = time.time()
        rows = U.due(self.db, "test", now)
        self.assertEqual([json.loads(r["message"])["i"] for r in rows], [0, 1, 2])
        U.settle(self.db, rows[0]["id"], "sent", "200 OK", now)
        U.settle(self.db, rows[1]["id"], "queued", "503", now, retry_in=60)       # back off
        U.settle(self.db, rows[2]["id"], "dropped", "400 FAIL: Schema Validation", now)
        self.assertEqual([json.loads(r["message"])["i"] for r in U.due(self.db, "test", now)], [])
        self.assertEqual([json.loads(r["message"])["i"] for r in U.due(self.db, "test", now + 61)], [1])
        c = U.counts(self.db, "test")
        self.assertEqual((c["queued"], c["sent_24h"], c["dropped_24h"]), (1, 1, 1))
        U.prune(self.db, now + 8 * 86400)
        self.assertEqual(self.db.execute("SELECT count(*) FROM upload_queue").fetchone()[0], 1)   # the queued one stays

    def test_a_reread_keeps_the_outbox(self):
        self.assertNotIn("upload_queue", ed_outrider.RESET_JOURNAL_DATA)

    def test_a_failed_tick_puts_the_session_back(self):
        self.write(header(now_ts(30)), loadgame(now_ts(29)), location(now_ts(28)))
        self.j.scan_dir(self.dir, upload="catchup")
        cp = self.j.checkpoint()
        self.hub.session.feed({"timestamp": now_ts(5), "event": "FSDJump", "StarSystem": "B", "SystemAddress": 11, "StarPos": [1, 2, 3]})
        self.j.restore(cp)                                       # the tick's lines will be handled again
        self.assertEqual(self.hub.session.system, "Sol")


class Continuation(unittest.TestCase):
    """A long session goes on in a part-2 file (Fileheader "part": 2, no LoadGame after it): the session, the commander
    and the place carry on (2026-10-09: every upload stopped there until the next login)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.p1 = os.path.join(self.dir, "Journal.2026-10-08T100000.01.log")
        self.p2 = os.path.join(self.dir, "Journal.2026-10-08T180000.02.log")
        with open(self.p1, "w", encoding="utf-8") as f:
            for e in (header(now_ts(900)), loadgame(now_ts(899)),
                      {"timestamp": now_ts(800), "event": "FSDJump", "StarSystem": "B", "SystemAddress": 11, "StarPos": [1, 2, 3]},
                      {"timestamp": now_ts(700), "event": "Continued", "Part": 2}):
                f.write(json.dumps(e) + "\n")
        self.lines2 = [dict(header(now_ts(699)), part=2), {"timestamp": now_ts(600), "event": "Scan", "BodyName": "B 1"}]
        with open(self.p2, "w", encoding="utf-8") as f:
            for e in self.lines2:
                f.write(json.dumps(e) + "\n")

    def test_session_goes_on(self):
        s = U.Session()
        for p in (self.p1, self.p2):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    s.feed(json.loads(line), os.path.basename(p))
        self.assertEqual((s.blocked(), s.cmdr, s.addr), (None, "Briadin", 11))
        self.assertTrue(U.continued(self.lines2[0]))
        self.assertFalse(U.continued(header(now_ts(1))))
        self.assertEqual(U.continued_from(self.p2), self.p1)
        self.assertIsNone(U.continued_from(self.p1))

    def test_started_in_a_part_2(self):
        """Outrider started part way through a part-2 file: it learns who and where from the file before it."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        hub = U.UploadHub(db, {"echo": lambda ev, s: [("echo/1", {"event": ev["event"]})] if ev["event"] == "Scan" else []},
                          enabled=lambda s: True)
        off = len((json.dumps(self.lines2[0]) + "\n").encode())
        self.assertEqual(hub.line(self.p2, off, json.dumps(self.lines2[1]).encode(), "live"), 1)
        self.assertEqual((hub.session.cmdr, hub.session.addr), ("Briadin", 11))

    def test_catch_up_from_a_part_2(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        hub = U.UploadHub(db, {"echo": lambda ev, s: [("echo/1", {"event": ev["event"]})] if ev["event"] == "Scan" else []},
                          enabled=lambda s: True)
        hub.marks["echo"] = [os.path.basename(self.p2), 0, None]          # stopped at the top of the part-2 file
        self.assertEqual(hub.catch_up("echo", [self.dir], {self.p1: os.path.getsize(self.p1), self.p2: os.path.getsize(self.p2)}), 1)


class Settings(unittest.TestCase):

    def test_config(self):
        self.assertEqual(U.upload_settings({})["uploads"], {"eddn": {"enabled": False}, "edsm": {"enabled": False},
                                                          "inara": {"enabled": False}})
        got = U.upload_settings({"eddn": {"enabled": True, "test": True}, "edsm": {"enabled": "yes"}, "inara": {"enabled": True}})["uploads"]
        self.assertEqual(got, {"eddn": {"enabled": True}, "edsm": {"enabled": False}, "inara": {"enabled": True}})   # a non-bool is the default

    def test_test_mode_is_the_developers(self):
        """EDDN's test schemas: an environment variable, never a setting (nothing in the config reads it)."""
        self.assertFalse(U.eddn_test_mode({}))
        self.assertTrue(U.eddn_test_mode({U.TEST_ENV: "1"}))
        self.assertFalse(U.eddn_test_mode({U.TEST_ENV: "0"}))
        self.assertNotIn("test", U.upload_settings({"eddn": {"test": True}})["uploads"]["eddn"])


class StateSwitches(unittest.TestCase):
    """[eddn]/[edsm] enabled, switched only in Settings -> Uploads, which writes the config file; never in --simulate,
    held on a refused key."""

    def setUp(self):
        import tempfile
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state.config_path = os.path.join(tmp.name, "ed_outrider.toml")

    def written(self):
        return U.upload_settings(ed_outrider.load_config(self.state.config_path))["uploads"]

    def test_switches(self):
        st = self.state
        self.assertIs(self.j.uploads, st.uploads_hub)
        self.assertEqual((st.upload_on("eddn"), st.upload_on("edsm"), st.upload_on("inara")), (False, False, False))
        st.upload_cfg["eddn"]["enabled"] = True                  # as the config said at the start
        self.assertTrue(st.upload_on("eddn"))
        st.set_upload("eddn", False)
        self.assertFalse(st.upload_on("eddn"))
        self.assertEqual(self.written()["eddn"]["enabled"], False)   # written into the config file
        st.set_upload("edsm", True)
        self.assertTrue(st.upload_on("edsm"))
        self.assertEqual(self.written(), {"eddn": {"enabled": False}, "edsm": {"enabled": True}, "inara": {"enabled": False}})
        st.upload_report("edsm", {"error": None, "at": 1, "results": [(1, "held", "203 Commander name/API Key not found", None)]})
        self.assertFalse(st.upload_on("edsm"))                   # waiting on the player
        self.assertEqual(st.uploads_summary()["edsm"]["held"], "203 Commander name/API Key not found")
        st.set_upload("edsm", True)                              # switching it on again clears the hold
        self.assertTrue(st.upload_on("edsm"))
        st.simulate = True
        self.assertFalse(st.upload_on("edsm"))

    def test_startup_line(self):
        """The console says whether each upload is on, and EDDN's test schemas whenever OUTRIDER_EDDN_TEST is set."""
        st = self.state
        with unittest.mock.patch.dict(os.environ, {U.TEST_ENV: ""}):
            self.assertEqual(st.uploads_line(), "uploads: EDDN off, EDSM off, Inara off (change them in Settings -> Uploads)")
        st.upload_cfg["eddn"]["enabled"] = True
        with unittest.mock.patch.dict(os.environ, {U.TEST_ENV: "1"}):
            self.assertEqual(st.uploads_line(), "uploads: EDDN on (TEST: EDDN's test schemas only, OUTRIDER_EDDN_TEST is set), "
                                                "EDSM off, Inara off (change them in Settings -> Uploads)")
            self.assertTrue(st.uploads_summary()["eddn"]["test"])

    def test_written_in_place(self):
        """The switch rewrites only its own key: the rest of the file and its comments stay; a file that cannot be
        written still switches for this run."""
        with open(self.state.config_path, "w", encoding="utf-8") as f:
            f.write('# mine\n[server]\nport = 8030   # kept\n\n[eddn]\nenabled = false\n')
        self.state.set_upload("eddn", True)
        with open(self.state.config_path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("# mine", text)
        self.assertIn("port = 8030   # kept", text)
        self.assertIn("[eddn]\nenabled = true", text)
        self.assertIsNone(self.state.set_upload("eddn", True))
        self.state.uploads_hub.set_mark("eddn", ("Journal.2026-10-01T000000.01.log", 100), "2026-10-01T00:00:00Z")
        self.state.uploads_hub.flush()
        self.assertIn("eddn", ed_outrider.meta_get(self.db, "upload_marks"))
        self.state.config_path = os.path.join(self.state.config_path, "not-a-folder", "x.toml")
        with unittest.mock.patch("sys.stderr"):
            note = self.state.set_upload("eddn", False)
        self.assertFalse(self.state.upload_on("eddn"))
        self.assertTrue(note.startswith("EDDN is off until Outrider stops, but the config file could not keep it"), note)
        # its mark is gone with the switch: a next start reading enabled = true from the file starts from then, not from
        # where it was switched off (review 2026-10-11)
        self.assertNotIn("eddn", self.state.uploads_hub.marks)
        self.assertNotIn("eddn", ed_outrider.meta_get(self.db, "upload_marks") or {})

    def test_not_among_server_settings(self):
        secs = [s["section"] for s in self.state.config_info()["sections"]]
        self.assertNotIn("eddn", secs)
        self.assertNotIn("edsm", secs)
        out, status = self.state.config_save({"eddn": {"enabled": True}})   # POST /api/config: not this way
        self.assertEqual((status, out["error"]), (400, "[eddn] is switched in Settings -> Uploads"))
        self.assertFalse(os.path.exists(self.state.config_path))

    def test_endpoint(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = [(await c.post("/api/uploads", json={"service": "eddn", "on": True})).status]
                for bad in ({"service": "spansh", "on": True}, {"service": "eddn", "on": "yes"}, ["eddn"]):
                    out.append((await c.post("/api/uploads", json=bad)).status)
                return out
        self.assertEqual(asyncio.run(go()), [200, 400, 400, 400])
        self.assertTrue(self.state.upload_on("eddn"))


class Loop(unittest.TestCase):
    """upload_loop: each row settled as the sender says; a network failure waits (at least a minute, growing)."""

    def test_rounds(self):
        import asyncio
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        for i in range(3):
            U.enqueue(db, "eddn", "x/1", f"J.log:{i}", now_ts(5), s, {"i": i})
        db.commit()
        clock = [1000.0]
        calls, reports = [], []

        when = []

        async def send(rows):
            when.append(clock[0])
            calls.append([json.loads(r["message"])["i"] for r in rows])
            if len(calls) == 1:
                raise ConnectionError("unreachable")
            return [(rows[0]["id"], "sent", "200 OK", None), (rows[1]["id"], "dropped", "400 FAIL", None),
                    (rows[2]["id"], "queued", "503", 60)][:len(rows)]

        async def sleep(secs):
            clock[0] += max(secs, 1)
            if clock[0] > 1000 + 400:
                raise asyncio.CancelledError

        async def go():
            try:
                await U.upload_loop("eddn", db, send, lambda s: True, clock=lambda: clock[0], sleep=sleep,
                                    report=lambda s, o: reports.append(o["error"]))
            except asyncio.CancelledError:
                pass
        asyncio.run(go())
        self.assertEqual(calls[0], [0, 1, 2])                    # the first round: unreachable
        self.assertEqual(calls[1], [0, 1, 2])                    # again, a minute later (not at once)
        self.assertGreaterEqual(when[1] - when[0], 60)
        self.assertEqual(reports[0], "ConnectionError: unreachable")
        states = {json.loads(r["message"])["i"]: r["state"] for r in db.execute("SELECT * FROM upload_queue")}
        self.assertEqual(states, {0: "sent", 1: "dropped", 2: "queued"})


class OneUploaderAtATime(unittest.TestCase):
    """Lease files in the journal folder (.outrider/uploads-<id>.json) and EDMC's switches on this PC."""

    def setUp(self):
        import types
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.game_pc = False
        p = unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir])
        p.start()
        self.addCleanup(p.stop)

    def other(self, services, iid="otherpc1", host="erangel"):
        U.write_lease(self.dir, iid, {"host": host, "services": services, "beat": time.time()})

    def test_lease_written_and_others_seen(self):
        self.state.set_upload("eddn", True)
        self.state.refresh_leases()
        mine = os.path.join(self.dir, ".outrider", f"uploads-{self.state.leases.instance}.json")
        with open(mine, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["services"], ["eddn"])
        self.assertTrue(self.state.upload_on("eddn"))
        self.other(["eddn"])                                    # another Outrider claims it too: this one holds
        self.state.refresh_leases()
        self.assertFalse(self.state.upload_on("eddn"))
        self.assertEqual(self.state.uploads_summary()["eddn"]["held"], "also uploading from erangel")
        self.state.drop_leases()                                 # stopped: no claim, but a handover note
        with open(mine, encoding="utf-8") as f:
            note = json.load(f)
        self.assertEqual((note["services"], note["stopped"]), ([], True))
        self.assertIn("marks", note)

    def peer(self, iid):
        """Another State on its own database, sharing this journal folder, with the instance id `iid`."""
        import types
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        ed_outrider.meta_set(db, "instance_id", iid)
        st = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        st.game_pc = False
        st.upload_cfg = {"eddn": {"enabled": True}}   # switched on in its config (persisted, copied...)
        return st

    def test_two_switched_on_one_sends(self):   # Codex F1: both held for good, and that stretch was never sent
        for order in ("aaaaaa1", "zzzzzz1"), ("zzzzzz1", "aaaaaa1"):
            for f in glob.glob(os.path.join(self.dir, ".outrider", "*")):
                os.remove(f)
            first, second = self.peer(order[0]), self.peer(order[1])
            for _ in range(4):
                first.refresh_leases()
                second.refresh_leases()
                # the one already sending keeps it, whichever id is lower; the other gives way and says why
                self.assertEqual([first.upload_on("eddn"), second.upload_on("eddn")], [True, False], order)
                self.assertTrue(second.upload_conflict("eddn").startswith("also uploading from"))
            first.drop_leases()                                  # it stops: the other takes over
            second.refresh_leases()
            self.assertTrue(second.upload_on("eddn"))

    def test_started_together_lowest_id_sends(self):
        st = self.peer("mmmmmm1")
        U.write_lease(self.dir, "aaaaaa1", {"host": "pc", "services": [], "wanted": ["eddn"]})   # deciding too
        st.refresh_leases()
        self.assertFalse(st.upload_on("eddn"))                  # the lower id has it
        U.write_lease(self.dir, "aaaaaa1", {"host": "pc", "services": [], "wanted": []})
        U.write_lease(self.dir, "zzzzzz1", {"host": "srv", "services": [], "wanted": ["eddn"]})
        st.refresh_leases()
        self.assertTrue(st.upload_on("eddn"))                   # now this one is the lowest
        with open(os.path.join(self.dir, ".outrider", "uploads-mmmmmm1.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["services"], ["eddn"])   # written at once, not a minute later
        # both sending (each started before seeing the other): the higher id gives way
        U.write_lease(self.dir, "aaaaaa1", {"host": "pc", "services": ["eddn"], "wanted": ["eddn"]})
        st.refresh_leases()
        self.assertFalse(st.upload_on("eddn"))
        self.assertEqual(st.upload_conflict("eddn"), "also uploading from pc")

    def test_an_older_outrider_is_given_way_to(self):   # 2026.10.19 holds whenever another lease names the service
        st = self.peer("aaaaaa1")
        st.refresh_leases()
        self.assertTrue(st.upload_on("eddn"))
        self.other(["eddn"], iid="zzzzzz1")                     # no "wanted": an older version's lease
        st.refresh_leases()
        self.assertFalse(st.upload_on("eddn"))                  # gives way, whatever the ids...
        with open(os.path.join(self.dir, ".outrider", "uploads-aaaaaa1.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["services"], [])     # ...and stops naming it, so the older one sends

    def test_stale_lease_by_our_own_clock(self):
        clock = [1000.0]
        leases = U.Leases("me", clock=lambda: clock[0])
        self.other(["edsm"])
        self.assertIn("otherpc1", leases.others([self.dir]))
        clock[0] += U.LEASE_STALE_S + 1                          # unchanged for 5 minutes: a crashed instance
        self.assertEqual(leases.others([self.dir]), {})
        self.other(["edsm"], host="erangel again")               # it beats again
        self.assertIn("otherpc1", leases.others([self.dir]))

    def test_starting_rules(self):
        self.other(["eddn"])
        self.assertEqual(self.state.check_upload_start("eddn", False)[0], "other_instance")
        self.assertIn("Already uploading from erangel", self.state.check_upload_start("eddn", False)[1])
        self.assertIsNone(self.state.check_upload_start("edsm", False))
        # a read-only folder: a claim refuses with the author's words; none asks first
        with unittest.mock.patch.object(U, "write_lease", lambda *a, **k: False):
            self.assertEqual(self.state.check_upload_start("eddn", False),
                             ("other_instance", "Filesystem is read-only and another instance is set for upload"))
            self.assertEqual(self.state.check_upload_start("edsm", False)[0], "confirm_needed")
            self.assertIsNone(self.state.check_upload_start("edsm", True))

    def test_edmc_on_this_pc(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.makedirs(os.path.join(home, ".local", "share", "EDMarketConnector"))
        with open(os.path.join(home, ".local", "share", "EDMarketConnector", "config.toml"), "w") as f:
            f.write('[settings]\noutput = 2065\nedsm_out = 1\ninara_out = 0\n')
        got = U.edmc_uploads(home=home, environ={}, platform="linux", running=lambda: True)
        self.assertEqual(got, {"running": True, "eddn": True, "edsm": True, "inara": False})
        self.assertIsNone(U.edmc_uploads(home=self.dir, environ={}, platform="linux"))   # not installed here
        self.state.edmc = got
        self.state.set_upload("eddn", True)
        self.assertFalse(self.state.upload_on("eddn"))
        self.assertIn("EDMC on this PC", self.state.upload_conflict("eddn"))


class EdsmAccounts(unittest.TestCase):
    """EDSM's commander name and API key per in-game commander: stored here (meta), never served back."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle(loadgame("2026-10-08T10:00:00Z", cmdr="Briadin"))

    def test_accounts(self):
        key = "0123456789abcdef0123456789abcdef01234567"
        self.assertEqual(self.state.edsm_account_list(), [{"commander": "Briadin", "name": "Briadin", "set": False, "hint": None}])
        self.assertEqual(self.state.set_edsm_account("Briadin", "", "nope")[1], 400)                 # not a key
        out, status = self.state.set_edsm_account("Briadin", "Briadin EDSM", key)
        # the key's ends and length, to compare with edsm.net (the author's 203s, 2026-10-08), never the key itself
        self.assertEqual((status, out["accounts"]), (200, [{"commander": "Briadin", "name": "Briadin EDSM", "set": True,
                                                            "hint": "0123…4567 (40 characters)"}]))
        self.assertEqual(self.state.set_edsm_account("Briadin", "Renamed", "")[1], 200)             # an empty key keeps it
        self.assertEqual(self.state.edsm_accounts()["Briadin"], {"name": "Renamed", "key": key})
        self.assertNotIn(key, json.dumps(self.state.uploads_summary()))                          # never served
        self.assertNotIn(key[4:-4], json.dumps(self.state.uploads_summary()))                    # not even its middle
        self.assertNotIn(key, json.dumps(self.state.payload(), default=str))
        self.state.set_edsm_account("Briadin", remove=True)
        self.assertEqual(self.state.edsm_accounts(), {})
        self.assertNotIn("edsm_accounts", ed_outrider.RESET_JOURNAL_DATA)                        # a re-read keeps them


class MarksAndCatchUp(unittest.TestCase):
    """Part A4 (the author's idea): each service's mark says how far it has queued; at start it catches up from there
    (what was played while Outrider was not running, at most a week back); a re-read sends nothing again; switching on
    starts at another instance's handover mark, else now."""

    def setUp(self):
        import types
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        p = unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir])
        p.start()
        self.addCleanup(p.stop)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.game_pc = False
        cfg_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cfg_dir)
        self.state.config_path = os.path.join(cfg_dir, "ed_outrider.toml")   # where the switch is written
        self.path = os.path.join(self.dir, "Journal.2026-10-08T100000.01.log")
        echo = lambda ev, session: [("echo/1", {"event": ev["event"]})] if ev["event"] in ("FSDJump", "Scan") else []
        self.state.uploads_hub.builders = {"eddn": echo}

    def write(self, *events):
        with open(self.path, "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def jump(self, ago, name="B"):
        return {"timestamp": now_ts(ago), "event": "FSDJump", "StarSystem": name, "SystemAddress": addr(name),
                "StarPos": [1, 2, 3]}

    def queued(self):
        return [json.loads(r["message"]) for r in self.db.execute("SELECT message FROM upload_queue ORDER BY id")]

    def test_switching_on_starts_now_then_live_then_catch_up(self):
        self.write(header(now_ts(7200)), loadgame(now_ts(7199)), self.jump(7000, "Old"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)                      # on: from now, never the history before it
        self.assertEqual(self.queued(), [])
        self.write(self.jump(600, "Live"))                       # ten minutes ago, read live (NFS late): sent
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        self.assertEqual(len(self.queued()), 1)
        mark = ed_outrider.meta_get(self.db, "upload_marks")["eddn"]
        # Outrider stops; the game goes on; Outrider starts again
        self.write(self.jump(300, "WhileDown1"), self.jump(200, "WhileDown2"))
        db2 = self.db
        j2 = ed_outrider.Journals(db2)
        j2.scan_dir(self.dir, commit_each=True, upload="catchup")   # the start-up scan (no hub yet)
        import types
        st2 = ed_outrider.State(db2, j2, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        st2.game_pc = False
        st2.config_path = self.state.config_path                 # the switch, as run() reads it from the config file
        st2.upload_cfg = U.upload_settings(ed_outrider.load_config(st2.config_path))["uploads"]
        self.assertTrue(st2.upload_on("eddn"))
        st2.uploads_hub.builders = {"eddn": self.state.uploads_hub.builders["eddn"]}
        self.assertEqual(st2.uploads_hub.marks["eddn"], mark)
        self.assertEqual(st2.catch_up_uploads(), 2)              # the two jumps made while it was down
        self.assertEqual(st2.catch_up_uploads(), 0)              # once
        self.assertEqual(len(self.queued()), 3)

    def test_eddn_catches_up_an_hour_edsm_a_week(self):
        """After a gap, EDDN gets only the last hour's lines (eddn.CATCHUP_MAX_S); EDSM gets up to a week."""
        self.write(header(now_ts(3 * 3600)), loadgame(now_ts(3 * 3600 - 1)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        edsm = lambda ev, session: [(ev["event"], {"event": ev["event"]})] if ev["event"] == "FSDJump" else []
        self.state.uploads_hub.builders["edsm"] = edsm
        self.state.set_upload("eddn", True)
        self.state.set_upload("edsm", True)
        self.write(self.jump(2 * 3600, "TwoHoursAgo"), self.jump(600, "TenMinutesAgo"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")    # read at a start: caught up below
        self.state.catch_up_uploads()
        got = [(r["service"], json.loads(r["message"])["event"], r["created"]) for r in
               self.db.execute("SELECT service, message, created FROM upload_queue ORDER BY id")]
        self.assertEqual(len([g for g in got if g[0] == "eddn"]), 1)       # only the ten-minute-old jump
        self.assertEqual(len([g for g in got if g[0] == "edsm"]), 2)       # both

    def test_a_reread_sends_nothing_again(self):
        self.write(header(now_ts(600)), loadgame(now_ts(599)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.write(self.jump(100))
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)    # a parser bump: every journal read from 0 again
        j2 = ed_outrider.Journals(self.db)
        j2.scan_dir(self.dir, commit_each=True, upload="catchup")
        import types
        st2 = ed_outrider.State(self.db, j2, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        st2.uploads_hub.builders = {"eddn": self.state.uploads_hub.builders["eddn"]}
        self.assertEqual(st2.catch_up_uploads(), 0)
        self.assertEqual(len(self.queued()), 1)

    def test_handover_from_another_instance(self):
        self.write(header(now_ts(900)), loadgame(now_ts(899)), self.jump(800, "A"), self.jump(700, "Bsys"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        with open(self.path, "rb") as f:
            lines = f.read().split(b"\n")
        at_a = sum(len(x) + 1 for x in lines[:2])                # the other instance stopped after the first jump
        U.write_lease(self.dir, "otherpc1", {"host": "erangel", "services": [], "stopped": True,
                                             "marks": {"eddn": [os.path.basename(self.path), at_a, now_ts(800)]}})
        self.state.set_upload("eddn", True)                      # starts at its mark: the second jump is caught up
        self.assertEqual([m["event"] for m in self.queued()], ["FSDJump"])
        self.assertEqual(len(self.queued()), 1)

    def test_take_over_sends_what_was_played_since_the_other_stopped(self):
        """The Fable review of 2026-10-10 #1: while another Outrider sends, this one follows the journal (its mark moves,
        nothing is queued). When the other stops, the lines played between its stop and this one's next lease refresh
        (up to a minute) were sent by nobody; taking over now catches up from the other's handover mark."""
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        at_a = os.path.getsize(self.path)                          # a mark is the start of the last line handled: A
        self.write(self.jump(800, "A"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        mark = [os.path.basename(self.path), at_a, now_ts(800)]
        U.write_lease(self.dir, "aaaaaa0", {"host": "erangel", "services": ["eddn"], "wanted": ["eddn"], "beat": 1,
                                            "marks": {"eddn": mark}})
        self.state.refresh_leases()
        self.assertFalse(self.state.upload_on("eddn"))            # the other sends: this one follows
        self.write(self.jump(30, "Bsys"))                          # played after the other stopped, before the refresh
        U.write_lease(self.dir, "aaaaaa0", {"host": "erangel", "services": [], "stopped": True, "marks": {"eddn": mark}})
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.queued(), [])                        # followed: the mark moved past it, nothing queued
        self.state.refresh_leases()                                # the other's note: it stopped
        self.assertTrue(self.state.upload_on("eddn"))
        self.assertEqual([m["event"] for m in self.queued()], ["FSDJump"])   # Bsys, not lost
        self.state.refresh_leases()                                # nothing queued twice
        self.assertEqual(len(self.queued()), 1)

    def test_take_over_with_a_third_instance_following(self):
        """Three Outriders on one journal: A sends, this one and C follow. A stops; this one takes over and rewinds to A's
        handover mark, not to C's (C only followed, its mark at the journal's end): the stretch after A's stop was sent
        by nobody (review 2026-10-11)."""
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        at_a = os.path.getsize(self.path)
        self.write(self.jump(800, "A"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        mark = [os.path.basename(self.path), at_a, now_ts(800)]
        U.write_lease(self.dir, "aaaaaa0", {"host": "erangel", "services": ["eddn"], "wanted": ["eddn"], "beat": 1,
                                            "marks": {"eddn": mark}})
        self.state.refresh_leases()
        self.assertFalse(self.state.upload_on("eddn"))
        self.write(self.jump(30, "Bsys"))
        end = [os.path.basename(self.path), os.path.getsize(self.path), now_ts(30)]
        U.write_lease(self.dir, "zzzzzz9", {"host": "third", "services": [], "wanted": ["eddn"], "beat": 1,
                                            "marks": {"eddn": end}})   # C: follows, its mark past Bsys
        U.write_lease(self.dir, "aaaaaa0", {"host": "erangel", "services": [], "stopped": True, "marks": {"eddn": mark}})
        self.j.scan_dir(self.dir, upload="live")
        self.state.refresh_leases()
        self.assertTrue(self.state.upload_on("eddn"))
        self.assertEqual([m["event"] for m in self.queued()], ["FSDJump"])   # Bsys, from A's mark

    def test_cap(self):
        self.write(header(now_ts(9 * 86400)), loadgame(now_ts(9 * 86400 - 1)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.state.uploads_hub.set_mark("eddn", (os.path.basename(self.path), 0))
        self.write(self.jump(8 * 86400, "TooOld"), self.jump(60, "Fresh"))
        self.j.offsets[self.path] = os.path.getsize(self.path)
        self.assertEqual(self.state.uploads_hub.catch_up("eddn", [self.dir], dict(self.j.offsets)), 1)   # over a week: skipped


class CoreFixes(MarksAndCatchUp):
    """The bug check of 2026-10-09 (the upload core and the server's side of it)."""

    def test_old_format_journal_names_sort_by_time(self):
        """A 2021 journal named the old way (Journal.YYMMDDhhmmss.NN.log) sorts before a 2026 one: the mark never sticks
        in it (as text it sorted after every new name, and nothing was queued again)."""
        old = os.path.join(self.dir, "Journal.211015123456.01.log")
        with open(old, "w", encoding="utf-8") as f:
            f.write(json.dumps(header("2021-10-15T12:34:56Z")) + "\n")
        self.assertLess(U.name_key("Journal.211015123456.01.log"), U.name_key("Journal.2026-10-08T100000.01.log"))
        self.write(header(now_ts(600)), loadgame(now_ts(599)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.assertEqual(self.state.uploads_hub.marks["eddn"][0], os.path.basename(self.path))
        self.write(self.jump(10, "Live"))
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(len(self.queued()), 1)
        self.assertEqual([os.path.basename(p) for p in U.glob_journals(self.dir)],
                         ["Journal.211015123456.01.log", "Journal.2026-10-08T100000.01.log"])

    def test_handover_mark_in_an_old_format_file(self):
        """Another instance's handover mark in an old-format file compares by time with the reader's end."""
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        U.write_lease(self.dir, "other1", {"host": "x", "services": [], "stopped": True,
                                           "marks": {"eddn": ["Journal.261009120000.01.log", 10, None]}})
        self.state.refresh_leases()
        self.assertEqual(self.state.upload_start_mark("eddn")[0][0], os.path.basename(self.path))   # 2026-10-09 is past the end: ours
        U.write_lease(self.dir, "other1", {"host": "x", "services": [], "stopped": True,
                                           "marks": {"eddn": ["Journal.261008090000.01.log", 10, None]}})
        self.assertEqual(self.state.upload_start_mark("eddn")[0], ("Journal.261008090000.01.log", 10))   # before the end: theirs

    def test_eddn_waits_dropped_while_another_uploader_has_it(self):
        self.write(header(now_ts(900)), loadgame(now_ts(899)), self.jump(800, "Here"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.uploads_hub.builders = {"eddn": self.state.eddn_build}
        self.state.set_upload("eddn", True)
        self.write({"timestamp": now_ts(700), "event": "FSSSignalDiscovered", "SystemAddress": addr("Here"), "SignalName": "X"})
        self.j.scan_dir(self.dir, upload="live")
        self.assertIn("signals", self.state.uploads_hub.session.pending)
        self.state.edmc = {"running": True, "eddn": True, "edsm": False, "inara": False}
        self.write({"timestamp": now_ts(600), "event": "Music"})
        self.j.scan_dir(self.dir, upload="live")
        self.assertNotIn("signals", self.state.uploads_hub.session.pending)

    def test_another_uploader_keeps_the_mark_moving(self):
        """While EDMC (or another Outrider) has the service, its lines are theirs: the mark moves with them, and a
        restart neither catches them up nor, with the other uploader still there, catches up at all."""
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.state.edmc = {"running": True, "eddn": True, "edsm": False, "inara": False}
        self.write(self.jump(300, "EdmcSent1"), self.jump(200, "EdmcSent2"))
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        self.assertEqual(self.queued(), [])
        mark = self.state.uploads_hub.marks["eddn"]
        self.assertGreater(mark[1], 0)
        self.assertEqual(mark[2], self.jump(200)["timestamp"])       # moved with EDMC's lines
        self.write(self.jump(100, "WhileDown"))                       # Outrider stops; EDMC goes on
        import types
        j2 = ed_outrider.Journals(self.db)
        j2.scan_dir(self.dir, commit_each=True, upload="catchup")
        st2 = ed_outrider.State(self.db, j2, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        st2.game_pc, st2.config_path, st2.upload_cfg = False, self.state.config_path, {"eddn": {"enabled": True}, "edsm": {"enabled": False}}
        st2.uploads_hub.builders = self.state.uploads_hub.builders
        st2.edmc = self.state.edmc                                    # EDMC still sends EDDN
        self.assertEqual(st2.catch_up_uploads(), 0)
        self.assertEqual(st2.uploads_hub.marks["eddn"][0], os.path.basename(self.path))
        self.assertEqual(st2.uploads_hub.marks["eddn"][1], st2.journal_end()[1])   # moved to the end

    def test_switched_back_on_mid_file_knows_where_you_are(self):
        """With every upload off the hub stops following; switched on again mid-file it reads the file from its top,
        so a jump made while off is not forgotten (it built messages with the old system)."""
        self.state.uploads_hub.builders = {"eddn": lambda ev, s: [("where", {"system": s.system})] if ev["event"] == "Scan" else []}
        self.write(header(now_ts(900)), loadgame(now_ts(899)), self.jump(800, "First"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.write({"timestamp": now_ts(700), "event": "Music"})
        self.j.scan_dir(self.dir, upload="live")                      # the hub has primed this file
        self.state.set_upload("eddn", False)
        self.write(self.jump(500, "WhileOff"))
        self.j.scan_dir(self.dir, upload="live")
        self.state.set_upload("eddn", True)
        self.write({"timestamp": now_ts(10), "event": "Scan", "BodyName": "X 1"})
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        self.assertEqual(self.queued(), [{"system": "WhileOff"}])

    def test_lease_marks_only_what_is_uploaded(self):
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.state.uploads_hub.marks["edsm"] = ["Journal.2026-01-01T000000.01.log", 5, None]   # switched off long ago
        self.state.refresh_leases()
        path = U.lease_path(self.dir, self.state.leases.instance)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)["marks"]), {"eddn"})
        self.state.drop_leases()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)["marks"]), {"eddn"})
        self.state.uploads_hub.builders["edsm"] = self.state.uploads_hub.builders["eddn"]
        self.state.set_upload("edsm", True)                              # switched on in the last minute
        self.state.uploads_hub.marks["edsm"] = ["Journal.2026-10-08T100000.01.log", 5, None]
        self.state.drop_leases()                                         # no refresh between: still in the note
        with open(path, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)["marks"]), {"eddn", "edsm"})

    def test_a_crashed_instances_old_lease_is_stale_at_once(self):
        U.write_lease(self.dir, "crashed1", {"host": "old", "services": ["eddn"]})
        path = U.lease_path(self.dir, "crashed1")
        old = time.time() - 2 * U.LEASE_ABANDONED_S
        os.utime(path, (old, old))
        self.assertEqual(U.Leases("me").others([self.dir]), {})
        U.write_lease(self.dir, "fresh1", {"host": "new", "services": ["eddn"]})
        self.assertIn("fresh1", U.Leases("me").others([self.dir]))      # one written just now still counts
        U.write_lease(self.dir, "skewed1", {"host": "behind", "services": ["eddn"]})
        skew = time.time() - 20 * 60                                     # a file server's clock 20 minutes behind
        os.utime(U.lease_path(self.dir, "skewed1"), (skew, skew))
        self.assertIn("skewed1", U.Leases("me").others([self.dir]))     # still counts

    def test_instance_id_belongs_to_this_database(self):
        ed_outrider.meta_set(self.db, "instance_id", "olderdb1")        # a database from before: keeps its id
        self.state.refresh_leases()
        self.assertEqual(self.state.leases.instance, "olderdb1")
        iid = self.state.leases.instance
        ed_outrider.meta_set(self.db, "instance_where", "another-pc:/elsewhere.sqlite")   # as a copied database says
        self.state.leases = None
        self.state.refresh_leases()
        self.assertNotEqual(self.state.leases.instance, iid)
        iid2 = self.state.leases.instance
        self.state.leases = None
        self.state.refresh_leases()
        self.assertEqual(self.state.leases.instance, iid2)               # kept while it is the same file and computer
        # moved on this computer (a restore, a new path): its own old note goes, not read as another Outrider's
        import socket
        U.write_lease(self.dir, iid2, {"host": "me", "services": [], "stopped": True, "marks": {"eddn": ["J.log", 1, None]}})
        ed_outrider.meta_set(self.db, "instance_where", f"{socket.gethostname()}|/old/path.sqlite|1")
        self.state.leases = None
        self.state.refresh_leases()
        self.assertFalse(os.path.exists(U.lease_path(self.dir, iid2)))
        self.assertEqual(U.lease_marks([self.dir], self.state.leases.instance), {})

    def test_watch_prunes_the_outbox(self):
        import asyncio
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        U.enqueue(self.db, "eddn", "x/1", "J:1", now_ts(5), s, {})
        self.db.execute("UPDATE upload_queue SET state='sent', done_at=?", (time.time() - 8 * 86400,))
        self.db.commit()

        async def once():
            with unittest.mock.patch("asyncio.sleep", side_effect=asyncio.CancelledError):
                try:
                    await self.state.watch_leases()
                except asyncio.CancelledError:
                    pass
        asyncio.run(once())
        self.assertEqual(self.db.execute("SELECT count(*) FROM upload_queue").fetchone()[0], 0)

    def test_restored_database_forgets_its_marks(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "restored.sqlite")
        db = ed_outrider.open_db(path)
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        U.enqueue(db, "eddn", "x/1", "J:1", now_ts(5), s, {})
        U.enqueue(db, "eddn", "x/1", "J:2", now_ts(5), s, {})
        db.execute("UPDATE upload_queue SET state='sent' WHERE source='J:2'")
        ed_outrider.meta_set(db, "upload_marks", {"eddn": ["J.log", 1, None]})
        ed_outrider.meta_set(db, "edsm_backfill", {"state": "running", "total": 3})   # S47's, under way in the backup
        db.commit()
        db.close()
        ed_outrider.forget_upload_position(path)
        db = ed_outrider.open_db(path)
        self.addCleanup(db.close)
        self.assertIsNone(ed_outrider.meta_get(db, "upload_marks"))
        bf = ed_outrider.meta_get(db, "edsm_backfill")
        self.assertEqual((bf["state"], bf["total"]), ("stopped", 3))   # its queued rows are gone: it ends, said so
        self.assertEqual([r[0] for r in db.execute("SELECT state FROM upload_queue")], ["sent"])


class LoopFixes(unittest.TestCase):
    """upload_loop after the bug check of 2026-10-09: a retry answer pauses the whole queue; a database error does not
    end the sender."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        for i in range(3):
            U.enqueue(self.db, "eddn", "x/1", f"J.log:{i}", now_ts(5), s, {"i": i})
        self.db.commit()

    def run_loop(self, send, rounds=4):
        import asyncio
        clock, slept = [1000.0], []

        async def sleep(secs):
            slept.append(secs)
            clock[0] += max(secs, 0.5)
            if len(slept) >= rounds:
                raise asyncio.CancelledError

        async def go():
            try:
                await U.upload_loop("eddn", self.db, send, lambda s: True, clock=lambda: clock[0], sleep=sleep, batch=1)
            except asyncio.CancelledError:
                pass
        asyncio.run(go())
        return slept

    def test_a_retry_answer_pauses_the_queue(self):
        calls = []

        async def send(rows):
            calls.append(rows[0]["id"])
            return [(rows[0]["id"], "queued", "503 busy", 60)]
        slept = self.run_loop(send, rounds=1)
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(slept[0], 60)              # the whole queue waits, not the next row half a second later

    def test_a_database_error_does_not_end_the_sender(self):
        import sqlite3
        real = U.due
        boom = [True]

        def flaky(*a, **k):
            if boom.pop() if boom else False:
                raise sqlite3.OperationalError("database is locked")
            return real(*a, **k)
        sent = []

        async def send(rows):
            sent.append(rows[0]["id"])
            return [(rows[0]["id"], "sent", "200 OK", None)]
        with unittest.mock.patch.object(U, "due", flaky), unittest.mock.patch("builtins.print"):
            self.run_loop(send, rounds=3)
        self.assertTrue(sent)                              # went on after the error


class FableUploads(MarksAndCatchUp):
    """The Fable sweep of 2026-10-09: the uploads."""

    def sig(self, ago, name, addr):
        return {"timestamp": now_ts(ago), "event": "FSSSignalDiscovered", "SystemAddress": addr, "SignalName": name}

    def eddn_rows(self):
        return [r["schema"] for r in self.db.execute("SELECT schema FROM upload_queue WHERE service='eddn' ORDER BY id")]

    def test_signals_ending_a_catch_up_are_sent(self):
        """A jump and its signals were the last lines while Outrider was down: the catch-up sends the signals too (they
        waited for a next line that never came inside it)."""
        self.state.uploads_hub.builders = {"eddn": self.state.eddn_build}
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        here = self.jump(300, "Here")
        self.write(here, self.sig(299, "OUT OF THE BLUE G0X-85Z", here["SystemAddress"]))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.catch_up_uploads()
        self.assertIn("fsssignaldiscovered", self.eddn_rows())

    def test_signals_before_their_jump_go_with_the_live_jump(self):
        """Odyssey writes a jump's signals before its FSDJump: left at the end of a catch-up, they go over to the live
        session, and the FSDJump read live sends them."""
        self.state.uploads_hub.builders = {"eddn": self.state.eddn_build}
        self.write(header(now_ts(900)), loadgame(now_ts(899)), self.jump(800, "Before"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        there = self.jump(10, "There")
        self.write(self.sig(11, "A station", there["SystemAddress"]))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.catch_up_uploads()
        self.assertNotIn("fsssignaldiscovered", self.eddn_rows())
        self.write(there)
        self.j.scan_dir(self.dir, upload="live")
        self.assertIn("fsssignaldiscovered", self.eddn_rows())

    def test_a_companion_file_after_a_catch_up_is_sent(self):
        """Codex F2: the catch-up's last line is a NavRoute whose file has not arrived yet (a journal share): the wait
        goes over to the live session, which sends it once the file comes. The catch-up's clock, moved on for the
        signals, gave the wait up before."""
        self.state.uploads_hub.builders = {"eddn": self.state.eddn_build}
        self.write(header(now_ts(900)), loadgame(now_ts(899)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        here = self.jump(30, "Here")
        route = {"timestamp": now_ts(2), "event": "NavRoute"}
        self.write(here, route)
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.catch_up_uploads()
        self.assertNotIn("navroute", self.eddn_rows())
        with open(os.path.join(self.dir, "NavRoute.json"), "w", encoding="utf-8") as f:   # it arrives
            json.dump({"timestamp": route["timestamp"], "event": "NavRoute", "Route": [
                {"StarSystem": "Here", "SystemAddress": here["SystemAddress"], "StarPos": [1, 2, 3], "StarClass": "K"},
                {"StarSystem": "Next", "SystemAddress": 22, "StarPos": [5, 2, 3], "StarClass": "M"}]}, f)
        self.state.uploads_hub.idle()
        self.state.uploads_hub.idle()
        self.assertEqual(self.eddn_rows().count("navroute"), 1)

    def test_edmc_is_looked_for_off_the_event_loop(self):
        import inspect
        src = inspect.getsource(ed_outrider.State.watch_leases)
        self.assertIn("run_in_executor(None, outrider.uploads.edmc_uploads)", src)


class StatusForEddn(unittest.TestCase):
    """The hub keeps the live Status.json's body and, on a body, the position and its time (scanorganic's place)."""

    def test_status(self):
        hub = U.UploadHub(None, {}, enabled=lambda s: False)
        hub.status({"live": True, "body": "X 1", "lat": 1.5, "lon": -2.5, "ts": "2026-10-08T10:00:00Z"})
        self.assertEqual((hub.session.status_body, hub.session.status_pos), ("X 1", (1.5, -2.5, "X 1", "2026-10-08T10:00:00Z")))
        hub.status({"live": True, "body": "X 1", "lat": None, "lon": None, "ts": "2026-10-08T10:01:00Z"})   # in the air
        self.assertIsNone(hub.session.status_pos)
        hub.status({"live": False, "body": "X 1", "lat": 1.5, "lon": -2.5})   # not live: nothing
        self.assertEqual((hub.session.status_body, hub.session.status_pos), (None, None))



def rnd(at, *states, raised=None, error=None, wait=0):
    """An upload_loop report: one row per (state, status text)."""
    return {"at": at, "results": [(i, st, text, None) for i, (st, text) in enumerate(states)], "raised": raised,
            "error": error, "wait": wait}


class RecentRounds(unittest.TestCase):
    """G1 (UP1): uploads.Recent, each service's last rounds in memory, and the outage it tracks (S3, S16)."""

    def test_merges_and_keeps_the_last(self):
        r = U.Recent(keep=3)
        r.add("eddn", rnd(100, ("sent", "200 OK")))
        r.add("eddn", rnd(160, ("sent", "200 OK"), ("dropped", "400 FAIL")))
        [e] = r.recent("eddn")
        self.assertEqual((e["state"], e["sent"], e["dropped"], e["first"], e["at"], e["rounds"], e["note"]),
                         ("ok", 2, 1, 100, 160, 2, "400 FAIL"))           # back to back: one entry, "sent 2 (first-at)"
        r.add("eddn", rnd(160 + U.MERGE_GAP_S + 1, ("sent", "200 OK")))   # a long gap: a new entry
        self.assertEqual(len(r.recent("eddn")), 2)
        boom = ConnectionError("unreachable")
        r.add("eddn", rnd(2000, ("queued", "x"), raised=boom, error="ConnectionError: unreachable", wait=60))
        r.add("eddn", rnd(2060, ("queued", "x"), raised=boom, error="ConnectionError: unreachable", wait=120))
        f = r.recent("eddn")[0]                                         # the same failure again: merged, newest first
        self.assertEqual((f["state"], f["rounds"], f["first"], f["next"], f["kind"]), ("fail", 2, 2000, 2180, "refused"))
        r.add("eddn", rnd(2200, ("held", "203 refused")))
        r.add("eddn", rnd(2300, ("sent", "200 OK")))
        self.assertEqual([e["state"] for e in r.recent("eddn")], ["ok", "held", "fail"])   # only the last 3 kept
        self.assertEqual(r.recent("edsm"), [])

    def test_outage_state_table(self):
        r = U.Recent()
        boom = OSError(101, "Network is unreachable")
        self.assertIsNone(r.add("edsm", rnd(10, ("queued", "x"), raised=boom, error="OSError")))
        o = r.outage("edsm")
        self.assertEqual((o["since"], o["kind"], o["user_fix"]), (10, "offline", True))   # a raised round starts it
        r.add("edsm", rnd(20, ("queued", "503 busy")))                                     # retry only: goes on
        self.assertEqual((r.outage("edsm")["since"], r.outage("edsm")["last"], r.outage("edsm")["kind"]), (10, 20, "http5xx"))
        r.add("edsm", rnd(30, ("held", "203 EDSM refused the commander name or API key")))   # held: neither
        r.add("edsm", rnd(40, ("dropped", "not sent: no EDSM account for CMDR X")))         # settled here: neither
        r.add("edsm", rnd(45, ("dry", "dry run: not sent")))
        self.assertEqual(r.outage("edsm")["since"], 10)
        ended = r.add("edsm", rnd(50, ("sent", "100 OK"), ("queued", "503")))                # answered: ends it
        self.assertEqual((ended["since"], ended["until"]), (10, 50))
        self.assertIsNone(r.outage("edsm"))
        r.add("eddn", rnd(60, ("queued", "503 x"), raised=None, error="503 x"))
        self.assertEqual(r.add("eddn", rnd(70, ("dropped", "400 FAIL")))["until"], 70)        # refused by EDDN itself: answered
        r.add("inara", rnd(80, ("queued", "400 Too much requests, slow down, cowboy."), error="400 Too much requests"))
        self.assertEqual(r.outage("inara")["kind"], "rate")
        r.end("inara")                                                                        # switched off: forgotten
        self.assertIsNone(r.outage("inara"))

    def test_catchup_record(self):
        r = U.Recent()
        r.note_catchup("eddn", 100, "caught_up", count=12, since="2026-10-11T21:14:00Z")
        r.note_catchup("edsm", 100, "other", who="EDMC")
        self.assertEqual(r.catchup["eddn"], {"at": 100, "why": "caught_up", "count": 12, "since": "2026-10-11T21:14:00Z", "who": None})
        self.assertEqual(r.catchup["edsm"]["who"], "EDMC")


class Classify(unittest.TestCase):
    """outrider.health.classify: what kind of failure (the Recent list's words, the outage card's)."""

    def test_kinds(self):
        import asyncio
        import errno
        import socket
        import aiohttp
        from aiohttp.client_reqrep import ConnectionKey
        from outrider.health import HttpError, classify
        key = ConnectionKey("eddn.edcd.io", 4430, True, True, None, None, None)
        cases = [(socket.gaierror(-2, "Name or service not known"), ("dns", True)),
                 (aiohttp.ClientConnectorError(key, OSError(errno.ENETUNREACH, "Network is unreachable")), ("offline", True)),
                 (aiohttp.ClientConnectorError(key, ConnectionRefusedError(errno.ECONNREFUSED, "refused")), ("refused", False)),
                 (asyncio.TimeoutError(), ("timeout", False)),
                 (HttpError(503, "EDSM answered HTTP 503"), ("http5xx", False)),
                 (HttpError(429, "Inara answered HTTP 429"), ("rate", False)),
                 (ValueError("EDSM's answer has no msgnum"), ("bad_answer", False)),
                 (RuntimeError("?"), ("other", False))]
        for exc, want in cases:
            self.assertEqual(classify(exc), want, exc)
        self.assertEqual(classify(text="503 Service Unavailable"), ("http5xx", False))
        self.assertEqual(classify(text="408 timeout"), ("http4xx", False))
        self.assertEqual(classify(text="400 Too much requests, slow down, cowboy."), ("rate", False))
        self.assertEqual(classify(text="503 temporarily unavailable"), ("http5xx", False))   # rate words count on a 4xx only


class SchemaHoldRelease(unittest.TestCase):
    """S16: EDDN's kind on hold, listed with when, and released by Try again with its refusals."""

    def test_release(self):
        import outrider.eddn as E
        h = E.SchemaHold()
        for t in (100, 110, 120):
            h.refused("commodity", t, "400 FAIL: Schema Validation")
        self.assertEqual(h.held_list(), [{"schema": "commodity", "why": "400 FAIL: Schema Validation", "since": 120, "refusals": 3}])
        self.assertTrue(h.release("commodity"))
        self.assertFalse(h.release("commodity"))
        self.assertEqual(h.held_list(), [])
        h.refused("commodity", 130, "400 FAIL")                  # its old refusals went too: one more does not hold it
        self.assertIsNone(h.is_held("commodity"))


class LoopReportsAndWakes(unittest.TestCase):
    """upload_loop's report carries the exception and the wait (Recent), and a wake ends a held key's wait at once."""
    setUp = LoopFixes.setUp

    def test_report_has_the_exception_and_the_wait(self):
        reports = []
        boom = ConnectionError("unreachable")

        async def send(rows):
            raise boom
        import asyncio
        clock = [1000.0]

        async def sleep(secs):
            clock[0] += secs
            raise asyncio.CancelledError

        async def go():
            try:
                await U.upload_loop("eddn", self.db, send, lambda s: True, clock=lambda: clock[0], sleep=sleep,
                                    report=lambda s, o: reports.append(o))
            except asyncio.CancelledError:
                pass
        asyncio.run(go())
        self.assertIs(reports[0]["raised"], boom)
        self.assertEqual(reports[0]["wait"], U.BACKOFF_S[0])

    def test_wake_ends_a_held_wait(self):
        import asyncio
        sent, held = [], [True]

        async def send(rows):
            sent.append(asyncio.get_running_loop().time())
            return [(rows[0]["id"], "held" if held else "sent", "203 refused" if held else "100 OK", None)]

        async def go():
            wake = asyncio.Event()
            on = lambda s: True
            task = asyncio.ensure_future(U.upload_loop("eddn", self.db, send, on, batch=1, wake=wake))   # the rows' service
            while not sent:
                await asyncio.sleep(0.01)
            held.clear()
            wake.set()                                         # Try again: no 30 s wait
            t0 = asyncio.get_running_loop().time()
            while len(sent) < 2:
                await asyncio.sleep(0.01)
                self.assertLess(asyncio.get_running_loop().time() - t0, 3)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        asyncio.run(asyncio.wait_for(go(), 10))
        self.assertEqual(len(sent), 2)

    def test_woken_early_the_pace_still_holds(self):
        import asyncio
        clock, slept, sent = [1000.0], [], []

        async def send(rows):
            sent.append(clock[0])
            return [(rows[0]["id"], "held", "Inara refused: bad key", None)]

        async def sleep(secs):
            slept.append(secs)
            clock[0] += secs
            if len(sent) >= 2:
                raise asyncio.CancelledError

        async def go():
            wake = asyncio.Event()
            wake.set()   # pressed already: the held round's wait ends at once, but 35 s apart all the same
            try:
                await U.upload_loop("eddn", self.db, send, lambda s: True, clock=lambda: clock[0], sleep=sleep, batch=1,
                                    min_gap=35, wake=wake)
            except asyncio.CancelledError:
                pass
        asyncio.run(go())
        self.assertGreaterEqual(sent[1] - sent[0], 35)


class UploadsS16(unittest.TestCase):
    """S16: Settings -> Uploads' Recent list, the start-up catch-up, holds with Try again (one helper for a key hold)."""
    setUp, write, jump = MarksAndCatchUp.setUp, MarksAndCatchUp.write, MarksAndCatchUp.jump

    def test_catch_up_is_recorded(self):
        self.write(header(now_ts(7200)), loadgame(now_ts(7199)))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        self.state.set_upload("eddn", True)
        self.state.uploads_hub.marks.pop("eddn")                   # no mark yet (a first start with it on)
        self.state.catch_up_uploads()
        self.assertEqual(self.state.uploads_summary()["eddn"]["catchup"]["why"], "fresh")
        self.write(self.jump(300, "WhileDown1"), self.jump(200, "WhileDown2"))
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        mark = self.state.uploads_hub.marks["eddn"]
        self.state.catch_up_uploads()
        c = self.state.uploads_summary()["eddn"]["catchup"]
        self.assertEqual((c["why"], c["count"], c["since"]), ("caught_up", 2, mark[2] if len(mark) > 2 else None))
        self.state.catch_up_uploads()
        self.assertEqual(self.state.uploads_summary()["eddn"]["catchup"]["count"], 0)    # "nothing missed"
        self.state.edmc = {"running": True, "eddn": True}
        self.state.catch_up_uploads()
        self.assertEqual(self.state.uploads_summary()["eddn"]["catchup"], dict(self.state.upload_recent.catchup["eddn"],
                                                                              why="other", who="EDMC"))

    def test_summary_lists_recent_rounds_and_holds(self):
        st = self.state
        st.set_upload("eddn", True)
        st.upload_report("eddn", rnd(time.time() - 60, ("queued", "x"), raised=ConnectionError("unreachable"),
                                     error="ConnectionError: unreachable", wait=60))
        st.upload_report("eddn", rnd(time.time(), ("sent", "200 OK")))
        for t in (1, 2, 3):
            st.eddn_hold.refused("commodity", time.time() + t, "400 FAIL")
        u = st.uploads_summary()["eddn"]
        self.assertEqual([e["state"] for e in u["recent"]], ["ok", "fail"])
        self.assertEqual(u["recent"][1]["error"], "ConnectionError: unreachable")   # the raw text kept
        self.assertEqual([h["schema"] for h in u["holds"]], ["commodity"])
        self.assertIsNone(u["key_held"])

    def test_try_again(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        st = self.state
        st.set_upload("edsm", True)
        st.upload_wake["edsm"] = asyncio.Event()
        st.upload_report("edsm", rnd(1, ("held", "203 EDSM refused the commander name or API key")))
        self.assertFalse(st.upload_on("edsm"))
        self.assertEqual(st.uploads_summary()["edsm"]["key_held"], "203 EDSM refused the commander name or API key")
        for t in (1, 2, 3):
            st.eddn_hold.refused("commodity", t, "400 FAIL")

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(st))) as c:
                post = lambda body, **kw: c.post("/api/uploads/retry", json=body, **kw)
                out = [(await post({"service": "edsm"}, headers={"Origin": "http://evil.example"})).status]   # another site's page
                out.append(st.upload_on("edsm"))
                for bad in ({"service": "spansh"}, {"service": "eddn"}, {"service": "edsm", "schema": "x"}, ["edsm"]):
                    out.append((await post(bad)).status)
                r = await post({"service": "edsm"})
                out += [r.status, (await r.json())["edsm"]["key_held"], st.upload_wake["edsm"].is_set()]
                out.append((await post({"service": "edsm"})).status)          # not held now
                out.append((await post({"service": "eddn", "schema": "commodity"})).status)
                out.append((await post({"service": "eddn", "schema": "commodity"})).status)   # released already
                return out
        with unittest.mock.patch("builtins.print"):
            got = asyncio.run(go())
        self.assertEqual(got, [403, False, 400, 400, 400, 400, 200, None, True, 409, 200, 404])
        self.assertTrue(st.upload_on("edsm"))                     # sending again
        self.assertIsNone(st.eddn_hold.is_held("commodity"))
        st.eddn_hold.refused("commodity", 10, "400 FAIL")         # its refusals were cleared: one more holds nothing
        self.assertIsNone(st.eddn_hold.is_held("commodity"))

    def test_a_new_key_clears_the_hold_through_the_same_helper(self):
        st = self.state
        st.set_upload("inara", True)
        with unittest.mock.patch.object(st, "clear_key_hold", wraps=st.clear_key_hold) as helper:
            st.set_inara_account("Briadin", "abcdefghijklmnop1234")
            st.set_edsm_account("Briadin", "Briadin", "0123456789abcdef0123456789abcdef01234567")
        self.assertEqual([c.args[0] for c in helper.call_args_list], ["inara", "edsm"])


class UploadOutageAlert(unittest.TestCase):
    """S3: an upload failing for 15 minutes with messages waiting: a card on the banner and a moment (a notification,
    never spoken), once per outage; the first answered round after it says it is sending again."""

    def setUp(self):
        MarksAndCatchUp.setUp(self)
        self.state.set_upload("eddn", True)
        self.state.set_upload("edsm", True)
        self.t0 = time.time()
        s = U.Session()
        s.feed(header(now_ts(9)), "J.log")
        s.feed(loadgame(now_ts(8)))
        self.session = s

    def queue(self, service, n, ago=60):
        for i in range(n):
            U.enqueue(self.db, service, "journal", f"J{service}{ago}:{i}", now_ts(ago), self.session, {"i": i})
        self.db.commit()

    def down(self, service, at):
        self.state.upload_report(service, rnd(at, ("queued", "x"), raised=OSError(101, "Network is unreachable"),
                                              error="ClientConnectorError: Cannot connect to host", wait=60))

    def moments(self, kind):
        return [m for m in self.j.moments if m["kind"] == kind]

    def test_once_per_outage_and_back(self):
        st = self.state
        self.queue("eddn", 42, ago=22 * 60 - 30)                               # the oldest 37.5 min from its hour
        self.down("eddn", self.t0)
        st.check_upload_outages(self.t0 + 14 * 60)
        self.assertEqual(self.moments("upload_down"), [])                       # not 15 minutes yet
        with unittest.mock.patch("sys.stderr"):
            st.check_upload_outages(self.t0 + 15 * 60)
            st.check_upload_outages(self.t0 + 16 * 60)
        [m] = self.moments("upload_down")                                       # once
        self.assertEqual(m["text"], "EDDN unreachable (no network) for 15 min: 42 messages waiting, they drop after an "
                                    "hour (the oldest in 23 min)")
        self.assertEqual((m["service"], m["failure"], m["waiting"], m["stake"]), ("eddn", "offline", 42, 23))
        [n] = [n for n in st.notices.active() if n["key"] == "upload_down:eddn"]
        self.assertEqual((n["text"], n["action"]), (m["text"], "open:uploads"))
        # two were dropped as over an hour old meanwhile, then EDDN answers
        self.db.execute("UPDATE upload_queue SET state='dropped', last_status='not sent: over an hour old', done_at=? "
                        "WHERE id IN (SELECT id FROM upload_queue WHERE service='eddn' LIMIT 2)", (self.t0 + 30 * 60,))
        self.db.commit()
        with unittest.mock.patch("builtins.print"):
            st.upload_report("eddn", rnd(self.t0 + 37 * 60, ("dropped", "not sent: over an hour old")))   # settled here: not back
            self.assertEqual(self.moments("upload_back"), [])
            st.upload_report("eddn", rnd(self.t0 + 37 * 60, ("sent", "200 OK")))
        [b] = self.moments("upload_back")
        self.assertEqual(b["text"], "EDDN sending again after 37 min: sending the 40 waiting (2 were over an hour old and dropped)")
        self.assertEqual([n for n in st.notices.active() if n["key"] == "upload_down:eddn"], [])   # the card goes
        self.down("eddn", self.t0 + 40 * 60)                                     # a new outage: said again later
        with unittest.mock.patch("sys.stderr"):
            st.check_upload_outages(self.t0 + 56 * 60)
        self.assertEqual(len(self.moments("upload_down")), 2)

    def test_only_with_messages_waiting_and_while_on(self):
        st = self.state
        self.down("edsm", self.t0)
        st.check_upload_outages(self.t0 + 20 * 60)
        self.assertEqual(self.moments("upload_down"), [])                       # nothing waiting: nothing at stake
        self.queue("edsm", 3)
        with unittest.mock.patch("sys.stderr"):
            st.check_upload_outages(self.t0 + 20 * 60)
        [m] = self.moments("upload_down")
        self.assertEqual(m["text"], "EDSM unreachable (no network) for 20 min: 3 messages waiting, kept until it answers")
        st.set_upload("edsm", False)                                             # switched off: the card goes
        self.assertEqual([n for n in st.notices.active() if n["key"].startswith("upload_down")], [])
        st.set_upload("edsm", True)
        self.down("edsm", self.t0 + 21 * 60)
        st.check_upload_outages(self.t0 + 30 * 60)                               # a new outage, 9 minutes old
        self.assertEqual(len(self.moments("upload_down")), 1)

    def test_inara_asked_to_slow_down(self):
        st = self.state
        st.set_upload("inara", True)
        self.queue("inara", 5)
        st.upload_report("inara", rnd(self.t0, ("queued", "400 Too much requests, slow down, cowboy."),
                                      error="400 Too much requests, slow down, cowboy.", wait=3600))
        with unittest.mock.patch("sys.stderr"):
            st.check_upload_outages(self.t0 + 15 * 60)
        [m] = self.moments("upload_down")
        self.assertEqual(m["text"], "Inara asked Outrider to slow down 15 min ago: 5 messages waiting, kept until it answers")


class LogMarks(unittest.TestCase):
    """S68: the Log's upload marks (✓ EDDN · ✓ EDSM, ⏳, ⏸, ✗ with the reason) and its "not sent" filter."""

    def setUp(self):
        import types
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        p = unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir])
        p.start()
        self.addCleanup(p.stop)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.name = "Journal.2026-10-08T100000.01.log"
        self.who = types.SimpleNamespace(cmdr="Sample Pilot", gameversion="4.2", gamebuild="r1")

    def queue(self, service, source, state="queued", status=None, attempts=0, next_try=0, created=None, schema="s"):
        U.enqueue(self.db, service, schema, source, created or now_ts(60), self.who, {"x": 1}, next_try)
        self.db.execute("UPDATE upload_queue SET state=?, last_status=?, attempts=? WHERE service=? AND source=?",
                        (state, status, attempts, service, source))

    def test_offsets_are_the_readers_byte_offsets(self):
        import outrider.log
        lines = [json.dumps({"timestamp": now_ts(30), "event": "FSDJump", "StarSystem": "A", "SystemAddress": 1}),
                 # a bare carriage return between two keys: JSON whitespace, one line for the journal reader
                 '{"timestamp":"%s", "event":"Location",\r "StarSystem":"B", "SystemAddress":2}' % now_ts(20),
                 json.dumps({"timestamp": now_ts(10), "event": "Docked", "StationName": "C"})]
        data = "\r\n".join(lines).encode() + b"\r\n"
        with open(os.path.join(self.dir, self.name), "wb") as f:
            f.write(data)
        rows = outrider.log.read_log([self.dir], days=1)["rows"]
        self.assertEqual([r["event"] for r in rows], ["Docked", "Location", "FSDJump"])
        starts = [0]
        for line in data.split(b"\n")[:-2]:
            starts.append(starts[-1] + len(line) + 1)
        self.assertEqual([r["at"] for r in rows], starts[::-1])   # what Journals.read_file hands the uploader
        only = outrider.log.read_log([self.dir], days=1, cats=set(), only={self.name: {starts[1]}})["rows"]
        self.assertEqual([r["event"] for r in only], ["Location"])   # "not sent" overrides the category boxes

    def test_worst_state_wins_per_service_and_the_backfill_is_edsm(self):
        n = self.name
        self.queue("eddn", f"{n}:100", "sent", "200 OK")
        self.queue("eddn", f"{n}:100#1", "dropped", "400 schema refused")      # the same line's second message
        self.queue("edsm", f"{n}:100", next_try=time.time() + 300)              # waits for the next jump
        self.queue("inara", f"{n}:100", "sent", "200")
        self.queue("edsm_bf", f"{n}:200", "dropped", "102 Message older than the stored one")
        self.queue("eddn", f"{n}:2000", "queued", "HTTP 503", attempts=2)
        self.queue("eddn", "other.log:100", "dropped", "x")                    # another file's line at the same offset
        m = U.line_marks(self.db, {(n, 100), (n, 200), (n, 300), (n, 2000)})
        self.assertEqual(m[(n, 100)], {"eddn": {"state": "dropped", "why": "400 schema refused"},
                                       "edsm": {"state": "queued", "why": "waiting for the next jump or docking"},
                                       "inara": {"state": "sent", "why": "200"}})
        self.assertEqual(m[(n, 200)], {"edsm": {"state": "dropped", "why": "flight log backfill: 102 Message older than the stored one"}})
        self.assertNotIn((n, 300), m)                                           # nothing to send: no mark at all
        self.assertEqual(m[(n, 2000)]["eddn"], {"state": "queued", "why": "trying again: HTTP 503"})
        held = U.line_marks(self.db, {(n, 100)}, held=lambda s, schema: "203 EDSM refused the key" if s == "edsm" else None)
        self.assertEqual(held[(n, 100)]["edsm"], {"state": "held", "why": "203 EDSM refused the key"})

    def test_state_marks_the_last_week_only_and_holds(self):
        st, n = self.state, self.name
        st.upload_cfg["edsm"]["enabled"] = True
        self.queue("edsm", f"{n}:10")
        self.queue("eddn", f"{n}:20", "sent", "200 OK")
        rows = [{"id": f"{n}|0", "at": 10, "ts": now_ts(60)}, {"id": f"{n}|1", "at": 20, "ts": now_ts(8 * 86400)},
                {"id": f"{n}|2", "at": 30, "ts": now_ts(30)}]
        st.log_marks(rows)
        self.assertEqual(rows[0]["up"], [{"service": "edsm", "state": "queued", "why": "waiting to be sent"}])
        self.assertNotIn("up", rows[1])                     # over a week old: the outbox has forgotten, no mark
        self.assertEqual(rows[2]["up"], [])                 # nothing of that line was for an upload
        st.upload_report("edsm", {"error": None, "at": 1.0, "raised": None, "wait": 30,
                                  "results": [(1, "held", "203 EDSM refused the commander name or API key", None)]})
        rows = [{"id": f"{n}|0", "at": 10, "ts": now_ts(60)}]
        st.log_marks(rows)
        self.assertEqual(rows[0]["up"][0]["state"], "held")
        st.upload_cfg["edsm"]["enabled"] = False
        st.upload_status.pop("edsm")
        st.log_marks(rows)
        self.assertEqual(rows[0]["up"][0]["why"], "EDSM is switched off")

    def test_the_route_marks_rows_and_filters_not_sent(self):
        from aiohttp.test_utils import TestClient, TestServer
        lines = [{"timestamp": now_ts(300), "event": "Music", "MusicTrack": "Exploration"},          # noise, waiting for EDDN
                 {"timestamp": now_ts(200), "event": "FSDJump", "StarSystem": "A", "SystemAddress": 1},  # sent
                 {"timestamp": now_ts(100), "event": "Docked", "StationName": "C"}]                      # nothing to send
        data, offs = b"", []
        for e in lines:
            offs.append(len(data))
            data += (json.dumps(e) + "\n").encode()
        with open(os.path.join(self.dir, self.name), "wb") as f:
            f.write(data)
        self.queue("eddn", f"{self.name}:{offs[0]}", created=lines[0]["timestamp"])
        self.queue("eddn", f"{self.name}:{offs[1]}", "sent", "200 OK", created=lines[1]["timestamp"])
        self.state.upload_cfg["eddn"]["enabled"] = True

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                a = await (await c.get("/api/log?days=7&cat=travel,other")).json()
                b = await (await c.get("/api/log?days=7&cat=travel&unsent=1")).json()
                return a, b
        a, b = asyncio_run(go())
        self.assertEqual(a["marks_days"], 7)
        self.assertEqual([(r["event"], [m["state"] for m in r["up"]]) for r in a["rows"]], [("Docked", []), ("FSDJump", ["sent"])])
        self.assertEqual([r["event"] for r in b["rows"]], ["Music"])           # noise too: "not sent" overrides the boxes
        self.assertEqual(b["rows"][0]["up"], [{"service": "eddn", "state": "queued", "why": "waiting to be sent"}])


class RetriedRowsKeepTheirPlace(unittest.TestCase):
    """Review 2026-10-20 M0: a wake during a backoff (a Save or Check of the key, Try again) sent rows queued since ahead
    of the batch waiting to be retried (EDSM's events out of order), and Inara's slow-down hour was cut short."""

    def setUp(self):
        LoopFixes.setUp(self)

    def test_newer_rows_wait_behind_a_retry(self):
        first = U.due(self.db, "eddn", 1000.0)[0]["id"]
        U.settle(self.db, first, "queued", "503 busy", 1000.0, retry_in=60)
        self.assertEqual(U.due(self.db, "eddn", 1010.0), [])            # woken early: nothing overtakes the retry
        self.assertEqual([r["id"] for r in U.due(self.db, "eddn", 1061.0)][0], first)   # then the oldest goes first

    def test_a_save_or_check_without_a_hold_keeps_the_wait(self):
        import asyncio
        st = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        st.upload_wake["inara"] = asyncio.Event()
        st.upload_status["inara"] = {"error": "Inara: too many requests, slow down"}
        self.assertFalse(st.clear_key_hold("inara"))
        self.assertFalse(st.upload_wake["inara"].is_set())
        self.assertEqual(st.upload_status["inara"]["error"], "Inara: too many requests, slow down")
        st.upload_status["inara"] = {"held": "203 refused"}
        self.assertTrue(st.clear_key_hold("inara"))
        self.assertTrue(st.upload_wake["inara"].is_set())
        self.assertNotIn("inara", st.upload_status)


class EdmcOnWindows(unittest.TestCase):
    """Review 2026-10-20 H1: tasklist writes the OEM code page; read as text, a German "keine Aufgaben ... ausgeführt"
    (ü = 0x81, no cp1252 byte) raised UnicodeDecodeError out of edmc_running, crashing Outrider's start-up on a game PC
    with EDMC installed and not running."""

    def run_with(self, stdout):
        import subprocess
        done = subprocess.CompletedProcess(["tasklist"], 0, stdout=stdout, stderr=b"")
        with unittest.mock.patch("subprocess.run", return_value=done) as run:
            got = U.edmc_running("win32")
        self.assertNotIn("text", run.call_args.kwargs)   # bytes, never decoded
        return got

    def test_localized_no_tasks_message(self):
        self.assertFalse(self.run_with(b"INFORMATION: Es werden keine Aufgaben mit den angegebenen Kriterien ausgef\x81hrt.\r\n"))

    def test_running(self):
        self.assertTrue(self.run_with(b"EDMarketConnector.exe        4242 Console    1    81.200 K\r\n"))


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
