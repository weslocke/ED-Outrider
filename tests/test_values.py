"""Unit tests: Body and data values, exobiology predictions, sales, the ledger and first discoveries.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import datetime as dt
import json
import os
import time
import unittest
import unittest.mock
import sqlite3

from support import (  # also puts the repository root on sys.path
    ARGS, BIO_M_SYSTEM, CANDS, Q, T, _FakeResponse, death, org, sale, scan, types_ns, voice_honk, voice_jump,
    voice_planet,
)
import outrider.bio  # noqa: E402
import outrider.materials  # noqa: E402
import ed_outrider  # noqa: E402
import outrider.unsold  # noqa: E402


class UnsoldEstimate(unittest.TestCase):
    def test_partial_sale_keeps_unsold_systems(self):
        ev = [scan("2026-01-01T00:00:00Z", "A", 1, 0, "A", star=True), scan("2026-01-01T00:00:00Z", "B", 2, 0, "B", star=True),
              sale("2026-01-02T00:00:00Z", ["A"])]
        ex = outrider.unsold.analyse(ev, ARGS)["exploration"]
        self.assertEqual({r["system"] for r in ex["rows"]}, {"B"})

    def test_ship_loss_before_sale_is_lost_but_rescan_counts(self):
        ev = [scan("2026-01-01T00:00:00Z", "A", 1, 0, "A", star=True)] + death("2026-01-02T00:00:00Z") + \
             [sale("2026-01-03T00:00:00Z", ["A"]), scan("2026-01-04T00:00:00Z", "A", 1, 0, "A", star=True)]
        ex = outrider.unsold.analyse(ev, ARGS)["exploration"]
        self.assertEqual([r["system"] for r in ex["rows"]], ["A"])
        self.assertTrue(ex["rows"][0]["first_discovered"])

    def test_on_foot_death_keeps_ship_data(self):
        ev = [scan("2026-01-01T00:00:00Z", "A", 1, 0, "A", star=True)] + death("2026-01-02T00:00:00Z", "recover")
        self.assertEqual(outrider.unsold.analyse(ev, ARGS)["exploration"]["bodies"], 1)

    def test_crew_cut_only_from_sales_with_same_crew(self):
        stats = lambda ts, hired, fired: (T(ts), None, {"event": "Statistics", "timestamp": ts,
                                                         "Crew": {"NpcCrew_Hired": hired, "NpcCrew_Fired": fired}})
        cut = (T("2026-01-02T00:00:00Z"), None, {"event": "MultiSellExplorationData", "timestamp": "2026-01-02T00:00:00Z",
                                                  "TotalEarnings": 910, "BaseValue": 1000, "Bonus": 0, "Discovered": []})
        ev = [stats("2026-01-01T00:00:00Z", 1, 0), cut, stats("2026-02-01T00:00:00Z", 1, 1)]
        ex = outrider.unsold.analyse(ev, ARGS)["exploration"]
        self.assertEqual(ex["npc_crew"], 0)
        self.assertEqual(ex["payout_ratio"], 1.0)
        ev = [stats("2026-01-01T00:00:00Z", 1, 0), cut]
        self.assertAlmostEqual(outrider.unsold.analyse(ev, ARGS)["exploration"]["payout_ratio"], 0.91)

    def test_mapping_before_the_system_is_named_is_sold_with_it(self):   # F36
        saa = lambda ts: (T(ts), None, {"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": 1, "BodyID": 7,
                                        "BodyName": "Asgara 7", "ProbesUsed": 4, "EfficiencyTarget": 6})
        for first in ("Detailed", "NavBeaconDetail"):
            sc = scan("2026-01-01T00:05:00Z", "Asgara", 1, 7, "Asgara 7")
            sc[2]["ScanType"] = first
            ev = [saa("2026-01-01T00:00:00Z"), sc, sale("2026-01-02T00:00:00Z", ["Asgara"])]
            ex = outrider.unsold.analyse(ev, ARGS)["exploration"]
            self.assertEqual((ex["rows"], ex["mapped"]), ([], 0), first)
        # still aboard when no sale named it; and never named at all: not counted either way
        ex = outrider.unsold.analyse([saa("2026-01-01T00:00:00Z"), scan("2026-01-01T00:05:00Z", "Asgara", 1, 7, "Asgara 7")], ARGS)["exploration"]
        self.assertEqual(ex["mapped"], 1)
        self.assertEqual(outrider.unsold.analyse([saa("2026-01-01T00:00:00Z")], ARGS)["exploration"]["mapped"], 0)

    def test_calibrate_filters_the_sales_by_commander_too(self):   # Codex F8
        import argparse, contextlib, io
        who = lambda e, c: (e[0], c, e[2])
        alice = [who(sale("2026-01-01T00:00:00Z", []), "Alice"),
                 who(scan("2026-01-02T00:00:00Z", "A", 1, 0, "A", star=True), "Alice"),
                 who(sale("2026-01-03T00:00:00Z", ["A"]), "Alice")]
        bob = [who(sale("2026-01-03T00:01:00Z", ["A"]), "Bob")]   # within the five minutes of Alice's sale
        args = argparse.Namespace(**dict(vars(ARGS), commander="Alice"))

        def aggregate(events):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                outrider.unsold.calibrate(sorted(events, key=lambda e: e[0]), args)
            return next(line for line in out.getvalue().splitlines() if line.startswith("AGGREGATE")).split()
        self.assertEqual(aggregate(alice + bob), aggregate(alice))   # Bob's sale is not in Alice's batch
        self.assertEqual(aggregate(alice)[1], "1,000")

    def test_journal_dirs_env_override(self):
        os.environ["ED_JOURNALS"] = os.pathsep.join([os.getcwd(), "/nonexistent/xyz"])
        try:
            live, legacy = outrider.unsold.find_journal_dirs()
        finally:
            del os.environ["ED_JOURNALS"]
        self.assertEqual(live, [os.getcwd()])


class FirstsAndRings(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)

    def first(self, ts, bid, name, disc, mapped, main=0):
        self.db.execute("INSERT INTO own_firsts (system, body_id, name, is_main, was_discovered, was_mapped, was_footfalled, first_ts, undisc_ts) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(system, body_id) DO UPDATE SET "
                        "undisc_ts=coalesce(excluded.undisc_ts, undisc_ts)",
                        (1, bid, name, main, int(disc), int(mapped), None, ts, None if disc else ts))

    def test_rescan_after_loss_is_unsold_per_body(self):
        self.first("T1", 0, "Sys", False, True, main=1); self.first("T1", 1, "Sys 1", False, True)
        self.db.execute("INSERT INTO deaths VALUES ('T2', 'rebuy')")
        self.first("T3", 0, "Sys", False, True, main=1)
        f = ed_outrider.own_firsts(self.db, 1, "Sys")
        self.assertEqual(f["system_state"], "unsold")
        self.assertEqual(f["bodies_by"], {"sold": 0, "unsold": 1, "lost": 1})

    def test_partial_sale_headline(self):
        self.first("T1", 0, "Sys", False, True, main=1)
        self.db.execute("INSERT INTO sales VALUES ('Sys', 'T2', 1)")
        self.first("T3", 2, "Sys 2", True, False)
        self.db.execute("INSERT INTO own_mapped (system, body_id, ts) VALUES (1, 2, 'T3')")
        f = ed_outrider.own_firsts(self.db, 1, "Sys")
        self.assertEqual((f["system_state"], f["sale"]), ("sold", "unsold"))

    def test_lone_star_ring_name(self):
        self.assertEqual(ed_outrider.split_ring_name("Sys", "Sys A Ring"), ("Sys", "A Ring"))
        self.assertEqual(ed_outrider.split_ring_name("Sys", "Sys 3 B Ring"), ("3", "B Ring"))

    def test_organic_state(self):
        self.db.execute("INSERT INTO deaths VALUES ('T2', 'rebuy')")
        self.db.execute("INSERT INTO bio_sales (ts, species) VALUES ('T4', 3)")   # no BioData kept: sells every run
        self.assertEqual(ed_outrider.organic_state(self.db, "T1"), "lost")
        self.assertEqual(ed_outrider.organic_state(self.db, "T3"), "sold")
        self.assertEqual(ed_outrider.organic_state(self.db, "T5"), "aboard")

    def test_ring_density(self):
        r = ed_outrider.ring_stats([{"name": "A Ring", "type": "Rocky", "mass": 1000.0, "inner": 1000.0, "outer": 2000.0}])[0]
        self.assertEqual(r["width_km"], 1)
        self.assertAlmostEqual(r["density"], 1000.0 / (3.141592653589793 * 3e6 / 1e6), places=3)


class BioNames(unittest.TestCase):
    """Spelling normalisation needs no downloaded rules."""

    def test_atmosphere_and_volcanism_spellings(self):
        self.assertEqual(outrider.bio.norm_atmosphere("Hot thin Sulphur dioxide"), "sulphurdioxide")
        self.assertEqual(outrider.bio.norm_atmosphere("CarbonDioxideRich"), "carbondioxiderich")
        self.assertEqual(outrider.bio.norm_atmosphere(None), "none")
        self.assertEqual(outrider.bio.norm_volcanism("Major Rocky Magma"), "major rocky magma volcanism")
        self.assertEqual(outrider.bio.norm_volcanism("No volcanism"), "")
        self.assertEqual(outrider.bio.journal_class("High metal content world"), "High metal content body")
        self.assertEqual(outrider.bio.journal_class("Earth-like world"), "Earthlike body")

    def test_star_codes(self):
        for name, code in [("M (Red dwarf) Star", "M"), ("M (Red giant) Star", "M_RedGiant"),
                           ("K (Yellow-Orange giant) Star", "K_OrangeGiant"), ("White Dwarf (DA) Star", "DA"),
                           ("Wolf-Rayet N Star", "WN"), ("Neutron Star", "N"), ("Black Hole", "H"),
                           ("Herbig Ae/Be Star", "AeBe"), ("T Tauri Star", "TTS"), ("DA", "DA"), ("M_RedGiant", "M_RedGiant")]:
            self.assertEqual(outrider.bio.star_code(name), code, name)
        self.assertTrue(outrider.bio.star_matches("M", "M_RedGiant"))
        self.assertTrue(outrider.bio.star_matches("D", "DAB"))
        self.assertFalse(outrider.bio.star_matches("K", "M"))
        self.assertTrue(outrider.bio.luminosity_matches("V", "Vab"))
        self.assertFalse(outrider.bio.luminosity_matches("V", "IV"))


@unittest.skipUnless(outrider.bio.available(), "bio_rules.json not downloaded (python3 -m outrider.bio --update-rules)")
class BioRules(unittest.TestCase):
    """Against the downloaded BioScan rules: the things a wrong evaluator would get wrong."""
    M_SYSTEM = BIO_M_SYSTEM

    def names(self, body, system=None):
        return [s["name"] for s in outrider.bio.predict(body, system or self.M_SYSTEM)]

    def test_icy_argon_is_bacterium_and_fonticulua_only(self):
        n = self.names({"class": "Icy body", "atmosphere": "Argon", "gravity": 0.2, "temperature": 80, "parents": ["M"]})
        self.assertIn("Fonticulua Campestris", n)
        self.assertNotIn("Tussock Capillum", n)
        self.assertNotIn("Osseus Pumice", n)
        self.assertFalse([x for x in n if x.startswith("Electricae")], "Electricae need an A/N/D/H parent star")

    def test_spansh_two_prefix_atmosphere(self):
        # every body known (F20: until then an unscanned companion star could still be the hot one)
        n = self.names({"class": "Rocky body", "atmosphere": "Hot thin Sulphur dioxide", "gravity": 0.3, "temperature": 420},
                       dict(self.M_SYSTEM, complete=True))
        self.assertIn("Bacterium Tela", n)
        self.assertNotIn("Prasinum Bioluminescent Anemone", n, "anemones want a hot star")

    def test_tubus_needs_low_gravity(self):
        base = {"class": "Rocky body", "atmosphere": "CarbonDioxide", "temperature": 170}
        self.assertIn("Tubus Compagibus", self.names(dict(base, gravity=0.1)))
        self.assertNotIn("Tubus Compagibus", self.names(dict(base, gravity=0.2)))

    def test_brain_trees_only_near_guardian_nebulae(self):
        body = {"class": "Rocky body", "atmosphere": "None", "gravity": 0.2, "temperature": 300,
                "volcanism": "minor metallic magma volcanism"}
        near = {"x": -840, "y": -561, "z": 13361, "stars": [{"type": "K", "main": True}], "planet_types": ["Water world"]}
        self.assertIn("Roseum Brain Tree", self.names(body, near))
        self.assertNotIn("Roseum Brain Tree", self.names(body))

    def test_regions(self):
        self.assertEqual(outrider.bio.region_name(0, 0, 0), "Inner Orion Spur")
        self.assertEqual(outrider.bio.region_name(-9530.5, -910.3, 19808.1), "Inner Scutum-Centaurus Arm")
        self.assertIsNone(outrider.bio.region_number(90000, 0, 0))

    def test_unruled_genus_still_priced(self):
        val, groups = outrider.bio.potential([], genera=["Crystalline Shards"])
        self.assertGreater(val, 1_000_000)
        self.assertTrue(groups[0]["unruled"])


class Samples(unittest.TestCase):
    """Batch 1: the Samples view's states, first-footfall factor and totals."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, None, 25)
        now = dt.datetime.now(dt.timezone.utc)
        self.t = lambda h: (now - dt.timedelta(hours=100 - h)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def sample_run(self, h, system, body, sp):
        for i, k in enumerate(("Log", "Sample", "Analyse")):
            self.j.handle(org(self.t(h + i * 0.01), system, body, sp, k))

    def test_states_factor_totals(self):
        s = scan(self.t(0), "Sys", 1, 5, "Sys 5")[2]; s["WasFootfalled"] = False
        self.j.handle(s)
        self.j.handle({"event": "FSDJump", "timestamp": self.t(0), "StarSystem": "Sys", "SystemAddress": 1, "StarPos": [0, 0, 0]})
        self.sample_run(1, 1, 5, "Bacterial_01")                     # sold below
        self.j.handle({"event": "SellOrganicData", "timestamp": self.t(2), "BioData": [{"Species": "$Codex_Ent_Bacterial_01;", "Value": 1, "Bonus": 0}]})
        self.sample_run(3, 1, 6, "Bacterial_02")                     # lost below
        self.j.handle({"event": "Died", "timestamp": self.t(4)}); self.j.handle({"event": "Resurrect", "timestamp": self.t(4), "Option": "rebuy"})
        self.sample_run(5, 1, 7, "Bacterial_03")                     # aboard
        self.j.handle(org(self.t(6), 1, 8, "Bacterial_04", "Log"))   # in progress
        o = self.state.organics(30)
        by = {r["body"]: r for r in o["rows"]}
        self.assertEqual(by["5"]["state"], "sold")
        self.assertEqual(by["5"]["factor"], 5)
        self.assertEqual(by["body #6"]["state"], "lost")
        self.assertEqual(by["body #7"]["state"], "aboard")
        self.assertEqual(by["body #8"]["state"], "in progress")
        self.assertEqual(o["counts"], {"aboard": 1, "sold": 1, "lost": 1, "in progress": 1})
        self.assertEqual(by["5"]["system"]["name"], "Sys")
        if outrider.bio:
            self.assertEqual(o["totals"]["sold"], by["5"]["value"])


class HeaderAndTotals(unittest.TestCase):
    """Batch 2: commander, position details and the all-time history row."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, None, 25)

    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def test_payload_fields(self):
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:00Z", "Commander": "Jameson", "Credits": 1000})
        self.jump("2026-01-01T00:01:00Z", 1, 0); self.jump("2026-01-01T00:02:00Z", 2, 10); self.jump("2026-01-01T00:03:00Z", 1, 0)
        p = self.state.payload()
        self.assertEqual(p["commander"]["name"], "Jameson")
        self.assertEqual(p["commander"]["credits"], 1000)
        self.assertEqual(p["position"]["visits"], 2)
        self.assertIsNone(p["materials"])

    def test_exact_string_ids(self):   # F57: an id64 above 2^53 is rounded by a JavaScript number
        big = 2 ** 53 + 1
        self.jump("2026-01-01T00:01:00Z", big + 2, 0); self.jump("2026-01-01T00:02:00Z", big, 10)
        self.state.target = {"id64": big + 4, "name": "T", "status": "unreported", "seq": 1}
        p = self.state.payload()
        self.assertEqual((p["position"]["id"], p["previous"]["id"], p["target"]["id"]),
                         (str(big), str(big + 2), str(big + 4)))
        self.assertEqual(p["position"]["id64"], big)            # the number stays for what already uses it
        read = p["freshness"]["read"]
        self.j.offsets["/j/Journal.2026-01-01T000000.01.log"] = 1234
        self.assertEqual(self.state.payload()["freshness"]["read"], read + 1234)   # moves with every line read

    def test_all_time_equals_sum_of_sessions(self):
        for i, ts in enumerate(("2020-01-01T00:00:00Z", "2020-01-01T00:10:00Z", "2020-01-01T00:20:00Z",
                                "2020-02-01T00:00:00Z", "2020-02-01T00:30:00Z")):
            self.jump(ts, i + 1, i * 7)
        h = self.state.history(3650 * 3)
        self.assertEqual(len(h["sessions"]), 2)
        self.assertEqual(h["all_time"]["jumps"], sum(s["jumps"] for s in h["sessions"]))
        self.assertAlmostEqual(h["all_time"]["ly"], sum(s["ly"] for s in h["sessions"]), places=1)
        self.assertEqual(h["all_time"]["since"], "2020-01-01T00:00:00Z")
        # a short window still reports everything in the all-time row
        self.assertEqual(self.state.history(1)["all_time"]["jumps"], 5)


class Highlights(unittest.TestCase):
    def test_highlight_settings(self):
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual((st["body_highlight"], st["bio_highlight"]), (500_000, 10_000_000))
        st = ed_outrider.settings_from({"defaults": {"body_highlight_level": 750000, "biology_highlight_value": 5000000}},
                                       args, None, ([], []))
        self.assertEqual((st["body_highlight"], st["bio_highlight"]), (750_000, 5_000_000))
        import tomllib
        back = tomllib.loads(ed_outrider.config_text(st))["defaults"]
        self.assertEqual((back["body_highlight_level"], back["biology_highlight_value"]), (750_000, 5_000_000))
        self.assertTrue(st["max_include_bonus"])
        st = ed_outrider.settings_from({"defaults": {"body_max_value_include_bonus": False}}, args, None, ([], []))
        self.assertFalse(st["max_include_bonus"])
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["defaults"]["body_max_value_include_bonus"], False)


class BioSearch(unittest.TestCase):
    """Search: bodies with bio you have not finished, by what the rest could pay."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)

    def test_finished_bodies_drop_out_and_threshold_applies(self):
        recs = [{"name": "1", "type": "Planet", "subtype": "Rocky body", "body_id": 1, "bio": 1},
                {"name": "2", "type": "Planet", "subtype": "Rocky body", "body_id": 2, "bio": 2}]
        # body 1: its one species analysed; body 2: one of two analysed
        for bid, g in ((1, "Bacterium"), (2, "Stratum")):
            self.db.execute("INSERT INTO own_organic (system, body_id, species, genus_name, species_name, samples, done_ts, ts) "
                            "VALUES (9, ?, 'x', ?, 'y', 3, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')", (bid, g))
        hits = ed_outrider.bio_hits(self.db, 9, "Sys", 0, 0, 0, recs, 0)
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]["t"].startswith("2 · 1 of 2 unscanned"))
        self.assertEqual(hits[0]["body"], "2")
        # an unpriceable remainder never passes a credit threshold
        with unittest.mock.patch.object(ed_outrider, "bio_guess", return_value=(None, [])):
            self.assertEqual(ed_outrider.bio_hits(self.db, 9, "Sys", 0, 0, 0, recs, 1_000_000), [])
            self.assertEqual(len(ed_outrider.bio_hits(self.db, 9, "Sys", 0, 0, 0, recs, 0)), 1)


class SpanshGenera(unittest.TestCase):
    def test_dump_genera_as_codes_or_objects(self):
        b = {"name": "Sys 1", "type": "Planet", "subType": "Rocky body",
             "signals": {"genuses": ["$Codex_Ent_Bacterial_Genus_Name;", {"name": "Stratum"}]}}
        self.assertEqual(ed_outrider.record_from_dump("Sys", b)["genera"], ["Bacterium", "Stratum"])


class Curiosities(unittest.TestCase):
    def test_flags(self):
        star = {"name": "A", "type": "Star", "radius_km": 700000, "body_id": 0}
        hot = {"name": "1", "type": "Planet", "subtype": "Class I gas giant", "sma_ls": 20, "radius_km": 70000}
        self.assertIn("hot Jupiter", [t for t, _ in ed_outrider.curiosities(hot, star)])
        ringed = {"name": "2", "type": "Planet", "subtype": "Icy body", "landable": True, "gravity": 3.5, "radius_km": 2000,
                  "ring_details": [{"name": "A Ring", "inner": 3e6, "outer": 30e6}], "rings": 1}
        tags = [t for t, _ in ed_outrider.curiosities(ringed)]
        self.assertEqual(set(tags), {"ringed landable", "high g", "wide rings"})
        moon = {"name": "3 a a", "type": "Planet", "parents_full": [{"kind": "Planet", "id": 5}, {"kind": "Planet", "id": 4}]}
        self.assertEqual([t for t, _ in ed_outrider.curiosities(moon)], ["moon of a moon"])
        spin = {"name": "4", "type": "Planet"}
        self.assertEqual([t for t, _ in ed_outrider.curiosities(spin, raw={"RotationPeriod": 3600, "TidalLock": False})], ["fast spin"])
        self.assertEqual(ed_outrider.curiosities({"name": "5", "type": "Planet", "subtype": "Rocky body"}), [])

    def test_system_pair_not_close_orbit(self):
        # two planets round a barycentre that circles the star: a pair, and never a "close orbit" of the star
        # (their small orbit is around the shared centre, not the star's surface)
        star = {"name": "A", "type": "Star", "radius_km": 700000, "body_id": 1, "parents_full": []}
        via = [{"kind": "Null", "id": 7}, {"kind": "Star", "id": 1}]
        p5 = {"name": "5", "type": "Planet", "body_id": 8, "sma_ls": 1.0, "radius_km": 3000, "parents_full": via}
        p6 = {"name": "6", "type": "Planet", "body_id": 9, "sma_ls": 1.0, "radius_km": 3000, "parents_full": via}
        moon = {"name": "6 a", "type": "Planet", "body_id": 10, "sma_ls": 0.02,
                "parents_full": [{"kind": "Planet", "id": 9}] + via}
        got = ed_outrider.system_curiosities("S", [star, p5, p6, moon])
        self.assertEqual([t for t, _ in got["5"]], ["planet pair"])
        self.assertEqual([t for t, _ in got["6"]], ["planet pair"])
        self.assertEqual([t for t, _ in got["6 a"]], ["close orbit"])   # 6 a really does hug planet 6
        # a star sharing the centre stops it being a planet pair
        s2 = {"name": "B", "type": "Star", "body_id": 11, "parents_full": [{"kind": "Null", "id": 7}]}
        self.assertNotIn("5", ed_outrider.system_curiosities("S", [star, p5, s2]))


class BioColours(unittest.TestCase):
    """BioScan's colour check (a species needs a colour variant for its star or materials) and the
    undecided-genus options shown before the DSS."""

    def test_colour_ok(self):
        stratum = {"star": {"F": "Emerald", "K": "Lime", "M": "Green", "Ae": "Teal"}}
        b = lambda parents, mats=None: {"parents": parents, "materials": mats}
        s = lambda main, n=1, complete=True: {"main": {"type": main} if main else None, "stars": [{}] * n, "complete": complete}
        self.assertFalse(outrider.bio._colour_ok(stratum, b(["G"]), s("G")))         # never seen at a G star
        self.assertTrue(outrider.bio._colour_ok(stratum, b(["K_OrangeGiant"]), s("G")))   # giant variants count
        self.assertTrue(outrider.bio._colour_ok(stratum, b(["G"]), s("M")))          # the main star counts too
        self.assertTrue(outrider.bio._colour_ok(stratum, b(["AeBe"]), s("AeBe")))    # Ae is the journal's AeBe
        self.assertTrue(outrider.bio._colour_ok(stratum, b(None), s("G", 2)))        # parents unknown, 2 stars: no call
        self.assertFalse(outrider.bio._colour_ok(stratum, b(None), s("G", 1)))       # one star: it must be that one
        self.assertTrue(outrider.bio._colour_ok(stratum, b(None), s("G", 1, False)))  # one star known, others may be (F39)
        self.assertTrue(outrider.bio._colour_ok(stratum, b(["G"]), s("H")))          # black hole primary: no call
        fung = {"element": {"polonium": "Yellow", "tin": "Grey"}}
        self.assertTrue(outrider.bio._colour_ok(fung, b(["G"], None), s("G")))       # materials unknown: no call
        self.assertFalse(outrider.bio._colour_ok(fung, b(["G"], {"iron", "nickel"}), s("G")))
        self.assertTrue(outrider.bio._colour_ok(fung, b(["G"], {"iron", "tin"}), s("G")))
        self.assertTrue(outrider.bio._colour_ok(None, b(["G"]), s("G")))            # no colour table: no check

    def test_variant_names(self):   # P11: the colour variant, a candidate set that is [] whenever unsure
        aur = {"name": "Bacterium Aurasus", "colors": {"star": {"K": "Teal", "M": "Green", "F": "Lime", "Y": "Mauve"}}}
        b = lambda parents, mats=None: {"parents": parents, "materials": mats}
        s = lambda *types, complete=True: {"main": {"type": types[0]} if types else None, "complete": complete,
                                           "stars": [{"type": t} for t in types]}
        v = outrider.bio.variant_names
        self.assertEqual(v(aur, b(["K"]), s("K")), ["Bacterium Aurasus - Teal"])           # K parent
        self.assertEqual(v(aur, b(["K_OrangeGiant"]), s("K_OrangeGiant")), ["Bacterium Aurasus - Teal"])
        self.assertEqual(v(aur, b([None]), s("K")), [])                  # nearest parent not a known star
        self.assertEqual(v(aur, b([]), s("K")), [])                      # only barycentres above it
        self.assertEqual(v(aur, b(None), s("K")), ["Bacterium Aurasus - Teal"])   # complete, one star: that one
        self.assertEqual(v(aur, b(None), s("K", "M")), [])               # parents unknown, two stars
        self.assertEqual(v(aur, b(["K"]), s("K", complete=False)), [])   # a star not found yet may colour it
        # another star could give another colour: in the journals a Y dwarf's moons took the F star's colour
        self.assertEqual(v(aur, b(["Y"]), s("F", "Y")), [])
        self.assertEqual(v(aur, b(["K"]), s("K", "G")), ["Bacterium Aurasus - Teal"])   # G gives no colour: no rival
        self.assertEqual(v(aur, b(["K"]), s("K", "K")), ["Bacterium Aurasus - Teal"])   # two K stars agree
        self.assertEqual(v(aur, b(["G"]), s("G")), [])                    # no colour for the parent
        self.assertEqual(v(aur, b(["K"]), s("H", "K")), [])               # black hole primary
        fung = {"name": "Fungoida Setisis", "colors": {"element": {"polonium": "Yellow", "tin": "Grey", "iron": "Red"}}}
        self.assertEqual(v(fung, b(["K"], {"tin", "polonium", "nickel"}), s("K")),
                         ["Fungoida Setisis - Yellow", "Fungoida Setisis - Grey"])   # two materials: two names
        self.assertEqual(v(fung, b(["K"], None), s("K")), [])            # materials unknown
        self.assertEqual(v({"name": "Frutexa Acus", "colors": None}, b(["K"]), s("K")), [])   # no table

    def test_variant_names_real_rules(self):
        # the colour spellings come from ExploData's tables; they match the journal's (e.g. "Ocher", "Grey")
        if not outrider.bio.colours_available():
            self.skipTest("ExploData's colour tables not downloaded (bio_colours.json: python3 -m outrider.bio --update-rules)")
        cols = {c for sp in outrider.bio.load_rules()["species"] for t in (sp.get("colors") or {}).values() for c in t.values()}
        self.assertIn("Ocher", cols)
        self.assertIn("Grey", cols)
        self.assertNotIn("Ochre", cols)
        self.assertNotIn("Gray", cols)

    def test_codex_per_variant(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        db.execute("INSERT INTO codex (ts, entry_id, name, region) VALUES ('t', 1, 'Bacterium Aurasus - Green', 'Inner Orion Spur')")
        known = ed_outrider.codex_species(db, "Inner Orion Spur")
        self.assertEqual(known, ({"bacterium aurasus - green"}, {"bacterium aurasus"}))
        self.assertEqual(ed_outrider.codex_species(db, None), (set(), set()))
        g = {"genus": "Bacterium", "best": "Bacterium Aurasus", "variants": ["Bacterium Aurasus - Teal"]}
        self.assertTrue(ed_outrider.codex_new_group(g, known))            # a new colour of a logged species
        self.assertFalse(ed_outrider.codex_new_group(dict(g, variants=["Bacterium Aurasus - Green"]), known))
        self.assertFalse(ed_outrider.codex_new_group(dict(g, variants=[]), known))   # unsure: species level
        self.assertTrue(ed_outrider.codex_new_group(dict(g, best="Bacterium Vesicula", variants=[]), known))
        self.assertFalse(ed_outrider.codex_new_group(dict(g, best=None, variants=[]), known))
        # the colour the journal logged wins over the guess
        [lg] = ed_outrider.with_logged_variants([g], {"Bacterium": "Bacterium Aurasus - Green"})
        self.assertEqual((lg["variants"], lg["variant"]), (["Bacterium Aurasus - Green"], "Bacterium Aurasus - Green"))
        self.assertFalse(ed_outrider.codex_new_group(lg, known))
        self.assertIs(ed_outrider.with_logged_variants([g], {})[0], g)

    def test_codex_have_names_logged_colours(self):
        # Smojooe AR-E b25-4, 2026-09-30: Acies - Lime and - Aquamarine logged in the Inner Orion Spur, body 6's
        # tellurium predicts White: its ✦ is right, and the tooltip says which colours you already have
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        db.executemany("INSERT INTO codex (ts, entry_id, name, region) VALUES ('t', ?, ?, ?)",
                       [(2320401, "Bacterium Acies - Lime", "Inner Orion Spur"),
                        (2320406, "Bacterium Acies - Aquamarine", "Inner Orion Spur"),
                        (2320407, "Bacterium Acies - White", "Norma Arm"),        # another region: not yours here
                        (2320201, "Bacterium Aurasus - Teal", "Inner Orion Spur")])
        known = ed_outrider.codex_species(db, "Inner Orion Spur")
        g = {"genus": "Bacterium", "best": "Bacterium Acies", "variants": ["Bacterium Acies - White"]}
        self.assertTrue(ed_outrider.codex_new_group(g, known))
        self.assertEqual(ed_outrider.codex_have(g, known), ["Aquamarine", "Lime"])
        self.assertEqual(ed_outrider.codex_have(dict(g, best="Bacterium Vesicula"), known), [])
        self.assertEqual(ed_outrider.codex_have(dict(g, best=None), known), [])
        self.assertEqual(ed_outrider.codex_have(g, ed_outrider.codex_species(db, None)), [])

    def test_codex_new_anywhere(self):
        """Plugin gaps C (BioScan's 🌌 against its 📝): a colour logged in another region is still new HERE (✦) but not
        new anywhere; one in no region at all is new anywhere (✪)."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        db.executemany("INSERT INTO codex (ts, entry_id, name, region) VALUES ('t', ?, ?, ?)",
                       [(2320407, "Bacterium Acies - White", "Norma Arm"), (2320201, "Bacterium Aurasus - Teal", "Inner Orion Spur")])
        here, anywhere = ed_outrider.codex_species(db, "Inner Orion Spur"), ed_outrider.codex_species_all(db)
        acies = {"genus": "Bacterium", "best": "Bacterium Acies", "variants": ["Bacterium Acies - White"]}
        vesicula = {"genus": "Bacterium", "best": "Bacterium Vesicula", "variants": []}
        self.assertEqual([ed_outrider.codex_new_group(g, here) for g in (acies, vesicula)], [True, True])
        self.assertEqual([ed_outrider.codex_new_group(g, anywhere) for g in (acies, vesicula)], [False, True])

    def test_by_genus_carries_variants(self):
        cands = [{"name": "Bacterium Aurasus", "genus": "Bacterium", "value": 1000000, "variants": ["Bacterium Aurasus - Teal"]},
                 {"name": "Bacterium Vesicula", "genus": "Bacterium", "value": 500000, "variants": []}]
        [g] = outrider.bio.by_genus(cands)
        self.assertEqual((g["variants"], g["variant"]), (["Bacterium Aurasus - Teal"], "Bacterium Aurasus - Teal"))
        self.assertEqual(outrider.bio.by_genus(cands, ["Stratum"])[0]["variants"], [])   # unruled genus

    def test_options(self):
        cands = [{"name": "Stratum Tectonicas", "genus": "Stratum", "value": 19010800},
                 {"name": "Bacterium Aurasus", "genus": "Bacterium", "value": 1000000}]
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=cands):
            r = {"type": "Planet", "bio": 1}
            o = ed_outrider.bio_options(r)
            self.assertEqual((o["low"], o["high"], [g["genus"] for g in o["genera"]]),
                             (1000000, 19010800, ["Stratum", "Bacterium"]))
            self.assertIsNone(ed_outrider.bio_options(dict(r, bio=2)))   # two signals, two genera: both are there
            self.assertIsNone(ed_outrider.bio_options(dict(r, bio=0)))
            # F27: a genus sampled without a DSS takes one signal and is no longer an option
            cands.append({"name": "Fungoida Setisis", "genus": "Fungoida", "value": 1500000})
            o = ed_outrider.bio_options(dict(r, bio=2), known={"Stratum"})
            self.assertEqual((o["low"], o["high"], [g["genus"] for g in o["genera"]]),
                             (1000000, 1500000, ["Fungoida", "Bacterium"]))
            self.assertIsNone(ed_outrider.bio_options(dict(r, bio=2), known={"Stratum", "Bacterium"}))   # all known


class SampleSpacing(unittest.TestCase):
    """Batch 6: positions are recorded live and the distance to go counts down as you walk."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def at(self, ts, lat, lon):
        self.j.status_json = {"live": True, "ts": ts, "fuel_main": 10, "flags": 0, "flags2": 1, "body": "Sys 4",
                              "lat": lat, "lon": lon, "planet_radius": 1_000_000}

    def organic(self, ts, kind):
        self.j.handle({"event": "ScanOrganic", "timestamp": ts, "SystemAddress": 1, "Body": 4, "ScanType": kind,
                       "Genus": "$Codex_Ent_Tussocks_Genus_Name;", "Genus_Localised": "Tussock",
                       "Species": "$Codex_Ent_Tussocks_01_Name;", "Species_Localised": "Tussock Pennata"})

    def test_countdown(self):
        self.at("2026-01-01T00:10:00Z", 0.0, 0.0)
        self.organic("2026-01-01T00:10:00Z", "Log")
        s = self.state.sampling_summary()
        self.assertEqual((s["need"], s["to_go"], s["clear"]), (200, 200, False))
        # 0.009 degrees on a 1,000 km body is about 157 m: 43 m still to go
        self.at("2026-01-01T00:11:00Z", 0.0, 0.009)
        s = self.state.sampling_summary()
        self.assertEqual((s["nearest"], s["to_go"], s["clear"]), (157, 43, False))
        self.at("2026-01-01T00:12:00Z", 0.0, 0.012)
        self.assertTrue(self.state.sampling_summary()["clear"])
        self.organic("2026-01-01T00:12:00Z", "Sample")                   # the second sample: now measured from both
        self.at("2026-01-01T00:13:00Z", 0.0, 0.006)                      # back between them
        self.assertFalse(self.state.sampling_summary()["clear"])
        self.organic("2026-01-01T00:20:00Z", "Analyse")
        self.assertIsNone(self.state.sampling_summary())                  # run complete

    def codex(self, ts, variant="$Codex_Ent_Tussocks_01_A_Name;", name="Tussock Pennata - Teal", lat=None, lon=None):
        ev = {"event": "CodexEntry", "timestamp": ts, "EntryID": 2310101, "Name": variant, "Name_Localised": name,
              "Category": "$Codex_Category_Biology;", "SubCategory": "$Codex_SubCategory_Organic_Structures;",
              "Region": "$Codex_RegionName_18;", "System": "Sys", "SystemAddress": 1, "BodyID": 4}
        if lat is not None:
            ev.update(Latitude=lat, Longitude=lon)
        self.j.handle(ev)

    def test_tagged_plants(self):
        """BioScan's waypoints (plugin gaps B): a plant tagged with the composition scanner is where to go for the next
        sample. On foot the codex entry carries its position; from the ship or SRV it doesn't, so yours at that moment
        is taken. The nearest one far enough from the run's samples is pointed to, with the turn to face it."""
        self.j.handle({"event": "Scan", "timestamp": "2026-01-01T00:05:00Z", "BodyName": "Sys 4", "BodyID": 4,
                       "StarSystem": "Sys", "SystemAddress": 1, "PlanetClass": "Rocky body", "Landable": True,
                       "MassEM": 0.1, "ScanType": "Detailed", "WasDiscovered": False, "WasMapped": False})
        self.at("2026-01-01T00:10:00Z", 0.0, 0.0)
        self.codex("2026-01-01T00:10:00Z", lat=0.0, lon=0.005)            # on foot: 87 m east, its own position
        self.at("2026-01-01T00:10:30Z", 0.0, 0.030)                      # flying low, 524 m east
        self.codex("2026-01-01T00:10:30Z")                               # from the ship: tagged where you are
        self.codex("2026-01-01T00:10:40Z", variant="$Codex_Ent_Bacterial_04_Antimony_Name;", name="Bacterium Acies - Teal")
        self.codex("2026-01-01T00:10:45Z", variant="$Codex_Ent_L_Seed_Pln01_V1_Bl_Name;", name="Brain tree")   # not a sample species
        rows = self.db.execute("SELECT species, genus, name, round(lon, 3) FROM bio_tags ORDER BY ts").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            ("$Codex_Ent_Tussocks_01_Name;", "$Codex_Ent_Tussocks_Genus_Name;", "Tussock Pennata", 0.005),
            ("$Codex_Ent_Tussocks_01_Name;", "$Codex_Ent_Tussocks_Genus_Name;", "Tussock Pennata", 0.03),
            ("$Codex_Ent_Bacterial_04_Name;", "$Codex_Ent_Bacterial_Genus_Name;", "Bacterium Acies", 0.03)])
        self.at("2026-01-01T00:11:00Z", 0.0, 0.0)
        self.j.status_json["heading"] = 0                                # facing north
        self.organic("2026-01-01T00:11:00Z", "Log")                      # the first sample, at the origin
        s = self.state.sampling_summary()
        # the 87 m one is inside the 200 m colony of that sample: the 524 m one is next, east (turn 90 right)
        self.assertEqual((s["tag"]["dist"], s["tag"]["bearing"], s["tag"]["turn"], s["tag"]["way"]), (524, 90, 90, "on your right"))
        h = self.state.surface_here() or {"system": 1, "body_id": 4, "lat": 0.0, "lon": 0.0, "radius": 1_000_000, "heading": 0}
        tags = self.state.bio_tags_here(h)
        self.assertEqual([(t["genus"], t["dist"], t["current"], t["usable"]) for t in tags],
                         [("Tussock", 87, True, False), ("Tussock", 524, True, True), ("Bacterium", 524, False, True)])
        # a journal re-read keeps them (live only: the ship's position could not be rebuilt)
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual(self.db.execute("SELECT count(*) FROM bio_tags").fetchone()[0], 3)
        # the species finished here: its tags go
        self.organic("2026-01-01T00:12:00Z", "Sample")
        self.organic("2026-01-01T00:13:00Z", "Analyse")
        self.assertEqual([t["genus"] for t in self.state.bio_tags_here(h)], ["Bacterium"])

    def test_variantless_species_and_the_logs_own_entry(self):
        """Review of plugin gaps: Brain Trees, Anemones, Tubers... have no number or variant in their codex code, so they
        were never tagged (found by name in the rules now); and the codex entry a first Log writes (the same second)
        is where you sample, not a plant to go to, so it goes when the Log comes."""
        import outrider.bio
        if not outrider.bio.load_rules():
            self.skipTest("no bio_rules.json")
        self.j.handle({"event": "Scan", "timestamp": "2026-01-01T00:05:00Z", "BodyName": "Sys 4", "BodyID": 4,
                       "StarSystem": "Sys", "SystemAddress": 1, "PlanetClass": "Rocky body", "Landable": True,
                       "MassEM": 0.1, "ScanType": "Detailed", "WasDiscovered": False, "WasMapped": False})
        self.at("2026-01-01T00:10:00Z", 0.0, 0.03)
        self.codex("2026-01-01T00:10:00Z", variant="$Codex_Ent_SeedABCD_01_Name;", name="Roseum Brain Tree")
        row = self.db.execute("SELECT species, genus, name FROM bio_tags").fetchone()
        self.assertEqual(tuple(row), ("$Codex_Ent_Seed_Name;", "$Codex_Ent_Brancae_Name;", "Roseum Brain Tree"))
        h = {"system": 1, "body_id": 4, "lat": 0.0, "lon": 0.0, "radius": 1_000_000, "heading": 0}
        [t] = self.state.bio_tags_here(h)
        self.assertEqual((t["genus"], t["dist"], t["usable"]), ("Brain Trees", 524, True))
        # on foot: a first Log writes its codex entry in the same second, just before the ScanOrganic
        self.at("2026-01-01T00:20:00Z", 0.0, 0.0)
        self.codex("2026-01-01T00:20:00Z", lat=0.0, lon=0.0)
        self.organic("2026-01-01T00:20:00Z", "Log")
        self.assertEqual([r[0] for r in self.db.execute("SELECT name FROM bio_tags")], ["Roseum Brain Tree"])

    def test_tag_needs_a_position_of_that_moment(self):
        self.at("2026-01-02T00:00:00Z", 0.0, 0.0)                        # today's reading...
        self.codex("2026-01-01T00:10:00Z")                               # ...is not where yesterday's tag was made
        self.assertEqual(self.db.execute("SELECT count(*) FROM bio_tags").fetchone()[0], 0)

    def test_no_position_from_an_old_line(self):
        self.at("2026-01-02T00:00:00Z", 0.0, 0.0)                         # today's reading...
        self.organic("2026-01-01T00:10:00Z", "Log")                      # ...does not belong to yesterday's sample
        s = self.state.sampling_summary()
        self.assertEqual((s["points"], s["to_go"]), (0, None))


class Batch2Values(unittest.TestCase):
    """Second review, batch 2: values shown or spoken, and the exobiology guesses."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def body(self, name):
        self.db.commit()
        return next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == name)

    def test_rescan_after_sale_adds_only_the_map(self):   # F36
        mapped = lambda ts: (T(ts), None, {"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": 1, "BodyID": 4,
                                           "BodyName": "Sys 4", "ProbesUsed": 5, "EfficiencyTarget": 6})
        ev = [scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4"), sale("2026-01-02T00:00:00Z", ["Sys"]),
              scan("2026-01-03T00:00:00Z", "Sys", 1, 4, "Sys 4")]           # an AutoScan on the way back
        self.assertEqual(outrider.unsold.analyse(ev, ARGS)["exploration"]["rows"], [])
        rows = outrider.unsold.analyse(ev + [mapped("2026-01-03T00:05:00Z")], ARGS)["exploration"]["rows"]
        body = {"PlanetClass": "High metal content body", "MassEM": 1.0, "TerraformState": "", "first_mapped": True}
        self.assertEqual([(r["map_only"], r["value"]) for r in rows],
                         [(True, outrider.unsold.body_value(body, True, False, True) - outrider.unsold.body_value(body, False, False, True))])
        # Here agrees: the rescanned body is sold data, not something on board
        for e in ev:
            self.j.handle(e[2])
        b = self.body("4")
        self.assertEqual((b["value_parts"]["scan_state"], b["value_now"]), ("sold", 0))
        self.assertEqual(b["value_max"], b["value_parts"]["carto_left"])        # only the map is still there to add

    def test_small_body_floor_matches_eddiscovery(self):   # F35: checked, left as the reference has it
        # EDDiscovery's EstimatedValues.cs floors the base value at 500 before the mapping multiplier
        icy = {"PlanetClass": "Icy body", "MassEM": 0.01, "TerraformState": "", "first_discovered": True, "first_mapped": True}
        self.assertEqual(outrider.unsold.planet_base_value(300.0, 0.01), 500.0)
        self.assertEqual(outrider.unsold.body_value(icy, True, False, True), int((500 * 3.699622554 + 555) * 2.6))

    def test_sold_bio_is_not_on_board(self):   # F3
        if not outrider.bio:
            self.skipTest("no rules")
        s = scan("2026-01-01T00:01:00Z", "Sys", 1, 5, "Sys 5")[2]; s["WasFootfalled"] = False
        self.j.handle(s)
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:01:00Z", "SystemAddress": 1, "BodyID": 5,
                       "BodyName": "Sys 5", "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 1}]})
        for i, k in enumerate(("Log", "Sample", "Analyse")):
            self.j.handle(org(f"2026-01-01T00:0{2 + i}:00Z", 1, 5, "Bacterial_01", k))
        value = outrider.bio.species_value("Bacterium Aurasus")
        self.assertEqual(self.body("5")["value_parts"]["bio_now"], value * 5)
        recs = lambda: ed_outrider.merge_records([], *ed_outrider.own_data(self.db, 1, "Sys")[:2])
        self.assertEqual(self.state.system_value(1, "Sys", recs(), None)["value_parts"]["bio_now"], value * 5)
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T01:00:00Z",
                       "BioData": [{"Species": "$Codex_Ent_Bacterial_01;", "Value": value, "Bonus": 0}]})
        b = self.body("5")
        self.assertEqual(b["value_parts"]["bio_now"], 0)                            # banked at Vista Genomics
        self.assertEqual(self.state.system_value(1, "Sys", recs(), None)["value_parts"]["bio_now"], 0)

    CANDS = CANDS

    def test_nearby_uses_your_dss_genera(self):   # F2
        recs = [{"name": "4", "type": "Planet", "subtype": "Rocky body", "bio": 2, "full": True}]
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            self.assertEqual(ed_outrider.summarise(recs, 1)["bio_potential"], 19_010_800 + 16_777_215)
            s = ed_outrider.summarise(recs, 1, genera={"4": ["Bacterium", "Fungoida"]})
        self.assertEqual(s["bio_potential"], 4_703_200)

    def test_search_remainder_after_a_sampled_genus(self):   # F20
        self.db.execute("INSERT INTO own_organic (system, body_id, species, genus_name, species_name, samples, done_ts, ts) "
                        "VALUES (9, 2, 'x', 'Bacterium', 'Bacterium Aurasus', 3, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')")
        recs = [{"name": "2", "type": "Planet", "subtype": "Rocky body", "body_id": 2, "bio": 2}]
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            hits = ed_outrider.bio_hits(self.db, 9, "Sys", 0, 0, 0, recs, 0)
            self.assertEqual(hits[0]["t"], "2 · 1 of 2 unscanned · up to 19.0M")
            self.assertEqual(ed_outrider.bio_hits(self.db, 9, "Sys", 0, 0, 0, recs, 20_000_000), [])

    def test_sample_run_on_another_body_is_not_shown(self):   # F4
        for bid in (4, 5):
            self.j.handle(scan("2026-01-01T00:01:00Z", "Sys", 1, bid, f"Sys {bid}")[2])
        self.j.handle({"event": "ScanOrganic", "timestamp": "2026-01-01T00:10:00Z", "SystemAddress": 1, "Body": 4, "ScanType": "Log",
                       "Genus": "$Codex_Ent_Tussocks_Genus_Name;", "Genus_Localised": "Tussock",
                       "Species": "$Codex_Ent_Tussocks_01_Name;", "Species_Localised": "Tussock Pennata"})
        at = lambda body: setattr(self.j, "status_json", {"live": True, "ts": "2026-01-01T00:11:00Z", "fuel_main": 10, "flags": 0,
                                                          "flags2": 1, "body": body, "lat": 0.0, "lon": 0.0, "planet_radius": 1_000_000})
        at("Sys 5")   # no distance across two planets: only the in-progress-elsewhere line (P5)
        self.assertEqual(set(self.state.sampling_summary()), {"elsewhere"})
        at("Sys 4")
        self.assertEqual(self.state.sampling_summary()["genus"], "Tussock")

    def test_rules_see_unrounded_gravity_and_unknown_volcanism(self):   # F10, F9
        ev = scan("2026-01-01T00:01:00Z", "Sys", 1, 4, "Sys 4")[2]
        ev.update(SurfaceGravity=0.2756 * 9.80665, Volcanism="")
        r = ed_outrider.record_from_scan(ev)
        self.assertEqual(r["gravity"], 0.28)                                     # shown rounded
        self.assertAlmostEqual(ed_outrider._bio_body(r, None, None)["gravity"], 0.2756)   # judged unrounded (max 0.276)
        self.assertEqual(r["volcanism"], "")                                     # the journal says: none
        del ev["Volcanism"]
        self.assertIsNone(ed_outrider.record_from_scan(ev)["volcanism"])         # not said: unknown
        facts = lambda v: outrider.bio._body_facts({"class": "Rocky body", "volcanism": v})
        self.assertIs(outrider.bio._check("volcanism", "None", facts(None), {}), outrider.bio.SKIP)
        self.assertIs(outrider.bio._check("volcanism", ["silicate"], facts(None), {}), outrider.bio.SKIP)
        self.assertTrue(outrider.bio._check("volcanism", "None", facts(""), {}))
        self.assertFalse(outrider.bio._check("volcanism", "Any", facts("No volcanism"), {}))

    def test_incomplete_system_rules_nothing_out(self):   # F37, F39
        recs = [{"type": "Star", "subtype": "M", "main": True, "body_id": 0},
                {"type": "Planet", "subtype": "Rocky body", "body_id": 3, "parents": [2]}]
        ctx = ed_outrider.bio_context("Sys", recs, body_count=4)
        self.assertEqual((ctx["planet_types"], ctx["complete"]), (None, False))   # a water giant may be unscanned
        self.assertIs(outrider.bio._check("bodies", {"Water giant"}, {}, outrider.bio._system_facts(ctx, {})), outrider.bio.SKIP)
        done = ed_outrider.bio_context("Sys", recs, body_count=2)
        self.assertEqual((done["planet_types"], done["complete"]), (["Rocky body"], True))
        # the planet orbits star 2, not scanned yet: its parents are unknown, not "the arrival M star"
        self.assertIsNone(ed_outrider._bio_body(recs[1], None, ctx)["parents"])
        self.assertEqual(ed_outrider._bio_body(recs[1], None, dict(ctx, star_types={0: "M", 2: "B"}))["parents"], ["B"])
        stratum = {"star": {"F": "Emerald", "K": "Lime", "M": "Green"}}
        b = outrider.bio._body_facts({"class": "Rocky body", "parents": None})
        self.assertTrue(outrider.bio._colour_ok(stratum, b, outrider.bio._system_facts(dict(ctx, stars=[{"type": "G", "main": True}]), {})))

    def test_obelisk_data_caps_at_150(self):   # G3.2
        self.assertEqual(outrider.materials.MATERIALS["ancientculturaldata"][2], 4)
        st = outrider.materials.new_state()
        outrider.materials._add(st, "AncientCulturalData", 149)
        outrider.materials._add(st, "AncientCulturalData", 3)
        self.assertEqual(st["counts"]["ancientculturaldata"], 150)


class Batch4Ledger(unittest.TestCase):
    """Batch 4: sale payouts, trips between sales, what a ship loss cost, ranks."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def sell(self, ts, total, systems):
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": ts, "TotalEarnings": total, "BaseValue": total, "Bonus": 0,
                       "Discovered": [{"SystemName": s, "NumBodies": 1} for s in systems]})

    def test_trips_merge_batches_and_price_losses(self):
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        self.j.handle(scan("2026-01-01T00:01:00Z", "S1", 1, 0, "S1", star=True)[2])
        self.sell("2026-01-02T00:00:00Z", 100, ["S1"])
        self.sell("2026-01-02T00:05:00Z", 50, [])                 # a second batch at the same station
        self.jump("2026-01-03T00:00:00Z", 2, 10)
        self.j.handle(scan("2026-01-03T00:01:00Z", "S2", 2, 0, "S2", star=True)[2])
        self.j.handle({"event": "Died", "timestamp": "2026-01-04T00:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-04T00:00:00Z", "Option": "rebuy"})
        self.db.commit()
        L = self.state.ledger()
        self.assertEqual(len(L["trips"]), 1)
        self.assertEqual(L["trips"][0]["paid"], 150)
        self.assertEqual(len(L["losses"]), 1)
        self.assertEqual(L["losses"][0]["bodies"], 1)              # S2's star died with the ship; S1's was sold
        self.assertGreater(L["losses"][0]["value"], 0)
        self.assertEqual(L["since_last_sale"]["jumps"], 1)

    def test_ranks_named(self):
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:00Z", "Commander": "J", "Credits": 1})
        self.j.handle({"event": "Rank", "timestamp": "2026-01-01T00:00:01Z", "Explore": 10, "Exobiologist": 7})
        self.j.handle({"event": "Progress", "timestamp": "2026-01-01T00:00:01Z", "Explore": 24, "Exobiologist": 43})
        r = self.state.commander_summary()["ranks"]
        self.assertEqual((r["Explore"]["name"], r["Explore"]["progress"]), ("Elite II", 24))
        self.j.handle({"event": "Promotion", "timestamp": "2026-01-02T00:00:00Z", "Explore": 11})
        r = self.state.commander_summary()["ranks"]
        self.assertEqual((r["Explore"]["name"], r["Explore"]["progress"]), ("Elite III", 0))


class RulesDownload(unittest.TestCase):
    """F38/F80: the spawn-rules download (every fetch mocked: bio_rules.json is never touched)."""

    V = {"bioscan": "b1", "regionmap": "r1", "explodata": "e1"}

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "rules.json")
        self.log = []

    def tearDown(self):
        outrider.bio.load_rules(outrider.bio.RULES_FILE, force=True)   # back to the shipped copy for the other tests
        self.tmp.cleanup()

    def fake_get(self, fail=()):
        def get(url):
            if any(f in url for f in fail):
                raise OSError("timed out")
            for key, src in (("contents/", '[{"name": "stratum.py"}]'), ("rulesets", "catalog = {}"), ("species.py", "_mound_amphora = {}"),
                             ("regions.py", "region_map = {}"), ("reference_stars.py", "coordinates = {}"),
                             ("sectors.py", "data = []"), ("RegionMapData", "regions = []\nregionmap = []"),
                             ("genus.py", "data = {}")):
                if key in url:
                    return src
            raise AssertionError(f"unexpected fetch {url}")
        return get

    def test_a_table_no_longer_literal_fails_the_update(self):
        """Upstream writing a region, nebula or grid table as code (region_map = build_map()): the update fails and the
        old file stays, rather than empty tables ruling out Anemone, Brain Trees, Tubers... everywhere (the Fable sweep,
        2026-10-09)."""
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            before = fh.read()
        good = self.fake_get()

        def get(url):
            return "region_map = build_map()" if "regions.py" in url else good(url)
        with unittest.mock.patch.object(outrider.bio, "_get", get), self.assertRaises(ValueError):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V, bioscan="b2"))
        with open(self.path) as fh:
            self.assertEqual(fh.read(), before)

    def test_colours_no_longer_literal_are_retried(self):
        """ExploData's colour table written as code (data = build_colours()): not taken as "no colours" with its version
        recorded (never fetched again), but as a failed fetch, retried at the next start (Codex, 2026-10-09)."""
        good = self.fake_get()

        def get(url):
            return "data = build_colours()" if "genus.py" in url else good(url)
        with unittest.mock.patch.object(outrider.bio, "_get", get):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["versions"]["explodata"], "")
        self.assertTrue(any("could not fetch colour variants" in m for m in self.log))

    def test_colours_table_gone_is_retried(self):
        """ExploData's genus.py with no `data` table at all (renamed or moved upstream): a failed fetch too, not "no
        colours" with its version recorded (the Fable review of 2026-10-10, #9)."""
        good = self.fake_get()

        def get(url):
            return "genus_data = {}" if "genus.py" in url else good(url)
        with unittest.mock.patch.object(outrider.bio, "_get", get):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["versions"]["explodata"], "")
        self.assertTrue(any("could not fetch colour variants" in m and "no data table" in m for m in self.log))

    def test_a_failed_part_is_saved_without_a_version(self):   # F38
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get(fail=("contents/", "genus.py"))):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            saved = json.load(fh)["versions"]
        self.assertEqual(saved, {"bioscan": "", "regionmap": "r1", "explodata": ""})   # retried at the next start
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["versions"], self.V)
        # and the next start sees the gap and fetches again
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get(fail=("genus.py",))):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=dict(self.V)), \
                unittest.mock.patch.object(outrider.bio, "update_rules") as upd:
            self.assertTrue(outrider.bio.update_if_newer(self.path, log=self.log.append))
            upd.assert_called_once()

    def test_failed_update_keeps_the_old_copy(self):   # F80
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with open(self.path) as fh:
            before = fh.read()
        newer = dict(self.V, bioscan="b2")
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=newer), \
                unittest.mock.patch.object(outrider.bio, "_get", self.fake_get(fail=("reference_stars.py",))):
            self.assertIsNone(outrider.bio.update_if_newer(self.path, log=self.log.append))
        self.assertIn("update failed", self.log[-1])
        with open(self.path) as fh:
            self.assertEqual(fh.read(), before)
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=dict(self.V)):
            self.assertIs(outrider.bio.update_if_newer(self.path, log=self.log.append), False)   # current
        missing = os.path.join(self.tmp.name, "none.json")
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=newer), \
                unittest.mock.patch.object(outrider.bio, "_get", self.fake_get(fail=("reference_stars.py",))):
            with self.assertRaises(OSError):
                outrider.bio.update_if_newer(missing, log=self.log.append)       # nothing to fall back on

    def test_failed_colour_fetch_keeps_the_colours_there(self):   # F66
        catalog = ('catalog = {"$Codex_Ent_Bacterial_Genus_Name;": {"$Codex_Ent_Bacterial_01_Name;": '
                   '{"name": "Bacterium Aurasus", "value": 1000000, "rulesets": []}}}')
        genus = ('data = {"$Codex_Ent_Bacterial_Genus_Name;": {"colors": {"species": '
                 '{"$Codex_Ent_Bacterial_01_Name;": {"star": {"F": "Teal"}}}}}}')

        def get_with(fail=()):
            base = self.fake_get(fail)

            def get(url):
                if any(f in url for f in fail):
                    raise OSError("timed out")
                if "rulesets/" in url:
                    return catalog
                return genus if "genus.py" in url else base(url)
            return get

        def colours():   # as loaded: the rules with the colour tables beside them merged in
            return [sp["colors"] for sp in outrider.bio.load_rules(self.path, force=True)["species"]]
        with unittest.mock.patch.object(outrider.bio, "_get", get_with()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        self.assertEqual(colours(), [{"star": {"F": "Teal"}}])
        # ExploData's colours are never in the rules file itself (it ships): in bio_colours.json beside it (downloaded)
        with open(self.path) as fh:
            self.assertEqual([sp["colors"] for sp in json.load(fh)["species"]], [None])
        self.assertTrue(os.path.exists(outrider.bio.colours_path(self.path)))
        with unittest.mock.patch.object(outrider.bio, "_get", get_with(fail=("genus.py",))):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V, bioscan="b2"))
        self.assertEqual(colours(), [{"star": {"F": "Teal"}}])      # the colour check stays on: the file there is kept
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["versions"]["explodata"], "")   # and ExploData is fetched again next start

    def test_no_colour_file_means_out_of_date(self):
        """The shipped rules carry no colours (ExploData's are downloaded, never shipped: the author, 2026-10-10): with
        no bio_colours.json beside them they are fetched on the first start even when their versions are current."""
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        os.remove(outrider.bio.colours_path(self.path))
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=dict(self.V)), \
                unittest.mock.patch.object(outrider.bio, "update_rules") as upd:
            self.assertTrue(outrider.bio.update_if_newer(self.path, log=self.log.append))
            upd.assert_called_once()
        with unittest.mock.patch.object(outrider.bio, "_get", self.fake_get()):
            outrider.bio.update_rules(self.path, log=self.log.append, versions=dict(self.V))
        with unittest.mock.patch.object(outrider.bio, "remote_versions", return_value=dict(self.V)):
            self.assertFalse(outrider.bio.update_if_newer(self.path, log=self.log.append))   # both there: current


class BatchS1(unittest.TestCase):
    """Suggestions batch S1: values and decisions on screen (P1, P2, P6, P13, P17)."""

    CANDS = CANDS

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.jump("2026-01-01T00:00:00Z", 1, 0)

    jump, honk, planet = voice_jump, voice_honk, voice_planet

    def signals(self, ts, id64, body_id, name, n):
        self.j.handle({"event": "FSSBodySignals", "timestamp": ts, "SystemAddress": id64, "BodyName": f"S{id64} {name}",
                       "BodyID": body_id, "Signals": [{"Type": ed_outrider.BIO, "Count": n}]})

    def analysed(self, ts, id64, body_id, species, genus):
        self.j.handle({"event": "ScanOrganic", "timestamp": ts, "ScanType": "Analyse", "SystemAddress": id64, "Body": body_id,
                       "Genus": f"$Codex_Ent_{genus}_Genus_Name;", "Genus_Localised": genus,
                       "Species": f"$Codex_Ent_{species.replace(' ', '_')}_Name;", "Species_Localised": species})

    def test_leaving_carries_factor_gravity_and_atmosphere(self):   # P1, P13
        rocky = dict(Landable=True, PlanetClass="Rocky body", MassEM=0.2)
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", WasFootfalled=False, SurfaceGravity=2.6 * 9.80665,
                    AtmosphereType="CarbonDioxide", **rocky)
        self.planet("2026-01-01T00:01:10Z", 1, 5, "A 5", WasFootfalled=True, **rocky)
        self.planet("2026-01-01T00:01:20Z", 1, 6, "A 6", **rocky)                    # no WasFootfalled at all
        for bid, name in ((4, "A 4"), (5, "A 5"), (6, "A 6")):
            self.signals("2026-01-01T00:02:00Z", 1, bid, name, 1)
        self.db.commit()
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            pend = {p["body"]: p for p in self.state.leaving_summary(1)["bio_pending"]}
        self.assertEqual({b: p["factor"] for b, p in pend.items()}, {"A 4": 5, "A 5": 1, "A 6": 1})
        self.assertEqual(pend["A 4"]["potential"], 19_010_800)                      # still bonus-free
        self.assertEqual((pend["A 4"]["gravity"], pend["A 4"]["atmosphere"]), (2.6, "CarbonDioxide"))
        self.assertIsNone(pend["A 6"]["atmosphere"])

    def test_left_behind_lists_signals_never_dssd(self):   # P2
        self.jump("2026-01-01T00:01:00Z", 2, 30)
        rocky = dict(Landable=True, PlanetClass="Rocky body", MassEM=0.2)
        self.planet("2026-01-01T00:02:00Z", 2, 4, "A 4", **rocky)
        self.signals("2026-01-01T00:02:10Z", 2, 4, "A 4", 3)
        self.planet("2026-01-01T00:02:20Z", 2, 5, "A 5", **rocky)
        self.signals("2026-01-01T00:02:30Z", 2, 5, "A 5", 1)                        # its one signal is sampled
        self.analysed("2026-01-01T00:03:00Z", 2, 5, "Bacterium Aurasus", "Bacterium")
        self.planet("2026-01-01T00:03:10Z", 2, 6, "A 6", **rocky)                   # DSS'd: its genera win
        self.signals("2026-01-01T00:03:20Z", 2, 6, "A 6", 2)
        self.j.handle({"event": "SAASignalsFound", "timestamp": "2026-01-01T00:03:30Z", "SystemAddress": 2, "BodyID": 6,
                       "BodyName": "S2 A 6", "Signals": [{"Type": ed_outrider.BIO, "Count": 2}],
                       "Genuses": [{"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"}]})
        self.jump("2026-01-01T00:04:00Z", 1, 0)
        self.db.commit()
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            left = self.state.left_behind(100)["systems"]
        self.assertEqual([r["name"] for r in left], ["S2"])
        bio = {b["body"]: b for b in left[0]["bio"]}
        self.assertEqual(sorted(bio), ["A 4", "A 6"])                                # A 5: nothing left
        self.assertEqual((bio["A 4"]["genera"], bio["A 4"]["signals"]), (None, 3))
        self.assertEqual(bio["A 4"]["value"], 19_010_800 + 16_777_215 + 3_703_200)   # the three best the rules allow
        self.assertEqual(bio["A 6"]["genera"], ["Stratum"])

    def test_base_known(self):   # P6
        recs = [ed_outrider.record_from_dump("S1", {"name": f"S1 A {i}", "type": "Planet", "subType": "Icy body", "bodyId": i})
                for i in range(1, 12)] + [ed_outrider.record_from_dump("S1", {"name": "S1 A", "type": "Star", "subType": "K (Yellow-Orange) Star",
                                                                                "mainStar": True, "bodyId": 0})]
        base = {"name": "S1", "x": 0, "y": 0, "z": 0, "body_count": 12, "records": recs}
        self.assertEqual(ed_outrider.base_known(base), 12)
        self.assertEqual(ed_outrider.base_known(dict(base, records=[{"name": "S1", "type": "Star", "placeholder": True}])), 0)
        self.assertIsNone(ed_outrider.base_known(base, "own"))                       # a stand-in: knows nothing
        self.assertIsNone(ed_outrider.base_known(None))
        self.state.bases[1] = ("spansh", base)
        self.honk("2026-01-01T00:00:10Z", 1, 14)
        self.db.commit()
        f = self.state.arrival_facts(1)
        self.assertEqual((f["body_count"], f["base_known"]), (14, 12))              # 2 not on Spansh
        self.assertEqual(self.state.system_detail(1)["leaving"]["base_known"], 12)
        self.state.bases[1] = ("own", dict(base, records=[]))
        self.assertIsNone(self.state.arrival_facts(1)["base_known"])

    def test_backup_holds_speech_and_config(self):   # P17
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            sqlite3.connect(dbp).close()
            self.state.db_path = dbp
            self.state.speech_path, self.state.config_path = os.path.join(d, "my_lines.json"), os.path.join(d, "cfg.toml")
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", os.path.join(d, "b1")), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
                out = self.state.make_backup()                                      # neither file exists yet
            self.assertEqual(out["files"], ["x.sqlite"])
            self.assertNotIn("warning", out)
            with open(self.state.speech_path, "w") as f:
                f.write("{}")
            with open(self.state.config_path, "w") as f:
                f.write("radius = 25\n")
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", os.path.join(d, "b2")), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
                out = self.state.make_backup()
            self.assertEqual(out["files"], ["x.sqlite", "speech.json", "ed_outrider.toml"])
            with zipfile.ZipFile(out["path"]) as z:
                self.assertEqual(sorted(z.namelist()), ["ed_outrider.toml", "speech.json", "x.sqlite"])
                self.assertEqual(z.read("ed_outrider.toml"), b"radius = 25\n")
            os.chmod(self.state.speech_path, 0)
            if not os.access(self.state.speech_path, os.R_OK):                     # (root reads it anyway)
                with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", os.path.join(d, "b3")), \
                        unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
                    out = self.state.make_backup()                                  # unreadable: a warning, not a failure
                self.assertEqual(out["files"], ["x.sqlite", "ed_outrider.toml"])
                self.assertIn("speech.json not backed up", out["warning"])
                self.assertTrue(os.path.exists(out["path"]))
            os.chmod(self.state.speech_path, 0o600)


class Batch4Review(unittest.TestCase):
    """PLAN-review-2026-09-30b Batch 4: exobiology, unsold and the helper modules."""

    def test_bark_mounds_are_priced(self):   # F50
        self.assertEqual(outrider.bio.species_value("Bark Mounds"), 1471900)
        self.assertEqual(outrider.bio.species_value("Bark Mound"), 1471900)
        self.assertEqual(outrider.bio.species_value("Bacterium Aurasus"), outrider.unsold.species_value("$Codex_Ent_Bacterial_01")[0])

    def test_pressure_keeps_its_fine_digits(self):   # F53
        ev = {"event": "Scan", "BodyName": "S 1", "BodyID": 1, "PlanetClass": "Rocky body", "MassEM": 0.1,
              "SurfacePressure": 0.002862 * 101325, "DistanceFromArrivalLS": 10}
        r = ed_outrider.record_from_scan(ev)
        self.assertEqual(r["pressure"], 0.0029)                     # shown rounded
        self.assertAlmostEqual(ed_outrider._bio_body(r, "K", {})["pressure"], 0.002862)   # judged unrounded
        self.assertLess(ed_outrider._bio_body(r, "K", {})["pressure"], 0.00289)
        d = ed_outrider.record_from_dump("S", {"name": "S 1", "type": "Planet", "subType": "Rocky body",
                                               "surfacePressure": 0.002862})
        self.assertEqual((d["pressure"], d["pressure_raw"]), (0.0029, 0.002862))
        self.assertIsNone(ed_outrider.record_from_scan(dict(ev, SurfacePressure=0))["pressure_raw"])

    @unittest.skipUnless(outrider.bio.available(), "bio_rules.json not downloaded")
    def test_rules_file_missing_a_key_counts_as_absent(self):   # F54
        import tempfile
        good = outrider.bio._rules_path or outrider.bio.RULES_FILE
        with open(good, encoding="utf-8") as f:
            data = json.load(f)
        try:
            with tempfile.TemporaryDirectory() as d:
                for drop in ("nebulae_planetary", "tuber_zones"):
                    path = os.path.join(d, f"no-{drop}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({k: v for k, v in data.items() if k != drop}, f)
                    self.assertIsNone(outrider.bio.load_rules(path, force=True))
                    self.assertIsNone(outrider.bio.load_rules(path))               # no KeyError on the next call either
                path = os.path.join(d, "list.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump([1, 2], f)
                self.assertIsNone(outrider.bio.load_rules(path, force=True))
        finally:
            self.assertIsNotNone(outrider.bio.load_rules(good, force=True))

    def test_unknown_luminosity_does_not_rule_out_anemone(self):   # F52
        want = [["B", "IV"], ["B", "V"]]
        facts = lambda lum, complete=True: {"stars": [{"type": "B", "luminosity": lum, "main": True}],
                                            "main": {"type": "B", "luminosity": lum, "main": True}, "complete": complete}
        self.assertIs(outrider.bio._check("star", want, {}, facts(None)), outrider.bio.SKIP)
        self.assertIs(outrider.bio._check("star", want, {}, facts("Va")), True)
        self.assertIs(outrider.bio._check("star", want, {}, facts("III")), False)     # known and wrong: still out
        self.assertIs(outrider.bio._check("main_star", want, {}, facts(None)), outrider.bio.SKIP)
        self.assertIs(outrider.bio._check("main_star", want, {}, facts("III")), False)
        self.assertIs(outrider.bio._check("star", ["O"], {}, facts(None)), False)       # wrong class: out

    def test_remap_after_the_map_was_sold_adds_nothing(self):   # F55
        mapped = lambda ts: (T(ts), None, {"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": 1, "BodyID": 4,
                                           "BodyName": "Sys 4", "ProbesUsed": 5, "EfficiencyTarget": 6})
        ev = [scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4"), mapped("2026-01-01T00:06:00Z"),
              sale("2026-01-02T00:00:00Z", ["Sys"]), mapped("2026-01-03T00:00:00Z")]
        self.assertEqual(outrider.unsold.analyse(ev, ARGS)["exploration"]["rows"], [])
        # a first mapping after the scan alone was sold is still worth the map (F36)
        ev = [scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4"), sale("2026-01-02T00:00:00Z", ["Sys"]),
              mapped("2026-01-03T00:00:00Z")]
        self.assertEqual([r["map_only"] for r in outrider.unsold.analyse(ev, ARGS)["exploration"]["rows"]], [True])

    # ---- Piper ----
    def _speaker(self, d, **kw):
        import outrider.tts
        open(os.path.join(d, "en_GB-b-low.onnx"), "w").close()
        open(os.path.join(d, "en_GB-b-low.onnx.json"), "w").close()
        sp = outrider.tts.Speaker("en_GB-a-low", "en_GB-b-low", voices_dir=d, **kw)
        sp.PiperVoice = unittest.mock.Mock()
        sp.PiperVoice.load = lambda path: os.path.basename(path)
        return sp

    def test_missing_preferred_voice_is_fetched_behind_the_fallback(self):   # G3.2
        import contextlib, io, tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            seen, switched, threads = [], [], []
            sp = self._speaker(d, on_switched=switched.append)
            sp.on_change = lambda: seen.append(sp.status)
            with unittest.mock.patch.object(outrider.tts.threading, "Thread",
                                            lambda **kw: threads.append(kw) or unittest.mock.Mock()), \
                    contextlib.redirect_stdout(io.StringIO()):
                sp._prepare(None)
            self.assertEqual(sp.voice_name, "en_GB-b-low")                # the installed one speaks at once
            self.assertEqual([t["args"] for t in threads], [("en_GB-a-low", "en_GB-b-low")])
            it = iter([_FakeResponse(b"{}"), _FakeResponse(b"model")])
            with unittest.mock.patch.object(outrider.tts.urllib.request, "urlopen", lambda url, timeout: next(it)), \
                    contextlib.redirect_stdout(io.StringIO()):
                threads[0]["target"](*threads[0]["args"])
            self.assertEqual(sp.voice_name, "en_GB-a-low")                # switched once it arrived
            self.assertEqual(seen[2:], ["using en_GB-b-low; downloading en_GB-a-low (about 63 MB), switching to it "
                                        "when it is ready", "loading en_GB-a-low", "ready"])
            self.assertEqual(switched, [])                                # the config's voice, not a dialog choice
            self.assertIn("en_GB-a-low", outrider.tts.installed_voices(d))
        # a failed download keeps the fallback and says so; a dialog pick made meanwhile wins
        with tempfile.TemporaryDirectory() as d:
            sp = self._speaker(d)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                    unittest.mock.patch.object(outrider.tts.threading, "Thread", lambda **kw: unittest.mock.Mock()):
                sp._prepare(None)
                with unittest.mock.patch.object(outrider.tts, "download_voice_files", side_effect=OSError("offline")):
                    sp._fetch_preferred("en_GB-a-low", "en_GB-b-low")
            self.assertEqual((sp.voice_name, sp.status), ("en_GB-b-low", "using en_GB-b-low; could not download en_GB-a-low"))
            sp.wanted = "en_GB-c-low"
            with contextlib.redirect_stdout(io.StringIO()), \
                    unittest.mock.patch.object(outrider.tts, "download_voice_files", lambda files, d: None):
                sp._fetch_preferred("en_GB-a-low", "en_GB-b-low")
            self.assertEqual(sp.voice_name, "en_GB-b-low")
        # an installed preferred voice starts no download
        with tempfile.TemporaryDirectory() as d:
            sp = self._speaker(d)
            sp.preferred = "en_GB-b-low"
            threads = []
            with unittest.mock.patch.object(outrider.tts.threading, "Thread",
                                            lambda **kw: threads.append(kw) or unittest.mock.Mock()), \
                    contextlib.redirect_stdout(io.StringIO()):
                sp._prepare(None)
            self.assertEqual(threads, [])

    def test_unspeakable_line_is_none_not_an_error(self):   # G3.1
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            sp = self._speaker(d)
            calls = []
            sp._voice = types_ns(synthesize_wav=lambda text, wf, syn_config=None: calls.append(text))
            self.assertIsNone(sp.say("…"))
            self.assertIsNone(sp.say("…"))
            self.assertEqual(calls, ["…"])                               # remembered, not synthesised again

    # ---- voice lab ----
    def _lab(self):
        try:
            import voice_lab
        except (ImportError, SystemExit):
            self.skipTest("no tkinter")
        return voice_lab

    def test_voice_lab_reads_the_configured_speech_file(self):   # F59
        voice_lab = self._lab()
        with unittest.mock.patch.object(voice_lab, "_config", lambda: {"server": {"speech_file": "~/my_lines.json"}}):
            self.assertEqual(voice_lab.configured_speech_file(), os.path.expanduser("~/my_lines.json"))
        with unittest.mock.patch.object(voice_lab, "_config", lambda: {"server": {"speech_file": "mine.json"}}):
            self.assertEqual(voice_lab.configured_speech_file(), os.path.join(voice_lab.outrider.ROOT, "mine.json"))
        with unittest.mock.patch.object(voice_lab, "_config", lambda: {}):
            self.assertEqual(voice_lab.configured_speech_file(), voice_lab.SPEECH_FILE)

    def test_voice_lab_removes_each_spoken_wav(self):   # F60
        import tempfile
        voice_lab = self._lab()
        with tempfile.TemporaryDirectory() as d:
            p = voice_lab.Player()
            p.cmd = None                                                  # nothing is played in a test
            a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
            for path in (a, b):
                open(path, "wb").close()
            p.play(a)
            p.play(b)
            self.assertEqual(os.listdir(d), ["b.wav"])
            p.stop()
            self.assertEqual(os.listdir(d), [])

    def test_voice_lab_refetches_a_truncated_catalogue(self):   # F61
        import io, tempfile
        voice_lab = self._lab()
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "voices.json")
            with open(cache, "w") as f:
                f.write('{"en_GB-a-low": {"lang')
            with unittest.mock.patch.object(voice_lab, "VOICES_DIR", d), \
                    unittest.mock.patch.object(voice_lab, "CATALOGUE_CACHE", cache), \
                    unittest.mock.patch.object(voice_lab.outrider.tts.urllib.request, "urlopen",
                                               lambda url, timeout: io.BytesIO(b'{"en_GB-a-low": {}}')):
                self.assertEqual(voice_lab.fetch_catalogue(), {"en_GB-a-low": {}})
            with open(cache) as f:
                self.assertEqual(json.load(f), {"en_GB-a-low": {}})
            self.assertEqual(os.listdir(d), ["voices.json"])              # no .part left behind

    def test_numpad_operator_labels(self):   # F57
        import outrider.honk
        self.assertEqual([outrider.honk.key_label(k) for k in ("KEY_KPPLUS", "KEY_KPENTER", "KEY_KPDOT", "KEY_SYSRQ",
                                                         "KEY_102ND", "KEY_KP5", "KEY_LEFTALT", "KEY_K")],
                         ["Numpad +", "Numpad Enter", "Numpad .", "Print Screen", "OEM 102", "Numpad 5", "Left Alt", "K"])


class BatchEExobio(unittest.TestCase):
    """Batch E: the run in progress elsewhere (P5), per-run x5 pricing and the sale check (P8), the region crossing
    (P10) and the jumponium call-out (P17)."""

    STRATUM = "$Codex_Ent_Stratum_07_Name;"
    TUSSOCK = "$Codex_Ent_Tussocks_01_Name;"

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    @staticmethod
    def body_scan(ts, body_id, footfalled, addr=1, system="Sys", **kw):
        ev = scan(ts, system, addr, body_id, f"{system} {body_id}")[2]
        if footfalled is not None:
            ev["WasFootfalled"] = footfalled
        ev.update(kw)
        return ev

    @staticmethod
    def organic(ts, body_id, kind, species, name, addr=1):
        genus = name.split()[0]
        return {"event": "ScanOrganic", "timestamp": ts, "SystemAddress": addr, "Body": body_id, "ScanType": kind,
                "Genus": f"$Codex_Ent_{genus}_Genus_Name;", "Genus_Localised": genus, "Species": species, "Species_Localised": name}

    # ---- P8: per-run pricing ----
    def test_per_run_pricing(self):
        ev = lambda e: (T(e["timestamp"]), None, e)
        v, _ = outrider.unsold.species_value(self.STRATUM)
        sold = {"event": "SellOrganicData", "timestamp": "2026-01-01T00:00:00Z",   # 1 of 4 sold entries earned x5: 25%
                "BioData": [{"Species": self.TUSSOCK, "Value": 10, "Bonus": 40}] + [{"Species": self.TUSSOCK, "Value": 10, "Bonus": 0}] * 3}
        events = [ev(sold)] + [ev(self.body_scan("2026-01-02T00:00:00Z", b, f)) for b, f in ((1, False), (2, True), (3, None))] + \
                 [ev(self.organic(f"2026-01-03T00:0{b}:00Z", b, "Analyse", self.STRATUM, "Stratum Tectonicas")) for b in (1, 2, 3)]
        bio = outrider.unsold.analyse(events, ARGS)["exobiology"]
        self.assertEqual((bio["x5_runs"], bio["x1_runs"], bio["unknown_runs"]), (1, 1, 1))
        self.assertEqual(bio["estimated_value"], int(v * 5 + v + v * (1 + 4 * 0.25)))
        self.assertEqual((bio["base_value"], bio["max_value"]), (3 * v, 15 * v))   # unchanged
        self.assertEqual({k: bio["rows"][0][k] for k in ("x5", "x1", "unknown")}, {"x5": 1, "x1": 1, "unknown": 1})
        # a rescan after your own landing says footfalled: the first scan decides
        events.insert(4, ev(self.body_scan("2026-01-02T01:00:00Z", 1, True)))
        self.assertEqual(outrider.unsold.analyse(events, ARGS)["exobiology"]["x5_runs"], 1)

    def test_populated_runs_price_x1(self):
        """Plugin gaps C: a body nobody had set foot on in a populated system is priced x1 (Vista pays no x5 there)."""
        ev = lambda e: (T(e["timestamp"]), None, e)
        v, _ = outrider.unsold.species_value(self.STRATUM)
        events = [ev({"event": "FSDJump", "timestamp": "2026-01-02T00:00:00Z", "StarSystem": "Busy", "SystemAddress": 7,
                      "StarPos": [0, 0, 0], "Population": 14655365}),
                  ev(self.body_scan("2026-01-02T00:01:00Z", 1, False, addr=7, system="Busy")),
                  ev(self.organic("2026-01-03T00:01:00Z", 1, "Analyse", self.STRATUM, "Stratum Tectonicas", addr=7))]
        bio = outrider.unsold.analyse(events, ARGS)["exobiology"]
        self.assertEqual((bio["x5_runs"], bio["x1_runs"], bio["estimated_value"]), (0, 1, v))

    # ---- P8: the sale check ----
    def sale_journal(self):
        return [self.body_scan("2026-01-01T00:00:00Z", 1, False), self.body_scan("2026-01-01T00:00:01Z", 2, False),
                self.body_scan("2026-01-01T00:00:02Z", 3, True), self.body_scan("2026-01-01T00:00:03Z", 4, None),
                self.organic("2026-01-01T01:00:00Z", 1, "Analyse", self.STRATUM, "Stratum Tectonicas"),
                self.organic("2026-01-01T01:10:00Z", 2, "Analyse", self.STRATUM, "Stratum Tectonicas"),
                self.organic("2026-01-01T01:20:00Z", 3, "Analyse", self.TUSSOCK, "Tussock Pennata"),
                self.organic("2026-01-01T01:30:00Z", 4, "Analyse", self.TUSSOCK, "Tussock Pennata"),
                {"event": "SellOrganicData", "timestamp": "2026-01-02T00:00:00Z", "BioData": [
                    {"Species": self.STRATUM, "Value": 100, "Bonus": 400}, {"Species": self.STRATUM, "Value": 100, "Bonus": 0},
                    {"Species": self.TUSSOCK, "Value": 10, "Bonus": 40}, {"Species": self.TUSSOCK, "Value": 10, "Bonus": 0}]},
                {"event": "MultiSellExplorationData", "timestamp": "2026-01-02T00:05:00Z", "TotalEarnings": 1000,
                 "BaseValue": 1000, "Bonus": 0, "Discovered": []}]

    def test_sale_check(self):
        for i, e in enumerate(self.sale_journal()):
            self.j.line_source = f"j:{i}"
            self.j.handle(e)
        row = self.db.execute("SELECT x5_check FROM sale_events WHERE kind = 'bio'").fetchone()
        want = {"sold": 4, "predicted": 2, "matched": 1, "paid": 2, "unknown": 1}
        used = {self.STRATUM.lower(): [2, 0], self.TUSSOCK.lower(): [0, 1]}
        self.assertEqual(json.loads(row[0]), dict(want, used=used))
        # the estimate is live only; the check comes back from the journals alone after a re-read
        self.db.execute("INSERT INTO sale_estimates VALUES ('2026-01-02T00:00:00Z', 'bio', 400)")
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.j.reload()
        for i, e in enumerate(self.sale_journal()):
            self.j.line_source = f"j:{i}"
            self.j.handle(e)
        self.assertEqual(json.loads(self.db.execute("SELECT x5_check FROM sale_events WHERE kind = 'bio'").fetchone()[0]), dict(want, used=used))
        trip = self.state.ledger()["trips"][0]
        self.assertEqual(trip["x5"], want)
        self.assertEqual((trip["estimate_bio"], trip["paid_bio_estimated"]), (400, 660))
        # a death before the sale takes the runs done before it out of the prediction
        self.assertEqual(ed_outrider.sale_check(self.db, "2026-01-02T00:00:00Z", []), None)
        self.db.execute("INSERT INTO deaths VALUES ('2026-01-01T01:15:00Z', 'recover')")
        self.assertEqual(ed_outrider.sale_check(self.db, "2026-01-03T00:00:00Z", [{"Species": self.STRATUM, "Bonus": 1}]),
                         {"sold": 1, "predicted": 0, "matched": 0, "paid": 1, "unknown": 0, "used": {self.STRATUM.lower(): [0, 0]}})

    def test_sale_check_over_one_visit(self):
        # selling in three goes at one station: each later sale draws on the runs the earlier ones left
        journal = self.sale_journal()[:8]
        parts = [[{"Species": self.STRATUM, "Value": 100, "Bonus": 400}], [{"Species": self.STRATUM, "Value": 100, "Bonus": 400}],
                 [{"Species": self.TUSSOCK, "Value": 10, "Bonus": 0}, {"Species": self.TUSSOCK, "Value": 10, "Bonus": 0}]]
        for i, (t, bio) in enumerate(zip(("00:00:00", "00:00:11", "00:02:10"), parts)):
            journal.append({"event": "SellOrganicData", "timestamp": f"2026-01-02T{t}Z", "BioData": bio})
        for i, e in enumerate(journal):
            self.j.line_source = f"j:{i}"
            self.j.handle(e)
        got = [{k: c[k] for k in ("sold", "predicted", "matched", "unknown")} for c in
               (json.loads(r[0]) for r in self.db.execute("SELECT x5_check FROM sale_events WHERE kind = 'bio' ORDER BY ts"))]
        self.assertEqual(got, [{"sold": 1, "predicted": 1, "matched": 1, "unknown": 0}, {"sold": 1, "predicted": 1, "matched": 1, "unknown": 0},
                               {"sold": 2, "predicted": 0, "matched": 0, "unknown": 1}])

    def visit(self, sales, gap=11):
        """Body 1 not footfalled (x5 predicted), body 2 footfalled (x1), a Stratum run done on each; then the sales,
        `gap` s apart. -> the x5_check rows, in journal order, and the trip's x5."""
        journal = [self.body_scan("2026-01-01T00:00:00Z", 1, False), self.body_scan("2026-01-01T00:00:01Z", 2, True),
                   self.organic("2026-01-01T01:00:00Z", 1, "Analyse", self.STRATUM, "Stratum Tectonicas"),
                   self.organic("2026-01-01T01:10:00Z", 2, "Analyse", self.STRATUM, "Stratum Tectonicas")]
        for k, bonus in enumerate(sales):
            journal.append({"event": "SellOrganicData", "timestamp": ed_outrider.iso_ts(ed_outrider.ts_seconds("2026-01-02T00:00:00Z") + k * gap),
                            "BioData": [{"Species": self.STRATUM, "Value": 100, "Bonus": 400 if bonus else 0}]})
        journal.append({"event": "MultiSellExplorationData", "timestamp": "2026-01-02T01:00:00Z", "TotalEarnings": 1000,
                        "BaseValue": 1000, "Bonus": 0, "Discovered": []})
        for i, e in enumerate(journal):
            self.j.line_source = f"j:{i}"
            self.j.handle(e)
        rows = [{k: c[k] for k in ("sold", "predicted", "matched")} for c in
                (json.loads(r[0]) for r in self.db.execute("SELECT x5_check FROM sale_events WHERE kind = 'bio' ORDER BY ts, source"))]
        return rows, self.state.ledger()["trips"][0]["x5"]

    def test_a_visit_in_several_goes_is_one_check(self):   # F21
        rows, trip = self.visit([False, False])   # the prediction was wrong: no bonus on either
        self.assertEqual([r["predicted"] for r in rows], [1, 0])
        self.assertEqual({k: trip[k] for k in ("sold", "predicted", "matched")}, {"sold": 2, "predicted": 1, "matched": 0})

    def test_x1_sold_before_the_x5_is_no_false_miss(self):   # F21, the skeptic's case: the prediction was right
        _rows, trip = self.visit([False, True])
        self.assertEqual({k: trip[k] for k in ("sold", "predicted", "matched")}, {"sold": 2, "predicted": 1, "matched": 1})

    def test_two_vista_sales_in_one_second(self):   # Codex C1: both kept, each takes its own run
        rows, trip = self.visit([True, False], gap=0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM bio_sales").fetchone()[0], 2)
        self.assertEqual({k: trip[k] for k in ("sold", "predicted", "matched")}, {"sold": 2, "predicted": 1, "matched": 1})
        states = sorted(r["state"] for r in self.state.organics(36500)["rows"])
        self.assertEqual(states, ["sold", "sold"])

    def test_old_bio_sales_table_is_rebuilt(self):   # Codex C1: the old key could not keep two sales in one second
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "old.sqlite")
        try:
            old = sqlite3.connect(path)
            old.executescript("""CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE bio_sales (ts TEXT PRIMARY KEY, species INTEGER, bio_data TEXT);
                INSERT INTO meta VALUES ('parser_version', '37');
                INSERT INTO bio_sales VALUES ('2026-01-02T00:00:00Z', 1, '[]');""")
            old.commit()
            old.close()
            db = ed_outrider.open_db(path)
            try:
                pk = [r["name"] for r in db.execute("PRAGMA table_info(bio_sales)") if r["pk"]]
                self.assertEqual(pk, ["ts", "source"])
                self.assertEqual(db.execute("SELECT count(*) FROM bio_sales").fetchone()[0], 0)   # re-read from the journals
            finally:
                db.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_old_sale_events_gain_the_column(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "old.sqlite")
        try:
            old = sqlite3.connect(path)
            old.executescript("""CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE sale_events (ts TEXT, kind TEXT, base INTEGER, bonus INTEGER, total INTEGER, systems INTEGER,
                                          species INTEGER, source TEXT, PRIMARY KEY (ts, kind, source));
                CREATE TABLE sale_estimates (ts TEXT, kind TEXT, estimate INTEGER, PRIMARY KEY (ts, kind));
                INSERT INTO meta VALUES ('parser_version', '30');
                INSERT INTO sale_events VALUES ('2026-01-02T00:00:00Z', 'bio', 1, 0, 1, 0, 1, 'j:1');
                INSERT INTO sale_estimates VALUES ('2026-01-02T00:00:00Z', 'bio', 2);""")
            old.commit()
            old.close()
            db = ed_outrider.open_db(path)   # PARSER_VERSION 31: the sales are re-read to gain their check
            try:
                self.assertIn("x5_check", [r["name"] for r in db.execute("PRAGMA table_info(sale_events)")])
                self.assertEqual(db.execute("SELECT count(*) FROM sale_events").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT estimate FROM sale_estimates").fetchone()[0], 2)   # live only: kept
            finally:
                db.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    # ---- P5: the run in progress elsewhere ----
    def test_run_elsewhere_and_discard_card(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1, "StarPos": [0, 0, 0]})
        for b in (4, 5):
            self.j.handle(self.body_scan("2026-01-01T00:01:00Z", b, False))
        self.j.handle(self.organic("2026-01-01T00:10:00Z", 4, "Log", self.TUSSOCK, "Tussock Pennata"))
        self.j.handle(self.organic("2026-01-01T00:12:00Z", 4, "Sample", self.TUSSOCK, "Tussock Pennata"))
        self.j.status_json = {"live": True, "ts": "2026-01-01T00:20:00Z", "fuel_main": 10, "flags": 0, "flags2": 1,
                              "body": "Sys 5", "lat": 0.0, "lon": 0.0, "planet_radius": 1_000_000}
        e = self.state.sampling_summary()["elsewhere"]
        self.assertEqual((e["species"], e["samples"], e["body"], e["system"]), ("Tussock Pennata", 2, "4", None))
        self.assertEqual(e["value"], outrider.bio.species_value("Tussock Pennata") * 5)
        # an old Log (a re-read) discards it silently; a live one leaves a card
        seq = self.j.moment_seq
        now = ed_outrider.iso_ts(time.time())
        self.j.handle(self.organic(now, 5, "Log", self.STRATUM, "Stratum Tectonicas"))
        m = [x for x in self.j.moments if x["seq"] > seq and x["kind"] == "bio_dropped"]
        self.assertEqual([(x["species"], x["body"], x["elsewhere"]) for x in m], [("Tussock Pennata", "4", False)])
        self.assertIsNone(self.db.execute("SELECT 1 FROM own_organic WHERE body_id = 4").fetchone())
        self.db.execute("INSERT INTO own_organic VALUES (1, 4, 'x', 'Bacterium', 'Bacterium Aurasus', NULL, 2, NULL, '2026-01-01T00:30:00Z')")
        seq = self.j.moment_seq
        self.j.handle(self.organic("2026-01-01T00:40:00Z", 5, "Log", self.TUSSOCK, "Tussock Pennata"))
        self.assertEqual([x for x in self.j.moments if x["seq"] > seq and x["kind"] == "bio_dropped"], [])

    # ---- P10: the region crossing ----
    def jump(self, ts, id64, z):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [0, 0, z]})

    def regions(self, seq=0):
        return [(m["region"], m["spoken"], m["count"]) for m in self.j.moments if m["kind"] == "region" and m["seq"] > seq]

    def test_region_crossing_once(self):
        if not outrider.bio.available():
            self.skipTest("no bio rules")
        for i, (name, region) in enumerate((("Stratum Tectonicas - Green", "Inner Orion Spur"), ("Aleoida Spica - Yellow", "Inner Orion Spur"),
                                            ("Aleoida Laminiae - Teal", "Inner Orion Spur"), ("Tussock Pennata - Red", "Inner Orion Spur"),
                                            ("Fumarole", "Inner Orion Spur"), ("Tussock Pennata - Red", "Inner Scutum-Centaurus Arm"))):
            self.db.execute("INSERT INTO codex (ts, entry_id, name, region) VALUES (?, ?, ?, ?)", (f"2025-01-01T00:00:0{i}Z", i, name, region))
        self.jump("2026-01-01T00:00:00Z", 1, 0)         # first position known: nothing (the startup Location)
        self.assertEqual(self.regions(), [])
        self.jump("2026-01-01T00:01:00Z", 2, 9000)      # into the Inner Scutum-Centaurus Arm: once
        # Stratum (no region rule) and Aleoida Laminiae; Spica cannot grow there, Tussock is logged there, Fumarole is no species
        self.assertEqual(self.regions(), [("Inner Scutum-Centaurus Arm", "the Inner Scutum-Centaurus Arm", 2)])
        self.assertEqual(self.state.region_crossed(2), {"region": "Inner Scutum-Centaurus Arm", "spoken": "the Inner Scutum-Centaurus Arm", "count": 2})
        seq = self.j.moment_seq
        cp = self.j.checkpoint()
        self.jump("2026-01-01T00:02:00Z", 3, 0)         # back and forth along the border: nothing more
        self.jump("2026-01-01T00:03:00Z", 4, 9000)
        self.assertEqual(self.regions(seq), [])
        self.assertIsNone(self.state.region_crossed(4))   # a later arrival is not the crossing
        self.j.restore(cp)                              # a rolled-back tick keeps the announced set
        self.assertIn("Inner Scutum-Centaurus Arm", self.j.regions_said)
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T00:00:00Z", "Commander": "X"})   # a new session
        self.jump("2026-01-02T00:01:00Z", 5, 0)
        self.assertEqual(self.regions(seq), [("Inner Orion Spur", "the Inner Orion Spur", 0)])
        self.assertEqual([ed_outrider.region_spoken(n) for n in ("Norma Arm", "The Veils", "Ryker's Hope", "Izanami", "Mare Somnia")],
                         ["the Norma Arm", "the Veils", "Ryker's Hope", "Izanami", "Mare Somnia"])

    # ---- P17: jumponium ----
    def test_jumponium_limits(self):
        short = outrider.materials.jumponium_short
        c = {"carbon": 10, "germanium": 10, "arsenic": 2, "niobium": 2, "yttrium": 2, "polonium": 10, "vanadium": 10, "cadmium": 10}
        self.assertEqual(short(c), {"arsenic": 2, "yttrium": 2})    # the tie set, niobium (not scarce) left out
        self.assertEqual(short(dict(c, arsenic=3, niobium=3, yttrium=3)), {})   # 3 premium boosts: not short
        self.assertEqual(short(dict(c, cadmium=1)), {"arsenic": 2, "yttrium": 2, "cadmium": 1})   # standard at 1 too
        pick = outrider.materials.jumponium_pick
        self.assertIsNone(pick([{"Name": "yttrium", "Percent": 0.8}, {"Name": "iron", "Percent": 20}], {"yttrium": 2}))   # under the floor
        self.assertEqual(pick([{"Name": "arsenic", "Percent": 1.6}, {"Name": "yttrium", "Percent": 1.3}], {"arsenic": 2, "yttrium": 1}),
                         {"material": "yttrium", "pct": 1.3})      # the scarcest held wins over a richer share
        self.assertIsNone(pick([{"Name": "arsenic", "Percent": 1.2}], {"arsenic": 2}))   # grade 2-3 floor 1.5%

    def mats_login(self, snap_ts="2026-01-01T00:00:05Z"):
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:00Z", "Commander": "X"})
        self.j.handle({"event": "Materials", "timestamp": snap_ts, "Raw": [{"Name": n, "Count": c} for n, c in (
            ("carbon", 10), ("germanium", 10), ("arsenic", 10), ("niobium", 10), ("yttrium", 10), ("polonium", 1), ("vanadium", 10), ("cadmium", 10))]})
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:01:00Z", "StarSystem": "Sys", "SystemAddress": 1, "StarPos": [0, 0, 0]})

    def rich(self, ts, body_id, pct, landable=True):
        return self.body_scan(ts, body_id, False, Landable=landable, Materials=[{"Name": "iron", "Percent": 20.0}, {"Name": "polonium", "Percent": pct}])

    def test_jumponium_fss_and_alone(self):
        self.mats_login()
        self.j.handle(self.rich("2026-01-01T00:02:00Z", 3, 1.3))
        self.j.handle(self.rich("2026-01-01T00:02:10Z", 4, 1.1))   # a lower share in the same system: silent
        self.j.handle(self.rich("2026-01-01T00:02:20Z", 5, 2.0, landable=False))   # not landable
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:03:00Z", "SystemName": "Sys", "SystemAddress": 1, "Count": 6})
        fss = [m for m in self.j.moments if m["kind"] == "fss_done"]
        self.assertEqual(fss[-1]["jumponium"], {"body": "3", "material": "polonium", "name": "Polonium", "pct": 1.3})
        self.assertEqual([m for m in self.j.moments if m["kind"] == "jumponium"], [])
        self.j.handle(self.rich("2026-01-01T00:04:00Z", 6, 1.8))   # richer, after the debrief: said alone
        self.assertEqual([m["jumponium"]["body"] for m in self.j.moments if m["kind"] == "jumponium"], ["6"])
        # no FSS finished in the next system: said when the FSD charges to leave
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:10:00Z", "StarSystem": "Two", "SystemAddress": 2, "StarPos": [0, 0, 5]})
        self.j.handle(self.rich("2026-01-01T00:11:00Z", 1, 1.5) | {"SystemAddress": 2, "StarSystem": "Two", "BodyName": "Two 1"})
        self.j.handle({"event": "StartJump", "timestamp": "2026-01-01T00:12:00Z", "JumpType": "Hyperspace", "StarSystem": "Three",
                       "SystemAddress": 3, "StarClass": "K"})
        said = [m for m in self.j.moments if m["kind"] == "jumponium"]
        self.assertEqual((said[-1]["system"], said[-1]["jumponium"]["body"]), (2, "1"))

    def test_jumponium_silent_when_counts_are_stale(self):
        self.mats_login(snap_ts="2025-12-31T00:00:00Z")   # the login wrote no Materials line: yesterday's counts
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:30Z", "Commander": "X"})
        self.j.handle(self.rich("2026-01-01T00:02:00Z", 3, 1.3))
        self.assertIsNone(self.j.jumponium)


class SaleLeft(unittest.TestCase):
    """A sale that leaves data aboard: said once the pages stop and a fresh estimate has run, live sales only."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.base = time.time()

    def at(self, s, ev):
        """Handle ev as a journal line read s seconds after the test's start (its timestamp then too)."""
        with unittest.mock.patch.object(ed_outrider.time, "time", lambda: self.base + s):
            self.j.handle(dict(ev, timestamp=ed_outrider.iso_ts(self.base + s)))

    def page(self, s, systems, earned):
        self.at(s, {"event": "MultiSellExplorationData", "TotalEarnings": earned, "BaseValue": earned, "Bonus": 0,
                    "Discovered": [{"SystemName": f"S{i}", "NumBodies": 3} for i in range(systems)]})

    def estimate(self, started, systems=0, payout=0, firsts=0, samples=0, bio=0):
        self.state.unsold = {"carto": {"systems": systems, "estimated_payout": payout, "first_discoveries": firsts},
                             "bio": {"samples": samples, "estimated_value": bio}}
        self.state.unsold_from = self.base + started

    def kinds(self):
        return [m for m in self.j.moments if m["kind"] in ("sale_left", "bio_left")]

    def test_one_page_with_data_left(self):
        self.estimate(-30, 93, 16800000, 300)            # before the sale: it cannot say what the sale left
        self.page(0, 50, 14814687)
        self.state.maybe_sale_left(self.base + 5)
        self.state.maybe_sale_left(self.base + Q + 2)    # quiet long enough, but no estimate since the page
        self.assertEqual(self.kinds(), [])
        self.estimate(3, 43, 2026392, 270)
        self.state.maybe_sale_left(self.base + Q + 10)
        m = self.kinds()
        self.assertEqual(len(m), 1)
        self.assertEqual({k: m[0][k] for k in ("kind", "sold_systems", "sold_value", "left_systems", "left_value", "left_firsts")},
                         {"kind": "sale_left", "sold_systems": 50, "sold_value": 14814687, "left_systems": 43,
                          "left_value": 2026392, "left_firsts": 270})
        self.assertIsNone(self.j.sale_run)
        self.state.maybe_sale_left(self.base + Q + 30)   # said once
        self.assertEqual(len(self.kinds()), 1)

    def test_three_pages_all_sold(self):
        self.page(0, 50, 14000000)
        self.estimate(1, 60, 9000000, 100)               # between pages: data left, but the sale is still going
        self.state.maybe_sale_left(self.base + 3)
        self.page(4, 50, 9000000)
        self.estimate(5, 10, 1000000, 20)
        self.state.maybe_sale_left(self.base + 7)
        self.page(8, 10, 1000000)
        self.state.maybe_sale_left(self.base + Q + 12)   # the page-2 estimate is older than the last page
        self.state.maybe_sale_left(self.base + Q + 19)
        self.assertEqual(self.kinds(), [])
        self.assertEqual((self.j.sale_run["systems"], self.j.sale_run["carto"]), (110, 24000000))
        self.estimate(10)                                # everything sold
        self.state.maybe_sale_left(self.base + Q + 25)
        self.assertEqual(self.kinds(), [])
        self.assertIsNone(self.j.sale_run)

    def test_three_pages_with_data_left_counts_the_whole_sale(self):
        for s in (0, 3, 6):
            self.page(s, 50, 5000000)
        self.estimate(8, 43, 2000000, 270)
        self.state.maybe_sale_left(self.base + Q + 20)
        m = self.kinds()
        self.assertEqual([(x["sold_systems"], x["sold_value"], x["left_systems"]) for x in m], [(150, 15000000, 43)])

    def test_replayed_sale_says_nothing(self):
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": "2026-01-01T01:00:00Z", "TotalEarnings": 5000,
                       "Discovered": [{"SystemName": "Sys", "NumBodies": 3}]})
        self.assertIsNone(self.j.sale_run)
        self.estimate(10, 43, 2000000, 270)
        self.state.maybe_sale_left(self.base + Q + 60)
        self.assertEqual(self.kinds(), [])
        self.assertEqual(self.j.last_sale["carto"], 5000)   # the sale itself still counts

    def test_bio_left(self):
        self.at(0, {"event": "SellOrganicData", "BioData": [{"Value": 1000000, "Bonus": 4000000}] * 3})
        self.estimate(2, 40, 3000000, 10, samples=2, bio=30000000)
        self.state.maybe_sale_left(self.base + Q + 20)
        m = self.kinds()
        self.assertEqual([(x["kind"], x["sold_species"], x["sold_value"], x["left_samples"], x["left_value"]) for x in m],
                         [("bio_left", 3, 15000000, 2, 30000000)])   # cartographics aboard: not this sale's news

    def test_carto_sale_says_nothing_of_bio(self):
        self.page(0, 20, 3000000)
        self.estimate(2, samples=4, bio=50000000)
        self.state.maybe_sale_left(self.base + Q + 20)
        self.assertEqual(self.kinds(), [])

    def test_failed_tick_does_not_double_the_run(self):
        self.page(0, 50, 1000)
        cp = self.j.checkpoint()
        self.page(2, 50, 1000)
        self.j.restore(cp)
        self.assertEqual(self.j.sale_run["systems"], 50)


class SalesAndBioValue(unittest.TestCase):
    """Review 2026-10-01 batch B: footfall pricing through the journal reader, nav beacons, partial Vista Genomics
    sales, the sale-left wait, the bio ledger and a failed tick's sales."""

    def setUp(self):
        import tempfile, types
        self.tmp = tempfile.mkdtemp()
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def journal(self, events):
        """A journal folder holding these events: what read_events (and so the server's estimate) reads."""
        d = os.path.join(self.tmp, f"j{len(os.listdir(self.tmp))}")
        os.makedirs(d)
        with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "w") as f:
            for e in [{"timestamp": "2026-01-01T00:00:00Z", "event": "LoadGame", "Commander": "X"}] + events:
                f.write(json.dumps(e) + "\n")
        return d

    def unsold(self, events):
        return outrider.unsold.analyse(outrider.unsold.read_events([self.journal(events)]), ARGS)

    @staticmethod
    def body(ts, body_id, footfalled, scan_type="Detailed", disc=True):
        return {"timestamp": ts, "event": "Scan", "ScanType": scan_type, "BodyName": f"Sys {body_id}", "BodyID": body_id,
                "StarSystem": "Sys", "SystemAddress": 1, "PlanetClass": "Rocky body", "MassEM": 0.1, "TerraformState": "",
                "DistanceFromArrivalLS": 500.0, "WasDiscovered": disc, "WasMapped": False, "WasFootfalled": footfalled}

    @staticmethod
    def analysed(ts, body_id, species="$Codex_Ent_Bacterial_01_Name;"):
        return {"timestamp": ts, "event": "ScanOrganic", "ScanType": "Analyse", "Species": species,
                "SystemAddress": 1, "Body": body_id}

    @staticmethod
    def bio_sale(ts, *entries):
        return {"timestamp": ts, "event": "SellOrganicData",
                "BioData": [{"Species": sp, "Value": 1000000, "Bonus": bonus} for sp, bonus in entries]}

    # ---- R1: the reader keeps WasFootfalled, so each run is priced x5 or x1 from its body's scan ----
    def test_footfall_survives_the_journal_reader(self):
        b = self.unsold([self.body("2026-01-01T01:00:00Z", 5, False), self.analysed("2026-01-01T01:10:00Z", 5),
                         self.body("2026-01-01T02:00:00Z", 6, True), self.analysed("2026-01-01T02:10:00Z", 6)])["exobiology"]
        self.assertEqual((b["x5_runs"], b["x1_runs"], b["unknown_runs"]), (1, 1, 0))
        self.assertEqual(b["estimated_value"], 6000000)

    # ---- R6: Universal Cartographics does not buy nav-beacon scans ----
    def test_nav_beacon_scans_are_not_unsold_data(self):
        ex = self.unsold([self.body("2026-01-01T01:00:00Z", 5, False, "NavBeaconDetail", disc=False),
                          self.body("2026-01-01T01:00:00Z", 6, False, "NavBeacon", disc=False)])["exploration"]
        self.assertEqual((ex["bodies"], ex["systems"], ex["first_discoveries"]), (0, 0, 0))
        ex = self.unsold([self.body("2026-01-01T01:00:00Z", 5, False, "NavBeaconDetail", disc=False),
                          self.body("2026-01-01T02:00:00Z", 5, False, "Detailed", disc=True)])["exploration"]
        self.assertEqual((ex["bodies"], ex["first_discoveries"]), (1, 0))   # your own scan of it still counts

    # ---- R7: a Vista Genomics sale takes only the species it names ----
    def test_partial_bio_sale_leaves_the_rest_aboard(self):
        cerbrus, stratum = "$Codex_Ent_Bacterial_12_Name;", "$Codex_Ent_Stratum_07_Name;"
        runs = [self.body("2026-01-01T00:50:00Z", 2, True), self.body("2026-01-01T00:51:00Z", 3, True),
                self.analysed("2026-01-01T01:00:00Z", 2, cerbrus), self.analysed("2026-01-01T02:00:00Z", 3, stratum)]
        b = self.unsold(runs + [self.bio_sale("2026-01-01T03:00:00Z", (cerbrus, 0))])["exobiology"]
        self.assertEqual((b["samples"], [r["species"] for r in b["rows"]], b["estimated_value"]),
                         (1, ["Stratum Tectonicas"], 19010800))
        b = self.unsold(runs + [self.bio_sale("2026-01-01T03:00:00Z", (cerbrus, 0), (stratum, 0))])["exobiology"]
        self.assertEqual(b["samples"], 0)                                            # a full sale empties it
        b = self.unsold(runs + [self.bio_sale("2026-01-01T03:00:00Z", (cerbrus, 0)),
                                {"timestamp": "2026-01-01T04:00:00Z", "event": "Died"}])["exobiology"]
        self.assertEqual(b["samples"], 0)                                            # a death takes the rest

    def test_bio_sale_takes_the_run_its_bonus_says(self):
        aurasus = "$Codex_Ent_Bacterial_01_Name;"
        runs = [self.body("2026-01-01T00:50:00Z", 2, True), self.body("2026-01-01T00:51:00Z", 3, False),
                self.analysed("2026-01-01T01:00:00Z", 2), self.analysed("2026-01-01T02:00:00Z", 3)]
        b = self.unsold(runs + [self.bio_sale("2026-01-01T03:00:00Z", (aurasus, 4000000))])["exobiology"]
        self.assertEqual((b["samples"], b["x5_runs"], b["x1_runs"]), (1, 0, 1))      # the x5 run was the one sold
        b = self.unsold(runs + [self.bio_sale("2026-01-01T03:00:00Z", (aurasus, 0))])["exobiology"]
        self.assertEqual((b["samples"], b["x5_runs"], b["x1_runs"]), (1, 1, 0))

    def test_bio_left_fires_from_the_real_estimate(self):
        now = time.time()
        cerbrus, stratum = "$Codex_Ent_Bacterial_12_Name;", "$Codex_Ent_Stratum_07_Name;"
        d = self.journal([self.analysed(ed_outrider.iso_ts(now - 600), 2, cerbrus),
                          self.analysed(ed_outrider.iso_ts(now - 300), 3, stratum)])
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]), \
                unittest.mock.patch.object(ed_outrider, "LEGACY_DIRS", []):
            self.j.handle(dict(self.bio_sale(ed_outrider.iso_ts(now), (cerbrus, 0)), timestamp=ed_outrider.iso_ts(now)))
            with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "a") as f:
                f.write(json.dumps(self.bio_sale(ed_outrider.iso_ts(now), (cerbrus, 0))) + "\n")
            self.state.unsold = ed_outrider.compute_unsold()
        self.state.unsold_from = now + 1
        self.state.maybe_sale_left(now + ed_outrider.SALE_QUIET_S + 5)
        m = [x for x in self.j.moments if x["kind"] == "bio_left"]
        self.assertEqual([(x["sold_species"], x["left_samples"]) for x in m], [(1, 1)])

    # ---- R5: the pages of one sale come up to a minute apart ----
    def test_sale_left_waits_out_the_real_page_gaps(self):
        base = time.time()

        def page(s, n):
            with unittest.mock.patch.object(ed_outrider.time, "time", lambda: base + s):
                self.j.handle({"event": "MultiSellExplorationData", "timestamp": ed_outrider.iso_ts(base + s),
                               "TotalEarnings": 1000, "BaseValue": 1000, "Bonus": 0,
                               "Discovered": [{"SystemName": f"S{s}-{i}", "NumBodies": 3} for i in range(n)]})

        def estimate(s, systems):
            self.state.unsold = {"carto": {"systems": systems, "estimated_payout": systems * 100000, "first_discoveries": 0},
                                 "bio": {"samples": 0, "estimated_value": 0}}
            self.state.unsold_from = base + s
        # one player's real sales: 50-system pages 24, 14, 13 s apart, and a 49-system page followed 67 s later
        for s, n, left in ((0, 50, 110), (24, 50, 60), (38, 50, 10), (51, 49, 0)):
            page(s, n)
            estimate(s + 1, left)
            for t in range(s + 2, s + 67, 5):
                self.state.maybe_sale_left(base + t)
        page(118, 10)
        estimate(119, 5)
        for t in range(120, 118 + ed_outrider.SALE_QUIET_S, 5):
            self.state.maybe_sale_left(base + t)
        self.assertEqual([m for m in self.j.moments if m["kind"] == "sale_left"], [])
        self.state.maybe_sale_left(base + 118 + ed_outrider.SALE_QUIET_S + 1)
        m = [m for m in self.j.moments if m["kind"] == "sale_left"]
        self.assertEqual([(x["sold_systems"], x["left_systems"]) for x in m], [(209, 5)])   # once, for the whole sale

    # ---- R2 / R13: the bio side of the trip ledger ----
    def sell_bio(self, ts, n, source):
        self.j.line_source = source
        self.j.handle({"event": "SellOrganicData", "timestamp": ts,
                       "BioData": [{"Species": "$Codex_Ent_Bacterial_01_Name;", "Value": 1000000, "Bonus": 0}] * n})

    def sell_carto(self, ts, source):
        self.j.line_source = source
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": ts, "Discovered": [], "BaseValue": 1, "Bonus": 0,
                       "TotalEarnings": 1})

    def test_bio_visit_in_several_goes_is_one_estimate(self):
        t = lambda sec: ed_outrider.iso_ts(time.time() - 1800 + sec)
        self.state.unsold_log = [(t(-5), {"carto": {"estimated_payout": 0}, "bio": {"estimated_value": 5000000}})]
        self.sell_bio(t(0), 3, "J:1")
        self.sell_bio(t(11), 2, "J:2")                   # 11 s later: no fresh estimate in between
        self.state.note_sale_estimates()
        self.sell_carto(t(200), "J:3")
        tr = self.state.ledger()["trips"][0]
        self.assertEqual((tr["paid_bio"], tr["estimate_bio"], tr["paid_bio_estimated"]), (5000000, 5000000, 5000000))

    def test_bio_sales_after_the_last_carto_sale_show_as_the_trip_under_way(self):
        self.sell_carto("2025-12-01T00:00:00Z", "J:1")
        self.sell_bio("2026-01-02T00:00:00Z", 2, "J:2")
        L = self.state.ledger()
        self.assertEqual([t["paid_bio"] for t in L["trips"]], [0])
        cur = L["current"]
        self.assertEqual((cur["start"], cur["end"], cur["paid_bio"], cur["paid_carto"], cur["x5"]["sold"]),
                         ("2025-12-01T00:00:00Z", None, 2000000, None, 2))
        self.sell_carto("2026-01-03T00:00:00Z", "J:3")   # the next carto sale closes it
        L = self.state.ledger()
        self.assertIsNone(L["current"])
        self.assertEqual([t["paid_bio"] for t in L["trips"]], [2000000, 0])

    def test_bio_only_player_gets_a_trip(self):
        self.sell_bio("2026-01-02T00:00:00Z", 1, "J:1")
        L = self.state.ledger()
        self.assertEqual((L["trips"], L["current"]["start"], L["current"]["paid"]), ([], None, 1000000))

    # ---- R18: a failure after the commit keeps the tick's sales for their estimate ----
    def test_post_commit_failure_keeps_the_sale_for_its_estimate(self):
        import contextlib, io
        now = time.time()
        d = os.path.join(self.tmp, "live")
        os.makedirs(d)
        with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "w") as f:
            f.write(json.dumps({"timestamp": ed_outrider.iso_ts(now - 30), "event": "MultiSellExplorationData",
                                "Discovered": [{"SystemName": "A", "NumBodies": 1}], "BaseValue": 9, "Bonus": 0,
                                "TotalEarnings": 9}, separators=(",", ":")) + "\n")
        self.state.unsold_log = [(ed_outrider.iso_ts(now - 60), {"carto": {"estimated_payout": 42}, "bio": {"estimated_value": 0}})]
        quiet = ("maybe_refresh", "maybe_classify_target", "maybe_unsold", "maybe_sale_left", "maybe_locate_carrier",
                 "maybe_find_sellers", "maybe_backup_on_quit")
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]))
            for name in quiet:
                stack.enter_context(unittest.mock.patch.object(self.state, name, lambda: None))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            with unittest.mock.patch.object(self.state, "watch_status", side_effect=sqlite3.OperationalError("database is locked")):
                self.state.tick({})
            self.assertTrue(self.state.tail_error)
            self.state.tick({})
        self.assertIsNone(self.state.tail_error)
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT kind, estimate FROM sale_estimates")], [("carto", 42)])

    def test_failed_estimate_insert_keeps_the_sales(self):
        now = time.time()
        self.sell_carto(ed_outrider.iso_ts(now - 30), "J:1")
        self.state.unsold_log = [(ed_outrider.iso_ts(now - 60), {"carto": {"estimated_payout": 42}, "bio": {"estimated_value": 0}})]
        real, db = self.db, unittest.mock.MagicMock()
        db.execute.side_effect = sqlite3.OperationalError("database is locked")
        self.state.db = db
        with self.assertRaises(sqlite3.OperationalError):
            self.state.note_sale_estimates()
        self.state.db = real
        self.assertEqual(len(self.j.new_sales), 1)
        self.state.note_sale_estimates()
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT kind, estimate FROM sale_estimates")], [("carto", 42)])


class RescanChecklist(unittest.TestCase):
    """My firsts as a rescan checklist: first discoveries and first maps lost with a ship, scanned (and mapped) again
    since, until they are sold; worked out from the journal tables alone (firsts_recovery)."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types_ns(cached=lambda i: (None, None)), 25)

    def jump(self, ts, name, id64, x=0):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": name, "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def scans(self, ts, name, id64, bodies):
        for b in bodies:
            self.j.handle(scan(ts, name, id64, b, f"{name} A" if b == 1 else f"{name} A {b}", star=b == 1)[2])
        self.db.commit()

    def dss(self, ts, name, id64, body):
        self.j.handle({"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": id64, "BodyID": body,
                       "BodyName": f"{name} A {body}", "ProbesUsed": 4, "EfficiencyTarget": 6})
        self.db.commit()

    def die(self, ts, option="rebuy"):
        self.j.handle({"event": "Died", "timestamp": ts})
        self.j.handle({"event": "Resurrect", "timestamp": ts, "Option": option})
        self.db.commit()

    def entry(self, name):
        """The firsts_list entry, with recover's to-do lists as plain names (the values are tested apart, from
        self.values and self.items)."""
        self.state._firsts_cache = None
        e = next((x for x in self.state.firsts_list() if x["name"] == name), None)
        if e and e["recover"]:
            r = e["recover"] = dict(e["recover"])
            self.values = {k: r.pop(k) for k in ("lost_scan", "lost_map", "lost_total")}
            self.items = {k: r[k] for k in ("todo_scan", "todo_map")}
            r.update({k: [t["name"] for t in r[k]] for k in ("todo_scan", "todo_map")})
        return e

    def test_lost_rescanned_and_sold(self):
        self.jump("2026-01-01T00:00:00Z", "Lossy", 5)
        self.scans("2026-01-01T00:01:00Z", "Lossy", 5, [1, 2, 3, 4])
        self.dss("2026-01-01T00:02:00Z", "Lossy", 5, 2)
        self.jump("2026-01-01T00:10:00Z", "Gone", 8, x=20)
        self.scans("2026-01-01T00:11:00Z", "Gone", 8, [1, 2])
        e = self.entry("Lossy")
        self.assertEqual((e["state"], e["sale"], e["recover"]), ("unsold", "unsold", None))   # nothing lost yet
        self.die("2026-01-01T01:00:00Z")
        e = self.entry("Lossy")
        self.assertEqual((e["state"], e["sale"]), ("lost", "lost"))
        self.assertEqual(e["recover"], {"lost_bodies": 4, "rescanned": 0, "maps_lost": 1, "maps_redone": 0,
                                        "todo_scan": ["A", "A 2", "A 3", "A 4"], "todo_map": ["A 2"]})
        # a rebuy that kept the ship (recover) loses nothing more; a system found after the loss is never on it
        self.die("2026-01-01T01:30:00Z", option="recover")
        self.jump("2026-01-01T02:00:00Z", "Clean", 6, x=40)
        self.scans("2026-01-01T02:01:00Z", "Clean", 6, [1, 2])
        # back later: two of the four scanned again -- part-way, still on the checklist, and unsold data again
        self.jump("2026-01-02T00:00:00Z", "Lossy", 5)
        self.scans("2026-01-02T00:01:00Z", "Lossy", 5, [1, 3])
        e = self.entry("Lossy")
        self.assertEqual((e["state"], e["sale"]), ("lost", "unsold"))
        self.assertEqual(e["recover"], {"lost_bodies": 4, "rescanned": 2, "maps_lost": 1, "maps_redone": 0,
                                        "todo_scan": ["A 2", "A 4"], "todo_map": ["A 2"]})
        # every body scanned again (body 2's Scan too), but its lost first map needs a new DSS
        self.scans("2026-01-02T00:02:00Z", "Lossy", 5, [2, 4])
        e = self.entry("Lossy")
        self.assertEqual((e["state"], e["recover"]), ("lost", {"lost_bodies": 4, "rescanned": 4, "maps_lost": 1, "maps_redone": 0,
                                                             "todo_scan": [], "todo_map": ["A 2"]}))
        self.dss("2026-01-02T00:03:00Z", "Lossy", 5, 2)
        e = self.entry("Lossy")
        self.assertEqual((e["state"], e["sale"]), ("rescanned", "unsold"))
        self.assertEqual(e["recover"], {"lost_bodies": 4, "rescanned": 4, "maps_lost": 1, "maps_redone": 1,
                                        "todo_scan": [], "todo_map": []})
        self.assertEqual(e["bodies_by"], {"sold": 0, "unsold": 4, "lost": 0})
        # a system never lost is not on the checklist; one lost and never revisited is, with nothing rescanned
        c, g = self.entry("Clean"), self.entry("Gone")
        self.assertEqual((c["state"], c["sale"], c["recover"]), ("unsold", "unsold", None))
        self.assertEqual((g["state"], g["sale"], g["recover"]), ("lost", "lost", {"lost_bodies": 2, "rescanned": 0,
                                                                                  "maps_lost": 0, "maps_redone": 0,
                                                                                  "todo_scan": ["A", "A 2"], "todo_map": []}))
        # the watch and the Unsold tile's count treat the rescanned system as unsold, as the clean one; not the lost one
        self.assertTrue(ed_outrider.firsts_watched(e))
        self.assertTrue(ed_outrider.firsts_watched(c))
        self.assertFalse(ed_outrider.firsts_watched(g))
        self.state.firsts_watch_on = True
        self.state.system_values = {"Lossy": 5_000_000, "Clean": 100}
        self.assertEqual(self.state.firsts_watch_info(), {"on": True, "seen": 0, "checked": 0, "of": 2})
        self.assertEqual(self.state.firsts_watch_due(ed_outrider.ts_seconds("2026-01-03T00:00:00Z")), (5, "Lossy"))
        # sold: gone from the list, as any sold system
        self.j.handle(sale("2026-01-03T00:00:00Z", ["Lossy"])[2])
        self.db.commit()
        self.assertIsNone(self.entry("Lossy"))
        self.assertEqual((self.entry("Clean")["state"], self.entry("Gone")["state"]), ("unsold", "lost"))

    def test_todo_names_what_is_left_short_and_in_natural_order(self):
        # the rescan checklist's to-do lists: short body names still to scan (FSS) and maps still to redo (DSS),
        # naturally sorted (A 10 after A 3); empty once everything is back
        self.jump("2026-01-01T00:00:00Z", "Todo", 9)
        self.scans("2026-01-01T00:01:00Z", "Todo", 9, [1, 2, 3, 10, 11])
        self.dss("2026-01-01T00:02:00Z", "Todo", 9, 10)
        self.dss("2026-01-01T00:02:30Z", "Todo", 9, 3)
        self.die("2026-01-01T01:00:00Z")
        self.jump("2026-01-02T00:00:00Z", "Todo", 9)
        self.scans("2026-01-02T00:01:00Z", "Todo", 9, [1, 3])
        self.dss("2026-01-02T00:02:00Z", "Todo", 9, 3)
        r = self.entry("Todo")["recover"]
        self.assertEqual((r["rescanned"], r["maps_redone"]), (2, 1))
        self.assertEqual((r["todo_scan"], r["todo_map"]), (["A 2", "A 10", "A 11"], ["A 10"]))
        self.scans("2026-01-02T00:03:00Z", "Todo", 9, [2, 10, 11])
        r = self.entry("Todo")["recover"]
        self.assertEqual((r["todo_scan"], r["todo_map"]), ([], ["A 10"]))   # every body back, one map to redo
        self.dss("2026-01-02T00:04:00Z", "Todo", 9, 10)
        e = self.entry("Todo")
        self.assertEqual((e["state"], e["recover"]["todo_scan"], e["recover"]["todo_map"]), ("rescanned", [], []))

    def test_never_lost_and_partly_rescanned_stays_watched(self):
        self.jump("2026-01-01T00:00:00Z", "Safe", 7)
        self.scans("2026-01-01T00:01:00Z", "Safe", 7, [1, 2])
        self.die("2026-01-01T00:30:00Z", option="recover")   # the ship survived: no loss
        e = self.entry("Safe")
        self.assertEqual((e["state"], e["sale"], e["recover"]), ("unsold", "unsold", None))
        self.assertTrue(ed_outrider.firsts_watched(e))
        # lost, then only one body scanned again: the headline is unsold, so the watch keeps looking at it
        self.die("2026-01-01T01:00:00Z")
        self.scans("2026-01-01T02:00:00Z", "Safe", 7, [2])
        e = self.entry("Safe")
        self.assertEqual((e["state"], e["sale"], e["recover"]["rescanned"], e["recover"]["lost_bodies"]), ("lost", "unsold", 1, 2))
        self.assertTrue(ed_outrider.firsts_watched(e))
        # a sale banks the rescanned body; the one still lost stays, with nothing rescanned
        self.j.handle(sale("2026-01-01T03:00:00Z", ["Safe"])[2])
        self.db.commit()
        e = self.entry("Safe")
        self.assertEqual((e["state"], e["sale"], e["recover"]), ("lost", "lost", {"lost_bodies": 1, "rescanned": 0,
                                                                                  "maps_lost": 0, "maps_redone": 0, "todo_scan": ["A"],
                                                                              "todo_map": []}))

    # values: what is still lost, with the bonuses earned, as outrider.unsold.body_value prices it (no efficiency bonus)
    def worth(self, id64, body, mapped):
        rec = json.loads(self.db.execute("SELECT record FROM own_bodies WHERE system=? AND body_id=?", (id64, body)).fetchone()[0])
        return outrider.unsold.body_value(dict(rec["ed"], first_discovered=True, first_mapped=True), mapped, False, True)

    def test_values_of_what_is_still_lost(self):
        self.jump("2026-01-01T00:00:00Z", "Worth", 11)
        self.scans("2026-01-01T00:01:00Z", "Worth", 11, [1, 2, 3, 10])
        self.dss("2026-01-01T00:02:00Z", "Worth", 11, 2)
        self.dss("2026-01-01T00:02:30Z", "Worth", 11, 10)
        star, planet, mapped = self.worth(11, 1, False), self.worth(11, 2, False), self.worth(11, 2, True)
        inc = mapped - planet            # what the map adds on top of the scan
        self.assertTrue(0 < planet < mapped and star > 0)
        self.die("2026-01-01T01:00:00Z")
        # nothing rescanned yet: the full loss (the page hides the pop-up list but shows the values in the row)
        self.entry("Worth")
        self.assertEqual(self.items["todo_scan"], [{"name": "A", "value": star}, {"name": "A 2", "value": planet},
                                                   {"name": "A 3", "value": planet}, {"name": "A 10", "value": planet}])
        self.assertEqual(self.items["todo_map"], [{"name": "A 2", "value": inc}, {"name": "A 10", "value": inc}])
        self.assertEqual(self.values, {"lost_scan": star + 3 * planet, "lost_map": 2 * inc,
                                       "lost_total": star + 3 * planet + 2 * inc})
        # part-way: the star and A 2 scanned again, A 2 remapped
        self.jump("2026-01-02T00:00:00Z", "Worth", 11)
        self.scans("2026-01-02T00:01:00Z", "Worth", 11, [1, 2])
        self.dss("2026-01-02T00:02:00Z", "Worth", 11, 2)
        self.entry("Worth")
        self.assertEqual(self.items["todo_scan"], [{"name": "A 3", "value": planet}, {"name": "A 10", "value": planet}])
        self.assertEqual(self.items["todo_map"], [{"name": "A 10", "value": inc}])
        self.assertEqual(self.values, {"lost_scan": 2 * planet, "lost_map": inc, "lost_total": 2 * planet + inc})
        # every body back, only a map left
        self.scans("2026-01-02T00:03:00Z", "Worth", 11, [3, 10])
        self.entry("Worth")
        self.assertEqual((self.items["todo_scan"], self.items["todo_map"]), ([], [{"name": "A 10", "value": inc}]))
        self.assertEqual(self.values, {"lost_scan": 0, "lost_map": inc, "lost_total": inc})
        # complete: nothing lost any more
        self.dss("2026-01-02T00:04:00Z", "Worth", 11, 10)
        self.assertEqual(self.entry("Worth")["state"], "rescanned")
        self.assertEqual(self.values, {"lost_scan": 0, "lost_map": 0, "lost_total": 0})

    def test_values_match_the_unsold_estimate(self):
        # scan + map of a body both lost add up to what outrider.unsold's own estimate gave those bodies while aboard
        evs = [(T(t), None, e) for t, e in [
            ("2026-01-01T00:00:00Z", {"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Est",
                                      "SystemAddress": 12, "StarPos": [0, 0, 0]})]]
        evs += [scan("2026-01-01T00:01:00Z", "Est", 12, b, "Est A" if b == 1 else f"Est A {b}", star=b == 1) for b in (1, 2, 3)]
        dss = {"event": "SAAScanComplete", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 12, "BodyID": 2,
               "BodyName": "Est A 2", "ProbesUsed": 9, "EfficiencyTarget": 6}
        evs.append((T(dss["timestamp"]), None, dss))
        aboard = [r for r in outrider.unsold.analyse(evs, ARGS)["exploration"]["rows"] if r["system"] == "Est"]
        self.assertEqual(len(aboard), 3)
        for _t, _c, e in evs:
            self.j.handle(e)
        self.db.commit()
        self.die("2026-01-01T01:00:00Z")
        self.entry("Est")
        self.assertEqual(self.values["lost_total"], sum(r["value"] for r in aboard))
        self.assertEqual({t["name"]: t["value"] for t in self.items["todo_map"]},
                         {"A 2": self.worth(12, 2, True) - self.worth(12, 2, False)})


class PopulatedNoX5(unittest.TestCase):
    """Plugin gaps C (BioScan's rule, checked in A on the author's sales: 0 of 8 runs paid x5 in a populated system,
    208 of 208 elsewhere): Vista Genomics pays the first-footfall x5 only where nobody had set foot AND nobody lives."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def system(self, ts, id64, pop, event="FSDJump"):
        ev = {"event": event, "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [id64, 0, 0]}
        if pop is not None:
            ev["Population"] = pop
        self.j.handle(ev)
        self.j.handle({"event": "Scan", "timestamp": ts, "BodyName": f"S{id64} 1", "BodyID": 1, "StarSystem": f"S{id64}",
                       "SystemAddress": id64, "PlanetClass": "Rocky body", "Landable": True, "MassEM": 0.1,
                       "ScanType": "Detailed", "WasDiscovered": True, "WasMapped": False, "WasFootfalled": False})

    def test_populated_pays_no_x5(self):
        self.system("2026-01-01T00:00:00Z", 1, 0)                    # nobody lives here: x5
        self.system("2026-01-01T01:00:00Z", 2, 14655365)             # 14.7 million: x1, footfall or not
        self.system("2026-01-01T02:00:00Z", 3, None)                 # no population given: as most of the galaxy, x5
        self.system("2026-01-01T03:00:00Z", 4, 120, event="Location")
        x5 = {r[0]: r[1] for r in self.db.execute("SELECT system, bio_x5 FROM own_firsts")}
        self.assertEqual(x5, {1: 1, 2: 0, 3: 1, 4: 0})
        self.assertEqual([self.state.body_bio(i, 1)["factor"] for i in (1, 2, 3, 4)], [5, 1, 5, 1])
        # the flag itself still says nobody had set foot (My firsts counts your first footfall there)
        self.assertEqual({r[0] for r in self.db.execute("SELECT was_footfalled FROM own_firsts")}, {0})
        # a re-read rebuilds the populations from the journal
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual(self.db.execute("SELECT count(*) FROM system_population").fetchone()[0], 0)


class NearBody(unittest.TestCase):
    """Plugin gaps C (BioScan's "near surface" focus): in your ship below 5,000 m over a body, the strip shows its card."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def status(self, flags, alt, flags2=0):
        self.j.status_json = {"live": True, "ts": "2026-01-01T00:10:00Z", "flags": flags, "flags2": flags2, "body": "Sys 4",
                              "lat": 1.0, "lon": 2.0, "alt": alt, "planet_radius": 1_000_000}

    def test_flying_low(self):
        ship = ed_outrider.FLAG_IN_MAIN_SHIP
        self.status(ship, 2300.4)
        self.assertEqual(self.state.near_body(), {"body": "4", "full": "Sys 4", "how": "flying low", "alt": 2300, "system": "1"})
        self.assertIsNone(self.state.on_body())
        self.status(ship, 6000)                                          # too high
        self.assertIsNone(self.state.near_body())
        self.status(ship | ed_outrider.FLAG_ALT_AVG, 2000)               # a rough altitude: high up
        self.assertIsNone(self.state.near_body())
        self.status(ship | ed_outrider.FLAG_LANDED, 0)                   # landed: on_body's
        self.assertIsNone(self.state.near_body())
        self.assertEqual(self.state.on_body()["how"], "landed")
        self.status(ed_outrider.FLAG_IN_SRV, 0)                          # the SRV: on_body's
        self.assertIsNone(self.state.near_body())


class FullScanBonus(unittest.TestCase):
    """Plugin gaps D: the sale's Bonus field, 1,000 cr per body of a system you found complete while every star and
    planet was undiscovered (Pioneer's rule, narrowed by the author's sales). In the payout estimate, apart from it."""

    def events(self, disc_planet=False, count=3, all_found=True):
        from support import scan
        ev = [scan("2026-01-01T00:00:00Z", "Sys", 1, 0, "Sys", star=True),
              scan("2026-01-01T00:01:00Z", "Sys", 1, 1, "Sys 1"),
              scan("2026-01-01T00:02:00Z", "Sys", 1, 2, "Sys 2", disc=disc_planet)]
        if all_found:
            ev.append((T("2026-01-01T00:03:00Z"), None, {"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:03:00Z",
                                                          "SystemName": "Sys", "SystemAddress": 1, "Count": count}))
        return ev

    def test_bonus(self):
        ex = outrider.unsold.analyse(self.events(), ARGS)["exploration"]
        self.assertEqual((ex["full_scan_bonus"], ex["full_scan_systems"]), (3000, 1))
        self.assertEqual(ex["estimated_payout"], ex["estimated_value"] + 3000)   # base estimate unchanged, the bonus on top
        for kw in ({"disc_planet": True}, {"all_found": False}, {"count": 4}):   # someone found one first / not all found
            self.assertEqual(outrider.unsold.analyse(self.events(**kw), ARGS)["exploration"]["full_scan_bonus"], 0, kw)

    def test_report_counts_the_bonus(self):
        """Review: the CLI's ESTIMATED and TOTAL left the bonus out while the payout (and the page) had it."""
        import contextlib, io
        res = outrider.unsold.analyse(self.events(), ARGS)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            outrider.unsold.report(res, ARGS)
        text = out.getvalue()
        base = res["exploration"]["estimated_value"]
        self.assertIn("full-scan bonus: 3,000", text.replace(" cr", ""))
        self.assertIn(f"ESTIMATED     : {outrider.unsold.cr(base + 3000)}", text)


class BioforgeLink(unittest.TestCase):
    """Review: only an organic codex entry links to Canonn's Bioforge (the category reads "Biological and Geological"
    for geysers too)."""

    def test_only_organic(self):
        import types
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        state = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1, "StarPos": [0, 0, 0]})
        j.handle({"event": "Scan", "timestamp": "2026-01-01T00:01:00Z", "BodyName": "Sys 4", "BodyID": 4, "StarSystem": "Sys",
                  "SystemAddress": 1, "PlanetClass": "Rocky body", "Landable": True, "MassEM": 0.1, "ScanType": "Detailed",
                  "WasDiscovered": False, "WasMapped": False})
        for i, (sub, name) in enumerate((("Organic structures", "Tussock Pennata - Teal"), ("Geology and anomalies", "Ice Geysers"))):
            j.handle({"event": "CodexEntry", "timestamp": f"2026-01-01T00:0{2 + i}:00Z", "EntryID": 100 + i, "Name": "$x;",
                      "Name_Localised": name, "Category_Localised": "Biological and Geological", "SubCategory_Localised": sub,
                      "Region_Localised": "Inner Orion Spur", "System": "Sys", "SystemAddress": 1, "BodyID": 4})
        body = next(b for b in state.system_detail(1)["bodies"] if b["name"] == "4")
        self.assertEqual({c["name"]: c["entry_id"] for c in body["codex"]}, {"Tussock Pennata - Teal": 100, "Ice Geysers": None})
