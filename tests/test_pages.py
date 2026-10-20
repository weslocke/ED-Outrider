"""Unit tests: The Log, materials, the schematic and labels, and page-facing summaries.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import datetime as dt
import json
import os
import unittest
import unittest.mock

from support import (  # also puts the repository root on sys.path
    B, scan, shape, types_ns,
)
import outrider.materials  # noqa: E402
import outrider.log  # noqa: E402
import ed_outrider  # noqa: E402


class Log(unittest.TestCase):
    """Batch 3: formatters never throw, file windows, cursors and the live tail."""

    SAMPLES = [
        {"event": "FSDJump", "StarSystem": "Sys", "JumpDist": 32.1, "FuelUsed": 2.4, "BoostUsed": 4},
        {"event": "StartJump", "JumpType": "Hyperspace", "StarSystem": "Sys", "StarClass": "K"},
        {"event": "FSDTarget", "Name": "Sys", "StarClass": "M", "RemainingJumpsInRoute": 3},
        {"event": "Location", "StarSystem": "Sys", "Docked": True, "StationName": "Port"},
        {"event": "CarrierJump", "StarSystem": "Sys"}, {"event": "SupercruiseExit", "Body": "Sys 1", "BodyType": "Planet"},
        {"event": "Touchdown", "Body": "Sys 1", "Latitude": 1.5, "Longitude": -3.2}, {"event": "Docked", "StationName": "Port"},
        {"event": "FuelScoop", "Scooped": 2.1, "Total": 30.5}, {"event": "JetConeBoost", "BoostValue": 4.0},
        {"event": "Scan", "BodyName": "Sys 1", "StarSystem": "Sys", "PlanetClass": "Icy body", "MassEM": 1.1,
         "WasDiscovered": False, "WasMapped": False, "ScanType": "Detailed", "Landable": True, "SurfaceGravity": 1.9},
        {"event": "Scan", "BodyName": "Sys", "StarSystem": "Sys", "StarType": "K", "StellarMass": 0.8, "Age_MY": 10},
        {"event": "Scan", "BodyName": "Sys A Belt Cluster 1", "ScanType": "AutoScan"},
        {"event": "FSSDiscoveryScan", "BodyCount": 15, "NonBodyCount": 3, "Progress": 0.5},
        {"event": "FSSAllBodiesFound", "Count": 15, "SystemName": "Sys"},
        {"event": "FSSBodySignals", "BodyName": "Sys 1", "Signals": [{"Type": "$SAA_SignalType_Biological;", "Type_Localised": "Biological", "Count": 5}]},
        {"event": "SAASignalsFound", "BodyName": "Sys 1", "Signals": [], "Genuses": [{"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"}]},
        {"event": "SAAScanComplete", "BodyName": "Sys 1", "ProbesUsed": 6, "EfficiencyTarget": 8},
        {"event": "ScanBaryCentre", "BodyID": 3, "SemiMajorAxis": 1e10},
        {"event": "MultiSellExplorationData", "Discovered": [{}, {}], "TotalEarnings": 8200000, "Bonus": 1100000},
        {"event": "SellExplorationData", "Systems": ["a"], "TotalEarnings": 5},
        {"event": "ScanOrganic", "ScanType": "Log", "Species_Localised": "Bacterium Cerbrus", "Body": 7, "SystemAddress": 1},
        {"event": "CodexEntry", "Name_Localised": "Thing", "Category_Localised": "Bio", "IsNewEntry": True, "VoucherAmount": 5000},
        {"event": "SellOrganicData", "BioData": [{"Value": 1, "Bonus": 2}]},
        {"event": "Disembark", "OnPlanet": True, "Body": "Sys 1"}, {"event": "Embark", "SRV": True},
        {"event": "Loadout", "ShipName": "Mandalay", "Ship": "mandalay", "MaxJumpRange": 78.07, "Rebuy": 100},
        {"event": "RefuelAll", "Amount": 5.0, "Cost": 200}, {"event": "Resurrect", "Option": "rebuy", "Cost": 5},
        {"event": "Died"}, {"event": "HullDamage", "Health": 0.8}, {"event": "Synthesis", "Name": "FSD Premium"},
        {"event": "EngineerCraft", "Engineer": "Felicity", "BlueprintName": "FSD_LongRange", "Level": 5, "Slot": "FSD"},
        {"event": "MaterialCollected", "Name": "carbon", "Count": 3}, {"event": "MaterialTrade", "Paid": {}, "Received": {}},
        {"event": "Materials", "Raw": [{"Count": 3}]}, {"event": "LoadGame", "Commander": "J", "Credits": 5, "GameMode": "Solo"},
        {"event": "CarrierJumpRequest", "SystemName": "Sys", "DepartureTime": "2026-01-01T12:34:00Z"},
        {"event": "CarrierStats", "Name": "C", "Callsign": "X", "FuelLevel": 500, "Finance": {"CarrierBalance": 9}},
        {"event": "CarrierDepositFuel", "Amount": 5, "Total": 505}, {"event": "SupercruiseDestinationDrop", "Type": "$x;"},
        {"event": "SomethingNew", "Thing_Localised": "Nice", "Thing": "$nice;", "Count": 3, "Ratio": 0.5, "Nested": {"a": 1}},
    ]

    def test_formatters_never_throw(self):
        for ev in self.SAMPLES:
            s = outrider.log.summary(dict(ev, timestamp="2026-01-01T00:00:00Z"), {(1, 7): "B 7"})
            self.assertIsInstance(s, str, ev["event"])
            self.assertTrue(s, ev["event"])
        # every formatter survives an event with no fields at all
        for name in outrider.log.LOG_FORMAT:
            self.assertIsInstance(outrider.log.summary({"event": name}), str, name)

    def test_specific_summaries(self):
        self.assertEqual(outrider.log.summary(self.SAMPLES[0]), "→ Sys · 32.10 ly · 2.40 t · boosted")
        self.assertEqual(outrider.log.summary({"event": "FSDTarget", "Name": "Sys", "StarClass": "M", "RemainingJumpsInRoute": 1}),
                         "Targeted Sys (M) · 1 jump left")
        self.assertEqual(outrider.log.summary({"event": "CarrierCrewServices", "CrewRole": "Exploration", "Operation": "Pause"}),
                         "Carrier service Exploration: suspended")   # S55
        self.assertIn("🏁 undiscovered", outrider.log.summary(self.SAMPLES[10]))
        self.assertIn("landable 0.19 g", outrider.log.summary(self.SAMPLES[10]))
        self.assertEqual(outrider.log.summary(self.SAMPLES[21], {(1, 7): "B 7"}), "Log: Bacterium Cerbrus on B 7")
        self.assertEqual(outrider.log.fallback({"event": "X", "Thing": "$nice;", "Thing_Localised": "Nice", "Count": 3}),
                         "X · Thing: Nice · Count: 3")
        self.assertEqual(outrider.log.fallback({"event": "RepairDrone"}), "Repair drone")   # never blank
        self.assertEqual(outrider.log.category("CarrierBankTransfer"), "carrier")
        self.assertEqual(outrider.log.category("Music"), "noise")

    def test_file_keys_and_window(self):
        self.assertEqual(outrider.log.file_key("/x/Journal.2026-09-27T220610.01.log"), ("2026-09-27T22:06:10", 1))
        self.assertEqual(outrider.log.file_key("Journal.180615221530.02.log"), ("2018-06-15T22:15:30", 2))
        files = [(("2026-01-01T00:00:00", 1), "a"), (("2026-01-05T00:00:00", 1), "b"), (("2026-01-09T00:00:00", 1), "c")]
        now = dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual([p for _, p in outrider.log.window(files, 2, now)], ["b", "c"])   # the one before runs into it
        self.assertEqual([p for _, p in outrider.log.window(files, 30, now)], ["a", "b", "c"])

    def test_read_paging_tail_and_half_line(self):
        import tempfile
        d = tempfile.mkdtemp()
        now = dt.datetime.now(dt.timezone.utc)
        ts = lambda m: (now - dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ")
        name = lambda m: (now - dt.timedelta(minutes=m)).strftime("Journal.%Y-%m-%dT%H%M%S.01.log")
        import json as _j
        with open(os.path.join(d, name(60)), "w") as f:
            for i in range(5):
                f.write(_j.dumps({"timestamp": ts(60 - i), "event": "FSDJump", "StarSystem": f"Old{i}", "JumpDist": 1, "FuelUsed": 1}) + "\n")
        p2 = os.path.join(d, name(30))
        with open(p2, "w") as f:
            f.write(_j.dumps({"timestamp": ts(30), "event": "Music", "MusicTrack": "x"}) + "\n")
            for i in range(3):
                f.write(_j.dumps({"timestamp": ts(29 - i), "event": "FSDJump", "StarSystem": f"New{i}", "JumpDist": 1, "FuelUsed": 1}) + "\n")
            f.write('{"timestamp":"' + ts(1) + '","event":"FSDJump","StarSys')   # half-written line
        r = outrider.log.read_log([d], days=1, limit=4)
        self.assertEqual([x["system"] for x in r["rows"]], ["New2", "New1", "New0", "Old4"])
        r2 = outrider.log.read_log([d], days=1, limit=4, before=r["next"])
        self.assertEqual([x["system"] for x in r2["rows"]], ["Old3", "Old2", "Old1", "Old0"])
        self.assertTrue(outrider.log.read_log([d], days=1, noise=True)["rows"][3]["event"] == "Music")
        self.assertEqual(len(outrider.log.read_log([d], days=1, q="new1")["rows"]), 1)
        self.assertEqual(len(outrider.log.read_log([d], days=1, q="→ old")["rows"]), 5)   # matches the summary only
        tail = r["newest"]
        with open(p2, "a") as f:
            f.write('tem":"Fresh","JumpDist":1,"FuelUsed":1}\n')
        t = outrider.log.read_log([d], after=tail)
        self.assertEqual([x["system"] for x in t["rows"]], ["Fresh"])
        self.assertEqual(outrider.log.read_log([d], after=t["newest"])["rows"], [])


class LogFixes(unittest.TestCase):
    def folder(self, files):
        import tempfile, json as _j
        d = tempfile.mkdtemp()
        for name, events in files.items():
            with open(os.path.join(d, name), "w") as f:
                for e in events:
                    f.write(_j.dumps(e, separators=(",", ":")) + "\n")
        return d

    def test_search_ignores_json_keys(self):
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        d = self.folder({dt.datetime.now(dt.timezone.utc).strftime("Journal.%Y-%m-%dT%H%M%S.01.log"): [
            {"timestamp": now, "event": "FSDJump", "StarSystem": "Alpha", "StarPos": [0, 0, 0], "JumpDist": 5, "FuelUsed": 1},
            {"timestamp": now, "event": "Scan", "BodyName": "Alpha 1", "StarSystem": "Alpha", "PlanetClass": "Icy body",
             "WasMapped": False, "ScanType": "Detailed"}]})
        self.assertEqual(len(outrider.log.read_log([d], days=1, q="star")["rows"]), 0)     # only the StarSystem key has it
        self.assertEqual(len(outrider.log.read_log([d], days=1, q="alpha")["rows"]), 2)    # a value in both
        self.assertEqual(len(outrider.log.read_log([d], days=1, q="icy")["rows"]), 1)

    def test_before_cursor_past_the_end(self):
        now = dt.datetime.now(dt.timezone.utc)
        name = now.strftime("Journal.%Y-%m-%dT%H%M%S.01.log")
        d = self.folder({name: [{"timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "event": "Music"}]})
        r = outrider.log.read_log([d], days=1, before=f"{name}|999999", noise=True)   # no IndexError
        self.assertEqual(len(r["rows"]), 1)

    def test_files_ordered_by_first_line_not_local_name(self):
        # DST fall-back: the newer session's local-time name sorts before the older one's
        d = self.folder({"Journal.2026-10-25T013000.01.log": [{"timestamp": "2026-10-25T00:30:00Z", "event": "Music"}],
                         "Journal.2026-10-25T011500.01.log": [{"timestamp": "2026-10-25T01:15:00Z", "event": "Music"}]})
        order = [os.path.basename(p) for _, p in outrider.log.journal_files([d])]
        self.assertEqual(order, ["Journal.2026-10-25T013000.01.log", "Journal.2026-10-25T011500.01.log"])

    def test_legacy_sale_counts_systems(self):
        s = outrider.log.summary({"event": "SellExplorationData", "Systems": ["A", "B", "C", "D", "E"], "Discovered": ["B"],
                            "TotalEarnings": 1500, "Bonus": 500})
        self.assertTrue(s.startswith("Sold data from 5 systems (1 new)"), s)

    def test_organic_body_name_from_touchdown(self):
        now = dt.datetime.now(dt.timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        d = self.folder({now.strftime("Journal.%Y-%m-%dT%H%M%S.01.log"): [
            {"timestamp": ts, "event": "Touchdown", "Body": "Sys 8 g", "BodyID": 29, "SystemAddress": 5, "StarSystem": "Sys"},
            {"timestamp": ts, "event": "ScanOrganic", "ScanType": "Sample", "Species_Localised": "Bacterium Aurasus",
             "SystemAddress": 5, "Body": 29}]})
        rows = outrider.log.read_log([d], days=1, cats={"bio"})["rows"]
        self.assertEqual(rows[0]["summary"], "Sample: Bacterium Aurasus on 8 g")


class Materials(unittest.TestCase):
    def snap(self, ts="2026-01-01T00:00:00Z", **raw):
        return {"event": "Materials", "timestamp": ts, "Raw": [{"Name": k, "Count": v} for k, v in raw.items()],
                "Manufactured": [], "Encoded": []}

    def test_snapshot_then_deltas(self):
        st = outrider.materials.new_state()
        outrider.materials.apply(st, self.snap(carbon=5, iron=10, nickel=3))
        outrider.materials.apply(st, {"event": "MaterialCollected", "timestamp": "2026-01-01T00:01:00Z", "Category": "Raw",
                                "Name": "carbon", "Count": 2})
        outrider.materials.apply(st, {"event": "Synthesis", "timestamp": "2026-01-01T00:02:00Z", "Name": "Repair Basic",
                                "Materials": [{"Name": "iron", "Count": 2}, {"Name": "nickel", "Count": 1}]})
        outrider.materials.apply(st, {"event": "MaterialDiscarded", "timestamp": "2026-01-01T00:03:00Z", "Name": "nickel", "Count": 9})
        self.assertEqual(st["counts"], {"carbon": 7, "iron": 8})

    def test_trade_sign_convention(self):
        st = outrider.materials.new_state()
        outrider.materials.apply(st, self.snap(arsenic=10))
        outrider.materials.apply(st, {"event": "MaterialTrade", "timestamp": "2026-01-01T00:01:00Z", "TraderType": "raw",
                                "Paid": {"Material": "arsenic", "Quantity": 6},
                                "Received": {"Material": "polonium", "Quantity": 1}})
        self.assertEqual(st["counts"], {"arsenic": 4, "polonium": 1})

    def test_events_before_snapshot_ignored(self):
        st = outrider.materials.new_state()
        outrider.materials.apply(st, self.snap("2026-01-02T00:00:00Z", carbon=1))
        outrider.materials.apply(st, {"event": "MaterialCollected", "timestamp": "2026-01-01T00:00:00Z", "Name": "carbon", "Count": 5})
        outrider.materials.apply(st, self.snap("2026-01-01T00:00:00Z", carbon=99))
        self.assertEqual(st["counts"], {"carbon": 1})

    def test_boosts(self):
        counts = {"carbon": 9, "vanadium": 4, "germanium": 5, "cadmium": 2, "niobium": 3, "arsenic": 1,
                  "yttrium": 1, "polonium": 0}
        self.assertEqual(outrider.materials.boosts(counts), {"basic": 4, "standard": 2, "premium": 0})
        self.assertEqual(outrider.materials.craftable(counts, {"carbon": 2, "niobium": 1}), (3, "niobium"))

    def test_raw_names_and_caps(self):
        inv = outrider.materials.inventory(None)
        carbon = next(r for r in inv["rows"] if r["id"] == "carbon")
        self.assertEqual((carbon["name"], carbon["grade"], carbon["cap"]), ("Carbon", 1, 300))

    def synth(self, ts, name, **mats):
        return {"event": "Synthesis", "timestamp": ts, "Name": name, "Materials": [{"Name": k, "Count": v} for k, v in mats.items()]}

    def test_recipes_learned(self):
        """S15: each Synthesis keeps its recipe (the latest materials, how often made), even one older than the counts'
        snapshot (its counts are in that snapshot, its recipe is not); a learned recipe overrides the table and checks it
        (✓ with its date); a name the table lacks goes to "Other recipes you have made"; the oldest journals' object form
        of Materials reads too."""
        st = outrider.materials.new_state()
        outrider.materials.apply(st, self.snap("2026-01-02T00:00:00Z", iron=30, nickel=20, sulphur=9))
        self.assertTrue(outrider.materials.apply(st, self.synth("2026-01-01T00:00:00Z", "Limpet Basic", iron=10, nickel=10)))
        self.assertEqual(st["counts"]["iron"], 30)   # before the snapshot: counted there already
        outrider.materials.apply(st, self.synth("2026-01-02T00:01:00Z", "limpet basic", iron=10, nickel=10))
        outrider.materials.apply(st, self.synth("2026-01-02T00:02:00Z", "Ammo Basic", iron=2, nickel=1, sulphur=2))
        outrider.materials.apply(st, {"event": "Synthesis", "timestamp": "2026-01-02T00:03:00Z", "Name": "Life Support Basic",
                                      "Materials": {"iron": 2, "nickel": 2}})   # the object form; the table says 1 nickel
        self.assertEqual(st["counts"], {"iron": 16, "nickel": 7, "sulphur": 7})
        self.assertEqual(st["recipes"]["Limpet Basic"], {"materials": {"iron": 10, "nickel": 10}, "ts": "2026-01-02T00:01:00Z", "n": 2})
        inv = {r["name"]: r for r in outrider.materials.inventory(st)["synthesis"]}
        limpet = inv["Limpet basic"]   # "Limpet Basic" and "limpet basic": one recipe, the table's matched without regard to case
        self.assertEqual((limpet["group"], limpet["verified"], limpet["learned"]["n"], limpet["learned"]["differs"]),
                         ("ship", True, 2, False))
        life = inv["Life support"]
        self.assertEqual((life["learned"]["differs"], [(m["id"], m["need"]) for m in life["materials"]], life["craftable"]),
                         (True, [("iron", 2), ("nickel", 2)], 3))   # yours wins over the published recipe
        other = inv["Ammo Basic"]
        self.assertEqual((other["group"], other["journal"], other["craftable"], other["learned"]["ts"]),
                         ("other", "Ammo Basic", 3, "2026-01-02T00:02:00Z"))
        afmu = inv["AFMU refill basic"]   # published, not made: no ✓
        self.assertEqual((afmu["group"], afmu["family"], afmu["grade"], afmu["verified"], afmu["learned"]),
                         ("ship", "AFMU refill", "basic", False, None))
        self.assertTrue(all(r["group"] in outrider.materials.SYNTH_GROUPS for r in inv.values()))
        self.assertEqual([r["name"] for r in inv.values() if r["group"] == "fsd"],
                         ["FSD injection basic", "FSD injection standard", "FSD injection premium"])
        # a Synthesis with no materials (or no name) teaches nothing
        self.assertFalse(outrider.materials.learn_recipe(st, {"event": "Synthesis", "timestamp": "2026-01-03T00:00:00Z", "Name": "X"}))

    def test_published_recipes_use_known_materials(self):
        """Every table recipe names materials the inventory knows (a typo would never be craftable), and a journal name."""
        for name, r in outrider.materials.SYNTH.items():
            self.assertTrue(r["name"] and r["group"] in outrider.materials.SYNTH_GROUPS, name)
            for m in r["materials"]:
                self.assertIn(m, outrider.materials.MATERIALS, name)

    def test_recipes_through_the_reader(self):
        """The reader keeps the recipes in meta materials (journal-derived: a re-read, PARSER_VERSION 50, fills them)."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle(self.snap(iron=30, nickel=20))
        j.handle(self.synth("2026-01-01T00:01:00Z", "Limpet Basic", iron=10, nickel=10))
        self.assertTrue(j.materials_changed)
        self.assertEqual(ed_outrider.meta_get(db, "materials")["recipes"]["Limpet Basic"]["n"], 1)
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 50)


class Schematic(unittest.TestCase):
    """Batch 5: the system hierarchy from Parents chains, names, and barycentres."""

    def test_single_star_planets_moons(self):
        bodies = [B("Sys", 0, [], "Star", True), B("1", 1, [("Star", 0)]), B("2", 2, [("Star", 0)]),
                  B("2 a", 3, [("Planet", 2), ("Star", 0)]), B("2 a a", 4, [("Planet", 3), ("Planet", 2), ("Star", 0)])]
        tree, parent_of = ed_outrider.build_tree("Sys", bodies)
        self.assertEqual(shape(tree), [("Sys", ["1", ("2", [("2 a", ["2 a a"])])])])
        self.assertEqual(parent_of["2 a"], ("b", "2"))

    def test_binary_with_barycentre(self):
        bodies = [B("A", 1, [("Null", 0)], "Star", True), B("B", 2, [("Null", 0)], "Star"),
                  B("AB 1", 3, [("Null", 0)]), B("A 1", 4, [("Star", 1), ("Null", 0)]),
                  B("AB 2", 5, None)]                     # no Parents: found by name through the barycentre label
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        self.assertEqual(shape(tree), [("A+B", [("A", ["A 1"]), "B", "AB 1", "AB 2"])])

    def test_name_only(self):
        bodies = [B("A", None, None, "Star", True), B("A 6", None, None), B("A 6 a", None, None), B("7", None, None)]
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        self.assertEqual(shape(tree), [("A", ["7", ("A 6", ["A 6 a"])])])

    def test_named_body_with_parents_only(self):
        bodies = [B("Sol", 0, [], "Star", True), B("Earth", 3, [("Star", 0)]), B("Moon", 4, [("Planet", 3), ("Star", 0)])]
        tree, _ = ed_outrider.build_tree("Sol", bodies)
        self.assertEqual(shape(tree), [("Sol", [("Earth", ["Moon"])])])

    def test_unscanned_barycentre_and_parent(self):
        # the Null the pair orbits was never scanned and the planet the moon orbits is unknown: both still appear
        bodies = [B("A", 1, [("Null", 0)], "Star", True), B("B", 2, [("Null", 0)], "Star"),
                  B("C 1 a", 9, [("Planet", 8), ("Star", 7), ("Null", 6)])]
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        labels = shape(tree)
        self.assertIn(("A+B", ["A", "B"]), labels)
        self.assertIn(("barycentre #6", [("body #7", [("body #8", ["C 1 a"])])]), labels)

    def test_cycle_does_not_hang(self):
        bodies = [B("X", 1, [("Planet", 2)]), B("Y", 2, [("Planet", 1)])]
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        self.assertEqual(len(tree), 1)


class BarycentreLabels(unittest.TestCase):
    def test_star_orbiting_a_pair(self):
        # A circles the centre it shares with the B-C pair (Drojau TF-H c13-3)
        bodies = [B("A", 1, [("Null", 0)], "Star", True), B("B", 3, [("Null", 2), ("Null", 0)], "Star"),
                  B("C", 4, [("Null", 2), ("Null", 0)], "Star")]
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        self.assertEqual(tree[0]["label"], "A+(B+C)")
        self.assertEqual(tree[0]["children"][1]["label"], "B+C")


class BrownDwarfPairLabel(unittest.TestCase):
    def test_star_and_planet_sharing_a_centre(self):
        # Scaulae GH-V e2-1: a numbered brown dwarf "15" and planet "16" circle a shared centre
        bodies = [B("A", 1, [], "Star", True), B("15", 30, [("Null", 29), ("Star", 1)], "Star"),
                  B("16", 31, [("Null", 29), ("Star", 1)])]
        tree, _ = ed_outrider.build_tree("Sys", bodies)
        bary = tree[0]["children"][0]
        self.assertEqual(bary["label"], "15 + 16")


class ReviewBatchF(unittest.TestCase):
    """Review 2026-10-01, Batch F: planetary mining in Search and Nearby (S4), core module health (S5) and Now's
    This session line (S10). In-memory databases and temp folders only; no network (the Spansh search is refused
    before any request)."""

    MINE = "$PlanetaryMiningLocation_Name;"

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types_ns(cached=lambda i: (None, None)), 25)

    @staticmethod
    def rec(name, subtype, mining, volcanism=None):
        return {"name": name, "type": "Planet", "subtype": subtype, "volcanism": volcanism, "mining": mining}

    # ---- S4: Search's mining section and Nearby's Rhino-worthy count ----
    def test_match_system_mining(self):
        recs = [self.rec("A 1", "Icy body", 20), self.rec("A 2", "Metal-rich body", 5),
                self.rec("A 3", "Rocky body", 3, "major rocky magma volcanism"), self.rec("A 4", "Rocky body", 4),
                self.rec("A 5", "High metal content world", 10), self.rec("A 6", "Metal-rich body", 0),
                {"name": "A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "mining": 9}]
        match = lambda mineral: ed_outrider.match_system("S", recs, {"stars": set(), "planets": set(), "rings": set(),
                                                                   "hotspots": set(), "mining": {"mineral": mineral}})
        anym = match(None)["mining"]
        self.assertEqual([h["body"] for h in anym], ["A 1", "A 5", "A 2", "A 4", "A 3"])   # most locations first
        self.assertEqual(anym[0], {"t": "A 1 · icy: ⛏ 20", "body": "A 1", "here": True})
        plat = match("Platinum")["mining"]   # icy ground has no platinum: left out; ranked by the expected count
        self.assertEqual([h["t"] for h in plat],
                         ["A 5 · high-metal-content: ⛏ 10, Platinum 34% of surveyed locations (~3 expected)",
                          "A 2 · metal-rich: ⛏ 5, Platinum 46% of surveyed locations (~2 expected)"])
        alex = match("Alexandrite")["mining"]   # rocky with magma is its own ground; plain rocky is 2.8%, under 10%
        self.assertEqual([h["body"] for h in alex], ["A 3"])
        self.assertIn("volcanic magma: ⛏ 3, Alexandrite 35%", alex[0]["t"])
        self.assertNotIn("mining", match("Painite"))                                     # not surveyed anywhere
        olivine = ed_outrider.match_system("S", [self.rec("B 1", "Rocky Ice world", 7)],
                                           {"stars": set(), "planets": set(), "rings": set(), "hotspots": set(),
                                            "mining": {"mineral": "Olivine"}})["mining"]
        self.assertTrue(olivine[0]["t"].endswith("(~1 expected) · few reports"))           # 14 surveyed locations
        self.assertNotIn("mining", ed_outrider.match_system("S", recs, {"stars": set(), "planets": set(), "rings": set(),
                                                                       "hotspots": set()}))   # not asked for

    def test_nearby_counts_rhino_ground_only(self):
        recs = [dict(self.rec("A 1", "Icy body", 20, "minor water magma volcanism"), full=True),
                dict(self.rec("A 2", "Metal-rich body", 5), full=True),
                dict(self.rec("A 3", "Rocky body", 3, "major rocky magma volcanism"), full=True),
                dict(self.rec("A 4", "Rocky body", 4), full=True), dict(self.rec("A 5", "Rocky Ice world", 6), full=True),
                {"name": "A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "main": True, "full": True}]
        d = ed_outrider.summarise(recs, 6)["detail"]
        self.assertEqual((d["mining"], d["mining_bodies"]), (8, 2))
        self.assertEqual(ed_outrider.rhino_mining([self.rec("A 1", "Icy body", 20)]), (0, 0))

    def search(self, params):
        import asyncio
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "S1", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})
        for i, (name, cls, n) in enumerate([("A 1", "Icy body", 12), ("A 2", "Metal rich body", 4)]):
            ev = scan(f"2026-01-01T00:0{i + 1}:00Z", "S1", 1, 10 + i, f"S1 {name}")[2]
            ev.update(PlanetClass=cls, Landable=True)
            self.j.handle(ev)
            self.j.handle({"event": "FSSBodySignals", "timestamp": f"2026-01-01T00:0{i + 1}:30Z", "SystemAddress": 1,
                           "BodyID": 10 + i, "BodyName": f"S1 {name}", "Signals": [{"Type": self.MINE, "Count": n}]})
        self.db.commit()
        s = ed_outrider.Searcher(ed_outrider.State(self.db, self.j, ed_outrider.Spansh(self.db), 25))

        async def go():
            s.start(dict({"radius": 50}, **params))
            await s.task
        asyncio.run(go())
        return s.result

    def test_search_mining_local_and_spansh_refused(self):
        r = self.search({"source": "local", "mining": True, "mining_mineral": "Platinum"})
        self.assertEqual([x["name"] for x in r["results"]], ["S1"])
        self.assertEqual([h["body"] for h in r["results"][0]["matches"]["mining"]], ["A 2"])   # icy has no platinum
        r = self.search({"source": "local", "mining": True, "mining_mineral": "Unobtainium"})  # unknown: any mineral
        self.assertEqual([h["body"] for h in r["results"][0]["matches"]["mining"]], ["A 1", "A 2"])
        r = self.search({"source": "spansh", "mining": True})
        self.assertEqual(r["results"], [])
        self.assertIn("Spansh's search can't filter on planetary mining locations", r["status"])
        self.assertIn("mining", self.search({"source": "local"})["status"])   # nothing ticked names the section
        self.assertIn("Platinum", ed_outrider.SEARCH_OPTIONS["mining"])

    def test_search_lists_what_you_mined_first(self):   # S38
        # Gold is not in the survey's list (nothing searchable before); you refined 22 t of it on A 1 (icy: no gold
        # in the survey at all) and 3 t on A 2
        for bid, tons in ((10, 22), (11, 3)):
            self.db.execute("INSERT INTO own_mined VALUES (1, ?, 'gold', 'Gold', ?, 't', 't', '')", (bid, tons))
        self.db.commit()
        self.assertNotIn("Gold", ed_outrider.mining_minerals())
        self.assertIn("Gold", ed_outrider.searchable_minerals(self.db))
        r = self.search({"source": "local", "mining": True, "mining_mineral": "Gold"})
        self.assertEqual([h["t"] for h in r["results"][0]["matches"]["mining"]][:2],
                         ["A 1 · Gold 22 t mined here before", "A 2 · Gold 3 t mined here before"])
        # a surveyed mineral you also refined: your body first, the survey's others after it
        self.db.execute("INSERT INTO own_mined VALUES (1, 11, 'platinum', 'Platinum', 2, 't', 't', '')")
        self.db.commit()
        r = self.search({"source": "local", "mining": True, "mining_mineral": "Platinum"})
        self.assertEqual([h["t"] for h in r["results"][0]["matches"]["mining"]], ["A 2 · Platinum 2 t mined here before"])

    def test_favicon(self):   # an original drawing in the HUD's orange, served with the page
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                page = await (await c.get("/")).text()
                r = await c.get("/static/favicon.svg")
                return page, r.status, r.content_type, await r.text()
        page, status, ctype, svg = asyncio.run(go())
        self.assertIn('<link rel="icon" type="image/svg+xml" href="static/favicon.svg">', page)
        self.assertEqual((status, ctype), (200, "image/svg+xml"))
        self.assertIn("<svg", svg)

    # ---- S5: core module health ----
    def loadout(self, ts, sid, fsd=0.884, extra=()):
        mods = [{"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii", "Health": fsd},
                {"Slot": "PowerPlant", "Item": "int_powerplant_size6_class5", "Health": 0.924},
                {"Slot": "MainEngines", "Item": "int_engine_size6_class5", "Health": 0.951},
                {"Slot": "LifeSupport", "Item": "int_lifesupport_size4_class2", "Health": 0.796},
                {"Slot": "Radar", "Item": "int_sensors_size5_class2", "Health": 0.952},
                {"Slot": "Slot01_Size7", "Item": "int_fuelscoop_size7_class5", "Health": 1.0},
                {"Slot": "Slot04_Size6", "Item": "int_repairer_size6_class5", "Health": 0.930},
                {"Slot": "MediumHardpoint1", "Item": "hpt_heatsinklauncher_turret_tiny", "Health": 0.5,
                 "AmmoInClip": 1, "AmmoInHopper": 2}] + list(extra)
        self.j.handle({"event": "Loadout", "timestamp": ts, "Ship": "explorer_nx", "ShipID": sid, "MaxJumpRange": 80,
                       "HullHealth": 1.0, "Modules": mods})

    def test_module_health_from_loadout_repairs_and_boosts(self):
        self.loadout("2026-09-25T20:19:46Z", 7)
        ms = self.state.modules_summary()
        self.assertEqual([(m["label"], m["pct"]) for m in ms],
                         [("FSD", 88), ("Power plant", 92), ("Thrusters", 95), ("Life support", 79), ("Sensors", 95),
                          ("Fuel scoop", 100), ("AFMU", 93)])                    # no hardpoints; 79.6% reads 79
        self.assertNotIn("ammo", json.dumps(ms).lower())
        for t in ("2026-09-25T20:25:00Z", "2026-09-25T20:28:00Z"):
            self.j.handle({"event": "JetConeBoost", "timestamp": t, "BoostValue": 4.0})
        self.assertEqual({m["boosts"] for m in self.state.modules_summary()}, {2})
        self.j.handle({"event": "AfmuRepairs", "timestamp": "2026-09-25T21:33:00Z",
                       "Module": "$int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii_name;",
                       "Module_Localised": "FSD", "FullyRepaired": False, "Health": 0.97})
        fsd = self.state.modules_summary()[0]
        self.assertEqual((fsd["pct"], fsd["boosts"], fsd["ts"]), (97, 0, "2026-09-25T21:33:00Z"))
        self.assertEqual(self.state.modules_summary()[1]["boosts"], 2)                # the others still stale
        self.j.handle({"event": "RepairAll", "timestamp": "2026-09-25T22:00:00Z", "Cost": 100})
        self.assertEqual({m["pct"] for m in self.state.modules_summary()}, {100})
        self.assertEqual(self.state.payload()["modules"], self.state.modules_summary())

    def test_module_health_per_ship(self):
        self.loadout("2026-09-25T20:19:46Z", 7)
        self.loadout("2026-09-26T10:00:00Z", 9, fsd=0.5)             # another ship
        self.assertEqual(self.state.modules_summary()[0]["pct"], 50)
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-09-26T10:05:00Z", "BoostValue": 4.0})
        self.loadout("2026-09-26T11:00:00Z", 7, fsd=0.884)           # back in the first: its own record
        self.assertEqual((self.state.modules_summary()[0]["pct"], self.state.modules_summary()[0]["boosts"]), (88, 0))
        self.j.handle({"event": "Repair", "timestamp": "2026-09-26T11:10:00Z", "Items": ["$int_lifesupport_size4_class2_name;"]})
        self.assertEqual([m["pct"] for m in self.state.modules_summary()][3], 100)
        self.assertEqual(self.state.modules_summary()[0]["pct"], 88)                   # only the one named
        self.loadout("2026-09-20T10:00:00Z", 7, fsd=0.3)             # an older Loadout read late: ignored
        self.assertEqual(self.state.modules_summary()[0]["pct"], 88)
        j2 = ed_outrider.Journals(self.db)                           # kept over a restart
        self.assertEqual(j2.modules["9"]["mods"]["FrameShiftDrive"]["health"], 0.5)
        self.assertIn("modules", ed_outrider.RESET_JOURNAL_DATA)

    def test_module_warn_config(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual(st["module_warn"], 80)
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["defaults"]["module_warn"], 80)
        for raw, want in ((90, 90), (0, 1), (150, 100)):
            self.assertEqual(ed_outrider.settings_from({"defaults": {"module_warn": raw}}, args, None, ([], []))["module_warn"], want)
        self.assertEqual(self.state.payload()["defaults"]["module_warn"], ed_outrider.MODULE_WARN)
        self.assertIn("moduleWarn", ed_outrider.BROWSER_SETTINGS)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "ed_outrider.toml.example"), encoding="utf-8") as f:
            self.assertIn("module_warn = 80", f.read())

    def test_highway_form_is_a_shared_setting(self):
        # the Highway tab's last plot options (H2): per browser, exported, and accepted as a server copy; an object, so
        # the page reads a value of another shape as unset; the per-device folds (hwyDoneOpen) stay out
        import re
        self.assertIn("highway", ed_outrider.BROWSER_SETTINGS)
        self.assertNotIn("hwyDoneOpen", ed_outrider.BROWSER_SETTINGS)
        doc, err = ed_outrider.check_browser_defaults({"version": 1, "settings": {"highway": {"plotter": "neutron", "injections": True}}})
        self.assertIsNone(err)
        self.assertEqual(doc["settings"]["highway"]["plotter"], "neutron")
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        shapes = js[js.index("const SETTING_SHAPES = {"):js.index("};", js.index("const SETTING_SHAPES = {"))]
        self.assertTrue(re.search(r"\bhighway: isObj\b", shapes))

    def test_tiles_collapsed_is_a_shared_setting(self):
        # the header tiles folded into one line: per browser, exported, and accepted as a server copy for new browsers
        self.assertIn("tilesCollapsed", ed_outrider.BROWSER_SETTINGS)
        doc, err = ed_outrider.check_browser_defaults({"version": 1, "settings": {"tilesCollapsed": True}})
        self.assertIsNone(err)
        self.assertTrue(doc["settings"]["tilesCollapsed"])

    # ---- S10: This session ----
    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def test_this_session(self):
        self.assertIsNone(self.state.this_session())                                    # no login yet
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X", "Credits": 1000})
        self.db.commit()
        self.assertIsNone(self.state.this_session())                                    # nothing done yet
        for i in range(3):
            self.jump(f"2026-01-01T01:0{i + 1}:00Z", 10 + i, 10 * (i + 1))
        self.j.handle(scan("2026-01-01T01:03:05Z", "S12", 12, 0, "S12", disc=False, star=True)[2])
        self.db.commit()
        self.state.bump()
        ts = self.state.this_session()
        self.assertEqual((ts["jumps"], ts["ly"], ts["firsts"], ts["start"], ts["found"]), (3, 20.0, 1, "2026-01-01T01:00:00Z", None))
        self.assertIsNone(self.state.last_session())                                    # never both
        # found: the estimate now less the one from before the login, plus what was sold since
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T01:10:00Z", "MarketID": 1,
                       "BioData": [{"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Species": "$Codex_Ent_Bacterial_01_Name;",
                                    "Value": 5_000_000, "Bonus": 0}]})
        self.state.unsold, self.state.unsold_login = {"total": 30_000_000}, ("2026-01-01T01:00:00Z", 10_000_000)
        self.assertEqual(self.state.this_session()["found"], 25_000_000)
        self.state.unsold_login = ("2025-12-31T01:00:00Z", 10_000_000)                 # another login's: not used
        self.assertIsNone(self.state.this_session()["found"])
        self.state.unsold_login = ("2026-01-01T01:00:00Z", 90_000_000)                 # a death took more: not below 0
        self.assertEqual(self.state.this_session()["found"], 0)
        self.assertEqual(self.state.payload()["this_session"]["jumps"], 3)
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T02:00:00Z"})
        self.db.commit()
        self.assertIsNone(self.state.this_session())                                    # quit: Last session instead
        self.assertEqual(self.state.last_session()["jumps"], 3)

    def test_unsold_before_the_login(self):
        import asyncio, tempfile
        with tempfile.TemporaryDirectory() as d:
            lines = [scan("2026-01-01T00:01:00Z", "S1", 1, 0, "S1", star=True)[2],
                     scan("2026-01-01T02:01:00Z", "S2", 2, 0, "S2", star=True)[2]]
            with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "w") as f:
                f.write("".join(json.dumps(ev) + "\n" for ev in lines))
            with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]), unittest.mock.patch.object(ed_outrider, "LEGACY_DIRS", []):
                before, after = ed_outrider.unsold_total_at("2026-01-01T01:00:00Z"), ed_outrider.unsold_total_at("2026-01-01T03:00:00Z")
                self.assertGreater(before, 0)
                self.assertGreater(after, before)
                self.assertEqual(ed_outrider.unsold_total_at("2025-01-01T00:00:00Z"), 0)
        self.assertIsNone(ed_outrider.unsold_total_at("not a time"))
        # worked out once per login, beside the ordinary estimate
        calls = []
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X"})

        async def once():
            self.state.unsold_dirty, self.state.unsold_at = True, 0
            self.state.maybe_unsold()
            await self.state.unsold_task
        with unittest.mock.patch.object(ed_outrider, "compute_unsold", lambda: {"total": 5, "system_values": {}}), \
                unittest.mock.patch.object(ed_outrider, "unsold_total_at", lambda t: calls.append(t) or 3):
            asyncio.run(once())
            asyncio.run(once())
        self.assertEqual((calls, self.state.unsold_login), (["2026-01-01T01:00:00Z"], ("2026-01-01T01:00:00Z", 3)))


class ShipNames(unittest.TestCase):
    def test_the_page_names_the_newer_ships(self):
        """page.js' SHIP_NAMES: the journal's ship symbols -> the names the game shows. The Lynx Highliner read
        "MediumTransport01" in the ship list (the author, in game, 2026-10-14): the newer ships' symbols are not their
        names."""
        import re
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "static", "page.js"), encoding="utf-8") as f:
            table = re.search(r"const SHIP_NAMES = \{(.*?)\};", f.read(), re.S).group(1)
        names = dict(re.findall(r'(\w+): "([^"]+)"', table))
        for symbol, name in (("mediumtransport01", "Lynx Highliner"), ("lakonminer", "Type-11 Prospector"),
                             ("smallcombat01_nx", "Kestrel Mk II"), ("explorer_nx", "Caspian Explorer"),
                             ("panthermkii", "Panther Clipper Mk II"), ("python_nx", "Python Mk II"),
                             ("cobramkv", "Cobra Mk V"), ("mandalay", "Mandalay"), ("corsair", "Corsair"),
                             ("type8", "Type-8 Transporter"), ("type9_military", "Type-10 Defender"),
                             ("anacondamkii", "Anaconda Mk II")):
            self.assertEqual(names.get(symbol), name, symbol)
