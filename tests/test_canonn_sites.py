"""Known sites from Canonn (the pins follow-up, project/PLAN-canonn-sites-2026-10-26.md): the pure reading of Canonn's
answers (outrider/canonn_sites.py) and the server's ask, through a journal's body, State.canonn_sites and its route. The
page's part is in tests/page_smoke.js ("known sites"). Fakes only: nothing here reaches Canonn."""
import asyncio
import time
import unittest

from support import _HwSession, ed_outrider  # also puts the repository root on sys.path

import outrider.canonn_sites as CS

# Canonn's /settlement answer for Synuefe XR-H d11-102 (2026-10-26), trimmed: one ruin with the game's name, another
# reported only in five languages a few metres apart, a structure, an Odyssey settlement, another body's ruin
SETTLEMENTS = [
    {"bodyid": 13, "lat": "-46.576920", "lon": "133.985110", "market_id": None, "name": "$Ancient:#index=1;", "name_localised": None},
    {"bodyid": 13, "lat": "-31.838920", "lon": "-128.965850", "market_id": None, "name": "Ancient Ruins", "name_localised": None},
    {"bodyid": 13, "lat": "-31.838920", "lon": "-128.965850", "market_id": None, "name": "Antike Ruinen", "name_localised": None},
    {"bodyid": 13, "lat": "-31.838907", "lon": "-128.965881", "market_id": None, "name": "Ruínas Antigas", "name_localised": None},
    {"bodyid": 13, "lat": "-31.838921", "lon": "-128.965851", "market_id": None, "name": "Ruines anciennes", "name_localised": None},
    {"bodyid": 13, "lat": "-31.838907", "lon": "-128.965866", "market_id": None, "name": "Древние руины", "name_localised": None},
    {"bodyid": 13, "lat": "11.428930", "lon": "-30.327940", "market_id": None, "name": "$Ancient_Small_001:#index=1;", "name_localised": None},
    {"bodyid": 13, "lat": "5.0", "lon": "5.0", "market_id": 3900000001, "name": "Smith's Hold", "name_localised": None},
    {"bodyid": 14, "lat": "1.0", "lon": "1.0", "market_id": None, "name": "$Ancient:#index=2;", "name_localised": None},
    {"bodyid": 13, "lat": None, "lon": "1.0", "market_id": None, "name": "$Ancient:#index=3;", "name_localised": None},
]
POI = {"system": "Synuefe XR-H d11-102", "codex": [
    {"body": "1 b", "english_name": "Silicate Vapour Fumarole", "hud_category": "Geology", "latitude": "-2.049685", "longitude": "-68.896057"},
    {"body": "1 b", "english_name": "Silicate Vapour Fumarole", "hud_category": "Geology", "latitude": "2.759610", "longitude": "95.503170"},
    {"body": "1 b", "english_name": "Iron Magma Lava Spout", "hud_category": "Geology", "latitude": "-0.28", "longitude": "-97.0"},
    {"body": "1 b", "english_name": "Sulphur Dioxide Gas Vent", "hud_category": "Geology", "latitude": None, "longitude": None},
    {"body": "1 c", "english_name": "Silicate Vapour Fumarole", "hud_category": "Geology", "latitude": "64.3", "longitude": "-93.3"},
    {"body": "1 b", "english_name": "Guardian Relic Tower", "hud_category": "Guardian", "latitude": None, "longitude": None},
    {"body": "1 b", "english_name": "Bacterium Aurasus - Teal", "hud_category": "Biology", "latitude": "1", "longitude": "1"}]}


class Reading(unittest.TestCase):
    def test_guardian_sites_one_per_place(self):
        got = CS.guardian_sites(SETTLEMENTS, 13, 2000)
        self.assertEqual([(s["name"], s["lat"], s["lon"]) for s in got], [
            ("Guardian ruins 1", -46.57692, 133.98511),
            ("Guardian ruins", -31.83892, -128.96585),          # five languages, one ruin
            ("Guardian structure (small)", 11.42893, -30.32794)])
        self.assertEqual({s["kind"] for s in got}, {"guardian"})
        self.assertEqual([s["name"] for s in CS.guardian_sites(SETTLEMENTS, 14)], ["Guardian ruins 2"])   # by BodyID
        self.assertEqual(CS.guardian_sites(SETTLEMENTS, 99), [])
        with self.assertRaises(ValueError):
            CS.guardian_sites({"error": "busy"}, 13)

    def test_the_games_own_name_wins_a_merge(self):
        rows = [{"bodyid": 1, "lat": "10.00001", "lon": "20.0", "name": "Ancient Ruins"},
                {"bodyid": 1, "lat": "10.0", "lon": "20.0", "name": "$Ancient:#index=4;"},
                {"bodyid": 1, "lat": "10.0", "lon": "20.0", "name": "$Ancient_Huge_002:#index=2;"},   # the same spot: merged
                {"bodyid": 1, "lat": "-3", "lon": "7", "name": "$Ancient:#index=None;"},
                {"bodyid": 1, "lat": "40", "lon": "7", "name": "$Ancient_Medium_003:#index=2;"},
                {"bodyid": 1, "lat": "45", "lon": "7", "name": "$Ancient_Small:#index=1;"}]       # not the game's shape
        self.assertEqual([s["name"] for s in CS.guardian_sites(rows, 1, 1000)],
                         ["Guardian ruins 4", "Guardian ruins", "Guardian structure (medium) 2"])

    def test_geology_per_formation_with_positions(self):
        got = CS.geology_sites(POI, "1 b")
        self.assertEqual([(g["name"], g["n"], g["points"]) for g in got], [
            ("Silicate Vapour Fumarole", 2, [[-2.049685, -68.896057], [2.75961, 95.50317]]),
            ("Iron Magma Lava Spout", 1, [[-0.28, -97.0]])])      # no position, another body, not geology: left out
        many = {"system": "X", "codex": [{"body": "A", "english_name": "Water Ice Geyser", "hud_category": "Geology", "latitude": i / 100,
                           "longitude": 0} for i in range(CS.GEO_POINTS_MAX + 5)]}
        g = CS.geology_sites(many, "A")[0]
        self.assertEqual((g["n"], len(g["points"])), (CS.GEO_POINTS_MAX + 5, CS.GEO_POINTS_MAX))
        self.assertEqual(CS.geology_sites({"system": "X"}, "A"), [])   # no codex reports at all
        with self.assertRaises(ValueError):
            CS.geology_sites([], "A")


class Asking(unittest.TestCase):
    """Through the real path: your journal's body (its Scan and DSS signals) -> system_detail's row -> canonn_sites."""
    ID = 3302246887123

    def state(self, signals):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        ts = lambda s: ed_outrider.iso_ts(time.time() - s)
        sysname = "Synuefe XR-H d11-102"
        j.handle({"event": "FSDJump", "timestamp": ts(60), "StarSystem": sysname, "SystemAddress": self.ID, "StarPos": [0, 0, 0]})
        for name, bid, landable in (("1 b", 13, True), ("1 c", 15, False)):
            j.handle({"event": "Scan", "timestamp": ts(50), "ScanType": "Detailed", "BodyName": f"{sysname} {name}", "BodyID": bid,
                      "StarSystem": sysname, "SystemAddress": self.ID, "DistanceFromArrivalLS": 500.0, "PlanetClass": "Rocky body",
                      "Landable": landable, "Radius": 2000000.0, "SurfaceGravity": 2.0, "Parents": [{"Star": 0}]})
            j.handle({"event": "SAASignalsFound", "timestamp": ts(40), "BodyName": f"{sysname} {name}", "BodyID": bid,
                      "SystemAddress": self.ID, "Signals": [{"Type": t, "Count": c} for t, c in signals]})
        db.commit()
        sp = ed_outrider.Spansh(db)
        st = ed_outrider.State(db, j, sp, 25)
        return st

    def test_asks_only_for_what_the_body_has_and_keeps_it(self):
        st = self.state([("$SAA_SignalType_Guardian;", 3), ("$SAA_SignalType_Geological;", 2)])
        st.spansh.session = _HwSession([(200, SETTLEMENTS), (200, POI)])
        out, status = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual(status, 200)
        self.assertEqual([s["name"] for s in out["sites"]], ["Guardian ruins 1", "Guardian ruins", "Guardian structure (small)",
                                                             "Silicate Vapour Fumarole", "Iron Magma Lava Spout"])
        self.assertNotIn("error", out)
        self.assertEqual([c[0] for c in st.spansh.session.calls], [CS.SETTLEMENT_URL.format(self.ID), CS.POI_URL])
        self.assertEqual(st.spansh.session.calls[1][1], {"system": "Synuefe XR-H d11-102", "odyssey": "Y"})
        asyncio.run(st.canonn_sites(self.ID, "1 b"))                       # kept: Canonn is not asked again
        self.assertEqual(len(st.spansh.session.calls), 2)
        # a body that is not landable, a star, an unknown name: nothing asked
        self.assertEqual(asyncio.run(st.canonn_sites(self.ID, "1 c")), ({"sites": []}, 200))
        self.assertEqual(asyncio.run(st.canonn_sites(self.ID, "9 z"))[1], 404)
        self.assertEqual(len(st.spansh.session.calls), 2)

    def test_geology_alone_and_canonn_down(self):
        st = self.state([("$SAA_SignalType_Geological;", 2)])               # no Guardian signal: no settlement ask
        st.spansh.session = _HwSession([ed_outrider.ClientError("down")])
        out, status = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual((status, out["sites"]), (200, []))
        self.assertIn("Canonn could not be reached", out["error"])
        self.assertEqual([c[0] for c in st.spansh.session.calls], [CS.POI_URL])
        st.spansh.session = _HwSession([(200, POI)])
        asyncio.run(st.canonn_sites(self.ID, "1 b"))                        # a failure is kept a while, not asked at once
        self.assertEqual(st.spansh.session.calls, [])
        st.canonn_cache[self.ID]["poi"] = (time.time() - ed_outrider.CANONN_SITES_RETRY - 1,) + st.canonn_cache[self.ID]["poi"][1:]
        out, _ = asyncio.run(st.canonn_sites(self.ID, "1 b"))              # then asked again
        self.assertEqual(([s["name"] for s in out["sites"]], "error" in out), (["Silicate Vapour Fumarole", "Iron Magma Lava Spout"], False))
        st.spansh.session = _HwSession([(200, {"error": "changed"})])       # another shape: said, not raised
        st.canonn_cache.clear()
        out, _ = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual((out["sites"], out["error"]), ([], "Canonn answered in an unexpected shape"))

    def test_a_wrong_shape_is_a_failure_kept_briefly(self):
        """Review 8: a 200 answer of another shape (an error object, a codex that is not a list) was cached a day as an
        answer, the panel showing the error until then; a non-list codex raised a 500. Now both are failures, asked
        again after CANONN_SITES_RETRY."""
        with self.assertRaises(ValueError):
            CS.geology_sites({"system": "X", "codex": 5}, "A")
        with self.assertRaises(ValueError):
            CS.geology_sites({"system": "X", "codex": True}, "A")
        st = self.state([("$SAA_SignalType_Geological;", 2)])
        st.spansh.session = _HwSession([(200, {"error": "busy"})])
        out, status = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual((status, out["error"]), (200, "Canonn answered in an unexpected shape"))
        st.canonn_cache[self.ID]["poi"] = (time.time() - ed_outrider.CANONN_SITES_RETRY - 1,) + st.canonn_cache[self.ID]["poi"][1:]
        st.spansh.session = _HwSession([(200, POI)])
        out, _ = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual(([s["name"] for s in out["sites"]], "error" in out), (["Silicate Vapour Fumarole", "Iron Magma Lava Spout"], False))
        st.canonn_cache.clear()
        st.spansh.session = _HwSession([(200, {"system": "Synuefe XR-H d11-102", "codex": 7})])
        out, status = asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual((status, out["sites"], out["error"]), (200, [], "Canonn answered in an unexpected shape"))

    def test_the_cache_keeps_at_most_its_systems(self):
        st = self.state([("$SAA_SignalType_Geological;", 1)])
        st.spansh.session = _HwSession([(200, {"system": "X", "codex": []})])
        for i in range(ed_outrider.CANONN_SITES_SYSTEMS):
            st.canonn_cache[i] = {"poi": (time.time() - 100 + i, {}, None)}
        asyncio.run(st.canonn_sites(self.ID, "1 b"))
        self.assertEqual(len(st.canonn_cache), ed_outrider.CANONN_SITES_SYSTEMS)
        self.assertNotIn(0, st.canonn_cache)                               # the oldest dropped
        self.assertIn(self.ID, st.canonn_cache)

    def test_the_route(self):
        from aiohttp.test_utils import TestClient, TestServer
        st = self.state([("$SAA_SignalType_Guardian;", 1)])
        st.spansh.session = _HwSession([(200, SETTLEMENTS)])

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(st))) as c:
                r = await c.get("/api/body/sites", params={"system": str(self.ID), "name": "1 b"})
                out = [r.status, [s["name"] for s in (await r.json())["sites"]]]
                out.append((await c.get("/api/body/sites", params={"system": "x", "name": "1 b"})).status)
                out.append((await c.get("/api/body/sites", params={"system": str(self.ID)})).status)
                return out
        self.assertEqual(asyncio.run(go()), [200, ["Guardian ruins 1", "Guardian ruins", "Guardian structure (small)"], 400, 400])


if __name__ == "__main__":
    unittest.main()
