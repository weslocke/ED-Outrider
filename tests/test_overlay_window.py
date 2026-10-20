"""Unit tests: the in-game overlay's window, its parts that need no screen (outrider/overlay_window.py: the layout in
window pixels, colours, the client; outrider/overlay_tracking.py: finding Elite's window from wmctrl / xprop /
xwininfo's output). Nothing here opens a window or runs those tools: their output is given. Drawing is checked only
when PyQt6 is installed (into a picture, never on screen).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import io
import http.client
import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the repository root
import outrider.overlay as O  # noqa: E402
import outrider.overlay_tracking as T  # noqa: E402
import outrider.overlay_window as W  # noqa: E402

LOG = logging.getLogger("test-overlay")
LOG.addHandler(logging.NullHandler())
LOG.propagate = False


class LayoutInPixels(unittest.TestCase):
    def test_corners(self):
        e = lambda corner: dict(O.LAYOUT_DEFAULT["system"], corner=corner, x=0.1, y=0.2, scale=1.0)   # noqa: E731
        W_, H_ = 1920, 1080
        s = H_ / O.CANVAS_H
        self.assertEqual(W.panel_rect(e("nw"), 400, 100, W_, H_), (192.0, 216.0, 400 * s, 100 * s))
        x, y, w, h = W.panel_rect(e("se"), 400, 100, W_, H_)
        self.assertAlmostEqual(x + w, W_ - 192)
        self.assertAlmostEqual(y + h, H_ - 216)
        x, y, w, h = W.panel_rect(e("ne"), 400, 100, W_, H_)
        self.assertEqual((round(x + w), round(y)), (W_ - 192, 216))
        # kept inside the window, however far it was put
        x, y, w, h = W.panel_rect(dict(e("nw"), x=0.95, scale=2.5), 400, 100, W_, H_)
        self.assertLessEqual(x + w, W_ + 1e-6)

    def test_centred(self):
        e = dict(O.LAYOUT_DEFAULT["strip"], y=0.01)
        x, y, w, h = W.panel_rect(e, 800, 40, 1920, 1080)
        self.assertAlmostEqual(x + w / 2, 960)                                          # centred, whatever x says
        self.assertAlmostEqual(y, 10.8)
        x, y, w, h = W.panel_rect(dict(e, corner="s"), 800, 40, 2560, 1440)
        self.assertAlmostEqual((x + w / 2, y + h), (1280, 1440 - 14.4))
        self.assertEqual(W.place(960 - 400 + 30, 20, 800, 40, 1920, 1080)["corner"], "n")   # dropped about the middle
        self.assertEqual(W.place(960 - 400 + 30, 1000, 800, 40, 1920, 1080)["corner"], "s")
        self.assertEqual(W.place(100, 20, 800, 40, 1920, 1080)["corner"], "nw")             # well off it: a corner

    def test_place_is_the_inverse(self):
        """A panel dropped somewhere is stored from its nearest corner, and put back exactly there."""
        W_, H_ = 2560, 1440
        for (x, y) in ((50, 60), (2000, 80), (100, 1200), (2100, 1250)):
            w, h = 300, 150
            got = W.place(x, y, w, h, W_, H_)
            entry = dict(O.LAYOUT_DEFAULT["system"], **got, scale=w / (300 * W.base_scale(H_)))
            rx, ry, rw, rh = W.panel_rect(entry, 300, 150, W_, H_)
            self.assertAlmostEqual(rx, x, delta=1)
            self.assertAlmostEqual(ry, y, delta=1)
        self.assertEqual(W.place(2100, 1250, 300, 150, W_, H_)["corner"], "se")
        self.assertEqual(W.place(50, 1250, 300, 150, W_, H_)["corner"], "sw")
        # the same share of a smaller window keeps it against the same corner
        small = W.panel_rect(dict(O.LAYOUT_DEFAULT["system"], **W.place(2100, 1250, 300, 150, W_, H_)), 300, 150, 1280, 720)
        self.assertGreater(small[0], 640)

    def test_colours_and_screens(self):
        self.assertEqual(W.rgba("#FF8000"), (255, 128, 0, 255))
        self.assertEqual(W.rgba("#80FF8000"), (255, 128, 0, 128))
        self.assertEqual(W.rgba("#FF8000", 0.5), (255, 128, 0, 128))
        self.assertEqual(W.rgba("nonsense"), (128, 128, 128, 255))
        a = T.ScreenInfo("a", (0, 0, 1920, 1080), (0, 0, 1920, 1080), 1.0)
        b = T.ScreenInfo("b", (1920, 0, 1280, 720), (3840, 0, 2560, 1440), 2.0)
        self.assertIs(W.screen_for([a, b], 4000, 500), b)
        self.assertIs(W.screen_for([a, b], -50, -50), a)
        self.assertIsNone(W.screen_for([], 0, 0))


class Arranging(unittest.TestCase):
    """Arrange mode's maths: which panel a press is on, what a drag or the wheel makes of its layout."""

    def test_hit(self):
        geoms = [("system", (10, 10, 200, 100)), ("body", (150, 50, 200, 100))]
        self.assertEqual(W.hit(geoms, 20, 20), ("system", "move"))
        self.assertEqual(W.hit(geoms, 160, 60), ("body", "move"))                     # the one drawn last is on top
        self.assertEqual(W.hit(geoms, 345, 145), ("body", "resize"))                  # its corner handle
        self.assertIsNone(W.hit(geoms, 500, 500))
        x, y, w, h = W.done_rect(1920)
        self.assertTrue(W.inside((x, y, w, h), 960, y + 5))

    def test_drag_moves_and_keeps_inside(self):
        e = dict(O.LAYOUT_DEFAULT["system"])
        start = W.panel_rect(e, 400, 100, 1920, 1080)
        moved = W.dragged(e, start, 1300, 800, "move", 400, 100, 1920, 1080)
        self.assertEqual(moved["corner"], "se")                                     # dropped bottom right: kept from there
        x, y, w, h = W.panel_rect(moved, 400, 100, 1920, 1080)
        self.assertAlmostEqual(x, start[0] + 1300, delta=1)
        far = W.dragged(e, start, 99999, 99999, "move", 400, 100, 1920, 1080)
        x, y, w, h = W.panel_rect(far, 400, 100, 1920, 1080)
        self.assertLessEqual(x + w, 1920 + 1e-6)
        self.assertLessEqual(y + h, 1080 + 1e-6)

    def test_drag_corner_sizes(self):
        e = dict(O.LAYOUT_DEFAULT["system"])
        start = W.panel_rect(e, 400, 100, 1920, 1080)
        bigger = W.dragged(e, start, start[2] / 2, 0, "resize", 400, 100, 1920, 1080)
        self.assertAlmostEqual(bigger["scale"], 1.5, places=3)
        x, y, w, h = W.panel_rect(bigger, 400, 100, 1920, 1080)
        self.assertAlmostEqual((x, y), start[:2], delta=1)                         # its top left stays put
        self.assertEqual(W.dragged(e, start, 99999, 0, "resize", 400, 100, 1920, 1080)["scale"], O.LIMITS["scale"][1])
        self.assertEqual(W.dragged(e, start, -99999, 0, "resize", 400, 100, 1920, 1080)["scale"], O.LIMITS["scale"][0])

    def test_when_it_shows(self):
        """Over the game while it is in front; Arrange mode and the test panels whatever is in front (pressed from the
        page, the game is behind it: they showed only once you were back in the game, the author, 2026-10-10)."""
        front = T.WindowState(0, 0, 1920, 1080, True, True)
        behind = T.WindowState(0, 0, 1920, 1080, False, True)
        self.assertTrue(W.should_show(front, {}))
        self.assertFalse(W.should_show(behind, {}))
        self.assertTrue(W.should_show(behind, {"test": True}))
        self.assertTrue(W.should_show(behind, {"arrange": True}))
        self.assertTrue(W.should_show(behind, {}, active=True))
        self.assertFalse(W.should_show(None, {"test": True}))                       # no game window: nowhere to draw
        self.assertFalse(W.should_show(T.WindowState(0, 0, 0, 0, True, False), {"test": True}))   # minimised

    def test_keep_showing_when_not_active(self):
        """S25: with show_inactive the overlay stays over the game while another window is in front, unless other
        windows cover the game (S25b) or it is minimised / on another desktop (not visible)."""
        behind = T.WindowState(0, 0, 1920, 1080, False, True)
        covered = T.WindowState(0, 0, 1920, 1080, False, True, covered=True)
        hidden = T.WindowState(0, 0, 1920, 1080, False, False)
        self.assertTrue(W.should_show(behind, {"show_inactive": True}))
        self.assertFalse(W.should_show(behind, {"show_inactive": False}))
        self.assertFalse(W.should_show(covered, {"show_inactive": True}))
        self.assertFalse(W.should_show(hidden, {"show_inactive": True}))
        self.assertTrue(W.should_show(covered, {"show_inactive": True, "test": True}))   # the test panels: whatever is in front

    def test_track_code(self):
        """S8: what the window sees, sent with its GET for the page's overlay pill."""
        class Tr:
            missing = xprop_missing = False
        tr, front = Tr(), T.WindowState(0, 0, 10, 10, True, True)
        self.assertEqual(W.track_code(None, None, False), "no_tracker")
        self.assertEqual(W.track_code(tr, None, False), "no_window")
        self.assertEqual(W.track_code(tr, front, True), "drawing")
        self.assertEqual(W.track_code(tr, T.WindowState(0, 0, 10, 10, False, True), False), "behind")
        self.assertEqual(W.track_code(tr, T.WindowState(0, 0, 10, 10, False, False), False), "hidden")
        self.assertEqual(W.track_code(tr, T.WindowState(0, 0, 10, 10, False, True, covered=True), False), "covered")
        tr.xprop_missing = True
        self.assertEqual(W.track_code(tr, front, False), "no_xprop")
        tr.missing = True
        self.assertEqual(W.track_code(tr, None, False), "no_wmctrl")
        self.assertTrue(set(O.TRACK_CODES) >= {"drawing", "behind", "hidden", "covered", "no_window", "no_wmctrl",
                                               "no_xprop", "no_tracker"})

    def test_windows_click_through_both_ways(self):
        """On Windows the click-through style is taken away for Arrange mode as well as added (it was only added)."""
        through = W.win_exstyle(0x100, True)
        self.assertEqual(through, 0x100 | W.WS_EX_LAYERED | W.WS_EX_TRANSPARENT)
        self.assertEqual(W.win_exstyle(through, False), 0x100 | W.WS_EX_LAYERED)   # takes the mouse; layered stays

    def test_frames(self):
        self.assertEqual(W.frame_points("chamfer", 100, 50, cut=10), [(10, 0), (100, 0), (100, 40), (90, 50), (0, 50), (0, 10)])
        self.assertIsNone(W.frame_points("rounded", 100, 50))

    def test_wheel(self):
        e = dict(O.LAYOUT_DEFAULT["system"], bg=0.65, alpha=1.0)
        self.assertEqual(W.wheeled(e, "bg", 2)["bg"], 0.75)
        self.assertEqual(W.wheeled(e, "bg", -100)["bg"], 0.0)
        self.assertEqual(W.wheeled(e, "alpha", 3)["alpha"], 1.0)
        self.assertEqual(W.wheeled(e, "alpha", -100)["alpha"], O.LIMITS["alpha"][0])

    def test_wheel_for_all_panels(self):
        """The 4K TV report (2026-10-14): Ctrl + wheel over any panel sizes all of them ([overlay] panel_scale, in 5 %
        notches within PANEL_SCALE_LIMITS); the wheel alone and with Shift keep their opacities."""
        self.assertEqual([W.wheel_key(False, False), W.wheel_key(True, False), W.wheel_key(False, True),
                          W.wheel_key(True, True)], ["bg", "alpha", "all", "all"])
        self.assertEqual(W.wheeled_all(100, -2), 90)
        self.assertEqual(W.wheeled_all(100, 1.5), 108)                               # a smooth wheel: whole percents
        self.assertEqual((W.wheeled_all(30, -9), W.wheeled_all(240, 9)), O.PANEL_SCALE_LIMITS)
        self.assertEqual((W.panel_scale_of({"panel_scale": 50}), W.panel_scale_of({"panel_scale": 50}, 80),
                          W.panel_scale_of({}), W.panel_scale_of(None), W.panel_scale_of({"panel_scale": "big"})),
                         (0.5, 0.8, 1.0, 1.0, 1.0))

    def test_drag_corner_with_all_panels_and_the_floor(self):
        """Sizing a panel draws it as paint does: times all panels' size, and never under the text floor."""
        e = dict(O.LAYOUT_DEFAULT["system"])
        s = O.effective_scale(2160, 0.5, 1.0, O.FONT_PX["normal"])
        start = W.panel_rect(e, 400, 100, 3840, 2160, s)
        self.assertAlmostEqual(start[2], 400 * 2.25 * 0.5)
        bigger = W.dragged(e, start, start[2] / 2, 0, "resize", 400, 100, 3840, 2160, 0.5, O.FONT_PX["normal"])
        x, y, w, h = W.panel_rect(bigger, 400, 100, 3840, 2160, O.effective_scale(2160, 0.5, bigger["scale"], O.FONT_PX["normal"]))
        self.assertAlmostEqual((bigger["scale"], x, y, w), (1.5, start[0], start[1], start[2] * 1.5), places=3)
        # far smaller on a 1080p window: the scale goes to its least, the panel stays at the text floor's size
        tiny = W.dragged(e, start, -99999, 0, "resize", 400, 100, 1920, 1080, 0.5, O.FONT_PX["small"])
        self.assertEqual(tiny["scale"], O.LIMITS["scale"][0])


class GameMouseLock(unittest.TestCase):
    """#1: on Linux a window per panel, each only as big as its panel, and none when there is nothing to draw (the game's
    pointer lock is refused while a window lies over it). Pure parts; the windows themselves are checked in game."""

    def test_linux_only(self):
        self.assertEqual(W.FIT_WINDOW, sys.platform.startswith("linux"))

    def test_window_rect(self):
        """The panels' bounding box, each grown by PANEL_PAD, inside the game window, whole pixels; one corner pixel
        when none is drawn (or none lies inside)."""
        geoms = [("radar", (1500.4, 800.0, 300.0, 200.0)), ("strip", (100.0, 0.0, 1700.0, 30.0))]
        self.assertEqual(W.window_rect(geoms, 1920, 1080, pad=6), (94, 0, 1713, 1006))
        self.assertEqual(W.window_rect(geoms[:1], 1920, 1080, pad=6), (1494, 794, 313, 212))
        self.assertEqual(W.window_rect([("now", (1900.0, 1070.0, 50.0, 50.0))], 1920, 1080, pad=6), (1894, 1064, 26, 16))
        self.assertEqual(W.window_rect([], 1920, 1080), (0, 0, 1, 1))
        self.assertEqual(W.window_rect([("x", (2000.0, 10.0, 50.0, 50.0))], 1920, 1080), (0, 0, 1, 1))

    def test_window_plan(self):
        """No window out of sight or with nothing to draw; one over the whole game in Arrange mode (it takes the mouse)
        or where not FIT_WINDOW; else one per panel, in the feed's order."""
        two = {"panels": [{"id": "radar"}, {"id": "strip"}]}
        self.assertEqual(W.window_plan(two, True, False, fit=True), ("panels", ["radar", "strip"]))
        self.assertEqual(W.window_plan(two, True, False, fit=False), ("all", []))
        self.assertEqual(W.window_plan(two, True, True, fit=True), ("all", []))
        self.assertEqual(W.window_plan({"panels": []}, True, True, fit=True), ("all", []))   # arranging: the frames and Done
        self.assertEqual(W.window_plan(two, False, False, fit=True), ("none", []))
        for empty in ({"panels": []}, None, {}):
            for fit in (True, False):
                self.assertEqual(W.window_plan(empty, True, False, fit=fit), ("none", []))


class Tracking(unittest.TestCase):
    WMCTRL = ("0x04400003  0 0    0    2560 1440 steam_app_359320.steam_app_359320  pc Elite - Dangerous (CLIENT)\n"
              "0x03000007  0 100  100  800  600  firefox.Firefox  pc Elite - Dangerous wiki - Mozilla Firefox\n"
              "0x02a00001  0 0    0    300  200  gnome-terminal  pc Terminal\n")

    def fake_run(self, active="0x04400003", wmctrl=None, missing=False):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd[0])
            if missing and cmd[0] == "wmctrl":
                raise FileNotFoundError("wmctrl")
            out = {"wmctrl": wmctrl if wmctrl is not None else self.WMCTRL,
                   "xprop": f"_NET_ACTIVE_WINDOW(WINDOW): window id # {active}\n",
                   "xwininfo": "  Absolute upper-left X:  0\n  Absolute upper-left Y:  0\n  Width: 2560\n  Height: 1440\n"}[cmd[0]]
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        run.calls = calls
        return run

    def test_finds_the_game_in_front(self):
        t = T.X11Tracker(LOG, run=self.fake_run())
        st = t.poll()
        self.assertEqual((st.x, st.y, st.width, st.height, st.is_foreground, st.identifier),
                         (0, 0, 2560, 1440, True, "0x04400003"))

    def test_not_in_front_and_not_there(self):
        st = T.X11Tracker(LOG, run=self.fake_run(active="0x02a00001")).poll()
        self.assertFalse(st.is_foreground)   # the largest Elite window, behind the terminal
        self.assertEqual(st.identifier, "0x04400003")
        self.assertIsNone(T.X11Tracker(LOG, run=self.fake_run(wmctrl="0x1 0 0 0 10 10 x pc Terminal\n")).poll())
        t = T.X11Tracker(LOG, run=self.fake_run(missing=True))
        self.assertIsNone(t.poll())
        self.assertTrue(t.missing)

    def test_monitors_give_global_coordinates(self):
        t = T.X11Tracker(LOG, monitor_provider=lambda: [("DP-1", 0, 0, 2560, 1440)], run=self.fake_run())
        st = t.poll()
        self.assertEqual((st.global_x, st.global_y), (0, 0))

    def test_title_match(self):
        self.assertTrue(T.matches_window_title("Elite - Dangerous (CLIENT)"))
        self.assertTrue(T.matches_window_title("elite-dangerous"))
        self.assertFalse(T.matches_window_title("Elite Dangerous Odyssey trailer - YouTube - firefox"))
        self.assertFalse(T.matches_window_title(""))

    def test_scaled_desktop_and_title_bar(self):
        info = T.ScreenInfo("hidpi", (0, 0, 1280, 720), (0, 0, 2560, 1440), 2.0)
        self.assertEqual(T.native_rect_to_qt((0, 0, 2560, 1440), info), (0, 0, 1280, 720))
        self.assertEqual(T.native_rect_to_qt((10, 20, 30, 40), None), (10, 20, 30, 40))
        self.assertEqual(T.title_bar_offset((0, 0, 1920, 1080), 30), (0, 30, 1920, 1050))
        self.assertEqual(T.title_bar_offset((0, 0, 1920, 1080), 0), (0, 0, 1920, 1080))

    def test_factory(self):
        self.assertIsInstance(T.create_tracker(LOG, platform="linux"), T.X11Tracker)
        self.assertIsNone(T.create_tracker(LOG, platform="darwin"))

    def test_xprop_missing(self):
        """Without xprop the game could never be in front (the overlay never shows): said, for the pill (S8)."""
        def run(cmd, **kw):
            if cmd[0] == "xprop":
                raise FileNotFoundError("xprop")
            return subprocess.CompletedProcess(cmd, 0, stdout=self.WMCTRL, stderr="")
        t = T.X11Tracker(LOG, run=run)
        self.assertFalse(t.poll().is_foreground)
        self.assertTrue(t.xprop_missing)


class Desktop:
    """An X desktop's answers to wmctrl and xprop for the out-of-sight and covered checks (S25, S25b): windows
    [(id, desktop, x, y, w, h, title)], the active one, the stacking order (bottom to top), minimised ids, the current
    desktop, and xwininfo's map state for every window (None: no Map State line, as when it cannot be read). Records
    every command."""
    GAME, BROWSER, CHAT = 0x04400003, 0x03000007, 0x02a00001

    def __init__(self, windows, active, stacking, minimised=(), current=0, map_state=None):
        self.windows, self.active, self.stacking = windows, active, stacking
        self.minimised, self.current, self.calls = set(minimised), current, []
        self.map_state = map_state

    def run(self, cmd, **kw):
        self.calls.append(list(cmd))
        if cmd[0] == "wmctrl":
            out = "".join(f"0x{i:08x}  {d} {x} {y} {w} {h} cls pc {t}\n" for i, d, x, y, w, h, t in self.windows)
        elif cmd[:2] == ["xprop", "-root"]:
            out = {"_NET_ACTIVE_WINDOW": f"_NET_ACTIVE_WINDOW(WINDOW): window id # 0x{self.active:x}\n",
                   "_NET_CURRENT_DESKTOP": f"_NET_CURRENT_DESKTOP(CARDINAL) = {self.current}\n",
                   "_NET_CLIENT_LIST_STACKING": "_NET_CLIENT_LIST_STACKING(WINDOW): window id # " +
                                                ", ".join(f"0x{i:x}" for i in self.stacking) + "\n"}[cmd[2]]
        elif cmd[:2] == ["xprop", "-id"]:
            hidden = int(cmd[2], 16) in self.minimised
            out = "_NET_WM_STATE(ATOM) = " + ("_NET_WM_STATE_HIDDEN" if hidden else "_NET_WM_STATE_MAXIMIZED_VERT") + "\n"
        elif cmd[0] == "xwininfo" and self.map_state:
            out = f"  Width: 2560\n  Height: 1440\n  Map State: {self.map_state}\n"
        else:
            out = ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    def poll(self, checks=True):
        t = T.X11Tracker(LOG, run=self.run, min_interval=0)
        t.inactive_checks = checks
        return t.poll()


class OutOfSight(unittest.TestCase):
    D = Desktop
    GAME = (D.GAME, 0, 0, 0, 2560, 1440, "Elite - Dangerous (CLIENT)")

    def test_covered_share(self):
        self.assertEqual(T.covered_share((0, 0, 100, 100), []), 0.0)
        self.assertEqual(T.covered_share((0, 0, 100, 100), [(0, 0, 100, 100)]), 1.0)
        self.assertEqual(T.covered_share((0, 0, 100, 100), [(50, 0, 100, 100), (0, 50, 100, 100)]), 0.75)   # overlap once
        self.assertEqual(T.covered_share((0, 0, 100, 100), [(200, 200, 50, 50)]), 0.0)
        self.assertEqual(T.covered_share((0, 0, 0, 0), [(0, 0, 10, 10)]), 0.0)

    def test_a_window_over_the_game(self):
        d = self.D([self.GAME, (self.D.BROWSER, 0, 0, 0, 1920, 1080, "Mozilla Firefox")], self.D.BROWSER, [self.D.GAME, self.D.BROWSER])
        st = d.poll()
        self.assertEqual((st.is_foreground, st.is_visible, st.covered), (False, True, True))   # 56% of it
        # the same browser beneath the game in the stacking order (a second screen's window last clicked): not covering
        d.stacking = [self.D.BROWSER, self.D.GAME]
        self.assertFalse(d.poll().covered)
        # a small window over it (a chat in a corner, under a quarter): the overlay stays
        d = self.D([self.GAME, (self.D.CHAT, 0, 0, 0, 600, 800, "Chat")], self.D.CHAT, [self.D.GAME, self.D.CHAT])
        self.assertFalse(d.poll().covered)
        # minimised, or on another desktop: no cover
        d = self.D([self.GAME, (self.D.BROWSER, 0, 0, 0, 2560, 1440, "Mozilla Firefox")], self.D.BROWSER,
                   [self.D.GAME, self.D.BROWSER], minimised=[self.D.BROWSER])
        self.assertFalse(d.poll().covered)
        d = self.D([self.GAME, (self.D.BROWSER, 1, 0, 0, 2560, 1440, "Mozilla Firefox")], self.D.BROWSER, [self.D.GAME, self.D.BROWSER])
        self.assertFalse(d.poll().covered)

    def test_the_game_out_of_sight(self):
        d = self.D([self.GAME], self.D.CHAT, [self.D.GAME], minimised=[self.D.GAME])
        self.assertFalse(d.poll().is_visible)                         # minimised
        d = self.D([(self.D.GAME, 1, 0, 0, 2560, 1440, "Elite - Dangerous (CLIENT)")], self.D.CHAT, [self.D.GAME], current=0)
        self.assertFalse(d.poll().is_visible)                         # on another desktop
        d.current = 1
        self.assertTrue(d.poll().is_visible)

    def test_one_workspace_per_monitor(self):
        """A window manager with a workspace per monitor (i3 and the like): the browser clicked on the second monitor
        makes its workspace the current desktop while the game stays in sight on the first. The map state decides:
        viewable stays shown; unmapped (a workspace not on any monitor, as GNOME and KDE unmap) is hidden."""
        d = self.D([(self.D.GAME, 1, 0, 0, 2560, 1440, "Elite - Dangerous (CLIENT)"),
                    (self.D.BROWSER, 2, 2560, 0, 1920, 1080, "Mozilla Firefox")], self.D.BROWSER,
                   [self.D.GAME, self.D.BROWSER], current=2, map_state="IsViewable")
        self.assertTrue(d.poll().is_visible)
        d.map_state = "IsUnMapped"
        self.assertFalse(d.poll().is_visible)
        d.map_state = "IsUnviewable"
        self.assertFalse(d.poll().is_visible)
        d.map_state, d.current = "IsUnMapped", 1   # the desktop's own: the map state is not asked
        d.calls.clear()
        self.assertTrue(d.poll().is_visible)
        self.assertNotIn("xwininfo", [c[0] for c in d.calls if c[1:2] == ["-id"]])

    def test_only_when_asked(self):
        """The extra xprop calls run only with inactive_checks on and the game not in front."""
        d = self.D([self.GAME, (self.D.BROWSER, 0, 0, 0, 2560, 1440, "Mozilla Firefox")], self.D.BROWSER, [self.D.GAME, self.D.BROWSER])
        st = d.poll(checks=False)
        self.assertEqual((st.covered, [c[2] for c in d.calls if c[0] == "xprop"]), (False, ["_NET_ACTIVE_WINDOW"]))
        d.calls.clear()
        d.active = self.D.GAME
        st = d.poll()
        self.assertEqual((st.is_foreground, st.covered, [c[2] for c in d.calls if c[0] == "xprop"]), (True, False, ["_NET_ACTIVE_WINDOW"]))

    def test_kept_a_while(self):
        """The answer is kept INACTIVE_EVERY_S: a poll twice a second does not ask xprop four more times each."""
        d = self.D([self.GAME, (self.D.BROWSER, 0, 0, 0, 2560, 1440, "Mozilla Firefox")], self.D.BROWSER, [self.D.GAME, self.D.BROWSER])
        t = T.X11Tracker(LOG, run=d.run, min_interval=0)
        t.inactive_checks = True
        t.poll()
        n = len(d.calls)
        t.poll()
        self.assertEqual(len(d.calls) - n, 2)   # wmctrl and the active window only

    def test_windows_z_order(self):
        """S25b on Windows: the windows above the game that can hide it (a fake user32: never Windows itself)."""
        class R:
            def __init__(self, l, t, r, b):
                self.left, self.top, self.right, self.bottom = l, t, r, b
        # z-order, top first: a click-through overlay, a tool window, a minimised one, ours, a cloaked one, a browser
        wins = {1: dict(ex=0x20), 2: dict(ex=0x80), 3: dict(iconic=True), 4: dict(pid=99), 5: dict(cloaked=True),
                6: dict(), 7: dict(game=True)}
        order = [1, 2, 3, 4, 5, 6, 7]

        class U32:
            def GetWindow(self, h, how):
                assert how == T.GW_HWNDPREV
                i = order.index(h)
                return order[i - 1] if i > 0 else 0

            def IsWindowVisible(self, h):
                return True

            def IsIconic(self, h):
                return wins[h].get("iconic", False)

            def GetWindowLongW(self, h, idx):
                return wins[h].get("ex", 0)

            def GetWindowThreadProcessId(self, h, ref):
                ref._obj.value = wins[h].get("pid", 5)
                return 1
        got = T.win_rects_above(U32(), 7, lambda h: R(0, 0, 1920 + h, 1080), lambda h: wins[h].get("cloaked", False), 99)
        self.assertEqual(got, [(0, 0, 1926, 1080)])   # the browser alone


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    """Answers like this PC's Outrider: the panels, or {same} when nothing changed."""

    def __init__(self):
        self.seen = []

    def open(self, req, timeout=None):
        self.seen.append((req.get_method(), req.full_url, req.get_header("User-agent")))
        if "since=v1" in req.full_url:
            return FakeResponse(b'{"same": true, "version": "v1"}')
        return FakeResponse(json.dumps({"version": "v1", "panels": [{"id": "system"}], "layout": {}}).encode())


class ClientAndFeed(unittest.TestCase):
    def test_client(self):
        op = FakeOpener()
        c = W.Client("http://127.0.0.1:8025/", opener=op)
        self.assertEqual(c.view()["version"], "v1")
        self.assertEqual(c.view("v1"), {"same": True, "version": "v1"})
        self.assertEqual(op.seen[0], ("GET", "http://127.0.0.1:8025/api/overlay", "outrider-overlay"))   # the window's own UA
        c.view("v1", "behind")
        c.view(None, "no_window")
        c.view("v1", "drawing", 2160)   # the game window's height: Settings' "≈ N px text"
        self.assertEqual([u for _, u, _ in op.seen[2:]], ["http://127.0.0.1:8025/api/overlay?since=v1&w=behind",
                                                          "http://127.0.0.1:8025/api/overlay?w=no_window",
                                                          "http://127.0.0.1:8025/api/overlay?since=v1&w=drawing&h=2160"])

    def test_feed_keeps_the_last_answer_and_drops_it_when_gone(self):
        op = FakeOpener()
        feed = W.Feed(W.Client("http://127.0.0.1:8025", opener=op))
        feed.fetch_once()
        self.assertEqual((feed.data["version"], feed.seq), ("v1", 1))
        feed.fetch_once()   # unchanged: the same data, no repaint
        self.assertEqual(feed.seq, 1)
        feed.track = "covered"   # what the window sees goes with the next GET (S8)
        feed.fetch_once()
        self.assertTrue(op.seen[-1][1].endswith("?since=v1&w=covered"))
        feed.height = 1440
        feed.fetch_once()
        self.assertTrue(op.seen[-1][1].endswith("?since=v1&w=covered&h=1440"))

        class Gone:
            def open(self, req, timeout=None):
                raise urllib.error.URLError("connection refused")
        feed.client.opener = Gone()
        logging.getLogger("outrider.overlay_window").disabled = True
        try:
            feed.fetch_once()
        finally:
            logging.getLogger("outrider.overlay_window").disabled = False
        self.assertIsNone(feed.data)   # nothing stale stays on screen
        self.assertEqual(feed.seq, 2)
        self.assertIn("connection refused", feed.error)

        # Outrider killed while answering: the cut-off body is an http.client error, not an OSError; the feed thread
        # must live on and drop the panels (review 2026-10-11)
        feed.client.opener = op
        feed.fetch_once()
        self.assertEqual(feed.seq, 3)

        class Cut:
            def open(self, req, timeout=None):
                raise http.client.IncompleteRead(b"{")
        feed.client.opener = Cut()
        logging.getLogger("outrider.overlay_window").disabled = True
        try:
            feed.fetch_once()
        finally:
            logging.getLogger("outrider.overlay_window").disabled = False
        self.assertEqual((feed.data, feed.seq), (None, 4))
        self.assertIsNotNone(feed.error)

    def test_feed_drops_the_panels_on_an_error_answer(self):
        """Review 2026-10-20 M8: a JSON error answer (a panel builder raising: json_errors' 500) neither cleared the
        panels nor set the error, so the last system stayed drawn after you jumped on, and nothing was logged."""
        import io
        op = FakeOpener()
        feed = W.Feed(W.Client("http://127.0.0.1:8025", opener=op))
        feed.fetch_once()
        self.assertEqual(feed.seq, 1)

        class Failing:
            def open(self, req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {},
                                             io.BytesIO(b'{"error": "KeyError: x", "code": "server_error"}'))
        feed.client.opener = Failing()
        logging.getLogger("outrider.overlay_window").disabled = True
        try:
            feed.fetch_once()
        finally:
            logging.getLogger("outrider.overlay_window").disabled = False
        self.assertEqual((feed.data, feed.seq, feed.error), (None, 2, "KeyError: x"))
        feed.client.opener = op
        feed.fetch_once()
        self.assertEqual((feed.data["version"], feed.seq, feed.error), ("v1", 3, None))   # back once it answers

    def test_config_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.toml")
            with open(path, "w") as f:
                f.write('[server]\nport = 8100\n')
            self.assertEqual(W.config_url(path), "http://127.0.0.1:8100")
            self.assertEqual(W.config_url(os.path.join(tmp, "none.toml")), "http://127.0.0.1:8025")


class Drawing(unittest.TestCase):
    """Into a picture with Qt's offscreen platform, only where PyQt6 is installed (it is not in the test venv)."""

    def test_render(self):
        import importlib.util
        if importlib.util.find_spec("PyQt6") is None:
            self.skipTest("PyQt6 not installed (pip install -r requirements-overlay.txt)")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtGui import QImage
        data = {"layout": O.clean_layout(None), "panels": O.test_panels(O.palette())}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "frame.png")
            self.assertTrue(W.render_png(data, path, 1280, 720, arrange=True))
            img = QImage(path)
            self.assertEqual((img.width(), img.height()), (1280, 720))
            # the system panel's background is drawn at its top-left place, not the stand-in's colour
            x, y, w, h = W.panel_rect(data["layout"]["system"], data["panels"][0]["w"], data["panels"][0]["h"], 1280, 720)
            self.assertNotEqual(img.pixelColor(int(x + 4), int(y + h / 2)).name(), "#14181e")

    def test_text_floor_on_a_4k_window(self):
        """The 4K TV report (2026-10-14): a 4K window with all panels at 25 % draws every panel smaller than at 100 %,
        yet no text under MIN_TEXT_PX: each panel's scale times its smallest font is at least the floor, the small-text
        radar held exactly there, and its background is drawn as big as the floor makes it."""
        import importlib.util
        if importlib.util.find_spec("PyQt6") is None:
            self.skipTest("PyQt6 not installed (pip install -r requirements-overlay.txt)")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtGui import QColor, QImage, QPainter
        W_, H_ = 3840, 2160
        panels = O.test_panels(O.palette(), "small")
        data = {"layout": O.clean_layout(None), "panels": panels, "panel_scale": 25}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "frame.png")
            self.assertTrue(W.render_png(data, path, W_, H_))   # the whole frame draws
            img = QImage(W_, H_, QImage.Format.Format_ARGB32)
            img.fill(QColor(20, 24, 30))
            painter = QPainter(img)
            try:
                geoms = dict(W.paint(painter, data, W_, H_))
            finally:
                painter.end()
        for p in panels:
            x, y, w, h = geoms[p["id"]]
            drawn = w / p["w"]                                         # canvas units to pixels, as painted
            self.assertGreaterEqual(drawn * O.smallest_font(p), O.MIN_TEXT_PX - 1e-6, p["id"])
            self.assertLess(drawn, W.base_scale(H_), p["id"])          # yet smaller than at 100 %
            self.assertAlmostEqual(drawn, O.MIN_TEXT_PX / O.FONT_PX["small"], places=6)   # 2.25 x 0.25 is under it
            self.assertNotEqual(img.pixelColor(int(x + 4), int(y + h - 4)).name(), "#14181e", p["id"])   # filled to there
