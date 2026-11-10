"""Modules left switched off after an AFMU repair: the spoken alert (Journals.module_left_off, loadout_modules,
State.module_watch). Life support repeats while the in-danger flag is on; the others get one reminder. The flags are as
read in a live game on 2026-11-09 (docs/JOURNAL_REFERENCE.md). Fakes only: no game, no real data."""
import time
import types
import unittest

from support import ed_outrider

SHIP = ed_outrider.FLAG_IN_MAIN_SHIP
DANGER = ed_outrider.outrider.target.FLAG_IN_DANGER
SHIELDS = ed_outrider.FLAG_SHIELDS_UP
FIRST, REPEAT, SETTLE = ed_outrider.LIFE_SUPPORT_FIRST_S, ed_outrider.LIFE_SUPPORT_REPEAT_S, ed_outrider.MODULES_OFF_SETTLE_S
LIFE = "$int_lifesupport_size5_class2_name;"
FSD = "$int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii_name;"
SCOOP = "$int_fuelscoop_size7_class5_name;"
SHIELD = "$int_shieldgenerator_size5_class2_name;"
DOCK = "$int_dockingcomputer_advanced_name;"


class ModuleOff(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.t0 = int(time.time())

    def iso(self, off=0):
        return ed_outrider.iso_ts(self.t0 + off)

    def repair(self, module, label="", off=0):
        self.j.handle({"timestamp": self.iso(off), "event": "AfmuRepairs", "Module": module, "Module_Localised": label,
                       "FullyRepaired": True, "Health": 1.0})

    def loadout(self, modules, off=0):
        self.j.handle({"timestamp": self.iso(off), "event": "Loadout", "Ship": "explorer_nx", "ShipID": 39,
                       "Modules": [{"Slot": str(n), "Item": i, "On": on} for n, (i, on) in enumerate(modules)]})

    def watch(self, off, flags=SHIP, live=True):
        self.state.module_watch({"live": live, "flags": flags}, self.t0 + off)

    def said(self, kind):
        return [m for m in self.j.moments if m["kind"] == kind]

    def test_life_support_waits_for_the_flag_to_settle_then_repeats_until_it_clears(self):
        self.repair(LIFE, "Life Support")
        self.watch(FIRST - 1, SHIP | DANGER)
        self.assertEqual(self.said("life_support"), [])                  # the first few seconds: you may be switching it on
        self.watch(FIRST, SHIP | DANGER)
        self.assertEqual(len(self.said("life_support")), 1)
        self.watch(FIRST + REPEAT - 1, SHIP | DANGER)
        self.assertEqual(len(self.said("life_support")), 1)
        self.watch(FIRST + REPEAT, SHIP | DANGER)
        self.assertEqual(len(self.said("life_support")), 2)
        self.watch(FIRST + REPEAT + 1, SHIP)                             # switched back on: the flag clears
        self.assertIsNone(self.j.life_support_off)
        self.watch(FIRST + 2 * REPEAT, SHIP | DANGER)                    # danger later (heat) is no longer about this
        self.assertEqual(len(self.said("life_support")), 2)

    def test_life_support_already_back_on_says_nothing(self):
        self.repair(LIFE, "Life Support")
        self.watch(FIRST, SHIP)
        self.assertEqual(self.said("life_support"), [])
        self.assertIsNone(self.j.life_support_off)

    def test_the_danger_flag_alone_never_starts_it(self):
        self.watch(0, SHIP | DANGER)
        self.watch(FIRST + REPEAT, SHIP | DANGER)
        self.assertEqual(self.said("life_support"), [])

    def test_a_later_repair_does_not_hold_back_life_support(self):
        """2026-09-25: repairs went on for 7 minutes with life support off. It must not wait for the run to end."""
        self.repair(LIFE, "Life Support")
        for off in range(5, FIRST + 1, 5):
            self.repair(SCOOP, "Fuel Scoop", off=off)
        self.watch(FIRST, SHIP | DANGER)
        self.assertEqual(len(self.said("life_support")), 1)
        self.assertEqual(self.said("modules_off"), [])                   # the others wait for the run's end

    def test_a_run_of_repairs_is_one_reminder_critical_first(self):
        self.repair(DOCK, "Docking Computer")
        self.repair(SCOOP, "Fuel Scoop", off=5)
        self.repair(FSD, "FSD (SCO)", off=10)
        self.watch(10 + SETTLE - 1)
        self.assertEqual(self.said("modules_off"), [])
        self.watch(10 + SETTLE)
        self.assertEqual([m["modules"] for m in self.said("modules_off")], [["FSD", "fuel scoop", "docking computer"]])
        self.watch(10 + SETTLE + 300)
        self.assertEqual(len(self.said("modules_off")), 1)               # said once: nothing shows it came back on

    def test_a_modules_game_name_loses_its_bracket(self):
        self.assertEqual(ed_outrider.module_words("int_guardianfsdbooster_size5", "Guardian FSD Booster (Mk II)"),
                         "guardian fsd booster")
        self.assertEqual(ed_outrider.module_words("int_mystery"), "a module")

    def test_shields_already_up_are_not_said_and_down_are(self):
        self.repair(SHIELD, "Shield Generator")
        self.watch(SETTLE, SHIP | SHIELDS)
        self.assertEqual(self.said("modules_off"), [])
        self.repair(SHIELD, "Shield Generator", off=SETTLE)
        self.watch(2 * SETTLE, SHIP)
        self.assertEqual([m["modules"] for m in self.said("modules_off")], [["shields"]])

    def test_a_replayed_journal_says_nothing(self):
        self.j.handle({"timestamp": "2026-09-25T21:33:31Z", "event": "AfmuRepairs", "Module": LIFE, "Module_Localised": "Life Support",
                       "FullyRepaired": True, "Health": 1.0})
        self.j.handle({"timestamp": "2026-09-25T21:33:40Z", "event": "AfmuRepairs", "Module": FSD, "Module_Localised": "FSD (SCO)",
                       "FullyRepaired": True, "Health": 1.0})
        self.assertIsNone(self.j.life_support_off)
        self.assertEqual(self.j.modules_off, {})

    def test_a_loadout_listing_life_support_off_is_said_even_without_the_flag(self):
        """The login the day after the 2026-09-25 death still listed it off; docked, no danger flag need be set."""
        self.loadout([("int_lifesupport_size5_class2", False)])
        self.watch(FIRST, SHIP)
        self.assertEqual(len(self.said("life_support")), 1)
        self.assertIsNone(self.j.life_support_off)                       # said once with no flag to keep it going

    def test_a_loadout_says_a_critical_module_once_a_login(self):
        self.loadout([("int_sensors_size8_class2", False), ("int_dockingcomputer_advanced", False)])
        self.watch(SETTLE)
        self.assertEqual([m["modules"] for m in self.said("modules_off")], [["sensors"]])   # not the docking computer
        self.loadout([("int_sensors_size8_class2", False)], off=SETTLE)                     # a docking's Loadout
        self.watch(2 * SETTLE)
        self.assertEqual(len(self.said("modules_off")), 1)
        self.j.handle({"timestamp": self.iso(2 * SETTLE), "event": "LoadGame", "Commander": "C", "FID": "F1"})
        self.loadout([("int_sensors_size8_class2", False)], off=2 * SETTLE)                 # the next login: said again
        self.watch(3 * SETTLE)
        self.assertEqual(len(self.said("modules_off")), 2)

    def test_a_loadout_listing_it_on_cancels_a_waiting_alert(self):
        self.repair(LIFE, "Life Support")
        self.repair(FSD, "FSD (SCO)")
        self.loadout([("int_lifesupport_size5_class2", True), ("int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii", True)], off=1)
        self.watch(max(FIRST, SETTLE) + 1, SHIP | DANGER)
        self.assertEqual(self.said("life_support"), [])
        self.assertEqual(self.said("modules_off"), [])

    def test_death_and_quitting_end_it(self):
        for event in ("Died", "Shutdown"):
            self.repair(LIFE, "Life Support")
            self.repair(FSD, "FSD (SCO)")
            self.j.handle({"timestamp": self.iso(1), "event": event})
            self.assertIsNone(self.j.life_support_off, event)
            self.assertEqual(self.j.modules_off, {}, event)

    def test_a_failed_tick_does_not_lose_or_double_it(self):
        self.repair(LIFE, "Life Support")
        cp = self.j.checkpoint()
        self.j.life_support_off = None
        self.j.modules_off["int_x"] = "x"
        self.j.restore(cp)
        self.assertIsNotNone(self.j.life_support_off)
        self.assertEqual(self.j.modules_off, {})


if __name__ == "__main__":
    unittest.main()
