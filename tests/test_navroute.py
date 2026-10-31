"""Unit tests: NavRoute.json that the game does not write (2026-10-14). The journal had NavRouteClear, then a NavRoute
line, but NavRoute.json stayed the cleared file, so the In-Game Route line showed nothing mid-route. Outrider now reads
the file again for a while after the line (a late write), never takes an older file for the new route, and meanwhile
says what FSDTarget and Status.json tell (State.route_minimal).

The fixture folder tests/fixtures/navroute_late reproduces that sequence: NavRouteClear 09:10:46, NavRoute 09:11:58,
FSDTarget (3 left), a jump, FSDTarget (2 left), the cleared NavRoute.json from 09:10:46 and a Status.json whose
Destination names the route's end.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import json
import os
import shutil
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "navroute_late")
PLOT = "2026-10-14T09:11:58Z"   # the NavRoute line the file never followed


def hop(i, name, x):
    return {"StarSystem": name, "SystemAddress": i, "StarPos": [x, 0.0, 0.0], "StarClass": "K"}


class LateNavRoute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.d = os.path.join(self.tmp, "live")
        shutil.copytree(FIXTURE, self.d)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.scan_dir(self.d)
        self.j.read_status(self.d)
        self.j.read_navroute(self.d)

    def write_route(self, ts, hops):
        with open(os.path.join(self.d, "NavRoute.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": ts, "event": "NavRoute", "Route": hops}, f)

    def test_the_line_says_what_the_game_tells(self):
        """The cleared file is not the route: the payload's route is the minimal form, 2 jumps left (the latest
        FSDTarget) to the route's end (Status.json's Destination), with no hops; nothing else reads a route."""
        self.assertEqual(self.j.navroute_waiting(), PLOT)
        self.assertIsNone(ed_outrider.meta_get(self.db, "route"))
        self.assertEqual(self.state.route_summary(), {"minimal": True, "hops": [], "jumps_left": 2,
                                                      "destination": "Smojooe SJ-I b23-0", "ts": PLOT,
                                                      "next": "Smojooe BB-B h2"})   # the system targeted: the voice's next
        # the look-ahead (S1, S2), the Map's route and S11's game target see no hops: no fuel window, no last-scoop claim
        self.assertEqual((self.state.navroute_ahead(), self.state.route_ahead()), ([], []))
        self.assertEqual(self.state.game_target()["via"], "destination")
        self.assertIsNone((self.state.map_route() or {}).get("navroute") or None)
        # Status.json's Destination gone (or in this system): the FSDTarget's name stands for the end
        self.j.status_json = dict(self.j.status_json, destination=None)
        self.assertEqual(self.state.route_summary()["destination"], "Smojooe BB-B h2")

    def test_late_write_is_taken(self):
        """The file written after all (late): read as today, the line's stars back, nothing owed any more."""
        self.write_route(PLOT, [hop(902, "Smojooe AA-A h1", 140), hop(903, "Smojooe BB-B h2", 180),
                                hop(904, "Smojooe SJ-I b23-0", 220)])
        self.assertTrue(self.j.read_navroute(self.d))
        self.assertIsNone(self.j.navroute_waiting())
        r = self.state.route_summary()
        self.assertNotIn("minimal", r)
        self.assertEqual([h["name"] for h in r["hops"]], ["Smojooe BB-B h2", "Smojooe SJ-I b23-0"])
        self.assertEqual(self.j.navroute_end, 904)

    def test_an_older_file_is_never_the_new_route(self):
        """A route plotted with no clear before it: the previous route's file (older than the NavRoute line) is not the
        route flown now, so neither the line nor the look-ahead use its stars, and reading it again changes nothing."""
        self.write_route("2026-10-14T09:00:00Z", [hop(902, "Smojooe AA-A h1", 140), hop(950, "Elsewhere", 300)])
        self.j.handle({"event": "NavRoute", "timestamp": "2026-10-14T08:59:00Z"})   # an older plot: ignored (fresh)
        self.assertFalse(self.j.read_navroute(self.d))                              # older than PLOT: not taken
        self.assertIsNone(ed_outrider.meta_get(self.db, "route"))
        # now as if that file had been taken before the plot it does not belong to
        ed_outrider.meta_set(self.db, "route", {"ts": "2026-10-14T09:00:00Z", "hops": [{"id64": 902, "name": "Smojooe AA-A h1",
                             "star_class": "K", "x": 140, "y": 0, "z": 0}, {"id64": 950, "name": "Elsewhere", "star_class": "K",
                                                                       "x": 300, "y": 0, "z": 0}]})
        self.assertIsNone(self.j.game_route())
        self.assertEqual(self.state.navroute_ahead(), [])
        self.assertTrue(self.state.route_summary()["minimal"])

    def test_file_read_before_its_line(self):
        """NavRoute.json read a tick before its journal line: the line finds the route already there, nothing owed."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        self.write_route(PLOT, [hop(902, "Smojooe AA-A h1", 140)])
        self.assertTrue(j.read_navroute(self.d))
        j.handle({"event": "NavRoute", "timestamp": PLOT})
        self.assertIsNone(j.navroute_waiting())
        self.assertIsNotNone(j.game_route())

    def test_clear_and_arrival_end_it(self):
        """NavRouteClear: nothing owed, no line. Arriving at the last target: no line either (its FSDTarget is gone)."""
        self.j.handle({"event": "NavRouteClear", "timestamp": "2026-10-14T09:14:00Z"})
        self.assertIsNone(self.j.navroute_waiting())
        self.assertIsNone(self.state.route_summary())
        self.j.handle({"event": "NavRoute", "timestamp": "2026-10-14T09:15:00Z"})
        self.assertIsNone(self.state.route_summary())   # no FSDTarget since this plot: nothing to say yet
        self.j.handle({"event": "FSDTarget", "timestamp": "2026-10-14T09:15:01Z", "Name": "Smojooe SJ-I b23-0",
                       "SystemAddress": 904, "StarClass": "K", "RemainingJumpsInRoute": 1})
        self.assertIsNone(self.state.route_summary())   # a route of one jump: the target says it, no line (the author)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-10-14T09:16:00Z", "StarSystem": "Smojooe SJ-I b23-0",
                       "SystemAddress": 904, "StarPos": [220.0, 0.0, 0.0], "StarClass": "K"})
        self.assertIsNone(self.state.route_summary())

    def test_one_jump_routes_have_no_line(self):
        """A system targeted one jump away (the game writes a one-jump route for it): no In-Game Route line, written file
        or not; a longer route down to its last jump keeps its line (the author, 2026-10-14)."""
        self.assertEqual(self.state.route_summary()["jumps_left"], 2)   # the fixture: 3 at the plot, a jump, 2 left
        self.j.handle({"event": "FSDTarget", "timestamp": "2026-10-14T09:13:30Z", "Name": "Smojooe SJ-I b23-0",
                       "SystemAddress": 904, "StarClass": "K", "RemainingJumpsInRoute": 1})
        self.assertEqual(self.state.route_summary()["jumps_left"], 1)   # jumped since the plot: the route's last jump
        # the file: a one-jump route (where you are, then the target) gives no line; two jumps do
        here = self.j.pos
        self.write_route("2026-10-14T09:20:00Z", [hop(here["id64"], here["name"], here["x"]), hop(950, "Next Door", here["x"] + 9)])
        self.j.handle({"event": "NavRoute", "timestamp": "2026-10-14T09:20:00Z"})
        self.assertTrue(self.j.read_navroute(self.d))
        self.assertIsNone(self.state.route_summary())
        self.write_route("2026-10-14T09:21:00Z", [hop(here["id64"], here["name"], here["x"]), hop(950, "Next Door", here["x"] + 9),
                                                  hop(951, "Beyond", here["x"] + 18)])
        self.j.handle({"event": "NavRoute", "timestamp": "2026-10-14T09:21:00Z"})
        self.assertTrue(self.j.read_navroute(self.d))
        self.assertEqual([h["name"] for h in self.state.route_summary()["hops"]], ["Next Door", "Beyond"])
        # flown down to its last jump: still shown
        self.j.handle({"event": "FSDJump", "timestamp": "2026-10-14T09:25:00Z", "StarSystem": "Next Door",
                       "SystemAddress": 950, "StarPos": [here["x"] + 9, 0.0, 0.0], "StarClass": "K"})
        self.assertEqual([h["name"] for h in self.state.route_summary()["hops"]], ["Beyond"])

    def test_reread_late_for_a_minute(self):
        """State.navroute_retry: read again at once, then every NAVROUTE_RETRY_S up to NAVROUTE_LATE_S after the line;
        then only when the file changes. The tick takes a late file whose mtime did not move."""
        R, L = ed_outrider.NAVROUTE_RETRY_S, ed_outrider.NAVROUTE_LATE_S
        self.assertEqual([self.state.navroute_retry(t) for t in (100, 100.5, 100 + R, 100 + R + 0.5, 100 + L - 0.1, 100 + L + 1)],
                         [True, False, True, False, True, False])
        self.j.handle({"event": "NavRouteClear", "timestamp": "2026-10-14T09:14:00Z"})
        self.assertFalse(self.state.navroute_retry(200))
        self.assertIsNone(self.state.navroute_late)
        # a tick: the file written late with the same mtime as before is still read while it is owed
        self.j.handle({"event": "NavRoute", "timestamp": "2026-10-14T09:15:00Z"})
        path = os.path.join(self.d, "NavRoute.json")
        mtimes = {path: os.path.getmtime(path)}
        self.write_route("2026-10-14T09:15:00Z", [hop(902, "Smojooe AA-A h1", 140), hop(904, "Smojooe SJ-I b23-0", 220)])
        os.utime(path, (mtimes[path], mtimes[path]))
        later = ("watch_status", "maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold",
                 "maybe_sale_left", "maybe_locate_carrier", "maybe_find_sellers", "maybe_backup_on_quit")
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.d]):
            patches = [unittest.mock.patch.object(self.state, n, lambda *a: None) for n in later]
            for p in patches:
                p.start()
            try:
                self.state.tick(mtimes)
            finally:
                for p in patches:
                    p.stop()
        self.assertIsNone(self.state.tail_error)
        self.assertEqual(len(ed_outrider.meta_get(self.db, "route")["hops"]), 2)
        self.assertIsNone(self.j.navroute_waiting())


if __name__ == "__main__":
    unittest.main()
