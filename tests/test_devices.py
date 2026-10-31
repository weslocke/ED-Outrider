"""Unit tests: Auto honk, the co-pilot button, the surface map, Rhino rigs and mining (fake devices only).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import json
import math
import os
import sys
import time
import unittest
import unittest.mock
import sqlite3

from support import (  # also puts the repository root on sys.path
    RHINO_SESSION, button_fake_evdev, scan, user_docs,
)
import outrider.materials  # noqa: E402
import ed_outrider  # noqa: E402
import outrider.speech  # noqa: E402


class HonkBinding(unittest.TestCase):
    """Auto honk reads Primary Fire's keyboard binding (with modifiers) from the active controls preset."""

    def test_reads_preset(self):
        import tempfile
        import outrider.honk
        self.assertEqual([outrider.honk.elite_key(k) for k in ("Key_K", "Key_Numpad_0", "Key_LeftAlt", "Key_RightControl", "Joy_1")],
                         ["KEY_K", "KEY_KP0", "KEY_LEFTALT", "KEY_RIGHTCTRL", None])
        with tempfile.TemporaryDirectory() as root:
            journals = os.path.join(root, "steamuser", "Saved Games", "Frontier Developments", "Elite Dangerous")
            binds = os.path.join(root, "steamuser", "AppData", "Local", "Frontier Developments", "Elite Dangerous",
                                 "Options", "Bindings")
            os.makedirs(journals)
            os.makedirs(binds)
            with open(os.path.join(binds, "StartPreset.4.start"), "w") as f:
                f.write("My X56\nMy X56\nMy X56\nMy X56")

            def preset(secondary):
                with open(os.path.join(binds, "My X56.4.2.binds"), "w") as f:
                    f.write(f"""<?xml version="1.0" encoding="UTF-8" ?><Root PresetName="My X56"><PrimaryFire>
                        <Primary Device="SaitekX56Joystick" Key="Joy_1" />{secondary}</PrimaryFire></Root>""")
            preset('<Secondary Device="Keyboard" Key="Key_K"><Modifier Device="Keyboard" Key="Key_LeftAlt" />'
                   '<Modifier Device="Keyboard" Key="Key_RightAlt" /></Secondary>')
            keys, what = outrider.honk.primary_fire_binding([journals])
            self.assertEqual(keys, ["KEY_LEFTALT", "KEY_RIGHTALT", "KEY_K"])
            self.assertIn("Left Alt + Right Alt + K", what)
            preset('<Secondary Device="{NoDevice}" Key="" />')
            keys, what = outrider.honk.primary_fire_binding([journals])
            self.assertIsNone(keys)
            self.assertIn("no keyboard binding", what)
        self.assertEqual(outrider.honk.parse_combo("alt+k"), ["KEY_LEFTALT", "KEY_K"])


class HonkReadiness(unittest.TestCase):
    """S69: Settings says up front whether auto honk can work here and how to fix what stops it, only by looking: no
    virtual keyboard is ever created, no device opened, no key pressed."""

    def setUp(self):
        import types
        import outrider.honk
        from support import _fake_evdev
        self.H = outrider.honk

        def never(*a, **k):
            raise AssertionError("a virtual keyboard was created")
        self.evdev = _fake_evdev()
        self.evdev.UInput = never
        self.types = types

    def ready(self, backend="evdev", keys=("KEY_LEFTALT", "KEY_K"), there=True, writable=True, platform="linux", off=None):
        combo = lambda: (list(keys), "Left Alt + K (secondary binding of Primary Fire in My X56)") if keys \
            else (None, "Primary Fire has no keyboard binding in My X56: give it a keyboard key")
        return self.H.readiness(self.evdev if backend == "evdev" else backend, combo, platform=platform,
                                uinput="/dev/uinput", exists=lambda p: there, writable=lambda p: writable, off=off)

    def test_ready(self):
        r = self.ready()
        self.assertTrue(r["ready"])
        self.assertEqual([(c["id"], c["label"], c["ok"]) for c in r["checks"]],
                         [("evdev", "evdev", True), ("uinput", "/dev/uinput", True),
                          ("uinput_writable", "/dev/uinput writable", True), ("binding", "Primary Fire: Left Alt + K", True)])
        self.assertTrue(all(c["fix"] is None and c["commands"] == [] for c in r["checks"]))

    def test_each_problem_with_its_fix(self):
        r = self.ready(backend=None)
        self.assertFalse(r["ready"])
        self.assertIn(".venv/bin/pip install evdev", r["checks"][0]["commands"])
        r = self.ready(there=False)
        self.assertEqual([c["id"] for c in r["checks"]], ["evdev", "uinput", "binding"])   # no writable check without it
        self.assertEqual(r["checks"][1]["commands"][0], "sudo modprobe uinput")
        r = self.ready(writable=False)
        w = r["checks"][2]
        self.assertEqual((r["ready"], w["ok"], w["label"]), (False, False, "/dev/uinput is not writable for you"))
        self.assertIn('TAG+="uaccess"', w["commands"][0])    # the udev rule first, the input group only mentioned
        self.assertIn("input group", w["fix"])
        r = self.ready(keys=())
        self.assertEqual(r["checks"][-1]["label"], "Primary Fire: Primary Fire has no keyboard binding in My X56: give it a keyboard key")
        self.assertIn("give the key in Settings -> Auto honk", r["checks"][-1]["fix"])   # its own field now (2026-10-23)

    def test_windows_and_elsewhere(self):
        def no_look(p):
            raise AssertionError("/dev/uinput looked at on Windows")
        r = self.H.readiness(self.types.SimpleNamespace(), lambda: (["KEY_K"], "K"), platform="win32",
                             exists=no_look, writable=no_look)
        self.assertEqual([(c["id"], c["ok"]) for c in r["checks"]], [("backend", True), ("binding", True)])
        self.assertIn("experimental", r["checks"][0]["label"])
        r = self.ready(platform="darwin")
        self.assertEqual((r["ready"], r["checks"][0]["id"]), (False, "platform"))
        r = self.ready(off="--simulate")
        self.assertEqual((r["ready"], r["checks"][0]["label"]), (False, "the virtual keyboard is off (--simulate)"))

    def test_route_looks_only_and_is_game_pc_only(self):
        """GET /api/autohonk/check on the server: the honker's own backend and binding, its device never opened; on a
        server away from the game PC 409 not_game_pc (as the autohonk POSTs)."""
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        state.honker = self.H.Honker("KEY_LEFTALT+KEY_K", 6.0, [])
        state.honker.evdev = self.evdev

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                out = [await (await c.get("/api/autohonk/check")).json()]
                state.game_pc = False
                r = await c.get("/api/autohonk/check")
                return out + [(r.status, (await r.json()).get("code"))]
        here, server = asyncio.run(go())
        self.assertEqual(server, (409, "not_game_pc"))
        self.assertEqual(here["checks"][-1], {"id": "binding", "ok": True, "label": "Primary Fire: Left Alt + K", "fix": None,
                                              "commands": []})
        self.assertIsNone(state.honker.ui)
        ed_outrider.simulate_keyboard_off(state.honker)
        self.assertEqual(state.autohonk_check()["checks"][0]["label"], "the virtual keyboard is off (--simulate)")


class WindowsKeys(unittest.TestCase):
    """Auto honk, auto-target and the rail on Windows: outrider/winkeys.py stands in for evdev, pressing keys by scan
    code with SendInput. Tests record what would be sent (winkeys.SEND); nothing reaches Windows."""

    def setUp(self):
        import outrider.winkeys as wk
        self.wk, self.sent = wk, []
        self.addCleanup(setattr, wk, "SEND", wk.SEND)
        wk.SEND = self.sent.extend

    def test_every_key_outrider_presses_has_a_scan_code(self):
        import outrider.honk as honk
        import outrider.target as target
        codes = self.wk.ecodes.ecodes
        names = {honk.elite_key("Key_" + k) for k in honk.ELITE_KEYS}
        names |= {f"KEY_KP{d}" for d in range(10)} | {f"KEY_F{n}" for n in range(1, 25)}
        names |= {f"KEY_{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
        names |= {k for k, _ in target.US_KEYMAP.values()}
        self.assertEqual(sorted(n for n in names if n not in codes), [])
        self.assertEqual(len(set(codes.values())), len(codes))   # no two keys share a scan code
        self.assertEqual(codes["KEY_K"], 0x25)
        self.assertEqual(codes["KEY_RIGHTCTRL"], 0xE01D)         # extended
        self.assertEqual(codes["KEY_KPENTER"], 0xE01C)
        self.assertEqual(codes["KEY_ENTER"], 0x1C)               # the main Enter is not

    def test_write_sends_scan_codes(self):
        ui = self.wk.UInput({}, name="test")
        ui.write(self.wk.EV_KEY, 0xE048, 1)   # the up arrow: extended
        ui.write(self.wk.EV_KEY, 0xE048, 2)   # autorepeat: nothing
        ui.write(self.wk.EV_KEY, 0xE048, 0)
        ui.write(0, 0, 0)                     # evdev's SYN: nothing
        ui.syn()
        self.assertEqual(self.sent, [(0x48, True, False), (0x48, True, True)])
        with self.assertRaises(OSError):
            ui.write(self.wk.EV_KEY, None, 1)

    def test_honker_presses_through_winkeys(self):
        import outrider.honk as honk
        with unittest.mock.patch.object(honk.sys, "platform", "win32"):
            self.assertIs(honk.keyboard_backend(), self.wk)
        with unittest.mock.patch.object(honk.sys, "platform", "darwin"):
            self.assertIsNone(honk.keyboard_backend())
        h = honk.Honker("KEY_RIGHTCTRL+KEY_K", hold=0.01)
        h.evdev = self.wk
        self.assertTrue(h.open())
        self.assertEqual(h.press(), "Right Ctrl + K")
        # modifiers first, released in reverse, as a person would
        self.assertEqual(self.sent, [(0x1D, True, False), (0x25, False, False), (0x25, False, True), (0x1D, True, True)])
        self.sent.clear()
        h.tap(["KEY_LEFTSHIFT", "KEY_A"], hold=0)
        self.assertEqual(self.sent, [(0x2A, False, False), (0x1E, False, False), (0x1E, False, True), (0x2A, False, True)])
        h.close()
        self.assertFalse(h.ready)

    def test_clipboard_on_windows(self):
        got = []
        cb = ed_outrider.Clipboard(True, platform="win32", win_set=got.append, which=lambda n: None, env={})
        self.assertEqual(cb.info()["tool"], "Windows")
        self.assertTrue(cb.info()["available"])
        self.assertTrue(cb.copy("Col 285 Sector AB-C d1-2"))
        self.assertEqual(got, ["Col 285 Sector AB-C d1-2"])

        def busy(text):
            raise OSError(5, "the clipboard is in use by another program")
        cb = ed_outrider.Clipboard(True, platform="win32", win_set=busy)
        self.assertFalse(cb.copy("X"))
        self.assertIn("in use", cb.last["error"])
        self.assertFalse(ed_outrider.Clipboard(False, platform="win32", win_set=got.append).copy("Y"))   # [highway] clipboard off
        self.assertEqual(len(got), 1)


class BatchGHonkBackups(unittest.TestCase):
    """Batch G: auto honk's combat-mode and fire-group safety (P7, unit tests only: fake honkers, no device, no
    keys), and verified backups with --restore / --list-backups (P19, temp files only)."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    @staticmethod
    def now_ts():
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def live(self, **kw):
        return dict({"live": True, "ts": self.now_ts(), "flags": 1 << 4 | 1 << 27, "gui_focus": 0, "fire_group": 0}, **kw)

    # ---- P7 ----
    def test_read_status_keeps_the_fire_group(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Status.json"), "w") as f:
                json.dump({"timestamp": self.now_ts(), "Flags": 1 << 27, "Flags2": 0, "FireGroup": 2, "GuiFocus": 0,
                           "Fuel": {"FuelMain": 8.0, "FuelReservoir": 0.5}}, f)
            self.j.read_status(d)
        self.assertEqual((self.j.status_json["fire_group"], ed_outrider.fire_group_letter(2)), (2, "C"))
        self.assertIsNone(ed_outrider.fire_group_letter(None))
        self.assertIsNone(ed_outrider.fire_group_letter(True))

    def test_honk_decision_combat_mode_and_groups(self):
        d, t = ed_outrider.honk_decision, time.time()
        self.assertEqual(d(self.live(), t), ("press", None))
        # combat mode: Primary Fire would fire the weapons
        self.assertEqual(d(self.live(flags=1 << 4), t), ("wait", "the HUD is in combat mode"))
        self.assertEqual(d(self.live(flags=1 << 4 | 1 << 30), t), ("wait", "still in the jump"))
        self.assertEqual(d(self.live(flags=1 << 4, gui_focus=6), t), ("wait", "the galaxy map is open"))
        self.assertEqual(d(self.live(flags=None), t), ("press", None))           # no flags at all: as before
        groups = {"good": ["A"], "bad": ["C"]}
        self.assertEqual(d(self.live(fire_group=2), t, groups),
                         ("wait", "fire group C selected; honks missed there before (worked on A)"))
        self.assertEqual(d(self.live(fire_group=2), t, {"good": [], "bad": ["C"]}),
                         ("wait", "fire group C selected; honks missed there before"))
        self.assertEqual(d(self.live(fire_group=1), t, groups), ("press", None))   # unknown group: still pressed
        self.assertEqual(d(self.live(fire_group=0), t, groups), ("press", None))
        self.assertEqual(d(self.live(fire_group=2), t), ("press", None))            # nothing learned for this ship
        # a stale reading presses, whatever it says; one saying the game is not live waits (review 2026-10-11)
        self.assertEqual(d(self.live(fire_group=2, flags=1 << 4), t + 120, groups), ("press", None))
        self.assertEqual(d(dict(self.live(fire_group=2), live=False), t, groups), ("wait", "the game is not live"))

    def test_honk_learn(self):
        learn = ed_outrider.honk_learn
        self.assertEqual(learn(None, "A", True), {"good": ["A"], "bad": []})
        # R24: one miss is only counted (an alt-tab sends the key to another window, and the game cannot tell);
        # the second in a row makes the group bad
        self.assertEqual(learn({"good": ["A"], "bad": []}, "C", False), {"good": ["A"], "bad": [], "miss": {"C": 1}})
        self.assertEqual(learn({"good": ["A"], "bad": [], "miss": {"C": 1}}, "C", False), {"good": ["A"], "bad": ["C"]})
        self.assertEqual(learn(learn(None, "A", False), "A", False), {"good": [], "bad": ["A"]})   # no record yet: the same
        # a success anywhere between ends every run of misses
        self.assertEqual(learn({"good": [], "bad": [], "miss": {"A": 1, "C": 1}}, "B", True), {"good": ["B"], "bad": []})
        self.assertEqual(learn(learn(learn(None, "A", False), "B", True), "A", False),
                         {"good": ["B"], "bad": [], "miss": {"A": 1}})
        # misses in two groups count apart
        self.assertEqual(learn(learn(None, "A", False), "C", False), {"good": [], "bad": [], "miss": {"A": 1, "C": 1}})
        self.assertEqual(learn({"good": [], "bad": ["C"]}, "C", False), {"good": [], "bad": ["C"]})   # already bad
        self.assertEqual(learn({"good": ["A"], "bad": []}, "A", False), {"good": ["A"], "bad": []})   # worked there before
        self.assertEqual(learn({"good": ["A"], "bad": ["C"]}, "C", True), {"good": ["A", "C"], "bad": []})   # a success clears it
        self.assertEqual(learn({"good": ["A"], "bad": []}, None, False), {"good": ["A"], "bad": []})

    def honk(self, id64, answers, status, ship_id=7, during=None):
        """One auto-honk arrival with a fake honker (no device, no keys): the presses, and the honk moment."""
        import asyncio
        j, presses, now_ts = self.j, [], self.now_ts

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                presses.append(id64)
                if callable(during):
                    during()
                elif during:
                    j.status_json = dict(j.status_json, **during)
                if answers:
                    j.last_honk = {"id64": id64, "ts": now_ts(), "bodies": 5, "progress": 0.3}
                return True
        self.j.ship = {"name": "Ship", "type": "dolphin", "ship_id": ship_id}
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.state.honk_confirm = 0.2
        self.j.handle({"event": "FSDJump", "timestamp": now_ts(), "StarSystem": f"S{id64}", "SystemAddress": id64,
                       "StarPos": [id64, 0, 0]})
        self.j.ship = {"name": "Ship", "type": "dolphin", "ship_id": ship_id}
        self.j.status_json = status

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.6)
        asyncio.run(go())
        honks = [m for m in self.state.moments_summary() if m["kind"] == "honk" and m["system"] == f"S{id64}"]
        return presses, honks[-1] if honks else None

    def test_fire_groups_learned_from_auto_honk_presses(self):
        # a confirmed press in group A: good
        presses, m = self.honk(101, True, self.live(fire_group=0))
        self.assertEqual((presses, m["ok"]), ([101], True))
        self.assertEqual(self.state.honk_groups(), {"good": ["A"], "bad": []})
        # a miss in group C with the cockpit focused and analysis mode on: bad, and the message names the group
        presses, m = self.honk(102, False, self.live(fire_group=2))
        self.assertEqual(presses, [102])
        self.assertEqual(m["why"], "no discovery scan followed with fire group C selected: is the D-Scanner on primary fire there?")
        self.assertEqual(self.state.honk_groups(), {"good": ["A"], "bad": [], "miss": {"C": 1}})   # R24: once is not enough
        presses, m = self.honk(1021, False, self.live(fire_group=2))   # the second in a row
        self.assertEqual(presses, [1021])
        self.assertEqual(self.state.honk_groups(), {"good": ["A"], "bad": ["C"]})
        self.state.honker.combo = lambda: (["KEY_K"], "K")
        self.assertEqual(self.state.autohonk_info()["groups"], {"good": ["A"], "bad": ["C"]})
        # a miss explained by a screen opening during the press is not held against the group
        presses, m = self.honk(103, False, self.live(fire_group=1), during={"gui_focus": 6})
        self.assertEqual(m["why"], "no discovery scan followed with fire group B selected: the galaxy map is open")
        self.assertEqual(self.state.honk_groups(), {"good": ["A"], "bad": ["C"]})
        # a miss with no fresh status names no group and learns nothing
        stale = self.live(fire_group=1, ts="2020-01-01T00:00:00Z")
        presses, m = self.honk(104, False, stale)
        self.assertEqual(m["why"], "no discovery scan followed: is the D-Scanner on primary fire?")
        self.assertEqual(self.state.honk_groups(), {"good": ["A"], "bad": ["C"]})
        # another ship has its own record: group C is not held against it
        presses, m = self.honk(105, True, self.live(fire_group=2), ship_id=8)
        self.assertEqual(presses, [105])
        self.assertEqual(self.state.honk_groups(8), {"good": ["C"], "bad": []})
        self.assertEqual(self.state.honk_groups(7), {"good": ["A"], "bad": ["C"]})
        # back in ship 7 with C selected: it waits, and a switch to A releases the press
        import asyncio
        self.j.ship = {"name": "Ship", "type": "dolphin", "ship_id": 7}
        presses = []

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                presses.append(1)
                return True
        self.state.honker = FakeHonker()
        self.j.handle({"event": "FSDJump", "timestamp": self.now_ts(), "StarSystem": "S106", "SystemAddress": 106,
                       "StarPos": [106, 0, 0]})
        self.j.ship = {"name": "Ship", "type": "dolphin", "ship_id": 7}
        self.j.status_json = self.live(fire_group=2)

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.5)
            waiting = (list(presses), self.state.honker.status)
            self.j.status_json = self.live(fire_group=0)
            await asyncio.sleep(0.8)
            return waiting
        waiting = asyncio.run(go())
        self.assertEqual(waiting, ([], "waiting: fire group C selected; honks missed there before (worked on A)"))
        self.assertEqual(presses, [1])

    def test_own_jump_cuts_the_honk_short(self):   # F42: not held against the fire group, and no failure reported
        jumping = self.live(fire_group=2, flags=self.live()["flags"] | 1 << 30)
        presses, m = self.honk(121, False, self.live(fire_group=2), during={"flags": jumping["flags"]})
        self.assertEqual((presses, m), ([121], None))
        presses, m = self.honk(122, False, self.live(fire_group=2), during={"flags": jumping["flags"]})
        self.assertEqual((presses, m), ([122], None))
        self.assertIsNone(self.state.honk_groups())   # two such presses: group C is not marked bad
        # a hyperspace StartJump after the arrival (the FSD charging for the next jump) says the same
        later = lambda: setattr(self.j, "last_start_jump", "9999-01-01T00:00:00Z")
        presses, m = self.honk(123, False, self.live(fire_group=2), during=later)
        self.assertEqual((presses, m), ([123], None))
        self.assertIsNone(self.state.honk_groups())
        # a plain miss still counts
        self.j.last_start_jump = None
        presses, m = self.honk(124, False, self.live(fire_group=2))
        self.assertFalse(m["ok"])
        self.assertEqual(self.state.honk_groups(), {"good": [], "bad": [], "miss": {"C": 1}})

    def test_a_failed_tick_hides_no_honk(self):
        """Review 8: last_honk is the reader's, rolled back with a failed tick; the honk task watching it saw no scan,
        said the honk failed and marked the fire group. The scan really read stays seen (honk_seen). The tick runs on
        the event loop, as the real one (the fake press is on a worker thread)."""
        import asyncio
        loop = {}

        def failed_tick():
            cp = self.j.checkpoint()
            self.j.handle({"event": "FSSDiscoveryScan", "timestamp": self.now_ts(), "Progress": 0.3, "BodyCount": 5,
                           "NonBodyCount": 0, "SystemName": "S131", "SystemAddress": 131})
            self.j.restore(cp)
        start = self.state.maybe_honk

        def maybe_honk():
            loop["it"] = asyncio.get_running_loop()
            return start()
        self.state.maybe_honk = maybe_honk
        presses, m = self.honk(131, False, self.live(fire_group=2), during=lambda: loop["it"].call_soon_threadsafe(failed_tick))
        self.assertIsNone(self.j.last_honk)   # rolled back, as the reader's state should be
        self.assertEqual((presses, m["ok"]), ([131], True))
        self.assertEqual(self.state.honk_groups(), {"good": ["C"], "bad": []})

    def test_honk_checks_again_under_the_lock(self):   # CX-F3: what changed while auto-target held the keyboard
        import asyncio
        import outrider.honk
        calls, presses, j, live = [], [], self.j, self.live

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                calls.append(1)
                if len(calls) == 1:   # auto-target opened the map while the honk waited for the keyboard
                    j.status_json = live(gui_focus=6)
                why = check() if check else None
                if why:
                    raise outrider.honk.NotNow(why)
                presses.append(1)
                return True
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.state.honk_confirm = 0.2
        self.j.handle({"event": "FSDJump", "timestamp": self.now_ts(), "StarSystem": "S131", "SystemAddress": 131,
                       "StarPos": [1, 0, 0]})
        self.j.status_json = self.live()

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.5)
            waiting = (len(calls), list(presses), self.state.honker.status)
            self.j.status_json = self.live()   # the map closed again
            await asyncio.sleep(0.8)
            return waiting
        self.assertEqual(asyncio.run(go()), (1, [], "waiting: the galaxy map is open"))
        self.assertEqual((len(calls), presses), (2, [1]))

    def test_switch_off_ends_the_hold_with_auto_target_on(self):   # CX-F1, F12: the device stays open for auto-target
        import asyncio
        ended = []

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                start = time.time()
                cut = cancel.wait(3) if cancel is not None else time.sleep(1.5)   # no token: the full hold
                ended.append(time.time() - start)
                return None if cut else True

            def open(self, owner="honk"):
                return True

            def close(self, owner="honk"):
                pass   # auto-target still owns the virtual keyboard: closing it is not what ends the hold
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.j.handle({"event": "FSDJump", "timestamp": self.now_ts(), "StarSystem": "S141", "SystemAddress": 141,
                       "StarPos": [1, 0, 0]})
        self.j.status_json = self.live()

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.3)
            self.state.set_autohonk(False)
            await asyncio.sleep(0.4)
        asyncio.run(go())
        self.assertEqual(len(ended), 1)
        self.assertLess(ended[0], 1)
        self.assertEqual([m for m in self.state.moments_summary() if m["kind"] == "honk"], [])

    def test_combat_mode_waits_then_gives_up(self):
        import asyncio
        presses = []

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                presses.append(1)
                return True
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.j.handle({"event": "FSDJump", "timestamp": self.now_ts(), "StarSystem": "S111", "SystemAddress": 111,
                       "StarPos": [1, 0, 0]})
        self.j.status_json = self.live(flags=1 << 4)

        async def go():
            with unittest.mock.patch.object(ed_outrider, "AUTOHONK_WAIT_MAX", 0.4):
                self.state.maybe_honk()
                await asyncio.sleep(0.2)
                status = self.state.honker.status
                await asyncio.sleep(0.6)
                return status
        self.assertEqual(asyncio.run(go()), "waiting: the HUD is in combat mode")
        self.assertEqual(presses, [])
        m = [m for m in self.state.moments_summary() if m["kind"] == "honk"][-1]
        self.assertEqual((m["ok"], m["why"]), (False, "gave up waiting: the HUD is in combat mode"))
        self.assertIsNone(self.state.honk_groups())   # never pressed: nothing learned

    def test_forget_fire_groups(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        self.j.ship = {"name": "Ship", "type": "dolphin", "ship_id": 7}
        self.state.note_honk_group(7, "A", True)
        self.state.note_honk_group(7, "C", False)
        self.state.note_honk_group(8, "B", True)

        async def go():   # the test client only: no auto honk, no device (forget touches the meta record alone)
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.post("/api/autohonk/forget")
                return r.status, await r.json()
        status, body = asyncio.run(go())
        self.assertEqual((status, body["groups"]), (200, None))
        self.assertIsNone(self.state.honk_groups(7))
        self.assertEqual(self.state.honk_groups(8), {"good": ["B"], "bad": []})   # other ships keep theirs

    def test_page_names_the_group(self):
        with open(os.path.join(os.path.dirname(ed_outrider.__file__), "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("Is the discovery scanner on primary fire in fire group ${honkGroup(m.why)}?", js)
        self.assertIn("api/autohonk/forget", js)

    # ---- P19 ----
    def make_db(self, path, rows=50):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        con.execute("CREATE INDEX t_v ON t (v)")
        con.executemany("INSERT INTO t (v) VALUES (?)", [(f"row {i} " + "x" * 200,) for i in range(rows)])
        con.commit()
        con.close()

    def backup_env(self, d):
        live, out = os.path.join(d, "live"), os.path.join(d, "backups")
        os.makedirs(live); os.makedirs(out)
        dbp = os.path.join(d, "x.sqlite")
        self.make_db(dbp)
        self.state.db_path = dbp
        self.state.speech_path = self.state.config_path = None
        return live, out, dbp

    def test_backup_is_verified(self):
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            live, out, dbp = self.backup_env(d)
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]):
                res = self.state.make_backup()
            self.assertTrue(res["verified"])
            self.assertIsNone(ed_outrider.check_zip(res["path"]))
            with zipfile.ZipFile(res["path"]) as z:
                self.assertIsNone(z.testzip())

    def test_corrupt_copy_fails_and_keeps_older_zips(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            live, out, dbp = self.backup_env(d)
            older = []
            for i in range(1, 3):
                older.append(f"outrider-x-2020010{i}-000000Z.zip")
                with open(os.path.join(out, older[-1]), "w") as f:
                    f.write("old")
            real = ed_outrider.copy_database

            def corrupting(src, dst, **kw):   # the copy goes through, then its pages are overwritten
                real(src, dst, **kw)
                path = dst.execute("PRAGMA database_list").fetchone()[2]
                size = os.path.getsize(path)
                with open(path, "r+b") as f:
                    f.seek(24)
                    f.write(b"\x7f\x7f\x7f\x7f")   # a new change counter: the connection re-reads the pages
                    f.seek(size // 4096 // 2 * 4096 if size > 8192 else 4096)
                    f.write(b"\xde\xad" * 2048)
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 1), \
                    unittest.mock.patch.object(ed_outrider, "copy_database", corrupting):
                with self.assertRaises(Exception) as e:
                    self.state.make_backup()
            self.assertRegex(str(e.exception), "check|malformed|corrupt")
            self.assertEqual(sorted(os.listdir(out)), older)   # nothing rotated, no bad zip, no temp copy left

    def test_bad_zip_is_deleted_and_nothing_rotates(self):
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            live, out, dbp = self.backup_env(d)
            with open(os.path.join(out, "outrider-x-20200101-000000Z.zip"), "w") as f:
                f.write("old")
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 1), \
                    unittest.mock.patch.object(zipfile.ZipFile, "testzip", return_value="x.sqlite"):
                with self.assertRaisesRegex(RuntimeError, "the zip failed its check: x.sqlite is damaged"):
                    self.state.make_backup()
            self.assertEqual(os.listdir(out), ["outrider-x-20200101-000000Z.zip"])

    def make_zip(self, d, name="outrider-x-20260101-000000Z.zip", rows=10, defaults=None):
        import zipfile
        src = os.path.join(d, f"src-{name}.sqlite")
        self.make_db(src, rows)
        path = os.path.join(d, "backups", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(src, "x.sqlite")
            if defaults is not None:
                z.writestr("browser_defaults.json", json.dumps(defaults))
            z.writestr("speech.json", "{}")
        return path

    def test_restore(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            self.make_db(dbp, 3)
            with open(dbp + "-journal", "w") as f:
                f.write("left over")
            defaults = ed_outrider.browser_defaults_path(dbp)
            ed_outrider.write_browser_defaults(defaults, {"version": 1, "settings": {"sound": False}})
            z = self.make_zip(d, rows=10, defaults={"version": 1, "settings": {"sound": True}})
            lines = ed_outrider.restore_backup(z, dbp, "127.0.0.1", 0, now=0)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(0))
            con = sqlite3.connect(dbp)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 10)
            con.close()
            aside = f"{dbp}.pre-restore-{stamp}"
            self.assertFalse(os.path.exists(dbp + "-journal"))
            self.assertTrue(os.path.exists(aside + "-journal"))   # went with the old file (before SQLite opens it)
            con = sqlite3.connect(aside)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 3)   # the old one kept
            con.close()
            with open(defaults) as f:
                self.assertEqual(json.load(f)["settings"], {"sound": True})
            with open(f"{defaults}.pre-restore-{stamp}") as f:
                self.assertEqual(json.load(f)["settings"], {"sound": False})
            self.assertTrue(lines[0].startswith(f"restored {dbp} from {z}"))
            self.assertIn("also in the zip, not restored: speech.json", lines[-1])
            self.assertFalse([f for f in os.listdir(d) if f.endswith(".part")])

    def test_restore_sets_a_stray_journal_aside(self):
        """The database file gone (deleted by hand after a crash), its rollback journal left: SQLite would roll that
        journal into the restored file. It is set aside too (review 2026-10-11)."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            with open(dbp + "-journal", "w") as f:
                f.write("left over")
            z = self.make_zip(d, rows=10)
            lines = ed_outrider.restore_backup(z, dbp, "127.0.0.1", 0, now=0)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(0))
            self.assertFalse(os.path.exists(dbp + "-journal"))
            self.assertTrue(os.path.exists(f"{dbp}.pre-restore-{stamp}-journal"))
            self.assertTrue(any("stray x.sqlite-journal" in line for line in lines), lines)

    def test_restore_a_database_not_named_sqlite(self):   # F33
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "mydata.db")
            self.make_db(dbp, 3)
            src = os.path.join(d, "src.db")
            self.make_db(src, 10)
            z = os.path.join(d, "mydata-20260101-000000Z.zip")
            with zipfile.ZipFile(z, "w") as zf:
                zf.write(src, "mydata.db")   # as make_backup names the member: after the database's own file
            lines = ed_outrider.restore_backup(z, dbp, "127.0.0.1", 0, now=0)
            self.assertIn("(mydata.db)", lines[0])
            con = sqlite3.connect(dbp)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 10)
            con.close()

    def test_restore_when_the_defaults_cannot_be_written(self):   # F34
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            self.make_db(dbp, 3)
            defaults = ed_outrider.browser_defaults_path(dbp)
            ed_outrider.write_browser_defaults(defaults, {"version": 1, "settings": {"sound": False}})
            os.makedirs(defaults + ".part")   # the write fails (as a full disk would)
            z = self.make_zip(d, rows=10, defaults={"version": 1, "settings": {"sound": True}})
            lines = ed_outrider.restore_backup(z, dbp, "127.0.0.1", 0, now=0)
            self.assertTrue(lines[0].startswith(f"restored {dbp}"))
            self.assertTrue(any("could not be written" in x and "the old one stays" in x for x in lines), lines)
            with open(defaults) as f:
                self.assertEqual(json.load(f)["settings"], {"sound": False})   # still there, unchanged

    def test_restore_refuses_defaults_that_are_not_settings(self):   # Codex F9
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            self.make_db(dbp, 3)
            for bad in ([], 42, "x"):   # (make_zip writes no file for None: JSON null is in the read check below)
                z = self.make_zip(d, name=f"outrider-x-{type(bad).__name__}.zip", rows=10, defaults=bad)
                with self.assertRaisesRegex(RuntimeError, "is not a settings document"):
                    ed_outrider.restore_backup(z, dbp, "127.0.0.1", 0, now=0)
            con = sqlite3.connect(dbp)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 3)   # nothing replaced
            con.close()
            for bad in (None, [], 42, "x"):   # and in place: the page still loads, with no defaults
                with open(ed_outrider.browser_defaults_path(dbp), "w") as f:
                    json.dump(bad, f)
                self.assertIsNone(ed_outrider.read_browser_defaults(ed_outrider.browser_defaults_path(dbp)))

    def test_restore_refuses_while_the_port_is_bound(self):
        import socket, tempfile
        with tempfile.TemporaryDirectory() as d, socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            dbp = os.path.join(d, "x.sqlite")
            self.make_db(dbp, 3)
            z = self.make_zip(d)
            with self.assertRaisesRegex(RuntimeError, f"port {port} is in use"):
                ed_outrider.restore_backup(z, dbp, "127.0.0.1", port)
            self.assertEqual(sorted(os.listdir(d)), ["backups", "src-outrider-x-20260101-000000Z.zip.sqlite", "x.sqlite"])

    def test_restore_refuses_a_bad_zip_or_database(self):
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            self.make_db(dbp, 3)
            os.makedirs(os.path.join(d, "backups"))
            junk = os.path.join(d, "backups", "outrider-x-20260101-000000Z.zip")
            with open(junk, "w") as f:
                f.write("not a zip")
            with self.assertRaisesRegex(RuntimeError, "failed its check"):
                ed_outrider.restore_backup(junk, dbp, "127.0.0.1", 0)
            with zipfile.ZipFile(junk, "w") as z:
                z.writestr("x.sqlite", b"SQLite format 3\x00" + b"\x00" * 200)
            with self.assertRaisesRegex(RuntimeError, "the database in .* failed its check"):
                ed_outrider.restore_backup(junk, dbp, "127.0.0.1", 0)
            self.assertEqual(sorted(os.listdir(d)), ["backups", "x.sqlite"])   # untouched, no temp file left

    def test_list_backups_and_cli(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            z1 = self.make_zip(d, "outrider-x-20260101-000000Z.zip", rows=4)
            self.make_zip(d, "outrider-x-20260102-000000Z.zip", rows=6)
            self.make_zip(d, "outrider-other-20260103-000000Z.zip")
            out = os.path.join(d, "backups")
            lines = ed_outrider.list_backups(out, os.path.join(d, "x.sqlite"))
            self.assertEqual([l.split()[0] for l in lines], ["outrider-x-20260101-000000Z.zip", "outrider-x-20260102-000000Z.zip"])
            self.assertIn(" MB ", lines[0])
            self.assertEqual(ed_outrider.list_backups(os.path.join(d, "none"), "x.sqlite")[0][:11], "no backups:")
            cfg = os.path.join(d, "t.toml")
            with open(cfg, "w") as f:
                f.write(f'[server]\nbackup_dir = "{out}"\n')
            dbp = os.path.join(d, "x.sqlite")
            got = self.cli(["--config", cfg, "--db", dbp, "--list-backups"])
            self.assertEqual(len(got.stdout.strip().splitlines()), 2)
            got = self.cli(["--config", cfg, "--db", dbp, "--restore"])   # no zip named: the newest of this database's
            self.assertEqual(got.returncode, 0, got.stderr)
            con = sqlite3.connect(dbp)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 6)
            con.close()
            got = self.cli(["--config", cfg, "--db", dbp, "--restore", os.path.basename(z1)])   # a bare name, found in backup_dir
            self.assertEqual(got.returncode, 0, got.stderr)
            con = sqlite3.connect(dbp)
            self.assertEqual(con.execute("SELECT count(*) FROM t").fetchone()[0], 4)
            con.close()
            self.assertEqual(len([f for f in os.listdir(d) if ".pre-restore-" in f]), 1)   # the first had no database to move
            got = self.cli(["--config", cfg, "--db", dbp, "--restore", "nope.zip"])
            self.assertEqual(got.returncode, 1)
            self.assertIn("not restored:", got.stderr)

    @staticmethod
    def cli(args):
        """ed_outrider.py in a subprocess on a free scratch port: these flags exit before any server starts."""
        import socket, subprocess
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        return subprocess.run([sys.executable, ed_outrider.__file__, "--port", str(port), "--host", "127.0.0.1"] + args,
                              capture_output=True, text=True, timeout=60)

    def test_help_and_readme_name_the_flags(self):
        out = self.cli(["--help"]).stdout
        self.assertIn("--restore", out)
        self.assertIn("--list-backups", out)
        readme = user_docs()
        self.assertIn("--restore", readme)
        self.assertIn("--list-backups", readme)


class BatchBVoiceControl(unittest.TestCase):
    """Batch B: the hush, the co-pilot channel and button (never a real input device: the device layer is a
    stand-in), banned lines (temp files only, never a speech_banned.json in the repo)."""

    def setUp(self):
        import tempfile
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.addCleanup(self.db.close)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def client(self, go):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return await go(c)
        return asyncio.run(run())

    def speech_file(self, lines=None):
        path = os.path.join(self.tmp, "speech.json")
        doc = {"styles": {"business": "Business", "sarcastic": "Sarcastic"},
               "lines": lines or {"hull": {"business": ["Hull {pct}.", "Hull at {pct} percent.", "Hull damage."],
                                           "sarcastic": ["Ouch, {pct}."]},
                                  "heat": {"business": ["Heat damage.", "Hot."]}}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        return path

    # ---- the gesture classifier: a pure function ----
    def test_gestures(self):
        import outrider.button
        c = lambda ev, end=None: outrider.button.classify(ev, 600, 350, end)
        self.assertEqual(c([(0, 1), (100, 0)]), ["status"])                                  # a tap
        self.assertEqual(c([(0, 1), (100, 0)], end=400), [])                                 # still waiting for a second
        self.assertEqual(c([(0, 1), (100, 0)], end=451), ["status"])
        self.assertEqual(c([(0, 1), (100, 0), (300, 1), (380, 0)]), ["again"])               # press 200 ms after the release
        self.assertEqual(c([(0, 1), (100, 0), (500, 1), (580, 0)]), ["status", "status"])    # too far apart: two taps
        self.assertEqual(c([(0, 1), (650, 0)]), ["hush"])                                    # a hold: on the release
        self.assertEqual(c([(0, 1), (599, 0)]), ["status"])                                  # just short of a hold
        self.assertEqual(c([(0, 1), (200, 2), (400, 2), (700, 0)]), ["hush"])                # autorepeat ignored
        self.assertEqual(c([(0, 1), (100, 0), (200, 1), (900, 0)]), ["hush"])                # a hold swallows the tap before
        self.assertEqual(c([(0, 0), (50, 2)]), [])                                           # a release with no press
        self.assertEqual(c([(0, 1), (100, 0), (300, 1), (380, 0), (500, 1), (560, 0)]), ["again", "status"])
        g = outrider.button.Gestures(600, 350)
        self.assertEqual(g.feed(0, 1) + g.feed(50, 0), [])
        self.assertEqual(g.due(300), [])
        self.assertEqual(g.due(401), ["status"])
        self.assertEqual(g.due(900), [])                                                     # said once

    fake_evdev = button_fake_evdev

    def test_button_code_and_find_device(self):
        import outrider.button
        ev, Dev = self.fake_evdev([])
        self.assertEqual(outrider.button.button_code(ev, "btn_trigger_happy5"), 300)
        self.assertEqual(outrider.button.button_code(ev, "183"), 183)
        self.assertEqual(outrider.button.button_code(ev, 300), 300)
        self.assertIsNone(outrider.button.button_code(ev, "BTN_NOPE"))
        self.assertIsNone(outrider.button.button_code(ev, ""))
        dev, why = outrider.button.find_device(ev, "x-56", 300)
        self.assertEqual((dev.path, why), ("/dev/input/event5", None))      # the throttle: the stick has no button 300
        self.assertTrue(all(d.closed for d in Dev.opened if d is not dev))   # the others are let go
        dev, why = outrider.button.find_device(ev, "x-56", 999)
        self.assertEqual(dev.path, "/dev/input/event4")                     # none has it: the first, and S7-S5 says so
        self.assertIn("which that device does not report", why)
        self.assertEqual(outrider.button.find_device(ev, "x-56")[0].path, "/dev/input/event4")        # no code: the first
        dev, why = outrider.button.find_device(ev, "Rhino")
        self.assertIsNone(dev)
        self.assertIn("1 could not be opened", why)                           # the unreadable one is counted
        self.assertEqual(outrider.button.find_device(ev, "/dev/input/event5")[0].path, "/dev/input/event5")
        self.assertIn("Permission denied", outrider.button.find_device(ev, "/dev/input/event9")[1])
        self.assertIsNone(outrider.button.find_device(ev, "")[0])

    def test_button_watch(self):
        import asyncio
        import outrider.button
        # a tap, then a double tap, then a hold, then the device goes away
        ev, Dev = self.fake_evdev([(0, 1), (0.02, 0), (0.25, 1), (0.02, 0), (0.03, 1), (0.02, 0),
                                   (0.25, 1), (0.2, 0), (0.05, 2)])
        got, presses = [], []

        async def go():
            w = outrider.button.ButtonWatch("X-56", "BTN_TRIGGER_HAPPY5", got.append, hold_ms=150, double_ms=100, evdev=ev,
                                            on_press=lambda: presses.append(len(got)))
            seen = set()
            with unittest.mock.patch.object(outrider.button, "RETRY", 0.05):
                t = asyncio.ensure_future(w.run())
                for _ in range(130):   # every status it shows on the way
                    seen.add(w.status)
                    await asyncio.sleep(0.01)
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
            return seen
        seen = asyncio.run(go())
        self.assertIn("listening to Saitek X-56 Throttle for BTN_TRIGGER_HAPPY5", seen)
        self.assertEqual(got[:3], ["status", "again", "hush"])
        self.assertTrue(set(got) <= {"status", "again", "hush"})
        # on_press: every press as it happens, before its gesture is decided (the autorepeat is not a press)
        self.assertEqual(presses[:4], [0, 1, 1, 2])
        self.assertTrue(any("No such device; looking again" in x for x in seen), seen)   # the unplug, then a retry
        self.assertTrue(all(d.closed for d in Dev.opened))        # every device it opened was closed again
        self.assertGreater(len([d for d in Dev.opened if d.path.endswith("5")]), 1)   # and it looked again

        # Review 2026-10-08 #19: a second press that comes after the double-tap window but before the settle timer
        # fires (kernel times 110 ms apart, read in one go): the lone tap is handed over BEFORE the press is
        # reported, so the press can cancel the targeting that tap starts instead of arriving first and missing it.
        ev2, Dev2 = self.fake_evdev([])

        class Stamped:
            def __init__(self, value, secs):
                self.type, self.code, self.value, self.secs = 1, 300, value, secs

            def timestamp(self):
                return self.secs

        async def burst(dev):
            for value, secs in ((1, 1000.0), (0, 1000.02), (1, 1000.13), (0, 1000.15)):
                yield Stamped(value, secs)
            raise OSError(19, "No such device")
        Dev2.async_read_loop = burst
        got2, presses2 = [], []

        async def go2():
            w = outrider.button.ButtonWatch("X-56", "BTN_TRIGGER_HAPPY5", got2.append, hold_ms=600, double_ms=100,
                                            evdev=ev2, on_press=lambda: presses2.append(list(got2)))
            with unittest.mock.patch.object(outrider.button, "RETRY", 5):
                t = asyncio.ensure_future(w.run())
                await asyncio.sleep(0.05)
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
        asyncio.run(go2())
        self.assertEqual(presses2, [[], ["status"]])   # the first tap was settled when the second press came

        async def bad(button):
            w = outrider.button.ButtonWatch("X-56", button, got.append, evdev=ev)
            await w.run()   # returns at once: nothing to listen for
            return w.status
        self.assertIn("is not a button name or number", asyncio.run(bad("BTN_NOPE")))

    def stamped_evdev(self, script):
        """Like fake_evdev, but each event carries a kernel timestamp: `script` is a list of (seconds the loop
        waits before handing it over, the event's own time in seconds, value), then an unplug."""
        import types
        base = time.time()

        class Ev:
            def __init__(self, value, t):
                self.type, self.code, self.value, self.t = 1, 300, value, t

            def timestamp(self):
                return base + self.t

        class Dev:
            opened = []

            def __init__(self, path):
                self.path, self.name, self.closed = path, "Saitek X-56 Throttle", False
                Dev.opened.append(self)

            def close(self):
                self.closed = True

            async def async_read_loop(self):
                import asyncio
                for wait, t, value in script:
                    await asyncio.sleep(wait)
                    yield Ev(value, t)
                await asyncio.sleep(0.5)   # let a lone tap settle before the unplug
                raise OSError(19, "No such device")
        ecodes = types.SimpleNamespace(EV_KEY=1, ecodes={"BTN_TRIGGER_HAPPY5": 300}, BTN={300: "BTN_TRIGGER_HAPPY5"}, KEY={})
        return types.SimpleNamespace(ecodes=ecodes, InputDevice=Dev, list_devices=lambda: ["/dev/input/event5"])

    def watch(self, ev, on_gesture, seconds):
        import asyncio
        import outrider.button

        async def go():
            w = outrider.button.ButtonWatch("X-56", "BTN_TRIGGER_HAPPY5", on_gesture, hold_ms=300, double_ms=150, evdev=ev)
            seen = []
            with unittest.mock.patch.object(outrider.button, "RETRY", 30):
                t = asyncio.ensure_future(w.run())
                for _ in range(int(seconds / 0.01)):
                    if w.status not in seen:
                        seen.append(w.status)
                    await asyncio.sleep(0.01)
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
            return seen
        return asyncio.run(go())

    def test_gestures_are_timed_by_the_event_timestamps(self):
        """R33: a 50 ms tap whose release reaches the loop 0.6 s late (the loop was busy) is still a tap, and a
        0.5 s hold whose press and release arrive together is still a hold."""
        got = []
        ev = self.stamped_evdev([(0, 0.0, 1), (0.6, 0.05, 0),                 # a tap, its release handed over late
                                 (0.4, 1.0, 1), (0.0, 1.5, 0)])               # a hold, both events queued together
        self.watch(ev, got.append, 2.2)
        self.assertEqual(got, ["status", "hush"])

    def test_a_failing_gesture_handler_does_not_kill_the_button(self):
        """R12: a handler that raises (a locked database while marking a rig) is logged and shown in the status;
        the next gestures still arrive."""
        import sqlite3
        got = []

        def handler(g):
            got.append(g)
            if len(got) == 1:
                raise sqlite3.OperationalError("database is locked")
        ev = self.stamped_evdev([(0, 0.0, 1), (0.01, 0.4, 0),                 # a hold: the handler raises
                                 (0.1, 0.6, 1), (0.01, 0.65, 0)])             # a tap afterwards still gets through
        with unittest.mock.patch("sys.stderr"):
            seen = self.watch(ev, handler, 1.2)
        self.assertEqual(got, ["hush", "status"])
        self.assertIn("listening to Saitek X-56 Throttle for BTN_TRIGGER_HAPPY5 (the last hush failed: database is locked)", seen)

    def test_config(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = lambda cfg: ed_outrider.settings_from(cfg, args, None, ([], []))["copilot"]
        self.assertEqual(st({}), {"enabled": False, "device": "", "button": "", "hold_ms": 600, "double_ms": 400})
        got = st({"copilot": {"enabled": True, "device": "X-56 Rhino Throttle", "button": 300, "hold_ms": 50, "double_ms": 5000}})
        self.assertEqual(got, {"enabled": True, "device": "X-56 Rhino Throttle", "button": "300", "hold_ms": 200, "double_ms": 1000})
        with unittest.mock.patch("sys.stderr"):
            self.assertFalse(st({"copilot": {"enabled": "true"}})["enabled"])   # a quoted switch is reported, stays off
            self.assertEqual(st({"copilot": {"button": True}})["button"], "")
            self.assertEqual(st({"copilot": {"device": 5}})["device"], "")
        full = ed_outrider.settings_from({"copilot": {"device": "X-56", "button": "BTN_TRIGGER_HAPPY5"}}, args, None, ([], []))
        back = tomllib.loads(ed_outrider.config_text(full))["copilot"]
        self.assertEqual(back, {"enabled": False, "device": "X-56", "button": "BTN_TRIGGER_HAPPY5", "hold_ms": 600, "double_ms": 400})
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "ed_outrider.toml.example"), encoding="utf-8") as f:
            example = f.read()
        self.assertIn("copilot", tomllib.loads(example))
        section = example.split("[copilot]", 1)[1]
        for key in ("enabled = false", "device", "button", "hold_ms = 600", "double_ms = 400"):
            self.assertIn(f"# {key}", section)
        readme = user_docs()
        for words in ("[copilot]", "uaccess", "`input` group", "latching", "Spoken lines", "Cut this line", "sound only"):
            self.assertIn(words, readme)

    # ---- the hush (server side) ----
    def test_hush(self):
        self.j.pos = {"id64": 11, "name": "A", "x": 0, "y": 0, "z": 0}
        self.assertIsNone(self.state.hush_info())
        v = self.state.version
        self.state.set_hush("10m")
        h = self.state.hush_info()
        self.assertEqual((h["mode"], h["sys"], self.state.version), ("10m", None, v + 1))
        self.assertAlmostEqual(h["left"], 600, delta=2)
        with unittest.mock.patch.object(ed_outrider.time, "time", lambda: h["until"] + 1):
            self.assertIsNone(self.state.hush_info())                      # run out
        self.assertIsNone(self.state.hush)
        self.state.set_hush("jump")
        self.assertEqual(self.state.hush_info(), {"mode": "jump", "until": None, "left": None, "sys": "11"})
        self.j.pos = dict(self.j.pos, id64=12)                              # the jump ends it
        self.assertIsNone(self.state.hush_info())
        self.state.set_hush("30m")
        self.state.set_hush("off")
        self.assertIsNone(self.state.hush_info())

        async def go(c):
            out = [(await c.post("/api/hush", json={"mode": "jump"})).status, self.state.hush_info()["sys"]]
            for body in ({"mode": "5m"}, {}, [1]):
                out.append((await c.post("/api/hush", json=body)).status)
            out.append((await c.post("/api/hush", json={"mode": "off"}, headers={"Sec-Fetch-Site": "cross-site"})).status)
            out.append(self.state.hush_info() is not None)                  # the refused request changed nothing
            r = await c.post("/api/hush", json={"mode": "off"})
            out.append((r.status, (await r.json())["hush"]))
            return out
        self.assertEqual(self.client(go), [200, "12", 400, 400, 400, 403, True, (200, None)])

    # ---- the co-pilot channel ----
    def test_copilot(self):
        self.j.pos = {"id64": 11, "name": "A", "x": 0, "y": 0, "z": 0}
        moments = list(self.j.moments) if hasattr(self.j, "moments") else None

        async def go(c):
            out = []
            r = await c.post("/api/copilot", json={"action": "status"})
            out.append((r.status, (await r.json())["seq"], self.state.copilot["action"]))
            out.append((await c.post("/api/copilot", json={"action": "replay"})).status)          # no words
            r = await c.post("/api/copilot", json={"action": "replay", "words": "  Tank   full. "})
            out.append((r.status, self.state.copilot["words"]))
            out.append((await c.post("/api/copilot", json={"action": "dance"})).status)
            out.append((await c.post("/api/copilot", json={"action": "status"}, headers={"Origin": "http://evil.example"})).status)
            await c.post("/api/copilot", json={"action": "hush"})                                  # a hold: hush till the jump
            out.append(self.state.hush_info()["mode"])
            await c.post("/api/copilot", json={"action": "hush"})                                  # another hold ends it
            out.append(self.state.hush_info())
            out.append(self.state.copilot["seq"])
            return out
        self.assertEqual(self.client(go), [(200, 1, "status"), 400, (200, "Tank full."), 400, 403, "jump", None, 4])
        if moments is not None:
            self.assertEqual(list(self.j.moments), moments)   # never a moment: a journal re-read cannot replay it
        # the button's gestures go through the same channel
        self.state.copilot_action("again")
        self.assertEqual((self.state.copilot["seq"], self.state.copilot["action"]), (5, "again"))

    def test_malformed_speech_file_keeps_the_last_good_one(self):   # Codex F7
        path = self.speech_file()
        sl = outrider.speech.SpeechLines(path)
        self.assertEqual(sl.set_ban("hull", "Hull {pct}.")[0], 200)
        good = sl.lines()["lines"]
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        doc["lines"]["hull"]["business"].append({"oops": "an object"})   # valid JSON, a wrong inner shape
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        os.utime(path, ns=(time.time_ns() + 10**9, time.time_ns() + 10**9))
        out = sl.lines()   # no TypeError in the bans
        self.assertEqual(out["lines"], good)
        self.assertIn("must be a list of strings", out["error"])
        self.assertIn("the last good copy is still in use", out["error"])
        self.assertEqual(sl.set_ban("hull", "Hull damage.")[0], 200)   # bans still work

    # ---- banned lines ----
    def test_ban_validation(self):
        path = self.speech_file()
        sl = outrider.speech.SpeechLines(path)
        v0 = sl.version()
        self.assertEqual(sl.set_ban("fuel_low", "Hull {pct}.")[0], 400)             # not an alert in the file
        self.assertEqual(sl.set_ban("hull", "Hull {pct} percent!")[0], 400)         # not a line in the file
        self.assertEqual(sl.set_ban("hull", 5)[0], 400)
        self.assertFalse(os.path.exists(outrider.speech.banned_path(path)))               # nothing written for a refusal
        status, out = sl.set_ban("hull", "Hull {pct}.")
        self.assertEqual((status, out), (200, {"ok": True, "banned": 1}))
        self.assertEqual(os.path.dirname(outrider.speech.banned_path(path)), self.tmp)    # next to the speech file
        got = sl.lines()
        self.assertEqual(got["lines"]["hull"]["business"], ["Hull at {pct} percent.", "Hull damage."])
        self.assertEqual(got["banned"], {"hull": ["Hull {pct}."]})
        self.assertNotEqual(sl.version(), v0)                                        # pages fetch the trimmed lines
        self.assertEqual(sl.set_ban("hull", "Hull {pct}.")[1]["banned"], 1)         # twice is once
        # a second reader (another process) sees the same bans
        self.assertEqual(outrider.speech.SpeechLines(path).lines()["lines"]["hull"]["business"], ["Hull at {pct} percent.", "Hull damage."])
        self.assertEqual(sl.set_ban("hull", "Hull {pct}.", ban=False), (200, {"ok": True, "banned": 0}))
        self.assertEqual(len(sl.lines()["lines"]["hull"]["business"]), 3)
        # a broken or odd file bans nothing, and never stops the lines loading
        for text in ("{not json", "[1, 2]", '{"hull": "Hull {pct}."}'):
            with open(outrider.speech.banned_path(path), "w") as f:
                f.write(text)
            fresh = outrider.speech.SpeechLines(path)
            self.assertEqual(len(fresh.lines()["lines"]["hull"]["business"]), 3, text)
            self.assertIsNone(fresh.lines()["error"])
        self.assertEqual(outrider.speech.read_bans(os.path.join(self.tmp, "missing.json")), {})

    def test_ban_never_empties_a_list(self):
        path = self.speech_file()
        sl = outrider.speech.SpeechLines(path)
        self.assertEqual(sl.set_ban("heat", "Heat damage.")[0], 200)
        status, out = sl.set_ban("heat", "Hot.")                                    # the last line left in the list
        self.assertEqual(status, 409)
        self.assertIn("last line", out["error"])
        self.assertEqual(sl.lines()["lines"]["heat"]["business"], ["Hot."])
        self.assertEqual(sl.set_ban("hull", "Ouch, {pct}.")[0], 409)               # a list of one
        # a hand-edited file that bans a whole list: the list is used whole, and the review says so
        with open(outrider.speech.banned_path(path), "w") as f:
            json.dump({"heat": ["Heat damage.", "Hot."]}, f)
        got = outrider.speech.SpeechLines(path).lines()
        self.assertEqual(got["lines"]["heat"]["business"], ["Heat damage.", "Hot."])
        self.assertEqual(got["banned_whole"], ["heat/business"])
        lines, whole = outrider.speech.apply_bans({"hull": {"business": ["a", "b"], "_note": "x", "when": ["a"]}}, {"hull": ["a"]})
        self.assertEqual((lines["hull"], whole), ({"business": ["b"], "_note": "x", "when": ["a"]}, []))

    def test_ban_endpoints_and_backup(self):
        import zipfile
        path = self.speech_file()
        self.state.speech = outrider.speech.SpeechLines(path)

        async def go(c):
            out = []
            v = self.state.version
            out.append((await c.post("/api/speech/ban", json={"alert": "hull", "template": "Hull damage."})).status)
            out.append(self.state.version > v)
            r = await c.get("/api/speech")
            doc = await r.json()
            out.append(("Hull damage." in doc["lines"]["hull"]["business"], doc["banned"]))
            out.append((await c.post("/api/speech/ban", json={"alert": "hull", "template": "made up"})).status)
            out.append((await c.post("/api/speech/ban", json={"alert": "hull"})).status)
            out.append((await c.post("/api/speech/ban", json={"alert": "hull", "template": "Hull {pct}."},
                                     headers={"Sec-Fetch-Site": "cross-site"})).status)
            out.append((await c.post("/api/speech/unban", json={"alert": "hull", "template": "Hull damage."})).status)
            out.append((await (await c.get("/api/speech")).json())["banned"])
            await c.post("/api/speech/ban", json={"alert": "heat", "template": "Hot."})
            return out
        self.assertEqual(self.client(go), [200, True, (False, {"hull": ["Hull damage."]}), 400, 400, 403, 200, {}])
        # the backup zip carries the bans beside the speech file
        dbp = os.path.join(self.tmp, "x.sqlite")
        sqlite3.connect(dbp).close()
        self.state.db_path, self.state.speech_path, self.state.config_path = dbp, path, None
        with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", os.path.join(self.tmp, "b")), \
                unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
            out = self.state.make_backup()
        self.assertEqual(out["files"], ["x.sqlite", "speech.json", "speech_banned.json"])
        with zipfile.ZipFile(out["path"]) as z:
            self.assertEqual(json.loads(z.read("speech_banned.json")), {"heat": ["Hot."]})

    def test_gitignored(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("data/", f.read().split())   # speech_banned.json lives in data/, ignored as a whole


class MiningLocations(unittest.TestCase):
    """Batch M4: planetary mining locations in Here, with the EDFM survey's odds as a tooltip."""

    MINE = "$PlanetaryMiningLocation_Name;"

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "S1", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def body(self, name, cls="Rocky body", volcanism=""):
        ev = scan("2026-01-01T00:01:00Z", "S1", 1, sum(map(ord, name)), f"S1 {name}")[2]
        ev.update(PlanetClass=cls, Volcanism=volcanism, Landable=True)
        self.j.handle(ev)

    def detail(self, name):
        self.db.commit()
        return next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == name)

    def test_count_from_fss_and_dss(self):
        self.body("A 1", "Icy body")
        self.body("A 2", "Metal rich body")
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyID": 3,
                       "BodyName": "S1 A 1", "Signals": [
                           {"Type": self.MINE, "Type_Localised": "Planetary Mining Location", "Count": 4},
                           {"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 2}]})
        self.j.handle({"event": "SAASignalsFound", "timestamp": "2026-01-01T00:03:00Z", "SystemAddress": 1, "BodyID": 3,
                       "BodyName": "S1 A 2", "Signals": [
                           {"Type": "$SAA_SignalType_Biological;", "Type_Localised": "Biological", "Count": 7},
                           {"Type": self.MINE, "Type_Localised": "Planetary Mining Location", "Count": 19}],
                       "Genuses": []})
        a1, a2 = self.detail("A 1"), self.detail("A 2")
        self.assertEqual((a1["mining"], a1["geo"], a2["mining"], a2["bio"]), (4, 2, 19, 7))
        self.assertEqual(a1["mining_odds"]["ground"], "icy")
        self.assertEqual(a2["mining_odds"]["ground"], "metal-rich")

    def test_no_count_no_tooltip(self):
        self.body("A 1", "Icy body")
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyID": 3,
                       "BodyName": "S1 A 1", "Signals": [{"Type": "$SAA_SignalType_Geological;", "Count": 2}]})
        b = self.detail("A 1")
        self.assertEqual((b["mining"], b["mining_odds"]), (0, None))

    def test_ground_classification(self):
        g = ed_outrider.mining_ground
        self.assertEqual(g("Metal-rich body", None), "metal-rich")
        self.assertEqual(g("High metal content world", "major rocky magma volcanism"), "high-metal-content")
        self.assertEqual(g("Rocky Ice world", ""), "rocky-ice")
        self.assertEqual(g("Icy body", "water geysers volcanism"), "icy")
        self.assertEqual(g("Rocky body", ""), "rocky")
        self.assertEqual(g("Rocky body", None), "rocky")
        self.assertEqual(g("Rocky body", "carbon dioxide geysers volcanism"), "rocky")
        self.assertEqual(g("Rocky body", "minor metallic magma volcanism"), "volcanic magma")
        self.assertEqual(g("Rocky body", "Rocky Magma"), "volcanic magma")          # Spansh's wording
        self.assertEqual(g("Rocky body", "major silicate vapour geysers volcanism"), "volcanic silicate")
        self.assertEqual(g("Rocky body", "Silicate Vapour Geysers"), "volcanic silicate")
        self.assertIsNone(g("Water world", ""))
        self.assertIsNone(g("Class I gas giant", None))
        # a scan's journal class is normalised to these names on the record
        self.body("B 1", "Rocky ice body")
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyID": 3,
                       "BodyName": "S1 B 1", "Signals": [{"Type": self.MINE, "Count": 3}]})
        self.assertEqual(self.detail("B 1")["mining_odds"]["ground"], "rocky-ice")

    def test_odds_file_loads(self):
        with open(ed_outrider.MINING_ODDS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertIn("CC BY-SA 4.0", raw["_note"]["license"])
        self.assertIn("edfieldmanual.com", raw["_note"]["source"])
        self.assertEqual(raw["attribution"]["researcher"], "CMDR Grumlop")
        odds = ed_outrider.load_mining_odds()
        self.assertEqual(set(odds), {"metal-rich", "high-metal-content", "rocky-ice", "rocky", "icy",
                                     "volcanic magma", "volcanic silicate"})
        for e in odds.values():
            pcts = [p for _, p in e["materials"]]
            self.assertEqual(pcts, sorted(pcts, reverse=True))
        self.assertEqual(ed_outrider.load_mining_odds("/nonexistent/mining_odds.json"), {})

    def test_odds_for_one_ground(self):
        o = ed_outrider.mining_odds("volcanic magma")
        self.assertEqual((o["surveyed"], o["few"]), (57, False))
        self.assertEqual([m["name"] for m in o["top"][:4]], ["Olivine", "Monazite", "Bastnasite", "Alexandrite"])
        self.assertEqual(o["top"][0]["pct"], 56.1)
        self.assertEqual((len(o["top"]), o["more"]), (ed_outrider.MINING_TOP, True))
        icy = ed_outrider.mining_odds("icy")
        self.assertEqual(icy["surveyed"], 124)
        self.assertEqual(icy["top"][0]["name"], "Deuterium")
        self.assertTrue(ed_outrider.mining_odds("rocky-ice")["few"])      # 14 locations surveyed
        self.assertIsNone(ed_outrider.mining_odds(None))
        self.assertIsNone(ed_outrider.mining_odds("gas giant"))

    def test_spansh_count_for_unscanned_and_scanned_bodies(self):
        dump = {"name": "S1 A 3", "type": "Planet", "subType": "Rocky body", "volcanismType": "Silicate Vapour Geysers",
                "signals": {"signals": {self.MINE: 12}, "updateTime": "2026-09-28T03:16:00Z"}}
        r = ed_outrider.record_from_dump("S1", dump)
        self.assertEqual(r["mining"], 12)
        self.assertEqual(ed_outrider.mining_ground(r["subtype"], r["volcanism"]), "volcanic silicate")
        # your scan without an FSS signal count takes Spansh's
        own = {"A 3": {"name": "A 3", "subtype": "Rocky body", "bio": 0, "geo": 0, "rings": []}}
        merged = ed_outrider.merge_records([r], own, {})
        self.assertEqual(merged[0]["mining"], 12)

    def test_old_database_gets_the_column(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.sqlite")
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE own_signals (system INTEGER, name TEXT, bio INTEGER, geo INTEGER, ts TEXT, "
                        "PRIMARY KEY (system, name))")
            con.commit()
            con.close()
            db = ed_outrider.open_db(path)
            self.addCleanup(db.close)
            self.assertIn("mining", {r["name"] for r in db.execute("PRAGMA table_info(own_signals)")})
            j = ed_outrider.Journals(db)
            j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyID": 3,
                      "BodyName": "S1 A 1", "Signals": [{"Type": self.MINE, "Count": 5}]})
            self.assertEqual(db.execute("SELECT mining FROM own_signals").fetchone()[0], 5)


class MinedPreviously(unittest.TestCase):
    """Batch M4b: what the SRV's refinery collected on each body (MiningRefined, 1 t each), rebuilt by a re-read."""

    SYS = 18207037532889

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)

    @staticmethod
    def session(t0="2026-09-30T03:00:"):
        """A login, a Rhino on body 19 (3 refined, docked), then relaunched on body 12 (2 refined)."""
        sys_ = MinedPreviously.SYS
        n = iter(range(10, 60))
        t = lambda: f"{t0}{next(n):02d}Z"
        body = lambda ev, bid, **kw: dict({"event": ev, "timestamp": t(), "StarSystem": "Smojooe AR-E b25-8",
                                           "SystemAddress": sys_, "Body": f"B {bid}", "BodyID": bid}, **kw)
        refine = lambda kind, loc: {"event": "MiningRefined", "timestamp": t(), "Type": f"${kind};", "Type_Localised": loc}
        return [
            {"event": "LoadGame", "timestamp": t(), "Commander": "X", "Ship": "Explorer_NX"},
            {"event": "Location", "timestamp": t(), "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": sys_,
             "StarPos": [0, 0, 0], "Docked": True, "StationName": "G0X-85Z", "StationType": "FleetCarrier"},
            body("ApproachBody", 19), body("SupercruiseExit", 19, BodyType="Planet"),
            {"event": "LaunchSRV", "timestamp": t(), "SRVType": "mev_rhino", "ID": 51, "PlayerControlled": True},
            refine("water_name", "Water"), refine("water_name", "Water"),
            refine("methanolmonohydratecrystals_name", "Methanol Monohydrate Crystals"),
            {"event": "DockSRV", "timestamp": t(), "SRVType": "mev_rhino", "ID": 51},
            refine("water_name", "Water"),                     # the ship's own refinery (no SRV out): not counted
            body("LeaveBody", 19), body("ApproachBody", 12), body("Touchdown", 12, PlayerControlled=True),
            {"event": "LaunchSRV", "timestamp": t(), "SRVType": "mev_rhino", "ID": 51, "PlayerControlled": True},
            refine("gold_name", "Gold"), refine("gold_name", "Gold"),
            {"event": "DockSRV", "timestamp": t(), "SRVType": "mev_rhino", "ID": 51},
        ]

    def mined(self, db=None):
        return {(r["body_id"], r["name"]): (r["tons"], r["first_ts"], r["last_ts"]) for r in
                (db or self.db).execute("SELECT * FROM own_mined WHERE system=?", (self.SYS,))}

    def test_launch_refine_dock_relaunch_on_another_body(self):
        for ev in self.session():
            self.j.handle(ev)
        got = self.mined()
        self.assertEqual({k: v[0] for k, v in got.items()},
                         {(19, "Water"): 2, (19, "Methanol Monohydrate Crystals"): 1, (12, "Gold"): 2})
        self.assertEqual(got[(19, "Water")][1:], ("2026-09-30T03:00:15Z", "2026-09-30T03:00:16Z"))
        self.assertIsNone(self.j.srv_state[""]["srv"])       # docked

    def test_nomad_first_then_the_rhino(self):   # F5: LaunchVessel kept the body; it used to forget it
        sys_, n = self.SYS, iter(range(10, 60))
        t = lambda: f"2026-09-30T05:00:{next(n):02d}Z"
        body = lambda ev, bid, **kw: dict({"event": ev, "timestamp": t(), "StarSystem": "S", "SystemAddress": sys_,
                                           "Body": f"B {bid}", "BodyID": bid}, **kw)
        for ev in (body("ApproachBody", 7), body("Touchdown", 7, PlayerControlled=True),
                   {"event": "LaunchVessel", "timestamp": t(), "VesselType": "lander01", "ID": 49, "PlayerControlled": True}):
            self.j.handle(ev)
        self.assertEqual(self.j.srv_state[""]["srv"]["body_id"], 7)
        self.assertEqual(self.j.body_here["body_id"], 7)
        for ev in ({"event": "DockSRV", "timestamp": t(), "SRVType": "lander01", "ID": 49},
                   {"event": "LaunchSRV", "timestamp": t(), "SRVType": "mev_rhino", "ID": 51, "PlayerControlled": True},
                   {"event": "MiningRefined", "timestamp": t(), "Type": "$bauxite_name;", "Type_Localised": "Bauxite"},
                   {"event": "MiningRefined", "timestamp": t(), "Type": "$bauxite_name;", "Type_Localised": "Bauxite"}):
            self.j.handle(ev)
        self.assertEqual({k: v[0] for k, v in self.mined().items()}, {(7, "Bauxite"): 2})

    def test_refined_with_no_known_body_is_ignored(self):
        ts = iter(f"2026-09-30T04:00:{i:02d}Z" for i in range(10, 60))
        # a ring: the ship's refinery
        self.j.handle({"event": "MiningRefined", "timestamp": next(ts), "Type": "$painite_name;", "Type_Localised": "Painite"})
        # an SRV launched with no body known (the journals began mid-session)
        self.j.handle({"event": "LaunchSRV", "timestamp": next(ts), "SRVType": "mev_rhino"})
        self.j.handle({"event": "MiningRefined", "timestamp": next(ts), "Type": "$water_name;", "Type_Localised": "Water"})
        # at a station, not a planet
        self.j.handle({"event": "SupercruiseExit", "timestamp": next(ts), "SystemAddress": 5, "Body": "Port", "BodyID": 40,
                       "BodyType": "Station"})
        self.j.handle({"event": "LaunchSRV", "timestamp": next(ts), "SRVType": "mev_rhino"})
        self.j.handle({"event": "MiningRefined", "timestamp": next(ts), "Type": "$water_name;"})
        # on a body, but supercruise in between ends the SRV
        self.j.handle({"event": "Touchdown", "timestamp": next(ts), "SystemAddress": 5, "Body": "P", "BodyID": 7})
        self.j.handle({"event": "LaunchSRV", "timestamp": next(ts), "SRVType": "mev_rhino"})
        self.j.handle({"event": "SupercruiseEntry", "timestamp": next(ts), "SystemAddress": 5})
        self.j.handle({"event": "MiningRefined", "timestamp": next(ts), "Type": "$water_name;"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM own_mined").fetchone()[0], 0)

    def test_login_in_the_srv(self):
        self.j.handle({"event": "LoadGame", "timestamp": "2026-09-19T15:48:00Z", "Commander": "X", "Ship": "Lander01"})
        self.j.handle({"event": "Location", "timestamp": "2026-09-19T15:49:04Z", "InSRV": True, "StarSystem": "Scaulae",
                       "SystemAddress": 8, "StarPos": [0, 0, 0], "Body": "Scaulae 8 g", "BodyID": 29, "BodyType": "Planet"})
        self.j.handle({"event": "MiningRefined", "timestamp": "2026-09-19T15:50:00Z", "Type": "$gold_name;",
                       "Type_Localised": "Gold"})
        self.assertEqual(self.db.execute("SELECT system, body_id, tons FROM own_mined").fetchall()[0][:], (8, 29, 1))

    def write_journals(self, d):
        """Two sessions in two files: the second's lines must not borrow the first's SRV."""
        first = self.session()
        second = [{"event": "MiningRefined", "timestamp": "2026-09-30T05:00:00Z", "Type": "$gold_name;",
                   "Type_Localised": "Gold"}]   # no LoadGame, no body: an SRV the journals never saw launched
        # the first session leaves an SRV out when its journal ends (a crash): drop its last DockSRV
        first = first[:-1]
        for name, evs in (("Journal.2026-09-30T030000.01.log", first), ("Journal.2026-09-30T045900.01.log", second)):
            with open(os.path.join(d, name), "w") as f:
                f.write("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in evs))   # the game writes "event":"X"

    def test_a_reread_gives_the_same_totals(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            jdir = os.path.join(d, "j"); os.mkdir(jdir)
            self.write_journals(jdir)
            path = os.path.join(d, "m.sqlite")
            db = ed_outrider.open_db(path)
            ed_outrider.Journals(db).scan_dir(jdir)
            db.commit()
            before = self.mined(db)
            self.assertEqual({k: v[0] for k, v in before.items()},
                             {(19, "Water"): 2, (19, "Methanol Monohydrate Crystals"): 1, (12, "Gold"): 2})
            # the same file read again (a line handled twice) adds nothing: offsets, and the source guard
            j = ed_outrider.Journals(db)
            j.line_source = "Journal.2026-09-30T030000.01.log:999"
            j.srv_state[j.session_key()] = {"at": None, "srv": {"system": self.SYS, "body_id": 12, "ts": ""}}
            ev = {"event": "MiningRefined", "timestamp": "2026-09-30T03:01:00Z", "Type": "$gold_name;", "Type_Localised": "Gold"}
            j.handle(ev); j.handle(ev)
            self.assertEqual(self.mined(db)[(12, "Gold")][0], 3)
            db.close()
            db = ed_outrider.open_db(path, rescan=True)
            self.addCleanup(db.close)
            self.assertEqual(db.execute("SELECT count(*) FROM own_mined").fetchone()[0], 0)
            self.assertIsNone(ed_outrider.meta_get(db, "srv_state"))
            ed_outrider.Journals(db).scan_dir(jdir)
            db.commit()
            self.assertEqual(self.mined(db), before)

    def test_session_key_drops_the_part_number(self):
        self.j.line_source = "Journal.2026-09-30T023726.02.log:12345"
        self.assertEqual(self.j.session_key(), "Journal.2026-09-30T023726")
        self.j.line_source = ""
        self.assertEqual(self.j.session_key(), "")

    def test_payload(self):
        import types
        state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        for ev in self.session():
            self.j.handle(ev)
        for bid in (19, 12):
            self.j.handle(dict(scan("2026-09-30T03:01:00Z", "Smojooe AR-E b25-8", self.SYS, bid,
                                    f"Smojooe AR-E b25-8 B {bid}")[2], PlanetClass="Icy body", Landable=True))
        self.db.commit()
        bodies = {b["name"]: b for b in state.system_detail(self.SYS)["bodies"]}
        self.assertEqual(bodies["B 19"]["mined"], [
            {"name": "Water", "tons": 2, "last": "2026-09-30T03:00:16Z"},
            {"name": "Methanol Monohydrate Crystals", "tons": 1, "last": "2026-09-30T03:00:17Z"}])
        self.assertEqual([m["tons"] for m in bodies["B 12"]["mined"]], [2])
        self.assertEqual(bodies["B 12"]["mining"], 0)        # mined history with no survey count still shows


class SurfaceRigs(unittest.TestCase):
    """Batch M1: the surface map's server side: rigs marked by the co-pilot button in the Rhino, collections placed
    from Status.json, the ship marker, the vehicle, mining location markers, the leash and the payload block."""

    SYS, BODY, NAME, R = 18207037532889, 19, "Smojooe AR-E b25-8 ABC 3 d", 1_000_000.0
    SRV = 1 << 26

    def setUp(self):
        import tempfile
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dir, ignore_errors=True))
        self.base = time.time()
        self.line = 0
        self.ev(0, {"event": "Location", "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": self.SYS, "StarPos": [0, 0, 0],
                    "Docked": True, "StationType": "FleetCarrier"})
        self.ev(1, {"event": "SupercruiseExit", "StarSystem": "Smojooe AR-E b25-8", "SystemAddress": self.SYS,
                    "Body": self.NAME, "BodyID": self.BODY, "BodyType": "Planet"})

    def ts(self, s):
        return ed_outrider.iso_ts(self.base + s)

    def ev(self, s, ev):
        """A journal line read s seconds into the test (its timestamp then too), as a live line."""
        self.line += 1
        self.j.line_source = f"Journal.2026-09-30T030000.01.log:{self.line}"
        with unittest.mock.patch.object(ed_outrider.time, "time", lambda: self.base + s):
            self.j.handle(dict(ev, timestamp=self.ts(s)))
        self.j.line_source = ""

    def status(self, s, north=0.0, east=0.0, heading=0, flags=None, alt=0, flags2=0, **kw):
        """Status.json at s seconds, `north`/`east` metres from lat 0, lon 0 (read the way the tick reads it)."""
        k = 180 / math.pi / self.R
        st = {"timestamp": self.ts(s), "event": "Status", "Flags": self.SRV if flags is None else flags, "Flags2": flags2,
              "Latitude": north * k, "Longitude": east * k, "Heading": heading, "Altitude": alt,
              "BodyName": self.NAME, "PlanetRadius": self.R, **kw}
        with open(os.path.join(self.dir, "Status.json"), "w") as f:
            json.dump(st, f)
        self.j.read_status(self.dir)

    def launch(self, s=2, srv="mev_rhino"):
        self.ev(s, {"event": "LaunchSRV", "SRVType": srv, "ID": 51, "PlayerControlled": True})

    def texts(self, kinds=("rig", "rig_leash")):
        return [m["text"] for m in self.j.moments if m["kind"] in kinds]

    def refine(self, s, what="Water", n=1):
        for i in range(n):
            self.ev(s + i, {"event": "MiningRefined", "Type": f"${what.lower()}_name;", "Type_Localised": what})

    def out(self):
        return {r["n"]: r for r in self.state.rigs_out(self.SYS, self.BODY)}

    def test_presses_place_1_2_3_and_a_tap_by_one_picks_it_up(self):
        self.launch()
        self.status(10, 0, 0, heading=0)
        self.assertEqual(self.state.mark_rig(self.base + 10)["n"], 1)
        rig = self.out()[1]   # 7 m behind the cockpit: heading north, so 7 m south
        self.assertAlmostEqual(ed_outrider.surface_m(0, 0, rig["lat"], rig["lon"], self.R), 7.0, places=2)
        self.assertLess(rig["lat"], 0)
        self.status(20, 100, 0, heading=90)
        self.state.mark_rig(self.base + 20)
        self.status(30, 200, 0, heading=90)
        self.state.mark_rig(self.base + 30)
        self.assertEqual(sorted(self.out()), [1, 2, 3])
        self.state.mark_rig(self.base + 35)          # the same spot again: rig 3 is within 5 m, so it is picked up
        self.assertEqual(sorted(self.out()), [1, 2])
        self.assertEqual(self.texts(), ["Rig 1 placed.", "Rig 2 placed.", "Rig 3 placed.", "Rig 3 picked up."])
        self.assertEqual(self.db.execute("SELECT count(*) FROM surface_rigs").fetchone()[0], 2)   # an empty rig is forgotten

    def test_the_lowest_free_number_after_a_pickup(self):
        self.launch()
        for i, north in enumerate((0, 100, 200)):
            self.status(10 + i, north, 0, heading=0)
            self.state.mark_rig(self.base + 10 + i)
        self.status(20, 100 - 5, 0, heading=90)      # drive over rig 2 (7 m south of where you pressed): 2 m off
        self.assertEqual(self.state.mark_rig(self.base + 20)["what"], "picked")
        self.status(30, 400, 0, heading=0)
        self.assertEqual(self.state.mark_rig(self.base + 30)["n"], 2)
        self.status(40, 600, 0, heading=0)
        self.assertEqual(self.state.mark_rig(self.base + 40)["n"], 4)

    def test_six_out_refuses(self):
        self.launch()
        for i in range(7):
            self.status(10 + i, 100 * i, 0)
            self.state.mark_rig(self.base + 10 + i)
        self.assertEqual(sorted(self.out()), [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.texts()[-1], "Six rigs out.")

    def test_the_button_does_nothing_else_in_the_rhino(self):
        self.launch()
        self.status(10)
        for g in ("status", "again", "hush"):
            self.state.copilot_gesture(g)
        self.assertEqual(self.state.copilot["seq"], 0)       # no status report, say again...
        self.assertIsNone(self.state.hush)                    # ...or hush
        self.assertEqual(self.texts(), ["Rig 1 placed.", "Rig 1 picked up.", "Rig 1 placed."])
        # outside the Rhino (on foot, in the ship, in a Scarab) the button works as usual: a double press is the status
        # report, a hold the hush (the single press targets the next route system in the ship: test_highway)
        self.status(70, flags=(1 << 1) | ed_outrider.FLAG_IN_MAIN_SHIP)   # landed, back in the ship a minute on
        self.state.watch_surface(self.base + 70)
        self.assertIsNone(self.j.vehicle)
        self.state.copilot_gesture("again")
        self.state.copilot_gesture("hush")
        self.assertEqual((self.state.copilot["seq"], self.state.copilot["action"]), (2, "hush"))
        self.assertIsNotNone(self.state.hush)
        self.launch(80, "testbuggy")
        self.status(81)
        self.state.copilot_gesture("status")   # a single press in a Scarab: nothing to target there, nothing done
        self.assertEqual(self.state.copilot["seq"], 2)
        self.state.copilot_gesture("again")
        self.assertEqual(self.state.copilot["action"], "status")
        self.assertEqual(len(self.texts()), 3)
        # the page's own requests (the Now bar) never mark rigs, even in the Rhino
        self.launch(90)
        self.status(91, 300)
        self.state.copilot_action("status")
        self.assertEqual(self.state.copilot["action"], "status")
        self.assertEqual(len(self.texts()), 3)

    def test_the_button_watch_marks_rigs_through_a_stand_in_device(self):
        """The co-pilot path end to end with the stand-in evdev (never a real device): the button's tap, double tap
        and hold reach State.copilot_gesture, which in the Rhino marks rigs with each."""
        import asyncio
        import outrider.button
        ev, Dev = button_fake_evdev(self, [(0, 1), (0.02, 0), (0.25, 1), (0.02, 0), (0.03, 1), (0.02, 0),
                                                        (0.25, 1), (0.2, 0), (0.05, 2)])
        self.launch()
        self.status(10, 0, 0, heading=180)

        async def go():
            w = outrider.button.ButtonWatch("X-56", "BTN_TRIGGER_HAPPY5", self.state.copilot_gesture, hold_ms=150,
                                      double_ms=100, evdev=ev)
            with unittest.mock.patch.object(outrider.button, "RETRY", 5):
                t = asyncio.ensure_future(w.run())
                await asyncio.sleep(1.0)
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
        asyncio.run(go())
        self.assertEqual(self.texts(), ["Rig 1 placed.", "Rig 1 picked up.", "Rig 1 placed."])
        self.assertEqual(self.state.copilot["seq"], 0)
        self.assertIsNone(self.state.hush)

    def test_collections_add_up_on_a_rig_and_a_far_one_is_an_unmarked_site(self):
        self.launch()
        self.status(10, 0, 0, heading=180)                    # facing south: the rig lands 7 m north
        self.state.mark_rig(self.base + 10)
        self.status(100, 9, 0, heading=0)                     # over the rig, 2 m off
        self.refine(101, "Water", 11)
        self.state.watch_surface(self.base + 120)             # still going: not said yet
        self.assertEqual(self.texts()[-1], "Rig 1 placed.")
        self.state.watch_surface(self.base + 145)
        self.assertEqual(self.texts()[-1], "Rig 1: 11 tons of Water.")
        self.status(300, 7, 1)                                # a second collection three minutes later
        self.refine(301, "Water", 3)
        self.state.watch_surface(self.base + 340)
        rig = self.out()[1]
        self.assertEqual((json.loads(rig["minerals"]), rig["tons"]), ({"Water": 14}, 14))
        self.assertIsNone(rig["picked_ts"])                   # the rig stays out
        self.status(500, 0, 400)                              # 400 m away, no rig marked there
        self.refine(501, "Gold", 1)
        self.state.watch_surface(self.base + 540)
        self.assertEqual(self.texts()[-1], "1 ton of Gold. No rig marked here; site saved.")
        site = self.db.execute("SELECT * FROM surface_sites").fetchone()
        self.assertEqual((site["tons"], json.loads(site["minerals"])), (1, {"Gold": 1}))
        # own_mined counted the same tons once each (the map only says where they came from)
        self.assertEqual({r["name"]: r["tons"] for r in self.db.execute("SELECT * FROM own_mined")}, {"Water": 14, "Gold": 1})
        # a replayed (old) line places nothing
        self.j.handle({"event": "MiningRefined", "timestamp": "2026-01-01T00:00:00Z", "Type": "$water_name;", "Type_Localised": "Water"})
        self.assertEqual(self.out()[1]["tons"], 14)

    def test_a_late_ton_joins_the_collection_and_a_failed_tick_does_not_double_it(self):
        self.launch()
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        self.status(20, 7, 0)
        self.refine(21, "Water", 2)
        self.state.watch_surface(self.base + 60)
        self.db.commit()                                     # the tick commits before a later one fails
        cp = self.j.checkpoint()
        self.refine(70, "Water", 1)                          # 48 s later: the refinery's last bin, same rig, unsaid
        self.j.restore(cp)
        self.db.rollback()
        self.refine(70, "Water", 1)
        self.state.watch_surface(self.base + 110)
        self.assertEqual(self.out()[1]["tons"], 3)
        self.assertEqual(self.texts(), ["Rig 1 placed.", "Rig 1: 2 tons of Water."])

    def test_two_rigs_collected_within_the_minute_are_two_collections(self):
        self.launch()
        for s, north in ((10, 0), (20, 80)):
            self.status(s, north, 0, heading=180)
            self.state.mark_rig(self.base + s)
        self.status(100, 7, 0)
        self.refine(101, "Water", 10)
        self.status(130, 87, 0)                               # 80 m on, 20 s after the last ton
        self.refine(131, "Water", 2)
        self.state.watch_surface(self.base + 170)
        self.assertEqual(self.texts()[-2:], ["Rig 1: 10 tons of Water.", "Rig 2: 2 tons of Water."])
        self.assertEqual({n: r["tons"] for n, r in self.out().items()}, {1: 10, 2: 2})

    def test_tables_survive_a_journal_reread(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.sqlite")
            db = ed_outrider.open_db(path)
            db.execute("INSERT INTO surface_rigs (system, body_id, n, lat, lon, placed_ts, minerals, tons) VALUES (1, 2, 1, 0, 0, 'x', '{}', 0)")
            db.execute("INSERT INTO surface_sites (system, body_id, lat, lon, minerals, tons) VALUES (1, 2, 0, 0, '{}', 3)")
            db.execute("INSERT INTO mining_locations VALUES (1, 2, 3, 'B', 0, 0, 'x')")
            ed_outrider.meta_set(db, "vehicle", {"srv_type": "mev_rhino", "ts": "x"})
            db.commit(); db.close()
            db = ed_outrider.open_db(path, rescan=True)
            self.addCleanup(db.close)
            for t in ("surface_rigs", "surface_sites", "mining_locations"):
                self.assertEqual(db.execute(f"SELECT count(*) FROM {t}").fetchone()[0], 1, t)
            self.assertIsNone(ed_outrider.meta_get(db, "vehicle"))   # journal-derived: rebuilt by the re-read
        self.assertNotIn("surface_", ed_outrider.RESET_JOURNAL_DATA)
        self.assertNotIn("mining_locations", ed_outrider.RESET_JOURNAL_DATA)

    def test_show_hide_hysteresis(self):
        show = lambda s, **kw: (self.status(s, **kw), self.state.surface_summary()["show"])[1]
        self.assertTrue(show(1, flags=0, alt=900))
        self.assertTrue(show(2, flags=0, alt=1050))           # between the two: unchanged
        self.assertFalse(show(3, flags=0, alt=1150))
        self.assertFalse(show(4, flags=0, alt=1050))          # still unchanged, from the other side
        self.assertTrue(show(5, flags=0, alt=999))
        self.assertFalse(show(6, flags=ed_outrider.FLAG_ALT_AVG, alt=500))   # altitude from the average radius
        self.assertTrue(show(7, alt=None))                    # in the SRV, no altitude
        self.assertTrue(show(8, flags=0, flags2=1, alt=None))  # on foot
        self.assertFalse(show(9, flags=0, alt=None))          # flying with no altitude
        sf = self.state.surface_summary()
        self.assertEqual((sf["down"], sf["alt_avg"]), (False, False))   # the page's own show/hide altitude reads these
        self.status(9, flags=ed_outrider.FLAG_ALT_AVG, alt=500)
        self.assertEqual((self.state.surface_summary()["down"], self.state.surface_summary()["alt_avg"]), (False, True))
        self.status(9, flags=ed_outrider.FLAG_LANDED, alt=0)
        self.assertTrue(self.state.surface_summary()["down"])
        self.status(9, flags=0, flags2=1, alt=None)
        self.assertTrue(self.state.surface_summary()["down"])
        self.status(10, flags=0, alt=500, BodyName=None)
        self.assertIsNone(self.state.surface_summary())       # no body under you: no block at all

    def test_the_map_bumps_on_5_m_or_10_degrees_twice_a_second_at_most(self):
        self.status(1, 0, 0, heading=10)
        self.assertTrue(self.state.surface_moved(100.0))
        self.status(2, 3, 0, heading=15)
        self.assertFalse(self.state.surface_moved(101.0))     # 3 m and 5 degrees
        self.status(3, 6, 0, heading=15)
        self.assertTrue(self.state.surface_moved(101.6))
        self.status(4, 12, 0, heading=15)
        self.assertFalse(self.state.surface_moved(101.9))     # 6 m more, but too soon
        self.status(4, 6, 0, heading=359)
        self.assertTrue(self.state.surface_moved(102.5))      # a 16 degree turn across north
        self.status(5, 6, 0, heading=359, flags=0, alt=5000)
        self.assertTrue(self.state.surface_moved(104.0))      # it just stopped showing: the page hears that once (F24)
        self.status(6, 6, 0, heading=359, flags=0, alt=6000)
        self.assertFalse(self.state.surface_moved(105.0))     # the map is hidden: no bumps

    def test_climbing_past_the_altitude_wakes_the_page(self):   # F24: in the air, nothing else changes as you climb
        self.status(1, 0, 0, heading=10, flags=0, alt=900)
        self.assertTrue(self.state.surface_moved(100.0))
        self.status(2, 0, 0, heading=10, flags=0, alt=1050)   # inside the hide margin: still shown, not moved
        self.assertFalse(self.state.surface_moved(101.0))
        self.status(3, 0, 0, heading=10, flags=0, alt=1200)
        self.assertTrue(self.state.surface_moved(102.0))
        self.assertFalse(self.state.surface_summary()["show"])
        self.status(4, 0, 0, heading=10, flags=0, alt=3000)
        self.assertFalse(self.state.surface_moved(103.0))
        self.status(5, 0, 0, heading=10, flags=0, alt=800)    # down again: shows, and says so
        self.assertTrue(self.state.surface_moved(104.0))

    def test_ship_marker_survives_an_srv_or_on_foot_liftoff(self):
        td = {"event": "Touchdown", "StarSystem": "S", "SystemAddress": self.SYS, "Body": self.NAME, "BodyID": self.BODY,
              "Latitude": 1.5, "Longitude": 2.5, "PlayerControlled": True}
        self.ev(10, td)
        self.assertEqual((self.j.ship_marker["lat"], self.j.ship_marker["lon"]), (1.5, 2.5))
        self.ev(20, {"event": "Liftoff", "SystemAddress": self.SYS, "BodyID": self.BODY, "Latitude": 1.5, "Longitude": 2.5,
                     "PlayerControlled": False})       # dismissed with you on foot or in the SRV
        self.assertIsNotNone(self.j.ship_marker)
        self.ev(25, dict(td, Latitude=9.0, Taxi=True))         # an Apex shuttle is not your ship
        self.assertEqual(self.j.ship_marker["lat"], 1.5)
        self.status(26, 0, 0)
        self.assertEqual(self.state.surface_summary()["ship"]["lat"], 1.5)
        self.ev(30, {"event": "Liftoff", "SystemAddress": self.SYS, "BodyID": self.BODY, "PlayerControlled": True})
        self.assertIsNone(self.j.ship_marker)
        # no Touchdown seen on this body (the 30 Sep run): the SRV's launch spot is the ship's
        self.status(40, 50, 60, flags=1 << 1)
        self.launch(41)
        self.assertAlmostEqual(self.j.ship_marker["lat"], 50 * 180 / math.pi / self.R)

    def test_vehicle_and_a_relog_in_the_srv(self):
        self.launch()
        self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino")
        self.ev(10, {"event": "LoadGame", "Commander": "X", "Ship": "Explorer_NX"})
        self.ev(11, {"event": "Location", "InSRV": True, "StarSystem": "S", "SystemAddress": self.SYS, "StarPos": [0, 0, 0],
                     "Body": self.NAME, "BodyID": self.BODY, "BodyType": "Planet"})
        self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino")   # the SRV launched and never docked
        self.status(12)
        self.assertTrue(self.state.in_rhino())
        self.launch(13)                                       # a relaunch read before Status.json catches up:
        self.status(13, flags=1 << 1)                         # the in-SRV flag not set yet, same second
        self.state.watch_surface(self.base + 13)
        self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino")   # not taken for leaving the SRV
        self.ev(20, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})
        self.assertIsNone(self.j.vehicle)
        self.ev(30, {"event": "Location", "InSRV": True, "StarSystem": "S", "SystemAddress": self.SYS, "StarPos": [0, 0, 0],
                     "Body": self.NAME, "BodyID": self.BODY, "BodyType": "Planet"})
        self.assertIsNone(self.j.vehicle["srv_type"])               # an SRV of unknown type: the button is unchanged
        self.assertFalse(self.state.in_rhino())

    def test_which_way_in_eight_sectors(self):   # S9
        w, b = ed_outrider.which_way, ed_outrider.surface_bearing
        self.assertEqual([w(x, 0) for x in (0, 44, 90, 140, 180, 225, 270, 330)],
                         ["ahead", "ahead on your right", "on your right", "behind on your right", "behind you",
                          "behind on your left", "on your left", "ahead on your left"])
        self.assertEqual(w(90, 90), "ahead")                          # relative to where you face
        self.assertEqual([w(45), w(181), w(359)], ["to the north-east", "to the south", "to the north"])   # no heading
        self.assertAlmostEqual(b(0, 0, 1, 0), 0, places=6)            # due north
        self.assertAlmostEqual(b(0, 0, 0, 1), 90, places=6)           # due east
        self.assertAlmostEqual(b(0, 0, -1, -1), 225, delta=0.1)

    def test_the_leash(self):
        self.launch()
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        for s, north in ((20, 3000), (30, 3600), (40, 3700), (50, 4600), (60, 4700)):
            self.status(s, north, 0)
            self.state.watch_surface(self.base + s)
        self.assertEqual(self.texts(("rig_leash",)), ["Rig 1 is 3.6 kilometres away, behind you; it is lost at 5.",
                                                   "Rig 1 is 4.6 kilometres away, behind you; it is lost at 5."])
        self.status(70, 2000, 0)
        self.state.watch_surface(self.base + 70)              # back in range: it may warn again
        self.status(80, 5100, 0)
        self.state.watch_surface(self.base + 80)
        self.assertEqual(self.texts(("rig_leash",))[-1], "Rig 1 lost: over 5 kilometres from the Rhino.")
        self.assertEqual(self.out(), {})
        # a lost rig that collected is kept as a site, and says it was lost, not picked up (F43)
        self.status(81, 5100, 0, heading=180)
        self.state.mark_rig(self.base + 81)
        self.status(82, 5107, 0)
        self.refine(83, "Gold", 3)
        self.status(84, 10300, 0)
        self.state.watch_surface(self.base + 84)
        self.assertEqual([(s["tons"], s["lost"]) for s in self.state.surface_sites(self.SYS, self.BODY)], [(3, True)])
        # leaving the body loses the rigs too; one that collected keeps its site
        self.status(90, 0, 0, heading=180)
        self.state.mark_rig(self.base + 90)
        self.status(100, 7, 0)
        self.refine(101, "Gold", 2)
        self.ev(200, {"event": "LeaveBody", "StarSystem": "S", "SystemAddress": self.SYS, "Body": self.NAME, "BodyID": self.BODY})
        self.assertEqual(self.out(), {})
        self.assertEqual(sorted((s["kind"], s["tons"], s["lost"]) for s in self.state.surface_sites(self.SYS, self.BODY)),
                         [("rig", 2, True), ("rig", 3, True)])

    def test_mining_location_marker_and_sites_grouped_by_it(self):
        dest = {"System": self.SYS, "Body": self.BODY, "Name": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=3;"}
        self.status(10, 500, 0, flags=0, alt=300, Destination=dest)
        self.state.watch_surface(self.base + 10)              # flying: not arrived
        self.assertEqual(self.db.execute("SELECT count(*) FROM mining_locations").fetchone()[0], 0)
        self.status(20, 1000, 0, flags=1 << 1, Destination=dest)   # landed with it targeted
        self.state.watch_surface(self.base + 20)
        self.launch(30)
        self.status(31, 1010, 0, heading=180, Destination=dest)
        self.state.watch_surface(self.base + 31)              # in the SRV: the landing's marker stays
        loc = self.state.surface_summary()["locations"]
        self.assertEqual([(l["n"], round(l["dist"])) for l in loc], [(3, 10)])
        self.state.mark_rig(self.base + 32)
        self.status(40, 1017, 0)
        self.refine(41, "Water", 2)
        self.state.watch_surface(self.base + 80)
        self.status(90, 1017, 0, heading=0)
        self.state.mark_rig(self.base + 90)                   # pick it up: now a saved site
        self.status(200, 9000, 0)
        self.refine(201, "Gold", 1)                           # far from L3: an unmarked site of no location
        sites = self.state.surface_sites(self.SYS, self.BODY, self.state.surface_here())
        self.assertEqual([(s["kind"], s["location"], s["tons"]) for s in sites], [("rig", 3, 2), ("site", None, 1)])
        # a location on another body is not this body's
        self.db.execute("INSERT INTO own_bodies (system, body_id, name) VALUES (?, 12, 'other')", (self.SYS,))
        self.status(110, 9000, 0, flags=1 << 1, Destination=dict(dest, Body=12, Name=dest["Name"].replace("=3", "=5")))
        self.state.watch_surface(self.base + 110)
        self.assertEqual([r[0] for r in self.db.execute("SELECT idx FROM mining_locations")], [3])

    def test_payload_block(self):
        self.ev(3, {"event": "Touchdown", "SystemAddress": self.SYS, "Body": self.NAME, "BodyID": self.BODY,
                    "Latitude": 0.0, "Longitude": 0.0, "PlayerControlled": True})
        self.launch(4)
        self.db.execute("INSERT INTO own_organic (system, body_id, species, genus_name, species_name, samples, ts) "
                        "VALUES (?, ?, 'sp_a', 'Bacterium', 'Bacterium Aurasus', 1, ?)", (self.SYS, self.BODY, self.ts(5)))
        self.db.execute("INSERT INTO own_organic (system, body_id, species, genus_name, species_name, samples, ts) "
                        "VALUES (?, ?, 'sp_b', 'Stratum', 'Stratum Tectonicas', 2, ?)", (self.SYS, self.BODY, self.ts(4)))
        k = 180 / math.pi / self.R
        self.db.execute("INSERT INTO sample_points VALUES (?, ?, 'sp_a', '$Codex_Ent_Bacterial_Genus_Name;', 1, ?, 0, ?)",
                        (self.SYS, self.BODY, 600 * k, self.ts(5)))
        self.db.execute("INSERT INTO sample_points VALUES (?, ?, 'sp_b', '$Codex_Ent_Stratum_Genus_Name;', 1, ?, 0, ?)",
                        (self.SYS, self.BODY, 100 * k, self.ts(4)))
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        p = self.state.payload()
        sf = p["surface"]
        self.assertEqual((sf["body"], sf["body_id"], sf["heading"], sf["show"], sf["rhino"]), ("ABC 3 d", 19, 180, True, True))
        self.assertEqual(sf["ship"]["dist"], 0)
        self.assertEqual([(r["n"], r["dist"], r["tons"], r["full"]) for r in sf["rigs"]], [(1, 7, 0, False)])
        self.assertEqual([(b["species"], b["current"], b["need"], b["clear"]) for b in sf["bio"]],
                         [("Bacterium Aurasus", True, 500, True), ("Stratum Tectonicas", False, 500, False)])
        self.assertEqual(p["defaults"]["rig_spacing"], 50)
        self.assertTrue(self.state.surface_summary(now=self.base + 10 + 481)["rigs"][0]["full"])   # 8 min: probably full

    def test_mining_sites_list(self):
        """Batch M3: Materials' Mining sites, one entry per body: a rig and two unmarked sites on ABC 3 d (Water twice,
        combined), own_mined on another body only, tons never counted twice, and forget keeping the mined history."""
        self.launch()
        self.status(10, 0, 0, heading=0)
        self.state.mark_rig(self.base + 10)                       # rig 1, 7 m south
        self.status(20, -7, 0, heading=0)
        self.refine(20, "Water", 4)
        self.status(200, 500, 0)
        self.refine(200, "Methanol Monohydrate Crystals", 3)      # far from the rig: an unmarked site
        self.status(400, 1000, 0)
        self.refine(400, "Water", 2)                              # another unmarked site
        self.state.journals.end_burst(self.base + 1000, force=True)
        self.db.execute("INSERT INTO mining_locations VALUES (?, ?, 3, ?, 0, 0, 'x')", (self.SYS, self.BODY, self.NAME))
        self.db.execute("INSERT INTO mining_locations VALUES (?, 5, 1, 'elsewhere', 0, 0, 'x')", (self.SYS,))  # nothing mined
        self.db.execute("INSERT INTO own_mined VALUES (?, 7, 'gold', 'Gold', 5, ?, ?, '')", (self.SYS, self.ts(1), self.ts(1)))
        sites = {s["body_id"]: s for s in self.state.mining_sites()}
        self.assertEqual(sorted(sites), [7, self.BODY])
        abc = sites[self.BODY]
        self.assertEqual((abc["system"], abc["id"], abc["body"], abc["distance"]), ("Smojooe AR-E b25-8", str(self.SYS), "ABC 3 d", 0.0))
        self.assertEqual(abc["minerals"], [{"name": "Water", "tons": 6}, {"name": "Methanol Monohydrate Crystals", "tons": 3}])
        self.assertEqual((abc["tons"], abc["rigs"], abc["unmarked"], abc["locations"], abc["saved"]), (9, 1, 2, [3], True))
        self.assertEqual(abc["last"], self.ts(401))
        self.assertEqual((sites[7]["body"], sites[7]["minerals"], sites[7]["saved"]), ("body 7", [{"name": "Gold", "tons": 5}], False))
        self.state.forget_sites(self.SYS, self.BODY)             # the rig is still out, so it stays
        abc = {s["body_id"]: s for s in self.state.mining_sites()}[self.BODY]
        self.assertEqual((abc["tons"], abc["rigs"], abc["unmarked"], abc["locations"]), (9, 1, 0, []))
        self.assertFalse(abc["saved"])            # R28: only the rig still out is left, and forget never takes it
        self.state.mark_rig(self.base + 1100)                    # not by the rig: a new one (empty rigs are not sites)
        self.status(1110, -7, 0, heading=0)
        self.state.mark_rig(self.base + 1110)                    # by rig 1: picked up, kept as a saved site
        self.state.forget_sites(self.SYS, self.BODY)
        abc = {s["body_id"]: s for s in self.state.mining_sites()}[self.BODY]
        self.assertEqual((abc["tons"], abc["rigs"], abc["saved"]), (6 + 3, 0, False))   # the mined history stays

    def test_rig_restock_recipe(self):
        inv = outrider.materials.inventory({"counts": {"iron": 10, "nickel": 5, "mechanicalequipment": 4}, "names": {}})
        r = next(x for x in inv["synthesis"] if x["name"] == "Mining rig restock")
        self.assertEqual((r["craftable"], r["limit"]), (2, "Nickel"))
        self.assertEqual([(m["name"], m["need"]) for m in r["materials"]], [("Iron", 3), ("Nickel", 2), ("Mechanical Equipment", 1)])
        self.assertEqual(outrider.materials.MATERIALS["mechanicalequipment"], ("Mechanical Equipment", "Manufactured", 2))
        self.assertEqual(outrider.materials.craftable({"iron": 30, "nickel": 20}, r and outrider.materials.SYNTH["Mining rig restock"]["materials"]),
                         (0, "mechanicalequipment"))

    def test_endpoints(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        self.launch()
        self.status(10, 0, 0, heading=180)
        rid = self.state.mark_rig(self.base + 10)["id"]
        self.db.execute("INSERT INTO surface_sites (system, body_id, lat, lon, minerals, tons) VALUES (?, ?, 0, 0, '{}', 3)",
                        (self.SYS, self.BODY))
        self.db.execute("INSERT INTO mining_locations VALUES (?, ?, 1, 'B', 0, 0, 'x')", (self.SYS, self.BODY))

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                mat = await (await c.get("/api/materials")).json()
                self.assertEqual([x["unmarked"] for x in mat["mining_sites"]], [1])
                r1 = await c.post("/api/rigs/remove", json={"id": rid}, headers={"Origin": "http://evil.example"})
                r2 = await c.post("/api/rigs/remove", json={"id": "x"})
                r3 = await c.post("/api/rigs/remove", json={"id": rid})
                r4 = await c.post("/api/rigs/remove", json={"id": rid})
                r5 = await c.post("/api/sites/forget", json={"system": str(self.SYS), "body": self.BODY})
                r6 = await c.post("/api/sites/forget", json={"system": "nope"})
                return [r.status for r in (r1, r2, r3, r4, r5, r6)], await r5.json()
        statuses, forgot = asyncio.run(go())
        self.assertEqual(statuses, [403, 400, 200, 404, 200, 400])
        self.assertEqual(forgot["forgot"], 2)
        for t in ("surface_rigs", "surface_sites", "mining_locations"):
            self.assertEqual(self.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0], 0, t)

    def test_config_keys(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual((st["surface_alt"], st["rig_spacing"], st["surface_map_min"], st["surface_map_strip"], st["rig_warn"]),
                         (1000, 50, 500, False, 3500))
        back = tomllib.loads(ed_outrider.config_text(st))["defaults"]
        self.assertEqual((back["surface_alt"], back["rig_spacing"], back["surface_map_min"], back["surface_map_strip"], back["rig_warn"]),
                         (1000, 50, 500, False, 3500))
        st = ed_outrider.settings_from({"defaults": {"rig_warn": 9000, "rig_spacing": -1}}, args, None, ([], []))
        self.assertEqual((st["rig_warn"], st["rig_spacing"]), (4900, 0))
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ed_outrider.toml.example")) as f:
            example = f.read()
        for key in ("surface_alt", "rig_spacing", "surface_map_min", "surface_map_strip", "rig_warn"):
            self.assertIn(f"# {key} = ", example)

    # ---- Batch A of the 2026-10-01 review ----

    def test_out_on_foot_and_back_in_keeps_the_rhino(self):
        """R9: out of the Rhino on foot (the in-SRV flag gone, Flags2 on foot) and back in: still the Rhino, so the
        button marks rigs and the leash watches; boarding the ship ends it."""
        self.launch()
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        self.ev(20, {"event": "Disembark", "SRV": True, "Taxi": False, "Multicrew": False, "ID": 51, "SystemAddress": self.SYS,
                     "Body": self.NAME, "BodyID": self.BODY, "OnPlanet": True})
        self.status(21, 5, 5, flags=0, flags2=1 | 16)
        self.state.watch_surface(self.base + 21)
        self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino")
        self.ev(40, {"event": "Embark", "SRV": True, "Taxi": False, "Multicrew": False, "ID": 51, "SystemAddress": self.SYS,
                     "Body": self.NAME, "BodyID": self.BODY, "OnPlanet": True})
        self.status(41, 0, 0)
        self.state.watch_surface(self.base + 41)
        self.assertTrue(self.state.in_rhino())
        self.status(50, 3600, 0)
        self.state.watch_surface(self.base + 50)
        self.assertEqual(self.texts(("rig_leash",)), ["Rig 1 is 3.6 kilometres away, behind you; it is lost at 5."])
        self.status(70, 3600, 0, flags=(1 << 1) | ed_outrider.FLAG_IN_MAIN_SHIP)   # aboard the ship, landed: not on foot, the SRV is left
        self.state.watch_surface(self.base + 70)
        self.assertIsNone(self.j.vehicle)

    def test_the_rhino_is_kept_while_it_deploys(self):   # found in game 2026-10-03: the button gave the status report
        self.launch()
        for s in (3, 8):   # Status.json written during the deployment, without the SRV flag (still in the ship's bay)
            self.status(s, flags=(1 << 1) | ed_outrider.FLAG_IN_MAIN_SHIP)
            self.state.watch_surface(self.base + s)
            self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino", s)
        self.status(12, flags=1 << 1)                     # not in the SRV, but not said to be in the ship either
        self.state.watch_surface(self.base + 12)
        self.assertEqual(self.j.vehicle["srv_type"], "mev_rhino")
        self.status(15, heading=180)                      # out on the ground: the press marks a rig
        self.state.watch_surface(self.base + 15)
        self.assertTrue(self.state.in_rhino())
        self.state.copilot_gesture("status")
        self.assertEqual(self.texts(), ["Rig 1 placed."])

    def test_rigs_go_with_a_destroyed_rhino_a_death_or_a_relog(self):
        """R10: SRVDestroyed, Died and a relog (LoadGame) take the rigs out with them; one that collected stays a saved
        site; a rig placed after the line (a journal re-read) stays; DockSRV alone keeps them (see the rigs-out call)."""
        self.launch()
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        self.ev(20, {"event": "SRVDestroyed", "ID": 51, "SRVType": "mev_rhino"})
        self.assertEqual(self.out(), {})
        self.launch(30)
        self.status(31, 100, 0, heading=180)
        self.assertEqual(self.state.mark_rig(self.base + 31)["n"], 1)   # the game's HUD numbers it 1 too
        self.status(40, 107, 0)
        self.refine(41, "Gold", 2)
        self.state.journals.end_burst(self.base + 100, force=True)
        self.ev(110, {"event": "Died"})
        self.assertEqual(self.out(), {})
        self.assertEqual([(s["kind"], s["tons"]) for s in self.state.surface_sites(self.SYS, self.BODY)], [("rig", 2)])
        self.ev(200, {"event": "SupercruiseExit", "StarSystem": "S", "SystemAddress": self.SYS, "Body": self.NAME,
                      "BodyID": self.BODY, "BodyType": "Planet"})
        self.launch(210)
        self.status(211, 0, 0)
        self.state.mark_rig(self.base + 211)
        self.ev(220, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})
        self.assertEqual(sorted(self.out()), [1])
        self.j.handle({"event": "LoadGame", "timestamp": self.ts(100), "Commander": "X"})   # an older session, re-read
        self.assertEqual(sorted(self.out()), [1])
        self.ev(300, {"event": "LoadGame", "Commander": "X", "Ship": "Explorer_NX"})
        self.assertEqual(self.out(), {})

    def test_docking_the_rhino_with_rigs_out_says_so(self):
        """S1: a live DockSRV of the Rhino with rigs still marked out on its body: one rigs_out moment naming them and
        the probably full ones (the body from the SRV state, which DockSRV clears); the rigs stay out."""
        self.launch()
        self.status(10, 0, 0, heading=180)
        self.state.mark_rig(self.base + 10)
        self.status(400, 300, 0, heading=180)
        self.state.mark_rig(self.base + 400)
        self.ev(500, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})
        m = [m for m in self.j.moments if m["kind"] == "rigs_out"]
        self.assertEqual([x["text"] for x in m], ["Rigs 1 and 2 still marked out; rig 1 is probably full."])
        self.assertEqual((m[0]["system"], m[0]["body_id"], m[0]["rigs"], m[0]["full"]), (str(self.SYS), self.BODY, [1, 2], [1]))
        self.assertEqual(sorted(self.out()), [1, 2])
        self.assertIsNone(self.j.vehicle)
        self.ev(510, {"event": "Liftoff", "SystemAddress": self.SYS, "BodyID": self.BODY, "PlayerControlled": True})
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "rigs_out"]), 1)   # no repeat on Liftoff
        # one rig: singular
        self.launch(600)
        self.status(601, 307, 0, heading=0)
        self.assertEqual(self.state.mark_rig(self.base + 601)["what"], "picked")   # by rig 2
        self.ev(620, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})
        self.assertEqual(self.texts(("rigs_out",))[-1], "Rig 1 still marked out; it is probably full.")

    def test_rigs_out_is_quiet_without_rigs_for_a_scarab_and_on_a_reread(self):
        self.launch()
        self.ev(20, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})    # nothing out
        self.launch(30, "testbuggy")
        self.status(31, 0, 0)
        self.db.execute("INSERT INTO surface_rigs (system, body_id, n, lat, lon, placed_ts, minerals, tons) "
                        "VALUES (?, ?, 1, 0, 0, ?, '{}', 0)", (self.SYS, self.BODY, self.ts(31)))
        self.ev(40, {"event": "DockSRV", "SRVType": "testbuggy", "ID": 51})     # a Scarab
        self.launch(50)
        self.line += 1
        self.j.line_source = f"Journal.2026-09-30T030000.01.log:{self.line}"
        with unittest.mock.patch.object(ed_outrider.time, "time", lambda: self.base + 3600):
            self.j.handle({"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51, "timestamp": self.ts(60)})   # read an hour later
        self.j.line_source = ""
        self.assertEqual([m for m in self.j.moments if m["kind"] == "rigs_out"], [])
        self.launch(70)
        self.ev(80, {"event": "DockSRV", "SRVType": "mev_rhino", "ID": 51})
        self.assertEqual(self.texts(("rigs_out",)), ["Rig 1 still marked out."])

    def test_the_maps_remove_marks_a_rig_picked_up(self):
        """S1: the legend's ✕ (POST /api/rigs/remove) on a rig picked up without a tap: picked up as a tap would, its
        tons kept as a saved site; a second remove forgets the saved site."""
        self.launch()
        self.status(10, 0, 0, heading=180)
        rid = self.state.mark_rig(self.base + 10)["id"]
        self.status(20, 7, 0)
        self.refine(21, "Water", 3)
        self.state.journals.end_burst(self.base + 100, force=True)
        self.assertTrue(self.state.remove_rig(rid))
        self.assertEqual(self.out(), {})
        self.assertEqual([(s["kind"], s["tons"]) for s in self.state.surface_sites(self.SYS, self.BODY)], [("rig", 3)])
        self.assertTrue(self.state.remove_rig(rid))
        self.assertEqual(self.state.surface_sites(self.SYS, self.BODY), [])
        self.assertFalse(self.state.remove_rig(rid))

    def test_a_dropped_runs_sample_points_go_with_it(self):
        """R17: a new species' Log drops the run in progress, and a death drops the one after it: their points go too,
        and the surface map never shows a species with no run (its raw codex key and ?/3)."""
        def scan(s, kind, species, genus):
            self.ev(s, {"event": "ScanOrganic", "ScanType": kind, "Genus": f"$Codex_Ent_{genus}_Genus_Name;", "Genus_Localised": genus,
                        "Species": species, "Species_Localised": species.strip("$;"), "SystemAddress": self.SYS, "Body": self.BODY})
        self.status(10, 0, 0, flags=0, flags2=1)
        scan(10, "Log", "$Codex_Ent_Stratum_07_Name;", "Stratum")
        self.status(20, 200, 0, flags=0, flags2=1)
        scan(20, "Log", "$Codex_Ent_Bacterial_04_Name;", "Bacterial")
        points = lambda: sorted({r[0] for r in self.db.execute("SELECT species FROM sample_points")})
        self.assertEqual(points(), ["$Codex_Ent_Bacterial_04_Name;"])
        self.db.execute("INSERT INTO sample_points VALUES (?, ?, 'stale', 'g', 1, 0, 0, ?)", (self.SYS, self.BODY, self.ts(5)))
        self.status(30, 0, 0, flags=0, flags2=1)
        h = self.state.surface_here()
        self.assertEqual([b["species"] for b in self.state.surface_bio(h)], ["Codex_Ent_Bacterial_04_Name"])
        self.ev(40, {"event": "Died"})
        self.assertEqual(points(), ["stale"])
        self.assertEqual(self.state.surface_bio(h), [])

    def test_site_tags_keep_their_order_while_you_mine(self):
        """R29: the page numbers U1, U2... in the server's order: mining more at the first site must not move it."""
        order = lambda: [round(s["lon"] * math.pi / 180 * self.R) for s in self.state.surface_sites(self.SYS, self.BODY)]
        self.launch()
        for i, east in enumerate((500, 1000, 1500)):
            self.status(100 * (i + 1), 0, east)
            self.refine(100 * (i + 1) + 1, "Gold", 1)
        self.assertEqual(order(), [500, 1000, 1500])
        self.status(500, 0, 500)
        self.refine(501, "Gold", 2)                       # back at the first: its latest ton is now the newest
        self.assertEqual(order(), [500, 1000, 1500])

    def test_a_stale_first_position_moves_onto_the_rig(self):
        """R31: the tick read the first ton before the Status.json of the Rhino settling over rig 2 (the recorded
        03:38:30/31 readings after the ton): the site that stale reading made moves onto the rig, 6 tons in one."""
        lines = list(RHINO_SESSION)
        i30 = next(i for i, x in enumerate(lines) if x.startswith("S") and "03:38:30Z" in x)
        s30, s31 = lines.pop(i30), lines.pop(i30)
        at = next(i for i, x in enumerate(lines) if "MiningRefined" in x and "03:38:31Z" in x)
        lines[at + 1:at + 1] = [s30, s31]
        said, db = self.replay(lines)
        self.assertEqual(said[-1], "Rig 2: 6 tons of Methanol Monohydrate Crystals.")
        self.assertEqual(db.execute("SELECT count(*) FROM surface_sites").fetchone()[0], 0)
        self.assertEqual({r["n"]: r["tons"] for r in db.execute("SELECT * FROM surface_rigs")}, {1: 10, 2: 20, 3: 0})

    def test_an_unmarked_site_then_a_rig_within_the_minute_stays_two(self):
        """R31's limit: a site mined from a reading of its own moment is kept when you drive on to a rig."""
        self.launch()
        self.status(10, 80, 0, heading=180)
        self.state.mark_rig(self.base + 10)               # rig 1 at 87 m north
        self.status(100, 0, 0)
        self.refine(100, "Water", 3)                      # the reading is from the ton's own second: no rig near
        self.status(103, 87, 0)                           # at the rig 3 s later
        self.refine(103, "Water", 2)
        self.state.watch_surface(self.base + 150)
        self.assertEqual(self.texts()[-2:], ["3 tons of Water. No rig marked here; site saved.", "Rig 1: 2 tons of Water."])

    def test_replay_of_the_rhino_session(self):
        """The author's 30 Sep Rhino run on ABC 3 d (journal and Status.json as recorded), with the presses where the
        recording shows the rigs were placed: rig 1 at 03:10:13, rig 2 at 03:22:59, and at 03:35:21 (rig 2 still out,
        so that press is rig 3). Water 10 from rig 1; Methanol 11 + 3 + 6 from rig 2."""
        said, db = self.replay(RHINO_SESSION)
        self.assertEqual(said, ["Rig 1 placed.", "Rig 1: 10 tons of Water.", "Rig 2 placed.",
                                "Rig 2: 11 tons of Methanol Monohydrate Crystals.",
                                "Rig 2: 3 tons of Methanol Monohydrate Crystals.", "Rig 3 placed.",
                                "Rig 2: 6 tons of Methanol Monohydrate Crystals."])
        j, state = self.replayed
        # S1: the DockSRV at 03:41:31 with rigs 1-3 still marked out (rig 1 was picked up with no press in this
        # replay), and only rig 1 8 minutes past its last collection
        self.assertEqual([m["text"] for m in j.moments if m["kind"] == "rigs_out"],
                         ["Rigs 1, 2 and 3 still marked out; rig 1 is probably full."])
        water = [m for m in j.moments if m.get("what") == "collected"][0]
        self.assertEqual((water["lat"], water["lon"]), (-53.794037, -144.581116))   # where the Water was refined
        rigs = {r["n"]: r for r in db.execute("SELECT * FROM surface_rigs")}
        self.assertEqual({n: (json.loads(r["minerals"]), r["tons"]) for n, r in rigs.items()},
                         {1: ({"Water": 10}, 10), 2: ({"Methanol Monohydrate Crystals": 20}, 20), 3: ({}, 0)})
        self.assertEqual((rigs[1]["site_lat"], rigs[1]["site_lon"]), (-53.794037, -144.581116))
        r = 1204549.875
        self.assertLess(ed_outrider.surface_m(rigs[1]["lat"], rigs[1]["lon"], -53.794037, -144.581116, r), 10)
        self.assertLess(ed_outrider.surface_m(rigs[2]["lat"], rigs[2]["lon"], -53.868797, -144.483139, r), 1)   # 7 m behind: spot on
        self.assertEqual(db.execute("SELECT count(*) FROM surface_sites").fetchone()[0], 0)   # every collection had its rig
        # the journal's own count agrees, ton for ton
        self.assertEqual({x["name"]: x["tons"] for x in db.execute("SELECT * FROM own_mined")},
                         {"Water": 10, "Methanol Monohydrate Crystals": 20})
        self.assertIsNone(j.vehicle)                     # docked
        self.assertFalse(state.in_rhino())

    def replay(self, session):
        """Play a recorded Rhino run ("S " Status.json, "J " journal lines) with the watch loop's ticks in between and
        the presses where the recording shows the rigs were placed. The rig lines said, and the database."""
        presses = {"2026-09-30T03:10:13Z", "2026-09-30T03:22:59Z", "2026-09-30T03:35:21Z"}
        t0 = ed_outrider.ts_seconds("2026-09-30T03:06:00Z")
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        import types
        state = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.replayed = (j, state)
        clock = [t0]
        with unittest.mock.patch.object(ed_outrider.time, "time", lambda: clock[0]):
            for i, line in enumerate(session):
                kind, doc = line[0], json.loads(line[2:])
                t = ed_outrider.ts_seconds(doc["timestamp"])
                while clock[0] < t:              # the watch loop's ticks in between
                    clock[0] += 1
                    state.watch_surface(clock[0])
                if kind == "S":
                    with open(os.path.join(self.dir, "Status.json"), "w") as f:
                        json.dump(doc, f)
                    j.read_status(self.dir)
                    if doc["timestamp"] in presses:
                        state.mark_rig(t)
                else:
                    j.line_source = f"Journal.2026-09-29T223726.01.log:{i}"
                    j.handle(doc)
                    j.line_source = ""
            for _ in range(90):
                clock[0] += 1
                state.watch_surface(clock[0])
        return [m["text"] for m in j.moments if m["kind"] in ("rig", "rig_leash")], db
