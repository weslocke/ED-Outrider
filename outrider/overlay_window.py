"""The in-game overlay's window, run on the game PC beside Elite (borderless or windowed):

    python3 -m outrider.overlay_window                     (this PC's Outrider: [overlay] url/password, else [server] port)
    python3 -m outrider.overlay_window --url http://192.168.1.81:8025 --password ...   (an Outrider on a server)
    python3 -m outrider.overlay_window --render frame.png  (draw one frame into a picture and stop: nothing on screen)

It asks Outrider for the panels (GET /api/overlay, about once a second) and paints them over Elite's window: a
frameless, translucent, always-on-top window that lets every click through to the game, follows Elite's window and
hides when the game is not in front. Needs PyQt6 (pip install -r requirements-overlay.txt; never in the Docker
image: the window runs on the game PC and can point at a server). On Linux it finds Elite's window with wmctrl, xprop
and xwininfo; on a Wayland session it runs through XWayland, as Elite under Proton does.

The window's flags and the Windows click-through call are adapted from EDMC Modern Overlay
(https://github.com/SweetJonnySauce/EDMCModernOverlay, overlay_client/setup_surface.py and
overlay_client/platform_integration.py at commit c78df18, release 0.9.2), copyright its authors, GNU GPL version 3;
changed for ED Outrider on 2026-10-10 (only those flags and that call; the rest of this file is ED Outrider's own).
Finding the game's window: outrider/overlay_tracking.py.

The layout maths, the colours and the HTTP client are plain Python (tested without Qt); everything Qt is inside
run_window() and paint().
"""
import argparse
import json
import logging
import os
import sys
import threading
import urllib.error
import urllib.request

from . import overlay as O

POLL_S = 1.0           # how often the window asks Outrider for the panels
FOLLOW_MS = 500        # how often it looks where Elite's window is
HTTP_TIMEOUT = 5
FONT_PX = {"small": 12, "normal": 15, "large": 19}   # text sizes in canvas units (scaled with the panel)
RADIUS = 6             # the panels' corner rounding in canvas units

log = logging.getLogger("outrider.overlay_window")


# ---- the layout, in window pixels (pure) ----

def base_scale(win_h):
    """Canvas units to window pixels: the 960-unit-high canvas fits the game window's height."""
    return max(0.1, win_h / O.CANVAS_H)


def panel_rect(entry, pw, ph, win_w, win_h):
    """Where a panel goes in a game window of win_w x win_h px: (x, y, w, h). entry: one panel's layout (corner, x, y
    as shares of the window from that corner, scale). Kept inside the window."""
    s = base_scale(win_h) * entry["scale"]
    w, h = pw * s, ph * s
    ox, oy = entry["x"] * win_w, entry["y"] * win_h
    corner = entry["corner"]
    x = win_w - ox - w if corner in ("ne", "se") else ox
    y = win_h - oy - h if corner in ("sw", "se") else oy
    x = min(max(0.0, x), max(0.0, win_w - w))
    y = min(max(0.0, y), max(0.0, win_h - h))
    return x, y, w, h


def place(x, y, w, h, win_w, win_h):
    """A panel moved to (x, y) as a layout entry's corner and offsets: the corner nearest the panel's centre, so it
    stays put against that edge when the window changes size."""
    cx, cy = x + w / 2, y + h / 2
    east, south = cx > win_w / 2, cy > win_h / 2
    corner = ("s" if south else "n") + ("e" if east else "w")
    ox = (win_w - x - w) if east else x
    oy = (win_h - y - h) if south else y
    lo_x, hi_x = O.LIMITS["x"]
    lo_y, hi_y = O.LIMITS["y"]
    return {"corner": corner, "x": round(min(hi_x, max(lo_x, ox / win_w)), 4) if win_w else 0.0,
            "y": round(min(hi_y, max(lo_y, oy / win_h)), 4) if win_h else 0.0}


# ---- Arrange mode (pure): which panel is under the mouse, what a drag or the wheel makes of its layout ----

HANDLE_PX = 16          # the square at a panel's bottom-right corner that sizes it
DONE_W, DONE_H = 220, 34
WHEEL_STEP = 0.05       # one wheel notch: this much more or less opacity


def done_rect(win_w):
    """Arrange mode's Done button, at the top middle of the game window: (x, y, w, h)."""
    return win_w / 2 - DONE_W / 2, 10, DONE_W, DONE_H


def inside(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def hit(geoms, x, y):
    """geoms: [(panel id, (x, y, w, h))] in drawing order. The topmost panel under (x, y) and what a press there does:
    (id, "resize") on its corner handle, (id, "move") elsewhere on it; None off every panel."""
    for pid, (px, py, pw, ph) in reversed(geoms):
        if inside((px, py, pw, ph), x, y):
            return pid, ("resize" if x >= px + pw - HANDLE_PX and y >= py + ph - HANDLE_PX else "move")
    return None


def dragged(entry, start_rect, dx, dy, mode, nat_w, nat_h, win_w, win_h):
    """A panel's layout entry after dragging (dx, dy) px from where it was (start_rect): moved (kept inside the
    window), or sized from its corner handle (top left kept, the aspect kept, the scale within LIMITS); its corner and
    offsets re-chosen from where it ends up (place)."""
    x, y, w, h = start_rect
    if mode == "move":
        nx = min(max(0.0, x + dx), max(0.0, win_w - w))
        ny = min(max(0.0, y + dy), max(0.0, win_h - h))
        return dict(entry, **place(nx, ny, w, h, win_w, win_h))
    lo, hi = O.LIMITS["scale"]
    gx, gy = (dx / w if w else 0.0), (dy / h if h else 0.0)
    grow = gx if abs(gx) >= abs(gy) else gy   # the direction dragged more: smaller as well as bigger
    scale = round(min(hi, max(lo, entry["scale"] * (1 + grow))), 4)
    s = base_scale(win_h) * scale
    return dict(entry, scale=scale, **place(x, y, nat_w * s, nat_h * s, win_w, win_h))


def wheeled(entry, key, notches):
    """The entry with its background's ("bg") or whole panel's ("alpha") opacity moved by `notches` wheel steps."""
    lo, hi = O.LIMITS[key]
    return dict(entry, **{key: round(min(hi, max(lo, entry[key] + WHEEL_STEP * notches)), 4)})


def screen_for(infos, nx, ny):
    """Of the screens (overlay_tracking.ScreenInfo), the one whose native rectangle holds the point (nx, ny), else the
    first; None with no screens."""
    for info in infos:
        x, y, w, h = info.native_geometry
        if x <= nx < x + w and y <= ny < y + h:
            return info
    return infos[0] if infos else None


def rgba(colour, alpha=1.0):
    """'#RRGGBB' or '#AARRGGBB' -> (r, g, b, a 0-255), times `alpha`; a bad colour is mid grey."""
    c = (colour or "").lstrip("#")
    try:
        if len(c) == 8:
            a, r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4, 6))
        elif len(c) == 6:
            a, (r, g, b) = 255, (int(c[i:i + 2], 16) for i in (0, 2, 4))
        else:
            raise ValueError(c)
    except ValueError:
        r = g = b = 128
        a = 255
    return r, g, b, max(0, min(255, round(a * alpha)))


# ---- talking to Outrider (pure: urllib) ----

def config_target(path=None):
    """(url, password) from the config file beside this checkout: [overlay] url and password, else this PC at
    [server] port. A missing or broken file: this PC on 8025."""
    import tomllib
    path = path or os.path.join(O_ROOT, "ed_outrider.toml")
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, ValueError):
        cfg = {}
    ov = O.overlay_settings(cfg)["overlay"]
    sv = cfg.get("server") if isinstance(cfg.get("server"), dict) else {}
    port = sv.get("port", 8025)
    port = port if isinstance(port, int) and not isinstance(port, bool) else 8025
    return ov["url"] or f"http://127.0.0.1:{port}", ov["password"]


O_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Client:
    """GET /api/overlay and POST the layout, signing in with the password when the Outrider asks for one (a server
    elsewhere): the session goes as a Bearer token, as the MCP bridge sends it."""

    def __init__(self, url, password="", opener=None):
        self.url, self.password = url.rstrip("/"), password
        self.token = None
        self.opener = opener or urllib.request.build_opener()
        self.error = None

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        for attempt in (1, 2):
            req = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"User-Agent": "outrider-overlay", "Content-Type": "application/json",
                                                  **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
            try:
                with self.opener.open(req, timeout=HTTP_TIMEOUT) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                with e:   # its body read (or not) and closed
                    if e.code == 401 and self.password and attempt == 1:
                        self._signin()
                        continue
                    if e.code == 401:
                        raise RuntimeError("this Outrider asks for a password: set [overlay] password (its [server] password)")
                    try:
                        return json.loads(e.read().decode("utf-8"))
                    except ValueError:
                        raise RuntimeError(f"HTTP {e.code}") from None
        raise RuntimeError("could not sign in")

    def _signin(self):
        req = urllib.request.Request(self.url + "/api/auth/signin", data=json.dumps({"password": self.password}).encode(),
                                     method="POST", headers={"User-Agent": "outrider-overlay", "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=HTTP_TIMEOUT) as r:
                self.token = json.loads(r.read().decode("utf-8")).get("token")
        except (urllib.error.URLError, ValueError, OSError):
            self.token = None

    def view(self, since=None):
        q = f"?since={urllib.request.quote(since)}" if since else ""
        return self._request("GET", "/api/overlay" + q)

    def set_layout(self, change):
        return self._request("POST", "/api/overlay/layout", change)

    def set(self, body):
        return self._request("POST", "/api/overlay", body)


class Feed:
    """The panels as last fetched, kept fresh by a thread asking once a second (`since` the last version, so an
    unchanged answer is a few bytes). The window reads `data` and `seq` (it repaints when seq changes)."""

    def __init__(self, client):
        self.client, self.data, self.seq, self.error = client, None, 0, None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def fetch_once(self):
        try:
            got = self.client.view(self.data["version"] if self.data else None)
        except (OSError, RuntimeError, ValueError, urllib.error.URLError) as e:
            with self._lock:
                if self.error != str(e):
                    log.warning("overlay: %s", e)
                self.error = str(e)
                if self.data is not None:   # Outrider gone: nothing stale stays on screen
                    self.data, self.seq = None, self.seq + 1
            return
        with self._lock:
            if self.error:
                log.info("overlay: connected to %s", self.client.url)
            self.error = None
            if isinstance(got, dict) and not got.get("same") and isinstance(got.get("panels"), list):
                self.data, self.seq = got, self.seq + 1

    def run(self):
        while not self._stop.is_set():
            self.fetch_once()
            self._stop.wait(POLL_S)

    def start(self):
        threading.Thread(target=self.run, name="overlay-feed", daemon=True).start()

    def stop(self):
        self._stop.set()


# ---- Qt: painting and the window ----

def paint(painter, data, win_w, win_h, arrange=False, override=None):
    """Draw every panel of `data` (GET /api/overlay's answer) for a game window of win_w x win_h px. arrange: frame
    and label each panel for moving and sizing, and the Done button (Arrange mode); override: {panel: layout entry}
    being dragged here, not saved yet. -> [(panel id, (x, y, w, h))] as drawn (for hit tests)."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainterPath, QPen, QPolygonF

    def colour(c, a=1.0):
        return QColor(*rgba(c, a))

    def pen(c, lw=1.0):
        p = QPen(colour(c)) if c else QPen(Qt.PenStyle.NoPen)
        if c:
            p.setWidthF(lw)
        return p

    layout = dict((data or {}).get("layout") or O.clean_layout(None), **(override or {}))
    geoms = []
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    painter.setRenderHint(painter.RenderHint.TextAntialiasing, True)
    for panel in (data or {}).get("panels") or []:
        entry = layout.get(panel.get("id")) or O.LAYOUT_DEFAULT.get(panel.get("id")) or O.LAYOUT_DEFAULT["system"]
        x, y, w, h = panel_rect(entry, panel["w"], panel["h"], win_w, win_h)
        s = base_scale(win_h) * entry["scale"]
        painter.save()
        painter.setOpacity(entry["alpha"])
        painter.translate(x, y)
        painter.scale(s, s)
        if entry["bg"] > 0:
            paint_frame(painter, panel, entry["bg"])
        for it in panel.get("items") or []:
            t = it.get("t")
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if t == "text":
                f = QFont()
                f.setPixelSize(FONT_PX.get(it.get("size"), 15))
                f.setBold(bool(it.get("bold")))
                painter.setFont(f)
                painter.setPen(colour(it.get("c")))
                fm = QFontMetricsF(f)
                tx = it["x"] - fm.horizontalAdvance(it["s"]) if it.get("align") == "right" else it["x"]
                painter.drawText(QPointF(tx, it["y"] + fm.ascent()), it["s"])
            elif t == "runs":   # coloured parts of one line, each after the last at the font's real width, on one baseline
                fonts = []
                for s_, c_, size_, bold_ in it.get("runs") or []:
                    f = QFont()
                    f.setPixelSize(FONT_PX.get(size_, 15))
                    f.setBold(bool(bold_))
                    fonts.append((s_, c_, f, QFontMetricsF(f)))
                base = it["y"] + max((fm.ascent() for *_, fm in fonts), default=0)
                fm_x = it["x"]
                for s_, c_, f, fm in fonts:
                    painter.setFont(f)
                    painter.setPen(colour(c_))
                    painter.drawText(QPointF(fm_x, base), s_)
                    fm_x += fm.horizontalAdvance(s_)
            elif t == "rect":
                painter.setPen(pen(it.get("c"), it.get("lw", 1)))
                if it.get("f"):
                    painter.setBrush(QBrush(colour(it["f"])))
                painter.drawRect(QRectF(it["x"], it["y"], it["w"], it["h"]))
            elif t == "circle":
                painter.setPen(pen(it.get("c"), it.get("lw", 1)))
                if it.get("f"):
                    painter.setBrush(QBrush(colour(it["f"])))
                painter.drawEllipse(QPointF(it["x"], it["y"]), it["r"], it["r"])
            elif t == "line":
                painter.setPen(pen(it.get("c"), it.get("lw", 1)))
                painter.drawPolyline(QPolygonF([QPointF(px, py) for px, py in it.get("pts") or []]))
            elif t == "marker":
                c, r, mx, my = it.get("c"), it.get("r", 6), it["x"], it["y"]
                kind = it.get("kind")
                if kind == "dot":
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                    painter.setBrush(QBrush(colour(c)))
                    painter.drawEllipse(QPointF(mx, my), r, r)
                elif kind == "cross":
                    painter.setPen(pen(c, 2))
                    painter.drawLine(QPointF(mx - r, my - r), QPointF(mx + r, my + r))
                    painter.drawLine(QPointF(mx - r, my + r), QPointF(mx + r, my - r))
                else:   # arrow: a triangle pointing up, turned rot degrees clockwise
                    painter.save()
                    painter.translate(mx, my)
                    painter.rotate(it.get("rot", 0))
                    path = QPainterPath()
                    path.moveTo(0, -r)
                    path.lineTo(r * 0.7, r)
                    path.lineTo(0, r * 0.45)
                    path.lineTo(-r * 0.7, r)
                    path.closeSubpath()
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                    painter.setBrush(QBrush(colour(c)))
                    painter.drawPath(path)
                    painter.restore()
        painter.restore()
        geoms.append((panel.get("id"), (x, y, w, h)))
        if arrange:
            paint_arrange_frame(painter, panel, (x, y, w, h))
    if arrange:
        paint_done(painter, win_w)
    return geoms


def frame_points(style, w, h, cut=10):
    """The outline of a panel's frame for a polygon style ("chamfer": the top left and bottom right corners cut), in
    the panel's own units; None for the other styles (pure: tested without Qt)."""
    if style == "chamfer":
        return [(cut, 0), (w, 0), (w, h - cut), (w - cut, h), (0, h), (0, cut)]
    return None


def paint_frame(painter, panel, opacity):
    """A panel's background at `opacity` and its frame in the theme's style."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
    w, h, style = panel["w"], panel["h"], panel.get("style") or "rounded"
    fill = QBrush(QColor(*rgba(panel.get("bg"), opacity)))
    line = QPen(QColor(*rgba(panel.get("frame")))) if opacity >= 0.15 else QPen(Qt.PenStyle.NoPen)
    painter.setPen(line)
    painter.setBrush(fill)
    pts = frame_points(style, w, h)
    if pts:
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    elif style == "double":
        painter.drawRect(QRectF(0, 0, w, h))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(3, 3, w - 6, h - 6))
    elif style == "lcars":   # a solid bar down the left and one across the top, in the theme's title colour
        painter.drawRect(QRectF(0, 0, w, h))
        bar = QColor(*rgba(panel.get("accent") or panel.get("frame"), max(opacity, 0.6)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(bar))
        painter.drawRect(QRectF(0, 0, 5, h))
        painter.drawRect(QRectF(0, 0, w * 0.4, 3))
    else:
        painter.drawRoundedRect(QRectF(0, 0, w, h), RADIUS, RADIUS)


def paint_done(painter, win_w):
    """Arrange mode's Done button and what the mouse does, at the top middle."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QFont, QPen
    x, y, w, h = done_rect(win_w)
    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor(255, 200, 60)))
    painter.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
    f = QFont()
    f.setPixelSize(15)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(20, 20, 20))
    painter.drawText(QRectF(x, y, w, h), int(Qt.AlignmentFlag.AlignCenter), "✓ Done arranging")
    f.setPixelSize(13)
    f.setBold(False)
    painter.setFont(f)
    painter.setPen(QColor(255, 200, 60))
    painter.drawText(QPointF(x - 170, y + h + 22), "drag: move · drag the corner: size · wheel: background · Shift+wheel: panel")


def paint_arrange_frame(painter, panel, rect):
    """Arrange mode's frame around a panel: a dashed outline, its name, the corner handle that sizes it."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QFont, QPen
    x, y, w, h = rect
    p = QPen(QColor(255, 200, 60))
    p.setWidthF(2)
    p.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(p)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(x, y, w, h))
    painter.setBrush(QBrush(QColor(255, 200, 60)))
    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.drawRect(QRectF(x + w - HANDLE_PX, y + h - HANDLE_PX, HANDLE_PX, HANDLE_PX))
    f = QFont()
    f.setPixelSize(13)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(255, 200, 60))
    painter.drawText(QPointF(x + 4, y - 6 if y > 20 else y + h + 16), O.PANEL_NAMES.get(panel.get("id"), panel.get("id", "")))


_APP = None      # render_png's application when none runs (kept: Qt must not lose it mid-paint)


def render_png(data, path, win_w=1920, win_h=1080, arrange=False):
    """One frame of `data` drawn into a PNG over a dark stand-in for the game (testing, screenshots): no window."""
    global _APP
    from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter
    if QGuiApplication.instance() is None:   # fonts need an application, even with nothing on screen
        _APP = QGuiApplication(sys.argv[:1])
    img = QImage(win_w, win_h, QImage.Format.Format_ARGB32)
    img.fill(QColor(20, 24, 30))
    painter = QPainter(img)
    try:
        paint(painter, data, win_w, win_h, arrange)
    finally:
        painter.end()
    return img.save(path)


def run_window(client, title_hint=None):   # pragma: no cover - needs a display; checked by hand
    """The overlay window: follows Elite's window, paints the feed's panels, passes clicks through."""
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QGuiApplication, QPainter
    from PyQt6.QtWidgets import QApplication, QWidget
    from . import overlay_tracking

    app = QApplication.instance() or QApplication(sys.argv[:1])
    feed = Feed(client)
    feed.start()
    tracker = overlay_tracking.create_tracker(log, title_hint or overlay_tracking.TITLE_HINT,
                                              monitor_provider=lambda: [
                                                  (s.name() or f"screen-{i}", s.geometry().x(), s.geometry().y(),
                                                   s.geometry().width(), s.geometry().height())
                                                  for i, s in enumerate(QGuiApplication.screens())])

    def screen_of(st):
        """The screen the game's window is on (by its centre, in native pixels), as overlay_tracking.ScreenInfo."""
        infos = []
        for s in QGuiApplication.screens():
            g, dpr = s.geometry(), s.devicePixelRatio()
            infos.append(overlay_tracking.ScreenInfo(s.name(), (g.x(), g.y(), g.width(), g.height()),
                                                     (round(g.x() * dpr), round(g.y() * dpr), round(g.width() * dpr),
                                                      round(g.height() * dpr)), dpr))
        return screen_for(infos, st.x + st.width / 2, st.y + st.height / 2)

    class Overlay(QWidget):
        def __init__(self):
            super().__init__()
            # Modern Overlay's window: frameless, on top, translucent, never activated, clicks passed through
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
            if sys.platform.startswith("linux"):
                flags |= Qt.WindowType.X11BypassWindowManagerHint
            else:
                flags |= Qt.WindowType.Tool
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setWindowTitle("ED Outrider overlay")
            self.seq = -1
            self.click_through = True
            # Arrange mode: the panels as drawn (for hit tests), the drag under way, the edits not saved yet
            # dirty: an edit not sent yet (kept over Outrider's answers until it is); saved_at: the feed's seq when the
            # last edit was sent (the next answer carries it, and the local copy can go)
            self.geoms, self.drag, self.override, self.saved_at, self.dirty = [], None, {}, None, False
            self.wheel_timer = QTimer(self)
            self.wheel_timer.setSingleShot(True)
            self.wheel_timer.timeout.connect(self.save_override)

        def arranging(self):
            return bool(feed.data and feed.data.get("arrange"))

        def post(self, fn, *args):
            """Send to Outrider off the GUI thread (a slow server must not freeze the overlay)."""
            def run():
                try:
                    fn(*args)
                except (OSError, RuntimeError, ValueError) as e:
                    log.warning("overlay: %s", e)
                self.saved_at = feed.seq   # the next answer after this one carries the change: the edits can go
            threading.Thread(target=run, daemon=True).start()

        def edited(self):
            self.dirty, self.saved_at = True, None

        def save_override(self):
            change = {pid: {k: e[k] for k in ("corner", "x", "y", "scale", "bg", "alpha")} for pid, e in self.override.items()}
            self.dirty = False
            if change:
                self.post(client.set_layout, change)

        def entry(self, pid):
            lay = (feed.data or {}).get("layout") or O.clean_layout(None)
            return dict(self.override.get(pid) or lay.get(pid) or O.LAYOUT_DEFAULT[pid])

        def panel(self, pid):
            return next((p for p in (feed.data or {}).get("panels") or [] if p.get("id") == pid), None)

        def mousePressEvent(self, ev):
            if not self.arranging():
                return
            x, y = ev.position().x(), ev.position().y()
            if inside(done_rect(self.width()), x, y):
                self.post(client.set, {"arrange": False})
                return
            got = hit(self.geoms, x, y)
            if got:
                pid, mode = got
                rect = dict(self.geoms)[pid]
                self.drag = (pid, mode, x, y, rect, self.entry(pid))

        def mouseMoveEvent(self, ev):
            if not self.drag:
                return
            pid, mode, x0, y0, rect, start = self.drag
            p = self.panel(pid)
            if not p:
                return
            self.override[pid] = dragged(start, rect, ev.position().x() - x0, ev.position().y() - y0, mode, p["w"], p["h"],
                                         self.width(), self.height())
            self.edited()
            self.update()

        def mouseReleaseEvent(self, _ev):
            if self.drag:
                self.drag = None
                self.save_override()

        def wheelEvent(self, ev):
            if not self.arranging():
                return
            got = hit(self.geoms, ev.position().x(), ev.position().y())
            if not got:
                return
            notches = ev.angleDelta().y() / 120 or ev.angleDelta().x() / 120
            key = "alpha" if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else "bg"
            self.override[got[0]] = wheeled(self.entry(got[0]), key, notches)
            self.edited()
            self.update()
            self.wheel_timer.start(400)   # saved once the wheel stops

        def apply_click_through(self, through):
            self.click_through = through
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, through)
            handle = self.windowHandle()
            if handle is not None:
                handle.setFlag(Qt.WindowType.WindowTransparentForInput, through)
            if through and sys.platform.startswith("win"):   # Modern Overlay's platform_integration
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = int(self.winId())
                    style = user32.GetWindowLongW(hwnd, -20)   # GWL_EXSTYLE
                    user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)   # WS_EX_LAYERED | WS_EX_TRANSPARENT
                except Exception as e:  # noqa: BLE001 -- best effort
                    log.debug("Windows click-through: %s", e)

        def follow(self):
            st = tracker.poll() if tracker else None
            arranging = self.arranging()
            if self.click_through == arranging:   # Arrange mode takes the mouse; otherwise every click goes to the game
                self.apply_click_through(not arranging)
            if not st or not st.is_visible or not (st.is_foreground or arranging or self.isActiveWindow()):
                if self.isVisible():
                    self.hide()
                return
            x, y, w, h = overlay_tracking.native_rect_to_qt((st.x, st.y, st.width, st.height), screen_of(st))
            if (self.x(), self.y(), self.width(), self.height()) != (x, y, w, h):
                self.setGeometry(x, y, w, h)
            if not self.isVisible():
                self.show()
                self.apply_click_through(self.click_through)
            self.raise_()

        def tick(self):
            if feed.seq != self.seq:
                self.seq = feed.seq
                if self.saved_at is not None and self.seq > self.saved_at and not self.drag and not self.dirty:
                    self.override, self.saved_at = {}, None   # Outrider has the edits now
                if not self.arranging():
                    self.override, self.drag = {}, None
                self.update()

        def paintEvent(self, _event):
            p = QPainter(self)
            try:
                self.geoms = paint(p, feed.data, self.width(), self.height(), arrange=self.arranging(), override=self.override)
            finally:
                p.end()

    win = Overlay()
    follow = QTimer(win)
    follow.timeout.connect(win.follow)
    follow.start(FOLLOW_MS)
    ticker = QTimer(win)
    ticker.timeout.connect(win.tick)
    ticker.start(250)
    win.follow()
    log.info("overlay: drawing from %s%s", client.url, "" if tracker else " (cannot follow the game's window here)")
    try:
        return app.exec()
    finally:
        feed.stop()


def main(argv=None):
    p = argparse.ArgumentParser(description="ED Outrider's in-game overlay: panels drawn over Elite's window.")
    p.add_argument("--url", help="the Outrider to draw from (default: [overlay] url, else this PC)")
    p.add_argument("--password", help="its [server] password (default: [overlay] password)")
    p.add_argument("--config", help="the config file to read url and password from (default: ed_outrider.toml here)")
    p.add_argument("--title", help="a part of the game window's title (default: Elite - Dangerous)")
    p.add_argument("--render", metavar="PNG", help="draw one frame of the current panels into this picture and stop")
    p.add_argument("--size", default="1920x1080", help="--render's game window size (default 1920x1080)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    url, password = config_target(a.config)
    client = Client(a.url or url, a.password if a.password is not None else password)
    if a.render and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"   # a picture needs no screen
    elif sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" \
            and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"   # XWayland: a Wayland window cannot place itself over the game
    if os.environ.get("QT_QPA_PLATFORM") == "xcb":
        # Qt's GNOME theme starts Gtk, which follows GDK_BACKEND (wayland on a GNOME session): on the same X display
        # as Qt, or without a Wayland display it exits the program
        os.environ["GDK_BACKEND"] = "x11"
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("The overlay needs PyQt6: pip install -r requirements-overlay.txt (in Outrider's .venv)", file=sys.stderr)
        return 2
    if a.render:
        try:
            w, h = (int(v) for v in a.size.lower().split("x"))
        except ValueError:
            p.error("--size is WIDTHxHEIGHT, e.g. 1920x1080")
        app = QApplication.instance() or QApplication(sys.argv[:1])
        try:
            data = client.view()
        except (OSError, RuntimeError, ValueError) as e:
            print(f"cannot reach {client.url}: {e}", file=sys.stderr)
            return 1
        ok = render_png(data, a.render, w, h, arrange=bool(data.get("arrange")))
        app.quit()
        print(f"{'wrote' if ok else 'could not write'} {a.render}: {len(data.get('panels') or [])} panels")
        return 0 if ok else 1
    return run_window(client, a.title)


if __name__ == "__main__":
    sys.exit(main())
