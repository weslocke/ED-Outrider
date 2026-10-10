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
    {"t": "runs", "x", "y", "runs": [[s, c, size, bold], ...]}   (a line of differently coloured parts, set one after the
                                                                 other with the font's own widths)
    {"t": "rect", "x", "y", "w", "h", "c", "f", "lw"}            (c: the line's colour or None, f: the fill or None)
    {"t": "circle", "x", "y", "r", "c", "f", "lw"}               (x, y: the centre)
    {"t": "line", "pts": [[x, y], ...], "c", "lw"}
    {"t": "marker", "x", "y", "kind": "dot"|"cross"|"arrow", "c", "r", "rot"}   (rot: degrees clockwise, arrow only)

Colours are "#RRGGBB" or "#AARRGGBB".
"""
import copy
import math
import os
import re
import sys

from . import ROOT

CANVAS_W, CANVAS_H = 1280, 960
PANELS = ("system", "body", "radar")
PANEL_NAMES = {"system": "System", "body": "Body", "radar": "Surface radar"}
CORNERS = ("nw", "ne", "sw", "se")
SIZES = ("small", "normal", "large")
THEMES = ("default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark")
TEST_SECONDS = 60       # "Show test panels": how long they stay (shown whether or not the game is in front)
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


def runs(x, y, parts):
    """A line of (text, colour, size, bold) parts set one after another by the window, with the font's real widths."""
    return {"t": "runs", "x": round(x, 1), "y": round(y, 1), "runs": [[str(s), c, size, bool(b)] for s, c, size, b in parts]}


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
