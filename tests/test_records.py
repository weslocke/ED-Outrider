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

    def test_dated_by_the_first_scan_and_never_lost_to_a_nav_beacon(self):
        """Review 2026-10-25: a return visit's AutoScan re-dated a years-old record today (marked 🏆 new), a nav beacon
        read replaced the body's own scan (which the records leave out) so it dropped from them, and the scan count
        said beacon reads were left out while counting them."""
        j = self.j
        body = dict(BodyID=1, BodyName="Sys A 1", StarSystem="Sys", SystemAddress=7, PlanetClass="Icy body", Landable=True,
                    SurfaceGravity=2.5 * G, Radius=1e6, DistanceFromArrivalLS=10)
        j.handle({"event": "FSDJump", "timestamp": "2023-05-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7, "StarPos": [3, 4, 0]})
        j.handle(dict(body, event="Scan", timestamp="2023-05-01T00:01:00Z", ScanType="Detailed"))
        j.handle({"event": "FSDJump", "timestamp": "2026-10-20T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7, "StarPos": [3, 4, 0]})
        j.handle(dict(body, event="Scan", timestamp="2026-10-20T00:01:00Z", ScanType="AutoScan"))
        j.handle(dict(body, event="Scan", timestamp="2026-10-20T00:02:00Z", ScanType="NavBeaconDetail"))
        j.handle(dict(body, event="Scan", timestamp="2026-10-20T00:02:00Z", ScanType="NavBeaconDetail", BodyID=2, BodyName="Sys A 2"))
        self.db.commit()
        out = ed_outrider.body_records(self.db)
        rec = {r["key"]: r for r in out["records"]}
        self.assertEqual((rec["high_g"]["body"], rec["high_g"]["ts"]), ("A 1", "2023-05-01T00:01:00Z"))
        self.assertEqual(rec["far_sol"]["ts"], "2023-05-01T00:00:00Z")   # your first jump there
        self.assertEqual(out["bodies"], 1)                               # A 2, a beacon read only: not counted


    def test_a_beacon_read_first_and_zero_figures(self):
        """In-depth review 2026-10-25: a body first read off a nav beacon was dated by that read; an airless body's 0
        held "Thickest atmosphere 0.0 atm", an arrival star's 0 "Farthest from its arrival star"; a thin one read 0.0."""
        j = self.j
        body = dict(BodyID=3, BodyName="Sys B 1", StarSystem="Sys", SystemAddress=7, PlanetClass="Rocky body", Landable=True,
                    SurfaceGravity=3.5 * G, Radius=1e6, DistanceFromArrivalLS=0, SurfacePressure=0.0)
        j.handle({"event": "FSDJump", "timestamp": "2024-05-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7, "StarPos": [3, 4, 0]})
        j.handle(dict(body, event="Scan", timestamp="2024-05-01T00:01:00Z", ScanType="NavBeaconDetail"))
        j.handle(dict(body, event="Scan", timestamp="2026-10-25T00:01:00Z", ScanType="Detailed"))
        self.db.commit()
        rec = {r["key"]: r for r in ed_outrider.body_records(self.db)["records"]}
        self.assertEqual(rec["high_g"]["ts"], "2026-10-25T00:01:00Z")   # your own scan, not the beacon's
        self.assertNotIn("pressure", rec)
        self.assertNotIn("far_out", rec)
        thin = R.records([(1, "S", "1", "t", scan("S 1", PlanetClass="Rocky body", SurfacePressure=500.0, Radius=1e6))])
        self.assertEqual({r["key"]: r["text"] for r in thin}["pressure"], "500.0 Pa")


    def test_review_3(self):
        """Third in-depth review 2026-10-25: a few Pa read "0.0000 atm"; a nav beacon read after your AutoScan stamped
        the record a beacon read over your raw scan."""
        thin = R.records([(1, "S", "1", "t", scan("S 1", PlanetClass="Rocky body", SurfacePressure=3.0, Radius=1e6))])
        self.assertEqual({r["key"]: r["text"] for r in thin}["pressure"], "3.0 Pa")
        star = dict(BodyID=0, BodyName="Sys", StarSystem="Sys", SystemAddress=7, StarType="G", Radius=7e8, SurfaceTemperature=5000.0)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-10-25T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7, "StarPos": [0, 0, 0]})
        self.j.handle(dict(star, event="Scan", timestamp="2026-10-25T00:00:05Z", ScanType="AutoScan"))
        self.j.handle(dict(star, event="Scan", timestamp="2026-10-25T00:05:00Z", ScanType="NavBeaconDetail"))
        rec = json.loads(self.db.execute("SELECT record FROM own_bodies WHERE system=7 AND body_id=0").fetchone()[0])
        self.assertEqual(rec["scan_type"], "AutoScan")


if __name__ == "__main__":
    unittest.main()
