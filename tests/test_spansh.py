"""Unit tests: Spansh and EDSM records, the dump cache, search lookups and the firsts watch (all with fakes).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import json
import os
import time
import unittest
import unittest.mock
import sqlite3

from support import (  # also puts the repository root on sys.path
    guard_status, org, scan, types_ns,
)
import ed_outrider  # noqa: E402
import outrider.unsold  # noqa: E402


class DumpPricing(unittest.TestCase):
    """Batch 0.2: Spansh bodies are priced with the same formula as your scans."""

    def test_dump_body_priced_like_a_scan(self):
        dump = {"name": "Sys 1", "type": "Planet", "subType": "Water world", "earthMasses": 0.5,
                "terraformingState": "Candidate for terraforming", "bodyId": 1}
        r = ed_outrider.record_from_dump("Sys", dump)
        cv = ed_outrider.carto_values(r, False, None, None, None)
        expect = outrider.unsold.body_value({"PlanetClass": "Water world", "MassEM": 0.5, "TerraformState": "Terraformable"},
                                      True, False, True)
        self.assertEqual(cv["left"], expect)
        self.assertEqual(cv["now"], 0)
        # the same body once you have scanned it (no bonuses: someone discovered it) is worth the same in total
        f = {"was_discovered": 1, "was_mapped": 1}
        scanned = ed_outrider.carto_values(r, True, f, "unsold", None)
        self.assertEqual(scanned["now"] + scanned["left"], expect)

    def test_surface_sites_from_spansh(self):
        """S9-S3: a Spansh body with Guardian (and other) site counts carries them, marked reported by others; your
        own DSS's counts win in the merge, and a body without any carries none."""
        body = {"name": "Sys 3", "type": "Planet", "subType": "Rocky body", "bodyId": 3,
                "signals": {"signals": {"$SAA_SignalType_Guardian;": 2, "$SAA_SignalType_Geological;": 4,
                                        "$SAA_SignalType_Thargoid;": 0}}}
        r = ed_outrider.record_from_dump("Sys", body)
        self.assertEqual((r["sites"], r["sites_reported"], r["geo"]), ({"guardian": 2}, True, 4))
        self.assertEqual(ed_outrider.surface_sites([r]), [{"body": "3", "sites": {"guardian": 2}, "reported": True}])
        plain = ed_outrider.record_from_dump("Sys", dict(body, signals={"signals": {}}))
        self.assertNotIn("sites", plain)
        mine = {"name": "3", "type": "Planet", "rings": [], "sites": {"guardian": 3, "anomaly": 1}}
        [m] = ed_outrider.merge_records([r], {"3": mine}, {})
        self.assertEqual((m["sites"], m.get("sites_reported")), ({"guardian": 3, "anomaly": 1}, None))   # yours win
        [m] = ed_outrider.merge_records([r], {"3": dict(mine, sites=None)}, {})
        self.assertEqual((m["sites"], m["sites_reported"]), ({"guardian": 2}, True))   # scanned, not mapped: theirs

    def test_terraformable_as_spansh_spells_it_now(self):
        """Spansh's dumps say "Terraformable" (no longer "Candidate for terraforming"): priced as terraformable (a
        terraformable high metal content world was priced as a plain one, 59k, 2026-10-09)."""
        body = {"name": "Sys 2", "type": "Planet", "subType": "High metal content world", "earthMasses": 0.20102, "bodyId": 9}
        for state in ("Terraformable", "Candidate for terraforming"):
            r = ed_outrider.record_from_dump("Sys", dict(body, terraformingState=state))
            self.assertEqual((r["terraformable"], r["ed"]["TerraformState"]), (True, "Terraformable"), state)
        plain = ed_outrider.carto_values(ed_outrider.record_from_dump("Sys", dict(body, terraformingState="Not terraformable")),
                                         False, None, None, None)["left"]
        tf = ed_outrider.carto_values(ed_outrider.record_from_dump("Sys", dict(body, terraformingState="Terraformable")),
                                      False, None, None, None)["left"]
        self.assertLess(plain, 100000)
        self.assertGreater(tf, 5 * plain)

    def test_star_and_unpriceable(self):
        star = ed_outrider.record_from_dump("Sys", {"name": "Sys", "type": "Star", "subType": "Neutron Star", "solarMasses": 1.4})
        self.assertEqual(star["ed"]["StarType"], "N")
        self.assertGreater(ed_outrider.carto_values(star, False, None, None, None)["left"], 20000)
        odd = ed_outrider.record_from_dump("Sys", {"name": "Sys 2", "type": "Planet", "subType": "Icy body"})   # no mass
        self.assertIsNone(odd["ed"])


class DumpRetries(unittest.TestCase):
    """Batch 0.1: failed body-detail fetches are retried a few times, logged, then given up on."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db),
                                       types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_cap(self):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            for _ in range(ed_outrider.DUMP_MAX_TRIES):
                self.state.dump_failed(7, RuntimeError("boom"))
                if 7 in self.state.failed_dumps and self.state.dump_tries[7] < ed_outrider.DUMP_MAX_TRIES:
                    self.state.failed_dumps.discard(7)
        self.assertNotIn(7, self.state.failed_dumps)
        self.assertEqual(err.getvalue().count("RuntimeError"), 2)   # first failure and giving up, not every retry

    def test_failed_lookups_name_spansh(self):
        """The page labels a status by its words: "Spansh failed" when it names Spansh, else "server error". Failed
        body-detail lookups are Spansh's (review 2026-10-11)."""
        import asyncio, contextlib, io

        async def boom(*a):
            raise RuntimeError("dump endpoint down")
        self.state.spansh.full_records = boom
        self.state.bases[7] = ("spansh", {"records": [], "body_count": 1})
        self.state.failed_dumps = {7}
        self.state.schedule_retry = lambda: 60
        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(self.state.retry_dumps(None))
        self.assertIn("Spansh body lookups failed", self.state.status)

    def test_partial_while_details_pending(self):
        self.db.execute("INSERT INTO visits VALUES (7, 'Sys', 0, 0, 0, 't', 't', 1)")
        search_level = {"name": "Sys 1", "type": "Planet", "subtype": "Icy body", "full": False, "value": 1000,
                        "scan_value": 500}
        self.state.bases[7] = ("spansh", {"name": "Sys", "x": 0, "y": 0, "z": 0, "records": [search_level]})
        self.assertTrue(self.state.system_detail(7)["partial"])
        self.state.dump_tries[7] = ed_outrider.DUMP_MAX_TRIES     # given up: stop asking the page to poll
        self.assertFalse(self.state.system_detail(7)["partial"])


class FindSystem(unittest.TestCase):
    """P12: GET /api/find, a system by name. EDSM and Spansh's record by name are mocked (the Spansh object has no
    session: a real call fails)."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.sp = ed_outrider.Spansh(self.db)
        self.edsm = unittest.mock.AsyncMock(return_value=None)
        self.sp.edsm_system = self.edsm
        self.spansh = unittest.mock.AsyncMock(return_value=None)   # S48: Spansh's record by name, after EDSM
        self.sp.system_record = self.spansh
        self.state = ed_outrider.State(self.db, self.j, self.sp, 25)

    def find(self, name):
        import asyncio
        return asyncio.run(self.state.find_system(name))

    def test_resolution_order_and_case(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Here", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})
        self.db.execute("INSERT INTO bookmarks VALUES (5, 'Far Away', 30, 40, 0, '', 't')")
        self.sp.store(6, None, {"v": ed_outrider.CACHE_VERSION, "name": "Synuefe XR-H d11-102", "x": 3, "y": 4, "z": 0,
                                "records": [{"name": "Decoy", "type": "Planet"}]})
        self.sp.store(8, None, {"v": ed_outrider.CACHE_VERSION, "name": "Other", "x": 0, "y": 0, "z": 1,
                                "records": [{"name": "Decoy 100%", "type": "Planet"}]})
        self.db.execute("INSERT INTO route_systems VALUES (7, 'Far Away', 1, 1, 1, 'K', 't')")   # the bookmark wins
        self.db.execute("INSERT INTO route_systems VALUES (9, 'Route Only', 0, 6, 8, 'K', 't')")
        st, d = self.find("far away")
        self.assertEqual((st, d["id"], d["name"], d["source"], d["distance"], d["bookmarked"], d["visited"]),
                         (200, "5", "Far Away", "bookmark", 50.0, True, None))
        st, d = self.find("SYNUEFE xr-h D11-102")
        self.assertEqual((d["id"], d["source"], d["distance"], d["bookmarked"]), ("6", "spansh", 5.0, False))
        self.assertEqual(self.find("decoy")[0], 404)          # a body record's name is not a system
        self.assertEqual(self.find("Decoy 100%")[0], 404)     # LIKE wildcards are taken literally
        self.assertEqual(self.find("route only")[1]["source"], "route")
        st, d = self.find("here")
        self.assertEqual((d["id"], d["source"], d["visited"]["count"], d["next_stop"]), ("1", "visited", 1, False))
        self.state.set_next_stop(5)
        self.assertTrue(self.find("Far Away")[1]["next_stop"])
        # only the two names nobody here knows went on to (the mocked) EDSM
        self.assertEqual([c.args for c in self.edsm.await_args_list], [("decoy",), ("Decoy 100%",)])

    def test_edsm_hit_is_kept_for_after_a_restart(self):
        self.edsm.return_value = {"name": "Deep Space", "id64": 4242, "coords": {"x": 100, "y": 0, "z": 0},
                                  "primaryStar": {"type": "K (Yellow-Orange) Star", "isScoopable": True}}
        st, d = self.find("deep space")
        self.assertEqual((st, d["id"], d["name"], d["source"], d["distance"]), (200, "4242", "Deep Space", "edsm", None))
        self.edsm.assert_awaited_once_with("deep space")
        # a new State (a restart) finds it by id64: bookmark and next stop work
        state2 = ed_outrider.State(self.db, ed_outrider.Journals(self.db), self.sp, 25)
        self.assertEqual(state2.locate(4242), ("Deep Space", 100, 0, 0))
        self.assertTrue(state2.set_next_stop(4242))
        # the cached answer is stale on purpose: opening the system fetches Spansh's bodies at once
        self.assertGreater(self.sp.fetched_age(4242), ed_outrider.ON_DEMAND_MAX_AGE)
        self.assertEqual(self.find("Deep Space")[1]["source"], "spansh")   # now local
        self.assertEqual(self.edsm.await_count, 1)

    def test_unknown_and_failed(self):
        st, d = self.find("Nowhere")
        self.assertEqual(st, 404)
        self.assertIn("Nowhere", d["error"])
        self.edsm.return_value = {"name": "Vague", "id64": 3}      # EDSM knows it but has no coordinates
        self.assertEqual(self.find("Vague")[0], 404)
        self.edsm.side_effect = OSError("down")   # EDSM down: Spansh still answers (S48)
        self.assertEqual(self.find("Nowhere")[0], 404)
        self.spansh.side_effect = OSError("down")
        self.assertEqual(self.find("Nowhere")[0], 502)
        self.assertEqual(self.db.execute("SELECT count(*) FROM spansh_systems").fetchone()[0], 0)

    def test_spansh_when_edsm_fails(self):   # S48
        rec = {"name": "Fresh Spansh", "id64": 5151, "x": 10.0, "y": 0.0, "z": 0.0}
        # EDSM down: Spansh's record, cached stale like EDSM's (opening it fetches the bodies at once)
        self.edsm.side_effect = OSError("down")
        self.spansh.return_value = rec
        st, d = self.find("fresh spansh")
        self.assertEqual((st, d["id"], d["name"], d["source"]), (200, "5151", "Fresh Spansh", "spansh"))
        self.spansh.assert_awaited_once_with("fresh spansh")
        self.assertGreater(self.sp.fetched_age(5151), ed_outrider.ON_DEMAND_MAX_AGE)
        state2 = ed_outrider.State(self.db, ed_outrider.Journals(self.db), self.sp, 25)   # after a restart
        self.assertEqual(state2.locate(5151), ("Fresh Spansh", 10.0, 0.0, 0.0))
        self.assertTrue(state2.set_next_stop(5151))
        self.assertEqual(ed_outrider.cached_source(self.sp.cached(5151)[1]), "spansh")
        # EDSM answers but doesn't know it (or has no position): Spansh too
        self.edsm.side_effect = None
        self.edsm.return_value = None
        self.spansh.return_value = dict(rec, name="Other Spansh", id64=5152)
        self.assertEqual(self.find("Other Spansh")[1]["source"], "spansh")
        self.edsm.return_value = {"name": "Vague", "id64": 3}
        self.spansh.return_value = dict(rec, name="Vague", id64=3)
        self.assertEqual(self.find("Vague")[1]["id"], "3")
        # neither knows it; one of them failed; both failed
        self.edsm.return_value = None
        self.spansh.return_value = None
        st, d = self.find("Nowhere")
        self.assertEqual((st, d["error"]), (404, "No system called 'Nowhere' is known here, to EDSM or to Spansh."))
        self.spansh.side_effect = ed_outrider.HighwayError("Spansh cannot be reached (no network session)")
        self.assertIn("Spansh could not be reached", self.find("Nowhere")[1]["error"])
        self.edsm.side_effect = OSError("down")
        self.assertEqual(self.find("Nowhere")[0], 502)
        self.spansh.side_effect = None
        self.assertIn("EDSM could not be reached", self.find("Nowhere")[1]["error"])
        # EDSM knows the name but not where, and Spansh could not be asked: not "Spansh doesn't know it"
        self.edsm.side_effect = None
        self.edsm.return_value = {"name": "Vague Two", "id64": 4}
        self.spansh.side_effect = ed_outrider.HighwayError("Spansh cannot be reached (no network session)")
        self.assertEqual(self.find("Vague Two"), (502, {"error": "EDSM knows Vague Two but not where it is, and Spansh could not be reached; try again."}))
        self.spansh.side_effect = None
        self.edsm.return_value = None
        # a record without a position is no hit
        self.spansh.return_value = dict(rec, name="Nowhere", id64=77, x=None)
        self.assertEqual(self.find("Nowhere")[0], 404)
        self.assertIsNone(self.sp.cached(77)[1])

    def test_route(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                self.assertEqual((await c.get("/api/find", params={"name": "  "})).status, 400)
                self.assertEqual((await c.get("/api/find", params={"name": "x" * 101})).status, 400)
                r = await c.get("/api/find", params={"name": "  Nowhere   Here "})
                self.assertEqual(r.status, 404)
                # another site's no-cors fetch cannot make it look names up on EDSM
                r = await c.get("/api/find", params={"name": "a"}, headers={"Sec-Fetch-Site": "cross-site"})
                self.assertEqual(r.status, 403)
        asyncio.run(go())
        self.edsm.assert_awaited_once_with("Nowhere Here")   # whitespace tidied; the cross-site one never asked


class BatchFSpansh(unittest.TestCase):
    """Batch F: the pre-Odyssey mark (P16) and the firsts watch (P20). No network: Spansh is a fake."""

    # a thin-atmosphere rocky world as a 2019 client reported it: not landable, no signals block
    OLD = {"name": "Sys A 3", "type": "Planet", "subType": "Rocky body", "isLandable": False,
           "atmosphereType": "Thin Carbon dioxide", "surfacePressure": 0.02, "gravity": 0.12, "surfaceTemperature": 180,
           "volcanismType": "No volcanism", "distanceToArrival": 500, "bodyId": 3, "earthMasses": 0.01,
           "updateTime": "2019-06-01 10:00:00+00"}

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types_ns(cached=lambda i: (None, None)), 25)

    def rec(self, **kw):
        return ed_outrider.record_from_dump("Sys", dict(self.OLD, **kw))

    # ---- P16 ----

    def test_record_keeps_update_time_and_signals_block(self):
        self.assertEqual(ed_outrider.CACHE_VERSION, 20)   # 16: mining (Batch M4); 17: "Terraformable" priced; 18: spansh_old; 19: reserve; 20: sites
        r = self.rec()
        self.assertEqual((r["updated"], r["signals_known"]), ("2019-06-01 10:00:00+00", False))
        self.assertTrue(self.rec(signals={"signals": {}, "updateTime": "2019-06-01"})["signals_known"])

    def test_stale_bio_cases(self):
        self.assertTrue(ed_outrider.stale_bio_body(self.rec(), "K"))                             # the old one
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(signals={"signals": {}}), "K"))    # a signals block
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(updateTime="2023-01-05T10:00:00Z"), "K"))   # after the cutoff
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(updateTime="2022-11-29T00:00:00Z"), "K"))   # the day itself
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(isLandable=True), "K"))             # already landable
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(atmosphereType="Carbon dioxide"), "K"))   # not thin
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(atmosphereType=None), "K"))
        # the rules allow nothing on a 30 K neon world, however old the record
        self.assertFalse(ed_outrider.stale_bio_body(self.rec(atmosphereType="Thin Neon", surfaceTemperature=30, gravity=0.3), "K"))
        # your own scan replaces the Spansh record: no updated, never flagged
        own = dict(self.rec(), updated=None)
        own.pop("signals_known")
        self.assertFalse(ed_outrider.stale_bio_body(own, "K"))

    def test_bio_possible_signals_unknown(self):
        """Plugin gaps C (BioScan's "Bios possible, check FSS for signals"): a landable world you have only from an
        AutoScan or a nav beacon, with no signal count of yours or Spansh's, where the rules allow life."""
        ev = {"event": "Scan", "timestamp": "2026-01-01T00:00:00Z", "ScanType": "AutoScan", "BodyName": "Sys A 3", "BodyID": 3,
              "StarSystem": "Sys", "SystemAddress": 9, "PlanetClass": "Rocky body", "Landable": True,
              "AtmosphereType": "CarbonDioxide", "Atmosphere": "thin carbon dioxide atmosphere", "SurfacePressure": 2000.0,
              "SurfaceGravity": 0.12 * 9.80665, "SurfaceTemperature": 180, "Volcanism": "", "MassEM": 0.01,
              "DistanceFromArrivalLS": 500, "TerraformState": ""}
        r = ed_outrider.record_from_scan(ev)
        self.assertTrue(ed_outrider.unknown_bio_groups(r, "K"))
        self.assertEqual(ed_outrider.unknown_bio_groups(ed_outrider.record_from_scan(dict(ev, ScanType="Detailed")), "K"), [])   # FSS'd: its signals were said
        self.assertEqual(ed_outrider.unknown_bio_groups(dict(r, signals_seen=True), "K"), [])   # you counted them
        self.assertEqual(ed_outrider.unknown_bio_groups(dict(r, signals_known=True), "K"), [])  # someone did (Spansh)
        self.assertEqual(ed_outrider.unknown_bio_groups(dict(r, bio=2), "K"), [])               # known to have life
        self.assertEqual(ed_outrider.unknown_bio_groups(dict(r, landable=False), "K"), [])
        self.assertEqual(ed_outrider.summarise([r], 1, "K")["bio_unknown"], 1)
        # review: an FSS (Detailed) of a lifeless body said its signals; a later AutoScan replacing the row keeps that
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 9, "StarPos": [0, 0, 0]})
        j.handle(dict(ev, ScanType="Detailed", timestamp="2026-01-01T00:01:00Z"))
        j.handle(dict(ev, ScanType="AutoScan", timestamp="2026-01-02T00:01:00Z"))
        import json as _json
        rec = _json.loads(db.execute("SELECT record FROM own_bodies WHERE system=9").fetchone()[0])
        self.assertEqual((rec["scan_type"], ed_outrider.unknown_bio_groups(rec, "K")), ("Detailed", []))

    def test_why_genera_are_ruled_out(self):
        """Plugin gaps C (BioScan's elimination log): each genus not predicted, with the rule that came closest."""
        import outrider.bio
        if not outrider.bio.load_rules():
            self.skipTest("no bio_rules.json")
        ev = {"event": "Scan", "timestamp": "2026-01-01T00:00:00Z", "ScanType": "Detailed", "BodyName": "Sys A 3", "BodyID": 3,
              "StarSystem": "Sys", "SystemAddress": 9, "PlanetClass": "Rocky body", "Landable": True,
              "AtmosphereType": "CarbonDioxide", "Atmosphere": "thin carbon dioxide atmosphere", "SurfacePressure": 2000.0,
              "SurfaceGravity": 0.12 * 9.80665, "SurfaceTemperature": 180, "Volcanism": "", "MassEM": 0.01,
              "DistanceFromArrivalLS": 500, "TerraformState": ""}
        body = ed_outrider._bio_body(ed_outrider.record_from_scan(ev), "K", None)
        kept = {x["genus"] for x in outrider.bio.predict(body)}
        out = {x["genus"]: x["why"] for x in outrider.bio.ruled_out(body)}
        self.assertTrue(out and not kept & set(out))                     # each genus once: expected, or ruled out
        self.assertEqual((out["Cactoida"], out["Bark Mounds"]), ("pressure too low", "the volcanism"))
        self.assertEqual(outrider.bio.ruled_out({"PlanetClass": "Sudarsky class I gas giant"}), [])   # hosts nothing at all

    def test_summary_is_a_mark_and_values_are_unchanged(self):
        star = ed_outrider.record_from_dump("Sys", {"name": "Sys A", "type": "Star", "subType": "K (Yellow-Orange) Star",
                                                    "mainStar": True, "solarMasses": 0.8, "bodyId": 1,
                                                    "updateTime": "2019-06-01 10:00:00+00"})
        old, new = [star, self.rec()], [star, self.rec(updateTime="2023-01-05T10:00:00Z")]
        s_old, s_new = ed_outrider.summarise(old, 2, "K"), ed_outrider.summarise(new, 2, "K")
        self.assertEqual(s_old["stale_bio"]["bodies"], 1)
        self.assertEqual((s_old["stale_bio"]["reported"], s_old["stale_bio"]["names"]), ("2019-06-01", ["A 3"]))
        self.assertTrue(s_old["stale_bio"]["genera_top"])
        groups = ed_outrider.stale_bio_groups(self.rec(), "K")
        vals = sorted(g["value"] or 0 for g in groups)
        self.assertEqual(s_old["stale_bio"]["up_to"], vals[len(vals) // 2])   # one genus, the median, not the best
        self.assertIsNone(s_new["stale_bio"])
        self.assertEqual((s_old["bio_potential"], s_old["est_value"]), (s_new["bio_potential"], s_new["est_value"]))
        # system_value (Nearby's value columns) counts nothing for it
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 9,
                       "StarPos": [0, 0, 0]})
        self.assertEqual(self.state.system_value(9, "Sys", old, "K"), self.state.system_value(9, "Sys", new, "K"))

    def test_pre_odyssey_systems(self):
        """#11 (Kurbo26): a system whose Spansh records all predate the legacy split is "pre-Odyssey" (Nearby's pill, Here's
        header, the arrival briefing never routine, the overlay's strip), whatever its bodies; one newer record, not."""
        star = ed_outrider.record_from_dump("Sys", {"name": "Sys A", "type": "Star", "subType": "K (Yellow-Orange) Star",
                                                    "mainStar": True, "solarMasses": 0.8, "bodyId": 1,
                                                    "updateTime": "2019-02-11 10:00:00+00"})
        gas = self.rec(name="Sys A 5", bodyId=5, subType="Class I gas giant", atmosphereType=None, updateTime="2019-02-12 09:00:00+00")
        self.assertEqual((ed_outrider.spansh_date([star, gas]), ed_outrider.spansh_old([star, gas])), ("2019-02-12", "2019-02-12"))
        newer = self.rec(name="Sys A 6", bodyId=6, updateTime="2023-03-01T00:00:00Z")
        self.assertEqual((ed_outrider.spansh_date([star, newer]), ed_outrider.spansh_old([star, newer])), ("2023-03-01", None))
        self.assertEqual((ed_outrider.spansh_date([{"name": "mine"}]), ed_outrider.spansh_old([])), (None, None))   # your own scans: no date
        s = ed_outrider.summarise([star, gas], 2, "K")
        self.assertEqual((s["spansh_date"], s["spansh_old"], s["stale_bio"]), ("2019-02-12", "2019-02-12", None))   # no bio candidate: still old
        # Here and the arrival briefing
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 9,
                       "StarPos": [0, 0, 0]})
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 3, "records": [star, gas, self.rec()]}
        self.state.bases[9] = ("spansh", base)
        d = self.state.system_detail(9)
        self.assertEqual((d["spansh_date"], d["spansh_old"]), ("2019-06-01", "2019-06-01"))
        facts = self.state.arrival_facts(9)
        self.assertEqual((facts["spansh_old"], facts["old_bodies"]), ("2019-06-01", 1))
        base["records"].append(newer)
        self.assertEqual((self.state.system_detail(9)["spansh_old"], self.state.arrival_facts(9)["spansh_old"]), (None, None))
        # the overlay's system strip
        import outrider.overlay as O
        texts = lambda info: [r[0] for it in O.strip_panel(info, O.palette("elite"))["items"] for r in it.get("runs", [])]
        self.assertIn("Spansh ✓ (pre-Odyssey)", texts({"name": "Sys", "in_spansh": True, "spansh_old": "2019-06-01"}))
        self.assertIn("Spansh ✓", texts({"name": "Sys", "in_spansh": True, "spansh_old": None}))

    def test_here_and_left_behind_show_the_mark(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 9,
                       "StarPos": [0, 0, 0]})
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 2,
                "records": [self.rec(), self.rec(name="Sys A 4", bodyId=4, updateTime="2024-01-01T00:00:00Z")]}
        self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (9, 'u', ?, 0, 0, 0, 0)",
                        (json.dumps(base),))
        self.state.bases[9] = ("spansh", base)
        self.state.center = {"x": 0, "y": 0, "z": 0}
        bodies = {b["name"]: b for b in self.state.system_detail(9)["bodies"]}
        self.assertTrue(bodies["A 3"]["stale_bio"])
        self.assertFalse(bodies["A 4"]["stale_bio"])
        self.assertEqual(self.state.row(9)["stale_bio"]["bodies"], 1)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T01:00:00Z", "StarSystem": "Far", "SystemAddress": 10,
                       "StarPos": [20, 0, 0]})
        left = {r["id"]: r for r in self.state.left_behind(100)["systems"]}
        self.assertEqual(left["9"]["old_data"]["bodies"], 1)
        # scanned yourself: the Spansh record is replaced, and the mark goes
        ev = scan("2026-01-01T01:10:00Z", "Sys", 9, 3, "Sys A 3", disc=True)[2]
        self.j.handle(dict(ev, event="Scan", StarSystem="Sys"))
        self.db.commit()
        self.state.scan_version += 1
        self.state.left_seq += 1   # as apply_own_changes does for a scan elsewhere than where you are (S2-S1)
        left = {r["id"]: r for r in self.state.left_behind(100)["systems"]}
        self.assertIsNone((left.get("9") or {}).get("old_data"))

    # ---- P20 ----

    # a fixture dump in Spansh's layout: your three discoveries (A, A 1 and A 2), one body you never scanned
    def dump(self, a1_time, a2_time="2026-01-01T00:02:00Z", extra=None):
        bodies = [{"name": "Sys A", "type": "Star", "subType": "K (Yellow-Orange) Star", "bodyId": 1,
                   "updateTime": "2026-01-01T00:00:10Z"},
                  {"name": "Sys A 1", "type": "Planet", "subType": "Icy body", "bodyId": 2, "updateTime": a1_time},
                  {"name": "Sys A 2", "type": "Planet", "subType": "Icy body", "bodyId": 3, "updateTime": a2_time},
                  {"name": "Sys A belt cluster", "type": "Barycentre", "updateTime": "2026-02-01T00:00:00Z"}]
        return {"system": {"name": "Sys", "id64": 9, "bodyCount": 4, "date": "2026-02-01T00:00:00Z",
                           "bodies": bodies + (extra or [])}}

    def records(self, d):
        return [ed_outrider.record_from_dump("Sys", b) for b in d["system"]["bodies"] if b["type"] in ("Star", "Planet")]

    MINE = {"A": ["2026-01-01T00:00:10Z"], "A 1": ["2026-01-01T00:01:00Z", "2026-01-01T00:05:00Z"],
            "A 2": ["2026-01-01T00:02:00Z"]}

    def test_own_uploads_are_not_someone_else(self):
        # EDDN stamps an upload with the journal's time: every update matches one of your own scans or the map
        self.assertIsNone(ed_outrider.firsts_reported(self.records(self.dump("2026-01-01T00:05:00Z")), self.MINE, 4))
        self.assertIsNone(ed_outrider.firsts_reported(self.records(self.dump("2026-01-01T00:06:30Z")), self.MINE, 4))   # grace

    def test_someone_else_later(self):
        d = self.dump("2026-01-09T12:00:00Z", "2026-01-08T00:00:00Z",
                      extra=[{"name": "Sys B", "type": "Star", "subType": "M (Red dwarf) Star", "bodyId": 5,
                              "updateTime": "2026-01-07T00:00:00Z"}])   # a body you never discovered: not counted
        got = ed_outrider.firsts_reported(self.records(d), self.MINE, 4)
        self.assertEqual(got, {"reported_ts": "2026-01-08T00:00:00Z", "bodies": 2, "spansh_bodies": 4, "body_count": 4})
        # Spansh's other time format reads the same
        d2 = self.dump("2026-01-09 12:00:00+00")
        self.assertEqual(ed_outrider.firsts_reported(self.records(d2), self.MINE, None)["reported_ts"], "2026-01-09T12:00:00Z")

    def test_snapshot_and_unknown_times_do_not_count(self):
        # updated before your scan: in the snapshot when you arrived; no time at all: cannot tell
        self.assertIsNone(ed_outrider.firsts_reported(self.records(self.dump("2025-12-01T00:00:00Z")), self.MINE, 4))
        d = self.dump(None)
        self.assertIsNone(ed_outrider.firsts_reported(self.records(d), self.MINE, 4))
        self.assertIsNone(ed_outrider.firsts_reported([], self.MINE, 4))   # Spansh has nothing: nobody reported

    def discover(self, id64, name, t0, x=0):
        self.j.handle({"event": "FSDJump", "timestamp": t0, "StarSystem": name, "SystemAddress": id64, "StarPos": [x, 0, 0]})
        self.j.handle(scan(t0[:-3] + "10Z", name, id64, 1, f"{name} A", star=True)[2])
        self.j.handle(scan(t0[:-6] + "01:00Z", name, id64, 2, f"{name} A 1")[2])
        self.j.handle(scan(t0[:-6] + "02:00Z", name, id64, 3, f"{name} A 2")[2])
        self.db.commit()

    def fake(self, dumps):
        calls = []

        class FakeSpansh(ed_outrider.Spansh):
            async def lookup(self, id64, interactive=True):
                calls.append((id64, interactive))
                return dumps.get(id64)
        return FakeSpansh(self.db), calls

    def test_watch_step_most_valuable_first_once_a_day(self):
        import asyncio
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        self.discover(8, "Cheap", "2026-01-02T00:00:00Z", x=5)
        self.state.system_values = {"Sys": 5_000_000, "Cheap": 100}
        cheap = self.dump("2026-01-02T00:01:00Z", "2026-01-02T00:02:00Z")
        for b in cheap["system"]["bodies"]:
            b["name"] = b["name"].replace("Sys", "Cheap")
        sp, calls = self.fake({9: self.dump("2026-01-09T12:00:00Z"), 8: cheap})
        self.state.spansh = sp
        now = ed_outrider.ts_seconds("2026-01-10T00:00:00Z")
        got = asyncio.run(self.state.firsts_watch_step(now))
        self.assertEqual(calls, [(9, False)])                  # the valuable one first, on the bulk lane
        self.assertEqual(got["reported_ts"], "2026-01-09T12:00:00Z")
        self.assertIsNone(asyncio.run(self.state.firsts_watch_step(now + 20)))   # Cheap: your own upload
        self.assertEqual(calls, [(9, False), (8, False)])
        self.assertIsNone(asyncio.run(self.state.firsts_watch_step(now + 40)))   # nothing due until tomorrow
        self.assertEqual(len(calls), 2)
        self.assertIsNone(self.db.execute("SELECT * FROM spansh_systems").fetchone())   # never cached: not stored
        seen = {x["name"]: x["seen"] for x in self.state.firsts_list()}
        self.assertEqual(seen["Sys"], {"reported_ts": "2026-01-09T12:00:00Z", "days": 8, "bodies": 1,
                                       "spansh_bodies": 3, "body_count": 4})
        self.assertIsNone(seen["Cheap"])
        # the watch is off here, but what it found still counts on the Unsold tile
        self.assertEqual(self.state.firsts_watch_info(), {"on": False, "seen": 1, "checked": 2, "of": 2})

    def test_watch_info_and_reports_stay(self):
        import asyncio
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        self.state.system_values = {"Sys": 5_000_000}
        self.state.firsts_watch_on = True
        self.assertEqual(self.state.firsts_watch_info(), {"on": True, "seen": 0, "checked": 0, "of": 1})
        sp, calls = self.fake({9: self.dump("2026-01-09T12:00:00Z")})
        self.state.spansh = sp
        now = ed_outrider.ts_seconds("2026-01-10T00:00:00Z")
        asyncio.run(self.state.firsts_watch_step(now))
        self.assertEqual(self.state.firsts_watch_info(), {"on": True, "seen": 1, "checked": 1, "of": 1})
        self.assertEqual(self.state.payload()["firsts_watch"]["seen"], 1)
        # seen by others: not due again for a week; then Spansh answers without it (a glitch): the first sighting stays
        sp2, calls2 = self.fake({9: None})
        self.state.spansh = sp2
        self.assertIsNone(asyncio.run(self.state.firsts_watch_step(now + 86400)))
        self.assertEqual(calls2, [])
        later = now + ed_outrider.FIRSTS_WATCH_SLOW
        asyncio.run(self.state.firsts_watch_step(later))
        row = self.db.execute("SELECT * FROM firsts_watch WHERE id64=9").fetchone()
        self.assertEqual((row["reported_ts"], row["checked_ts"]), ("2026-01-09T12:00:00Z", later))
        self.state.firsts_watch_on = False
        self.assertEqual(self.state.firsts_watch_info()["seen"], 1)   # off: what was found still shows

    def test_first_sighting_is_a_moment_spoken_at_most_every_half_hour(self):
        """S6: someone else's scans first seen in a system of yours: a firsts_seen moment (once per system: a report never
        goes away), its facts as timestamps; the spoken line at most once in FIRSTS_SEEN_SAY_S, "so far today" counted."""
        import asyncio
        for i, (id64, name) in enumerate(((9, "Sys"), (8, "Two"), (7, "Three"))):
            self.discover(id64, name, "2026-01-01T00:00:00Z", x=i * 5)
        self.state.system_values = {"Sys": 14_200_000, "Two": 3_000_000, "Three": 1_000_000}
        dumps = {}
        for id64, name in ((9, "Sys"), (8, "Two"), (7, "Three")):
            d = self.dump("2026-01-09T12:00:00Z")
            for b in d["system"]["bodies"]:
                b["name"] = b["name"].replace("Sys", name)
            dumps[id64] = d
        sp, _ = self.fake(dumps)
        self.state.spansh = sp
        now = ed_outrider.ts_seconds("2026-01-10T00:00:00Z")
        seq = self.j.moment_seq
        asyncio.run(self.state.firsts_watch_step(now))
        [m] = [x for x in self.j.moments if x["seq"] > seq]
        self.assertEqual({k: m[k] for k in ("kind", "system", "id64", "bodies", "first_ts", "reported_ts", "value", "today", "speak")},
                         {"kind": "firsts_seen", "system": "Sys", "id64": "9", "bodies": 1, "first_ts": "2026-01-01T00:00:10Z",
                          "reported_ts": "2026-01-09T12:00:00Z", "value": 14_200_000, "today": 1, "speak": True})
        asyncio.run(self.state.firsts_watch_step(now + 20))                      # the next one within half an hour
        m2 = self.j.moments[-1]
        self.assertEqual((m2["system"], m2["today"], m2["speak"]), ("Two", 2, False))   # a card, not said again
        # the same system checked again (a week on) is no new sighting
        seq = self.j.moment_seq
        self.db.execute("UPDATE firsts_watch SET checked_ts = 0 WHERE id64 = 9")
        asyncio.run(self.state.firsts_watch_step(now + ed_outrider.FIRSTS_SEEN_SAY_S + 30))
        new = [x for x in self.j.moments if x["seq"] > seq]
        self.assertEqual([(x["system"], x["speak"]) for x in new], [("Three", True)])   # half an hour on: said again
        asyncio.run(self.state.firsts_watch_step(now + ed_outrider.FIRSTS_SEEN_SAY_S + 60))
        self.assertEqual([x["system"] for x in self.j.moments if x["seq"] > seq], ["Three"])

    def test_watch_gap_slows_for_old_or_seen_firsts(self):
        gap, day = ed_outrider.firsts_watch_gap, 86400
        t0 = ed_outrider.ts_seconds("2026-01-01T00:00:10Z")
        row = {"first_ts": "2026-01-01T00:00:10Z", "reported_ts": None}
        self.assertEqual(gap(row, t0 + 10 * day), ed_outrider.FIRSTS_WATCH_EVERY)           # young: daily
        self.assertEqual(gap(row, t0 + 31 * day), ed_outrider.FIRSTS_WATCH_SLOW)            # a month on: weekly
        self.assertEqual(gap(dict(row, reported_ts="2026-01-02T00:00:00Z"), t0 + day), ed_outrider.FIRSTS_WATCH_SLOW)
        self.assertEqual(gap({"first_ts": None, "reported_ts": None}, t0), ed_outrider.FIRSTS_WATCH_EVERY)

    def test_watch_daily_cap(self):
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        self.state.system_values = {"Sys": 5_000_000}
        now = ed_outrider.ts_seconds("2026-01-10T00:00:00Z")
        self.assertEqual(self.state.firsts_watch_due(now), (9, "Sys"))
        cap = ed_outrider.FIRSTS_WATCH_DAY_CAP
        self.db.executemany("INSERT INTO firsts_watch VALUES (?, ?, NULL, 0, 0, 0, NULL)",
                            [(1000 + i, now - 3600) for i in range(cap)])   # other systems checked in the last hour
        self.assertIsNone(self.state.firsts_watch_due(now))                  # the day's checks are used up
        self.assertEqual(self.state.firsts_watch_due(now + 86400), (9, "Sys"))   # a day on they have aged out

    def test_watch_uses_a_fresh_cache_and_refreshes_a_stale_one(self):
        import asyncio
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        sp, calls = self.fake({9: self.dump("2026-01-09T12:00:00Z")})
        self.state.spansh = sp
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 4,
                "records": self.records(self.dump("2026-01-01T00:01:00Z"))}
        sp.store(9, "u1", base)   # fetched just now, with your own upload only
        got = asyncio.run(self.state.firsts_watch_step())
        self.assertIsNone(got)
        self.assertEqual(calls, [])                              # no request: the cache is under a day old
        self.db.execute("UPDATE spansh_systems SET fetched_ts = ?", (time.time() - 2 * 86400,))
        self.db.execute("UPDATE firsts_watch SET checked_ts = 0")
        got = asyncio.run(self.state.firsts_watch_step())
        self.assertEqual(calls, [(9, False)])
        self.assertEqual(got["bodies"], 1)
        self.assertEqual(sp.cached(9)[1]["records"][1]["updated"], "2026-01-09T12:00:00Z")   # Nearby's cache refreshed too

    def test_watch_table_survives_a_journal_reread_and_goes_in_the_backup(self):
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.sqlite")
            db = ed_outrider.open_db(path)
            db.execute("INSERT INTO firsts_watch VALUES (9, 1.5, '2026-01-09T12:00:00Z', 2, 3, 4, '2026-01-01T00:00:10Z')")
            db.commit(); db.close()
            db = ed_outrider.open_db(path, rescan=True)   # the journal re-read (also what a PARSER_VERSION bump does)
            try:
                self.assertEqual(tuple(db.execute("SELECT * FROM firsts_watch").fetchone()),
                                 (9, 1.5, "2026-01-09T12:00:00Z", 2, 3, 4, "2026-01-01T00:00:10Z"))
                self.assertNotIn("firsts_watch", ed_outrider.RESET_JOURNAL_DATA)
                state = ed_outrider.State(db, ed_outrider.Journals(db), types_ns(cached=lambda i: (None, None)), 25)
                state.db_path = path
                out = os.path.join(d, "backups")
                with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                        unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
                    res = state.make_backup()
                with zipfile.ZipFile(res["path"]) as z:
                    z.extract("w.sqlite", os.path.join(d, "x"))
                copy = sqlite3.connect(os.path.join(d, "x", "w.sqlite"))
                self.assertEqual(copy.execute("SELECT reported_ts FROM firsts_watch").fetchone()[0], "2026-01-09T12:00:00Z")
                copy.close()
            finally:
                db.close()

    def test_config_switch(self):
        import tomllib
        st = ed_outrider.settings_from({}, argparse.Namespace(journals=None, legacy=None, host=None, port=None,
                                                               radius=None, db=None))
        self.assertIs(st["watch_firsts"], True)
        st = ed_outrider.settings_from({"spansh": {"watch_firsts": False}},
                                       argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None))
        self.assertIs(st["watch_firsts"], False)
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["spansh"]["watch_firsts"], False)
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ed_outrider.toml.example")) as f:
            self.assertIn("watch_firsts", f.read())

    def test_your_own_later_visit_is_not_someone_else(self):
        # found on the real journals: a jump back in two days later updated the arrival star on Spansh (EDDN)
        d = self.dump("2026-01-01T00:01:00Z")
        d["system"]["bodies"][0]["updateTime"] = "2026-01-03T03:09:50Z"
        self.assertIsNone(ed_outrider.firsts_reported(self.records(d), self.MINE, 4, ["2026-01-03T03:09:50Z"]))
        self.assertEqual(ed_outrider.firsts_reported(self.records(d), self.MINE, 4, ["2026-01-02T00:00:00Z"])["bodies"], 1)
        # and the watch passes your arrivals in: a revisit leaves the system unflagged
        import asyncio
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-02T00:00:00Z", "StarSystem": "Elsewhere", "SystemAddress": 7,
                       "StarPos": [9, 0, 0]})
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-03T03:09:50Z", "StarSystem": "Sys", "SystemAddress": 9,
                       "StarPos": [0, 0, 0]})
        self.db.commit()
        sp, calls = self.fake({9: d})
        self.state.spansh = sp
        self.assertIsNone(asyncio.run(self.state.firsts_watch_step(ed_outrider.ts_seconds("2026-01-10T00:00:00Z"))))
        self.assertEqual(calls, [(9, False)])


class ReviewBatchE(unittest.TestCase):
    """Review 2026-10-01, Batch E: the firsts watch's rotation, failures and map-only systems (R8, R25, R26), the
    Materials sources cache (R19), the cross-site GET guard (R20), a bad port (R22), bad ids (R23), auto honk's
    fire-group learning (R24, unit only: a fake honker, no device), per-species bio sales (X1) and nav-beacon scans
    in own_firsts (X2). No network: Spansh is a fake."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types_ns(cached=lambda i: (None, None)), 25)

    def discover(self, id64, name, t0, x=0):
        self.j.handle({"event": "FSDJump", "timestamp": t0, "StarSystem": name, "SystemAddress": id64, "StarPos": [x, 0, 0]})
        self.j.handle(scan(t0[:-3] + "10Z", name, id64, 1, f"{name} A", star=True)[2])
        self.j.handle(scan(t0[:-6] + "01:00Z", name, id64, 2, f"{name} A 1")[2])
        self.db.commit()

    def fake(self, fail=()):
        calls = []

        class FakeSpansh(ed_outrider.Spansh):
            async def lookup(self, id64, interactive=True):
                calls.append(id64)
                if id64 in fail:
                    raise RuntimeError("Spansh answered 500")
                return None
        return FakeSpansh(self.db), calls

    # ---- R8: the watch goes round every system, within the daily cap ----
    def test_watch_rotates_past_the_top_150(self):
        rows, now0 = {}, 1_790_000_000
        first = ed_outrider.iso_ts(now0 - 86400)   # your first scans there: yesterday (daily checks for a month)
        unsold = [{"id": str(i), "name": f"S{i}", "state": "unsold", "bodies_by": {"sold": 0, "unsold": 1, "lost": 0}}
                  for i in range(400)]   # most valuable first
        self.state.firsts_watch_rows = lambda: rows
        self.state.firsts_cached = lambda: unsold
        checks, t = [], now0
        while t < now0 + 3 * 86400:
            due = self.state.firsts_watch_due(t)
            if due:
                rows[due[0]] = {"id64": due[0], "checked_ts": t, "reported_ts": None, "first_ts": first}
                checks.append((t, due[0]))
            t += 120
        self.assertEqual(len({i for _, i in checks}), 400)   # before: the same top 150 every day, the rest never
        self.assertEqual(checks[0][1], 0)                     # the most valuable first
        for k, (t, _) in enumerate(checks):                   # at most FIRSTS_WATCH_DAY_CAP in any 24 h
            self.assertLessEqual(sum(1 for u, _ in checks[k:] if u - t < 86400), ed_outrider.FIRSTS_WATCH_DAY_CAP)
        last = {}
        for t, i in checks:                                   # and no system more than once a day
            self.assertGreaterEqual(t - last.get(i, -1e18), 86400)
            last[i] = t

    # ---- R25: one failing system does not hold up the rest ----
    def test_a_failing_system_is_skipped_for_a_day(self):
        import asyncio
        self.discover(9, "Sys", "2026-01-01T00:00:00Z")
        self.discover(8, "Cheap", "2026-01-02T00:00:00Z", x=5)
        self.state.system_values = {"Sys": 5_000_000, "Cheap": 100}
        self.state.spansh, calls = self.fake(fail={9})
        now = ed_outrider.ts_seconds("2026-01-10T00:00:00Z")

        def step(t):
            try:
                return asyncio.run(self.state.firsts_watch_step(t))
            except RuntimeError:
                return "failed"
        self.assertEqual(step(now), "failed")
        self.assertIsNone(step(now + 620))                    # after the loop's backoff: the next system, not 9 again
        self.assertEqual(calls, [9, 8])
        self.assertIsNone(step(now + 1240))                   # nothing due: 9 waits a day, 8 was checked
        self.assertEqual(calls, [9, 8])
        self.assertEqual(step(now + 86400 + 10), "failed")    # a day on, 9 is tried again
        self.assertEqual(calls, [9, 8, 9])
        # a failed check counts against the daily cap like any other request
        self.state.firsts_watch_failed = {9: now}
        self.db.execute("DELETE FROM firsts_watch")
        with unittest.mock.patch.object(ed_outrider, "FIRSTS_WATCH_DAY_CAP", 1):
            self.assertIsNone(self.state.firsts_watch_due(now + 10))

    # ---- R26: a system whose only firsts are first-mapped bodies is not watched ----
    def test_map_only_systems_are_not_watched(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Mapd", "SystemAddress": 7,
                       "StarPos": [0, 0, 0]})
        self.j.handle(scan("2026-01-01T00:01:00Z", "Mapd", 7, 2, "Mapd A 1", disc=True)[2])   # discovered by someone else
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:05:00Z", "SystemAddress": 7, "BodyID": 2,
                       "BodyName": "Mapd A 1", "ProbesUsed": 4, "EfficiencyTarget": 6})           # ...but mapped first by you
        self.db.commit()
        self.state.firsts_watch_on = True
        self.assertEqual([(x["name"], x["state"]) for x in self.state.firsts_list()], [("Mapd", "unsold")])   # still listed
        now = ed_outrider.ts_seconds("2026-03-01T00:00:00Z")
        self.assertIsNone(self.state.firsts_watch_due(now))   # before: due every day, forever, finding nothing
        self.assertEqual(self.state.firsts_watch_info(), {"on": True, "seen": 0, "checked": 0, "of": 0})
        self.discover(9, "Sys", "2026-01-01T01:00:00Z", x=3)
        self.state._firsts_cache = None   # (the server's unsold estimate moves on after a scan)
        self.assertEqual(self.state.firsts_watch_due(now), (9, "Sys"))
        self.assertEqual(self.state.firsts_watch_info()["of"], 1)

    # ---- R19: the Materials sources are not rebuilt from every body on each scan ----
    def test_material_sources_only_read_new_rows(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

        def body(bid, mats=True, ts="2026-01-01T00:01:00Z"):
            ev = scan(ts, "Sys", 1, bid, f"Sys {bid}")[2]
            ev["Landable"] = True
            if mats:
                ev["Materials"] = [{"Name": "polonium", "Percent": 1.0 + bid / 100}, {"Name": "iron", "Percent": 20.0}]
            self.j.handle(ev)
        for bid in range(1, 31):
            body(bid)
        self.db.commit()
        got = self.state.material_sources(per=100)
        self.assertEqual(len(got["polonium"]), 30)
        body(31)
        self.state.scan_version += 1
        with unittest.mock.patch.object(ed_outrider.json, "loads", wraps=json.loads) as loads:
            got = self.state.material_sources(per=100)
        self.assertEqual(loads.call_count, 1)                 # the new body only (before: all 31 again)
        self.assertEqual(len(got["polonium"]), 31)
        body(5, mats=False, ts="2026-01-01T00:02:00Z")         # a rescan without materials drops the body
        self.assertEqual({b["body"] for b in self.state.material_sources(per=100)["polonium"]} & {"5"}, set())
        self.db.execute("DELETE FROM own_bodies")              # a journal re-read empties the table...
        body(40)
        self.assertEqual([b["body"] for b in self.state.material_sources(per=100)["polonium"]], ["40"])   # ...rebuilt

    # ---- R20: another site's reads are refused, except the overlays' status ----
    def test_cross_site_reads_refused(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        guard = guard_status
        for path in ("/api/log", "/api/history", "/api/map", "/api/materials", "/api/export", "/api/system/1",
                     "/api/firsts", "/api/organics", "/api/search", "/api/speech", "/api/defaults"):
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path=path), 403, path)
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="same-site", path=path), 403, path)
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="same-origin", path=path), 200, path)   # the page
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="none", path=path), 200, path)   # typed in
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", path=path), 200, path)                # curl
        for path in ("/api/status", "/api/status.txt", "/", "/static/page.js"):
            self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path=path), 200, path)

        async def go():   # the real app: the History sums never run for another site
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                with unittest.mock.patch.object(self.state, "history", side_effect=AssertionError("ran")) as h:
                    r1 = await c.get("/api/history", headers={"Sec-Fetch-Site": "cross-site"})
                    called = h.called
                r2 = await c.get("/api/status.txt", headers={"Sec-Fetch-Site": "cross-site"})
                # an overlay's page on another origin may read these two (F6); nothing else says so
                acao = {}
                for path in ("/api/status", "/api/status.txt", "/api/nearby", "/api/speech"):
                    r = await c.get(path, headers={"Origin": "http://overlay.local"} if path.startswith("/api/status") else {})
                    acao[path] = (r.status, r.headers.get("Access-Control-Allow-Origin"))
                # S20: the long poll's payload is gzipped for a browser that takes it, and plain for one that does not
                r = await c.get("/api/nearby", headers={"Accept-Encoding": "gzip, deflate, br"})
                acao["gzip"] = (r.status, r.headers.get("Content-Encoding"), "version" in await r.json())
                r = await c.get("/api/nearby", headers={"Accept-Encoding": "identity"}, auto_decompress=False)
                acao["plain"] = r.headers.get("Content-Encoding")
                return r1.status, called, r2.status, acao
        self.assertEqual(asyncio.run(go()), (403, False, 200, {"/api/status": (200, "*"), "/api/status.txt": (200, "*"),
                                                               "/api/nearby": (200, None), "/api/speech": (200, None),
                                                               "gzip": (200, "gzip", True), "plain": None}))

    # ---- R22: a port out of range is reported, not a traceback ----
    def test_bad_port_is_reported(self):
        import contextlib
        import io
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        for bad in (70000, -1, 0, True, 80.5, "http"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                st = ed_outrider.settings_from({"server": {"port": bad}}, args, None, ([], []))
            self.assertEqual(st["port"], 8025, bad)
            self.assertIn("[server] port", err.getvalue())
        self.assertEqual(ed_outrider.settings_from({"server": {"port": 9000}}, args, None, ([], []))["port"], 9000)
        self.assertEqual(ed_outrider.settings_from({"server": {"port": 65535}}, args, None, ([], []))["port"], 65535)
        for bad in ("70000", "-1", "x"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                ed_outrider.main(["--port", bad])   # argparse stops before anything starts
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("not a port from 1 to 65535", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    # ---- R23: bad ids are a 400 ----
    def test_bad_ids_are_400(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                post = lambda path, data: c.post(path, data=data, headers={"Content-Type": "application/json"})
                for data in ('{"id": 99999999999999999999999}', '{"id": -1}', '{"id": 1e400}', '{"id": true}'):
                    out.append((await post("/api/rigs/remove", data)).status)
                out.append((await post("/api/rigs/remove", '{"id": 5}')).status)   # well formed: no such rig
                for data in ('{"system": 1, "body": 1e400}', '{"system": 1, "body": 99999999999999999999999}',
                             '{"system": 1, "body": true}', '{"system": 1, "body": 2.5}', '{"system": 1e400, "body": 1}'):
                    out.append((await post("/api/sites/forget", data)).status)
                out.append((await post("/api/sites/forget", '{"system": "1", "body": 1}')).status)
            return out
        self.assertEqual(asyncio.run(go()), [400, 400, 400, 400, 404, 400, 400, 400, 400, 400, 200])

    # ---- R24: one miss while the game may not have had the keys does not lock a group out ----
    def test_one_honk_miss_keeps_the_group(self):
        live = {"live": True, "ts": ed_outrider.iso_ts(time.time()), "flags": ed_outrider.FLAG_HUD_ANALYSIS,
                "gui_focus": 0, "fire_group": 0}
        rec = ed_outrider.honk_learn(None, "A", False)   # a new ship, one miss in A (an alt-tab, say)
        self.assertEqual(ed_outrider.honk_decision(live, time.time(), rec), ("press", None))   # still pressed
        rec = ed_outrider.honk_learn(rec, "A", False)
        self.assertEqual(ed_outrider.honk_decision(live, time.time(), rec),
                         ("wait", "fire group A selected; honks missed there before"))

    # ---- X1: a Vista Genomics sale takes one run per BioData entry of its species ----
    SP1, SP2 = "$Codex_Ent_Bacterial_01;", "$Codex_Ent_Bacterial_02;"

    def two_runs(self):
        s = scan("2026-01-01T00:00:00Z", "Sys", 1, 5, "Sys 5")[2]
        s["WasFootfalled"] = False
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})
        self.j.handle(s)
        for m, sp in ((1, "Bacterial_01"), (2, "Bacterial_02")):
            for i, k in enumerate(("Log", "Sample", "Analyse")):
                self.j.handle(org(f"2026-01-01T0{m}:0{i}:00Z", 1, 5, sp, k))
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T03:00:00Z",
                       "BioData": [{"Species": self.SP1, "Value": 100, "Bonus": 400}]})   # sells one species only

    def test_partial_bio_sale_keeps_the_rest_aboard(self):
        self.two_runs()
        by = {(r["ts"][11:13]): r for r in self.state.organics(36500)["rows"]}
        self.assertEqual((by["01"]["state"], by["01"]["sold_ts"]), ("sold", "2026-01-01T03:00:00Z"))
        self.assertEqual((by["02"]["state"], by["02"]["sold_ts"]), ("aboard", None))   # before: sold with the first
        self.assertEqual(ed_outrider.organic_state(self.db, by["02"]["ts"], (1, 5, self.SP2)), "aboard")
        # a later sale (hours on: another visit) finds the run left aboard in its x5 pool
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-02T00:00:00Z",
                       "BioData": [{"Species": self.SP2, "Value": 100, "Bonus": 400}]})
        check = json.loads(self.db.execute("SELECT x5_check FROM sale_events WHERE kind='bio' ORDER BY ts DESC").fetchone()[0])
        self.assertEqual({k: check[k] for k in ("sold", "predicted", "matched")}, {"sold": 1, "predicted": 1, "matched": 1})
        out = self.state.organics(36500)
        by = {(r["ts"][11:13]): r for r in out["rows"]}
        self.assertEqual((by["02"]["state"], by["02"]["sold_ts"]), ("sold", "2026-01-02T00:00:00Z"))
        # S9-S5: what each sold run was paid (Value + Bonus), and the sold total from those figures
        self.assertEqual((by["01"]["paid"], by["02"]["paid"]), (500, 500))
        self.assertEqual((out["totals"]["sold"], out["sold_estimated"]), (1000, False))
        # the sale keeps its species through a journal re-read (PARSER_VERSION 34), with what each paid (53)
        self.assertEqual(json.loads(self.db.execute("SELECT bio_data FROM bio_sales ORDER BY ts").fetchone()[0]),
                         [[self.SP1.lower(), True, 100, 400, None]])
        # a row from before 53 ([species, bonus] only) still reads: the run it sold stays sold
        self.db.execute("UPDATE bio_sales SET bio_data = ? WHERE ts = '2026-01-01T03:00:00Z'", (json.dumps([[self.SP1.lower(), True]]),))
        self.assertEqual(ed_outrider.organic_replay(self.db)[0][(1, 5, self.SP1)][0], "sold")
        out = self.state.organics(36500)   # its run keeps the estimate, and the total says so
        by = {(r["ts"][11:13]): r for r in out["rows"]}
        self.assertEqual((by["01"]["paid"], by["02"]["paid"], out["sold_estimated"]), (None, 500, True))

    def test_run_left_aboard_dies_with_you(self):
        self.two_runs()
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T04:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T04:00:01Z", "Option": "recover"})
        by = {(r["ts"][11:13]): r["state"] for r in self.state.organics(36500)["rows"]}
        self.assertEqual(by, {"01": "sold", "02": "lost"})
        losses = self.state.ship_losses()
        self.assertEqual([(l["ts"][11:13], l["bio_runs"]) for l in losses], [("04", 1)])   # before: nothing lost

    # ---- X2: a nav-beacon scan is no first discovery ----
    def test_nav_beacon_scans_make_no_firsts(self):
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 34)   # bumped for it (35: fleet_loadouts)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Old", "SystemAddress": 3,
                       "StarPos": [0, 0, 0]})
        for kind in ("NavBeaconDetail", "NavBeacon"):
            ev = scan("2026-01-01T00:01:00Z", "Old", 3, 4 if kind == "NavBeacon" else 2, f"Old A {kind}")[2]
            ev["ScanType"] = kind   # a beacon in a long-surveyed system can say WasDiscovered false
            self.j.handle(ev)
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT count(*) FROM own_firsts").fetchone()[0], 0)
        self.assertEqual(self.state.firsts_list(), [])
        self.assertEqual(self.db.execute("SELECT count(*) FROM own_bodies").fetchone()[0], 2)   # the bodies still show
        self.j.handle(scan("2026-01-01T00:02:00Z", "Old", 3, 2, "Old A NavBeaconDetail")[2])     # your own scan counts
        self.assertEqual(self.db.execute("SELECT count(*) FROM own_firsts").fetchone()[0], 1)


class TargetCounts(unittest.TestCase):
    """Plugin gaps E (SystemStatusOverlay): the targeted system's known bodies of its count, and EDSM's beside Spansh."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types_ns(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Here", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})
        test = self

        class Fake:
            edsm_calls = []

            async def lookup(self, id64):
                return {"system": {"bodyCount": 12, "bodies": [{"type": "Star"}, {"type": "Planet"}, {"type": "Planet"},
                                                               {"type": "Barycentre"}]}}

            async def edsm_bodies(self, name):
                Fake.edsm_calls.append(name)
                if test.edsm_error:
                    raise ed_outrider.ClientError("down")
                return {"known": 5, "count": 12}
        self.fake, self.edsm_error = Fake(), False
        self.state.spansh = self.fake

    def classify(self):
        import asyncio
        t = {"id64": 99, "name": "There", "star_class": "K"}
        self.state.target_key = ("There", 99)
        asyncio.run(self.state.classify_target(t, ("There", 99)))
        return self.state.target

    def test_counts_and_edsm(self):
        t = self.classify()
        self.assertEqual((t["status"], t["known"], t["count"], t["edsm"]), ("partial", 3, 12, {"known": 5, "count": 12}))
        self.edsm_error = True                       # EDSM down: Spansh's counts still shown, the sound unaffected
        t = self.classify()
        self.assertEqual((t["known"], t["edsm"], t["sound"]), (3, None, "upbeat"))

    def test_edsm_bodies_request(self):
        import asyncio
        from support import _HwSession
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(200, {"name": "There", "bodyCount": 9, "bodies": [{"type": "Star"}, {"type": "Planet"}, {"type": "Belt"}]})])
        self.assertEqual(asyncio.run(sp.edsm_bodies("There")), {"known": 2, "count": 9})
        self.assertEqual(sp.session.calls[0], (ed_outrider.EDSM_BODIES, {"systemName": "There"}))
        sp.session = _HwSession([(200, [])])   # EDSM's answer for a system it does not have
        self.assertEqual(asyncio.run(sp.edsm_bodies("Nowhere")), {"known": 0, "count": None, "missing": True})
