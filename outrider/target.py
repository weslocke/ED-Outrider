"""Neutron Highway auto-target: after an FSD supercharge on the route, make the next route system the target by
pressing keys in the galaxy map (optional, Linux, and Windows as an experiment; off by default).

It presses keys on the same keyboard as auto honk (outrider/honk.py: a uinput virtual keyboard on Linux, SendInput
through outrider/winkeys.py on Windows), with your own keyboard bindings
read from the active controls preset, and checks Status.json at every step: GuiFocus (0 the cockpit, 6 the galaxy
map) and, at the end, Destination.System, which must be the next system's id64.

The default sequence (each key can be overridden with [highway] autotarget_keys, the plot step with autotarget_plot):

    1 open the galaxy map        GalaxyMapOpen, then wait for GuiFocus 6 (autotarget_map_wait s)
    2 go to the search field     UI_Up (highlights "Search the Galaxy"), UI_Select (cursor in it); autotarget_search
    3 enter the system name      typed with a US keymap (or pasted: autotarget_entry = "paste")
    4 submit                     wait 0.5 s, Enter, wait 0.5 s, Enter (autotarget_submit), then wait
                                 autotarget_search_wait s for the map to fly there
    5 plot the route             hold CamYawRight 0.3 s (gives the focus back to the map), hold UI_Select 1 s
    6 close the galaxy map       GalaxyMapOpen, then wait for GuiFocus 0
    7 check                      Status.json Destination.System is the next system

It stops when GuiFocus goes anywhere unexpected, a step times out, the system changes, a jump starts or danger
comes; it then closes the galaxy map only if it opened it. The keys go to whichever window has focus: the server
brings Elite's window to the front first where it can (outrider/game_window.py) and then hands run() a `front` check,
asked before every key, so a key is pressed only while the game's window is the one in front (S74).

    python3 -m outrider.target --show          print the steps with your keys (a dry run: nothing is pressed)
    python3 -m outrider.target --show --name "Col 285 Sector AB-C d13-5"
"""
import os
import sys
import threading
import time

from . import ROOT
from . import honk

GUI_COCKPIT, GUI_GALAXY_MAP = 0, 6
# Status.json GuiFocus: what has the game's focus other than the cockpit (0)
GUI_FOCUS = {1: "the internal panel is open", 2: "the external panel is open", 3: "the comms panel is open",
             4: "the role panel is open", 5: "station services are open", 6: "the galaxy map is open",
             7: "the system map is open", 8: "the orrery is open", 9: "the FSS is open",
             10: "the surface scanner is open", 11: "the codex is open"}

# Status.json Flags / Flags2 the guards read
FLAG_DOCKED, FLAG_LANDED = 1 << 0, 1 << 1
FLAG_FSD_CHARGING, FLAG_IN_DANGER, FLAG_INTERDICTED = 1 << 17, 1 << 22, 1 << 23
FLAG_IN_SRV, FLAG_FSD_JUMP = 1 << 26, 1 << 30
FLAG2_ON_FOOT = 1 << 0

# the controls the sequence may use (read from the preset); Enter and Paste are not game controls
ACTIONS = ("GalaxyMapOpen", "UI_Right", "UI_Left", "UI_Up", "UI_Down", "UI_Select", "UI_Back", "CycleNextPanel",
           # the galaxy map's camera: after a search the focus stays in the search panel, and only moving the camera
           # gives it back to the map, where a held UI_Select plots the route (found in game 2026-10-02)
           "CamYawLeft", "CamYawRight", "CamZoomIn", "CamZoomOut", "CamTranslateLeft", "CamTranslateRight",
           "CamTranslateForward", "CamTranslateBackward")
FIXED_KEYS = {"Enter": ["KEY_ENTER"], "Paste": ["KEY_LEFTCTRL", "KEY_V"]}
# a control or fixed key named in any case ("UI_SELECT", "ui_select") is that one: the names are the game's, and a player
# writing them from memory should not get "no keyboard binding" (a Windows player on Reddit, 2026-10-22)
_CANON = {n.lower(): n for n in ACTIONS + tuple(FIXED_KEYS)}


def canon_key(name):
    """A step's key name with a control's or fixed key's own spelling; anything else (evdev names, combos) as given."""
    return _CANON.get(str(name).strip().lower(), name)
# step 5: a short camera move hands the focus from the search panel back to the map (no key does; a mouse click
# does), then UI_Select held plots the route to the system under the crosshair. The move is a zoom (found in game
# 2026-10-03): it keeps the found system under the crosshair, where a yaw (the 2026-10-02 step) turns about a pivot
# and once swung it onto a close neighbour, which was then plotted.
DEFAULT_PLOT = ("hold CamZoomOut 0.2", "hold UI_Select 1")
# step 2: from the opened galaxy map into its search field. Found in game (2026-10-02): UI_Up straight after the map
# opens highlights "Search the Galaxy" and UI_Select puts the cursor in it; UI_Select alone opens the current system's
# details, and UI_Right (Auto_Neutron's older sequence) moves along the tab column (Trade Routes, Bookmarks...).
# 2026-10-03: the map remembers its last side panel (Display Options, say), and with one open UI_Up moves inside it;
# a short camera yaw first closes any panel (nothing is selected yet, so the turn moves nothing that matters)
DEFAULT_SEARCH = ("hold CamYawRight 0.3", "press UI_Up", "press UI_Select")
# step 4: the search lists its suggestion a moment after the name goes in, and an Enter before that selects nothing
# (found in game 2026-10-02); a second Enter in case the first only highlighted it
# 2026-10-03: with the name pasted, the single suggestion lists about a second later; an Enter at 0.5 s selected while
# the search was still running and the wrong system was plotted. 1.5 s
DEFAULT_SUBMIT = ("wait 1.5", "press Enter", "wait 0.5", "press Enter")
DEFAULTS = {"entry": "type", "map_wait": 5.0, "search_wait": 2.0, "key_delay": 0.05, "keys": {}, "plot": list(DEFAULT_PLOT),
            "search": list(DEFAULT_SEARCH), "submit": list(DEFAULT_SUBMIT),
            "dry_run": False}
TAP_S = 0.05        # s a tapped key stays down
VERIFY_WAIT = 3.0   # s for Status.json to show the new Destination after the map closes
POLL_S = 0.05       # s between Status.json looks while waiting
LOCK_WAIT = 30.0    # s to wait for auto honk to let go of the virtual keyboard

PHASES = {1: "open the galaxy map", 2: "go to the search field", 3: "enter the system name", 4: "submit the search",
          5: "plot the route", 6: "close the galaxy map", 7: "check the target"}

# US keyboard layout: each printable ASCII character as (evdev key, shift)
US_KEYMAP = {" ": ("KEY_SPACE", False)}
for _c in "abcdefghijklmnopqrstuvwxyz":
    US_KEYMAP[_c] = ("KEY_" + _c.upper(), False)
    US_KEYMAP[_c.upper()] = ("KEY_" + _c.upper(), True)
for _c in "0123456789":
    US_KEYMAP[_c] = ("KEY_" + _c, False)
for _c, _k in zip(")!@#$%^&*(", "0123456789"):
    US_KEYMAP[_c] = ("KEY_" + _k, True)
for _c, _k, _s in (("-", "MINUS", "_"), ("=", "EQUAL", "+"), ("[", "LEFTBRACE", "{"), ("]", "RIGHTBRACE", "}"),
                   ("\\", "BACKSLASH", "|"), (";", "SEMICOLON", ":"), ("'", "APOSTROPHE", '"'), (",", "COMMA", "<"),
                   (".", "DOT", ">"), ("/", "SLASH", "?"), ("`", "GRAVE", "~")):
    US_KEYMAP[_c] = ("KEY_" + _k, False)
    US_KEYMAP[_s] = ("KEY_" + _k, True)


def untypeable(text):
    """The characters of text the US keymap cannot type (accented letters, say), in order of first appearance."""
    out = []
    for c in str(text):
        if c not in US_KEYMAP and c not in out:
            out.append(c)
    return out


def keystrokes(text):
    """text as [(key, shift)] on a US keyboard; ValueError naming the characters it cannot type."""
    bad = untypeable(text)
    if bad:
        raise ValueError(f"cannot type {''.join(bad)!r} on a US keyboard")
    return [US_KEYMAP[c] for c in str(text)]


def parse_step(text):
    """One plot-route step from the config: "press <key>", "hold <key> <seconds>" or "wait <seconds>". <key> is a
    control (UI_Select, ...), Enter, or evdev names such as KEY_LEFTALT+KEY_T. ValueError when it is not one."""
    parts = str(text or "").split()
    if not parts:
        raise ValueError("an empty step")
    verb = parts[0].lower()
    try:
        if verb == "press" and len(parts) == 2:
            return {"do": "press", "keys": canon_key(parts[1])}
        if verb == "hold" and len(parts) == 3 and 0 < float(parts[2]) <= 10:
            return {"do": "hold", "keys": canon_key(parts[1]), "secs": float(parts[2])}
        if verb == "wait" and len(parts) == 2 and 0 <= float(parts[1]) <= 30:
            return {"do": "wait", "secs": float(parts[1])}
    except ValueError:
        pass
    raise ValueError(f"{text!r} is not a step (use \"press UI_Select\", \"hold UI_Select 1\" or \"wait 0.5\")")


def build_steps(cfg=None):
    """The sequence as steps: {"do", "phase", "label", ...}. do: press/hold (keys: a name to resolve), type, paste,
    focus (value, timeout), wait (secs), verify."""
    c = dict(DEFAULTS, **(cfg or {}))
    s = [{"do": "press", "keys": "GalaxyMapOpen", "phase": 1, "label": "open the galaxy map", "opens": True},
         {"do": "focus", "value": GUI_GALAXY_MAP, "timeout": c["map_wait"], "phase": 1, "label": "wait for the galaxy map"},
         *[dict(parse_step(t), phase=2, label="focus the search field") for t in (c["search"] or DEFAULT_SEARCH)],
         {"do": "paste" if c["entry"] == "paste" else "type", "phase": 3, "label": "enter the system name"},
         *[dict(parse_step(t), phase=4, label="submit the search") for t in (c["submit"] or DEFAULT_SUBMIT)],
         {"do": "wait", "secs": c["search_wait"], "phase": 4, "label": "wait for the map to find the system"}]
    for t in c["plot"] or DEFAULT_PLOT:
        s.append(dict(parse_step(t), phase=5, label="plot the route"))
    s += [{"do": "press", "keys": "GalaxyMapOpen", "phase": 6, "label": "close the galaxy map", "closes": True},
          {"do": "focus", "value": GUI_COCKPIT, "timeout": c["map_wait"], "phase": 6, "label": "wait for the cockpit"},
          {"do": "verify", "phase": 7, "label": "check the target"}]
    return s


def guard(status, next_id64, route_end=None):
    """Why auto-target must not start now: None, or (code, why). code "already" is no failure (the next system is the
    target already: Status.json's Destination, or the end of the route the game plotted, NavRoute.json's last hop when
    the next system is several jumps away); it comes first, whatever the flags or focus (review F11). Everything else
    is a reason not to press."""
    st = status or {}
    if not st.get("live"):
        return "live", "the game is not live"
    if targeted(st, next_id64, route_end):
        return "already", "the next system is already the target"
    flags, flags2 = st.get("flags") or 0, st.get("flags2") or 0
    for bit, why in ((FLAG_DOCKED, "you are docked"), (FLAG_LANDED, "you are landed"), (FLAG_IN_SRV, "you are in the SRV")):
        if flags & bit:
            return "place", why
    if flags2 & FLAG2_ON_FOOT:
        return "place", "you are on foot"
    if flags & (FLAG_IN_DANGER | FLAG_INTERDICTED):
        return "danger", "you are in danger"
    if flags & (FLAG_FSD_CHARGING | FLAG_FSD_JUMP):
        return "jump", "an FSD jump is charging"
    focus = st.get("gui_focus") or 0
    if focus:
        return "focus", GUI_FOCUS.get(focus, f"GuiFocus is {focus}") + " (the cockpit must have focus)"
    return None


def targeted(status, next_id64, route_end=None):
    """Whether the game's target is the next system: Status.json's Destination is it, or the route the game plotted
    ends at it (a waypoint several jumps away: the Destination is then the first hop, review F2). route_end: a callable
    giving NavRoute.json's last hop id64, or None."""
    if next_id64 is None:
        return False
    dest = (status or {}).get("destination")
    if isinstance(dest, dict) and dest.get("System") == next_id64:
        return True
    end = route_end() if route_end else None
    return end is not None and end == next_id64


def game_target(status, here=None, route=None, fsd=None):
    """The system the game is aiming its jumps at (F3), or None: {id64, name, via}. With the game live, Status.json's
    Destination decides: none locked, or one in the system you are in (`here`: a body, a station, a signal), is no jump
    target; a Destination on the route the game plotted (`route`: NavRoute.json's hops, [{id64, name}], the start
    included) means that route's end ("route": the Destination is then only its first hop, review F2), else the
    Destination itself ("destination"). A Status.json not live (not read yet, the game at the menu): the journal's last
    FSDTarget (`fsd`: {id64, name}, "fsd") when it is not where you are. Pure: S11's wrong-jump check reads it, and the
    Target panel, the voice's "this body" and Search's "around" can."""
    st = status or {}
    if st.get("live"):
        dest = st.get("destination")
        if not isinstance(dest, dict) or not dest.get("System") or dest["System"] == here:
            return None
        hops = [h for h in route or () if isinstance(h, dict) and h.get("id64")]
        ids = [h["id64"] for h in hops]
        if hops and ids[-1] != here and dest["System"] in ids:
            return {"id64": ids[-1], "name": hops[-1].get("name"), "via": "route"}
        return {"id64": dest["System"], "name": dest.get("Name") or None, "via": "destination"}
    f = fsd or {}
    if f.get("id64") and f["id64"] != here:
        return {"id64": f["id64"], "name": f.get("name"), "via": "fsd"}
    return None


class Abort(Exception):
    def __init__(self, step, why, code=None, **extra):
        super().__init__(why)
        self.step, self.why, self.code, self.extra = step, why, code, extra


class Targeter:
    """The step runner. It shares auto honk's Honker: its virtual keyboard (honker.ui) and its lock (one sequence at
    a time). run() blocks: call it on a worker thread."""

    def __init__(self, honker, journal_dirs=(), cfg=None, copy=None, log=print):
        self.honker, self.journal_dirs = honker, list(journal_dirs or ())
        self.cfg = dict(DEFAULTS)
        self.configure(cfg or {})
        self.copy = copy   # copy(text) -> bool: the desktop clipboard, for the paste entry
        self.log = log
        self.cancel = threading.Event()   # set to stop any run (shutdown): checked between keys and while waiting
        self._run_local = threading.local()   # each run's own token, per worker thread (run_cancel)
        # time, injectable so tests can run on a fake clock that moves only when something waits (the defaults are
        # the real ones): clock() for deadlines, wait(secs) an interruptible pause (True once cancelled), sleep(secs)
        # an uninterruptible one (the gaps between the keys of one combination, a hold that must complete)
        self.clock, self.wait, self.sleep = time.monotonic, self._wait, time.sleep

    @property
    def run_cancel(self):
        """The running sequence's own token (auto-target switched off, the route cleared: set by its owner), kept per
        thread: two runs never share or overwrite one (review 2026-10-08 #1)."""
        return getattr(self._run_local, "cancel", None)

    @run_cancel.setter
    def run_cancel(self, token):
        self._run_local.cancel = token

    @property
    def run_front(self):
        """The running sequence's window check (run's `front`), per thread like run_cancel."""
        return getattr(self._run_local, "front", None)

    @run_front.setter
    def run_front(self, check):
        self._run_local.front = check

    def cancelled(self):
        """Shutdown, or the current run's own token."""
        token = self.run_cancel
        return self.cancel.is_set() or (token is not None and token.is_set())

    def _wait(self, secs):
        """Pause `secs`, returning early (True) once cancelled by either token."""
        end = time.monotonic() + max(0.0, secs or 0)
        while not self.cancelled():
            left = end - time.monotonic()
            if left <= 0:
                return False
            self.cancel.wait(min(0.05, left))
        return True

    def configure(self, cfg):
        self.cfg.update({k: v for k, v in cfg.items() if k in DEFAULTS})

    @property
    def available(self):
        return bool(self.honker and self.honker.available)

    def bindings(self):
        return honk.keyboard_bindings(self.journal_dirs, ACTIONS)

    def resolve(self, name, binds=None):
        """A step's key name as (evdev names, text) or (None, why): an override first, then Enter/Paste, a control's
        binding from the preset, or evdev names typed in."""
        name = canon_key(name)
        over = {canon_key(k): v for k, v in (self.cfg.get("keys") or {}).items()}.get(name)
        if over:
            keys = honk.parse_combo(over)
            return keys, " + ".join(honk.key_label(k) for k in keys) + " (autotarget_keys)"
        if name in FIXED_KEYS:
            return FIXED_KEYS[name], " + ".join(honk.key_label(k) for k in FIXED_KEYS[name])
        if name in ACTIONS:
            return (binds if binds is not None else self.bindings()).get(name, (None, f"{name} was not read"))
        keys = honk.parse_combo(name)
        return (keys, " + ".join(honk.key_label(k) for k in keys)) if keys else (None, f"no key {name!r}")

    def plan(self):
        """(steps with "codes" and "what" filled in, missing [(name, why)]): missing are the keys a step needs that
        have no keyboard binding (or no evdev key), so nothing runs."""
        steps, missing, binds = build_steps(self.cfg), [], None
        ev = self.honker.evdev if self.honker else None
        for st in steps:
            name = st.get("keys") or ("Paste" if st["do"] == "paste" else None)
            if not name:
                continue
            if binds is None and name in ACTIONS:
                binds = self.bindings()
            keys, what = self.resolve(name, binds)
            bad = [k for k in keys if honk.key_code(ev, k) is None] if keys and ev else []
            if not keys or bad:
                why = what if not keys else f"no {honk.KEYS_WORD} key for {', '.join(bad)}"
                if (name, why) not in missing:
                    missing.append((name, why))
                continue
            st.update(names=keys, what=what)
        for st in steps:   # typing falls back to pasting a name it cannot type, when Ctrl+V can be pressed
            if st["do"] == "type":
                keys, _what = self.resolve("Paste")
                if keys and not (ev and any(honk.key_code(ev, k) is None for k in keys)):
                    st["paste_names"] = keys
        return steps, missing

    def describe(self, steps=None):
        """The steps in words: '1 open the galaxy map: press Left Alt + Right Alt + T (secondary binding of ...)'."""
        out = []
        for st in steps or self.plan()[0]:
            how = {"press": lambda: f"press {st.get('what') or st['keys'] + ' (no keyboard binding)'}",
                   "hold": lambda: f"hold {st.get('what') or st['keys'] + ' (no keyboard binding)'} for {st['secs']:g} s",
                   "type": lambda: "type the name (US keymap)",
                   "paste": lambda: f"copy the name to the clipboard, press {st.get('what') or 'Ctrl + V'}",
                   "focus": lambda: f"wait for GuiFocus {st['value']} (up to {st['timeout']:g} s)",
                   "wait": lambda: f"wait {st['secs']:g} s",
                   "verify": lambda: "Status.json Destination must be the next system"}[st["do"]]()
            out.append(f"{st['phase']} {st['label']}: {how}")
        return out

    # ---- running ----
    def run(self, name, id64, status, system, dry_run=None, cancel=None, origin=None, route_end=None, front=None):
        """Target `name` (id64) now: status() gives Status.json's reading ({gui_focus, flags, flags2, destination,
        live}), system() the current system's id64. cancel: this run's own token (a threading.Event its owner sets:
        auto-target switched off, the route cleared or replaced); origin: the system the run was decided in (default:
        where you are when it starts), so a jump while it waited for the keyboard aborts it instead of becoming its new
        baseline; route_end: a callable giving the last hop of the route the game plotted (NavRoute.json), so a waypoint
        several jumps away counts as targeted; front: a callable giving None while Elite's window is the one in front,
        else why not, asked before every key (the first one too): a no stops the run, code "window" (None: nothing to
        check with, every key goes to whichever window has focus). -> {"ok", "phase", "label", "why", "code", "log",
        "dry_run"}; code "already" (nothing to do) or "wrong" (a different system was targeted: `wrong` names it).
        The step log is printed only when the run fails, or throughout a dry run: a success is the caller's one line."""
        dry = self.cfg.get("dry_run") if dry_run is None else dry_run
        result = {"ok": False, "phase": None, "label": None, "why": None, "code": None, "log": [], "dry_run": bool(dry)}
        tag = f"auto-target{' (dry run)' if dry else ''}: "

        def say(line):
            result["log"].append(line)
            if dry:
                self.log(tag + line)
        self.run_cancel, self.run_front = cancel, front
        try:
            self._run(result, say, name, id64, status, system, dry, origin, route_end)
        except BaseException:
            for line in result["log"]:   # an unexpected error: the steps so far are the debugging detail
                self.log(tag + line)
            raise
        finally:
            self.run_cancel = self.run_front = None
        if not result["ok"] and not dry:
            for line in result["log"]:
                self.log(tag + line)
        return result

    def _run(self, result, say, name, id64, status, system, dry, origin, route_end):
        steps, missing = self.plan()
        if missing:
            result.update(phase=0, label="read the bindings",
                          why="no keyboard binding for " + ", ".join(f"{n} ({w})" for n, w in missing))
            return
        start = guard(status(), id64, route_end)
        if start:
            result.update(phase=0, label="check before starting", why=start[1], code=start[0])
            return
        if dry:
            for st in steps:
                say("would " + self.describe([st])[0].split(": ", 1)[1] + f"  [{st['phase']} {st['label']}]")
            result.update(ok=True, why="dry run: nothing pressed")
            return
        h = self.honker
        if not h.lock.acquire(timeout=LOCK_WAIT):
            result.update(phase=0, label="wait for the keyboard", why="the virtual keyboard stayed busy (auto honk)")
            return
        here = origin if origin is not None else system()
        expect, opened, cur, close_pressed = {GUI_COCKPIT}, False, None, False
        try:
            if h.ui is None or h.stop.is_set():
                raise Abort(None, "the virtual keyboard is not open")
            # the wait for the keyboard can be long: everything again, under the lock, before the first key (review
            # CX-F3): cancelled meanwhile, a jump away from where the run was decided, docked, landed, a panel open...
            if self.cancelled():
                raise Abort(None, "stopped")
            if system() != here:
                raise Abort(None, "the system changed while it waited for the keyboard")
            again = guard(status(), id64, route_end)
            if again:
                result.update(phase=0, label="check before the first key", why=again[1], code=again[0])
                return
            not_front = self.run_front() if self.run_front else None   # S74: the game's window is the one in front
            if not_front:
                result.update(phase=0, label="check before the first key", why=not_front, code="window")
                return
            for st in steps:
                cur = st
                self._check(st, status, system, here, expect)
                d = st["do"]
                if d in ("press", "hold"):
                    if st.get("opens"):
                        expect, opened = {GUI_COCKPIT, GUI_GALAXY_MAP}, True
                    elif st.get("closes"):
                        expect, close_pressed = {GUI_GALAXY_MAP, GUI_COCKPIT}, True
                    self._tap(st["names"], st.get("secs", TAP_S), st)
                elif d == "type" and untypeable(name):
                    if not (self.copy and st.get("paste_names")):
                        raise Abort(st, f"cannot type {''.join(untypeable(name))!r} on a US keyboard "
                                        "(no clipboard tool to paste it with)")
                    if not self.copy(name):
                        raise Abort(st, "the name could not be put on the clipboard (wl-copy or xclip)")
                    self._sleep(0.2, st, status, system, here, expect)
                    self._tap(st["paste_names"], TAP_S, st)
                    say(f"pasted {name!r}: it has characters a US keyboard cannot type")
                elif d == "type":
                    for key, shift in keystrokes(name):
                        self._tap((["KEY_LEFTSHIFT"] if shift else []) + [key], TAP_S, st, gap=0.01)
                        self._sleep(self.cfg["key_delay"], st, status, system, here, expect)
                elif d == "paste":
                    if not (self.copy and self.copy(name)):
                        raise Abort(st, "the name could not be put on the clipboard (wl-copy or xclip)")
                    self._sleep(0.2, st, status, system, here, expect)
                    self._tap(st["names"], TAP_S, st)
                elif d == "focus":
                    self._wait_focus(st, status, system, here, expect)
                    expect = {st["value"]}
                elif d == "wait":
                    self._sleep(st["secs"], st, status, system, here, expect)
                elif d == "verify":
                    self._verify(st, id64, status, system, here, expect, route_end)
                # what it did, keys included ("5 plot the route: hold Space for 1 s: done"): a log shows what was pressed
                say(self.describe([st])[0] + ": done")
            result.update(ok=True)
        except Abort as e:
            st = e.step or cur
            # the FSD charged (or the jump went) once the route was plotted and the map was closing: you set off before
            # step 7 looked. Not a failure when the target is set (or you arrived there): the jump confirms it
            if close_pressed and e.code in ("jump", "moved") and (system() == id64 or targeted(status(), id64, route_end)):
                say(f"{st['phase']} {st['label']}: {e.why}, the target was set: done")
                result.update(ok=True)
                return
            result.update(phase=st["phase"] if st else 0, label=st["label"] if st else "start", why=e.why,
                          code=e.code, **e.extra)
            say(f"stopped at step {result['phase']} ({result['label']}): {e.why}")
            # close the map only if this run opened it and it is still open (pressing it otherwise would open it). Once
            # its close key went down the map is closing (Status.json lags): pressed again it would open, unless the
            # close demonstrably failed (the wait for the cockpit timed out with the map still open)
            close_failed = e.why == "the galaxy map did not close"
            # (the device is still open under our lock even when switching off set `stop`: the finally closes it after)
            if opened and (not close_pressed or close_failed) and (status() or {}).get("gui_focus") == GUI_GALAXY_MAP \
                    and h.ui is not None:
                close = next((s for s in steps if s.get("closes")), None)
                try:
                    if close and close.get("names"):
                        self._tap(close["names"], TAP_S, close, check=False)
                        say("closed the galaxy map it had opened")
                except Exception:  # noqa: BLE001 -- the result already says what went wrong
                    pass
        finally:
            if h.stop.is_set() and not h.owners:
                h._close_now()   # close() came during the run: the device is closed now that the keys are up
            h.lock.release()

    def _check(self, st, status, system, here, expect):
        if self.cancelled() or self.honker.stop.is_set():
            raise Abort(st, "stopped")
        s = status() or {}
        if not s.get("live"):
            raise Abort(st, "the game is no longer live")
        if system() != here:
            raise Abort(st, "the system changed", code="moved")
        flags = s.get("flags") or 0
        if flags & (FLAG_FSD_CHARGING | FLAG_FSD_JUMP):
            raise Abort(st, "an FSD jump started", code="jump")
        if flags & (FLAG_IN_DANGER | FLAG_INTERDICTED):
            raise Abort(st, "danger")
        focus = s.get("gui_focus") or 0
        if focus not in expect:
            raise Abort(st, (GUI_FOCUS.get(focus, f"GuiFocus went to {focus}") if focus else "the cockpit came back")
                        + " (unexpected)")

    def _tap(self, names, secs, st, gap=0.03, check=True):
        """Keys down (modifiers first), held `secs`, then up in reverse, always let go."""
        h, ev = self.honker, self.honker.evdev
        ui, e = h.ui, ev.ecodes
        if ui is None:
            raise Abort(st, "the virtual keyboard is not open")
        not_front = self.run_front() if self.run_front else None   # every key, closing the map too (S74)
        if not_front:
            raise Abort(st, not_front, code="window")
        down = []
        try:
            for n in names:
                ui.write(e.EV_KEY, honk.key_code(ev, n), 1)
                ui.syn()
                down.append(n)
                self.sleep(gap if n != names[-1] else 0)
            if check:
                if self.wait(secs) or h.stop.is_set():
                    raise Abort(st, "stopped")
            else:
                self.sleep(secs)   # a hold that must complete (closing the map on the way out: review F13)
        finally:
            for n in reversed(down):
                ui.write(e.EV_KEY, honk.key_code(ev, n), 0)
                ui.syn()

    def _sleep(self, secs, st, status, system, here, expect):
        end = self.clock() + secs
        while True:
            self._check(st, status, system, here, expect)
            left = end - self.clock()
            if left <= 0:
                return
            self.wait(min(POLL_S, left))

    def _wait_focus(self, st, status, system, here, expect):
        end = self.clock() + st["timeout"]
        while True:
            if ((status() or {}).get("gui_focus") or 0) == st["value"]:
                return
            self._check(st, status, system, here, expect)
            if self.clock() >= end:
                raise Abort(st, "the galaxy map did not open" if st["value"] == GUI_GALAXY_MAP
                            else "the galaxy map did not close")
            self.wait(POLL_S)

    def _verify(self, st, id64, status, system, here, expect, route_end=None):
        end = self.clock() + VERIFY_WAIT
        while True:
            if targeted(status(), id64, route_end):   # the next system, or a plotted route ending there (review F2)
                return
            self._check(st, status, system, here, expect)
            if self.clock() >= end:
                dest = (status() or {}).get("destination")
                if isinstance(dest, dict) and dest.get("System") is not None:
                    got = dest.get("Name") or str(dest.get("System"))
                    raise Abort(st, f"targeted the wrong system: {got}", code="wrong", wrong=got)
                raise Abort(st, "no system was targeted")
            self.wait(POLL_S)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Neutron Highway auto-target: print the key sequence (nothing is pressed).")
    p.add_argument("--show", action="store_true", help="print the steps with the keys from your controls preset")
    p.add_argument("--name", default="Example System", help="the system name to show the typing for")
    p.add_argument("--journals", action="append", default=[], help="journal folder (to find the controls preset)")
    a = p.parse_args(argv)
    cfg = {}
    try:
        import tomllib
        with open(os.path.join(ROOT, "ed_outrider.toml"), "rb") as f:
            cfg = tomllib.load(f)
    except Exception:
        pass
    hw = cfg.get("highway") if isinstance(cfg.get("highway"), dict) else {}
    jr = cfg.get("journals") if isinstance(cfg.get("journals"), dict) else {}
    dirs = a.journals or ([jr["live"]] if isinstance(jr.get("live"), str) else
                          [d for d in jr.get("live") or [] if isinstance(d, str)])
    if not dirs:
        try:
            from . import unsold
            dirs = unsold.find_journal_dirs()[0]
        except Exception:
            dirs = []
    dirs = [os.path.expanduser(d) for d in dirs]
    t_cfg = {k[len("autotarget_"):]: v for k, v in hw.items() if k.startswith("autotarget_")
             and k[len("autotarget_"):] in DEFAULTS}

    class _NoDevice:   # describing needs no virtual keyboard: never opened here
        available, evdev = True, None
    t = Targeter(_NoDevice(), dirs, t_cfg)
    steps, missing = t.plan()
    for line in t.describe(steps):
        print(line)
    if missing:
        print("missing: " + "; ".join(f"{n}: {w}" for n, w in missing))
    bad = untypeable(a.name)
    if bad:
        print(f"{a.name!r}: cannot type {''.join(bad)!r} on a US keyboard: it is pasted instead (needs wl-copy or xclip)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
