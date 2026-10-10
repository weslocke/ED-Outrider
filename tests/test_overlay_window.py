"""Unit tests: the in-game overlay's window, its parts that need no screen (outrider/overlay_window.py: the layout in
window pixels, colours, the client; outrider/overlay_tracking.py: finding Elite's window from wmctrl / xprop /
xwininfo's output). Nothing here opens a window or runs those tools: their output is given. Drawing is checked only
when PyQt6 is installed (into a picture, never on screen).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import io
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

    def test_frames(self):
        self.assertEqual(W.frame_points("chamfer", 100, 50, cut=10), [(10, 0), (100, 0), (100, 40), (90, 50), (0, 50), (0, 10)])
        self.assertIsNone(W.frame_points("rounded", 100, 50))

    def test_wheel(self):
        e = dict(O.LAYOUT_DEFAULT["system"], bg=0.65, alpha=1.0)
        self.assertEqual(W.wheeled(e, "bg", 2)["bg"], 0.75)
        self.assertEqual(W.wheeled(e, "bg", -100)["bg"], 0.0)
        self.assertEqual(W.wheeled(e, "alpha", 3)["alpha"], 1.0)
        self.assertEqual(W.wheeled(e, "alpha", -100)["alpha"], O.LIMITS["alpha"][0])


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


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    """Answers like an Outrider with a password: 401 without the Bearer token, the panels with it."""

    def __init__(self, password="pw"):
        self.password, self.seen = password, []

    def open(self, req, timeout=None):
        self.seen.append((req.get_method(), req.full_url, req.get_header("Authorization")))
        if req.full_url.endswith("/api/auth/signin"):
            ok = json.loads(req.data.decode())["password"] == self.password
            if not ok:
                raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b'{"error": "wrong password"}'))
            return FakeResponse(b'{"token": "tok"}')
        if req.get_header("Authorization") != "Bearer tok":
            raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b'{"error": "signin_required"}'))
        if "since=v1" in req.full_url:
            return FakeResponse(b'{"same": true, "version": "v1"}')
        return FakeResponse(json.dumps({"version": "v1", "panels": [{"id": "system"}], "layout": {}}).encode())


class ClientAndFeed(unittest.TestCase):
    def test_signs_in_on_401(self):
        op = FakeOpener()
        c = W.Client("http://srv:8025/", "pw", opener=op)
        self.assertEqual(c.view()["version"], "v1")
        self.assertEqual([m for m, *_ in op.seen], ["GET", "POST", "GET"])   # refused, signed in, asked again
        self.assertEqual(c.view("v1"), {"same": True, "version": "v1"})
        with self.assertRaises(RuntimeError):
            W.Client("http://srv:8025", "", opener=FakeOpener()).view()   # no password: says what to set

    def test_feed_keeps_the_last_answer_and_drops_it_when_gone(self):
        op = FakeOpener()
        feed = W.Feed(W.Client("http://srv:8025", "pw", opener=op))
        feed.fetch_once()
        self.assertEqual((feed.data["version"], feed.seq), ("v1", 1))
        feed.fetch_once()   # unchanged: the same data, no repaint
        self.assertEqual(feed.seq, 1)

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

    def test_config_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.toml")
            with open(path, "w") as f:
                f.write('[server]\nport = 8100\n')
            self.assertEqual(W.config_target(path), ("http://127.0.0.1:8100", ""))
            with open(path, "w") as f:
                f.write('[overlay]\nurl = "http://192.168.1.81:8025"\npassword = "x"\n')
            self.assertEqual(W.config_target(path), ("http://192.168.1.81:8025", "x"))
            self.assertEqual(W.config_target(os.path.join(tmp, "none.toml")), ("http://127.0.0.1:8025", ""))


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
