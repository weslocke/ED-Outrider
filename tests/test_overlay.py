"""Unit tests: the in-game overlay, Outrider's side (outrider/overlay.py and the State's GET/POST /api/overlay). The
window on the game PC is never opened here (its pure parts are tested in test_overlay_window.py).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import contextlib
import io
import math
import os
import tempfile
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.overlay as O  # noqa: E402


class Settings(unittest.TestCase):
    def test_defaults_and_bad_values(self):
        self.assertEqual(O.overlay_settings({})["overlay"], O.DEFAULTS)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = O.overlay_settings({"overlay": {"enabled": "yes", "theme": "Neon", "text_size": "LARGE", "radar_range": 50,
                                                  "system_seconds": True}})["overlay"]
        self.assertEqual((got["enabled"], got["theme"], got["text_size"], got["radar_range"], got["system_seconds"]),
                         (False, "default", "large", 100, 0))
        for word in ("enabled", "theme", "system_seconds"):
            self.assertIn(word, err.getvalue())
        # no url or password: the overlay is a game-PC feature, drawn from this PC's Outrider only (the author, 2026-10-10)
        self.assertNotIn("url", O.overlay_settings({"overlay": {"url": "http://erangel:8025"}})["overlay"])

    def test_written_and_read_back(self):
        """--write-config writes [overlay] with every key, and the file reads back to the same settings."""
        import tomllib
        args = types.SimpleNamespace(**{k: None for k in ("journals", "legacy", "host", "port", "db", "radius")})
        st = ed_outrider.settings_from({"overlay": {"enabled": True, "theme": "lcars", "radar_range": 1200}}, args)
        text = ed_outrider.config_text(st)
        back = tomllib.loads(text)["overlay"]
        self.assertEqual((back["enabled"], back["theme"], back["radar_range"]), (True, "lcars", 1200))
        self.assertEqual(set(back), set(O.DEFAULTS))


class Layout(unittest.TestCase):
    def test_clean_fills_and_clamps(self):
        self.assertEqual(O.clean_layout(None), O.LAYOUT_DEFAULT)
        got = O.clean_layout({"body": {"corner": "sw", "x": 5, "scale": "big", "alpha": 0}, "ghost": {}})
        self.assertEqual((got["body"]["corner"], got["body"]["x"], got["body"]["scale"], got["body"]["alpha"]),
                         ("sw", 0.95, 1.0, 0.1))
        self.assertNotIn("ghost", got)

    def test_update(self):
        new, why = O.layout_update(None, {"radar": {"x": 0.3, "y": 0.2, "scale": 1.5, "bg": 0, "corner": "ne"}})
        self.assertIsNone(why)
        self.assertEqual(new["radar"], {"corner": "ne", "x": 0.3, "y": 0.2, "scale": 1.5, "bg": 0.0, "alpha": 1.0})
        self.assertEqual(new["system"], O.LAYOUT_DEFAULT["system"])
        again, _ = O.layout_update(new, {"radar": {"reset": True}})
        self.assertEqual(again["radar"], O.LAYOUT_DEFAULT["radar"])
        for bad in ({}, [], {"moon": {"x": 1}}, {"body": {"x": "left"}}, {"body": {"corner": "middle"}}, {"body": {"size": 2}},
                    {"body": {}}):
            self.assertIsNone(O.layout_update(None, bad)[0], bad)


class Panels(unittest.TestCase):
    def test_text_panel(self):
        pal = O.palette()
        p = O.text_panel("system", "Title", [[("plain", "text")], {"left": [("left", "muted")], "right": ("9.9M", "accent")},
                                             "rule", None, [("x" * 200, "text")]], pal, width=300)
        self.assertEqual((p["id"], p["w"], p["bg"], p["frame"]), ("system", 300, pal["panel"], pal["frame"]))
        lines = [i for i in p["items"] if i["t"] == "runs"]
        self.assertEqual(lines[0]["runs"], [["Title", pal["title"], "large", True]])
        self.assertEqual(lines[1]["runs"], [["plain", pal["text"], "normal", False]])
        right = next(i for i in p["items"] if i["t"] == "text" and i["s"] == "9.9M")
        self.assertEqual((right["align"], right["x"], right["c"]), ("right", 300 - O.PAD, pal["accent"]))
        long = lines[-1]["runs"][0][0]
        self.assertTrue(long.endswith("…") and O.text_width(long) <= 300 - 2 * O.PAD)   # cut to the panel's width
        sub = O.text_panel("body", "B 1", [], pal, width=300, subtitle="Icy body")["items"][0]["runs"]
        self.assertEqual([r[0] for r in sub], ["B 1", "  Icy body"])
        self.assertGreater(p["h"], 5 * O.LINE_H["normal"])
        self.assertTrue(all(0 <= i.get("y", 0) <= p["h"] for i in p["items"]))

    def test_test_panels(self):
        panels = O.test_panels(O.palette())
        self.assertEqual([p["id"] for p in panels], list(O.PANELS))   # the strip too
        for p in panels:
            self.assertTrue(p["items"] and p["w"] > 0 and p["h"] > 0)
            for i in p["items"]:
                self.assertIn(i["t"], ("text", "runs", "rect", "circle", "line", "marker"))
                for k in ("c", "f"):
                    if i.get(k) is not None:
                        self.assertRegex(i[k], r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


def body(name, dist, **kw):
    b = {"name": name, "type": "Planet", "subtype": "High metal content body", "dist_ls": dist, "value_parts": {}, "organics": [],
         "bio_guess": [], "mapped": False, "value_max": 0}
    b.update(kw)
    return b


DETAIL = {"name": "Test Sector AB-C d1-2", "bodies": [
    {"name": "A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "dist_ls": 0, "value_parts": {"carto_left": 0}},
    body("A 3", 900, notable="WW", terraformable=True, subtype="Water world", value_parts={"carto_left": 2_400_000}),
    body("A 1", 300, value_parts={"carto_left": 90_000}),                                        # small: not listed
    body("B 1", 50, subtype="Icy body", value_parts={"bio_left": 19_000_000}, genera=["Stratum"],
         bio_guess=[{"genus": "Stratum", "codex_new": True, "codex_galaxy_new": True, "variants": ["Stratum Tectonicas - Lime"],
                     "codex_have": []}]),
    body("B 2", 70, subtype="Rocky body", value_parts={"bio_left": 4_000_000}, organics=[
        {"genus": "Bacterium", "samples": 1, "done": False, "lost": False}]),
    body("C 1", 20, mapped=True, value_max=3_000_000, value_parts={"carto_left": 0}),
    body("C 2", 25, value_parts={"carto_left": 600_000}, curiosities=[{"tag": "close ring", "why": "x"}]),
]}


class SystemPanel(unittest.TestCase):
    def test_rows(self):
        rows, left, under = O.system_rows(DETAIL, 500_000, 10_000_000)
        self.assertEqual(under, 1)   # A 1: 90k of mapping, under the 500k level
        got = [(r["name"], r["status"], r["value"]) for r in rows]
        self.assertEqual(got, [("C 2", "TO MAP", 600_000), ("B 1", "TO LAND", 19_000_000), ("B 2", "Bacterium 1/3", 4_000_000),
                               ("A 3", "TO MAP", 2_400_000), ("C 1", "MAPPED", None)])   # to do nearest first, then done
        self.assertEqual(left, 600_000 + 19_000_000 + 4_000_000 + 2_400_000 + 90_000)
        self.assertEqual(rows[1]["mark"], "✪ Lime")
        self.assertEqual(rows[3]["what"], "WW T")

    def test_panel(self):
        pal = O.palette()
        p = O.system_panel(DETAIL, pal, highlight=500_000, bio_min=10_000_000, max_rows=3)
        texts = [" ".join(r[0] for r in i["runs"]) if i["t"] == "runs" else i["s"] for i in p["items"] if i["t"] in ("runs", "text")]
        self.assertTrue(texts[0].startswith("Test Sector AB-C d1-2"))
        self.assertIn("TO LAND 19.0M", texts)
        self.assertTrue(any("Also here:" in t and "C 2 close ring" in t for t in texts))
        self.assertTrue(any(t.startswith("Left here:") and "26.1M" in t and "2 more" in t and "1 under your levels" in t for t in texts))
        self.assertIsNone(O.system_panel({"name": "Empty", "bodies": [body("A 1", 10)]}, pal))   # nothing worth it: no panel

    def test_credits(self):
        self.assertEqual([O.credits(v) for v in (950, 59_400, 2_400_000, 1_230_000_000, None)], ["950", "59k", "2.4M", "1.2B", "0"])


class BodyPanel(unittest.TestCase):
    B = body("B 1", 50, subtype="Icy body", landable=True, gravity=0.42, atmosphere="Thin Neon atmosphere", temperature=27.4,
             first_discovered=True, geo=2, value_parts={"carto_left": 1_200_000, "bio_left": 20_000_000, "bio_factor": 5},
             genera=["Stratum", "Bacterium"],
             bio_guess=[{"genus": "Stratum", "best": "Stratum Tectonicas", "value": 3_800_000, "codex_galaxy_new": True,
                         "variants": ["Stratum Tectonicas - Lime"], "codex_have": []},
                        {"genus": "Bacterium", "best": "Bacterium Acies", "value": 1_000_000}],
             organics=[{"genus": "Bacterium", "species": "Bacterium Acies", "samples": 2, "done": False, "lost": False, "value": 1_000_000}])

    def texts(self, p):
        return [" ".join(" ".join(r[0] for r in i["runs"]).split()) if i["t"] == "runs" else i["s"] for i in p["items"]
                if i["t"] in ("runs", "text")]

    def test_body(self):
        t = self.texts(O.body_panel(self.B, O.palette(), high_gravity=2.0, colony={"stratum": 500, "bacterium": 500}))
        self.assertEqual(t[0], "B 1 Icy")
        self.assertIn("landable · 0.42 g · Thin Neon · 27 K", t)
        self.assertTrue(any("Map:" in x and "1.2M" in x and "first discovered" in x and "2 geo" in x for x in t))
        self.assertTrue(any(x.startswith("Bacterium Acies") and "2/3" in x and "500 m" in x for x in t))     # the run under way
        self.assertTrue(any(x.startswith("Stratum Tectonicas") and "✪ Lime" in x for x in t))
        self.assertIn("≤19.0M", t)                                                                       # x5: nobody's foot here
        self.assertTrue(any(x.startswith("Worth landing: up to") and "20.0M" in x and "×5" in x for x in t))

    def test_heavy_and_undecided(self):
        heavy = dict(self.B, gravity=2.6, organics=[], bio_guess=[], genera=[], bio=2,
                     bio_options={"genera": [{"genus": "Stratum"}, {"genus": "Bacterium"}], "low": 1_000_000, "high": 4_000_000})
        p = O.body_panel(heavy, O.palette(), high_gravity=2.0)
        g = next(r for i in p["items"] if i["t"] == "runs" for r in i["runs"] if r[0].endswith(" g"))
        self.assertEqual((g[0], g[1]), ("2.60 g", O.palette()["warn"]))
        t = self.texts(p)
        self.assertIn("2 signals, not DSS'd: Stratum or Bacterium", t)
        self.assertIn("5.0M to 20.0M", t)
        done = dict(self.B, organics=[dict(self.B["organics"][0], samples=3, done=True)], bio_guess=self.B["bio_guess"][1:],
                    value_parts={"bio_left": 0, "bio_factor": 5})
        t = self.texts(O.body_panel(done, O.palette()))
        self.assertIn("Bacterium Acies ✓", t)                     # finished: shown with its ✓, not left out
        self.assertFalse(any(x.startswith("Worth landing") for x in t))
        self.assertIsNone(O.body_panel({"name": "A", "type": "Star"}, O.palette()))
        self.assertIsNone(O.body_panel(None, O.palette()))


class Radar(unittest.TestCase):
    R = 1_000_000.0

    def at(self, north_m, east_m):
        import math
        return math.degrees(north_m / self.R), math.degrees(east_m / self.R)

    def test_projection(self):
        here = {"lat": 0.0, "lon": 0.0, "heading": 0, "radius": self.R}
        lat, lon = self.at(400, 0)                              # 400 m due north, facing north: straight up, half way out
        x, y, beyond = O.radar_xy(here, lat, lon, 100, 100, 50, 800)
        self.assertAlmostEqual(x, 100, delta=0.1)
        self.assertAlmostEqual(y, 75, delta=0.2)
        self.assertFalse(beyond)
        x, y, _ = O.radar_xy(dict(here, heading=90), lat, lon, 100, 100, 50, 800)   # facing east: north is on the left
        self.assertAlmostEqual((x, y), (75, 100), delta=0.2)
        lat, lon = self.at(0, 5000)                             # 5 km east: on the rim, to the right
        x, y, beyond = O.radar_xy(here, lat, lon, 100, 100, 50, 800)
        self.assertTrue(beyond)
        self.assertAlmostEqual((x, y), (150, 100), delta=0.2)

    def surf(self, clear=False, **kw):
        lat, lon = self.at(300, 0)
        out = {"lat": 0.0, "lon": 0.0, "heading": 0, "radius": self.R, "body": "B 1", "ship": None, "rigs": [], "tags": [],
               "bio": [{"species": "Stratum Tectonicas", "genus": "Stratum", "samples": 1, "current": True, "need": 500,
                        "clear": clear, "points": [{"n": 1, "lat": lat, "lon": lon, "dist": 300}]}]}
        out.update(kw)
        return out

    def test_panel(self):
        pal = O.palette()
        p = O.radar_panel(self.surf(), pal, radar_range=200)
        rings = [i for i in p["items"] if i["t"] == "circle" and i["c"] == pal["bad"]]
        self.assertEqual(len(rings), 1)                         # the colony ring, red: you are inside it
        texts = [i["s"] for i in p["items"] if i["t"] == "text"]
        self.assertIn("Next: 500 m from all · nearest 300 m", texts)
        self.assertIn("edge 700 m", texts)                       # widened from 200 m to fit the 500 m ring
        self.assertEqual([p["items"][0]["runs"][0][0], p["items"][1]["runs"][0][0]], ["Stratum Tectonicas", "sample 2 of 3"])
        ok = O.radar_panel(self.surf(clear=True), pal)
        self.assertTrue(any(i["t"] == "circle" and i["c"] == pal["good"] for i in ok["items"]))
        self.assertIn("Clear: sample here (500 m from all)", [i["s"] for i in ok["items"] if i["t"] == "text"])
        self.assertIsNone(O.radar_panel(self.surf(bio=[]), pal))          # nothing to draw
        self.assertIsNone(O.radar_panel(None, pal))
        shipped = O.radar_panel(self.surf(bio=[], ship={"lat": 0.0, "lon": 0.0, "dist": 1500}), pal)
        self.assertIn("ship 1.5 km", [i["s"] for i in shipped["items"] if i["t"] == "text"])


class Themes(unittest.TestCase):
    def test_colours(self):
        self.assertEqual(O.css_colour("#abc"), "#AABBCC")
        self.assertEqual(O.css_colour("#11223380"), "#80112233")          # CSS's alpha last, the window's first
        self.assertEqual(O.css_colour("rgba(63, 200, 244, .14)"), "#243FC8F4")
        self.assertEqual(O.css_colour("rgb(1,2,3)"), "#010203")
        self.assertIsNone(O.css_colour("transparent"))
        self.assertIsNone(O.css_colour(None))

    def test_vars_resolved(self):
        css = (':root[data-theme="x"] { --a: #FF0000; --b: var(--a); --c: var(--missing, #00FF00); }\n'
               ':root[data-theme="x"] body.tablet { --b: #000; }\n:root[data-theme="y"] { --a: #123456; }')
        self.assertEqual(O.theme_vars(css, "x"), {"a": "#FF0000", "b": "#FF0000", "c": "#00FF00"})

    def test_every_theme(self):
        for t in O.THEMES:
            pal = O.palette(t)
            self.assertEqual(set(pal), set(O.DEFAULT_PALETTE), t)
            for k, v in pal.items():
                if k != "style":
                    self.assertRegex(v, r"^#([0-9A-F]{6}|[0-9A-F]{8})$", f"{t}.{k}")
            self.assertIn(pal["style"], ("rounded", "chamfer", "double", "lcars"))
        self.assertEqual(O.palette("elite")["title"], "#FF7A00")             # elite.css's --tb-title, its orange
        self.assertEqual(O.palette("elite")["style"], "chamfer")
        self.assertNotEqual(O.palette("lcars"), O.palette("default"))
        self.assertEqual(O.test_panels(O.palette("minbari"))[0]["style"], "double")


class FakeProc:
    def __init__(self, cmd, cwd=None):
        self.cmd, self.cwd, self.code, self.pid, self.signals = cmd, cwd, None, 4242, []

    def poll(self):
        return self.code

    def terminate(self):
        self.signals.append("term")
        self.code = 0

    def wait(self, timeout=None):
        return self.code

    def kill(self):
        self.signals.append("kill")


class Runner(unittest.TestCase):
    """Outrider runs the overlay window itself (outrider/overlay_runner.py), here with a fake process and clock: nothing
    is started for real."""

    def setUp(self):
        import outrider.overlay_runner as R
        self.R, self.started, self.t, self.qt, self.pips, self.pip_answer = R, [], 0.0, True, [], (0, "")
        self.run = R.OverlayRunner("http://127.0.0.1:8025", popen=self.popen, has_qt=lambda: self.qt, python="py",
                                   log=lambda *a: None, clock=lambda: self.t, pip=self.pip, background=False)

    def pip(self, cmd, **kw):
        """A fake pip: records the command and answers pip_answer (returncode, stderr)."""
        self.pips.append(cmd)
        return types.SimpleNamespace(returncode=self.pip_answer[0], stdout="", stderr=self.pip_answer[1])

    def popen(self, cmd, cwd=None):
        p = FakeProc(cmd, cwd)
        self.started.append(p)
        return p

    def test_runs_while_wanted(self):
        self.run.tick(False)
        self.assertEqual((self.started, self.run.status()["state"]), ([], "off"))
        self.run.tick(True)
        self.assertEqual(self.started[0].cmd, ["py", "-m", "outrider.overlay_window", "--url", "http://127.0.0.1:8025"])
        self.run.tick(True)
        self.assertEqual((len(self.started), self.run.status()["state"]), (1, "running"))   # one window, kept
        self.run.tick(False)
        self.assertEqual((self.started[0].signals, self.run.status()["state"]), (["term"], "off"))

    def test_without_pyqt_it_installs_it_once(self):
        """The overlay on and PyQt6 missing: Outrider installs it by itself (no button: the author, 2026-10-10), once per
        switching on; a failure waits for the overlay to be switched off and on."""
        self.qt, self.pip_answer = False, (1, "ERROR: No matching distribution found for PyQt6")
        self.run.tick(False)
        self.assertEqual(self.pips, [])                                              # not wanted: nothing installed
        self.run.tick(True)
        self.assertEqual(self.pips[0][:5], ["py", "-m", "pip", "install", "--quiet"])
        self.assertEqual(self.run.status(), {"state": "install_failed", "why": "ERROR: No matching distribution found for PyQt6"})
        self.run.tick(True)
        self.assertEqual(len(self.pips), 1)                                          # not again and again
        self.run.tick(False)
        self.pip_answer = (0, "")
        self.run.tick(True)                                                          # switched off and on: tried again
        self.assertEqual((len(self.pips), self.started), (2, []))
        self.qt = True
        self.run.tick(True)
        self.assertEqual((len(self.started), self.run.status()["state"]), (1, "starting"))   # installed: started
        self.assertEqual(len(self.pips), 2)

    def test_launcher_setup(self):
        """launch_outrider.sh / .bat: PyQt6 installed before Outrider starts when [overlay] enabled is true and it is
        missing; nothing otherwise; never a reason not to start."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = os.path.join(tmp.name, "ed_outrider.toml")
        said = []

        def setup(text, qt=False, wmctrl=True, answer=0, platform="linux"):
            with open(cfg, "w", encoding="utf-8") as f:
                f.write(text)
            self.pips.clear(), said.clear()
            self.pip_answer = (answer, "")
            return self.R.setup(cfg, python="py", has_qt=lambda: qt, run=self.pip, which=lambda name: "/usr/bin/x" if wmctrl else None,
                                platform=platform, out=said.append)
        self.assertTrue(setup("[overlay]\nenabled = false\n"))
        self.assertEqual((self.pips, said), ([], []))
        self.assertTrue(setup(""))                                                  # no [overlay]: off
        self.assertTrue(setup("not = [valid"))                                       # a config that does not parse: off
        self.assertEqual(self.pips, [])
        self.assertTrue(setup("[overlay]\nenabled = true\n"))
        self.assertEqual(self.pips[0], ["py", "-m", "pip", "install", "--quiet", "-r", self.R.REQUIREMENTS])
        self.assertIn("installing PyQt6 in Outrider's venv", said[0])                 # not system-wide
        self.assertTrue(setup("[overlay]\nenabled = true\n", qt=True))
        self.assertEqual((self.pips, said), ([], []))                                # already there
        self.assertFalse(setup("[overlay]\nenabled = true\n", answer=1))
        self.assertIn("starts anyway", said[-1])
        setup("[overlay]\nenabled = true\n", qt=True, wmctrl=False)
        self.assertIn("wmctrl", said[0])                                             # Linux: the system programs
        setup("[overlay]\nenabled = true\n", qt=True, wmctrl=False, platform="win32")
        self.assertEqual(said, [])
        self.assertEqual(self.R.main(["--port", "8026", "--config", os.path.join(tmp.name, "none.toml"), "--setup"]), 0)   # Outrider's own arguments pass

    def test_crashes_back_off_then_give_up(self):
        self.run.tick(True)
        for n in range(1, self.R.CRASHES_MAX + 1):
            self.started[-1].code = 1                                 # it died
            self.run.tick(True)
            if n == self.R.CRASHES_MAX:
                break
            self.assertEqual(self.run.status()["state"], "restarting")
            wait = self.R.BACKOFF_S[min(n - 1, len(self.R.BACKOFF_S) - 1)]
            self.t += wait - 1
            self.run.tick(True)
            self.assertEqual(len(self.started), n)                   # not before the wait
            self.t += 1
            self.run.tick(True)
            self.assertEqual(len(self.started), n + 1)               # then again
        self.assertEqual(self.run.status()["state"], "failed")
        self.t += 10_000
        self.run.tick(True)
        self.assertEqual(len(self.started), self.R.CRASHES_MAX)      # given up
        self.run.tick(False)                                         # switched off and on: tries again
        self.run.tick(True)
        self.assertEqual(len(self.started), self.R.CRASHES_MAX + 1)


def texts(p):
    """A panel's lines as plain text (a right-aligned value as its own entry, after its row)."""
    return ["".join(r[0] for r in i["runs"]) if i["t"] == "runs" else i["s"] for i in p["items"] if i["t"] in ("runs", "text")]


def colour_of(p, word):
    """The colour of the first run or text holding `word`."""
    for i in p["items"]:
        for s, c in ([(r[0], r[1]) for r in i["runs"]] if i["t"] == "runs" else [(i.get("s", ""), i.get("c"))]):
            if word in s:
                return c
    return None


LEAVING = {"honked": True, "unscanned": 0, "body_count": 6, "scanned": 6, "bio_pending": [
    {"body": "B 3", "signals": 1, "genera": None, "partial": {}, "potential": 1_000_000, "factor": 5, "dist_ls": 30},   # under bio_min
    {"body": "B 1", "signals": 2, "genera": ["Stratum"], "partial": {"Bacterium": 1}, "potential": 19_000_000, "factor": 1,
     "dist_ls": 900, "gravity": 2.4, "atmosphere": "Thin Neon atmosphere"},
    {"body": "B 2", "signals": 1, "genera": ["Fonticulua"], "partial": {}, "potential": 2_000_000, "factor": 1, "dist_ls": 40,
     "codex_new": True},                                                                         # new to your codex: worth it
    {"body": "B 4", "signals": 1, "genera": None, "partial": {}, "potential": None, "factor": 1, "dist_ls": None}],   # unpriced
    "unmapped": [
    {"body": "A 2", "subtype": "Icy body", "increment": 1_721, "value_mapped": 2_221, "value_mapped_bonus": 6_252, "dist_ls": 20},
    {"body": "A 3", "subtype": "Water world", "terraformable": True, "increment": 900_000, "value_mapped": 1_100_000,
     "value_mapped_bonus": 3_400_000, "dist_ls": 600},
    {"body": "A 5", "subtype": "High metal content body", "increment": 800_000, "dist_ls": 10, "mapped_before": True}]}


class NowPanel(unittest.TestCase):
    def test_supercruise_times_as_the_page(self):
        self.assertEqual([O.sc_seconds(x) for x in (None, -1, "far")], [None, None, None])
        self.assertEqual(O.sc_seconds(50), 15)                                   # never under 15 s
        self.assertAlmostEqual(O.sc_seconds(2000), 7.5 * math.log(2000) - 20)
        self.assertAlmostEqual(O.sc_seconds(100_000), 360)
        self.assertEqual([O.sc_text(s) for s in (15, 37.0, 12.4, 360)], ["~15 s", "~35 s", "~10 s", "~6 min"])
        self.assertEqual(O.sc_text(17.5), "~20 s")                               # JavaScript's rounding, half up

    def test_plan_as_the_page(self):
        plan = O.plan_items(LEAVING, 500_000, 10_000_000)
        self.assertEqual([(it["kind"], it["body"]) for it in plan],
                         [("bio", "B 2"), ("map", "A 3"), ("bio", "B 1"), ("bio", "B 4")])   # nearest first, no distance last
        self.assertEqual([it["body"] for it in O.plan_items(LEAVING, 500_000, 10_000_000, codex=False)], ["A 3", "B 1", "B 4"])
        self.assertEqual(O.plan_items(None, 500_000, 10_000_000), [])
        b1 = plan[2]
        self.assertAlmostEqual(b1["per_min"], 19_000_000 / (O.sc_seconds(900) / 60))
        head, detail = O.plan_parts(b1, high_gravity=2.0)
        self.assertEqual("".join(t for t, _ in head), "bio on B 1: Bacterium 1/3, Stratum")
        self.assertIn(("2.4 g", "warn"), detail)                                # at your high-gravity level
        head, detail = O.plan_parts(plan[1])
        self.assertEqual("".join(t for t, _ in head), "map A 3 (Water world T)")
        self.assertEqual(detail[0], ("1.1M/3.4M", "accent"))                    # with your bonuses, as Now
        head, _ = O.plan_parts(plan[3])
        self.assertEqual("".join(t for t, _ in head), "bio on B 4 (1 signal not DSS'd)")

    INFO = {"name": "Drojau BJ-A a41-3", "now": 1_000_000, "detail_ready": True, "leaving": LEAVING, "value_now": 4_500_000,
            "target": {"name": "Drojau AB-C d1", "status": "unreported", "known": 0, "count": 12, "star_class": "N"},
            "fuel": {"live": True, "pct": 22, "jumps_max": 4, "since_scoop": 6}, "boost": 4,
            "unsold": {"total": 120_000_000, "carto": {"estimated_payout": 20_000_000}, "bio": {"estimated_value": 100_000_000}},
            "unsold_levels": (50_000_000, 250_000_000), "rebuy": 10_000_000, "since_sale": {"days": 3.6},
            "this_session": {"start": "1970-01-12T12:00:00Z", "jumps": 28, "ly": 6540.7, "firsts": 12, "samples": 1}}

    def test_now(self):
        pal = O.palette()
        p = O.now_panel(self.INFO, pal)
        lines = texts(p)
        self.assertEqual(p["id"], "now")
        self.assertEqual(lines[0], "Drojau BJ-A a41-3")
        self.assertEqual(lines[1], "➜ Drojau AB-C d1  never reported · 0/12 known · N ✕ ⚠")
        self.assertEqual(lines[2], "⛽ 22% · 4 jumps · 6 since scoop · boosted ×4")
        self.assertEqual(colour_of(p, "⛽ 22%"), pal["warn"])
        self.assertEqual(lines[3], "⚠ 🗺 20.0M · 🧬 100.0M aboard · 12.0× rebuy · 3 days unsold")   # 3.6: 3 whole days
        risk = lambda days, **kw: texts(O.now_panel(dict(self.INFO, since_sale={"days": days}, **kw), pal))[3]
        self.assertTrue(risk(16, rebuy=None).endswith("aboard · 2 weeks 2 days since sold"))   # fits: written out
        self.assertTrue(risk(16).endswith("· 12.0× rebuy · 2wk2d since sold"))                 # would wrap: short
        self.assertTrue(risk(0.9).endswith("12.0× rebuy"))                                     # under a day: nothing
        self.assertEqual(lines[4:6], ["4.5M here", "Next: bio on B 2: Fonticulua"])
        self.assertTrue(lines[6].strip().startswith("up to 2.0M ✦ · ~15 s · 8.0M/min · 3 more"))
        self.assertEqual(lines[-2:], ["This session 1 h 46 · 28 jumps · 6,541 ly · 12 new systems", "1 sample"])   # wrapped, not cut
        quiet = O.now_panel(dict(self.INFO, unsold={"total": 1_000_000}, fuel={"live": True, "pct": 80}, target=None,
                                 this_session=None, last_session={"jumps": 3}), pal)
        self.assertNotIn("aboard", " ".join(texts(quiet)))                      # under unsold_warn: nothing at risk
        self.assertEqual(colour_of(quiet, "⛽ 80%"), pal["text"])
        self.assertEqual(texts(quiet)[-1], "Last session · 3 jumps")
        self.assertIsNone(O.now_panel({}, pal))

    def test_long_rows_wrap_not_cut(self):
        """A row too long for the panel goes on the next line, broken between its parts, never cut with … (the Next
        detail and the Bio signals footer were: the author's overlay screenshot, 2026-10-11)."""
        pal = O.palette()
        b = dict(LEAVING["bio_pending"][2], gravity=0.17, atmosphere="Thin Carbon dioxide atmosphere", codex_galaxy=True,
                 factor=5, dist_ls=1326)
        long = dict(LEAVING, unmapped=[], bio_pending=[b, dict(b, body="B 9", dist_ls=2500)])
        lines = texts(O.now_panel(dict(self.INFO, leaving=long), pal))
        self.assertFalse(any(t.endswith("…") for t in lines), lines)
        i = next(n for n, t in enumerate(lines) if t.startswith("Next: "))
        cont = [t for t in lines[i + 1:] if t.startswith("   ")]
        self.assertGreaterEqual(len(cont), 2, lines)                             # continued on indented rows
        self.assertTrue(cont[-1].endswith("1 more") and not cont[-1].startswith("    ·"), lines)
        rows = O.flow([("a" * 30, "text"), (" · ", "muted"), ("b" * 30, "text")], 300)
        self.assertEqual([["".join(t for t, _ in r)] for r in rows], [["a" * 30 + " · "], ["b" * 30]])   # no " · " starts a row

    def test_unsold_age(self):
        self.assertEqual([O.unsold_age(d) for d in (None, 0.99, 1.6, 6.9)],
                         [("", ""), ("", ""), ("1 day unsold", "1 day unsold"), ("6 days unsold", "6 days unsold")])
        self.assertEqual([O.unsold_age(d) for d in (7, 8, 14, 16.5)],
                         [("1 week since sold", "1wk since sold"), ("1 week 1 day since sold", "1wk1d since sold"),
                          ("2 weeks since sold", "2wk since sold"), ("2 weeks 2 days since sold", "2wk2d since sold")])

    def test_arrival_next_states_and_destination(self):
        pal = O.palette()
        arrived = dict(self.INFO, arrival={"ts": "1970-01-12T13:46:30Z", "undiscovered": True})   # 10 s ago
        self.assertIn("🏁 undiscovered", texts(O.now_panel(arrived, pal))[0])
        self.assertEqual(texts(O.now_panel(dict(arrived, now=1_000_000 + 30), pal))[0], "Drojau BJ-A a41-3")   # 40 s: gone
        line = lambda **kw: [t for t in texts(O.now_panel(dict(self.INFO, **kw), pal)) if "Next" in t or "✓" in t or "checking" in t][0]
        self.assertEqual(line(detail_ready=False), "checking…")
        self.assertEqual(line(leaving=None), "Next: honk (FSS discovery scan)")
        self.assertEqual(line(leaving={"honked": True, "unscanned": 3}), "Next: 3 bodies to find in the FSS")
        self.assertEqual(line(leaving={"honked": True, "unscanned": 0}), "✓ nothing worth staying for")
        heading = texts(O.now_panel(dict(self.INFO, destination="A 3", destination_ls=600), pal))
        self.assertIn("➜ A 3 · ~30 s · worth it · 1.9M/min", heading)
        self.assertIn("➜ A 2 · nothing to do here", texts(O.now_panel(dict(self.INFO, destination="A 2"), pal)))
        self.assertIn("Next: ➜ bio on B 2: Fonticulua", texts(O.now_panel(dict(self.INFO, destination="B 2"), pal)))   # it is Next

    def test_on_a_body(self):
        pal = O.palette()
        b = {"name": "B 1", "bio": 3, "geo": 1, "genera": ["Stratum", "Bacterium"],
             "organics": [{"genus": "Bacterium", "samples": 2}, {"genus": "Stratum", "samples": 3, "done": True}]}
        info = dict(self.INFO, on_body={"body": "B 1", "how": "in the SRV", "vehicle": "Scarab"}, body=b,
                    sampling={"genus": "Bacterium", "samples": 2, "need": 500, "nearest": 320, "to_go": 180, "clear": False})
        lines = texts(O.now_panel(info, pal))
        self.assertIn("On B 1 (in the Scarab)", lines)
        i = lines.index("Stratum 3/3 ✓  ·  Bacterium 2/3  ·  1 bio not DSS'd")
        self.assertEqual(lines[i + 1], "🪨 1 geo")                                 # wrapped onto the next row
        self.assertIn("Bacterium 2/3 · 180 m to go (320 of 500 m)", lines)
        self.assertFalse(any(t.startswith("Next") for t in lines))             # the body's card instead of Next
        clear = texts(O.now_panel(dict(info, sampling=dict(info["sampling"], clear=True, to_go=0, nearest=540)), pal))
        self.assertIn("Bacterium 2/3 · ✓ clear to sample (540 of 500 m)", clear)


BIO_DETAIL = {"name": "Drojau BJ-A a41-3", "bodies": [
    {"name": "A", "type": "Star", "bio": 0},
    {"name": "A 1", "type": "Planet", "bio": 1, "gravity": 0.39, "dist_ls": 335, "genera": ["Bacterium"],
     "value_parts": {"bio_left": 0, "bio_factor": 5},
     "organics": [{"genus": "Bacterium", "species": "Bacterium Acies", "variant": "Bacterium Acies - Cyan", "samples": 3, "done": True,
                   "value": 1_000_000}]},
    {"name": "A 4", "type": "Planet", "bio": 1, "gravity": 0.35, "dist_ls": 996, "genera": [],
     "value_parts": {"bio_left": 5_000_000, "bio_factor": 5},
     "bio_guess": [{"genus": "Bacterium", "best": "Bacterium Acies", "value": 1_000_000, "variants": ["Bacterium Acies - Cobalt"],
                    "codex_have": ["Cobalt"]}]},
    {"name": "B 1", "type": "Planet", "bio": 3, "gravity": 2.6, "dist_ls": 1200, "genera": ["Stratum", "Bacterium"],
     "value_parts": {"bio_left": 20_000_000, "bio_factor": 1},
     "organics": [{"genus": "Bacterium", "species": "Bacterium Vesicula", "samples": 1, "value": 1_000_000}],
     "bio_guess": [{"genus": "Stratum", "best": "Stratum Tectonicas", "value": 19_000_000, "codex_new": True,
                    "codex_galaxy_new": True, "variants": ["Stratum Tectonicas - Lime"], "codex_have": []}],
     "bio_options": {"genera": [{"genus": "Osseus"}, {"genus": "Tussock"}, {"genus": "Stratum"}], "low": 1_000_000, "high": 8_000_000}},
    {"name": "C 1", "type": "Planet", "bio": 1, "dist_ls": 50, "genera": ["Fungoida"],
     "value_parts": {"bio_left": 1_500_000, "bio_factor": 1},
     "organics": [{"genus": "Fungoida", "species": "Fungoida Setisis", "samples": 3, "done": True, "lost": True, "value": 1_500_000}]},
    {"name": "C 2", "type": "Planet", "subtype": "Rocky body", "dist_ls": 60}]}   # no bio: not listed


class BioPanel(unittest.TestCase):
    def test_every_signal_worth_it_or_not(self):
        blocks, tot = O.bio_blocks(BIO_DETAIL, bio_min=10_000_000)
        self.assertEqual([(b["name"], b["state"]) for b in blocks],
                         [("C 1", "todo"), ("B 1", "todo"), ("A 4", "under"), ("A 1", "done")])   # worth it, under, done
        self.assertEqual(tot, {"signals": 6, "done": 1, "left": 26_500_000, "under": 1})
        self.assertEqual([b["state"] for b in O.bio_blocks(BIO_DETAIL, bio_min=500_000)[0]], ["todo", "todo", "todo", "done"])

    def test_panel(self):
        pal = O.palette()
        p = O.bio_panel(BIO_DETAIL, pal, bio_min=10_000_000)
        lines = texts(p)
        self.assertEqual(lines[0], "Bio signals  4 bodies · 6 signals")
        self.assertIn("B 1  🧬3 · 2.60 g · 1,200 ls", lines)
        self.assertIn("   Stratum Tectonicas  ✪ Lime", lines)
        self.assertIn("   Bacterium Vesicula  1/3", lines)
        self.assertIn("   ? 1 not DSS'd: Osseus or Tussock", lines)              # the options less the genera known
        self.assertIn("1.0M–8.0M", lines)
        self.assertIn("   ✗ Fungoida Setisis  lost: sample again", lines)
        self.assertIn("   ? Bacterium Acies  Cobalt", lines)
        self.assertIn("≤5.0M", lines)                                            # with the first-footfall ×5
        self.assertIn("   ✓ Bacterium Acies  Cyan", lines)
        self.assertIn("✓ 5.0M", lines)
        self.assertEqual(lines[-1], "Sampled 1/6 · left 26.5M · 1 under your level")
        self.assertEqual(colour_of(p, "B 1"), pal["title"])                      # worth it: highlighted
        self.assertEqual(colour_of(p, "A 4"), pal["muted"])                      # under your level: muted
        self.assertEqual(colour_of(p, "A 1"), pal["good"])                       # finished
        self.assertEqual(colour_of(p, "2.60 g"), pal["warn"])
        self.assertIsNone(O.bio_panel({"bodies": [BIO_DETAIL["bodies"][-1]]}, pal))   # no bio: no panel

    def test_long_list_cut(self):
        pal = O.palette()
        many = {"bodies": [dict(BIO_DETAIL["bodies"][1], name=f"A {i}", dist_ls=i) for i in range(10)] +
                          [dict(BIO_DETAIL["bodies"][3], name=f"B {i}", dist_ls=i) for i in range(10)]}
        lines = texts(O.bio_panel(many, pal, max_rows=20))
        self.assertTrue(lines[-1].endswith("15 more"))                         # 5 bodies of 4 rows; the rest counted
        self.assertFalse(any(t.endswith("…") for t in lines))                   # the footer wraps, never cut
        self.assertFalse(any("Cyan" in t for t in lines))                       # finished bodies keep only their head
        self.assertTrue(O.bio_panel(many, pal, max_rows=20)["h"] < 26 * O.LINE_H["normal"] + 60)

    def test_settings(self):
        cfg = O.overlay_settings({})["overlay"]
        self.assertEqual((cfg["now_panel"], cfg["bio_panel"]), (False, False))   # optional: off by default
        self.assertTrue(O.overlay_settings({"overlay": {"bio_panel": True}})["overlay"]["bio_panel"])
        self.assertEqual(set(O.clean_layout(None)), set(O.PANELS))
        self.assertEqual(O.PANEL_NAMES["now"], "Now (To-Do & Info)")             # its name in Settings and Arrange mode


class Strip(unittest.TestCase):
    def test_strip(self):
        pal = O.palette()
        info = {"name": "Drojau BJ-A a41-3", "region": "Inner Orion Spur", "sol_ly": 5411.4, "star": "L", "found": 20, "total": 20,
                "all_found": True, "honked": True, "value_now": 20_049_458, "value_max": 35_118_786, "first": True,
                "firsts": 20, "mapped": 4, "planets": 18, "in_spansh": True}
        p = O.strip_panel(info, pal)
        lines = ["".join(r[0] for r in i["runs"]) for i in p["items"]]
        self.assertEqual(lines, ["Drojau BJ-A a41-3  ·  Inner Orion Spur  ·  L dwarf",
                                 "Sol 5,411 ly  ·  now 20.0M  ·  max 35.1M  ·  🏁 first discovered  ·  20 bodies  ·  20/20 found ✓  ·  "
                                 "🏁 20  ·  🗺 4/18  ·  Spansh ✓"])
        self.assertTrue(all(i.get("align") == "center" and i["x"] == p["w"] / 2 for i in p["items"]))   # both centred
        self.assertEqual(p["id"], "strip")
        self.assertLessEqual(p["w"], O.CANVAS_W - 40)
        self.assertLess(p["h"], 70)                                   # short: two lines
        new = O.strip_panel(dict(info, total=None, honked=False, first=False, firsts=0, planets=None, in_spansh=False), pal)
        second = "".join(r[0] for r in new["items"][1]["runs"])
        self.assertEqual(second, "Sol 5,411 ly  ·  now 20.0M  ·  max 35.1M  ·  not honked  ·  Spansh ✗ (new to it)")
        self.assertNotIn("first discovered", "".join(r[0] for r in new["items"][0]["runs"]))
        self.assertIsNone(O.strip_panel({}, pal))

    def test_star_words(self):
        self.assertEqual([O.star_words(c) for c in ("K", "M", "N", "DA", "H", "Y", "TTS", "B_BlueWhiteSuperGiant", "")],
                         ["K star ⛽", "M star ⛽", "neutron star ⚡", "white dwarf ⚡", "black hole", "Y dwarf", "T Tauri star",
                          "B supergiant ⛽", ""])

    def test_setting_and_centred_layout(self):
        self.assertFalse(O.overlay_settings({})["overlay"]["strip_panel"])          # optional: off by default
        self.assertTrue(O.overlay_settings({"overlay": {"strip_panel": True}})["overlay"]["strip_panel"])
        self.assertEqual(O.clean_layout(None)["strip"]["corner"], "n")
        self.assertEqual(O.layout_update(None, {"system": {"corner": "s"}})[0]["system"]["corner"], "s")


class Server(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state.config_path = os.path.join(tmp.name, "ed_outrider.toml")   # where the switches are written

    def test_view_and_version(self):
        v = self.state.overlay_view(now=1000)
        self.assertEqual((v["enabled"], v["arrange"], v["test"], v["panels"], v["canvas"]), (False, False, False, [], [1280, 960]))
        self.assertEqual(self.state.overlay_view(since=v["version"], now=1001), {"same": True, "version": v["version"]})
        self.assertTrue(self.state.overlay_info(now=1002)["window"])   # it asked just now
        self.assertFalse(self.state.overlay_info(now=1000 + ed_outrider.OVERLAY_SEEN_S + 1)["window"])

    def test_switches(self):
        out, status = self.state.overlay_set({"enabled": True, "theme": "elite", "panels": {"radar": False}, "test": True}, now=50)
        self.assertEqual(status, 200)
        self.assertEqual((out["enabled"], out["theme"], out["panels"], out["test"]),
                         (True, "elite", {"system": True, "body": True, "radar": False, "strip": False, "now": False, "bio": False},
                          O.TEST_SECONDS))
        with open(self.state.config_path, encoding="utf-8") as f:   # written for the next start
            text = f.read()
        for line in ('enabled = true', 'theme = "elite"', 'radar = false'):
            self.assertIn(line, text)
        v = self.state.overlay_view(now=51)
        self.assertEqual([p["id"] for p in v["panels"]], list(O.PANELS))   # the test panels show
        self.assertEqual(self.state.overlay_view(now=51 + O.TEST_SECONDS)["panels"], [])   # then go
        self.state.overlay_set({"arrange": True}, now=100)
        self.assertTrue(self.state.overlay_view(now=101)["arrange"])
        self.assertFalse(self.state.overlay_view(now=101 + O.ARRANGE_SECONDS)["arrange"])   # ends by itself
        self.state.overlay_set({"arrange": True}, now=200)
        self.state.overlay_set({"arrange": False}, now=201)
        self.assertFalse(self.state.overlay_view(now=202)["arrange"])
        for bad in (None, {}, {"enabled": "yes"}, {"theme": "neon"}, {"panels": {"map": True}}, {"panels": {}}, {"test": 1},
                    {"volume": 3}):
            self.assertEqual(self.state.overlay_set(bad, now=300)[1], 400, bad)

    def test_system_panel_shows_in_supercruise(self):
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True)
        st = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE, "gui_focus": 0}
        self.state.journals.status_json = st
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], ["system"])
        st["gui_focus"] = 9                                                # the FSS: nothing over it
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        st["gui_focus"] = 0
        st["flags"] = ed_outrider.FLAG_SUPERCRUISE | ed_outrider.FLAG_FSD_JUMP   # the hyperspace tunnel: nothing
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        st.update(gui_focus=0, flags=0)                                   # dropped out of supercruise
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        st["flags"] = ed_outrider.FLAG_SUPERCRUISE
        self.state.overlay_cfg.update(system_seconds=60)                  # only for a minute after arriving
        self.assertEqual(len(self.state.overlay_panels(now=1050)), 1)
        self.assertEqual(self.state.overlay_panels(now=1070), [])
        self.state.overlay_cfg.update(system_seconds=0, system_panel=False)
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        self.state.overlay_cfg.update(system_panel=True, enabled=False)
        self.assertEqual(self.state.overlay_panels(now=1010), [])

    def test_body_panel_shows_flying_near_or_heading_to(self):
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True, system_panel=False)
        ship = ed_outrider.FLAG_IN_MAIN_SHIP
        st = {"live": True, "flags": ship, "gui_focus": 0, "body": "Test Sector AB-C d1-2 B 1"}
        self.state.journals.status_json = st
        self.assertEqual([p["items"][0]["runs"][0][0] for p in self.state.overlay_panels(now=1010)], ["B 1"])   # near it
        st.update(destination={"System": 77, "Body": 9, "Name": "Test Sector AB-C d1-2 A 3"})
        self.assertEqual([p["items"][0]["runs"][0][0] for p in self.state.overlay_panels(now=1010)], ["A 3"])   # targeted wins
        st["flags"] = ship | ed_outrider.FLAG_LANDED                                                    # landed: the radar's
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        st.update(flags=ship, destination=None, body=None)                                             # nothing near
        self.assertEqual(self.state.overlay_panels(now=1010), [])

    def test_radar_on_a_body(self):
        self.state.overlay_cfg.update(enabled=True, system_panel=False, body_panel=False)
        self.state.journals.status_json = {"live": True, "flags": ed_outrider.FLAG_IN_SRV, "gui_focus": 0}
        surf = Radar().surf()
        self.state.surface_summary = lambda now=None: dict(surf, down=True, show=True)
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1)], ["radar"])
        self.state.surface_summary = lambda now=None: dict(surf, down=False, show=False)   # high over it: no radar
        self.assertEqual(self.state.overlay_panels(now=1), [])
        self.state.surface_summary = lambda now=None: None
        self.assertEqual(self.state.overlay_panels(now=1), [])

    def test_window_wanted(self):
        import outrider.overlay_runner as R
        self.assertFalse(self.state.overlay_wanted(now=100))
        self.state.overlay_set({"test": True}, now=100)
        self.assertTrue(self.state.overlay_wanted(now=101))                   # test panels: the window runs for them
        self.assertFalse(self.state.overlay_wanted(now=101 + O.TEST_SECONDS))
        self.state.overlay_cfg.update(enabled=True)
        self.assertTrue(self.state.overlay_wanted(now=500))
        self.state.overlay_runner = R.OverlayRunner("http://x", popen=None, has_qt=lambda: True, log=lambda *a: None)
        self.state.overlay_view(window=True, now=500)                         # a window started by hand is drawing
        self.assertFalse(self.state.overlay_wanted(now=501))                  # no second one
        self.assertTrue(self.state.overlay_wanted(now=500 + ed_outrider.OVERLAY_SEEN_S + 1))
        self.assertEqual(self.state.overlay_info(now=600)["runner"], {"state": "off", "why": None})

    def test_strip_shows_anywhere(self):
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [3, 4, 0]})
        self.state.system_detail = lambda id64: dict(DETAIL, region="Inner Orion Spur", value_now=1, value_max=2_000_000,
                                                     leaving={"scanned": 5, "body_count": 9, "honked": True},
                                                     firsts={"system": True, "bodies": 4})
        self.state.systems[77] = {"in_spansh": False, "planets": 6, "body_count": 9}
        self.state.overlay_cfg.update(enabled=True, system_panel=False, body_panel=False, radar=False)
        self.state.journals.status_json = {"live": True, "flags": 0, "flags2": 1, "gui_focus": 0}   # on foot
        self.assertEqual(self.state.overlay_panels(now=1010), [])                                 # off by default
        self.state.overlay_cfg.update(strip_panel=True)
        p = self.state.overlay_panels(now=1010)[0]
        text = ["".join(r[0] for r in i["runs"]) for i in p["items"]]
        self.assertEqual(text[0], "Test Sector AB-C d1-2  ·  Inner Orion Spur")
        self.assertEqual(text[1], "Sol 5 ly  ·  now 1  ·  max 2.0M  ·  🏁 first discovered  ·  9 bodies  ·  5/9 found  ·  🏁 4  ·  "
                                  "🗺 1/6  ·  Spansh ✗ (new to it)")   # C 1 is mapped

    def test_now_and_bio_show_anywhere(self):
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Drojau BJ-A a41-3",
                                    "SystemAddress": 77, "StarPos": [3, 4, 0]})
        self.state.system_detail = lambda id64: dict(BIO_DETAIL, leaving=LEAVING) if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True, system_panel=False, body_panel=False, radar=False)
        st = {"live": True, "flags": 0, "flags2": 1, "gui_focus": 0, "body": "Drojau BJ-A a41-3 B 1"}   # on foot on B 1
        self.state.journals.status_json = st
        self.assertEqual(self.state.overlay_panels(now=1010), [])                               # both off by default
        self.state.overlay_cfg.update(now_panel=True, bio_panel=True)
        now, bio = self.state.overlay_panels(now=1010)
        self.assertEqual((now["id"], bio["id"]), ("now", "bio"))
        self.assertIn("On B 1 (on foot)", texts(now))
        self.assertIn("Stratum 0/3  ·  Bacterium 1/3  ·  1 bio not DSS'd", texts(now))   # the body's card from system_detail
        self.assertEqual(texts(bio)[0], "Bio signals  4 bodies · 6 signals")
        st.update(flags=ed_outrider.FLAG_SUPERCRUISE | ed_outrider.FLAG_IN_MAIN_SHIP, flags2=0, body=None)   # in supercruise
        now = self.state.overlay_panels(now=1010)[0]
        self.assertIn("Next: bio on B 2: Fonticulua", texts(now))                # the config's levels (bio_min 10M)
        st["gui_focus"] = 6                                                       # the galaxy map: nothing
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        st.update(gui_focus=0, flags=ed_outrider.FLAG_DOCKED | ed_outrider.FLAG_IN_MAIN_SHIP)     # docked: no Now
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], ["bio"])
        st.update(flags=0, flags2=1 | (1 << 3))                                   # on foot in the station: no Now
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], ["bio"])
        st.update(flags=ed_outrider.FLAG_SUPERCRUISE | ed_outrider.FLAG_IN_MAIN_SHIP, flags2=0)  # undocked: back
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], ["now", "bio"])

    def test_no_rebuy_multiple_for_a_hull_without_value(self):
        """An Arx-bought ship's Loadout has ModulesValue and no HullValue: its rebuy covers the modules only, so no
        "× rebuy" (the author, 2026-10-10); a ship with a hull value keeps it."""
        arx = {"rebuy": 1_087_554, "modules_value": 21_751_050, "hull_value": None}
        self.assertIsNone(ed_outrider.risk_rebuy(arx))
        self.assertIsNone(ed_outrider.risk_rebuy(dict(arx, hull_value=0)))
        self.assertEqual(ed_outrider.risk_rebuy(dict(arx, hull_value=80_000_000)), 1_087_554)
        self.assertEqual(ed_outrider.risk_rebuy({"rebuy": 5_000_000}), 5_000_000)   # no values known: as before
        self.assertIsNone(ed_outrider.risk_rebuy(None))
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "X",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.journals.ship = arx
        self.assertIsNone(self.state.overlay_now_info(self.state.journals.pos, 1010)["rebuy"])

    def test_layout(self):
        out, status = self.state.overlay_layout_set({"body": {"x": 0.4, "scale": 2.0}})
        self.assertEqual((status, out["layout"]["body"]["x"], out["layout"]["body"]["scale"]), (200, 0.4, 2.0))
        self.assertEqual(self.state.overlay_layout()["body"]["x"], 0.4)   # stored
        self.assertNotIn("overlay_layout", ed_outrider.RESET_JOURNAL_DATA)   # the player's own: a re-read keeps it
        self.assertEqual(self.state.overlay_layout_set({"body": {"x": "far"}})[1], 400)

    def test_endpoints(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.get("/api/overlay")
                first = await r.json()
                seen_by_visitor = self.state.overlay_info()["window"]   # another visitor's GET: not a window
                await c.get("/api/overlay", headers={"User-Agent": "outrider-overlay"})
                seen_by_window = self.state.overlay_info()["window"]
                same = await (await c.get("/api/overlay", params={"since": first["version"]})).json()
                bad = (await c.post("/api/overlay", data="[1]", headers={"Content-Type": "application/json"})).status
                ok = await (await c.post("/api/overlay", json={"test": True})).json()
                lay = await c.post("/api/overlay/layout", json={"system": {"y": 0.5}})
                lay_bad = (await c.post("/api/overlay/layout", json={"system": {"y": "low"}})).status
                cross = (await c.post("/api/overlay", json={"test": True}, headers={"Origin": "http://evil.example"})).status
                self.state.game_pc = False   # a server: the overlay is a game-PC feature
                server = [(await c.post(u, json=b)).status for u, b in (("/api/overlay", {"test": True}),
                                                                        ("/api/overlay/layout", {"system": {"y": 0.5}}))]
                self.assertEqual(server, [409, 409])
                self.state.game_pc = True
                return (first, same, bad, ok, lay.status, (await lay.json())["layout"]["system"]["y"], lay_bad, cross,
                        seen_by_visitor, seen_by_window)
        first, same, bad, ok, lay, y, lay_bad, cross, by_visitor, by_window = asyncio.run(go())
        self.assertEqual((by_visitor, by_window), (False, True))   # only the overlay window counts as drawing
        self.assertEqual((first["panels"], same["same"], bad, ok["test"], lay, y, lay_bad, cross),
                         ([], True, 400, O.TEST_SECONDS, 200, 0.5, 400, 403))
