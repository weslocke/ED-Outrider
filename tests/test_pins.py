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

    def test_in_the_ship_arrival_needs_being_down(self):
        """Complete review 2026-10-30: only the distance along the ground counted, so flying over a pin at 30 km was
        "arrived" and the next pin took over. In the ship the distance through the air counts (Status.json's altitude)."""
        self.post(action="add", system="1", sysname="Sys", body="Sys B 7", name="Wreck", lat=0.0, lon=lon_for(100))
        self.state.pin_watch()
        for alt in (30000, 2000):
            self.at(0.0, lon_for(80), flags=0, flags2=0)
            self.j.status_json["alt"] = alt
            self.state.pin_watch()
            self.assertNotIn(("arrived", "Wreck"), self.said(), alt)
        self.j.status_json["alt"] = 100                     # 20 m along, 100 m up
        self.state.pin_watch()
        self.assertEqual(self.said()[-1], ("arrived", "Wreck"))

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
        # a tick that fails after pin_watch: its moment goes back, and so does the memory of having said it (a database
        # error: any other error in a step before the commit is reported and the lines still commit, review S1x-S1)
        import contextlib
        import io
        import sqlite3
        import unittest.mock
        self.db.commit()                           # (the real tick commits what pin_watch marked)
        self.at(0.0, lon_for(1250))                # 50 m from B, on foot: arrived
        n = len(self.said())
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), \
                unittest.mock.patch.object(self.state.uploads_hub, "idle", side_effect=[sqlite3.OperationalError("database is locked"), None]), \
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



class PinsExportImport(unittest.TestCase):
    """S9-S30: pins in Bookmarks' Export, and Import taking that file (CSV or JSON) through the same button."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def pins(self):
        return [(r["system"], r["sysname"], r["body"], r["name"], r["lat"], r["lon"])
                for r in self.db.execute("SELECT * FROM surface_pins ORDER BY id")]

    def test_export_then_import_gives_the_same_pins(self):
        import csv
        import io
        big = 2 ** 62 + 7   # an id64 a spreadsheet or JavaScript would round
        for name, lat in (("Wreck", 12.5), ("Guardian site", -3.25)):
            self.state.pins_post({"action": "add", "system": str(big), "sysname": "Far Sys", "body": "Far Sys A 1",
                                  "name": name, "lat": lat, "lon": 100.0})
        cols, rows = self.state.export_rows("pins")
        self.assertEqual(cols, list(ed_outrider.PIN_COLUMNS))
        before = self.pins()
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
        text = out.getvalue()
        self.assertTrue(ed_outrider.import_is_pins(text))
        self.assertFalse(ed_outrider.import_is_pins("id64,name,x,y,z,note,created_ts\n1,Sol,0,0,0,,"))
        parsed, bad, _ = ed_outrider.parse_pins(text)
        self.assertEqual(self.state.import_pins(parsed), (0, 2))     # already there
        self.db.execute("DELETE FROM surface_pins")
        self.assertEqual(self.state.import_pins(parsed), (2, 0))
        self.assertEqual(self.pins(), before)
        js = __import__("json").dumps(rows)
        self.assertTrue(ed_outrider.import_is_pins(js))
        self.assertEqual(ed_outrider.parse_pins(js)[0], parsed)

    def test_a_bad_row_is_said_not_added(self):
        rows, bad, problems = ed_outrider.parse_pins("system_id64,system,body,name,lat,lon\n5,S,S 1,A,95,10\n5,S,S 1,B,10,10\n,S,S 1,C,1,1")
        self.assertEqual((len(rows), bad), (1, 2))
        self.assertEqual(problems, ["line 2: lat or lon missing or out of range (-90 to 90, -180 to 180)",
                                    "line 4: no system_id64 (a whole number)"])


class PickupPins(unittest.TestCase):
    """Plan 2026-11-06 part 2 (2026-11-07): a live Guardian or Thargoid pickup on a body (on foot, in the SRV or landed)
    drops a pin where you stand (Journals.note_pickup_pin): source set, made reached so the guidance stays silent; one per
    site (within PICKUP_PIN_M of an earlier pickup pin of the same kind it adds to it); never in space, never from a
    catch-up or re-read, not with [defaults] pickup_pins off."""
    FOOT = ed_outrider.FLAG2_ON_FOOT | ed_outrider.FLAG2_ON_FOOT_PLANET

    def setUp(self):
        import time
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.pos = {"id64": 1, "name": "Sys", "x": 0, "y": 0, "z": 0}
        self.j.body_here = {"system": 1, "name": "Sys B 7", "body_id": 7}
        self.now = time.time()
        self.at(0.0, 0.0)

    def ts(self, ago=0):
        return ed_outrider.iso_ts(self.now - ago)

    def at(self, lat, lon, flags=0, flags2=FOOT, ago=0):
        self.j.status_json = {"live": True, "body": "Sys B 7", "lat": lat, "lon": lon, "planet_radius": R, "heading": 0,
                              "flags": flags, "flags2": flags2, "ts": self.ts(ago)}

    def material(self, name, ago=0):
        self.j.handle({"timestamp": self.ts(ago), "event": "MaterialCollected", "Category": "Manufactured", "Name": name,
                       "Count": 1})

    def cargo(self, typ, ago=0):
        self.j.handle({"timestamp": self.ts(ago), "event": "CollectCargo", "Type": typ, "Stolen": False})

    def pins(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM surface_pins ORDER BY id")]

    def test_a_pickup_on_foot_makes_one_pin(self):
        v = self.state.pins_summary()["v"]
        self.material("guardian_powercell")
        (p,) = self.pins()
        self.assertEqual((p["system"], p["sysname"], p["body"], p["name"], p["lat"], p["lon"], p["source"], p["pickups"]),
                         (1, "Sys", "Sys B 7", "Guardian site (pickup)", 0.0, 0.0, "guardian", 1))
        self.assertIsNotNone(p["reached_ts"])                    # you are at it: the guidance has nothing to say
        self.assertGreater(self.state.pins_summary()["v"], v)    # every window asks for the pins again
        self.state.pin_watch()
        self.assertEqual([m for m in self.j.moments if m["kind"] == "pin"], [])   # silent
        self.assertEqual([x["name"] for x in self.state.pins_list()["pins"]], ["Guardian site (pickup)"])

    def test_a_second_pickup_nearby_adds_to_it(self):
        self.material("guardian_sentinel_wreckagecomponents")
        self.at(0.0, lon_for(1500))
        self.material("ancientbiologicaldata")                   # an obelisk's data, 1.5 km on: the same site
        self.cargo("ancientrelic")
        (p,) = self.pins()
        self.assertEqual((p["name"], p["pickups"], p["lat"], p["lon"]), ("Guardian site (pickup) ×3", 3, 0.0, 0.0))
        # a name you gave it is kept, the count still goes up
        self.state.pins_post({"action": "rename", "id": p["id"], "name": "Ruins"})
        self.material("guardian_powerconduit")
        self.assertEqual([(x["name"], x["pickups"]) for x in self.pins()], [("Ruins", 4)])
        # a Thargoid pickup at the same spot is another kind: a pin of its own
        self.material("unknownenergysource")                     # Sensor Fragment
        self.assertEqual([(x["name"], x["source"]) for x in self.pins()],
                         [("Ruins", "guardian"), ("Thargoid site (pickup)", "thargoid")])

    def test_one_over_2_km_makes_a_second(self):
        self.material("tg_wreckagecomponents")
        self.at(0.0, lon_for(2500))
        self.material("unknowncarapace")
        self.assertEqual([(x["name"], x["pickups"], x["source"]) for x in self.pins()],
                         [("Thargoid site (pickup)", 1, "thargoid"), ("Thargoid site (pickup)", 1, "thargoid")])
        self.assertEqual(sorted(x["ord"] for x in self.pins()), [1, 2])

    def test_in_the_srv_and_landed_too(self):
        self.at(0.0, 0.0, flags=ed_outrider.FLAG_IN_SRV, flags2=0)
        self.cargo("$UnknownArtifact2_name;")                    # a Thargoid Probe scooped by the SRV
        self.at(0.0, lon_for(5000), flags=ed_outrider.FLAG_LANDED, flags2=0)
        self.cargo("ancientorb")
        self.assertEqual([x["source"] for x in self.pins()], ["thargoid", "guardian"])

    def test_none_in_space_or_flying(self):
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE, "flags2": 0, "ts": self.ts()}
        self.material("tg_causticshard")                         # after an AX fight: no body
        self.at(0.0, 0.0, flags=0, flags2=0)                     # in the ship over the body, no altitude known
        self.material("unknowntechnologycomponents")
        self.j.status_json["alt"] = 25000                        # in the ship high over the body (an AX fight there)
        self.cargo("unknownartifact")
        self.j.status_json.update(alt=300, flags=ed_outrider.FLAG_SUPERCRUISE)   # orbital cruise, however low
        self.cargo("unknownartifact")
        self.assertEqual(self.pins(), [])

    def test_hovering_low_in_the_ship(self):
        """Sensors and probes are often scooped with the ship hovering over the site: under PICKUP_PIN_HOVER_M it counts."""
        self.at(0.0, 0.0, flags=0, flags2=0)
        self.j.status_json["alt"] = 40
        self.cargo("unknownartifact")
        self.assertEqual([(p["name"], p["source"]) for p in self.pins()], [("Thargoid site (pickup)", "thargoid")])

    def test_none_from_a_reread_or_a_stale_position(self):
        self.material("guardian_powercell", ago=3600)            # an old line: a re-read or a catch-up
        self.j.importing = True                                  # the start-up import, even of a line just written
        self.material("guardian_powercell")
        self.j.importing = False
        self.at(0.0, 0.0, ago=120)                               # the position is two minutes older than the line
        self.material("guardian_powercell")
        self.j.status_json["live"] = False                       # the game quit
        self.material("guardian_powercell")
        self.at(0.0, 0.0)
        self.material("iron")                                    # not a Guardian or Thargoid pickup
        self.cargo("gold")
        self.assertEqual(self.pins(), [])

    def test_the_setting_off_makes_none(self):
        import unittest.mock
        with unittest.mock.patch.object(ed_outrider, "PICKUP_PINS", False):
            self.material("guardian_powercell")
            self.cargo("ancientrelic")
        self.assertEqual(self.pins(), [])

    def test_kinds(self):
        kind = ed_outrider.Journals.pickup_kind
        for name, want in (("guardian_techcomponent", "guardian"), ("Guardian_PowerCell", "guardian"),
                           ("ancienttechnologicaldata", "guardian"), ("tg_structuraldata", "thargoid"),
                           ("unknownorganiccircuitry", "thargoid"), ("unknownenergycell", "thargoid"), ("iron", None),
                           ("", None)):
            self.assertEqual(kind("MaterialCollected", {"Name": name}), want, name)
        for typ, want in (("ancientcasket", "guardian"), ("ancienttablet", "guardian"), ("ancienttotem", "guardian"),
                          ("ancienturn", "guardian"), ("unknownartifact", "thargoid"), ("unknownartifact3", "thargoid"),
                          ("unknownbiologicalmatter", "thargoid"), ("unknownresin", "thargoid"),
                          ("unknowntechnologysamples", "thargoid"), ("metaalloys", "thargoid"),
                          ("usscargoancientartefact", None), ("ancientrelictg", None), ("gold", None), (None, None)):
            self.assertEqual(kind("CollectCargo", {"Type": typ}), want, typ)


class PickupPinsMigration(unittest.TestCase):
    def test_an_old_table_gets_the_columns(self):
        """A database from before the pickup pins: surface_pins without source and pickups gets both, its pins kept as
        yours (source NULL)."""
        import os
        import sqlite3
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "old.sqlite")
        old = sqlite3.connect(path)
        old.executescript("""CREATE TABLE surface_pins (
            id INTEGER PRIMARY KEY, system INTEGER NOT NULL, body TEXT NOT NULL, sysname TEXT, name TEXT NOT NULL,
            lat REAL NOT NULL, lon REAL NOT NULL, ord INTEGER NOT NULL DEFAULT 0, reached_ts TEXT, created_ts TEXT);
            INSERT INTO surface_pins (system, body, sysname, name, lat, lon, ord) VALUES (1, 'Sys B 7', 'Sys', 'Wreck', 1, 2, 1);""")
        old.commit()
        old.close()
        db = ed_outrider.open_db(path)
        self.addCleanup(db.close)
        cols = {r["name"] for r in db.execute("PRAGMA table_info(surface_pins)")}
        self.assertTrue({"source", "pickups"} <= cols)
        self.assertEqual([tuple(r) for r in db.execute("SELECT name, source, pickups FROM surface_pins")], [("Wreck", None, None)])


class PickupPinsSetting(unittest.TestCase):
    """[defaults] pickup_pins: on by default, in the config file and its example, homed in Settings -> Surface map
    (data-find), written by the page's tick and used at once (LIVE_CONFIG)."""

    def test_default_and_round_trip(self):
        import argparse
        import os
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertIs(st["pickup_pins"], True)
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["defaults"]["pickup_pins"], True)
        self.assertIs(ed_outrider.settings_from({"defaults": {"pickup_pins": False}}, args, None, ([], []))["pickup_pins"], False)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "ed_outrider.toml.example"), encoding="utf-8") as f:
            self.assertIn("# pickup_pins = true", f.read())
        with open(os.path.join(root, "static", "page.html"), encoding="utf-8") as f:
            self.assertIn('data-find="defaults.pickup_pins"', f.read())

    def test_saved_and_used_at_once(self):
        import os
        import tempfile
        import tomllib
        from aiohttp.test_utils import TestClient, TestServer
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "ed_outrider.toml")
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ed_outrider.toml.example"),
                  encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        state.config_path = path
        keep = ed_outrider.PICKUP_PINS
        self.addCleanup(lambda: setattr(ed_outrider, "PICKUP_PINS", keep))
        self.assertIn(("defaults", "pickup_pins"), ed_outrider.State.LIVE_CONFIG)

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                r = await c.post("/api/config", json={"defaults": {"pickup_pins": False}})
                return r.status, await r.json()
        status, answer = asyncio.run(go())
        self.assertEqual((status, answer["live"], answer["restart"]), (200, ["defaults.pickup_pins"], False))
        self.assertIs(ed_outrider.PICKUP_PINS, False)
        self.assertIs(state.payload()["defaults"]["pickup_pins"], False)
        with open(path, encoding="utf-8") as f:
            self.assertIs(tomllib.loads(f.read())["defaults"]["pickup_pins"], False)


if __name__ == "__main__":
    unittest.main()

