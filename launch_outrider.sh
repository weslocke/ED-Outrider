#!/usr/bin/env bash
# Start ED Outrider, setting it up first when needed: makes the virtual environment (.venv) and installs
# requirements.txt on the first run, again whenever requirements.txt has changed (after a git pull), and if the
# environment is broken; otherwise it starts at once. With the in-game overlay on ([overlay] enabled = true), it also
# installs PyQt6 when missing. Any arguments go to Outrider (./launch_outrider.sh --port 8026).
# PYTHON=/path/to/python3.x picks the Python that makes the environment (3.11 or newer).
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv
STAMP="$VENV/.requirements.sha256"   # requirements.txt as it was when last installed

# hashed with Python, which this needs anyway: macOS has no sha256sum (only shasum)
# (the same hex sha256sum gave, so an existing stamp still matches); the environment's own Python when it has one
HASHPY="${PYTHON:-python3}"
[ -x "$VENV/bin/python" ] && HASHPY="$VENV/bin/python"
want=$("$HASHPY" -c 'import hashlib; print(hashlib.sha256(open("requirements.txt", "rb").read()).hexdigest())' 2>/dev/null || true)
have=$(cat "$STAMP" 2>/dev/null || true)

needs_install() {
    [ ! -x "$VENV/bin/python" ] && return 0
    [ "$want" != "$have" ] && return 0
    "$VENV/bin/python" -c "import aiohttp" 2>/dev/null || return 0   # a broken or emptied environment
    return 1
}

if needs_install; then
    # a half-made environment (venv failed part way: python but no pip, e.g. before python3-venv was installed) is
    # made again rather than failing on every run
    if [ -x "$VENV/bin/python" ] && ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
        echo "$VENV is incomplete (no pip): making it again"
        rm -rf "$VENV"
    elif [ -e "$VENV/pyvenv.cfg" ] && [ ! -x "$VENV/bin/python" ]; then
        # its Python is gone (a dangling link after the system's Python was upgraded): venv would not replace it
        echo "$VENV's Python is gone: making it again"
        rm -rf "$VENV"
    fi
    if [ ! -x "$VENV/bin/python" ]; then
        PY="${PYTHON:-python3}"
        if ! command -v "$PY" >/dev/null 2>&1; then
            echo "Python not found ($PY). Install Python 3.11 or newer, or set PYTHON=/path/to/python3.x" >&2
            exit 1
        fi
        if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
            echo "ED Outrider needs Python 3.11 or newer ($("$PY" --version 2>&1) found). Set PYTHON=/path/to/python3.x" >&2
            exit 1
        fi
        echo "Setting up ED Outrider: creating $VENV (the first time takes a minute or two: about 100 MB with Piper)"
        if ! "$PY" -m venv "$VENV" || ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
            rm -rf "$VENV"   # nothing half-made left behind: the next run starts clean
            echo "Could not create $VENV. On Debian or Ubuntu: sudo apt install python3-venv" >&2
            exit 1
        fi
    fi
    echo "Installing ED Outrider's requirements into $VENV"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    if ! "$VENV/bin/python" -m pip install --quiet -r requirements.txt; then
        echo "Installing the requirements failed. evdev (auto honk, the co-pilot button) is built from source and needs" >&2
        echo "your Python's development headers (Debian/Ubuntu: sudo apt install python3-dev); or remove its line from" >&2
        echo "requirements.txt to do without it. Then run this again." >&2
        exit 1
    fi
    echo "$want" > "$STAMP"
    # not pip's to install (system programs): said once, after an install, when the desktop has neither
    if [ "$(uname)" != "Darwin" ] && ! command -v wl-copy >/dev/null 2>&1 && ! command -v xclip >/dev/null 2>&1; then
        echo "Optional: for the Highway's clipboard copy, install wl-copy (Wayland: the wl-clipboard package) or xclip (X11)"
        echo "with your package manager, e.g. sudo apt install wl-clipboard"
    fi
fi

# the in-game overlay's PyQt6, installed when [overlay] enabled is true in the config and it is missing (never stops
# Outrider from starting)
"$VENV/bin/python" -m outrider.overlay_runner --setup "$@" || true

# shellcheck disable=SC1091
source "$VENV/bin/activate"
exec python ed_outrider.py "$@"
