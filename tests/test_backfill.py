"""Unit tests: filling a gap in EDSM's flight log (S47, outrider/backfill.py and the server's Check, Preview, guard and
Send). Fake sessions answer in the documented shapes (tests/fixtures/account_checks.json); nothing here reaches EDSM, no
real key is used, and every journal is written into a scratch folder.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import json
import os
import shutil
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider, _HwSession  # also puts the repository root on sys.path
import outrider.backfill as BF  # noqa: E402
import outrider.edsm as E  # noqa: E402
import outrider.readclient as RC  # noqa: E402
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "fixtures", "account_checks.json"), encoding="utf-8") as _f:
    EX = json.load(_f)
KEY = "0123456789abcdef0123456789abcdef01234567"
T0 = BF.parse_when("2026-10-01 12:00")   # the journals below start here


def at(minutes):
    return iso_ts(T0 + minutes * 60)


def header(m, part=1, version="4.2.0.100"):
    return {"timestamp": at(m), "event": "Fileheader", "part": part, "gameversion": version, "build": "r1 "}


def loadgame(m, cmdr="Sample Pilot"):
    return {"timestamp": at(m), "event": "LoadGame", "FID": "F1", "Commander": cmdr, "Horizons": True, "Odyssey": True,
            "ShipID": 7}


def jump(m, name, addr):
    return {"timestamp": at(m), "event": "FSDJump", "StarSystem": name, "SystemAddress": addr, "StarPos": [1.0, 2.0, 3.0]}


class Pure(unittest.TestCase):

    def test_parse_when_and_windows(self):
        self.assertEqual(BF.parse_when("2026-10-09 21:14"), BF.parse_when("2026-10-09T21:14:00Z"))
        self.assertEqual(iso_ts(BF.parse_when("2026-10-09 21:14:05")), "2026-10-09T21:14:05Z")
        for bad in ("", "yesterday", "2026-02-30 10:00", "2026-10-09", None):
            self.assertIsNone(BF.parse_when(bad), bad)
        self.assertEqual(BF.windows(0, 10, 4), [(0, 4), (4, 8), (8, 10)])
        self.assertEqual(BF.windows(5, 5, 4), [])

    def test_files_for(self):
        names = ["Journal.2026-09-20T100000.01.log", "Journal.2026-09-28T100000.01.log", "Journal.2026-10-01T100000.01.log",
                 "Journal.2026-10-03T100000.01.log", "Journal.2026-10-09T100000.01.log", "Journal.260925100000.01.log"]
        files = {n: n for n in names}
        got = BF.files_for(files, BF.parse_when("2026-10-02 00:00"), BF.parse_when("2026-10-04 00:00"))
        # the file started last before the range (with a day's slack) and those within it; the old name form sorts too
        self.assertEqual(got, ["Journal.2026-09-28T100000.01.log", "Journal.2026-10-01T100000.01.log", "Journal.2026-10-03T100000.01.log"])

    def test_strict_answer_counts_102_as_not_taken(self):
        rows = [{"id": i} for i in range(6)]
        reply = {"msgnum": 100, "msg": "OK", "events": [{"msgnum": c, "msg": m} for c, m in (
            (100, "OK"), (101, "Message already stored"), (102, "Message older than the stored one"),
            (103, "Duplicate event request"), (104, "Crew session"), (302, "Event not processed"))]}
        results, tally = E.backfill_answer(rows, reply)
        self.assertEqual([s for _, s, _, _ in results], ["sent", "sent", "dropped", "sent", "dropped", "dropped"])
        self.assertEqual(tally, {"stored": 1, "already": 1, "older": 1, "duplicate": 1, "crew": 1, "refused": 1})
        self.assertEqual(results[2][2], "102 Message older than the stored one")
        # the live stream's answer() takes 102 as sent: right there, wrong for a backfill (the review's S47 finding)
        self.assertEqual(E.answer(rows, reply)[2][1], "sent")
        held, tally = E.backfill_answer(rows[:1], {"msgnum": 203, "msg": "Commander name/API Key not found"})
        self.assertEqual((held[0][1], tally), ("held", {}))
        with self.assertRaises(ValueError):
            E.backfill_answer(rows, "<html>")


class Rebuild(unittest.TestCase):
    """The range's EDSM events rebuilt from the journals: one copy per file name, a continuation's session carried on,
    only that commander, only what EDSM wants, keyed like the outbox."""

    def setUp(self):
        self.live, self.archive = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.live)
        self.addCleanup(shutil.rmtree, self.archive)

    def write(self, folder, name, events):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            for e in events:
                f.write(json.dumps(e) + "\r\n")
        return path

    def journals(self):
        first = [header(0), loadgame(1), jump(5, "Before", 1), jump(30, "Alpha", 2),
                 {"timestamp": at(31), "event": "Music", "MusicTrack": "Exploration"},          # on EDSM's discard list
                 {"timestamp": at(32), "event": "Scan", "BodyName": "Alpha 1", "BodyID": 1, "ScanType": "Detailed"},
                 {"timestamp": at(40), "event": "Continued", "Part": 2}]
        second = [header(40, part=2), jump(50, "Beta", 3), jump(200, "After", 4)]   # part 2: no LoadGame, same session
        other = [header(60), loadgame(61, cmdr="Someone Else"), jump(70, "Theirs", 5)]
        self.write(self.archive, "Journal.2026-10-01T120000.01.log", first[:4])             # an archived copy, shorter
        self.write(self.live, "Journal.2026-10-01T120000.01.log", first)
        self.write(self.live, "Journal.2026-10-01T124000.02.log", second)
        self.write(self.live, "Journal.2026-10-01T130000.01.log", other)

    def test_range_commander_and_keys(self):
        self.journals()
        rows, files = BF.rebuild([self.live, self.archive], T0 + 20 * 60, T0 + 100 * 60, "Sample Pilot")
        self.assertEqual([(r["event"], r["message"].get("StarSystem") or r["message"].get("BodyName")) for r in rows],
                         [("FSDJump", "Alpha"), ("Scan", "Alpha 1"), ("FSDJump", "Beta")])
        self.assertEqual(files, 3)
        scan = rows[1]["message"]
        self.assertEqual((scan["_systemName"], scan["_systemAddress"], scan["_shipId"]), ("Alpha", 2, 7))   # EDSM's transient fields
        self.assertEqual((rows[2]["cmdr"], rows[2]["gameversion"]), ("Sample Pilot", "4.2.0.100"))          # carried into part 2
        name, off = rows[0]["source"].split(":")
        with open(os.path.join(self.live, name), "rb") as f:
            f.seek(int(off))
            self.assertEqual(json.loads(f.readline())["StarSystem"], "Alpha")                               # the outbox's key
        skipped, _ = BF.rebuild([self.live], T0 + 20 * 60, T0 + 100 * 60, "Sample Pilot", skip={rows[0]["source"]})
        self.assertEqual(len(skipped), 2)                    # what EDSM's live stream had is never sent again
        theirs, _ = BF.rebuild([self.live], T0, T0 + 300 * 60, "Someone Else")
        self.assertEqual([r["message"]["StarSystem"] for r in theirs if r["event"] == "FSDJump"], ["Theirs"])

    def test_summary_groups_requests_as_the_sender(self):
        rows = [{"event": "FSDJump", "ts": at(i), "cmdr": "A", "gameversion": "4.2" if i < 3 else "4.3", "gamebuild": "r1"}
                for i in range(5)]
        s = BF.summary(rows, gap_s=10, batch=2)
        self.assertEqual((s["events"], s["jumps"], s["requests"], s["seconds"]), (5, 5, 3, 20))   # [2] [1: version ends] [2]
        self.assertEqual(BF.summary([])["requests"], 0)


class Server(unittest.TestCase):
    """The Check, the Preview, the guard and Send, through the route; the sender and its report."""

    def setUp(self):
        self.live = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.live)
        for name, value in (("LIVE_DIRS", [self.live]), ("LEGACY_DIRS", [])):
            p = unittest.mock.patch.object(ed_outrider, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.edsm_gate = U.Gate(0)
        cfg = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cfg)
        self.state.config_path = os.path.join(cfg, "ed_outrider.toml")
        self.state.set_edsm_account("Sample Pilot", "Sample EDSM", KEY)
        self.printed, self.slept, self.hang = [], [], False
        p = unittest.mock.patch("builtins.print", lambda *a, **k: self.printed.append(" ".join(map(str, a))))
        p.start()
        self.addCleanup(p.stop)

        async def no_wait(seconds):   # readclient.retrying's waits: kept with the job's line meanwhile, never slept
            self.slept.append((seconds, (self.state.edsm_bf_job or {}).get("text")))
            if self.hang:
                await asyncio.Event().wait()   # until Stop cancels it
        p = unittest.mock.patch.object(RC, "_sleep", no_wait)
        p.start()
        self.addCleanup(p.stop)
        with open(os.path.join(self.live, "Journal.2026-10-01T120000.01.log"), "w", encoding="utf-8") as f:
            for e in (header(0), loadgame(1), jump(30, "Alpha", 2), jump(40, "Beta", 3), jump(50, "Gamma", 4)):
                f.write(json.dumps(e) + "\n")

    def post(self, script, *bodies, wait=True):
        """POST each body to /api/uploads/edsm/backfill with a fake EDSM; a background Check or guard is awaited."""
        from aiohttp.test_utils import TestClient, TestServer
        self.state.upload_session = _HwSession(script)

        async def go():
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for body in bodies:
                    r = await c.post("/api/uploads/edsm/backfill", json=body)
                    out.append((r.status, await r.json()))
                    if wait and self.state.edsm_bf_task:
                        await self.state.edsm_bf_task
            return out
        return asyncio.run(go())

    def logs(self, *entries):
        return {"msgnum": 100, "msg": "OK", "logs": [{"system": s, "systemId64": 1, "date": d} for s, d in entries]}

    def test_check_from_edsm_since(self):
        ed_outrider.meta_set(self.db, "edsm_since", at(45))
        self.db.execute("INSERT INTO jumps (ts, id64, name) VALUES (?, 2, 'Alpha'), (?, 3, 'Beta')", (at(30), at(40)))
        pos = dict(EX["edsm_position_ok"], date="2026-10-01 12:10:00")
        [(status, j)] = self.post([(200, pos)], {"action": "check", "commander": "Sample Pilot"})
        self.assertEqual(status, 202)
        job = self.state.edsm_bf_job
        self.assertEqual((job["state"], job["result"]["start"], job["result"]["end"], job["result"]["jumps"]),
                         ("done", "2026-10-01T12:10:01Z", at(45), 2))
        self.assertEqual(job["text"], "EDSM's flight log ends 2026-10-01 12:10 UTC at Sample Reach; Outrider has sent since "
                                      "2026-10-01 12:45 UTC; your journals have 2 jumps between.")
        call = self.state.upload_session.calls[0]
        self.assertEqual((call[1], call[2]["commanderName"]), (ed_outrider.outrider.readclient.EDSM_POSITION_URL, "Sample EDSM"))
        self.assertFalse([p for p in self.printed if KEY in p])
        self.assertNotIn(KEY, json.dumps(self.state.uploads_summary()))

    def test_check_walks_back_when_edsm_has_later_entries(self):
        ed_outrider.meta_set(self.db, "edsm_since", "2026-09-10T00:00:00Z")
        pos = dict(EX["edsm_position_ok"], date="2026-10-01 12:00:00")   # Outrider's own sends since
        script = [(200, pos), (200, self.logs()), (200, self.logs(("Old Place", "2026-09-01 08:00:00"), ("Late", "2026-09-11 08:00:00")))]
        self.post(script, {"action": "check", "commander": "Sample Pilot"})
        job = self.state.edsm_bf_job
        self.assertEqual(job["result"]["log_end"], {"date": "2026-09-01T08:00:00Z", "system": "Old Place"})
        self.assertEqual((job["result"]["start"], job["result"]["end"]), ("2026-09-01T08:00:01Z", "2026-09-10T00:00:00Z"))
        calls = self.state.upload_session.calls
        self.assertEqual(len(calls), 3)                          # get-position, then two weeks of get-logs going back
        self.assertEqual((calls[1][2]["startDateTime"], calls[1][2]["endDateTime"]), ("2026-09-03 00:00:00", "2026-09-10 00:00:00"))

    def test_check_says_unknown_without_edsm_since(self):
        self.state.upload_cfg["edsm"]["enabled"] = True        # on from before edsm_since was kept
        pos = dict(EX["edsm_position_ok"], date="2026-10-01 12:10:00")
        self.post([(200, pos)], {"action": "check", "commander": "Sample Pilot"})
        job = self.state.edsm_bf_job
        self.assertIn("since when Outrider has sent: unknown", job["text"])
        self.assertIsNone(job["result"]["since"])
        self.assertEqual(job["result"]["start"], "2026-10-01T12:10:01Z")   # to now: the range is the player's to narrow

    def test_check_failures_say_the_kind_only(self):
        self.post([ConnectionRefusedError(f"https://www.edsm.net/x?apiKey={KEY}")], {"action": "check", "commander": "Sample Pilot"})
        self.assertEqual(self.state.edsm_bf_job["text"], "Couldn't reach EDSM: the connection was refused (tried 6 times)")
        self.assertEqual([s for s, _ in self.slept], [30, 60, 120, 300, 600])   # asked again, then it stops
        self.slept.clear()
        self.post([(200, EX["edsm_credits_wrong"])], {"action": "check", "commander": "Sample Pilot"})
        self.assertEqual(self.state.edsm_bf_job["text"], "EDSM: 203 commander name or API key not found")
        self.assertEqual((len(self.state.upload_session.calls), self.slept), (1, []))   # a refusal: at once
        [(status, j)] = self.post([(200, {})], {"action": "check", "commander": "Nobody"})
        self.assertEqual(status, 400)                            # no key stored for that commander
        self.assertFalse([p for p in self.printed if KEY in p])

    def test_check_and_guard_ride_out_a_failure_that_passes(self):
        """S47's reads are asked again after a timeout or a 5xx (the job's line says when) instead of failing at once;
        reads only, so nothing a retry repeats was stored."""
        ed_outrider.meta_set(self.db, "edsm_since", at(45))
        pos = dict(EX["edsm_position_ok"], date="2026-10-01 12:10:00")
        self.post([asyncio.TimeoutError(), (502, {}), (200, pos)], {"action": "check", "commander": "Sample Pilot"})
        job = self.state.edsm_bf_job
        self.assertEqual((job["state"], job["result"]["start"]), ("done", "2026-10-01T12:10:01Z"))
        self.assertEqual([s for s, _ in self.slept], [30, 60])
        self.assertRegex(self.slept[0][1], r"^EDSM not answering: trying again at \d\d:\d\d \(attempt 2 of 6\)…$")
        self.slept.clear()
        self.post([(200, {})], dict(self.range(), action="preview"))
        self.post([asyncio.TimeoutError(), (200, self.logs())], dict(self.range(), action="send"))
        self.assertEqual((self.state.edsm_bf_job["state"], len(self.state.upload_session.calls)), ("done", 2))
        self.assertEqual(self.queued(), [("edsm_bf", "FSDJump", "queued"), ("edsm_bf", "FSDJump", "queued")])
        self.assertEqual([s for s, _ in self.slept], [30])
        self.assertEqual(self.slept[0][1].split(" again at")[0], "EDSM not answering: trying")   # one week: no "week 1 of 1"

    def test_stop_ends_a_check_waiting_to_ask_again(self):
        self.hang = True
        [(s1, _), (s2, j)] = self.post([asyncio.TimeoutError()], {"action": "check", "commander": "Sample Pilot"},
                                       {"action": "stop"}, wait=False)
        self.assertEqual((s1, s2, j["job"]["state"], j["job"]["text"]), (202, 200, "failed", "stopped by you"))
        self.assertIsNone(self.state.edsm_backfill())                  # no backfill was under way

    def range(self, **kw):
        return dict({"commander": "Sample Pilot", "start": "2026-10-01 12:20", "end": "2026-10-01 12:45"}, **kw)

    def queued(self):
        return [tuple(r) for r in self.db.execute("SELECT service, schema, state FROM upload_queue ORDER BY id")]

    def test_preview_then_the_guard_refuses_a_range_edsm_has(self):
        [(s1, j1), (s2, j2)] = self.post([(200, self.logs(("Beta", "2026-10-01 12:40:00")))],
                                         dict(self.range(), action="send"), dict(self.range(), action="preview"))
        self.assertEqual(s1, 409)                                # no Preview yet
        self.assertEqual((s2, j2["preview"]["summary"]["events"], j2["preview"]["summary"]["jumps"]), (200, 2, 2))
        self.assertEqual(j2["preview"]["start"], "2026-10-01T12:20:00Z")
        self.assertNotIn("rows", j2["preview"])                  # the events themselves stay on the server
        [(status, j)] = self.post([(200, self.logs(("Beta", "2026-10-01 12:40:00")))], dict(self.range(), action="send"))
        self.assertEqual(status, 202)
        self.assertEqual(self.state.edsm_bf_job["state"], "failed")
        self.assertIn("EDSM's flight log already has 1 jump in this range", self.state.edsm_bf_job["text"])
        self.assertEqual(self.queued(), [])                      # never resend what EDSM has
        self.assertIsNone(self.state.edsm_backfill())

    def test_send_queues_once_then_sends_strictly(self):
        self.post([(200, {})], dict(self.range(), action="preview"))
        [(status, _)] = self.post([(200, self.logs())], dict(self.range(), action="send"))
        self.assertEqual((status, self.state.edsm_bf_job["state"]), (202, "done"))
        self.assertEqual(self.queued(), [("edsm_bf", "FSDJump", "queued"), ("edsm_bf", "FSDJump", "queued")])
        bf = self.state.edsm_backfill()
        self.assertEqual((bf["state"], bf["total"], bf["commander"]), ("running", 2, "Sample Pilot"))
        self.assertTrue(self.state.edsm_bf_on("edsm_bf"))
        self.assertFalse(self.state.upload_on("edsm"))           # EDSM's live stream is a separate thing
        [(status, j)] = self.post([(200, {})], dict(self.range(), action="preview"))
        self.assertEqual(status, 409)                            # one at a time
        # the sender: EDSM stores one, finds the other older than its log (102): counted apart, not called sent
        self.state.upload_session = _HwSession([(200, {"msgnum": 100, "msg": "OK", "events": [
            {"msgnum": 100, "msg": "OK"}, {"msgnum": 102, "msg": "Message older than the stored one"}]})])
        rows = U.due(self.db, "edsm_bf", ed_outrider.time.time())
        results = asyncio.run(self.state.edsm_bf_send(rows))
        body = self.state.upload_session.calls[0][2]
        self.assertEqual((body["fromSoftware"], body["apiKey"], [e["StarSystem"] for e in body["message"]]),
                         ("ED Outrider", KEY, ["Alpha", "Beta"]))
        for row_id, st, status, retry in results:
            U.settle(self.db, row_id, st, status, 0)
        self.state.edsm_bf_report("edsm_bf", {"error": None, "results": results, "at": 0, "raised": None, "wait": 10})
        bf = self.state.edsm_backfill()
        self.assertEqual((bf["state"], bf["counts"]), ("done", {"stored": 1, "older": 1}))
        self.assertEqual(self.queued(), [("edsm_bf", "FSDJump", "sent"), ("edsm_bf", "FSDJump", "dropped")])
        # the same range again: every line is in the outbox already, nothing new
        self.post([(200, {})], dict(self.range(), action="preview"))
        self.post([(200, self.logs())], dict(self.range(), action="send"))
        self.assertEqual(self.state.edsm_bf_job["text"], "every event of this range was queued before: nothing new to send")

    def start(self, **kw):
        self.post([(200, {})], dict(self.range(**kw), action="preview"))
        self.post([(200, self.logs())], dict(self.range(**kw), action="send"))

    def test_first_request_all_102_stops_it(self):
        self.start(end="2026-10-01 12:55")
        rows = U.due(self.db, "edsm_bf", ed_outrider.time.time(), 2)   # the first request: two of the three
        self.state.upload_session = _HwSession([(200, {"msgnum": 100, "events": [{"msgnum": 102}, {"msgnum": 102}]})])
        results = asyncio.run(self.state.edsm_bf_send(rows))
        for row_id, st, status, retry in results:
            U.settle(self.db, row_id, st, status, 0)
        self.state.edsm_bf_report("edsm_bf", {"error": None, "results": results, "at": 0, "raised": None, "wait": 10})
        bf = self.state.edsm_backfill()
        self.assertEqual((bf["state"], bf["unsent"]), ("stopped", 1))
        self.assertIn("does not take back-dated events", bf["why"])
        self.assertEqual([s for _, _, s in self.queued()], ["dropped", "dropped", "dropped"])

    def test_a_new_backfill_does_not_carry_the_last_ones_unsent(self):
        """Review 2026-10-23 S3-B2: a backfill stopped with rows unsent left "N not sent" on the next one's line."""
        self.start()
        [(status, j)] = self.post([(200, {})], {"action": "stop"})
        self.assertEqual(j["progress"]["unsent"], 2)
        self.start(end="2026-10-01 12:55")                              # one more event: a new backfill
        bf = self.state.edsm_backfill()
        self.assertEqual(bf["state"], "running", bf)
        self.assertFalse(bf.get("unsent"))

    def test_dry_run_hold_go_on_and_stop(self):
        self.start()
        rows = U.due(self.db, "edsm_bf", ed_outrider.time.time())
        with unittest.mock.patch.dict(os.environ, {E.DRY_ENV: "1"}), unittest.mock.patch.object(self.state, "edsm_dry_path", None):
            results = asyncio.run(self.state.edsm_bf_send(rows))
        self.assertEqual({st for _, st, _, _ in results}, {"dry"})
        self.assertEqual(self.state.edsm_backfill()["counts"], {"dry": 2})
        # a refused key holds it until Go on; Stop drops what waits
        self.state.edsm_bf_report("edsm_bf", {"error": None, "at": 0, "raised": None, "wait": 10,
                                              "results": [(rows[0]["id"], "held", "203 EDSM refused the commander name or API key", None)]})
        self.assertEqual((self.state.edsm_backfill()["state"], self.state.edsm_bf_on()), ("held", False))
        [(status, j)] = self.post([(200, {})], {"action": "resume"})
        self.assertEqual((status, j["progress"]["state"]), (200, "running"))
        [(status, j)] = self.post([(200, {})], {"action": "stop"})
        self.assertEqual((status, j["progress"]["state"], j["progress"]["unsent"]), (200, "stopped", 2))
        self.assertEqual([s for _, _, s in self.queued()], ["dropped", "dropped"])
        self.assertEqual(self.post([(200, {})], {"action": "stop"})[0][0], 409)

    def test_never_sent_under_simulate_or_another_uploader(self):
        """A backfill left running (its state and queue are in the database) sends nothing from an Outrider started with
        --simulate on the same data, nor from one while another Outrider holds the EDSM uploader lease; the Settings
        block says why it waits."""
        self.start()
        self.assertTrue(self.state.edsm_bf_on("edsm_bf"))
        sent = []

        async def send(rows):
            sent.append(rows)
            return [(r["id"], "sent", "200", None) for r in rows]

        class Stop(Exception):
            pass

        async def sleep(secs):
            raise Stop

        def drain():
            with self.assertRaises(Stop):
                asyncio.run(U.upload_loop("edsm_bf", self.db, send, self.state.edsm_bf_on, sleep=sleep))

        self.state.simulate = True
        self.assertFalse(self.state.edsm_bf_on("edsm_bf"))
        drain()
        self.assertEqual(sent, [])
        self.assertIn("--simulate", self.state.edsm_backfill_summary()["paused"])
        self.state.simulate = False
        self.state.lease_others = {"abc123": {"host": "other-pc", "services": ["edsm"], "wanted": ["edsm"], "legacy": False}}
        self.assertFalse(self.state.edsm_bf_on("edsm_bf"))
        drain()
        self.assertEqual(sent, [])
        self.assertEqual(self.state.edsm_backfill_summary()["paused"], "another Outrider (other-pc) uploads to EDSM")
        self.state.lease_others = {}
        self.state.lease_hold = {"edsm": "other-pc"}   # switched on here too, giving way to the other
        self.assertFalse(self.state.edsm_bf_on("edsm_bf"))
        self.state.lease_hold = {}
        self.assertTrue(self.state.edsm_bf_on("edsm_bf"))
        self.assertIsNone(self.state.edsm_backfill_summary()["paused"])

    def test_switching_edsm_on_records_since(self):
        self.assertIsNone(ed_outrider.meta_get(self.db, "edsm_since"))
        self.state.set_upload("edsm", True)
        since = ed_outrider.meta_get(self.db, "edsm_since")
        self.assertTrue(since and since.endswith("Z"))
        self.assertEqual(self.state.edsm_backfill_summary()["since"], since)

    def test_bad_requests(self):
        cases = [{"action": "fly"}, dict(self.range(start="soon"), action="preview"),
                 dict(self.range(start="2026-10-02 00:00"), action="preview"),                  # after the end
                 dict(self.range(start="2020-01-01 00:00"), action="preview"),                  # over BF_MAX_DAYS
                 dict(self.range(end="2099-01-01 00:00"), action="preview")]                    # the future
        self.assertEqual([s for s, _ in self.post([(200, {})], *cases)], [400] * len(cases))


if __name__ == "__main__":
    unittest.main()
