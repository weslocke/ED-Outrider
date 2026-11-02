"""Unit tests: the Plotted Route pane (issue #22, Psilovybin: "when I plot a route in-game, is there a way that ED
Outrider shows the route and EDSM data along that route?"; project/PLAN-route-pane-2026-11-02.md). Nearby's rows for
the systems ahead on a route: the game's, the Highway's, the survey slot's or a carrier trip's (State.route_lists,
route_list_hops, route_list), Spansh asked only while the pane is open (maybe_route_list_fetch / fetch_route_list:
one id search, then a dump per system it has whose cached copy is old). And the In-Game Route chips' hover: Spansh's
body count and update time (State.spansh_brief). Nothing here touches the network.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import contextlib
import io
import time
import unittest

from support import ed_outrider  # also puts the repository root on sys.path

FAR = (-4000.0, 0.0, 3000.0)   # out in the black: the populated regions' rule does not apply


def hop(i, x=None):
    return {"id64": i, "name": f"S{i}", "star_class": "K", "x": FAR[0] + (i * 10.0 if x is None else x), "y": FAR[1],
            "z": FAR[2]}


def hw_row(i, jumps=1):
    h = hop(i)
    return {"system": h["name"], "id64": i, "x": h["x"], "y": h["y"], "z": h["z"], "distance": 10.0, "fuel_used": 1.0,
            "fuel_left": 10.0, "neutron": False, "refuel": False, "jumps": jumps, "remaining": 0.0}


def survey_row(i):
    h = hop(i)
    return {"system": h["name"], "id64": i, "x": h["x"], "y": h["y"], "z": h["z"], "jumps": 1, "bodies": []}


class Base(unittest.TestCase):
    """You in S1, out in the black; a Spansh with its cache only (no session: nothing is asked)."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.sp = ed_outrider.Spansh(self.db)
        self.state = ed_outrider.State(self.db, self.j, self.sp, 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "S1", "SystemAddress": 1,
                       "StarPos": [FAR[0] + 10.0, FAR[1], FAR[2]]})

    def game_route(self, n):
        ed_outrider.meta_set(self.db, "route", {"ts": "2026-01-01T00:00:30Z", "hops": [hop(i) for i in range(1, n + 1)]})

    def cache(self, i, updated="u1", records=None):
        h = hop(i)
        self.sp.store(i, updated, {"v": ed_outrider.CACHE_VERSION, "name": h["name"], "x": h["x"], "y": h["y"],
                                   "z": h["z"], "body_count": 5, "records": records or []})


class Choices(Base):
    def test_only_the_routes_there_are(self):
        self.assertEqual(self.state.route_lists(), [])
        self.game_route(2)   # one jump: the target's, no In-Game Route line, no pane choice
        self.assertEqual(self.state.route_lists(), [])
        self.game_route(5)
        self.assertEqual([c["id"] for c in self.state.route_lists()], ["game"])
        self.state.highway_store([hw_row(i) for i in range(1, 6)], {"plotter": "exact", "options": {}, "ship": None})
        self.state.riches_store([survey_row(i) for i in (1, 7, 9)], {"options": {}, "kind": "elw"})
        ed_outrider.meta_set(self.db, "carrier_trip", {"id": "t", "at": 0, "legs": [
            {"system": "S1", "id64": 1, "ly": 0}, {"system": "S30", "id64": 30, "ly": 400.0}]})
        got = self.state.route_lists()
        self.assertEqual([c["id"] for c in got], ["game", "highway", "survey", "carrier"])
        self.assertEqual(got[2]["label"], "Earth-like worlds")
        # the default: the game's route; without it, the route plotted last (route_newest: the survey's here)
        for k, ts in (("highway", "2026-01-01T00:00:00Z"), ("riches", "2026-01-02T00:00:00Z")):
            ed_outrider.meta_set(self.db, k, dict(ed_outrider.meta_get(self.db, k), created_ts=ts))
        self.assertEqual(self.state.route_list_default(["game", "highway", "survey"]), "game")
        self.assertEqual(self.state.route_list_default(["highway", "survey", "carrier"]), "survey")
        self.assertEqual(self.state.route_list_default(["carrier"]), "carrier")
        self.assertIsNone(self.state.route_list_default([]))
        # finished ones go
        ed_outrider.meta_set(self.db, "carrier_trip", {"id": "t", "at": 1, "legs": [{"system": "S1", "id64": 1, "ly": 0},
                                                                                  {"system": "S30", "id64": 30, "ly": 400.0}]})
        ed_outrider.meta_set(self.db, "highway", dict(ed_outrider.meta_get(self.db, "highway"), done_ts="2026-01-01T01:00:00Z"))
        self.assertEqual([c["id"] for c in self.state.route_lists()], ["game", "survey"])


class Hops(Base):
    def test_the_games_route_from_where_you_are(self):
        self.game_route(40)
        hops, total = self.state.route_list_hops("game")
        self.assertEqual((len(hops), total), (ed_outrider.ROUTE_LIST_MAX, 39))
        self.assertEqual([(h["id64"], h["n"], h["along"]) for h in hops[:3]], [(2, 1, 10.0), (3, 2, 20.0), (4, 3, 30.0)])
        self.assertEqual(hops[0]["star_class"], "K")
        out = self.state.route_list("game")
        self.assertEqual((out["which"], out["more"], len(out["rows"])), ("game", 15, 24))

    def test_highway_from_its_next_row_counting_its_jumps(self):
        """A neutron-plotter row stands for several jumps: n counts them; rows before where you are are left out."""
        self.state.highway_store([hw_row(1), hw_row(2), hw_row(5, jumps=3), hw_row(6)],
                                 {"plotter": "neutron", "options": {}, "ship": None})
        hops, total = self.state.route_list_hops("highway")
        self.assertEqual([(h["id64"], h["n"], h["along"]) for h in hops], [(2, 1, 10.0), (5, 4, 40.0), (6, 5, 50.0)])
        self.assertEqual(total, 3)

    def test_survey_stops_fold_a_trade_routes_stations(self):
        rows = [survey_row(1), survey_row(4), survey_row(4), survey_row(8)]
        self.state.riches_store(rows, {"options": {}})
        hops, _ = self.state.route_list_hops("survey")
        self.assertEqual([(h["id64"], h["n"]) for h in hops], [(4, 1), (8, 2)])

    def test_a_carrier_trip_by_its_legs(self):
        """A leg has no position: the cache or Spansh's id search places it; until then the row says nothing of it."""
        ed_outrider.meta_set(self.db, "carrier_trip", {"id": "t", "at": 0, "legs": [
            {"system": "S1", "id64": 1, "ly": 0}, {"system": "S30", "id64": 30, "ly": 480.5},
            {"system": "S60", "id64": 60, "ly": 300.0}]})
        self.cache(30)
        hops, _ = self.state.route_list_hops("carrier")
        self.assertEqual([(h["id64"], h["n"], h["along"], h["x"] is not None) for h in hops],
                         [(30, 1, 480.5, True), (60, 2, 780.5, False)])
        rows = self.state.route_list("carrier")["rows"]
        self.assertEqual([r.get("nodata", False) for r in rows], [False, True])


class Rows(Base):
    def test_nearbys_row_with_what_is_known(self):
        """Spansh's cached record: its bodies; asked and absent: unreported; never asked: no claim (unasked); Spansh
        has it but its dump is not here yet: Spansh's, no bodies yet."""
        self.game_route(6)
        self.cache(2, records=[{"name": "S2 A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "main": True,
                                "scoopable": True, "terraformable": False, "full": True}])
        self.state.route_spansh[3] = (time.time(), False, None)
        self.state.route_spansh[5] = (time.time(), True, {"body_count": 7, "updated_at": "u5", "x": 0, "y": 0, "z": 0})
        rows = {r["id"]: r for r in self.state.route_list("game")["rows"]}
        self.assertEqual(rows["2"]["source"], "spansh")
        self.assertEqual(rows["2"]["bodies_known"], 1)
        self.assertEqual((rows["3"]["status"], rows["3"]["in_spansh"]), ("unreported", False))
        self.assertEqual(rows["4"]["status"], "unasked")
        self.assertEqual((rows["5"]["source"], rows["5"]["body_count"]), ("spansh", 7))
        self.assertEqual((rows["2"]["n"], rows["2"]["along"], rows["2"]["from_you"]), (1, 10.0, 10.0))
        # a click opens the system: locate knows it now
        self.assertEqual(self.state.locate(4)[0], "S4")

    def test_an_unknown_which_is_the_default(self):
        self.game_route(4)
        self.assertEqual(self.state.route_list("nonsense")["which"], "game")
        self.assertEqual(self.state.route_list("highway")["which"], "game")   # no Highway route: the one there is
        ed_outrider.meta_set(self.db, "route", None)
        self.assertEqual(self.state.route_list(None), {"choices": [], "which": None, "rows": [], "more": 0, "asking": None})


class Fetch(Base):
    def setUp(self):
        super().setUp()
        self.searches, self.dumps, self.fail = [], [], set()
        test = self

        class Fake(ed_outrider.Spansh):
            async def records_by_id(self, ids):
                test.searches.append(list(ids))
                if "search" in test.fail:
                    raise ed_outrider.ClientError("down")
                return [{"id64": i, "name": f"S{i}", "body_count": 4, "updated_at": f"u{i}", "x": 0, "y": 0, "z": 0}
                        for i in ids if i % 2 == 0]   # Spansh has the even ones

            async def lookup(self, id64, interactive=True):
                test.dumps.append(id64)
                if id64 in test.fail:
                    raise ed_outrider.ClientError("down")
                return {"system": {"bodyCount": 4, "bodies": [{"name": f"S{id64}", "type": "Star", "subType": "K (Yellow-Orange) Star",
                                                               "isMainStar": True, "isScoopable": True}]}}

        self.sp = Fake(self.db)
        self.sp.session = object()   # "started": the fakes answer, nothing goes out
        self.state.spansh = self.sp

    def fetch(self, which="game"):
        async def go():
            self.state.maybe_route_list_fetch(which)
            if self.state.route_list_task:
                await self.state.route_list_task
        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(go())
        self.state.route_list_task = None

    def test_one_search_then_dumps_of_what_spansh_has(self):
        self.game_route(8)   # 7 hops ahead: S2..S8
        self.fetch()
        self.assertEqual(self.searches, [[2, 3, 4, 5, 6, 7, 8]])
        self.assertEqual(sorted(self.dumps), [2, 4, 6, 8])
        rows = {r["id"]: r for r in self.state.route_list("game")["rows"]}
        self.assertEqual((rows["4"]["bodies_known"], rows["3"]["status"]), (1, "unreported"))
        self.assertGreater(self.state.route_list_seq, 0)
        self.fetch()   # all answered and cached for their updated_at: nothing more is asked
        self.assertEqual((len(self.searches), len(self.dumps)), (1, 4))

    def test_a_newer_spansh_record_is_fetched_again(self):
        self.game_route(3)
        self.cache(2, updated="old")
        self.state.route_spansh[2] = (time.time(), True, {"body_count": 4, "updated_at": "new", "x": 0, "y": 0, "z": 0})
        self.state.route_spansh[3] = (time.time(), False, None)
        self.fetch()
        self.assertEqual((self.searches, self.dumps), ([], [2]))
        self.assertEqual(self.sp.cached(2)[0], "new")

    def test_failures_wait(self):
        self.game_route(5)
        self.fail = {"search"}
        self.fetch()
        self.assertEqual((len(self.searches), self.dumps), (1, []))
        self.fetch()   # the search is not asked again so soon
        self.assertEqual(len(self.searches), 1)
        self.fail, self.state.route_list_retry_at = {4}, 0
        self.fetch()
        self.assertEqual((len(self.searches), sorted(self.dumps)), (2, [2, 4]))
        self.fetch()   # the failed dump waits too
        self.assertEqual(sorted(self.dumps), [2, 4])
        self.state.route_list_failed[4] -= ed_outrider.ROUTE_LOOKUP_RETRY_S + 1
        self.fetch()
        self.assertEqual(sorted(self.dumps), [2, 4, 4])

    def test_the_sphere_and_populated_hops_are_left_alone(self):
        """Nearby's own systems: its refresh fetches them. Around Sol Spansh knows every system: no id search, the
        dump says the rest."""
        ed_outrider.meta_set(self.db, "route", {"ts": "2026-01-01T00:00:30Z", "hops": [
            hop(1), hop(2), hop(3), {"id64": 4, "name": "Sol-ish", "star_class": "G", "x": 50.0, "y": 0, "z": 30.0}]})
        self.state.bases[2] = ("spansh", {"name": "S2", "x": 0, "y": 0, "z": 0, "records": []})
        self.fetch()
        self.assertEqual(self.searches, [[3]])
        self.assertEqual(self.dumps, [4])

    def test_nothing_without_a_session(self):
        self.game_route(4)
        self.sp.session = None
        self.fetch()
        self.assertEqual((self.searches, self.dumps, self.state.route_list_task), ([], [], None))


class Chips(Base):
    def test_spansh_count_and_update_in_the_hover(self):
        self.game_route(4)
        self.cache(2, updated="2024-06-12 10:00:00+00")
        self.state.route_spansh[3] = (time.time(), True, {"body_count": 9, "updated_at": "2025-01-02 00:00:00+00"})
        self.state.route_spansh[4] = (time.time(), False, None)
        got = {h["id"]: (h["spansh_bodies"], h["spansh_updated"]) for h in self.state.route_summary()["hops"]}
        self.assertEqual(got, {"2": (5, "2024-06-12 10:00:00+00"), "3": (9, "2025-01-02 00:00:00+00"), "4": (None, None)})

    def test_the_hop_search_keeps_the_record(self):
        self.state.keep_route_spansh([2, 3], [{"id64": 2, "body_count": 4, "updated_at": "u", "x": 1, "y": 2, "z": 3}])
        self.assertEqual(self.state.route_spansh[2][1:], (True, {"body_count": 4, "updated_at": "u", "x": 1, "y": 2, "z": 3}))
        self.assertEqual(self.state.route_spansh[3][1:], (False, None))


class Payload(Base):
    def test_the_key_moves_with_a_jump_and_an_answer(self):
        self.game_route(5)
        k = self.state.route_list_key()
        self.state.route_list_seq += 1
        self.assertNotEqual(self.state.route_list_key(), k)
        k = self.state.route_list_key()
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:01:00Z", "StarSystem": "S2", "SystemAddress": 2,
                       "StarPos": [FAR[0] + 20.0, FAR[1], FAR[2]]})
        self.assertNotEqual(self.state.route_list_key(), k)


if __name__ == "__main__":
    unittest.main()
