"""Unit tests: Road to Riches: Spansh's route of systems with valuable bodies, plotting it, following it by the journal
(fakes only: no network, no clipboard tool).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import time
import unittest
import unittest.mock

from support import _HwSession, hwy_jump, hwy_ts, types_ns  # also puts the repository root on sys.path
import ed_outrider  # noqa: E402
import outrider.riches as riches  # noqa: E402


def body(name, subtype, ls, scan, mapped, **kw):
    return dict({"name": name, "type": "Planet", "subtype": subtype, "distance_to_arrival": ls,
                 "estimated_scan_value": scan, "estimated_mapping_value": mapped}, **kw)


# A synthetic answer in Spansh's Road to Riches layout (made-up systems, for the route logic); RichesRows.test_real_answer
# reads a real one (tests/fixtures/spansh_riches.json).
RESULT = [
    {"name": "Alpha Rich", "id64": 1001, "x": 0, "y": 0, "z": 0, "jumps": 0,
     "bodies": [body("Alpha Rich 1", "Earth-like world", 500, 1200000, 3000000, is_terraformable=False),
                body("Alpha Rich 2 a", "Water world", 8000, 800000, 1500000)]},
    {"name": "Beta Rich", "id64": 1002, "x": 20, "y": 0, "z": 0, "jumps": 1,
     "bodies": [body("Beta Rich 4", "High metal content world", 300, 450000, 900000, is_terraformable=True)]},
    {"name": "Gamma Rich", "id64": 1003, "x": 45, "y": 0, "z": 0, "jumps": 2,
     "bodies": [body("Gamma Rich 1", "Ammonia world", 1200, 600000, 1100000)]},
]


class RichesRows(unittest.TestCase):
    """riches_rows, riches_match, todo and the arrival line: pure."""

    def test_rows(self):
        rows = riches.riches_rows(RESULT)
        self.assertEqual([(r["system"], r["id64"], r["jumps"], len(r["bodies"])) for r in rows],
                         [("Alpha Rich", 1001, 0, 2), ("Beta Rich", 1002, 1, 1), ("Gamma Rich", 1003, 2, 1)])
        b = rows[0]["bodies"][0]
        self.assertEqual((b["name"], b["subtype"], b["ls"], b["scan"], b["map"], b["terraformable"]),
                         ("Alpha Rich 1", "Earth-like world", 500.0, 1200000, 3000000, 0))
        self.assertEqual(rows[1]["bodies"][0]["terraformable"], 1)
        # the answer may hold the list under "result" or "systems"
        self.assertEqual(len(riches.riches_rows({"result": RESULT})), 3)
        self.assertEqual(len(riches.riches_rows({"systems": RESULT})), 3)

    def test_real_answer(self):
        """A real answer (recorded 2026-10-06 from Colonia, trimmed): the systems and bodies as Spansh sends them, the
        body's id64 (a string) giving the game's BodyID (its top 9 bits), as body_id is everywhere else."""
        import json
        import os
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_riches.json"), encoding="utf-8") as f:
            answer = json.load(f)
        rows = riches.riches_rows(answer["result"])
        self.assertEqual([r["system"] for r in rows], ["Colonia", "Eol Prou PC-K c9-4", "Eol Prou WY-R d4-388"])
        self.assertEqual((rows[1]["id64"], rows[1]["jumps"], len(rows[1]["bodies"])), (1167391498834, 1, 2))
        b = rows[1]["bodies"][0]
        self.assertEqual((b["name"], b["subtype"], b["terraformable"], b["body_id"], round(b["ls"])),
                         ("Eol Prou PC-K c9-4 A 6", "High metal content world", 1, 9, 364))
        self.assertEqual((b["scan"], b["map"]), (161983, 588537))
        self.assertEqual([x["body_id"] for x in rows[2]["bodies"]], [13, 17])   # "A 7" and "BC 3"

    def test_lenient_and_errors(self):
        rows = riches.riches_rows([
            "junk", {"id64": 5}, {"name": "  ", "id64": 6},
            {"name": "Ok", "id64": "77", "x": "bad", "jumps": "x",
             "bodies": [None, {"name": ""}, {"name": " Ok  1 ", "estimated_scan_value": "oops"},
                        {"name": "Ok 2", "distance_to_arrival": float("inf"), "estimated_scan_value": 10}]},
            {"system": "Named By System", "id64": 2 ** 70}])
        self.assertEqual([r["system"] for r in rows], ["Ok", "Named By System"])
        self.assertEqual((rows[0]["id64"], rows[0]["x"], rows[0]["jumps"]), (77, None, 0))
        self.assertEqual([(b["name"], b["scan"], b["ls"]) for b in rows[0]["bodies"]], [("Ok 1", None, None), ("Ok 2", 10, None)])
        self.assertIsNone(rows[1]["id64"])   # out of range: no id64, matched by name
        for bad in (None, {}, "x", 5, [], [{"bodies": []}], {"result": "no"}):
            with self.assertRaises(riches.RichesError):
                riches.riches_rows(bad)
        with unittest.mock.patch.object(riches, "RICHES_MAX_SYSTEMS", 2):
            with self.assertRaisesRegex(riches.RichesError, "longer than Outrider keeps"):
                riches.riches_rows(RESULT)

    def test_match(self):
        rows = riches.riches_rows(RESULT + [dict(RESULT[0], jumps=1)])   # Alpha Rich twice
        self.assertEqual(riches.riches_match(rows, 1002, "x"), 1)
        self.assertEqual(riches.riches_match(rows, None, "  gamma  RICH "), 2)
        self.assertEqual(riches.riches_match(rows, 1001, "Alpha Rich", near=0), 0)
        self.assertEqual(riches.riches_match(rows, 1001, "Alpha Rich", near=1), 3)
        self.assertEqual(riches.riches_match(rows, 1001, "Alpha Rich", near=4), 3)   # past the last: the latest before
        self.assertIsNone(riches.riches_match(rows, 999, "Nowhere"))

    def test_todo_and_value(self):
        bodies = riches.riches_rows(RESULT)[0]["bodies"]
        out = riches.todo(bodies, {"alpha rich 1"}, set(), True)
        self.assertEqual([(b["scanned"], b["mapped"], b["done"]) for b in out], [(True, False, False), (False, False, False)])
        out = riches.todo(bodies, {"alpha rich 1"}, {"alpha rich 1"}, True)
        self.assertTrue(out[0]["done"])
        out = riches.todo(bodies, {"alpha rich 1"}, set(), False)   # a route that does not count the map
        self.assertTrue(out[0]["done"])
        self.assertEqual(riches.body_value(bodies[0], True), 4200000)
        self.assertEqual(riches.body_value(bodies[0], False), 1200000)
        self.assertIsNone(riches.body_value({"name": "x", "scan": None, "map": 5}, False))
        self.assertEqual(riches.body_value({"name": "x", "scan": None, "map": 5}, True), 5)

    def test_text(self):
        rows = riches.riches_rows(RESULT)
        left = riches.todo(rows[0]["bodies"], set(), set(), True)
        self.assertEqual(riches.riches_text(rows, 0, left),
                         "Two bodies here: the best is a earth-like world, about 1.2 million credits, 500 light seconds out.")
        self.assertEqual(riches.riches_text(rows, 1, riches.todo(rows[1]["bodies"], set(), set(), True)),
                         "One body here: the best is a high metal content world, about 450 thousand credits, 300 light seconds out.")
        self.assertEqual(riches.riches_text(rows, 0, []), "Nothing left to do in Alpha Rich. Next stop: Beta Rich.")
        self.assertEqual(riches.riches_text(rows, 2, []), "Nothing left to do in Gamma Rich. Road to Riches complete.")
        self.assertEqual([riches.money(n) for n in (None, 950, 12000, 1000000, 2450000)],
                         [None, "950", "12 thousand", "1 million", "2.5 million"])
        # S12: the next stop past the systems you finished
        self.assertEqual(riches.riches_text(rows, 0, [], 1), "Nothing left to do in Alpha Rich. Next stop: Gamma Rich, "
                                                              "skipping 1 system you've finished.")
        self.assertEqual(riches.riches_text(rows, 0, [], 2), "Nothing left to do in Alpha Rich. Road to Riches complete.")
        self.assertEqual(riches.next_stop(rows + rows, 0, 2), "Next stop: Alpha Rich, skipping 2 systems you've finished.")
        self.assertEqual([riches.had_work(k, r) for k, r in (("riches", rows[0]), ("riches", dict(rows[0], bodies=[])),
                                                             ("exo", rows[0]), ("trade", rows[0]))], [True, False, False, False])


class RichesRoute(unittest.TestCase):
    """The route in the database, progress by the journal, the plot and the endpoints (fakes only)."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()

    ts = hwy_ts
    jump = hwy_jump

    def store(self, start=-100, mapping=True):
        self.jump(start, 1001, "Alpha Rich", 0)
        return self.state.riches_store(riches.riches_rows(RESULT), {"options": {"use_mapping_value": mapping}})

    def moments(self):
        return [(m["what"], m["text"]) for m in self.j.moments if m["kind"] == "riches"]

    def scan(self, s, system, addr, body_id, name):
        self.j.handle({"event": "Scan", "timestamp": self.ts(s), "StarSystem": system, "SystemAddress": addr,
                       "BodyID": body_id, "BodyName": name, "WasDiscovered": False, "WasMapped": False,
                       "ScanType": "Detailed", "DistanceFromArrivalLS": 500.0, "PlanetClass": "Water world",
                       "MassEM": 1.0, "TerraformState": ""})

    def mapped(self, s, addr, body_id, name):
        self.j.handle({"event": "SAAScanComplete", "timestamp": self.ts(s), "SystemAddress": addr, "BodyID": body_id,
                       "BodyName": name, "ProbesUsed": 6, "EfficiencyTarget": 8})

    def test_store_and_state(self):
        rc = self.store()
        rows = self.j.riches_route(rc)
        self.assertEqual([(r["system"], len(r["bodies"])) for r in rows], [("Alpha Rich", 2), ("Beta Rich", 1), ("Gamma Rich", 1)])
        self.assertEqual((rc["at"], rc["furthest"], rc["done_ts"], rc["options"]), (0, 0, None, {"use_mapping_value": True}))
        meta, rows = self.state.riches_state()
        self.assertEqual(self.state.riches_next(meta, rows), 1)
        self.assertEqual(rows[0]["bodies"][1]["name"], "Alpha Rich 2 a")
        # a new plot replaces the old route entirely
        self.state.riches_store(riches.riches_rows(RESULT[1:]), {"options": {}})
        self.assertEqual(self.db.execute("SELECT count(*) FROM riches_route").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM riches_bodies").fetchone()[0], 2)
        self.state.riches_clear()
        self.assertEqual((self.state.riches_state(), self.db.execute("SELECT count(*) FROM riches_bodies").fetchone()[0]),
                         ((None, []), 0))

    def test_arrival_progress_and_done(self):
        self.store()
        self.jump(-90, 1002, "Beta Rich", 20)
        what = self.moments()
        self.assertEqual(what[0][0], "next")
        self.assertIn("One body here", what[0][1])
        meta = ed_outrider.meta_get(self.db, "riches")
        self.assertEqual((meta["at"], meta["furthest"]), (1, 1))
        # the one body there: scanned is not enough while the route counts the map; mapped finishes the system
        self.scan(-80, "Beta Rich", 1002, 4, "Beta Rich 4")
        self.assertEqual(len(self.moments()), 1)
        self.mapped(-70, 1002, 4, "Beta Rich 4")
        self.assertEqual(self.moments()[1], ("done", "Everything here is done. Next stop: Gamma Rich."))
        self.mapped(-60, 1002, 4, "Beta Rich 4")   # a remap: nothing more said
        self.assertEqual(len(self.moments()), 2)
        # the last system: arriving says what is there, doing it ends the route
        self.jump(-50, 1003, "Gamma Rich", 45)
        self.assertEqual(self.moments()[2][0], "next")
        self.scan(-40, "Gamma Rich", 1003, 1, "Gamma Rich 1")
        self.mapped(-30, 1003, 1, "Gamma Rich 1")
        self.assertEqual(self.moments()[3], ("complete", "Everything here is done. Road to Riches complete."))
        self.assertTrue(ed_outrider.meta_get(self.db, "riches")["done_ts"])
        self.assertEqual(ed_outrider.meta_get(self.db, "riches")["done_id64"], 1003)
        self.assertIsNotNone(self.state.survey_summary())       # still shown in the system where it finished
        self.jump(-20, 1001, "Alpha Rich", 0)   # after the end: quiet, and the route clears (the author, 2026-10-24)
        self.assertEqual(len(self.moments()), 4)
        self.assertIsNone(ed_outrider.meta_get(self.db, "riches"))
        self.assertIsNone(self.state.survey_summary())
        self.assertEqual(self.db.execute("SELECT count(*) FROM riches_route").fetchone()[0], 0)

    def test_scan_only_route(self):
        self.store(mapping=False)   # use_mapping_value off: a scan finishes a body
        self.scan(-90, "Alpha Rich", 1001, 1, "Alpha Rich 1")
        self.scan(-80, "Alpha Rich", 1001, 2, "Alpha Rich 2 a")
        self.assertEqual(self.moments(), [("done", "Everything here is done. Next stop: Beta Rich.")])

    def test_detour_and_back(self):
        self.store()
        self.jump(-90, 555, "Somewhere Else", 99)
        self.assertEqual(self.moments(), [("off_route", "Off route: detour.")])
        self.jump(-80, 555, "Somewhere Else", 99)   # a relog / the same system again: said once
        self.jump(-70, 1002, "Beta Rich", 20)
        self.assertEqual([w for w, _ in self.moments()], ["off_route", "back"])
        self.assertTrue(self.moments()[1][1].startswith("Back on the route. One body here"))
        self.assertIsNone(ed_outrider.meta_get(self.db, "riches")["off_route"])

    def test_catch_up_and_reread_say_nothing(self):
        self.store()
        # a jump written before the route was plotted, and one long ago (a journal being caught up on): no moments
        self.j.handle({"event": "FSDJump", "timestamp": self.ts(-500), "StarSystem": "Beta Rich", "SystemAddress": 1002,
                       "StarPos": [20, 0, 0]})
        self.assertEqual((self.moments(), ed_outrider.meta_get(self.db, "riches")["at"]), ([], 0))
        # progress read from an old journal is marked but never spoken
        self.jump(-90000, 1002, "Beta Rich", 20)
        old = ed_outrider.iso_ts(time.time() - 3 * 86400)
        rc = ed_outrider.meta_get(self.db, "riches")
        rc.update(at=1, furthest=1, since_ts=None, created_ts="2000-01-01T00:00:00Z")
        ed_outrider.meta_set(self.db, "riches", rc)
        self.j.handle({"event": "Scan", "timestamp": old, "StarSystem": "Beta Rich", "SystemAddress": 1002, "BodyID": 4,
                       "BodyName": "Beta Rich 4", "ScanType": "Detailed", "DistanceFromArrivalLS": 300.0,
                       "PlanetClass": "Water world", "MassEM": 1.0, "TerraformState": ""})
        self.j.handle({"event": "SAAScanComplete", "timestamp": old, "SystemAddress": 1002, "BodyID": 4,
                       "BodyName": "Beta Rich 4", "ProbesUsed": 6, "EfficiencyTarget": 8})
        self.assertEqual(self.moments(), [])
        self.assertEqual(ed_outrider.meta_get(self.db, "riches")["said_done"], 1)

    def test_route_survives_a_journal_reread(self):
        self.assertNotIn("riches", ed_outrider.RESET_JOURNAL_DATA)
        self.assertNotIn("riches_route", ed_outrider.RESET_JOURNAL_DATA)
        self.assertNotIn("riches_bodies", ed_outrider.RESET_JOURNAL_DATA)

    def test_view_marks_bodies_from_the_journal(self):
        self.store()
        self.scan(-90, "Alpha Rich", 1001, 1, "Alpha Rich 1")
        self.mapped(-80, 1001, 1, "Alpha Rich 1")
        v = self.state.riches_view()
        r = v["route"]
        self.assertEqual((r["from"], r["to"], r["count"], r["at"], r["next"], r["first"]), ("Alpha Rich", "Gamma Rich", 3, 0, 1, 0))
        first = r["systems"][0]
        self.assertEqual([(b["name"], b["scanned"], b["mapped"], b["done"]) for b in first["bodies"]],
                         [("Alpha Rich 1", True, True, True), ("Alpha Rich 2 a", False, False, False)])
        self.assertEqual((first["left"], first["value"], first["value_left"], first["id"]), (1, 6500000, 2300000, "1001"))
        self.assertEqual([s["system"] for s in r["systems"]], ["Alpha Rich", "Beta Rich", "Gamma Rich"])
        self.assertEqual(v["defaults"]["radius"], 25)

    def test_copy_next(self):
        cb = types_ns(enabled=True, tool="wl-copy", copied=[])
        cb.copy = lambda text: cb.copied.append(text) or True
        self.state.clipboard = cb
        self.store()
        self.assertTrue(self.state.riches_copy_next(force=True))
        self.jump(-10, 1002, "Beta Rich", 20)
        self.assertTrue(self.state.riches_copy_next())
        self.assertFalse(self.state.riches_copy_next())   # once per arrival
        self.assertEqual(cb.copied, ["Beta Rich", "Gamma Rich"])

    def test_survey_summary(self):
        """The line under the tiles for a survey route (the payload's `survey`): the next system, where you are on it,
        what is left where you are; None without a route. The Highway's summary carries its plot time too (which of
        the two the line shows)."""
        self.assertIsNone(self.state.survey_summary())
        self.store()
        s = self.state.survey_summary()
        self.assertEqual((s["kind"], s["at"], s["index"], s["total"], s["complete"], s["off_route"]), ("riches", 0, 1, 2, False, False))
        self.assertEqual((s["next"]["name"], s["next"]["jumps"]), ("Beta Rich", 1))
        self.assertEqual(s["left_here"], 2)   # Alpha Rich's two bodies, neither scanned
        self.jump(-10, 1002, "Beta Rich", 20)
        s = self.state.survey_summary()
        self.assertEqual((s["at"], s["index"], s["next"]["name"], s["left_here"]), (1, 2, "Gamma Rich", 1))
        self.assertEqual(self.state.payload()["survey"]["at"], 1)   # in the page's payload

    def test_skip_finished_systems(self):
        """S12: the next stop passes over the systems after where you are that you have finished (they had work, none
        is left): the line (skipped, with their names), the tab, the clipboard, the co-pilot button and the voice. The
        last system is never passed over (arriving there ends the route), nor a system that came without bodies."""
        cb = types_ns(enabled=True, tool="wl-copy", copied=[])
        cb.copy = lambda text: cb.copied.append(text) or True
        cb.info = lambda: {"enabled": True, "available": True}
        self.state.clipboard = cb
        extra = {"name": "Delta Rich", "id64": 1004, "x": 70, "y": 0, "z": 0, "jumps": 1,
                 "bodies": [body("Delta Rich 2", "Water world", 900, 700000, 1300000)]}
        self.jump(-100, 1001, "Alpha Rich", 0)
        self.state.riches_store(riches.riches_rows(RESULT + [extra]), {"options": {"use_mapping_value": True}})
        # Beta and Gamma done on an earlier trip (scanned and mapped in your journal)
        for s, (sysname, addr, bid, name) in enumerate((("Beta Rich", 1002, 4, "Beta Rich 4"), ("Gamma Rich", 1003, 1, "Gamma Rich 1"))):
            self.scan(-99 + s, sysname, addr, bid, name)
            self.mapped(-98.5 + s, addr, bid, name)
        s = self.state.survey_summary()
        self.assertEqual((s["index"], s["next"]["name"], s["skipped"], s["skipped_names"]), (3, "Delta Rich", 2, ["Beta Rich", "Gamma Rich"]))
        self.assertEqual(s["next"]["jumps"], 4)   # Beta's leg 1, Gamma's 2 and Delta's 1: the jumps from where you are
        self.assertEqual(self.state.riches_view()["route"]["next"], 3)
        self.assertEqual(self.state.copilot_next(), (("next", ("survey", 3)), None))
        self.assertTrue(self.state.riches_copy_next(force=True))
        self.assertEqual(cb.copied, ["Delta Rich"])
        # finishing Alpha says the stop it skips to
        self.scan(-90, "Alpha Rich", 1001, 1, "Alpha Rich 1")
        self.mapped(-89, 1001, 1, "Alpha Rich 1")
        self.scan(-88, "Alpha Rich", 1001, 2, "Alpha Rich 2 a")
        self.mapped(-87, 1001, 2, "Alpha Rich 2 a")
        self.assertEqual(self.moments()[-1], ("done", "Everything here is done. Next stop: Delta Rich, skipping 2 systems you've finished."))
        self.assertEqual([m["next"] for m in self.j.moments if m["kind"] == "riches"][-1], "Delta Rich")
        # arriving at Beta anyway (finished): the next stop is past Gamma too
        self.jump(-80, 1002, "Beta Rich", 20)
        self.assertEqual(self.moments()[-1], ("next", "Nothing left to do in Beta Rich. Next stop: Delta Rich, skipping 1 system you've finished."))
        self.assertEqual(self.state.survey_summary()["next"]["jumps"], 3)
        # Delta done as well: the last system is still the next stop (arriving there ends the route)
        self.scan(-70, "Delta Rich", 1004, 2, "Delta Rich 2")
        self.mapped(-69, 1004, 2, "Delta Rich 2")
        s = self.state.survey_summary()
        self.assertEqual((s["index"], s["skipped"]), (3, 1))
        self.jump(-60, 1004, "Delta Rich", 70)
        self.assertEqual(self.moments()[-1][0], "complete")
        self.assertEqual(ed_outrider.meta_get(self.db, "riches")["done_id64"], 1004)   # finished on arrival: where

    def test_two_routes_one_clipboard(self):
        """A Highway route and a Road to Riches route at once: only the one plotted last copies its next system (one
        copy per jump), and the tab's map gets the whole Riches route's points."""
        cb = types_ns(enabled=True, tool="wl-copy", copied=[])
        cb.copy = lambda text: cb.copied.append(text) or True
        cb.info = lambda: {"enabled": True, "available": True}
        self.state.clipboard = cb
        self.assertIsNone(self.state.route_newest())
        self.store()
        self.assertEqual(self.state.route_newest(), "riches")
        self.assertEqual(self.state.riches_view()["route"]["points"], [[0, 0], [20, 0], [45, 0]])
        # a Highway route plotted after it takes the clipboard over
        ed_outrider.meta_set(self.db, "highway", {"id": "h", "created_ts": "2999-01-01T00:00:00Z", "at": 0})
        self.assertEqual(self.state.route_newest(), "highway")
        self.jump(-10, 1002, "Beta Rich", 20)
        self.assertFalse(self.state.riches_copy_next())
        self.assertEqual(cb.copied, [])
        # cleared: Road to Riches has it again
        ed_outrider.meta_set(self.db, "highway", None)
        self.assertEqual(self.state.route_newest(), "riches")
        # finished but left on screen: the other route has the clipboard (it went to neither)
        ed_outrider.meta_set(self.db, "highway", {"id": "h", "created_ts": "2000-01-01T00:00:00Z", "at": 0})
        rc = ed_outrider.meta_get(self.db, "riches")
        ed_outrider.meta_set(self.db, "riches", dict(rc, done_ts="2026-01-01T00:00:00Z"))
        self.assertEqual(self.state.route_newest(), "highway")

    # ---- the plot ----

    def spansh(self, script, knows=None):
        """Spansh answering `script`; its name search (State.highway_ends) knows every system, else only `knows`."""
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession(script)
        sp.system_record = unittest.mock.AsyncMock(side_effect=lambda n: {"name": n, "id64": 1, "x": 0.0, "y": 0.0, "z": 0.0}
                                                   if knows is None or n in knows else None)
        self.state.spansh = sp
        return sp

    def test_plot_from_a_system_spansh_does_not_know(self):
        """A fresh discovery Spansh does not know yet: the survey is plotted from a Spansh system near it (out of what
        Spansh sent about the neighbourhood) and starts with the jump there, nothing to survey in yours."""
        self.jump(-100, 900, "Fresh", -60)
        self.state.bases = {1001: ("spansh", {"name": "Alpha Rich", "x": 0.0, "y": 0.0, "z": 0.0})}
        sp = self.spansh([(200, {"job": "r1", "status": "ok", "result": RESULT})], knows=())

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                self.state.riches_start_plot({"range": 42.5})
                await self.state.riches_task
        asyncio.run(go())
        p = self.state.riches_plotting
        self.assertEqual(p["state"], "done", p["error"])
        # nothing in range held: Spansh is asked around Fresh first (it knows nothing nearer here), then the plot
        self.assertEqual([c[:2] for c in sp.session.calls][:2], [("POST", ed_outrider.SPANSH_SEARCH), ("POST", ed_outrider.SPANSH_RICHES)])
        self.assertEqual(sp.session.calls[1][2]["from"], "Alpha Rich")
        self.assertIn("Spansh doesn't know Fresh yet: the route starts with a 60.0 ly jump to Alpha Rich", p["note"])
        self.assertIn("longer than this ship's 42.5 ly range", p["note"])
        meta, rows = self.state.riches_state()
        self.assertEqual([(r["system"], r["jumps"]) for r in rows[:2]], [("Fresh", 0), ("Alpha Rich", 2)])
        self.assertEqual((meta["at"], meta["stand_in"]), (0, p["note"]))
        self.assertEqual(riches.splice_survey(riches.riches_rows(RESULT), 42.5), riches.riches_rows(RESULT))   # nothing to do

    def test_plot_posts_form_fields_and_stores(self):
        self.jump(-100, 1001, "Alpha Rich", 0)
        sp = self.spansh([(200, {"job": "r1", "status": "queued"}), (200, {"job": "r1", "status": "ok", "result": RESULT})])

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot({"range": 42.5, "radius": 30, "min_value": 250000, "loop": True})
                await self.state.riches_task
            return out
        out = asyncio.run(go())
        self.assertEqual(out[1], 202)
        self.assertEqual(self.state.riches_plotting["state"], "done")
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_RICHES))
        # form fields are text on the wire
        self.assertEqual(fields, {"range": "42.5", "radius": "30.0", "max_results": "25", "max_distance": "50000",
                                  "min_value": "250000", "use_mapping_value": "1", "avoid_thargoids": "1", "loop": "1",
                                  "from": "Alpha Rich"})
        self.assertEqual(sp.session.calls[1][0], ed_outrider.SPANSH_RESULTS.format(job="r1"))   # the results are a GET
        meta, rows = self.state.riches_state()
        self.assertEqual((len(rows), meta["at"], meta["options"]["min_value"], meta["options"]["loop"]), (3, 0, 250000, True))

    def test_plot_failures_are_said(self):
        self.jump(-100, 1001, "Alpha Rich", 0)
        for script, why in (([(400, {"error": "Could not find starting system"})], "Spansh: Could not find starting system"),
                            ([(200, {"job": "e", "status": "ok", "result": []})], "found no route"),
                            # Spansh's answer from inside the bubble (Sol, Lave: 2026-10-26): the start alone, nothing to visit
                            ([(200, {"job": "e", "status": "ok", "result": [dict(RESULT[0], bodies=[])]})], "found nothing to visit"),
                            ([(200, {"job": "e", "status": "ok", "result": {"unknown": 1}})], "shape Outrider does not know"),
                            ([ed_outrider.ClientError("refused")], "cannot be reached")):
            self.spansh(script)

            async def go():
                self.state.riches_start_plot({"range": 40})
                await self.state.riches_task
            asyncio.run(go())
            self.assertEqual(self.state.riches_plotting["state"], "failed")
            self.assertIn(why, self.state.riches_plotting["error"])
            self.assertEqual(self.state.riches_state(), (None, []))

    def test_plot_validation(self):
        self.jump(-100, 1001, "Alpha Rich", 0)

        async def go():
            return [self.state.riches_start_plot(b)[1] for b in (
                {}, {"range": "far"}, {"range": 0}, {"range": 40, "radius": 5000}, {"range": 40, "max_results": 0},
                {"range": 40, "loop": "yes"}, {"range": 40, "use_mapping_value": 1}, {"range": 40, "min_value": -1},
                {"from": "x" * 500, "range": 40}, {"range": True})]
        self.assertEqual(asyncio.run(go()), [400] * 10)
        self.assertIsNone(self.state.riches_task)

    def test_plot_range_from_the_ship_and_busy(self):
        self.j.handle({"event": "Loadout", "timestamp": "2026-01-02T00:00:00Z", "Ship": "krait_light", "ShipID": 7,
                       "ShipName": "S", "ShipIdent": "S-1", "HullHealth": 1.0, "UnladenMass": 410.5, "CargoCapacity": 8,
                       "MaxJumpRange": 58.4, "FuelCapacity": {"Main": 32.0, "Reserve": 0.63},
                       "Modules": [{"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size5_class5", "Health": 1.0}]})
        self.jump(-100, 1001, "Alpha Rich", 0)
        sp = self.spansh([(200, {"job": "slow", "status": "queued"})])

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                first = self.state.riches_start_plot({})
                second = self.state.riches_start_plot({})
                await asyncio.sleep(0.05)
                self.state.riches_clear()   # cancels the job that is still waiting
                await asyncio.sleep(0.02)
            return first, second
        first, second = asyncio.run(go())
        self.assertEqual((first[1], second[1]), (202, 409))
        self.assertAlmostEqual(float(sp.session.calls[0][2]["range"]), ed_outrider.fleet_range(
            self.state.fleet_ship(7)["figures"]), places=1)
        self.assertEqual(self.state.riches_plotting["error"], "cancelled")

    def test_endpoints(self):
        from aiohttp.test_utils import TestClient, TestServer
        self.jump(-100, 1001, "Alpha Rich", 0)
        self.spansh([(200, {"job": "e1", "status": "ok", "result": RESULT})])

        async def go():
            out = {}
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.get("/api/riches")
                out["empty"] = await r.json()
                r = await c.post("/api/riches/plot", json={"range": 40})
                out["started"] = (r.status, await r.json())
                await self.state.riches_task
                r = await c.get("/api/riches")
                out["view"] = await r.json()
                r = await c.post("/api/riches/plot", json=[1])
                out["list"] = r.status
                r = await c.get("/api/riches", headers={"Sec-Fetch-Site": "cross-site"})
                out["cross"] = r.status
                r = await c.post("/api/riches/clear", headers={"Origin": "http://evil.example"})
                out["evil"] = r.status
                r = await c.post("/api/riches/clear")
                out["cleared"] = r.status
                r = await c.get("/api/riches")
                out["after"] = (await r.json())["route"]
            return out
        out = asyncio.run(go())
        self.assertIsNone(out["empty"]["route"])
        self.assertEqual(out["started"][0], 202)
        self.assertEqual(out["view"]["plotting"]["state"], "done")
        self.assertEqual(out["view"]["route"]["count"], 3)
        self.assertEqual((out["list"], out["cross"], out["evil"], out["cleared"], out["after"]), (400, 403, 403, 200, None))


if __name__ == "__main__":
    unittest.main()


def _exo_answer():
    import json
    import os
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_exo.json"), encoding="utf-8") as f:
        return json.load(f)


class ExoRoute(unittest.TestCase):
    """Expressway to Exomastery in the survey slot (the author, 2026-10-07): Spansh's answer with each body's species,
    progress from the journal's samples (own_organic, by BodyID and species), its own lines and alert (`exo`), and the
    plot through its own endpoint. A real answer: tests/fixtures/spansh_exo.json (from Colonia, 2026-10-07)."""
    setUp = RichesRoute.setUp
    spansh = RichesRoute.spansh
    ts = hwy_ts
    jump = hwy_jump

    def store_exo(self):
        rows = riches.riches_rows(_exo_answer()["result"])
        self.jump(-100, rows[0]["id64"], rows[0]["system"], 0)
        self.state.riches_store(rows, {"options": {}, "kind": "exo"})
        return rows

    def analyse(self, s, addr, body_id, species):
        self.j.handle({"event": "ScanOrganic", "timestamp": self.ts(s), "ScanType": "Analyse", "SystemAddress": addr,
                       "Body": body_id, "Genus": "$Codex_Ent_X;", "Genus_Localised": species.split()[0],
                       "Species": "$Codex_Ent_" + species.replace(" ", "_") + ";", "Species_Localised": species})

    def test_rows_with_species(self):
        rows = riches.riches_rows(_exo_answer()["result"])
        b = rows[1]["bodies"][0]
        self.assertEqual((b["name"], b["body_id"], len(b["species"])), ("Eol Prou PX-T d3-813 ABC 2 e", 28, 7))
        self.assertEqual(b["species"][0], {"genus": "Frutexa", "species": "Frutexa Flammasis", "value": 10326000, "count": 5})
        self.assertEqual([x["value"] for x in b["species"]], sorted((x["value"] for x in b["species"]), reverse=True))
        self.assertEqual(riches._species([None, {"subtype": ""}, {"subtype": "Tubus Rosarium", "value": "x"}]),
                         [{"genus": None, "species": "Tubus Rosarium", "value": None, "count": None}])

    def test_arrival_progress_and_done(self):
        rows = self.store_exo()
        sys1 = rows[1]
        self.jump(-10, sys1["id64"], sys1["system"], 20)
        what, text = self.moments_exo()[-1]
        self.assertEqual(what, "next")
        self.assertTrue(text.startswith("14 species on two bodies here: the best, Frutexa Flammasis on ABC 2 e, about 10.3 million"), text)
        # S9-S29: with nothing in your codex, every species left would be new: counted, the best named first
        m = [m for m in self.j.moments if m["kind"] == "exo"][-1]
        distinct = len({x["species"] for b in sys1["bodies"] for x in b["species"]})   # one name counts once
        self.assertEqual((m["codex_new"], m["codex_best"]), (distinct, "Frutexa Flammasis"))
        s = self.state.survey_summary()
        self.assertEqual((s["kind"], s["at"], s["left_here"]), ("exo", 1, 14))
        out = self.state.riches_view()["route"]
        self.assertEqual(out["kind"], "exo")
        row = out["systems"][1]
        self.assertEqual((row["left"], len(row["bodies"]), len(row["bodies"][0]["species"])), (14, 2, 7))
        # every species sampled on both bodies: the last says so, once, with the next stop
        n = 0
        for b in sys1["bodies"]:
            for x in b["species"]:
                n += 1
                self.analyse(-5 + n * 0.01, sys1["id64"], b["body_id"], x["species"])
        self.assertEqual(self.state.survey_summary()["left_here"], 0)
        self.assertEqual(self.moments_exo()[-1], ("done", f"Every species here is sampled. Next stop: {rows[2]['system']}."))
        self.assertEqual(len([m for m in self.moments_exo() if m[0] == "done"]), 1)
        self.assertEqual(self.state.riches_view()["route"]["systems"][1]["left"], 0)

    def moments_exo(self):
        return [(m["what"], m["text"]) for m in self.j.moments if m["kind"] == "exo"]

    def test_plot_exo(self):
        self.jump(-100, 1001, "Alpha Rich", 0)
        sp = self.spansh([(200, {"job": "e1", "status": "queued"}), (200, {"job": "e1", "status": "ok", "result": _exo_answer()["result"]})])
        self.assertEqual(self.state.riches_start_plot({"kind": "moon"})[1], 400)

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot({"kind": "exo", "range": 50, "radius": 25, "min_value": 1000000})
                await self.state.riches_task
            return out
        out = asyncio.run(go())
        self.assertEqual(out[1], 202)
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_EXO))
        self.assertNotIn("use_mapping_value", fields)   # Exomastery has none
        meta, rows = self.state.riches_state()
        self.assertEqual((meta["kind"], len(rows), len(rows[1]["bodies"][0]["species"])), ("exo", 3, 7))
        # one slot: a Road to Riches plot replaces it
        self.state.riches_store(riches.riches_rows(RESULT), {"options": {}})
        meta, rows = self.state.riches_state()
        self.assertEqual((meta.get("kind"), rows[0]["system"], self.db.execute("SELECT COUNT(*) FROM riches_species").fetchone()[0]),
                         (None, "Alpha Rich", 0))


def _fixture(name):
    import json
    import os
    with open(os.path.join(os.path.dirname(__file__), "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


class SurveyKinds(unittest.TestCase):
    """G4: one table of the survey slot's route kinds (outrider.riches.SURVEY_KINDS) read by the server, the overlay and
    (its copy) the page; S52's Earth-like and ammonia world routes and S51's sweep are kinds of it. Probed answers:
    tests/fixtures/spansh_body_types.json, spansh_tourist.json (2026-10-13). Fakes only."""
    setUp = RichesRoute.setUp
    spansh = RichesRoute.spansh
    scan = RichesRoute.scan
    mapped = RichesRoute.mapped
    ts = hwy_ts
    jump = hwy_jump

    def test_page_table_in_step(self):
        """page.js SURVEY holds every kind, one line each, with the table's glyph, name, what, a, work and left; each
        kind's alert is a row of the page's alerts table."""
        import os
        import re
        with open(os.path.join(os.path.dirname(__file__), "..", "static", "page.js"), encoding="utf-8") as f:
            page = f.read()
        block = page[page.index("const SURVEY = {"):page.index("const surveyOf")]
        self.assertEqual(re.findall(r"^  (\w+): \{glyph", block, re.M), list(riches.SURVEY_KINDS))
        js = lambda v: "null" if v is None else '"' + v + '"'
        for key, k in riches.SURVEY_KINDS.items():
            want = (f'  {key}: {{glyph: "{k.glyph}", name: "{k.name}", what: "{k.what}", a: "{k.a}", work: {js(k.work)}, '
                    f'left: [{", ".join(js(x) for x in k.left)}]')
            self.assertIn(want, block, key)
            self.assertIn(f'["{k.alert}", "', page[page.index("const ALERTS"):], key)
            self.assertTrue(hasattr(ed_outrider, k.url), k.url)
        self.assertEqual([riches.left_words(k, n) for k, n in (("riches", 1), ("elw", 2), ("exo", 3), ("trade", 1))],
                         ["1 body to do here", "2 bodies to do here", "3 species to sample here", "1 trade to make here"])
        self.assertEqual((riches.kind_of(None), riches.kind_of({"kind": "bogus"}), riches.kind_of({"kind": "aw"})),
                         ("riches", "riches", "aw"))

    def test_worlds_answers_are_road_to_riches(self):
        """P3 (U3): Spansh's Earth-like and ammonia routes are the Road to Riches router asked for one body type: the
        answer reads as Road to Riches' does."""
        fx = _fixture("spansh_body_types.json")
        self.assertEqual(fx["elw"]["parameters"]["body_types"], ["Earth-like world"])
        elw = riches.survey_rows("elw", fx["elw"]["result"])
        self.assertEqual([len(r["bodies"]) for r in elw], [0, 1, 1, 1, 1])
        self.assertEqual({b["subtype"] for r in elw for b in r["bodies"]}, {"Earth-like world"})
        b = elw[1]["bodies"][0]
        self.assertEqual((b["name"], b["scan"], b["map"]), ("Eol Prou TD-S d4-487 AB 2", 292021, 1061009))
        aw = riches.survey_rows("aw", fx["aw"]["result"])
        self.assertEqual([len(r["bodies"]) for r in aw], [0, 2, 1, 1, 1])
        self.assertEqual({b["subtype"] for r in aw for b in r["bodies"]}, {"Ammonia world"})
        # #18 (2026-10-17): the terraformable route, both body types over Spansh's SCAN-value floor: terraformables only
        self.assertEqual(fx["tf"]["parameters"], {"body_types": ["Rocky body", "High metal content world"], "min_value": "100000"})
        tf = riches.survey_rows("tf", fx["tf"]["result"])
        self.assertEqual([len(r["bodies"]) for r in tf], [0, 4, 4, 5, 4])
        self.assertTrue(all(b["scan"] >= 100000 for r in tf for b in r["bodies"]))
        self.assertEqual({b["subtype"] for r in tf for b in r["bodies"]}, {"High metal content world", "Rocky body"})

    def test_plot_worlds(self):
        """S52: an Earth-like world route plots through Road to Riches' endpoint with Spansh's own page's fields
        (body_types, min_value 1, no mapping value: the map always counts), and is followed as Road to Riches is, with
        its own words; its moments are the Road to Riches alert's, naming the route."""
        self.jump(-100, 1001, "Alpha Rich", 0)
        sp = self.spansh([(200, {"job": "w1", "status": "queued"}), (200, {"job": "w1", "status": "ok", "result": RESULT})])

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot({"kind": "elw", "range": 50, "radius": 40, "min_value": 5,
                                                    "use_mapping_value": "ignored"})
                await self.state.riches_task
            return out
        self.assertEqual(asyncio.run(go())[1], 202)
        self.assertEqual(self.state.riches_plotting["state"], "done", self.state.riches_plotting.get("error"))
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_RICHES))
        self.assertEqual(fields, {"range": "50.0", "radius": "40.0", "max_results": "25", "max_distance": "50000",
                                  "avoid_thargoids": "1", "loop": "0", "from": "Alpha Rich", "min_value": "1",
                                  "body_types": "Earth-like world"})
        meta, rows = self.state.riches_state()
        self.assertEqual((meta["kind"], "use_mapping_value" in meta["options"]), ("elw", False))
        self.assertTrue(self.state.riches_view()["route"]["mapping"])
        self.assertEqual(self.state.survey_summary()["kind"], "elw")
        # followed: a scan alone leaves the body to do (the map counts), the map finishes it
        self.jump(-90, 1002, "Beta Rich", 20)
        self.scan(-80, "Beta Rich", 1002, 4, "Beta Rich 4")
        said = [m for m in self.j.moments if m["kind"] == "riches"]
        self.assertEqual([(m["what"], m["route"]) for m in said], [("next", "elw")])
        self.mapped(-70, 1002, 4, "Beta Rich 4")
        self.jump(-60, 1003, "Gamma Rich", 45)
        self.scan(-50, "Gamma Rich", 1003, 1, "Gamma Rich 1")
        self.mapped(-40, 1003, 1, "Gamma Rich 1")
        said = [(m["what"], m["text"]) for m in self.j.moments if m["kind"] == "riches"]
        self.assertEqual(said[1], ("done", "Everything here is done. Next stop: Gamma Rich."))
        self.assertEqual(said[-1], ("complete", "Everything here is done. Earth-like route complete."))
        # the overlay's Now line names it from the same table
        import outrider.overlay as ov
        parts = ov.route_parts({"kind": "riches", "summary": dict(self.state.survey_summary(), complete=False, next=None,
                                                                    left_here=2)})
        self.assertEqual("".join(t for t, _c in parts), "🌍 To Gamma Rich · 2 bodies to do here")

    def test_plot_terraformable(self):
        """#18 (the author, 2026-10-17): the terraformable route asks Road to Riches for both rocky and high metal content
        worlds with a 100,000 floor (Spansh tests it against the scan value: plain HMC scan under 20 thousand,
        terraformables over 120), whatever min_value the form sends; it is followed with its own words."""
        self.jump(-100, 1001, "Alpha Rich", 0)
        sp = self.spansh([(200, {"job": "t1", "status": "queued"}), (200, {"job": "t1", "status": "ok", "result": RESULT})])

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot({"kind": "tf", "range": 50, "radius": 40, "min_value": 5})
                await self.state.riches_task
            return out
        self.assertEqual(asyncio.run(go())[1], 202)
        self.assertEqual(self.state.riches_plotting["state"], "done", self.state.riches_plotting.get("error"))
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url, fields["min_value"]), ("POST", ed_outrider.SPANSH_RICHES, "100000"))
        sent = fields["body_types"]
        self.assertEqual(sorted(sent if isinstance(sent, list) else [sent]), ["High metal content world", "Rocky body"])
        self.assertEqual((self.state.riches_state()[0]["kind"], self.state.riches_view()["route"]["mapping"]), ("tf", True))
        self.assertEqual(riches.survey_kind("tf").complete, "Terraformable route complete.")

    def test_tourist_rows(self):
        """P2 (U2): the tourist router's answer: its system_jumps in the order to fly them, each with the jumps from the
        one before (a loop back to the start as its last row); an unknown system is refused by name."""
        fx = _fixture("spansh_tourist.json")
        rows = riches.tourist_rows(fx["short"]["result"])
        self.assertEqual([(r["system"], r["jumps"], r["bodies"]) for r in rows],
                         [("Sol", 0, []), ("Alpha Centauri", 1, []), ("Barnard's Star", 1, []), ("Wolf 359", 1, [])])
        self.assertEqual((rows[1]["id64"], rows[1]["x"]), (1178708478315, 3.03125))
        loop = riches.tourist_rows(fx["loop"]["result"])
        self.assertEqual([(r["system"], r["jumps"]) for r in loop][-1], ("Sol", 2))
        self.assertEqual(loop[-1]["id64"], 10477373803)   # a string there
        for bad in (None, {}, {"system_jumps": "x"}, {"system_jumps": [{"system": "Only"}]}, [None, {"system": " "}]):
            with self.assertRaises(riches.RichesError):
                riches.tourist_rows(bad)
        one, two = fx["unknown"]["body"]["error"], fx["unknown_two"]["body"]["error"]
        asked = ["Alpha Centauri", "nonexistent  zzyzx 12", "Qqqq Imaginary 7"]
        self.assertEqual(riches.unknown_systems("Spansh: " + one, asked), ["nonexistent  zzyzx 12"])
        self.assertEqual(riches.unknown_systems(two, asked), ["nonexistent  zzyzx 12", "Qqqq Imaginary 7"])
        self.assertEqual(riches.unknown_systems("Spansh: Could not find starting system", asked), [])

    def sweep(self, script, body):
        sp = self.spansh(script)

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot(dict({"kind": "sweep", "range": 30}, **body))
                if out[1] == 202:
                    await self.state.riches_task
            return out
        return sp, asyncio.run(go())

    def test_plot_and_follow_a_sweep(self):
        """S51: a sweep plots the ticked systems with Spansh's tourist router (repeated destination fields, from where
        you are, no destination of its own), takes the survey slot, and moves on by arrival alone: the next stop on each
        arrival, never a system passed over, "Sweep complete." at its end."""
        fx = _fixture("spansh_tourist.json")
        self.jump(-100, 10477373803, "Sol", 0)
        sp, out = self.sweep([(200, {"job": "t1", "status": "queued"}), (200, fx["short"])],
                             {"systems": ["Wolf 359", " Alpha  Centauri ", "Barnard's Star", "wolf 359", "SOL"], "to": "x"})
        self.assertEqual(out[1], 202)
        self.assertEqual(self.state.riches_plotting["state"], "done", self.state.riches_plotting.get("error"))
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_TOURIST))
        self.assertEqual(fields, {"source": "Sol", "range": "30.0", "loop": "0",
                                  "destination": ["Wolf 359", "Alpha Centauri", "Barnard's Star"]})
        meta, rows = self.state.riches_state()
        self.assertEqual((meta["kind"], meta["options"], [r["system"] for r in rows]),
                         ("sweep", {"range": 30.0, "loop": False, "systems": 3}, ["Sol", "Alpha Centauri", "Barnard's Star", "Wolf 359"]))
        s = self.state.survey_summary()
        self.assertEqual((s["kind"], s["index"], s["next"]["name"], s["left_here"], s["skipped"]), ("sweep", 1, "Alpha Centauri", 0, 0))
        self.jump(-90, 1178708478315, "Alpha Centauri", 3)
        self.jump(-85, 555, "Somewhere Else", 9)   # a detour, then back
        self.jump(-80, 18263140541865, "Barnard's Star", -3)
        self.assertIsNone(ed_outrider.meta_get(self.db, "riches")["done_ts"])
        self.jump(-70, 24860210308521, "Wolf 359", 4)
        said = [(m["what"], m["text"], m["route"]) for m in self.j.moments if m["kind"] == "riches"]
        self.assertEqual(said, [("next", "Next stop: Barnard's Star.", "sweep"), ("off_route", "Off route: detour.", "sweep"),
                                ("back", "Back on the route. Next stop: Wolf 359.", "sweep"),
                                ("complete", "Sweep complete.", "sweep")])
        self.assertTrue(ed_outrider.meta_get(self.db, "riches")["done_ts"])

    def test_sweep_leaves_out_systems_spansh_does_not_know(self):
        """A lost first may be a system Spansh has never heard of: Spansh refuses the whole sweep naming it, so it is
        plotted again without it and the note says so; with none it knows, the plot fails in words."""
        fx = _fixture("spansh_tourist.json")
        self.jump(-100, 10477373803, "Sol", 0)
        refused = (400, {"error": "Could not find destination systems [Fresh Find 1]"})
        sp, out = self.sweep([refused, (200, {"job": "t2", "status": "queued"}), (200, fx["short"])],
                             {"systems": ["Alpha Centauri", "Fresh Find 1"]})
        p = self.state.riches_plotting
        self.assertEqual(p["state"], "done", p.get("error"))
        self.assertIn("Spansh doesn't know Fresh Find 1 yet: left out.", p["note"])
        self.assertEqual([c[2]["destination"] for c in sp.session.calls if c[0] == "POST"], [["Alpha Centauri", "Fresh Find 1"], "Alpha Centauri"])
        meta, _rows = self.state.riches_state()
        self.assertEqual((meta["options"]["unknown"], meta["options"]["systems"], meta["stand_in"]), (["Fresh Find 1"], 1, p["note"]))
        _sp, out = self.sweep([(400, {"error": "Could not find destination systems [Fresh Find 1, Fresh Find 2]"})],
                              {"systems": ["Fresh Find 1", "Fresh Find 2"]})
        self.assertEqual((self.state.riches_plotting["state"], self.state.riches_plotting["error"]),
                         ("failed", "Spansh doesn't know any of these systems yet"))

    def test_sweep_validation(self):
        self.jump(-100, 10477373803, "Sol", 0)
        bad = [{}, {"systems": "Sol"}, {"systems": []}, {"systems": ["Sol"]}, {"systems": ["ok", 5]},
               {"systems": ["x" * 500]}, {"systems": [f"S{i}" for i in range(riches.SWEEP_MAX + 1)]},
               {"systems": ["A"], "loop": "yes"}]
        for b in bad:
            _sp, out = self.sweep([(500, {})], b)
            self.assertEqual(out[1], 400, b)
        self.assertIsNone(self.state.riches_task)
        _sp, out = self.sweep([(500, {})], {"kind": "moon"})
        self.assertEqual((out[1], "elw" in out[0]["error"]), (400, True))
