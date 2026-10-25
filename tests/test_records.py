"""My firsts' Your records (the author, 2026-10-25): the most extreme bodies among your own scans, and the system
farthest from Sol (outrider/records.py, State.body_records, GET /api/records). Fakes only."""
import asyncio
import json
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.records as R  # noqa: E402

G = 9.80665


def scan(name, **kw):
    return dict({"event": "Scan", "ScanType": "Detailed", "BodyName": name}, **kw)


class Records(unittest.TestCase):
    def test_each_record_and_its_words(self):
        self.maxDiff = None
        bodies = [
            (1, "S", "A", "2026-01-01T00:00:00Z", scan("S A", StarType="O", SurfaceTemperature=40000, Radius=6.957e9, StellarMass=30)),
            (1, "S", "B", "2026-01-01T00:00:01Z", scan("S B", StarType="M", SurfaceTemperature=3000, Radius=3e8, StellarMass=0.4)),
            (1, "S", "1", "2026-01-01T00:00:02Z", scan("S 1", PlanetClass="Earthlike body", Landable=False, SurfaceGravity=1.5 * G,
                                                       SurfaceTemperature=290, Radius=7e6, MassEM=1.2, SurfacePressure=101325,
                                                       RotationPeriod=-86400, OrbitalPeriod=3e7, DistanceFromArrivalLS=500)),
            (2, "T", "2 a", "2026-01-02T00:00:00Z", scan("T 2 a", PlanetClass="Icy body", Landable=True, SurfaceGravity=0.02 * G,
                                                         SurfaceTemperature=20, Radius=1.5e5, MassEM=0.0001, RotationPeriod=3000,
                                                         OrbitalPeriod=7200, DistanceFromArrivalLS=250000)),
            (2, "T", "3", "2026-01-02T00:00:01Z", scan("T 3", PlanetClass="Sudarsky class I gas giant", SurfaceTemperature=100, SurfacePressure=1e13,
                                                       OrbitalPeriod=-3600,
                                                       Radius=7e7, MassEM=900, Rings=[{"Name": "T 3 A Ring", "InnerRad": 8e7, "OuterRad": 2e8},
                                                                                       {"Name": "T 3 A Belt", "InnerRad": 1e8, "OuterRad": 9e8}])),
            (2, "T", "4", "2026-01-02T00:00:02Z", scan("T 4", PlanetClass="High metal content body", Landable=True,
                                                       SurfaceGravity=4.2 * G, SurfaceTemperature=900, Radius=6e6, MassEM=7)),
            (3, "U", "1", "2026-01-03T00:00:00Z", scan("U 1", ScanType="NavBeaconDetail", PlanetClass="Icy body", Radius=10)),
        ]
        jumps = [(1, "S", 100.0, 0.0, 0.0, "2026-01-01T00:00:00Z"), (2, "T", 0.0, 0.0, 22000.0, "2026-01-02T00:00:00Z"),
                 (9, "Ride", None, None, None, "2026-01-02T00:00:00Z")]
        got = {r["key"]: (r["body"], r["system"], r["text"]) for r in R.records(bodies, jumps)}
        self.assertEqual(got, {
            "hot_star": ("A", "S", "40,000 K"), "big_star": ("A", "S", "10.0 solar radii"),
            "heavy_star": ("A", "S", "30.00 solar masses"), "hot_planet": ("4", "T", "900 K"), "cold_planet": ("2 a", "T", "20 K"),
            "big_planet": ("3", "T", "70,000 km"), "small_body": ("2 a", "T", "150 km"),   # the nav beacon's 10 m: not yours
            "heavy_planet": ("3", "T", "900.0 Earth masses"), "high_g": ("4", "T", "4.20 g"), "low_g": ("2 a", "T", "0.020 g"),
            "elw_g": ("1", "S", "1.50 g"), "pressure": ("1", "S", "1.0 atm"),   # the gas giant's 1e13 Pa: no surface
            "spin": ("2 a", "T", "50.0 min"),
            "orbit": ("3", "T", "1.0 h"),   # retrograde (-3600 s): its length counts
            "far_out": ("2 a", "T", "250,000 ls"), "wide_ring": ("3", "T", "120,000 km"),
            "far_sol": (None, "T", "22,000 ly")})
        self.assertEqual(R.records([], []), [])


class Server(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, type("S", (), {"cached": lambda self, i: (None, None)})(), 25)

    def add(self, ts, body_id, name, **kw):
        ev = scan(f"Sys {name}", BodyID=body_id, StarSystem="Sys", SystemAddress=7, **kw)
        self.db.execute("INSERT INTO own_bodies (system, body_id, name, record, ts, raw) VALUES (7, ?, ?, '{}', ?, ?)",
                        (body_id, f"Sys {name}", ts, json.dumps(ev)))
        self.db.commit()

    def test_short_names_and_worked_out_again_only_on_change(self):
        self.db.execute("INSERT INTO jumps (ts, id64, name, x, y, z) VALUES ('2026-01-01T00:00:00Z', 7, 'Sys', 3, 4, 0)")
        self.add("2026-01-01T00:01:00Z", 1, "A 1", PlanetClass="Icy body", Landable=True, SurfaceGravity=0.5 * G)
        first = asyncio.run(self.state.body_records())
        rec = {r["key"]: r for r in first["records"]}
        self.assertEqual((rec["high_g"]["body"], rec["high_g"]["system"], rec["high_g"]["id64"]), ("A 1", "Sys", "7"))
        self.assertEqual((rec["far_sol"]["text"], first["bodies"]), ("5 ly", 1))
        self.assertIs(asyncio.run(self.state.body_records()), first)                 # nothing new: the same answer
        self.add("2026-01-01T00:02:00Z", 2, "A 2", PlanetClass="Rocky body", Landable=True, SurfaceGravity=2 * G)
        again = asyncio.run(self.state.body_records())
        self.assertEqual({r["key"]: r["body"] for r in again["records"]}["high_g"], "A 2")


if __name__ == "__main__":
    unittest.main()
