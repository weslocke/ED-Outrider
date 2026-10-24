"""EDSM's journal upload (outrider/edsm.py, the server's edsm_send; PLAN-edmc-functionality part H).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import json
import os
import shutil
import tempfile
import time
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.edsm as S  # noqa: E402
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts  # noqa: E402

KEY = "0123456789abcdef0123456789abcdef01234567"


def session(d=None):
    s = U.Session()
    s.dir = d
    s.feed({"event": "Fileheader", "timestamp": "2026-10-08T10:00:00Z", "gameversion": "4.4.1.1", "build": "r332841/r0 "},
           "Journal.2026-10-08T100000.01.log")
    s.feed({"event": "LoadGame", "timestamp": "2026-10-08T10:00:01Z", "Commander": "Briadin", "FID": "F1", "ShipID": 39,
            "Horizons": True, "Odyssey": True})
    return s


JUMP = {"timestamp": "2026-10-08T10:05:00Z", "event": "FSDJump", "StarSystem": "Smojooe AR-E b25-8",
        "SystemAddress": 18207037532889, "StarPos": [-4177.09, -1.0, 3324.53], "JumpDist": 43.1}


class Build(unittest.TestCase):

    def test_where_you_were(self):
        """Each event carries EDSM's transient fields from the session, which has seen the line already."""
        s = session()
        s.feed(JUMP)
        [(name, m)] = S.build(JUMP, s)
        self.assertEqual(name, "FSDJump")
        self.assertEqual((m["_systemAddress"], m["_systemName"], m["_systemCoordinates"], m["_shipId"]),
                         (18207037532889, "Smojooe AR-E b25-8", [-4177.09, -1.0, 3324.53], 39))
        self.assertNotIn("_marketId", m)
        docked = {"timestamp": "2026-10-08T10:09:00Z", "event": "Docked", "StationName": "G0X-85Z", "MarketID": 3700251648,
                  "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": 18207037532889}
        s.feed(docked)
        [(_, m)] = S.build(docked, s)
        self.assertEqual((m["_marketId"], m["_stationName"]), (3700251648, "G0X-85Z"))
        undocked = {"timestamp": "2026-10-08T10:12:00Z", "event": "Undocked", "StationName": "G0X-85Z", "MarketID": 3700251648}
        s.feed(undocked)
        [(_, m)] = S.build(undocked, s)
        self.assertNotIn("_marketId", m)
        self.assertEqual(m["MarketID"], 3700251648)                  # the event itself is sent as the game wrote it

    def test_discarded(self):
        s = session()
        self.assertEqual(S.build({"timestamp": "t", "event": "Music", "MusicTrack": "NoTrack"}, s), [])
        self.assertEqual(S.build({"timestamp": "t", "event": "FSSBodySignals"}, s), [])
        self.assertEqual(len(S.build({"timestamp": "t", "event": "Docked"}, s, frozenset({"Docked"}))), 1)   # always kept
        self.assertEqual(len(S.build({"timestamp": "t", "event": "Music"}, s, frozenset())), 1)   # EDSM's live list rules
        self.assertEqual(S.build({"timestamp": "t"}, s), [])

    def test_discard_list(self):
        self.assertEqual(S.discard_list(["Music", "Fileheader"]), frozenset({"Music", "Fileheader"}))
        for bad in (None, [], {"Music": 1}, ["Music", 3], "Music"):
            self.assertIsNone(S.discard_list(bad))
        self.assertIn("Fileheader", S.DISCARD)
        self.assertNotIn("FSDJump", S.DISCARD)

    def test_contents_from_the_file(self):
        """Cargo, ShipLocker and Backpack written without their contents get them from the file the game wrote with
        them (same timestamp); an older file leaves the event as it is."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        s = session(d)
        ev = {"timestamp": "2026-10-08T10:20:00Z", "event": "Cargo", "Vessel": "Ship", "Count": 4}
        with open(os.path.join(d, "Cargo.json"), "w", encoding="utf-8") as f:
            json.dump(dict(ev, Inventory=[{"Name": "gold", "Count": 4, "Stolen": 0}]), f)
        [(_, m)] = S.build(ev, s)
        self.assertEqual(m["Inventory"], [{"Name": "gold", "Count": 4, "Stolen": 0}])
        [(_, m)] = S.build(dict(ev, timestamp="2026-10-08T10:21:00Z"), s)   # the file is an earlier one
        self.assertNotIn("Inventory", m)
        [(_, m)] = S.build(dict(ev, Vessel="SRV"), s)                     # the SRV's hold, not the ship's
        self.assertNotIn("Inventory", m)
        locker = {"timestamp": "2026-10-08T10:22:00Z", "event": "ShipLocker"}
        with open(os.path.join(d, "ShipLocker.json"), "w", encoding="utf-8") as f:
            json.dump(dict(locker, Items=[{"Name": "x", "Count": 1}], Components=[], Consumables=[], Data=[]), f)
        [(_, m)] = S.build(locker, s)
        self.assertEqual((m["Items"], m["Data"]), ([{"Name": "x", "Count": 1}], []))
        full = dict(ev, Inventory=[{"Name": "silver", "Count": 1}])
        [(_, m)] = S.build(full, s)                                        # written with its contents: as it is
        self.assertEqual(m["Inventory"], [{"Name": "silver", "Count": 1}])


class Batches(unittest.TestCase):

    def test_waits_for_a_jump(self):
        """Events wait (at most HOLD_S) until a jump, a docking or a Location, which sends what waits with it."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        clock = [time.time()]
        hub = U.UploadHub(db, {"edsm": lambda ev, s: S.build(ev, s)}, enabled=lambda s: True,
                          clock=lambda: clock[0], holds={"edsm": S.hold})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "Journal.2026-10-08T100000.01.log")
        lines = [{"timestamp": iso_ts(clock[0] - 60), "event": "Fileheader", "gameversion": "4.4.1.1", "build": "r1 "},
                 {"timestamp": iso_ts(clock[0] - 59), "event": "LoadGame", "Commander": "Briadin"},
                 {"timestamp": iso_ts(clock[0] - 30), "event": "Scan", "BodyName": "A 1"},
                 {"timestamp": iso_ts(clock[0] - 20), "event": "Scan", "BodyName": "A 2"}]
        off = 0
        for e in lines:
            raw = json.dumps(e).encode()
            hub.line(path, off, raw, "live")
            off += len(raw) + 1
        self.assertEqual(U.due(db, "edsm", clock[0]), [])                  # waiting
        self.assertEqual(len(U.due(db, "edsm", clock[0] + S.HOLD_S)), 3)   # ...at most HOLD_S (LoadGame and the scans)
        hub.line(path, off, json.dumps(dict(JUMP, timestamp=iso_ts(clock[0]))).encode(), "live")
        self.assertEqual([json.loads(r["message"])["event"] for r in U.due(db, "edsm", clock[0])],
                         ["LoadGame", "Scan", "Scan", "FSDJump"])            # all now, in order

    def test_a_long_stay_sends_one_batch(self):
        """Events join the waiting batch's deadline (the first one's HOLD_S): a long stay in one system sends them
        together, not each HOLD_S after itself (the author's dry run, 2026-10-08: nine scans went one by one)."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        clock = [time.time()]
        hub = U.UploadHub(db, {"edsm": lambda ev, s: S.build(ev, s)}, enabled=lambda s: True,
                          clock=lambda: clock[0], holds={"edsm": S.hold})
        path = os.path.join(tempfile.mkdtemp(), "Journal.2026-10-08T100000.01.log")
        self.addCleanup(shutil.rmtree, os.path.dirname(path))
        off, start = 0, clock[0]
        for i, e in enumerate([{"event": "Fileheader", "gameversion": "4.4.1.1", "build": "r1 "},
                               {"event": "LoadGame", "Commander": "Briadin"}, JUMP] + [{"event": "Scan", "BodyName": f"A {n}"} for n in range(4)]):
            if e["event"] == "Scan":
                clock[0] += 120                                    # a scan every two minutes
            raw = json.dumps(dict(e, timestamp=iso_ts(clock[0]))).encode()
            hub.line(path, off, raw, "live")
            off += len(raw) + 1
        db.execute("UPDATE upload_queue SET state='sent' WHERE schema IN ('LoadGame', 'FSDJump')")   # went with the jump
        self.assertEqual(U.due(db, "edsm", start + 120 + S.HOLD_S - 1), [])
        self.assertEqual(len(U.due(db, "edsm", start + 120 + S.HOLD_S)), 4)   # all four at the first one's deadline

    def test_one_commander_and_version_per_request(self):
        rows = [{"id": i, "cmdr": c, "gameversion": v, "gamebuild": "b", "message": "{}"}
                for i, (c, v) in enumerate([("A", "4.4"), ("A", "4.4"), ("B", "4.4"), ("A", "4.4")])]
        self.assertEqual([r["id"] for r in S.same_batch(rows)], [0, 1])
        self.assertEqual([r["id"] for r in S.same_batch(rows[2:])], [2])
        rows[1]["gameversion"] = "4.5"
        self.assertEqual([r["id"] for r in S.same_batch(rows)], [0])
        self.assertEqual(len(S.same_batch(rows[:1] * 300)), S.BATCH)

    def test_request(self):
        rows = [{"id": 1, "cmdr": "Briadin", "gameversion": "4.4.1.1", "gamebuild": "r332841/r0 ", "message": json.dumps(JUMP)}]
        body = S.request(rows, {"name": "Briadin EDSM", "key": KEY}, "2026.10.18")
        self.assertEqual({k: v for k, v in body.items() if k != "message"},
                         {"commanderName": "Briadin EDSM", "apiKey": KEY, "fromSoftware": "ED Outrider",
                          "fromSoftwareVersion": "2026.10.18", "fromGameVersion": "4.4.1.1", "fromGameBuild": "r332841/r0 "})
        self.assertEqual(body["message"], [JUMP])


class Answers(unittest.TestCase):
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_per_event(self):
        got = S.answer(self.rows, {"msgnum": 100, "msg": "OK", "events": [
            {"msgnum": 100, "msg": "OK", "systemId": 5}, {"msgnum": 304, "msg": "Discarded event"}, {"msgnum": 501, "msg": "x"}]})
        self.assertEqual([(i, st) for i, st, _, _ in got], [(1, "sent"), (2, "dropped"), (3, "sent")])
        self.assertEqual(got[1][2], "304 Discarded event")
        self.assertEqual([st for _, st, _, _ in S.answer(self.rows, {"msgnum": 100, "events": []})], ["sent"] * 3)

    def test_whole_request(self):
        held = S.answer(self.rows, {"msgnum": 203, "msg": "Commander name/API Key not found"})
        self.assertEqual({(st, text) for _, st, text, _ in held}, {("held", "203 EDSM refused the commander name or API key")})
        self.assertEqual({st for _, st, _, _ in S.answer(self.rows, {"msgnum": 208, "msg": "too old"})}, {"dropped"})
        self.assertEqual({st for _, st, _, _ in S.answer(self.rows, {"msgnum": 206, "msg": "bad"})}, {"dropped"})
        self.assertEqual({(st, r) for _, st, _, r in S.answer(self.rows, {"msgnum": 999})}, {("queued", 60)})
        for bad in ([], {"msg": "no number"}):
            with self.assertRaises(ValueError):   # the loop backs off
                S.answer(self.rows, bad)


class _Resp:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self, content_type=None):
        return self.body


class _Http:
    def __init__(self, answers):
        self.answers, self.posts, self.gets = list(answers), [], []

    def post(self, url, json=None):
        self.posts.append((url, json))
        return _Resp(*self.answers.pop(0))

    def get(self, url):
        self.gets.append(url)
        return _Resp(*self.answers.pop(0))


class Sender(unittest.TestCase):

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.state.config_path = os.path.join(self.dir, "ed_outrider.toml")
        s = session()
        for i, e in enumerate((JUMP, {"timestamp": "2026-10-08T10:06:00Z", "event": "Scan", "BodyName": "A 1"})):
            U.enqueue(self.db, "edsm", e["event"], f"J:{i}", e["timestamp"], s, dict(e, _systemName="X"))
        self.db.commit()

    def rows(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM upload_queue ORDER BY id")]

    def test_sent_with_the_commanders_account(self):
        self.state.set_edsm_account("Briadin", "Briadin EDSM", KEY)
        self.state.upload_session = _Http([(200, {"msgnum": 100, "msg": "OK", "events": [{"msgnum": 100}, {"msgnum": 101}]})])
        with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: ""}):
            out = asyncio.run(self.state.edsm_send(self.rows()))
        self.assertEqual([st for _, st, _, _ in out], ["sent", "sent"])
        [(url, body)] = self.state.upload_session.posts
        self.assertEqual((url, body["commanderName"], body["apiKey"], [e["event"] for e in body["message"]]),
                         (S.UPLOAD_URL, "Briadin EDSM", KEY, ["FSDJump", "Scan"]))

    def test_no_account(self):
        self.state.upload_session = _Http([])
        out = asyncio.run(self.state.edsm_send(self.rows()))
        self.assertEqual({(st, text) for _, st, text, _ in out},
                         {("dropped", "not sent: no EDSM account for CMDR Briadin (Settings -> Uploads)")})
        self.state.upload_report("edsm", {"error": None, "at": 1, "results": out})
        self.assertEqual(self.state.uploads_summary()["edsm"]["error"], out[0][2])   # the page says why

    def test_no_account_for_the_playing_commander_holds(self):
        # S3-S1: EDSM switched on before the key is added: the session waits in the outbox instead of being dropped
        self.state.upload_cfg["edsm"]["enabled"] = True
        self.j.commander = {"name": "Briadin"}
        self.state.upload_session = _Http([])
        out = asyncio.run(self.state.edsm_send(self.rows()))
        self.assertEqual({st for _, st, _, _ in out}, {"held"})
        self.assertIn("no EDSM account for CMDR Briadin", out[0][2])
        self.state.upload_report("edsm", {"error": None, "at": 1, "results": out})
        self.assertFalse(self.state.upload_on("edsm"))
        self.state.set_edsm_account("Briadin", "Briadin", KEY)   # saving the key releases them
        self.assertTrue(self.state.upload_on("edsm"))

    def test_a_no_key_hold_ends_when_another_commander_plays(self):
        self.state.upload_cfg["edsm"]["enabled"] = True
        self.j.commander = {"name": "Briadin"}
        self.state.upload_session = _Http([])
        out = asyncio.run(self.state.edsm_send(self.rows()))
        self.state.upload_report("edsm", {"error": None, "at": 1, "results": out})
        self.assertFalse(self.state.upload_on("edsm"))
        self.j.commander = {"name": "Alt"}
        self.assertTrue(self.state.upload_on("edsm"))   # the queue goes on: Briadin's rows are dropped as before
        out = asyncio.run(self.state.edsm_send(self.rows()))
        self.assertEqual({st for _, st, _, _ in out}, {"dropped"})

    def test_refused_key_holds(self):
        self.state.set_edsm_account("Briadin", "Briadin", KEY)
        self.state.upload_cfg["edsm"]["enabled"] = True
        self.state.upload_session = _Http([(200, {"msgnum": 203, "msg": "Commander name/API Key not found"})])
        with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: ""}), unittest.mock.patch("sys.stderr"):
            out = asyncio.run(self.state.edsm_send(self.rows()))
        self.state.upload_report("edsm", {"error": None, "at": 1, "results": out})
        self.assertFalse(self.state.upload_on("edsm"))                  # until the key changes
        self.state.set_edsm_account("Briadin", "Briadin", KEY)
        self.assertTrue(self.state.upload_on("edsm"))

    def test_a_hold_gets_a_card_and_a_moment_once(self):
        """S9-S20: a refused key stops EDSM until the player acts: a card on the banner and an upload_held moment, once
        per hold (the next held round says nothing more); the card goes with the hold."""
        self.state.set_edsm_account("Briadin", "Briadin", KEY)
        self.state.upload_cfg["edsm"]["enabled"] = True
        for _ in range(2):
            self.state.upload_session = _Http([(200, {"msgnum": 203, "msg": "Commander name/API Key not found"})])
            with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: ""}), unittest.mock.patch("sys.stderr"):
                out = asyncio.run(self.state.edsm_send(self.rows()))
                self.state.upload_report("edsm", {"error": None, "at": 1, "results": out})
        cards = [n for n in self.state.notices.active() if n["key"] == "upload_held:edsm"]
        self.assertEqual(len(cards), 1)
        self.assertIn("EDSM uploads on hold", cards[0]["text"])
        held = [m for m in self.j.moments if m["kind"] == "upload_held"]
        self.assertEqual([(m["service"], m["name"]) for m in held], [("edsm", "EDSM")])
        self.state.retry_upload("edsm")                                 # Try again: the card goes
        self.assertFalse([n for n in self.state.notices.active() if n["key"] == "upload_held:edsm"])

    def test_http_failure_backs_off(self):
        self.state.set_edsm_account("Briadin", "Briadin", KEY)
        self.state.upload_session = _Http([(503, None)])
        with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: ""}), self.assertRaises(ConnectionError):
            asyncio.run(self.state.edsm_send(self.rows()))

    def test_dry_run(self):
        """OUTRIDER_EDSM_DRYRUN: the request is built and logged without its key, nothing is sent, the rows are 'dry'."""
        self.state.set_edsm_account("Briadin", "Briadin", KEY)
        self.state.edsm_dry_path = os.path.join(self.dir, "edsm-dryrun.jsonl")
        self.state.upload_session = _Http([])
        with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: "1"}), unittest.mock.patch("builtins.print") as p:
            out = asyncio.run(self.state.edsm_send(self.rows()))
        self.assertEqual({st for _, st, _, _ in out}, {"dry"})
        self.assertEqual(self.state.upload_session.posts, [])
        self.assertIn("EDSM dry run: 2 events for Briadin (FSDJump, Scan), not sent", p.call_args[0][0])
        with open(self.state.edsm_dry_path, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn(KEY, text)
        logged = json.loads(text)
        self.assertEqual((logged["apiKey"], len(logged["message"])), ("(not logged)", 2))
        for row_id, st, status, retry in out:
            U.settle(self.db, row_id, st, status, time.time(), retry)
        self.assertEqual(U.counts(self.db, "edsm")["dry_24h"], 2)
        with unittest.mock.patch.dict(os.environ, {S.DRY_ENV: "1"}):
            self.assertTrue(self.state.uploads_summary()["edsm"]["dry_run"])
            self.assertIn("EDSM off (DRY RUN: built and logged, nothing sent, OUTRIDER_EDSM_DRYRUN is set)",
                          self.state.uploads_line())

    def test_discard_list_fetched(self):
        self.state.upload_cfg["edsm"]["enabled"] = True
        self.state.upload_session = _Http([(200, ["Music", "Scan"])])

        async def once():
            task = asyncio.create_task(self.state.watch_edsm_discard())
            await asyncio.sleep(0.01)
            task.cancel()
        asyncio.run(once())
        self.assertEqual((self.state.upload_session.gets, self.state.edsm_discard), ([S.DISCARD_URL], frozenset({"Music", "Scan"})))
        self.assertEqual(self.state.edsm_build({"timestamp": "t", "event": "Scan"}, session()), [])

    def test_discard_list_not_fetched_while_off(self):
        self.state.upload_session = _Http([])

        async def once():
            task = asyncio.create_task(self.state.watch_edsm_discard())
            await asyncio.sleep(0.01)
            task.cancel()
        asyncio.run(once())
        self.assertEqual(self.state.upload_session.gets, [])
        self.assertIs(self.state.edsm_discard, S.DISCARD)


class NoNewToEdsm(unittest.TestCase):

    def test_old_table_dropped(self):
        """The removed "New to EDSM" badge's table goes from a database that had it (the author's, 2026-10-09)."""
        import sqlite3
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "old.sqlite")
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE edsm_new_systems (system INTEGER PRIMARY KEY, name TEXT, ts TEXT)")
        con.commit()
        con.close()
        db = ed_outrider.open_db(path)
        self.addCleanup(db.close)
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='edsm_new_systems'").fetchone())
        self.assertNotIn("new_24h", ed_outrider.State(db, ed_outrider.Journals(db),
                                                      types.SimpleNamespace(cached=lambda i: (None, None)), 25).uploads_summary()["edsm"])


class HeldStillQueues(unittest.TestCase):
    """A refused key holds EDSM's sending, not its queueing: what is played meanwhile goes once the key is fixed (the
    author's 203s, 2026-10-08: twelve events played while held were skipped when the hold cleared)."""

    def test_held_then_fixed(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d])
        p.start()
        self.addCleanup(p.stop)
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        st = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        st.config_path = os.path.join(d, "cfg.toml")
        path = os.path.join(d, "Journal.2026-10-08T100000.01.log")
        now = lambda ago: iso_ts(time.time() - ago)

        def write(*events):
            with open(path, "a", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
        write({"timestamp": now(600), "event": "Fileheader", "gameversion": "4.4.1.1", "build": "r1 "},
              {"timestamp": now(599), "event": "LoadGame", "Commander": "Briadin"})
        j.scan_dir(d, commit_each=True, upload="catchup")
        st.set_upload("edsm", True)
        st.set_edsm_account("Briadin", "Briadin", KEY)
        st.upload_report("edsm", {"error": None, "at": 1, "results": [(1, "held", "203 EDSM refused the commander name or API key", None)]})
        self.assertFalse(st.upload_on("edsm"))                           # not sending...
        write(dict(JUMP, timestamp=now(300)), {"timestamp": now(200), "event": "Scan", "BodyName": "A 1"})
        j.scan_dir(d, upload="live")
        db.commit()
        self.assertEqual([r["schema"] for r in db.execute("SELECT schema FROM upload_queue WHERE service='edsm'")],
                         ["FSDJump", "Scan"])                             # ...but still queueing
        st.set_edsm_account("Briadin", "Briadin", KEY)                    # a new key: sending again
        self.assertTrue(st.upload_on("edsm"))
        self.assertEqual(len(U.due(db, "edsm", time.time() + S.HOLD_S)), 2)


if __name__ == "__main__":
    unittest.main()
