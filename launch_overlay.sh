#!/usr/bin/env bash
# Start ED Outrider's in-game overlay window on the game PC (python3 -m outrider.overlay_window): it draws Outrider's
# panels over Elite's window. Uses Outrider's own environment (.venv: run launch_outrider.sh once first) and offers to
# install PyQt6 into it the first time (about 100 MB). Any arguments go to the window
# (./launch_overlay.sh --url http://192.168.1.81:8025 --password ... for an Outrider on a server).
set -euo pipefail
cd "$(dirname "$0")"
VPY=.venv/bin/python

if [ ! -x "$VPY" ]; then
    echo "Outrider's environment (.venv) is not set up yet: run ./launch_outrider.sh once first." >&2
    exit 1
fi
if ! "$VPY" -c "import PyQt6.QtWidgets" 2>/dev/null; then
    echo "The overlay needs PyQt6 (about 100 MB), installed into Outrider's .venv only."
    if [ -t 0 ]; then
        read -r -p "Install it now? [y/N] " yes
    else
        yes=n
    fi
    case "$yes" in
        [yY]*) "$VPY" -m pip install --quiet -r requirements-overlay.txt || { echo "Installing PyQt6 failed." >&2; exit 1; } ;;
        *) echo "Not installed. To install it yourself: $VPY -m pip install -r requirements-overlay.txt" >&2; exit 1 ;;
    esac
fi
# on Linux the window finds Elite's with wmctrl, xprop and xwininfo (Debian/Ubuntu: wmctrl and x11-utils)
if [ "$(uname -s)" = "Linux" ]; then
    for tool in wmctrl xprop xwininfo; do
        command -v "$tool" >/dev/null 2>&1 || echo "warning: $tool is missing: the overlay cannot follow the game's window (sudo apt install wmctrl x11-utils)" >&2
    done
fi
exec "$VPY" -m outrider.overlay_window "$@"
