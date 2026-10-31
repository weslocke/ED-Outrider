"""Finding Elite's window for the in-game overlay window: where it is, how big, whether it is in front.

Adapted from EDMC Modern Overlay (https://github.com/SweetJonnySauce/EDMCModernOverlay), files
overlay_client/window_tracking.py and overlay_client/follow_geometry.py at commit c78df18 (release 0.9.2), copyright
its authors, licensed under the GNU General Public License version 3.

Changed for ED Outrider on 2026-10-10: only the X11 tracker (wmctrl, xprop, xwininfo; on a Wayland session the
overlay window runs through XWayland, as Modern Overlay does on GNOME) and the Windows tracker are kept, the Wayland
compositor trackers left out; the trackers take an injectable `run` (subprocess.run) so tests need no X server; the
tracker factory reads no EDMC environment variables; `native_rect_to_qt` is Modern Overlay's
_convert_native_rect_to_qt_standard without its logging, and `title_bar_offset` its _apply_title_bar_offset likewise.
Changed on 2026-10-12 for auto-target (outrider/game_window.py): the trackers and `create_tracker` take a `match`
(which titles count as the game's: auto-target wants the game's own title exactly, never a browser tab about it), the
X11 tracker a `min_interval` (0: every poll asks afresh) and `create_tracker` the `run` it hands to it.
Changed on 2026-10-13 for the overlay's status pill and "keep showing when Elite is not the active window" (S8, S25,
S25b): the X11 tracker notes a missing xprop (`xprop_missing`: the game could never be "in front"); with
`inactive_checks` on and the game not in front, both trackers say whether its window is out of sight (X11: minimised,
_NET_WM_STATE_HIDDEN, or on another desktop than the current one and not viewable by xwininfo's map state, since a
window manager with a workspace per monitor calls the focused monitor's workspace the current one; Windows: cloaked, as
on another virtual desktop) and
whether other windows cover it (`WindowState.covered`, `covered_share` over COVERED_SHARE: X11 from the stacking order,
_NET_CLIENT_LIST_STACKING, and wmctrl's geometries; Windows by walking the z-order above it, `win_rects_above`). A native
Wayland window is in neither list: it is never seen covering the game.
"""
from __future__ import annotations

import ctypes
import logging
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

try:
    from ctypes import wintypes
except Exception:  # pragma: no cover - not every platform has it
    wintypes = None


@dataclass(slots=True)
class WindowState:
    """Geometry details for a tracked window in virtual desktop coordinates."""

    x: int
    y: int
    width: int
    height: int
    is_foreground: bool
    is_visible: bool
    identifier: str = ""
    global_x: Optional[int] = None
    global_y: Optional[int] = None
    covered: bool = False    # other windows over more than COVERED_SHARE of it (asked only with inactive_checks)


MonitorSnapshot = Tuple[str, int, int, int, int]
MonitorProvider = Callable[[], List[MonitorSnapshot]]
Geometry = Tuple[int, int, int, int]

_TITLE_PATTERN = re.compile(r"elite\s*-\s*dangerous", re.IGNORECASE)
_DWMWA_EXTENDED_FRAME_BOUNDS = 9
_DWMWA_CLOAKED = 14
TITLE_HINT = "elite - dangerous"
COVERED_SHARE = 0.25     # other windows over more than this share of the game's window: covered (S25b)
INACTIVE_EVERY_S = 1.0   # how often the out-of-sight and covered checks ask afresh (a few more xprop calls each)


def covered_share(rect: Geometry, others: List[Geometry]) -> float:
    """How much of `rect` (x, y, w, h) the rectangles `others` cover together, 0 to 1 (overlaps counted once)."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return 0.0
    cut = []
    for ox, oy, ow, oh in others:
        l, t, r, b = max(x, ox), max(y, oy), min(x + w, ox + ow), min(y + h, oy + oh)
        if r > l and b > t:
            cut.append((l, t, r, b))
    if not cut:
        return 0.0
    xs = sorted({v for l, _, r, _ in cut for v in (l, r)})
    area = 0
    for x0, x1 in zip(xs, xs[1:]):   # the union's area: strip by strip, the covered spans of each strip merged
        spans = sorted((t, b) for l, t, r, b in cut if l <= x0 and r >= x1)
        covered, end = 0, None
        for t, b in spans:
            if end is None or t > end:
                covered += b - t
                end = b
            elif b > end:
                covered += b - end
                end = b
        area += covered * (x1 - x0)
    return min(1.0, area / float(w * h))


def matches_window_title(title: str, hint: str = TITLE_HINT) -> bool:
    if not title:
        return False
    lowered = title.lower()
    if hint and hint in lowered:
        return True
    return bool(_TITLE_PATTERN.search(title))


def _invoke_monitor_provider(provider: Optional[MonitorProvider], logger: logging.Logger) -> List[MonitorSnapshot]:
    if provider is None:
        return []
    try:
        snapshot = provider()
    except Exception as exc:
        logger.debug("Monitor provider failed: %s", exc)
        return []
    return list(snapshot)


def _find_monitor_for_rect(monitors: List[MonitorSnapshot], x: int, y: int, width: int, height: int, *,
                           relative: bool) -> Optional[MonitorSnapshot]:
    best: Optional[MonitorSnapshot] = None
    best_area = 0
    for name, offset_x, offset_y, mon_w, mon_h in monitors:
        global_x = x + offset_x if relative else x
        global_y = y + offset_y if relative else y
        overlap_w = max(0, min(global_x + width, offset_x + mon_w) - max(global_x, offset_x))
        overlap_h = max(0, min(global_y + height, offset_y + mon_h) - max(global_y, offset_y))
        area = overlap_w * overlap_h
        if area > best_area:
            best_area = area
            best = (name, offset_x, offset_y, mon_w, mon_h)
    return best


def _augment_state_with_monitors(state: WindowState, monitors: List[MonitorSnapshot], logger: logging.Logger, *,
                                 absolute_geometry: Optional[Tuple[int, int, int, int]] = None) -> WindowState:
    width, height = state.width, state.height
    abs_x: Optional[int] = None
    abs_y: Optional[int] = None
    if absolute_geometry is not None:
        abs_x, abs_y, abs_width, abs_height = absolute_geometry
        if abs_width:
            width = abs_width
        if abs_height:
            height = abs_height
    monitor_info = None
    if abs_x is not None and abs_y is not None and monitors:
        monitor_info = _find_monitor_for_rect(monitors, abs_x, abs_y, width, height, relative=False)
    if monitor_info is None and monitors:
        monitor_info = _find_monitor_for_rect(monitors, state.x, state.y, state.width, state.height, relative=True)
    if monitor_info is not None:
        _name, offset_x, offset_y, _mon_w, _mon_h = monitor_info
        abs_x = abs_x if abs_x is not None else state.x + offset_x
        abs_y = abs_y if abs_y is not None else state.y + offset_y
    if abs_x is None or abs_y is None:
        return WindowState(x=state.x, y=state.y, width=width, height=height, is_foreground=state.is_foreground,
                           is_visible=state.is_visible, identifier=state.identifier)
    return WindowState(x=abs_x, y=abs_y, width=width, height=height, is_foreground=state.is_foreground,
                       is_visible=state.is_visible, identifier=state.identifier, global_x=abs_x, global_y=abs_y)


class X11Tracker:
    """Use wmctrl / xprop / xwininfo to locate Elite's window under X11 (and XWayland: Elite under Proton is an
    XWayland window on a Wayland session)."""

    def __init__(self, logger: logging.Logger, title_hint: str = TITLE_HINT,
                 monitor_provider: Optional[MonitorProvider] = None, run=None, match=None,
                 min_interval: float = 0.3) -> None:
        self._logger = logger
        self._title_hint = title_hint.lower()
        self._match = match or (lambda title: matches_window_title(title, self._title_hint))
        self._last_state: Optional[WindowState] = None
        self._last_refresh: float = 0.0
        self._min_interval: float = min_interval
        self._wmctrl_missing = False
        self._xprop_missing = False
        self._monitor_provider = monitor_provider
        self._run = run or subprocess.run
        # S25: with the game not in front, also ask whether it is out of sight or covered (the overlay window sets it
        # while "keep showing when Elite is not the active window" is on); the answer kept INACTIVE_EVERY_S
        self.inactive_checks = False
        self._inactive: Optional[Tuple[str, float, bool, bool]] = None   # (window id, when, hidden, covered)

    @property
    def missing(self) -> bool:
        """wmctrl is not installed (the window cannot follow the game)."""
        return self._wmctrl_missing

    @property
    def xprop_missing(self) -> bool:
        """xprop is not installed: which window is in front cannot be known, so the game never is (S8)."""
        return self._xprop_missing

    def poll(self) -> Optional[WindowState]:
        if self._wmctrl_missing:
            return None
        now = time.monotonic()
        if self._last_state and now - self._last_refresh < self._min_interval:
            return self._last_state
        try:
            result = self._run(["wmctrl", "-lGx"], check=False, capture_output=True, text=True, errors="replace", timeout=1.0)
        except FileNotFoundError:
            self._wmctrl_missing = True
            self._logger.warning("wmctrl is not installed: the overlay cannot find Elite's window (install wmctrl)")
            self._last_state = None
            return None
        except (subprocess.SubprocessError, ValueError, OSError) as exc:   # a byte not UTF-8 is replaced, never a crash
            self._logger.debug("wmctrl invocation failed: %s", exc)
            self._last_state = None
            self._last_refresh = now
            return None
        self._last_refresh = now
        if result.returncode != 0:
            self._last_state = None
            return None
        active_id = self._active_window_id()
        target_state: Optional[WindowState] = None
        best_state: Optional[WindowState] = None
        best_area = 0
        listed = {}   # every window wmctrl lists: id -> (desktop, (x, y, w, h)), for the covered check
        for line in result.stdout.splitlines():
            fields = line.split(None, 8)
            if len(fields) < 9:
                continue
            win_id_hex, desktop, x, y, w, h, _wm_class, _host, title = fields
            try:
                x_val, y_val, width, height = int(x), int(y), int(w), int(h)
                win_id = int(win_id_hex, 16)
                listed[win_id] = (int(desktop), (x_val, y_val, width, height))
            except ValueError:
                continue
            if not self._match(title):
                continue
            is_foreground = active_id is not None and win_id == active_id
            candidate = WindowState(x=x_val, y=y_val, width=width, height=height, is_foreground=is_foreground,
                                    is_visible=width > 0 and height > 0, identifier=win_id_hex)
            if is_foreground:
                target_state = candidate
                break
            area = max(width, 0) * max(height, 0)
            if area > best_area:
                best_state, best_area = candidate, area
        if target_state is None:
            target_state = best_state
        if target_state is None:
            self._last_state = None
            return None
        hidden = covered = False
        if self.inactive_checks and not target_state.is_foreground:
            hidden, covered = self._out_of_sight(target_state.identifier, listed, now)
        monitors = _invoke_monitor_provider(self._monitor_provider, self._logger)
        geometry = self._absolute_geometry(target_state.identifier) if monitors else None
        state = _augment_state_with_monitors(target_state, monitors, self._logger, absolute_geometry=geometry)
        if hidden or covered:
            state.is_visible = state.is_visible and not hidden
            state.covered = covered
        self._last_state = state
        return self._last_state

    def _out_of_sight(self, win_id_hex: str, listed, now: float) -> Tuple[bool, bool]:
        """(hidden, covered) for the game's window, not in front (S25, S25b): hidden when minimised
        (_NET_WM_STATE_HIDDEN) or on another desktop than the current one and not viewable (a window manager with one
        workspace per monitor, i3 and the like, reports the focused monitor's workspace as the current one while the
        game's stays in sight on its own monitor: xwininfo's map state decides, the desktop alone when it cannot be
        read); covered when the windows above it in the stacking order (on its desktop, not minimised) hide more than
        COVERED_SHARE of it."""
        kept = self._inactive
        if kept and kept[0] == win_id_hex and now - kept[1] < INACTIVE_EVERY_S:
            return kept[2], kept[3]
        win_id = int(win_id_hex, 16)
        desktop, rect = listed.get(win_id, (-1, (0, 0, 0, 0)))
        current = self._root_cardinal("_NET_CURRENT_DESKTOP")
        elsewhere = desktop >= 0 and current is not None and desktop != current
        hidden = self._minimised(win_id_hex) or (elsewhere and self._viewable(win_id_hex) is not True)
        covered = False
        if not hidden:
            stack = self._root_windows("_NET_CLIENT_LIST_STACKING")   # bottom to top
            above = stack[stack.index(win_id) + 1:] if win_id in stack else []
            others = []
            for other in above:
                o_desktop, o_rect = listed.get(other, (None, None))
                if o_rect is None or (o_desktop >= 0 and desktop >= 0 and o_desktop != desktop):
                    continue
                if covered_share(rect, [o_rect]) > 0 and not self._minimised(hex(other)):
                    others.append(o_rect)
            covered = covered_share(rect, others) > COVERED_SHARE
        self._inactive = (win_id_hex, now, hidden, covered)
        return hidden, covered

    def _xprop(self, args) -> Optional[str]:
        try:
            result = self._run(["xprop"] + list(args), check=False, capture_output=True, text=True, errors="replace", timeout=0.5)
        except FileNotFoundError:
            self._xprop_missing = True
            return None
        except (subprocess.SubprocessError, ValueError, OSError):
            return None
        return result.stdout if result.returncode == 0 and result.stdout else None

    def _minimised(self, win_id_hex: str) -> bool:
        out = self._xprop(["-id", win_id_hex, "_NET_WM_STATE"])
        return bool(out) and "_NET_WM_STATE_HIDDEN" in out

    def _viewable(self, win_id_hex: str) -> Optional[bool]:
        """Whether the window is mapped and on screen (xwininfo's Map State IsViewable); None when xwininfo cannot say."""
        try:
            result = self._run(["xwininfo", "-id", win_id_hex], check=False, capture_output=True, text=True, errors="replace", timeout=0.5)
        except (subprocess.SubprocessError, ValueError, OSError):   # FileNotFoundError is an OSError
            return None
        match = re.search(r"Map State:\s*(\w+)", result.stdout or "") if result.returncode == 0 else None
        return match.group(1) == "IsViewable" if match else None

    def _root_cardinal(self, prop: str) -> Optional[int]:
        out = self._xprop(["-root", prop])
        match = re.search(r"=\s*(\d+)", out or "")
        return int(match.group(1)) if match else None

    def _root_windows(self, prop: str) -> List[int]:
        out = self._xprop(["-root", prop]) or ""
        return [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]+", out.split("#", 1)[-1])] if "#" in out else []

    def set_monitor_provider(self, provider: Optional[MonitorProvider]) -> None:
        self._monitor_provider = provider

    def active_window_id(self) -> Optional[int]:
        """The window in front (_NET_ACTIVE_WINDOW): the overlay's own window while you arrange its panels."""
        return self._active_window_id()

    def _absolute_geometry(self, win_id_hex: str) -> Optional[Tuple[int, int, int, int]]:
        try:
            result = self._run(["xwininfo", "-id", win_id_hex], check=False, capture_output=True, text=True, errors="replace", timeout=0.5)
        except (subprocess.SubprocessError, ValueError, OSError):   # FileNotFoundError is an OSError
            return None
        if result.returncode != 0:
            return None
        abs_x = abs_y = width = height = None
        for line in result.stdout.splitlines():
            line = line.strip()
            for label, name in (("Absolute upper-left X:", "x"), ("Absolute upper-left Y:", "y"), ("Width:", "w"),
                                ("Height:", "h")):
                if line.startswith(label):
                    try:
                        value = int(line.split(":", 1)[1])
                    except ValueError:
                        value = None
                    if name == "x":
                        abs_x = value
                    elif name == "y":
                        abs_y = value
                    elif name == "w":
                        width = value
                    else:
                        height = value
        if abs_x is None or abs_y is None:
            return None
        return abs_x, abs_y, width or 0, height or 0

    def _active_window_id(self) -> Optional[int]:
        out = self._xprop(["-root", "_NET_ACTIVE_WINDOW"])
        if not out:
            return None
        match = re.search(r"0x[0-9a-fA-F]+", out)
        if not match:
            return None
        try:
            return int(match.group(0), 16)
        except ValueError:
            return None


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def client_bounds(user32, hwnd):
    """The game's picture on screen: its client rectangle (GetClientRect, its top-left through ClientToScreen), without
    a windowed game's title bar and frame (complete review 2026-10-30: the panels were placed and scaled against the
    whole window, the title bar's ~31 px too high). None when Windows cannot say (the caller keeps the window's)."""
    rect, origin = _RECT(), _POINT(0, 0)
    try:
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)) or not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
    except Exception:  # noqa: BLE001 -- a user32 without them: the window's rectangle as before
        return None
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None
    out = _RECT()
    out.left, out.top, out.right, out.bottom = origin.x, origin.y, origin.x + w, origin.y + h
    return out


GW_HWNDPREV = 3                                 # GetWindow: the window above in the z-order
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x20, 0x80
Z_WALK_MAX = 1000                               # windows looked at above the game, at most


def win_rects_above(user32, hwnd, bounds, cloaked, own_pid) -> List[Geometry]:
    """The rectangles (x, y, w, h) of the windows above `hwnd` in Windows' z-order that can hide it (S25b): shown, not
    minimised, not cloaked (on another virtual desktop), not click-through (an overlay such as this one) or a tool
    window, not this process's own. bounds(h) -> RECT or None; cloaked(h) -> bool (injected: tested without Windows)."""
    out = []
    pid = ctypes.c_ulong() if wintypes is None else wintypes.DWORD()
    above = user32.GetWindow(hwnd, GW_HWNDPREV)
    for _ in range(Z_WALK_MAX):
        if not above:
            break
        if user32.IsWindowVisible(above) and not user32.IsIconic(above) and not cloaked(above):
            ex = user32.GetWindowLongW(above, -20)   # GWL_EXSTYLE
            user32.GetWindowThreadProcessId(above, ctypes.byref(pid))
            if not ex & (WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW) and pid.value != own_pid:
                rect = bounds(above)
                if rect is not None and rect.right > rect.left and rect.bottom > rect.top:
                    out.append((int(rect.left), int(rect.top), int(rect.right - rect.left), int(rect.bottom - rect.top)))
        above = user32.GetWindow(above, GW_HWNDPREV)
    return out


class WindowsTracker:
    """Locate Elite's window using Win32 APIs (not yet tried against the game: Windows is experimental)."""

    def __init__(self, logger: logging.Logger, title_hint: str = TITLE_HINT, match=None) -> None:
        if wintypes is None or not hasattr(ctypes, "windll"):
            raise RuntimeError("the Win32 API is unavailable")
        self._logger = logger
        self._title_hint = title_hint.lower()
        self._match = match
        self._user32 = ctypes.windll.user32
        try:
            dwmapi = ctypes.windll.dwmapi
            self._dwm_get_window_attribute = dwmapi.DwmGetWindowAttribute
            self._dwm_get_window_attribute.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.POINTER(_RECT), ctypes.c_uint]
            self._dwm_get_window_attribute.restype = ctypes.c_int
            # the same call for DWMWA_CLOAKED, whose answer is an int (its own prototype: the one above takes a RECT)
            self._dwm_cloaked = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, ctypes.c_uint, ctypes.c_void_p,
                                                   ctypes.c_uint)(("DwmGetWindowAttribute", dwmapi))
        except Exception:
            self._dwm_get_window_attribute = None
            self._dwm_cloaked = None
        self.inactive_checks = False   # S25: as the X11 tracker's
        self._last_hwnd: Optional[int] = None
        self._enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(self._enum_windows)

    missing = False

    def poll(self) -> Optional[WindowState]:
        hwnd = self._resolve_window()
        if hwnd is None:
            return None
        rect = client_bounds(self._user32, hwnd) or self._window_bounds(hwnd)
        if rect is None:
            return None
        width, height = max(0, rect.right - rect.left), max(0, rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return None
        foreground = self._user32.GetForegroundWindow()
        is_foreground = bool(foreground and hwnd == foreground)
        is_visible = bool(self._user32.IsWindowVisible(hwnd)) and not bool(self._user32.IsIconic(hwnd))
        covered = False
        if self.inactive_checks and not is_foreground:
            is_visible = is_visible and not self._cloaked(hwnd)
            if is_visible:
                others = win_rects_above(self._user32, hwnd, self._window_bounds, self._cloaked, os.getpid())
                covered = covered_share((int(rect.left), int(rect.top), int(width), int(height)), others) > COVERED_SHARE
        return WindowState(x=int(rect.left), y=int(rect.top), width=int(width), height=int(height),
                           is_foreground=is_foreground, is_visible=is_visible, identifier=hex(hwnd), covered=covered)

    def _cloaked(self, hwnd: int) -> bool:
        """DWM keeps a window cloaked while it is on another virtual desktop (and for some hidden app windows)."""
        if self._dwm_cloaked is None:
            return False
        value = ctypes.c_int(0)
        try:
            ok = self._dwm_cloaked(hwnd, ctypes.c_uint(_DWMWA_CLOAKED), ctypes.addressof(value), ctypes.sizeof(value)) == 0
        except Exception:  # pragma: no cover - defensive
            return False
        return ok and value.value != 0

    def set_monitor_provider(self, provider: Optional[MonitorProvider]) -> None:
        return None   # monitor offsets are only used on X11

    def active_window_id(self) -> Optional[int]:
        return int(self._user32.GetForegroundWindow() or 0) or None

    def _resolve_window(self) -> Optional[int]:
        hwnd = self._last_hwnd
        if hwnd and self._is_target(hwnd):
            return hwnd
        self._last_hwnd = None
        self._user32.EnumWindows(self._enum_proc, 0)
        return self._last_hwnd

    def _enum_windows(self, hwnd: int, _: int) -> bool:
        if self._is_target(hwnd):
            self._last_hwnd = hwnd
            return False
        return True

    def _window_bounds(self, hwnd: int):
        rect = _RECT()
        if self._dwm_get_window_attribute is not None:
            result = self._dwm_get_window_attribute(hwnd, ctypes.c_uint(_DWMWA_EXTENDED_FRAME_BOUNDS), ctypes.byref(rect),
                                                    ctypes.sizeof(rect))
            if result == 0:
                return rect
        if not self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return rect

    def _is_target(self, hwnd: int) -> bool:
        if not self._user32.IsWindow(hwnd):
            return False
        length = self._user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return False
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip().lower()
        hit = self._match(buffer.value) if self._match else self._title_hint in title
        return bool(title) and hit and bool(self._user32.IsWindowVisible(hwnd))


def create_tracker(logger: logging.Logger, title_hint: str = TITLE_HINT,
                   monitor_provider: Optional[MonitorProvider] = None, platform: Optional[str] = None, run=None,
                   match=None, min_interval: float = 0.3):
    """The tracker for this platform, or None where there is none. match: which titles are the game's (default: the
    overlay's, any title naming the game); run: the X11 tracker's subprocess.run."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        try:
            return WindowsTracker(logger, title_hint, match=match)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Windows tracker unavailable: %s", exc)
            return None
    if platform.startswith("linux"):
        return X11Tracker(logger, title_hint, monitor_provider, run=run, match=match, min_interval=min_interval)
    logger.info("The overlay cannot follow the game's window on '%s'", platform)
    return None


# ---- native pixels to Qt's coordinates (Modern Overlay's follow_geometry) ----

@dataclass(frozen=True)
class ScreenInfo:
    name: str
    logical_geometry: Geometry
    native_geometry: Geometry
    device_ratio: float


def native_rect_to_qt(rect: Geometry, screen_info: Optional[ScreenInfo]) -> Geometry:
    """A window rectangle in the desktop's native pixels (what wmctrl reports) in Qt's logical coordinates, for a
    scaled desktop (a device pixel ratio other than 1)."""
    x, y, width, height = rect
    if width <= 0 or height <= 0 or screen_info is None:
        return rect
    logical, native = screen_info.logical_geometry, screen_info.native_geometry
    device_ratio = screen_info.device_ratio if screen_info.device_ratio > 0.0 else 1.0
    native_width, native_height = native[2], native[3]
    scale_x = logical[2] / native_width if native_width else 1.0
    scale_y = logical[3] / native_height if native_height else 1.0
    if math.isclose(scale_x, 1.0, abs_tol=1e-4):
        scale_x = 1.0 / device_ratio
    if math.isclose(scale_y, 1.0, abs_tol=1e-4):
        scale_y = 1.0 / device_ratio
    native_origin_x, native_origin_y = native[0], native[1]
    if math.isclose(native_origin_x, logical[0], abs_tol=1e-4):
        native_origin_x = logical[0] * device_ratio
    if math.isclose(native_origin_y, logical[1], abs_tol=1e-4):
        native_origin_y = logical[1] * device_ratio
    qt_x = logical[0] + (x - native_origin_x) * scale_x
    qt_y = logical[1] + (y - native_origin_y) * scale_y
    return (int(round(qt_x)), int(round(qt_y)), max(1, int(round(width * scale_x))), max(1, int(round(height * scale_y))))


def title_bar_offset(geometry: Geometry, title_bar_height: int, scale_y: float = 1.0) -> Geometry:
    """A windowed game's rectangle without its title bar (`title_bar_height` px at scale 1); a borderless one as it
    is (height 0)."""
    x, y, width, height = geometry
    if title_bar_height <= 0 or height <= 1:
        return geometry
    offset = min(int(round(float(title_bar_height) * max(scale_y, 0.0))), max(0, height - 1))
    if offset <= 0:
        return geometry
    return (x, y + offset, width, max(1, height - offset))
