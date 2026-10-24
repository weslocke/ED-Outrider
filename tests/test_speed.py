"""Speed, the full Fable review of 2026-10-23's suggestions, batch B (S2-S2, S2-S1, S6-S1, S6-S2, S7-S2, S3-S2, S5-S3)."""
import types
import unittest
import unittest.mock

from support import ed_outrider


class Speed(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_history_counts_use_an_index(self):
        """S2-S2: every History range was ten full table scans (about 4 s for "everything" on a big database)."""
        for k, sql in ed_outrider.State.COUNT_QUERIES.items():
            plan = " ".join(str(tuple(r)) for r in self.db.execute("EXPLAIN QUERY PLAN " + sql, ("", "~")))
            self.assertIn("INDEX", plan.upper(), (k, plan))


    def apply(self, dirty=(), sold=False):
        self.j.dirty, self.j.sales_changed = set(dirty), sold
        with unittest.mock.patch.multiple(self.state, maybe_honk=lambda: None, maybe_brief=lambda: None,
                                          reconcile_arrival=lambda: None, note_sale_estimates=lambda: None,
                                          safe_row=lambda i: True):
            self.state.apply_own_changes()

    def test_left_behind_is_not_rebuilt_for_scans_here(self):
        """S2-S1: Left behind (your own system left out) was rebuilt after every scan here, 40 times in an FSS session."""
        self.j.pos = {"id64": 7, "name": "Here", "x": 0, "y": 0, "z": 0}
        seq = self.state.left_seq
        self.apply(dirty={7})
        self.assertEqual(self.state.left_seq, seq)                        # a scan here: the list cannot change
        self.apply(dirty={8})
        self.assertEqual(self.state.left_seq, seq + 1)                    # elsewhere: it can
        self.apply(sold=True)
        self.assertEqual(self.state.left_seq, seq + 2)
        self.assertIn("left_seq", self.state.payload())
        first = self.state.left_behind()
        self.apply(dirty={7})
        self.assertIs(self.state.left_behind(), first)                    # the same answer, not built again

    def test_the_unsold_estimate_waits_for_a_line_it_reads(self):
        """S6-S1: any journal line (Music, ReceiveText, FuelScoop) re-ran the estimate every 15 s while the game wrote."""
        import json
        import os
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(d, f)) for f in os.listdir(d)] and os.rmdir(d))
        path = os.path.join(d, "Journal.2026-01-01T000000.01.log")
        line = lambda **e: json.dumps(dict({"timestamp": "2026-01-01T00:00:00Z"}, **e), separators=(",", ":")) + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(line(event="Music", MusicTrack="NoTrack") + line(event="FuelScoop", Scooped=1.0, Total=10.0))
        self.j.scan_dir(d)
        self.assertFalse(self.j.unsold_touched)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line(event="Scan", ScanType="AutoScan", BodyName="A 1", BodyID=1, StarSystem="A", SystemAddress=1))
        self.j.scan_dir(d)
        self.assertTrue(self.j.unsold_touched)

    def test_the_upload_counts_are_kept_until_the_outbox_changes(self):
        """S7-S2: the Uploads box ran five count queries per service for every window at every payload."""
        import outrider.uploads as U
        calls = []
        real = U.counts
        with unittest.mock.patch.object(U, "counts", lambda db, sv: calls.append(sv) or real(db, sv)):
            self.state.uploads_summary()
            n = len(calls)
            self.state.uploads_summary()
            self.assertEqual(len(calls), n)                                # nothing changed: none asked again
            ed_outrider.meta_set(self.db, "probe", 1)                      # any write
            self.state.uploads_summary()
            self.assertEqual(len(calls), 2 * n)

if __name__ == "__main__":
    unittest.main()
