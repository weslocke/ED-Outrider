"""Outrider runs the in-game overlay's window itself on the game PC (the author, 2026-10-10: one application, not two):
python3 -m outrider.overlay_window as a child process, started while the overlay is wanted ([overlay] enabled, or the
test panels or Arrange mode), stopped when it is not and when Outrider stops, started again after a crash (after a
growing wait; given up after CRASHES_MAX in a row). PyQt6 is not one of Outrider's requirements: without it the
status says so and `install()` puts it into Outrider's own environment (requirements-overlay.txt), from Settings.

Never on a server (Docker: no display; there the window runs on the game PC, launch_overlay.sh --url), under
--simulate, or with OUTRIDER_NO_OVERLAY_WINDOW set (verify.sh's scratch server). Tests drive it with a fake `popen`,
`has_qt` and clock: nothing here opens a window in a test.
"""
import importlib
import importlib.util
import os
import subprocess
import sys
import threading
import time

from . import ROOT

REQUIREMENTS = os.path.join(ROOT, "requirements-overlay.txt")
CRASHES_MAX = 5          # crashes in a row before it stops trying (until the overlay is switched off and on again)
BACKOFF_S = (5, 10, 30, 60, 120)
STOP_WAIT_S = 3          # s for the window to close when asked before it is killed
NO_WINDOW_ENV = "OUTRIDER_NO_OVERLAY_WINDOW"


def has_pyqt6():
    """Whether PyQt6 can be imported in this Python (asked afresh: it may have been installed since)."""
    importlib.invalidate_caches()
    return importlib.util.find_spec("PyQt6") is not None


class OverlayRunner:
    """The overlay window as Outrider's child process. tick(want) every couple of seconds does what is needed;
    `status()` is for Settings: {state, why} with state off, starting, running, restarting, failed, no_qt,
    installing, install_failed."""

    def __init__(self, url, popen=subprocess.Popen, has_qt=has_pyqt6, python=None, root=ROOT, log=print, clock=time.monotonic):
        self.url, self.popen, self.has_qt, self.python, self.root = url, popen, has_qt, python or sys.executable, root
        self.log, self.clock = log, clock
        self.proc, self.crashes, self.next_try = None, 0, 0.0
        self.state, self.why = "off", None
        self.installing, self.install_error = False, None

    def status(self):
        if self.installing:
            return {"state": "installing", "why": None}
        if self.install_error and self.state == "no_qt":
            return {"state": "install_failed", "why": self.install_error}
        return {"state": self.state, "why": self.why}

    def tick(self, want):
        """Start, keep or stop the window as `want` says."""
        if not want:
            self.stop()
            self.state, self.why, self.crashes, self.next_try = "off", None, 0, 0.0
            return
        if self.proc is not None:
            code = self.proc.poll()
            if code is None:
                self.state, self.why = "running", None
                return
            self.proc = None
            self.crashes += 1
            self.log(f"overlay window: it stopped (exit {code})")
            if self.crashes >= CRASHES_MAX:
                self.state, self.why = "failed", f"it stopped {self.crashes} times in a row (exit {code}): see Outrider's log"
                return
            wait = BACKOFF_S[min(self.crashes - 1, len(BACKOFF_S) - 1)]
            self.next_try = self.clock() + wait
            self.state, self.why = "restarting", f"it stopped (exit {code}); starting it again in {wait} s"
            return
        if self.state == "failed":
            return
        if self.installing or not self.has_qt():
            self.state, self.why = "no_qt", None
            return
        if self.clock() < self.next_try:
            return
        try:
            self.proc = self.popen([self.python, "-m", "outrider.overlay_window", "--url", self.url], cwd=self.root)
        except OSError as e:
            self.proc = None
            self.state, self.why = "failed", f"could not start it: {e}"
            return
        self.state, self.why = "starting", None
        self.log(f"overlay window: started (pid {getattr(self.proc, 'pid', '?')})")

    def stop(self):
        """Close the window (asked first, then killed), if it runs."""
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
        self.log("overlay window: stopped")

    def install(self, run=subprocess.run, background=True):
        """pip install -r requirements-overlay.txt into this Python's environment (Settings' Install PyQt6), on a thread
        unless background is False. False when an install is already under way."""
        if self.installing:
            return False
        self.installing, self.install_error = True, None

        def go():
            try:
                r = run([self.python, "-m", "pip", "install", "--quiet", "-r", REQUIREMENTS],
                        capture_output=True, text=True, timeout=900)
                if r.returncode != 0:
                    lines = (r.stderr or r.stdout or "").strip().splitlines()
                    self.install_error = (lines[-1] if lines else f"pip exited {r.returncode}")[:300]
                    self.log(f"overlay window: installing PyQt6 failed: {self.install_error}")
                else:
                    self.log("overlay window: PyQt6 installed")
                    self.state = "off"   # the next tick starts the window
            except (OSError, subprocess.SubprocessError) as e:
                self.install_error = str(e)[:300]
            finally:
                self.installing = False
        if background:
            threading.Thread(target=go, name="overlay-install", daemon=True).start()
        else:
            go()
        return True
