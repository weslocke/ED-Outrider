"""Unit tests: The fuel model, jump range and scooping.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import unittest
import unittest.mock

from support import (  # also puts the repository root on sys.path
    MANDALAY, MANDALAY_JUMPS,
)
import ed_outrider  # noqa: E402
import outrider.fsd  # noqa: E402


class BatchDFuel(unittest.TestCase):
    """Batch D: the fuel model (laden range, per-hop fuel, jumps left), the local scoopable share, the in-system
    scoopable star and the targeted jump's cost."""

    # Real [JumpDist, FuelUsed, FuelLevel, cargo t] from the author's journals (copied here, never read from a live
    # database): a Mandalay (SCO 5A, Guardian booster size 5, UnladenMass 323.15 t, MaxJumpRange 83.487473 ly)
    # hopping to the nearest unvisited system, and a Panther Clipper Mk II (SCO 7A, booster size 4, 1596.8 t,
    # 44.958641 ly) on the same 12.571 ly jump empty and with 1,153 t in the hold.
    MANDALAY = MANDALAY
    MANDALAY_JUMPS = MANDALAY_JUMPS
    PANTHER = {"unladen": 1596.800049, "max_range": 44.958641, "fsd_size": 7, "booster_ly": 9.25, "max_fuel": None}
    PANTHER_JUMPS = [[12.571, 0.456644, 126.433357, 0], [12.571, 1.287122, 126.712875, 1153],
                     [12.571, 0.457277, 127.542725, 0], [12.571, 1.285804, 125.146919, 1153], [12.571, 0.456283, 125.799706, 0]]

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_model_against_real_jumps(self):
        m = ed_outrider.fuel_model(self.MANDALAY, self.MANDALAY_JUMPS)
        self.assertEqual((m["power"], m["fitted"]), (2.45, True))
        self.assertAlmostEqual(m["max_fuel"], 5.2, delta=0.01)          # an SCO 5A's MaxFuelPerJump
        for d, used, left, cargo in self.MANDALAY_JUMPS:                 # every real burn, to within 1%
            self.assertAlmostEqual(ed_outrider.hop_fuel(m, d, m["unladen"] + left + used + cargo) / used, 1, delta=0.01)
        # the Panther's cargo counts: the same jump burns 2.8 times the fuel with the hold full
        p = ed_outrider.fuel_model(self.PANTHER, self.PANTHER_JUMPS)
        self.assertEqual(p["power"], 2.75)
        self.assertAlmostEqual(p["max_fuel"], 13.1, delta=0.02)
        for d, used, left, cargo in self.PANTHER_JUMPS:
            self.assertAlmostEqual(ed_outrider.hop_fuel(p, d, p["unladen"] + left + used + cargo) / used, 1, delta=0.01)
        # a wrong exponent would not fit: at p 2.30 the estimates drift with the distance
        e = outrider.fsd._fit_estimates(m, self.MANDALAY_JUMPS, 2.30)
        self.assertGreater((max(e) - min(e)) / min(e), 0.3)
        # an engineered drive that says its MaxFuelPerJump is taken as said
        self.assertEqual(ed_outrider.fuel_model(dict(self.MANDALAY, max_fuel=6.1), self.MANDALAY_JUMPS)["max_fuel"], 6.1)

    def test_power_fitted_for_a_size_the_table_lacks(self):
        truth = dict(unladen=1600.0, r0=50.0, boost=0, power=2.6, max_fuel=8.0)
        # jumps as that drive would burn them, 100 t in the tank before each
        jumps = [[d, ed_outrider.hop_fuel(truth, d, 1700), 100 - ed_outrider.hop_fuel(truth, d, 1700), 0] for d in (3, 9, 17, 25, 33, 40)]
        new = {"unladen": 1600.0, "max_range": 50.0, "fsd_size": 8, "booster_ly": 0,
               "fsd": "int_hyperdrive_overcharge_size8_class5_somethingnew"}   # a variant neither table knows
        m = ed_outrider.fuel_model(new, jumps)
        self.assertEqual(m["power"], 2.6)
        self.assertAlmostEqual(m["max_fuel"], 8.0, places=2)
        # too few jumps to tell: no exponent, so no per-hop fuel (the range still works)
        few = ed_outrider.fuel_model(new, jumps[:3])
        self.assertIsNone(few["power"])
        self.assertIsNone(ed_outrider.jumps_left(few, 50, 0))

    def test_range_scaling_and_jumps_left(self):
        m = ed_outrider.fuel_model(self.MANDALAY, self.MANDALAY_JUMPS)
        u, mf = m["unladen"], m["max_fuel"]
        self.assertAlmostEqual(ed_outrider.fsd_range(m, u + mf), m["r0"], places=6)   # the Loadout's figure
        full = ed_outrider.fsd_range(m, u + 32)
        self.assertAlmostEqual(full, 77.98, delta=0.02)
        # the booster's 10.5 ly do not shrink with mass: 700 t of cargo halves only the drive's own part
        heavy = ed_outrider.fsd_range(m, 2 * (u + 32))
        self.assertAlmostEqual(heavy - 10.5, (full - 10.5) / 2, places=6)
        # at max range every jump burns MaxFuelPerJump, and each is longer than the one before (lighter)
        n, ly = ed_outrider.jumps_left(m, 32, 0)
        self.assertEqual(n, int(32 / mf))
        self.assertGreater(ly, n * full)
        # hops of 5 ly: thousands of them, counted past the cap at the last hop's cost
        pace, _ = ed_outrider.jumps_left(m, 32, 0, d=5)
        self.assertGreater(pace, 3000)
        self.assertEqual(ed_outrider.jumps_left(m, 3, 0), (0, 0.0))    # under one max jump's fuel
        self.assertIsNone(ed_outrider.jumps_left(m, 32, None))          # no cargo figure: no answer, not a wrong one

    def test_journal_loadout_cargo_and_samples(self):
        mods = [{"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size5_class5",
                 "Engineering": {"Modifiers": [{"Label": "FSDOptimalMass", "Value": 2077.4}]}},
                {"Slot": "Slot03_Size5", "Item": "Int_GuardianFSDBooster_Size5"}]
        lo = {"event": "Loadout", "timestamp": "2026-01-01T00:00:00Z", "Ship": "mandalay", "ShipID": 32,
              "UnladenMass": 323.150024, "MaxJumpRange": 83.487473, "FuelCapacity": {"Main": 32.0, "Reserve": 0.5}, "Modules": mods}
        self.j.handle(lo)
        s = self.j.ship
        self.assertEqual((s["unladen"], s["fsd_size"], s["booster_ly"], s["max_fuel"]), (323.150024, 5, 10.5, None))
        self.j.handle({"event": "Cargo", "timestamp": "2026-01-01T00:00:01Z", "Vessel": "SRV", "Count": 4})   # the SRV's hold
        self.assertIsNone(self.j.cargo)
        self.j.handle({"event": "Cargo", "timestamp": "2026-01-01T00:00:02Z", "Vessel": "Ship", "Count": 0})
        self.assertEqual(self.j.cargo["count"], 0)
        for k, (d, used, left, _) in enumerate(self.MANDALAY_JUMPS[:4]):
            self.j.handle({"event": "FSDJump", "timestamp": f"2026-01-01T00:0{k + 1}:00Z", "StarSystem": f"S{k}", "SystemAddress": 100 + k,
                           "StarPos": [k, 0, 0], "JumpDist": d, "FuelUsed": used, "FuelLevel": left})
        self.assertEqual(self.j.fuel_hist[0], self.MANDALAY_JUMPS[0])
        self.assertIsNotNone(ed_outrider.fuel_model(self.j.ship, self.j.fuel_hist)["max_fuel"])
        # the same ship logged again with float jitter keeps its samples; a new drive starts them afresh
        self.j.handle(dict(lo, timestamp="2026-01-01T01:00:00Z", UnladenMass=323.149994, MaxJumpRange=83.487465))
        self.assertEqual(len(self.j.fuel_hist), 4)
        self.j.handle(dict(lo, timestamp="2026-01-01T01:30:00Z", Modules=[mods[0], dict(mods[1], On=False)]))
        self.assertEqual(self.j.ship["booster_ly"], 0)                  # switched off: no boost (Codex F3)
        self.j.handle(dict(lo, timestamp="2026-01-01T01:40:00Z", Modules=[mods[0], dict(mods[1], On=True)]))
        self.assertEqual(self.j.ship["booster_ly"], 10.5)
        mods2 = [dict(mods[0], Item="int_hyperdrive_size5_class5"), mods[1]]
        self.j.handle(dict(lo, timestamp="2026-01-01T02:00:00Z", Modules=mods2, MaxJumpRange=70.1))
        self.assertEqual(self.j.fuel_hist, [])

    def test_fuel_summary_model_and_null_paths(self):
        self.j.ship = dict(self.MANDALAY, fuel_main=32.0)
        self.j.jump_range = {"ly": self.MANDALAY["max_range"], "ts": "x"}
        self.j.fuel_hist = [list(x) for x in self.MANDALAY_JUMPS]
        self.j.status_json = {"live": True, "fuel_main": 32.0, "flags": 1 << 24}   # no Cargo in Status.json, none from the journal
        f = self.state.fuel_summary()
        self.assertIsNone(f["model"])                                    # no cargo figure: the old estimate, no model
        self.assertIsNone(self.state.payload()["jump_range_now"])
        old_max = f["jumps_max"]
        self.j.status_json["cargo"] = 0
        f = self.state.fuel_summary()
        self.assertEqual((f["jumps_max"], f["model"]["fitted"]), (6, True))
        self.assertAlmostEqual(f["model"]["range_now"], 77.98, delta=0.02)
        self.assertNotEqual(old_max, f["jumps_max"])                     # the dist^2.5 guess said otherwise
        self.assertGreater(f["jumps_recent"], 1000)
        self.assertAlmostEqual(self.state.payload()["jump_range_now"], 77.98, delta=0.02)
        self.j.ship = {"fuel_main": 32.0, "max_range": 83.5}             # a Loadout from before UnladenMass was kept
        self.assertIsNone(self.state.fuel_summary()["model"])
        self.assertIsNone(self.state.range_now())

    def test_scoop_rate_and_dry_run(self):
        self.assertIsNone(self.state.scoop_rate())
        classes = ["K", "M", "L", "F", "T", "G", "M_RedGiant", "Y", "DA", "N"]   # oldest first; the newest three are dry
        for k, c in enumerate(classes):
            self.db.execute("INSERT INTO jumps (ts, id64, star_class, kind) VALUES (?, ?, ?, 'FSDJump')", (f"2026-01-01T00:{k:02d}:00Z", k, c))
        self.db.execute("INSERT INTO jumps (ts, id64, star_class, kind) VALUES ('2026-01-01T01:00:00Z', 50, NULL, 'FSDJump')")      # a journal gap
        self.db.execute("INSERT INTO jumps (ts, id64, star_class, kind) VALUES ('2026-01-01T01:01:00Z', 51, 'K', 'CarrierJump')")   # the carrier's
        self.assertEqual(self.state.scoop_rate(), {"scoopable": 5, "of": 10, "dry_run": 3})
        self.db.execute("DELETE FROM jumps WHERE id64 < 3")
        self.assertIsNone(self.state.scoop_rate())                       # 7 known: too few to say

    def test_here_scoop_complete_and_incomplete(self):
        self.j.pos = {"id64": 9, "name": "Here", "x": 0, "y": 0, "z": 0, "ts": "2026-01-01T00:00:00Z"}
        self.state.here_star = lambda: "DA"
        recs = [{"name": "A", "type": "Star", "main": True, "scoopable": False, "dist_ls": 0},
                {"name": "B", "type": "Star", "main": False, "scoopable": True, "subtype": "K (Yellow-Orange) Star", "dist_ls": 1240.4},
                {"name": "C", "type": "Star", "main": False, "scoopable": True, "subtype": "M (Red dwarf) Star", "dist_ls": 88000},
                {"name": "A 1", "type": "Planet", "main": False, "scoopable": False, "dist_ls": 12}]
        self.state.merged_records = lambda i: {"records": recs}
        self.assertEqual(self.state.here_scoop(), {"name": "B", "subtype": "K (Yellow-Orange) Star", "dist_ls": 1240, "complete": False})
        self.state.scan_version += 1                                     # every body found: now complete
        self.db.execute("INSERT INTO own_systems VALUES (9, 'Here', 4, 1)")
        recs[1]["scoopable"] = recs[2]["scoopable"] = False
        self.assertEqual(self.state.here_scoop(), {"name": None, "subtype": None, "dist_ls": None, "complete": True})
        self.state.scan_version += 1                                     # Spansh knows 6 bodies, 4 records here: not complete
        self.db.execute("DELETE FROM own_systems")
        self.state.bases[9] = ("spansh", {"body_count": 6})
        self.assertFalse(self.state.here_scoop()["complete"])
        self.state.here_star = lambda: "K"                               # the arrival star scoops: nothing to find
        self.assertIsNone(self.state.here_scoop())

    def test_target_hop(self):
        self.j.pos = {"id64": 9, "name": "Here", "x": 0, "y": 0, "z": 0, "ts": "2026-01-01T00:00:00Z"}
        self.db.execute("INSERT INTO route_systems VALUES (77, 'Next', 38.2, 0, 0, 'K', 'x')")
        t = {"id64": 77, "name": "Next"}
        self.assertEqual(self.state.target_hop(t), {"ly": 38.2, "fuel": None, "left": None, "reach": None})   # no model yet
        self.j.ship = dict(self.MANDALAY, fuel_main=32.0)
        self.j.fuel_hist = [list(x) for x in self.MANDALAY_JUMPS]
        self.j.status_json = {"live": True, "fuel_main": 32.0, "cargo": 0}
        h = self.state.target_hop(t)
        self.assertAlmostEqual(h["fuel"], 0.91, delta=0.01)
        self.assertEqual((h["left"], h["reach"]), (5, True))
        self.db.execute("UPDATE route_systems SET x = 95 WHERE id64 = 77")   # past the laden range
        self.assertEqual(self.state.target_hop(t)["reach"], False)
        self.j.boost = {"value": 4.0, "ts": "x"}                         # a neutron charge reaches it
        self.assertTrue(self.state.target_hop(t)["reach"])

    def test_target_hop_from_you_while_nearby_is_elsewhere(self):
        """Review 2026-10-20 M1: with Nearby Around another system, a targeted row's distance is from that centre; the
        hop (Now's target line, the overlay's Target panel) must be from you: a 190 ly jump read as a reachable 10 ly."""
        self.j.pos = {"id64": 9, "name": "Here", "x": 0, "y": 0, "z": 0, "ts": "2026-01-01T00:00:00Z"}
        self.state.systems[77] = {"id64": 77, "name": "Next", "distance": 10.0, "xyz": (190.0, 0.0, 0.0)}
        self.j.target = {"id64": 77, "name": "Next", "ts": "2026-01-01T00:00:01Z"}
        self.j.ship = dict(self.MANDALAY, fuel_main=32.0)
        self.j.fuel_hist = [list(x) for x in self.MANDALAY_JUMPS]
        self.j.status_json = {"live": True, "fuel_main": 32.0, "cargo": 0}
        with unittest.mock.patch.object(self.state, "near_pinned", return_value=True):
            h = self.state.target_hop({"id64": 77, "name": "Next"})
            self.assertEqual((h["ly"], h["reach"]), (190.0, False))
            self.assertEqual(self.state.overlay_target_info(self.j.pos)["distance"], 190.0)
        self.assertEqual(self.state.target_hop({"id64": 77, "name": "Next"})["ly"], 10.0)   # around you: the row's own

    def test_fuel_run_and_window(self):   # the fuel plan's groundwork (S1): hop by hop, then a grid of starting levels
        m = ed_outrider.fuel_model(self.MANDALAY, self.MANDALAY_JUMPS)
        self.assertIsNone(outrider.fsd.fuel_run(dict(m, max_fuel=None), 32, 0, [(30, 1)]))   # no per-hop fuel
        self.assertIsNone(outrider.fsd.fuel_window(dict(m, max_fuel=None), 0, [(30, 1)], 32))
        # the ship lightens as it burns: the same 60 ly hop costs less each time, and the run stops where the tank does
        n, after = outrider.fsd.fuel_run(m, 32.0, 0, [(60, 1)] * 20)
        burns = [a - b for a, b in zip([32.0] + after, after)]
        self.assertTrue(all(x > y for x, y in zip(burns, burns[1:])))
        self.assertEqual((n, round(after[-1], 6)), (len(after), round(32.0 - sum(burns), 6)))
        self.assertLess(n, 20)
        self.assertLess(after[-1], ed_outrider.hop_fuel(m, 60, m["unladen"] + after[-1]))   # the next one unpaid
        # a supercharge divides the hop: 240 ly at x4 costs what 60 ly does
        self.assertAlmostEqual(outrider.fsd.fuel_run(m, 32.0, 0, [(240, 4)])[1][0], after[0], places=9)
        # past the range at any fuel: no window; a run the full tank makes has no upper end
        self.assertIsNone(outrider.fsd.fuel_window(m, 0, [(200, 1)], 32))
        lo, hi = outrider.fsd.fuel_window(m, 0, [(60, 1)] * 4, 32)
        self.assertEqual(hi, 32)
        self.assertEqual(outrider.fsd.fuel_run(m, lo, 0, [(60, 1)] * 4)[0], 4)
        self.assertEqual(outrider.fsd.fuel_run(m, lo - 0.01, 0, [(60, 1)] * 4)[0], 3)
        # a supercharged jump right at the limit: a full tank fails, a part one passes. The window finds both ends; a
        # bisection of the whole tank for "the least that works" would start from a failing full tank and say none does
        far = outrider.fsd.fsd_range(m, m["unladen"] + 12) * 4
        hops = [(far, 4), (40, 1), (40, 1)]
        self.assertLess(outrider.fsd.fuel_run(m, 32.0, 0, hops)[0], 3)
        lo, hi = outrider.fsd.fuel_window(m, 0, hops, 32)
        self.assertAlmostEqual(hi, 12, delta=0.01)
        self.assertLess(lo, hi)
        for f in (lo + 0.01, (lo + hi) / 2, hi - 0.01):
            self.assertEqual(outrider.fsd.fuel_run(m, f, 0, hops)[0], 3)
        self.assertLess(outrider.fsd.fuel_run(m, hi + 0.05, 0, hops)[0], 3)
        # cargo weighs like fuel: 5 t in the hold takes 5 t off the high end
        self.assertAlmostEqual(outrider.fsd.fuel_window(m, 5, hops, 32)[1], 7, delta=0.01)
        # at most FUEL_RUN_MAX_HOPS hops are looked at
        many = [(1, 1)] * (outrider.fsd.FUEL_RUN_MAX_HOPS + 10)
        self.assertEqual(outrider.fsd.fuel_run(m, 32.0, 0, many)[0], outrider.fsd.FUEL_RUN_MAX_HOPS)


class ReviewFuel(unittest.TestCase):
    """Review 2026-10-01, batch C: the fuel model for any drive (R3), engineering between Loadouts (R4), a tank
    under one max jump's fuel (R14), how many jumps the fit still needs (R15), rides out of the scoop counts (R16)."""

    MANDALAY = MANDALAY
    MANDALAY_JUMPS = MANDALAY_JUMPS
    # Real jumps of a Caspian Explorer (explorer_nx: the Mk II SCO 8A drive, Guardian booster size 5, UnladenMass
    # 1290.875 t, MaxJumpRange 83.246773 ly, 32 t in the hold), copied from the author's journals
    NX = {"unladen": 1290.875, "max_range": 83.246773, "fsd_size": 8, "booster_ly": 10.5, "max_fuel": None,
          "fsd": "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii"}
    NX_JUMPS = [[1.87, 0.000678, 157.71933, 32], [5.416, 0.00972, 158.850281, 32], [8.846, 0.032959, 154.267044, 32],
                [11.716, 0.067139, 159.932861, 32], [13.637, 0.098173, 159.901825, 32], [16.035, 0.147014, 158.712982, 32],
                [17.58, 0.185373, 159.814621, 32], [52.561, 2.873145, 157.126862, 32], [73.633, 6.624328, 147.675674, 32]]

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    # ---- R3: every drive's power constant, the Mk II's own included ----
    def test_power_constant_per_drive(self):   # R3
        p = outrider.fsd.fsd_power
        self.assertEqual(p(self.NX), 2.5025)
        self.assertEqual(p({"fsd": "int_hyperdrive_overcharge_size8_class5", "fsd_size": 8}), 2.90)
        self.assertEqual(p({"fsd": "int_hyperdrive_overcharge_size8_class1", "fsd_size": 8}), 2.90)
        self.assertEqual(p({"fsd": "Int_Hyperdrive_Size5_Class3", "fsd_size": 5}), 2.45)   # case as outfitting writes it
        self.assertEqual(p({"fsd": "int_hyperdrive_size2_class1_free", "fsd_size": 2}), 2.00)
        self.assertEqual(p({"fsd": "int_hyperdrive_overcharge_size7_class5", "fsd_size": 7}), 2.75)
        self.assertIsNone(p({"fsd": "int_hyperdrive_overcharge_size7_class5_mkiii", "fsd_size": 7}))   # unknown: fitted
        self.assertEqual(p({"fsd_size": 6}), 2.60)                       # a ship saved before the drive's name was kept
        # the real jumps: per-hop fuel to within 0.5% on every one, and the Mk II's 6.8 t MaxFuelPerJump
        m = ed_outrider.fuel_model(self.NX, self.NX_JUMPS)
        self.assertEqual(m["power"], 2.5025)
        self.assertAlmostEqual(m["max_fuel"], 6.8, delta=0.01)
        for d, used, left, cargo in self.NX_JUMPS:
            self.assertAlmostEqual(ed_outrider.hop_fuel(m, d, m["unladen"] + left + used + cargo) / used, 1, delta=0.005)
        # without the drive's name the size-8 fit still picks the Mk II's constant from the jumps
        self.assertEqual(ed_outrider.fuel_model(dict(self.NX, fsd="int_hyperdrive_overcharge_size8_class5_x"), self.NX_JUMPS)["power"], 2.5025)

    # ---- R4: engineering at an engineer moves the range before the next Loadout ----
    def loadout(self, ts, rng=80.403503, opt=1997.5, extra=()):
        fsd = {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size5_class5", "Engineering": {"Modifiers": [
            {"Label": "Mass", "Value": 26.0, "OriginalValue": 20.0}, {"Label": "Integrity", "Value": 84.0, "OriginalValue": 120.0},
            {"Label": "FSDOptimalMass", "Value": opt, "OriginalValue": 1175.0}]}}
        self.j.handle({"event": "Loadout", "timestamp": ts, "Ship": "mandalay", "ShipID": 32, "UnladenMass": 324.450012,
                       "MaxJumpRange": rng, "FuelCapacity": {"Main": 32.0, "Reserve": 0.5},
                       "Modules": [fsd, {"Slot": "Slot03_Size5", "Item": "int_guardianfsdbooster_size5"},
                                   {"Slot": "LifeSupport", "Item": "int_lifesupport_size4_class2"}, *extra]})

    def craft(self, ts, slot, module, mods):
        self.j.handle({"event": "EngineerCraft", "timestamp": ts, "Slot": slot, "Module": module, "BlueprintName": "x",
                       "Level": 5, "Ingredients": [], "Modifiers": mods})

    def test_engineer_craft_moves_the_range(self):   # R4
        # the author's journal, 2025-03-18: Loadout 80.403503 ly, a Mass Manager craft (optimal mass 1997.5 -> 2077.4)
        # and 52 jumps before the next Loadout, which said 83.199631 ly
        self.loadout("2025-03-18T04:37:11Z")
        self.j.fuel_hist = [list(x) for x in self.MANDALAY_JUMPS]
        self.j.jump_range = {"ly": 80.403503, "ts": "2025-03-18T04:37:11Z"}
        drive = "int_hyperdrive_overcharge_size5_class5"
        self.craft("2025-03-18T04:40:18Z", "FrameShiftDrive", drive, [
            {"Label": "Mass", "Value": 26.0, "OriginalValue": 20.0}, {"Label": "Integrity", "Value": 77.28, "OriginalValue": 120.0},
            {"Label": "FSDOptimalMass", "Value": 2077.399902, "OriginalValue": 1175.0}])
        self.assertAlmostEqual(self.j.ship["max_range"], 83.199631, delta=0.005)
        self.assertAlmostEqual(self.j.ship["unladen"], 324.45, delta=0.01)
        self.assertAlmostEqual(self.j.jump_range["ly"], 83.199631, delta=0.005)
        self.assertEqual(self.j.fuel_hist, [])                           # the old drive's samples: gone, as on a refit
        # a 77.5 ly jump the engineered drive makes (at ~356 t) is in range now
        m = ed_outrider.fuel_model(dict(self.j.ship, max_fuel=5.2), [])
        self.assertGreater(ed_outrider.fsd_range(m, 356), 77.5)
        # jumps after the craft are kept when the next Loadout says what was worked out
        self.j.handle({"event": "Cargo", "timestamp": "2025-03-18T04:41:00Z", "Vessel": "Ship", "Count": 0})
        self.j.handle({"event": "FSDJump", "timestamp": "2025-03-18T04:50:00Z", "StarSystem": "S", "SystemAddress": 5,
                       "StarPos": [1, 0, 0], "JumpDist": 77.5, "FuelUsed": 4.9, "FuelLevel": 27.0})
        self.loadout("2025-03-18T05:55:37Z", rng=83.199631, opt=2077.399902)
        self.assertEqual(len(self.j.fuel_hist), 1)
        # a lightweight craft on another module: 4 t off the unladen mass (a module the Loadout listed stock)
        r0 = self.j.ship["max_range"]
        self.craft("2025-03-18T06:00:00Z", "LifeSupport", "int_lifesupport_size4_class2",
                   [{"Label": "Mass", "Value": 1.8, "OriginalValue": 4.0}, {"Label": "Integrity", "Value": 50, "OriginalValue": 70}])
        self.assertAlmostEqual(self.j.ship["unladen"], 324.45 - 2.2, delta=0.01)
        self.assertAlmostEqual(self.j.ship["max_range"] - 10.5, (r0 - 10.5) * (324.45 + 5.2) / (322.25 + 5.2), delta=0.02)
        self.assertEqual(self.j.fuel_hist, [])                           # 2.2 t is a refit: the samples were heavier
        # a craft that changes nothing about the range (a faster boot) and a craft on another ship's drive: no change
        before = dict(self.j.ship)
        self.craft("2025-03-18T06:01:00Z", "PowerDistributor", "int_powerdistributor_size7_class5",
                   [{"Label": "WeaponsCapacity", "Value": 60, "OriginalValue": 50}])
        self.craft("2025-03-18T06:02:00Z", "FrameShiftDrive", "int_hyperdrive_size6_class5",
                   [{"Label": "FSDOptimalMass", "Value": 2900, "OriginalValue": 1800}])
        self.assertEqual(self.j.ship, before)
        # a blueprint that drops a modifier the drive had (optimal mass back to a stock value the event doesn't
        # give): left alone until the next Loadout
        self.craft("2025-03-18T06:03:00Z", "FrameShiftDrive", drive, [{"Label": "Mass", "Value": 20.0, "OriginalValue": 20.0},
                                                                     {"Label": "BootTime", "Value": 4, "OriginalValue": 10}])
        self.assertEqual(self.j.ship["max_range"], before["max_range"])
        # a Mass Manager on MaxFuelPerJump (p known from the drive): the range grows as MaxFuelPerJump^(1/p)
        self.loadout("2025-03-18T07:00:00Z", rng=83.199631, opt=2077.399902)
        self.j.ship["max_fuel"] = None
        self.craft("2025-03-18T07:01:00Z", "FrameShiftDrive", drive, [
            {"Label": "Mass", "Value": 26.0, "OriginalValue": 20.0}, {"Label": "FSDOptimalMass", "Value": 2077.399902, "OriginalValue": 1175.0},
            {"Label": "MaxFuelPerJump", "Value": 5.72, "OriginalValue": 5.2}])
        self.assertEqual(self.j.ship["max_fuel"], 5.72)
        want = (83.199631 - 10.5) * (324.45 + 5.2) / (324.45 + 5.72) * (5.72 / 5.2) ** (1 / 2.45) + 10.5
        self.assertAlmostEqual(self.j.ship["max_range"], want, delta=0.005)
        # the craft is replayed on a re-read before a newer Loadout: that Loadout wins
        self.loadout("2025-03-18T08:00:00Z", rng=90.0)
        self.craft("2025-03-18T07:30:00Z", "FrameShiftDrive", drive, [{"Label": "FSDOptimalMass", "Value": 3000, "OriginalValue": 1175.0},
                                                                     {"Label": "Mass", "Value": 26.0, "OriginalValue": 20.0}])
        self.assertEqual(self.j.ship["max_range"], 90.0)

    # ---- R14: a tank under one max jump's fuel ----
    def test_low_tank_caps_the_range_and_reach(self):   # R14
        m = ed_outrider.fuel_model(self.MANDALAY, self.MANDALAY_JUMPS)
        mass = m["unladen"] + 3.0
        full = ed_outrider.fsd_range(m, mass)
        capped = ed_outrider.fsd_range(m, mass, 3.0)
        self.assertAlmostEqual(capped, full * (3.0 / m["max_fuel"]) ** (1 / m["power"]), places=6)
        self.assertAlmostEqual(ed_outrider.hop_fuel(m, capped, mass), 3.0, places=6)   # the jump 3 t pays for
        self.assertEqual(ed_outrider.fsd_range(m, mass, 20.0), full)      # a tank over one max jump: no cap
        self.j.pos = {"id64": 9, "name": "Here", "x": 0, "y": 0, "z": 0, "ts": "2026-01-01T00:00:00Z"}
        self.db.execute("INSERT INTO route_systems VALUES (77, 'Far', 75.6, 0, 0, 'K', 'x')")
        self.j.ship = dict(self.MANDALAY, fuel_main=32.0)
        self.j.fuel_hist = [list(x) for x in self.MANDALAY_JUMPS]
        self.j.status_json = {"live": True, "fuel_main": 3.0, "cargo": 0}
        h = self.state.target_hop({"id64": 77, "name": "Far"})
        self.assertFalse(h["reach"])                                     # was True: "4.0 t · leaves 0 max jumps"
        self.assertGreater(h["fuel"], 3.0)
        self.assertAlmostEqual(self.state.range_now(), round(capped, 2), places=2)
        self.assertLess(self.state.range_now(), 70)
        self.j.status_json["fuel_main"] = 30.0                           # a full tank reaches it
        self.assertTrue(self.state.target_hop({"id64": 77, "name": "Far"})["reach"])

    # ---- R15: how many jumps the fit still needs, and jumps before any Cargo record ----
    def test_fit_says_how_many_jumps_it_needs(self):   # R15
        new = dict(self.NX, fsd="int_hyperdrive_overcharge_size8_class5_x")   # p to fit: five jumps
        self.assertEqual(ed_outrider.fuel_model(new, self.NX_JUMPS[:3])["need"], 2)
        self.assertEqual(ed_outrider.fuel_model(new, self.NX_JUMPS[:5])["need"], 0)
        self.assertEqual(ed_outrider.fuel_model(self.NX, self.NX_JUMPS[:1])["need"], 2)   # p known: three for MaxFuelPerJump
        self.assertEqual(ed_outrider.fuel_model(self.NX, [])["need"], 3)
        self.assertEqual(ed_outrider.fuel_model(dict(self.NX, max_fuel=6.8), [])["need"], 0)
        self.assertEqual(ed_outrider.fuel_model(new, [s[:3] + [None] for s in self.NX_JUMPS])["need"], 5)   # no cargo figure
        self.j.ship = dict(self.NX, fuel_main=160.0)
        self.j.status_json = {"live": True, "fuel_main": 150.0, "cargo": 32, "ts": "2026-07-01T11:00:05Z"}
        self.assertEqual(self.state.fuel_summary()["model"]["need"], 3)
        # no Cargo record read yet: a live Status.json hold read within two minutes of the jump stands in
        self.j.handle({"event": "FSDJump", "timestamp": "2026-07-01T11:00:00Z", "StarSystem": "S", "SystemAddress": 5,
                       "StarPos": [1, 0, 0], "JumpDist": 52.561, "FuelUsed": 2.873145, "FuelLevel": 157.126862})
        self.assertEqual(self.j.fuel_hist[-1][3], 32)
        self.j.status_json["ts"] = "2026-07-01T12:00:00Z"                 # an hour off (a journal being caught up on)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-07-01T11:01:00Z", "StarSystem": "T", "SystemAddress": 6,
                       "StarPos": [2, 0, 0], "JumpDist": 17.58, "FuelUsed": 0.185373, "FuelLevel": 159.814621})
        self.assertIsNone(self.j.fuel_hist[-1][3])
        self.j.handle({"event": "Cargo", "timestamp": "2026-07-01T11:02:00Z", "Vessel": "Ship", "Count": 16})
        self.j.status_json = {"live": True, "fuel_main": 150.0, "cargo": 32, "ts": "2026-07-01T11:03:00Z"}
        self.j.handle({"event": "FSDJump", "timestamp": "2026-07-01T11:03:00Z", "StarSystem": "U", "SystemAddress": 7,
                       "StarPos": [3, 0, 0], "JumpDist": 17.58, "FuelUsed": 0.185373, "FuelLevel": 159.814621})
        self.assertEqual(self.j.fuel_hist[-1][3], 16)                    # the journal's Cargo, once there is one

    # ---- R16: an Apex shuttle or multicrew jump is not your tank's ----
    def test_rides_leave_the_scoop_counts(self):   # R16
        self.j.status_json = {"live": True, "fuel_main": 20.0}
        self.j.ship = {"fuel_main": 32.0}
        self.j.last_scoop = "2026-01-01T00:00:00Z"
        for k in range(8):
            self.j.handle({"event": "FSDJump", "timestamp": f"2026-01-01T00:0{k + 1}:00Z", "StarSystem": f"S{k}",
                           "SystemAddress": 10 + k, "StarPos": [k, 0, 0], "FuelUsed": 1.0, "JumpDist": 10})
            self.db.execute("UPDATE jumps SET star_class = 'K' WHERE id64 = ?", (10 + k,))
        for k in range(5):   # a five-jump Apex ride to M stars, and one in another commander's ship
            self.j.handle({"event": "FSDJump", "timestamp": f"2026-01-01T01:0{k}:00Z", "StarSystem": f"T{k}",
                           "SystemAddress": 30 + k, "StarPos": [50 + k, 0, 0], "Taxi": True})
            self.db.execute("UPDATE jumps SET star_class = 'L' WHERE id64 = ?", (30 + k,))
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T01:30:00Z", "StarSystem": "M", "SystemAddress": 40,
                       "StarPos": [70, 0, 0], "Multicrew": True})
        self.db.execute("UPDATE jumps SET star_class = 'T' WHERE id64 = 40")
        self.assertEqual(self.db.execute("SELECT count(*) FROM jumps WHERE ride = 1").fetchone()[0], 6)
        self.assertEqual(self.state.fuel_summary()["since_scoop"], 8)     # was 14
        self.assertEqual(self.state.scoop_rate(), {"scoopable": 8, "of": 8, "dry_run": 0})   # was 8 of 14, 6 dry
