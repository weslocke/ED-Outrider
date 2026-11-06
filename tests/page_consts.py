"""page.js's constants for the Python tests (round 10's S23 (a)): the page loaded in jsdom from disk, as
tests/page_unit.js loads it (tests/page_load.js), and each constant asked for read from its window as JSON. In place of
slicing page.js's text with a regex, which went quietly wrong the day a constant was laid out differently (a second
line, a nested bracket).

    from page_consts import consts
    rows = consts("ALERTS")                          # one name: its value
    words, keys = consts("ROW_WORDS", "ROW_KEYS")    # several: a tuple in that order

A Set comes back as a list, a Map as a dict, a function as its name. A name page.js does not define fails the test
that asked. Node runs once per test process for every name in NAMES (a name asked for that is not there runs it once
more); with no node or no jsdom the test is skipped, saying why (scripts/verify.sh needs both anyway)."""
import json
import os
import shutil
import subprocess
import unittest

from support import ed_outrider

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
# the constants the tests read: fetched together, in one node run
NAMES = ("ALERTS", "ALERT_NAMES", "ALERT_GROUPS", "ROW_WORDS", "ROW_KEYS", "DANGER", "TABLET_VIEWS", "TB.groups",
         "TB_EMBLEMS", "SHIP_NAMES", "SHIP_NO_PICTURE", "MARKERS", "SERVER_LINE_KEYS", "SOUND_LEAD", "AUDITION_KEYS",
         "SETTING_SHAPES", "BM_IMPORT_MAX", "SURVEY", "SETTINGS_KEYS")
_values, _undefined = {}, set()


def _node_modules():
    return os.environ.get("NODE_MODULES") or os.path.join(REPO, "node_modules")


def _fetch(names):
    node, mods = shutil.which("node"), _node_modules()
    if not node:
        raise unittest.SkipTest("page.js's constants need node (Node.js 22 or newer)")
    if not os.path.isdir(os.path.join(mods, "jsdom")):
        raise unittest.SkipTest(f"page.js's constants need jsdom in {mods}: run npm install (or set NODE_MODULES)")
    options = json.dumps(dict(ed_outrider.SEARCH_OPTIONS, mining=[]))   # what scripts/verify.sh gives page_unit.js
    r = subprocess.run([node, os.path.join(TESTS, "page_consts.js"), os.path.abspath(mods), *names], input=options,
                       capture_output=True, text=True, timeout=180, cwd=REPO)
    if r.returncode != 0:
        raise AssertionError(f"tests/page_consts.js failed (exit {r.returncode}): {r.stderr.strip()[-2000:]}")
    out = json.loads(r.stdout)
    if out["errors"]:
        raise AssertionError("page.js did not load in jsdom: " + "; ".join(out["errors"]))
    _values.update(out["values"])
    _undefined.update(out["undefined"])


def consts(*names):
    """The value of each page.js constant named (one name: the value; several: a tuple). Asserts each is defined."""
    new = [n for n in names if n not in _values and n not in _undefined]
    if new:
        _fetch(sorted((set(NAMES) | set(new)) - set(_values) - _undefined))
    missing = [n for n in names if n in _undefined]
    if missing:
        raise AssertionError(f"page.js does not define {', '.join(missing)}")
    got = tuple(_values[n] for n in names)
    return got[0] if len(names) == 1 else got
