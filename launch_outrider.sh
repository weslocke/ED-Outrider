#!/usr/bin/env bash
# Start ED Outrider, setting it up first when needed: makes the virtual environment (.venv) and installs
# requirements.txt on the first run, again whenever requirements.txt has changed (after a git pull), and if the
# environment is broken; otherwise it starts at once. With the in-game overlay on ([overlay] enabled = true), it also
# installs PyQt6 when missing. On a Linux desktop without the clipboard program it needs (xclip with an X display,
# X11 or XWayland; wl-copy under Wayland without one) it says how to install it, at every start until it is there. Any arguments go to Outrider
# (./launch_outrider.sh --port 8026).
# PYTHON=/path/to/python3.x picks the Python that makes the environment (3.11 or newer).
set -euo pipefail
# relative paths in the arguments (--config my.toml, --db, --journals .) are the caller's: Outrider is started from
# the folder this was run in, with the repository's files by their full path
CALLER=$PWD
cd "$(dirname "$0")"
HERE=$PWD

# a header at every start and Settings' Restart (which runs this script again), so each run stands out in the
# terminal and in a service's log (the author, 2026-10-14); the version read from outrider/__init__.py in bash alone
# (no sed or head: the launcher runs where only bash and Python can be counted on)
banner() {
    local version="" line bar="======================================================================"
    if [ -r outrider/__init__.py ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            case $line in
                '__version__ = "'*) version=${line#*\"}; version=${version%%\"*}; break ;;
            esac
        done < outrider/__init__.py
    fi
    echo
    echo "$bar"
    echo "#      ED Outrider v${version:-?}"
    echo "#"
    echo "#                       https://github.com/weslocke/ED-Outrider"
    echo "$bar"
}
banner

VENV=.venv
STAMP="$VENV/.requirements.sha256"   # requirements.txt as it was when last installed

# hashed with Python, which this needs anyway: macOS has no sha256sum (only shasum)
# (the same hex sha256sum gave, so an existing stamp still matches); the environment's own Python when it has one
HASHPY="${PYTHON:-python3}"
[ -x "$VENV/bin/python" ] && HASHPY="$VENV/bin/python"
want=$("$HASHPY" -c 'import hashlib; print(hashlib.sha256(open("requirements.txt", "rb").read()).hexdigest())' 2>/dev/null || true)
have=$(cat "$STAMP" 2>/dev/null || true)

needs_install() {
    [ -n "${OUTRIDER_REINSTALL:-}" ] && return 0   # asked for (an optional package that could not be built before)
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
    "$VENV/bin/python" -m pip install --quiet --upgrade pip || true   # offline or refused: the installed pip will do
    # one line at a time when all at once fails: an optional package that will not build (evdev without the headers),
    # or no network after a git pull while the environment still works, no longer stops the start (scripts/
    # install_requirements.py: 0 all, 2 optional ones missing, 3 offline with a working environment, 1 cannot run)
    code=0
    "$VENV/bin/python" scripts/install_requirements.py requirements.txt || code=$?
    case $code in
        0|2) echo "$want" > "$STAMP" ;;
        3) ;;   # the stamp left as it was: the next start tries again
        *) exit 1 ;;
    esac
fi

# certifi (the root certificates every HTTPS request also trusts, outrider/tls.py) upgraded once a week: pip never
# upgrades an installed one that meets requirements.txt's floor (the author, 2026-10-14). The stamp holds the date of
# the last check, compared in Python; written only when pip got through, so an offline start tries again next time.
# Never stops Outrider from starting.
CERTIFI_STAMP="$VENV/.certifi-checked"
if ! "$VENV/bin/python" -c 'import datetime as d, sys; s = open(sys.argv[1]).read().strip(); sys.exit(not 0 <= (d.date.today() - d.date.fromisoformat(s)).days < 7)' "$CERTIFI_STAMP" >/dev/null 2>&1; then
    if "$VENV/bin/python" -m pip install --upgrade --quiet --disable-pip-version-check --retries 1 --timeout 10 certifi >/dev/null 2>&1; then
        "$VENV/bin/python" -c 'import datetime, sys; open(sys.argv[1], "w").write(datetime.date.today().isoformat() + "\n")' "$CERTIFI_STAMP" || true
    else
        echo "certifi: could not check for a newer certificate bundle (offline?); using the installed one"
    fi
fi

# the in-game overlay's PyQt6, installed when [overlay] enabled is true in the config and it is missing (never stops
# Outrider from starting). Run in the caller's folder like Outrider, so a relative --config is the same file.
(cd "$CALLER" && PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" "$HERE/$VENV/bin/python" -m outrider.overlay_runner --setup "$@") || true

# Plot Route's clipboard copy (and auto-target's paste) on Linux needs a system program, not pip's: xclip where there is
# an X display (X11, or XWayland beside Wayland: the game reads the X11 clipboard, and on GNOME wl-copy takes the keyboard
# focus to copy), else wl-copy under Wayland (outrider/highway.py Clipboard: xclip when DISPLAY is set, else wl-copy
# when WAYLAND_DISPLAY is). Said in a block at every start while the desktop session has neither it can use, with the command for this
# system's package manager (the author, 2026-10-11). Nothing on macOS or without a desktop session (a server).
clipboard_hint() {
    [ "$(uname)" = "Darwin" ] && return 0
    local session
    if [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
        session=Wayland
    elif [ -n "${DISPLAY:-}" ] || [ "${XDG_SESSION_TYPE:-}" = "x11" ]; then
        session=X11
    else
        return 0
    fi
    if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v wl-copy >/dev/null 2>&1; then return 0; fi
    if [ -n "${DISPLAY:-}" ] && command -v xclip >/dev/null 2>&1; then return 0; fi
    local tool pkg pm=""
    if [ -n "${DISPLAY:-}" ] || [ "$session" = X11 ]; then tool=xclip; pkg=xclip; else tool=wl-copy; pkg=wl-clipboard; fi
    if command -v apt-get >/dev/null 2>&1; then pm="sudo apt install"
    elif command -v dnf >/dev/null 2>&1; then pm="sudo dnf install"
    elif command -v pacman >/dev/null 2>&1; then pm="sudo pacman -S"
    elif command -v zypper >/dev/null 2>&1; then pm="sudo zypper install"
    fi
    local bar="==============================================================================" on="" off=""
    if [ -t 1 ]; then on=$'\033[1;33m'; off=$'\033[0m'; fi
    echo
    echo "${on}${bar}"
    echo "  OPTIONAL: install $tool for Plot Route's clipboard copy (and auto-target's paste)"
    echo "${bar}${off}"
    echo "  Outrider copies with xclip where there is an X display (X11, or XWayland, which the game runs under) and"
    echo "  with wl-copy (the wl-clipboard package) in a Wayland session without one."
    echo "  Your desktop session is $session, and $tool is not installed."
    if [ -n "$pm" ]; then
        echo "  Install it with:"
        echo
        echo "      $pm $pkg"
        echo
        echo "  Or both, if you switch between Wayland and X11 sessions:"
        echo
        echo "      $pm wl-clipboard xclip"
        echo
    else
        echo "  Install the $pkg package with your distribution's package manager (or both: wl-clipboard and xclip)."
    fi
    echo "  Without it nothing is copied, and auto-target cannot paste the system name (by default it types the name,"
    echo "  which still works); everything else works. This note shows at each start until it is installed."
    echo "${on}${bar}${off}"
    echo
}
clipboard_hint


# shellcheck disable=SC1091
source "$VENV/bin/activate"
# Settings -> Server's Restart starts this script again in Outrider's place (same process, terminal and Ctrl-C; the
# setup above runs again, so requirements changed by a git pull are installed)
export OUTRIDER_LAUNCHER="$HERE/$(basename "$0")"
cd "$CALLER"
exec python "$HERE/ed_outrider.py" "$@"
