"""Unit tests: the in-game overlay, Outrider's side (outrider/overlay.py and the State's GET/POST /api/overlay). The
window on the game PC is never opened here (its pure parts are tested in test_overlay_window.py).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
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

    def test_panel_scale(self):
        """The 4K TV report (2026-10-14): [overlay] panel_scale, all panels' size in % (100 when missing), a whole
        number within PANEL_SCALE_LIMITS (20 to 250), anything but a number the default with a warning."""
        self.assertEqual(O.overlay_settings({})["overlay"]["panel_scale"], 100)
        self.assertEqual(O.PANEL_SCALE_LIMITS, (20, 250))
        for v, want in ((40, 40), (37.6, 37), (5, 20), (900, 250)):
            self.assertEqual(O.overlay_settings({"overlay": {"panel_scale": v}})["overlay"]["panel_scale"], want, v)
        for bad in ("50%", True):
            with contextlib.redirect_stderr(io.StringIO()) as e:
                self.assertEqual(O.overlay_settings({"overlay": {"panel_scale": bad}})["overlay"]["panel_scale"], 100)
            self.assertIn("panel_scale", e.getvalue())

    def test_analysis_only_list(self):
        """D2a: [overlay] analysis_only, the overlay's one list: panel ids kept in PANELS' order, unknown ones dropped
        with a warning, anything but a list of names the default []."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = O.overlay_settings({"overlay": {"analysis_only": ["Bio", "system", "moon", "system"]}})["overlay"]
        self.assertEqual(got["analysis_only"], ["system", "bio"])
        self.assertIn("'moon' not a panel", err.getvalue())
        for bad in ("system", [1], {"system": True}):
            with contextlib.redirect_stderr(io.StringIO()) as e:
                self.assertEqual(O.overlay_settings({"overlay": {"analysis_only": bad}})["overlay"]["analysis_only"], [])
            self.assertIn("analysis_only", e.getvalue())
        a = O.overlay_settings({})["overlay"]
        a["analysis_only"].append("now")                                     # one config's list is never another's
        self.assertEqual(O.overlay_settings({})["overlay"]["analysis_only"], [])

    def test_hide_docked_list(self):
        """[overlay] hide_docked (the author, 2026-10-14): missing, the default (System, Target, Now, Bio: what Outrider
        hid before, Now and the Target panel, and the System and Bio panels); a list kept in PANELS' order; the radar is
        never one (it shows only on a body's surface); anything but a list of names the default, with a warning."""
        self.assertEqual(O.overlay_settings({})["overlay"]["hide_docked"], ["system", "body", "now", "bio"])
        self.assertEqual(O.overlay_settings({"overlay": {"hide_docked": []}})["overlay"]["hide_docked"], [])
        with contextlib.redirect_stderr(io.StringIO()) as e:
            got = O.overlay_settings({"overlay": {"hide_docked": ["Alerts", "strip", "radar", "moon"]}})["overlay"]["hide_docked"]
        self.assertEqual(got, ["strip", "alerts"])
        self.assertIn("'radar', 'moon' not a panel", e.getvalue())
        for bad in ("now", [1]):
            with contextlib.redirect_stderr(io.StringIO()) as e:
                self.assertEqual(O.overlay_settings({"overlay": {"hide_docked": bad}})["overlay"]["hide_docked"],
                                 list(O.HIDE_DOCKED_DEFAULT))
            self.assertIn("hide_docked", e.getvalue())
        a = O.overlay_settings({})["overlay"]
        a["hide_docked"].append("strip")                                       # one config's list is never another's
        self.assertEqual(O.overlay_settings({})["overlay"]["hide_docked"], ["system", "body", "now", "bio"])
        self.assertNotIn("radar", O.DOCKED_PANELS)

    def test_written_and_read_back(self):
        """--write-config writes [overlay] with every key, and the file reads back to the same settings."""
        import tomllib
        args = types.SimpleNamespace(**{k: None for k in ("journals", "legacy", "host", "port", "db", "radius")})
        st = ed_outrider.settings_from({"overlay": {"enabled": True, "theme": "lcars", "radar_range": 1200,
                                                    "analysis_only": ["now", "bio"], "hide_docked": ["strip", "bio"],
                                                    "panel_scale": 45, "hide_on_foot": ["Now", "radar"],
                                                    "hide_mouse_lock": True}}, args)
        text = ed_outrider.config_text(st)
        back = tomllib.loads(text)["overlay"]
        self.assertEqual((back["enabled"], back["theme"], back["radar_range"], back["analysis_only"], back["hide_docked"],
                          back["panel_scale"], back["hide_on_foot"], back["hide_mouse_lock"]),
                         (True, "lcars", 1200, ["now", "bio"], ["strip", "bio"], 45, ["radar", "now"], True))
        # a config written before hide_docked: the default, written out as such
        back = tomllib.loads(ed_outrider.config_text(ed_outrider.settings_from({"overlay": {}}, args)))["overlay"]
        self.assertEqual(back["hide_docked"], ["system", "body", "now", "bio"])
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
        self.assertEqual(new["radar"], {"corner": "ne", "x": 0.3, "y": 0.2, "scale": 1.5, "bg": 0.0, "alpha": 1.0, "text": ""})
        self.assertEqual(new["system"], O.LAYOUT_DEFAULT["system"])
        again, _ = O.layout_update(new, {"radar": {"reset": True}})
        self.assertEqual(again["radar"], O.LAYOUT_DEFAULT["radar"])
        for bad in ({}, [], {"moon": {"x": 1}}, {"body": {"x": "left"}}, {"body": {"corner": "middle"}}, {"body": {"size": 2}},
                    {"body": {}}, {"body": {"text": "huge"}}, {"body": {"text": 1}}):
            self.assertIsNone(O.layout_update(None, bad)[0], bad)

    def test_size_down_to_20_percent(self):
        """The 4K TV report (2026-10-14): a panel's size goes down to 20 % (it was put back to 50 %): what keeps it
        readable is the window's MIN_TEXT_PX floor, not a percentage."""
        self.assertEqual(O.LIMITS["scale"], (0.2, 2.5))
        new, _ = O.layout_update(None, {"system": {"scale": 0.2}, "radar": {"scale": 0.05}})
        self.assertEqual((new["system"]["scale"], new["radar"]["scale"]), (0.2, 0.2))
        self.assertEqual(O.clean_layout(new)["system"]["scale"], 0.2)                # stored and read back as it was
        self.assertEqual(O.clean_layout({"body": {"scale": 0.25}})["body"]["scale"], 0.25)

    def test_text_size_per_panel(self):
        """3b: a panel's own text size in the layout ("text": small, normal, large; "" as all panels, the default); a
        layout saved before it reads unchanged, with every panel as all panels."""
        old = {"system": {"corner": "sw", "x": 0.1, "y": 0.2, "scale": 0.8, "bg": 0.3, "alpha": 0.9}}
        got = O.clean_layout(old)
        self.assertEqual(got["system"], dict(old["system"], text=""))
        self.assertTrue(all(e["text"] == "" for e in got.values()))
        new, why = O.layout_update(old, {"system": {"text": "large"}, "bio": {"text": "small"}})
        self.assertIsNone(why)
        self.assertEqual((new["system"]["text"], new["bio"]["text"], new["system"]["scale"]), ("large", "small", 0.8))
        self.assertEqual(O.layout_update(new, {"system": {"text": ""}})[0]["system"]["text"], "")
        self.assertEqual(O.layout_update(new, {"system": {"text": None}})[0]["system"]["text"], "")
        self.assertEqual(O.clean_layout({"system": {"text": "huge"}})["system"]["text"], "")
        self.assertEqual(O.layout_update(new, {"system": {"reset": True}})[0]["system"]["text"], "")


class TextFloor(unittest.TestCase):
    """The 4K TV report (2026-10-14): the overlay never draws text under MIN_TEXT_PX pixels."""

    def test_effective_scale(self):
        self.assertEqual(O.MIN_TEXT_PX, 9)
        # 1080p, all at 100 %: unchanged for every text size (small text is 13.5 px)
        for size, font in O.FONT_PX.items():
            self.assertAlmostEqual(O.effective_scale(1080, 1.0, 1.0, font), 1.125, msg=size)
        # 1080p at 50 %: small text would be 6.75 px, held at 9; normal (8.4 px) held too; large (10.7 px) not
        self.assertAlmostEqual(O.effective_scale(1080, 1.0, 0.5, O.FONT_PX["small"]), 9 / 12)
        self.assertAlmostEqual(O.effective_scale(1080, 0.5, 1.0, O.FONT_PX["normal"]), 9 / 15)
        self.assertAlmostEqual(O.effective_scale(1080, 1.0, 0.5, O.FONT_PX["large"]), 0.5625)
        # 4K at 50 %: small text 13.5 px, nothing held; at 25 % (all panels) x 100 % small and normal are held, large not
        self.assertAlmostEqual(O.effective_scale(2160, 1.0, 0.5, O.FONT_PX["small"]), 1.125)
        self.assertAlmostEqual(O.effective_scale(2160, 0.25, 1.0, O.FONT_PX["small"]), 0.75)
        self.assertAlmostEqual(O.effective_scale(2160, 0.25, 1.0, O.FONT_PX["normal"]), 0.6)
        self.assertAlmostEqual(O.effective_scale(2160, 0.25, 1.0, O.FONT_PX["large"]), 0.5625)
        for win_h in (720, 1080, 1440, 2160):
            for every in (0.2, 0.5, 1.0):
                for size in (0.2, 0.5, 1.0, 2.5):
                    for font in O.FONT_PX.values():
                        s = O.effective_scale(win_h, every, size, font)
                        self.assertGreaterEqual(s * font, O.MIN_TEXT_PX - 1e-9)
                        self.assertGreaterEqual(s, O.base_scale(win_h) * every * size - 1e-9)   # only ever raised
        self.assertAlmostEqual(O.effective_scale(2160, 0.2, 0.2, None), 0.09)   # no text: no floor

    def test_settings_figure(self):
        self.assertEqual(O.text_px(1080, 1.0, 1.0, O.FONT_PX["normal"]), (17, False))
        self.assertEqual(O.text_px(2160, 0.25, 1.0, O.FONT_PX["large"]), (11, False))
        self.assertEqual(O.text_px(1080, 1.0, 0.3, O.FONT_PX["small"]), (9, True))
        self.assertEqual(O.text_px(720, 1.0, 1.0, O.FONT_PX["small"]), (9, False))     # exactly at it: not held

    def test_smallest_font(self):
        """The window floors each panel by its smallest text; Settings' figure (panel_font, before a panel is built)
        names the same one for every panel and text size: the radar's labels are small whatever the size."""
        for size in O.SIZES:
            for p in O.test_panels(O.palette(), size):
                self.assertEqual(O.smallest_font(p), O.panel_font(p["id"], size), (p["id"], size))
        self.assertIsNone(O.smallest_font({"items": [{"t": "rect"}]}))


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
    {"name": "A", "body_id": 0, "type": "Star", "subtype": "K (Yellow-Orange) Star", "dist_ls": 0, "value_parts": {"carto_left": 0}},
    body("A 3", 900, body_id=9, notable="WW", terraformable=True, subtype="Water world", value_parts={"carto_left": 2_400_000}),
    body("A 1", 300, body_id=7, value_parts={"carto_left": 90_000}),                                        # small: not listed
    body("B 1", 50, body_id=12, subtype="Icy body", value_parts={"bio_left": 19_000_000}, genera=["Stratum"],
         bio_guess=[{"genus": "Stratum", "codex_new": True, "codex_galaxy_new": True, "variants": ["Stratum Tectonicas - Lime"],
                     "codex_have": []}]),
    body("B 2", 70, body_id=13, subtype="Rocky body", value_parts={"bio_left": 4_000_000}, organics=[
        {"genus": "Bacterium", "samples": 1, "done": False, "lost": False}]),
    body("C 1", 20, body_id=20, mapped=True, value_max=3_000_000, value_parts={"carto_left": 0}),
    body("C 2", 25, body_id=21, value_parts={"carto_left": 600_000}, curiosities=[{"tag": "close ring", "why": "x"}]),
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
        self.assertEqual([O.credits(v) for v in (950, 59_400, 2_400_000, 1_230_000_000, None)], ["950", "59k", "2.4M", "1.23B", "0"])
        # as page.js credits(): the unit follows what the figure rounds to (review 2026-10-11)
        self.assertEqual([O.credits(v) for v in (999_999, 999_600, 999_950_000, 1_250_000_000, 999.6, 2_500)],
                         ["1.0M", "1.0M", "1.00B", "1.25B", "1k", "3k"])


# S30: a system you scanned, with its suggested order (the leaving summary): the panel numbers its stops
LEAVING_PLAN = {"id64": "77", "honked": True, "unscanned": 0, "body_count": 7, "scanned": 6, "bio_pending": [
    {"body": "B 2", "signals": 1, "genera": ["Fonticulua"], "partial": {}, "potential": 2_000_000, "factor": 1, "dist_ls": 40,
     "codex_new": True},                                                                         # new to your codex: in the order
    {"body": "A 3", "signals": 1, "genera": ["Stratum"], "partial": {}, "potential": 19_000_000, "factor": 1, "dist_ls": 600},
    {"body": "B 1", "signals": 2, "genera": ["Stratum"], "partial": {"Bacterium": 1}, "potential": 19_000_000, "factor": 1,
     "dist_ls": 900}],
    "unmapped": [
    {"body": "A 2", "subtype": "Icy body", "increment": 1_721, "dist_ls": 20},                     # under the 500k level
    {"body": "A 3", "subtype": "Water world", "terraformable": True, "increment": 900_000, "special": True, "dist_ls": 600}]}
DETAIL_PLAN = {"name": "Test Sector AB-C d1-2", "leaving": LEAVING_PLAN, "bodies": [
    {"name": "A", "body_id": 0, "type": "Star", "subtype": "K (Yellow-Orange) Star", "dist_ls": 0, "value_parts": {}, "scanned": True},
    body("A 2", 20, body_id=4, subtype="Icy body", scanned=True, value_parts={"carto_left": 1_721}),
    body("B 2", 40, body_id=13, subtype="Rocky body", scanned=True, value_parts={"bio_left": 2_000_000}),
    body("A 3", 600, body_id=9, notable="WW", terraformable=True, subtype="Water world", scanned=True,
         value_parts={"carto_left": 2_400_000, "bio_left": 19_000_000}),
    body("B 1", 900, body_id=12, subtype="Icy body", scanned=True, value_parts={"bio_left": 19_000_000}, organics=[
        {"genus": "Bacterium", "samples": 1, "done": False, "lost": False}]),
    body("D 1", 30, body_id=30, value_parts={"carto_left": 2_000_000}),                            # Spansh's only: not yours yet
    body("C 1", 20, body_id=20, mapped=True, scanned=True, value_max=3_000_000, value_parts={"carto_left": 0}),
]}


class NumberedStops(unittest.TestCase):
    """S30 (overlay): the system panel numbers the suggested order's stops as Here's schematic does."""

    def test_glyphs(self):
        self.assertEqual([O.stop_glyph(n) for n in (1, 2, 10, 20, 21, 35)], ["①", "②", "⑩", "⑳", "(21)", "(35)"])

    def test_rows_in_the_order(self):
        rows, left, under = O.system_rows(DETAIL_PLAN, 500_000, 10_000_000)
        got = [(r["name"], r["stops"], r["status"], r["value"]) for r in rows]
        self.assertEqual(got, [("B 2", [1], "TO LAND", 2_000_000),                  # nearest, new to your codex
                               ("A 3", [2, 3], "MAP + LAND", 21_400_000),           # two stops: bio, then the map
                               ("B 1", [4], "Bacterium 1/3", 19_000_000),
                               ("D 1", [], "TO MAP", 2_000_000),                    # not yours: by its value, unnumbered
                               ("C 1", [], "MAPPED", None)])                         # done: unnumbered, below
        self.assertEqual(under, 1)                                                  # A 2's 1.7k of mapping
        # golden parity with plan_items (the page's planItems): the numbers run 1..n in its order
        plan = O.plan_items(LEAVING_PLAN, 500_000, 10_000_000)
        self.assertEqual([(it["kind"], it["body"]) for it in plan], [("bio", "B 2"), ("bio", "A 3"), ("map", "A 3"), ("bio", "B 1")])
        self.assertEqual([n for r in rows for n in r["stops"]], list(range(1, len(plan) + 1)))
        rows, _, under = O.system_rows(DETAIL_PLAN, 500_000, 10_000_000, codex=False)   # codex finds not counted
        self.assertEqual([(r["name"], r["stops"]) for r in rows if r["stops"]], [("A 3", [1, 2]), ("B 1", [3])])
        self.assertEqual(under, 2)                                                  # B 2 is under your levels now

    def test_mapped_by_others_is_not_under_your_levels(self):
        """A planet you scanned that someone else had mapped (leaving.unmapped's mapped_before): never a stop, as on the
        page, and not counted "under your levels" either though its mapping would add 2M (over the 500k level)."""
        leaving = dict(LEAVING_PLAN, unmapped=LEAVING_PLAN["unmapped"] + [
            {"body": "E 1", "subtype": "High metal content body", "increment": 2_000_000, "dist_ls": 50, "mapped_before": True}])
        detail = dict(DETAIL_PLAN, leaving=leaving, bodies=DETAIL_PLAN["bodies"] + [
            body("E 1", 50, body_id=40, scanned=True, value_parts={"carto_left": 2_000_000})])
        rows, left, under = O.system_rows(detail, 500_000, 10_000_000)
        self.assertNotIn("E 1", [r["name"] for r in rows])
        self.assertEqual(under, 1)                                                  # A 2's 1.7k of mapping only
        foot = [t for t in texts(O.system_panel(detail, O.palette())) if "under your levels" in t]
        self.assertEqual(len(foot), 1)
        self.assertIn(" · 1 under your levels", foot[0])

    def test_first_stop(self):
        plan = O.plan_items(LEAVING_PLAN, 500_000, 10_000_000, first="A 3")
        self.assertEqual([(it["body"], it["first"]) for it in plan], [("A 3", True), ("A 3", True), ("B 2", False), ("B 1", False)])
        self.assertEqual([it["body"] for it in O.plan_items(LEAVING_PLAN, 500_000, 10_000_000, first="A 2")],   # not in the list
                         ["B 2", "A 3", "A 3", "B 1"])
        rows, _, _ = O.system_rows(DETAIL_PLAN, 500_000, 10_000_000, first="B 1")
        self.assertEqual([(r["name"], r["stops"]) for r in rows if r["stops"]], [("B 1", [1]), ("B 2", [2]), ("A 3", [3, 4])])
        p = O.system_panel(DETAIL_PLAN, O.palette(), first="B 1")
        lines = texts(p)
        self.assertEqual(lines[1:5], ["Bacterium 1/3 19.0M", "① B 1 Icy", "TO LAND 2.0M", "② B 2 Rocky"])   # (the right column first)
        self.assertEqual(colour_of(p, "①"), O.palette()["accent"])
        info = dict(NowPanel.INFO, leaving=LEAVING_PLAN, plan_first="B 1")
        self.assertIn("Next: bio on B 1: Bacterium 1/3, Stratum", texts(O.now_panel(info, O.palette())))


class BodyPanel(unittest.TestCase):
    B = body("B 1", 50, body_id=12, subtype="Icy body", landable=True, gravity=0.42, atmosphere="Thin Neon atmosphere", temperature=27.4,
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
        self.assertIn("1.0M (×5: 5.0M)", t)                                       # the run under way pays, the x5 apart (S62)
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


class TargetPanel(unittest.TestCase):
    """D1: the Target panel's system (outrider.overlay.target_system_panel)."""
    def test_system(self):
        t = {"name": "Ossia", "status": "unreported", "star_class": "K", "hop": {"ly": 21.04, "fuel": 1.234, "left": 1, "reach": True}}
        p = O.target_system_panel(t, O.palette())
        self.assertEqual(p["id"], "body")                                    # the Body panel's place and size
        self.assertEqual(texts(p), ["➜ Ossia", "never reported", "K star ⛽", "21.0 ly · 1.2 t · leaves 1 max jump"])
        self.assertEqual(colour_of(p, "never reported"), O.palette()["good"])
        t.update(status="no bodies", source="edsm", edsm={"known": 0, "count": None, "missing": True}, star_class="DA",
                 hop={"ly": 60.0, "fuel": 0.05, "left": 0, "reach": False}, remaining=7)
        got = texts(O.target_system_panel(t, O.palette()))
        self.assertEqual(got, ["➜ Ossia", "next jump of your route · 7 to go", "no scan data (known to EDSM only)", "EDSM: not logged",
                               "white dwarf ⚡ · ✕ not scoopable", "⚠ throttle down", "60.0 ly · out of range (needs 0.05 t)"])
        t.update(hop=None, distance=12.345, status="lookup failed", edsm=None, source="spansh", known=4, count=None, star_class=None,
                 remaining=None)
        self.assertEqual(texts(O.target_system_panel(t, O.palette()))[1:], ["lookup failed · 4 known", "12.3 ly"])
        self.assertIsNone(O.target_system_panel({"name": None}, O.palette()))
        self.assertIsNone(O.target_system_panel(None, O.palette()))

    def test_route_check(self):
        """S11's one overlay place (the plan-wide review): the followed route's next stop against the game's target, on
        the Target panel under "next jump of your route": the next stop, a later stop of it, or another system."""
        t = {"name": "Ossia", "status": "unreported", "remaining": 3,
             "route_check": {"ok": True, "name": "Pru Aim", "id": "5", "next": "Pru Aim", "ahead": 0}}
        pal = O.palette()
        p = O.target_system_panel(t, pal)
        self.assertEqual(texts(p)[1:3], ["next jump of your route · 3 to go", "✓ the next stop of your route"])
        self.assertEqual(colour_of(p, "✓ the next stop"), pal["good"])
        t["route_check"] = {"ok": False, "name": "Ossia", "id": "9", "next": "Pru Aim", "ahead": 2}
        self.assertEqual(texts(O.target_system_panel(t, pal))[2], "↷ 2 stops ahead on your route")
        t["route_check"] = {"ok": False, "name": "Ossia", "id": "9", "next": "Pru Aim", "ahead": 0}
        p = O.target_system_panel(t, pal)
        self.assertEqual(texts(p)[2], "⚠ not the next stop: Pru Aim")
        self.assertEqual(colour_of(p, "⚠ not the next stop"), pal["bad"])
        t["route_check"] = None
        self.assertEqual(texts(O.target_system_panel(t, pal))[1:], ["next jump of your route · 3 to go", "never reported"])

    def test_hazard_as_the_page(self):
        """page.js hazardNote: a neutron star, a white dwarf, a black hole (the overlay's Now left out the black hole)."""
        self.assertEqual([O.star_hazard(c) for c in ("N", "DAV", "H", "SupermassiveBlackHole", "K", "", None)],
                         ["neutron star", "white dwarf", "black hole", "black hole", "", "", ""])
        now = O.now_panel({"name": "X", "target": {"name": "Ossia", "status": "visited", "star_class": "H"}}, O.palette())
        self.assertTrue(any(t.startswith("➜ Ossia") and t.endswith("H ✕ ⚠") for t in texts(now)))

    def test_test_panel_is_the_target(self):
        body = next(p for p in O.test_panels(O.palette()) if p["id"] == "body")
        self.assertEqual(texts(body)[:2], ["➜ Test Sector AB-C d1-3  test panel", "next jump of your route · 4 to go"])


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
    def __init__(self, cmd, cwd=None, output=None, **kw):
        self.cmd, self.cwd, self.code, self.pid, self.signals, self.kw = cmd, cwd, None, 4242, [], kw
        self.stdout = io.BytesIO(output) if output is not None else None   # the window's piped output (S5b)

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

    def popen(self, cmd, cwd=None, **kw):
        p = FakeProc(cmd, cwd, **kw)
        self.started.append(p)
        return p

    def test_the_windows_output_reaches_outriders_log(self):
        """S5b: the window's output is piped (stdout and stderr together, unbuffered, UTF-8) and passed on as Outrider's
        own lines, so Show log and outrider.log have it; its last words are read before "it stopped" is said."""
        import subprocess
        said = []
        self.run.log = said.append
        self.run.popen = lambda cmd, cwd=None, **kw: self.popen(cmd, cwd, output="drawing\noverlay: connected to x\nTraceback: boom ✗\n".encode(), **kw)
        self.run.tick(True)
        p = self.started[0]
        self.assertEqual((p.kw["stdout"], p.kw["stderr"]), (subprocess.PIPE, subprocess.STDOUT))
        self.assertEqual((p.kw["env"]["PYTHONUNBUFFERED"], p.kw["env"]["PYTHONIOENCODING"]), ("1", "utf-8"))
        p.code = 1
        self.run.tick(True)
        # its own "overlay: " (for when it runs by itself) is not said twice (2026-10-16)
        self.assertEqual(said, ["overlay window: started (pid 4242)", "overlay window: drawing",
                                "overlay window: connected to x", "overlay window: Traceback: boom ✗", "overlay window: it stopped (exit 1)"])
        self.assertTrue(p.stdout.closed)
        self.assertIsNone(self.run.drain)

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

    def test_pip_ok_without_pyqt_is_not_repeated(self):
        """pip answers 0 but this Python still cannot import PyQt6 (a --user or target install elsewhere): said once,
        not a new pip run on every tick (review 2026-10-11)."""
        self.qt, self.pip_answer = False, (0, "")
        for _ in range(4):
            self.run.tick(True)
        self.assertEqual(len(self.pips), 1)
        st = self.run.status()
        self.assertEqual(st["state"], "install_failed")
        self.assertIn("still cannot be imported", st["why"])

    def test_a_stop_after_a_healthy_run_starts_a_new_count(self):
        """'Five times in a row' (the guide): a window that drew for a while and then stopped is not a start-up crash,
        so stops spread over days of play never add up to giving up (review 2026-10-11)."""
        self.run.tick(True)
        for n in range(self.R.CRASHES_MAX + 2):
            self.t += self.R.HEALTHY_S + 1                            # it ran a good while
            self.started[-1].code = 1
            self.run.tick(True)
            self.assertEqual(self.run.status()["state"], "restarting", n)
            self.t += self.R.BACKOFF_S[0]                             # always the first, shortest wait
            self.run.tick(True)
        self.assertEqual(len(self.started), self.R.CRASHES_MAX + 3)

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

    def test_now_route_and_boxel(self):
        """Now's panel says where the next jump goes: the route's next stop as the page's strip words it, the kept
        boxel's Next (review suggestion, 2026-10-12)."""
        pal = O.palette()
        join = lambda parts: "".join(t for t, _ in parts)
        hw = {"index": 38, "at": 37, "total": 120, "destination": "Colonia", "refuel_in": 3,
              "next": {"name": "Stop 38", "jumps": 1, "distance": 4.23, "neutron": True}}
        self.assertEqual(join(O.route_parts({"kind": "highway", "summary": hw})),
                         "🛣 Next: Stop 38 · ⚡ neutron · 4.2 ly · 38 of 120 · refuel in 3 jumps")
        self.assertEqual(join(O.route_parts({"kind": "highway", "summary": dict(hw, index=0, at=None, refuel_in=None, refuel_here=True)})),
                         "🛣 Start: Stop 38 · ⚡ neutron · 4.2 ly · 0 of 120 · ⛽ refuel here")
        self.assertEqual(join(O.route_parts({"kind": "highway", "summary": dict(hw, off_route=True, nearest={"name": "Stop 12", "distance": 8.04})})),
                         "🛣 Off Route: Detour · nearest Stop 12 8.0 ly")
        self.assertEqual(join(O.route_parts({"kind": "highway", "summary": dict(hw, complete=True)})), "🛣 Highway complete")
        # S1: short of the refuel stop, in red; at a refuel stop, how much to scoop; a later hop's too-heavy jump named
        short = {"need_t": 24.3, "max_t": 36.0, "have_t": 10.0, "refuel_at": "Stop 42", "jumps": 4, "end": "refuel", "here_refuel": False}
        p = O.route_parts({"kind": "highway", "summary": dict(hw, short=short)})
        self.assertEqual(p[-1], (" · ⚠ fuel won't reach the refuel stop: Stop 42 in 4 jumps · scoop to ≥ 24.3 t, at most 36.0 t", "bad"))
        p = O.route_parts({"kind": "highway", "summary": dict(hw, short=dict(short, here_refuel=True, max_t=None, jumps=1, end="end"))})
        self.assertEqual(p[-1], (" · ⛽ scoop to ≥ 24.3 t to reach Stop 42 in 1 jump", "warn"))
        p = O.route_parts({"kind": "highway", "summary": dict(hw, short=dict(short, need_t=None, max_t=None))})
        self.assertTrue(join(p).endswith("Stop 42 in 4 jumps · no amount of fuel makes it"))
        p = O.route_parts({"kind": "highway", "summary": dict(hw, heavy={"need_t": 36.07, "have_t": 160, "next": "Far C", "hop": 3})})
        self.assertEqual(p[-1], (" · ⚠ too much fuel for the jump to Far C: ≤ 36 t, you have 160 t", "bad"))
        rc ={"kind": "exo", "index": 2, "at": 1, "total": 9, "left_here": 2, "next": {"name": "Pru Aim", "jumps": 3, "distance": None}}
        self.assertEqual(join(O.route_parts({"kind": "riches", "summary": rc})), "🧬 Next: Pru Aim · 3 jumps · 2 of 9 · 2 species to sample here")
        # S12: finished systems the next stop passes over (a survey route only); S11's mark is the Target panel's alone
        self.assertEqual(join(O.route_parts({"kind": "riches", "summary": dict(rc, skipped=2, target_check={"ok": True, "next": "Pru Aim"})})),
                         "🧬 Next: Pru Aim · 3 jumps · 2 of 9 · skipping 2 done · 2 species to sample here")
        self.assertEqual(O.route_parts(None), [])
        bx = {"label": "Smojooe KL-P d5", "name": "Smojooe KL-P d5-41", "n": 41, "spansh": False}
        self.assertEqual(join(O.boxel_parts(bx)), "▦ Boxel: next Smojooe KL-P d5-41 · to try")
        self.assertEqual(join(O.boxel_parts(dict(bx, spansh=True, known={"bodies": 3, "count": 14}))), "▦ Boxel: next Smojooe KL-P d5-41 · known · 3 of 14 bodies")
        self.assertEqual(join(O.boxel_parts(dict(bx, complete=True))), "▦ Smojooe KL-P d5 ✓ complete")
        self.assertEqual([O.boxel_known_words(dict(spansh=True, scanned=True, known={"bodies": 9, "count": 9})),
                          O.boxel_known_words(dict(known={"bodies": 0, "count": 9})), O.boxel_known_words(dict(known={"bodies": 1}))],
                         ["known · all 9 bodies", "known · honked only", "known · 1 body, count unknown"])
        lines = texts(O.now_panel(dict(self.INFO, route={"kind": "highway", "summary": hw}, boxel=bx), pal))
        self.assertEqual(lines[2:5], ["🛣 Next: Stop 38 · ⚡ neutron · 4.2 ly · 38 of 120", "   refuel in 3 jumps",   # wrapped, not cut
                                      "▦ Boxel: next Smojooe KL-P d5-41 · to try"])   # under the target, before fuel
        self.assertTrue(lines[5].startswith("⛽ 22%"))

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
        # S62: what the run pays from sample 1, the x5 first footfall apart
        pays = texts(O.now_panel(dict(info, sampling=dict(info["sampling"], samples=1, value=1_000_000, factor=5)), pal))
        self.assertIn("Bacterium 1/3 · 1.0M (×5: 5.0M) · 180 m to go (320 of 500 m)", pays)
        self.assertEqual((O.run_pays(1_000_000, 5), O.run_pays(1_000_000, 1), O.run_pays(None, 5)), ("1.0M (×5: 5.0M)", "1.0M", ""))


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

    def test_security_and_reputation(self):
        """A populated system: its security and your reputation with its controlling faction on the top row's right, in
        the region's font; Hostile in red; none in an unpopulated system (the author, 2026-10-14)."""
        pal = O.palette()
        info = {"name": "Shinrarta Dezhra", "region": "Inner Orion Spur", "star": "K", "sol_ly": 47.0}
        plain = O.strip_panel(info, pal)
        p = O.strip_panel(dict(info, standing={"security": "High Security", "faction": "Pilots' Federation", "rep": 95}), pal)
        right = [i for i in p["items"] if i.get("align") == "right"]
        self.assertEqual(len(right), 1)
        self.assertEqual(["".join(r[0] for r in i["runs"]) for i in right], ["High Security  ·  Allied"])
        region = next(r for r in p["items"][0]["runs"] if r[0] == "Inner Orion Spur")
        self.assertTrue(all(r[1:] == region[1:] for r in right[0]["runs"]))   # the region's colour, size, weight
        self.assertEqual(right[0]["x"], p["w"] - O.PAD - 4)
        self.assertGreater(p["w"], plain["w"])                                 # room for it, the row still centred
        self.assertEqual([i for i in plain["items"] if i.get("align") == "right"], [])
        hostile = O.strip_panel(dict(info, standing={"security": "Anarchy", "faction": "X", "rep": -95}), pal)
        word = next(r for i in hostile["items"] if i.get("align") == "right" for r in i["runs"] if r[0] == "Hostile")
        self.assertEqual(word[1], pal["bad"])
        self.assertEqual([O.rep_level(x) for x in (-100, -90, -89.9, -35, 0, 4, 4.1, 35, 89.9, 90, 90.1, None)],
                         ["Hostile", "Hostile", "Unfriendly", "Unfriendly", "Neutral", "Neutral", "Cordial", "Cordial",
                          "Friendly", "Friendly", "Allied", None])

    def test_standing_from_the_journal(self):
        """system_standing: an FSDJump's security and the controlling faction's MyReputation; None in the black."""
        ev = {"SystemSecurity": "$SYSTEM_SECURITY_high;", "SystemSecurity_Localised": "High Security", "Population": 22780919531,
              "SystemFaction": {"Name": "Pilots' Federation Local Branch"},
              "Factions": [{"Name": "Other", "MyReputation": -50.0}, {"Name": "Pilots' Federation Local Branch", "MyReputation": 100.0}]}
        self.assertEqual(ed_outrider.system_standing(ev),
                         {"security": "High Security", "faction": "Pilots' Federation Local Branch", "rep": 100.0})
        self.assertEqual(ed_outrider.system_standing(dict(ev, SystemSecurity_Localised=None))["security"], "High Security")
        self.assertIsNone(ed_outrider.system_standing({"SystemSecurity": "$GAlAXY_MAP_INFO_state_anarchy;", "Population": 0}))
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle(dict(ev, event="FSDJump", timestamp="2026-10-14T20:00:00Z", StarSystem="Shinrarta Dezhra",
                      SystemAddress=3932277478106, StarPos=[55.7, 17.6, 27.2], StarClass="K"))
        self.assertEqual(j.pos["standing"]["rep"], 100.0)
        j.handle({"event": "FSDJump", "timestamp": "2026-10-14T20:10:00Z", "StarSystem": "Empty", "SystemAddress": 77,
                  "StarPos": [60.0, 17.6, 27.2], "StarClass": "M", "Population": 0})
        self.assertNotIn("standing", j.pos)

    def test_star_words(self):
        self.assertEqual([O.star_words(c) for c in ("K", "M", "N", "DA", "H", "Y", "TTS", "B_BlueWhiteSuperGiant", "")],
                         ["K star ⛽", "M star ⛽", "neutron star ⚡", "white dwarf ⚡", "black hole", "Y dwarf", "T Tauri star",
                          "B supergiant ⛽", ""])

    def test_setting_and_centred_layout(self):
        self.assertFalse(O.overlay_settings({})["overlay"]["strip_panel"])          # optional: off by default
        self.assertTrue(O.overlay_settings({"overlay": {"strip_panel": True}})["overlay"]["strip_panel"])
        self.assertEqual(O.clean_layout(None)["strip"]["corner"], "n")
        self.assertEqual(O.layout_update(None, {"system": {"corner": "s"}})[0]["system"]["corner"], "s")


def alert(title, t, body="", danger=False, kind="find"):
    return {"kind": kind, "title": title, "body": body, "danger": danger, "t": t}


class AlertsPanel(unittest.TestCase):
    """S26: the page's alerts on the overlay for a few seconds (the author: 8 s, 15 s for danger, placed in Arrange
    mode like the other panels)."""

    def test_entry_checked(self):
        e, why = O.alert_entry({"kind": "rare_star", "title": " ⭐ A  black hole ", "body": "the main star", "danger": False}, 50)
        self.assertIsNone(why)
        self.assertEqual(e, {"kind": "rare_star", "title": "⭐ A black hole", "body": "the main star", "danger": False, "t": 50})
        self.assertEqual(O.alert_entry({"kind": "fuel", "title": "Fuel low"}, 1)[0]["body"], "")   # body and danger optional
        for bad in (None, [], {"title": "x"}, {"kind": "Find!", "title": "x"}, {"kind": "find", "title": ""},
                    {"kind": "find", "title": "x" * (O.ALERT_TITLE_MAX + 1)}, {"kind": "find", "title": "x", "body": 3},
                    {"kind": "find", "title": "x", "body": "y" * (O.ALERT_BODY_MAX + 1)},
                    {"kind": "find", "title": "x", "danger": "yes"}, {"kind": "find", "title": "x", "sound": "chime"}):
            self.assertIsNone(O.alert_entry(bad, 1)[0], bad)

    def test_kept_and_deduped(self):
        """Every page window posts each alert (the tablet too): the same title and text within ALERT_SAME_S counts once;
        the newest ALERT_KEEP are kept."""
        kept = []
        self.assertTrue(O.alert_add(kept, alert("Fuel low", 100)))
        self.assertFalse(O.alert_add(kept, alert("Fuel low", 100 + O.ALERT_SAME_S - 1)))   # another window's copy
        self.assertTrue(O.alert_add(kept, alert("Fuel low", 100, body="2 jumps left")))     # other text: another alert
        self.assertTrue(O.alert_add(kept, alert("Fuel low", 100 + O.ALERT_SAME_S)))         # later: again
        for i in range(10):
            O.alert_add(kept, alert(f"Find {i}", 200 + i))
        self.assertEqual([a["title"] for a in kept], [f"Find {i}" for i in range(10 - O.ALERT_KEEP, 10)])

    def test_panel(self):
        pal = O.palette()
        kept = [alert("Oldest", 100), alert("Interdicted", 101, "you submitted", danger=True), alert("Second", 102),
                alert("Newest", 103, "a long text " * 30)]
        p = O.alerts_panel(kept, pal, now=104)
        lines = texts(p)
        self.assertEqual([lines[0], lines[1], lines[-2], lines[-1]], ["Newest", lines[1], "Interdicted", "you submitted"])
        self.assertNotIn("Oldest", lines)                                          # three at most, newest first
        self.assertEqual(lines[1 + O.ALERT_BODY_ROWS], "Second")                  # the long text wrapped to two rows,
        self.assertTrue(lines[O.ALERT_BODY_ROWS].endswith("…"))                    # then cut
        self.assertTrue(all(O.text_width(t) <= O.ALERT_W - 2 * O.PAD for t in lines))
        self.assertEqual((p["id"], p["frame"], colour_of(p, "Interdicted")), ("alerts", pal["bad"], pal["bad"]))
        self.assertEqual(colour_of(p, "Newest"), pal["text"])
        [box] = [i for i in p["items"] if i["t"] == "rect"]                        # the danger alert framed in red
        self.assertEqual(box["c"], pal["bad"])
        self.assertTrue(all(0 <= i.get("y", 0) <= p["h"] for i in p["items"]))
        # 8 s each, 15 for danger
        after = O.alerts_panel(kept, pal, now=101 + O.ALERT_SECONDS + 2)
        self.assertEqual(texts(after), ["Interdicted", "you submitted"])
        self.assertIsNone(O.alerts_panel(kept, pal, now=101 + O.ALERT_DANGER_SECONDS))
        self.assertEqual(O.alerts_panel([alert("Calm", 100)], pal, now=101)["frame"], pal["frame"])
        self.assertIsNone(O.alerts_panel([], pal, now=1))

    def test_setting_and_place(self):
        self.assertFalse(O.overlay_settings({})["overlay"]["alerts_panel"])           # optional: off by default
        self.assertTrue(O.overlay_settings({"overlay": {"alerts_panel": True}})["overlay"]["alerts_panel"])
        lay = O.clean_layout({"strip": {"y": 0.01}})                                 # a layout from before: filled in
        self.assertEqual(lay["alerts"]["corner"], "n")                              # top centre, under the strip
        self.assertGreater(lay["alerts"]["y"], lay["strip"]["y"])
        self.assertEqual(O.layout_update(None, {"alerts": {"y": 0.2}})[0]["alerts"]["y"], 0.2)
        self.assertEqual(O.analysis_list(["alerts"]), ["alerts"])
        self.assertEqual(O.PANEL_NAMES["alerts"], "Alerts")


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
        self.assertEqual((out["enabled"], out["theme"], out["panels"], out["test"], out["analysis_only"]),
                         (True, "elite", {"system": True, "body": True, "radar": False, "strip": False, "now": False, "bio": False,
                                          "alerts": False}, O.TEST_SECONDS, []))
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
        out, _ = self.state.overlay_set({"analysis_only": ["bio", "system"]}, now=250)   # D2a: the whole list
        self.assertEqual((out["analysis_only"], self.state.overlay_cfg["analysis_only"]), (["system", "bio"], ["system", "bio"]))
        with open(self.state.config_path, encoding="utf-8") as f:
            self.assertIn('analysis_only = ["system", "bio"]', f.read())
        self.assertEqual(self.state.overlay_set({"analysis_only": []}, now=251)[0]["analysis_only"], [])
        self.assertEqual(out["hide_docked"], ["system", "body", "now", "bio"])          # the default, as the page shows it
        out, _ = self.state.overlay_set({"hide_docked": ["alerts", "now"]}, now=252)  # the whole list
        self.assertEqual((out["hide_docked"], self.state.overlay_cfg["hide_docked"]), (["now", "alerts"], ["now", "alerts"]))
        with open(self.state.config_path, encoding="utf-8") as f:
            self.assertIn('hide_docked = ["now", "alerts"]', f.read())
        out, _ = self.state.overlay_set({"hide_on_foot": ["now", "radar"], "hide_mouse_lock": True}, now=253)
        self.assertEqual((out["hide_on_foot"], out["hide_mouse_lock"]), (["radar", "now"], True))
        with open(self.state.config_path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('hide_on_foot = ["radar", "now"]', text)
        self.assertIn("hide_mouse_lock = true", text)
        for bad in (None, {}, {"enabled": "yes"}, {"theme": "neon"}, {"panels": {"map": True}}, {"panels": {}}, {"test": 1},
                    {"volume": 3}, {"analysis_only": ["map"]}, {"analysis_only": "bio"}, {"analysis_only": [True]},
                    {"hide_docked": ["radar"]}, {"hide_docked": "now"}, {"hide_on_foot": ["map"]}, {"hide_on_foot": "now"},
                    {"hide_mouse_lock": "yes"}):
            self.assertEqual(self.state.overlay_set(bad, now=300)[1], 400, bad)

    def test_all_panels_size(self):
        """The 4K TV report (2026-10-14): POST /api/overlay {panel_scale} sets all panels' size (clamped, a whole %),
        written into [overlay], in the window's GET and in Settings' state."""
        out, status = self.state.overlay_set({"panel_scale": 35}, now=10)
        self.assertEqual((status, out["panel_scale"], self.state.overlay_view(now=11)["panel_scale"]), (200, 35, 35))
        with open(self.state.config_path, encoding="utf-8") as f:
            self.assertIn("panel_scale = 35", f.read())
        self.assertEqual(self.state.overlay_set({"panel_scale": 3}, now=12)[0]["panel_scale"], 20)
        self.assertEqual(self.state.overlay_set({"panel_scale": 120.4}, now=12)[0]["panel_scale"], 120)
        for bad in ({"panel_scale": "50"}, {"panel_scale": True}, {"panel_scale": None}, {"panel_scale": float("nan")}):
            self.assertEqual(self.state.overlay_set(bad, now=13)[1], 400, bad)

    def test_text_size_per_panel_reaches_the_builders(self):
        """3b: a panel's own text size (the layout's "text") builds that panel at it; the others at [overlay]
        text_size; the test panels too."""
        self.state.overlay_cfg["text_size"] = "small"
        self.state.overlay_layout_set({"system": {"text": "large"}, "radar": {"text": "normal"}})
        self.assertEqual(self.state.overlay_sizes(), {"system": "large", "body": "small", "radar": "normal", "strip": "small",
                                                      "now": "small", "bio": "small", "alerts": "small"})
        self.state.overlay_set({"test": True}, now=50)
        panels = {p["id"]: p for p in self.state.overlay_view(now=51)["panels"]}
        sizes = lambda p: {it.get("size") for it in p["items"] if it["t"] == "text"} | \
            {r[2] for it in p["items"] if it["t"] == "runs" for r in it["runs"]}   # noqa: E731
        self.assertEqual(sizes(panels["system"]), {"large"})
        self.assertEqual(sizes(panels["bio"]) - {"large"}, {"small"})           # its title is large at any size
        self.assertEqual(panels["system"]["w"], O.test_panels(O.palette(), "large")[0]["w"])
        # live, as the test panels: the alerts panel at its own size
        self.state.overlay_test_until = 0
        self.state.overlay_cfg.update(enabled=True, alerts_panel=True)
        self.state.overlay_layout_set({"alerts": {"text": "large"}})
        self.state.journals.status_json = {"live": True, "flags": 0, "gui_focus": 0}
        self.state.overlay_alerts.append({"kind": "find", "title": "B 1", "body": "x", "danger": False, "t": 100})
        got = [p for p in self.state.overlay_panels(now=101) if p["id"] == "alerts"]
        self.assertEqual(sizes(got[0]) if got else None, {"large"})

    def test_text_figures_from_the_windows_height(self):
        """Settings says what each size comes to: the window's GET carries the game window's height (&h=), kept from
        the window only, the page woken on a change; each panel's smallest text in pixels, held at MIN_TEXT_PX where the
        sizes would draw it smaller. No window drawing: no figure."""
        s = self.state
        s.overlay_view(now=10, window=False, height="2160")                   # another visitor: nothing learned
        self.assertIsNone(s.overlay_win_h)
        v0 = s.version
        s.overlay_view(now=11, height="2160")
        self.assertEqual((s.overlay_win_h, s.version), (2160, v0 + 1))
        s.overlay_view(now=12, height="2160")                                 # the same: nothing to wake the page for
        s.overlay_view(now=12, height="tall")                                 # not a number: ignored
        s.overlay_view(now=12, height="99999")                                # out of reason: ignored
        self.assertEqual((s.overlay_win_h, s.version), (2160, v0 + 1))
        s.overlay_cfg["panel_scale"] = 25
        info = s.overlay_info(now=13)
        self.assertEqual((info["win_h"], info["panel_scale"], info["min_text_px"]), (2160, 25, O.MIN_TEXT_PX))
        # 4K at 25 %, normal text: 2.25 x 0.25 x 15 = 8.4 px, held at 9; the radar's small labels too
        self.assertEqual(info["text_px"]["system"], {"px": 9, "held": True})
        self.assertEqual(info["text_px"]["radar"], {"px": 9, "held": True})
        s.overlay_layout_set({"system": {"scale": 2.0, "text": "large"}})
        self.assertEqual(s.overlay_info(now=13)["text_px"]["system"], {"px": 21, "held": False})   # 2.25 x .5 x 19
        s.overlay_view(now=14, height="")                                      # no game window now
        self.assertIsNone(s.overlay_info(now=14)["text_px"])
        s.overlay_view(now=15, height="1080")
        self.assertEqual(s.overlay_info(now=15 + ed_outrider.OVERLAY_SEEN_S + 1)["text_px"], None)   # no window drawing

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

    def test_first_stop_for_every_window(self):
        """S30: the first stop picked on Here's schematic (POST /api/plan/first) is kept on the server, for the system
        you are in only: the overlay's system and Now panels follow it, another system ignores it."""
        from aiohttp.test_utils import TestClient, TestServer
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL_PLAN if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True, now_panel=True)
        self.state.journals.status_json = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE, "gui_focus": 0}
        panel = lambda pid: next(texts(p) for p in self.state.overlay_panels(now=1010) if p["id"] == pid)
        self.assertIn("① B 2 Rocky", panel("system"))

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                post = lambda body: c.post("/api/plan/first", json=body)
                out = [(await post({"id64": "77", "body": "B 1"})).status]
                out.append(self.state.plan_first())
                out += [(await post(b)).status for b in ({"id64": "78", "body": "B 1"}, {"id64": "77", "body": 5}, {"body": "B 1"},
                                                         {"id64": "77", "body": "x" * 101})]
                return out
        ok, kept, elsewhere, bad, no_id, long = asyncio.run(go())
        self.assertEqual((ok, kept, elsewhere, bad, no_id, long), (200, {"id64": "77", "body": "B 1"}, 409, 400, 400, 400))
        self.assertEqual(self.state.payload()["plan_first"], {"id64": "77", "body": "B 1"})
        self.assertEqual(panel("system")[2:5], ["① B 1 Icy", "TO LAND 2.0M", "② B 2 Rocky"])
        self.assertTrue(any(t.startswith("Next: bio on B 1") for t in panel("now")))
        self.assertTrue(self.state.set_plan_first(77, None))                         # ↺ order: the suggested order again
        self.assertIsNone(self.state.plan_first())
        self.assertIn("① B 2 Rocky", panel("system"))
        self.state.set_plan_first(77, "B 1")
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(2000), "StarSystem": "Elsewhere",
                                    "SystemAddress": 78, "StarPos": [5, 0, 0]})
        self.assertIsNone(self.state.plan_first())                                   # another system: forgotten
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(3000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.assertIsNone(self.state.plan_first())                                   # and back again: still forgotten
        self.state.set_plan_first(77, "B 1")
        self.state.journals.handle({"event": "Location", "timestamp": ed_outrider.iso_ts(3100), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.assertEqual(self.state.plan_first_body(), "B 1")                        # a relog here keeps it
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1500), "StarSystem": "Elsewhere",
                                    "SystemAddress": 78, "StarPos": [5, 0, 0]})
        self.assertEqual(self.state.plan_first_body(), "B 1")                        # an older arrival read late: kept
        self.assertNotIn("plan_first", ed_outrider.RESET_JOURNAL_DATA)              # live-only: a re-read keeps it

    def test_nothing_while_the_game_loads(self):
        """After a crash the old Status.json still says live: the relaunched game's loading screens, before the menu
        and after it, showed the dead session's panels until the new session's Location (the author, 2026-10-11)."""
        j = self.state.journals
        j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                  "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True)
        j.status_json = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE, "gui_focus": 0}   # the crashed session's
        shown = lambda: [p["id"] for p in self.state.overlay_panels(now=1010)]
        self.assertEqual(shown(), ["system"])
        j.handle({"event": "Fileheader", "timestamp": ed_outrider.iso_ts(1100), "part": 1})       # relaunched
        self.assertEqual(shown(), [])
        j.handle({"event": "Location", "timestamp": ed_outrider.iso_ts(1200), "StarSystem": "Test Sector AB-C d1-2",
                  "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.assertEqual(shown(), ["system"])
        j.handle({"event": "Fileheader", "timestamp": ed_outrider.iso_ts(1300), "part": 2})       # a long session's next file
        self.assertEqual(shown(), ["system"])
        j.handle({"event": "LoadGame", "timestamp": ed_outrider.iso_ts(1400), "Commander": "Test", "FID": "F1"})   # menu, then in
        self.assertEqual(shown(), [])
        # kept over a restart of Outrider (the reader resumes from its offsets)
        self.assertTrue(ed_outrider.Journals(self.db).loading())
        j.handle({"event": "Location", "timestamp": ed_outrider.iso_ts(1400), "StarSystem": "Test Sector AB-C d1-2",
                  "SystemAddress": 77, "StarPos": [0, 0, 0]})   # the same second as the LoadGame: loaded
        self.assertEqual(shown(), ["system"])

    def target_setup(self):
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL if id64 == 77 else None
        self.state.overlay_cfg.update(enabled=True, system_panel=False)
        st = {"live": True, "flags": ed_outrider.FLAG_IN_MAIN_SHIP | ed_outrider.FLAG_SUPERCRUISE, "gui_focus": 0}
        self.state.journals.status_json = st
        return st

    def target(self, now=1010):
        """The Target panel's title, or None when it is not shown."""
        got = [p for p in self.state.overlay_panels(now=now) if p["id"] == "body"]
        return got[0]["items"][0]["runs"][0][0] if got else None

    def test_target_panel_body_targeted_else_system(self):
        """D1: outside a body's zone the Target panel shows the body targeted in this system, else the system targeted,
        else nothing (no "body you fly near" fallback); its id stays "body", so the Body panel's place and size apply."""
        st = self.target_setup()
        self.assertEqual(O.PANEL_NAMES["body"], "Target")
        self.assertIsNone(self.target())                                            # nothing targeted: hidden
        st["body"] = "Test Sector AB-C d1-2 B 1"                                   # near a body, no altitude: no zone
        self.assertIsNone(self.target())
        st.update(destination={"System": 77, "Body": 9, "Name": "Test Sector AB-C d1-2 A 3"})
        self.assertEqual(self.target(), "A 3")                                      # the body targeted
        st.update(destination={"System": 77, "Body": 13, "Name": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=3;"})
        self.assertEqual(self.target(), "B 2")                                      # a mining site: its planet
        self.state.journals.handle({"event": "FSDTarget", "timestamp": ed_outrider.iso_ts(1005), "Name": "Ossia",
                                    "SystemAddress": 99, "StarClass": "H", "RemainingJumpsInRoute": 4})
        self.assertEqual(self.state.journals.target["remaining"], 4)                # kept for "next jump · 4 to go"
        self.assertEqual(self.target(), "B 2")                                      # a body targeted beats the system
        st.update(destination={"System": 77, "Body": 40, "Name": "Harper Dock"})   # a station is no body: the system
        p = next(p for p in self.state.overlay_panels(now=1010) if p["id"] == "body")
        self.assertEqual(texts(p)[:3], ["➜ Ossia", "next jump of your route · 4 to go", "checking…"])   # lookup not in yet
        self.assertIn("black hole · ✕ not scoopable · ⚠ throttle down", texts(p))
        # the lookup lands for this target: its verdict, counts and EDSM's; the Nearby row's value and notables
        self.state.target = dict(self.state.journals.target, status="partial", known=3, count=12, source="spansh",
                                 edsm={"known": 5, "count": 12})
        self.state.systems[99] = {"distance": 38.24, "notable": {"WW": 2, "T": 1},
                                  "value_parts": {"carto_now": 0, "carto_left": 12_300_000, "bio_now": 0, "bio_left": 40_000_000}}
        t = texts(next(p for p in self.state.overlay_panels(now=1010) if p["id"] == "body"))
        self.assertEqual(t[2:], ["partly scanned · 3/12 known · EDSM 5/12", "black hole · ✕ not scoopable · ⚠ throttle down",
                                 "38.2 ly", "~12.3M scan+map · bio up to 40.0M · WW×2 T"])
        self.state.target = dict(self.state.target, ts="older")                    # a verdict for an older target: checking
        self.assertIn("checking…", texts(next(p for p in self.state.overlay_panels(now=1010) if p["id"] == "body")))
        st["flags"] |= ed_outrider.FLAG_DOCKED                                       # docked: hidden (outside the galaxy map)
        self.assertIsNone(self.target())
        st["flags"] = ed_outrider.FLAG_IN_MAIN_SHIP | ed_outrider.FLAG_LANDED       # landed: the radar's
        self.assertIsNone(self.target())
        st["flags"] = ed_outrider.FLAG_IN_MAIN_SHIP
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1100), "StarSystem": "Ossia",
                                    "SystemAddress": 99, "StarPos": [30, 0, 0]})
        self.assertIsNone(self.target(now=1110))                                    # arrived: the target is gone

    def test_target_panel_near_body_zone(self):
        """D1 (the author's final rule): inside the near-body zone (Status.json names the body and gives an altitude)
        the panel shows that body, even over a target; after leaving it the target again, but only once 5 s out of the
        zone (its edge bounces)."""
        st = self.target_setup()
        st.update(destination={"System": 77, "Body": 9, "Name": "Test Sector AB-C d1-2 A 3"})
        self.assertEqual(self.target(now=1010), "A 3")
        st.update(body="Test Sector AB-C d1-2 B 1", alt=480_000)                  # in B 1's zone (ApproachBody's point)
        self.assertEqual(self.target(now=1011), "B 1")                              # at once, over the target
        st.update(body=None, alt=None)                                              # out of the zone
        self.assertEqual(self.target(now=1012), "B 1")                              # kept for a while
        self.assertEqual(self.target(now=1011 + ed_outrider.TARGET_ZONE_LINGER_S - 0.5), "B 1")
        self.assertEqual(self.target(now=1011 + ed_outrider.TARGET_ZONE_LINGER_S), "A 3")   # then the target again
        st.update(body="Test Sector AB-C d1-2 B 1", alt=60_000)                   # back in: at once
        self.assertEqual(self.target(now=1030), "B 1")
        st.update(body="Test Sector AB-C d1-2 C 9", alt=1000)                     # a body nothing is known of: the target
        self.assertEqual(self.target(now=1031), "A 3")
        st.update(body=None, alt=None, destination=None)
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1032), "StarSystem": "Elsewhere",
                                    "SystemAddress": 78, "StarPos": [5, 0, 0]})
        self.state.overlay_zone = {"system": 77, "body": "B 1", "t": 1032}          # left in another system: never kept
        self.assertIsNone(self.target(now=1033))

    def test_target_panel_over_the_galaxy_map(self):
        """D1: the galaxy map is the one screen the overlay does not leave: the Target panel alone, with the system
        targeted there (even docked, even in a body's zone); the system map and the rest still hide every panel."""
        st = self.target_setup()
        self.state.overlay_cfg.update(system_panel=True, strip_panel=True, now_panel=True, bio_panel=True)
        st.update(body="Test Sector AB-C d1-2 B 1", alt=2000, destination={"System": 77, "Body": 9, "Name": "A 3"},
                  gui_focus=ed_outrider.OVERLAY_GALAXY_MAP, flags=ed_outrider.FLAG_IN_MAIN_SHIP | ed_outrider.FLAG_DOCKED)
        self.assertEqual(self.state.overlay_panels(now=1010), [])                  # no system targeted: nothing
        self.state.journals.handle({"event": "FSDTarget", "timestamp": ed_outrider.iso_ts(1005), "Name": "Ossia",
                                    "SystemAddress": 99, "StarClass": "K", "RemainingJumpsInRoute": 1})
        got = self.state.overlay_panels(now=1010)
        self.assertEqual([(p["id"], p["items"][0]["runs"][0][0]) for p in got], [("body", "➜ Ossia")])
        self.assertFalse(any("next jump" in x for x in texts(got[0])))              # a lone target: no route words
        self.state.overlay_cfg.update(body_panel=False)
        self.assertEqual(self.state.overlay_panels(now=1010), [])
        self.state.overlay_cfg.update(body_panel=True)
        st["gui_focus"] = 7                                                         # the system map: nothing
        self.assertEqual(self.state.overlay_panels(now=1010), [])

    def test_now_heads_only_for_a_body_of_this_system(self):
        """Now's heading-to line: a targeted station or mining site is no body (the page's Now view matches by body id
        too), so no "➜ Harper Dock · nothing to do here" and no raw $SAA_ name (review 2026-10-11)."""
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Test Sector AB-C d1-2",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.system_detail = lambda id64: DETAIL if id64 == 77 else None
        st = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE | ed_outrider.FLAG_IN_MAIN_SHIP, "gui_focus": 0}
        self.state.journals.status_json = st
        info = lambda: self.state.overlay_now_info(self.state.journals.pos, 1010)
        st["destination"] = {"System": 77, "Body": 40, "Name": "Harper Dock"}
        self.assertEqual((info()["destination"], info()["destination_ls"]), (None, None))
        st["destination"] = {"System": 77, "Body": 13, "Name": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=3;"}
        self.assertEqual((info()["destination"], info()["destination_ls"]), ("B 2", 70))   # the site's planet
        st["destination"] = {"System": 77, "Body": 9, "Name": "Test Sector AB-C d1-2 A 3"}
        self.assertEqual((info()["destination"], info()["destination_ls"]), ("A 3", 900))

    def test_now_never_names_the_previous_target(self):
        """Review 2026-10-20 L10: while a new target's lookup ran, Now (its overlay panel and the page's line) named the
        previous target with its verdict; the Target panel already showed the new one as checking."""
        self.state.journals.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(1000), "StarSystem": "Here",
                                    "SystemAddress": 77, "StarPos": [0, 0, 0]})
        self.state.target = {"id64": 5, "name": "Old Target", "ts": ed_outrider.iso_ts(1001), "status": "unreported"}
        self.state.journals.target = {"id64": 6, "name": "New Target", "ts": ed_outrider.iso_ts(1005), "star_class": "K"}
        t = self.state.overlay_now_info(self.state.journals.pos, 1010)["target"]
        self.assertEqual((t["name"], t["status"], t["star_class"]), ("New Target", "checking", "K"))
        self.assertEqual((self.state.payload()["target"]["name"], self.state.payload()["target"]["status"]), ("New Target", "checking"))
        self.state.target = {"id64": 6, "name": "New Target", "ts": ed_outrider.iso_ts(1005), "status": "partial"}
        self.assertEqual(self.state.overlay_now_info(self.state.journals.pos, 1010)["target"]["status"], "partial")   # landed

    def test_overlay_detail_follows_a_new_spansh_record(self):
        """Review 2026-10-20 L11: a newer Spansh record with the same status (the full dump after the search's brief
        one, a refresh) was missed by the panels' cache until your next own scan."""
        built = []
        self.state.system_detail = lambda id64: built.append(id64) or {"n": len(built)}
        self.state.bases[77] = {"records": []}
        self.assertEqual(self.state.overlay_detail(77), {"n": 1})
        self.assertEqual(self.state.overlay_detail(77), {"n": 1})   # cached
        self.state.bases[77] = {"records": [{"name": "A 1"}]}       # replaced, same status
        self.assertEqual(self.state.overlay_detail(77), {"n": 2})

    def test_analysis_only_panels(self):
        """D2a: a panel marked analysis only shows in your ship only with the HUD in analysis mode; in the SRV, on foot,
        over the galaxy map and for the test panels the mark is ignored."""
        st = self.target_setup()
        self.state.overlay_cfg.update(system_panel=True, strip_panel=True, analysis_only=["system"])
        ship, sc, hud = ed_outrider.FLAG_IN_MAIN_SHIP, ed_outrider.FLAG_SUPERCRUISE, ed_outrider.FLAG_HUD_ANALYSIS
        shown = lambda: [p["id"] for p in self.state.overlay_panels(now=1010)]
        st["flags"] = ship | sc                                                     # combat mode: the system panel off
        self.assertEqual(shown(), ["strip"])
        st["flags"] = ship | sc | hud                                               # analysis mode: on
        self.assertEqual(shown(), ["system", "strip"])
        self.state.overlay_cfg.update(analysis_only=["strip"])
        st.update(flags=ed_outrider.FLAG_IN_SRV, flags2=0)                          # the SRV has no HUD modes: shown
        self.assertEqual(shown(), ["strip"])
        st.update(flags=0, flags2=1)                                                # on foot: shown
        self.assertEqual(shown(), ["strip"])
        self.state.overlay_cfg.update(analysis_only=["body"])
        self.state.journals.handle({"event": "FSDTarget", "timestamp": ed_outrider.iso_ts(1005), "Name": "Ossia",
                                    "SystemAddress": 99, "StarClass": "K"})
        st.update(flags=ship, flags2=0, gui_focus=ed_outrider.OVERLAY_GALAXY_MAP)  # the galaxy map: the target shows
        self.assertEqual(shown(), ["body"])
        st["gui_focus"] = 0
        self.assertEqual(shown(), ["strip"])
        self.state.overlay_set({"test": True}, now=1000)                            # the test panels: all of them
        self.assertEqual(shown(), list(O.PANELS))

    def test_hidden_on_foot(self):
        """[overlay] hide_on_foot (the author, 2026-10-15): each panel ticked hides on foot, anywhere (a station, a
        planet's surface), none by default; hide_mouse_lock: nothing at all on foot (the DSS never had panels); in the
        ship neither hides anything."""
        st = self.target_setup()
        self.state.overlay_cfg.update(strip_panel=True, now_panel=True, alerts_panel=True, hide_docked=[])
        self.state.overlay_alert({"kind": "find", "title": "B 1: Earth-like world"}, now=1009)
        shown = lambda: [p["id"] for p in self.state.overlay_panels(now=1010)]
        self.assertEqual(O.DEFAULTS["hide_on_foot"], [])
        flying = shown()
        self.assertIn("now", flying)
        st.update(flags=0, flags2=ed_outrider.FLAG2_ON_FOOT)                         # on foot on a surface: by default all
        self.assertEqual(shown(), ["strip", "now", "alerts"])
        self.state.overlay_cfg["hide_on_foot"] = ["now"]                               # Now ticked: hidden on foot
        self.assertEqual(shown(), ["strip", "alerts"])
        st.update(flags2=ed_outrider.FLAG2_ON_FOOT | (1 << 13))                        # on foot in a hangar: the same
        self.assertEqual(shown(), ["strip", "alerts"])
        self.state.overlay_cfg["hide_mouse_lock"] = True                               # nothing on foot
        self.assertEqual(shown(), [])
        st.update(flags=ed_outrider.FLAG_IN_MAIN_SHIP, flags2=0)                       # back in the ship: as before
        self.assertEqual(shown(), flying)
        st["gui_focus"] = 10                                                           # the DSS: never any
        self.assertEqual(shown(), [])

    def test_hidden_while_docked(self):
        """[overlay] hide_docked (the author, 2026-10-14): each panel docked (the ship's flag, or on foot in a station)
        shows or hides as its box says; by default System, Target, Now and Bio hide, Strip and Alerts show; the Target
        panel still shows over the galaxy map, docked; undocked nothing is hidden by it."""
        st = self.target_setup()
        self.state.journals.handle({"event": "FSDTarget", "timestamp": ed_outrider.iso_ts(1005), "Name": "Ossia",
                                    "SystemAddress": 99, "StarClass": "K"})
        self.state.overlay_cfg.update(strip_panel=True, now_panel=True, bio_panel=True, alerts_panel=True)
        self.state.overlay_alert({"kind": "find", "title": "B 1: Earth-like world"}, now=1009)
        shown = lambda: [p["id"] for p in self.state.overlay_panels(now=1010)]
        ship = ed_outrider.FLAG_IN_MAIN_SHIP
        self.assertEqual(shown(), ["body", "strip", "now", "bio", "alerts"])         # flying: all of them
        st["flags"] = ship | ed_outrider.FLAG_DOCKED
        self.assertEqual(shown(), ["strip", "alerts"])                               # docked, the defaults
        st.update(flags=0, flags2=1 | (1 << 13))                                     # on foot in a hangar: the same
        self.assertEqual(shown(), ["strip", "alerts"])
        st.update(flags=ship | ed_outrider.FLAG_DOCKED, flags2=0)
        for p in ("body", "strip", "now", "bio", "alerts"):                          # each box on its own
            others = [x for x in ("body", "strip", "now", "bio", "alerts") if x != p]
            self.state.overlay_cfg["hide_docked"] = others
            self.assertEqual(shown(), [p], p)
        self.state.overlay_cfg["hide_docked"] = []                                   # nothing ticked: all of them docked
        self.assertEqual(shown(), ["body", "strip", "now", "bio", "alerts"])
        self.state.overlay_cfg["hide_docked"] = list(O.HIDE_DOCKED_DEFAULT)
        st["gui_focus"] = ed_outrider.OVERLAY_GALAXY_MAP                             # the galaxy map: the Target panel shows
        self.assertEqual(shown(), ["body", "alerts"])
        st.update(gui_focus=0, flags=ship | ed_outrider.FLAG_SUPERCRUISE)            # the system panel: hidden docked only
        self.state.overlay_cfg.update(system_panel=True)
        self.assertEqual(shown()[0], "system")

    def test_alerts_panel(self):
        """S26: an alert the page posts shows on the Alerts panel for ALERT_SECONDS wherever the overlay shows panels
        (docked, on foot, over the galaxy map beside the Target panel), never over the system map; kept only while
        the overlay and the panel are on; analysis only applies to it as to the others."""
        st = self.target_setup()
        shown = lambda now=1010: [p["id"] for p in self.state.overlay_panels(now=now)]
        post = lambda title, now=1010, **kw: self.state.overlay_alert(dict({"kind": "find", "title": title}, **kw), now=now)
        self.assertEqual(post("Off"), ({"kept": False, "why": "the overlay or its Alerts panel is off"}, 200))
        self.assertEqual(self.state.overlay_alerts, [])
        self.state.overlay_cfg.update(alerts_panel=True)
        self.assertEqual(post("B 1: Earth-like world", body="2.4M cr"), ({"kept": True}, 200))
        self.assertEqual(post("B 1: Earth-like world", now=1011, body="2.4M cr"), ({"kept": False}, 200))   # another window's
        self.assertEqual(post(""), ({"error": f"title: text, 1 to {O.ALERT_TITLE_MAX} characters"}, 400))
        self.assertEqual(shown(), ["alerts"])
        st["flags"] = ed_outrider.FLAG_IN_MAIN_SHIP | ed_outrider.FLAG_DOCKED            # docked: still shown
        self.assertEqual(shown(), ["alerts"])
        st.update(flags=0, flags2=1)                                                    # on foot
        self.assertEqual(shown(), ["alerts"])
        self.state.journals.handle({"event": "FSDTarget", "timestamp": ed_outrider.iso_ts(1005), "Name": "Ossia",
                                    "SystemAddress": 99, "StarClass": "K"})
        st.update(flags=ed_outrider.FLAG_IN_MAIN_SHIP, flags2=0, gui_focus=ed_outrider.OVERLAY_GALAXY_MAP)
        self.assertEqual(shown(), ["body", "alerts"])                                  # over the galaxy map too
        st["gui_focus"] = 7
        self.assertEqual(shown(), [])                                                  # the system map: nothing
        st["gui_focus"] = 0
        self.assertEqual(shown(1010 + O.ALERT_SECONDS), ["body"])                      # gone after 8 s
        self.state.overlay_cfg.update(analysis_only=["alerts"])
        self.assertEqual(shown(), ["body"])                                            # combat mode: off
        st["flags"] |= ed_outrider.FLAG_HUD_ANALYSIS
        self.assertEqual(shown(), ["body", "alerts"])
        self.state.overlay_cfg.update(alerts_panel=False)
        self.assertEqual(shown(), ["body"])

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

    def test_loopback_for_the_window(self):
        """The window always asks http://127.0.0.1:<port>: with [server] host one LAN address Outrider listens on
        loopback too, or the window draws nothing (review 2026-10-11)."""
        self.assertTrue(ed_outrider.loopback_too("192.168.1.20"))
        self.assertTrue(ed_outrider.loopback_too("mypc.lan"))
        for h in ("127.0.0.1", "::1", "localhost", "0.0.0.0", "::", ""):
            self.assertFalse(ed_outrider.loopback_too(h), h)

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
        st.update(gui_focus=0, flags=ed_outrider.FLAG_DOCKED | ed_outrider.FLAG_IN_MAIN_SHIP)     # docked: neither (hide_docked's default)
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], [])
        st.update(flags=0, flags2=1 | (1 << 3))                                   # on foot in the station: neither
        self.assertEqual([p["id"] for p in self.state.overlay_panels(now=1010)], [])
        self.state.overlay_cfg.update(hide_docked=["now"])                        # Bio unticked: it shows docked
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
                await c.get("/api/overlay", headers={"User-Agent": "outrider-overlay"}, params={"w": "drawing", "h": "1440"})
                seen_by_window = self.state.overlay_info()["window"]
                self.assertEqual(self.state.overlay_win_h, 1440)   # the game window's height, through the route
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
                # S26: the page's alerts, pc_only like the rest; checked, capped, refused from another site
                self.state.overlay_cfg.update(enabled=True, alerts_panel=True)
                one = {"kind": "hull", "title": "Interdicted", "body": "you submitted", "danger": True}
                alerts = [await (await c.post("/api/overlay/alert", json=one)).json(),
                          (await c.post("/api/overlay/alert", json=dict(one, body="x" * 400))).status,
                          (await c.post("/api/overlay/alert", data="[1]", headers={"Content-Type": "application/json"})).status,
                          (await c.post("/api/overlay/alert", json=dict(one, title="Other"),
                                        headers={"Origin": "http://evil.example"})).status]
                self.state.game_pc = False
                alerts.append((await c.post("/api/overlay/alert", json=one)).status)
                self.state.game_pc = True
                self.assertEqual(alerts, [{"kept": True}, 400, 400, 403, 409])
                self.assertEqual([a["title"] for a in self.state.overlay_alerts], ["Interdicted"])
                return (first, same, bad, ok, lay.status, (await lay.json())["layout"]["system"]["y"], lay_bad, cross,
                        seen_by_visitor, seen_by_window)
        first, same, bad, ok, lay, y, lay_bad, cross, by_visitor, by_window = asyncio.run(go())
        self.assertEqual((by_visitor, by_window), (False, True))   # only the overlay window counts as drawing
        self.assertEqual((first["panels"], same["same"], bad, ok["test"], lay, y, lay_bad, cross),
                         ([], True, 400, O.TEST_SECONDS, 200, 0.5, 400, 403))


class FakeRunner:
    """OverlayRunner's face to the State (status, tick, proc): starts at "off", "starting" on the first wanted tick,
    "running" after; never a process."""

    def __init__(self, state="off", why=None):
        self.state, self.why, self.proc, self.wants = state, why, None, []

    def status(self):
        return {"state": self.state, "why": self.why}

    def tick(self, want):
        self.wants.append(want)
        self.state = ("starting" if self.state == "off" else "running") if want else "off"


class Pill(unittest.TestCase):
    """S8: the page's overlay pill, from the runner, the window's word (&w=), the game and DisplaySettings.xml."""

    def test_health(self):
        run = {"state": "running", "why": None}
        h = lambda **kw: O.health(**dict(dict(wanted=True, runner=run, track="drawing", quiet=1, started=True, live=True,
                                              loading=False), **kw))
        self.assertEqual(h(), {"state": "ok", "code": "drawing", "why": "drawing over Elite"})
        self.assertIsNone(h(wanted=False))                     # the overlay off: no pill
        self.assertIsNone(h(runner=None))                      # no window run here (a server)
        word = lambda **kw: (h(**kw)["state"], h(**kw)["code"])
        self.assertEqual(word(runner={"state": "installing", "why": None}), ("wait", "installing"))
        self.assertEqual(word(runner={"state": "install_failed", "why": "no network"}), ("bad", "install_failed"))
        self.assertIn("no network", h(runner={"state": "install_failed", "why": "no network"})["why"])
        self.assertEqual(word(runner={"state": "failed", "why": "it stopped 5 times"}), ("bad", "failed"))
        self.assertEqual(word(runner={"state": "restarting", "why": "stopped"}), ("wait", "restarting"))
        self.assertEqual(word(runner={"state": "starting", "why": None}), ("wait", "starting"))
        self.assertEqual(word(started=False, quiet=3), ("wait", "starting"))           # started, not asked yet
        self.assertEqual(word(started=False, quiet=O.QUIET_S + 1), ("bad", "quiet"))    # started and never asked
        self.assertEqual(word(quiet=O.QUIET_S + 1), ("bad", "quiet"))                  # asked, then went quiet
        self.assertEqual(word(quiet=None, started=False, runner={"state": "off", "why": None}), ("wait", "starting"))
        # the tools first (a fix for the player, whatever the game does), then the game, then the window's word
        self.assertEqual(word(track="no_wmctrl", live=False), ("bad", "no_wmctrl"))
        self.assertIn("wmctrl not installed", h(track="no_wmctrl")["why"])
        self.assertEqual(word(track="no_xprop"), ("bad", "no_xprop"))
        self.assertEqual(word(track="no_window", loading=True), ("wait", "loading"))
        self.assertEqual(word(track="no_window", live=False), ("wait", "no_game"))
        self.assertEqual(word(track="no_window"), ("bad", "no_window"))
        self.assertEqual(word(fullscreen=True), ("bad", "fullscreen"))
        self.assertIn("Borderless", h(fullscreen=True)["why"])
        for code, level in (("behind", "wait"), ("hidden", "wait"), ("covered", "wait"), ("no_tracker", "bad")):
            self.assertEqual(word(track=code), (level, code))
        self.assertEqual(word(track=None), ("wait", "starting"))
        self.assertEqual(set(O.TRACK_WHY), set(O.TRACK_CODES))

    def test_display_settings(self):
        """Exclusive fullscreen from the game's DisplaySettings.xml, found from the journal folder (Proton or Windows)."""
        j = os.path.join("pfx", "drive_c", "users", "steamuser", "Saved Games", "Frontier Developments", "Elite Dangerous")
        got = O.display_settings_paths([j, j + os.sep], {"LOCALAPPDATA": "L"})
        self.assertEqual(got, [os.path.join("pfx", "drive_c", "users", "steamuser", "AppData", "Local", "Frontier Developments",
                                            "Elite Dangerous", "Options", "Graphics", "DisplaySettings.xml"),
                               os.path.join("L", "Frontier Developments", "Elite Dangerous", "Options", "Graphics",
                                            "DisplaySettings.xml")])
        xml = "<?xml version=\"1.0\"?>\n<DisplayConfig>\n\t<ScreenWidth>2560</ScreenWidth>\n\t<FullScreen>{}</FullScreen>\n</DisplayConfig>\n"
        self.assertEqual([O.display_mode(xml.format(v)) for v in ("0", "1", "2", "7")], ["windowed", "fullscreen", "borderless", None])
        self.assertIsNone(O.display_mode("<DisplayConfig/>"))

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.state.config_path = os.path.join(tmp.name, "ed_outrider.toml")
        live = ed_outrider.LIVE_DIRS
        ed_outrider.LIVE_DIRS = []
        self.addCleanup(setattr, ed_outrider, "LIVE_DIRS", live)

    def test_the_windows_word(self):
        """The window's &w= is kept from its own GETs only, a known word only; the page is woken when it changes."""
        s = self.state
        s.overlay_view(now=10, window=False, track="behind")       # another visitor: not the window
        self.assertIsNone(s.overlay_track)
        v0 = s.version
        s.overlay_view(now=11, track="behind")
        self.assertEqual((s.overlay_track, s.version), ("behind", v0 + 1))
        s.overlay_view(now=12, track="behind")                      # the same word: nothing to wake the page for
        s.overlay_view(now=13, track="nonsense")                    # not a word: ignored
        self.assertEqual((s.overlay_track, s.version), ("behind", v0 + 1))
        s.overlay_view(now=14, track="drawing")
        self.assertEqual((s.overlay_track, s.version), ("drawing", v0 + 2))

    def test_pill_from_the_server(self):
        s = self.state
        self.assertIsNone(s.overlay_info(now=100)["pill"])           # no runner (a server, tests): no pill
        s.overlay_runner = FakeRunner()
        self.assertIsNone(s.overlay_info(now=100)["pill"])           # the overlay off
        s.overlay_cfg.update(enabled=True)
        last = s.overlay_window_tick(None, now=100)                   # the runner starts the window
        self.assertEqual((s.overlay_started, s.overlay_info(now=100)["pill"]["code"]), (100, "starting"))
        s.overlay_window_tick(last, now=102)                          # running, not asked yet
        self.assertEqual(s.overlay_pill(now=103)["code"], "starting")
        self.assertEqual(s.overlay_pill(now=100 + O.QUIET_S + 1)["code"], "quiet")   # never asked
        s.overlay_view(now=104, track="drawing")
        self.assertEqual(s.overlay_pill(now=105)["code"], "no_game")  # Elite not running (no live Status.json)
        s.journals.status_json = {"live": True, "flags": 0}
        self.assertEqual(s.overlay_pill(now=105), {"state": "ok", "code": "drawing", "why": "drawing over Elite"})
        # a window gone quiet changes the pill with nothing else happening: the watcher's tick wakes the page
        last = s.overlay_window_tick(None, now=105)
        v0 = s.version
        last = s.overlay_window_tick(last, now=106)
        self.assertEqual(s.version, v0)
        last = s.overlay_window_tick(last, now=104 + O.QUIET_S + 1)
        self.assertEqual((s.version, last[1]["code"]), (v0 + 1, "quiet"))

    def test_exclusive_fullscreen(self):
        s = self.state
        user = os.path.join(self.tmp, "steamuser")
        jdir = os.path.join(user, "Saved Games", "Frontier Developments", "Elite Dangerous")
        gdir = os.path.join(user, "AppData", "Local", "Frontier Developments", "Elite Dangerous", "Options", "Graphics")
        os.makedirs(jdir)
        os.makedirs(gdir)
        with open(os.path.join(gdir, "DisplaySettings.xml"), "w", encoding="utf-8") as f:
            f.write("<DisplayConfig><FullScreen>1</FullScreen></DisplayConfig>")
        ed_outrider.LIVE_DIRS = [jdir]
        s.overlay_runner = FakeRunner("running")
        s.overlay_cfg.update(enabled=True)
        s.journals.status_json = {"live": True, "flags": 0}
        s.overlay_view(now=200, track="drawing")
        self.assertEqual(s.overlay_pill(now=201)["code"], "fullscreen")
        with open(os.path.join(gdir, "DisplaySettings.xml"), "w", encoding="utf-8") as f:
            f.write("<DisplayConfig><FullScreen>2</FullScreen></DisplayConfig>")
        self.assertEqual(s.overlay_pill(now=202)["code"], "fullscreen")                     # looked at now and then
        later = 200 + ed_outrider.OVERLAY_DISPLAY_CHECK_S + 2
        s.overlay_view(now=later, track="drawing")
        self.assertEqual(s.overlay_pill(now=later)["code"], "drawing")

    def test_show_inactive(self):
        """S25: [overlay] show_inactive, switched from Settings, written for the next start, in the window's answer."""
        s = self.state
        self.assertFalse(s.overlay_view(now=1)["show_inactive"])
        out, status = s.overlay_set({"show_inactive": True}, now=2)
        self.assertEqual((status, out["show_inactive"]), (200, True))
        self.assertTrue(s.overlay_view(now=3)["show_inactive"])
        with open(s.config_path, encoding="utf-8") as f:
            self.assertIn("show_inactive = true", f.read())
        self.assertEqual(s.overlay_set({"show_inactive": "yes"}, now=4)[1], 400)

    def test_show_inactive_setting(self):
        self.assertFalse(O.overlay_settings({})["overlay"]["show_inactive"])
        self.assertTrue(O.overlay_settings({"overlay": {"show_inactive": True}})["overlay"]["show_inactive"])
        with contextlib.redirect_stderr(io.StringIO()) as e:
            self.assertFalse(O.overlay_settings({"overlay": {"show_inactive": "on"}})["overlay"]["show_inactive"])
        self.assertIn("show_inactive", e.getvalue())

    def test_the_word_through_the_route(self):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                await c.get("/api/overlay", params={"w": "covered"})                       # a visitor's word: ignored
                visitor = self.state.overlay_track
                await c.get("/api/overlay", params={"w": "covered"}, headers={"User-Agent": "outrider-overlay"})
                return visitor, self.state.overlay_track
        self.assertEqual(asyncio.run(go()), (None, "covered"))
