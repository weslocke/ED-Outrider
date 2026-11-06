"""Unit tests: round 10's S20, Nearby's ✦/✪ in the 🧬 tag: a species surely new to your codex ("sure", the author's
answer 9), judged at each payload against your codex as it is then, so logging the species clears it at once.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import types
import unittest
import unittest.mock

from support import CANDS, ed_outrider  # also puts the repository root on sys.path
import outrider.bio  # noqa: E402

NONE = (set(), set())


def cand(body, n, *groups):
    """codex_body_cands' shape: groups as (genus, [species names])."""
    return {"body": body, "n": n, "groups": [{"genus": g, "best": sp[0] if sp else None, "species": [{"name": x} for x in sp]}
                                             for g, sp in groups]}


class SureRule(unittest.TestCase):
    def test_known_genera_any_sure_one(self):
        """With the genera known (a DSS, Spansh's list), any genus whose every possible species is unlogged is sure."""
        c = [cand("A 1", None, ("Bacterium", ["Bacterium Aurasus", "Bacterium Cerbrus"]), ("Stratum", ["Stratum Tectonicas"]))]
        self.assertEqual(ed_outrider.codex_sure_bodies(c, NONE), ["A 1: Bacterium Aurasus / Bacterium Cerbrus, Stratum Tectonicas"])
        # one of Bacterium's species logged (any colour): that genus is no longer sure, Stratum still is
        known = ({"bacterium cerbrus - teal"}, {"bacterium cerbrus"})
        self.assertEqual(ed_outrider.codex_sure_bodies(c, known), ["A 1: Stratum Tectonicas"])
        known = ({"x"}, {"bacterium cerbrus", "stratum tectonicas"})
        self.assertEqual(ed_outrider.codex_sure_bodies(c, known), [])

    def test_signals_only_needs_more_sure_genera_than_the_rest_allows(self):
        """Before the DSS the signals may be any of the genera the rules allow: flagged only when the genera that are
        not sure are fewer than the signals (at least one signal must then be a sure one)."""
        groups = [("Bacterium", ["Bacterium Aurasus"]), ("Stratum", ["Stratum Tectonicas"]), ("Concha", ["Concha Biconcavis"])]
        logged = ({"x"}, {"bacterium aurasus"})                       # Bacterium is not new; the others are
        self.assertEqual(ed_outrider.codex_sure_bodies([cand("B 2", 1, *groups)], logged), [])   # 1 signal: it may be Bacterium
        self.assertEqual(ed_outrider.codex_sure_bodies([cand("B 2", 2, *groups)], logged),
                         ["B 2: Stratum Tectonicas or Concha Biconcavis"])   # 2 signals, one at most Bacterium
        # the rules allow fewer genera than the signals: one of them is a genus they do not know, nothing is sure
        self.assertEqual(ed_outrider.codex_sure_bodies([cand("B 2", 4, *groups)], NONE), [])
        # a genus with no species the rules name is never sure
        self.assertEqual(ed_outrider.codex_sure_bodies([cand("B 3", None, ("Fonticulua", []))], NONE), [])


class NearbyFlag(unittest.TestCase):
    """The flag rides on the payload's rows, judged at each payload (never baked into row(): rows are rebuilt only for
    dirty systems), and the Plotted Route pane's rows get it through the same judging."""

    def setUp(self):
        if not outrider.bio or not outrider.bio.load_rules():
            self.skipTest("no rules")
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.region = outrider.bio.region_name(0, 0, 0)
        p = unittest.mock.patch.object(outrider.bio, "predict", return_value=CANDS)
        p.start()
        self.addCleanup(p.stop)
        self.base = {"name": "Testa", "x": 0.0, "y": 0.0, "z": 0.0, "body_count": 1,
                     "records": [{"name": "1", "type": "Planet", "subtype": "Rocky body", "bio": 1, "genera": ["Bacterium"]}]}
        self.state.bases[7] = ("spansh", self.base)
        self.state.set_row(7)

    def row(self):
        return next(s for s in self.state.payload()["systems"] if s["id64"] == 7)

    def codex(self, region, n):
        self.db.execute("INSERT INTO codex (ts, entry_id, name, region, system, code) VALUES (?, 2320101, ?, ?, 99, ?)",
                        (f"2026-11-06T00:00:0{n}Z", "Bacterium Aurasus - Teal", region, "$Codex_Ent_Bacterial_01_M_Name;"))

    def test_flag_clears_when_the_species_is_logged(self):
        self.assertNotIn("codex_cands", self.state.systems[7])   # kept beside the row, never sent
        self.assertEqual(self.row()["codex_sure"], {"galaxy": ["1: Bacterium Aurasus"], "region": ["1: Bacterium Aurasus"]})
        self.codex("Norma Expanse", 1)   # logged elsewhere: no longer new anywhere (✪), still new here (✦)
        self.assertEqual(self.row()["codex_sure"], {"galaxy": [], "region": ["1: Bacterium Aurasus"]})
        self.codex(self.region, 2)       # logged in this region: the flag goes at the next payload, the row not rebuilt
        self.assertNotIn("codex_sure", self.row())
        self.assertEqual(self.state.systems[7]["bio_potential"], 1_000_000)   # the 🧬 tag itself stays

    def test_row_rebuilt_is_judged_again(self):
        self.assertIn("codex_sure", self.row())
        self.base["records"][0]["genera"] = ["Stratum"]   # the row's bodies changed: set_row drops its judgement
        self.codex(self.region, 1)
        self.state.set_row(7)
        self.assertEqual(self.row()["codex_sure"]["region"], ["1: Stratum Tectonicas"])
        # a row made and not kept (the Plotted Route pane's, the boxel's) is judged at once
        r = self.state.row(7)
        self.state.mark_row(r, self.state.codex_known())
        self.assertNotIn("codex_cands", r)
        self.assertEqual(r["codex_sure"]["galaxy"], ["1: Stratum Tectonicas"])


if __name__ == "__main__":
    unittest.main()
