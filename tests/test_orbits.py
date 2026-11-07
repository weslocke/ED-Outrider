"""Unit tests: where a system's bodies are (outrider/orbits.py), checked against the game's own navigation panel, and the
server's places for the suggested order (State.leaving_summary's pos, approx, arrival and at_body).

The fixtures (tests/fixtures/orbit_readings.json) are the scans of four systems the author read the panel in on
2026-11-07, each reading at its own time: a single star (within 1%), moons (within 1%), a binary (the frame rule) and
a planet pair's family orbiting the root (within 2%). The readings were taken a few ls off the body at times, which is
part of the tolerance.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import json
import math
import os
import time
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.orbits as orbits  # noqa: E402
from outrider.core import ts_seconds  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "orbit_readings.json")


def readings():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def split(lines):
    return [x for x in lines if x["event"] == "Scan"], [x for x in lines if x["event"] == "ScanBaryCentre"]


class Kepler(unittest.TestCase):
    def test_solves_the_equation(self):
        for e in (0.0, 0.1, 0.5, 0.79, 0.85, 0.95):
            for m in (0.0, 0.3, 1.0, math.pi - 0.01, 3.5, 6.0, -2.0):
                E = orbits.kepler(m, e)
                self.assertAlmostEqual(E - e * math.sin(E), math.fmod(m, 2 * math.pi), places=10, msg=(m, e))
        self.assertEqual(orbits.kepler(1.2, 0.0), 1.2)              # a circle: E is M

    def test_offset_on_the_orbit(self):
        el = {"SemiMajorAxis": orbits.C * 100, "Eccentricity": 0.2, "MeanAnomaly": 0.0, "OrbitalPeriod": 1000.0,
              "timestamp": "2026-01-01T00:00:00Z"}
        t0 = ts_seconds(el["timestamp"])
        self.assertAlmostEqual(math.dist(orbits.offset(el, t0), (0, 0, 0)), 80.0)          # periapsis: a(1 - e)
        self.assertAlmostEqual(math.dist(orbits.offset(el, t0 + 500), (0, 0, 0)), 120.0)   # half a period on: apoapsis
        self.assertAlmostEqual(orbits.offset(el, t0 + 1000)[0], 80.0)                      # round again
        # the mirrored convention: a quarter period on, the body is on the -y side (the textbook's would be +y)
        self.assertLess(orbits.offset(dict(el, Eccentricity=0.0), t0 + 250)[1], -99.9)
        self.assertIsNone(orbits.offset({"SemiMajorAxis": 1e9}, t0))                       # no MeanAnomaly (old journals)
        self.assertIsNone(orbits.offset({}, t0))

    def test_turn_is_a_rotation(self):
        r = orbits.turn({"AscendingNode": 40.0, "OrbitalInclination": 86.0, "Periapsis": 200.0})
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(sum(r[i][k] * r[j][k] for k in range(3)), 1.0 if i == j else 0.0)
        self.assertEqual(orbits.turn({}), ((1, -0.0, 0.0), (0.0, 1, -0.0), (0.0, 0.0, 1)))


class NavigationPanel(unittest.TestCase):
    """The distances the game's navigation panel showed, against the positions worked out at the reading's time."""

    def test_the_four_systems(self):
        fx = readings()
        self.assertEqual(sorted(fx), ["Smojooe WK-G b24-4", "Smojooe YC-D c12-0", "Smojooe YC-D c12-3", "Smojooe ZC-D c12-27"])
        for name, f in fx.items():
            scans, bary = split(f["lines"])
            ids = {s["BodyName"][len(name):].strip(): s["BodyID"] for s in scans}
            for r in f["readings"]:
                pos, approx = orbits.positions(scans, bary, ts_seconds(r["at"]))
                here = pos[ids[r["from"]]]
                for body, want in r["panel"].items():
                    got = orbits.distance(here, pos[ids[body]])
                    with self.subTest(system=name, frm=r["from"], to=body or "the star"):
                        self.assertLess(abs(got - want) / want, f["tolerance"], f"game {want} ls, worked out {got:.2f}")
                self.assertEqual(approx, set(), name)   # root-level layouts: nothing approximate

    @staticmethod
    def system(name):
        f = readings()[name]
        scans, bary = split(f["lines"])
        return f, scans, bary, {s["BodyName"][len(name):].strip(): s["BodyID"] for s in scans}

    def test_the_moons_need_the_mirror(self):
        """WK-G b24-4's moons from 5 e: the textbook convention (M advanced and not negated) puts 5 d 1.6 ls away, the
        panel said 9.50 (research note, 2026-11-07); the mirrored one gets it."""
        f, scans, bary, ids = self.system("Smojooe WK-G b24-4")
        at = ts_seconds(f["readings"][0]["at"])
        d = lambda pos: orbits.distance(pos[ids["5 e"]], pos[ids["5 d"]])
        self.assertAlmostEqual(d(orbits.positions(scans, bary, at)[0]), 9.50, delta=0.05)
        # the textbook: E from +M (M and the period negated, so the mirror undoes them)
        tb = lambda xs: [dict(x, MeanAnomaly=-x["MeanAnomaly"], OrbitalPeriod=-x["OrbitalPeriod"]) if "MeanAnomaly" in x else x for x in xs]
        self.assertAlmostEqual(d(orbits.positions(tb(scans), tb(bary), at)[0]), 1.63, delta=0.05)

    def test_frame_rule_matters_in_the_binary(self):
        """YC-D c12-0 from A 2: B's family within 0.1% with each star's children turned by its orbit; as plain bodies
        (no turn) up to 2% off."""
        f, scans, bary, ids = self.system("Smojooe YC-D c12-0")
        r = f["readings"][1]
        self.assertEqual(r["from"], "A 2")
        plain = [{k: v for k, v in x.items() if k != "StarType"} if x["BodyID"] in (ids["A"], ids["B"]) else x for x in scans]
        at = ts_seconds(r["at"])
        err = lambda pos, b: abs(orbits.distance(pos[ids["A 2"]], pos[ids[b]]) - r["panel"][b]) / r["panel"][b]
        turned, unturned = orbits.positions(scans, bary, at)[0], orbits.positions(plain, bary, at)[0]
        fam = [b for b in r["panel"] if b.startswith("B")]
        self.assertEqual(len(fam), 7)
        self.assertLess(max(err(turned, b) for b in fam), 0.001)
        self.assertGreater(max(err(unturned, b) for b in fam), 0.015)


class Approximate(unittest.TestCase):
    STAR = {"event": "Scan", "timestamp": "2026-11-07T00:00:00Z", "BodyName": "S A", "BodyID": 1, "Parents": [{"Null": 0}],
            "StarType": "K", "SemiMajorAxis": orbits.C * 50, "Eccentricity": 0.0, "OrbitalInclination": 0.0, "Periapsis": 0.0,
            "AscendingNode": 0.0, "MeanAnomaly": 0.0, "OrbitalPeriod": 1e9}

    def planet(self, bid, parents, a_ls, **kw):
        return dict({"event": "Scan", "timestamp": "2026-11-07T00:00:00Z", "BodyName": f"S {bid}", "BodyID": bid, "Parents": parents,
                     "PlanetClass": "Icy body", "SemiMajorAxis": orbits.C * a_ls, "Eccentricity": 0.0, "OrbitalInclination": 0.0,
                     "Periapsis": 0.0, "AscendingNode": 0.0, "MeanAnomaly": 0.0, "OrbitalPeriod": 1e9}, **kw)

    def test_a_barycentre_with_no_scan(self):
        """A planet pair's barycentre 5 (round star A) has no ScanBaryCentre: its members are placed at A, never at the
        origin, and marked approximate; A's other planet is exact."""
        at = ts_seconds("2026-11-07T00:00:00Z")
        scans = [self.STAR, self.planet(6, [{"Null": 5}, {"Star": 1}, {"Null": 0}], 2.0),
                 self.planet(7, [{"Null": 5}, {"Star": 1}, {"Null": 0}], 3.0), self.planet(8, [{"Star": 1}, {"Null": 0}], 400.0)]
        pos, approx = orbits.positions(scans, [], at)
        self.assertEqual(approx, {6, 7})
        self.assertAlmostEqual(math.dist(pos[6], pos[1]), 2.0, places=6)    # at A (plus its own small orbit)
        self.assertAlmostEqual(math.dist(pos[1], (0, 0, 0)), 50.0, places=6)
        self.assertAlmostEqual(math.dist(pos[8], pos[1]), 400.0, places=6)
        # with the barycentre's scan: placed on its orbit, exact
        b = {"event": "ScanBaryCentre", "timestamp": "2026-11-07T00:00:00Z", "BodyID": 5, "SemiMajorAxis": orbits.C * 900,
             "Eccentricity": 0.0, "OrbitalInclination": 0.0, "Periapsis": 0.0, "AscendingNode": 0.0, "MeanAnomaly": 0.0,
             "OrbitalPeriod": 1e9}
        pos, approx = orbits.positions(scans, [b], at)
        self.assertEqual(approx, set())
        self.assertAlmostEqual(math.dist(pos[6], pos[1]), 902.0, places=4)

    def test_a_stellar_barycentre_not_the_root(self):
        """A pair of stars (barycentre 2) orbiting the root barycentre 0 with a third star: the pair's families are
        approximate (up to ~14% across families in game); the third star's are not."""
        at = ts_seconds("2026-11-07T00:00:00Z")
        star = lambda bid, parents, a: dict(self.STAR, BodyID=bid, BodyName=f"S {bid}", Parents=parents, SemiMajorAxis=orbits.C * a)
        scans = [star(1, [{"Null": 2}, {"Null": 0}], 10), star(3, [{"Null": 2}, {"Null": 0}], 12), star(4, [{"Null": 0}], 5000),
                 self.planet(5, [{"Star": 1}, {"Null": 2}, {"Null": 0}], 100), self.planet(6, [{"Star": 4}, {"Null": 0}], 100),
                 self.planet(7, [{"Null": 2}, {"Null": 0}], 300)]
        bary = {2: {"SemiMajorAxis": orbits.C * 4000, "MeanAnomaly": 10.0, "OrbitalPeriod": 1e9, "timestamp": "2026-11-07T00:00:00Z"}}
        _, approx = orbits.positions(scans, bary, at)
        self.assertEqual(approx, {1, 3, 5, 7})

    def test_no_orbit_no_position(self):
        """An old scan without MeanAnomaly has no position (the order falls back to its distance from the arrival star);
        a lone star with no orbit is the origin."""
        at = ts_seconds("2026-11-07T00:00:00Z")
        old = self.planet(2, [{"Star": 0}], 100.0)
        del old["MeanAnomaly"]
        pos, approx = orbits.positions([{"event": "Scan", "BodyID": 0, "BodyName": "S", "StarType": "G"}, old], [], at)
        self.assertEqual((pos, approx), ({0: (0.0, 0.0, 0.0)}, set()))


class ServerPlaces(unittest.TestCase):
    """leaving_summary: every item's pos (to 0.1 ls) and approx, the arrival star's place, and at_body: the body you are at
    or were last at in the system you are in this visit."""
    NAME = "Smojooe YC-D c12-0"

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        f = readings()[self.NAME]
        self.lines = f["lines"]
        self.id64 = self.lines[0]["SystemAddress"]
        self.j.handle({"event": "FSDJump", "timestamp": "2026-11-07T03:00:00Z", "StarSystem": self.NAME,
                       "SystemAddress": self.id64, "StarPos": [0, 0, 0]})
        for line in self.lines:
            self.j.handle(line)
        self.db.commit()

    def test_items_carry_their_place(self):
        before = time.time()
        l = self.state.leaving_summary(self.id64)
        scans, bary = split(self.lines)
        want, _ = orbits.positions(scans, bary, before)
        ids = {s["BodyName"][len(self.NAME):].strip(): s["BodyID"] for s in scans}
        items = l["unmapped"] + l["bio_pending"]
        self.assertTrue(items)
        for it in items:
            self.assertEqual(len(it["pos"]), 3)
            self.assertLess(math.dist(it["pos"], want[ids[it["body"]]]), 0.2, it["body"])   # to 0.1 ls (and a moment later)
            self.assertIs(it["approx"], False)
        self.assertEqual(l["arrival"]["body"], "A")
        self.assertEqual(l["arrival"]["dist_ls"], 0)
        self.assertLess(math.dist(l["arrival"]["pos"], want[ids["A"]]), 0.2)
        self.assertIsNone(l["at_body"])                                   # no body yet: the order starts at the star
        self.assertNotIn("_places", l)

    def test_at_body_is_the_last_body_this_visit(self):
        approach = lambda ts, name, bid: {"event": "ApproachBody", "timestamp": ts, "StarSystem": self.NAME,
                                          "SystemAddress": self.id64, "Body": f"{self.NAME} {name}", "BodyID": bid}
        a2 = next(x["BodyID"] for x in self.lines if x.get("BodyName") == f"{self.NAME} A 2")
        self.j.handle(approach("2026-11-07T03:10:00Z", "A 2", a2))
        at = self.state.leaving_summary(self.id64)["at_body"]
        self.assertEqual((at["body"], at["approx"], len(at["pos"])), ("A 2", False, 3))
        self.j.handle({"event": "LeaveBody", "timestamp": "2026-11-07T03:20:00Z", "StarSystem": self.NAME,
                       "SystemAddress": self.id64, "Body": f"{self.NAME} A 2", "BodyID": a2})
        self.assertEqual(self.state.leaving_summary(self.id64)["at_body"]["body"], "A 2")   # left it: still where you were
        self.j.handle({"event": "SupercruiseExit", "timestamp": "2026-11-07T03:30:00Z", "StarSystem": self.NAME,
                       "SystemAddress": self.id64, "Body": f"{self.NAME} B", "BodyID": 2, "BodyType": "Star"})
        self.assertEqual(self.state.leaving_summary(self.id64)["at_body"]["body"], "B")    # a star you dropped at
        self.j.handle({"event": "FSDJump", "timestamp": "2026-11-07T04:00:00Z", "StarSystem": "Elsewhere", "SystemAddress": 99,
                       "StarPos": [1, 0, 0]})
        self.assertIsNone(self.state.leaving_summary(self.id64)["at_body"])                # another system
        self.j.handle({"event": "FSDJump", "timestamp": "2026-11-07T04:10:00Z", "StarSystem": self.NAME,
                       "SystemAddress": self.id64, "StarPos": [0, 0, 0]})
        self.assertIsNone(self.state.leaving_summary(self.id64)["at_body"])                # back: a new visit, no body yet
        self.assertIn("'body_last'", ed_outrider.RESET_JOURNAL_DATA)                       # rebuilt by a re-read


if __name__ == "__main__":
    unittest.main()
