#!/usr/bin/env bash
# One-command check for a change to ED Outrider: unit tests, lint, the page's JavaScript syntax, then the page
# smoke test (tests/page_smoke.js, jsdom) against a scratch server built from the synthetic sample journals in
# tests/fixtures/journals.
#
#   scripts/verify.sh
#
# Needs: pip install -r requirements.txt -r requirements-dev.txt, and npm install (jsdom) in the repo root.
# Environment: PYTHON (default .venv/bin/python if present, else python3), NODE_MODULES (default ./node_modules),
# PORT (default: a free one picked at random), VERBOSE=1 (print every smoke line and the server log).
# ED_JOURNALS is ignored: the scratch server always reads the fixture journals (--journals).
#
# Safe by construction: it never reads or writes your own data/ (ed_outrider.sqlite, ...) or ed_outrider.toml, never uses
# port 8025, never plays audio, never presses keys (auto honk off) or opens input devices (co-pilot off), makes
# no backups, and stays offline (Spansh, EDSM, GitHub and voice downloads are pointed at a closed local port).
# Everything it makes goes in a mktemp folder that is deleted at the end; the server is stopped by its PID.
set -u
cd "$(dirname "$0")/.." || exit 1

PY=${PYTHON:-}
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
fi
MODS=${NODE_MODULES:-node_modules}
FAIL=0
step() { printf '\n=== %s\n' "$*"; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/outrider-verify.XXXXXX") || exit 1
PID=""
cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    for _ in $(seq 1 50); do kill -0 "$PID" 2>/dev/null || break; sleep 0.2; done
    kill -9 "$PID" 2>/dev/null
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

step "unit tests ($PY)"
# ResourceWarnings shown (they are raised in finalizers, so -W error would not fail the run): any in the log fails it
if "$PY" -W always::ResourceWarning -m unittest discover tests 2>"$TMP/unit.log"; then tail -3 "$TMP/unit.log"; else tail -40 "$TMP/unit.log"; FAIL=1; fi
if grep -q "ResourceWarning" "$TMP/unit.log"; then
  echo "the tests leak resources (close every database and file a test opens):"; grep -m 10 -A1 "ResourceWarning" "$TMP/unit.log"; FAIL=1
fi

step "pyflakes (any warning fails)"
if "$PY" -m pyflakes --version >/dev/null 2>&1; then
  if "$PY" -m pyflakes ed_outrider.py outrider/*.py voice_lab.py tests/*.py; then echo "no warnings"; else FAIL=1; fi
elif command -v pyflakes >/dev/null 2>&1; then
  if pyflakes ed_outrider.py outrider/*.py voice_lab.py tests/*.py; then echo "no warnings"; else FAIL=1; fi
else
  echo "pyflakes not installed: skipped (pip install -r requirements-dev.txt)"
fi

step "node --check static/page.js"
if ! command -v node >/dev/null 2>&1; then echo "node not found (Node.js 22 or newer is needed)"; FAIL=1
elif node --check static/page.js; then echo "ok"; else FAIL=1; fi

step "page smoke test on a scratch server"
if ! command -v node >/dev/null 2>&1; then
  echo "skipped: no node"
elif [ ! -d "$MODS/jsdom" ]; then
  echo "jsdom not found in $MODS: run npm install (or set NODE_MODULES)"; FAIL=1
else
  PORT=${PORT:-$("$PY" - <<'EOF'
import socket
s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()
EOF
)}
  if [ "$PORT" = 8025 ]; then echo "refusing port 8025 (the default port of a real Outrider)"; exit 1; fi
  mkdir -p "$TMP/journals" "$TMP/backups"
  cp tests/fixtures/journals/* "$TMP/journals/"
  cp resources/speech.json "$TMP/speech.json"   # a 👎 ban writes speech_banned.json beside it: keep that out of the repo
  # a fresh database, built from the sample journals at start (never ed_outrider.sqlite)
  cat > "$TMP/scratch.toml" <<EOF
# scratch config written by scripts/verify.sh
[journals]
live = ["$TMP/journals"]
legacy = []

[server]
host = "127.0.0.1"
port = $PORT
password = "smoke"   # the page still loads from this PC (loopback needs no sign-in)
db = "$TMP/scratch.sqlite"
backup_dir = "$TMP/backups"
backup_every_days = 0
speech_file = "$TMP/speech.json"

[spansh]
watch_firsts = false

[speech]
server_player = "off"

[autohonk]
enabled = false

[copilot]
enabled = false
EOF
  # Offline: every outside service goes to a closed local port, the bio-rules check keeps the shipped copy
  # (it would otherwise rewrite resources/bio_rules.json) and a missing Piper voice is not downloaded.
  # --journals: the fixture copy, whatever ED_JOURNALS says (the flag beats the environment, which beats the config)
  "$PY" - --config "$TMP/scratch.toml" --db "$TMP/scratch.sqlite" --port "$PORT" --host 127.0.0.1 --journals "$TMP/journals" \
      >"$TMP/server.log" 2>&1 <<'EOF' &
import sys
sys.path.insert(0, ".")
import ed_outrider, outrider.tts
OFF = "http://127.0.0.1:9/offline"
for k in ("SPANSH_SEARCH", "SPANSH_BODY_SEARCH", "SPANSH_STATION_SEARCH", "EDSM_SYSTEM", "EDSM_SPHERE", "EDSM_BODIES",
          "SPANSH_ROUTE", "SPANSH_GENERIC_ROUTE", "SPANSH_SYSTEM_NAMES", "SPANSH_SYSTEM_SEARCH", "SPANSH_RICHES",
          "SPANSH_EXO", "SPANSH_COMMODITIES", "SPANSH_TRADE"):
    setattr(ed_outrider, k, OFF)
ed_outrider.SPANSH_DUMP = OFF + "/{id64}"
ed_outrider.SPANSH_RESULTS = OFF + "/{job}"
ed_outrider.RELEASES_LATEST = OFF   # the update check never asks GitHub from here
import outrider.eddn
outrider.eddn.UPLOAD_URL = OFF        # nor EDDN (uploads are off there anyway)
outrider.edsm.UPLOAD_URL = outrider.edsm.DISCARD_URL = OFF   # nor EDSM's journal upload
ed_outrider.DSSA_URL = OFF          # nor EDAstro for the DSSA list
ed_outrider.Clipboard.TOOLS = ()   # the desktop clipboard is never touched by the smoke test
if outrider.bio:
    outrider.bio.update_if_newer = lambda path=None, log=print: None
outrider.tts.Speaker._download = lambda self, name, status=None: False
ed_outrider.main(sys.argv[1:])
EOF
  PID=$!
  up=0
  for _ in $(seq 1 60); do
    if ! kill -0 "$PID" 2>/dev/null; then break; fi
    if "$PY" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/', timeout=2)" 2>/dev/null; then up=1; break; fi
    sleep 1
  done
  if [ "$up" != 1 ]; then
    echo "scratch server did not start:"; tail -30 "$TMP/server.log"; FAIL=1
  else
    sleep 2
    node tests/page_smoke.js "$PORT" "$MODS" >"$TMP/smoke.log" 2>&1
    smoke_rc=$?
    if [ -n "${VERBOSE:-}" ]; then cat "$TMP/smoke.log"; else grep -v '^OK' "$TMP/smoke.log"; fi
    ok=$(grep -c '^OK' "$TMP/smoke.log"); bad=$(grep -c '^FAIL' "$TMP/smoke.log")
    echo "smoke: $ok OK, $bad FAIL"
    if [ "$bad" != 0 ] || [ "$ok" = 0 ] || [ "$smoke_rc" != 0 ]; then FAIL=1; fi
    if [ -n "${VERBOSE:-}" ]; then echo "--- server log"; cat "$TMP/server.log"; fi
    # SIGTERM (docker stop, systemd) stops it as Ctrl-C does: its cleanup runs and it exits 0
    kill -TERM "$PID" 2>/dev/null; wait "$PID"; rc=$?; PID=""
    if [ "$rc" != 0 ] || ! grep -q "stopped cleanly" "$TMP/server.log"; then
      echo "the scratch server did not stop cleanly on SIGTERM (exit $rc):"; tail -15 "$TMP/server.log"; FAIL=1
    fi
    if grep -q "Traceback" "$TMP/server.log"; then
      echo "server log has a traceback:"; grep -n -A12 "Traceback" "$TMP/server.log" | head -40; FAIL=1
    fi
  fi
fi

step "result"
if [ "$FAIL" = 0 ]; then echo "PASS"; else echo "FAILED"; fi
exit "$FAIL"
