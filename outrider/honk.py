"""Auto honk: hold Primary Fire on arriving in a system, so the Discovery Scanner fires (optional; Linux, and
Windows as an experiment: outrider/winkeys.py presses the keys there with SendInput, the rest is the same).

Outrider presses keys on a virtual keyboard (the kernel's uinput, the same route Steam Input uses), so the
game sees ordinary key presses, under Wayland or X and through Proton alike. For it to work:

1. The Discovery Scanner must be on PRIMARY FIRE in the fire group that is active when you jump.
2. Primary Fire needs a keyboard binding (as its first or second binding) in Elite's controls. With
   key = "auto" (the default) Outrider reads it from your active controls preset -- modifiers too, such
   as the Alt+Alt+K that VoiceAttack profiles use -- so whatever is bound there is what gets pressed.
3. The python evdev package (in requirements.txt) and write access to /dev/uinput: Steam's controller
   rule already grants that to the logged-in user on most distributions.

The keys go to whichever window has focus: if you alt-tab away during a jump they land there instead,
so the page's alerts dialog has a quick on/off.

    python3 -m outrider.honk --test 10     count down 10 s (click into the game), then press Primary Fire once
    python3 -m outrider.honk --show        print the binding it would press
"""
import glob
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET

from . import ROOT   # the repository: ed_outrider.toml and .venv are there

DEFAULT_KEY = "auto"   # read Primary Fire's keyboard binding from the active controls preset

# Elite's key names -> evdev's, where they differ by more than the prefix
ELITE_KEYS = {
    "LeftAlt": "LEFTALT", "RightAlt": "RIGHTALT", "LeftControl": "LEFTCTRL", "RightControl": "RIGHTCTRL",
    "LeftShift": "LEFTSHIFT", "RightShift": "RIGHTSHIFT", "LeftWin": "LEFTMETA", "RightWin": "RIGHTMETA",
    "Return": "ENTER", "Enter": "ENTER", "Equals": "EQUAL", "LeftBracket": "LEFTBRACE", "RightBracket": "RIGHTBRACE",
    "SemiColon": "SEMICOLON", "Period": "DOT", "BackSlash": "BACKSLASH", "Grave": "GRAVE", "Apostrophe": "APOSTROPHE",
    "UpArrow": "UP", "DownArrow": "DOWN", "LeftArrow": "LEFT", "RightArrow": "RIGHT", "PageUp": "PAGEUP",
    "PageDown": "PAGEDOWN", "Numpad_Add": "KPPLUS", "Numpad_Subtract": "KPMINUS", "Numpad_Multiply": "KPASTERISK",
    "Numpad_Divide": "KPSLASH", "Numpad_Decimal": "KPDOT", "Numpad_Enter": "KPENTER", "CapsLock": "CAPSLOCK",
    "ScrollLock": "SCROLLLOCK", "NumLock": "NUMLOCK", "Backspace": "BACKSPACE", "Space": "SPACE", "Tab": "TAB",
    "Escape": "ESC", "Insert": "INSERT", "Delete": "DELETE", "Home": "HOME", "End": "END", "Minus": "MINUS",
    "Comma": "COMMA", "Slash": "SLASH", "Pause": "PAUSE",
    # names with no same-named evdev key (upper-casing them gives a code evdev does not have)
    "Apps": "COMPOSE", "Numpad_Equals": "KPEQUAL", "Numpad_Comma": "KPCOMMA", "OEM_102": "102ND",
    "Hash": "BACKSLASH", "PrintScreen": "SYSRQ", "PrevTrack": "PREVIOUSSONG", "NextTrack": "NEXTSONG",
    "MediaStop": "STOPCD", "Calculator": "CALC", "WebHome": "HOMEPAGE",
}


def _import_evdev():
    """evdev, from this interpreter or from the repository's .venv; None if neither has it."""
    try:
        import evdev
        return evdev
    except ImportError:
        pass
    venv = os.path.join(ROOT, ".venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages")
    if os.path.isdir(venv) and venv not in sys.path:
        sys.path.append(venv)
        try:
            import evdev
            return evdev
        except ImportError:
            sys.path.remove(venv)
    return None


WINDOWS = sys.platform.startswith("win")
EXPERIMENTAL = " (experimental on Windows)" if WINDOWS else ""   # said in every "ready" status there
KEYS_WORD = "Windows key" if WINDOWS else "evdev"                  # "no evdev equivalent for KEY_..."


def keyboard_backend():
    """What presses keys on this system: evdev on Linux (None without the package), outrider.winkeys on Windows,
    None anywhere else."""
    if sys.platform.startswith("linux"):
        return _import_evdev()
    if sys.platform.startswith("win"):
        from . import winkeys
        return winkeys
    return None


def elite_key(name):
    """'Key_K' -> 'KEY_K', 'Key_Numpad_0' -> 'KEY_KP0', 'Key_LeftAlt' -> 'KEY_LEFTALT'; None if not a key."""
    n = str(name or "")
    if not n.startswith("Key_"):
        return None
    n = n[4:]
    m = re.fullmatch(r"Numpad_(\d)", n)
    if m:
        return "KEY_KP" + m.group(1)
    return "KEY_" + ELITE_KEYS.get(n, n).upper()


def bindings_dir(journal_dirs=()):
    """Elite's Options/Bindings folder: next to the journals' user folder under Proton, or %LOCALAPPDATA%."""
    for d in journal_dirs or ():
        parts = os.path.normpath(d).split(os.sep)
        if "Saved Games" in parts:
            home = os.sep.join(parts[:parts.index("Saved Games")]) or os.sep
            cand = os.path.join(home, "AppData", "Local", "Frontier Developments", "Elite Dangerous", "Options", "Bindings")
            if os.path.isdir(cand):
                return cand
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cand = os.path.join(local, "Frontier Developments", "Elite Dangerous", "Options", "Bindings")
        if os.path.isdir(cand):
            return cand
    return None


_binding_cache = {}   # controls folder -> (its files' names and mtimes, primary_fire_binding's answer)


def primary_fire_binding(journal_dirs=()):
    """Primary Fire's keyboard binding in the active controls preset: (["KEY_LEFTALT", ..., "KEY_K"], text)
    with modifiers first, or (None, why not). Called for every page update, so the answer is kept until a
    file in the controls folder changes; a file Elite is rewriting at that moment is a reason, not an error."""
    d = bindings_dir(journal_dirs)
    if not d:
        return None, "Elite's controls folder was not found"
    try:
        stamp = tuple(sorted((p, os.path.getmtime(p)) for p in glob.glob(os.path.join(glob.escape(d), "*.start"))
                             + glob.glob(os.path.join(glob.escape(d), "*.binds"))))
        hit = _binding_cache.get(d)
        if hit and hit[0] == stamp:
            return hit[1]
        answer = _read_binding(d)
    except OSError as e:   # a file removed or rewritten between listing and reading it
        return None, f"Elite's controls could not be read ({e})"
    _binding_cache[d] = (stamp, answer)
    return answer


# StartPreset.4.start (Odyssey) names one preset per line: General, Ship, SRV, On foot. The interface keys (UI_*) are
# General controls, Primary Fire and the galaxy map Ship ones; an older file has a single line for everything
GENERAL_ACTIONS = frozenset({"UI_Up", "UI_Down", "UI_Left", "UI_Right", "UI_Select", "UI_Back", "UI_Toggle",
                             "CycleNextPage", "CyclePreviousPage"})


# the preset category an action is bound in: StartPreset.4.start's line for it (the rail's SRV and on-foot buttons)
PRESET_LINE = {"general": 0, "ship": 1, "srv": 2, "foot": 3}


def _preset_file(d, action, hint, category=None):
    """(preset name or None, the .binds file to read) for `action`, or (None, None, why not). category: the preset the
    action is bound in ("ship", "srv", "foot"; default: General for the UI_* keys, else Ship)."""
    starts = sorted(glob.glob(os.path.join(glob.escape(d), "StartPreset*.start")), key=os.path.getmtime)
    preset = None
    if starts:
        with open(starts[-1], encoding="utf-8", errors="replace") as f:
            lines = [x.strip() for x in f.read().splitlines()]
        line = PRESET_LINE.get(category, 0 if action in GENERAL_ACTIONS else 1)
        preset = (lines[line] if len(lines) >= 4 and lines[line] else lines[0] if lines else "") or None
    if preset:
        files = sorted(glob.glob(os.path.join(glob.escape(d), glob.escape(preset) + ".*binds")), key=os.path.getmtime)
        if not files:   # the built-in presets live in the game's install folder, not here
            return None, None, (f"the controls preset {preset!r} is a built-in one (no .binds file in the controls folder): "
                                f"bind {action_label(action)} in a custom preset" + (f", or set {hint}" if hint else ""))
    else:
        files = sorted(glob.glob(os.path.join(glob.escape(d), "Custom*.binds")), key=os.path.getmtime)
        if not files:
            return None, None, "no controls preset found"
    return preset, files[-1], None


def action_label(action):
    """'PrimaryFire' -> 'Primary Fire', 'GalaxyMapOpen' -> 'Galaxy Map Open', 'UI_Select' -> 'UI Select'."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(action)).replace("_", " ")


def _action_binding(root, action, preset, hint):
    """`action`'s keyboard binding in a parsed .binds root: (keys with modifiers first, text) or (None, why not)."""
    node = root.find(action)
    name = action_label(action)
    mixed = False   # a keyboard key held with a joystick/HOTAS modifier: a virtual keyboard cannot press it
    for slot in ("Primary", "Secondary"):
        b = node.find(slot) if node is not None else None
        if b is None or b.get("Device") != "Keyboard":
            continue
        modifiers = b.findall("Modifier")
        if any(m.get("Device") != "Keyboard" for m in modifiers):
            mixed = True   # pressing the bare key would be some other control
            continue
        key = elite_key(b.get("Key"))
        mods = [elite_key(m.get("Key")) for m in modifiers]
        if key and all(mods):
            return mods + [key], f"{' + '.join(key_label(k) for k in mods + [key])} ({slot.lower()} binding of {name} in {preset or 'your preset'})"
    # what it IS bound to (a HOTAS button): a virtual keyboard cannot press it, since the game takes a joystick
    # button only from that joystick, so the words say where it is now and what to add
    other = next((f"{b.get('Key').replace('_', ' ')} on {b.get('Device')}" for slot in ("Primary", "Secondary")
                  for b in [node.find(slot) if node is not None else None]
                  if b is not None and b.get("Device") not in (None, "", "Keyboard", "{NoDevice}") and b.get("Key")), None)
    return None, (f"{name} has no keyboard binding in {preset or 'your preset'}"
                  + (f" (now only {other}: a joystick button cannot be pressed from here)" if other else "")
                  + (" (a key with a joystick modifier cannot be pressed from here)" if mixed else "")
                  + ": give it a keyboard key as its second binding in Elite's controls" + (f", or set {hint}" if hint else ""))


def _read_action(d, action, hint, parsed, category=None):
    """One action's binding from the controls folder d (OSError passes through); parsed caches each file's root."""
    preset, path, why = _preset_file(d, action, hint, category)
    if why:
        return None, why
    if path not in parsed:
        try:
            parsed[path] = ET.parse(path).getroot()
        except ET.ParseError as e:
            parsed[path] = f"{os.path.basename(path)} could not be read ({e})"
    root = parsed[path]
    if isinstance(root, str):
        return None, root
    return _action_binding(root, action, preset, hint)


def _read_binding(d):
    """primary_fire_binding for the controls folder d, read from disk (OSError passes through)."""
    return _read_action(d, "PrimaryFire", "[autohonk] key", {})


_bindings_cache = {}   # (controls folder, actions, hint) -> (its files' names and mtimes, keyboard_bindings' answer)


def keyboard_bindings(journal_dirs, actions, hint="[highway] autotarget_keys", category=None):
    """Several actions' keyboard bindings in the active controls preset: {action: (keys or None, text or why)}, read
    once per change of the controls folder (as primary_fire_binding). Every action gets an answer: a missing folder
    or an unreadable file is each action's reason. category: the preset they are bound in (see _preset_file)."""
    actions = tuple(actions)
    d = bindings_dir(journal_dirs)
    if not d:
        return {a: (None, "Elite's controls folder was not found") for a in actions}
    try:
        stamp = tuple(sorted((p, os.path.getmtime(p)) for p in glob.glob(os.path.join(glob.escape(d), "*.start"))
                             + glob.glob(os.path.join(glob.escape(d), "*.binds"))))
        key = (d, actions, hint, category)
        hit = _bindings_cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
        parsed = {}
        answer = {a: _read_action(d, a, hint, parsed, category) for a in actions}
    except OSError as e:
        return {a: (None, f"Elite's controls could not be read ({e})") for a in actions}
    _bindings_cache[key] = (stamp, answer)
    return answer


def key_label(name):
    """'KEY_LEFTALT' -> 'Left Alt', 'KEY_KP0' -> 'Numpad 0', 'KEY_K' -> 'K' (for messages)."""
    n = str(name)[4:] if str(name).startswith("KEY_") else str(name)
    special = {"LEFTALT": "Left Alt", "RIGHTALT": "Right Alt", "LEFTCTRL": "Left Ctrl", "RIGHTCTRL": "Right Ctrl",
               "LEFTSHIFT": "Left Shift", "RIGHTSHIFT": "Right Shift", "LEFTMETA": "Left Super", "RIGHTMETA": "Right Super",
               "COMPOSE": "Menu (Apps)", "KPPLUS": "Numpad +", "KPMINUS": "Numpad -", "KPASTERISK": "Numpad *",
               "KPSLASH": "Numpad /", "KPDOT": "Numpad .", "KPENTER": "Numpad Enter", "KPCOMMA": "Numpad ,",
               "KPEQUAL": "Numpad =", "SYSRQ": "Print Screen", "102ND": "OEM 102"}
    if n in special:
        return special[n]
    m = re.fullmatch(r"KP(\d)", n)
    return f"Numpad {m.group(1)}" if m else n.replace("_", " ").title() if len(n) > 1 else n


def parse_combo(text):
    """'KEY_LEFTALT+KEY_K' or 'alt+k' style text -> ['KEY_LEFTALT', 'KEY_K'] (names not yet checked)."""
    out = []
    for part in str(text or "").split("+"):
        p = part.strip().upper()
        if not p:
            continue
        p = {"ALT": "LEFTALT", "CTRL": "LEFTCTRL", "CONTROL": "LEFTCTRL", "SHIFT": "LEFTSHIFT"}.get(p, p)
        out.append(p if p.startswith("KEY_") else "KEY_" + p)
    return out


def key_code(evdev, name):
    """An evdev key code from a name: 'KEY_KP0', 'kp0' and 'KP0' all work. None if unknown."""
    n = str(name or "").strip().upper()
    if not n.startswith("KEY_"):
        n = "KEY_" + n
    code = evdev.ecodes.ecodes.get(n)
    return code if isinstance(code, int) else None


class NotNow(Exception):
    """press(): the check made under the lock, just before the first key, gave a reason not to press now (the cockpit
    lost the focus, a jump started, auto honk was switched off while it waited for the keyboard). Nothing was pressed;
    the caller may wait and try again."""


class Honker:
    """A virtual keyboard; press() holds Primary Fire's key (with its modifiers) for `hold` seconds."""

    def __init__(self, key=DEFAULT_KEY, hold=6.0, journal_dirs=()):
        self.key, self.hold, self.journal_dirs = key, hold, list(journal_dirs or ())
        self.evdev = keyboard_backend()   # evdev, or its Windows stand-in (outrider/winkeys.py)
        self.ui = None
        # who wants the device open: "honk" (auto honk and its Test button) and "target" (the Highway's auto-target);
        # it is closed when the last one lets go
        self.owners = set()
        self.lock = threading.Lock()   # held by press() for the whole hold, and by auto-target for its whole sequence
        self.stop = threading.Event()  # close() during a hold: let go now, then close the device
        self.status = ("Linux and Windows only" if not (sys.platform.startswith("linux") or WINDOWS)
                       else "needs the python evdev package (pip install evdev)" if not self.evdev else "off")

    @property
    def available(self):
        return self.evdev is not None

    @property
    def ready(self):
        return self.ui is not None and not self.stop.is_set()

    def combo(self):
        """(keys, description) to press now: read from the controls preset for "auto" (so a rebind is
        picked up without a restart), else the configured combination. keys is None when there is none."""
        if str(self.key).strip().lower() == "auto":
            keys, what = primary_fire_binding(self.journal_dirs)
            # checked here too, or the status says ready and every press fails on a key evdev lacks
            bad = [k for k in keys if key_code(self.evdev, k) is None] if keys and self.evdev else []
            if bad:
                return None, (f"no {KEYS_WORD} equivalent for {', '.join(bad)} (Primary Fire's keyboard binding): "
                              "bind it to another key, or give the key in Settings -> Auto honk")
            return keys, what
        keys = parse_combo(self.key)
        bad = [k for k in keys if key_code(self.evdev, k) is None] if self.evdev else []
        if not keys or bad:
            return None, f"unknown key {', '.join(bad) or self.key!r} (use evdev names such as KEY_KP0, or KEY_LEFTALT+KEY_K)"
        return keys, " + ".join(key_label(k) for k in keys)

    def open(self, owner="honk"):
        """Create the virtual keyboard (once, with every key, so a changed binding needs no restart). `owner` says who
        wants it; only auto honk's own opening sets its status."""
        if not self.evdev:
            return bool(self.ui)
        self.owners.add(owner)
        if self.ui:
            if self.stop.is_set():   # reopened while a press was still letting go: keep the device
                self.stop.clear()
            if owner == "honk":      # already open for auto-target: auto honk's status still says what it presses
                keys, what = self.combo()
                self.status = f"ready: holds {what} for {self.hold:g} s{EXPERIMENTAL}" if keys else f"not ready: {what}"
            return True
        keys, what = self.combo()
        e = self.evdev.ecodes
        try:
            all_keys = sorted(v for k, v in e.ecodes.items() if k.startswith("KEY_") and isinstance(v, int) and v < 0x2ff)
            self.ui = self.evdev.UInput({e.EV_KEY: all_keys}, name="ED Outrider auto honk")
        except (OSError, self.evdev.UInputError) as err:
            self.owners.discard(owner)
            self.device_error = (f"cannot press keys on Windows ({err})" if WINDOWS
                                 else f"cannot create the virtual keyboard ({err}); /dev/uinput needs to be writable")
            if owner == "honk":
                self.status = self.device_error
            return False
        if owner == "honk":
            self.status = f"ready: holds {what} for {self.hold:g} s{EXPERIMENTAL}" if keys else f"not ready: {what}"
        return True

    device_error = None   # why the virtual keyboard could not be created (the last try)

    def close(self, owner="honk"):
        """Close the virtual keyboard once nobody else wants it. Called on the event loop, so it never waits for a
        press: during a hold (or an auto-target sequence) it cuts it short, and the one holding the keys closes the
        device once it has let go of them."""
        self.owners.discard(owner)
        if self.owners:
            return   # still wanted (auto honk off while auto-target is on, or the other way round)
        self.stop.set()
        if not self.lock.acquire(blocking=False):
            return   # press() is holding keys: it sees `stop` and closes after releasing them
        try:
            if self.stop.is_set():   # not reopened meanwhile
                self._close_now()
        finally:
            self.lock.release()

    def shutdown(self):
        """Outrider stopping: every owner gone, a hold under way lets go now (it sees `stop`), a press still waiting for
        the lock is refused (it checks `stop` under the lock), and the device closes once the keys are up."""
        self.owners.clear()
        self.stop.set()
        if self.lock.acquire(blocking=False):
            try:
                self._close_now()
                self.stop.set()   # _close_now cleared it: keep refusing anything still queued
            finally:
                self.lock.release()

    def _close_now(self):
        """With self.lock held."""
        if self.ui:
            try:
                self.ui.close()
            except OSError:
                pass
        self.ui = None
        self.stop.clear()

    def press(self, check=None, cancel=None):
        """Hold Primary Fire's keys for `hold` seconds (blocking: run it on a worker thread). Returns the
        description of what was pressed, or None when the hold was cut short (close(), or `cancel`); raises
        ValueError when there is nothing to press. check: a callable run under the lock just before the first key
        (the wait for the lock can be long: auto-target holds it for its whole sequence) returning a reason not to
        press, or None; a reason raises NotNow and nothing is pressed. cancel: this press's own token (a
        threading.Event: auto honk switched off while auto-target keeps the device open); it ends the hold early
        without closing the device."""
        if not self.ready:
            raise ValueError("the virtual keyboard is not open")
        keys, what = self.combo()
        if not keys:
            self.status = f"not ready: {what}"
            raise ValueError(what)
        codes = [key_code(self.evdev, k) for k in keys]
        e = self.evdev.ecodes
        with self.lock:
            ui = self.ui   # a press queued behind another finds the device closed by then
            if ui is None or self.stop.is_set():
                if ui is not None and not self.owners:
                    self._close_now()
                raise ValueError("the virtual keyboard is not open")
            why = (("switched off" if cancel is not None and cancel.is_set() else None) or (check() if check else None))
            if why:
                if self.stop.is_set() and not self.owners:   # close() came during the check: it left the closing to us
                    self._close_now()
                raise NotNow(why)
            done = []
            try:
                for c in codes:            # modifiers first, the key last, as a person would
                    ui.write(e.EV_KEY, c, 1)
                    ui.syn()
                    done.append(c)
                    time.sleep(0.03)
                self._hold(cancel)         # close() or `cancel` ends the hold early
            finally:
                for c in reversed(done):   # always let go, whatever happened
                    ui.write(e.EV_KEY, c, 0)
                    ui.syn()
                stopped = self.stop.is_set()
                if stopped and not self.owners:   # reopened during the hold (auto-target switched on): kept
                    self._close_now()
        if stopped or (cancel is not None and cancel.is_set()):
            return None
        if self.stop.is_set():   # close() came just after the check above, while the lock was still held
            self.close()
            return None
        self.status = f"ready: holds {what} for {self.hold:g} s{EXPERIMENTAL}"
        return what

    TAP_HOLD_S = 0.1   # a tap's key-down time (the game misses shorter presses now and then)

    def tap(self, keys, check=None, hold=None):
        """One short press of `keys` (modifiers first, released in reverse): a rail button. Blocking (a worker thread).
        Refused, never queued, while auto honk or auto-target hold the keyboard: NotNow with the reason, as is a reason
        from `check` (run under the lock just before the first key). ValueError when the device is not open or a key
        has no evdev code."""
        if not self.ready:
            raise ValueError("the virtual keyboard is not open")
        codes = [key_code(self.evdev, k) for k in keys or ()]
        if not codes or None in codes:
            raise ValueError(f"no {KEYS_WORD} key for {' + '.join(map(str, keys or ())) or 'nothing'}")
        e = self.evdev.ecodes
        if not self.lock.acquire(blocking=False):
            raise NotNow("auto honk or auto-target is pressing keys: try again in a moment")
        try:
            ui = self.ui
            if ui is None or self.stop.is_set():
                raise ValueError("the virtual keyboard is not open")   # (closed below if close() is waiting on us)
            why = check() if check else None
            if why:
                raise NotNow(why)
            done = []
            try:
                for c in codes:
                    ui.write(e.EV_KEY, c, 1)
                    ui.syn()
                    done.append(c)
                    time.sleep(0.03)
                time.sleep(self.TAP_HOLD_S if hold is None else hold)
            finally:
                for c in reversed(done):
                    ui.write(e.EV_KEY, c, 0)
                    ui.syn()
        finally:
            # close() while we held the lock (the key down, the check, or just as we took it) left the closing to us:
            # done now, however the tap ended (review R12)
            if self.stop.is_set() and not self.owners and self.ui is not None:   # (not reopened meanwhile)
                self._close_now()
            self.lock.release()

    def _hold(self, cancel=None):
        """Wait `hold` seconds, or until close() (stop) or this press's `cancel` is set."""
        end = time.monotonic() + self.hold
        while not self.stop.is_set() and not (cancel is not None and cancel.is_set()):
            left = end - time.monotonic()
            if left <= 0:
                return
            self.stop.wait(min(0.05, left))


UINPUT = "/dev/uinput"
# the udev rule that gives the logged-in user /dev/uinput (Steam's controller rule, the steam-devices package, has the same)
UACCESS_RULE = 'KERNEL=="uinput", SUBSYSTEM=="misc", OPTIONS+="static_node=uinput", TAG+="uaccess"'
UACCESS_FILE = "/etc/udev/rules.d/60-ed-outrider-uinput.rules"


def readiness(backend, combo, platform=None, uinput=UINPUT, exists=os.path.exists,
              writable=lambda p: os.access(p, os.W_OK), off=None):
    """Whether auto honk can work here, said up front (Settings -> Auto honk, GET /api/autohonk/check; S69), WITHOUT
    pressing anything: no virtual keyboard is created and no device opened, only looked at. backend: what
    keyboard_backend() gave (None: missing); combo: () -> (keys or None, text), Honker.combo (reads the controls preset
    only); off: why the keyboard is switched off on purpose (--simulate). -> {ready, checks: [{id, ok, label, fix,
    commands}]}: each check in order, a failed one with its fix in words and the commands that do it."""
    platform = sys.platform if platform is None else platform
    checks = []

    def check(cid, ok, label, fix=None, commands=()):
        checks.append({"id": cid, "ok": bool(ok), "label": label, "fix": None if ok else fix,
                       "commands": [] if ok else list(commands)})
    if off:
        check("off", False, f"the virtual keyboard is off ({off})", "start Outrider without --simulate")
    elif platform.startswith("win"):
        check("backend", backend is not None, "Windows key presses (SendInput, experimental)",
              "Outrider's Windows key presses could not load: say so in an issue on GitHub")
    elif not platform.startswith("linux"):
        check("platform", False, "auto honk runs on Linux and Windows only", "run Outrider on the game PC under Linux or Windows")
    else:
        check("evdev", backend is not None, "evdev" if backend is not None else "evdev is not installed",
              "Outrider's environment lacks the python evdev package: run ./launch_outrider.sh, which installs "
              "requirements.txt (building evdev needs your Python's headers: python3-dev on Debian and Ubuntu), or "
              "install it by hand in the Outrider folder", [".venv/bin/pip install evdev"])
        there = exists(uinput)
        check("uinput", there, f"{uinput}" if there else f"{uinput} is missing",
              "the kernel's uinput module is not loaded: load it now, and at every boot with the second command",
              ["sudo modprobe uinput", "echo uinput | sudo tee /etc/modules-load.d/uinput.conf"])
        if there:
            ok = writable(uinput)
            check("uinput_writable", ok, f"{uinput} writable" if ok else f"{uinput} is not writable for you",
                  "give the logged-in user access with a udev rule (Steam's controller rule, the steam-devices package, "
                  "is the same), then log out and in. The input group works too (sudo usermod -aG input $USER), but "
                  "lets every program you run read every keyboard",
                  [f"echo '{UACCESS_RULE}' | sudo tee {UACCESS_FILE}",
                   "sudo udevadm control --reload-rules && sudo udevadm trigger"])
    keys, what = combo()
    check("binding", keys, f"Primary Fire: {' + '.join(key_label(k) for k in keys)}" if keys else f"Primary Fire: {what}",
          "give Primary Fire a keyboard key in Elite's controls (as its second binding, keeping your trigger as the "
          "first), in a custom preset; or give the key in Settings -> Auto honk")
    return {"ready": all(c["ok"] for c in checks), "checks": checks}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Auto honk helper: show or test Primary Fire's keyboard binding.")
    p.add_argument("--show", action="store_true", help="print the binding it would press")
    p.add_argument("--test", type=float, metavar="SECONDS", help="count down, then hold Primary Fire once")
    p.add_argument("--hold", type=float, default=6.0, help="seconds to hold (default 6)")
    p.add_argument("--key", help="'auto' or a combination such as KEY_LEFTALT+KEY_K (default: [autohonk] key "
                                 "in ed_outrider.toml, else auto)")
    p.add_argument("--journals", action="append", default=[], help="journal folder (to find the controls preset)")
    a = p.parse_args(argv)
    cfg = {}
    try:   # ed_outrider's config, when it can be read: the same folders and key the server uses
        import tomllib
        with open(os.path.join(ROOT, "ed_outrider.toml"), "rb") as f:
            cfg = tomllib.load(f)
    except Exception:   # no file, no tomllib (Python before 3.11), a broken file
        pass
    sec = lambda n: cfg.get(n) if isinstance(cfg.get(n), dict) else {}   # a section that is not a table: ignored
    dirs = a.journals
    if not dirs:
        live = sec("journals").get("live")
        dirs = [live] if isinstance(live, str) else [d for d in live if isinstance(d, str)] if isinstance(live, list) else []
    if not dirs and sec("journals").get("live") is None:   # as the server does: auto-detect
        try:
            from . import unsold
            dirs = unsold.find_journal_dirs()[0]
        except Exception:
            dirs = []
    dirs = [os.path.expanduser(d) for d in dirs]
    key = a.key or str(sec("autohonk").get("key") or DEFAULT_KEY)
    h = Honker(key, a.hold, dirs)
    keys, what = h.combo()
    print(f"Primary Fire: {what}" if keys else f"no key to press: {what}")
    if not keys or a.test is None:
        return 0 if keys else 1
    if not h.open():
        print(h.status)
        return 1
    time.sleep(0.5)   # let the desktop notice the new keyboard
    for n in range(int(a.test), 0, -1):
        print(f"  pressing in {n} s: click into the game now", flush=True)
        time.sleep(1)
    print(f"holding {what} for {a.hold:g} s", flush=True)
    h.press()
    h.close()
    print("released; the journal shows FSSDiscoveryScan if the Discovery Scanner fired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
