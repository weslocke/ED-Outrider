"""A game in another language (review round 10, S11): the same journals read twice, the second time with every
`*_Localised` value in other words, must give the same results once those words are mapped back.

Matching on the game's localised words instead of its codes was the bug found most often across the reviews (round 8,
the complete review, round 9, round 10's B2 bio values by the localised genus, B3 codex-new marks against the localised
variant, B7 Here's 📷). The second reading turns each letter of each `*_Localised` value, at any depth, into its
fullwidth form (A -> U+FF21): words no English table knows, as a Russian game's would be, mapped back exactly before
the two results are compared whole. A field added later is covered without editing a list.

The journals: tests/fixtures/journals (a finished run, a run under way, the DSS's genera) plus the lines here: a codex
entry for the colour of the run under way, on its body (B3's case: a logged colour is not new)."""
import json
import os
import shutil
import tempfile
import types
import unittest

import ed_outrider

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "journals")
TALVIK = 3333333333
# appended to the second fixture journal, after its lines: what the fixtures lack
EXTRA = [
    {"timestamp": "2026-09-20T19:12:30Z", "event": "CodexEntry", "EntryID": 2420202, "Name": "$Codex_Ent_Stratum_02_K_Name;",
     "Name_Localised": "Stratum Paleas - Green", "SubCategory": "$Codex_SubCategory_Organic_Structures;",
     "SubCategory_Localised": "Organic structures", "Category": "$Codex_Category_Biology;", "Category_Localised": "Biological and Geological",
     "Region": "$Codex_RegionName_18;", "Region_Localised": "Inner Orion Spur", "System": "Talvik Reach", "SystemAddress": TALVIK,
     "BodyID": 1, "IsNewEntry": True},
]
SECOND = "Journal.2026-09-20T190000.01.log"


def wide(text):
    """Every ASCII letter in its fullwidth form: words no English table knows, mapped back exactly by narrow()."""
    return "".join(chr(ord(c) + 0xFEE0) if "a" <= c.lower() <= "z" else c for c in text)


def narrow(obj):
    """The fullwidth letters back to ASCII, in every string of a result (keys too)."""
    if isinstance(obj, str):
        return "".join(chr(ord(c) - 0xFEE0) if 0xFF21 <= ord(c) <= 0xFF5A else c for c in obj)
    if isinstance(obj, dict):
        return {narrow(k): narrow(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [narrow(v) for v in obj]
    return obj


def localise(ev):
    """A journal event as another game language writes it: each `*_Localised` value, at any depth, in other words."""
    if isinstance(ev, dict):
        return {k: wide(v) if k.endswith("_Localised") and isinstance(v, str) else localise(v) for k, v in ev.items()}
    if isinstance(ev, list):
        return [localise(v) for v in ev]
    return ev


class AnotherLanguage(unittest.TestCase):
    def read(self, other):
        """The fixture journals (and EXTRA), as written or in other words, read into a fresh database: its State."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        for name in os.listdir(FIXTURES):
            src, dst = os.path.join(FIXTURES, name), os.path.join(d, name)
            if not name.startswith("Journal."):
                shutil.copy(src, dst)
                continue
            with open(src, encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            if name == SECOND:
                lines += EXTRA
            with open(dst, "w", encoding="utf-8") as f:
                for ev in lines:   # the game's spacing: "event":"X", which the reader's prefilter looks for
                    f.write(json.dumps(localise(ev) if other else ev, separators=(", ", ":")) + "\n")
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.scan_dir(d)
        return ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_the_same_results_in_another_language(self):
        english, other = self.read(False), self.read(True)
        for what, get in (("system_detail", lambda s: s.system_detail(TALVIK)),
                          ("leaving_summary", lambda s: s.leaving_summary(TALVIK)),
                          ("body_bio", lambda s: s.body_bio(TALVIK, 1)),
                          ("codex_species_seen", lambda s: s.codex_species_seen(TALVIK)),
                          ("runs_under_way", lambda s: ed_outrider.runs_under_way(s.db, TALVIK)),
                          ("own_organic", lambda s: [dict(r) for r in s.db.execute(
                              "SELECT species, genus_name, species_name, samples FROM own_organic ORDER BY species")]),
                          ("own_genera", lambda s: [dict(r) for r in s.db.execute(
                              "SELECT genus, genus_name FROM own_genera ORDER BY genus")])):
            with self.subTest(what):
                want = json.loads(json.dumps(get(english), default=str))
                got = narrow(json.loads(json.dumps(get(other), default=str)))
                self.assertEqual(got, want)

    def test_the_fixtures_reach_the_cases(self):
        """The corpus holds what the comparison needs: a run under way, a finished run, the DSS's genera, and a codex
        entry for the colour of the run under way (else the test above would pass for want of data)."""
        s = self.read(False)
        runs = {r["species_name"]: r["done_ts"] is not None for r in s.db.execute("SELECT species_name, done_ts FROM own_organic")}
        self.assertEqual(runs, {"Bacterium Aurasus": True, "Stratum Paleas": False})
        self.assertEqual({r[0] for r in s.db.execute("SELECT genus_name FROM own_genera")} >= {"Bacterium", "Stratum"}, True)
        self.assertEqual(s.db.execute("SELECT count(*) FROM codex WHERE system=?", (TALVIK,)).fetchone()[0], 1)

    def test_the_logged_colour_is_not_new(self):
        """Round 10 B3: the codex already holds the run's own colour on that body: not a new codex entry, in either
        language (the German case compared codex_en's English names with the journal's localised variant)."""
        for other in (False, True):
            with self.subTest(other=other):
                s = self.read(other)
                body = next(b for b in s.leaving_summary(TALVIK)["bio_pending"] if b["body"] == "1")
                self.assertEqual((body["codex_new"], body["codex_names"]), (False, []))


if __name__ == "__main__":
    unittest.main()
