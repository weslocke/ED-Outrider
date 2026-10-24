"""Install requirements.txt into the running Python (the launchers run it with .venv's), telling apart what has to be
there from what is optional (the full Fable review of 2026-10-23, S7-S3 and S9-S25):

    python scripts/install_requirements.py [requirements.txt]

All of it at once first; when that fails, each line on its own, so one package that will not build (evdev without the
Python headers, piper-tts with no wheel for this Python) or no network no longer stops Outrider from starting. Exit:
0 everything is installed; 2 only optional packages are missing (said, with how to add them); 3 a required package could
not be installed but the environment already has what Outrider needs (offline after a git pull: it starts as it is, and
the launcher tries again next time); 1 Outrider cannot run (aiohttp or certifi missing). Nothing but pip is run.
"""
import os
import re
import subprocess
import sys

OPTIONAL = {"evdev": "auto honk, auto-target, the control rail and the co-pilot button (Linux): it is built from source and "
                     "needs your Python's development headers (Debian/Ubuntu: sudo apt install python3-dev)",
            "piper-tts": "Piper's natural voices: without it the page speaks with the browser's own voice"}
REQUIRED_IMPORTS = ("aiohttp", "certifi")   # what Outrider cannot start without


def lines(path):
    """requirements.txt's requirements, comments and blank lines left out."""
    with open(path, encoding="utf-8") as f:
        return [x for x in (re.sub(r"\s+#.*$", "", raw).strip() for raw in f) if x and not x.startswith("#")]


def name_of(req):
    return re.split(r"[\s;<>=!~\[]", req, maxsplit=1)[0].lower()


def pip(args, run=subprocess.run):
    return run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *args]).returncode == 0


def importable(run=subprocess.run):
    return run([sys.executable, "-c", "import " + ", ".join(REQUIRED_IMPORTS)],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def install(path, run=subprocess.run, out=print):
    """-> the exit code (see the docstring)."""
    if pip(["-r", path], run):
        return 0
    failed = [req for req in lines(path) if not pip([req], run)]
    optional = [r for r in failed if name_of(r) in OPTIONAL]
    required = [r for r in failed if name_of(r) not in OPTIONAL]
    if required:
        if importable(run):
            out("Could not install " + ", ".join(required) + " (offline?): starting with the packages already "
                "installed. Run this again when you are online.")
            return 3
        out("Installing what ED Outrider needs failed (" + ", ".join(required) + "): the messages above say why. "
            "Check your internet connection, then run this again.")
        return 1
    if optional:
        bar = "=" * 78
        out(bar)
        out("  OPTIONAL packages not installed: ED Outrider starts without them")
        out(bar)
        for r in optional:
            out(f"  {name_of(r)}: {OPTIONAL[name_of(r)]}")
        out("  To try again: OUTRIDER_REINSTALL=1 then start ED Outrider (Windows: set OUTRIDER_REINSTALL=1 first).")
        out(bar)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(install(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                          "..", "requirements.txt")))
