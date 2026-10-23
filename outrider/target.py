"""Neutron Highway auto-target: after an FSD supercharge on the route, make the next route system the target by
pressing keys in the galaxy map (optional, Linux, and Windows as an experiment; off by default).

It presses keys on the same keyboard as auto honk (outrider/honk.py: a uinput virtual keyboard on Linux, SendInput
through outrider/winkeys.py on Windows), with your own keyboard bindings
read from the active controls preset, and checks Status.json at every step: GuiFocus (0 the cockpit, 6 the galaxy
map) and, at the end, Destination.System, which must be the next system's id64.

The default sequence (each key can be overridden with [highway] autotarget_keys, the plot step with autotarget_plot):

    1 open the galaxy map        GalaxyMapOpen, then wait for GuiFocus 6 (autotarget_map_wait s)
    2 go to the search field     hold CamYawRight 0.3 s (closes a side panel), UI_Up (highlights "Search the Galaxy"),
                                 UI_Select (cursor in it); autotarget_search
    3 enter the system name      typed with a US keymap (or pasted: autotarget_entry = "paste")
    4 submit                     wait 1.5 s, the down arrow (KEY_DOWN: the first result), UI_Select (picks it, the map
                                 flies there; autotarget_submit), then wait autotarget_search_wait s
    5 plot the route             hold CamZoomOut 0.2 s (gives the focus back to the map), hold UI_Select 1 s
                                 (autotarget_plot)
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
# what each control and fixed key does in the galaxy map, for the steps' cheatsheet (outrider/target_help.py; a test
# keeps it in step with ACTIONS and FIXED_KEYS)
KEY_HELP = {"GalaxyMapOpen": "opens and closes the galaxy map (Outrider does both itself: steps 1 and 6)",
            "UI_Up": "moves the highlight up: straight after the map opens, onto \"Search the Galaxy\"",
            "UI_Down": "moves the highlight down a panel or list (in the search box, a letter key types itself)",
            "UI_Left": "moves the highlight left, along the panel's tabs and icons",
            "UI_Right": "moves the highlight right, along the panel's tabs and icons",
            "UI_Select": "selects what is highlighted; held on the map with a system under the crosshair, plots the route",
            "UI_Back": "backs out of a panel or the search",
            "CycleNextPanel": "the next tab of the open panel",
            "CamYawLeft": "turns the camera left; any camera move gives the focus back to the map",
            "CamYawRight": "turns the camera right (the default's first step: it closes a side panel the map reopened on)",
            "CamZoomIn": "zooms the camera in; gives the focus back to the map",
            "CamZoomOut": "zooms the camera out, keeping the found system under the crosshair (the default plot's first step)",
            "CamTranslateLeft": "moves the camera left", "CamTranslateRight": "moves the camera right",
            "CamTranslateForward": "moves the camera forward", "CamTranslateBackward": "moves the camera back",
            "Enter": "the Enter key, always (not a control: needs no binding)",
            "Paste": "Left Ctrl + V, always: pastes the clipboard"}
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
# step 5 for a route's next stop the route makes one jump (the Highway's after a supercharge, a survey route's): make it
# the target rather than plot a route to it. A plotted route is the game's planner's, and with "Use Jet-Cone Boost"
# off in its Route Settings it ignores the supercharge: 6 jumps to a stop the supercharged jump reaches (the author,
# 2026-10-23; Kurbo26 saw a stop added with it on). The system panel's icons: two UI_Rights reach the column from the
# system's details (one stopped short for Sol), "Target System" is eight UI_Downs from its top (Kurbo26's steps,
# checked in game by the author, a pause between keys: STEP_PAUSE). Discussion #12.
DEFAULT_TARGET = ("hold CamZoomOut 0.2", "press UI_Right", "press UI_Right") + ("press UI_Down",) * 8 + ("press UI_Select",)
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
# 2026-10-23 (discussion #12, Kurbo26; checked in game by the author): a name with several results (Sol, Solati...)
# defeats Enter, which only moves the focus out of the box to the panel's icons; and in the box a control bound to a
# letter (UI_Down on S) types it. The arrow key by name types nothing and moves into the list; UI_Select then picks
# the first result, the system itself when the name is whole, and flies there. One result or several alike.
DEFAULT_SUBMIT = ("wait 1.5", "press KEY_DOWN", "press UI_Select")
# a pause after each key of the three editable parts: back to back, the galaxy map can miss a press (eight UI_Downs
# down the system panel's icons lost some; 0.25 s each worked: the author, 2026-10-23, discussion #12)
STEP_PAUSE = 0.25
# the map's flight to the system after the search takes longer the further it is (the author, 2026-10-23: Sol from 5,000
# ly outlasted 2 s; a close jump needs less than 5): the search wait plus a second for each SEARCH_WAIT_STEP_LY to it,
# up to SEARCH_WAIT_MAX (a search wait set longer than that is kept as it is)
SEARCH_WAIT_STEP_LY, SEARCH_WAIT_MAX = 200.0, 7.0


def search_wait(base, ly):
    """Seconds to wait for the map to fly to a system `ly` away (None: not known, the base alone)."""
    if ly is None or ly < 0:
        return base
    return max(base, min(SEARCH_WAIT_MAX, base + int(ly // SEARCH_WAIT_STEP_LY)))


DEFAULTS = {"entry": "type", "map_wait": 5.0, "search_wait": 3.0, "key_delay": 0.05, "step_pause": STEP_PAUSE, "keys": {},
            "plot": list(DEFAULT_PLOT), "target": list(DEFAULT_TARGET), "route_target": True,
            "search": list(DEFAULT_SEARCH), "submit": list(DEFAULT_SUBMIT),
            "dry_run": False}
TAP_S = 0.05        # s a tapped key stays down
VERIFY_WAIT = 3.0   # s for Status.json to show the new Destination after the map closes
TARGET_CLOSE_WAIT = 2.0   # s after the target steps for the map to close by itself while the target is not seen taken;
#                           once the journal's FSDTarget (written at once) or the Destination says so, the map wait: the Music
#                           of the map's closing came 1-3 s after it (the author's recordings, 2026-10-23; review A3)
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


def build_steps(cfg=None, mode="plot"):
    """The sequence as steps: {"do", "phase", "label", ...}. do: press/hold (keys: a name to resolve), type, paste,
    focus (value, timeout), wait (secs), verify. mode "target": step 5 makes the system the target (cfg's `target`)
    instead of plotting a route to it (`plot`)."""
    c = dict(DEFAULTS, **(cfg or {}))
    s = [{"do": "press", "keys": "GalaxyMapOpen", "phase": 1, "label": "open the galaxy map", "opens": True},
         {"do": "focus", "value": GUI_GALAXY_MAP, "timeout": c["map_wait"], "phase": 1, "label": "wait for the galaxy map"},
         *[dict(parse_step(t), phase=2, label="focus the search field") for t in (c["search"] or DEFAULT_SEARCH)],
         {"do": "paste" if c["entry"] == "paste" else "type", "phase": 3, "label": "enter the system name"},
         *[dict(parse_step(t), phase=4, label="submit the search") for t in (c["submit"] or DEFAULT_SUBMIT)],
         {"do": "wait", "secs": c["search_wait"], "phase": 4, "label": "wait for the map to find the system", "search": True}]
    five = (c["target"] or DEFAULT_TARGET, "target the system") if mode == "target" else (c["plot"] or DEFAULT_PLOT, "plot the route")
    for t in five[0]:
        s.append(dict(parse_step(t), phase=5, label=five[1]))
    s += [{"do": "press", "keys": "GalaxyMapOpen", "phase": 6, "label": "close the galaxy map", "closes": True},
          {"do": "focus", "value": GUI_COCKPIT, "timeout": c["map_wait"], "phase": 6, "label": "wait for the cockpit"},
          {"do": "verify", "phase": 7, "label": "check the target"}]
    return s


def guard(status, next_id64, route_end=None, music=None):
    """Why auto-target must not start now: None, or (code, why). code "already" is no failure (the next system is the
    target already: Status.json's Destination, or the end of the route the game plotted, NavRoute.json's last hop when
    the next system is several jumps away); it comes first, whatever the flags or focus (review F11). Everything else
    is a reason not to press. music: the journal's latest Music event (file, position, track) or None: a GuiFocus 6
    after it said another track is the map closed (Status.json kept 6 for 18 s after Target System closed the map:
    review 2026-10-23 B2, Target next refused meanwhile)."""
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
    if focus == GUI_GALAXY_MAP and music and music[2] != "GalaxyMap":
        focus = GUI_COCKPIT
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


class _PerRun:
    """A Targeter attribute kept per worker thread, each run's own (None until set): two runs never share or overwrite
    one (review 2026-10-08 #1; the journal's marks too, review 2026-10-23 C4)."""

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        return self if obj is None else getattr(obj._run_local, self.name, None)

    def __set__(self, obj, value):
        setattr(obj._run_local, self.name, value)


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
        self._run_local = threading.local()   # each run's own state, per worker thread (_PerRun)
        # time, injectable so tests can run on a fake clock that moves only when something waits (the defaults are
        # the real ones): clock() for deadlines, wait(secs) an interruptible pause (True once cancelled), sleep(secs)
        # an uninterruptible one (the gaps between the keys of one combination, a hold that must complete)
        self.clock, self.wait, self.sleep = time.monotonic, self._wait, time.sleep

    # the running sequence's own token (auto-target switched off, the route cleared: set by its owner), its window
    # check (run's `front`), its journal readers (`music`, `fsd_target`), and its marks: the journal's Music and
    # FSDTarget at its first key, the Music at the key that closes the map (focus(), _target_taken(), _reopened()),
    # whether that key has gone, whether a Music override was logged, its log (say)
    run_cancel, run_front, run_music, run_fsd = _PerRun(), _PerRun(), _PerRun(), _PerRun()
    _music0, _music_t, _fsd0, _closing, _started, _overrode, _say = (_PerRun(), _PerRun(), _PerRun(), _PerRun(),
                                                                     _PerRun(), _PerRun(), _PerRun())

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

    def plan(self, mode="plot", entry=None):
        """(steps with "codes" and "what" filled in, missing [(name, why)]): missing are the keys a step needs that
        have no keyboard binding (or no evdev key), so nothing runs. mode: build_steps'; entry: "type" or "paste" over
        the configured one."""
        steps, missing, binds = build_steps(dict(self.cfg, entry=entry) if entry else self.cfg, mode), [], None
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
    def run(self, name, id64, status, system, dry_run=None, cancel=None, origin=None, route_end=None, front=None, ly=None,
            one_jump=False, music=None, fsd_target=None):
        """Target `name` (id64) now: status() gives Status.json's reading ({gui_focus, flags, flags2, destination,
        live}), system() the current system's id64. cancel: this run's own token (a threading.Event its owner sets:
        auto-target switched off, the route cleared or replaced); origin: the system the run was decided in (default:
        where you are when it starts), so a jump while it waited for the keyboard aborts it instead of becoming its new
        baseline; route_end: a callable giving the last hop of the route the game plotted (NavRoute.json), so a waypoint
        several jumps away counts as targeted; front: a callable giving None while Elite's window is the one in front,
        else why not, asked before every key (the first one too): a no stops the run, code "window" (None: nothing to
        check with, every key goes to whichever window has focus); ly: how far the system is, when known (over
        search_wait: a second more for each SEARCH_WAIT_STEP_LY, up to SEARCH_WAIT_MAX); one_jump: a route's next
        stop the route makes one jump, so the system itself must end up the target (a longer route the game plotted
        there fails, code "multi", saying how to fix it), and with `route_target` on it is targeted, not plotted (the
        plot steps after all when the target steps' keys are not bound); music: a callable giving the journal's latest
        Music event as (file, position, track), or None: the galaxy map's own word on whether it is open, which Status.json's
        GuiFocus can lag behind by many seconds or never give (focus()); fsd_target: likewise the journal's latest
        FSDTarget (file, position, id64), the moment Target System takes. -> {"ok", "phase", "label", "why", "code", "log",
        "dry_run"}; code "already" (nothing to do) or "wrong" (a different system was targeted: `wrong` names it).
        The step log is printed only when the run fails, or throughout a dry run: a success is the caller's one line."""
        dry = self.cfg.get("dry_run") if dry_run is None else dry_run
        result = {"ok": False, "phase": None, "label": None, "why": None, "code": None, "log": [], "dry_run": bool(dry)}
        tag = f"auto-target{' (dry run)' if dry else ''}: "

        def say(line):
            result["log"].append(line)
            if dry:
                self.log(tag + line)
        self.run_cancel, self.run_front, self.run_music, self.run_fsd = cancel, front, music, fsd_target
        self._say, entry = say, None
        try:
            while True:
                self._music0 = self._music_t = self._fsd0 = None
                self._closing = self._started = self._overrode = False
                self._run(result, say, name, id64, status, system, dry, origin, route_end, ly, one_jump, entry)
                # a pasted name that found nothing (the author, 2026-10-23: the first paste of a run came out empty, the
                # second worked): once more, typing it, when it can be typed (review C1)
                if entry or result["ok"] or dry or not result.get("pasted") or result["why"] != "no system was targeted" \
                        or untypeable(name) or self.cancelled():
                    break
                say("pasted nothing: typed it")
                entry = "type"
                result.update(phase=None, label=None, why=None, code=None, pasted=False)
        except BaseException:
            for line in result["log"]:   # an unexpected error: the steps so far are the debugging detail
                self.log(tag + line)
            raise
        finally:
            self.run_cancel = self.run_front = self.run_music = self.run_fsd = self._say = None
        if not result["ok"] and not dry:
            for line in result["log"]:
                self.log(tag + line)
        return result

    def _run(self, result, say, name, id64, status, system, dry, origin, route_end, ly=None, one_jump=False, entry=None):
        mode = "target" if one_jump and self.cfg.get("route_target") else "plot"
        steps, missing = self.plan(mode, entry)
        if missing and mode == "target":   # the icons need UI_Right and UI_Down: plot instead where they are not bound
            say("the target steps need " + ", ".join(f"{n} ({w})" for n, w in missing) + ": plotting instead")
            mode, (steps, missing) = "plot", self.plan("plot", entry)
        result["mode"] = mode
        # one jump: the system itself must be the target, never a plotted route merely ending there
        game_route, route_end = route_end, None if one_jump else route_end
        if missing:
            result.update(phase=0, label="read the bindings",
                          why="no keyboard binding for " + ", ".join(f"{n} ({w})" for n, w in missing))
            return
        start = guard(status(), id64, route_end, self._music())
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
            again = guard(status(), id64, route_end, self._music())
            if again:
                result.update(phase=0, label="check before the first key", why=again[1], code=again[0])
                return
            not_front = self.run_front() if self.run_front else None   # S74: the game's window is the one in front
            if not_front:
                result.update(phase=0, label="check before the first key", why=not_front, code="window")
                return
            self._music0, self._fsd0 = self._music(), self._fsd()   # before the first key: what comes after is this run's
            self._started = True
            # the Target System key: step 5's last key (a wait after it, set by hand, then runs with the cockpit expected)
            last5 = max((i for i, s in enumerate(steps) if s["phase"] == 5 and s["do"] in ("press", "hold")), default=None)
            for i, st in enumerate(steps):
                cur = st
                if st.get("closes") and mode == "target":
                    # Target System closes the map itself (the author's recordings, 2026-10-23: the close key then
                    # opened it again and the run said it failed, the target set): wait for it, then no close key
                    if self._closed_by_itself(st, status, system, here, expect, id64):
                        expect, close_pressed = {GUI_GALAXY_MAP, GUI_COCKPIT}, True
                        say(f"{st['phase']} {st['label']}: the galaxy map closed by itself: done")
                        continue
                self._check(st, status, system, here, expect)
                d = st["do"]
                if d in ("press", "hold"):
                    if st.get("opens"):
                        expect, opened = {GUI_COCKPIT, GUI_GALAXY_MAP}, True
                    elif st.get("closes"):
                        expect, close_pressed = {GUI_GALAXY_MAP, GUI_COCKPIT}, True
                    closing = st.get("closes") or (mode == "target" and i == last5)
                    if closing:   # the Music mark before the key: the map's closing Music may come while it is down
                        self._music_t = self._music()
                    self._tap(st["names"], st.get("secs", TAP_S), st)
                    if closing:
                        # the Target System key: the map may close at once (review A1: the pause after it met the
                        # cockpit and failed the run), and from here a jump with the target set is a success (A2)
                        self._closing = True
                        expect = expect | {GUI_COCKPIT}
                    if st["phase"] in (2, 4, 5) and self.cfg.get("step_pause"):   # the editable parts' keys, one at a time
                        self._sleep(self.cfg["step_pause"], st, status, system, here, expect)
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
                    result["pasted"] = True
                elif d == "focus":
                    self._wait_focus(st, status, system, here, expect)
                    expect = {st["value"]}
                elif d == "wait":
                    if st.get("search"):   # the map's flight there: longer the further it is
                        cur = st = dict(st, secs=search_wait(st["secs"], ly))
                    self._sleep(st["secs"], st, status, system, here, expect)
                elif d == "verify":
                    self._verify(st, id64, status, system, here, expect, route_end, name if one_jump else None, game_route)
                # what it did, keys included ("5 plot the route: hold Space for 1 s: done"): a log shows what was pressed
                say(self.describe([st])[0] + ": done")
            result.update(ok=True)
        except Abort as e:
            st = e.step or cur
            # the FSD charged (or the jump went) once the route was plotted and the map was closing: you set off before
            # step 7 looked. Not a failure when the target is set (or you arrived there): the jump confirms it
            if (close_pressed or self._closing) and e.code in ("jump", "moved") \
                    and (system() == id64 or targeted(status(), id64, route_end) or self._target_taken(id64, status)):
                say(f"{st['phase']} {st['label']}: {e.why}, the target was set: done")
                result.update(ok=True)
                return
            result.update(phase=st["phase"] if st else 0, label=st["label"] if st else "start", why=e.why,
                          code=e.code, **e.extra)
            say(f"stopped at step {result['phase']} ({result['label']}): {e.why}")
            if self._started:
                say(self._seen(status))
            # close the map only if this run opened it and it is still open (pressing it otherwise would open it). Once
            # its close key went down the map is closing (Status.json lags): pressed again it would open, unless the
            # close demonstrably failed (the wait for the cockpit timed out with the map still open)
            close_failed = e.why == "the galaxy map did not close"
            # (the device is still open under our lock even when switching off set `stop`: the finally closes it after)
            # after the Target System key the map closes itself: pressed then, the key would open it (review A2), so
            # only a map the journal shows opened again since that key is closed
            if opened and (not close_pressed or close_failed) and self.focus(status()) == GUI_GALAXY_MAP \
                    and (not self._closing or self._reopened()) \
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

    def _music(self):
        """The journal's latest Music event (file, position, track), or None (none, or no way to read it)."""
        try:
            return self.run_music() if self.run_music else None
        except Exception:  # noqa: BLE001 -- the journal is a second opinion: without it, Status.json alone
            return None

    def focus(self, s):
        """GuiFocus as the run takes it: Status.json's, unless the journal's Music, newer than the run's start, says
        otherwise about the galaxy map (the author's recording, 2026-10-23: the map opened, Music "GalaxyMap" at once and
        Status.json still the cockpit; Target System closed it, Music "Supercruise" and Status.json still the map, 18 s).
        Other screens (a panel, the system map) are Status.json's word alone."""
        g = (s or {}).get("gui_focus") or 0
        m = self._music()
        if not m:
            return g
        # once the key that closes the map has gone (Target System's, the close key), only Music written after it counts:
        # the opening's GalaxyMap no longer says the map is open (review A5), and before it a track change says nothing
        # of the map closing (A4)
        base = self._music_t if self._closing else self._music0
        if m[2] == "GalaxyMap" and g == GUI_COCKPIT and self._newer(m, base):
            out = GUI_GALAXY_MAP
        elif m[2] != "GalaxyMap" and g == GUI_GALAXY_MAP and self._closing and self._newer(m, base):
            out = GUI_COCKPIT
        else:
            return g
        if not self._overrode and self._say:   # the first in a run, in its log (review C2)
            self._overrode = True
            self._say(f"the journal's Music {m[2]!r} taken over Status.json's GuiFocus {g}")
        return out

    def _seen(self, status):
        """What both sources said as a run failed, its log's last line (review 2026-10-23 C2): Status.json's GuiFocus,
        Destination and time; the journal's last Music and FSDTarget, before or since the run's first key."""
        try:
            s = status() or {}
        except Exception:  # noqa: BLE001 -- a log line: whatever there is
            s = {}
        dest = s.get("destination")
        dest = (dest.get("Name") or dest.get("System")) if isinstance(dest, dict) else None
        out = f"seen: Status.json GuiFocus {s.get('gui_focus') or 0}, Destination {dest or 'none'}, at {s.get('ts') or '?'}"
        when = lambda x, base: "since the first key" if self._newer(x, base) else "before the first key"
        m, f = self._music(), self._fsd()
        out += f"; the journal's Music {m[2]!r} ({when(m, self._music0)})" if m else "; no Music in the journal"
        if f:
            out += f", FSDTarget {f[2]} ({when(f, self._fsd0)})"
        return out

    @staticmethod
    def _newer(m, base):
        return m is not None and (base is None or m[0] != base[0] or m[1] > base[1])

    def _fsd(self):
        """The journal's latest FSDTarget (file, position, id64), or None."""
        try:
            return self.run_fsd() if self.run_fsd else None
        except Exception:  # noqa: BLE001 -- a second opinion: without it, Status.json's Destination alone
            return None

    def _target_taken(self, id64, status):
        """Whether the target is set: an FSDTarget for it since the run began, or Status.json's Destination."""
        f = self._fsd()
        return (self._newer(f, self._fsd0) and f[2] == id64) or targeted(status(), id64)

    def _reopened(self):
        """Whether the journal shows the galaxy map opened again since the Target System key."""
        m = self._music()
        return bool(m and m[2] == "GalaxyMap" and self._newer(m, self._music_t))

    def _closed_by_itself(self, st, status, system, here, expect, id64=None):
        """Whether the galaxy map closed by itself (the cockpit, by focus()): within TARGET_CLOSE_WAIT, or once the
        target is seen taken (FSDTarget, the Destination) within the map wait, as long as the Music can trail it."""
        start = self.clock()
        while True:
            self._check(st, status, system, here, expect)
            if self.focus(status()) == GUI_COCKPIT:
                return True
            left = (self.cfg.get("map_wait") or TARGET_CLOSE_WAIT) if self._target_taken(id64, status) else TARGET_CLOSE_WAIT
            if self.clock() - start >= left:
                return False
            self.wait(POLL_S)

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
        focus = self.focus(s)
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
            if self.focus(status()) == st["value"]:
                return
            self._check(st, status, system, here, expect)
            if self.clock() >= end:
                raise Abort(st, "the galaxy map did not open" if st["value"] == GUI_GALAXY_MAP
                            else "the galaxy map did not close")
            self.wait(POLL_S)

    def _verify(self, st, id64, status, system, here, expect, route_end=None, one_jump=None, game_route=None):
        """one_jump: the stop's name when the route makes it one jump: a route the game plotted to it (game_route's
        last hop) is then the failure it is, said with its fix."""
        end = self.clock() + VERIFY_WAIT
        while True:
            if targeted(status(), id64, route_end):   # the next system, or a plotted route ending there (review F2)
                return
            self._check(st, status, system, here, expect)
            if self.clock() >= end:
                if one_jump and game_route and game_route() == id64:
                    raise Abort(st, f"the game plotted more than one jump to {one_jump}, which the route makes in one: "
                                    "tick Use Jet-Cone Boost in the galaxy map's Route Settings", code="multi")
                dest = (status() or {}).get("destination")
                # a body of the system you are in (the neutron star targeted before the supercharge) is no wrong
                # system, only nothing targeted (review 2026-10-23 B1)
                if isinstance(dest, dict) and dest.get("System") is not None and dest.get("System") != here:
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
