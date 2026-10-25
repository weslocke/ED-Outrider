"""The tablet's control rail (tablet plan phase 4): contexts, the agreed default sets, button states from Status.json,
bindings per preset category, one tap of the right keys, and every refusal. Never a real device: _fake_evdev (key
codes, no UInput) and a recording stand-in for the virtual keyboard."""
import asyncio
import os
import tempfile
import threading
import unittest

from support import _fake_evdev, ed_outrider, make_controls

import outrider.honk  # noqa: E402
import outrider.rail as rail  # noqa: E402

F = lambda *bits: sum(1 << b for b in bits)   # noqa: E731


class RecordingUI:
    """The virtual keyboard's stand-in: records (key name, down/up)."""

    def __init__(self, evdev):
        self.names = {v: k for k, v in evdev.ecodes.ecodes.items()}
        self.events, self.closed = [], False

    def write(self, _type, code, value):
        self.events.append((self.names[code], value))

    def syn(self):
        pass

    def close(self):
        self.closed = True


def binds_xml(name, actions):
    """A .binds file giving each action a keyboard Secondary binding: {action: "Key_X"} or (key, [modifiers])."""
    body = ""
    for a, k in actions.items():
        key, mods = (k, []) if isinstance(k, str) else k
        mod = "".join(f'<Modifier Device="Keyboard" Key="{m}" />' for m in mods)
        body += f'<{a}><Primary Device="SaitekX56Joystick" Key="Joy_1" /><Secondary Device="Keyboard" Key="{key}">{mod}</Secondary></{a}>'
    return f'<?xml version="1.0" encoding="UTF-8" ?><Root PresetName="{name}">{body}</Root>'


class Pure(unittest.TestCase):
    def test_contexts(self):
        cases = [({"live": False, "flags": F(24)}, None, (None, "the game is not running")),
                 ({"live": True, "flags": F(24)}, None, ("ship", None)),
                 ({"live": True, "flags": F(24, 0)}, None, (None, "docked")),
                 ({"live": True, "flags": F(26)}, "testbuggy", ("srv", None)),
                 ({"live": True, "flags": F(26)}, "combat_multicrew_srv_01", ("srv", None)),
                 ({"live": True, "flags": F(26)}, "lander01", ("nomad", None)),
                 ({"live": True, "flags": F(25)}, None, ("fighter", None)),
                 ({"live": True, "flags": 0, "flags2": F(0)}, None, ("foot", None)),
                 # Status.json Flags2: OnFootInStation 3, InHangar 13, SocialSpace 14 (a planetary port has 13 or 14
                 # with OnFootOnPlanet 4, not 3: the sweep of 2026-10-09); 1 is InTaxi
                 ({"live": True, "flags": 0, "flags2": F(0, 3)}, None, (None, "on foot in a station")),
                 ({"live": True, "flags": 0, "flags2": F(0, 4, 14)}, None, (None, "on foot in a station")),
                 ({"live": True, "flags": 0, "flags2": F(0, 4, 13)}, None, (None, "on foot in a station")),
                 ({"live": True, "flags": 0}, None, (None, "not in a ship, SRV, fighter or on foot"))]
        for st, veh, want in cases:
            self.assertEqual(rail.context_of(st, veh), want, (st, veh))

    def test_default_sets_are_the_agreed_ones(self):
        actions = {c: [rail.catalogue_entry(c, b["id"])["action"] for b in rail.default_set(c)] for c in rail.CONTEXTS}
        fixed = ["HideUI", "Screenshot", "HighResScreenshot"]   # the game's own keys, in every set (the author, 2026-10-25)
        self.assertTrue(all(v[-3:] == fixed for v in actions.values()))
        actions = {c: v[:-3] for c, v in actions.items()}
        self.assertEqual(actions["ship"], ["LandingGearToggle", "ToggleCargoScoop", "NightVisionToggle", "ShipSpotLightToggle",
                                           "ToggleFlightAssist", "ToggleButtonUpInput", "DeployHardpointToggle", "PlayerHUDModeToggle"])
        self.assertEqual(actions["srv"], ["ToggleDriveAssist", "HeadlightsBuggyButton", "AutoBreakBuggyButton", "NightVisionToggle",
                                          "ToggleBuggyTurretButton", "ToggleCargoScoop_Buggy", "PlayerHUDModeToggle_Buggy", "RecallDismissShip"])
        self.assertEqual(actions["nomad"], ["ToggleFlightAssist", "ShipSpotLightToggle", "NightVisionToggle"])
        self.assertEqual(actions["fighter"], actions["nomad"])
        self.assertEqual(actions["foot"], ["HumanoidToggleFlashlightButton", "HumanoidToggleNightVisionButton",
                                           "HumanoidToggleShieldsButton", "HumanoidSwitchToSuitTool"])
        self.assertTrue(all(len(v) <= rail.RAIL_MAX for v in actions.values()))
        self.assertEqual([b["id"] for b in rail.CATALOGUE["ship"] if b["amber"]], ["silent"])

    def test_short_labels(self):
        """A small tablet's narrow rail (under 1200 x 700 CSS px): every catalogue name has a short form of at most 10
        characters (the author's set, 2026-10-05); a name the player chose is shown as it is."""
        for c in rail.CONTEXTS:
            for b in rail.CATALOGUE[c]:
                self.assertIn(b["label"], rail.SHORT_LABELS, f"{c} {b['label']} has no short form")
                self.assertLessEqual(len(rail.short_label(b["label"])), 10, b["label"])
        self.assertEqual([rail.short_label(b["label"]) for b in rail.default_set("ship")],
                         ["Gear", "Scoop", "Night vis.", "Lights", "FA", "Silent", "Hardpts", "Analysis", "Hide UI", "Shot", "HiRes"])
        self.assertEqual(rail.short_label("Scoop!"), "Scoop!")

    def test_states(self):
        st = lambda c, i, **kw: rail.state_of(rail.catalogue_entry(c, i), dict(kw, live=True))   # noqa: E731
        self.assertEqual([st("ship", "gear", flags=F(2)), st("ship", "gear", flags=0)], ["on", "off"])
        self.assertEqual([st("ship", "fa", flags=0), st("ship", "fa", flags=F(5))], ["on", "off"])   # bit 5 is FA OFF
        self.assertEqual([st("ship", "silent", flags=F(10)), st("ship", "hud", flags=F(27)), st("ship", "nv", flags=F(28))], ["on"] * 3)
        self.assertEqual([st("srv", "head", flags=0), st("srv", "head", flags=F(8)), st("srv", "head", flags=F(8, 31))], ["off", "on", "high"])
        self.assertEqual([st("srv", "da", flags=F(15)), st("srv", "brake", flags=F(12)), st("srv", "turret", flags=F(13))], ["on"] * 3)
        self.assertEqual([st("foot", "torch", flags=F(8)), st("foot", "shields", flags=F(3))], ["on", "on"])
        self.assertEqual([st("foot", "bio", selected_weapon="$humanoid_sampletool_name;"), st("foot", "bio", selected_weapon="$humanoid_fists_name;"),
                          st("foot", "bio")], ["on", "off", None])
        self.assertEqual([st("srv", "recall", flags=F(2)), st("foot", "nv", flags=F(28))], [None, None])   # not reported
        # the game sets the hardpoints flag in supercruise (after a jump, Analysis mode on): not available there
        self.assertEqual([st("ship", "hard", flags=F(4, 6, 27)), st("ship", "hard", flags=F(4)), st("ship", "hard", flags=F(6)),
                          st("ship", "hard", flags=0)], ["na", "na", "on", "off"])
        self.assertEqual(rail.NA_WHY["hard"], "in supercruise")
        # landing gear and cargo scoop too (the author's choice); the SRV's scoop is never in supercruise
        self.assertEqual([st("ship", "gear", flags=F(4, 2)), st("ship", "scoop", flags=F(4, 9)), st("ship", "gear", flags=F(2)),
                          st("ship", "scoop", flags=F(9)), st("srv", "scoop", flags=F(9))], ["na", "na", "on", "on", "on"])
        self.assertEqual((rail.NA_WHY["gear"], rail.NA_WHY["scoop"]), ("in supercruise", "in supercruise"))

    def test_check_set(self):
        ok, why = rail.check_set("ship", [{"id": "fa", "label": "  F.A.   toggle  "}, {"id": "dock"}])
        self.assertEqual((ok, why), ([{"id": "fa", "label": "F.A. toggle"}, {"id": "dock", "label": "Fighter: dock"}], None))
        for bad in ([{"id": "fa"}, {"id": "fa"}], [{"id": "head"}], [{"id": "gear"}] * 9, "x", [{"label": "x"}]):
            self.assertIsNone(rail.check_set("ship", bad)[0], bad)
        self.assertEqual(rail.check_set("moon", [])[1], "unknown context")
        self.assertEqual(rail.check_set("ship", [{"id": "gear", "label": "x" * 50}])[0][0]["label"], "x" * rail.LABEL_MAX)


class Bindings(unittest.TestCase):
    def test_preset_per_category(self):
        """SRV controls come from StartPreset.4.start's third line, on-foot ones from its fourth (review: honk read only
        the General and Ship lines)."""
        with tempfile.TemporaryDirectory() as root:
            journals, binds = make_controls(self, root, start="Gen\nShipP\nBuggyP\nFootP")
            for name, key in (("Gen", "Key_G"), ("ShipP", "Key_S"), ("BuggyP", "Key_B"), ("FootP", "Key_F")):
                with open(os.path.join(binds, f"{name}.4.2.binds"), "w") as f:
                    f.write(binds_xml(name, {"NightVisionToggle": key, "UI_Select": key, "HumanoidToggleShieldsButton": key}))
            kb = outrider.honk.keyboard_bindings
            self.assertEqual(kb([journals], ["NightVisionToggle"], category="srv")["NightVisionToggle"][0], ["KEY_B"])
            self.assertEqual(kb([journals], ["HumanoidToggleShieldsButton"], category="foot")["HumanoidToggleShieldsButton"][0], ["KEY_F"])
            self.assertEqual(kb([journals], ["NightVisionToggle"], category="ship")["NightVisionToggle"][0], ["KEY_S"])
            self.assertEqual(kb([journals], ["NightVisionToggle"])["NightVisionToggle"][0], ["KEY_S"])   # as before
            self.assertEqual(kb([journals], ["UI_Select"])["UI_Select"][0], ["KEY_G"])


class Tap(unittest.TestCase):
    def honker(self):
        ev = _fake_evdev()
        h = outrider.honk.Honker("KEY_K")
        h.evdev, h.ui = ev, RecordingUI(ev)
        return h

    def test_one_tap_of_the_keys(self):
        h = self.honker()
        h.tap(["KEY_LEFTALT", "KEY_K"], hold=0)
        self.assertEqual(h.ui.events, [("KEY_LEFTALT", 1), ("KEY_K", 1), ("KEY_K", 0), ("KEY_LEFTALT", 0)])

    def test_refusals(self):
        h = self.honker()
        with h.lock:   # auto honk or auto-target is pressing: refused at once, never queued
            with self.assertRaisesRegex(outrider.honk.NotNow, "auto honk or auto-target"):
                h.tap(["KEY_K"], hold=0)
        with self.assertRaisesRegex(outrider.honk.NotNow, "moved"):
            h.tap(["KEY_K"], check=lambda: "moved", hold=0)
        with self.assertRaises(ValueError):
            h.tap(["KEY_NOSUCH"], hold=0)
        self.assertEqual(h.ui.events, [])
        h.ui = None
        with self.assertRaises(ValueError):
            h.tap(["KEY_K"], hold=0)

    def test_close_during_a_tap(self):
        h = self.honker()
        ui = h.ui
        t = threading.Thread(target=lambda: h.tap(["KEY_K"], hold=0.3))
        t.start()
        threading.Event().wait(0.1)
        h.close("rail")
        t.join(2)
        self.assertEqual((ui.events, ui.closed, h.ui), ([("KEY_K", 1), ("KEY_K", 0)], True, None))

    # ---- R12: close() arriving while a tap or a press holds the lock (it leaves the closing to them) ----
    class LockThen:
        """The Honker's lock, running `then` once right after it is taken: close() lands at that moment."""

        def __init__(self, real, then):
            self.real, self.then = real, then

        def acquire(self, blocking=True, timeout=-1):
            ok = self.real.acquire(blocking, timeout)
            if ok and self.then:
                then, self.then = self.then, None
                then()
            return ok

        def release(self):
            self.real.release()

        def __enter__(self):
            self.acquire()

        def __exit__(self, *exc):
            self.release()

    def test_close_as_the_tap_takes_the_lock(self):
        h = self.honker()
        ui, h.owners = h.ui, {"rail"}
        h.lock = self.LockThen(h.lock, lambda: h.close("rail"))
        with self.assertRaises(ValueError):
            h.tap(["KEY_K"], hold=0)
        self.assertEqual((ui.closed, h.ui, ui.events), (True, None, []))

    def test_close_during_a_refused_tap(self):
        h = self.honker()
        ui, h.owners = h.ui, {"rail"}
        with self.assertRaises(outrider.honk.NotNow):
            h.tap(["KEY_K"], check=lambda: (h.close("rail"), "moved")[1], hold=0)
        self.assertEqual((ui.closed, h.ui), (True, None))

    def test_close_during_a_refused_press(self):
        h = self.honker()
        ui, h.owners, h.hold = h.ui, {"honk"}, 0
        with self.assertRaises(outrider.honk.NotNow):
            h.press(check=lambda: (h.close("honk"), "jumping")[1])
        self.assertEqual((ui.closed, h.ui, ui.events), (True, None, []))


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        journals, binds = make_controls(self, self.tmp.name, start="P\nP\nP\nP")
        with open(os.path.join(binds, "P.4.2.binds"), "w") as f:
            f.write(binds_xml("P", {"LandingGearToggle": ("Key_L", ["Key_LeftAlt"]), "ToggleCargoScoop": "Key_H",
                                    "ToggleDriveAssist": "Key_D"}).replace("</Root>",   # night vision on the HOTAS only
                    '<NightVisionToggle><Primary Device="SaitekX56Throttle" Key="Joy_5" /><Secondary Device="{NoDevice}" Key="" /></NightVisionToggle></Root>'))
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        ev = _fake_evdev()
        h = outrider.honk.Honker("KEY_K", journal_dirs=[journals])
        h.evdev, h.ui = ev, RecordingUI(ev)
        h.open = lambda owner="honk": (h.owners.add(owner), True)[1]   # never a real UInput
        self.state.honker = self.h = h
        self.ship(F(24))

    def ship(self, flags, flags2=0, live=True):
        self.state.journals.status_json = {"live": live, "flags": flags, "flags2": flags2}

    def press(self, ctx, id_):
        return asyncio.run(self.state.rail_press(ctx, id_))

    def test_info(self):
        r = self.state.rail_info()
        self.assertEqual((r["context"], r["can_press"], [b["id"] for b in r["buttons"]]),
                         ("ship", True, ["gear", "scoop", "nv", "lights", "fa", "silent", "hard", "hud", "hideui", "shot", "hires"]))
        gear, nv = r["buttons"][0], r["buttons"][2]
        self.assertEqual((gear["label"], gear["short"], nv["short"]), ("Landing gear", "Gear", "Night vis."))
        self.assertEqual((gear["bound"], gear["state"], nv["bound"], nv["action_label"]), (True, "off", False, "Night Vision Toggle"))
        self.assertIn("no keyboard binding", nv["why"])
        # bound on the HOTAS only: it says where, and that a keyboard key is what the rail needs (asked by the author)
        self.assertEqual(nv["now_on"], "Joy 5")
        self.assertIn("now only Joy 5 on SaitekX56Throttle", nv["why"])
        self.assertNotIn("or set", nv["why"])
        self.assertIsNone(r["buttons"][3]["now_on"])   # ship lights: bound nowhere
        self.assertEqual(self.state.payload()["rail"]["context"], "ship")   # in the long poll's payload: confirmed there
        full = self.state.rail_info(full=True)
        self.assertEqual(set(full["edit"]), set(rail.CONTEXTS))
        self.ship(F(24, 0))
        self.assertEqual((self.state.rail_info()["context"], self.state.rail_info()["why"]), (None, "docked"))

    def test_press_and_refusals(self):
        out, status = self.press("ship", "gear")
        self.assertEqual((status, out["before"], out["label"]), (200, "off", "Landing gear"))
        self.assertEqual(self.h.ui.events, [("KEY_LEFTALT", 1), ("KEY_L", 1), ("KEY_L", 0), ("KEY_LEFTALT", 0)])
        self.h.ui.events.clear()
        refusals = [("srv", "da", "not in the srv"), ("ship", "nv", "no keyboard binding"), ("ship", "nope", "no such button")]
        for ctx, id_, why in refusals:
            out, status = self.press(ctx, id_)
            self.assertIn(why, out["error"].lower())
        self.ship(F(24), live=False)
        self.assertIn("not running", self.press("ship", "gear")[0]["error"])
        self.ship(F(24))
        with self.h.lock:   # an auto-target run holds the keyboard
            self.assertIn("auto honk or auto-target", self.press("ship", "gear")[0]["error"])
        self.state.simulate = True
        self.assertIn("--simulate", self.press("ship", "gear")[0]["error"])
        self.state.simulate = False
        self.state.honker = None
        self.assertEqual(self.press("ship", "gear")[1], 409)
        self.assertEqual(self.h.ui.events, [])   # nothing pressed by any refusal
        self.state.honker = self.h
        self.ship(F(26))   # the SRV: its own set, bound in the SRV line
        out, status = self.press("srv", "da")
        self.assertEqual((status, self.h.ui.events), (200, [("KEY_D", 1), ("KEY_D", 0)]))

    def test_fixed_keys(self):
        """The author's (2026-10-25): Hide UI, Screenshot and HighRes in every set press the game's own keys, which no
        .binds file holds; a plain press (no state); removable in the editor like any button."""
        self.press("ship", "shot")
        self.assertEqual(self.h.ui.events, [("KEY_F10", 1), ("KEY_F10", 0)])   # in the ship too
        self.ship(0, flags2=F(rail.F2_ON_FOOT))
        r = self.state.rail_info(full=True)
        b = {x["id"]: x for x in r["buttons"]}
        self.assertEqual((r["context"], b["shot"]["bound"], b["hires"]["short"], b["hideui"]["reported"]), ("foot", True, "HiRes", False))
        self.assertEqual([x["id"] for x in r["buttons"] if x["press"]], ["hideui", "shot", "hires"])
        self.assertIn("Left Ctrl + Left Alt + G", b["hideui"]["keys"])
        self.assertEqual({c["id"]: c["action"] for c in r["edit"]["foot"]["catalogue"]}["hires"], "Left Alt + F10")
        for id_, keys in (("shot", [("KEY_F10", 1), ("KEY_F10", 0)]),
                          ("hires", [("KEY_LEFTALT", 1), ("KEY_F10", 1), ("KEY_F10", 0), ("KEY_LEFTALT", 0)]),
                          ("hideui", [("KEY_LEFTCTRL", 1), ("KEY_LEFTALT", 1), ("KEY_G", 1), ("KEY_G", 0), ("KEY_LEFTALT", 0), ("KEY_LEFTCTRL", 0)])):
            self.h.ui.events.clear()
            out, status = self.press("foot", id_)
            self.assertEqual((status, self.h.ui.events), (200, keys), id_)
        self.assertEqual(self.state.rail_save("foot", [{"id": "torch"}, {"id": "shot"}])[1], 200)
        self.assertEqual([x["id"] for x in self.state.rail_info()["buttons"]], ["torch", "shot"])
        self.assertEqual(self.press("foot", "hires")[1], 404)   # taken off the rail: not pressed

    def test_edit_sets(self):
        out, status = self.state.rail_save("ship", [{"id": "scoop", "label": "Scoop!"}, {"id": "gear"}])
        self.assertEqual((status, [b["label"] for b in self.state.rail_info()["buttons"]]), (200, ["Scoop!", "Landing gear"]))
        self.assertEqual([b["short"] for b in self.state.rail_info()["buttons"]], ["Scoop!", "Gear"])   # a chosen name stays
        self.assertEqual(self.state.rail_save("ship", [{"id": "head"}])[1], 400)
        self.assertEqual(self.state.rail_save("moon", [])[1], 400)
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)   # a journal re-read keeps your sets (live-only data)
        self.assertEqual(len(self.state.rail_sets()["ship"]), 2)
        self.state.rail_save("ship", reset=True)
        self.assertEqual(len(self.state.rail_sets()["ship"]), 11)

    def test_device_follows_the_game(self):
        self.state.rail_device()
        self.assertIn("rail", self.h.owners)
        self.ship(F(24), live=False)
        self.state.rail_device()
        self.assertNotIn("rail", self.h.owners)

    def test_endpoints(self):
        from aiohttp.test_utils import TestClient, TestServer
        import unittest.mock
        import outrider.auth
        self.state.password = "pw"

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = [(await c.get("/api/rail")).status]
                r = await c.post("/api/rail/press", json={"context": "ship", "id": "scoop"})
                out.append((r.status, (await r.json())["before"]))
                out.append((await c.post("/api/rail/press", json={"context": 1})).status)
                out.append((await c.post("/api/rail/sets", json={"context": "ship", "buttons": [{"id": "x"}]})).status)
                out.append((await c.post("/api/rail/press", json={"context": "ship", "id": "scoop"},
                                         headers={"Origin": "http://evil.example"})).status)
                with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
                    out.append((await c.post("/api/rail/press", json={"context": "ship", "id": "scoop"})).status)
                return out
        self.assertEqual(asyncio.run(go()), [200, (200, "off"), 400, 400, 403, 401])
        self.assertEqual(self.h.ui.events, [("KEY_H", 1), ("KEY_H", 0)])   # only the signed-in, same-site press


if __name__ == "__main__":
    unittest.main()
