"""Unit tests: the suggested order by where the bodies are (outrider/overlay.py plan_leg ... order_plan, plan_items: the
Python twin of page.js planLeg ... orderPlan, planItems).

The shared cases in tests/fixtures/plan_order_cases.json run here and in tests/page_unit.js, so the page and the
overlay give one order.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import copy
import json
import os
import unittest

import support  # puts the repository root on sys.path
import outrider.overlay as O  # noqa: E402

CASES = os.path.join(os.path.dirname(os.path.abspath(support.__file__)), "fixtures", "plan_order_cases.json")
STAR = {"body": "A", "pos": [0, 0, 0], "approx": False, "dist": 0}


def item(kind, body, pos, dist, value=1_000_000, approx=False):
    return {"kind": kind, "body": body, "pos": pos, "approx": approx, "dist": dist, "value": value}


def order(items, start=STAR, first=None, prev=None):
    got, _ = O.order_plan(copy.deepcopy(items), start, first, prev)
    return got


def bodies(items):
    return [it["body"] for it in items]


class SharedCases(unittest.TestCase):
    def test_as_the_page(self):
        """The same cases as page_unit.js's "orderPlan: the shared cases": the order, each leg's seconds and its ≈."""
        with open(CASES, encoding="utf-8") as f:
            cases = json.load(f)
        self.assertGreaterEqual(len(cases), 8)
        for c in cases:
            with self.subTest(c["name"]):
                got = order(c["items"], c["start"], c["first"], c["prev"])
                self.assertEqual([[it["kind"], it["body"]] for it in got], c["want"])
                self.assertEqual([None if it["sec"] is None else round(it["sec"], 3) for it in got], c["want_sec"])
                self.assertEqual([it["leg_approx"] for it in got], c["want_approx"])


class Order(unittest.TestCase):
    def setUp(self):
        O.PLAN_MEMO.clear()

    def test_opposite_sides_are_not_neighbours(self):
        """A 1 and A 2 are about as far from the star (1,000 and 1,010 ls), on opposite sides: the old measure (the
        difference of their distances) made them neighbours 10 ls apart; they are 2,010 ls apart."""
        items = [item("map", "A 1", [1000, 0, 0], 1000), item("map", "A 2", [-1010, 0, 0], 1010), item("map", "A 3", [1050, 30, 0], 1050)]
        got = order(items)
        self.assertEqual(bodies(got), ["A 1", "A 3", "A 2"])
        self.assertAlmostEqual(got[2]["ls"], 2060.2, places=1)
        self.assertGreater(got[2]["sec"], 35)
        # without positions (old scans) the fallback keeps the old measure: A 2 next to A 1
        flat = [dict(it, pos=None) for it in items]
        self.assertEqual(bodies(order(flat)), ["A 1", "A 2", "A 3"])

    def test_moons_stay_together(self):
        items = [item("bio", "A 6", [-480, 0, 0], 480), item("bio", "A 5 b", [600, 0.4, 0], 600), item("map", "A 5", [600.5, 0, 0], 600.5),
                 item("bio", "A 7", [-700, 50, 0], 702), item("bio", "A 5 a", [601, 0.3, 0], 601)]
        got = bodies(order(items))
        at = [i for i, b in enumerate(got) if b.startswith("A 5")]
        self.assertEqual(at, list(range(at[0], at[0] + 3)), got)   # the planet and its moons one after another

    def test_map_and_bio_on_one_body(self):
        """Adjacent, the map first whatever the server's order; the second has no leg (0 s) and no time shown."""
        items = [item("bio", "B 1", [900, 0, 0], 900), item("map", "B 2", [300, 0, 0], 300), item("map", "B 1", [900, 0, 0], 900)]
        got = order(items)
        self.assertEqual([(it["kind"], it["body"]) for it in got], [("map", "B 2"), ("map", "B 1"), ("bio", "B 1")])
        self.assertEqual((got[2]["sec"], got[2]["ls"], O.leg_text(got[2])), (0, 0, ""))
        self.assertEqual(got[2]["frm"], "B 1")
        self.assertEqual(got[1]["frm"], "B 2")

    def test_detour_cost(self):
        """A stop's detour: the order's time with it less its time without it; per minute of that for its value (both
        items of a body together)."""
        items = [item("map", "A 1", [1000, 0, 0], 1000, 600_000), item("bio", "A 1", [1000, 0, 0], 1000, 400_000),
                 item("map", "A 3", [1050, 30, 0], 1050), item("map", "A 2", [-1010, 0, 0], 1010)]
        got = order(items)
        self.assertEqual(bodies(got), ["A 1", "A 1", "A 3", "A 2"])
        sc, d = O.sc_seconds, lambda p, q: sum((p[k] - q[k]) ** 2 for k in range(3)) ** 0.5
        a1, a2, a3 = [1000, 0, 0], [-1010, 0, 0], [1050, 30, 0]
        want_a1 = sc(1000) + sc(d(a1, a3)) - sc(d([0, 0, 0], a3))
        self.assertAlmostEqual(got[0]["detour"], want_a1)
        self.assertEqual(got[1]["detour"], got[0]["detour"])
        self.assertAlmostEqual(got[0]["per_min"], 1_000_000 / (want_a1 / 60))   # 600k + 400k
        self.assertAlmostEqual(got[2]["detour"], sc(d(a1, a3)) + sc(d(a3, a2)) - sc(d(a1, a2)))
        self.assertAlmostEqual(got[3]["detour"], sc(d(a3, a2)))                  # the last: only the leg to it
        # you are at A 1: no detour to it, no per-minute figure
        at = order(items, start={"body": "A 1", "pos": a1, "approx": False, "dist": 1000})
        self.assertEqual((at[0]["sec"], at[0]["detour"], at[0]["per_min"]), (0, 0, None))

    def test_keep_rule(self):
        """The order shown stays unless the new one saves 10% of the time left or 30 s."""
        near = [item("map", "A 1", [100, 0, 0], 100), item("map", "A 2", [0, 120, 0], 120)]
        self.assertEqual(bodies(order(near)), ["A 1", "A 2"])
        self.assertEqual(bodies(order(near, prev=["A 2", "A 1"])), ["A 2", "A 1"])            # saves ~1 s: kept
        far = [item("map", "A 1", [1000, 0, 0], 1000), item("map", "A 2", [-1010, 0, 0], 1010), item("map", "A 3", [1050, 30, 0], 1050)]
        self.assertEqual(bodies(order(far, prev=["A 1", "A 2", "A 3"])), ["A 1", "A 3", "A 2"])  # saves 21%: replaced
        stops = [{"body": it["body"], "pos": it["pos"], "approx": False, "dist": it["dist"]} for it in far]
        old, new = [stops[0], stops[1], stops[2]], [stops[0], stops[2], stops[1]]
        self.assertGreater(O.plan_total(STAR, old) - O.plan_total(STAR, new), 0.1 * O.plan_total(STAR, old))
        # 30 s but under 10% (a long order): replaced too
        five = [item("map", "F", [90000, 0, 0], 90000), item("map", "G", [-90000, 0, 0], 90000), item("map", "N1", [1000, 0, 0], 1000),
                item("map", "N2", [-1000, 0, 0], 1000), item("map", "N3", [1020, 30, 0], 1020)]
        prev = ["N1", "N2", "N3", "G", "F"]
        st = {s["body"]: {"body": s["body"], "pos": s["pos"], "approx": False, "dist": s["dist"]} for s in five}
        was, now = O.plan_total(STAR, [st[b] for b in prev]), O.plan_total(STAR, [st[b] for b in bodies(order(five))])
        self.assertTrue(30 <= was - now < 0.1 * was, (was, now))
        self.assertNotEqual(bodies(order(five, prev=prev)), prev)
        # the stops done drop out; a new stop goes in at its cheapest place in the order shown
        self.assertEqual(bodies(order(near + [item("bio", "A 9", [5, 118, 0], 118)], prev=["A 2", "A 1"])), ["A 2", "A 9", "A 1"])

    def test_starts(self):
        """From the first stop you picked (the rest from it), else the body you are at, else the arrival star."""
        items = [item("map", "A 1", [1000, 0, 0], 1000), item("map", "A 2", [-1010, 0, 0], 1010), item("map", "A 3", [1050, 30, 0], 1050),
                 item("map", "A 4", [-1000, 40, 0], 1001)]
        self.assertEqual(bodies(order(items, first="A 2")), ["A 2", "A 4", "A 1", "A 3"])
        self.assertEqual(bodies(order(items, first="Z 9")), bodies(order(items)))   # not in the list: nothing changes
        at3 = {"body": "A 3", "pos": [1050, 30, 0], "approx": False, "dist": 1050}
        self.assertEqual(bodies(order(items, start=at3)), ["A 3", "A 1", "A 4", "A 2"])
        at4 = {"body": "A 4", "pos": [-1000, 40, 0], "approx": False, "dist": 1001}
        self.assertEqual(bodies(order(items, start=at4))[:2], ["A 4", "A 2"])
        # plan_start: at_body, else the arrival star, else the origin with distance 0
        self.assertEqual(O.plan_start({"at_body": {"body": "A 3", "pos": [1, 2, 3], "dist_ls": 1050}, "arrival": {"body": "A"}})["body"], "A 3")
        self.assertEqual(O.plan_start({"at_body": None, "arrival": {"body": "A", "pos": [0, 0, 0], "approx": False, "dist_ls": 0}}),
                         {"body": "A", "pos": [0, 0, 0], "approx": False, "dist": 0})
        self.assertEqual(O.plan_start({}), {"body": None, "pos": None, "approx": False, "dist": 0})

    def test_plan_items_remembers_per_system(self):
        """plan_items keeps the order shown per system (PLAN_MEMO): a nearly equal order found later does not replace
        it; another first stop picked forgets it."""
        u = lambda body, pos, dist: {"body": body, "subtype": "Rocky body", "increment": 900_000, "dist_ls": dist, "pos": pos, "approx": False}
        leaving = {"id64": "9", "honked": True, "unscanned": 0, "bio_pending": [], "at_body": None,
                   "arrival": {"body": "A", "pos": [0, 0, 0], "approx": False, "dist_ls": 0},
                   "unmapped": [u("A 1", [1000, 0, 0], 1000), u("A 2", [-1010, 0, 0], 1010), u("A 4", [-1000, 40, 0], 1001)]}
        first = bodies(O.plan_items(leaving, 500_000, 10_000_000))
        self.assertEqual(O.PLAN_MEMO["9"], {"first": None, "bodies": first})
        swapped = first[:1] + first[:0:-1]
        O.PLAN_MEMO["9"]["bodies"] = swapped
        self.assertEqual(bodies(O.plan_items(leaving, 500_000, 10_000_000)), swapped)        # within 10% and 30 s: kept
        self.assertEqual(bodies(O.plan_items(leaving, 500_000, 10_000_000, first="A 2"))[0], "A 2")
        self.assertEqual(bodies(O.plan_items(leaving, 500_000, 10_000_000, memo=None)), first)   # no memory: the fresh order

    def test_approx_and_fallback_legs(self):
        items = [item("map", "C 2", [40, 0, 0], 40), item("bio", "C 4", [4000, 3000, 0], 5000, approx=True), item("map", "C 3", None, None)]
        got = order(items)
        self.assertEqual(bodies(got), ["C 2", "C 4", "C 3"])                 # no distance at all: last
        self.assertEqual([it["leg_approx"] for it in got], [False, True, True])
        self.assertEqual(O.leg_text(got[1]), "≈" + O.ls_short(got[1]["ls"]))   # distances, never times (2026-11-08)
        self.assertEqual(O.leg_text(got[0]), "40 ls")
        self.assertEqual((got[2]["sec"], got[2]["detour"], O.leg_text(got[2])), (None, None, ""))
        self.assertIsNotNone(got[1]["detour"])                               # the unknown stop after it does not count


if __name__ == "__main__":
    unittest.main()
