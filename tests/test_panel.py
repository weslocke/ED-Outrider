"""The tablet's Ship page, the server's side: outrider/panel.py's lights and State.panel, panel_ack and panel_watch. The
flags are as a live game wrote them on 2026-11-09 (docs/JOURNAL_REFERENCE.md). Fakes only: no game, no real data."""
import json
import time
import types
import unittest

from support import ed_outrider
import outrider.panel as P

SHIP = P.FLAG_IN_MAIN_SHIP
FULL = SHIP | P.FLAG_SHIELDS_UP


def level(lights, id_):
    return next(l for l in lights if l["id"] == id_)


class Lights(unittest.TestCase):
    def test_a_normal_flight_is_a_dark_board(self):
        self.assertEqual({l["level"] for l in P.lights(FULL)}, {"off"})

    def test_every_lit_light_has_words(self):
        """Never colour alone."""
        lit = P.lights(SHIP | P.FLAG_IN_DANGER | P.FLAG_OVERHEATING | P.FLAG_INTERDICTED | P.FLAG_MASS_LOCKED | P.FLAG_FSD_CHARGING | P.FLAG_SILENT,
                       legal="Wanted", life_support="live", off_words=["FSD"], under_attack=True, canopy=True)
        self.assertEqual([l["id"] for l in lit if l["level"] != "off" and not l["words"]], ["life_support"])   # the page's oxygen line

    def test_danger_is_explained_or_red(self):
        danger = SHIP | P.FLAG_IN_DANGER
        self.assertEqual(level(P.lights(danger), "danger")["level"], "warning")
        got = level(P.lights(danger, settling=True), "danger")
        self.assertEqual((got["level"], got["words"]), ("settling", "FSD settling"))
        got = level(P.lights(danger, life_support="live"), "danger")
        self.assertEqual((got["level"], got["words"]), ("settling", "life support off"))
        self.assertEqual(level(P.lights(danger, settling=True, under_attack=True), "danger")["level"], "warning")
        self.assertEqual(level(P.lights(danger | P.FLAG_INTERDICTED, life_support="live"), "danger")["level"], "warning")

    def test_shields_only_when_there_is_something_to_say(self):
        self.assertEqual(level(P.lights(SHIP), "shields")["level"], "caution")
        self.assertEqual(level(P.lights(SHIP, has_shields=False), "shields")["level"], "off")        # none fitted
        self.assertEqual(level(P.lights(SHIP | P.FLAG_DOCKED), "shields")["level"], "off")
        self.assertEqual(level(P.lights(SHIP | P.FLAG_LANDED), "shields")["level"], "off")
        self.assertEqual(level(P.lights(0), "shields")["level"], "off")                              # in the SRV or on foot
        self.assertEqual(level(P.lights(SHIP, shields_repaired=True), "shields")["words"], "repaired · recharging")

    def test_overheat_is_red_while_hot_then_a_latched_reminder(self):
        self.assertEqual(level(P.lights(SHIP | P.FLAG_OVERHEATING), "overheat")["level"], "warning")
        got = level(P.lights(SHIP, overheated=38), "overheat")
        self.assertEqual((got["level"], got["words"], got["latched"]), ("advisory", "38 s · check modules", True))

    def test_the_rest_named_with_a_capital(self):
        got = level(P.lights(SHIP, off_words=["FSD", "fuel scoop"]), "off_after_repair")
        self.assertEqual((got["level"], got["words"], got["latched"]), ("caution", "FSD · Fuel scoop · tap when back on", True))

    def test_only_a_real_legal_state_is_wanted(self):
        for fine in ("Clean", "Allied", "Thargoid", None, ""):
            self.assertEqual(level(P.lights(SHIP, legal=fine), "wanted")["level"], "off", fine)
        self.assertEqual(level(P.lights(SHIP, legal="Warrant"), "wanted")["words"], "warrant")

    def test_fsd_charging_and_cooldown(self):
        self.assertEqual(level(P.lights(SHIP | P.FLAG_FSD_CHARGING), "fsd")["words"], "charging")
        self.assertEqual(level(P.lights(SHIP | P.FLAG_FSD_COOLDOWN), "fsd")["words"], "cooldown")


class ShipPanel(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.t0 = int(time.time())

    def iso(self, off=0):
        return ed_outrider.iso_ts(self.t0 + off)

    def status(self, flags, **kw):
        self.j.status_json = dict({"live": True, "flags": flags, "ts": self.iso()}, **kw)

    def lights(self, off=0):
        return self.state.panel(self.t0 + off)["lights"]

    def loadout(self, modules, off=0):
        self.j.handle({"timestamp": self.iso(off), "event": "Loadout", "Ship": "explorer_nx", "ShipID": 39, "ShipIdent": "BR-03E", "MaxJumpRange": 90.7,
                       "FuelCapacity": {"Main": 160}, "Modules": [dict({"Slot": s, "Item": i, "Health": h, "On": on}) for s, i, h, on in modules]})

    def repair(self, module, label, off=0):
        self.j.handle({"timestamp": self.iso(off), "event": "AfmuRepairs", "Module": module, "Module_Localised": label, "FullyRepaired": True, "Health": 1.0})

    def test_the_payload_has_the_panel_as_json(self):
        self.status(FULL, pips=[2, 8, 2], cargo=0.0, balance=18579866357)
        got = json.loads(json.dumps(self.state.panel()))
        self.assertEqual((got["pips"], got["cargo"], got["balance"], got["live"]), ([2, 8, 2], 0.0, 18579866357, True))

    def test_status_reading_keeps_the_pips_and_legal_state(self):
        st = self.j.status_reading({"timestamp": self.iso(), "Flags": FULL, "Flags2": 0, "Fuel": {"FuelMain": 160.0}, "Pips": [2, 8, 2], "LegalState": "Wanted", "Balance": 5}, None)
        self.assertEqual((st["pips"], st["legal"], st["balance"]), ([2, 8, 2], "Wanted", 5))

    def test_life_support_lights_with_the_oxygen_from_its_rating(self):
        self.loadout([("LifeSupport", "int_lifesupport_size5_class2", 1.0, True)])
        self.status(SHIP | P.FLAG_IN_DANGER)
        self.state.panel_watch(self.j.status_json, self.t0)
        self.repair("$int_lifesupport_size5_class2_name;", "Life Support", off=6)
        got = self.state.panel(self.t0 + 110)
        self.assertEqual(level(got["lights"], "life_support")["level"], "warning")
        self.assertEqual(level(got["lights"], "danger")["words"], "life support off")
        self.assertEqual(got["oxygen_left"], 450 - 110)                      # a D-rated module, counted from the flag

    def test_life_support_goes_out_with_the_flag(self):
        self.status(SHIP | P.FLAG_IN_DANGER)
        self.repair("$int_lifesupport_size5_class2_name;", "Life Support")
        self.state.module_watch(self.j.status_json, self.t0 + ed_outrider.LIFE_SUPPORT_FIRST_S)
        self.status(SHIP)
        self.state.module_watch(self.j.status_json, self.t0 + ed_outrider.LIFE_SUPPORT_FIRST_S + 1)
        self.assertEqual(level(self.lights(), "life_support")["level"], "off")

    def test_off_after_repair_lists_critical_first_and_a_tap_clears_it(self):
        self.status(FULL)
        self.repair("$int_dockingcomputer_advanced_name;", "Docking Computer")
        self.repair("$int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii_name;", "FSD (SCO)")
        got = level(self.lights(), "off_after_repair")
        self.assertEqual(got["words"], "FSD · Docking computer · tap when back on")
        self.state.module_watch(self.j.status_json, self.t0 + 600)           # said out loud: the light stays
        self.assertEqual(level(self.lights(), "off_after_repair")["level"], "caution")
        self.assertTrue(self.state.panel_ack("off_after_repair"))
        self.assertEqual(level(self.lights(), "off_after_repair")["level"], "off")

    def test_a_loadout_listing_it_on_clears_the_light(self):
        self.status(FULL)
        self.repair("$int_fuelscoop_size7_class5_name;", "Fuel Scoop")
        self.loadout([("Slot01_Size7", "int_fuelscoop_size7_class5", 1.0, True)], off=1)
        self.assertEqual(level(self.lights(), "off_after_repair")["level"], "off")

    def test_shields_repaired_until_they_are_back_up(self):
        self.status(SHIP)
        self.repair("$int_shieldgenerator_size5_class2_name;", "Shield Generator")
        got = self.lights()
        self.assertEqual(level(got, "shields")["words"], "repaired · recharging")
        self.assertEqual(level(got, "off_after_repair")["level"], "off")     # shields have their own light
        self.status(FULL)
        self.state.panel_watch(self.j.status_json, self.t0 + 180)
        self.assertEqual(self.j.modules_left, {})

    def test_an_overheat_is_timed_and_cleared_by_a_loadout(self):
        self.status(SHIP | P.FLAG_OVERHEATING)
        self.state.panel_watch(self.j.status_json, self.t0)
        self.status(SHIP)
        self.state.panel_watch(self.j.status_json, self.t0 + 38)
        self.assertEqual(level(self.lights(), "overheat")["words"], "38 s · check modules")
        self.loadout([("LifeSupport", "int_lifesupport_size5_class2", 1.0, True)], off=40)
        self.assertEqual(level(self.lights(), "overheat")["level"], "off")

    def test_under_attack_clears_after_a_quiet_minute_or_a_tap(self):
        self.status(FULL)
        self.j.handle({"timestamp": self.iso(), "event": "UnderAttack", "Target": "You"})
        self.assertEqual(level(self.lights(59), "under_attack")["level"], "warning")
        self.assertEqual(level(self.lights(60), "under_attack")["level"], "off")
        self.assertEqual(level(self.lights(0), "under_attack")["level"], "warning")
        self.state.panel_ack("under_attack")
        self.assertEqual(level(self.lights(0), "under_attack")["level"], "off")

    def test_a_replayed_attack_says_nothing(self):
        self.status(FULL)
        self.j.handle({"timestamp": "2026-01-01T00:00:00Z", "event": "UnderAttack", "Target": "You"})
        self.j.handle({"timestamp": "2026-01-01T00:00:01Z", "event": "CockpitBreached"})
        self.assertIsNone(self.j.under_attack_at)
        self.assertFalse(self.j.canopy_breached)

    def test_a_breached_canopy_lasts_until_docked_or_repaired(self):
        self.status(FULL)
        for clear in ("Docked", "RepairAll"):
            self.j.handle({"timestamp": self.iso(), "event": "CockpitBreached"})
            self.assertEqual(level(self.lights(), "canopy")["level"], "warning")
            self.j.handle({"timestamp": self.iso(1), "event": clear, "StationName": "X", "MarketID": 1, "StarSystem": "S", "SystemAddress": 1, "StationType": "Coriolis", "Cost": 0})
            self.assertEqual(level(self.lights(), "canopy")["level"], "off", clear)

    def test_clear_puts_out_every_latched_light_and_no_other_id_works(self):
        self.status(FULL)
        self.j.handle({"timestamp": self.iso(), "event": "UnderAttack", "Target": "You"})
        self.j.handle({"timestamp": self.iso(), "event": "CockpitBreached"})
        self.j.overheated = 12
        self.repair("$int_fuelscoop_size7_class5_name;", "Fuel Scoop")
        self.assertFalse(self.state.panel_ack("danger"))
        self.assertTrue(self.state.panel_ack("all"))
        self.assertEqual({l["level"] for l in self.lights()}, {"off"})

    def test_lowest_module_and_whether_shields_are_fitted(self):
        self.status(FULL)
        self.loadout([("Slot14_Size1", "int_dockingcomputer_advanced", 0.7, True), ("Radar", "int_sensors_size8_class2", 0.98, True)])
        self.assertEqual(self.state.panel()["lowest_module"], 70)
        self.status(SHIP)
        self.assertEqual(level(self.lights(), "shields")["level"], "off")    # no shield generator in that Loadout


if __name__ == "__main__":
    unittest.main()
