"""Surface pins (NEXT-VERSION #16, the author 2026-10-17): named points on a body kept until deleted (POST /api/pins),
one active at a time (the one tapped, else the first not reached, in order), guided from orbit down (the payload's
pins), said as it is set, at 10 km, 1 km and 100 m, and on arrival, when the next one takes over (State.pin_watch).
The page's side: tests/page_smoke.js ("surface pins")."""
import asyncio
import math
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path

R = 1_000_000.0   # the body's radius (m)


def lon_for(m):
    """The longitude m metres east of 0, 0 on the test body."""
    return math.degrees(m / R)


class Pins(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.pos = {"id64": 1, "name": "Sys", "x": 0, "y": 0, "z": 0}
        self.j.body_here = {"system": 1, "name": "Sys B 7", "body_id": 7}
        self.at(0.0, 0.0)

    def at(self, lat, lon, heading=0, flags=0, flags2=1):
        self.j.status_json = {"live": True, "body": "Sys B 7", "lat": lat, "lon": lon, "planet_radius": R, "heading": heading,
                              "flags": flags, "flags2": flags2}

    def post(self, **body):
        out, status = self.state.pins_post(body)
        self.assertEqual(status, 200, out)
        return out

    def said(self):
        return [(m["what"], m["name"]) for m in self.j.moments if m["kind"] == "pin"]

    def test_add_and_change(self):
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="Wreck", lat=0.0, lon=lon_for(12000))
        out = self.post(action="add", system="1", sysname="Sys", body="Sys B 7", lat=0.0, lon=lon_for(500))   # no name
        self.assertEqual([p["name"] for p in out["pins"]], ["Wreck", "Pin 2"])
        self.post(action="here", name="  Spot   here ")
        a, b, c = self.state.pins_body(1, "Sys B 7")
        self.assertEqual((c["name"], c["lat"], c["lon"]), ("Spot here", 0.0, 0.0))
        for bad, why in (({"action": "add", "system": "x", "body": "B", "lat": 0, "lon": 0}, "system"),
                         ({"action": "add", "system": "1", "body": "Sys B 7", "lat": 91, "lon": 0}, "latitude"),
                         ({"action": "add", "system": "1", "body": "Sys B 7", "lat": 0, "lon": True}, "longitude"),
                         ({"action": "rename", "id": a["id"], "name": "  "}, "name"),
                         ({"action": "move", "id": a["id"], "dir": 2}, "dir"), ({"action": "fly", "id": a["id"]}, "action")):
            out, status = self.state.pins_post(bad)
            self.assertEqual(status, 400, bad)
            self.assertIn(why, out["error"])
        self.assertEqual(self.state.pins_post({"action": "delete", "id": 999})[1], 404)
        self.post(action="move", id=c["id"], dir=-1)
        self.post(action="rename", id=a["id"], name="Anaconda wreck")
        self.assertEqual([p["name"] for p in self.state.pins_body(1, "Sys B 7")], ["Anaconda wreck", "Spot here", "Pin 2"])
        self.post(action="delete", id=b["id"])
        self.assertEqual(len(self.state.pins_body(1, "Sys B 7")), 2)
        # every pin, for Bookmarks; kept through a journal re-read
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual([(p["short"], p["name"]) for p in self.state.pins_list()["pins"]], [("B 7", "Anaconda wreck"), ("B 7", "Spot here")])
        # "pin here" needs a position on a body
        self.j.status_json = {"live": True}
        self.assertEqual(self.state.pins_post({"action": "here"})[1], 400)

    def test_review_fixes(self):
        """Review 2026-10-20: L13, every change moves pins.v (another window notices a pin on another system's body);
        L21, a Unicode digit or a 30-digit system id is a 400 (not a 500), and a body name stays capped at 200."""
        v = self.state.pins_summary()["v"]
        self.post(action="add", system="99", sysname="Far", body="Far A 1", lat=0.0, lon=0.0)   # another system
        self.assertEqual(self.state.pins_summary()["v"], v + 1)
        for sid in ("²", "9" * 30):
            self.assertEqual(self.state.pins_post({"action": "add", "system": sid, "body": "X 1", "lat": 0, "lon": 0})[1], 400, sid)
        self.post(action="add", system="1", sysname="Sys", body="B" * 100000, lat=0.0, lon=0.0)
        self.assertEqual(max(len(p["body"]) for p in self.state.pins_list()["pins"]), 200)

    def test_guided_said_and_arrived(self):
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="Wreck", lat=0.0, lon=lon_for(12000))
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="Beacon", lat=0.0, lon=-lon_for(3000))
        s = self.state.pins_summary()
        self.assertEqual(s["counts"], {"B 7": 2})
        act = s["here"]["active"]
        self.assertEqual((act["name"], act["dist"], act["bearing"], act["turn"], act["way"]), ("Wreck", 12000, 90, 90, "on your right"))
        self.assertTrue(self.state.pin_watch())
        self.assertFalse(self.state.pin_watch())             # nothing moved: no new guidance
        self.at(0.0, lon_for(4000))                         # 8 km to go: past 10 km
        self.state.pin_watch()
        self.at(0.0, lon_for(11500))                        # 500 m: past 1 km
        self.state.pin_watch()
        self.at(0.0, lon_for(11960), flags2=1)              # 40 m on foot: arrived; the next one takes over
        self.state.pin_watch()
        self.assertEqual(self.said(), [("set", "Wreck"), ("near", "Wreck"), ("near", "Wreck"), ("arrived", "Wreck")])
        arrived = [m for m in self.j.moments if m["kind"] == "pin"][-1]
        self.assertEqual((arrived["next"]["name"], arrived["next"]["dist"]), ("Beacon", 14960))
        rows = self.state.pins_summary()["here"]["pins"]
        self.assertEqual([(r["name"], r["reached"], r["active"]) for r in rows], [("Wreck", True, False), ("Beacon", False, True)])
        # tapped: the reached one is active again; in the ship (not on foot, not in the SRV) 200 m is arrived (250 m)
        self.post(action="activate", id=rows[0]["id"])
        self.at(0.0, lon_for(11800), flags=0, flags2=0)
        self.state.pin_watch()
        self.assertEqual(self.said()[4:], [("arrived", "Wreck")])
        # on foot, 200 m is not yet (50 m): said as set instead
        self.post(action="activate", id=rows[0]["id"])
        self.at(0.0, lon_for(11800), flags=0, flags2=1)
        self.state.pin_watch()
        self.assertEqual(self.said()[5:], [("set", "Wreck")])

    def test_sweep_fixes(self):
        """The sweep of 2026-10-17: the body you are on is named with no pins yet (the legend's first 📍 needs it); after
        arriving, the next pin's way is said once (not again a tick later); a rolled-back tick says its lost line again."""
        here = self.state.pins_summary()["here"]
        self.assertEqual((here["body"], here["pins"], here["active"]), ("Sys B 7", [], None))
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="A", lat=0.0, lon=lon_for(500))
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="B", lat=0.0, lon=lon_for(1300))
        self.state.pin_watch()
        self.at(0.0, lon_for(490))
        self.state.pin_watch()
        self.state.pin_watch()                     # unmoved: B's 810 m was just said with the arrival
        self.assertEqual(self.said(), [("set", "A"), ("arrived", "A")])
        # a tick that fails after pin_watch: its moment goes back, and so does the memory of having said it
        import contextlib
        import io
        import unittest.mock
        self.db.commit()                           # (the real tick commits what pin_watch marked)
        self.at(0.0, lon_for(1250))                # 50 m from B, on foot: arrived
        n = len(self.said())
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), \
                unittest.mock.patch.object(self.state.uploads_hub, "idle", side_effect=[RuntimeError("boom"), None]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.state.tick({})
            self.assertEqual(len(self.said()), n)     # rolled back
            self.j.body_here = {"system": 1, "name": "Sys B 7", "body_id": 7}   # (the failed tick reloaded the reader)
            self.j.pos = {"id64": 1, "name": "Sys", "x": 0, "y": 0, "z": 0}
            self.at(0.0, lon_for(1250))
            self.state.tick({})
        self.assertEqual(self.said()[n:], [("arrived", "B")])     # said on the retry, not lost

    def test_pins_route(self):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                a = await c.post("/api/pins", json={"action": "add", "system": "1", "sysname": "Sys", "body": "Sys B 7", "lat": 1.5, "lon": 2.5})
                b = await c.get("/api/pins")
                return a.status, [p["name"] for p in (await b.json())["pins"]]
        self.assertEqual(asyncio.run(go()), (200, ["Pin 1"]))


if __name__ == "__main__":
    unittest.main()
