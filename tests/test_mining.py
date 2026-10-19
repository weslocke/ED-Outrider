"""Mining (branch `mining`, project/PLAN-mining-2026-10-18.md): the limpet reminder on undocking (A). The page's side
(Settings → Mining's switch and its alerts table): tests/page_smoke.js ("mining alerts"). Fakes only."""
import time
import unittest

from support import ed_outrider  # also puts the repository root on sys.path


class LimpetReminder(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 120 + s)

    def loadout(self, s, *items, ship_id=7):
        self.j.handle({"event": "Loadout", "timestamp": self.at(s), "Ship": "python", "ShipID": ship_id, "ShipName": "Digger",
                       "ShipIdent": "DG-01", "CargoCapacity": 128, "MaxJumpRange": 20.0,
                       "Modules": [{"Slot": f"Slot0{i}", "Item": it} for i, it in enumerate(items)]})

    def cargo(self, s, **counts):
        self.j.handle({"event": "Cargo", "timestamp": self.at(s), "Vessel": "Ship", "Count": sum(counts.values()),
                       "Inventory": [{"Name": k, "Count": v, "Stolen": 0} for k, v in counts.items()]})

    def undock(self, s, **kw):
        self.j.handle(dict({"event": "Undocked", "timestamp": self.at(s), "StationName": "Hub", "StationType": "Coriolis",
                            "MarketID": 1, "Taxi": False, "Multicrew": False}, **kw))

    def said(self):
        return [m["what"] for m in self.j.moments if m["kind"] == "limpets"]

    def test_mining_ship_without_limpets(self):
        self.loadout(0, "int_refinery_size4_class5", "int_dronecontrol_collection_size5_class5")
        self.cargo(1, platinum=4)
        self.undock(2)
        self.assertEqual(self.said(), ["none"])
        # limpets aboard: nothing; a taxi or multicrew: nothing
        self.cargo(3, drones=20)
        self.undock(4)
        self.cargo(5)
        self.undock(6, Taxi=True)
        self.undock(7, Multicrew=True)
        self.assertEqual(self.said(), ["none"])

    def test_which_ships_count(self):
        """A refinery, a collector or prospector controller, or a multi-limpet mining or universal one makes a mining ship;
        a ship without them, or whose loadout or hold is not known, says nothing."""
        for i, item in enumerate(("int_refinery_size1_class1", "int_dronecontrol_prospector_size1_class4",
                                  "int_multidronecontrol_mining_size3_class3", "int_multidronecontrol_universal_size7_class5")):
            self.j.moments.clear()
            self.loadout(10 * i, item)
            self.cargo(10 * i + 1)
            self.undock(10 * i + 2)
            self.assertEqual(self.said(), ["none"], item)
        self.j.moments.clear()
        self.loadout(50, "int_fuelscoop_size5_class5", "int_dronecontrol_repair_size3_class5")
        self.cargo(51)
        self.undock(52)
        self.assertEqual(self.said(), [])

    def test_hold_or_ship_unknown_and_old_lines(self):
        j2 = ed_outrider.Journals(self.db)
        self.j = j2
        self.loadout(0, "int_refinery_size4_class5")
        self.undock(1)                      # no Cargo snapshot yet: the hold is not known
        self.assertEqual(self.said(), [])
        self.cargo(2)
        self.j.handle({"event": "Undocked", "timestamp": "2020-01-01T00:00:00Z", "StationName": "Hub", "MarketID": 1})
        self.assertEqual(self.said(), [])   # a journal caught up on: never said


if __name__ == "__main__":
    unittest.main()
