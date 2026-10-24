"""The rest of the server, the full Fable review of 2026-10-23 (fix batch 5): S3-B6, S4-B6, S4-B9, S4-B10, S4-B12."""
import threading
import time
import types
import unittest
import unittest.mock

from support import ed_outrider
import outrider.notices  # noqa: E402
import outrider.target  # noqa: E402


class ServerFixes(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_an_unchanged_notice_keeps_its_place(self):
        """S4-B12: setting a notice again as it was moved it to the end of the banner."""
        b = outrider.notices.Board()
        b.set("a", "first")
        b.set("b", "second")
        self.assertFalse(b.set("a", "first"))
        self.assertEqual([n["key"] for n in b.active()], ["a", "b"])

    def test_search_keeps_only_what_it_shows(self):
        """S4-B10: every match of every search was kept for the life of the server."""
        s = ed_outrider.Searcher(self.state)
        with unittest.mock.patch.object(ed_outrider, "SEARCH_MAX_RESULTS", 3):
            for run in range(5):
                found = {run * 10 + i: (f"S{run}-{i}", 0, 0, 0) for i in range(6)}
                results = [{"id": str(k), "distance": i} for i, k in enumerate(found)]
                s.keep_found(found, results)
            self.assertLessEqual(len(s.found), 6)
            self.assertIn(40, s.found)                                   # the last search's shown rows
            self.assertNotIn(45, s.found)                                # past the rows shown

    def test_the_danger_wait_judges_the_runs_own_reading(self):
        """S4-B6: start_autotarget_run's guard read Status.json itself, the danger-wait the watcher's (older) copy."""
        T = outrider.target
        now = time.time()
        self.j.pos = {"id64": 7, "ts": ed_outrider.iso_ts(now - 5)}
        self.j.jump_arrival = {"id64": 7, "ts": ed_outrider.iso_ts(now - 5)}
        self.j.status_json = {"flags": 0}                               # the watcher's copy: not in danger yet
        fresh = {"flags": T.FLAG_IN_DANGER}
        self.assertIsNone(self.state.arrival_danger_until(now))
        self.assertIsNotNone(self.state.arrival_danger_until(now, st=fresh))

    def test_skip_known_is_named_as_the_reason(self):
        """S3-B6: with Skip known passing the rest over, the reason said every system was visited."""
        ed_outrider.meta_set(self.db, "boxel_skip_known", True)
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(time.time() - 60), "StarSystem": "Drojau TF-H c13-0",
                       "SystemAddress": 2870515095985, "StarPos": [-4179.0, -64.0, 3339.0]})
        real = ed_outrider.boxel_next_number
        with unittest.mock.patch.object(ed_outrider, "boxel_next_number",
                                        lambda v, s, e, skip=False: None if skip else real(v, s, e)):
            tgt, why = self.state.boxel_target()
        self.assertIsNone(tgt)
        self.assertIn("Skip known is on", why)

    def test_the_boxels_run_has_its_own_token(self):
        """S4-B9: the boxel's automatic run took the Highway run's cancel token: the Highway's switch or a cleared route
        stopped it, and its own switch did not."""
        tok = threading.Event()
        self.state._boxel_cancel, self.state._autotarget_cancel = tok, None
        self.state.cancel_autotarget(route=True)                        # the Highway's route cleared
        self.assertFalse(tok.is_set())
        self.state.set_boxel_auto(False)                                 # its own switch
        self.assertTrue(tok.is_set())
        self.assertFalse(ed_outrider.meta_get(self.db, "boxel_auto"))
        honker = types.SimpleNamespace(available=True, opened=[], closed=[])
        honker.open, honker.close = honker.opened.append, honker.closed.append
        self.state.honker = honker
        self.state.set_boxel_auto(True)
        self.state.set_boxel_auto(False)
        self.assertEqual((honker.opened, honker.closed), (["boxel"], ["boxel"]))   # it holds the keyboard while on


if __name__ == "__main__":
    unittest.main()
