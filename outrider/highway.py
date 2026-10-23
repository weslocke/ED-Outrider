"""The Neutron Highway's route helpers: Spansh's answer as route rows, which row a system is, the refuel stop
ahead, the spoken arrival line, the background image's check, and the desktop clipboard the next system goes on.
The route's state and the auto-target orchestration live in ed_outrider.State."""
import math
import os
import sys
import time

from outrider.core import iso_ts

# limits and the background image's accepted types (the extent and opacity are config: ed_outrider)
HIGHWAY_BG_TYPES = {".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)), ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
                    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)), ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
                    ".webp": ("image/webp", (b"RIFF",))}
HIGHWAY_BG_MAX_BYTES = 64 * 1024 * 1024   # a bigger file is refused (a galaxy image is a few MB)
HIGHWAY_REFUEL_WARN = 5     # the arrival line says "with three jumps left to refuel" this many jumps ahead or fewer
HIGHWAY_MAX_ROWS = 50000    # a route longer than this is refused (Spansh's own cap is far lower)


class HighwayError(Exception):
    """A plot that failed, in words for the page (Spansh down, an unknown system, a timeout)."""


def _num(v, conv=float):
    """A number from Spansh's answer, or None (a missing or broken field)."""
    try:
        out = conv(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if not isinstance(out, float) or math.isfinite(out) else None


def highway_rows(plotter, result):
    """Spansh's finished route as highway_route rows (dicts), the start first. The exact plotter's "jumps" carry every
    jump with its fuel; the neutron plotter's "system_jumps" are waypoints with the jumps between them."""
    if not isinstance(result, dict):
        raise HighwayError("Spansh sent a route in a shape Outrider does not know")
    raw = result.get("jumps") if plotter == "exact" else result.get("system_jumps")
    if not isinstance(raw, list):
        raise HighwayError("Spansh sent a route in a shape Outrider does not know")
    rows = []
    for i, j in enumerate(raw):
        if not isinstance(j, dict):
            continue
        name = j.get("name") if plotter == "exact" else j.get("system")
        if not isinstance(name, str) or not name.strip():
            continue
        id64 = _num(j.get("id64"), int)
        row = {"system": name.strip(), "id64": id64 if id64 is not None and 0 <= id64 < 2 ** 63 else None,
               "x": _num(j.get("x")), "y": _num(j.get("y")), "z": _num(j.get("z"))}
        if plotter == "exact":
            row.update(distance=_num(j.get("distance")), fuel_used=_num(j.get("fuel_used")),
                       fuel_left=_num(j.get("fuel_in_tank")), neutron=1 if j.get("has_neutron") else 0,
                       refuel=1 if j.get("must_refuel") else 0, jumps=0 if not rows else 1,
                       remaining=_num(j.get("distance_to_destination")))
        else:
            row.update(distance=_num(j.get("distance_jumped")), fuel_used=None, fuel_left=None,
                       neutron=1 if j.get("neutron_star") else 0, refuel=0,
                       jumps=max(0, _num(j.get("jumps"), int) or 0) if rows else 0, remaining=_num(j.get("distance_left")))
        rows.append(row)
    if len(rows) < 2:
        raise HighwayError("Spansh found no route between those systems")
    if len(rows) > HIGHWAY_MAX_ROWS:
        raise HighwayError(f"a route of {len(rows)} systems is longer than Outrider keeps ({HIGHWAY_MAX_ROWS})")
    return rows


def _ly(a, b):
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))


def stand_in(around, toward, candidates, reach):
    """The system to plot from (or to) in place of one Spansh does not know yet (`around`: its x, y, z): of
    `candidates` (dicts with name, id64, x, y, z: systems Spansh knows), the one within `reach` ly of it that is nearest
    `toward` (the route's other end: no jump wasted going the wrong way), else simply the nearest. None when there are
    no candidates."""
    known = [c for c in candidates if None not in (c.get("x"), c.get("y"), c.get("z")) and c.get("name")]
    if not known:
        return None
    near = [c for c in known if reach and _ly(around, c) <= reach]
    if near and toward and None not in (toward.get("x"), toward.get("y"), toward.get("z")):
        return min(near, key=lambda c: _ly(toward, c))
    return min(known, key=lambda c: _ly(around, c))


def splice_route(rows, plotter, reach, start=None, end=None):
    """A route plotted between stand-ins with the real ends put back: `start` before the first row and `end` after the
    last (dicts with system, id64, x, y, z), each a leg of its own from (or to) its stand-in. The legs' fuel is not
    known (Spansh's figures begin at the stand-in), and the neutron plotter's jump count for one is what `reach` needs."""
    rows = [dict(r) for r in rows]

    def jumps(d):
        return 1 if plotter == "exact" or not reach else max(1, math.ceil(d / reach))
    if end:
        d = _ly(rows[-1], end)
        for r in rows:
            r["remaining"] = (r["remaining"] or 0) + d if r["remaining"] is not None else None
        rows.append(dict(end, distance=round(d, 2), fuel_used=None, fuel_left=None, neutron=0, refuel=0, jumps=jumps(d),
                         remaining=0.0))
    if start:
        d = _ly(start, rows[0])
        rows[0].update(distance=round(d, 2), fuel_used=None, fuel_left=None, jumps=jumps(d))
        rows.insert(0, dict(start, distance=None, fuel_used=None, fuel_left=None, neutron=0, refuel=0, jumps=0,
                            remaining=round((rows[0]["remaining"] or 0) + d, 2) if rows[0]["remaining"] is not None else None))
    return rows


NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def number_words(n):
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def highway_match(rows, id64, name, near=0):
    """The route row a system is, or None: by id64 (by name when a row has none). A system on the route twice gives
    the occurrence at or after `near` (where you were), else the latest before it."""
    low = (name or "").strip().lower()
    hits = [i for i, r in enumerate(rows)
            if (r["id64"] == id64 if r["id64"] is not None and id64 is not None else (r["system"] or "").lower() == low)]
    if not hits:
        return None
    ahead = [i for i in hits if i >= near]
    return ahead[0] if ahead else hits[-1]


def highway_refuel_in(rows, i):
    """Jumps from row i to the next refuel stop after it, or None."""
    return next((j - i for j in range(i + 1, len(rows)) if rows[j]["refuel"]), None)


def highway_bg_file(path):
    """The Highway map's background image at `path` (the configured one): (content type, os.stat result), or
    ValueError in words when it cannot be served: not one of HIGHWAY_BG_TYPES by its extension and its first bytes,
    missing, not a regular file, empty or over HIGHWAY_BG_MAX_BYTES."""
    kind = HIGHWAY_BG_TYPES.get(os.path.splitext(path)[1].lower())
    if not kind:
        raise ValueError("not an image file (" + ", ".join(HIGHWAY_BG_TYPES) + ")")
    try:
        st = os.stat(path)
        if not os.path.isfile(path):
            raise ValueError("not a file")
        with open(path, "rb") as fh:
            head = fh.read(12)
    except OSError as e:
        raise ValueError(f"cannot be read ({e.strerror or type(e).__name__})") from None
    if not 0 < st.st_size <= HIGHWAY_BG_MAX_BYTES:
        raise ValueError("empty" if not st.st_size else f"over {HIGHWAY_BG_MAX_BYTES // 2 ** 20} MB")
    if not head.startswith(kind[1]) or (kind[0] == "image/webp" and head[8:12] != b"WEBP"):
        raise ValueError(f"its content is not {kind[0]}")
    return kind[0], st


def highway_text(rows, i):
    """The line said on arriving at route row i (not the last): the next stop, a refuel coming up or due here, and
    the supercharge in a neutron system. Plain words (personality lines come later)."""
    here, nxt = rows[i], rows[i + 1]
    k = highway_refuel_in(rows, i)
    text = f"Next Neutron Highway Stop: {nxt['system']}"
    if k is not None and k <= HIGHWAY_REFUEL_WARN:
        text += f", with {number_words(k)} jump{'' if k == 1 else 's'} left to refuel"
    text += "."
    if here["refuel"]:
        text = "Refuel here before continuing. " + text
    if here["neutron"]:
        text += " Boost your FSD to continue."
    return text


PASTE_MAX = 100   # characters: a system or station name to paste is at most this long (the To field's maxlength)


def paste_name(text):
    """The clipboard's text as a name to paste into a system or station field (NEXT-VERSION #5): stripped, one line, at
    most PASTE_MAX characters, no control characters and no link; None for anything else (a paragraph, a URL, nothing)."""
    if not isinstance(text, str):
        return None
    name = text.strip()
    if not name or len(name) > PASTE_MAX or "://" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        return None
    return name


class Clipboard:
    """The desktop clipboard. Linux: xclip where there is an X display (an X11 session, or XWayland beside Wayland),
    else wl-copy under Wayland, whichever is installed, run as a plain subprocess (no shell) with the text on its stdin;
    both fork to serve the selection, so the call returns at once. xclip first: the game (Proton) is an X11 client
    reading the X11 clipboard, and where the compositor has no data-control protocol (GNOME) wl-copy sets the clipboard
    by opening a surface of its own that takes the keyboard focus, which the game then misses: the author's auto-target
    paste came out empty, and its retry found Elite no longer the active window (2026-10-23). Windows: the clipboard API itself (outrider.winkeys.set_clipboard). Reading it (`paste`,
    the page's 📋 buttons): wl-paste or xclip -o, Windows' get_clipboard. Tests pass fakes for `which`, `run`, `env`,
    `platform`, `win_set` and `win_get`: nothing is ever copied or read from a test."""
    TOOLS = (("xclip", "DISPLAY", ("xclip", "-selection", "clipboard")), ("wl-copy", "WAYLAND_DISPLAY", ("wl-copy",)))
    READ_TOOLS = (("xclip", "DISPLAY", ("xclip", "-selection", "clipboard", "-o")),
                  ("wl-paste", "WAYLAND_DISPLAY", ("wl-paste", "--no-newline", "--type", "text")))

    def __init__(self, enabled=True, which=None, run=None, env=None, platform=None, win_set=None, win_get=None):
        import shutil
        import subprocess
        self.enabled = bool(enabled)
        self._which, self._run, self._env = which or shutil.which, run or subprocess.run, os.environ if env is None else env
        self._devnull = subprocess.DEVNULL
        self._pipe = subprocess.PIPE
        self.tool = self.argv = self._win_set = self.read_tool = self.read_argv = self._win_get = None
        if (platform or sys.platform).startswith("win"):
            if win_set is None:
                from outrider.winkeys import set_clipboard as win_set
            if win_get is None:
                from outrider.winkeys import get_clipboard as win_get
            self.tool, self._win_set = "Windows", win_set
            self.read_tool, self._win_get = "Windows", win_get
        for name, var, argv in () if self.tool else self.TOOLS:
            if self._env.get(var) and self._which(name):
                self.tool, self.argv = name, list(argv)
                break
        for name, var, argv in () if self.read_tool else self.READ_TOOLS:
            if self._env.get(var) and self._which(name):
                self.read_tool, self.read_argv = name, list(argv)
                break
        self.last = None   # {text, ok, ts, error}: the latest copy, for the Plot Route tab

    def info(self):
        why = None if self.tool else "neither xclip (X11, XWayland) nor wl-copy (Wayland) was found for this desktop session"
        return {"enabled": self.enabled, "available": bool(self.tool), "tool": self.tool, "why": why, "last": self.last}

    def copy(self, text, force=False):
        """Put `text` on the clipboard; True when the tool said it did (blocking, briefly: run it off the loop). force:
        even with [highway] clipboard off (auto-target's paste entry asked for it)."""
        if not ((self.enabled or force) and (self.argv or self._win_set) and text):
            return False
        err = None
        try:
            if self._win_set:
                self._win_set(str(text))
                ok = True
            else:
                ok = self._run(self.argv, input=str(text).encode(), stdout=self._devnull, stderr=self._devnull,
                               timeout=5, check=False).returncode == 0
            if not ok:
                err = f"{self.tool} failed"
        except (OSError, ValueError) as e:
            ok, err = False, f"{self.tool}: {e}"
        except Exception as e:  # noqa: BLE001 -- subprocess.TimeoutExpired and the like: report, never raise
            ok, err = False, f"{self.tool}: {type(e).__name__}"
        self.last = {"text": str(text), "ok": ok, "ts": iso_ts(time.time()), "error": err}
        return ok

    def paste_why(self):
        """Why the clipboard cannot be read on this desktop, or None when it can."""
        return None if self.read_tool else \
            "neither xclip (X11, XWayland) nor wl-paste (Wayland) was found for Outrider's desktop session"

    def paste(self):
        """The clipboard's text as a name to paste (paste_name): {text} or {error, code} (no_tool, failed, empty,
        not_a_name). Blocking, briefly (run it off the loop); never raises. The [highway] clipboard switch is about
        copying the next system, not this."""
        if not self.read_tool:
            return {"error": self.paste_why(), "code": "no_tool"}
        try:
            if self._win_get:
                text = self._win_get()
            else:
                r = self._run(self.read_argv, stdout=self._pipe, stderr=self._devnull, timeout=3, check=False)
                # wl-paste exits 1 on an empty clipboard ("Nothing is copied"): read as empty, not as a failure
                text = r.stdout.decode("utf-8") if r.returncode == 0 else ""
        except UnicodeDecodeError:
            return {"error": "the clipboard doesn't hold text", "code": "not_a_name"}
        except Exception as e:  # noqa: BLE001 -- OSError, subprocess.TimeoutExpired, Windows refusing: said, never raised
            return {"error": f"couldn't read the clipboard ({self.read_tool}: {type(e).__name__})", "code": "failed"}
        if not (text or "").strip():
            return {"error": "the clipboard is empty", "code": "empty"}
        name = paste_name(text)
        if name is None:
            return {"error": "the clipboard doesn't hold a system name (one short line)", "code": "not_a_name"}
        return {"text": name}
