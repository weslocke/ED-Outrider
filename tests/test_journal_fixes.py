"""Journal data, the full Fable review of 2026-10-23 (fix batch 4): S2-B1, S1-B2, S1-B3, S1-B4, S1-B6, S3-B3, S6-B4
(S1-B5 is in test_earnings_data, S6-B1 in test_codex_bodies)."""
import contextlib
import io
import json
import os
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider
import outrider.log  # noqa: E402


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


class JournalFixes(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_since_the_last_sale_counts_only_sales_after_it(self):
        """S2-B1: the row counted the last cartographic sale itself as sold since (5,000 + 1,000 shown for 1,000)."""
        self.j.handle(ev("2026-01-02T00:00:00Z", "MultiSellExplorationData", TotalEarnings=5000, BaseValue=5000, Bonus=0,
                         Discovered=[{"SystemName": "A", "NumBodies": 1}]))
        self.j.handle(ev("2026-01-03T00:00:00Z", "SellOrganicData", MarketID=1,
                         BioData=[{"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Species": "$Codex_Ent_Bacterial_01_Name;",
                                   "Value": 1000, "Bonus": 0}]))
        self.db.commit()
        since = self.state.ledger()["since_last_sale"]
        self.assertEqual(since["sold"], 1000)

    def test_an_older_sample_read_late_does_not_replace_a_newer_run(self):
        """S1-B4: a legacy folder read after the live one replaced a completed run with an older one of the species."""
        def org(ts, kind):
            return ev(ts, "ScanOrganic", ScanType=kind, Genus="$Codex_Ent_Stratum_Genus_Name;", Species="$Codex_Ent_Stratum_07_Name;",
                      Species_Localised="Stratum Tectonicas", SystemAddress=5, Body=3)
        for ts, kind in (("2026-01-01T00:00:00Z", "Log"), ("2026-01-01T00:05:00Z", "Sample"), ("2026-01-01T00:10:00Z", "Analyse")):
            self.j.handle(org(ts, kind))
        self.j.handle(org("2025-01-01T00:00:00Z", "Log"))      # the older run, read late
        row = self.db.execute("SELECT samples, done_ts FROM own_organic WHERE system=5 AND body_id=3").fetchone()
        self.assertEqual((row["samples"], row["done_ts"]), (3, "2026-01-01T00:10:00Z"))

    def test_a_first_scan_read_late_keeps_its_flags(self):
        """S1-B6: the rescan's flags (WasDiscovered true: your own rescan of a body you discovered) stood after the first
        scan arrived late from a legacy folder."""
        scan = lambda ts, disc: ev(ts, "Scan", ScanType="Detailed", StarSystem="Sys", SystemAddress=9, BodyID=4, BodyName="Sys 4",
                                   PlanetClass="Icy body", DistanceFromArrivalLS=900.0, WasDiscovered=disc, WasMapped=False)
        self.j.handle(ev("2026-01-01T00:00:00Z", "FSDJump", StarSystem="Sys", SystemAddress=9, StarPos=[0, 0, 0]))
        self.j.handle(scan("2026-01-02T00:00:00Z", True))      # the rescan, read first
        self.j.handle(scan("2025-06-01T00:00:00Z", False))     # the first scan, read late
        row = self.db.execute("SELECT was_discovered, first_ts FROM own_firsts WHERE system=9 AND body_id=4").fetchone()
        self.assertEqual((row["was_discovered"], row["first_ts"]), (0, "2025-06-01T00:00:00Z"))

    def test_a_journal_cut_mid_line_is_not_touched_every_tick(self):
        """S1-B2: a journal whose last line has no newline counted as touched on every look (an unsold recompute every
        15 s and a database write every second)."""
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(d, f)) for f in os.listdir(d)] and os.rmdir(d))
        path = os.path.join(d, "Journal.2026-01-01T000000.01.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(ev("2026-01-01T00:00:00Z", "Music", MusicTrack="NoTrack")) + "\n" + '{"timestamp":"2026-01-01T00:0')
        writes = []
        self.db.set_trace_callback(lambda sql: writes.append(sql) if "journal_files" in sql and "INSERT" in sql else None)
        counts = [self.j.scan_dir(d, quick=True) for _ in range(3)]
        self.db.set_trace_callback(None)
        self.assertEqual((counts, len(writes)), ([1, 0, 0], 1))

    def test_a_legacy_folder_with_an_unreadable_journal_is_tried_again(self):
        """S1-B3: the folder was marked imported though one of its journals could not be read; it was never read."""
        d = tempfile.mkdtemp()
        bad = os.path.join(d, "Journal.2026-01-01T000000.01.log")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(json.dumps(ev("2026-01-01T00:00:00Z", "Music", MusicTrack="NoTrack")) + "\n")
        os.chmod(bad, 0)
        self.addCleanup(lambda: (os.chmod(bad, 0o644), os.remove(bad), os.rmdir(d)))
        if os.access(bad, os.R_OK):
            self.skipTest("running as a user who can read anything")
        board = ed_outrider.outrider.notices.Board()
        with unittest.mock.patch.object(ed_outrider, "LEGACY_DIRS", [d]), \
                unittest.mock.patch.object(ed_outrider.outrider.notices, "BOARD", board), \
                contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.j.import_legacy()
        self.assertIsNone(ed_outrider.meta_get(self.db, f"legacy:{d}"))
        self.assertEqual([n["key"] for n in board.active()], [f"legacy_unread:{d}"])

    def test_a_bio_sale_rebuilds_the_rows(self):
        """S3-B3: a bio sale left Nearby's "now" values stale: no row was rebuilt (the current system's only after the
        loop that rebuilds them)."""
        self.state.bases = {1: (None, {}), 2: (None, {})}
        rebuilt = []
        self.j.bio_sales_changed = True
        with unittest.mock.patch.object(self.state, "safe_row", lambda i: rebuilt.append(i) or True), \
                unittest.mock.patch.multiple(self.state, maybe_honk=lambda: None, maybe_brief=lambda: None,
                                             reconcile_arrival=lambda: None):
            self.state.apply_own_changes()
        self.assertEqual(sorted(rebuilt), [1, 2])

    def test_the_logs_embark_line_names_the_craft(self):
        """S6-B4: the Log's Embark line said "ship" for a taxi or another commander's ship too."""
        say = lambda e: outrider.log.LOG_FORMAT[e["event"]](e)
        self.assertEqual(say(ev("t", "Embark", Taxi=True)), "Embarked in a taxi")
        self.assertEqual(say(ev("t", "Embark", Multicrew=True)), "Embarked in another commander's ship")
        self.assertEqual(say(ev("t", "Embark", SRV=True)), "Embarked in SRV")
        self.assertEqual(say(ev("t", "Embark")), "Embarked in your ship")
        self.assertEqual(say(ev("t", "Disembark", Taxi=True)), "Disembarked from a taxi")


    def test_a_line_thrown_away_is_said(self):
        """Review 2026-10-23 S1-S1: a ValueError a handler raised on a well-formed line was swallowed with the lines that
        are not JSON; now it is printed like a KeyError, and the not-JSON lines are said once per file."""
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(d, f)) for f in os.listdir(d)] and os.rmdir(d))
        path = os.path.join(d, "Journal.2026-01-01T000000.01.log")
        jump = json.dumps(ev("2026-01-01T00:00:00Z", "FSDJump", StarSystem="A", SystemAddress=1, StarPos=[0, 0, 0]), separators=(",", ":"))
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"event":"FSDJump", "Star\n{"event":"FSDJump", "Sys\n' + jump + "\n")   # cut short: not JSON
        err = io.StringIO()
        real = self.j.handle

        def handle(e):
            if e.get("event") == "FSDJump":
                raise ValueError("an odd timestamp")
            return real(e)
        with unittest.mock.patch.object(self.j, "handle", handle), contextlib.redirect_stderr(err):
            self.j.scan_dir(d)
        out = err.getvalue()
        self.assertEqual(out.count("(not JSON)"), 1)
        self.assertIn("journal line skipped (ValueError: an odd timestamp)", out)

if __name__ == "__main__":
    unittest.main()
