"""The in-game overlay, Outrider's side (project/PLAN-overlay-build-2026-10-10.md): what each panel draws, as small
draw lists on a 1280x960 canvas, for the overlay window on the game PC (outrider/overlay_window.py) to paint over
Elite's window. Pure: the server's State hands these builders the summaries Here, Now and the surface map already
have, and serves the result at GET /api/overlay.

A panel is {"id", "w", "h", "bg", "frame", "items"}: its natural size in canvas units, its background and frame
colours, and its items in its own coordinates (0,0 its top left). The window places each panel by the layout (a
corner of the game window, an offset as a share of the window, a scale) and draws its background at the layout's
opacity, then the items, the whole panel at the layout's alpha. Items:

    {"t": "text", "x", "y", "s", "c", "size", "bold", "align"}   (x, y: the text's top left; align right: x is its right edge)
    {"t": "rect", "x", "y", "w", "h", "c", "f", "lw"}            (c: the line's colour or None, f: the fill or None)
    {"t": "circle", "x", "y", "r", "c", "f", "lw"}               (x, y: the centre)
    {"t": "line", "pts": [[x, y], ...], "c", "lw"}
    {"t": "marker", "x", "y", "kind": "dot"|"cross"|"arrow", "c", "r", "rot"}   (rot: degrees clockwise, arrow only)

Colours are "#RRGGBB" or "#AARRGGBB".
"""
import copy
import math
import sys

CANVAS_W, CANVAS_H = 1280, 960
PANELS = ("system", "body", "radar")
PANEL_NAMES = {"system": "System", "body": "Body", "radar": "Surface radar"}
CORNERS = ("nw", "ne", "sw", "se")
SIZES = ("small", "normal", "large")
THEMES = ("default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark")
TEST_SECONDS = 20       # "Show test panels": how long they stay
ARRANGE_SECONDS = 600   # Arrange mode ends by itself after this, so the overlay never stays in the way of the mouse

DEFAULTS = {"enabled": False, "theme": "default", "text_size": "normal", "system_panel": True, "body_panel": True,
            "radar": True, "system_seconds": 0, "radar_range": 800, "url": "", "password": ""}
# where each panel starts: a corner of the game window, the offset from it as a share of the window's width (x) and
# height (y), its size (1 = the canvas's own), its background's opacity (0: text only) and the whole panel's
LAYOUT_DEFAULT = {"system": {"corner": "nw", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "body": {"corner": "ne", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "radar": {"corner": "se", "x": 0.02, "y": 0.10, "scale": 1.0, "bg": 0.5, "alpha": 1.0}}
LIMITS = {"x": (0.0, 0.95), "y": (0.0, 0.95), "scale": (0.5, 2.5), "bg": (0.0, 1.0), "alpha": (0.1, 1.0)}

# text metrics on the canvas: line heights and an average character width per size (the window's font is close to
# these; long texts are cut with … to the panel's width rather than run over its edge)
LINE_H = {"small": 16, "normal": 20, "large": 26}
CHAR_W = {"small": 6.6, "normal": 8.2, "large": 10.4}
PAD = 10

# the Default theme's colours (the page's dark values); outrider.overlay_theme reads the other themes' (O7)
DEFAULT_PALETTE = {"title": "#4FC3F7", "text": "#E6E6E6", "muted": "#9AA4AE", "good": "#4CD964", "warn": "#FFB020",
                   "bad": "#FF5A5A", "accent": "#FF8C00", "panel": "#101418", "frame": "#3A4450"}


def palette(theme="default"):
    """A theme's colours for the panels: {title, text, muted, good, warn, bad, accent, panel, frame}."""
    return dict(DEFAULT_PALETTE)


def _warn(msg):
    print(f"config: [overlay] {msg}", file=sys.stderr)


def overlay_settings(cfg):
    """[overlay] from a parsed config: {"overlay": {...}} with DEFAULTS for anything missing or wrong (reported on stderr,
    as every other section's checks are)."""
    o = cfg.get("overlay") if isinstance(cfg.get("overlay"), dict) else {}
    if "overlay" in cfg and not isinstance(cfg.get("overlay"), dict):
        _warn("must be a section (a table of settings); ignored")
    out = dict(DEFAULTS)
    for key in ("enabled", "system_panel", "body_panel", "radar"):
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
    for key, lo, hi in (("system_seconds", 0, 3600), ("radar_range", 100, 20000)):
        v = o.get(key)
        if v is None:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out[key] = int(min(hi, max(lo, v)))
        else:
            _warn(f"{key} = {v!r} must be a number; using {DEFAULTS[key]}")
    url = o.get("url", "")
    if not isinstance(url, str) or (url and not url.startswith(("http://", "https://"))):
        _warn(f"url = {url!r} must be an http:// address, e.g. \"http://192.168.1.81:8025\"; using this PC")
        url = ""
    password = o.get("password", "")
    if not isinstance(password, str):
        _warn("password must be text in quotes; ignored")
        password = ""
    out["url"], out["password"] = url.rstrip("/"), password
    return {"overlay": out}


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
    lh, big = LINE_H.get(size, 20), "large" if size != "large" else "large"
    items, y = [], PAD
    items.append(text(PAD, y, fit(title, width - 2 * PAD, big), pal["title"], big, bold=True))
    if subtitle:
        tw = text_width(title, big) + 10
        items.append(text(PAD + tw, y + (LINE_H[big] - lh) / 2 + 1, fit(subtitle, width - 2 * PAD - tw, size), pal["muted"], size))
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
        x = PAD
        for seg, key in left:
            room = width - PAD - room_right - x
            if room <= CHAR_W[size]:
                break
            s = fit(seg, room, size)
            items.append(text(x, y, s, pal.get(key, pal["text"]), size, bold=key == "title"))
            x += text_width(s, size)
        y += lh
    return {"id": pid, "w": width, "h": round(y + PAD - 2), "bg": pal["panel"], "frame": pal["frame"], "items": items}


# ---- the test panels: every panel with sample data, to arrange them before flying ----

def test_panels(pal, size="normal", radar_range=800):
    """The three panels with made-up contents ("Show test panels" in Settings, and the window's Arrange mode)."""
    system = text_panel("system", "Test Sector AB-C d1-2", [
        {"left": [("A 3 ", "title"), ("Water world, terraformable", "text")], "right": ("TO MAP 2.4M", "warn")},
        {"left": [("B 1 ", "title"), ("Bacterium · Stratum", "text")], "right": ("TO LAND 19.0M", "warn")},
        {"left": [("A 1 ", "title"), ("High metal content", "muted")], "right": ("MAPPED", "good")},
        "rule",
        [("Left here: ", "muted"), ("21.4M", "accent"), (" · 9 bodies not listed", "muted")],
    ], pal, width=420, size=size, subtitle="test panel")
    body = text_panel("body", "B 1", [
        [("Icy body · landable · ", "text"), ("0.42 g", "good"), (" · thin neon", "text")],
        [("Mapped: ", "muted"), ("1.2M", "text"), (" · first discovered", "muted")],
        "rule",
        {"left": [("Stratum Tectonicas ", "text"), ("✪ Lime", "good")], "right": ("19.0M", "accent")},
        {"left": [("Bacterium Acies ", "text"), ("✦ Cobalt", "accent")], "right": ("1.0M", "text")},
        [("Worth landing: up to 20.0M (×5 first footfall)", "good")],
    ], pal, width=400, size=size, subtitle="test panel")
    return [system, body, radar_test(pal, size, radar_range)]


def radar_test(pal, size="normal", radar_range=800):
    """A sample surface radar: you at the centre heading up, a sample point with its colony ring, the ship, N."""
    w, r = 300, 120
    cx, cy = w / 2, 40 + r
    items = [text(PAD, PAD, "Stratum Tectonicas · 1 of 3", pal["title"], size, bold=True),
             circle(cx, cy, r, pal["frame"]), circle(cx, cy, r / 2, pal["frame"]),
             text(cx, cy - r - 16, "N", pal["muted"], "small", align="left"),
             circle(cx + 40, cy - 50, 500 / radar_range * r, pal["bad"]),   # a 500 m colony ring, you inside it
             marker(cx + 40, cy - 50, "dot", pal["bad"], r=4),
             marker(cx - 70, cy + 60, "cross", pal["muted"], r=6),
             text(cx - 64, cy + 68, "ship 1.4 km", pal["muted"], "small"),
             marker(cx, cy, "arrow", pal["text"], r=9, rot=0),
             text(PAD, cy + r + 10, "Next: 500 m from the sample · nearest 64 m", pal["warn"], "small")]
    return {"id": "radar", "w": w, "h": round(cy + r + 10 + LINE_H["small"] + PAD), "bg": pal["panel"],
            "frame": pal["frame"], "items": items}
