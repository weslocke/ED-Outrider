"""Unit tests: the in-game overlay, Outrider's side (outrider/overlay.py and the State's GET/POST /api/overlay). The
window on the game PC is never opened here (its pure parts are tested in test_overlay_window.py).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import contextlib
import io
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
                                                  "system_seconds": True, "url": "ftp://x", "password": 3}})["overlay"]
        self.assertEqual((got["enabled"], got["theme"], got["text_size"], got["radar_range"], got["system_seconds"],
                          got["url"], got["password"]), (False, "default", "large", 100, 0, "", ""))
        for word in ("enabled", "theme", "system_seconds", "url", "password"):
            self.assertIn(word, err.getvalue())
        self.assertEqual(O.overlay_settings({"overlay": {"url": "http://erangel:8025/"}})["overlay"]["url"], "http://erangel:8025")

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
        self.assertEqual([p["id"] for p in panels], list(O.PANELS))
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
                         (True, "elite", {"system": True, "body": True, "radar": False}, O.TEST_SECONDS))
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
                same = await (await c.get("/api/overlay", params={"since": first["version"]})).json()
                bad = (await c.post("/api/overlay", data="[1]", headers={"Content-Type": "application/json"})).status
                ok = await (await c.post("/api/overlay", json={"test": True})).json()
                lay = await c.post("/api/overlay/layout", json={"system": {"y": 0.5}})
                lay_bad = (await c.post("/api/overlay/layout", json={"system": {"y": "low"}})).status
                cross = (await c.post("/api/overlay", json={"test": True}, headers={"Origin": "http://evil.example"})).status
                return first, same, bad, ok, lay.status, (await lay.json())["layout"]["system"]["y"], lay_bad, cross
        first, same, bad, ok, lay, y, lay_bad, cross = asyncio.run(go())
        self.assertEqual((first["panels"], same["same"], bad, ok["test"], lay, y, lay_bad, cross),
                         ([], True, 400, O.TEST_SECONDS, 200, 0.5, 400, 403))
