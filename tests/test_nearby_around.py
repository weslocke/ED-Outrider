"""Unit tests: Nearby's Around (2026-10-14, the ideas of Rainmangames' PR #8, "Lock System" and filters, built on S49's
Around): where Nearby's sphere is (you, your destination, carrier or next stop, this system locked, a system by id64),
the choice saved on the server, Spansh asked only when the centre changes or on ↻ (paced), From you beside Dist.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import json
import time
import types
import unittest
from unittest import mock

from support import ed_outrider  # also puts the repository root on sys.path

import outrider.tools as tools


class NearbyAround(unittest.TestCase):

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()
        self.jump(9, "Home Port", 0)
        # two systems Outrider can place: one 100 ly away (a system typed by name), one 300 ly (the next stop)
        for id64, name, x in ((77, "Far Water", 100.0), (79, "Farther Water", 300.0)):
            base = {"name": name, "x": x, "y": 0.0, "z": 0.0, "records": []}
            self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (?, 'x', ?, ?, ?, 0, 0)",
                            (id64, json.dumps(base), self.now, x))
        self.db.commit()
        self.asked = []   # every sphere search: (centre name, radius)

        async def sphere(pos, r):
            self.asked.append((pos["name"], r))
            return [{"id64": 500 + i, "name": f"Near {pos['name']} {i}", "x": pos["x"] + i, "y": 0.0, "z": 0.0,
                     "distance": float(i), "bodies": []} for i in (1, 2)]
        self.spansh = types.SimpleNamespace(sphere=sphere, cached=lambda i: (None, None), store=lambda *a, **k: None,
                                            full_records=None)
        self.state = ed_outrider.State(self.db, self.j, self.spansh, 25)

    def jump(self, id64, name, x):
        self.now += 60
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(self.now), "StarSystem": name,
                       "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def run_ticks(self, *steps):
        """Each step (a callable or None) then a tick's maybe_refresh and the search it started, on one event loop."""
        async def go():
            out = []
            for step in steps:
                if step:
                    out.append(step())
                self.state.maybe_refresh()
                if self.state.refresh_task:
                    await self.state.refresh_task
            return out
        return asyncio.run(go())

    def test_saved_choice_is_checked(self):
        """meta near_around read back: a moving kind keeps only its name, a fixed one its place; anything else is you."""
        nc = ed_outrider.near_choice
        self.assertEqual(nc(None), {"around": "here"})
        self.assertEqual(nc({"around": "carrier", "id64": 5}), {"around": "carrier"})
        lock = {"around": "lock", "id64": 9, "name": "Home Port", "x": 0, "y": 1.5, "z": -2}
        self.assertEqual(nc(dict(lock, extra=1)), lock)
        for bad in ({"around": "lock", "id64": 9, "name": "Home Port"}, {"around": "system", "id64": "9", "name": "A", "x": 0, "y": 0, "z": 0},
                    {"around": "lock", "id64": 9, "name": "A", "x": True, "y": 0, "z": 0}, {"around": "somewhere"}, "lock", []):
            self.assertEqual(nc(bad), {"around": "here"}, bad)

    def test_centre_per_option(self):
        """You by default; "lock" pins where you are now (it stays as you fly on); a system by id64 is fixed there; the
        destination, carrier and next stop follow what they name, and one that names nothing leaves the sphere around
        you with why. Each answer is the summary the payload carries."""
        st = self.state
        self.assertEqual(st.nearby_centre()["name"], "Home Port")
        self.assertEqual(st.near_around_summary(), {"around": "here"})
        self.run_ticks(lambda: st.set_near_around("lock"))
        self.jump(10, "Elsewhere", 30)
        self.assertEqual((st.nearby_centre()["name"], st.nearby_centre()["around"]), ("Home Port", "lock"))
        s = st.near_around_summary()
        self.assertEqual((s["around"], s["name"], s["id"], s["from_you"], s["why"]), ("lock", "Home Port", "9", 30.0, None))
        out = self.run_ticks(lambda: st.set_near_around("77"))[0]
        self.assertEqual((out[0]["around"], out[0]["name"], out[0]["from_you"]), ("system", "Far Water", 70.0))
        self.assertEqual(st.nearby_centre()["x"], 100.0)
        # the moving kinds
        self.run_ticks(lambda: st.set_near_around("next_stop"))
        self.assertEqual(st.near_around_summary()["why"], "no next stop is set")
        self.assertEqual(st.nearby_centre()["name"], "Elsewhere")          # around you meanwhile
        self.assertFalse(st.near_pinned())
        self.assertTrue(st.set_next_stop(79))
        self.run_ticks(None)
        self.assertEqual((st.center["name"], st.near_around_summary()["why"]), ("Farther Water", None))
        self.run_ticks(lambda: st.set_near_around("carrier"))
        self.assertEqual(st.near_around_summary()["why"], "you have no fleet carrier")
        self.j.carrier = {"id64": 77, "system": "Far Water"}
        self.run_ticks(None)
        self.assertEqual(st.center["name"], "Far Water")
        self.run_ticks(lambda: st.set_near_around("destination"))
        self.assertEqual(st.near_around_summary()["why"], "no system is targeted in game")
        self.j.status_json = {"live": True, "destination": {"System": 79, "Name": "Farther Water"}}
        self.run_ticks(None)
        self.assertEqual(st.center["name"], "Farther Water")
        # refusals: nothing saved
        self.assertEqual(st.set_near_around("somewhere"), (None, ed_outrider.AROUND_BAD))
        self.assertIn("doesn't know where", st.set_near_around("123456")[1])
        self.assertEqual(st.near_choice, {"around": "destination"})

    def test_carrier_placed_later_is_used(self):
        """A carrier (or target) Outrider cannot place yet is tried again after NEAR_MISS_RETRY_S, under the same id64:
        its place is often learnt a moment later (a carrier that jumped without you), and Nearby then moves there."""
        st = self.state
        self.j.carrier = {"id64": 1234, "system": "Far Away"}
        self.run_ticks(lambda: st.set_near_around("carrier"))
        self.assertEqual(st.near_around_summary()["why"], "Outrider doesn't know where Far Away is")
        base = {"name": "Far Away", "x": 500.0, "y": 0.0, "z": 0.0, "records": []}
        self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (1234, 'x', ?, ?, 500, 0, 0)",
                        (json.dumps(base), self.now))
        self.run_ticks(None)
        self.assertEqual(st.center["name"], "Home Port")   # not worked out again every tick
        st._near_miss = st._near_miss[:2] + (st._near_miss[2] - ed_outrider.NEAR_MISS_RETRY_S,)
        self.run_ticks(None)
        self.assertEqual((st.center["name"], st.near_why), ("Far Away", None))
        self.assertTrue(st.near_pinned())

    def test_lock_needs_a_position(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        st = ed_outrider.State(db, ed_outrider.Journals(db), self.spansh, 25)
        self.assertEqual(st.set_near_around("lock"), (None, "your position is not known yet"))
        self.assertIsNone(ed_outrider.meta_get(db, "near_around"))

    def test_choice_survives_a_restart_and_a_reread(self):
        """Saved in meta near_around (live-only): a new State reads it back, a journal re-read keeps it."""
        self.run_ticks(lambda: self.state.set_near_around("lock"))
        want = {"around": "lock", "id64": 9, "name": "Home Port", "x": 0.0, "y": 0.0, "z": 0.0}
        self.assertEqual(ed_outrider.meta_get(self.db, "near_around"), want)
        ed_outrider.reset_journal_data(self.db)
        self.assertEqual(ed_outrider.meta_get(self.db, "near_around"), want)
        again = ed_outrider.State(self.db, self.j, self.spansh, 25)
        self.assertEqual(again.near_choice, want)
        self.assertEqual(again.nearby_centre()["name"], "Home Port")

    def test_spansh_asked_only_when_the_centre_changes(self):
        """Around you every arrival asks (as before). Locked: arrivals ask nothing (no timer either), a system inside the
        sphere Spansh did not list joins it as your own at once; a new centre asks once; back to you asks around you."""
        st = self.state
        self.run_ticks(None, None)
        self.assertEqual(self.asked, [("Home Port", 25)])
        self.run_ticks(lambda: st.set_near_around("lock"), None)
        self.assertEqual(self.asked, [("Home Port", 25)])                   # locked where the sphere already is
        self.run_ticks(lambda: self.jump(10, "Inside", 5), lambda: self.jump(11, "Outside", 60), None)
        with mock.patch.object(time, "time", return_value=self.now + 3600):
            self.run_ticks(None)                                            # an hour on: still nothing
        self.assertEqual(self.asked, [("Home Port", 25)])
        self.assertIn(10, st.systems)                                       # the visit inside the sphere joined
        self.assertEqual((st.systems[10]["source"], st.systems[10]["distance"], st.systems[10]["in_spansh"]), ("own", 5.0, False))
        self.assertNotIn(11, st.systems)                                    # outside it: not a row
        self.assertNotIn("Home Port", [n for n, _ in self.asked[1:]])
        self.run_ticks(lambda: st.set_near_around("77"), None)
        self.assertEqual(self.asked[1:], [("Far Water", 25)])
        self.run_ticks(lambda: st.set_near_around("here"), None)
        self.assertEqual(self.asked[2:], [("Outside", 25)])
        self.run_ticks(lambda: self.jump(12, "Next", 70))                   # around you: an arrival asks
        self.assertEqual(self.asked[3:], [("Next", 25)])

    def test_refresh_is_paced(self):
        """↻: only while Nearby is around another system, not while a search runs, NEAR_REFRESH_GAP_S after the last
        ask; it then asks the same sphere again."""
        st = self.state
        self.run_ticks(None)
        self.assertEqual(st.refresh_nearby(), (False, "Nearby is around you: it asks Spansh again at each arrival"))
        self.run_ticks(lambda: st.set_near_around("77"))
        ok, why = st.refresh_nearby()
        self.assertFalse(ok)
        self.assertRegex(why, r"^Spansh was asked \d+ s ago: again in \d+ s$")
        later = st.near_asked + ed_outrider.NEAR_REFRESH_GAP_S + 1

        async def go():
            ok = st.refresh_nearby(now=later)
            busy = st.refresh_nearby(now=later + 999)                       # the search it started still runs
            await st.refresh_task
            return ok, busy
        ok, busy = asyncio.run(go())
        self.assertEqual((ok, busy), ((True, None), (False, "Spansh is being asked already")))
        self.assertEqual([n for n, _ in self.asked], ["Home Port", "Far Water", "Far Water"])

    def test_rows_measure_from_the_centre_and_from_you(self):
        """Dist is from the centre; each row carries its xyz, so From you (and the jump count) is from you; the
        auto-target test's "nearest known system a plain jump away" stays from you."""
        st = self.state
        self.run_ticks(lambda: st.set_near_around("77"))
        row = st.systems[501]
        self.assertEqual((row["distance"], row["xyz"]), (1.0, [101.0, 0.0, 0.0]))
        self.assertEqual(st.near_from_you(row), 101.0)
        self.run_ticks(lambda: self.jump(10, "Close", 99))
        self.assertEqual(st.near_from_you(st.systems[502]), 3.0)
        self.j.jump_range = {"ly": 10.0}
        st.range_now = lambda: 10.0
        self.assertEqual(st.autotarget_test_target()[0]["name"], "Near Far Water 1")   # 2 ly from you, not "1 ly"
        self.run_ticks(lambda: self.jump(13, "Away", 500))
        self.assertIsNone(st.autotarget_test_target()[0])                  # nothing a jump from you
        p = st.payload()
        self.assertEqual((p["near_around"]["name"], p["near_around"]["from_you"]), ("Far Water", 400.0))

    def test_ai_tools_measure_from_you(self):
        """The AI's nearby_systems gives distances from the commander when the list is around another system (and says
        where it is); nearest_unvisited says it cannot answer then rather than claim the horizon."""
        st = self.state
        self.run_ticks(lambda: st.set_near_around("77"))
        p = json.loads(json.dumps(st.payload()))

        async def get(path, params=None):
            return p
        out = asyncio.run(tools.call("nearby_systems", {}, get, 10))
        self.assertEqual(out["list_around"], "Far Water")
        self.assertEqual([(x["name"], x["distance_ly"]) for x in out["systems"]], [("Near Far Water 1", 101.0), ("Near Far Water 2", 102.0)])
        n = asyncio.run(tools.call("nearest_unvisited", {}, get, 10))
        self.assertIsNone(n["nearest"])
        self.assertIn("Nearby is set around Far Water", n["note"])
        self.run_ticks(lambda: st.set_near_around("here"))
        p = json.loads(json.dumps(st.payload()))
        self.assertNotIn("list_around", asyncio.run(tools.call("nearby_systems", {}, get, 10)))

    def test_routes(self):
        """POST /api/nearby/around and /api/nearby/refresh: the body checked, a refusal's status, the saved summary."""
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                post = lambda path, body=None: c.post(path, json=body)
                out = []
                for body in ({"around": "lock"}, {"around": 5}, {}, {"around": "x" * 30}, {"around": "nowhere"}, {"around": "123456"}):
                    r = await post("/api/nearby/around", body)
                    out.append((r.status, await r.json()))
                r = await post("/api/nearby/refresh")
                out.append((r.status, await r.json()))
                if self.state.refresh_task:
                    await self.state.refresh_task
                return out
        out = asyncio.run(go())
        self.assertEqual(out[0][0], 200)
        self.assertEqual((out[0][1]["near_around"]["around"], out[0][1]["near_around"]["name"]), ("lock", "Home Port"))
        self.assertEqual([s for s, _ in out[1:]], [400, 400, 400, 400, 409, 409])
        self.assertIn("Spansh was asked", out[6][1]["error"])
        self.assertEqual(self.state.near_choice["around"], "lock")


if __name__ == "__main__":
    unittest.main()
