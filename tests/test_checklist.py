"""Unit tests: the exobiology checklist (outrider.checklist): where each species can grow, its colours, and your best
state with it per region.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.bio  # noqa: E402
import outrider.checklist as cl  # noqa: E402

# regions 1..3; a ruleset's "regions" is the list of region numbers it allows (the stand-in for outrider.bio's)
region_ok = lambda r, region: "regions" not in r or region in r["regions"]   # noqa: E731
SPECIES = [
    {"id": "$A1;", "genus": "Aleoida", "name": "Aleoida Arcus", "value": 7252500, "rulesets": [{"regions": [1, 2]}],
     "colors": {"star": {"F": "Teal", "G": "Teal", "M": "Emerald"}}},
    {"id": "$B1;", "genus": "Bacterium", "name": "Bacterium Nebulus", "value": 5289900, "rulesets": [{}],
     "colors": {"element": {"polonium": "Gold", "antimony": "Magenta"}}},
    {"id": "$T1;", "genus": "Sinuous Tubers", "name": "Roseum Sinuous Tubers", "value": 111300,
     "rulesets": [{"tuber": ["Galactic Center"]}], "colors": None},
    {"id": "$S4;", "genus": "Stratum", "name": "Stratum Aranaemus", "value": 2448900, "rulesets": [], "colors": None},
    {"id": "$S4;", "genus": "Stratum", "name": "Stratum Araneamus", "value": 2448900, "rulesets": [{"regions": [3]}],
     "colors": {"star": {"F": "Lime"}}},
]


def rows(t):
    return {r["name"]: r for g in t["genera"] for r in g["species"]}


class Checklist(unittest.TestCase):
    def test_possibility(self):
        self.assertEqual(cl.possibility(SPECIES[0], 1, region_ok), "yes")
        self.assertIsNone(cl.possibility(SPECIES[0], 3, region_ok))                 # the rules rule it out
        self.assertEqual(cl.possibility(SPECIES[2], 3, region_ok), "parts")        # tubers: in their zones only
        self.assertEqual(cl.possibility(SPECIES[3], 2, region_ok), "yes")          # no rules at all: unknown, not "no"
        both = {"rulesets": [{"guardian": True, "regions": [1]}, {"regions": [1]}]}
        self.assertEqual(cl.possibility(both, 1, region_ok), "yes")                # plainly allowed by one ruleset
        self.assertEqual(cl.possibility({"rulesets": [{"guardian": True}]}, 2, region_ok), "parts")
        self.assertEqual(cl.possibility({"rulesets": [{"guardian": False}]}, 2, region_ok), "yes")   # no tie

    def test_colours(self):
        self.assertEqual(cl.colours(SPECIES[0]), [("Teal", ["F", "G"]), ("Emerald", ["M"])])
        self.assertEqual(cl.colours(SPECIES[1]), [("Gold", ["polonium"]), ("Magenta", ["antimony"])])
        self.assertEqual(cl.colours(SPECIES[2]), [])
        self.assertEqual(cl.colour_of("Aleoida Arcus - Teal", "Aleoida Arcus"), "teal")
        self.assertIsNone(cl.colour_of("Aleoida Arcus", "Aleoida Arcus"))          # before the 2023 patch
        self.assertIsNone(cl.colour_of("Other Thing - Teal", "Aleoida Arcus"))

    def test_duplicate_species_merged(self):
        merged, names = cl.merge_species(SPECIES)
        self.assertEqual([s["name"] for s in merged], ["Aleoida Arcus", "Bacterium Nebulus", "Roseum Sinuous Tubers",
                                                       "Stratum Araneamus"])   # the one with rules
        self.assertEqual(names["stratum aranaemus"], names["stratum araneamus"])
        # the real rules have that duplicate: one row for it, possible somewhere
        R = outrider.bio.load_rules()
        if not R:
            self.skipTest("no bio rules")
        t = cl.table(R["species"], None, outrider.bio.ruleset_region_ok, [], [], len(R["region_names"]) - 1)
        names = [r["name"] for g in t["genera"] for r in g["species"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(t["summary"]["possible"], len(names))   # every species can grow somewhere

    def test_bark_mounds(self):
        """The game (and Canonn) say "Bark Mounds", the rules "Bark Mound" (their genus has the plural): a codex entry
        under the game's name counts (the Fable review of 2026-10-10, #2)."""
        sp = [{"id": "$Codex_Ent_Cone_Name;", "genus": "Bark Mounds", "name": "Bark Mound", "value": 1471900,
               "rulesets": [{}], "colors": None}]
        t = rows(cl.table(sp, 1, region_ok, [], [{"name": "Bark Mounds", "region": 1}], 3))
        self.assertEqual(t["Bark Mound"]["state"], "logged")
        # in the real rules it is the only species named so; no genus name is taken for a species of another name
        R = outrider.bio.load_rules()
        if not R:
            self.skipTest("no bio rules")
        merged, names = cl.merge_species(R["species"])
        self.assertEqual(names["bark mounds"], "$Codex_Ent_Cone_Name;")
        self.assertNotIn("bacterium", names)

    def test_states_by_region(self):
        runs = [{"species_id": "$A1;", "species": "Aleoida Arcus", "variant": "Aleoida Arcus - Teal", "region": 1, "state": "lost"},
                {"species_id": "$A1;", "species": "Aleoida Arcus", "variant": "Aleoida Arcus - Teal", "region": 1, "state": "sold"},
                {"species_id": "$A1;", "species": "Aleoida Arcus", "variant": "Aleoida Arcus - Emerald", "region": 2, "state": "aboard"},
                {"species_id": "$S4;", "species": "Stratum Araneamus", "variant": "Stratum Araneamus", "region": 3,
                 "state": "in progress"},
                {"species_id": None, "species": "Unknown Thing", "variant": None, "region": 1, "state": "sold"}]
        codex = [{"name": "Bacterium Nebulus - Gold", "region": 1}, {"name": "Roseum Sinuous Tubers", "region": 3}]
        t = rows(cl.table(SPECIES, 1, region_ok, runs, codex, 3))
        a = t["Aleoida Arcus"]
        self.assertEqual((a["state"], a["runs"], a["possible"]), ("sold", 2, "yes"))   # sold beats lost; region 2's not here
        self.assertEqual([(v["colour"], v["where"], v["state"]) for v in a["variants"]["list"]],
                         [("Teal", "F, G stars", "sold"), ("Emerald", "M stars", None)])
        self.assertEqual((a["variants"]["found"], a["variants"]["total"]), (1, 2))
        self.assertEqual((t["Bacterium Nebulus"]["state"], t["Bacterium Nebulus"]["variants"]["found"]), ("logged", 1))
        self.assertIsNone(t["Stratum Araneamus"]["possible"])                       # region 3 only
        self.assertIsNone(t["Roseum Sinuous Tubers"]["state"])                      # logged in region 3, not here
        self.assertEqual(t["Roseum Sinuous Tubers"]["elsewhere"], "logged")        # ...but found elsewhere
        self.assertIsNone(t["Aleoida Arcus"]["elsewhere"])                          # found here: no "elsewhere"
        self.assertEqual(t["Roseum Sinuous Tubers"]["short"], "Roseum")
        t3 = rows(cl.table(SPECIES, 3, region_ok, runs, codex, 3))
        self.assertEqual(t3["Stratum Araneamus"]["state"], "logged")               # a run under way
        self.assertEqual((t3["Roseum Sinuous Tubers"]["state"], t3["Roseum Sinuous Tubers"]["variants"]["found"]),
                         ("logged", 1))                                              # its own one variant
        everywhere = cl.table(SPECIES, None, region_ok, runs, codex, 3)
        a = rows(everywhere)["Aleoida Arcus"]
        self.assertEqual((a["state"], [v["state"] for v in a["variants"]["list"]]), ("sold", ["sold", "aboard"]))
        s = everywhere["summary"]
        self.assertEqual((s["possible"], s["found"], s["sold"], s["logged"]), (4, 4, 1, 3))
        self.assertEqual(s["colours_found"], 4)   # Teal, Emerald, Gold, the tubers' own one (Araneamus's run has no colour)

    def test_the_server_has_it(self):
        self.assertIs(ed_outrider.outrider.checklist, cl)

    def test_completion(self):
        """Each possible species scores the share of its colours found there (any state), averaged over the region's
        possible species: half of every species is 50% with none finished (the author's measure, 2026-10-09)."""
        runs = [{"species_id": "$A1;", "species": "Aleoida Arcus", "variant": "Aleoida Arcus - Teal", "region": 1, "state": "sold"},
                {"species_id": "$A1;", "species": "Aleoida Arcus", "variant": "Aleoida Arcus - Emerald", "region": 2, "state": "lost"},
                {"species_id": "$S4;", "species": "Stratum Araneamus", "variant": "Stratum Araneamus", "region": 3, "state": "aboard"}]
        codex = [{"name": "Bacterium Nebulus - Gold", "region": 1}, {"name": "Roseum Sinuous Tubers", "region": 3}]
        done = cl.completion(SPECIES, region_ok, runs, codex, 3)
        # region 1: Arcus 1/2, Nebulus 1/2, tubers 0 -> 33.33; region 3: Nebulus 0, tubers 1, Araneamus 0 (no colour) -> 33.33
        # all: Arcus 2/2, Nebulus 1/2, tubers 1, Araneamus 0 -> 62.5
        self.assertEqual((done[1], done[3], done["all"]), (33.33, 33.33, 62.5))
        # the table's summary says the same for its region
        self.assertEqual([cl.table(SPECIES, r, region_ok, runs, codex, 3)["summary"]["completion"] for r in (1, 3, None)],
                         [33.33, 33.33, 62.5])
        self.assertIsNone(cl.completion([], region_ok, [], [], 3)[1])   # nothing can grow: no figure

    def test_geology(self):
        """The geology checklist: an entry is logged in a region or not; "possible" is reported there (Canonn's sites)."""
        E = [{"id": 1, "name": "Water Ice Geyser", "kind": "Geology", "group": "Geyser", "regions": {"1": 50, "2": 3}},
             {"id": 2, "name": "Caeruleum Lagrange Cloud", "kind": "Cloud", "group": "Lagrange Cloud", "regions": {"2": 7}},
             {"id": 3, "name": "K01-Type Anomaly", "kind": "Anomaly", "group": "K-Type Anomaly", "regions": {"3": 1}}]
        self.assertEqual([cl.geo_short(e) for e in E], ["Water Ice", "Caeruleum", "K01"])
        codex = [{"entry_id": 1, "region": 2}, {"entry_id": 2, "region": 2}]
        t = rows(cl.geo_table(E, 1, codex, 3))
        self.assertEqual((t["Water Ice Geyser"]["sites"], t["Water Ice Geyser"]["state"], t["Water Ice Geyser"]["elsewhere"]),
                         (50, None, "logged"))
        self.assertIsNone(t["Caeruleum Lagrange Cloud"]["possible"])               # not reported in region 1
        t2 = cl.geo_table(E, 2, codex, 3)
        self.assertEqual([g["genus"] for g in t2["genera"]], ["Geyser", "Lagrange Cloud", "K-Type Anomaly"])   # geology first
        self.assertEqual((t2["summary"]["logged"], t2["summary"]["possible"], t2["summary"]["completion"]), (2, 2, 100.0))
        done = cl.geo_completion(E, codex, 3)
        self.assertEqual((done[1], done[2], done[3], done["all"]), (0.0, 100.0, 0.0, 66.67))

    def test_geo_codex_resource(self):
        """resources/geo_codex.json (scripts/build_geo_codex.py, from Canonn): the codex's Geology and Anomalies entries,
        each with its reported sites per region (1-42)."""
        import json
        with open(ed_outrider.GEO_CODEX_FILE, encoding="utf-8") as f:
            doc = json.load(f)
        E = doc["entries"]
        self.assertGreaterEqual(len(E), 80)
        self.assertEqual({e["kind"] for e in E}, {"Geology", "Cloud", "Anomaly"})
        self.assertEqual(len({e["id"] for e in E}), len(E))
        for e in E:
            self.assertTrue(e["name"] and e["group"])
            self.assertTrue(all(1 <= int(r) <= 42 and n > 0 for r, n in e["regions"].items()), e["name"])
        self.assertIn("Canonn", doc["source"])

    def test_short_names(self):
        self.assertEqual(cl.short_name({"name": "Aleoida Arcus", "genus": "Aleoida"}), "Arcus")
        self.assertEqual(cl.short_name({"name": "Luteolum Anemone", "genus": "Anemone"}), "Luteolum")
        self.assertEqual(cl.short_name({"name": "Bark Mound", "genus": "Bark Mound"}), "Bark Mound")



class ChecklistServer(unittest.TestCase):
    """State.checklist and GET /api/checklist: your runs (their fates as Samples has them) and codex entries, placed by
    region; where you are by default."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        if not outrider.bio.load_rules():
            self.skipTest("no bio rules")

    def jump(self, ts, id64, name, pos):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": name, "SystemAddress": id64, "StarPos": pos})

    def organic(self, system, variant, done):
        self.db.execute("INSERT INTO own_organic (system, body_id, species, genus_name, species_name, variant_name, samples,"
                        " done_ts, ts) VALUES (?, 1, '$Codex_Ent_Stratum_07_Name;', 'Stratum', 'Stratum Tectonicas', ?, 3, ?, ?)",
                        (system, variant, done, done))

    def test_checklist(self):
        if not outrider.bio.colours_available():   # the colours' states below need ExploData's tables (downloaded)
            self.skipTest("ExploData's colour tables not downloaded (bio_colours.json)")
        self.jump("2026-01-01T00:00:00Z", 1, "Near Sol", [0, 0, 0])                         # Inner Orion Spur (18)
        self.organic(1, "Stratum Tectonicas - Lime", "2026-01-01T00:10:00Z")
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T00:20:00Z"})                # lost with the ship
        self.jump("2026-01-02T00:00:00Z", 2, "Near Colonia", [-9530.5, -910.28, 19808.1])    # Inner Scutum-Centaurus (9)
        self.organic(2, "Stratum Tectonicas - Emerald", "2026-01-02T00:10:00Z")                  # aboard
        self.db.execute("INSERT INTO codex (ts, entry_id, name, region) VALUES ('2026-01-01T00:05:00Z', 2310101,"
                        " 'Bacterium Aurasus - Teal', 'Inner Orion Spur')")
        self.jump("2026-01-03T00:00:00Z", 1, "Near Sol", [0, 0, 0])
        self.db.commit()
        row = lambda out, name: next(r for g in out["genera"] for r in g["species"] if r["name"] == name)   # noqa: E731
        out, status = self.state.checklist()
        self.assertEqual((status, out["region"], out["here"], out["region_name"]), (200, 18, 18, "Inner Orion Spur"))
        t = row(out, "Stratum Tectonicas")
        self.assertEqual((t["state"], t["runs"]), ("lost", 1))
        self.assertEqual({v["colour"]: v["state"] for v in t["variants"]["list"]}["Lime"], "lost")
        self.assertEqual(row(out, "Bacterium Aurasus")["state"], "logged")
        out, _ = self.state.checklist("9")
        self.assertEqual((row(out, "Stratum Tectonicas")["state"], row(out, "Bacterium Aurasus")["state"]), ("aboard", None))
        out, _ = self.state.checklist("all")
        self.assertEqual((out["region"], row(out, "Stratum Tectonicas")["state"], row(out, "Stratum Tectonicas")["runs"]),
                         (None, "aboard", 2))
        self.assertEqual(len(out["regions"]), 42)
        self.assertTrue(all(isinstance(r["completion"], float) for r in out["regions"]))
        self.assertGreater(out["completion_all"], 0)
        for bad in ("99", "0", "x"):
            self.assertEqual(self.state.checklist(bad)[1], 400, bad)
        # the panel: where it can grow, where you sampled it
        sid = row(out, "Stratum Tectonicas")["id"]
        sp, status = self.state.checklist_species(sid)
        self.assertEqual((status, sp["name"]), (200, "Stratum Tectonicas"))
        self.assertEqual(sorted((r["system"], r["state"]) for r in sp["runs"]), [("Near Colonia", "aboard"), ("Near Sol", "lost")])
        self.assertTrue(sp["regions"] and set(sp["regions"].values()) <= {"yes", "parts"})
        self.assertEqual(self.state.checklist_species("$Nope;")[1], 404)
        # Bark Mound's picture: Canonn keys it "bark mounds", as the game names it (the Fable review of 2026-10-10, #2)
        bark, status = self.state.checklist_species("$Codex_Ent_Cone_Name;")
        self.assertEqual(status, 200)
        self.assertTrue(bark["images"] and all(i["url"].startswith("https://") for i in bark["images"].values()))
        # its pictures, linked from Canonn by the codex's names (resources/codex_images.json): one per colour
        self.assertTrue(sp["images"] and all(i["url"].startswith("https://") for i in sp["images"].values()))
        self.assertLessEqual(set(sp["images"]), {c.lower() for c, _ in outrider.checklist.colours(
            next(s for s in outrider.bio.load_rules()["species"] if s["name"] == "Stratum Tectonicas"))})
        # the geology checklist (the shipped resources/geo_codex.json), from your codex entries by entry id
        self.db.execute("INSERT INTO codex (ts, entry_id, name, region, system) VALUES ('2026-01-01T00:06:00Z', 1400258,"
                        " 'Water Ice Geyser', 'Inner Orion Spur', 1)")
        self.db.commit()
        geo, status = self.state.checklist(kind="geo")
        self.assertEqual((status, geo["kind"], geo["region"]), (200, "geo", 18))
        self.assertEqual(row(geo, "Water Ice Geyser")["state"], "logged")
        self.assertGreater(row(geo, "Water Ice Geyser")["sites"], 0)
        self.assertGreater(geo["summary"]["completion"], 0)
        one, status = self.state.checklist_geo("1400258")
        self.assertEqual((status, one["name"], [r["system"] for r in one["runs"]]), (200, "Water Ice Geyser", ["Near Sol"]))
        self.assertTrue(one["image"]["url"].startswith("https://"))
        self.assertEqual(self.state.checklist_geo("1")[1], 404)
        self.assertEqual(self.state.checklist(kind="x")[1], 400)

    def test_picture_list_refreshed_from_canonn(self):
        """The checklists' picture links: fetched from Canonn's codex reference into data/ (here a scratch file), used
        over the shipped list; an answer of a changed shape (too few entries) changes nothing; a damaged copy falls back
        to the shipped list."""
        import asyncio
        import outrider.codex_images as ci
        from support import _HwSession
        ref = {str(i): {"hud_category": "Biology", "english_name": f"Test Species {i} - Teal",
                        "image_url": f"https://example.org/{i}.jpg", "image_cmdr": "Tester"} for i in range(ci.MIN_ENTRIES)}
        ref["x"] = {"hud_category": "Stars", "english_name": "A star", "image_url": "https://example.org/s.jpg"}   # not ours
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(200, ref)])
        self.state.spansh = sp
        shipped = self.state.codex_images()
        self.assertIn("water ice geyser", shipped)                     # the shipped list to begin with
        self.assertTrue(asyncio.run(self.state.refresh_codex_images()))
        self.assertEqual(sp.session.calls[0][0], ci.REF)
        now = self.state.codex_images()
        self.assertEqual((len(now), now["test species 7 - teal"]), (ci.MIN_ENTRIES, ["https://example.org/7.jpg", "Tester"]))
        self.assertLess(ci.cache_age(), 60)
        sp.session = _HwSession([(200, {"1": ref["1"]})])            # a changed shape: refused, the list kept
        with self.assertRaises(ValueError):
            asyncio.run(self.state.refresh_codex_images())
        self.assertEqual(len(self.state.codex_images()), ci.MIN_ENTRIES)
        with open(ci.CACHE, "w") as f:
            f.write("{not json")
        self.assertEqual(ci.load(), shipped)                            # a damaged copy: the shipped list
        import os
        os.remove(ci.CACHE)
        self.assertIsNone(ci.cache_age())

    def test_endpoint(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.get("/api/checklist?region=all")
                return r.status, (await r.json())["summary"]["possible"]
        status, possible = asyncio.run(go())
        self.assertEqual(status, 200)
        self.assertGreater(possible, 100)


if __name__ == "__main__":
    unittest.main()
