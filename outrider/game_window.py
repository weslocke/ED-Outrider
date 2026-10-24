"""Elite's window for auto-target (S74): brought to the front before a run, and checked to be the window in front before
every key, so no key ever goes into another window.

The window is found with the overlay's tracker (outrider/overlay_tracking.py: wmctrl -lGx and xprop on X11, and on a
Wayland session for the game under XWayland, which is how Proton runs it; Win32 on Windows), by the game's own title,
"Elite - Dangerous (CLIENT)", matched whole: a browser tab or a window about the game must never pass for it.

- Linux: `wmctrl -i -a <id>` activates it (the author's GNOME on Wayland, the game under XWayland, 2026-10-12: it came
  forward from the browser). KDE Plasma on Wayland should do the same (KWin honours XWayland activation), untried.
- Windows: SetForegroundWindow, with the usual workaround of attaching to the thread in front (AttachThreadInput) and
  AllowSetForegroundWindow; never the other common trick, an Alt key tap, which is a key into the window in front.
  Untried against the game: Windows is experimental.
- Cannot work (then nothing is checked, as before this: the page's countdown to click into the game): the game as a
  native Wayland window (Proton's Wayland driver: wmctrl cannot see it, nor can the overlay follow it); compositors
  that ignore X11 activation (Sway, Hyprland: their own IPC, not planned) or a window manager set to refuse focus
  stealing: the activation is then ignored, which the check sees, so the run falls back to the countdown or stops.

Every outside call is injectable (run, which, the tracker, user32/kernel32, the clock): tests never touch a real window.
"""
import logging
import os
import shutil
import subprocess
import sys
import time

from . import overlay_tracking

GAME_TITLE = "elite - dangerous (client)"
NOT_FRONT = "Elite is not the active window: click into the game"
NOT_FOUND = "no game window found"
FRONT_WAIT_S = 1.0     # s: how long an activation may take to show (the tracker asked every FRONT_POLL_S)
FRONT_POLL_S = 0.1
SW_RESTORE, ASFW_ANY = 9, -1

log = logging.getLogger("outrider.game_window")


def is_game_title(title):
    """The game's own window, by its whole title (any case)."""
    return (title or "").strip().lower() == GAME_TITLE


class GameWindow:
    """Find Elite's window, bring it to the front, say whether it is in front. bring_forward() and is_front() block
    (subprocesses, short waits): call them on a worker thread."""

    def __init__(self, platform=None, run=None, which=None, environ=None, tracker=None, user32=None, kernel32=None,
                 clock=None, sleep=None):
        self.platform = platform or sys.platform
        self.run = run or subprocess.run
        self.which = which or shutil.which
        self.environ = os.environ if environ is None else environ
        self._tracker, self.user32, self.kernel32 = tracker, user32, kernel32
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.window = None    # the id (hex string) of the window found last, which is_front() compares against
        self.last = None      # the last bring_forward's outcome: {front, checked, why}
        self._why_not = self._tools()

    def _tools(self):
        """Why this PC cannot bring the game forward, from the platform and the tools alone (asked once), or None."""
        if self.platform.startswith("linux"):
            if not self.environ.get("DISPLAY"):
                return "no X display (DISPLAY is not set)"
            for tool in ("wmctrl", "xprop"):
                if not self.which(tool):
                    return f"{tool} is not installed"
            return None
        if self.platform.startswith("win"):
            return None
        return f"not on this system ({self.platform})"

    @property
    def tracker(self):
        if self._tracker is None and self._why_not is None:
            self._tracker = overlay_tracking.create_tracker(log, overlay_tracking.TITLE_HINT, platform=self.platform,
                                                            run=self.run, match=is_game_title, min_interval=0.0)
            if self._tracker is None:
                self._why_not = "the game's window cannot be found on this system"
        return self._tracker

    def why_not(self):
        """Why it cannot bring the game to the front, or None when it can (as far as is known without a run)."""
        return self._why_not

    def status(self):
        """Settings' line: {front: bool, why}. A run that found no game window says so until one finds it."""
        why = self._why_not or (NOT_FOUND if self.last and not self.last["checked"] else None)
        return {"front": why is None, "why": why}

    def locate(self):
        """Find the game's window afresh: True when found (is_front() then has it), False otherwise."""
        tr = self.tracker
        st = tr.poll() if tr is not None and not getattr(tr, "missing", False) else None
        self.window = st.identifier if st is not None and st.identifier else None
        if self.window is not None and self.last and not self.last.get("checked") and self.last.get("why") == NOT_FOUND:
            self.last = None   # found now: status() stops saying "no game window found" (review S4-B7)
        return self.window is not None

    def is_front(self):
        """Whether the window found by locate() is the one in front now (an unknown answer is a no)."""
        tr = self.tracker
        if self.window is None or tr is None:
            return False
        try:
            active = tr.active_window_id()
            return active is not None and active == int(self.window, 16)
        except (ValueError, OSError):
            return False

    def front_why(self):
        """The check before every key: None when the game's window is in front, else why not."""
        return None if self.is_front() else NOT_FRONT

    def bring_forward(self):
        """Find the game's window and bring it to the front, waiting up to FRONT_WAIT_S for it to show:
        {front, checked, why}. checked False: nothing can be known (no tools, no window found), so the caller does as
        before this (the countdown) and checks nothing; checked True and front False: the activation was ignored."""
        if self._why_not:
            out = {"front": False, "checked": False, "why": self._why_not}
        elif not self.locate():
            out = {"front": False, "checked": False, "why": NOT_FOUND}
        else:
            front = self.is_front()
            if not front:
                try:
                    self._activate()
                except Exception as e:  # noqa: BLE001 -- an activation that fails is one that was ignored
                    log.debug("activating the game's window failed: %s", e)
                end = self.clock() + FRONT_WAIT_S
                while not front and self.clock() < end:
                    self.sleep(FRONT_POLL_S)
                    front = self.is_front()
            out = {"front": front, "checked": True, "why": None if front else NOT_FRONT}
        self.last = out
        return out

    def _activate(self):
        if self.platform.startswith("win"):
            self._activate_windows(int(self.window, 16))
        else:
            self.run(["wmctrl", "-i", "-a", self.window], check=False, capture_output=True, text=True, timeout=1.0)

    def _activate_windows(self, hwnd):
        """SetForegroundWindow from a background process: Windows refuses it unless the caller shares the input of the
        thread in front, so attach to it for the call (untried against the game)."""
        if self.user32 is None or self.kernel32 is None:
            import ctypes
            self.user32, self.kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        u, k = self.user32, self.kernel32
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, SW_RESTORE)
        fg = u.GetForegroundWindow()
        fg_thread = u.GetWindowThreadProcessId(fg, None) if fg else 0
        me = k.GetCurrentThreadId()
        attached = bool(fg_thread and fg_thread != me and u.AttachThreadInput(me, fg_thread, True))
        try:
            u.AllowSetForegroundWindow(ASFW_ANY)
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
        finally:
            if attached:
                u.AttachThreadInput(me, fg_thread, False)
