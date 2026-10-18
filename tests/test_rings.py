"""Rings to mine (Settings → Mining, the author 2026-10-18): a ringed body resolved live is a "ring" moment with its ring
types and reserves, once per body and visit; the page says it when a type is ticked (tests/page_smoke.js, "rings to
mine"). Fakes only."""
import time
import unittest

from support import ed_outrider  # also puts the repository root on sys.path


class Rings(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 300 + s)

    def jump(self, s, name, id64):
        self.j.handle({"event": "FSDJump", "timestamp": self.at(s), "StarSystem": name, "SystemAddress": id64, "StarPos": [0, 0, id64]})

    def scan(self, s, bid, body, rings, reserve="PristineResources", system=("Ring", 9), scan_type="Detailed", ts=None):
        ev = {"event": "Scan", "timestamp": ts or self.at(s), "ScanType": scan_type, "StarSystem": system[0],
              "SystemAddress": system[1], "BodyID": bid, "BodyName": f"{system[0]} {body}", "PlanetClass": "Sudarsky class III gas giant",
              "DistanceFromArrivalLS": 900.0, "WasDiscovered": True, "WasMapped": False,
              "Rings": [{"Name": f"{system[0]} {body} {x[0]} Ring", "RingClass": x[1], "MassMT": 1e10, "InnerRad": 1e8, "OuterRad": 2e8}
                        for x in rings]}
        if reserve:
            ev["ReserveLevel"] = reserve
        self.j.handle(ev)

    def said(self):
        return [(m["system"], m["body"], m["types"], m["reserve"]) for m in self.j.moments if m["kind"] == "ring"]

    def test_once_per_body_and_visit(self):
        self.jump(0, "Ring", 9)
        self.scan(1, 3, "A 3", [("A", "eRingClass_Metalic"), ("B", "eRingClass_Icy")])
        self.scan(2, 5, "A 5", [("A", "eRingClass_Rocky")], reserve="CommonResources")
        self.scan(3, 3, "A 3", [("A", "eRingClass_Metalic"), ("B", "eRingClass_Icy")])   # the rescan after mapping it
        self.scan(4, 7, "A 7", [], reserve=None)                                           # no rings: nothing
        self.assertEqual(self.said(), [("9", "A 3", ["Icy", "Metallic"], "Pristine"), ("9", "A 5", ["Rocky"], "Common")])
        # an asteroid belt is no ring; a reserve level the game has not told is None
        self.j.handle({"event": "Scan", "timestamp": self.at(5), "ScanType": "AutoScan", "StarSystem": "Ring", "SystemAddress": 9,
                       "BodyID": 0, "BodyName": "Ring A", "StarType": "K", "DistanceFromArrivalLS": 0.0,
                       "Rings": [{"Name": "Ring A A Belt", "RingClass": "eRingClass_MetalRich"}]})
        self.scan(6, 8, "A 8", [("A", "eRingClass_MetalRich")], reserve=None)
        self.assertEqual(self.said()[2:], [("9", "A 8", ["Metal Rich"], None)])
        # away and back: a new visit, so each body is news again (its AutoScan or a nav beacon read)
        self.jump(10, "Other", 10)
        self.jump(20, "Ring", 9)
        self.scan(21, 3, "A 3", [("A", "eRingClass_Metalic")], scan_type="AutoScan")
        self.assertEqual(self.said()[3:], [("9", "A 3", ["Metallic"], "Pristine")])
        # a journal read again (not live): never said
        n = len(self.said())
        self.scan(0, 4, "A 4", [("A", "eRingClass_Icy")], ts="2020-01-01T00:00:00Z")
        self.assertEqual(len(self.said()), n)

    def test_a_failed_tick_says_it_once(self):
        """A tick that fails after the scan rolls the memory of having said it back with its moment."""
        self.jump(0, "Ring", 9)
        self.scan(1, 5, "A 5", [("A", "eRingClass_Icy")])      # said before the failed tick: stays said
        cp = self.j.checkpoint()
        self.scan(2, 3, "A 3", [("A", "eRingClass_Metalic")])
        self.j.restore(cp)
        self.assertEqual(self.said(), [("9", "A 5", ["Icy"], "Pristine")])
        self.scan(2, 3, "A 3", [("A", "eRingClass_Metalic")])
        self.scan(3, 5, "A 5", [("A", "eRingClass_Icy")])      # its rescan after mapping: nothing
        self.assertEqual(self.said(), [("9", "A 5", ["Icy"], "Pristine"), ("9", "A 3", ["Metallic"], "Pristine")])

    def test_a_ring_starting_a_sentence_has_its_capital(self):
        import outrider.speech as sp
        self.assertEqual(sp.fill("{ring} at {body}. So: {types} rings. {types}!", {"ring": "a metallic ring", "body": "A 3", "types": "icy"}),
                         "A metallic ring at A 3. So: icy rings. Icy!")

    def test_kept_in_step(self):
        """The page's alert row, its crew member and its lines (the speech registry's side)."""
        import outrider.speech as sp
        self.assertEqual(sp.CREW_ROW_ROLE["ring"], "mining")
        self.assertEqual(sp.ROW_KEYS["ring"], ("ring_found", "ring_found_many"))
        self.assertIn("miningRings", ed_outrider.BROWSER_SETTINGS)
        self.assertEqual(sorted(ed_outrider.RING_CLASSES.values()), sorted(["Icy", "Rocky", "Metallic", "Metal Rich"]))


if __name__ == "__main__":
    unittest.main()
