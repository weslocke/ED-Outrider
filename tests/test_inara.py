"""Unit tests: Inara's commander-profile uploads (outrider/inara.py; project/PLAN-inara-2026-10-11.md). What journal
lines become, the batching, the request and Inara's answers, the per-commander record of what was sent, and the
server's side (keys, the switch, the dry run). Nothing is sent anywhere.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import json
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.inara as I  # noqa: E402
import outrider.uploads as U  # noqa: E402
from outrider.core import iso_ts  # noqa: E402

T0 = "2026-10-11T10:00:00Z"


def ts(n):
    """The n-th second after T0."""
    return iso_ts(time.mktime(time.strptime(T0, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone + n)


def login(n=0, cmdr="Briadin", **kw):
    return [{"timestamp": ts(n), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1", "build": "r332841/r0 "},
            {"timestamp": ts(n), "event": "Commander", "FID": "F123", "Name": cmdr},
            dict({"timestamp": ts(n), "event": "LoadGame", "FID": "F123", "Commander": cmdr, "Odyssey": True,
                  "Ship": "mandalay", "ShipID": 74, "ShipName": "Wanderer", "ShipIdent": "WS-01",
                  "Credits": 24_000_000_000, "Loan": 0}, **kw)]


def jump(n, name="Sys A", dist=42.5, **kw):
    return dict({"timestamp": ts(n), "event": "FSDJump", "StarSystem": name, "SystemAddress": 77, "StarPos": [1.0, 2.0, 3.0],
                 "JumpDist": dist}, **kw)


class Feed:
    """A session fed like the hub's, and what each line builds for Inara."""

    def __init__(self):
        self.session, self.sent = U.Session(), I.Sent()

    def __call__(self, *events):
        out = []
        for ev in events:
            self.session.feed(ev, "Journal.2026-10-11T100000.01.log")
            out += I.build(ev, self.session, self.sent)
        return out


def names(built):
    return [n for n, _ in built]


def data(built, name):
    return [m["eventData"] for n, m in built if n == name]


class Travel(unittest.TestCase):
    """Batch B: the flight log (jumps, carrier jumps, docking, landing) and the current location."""

    def test_jump_with_the_ship_flown(self):
        f = Feed()
        f(*login())
        got = f(jump(10))
        self.assertEqual(names(got), ["addCommanderTravelFSDJump"])
        self.assertEqual(data(got, "addCommanderTravelFSDJump")[0],
                         {"starsystemName": "Sys A", "starsystemCoords": [1.0, 2.0, 3.0], "jumpDistance": 42.5,
                          "shipType": "mandalay", "shipGameID": 74})
        self.assertEqual(got[0][1]["eventTimestamp"], ts(10))   # the journal's own time
        self.assertEqual(got[0][1]["_fid"], "F123")             # for the request's header

    def test_carrier_jump_location_and_landing(self):
        f = Feed()
        f(*login())
        got = f({"timestamp": ts(5), "event": "CarrierJump", "Docked": True, "StationName": "G0X-85Z", "MarketID": 3700251648,
                 "StarSystem": "Sys B", "SystemAddress": 78, "StarPos": [4.0, 5.0, 6.0]})
        self.assertEqual(data(got, "addCommanderTravelCarrierJump")[0],
                         {"starsystemName": "Sys B", "starsystemCoords": [4.0, 5.0, 6.0], "stationName": "G0X-85Z",
                          "marketID": 3700251648, "shipType": "mandalay", "shipGameID": 74})
        got = f({"timestamp": ts(9), "event": "Touchdown", "PlayerControlled": True, "StarSystem": "Sys B", "Body": "Sys B 1 a",
                 "Latitude": 12.5, "Longitude": -40.25})
        self.assertEqual(data(got, "addCommanderTravelLand")[0],
                         {"starsystemName": "Sys B", "starsystemBodyName": "Sys B 1 a", "starsystemBodyCoords": [12.5, -40.25],
                          "shipType": "mandalay", "shipGameID": 74})
        self.assertEqual(f({"timestamp": ts(12), "event": "Touchdown", "PlayerControlled": False, "Body": "X"}), [])   # recalled ship
        got = f({"timestamp": ts(20), "event": "Location", "Docked": True, "StationName": "Hub", "MarketID": 5, "StarSystem": "Sys C",
                 "SystemAddress": 79, "StarPos": [0.0, 0.0, 0.0]})
        self.assertEqual(data(got, "setCommanderTravelLocation")[0],
                         {"starsystemName": "Sys C", "starsystemCoords": [0.0, 0.0, 0.0], "stationName": "Hub", "marketID": 5})
        got = f({"timestamp": ts(30), "event": "SupercruiseExit", "StarSystem": "Sys C", "Body": "Sys C 2", "BodyType": "Planet"})
        self.assertEqual(data(got, "setCommanderTravelLocation")[0], {"starsystemName": "Sys C", "starsystemBodyName": "Sys C 2"})

    def test_dock_after_jumping_straight_out(self):
        """A hyperspace jump charged in normal space writes no SupercruiseEntry: the first dock in the new system is a
        real one (review 2026-10-11)."""
        f = Feed()
        f(*login())
        f({"timestamp": ts(1), "event": "Location", "Docked": True, "StationName": "G0X-85Z", "MarketID": 3700251648,
           "StarSystem": "Sys A", "SystemAddress": 77, "StarPos": [1.0, 2.0, 3.0]})
        f({"timestamp": ts(5), "event": "Undocked", "StationName": "G0X-85Z", "MarketID": 3700251648})
        f(jump(60, name="Sys B"))
        got = f({"timestamp": ts(120), "event": "Docked", "StationName": "Station X", "MarketID": 9, "StarSystem": "Sys B",
                 "SystemAddress": 78})
        self.assertEqual(data(got, "addCommanderTravelDock")[0]["stationName"], "Station X")

    def test_docking_is_logged_once(self):
        """EDMC's rules: no docking at a login docked (the Location says so), after a ship swap, or on docking again
        where you undocked without entering supercruise; a real docking is logged."""
        f = Feed()
        f(*login())
        dock = lambda n, st="Hub": {"timestamp": ts(n), "event": "Docked", "StationName": st, "MarketID": 5, "StarSystem": "Sys"}
        f({"timestamp": ts(1), "event": "Location", "Docked": True, "StationName": "Hub", "MarketID": 5, "StarSystem": "Sys",
           "SystemAddress": 1, "StarPos": [0, 0, 0]})
        self.assertEqual(f(dock(2)), [])                                     # the login's
        f({"timestamp": ts(3), "event": "Undocked", "StationName": "Hub"})
        self.assertEqual(f(dock(4)), [])                                     # back on the pad, never left
        f({"timestamp": ts(5), "event": "Undocked", "StationName": "Hub"}, {"timestamp": ts(6), "event": "SupercruiseEntry"})
        got = f(dock(9, "Other"))
        self.assertEqual(data(got, "addCommanderTravelDock")[0],
                         {"starsystemName": "Sys", "stationName": "Other", "marketID": 5, "shipType": "mandalay", "shipGameID": 74})
        f({"timestamp": ts(10), "event": "ShipyardSwap", "ShipType": "anaconda", "ShipID": 3})
        self.assertEqual(f(dock(11, "Other")), [])                           # a swap writes one
        f({"timestamp": ts(12), "event": "Undocked"}, {"timestamp": ts(13), "event": "SupercruiseEntry"})
        self.assertEqual(data(f(dock(20, "Third")), "addCommanderTravelDock")[0]["shipType"], "anaconda")   # the new ship

    def test_taxis(self):
        f = Feed()
        f(*login())
        f({"timestamp": ts(1), "event": "BookTaxi", "Cost": 0})
        self.assertEqual(data(f(jump(5, Taxi=True)), "addCommanderTravelFSDJump")[0]["isTaxiShuttle"], True)
        f({"timestamp": ts(6), "event": "BookDropship", "Cost": 0})
        got = data(f(jump(9, Taxi=True)), "addCommanderTravelFSDJump")[0]
        self.assertEqual((got.get("isTaxiDropship"), "shipType" in got), (True, False))   # not the ship you own


RANK = {"event": "Rank", "Combat": 5, "Trade": 11, "Explore": 10, "Soldier": 0, "Exobiologist": 7, "Empire": 12, "Federation": 12, "CQC": 1}
PROGRESS = {"event": "Progress", "Combat": 6, "Trade": 98, "Explore": 35, "Soldier": 0, "Exobiologist": 51, "Empire": 7, "Federation": 13, "CQC": 11}
LOADOUT = {"event": "Loadout", "Ship": "explorer_nx", "ShipID": 39, "ShipName": " ", "ShipIdent": "BR-03E", "ModulesValue": 21751050,
           "HullHealth": 1.0, "UnladenMass": 1295.875, "CargoCapacity": 64, "MaxJumpRange": 82.96756,
           "FuelCapacity": {"Main": 160.0, "Reserve": 1.14}, "Rebuy": 1087554,
           "Modules": [{"Slot": "TinyHardpoint1", "Item": "hpt_heatsinklauncher_turret_tiny", "On": True, "Priority": 1,
                        "AmmoInClip": 1, "AmmoInHopper": 2, "Health": 1.0},
                       {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size5_class5", "On": True, "Priority": 0,
                        "Health": 1.0, "Value": 5103950,
                        "Engineering": {"Engineer": "Felicity Farseer", "EngineerID": 300100, "BlueprintID": 128673694,
                                        "BlueprintName": "FSD_LongRange", "Level": 5, "Quality": 1.0,
                                        "ExperimentalEffect": "special_fsd_heavy", "Modifiers": [
                                            {"Label": "Mass", "Value": 26.0, "OriginalValue": 20.0, "LessIsGood": 1},
                                            {"Label": "FSDOptimalMass", "Value": 2850.0, "OriginalValue": 1500.0, "LessIsGood": 0}]}}]}


class Profile(unittest.TestCase):
    """Batch C: every rank and its progress, engineers, Powerplay, credits and statistics once per session, the ship
    flown and its loadout; each only when it changed since the profile last got it."""

    def test_all_ranks_once(self):
        f = Feed()
        f(*login())
        got = f(dict(RANK, timestamp=ts(1)), dict(PROGRESS, timestamp=ts(1)))
        ranks, progress = data(got, "setCommanderRankPilot")
        self.assertEqual({r["rankName"]: r["rankValue"] for r in ranks},
                         {"combat": 5, "trade": 11, "explore": 10, "soldier": 0, "exobiologist": 7, "empire": 12, "federation": 12, "cqc": 1})
        self.assertEqual({r["rankName"]: r["rankProgress"] for r in progress}["exobiologist"], 0.51)
        self.assertEqual(f(*login(100), dict(RANK, timestamp=ts(101)), dict(PROGRESS, timestamp=ts(101))), [])   # next login: nothing new
        got = f(dict(PROGRESS, timestamp=ts(200), Explore=36))
        self.assertEqual(data(got, "setCommanderRankPilot"), [[{"rankName": "explore", "rankProgress": 0.36}]])   # only what moved
        got = f({"timestamp": ts(300), "event": "Promotion", "Exobiologist": 8})
        self.assertEqual(data(got, "setCommanderRankPilot"), [[{"rankName": "exobiologist", "rankValue": 8, "rankProgress": 0}]])

    def test_engineers_and_powerplay(self):
        f = Feed()
        f(*login())
        eng = {"timestamp": ts(1), "event": "EngineerProgress", "Engineers": [
            {"Engineer": "Hera Tani", "EngineerID": 300090, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Liz Ryder", "EngineerID": 300080, "Progress": "Invited"}]}
        self.assertEqual(data(f(eng), "setCommanderRankEngineer")[0],
                         [{"engineerName": "Hera Tani", "rankStage": "Unlocked", "rankValue": 5},
                          {"engineerName": "Liz Ryder", "rankStage": "Invited"}])
        self.assertEqual(f(dict(eng, timestamp=ts(50))), [])
        got = f({"timestamp": ts(60), "event": "EngineerProgress", "Engineer": "Liz Ryder", "EngineerID": 300080, "Progress": "Unlocked", "Rank": 1})
        self.assertEqual(data(got, "setCommanderRankEngineer"), [[{"engineerName": "Liz Ryder", "rankStage": "Unlocked", "rankValue": 1}]])
        pp = {"timestamp": ts(2), "event": "Powerplay", "Power": "Nakato Kaine", "Rank": 17, "Merits": 117279, "TimePledged": 27174494}
        self.assertEqual(data(f(pp), "setCommanderRankPower"), [{"powerName": "Nakato Kaine", "rankValue": 17, "meritsValue": 117279}])
        self.assertEqual(f({"timestamp": ts(3), "event": "PowerplayMerits", "Power": "Nakato Kaine", "MeritsGained": 50, "TotalMerits": 117329}), [])
        self.assertEqual(data(f({"timestamp": ts(4), "event": "PowerplayRank", "Power": "Nakato Kaine", "Rank": 18}), "setCommanderRankPower"),
                         [{"powerName": "Nakato Kaine", "rankValue": 18}])
        self.assertEqual(data(f({"timestamp": ts(5), "event": "PowerplayLeave", "Power": "Nakato Kaine"}), "setCommanderRankPower"),
                         [{"powerName": "Nakato Kaine", "rankValue": -1}])
        self.assertEqual(data(f({"timestamp": ts(6), "event": "PowerplayDefect", "FromPower": "Nakato Kaine", "ToPower": "Aisling Duval"}),
                              "setCommanderRankPower"), [{"powerName": "Aisling Duval", "rankValue": 1}])

    def test_credits_and_statistics_once_per_session(self):
        f = Feed()
        f(*login())
        stats = {"timestamp": ts(5), "event": "Statistics", "Bank_Account": {"Current_Wealth": 24695570786, "Spent_On_Ships": 1},
                 "Exploration": {"Systems_Visited": 4000}}
        got = f(stats)
        self.assertEqual(data(got, "setCommanderCredits"), [{"commanderCredits": 24_000_000_000, "commanderLoan": 0, "commanderAssets": 24695570786}])
        self.assertEqual(data(got, "setCommanderGameStatistics"), [{"Bank_Account": {"Current_Wealth": 24695570786, "Spent_On_Ships": 1},
                                                                    "Exploration": {"Systems_Visited": 4000}}])
        self.assertEqual(f({"timestamp": ts(9), "event": "MarketSell", "TotalSale": 5000}), [])   # never Outrider's own sums
        self.assertEqual(f(*login(100), dict(stats, timestamp=ts(105))), [])                    # nothing changed
        got = f(*login(200, Credits=25_000_000_000), dict(stats, timestamp=ts(205)))
        self.assertEqual(data(got, "setCommanderCredits")[0]["commanderCredits"], 25_000_000_000)

    def test_ship_and_loadout_when_changed(self):
        f = Feed()
        f(*login())
        got = f(dict(LOADOUT, timestamp=ts(5)))
        self.assertEqual(data(got, "setCommanderShip"), [{"shipType": "explorer_nx", "shipGameID": 39, "shipIdent": "BR-03E",
                                                          "isCurrentShip": True, "shipModulesValue": 21751050, "shipRebuyCost": 1087554,
                                                          "shipMaxJumpRange": 82.96756, "shipCargoCapacity": 64}])   # " ": no name
        loadout = data(got, "setCommanderShipLoadout")[0]
        self.assertEqual((loadout["shipType"], loadout["shipGameID"], len(loadout["shipLoadout"])), ("explorer_nx", 39, 2))
        self.assertEqual(loadout["shipLoadout"][1], {
            "slotName": "FrameShiftDrive", "itemName": "int_hyperdrive_overcharge_size5_class5", "itemValue": 5103950, "itemHealth": 1.0,
            "isOn": True, "itemPriority": 0, "engineering": {
                "blueprintName": "FSD_LongRange", "blueprintLevel": 5, "blueprintQuality": 1.0, "experimentalEffect": "special_fsd_heavy",
                "modifiers": [{"name": "Mass", "value": 26.0, "originalValue": 20.0, "lessIsGood": True},
                              {"name": "FSDOptimalMass", "value": 2850.0, "originalValue": 1500.0, "lessIsGood": False}]}})
        self.assertEqual(f(dict(LOADOUT, timestamp=ts(50))), [])                        # the same again: nothing
        other = dict(LOADOUT, timestamp=ts(60), Ship="mandalay", ShipID=74, Modules=LOADOUT["Modules"][:1])
        self.assertEqual(names(f(other)), ["setCommanderShip", "setCommanderShipLoadout"])
        self.assertEqual(names(f(dict(LOADOUT, timestamp=ts(70)))), ["setCommanderShip"])   # back to 39: current again, same loadout


class ReputationAndInventory(unittest.TestCase):
    """Batch C2: superpower and faction reputation; materials, the ship's hold and the ship locker as whole snapshots at
    the moments a batch goes, only when changed; never the SRV's hold or the fleet carrier's."""

    def test_reputation(self):
        f = Feed()
        f(*login())
        got = f({"timestamp": ts(1), "event": "Reputation", "Empire": 75.0, "Federation": 75.0, "Independent": 1.01452})
        self.assertEqual(data(got, "setCommanderReputationMajorFaction"),
                         [[{"majorfactionName": "empire", "majorfactionReputation": 0.75}, {"majorfactionName": "federation",
                           "majorfactionReputation": 0.75}, {"majorfactionName": "independent", "majorfactionReputation": 0.0101}]])
        got = f(jump(10, Factions=[{"Name": "Inara Nexus", "MyReputation": 42.5}, {"Name": "Others", "MyReputation": 0.0}]))
        self.assertEqual(data(got, "setCommanderReputationMinorFaction"),
                         [[{"minorfactionName": "Inara Nexus", "minorfactionReputation": 0.425}, {"minorfactionName": "Others", "minorfactionReputation": 0.0}]])
        got = f(jump(20, Factions=[{"Name": "Inara Nexus", "MyReputation": 50.0}, {"Name": "Others", "MyReputation": 0.0}]))
        self.assertEqual(data(got, "setCommanderReputationMinorFaction"), [[{"minorfactionName": "Inara Nexus", "minorfactionReputation": 0.5}]])
        self.assertEqual(data(f(jump(30)), "setCommanderReputationMinorFaction"), [])   # out in the black: no factions

    def test_materials_at_release_points_only(self):
        f = Feed()
        f(*login())
        f({"timestamp": ts(1), "event": "Materials", "Raw": [{"Name": "iron", "Count": 10}], "Manufactured": [], "Encoded": [
            {"Name": "bulkscandata", "Name_Localised": "Anomalous Bulk Scan Data", "Count": 3}]})
        pick = {"timestamp": ts(5), "event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3}
        self.assertEqual(f(pick, dict(pick, timestamp=ts(6))), [])          # never per pickup
        got = f(jump(10))
        self.assertEqual(data(got, "setCommanderInventoryMaterials"),
                         [[{"itemName": "bulkscandata", "itemCount": 3}, {"itemName": "iron", "itemCount": 16}]])   # folded
        self.assertEqual(data(f(jump(20)), "setCommanderInventoryMaterials"), [])   # unchanged

    def test_cargo_and_locker(self):
        f = Feed()
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        f.session.dir = d
        f(*login())
        short = {"timestamp": ts(3), "event": "Cargo", "Vessel": "Ship", "Count": 2}       # contents in Cargo.json
        with open(os.path.join(d, "Cargo.json"), "w") as fh:
            json.dump(dict(short, Inventory=[{"Name": "gold", "Count": 1, "Stolen": 0}, {"Name": "drones", "Name_Localised": "Limpet", "Count": 1, "Stolen": 0}]), fh)
        locker = {"timestamp": ts(2), "event": "ShipLocker", "Items": [], "Components": [{"Name": "graphene", "OwnerID": 0, "Count": 15}],
                  "Consumables": [], "Data": []}
        f(locker)
        got = f(short)                                                       # the login's last line: they go
        self.assertEqual(data(got, "setCommanderInventoryCargo"), [[{"itemName": "gold", "itemCount": 1}, {"itemName": "drones", "itemCount": 1}]])
        self.assertEqual(names(got), ["setCommanderInventoryCargo", "resetCommanderInventory", "setCommanderInventory"])
        self.assertEqual(data(got, "resetCommanderInventory"), [[{"itemType": k} for k in I.LOCKER]])
        self.assertEqual(data(got, "setCommanderInventory"), [[{"itemName": "graphene", "itemCount": 15, "itemType": "Components"}]])
        got = f({"timestamp": ts(5), "event": "Cargo", "Vessel": "SRV", "Count": 4, "Inventory": [{"Name": "gold", "Count": 4}]}, jump(10))
        self.assertEqual(names(got), ["addCommanderTravelFSDJump"])          # the SRV's hold: nothing (the ship's is unchanged)
        got = f({"timestamp": ts(20), "event": "Cargo", "Vessel": "Ship", "Count": 0, "Inventory": []}, jump(30))
        self.assertEqual(data(got, "setCommanderInventoryCargo"), [[]])      # sold it all: the hold is emptied there too

    def test_never_the_carrier(self):
        f = Feed()
        f(*login())
        got = f({"timestamp": ts(1), "event": "CargoTransfer", "Transfers": [{"Type": "tritium", "Count": 500, "Direction": "tocarrier"}]},
                {"timestamp": ts(2), "event": "CarrierDepositFuel", "CarrierID": 3700251648, "Amount": 500, "Total": 1000},
                {"timestamp": ts(3), "event": "CarrierStats", "CarrierID": 3700251648, "Callsign": "G0X-85Z"},
                {"timestamp": ts(4), "event": "Market", "MarketID": 3700251648, "StationType": "FleetCarrier"},
                {"timestamp": ts(5), "event": "CarrierTradeOrder", "CarrierID": 3700251648, "Commodity": "platinum", "SaleOrder": 1000})
        self.assertEqual(got, [])
        sent = json.dumps(f(jump(9)))
        self.assertNotIn("tritium", sent)
        self.assertNotIn("platinum", sent)


class Fleet(unittest.TestCase):
    """Batch D: ships bought, sold, swapped, sent elsewhere and renamed; the fleet's places; the stored modules."""

    def docked(self):
        f = Feed()
        f(*login())
        f({"timestamp": ts(1), "event": "Location", "Docked": True, "StationName": "Jameson Memorial", "MarketID": 128666762,
           "StarSystem": "Shinrarta Dezhra", "SystemAddress": 3932277478106, "StarPos": [55.7, 17.6, 27.2]})
        return f

    def test_buy_new_sell_swap(self):
        f = self.docked()
        here = {"starsystemName": "Shinrarta Dezhra", "stationName": "Jameson Memorial", "marketID": 128666762}
        got = f({"timestamp": ts(10), "event": "ShipyardBuy", "ShipType": "explorer_nx", "ShipPrice": 170990782, "StoreOldShip": "Explorer_NX",
                 "StoreShipID": 39, "MarketID": 128666762},
                {"timestamp": ts(11), "event": "ShipyardNew", "ShipType": "explorer_nx", "NewShipID": 50})
        self.assertEqual([(n, m["eventData"]) for n, m in got],
                         [("setCommanderShip", dict({"shipType": "Explorer_NX", "shipGameID": 39}, **here)),
                          ("addCommanderShip", {"shipType": "explorer_nx", "shipGameID": 50})])
        got = f({"timestamp": ts(20), "event": "ShipyardBuy", "ShipType": "hauler", "ShipPrice": 46262, "SellOldShip": "SideWinder",
                 "SellShipID": 2, "SellPrice": 35600, "MarketID": 128666762})
        self.assertEqual(data(got, "delCommanderShip"), [{"shipType": "SideWinder", "shipGameID": 2}])
        self.assertEqual(data(f({"timestamp": ts(30), "event": "ShipyardSell", "ShipType": "adder", "SellShipID": 6, "ShipPrice": 79027,
                                 "System": "Eranin", "MarketID": 1}), "delCommanderShip"), [{"shipType": "adder", "shipGameID": 6}])
        self.assertEqual(data(f({"timestamp": ts(31), "event": "SellShipOnRebuy", "ShipType": "dolphin", "System": "Shinrarta Dezhra",
                                 "SellShipId": 4, "ShipPrice": 4110183}), "delCommanderShip"), [{"shipType": "dolphin", "shipGameID": 4}])
        got = f({"timestamp": ts(40), "event": "ShipyardSwap", "ShipType": "explorer_nx", "ShipID": 50, "StoreOldShip": "Explorer_NX",
                 "StoreShipID": 39, "MarketID": 128666762})
        self.assertEqual(data(got, "setCommanderShip"), [dict({"shipType": "Explorer_NX", "shipGameID": 39}, **here)])   # the old one, stored

    def test_transfer_rename_fleet_and_modules(self):
        f = self.docked()
        got = f({"timestamp": ts(10), "event": "ShipyardTransfer", "ShipType": "Explorer_NX", "ShipID": 39, "System": "Sol",
                 "ShipMarketID": 1, "Distance": 5365.6, "TransferPrice": 7007804, "TransferTime": 53956, "MarketID": 128666762})
        self.assertEqual(data(got, "setCommanderShipTransfer"), [{"shipType": "Explorer_NX", "shipGameID": 39, "transferTime": 53956,
                                                                   "starsystemName": "Shinrarta Dezhra", "stationName": "Jameson Memorial",
                                                                   "marketID": 128666762}])
        got = f({"timestamp": ts(11), "event": "SetUserShipName", "Ship": "explorer_nx", "ShipID": 50, "UserShipName": "Rhinocart", "UserShipId": "br-rhi"})
        self.assertEqual(data(got, "setCommanderShip"), [{"shipType": "explorer_nx", "shipGameID": 50, "shipName": "Rhinocart", "shipIdent": "br-rhi"}])
        stored = {"timestamp": ts(20), "event": "StoredShips", "StationName": "G0X-85Z", "MarketID": 3700251648, "StarSystem": "Smojooe AR-E b25-8",
                  "ShipsHere": [{"ShipID": 43, "ShipType": "smallcombat01_nx", "Value": 111697, "Hot": False}],
                  "ShipsRemote": [{"ShipID": 7, "ShipType": "type9", "Name": "Hauler", "StarSystem": "Sol", "ShipMarketID": 128016640,
                                   "TransferPrice": 1, "TransferTime": 2, "Value": 3, "Hot": False},
                                  {"ShipID": 8, "ShipType": "cutter", "InTransit": True, "Value": 3, "Hot": False}]}
        got = f(stored)
        self.assertEqual(data(got, "setCommanderShip"), [
            {"shipType": "smallcombat01_nx", "shipGameID": 43, "isHot": False, "starsystemName": "Smojooe AR-E b25-8", "stationName": "G0X-85Z",
             "marketID": 3700251648},
            {"shipType": "type9", "shipGameID": 7, "shipName": "Hauler", "isHot": False, "starsystemName": "Sol", "marketID": 128016640},
            {"shipType": "cutter", "shipGameID": 8, "isHot": False}])
        self.assertEqual(f(dict(stored, timestamp=ts(30))), [])            # the fleet as it was: nothing
        mods = {"timestamp": ts(40), "event": "StoredModules", "MarketID": 3700251648, "StationName": "G0X-85Z", "StarSystem": "Smojooe AR-E b25-8",
                "Items": [{"Name": "$hpt_multicannon_fixed_medium_name;", "Name_Localised": "Multi-Cannon", "StorageSlot": 3,
                           "StarSystem": "Smojooe AR-E b25-8", "MarketID": 3700251648, "TransferCost": 0, "TransferTime": 0, "BuyPrice": 0,
                           "Hot": False, "EngineerModifications": "Weapon_RapidFire", "Level": 1, "Quality": 0.9569},
                          {"Name": "$int_dronecontrol_collection_size1_class5_name;", "StorageSlot": 1, "InTransit": True, "BuyPrice": 9600, "Hot": False}]}
        got = data(f(mods), "setCommanderStorageModules")[0]
        self.assertEqual([m["itemName"] for m in got], ["$int_dronecontrol_collection_size1_class5_name;", "$hpt_multicannon_fixed_medium_name;"])
        self.assertEqual(got[1]["engineering"], {"blueprintName": "Weapon_RapidFire", "blueprintLevel": 1, "blueprintQuality": 0.9569})
        self.assertEqual(f(dict(mods, timestamp=ts(50))), [])
        self.assertEqual(data(f(dict(mods, timestamp=ts(60), Items=[])), "setCommanderStorageModules"), [[]])   # all fitted again: emptied


class CommunityGoals(unittest.TestCase):
    """Batch E: every goal taken part in (exploration and biology ones too), the goal then your progress, changed only."""

    def test_goal_and_progress(self):
        f = Feed()
        f(*login())
        cg = {"timestamp": ts(5), "event": "CommunityGoal", "CurrentGoals": [{
            "CGID": 849, "Title": "Frontline Solutions Calls for Critical Supplies to Complete Runner Production", "SystemName": "HIP 58412",
            "MarketName": "Pawelczyk Dock", "Expiry": "2026-06-18T09:00:00Z", "IsComplete": True, "CurrentTotal": 195710083,
            "PlayerContribution": 24, "NumContributors": 20866, "TopTier": {"Name": "Tier 5", "Bonus": ""}, "TopRankSize": 10,
            "PlayerInTopRank": False, "TierReached": "Tier 4", "PlayerPercentileBand": 100, "Bonus": 50000000}]}
        got = f(cg)
        self.assertEqual(names(got), ["setCommunityGoal", "setCommanderCommunityGoalProgress"])   # the goal first, as Inara asks
        self.assertEqual(data(got, "setCommunityGoal")[0], {
            "communitygoalGameID": 849, "communitygoalName": "Frontline Solutions Calls for Critical Supplies to Complete Runner Production",
            "starsystemName": "HIP 58412", "stationName": "Pawelczyk Dock", "goalExpiry": "2026-06-18T09:00:00Z", "tierReached": 4, "tierMax": 5,
            "topRankSize": 10, "isCompleted": True, "contributorsNum": 20866, "contributionsTotal": 195710083})
        self.assertEqual(data(got, "setCommanderCommunityGoalProgress")[0], {"communitygoalGameID": 849, "contribution": 24,
                                                                              "percentileBand": 100, "percentileBandReward": 50000000,
                                                                              "isTopRank": False})
        self.assertEqual(f(dict(cg, timestamp=ts(60))), [])     # written again, nothing changed: nothing sent
        more = json.loads(json.dumps(cg))
        more["timestamp"], more["CurrentGoals"][0]["PlayerContribution"] = ts(90), 30
        self.assertEqual(names(f(more)), ["setCommanderCommunityGoalProgress"])   # only your part moved


class MissionsCombatFriendsSuits(unittest.TestCase):
    """Batch E2 (parity with EDMC's Inara plugin): missions and permits, the combat log, friends, suit loadouts. Shapes
    from the author's journals; PVPKill, Friends and MissionFailed, which they never wrote, from the journal manual."""

    def setUp(self):
        self.f = Feed()
        self.f(*login(), {"timestamp": ts(1), "event": "Location", "Docked": True, "StationName": "Hub", "MarketID": 5,
                          "StarSystem": "HIP 8825", "SystemAddress": 3382253228738, "StarPos": [0, 0, 0]})

    def test_missions_and_permits(self):
        acc = {"timestamp": ts(10), "event": "MissionAccepted", "Faction": "Revolutionary Party of HIP 8825",
               "Name": "Mission_PassengerBulk_Evacuation_POLITICIAN_LEAVING", "LocalisedName": "117 Politicians Require Evacuation",
               "DestinationSystem": "Cephei Sector CQ-Y b3", "DestinationStation": "Ronald Reagan Memorial", "Expiry": "2026-05-02T19:19:28Z",
               "Wing": False, "Influence": "++", "Reputation": "++", "Reward": 6044860, "PassengerCount": 117, "PassengerVIPs": False,
               "PassengerWanted": False, "PassengerType": "Politician", "MissionID": 1053233941}
        self.assertEqual(data(self.f(acc), "addCommanderMission"), [{
            "missionName": "Mission_PassengerBulk_Evacuation_POLITICIAN_LEAVING", "missionGameID": 1053233941, "influenceGain": "++",
            "reputationGain": "++", "starsystemNameOrigin": "HIP 8825", "stationNameOrigin": "Hub",
            "minorfactionNameOrigin": "Revolutionary Party of HIP 8825", "missionExpiry": "2026-05-02T19:19:28Z",
            "starsystemNameTarget": "Cephei Sector CQ-Y b3", "stationNameTarget": "Ronald Reagan Memorial", "passengerType": "Politician",
            "passengerCount": 117, "passengerIsVIP": False, "passengerIsWanted": False}])
        done = {"timestamp": ts(20), "event": "MissionCompleted", "Faction": "Revolutionary Party of HIP 8825", "MissionID": 1053233941,
                "Reward": 2234860, "PermitsAwarded": ["Sirius"],
                "MaterialsReward": [{"Name": "SecurityFirmware", "Name_Localised": "Security Firmware Patch", "Count": 16}],
                "FactionEffects": [{"Faction": "Interplanetary Explorations", "Effects": [], "Influence": [
                    {"SystemAddress": 7266413716873, "Trend": "UpGood", "Influence": "++"}, {"SystemAddress": 1, "Influence": "+++"}],
                    "ReputationTrend": "UpGood", "Reputation": "++"}]}
        got = self.f(done)
        self.assertEqual(names(got), ["addCommanderPermit", "setCommanderMissionCompleted"])
        self.assertEqual(data(got, "addCommanderPermit"), [{"starsystemName": "Sirius"}])
        self.assertEqual(data(got, "setCommanderMissionCompleted")[0], {
            "missionGameID": 1053233941, "rewardCredits": 2234860, "rewardPermits": [{"starsystemName": "Sirius"}],
            "rewardMaterials": [{"itemName": "SecurityFirmware", "itemCount": 16}],
            "minorfactionEffects": [{"minorfactionName": "Interplanetary Explorations", "influenceGain": "+++", "reputationGain": "++"}]})
        self.assertEqual(data(self.f({"timestamp": ts(30), "event": "MissionAbandoned", "Name": "x", "MissionID": 7}),
                              "setCommanderMissionAbandoned"), [{"missionGameID": 7}])
        self.assertEqual(data(self.f({"timestamp": ts(31), "event": "MissionFailed", "Name": "x", "MissionID": 8}),
                              "setCommanderMissionFailed"), [{"missionGameID": 8}])

    def test_combat(self):
        got = self.f({"timestamp": ts(10), "event": "Died", "KillerName": "$LUASC_Scenario_Warzone_NPC_SpecOps_A;",
                      "KillerName_Localised": "Spec Ops Wing Alpha", "KillerShip": "ferdelance", "KillerRank": "Elite"})
        self.assertEqual(data(got, "addCommanderCombatDeath"), [{"starsystemName": "HIP 8825", "opponentName": "Spec Ops Wing Alpha"}])
        got = self.f({"timestamp": ts(11), "event": "Died", "Killers": [{"Name": "Cmdr A", "Ship": "x"}, {"Name": "Cmdr B", "Ship": "y"}]})
        self.assertEqual(data(got, "addCommanderCombatDeath"), [{"starsystemName": "HIP 8825", "wingOpponentNames": ["Cmdr A", "Cmdr B"]}])
        got = self.f({"timestamp": ts(12), "event": "Interdicted", "Submitted": True, "Interdictor": "Helena Sigurj", "IsPlayer": False, "Faction": "Sobek Boys"})
        self.assertEqual(data(got, "addCommanderCombatInterdicted"),
                         [{"starsystemName": "HIP 8825", "opponentName": "Helena Sigurj", "isPlayer": False, "isSubmit": True}])
        got = self.f({"timestamp": ts(13), "event": "Interdiction", "Success": True, "IsPlayer": False, "Faction": "Society of Ngalinn"})
        self.assertEqual(data(got, "addCommanderCombatInterdiction"),
                         [{"starsystemName": "HIP 8825", "opponentName": "Society of Ngalinn", "isPlayer": False, "isSuccess": True}])
        got = self.f({"timestamp": ts(14), "event": "EscapeInterdiction", "Interdictor": "Ezekiel", "IsPlayer": False})
        self.assertEqual(data(got, "addCommanderCombatInterdictionEscape"), [{"starsystemName": "HIP 8825", "opponentName": "Ezekiel", "isPlayer": False}])
        got = self.f({"timestamp": ts(15), "event": "PVPKill", "Victim": "Cmdr Loser", "CombatRank": 3})   # the manual's shape
        self.assertEqual(data(got, "addCommanderCombatKill"), [{"starsystemName": "HIP 8825", "opponentName": "Cmdr Loser"}])
        self.assertEqual(self.f({"timestamp": ts(16), "event": "Died"}), [])   # no one named: Inara needs a name

    def test_friends(self):
        fr = lambda n, st: {"timestamp": ts(n), "event": "Friends", "Status": st, "Name": "Cmdr Pal"}   # the manual's shape
        self.assertEqual(data(self.f(fr(10, "Added")), "addCommanderFriend"), [{"commanderName": "Cmdr Pal", "gamePlatform": "pc"}])
        self.assertEqual(self.f(fr(11, "Online"), fr(12, "Offline")), [])     # every login: once is enough
        self.assertEqual(names(self.f(fr(13, "Lost"))), ["delCommanderFriend"])
        self.assertEqual(names(self.f(fr(14, "Online"))), ["addCommanderFriend"])   # friends again
        self.assertEqual(self.f(fr(15, "Requested")), [])

    def test_suit_loadouts(self):
        suit = {"timestamp": ts(10), "event": "SuitLoadout", "SuitID": 1826892828743577, "SuitName": "explorationsuit_class1",
                "SuitName_Localised": "Artemis Suit", "SuitMods": [], "LoadoutID": 4293000001, "LoadoutName": "Xenobio",
                "Modules": [{"SlotName": "PrimaryWeapon1", "SuitModuleID": 1826892921801189, "ModuleName": "wpn_m_sniper_plasma_charged",
                             "ModuleName_Localised": "Manticore Executioner", "Class": 1, "WeaponMods": []}]}
        self.assertEqual(data(self.f(suit), "setCommanderSuitLoadout"), [{
            "loadoutGameID": 4293000001, "loadoutName": "Xenobio", "suitGameID": 1826892828743577, "suitType": "explorationsuit_class1",
            "suitMods": [], "suitLoadout": [{"slotName": "PrimaryWeapon1", "itemName": "wpn_m_sniper_plasma_charged", "itemClass": 1,
                                             "itemGameID": 1826892921801189}]}])
        self.assertEqual(self.f(dict(suit, timestamp=ts(20))), [])     # worn again at the next disembark: nothing
        got = self.f({"timestamp": ts(30), "event": "RenameSuitLoadout", "SuitID": 1826892828743577, "SuitName": "explorationsuit_class1",
                      "LoadoutID": 4293000001, "LoadoutName": "Bio"})
        self.assertEqual(data(got, "updateCommanderSuitLoadout"), [{"loadoutGameID": 4293000001, "loadoutName": "Bio",
                                                                     "suitGameID": 1826892828743577, "suitType": "explorationsuit_class1"}])
        self.assertEqual(names(self.f(dict(suit, timestamp=ts(40), LoadoutName="Bio"))), ["setCommanderSuitLoadout"])   # whole again
        self.assertEqual(data(self.f({"timestamp": ts(50), "event": "DeleteSuitLoadout", "SuitID": 1, "SuitName": "x", "LoadoutID": 4293000001,
                                      "LoadoutName": "Bio"}), "delCommanderSuitLoadout"), [{"loadoutGameID": 4293000001}])


class Batching(unittest.TestCase):
    def test_release_points(self):
        f = Feed()
        for ev in login():
            f(ev)
            self.assertEqual(I.hold(ev, f.session), I.HOLD_S)
        cargo = {"timestamp": ts(3), "event": "Cargo", "Vessel": "Ship", "Count": 0, "Inventory": []}
        f(cargo)
        self.assertEqual(I.hold(cargo, f.session), 0)        # the start-up's lines end: they go together
        f(cargo)
        self.assertEqual(I.hold(cargo, f.session), I.HOLD_S)  # a later Cargo waits for company
        for ev in (jump(9), {"timestamp": ts(10), "event": "Docked"}, {"timestamp": ts(11), "event": "Shutdown"}):
            f(ev)
            self.assertEqual(I.hold(ev, f.session), 0)

    def test_one_commander_per_request(self):
        rows = [{"id": 1, "cmdr": "A"}, {"id": 2, "cmdr": "A"}, {"id": 3, "cmdr": "B"}]
        self.assertEqual([r["id"] for r in I.same_batch(rows)], [1, 2])
        self.assertEqual(len(I.same_batch([{"id": i, "cmdr": "A"} for i in range(250)])), I.BATCH)


class RequestAndAnswer(unittest.TestCase):
    def rows(self):
        f = Feed()
        f(*login())
        built = f(jump(10), jump(70, "Sys B"))
        return [{"id": 10 + i, "cmdr": "Briadin", "message": json.dumps(m)} for i, (_, m) in enumerate(built)]

    def test_request(self):
        body = I.request(self.rows(), "abcd1234efgh5678", "2026.10.21", developing=True)
        self.assertEqual(body["header"], {"appName": "ED Outrider", "appVersion": "2026.10.21", "isBeingDeveloped": True,
                                          "APIkey": "abcd1234efgh5678", "commanderName": "Briadin", "commanderFrontierID": "F123"})
        self.assertEqual([(e["eventName"], e["eventCustomID"]) for e in body["events"]],
                         [("addCommanderTravelFSDJump", 10), ("addCommanderTravelFSDJump", 11)])
        self.assertNotIn("_fid", json.dumps(body["events"]))   # ours, not Inara's

    def test_answers(self):
        rows = self.rows()
        ok = {"header": {"eventStatus": 200}, "events": [{"eventCustomID": 11, "eventStatus": 400, "eventStatusText": "bad"},
                                                         {"eventCustomID": 10, "eventStatus": 204, "eventStatusText": "No change"}]}
        self.assertEqual(I.answer(rows, ok), [(10, "sent", "204 No change", None), (11, "dropped", "400 bad", None)])
        refused = {"header": {"eventStatus": 400, "eventStatusText": "Invalid API key."}}
        self.assertEqual({s for _, s, _, _ in I.answer(rows, refused)}, {"held"})        # the player must act
        self.assertIn("Invalid API key", I.answer(rows, refused)[0][2])
        rate = {"header": {"eventStatus": 400, "eventStatusText": "Slow down, cowboy. Access was temporarily revoked."}}
        self.assertEqual({(s, r) for _, s, _, r in I.answer(rows, rate)}, {("queued", I.RATE_WAIT_S)})
        for bad in (None, [], {"events": []}, {"header": {}}):
            with self.assertRaises(ValueError):
                I.answer(rows, bad)

    def test_keys(self):
        self.assertTrue(I.key_ok("a1B2c3D4e5F6g7H8i9J0"))
        for bad in ("", "short", "has spaces in it at all", "x" * 200, "ключключключключключ", None):
            self.assertFalse(I.key_ok(bad), bad)


class SentRecord(unittest.TestCase):
    def test_changed_and_restored(self):
        saved = []
        s = I.Sent(save=saved.append)
        self.assertTrue(s.changed("A", "ranks", {"combat": 3}))
        self.assertFalse(s.changed("A", "ranks", {"combat": 3}))   # the same: nothing to send
        self.assertTrue(s.changed("B", "ranks", {"combat": 3}))    # another commander's profile
        snap = s.snapshot()
        self.assertTrue(s.changed("A", "ranks", {"combat": 4}))
        s.restore(snap)                                            # a failed tick: as before it
        self.assertTrue(s.changed("A", "ranks", {"combat": 4}))
        self.assertEqual(len(saved), 4)
        self.assertFalse(I.Sent(saved[-1]).changed("A", "ranks", {"combat": 4}))   # read back from the database


class Server(unittest.TestCase):
    """The server's side: the switch, the keys (never served), the sender, the dry run, EDMC's own Inara upload."""

    def setUp(self):
        import types
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        p = unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir])
        p.start()
        self.addCleanup(p.stop)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.game_pc = False
        self.state.config_path = os.path.join(self.dir, "ed_outrider.toml")
        self.path = os.path.join(self.dir, "Journal.2026-10-11T100000.01.log")

    def write(self, *events):
        with open(self.path, "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def rows(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM upload_queue WHERE service='inara' ORDER BY id")]

    def live_login(self):
        now = time.time()
        stamp = lambda ago: iso_ts(now - ago)
        evs = [dict(e, timestamp=stamp(120)) for e in login()]
        self.write(*evs)
        self.j.scan_dir(self.dir, commit_each=True, upload="catchup")
        return stamp

    def test_live_lines_are_queued_and_batched(self):
        stamp = self.live_login()
        self.state.set_upload("inara", True)
        self.write(dict(jump(0), timestamp=stamp(60)), {"timestamp": stamp(50), "event": "SupercruiseExit", "StarSystem": "Sys A"})
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        rows = self.rows()
        self.assertEqual([r["schema"] for r in rows], ["addCommanderTravelFSDJump", "setCommanderTravelLocation"])
        self.assertEqual(rows[0]["next_try"], 0)        # the jump goes now
        self.assertGreater(rows[1]["next_try"], 0)      # the location waits for company (the next jump or docking)
        self.assertEqual(rows[0]["cmdr"], "Briadin")

    def test_keys_never_served_and_the_sender(self):
        import asyncio
        out, status = self.state.set_inara_account("Briadin", "short")
        self.assertEqual(status, 400)
        out, status = self.state.set_inara_account("Briadin", "a1B2c3D4e5F6g7H8i9J0k1L2")
        self.assertEqual((status, out["accounts"][0]["hint"]), (200, "a1B2…k1L2 (24 characters)"))
        summary = json.dumps(self.state.uploads_summary())
        self.assertNotIn("a1B2c3D4e5F6g7H8i9J0k1L2", summary)   # the page never gets the key
        stamp = self.live_login()
        self.state.set_upload("inara", True)
        self.write(dict(jump(0), timestamp=stamp(60)))
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        rows = U.due(self.db, "inara", time.time())
        # the dry run: built and logged without the key, nothing sent
        self.state.inara_dry_path = os.path.join(self.dir, "dry.jsonl")
        with unittest.mock.patch.dict(os.environ, {I.DRY_ENV: "1"}), unittest.mock.patch("sys.stdout"):
            got = asyncio.run(self.state.inara_send(rows))
        self.assertEqual({s for _, s, _, _ in got}, {"dry"})
        with open(self.state.inara_dry_path, encoding="utf-8") as f:
            logged = f.read()
        self.assertIn("addCommanderTravelFSDJump", logged)
        self.assertNotIn("a1B2c3D4e5F6g7H8i9J0k1L2", logged)
        # the commander playing, with no key: held until one is saved (S3-S1), nothing forgotten
        self.state.set_inara_account("Briadin", remove=True)
        self.state.inara_sent.changed("Briadin", "rank:combat", 3)
        self.j.commander = {"name": "Briadin"}
        got = asyncio.run(self.state.inara_send(rows))
        self.assertEqual(got[0][1], "held")
        self.assertIn("no Inara API key for CMDR Briadin", got[0][2])
        self.assertFalse(self.state.inara_sent.changed("Briadin", "rank:combat", 3))
        # a commander not playing, with no key: dropped, and the status says why
        self.j.commander = {"name": "Alt"}
        got = asyncio.run(self.state.inara_send(rows))
        self.assertEqual(got[0][1], "dropped")
        self.assertIn("no Inara API key for CMDR Briadin", got[0][2])
        # what was dropped never arrived: sent again once the key is there (review 2026-10-11)
        self.assertTrue(self.state.inara_sent.changed("Briadin", "rank:combat", 3))
        self.state.set_inara_account("Briadin", "a1B2c3D4e5F6g7H8i9J0k1L2")       # a new key: maybe another profile
        self.assertTrue(self.state.inara_sent.changed("Briadin", "rank:combat", 3))
        self.state.set_inara_account("Briadin", "")                               # the same key kept: nothing resent
        self.assertFalse(self.state.inara_sent.changed("Briadin", "rank:combat", 3))

    def test_a_real_send_and_its_answer(self):
        import asyncio

        class Resp:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def json(self, content_type=None):
                return {"header": {"eventStatus": 200}, "events": [{"eventCustomID": i, "eventStatus": 200} for i in ids]}
        posted = []

        class Session:
            def post(self, url, json=None):
                posted.append((url, json))
                return Resp()
        self.state.set_inara_account("Briadin", "a1B2c3D4e5F6g7H8i9J0k1L2")
        stamp = self.live_login()
        self.state.set_upload("inara", True)
        self.write(dict(jump(0), timestamp=stamp(60)))
        self.j.scan_dir(self.dir, upload="live")
        self.db.commit()
        rows = U.due(self.db, "inara", time.time())
        ids = [r["id"] for r in rows]
        self.state.upload_session = Session()
        with unittest.mock.patch.dict(os.environ, {I.DRY_ENV: "", I.DEV_ENV: "1"}):
            got = asyncio.run(self.state.inara_send(rows))
        self.assertEqual([s for _, s, _, _ in got], ["sent"])
        url, body = posted[0]
        self.assertEqual((url, body["header"]["APIkey"], body["header"]["isBeingDeveloped"]), (I.URL, "a1B2c3D4e5F6g7H8i9J0k1L2", True))

    def test_edmc_sending_to_inara_holds_ours(self):
        self.state.edmc = {"running": True, "eddn": False, "edsm": False, "inara": True}
        self.state.upload_cfg["inara"]["enabled"] = True
        self.assertFalse(self.state.upload_on("inara"))
        self.assertIn("EDMC on this PC sends to Inara", self.state.upload_conflict("inara"))
        self.state.game_pc = True   # EDMC is looked for on the game PC
        with unittest.mock.patch.object(U, "edmc_uploads", lambda: dict(self.state.edmc)):
            self.assertEqual(self.state.check_upload_start("inara", False)[0], "edmc")

    def test_a_failed_tick_sends_nothing_twice(self):
        """What was sent (the Sent record) is in the hub's snapshot, which the tick's checkpoint takes."""
        snap = self.state.uploads_hub.snapshot()
        self.assertTrue(self.state.inara_sent.changed("Briadin", "ranks", {"combat": 1}))
        self.state.uploads_hub.restore(snap)
        self.assertTrue(self.state.inara_sent.changed("Briadin", "ranks", {"combat": 1}))
        self.assertNotIn("inara_sent", ed_outrider.RESET_JOURNAL_DATA)   # live-only: a re-read keeps it
        self.assertNotIn("inara_accounts", ed_outrider.RESET_JOURNAL_DATA)

    def test_endpoint(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = [(await c.post("/api/uploads/inara", json={"commander": "Briadin", "api_key": "a1B2c3D4e5F6g7H8i9J0k1L2"})).status,
                       (await c.post("/api/uploads/inara", json={"commander": "", "api_key": "x"})).status,
                       (await c.post("/api/uploads/inara", data="[1]", headers={"Content-Type": "application/json"})).status]
                j = await (await c.post("/api/uploads", json={"service": "inara", "on": True})).json()
                return out, j
        out, j = asyncio.run(go())
        self.assertEqual(out, [200, 400, 400])
        self.assertTrue(j["inara"]["wanted"])
        self.assertEqual(j["inara"]["accounts"][0]["commander"], "Briadin")
        with open(self.state.config_path, encoding="utf-8") as f:
            self.assertRegex(f.read(), r"\[inara\][^\[]*\nenabled = true")


if __name__ == "__main__":
    unittest.main()
