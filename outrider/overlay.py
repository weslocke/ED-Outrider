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

from . import ROOT

CANVAS_W, CANVAS_H = 1280, 960
PANELS = ("system", "body", "radar", "strip", "now", "bio")
PANEL_NAMES = {"system": "System", "body": "Body", "radar": "Surface radar", "strip": "System strip",
               "now": "Now (To-Do & Info)", "bio": "Bio signals"}
# a panel is placed from a corner of the game window, or centred along its top or bottom edge (n, s: x is not used)
CORNERS = ("nw", "ne", "sw", "se", "n", "s")
SIZES = ("small", "normal", "large")
THEMES = ("default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark")
TEST_SECONDS = 60       # "Show test panels": how long they stay (shown whether or not the game is in front)
ARRANGE_SECONDS = 600   # Arrange mode ends by itself after this, so the overlay never stays in the way of the mouse

DEFAULTS = {"enabled": False, "theme": "default", "text_size": "normal", "system_panel": True, "body_panel": True,
            "radar": True, "strip_panel": False, "now_panel": False, "bio_panel": False, "system_seconds": 0,
            "radar_range": 800}
# where each panel starts: a corner of the game window, the offset from it as a share of the window's width (x) and
# height (y), its size (1 = the canvas's own), its background's opacity (0: text only) and the whole panel's
LAYOUT_DEFAULT = {"system": {"corner": "nw", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "body": {"corner": "ne", "x": 0.02, "y": 0.16, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "radar": {"corner": "se", "x": 0.02, "y": 0.10, "scale": 1.0, "bg": 0.5, "alpha": 1.0},
                  "strip": {"corner": "n", "x": 0.0, "y": 0.005, "scale": 1.0, "bg": 0.5, "alpha": 1.0},
                  "now": {"corner": "sw", "x": 0.02, "y": 0.06, "scale": 1.0, "bg": 0.65, "alpha": 1.0},
                  "bio": {"corner": "nw", "x": 0.02, "y": 0.45, "scale": 1.0, "bg": 0.65, "alpha": 1.0}}
LIMITS = {"x": (0.0, 0.95), "y": (0.0, 0.95), "scale": (0.5, 2.5), "bg": (0.0, 1.0), "alpha": (0.1, 1.0)}

# text metrics on the canvas: line heights and an average character width per size (the window's font is close to
# these; long texts are cut with … to the panel's width rather than run over its edge)
LINE_H = {"small": 16, "normal": 20, "large": 26}
CHAR_W = {"small": 6.6, "normal": 8.2, "large": 10.4}
PAD = 10

# the Default theme's colours: the page's dark ones (page.css :root), the title in its info blue
DEFAULT_PALETTE = {"title": "#6AA8FF", "text": "#D8DDE4", "muted": "#7D8794", "good": "#5CC98A", "warn": "#E3B341",
                   "bad": "#E05D5D", "accent": "#FF8C1A", "panel": "#161A20", "frame": "#262C35", "style": "rounded"}
THEMES_DIR = os.path.join(ROOT, "static", "themes")
# each palette key from the theme's variables, the first one set (the themes' own: static/themes/<name>.css)
THEME_VARS = {"title": ("tb-title", "info", "accent"), "text": ("text",), "muted": ("muted",), "good": ("good",),
              "warn": ("warn",), "bad": ("bad",), "accent": ("accent",), "panel": ("panel",), "frame": ("line",)}
# the panels' frames per theme, as the 10-05 plan drew them: cut corners (Elite, Narn), a double line (Centauri,
# Minbari), LCARS's bars, rounded for the rest
THEME_STYLE = {"elite": "chamfer", "narn": "chamfer", "centauri": "double", "minbari": "double", "lcars": "lcars"}
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
    for key in ("enabled", "system_panel", "body_panel", "radar", "strip_panel", "now_panel", "bio_panel"):
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


def runs(x, y, parts, align="left"):
    """A line of (text, colour, size, bold) parts set one after another by the window, with the font's real widths;
    align "center": x is the line's middle."""
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
    """Credits as the page writes them: 950, 59k, 2.4M, 1.2B."""
    v = float(v or 0)
    for div, unit, digits in ((1e9, "B", 1), (1e6, "M", 1), (1e3, "k", 0)):
        if abs(v) >= div:
            return f"{v / div:.{digits}f}{unit}"
    return f"{v:.0f}"


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


def system_rows(detail, highlight, bio_min):
    """The system panel's bodies: what is left to do on each body worth it, nearest first, then the valuable ones
    already done. [{name, what, status, value, key (warn/accent/good), mark, todo, dist}], the credits left in the
    whole system, and how many bodies have something left that is under your levels (not listed)."""
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
        to_map = not mapped and b.get("type") == "Planet" and map_left > 0 and (map_left >= highlight or special)
        to_land = bool(partial) or bio_left >= bio_min
        base = {"name": b.get("name", "?"), "what": body_what(b), "mark": codex_mark(b.get("bio_guess")) if to_land else "",
                "dist": b.get("dist_ls") if b.get("dist_ls") is not None else 1e12}
        if partial:
            o = partial[0]
            rows.append(dict(base, status=f"{o.get('genus', 'bio')} {o.get('samples', 0)}/3", value=bio_left + (map_left if to_map else 0),
                             key="accent", todo=True))
        elif to_land or to_map:
            status = "MAP + LAND" if to_land and to_map else "TO LAND" if to_land else "TO MAP"
            rows.append(dict(base, status=status, value=(bio_left if to_land else 0) + (map_left if to_map else 0), key="warn", todo=True))
        elif (mapped and (b.get("value_max") or 0) >= highlight) or (organics and all(o.get("done") for o in organics)
                                                                      and (b.get("value_max") or 0) >= bio_min):
            rows.append(dict(base, status="MAPPED" if mapped else "SAMPLED", value=None, key="good", todo=False))
        if not to_land and not to_map and (bio_left or (map_left and not mapped)):
            under += 1
    rows.sort(key=lambda r: (not r["todo"], r["dist"]))
    return rows, left_all, under


def system_panel(detail, pal, size="normal", highlight=500_000, bio_min=10_000_000, max_rows=8):
    """The system panel ("worth your time"): None when no body is worth listing."""
    rows, left_all, under = system_rows(detail, highlight, bio_min)
    if not rows:
        return None
    shown = rows[:max_rows]
    lines = []
    for r in shown:
        left = [(r["name"] + " ", "title"), (r["what"], "text" if r["todo"] else "muted")]
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


def body_panel(b, pal, size="normal", high_gravity=2.0, colony=None):
    """The body panel: what the body is, what mapping it is worth, and its life (each likely species with its codex
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
                             "right": (credits((o.get("value") or 0) * factor), "accent")})
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
    your rigs; what the next sample needs underneath. None with nothing to draw."""
    if not surf or surf.get("lat") is None or not surf.get("radius"):
        return None
    bio = surf.get("bio") or []
    cur = next((s for s in bio if s.get("current")), None)
    if not (bio or surf.get("ship") or surf.get("rigs") or surf.get("tags")):
        return None
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
    items.append(marker(cx, cy, "arrow", pal["text"], r=9))
    y = cy + r + 14
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


def strip_panel(info, pal, size="normal"):
    """The system strip: two short lines across the top, centred in their box. Line 1: the system, its region, the
    star. Line 2: the distance from Sol, now and max, your first discovery; then bodies, found of total, discovered by
    you, mapped of planets, whether Spansh knows the system (the author, 2026-10-10). info: {name, region, star, sol_ly,
    total, found, all_found, honked, value_now, value_max, first, firsts, mapped, planets, in_spansh}. Its width follows
    its text."""
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
        rest.append(("Spansh ✓" if info["in_spansh"] else "Spansh ✗ (new to it)", "muted" if info["in_spansh"] else "warn"))
    two = line(None, rest)
    lines = [one] + ([two] if two else [])
    width = round(min(CANVAS_W - 40, PAD * 2 + 10 + max(sum(text_width(t, s) for t, _, s, _ in ln) for ln in lines)))
    items, y = [], PAD - 2
    for i, ln in enumerate(lines):
        items.append(runs(width / 2, y, ln, align="center"))
        y += LINE_H["large"] if i == 0 else LINE_H.get(size, 20)
    return {"id": "strip", "w": round(width), "h": round(y + PAD - 4), "bg": pal["panel"], "frame": pal["frame"],
            "style": pal.get("style", "rounded"), "accent": pal["title"], "items": items}


# ---- the Now panel: the page's Now view, condensed (the author, 2026-10-10) ----

# supercruise seconds from the arrival star on the page's community curve (page.js scSeconds): a rough guide
SC_KNEE = 7.5 * math.log(2000) - 20
TARGET_WORDS = {"unreported": ("never reported", "good"), "no bodies": ("no scan data", "warn"),
                "partial": ("partly scanned", "warn"), "explored": ("fully scanned", "muted"), "visited": ("visited", "muted")}
ARRIVAL_SECONDS = 20   # the arrival verdict stays this long after the jump, as on Now
NOW_W = 520


def _half_up(x):
    return math.floor(x + 0.5)   # JavaScript's Math.round, so the panel's figures are the page's


def sc_seconds(ls):
    if not isinstance(ls, (int, float)) or isinstance(ls, bool) or not math.isfinite(ls) or ls < 0:
        return None
    return max(15, 7.5 * math.log(max(ls, 1)) - 20) if ls <= 2000 else SC_KNEE + (ls - 2000) * (360 - SC_KNEE) / 98000


def sc_text(sec):
    return f"~{max(10, _half_up(sec / 5) * 5)} s" if sec < 90 else f"~{_half_up(sec / 60)} min"


def plan_items(leaving, highlight, bio_min, codex=True):
    """Now's suggested order (page.js worthLeavingFor + planItems) with the config's levels: the mapping over the
    highlight level (or special) and the bio over bio_min (or started, unpriced, or new to your codex), nearest to the
    arrival star first, then the best value per minute of supercruise. [{kind, body, dist, value, sec, per_min, u|b}]."""
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
    return sorted(items, key=lambda it: (it["dist"] is None, it["dist"] or 0,
                                         -(it["per_min"] if it["per_min"] is not None else -1)))


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
        head = (f"{sm.get('genus') or ''} {sm['samples']}/3 · ", "text")
        if sm.get("to_go") is None:
            rows.append([head, (f"need {sm['need']} m from the last sample" if sm.get("need") else "spacing unknown", "muted")])
        elif sm.get("clear"):
            rows.append([head, ("✓ clear to sample", "good"), (f" ({sm.get('nearest')} of {sm.get('need')} m)", "muted")])
        else:
            rows.append([head, (f"{sm['to_go']} m to go", "warn"), (f" ({sm.get('nearest')} of {sm.get('need')} m)", "muted")])
    elif (sm.get("elsewhere") or {}).get("species") and sm["elsewhere"].get("samples") == 2:
        e = sm["elsewhere"]
        rows.append([("In progress elsewhere: ", "warn"), (f"{e['species']} 2/3 on {e.get('body') or 'another body'}", "text")])
    return rows


def now_panel(info, pal, size="normal", highlight=500_000, bio_min=10_000_000, high_gravity=2.0, codex=True):
    """The Now panel: the page's Now view in a few lines (the author, 2026-10-10). The system (and, for 20 s after the
    jump, whether it was undiscovered); the system targeted next; fuel; what the data aboard stands to lose once it
    passes your levels; on a body its card, else Next (the first of the suggested order) and the body you have
    targeted; this session. The levels are the config's. info: {name, now, arrival, target, fuel, boost, unsold,
    unsold_levels, rebuy, since_sale, on_body, body, sampling, leaving, detail_ready, value_now, destination,
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
            if sc == "N" or sc.startswith("D"):
                row.append((" ⚠", "bad"))
        rows.append(row)
    f = info.get("fuel") or {}
    if f.get("live") and f.get("pct") is not None:
        key = "bad" if f["pct"] < 15 else "warn" if f["pct"] < 30 else "text"
        row = [(f"⛽ {f['pct']}%", key)]
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
        days = (info.get("since_sale") or {}).get("days") or 0
        if days >= 1:
            bits.append(f"{_half_up(days)} d unsold")
        rows.append([("⚠ ", key), (" · ".join(bits), key)])
    ob = info.get("on_body")
    if ob:
        rows += on_body_parts(ob, info.get("body"), info.get("sampling"), NOW_W - 2 * PAD, size)
    else:
        l = info.get("leaving")
        plan = plan_items(l, highlight, bio_min, codex) if info.get("detail_ready") else []
        dest = info.get("destination")
        dest_next = bool(dest and plan and plan[0]["body"] == dest)
        right = (f"{credits(info['value_now'])} here", "muted") if info.get("value_now") else None
        if plan:
            head, detail = plan_parts(plan[0], high_gravity)
            rows.append({"left": [("Next: ", "warn")] + ([("➜ ", "accent")] if dest_next else []) + head, "right": right})
            more = [(f" · {len(plan) - 1} more", "muted")] if len(plan) > 1 else []
            if detail or more:
                rows.append([("   ", "muted")] + detail + more)
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
    rows.append(foot)
    return text_panel("bio", "Bio signals", rows, pal, width=470, size=size,
                      subtitle=f"{len(blocks)} bod{'y' if len(blocks) == 1 else 'ies'} · {tot['signals']} signal{'' if tot['signals'] == 1 else 's'}")


# ---- the test panels: every panel with sample data, to arrange them before flying ----

def test_panels(pal, size="normal", radar_range=800):
    """Every panel with made-up contents ("Show test panels" in Settings, and the window's Arrange mode)."""
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
    strip = strip_panel({"name": "Test Sector AB-C d1-2", "region": "Inner Orion Spur", "sol_ly": 5411, "star": "K",
                         "found": 12, "total": 14, "honked": True, "value_now": 2_100_000, "value_max": 35_100_000,
                         "first": True, "firsts": 12, "mapped": 3, "planets": 11, "in_spansh": False}, pal, size)
    now = now_panel({"name": "Test Sector AB-C d1-2", "now": 0, "detail_ready": True, "value_now": 2_100_000,
                     "target": {"name": "Test Sector AB-C d1-3", "status": "unreported", "star_class": "K"},
                     "fuel": {"live": True, "pct": 64, "jumps_max": 9, "since_scoop": 3},
                     "unsold": {"total": 120_000_000, "carto": {"estimated_payout": 20_000_000}, "bio": {"estimated_value": 100_000_000}},
                     "rebuy": 12_000_000, "since_sale": {"days": 4},
                     "leaving": {"honked": True, "unscanned": 0, "unmapped": [], "bio_pending": [
                         {"body": "B 1", "genera": ["Stratum"], "partial": {}, "potential": 19_000_000, "factor": 1, "dist_ls": 50,
                          "gravity": 0.42, "atmosphere": "Neon", "codex_galaxy": True},
                         {"body": "B 2", "genera": ["Bacterium"], "partial": {}, "potential": 12_000_000, "factor": 1, "dist_ls": 70}]},
                     "this_session": {"start": None, "jumps": 28, "ly": 1540, "firsts": 12, "samples": 6}}, pal, size)
    now["items"][0]["runs"].append(["  test panel", pal["muted"], size, False])
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
                       "done": True, "value": 1_000_000}]}]}, pal, size)
    bio["items"][0]["runs"].append(["  test panel", pal["muted"], size, False])
    return [system, body, radar_test(pal, size, radar_range), strip, now, bio]


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
