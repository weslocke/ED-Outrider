"""Unit tests: star and planet types as codex entries (outrider/codex_bodies.py; a review suggestion the author picked,
2026-10-12), and the server's marks for Here and Nearby. The pairs are real: the author's journals and EDDN's codex
traffic (EntryID, Name, and the scan of the body).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import time
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.codex_bodies as C  # noqa: E402


def star(code, lum, **kw):
    return dict({"type": "Star", "subtype": ed_outrider.journal_star(code), "luminosity": lum, "ed": {"StarType": code}}, **kw)


def planet(cls, terraformable=False, atmosphere="None", **kw):
    return dict({"type": "Planet", "subtype": ed_outrider.journal_planet(cls), "terraformable": terraformable,
                 "atmosphere": atmosphere, "ed": {"PlanetClass": cls}}, **kw)


class Table(unittest.TestCase):
    def test_stars(self):
        """Luminosity III is the type's Giant entry, I its SuperGiant one; the journal's giant types log theirs whatever
        their class (EDDN's codex entries against the scans of their bodies)."""
        cases = [(("A", "Vb"), 1100301), (("F", "III"), 1100402), (("B", "IIIab"), 1100202), (("O", "I"), 1100103),
                 (("M_RedGiant", "IIIb"), 1100702), (("K_OrangeGiant", "IIab"), 1100602), (("A_BlueWhiteSuperGiant", "II"), 1100303),
                 (("DAB", "VII"), 1102203), (("DC", "VII"), 1102213), (("DQ", "VII"), 1102212), (("N", "VII"), 1102300),
                 (("H", "VII"), 1102400), (("TTS", "Va"), 1101001), (("AeBe", "VI"), 1101101), (("WNC", "I"), 1102104),
                 (("CN", "IIIb"), 1101502), (("Y", "V"), 1101201)]
        self.assertEqual([C.entry_for(star(*k)) for k, _ in cases], [v for _, v in cases])
        self.assertIsNone(C.entry_for(star("F", "II")))      # class II: no entry seen, no mark
        self.assertIsNone(C.entry_for(star("K", None)))      # a Spansh search record: no luminosity
        self.assertIsNone(C.entry_for(star("CJ", "III")))    # no ID seen for it
        # Spansh's wording (no ed): the same entries
        self.assertEqual(C.entry_for({"type": "Star", "subtype": "White Dwarf (DA) Star", "luminosity": "VII"}), 1102202)
        self.assertEqual(C.entry_for({"type": "Star", "subtype": "K (Yellow-Orange giant) Star"}), 1100602)

    def test_planets(self):
        """A solid planet's entry says terraformable or not and atmosphere or none (thin ones count); giants and the
        special worlds have no atmosphere split."""
        cases = [(planet("High metal content body", True, "Thin Sulfur dioxide atmosphere"), 1301502),
                 (planet("High metal content body", True), 1300502), (planet("Rocky body", False, "Carbon dioxide atmosphere"), 1301601),
                 (planet("Icy body"), 1300801), (planet("Rocky ice body", False, "Thin Neon rich atmosphere"), 1301701),
                 (planet("Metal rich body"), 1300401), (planet("Water world", True), 1300302), (planet("Earthlike body", True), 1300100),
                 (planet("Ammonia world"), 1300202), (planet("Sudarsky class IV gas giant"), 1200801),
                 (planet("Gas giant with water based life"), 1200301), (planet("Helium rich gas giant"), 1201001)]
        self.assertEqual([C.entry_for(r) for r, _ in cases], [v for _, v in cases])
        self.assertIsNone(C.entry_for(planet("Icy body", True)))                     # no terraformable icy entry seen
        self.assertIsNone(C.entry_for(planet("Rocky body", atmosphere=None)))        # atmosphere not known
        search = {"type": "Planet", "subtype": "Rocky body", "terraformable": False}  # Spansh's search: no atmosphere key
        self.assertIsNone(C.entry_for(search))
        self.assertEqual(C.entry_for(dict(search, atmosphere="No atmosphere")), 1300601)   # a Spansh dump's
        self.assertEqual(C.entry_for({"type": "Planet", "subtype": "Class II gas giant"}), 1200601)
        self.assertIsNone(C.entry_for({"type": "Planet", "subtype": "Helium gas giant"}))

    def test_names(self):
        self.assertEqual([C.NAMES[i] for i in (1100402, 1100303, 1102203, 1301502, 1300801, 1200301)],
                         ["F-type giant", "A-type supergiant", "DAB white dwarf",
                          "terraformable high metal content world with an atmosphere", "icy body, no atmosphere",
                          "gas giant with water-based life"])
        every = {C.star_entry(c, l) for c in list(C.STARS) + list(C.GIANT_TYPES) + list(C.OTHER_STARS) + C.WHITE_DWARFS
                 for l in ("V", "III", "I")} | set(C.GIANTS.values()) | {i for w in C.WORLDS.values() for i in w} \
            | {i for pair in C.SOLIDS.values() for half in pair for i in half}
        self.assertEqual(sorted(i for i in every - {None} if i not in C.NAMES), [])   # every entry has words


class Server(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()

    def test_here_nearby_and_payload(self):
        at = lambda s: ed_outrider.iso_ts(self.now - 60 + s)
        name = "Drojau TF-H c13-0"
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": name, "SystemAddress": 9, "StarPos": [-4179.0, -64.0, 3339.0]})
        self.j.handle({"event": "Scan", "timestamp": at(5), "ScanType": "Detailed", "StarSystem": name, "SystemAddress": 9, "BodyID": 4,
                       "BodyName": name + " B 3", "PlanetClass": "Water world", "TerraformState": "Terraformable",
                       "AtmosphereType": "CarbonDioxide", "DistanceFromArrivalLS": 900.0, "WasDiscovered": True, "WasMapped": False})
        body = next(b for b in self.state.system_detail(9)["bodies"] if b["name"] == "B 3")
        self.assertEqual(body["codex_type"], {"id": 1300302, "name": "terraformable water world"})
        row = self.state.row(9, ("own", {"name": name, "x": -4179.0, "y": -64.0, "z": 3339.0, "records": []}))
        self.assertEqual(row["codex_types"], [{"id": 1300302, "name": "terraformable water world", "body": "B 3"}])
        self.assertEqual(row["region"], ed_outrider.outrider.bio.region_name(-4179.0, -64.0, 3339.0))
        # your codex's body types per region (bio entries are not body types)
        for i, (eid, region) in enumerate(((1300302, "Inner Orion Spur"), (1100601, "Inner Orion Spur"), (1100601, "Norma Expanse"),
                                           (2310102, "Inner Orion Spur"))):
            self.db.execute("INSERT INTO codex (ts, entry_id, name, region) VALUES (?, ?, 'x', ?)", (at(10 + i), eid, region))
        self.assertEqual(self.state.payload()["codex_types"], {"Inner Orion Spur": [1100601, 1300302], "Norma Expanse": [1100601]})

    def test_scanned_types_count_as_logged(self):
        """The game logs a star or planet type only the first time you scan one in a region, and a commander's codex is
        often older than the journals kept (the author's go back to 2023, their codex further): a type you have scanned
        in a region without a codex line was logged before, so it is never ✦ there (review of the screenshots,
        2026-10-12: every body in Inner Orion Spur showed ✦). A nav beacon's scan logs nothing: it does not count."""
        at = lambda s: ed_outrider.iso_ts(self.now - 60 + s)
        name = "Drojau TF-H c13-0"
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": name, "SystemAddress": 9, "StarPos": [-4179.0, -64.0, 3339.0]})
        scan = {"event": "Scan", "timestamp": at(5), "ScanType": "Detailed", "StarSystem": name, "SystemAddress": 9, "BodyID": 4,
                "BodyName": name + " B 3", "PlanetClass": "Icy body", "AtmosphereType": "None", "TerraformState": "",
                "DistanceFromArrivalLS": 900.0, "WasDiscovered": True, "WasMapped": False}
        self.j.handle(scan)
        self.j.handle(dict(scan, timestamp=at(6), ScanType="NavBeaconDetail", BodyID=5, BodyName=name + " B 4", PlanetClass="Rocky body"))
        region = ed_outrider.outrider.bio.region_name(-4179.0, -64.0, 3339.0)
        logged = self.state.payload()["codex_types"]
        self.assertIn(1300801, logged.get(region, []))        # the icy body you scanned: logged before
        self.assertNotIn(1300601, logged.get(region, []))     # the nav beacon's rocky body: not counted
        # the game's other nav-beacon read, "NavBeacon", counts no more (review 2026-10-23 S6-B1)
        self.j.handle(dict(scan, timestamp=at(6.5), ScanType="NavBeacon", BodyID=7, BodyName=name + " B 6",
                           PlanetClass="Metal rich body"))
        self.assertNotIn(1300401, self.state.payload()["codex_types"].get(region, []))
        self.j.handle(dict(scan, timestamp=at(7), BodyID=6, BodyName=name + " B 5", PlanetClass="Rocky body"))
        self.assertIn(1300601, self.state.payload()["codex_types"][region])   # a later scan: read incrementally


if __name__ == "__main__":
    unittest.main()
