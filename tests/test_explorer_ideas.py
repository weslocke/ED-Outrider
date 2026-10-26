"""Explorer ideas from EDCodex's Exploration tools (project/PLAN-explorer-ideas-2026-10-25.md), the server's parts:
Search's "at least N" (7), EDSM's first reporter (5), the surface trail (1), catalogued sights (9). The page's parts are in tests/page_smoke.js ("explorer ideas"). Fakes only."""
import asyncio
import time
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path

CRIT = {"stars": set(), "planets": set(), "rings": set(), "hotspots": set()}


class AtLeastN(unittest.TestCase):
    """7: a system with at least N bodies among a section's ticks, Local and Spansh."""

    def recs(self, n_elw):
        return [{"name": f"S {i}", "type": "Planet", "subtype": "Earth-like world"} for i in range(n_elw)] + \
               [{"name": "S 9", "type": "Planet", "subtype": "Water world"}]

    def test_match_system(self):
        crit = dict(CRIT, planets={"Earth-like world"})
        self.assertIn("planets", ed_outrider.match_system("S", self.recs(1), crit))
        self.assertNotIn("planets", ed_outrider.match_system("S", self.recs(1), dict(crit, planets_min=2)))
        self.assertIn("planets", ed_outrider.match_system("S", self.recs(2), dict(crit, planets_min=2)))
        # two kinds ticked: two of either is two
        both = dict(crit, planets={"Earth-like world", "Water world"}, planets_min=2)
        self.assertIn("planets", ed_outrider.match_system("S", self.recs(1), both))
        stars = [{"name": "A", "type": "Star", "subtype": "M (Red dwarf) Star", "main": True},
                 {"name": "B", "type": "Star", "subtype": "M (Red dwarf) Star"}]
        scrit = dict(CRIT, stars={"M (Red dwarf) Star"}, main_only=False)
        self.assertIn("stars", ed_outrider.match_system("S", stars, dict(scrit, stars_min=2)))
        self.assertNotIn("stars", ed_outrider.match_system("S", stars, dict(scrit, stars_min=3)))
        # "arrival star only" (the form's default) with "at least 2": every star counts (review 2026-10-25: the arrival
        # star alone could never be two, so it matched nothing)
        crit = ed_outrider.search_criteria({"stars": ["M"], "main_only": True, "stars_min": 2}, None)
        self.assertFalse(crit["main_only"])
        self.assertIn("stars", ed_outrider.match_system("S", stars, dict(CRIT, **{k: crit[k] for k in ("stars", "main_only", "stars_min")})))
        self.assertTrue(ed_outrider.search_criteria({"stars": ["M"], "main_only": True}, None)["main_only"])   # one: as ticked

    def test_the_limits(self):
        self.assertEqual([ed_outrider.search_min(v) for v in (None, 0, 1, 2, 20, 21, "3", True, 2.5)],
                         [1, 1, 1, 2, 20, 1, 1, 1, 1])

    def test_through_the_searcher(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        now = time.time()
        j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(now - 30), "StarSystem": "Home", "SystemAddress": 9,
                  "StarPos": [0, 0, 0]})
        for i, (name, n) in enumerate((("One ELW", 1), ("Two ELW", 2))):
            recs = [{"name": f"{name} {k}", "type": "Planet", "subtype": "Earth-like world", "full": True} for k in range(n)]
            db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (?, 'x', ?, ?, ?, 0, 0)",
                       (100 + i, ed_outrider.json.dumps({"name": name, "x": 10.0 + i, "y": 0.0, "z": 0.0, "records": recs}), now, 10.0 + i))
        db.commit()
        s = ed_outrider.Searcher(ed_outrider.State(db, j, ed_outrider.Spansh(db), 25))

        def search(params):   # the Searcher `s` of the moment
            async def go():
                s.start(dict({"radius": 50, "source": "local", "planets": ["Earth-like world"]}, **params))
                await s.task
            asyncio.run(go())
            return sorted(x["name"] for x in s.result["results"])
        self.assertEqual(search({}), ["One ELW", "Two ELW"])
        self.assertEqual(search({"planets_min": 2}), ["Two ELW"])

        # Spansh answers body by body: grouped by system, then counted
        body = lambda sysname, i64, k: {"name": f"{sysname} {k}", "type": "Planet", "subtype": "Earth-like world", "body_id": k,
                                        "system_name": sysname, "system_id64": i64, "system_x": 10.0, "system_y": 0.0, "system_z": 0.0}

        class Fake:
            async def body_search(self, filters, pos, radius, pages):
                return [body("X", 501, 1), body("X", 501, 2), body("Y", 502, 1)], None
        s = ed_outrider.Searcher(ed_outrider.State(db, j, Fake(), 25))
        self.assertEqual(search({"source": "spansh"}), ["X", "Y"])
        self.assertEqual(search({"source": "spansh", "planets_min": 2}), ["X"])


class EdsmFirst(unittest.TestCase):
    """5: who first reported a system's bodies to EDSM, from the bodies answer Outrider already asks for the target."""

    def test_the_earliest(self):
        bodies = [{"type": "Star", "discovery": {"commander": "Late", "date": "2019-03-01 10:00:00"}},
                  {"type": "Planet", "discovery": {"commander": "Vorrash", "date": "2016-10-25 12:34:56"}},
                  {"type": "Planet"}, {"type": "Planet", "discovery": {"commander": None, "date": "2010-01-01 00:00:00"}}]
        self.assertEqual(ed_outrider.edsm_first(bodies), {"commander": "Vorrash", "date": "2016-10-25"})
        self.assertIsNone(ed_outrider.edsm_first([{"type": "Planet"}]))
        self.assertIsNone(ed_outrider.edsm_first(None))

    def test_kept_for_here(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        st = ed_outrider.State(db, ed_outrider.Journals(db), ed_outrider.Spansh(db), 25)
        base = {"name": "Far", "x": 10.0, "y": 0.0, "z": 0.0,
                "records": [{"name": "Far", "type": "Star", "subtype": "K (Yellow-Orange) Star", "main": True, "full": True, "body_id": 0}]}
        db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (42, 'x', ?, ?, 10, 0, 0)",
                   (ed_outrider.json.dumps(base), time.time()))
        db.commit()
        self.assertIsNone(st.system_detail(42)["edsm_first"])                    # EDSM never asked about it
        st.edsm_first[42] = {"commander": "Vorrash", "date": "2016-10-25"}
        self.assertEqual(st.system_detail(42)["edsm_first"], {"commander": "Vorrash", "date": "2016-10-25"})


class Trail(unittest.TestCase):
    """1: where you have been on this body this visit, for the surface map."""

    def here(self, lat, lon, body=5):
        return {"system": 9, "body_id": body, "lat": lat, "lon": lon, "radius": 1_000_000}

    def test_steps_bodies_and_leaving(self):
        t = ed_outrider.SurfaceTrail()
        t.note(self.here(0.0, 0.0))
        t.note(self.here(0.0, 0.0005))          # ~9 m: not a point yet
        self.assertEqual(t.points((9, 5)), [])  # one point is no line
        t.note(self.here(0.0, 0.002))           # ~35 m
        self.assertEqual(t.points((9, 5)), [[0.0, 0.0], [0.0, 0.002]])
        self.assertEqual(t.points((9, 6)), [])  # another body: not this trail
        t.note(self.here(0.0, 0.004, body=6))   # another body: afresh
        t.note(self.here(0.0, 0.006, body=6))
        self.assertEqual(t.points((9, 6)), [[0.0, 0.004], [0.0, 0.006]])
        t.note(None)                            # left the body: gone
        self.assertEqual(t.points((9, 6)), [])

    def test_capped_and_thinned(self):
        t = ed_outrider.SurfaceTrail()
        for i in range(t.TRAIL_MAX + 1):
            t.note(self.here(0.0, i * 0.002))
        self.assertLessEqual(len(t.pts), t.TRAIL_MAX)
        self.assertEqual(t.pts[-1], (0.0, round(t.TRAIL_MAX * 0.002, 5)))   # the newest kept
        sent = t.points((9, 5))
        self.assertEqual(len(sent), t.TRAIL_SENT)
        self.assertEqual(sent[-1], list(t.pts[-1]))


class Sights(unittest.TestCase):
    """9: EDAstro's catalogued sights, fetched at runtime (a made-up answer here, never their data)."""
    ANSWER = [{"id": 1, "id64": 42, "name": "Lyceum", "type": "Sights and Scenery", "summary": "x" * 400,
               "poiUrl": "https://edastro.com/gec/view/1", "galMapSearch": "Far", "coordinates": [100.0, 0.0, 0.0]},
              {"id": 2, "id64": 43, "name": "Spire", "type": "Planetary Features", "summary": "", "poiUrl": "javascript:x",
               "galMapSearch": "Farther", "coordinates": [400.0, 0.0, 0.0]},
              {"id": 3, "id64": None, "name": "No id", "coordinates": [1, 2, 3]}, "junk"]

    def test_compact_and_nearest(self):
        import outrider.sights as S
        got = S.compact(self.ANSWER)
        self.assertEqual([e["name"] for e in got], ["Lyceum", "Spire"])   # no id64: left out
        self.assertEqual((len(got[0]["summary"]), got[0]["id64"], got[1]["url"], got[1]["summary"]), (S.SUMMARY_MAX, "42", None, None))
        with self.assertRaises(ValueError):
            S.compact({"error": "maintenance"})
        near = S.nearest(got, {"x": 0.0, "y": 0.0, "z": 0.0}, 500)
        self.assertEqual((near["name"], near["distance"]), ("Lyceum", 100.0))
        self.assertIsNone(S.nearest(got, {"x": 0.0, "y": 0.0, "z": 0.0}, 50))   # none within reach
        self.assertIsNone(S.nearest(got, {"x": 0.0, "y": 0.0, "z": 0.0}, 0))    # off
        self.assertEqual(sorted(S.by_system(got)), ["42", "43"])

    def state(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(time.time() - 30), "StarSystem": "Home", "SystemAddress": 9,
                  "StarPos": [0, 0, 0]})
        return ed_outrider.State(db, j, ed_outrider.Spansh(db), 25)

    def test_the_conditional_fetch_here_nearby_and_now(self):
        st, asked = self.state(), []

        async def fake(url, etag=None, modified=None):
            asked.append((url, etag))
            return (200, self.ANSWER, "e1", "m1") if etag is None else (304, None, etag, modified)
        st.spansh.get_if_changed = fake
        self.assertIsNone(st.sight_near())                     # nothing fetched yet
        asyncio.run(st.sights_check())
        self.assertEqual(st.sight_near()["name"], "Lyceum")
        self.assertEqual([e["name"] for e in st.sights_here(42)], ["Lyceum"])
        asyncio.run(st.sights_check())                         # unchanged: asked with its etag, the copy kept
        self.assertEqual(asked, [(ed_outrider.GEC_URL, None), (ed_outrider.GEC_URL, "e1")])
        self.assertEqual(st.sight_near()["name"], "Lyceum")
        # read from the database once, not per Nearby row (in-depth review 2026-10-25); an unchanged answer is not
        # stored again (EDAstro sends no validators: the whole catalogue comes every day)
        st2 = self.state()
        st2.spansh.get_if_changed = lambda url, etag=None, modified=None: fake(url, None, None)
        asyncio.run(st2.sights_check())
        stored = ed_outrider.meta_get(st2.db, "sights")
        with unittest.mock.patch.object(ed_outrider, "meta_get", side_effect=AssertionError("read again")):
            for _ in range(5):
                st2.sights_here(42)
        with unittest.mock.patch.object(ed_outrider, "meta_set", wraps=ed_outrider.meta_set) as ms:
            asyncio.run(st2.sights_check())
        self.assertEqual([c.args[1] for c in ms.call_args_list], ["sights_checked"])
        self.assertEqual(ed_outrider.meta_get(st2.db, "sights"), stored)
        st.sights_range = 50                                   # out of reach
        st._sight_near = (None, None)
        self.assertIsNone(st.sight_near())
        st.sights_range = 0                                    # off: nothing shown anywhere
        self.assertEqual((st.sights_here(42), st.sight_near()), ([], None))

    def test_the_setting(self):
        self.assertEqual(ed_outrider.CONFIG_RANGES[("server", "sights_range")][:2], (0, 5000))
        import outrider.config_edit as C
        self.assertIn(("server", "sights_range"), [k for _, _, keys in C.GROUPS for k in keys])


if __name__ == "__main__":
    unittest.main()
