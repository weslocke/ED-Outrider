"""Unit tests: EDDN messages (outrider/eddn.py) checked against EDDN's own schemas (tests/fixtures/eddn, its live branch),
the sender against a fake session, and a journal line all the way to the outbox. Nothing is sent anywhere.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import gzip
import json
import os
import shutil
import tempfile
import time
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.eddn as E  # noqa: E402
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "eddn")
try:
    import jsonschema
except ImportError:   # requirements-dev.txt has it; without it only the schema checks are skipped
    jsonschema = None


def valid(envelope, schema_file):
    """Raise unless `envelope` passes EDDN's schema (draft-04, as EDDN's gateway validates)."""
    with open(os.path.join(FIX, schema_file), encoding="utf-8-sig") as f:   # some of EDDN's files start with a BOM
        schema = json.load(f)
    jsonschema.Draft4Validator(schema).validate(envelope)


def session(horizons=True, odyssey=True):
    s = U.Session()
    s.feed({"event": "Fileheader", "timestamp": "2026-10-08T10:00:00Z", "gameversion": "4.2.0.100", "build": "r312345/r0 "},
           "Journal.2026-10-08T100000.01.log")
    lg = {"event": "LoadGame", "timestamp": "2026-10-08T10:00:01Z", "Commander": "Briadin", "FID": "F1"}
    if horizons is not None:
        lg["Horizons"] = horizons
    if odyssey is not None:
        lg["Odyssey"] = odyssey
    s.feed(lg)
    return s


FSDJUMP = {"timestamp": "2026-10-08T10:05:00Z", "event": "FSDJump", "Taxi": False, "Multicrew": False,
           "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": 18264118102193, "StarPos": [-4177.09, -1.0, 3324.53],
           "SystemAllegiance": "", "SystemEconomy": "$economy_None;", "SystemEconomy_Localised": "None",
           "SystemSecondEconomy": "$economy_None;", "SystemSecondEconomy_Localised": "None", "SystemGovernment": "$government_None;",
           "SystemGovernment_Localised": "None", "SystemSecurity": "$GAlAXY_MAP_INFO_state_anarchy;",
           "SystemSecurity_Localised": "Anarchy", "Population": 0, "Body": "Smojooe AR-E b25-8", "BodyID": 0, "BodyType": "Star",
           "JumpDist": 43.12, "FuelUsed": 3.2, "FuelLevel": 28.1, "BoostUsed": 4, "Wanted": False,
           "Factions": [{"Name": "Some Faction", "FactionState": "None", "Government": "Democracy", "Influence": 0.5,
                         "Allegiance": "Independent", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
                         "MyReputation": 12.5, "HomeSystem": True, "SquadronFaction": False, "HappiestSystem": False}]}

SCAN = {"timestamp": "2026-10-08T10:06:00Z", "event": "Scan", "ScanType": "Detailed", "BodyName": "Smojooe AR-E b25-8 A 1",
        "BodyID": 5, "Parents": [{"Star": 1}, {"Null": 0}], "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": 18264118102193,
        "DistanceFromArrivalLS": 450.2, "TidalLock": False, "TerraformState": "", "PlanetClass": "Rocky body",
        "Atmosphere": "", "AtmosphereType": "None", "Volcanism": "", "MassEM": 0.02, "Radius": 1500000.0,
        "SurfaceGravity": 1.2, "SurfaceTemperature": 180.0, "SurfacePressure": 0.0, "Landable": True,
        "Materials": [{"Name": "iron", "Name_Localised": "Iron", "Percent": 20.1}, {"Name": "nickel", "Percent": 15.2}],
        "Composition": {"Ice": 0.0, "Rock": 0.9, "Metal": 0.1}, "SemiMajorAxis": 1.0e10, "Eccentricity": 0.01,
        "OrbitalInclination": 0.1, "Periapsis": 10.0, "OrbitalPeriod": 1.0e6, "AscendingNode": 1.0, "MeanAnomaly": 2.0,
        "RotationPeriod": 1.0e5, "AxialTilt": 0.1, "WasDiscovered": False, "WasMapped": False, "WasFootfalled": False}


@unittest.skipUnless(jsonschema, "jsonschema is not installed (requirements-dev.txt)")
class JournalSchema(unittest.TestCase):
    """journal/1: the personal fields gone, the cross-check, the flags, every message valid for EDDN."""

    def test_fsdjump(self):
        s = session()
        s.feed(FSDJUMP)
        [(name, env)] = E.build(FSDJUMP, s, "2026.10.18")
        valid(env, "journal-v1.0.json")
        m = env["message"]
        self.assertEqual(name, "journal")
        self.assertEqual(env["$schemaRef"], "https://eddn.edcd.io/schemas/journal/1")
        self.assertEqual(env["header"], {"uploaderID": "Briadin", "softwareName": "ED Outrider", "softwareVersion": "2026.10.18",
                                         "gameversion": "4.2.0.100", "gamebuild": "r312345/r0 "})
        for k in ("JumpDist", "FuelUsed", "FuelLevel", "BoostUsed", "Wanted", "SystemEconomy_Localised"):
            self.assertNotIn(k, m)
        self.assertEqual(set(m["Factions"][0]) & {"MyReputation", "HomeSystem", "SquadronFaction", "HappiestSystem", "Happiness_Localised"}, set())
        self.assertEqual((m["horizons"], m["odyssey"]), (True, True))
        self.assertEqual(E.build(FSDJUMP, s, "2026.10.18", test=True)[0][1]["$schemaRef"], "https://eddn.edcd.io/schemas/journal/1/test")

    def test_scan_cross_check(self):
        s = session(odyssey=None)                                # LoadGame without an Odyssey key: left out
        s.feed(FSDJUMP)
        [(_, env)] = E.build(SCAN, s, "v")
        valid(env, "journal-v1.0.json")
        m = env["message"]
        self.assertEqual(m["StarPos"], [-4177.09, -1.0, 3324.53])               # added from the jump
        self.assertEqual(m["Materials"][0], {"Name": "iron", "Percent": 20.1})  # _Localised gone, inside lists too
        self.assertNotIn("odyssey", m)
        self.assertEqual(E.build(dict(SCAN, SystemAddress=999), s, "v"), [])  # another system: never sent
        s2 = session()
        self.assertEqual(E.build(SCAN, s2, "v"), [])                          # no position yet

    def test_planetary_dock_names_its_body(self):
        """A Docked at a station on a planet's surface carries the body approached (Body, BodyType "Planet"), as EDMC
        adds it; an orbital station's never does, and nor does one with no body approached."""
        s = session()
        s.feed(FSDJUMP)
        dock = {"timestamp": "2026-10-08T10:20:00Z", "event": "Docked", "StationName": "Thorn Constructions",
                "StationType": "CraterOutpost", "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": 18264118102193,
                "MarketID": 3700000001}
        [(_, env)] = E.build(dock, s, "v")
        self.assertNotIn("Body", env["message"])                                  # nothing approached: nothing guessed
        s.feed({"timestamp": "2026-10-08T10:10:00Z", "event": "ApproachBody", "StarSystem": "Smojooe AR-E b25-8",
                "SystemAddress": 18264118102193, "Body": "Smojooe AR-E b25-8 A 1", "BodyID": 5})
        [(_, env)] = E.build(dock, s, "v")
        valid(env, "journal-v1.0.json")
        self.assertEqual((env["message"]["Body"], env["message"]["BodyType"]), ("Smojooe AR-E b25-8 A 1", "Planet"))
        [(_, env)] = E.build(dict(dock, StationType="Coriolis"), s, "v")
        self.assertNotIn("Body", env["message"])                                  # an orbital station: no body
        s.feed({"timestamp": "2026-10-08T10:30:00Z", "event": "LeaveBody", "StarSystem": "Smojooe AR-E b25-8",
                "SystemAddress": 18264118102193, "Body": "Smojooe AR-E b25-8 A 1", "BodyID": 5})
        [(_, env)] = E.build(dock, s, "v")
        self.assertNotIn("Body", env["message"])

    def test_saa_signals_and_docked_and_location(self):
        s = session()
        s.feed(FSDJUMP)
        saa = {"timestamp": "2026-10-08T10:07:00Z", "event": "SAASignalsFound", "BodyName": "Smojooe AR-E b25-8 A 1",
               "SystemAddress": 18264118102193, "BodyID": 5,
               "Signals": [{"Type": "$SAA_SignalType_Biological;", "Type_Localised": "Biological", "Count": 2}],
               "Genuses": [{"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Genus_Localised": "Bacterium"}]}
        [(_, env)] = E.build(saa, s, "v")
        valid(env, "journal-v1.0.json")
        self.assertEqual(env["message"]["StarSystem"], "Smojooe AR-E b25-8")
        loc = {"timestamp": "2026-10-08T11:00:00Z", "event": "Location", "Docked": True, "StationName": "OUT OF THE BLUE",
               "StationType": "FleetCarrier", "MarketID": 3700251648, "StarSystem": "Smojooe AR-E b25-8",
               "SystemAddress": 18264118102193, "StarPos": [-4177.09, -1.0, 3324.53], "Latitude": 1.0, "Longitude": 2.0,
               "Body": "Smojooe AR-E b25-8", "BodyID": 0, "BodyType": "Star", "Population": 0}
        s.feed(loc)
        [(_, env)] = E.build(loc, s, "v")
        valid(env, "journal-v1.0.json")
        self.assertNotIn("Latitude", env["message"])
        docked = {"timestamp": "2026-10-08T11:05:00Z", "event": "Docked", "StationName": "OUT OF THE BLUE",
                  "StationType": "FleetCarrier", "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": 18264118102193,
                  "MarketID": 3700251648, "StationFaction": {"Name": "FleetCarrier"}, "StationGovernment": "$government_Carrier;",
                  "StationGovernment_Localised": "Private Ownership", "StationServices": ["dock", "autodock"],
                  "StationEconomy": "$economy_Carrier;", "StationEconomy_Localised": "Private Enterprise",
                  "StationEconomies": [{"Name": "$economy_Carrier;", "Name_Localised": "Private Enterprise", "Proportion": 1.0}],
                  "DistFromStarLS": 0.0, "LandingPads": {"Small": 4, "Medium": 4, "Large": 8}, "Wanted": False,
                  "ActiveFine": False, "CockpitBreach": False}
        [(_, env)] = E.build(docked, s, "v")
        valid(env, "journal-v1.0.json")
        self.assertEqual(set(env["message"]) & {"Wanted", "ActiveFine", "CockpitBreach"}, set())

    def test_other_events_make_nothing(self):
        s = session()
        s.feed(FSDJUMP)
        self.assertEqual(E.build({"event": "Music", "timestamp": "2026-10-08T10:00:00Z", "MusicTrack": "x"}, s, "v"), [])


@unittest.skipUnless(jsonschema, "jsonschema is not installed (requirements-dev.txt)")
class FssFamily(unittest.TestCase):
    """Part C: fssdiscoveryscan, fssallbodiesfound, fssbodysignals, scanbarycentre, navbeaconscan: only what each
    schema lists, the place from the cross-check."""

    def setUp(self):
        self.s = session()
        self.s.feed(FSDJUMP)
        self.addr = FSDJUMP["SystemAddress"]

    def one(self, ev, schema_file):
        [(name, env)] = E.build(ev, self.s, "v")
        valid(env, schema_file)
        return name, env["message"]

    def test_each(self):
        t = "2026-10-08T10:06:00Z"
        name, m = self.one({"timestamp": t, "event": "FSSDiscoveryScan", "Progress": 0.42, "BodyCount": 12, "NonBodyCount": 3,
                            "SystemName": "Smojooe AR-E b25-8", "SystemAddress": self.addr}, "fssdiscoveryscan-v1.0.json")
        self.assertEqual((name, "Progress" in m, m["StarPos"]), ("fssdiscoveryscan", False, [-4177.09, -1.0, 3324.53]))
        self.assertEqual(self.one({"timestamp": t, "event": "FSSAllBodiesFound", "SystemName": "Smojooe AR-E b25-8",
                                   "SystemAddress": self.addr, "Count": 12}, "fssallbodiesfound-v1.0.json")[0], "fssallbodiesfound")
        name, m = self.one({"timestamp": t, "event": "FSSBodySignals", "BodyName": "Smojooe AR-E b25-8 A 1", "BodyID": 5,
                            "SystemAddress": self.addr, "Signals": [{"Type": "$SAA_SignalType_Biological;",
                                                                    "Type_Localised": "Biological", "Count": 2}]}, "fssbodysignals-v1.0.json")
        self.assertEqual((m["StarSystem"], m["Signals"]), ("Smojooe AR-E b25-8", [{"Type": "$SAA_SignalType_Biological;", "Count": 2}]))
        self.one({"timestamp": t, "event": "ScanBaryCentre", "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": self.addr,
                  "BodyID": 2, "SemiMajorAxis": 1.0e9, "Eccentricity": 0.1, "OrbitalInclination": 1.0, "Periapsis": 10.0,
                  "OrbitalPeriod": 1.0e5, "AscendingNode": 2.0, "MeanAnomaly": 3.0}, "scanbarycentre-v1.0.json")
        name, m = self.one({"timestamp": t, "event": "NavBeaconScan", "SystemAddress": self.addr, "NumBodies": 7}, "navbeaconscan-v1.0.json")
        self.assertEqual((name, m["StarSystem"]), ("navbeaconscan", "Smojooe AR-E b25-8"))

    def test_cross_check(self):
        ev = {"timestamp": "2026-10-08T10:06:00Z", "event": "FSSAllBodiesFound", "SystemName": "Elsewhere", "SystemAddress": 1, "Count": 3}
        self.assertEqual(E.build(ev, self.s, "v"), [])


@unittest.skipUnless(jsonschema, "jsonschema is not installed (requirements-dev.txt)")
class RouteCodexSettlement(unittest.TestCase):
    """Part D: navroute from NavRoute.json (only the file this event wrote), codexentry (the body from Status.json),
    approachsettlement."""

    def setUp(self):
        self.s = session()
        self.s.feed(FSDJUMP)
        self.addr = FSDJUMP["SystemAddress"]
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.s.dir = self.dir

    def navfile(self, ts, route=True):
        with open(os.path.join(self.dir, "NavRoute.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": ts, "event": "NavRoute", "Route": [
                {"StarSystem": "Smojooe AR-E b25-8", "SystemAddress": self.addr, "StarPos": [-4177.09, -1.0, 3324.53], "StarClass": "M"},
                {"StarSystem": "Next", "SystemAddress": 22, "StarPos": [-4100.0, 0.0, 3300.0], "StarClass": "K"}] if route else []}, f)

    def test_navroute_waits_for_its_file(self):
        self.navfile("2026-10-08T09:00:00Z")                              # an older route's file
        self.assertEqual(E.build({"timestamp": "2026-10-08T10:10:00Z", "event": "NavRoute"}, self.s, "v"), [])
        self.navfile("2026-10-08T10:10:01Z")                              # written now (NFS: a line later)
        [(name, env)] = E.build({"timestamp": "2026-10-08T10:10:02Z", "event": "Music", "MusicTrack": "x"}, self.s, "v")
        valid(env, "navroute-v1.0.json")
        self.assertEqual((name, [h["StarSystem"] for h in env["message"]["Route"]]), ("navroute", ["Smojooe AR-E b25-8", "Next"]))
        self.assertEqual(E.build({"timestamp": "2026-10-08T10:10:03Z", "event": "Music"}, self.s, "v"), [])   # once
        self.navfile("2026-10-08T09:00:00Z")
        E.build({"timestamp": "2026-10-08T11:00:00Z", "event": "NavRoute"}, self.s, "v")
        for i in range(E.NAVROUTE_TRIES):                                 # never the right file: given up
            E.build({"timestamp": "2026-10-08T11:00:01Z", "event": "Music"}, self.s, "v")
        self.assertNotIn("navroute", self.s.pending)
        E.build({"timestamp": "2026-10-08T12:00:00Z", "event": "NavRoute"}, self.s, "v")
        self.assertEqual(E.build({"timestamp": "2026-10-08T12:00:01Z", "event": "NavRouteClear"}, self.s, "v"), [])
        self.assertNotIn("navroute", self.s.pending)

    def test_codex(self):
        ev = {"timestamp": "2026-10-08T10:20:00Z", "event": "CodexEntry", "EntryID": 2310101, "Name": "$Codex_Ent_Tussocks_01_A_Name;",
              "Name_Localised": "Tussock Pennata - Teal", "SubCategory": "$Codex_SubCategory_Organic_Structures;",
              "SubCategory_Localised": "Organic structures", "Category": "$Codex_Category_Biology;", "Category_Localised": "Biological",
              "Region": "$Codex_RegionName_18;", "Region_Localised": "Inner Orion Spur", "System": "Smojooe AR-E b25-8",
              "SystemAddress": self.addr, "Latitude": 1.5, "Longitude": 2.5, "IsNewEntry": True, "VoucherAmount": 50000}
        self.s.feed({"event": "ApproachBody", "timestamp": "2026-10-08T10:15:00Z", "Body": "Smojooe AR-E b25-8 A 1", "BodyID": 5})
        self.s.status_body = "Smojooe AR-E b25-8 A 1"
        [(name, env)] = E.build(ev, self.s, "v")
        valid(env, "codexentry-v1.0.json")
        m = env["message"]
        self.assertEqual((name, m["BodyName"], m["BodyID"], "IsNewEntry" in m, "Name_Localised" in m), ("codexentry", "Smojooe AR-E b25-8 A 1", 5, False, False))
        self.s.status_body = "Smojooe AR-E b25-8 A 2"                    # a close binary: the name, not the other's id
        m = E.build(ev, self.s, "v")[0][1]["message"]
        self.assertEqual((m["BodyName"], "BodyID" in m), ("Smojooe AR-E b25-8 A 2", False))
        self.s.status_body = None
        self.assertNotIn("BodyName", E.build(ev, self.s, "v")[0][1]["message"])
        self.assertEqual(E.build(dict(ev, Region=""), self.s, "v"), [])   # an empty required name: not sent

    def test_scan_organic(self):
        """scanorganic/1 (the author, 2026-10-11): Log and Sample, never Analyse; Body renamed BodyID; BodyName only for the
        body approached with that id; Latitude/Longitude only from a live Status.json on that body, read at the scan."""
        body = "Smojooe AR-E b25-8 A 1"
        ev = {"timestamp": "2026-10-08T10:40:00Z", "event": "ScanOrganic", "ScanType": "Log",
              "Genus": "$Codex_Ent_Fungoids_Genus_Name;", "Genus_Localised": "Fungoida",
              "Species": "$Codex_Ent_Fungoids_01_Name;", "Species_Localised": "Fungoida Setisis",
              "Variant": "$Codex_Ent_Fungoids_01_Polonium_Name;", "Variant_Localised": "Fungoida Setisis - Teal",
              "SystemAddress": self.addr, "Body": 5}
        [(name, env)] = E.build(ev, self.s, "v")                                  # nothing approached: no name, no place
        valid(env, "scanorganic-v1.0.json")
        m = env["message"]
        self.assertEqual((name, m["StarSystem"], m["BodyID"], "Body" in m, "BodyName" in m, "Latitude" in m),
                         ("scanorganic", "Smojooe AR-E b25-8", 5, False, False, False))
        self.assertFalse(any(k.endswith("_Localised") for k in m))
        self.s.feed({"event": "ApproachBody", "timestamp": "2026-10-08T10:30:00Z", "Body": body, "BodyID": 5})
        self.s.status_pos = (12.5, -40.25, body, "2026-10-08T10:39:58Z")          # read 2 s before the scan
        m = E.build(ev, self.s, "v")[0][1]["message"]
        valid(E.build(ev, self.s, "v")[0][1], "scanorganic-v1.0.json")
        self.assertEqual((m["BodyName"], m["Latitude"], m["Longitude"]), (body, 12.5, -40.25))
        late = dict(ev, timestamp="2026-10-08T12:00:00Z")                         # a journal caught up later: no place
        self.assertNotIn("Latitude", E.build(late, self.s, "v")[0][1]["message"])
        self.s.status_pos = (12.5, -40.25, body, "2026-10-08T10:40:30Z")          # 30 s after: you have moved on
        self.assertNotIn("Latitude", E.build(ev, self.s, "v")[0][1]["message"])
        self.s.status_pos = (12.5, -40.25, "Smojooe AR-E b25-8 A 2", "2026-10-08T10:40:00Z")   # another body
        self.assertNotIn("Latitude", E.build(ev, self.s, "v")[0][1]["message"])
        other = E.build(dict(ev, Body=6), self.s, "v")[0][1]["message"]           # not the body approached
        self.assertEqual(("BodyName" in other, other["BodyID"]), (False, 6))
        self.assertNotIn("Variant", E.build({k: v for k, v in ev.items() if k != "Variant"}, self.s, "v")[0][1]["message"])
        self.assertEqual(E.build(dict(ev, ScanType="Sample"), self.s, "v")[0][0], "scanorganic")
        self.assertEqual(E.build(dict(ev, ScanType="Analyse"), self.s, "v"), [])   # can come anywhere: never sent
        self.assertEqual(E.build(dict(ev, SystemAddress=1), self.s, "v"), [])      # the cross-check

    def test_settlement(self):
        ev = {"timestamp": "2026-10-08T10:30:00Z", "event": "ApproachSettlement", "Name": "Hamilton Base", "MarketID": 3820000000,
              "StationFaction": {"Name": "Them", "FactionState": "Boom", "Happiness": "x"}, "StationGovernment": "$government_Corporate;",
              "StationGovernment_Localised": "Corporate", "StationEconomies": [{"Name": "$economy_Industrial;", "Name_Localised": "Industrial", "Proportion": 1.0}],
              "SystemAddress": self.addr, "BodyID": 5, "BodyName": "Smojooe AR-E b25-8 A 1", "Latitude": 10.0, "Longitude": 20.0}
        [(name, env)] = E.build(ev, self.s, "v")
        valid(env, "approachsettlement-v1.0.json")
        self.assertEqual((name, env["message"]["MarketID"], env["message"]["StationFaction"]), ("approachsettlement", 3820000000, {"Name": "Them", "FactionState": "Boom"}))
        self.assertEqual(E.build({k: v for k, v in ev.items() if k != "Latitude"}, self.s, "v"), [])   # a login at a port


@unittest.skipUnless(jsonschema, "jsonschema is not installed (requirements-dev.txt)")
class Signals(unittest.TestCase):
    """Part E: a run of FSSSignalDiscovered lines, sent as one message when the next other line comes."""

    def sig(self, name, addr, **kw):
        return dict({"timestamp": "2026-10-08T10:05:00Z", "event": "FSSSignalDiscovered", "SystemAddress": addr, "SignalName": name,
                     "SignalName_Localised": name}, **kw)

    def test_odyssey_order(self):
        s = session()
        s.feed(dict(FSDJUMP, SystemAddress=1, StarSystem="Before"))
        addr = FSDJUMP["SystemAddress"]
        lines = [self.sig("OUT OF THE BLUE G0X-85Z", addr, IsStation=True, SignalType="FleetCarrier"),
                 self.sig("$USS_Type_MissionTarget;", addr, USSType="$USS_Type_MissionTarget;"),
                 self.sig("Distress call", addr, USSType="$USS_Type_DistressSignal;", TimeRemaining=600, ThreatLevel=0)]
        for ev in lines:                                         # written before the jump: held back
            self.assertEqual(E.build(ev, s, "v"), [])
        s.feed(FSDJUMP)                                          # the hub feeds the session first, then builds
        out = E.build(FSDJUMP, s, "v")
        self.assertEqual([n for n, _ in out], ["fsssignaldiscovered", "journal"])
        env = out[0][1]
        valid(env, "fsssignaldiscovered-v1.0.json")
        m = env["message"]
        self.assertEqual([x["SignalName"] for x in m["signals"]], ["OUT OF THE BLUE G0X-85Z", "Distress call"])   # no mission target
        self.assertNotIn("TimeRemaining", m["signals"][1])
        self.assertEqual((m["StarSystem"], m["timestamp"]), ("Smojooe AR-E b25-8", "2026-10-08T10:05:00Z"))

    def test_horizons_order_and_another_system(self):
        s = session()
        s.feed(FSDJUMP)
        addr = FSDJUMP["SystemAddress"]
        self.assertEqual(E.build(self.sig("A station", addr), s, "v"), [])
        self.assertEqual(E.build(self.sig("Elsewhere", 999), s, "v"), [])
        out = E.build({"timestamp": "2026-10-08T10:06:00Z", "event": "Music", "MusicTrack": "x"}, s, "v")
        self.assertEqual([x["SignalName"] for x in out[0][1]["message"]["signals"]], ["A station"])   # the stray one dropped
        E.build(self.sig("Far", 999), s, "v")                    # a batch whose first is another system's: all dropped
        self.assertEqual(E.build({"timestamp": "2026-10-08T10:07:00Z", "event": "Music"}, s, "v"), [])


    def test_left_over_batches_are_not_sent_late(self):
        """What EDDN waited on while another uploader took over is dropped (quiet); one that waited on the tick past
        SIGNAL_MAX_S is dropped; a batch whose next line comes much later in a catch-up still goes (no tick there)."""
        s = session()
        s.feed(FSDJUMP)
        addr = FSDJUMP["SystemAddress"]
        E.build(self.sig("Old", addr), s, "v")
        E.quiet({"timestamp": "2026-10-08T10:06:00Z", "event": "Music"}, s)
        self.assertNotIn("signals", s.pending)
        s.source, s.now = "J:1", 100.0
        E.build(self.sig("Stuck", addr), s, "v")
        s.now = 100.0 + E.SIGNAL_MAX_S + 1                            # EDDN stopped building, then came back
        s.feed(dict(FSDJUMP, SystemAddress=1, StarSystem="Away"))     # (not located there now: idle would wait)
        self.assertEqual(E.idle(s, "v"), [])
        self.assertNotIn("signals", s.pending)
        s.feed(FSDJUMP)
        E.build(self.sig("Catch-up", addr, timestamp="2026-10-08T10:05:00Z"), s, "v")
        out = E.build({"timestamp": "2026-10-08T12:05:00Z", "event": "Music"}, s, "v")
        self.assertEqual([n for n, _ in out], ["fsssignaldiscovered"])

    def test_quiet_batch_goes_on_the_tick(self):
        """A batch with no line after it goes SIGNAL_QUIET_S after its last signal (2026-10-09), under
        the first signal's line; one for a system you are not in yet (Odyssey: just before the jump) waits."""
        s = session()
        s.feed(FSDJUMP)
        addr = FSDJUMP["SystemAddress"]
        s.source, s.now = "J.log:500", 1000.0
        self.assertEqual(E.build(self.sig("A station", addr), s, "v"), [])
        s.source, s.now = "J.log:600", 1001.0
        E.build(self.sig("Another", addr), s, "v")
        s.now = 1003.5
        self.assertEqual(E.idle(s, "v"), [])                         # 2.5 s after the last one: still waiting
        s.now = 1004.0
        [(name, env, origin)] = E.idle(s, "v")
        self.assertEqual((name, origin, [x["SignalName"] for x in env["message"]["signals"]]),
                         ("fsssignaldiscovered", "J.log:500", ["A station", "Another"]))
        self.assertNotIn("signals", s.pending)
        s.now = 2000.0
        E.build(self.sig("Next system's", 4242), s, "v")              # before the jump that takes you there
        s.now = 2010.0
        self.assertEqual(E.idle(s, "v"), [])                          # not in that system: it waits for the jump line
        self.assertIn("signals", s.pending)


@unittest.skipUnless(jsonschema, "jsonschema is not installed (requirements-dev.txt)")
class StationData(unittest.TestCase):
    """Part F: commodity/3, outfitting/2, shipyard/2, fcmaterials_journal/1 from the journal folder's files (only the
    file the event wrote: its time and MarketID), each sent only when changed; dockinggranted / dockingdenied."""

    def setUp(self):
        self.s = session()
        self.s.feed(FSDJUMP)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.s.dir = self.dir
        self.t = "2026-10-08T10:40:00Z"

    def file(self, name, body):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(dict({"timestamp": self.t, "MarketID": 128, "StationName": "Abraham Lincoln", "StarSystem": "Sol"}, **body), f)

    def ev(self, name, **kw):
        return dict({"timestamp": self.t, "event": name, "MarketID": 128, "StationName": "Abraham Lincoln", "StarSystem": "Sol"}, **kw)

    def test_market(self):
        self.file("Market.json", {"event": "Market", "StationType": "Orbis", "Items": [
            {"id": 1, "Name": "$gold_name;", "Name_Localised": "Gold", "Category": "$MARKET_category_metals;", "BuyPrice": 9000,
             "SellPrice": 8800, "MeanPrice": 9100, "StockBracket": 2, "DemandBracket": 0, "Stock": 500, "Demand": 0,
             "Consumer": False, "Producer": True, "Rare": False},
            {"id": 2, "Name": "$drones_name;", "Category": "$MARKET_category_nonmarketable;", "BuyPrice": 101, "SellPrice": 0,
             "MeanPrice": 101, "StockBracket": 3, "DemandBracket": 0, "Stock": 9999, "Demand": 0}]})
        [(name, env)] = E.build(self.ev("Market"), self.s, "v")
        valid(env, "commodity-v3.0.json")
        m = env["message"]
        self.assertEqual((name, env["$schemaRef"], m["stationType"], [c["name"] for c in m["commodities"]]),
                         ("commodity", "https://eddn.edcd.io/schemas/commodity/3", "Orbis", ["gold"]))
        self.assertEqual(set(m["commodities"][0]) & {"Producer", "Rare", "id", "Category"}, set())
        self.assertEqual(E.build(self.ev("Market"), self.s, "v"), [])          # unchanged: not again

    def test_sent_once_per_visit(self):
        """The same unchanged market opened twice in one docking goes once; a new docking sends it again (EDDN's readers
        date a station's data by it)."""
        self.file("Market.json", {"event": "Market", "Items": []})
        self.assertEqual(len(E.build(self.ev("Market"), self.s, "v")), 1)
        self.assertEqual(E.build(self.ev("Market"), self.s, "v"), [])           # the screen again, same docking
        for name in ("Undocked", "Docked"):
            self.s.feed(self.ev(name))
            E.build(self.ev(name), self.s, "v")
        self.assertEqual(len(E.build(self.ev("Market"), self.s, "v")), 1)      # back again: sent

    def test_late_file_goes_on_the_tick(self):
        """A file written after its event's line, with no line after it, goes on the server's tick (idle), under the
        event's line; a wait gives up FILE_WAIT_S later (2026-10-09)."""
        self.s.source, self.s.now = "J.log:900", 5000.0
        self.file("Market.json", {"timestamp": "2026-10-08T09:00:00Z", "event": "Market", "Items": []})   # yesterday's
        self.assertEqual(E.build(self.ev("Market", StationType="Orbis"), self.s, "v"), [])
        self.s.now = 5001.0
        self.assertEqual(E.idle(self.s, "v"), [])                     # still the old file
        self.file("Market.json", {"event": "Market", "StationType": "Orbis", "Items": []})   # the game writes it now
        self.s.now = 5002.0
        [(name, env, origin)] = E.idle(self.s, "v")
        valid(env, "commodity-v3.0.json")
        self.assertEqual((name, origin, env["message"]["marketId"]), ("commodity", "J.log:900", 128))
        self.assertEqual(E.idle(self.s, "v"), [])                     # once
        self.s.now = 6000.0
        E.build(self.ev("Shipyard"), self.s, "v")                     # never written
        self.s.now = 6000.0 + E.FILE_WAIT_S + 1
        self.assertEqual(E.idle(self.s, "v"), [])
        self.assertNotIn("shipyard", self.s.pending)                  # given up

    def test_empty_bracket_kept(self):
        """A bracket the game writes as "" ("not normally sold here") goes as "", not 0 (EDDN's schema)."""
        self.file("Market.json", {"event": "Market", "Items": [
            {"id": 1, "Name": "$gold_name;", "Category": "$MARKET_category_metals;", "BuyPrice": 9000, "SellPrice": 8800,
             "MeanPrice": 9100, "StockBracket": "", "DemandBracket": 0, "Stock": 5, "Demand": 0}]})
        [(name, env)] = E.build(self.ev("Market"), self.s, "v")
        valid(env, "commodity-v3.0.json")
        self.assertEqual((env["message"]["commodities"][0]["stockBracket"], env["message"]["commodities"][0]["demandBracket"]), ("", 0))

    def test_wrong_file_waits(self):
        self.file("Market.json", {"event": "Market", "MarketID": 999, "Items": []})   # the last station's file
        self.assertEqual(E.build(self.ev("Market"), self.s, "v"), [])
        self.file("Market.json", {"event": "Market", "Items": []})                   # now this one's (an empty market goes)
        [(name, env)] = E.build({"timestamp": self.t, "event": "Music"}, self.s, "v")
        valid(env, "commodity-v3.0.json")
        self.assertEqual(env["message"]["commodities"], [])

    def test_outfitting_shipyard_fcmaterials(self):
        self.file("Outfitting.json", {"event": "Outfitting", "Horizons": True, "Items": [
            {"id": 1, "Name": "hpt_pulselaser_fixed_small", "BuyPrice": 2000}, {"id": 2, "Name": "int_planetapproachsuite", "BuyPrice": 500},
            {"id": 3, "Name": "anaconda_armour_grade1", "BuyPrice": 0}, {"id": 4, "Name": "paintjob_x", "BuyPrice": 0}]})
        [(name, env)] = E.build(self.ev("Outfitting"), self.s, "v")
        valid(env, "outfitting-v2.0.json")
        self.assertEqual(env["message"]["modules"], ["Hpt_pulselaser_fixed_small", "anaconda_Armour_grade1"])   # EDMC's capitalising
        self.file("Shipyard.json", {"event": "Shipyard", "AllowCobraMkIV": False, "PriceList": [
            {"id": 1, "ShipType": "sidewinder", "ShipPrice": 30000}, {"id": 2, "ShipType": "adder", "ShipPrice": 80000}]})
        [(name, env)] = E.build(self.ev("Shipyard"), self.s, "v")
        valid(env, "shipyard-v2.0.json")
        self.assertEqual(env["message"]["ships"], ["adder", "sidewinder"])
        self.assertNotIn("allowCobraMkIV", env["message"])   # about the commander, not the station: left out as the others do
        with open(os.path.join(self.dir, "FCMaterials.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": self.t, "event": "FCMaterials", "MarketID": 3700251648, "CarrierName": "OUT OF THE BLUE",
                       "CarrierID": "G0X-85Z", "Items": [{"id": 128961524, "Name": "$aerogel_name;", "Name_Localised": "Aerogel",
                                                         "Price": 500, "Stock": 0, "Demand": 10}]}, f)
        [(name, env)] = E.build({"timestamp": self.t, "event": "FCMaterials", "MarketID": 3700251648, "CarrierName": "OUT OF THE BLUE",
                                 "CarrierID": "G0X-85Z"}, self.s, "v")
        valid(env, "fcmaterials_journal-v1.0.json")
        self.assertNotIn("Name_Localised", env["message"]["Items"][0])

    def test_docking(self):
        [(name, env)] = E.build(self.ev("DockingGranted", LandingPad=12, StationType="Orbis"), self.s, "v")
        valid(env, "dockinggranted-v1.0.json")
        [(name, env)] = E.build(self.ev("DockingDenied", Reason="NoSpace", StationType="Orbis"), self.s, "v")
        valid(env, "dockingdenied-v1.0.json")


class Answers(unittest.TestCase):

    def test_outcome(self):
        self.assertEqual(E.outcome(200), ("sent", None))
        for st in (400, 413, 426):
            self.assertEqual(E.outcome(st), ("dropped", None))   # never retried (EDDN's MUST NOT)
        self.assertEqual(E.outcome(503)[0], "queued")
        self.assertGreaterEqual(E.outcome(408)[1], 60)           # at least a minute
        h = E.SchemaHold()
        for t in (0, 10, 20):
            self.assertIsNone(h.is_held("journal"))
            h.refused("journal", t, "400 FAIL")
        self.assertEqual(h.is_held("journal"), "400 FAIL")
        h2 = E.SchemaHold()
        for t in (0, 2000, 4000):                                 # spread over more than an hour: not held
            h2.refused("journal", t, "400")
        self.assertIsNone(h2.is_held("journal"))


class _Resp:
    def __init__(self, status, text):
        self.status, self._text = status, text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Session:
    def __init__(self, answers):
        self.answers, self.posts = list(answers), []

    def post(self, url, data=None, headers=None):
        self.posts.append((url, json.loads(gzip.decompress(data)), headers))
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return _Resp(*a)


class SenderAndPipeline(unittest.TestCase):

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def rows(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM upload_queue ORDER BY id")]

    def test_journal_line_to_eddn(self):
        """A live jump goes through the reader, the hub and the EDDN builder into the outbox, then out as gzip JSON."""
        self.state.set_upload("eddn", True)
        path = os.path.join(self.dir, "Journal.2026-10-08T100000.01.log")
        now = lambda ago: iso_ts(time.time() - ago)
        with open(path, "w", encoding="utf-8") as f:
            for e in ({"timestamp": now(30), "event": "Fileheader", "gameversion": "4.2.0.100", "build": "r1 "},
                      {"timestamp": now(29), "event": "LoadGame", "Commander": "Briadin", "Horizons": True, "Odyssey": True},
                      dict(FSDJUMP, timestamp=now(5))):
                f.write(json.dumps(e) + "\n")
        self.j.scan_dir(self.dir, upload="live")
        [row] = self.rows()
        self.assertEqual((row["service"], row["schema"], row["state"]), ("eddn", "journal", "queued"))
        self.state.upload_session = _Session([(200, "OK")])
        out = asyncio.run(self.state.eddn_send([row]))
        self.assertEqual(out, [(row["id"], "sent", "200 OK", None)])
        url, sent, headers = self.state.upload_session.posts[0]
        self.assertEqual((url, headers["Content-Encoding"]), (E.UPLOAD_URL, "gzip"))
        self.assertEqual(sent["message"]["StarSystem"], "Smojooe AR-E b25-8")
        if jsonschema:
            valid(sent, "journal-v1.0.json")

    def test_refusals_hold_the_schema(self):
        s = session()
        for i in range(4):
            U.enqueue(self.db, "eddn", "journal", f"J:{i}", iso_ts(time.time() - 5), s, {"$schemaRef": "x", "message": {}})
        rows = self.rows()
        self.state.upload_session = _Session([(400, "FAIL: Schema Validation: [...]")] * 3)
        got = [asyncio.run(self.state.eddn_send([r]))[0][1] for r in rows[:3]]
        self.assertEqual(got, ["dropped"] * 3)
        out = asyncio.run(self.state.eddn_send([rows[3]]))      # held now: not even sent
        self.assertEqual((out[0][1], len(self.state.upload_session.posts)), ("dropped", 3))
        self.state.upload_session = _Session([ConnectionError("unreachable")])
        with self.assertRaises(ConnectionError):                 # the loop backs off
            asyncio.run(self.state.eddn_send([dict(rows[0], schema="fsssignaldiscovered")]))

    def test_outdated_schema_holds_at_once(self):
        """426: EDDN no longer takes that schema version; the next message of it is not even sent."""
        s = session()
        for i in range(2):
            U.enqueue(self.db, "eddn", "journal", f"J:{i}", iso_ts(time.time() - 5), s, {"$schemaRef": "x", "message": {}})
        rows = self.rows()
        self.state.upload_session = _Session([(426, "FAIL: Outdated Schema")])
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(asyncio.run(self.state.eddn_send([rows[0]]))[0][1], "dropped")
        self.assertEqual(asyncio.run(self.state.eddn_send([rows[1]]))[0][1], "dropped")
        self.assertEqual(len(self.state.upload_session.posts), 1)

    def test_hour_old_rows_are_not_sent(self):
        """Any EDDN message an hour late (an outage, switched off and on) is dropped, not sent as current."""
        s = session()
        U.enqueue(self.db, "eddn", "journal", "J:1", iso_ts(time.time() - 2 * 3600), s, {"$schemaRef": "x", "message": {}})
        [row] = self.rows()
        self.state.upload_session = _Session([])
        self.assertEqual(asyncio.run(self.state.eddn_send([row]))[:1], [(row["id"], "dropped", "not sent: over an hour old", None)])

    def test_stale_station_data_is_not_sent(self):
        s = session()
        U.enqueue(self.db, "eddn", "commodity", "J:1", iso_ts(time.time() - 7200), s, {"$schemaRef": "x", "message": {}})
        [row] = self.rows()
        self.state.upload_session = _Session([])
        self.assertEqual(asyncio.run(self.state.eddn_send([row]))[0][1], "dropped")

    def test_available_in_the_summary(self):
        self.assertTrue(self.state.uploads_summary()["eddn"]["available"])
        self.assertTrue(self.state.uploads_summary()["edsm"]["available"])   # part H
