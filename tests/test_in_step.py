"""Round 10's S23: regression nets for the rules that keep lists in step. Here (c): every table the schema makes is
either journal-derived (RESET_JOURNAL_DATA deletes it before a re-read) or live-only (LIVE_ONLY_TABLES: kept through
one), never neither and never both. The others: tests/test_ask.py's PhraseCorpus (d), page_unit.js's "alert rows in
step" block (b), tests/page_consts.py (a)."""
import re
import unittest

from support import ed_outrider


class TablesInStep(unittest.TestCase):
    def test_every_table_is_reset_or_live_only(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")} - {"sqlite_sequence"}
        reset = set(re.findall(r"DELETE FROM (\w+)", ed_outrider.RESET_JOURNAL_DATA))
        live = set(ed_outrider.LIVE_ONLY_TABLES)
        self.assertEqual(reset - tables, set(), "RESET_JOURNAL_DATA deletes from a table the schema does not make")
        self.assertEqual(live - tables, set(), "LIVE_ONLY_TABLES names a table the schema does not make")
        self.assertEqual(reset & live, set(), "in both RESET_JOURNAL_DATA and LIVE_ONLY_TABLES")
        self.assertEqual(tables - reset - live, set(),
                         "a table in neither: journal-derived goes in RESET_JOURNAL_DATA, kept through a re-read in "
                         "LIVE_ONLY_TABLES")


if __name__ == "__main__":
    unittest.main()
