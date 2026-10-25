"""Explorer ideas from EDCodex's Exploration tools (project/PLAN-explorer-ideas-2026-10-25.md), the server's parts:
Search's "at least N" (7). The page's parts are in tests/page_smoke.js ("explorer ideas"). Fakes only."""
import asyncio
import time
import unittest

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


if __name__ == "__main__":
    unittest.main()
