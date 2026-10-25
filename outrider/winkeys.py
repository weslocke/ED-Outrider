"""Key presses on Windows, for auto honk, auto-target and the control rail (experimental: see DESIGN_NOTES.md).

A stand-in for the small part of the python evdev package that outrider/honk.py and outrider/target.py use on
Linux, so the code that decides what to press stays the same on both: `ecodes.ecodes` maps evdev's key names
(KEY_A, KEY_KP0, KEY_LEFTALT...) to codes, `ecodes.EV_KEY`, and `UInput(...)` whose write(EV_KEY, code, 1 or 0)
presses or releases a key. Here a code is the key's scan code (set 1, with 0xE000 added for an extended key such as
the arrows, right Ctrl or the numpad's Enter), sent with SendInput as a hardware scan code: the same route
VoiceAttack and EDCopilot use, so the game sees an ordinary key press on whatever window has the focus.

No dependency: user32's SendInput through ctypes. Tests replace `SEND` (a callable taking a list of
(scan code, extended, up) tuples) and never reach Windows. Windows refuses keys to a program running as
administrator from one that is not (no error is reported): run Elite normally, or Outrider as administrator too.
"""
import ctypes
import sys

EV_KEY = 1
EXTENDED = 0xE000

# evdev's key names -> scan codes (set 1); an extended key has EXTENDED added
_SCANS = {
    "ESC": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A,
    "0": 0x0B, "MINUS": 0x0C, "EQUAL": 0x0D, "BACKSPACE": 0x0E, "TAB": 0x0F,
    "Q": 0x10, "W": 0x11, "E": 0x12, "R": 0x13, "T": 0x14, "Y": 0x15, "U": 0x16, "I": 0x17, "O": 0x18, "P": 0x19,
    "LEFTBRACE": 0x1A, "RIGHTBRACE": 0x1B, "ENTER": 0x1C, "LEFTCTRL": 0x1D,
    "A": 0x1E, "S": 0x1F, "D": 0x20, "F": 0x21, "G": 0x22, "H": 0x23, "J": 0x24, "K": 0x25, "L": 0x26,
    "SEMICOLON": 0x27, "APOSTROPHE": 0x28, "GRAVE": 0x29, "LEFTSHIFT": 0x2A, "BACKSLASH": 0x2B,
    "Z": 0x2C, "X": 0x2D, "C": 0x2E, "V": 0x2F, "B": 0x30, "N": 0x31, "M": 0x32,
    "COMMA": 0x33, "DOT": 0x34, "SLASH": 0x35, "RIGHTSHIFT": 0x36, "KPASTERISK": 0x37, "LEFTALT": 0x38,
    "SPACE": 0x39, "CAPSLOCK": 0x3A,
    "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42, "F9": 0x43,
    "F10": 0x44, "PAUSE": 0x45, "SCROLLLOCK": 0x46,
    "KP7": 0x47, "KP8": 0x48, "KP9": 0x49, "KPMINUS": 0x4A, "KP4": 0x4B, "KP5": 0x4C, "KP6": 0x4D, "KPPLUS": 0x4E,
    "KP1": 0x4F, "KP2": 0x50, "KP3": 0x51, "KP0": 0x52, "KPDOT": 0x53, "102ND": 0x56, "F11": 0x57, "F12": 0x58,
    "KPEQUAL": 0x59, "F13": 0x64, "F14": 0x65, "F15": 0x66, "F16": 0x67, "F17": 0x68, "F18": 0x69, "F19": 0x6A,
    "F20": 0x6B, "F21": 0x6C, "F22": 0x6D, "F23": 0x6E, "F24": 0x76, "KPCOMMA": 0x7E,
    # extended keys (Windows reports Num Lock as the extended one and Pause as the plain 0x45)
    "NUMLOCK": EXTENDED | 0x45, "KPENTER": EXTENDED | 0x1C, "RIGHTCTRL": EXTENDED | 0x1D, "KPSLASH": EXTENDED | 0x35,
    "SYSRQ": EXTENDED | 0x37, "RIGHTALT": EXTENDED | 0x38, "HOME": EXTENDED | 0x47, "UP": EXTENDED | 0x48,
    "PAGEUP": EXTENDED | 0x49, "LEFT": EXTENDED | 0x4B, "RIGHT": EXTENDED | 0x4D, "END": EXTENDED | 0x4F,
    "DOWN": EXTENDED | 0x50, "PAGEDOWN": EXTENDED | 0x51, "INSERT": EXTENDED | 0x52, "DELETE": EXTENDED | 0x53,
    "LEFTMETA": EXTENDED | 0x5B, "RIGHTMETA": EXTENDED | 0x5C, "COMPOSE": EXTENDED | 0x5D,
    "PREVIOUSSONG": EXTENDED | 0x10, "NEXTSONG": EXTENDED | 0x19, "MUTE": EXTENDED | 0x20, "CALC": EXTENDED | 0x21,
    "PLAYPAUSE": EXTENDED | 0x22, "STOPCD": EXTENDED | 0x24, "VOLUMEDOWN": EXTENDED | 0x2E,
    "VOLUMEUP": EXTENDED | 0x30, "HOMEPAGE": EXTENDED | 0x32,
}


class ecodes:   # noqa: N801 -- named as evdev's module is: honk.key_code reads evdev.ecodes.ecodes
    EV_KEY = EV_KEY
    ecodes = {"KEY_" + name: code for name, code in _SCANS.items()}


class UInputError(OSError):
    """The keyboard could not be set up (not on Windows, or SendInput unavailable)."""


SEND = None   # tests: a callable taking [(scan, extended, up)]; None is SendInput itself


def _send_input(events):
    """events: [(scan code, extended, key up)] sent as one SendInput call; OSError when Windows took none of them."""
    from ctypes import wintypes
    ulong_ptr = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

    class MOUSEINPUT(ctypes.Structure):   # in the union only so INPUT has Windows' size
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    scancode, extended_key, keyup, input_keyboard = 0x0008, 0x0001, 0x0002, 1
    arr = (INPUT * len(events))()
    for i, (scan, extended, up) in enumerate(events):
        arr[i].type = input_keyboard
        arr[i].u.ki = KEYBDINPUT(0, scan, scancode | (extended_key if extended else 0) | (keyup if up else 0), 0, 0)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    sent = user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise OSError(ctypes.get_last_error(), f"SendInput took {sent} of {len(events)} key events")


class UInput:
    """evdev.UInput's part that Outrider uses: write(EV_KEY, code, 1 down / 0 up) presses at once; syn() and close()
    have nothing to do (there is no device). `capabilities` and `name` are accepted as evdev takes them and ignored."""

    def __init__(self, capabilities=None, name="ED Outrider"):
        if SEND is None and not sys.platform.startswith("win"):
            raise UInputError("Windows key presses need Windows")
        self.name = name

    def write(self, etype, code, value):
        if etype != EV_KEY or value not in (0, 1):
            return   # evdev's autorepeat (2) and other event types: nothing to send
        if not isinstance(code, int) or code <= 0:
            raise OSError(f"not a key code: {code!r}")
        (SEND or _send_input)([(code & 0xFF, bool(code & EXTENDED), value == 0)])

    def syn(self):
        pass

    def close(self):
        pass


def get_clipboard():
    """The Windows clipboard's text ("" when it holds none); OSError when Windows refused (another program holds it
    open). For the page's 📋 paste buttons."""
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32.GlobalLock.restype, k32.GlobalLock.argtypes = wintypes.LPVOID, (wintypes.HGLOBAL,)
    k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    u32.OpenClipboard.argtypes = (wintypes.HWND,)
    u32.IsClipboardFormatAvailable.argtypes = (wintypes.UINT,)
    u32.GetClipboardData.restype, u32.GetClipboardData.argtypes = wintypes.HANDLE, (wintypes.UINT,)
    for _ in range(10):   # another program may have it open for a moment
        if u32.OpenClipboard(None):
            break
        import time
        time.sleep(0.05)
    else:
        raise OSError(ctypes.get_last_error(), "the clipboard is in use by another program")
    try:
        if not u32.IsClipboardFormatAvailable(13):   # CF_UNICODETEXT
            return ""
        h = u32.GetClipboardData(13)
        p = k32.GlobalLock(h) if h else None
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def set_clipboard(text):
    """Put text on the Windows clipboard (as Unicode text); OSError when Windows refused (another program holds it
    open, say). For the Highway's copy of the next system and auto-target's paste entry."""
    _set_clipboard([(13, str(text).encode("utf-16-le") + b"\0\0")], "the text")   # CF_UNICODETEXT


def set_clipboard_image(dib, png=None):
    """Put a picture on the Windows clipboard: CF_DIB (a BMP without its file header: every program pastes it) and,
    given, the registered "PNG" format too (browsers, Discord). OSError when Windows refused. For the screenshots."""
    formats = [(8, dib)]   # CF_DIB
    if png:
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.RegisterClipboardFormatW.restype = ctypes.c_uint
        fmt = u32.RegisterClipboardFormatW("PNG")
        if fmt:
            formats.append((fmt, png))
    _set_clipboard(formats, "the picture")


def _set_clipboard(formats, what):
    """The clipboard emptied and given each (format, bytes); the clipboard owns each block once it is set."""
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32.GlobalAlloc.restype, k32.GlobalAlloc.argtypes = wintypes.HGLOBAL, (wintypes.UINT, ctypes.c_size_t)
    k32.GlobalLock.restype, k32.GlobalLock.argtypes = wintypes.LPVOID, (wintypes.HGLOBAL,)
    k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    k32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    u32.OpenClipboard.argtypes = (wintypes.HWND,)
    u32.SetClipboardData.restype, u32.SetClipboardData.argtypes = wintypes.HANDLE, (wintypes.UINT, wintypes.HANDLE)
    for _ in range(10):   # another program may have it open for a moment
        if u32.OpenClipboard(None):
            break
        import time
        time.sleep(0.05)
    else:
        raise OSError(ctypes.get_last_error(), "the clipboard is in use by another program")
    try:
        u32.EmptyClipboard()
        for fmt, data in formats:
            h = k32.GlobalAlloc(0x0002, len(data))   # GMEM_MOVEABLE
            if not h:
                raise OSError(ctypes.get_last_error(), "no memory for the clipboard")
            p = k32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(fmt, h):   # on success the clipboard owns h
                k32.GlobalFree(h)
                raise OSError(ctypes.get_last_error(), f"Windows did not take {what}")
    finally:
        u32.CloseClipboard()
