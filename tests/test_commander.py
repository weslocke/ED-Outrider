"""The Commander view (outrider/commander.py, Journals.handle_commander, GET /api/commander/*): the commander,
inventory, engineering, missions and the combat and mining sessions, folded from made-up journal lines fed to
Journals.handle on a scratch database."""
import asyncio
import json
import os
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider

import outrider.commander as C

NOW = 1791806400   # 2026-10-12T12:00:00Z
T = lambda hms, day="2026-10-12": f"{day}T{hms}Z"


def temp_dir(test):
    d = tempfile.TemporaryDirectory()
    test.addCleanup(d.cleanup)
    return d.name


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


def write(folder, name, events):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, separators=(", ", ":")) + "\n")   # as the game writes: "event":"X"


def setup(test, events=()):
    """A scratch database, its Journals fed `events` and a State over it."""
    db = ed_outrider.open_db(":memory:")
    test.addCleanup(db.close)
    j = ed_outrider.Journals(db)
    for e in events:
        j.handle(e)
    return j, ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)


LOGIN = ev(T("08:00:00"), "LoadGame", Commander="Tester", FID="F1", Credits=1234567890, Loan=5000, Ship="krait_light",
           Ship_Localised="Krait Phantom")
INVENTORY = [
    LOGIN,
    ev(T("09:00:00"), "Loadout", Ship="krait_light", ShipID=7, ShipName="Sample Ship", ShipIdent="SP-01", HullValue=40, ModulesValue=60,
       Modules=[]),
    ev(T("09:01:00"), "StoredShips", StationName="Old Port", StarSystem="Sol", ShipsHere=[
        {"ShipID": 7, "ShipType": "krait_light", "Value": 100},
        {"ShipID": 3, "ShipType": "asp", "ShipType_Localised": "Asp Explorer", "Name": "Scout", "Value": 9000000, "Hot": False}],
       ShipsRemote=[{"ShipID": 5, "ShipType": "anaconda", "StarSystem": "Colonia", "TransferPrice": 1234567, "TransferTime": 7200,
                     "Value": 150000000, "Hot": True}, {"ShipID": 6, "ShipType": "sidewinder", "InTransit": True, "Value": 32000}, "junk"]),
    ev(T("09:02:00"), "StoredModules", StationName="Old Port", StarSystem="Sol", Items=[
        {"Name": "$int_hyperdrive_size5_class5_name;", "Name_Localised": "FSD", "StorageSlot": 1, "StarSystem": "Sol", "TransferCost": 0,
         "TransferTime": 0, "BuyPrice": 5103953, "Hot": False, "EngineerModifications": "FSD_LongRange", "Level": 5, "Quality": 0.87},
        {"Name": "$hpt_pulselaser_gimbal_medium_name;", "Name_Localised": "Pulse Laser", "StorageSlot": 2, "StarSystem": "Colonia", "TransferCost": 4100, "TransferTime": 6000,
         "BuyPrice": 35400, "Hot": False}, {"Name": "$int_fuelscoop_size6_class5_name;", "StorageSlot": 3, "InTransit": True}]),
    ev(T("09:03:00"), "ShipLocker", Items=[{"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "OwnerID": 0, "Count": 3},
                                           {"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "OwnerID": 0, "MissionID": 9, "Count": 1}],
       Components=[{"Name": "graphene", "OwnerID": 0, "Count": 12}], Consumables=[{"Name": "healthpack", "Name_Localised": "Medkit", "Count": 2}],
       Data=[]),
    ev(T("09:04:00"), "ShipLocker"),                                           # the stub the game writes later: not a list
    ev(T("09:05:00"), "SuitLoadout", SuitID=1, SuitName="explorationsuit_class3", SuitName_Localised="Artemis Suit",
       SuitMods=["suit_increasedsprintduration"], LoadoutID=4293000001, LoadoutName="Bio", Modules=[
           {"SlotName": "PrimaryWeapon1", "SuitModuleID": 11, "ModuleName": "wpn_m_assaultrifle_laser_fauto", "ModuleName_Localised": "TK Aphelion",
            "Class": 2, "WeaponMods": ["weapon_stability"]}]),
]


class Inventory(unittest.TestCase):
    def test_ships(self):
        _, state = setup(self, INVENTORY)
        s = state.commander_inventory()["ships"]
        self.assertEqual((s["ts"], s["here"]), (T("09:01:00"), {"system": "Sol", "station": "Old Port"}))
        rows = {r["id"]: r for r in s["ships"]}
        self.assertEqual(list(rows), [7, 3, 5, 6])                             # the one you fly first, and only once
        self.assertEqual((rows[7]["current"], rows[7]["name"], rows[7]["ident"], rows[7]["value"]), (True, "Sample Ship", "SP-01", 100))
        self.assertEqual((rows[3]["system"], rows[3]["station"], rows[3]["type_name"], rows[3]["transfer_cost"]), ("Sol", "Old Port", "Asp Explorer", None))
        self.assertEqual((rows[5]["system"], rows[5]["transfer_cost"], rows[5]["transfer_s"], rows[5]["hot"]), ("Colonia", 1234567, 7200, True))
        self.assertTrue(rows[6]["in_transit"])
        self.assertEqual(C.ships(None), {"ts": None, "ships": [], "here": None})

    def test_the_fleet_after_the_list(self):
        """Should 1: a ship sold, swapped, sent for or renamed after the last StoredShips (as inara._fleet reads them);
        a Loadout newer than the list gives the value."""
        j, state = setup(self, INVENTORY + [
            ev(T("09:10:00"), "Location", StarSystem="Lave", SystemAddress=1, StarPos=[1.0, 2.0, 3.0], Docked=True,
               StationName="Lave Station", StationType="Orbis", MarketID=55),
            ev(T("09:11:00"), "ShipyardSell", ShipType="asp", SellShipID=3, ShipPrice=8000000, MarketID=55),
            ev(T("09:12:00"), "ShipyardSwap", ShipType="anaconda", ShipID=5, StoreOldShip="krait_light", StoreShipID=7, MarketID=55),
            ev(T("09:12:05"), "Loadout", Ship="anaconda", ShipID=5, ShipName="Big", ShipIdent="BG-01", HullValue=140000000,
               ModulesValue=20000000, Modules=[]),
            ev(T("09:13:00"), "SetUserShipName", Ship="krait_light", ShipID=7, UserShipName="Old Faithful", UserShipId="OF-01"),
            ev(T("09:14:00"), "ShipyardTransfer", ShipType="sidewinder", ShipID=6, System="Sol", ShipMarketID=1, Distance=99.0,
               TransferPrice=1000, TransferTime=600, MarketID=55),
            ev(T("09:15:00"), "SellShipOnRebuy", ShipType="cobramkiii", System="Lave", SellShipId=4, ShipPrice=1)])
        rows = {r["id"]: r for r in state.commander_inventory()["ships"]["ships"]}
        self.assertEqual(list(rows), [5, 7, 6])                                # the Asp sold; the Anaconda flown now
        self.assertEqual((rows[5]["current"], rows[5]["name"], rows[5]["value"]), (True, "Big", 160000000))
        self.assertEqual((rows[7]["system"], rows[7]["station"], rows[7]["name"], rows[7]["ident"], rows[7]["value"]),
                         ("Lave", "Lave Station", "Old Faithful", "OF-01", 100))
        self.assertEqual((rows[6]["system"], rows[6]["station"], rows[6]["in_transit"]), ("Lave", "Lave Station", False))   # long arrived
        moving = C.ships(j.cmdr_view["stored_ships"], now=ed_outrider.ts_seconds(T("09:15:00")))["ships"]
        self.assertEqual([s["in_transit"] for s in moving if s["id"] == 6], [True])   # ten minutes on its way
        p = state.commander_profile()["profile"]
        self.assertEqual((p["assets"]["ships"], p["assets"]["fleet"]), (3, 160000000 + 100 + 32000))

    def test_a_shipyard_list_during_a_transfer_keeps_its_arrival(self):
        """Review 2026-10-20 L5: a StoredShips written while a ship is on its way (opening any shipyard) says InTransit
        with no time; the fold's transfer knew when it arrives, and without it the ship stayed "in transit" for good."""
        stored = lambda ts, transit: ev(ts, "StoredShips", StationName="Lave Station", MarketID=55, StarSystem="Lave",
                                        ShipsHere=[], ShipsRemote=[{"ShipID": 6, "ShipType": "sidewinder", "Value": 32000, "Hot": False,
                                                                    **({"InTransit": True} if transit else {"StarSystem": "Sol"})}])
        j, _ = setup(self, [
            ev(T("09:10:00"), "Location", StarSystem="Lave", SystemAddress=1, StarPos=[1.0, 2.0, 3.0], Docked=True,
               StationName="Lave Station", StationType="Orbis", MarketID=55),
            stored(T("09:11:00"), False),
            ev(T("09:14:00"), "ShipyardTransfer", ShipType="sidewinder", ShipID=6, System="Sol", ShipMarketID=1, Distance=99.0,
               TransferPrice=1000, TransferTime=600, MarketID=55),
            stored(T("09:14:30"), True)])
        at = lambda when: [(s["in_transit"], s["system"]) for s in
                           C.ships(j.cmdr_view["stored_ships"], now=ed_outrider.ts_seconds(when))["ships"] if s["id"] == 6]
        self.assertEqual(at(T("09:15:00")), [(True, "Lave")])    # on its way here
        self.assertEqual(at(T("10:00:00")), [(False, "Lave")])   # arrived: not "in transit" until the next list

    def test_modules_locker_and_suits(self):
        _, state = setup(self, INVENTORY)
        inv = state.commander_inventory()
        m = inv["modules"]["modules"]
        self.assertEqual([(r["name"], r["size"], r["rating"], r["blueprint"], r["level"]) for r in m],
                         [("FSD", 5, "A", "Long range", 5), ("Fuelscoop", 6, "A", None, None), ("Pulse Laser", 2, None, None, None)])   # the game's name, else the symbol's words
        self.assertEqual(C.module_label("Hpt_MultiCannon_Turret_Huge"), ("Multicannon", 4, None, "Turreted"))
        self.assertEqual(C.module_label("$int_shieldgenerator_size6_class3_fast_name;", " Bi-Weave Shield "), ("Bi-Weave Shield", 6, "C", None))
        self.assertEqual(C.module_label(None), ("?", None, None, None))
        self.assertEqual((m[2]["mount"], m[2]["system"], m[2]["transfer_cost"], m[1]["in_transit"]), ("Gimballed", "Colonia", 4100, True))
        lk = inv["locker"]
        self.assertEqual(lk["ts"], T("09:03:00"))                              # the whole list, not the later stub
        self.assertEqual([(k["name"], [(i["name"], i["count"], i["mission"]) for i in k["items"]]) for k in lk["kinds"]], [
            ("Goods", [("Weapon Schematic", 3, False), ("Weapon Schematic", 1, True)]), ("Assets", [("graphene", 12, False)]),
            ("Data", []), ("Consumables", [("Medkit", 2, False)])])
        su = inv["suits"]
        self.assertEqual((su[0]["loadout"], su[0]["suit"], su[0]["class"], su[0]["mods"]), ("Bio", "Artemis Suit", 3, ["Increased sprint duration"]))
        self.assertEqual(su[0]["weapons"], [{"name": "TK Aphelion", "class": 2, "slot": "PrimaryWeapon1", "mods": ["Stability"]}])

    def test_suit_loadouts_fold(self):
        """Should 2: created, equipped, upgraded, renamed and deleted loadouts (as inara._suits reads them)."""
        _, state = setup(self, INVENTORY + [
            ev(T("09:20:00"), "CreateSuitLoadout", SuitID=2, SuitName="utilitysuit_class1", SuitName_Localised="Maverick Suit", SuitMods=[],
               LoadoutID=4293000002, LoadoutName="Spare", Modules=[]),
            ev(T("09:21:00"), "LoadoutEquipModule", LoadoutName="Bio", SuitID=1, SuitName="explorationsuit_class3", LoadoutID=4293000001,
               SlotName="SecondaryWeapon", ModuleName="wpn_s_pistol_kinetic_sauto", ModuleName_Localised="Karma P-15", Class=1,
               WeaponMods=[], SuitModuleID=12),
            ev(T("09:22:00"), "UpgradeWeapon", Name="wpn_m_assaultrifle_laser_fauto", SuitModuleID=11, Class=3, Cost=1, Resources=[]),
            ev(T("09:23:00"), "UpgradeSuit", Name="explorationsuit_class3", SuitID=1, Class=4, Cost=1, Resources=[]),
            ev(T("09:24:00"), "RenameSuitLoadout", SuitID=1, SuitName="explorationsuit_class3", LoadoutID=4293000001, LoadoutName="Bio 2"),
            ev(T("09:25:00"), "DeleteSuitLoadout", SuitID=2, SuitName="utilitysuit_class1", LoadoutID=4293000002, LoadoutName="Spare"),
            ev(T("09:26:00"), "LoadoutRemoveModule", LoadoutName="Bio 2", SuitID=1, LoadoutID=4293000001, SlotName="PrimaryWeapon1",
               ModuleName="wpn_m_assaultrifle_laser_fauto", SuitModuleID=11),
            ev(T("09:27:00"), "RenameSuitLoadout", LoadoutID=99, LoadoutName="never seen whole")])
        su = state.commander_inventory()["suits"]
        self.assertEqual([(s["loadout"], s["class"], [(w["name"], w["class"]) for w in s["weapons"]]) for s in su],
                         [("Bio 2", 4, [("Karma P-15", 1)])])                  # the deleted one gone; the rifle removed after its upgrade

    def test_the_ship_locker_file(self):
        """Should 3: the login line, then ShipLocker.json when it is newer (the later lines carry no contents)."""
        j, state = setup(self, INVENTORY)
        d = temp_dir(self)
        path = os.path.join(d, "ShipLocker.json")

        def file(ts, count):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ev(ts, "ShipLocker", Items=[{"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "Count": count}],
                             Components=[], Data=[], Consumables=[]), f)
        v = j.commander_version
        file(T("09:30:00"), 5)
        self.assertTrue(j.read_locker_file(d))
        lk = state.commander_inventory()["locker"]
        self.assertEqual((lk["ts"], lk["kinds"][0]["items"], lk["kinds"][1]["items"]),
                         (T("09:30:00"), [{"name": "Weapon Schematic", "count": 5, "mission": False}], []))
        self.assertGreater(j.commander_version, v)
        self.assertFalse(j.read_locker_file(d))                                # the same file: nothing new
        file(T("09:00:00"), 1)
        self.assertFalse(j.read_locker_file(d))                                # older than what is kept (another folder's)
        self.assertEqual(state.commander_inventory()["locker"]["ts"], T("09:30:00"))
        self.assertFalse(j.read_locker_file(os.path.join(d, "none")))

    def test_the_tick_reads_the_locker_file_when_it_changes(self):
        """ShipLocker.json is read in the tick as Cargo.json: once, then only when its modification time moves."""
        j, state = setup(self, INVENTORY)
        d = temp_dir(self)
        path = os.path.join(d, "ShipLocker.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ev(T("09:30:00"), "ShipLocker", Items=[], Components=[], Data=[], Consumables=[]), f)
        reads, mtimes = [], {}
        later = ("watch_status", "maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold",
                 "maybe_sale_left", "maybe_locate_carrier", "maybe_find_sellers", "maybe_backup_on_quit")
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]), \
                unittest.mock.patch.object(j, "read_locker_file", lambda folder: reads.append(folder) or False):
            patches = [unittest.mock.patch.object(state, n, lambda *a: None) for n in later]
            for p in patches:
                p.start()
            try:
                state.tick(mtimes)
                state.tick(mtimes)                                             # unchanged: not read again
                m = os.path.getmtime(path)
                os.utime(path, (m + 5, m + 5))
                state.tick(mtimes)
            finally:
                for p in patches:
                    p.stop()
        self.assertIsNone(state.tail_error)
        self.assertEqual(reads, [d, d])


class Engineering(unittest.TestCase):
    ROWS = [{"id": "FSD_LongRange", "module": "Frame shift drive", "name": "Increased range", "grades": {
        "1": {"materials": {"atypicaldisruptedwakeechoes": 1}, "engineers": ["Felicity Farseer", "Elvira Martuuk"]},
        "5": {"materials": {"arsenic": 1, "chemicalmanipulators": 1, "dataminedwake": 2}, "engineers": ["Felicity Farseer", 'Tod "The Blaster" McQuinn']}}}]

    def test_engineers(self):
        j, state = setup(self, [
            ev(T("08:00:00"), "EngineerProgress", Engineers=[{"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Unlocked", "Rank": 4},
                                                              {"Engineer": "Elvira Martuuk", "EngineerID": 300160, "Progress": "Invited"}, "junk"]),
            ev(T("09:00:00"), "EngineerProgress", Engineer="Elvira Martuuk", EngineerID=300160, Progress="Unlocked"),
            ev(T("09:30:00"), "EngineerProgress", Engineer="Elvira Martuuk", EngineerID=300160, Rank=2)])
        self.assertEqual(j.cmdr_view["engineers"], {"Felicity Farseer": {"progress": "Unlocked", "rank": 4}, "Elvira Martuuk": {"progress": "Unlocked", "rank": 2}})
        j.materials = {"counts": {"arsenic": 4}, "names": {}}
        eng = state.commander_engineering()
        self.assertEqual(eng["engineers"][0], {"name": "Elvira Martuuk", "progress": "Unlocked", "rank": 2})
        fsd = next(b for b in eng["blueprints"] if b["id"] == "FSD_LongRange")
        self.assertEqual([m["have"] for m in fsd["grades"][-1]["materials"] if m["id"] == "arsenic"], [4])   # the materials held now

    def test_blueprints_against_your_materials(self):
        known = {"Felicity Farseer": {"progress": "Unlocked", "rank": 4}, "Elvira Martuuk": {"progress": "Invited", "rank": None},
                 "Tod 'The Blaster' McQuinn": {"progress": "Unlocked", "rank": 3}}
        counts = {"atypicaldisruptedwakeechoes": 7, "arsenic": 9, "chemicalmanipulators": 3, "dataminedwake": 5}
        b = C.blueprints(counts, known, lambda mid: mid.upper(), rows=self.ROWS)[0]
        self.assertEqual((b["module"], b["name"], [g["grade"] for g in b["grades"]]), ("Frame shift drive", "Increased range", [1, 5]))
        g1, g5 = b["grades"]
        self.assertEqual((g1["rolls"], g5["rolls"]), (7, 2))                    # 5 wake data at 2 a roll: twice
        self.assertEqual(g5["materials"][2], {"id": "dataminedwake", "name": "DATAMINEDWAKE", "need": 2, "have": 5, "category": "Encoded"})   # its trader's kind
        self.assertEqual([(e["name"], e["ready"]) for e in g1["engineers"]], [("Felicity Farseer", True), ("Elvira Martuuk", False)])
        # Rank is the highest grade an engineer crafts for you (the author's journals: no craft above it): rank 4, no G5
        self.assertEqual([(e["progress"], e["rank"], e["ready"]) for e in g5["engineers"]], [("Unlocked", 4, False), ("Unlocked", 3, False)])
        known["Felicity Farseer"]["rank"] = 5
        g5 = C.blueprints(counts, known, lambda mid: mid.upper(), rows=self.ROWS)[0]["grades"][1]
        self.assertEqual([e["ready"] for e in g5["engineers"]], [True, False])
        known["Felicity Farseer"].update(progress="Unlocked", rank=None)                 # unlocked, no rank said yet
        self.assertFalse(C.blueprints(counts, known, rows=self.ROWS)[0]["grades"][0]["engineers"][0]["ready"])
        self.assertEqual(C.blueprints({}, rows=self.ROWS)[0]["grades"][1]["rolls"], 0)

    def test_the_shipped_table(self):
        import outrider.materials as M
        rows = C.load_blueprints()
        self.assertGreater(len(rows), 70)
        for b in rows:
            self.assertTrue(b["module"] and b["name"] and b["grades"], b["id"])
            for g, v in b["grades"].items():
                self.assertIn(int(g), range(1, 6))
                self.assertTrue(v["materials"] and v["engineers"], f"{b['id']} G{g}")
                for mid, n in v["materials"].items():
                    self.assertIn(mid, M.MATERIALS, f"{b['id']} G{g}")           # the journal's own names: they meet your counts
                    self.assertGreater(n, 0)
        # the engineers are the module kind's (should 7): a pulse laser's Overcharged is not a cannon's, nor a heat
        # sink's Lightweight a chaff launcher's module
        over = {b["module"]: b["grades"]["1"]["engineers"] for b in rows if b["id"] == "Weapon_Overcharged"}
        self.assertIn("Broo Tarquin", over["Pulse laser"])
        self.assertNotIn("Broo Tarquin", over["Cannon"])
        self.assertIn("Tod \"The Blaster\" McQuinn", over["Cannon"])
        self.assertEqual(len({(b["module"], b["id"]) for b in rows}), len(rows))
        self.assertIn("Heat sink launcher", {b["module"] for b in rows if b["id"] == "Misc_LightWeight"})
        with open(C.BLUEPRINTS_FILE, encoding="utf-8") as f:
            src = json.load(f)["source"]
        self.assertEqual((len(src["commit"]), src["repo"]), (40, "https://github.com/EDCD/coriolis-data"))
        self.assertIn("Frontier", src["licence"])
        self.assertIsNone(C.load_blueprints(os.path.join(temp_dir(self), "none.json")))

    def test_an_unreadable_table_says_so(self):
        """Should 8: a missing or broken blueprints file is not "nothing matches"."""
        _, state = setup(self)
        self.assertFalse(state.commander_engineering()["unreadable"])
        bad = os.path.join(temp_dir(self), "blueprints.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{not json")
        for path in (bad, os.path.join(temp_dir(self), "none.json")):
            with unittest.mock.patch.object(C, "BLUEPRINTS_FILE", path), \
                    unittest.mock.patch.object(C.load_blueprints, "__defaults__", (path,)):
                eng = state.commander_engineering()
            self.assertEqual((eng["unreadable"], eng["blueprints"]), (True, []))


class Missions(unittest.TestCase):
    def test_what_you_hold(self):
        j, _ = setup(self, [
            ev(T("08:00:00"), "MissionAccepted", MissionID=1, Name="Mission_Delivery_name", LocalisedName="Deliver 20 units of Gold", Faction="Sol Workers",
               Commodity="$Gold_Name;", Commodity_Localised="Gold", Count=20, DestinationSystem="Alpha Centauri", DestinationStation="Hutton Orbital",
               Expiry=T("12:20:00"), Wing=False, Influence="++", Reputation="+", Reward=2500000),
            ev(T("08:05:00"), "MissionAccepted", MissionID=2, Name="Mission_Massacre", Faction="Sol Workers", TargetFaction="Bad Lot", KillCount=12,
               DestinationSystem="Wolf 359", Expiry=T("09:00:00", "2026-10-14"), Wing=True, Reward=9000000),
            ev(T("08:06:00"), "MissionAccepted", MissionID=3, Name="Mission_Courier", LocalisedName="Courier job", Faction="X", Expiry=T("09:00:00")),
            ev(T("08:07:00"), "MissionAccepted", MissionID=4, Name="Mission_Sightseeing", LocalisedName="Tour", PassengerCount=4, Expiry=T("09:00:00", "2026-10-20")),
            ev(T("08:30:00"), "CargoDepot", MissionID=1, ItemsDelivered=8, TotalItemsToDeliver=20),
            ev(T("08:40:00"), "MissionRedirected", MissionID=2, NewDestinationSystem="Sol", NewDestinationStation="Old Port"),
            ev(T("08:50:00"), "MissionCompleted", MissionID=4), ev(T("08:51:00"), "MissionFailed", MissionID=99)])
        m = C.missions(j.cmdr_view["missions"], now=NOW)
        self.assertEqual([r["id"] for r in m], [3, 1, 2])                       # the soonest first: the expired one leads
        self.assertEqual((m[0]["expired"], m[0]["soon"], m[1]["soon"], m[1]["expires_in"], m[2]["soon"]), (True, False, True, 1200, False))
        self.assertEqual((m[1]["name"], m[1]["commodity"], m[1]["count"], m[1]["delivered"], m[1]["station"], m[1]["reward"]),
                         ("Deliver 20 units of Gold", "Gold", 20, 8, "Hutton Orbital", 2500000))
        self.assertEqual((m[2]["name"], m[2]["target"], m[2]["count"], m[2]["wing"], m[2]["redirected"], m[2]["system"], m[2]["station"]),
                         ("Massacre", "Bad Lot", 12, True, True, "Sol", "Old Port"))

    def test_the_login_list_decides(self):
        missions = [ev(T("08:00:00"), "MissionAccepted", MissionID=1, Name="Mission_A", Expiry=T("20:00:00")),
                    ev(T("08:01:00"), "MissionAccepted", MissionID=2, Name="Mission_B"),
                    ev(T("10:00:00"), "Missions", Active=[{"MissionID": 2, "Name": "Mission_B", "PassengerMission": False, "Expires": 0},
                                                           {"MissionID": 7, "Name": "Mission_Old_name", "PassengerMission": True, "Expires": 7200}],
                       Failed=[], Complete=[])]
        j, state = setup(self, missions)
        m = C.missions(j.cmdr_view["missions"], now=NOW)
        self.assertEqual([(r["id"], r["name"], r["expiry"], r["passengers"]) for r in m],
                         [(7, "Old", T("12:00:00"), True), (2, "B", None, False)])   # 1 is gone; 7 was accepted before these journals
        self.assertEqual(C.missions(None, now=NOW), [])
        # a legacy folder read late: its lines are older than the login's list, which already says what is held
        j.handle(ev(T("07:00:00"), "MissionAccepted", MissionID=8, Name="Mission_Long_gone"))
        j.handle(ev(T("09:00:00"), "MissionCompleted", MissionID=2))
        self.assertEqual([r["id"] for r in state.commander_missions()["missions"]], [7, 2])


class RealLines(unittest.TestCase):
    """The field names checked against a player's real journals (2026-10-14): lines copied as the game wrote them."""
    def setup(self, lines):
        return setup(self, [json.loads(x) for x in lines])

    def test_a_colonisation_mission_on_the_login_list(self):
        """Its Expires is the time itself (a Unix time), every other mission's the seconds left; its name is localised
        and its symbol is written "$...;"."""
        j, _ = self.setup([
            '{ "timestamp":"2024-10-05T20:58:01Z", "event":"Missions", "Active":[ { "MissionID":979525210, "Name":"Mission_Courier_name", '
            '"PassengerMission":false, "Expires":85993 } ], "Failed":[  ], "Complete":[  ] }'])
        self.assertEqual([(r["name"], r["expiry"]) for r in C.missions(j.cmdr_view["missions"], now=NOW)],
                         [("Courier", "2024-10-06T20:51:14Z")])                # the MissionAccepted's own Expiry
        j, _ = self.setup([
            '{ "timestamp":"2025-03-24T19:38:35Z", "event":"Missions", "Active":[ { "MissionID":18446744073709551615, '
            '"Name":"$Mission_Colonisation_Initial_Name;", "Name_Localised":"Construct primary port", "PassengerMission":false, '
            '"Expires":1745159181 } ], "Failed":[  ], "Complete":[  ] }'])
        self.assertEqual([(r["name"], r["expiry"]) for r in C.missions(j.cmdr_view["missions"], now=NOW)],
                         [("Construct primary port", "2025-04-20T14:26:21Z")])
        self.assertEqual(C._mission({"Name": "$Mission_Colonisation_Initial_Name;"})["name"], "Colonisation Initial")

    def test_powerplay_join_after_its_rank(self):
        """The game writes PowerplayRank 0 just before PowerplayJoin, at the same second: the join keeps the rank."""
        j, _ = self.setup([
            '{ "timestamp":"2025-11-30T14:25:35Z", "event":"PowerplayRank", "Power":"Nakato Kaine", "Rank":0 }',
            '{ "timestamp":"2025-11-30T14:25:35Z", "event":"PowerplayJoin", "Power":"Nakato Kaine" }',
            '{ "timestamp":"2025-11-30T16:02:52Z", "event":"PowerplayMerits", "Power":"Nakato Kaine", "MeritsGained":52, "TotalMerits":52 }',
            '{ "timestamp":"2025-11-30T21:10:51Z", "event":"PowerplayRank", "Power":"Nakato Kaine", "Rank":1 }'])
        self.assertEqual({k: j.cmdr_view["powerplay"][k] for k in ("power", "rank", "merits")}, {"power": "Nakato Kaine", "rank": 1, "merits": 52})
        j, _ = self.setup(['{ "timestamp":"2025-11-30T14:25:35Z", "event":"PowerplayRank", "Power":"Nakato Kaine", "Rank":0 }',
                           '{ "timestamp":"2025-11-30T14:25:35Z", "event":"PowerplayJoin", "Power":"Nakato Kaine" }'])
        self.assertEqual(j.cmdr_view["powerplay"]["rank"], 0)
        j, _ = self.setup(['{ "timestamp":"2026-09-19T14:55:17Z", "event":"Powerplay", "Power":"Nakato Kaine", "Rank":17, "Merits":117279, "TimePledged":25316982 }'])
        self.assertEqual({k: j.cmdr_view["powerplay"][k] for k in ("power", "rank", "merits")}, {"power": "Nakato Kaine", "rank": 17, "merits": 117279})

    def test_the_shipyard_engineers_and_suits(self):
        j, state = self.setup([
            '{ "timestamp":"2026-09-26T14:17:19Z", "event":"StoredShips", "StationName":"G0X-85Z", "MarketID":3700251648, '
            '"StarSystem":"Col 285 Sector KM-V d2-106", "ShipsHere":[ { "ShipID":36, "ShipType":"panthermkii", "ShipType_Localised":"Panther Clipper Mk II", '
            '"Value":100, "Hot":false }, { "ShipID":29, "ShipType":"dolphin", "Name":"Dolph Cruises", "Value":6584028, "Hot":false } ], '
            '"ShipsRemote":[ { "ShipID":39, "ShipType":"explorer_nx", "ShipType_Localised":"Caspian Explorer", "Name":"", "StarSystem":"Shinrarta Dezhra", '
            '"ShipMarketID":128666762, "TransferPrice":7007804, "TransferTime":53956, "Value":170990782, "Hot":false } ] }',
            '{ "timestamp":"2026-09-26T14:20:57Z", "event":"ShipyardSwap", "ShipType":"panthermkii", "ShipType_Localised":"Panther Clipper Mk II", '
            '"ShipID":36, "StoreOldShip":"LakonMiner", "StoreShipID":35, "MarketID":3700251648 }',
            '{ "timestamp":"2026-09-27T17:50:57Z", "event":"ShipyardTransfer", "ShipType":"Explorer_NX", "ShipType_Localised":"Caspian Explorer", '
            '"ShipID":39, "System":"Shinrarta Dezhra", "ShipMarketID":128666762, "Distance":5365.605957, "TransferPrice":7007804, "TransferTime":53956, '
            '"MarketID":3700251648 }',
            '{ "timestamp":"2026-09-27T17:51:00Z", "event":"SetUserShipName", "Ship":"dolphin", "ShipID":29, "UserShipName":"Rhinocart", "UserShipId":"br-rhi" }',
            '{ "timestamp":"2025-10-02T02:06:11Z", "event":"EngineerProgress", "Engineer":"Bill Turner", "EngineerID":300010, "Rank":2 }',
            '{ "timestamp":"2025-03-18T05:54:49Z", "event":"CreateSuitLoadout", "SuitID":1826892828743577, "SuitName":"explorationsuit_class1", '
            '"SuitName_Localised":"Artemis Suit", "SuitMods":[  ], "LoadoutID":4293000001, "LoadoutName":"Xenobio", "Modules":[ { "SlotName":"PrimaryWeapon1", '
            '"SuitModuleID":1826892921801189, "ModuleName":"wpn_m_sniper_plasma_charged", "ModuleName_Localised":"Manticore Executioner", "Class":1, "WeaponMods":[  ] } ] }'])
        ships = {s["id"]: s for s in j.cmdr_view["stored_ships"]["ships"].values()}
        self.assertEqual(sorted(ships), [29, 35, 39])                          # the Panther flown now, the miner stored
        self.assertEqual((ships[39]["in_transit"], ships[39]["system"], ships[29]["name"], ships[29]["ident"], ships[35]["type"]),
                         (True, None, "Rhinocart", "br-rhi", "LakonMiner"))
        self.assertEqual(j.cmdr_view["engineers"], {"Bill Turner": {"progress": None, "rank": 2}})
        self.assertEqual([(s["loadout"], s["suit"], s["class"], [w["name"] for w in s["weapons"]]) for s in state.commander_inventory()["suits"]],
                         [("Xenobio", "Artemis Suit", 1, ["Manticore Executioner"])])

    def test_hot_ships(self):
        """Batch 4: whether the game marks a ship hot (wanted). In real journals every StoredShips entry carries `Hot`
        (false: the author was never hot) and no Loadout carries it at all; the ship you fly is not hot by them."""
        login = '{ "timestamp":"2026-09-26T14:04:44Z", "event":"LoadGame", "FID":"F331255", "Commander":"Briadin", "Horizons":true, ' \
                '"Odyssey":true, "Ship":"Explorer_NX", "Ship_Localised":"Caspian Explorer", "ShipID":39, "ShipName":"", "ShipIdent":"", ' \
                '"FuelLevel":128.000000, "FuelCapacity":160.000000, "GameMode":"Solo", "Credits":13329673300, "Loan":0, "language":"English/UK", ' \
                '"gameversion":"4.4.1.1", "build":"r332841/r0 " }'
        # (its Modules list cut)
        loadout = '{ "timestamp":"2026-09-26T14:05:46Z", "event":"Loadout", "Ship":"explorer_nx", "ShipID":39, "ShipName":" ", "ShipIdent":"BR-03E", ' \
                  '"ModulesValue":21751050, "HullHealth":1.000000, "UnladenMass":1290.875000, "CargoCapacity":64, "MaxJumpRange":72.746780, ' \
                  '"FuelCapacity":{ "Main":160.000000, "Reserve":1.140000 }, "Rebuy":1087554, "Modules":[  ] }'
        stored = '{ "timestamp":"2026-09-26T14:17:19Z", "event":"StoredShips", "StationName":"G0X-85Z", "MarketID":3700251648, ' \
                 '"StarSystem":"Col 285 Sector KM-V d2-106", "ShipsHere":[ { "ShipID":36, "ShipType":"panthermkii", "ShipType_Localised":"Panther Clipper Mk II", ' \
                 '"Value":100, "Hot":false } ], "ShipsRemote":[  ] }'
        j, state = self.setup([login, loadout, stored])
        self.assertEqual(j.cmdr_view["stored_ships"]["hot"], {"39": False, "36": False})
        self.assertEqual([(s["id"], s["current"], s["hot"]) for s in state.commander_fleet()["ships"]], [(39, True, False), (36, False, False)])
        # Frontier's journal manual (no real line): Loadout's Hot "if wanted at startup"; a StoredShips entry's when listed
        j.handle(ev("2026-09-26T15:00:00Z", "StoredShips", StationName="G0X-85Z", StarSystem="Col 285 Sector KM-V d2-106",
                    ShipsHere=[{"ShipID": 36, "ShipType": "panthermkii", "Value": 100, "Hot": True}], ShipsRemote=[]))
        self.assertEqual([(s["id"], s["hot"]) for s in state.commander_fleet()["ships"]], [(39, False), (36, True)])
        j.handle(ev("2026-09-26T15:01:00Z", "ShipyardSwap", ShipType="panthermkii", ShipID=36, StoreOldShip="Explorer_NX", StoreShipID=39, MarketID=3700251648))
        j.handle(ev("2026-09-26T15:01:02Z", "Loadout", Ship="panthermkii", ShipID=36, ShipName="", ShipIdent="BR-36P", Modules=[]))
        rows = {s["id"]: s for s in state.commander_fleet()["ships"]}
        self.assertEqual((rows[36]["current"], rows[36]["hot"], rows[39]["hot"]), (True, True, False))   # still hot once flown: no line said otherwise
        j.handle(ev("2026-09-27T10:00:00Z", "LoadGame", Commander="Briadin", Ship="panthermkii", ShipID=36))
        j.handle(ev("2026-09-27T10:00:05Z", "Loadout", Ship="panthermkii", ShipID=36, ShipName="", ShipIdent="BR-36P", Hot=True, Modules=[]))
        j.handle(ev("2026-09-27T10:30:00Z", "Loadout", Ship="panthermkii", ShipID=36, ShipName="", ShipIdent="BR-36P", Modules=[]))
        self.assertTrue(state.commander_fleet()["ships"][0]["hot"])           # a later Loadout says it only when it is
        j.handle(ev("2026-09-28T10:00:00Z", "LoadGame", Commander="Briadin", Ship="panthermkii", ShipID=36))
        j.handle(ev("2026-09-28T10:00:05Z", "Loadout", Ship="panthermkii", ShipID=36, ShipName="", ShipIdent="BR-36P", Modules=[]))
        self.assertFalse(state.commander_fleet()["ships"][0]["hot"])          # the login's without it: not wanted at startup
        j.handle(ev("2026-09-28T11:00:00Z", "ShipyardSwap", ShipType="explorer_nx", ShipID=39, StoreOldShip="panthermkii", StoreShipID=36, MarketID=1))
        j.handle(ev("2026-09-28T11:00:02Z", "Loadout", Ship="explorer_nx", ShipID=39, ShipName="", ShipIdent="BR-03E", Hot=True, Modules=[]))
        rows = {s["id"]: s for s in state.commander_fleet()["ships"]}
        self.assertEqual((rows[39]["hot"], rows[36]["hot"]), (True, False))  # stored: its marker kept the same way

    LISTED = ('{ "timestamp":"2026-09-26T14:37:29Z", "event":"StoredModules", "MarketID":128666762, "StationName":"Jameson Memorial", '
              '"StarSystem":"Shinrarta Dezhra", "Items":[ '   # (the list cut to three of its 207 items)
              '{ "Name":"$int_cargorack_size5_class1_name;", "Name_Localised":"Cargo Rack", "StorageSlot":9, "StarSystem":"Col 285 Sector KM-V d2-106", '
              '"MarketID":3700251648, "TransferCost":100, "TransferTime":2000, "BuyPrice":0, "Hot":false, "EngineerModifications":"CargoRack_IncreasedCapacity", '
              '"Level":5, "Quality":1.000000 }, '
              '{ "Name":"$int_cargorack_size5_class1_name;", "Name_Localised":"Cargo Rack", "StorageSlot":502, "StarSystem":"Shinrarta Dezhra", '
              '"MarketID":128666762, "TransferCost":0, "TransferTime":0, "BuyPrice":97900, "Hot":false }, '
              '{ "Name":"$int_detailedsurfacescanner_tiny_name;", "Name_Localised":"Surface Scanner", "StorageSlot":585, "StarSystem":"Col 285 Sector KM-V d2-106", '
              '"MarketID":3700251648, "TransferCost":2382, "TransferTime":2000, "BuyPrice":219375, "Hot":false, "EngineerModifications":"Sensor_Expanded", '
              '"Level":4, "Quality":0.934000 } ] }')
    DOCKED = ('{ "timestamp":"2026-09-26T14:34:33Z", "event":"Docked", "StationName":"Jameson Memorial", "StationType":"Orbis", "Taxi":false, '
              '"Multicrew":false, "StarSystem":"Shinrarta Dezhra", "SystemAddress":3932277478106, "MarketID":128666762, '
              '"DistFromStarLS":335.482538, "LandingPads":{ "Small":17, "Medium":18, "Large":9 } }')   # (its faction, services and economies cut)

    def test_stored_modules_between_lists(self):
        """Batch 4: modules stored, taken, sent for and stored instead of sold, followed between two Outfitting lists
        (real lines, 2026-09-26; the game's next list there had the point defence and the old drive here, the cargo
        rack and the heatsink gone), the next list replacing the fold."""
        stamp = lambda s: ed_outrider.ts_seconds(s)
        j, state = self.setup([self.DOCKED, self.LISTED,
            '{ "timestamp":"2026-09-26T14:39:23Z", "event":"ModuleBuy", "Slot":"FrameShiftDrive", "StoredItem":"$int_hyperdrive_overcharge_size8_class1_name;", '
            '"StoredItem_Localised":"FSD (SCO)", "BuyItem":"$int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii_name;", "BuyItem_Localised":"FSD (SCO)", '
            '"MarketID":128666762, "BuyPrice":71991912, "Ship":"explorer_nx", "ShipID":50 }',
            '{ "timestamp":"2026-09-26T14:42:57Z", "event":"ModuleRetrieve", "MarketID":128666762, "Slot":"Slot04_Size5", "RetrievedItem":"$int_cargorack_size5_class1_name;", '
            '"RetrievedItem_Localised":"Cargo Rack", "Ship":"explorer_nx", "ShipID":50, "Hot":false }',
            '{ "timestamp":"2026-09-26T14:53:56Z", "event":"ModuleBuy", "Slot":"TinyHardpoint6", "StoredItem":"$hpt_heatsinklauncher_turret_tiny_name;", '
            '"StoredItem_Localised":"Heatsink", "BuyItem":"$hpt_plasmapointdefence_turret_tiny_name;", "BuyItem_Localised":"Point Defence Turret", '
            '"MarketID":128666762, "BuyPrice":16275, "Ship":"explorer_nx", "ShipID":50 }',
            '{ "timestamp":"2026-09-26T14:54:12Z", "event":"ModuleRetrieve", "MarketID":128666762, "Slot":"TinyHardpoint1", "RetrievedItem":"$hpt_heatsinklauncher_turret_tiny_name;", '
            '"RetrievedItem_Localised":"Heatsink", "Ship":"explorer_nx", "ShipID":50, "Hot":false, "SwapOutItem":"$hpt_plasmapointdefence_turret_tiny_name;", '
            '"SwapOutItem_Localised":"Point Defence Turret" }',
            '{ "timestamp":"2026-09-26T15:11:11Z", "event":"FetchRemoteModule", "StorageSlot":585, "StoredItem":"$int_detailedsurfacescanner_tiny_name;", '
            '"StoredItem_Localised":"Surface Scanner", "ServerId":128666634, "TransferCost":277, "TransferTime":401, "Ship":"panthermkii", "ShipID":36 }'])
        rows = lambda now: [(m["name"], m["system"], m["in_transit"], m["blueprint"], m["value"])
                            for m in C.stored_modules(j.cmdr_view["stored_modules"], now=now)["modules"]]
        self.assertEqual(rows(stamp("2026-09-26T15:12:00Z")), [
            ("Cargo Rack", "Col 285 Sector KM-V d2-106", False, "Increased capacity", 0),   # the engineered one elsewhere stays
            ("Surface Scanner", None, True, "Expanded", 219375),                            # on its way here
            ("FSD (SCO)", "Shinrarta Dezhra", False, None, None),                           # stored, not sold: its value once listed
            ("Point Defence Turret", "Shinrarta Dezhra", False, None, None)])                # swapped out by the heatsink taken
        self.assertEqual(rows(stamp("2026-09-26T15:18:00Z"))[1], ("Surface Scanner", "Shinrarta Dezhra", False, "Expanded", 219375))   # 401 s later
        got = state.commander_inventory()["modules"]
        self.assertEqual((got["ts"], got["changed"]), ("2026-09-26T14:37:29Z", "2026-09-26T15:11:11Z"))
        # a line older than the latest list is a legacy folder's, read late: ignored; the next list replaces the fold
        j.handle(json.loads('{ "timestamp":"2026-09-26T15:11:12Z", "event":"StoredModules", "MarketID":128666762, "StationName":"Jameson Memorial", '
                            '"StarSystem":"Shinrarta Dezhra", "Items":[ { "Name":"$int_detailedsurfacescanner_tiny_name;", "Name_Localised":"Surface Scanner", '
                            '"StorageSlot":585, "InTransit":true, "BuyPrice":219375, "Hot":false, "EngineerModifications":"Sensor_Expanded", "Level":4, '
                            '"Quality":0.934000 } ] }'))
        j.handle(ev("2026-09-26T14:00:00Z", "ModuleStore", MarketID=128666762, StoredItem="$int_old_name;", Ship="x", ShipID=1))
        got = state.commander_inventory()["modules"]
        self.assertEqual((got["ts"], got["changed"], [m["name"] for m in got["modules"]]), ("2026-09-26T15:11:12Z", None, ["Surface Scanner"]))
        # the list says only "in transit": the fetch before it still knows when it arrives, and where
        self.assertEqual(rows(stamp("2026-09-26T15:18:00Z")), [("Surface Scanner", "Shinrarta Dezhra", False, "Expanded", 219375)])

    def test_a_module_stored_from_the_ship(self):
        """ModuleStore (a real line, 2026-09-26): stored where you are docked, with its engineering."""
        j, state = self.setup([
            '{ "timestamp":"2026-09-26T19:05:31Z", "event":"Docked", "StationName":"Port Drakkus", "StationType":"Coriolis", "Taxi":false, "Multicrew":false, '
            '"StarSystem":"Crucis Sector RT-R b4-3", "SystemAddress":7269098005961, "MarketID":4256091651, "DistFromStarLS":12.0 }',   # (cut)
            '{ "timestamp":"2026-09-26T19:06:26Z", "event":"ModuleStore", "MarketID":4256091651, "Slot":"Slot10_Size1", "StoredItem":"$int_detailedsurfacescanner_tiny_name;", '
            '"StoredItem_Localised":"Surface Scanner", "Ship":"panthermkii", "ShipID":36, "Hot":false, "EngineerModifications":"Sensor_Expanded", "Level":4, "Quality":0.934000 }'])
        m = state.commander_inventory()["modules"]
        self.assertEqual([(r["name"], r["system"], r["blueprint"], r["level"], r["hot"]) for r in m["modules"]],
                         [("Surface Scanner", "Crucis Sector RT-R b4-3", "Expanded", 4, False)])
        self.assertEqual((m["ts"], m["changed"]), (None, "2026-09-26T19:06:26Z"))   # no list yet: what was folded

    def test_the_events_with_no_real_line(self):
        """ModuleSellRemote and MassModuleStore: no line in the author's journals, so Frontier's journal manual's fields."""
        j, state = self.setup([self.DOCKED, self.LISTED])
        j.handle(ev("2026-09-26T15:00:00Z", "ModuleSellRemote", StorageSlot=9, SellItem="$int_cargorack_size5_class1_name;",
                    SellItem_Localised="Cargo Rack", ServerId=1, SellPrice=1000, Ship="explorer_nx", ShipID=50))
        j.handle(ev("2026-09-26T15:01:00Z", "MassModuleStore", MarketID=128666762, Ship="explorer_nx", ShipID=50, Items=[
            {"Slot": "MediumHardpoint1", "Name": "$hpt_pulselaser_gimbal_medium_name;", "Hot": True},
            {"Slot": "MediumHardpoint2", "Name": "$hpt_multicannon_fixed_medium_name;", "Hot": False, "EngineerModifications": "Weapon_Overcharged",
             "Level": 3, "Quality": 0.5}, "junk"]))
        got = [(r["name"], r["system"], r["hot"], r["level"]) for r in state.commander_inventory()["modules"]["modules"]]
        self.assertEqual(got, [("Multicannon", "Shinrarta Dezhra", False, 3), ("Surface Scanner", "Col 285 Sector KM-V d2-106", False, 4),
                               ("Cargo Rack", "Shinrarta Dezhra", False, None), ("Pulselaser", "Shinrarta Dezhra", True, None)])   # the sold one gone
        self.assertEqual(C.modules_apply(None, ev("2026-09-26T15:02:00Z", "ModuleSellRemote", StorageSlot=12345)), None)   # nothing to change


class Sessions(unittest.TestCase):
    EVENTS = [
        ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="krait_mkii", Ship_Localised="Krait Mk II"),
        ev(T("08:10:00"), "Bounty", Rewards=[{"Faction": "A", "Reward": 100000}, {"Faction": "B", "Reward": 50000}], Target="anaconda",
           Target_Localised="Anaconda", TotalReward=150000, VictimFaction="Bad Lot"),
        ev(T("08:20:00"), "Bounty", Target="anaconda", Target_Localised="Anaconda", TotalReward=250000),
        ev(T("08:40:00"), "FactionKillBond", Reward=60000, AwardingFaction="A", VictimFaction="B"),
        ev(T("08:41:00"), "Interdicted", Submitted=False), ev(T("08:45:00"), "Died"),
        ev(T("08:50:00"), "RedeemVoucher", Type="bounty", Amount=400000), ev(T("08:51:00"), "RedeemVoucher", Type="trade", Amount=5),
        ev(T("09:00:00"), "Shutdown"),
        ev(T("10:00:00"), "LoadGame", Commander="Tester", Ship="python"),
        ev(T("10:01:00"), "Scan"),
        ev(T("10:30:00"), "Shutdown"),                                          # nothing fought or mined: not listed
        ev(T("11:00:00"), "LoadGame", Commander="Tester", Ship="type9", Ship_Localised="Type-9 Heavy"),
        ev(T("11:00:30"), "LaunchDrone", Type="Prospector"), ev(T("11:00:40"), "LaunchDrone", Type="Collection"),
        ev(T("11:01:00"), "ProspectedAsteroid", Content="$AsteroidMaterialContent_High;", MotherlodeMaterial="Opal", Remaining=100.0),
        ev(T("11:02:00"), "ProspectedAsteroid", Content="$AsteroidMaterialContent_Low;", Remaining=100.0),
        ev(T("11:03:00"), "AsteroidCracked", Body="Ring A"),
    ] + [ev(T(f"11:{10 + i}:00"), "MiningRefined", Type="$platinum_name;", Type_Localised="Platinum") for i in range(5)] + [
        ev(T("11:31:00"), "MiningRefined", Type="$osmium_name;"),
        ev(T("11:50:00"), "MarketSell", Type="platinum", Type_Localised="Platinum", Count=5, TotalSale=1500000, MarketID=1),
        ev(T("11:51:00"), "MarketSell", Type="gold", Count=5, TotalSale=99, MarketID=1),
    ]

    def test_combat_and_mining(self):
        _, state = setup(self, self.EVENTS)
        got = state.commander_sessions(now=NOW)
        rows = got["sessions"]
        self.assertEqual([(r["start"], r["ship"], bool(r["combat"]), bool(r["mining"])) for r in rows],
                         [(T("11:00:00"), "Type-9 Heavy", False, True), (T("08:00:00"), "Krait Mk II", True, False)])   # newest first
        c = rows[1]["combat"]
        self.assertEqual((c["kills"], c["bounties"], c["bonds"], c["deaths"], c["interdicted"], c["redeemed"], c["by_ship"]),
                         (3, 400000, 60000, 1, 1, 400000, {"Anaconda": 2}))
        self.assertEqual((c["seconds"], c["per_hour"]), (1800, 6.0))            # three kills over half an hour
        m = rows[0]["mining"]
        self.assertEqual((m["tons"], m["refined"], m["prospected"], m["content"], m["motherlodes"], m["cracked"], m["srv_tons"]),
                         (6, {"Platinum": 5, "osmium": 1}, 2, {"High": 1, "Low": 1}, 1, 1, 0))
        self.assertEqual((m["prospectors"], m["collectors"], m["sold"], m["seconds"], m["per_hour"]), (1, 1, 1500000, 1800, 12.0))
        self.assertEqual((rows[0]["end"], rows[1]["end"]), (T("11:50:00"), T("08:50:00")))   # the last line that counted
        self.assertEqual((got["totals"]["combat"], got["totals"]["mining"], got["max"]),
                         ({"sessions": 1, "kills": 3, "bounties": 400000, "bonds": 60000, "deaths": 1},
                          {"sessions": 1, "tons": 6, "srv_tons": 0, "prospected": 2, "sold": 1500000}, C.SESSIONS_MAX))
        self.assertEqual(got["days"], 30)

    def test_the_last_30_days(self):
        """Batch 4: Sessions by days, as History: the logins of the last 30 days, 40 at most."""
        old = [ev(T("10:00:00", "2026-09-11"), "LoadGame", Commander="Tester", Ship="python"),     # 31 days before NOW
               ev(T("10:10:00", "2026-09-11"), "Bounty", TotalReward=5)]
        new = [ev(T("10:00:00", "2026-09-13"), "LoadGame", Commander="Tester", Ship="python"),     # 29 days
               ev(T("10:10:00", "2026-09-13"), "Bounty", TotalReward=5)]
        _, state = setup(self, old + new)
        self.assertEqual([s["start"] for s in state.commander_sessions(now=NOW)["sessions"]], [T("10:00:00", "2026-09-13")])
        self.assertEqual(state.commander_sessions(now=NOW - 2 * 86400)["totals"]["combat"]["sessions"], 2)
        many = []
        for i in range(45):                                                     # a login every half hour, each with a kill
            at = NOW - 86400 + i * 1800
            many += [ev(ed_outrider.iso_ts(at), "LoadGame", Commander="Tester"), ev(ed_outrider.iso_ts(at + 60), "Bounty", TotalReward=1)]
        _, state = setup(self, many)
        got = state.commander_sessions(now=NOW + 86400)["sessions"]
        self.assertEqual((len(got), got[0]["start"]), (40, ed_outrider.iso_ts(NOW - 86400 + 44 * 1800)))   # the newest 40

    def test_the_srv_refinery_apart(self):
        """Should 4: the Rhino's refinery is not the ship's mining (the reader knows the vehicle you are in)."""
        _, state = setup(self, [
            ev(T("11:00:00"), "LoadGame", Commander="Tester", Ship="python"),
            ev(T("11:05:00"), "MiningRefined", Type="$painite_name;", Type_Localised="Painite"),
            ev(T("11:20:00"), "LaunchSRV", SRVType="mev_rhino", SRVType_Localised="Rhino", Loadout="default", ID=1, PlayerControlled=True),
            ev(T("11:21:00"), "MiningRefined", Type="$gold_name;", Type_Localised="Gold"),
            ev(T("11:31:00"), "MiningRefined", Type="$gold_name;", Type_Localised="Gold"),
            ev(T("11:40:00"), "DockSRV", SRVType="mev_rhino", ID=1),
            ev(T("11:45:00"), "MiningRefined", Type="$painite_name;", Type_Localised="Painite"),
            ev(T("11:50:00"), "MarketSell", Type="gold", Type_Localised="Gold", Count=2, TotalSale=100000, MarketID=1)])
        m = state.commander_sessions(now=NOW)["sessions"][0]["mining"]
        self.assertEqual((m["tons"], m["refined"], m["srv_tons"], m["srv_refined"], m["seconds"], m["srv_seconds"], m["sold"]),
                         (2, {"Painite": 2}, 2, {"Gold": 2}, 2400, 600, 100000))

    def test_before_any_login(self):
        _, state = setup(self, self.EVENTS[1:3])                               # no login on record: no session to count in
        self.assertEqual(state.commander_sessions(now=NOW)["sessions"], [])

    def test_a_reread_doubles_nothing(self):
        """Everything is journal-derived: a re-read (RESET_JOURNAL_DATA, then the files again) gives the same, and a
        file read twice counts once."""
        d = temp_dir(self)
        write(d, "Journal.2026-10-12T080000.01.log", INVENTORY + Sessions.EVENTS[1:9] + [
            ev(T("08:01:00"), "MissionAccepted", MissionID=1, Name="Mission_A"),
            ev(T("08:02:00"), "EngineerProgress", Engineers=[{"Engineer": "Felicity Farseer", "Progress": "Unlocked", "Rank": 5}])])
        j, state = setup(self)
        reads = lambda: [state.commander_profile(), state.commander_inventory(), state.commander_missions(), state.commander_sessions(now=NOW),
                         state.commander_engineering()]
        j.scan_dir(d)
        first = reads()
        self.assertEqual(first[3]["sessions"][0]["combat"]["kills"], 3)
        j.scan_dir(d)
        self.assertEqual(reads(), first)
        ed_outrider.reset_journal_data(j.db)
        for key in C.COMMANDER_META:
            self.assertIsNone(ed_outrider.meta_get(j.db, key), key)
        self.assertEqual(j.db.execute("SELECT count(*) FROM play_activity").fetchone()[0], 0)
        j.reload()
        self.assertIsNone(state.commander_profile()["profile"])
        j.scan_dir(d)
        self.assertEqual(reads(), first)


class Profile(unittest.TestCase):
    EVENTS = [
        ev(T("07:00:00", "2026-10-10"), "LoadGame", Commander="Old Login", Credits=1, Loan=0),
        ev(T("07:59:58"), "Rank", Combat=3, Trade=7, Explore=8, Soldier=0, Exobiologist=4, Empire=2, Federation=14, CQC=0),
        ev(T("07:59:59"), "Progress", Combat=41, Trade=50, Explore=100, Soldier=0, Exobiologist=25, Empire=80, Federation=0, CQC=0),
        ev(T("07:59:59"), "Reputation", Empire=76.5, Federation=-40.0, Alliance=12.25),
        ev(T("07:59:59"), "SquadronStartup", SquadronName="Sample Wing", CurrentRank=1),
        LOGIN,
        ev(T("08:00:04"), "Powerplay", Power="Aisling Duval", Rank=3, Merits=4500),
        ev(T("08:00:06"), "Statistics", Bank_Account={"Current_Wealth": 9000000000, "Spent_On_Ships": 500000000, "Insurance_Claims": 3},
           Exploration={"Systems_Visited": 12345, "Total_Hyperspace_Distance": 987654, "Time_Played": 7200000, "Exploration_Profits": 0},
           Combat={"Bounties_Claimed": 40}),
        ev(T("08:00:07"), "CarrierStats", CarrierID=1, Callsign="X1X-X1X", Name="SAMPLE CARRIER", FuelLevel=800, Finance={"CarrierBalance": 250000000}),
        ev(T("08:30:00"), "Promotion", Combat=4),
        ev(T("08:40:00"), "PowerplayMerits", Power="Aisling Duval", MeritsGained=100, TotalMerits=4600),
    ] + INVENTORY[1:]

    def test_ranks_and_what_the_next_takes(self):
        _, state = setup(self, self.EVENTS)
        p = state.commander_profile()["profile"]
        r = {x["key"]: x for x in p["ranks"]}
        self.assertEqual([x["title"] for x in p["ranks"]], ["Combat", "Trade", "Exploration", "Exobiology", "Mercenary", "CQC", "Federal Navy", "Imperial Navy"])
        self.assertEqual((r["Combat"]["name"], r["Combat"]["progress"], r["Combat"]["next"], r["Combat"]["to_next"]), ("Expert", 0, "Master", None))   # promoted since
        # trade and exploration: their percentage only (no figures that could be checked against the game's own)
        self.assertEqual((r["Trade"]["name"], r["Trade"]["next"], r["Trade"]["progress"], r["Trade"]["to_next"], r["Trade"]["earned_by"]),
                         ("Tycoon", "Elite", 50, None, None))
        self.assertEqual((r["Explore"]["name"], r["Explore"]["next"], r["Explore"]["to_next"]), ("Elite", "Elite I", None))
        self.assertEqual((r["Exobiologist"]["name"], r["Exobiologist"]["to_next"], r["Exobiologist"]["earned_by"], r["Exobiologist"]["uncertain"]),
                         ("Cataloguer", 458_400_000, "exobiology data sold", False))   # 75% of the 611.2M step
        self.assertEqual((r["Federation"]["name"], r["Federation"]["progress"], r["Federation"]["next"]), ("Admiral", None, None))   # the top
        self.assertEqual((r["Empire"]["name"], r["Empire"]["next"], r["Empire"]["progress"]), ("Serf", "Master", 80))
        self.assertEqual(C.rank_rows({"Trade": 99, "Explore": "x"}, {})[0]["name"], "99")

    def test_the_exobiology_table(self):
        """The post-Update-14 thresholds (the Frontier forum, 2 Jan 2023), pinned; what is left is the step times the
        game's own share still to go. The author's journals: Geneticist 64% at the 2026-10-12 login."""
        self.assertEqual(C.RANK_CREDITS["Exobiologist"], (0, 22_500_000, 83_475_000, 210_560_000, 532_800_000, 1_144_000_000, 2_262_600_000,
                                                          3_996_000_000, 8_425_000_000, 12_969_000_000, 17_425_000_000, 21_925_000_000,
                                                          26_320_000_000, 30_917_860_900))
        self.assertEqual(set(C.RANK_CREDITS), {"Exobiologist"})
        row = lambda n, pct: C.rank_rows({"Exobiologist": n}, {"Exobiologist": pct})[0]
        g = row(7, 64)
        self.assertEqual((g["name"], g["next"], g["to_next"], g["uncertain"]), ("Geneticist", "Elite", 1_594_440_000, False))   # 36% of 4.429B
        self.assertEqual((row(8, 50)["to_next"], row(8, 50)["uncertain"]), (2_272_000_000, False))
        self.assertEqual([row(n, 0)["uncertain"] for n in (10, 11, 12)], [False, True, True])   # Elite IV and V are estimates
        top = row(13, 40)
        self.assertEqual((top["name"], top["next"], top["to_next"], top["progress"]), ("Elite V", None, None, None))

    def test_money_fleet_and_career(self):
        _, state = setup(self, self.EVENTS)
        p = state.commander_profile()["profile"]
        self.assertEqual((p["commander"], p["ts"], p["squadron"]), ("Tester", T("08:00:00"), "Sample Wing"))
        # credits and the carrier have one owner each: the payload's commander and carrier (the tiles'), not this
        self.assertFalse({"credits", "loan", "carrier"} & set(p))
        self.assertEqual(p["assets"], {"wealth": 9000000000, "ships": 4, "fleet": 100 + 9000000 + 150000000 + 32000, "modules": 5103953 + 35400})
        self.assertEqual([s["id"] for s in p["fleet"]], [7, 5, 3, 6])                    # the one you fly, then by value
        self.assertEqual(p["reputation"], {"Federation": -40.0, "Empire": 76.5, "Alliance": 12.2})
        self.assertEqual(p["power"], {"name": "Aisling Duval", "rank": 3, "merits": 4600})   # merits gained since the login
        self.assertEqual([(c["label"], c["value"], c["kind"]) for c in p["career"]], [
            ("Time played", 7200000, "time"), ("Systems visited", 12345, "n"), ("Distance jumped", 987654, "ly"), ("Bounties claimed", 40, "n"),
            ("Insurance claims", 3, "n"), ("Spent on ships", 500000000, "cr")])          # a zero is left out
        _, bare = setup(self, INVENTORY[1:])
        self.assertIsNone(bare.commander_profile()["profile"])                          # no login on record
        _, bare = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="New")])
        p = bare.commander_profile()["profile"]
        self.assertEqual((p["ranks"], p["fleet"], p["career"], p["power"]), ([], [], [], None))

    def test_powerplay_and_squadron_changes(self):
        _, state = setup(self, self.EVENTS + [
            ev(T("09:00:00"), "PowerplayDefect", FromPower="Aisling Duval", ToPower="Edmund Mahon"),
            ev(T("09:01:00"), "PowerplayRank", Power="Edmund Mahon", Rank=1),
            ev(T("09:02:00"), "LeftSquadron", SquadronName="Sample Wing")])
        p = state.commander_profile()["profile"]
        self.assertEqual((p["power"], p["squadron"]), ({"name": "Edmund Mahon", "rank": 1, "merits": None}, None))
        _, state = setup(self, self.EVENTS + [ev(T("09:00:00"), "PowerplayLeave", Power="Aisling Duval")])
        self.assertIsNone(state.commander_profile()["profile"]["power"])


class Reader(unittest.TestCase):
    def test_login_snapshots_leave_the_session_end(self):
        """The trap: the snapshots the game writes as you log in (missions, reputation, engineers, Powerplay, squadron,
        the ship locker) are not play, so they must not move last_play_ts (History's session end, the "away" greeting)."""
        j, _ = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester"), ev(T("08:10:00"), "Bounty", TotalReward=5)])
        self.assertEqual(j.last_play_ts, T("08:10:00"))
        for name, kw in (("Missions", {"Active": [], "Failed": [], "Complete": []}), ("Reputation", {"Empire": 1.0}),
                         ("EngineerProgress", {"Engineers": []}), ("Powerplay", {"Power": "X", "Rank": 1}),
                         ("SquadronStartup", {"SquadronName": "S"}), ("ShipLocker", {"Items": []}),
                         ("Music", {"MusicTrack": "MainMenu"})):   # the menu's track at every launch (review M2)
            j.handle(ev(T("12:00:00"), name, **kw))
            self.assertEqual(j.last_play_ts, T("08:10:00"), name)
            self.assertIn(name, ed_outrider.LOGIN_EVENTS)
        j.handle(ev(T("12:05:00"), "MissionAccepted", MissionID=1, Name="Mission_A"))   # accepting one is play
        self.assertEqual(j.last_play_ts, T("12:05:00"))

    def test_everything_kept_is_journal_derived(self):
        """Every fold's meta key and play_activity are cleared by a re-read (none of it is live-only), and the reader's
        filter lets their lines through."""
        reset = ed_outrider.RESET_JOURNAL_DATA
        for key in C.COMMANDER_META:
            self.assertIn(f"'{key}'", reset)
        self.assertIn("DELETE FROM play_activity", reset)
        for name in C.EVENTS:
            self.assertIn(f'"event":"{name}"'.encode(), ed_outrider.WANTED, name)
        self.assertIn(51, ed_outrider.PARSER_CHANGES)
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 51)

    def test_reread_stores_ships_where_they_were(self):
        """A fold's place (a ship stored by ShipyardSwap) comes from the lines replayed in order, not the live dock
        state a re-read keeps: docked elsewhere now, the re-read still stores the ship where it was swapped."""
        lines = [ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="krait_light", ShipID=7),
                 ev(T("08:00:05"), "Location", StarSystem="Sol", SystemAddress=10477373803, StarPos=[0, 0, 0], Docked=True,
                    StationName="Abraham Lincoln", StationType="Orbis", MarketID=100),
                 ev(T("08:10:00"), "ShipyardSwap", ShipType="anaconda", ShipID=5, StoreOldShip="krait_light", StoreShipID=7, MarketID=100),
                 ev(T("08:10:02"), "Loadout", Ship="anaconda", ShipID=5, ShipName="", ShipIdent="AN-05", Modules=[]),
                 ev(T("08:20:00"), "Undocked", StationName="Abraham Lincoln", MarketID=100),
                 ev(T("08:40:00"), "FSDJump", StarSystem="Alpha Centauri", SystemAddress=1, StarPos=[3, 0, 0]),
                 ev(T("09:00:00"), "Docked", StarSystem="Alpha Centauri", SystemAddress=1, StationName="Hutton Orbital",
                    StationType="Outpost", MarketID=200)]
        j, _ = setup(self, lines)
        want = ("Sol", "Abraham Lincoln")
        got = lambda jj: (jj.cmdr_view["stored_ships"]["ships"]["7"]["system"], jj.cmdr_view["stored_ships"]["ships"]["7"]["station"])
        self.assertEqual(got(j), want)
        ed_outrider.reset_journal_data(j.db)     # the re-read a PARSER_VERSION bump runs: meta docked is kept
        again = ed_outrider.Journals(j.db)
        for e in lines:
            again.handle(e)
        self.assertEqual(got(again), want)

    def test_a_ship_stored_at_your_carrier_after_it_jumped(self):
        """Review 2026-10-20 L1: aboard your carrier when it jumps, a ship swapped there afterwards was stored in the
        carrier's previous system (the dock's system was only followed by Docked / Undocked / Location)."""
        j, _ = setup(self, [
            ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="krait_light", ShipID=7),
            ev(T("08:00:05"), "Location", StarSystem="Sol", SystemAddress=10477373803, StarPos=[0, 0, 0], Docked=True,
               StationName="XYZ-123", StationType="FleetCarrier", MarketID=3700000000),
            ev(T("08:30:00"), "CarrierJump", Docked=True, StationName="XYZ-123", StationType="FleetCarrier",
               MarketID=3700000000, StarSystem="Alpha Centauri", SystemAddress=1, StarPos=[3, 0, 0]),
            ev(T("08:40:00"), "ShipyardSwap", ShipType="anaconda", ShipID=5, StoreOldShip="krait_light", StoreShipID=7,
               MarketID=3700000000)])
        ship = j.cmdr_view["stored_ships"]["ships"]["7"]
        self.assertEqual((ship["system"], ship["station"]), ("Alpha Centauri", "XYZ-123"))

    def test_other_handlers_still_see_shared_lines(self):
        """A line both the Commander view and another handler read (a MissionCompleted's materials, a Died) still
        reaches the other."""
        j, _ = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester"),
                            ev(T("08:10:00"), "Died")])
        self.assertEqual(j.db.execute("SELECT count(*) FROM deaths").fetchone()[0], 1)
        self.assertEqual(j.cmdr_view["missions"], None)


class Version(unittest.TestCase):
    def test_a_line_the_view_reads_moves_it(self):
        """The payload's commander_version: the page asks for the open tab again when it moves (as Materials on its
        version), not on a timer; State wakes the page for it."""
        j, state = setup(self)
        d = temp_dir(self)
        write(d, "Journal.2026-10-12T080000.01.log", [ev(T("08:00:00"), "Music", MusicTrack="Exploration"),
                                                      ev(T("08:01:00"), "MissionAccepted", MissionID=1, Name="Mission_A"),
                                                      ev(T("08:02:00"), "ReceiveText", Message="MissionAccepted"),
                                                      ev(T("08:03:00"), "Bounty", TotalReward=5)])
        v0 = j.commander_version
        j.read_file(os.path.join(d, "Journal.2026-10-12T080000.01.log"))
        self.assertEqual(j.commander_version, v0 + 2)              # the mission and the bounty, not a text naming one
        self.assertEqual(state.payload()["commander_version"], v0 + 2)
        v = state.version
        state.apply_own_changes()
        self.assertEqual(state.version, v + 1)                      # the page is woken for it
        state.apply_own_changes()
        self.assertEqual(state.version, v + 1)                      # once
        j.reload()                                                  # a rolled-back tick: what was read may differ
        self.assertGreater(j.commander_version, v0 + 2)


class Server(unittest.TestCase):
    def _get(self, state, parts):
        from aiohttp.test_utils import TestClient, TestServer
        app = ed_outrider.make_app(state)

        async def go():
            async with TestClient(TestServer(app)) as c:
                out = []
                for p in parts:
                    r = await c.get(f"/api/commander/{p}")
                    out.append((r.status, await r.json()))
                return out
        return asyncio.run(go())

    def test_routes(self):
        j, state = setup(self, INVENTORY + Sessions.EVENTS[1:5] + [
            ev(T("08:00:00"), "EngineerProgress", Engineers=[{"Engineer": "Felicity Farseer", "Progress": "Unlocked", "Rank": 5}]),
            ev(T("08:01:00"), "MissionAccepted", MissionID=1, Name="Mission_A", LocalisedName="A job")])
        j.materials = {"counts": {"arsenic": 4}, "names": {}}
        with unittest.mock.patch.object(C, "time", types.SimpleNamespace(time=lambda: NOW)):   # the sessions' 30 days
            (_, pro), (_, inv), (_, eng), (_, mis), (_, ses) = self._get(state, ("profile", "inventory", "engineering", "missions", "sessions"))
        self.assertEqual((pro["profile"]["commander"], len(pro["profile"]["fleet"])), ("Tester", 4))
        self.assertEqual((len(inv["ships"]["ships"]), len(inv["modules"]["modules"]), len(inv["suits"])), (4, 3, 1))
        fsd = next(b for b in eng["blueprints"] if b["id"] == "FSD_LongRange")
        self.assertEqual([m["have"] for m in fsd["grades"][-1]["materials"] if m["id"] == "arsenic"], [4])
        self.assertEqual(eng["engineers"], [{"name": "Felicity Farseer", "progress": "Unlocked", "rank": 5}])
        self.assertTrue(all(e["ready"] for g in fsd["grades"] for e in g["engineers"] if e["name"] == "Felicity Farseer"))
        self.assertEqual([m["name"] for m in mis["missions"]], ["A job"])
        self.assertEqual((ses["sessions"][0]["combat"]["kills"], ses["totals"]["combat"]["sessions"]), (3, 1))

    def test_an_error_is_the_servers_to_log(self):
        """No local 500: json_errors answers {error, code: server_error} and prints the traceback for Show log."""
        import contextlib
        import io
        _, state = setup(self)
        state.commander_inventory = lambda: (_ for _ in ()).throw(ValueError("a line nobody expected"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            [(status, body)] = self._get(state, ("inventory",))
        self.assertEqual((status, body["code"]), (500, "server_error"))
        self.assertIn("a line nobody expected", body["error"])
        self.assertIn("Traceback", err.getvalue())

    def test_the_real_server_has_them(self):
        _, state = setup(self)
        paths = {r.resource.canonical for r in ed_outrider.make_app(state).router.routes()}
        for part in ("profile", "inventory", "engineering", "missions", "sessions"):
            self.assertIn(f"/api/commander/{part}", paths)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(C.__file__), "jscan.py")))   # no file scanning left


if __name__ == "__main__":
    unittest.main()
