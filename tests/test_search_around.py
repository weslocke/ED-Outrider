"""Unit tests: S49, Search and the Nearest finder around another system (State.search_origin: where you are, the game's
destination, your carrier, the next stop or an id64; read only), the distances from there and each row's from you.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import json
import time
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path


def water(name):
    return {"name": name, "type": "Planet", "subtype": "Water world", "full": True}


class SearchAround(unittest.TestCase):

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(self.now - 60), "StarSystem": "Home Port",
                       "SystemAddress": 9, "StarPos": [0, 0, 0]})
        # a water world 10 ly from you, and two 1,000 ly away (one by the carrier, one by a system found by name)
        for id64, name, x in ((78, "Near Water", 10.0), (77, "Far Water", 1000.0), (79, "Farther Water", 1030.0)):
            base = {"name": name, "x": x, "y": 0.0, "z": 0.0, "records": [water(f"{name} 1")]}
            self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (?, 'x', ?, ?, ?, 0, 0)",
                            (id64, json.dumps(base), self.now, x))
        self.db.commit()
        self.state = ed_outrider.State(self.db, self.j, ed_outrider.Spansh(self.db), 25)

    def search(self, **params):
        s = ed_outrider.Searcher(self.state)

        async def go():
            s.start(dict({"source": "local", "radius": 50, "planets": ["Water world"]}, **params))
            await s.task
        asyncio.run(go())
        return s.result

    def test_origin(self):
        """Where you are by default; the carrier, the next stop, the game's target and an id64 by locate() (or what the
        page lists); each says why not when there is none."""
        self.assertEqual(self.state.search_origin(None)[0]["name"], "Home Port")
        self.assertEqual(self.state.search_origin("here")[0]["around"], "here")
        self.assertEqual(self.state.search_origin("carrier"), (None, "you have no fleet carrier"))
        self.assertEqual(self.state.search_origin("next_stop"), (None, "no next stop is set"))
        self.assertEqual(self.state.search_origin("destination"), (None, "no system is targeted in game"))
        self.assertEqual(self.state.search_origin("somewhere"), (None, ed_outrider.AROUND_BAD))
        self.assertEqual(self.state.search_origin(77), (None, ed_outrider.AROUND_BAD))   # an id64 comes as a string
        self.assertEqual(self.state.search_origin("²"), (None, ed_outrider.AROUND_BAD))   # a Unicode digit (review L20)
        self.assertIn("doesn't know where", self.state.search_origin("123456")[1])
        o, _ = self.state.search_origin("77")
        self.assertEqual((o["id64"], o["name"], o["x"], o["around"]), (77, "Far Water", 1000.0, "system"))
        self.j.carrier = {"id64": 500, "system": "Carrier Place", "x": 990.0, "y": 0.0, "z": 0.0}   # listed_system's
        o, _ = self.state.search_origin("carrier")
        self.assertEqual((o["name"], o["x"], o["around"]), ("Carrier Place", 990.0, "carrier"))
        self.assertTrue(self.state.set_next_stop(79))
        self.assertEqual(self.state.search_origin("next_stop")[0]["name"], "Farther Water")
        self.j.status_json = {"live": True, "destination": {"System": 77, "Name": "Far Water"}}
        self.assertEqual(self.state.search_origin("destination")[0]["name"], "Far Water")

    def test_search_around_another_system(self):
        """The search looks around the origin: what is near it, its distances, the status names it; each result says how
        far it is from you. Around you there is no from_you."""
        r = self.search()
        self.assertEqual([(x["name"], x["distance"], x["from_you"]) for x in r["results"]], [("Near Water", 10.0, None)])
        self.assertEqual(r["around"], "here")
        r = self.search(around="77")
        self.assertEqual([(x["name"], x["distance"], x["from_you"]) for x in r["results"]],
                         [("Far Water", 0.0, 1000.0), ("Farther Water", 30.0, 1030.0)])
        self.assertIn("within 50 ly of Far Water", r["status"])
        self.assertEqual((r["origin"], r["around"]), ("Far Water", "system"))
        r = self.search(around="carrier")   # no carrier: said, nothing searched
        self.assertEqual((r["status"], r["results"], r["running"]), ("search failed: you have no fleet carrier", [], False))


class NearestAround(unittest.TestCase):
    """The Nearest finder around another system: Spansh asked about that place, the distances from there, `here` and
    from_you from you, no jump count (your laden range says nothing there), the answer cached per origin."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.j.pos = {"id64": 9, "name": "Home Port", "x": 0.0, "y": 0.0, "z": 0.0}
        self.j.jump_range = {"ly": 50.0}
        self.asked = []
        rows = [{"system_id64": 9, "system_name": "Home Port", "system_x": 0.0, "system_y": 0.0, "system_z": 0.0},
                {"system_id64": 77, "system_name": "Far Water", "system_x": 1000.0, "system_y": 0.0, "system_z": 0.0}]
        stations = [dict(r, name=f"{r['system_name']} Dock", type="Coriolis Starport", distance_to_arrival=100,
                         has_large_pad=True, medium_pads=1, services=[{"name": "Universal Cartographics"}],
                         updated_at=ed_outrider.iso_ts(time.time() - 3600)) for r in rows]
        asked = self.asked

        class Spansh:
            async def dock_search(self, pos, need=()):
                asked.append(pos["x"])
                return stations

            async def permit_ids(self, ids):
                return set()

            async def get_if_changed(self, url, etag=None, modified=None):
                return 304, None, etag, modified
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.spansh = Spansh()
        self.state.range_now = lambda: 50.0
        base = {"name": "Far Water", "x": 1000.0, "y": 0.0, "z": 0.0, "records": []}
        self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (77, 'x', ?, 1, 1000, 0, 0)",
                        (json.dumps(base),))

    def ask(self, **q):
        return asyncio.run(self.state.nearest_dock(dict({"age": "30", "cached": "1"}, **q)))

    def test_around(self):
        out, status = self.ask()
        self.assertEqual(status, 200)
        home = {r["system"]: r for r in out["rows"]}
        self.assertTrue(home["Home Port"]["here"])
        self.assertEqual(home["Far Water"]["jumps"], 20)   # 1,000 ly at your 50 ly
        self.assertNotIn("from_you", home["Far Water"])
        self.assertEqual((out["around"], out["where"]), ("here", "Home Port"))
        out, status = self.ask(around="77")
        self.assertEqual(status, 200)
        self.assertEqual(self.asked, [0.0, 1000.0])   # Spansh asked about the place, not reused from your answer
        rows = {r["system"]: r for r in out["rows"]}
        self.assertEqual([r["system"] for r in out["rows"]], ["Far Water", "Home Port"])   # nearest the origin first
        far, home = rows["Far Water"], rows["Home Port"]
        self.assertEqual((far["ly"], far["from_you"], far["here"], far["jumps"]), (0.0, 1000.0, False, None))
        self.assertEqual((home["ly"], home["from_you"], home["here"], home["jumps"]), (1000.0, 0.0, True, None))
        self.assertEqual((out["around"], out["where"], out["laden"]), ("system", "Far Water", None))
        self.ask(around="77")
        self.assertEqual(len(self.asked), 2)   # the same place again: the search reused
        self.assertEqual(self.ask(around="carrier"), ({"error": "you have no fleet carrier"}, 409))
        self.assertEqual(self.ask(around="Far Water")[1], 400)   # a name goes through /api/find first


if __name__ == "__main__":
    unittest.main()
