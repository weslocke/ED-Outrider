"""Unit tests: importing your EDSM flight log from before your journals (S67, outrider/edsmlog.py and the server's
Import, Stop, Go on and Remove). Fake sessions answer in get-logs' documented shape (tests/fixtures/account_checks.json);
nothing here reaches EDSM or Spansh and no real key is used.

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

from support import ed_outrider, _HwSession  # also puts the repository root on sys.path
import outrider.edsmlog as EL  # noqa: E402
import outrider.readclient as RC  # noqa: E402
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts, ts_seconds  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "fixtures", "account_checks.json"), encoding="utf-8") as _f:
    EX = json.load(_f)
KEY = "0123456789abcdef0123456789abcdef01234567"
T0 = ts_seconds("2026-10-01T12:00:00Z")   # the first journal arrival
DAY = 86400


def at(seconds):
    return iso_ts(T0 + seconds)


def entry(name, t, id64=None, xyz=None):
    """One of get-logs' entries as readclient.edsm_logs_answer gives it."""
    return {"system": name, "id64": id64, "coords": dict(zip("xyz", xyz)) if xyz else None, "date": iso_ts(t)}


def journal(db):
    """Two journal arrivals from T0 (Alpha, Beta) and their visits."""
    for ts, id64, name, xyz in ((at(0), 2, "Alpha", (0.0, 0.0, 0.0)), (at(600), 3, "Beta", (5.0, 0.0, 0.0))):
        db.execute("INSERT INTO jumps (ts, id64, name, x, y, z, kind) VALUES (?, ?, ?, ?, ?, ?, 'FSDJump')", (ts, id64, name, *xyz))
        db.execute("INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?, 1)", (id64, name, *xyz, ts, ts))


class Rules(unittest.TestCase):
    """Which kept entries count as visits: before the oldest journal, no journal arrival within a minute; applied at
    every read, so a re-read or an older legacy folder moves it."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        journal(self.db)

    def test_counted_cutoff_match_and_remove(self):
        n = EL.store(self.db, "Sample Pilot", [
            entry("Old Place", T0 - 10 * DAY, 101, (10, 0, 0)), entry("Old Place", T0 - 9 * DAY, 101, (10, 0, 0)),
            entry("Alpha", T0 - 30, 2, (0, 0, 0)),                    # 30 s before the first journal arrival: that one
            entry("Later", T0 + 3600, 103, (1, 1, 1))])               # after the first journal: the journals say
        self.assertEqual(n, 4)
        self.assertEqual(EL.store(self.db, "Sample Pilot", [entry("Old Place", T0 - 10 * DAY, 101, (10, 0, 0))]), 0)   # no doubles
        self.assertEqual(EL.counted(self.db), {"visits": 2, "systems": 1, "first": iso_ts(T0 - 10 * DAY), "last": iso_ts(T0 - 9 * DAY)})
        self.assertEqual(EL.ids(self.db), {101})
        [r] = EL.rows(self.db, box=(5, 15, -1, 1, -1, 1))
        self.assertEqual((r["id64"], r["count"], r["first_ts"]), (101, 2, iso_ts(T0 - 10 * DAY)))
        self.assertEqual(EL.rows(self.db, box=(50, 60, -1, 1, -1, 1)), [])
        self.assertEqual(EL.visit(self.db, 101)["count"], 2)
        # an older journal read later (a legacy folder): what it covers is the journal's, the rest stays EDSM's
        self.db.execute("INSERT INTO jumps (ts, id64, name, x, y, z, kind) VALUES (?, 101, 'Old Place', 10, 0, 0, 'FSDJump')",
                        (iso_ts(T0 - 9 * DAY - 20),))
        self.assertEqual(EL.counted(self.db)["visits"], 1)
        self.assertEqual(EL.stored(self.db), 4)   # nothing thrown away
        self.assertEqual(EL.remove(self.db), 4)
        self.assertIsNone(EL.counted(self.db))
        self.assertEqual(self.db.execute("SELECT count(*) FROM visits").fetchone()[0], 2)   # your journals' visits stay

    def test_sessions_and_summary(self):
        EL.store(self.db, "Sample Pilot", [entry("A", T0 - 10 * DAY, 11, (0, 0, 0)), entry("B", T0 - 10 * DAY + 600, 12, (3, 4, 0)),
                                           entry("C", T0 - 5 * DAY, 13, (0, 0, 100)), entry("Nowhere", T0 - 5 * DAY + 60)])
        ss = EL.sessions(self.db)
        self.assertEqual([(s["start"], s["jumps"], s["ly"], s["edsm"]) for s in ss],
                         [(iso_ts(T0 - 5 * DAY), 2, 0.0, True), (iso_ts(T0 - 10 * DAY), 2, 5.0, True)])
        self.assertEqual((ss[0]["max_sol"], ss[0]["firsts"], ss[0]["sold"]), (100, 0, 0))   # what you did there: unknown
        self.assertEqual(EL.summary(ss), {"sessions": 2, "jumps": 4, "ly": 5.0, "since": iso_ts(T0 - 10 * DAY),
                                          "until": iso_ts(T0 - 5 * DAY + 60)})
        self.assertEqual(len(EL.sessions(self.db, since=iso_ts(T0 - 7 * DAY))), 1)
        self.assertEqual(EL.unlocated(self.db), ["Nowhere"])
        EL.set_location(self.db, "Nowhere", 14, 1.0, 2.0, 3.0)
        self.assertEqual(EL.locate(self.db, 14), ("Nowhere", 1.0, 2.0, 3.0))

    def test_twenty_thousand_entries_stay_quick(self):
        logs = [entry(f"Sys {i}", T0 - DAY - i * 300, 10_000 + i, (i % 1000, (i // 1000) % 50, i % 7)) for i in range(20000)]
        EL.store(self.db, "Sample Pilot", logs)
        t = time.perf_counter()
        ids = EL.ids(self.db)
        box = EL.rows(self.db, box=(0, 100, 0, 10, 0, 7))
        c = EL.counted(self.db)
        took = time.perf_counter() - t
        self.assertEqual((len(ids), c["visits"]), (20000, 20000))
        self.assertTrue(box)
        self.assertLess(took, 1.0, f"three reads over 20k entries took {took:.2f} s")


class Server(unittest.TestCase):
    """Import, Stop, Go on and Remove through the route; where the imported visits show and where they must not."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        journal(self.db)
        self.located = []

        async def system_record(name):
            self.located.append(name)
            return {"name": name, "id64": 404, "x": 7.0, "y": 8.0, "z": 9.0} if name == "Mystery" else None

        async def sphere(pos, radius, pages=None):
            return []
        spansh = types.SimpleNamespace(cached=lambda i: (None, None), system_record=system_record, sphere=sphere)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), spansh, 25)
        self.state.edsm_gate = U.Gate(0)
        cfg = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cfg)
        self.state.config_path = os.path.join(cfg, "ed_outrider.toml")
        self.state.set_edsm_account("Sample Pilot", "Sample EDSM", KEY)
        self.printed, self.slept = [], []

        async def no_wait(seconds):   # readclient.retrying's waits: kept with the progress said meanwhile, never slept
            self.slept.append((seconds, (self.state.edsm_import() or {}).get("why")))
        for patch in (unittest.mock.patch("builtins.print", lambda *a, **k: self.printed.append(" ".join(map(str, a)))),
                      unittest.mock.patch.object(RC, "_sleep", no_wait),
                      unittest.mock.patch.object(EL, "GAME_LAUNCH", at(-21 * DAY)),   # three weeks to read, not 600
                      unittest.mock.patch.object(ed_outrider, "IMPORT_GAP_S", 0),
                      unittest.mock.patch.object(ed_outrider, "IMPORT_LOOKUP_GAP_S", 0),
                      unittest.mock.patch.object(ed_outrider, "IMPORT_RATE_WAIT_S", 0)):
            patch.start()
            self.addCleanup(patch.stop)

    def post(self, script, *bodies):
        """POST each body to /api/uploads/edsm/import with a fake EDSM; the background import is awaited."""
        from aiohttp.test_utils import TestClient, TestServer
        self.state.upload_session = _HwSession(script)

        async def go():
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for body in bodies:
                    r = await c.post("/api/uploads/edsm/import", json=body)
                    out.append((r.status, await r.json()))
                    if self.state.edsm_import_task:
                        try:
                            await self.state.edsm_import_task
                        except asyncio.CancelledError:
                            pass
            return out
        return asyncio.run(go())

    @staticmethod
    def logs(*entries):
        return (200, {"msgnum": 100, "msg": "OK", "logs": [dict({"system": s, "systemId64": i, "date": d}, **(
            {"coordinates": dict(zip("xyz", c))} if c else {})) for s, i, d, c in entries]})

    def weeks(self):
        """EDSM's answers for the three weeks, newest first, as the import asks for them."""
        return [self.logs(("Gamma Old", 101, "2026-09-30 10:00:00", (10, 0, 0)), ("Alpha", 2, "2026-10-01 11:59:30", (0, 0, 0))),
                self.logs(("Delta Old", 102, "2026-09-20 08:00:00", (20, 0, 0)), ("Beta", 3, "2026-09-21 08:00:00", (5, 0, 0))),
                self.logs(("Mystery", None, "2026-09-12 08:00:00", None))]

    def start(self, script):
        return self.post(script, {"action": "start", "commander": "Sample Pilot"})

    def test_import_walks_back_from_the_first_journal(self):
        [(status, j)] = self.start(self.weeks())
        self.assertEqual(status, 202)
        calls = self.state.upload_session.calls
        self.assertEqual([(c[2]["startDateTime"], c[2]["endDateTime"]) for c in calls],
                         [("2026-09-24 12:00:00", "2026-10-01 12:00:00"), ("2026-09-17 12:00:00", "2026-09-24 12:00:00"),
                          ("2026-09-10 12:00:00", "2026-09-17 12:00:00")])
        self.assertEqual((calls[0][1], calls[0][2]["commanderName"], calls[0][2]["showCoordinates"]),
                         (ed_outrider.outrider.readclient.EDSM_LOGS_URL, "Sample EDSM", "1"))
        p = self.state.edsm_import()
        self.assertEqual((p["state"], p["weeks"], p["weeks_done"], p["entries"], p["cursor"]), ("done", 3, 3, 5, at(-21 * DAY)))
        self.assertEqual(self.located, ["Mystery"])                       # EDSM gave no position: found by name
        s = self.state.edsm_import_summary()
        # Alpha 30 s before the first journal arrival is that arrival: 4 of the 5 count
        self.assertEqual(s["counted"], {"visits": 4, "systems": 4, "first": "2026-09-12T08:00:00Z", "last": "2026-09-30T10:00:00Z"})
        self.assertEqual(s["stored"], 5)
        self.assertNotIn(KEY, json.dumps(self.state.uploads_summary()))
        self.assertFalse([x for x in self.printed if KEY in x])
        [(status, j)] = self.start(self.weeks())
        self.assertEqual(status, 409)                                     # once: Remove them first
        self.assertIn("Remove them first", j["error"])

    def test_name_lookups_are_paced(self):
        """The systems EDSM gave no position for are looked up one at a time, IMPORT_LOOKUP_GAP_S apart (Spansh, then
        EDSM through edsm_gate): back to back, up to 500 of them made a burst a rate limit refuses."""
        asked = []

        async def system_record(name):
            asked.append(("spansh", name, time.monotonic()))
            return None

        async def edsm_system(name):
            asked.append(("edsm", name, time.monotonic()))
            return {"name": name, "id64": 77, "coords": {"x": 1.0, "y": 2.0, "z": 3.0}} if name == "C" else None
        self.state.spansh = types.SimpleNamespace(cached=lambda i: (None, None), system_record=system_record, edsm_system=edsm_system)
        EL.store(self.db, "Sample Pilot", [{"system": n, "date": f"2026-09-12T08:0{i}:00Z"} for i, n in enumerate("ABC")])
        gate = U.Gate(0)
        self.state.edsm_gate = gate
        with unittest.mock.patch.object(ed_outrider, "IMPORT_LOOKUP_GAP_S", 0.05), \
                unittest.mock.patch.object(gate, "wait", wraps=gate.wait) as edsm_waits:
            asyncio.run(self.state.edsm_import_resolve(EL.unlocated(self.db)))
        self.assertEqual([(k, n) for k, n, _ in asked], [("spansh", "A"), ("edsm", "A"), ("spansh", "B"), ("edsm", "B"),
                                                         ("spansh", "C"), ("edsm", "C")])
        gaps = [b[2] - a[2] for a, b in zip(asked, asked[1:])]
        self.assertGreaterEqual(min(gaps), 0.04)
        self.assertEqual(edsm_waits.call_count, 3)                        # each EDSM request through its gate
        self.assertEqual(EL.unlocated(self.db), ["A", "B"])               # C found by EDSM
        self.assertIn("of 3", self.state.edsm_import()["why"])

    def test_a_lookup_found_survives_another_writers_rollback(self):
        """Review 2026-10-23 S3-B5: a name found was written but committed only every tenth lookup, so a failed tick's
        rollback on the same connection between two lookups took it, for good."""
        async def system_record(name):
            if name == "B":
                self.db.rollback()   # the tick failing meanwhile, on the shared connection
            return {"name": name, "id64": 55, "x": 1.0, "y": 2.0, "z": 3.0} if name == "A" else None
        self.state.spansh = types.SimpleNamespace(cached=lambda i: (None, None), system_record=system_record,
                                                  edsm_system=lambda name: None)

        async def no_edsm(name, gate=None):
            hit = await system_record(name)
            return (hit["id64"], hit["x"], hit["y"], hit["z"]) if hit else None
        EL.store(self.db, "Sample Pilot", [{"system": n, "date": f"2026-09-12T08:0{i}:00Z"} for i, n in enumerate("AB")])
        self.db.commit()
        with unittest.mock.patch.object(self.state, "edsm_import_locate", no_edsm):
            asyncio.run(self.state.edsm_import_resolve(EL.unlocated(self.db)))
        self.assertEqual(EL.unlocated(self.db), ["B"])                    # A's place kept

    def test_stop_or_failure_then_go_on_and_remove(self):
        [(status, _)] = self.start([self.weeks()[0], ConnectionRefusedError(f"https://www.edsm.net/x?apiKey={KEY}")])
        p = self.state.edsm_import_summary()["progress"]
        # refused every time: asked again after each growing wait (about 20 min), then it stops with the reason
        self.assertEqual((p["state"], p["weeks_done"], p["why"]),
                         ("failed", 1, "Couldn't reach EDSM: the connection was refused (tried 6 times)"))
        self.assertEqual([s for s, _ in self.slept], [30, 60, 120, 300, 600])
        self.assertEqual(len(self.state.upload_session.calls), 1 + 6)
        self.assertFalse([x for x in self.printed if KEY in x])
        self.assertIn(101, self.state.visited)   # the week read before the failure counts at once (review S3-B4)
        # Go on: from where it stopped, the week already read not asked again
        self.start(self.weeks()[1:])
        calls = self.state.upload_session.calls
        self.assertEqual(calls[0][2]["endDateTime"], "2026-09-24 12:00:00")
        p = self.state.edsm_import()
        self.assertEqual((p["state"], p["weeks_done"], p["entries"]), ("done", 3, 5))
        self.assertIn(101, self.state.visited)
        # Remove them: EDSM's entries go, your journals' visits stay
        [(status, j)] = self.post([(200, {})], {"action": "remove"})
        self.assertEqual((status, j["progress"], j["counted"], j["stored"]), (200, None, None, 0))
        self.assertEqual({r[0] for r in self.db.execute("SELECT id64 FROM visits")}, {2, 3})
        self.assertNotIn(101, self.state.visited)
        self.assertIn(2, self.state.visited)

    def test_a_failure_that_passes_is_asked_again_and_the_week_kept_once(self):
        """The author's import stopped for good at week 203 of 438 on one timeout. A timeout, a 5xx and EDSM's own
        failing answer (msgnum 500) are asked again, the same week, after 30 s, 1 min, 2 min; the progress says when."""
        week1, week2, week3 = self.weeks()
        t0 = time.time()
        self.start([week1, asyncio.TimeoutError(), (503, {}), (200, {"msgnum": 500, "msg": "Exception"}), week2, week3])
        t1 = time.time()
        calls = self.state.upload_session.calls
        self.assertEqual(len(calls), 6)
        self.assertEqual({c[2]["endDateTime"] for c in calls[1:5]}, {"2026-09-24 12:00:00"})   # the same week each time
        p = self.state.edsm_import()
        self.assertEqual((p["state"], p["weeks_done"], p["entries"], p["why"]), ("done", 3, 5, None))
        self.assertEqual(EL.stored(self.db), 5)                           # each week kept once
        self.assertEqual([s for s, _ in self.slept], [30, 60, 120])
        whys = [w for _, w in self.slept]
        at = {time.strftime("%H:%M", time.localtime(t + 30)) for t in (t0, t1)}
        self.assertIn(whys[0], {f"EDSM not answering: trying week 2 again at {hm} (attempt 2 of 6)" for hm in at})
        self.assertRegex(whys[2], r"^EDSM not answering: trying week 2 again at \d\d:\d\d \(attempt 4 of 6\)$")
        self.assertTrue([x for x in self.printed if "EDSM not answering (timeout), week 2 again at" in x])
        self.assertFalse([x for x in self.printed if KEY in x])

    def test_a_refusal_stops_at_once(self):
        """A wrong name or key (203), a malformed answer, an HTTP 4xx: no retry, the import stops as before."""
        week1 = self.weeks()[0]
        cases = [((200, EX["edsm_credits_wrong"]), "EDSM: 203 commander name or API key not found"),
                 ((200, ["not", "an", "answer"]), "EDSM's answer was not understood"),
                 ((403, {}), "Couldn't reach EDSM: it refused the request")]
        for answer, why in cases:
            with self.subTest(why=why):
                self.db.execute("DELETE FROM meta WHERE key = 'edsm_import'")
                self.slept.clear()
                self.start([week1, answer, *self.weeks()[1:]])
                p = self.state.edsm_import()
                self.assertEqual((p["state"], p["weeks_done"], p["why"]), ("failed", 1, why))
                self.assertEqual((len(self.state.upload_session.calls), self.slept), (2, []))

    def test_name_lookups_ride_out_a_failure_and_stop_when_it_lasts(self):
        """The lookups after the weeks: Spansh failing in passing is asked again; failing past the retries stops the
        import "failed" (not done with the names silently unplaced), and Go on looks them up again."""
        fails = [6]

        async def system_record(name):
            self.located.append(name)
            if fails[0]:
                fails[0] -= 1
                raise asyncio.TimeoutError()
            return {"name": name, "id64": 404, "x": 7.0, "y": 8.0, "z": 9.0}
        self.state.spansh.system_record = system_record
        self.start(self.weeks())
        p = self.state.edsm_import()
        self.assertEqual((p["state"], p["weeks_done"], p["why"]), ("failed", 3, "Couldn't reach Spansh: timeout (tried 6 times)"))
        self.assertEqual(self.located, ["Mystery"] * 6)
        self.assertRegex(self.slept[0][1], r"^Spansh not answering: trying the lookup of Mystery again at \d\d:\d\d \(attempt 2 of 6\)$")
        self.assertEqual(EL.unlocated(self.db), ["Mystery"])
        fails[0] = 1                                                     # Go on: no week asked again, the name looked up
        self.start([(200, {})])
        self.assertEqual(self.state.upload_session.calls, [])
        p = self.state.edsm_import()
        self.assertEqual((p["state"], p["why"]), ("done", None))
        self.assertEqual(EL.unlocated(self.db), [])
        self.assertIn(404, self.state.visited)

    def test_slow_down_waits_and_a_stopped_outrider_says_stopped(self):
        from outrider.health import HttpError
        self.start([HttpError(429, "HTTP 429"), *self.weeks()])
        self.assertEqual(self.state.edsm_import()["state"], "done")       # asked again after the wait
        self.assertEqual(len(self.state.upload_session.calls), 4)
        self.state.edsm_import_set(state="running")                      # as a restart finds it
        self.assertEqual(self.state.edsm_import_summary()["progress"]["state"], "stopped")

    def test_bad_requests(self):
        cases = [{"action": "fly"}, {"action": "start", "commander": ""}, {"action": "start", "commander": "Nobody"}]
        self.assertEqual([s for s, _ in self.post([(200, {})], *cases)], [400, 400, 400])
        self.assertEqual(self.post([(200, {})], {"action": "stop"})[0][0], 409)

    def test_where_the_visits_show_and_where_not(self):
        before = self.state.history(3650)
        self.start(self.weeks())
        st = self.state
        # Nearby's marks, the target's verdict, Find, the route's hops, the boxel lists, the Map, History
        self.assertTrue({101, 102, 404} <= st.visited)
        asyncio.run(st.classify_target({"id64": 102, "name": "Delta Old"}, "another"))
        self.assertEqual(st.target_verdicts[102], "visited")
        status, f = asyncio.run(st.find_system("gamma old"))
        self.assertEqual((status, f["source"], f["visited"]["count"], f["visited"]["edsm"]), (200, "edsm_log", 1, True))
        self.assertEqual(st.locate(101), ("Gamma Old", 10.0, 0.0, 0.0))
        st.journals.pos = {"id64": 3, "name": "Beta", "x": 5.0, "y": 0.0, "z": 0.0}
        ed_outrider.meta_set(self.db, "route", {"hops": [{"id64": 3, "name": "Beta", "x": 5, "y": 0, "z": 0},
                                                         {"id64": 101, "name": "Gamma Old", "x": 10, "y": 0, "z": 0, "star_class": "K"},
                                                         {"id64": 909, "name": "Beyond", "x": 20, "y": 0, "z": 0, "star_class": "K"}]})
        self.assertTrue(st.route_summary()["hops"][0]["visited"])
        m = asyncio.run(st.map_payload(50, 10))
        pt = next(p for p in m["points"] if p["id"] == "101")
        self.assertEqual((pt["visited"], pt["edsm"]), (True, True))
        h = st.history(3650)
        edsm = [s for s in h["sessions"] if s.get("edsm")]
        self.assertEqual(sum(s["jumps"] for s in edsm), 4)
        self.assertEqual(h["edsm"]["jumps"], 4)
        # never firsts, sales or discoveries: the journals' all-time row and counts are as they were
        self.assertEqual(h["all_time"], before["all_time"])
        self.assertFalse(self.db.execute("SELECT count(*) FROM own_firsts").fetchone()[0])

    def test_search_marks_them_visited_without_firsts(self):
        EL.store(self.db, "Sample Pilot", [entry("Gamma Old", T0 - 20 * DAY, 101, (10, 0, 0))])
        crit = {"stars": None, "main_only": False, "planets": None, "rings": None, "hotspots": None, "mining": None, "bio": None}
        systems = {101: ("Gamma Old", 10.0, 0.0, 0.0, []), 77: ("Never", 11.0, 0.0, 0.0, [])}
        results, *_ = ed_outrider.Searcher(self.state).match(self.db, {"x": 0, "y": 0, "z": 0}, "online", 50, crit, [],
                                                              systems, 50, None)
        got = {r["name"]: (r["visited"], r["firsts"]) for r in results}
        self.assertEqual(got, {"Gamma Old": (True, None), "Never": (False, None)})

    def test_boxel_lists_count_them(self):
        EL.store(self.db, "Sample Pilot", [entry("Smojooe AA-A h3", T0 - 20 * DAY, 501, (1, 2, 3))])
        self.assertIn(3, self.state.boxel_visited("Smojooe AA-A h"))


if __name__ == "__main__":
    unittest.main()
