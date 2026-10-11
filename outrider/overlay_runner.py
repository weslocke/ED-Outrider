"""Outrider runs the in-game overlay's window itself on the game PC (the author, 2026-10-10: one application, not two):
python3 -m outrider.overlay_window as a child process, started while the overlay is wanted ([overlay] enabled, or the
test panels or Arrange mode), stopped when it is not and when Outrider stops, started again after a crash (after a
growing wait; given up after CRASHES_MAX in a row). PyQt6 is not one of Outrider's requirements: it is installed
when the overlay is on (the author, 2026-10-10: no button for it). The launchers do it before Outrider starts when
[overlay] enabled is true (`python -m outrider.overlay_runner --setup`, `setup()`), and the runner does it once when
the overlay is switched on without it (`install()`, requirements-overlay.txt, into Outrider's own environment); after a
failure it waits until the overlay is switched off and on again.

Never on a server (the overlay is a game-PC feature: an Outrider on a server has none), under --simulate, or with
OUTRIDER_NO_OVERLAY_WINDOW set (verify.sh's scratch server). Tests drive it with a fake `popen`,
`has_qt`, `pip` and clock: nothing here opens a window or installs anything in a test.
"""
import importlib
import importlib.util
import argparse
import os
import shutil
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

    def __init__(self, url, popen=subprocess.Popen, has_qt=has_pyqt6, python=None, root=ROOT, log=print, clock=time.monotonic,
                 pip=subprocess.run, background=True):
        self.url, self.popen, self.has_qt, self.python, self.root = url, popen, has_qt, python or sys.executable, root
        self.log, self.clock, self.pip, self.background = log, clock, pip, background
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
            self.install_error = None   # switched off and on: a failed install is tried again
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
            if not self.installing and self.install_error is None:
                self.install()   # the overlay is on and PyQt6 is missing: installed, once per switching on
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

    def install(self, run=None, background=None):
        """pip install -r requirements-overlay.txt into this Python's environment, on a thread unless background is
        False. False when an install is already under way."""
        run = run or self.pip
        background = self.background if background is None else background
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


def overlay_enabled(path):
    """Whether the config at `path` has [overlay] enabled = true (False when it is missing or does not parse)."""
    import tomllib
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, ValueError):
        return False
    o = cfg.get("overlay")
    return isinstance(o, dict) and o.get("enabled") is True


def setup(config, python=None, has_qt=has_pyqt6, run=subprocess.run, which=shutil.which, platform=sys.platform, out=print):
    """The launchers' step before Outrider starts: PyQt6 installed when [overlay] enabled is true in `config` and it is
    missing; on Linux, a note when wmctrl (how the window finds Elite's) is missing. Never stops Outrider from
    starting: a failure is said and Outrider runs without the overlay. True when PyQt6 is there (or not wanted)."""
    if not overlay_enabled(config):
        return True
    if platform.startswith("linux") and not which("wmctrl"):
        out("The in-game overlay needs wmctrl and xprop to find Elite's window: sudo apt install wmctrl x11-utils "
            "(or your distribution's packages)")
    if has_qt():
        return True
    out("The in-game overlay is on: installing PyQt6 in Outrider's venv (about 100 MB, once; nothing system-wide)")
    try:
        r = run([python or sys.executable, "-m", "pip", "install", "--quiet", "-r", REQUIREMENTS], timeout=900)
        ok = r.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        out(f"Installing PyQt6 failed: {e}")
        return False
    if not ok:
        out("Installing PyQt6 failed (pip's messages above): Outrider starts anyway and tries once more itself")
    return ok


def main(argv=None):
    """python -m outrider.overlay_runner --setup [Outrider's own arguments]: the launchers' PyQt6 step (setup())."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--setup", action="store_true", help="install PyQt6 when [overlay] enabled is true in the config")
    ap.add_argument("--config", default=os.path.join(ROOT, "ed_outrider.toml"))
    args, _ = ap.parse_known_args(argv)   # the rest are Outrider's (--port, ...), passed through by the launchers
    if args.setup:
        setup(args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
