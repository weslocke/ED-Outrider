"""Finding Elite's window for the in-game overlay window: where it is, how big, whether it is in front.

Adapted from EDMC Modern Overlay (https://github.com/SweetJonnySauce/EDMCModernOverlay), files
overlay_client/window_tracking.py and overlay_client/follow_geometry.py at commit c78df18 (release 0.9.2), copyright
its authors, licensed under the GNU General Public License version 3.

Changed for ED Outrider on 2026-10-10: only the X11 tracker (wmctrl, xprop, xwininfo; on a Wayland session the
overlay window runs through XWayland, as Modern Overlay does on GNOME) and the Windows tracker are kept, the Wayland
compositor trackers left out; the trackers take an injectable `run` (subprocess.run) so tests need no X server; the
tracker factory reads no EDMC environment variables; `native_rect_to_qt` is Modern Overlay's
_convert_native_rect_to_qt_standard without its logging, and `title_bar_offset` its _apply_title_bar_offset likewise.
"""
from __future__ import annotations

import ctypes
import logging
import math
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


MonitorSnapshot = Tuple[str, int, int, int, int]
MonitorProvider = Callable[[], List[MonitorSnapshot]]
Geometry = Tuple[int, int, int, int]

_TITLE_PATTERN = re.compile(r"elite\s*-\s*dangerous", re.IGNORECASE)
_DWMWA_EXTENDED_FRAME_BOUNDS = 9
TITLE_HINT = "elite - dangerous"


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
                 monitor_provider: Optional[MonitorProvider] = None, run=None) -> None:
        self._logger = logger
        self._title_hint = title_hint.lower()
        self._last_state: Optional[WindowState] = None
        self._last_refresh: float = 0.0
        self._min_interval: float = 0.3
        self._wmctrl_missing = False
        self._monitor_provider = monitor_provider
        self._run = run or subprocess.run

    @property
    def missing(self) -> bool:
        """wmctrl is not installed (the window cannot follow the game)."""
        return self._wmctrl_missing

    def poll(self) -> Optional[WindowState]:
        if self._wmctrl_missing:
            return None
        now = time.monotonic()
        if self._last_state and now - self._last_refresh < self._min_interval:
            return self._last_state
        try:
            result = self._run(["wmctrl", "-lGx"], check=False, capture_output=True, text=True, timeout=1.0)
        except FileNotFoundError:
            self._wmctrl_missing = True
            self._logger.warning("wmctrl is not installed: the overlay cannot find Elite's window (install wmctrl)")
            self._last_state = None
            return None
        except subprocess.SubprocessError as exc:
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
        for line in result.stdout.splitlines():
            fields = line.split(None, 8)
            if len(fields) < 9:
                continue
            win_id_hex, _desktop, x, y, w, h, _wm_class, _host, title = fields
            if not matches_window_title(title, self._title_hint):
                continue
            try:
                x_val, y_val, width, height = int(x), int(y), int(w), int(h)
                win_id = int(win_id_hex, 16)
            except ValueError:
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
        monitors = _invoke_monitor_provider(self._monitor_provider, self._logger)
        geometry = self._absolute_geometry(target_state.identifier) if monitors else None
        self._last_state = _augment_state_with_monitors(target_state, monitors, self._logger, absolute_geometry=geometry)
        return self._last_state

    def set_monitor_provider(self, provider: Optional[MonitorProvider]) -> None:
        self._monitor_provider = provider

    def active_window_id(self) -> Optional[int]:
        """The window in front (_NET_ACTIVE_WINDOW): the overlay's own window while you arrange its panels."""
        return self._active_window_id()

    def _absolute_geometry(self, win_id_hex: str) -> Optional[Tuple[int, int, int, int]]:
        try:
            result = self._run(["xwininfo", "-id", win_id_hex], check=False, capture_output=True, text=True, timeout=0.5)
        except (FileNotFoundError, subprocess.SubprocessError):
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
        try:
            result = self._run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], check=False, capture_output=True, text=True,
                               timeout=0.5)
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        if result.returncode != 0 or not result.stdout:
            return None
        match = re.search(r"0x[0-9a-fA-F]+", result.stdout)
        if not match:
            return None
        try:
            return int(match.group(0), 16)
        except ValueError:
            return None


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class WindowsTracker:
    """Locate Elite's window using Win32 APIs (not yet tried against the game: Windows is experimental)."""

    def __init__(self, logger: logging.Logger, title_hint: str = TITLE_HINT) -> None:
        if wintypes is None or not hasattr(ctypes, "windll"):
            raise RuntimeError("the Win32 API is unavailable")
        self._logger = logger
        self._title_hint = title_hint.lower()
        self._user32 = ctypes.windll.user32
        try:
            dwmapi = ctypes.windll.dwmapi
            self._dwm_get_window_attribute = dwmapi.DwmGetWindowAttribute
            self._dwm_get_window_attribute.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.POINTER(_RECT), ctypes.c_uint]
            self._dwm_get_window_attribute.restype = ctypes.c_int
        except Exception:
            self._dwm_get_window_attribute = None
        self._last_hwnd: Optional[int] = None
        self._enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(self._enum_windows)

    missing = False

    def poll(self) -> Optional[WindowState]:
        hwnd = self._resolve_window()
        if hwnd is None:
            return None
        rect = self._window_bounds(hwnd)
        if rect is None:
            return None
        width, height = max(0, rect.right - rect.left), max(0, rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return None
        foreground = self._user32.GetForegroundWindow()
        is_visible = bool(self._user32.IsWindowVisible(hwnd)) and not bool(self._user32.IsIconic(hwnd))
        return WindowState(x=int(rect.left), y=int(rect.top), width=int(width), height=int(height),
                           is_foreground=bool(foreground and hwnd == foreground), is_visible=is_visible, identifier=hex(hwnd))

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
        return bool(title) and self._title_hint in title and bool(self._user32.IsWindowVisible(hwnd))


def create_tracker(logger: logging.Logger, title_hint: str = TITLE_HINT,
                   monitor_provider: Optional[MonitorProvider] = None, platform: Optional[str] = None):
    """The tracker for this platform, or None where there is none."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        try:
            return WindowsTracker(logger, title_hint)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Windows tracker unavailable: %s", exc)
            return None
    if platform.startswith("linux"):
        return X11Tracker(logger, title_hint, monitor_provider)
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
