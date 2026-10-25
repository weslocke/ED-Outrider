"""The in-game overlay, Outrider's side (project/PLAN-overlay-build-2026-10-10.md): what each panel draws, as small
draw lists on a 1280x960 canvas, for the overlay window on the game PC (outrider/overlay_window.py) to paint over
Elite's window. Pure: the server's State hands these builders the summaries Here, Now and the surface map already
have, and serves the result at GET /api/overlay.

A panel is {"id", "w", "h", "bg", "frame", "style", "accent", "items"}: its natural size in canvas units, its
background and frame colours, its frame's style (rounded, chamfer, double or lcars: the theme's) and the colour of
LCARS's bars, and its items in its own coordinates (0,0 its top left). The window places each panel by the layout (a
corner of the game window, an offset as a share of the window, a scale) and draws its background at the layout's
opacity, then the items, the whole panel at the layout's alpha. Items:

    {"t": "text", "x", "y", "s", "c", "size", "bold", "align"}   (x, y: the text's top left; align right: x is its right edge)
    {"t": "runs", "x", "y", "runs": [[s, c, size, bold], ...], "align"}   (a line of differently coloured parts, set one
                                         after the other with the font's own widths; align "center": x is its middle)
    {"t": "rect", "x", "y", "w", "h", "c", "f", "lw"}            (c: the line's colour or None, f: the fill or None)
    {"t": "circle", "x", "y", "r", "c", "f", "lw"}               (x, y: the centre)
    {"t": "line", "pts": [[x, y], ...], "c", "lw"}
    {"t": "marker", "x", "y", "kind": "dot"|"cross"|"arrow", "c", "r", "rot"}   (rot: degrees clockwise, arrow only)

Colours are "#RRGGBB" or "#AARRGGBB".
"""
import copy
import datetime
import math
import os
import re
import sys
import time

from . import ROOT
from . import pads as outrider_pads
from .riches import left_words, survey_kind

CANVAS_W, CANVAS_H = 1280, 960
PANELS = ("system", "body", "radar", "strip", "now", "bio", "alerts")
# "body" is the Target panel (D1): the body you are at or have targeted, else the system targeted. Its id, config key
# (body_panel) and layout key stayed, so an arrangement and a config made for the Body panel carry over unchanged.
PANEL_NAMES = {"system": "System", "body": "Target", "radar": "Surface radar", "strip": "System strip",
               "now": "Now (To-Do & Info)", "bio": "Bio signals", "alerts": "Alerts"}
# a panel is placed from a corner of the game window, or centred along its top or bottom edge (n, s: x is not used)
CORNERS = ("nw", "ne", "sw", "se", "n", "s")
SIZES = ("small", "normal", "large")
THEMES = ("default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "vorlon", "shadow", "sith", "alliance", "dark")
TEST_SECONDS = 60       # "Show test panels": how long they stay (shown whether or not the game is in front)
ARRANGE_SECONDS = 600   # Arrange mode ends by itself after this, so the overlay never stays in the way of the mouse

# [overlay] hide_docked (the author, 2026-10-14): the panels hidden while docked (the ship docked, or on foot in a station,
# hangar or social space). Every panel but the radar, which shows only on a body's surface; by default the ones about
# flying (System, Target, Now, Bio): the strip and the alerts still say where you are and what happened
DOCKED_PANELS = tuple(p for p in PANELS if p != "radar")
HIDE_DOCKED_DEFAULT = ("system", "body", "now", "bio")
# [overlay] hide_on_foot (the author, 2026-10-15): the panels hidden on foot (anywhere: a station, a planet's surface), none
# by default; hide_mouse_lock: the whole overlay off on foot and in the DSS, where Elite locks the mouse (#1: an overlay
# window over the game broke that lock on the author's Linux PC; the windows only as big as their panels fixed it there)
DEFAULTS = {"enabled": False, "theme": "default", "text_size": "normal", "system_panel": True, "body_panel": True,
            "radar": True, "strip_panel": False, "now_panel": False, "bio_panel": False, "alerts_panel": False, "system_seconds": 0,
            "radar_range": 800, "analysis_only": [], "hide_docked": list(HIDE_DOCKED_DEFAULT), "show_inactive": False,
            "panel_scale": 100, "pad_diagram": True, "hide_on_foot": [], "hide_mouse_lock": False}
# [overlay] panel_scale (a GitHub report, 2026-10-14: too large on a 4K TV): all panels' size in %, on top of each panel's
# own; Settings -> In-game overlay's All panels, Ctrl + wheel in Arrange mode
PANEL_SCALE_LIMITS = (20, 250)
SYSTEM_SECONDS_LIMITS, RADAR_RANGE_LIMITS = (0, 3600), (100, 20000)   # s, m (Settings -> In-game overlay, the config)
# where each panel starts: a corner of the game window, the offset from it as a share of the window's width (x) and
# height (y), its size (1 = the canvas's own), its background's opacity (0: text only) and the whole panel's; its own
# text size ("text": small, normal or large; "" as all panels, [overlay] text_size), added below
LAYOUT_DEFAULT = {"system": {"corner": "nw", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "body": {"corner": "ne", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "radar": {"corner": "se", "x": 0.02, "y": 0.10, "scale": 1.0, "bg": 0.5, "alpha": 1.0},
                  "strip": {"corner": "n", "x": 0.0, "y": 0.005, "scale": 1.0, "bg": 0.5, "alpha": 1.0},
                  "now": {"corner": "sw", "x": 0.02, "y": 0.06, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "bio": {"corner": "nw", "x": 0.02, "y": 0.45, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  # under the system strip, centred (S26)
                  "alerts": {"corner": "n", "x": 0.0, "y": 0.09, "scale": 1.0, "bg": 0.65, "alpha": 1.0}}
for _entry in LAYOUT_DEFAULT.values():
    _entry["text"] = ""   # as all panels: a layout saved before the per-panel text size reads as it drew then
del _entry
# the size goes down to 20 % (it stopped at 50 % until the 4K TV report): what keeps a panel readable is MIN_TEXT_PX,
# in the window's pixels, not a share (50 % of small text is about 7 px on a 1080p window but 13 px on a 4K one)
LIMITS = {"x": (0.0, 0.95), "y": (0.0, 0.95), "scale": (0.2, 2.5), "bg": (0.0, 1.0), "alpha": (0.1, 1.0)}

# text metrics on the canvas: line heights and an average character width per size (the window's font is close to
# these; long texts are cut with … to the panel's width rather than run over its edge)
LINE_H = {"small": 16, "normal": 20, "large": 26, "huge": 56}
CHAR_W = {"small": 6.6, "normal": 8.2, "large": 10.4, "huge": 26.0}
# the window's font sizes in canvas units (scaled with the panel); "huge" only for the docking pad's number (#3), not a
# text size a player picks (SIZES)
FONT_PX = {"small": 12, "normal": 15, "large": 19, "huge": 48}
PAD = 10
MIN_TEXT_PX = 9   # the window never draws a panel's text smaller than this many pixels, whatever the sizes say


def base_scale(win_h):
    """Canvas units to window pixels: the 960-unit-high canvas fits the game window's height."""
    return max(0.1, win_h / CANVAS_H)


def effective_scale(win_h, panel_scale, size, smallest_font):
    """Canvas units to window pixels for one panel: base_scale(win_h) times all panels' size (panel_scale, 1 = 100 %)
    times the panel's own (size, its layout's scale), raised to the least that draws its smallest text (smallest_font,
    canvas units: FONT_PX) at MIN_TEXT_PX, so a small setting stays readable on a small window while a 4K one can go
    much smaller. smallest_font None (no text): no floor."""
    s = base_scale(win_h) * panel_scale * size
    return max(s, MIN_TEXT_PX / smallest_font) if smallest_font else s


def smallest_font(panel):
    """The smallest text a panel's items draw, in canvas units (FONT_PX of their sizes); None with no text."""
    sizes = []
    for it in panel.get("items") or []:
        if it.get("t") == "text":
            sizes.append(it.get("size"))
        elif it.get("t") == "runs":
            sizes += [r[2] for r in it.get("runs") or [] if len(r) > 2]
    return min((FONT_PX.get(x, FONT_PX["normal"]) for x in sizes), default=None)


def panel_font(pid, size):
    """The smallest text panel `pid` draws at text size `size`, as smallest_font finds it in the panel (the radar's
    labels are small whatever the size): for Settings' figure, before the panel is built."""
    return FONT_PX["small"] if pid == "radar" else FONT_PX.get(size, FONT_PX["normal"])


def text_px(win_h, panel_scale, size, font):
    """Settings' figure for one panel: (the height of its smallest text in the game window's pixels, held: raised to
    MIN_TEXT_PX because the sizes would draw it smaller)."""
    want = base_scale(win_h) * panel_scale * size * font
    got = effective_scale(win_h, panel_scale, size, font) * font
    return round(got), got > want + 1e-9

# the Default theme's colours: the page's dark ones (page.css :root), the title in its info blue
DEFAULT_PALETTE = {"title": "#6AA8FF", "text": "#D8DDE4", "muted": "#7D8794", "good": "#5CC98A", "warn": "#E3B341",
                   "bad": "#E05D5D", "accent": "#FF8C1A", "panel": "#161A20", "frame": "#262C35", "style": "rounded"}
THEMES_DIR = os.path.join(ROOT, "static", "themes")
# each palette key from the theme's variables, the first one set (the themes' own: static/themes/<name>.css)
THEME_VARS = {"title": ("tb-title", "info", "accent"), "text": ("text",), "muted": ("muted",), "good": ("good",),
              "warn": ("warn",), "bad": ("bad",), "accent": ("accent",), "panel": ("panel",), "frame": ("line",)}
# the panels' frames per theme, as the 10-05 plan drew them: cut corners (Elite, Narn, Shadows), a double line
# (Centauri, Minbari), LCARS's bars, rounded for the rest (Vorlon among them)
THEME_STYLE = {"elite": "chamfer", "narn": "chamfer", "shadow": "chamfer", "centauri": "double", "minbari": "double",
               "lcars": "lcars"}
_palettes = {}


def css_colour(v):
    """A CSS colour as "#RRGGBB" or "#AARRGGBB" (#rgb, #rrggbb, #rrggbbaa, rgb(), rgba()), else None."""
    v = (v or "").strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + (h[6:] + h[:6] if len(h) == 8 else h).upper()   # CSS's alpha is last, the window's first
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", v)
    if m:
        r, g, b = (max(0, min(255, round(float(x)))) for x in m.groups()[:3])
        a = max(0, min(255, round(float(m.group(4)) * 255))) if m.group(4) is not None else 255
        return f"#{r:02X}{g:02X}{b:02X}" if a == 255 else f"#{a:02X}{r:02X}{g:02X}{b:02X}"
    return None


def theme_vars(css, theme):
    """A theme stylesheet's custom properties from its :root[data-theme="<theme>"] blocks, var() references resolved."""
    raw = {}
    for m in re.finditer(r':root\[data-theme="%s"\]\s*\{([^}]*)\}' % re.escape(theme), css):
        for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", m.group(1)):
            raw[name] = value.strip()

    def resolve(v, depth=0):
        if depth > 10:
            return v
        return re.sub(r"var\(--([\w-]+)(?:\s*,\s*([^)]*))?\)",
                      lambda m: resolve(raw.get(m.group(1), m.group(2) or ""), depth + 1), v)
    return {k: resolve(v) for k, v in raw.items()}


def palette(theme="default"):
    """A theme's colours for the panels: {title, text, muted, good, warn, bad, accent, panel, frame, style}. Read from
    the theme's stylesheet (once); anything missing or not a plain colour: the Default's."""
    if theme in _palettes:
        return dict(_palettes[theme])
    pal = dict(DEFAULT_PALETTE)
    if theme in THEMES and theme != "default":
        try:
            with open(os.path.join(THEMES_DIR, f"{theme}.css"), encoding="utf-8") as f:
                found = theme_vars(f.read(), theme)
        except OSError:
            found = {}
        for key, names in THEME_VARS.items():
            for name in names:
                c = css_colour(found.get(name))
                if c:
                    pal[key] = c
                    break
        pal["style"] = THEME_STYLE.get(theme, "rounded")
    _palettes[theme] = pal
    return dict(pal)


def _warn(msg):
    print(f"config: [overlay] {msg}", file=sys.stderr)


def overlay_settings(cfg):
    """[overlay] from a parsed config: {"overlay": {...}} with DEFAULTS for anything missing or wrong (reported on stderr,
    as every other section's checks are)."""
    o = cfg.get("overlay") if isinstance(cfg.get("overlay"), dict) else {}
    if "overlay" in cfg and not isinstance(cfg.get("overlay"), dict):
        _warn("must be a section (a table of settings); ignored")
    out = dict(DEFAULTS)
    for key in ("enabled", "system_panel", "body_panel", "radar", "strip_panel", "now_panel", "bio_panel", "alerts_panel",
                "show_inactive", "pad_diagram", "hide_mouse_lock"):
        v = o.get(key)
        if v is None:
            continue
        if isinstance(v, bool):
            out[key] = v
        else:
            _warn(f"{key} = {v!r} must be true or false; using {DEFAULTS[key]}")
    for key, allowed in (("theme", THEMES), ("text_size", SIZES)):
        v = o.get(key)
        if v is None:
            continue
        if isinstance(v, str) and v.strip().lower() in allowed:
            out[key] = v.strip().lower()
        else:
            _warn(f"{key} = {v!r} must be one of {', '.join(allowed)}; using {DEFAULTS[key]!r}")
    for key, lo, hi in (("system_seconds", *SYSTEM_SECONDS_LIMITS), ("radar_range", *RADAR_RANGE_LIMITS), ("panel_scale", *PANEL_SCALE_LIMITS)):
        v = o.get(key)
        if v is None:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out[key] = int(min(hi, max(lo, v)))
        else:
            _warn(f"{key} = {v!r} must be a number; using {DEFAULTS[key]}")
    out["analysis_only"] = analysis_list(o.get("analysis_only"), _warn)
    out["hide_docked"] = docked_list(o.get("hide_docked"), _warn)
    out["hide_on_foot"] = foot_list(o.get("hide_on_foot"), _warn)
    return {"overlay": out}


def panel_list(key, v, warn=None, default=(), allowed=PANELS):
    """One of [overlay]'s panel lists: panel ids in PANELS' order; an id not in `allowed` is dropped (said through
    `warn`), missing or anything but a list of names is `default` (a fresh list each time)."""
    if v is None:
        return list(default)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        if warn:
            warn(f"{key} = {v!r} must be a list of panel names ({', '.join(allowed)}); using {list(default)}")
        return list(default)
    unknown = [x for x in v if x.strip().lower() not in allowed]
    if unknown and warn:
        warn(f"{key}: {', '.join(repr(x) for x in unknown)} not a panel ({', '.join(allowed)}); left out")
    names = {x.strip().lower() for x in v}
    return [p for p in PANELS if p in names and p in allowed]


def analysis_list(v, warn=None):
    """[overlay] analysis_only (D2a): the panels shown in your ship only while the HUD is in analysis mode; none when
    the key is missing."""
    return panel_list("analysis_only", v, warn)


def docked_list(v, warn=None):
    """[overlay] hide_docked (the author, 2026-10-14): the panels hidden while docked, any of DOCKED_PANELS (the radar
    is never one: it shows only on a body's surface); HIDE_DOCKED_DEFAULT when the key is missing, so a config written
    before it hides what Outrider hid then (Now and the Target panel) and the System and Bio panels too."""
    return panel_list("hide_docked", v, warn, HIDE_DOCKED_DEFAULT, DOCKED_PANELS)


def foot_list(v, warn=None):
    """[overlay] hide_on_foot (the author, 2026-10-15): the panels hidden on foot, any of PANELS; none when missing."""
    return panel_list("hide_on_foot", v, warn)


# ---- the page's overlay pill (S8): how the overlay is doing, in one word and a reason ----

# what the overlay window sees, sent with each of its GETs as &w= (overlay_window.track_code)
TRACK_CODES = ("drawing", "behind", "hidden", "covered", "no_window", "no_wmctrl", "no_xprop", "no_tracker")
QUIET_S = 15   # s without a GET from a window that should be running: "not answering"
TRACK_WHY = {"drawing": ("ok", "drawing over Elite"),
             "behind": ("wait", "Elite is not the active window"),   # the page: "behind this page" while it has the focus
             "hidden": ("wait", "Elite's window is minimised or on another desktop"),
             "covered": ("wait", "another window covers Elite's"),
             "no_window": ("bad", "Elite's window cannot be found (exclusive fullscreen, or Proton's native Wayland mode?)"),
             "no_wmctrl": ("bad", "wmctrl not installed: the overlay cannot find Elite's window"),
             "no_xprop": ("bad", "xprop not installed: the overlay cannot tell whether Elite is in front"),
             "no_tracker": ("bad", "the overlay cannot follow the game's window on this system")}
FULLSCREEN_WHY = ("Elite is set to exclusive fullscreen: nothing can draw over it; "
                  "choose Borderless in the game's Options → Graphics → Display")


def health(wanted, runner, track, quiet, started, live, loading, fullscreen=False):
    """The page's overlay pill: {state: ok | wait | bad, code, why}, or None when there is nothing to say (the overlay
    not wanted, or Outrider runs no window here: a server). runner: OverlayRunner.status(); track: the window's last
    TRACK_CODES word (None: never said); quiet: s since the window last asked or was started, whichever is later (None:
    neither); started: whether it asked since the runner last started it (state off: not started yet); live / loading: the game, from the journals; fullscreen: DisplaySettings.xml says
    exclusive fullscreen. The tools the window lacks come first (a fix for the player), then the game, then the window."""
    if not wanted or runner is None:
        return None
    state, why = runner.get("state"), runner.get("why")

    def out(level, code, text):
        return {"state": level, "code": code, "why": text}
    if state == "installing":
        return out("wait", "installing", "installing PyQt6 for the overlay window")
    if state == "no_qt":
        return out("wait", "no_qt", "the overlay window needs PyQt6: Outrider installs it")
    if state == "install_failed":
        return out("bad", "install_failed", f"installing PyQt6 failed: {why or '?'}")
    if state == "failed":
        return out("bad", "failed", f"the overlay window: {why or 'it stopped'}")
    if state == "restarting":
        # as the failed one reads (review 2026-10-23 S7-B5: "the overlay window it stopped (exit 1)")
        return out("wait", "restarting", f"the overlay window: {why or 'it stopped'}")
    quiet = float("inf") if quiet is None else quiet
    if state == "starting" or (not started and (quiet <= QUIET_S or state == "off")):
        return out("wait", "starting", "starting the overlay window")
    if quiet > QUIET_S:
        return out("bad", "quiet", "the overlay window is not answering")
    if track in ("no_wmctrl", "no_xprop", "no_tracker"):
        return out(TRACK_WHY[track][0], track, TRACK_WHY[track][1])
    if loading:
        return out("wait", "loading", "Elite is loading")
    if not live:
        return out("wait", "no_game", "Elite is not running")
    if fullscreen:
        return out("bad", "fullscreen", FULLSCREEN_WHY)
    if track not in TRACK_WHY:
        return out("wait", "starting", "starting the overlay window")
    level, text = TRACK_WHY[track]
    return out(level, track, text)


# Elite's display mode, from its DisplaySettings.xml (S8): exclusive fullscreen hides anything drawn over the game
DISPLAY_SETTINGS = ("AppData", "Local", "Frontier Developments", "Elite Dangerous", "Options", "Graphics",
                    "DisplaySettings.xml")
FULLSCREEN_MODES = {"0": "windowed", "1": "fullscreen", "2": "borderless"}   # <FullScreen>: published values, unchecked


def display_settings_paths(journal_dirs, environ=None):
    """Where DisplaySettings.xml should be for these journal folders: the journals are in <user>/Saved Games/Frontier
    Developments/Elite Dangerous, the options in <user>/AppData/Local/... (on Windows and in a Proton prefix alike);
    on Windows also %LOCALAPPDATA%'s. Each once, in that order."""
    environ = os.environ if environ is None else environ
    out = []
    for d in journal_dirs or ():
        user = os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(d))))
        out.append(os.path.join(user, *DISPLAY_SETTINGS))
    if environ.get("LOCALAPPDATA"):
        out.append(os.path.join(environ["LOCALAPPDATA"], *DISPLAY_SETTINGS[2:]))
    return list(dict.fromkeys(out))


def display_mode(text):
    """DisplaySettings.xml's text -> "windowed", "fullscreen", "borderless", or None (no <FullScreen>, another value)."""
    m = re.search(r"<FullScreen>\s*(\d+)\s*</FullScreen>", text or "")
    return FULLSCREEN_MODES.get(m.group(1)) if m else None


def _num(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return min(hi, max(lo, float(v)))


def clean_layout(raw):
    """The stored layout made whole: every panel, every key, each within LIMITS (a missing or bad value: the default)."""
    raw = raw if isinstance(raw, dict) else {}
    out = copy.deepcopy(LAYOUT_DEFAULT)
    for panel, keys in out.items():
        got = raw.get(panel) if isinstance(raw.get(panel), dict) else {}
        if got.get("corner") in CORNERS:
            keys["corner"] = got["corner"]
        if got.get("text") in SIZES:
            keys["text"] = got["text"]
        for k, (lo, hi) in LIMITS.items():
            v = _num(got.get(k), lo, hi)
            if v is not None:
                keys[k] = round(v, 4)
    return out


def layout_update(current, change):
    """(the new layout, None) after `change` ({panel: {key: value}}, from Arrange mode or Settings), or (None, why) when
    any of it is wrong: an unknown panel or key, a value of the wrong kind. Values out of range are clamped."""
    if not isinstance(change, dict) or not change:
        return None, "expected {panel: {key: value}}"
    new = clean_layout(current)
    for panel, keys in change.items():
        if panel not in PANELS or not isinstance(keys, dict) or not keys:
            return None, f"unknown panel {panel!r}" if panel not in PANELS else f"{panel}: expected {{key: value}}"
        if keys.get("reset") is True:
            new[panel] = copy.deepcopy(LAYOUT_DEFAULT[panel])
            continue
        for k, v in keys.items():
            if k == "corner":
                if v not in CORNERS:
                    return None, f"{panel}.corner must be one of {', '.join(CORNERS)}"
                new[panel]["corner"] = v
            elif k == "text":   # the panel's own text size, "" (or null): as all panels
                if v not in SIZES and v not in ("", None):
                    return None, f"{panel}.text must be one of {', '.join(SIZES)} or \"\" (as all panels)"
                new[panel]["text"] = v or ""
            elif k in LIMITS:
                n = _num(v, *LIMITS[k])
                if n is None:
                    return None, f"{panel}.{k} must be a number"
                new[panel][k] = round(n, 4)
            else:
                return None, f"{panel}: unknown key {k!r}"
    return new, None


# ---- items ----

def text(x, y, s, c, size="normal", bold=False, align="left"):
    return {"t": "text", "x": round(x, 1), "y": round(y, 1), "s": str(s), "c": c, "size": size, "bold": bool(bold), "align": align}


def rect(x, y, w, h, c=None, f=None, lw=1):
    return {"t": "rect", "x": round(x, 1), "y": round(y, 1), "w": round(w, 1), "h": round(h, 1), "c": c, "f": f, "lw": lw}


def circle(x, y, r, c=None, f=None, lw=1):
    return {"t": "circle", "x": round(x, 1), "y": round(y, 1), "r": round(r, 1), "c": c, "f": f, "lw": lw}


def line(pts, c, lw=1):
    return {"t": "line", "pts": [[round(x, 1), round(y, 1)] for x, y in pts], "c": c, "lw": lw}


def marker(x, y, kind, c, r=6, rot=0):
    return {"t": "marker", "x": round(x, 1), "y": round(y, 1), "kind": kind, "c": c, "r": r, "rot": round(rot, 1)}


def runs(x, y, parts, align="left"):
    """A line of (text, colour, size, bold) parts set one after another by the window, with the font's real widths;
    align "center": x is the line's middle, "right" its right end."""
    out = {"t": "runs", "x": round(x, 1), "y": round(y, 1), "runs": [[str(s), c, size, bool(b)] for s, c, size, b in parts]}
    if align != "left":
        out["align"] = align
    return out


def text_width(s, size="normal"):
    return len(str(s)) * CHAR_W.get(size, CHAR_W["normal"])


def fit(s, width, size="normal"):
    """`s` cut with … to fit `width` canvas units at `size`."""
    s = str(s)
    room = int(width / CHAR_W.get(size, CHAR_W["normal"]))
    return s if len(s) <= room else (s[:max(0, room - 1)].rstrip() + "…" if room > 1 else "")


def text_panel(pid, title, rows, pal, width=400, size="normal", subtitle=None):
    """A panel of text: a title (and a muted subtitle on its line), a rule, then `rows`. A row is a list of segments
    (text, colour key) set left to right, with an optional right-aligned last part: {"left": [...], "right": (text,
    key)}; the string "rule" is a thin line; None is a half-line gap. Colour keys are the palette's (title, text,
    muted, good, warn, bad, accent). The panel's height follows its rows."""
    lh, big = LINE_H.get(size, 20), "large"
    items, y = [], PAD
    head = fit(title, width - 2 * PAD, big)
    parts = [(head, pal["title"], big, True)]
    if subtitle and head == title:
        room = width - 2 * PAD - text_width(title, big) - CHAR_W[size] * 2
        if room > CHAR_W[size] * 4:
            parts.append(("  " + fit(subtitle, room, size), pal["muted"], size, False))
    items.append(runs(PAD, y, parts))
    y += LINE_H[big] + 4
    items.append(line([(PAD, y), (width - PAD, y)], pal["frame"]))
    y += 6
    for row in rows:
        if row is None:
            y += lh // 2
            continue
        if row == "rule":
            items.append(line([(PAD, y + 3), (width - PAD, y + 3)], pal["frame"]))
            y += 8
            continue
        if isinstance(row, dict):
            left, right = row.get("left") or [], row.get("right")
        else:
            left, right = row, None
        room_right = 0
        if right:
            rt, rk = right
            items.append(text(width - PAD, y, rt, pal.get(rk, pal["text"]), size, align="right"))
            room_right = text_width(rt, size) + 12
        room, parts = width - 2 * PAD - room_right, []
        for seg, key in left:
            if room <= CHAR_W[size]:
                break
            s = fit(seg, room, size)
            parts.append((s, pal.get(key, pal["text"]), size, key == "title"))
            room -= text_width(s, size)
        if parts:
            items.append(runs(PAD, y, parts))
        y += lh
    return {"id": pid, "w": width, "h": round(y + PAD - 2), "bg": pal["panel"], "frame": pal["frame"],
            "style": pal.get("style", "rounded"), "accent": pal["title"], "items": items}


# ---- what the panels say ----

def credits(v):
    """Credits as the page writes them (page.js `credits`): 950, 59k, 2.4M, 1.23B. The unit is picked by what the
    value rounds to, so 999,600 is "1.0M", not "1000k"."""
    v = float(v or 0)
    a = abs(v)
    if a >= 999.95e6:
        return f"{v / 1e9:.2f}B"
    if a >= 999.5e3:
        return f"{v / 1e6:.1f}M"
    if a >= 999.5:
        return f"{_half_up(v / 1e3)}k"
    return str(_half_up(v))


def body_what(b):
    """A body in a few words: its notable tag (ELW, WW, AW) or its subtype without "body", T for terraformable."""
    what = b.get("notable") or (b.get("subtype") or "").replace(" body", "").replace("Sudarsky class", "Class")
    return what + (" T" if b.get("terraformable") and b.get("notable") != "T" else "")


def codex_mark(guesses):
    """The strongest codex mark among a body's likely species, with the new colour: "✪ Cobalt", "✦ Grey" or ""."""
    for key, mark in (("codex_galaxy_new", "✪"), ("codex_new", "✦")):
        for g in guesses or []:
            if g.get(key):
                have = set(g.get("codex_have") or [])
                fresh = [v.split(" - ")[-1] for v in g.get("variants") or [] if v.split(" - ")[-1] not in have]
                return f"{mark} {' or '.join(fresh)}" if fresh else mark
    return ""


def stop_glyph(n):
    """A stop's number in the suggested order, as Here's schematic writes it (page.js stopGlyph): ① to ⑳, then (21)."""
    return chr(0x245F + n) if 1 <= n <= 20 else f"({n})"


def system_rows(detail, highlight, bio_min, codex=True, first=None):
    """The system panel's bodies: what is left to do on each body worth it, then the valuable ones already done.
    [{name, what, status, value, key (warn/accent/good), mark, todo, dist, stops}], the credits left in the whole
    system, and how many bodies have something left that is under your levels (not listed; a body someone else mapped
    is neither).
    S30: the bodies you scanned are listed by the suggested order (plan_items, as Now and Here's schematic): `stops`
    their numbers in it (two on a body with both mapping and bio), the rows by their first number. A body you have not
    scanned (Spansh's record only: the order cannot know it yet) is listed by its value as before, unnumbered, after
    them; the done ones last."""
    plan = plan_items((detail or {}).get("leaving"), highlight, bio_min, codex, first)
    stops = {}
    for n, it in enumerate(plan, 1):
        stops.setdefault(it["body"], {}).setdefault("n", []).append(n)
        stops[it["body"]].setdefault("kinds", set()).add(it["kind"])
    # mapped by someone else before you scanned it (your Scan's WasMapped): never a stop (the page's rule, plan_items),
    # and not "under your levels" either, whatever its mapping would add
    others = {u.get("body") for u in ((detail or {}).get("leaving") or {}).get("unmapped") or [] if u.get("mapped_before")}
    rows, left_all, under = [], 0, 0
    for b in (detail or {}).get("bodies") or []:
        if b.get("type") == "Star":
            continue
        vp = b.get("value_parts") or {}
        map_left, bio_left = vp.get("carto_left") or 0, vp.get("bio_left") or 0
        left_all += map_left + bio_left
        organics = b.get("organics") or []
        partial = [o for o in organics if not o.get("done") and not o.get("lost")]
        mapped = bool(b.get("mapped") or b.get("first_mapped"))
        special = bool(b.get("notable") or b.get("terraformable"))
        st = stops.get(b.get("name"))
        if st:   # in the suggested order: what it holds there decides
            to_map, to_land = "map" in st["kinds"], "bio" in st["kinds"]
        elif b.get("scanned"):   # yours, and not in the order: under your levels (or nothing left)
            to_map = to_land = False
        else:
            to_map = not mapped and b.get("type") == "Planet" and map_left > 0 and (map_left >= highlight or special)
            to_land = bool(partial) or bio_left >= bio_min
        base = {"name": b.get("name", "?"), "what": body_what(b), "mark": codex_mark(b.get("bio_guess")) if to_land else "",
                "dist": b.get("dist_ls") if b.get("dist_ls") is not None else 1e12, "stops": st["n"] if st else []}
        if partial and to_land:
            o = partial[0]
            rows.append(dict(base, status=f"{o.get('genus', 'bio')} {o.get('samples', 0)}/3", value=bio_left + (map_left if to_map else 0),
                             key="accent", todo=True))
        elif to_land or to_map:
            status = "MAP + LAND" if to_land and to_map else "TO LAND" if to_land else "TO MAP"
            rows.append(dict(base, status=status, value=(bio_left if to_land else 0) + (map_left if to_map else 0), key="warn", todo=True))
        elif (mapped and (b.get("value_max") or 0) >= highlight) or (organics and all(o.get("done") for o in organics)
                                                                      and (b.get("value_max") or 0) >= bio_min):
            rows.append(dict(base, status="MAPPED" if mapped else "SAMPLED", value=None, key="good", todo=False))
        if not to_land and not to_map and (bio_left or (map_left and not mapped and b.get("name") not in others)):
            under += 1
    rows.sort(key=lambda r: (not r["todo"], not r["stops"], r["stops"][0] if r["stops"] else 0, r["dist"]))
    return rows, left_all, under


def system_panel(detail, pal, size="normal", highlight=500_000, bio_min=10_000_000, max_rows=8, codex=True, first=None):
    """The system panel ("worth your time"): None when no body is worth listing. codex, first: as plan_items (the
    config's codex_interesting, the first stop you picked here)."""
    rows, left_all, under = system_rows(detail, highlight, bio_min, codex, first)
    if not rows:
        return None
    shown = rows[:max_rows]
    lines = []
    for r in shown:
        left = ([("".join(stop_glyph(n) for n in r["stops"]) + " ", "accent")] if r["stops"] else []) + \
            [(r["name"] + " ", "title"), (r["what"], "text" if r["todo"] else "muted")]
        if r["mark"]:
            left.append(("  " + r["mark"], "good" if r["mark"].startswith("✪") else "accent"))
        right = f"{r['status']} {credits(r['value'])}" if r["value"] else r["status"]
        lines.append({"left": left, "right": (right, r["key"])})
    curious = [f"{b.get('name')} {c.get('tag')}" for b in (detail or {}).get("bodies") or [] for c in (b.get("curiosities") or [])[:1]]
    if curious:
        lines.append([("Also here: ", "muted"), (", ".join(curious), "text")])
    lines.append("rule")
    foot = [("Left here: ", "muted"), (credits(left_all), "accent")]
    if len(rows) > len(shown):
        foot.append((f" · {len(rows) - len(shown)} more", "muted"))
    if under:
        foot.append((f" · {under} under your levels", "muted"))
    lines.append(foot)
    n = len([b for b in (detail or {}).get("bodies") or []])
    return text_panel("system", (detail or {}).get("name") or "System", lines, pal, width=440, size=size,
                      subtitle=f"{n} bod{'y' if n == 1 else 'ies'}")


def run_pays(value, factor=1):
    """What a sample run pays, known from sample 1 (S62; page.js `runPays`): "1.0M (×5: 5.0M)" with the first footfall
    bonus, else "1.0M"; "" when unknown. `value` is the species' own, never one with the ×5 already in."""
    if not value:
        return ""
    return f"{credits(value)} (×{factor}: {credits(value * factor)})" if factor and factor > 1 else credits(value)

def body_panel(b, pal, size="normal", high_gravity=2.0, colony=None):
    """The Target panel's body (D1; it was the body panel): what the body is, what mapping it is worth, and its life (each likely species with its codex
    mark, colony distance and value, or what it could be before the DSS), and whether it is worth landing. None for
    a star or nothing known."""
    if not b or b.get("type") == "Star":
        return None
    colony = colony or {}
    vp = b.get("value_parts") or {}
    factor = vp.get("bio_factor") or 1
    facts = []
    if b.get("type") == "Planet":
        facts.append(("landable" if b.get("landable") else "not landable", "text" if b.get("landable") else "muted"))
        g = b.get("gravity")
        if isinstance(g, (int, float)):
            facts += [(" · ", "muted"), (f"{g:.2f} g", "warn" if g >= high_gravity else "good")]
        atm = b.get("atmosphere")
        if atm and atm != "None":
            facts += [(" · ", "muted"), (atm.replace(" atmosphere", ""), "text")]
        t = b.get("temperature")
        if isinstance(t, (int, float)):
            facts += [(" · ", "muted"), (f"{round(t)} K", "text")]
    lines = [facts] if facts else []
    worth = []
    if b.get("mapped") or b.get("first_mapped"):
        worth.append(("mapped", "good"))
    elif vp.get("carto_left"):
        worth += [("Map: ", "muted"), (credits(vp["carto_left"]), "accent")]
    if b.get("first_discovered"):
        worth += [(" · " if worth else "", "muted"), ("first discovered", "good")]
    if b.get("geo"):
        worth += [(" · " if worth else "", "muted"), (f"{b['geo']} geo", "text")]
    if worth:
        lines.append(worth)
    bio_rows = []
    running = {o.get("genus"): o for o in b.get("organics") or []}
    for o in b.get("organics") or []:
        if o.get("lost"):
            bio_rows.append({"left": [(o.get("species") or o.get("genus") or "?", "text"), ("  lost: sample again", "bad")]})
        elif o.get("done"):   # finished: as Here's ✓, with what it pays
            bio_rows.append({"left": [(o.get("species") or o.get("genus") or "?", "muted"), ("  ✓", "good")],
                             "right": (credits((o.get("value") or 0) * factor), "muted")})
        else:
            bio_rows.append({"left": [(o.get("species") or o.get("genus") or "?", "text"), (f"  {o.get('samples', 0)}/3", "accent")]
                             + ([(f" · {colony[o['genus'].lower()]} m", "muted")] if o.get("genus") and colony.get(o["genus"].lower()) else []),
                             "right": (run_pays(o.get("value"), factor) or credits(0), "accent")})
    for g in b.get("bio_guess") or []:
        if g.get("genus") in running:
            continue
        mark = codex_mark([g])
        left = [(g.get("best") or g.get("genus") or "?", "text")]
        if mark:
            left.append(("  " + mark, "good" if mark.startswith("✪") else "accent"))
        if colony.get((g.get("genus") or "").lower()):
            left.append((f" · {colony[g['genus'].lower()]} m", "muted"))
        bio_rows.append({"left": left, "right": ("≤" + credits((g.get("value") or 0) * factor), "text")})
    opts = b.get("bio_options")
    if opts and not b.get("genera"):
        n = b.get("bio") or 0
        bio_rows.append([(f"{n} signal{'s' if n != 1 else ''}, not DSS'd: ", "muted"),
                         (" or ".join(x.get("genus", "?") for x in opts.get("genera") or []) or "?", "text")])
        bio_rows.append({"left": [("could pay", "muted")],
                         "right": (f"{credits((opts.get('low') or 0) * factor)} to {credits((opts.get('high') or 0) * factor)}", "text")})
    if bio_rows:
        lines.append("rule")
        lines += bio_rows
        if vp.get("bio_left"):
            lines.append([("Worth landing: up to ", "good"), (credits(vp["bio_left"]), "good"),
                          (" (×5 first footfall)" if factor == 5 else "", "muted")])
    if not lines:
        return None
    return text_panel("body", b.get("name") or "Body", lines, pal, width=420, size=size, subtitle=body_what(b))


def surface_m(lat1, lon1, lat2, lon2, radius):
    """Great-circle metres between two points on a body of `radius` m (as the server's surface_m)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def bearing(lat1, lon1, lat2, lon2):
    """Degrees from north, from the first point to the second (as the server's surface_bearing)."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    return math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                   math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360


def radar_xy(here, lat, lon, cx, cy, r, rng):
    """Where a point goes on the heading-up radar (centre cx, cy; radius r for `rng` m), and whether it is beyond the
    edge (then on the rim, in its direction). here: {lat, lon, heading, radius}."""
    d = surface_m(here["lat"], here["lon"], lat, lon, here["radius"])
    rel = math.radians(bearing(here["lat"], here["lon"], lat, lon) - (here.get("heading") or 0))
    k = min(d / rng, 1.0) if rng else 1.0
    return cx + r * k * math.sin(rel), cy - r * k * math.cos(rel), d > rng


def radar_panel(surf, pal, size="normal", radar_range=800):
    """The surface radar, heading up: you at the centre, N on the rim; the sample points of the run in progress with
    their colony rings (red while you are inside one, green once clear), other runs' faint, tagged plants, the ship and
    your rigs; what the next sample needs underneath. None away from a body. Shown with nothing on it too, as the page's
    surface map is (the author, 2026-10-25: hovering low with no run, plant, pin or ship, it hid, useless when looking
    for geology): you, N and the edge's distance."""
    if not surf or surf.get("lat") is None or not surf.get("radius"):
        return None
    bio = surf.get("bio") or []
    cur = next((s for s in bio if s.get("current")), None)
    pins = surf.get("pins") or []
    rng = max(radar_range, (cur.get("need") or 0) * 1.4 if cur else 0)
    w, r = 300, 118
    lh_small = LINE_H["small"]
    title = cur["species"] if cur else surf.get("body") or "Surface"
    items = [runs(PAD, PAD, [(fit(title, w - 2 * PAD, "large"), pal["title"], "large", True)])]
    head = PAD + LINE_H["large"]
    if cur and (cur.get("samples") or 0) < 3:   # the run's next sample, on a line of its own (a long name fills the title)
        items.append(runs(PAD, head, [(f"sample {(cur.get('samples') or 0) + 1} of 3", pal["accent"], size, False)]))
        head += LINE_H.get(size, 20)
    cx, cy = w / 2, head + 14 + r
    items += [circle(cx, cy, r, pal["frame"]), circle(cx, cy, r / 2, pal["frame"])]
    north = math.radians(-(surf.get("heading") or 0))
    items.append(text(cx + (r + 8) * math.sin(north) - 4, cy - (r + 8) * math.cos(north) - 8, "N", pal["muted"], "small"))
    here = {"lat": surf["lat"], "lon": surf["lon"], "heading": surf.get("heading") or 0, "radius": surf["radius"]}
    # your trail on this body this visit (the author, 2026-10-25: wanted here too, not only on the page's map), under
    # everything: the stretches within the edge only (a point beyond it would be pressed onto the rim), joined to you
    seg, segs = [], []
    for lat, lon in list(surf.get("trail") or []) + [[surf["lat"], surf["lon"]]]:
        x, y, beyond = radar_xy(here, lat, lon, cx, cy, r, rng)
        if beyond:
            segs.append(seg)
            seg = []
        else:
            seg.append((x, y))
    segs.append(seg)
    items += [line(s, pal["muted"], lw=1.5) for s in segs if len(s) > 1 and len(surf.get("trail") or []) > 1]
    for s in sorted(bio, key=lambda s: bool(s.get("current"))):   # the run in progress drawn last, on top
        c = (pal["good"] if s.get("clear") else pal["bad"]) if s.get("current") else pal["muted"]
        for p in s.get("points") or []:
            x, y, beyond = radar_xy(here, p["lat"], p["lon"], cx, cy, r, rng)
            if s.get("need") and not beyond:
                items.append(circle(x, y, s["need"] / rng * r, c, lw=2 if s.get("current") else 1))
            items.append(marker(x, y, "dot", c, r=4 if s.get("current") else 3))
    for t in surf.get("tags") or []:
        x, y, _ = radar_xy(here, t["lat"], t["lon"], cx, cy, r, rng)
        items.append(marker(x, y, "dot", pal["accent"], r=4))
    ship = surf.get("ship")
    if ship:
        x, y, beyond = radar_xy(here, ship["lat"], ship["lon"], cx, cy, r, rng)
        items.append(marker(x, y, "cross", pal["text"], r=6))
        dist = ship.get("dist") or 0
        items.append(text(x + 8, y + 2, f"ship {dist / 1000:.1f} km" if dist >= 1000 else f"ship {round(dist)} m", pal["muted"], "small"))
    for rig in surf.get("rigs") or []:
        x, y, _ = radar_xy(here, rig["lat"], rig["lon"], cx, cy, r, rng)
        items.append(rect(x - 4, y - 4, 8, 8, pal["warn"], None))
        items.append(text(x + 6, y - 6, str(rig.get("n", "")), pal["warn"], "small"))
    # #16: surface pins; the active one (on the rim when beyond the edge) with its name
    for p in sorted(pins, key=lambda p: bool(p.get("active"))):
        if p.get("reached") and not p.get("active"):
            continue
        x, y, beyond = radar_xy(here, p["lat"], p["lon"], cx, cy, r, rng)
        c = pal["accent"] if p.get("active") else pal["muted"]
        items.append(marker(x, y, "diamond", c, r=6 if p.get("active") else 4))
        if p.get("active") and not beyond:
            items.append(text(x + 8, y - 8, fit(p.get("name") or "", 120, "small"), c, "small"))
    items.append(marker(cx, cy, "arrow", pal["text"], r=9))
    y = cy + r + 14
    act = next((p for p in pins if p.get("active")), None)
    if act:   # #16: the active pin, one line: "📍 Wreck 12.4 km, 30° left"
        d, t = act.get("dist") or 0, act.get("turn")
        way = act.get("way") or "" if t is None else "ahead" if abs(t) < 10 else f"{abs(t)}° {'right' if t > 0 else 'left'}"
        items.append(text(PAD, y, fit(f"📍 {act.get('name') or ''} {d / 1000:.1f} km, {way}" if d >= 1000 else
                                      f"📍 {act.get('name') or ''} {round(d)} m, {way}", w - 2 * PAD, "small"), pal["accent"], "small"))
        y += lh_small + 2
    scale = f"edge {rng / 1000:.1f} km" if rng >= 1000 else f"edge {round(rng)} m"
    items.append(text(w - PAD, y, scale, pal["muted"], "small", align="right"))
    if cur and cur.get("need"):
        near = min((p.get("dist") or 0 for p in cur.get("points") or []), default=None)
        if cur.get("clear"):
            items.append(text(PAD, y, f"Clear: sample here ({cur['need']} m from all)", pal["good"], "small"))
        elif near is not None:
            items.append(text(PAD, y, f"Next: {cur['need']} m from all · nearest {round(near)} m", pal["warn"], "small"))
    return {"id": "radar", "w": w, "h": round(y + lh_small + PAD), "bg": pal["panel"], "frame": pal["frame"],
            "style": pal.get("style", "rounded"), "accent": pal["title"], "items": items}


STAR_WORDS = {"N": "neutron star", "H": "black hole", "SupermassiveBlackHole": "black hole", "TTS": "T Tauri star",
              "AeBe": "Herbig Ae/Be star", "W": "Wolf-Rayet", "WN": "Wolf-Rayet", "WNC": "Wolf-Rayet", "WC": "Wolf-Rayet",
              "WO": "Wolf-Rayet", "C": "carbon star", "CN": "carbon star", "CJ": "carbon star", "MS": "MS-type star",
              "S": "S-type star", "L": "L dwarf", "T": "T dwarf", "Y": "Y dwarf", "X": "exotic"}


def star_words(code):
    """The arrival star in a few words from its journal class ("K" -> "K star", "DA" -> "white dwarf"), with ⛽ when it
    can be scooped (KGBFOAM) and ⚡ for a neutron star or white dwarf (a supercharge)."""
    if not code:
        return ""
    c = str(code)
    if c.startswith("D"):
        return "white dwarf ⚡"
    if c == "N":
        return "neutron star ⚡"
    giant = "supergiant" if "SuperGiant" in c else "giant" if "Giant" in c else None
    words = STAR_WORDS.get(c) or (f"{c.split('_')[0]} {giant}" if giant else f"{c.split('_')[0]} star" if len(c) <= 3
                                  else c.replace("_", " "))
    return words + (" ⛽" if c[:1] in "KGBFOAM" and len(c.split("_")[0]) == 1 else "")


# your reputation with a faction by the journal's MyReputation (-100..100), as the game's levels (Inara's thresholds)
REP_LEVELS = ((-90, "Hostile"), (-35, "Unfriendly"), (4, "Neutral"), (35, "Cordial"), (90, "Friendly"))


def rep_level(rep):
    """The game's word for a MyReputation figure: Hostile, Unfriendly, Neutral, Cordial, Friendly or Allied; None
    without one."""
    if not isinstance(rep, (int, float)) or isinstance(rep, bool):
        return None
    return next((word for top, word in REP_LEVELS if rep <= top), "Allied")


def strip_panel(info, pal, size="normal"):
    """The system strip: two short lines across the top, centred in their box. Line 1: the system, its region, the
    star. Line 2: the distance from Sol, now and max, your first discovery; then bodies, found of total, discovered by
    you, mapped of planets, whether Spansh knows the system (the author, 2026-10-10). In a populated system the top
    row's right side has its security and your reputation with its controlling faction, in the region's font, Hostile
    in red (the author, 2026-10-14). info: {name, region, star, sol_ly, total, found, all_found, honked, value_now,
    value_max, first, firsts, mapped, planets, in_spansh, standing: {security, faction, rep}, mining}. While you mine in a
    ring (mining D), a third line: `mining`, the mining strip in words. Its width follows its text."""
    if not info or not info.get("name"):
        return None
    sep = ("  ·  ", pal["muted"], size, False)

    def line(first, rest):
        parts = [first] if first else []
        for text, key in rest:
            if text:
                parts.extend([sep, (text, pal[key], size, False)] if parts else [(text, pal[key], size, False)])
        return parts
    one = line((info["name"], pal["title"], "large", True), [(info.get("region"), "muted"), (star_words(info.get("star")), "text")])
    rest = [(f"Sol {info['sol_ly']:,.0f} ly" if info.get("sol_ly") is not None else "", "muted")]
    if info.get("value_max"):
        rest += [(f"now {credits(info.get('value_now'))}", "text"), (f"max {credits(info['value_max'])}", "accent")]
    rest.append(("🏁 first discovered" if info.get("first") else "", "good"))
    total, found = info.get("total"), info.get("found")
    rest.append((f"{total} bod{'y' if total == 1 else 'ies'}" if total else "", "text"))
    if total:
        rest.append((f"{found or 0}/{total} found" + (" ✓" if info.get("all_found") else ""), "good" if info.get("all_found") else "warn"))
    elif not info.get("honked"):
        rest.append(("not honked", "warn"))
    rest += [(f"🏁 {info['firsts']}" if info.get("firsts") else "", "good"),
             (f"🗺 {info.get('mapped') or 0}/{info['planets']}" if info.get("planets") else "", "text")]
    if info.get("in_spansh") is not None:
        old = info["in_spansh"] and info.get("spansh_old")   # #11: its data predates Odyssey, worth a rescan
        rest.append(("Spansh ✓ (pre-Odyssey)" if old else "Spansh ✓" if info["in_spansh"] else "Spansh ✗ (new to it)",
                     "warn" if old else "muted" if info["in_spansh"] else "warn"))
    two = line(None, rest)
    three = [(info["mining"], pal["accent"], size, False)] if info.get("mining") else None
    lines = [one] + ([two] if two else []) + ([three] if three else [])
    st = info.get("standing") or {}
    level = rep_level(st.get("rep"))
    right = [(x, pal["bad"] if x == "Hostile" else pal["muted"], size, False)
             for x in ([st["security"]] if st.get("security") else []) + ([level] if level else [])]
    right = [p for i, part in enumerate(right) for p in ([sep, part] if i else [part])]
    wide = lambda ln: sum(text_width(t, s) for t, _, s, _ in ln)
    # the top row stays centred: room for the right side on both sides of it, so the two never meet
    need = max([wide(ln) for ln in lines] + ([wide(one) + 2 * (wide(right) + 24)] if right else []))
    width = round(min(CANVAS_W - 40, PAD * 2 + 10 + need))
    items, y = [], PAD - 2
    for i, ln in enumerate(lines):
        items.append(runs(width / 2, y, ln, align="center"))
        if i == 0 and right:   # level with the region's line: the large name's row, its baseline lower
            items.append(runs(width - PAD - 4, y + (LINE_H["large"] - LINE_H.get(size, 20)) / 2 + 1, right, align="right"))
        y += LINE_H["large"] if i == 0 else LINE_H.get(size, 20)
    return {"id": "strip", "w": round(width), "h": round(y + PAD - 4), "bg": pal["panel"], "frame": pal["frame"],
            "style": pal.get("style", "rounded"), "accent": pal["title"], "items": items}


def star_hazard(code):
    """What to mind arriving at this star (page.js hazardNote: throttle down on arrival): "neutron star", "white dwarf",
    "black hole", or "" for an ordinary star."""
    c = str(code or "")
    return "neutron star" if c == "N" else "white dwarf" if c.startswith("D") \
        else "black hole" if c in ("H", "SupermassiveBlackHole") else ""


def to_full_text(s):
    """Seconds to a full tank as the page writes them (page.js toFullText): "38 s", "2 min 05"."""
    s = int(s)
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60:02d}"


def fuel_t(x):
    """Tonnes of fuel as the page writes them (page.js fuelT): a short hop burns a few kilograms."""
    return f"{x:.1g}" if x < 0.1 else f"{x:.1f}"


NOTABLE_WORDS = ("ELW", "WW", "AW", "T")   # Nearby's notable bodies, in its order (page.js notable)
TARGET_W = 420


def target_system_panel(t, pal, size="normal"):
    """The Target panel's system (D1): the system targeted in game (in the galaxy map, or the next jump of a route
    plotted there) when no body is. What is known of it (TARGET_WORDS, Spansh's bodies of its count, EDSM's), its star
    (⛽, or ✕ not scoopable; ⚠ throttle down at a neutron star, white dwarf or black hole), the jump (the distance, its
    fuel and the max-range jumps left after it, or out of range) and, in the Nearby sphere, what it could pay and its
    notable bodies. t: {name, status (None while the lookup runs: "checking…"), source, known, count, edsm, star_class,
    hop: {ly, fuel, left, reach}, distance, value: {carto, bio}, notable, remaining (the route's jumps left, this one
    included), route_check (S11: the followed route's target_check, its one overlay place)}. None without a name."""
    if not t or not t.get("name"):
        return None
    room, rows = TARGET_W - 2 * PAD, []
    left = t.get("remaining")   # with a route plotted in game, the target is its next jump
    if isinstance(left, int) and not isinstance(left, bool) and left > 1:
        rows.append([("next jump of your route · ", "muted"), (f"{left} to go", "text")])
    tc = route_check_parts(t.get("route_check"))
    if tc:
        rows += flow(tc, room, size)
    status = t.get("status")
    if status is None:
        rows.append([("checking…", "muted")])
    else:
        words, key = TARGET_WORDS.get(status, (status, "muted"))
        row = [(words + (" (known to EDSM only)" if t.get("source") == "edsm" else ""), key)]
        if t.get("count"):
            row.append((f" · {t.get('known') or 0}/{t['count']} known", "muted"))
        elif t.get("known"):
            row.append((f" · {t['known']} known", "muted"))
        e = t.get("edsm")
        if e:
            row.append((" · EDSM: not logged" if e.get("missing") else
                        f" · EDSM {e.get('known') or 0}" + (f"/{e['count']}" if e.get("count") else ""), "muted"))
        rows += flow(row, room, size)
    sc = t.get("star_class")
    if sc:
        scoop = bool(re.match(r"^[OBAFGKM](_|$)", sc))
        row = [(star_words(sc), "good" if scoop else "text")] + ([] if scoop else [(" · ✕ not scoopable", "warn")])
        if star_hazard(sc):
            row.append((" · ⚠ throttle down", "bad"))
        rows += flow(row, room, size)
    hop = t.get("hop") or {}
    ly = hop.get("ly") if hop.get("ly") is not None else t.get("distance")
    if isinstance(ly, (int, float)):
        row = [(f"{ly:.1f} ly", "text")]
        if hop.get("reach") is False:
            row.append((" · out of range" + (f" (needs {fuel_t(hop['fuel'])} t)" if hop.get("fuel") is not None else ""), "bad"))
        elif hop.get("fuel") is not None:
            left = hop.get("left") or 0
            row.append((f" · {fuel_t(hop['fuel'])} t · leaves {left} max jump{'' if left == 1 else 's'}", "muted"))
        rows += flow(row, room, size)
    v, n = t.get("value") or {}, t.get("notable") or {}
    row = ([(f"~{credits(v['carto'])} scan+map", "accent")] if v.get("carto") else []) \
        + ([(" · " if v.get("carto") else "", "muted"), (f"bio up to {credits(v['bio'])}", "accent")] if v.get("bio") else [])
    marks = [k + (f"×{n[k]}" if n[k] > 1 else "") for k in NOTABLE_WORDS if n.get(k)]
    if marks:
        row.append(((" · " if row else "") + " ".join(marks), "good"))
    if row:
        rows += flow(row, room, size)
    return text_panel("body", "➜ " + t["name"], rows, pal, width=TARGET_W, size=size)


PAD_W = 300
SLOT_GREEN, SLOT_RED = "#3AD16B", "#E0453A"   # the slot's own lights: green and red whatever the theme


def pad_map_items(m, pal, x0, y0, w):
    """The pad diagram (#12) as draw items in a box `w` wide from (x0, y0), and its height: a starport seen from the slot
    looking in (12 wall sectors, 3 depths, outside near the slot; the slot's lights across the far wall, green on the
    right as the words assume) or a carrier from above, bow up (a squadron carrier's two decks side by side), your pad
    filled in. m: outrider.pads.where's map ({kind, pad, pads, outline: a carrier deck's})."""
    items, pad = [], m.get("pad")
    if m.get("kind") == "starport":
        import outrider.pads as P
        R = min(w / 2 - 6, 110)
        cx, cy = x0 + w / 2, y0 + R + 2
        for k, sc in enumerate(P.SHELLS):
            r = R * sc
            pts = [(cx + math.cos(math.radians(15 + 30 * j)) * r, cy + math.sin(math.radians(15 + 30 * j)) * r) for j in range(13)]
            items.append(line(pts, pal["frame"] if k else pal["muted"], 1))
        for j in range(12):
            a = math.radians(15 + 30 * j)
            r0 = R * P.SHELLS[-1]
            items.append(line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * R, cy + math.sin(a) * R)],
                              pal["frame"], 1))
        slot = R * P.SHELLS[-1] * 0.8
        items.append(line([(cx - slot, cy), (cx - 2, cy)], SLOT_RED, 3))
        items.append(line([(cx + 2, cy), (cx + slot, cy)], SLOT_GREEN, 3))
        for n, (sec, d, k, of) in enumerate(m.get("pads") or [], 1):
            dx, dy = P.SECTORS[sec]
            r = R * (P.SHELLS[d] + P.SHELLS[d + 1]) / 2
            a = math.atan2(dy, dx) + (k - (of + 1) / 2) * math.radians(9)
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            me = n == pad
            items.append(circle(x, y, 9 if me else 3.2, pal["good"] if me else pal["muted"], pal["good"] if me else None, 2 if me else 1))
            if me:
                items.append(runs(x, y - 7, [(str(pad), pal["panel"], "small", True)], align="center"))
        items.append(runs(cx, cy + R + 4, [("seen from the slot, looking in", pal["muted"], "small", False)], align="center"))
        return items, 2 * R + 6 + LINE_H["small"]
    boxes = m.get("pads") or []
    if not boxes:
        return items, 0
    decks = (26, -26) if m.get("kind") == "squadron" else (0,)
    span = 52 * len(decks) + 4
    u = min(2.6, (w - 8) / span)
    cx, top = x0 + w / 2, y0 + LINE_H["small"]
    outline = m.get("outline") or [list(p) for p in outrider_pads.CARRIER_OUTLINE]
    cy = top + 46 * u
    items.append(runs(cx, y0, [("bow ▲", pal["muted"], "small", False)], align="center"))
    for xo in decks:
        hx = cx + xo * u
        items.append(line([(hx + px * u, cy + py * u) for px, py in [*outline, outline[0]]], pal["muted"], 1))
    for n, (x, y, bw, bh) in enumerate(boxes, 1):
        me = n == pad
        items.append(rect(cx + x * u, cy + y * u, bw * u, bh * u, pal["good"] if me else pal["frame"], pal["good"] if me else None,
                          2 if me else 1))
        if me or bw >= 7:   # the small pads are too small to number, but yours
            items.append(runs(cx + (x + bw / 2) * u, cy + (y + bh / 2) * u - 8,
                              [(str(n), pal["panel"] if me else pal["muted"], "small", me)], align="center"))
    return items, LINE_H["small"] + 86 * u + 4


def pad_panel(d, pal, size="normal", pid="radar"):
    """The Surface radar's place while docking (#3, the author 2026-10-14: the pad number in large letters; at first the
    Target panel's, moved the same day: the radar's place is free in space), panel id `pid`: the station's name,
    then "PAD 34" (FONT_PX huge); #12: where it is ("at the back · up on your right") and, at a starport or carrier
    with [overlay] pad_diagram on, the diagram (pad_map_items). A refusal: "Docking denied" and its words. d:
    State.docking_shown's. None without either."""
    if not d:
        return None
    station = d.get("station") or "Docking"
    if d.get("pad") is not None:
        p = text_panel(pid, "🛬 " + station, [], pal, width=PAD_W, size=size)
        y = p["h"] - PAD + 2
        p["items"].append(runs(PAD_W / 2, y, [(f"PAD {d['pad']}", pal["good"], "huge", True)], align="center"))
        y += LINE_H["huge"]
        if d.get("where"):
            for row in flow([((" " if i else "") + x, "text") for i, x in enumerate(d["where"].split())], PAD_W - 2 * PAD, size):
                p["items"].append(runs(PAD_W / 2, y, [(t, pal["text"], size, False) for t, _ in row], align="center"))
                y += LINE_H[size]
            y += 6
        if d.get("map"):
            items, h = pad_map_items(d["map"], pal, PAD, y, PAD_W - 2 * PAD)
            p["items"] += items
            y += h
        p["h"] = round(y + PAD)
        return p
    if d.get("words"):
        words = d["words"].split()   # word by word, so the reason wraps rather than being cut with …
        rows = [[("Docking denied", "bad")]] + flow([((" " if i else "") + w, "warn") for i, w in enumerate(words)],
                                                    PAD_W - 2 * PAD, size)
        return text_panel(pid, "🛬 " + station, rows, pal, width=PAD_W, size=size)
    return None


# ---- the Now panel: the page's Now view, condensed (the author, 2026-10-10) ----

# supercruise seconds from the arrival star on the page's community curve (page.js scSeconds): a rough guide
SC_KNEE = 7.5 * math.log(2000) - 20
TARGET_WORDS = {"checking": ("checking…", "muted"), "unreported": ("never reported", "good"), "no bodies": ("no scan data", "warn"),
                "partial": ("partly scanned", "warn"), "explored": ("fully scanned", "muted"), "visited": ("visited", "muted")}
ARRIVAL_SECONDS = 20   # the arrival verdict stays this long after the jump, as on Now
NOW_W = 520
BIO_W = 470


def _half_up(x):
    return math.floor(x + 0.5)   # JavaScript's Math.round, so the panel's figures are the page's


def sc_seconds(ls):
    if not isinstance(ls, (int, float)) or isinstance(ls, bool) or not math.isfinite(ls) or ls < 0:
        return None
    return max(15, 7.5 * math.log(max(ls, 1)) - 20) if ls <= 2000 else SC_KNEE + (ls - 2000) * (360 - SC_KNEE) / 98000


def sc_text(sec):
    return f"~{max(10, _half_up(sec / 5) * 5)} s" if sec < 90 else f"~{_half_up(sec / 60)} min"


def route_check_parts(tc):
    """S11's mark for the Target panel (page.js targetCheckHtml's words): the followed route's next stop targeted, a
    later stop of it, or another system. [] without a check."""
    if not tc or not tc.get("next"):
        return []
    if tc.get("ok"):
        return [("✓ the next stop of your route", "good")]
    n = tc.get("ahead") or 0
    if n > 0:
        return [(f"↷ {n} stop{'' if n == 1 else 's'} ahead on your route", "muted")]
    return [("⚠ not the next stop: ", "bad"), (tc["next"], "text")]


def route_parts(route):
    """The route's next stop as Now gives it (page.js hwyLineHtml / surveyLineHtml, short): {kind: "highway" |
    "riches" (the survey slot), summary: highway_summary() or survey_summary()} -> (text, colour key) parts, or []
    with nothing to say."""
    s = (route or {}).get("summary")
    if not s:
        return []
    hw = route.get("kind") == "highway"
    k = None if hw else survey_kind(s.get("kind"))   # the survey slot's kinds: outrider.riches.SURVEY_KINDS
    glyph, name = ("🛣", "Highway") if hw else (k.glyph, k.name)
    left = None if hw else (lambda n: left_words(s.get("kind"), n))
    head = [(glyph + " ", "accent")]
    if s.get("complete"):
        return head + [(f"{name} complete", "good")]
    if s.get("off_route"):
        nr = s.get("nearest") if hw else None
        return head + [("Off Route: Detour", "warn")] + ([(f" · nearest {nr['name']} {nr['distance']:.1f} ly", "muted")]
                                                         if nr and isinstance(nr.get("distance"), (int, float)) else [])
    n = s.get("next")
    here = [(" · " + left(s["left_here"]), "warn")] if left and s.get("left_here") else []
    if not n:
        return head + [(f"To {s.get('destination') or ''}", "text")] + here
    start = s.get("index") == 0 and s.get("at") is None
    parts = head + [("Start: " if start else "Next: ", "warn"), ((f"{n['station']}, " if n.get("station") else "") + n["name"], "title")]
    if hw and n.get("neutron"):
        parts.append((" · ⚡ neutron", "good"))
    if (n.get("jumps") or 0) > 1:
        parts.append((f" · {n['jumps']} jumps", "muted"))
    if isinstance(n.get("distance"), (int, float)):
        parts.append((f" · {n['distance']:.1f} ly", "muted"))
    parts.append((f" · {s.get('index')} of {s.get('total')}", "muted"))
    if not hw and s.get("skipped"):   # S12: finished systems the next stop passes over
        parts.append((f" · skipping {s['skipped']} done", "muted"))
    if hw and s.get("refuel_here"):
        parts.append((" · ⛽ refuel here", "warn"))
    elif hw and s.get("refuel_in") is not None:
        parts.append((f" · refuel in {s['refuel_in']} jump{'' if s['refuel_in'] == 1 else 's'}", "muted"))
    hv = s.get("heavy") if hw else None
    if hv and isinstance(hv.get("need_t"), (int, float)) and isinstance(hv.get("have_t"), (int, float)):
        jump = f"the jump to {hv.get('next')}" if (hv.get("hop") or 1) > 1 else "the next jump"
        parts.append((f" · ⚠ too much fuel for {jump}: ≤ {math.floor(hv['need_t'])} t, you have {_half_up(hv['have_t'])} t", "bad"))
    sh = s.get("short") if hw else None
    if sh and isinstance(sh.get("jumps"), int) and sh.get("refuel_at"):
        parts.append((f" · {'⛽' if sh.get('here_refuel') else '⚠'} {short_text(sh)}", "warn" if sh.get("here_refuel") else "bad"))
    return parts + here


def short_text(sh):
    """S1's words (page.js hwyShortText): the fuel won't reach the refuel stop, or at one, how much to scoop."""
    where = {"refuel": "the refuel stop", "end": "the destination"}.get(sh.get("end"), "the stretch ahead")
    n = sh["jumps"]
    need, top = sh.get("need_t"), sh.get("max_t")
    fix = "no amount of fuel makes it" if not isinstance(need, (int, float)) else \
        f"scoop to ≥ {need:.1f} t" + (f", at most {top:.1f} t" if isinstance(top, (int, float)) else "")
    if sh.get("here_refuel") and isinstance(need, (int, float)):
        return f"{fix} to reach {sh['refuel_at']} in {n} jump{'' if n == 1 else 's'}"
    return f"fuel won't reach {where}: {sh['refuel_at']} in {n} jump{'' if n == 1 else 's'} · {fix}"


def boxel_known_words(bx):
    """A boxel system Spansh knows: how much of it anyone reported (page.js boxelKnown)."""
    k = bx.get("known") or {}
    b, c = k.get("bodies"), k.get("count")
    if bx.get("scanned"):
        return f"known · all {c} bodies"
    if isinstance(c, int) and c > 0:
        return f"known · {b} of {c} bodies" if b else "known · honked only"
    return f"known · {b} bod{'y' if b == 1 else 'ies'}, count unknown" if b else "known · nothing reported"


def boxel_parts(bx):
    """The kept boxel's Next as Now gives it: {label, n, name, spansh, known, scanned, complete, done} (State.boxel_next)
    -> (text, colour key) parts, or [] without one."""
    if not bx or not bx.get("label"):
        return []
    head = [("▦ ", "accent")]
    if bx.get("complete"):
        return head + [(f"{bx['label']} ", "title"), ("✓ complete", "good")]
    if bx.get("done"):
        return head + [(f"{bx['label']} ", "title"), ("✓ done", "good")]
    if not bx.get("name"):
        return head + [(f"{bx['label']} ", "title"), ("every system known is visited", "muted")]
    return head + [("Boxel: next ", "warn"), (bx["name"], "title"),
                   (" · " + (boxel_known_words(bx) if bx.get("spansh") else "to try"), "muted")]


def plan_items(leaving, highlight, bio_min, codex=True, first=None):
    """Now's suggested order (page.js worthLeavingFor + planItems) with the config's levels: the mapping over the
    highlight level (or special) and the bio over bio_min (or started, unpriced, or new to your codex), nearest to the
    arrival star first, then the best value per minute of supercruise. [{kind, body, dist, value, sec, per_min, u|b}].
    first: the body you made the first stop (S30, State.plan_first_body): its items lead, `first` True; a body not in
    the list changes nothing."""
    if not leaving:
        return []
    bio = [b for b in leaving.get("bio_pending") or [] if b.get("partial") or b.get("potential") is None
           or b["potential"] >= bio_min or (codex and b.get("codex_new"))]
    maps = [u for u in leaving.get("unmapped") or [] if not u.get("mapped_before")
            and (u.get("special") or (u.get("increment") is not None and u["increment"] >= highlight))]
    items = [{"kind": "map", "body": u.get("body"), "dist": u.get("dist_ls"), "value": u.get("increment"), "u": u} for u in maps]
    items += [{"kind": "bio", "body": b.get("body"), "dist": b.get("dist_ls"),
               "value": None if b.get("potential") is None else b["potential"] * (b.get("factor") or 1), "b": b} for b in bio]
    for it in items:
        it["sec"] = sc_seconds(it["dist"])
        it["per_min"] = it["value"] / (it["sec"] / 60) if it["sec"] and it["value"] else None
    items = sorted(items, key=lambda it: (it["dist"] is None, it["dist"] or 0,
                                          -(it["per_min"] if it["per_min"] is not None else -1)))
    if first:
        for it in items:
            it["first"] = it["body"] == first
        items.sort(key=lambda it: not it["first"])   # stable: the rest keep their order
    return items


def map_totals(u):
    """A body's mapped value as Now gives it: "771k" or, with your first-discovery / first-mapped bonuses, "771k/2.2M"."""
    a, b = (u or {}).get("value_mapped"), (u or {}).get("value_mapped_bonus")
    if not a:
        return ""
    return credits(a) if not b or credits(a) == credits(b) else f"{credits(a)}/{credits(b)}"


def plan_parts(it, high_gravity=2.0):
    """A plan item as two rows of (text, colour key): what to do, then what it pays and costs."""
    if it["kind"] == "map":
        u = it["u"]
        head = [("map ", "warn"), (u.get("body") or "?", "title"), (f" ({u.get('subtype') or '?'}{' T' if u.get('terraformable') else ''})", "text")]
        t = map_totals(u) or (f"+{credits(u['increment'])}" if u.get("increment") else "")
        detail = [(t, "accent")] if t else []
    else:
        b = it["b"]
        partial = b.get("partial") or {}
        parts = [f"{g} {n}/3" for g, n in partial.items()] + [g for g in b.get("genera") or [] if g not in partial]
        head = [("bio on ", "warn"), (b.get("body") or "?", "title")]
        if b.get("genera") is None:
            n = b.get("signals") or 0
            unk = [f"{n} signal{'' if n == 1 else 's'} not DSS'd"] if n else []
            head.append((f" ({', '.join(parts + unk)})", "text"))
        elif parts:
            head.append((": " + ", ".join(parts), "text"))
        detail = []
        if b.get("potential"):
            detail.append((f"up to {credits(b['potential'] * (b.get('factor') or 1))}", "accent"))
            if b.get("factor") == 5:
                detail.append((" 👣×5", "good"))
        if b.get("codex_galaxy") or b.get("codex_new"):
            detail.append((" ✪" if b.get("codex_galaxy") else " ✦", "good" if b.get("codex_galaxy") else "accent"))
        g = b.get("gravity")
        if isinstance(g, (int, float)):
            detail += [(" · " if detail else "", "muted"), (f"{g:.1f} g", "warn" if g >= high_gravity else "text")]
        if b.get("atmosphere") and b["atmosphere"] != "None":
            detail.append((f" · {b['atmosphere']}", "muted"))
    if it.get("sec") is not None:
        detail.append(((" · " if detail else "") + sc_text(it["sec"]) + (f" · {credits(it['per_min'])}/min" if it.get("per_min") else ""), "muted"))
    return head, detail


def wrap(bits, room, size="normal", sep=" · "):
    """(text, colour key) bits as rows joined by `sep`, a new row whenever the next bit would not fit in `room`."""
    rows, row, used = [], [], 0.0
    for t, k in bits:
        if not t:
            continue
        w = text_width(t, size) + (text_width(sep, size) if row else 0)
        if row and used + w > room:
            rows.append(row)
            row, used, w = [], 0.0, text_width(t, size)
        if row:
            row.append((sep, "muted"))
        row.append((t, k))
        used += w
    return rows + ([row] if row else [])


def flow(parts, room, size="normal", indent=""):
    """A row of (text, colour key) parts as rows within `room`, broken only between parts (never cut with …): a part
    that starts a new row loses its leading " · " and gets `indent`."""
    rows, row, used = [], [], 0.0
    for t, k in parts:
        if not t:
            continue
        if row and used + text_width(t, size) > room:
            rows.append(row)
            t = t.lstrip(" ·")
            if not t:
                row, used = [], 0.0
                continue
            row, used = ([(indent, "muted")] if indent else []), text_width(indent, size)
        row.append((t, k))
        used += text_width(t, size)
    return rows + ([row] if row else [])


def session_bits(st):
    """Now's session figures (page.js sessionLine): ["28 jumps", "6,541 ly", "12 new systems", …]."""
    def n(k, one, many):
        v = st.get(k)
        return f"{v:,} {one if v == 1 else many}" if v else None
    jumps = st.get("jumps") or 0
    bits = [f"{jumps:,} jump{'' if jumps == 1 else 's'}", f"{_half_up(st['ly']):,} ly" if st.get("ly") else None,
            n("firsts", "new system", "new systems"), n("bodies_first", "new body", "new bodies"), n("mapped", "mapped", "mapped"),
            n("footfalls", "footfall", "footfalls"), n("samples", "sample", "samples"), n("codex_new", "codex entry", "codex entries")]
    return [b for b in bits if b]


def _ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def on_body_parts(ob, b, sampling, room=500, size="normal"):
    """Now's on-body card: where you are and each genus on the body ("Bacterium 2/3", "Stratum 0/3"), then the sample
    spacing of the run under way. Rows of (text, colour key)."""
    how = f"in the {ob['vehicle']}" if ob.get("how") == "in the SRV" and ob.get("vehicle") else \
        f"flying low, {ob.get('alt')} m" if ob.get("how") == "flying low" else ob.get("how") or ""
    head = [("Over " if ob.get("how") == "flying low" else "On ", "muted"), (ob.get("body") or "?", "title"), (f" ({how})", "muted")]
    rows = [head]
    if b:
        orgs = {o.get("genus"): o for o in b.get("organics") or []}
        genera = list(dict.fromkeys(list(b.get("genera") or []) + list(orgs)))
        bits = []
        for g in genera:
            o = orgs.get(g)
            if o and o.get("lost"):
                bits.append((f"{g} lost ✗", "bad"))
            elif o:
                bits.append((f"{g} {o.get('samples', 0)}/3" + (" ✓" if o.get("done") else ""), "good" if o.get("done") else "accent"))
            else:
                bits.append((f"{g} 0/3", "text"))
        unknown = (b.get("bio") or 0) - len(genera)
        if unknown > 0:
            bits.append((f"{unknown} bio not DSS'd", "muted"))
        if b.get("geo"):
            bits.append((f"🪨 {b['geo']} geo", "text"))
        rows += wrap(bits, room, size, "  ·  ") or [[("no bio or geo signals known", "muted")]]
    sm = sampling or {}
    if sm.get("samples") and sm["samples"] < 3 and not sm.get("elsewhere"):
        head = [(f"{sm.get('genus') or ''} {sm['samples']}/3 · ", "text")]
        pays = run_pays(sm.get("value"), sm.get("factor") or 1)   # from sample 1 (S62)
        if pays:
            head.append((pays + " · ", "accent"))
        if sm.get("to_go") is None:
            rows.append([*head, (f"need {sm['need']} m from the last sample" if sm.get("need") else "spacing unknown", "muted")])
        elif sm.get("clear"):
            rows.append([*head, ("✓ clear to sample", "good"), (f" ({sm.get('nearest')} of {sm.get('need')} m)", "muted")])
        else:
            rows.append([*head, (f"{sm['to_go']} m to go", "warn"), (f" ({sm.get('nearest')} of {sm.get('need')} m)", "muted")])
    elif (sm.get("elsewhere") or {}).get("species") and sm["elsewhere"].get("samples") == 2:
        e = sm["elsewhere"]
        rows.append([("In progress elsewhere: ", "warn"), (f"{e['species']} 2/3 on {e.get('body') or 'another body'}", "text")])
    return rows


def unsold_age(days):
    """How long since you last sold, in whole days passed, for the data-at-risk line: (written out, short). Under a
    day: ("", ""). Under a week: "3 days unsold" both ways; from a week: "2 weeks 2 days since sold" or "2wk2d since
    sold" (the author, 2026-10-10)."""
    if not isinstance(days, (int, float)) or isinstance(days, bool) or not math.isfinite(days) or days < 1:
        return "", ""
    d = int(days)
    if d < 7:
        text = f"{d} day{'' if d == 1 else 's'} unsold"
        return text, text
    w, d = divmod(d, 7)
    long = f"{w} week{'' if w == 1 else 's'}" + (f" {d} day{'' if d == 1 else 's'}" if d else "") + " since sold"
    return long, f"{w}wk" + (f"{d}d" if d else "") + " since sold"


def now_panel(info, pal, size="normal", highlight=500_000, bio_min=10_000_000, high_gravity=2.0, codex=True):
    """The Now panel: the page's Now view in a few lines (the author, 2026-10-10). The system (and, for 20 s after the
    jump, whether it was undiscovered); the system targeted next; the route's next stop and the kept boxel's; fuel;
    what the data aboard stands to lose once it passes your levels; on a body its card, else Next (the first of the
    suggested order) and the body you have targeted; this session. The levels are the config's. info: {name, now, arrival, target, route, boxel, fuel, boost,
    unsold, unsold_levels, rebuy, since_sale, on_body, body, sampling, leaving, detail_ready, value_now, destination,
    this_session, last_session}. None without a system."""
    if not info or not info.get("name"):
        return None
    now = info.get("now") or 0
    rows = []
    a = info.get("arrival") or {}
    sub = None
    at = _ts(a.get("ts"))
    if a and at is not None and 0 <= now - at < ARRIVAL_SECONDS:
        sub = "🏁 undiscovered: first discovery is yours" if a.get("undiscovered") else "already discovered"
    t = info.get("target")
    if t and t.get("name"):
        words, key = TARGET_WORDS.get(t.get("status"), (t.get("status") or "", "muted"))
        row = [("➜ ", "accent"), (t["name"] + "  ", "title"), (words, key)]
        if t.get("count"):
            row.append((f" · {t.get('known') or 0}/{t['count']} known", "muted"))
        sc = t.get("star_class")
        if sc:
            scoop = bool(re.match(r"^[OBAFGKM](_|$)", sc))
            row.append((f" · {sc}{' ⛽' if scoop else ' ✕'}", "good" if scoop else "warn"))
            if star_hazard(sc):   # neutron star, white dwarf, black hole: throttle down on arrival
                row.append((" ⚠", "bad"))
        rows.append(row)
    for parts in (route_parts(info.get("route")), boxel_parts(info.get("boxel"))):   # where the next jump goes
        if parts:
            rows += flow(parts, NOW_W - 2 * PAD, size, indent="   ")
    f = info.get("fuel") or {}
    if f.get("live") and f.get("pct") is not None:
        key = "bad" if f["pct"] < 15 else "warn" if f["pct"] < 30 else "text"
        row = [(f"⛽ {f['pct']}%", key)]
        if f.get("to_full_s") is not None:   # while scooping (page.js toFullText)
            row.append((f" · {to_full_text(f['to_full_s'])} to full", "good"))
        if f.get("jumps_max") is not None:
            row.append((f" · {f['jumps_max']} jump{'' if f['jumps_max'] == 1 else 's'}", "muted"))
        if f.get("since_scoop") is not None:
            row.append((f" · {f['since_scoop']} since scoop", "muted"))
        if info.get("boost"):
            row.append((f" · boosted ×{info['boost']}", "good"))
        rows.append(row)
    u = info.get("unsold") or {}
    warn, urgent = info.get("unsold_levels") or (50_000_000, 250_000_000)
    total = u.get("total") if isinstance(u.get("total"), (int, float)) else None
    if total is not None and total >= warn:
        key = "bad" if total >= urgent else "warn"
        carto = (u.get("carto") or {}).get("estimated_payout") or (u.get("carto") or {}).get("estimated_value")
        bio = (u.get("bio") or {}).get("estimated_value")
        kinds = " · ".join(x for x in (f"🗺 {credits(carto)}" if carto else "", f"🧬 {credits(bio)}" if bio else "") if x)
        bits = [f"{kinds or credits(total)} aboard"]
        if info.get("rebuy"):
            bits.append(f"{total / info['rebuy']:.1f}× rebuy")
        long, short = unsold_age((info.get("since_sale") or {}).get("days"))
        if long:   # written out when the line fits the panel, else short ("2wk2d since sold"): never wrapped
            fits = text_width("⚠ " + " · ".join(bits + [long]), size) <= NOW_W - 2 * PAD
            bits.append(long if fits else short)
        rows.append([("⚠ ", key), (" · ".join(bits), key)])
    ob = info.get("on_body")
    if ob:
        rows += on_body_parts(ob, info.get("body"), info.get("sampling"), NOW_W - 2 * PAD, size)
    else:
        l = info.get("leaving")
        plan = plan_items(l, highlight, bio_min, codex, info.get("plan_first")) if info.get("detail_ready") else []
        dest = info.get("destination")
        dest_next = bool(dest and plan and plan[0]["body"] == dest)
        right = (f"{credits(info['value_now'])} here", "muted") if info.get("value_now") else None
        rescan = ((l or {}).get("rescan") or {}).get("bodies") if info.get("detail_ready") else None
        if rescan:   # S9-S1: the rescan trip's reason first (the page's Next line)
            n, value = len(rescan), l["rescan"].get("value")
            row = [("Next: ", "warn"), (f"rescan {n} lost scan{'' if n == 1 else 's'} in the FSS", "warn")]
            row += [(f" ({credits(value)})", "muted")] if value else []
            row += [(f" · {len(plan)} more", "muted")] if plan else []
            rows.append({"left": row, "right": right})
        elif plan:
            head, detail = plan_parts(plan[0], high_gravity)
            rows.append({"left": [("Next: ", "warn")] + ([("➜ ", "accent")] if dest_next else []) + head, "right": right})
            more = [(f" · {len(plan) - 1} more", "muted")] if len(plan) > 1 else []
            if detail or more:
                rows += flow([("   ", "muted")] + detail + more, NOW_W - 2 * PAD, size, indent="   ")
        else:
            left = [("checking…", "muted")] if not info.get("detail_ready") \
                else [("Next: honk", "warn"), (" (FSS discovery scan)", "muted")] if not l or not l.get("honked") \
                else [(f"Next: {l['unscanned']} bod{'y' if l['unscanned'] == 1 else 'ies'} to find in the FSS", "warn")] if (l.get("unscanned") or 0) > 0 \
                else [("✓ nothing worth staying for", "good")]
            rows.append({"left": left, "right": right})
        if dest and not dest_next:
            it = next((x for x in plan if x["body"] == dest), None)
            row = [("➜ ", "accent"), (dest, "title")]
            sec = sc_seconds(info.get("destination_ls"))
            if sec is not None:
                row.append((f" · {sc_text(sec)}", "muted"))
            row.append((" · worth it" + (f" · {credits(it['per_min'])}/min" if it.get("per_min") else ""), "good") if it
                       else (" · nothing to do here", "muted"))
            rows.append(row)
    ts, ls = info.get("this_session"), info.get("last_session")
    if ts or ls:
        rows.append("rule")
    if ts:
        start = _ts(ts.get("start"))
        mins = max(0, int((now - start) // 60)) if start is not None else None
        took = "" if mins is None else f" {mins} min" if mins < 60 else f" {mins // 60} h {mins % 60:02d}"
        rows += wrap([("This session" + took, "muted")] + [(b, "text") for b in session_bits(ts)]
                     + [(f"~{credits(ts['found'])} found" if ts.get("found") else "", "accent")], NOW_W - 2 * PAD, size)
    elif ls:
        rows += wrap([("Last session", "muted")] + [(b, "text") for b in session_bits(ls)], NOW_W - 2 * PAD, size)
    return text_panel("now", info["name"], rows, pal, width=NOW_W, size=size, subtitle=sub)


# ---- the bio panel: every bio signal in the system, worth it or not (the author, 2026-10-10) ----

def bio_blocks(detail, bio_min=10_000_000, high_gravity=2.0, codex=True):
    """Each body with bio signals: a header row and a row per species, worth it (by your bio level: started, new to
    your codex, unpriced, or a body that could pay at least bio_min before the first-footfall bonus) highlighted, the rest
    muted, finished ones ticked. [{name, state ("todo", "under", "done"), dist, rows}], and the totals."""
    blocks, tot = [], {"signals": 0, "done": 0, "left": 0, "under": 0}
    for b in (detail or {}).get("bodies") or []:
        if b.get("type") == "Star":
            continue
        orgs = {o.get("genus"): o for o in b.get("organics") or []}
        genera = list(dict.fromkeys(list(b.get("genera") or []) + list(orgs)))
        n_sig = max(b.get("bio") or 0, len(genera))
        if not n_sig:
            continue
        vp = b.get("value_parts") or {}
        factor, left = vp.get("bio_factor") or 1, vp.get("bio_left") or 0
        guesses = {g.get("genus"): g for g in b.get("bio_guess") or []}
        unknown = n_sig - len(genera)
        done = sum(1 for o in orgs.values() if o.get("done") and not o.get("lost"))
        started = any(not o.get("done") or o.get("lost") for o in orgs.values())
        unsampled = [guesses[g] for g in genera if g not in orgs and g in guesses]
        if unknown > 0 and not b.get("bio_options"):
            unsampled += [g for k, g in guesses.items() if k not in genera][:unknown]
        new_codex = codex and any(codex_mark([g]) for g in unsampled)
        finished = done >= n_sig
        unpriced = not finished and not left and unknown > 0
        worth = not finished and (started or new_codex or unpriced or left / factor >= bio_min)
        state = "done" if finished else "todo" if worth else "under"
        tot["signals"] += n_sig
        tot["done"] += done
        tot["left"] += left
        tot["under"] += state == "under"
        hue = {"todo": ("text", "accent"), "under": ("muted", "muted"), "done": ("muted", "muted")}[state]
        facts = [f"🧬{n_sig}"]
        g = b.get("gravity")
        head = [(b.get("name") or "?", {"todo": "title", "under": "muted", "done": "good"}[state]), ("  " + facts[0], "muted")]
        if isinstance(g, (int, float)):
            head.append((f" · {g:.2f} g", "warn" if g >= high_gravity and state == "todo" else "muted"))
        if b.get("dist_ls") is not None:
            head.append((f" · {_half_up(b['dist_ls']):,} ls", "muted"))
        if factor == 5 and not finished:
            head.append((" · 👣×5", "good" if state == "todo" else "muted"))
        right = (f"✓ {credits(sum((o.get('value') or 0) for o in orgs.values()) * factor)}", "good") if finished \
            else (f"up to {credits(left)}", hue[1]) if left else ("?", hue[1])
        rows = [{"left": head, "right": right}]
        for gname in genera:
            o, x = orgs.get(gname), guesses.get(gname)
            if o and o.get("lost"):
                rows.append({"left": [("   ✗ " + (o.get("species") or gname), "bad"), ("  lost: sample again", "bad")],
                             "right": (credits((o.get("value") or 0) * factor), "bad")})
            elif o and o.get("done"):
                colour = (o.get("variant") or "").split(" - ")[-1] if " - " in (o.get("variant") or "") else ""
                rows.append({"left": [("   ✓ ", "good"), (o.get("species") or gname, "muted"), (f"  {colour}" if colour else "", "muted")],
                             "right": (credits((o.get("value") or 0) * factor), "muted")})
            elif o:
                rows.append({"left": [("   " + (o.get("species") or gname), hue[0]), (f"  {o.get('samples', 0)}/3", "accent")],
                             "right": (credits((o.get("value") or 0) * factor), "accent")})
            else:
                rows.append(_guess_row(gname, x, factor, hue, "   ", "0/3 "))
        if unknown > 0:
            opts = b.get("bio_options")
            if opts:
                names = " or ".join(x.get("genus", "?") for x in opts.get("genera") or [] if x.get("genus") not in genera) or "?"
                rows.append({"left": [(f"   ? {unknown} not DSS'd: ", "muted"), (names, hue[0])],
                             "right": (f"{credits((opts.get('low') or 0) * factor)}–{credits((opts.get('high') or 0) * factor)}", hue[1])})
            else:
                extra = [g for k, g in guesses.items() if k not in genera][:unknown]
                for x in extra:
                    rows.append(_guess_row(x.get("genus"), x, factor, hue, "   ? ", "≤"))
                if len(extra) < unknown:
                    rows.append([(f"   ? {unknown - len(extra)} not DSS'd", "muted")])
        blocks.append({"name": b.get("name"), "state": state, "dist": b.get("dist_ls") if b.get("dist_ls") is not None else 1e12,
                       "rows": rows})
    blocks.sort(key=lambda k: ({"todo": 0, "under": 1, "done": 2}[k["state"]], k["dist"]))
    return blocks, tot


def _guess_row(genus, x, factor, hue, indent, prefix):
    """A species not sampled yet: its likeliest species, the codex mark with the colour, what it could pay."""
    x = x or {}
    mark = codex_mark([x])
    left = [(indent + (x.get("best") or genus or "?"), hue[0])]
    if mark:
        left.append(("  " + mark, "good" if mark.startswith("✪") else "accent"))
    elif x.get("variants"):
        left.append(("  " + " or ".join(v.split(" - ")[-1] for v in x["variants"]), "muted"))
    return {"left": left, "right": (prefix + credits((x.get("value") or 0) * factor), hue[1]) if x.get("value") else ("", "muted")}


def bio_panel(detail, pal, size="normal", bio_min=10_000_000, high_gravity=2.0, codex=True, max_rows=20):
    """The bio panel: every body with bio signals, worth it or not (blocks from bio_blocks), then the totals. Over
    max_rows the finished bodies lose their species rows first, then the last bodies are left out (counted). None
    without bio in the system."""
    blocks, tot = bio_blocks(detail, bio_min, high_gravity, codex)
    if not blocks:
        return None
    size_of = lambda bs: sum(len(b["rows"]) for b in bs)
    if size_of(blocks) > max_rows:
        for b in blocks:
            if b["state"] == "done":
                b["rows"] = b["rows"][:1]
    shown = []
    for b in blocks:
        if size_of(shown) + len(b["rows"]) > max_rows and shown:
            break
        shown.append(b)
    rows = [r for b in shown for r in b["rows"]]
    rows.append("rule")
    foot = [("Sampled ", "muted"), (f"{tot['done']}/{tot['signals']}", "good" if tot["done"] >= tot["signals"] else "text")]
    if tot["left"]:
        foot += [(" · left ", "muted"), (credits(tot["left"]), "accent")]
    if tot["under"]:
        foot.append((f" · {tot['under']} under your level", "muted"))
    if len(shown) < len(blocks):
        foot.append((f" · {len(blocks) - len(shown)} more", "muted"))
    rows += flow(foot, BIO_W - 2 * PAD, size)
    return text_panel("bio", "Bio signals", rows, pal, width=BIO_W, size=size,
                      subtitle=f"{len(blocks)} bod{'y' if len(blocks) == 1 else 'ies'} · {tot['signals']} signal{'' if tot['signals'] == 1 else 's'}")


# ---- the Alerts panel (S26): the page's alert cards, for a few seconds ----

# The alerts are worded and switched in the browser (speech.json's lines, each kind's notify / sound / speak ticks):
# the page posts each one it shows (POST /api/overlay/alert) and the server keeps the last few in memory. No page open
# anywhere: no alerts on the overlay (DESIGN_NOTES).
ALERT_SECONDS = 8            # how long an alert stays on the panel
ALERT_DANGER_SECONDS = 15    # a danger alert (hull, heat, interdiction, fuel, the carrier leaving without you...): longer
ALERT_KEEP = 6               # alerts kept (the newest)
ALERT_SHOWN = 3              # at most this many on the panel, newest first
ALERT_SAME_S = 10            # the same title and text again within this: dropped (every page window posts it)
ALERT_TITLE_MAX, ALERT_BODY_MAX = 200, 300
ALERT_KIND = re.compile(r"[a-z][a-z_]{0,31}")   # the page's alert kinds (page.js ALERTS: "find", "rare_star"...)
ALERT_W = 460
ALERT_BODY_ROWS = 2          # an alert's text wraps to at most this many rows


def alert_entry(body, now):
    """POST /api/overlay/alert's body {kind, title, body?, danger?} checked: ({kind, title, body, danger, t}, None),
    or (None, why)."""
    if not isinstance(body, dict):
        return None, "expected {kind, title, body, danger}"
    kind, title, text, danger = body.get("kind"), body.get("title"), body.get("body", ""), body.get("danger", False)
    if not isinstance(kind, str) or not ALERT_KIND.fullmatch(kind):
        return None, "kind: an alert kind (lower-case letters and _)"
    if not isinstance(title, str) or not title.strip() or len(title) > ALERT_TITLE_MAX:
        return None, f"title: text, 1 to {ALERT_TITLE_MAX} characters"
    if text is None:
        text = ""
    if not isinstance(text, str) or len(text) > ALERT_BODY_MAX:
        return None, f"body: text, at most {ALERT_BODY_MAX} characters"
    if not isinstance(danger, bool):
        return None, "danger: true or false"
    if set(body) - {"kind", "title", "body", "danger"}:
        return None, f"unknown keys: {', '.join(sorted(set(body) - {'kind', 'title', 'body', 'danger'}))}"
    return {"kind": kind, "title": " ".join(title.split()), "body": " ".join(text.split()), "danger": danger, "t": now}, None


def alert_add(alerts, entry):
    """`alerts` (oldest first) with `entry` added: the same title and text within ALERT_SAME_S is dropped (each page
    window posts every alert it shows, the tablet too); at most ALERT_KEEP kept. -> whether it was added."""
    if any(a["title"] == entry["title"] and a["body"] == entry["body"] and 0 <= entry["t"] - a["t"] < ALERT_SAME_S
           for a in alerts):
        return False
    alerts.append(entry)
    del alerts[:-ALERT_KEEP]
    return True


def alert_live(a, now):
    """Whether an alert is still on the panel: ALERT_SECONDS after it came, ALERT_DANGER_SECONDS for danger."""
    return 0 <= now - a["t"] < (ALERT_DANGER_SECONDS if a.get("danger") else ALERT_SECONDS)


def alerts_panel(alerts, pal, size="normal", now=None):
    """The Alerts panel: the alerts still live (`alerts` oldest first, as kept), newest first, at most ALERT_SHOWN; each
    its title (bold) and its text (muted, wrapped to ALERT_BODY_ROWS). A danger alert's title is red inside a red frame,
    and the panel's frame turns red. None when none is live."""
    now = time.time() if now is None else now
    shown = [a for a in reversed(alerts or []) if alert_live(a, now)][:ALERT_SHOWN]
    if not shown:
        return None
    lh, room, items, y = LINE_H.get(size, 20), ALERT_W - 2 * PAD, [], PAD
    for i, a in enumerate(shown):
        if i:
            y += 4
        top = y
        items.append(runs(PAD, y, [(fit(a["title"], room, size), pal["bad"] if a["danger"] else pal["text"], size, True)]))
        y += lh
        rows = ["".join(t for t, _ in row) for row in wrap([(w, "muted") for w in a["body"].split()], room, size, sep=" ")]
        if len(rows) > ALERT_BODY_ROWS:   # the rest joins the last row, cut there with …
            rows = rows[:ALERT_BODY_ROWS - 1] + [" ".join(rows[ALERT_BODY_ROWS - 1:])]
        for s in rows:
            items.append(runs(PAD, y, [(fit(s, room, size), pal["muted"], size, False)]))
            y += lh
        if a["danger"]:
            items.append(rect(PAD / 2, top - 3, ALERT_W - PAD, y - top + 4, c=pal["bad"], lw=2))
            y += 2
    danger = any(a["danger"] for a in shown)
    return {"id": "alerts", "w": ALERT_W, "h": round(y + PAD - 4), "bg": pal["panel"],
            "frame": pal["bad"] if danger else pal["frame"], "style": pal.get("style", "rounded"),
            "accent": pal["bad"] if danger else pal["title"], "items": items}


# ---- the test panels: every panel with sample data, to arrange them before flying ----

def test_panels(pal, size="normal", radar_range=800):
    """Every panel with made-up contents ("Show test panels" in Settings, and the window's Arrange mode). size: one text
    size for all, or {panel id: size} (each panel's own, State.overlay_sizes)."""
    sizes = size if isinstance(size, dict) else {}
    one = size if isinstance(size, str) else "normal"
    system = text_panel("system", "Test Sector AB-C d1-2", [
        {"left": [("A 3 ", "title"), ("Water world, terraformable", "text")], "right": ("TO MAP 2.4M", "warn")},
        {"left": [("B 1 ", "title"), ("Bacterium · Stratum", "text")], "right": ("TO LAND 19.0M", "warn")},
        {"left": [("A 1 ", "title"), ("High metal content", "muted")], "right": ("MAPPED", "good")},
        "rule",
        [("Left here: ", "muted"), ("21.4M", "accent"), (" · 9 bodies not listed", "muted")],
    ], pal, width=420, size=sizes.get("system", one), subtitle="test panel")
    # the Target panel's system (a body you are at or have targeted shows as the body panel did)
    body = target_system_panel({"name": "Test Sector AB-C d1-3", "status": "partial", "known": 3, "count": 12,
                                "edsm": {"known": 5, "count": 12}, "star_class": "N", "remaining": 4,
                                "hop": {"ly": 38.2, "fuel": 2.9, "left": 3, "reach": True},
                                "value": {"carto": 12_300_000, "bio": 40_000_000}, "notable": {"WW": 1, "T": 2}}, pal,
                               sizes.get("body", one))
    body["items"][0]["runs"].append(["  test panel", pal["muted"], sizes.get("body", one), False])
    strip = strip_panel({"name": "Test Sector AB-C d1-2", "region": "Inner Orion Spur", "sol_ly": 5411, "star": "K",
                         "found": 12, "total": 14, "honked": True, "value_now": 2_100_000, "value_max": 35_100_000,
                         "first": True, "firsts": 12, "mapped": 3, "planets": 11, "in_spansh": False}, pal, sizes.get("strip", one))
    now = now_panel({"name": "Test Sector AB-C d1-2", "now": 0, "detail_ready": True, "value_now": 2_100_000,
                     "target": {"name": "Test Sector AB-C d1-3", "status": "unreported", "star_class": "K"},
                     "fuel": {"live": True, "pct": 64, "jumps_max": 9, "since_scoop": 3},
                     "unsold": {"total": 120_000_000, "carto": {"estimated_payout": 20_000_000}, "bio": {"estimated_value": 100_000_000}},
                     "rebuy": 12_000_000, "since_sale": {"days": 4},
                     "leaving": {"honked": True, "unscanned": 0, "unmapped": [], "bio_pending": [
                         {"body": "B 1", "genera": ["Stratum"], "partial": {}, "potential": 19_000_000, "factor": 1, "dist_ls": 50,
                          "gravity": 0.42, "atmosphere": "Neon", "codex_galaxy": True},
                         {"body": "B 2", "genera": ["Bacterium"], "partial": {}, "potential": 12_000_000, "factor": 1, "dist_ls": 70}]},
                     "this_session": {"start": None, "jumps": 28, "ly": 1540, "firsts": 12, "samples": 6}}, pal, sizes.get("now", one))
    now["items"][0]["runs"].append(["  test panel", pal["muted"], sizes.get("now", one), False])
    bio = bio_panel({"bodies": [
        {"name": "B 1", "type": "Planet", "bio": 2, "gravity": 0.42, "dist_ls": 50, "genera": ["Stratum", "Bacterium"],
         "value_parts": {"bio_left": 20_000_000, "bio_factor": 1},
         "organics": [{"genus": "Bacterium", "species": "Bacterium Acies", "samples": 2, "value": 1_000_000}],
         "bio_guess": [{"genus": "Stratum", "best": "Stratum Tectonicas", "value": 19_000_000, "codex_new": True,
                        "codex_galaxy_new": True, "variants": ["Stratum Tectonicas - Lime"], "codex_have": []}]},
        {"name": "A 4", "type": "Planet", "bio": 1, "gravity": 0.35, "dist_ls": 996, "genera": [],
         "value_parts": {"bio_left": 1_000_000, "bio_factor": 1},
         "bio_guess": [{"genus": "Bacterium", "best": "Bacterium Acies", "value": 1_000_000, "variants": ["Bacterium Acies - Cobalt"]}]},
        {"name": "A 1", "type": "Planet", "bio": 1, "gravity": 0.39, "dist_ls": 335, "genera": ["Bacterium"],
         "value_parts": {"bio_left": 0, "bio_factor": 5},
         "organics": [{"genus": "Bacterium", "species": "Bacterium Acies", "variant": "Bacterium Acies - Cyan", "samples": 3,
                       "done": True, "value": 1_000_000}]}]}, pal, sizes.get("bio", one))
    bio["items"][0]["runs"].append(["  test panel", pal["muted"], sizes.get("bio", one), False])
    alerts = alerts_panel([{"kind": "find", "title": "B 1: Earth-like world (test panel)", "body": "2.4M cr scanned and mapped",
                            "danger": False, "t": 0},
                           {"kind": "hull", "title": "Interdicted", "body": "you submitted", "danger": True, "t": 0}], pal, sizes.get("alerts", one), now=0)
    return [system, body, radar_test(pal, sizes.get("radar", one), radar_range), strip, now, bio, alerts]


def radar_test(pal, size="normal", radar_range=800):
    """A sample surface radar, from radar_panel: a run's first sample 300 m ahead-right (you inside its 500 m colony
    ring), the ship behind on the left."""
    R = 1_000_000.0
    m = lambda dn, de: (math.degrees(dn / R), math.degrees(de / R))   # metres north/east to degrees near 0, 0
    (s1, s2), (h1, h2) = m(250, 170), m(-700, -900)
    surf = {"lat": 0.0, "lon": 0.0, "heading": 20, "radius": R, "body": "B 1",
            "bio": [{"species": "Stratum Tectonicas", "genus": "Stratum", "samples": 1, "current": True, "need": 500, "clear": False,
                     "points": [{"n": 1, "lat": s1, "lon": s2, "dist": 302}]}],
            "ship": {"lat": h1, "lon": h2, "dist": 1140}, "rigs": [], "tags": []}
    return radar_panel(surf, pal, size, radar_range)
