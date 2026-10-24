"""Unit tests: Journal reading, the tick, server state, moments and call-outs.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import sys
import time
import unittest
import unittest.mock
import sqlite3

from support import (  # also puts the repository root on sys.path
    BIO_M_SYSTEM, CANDS, death, guard_status, make_controls, org, outrider_honk, sale, scan, voice_honk, voice_jump,
    voice_moments, voice_organic, voice_planet, voice_sampling_body,
)
import outrider.bio  # noqa: E402
import outrider.materials  # noqa: E402
import outrider.log  # noqa: E402
import ed_outrider  # noqa: E402
import outrider.unsold  # noqa: E402


class FreshInstall(unittest.TestCase):
    """Batch 0: a brand-new database must accept every event the parser handles."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)

    def test_first_scan_on_fresh_database(self):
        ev = scan("2026-01-01T00:00:00Z", "Sys", 7, 1, "Sys 1")[2]
        self.j.handle(ev)
        raw = self.db.execute("SELECT raw FROM own_bodies WHERE system=7").fetchone()["raw"]
        self.assertIn('"BodyName": "Sys 1"', raw)

    def test_barycentre_stored(self):
        self.j.handle({"event": "ScanBaryCentre", "timestamp": "2026-01-01T00:00:00Z", "SystemAddress": 7,
                       "BodyID": 3, "SemiMajorAxis": 1.5e10, "Eccentricity": 0.1})
        row = self.db.execute("SELECT record FROM own_barycentres WHERE system=7 AND body_id=3").fetchone()
        self.assertIn("SemiMajorAxis", row["record"])

    def test_commander_credits_and_sales(self):
        self.j.handle({"event": "Commander", "timestamp": "2026-01-01T00:00:00Z", "Name": "Jameson", "FID": "F1"})
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:01Z", "Commander": "Jameson",
                       "Credits": 1000, "Loan": 0})
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": "2026-01-01T01:00:00Z", "TotalEarnings": 500,
                       "Discovered": []})
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T02:00:00Z",
                       "BioData": [{"Value": 100, "Bonus": 400}]})
        c = self.j.commander
        self.assertEqual((c["name"], c["credits"], c["earned"]), ("Jameson", 1000, 1000))
        # a new login resets the baseline; an older one read later is ignored
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T00:00:00Z", "Commander": "Jameson", "Credits": 3000})
        self.j.handle({"event": "LoadGame", "timestamp": "2025-12-01T00:00:00Z", "Commander": "Jameson", "Credits": 1})
        self.assertEqual((self.j.commander["credits"], self.j.commander["earned"]), (3000, 0))


class LatestPickup(unittest.TestCase):
    """Batch 0.2: data is judged by your latest scan, maps separately; lost data is recoverable."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        import types
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def ev(self, ts, **kw):
        self.j.handle(dict(kw, timestamp=ts))

    def body(self):
        self.db.commit()
        return next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == "5")

    def lose_ship(self, ts):
        self.ev(ts, event="Died"); self.ev(ts, event="Resurrect", Option="rebuy")

    def test_already_discovered_body_rescanned_after_loss_counts(self):
        self.j.handle(scan("2026-01-01T00:01:00Z", "Sys", 1, 5, "Sys 5", disc=True)[2])
        self.lose_ship("2026-01-02T00:00:00Z")
        self.assertEqual(self.body()["value_parts"]["scan_state"], "lost")
        self.j.handle(scan("2026-01-03T00:01:00Z", "Sys", 1, 5, "Sys 5", disc=True)[2])
        b = self.body()
        self.assertEqual(b["value_parts"]["scan_state"], "unsold")
        self.assertGreater(b["value_now"], 0)

    def test_map_lost_with_ship_is_not_counted_until_remapped(self):
        self.j.handle(scan("2026-01-01T00:01:00Z", "Sys", 1, 5, "Sys 5")[2])
        self.ev("2026-01-01T00:02:00Z", event="SAAScanComplete", SystemAddress=1, BodyID=5, BodyName="Sys 5")
        mapped_now = self.body()["value_now"]
        self.lose_ship("2026-01-02T00:00:00Z")
        self.j.handle(scan("2026-01-03T00:01:00Z", "Sys", 1, 5, "Sys 5")[2])     # rescanned, not remapped
        b = self.body()
        self.assertFalse(b["mapped"]); self.assertFalse(b["first_mapped"])
        self.assertEqual(b["map_state"], "lost")
        self.assertLess(b["value_now"], mapped_now)                  # the scan only
        self.assertEqual(b["value_now"] + b["value_parts"]["carto_left"], mapped_now)   # the map is still there to redo
        self.ev("2026-01-03T00:02:00Z", event="SAAScanComplete", SystemAddress=1, BodyID=5, BodyName="Sys 5")
        self.assertEqual(self.body()["value_now"], mapped_now)

    def test_lost_scan_not_rescanned_is_recoverable_in_max(self):
        self.j.handle(scan("2026-01-01T00:01:00Z", "Sys", 1, 5, "Sys 5")[2])
        full = self.body()["value_max"]
        self.lose_ship("2026-01-02T00:00:00Z")
        b = self.body()
        self.assertEqual(b["value_now"], 0)
        self.assertEqual(b["value_max"], full)     # scan and map it again: the same credits are there

    def test_sold_data_is_done(self):
        self.j.handle(scan("2026-01-01T00:01:00Z", "Sys", 1, 5, "Sys 5")[2])
        self.ev("2026-01-01T00:02:00Z", event="SAAScanComplete", SystemAddress=1, BodyID=5, BodyName="Sys 5")
        self.j.handle(sale("2026-01-02T00:00:00Z", ["Sys"])[2])
        b = self.body()
        self.assertEqual((b["value_now"], b["value_max"]), (0, 0))
        self.assertTrue(b["mapped"])


class TickSafety(unittest.TestCase):
    """Batch 0.3: a bad file or a failed tick never loses or double-counts journal events."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)

    def write(self, name, events):
        import json as _j
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            for e in events:
                f.write(_j.dumps(e, separators=(",", ":")) + "\n")
        return path

    def jump(self, ts, id64, x):
        return {"timestamp": ts, "event": "FSDJump", "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0],
                "JumpDist": 10.0, "FuelUsed": 1.0}

    def tick(self):
        """What watch() does: scan, commit; on an exception roll back and reload."""
        try:
            self.j.scan_dir(self.dir)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            self.j.reload()
            return False

    def test_unreadable_file_is_skipped_not_fatal(self):
        import contextlib, io
        self.write("Journal.2026-01-01T000000.01.log", [self.jump("2026-01-01T00:00:00Z", 1, 0)])
        bad = self.write("Journal.2026-01-02T000000.01.log", [self.jump("2026-01-02T00:00:00Z", 2, 10)])
        self.write("Journal.2026-01-03T000000.01.log", [self.jump("2026-01-03T00:00:00Z", 3, 20)])
        os.chmod(bad, 0)
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertTrue(self.tick())
                self.tick()
            self.assertEqual(self.j.pos["id64"], 3)          # the newer file was still read
            self.assertEqual(err.getvalue().count("journal skipped"), 1)   # reported once, not every tick
        finally:
            os.chmod(bad, 0o644)
        self.tick()
        self.assertEqual({r[0] for r in self.db.execute("SELECT id64 FROM visits")}, {1, 2, 3})

    def test_failed_tick_is_retried_exactly(self):
        self.write("Journal.2026-01-01T000000.01.log", [
            self.jump("2026-01-01T00:00:00Z", 1, 0),
            {"timestamp": "2026-01-01T00:01:00Z", "event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3},
            {"timestamp": "2026-01-01T00:02:00Z", "event": "LoadGame", "Commander": "J", "Credits": 100}])
        self.write("Journal.2026-01-02T000000.01.log", [
            {"timestamp": "2026-01-02T00:00:00Z", "event": "MultiSellExplorationData", "TotalEarnings": 50, "Discovered": []},
            self.jump("2026-01-02T00:01:00Z", 2, 10)])
        calls = {"n": 0}
        # the first file's events land, then a database error in the second file fails the tick once
        orig_handle = self.j.handle
        def flaky(ev):
            if ev.get("event") == "FSDJump" and ev.get("SystemAddress") == 2 and not calls["n"]:
                calls["n"] += 1
                raise sqlite3.OperationalError("database is locked")
            return orig_handle(ev)
        self.j.handle = flaky
        self.assertFalse(self.tick())
        self.assertTrue(self.tick())
        self.assertEqual({r[0] for r in self.db.execute("SELECT id64 FROM visits")}, {1, 2})   # nothing lost
        self.assertEqual(self.j.materials["counts"].get("iron"), 3)                             # nothing doubled
        self.assertEqual(self.j.fuel_hist, [[10.0, 1.0, None, None]] * 2)                     # one per jump
        self.assertEqual(self.j.commander["earned"], 50)


class LogTailRace(unittest.TestCase):
    def test_line_written_during_the_scan_is_not_lost(self):
        import tempfile, json as _j
        d = tempfile.mkdtemp(); now = dt.datetime.now(dt.timezone.utc)
        p = os.path.join(d, now.strftime("Journal.%Y-%m-%dT%H%M%S.01.log"))
        line = lambda n: _j.dumps({"timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "event": "FSDJump", "StarSystem": n}) + "\n"
        with open(p, "w") as f:
            f.write(line("S0"))
        first = outrider.log.read_log([d], days=1)
        real = outrider.log._load
        calls = []
        def racing(path):
            e = real(path)
            if not calls:
                calls.append(1)
                with open(p, "a") as f:
                    f.write(line("S1"))
            return e
        with unittest.mock.patch.object(outrider.log, "_load", racing):
            t1 = outrider.log.read_log([d], after=first["newest"])
        t2 = outrider.log.read_log([d], after=t1["newest"])
        self.assertEqual([r["system"] for r in t1["rows"] + t2["rows"]], ["S1"])


class QuickScan(unittest.TestCase):
    """S18: the tick's scan of a journal folder over a network share stats only the files still changing and the newest
    two; every file once a minute."""

    def setUp(self):
        import shutil
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = 1000.0
        self.j.clock = lambda: self.now
        self.paths = [self.write(n, "A") for n in range(1, 6)]

    def write(self, n, system, end="\n"):
        p = os.path.join(self.dir, f"Journal.2026-01-0{n}T000000.01.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": f"2026-01-0{n}T00:00:00Z", "event": "FSDJump", "StarSystem": system,
                                "SystemAddress": n, "StarPos": [n, 0, 0]}) + end)
        return p

    def scan(self, step=1):
        """One quick scan `step` seconds after the last: the paths it stat'd."""
        self.now += step
        seen, real = [], os.path.getsize
        with unittest.mock.patch("os.path.getsize", lambda p: seen.append(p) or real(p)):
            self.j.scan_dir(self.dir, quick=True)
        return seen

    def test_settled_files_wait_for_the_full_check(self):
        self.assertEqual(self.scan(), self.paths)                        # the first scan stats every file
        for _ in range(ed_outrider.JOURNAL_SETTLE_STATS):
            self.scan()
        self.assertEqual(self.j.settled, set(self.paths))
        self.assertEqual(self.scan(), self.paths[-2:])                   # settled: only the newest two
        new = self.write(7, "B")                                         # a new journal is listed and read at once
        self.assertEqual(self.scan(), self.paths[-1:] + [new])
        self.assertEqual(self.j.offsets[new], os.path.getsize(new))
        self.write(1, "C")                                               # a sync tool adds to an old one: not yet...
        self.assertNotIn(self.paths[0], self.scan())
        self.assertEqual(self.scan(ed_outrider.JOURNAL_FULL_CHECK_S), self.paths + [new])   # ...but within the minute
        self.assertEqual(self.j.offsets[self.paths[0]], os.path.getsize(self.paths[0]))
        self.assertNotIn(self.paths[0], self.j.settled)                  # it changed: settles again from scratch

    def test_a_file_cut_short_settles_and_a_bad_one_never(self):
        cut = self.write(2, "Half", end="")                              # its last line never finished
        real = self.j.read_file

        def read(path):
            if path == self.paths[2]:
                raise PermissionError(13, "Permission denied")
            return real(path)
        with unittest.mock.patch.object(self.j, "read_file", read), \
                unittest.mock.patch("sys.stderr", io.StringIO()):
            for _ in range(ed_outrider.JOURNAL_SETTLE_STATS + 1):
                self.scan()
            self.assertLess(self.j.offsets[cut], os.path.getsize(cut))      # size never reaches the offset...
            self.assertIn(cut, self.j.settled)                               # ...but it stopped changing
            self.assertNotIn(self.paths[2], self.j.settled)                  # unreadable: tried every time
            self.assertIn(self.paths[2], self.scan())

    def test_reload_forgets_what_settled(self):
        for _ in range(ed_outrider.JOURNAL_SETTLE_STATS + 1):
            self.scan()
        self.assertTrue(self.j.settled)
        self.j.reload()                                                   # a rolled-back tick: offsets went back
        self.assertEqual(self.j.settled, set())
        self.assertEqual(self.scan(), self.paths)

    def test_the_tick_scans_quick(self):
        import types
        state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        calls = []
        later = ("watch_status", "maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold",
                 "maybe_sale_left", "maybe_curious", "maybe_locate_carrier", "maybe_find_sellers", "maybe_backup_on_quit",
                 "highway_copy_next", "riches_copy_next", "highway_heavy_check", "maybe_autotarget",
                 "maybe_boxel_autotarget")
        with contextlib.ExitStack() as stack:
            for name in later:
                stack.enter_context(unittest.mock.patch.object(state, name, lambda *a: None))
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir]))
            stack.enter_context(unittest.mock.patch.object(self.j, "scan_dir", lambda d, **kw: calls.append(kw) and 0))
            state.tick({})
        self.assertIsNone(state.tail_error)
        self.assertEqual(calls, [{"upload": "live", "quick": True}])


class NamedBodyPanel(unittest.TestCase):
    def test_named_body_finds_its_scan(self):
        import asyncio, types
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sol", "SystemAddress": 10,
                  "StarPos": [0, 0, 0]})
        ev = scan("2026-01-01T00:01:00Z", "Sol", 10, 3, "Earth")[2]
        j.handle(ev)
        db.commit()
        async def lookup(id64, interactive=True):
            return None
        state = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None), lookup=lookup), 25)
        d = asyncio.run(state.body_detail(10, "Earth"))
        self.assertEqual(d["full_name"], "Earth")          # not the fabricated "Sol Earth"
        self.assertIsNotNone(d["own"])                      # your raw scan was found


class Batch1Server(unittest.TestCase):
    """Batch 1: hull, danger moments, sales, finds and the priced leaving summary."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def test_hull_only_counts_your_ship(self):
        # the game's line shapes: the ship's carry "Fighter": false; a fighter's says PlayerPilot false or Fighter true
        self.j.handle({"event": "HullDamage", "timestamp": "2026-01-01T00:01:00Z", "Health": 0.48, "PlayerPilot": True, "Fighter": False})
        self.assertEqual(self.j.hull["pct"], 48)
        self.j.handle({"event": "HullDamage", "timestamp": "2026-01-01T00:02:00Z", "Health": 0.1, "PlayerPilot": True, "Fighter": True})
        self.j.handle({"event": "HullDamage", "timestamp": "2026-01-01T00:02:00Z", "Health": 0.2, "PlayerPilot": False})
        self.assertEqual(self.j.hull["pct"], 48)                       # a fighter is not the ship
        self.j.handle({"event": "RepairAll", "timestamp": "2026-01-01T00:03:00Z", "Cost": 100})
        self.assertEqual(self.j.hull["pct"], 100)

    def test_sales_merge_into_one(self):
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": "2026-01-01T01:00:00Z", "TotalEarnings": 5000,
                       "Discovered": [{"SystemName": "Sys", "NumBodies": 3}]})
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T01:04:00Z", "BioData": [{"Value": 100, "Bonus": 400}]})
        self.assertEqual(self.j.last_sale["carto"], 5000)
        self.assertEqual(self.j.last_sale["bio"], 500)                  # same visit: one sale
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-02T01:00:00Z", "BioData": [{"Value": 7, "Bonus": 0}]})
        self.assertEqual((self.j.last_sale["carto"], self.j.last_sale["bio"]), (0, 7))

    def test_moments_priced(self):
        ev = scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4")[2]
        ev.update(PlanetClass="Water world", MassEM=0.5, TerraformState="Terraformable")
        self.j.handle(ev)
        self.j.handle({"event": "HeatDamage", "timestamp": "2026-01-01T00:06:00Z"})
        self.db.commit()
        m = self.state.moments_summary()
        scanm = next(x for x in m if x["kind"] == "scan")
        self.assertEqual((scanm["body"], scanm["terraformable"]), ("4", True))
        self.assertGreater(scanm["base_value"], 500000)
        self.assertTrue(any(x["kind"] == "heat" for x in m))
        self.assertEqual(m[-1]["seq"], self.j.moment_seq)

    def test_leaving_lists_increments(self):
        ev = scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4", disc=True)[2]
        ev.update(PlanetClass="Sudarsky class II gas giant", MassEM=300)
        self.j.handle(ev)
        self.db.commit()
        l = self.state.leaving_summary(1)
        self.assertEqual(l["id64"], "1")   # S30: the system it is about (the first stop you picked applies there only)
        u = l["unmapped"][0]
        self.assertEqual(u["body"], "4")
        self.assertFalse(u["special"])
        self.assertGreater(u["increment"], 0)
        # the Next lines' totals (Q5): mapped, without and with your bonuses; discovered by someone else, so the
        # first-mapped bonus alone separates them, and the plain total is more than what mapping adds
        self.assertGreater(u["value_mapped"], u["increment"])
        self.assertGreater(u["value_mapped_bonus"], u["value_mapped"])
        ev = scan("2026-01-01T00:06:00Z", "Sys", 1, 5, "Sys 5", disc=True)[2]
        ev.update(PlanetClass="Sudarsky class II gas giant", MassEM=300, WasMapped=True)   # no bonus of yours: equal
        self.j.handle(ev)
        self.db.commit()
        u5 = next(x for x in self.state.leaving_summary(1)["unmapped"] if x["body"] == "5")
        self.assertEqual(u5["value_mapped_bonus"], u5["value_mapped"])

    def test_leaving_summary_cached_until_its_data_changes(self):   # S17
        """The payload asks for the target's leaving summary on every poll: worked out once until the journal writes
        something it reads (data_seq: scans, deaths, sales), the system's place changes, the bio rules are updated or a
        tick is rolled back; each caller gets its own copy."""
        ev = scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4", disc=True)[2]
        ev.update(PlanetClass="Sudarsky class II gas giant", MassEM=300)
        self.j.handle(ev)
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:06:00Z", "SystemAddress": 1, "BodyID": 4,
                       "BodyName": "Sys 4", "ProbesUsed": 5, "EfficiencyTarget": 6})
        self.db.commit()
        calls, real = [], ed_outrider.bio_context
        unmapped = lambda: [u["body"] for u in self.state.leaving_summary(1)["unmapped"]]
        with unittest.mock.patch.object(ed_outrider, "bio_context", lambda *a, **k: calls.append(1) or real(*a, **k)):
            first = self.state.leaving_summary(1)
            self.assertEqual(first["unmapped"], [])                     # mapped
            first["unmapped"].append("changed by its caller")         # system_detail adds to its copy
            self.assertEqual(unmapped(), [])
            self.assertEqual(len(calls), 1)                             # worked out once
            for _, _, e in death("2026-01-01T00:07:00Z"):             # the map died with the ship: to do again
                self.j.handle(e)
            self.assertEqual(unmapped(), ["4"])
            self.assertEqual(len(calls), 2)
            self.j.handle(sale("2026-01-01T00:08:00Z", ["Sys"])[2])  # a sale (no dirty system) moves it too
            unmapped()
            self.assertEqual(len(calls), 3)
            self.j.handle(scan("2026-01-01T00:09:00Z", "Sys", 1, 5, "Sys 5")[2])
            self.assertEqual(self.state.leaving_summary(1)["scanned"], 2)
            self.assertEqual(len(calls), 4)
            self.state.bio_rules_gen += 1                               # check_bio_rules installed new rules
            unmapped()
            self.assertEqual(len(calls), 5)
            self.state.bases[1] = ("spansh", {"name": "Sys", "x": 1.0, "y": 2.0, "z": 3.0})   # a new place: the region
            unmapped()
            self.assertEqual(len(calls), 6)
            self.j.reload()                                             # a rolled-back tick
            unmapped()
            self.assertEqual(len(calls), 7)
            unmapped()
            self.assertEqual(len(calls), 7)

    def test_updated_bio_rules_count_a_generation(self):   # S17: leaving_summary's cache key
        import asyncio
        with unittest.mock.patch.object(outrider.bio, "update_if_newer", lambda log=print: True), \
                unittest.mock.patch.object(outrider.bio, "rules_info", lambda: {"species": 1, "generated": ""}), \
                unittest.mock.patch("sys.stdout", io.StringIO()):
            asyncio.run(ed_outrider.check_bio_rules(self.state))
            self.assertEqual(self.state.bio_rules_gen, 1)
            with unittest.mock.patch.object(outrider.bio, "update_if_newer", lambda log=print: False):
                asyncio.run(ed_outrider.check_bio_rules(self.state))   # up to date: the same rules
            self.assertEqual(self.state.bio_rules_gen, 1)

    def test_mapped_by_someone_else_is_flagged(self):
        """The author (2026-10-09): a body someone else mapped (WasMapped) is never pointed out. The leaving list and the
        scan's moment flag it (the page leaves it out, and says once per system that mapping still pays); the arrival
        briefing never picks it."""
        for bid, name, mapped in ((4, "Sys 4", False), (5, "Sys 5", True)):
            ev = scan(f"2026-01-01T00:0{bid}:00Z", "Sys", 1, bid, name, disc=True)[2]
            ev.update(PlanetClass="Sudarsky class II gas giant", MassEM=300, WasMapped=mapped)
            self.j.handle(ev)
        self.j.moment("scan", "2026-01-01T00:05:00Z", system=1, body_id=5)
        self.db.commit()
        flags = {u["body"]: u["mapped_before"] for u in self.state.leaving_summary(1)["unmapped"]}
        self.assertEqual(flags, {"4": False, "5": True})
        scanm = [x for x in self.state.moments_summary() if x["kind"] == "scan" and x["body"] == "5"][-1]
        self.assertTrue(scanm["mapped_before"])
        worth = [w["body"] for w in (self.state.arrival_facts(1) or {}).get("worth") or []]
        self.assertEqual(worth, ["4"])                          # the one nobody mapped; not 5


class Batch2Server(unittest.TestCase):
    """Batch 2: jet-cone boost, stellar phenomena, the on-body strip and the in-game destination."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def test_boost_until_the_next_jump(self):
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-01-01T00:01:00Z", "BoostValue": 3.0})
        self.assertEqual(self.state.payload()["boost"], 3.0)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:02:00Z", "StarSystem": "Two", "SystemAddress": 2,
                       "StarPos": [100, 0, 0], "BoostUsed": 4})
        self.assertIsNone(self.state.payload()["boost"])

    def test_phenomena_found_then_reached(self):
        self.j.handle({"event": "FSSSignalDiscovered", "timestamp": "2026-01-01T00:01:00Z", "SystemAddress": 1,
                       "SignalName": "$Fixed_Event_Life_Cloud;", "SignalType": "Codex"})
        self.j.handle({"event": "FSSSignalDiscovered", "timestamp": "2026-01-01T00:01:00Z", "SystemAddress": 1,
                       "SignalName": "$USS_Type_Salvage;"})                                  # ordinary signal: ignored
        rows = [dict(r) for r in self.db.execute("SELECT kind, reached_ts FROM phenomena")]
        self.assertEqual(rows, [{"kind": "cloud", "reached_ts": None}])
        self.j.handle({"event": "SupercruiseDestinationDrop", "timestamp": "2026-01-01T00:09:00Z", "Type": "$Fixed_Event_Life_Cloud;"})
        self.assertEqual(self.db.execute("SELECT reached_ts FROM phenomena").fetchone()[0], "2026-01-01T00:09:00Z")

    def test_phenomena_counted_and_announced_once(self):
        """The FSS lists several phenomena of a kind as identical lines in one moment: counted (they were folded into
        one), never added up when the FSS lists them again, and announced (live) the first time a system has any
        (the author's Smojooe XF-G b24-0, three rings, 2026-10-11: nothing said, one 🌀 shown)."""
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": "Smojooe XF-G b24-0", "SystemAddress": 614582987473,
                       "StarPos": [0, 0, 0]})
        sig = lambda s, kind="Ring": {"event": "FSSSignalDiscovered", "timestamp": at(s), "SystemAddress": 614582987473,
                                      "SignalName": f"$Fixed_Event_Life_{kind};", "SignalName_Localised": "Notable stellar phenomena",
                                      "SignalType": "Codex"}
        for _ in range(3):
            self.j.handle(sig(9))
        self.j.handle(sig(9, "Cloud"))
        rows = {r["kind"]: r["n"] for r in self.db.execute("SELECT kind, n FROM phenomena WHERE system=614582987473")}
        self.assertEqual(rows, {"ring": 3, "cloud": 1})
        said = [m for m in self.j.moments if m["kind"] == "phenomena"]
        self.assertEqual([(m["count"], m["kinds"], m["system_name"]) for m in said], [(4, {"ring": 3, "cloud": 1}, "Smojooe XF-G b24-0")])
        for _ in range(3):                                                    # the FSS opened again later
            self.j.handle(sig(40))
        self.assertEqual(self.db.execute("SELECT n FROM phenomena WHERE kind='ring'").fetchone()[0], 3)   # not 6
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "phenomena"]), 1)   # known now: not said again
        detail = self.state.system_detail(614582987473)
        self.assertEqual(sorted((p["kind"], p["n"]) for p in detail["phenomena"]), [("cloud", 1), ("ring", 3)])
        # a re-read of old journals: counted, never announced
        self.j.handle({"event": "FSSSignalDiscovered", "timestamp": "2020-01-01T00:00:00Z", "SystemAddress": 5,
                       "SignalName": "$Fixed_Event_Life_Cloud;", "SignalType": "Codex"})
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "phenomena"]), 1)

    def test_phenomena_sites_visited(self):
        """Visited counts the drops at a kind, at most how many the FSS found: the journal says only "a ring phenomenon",
        and two sites can share a ring (the author, 2026-10-11), so nothing better tells them apart."""
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": "Sys R", "SystemAddress": 7, "StarPos": [0, 0, 0]})
        for _ in range(3):
            self.j.handle({"event": "FSSSignalDiscovered", "timestamp": at(1), "SystemAddress": 7,
                           "SignalName": "$Fixed_Event_Life_Ring;", "SignalType": "Codex"})
        drop = lambda s: self.j.handle({"event": "SupercruiseDestinationDrop", "timestamp": at(s), "Type": "$Fixed_Event_Life_Ring;", "Threat": 0})
        visited = lambda: self.state.system_detail(7)["phenomena"][0]["visited"]
        drop(10)
        self.assertEqual(visited(), 1)
        drop(20)                                # another site (it may share the ring)
        self.assertEqual(visited(), 2)
        drop(10)                                # the same line read again: not another drop
        self.assertEqual(visited(), 2)
        self.assertIn("phenomena_sites", ed_outrider.RESET_JOURNAL_DATA)   # journal-derived: a re-read rebuilds it

    def test_surface_sites_kept_and_announced(self):
        """Guardian, Thargoid and planetary-anomaly body signals were dropped (only bio, geo and mining were kept): now
        kept per body and said once (live). The FSS says an anomaly; the DSS's map adds Guardian and Thargoid (HIP 22460
        10 b on EDDN, 2026-10-10). "Other" is kept but never said: nobody knows what it is yet."""
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": "HIP 22460", "SystemAddress": 8, "StarPos": [0, 0, 0]})
        self.j.handle({"event": "Scan", "timestamp": at(1), "ScanType": "Detailed", "StarSystem": "HIP 22460", "SystemAddress": 8,
                       "BodyID": 40, "BodyName": "HIP 22460 10 b", "PlanetClass": "Rocky body", "DistanceFromArrivalLS": 900.0,
                       "Landable": True, "WasDiscovered": True, "WasMapped": True})
        sig = lambda s, name, types: {"event": name, "timestamp": at(s), "SystemAddress": 8, "StarSystem": "HIP 22460",
                                      "BodyName": "HIP 22460 10 b", "BodyID": 40,
                                      "Signals": [{"Type": t, "Count": n} for t, n in types]}
        self.j.handle(sig(2, "FSSBodySignals", [("$SAA_SignalType_PlanetAnomaly;", 1), ("$SAA_SignalType_Geological;", 3)]))
        self.j.handle(sig(9, "SAASignalsFound", [("$SAA_SignalType_PlanetAnomaly;", 1), ("$SAA_SignalType_Geological;", 3),
                                                  ("$SAA_SignalType_Guardian;", 2), ("$SAA_SignalType_Thargoid;", 1),
                                                  ("$SAA_SignalType_Other;", 4), ("$SAA_SignalType_Human;", 2)]))
        said = [m["what"] for m in self.j.moments if m["kind"] == "surface_site"]
        self.assertEqual(said, ["an unknown planetary anomaly on 10 b", "Guardian and Thargoid sites on 10 b"])   # each news once
        body = next(b for b in self.state.system_detail(8)["bodies"] if b["name"] == "10 b")
        self.assertEqual(body["sites"], {"guardian": 2, "thargoid": 1, "anomaly": 1, "other": 4})
        self.assertEqual(body["geo"], 3)                                         # the rest as before
        # a later honk's FSS line names only the anomaly: the DSS's sites stay, and mapping again is no news (review)
        self.j.handle(sig(15, "FSSBodySignals", [("$SAA_SignalType_PlanetAnomaly;", 1)]))
        body = next(b for b in self.state.system_detail(8)["bodies"] if b["name"] == "10 b")
        self.assertEqual(body["sites"], {"guardian": 2, "thargoid": 1, "anomaly": 1, "other": 4})
        self.j.handle(sig(16, "SAASignalsFound", [("$SAA_SignalType_PlanetAnomaly;", 1), ("$SAA_SignalType_Guardian;", 2),
                                                   ("$SAA_SignalType_Thargoid;", 1), ("$SAA_SignalType_Other;", 4)]))
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "surface_site"]), 2)
        self.j.handle(sig(20, "SAASignalsFound", [("$SAA_SignalType_Guardian;", 2)]))
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "surface_site"]), 2)   # mapped again: nothing new

    def test_signals_worth_a_detour(self):
        """FSS signals worth a detour (a Titan, a listening post, tourist beacons...) were thrown away by the reader's
        filter: now kept; the rare kinds said once (live), the common ones only shown."""
        import tempfile, json as _j
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d)
        lines = [{"timestamp": at(0), "event": "FSDJump", "StarSystem": "HIP 8887", "SystemAddress": 11, "StarPos": [0, 0, 0]},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "Titan Cocijo", "SignalType": "Titan"},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "$ListeningPost:#index=1;",
                  "SignalName_Localised": "Listening Post", "SignalType": "Generic"},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "$ListeningPost:#index=2;",
                  "SignalName_Localised": "Listening Post", "SignalType": "Generic"},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "Listening Post Pollux D568",
                  "SignalType": "Generic"},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "Europa Ice Geyser", "SignalType": "TouristBeacon"},
                 {"timestamp": at(5), "event": "FSSSignalDiscovered", "SystemAddress": 11, "SignalName": "$USS_DegradedEmissions;", "SignalType": "USS"}]
        with open(os.path.join(d, "Journal.2026-10-11T100000.01.log"), "w") as f:
            for e in lines:
                f.write(_j.dumps(e, separators=(",", ":")) + "\n")   # the game's own spacing, as the filter sees it
        self.j.scan_dir(d)
        rows = [tuple(r) for r in self.db.execute("SELECT kind, name FROM poi WHERE system=11 ORDER BY kind")]
        # two indexed posts are two, and a named one passes the filter too (review 2026-10-11)
        self.assertEqual(rows, [("listening_post", "Listening Post #1"), ("listening_post", "Listening Post #2"),
                                ("listening_post", "Listening Post Pollux D568"), ("titan", "Titan Cocijo"),
                                ("tourist", "Europa Ice Geyser")])
        said = [m["what"] for m in self.j.moments if m["kind"] == "signal_poi"]
        self.assertEqual(said, ["the Titan Cocijo", "a listening post"])   # the tourist beacon is shown, not said
        self.assertEqual(len(self.state.system_detail(11)["pois"]), 5)
        self.j.handle(dict(lines[1], timestamp=at(30)))                     # the FSS lists it again
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "signal_poi"]), 2)
        self.assertIn("DELETE FROM poi", ed_outrider.RESET_JOURNAL_DATA)    # journal-derived

    def test_rare_planet_curiosities_and_the_curious_line(self):
        """Rare planet classes are curiosities (a water giant, helium giants, Sudarsky class V; a green gas giant from its
        codex entry), and a system with curiosities gets one "curious" line, once ever, while the game is live: "check
        your panels", not the list (the author, 2026-10-11)."""
        tags = lambda r: [t for t, _ in ed_outrider.curiosities(dict({"type": "Planet"}, **r))]
        self.assertEqual(tags({"subtype": "Water giant"}), ["water giant"])
        self.assertEqual(tags({"subtype": "Helium gas giant"}), ["helium giant"])
        self.assertEqual(tags({"subtype": "Class V gas giant"}), ["class V giant"])
        self.assertEqual(tags({"subtype": "Class I gas giant", "codex": [{"name": "Green Class I Gas Giant"}]}), ["green gas giant"])
        self.assertEqual(tags({"subtype": "Class I gas giant"}), [])
        now = time.time()
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(now - 30), "StarSystem": "Odd", "SystemAddress": 12, "StarPos": [0, 0, 0]})
        self.j.handle({"event": "Scan", "timestamp": ed_outrider.iso_ts(now - 20), "ScanType": "Detailed", "StarSystem": "Odd",
                       "SystemAddress": 12, "BodyID": 3, "BodyName": "Odd 3", "PlanetClass": "Water giant", "DistanceFromArrivalLS": 400.0,
                       "WasDiscovered": False, "WasMapped": False})
        self.j.status_json = {"live": False}
        self.state.maybe_curious()
        self.assertEqual([m for m in self.j.moments if m["kind"] == "curious"], [])   # the game not live: nothing said
        self.j.status_json = {"live": True}
        ed_outrider.meta_set(self.db, "curious_said", [99, 5])   # said before: 99, then 5
        with unittest.mock.patch.object(ed_outrider, "CURIOUS_KEEP", 2):
            self.state.maybe_curious()
            self.state.maybe_curious()
        said = [m for m in self.j.moments if m["kind"] == "curious"]
        self.assertEqual([(m["system"], m["bodies"]) for m in said], [("12", ["3"])])   # once
        # kept for after a restart; past CURIOUS_KEEP the oldest said goes, not the smallest id64 (review 2026-10-11)
        self.assertEqual(ed_outrider.meta_get(self.db, "curious_said"), [5, 12])

    def test_rare_stars_announced_and_shown(self):
        """A rare star (a black hole, a Wolf-Rayet...) resolved live is a "rare_star" moment, once; Nearby and Here list
        the rare stars, Spansh's included (seen before you go); common stars say nothing."""
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        self.j.handle({"event": "FSDJump", "timestamp": at(0), "StarSystem": "Rare", "SystemAddress": 9, "StarPos": [0, 0, 0]})
        star = lambda s, bid, name, kind, dist=0.0: {"event": "Scan", "timestamp": at(s), "ScanType": "AutoScan", "StarSystem": "Rare",
                                                     "SystemAddress": 9, "BodyID": bid, "BodyName": name, "StarType": kind,
                                                     "DistanceFromArrivalLS": dist, "WasDiscovered": False, "WasMapped": False}
        self.j.handle(star(1, 0, "Rare A", "H"))                          # the arrival star
        self.j.handle(star(2, 1, "Rare B", "WC", 1200.0))                 # another, from the FSS
        self.j.handle(star(3, 2, "Rare C", "M", 3000.0))                  # a red dwarf: nothing
        self.j.handle(star(4, 1, "Rare B", "WC", 1200.0))                 # scanned again: not news again
        said = [m["what"] for m in self.j.moments if m["kind"] == "rare_star"]
        self.assertEqual(said, ["a black hole, the main star", "a Wolf-Rayet star at B"])
        detail = self.state.system_detail(9)
        self.assertEqual([r["what"] for r in detail["rare_stars"]], ["a black hole", "a Wolf-Rayet star"])
        self.assertEqual(ed_outrider.rare_stars([{"name": "X A", "type": "Star", "subtype": "Herbig Ae/Be Star"},
                                                 {"name": "X B", "type": "Star", "subtype": "Neutron Star"},
                                                 {"name": "X 1", "type": "Planet", "subtype": "Black Hole"}], "X"),
                         [{"body": "A", "what": "a Herbig Ae Be star", "main": False}])   # Spansh's names too
        self.j.handle({"event": "Scan", "timestamp": "2020-01-01T00:00:00Z", "ScanType": "AutoScan", "StarSystem": "Old",
                       "SystemAddress": 10, "BodyID": 0, "BodyName": "Old", "StarType": "H", "DistanceFromArrivalLS": 0.0})
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "rare_star"]), 2)   # a re-read: never said

    def test_phenomena_lines_pass_the_filter(self):
        import tempfile, json as _j
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "w") as f:
            f.write(_j.dumps({"timestamp": "2026-01-01T00:05:00Z", "event": "FSSSignalDiscovered", "SystemAddress": 1,
                              "SignalName": "$Fixed_Event_Life_Ring;"}, separators=(",", ":")) + "\n")
        self.j.scan_dir(d)
        self.assertEqual(self.db.execute("SELECT kind FROM phenomena").fetchone()[0], "ring")

    def status(self, **kw):
        self.j.status_json = dict({"live": True, "fuel_main": 20, "flags": 0, "flags2": 0}, **kw)

    def test_on_body(self):
        self.status(body="Sys A 4", flags=2)                        # landed
        self.assertEqual(self.state.on_body()["body"], "A 4")
        self.status(body="Sys A 4", flags2=1)                       # on foot
        self.assertEqual(self.state.on_body()["how"], "on foot")
        self.status(body="Sys A 4")                                 # flying near it: not on it
        self.assertIsNone(self.state.on_body())
        # in the SRV: which one, from the journal's launch (Status.json's flag is the same for all of them)
        srv = 1 << 26
        self.j.handle({"event": "LaunchVessel", "timestamp": "2026-10-03T19:28:15Z", "VesselType": "lander01",
                       "VesselType_Localised": "Nomad", "ID": 49, "PlayerControlled": True})
        self.status(body="Sys A 4", flags=srv)
        self.assertEqual((self.state.on_body()["how"], self.state.on_body()["vehicle"]), ("in the SRV", "Nomad"))
        self.j.handle({"event": "DockSRV", "timestamp": "2026-10-03T19:34:30Z", "SRVType": "lander01", "ID": 49})
        self.j.handle({"event": "LaunchSRV", "timestamp": "2026-10-03T19:35:13Z", "SRVType": "mev_rhino",
                       "SRVType_Localised": "SRV Rhino", "ID": 54, "PlayerControlled": True})
        self.assertEqual(self.state.on_body()["vehicle"], "Rhino")
        self.j.vehicle = None                                       # a launch the journals never showed
        self.assertIsNone(self.state.on_body()["vehicle"])

    def test_destination(self):
        self.status(destination={"System": 1, "Body": 7, "Name": "Sys 7 a"})
        self.assertEqual(self.state.destination(), {"body_id": 7, "name": "7 a", "near": None})
        self.status(destination={"System": 1, "Body": 7, "Name": "Sys 7 a"}, body="Sys A 1")   # P13: flying near A 1
        self.assertEqual(self.state.destination()["near"], "A 1")
        self.status(destination={"System": 99, "Body": 7, "Name": "Elsewhere 7"})   # another system: not a body here
        self.assertIsNone(self.state.destination())


class Batch5(unittest.TestCase):
    """Batch 5: route strip, next stop, left behind, jumponium sources."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.jump("2026-01-01T00:00:00Z", 1, 0)

    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def test_route_summary(self):
        hops = [{"id64": i, "name": f"S{i}", "star_class": c, "x": i * 10.0, "y": 0, "z": 0}
                for i, c in ((1, "K"), (2, "N"), (3, "D"), (4, "Y"), (5, "M"))]
        ed_outrider.meta_set(self.db, "route", {"ts": "2026-01-01T00:00:30Z", "hops": hops})
        r = self.state.route_summary()
        self.assertEqual([h["name"] for h in r["hops"]], ["S2", "S3", "S4", "S5"])   # from where you are
        self.assertEqual((r["next_scoop"], r["longest_dry"]), (4, 3))
        self.j.handle({"event": "NavRouteClear", "timestamp": "2026-01-01T00:01:00Z"})
        self.assertIsNone(self.state.route_summary())

    def test_next_stop_clears_on_arrival(self):
        self.jump("2026-01-01T00:01:00Z", 2, 30)
        self.jump("2026-01-01T00:02:00Z", 1, 0)
        self.assertTrue(self.state.set_next_stop(2))
        self.assertEqual(self.state.next_stop_summary()["distance"], 30.0)
        self.jump("2026-01-01T00:03:00Z", 2, 30)
        self.assertIsNone(self.state.next_stop_summary())

    def test_left_behind_and_sources(self):
        self.jump("2026-01-01T00:01:00Z", 2, 30)
        ev = scan("2026-01-01T00:02:00Z", "S2", 2, 4, "S2 4")[2]
        ev.update(PlanetClass="High metal content body", MassEM=1.0, TerraformState="Terraformable", Landable=True,
                  Materials=[{"Name": "polonium", "Percent": 0.8}, {"Name": "iron", "Percent": 20}])
        self.j.handle(ev)
        self.j.handle({"event": "SAASignalsFound", "timestamp": "2026-01-01T00:03:00Z", "SystemAddress": 2, "BodyID": 4,
                       "BodyName": "S2 4", "Signals": [], "Genuses": [{"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"}]})
        self.jump("2026-01-01T00:04:00Z", 1, 0)
        self.db.commit()
        left = self.state.left_behind(100)["systems"]
        self.assertEqual(left[0]["name"], "S2")
        self.assertEqual(left[0]["bio"][0]["genera"], ["Stratum"])
        self.assertGreater(left[0]["maps"][0]["increment"], 500000)      # a terraformable HMC's map
        src = self.state.material_sources()
        self.assertEqual((src["polonium"][0]["body"], src["polonium"][0]["pct"]), ("4", 0.8))
        self.assertEqual(src["arsenic"], [])


class Batch1Alerts(unittest.TestCase):
    """Second review, batch 1: alerts that repeated or said something false."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})

    def kinds(self, kind):
        return [m for m in self.j.moments if m["kind"] == kind]

    def test_mapping_or_rescanning_a_body_announces_it_once(self):   # F1
        self.j.handle(scan("2026-01-01T00:05:00Z", "Sys", 1, 4, "Sys 4")[2])
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:08:00Z", "SystemAddress": 1,
                       "BodyName": "Sys 4", "BodyID": 4, "ProbesUsed": 5, "EfficiencyTarget": 6})
        self.j.handle(scan("2026-01-01T00:08:01Z", "Sys", 1, 4, "Sys 4")[2])      # the Detailed rescan after mapping
        self.j.handle(scan("2026-03-01T00:00:00Z", "Sys", 1, 4, "Sys 4")[2])      # an AutoScan on a return visit
        self.assertEqual([m["body_id"] for m in self.kinds("scan")], [4])
        self.j.handle(scan("2026-03-01T00:00:05Z", "Sys", 1, 5, "Sys 5")[2])      # a new body still is news
        self.assertEqual([m["body_id"] for m in self.kinds("scan")], [4, 5])

    def test_heat_damage_is_one_alert_per_30_s(self):   # F15
        for t in ("00:10:00", "00:10:03", "00:10:20", "00:10:31", "00:10:40"):
            self.j.handle({"event": "HeatDamage", "timestamp": f"2026-01-01T{t}Z"})
        self.assertEqual([m["ts"] for m in self.kinds("heat")], ["2026-01-01T00:10:00Z", "2026-01-01T00:10:31Z"])

    def test_failed_tick_does_not_repeat_moments_or_codex(self):   # F12
        import contextlib, io, tempfile
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "Journal.2026-01-02T000000.01.log"), "w") as f:
            for e in ({"timestamp": "2026-01-02T00:00:00Z", "event": "StartJump", "JumpType": "Hyperspace",
                       "StarSystem": "Next", "SystemAddress": 2, "StarClass": "K"},
                      {"timestamp": "2026-01-02T00:00:10Z", "event": "CodexEntry", "EntryID": 1, "Name": "x",
                       "SystemAddress": 1, "System": "Sys", "IsNewEntry": True},
                      {"timestamp": "2026-01-02T00:00:20Z", "event": "HeatDamage"},
                      {"timestamp": "2026-01-02T00:00:30Z", "event": "FSDJump", "StarSystem": "Next", "SystemAddress": 2,
                       "StarPos": [10, 0, 0]}):
                f.write(json.dumps(e, separators=(",", ":")) + "\n")   # the game writes "event":"X"
        calls = {"n": 0}
        orig = self.j.handle
        def flaky(ev):
            if ev.get("event") == "FSDJump" and not calls["n"]:
                calls["n"] += 1
                raise sqlite3.OperationalError("database is locked")
            return orig(ev)
        self.j.handle = flaky
        codex_rows = lambda: self.j.db.execute("SELECT count(*) FROM codex").fetchone()[0]
        seq0, codex0 = self.j.moment_seq, codex_rows()
        later = ("maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold", "maybe_locate_carrier",
                 "maybe_find_sellers")
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]))
            for name in later:
                stack.enter_context(unittest.mock.patch.object(self.state, name, lambda: None))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            self.state.tick({})
            self.assertTrue(self.state.tail_error)
            self.assertEqual((self.j.moment_seq, codex_rows()), (seq0, codex0))   # the failed tick left nothing
            self.state.tick({})
        self.assertIsNone(self.state.tail_error)
        self.assertEqual([m["kind"] for m in self.j.moments if m["seq"] > seq0], ["fsd_charge", "heat"])
        self.assertEqual(codex_rows(), codex0 + 1)
        self.assertEqual(self.j.pos["id64"], 2)

    def carrier_event(self, name, ts, **kw):
        base = {"CarrierLocation": {"CarrierType": "FleetCarrier", "CarrierID": 99},
                "CarrierJumpRequest": {"CarrierType": "FleetCarrier", "CarrierID": 99},
                "Docked": {"StationType": "FleetCarrier", "MarketID": 99, "StationName": "XYZ-123",
                           "StationServices": ["exploration"]}}.get(name, {})
        self.j.handle(dict(base, event=name, timestamp=ts, **kw))
        return self.j.carrier

    def test_carrier_arrival_and_booked_jump(self):   # F5, F45, F26
        self.carrier_event("CarrierStats", "2026-01-01T00:00:00Z", CarrierType="FleetCarrier", CarrierID=99,
                           Name="OUT OF THE BLUE", Callsign="XYZ-123")
        c = self.carrier_event("CarrierLocation", "2026-01-01T00:00:01Z", StarSystem="A", SystemAddress=10)
        first = c["moved_ts"]
        # a relog and a dock at the carrier where it already is: not an arrival
        self.carrier_event("CarrierLocation", "2026-01-02T00:00:00Z", StarSystem="A", SystemAddress=10)
        self.assertEqual(self.j.carrier["moved_ts"], first)
        self.carrier_event("CarrierJumpRequest", "2026-01-02T01:00:00Z", SystemName="B", SystemAddress=20,
                           DepartureTime="2026-01-02T01:15:00Z")
        self.carrier_event("Docked", "2026-01-02T01:05:00Z", StarSystem="A", SystemAddress=10)
        self.carrier_event("Undocked", "2026-01-02T01:06:00Z", StationName="XYZ-123")
        self.carrier_event("CarrierLocation", "2026-01-02T01:07:00Z", StarSystem="A", SystemAddress=10)   # relog
        c = self.j.carrier
        self.assertEqual((c["moved_ts"], c["planned"]["system"]), (first, "B"))   # the booking survives both
        self.assertEqual(self.state.carrier_summary()["moved_ts"], first)
        # the game writes CarrierLocation at the departure time; riding along adds a CarrierJump a minute later
        c = self.carrier_event("CarrierLocation", "2026-01-02T01:15:00Z", StarSystem="B", SystemAddress=20)
        self.assertEqual((c["system"], c["moved_ts"], c["planned"]), ("B", "2026-01-02T01:15:00Z", None))
        self.j.handle({"event": "CarrierJump", "timestamp": "2026-01-02T01:16:00Z", "StarSystem": "B", "SystemAddress": 20,
                       "StarPos": [5, 0, 0], "MarketID": 99, "Docked": True, "StationType": "FleetCarrier"})
        self.assertEqual((self.j.carrier["moved_ts"], self.j.carrier["x"]), ("2026-01-02T01:15:00Z", 5))
        # a booking made before quitting: nothing in the journal says it left, so after departure + 5 min it
        # is assumed at the destination, and the confirming CarrierLocation at the next login is no second arrival
        self.carrier_event("CarrierJumpRequest", "2026-01-03T00:00:00Z", SystemName="C", SystemAddress=30,
                           DepartureTime="2026-01-03T00:15:00Z")
        dep = ed_outrider.ts_seconds("2026-01-03T00:15:00Z")
        self.assertFalse(self.j.settle_carrier(dep + 60))
        self.assertTrue(self.j.settle_carrier(dep + 400))
        c = self.j.carrier
        self.assertEqual((c["system"], c["id64"], c["planned"], c["assumed"], c["moved_ts"]),
                         ("C", 30, None, True, "2026-01-03T00:15:00Z"))
        self.assertTrue(self.state.carrier_summary()["assumed"])
        self.assertFalse(self.j.settle_carrier(dep + 500))
        c = self.carrier_event("CarrierLocation", "2026-01-04T00:00:00Z", StarSystem="C", SystemAddress=30)
        self.assertEqual((c["moved_ts"], c["assumed"]), ("2026-01-03T00:15:00Z", False))
        self.assertEqual(ed_outrider.meta_get(self.db, "carrier")["system"], "C")
        # a jump that did not happen (the carrier is still here well after departure) is forgotten
        self.carrier_event("CarrierJumpRequest", "2026-01-05T00:00:00Z", SystemName="D", SystemAddress=40,
                           DepartureTime="2026-01-05T00:15:00Z")
        c = self.carrier_event("CarrierLocation", "2026-01-05T01:00:00Z", StarSystem="C", SystemAddress=30)
        self.assertEqual((c["system"], c["planned"]), ("C", None))
        # cancelling still ends a booking
        self.carrier_event("CarrierJumpRequest", "2026-01-06T00:00:00Z", SystemName="D", SystemAddress=40,
                           DepartureTime="2026-01-06T00:15:00Z")
        self.carrier_event("CarrierJumpCancelled", "2026-01-06T00:01:00Z", CarrierID=99)
        self.assertIsNone(self.j.carrier["planned"])

    def test_on_foot_in_a_station_is_still_docked(self):   # F6
        self.j.handle({"event": "Docked", "timestamp": "2026-01-01T01:00:00Z", "StationName": "Port", "StationType": "Coriolis",
                       "MarketID": 5, "StarSystem": "Sys", "SystemAddress": 1, "StationServices": ["exploration", "vistagenomics"]})
        live = lambda flags, flags2: setattr(self.j, "status_json", {"live": True, "flags": flags, "flags2": flags2, "fuel_main": 8})
        live(1 | (1 << 24), 0)
        self.assertTrue(self.state.docked_summary()["docked_now"])
        for bit in (3, 13, 14):   # walking the concourse to Vista Genomics: Flags 0, Flags2 OnFoot + where
            live(0, 1 | (1 << bit))
            self.assertEqual(self.state.docked_summary()["station"], "Port", bit)
        live(0, 1 | (1 << 4))     # on foot on a planet is not docked
        self.assertIsNone(self.state.docked_summary())
        # ...but the page is still told which dock that was, so a baseline taken now does not re-announce it (F44)
        self.assertEqual(self.state.payload()["docked_ts"], "2026-01-01T01:00:00Z")
        # the undock alert comes from the journal's Undocked, with the dock's ts (was anything sold since?)
        self.j.handle({"event": "Undocked", "timestamp": "2026-01-01T01:30:00Z", "StationName": "Port"})
        m = self.kinds("undocked")[-1]
        self.assertEqual((m["station"], m["dock_ts"], m["has_uc"], m["has_vista"]), ("Port", "2026-01-01T01:00:00Z", True, True))
        self.assertIsNone(self.state.docked_summary())

    def test_fuel_says_whether_you_are_in_the_ship(self):   # F75
        self.j.status_json = {"live": True, "flags": (1 << 24) | (1 << 19), "fuel_main": 4}
        f = self.state.fuel_summary()
        self.assertEqual((f["in_ship"], f["low_flag"]), (True, True))
        self.j.status_json = {"live": True, "flags": 0, "flags2": 1, "fuel_main": 4}   # on foot: LowFuel reads clear
        self.assertFalse(self.state.fuel_summary()["in_ship"])

    def test_late_target_verdict_is_reconciled_in_place(self):   # F56
        self.j.arrival_scan = {"id64": 1, "was_discovered": True, "ts": "2026-01-01T00:00:05Z"}
        self.state.reconcile_arrival()
        a = dict(self.state.arrival)
        self.assertIsNone(a["announced"])
        self.state.target_verdicts[1] = "unreported"   # the slow Spansh/EDSM lookup lands after the arrival scan
        self.state.reconcile_arrival()
        b = self.state.arrival
        self.assertEqual((b["announced"], b["wrong"], b["seq"], b["sound"]), ("unreported", True, a["seq"], None))
        v = self.state.version
        self.state.reconcile_arrival()               # settled: nothing more to do
        self.assertEqual(self.state.version, v)

    def test_second_scan_of_the_arrival_star_is_not_a_new_arrival(self):   # F30
        self.jump = lambda ts, id64, x: self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}",
                                                       "SystemAddress": id64, "StarPos": [x, 0, 0]})
        self.jump("2026-01-01T00:10:00Z", 7, 70)
        self.j.handle(scan("2026-01-01T00:10:05Z", "S7", 7, 0, "S7", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        a = dict(self.state.arrival)
        v = self.state.version
        # the Detailed scan after the honk, then a nav beacon's, at later seconds: the same arrival
        self.j.handle(scan("2026-01-01T00:10:08Z", "S7", 7, 0, "S7", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        self.j.handle(scan("2026-01-01T00:11:30Z", "S7", 7, 0, "S7", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        self.assertEqual((self.state.arrival["seq"], self.state.version), (a["seq"], v))
        # a relog in the same system keeps the arrival; a new jump (even back here) is a new one
        self.j.handle({"event": "Location", "timestamp": "2026-01-01T00:20:00Z", "StarSystem": "S7", "SystemAddress": 7,
                       "StarPos": [70, 0, 0]})
        self.j.handle(scan("2026-01-01T00:20:05Z", "S7", 7, 0, "S7", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        self.assertEqual(self.state.arrival["seq"], a["seq"])
        self.jump("2026-01-01T00:30:00Z", 8, 80)
        self.jump("2026-01-01T00:40:00Z", 7, 70)
        self.j.handle(scan("2026-01-01T00:40:05Z", "S7", 7, 0, "S7", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        self.assertEqual(self.state.arrival["seq"], a["seq"] + 1)


class Batch3Journal(unittest.TestCase):
    """Second review, batch 3: the journal reader (order, repairs, duplicate files)."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)

    def write(self, folder, name, events):
        d = os.path.join(self.tmp.name, folder)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "a") as f:
            for e in events:
                f.write(json.dumps(e, separators=(",", ":")) + "\n")
        return d

    @staticmethod
    def jump(ts, id64, x=0.0):
        return {"timestamp": ts, "event": "FSDJump", "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0],
                "JumpDist": 10.0, "FuelUsed": 1.0}

    def test_legacy_read_after_live_changes_nothing_current(self):   # F11
        live = self.write("live", "Journal.2026-05-01T100000.01.log", [
            {"timestamp": "2026-05-01T10:00:00Z", "event": "CarrierStats", "CarrierID": 7, "Name": "C", "Callsign": "ABC-123",
             "FuelLevel": 800, "JumpRangeCurr": 500},
            {"timestamp": "2026-05-01T10:00:05Z", "event": "CarrierLocation", "CarrierID": 7, "StarSystem": "S100",
             "SystemAddress": 100},
            self.jump("2026-05-01T10:01:00Z", 100),
            {"timestamp": "2026-05-01T10:02:00Z", "event": "Docked", "StationName": "Stn", "StationType": "Coriolis",
             "MarketID": 5, "StarSystem": "S100", "SystemAddress": 100, "StationServices": []},
            {"timestamp": "2026-05-01T10:03:00Z", "event": "HullDamage", "Health": 0.6, "PlayerPilot": True, "Fighter": False},
            {"timestamp": "2026-05-01T10:04:00Z", "event": "FuelScoop", "Scooped": 5.0, "Total": 32.0},
            {"timestamp": "2026-05-01T10:05:00Z", "event": "MultiSellExplorationData", "TotalEarnings": 1000,
             "BaseValue": 1000, "Bonus": 0, "Discovered": []},
            org("2026-05-01T10:06:00Z", 100, 3, "Bacterial_01", "Log")])
        legacy = self.write("legacy", "Journal.2025-01-01T100000.01.log", [
            {"timestamp": "2025-01-01T10:00:00Z", "event": "CarrierLocation", "CarrierID": 7, "StarSystem": "S50",
             "SystemAddress": 50},
            {"timestamp": "2025-01-01T10:00:01Z", "event": "CarrierStats", "CarrierID": 7, "Name": "C", "Callsign": "ABC-123",
             "FuelLevel": 100, "JumpRangeCurr": 500},
            self.jump("2025-01-01T10:01:00Z", 50, 10),
            {"timestamp": "2025-01-01T10:02:00Z", "event": "Undocked", "StationName": "Stn"},
            {"timestamp": "2025-01-01T10:02:30Z", "event": "Docked", "StationName": "Old", "StationType": "Outpost",
             "MarketID": 6, "StarSystem": "S50", "SystemAddress": 50, "StationServices": []},
            {"timestamp": "2025-01-01T10:03:00Z", "event": "HullDamage", "Health": 0.2, "PlayerPilot": True, "Fighter": False},
            {"timestamp": "2025-01-01T10:04:00Z", "event": "FuelScoop", "Scooped": 5.0, "Total": 32.0},
            {"timestamp": "2025-01-01T10:04:30Z", "event": "JetConeBoost", "BoostValue": 4.0},
            {"timestamp": "2025-01-01T10:04:40Z", "event": "SupercruiseDestinationDrop", "Type": "$Fixed_Event_Life_Cloud;"},
            {"timestamp": "2025-01-01T10:05:00Z", "event": "MultiSellExplorationData", "TotalEarnings": 5,
             "BaseValue": 5, "Bonus": 0, "Discovered": []},
            {"timestamp": "2025-01-01T10:06:00Z", "event": "Died"},
            org("2025-01-01T10:07:00Z", 50, 2, "Bacterial_02", "Log")])
        self.j.scan_dir(live)
        self.j.scan_dir(legacy)       # a legacy folder mounted later: imported after the live data
        j = self.j
        self.assertEqual((j.pos["id64"], j.docked["station"], j.hull["pct"]), (100, "Stn", 60))
        self.assertEqual((j.carrier["id64"], j.carrier["fuel"]), (100, 800))
        self.assertEqual(j.last_scoop, "2026-05-01T10:04:00Z")
        self.assertIsNone(j.boost)
        self.assertEqual((j.last_sale["ts"], j.last_sale["carto"]), ("2026-05-01T10:05:00Z", 1000))
        self.assertEqual(self.db.execute("SELECT count(*) FROM phenomena").fetchone()[0], 0)   # no old drop filed here
        runs = {r[0] for r in self.db.execute("SELECT system FROM own_organic WHERE done_ts IS NULL")}
        self.assertIn(100, runs)      # the old death and the old run did not abandon the current sample run
        # and the same state survives a reload from the database
        j.reload()
        self.assertEqual((j.docked["station"], j.hull["pct"], j.carrier["fuel"]), ("Stn", 60, 800))

    def test_station_repair_lists_items(self):   # F13
        self.j.handle({"timestamp": "2026-01-01T00:00:00Z", "event": "HullDamage", "Health": 0.57, "PlayerPilot": True, "Fighter": False})
        self.j.handle({"timestamp": "2026-01-01T00:01:00Z", "event": "Repair", "Items": ["Paint"], "Cost": 2})
        self.assertEqual(self.j.hull["pct"], 57)
        # "Wear" is the ship's integrity: a damaged hull's repair names "Hull" too (review 2026-10-11)
        self.j.handle({"timestamp": "2026-01-01T00:01:30Z", "event": "Repair", "Items": ["Wear"], "Cost": 3134})
        self.assertEqual(self.j.hull["pct"], 57)
        self.j.handle({"timestamp": "2026-01-01T00:02:00Z", "event": "Repair", "Items": ["Hull"], "Cost": 3134})
        self.assertEqual(self.j.hull["pct"], 100)
        self.j.handle({"timestamp": "2026-01-01T00:03:00Z", "event": "HullDamage", "Health": 0.5, "PlayerPilot": True, "Fighter": False})
        self.j.handle({"timestamp": "2026-01-01T00:04:00Z", "event": "Repair", "Item": "Hull", "Cost": 10})   # the older form
        self.assertEqual(self.j.hull["pct"], 100)

    def test_limpet_repair_makes_hull_unknown(self):   # F14; fourth review F4: Synthesis "Repair Basic" is the SRV's
        self.assertIn(b'"event":"RepairDrone"', ed_outrider.WANTED)
        self.j.handle({"timestamp": "2026-01-01T00:00:00Z", "event": "HullDamage", "Health": 0.38, "PlayerPilot": True, "Fighter": False})
        self.j.handle({"timestamp": "2026-01-01T00:01:00Z", "event": "RepairDrone", "HullRepaired": 58.5})
        self.assertEqual(self.j.hull, {"pct": None, "ts": "2026-01-01T00:01:00Z", "repaired": True})
        self.j.handle({"timestamp": "2026-01-01T00:02:00Z", "event": "HullDamage", "Health": 0.7, "PlayerPilot": True, "Fighter": False})
        self.assertEqual(self.j.hull["pct"], 70)
        self.j.handle({"timestamp": "2026-01-01T00:03:00Z", "event": "Synthesis", "Name": "Repair Basic",
                       "Materials": [{"Name": "iron", "Count": 2}, {"Name": "nickel", "Count": 1}]})
        self.assertEqual(self.j.hull["pct"], 70)   # the SRV's repair: the ship's hull stays known, no second alert
        self.assertIn("SRV repair basic", outrider.materials.SYNTH)

    def test_same_journal_in_two_folders_counts_once(self):   # F51
        name = "Journal.2026-01-01T000000.01.log"
        a = self.write("a", name, [self.jump("2026-01-01T00:00:00Z", 1)])
        b = self.write("b", name, [self.jump("2026-01-01T00:00:00Z", 1)])
        self.j.scan_dir(a)
        self.j.scan_dir(b)
        self.assertEqual(self.db.execute("SELECT count FROM visits WHERE id64=1").fetchone()[0], 1)
        self.write("b", name, [self.jump("2026-01-01T00:10:00Z", 2, 10)])   # the copy grows: only the new line is read
        self.j.scan_dir(b)
        self.j.scan_dir(a)
        self.assertEqual({r[0]: r[1] for r in self.db.execute("SELECT id64, count FROM visits")}, {1: 1, 2: 1})
        self.j.reload()                                                     # and after a restart
        self.j.scan_dir(a)
        self.j.scan_dir(b)
        self.assertEqual({r[0]: r[1] for r in self.db.execute("SELECT id64, count FROM visits")}, {1: 1, 2: 1})


class Batch3Server(unittest.TestCase):
    """Second review, batch 3: server state and background work."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def jump(self, ts, id64, x, kind="FSDJump"):
        self.j.handle({"event": kind, "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def fake_spansh(self, dump):
        calls = []

        class FakeSpansh(ed_outrider.Spansh):
            async def lookup(self, id64, interactive=True):
                calls.append(id64)
                return dump
        return FakeSpansh(self.db), calls

    def test_dump_404_is_remembered(self):   # F52
        import asyncio
        sp, calls = self.fake_spansh(None)
        self.state.spansh = sp
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 3,
                "records": [{"name": "Sys 1", "type": "Planet", "subtype": "Icy body", "full": False}]}
        got = asyncio.run(sp.full_records(7, "u1", base))
        self.assertTrue(got["no_dump"])
        self.assertEqual(sp.cached(7)[0], "u1")                # cached with the search's updated_at
        self.db.execute("INSERT INTO visits VALUES (7, 'Sys', 0, 0, 0, 't', 't', 1)")
        self.state.bases[7] = ("spansh", got)
        self.assertFalse(self.state.system_detail(7)["partial"])  # the page stops polling
        del self.state.bases[7]
        asyncio.run(self.state.ensure_records(7))                 # on demand: not asked again within the day
        self.assertEqual(calls, [7])

    def test_a_codex_entry_without_a_body_is_on_no_body(self):
        """A CodexEntry with no BodyID (a phenomenon found in space) was listed, voucher and all, on every body of the
        system you had not scanned yourself (review 2026-10-11)."""
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7,
                       "StarPos": [0, 0, 0]})
        self.j.handle({"timestamp": "2026-01-01T00:01:00Z", "event": "CodexEntry", "EntryID": 2100701, "Name": "$Codex_Ent_L_Clouds;",
                       "Name_Localised": "Lagrange Cloud", "SystemAddress": 7, "System": "Sys", "IsNewEntry": True,
                       "VoucherAmount": 2500, "NearestDestination": "$SAA_Unknown_Signal:#type=$SAA_SignalType_Stellar;"})
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 2, "records": [
            {"name": "Sys 1", "type": "Planet", "subtype": "Icy body", "full": True},
            {"name": "Sys 2", "type": "Planet", "subtype": "Rocky body", "full": True}]}
        self.state.bases[7] = ("spansh", base)
        bodies = [b for b in self.state.system_detail(7)["bodies"] if b.get("type") == "Planet"]
        self.assertEqual([(b["name"], b["codex"]) for b in bodies], [("Sys 1", []), ("Sys 2", [])])

    def test_a_species_scanned_twice_is_one_codex_line(self):
        """The game logs a CodexEntry for each composition scan of a species, not only its first: two scans of Tussock
        Cultro on one body showed it twice in the body's bio list, the second without its value (the author 2026-10-18)."""
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sys", "SystemAddress": 7,
                       "StarPos": [0, 0, 0]})
        self.j.handle({"timestamp": "2026-01-01T00:00:30Z", "event": "Scan", "ScanType": "Detailed", "BodyName": "Sys 1",
                       "BodyID": 1, "StarSystem": "Sys", "SystemAddress": 7, "PlanetClass": "Rocky body",
                       "DistanceFromArrivalLS": 10, "WasDiscovered": True, "WasMapped": True})
        for ts, new in (("2026-01-01T00:01:00Z", True), ("2026-01-01T00:09:00Z", False)):
            self.j.handle({"timestamp": ts, "event": "CodexEntry", "EntryID": 2450403, "Name": "$Codex_Ent_Tussocks_08_F_Name;",
                           "Name_Localised": "Tussock Cultro - Green", "SubCategory": "$Codex_SubCategory_Organic_Structures;", "SubCategory_Localised": "Organic structures",
                           "Category": "$Codex_Category_Biology;", "SystemAddress": 7, "System": "Sys", "BodyID": 1,
                           "IsNewEntry": new, "VoucherAmount": 2500 if new else None})
        base = {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0, "body_count": 1, "records": [
            {"name": "Sys 1", "body_id": 1, "type": "Planet", "subtype": "Rocky body", "full": True}]}
        self.state.bases[7] = ("spansh", base)
        body = [b for b in self.state.system_detail(7)["bodies"] if b.get("type") == "Planet"][0]
        self.assertEqual([(c["name"], c["new"], c["voucher"], c["entry_id"]) for c in body["codex"]],
                         [("Tussock Cultro - Green", True, 2500, 2450403)])

    def test_dump_replaces_an_edsm_stand_in(self):
        """A system first found through EDSM (find_system's fallback) and later filled from Spansh's dump is Spansh's:
        it kept the edsm marker, so spansh_verdict ignored it (review 2026-10-11)."""
        import asyncio
        sp, _ = self.fake_spansh({"system": {"bodyCount": 1, "bodies": [
            {"name": "Sys A", "type": "Star", "subType": "K (Yellow-Orange) Star", "solarMasses": 0.8}]}})
        stand_in = ed_outrider.base_from_edsm({"name": "Sys", "coords": {"x": 0, "y": 0, "z": 0},
                                               "primaryStar": {"type": "K (Yellow-Orange) Star", "isScoopable": True}})
        self.assertEqual(ed_outrider.cached_source(stand_in), "edsm")
        got = asyncio.run(sp.full_records(7, "u1", stand_in))
        self.assertNotIn("edsm", got)
        self.assertEqual(ed_outrider.cached_source(got), "spansh")

    def test_dump_body_count_is_kept(self):   # F53
        import asyncio
        sp, _ = self.fake_spansh({"system": {"bodyCount": 12, "bodies": []}})
        got = asyncio.run(sp.full_records(7, None, {"v": ed_outrider.CACHE_VERSION, "name": "Sys", "x": 0, "y": 0, "z": 0,
                                                    "body_count": None, "records": [], "no_dump": True}))
        self.assertEqual(got["body_count"], 12)
        self.assertNotIn("no_dump", got)

    def test_edsm_star_is_a_placeholder(self):   # F54
        base = ed_outrider.base_from_edsm({"name": "Sys", "coords": {"x": 0, "y": 0, "z": 0},
                                           "primaryStar": {"type": "K (Yellow-Orange) Star", "isScoopable": True}})
        own = {"A": {"name": "A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "main": True, "rings": []},
               "B": {"name": "B", "type": "Star", "subtype": "M (Red dwarf) Star", "main": False, "rings": []}}
        self.assertEqual([r["name"] for r in ed_outrider.merge_records(base["records"], own, {})], ["A", "B"])
        planets = {"1": {"name": "1", "type": "Planet", "subtype": "Icy body", "main": False, "rings": []}}
        self.assertEqual(len(ed_outrider.merge_records(base["records"], planets, {})), 2)   # still the only star known

    def test_carrier_lookup_backs_off(self):   # F19
        import asyncio
        sp, calls = self.fake_spansh(None)
        self.state.spansh = sp
        self.j.carrier = {"id": 7, "id64": 555, "system": "Deep", "x": None}

        async def go():
            for _ in range(3):
                self.state.maybe_locate_carrier()
                if self.state.carrier_task:
                    await self.state.carrier_task
        asyncio.run(go())
        self.assertEqual(calls, [555])
        self.state.carrier_retry[555] = 0     # ten minutes later: asked again
        asyncio.run(go())
        self.assertEqual(calls, [555, 555])

    def test_seller_reported_minutes_ago_is_fresh(self):   # F17
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1200))
        uc = [{"name": "XYZ-123", "type": "Drake-Class Carrier", "updated_at": now, "x": 40, "y": 0, "z": 0, "distance": 40},
              {"name": "Far Port", "type": "Coriolis Starport", "updated_at": "2026-01-01T00:00:00Z",
               "x": 400, "y": 0, "z": 0, "distance": 400}]
        ed_outrider.meta_set(self.db, "sellers", {"pos": {"x": 0, "y": 0, "z": 0, "name": "S1"}, "fetched": time.time(),
                                                  "uc": uc, "vista": []})
        self.assertEqual(self.state.sellers_summary()["uc"]["fresh"]["name"], "XYZ-123")

    def test_value_only_changes_leave_scan_version(self):   # G2.1
        import asyncio
        self.state.bases = {1: ("spansh", {"name": "S1", "x": 0, "y": 0, "z": 0, "records": []}),
                            2: ("spansh", {"name": "S2", "x": 1, "y": 0, "z": 0, "records": []})}
        self.state.center = {"x": 0, "y": 0, "z": 0}
        results = iter([{"carto": {}, "system_values": {"S1": 10}}, {"carto": {}, "system_values": {"S1": 10}},
                        {"carto": {}, "system_values": {"S1": 10, "S2": 5}}])

        async def unsold_once():
            self.state.unsold_dirty, self.state.unsold_at = True, 0
            self.state.maybe_unsold()
            await self.state.unsold_task
            return set(self.state.value_dirty)
        with unittest.mock.patch.object(ed_outrider, "compute_unsold", lambda: next(results)):
            self.assertEqual(asyncio.run(unsold_once()), {1})
            self.state.apply_own_changes()
            self.assertEqual(self.state.scan_version, 0)          # rows rebuilt, no "new scan data"
            self.assertIn(1, self.state.systems)
            self.assertEqual(asyncio.run(unsold_once()), set())   # nothing moved: nothing rebuilt
            self.assertEqual(asyncio.run(unsold_once()), {2})

    def test_failed_estimate_does_not_break_a_sale(self):   # F18
        self.state.unsold = {"error": "no journals"}
        self.state.bases = {1: ("spansh", {"name": "S1", "x": 0, "y": 0, "z": 0, "records": []})}
        self.state.center = {"x": 0, "y": 0, "z": 0}
        self.j.sales_changed = True
        self.j.dirty.add(1)
        self.state.apply_own_changes()
        self.assertIn(1, self.state.systems)
        self.assertFalse(self.j.sales_changed)

    def test_row_error_stays_visible_and_retries(self):   # F89
        import asyncio, contextlib, io
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        self.state.center = self.j.pos
        self.state.bases = {1: ("spansh", {"name": "S1", "x": 0, "y": 0, "z": 0, "records": []})}
        self.state.unsold_dirty = False
        self.j.dirty.add(1)
        fail = {"on": True}
        real = self.state.row

        def row(id64):
            if fail["on"]:
                raise ValueError("bad record")
            return real(id64)
        self.state.row = row
        err = io.StringIO()

        async def ticks(n):
            for _ in range(n):
                self.state.tick({})
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), contextlib.redirect_stderr(err):
            asyncio.run(ticks(3))
            self.assertIn("bad record", self.state.tail_error)     # still shown after the tick that set it
            self.assertEqual(err.getvalue().count("Traceback"), 1)   # one traceback, not one a second
            v = self.state.scan_version
            fail["on"] = False
            asyncio.run(ticks(1))
        self.assertIsNone(self.state.tail_error)
        self.assertIn(1, self.state.systems)                       # retried and built
        self.assertEqual(self.state.scan_version, v)               # a retry is not new scan data

    def test_backup_failure_leaves_nothing(self):   # F55
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            dbp = os.path.join(d, "x.sqlite")
            sqlite3.connect(dbp).close()
            out = os.path.join(d, "backups")
            self.state.db_path = dbp
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(zipfile.ZipFile, "write", side_effect=OSError(28, "No space left on device")):
                with self.assertRaises(OSError):
                    self.state.make_backup()
            self.assertEqual(os.listdir(out), [])

    def test_route_export_after_respawn(self):   # F57
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        self.jump("2026-01-01T01:00:00Z", 2, 100, kind="Location")   # respawn somewhere new
        self.jump("2026-01-01T01:10:00Z", 3, 122)
        _, rows = self.state.export_rows("route")
        self.assertEqual([r["ly"] for r in rows], [None, None, 22.0])
        self.assertEqual(self.state.sessions("")[0]["ly"], 22.0)

    def test_history_counts_after_the_last_jump(self):   # F7
        self.jump("2026-01-01T22:00:00Z", 1, 0)
        self.db.execute("INSERT INTO own_mapped (system, body_id, ts) VALUES (1, 4, '2026-01-01T23:00:00Z')")   # after the session's only jump
        self.db.execute("INSERT INTO own_mapped (system, body_id, ts) VALUES (1, 5, '2026-01-02T03:00:00Z')")   # a long stay, no jump
        self.jump("2026-01-03T10:00:00Z", 2, 10)
        self.db.execute("INSERT INTO own_mapped (system, body_id, ts) VALUES (2, 1, '2026-01-03T11:00:00Z')")
        h = self.state.history(3650 * 3)
        self.assertEqual([s["mapped"] for s in h["sessions"]], [1, 2])   # newest first; together = all time
        self.assertEqual(h["all_time"]["mapped"], 3)

    def test_history_sold_and_deaths(self):   # S63
        """Each session's sold (every sale, cartographics and exobiology) and its deaths with the Resurrect choice;
        the all-time row counts the deaths and the ships lost. A Resurrect has History ask again."""
        self.jump("2026-01-01T10:00:00Z", 1, 0)
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": "2026-01-01T10:10:00Z", "TotalEarnings": 300,
                       "BaseValue": 300, "Bonus": 0, "Discovered": []})
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T10:20:00Z", "MarketID": 1,
                       "BioData": [{"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Species": "$Codex_Ent_Bacterial_01_Name;",
                                    "Value": 1000, "Bonus": 4000}]})
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T10:30:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T10:31:00Z", "Option": "rebuy", "Cost": 1, "Bankrupt": False})
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T10:40:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T10:41:00Z", "Option": "recover", "Cost": 0, "Bankrupt": False})
        self.jump("2026-01-02T10:00:00Z", 2, 10)
        self.j.handle({"event": "Died", "timestamp": "2026-01-02T10:05:00Z"})   # no Resurrect yet: counted as a loss
        h = self.state.history(3650 * 3)
        new, old = h["sessions"]
        self.assertEqual((old["sold"], new["sold"]), (5300, 0))
        self.assertEqual([(d["ts"][11:16], d["option"], d["ship"]) for d in old["deaths"]],
                         [("10:30", "rebuy", True), ("10:40", "recover", False)])
        self.assertEqual([(d["option"], d["ship"]) for d in new["deaths"]], [(None, True)])
        self.assertEqual((h["all_time"]["sold"], h["all_time"]["died"], h["all_time"]["lost"]), (5300, 3, 2))
        self.state.apply_own_changes()
        v = self.state.history_version
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-02T10:06:00Z", "Option": "recover", "Cost": 0, "Bankrupt": False})
        self.state.apply_own_changes()
        self.assertEqual(self.state.history_version, v + 1)
        self.assertFalse(self.state.history(3650 * 3)["sessions"][0]["deaths"][0]["ship"])

    def test_trip_hours_clip_sessions_at_the_sale(self):   # F16
        # one session: 3 h flying home, a sale, 1 h more exploring (jumps every 30 min keep it one session)
        t0 = ed_outrider.ts_seconds("2026-01-01T00:00:00Z")
        stamp = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0 + s))
        for i in range(9):
            self.jump(stamp(i * 1800), 10 + i, i * 10)
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": stamp(3 * 3600), "TotalEarnings": 300,
                       "BaseValue": 300, "Bonus": 0, "Discovered": []})
        self.jump(stamp(4 * 3600 + 1800), 30, 200)
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": stamp(5 * 3600), "TotalEarnings": 100,
                       "BaseValue": 100, "Bonus": 0, "Discovered": []})
        self.db.commit()
        trips = self.state.ledger()["trips"]          # newest first
        self.assertEqual([t["hours"] for t in trips], [1.5, 3.0])
        self.assertEqual(trips[1]["per_hour"], 100)

    def test_autohonk_toggle_is_committed(self):   # F62
        self.state.set_autohonk(True)
        self.db.rollback()                            # a failing watcher tick
        self.assertIs(ed_outrider.meta_get(self.db, "autohonk_enabled"), True)

    def test_voice_choice_is_saved(self):   # F21
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        class FakeSpeaker:
            available = True

            def use(self, name):
                return name == "en_GB-alba-medium"
        self.state.speaker = FakeSpeaker()

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return (await c.post("/api/voice", json={"voice": "en_GB-alba-medium"})).status
        self.assertEqual(asyncio.run(go()), 200)
        self.assertIsNone(ed_outrider.meta_get(self.db, "voice_choice"))   # F36: saved once it has loaded
        self.state.remember_voice("en_GB-alba-medium")                      # (the Speaker's on_switched)
        self.db.rollback()
        self.assertEqual(ed_outrider.meta_get(self.db, "voice_choice"), "en_GB-alba-medium")

    def test_startup_voice_load_does_not_replace_the_chosen_one(self):   # F21
        import io, tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            for v in ("en_GB-a-low", "en_GB-b-low"):
                for ext in (".onnx", ".onnx.json"):
                    open(os.path.join(d, v + ext), "w").close()
            sp = outrider.tts.Speaker("en_GB-a-low", None, voices_dir=d)
            sp.PiperVoice = unittest.mock.Mock()
            sp.PiperVoice.load = lambda path: os.path.basename(path)
            sp.wanted = "en_GB-b-low"
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                sp._prepare("en_GB-b-low")    # the dialog's pick loads first
                sp._prepare(None)             # then the slow start-up load of the configured voice finishes
            self.assertEqual((sp.voice_name, sp._voice), ("en_GB-b-low", "en_GB-b-low.onnx"))

    def test_star_pair_planets_are_not_a_planet_pair(self):   # F47
        via = [{"kind": "Null", "id": 3}, {"kind": "Star", "id": 0}]
        p1 = {"name": "BC 1", "type": "Planet", "body_id": 20, "parents_full": via}
        p2 = {"name": "BC 2", "type": "Planet", "body_id": 21, "parents_full": via}
        self.assertEqual(ed_outrider.system_curiosities("S", [p1, p2]), {})   # stars B and C not scanned
        moons = [{"name": f"BC 1 {m}", "type": "Planet", "body_id": 30 + i, "parents_full": [{"kind": "Null", "id": 29}] + via}
                 for i, m in enumerate("ab")]
        self.assertEqual(ed_outrider.system_curiosities("S", moons), {})   # nor is a pair of moons (2026-10-12: no pairs at all)

    def test_bio_left_after_a_finished_genus(self):   # F20b
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        s = scan("2026-01-01T00:01:00Z", "S1", 1, 2, "S1 2")[2]
        self.j.handle(s)
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:01:00Z", "SystemAddress": 1, "BodyID": 2,
                       "BodyName": "S1 2", "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 1}]})
        for i, k in enumerate(("Log", "Sample", "Analyse")):
            self.j.handle(org(f"2026-01-01T00:0{2 + i}:00Z", 1, 2, "Bacterial_01", k))
        self.db.commit()
        cands = CANDS
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=cands):
            b = next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == "2")
            self.assertEqual(b["value_parts"]["bio_left"], 0)        # the one signal is done
            recs = ed_outrider.merge_records([], *ed_outrider.own_data(self.db, 1, "S1")[:2])
            self.assertEqual(self.state.system_value(1, "S1", recs, None)["value_parts"]["bio_left"], 0)
            # two signals, Bacterium done: the other is the most valuable of the rest (not Stratum + Concha)
            self.db.execute("UPDATE own_signals SET bio = 2")
            b = next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == "2")
            self.assertEqual(b["value_parts"]["bio_left"], 19_010_800 * b["value_parts"]["bio_factor"])
            recs = ed_outrider.merge_records([], *ed_outrider.own_data(self.db, 1, "S1")[:2])
            self.assertEqual(self.state.system_value(1, "S1", recs, None)["value_parts"]["bio_left"], 19_010_800)

    def test_local_search_runs_off_the_loop(self):   # F22
        import asyncio, tempfile, threading
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "odd name.sqlite")
            db = ed_outrider.open_db(path)
            self.addCleanup(db.close)
            j = ed_outrider.Journals(db)
            j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "S1", "SystemAddress": 1,
                      "StarPos": [0, 0, 0]})
            j.handle(scan("2026-01-01T00:01:00Z", "S1", 1, 0, "S1", star=True)[2])
            db.commit()
            state = ed_outrider.State(db, j, ed_outrider.Spansh(db), 25)
            state.db_path = path
            s = ed_outrider.Searcher(state)
            seen = []
            real = s.match

            def match(conn, *a, **kw):
                seen.append((threading.current_thread() is threading.main_thread(), conn is db))
                return real(conn, *a, **kw)
            s.match = match

            async def go():
                s.start({"source": "local", "radius": 50, "stars": ["K"]})
                await s.task
            asyncio.run(go())
            self.assertEqual(seen, [(False, False)])       # a worker thread, with its own connection
            self.assertEqual([r["name"] for r in s.result["results"]], ["S1"])


class Batch4Page(unittest.TestCase):
    """Second review, batch 4: the server side of the page-robustness fixes (map, schematic, Log)."""

    def folder(self, files):
        import tempfile, json as _j
        d = tempfile.mkdtemp()
        for name, events in files.items():
            with open(os.path.join(d, name), "w") as f:
                for e in events:
                    f.write(_j.dumps(e, separators=(",", ":")) + "\n")
        return d

    def state(self, spansh):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "S1", "SystemAddress": 1,
                  "StarPos": [0, 0, 0]})
        return ed_outrider.State(db, j, spansh, 25), j, db

    def test_body_rows_carry_belts(self):   # F69
        import types
        state, j, db = self.state(types.SimpleNamespace(cached=lambda i: (None, None)))
        ev = scan("2026-01-01T00:01:00Z", "S1", 1, 0, "S1", star=True)[2]
        ev["Rings"] = [{"Name": "S1 A Belt", "RingClass": "eRingClass_Rocky", "MassMT": 1e9, "InnerRad": 1, "OuterRad": 2}]
        j.handle(ev)
        db.commit()
        star = next(b for b in state.system_detail(1)["bodies"] if b["type"] == "Star")
        self.assertEqual(len(star["belts"]), 1)
        self.assertEqual(star["rings"], 0)

    def test_map_says_partial_when_spansh_failed(self):   # F71
        import asyncio, types
        ok = {"fail": True}

        async def sphere(pos, radius, pages):
            if ok["fail"]:
                raise RuntimeError("timeout")
            return [{"id64": 2, "name": "S2", "x": 1, "y": 0, "z": 0, "distance": 1, "bodies": []}]
        state, j, db = self.state(types.SimpleNamespace(cached=lambda i: (None, None), sphere=sphere))
        d = asyncio.run(state.map_payload(10, 5))
        self.assertTrue(d["partial"])
        self.assertIn("Spansh lookup failed", d["note"])
        ok["fail"] = False
        d = asyncio.run(state.map_payload(10, 5))          # not cached: asked again, and complete now
        self.assertFalse(d["partial"])
        self.assertIn("S2", [p["name"] for p in d["points"]])

    def test_tail_past_an_empty_new_journal(self):   # F84
        now = dt.datetime.now(dt.timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        a = (now - dt.timedelta(minutes=5)).strftime("Journal.%Y-%m-%dT%H%M%S.01.log")
        b = now.strftime("Journal.%Y-%m-%dT%H%M%S.01.log")
        d = self.folder({a: [{"timestamp": ts, "event": "FSDJump", "StarSystem": f"S{i}"} for i in range(4)]})
        open(os.path.join(d, b), "w").close()                 # the game just created it: no complete line yet
        first = outrider.log.read_log([d], days=1)
        self.assertEqual(first["newest"], f"{a}|3")             # not None: the tail can start
        t1 = outrider.log.read_log([d], after=f"{a}|1")
        self.assertEqual([r["system"] for r in t1["rows"]], ["S3", "S2"])
        self.assertEqual(t1["newest"], f"{a}|3")                # not back to a|1
        self.assertEqual(outrider.log.read_log([d], after=t1["newest"])["rows"], [])   # nothing twice
        with open(os.path.join(d, b), "a") as f:
            f.write(json.dumps({"timestamp": ts, "event": "FSDJump", "StarSystem": "S9"}) + "\n")
        t2 = outrider.log.read_log([d], after=t1["newest"])
        self.assertEqual([r["system"] for r in t2["rows"]], ["S9"])
        self.assertEqual(t2["newest"], f"{b}|0")

    def test_unreadable_journal_is_skipped(self):   # F29
        now = dt.datetime.now(dt.timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        d = self.folder({now.strftime("Journal.%Y-%m-%dT%H%M%S.01.log"): [{"timestamp": ts, "event": "FSDJump", "StarSystem": "S1"}]})
        real_open = open

        def failing(path, *a, **k):
            if str(path).startswith(d):
                raise PermissionError(13, "Permission denied")
            return real_open(path, *a, **k)
        with unittest.mock.patch("builtins.open", failing):
            r = outrider.log.read_log([d], days=1)
        self.assertEqual(r["rows"], [])

    def test_cache_is_thread_safe(self):   # F83
        import tempfile, threading
        d = tempfile.mkdtemp()
        paths = []
        for i in range(outrider.log._CACHE_MAX * 2):
            p = os.path.join(d, f"Journal.2026-09-{1 + i // 10:02d}T{10 + i % 10:02d}0000.01.log")
            with open(p, "w") as f:
                f.write('{"timestamp":"2026-09-01T00:00:00Z","event":"Music"}\n')
            paths.append(p)
        errors = []

        def work(k):
            for n in range(600):
                try:
                    outrider.log._load(paths[(n * 7 + k) % len(paths)])
                except Exception as e:     # without the lock: "OrderedDict mutated during iteration"
                    errors.append(e)
        old = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            ts = [threading.Thread(target=work, args=(k,)) for k in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        finally:
            sys.setswitchinterval(old)
        self.assertEqual(errors, [])


class BatchAIntegrity(unittest.TestCase):
    """Review 2026-09-30 batch A: live-only data kept through a re-read, sale pages, backups, config, journal
    reading. Files only in temp folders."""

    def setUp(self):
        import tempfile, types
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def write(self, folder, name, events):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e, separators=(",", ":")) + "\r\n")   # the game writes CRLF
        return path

    @staticmethod
    def page(ts, total, systems):
        return {"timestamp": ts, "event": "MultiSellExplorationData", "BaseValue": total, "Bonus": 0,
                "TotalEarnings": total, "Discovered": [{"SystemName": s, "NumBodies": 1} for s in systems]}

    def jump(self, ts, id64, x=0):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64,
                       "StarPos": [x, 0, 0]})

    # ---- F1: estimates and sample positions survive a journal re-read ----
    def test_old_database_keeps_estimates_and_sample_points(self):   # F1
        path = os.path.join(self.tmp, "old.sqlite")
        old = sqlite3.connect(path)
        old.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE sale_events (ts TEXT, kind TEXT, base INTEGER, bonus INTEGER, total INTEGER, systems INTEGER,
                                      species INTEGER, estimate INTEGER, PRIMARY KEY (ts, kind));
            CREATE TABLE sample_points (system INTEGER, body_id INTEGER, species TEXT, genus TEXT, n INTEGER,
                                        lat REAL, lon REAL, ts TEXT, PRIMARY KEY (system, body_id, species, n));
            INSERT INTO meta VALUES ('parser_version', '21');
            INSERT INTO sale_events VALUES ('2026-01-02T00:00:00Z', 'carto', 900, 0, 900, 1, 0, 1000);
            INSERT INTO sale_events VALUES ('2026-01-03T00:00:00Z', 'bio', 50, 0, 50, 0, 1, NULL);
            INSERT INTO sample_points VALUES (1, 4, '$Codex_Ent_Tussocks_01_Name;', 'g', 1, 1.0, 2.0,
                                              '2026-01-04T00:00:00Z');""")
        old.commit()
        old.close()
        db = ed_outrider.open_db(path)   # parser_version differs: the journal data is reset
        try:
            self.assertEqual(ed_outrider.meta_get(db, "parser_version"), ed_outrider.PARSER_VERSION)
            self.assertEqual(db.execute("SELECT count(*) FROM sale_events").fetchone()[0], 0)   # rebuilt by the replay
            self.assertEqual([tuple(r) for r in db.execute("SELECT * FROM sale_estimates")],
                             [("2026-01-02T00:00:00Z", "carto", 1000)])
            self.assertEqual(db.execute("SELECT lat, lon FROM sample_points").fetchall()[0][:], (1.0, 2.0))
            cols = [r["name"] for r in db.execute("PRAGMA table_info(sale_events)")]
            self.assertIn("source", cols)
            self.assertNotIn("estimate", cols)
            self.assertNotIn("sale_events_old", [r[0] for r in db.execute("SELECT name FROM sqlite_master")])
            # the replay: the sale comes back and the ledger shows its estimate again
            import types
            j = ed_outrider.Journals(db)
            state = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
            live = os.path.join(self.tmp, "live")
            self.write(live, "Journal.2026-01-01T000000.01.log", [
                {"timestamp": "2026-01-01T00:00:00Z", "event": "FSDJump", "StarSystem": "S1", "SystemAddress": 1,
                 "StarPos": [0, 0, 0]},
                self.page("2026-01-02T00:00:00Z", 900, ["S1"])])
            j.scan_dir(live)
            db.commit()
            trip = state.ledger()["trips"][0]
            self.assertEqual((trip["paid_carto"], trip["estimate"]), (900, 1000))
            db.close()
            db = ed_outrider.open_db(path, rescan=True)   # --rescan: the same again
            self.assertEqual(db.execute("SELECT count(*) FROM sale_estimates").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM sample_points").fetchone()[0], 1)
        finally:
            db.close()

    def test_replayed_log_keeps_the_current_runs_points(self):   # F1: the Log that began the run is read again
        self.jump("2026-01-01T00:00:00Z", 1)
        self.j.status_json = {"live": True, "ts": "2026-01-01T00:10:00Z", "lat": 0.0, "lon": 0.0}
        org = lambda ts, kind: {"event": "ScanOrganic", "timestamp": ts, "SystemAddress": 1, "Body": 4, "ScanType": kind,
                                "Genus": "$Codex_Ent_Tussocks_Genus_Name;", "Genus_Localised": "Tussock",
                                "Species": "$Codex_Ent_Tussocks_01_Name;", "Species_Localised": "Tussock Pennata"}
        self.j.handle(org("2026-01-01T00:10:00Z", "Log"))
        self.j.status_json = {"live": True, "ts": "2026-01-01T00:12:00Z", "lat": 0.0, "lon": 0.02}
        self.j.handle(org("2026-01-01T00:12:00Z", "Sample"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM sample_points").fetchone()[0], 2)
        self.j.status_json = {"live": True, "ts": "2026-01-02T00:00:00Z", "lat": 5.0, "lon": 5.0}   # a day later
        self.j.handle(org("2026-01-01T00:10:00Z", "Log"))       # the re-read replays the run's Log...
        self.j.handle(org("2026-01-01T00:12:00Z", "Sample"))
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT n, lat, lon FROM sample_points ORDER BY n")],
                         [(1, 0.0, 0.0), (2, 0.0, 0.02)])          # ...and the positions stay
        self.j.handle(org("2026-01-01T00:13:00Z", "Log"))       # a new run of it: the old points go
        self.assertEqual(self.db.execute("SELECT count(*) FROM sample_points").fetchone()[0], 0)

    # ---- F13: every page of a 'Sell all' counts, once ----
    def test_same_second_sale_pages_all_count_once(self):   # F13
        live = os.path.join(self.tmp, "live")
        path = self.write(live, "Journal.2026-01-01T000000.01.log", [
            {"timestamp": "2026-01-01T00:00:00Z", "event": "FSDJump", "StarSystem": "S1", "SystemAddress": 1,
             "StarPos": [0, 0, 0]},
            self.page("2026-01-02T10:00:00Z", 40_000_000, ["S1"]),
            self.page("2026-01-02T10:00:00Z", 38_000_000, ["S2"]),
            self.page("2026-01-02T10:00:00Z", 35_000_000, ["S3"])])
        self.j.scan_dir(live)
        self.db.commit()
        L = self.state.ledger()
        self.assertEqual(L["trips"][0]["paid_carto"], 113_000_000)
        # the same lines handled again (a twin folder, a retried tick): the same keys, nothing doubles
        self.j.offsets.clear()
        self.j.twins.clear()
        self.j.read_file(path)
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT count(*) FROM sale_events").fetchone()[0], 3)
        self.assertEqual(self.state.ledger()["trips"][0]["paid_carto"], 113_000_000)
        # a copy of the file in another folder is the same journal: the same keys again
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        import shutil
        shutil.copy(path, other)
        self.j.offsets.clear()
        self.j.twins.clear()
        self.j.scan_dir(other)
        self.assertEqual(self.db.execute("SELECT count(*) FROM sale_events").fetchone()[0], 3)

    def test_estimate_recorded_for_a_live_sale(self):   # F1: written to sale_estimates, one per sale moment
        now = ed_outrider.iso_ts(time.time() - 60)
        live = os.path.join(self.tmp, "live")
        self.write(live, "Journal.2026-01-01T000000.01.log", [self.page(now, 10, ["A"]), self.page(now, 20, ["B"])])
        self.j.scan_dir(live)
        self.state.unsold_log = [(ed_outrider.iso_ts(time.time() - 120), {"carto": {"estimated_payout": 31}, "bio": {"estimated_value": 0}})]
        self.state.note_sale_estimates()
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT kind, estimate FROM sale_estimates")], [("carto", 31)])
        self.assertEqual(self.state.ledger()["trips"][0]["estimate"], 31)

    # ---- F15 / F49 / F16: sold or already-lost data is not lost again ----
    def star_and_record(self, ts, id64):
        self.j.handle(scan(ts, f"S{id64}", id64, 0, f"S{id64}", star=True)[2])

    def test_sold_then_rescanned_is_not_lost(self):   # F15, F16
        self.jump("2026-01-01T00:00:00Z", 1)
        self.star_and_record("2026-01-01T00:01:00Z", 1)
        self.j.handle(self.page("2026-01-02T00:00:00Z", 100, ["S1"]))
        self.jump("2026-01-03T00:00:00Z", 1)                   # a return visit: the arrival scan again
        self.star_and_record("2026-01-03T00:01:00Z", 1)
        self.j.handle({"event": "Died", "timestamp": "2026-01-04T00:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-04T00:00:00Z", "Option": "rebuy"})
        self.db.commit()
        loss = self.state.ship_losses()[0]
        self.assertEqual((loss["bodies"], loss["value"], loss["firsts"]), (0, 0, 0))
        self.assertEqual(self.state.top_finds()[0]["state"], "sold")

    def test_map_lost_at_an_earlier_loss_is_not_lost_again(self):   # F49
        self.jump("2026-01-01T00:00:00Z", 1)
        self.star_and_record("2026-01-01T00:01:00Z", 1)
        self.j.handle(scan("2026-01-01T00:02:00Z", "S1", 1, 1, "S1 1")[2])
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:03:00Z", "SystemAddress": 1, "BodyID": 1,
                       "BodyName": "S1 1"})
        for ts in ("2026-01-02T00:00:00Z", "2026-01-04T00:00:00Z"):
            self.j.handle({"event": "Died", "timestamp": ts})
            self.j.handle({"event": "Resurrect", "timestamp": ts, "Option": "rebuy"})
            if ts.startswith("2026-01-02"):
                self.j.handle(scan("2026-01-03T00:00:00Z", "S1", 1, 1, "S1 1")[2])   # rescanned, not mapped again
        self.db.commit()
        rec = json.loads(self.db.execute("SELECT record FROM own_bodies WHERE body_id = 1").fetchone()[0])
        body = dict(rec["ed"], first_discovered=True, first_mapped=True)
        second = self.state.ship_losses()[1]
        self.assertEqual(second["bodies"], 1)
        self.assertEqual(second["value"], outrider.unsold.body_value(body, False, False, True))   # not as mapped

    # ---- F46 / F19 / F50: sessions ----
    def test_rescan_of_own_unsold_discovery_is_not_a_new_first(self):   # F46
        self.jump("2026-01-01T00:00:00Z", 1)
        self.star_and_record("2026-01-01T00:01:00Z", 1)
        self.jump("2026-01-05T00:00:00Z", 1)
        self.star_and_record("2026-01-05T00:01:00Z", 1)             # still reads as undiscovered: not sold yet
        self.assertEqual(self.state.range_counts("2026-01-05T00:00:00Z", "~")["firsts"], 0)
        self.assertEqual(self.state.range_counts("", "2026-01-02T00:00:00Z")["firsts"], 1)

    def test_session_window_starts_at_login(self):   # F19
        self.jump("2026-01-01T00:00:00Z", 1)
        self.jump("2026-01-01T01:00:00Z", 2, 10)
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T00:00:00Z", "Commander": "J", "Credits": 1})
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-02T00:10:00Z", "SystemAddress": 2, "BodyID": 3,
                       "BodyName": "S2 3"})                         # mapped after logging in, before the first jump
        self.jump("2026-01-02T01:00:00Z", 3, 20)
        rows = self.state.history(3650 * 3)["sessions"]
        self.assertEqual([(s["start"], s["from"], s["mapped"]) for s in rows],
                         [("2026-01-02T01:00:00Z", "2026-01-02T00:00:00Z", 1),
                          ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 0)])

    def test_a_login_with_no_jump_is_its_own_session(self):   # F31
        self.jump("2026-01-01T10:00:00Z", 1)
        self.jump("2026-01-01T11:00:00Z", 2, 10)
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T14:00:00Z", "Commander": "J", "Credits": 1})
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T14:10:00Z", "SystemAddress": 2, "BodyID": 3,
                       "BodyName": "S2 3"})                         # a Rhino evening: mapped, no jump
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T14:40:00Z", "Commander": "J", "Credits": 1})   # a relog
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T08:00:00Z", "Commander": "J", "Credits": 1})   # crashed,
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T09:00:00Z", "Commander": "J", "Credits": 1})   # back in
        self.jump("2026-01-02T09:30:00Z", 3, 20)
        rows = self.state.history(3650 * 3)["sessions"]
        self.assertEqual([(s["start"], s["end"], s["from"], s["jumps"], s["mapped"]) for s in rows],
                         [("2026-01-02T09:30:00Z", "2026-01-02T09:30:00Z", "2026-01-02T08:00:00Z", 1, 0),
                          ("2026-01-01T14:00:00Z", "2026-01-01T14:40:00Z", "2026-01-01T14:00:00Z", 0, 1),
                          ("2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z", "2026-01-01T10:00:00Z", 2, 0)])
        self.assertEqual(rows[1]["systems"][0]["name"], "S2")   # where you were
        self.assertEqual(self.state.history(3650 * 3)["all_time"]["mapped"], 1)

    def test_session_gaps_in_utc(self):   # F50: 1.5 h across the UK clocks going back is one session
        old = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/London"
        time.tzset()
        try:
            self.jump("2026-10-25T00:15:00Z", 1)
            self.jump("2026-10-25T01:45:00Z", 2, 10)
            self.assertEqual(len(self.state.sessions("")), 1)
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()

    # ---- backups: G2.1 / G2.2 / G2.3 / G2.4 / F53 ----
    def test_backup_names_and_rotation(self):   # G2.1, G2.3
        self.assertRegex(ed_outrider.backup_name("/a/ed_outrider.sqlite", 0), r"^outrider-ed_outrider-19700101-000000Z\.zip$")
        d = os.path.join(self.tmp, "b")
        os.makedirs(d)
        for f in ("outrider-x-20260101-000000Z.zip", "outrider-x-20260102-000000Z.zip", "outrider-x-20250101-000000Z.zip"):
            open(os.path.join(d, f), "w").close()
        # the zip just written sorts first (a clock set back): it is kept all the same
        self.assertEqual(ed_outrider.rotate_backups(d, 1, "/q/x.sqlite", current=os.path.join(d, "outrider-x-20250101-000000Z.zip")), 1)
        self.assertEqual(os.listdir(d), ["outrider-x-20250101-000000Z.zip"])

    def test_archive_shared_with_another_instance(self):
        """Codex F8: two instances archive the same journal into one folder, one from a lagging mirror. The shorter copy
        never replaces the longer one another instance put there meanwhile, and one's failure never removes the
        other's staging file."""
        import shutil
        live, dest = os.path.join(self.tmp, "live"), os.path.join(self.tmp, "arch")
        name = "Journal.2026-01-01T000000.01.log"
        self.write(live, name, [{"event": "Fileheader"}, {"event": "LoadGame"}])           # the lagging mirror's
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(live, name), "rb") as f:
            whole = f.read()
        with open(os.path.join(dest, name), "wb") as f:
            f.write(whole.split(b"\n")[0] + b"\n")                                       # archived earlier: its first line
        longer = whole + b'{"event":"Location"}\r\n' * 20                              # the fuller source's
        real = shutil.copy2

        def copy2(src, dst):   # the other instance finishes its fuller copy while this one copies
            real(src, dst)
            with open(os.path.join(dest, name), "wb") as f:
                f.write(longer)
        with unittest.mock.patch.object(shutil, "copy2", copy2):
            copied, _, failed = ed_outrider.archive_journals([live], dest)
        self.assertEqual((copied, failed), (0, []))
        with open(os.path.join(dest, name), "rb") as f:
            self.assertEqual(f.read(), longer)
        self.assertEqual(os.listdir(dest), [name])                                        # no staging file left
        # the other instance's staging file (the old shared name) is not this one's to remove on a failure
        os.remove(os.path.join(dest, name))
        theirs = os.path.join(dest, name + ".part")
        open(theirs, "w").close()

        def fails(src, dst):
            raise OSError(28, "No space left on device")
        with unittest.mock.patch.object(shutil, "copy2", fails):
            ed_outrider.archive_journals([live], dest)
        self.assertTrue(os.path.exists(theirs))

    def test_archive_failure_is_reported_and_rotation_still_runs(self):   # G2.2
        import shutil
        live, dest = os.path.join(self.tmp, "live"), os.path.join(self.tmp, "arch")
        self.write(live, "Journal.2026-01-01T000000.01.log", [{"event": "Fileheader"}])
        self.write(live, "Journal.2026-01-02T000000.01.log", [{"event": "Fileheader"}])
        real = shutil.copy2

        def copy2(src, dst):
            if "01-01" in src:
                with open(dst, "w") as f:
                    f.write("half")                      # a .part left by the failure
                raise OSError(28, "No space left on device")
            return real(src, dst)
        with unittest.mock.patch.object(shutil, "copy2", copy2):
            copied, _, failed = ed_outrider.archive_journals([live], dest)
        self.assertEqual((copied, [f for f, _ in failed]), (1, ["Journal.2026-01-01T000000.01.log"]))
        self.assertEqual(os.listdir(dest), ["Journal.2026-01-02T000000.01.log"])      # no .part left behind
        # make_backup: the zip is good, so the rotation runs and the failure is reported, not raised
        out = os.path.join(self.tmp, "backups")
        os.makedirs(out)
        dbp = os.path.join(self.tmp, "x.sqlite")
        sqlite3.connect(dbp).close()
        for i in range(1, 4):
            open(os.path.join(out, f"outrider-x-2020010{i}-000000Z.zip"), "w").close()
        self.state.db_path = dbp
        with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]), \
                unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 2), \
                unittest.mock.patch.object(shutil, "copy2", copy2):
            res = self.state.make_backup()
        # a warning, not an error: the zip was written, so it is the latest backup (amber on the page, not red)
        self.assertIn("not archived", res["warning"])
        self.assertNotIn("error", res)
        self.assertEqual(res["kept"], 2)
        self.assertEqual(len([f for f in os.listdir(out) if f.endswith(".zip")]), 2)

    def test_backup_records_warning_apart_from_error(self):   # the Data tile: amber for a warning, red for an error
        import asyncio, contextlib, io
        results = [{"path": "/b/1.zip", "size": 1, "kept": 1, "journals_to": None, "copied": 0,
                    "warning": "1 journal not archived (J.log: disk full)"},
                   {"path": "/b/2.zip", "size": 1, "kept": 2, "journals_to": None, "copied": 1}]
        with unittest.mock.patch.object(self.state, "make_backup", side_effect=results + [OSError("disk full")]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(self.state.backup())
            first = ed_outrider.meta_get(self.state.db, "last_backup")
            asyncio.run(self.state.backup())
            second = ed_outrider.meta_get(self.state.db, "last_backup")
            asyncio.run(self.state.backup())
            third = ed_outrider.meta_get(self.state.db, "last_backup")
        self.assertEqual((first["path"], "error" in first), ("/b/1.zip", False))
        self.assertIn("not archived", first["warning"])
        self.assertNotIn("warning", second)                     # the next good backup clears it
        self.assertEqual((third["path"], third["ts"]), (second["path"], second["ts"]))   # a failure keeps the last good one
        self.assertIn("disk full", third["error"])

    def test_archive_never_replaces_with_a_smaller_or_different_file(self):   # G2.1
        live, dest = os.path.join(self.tmp, "live"), os.path.join(self.tmp, "arch")
        os.makedirs(dest)
        self.write(live, "Journal.2026-01-01T000000.01.log", [{"event": "Fileheader", "part": 1}])
        self.write(live, "Journal.2026-01-02T000000.01.log", [{"event": "Fileheader", "who": "me"}, {"event": "More"}])
        self.write(dest, "Journal.2026-01-01T000000.01.log", [{"event": "Fileheader", "part": 1}, {"event": "Longer"}])
        self.write(dest, "Journal.2026-01-02T000000.01.log", [{"event": "Fileheader", "who": "someone else"}])
        self.assertEqual(ed_outrider.archive_journals([live], dest)[0], 0)
        with open(os.path.join(dest, "Journal.2026-01-02T000000.01.log")) as f:
            self.assertIn("someone else", f.read())

    def test_stale_browser_default_key_is_dropped_not_the_document(self):   # G2.4
        import contextlib, io
        path = os.path.join(self.tmp, "browser_defaults.json")
        with open(path, "w") as f:
            json.dump({"version": 1, "settings": {"sound": False, "someRetiredKey": 1}, "saved": "2026-01-01T00:00:00Z"}, f)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            doc = ed_outrider.read_browser_defaults(path)
        self.assertEqual(doc["settings"], {"sound": False})
        self.assertIn("someRetiredKey", err.getvalue())
        self.assertEqual(ed_outrider.check_browser_defaults({"version": 1, "settings": {"someRetiredKey": 1}})[0], None)

    def test_browser_defaults_saved_must_be_a_string(self):   # F64
        path = os.path.join(self.tmp, "browser_defaults.json")
        for saved, want in ((1727700000, None), (True, None), ({"a": 1}, None), ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")):
            with open(path, "w") as f:
                json.dump({"version": 1, "settings": {"sound": False}, "saved": saved}, f)
            doc = ed_outrider.read_browser_defaults(path)
            self.assertEqual((doc["settings"], doc["saved"]), ({"sound": False}, want))

    def test_shutdown_waits_for_a_running_backup(self):   # F53
        import asyncio, contextlib, io
        done = []

        async def go(delay, wait):
            async def backup():
                await asyncio.sleep(delay)
                done.append(delay)
            self.state.backup_task = asyncio.create_task(backup())
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                await ed_outrider.finish_backup(self.state, wait)
            return self.state.backup_task.cancelled()
        self.assertFalse(asyncio.run(go(0.05, 5)))
        self.assertEqual(done, [0.05])
        # past the wait: still waited for, and its result kept (the thread would hold the exit anyway: F35)
        self.assertFalse(asyncio.run(go(0.3, 0.05)))
        self.assertEqual(done, [0.05, 0.3])

    def test_shutdown_cancels_every_background_task(self):
        """Review 2026-10-08 #7: a survey or trade plot (riches_task, up to 10 minutes) was not among the tasks
        cancelled at shutdown, so it ran on into the closed Spansh session and database."""
        import types
        names = ("refresh_task", "target_task", "unsold_task", "seller_task", "carrier_task", "honk_test_task",
                 "highway_task", "riches_task", "autotarget_task", "autotarget_test_task", "reported_task")
        for n in names:
            setattr(self.state, n, n)
        self.state.searcher = types.SimpleNamespace(task="searcher")
        self.assertEqual(set(self.state.background_tasks()), set(names) | {"searcher"})

    def test_closing_right_after_the_game_still_backs_up(self):   # F32
        import asyncio, contextlib, io
        started = []

        async def go():
            async def backup():
                started.append("ran")
            self.state.start_backup = lambda auto=False: (started.append(auto),
                                                          setattr(self.state, "backup_task", asyncio.create_task(backup())))
            self.state.backup_task = None
            self.state.backup_wait_task = asyncio.create_task(asyncio.sleep(10))   # the quit backup's 10 s wait
            await asyncio.sleep(0)
            with contextlib.redirect_stdout(io.StringIO()):
                await ed_outrider.finish_backup(self.state, 5)
        asyncio.run(go())
        self.assertEqual(started, [True, "ran"])

    # ---- config: F42 / F40 ----
    def test_config_section_that_is_not_a_table(self):   # F42
        import contextlib, io
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            st = ed_outrider.settings_from({"journals": ["D:/Saved Games"], "server": 5, "defaults": "x",
                                            "spansh": [], "autohonk": True}, args, None, (["/det"], []))
        self.assertEqual((st["live"], st["port"]), (["/det"], 8025))
        self.assertIn("journals = ", err.getvalue())

    def test_write_config_comments_legacy_out_with_live(self):   # F40
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], ["/mnt/win/Saved Games"]))
        self.assertEqual(st["live"], [])
        back = tomllib.loads(ed_outrider.config_text(st))["journals"]
        self.assertEqual(back, {})                          # both left to auto-detection

    # ---- journal reading: F12 / F11 / F14 / F6 / F17 ----
    def test_journal_folder_with_brackets(self):   # F12
        d = os.path.join(self.tmp, "Games [SSD]")
        self.write(d, "Journal.2026-01-01T000000.01.log", [
            {"timestamp": "2026-01-01T00:00:00Z", "event": "FSDJump", "StarSystem": "S1", "SystemAddress": 1, "StarPos": [0, 0, 0]}])
        self.assertEqual(self.j.scan_dir(d), 1)
        self.assertEqual(self.j.pos["id64"], 1)
        self.assertEqual(len(outrider.log.journal_files([d])), 1)
        self.assertEqual(len(outrider.unsold.journal_files([d])), 1)

    def test_one_file_two_paths_read_once(self):   # F11
        a = os.path.join(self.tmp, "a")
        path = self.write(a, "Journal.2026-01-01T000000.01.log", [{"event": "Fileheader"}])
        b = os.path.join(self.tmp, "b")
        os.symlink(a, b)
        self.assertEqual(ed_outrider.unique_dirs([a, b, a + "/"]), [a])
        other = os.path.join(b, os.path.basename(path))
        self.j.offsets = {path: 100, other: 50}
        self.j.twins = {os.path.basename(path): path}
        self.assertEqual(self.j.start_offset(other), 100)   # its own offset lags the twin's: the further one

    def test_vehicle_fuel_is_not_the_ships(self):
        """In the SRV (the Nomad reports as one) or a fighter, Status.json's Fuel and Cargo are the vehicle's: the
        ship's last reading stays, marked away; back aboard, the ship's figures return."""
        d = os.path.join(self.tmp, "veh"); os.makedirs(d)
        def status(ts, flags, main, cargo):
            with open(os.path.join(d, "Status.json"), "w") as f:
                json.dump({"timestamp": ts, "event": "Status", "Flags": flags, "Flags2": 0,
                           "Fuel": {"FuelMain": main, "FuelReservoir": 0.5}, "Cargo": cargo}, f)
            self.j.read_status(d)
        status("2026-10-01T00:00:00Z", 1 << 24, 158.9, 0)
        status("2026-10-01T00:01:00Z", ed_outrider.FLAG_IN_SRV, 0.0, 12)       # the Nomad / Rhino
        st = self.j.status_json
        self.assertEqual((st["fuel_main"], st["cargo"], st["away"], st["vehicle_fuel"]), (158.9, 0, "SRV", 0.5))
        status("2026-10-01T00:02:00Z", ed_outrider.FLAG_IN_FIGHTER, 0.0, 0)
        self.assertEqual((self.j.status_json["fuel_main"], self.j.status_json["away"]), (158.9, "fighter"))
        status("2026-10-01T00:03:00Z", 1 << 24, 150.2, 3)                     # back aboard
        st = self.j.status_json
        self.assertEqual((st["fuel_main"], st["cargo"], st["away"]), (150.2, 3, None))
        self.assertIsNone(st["vehicle_fuel"])

    def test_first_reading_on_foot_or_in_the_srv(self):   # F9: the game runs; the ship's tank is simply not read yet
        state = ed_outrider.State(self.db, self.j, None, 25)
        self.j.status_json = {"fuel_main": None, "live": True, "flags2": 9, "ts": "2026-10-03T00:00:00Z"}   # on foot
        self.assertEqual(state.fuel_summary(), {"live": True, "main": None, "ts": "2026-10-03T00:00:00Z", "in_ship": False,
                                                "vehicle": None})
        self.j.status_json = {"fuel_main": None, "away": "SRV", "vehicle_fuel": 0.43, "live": True, "ts": "x"}
        self.j.vehicle = {"srv_type": "mev_rhino", "label": "SRV Rhino", "ts": "x"}
        self.assertEqual(state.fuel_summary()["vehicle"], {"label": "SRV Rhino", "fuel": 0.43})
        self.j.status_json = {"fuel_main": None, "live": False, "ts": "x"}    # the game closed: as before
        self.assertEqual(state.fuel_summary(), {"live": False})

    def test_simulate_shows_the_last_values_as_live(self):
        """--simulate (screenshots): with the game closed the panels read as live, with the last jump's fuel, while
        the real Status.json, which every guard reads, still says the game is not running."""
        state = ed_outrider.State(self.db, self.j, None, 25)
        self.j.status_json = {"live": False, "ts": "2026-10-02T00:00:00Z"}
        self.j.ship = {"fuel_main": 160}
        self.j.fuel_hist = [[40.0, 2.0, 150.5, 0], [42.0, 2.2, 148.3, 0]]
        self.assertFalse(state.fuel_summary()["live"])                      # off: the truth
        self.assertFalse(state.payload()["freshness"]["live"])
        state.simulate = True
        f = state.fuel_summary()
        self.assertEqual((f["live"], f["main"], f["pct"], f["in_ship"], f["vehicle"]), (True, 148.3, 93, True, None))
        self.assertTrue(state.payload()["freshness"]["live"])
        self.assertTrue(state.payload()["freshness"]["simulated"])   # the page then shows an old journal as no fault
        self.assertFalse(self.j.status_json["live"])                         # the guards' view is untouched
        self.j.fuel_hist = []                                                # no jump yet: a full tank
        self.assertEqual(state.fuel_summary()["main"], 160)
        self.j.status_json = {"live": False, "fuel_main": 99.0, "ts": "2026-10-02T00:00:00Z"}   # a reading this run
        self.assertEqual(state.fuel_summary()["main"], 99.0)
        self.j.status_json = {"live": True, "fuel_main": 12.0, "flags": 1 << 24}           # the game running wins
        self.assertEqual(state.shown_status(), self.j.status_json)

    def test_simulate_turns_the_keyboard_off(self):
        """--simulate never presses a key: run() makes the virtual keyboard unavailable before anything opens it, so
        auto honk, its test, auto-target and its test are all refused."""
        h = ed_outrider.simulate_keyboard_off(outrider_honk().Honker("auto", 6.0, []))
        self.assertFalse(h.available)
        self.assertFalse(h.open())
        self.assertFalse(h.open("target"))
        state = ed_outrider.State(self.db, self.j, None, 25)
        state.honker = h
        body, status = state.start_honk_test()
        self.assertEqual((status, body["error"]), (400, "off (--simulate)"))
        st = {"copilot": {"enabled": True, "device": "x"}, "highway": {"clipboard": True, "autotarget": True}, "port": 1}
        sim = ed_outrider.simulate_settings(st)
        self.assertEqual((sim["copilot"]["enabled"], sim["highway"]["clipboard"], sim["port"]), (False, False, 1))
        self.assertTrue(st["copilot"]["enabled"])   # a copy: the settings passed in are unchanged
        import subprocess   # the flag is on the command line (--help prints and exits before anything starts)
        out = subprocess.run([sys.executable, ed_outrider.__file__, "--help"], capture_output=True, text=True, timeout=60)
        self.assertIn("--simulate", out.stdout)

    def test_vehicle_damage_is_not_the_ships_hull(self):   # F25: the SRV's and the Nomad's lines have no Fighter key
        self.j.handle({"event": "HullDamage", "timestamp": "2026-10-01T00:00:00Z", "Health": 0.94, "PlayerPilot": True, "Fighter": False})
        self.j.handle({"event": "LaunchVessel", "timestamp": "2026-10-01T00:01:00Z", "VesselType": "lander01",
                       "VesselType_Localised": "Nomad", "ID": 49, "PlayerControlled": True})
        self.j.handle({"event": "HullDamage", "timestamp": "2026-10-01T00:02:00Z", "Health": 0.480464, "PlayerPilot": True})
        self.assertEqual(self.j.hull["pct"], 94)
        self.j.handle({"event": "DockSRV", "timestamp": "2026-10-01T00:03:00Z", "SRVType": "lander01", "ID": 49})
        self.j.handle({"event": "LaunchSRV", "timestamp": "2026-10-01T00:04:00Z", "SRVType": "mev_rhino", "ID": 51})
        self.j.handle({"event": "HullDamage", "timestamp": "2026-10-01T00:05:00Z", "Health": 0.2, "PlayerPilot": True})
        self.assertEqual(self.j.hull["pct"], 94)
        self.j.handle({"event": "DockSRV", "timestamp": "2026-10-01T00:06:00Z", "SRVType": "mev_rhino", "ID": 51})
        self.j.handle({"event": "HullDamage", "timestamp": "2026-10-01T00:07:00Z", "Health": 0.5, "PlayerPilot": True, "Fighter": False})
        self.assertEqual(self.j.hull["pct"], 50)

    def test_nomad_launch_names_the_vehicle(self):
        self.j.handle({"event": "LaunchVessel", "timestamp": "2026-10-01T00:00:00Z", "VesselType": "lander01",
                       "VesselType_Localised": "Nomad", "ID": 49, "PlayerControlled": True})
        self.assertEqual((self.j.vehicle["srv_type"], self.j.vehicle["label"]), ("lander01", "Nomad"))
        self.j.handle({"event": "DockSRV", "timestamp": "2026-10-01T00:05:00Z", "SRVType": "lander01", "ID": 49})
        self.assertIsNone(self.j.vehicle)

    def test_stale_navroute_and_status_in_a_second_folder(self):   # F14
        new, old = os.path.join(self.tmp, "new"), os.path.join(self.tmp, "old")
        hop = lambda i: {"StarSystem": f"S{i}", "SystemAddress": i, "StarPos": [i, 0, 0], "StarClass": "K"}
        for d, ts, n in ((new, "2026-09-01T00:00:00Z", 3), (old, "2026-01-01T00:00:00Z", 5)):
            os.makedirs(d)
            with open(os.path.join(d, "NavRoute.json"), "w") as f:
                json.dump({"timestamp": ts, "event": "NavRoute", "Route": [hop(i) for i in range(1, n + 1)]}, f)
            with open(os.path.join(d, "Status.json"), "w") as f:
                json.dump({"timestamp": ts, "event": "Status", "Flags": 1, "Fuel": {"FuelMain": n}}, f)
        for d in (new, old):
            self.j.read_navroute(d)
            self.j.read_status(d)
        self.assertEqual(len(ed_outrider.meta_get(self.db, "route")["hops"]), 3)
        self.assertEqual(self.j.status_json["fuel_main"], 3)
        self.j.handle({"event": "NavRouteClear", "timestamp": "2026-09-02T00:00:00Z"})
        self.j.read_navroute(new)                         # the file from before the clear: stays cleared
        self.assertIsNone(ed_outrider.meta_get(self.db, "route"))

    def test_failed_tick_reads_the_route_again_and_keeps_status_moments(self):   # F6, F17
        import contextlib, io
        d = os.path.join(self.tmp, "live")
        os.makedirs(d)
        with open(os.path.join(d, "NavRoute.json"), "w") as f:
            json.dump({"timestamp": "2026-01-01T00:00:00Z", "event": "NavRoute",
                       "Route": [{"StarSystem": "S1", "SystemAddress": 1, "StarPos": [0, 0, 0], "StarClass": "K"}]}, f)
        later = ("maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold", "maybe_locate_carrier",
                 "maybe_find_sellers", "maybe_backup_on_quit")
        watched, mtimes = [], {}
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]))
            for name in later:
                stack.enter_context(unittest.mock.patch.object(self.state, name, lambda: None))
            stack.enter_context(unittest.mock.patch.object(self.state, "watch_status", lambda now: watched.append(now)))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            with unittest.mock.patch.object(self.j, "settle_carrier", side_effect=sqlite3.OperationalError("database is locked")):
                self.state.tick(mtimes)
            self.assertTrue(self.state.tail_error)
            self.assertEqual(mtimes, {})                          # F6: the route will be read again
            self.assertEqual(watched, [])                         # F17: nothing consumed before the commit failed
            self.assertIsNone(ed_outrider.meta_get(self.db, "route"))
            self.state.tick(mtimes)
        self.assertIsNone(self.state.tail_error)
        self.assertEqual(len(ed_outrider.meta_get(self.db, "route")["hops"]), 1)
        self.assertEqual(len(watched), 1)

    # ---- server: F54 / F45 ----
    def test_port_80_extras_get_the_bare_name(self):   # F54
        h = ed_outrider.allowed_hosts("127.0.0.1", 80, ["mypc", "Box.lan:80"], own=lambda: set())
        self.assertTrue({"mypc", "mypc:80", "box.lan", "box.lan:80"} <= h)
        # on another port a configured name is answered bare too (an HTTPS proxy on the LAN: review R7); the
        # built-in names still only with the port
        h = ed_outrider.allowed_hosts("127.0.0.1", 8025, ["mypc"], own=lambda: set())
        self.assertEqual(("mypc" in h, "localhost" in h), (True, False))

    def test_spansh_cache_version(self):   # F45: gravity_raw and body_count need a refetch of older entries
        self.assertGreaterEqual(ed_outrider.CACHE_VERSION, 13)


class BatchBState(unittest.TestCase):
    """Third review, batch B: server state, call-outs and the helper modules."""

    CANDS = CANDS

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.jump("2026-01-01T00:00:00Z", 1, 0)

    jump, honk, planet, moments, organic = (voice_jump, voice_honk, voice_planet,
                                            voice_moments, voice_organic)

    # ---- G3.1 / G3.2: the next stop ----
    def test_bookmark_is_located(self):   # G3.1
        self.db.execute("INSERT INTO bookmarks VALUES (99, 'Far Away', 400, 0, 0, 'note', '2026-01-01T00:00:00Z')")
        self.assertEqual(self.state.locate(99), ("Far Away", 400, 0, 0))
        self.assertTrue(self.state.set_next_stop(99))
        self.assertEqual(ed_outrider.meta_get(self.db, "next_stop")["name"], "Far Away")
        self.assertTrue(self.state.set_bookmark(99, "new note"))

    def test_rescan_keeps_a_next_stop_visited_before(self):   # G3.2
        import tempfile
        self.jump("2026-01-01T01:00:00Z", 2, 10)
        self.jump("2026-01-01T02:00:00Z", 3, 20)
        self.assertTrue(self.state.set_next_stop(2))
        self.assertEqual(ed_outrider.meta_get(self.db, "next_stop")["set_ts"], "2026-01-01T02:00:00Z")
        with tempfile.TemporaryDirectory() as d:   # a re-read replays the earlier visit to S2: it stays
            path = os.path.join(d, "t.sqlite")
            db = ed_outrider.open_db(path)
            ed_outrider.meta_set(db, "pos", {"id64": 3, "ts": "2026-01-01T02:00:00Z"})
            ed_outrider.meta_set(db, "next_stop", {"id64": 2, "name": "S2", "x": 10, "y": 0, "z": 0})   # from before set_ts
            ed_outrider.meta_set(db, "plan_first", {"id64": "3", "body": "S3 1"})   # S30's first stop, from before set_ts too
            db.commit()
            db.close()
            db = ed_outrider.open_db(path, rescan=True)
            j = ed_outrider.Journals(db)
            for ts, i in (("2026-01-01T00:00:00Z", 1), ("2026-01-01T01:00:00Z", 2), ("2026-01-01T02:00:00Z", 3)):
                j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{i}", "SystemAddress": i, "StarPos": [i, 0, 0]})
            self.assertEqual(ed_outrider.meta_get(db, "next_stop")["id64"], 2)
            self.assertEqual(ed_outrider.meta_get(db, "plan_first")["body"], "S3 1")   # the re-read's older arrivals keep it
            j.handle({"event": "FSDJump", "timestamp": "2026-01-01T03:00:00Z", "StarSystem": "S2", "SystemAddress": 2,
                      "StarPos": [10, 0, 0]})
            self.assertIsNone(ed_outrider.meta_get(db, "next_stop"))   # arriving after it was chosen clears it
            self.assertIsNone(ed_outrider.meta_get(db, "plan_first"))   # and leaving S3 forgets its first stop
            db.close()

    # ---- G3.3 / F8: the Nearby refresh ----
    def refresh(self, sphere, bad=None, retry=False):
        import asyncio, types

        async def fail(*a):
            raise OSError("Spansh down")

        async def dump(id64, updated, base):
            return base
        self.state.spansh = types.SimpleNamespace(sphere=sphere, edsm_sphere=fail, cached=lambda i: (None, None),
                                                  store=lambda *a: None, full_records=dump)
        real = self.state.row

        def row(id64):
            if id64 == bad:
                raise ValueError("bad record")
            return real(id64)
        self.state.row = row
        self.state.center = self.j.pos
        asyncio.run(self.state._refresh(self.j.pos, retry))

    def test_a_retry_that_fails_again_sends_no_payload(self):
        """Network down: each retry failing at once changed nothing on the page, but bumped the payload twice (its
        "asking again" and the status back), so every open page redrew at every retry. A slow retry still says so."""
        import asyncio, contextlib, io
        from unittest import mock

        async def down(pos, r):
            raise OSError("Spansh down")
        with contextlib.redirect_stderr(io.StringIO()):
            self.refresh(down)
            self.assertEqual(self.state.status, "Spansh unavailable")
            v, rows = self.state.version, self.state.systems
            self.refresh(down, retry=True)
            self.assertEqual(self.state.version, v)                  # nothing changed: no payload
            self.assertEqual(self.state.systems, rows)
            self.assertEqual(self.state.status, "Spansh unavailable")

            async def slow(pos, r):   # a network that swallows the request: "asking again" shows while it waits
                await asyncio.sleep(0.05)
                seen.append((self.state.version, self.state.status))
                raise OSError("Spansh down")
            seen = []
            with mock.patch.object(ed_outrider, "RETRY_SAY_S", 0.01):
                self.refresh(slow, retry=True)
            self.assertEqual(seen[0][0], v + 1)
            self.assertTrue(seen[0][1].startswith("asking Spansh again"))
            self.assertEqual(self.state.version, v + 2)              # and the status back afterwards
            self.assertEqual(self.state.status, "Spansh unavailable")

        async def found(pos, r):
            return [{"id64": 11, "name": "N11", "x": 1, "y": 0, "z": 0, "distance": 1, "bodies": []}]
        self.refresh(found, retry=True)                             # Spansh back: the new rows go out
        self.assertGreater(self.state.version, v + 2)
        self.assertEqual(self.state.status, "ok")
        self.assertIn(11, self.state.systems)

    def test_failed_search_drops_the_old_sphere_cut(self):   # G3.3
        async def down(pos, r):
            raise OSError("Spansh down")
        import contextlib, io
        self.state.sphere_cut = 11.8
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.refresh(down)
        self.assertIsNone(self.state.sphere_cut)
        # S42: the page's status is the short form, the error itself goes to the log
        self.assertEqual(self.state.status, "Spansh unavailable")
        self.assertIn("Spansh search failed (OSError: Spansh down)", err.getvalue())

    def test_one_bad_row_does_not_stop_the_refresh(self):   # F8
        import contextlib, io
        body = lambda s: [{"name": f"{s} A 1", "type": "Planet", "subtype": "Rocky body"}]

        async def found(pos, r):
            return [{"id64": i, "name": f"N{i}", "x": i, "y": 0, "z": 0, "distance": i, "bodies": body(f"N{i}")}
                    for i in (11, 12, 13)]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.refresh(found, bad=12)
        self.assertTrue({11, 13} <= set(self.state.systems))
        self.assertNotIn(12, self.state.systems)
        self.assertIn(12, self.state.row_failed)
        self.assertIn(12, self.state.value_dirty)       # tried again at the next tick
        self.assertIn("bad record", self.state.tail_error)
        self.assertEqual(err.getvalue().count("Traceback"), 1)

    # ---- F9 / F10: fuel and boost state ----
    def test_ship_swap_counts_jumps_from_the_swap(self):   # F9
        loadout = lambda ts, sid: {"event": "Loadout", "timestamp": ts, "Ship": "anaconda", "ShipID": sid, "MaxJumpRange": 50,
                                   "FuelCapacity": {"Main": 32, "Reserve": 1}, "Modules": []}
        self.j.handle(loadout("2026-01-01T00:00:30Z", 1))
        self.jump("2026-01-01T00:01:00Z", 2, 10)
        self.j.handle(loadout("2026-01-01T00:02:00Z", 2))
        self.assertEqual(self.j.last_scoop, "2026-01-01T00:02:00Z")
        n = self.db.execute("SELECT count(*) FROM jumps WHERE kind='FSDJump' AND ts > ?", (self.j.last_scoop,)).fetchone()[0]
        self.assertEqual(n, 0)

    def test_rebuy_drops_the_jet_cone_charge(self):   # F10
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-01-01T00:01:00Z", "BoostValue": 4.0})
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T00:02:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T00:03:00Z", "Option": "rebuy"})
        self.assertIsNone(self.j.boost)
        self.assertIsNone(ed_outrider.meta_get(self.db, "boost"))
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-01-01T00:04:00Z", "BoostValue": 4.0})
        self.j.handle({"event": "Location", "timestamp": "2026-01-01T00:05:00Z", "StarSystem": "S9", "SystemAddress": 9,
                       "StarPos": [90, 0, 0]})   # arrived without a jump: a respawn elsewhere
        self.assertIsNone(self.j.boost)

    # ---- F56: moments answer the long poll ----
    def test_new_moment_bumps(self):   # F56
        import contextlib
        later = ("maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold", "maybe_locate_carrier",
                 "maybe_find_sellers", "maybe_backup_on_quit", "watch_status")
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", ["/nonexistent-outrider-dir"]))
            for name in later:
                stack.enter_context(unittest.mock.patch.object(self.state, name, lambda *a: None))
            stack.enter_context(unittest.mock.patch.object(
                self.j, "scan_dir", lambda d, **kw: self.j.moment("supercharged", "2026-01-01T00:01:00Z", mult=4.0) and False))
            v = self.state.version
            self.state.tick({})
        self.assertGreater(self.state.version, v)

    def test_payload_carries_the_colony_distances(self):   # S1: shown before you land
        col = self.state.payload()["colony"]
        self.assertEqual((col["bacterium"], col["electricae"], col["tussock"]), (500, 1000, 200))

    def test_the_jump_line_waits_for_the_tunnel(self):   # S14
        now = time.time()
        ts = ed_outrider.iso_ts(now - 5)
        self.j.handle({"event": "StartJump", "timestamp": ts, "JumpType": "Hyperspace", "StarSystem": "Far", "SystemAddress": 77,
                       "StarClass": "K"})
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_FSD_CHARGING, "ts": ts}
        self.state.watch_status(now)                                 # the countdown: nothing yet
        kinds = lambda: [m["kind"] for m in self.j.moments]
        self.assertNotIn("hyperspace", kinds())
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_FSD_JUMP, "ts": ed_outrider.iso_ts(now)}
        self.state.watch_status(now)
        self.state.watch_status(now + 1)                             # still in it: once
        m = [x for x in self.j.moments if x["kind"] == "hyperspace"]
        self.assertEqual([(x["system"], x["charge"]) for x in m],
                         [("Far", next(x for x in self.j.moments if x["kind"] == "fsd_charge")["seq"])])
        # out and into the tunnel again with no new charge (supercruise): no second line
        self.j.status_json = {"live": True, "flags": 0, "ts": "x"}
        self.state.watch_status(now + 20)
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_FSD_JUMP, "ts": "y"}
        self.state.watch_status(now + 30)
        self.assertEqual(kinds().count("hyperspace"), 1)

    def test_a_failing_follow_up_does_not_starve_the_rest(self):   # S5
        import contextlib, io
        ran, follow = [], ("watch_status", "maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold",
                           "maybe_sale_left", "maybe_locate_carrier", "maybe_find_sellers", "maybe_backup_on_quit",
                           "highway_copy_next", "highway_heavy_check", "maybe_autotarget")

        def boom(*a):
            ran.append("heavy")
            raise KeyError("fuel_main")
        err = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", ["/nonexistent-outrider-dir"]))
            for name in follow:
                stack.enter_context(unittest.mock.patch.object(
                    self.state, name, boom if name == "highway_heavy_check" else (lambda n: lambda *a: ran.append(n))(name)))
            stack.enter_context(contextlib.redirect_stderr(err))
            self.state.tick({})
            self.state.tick({})
        self.assertEqual(ran.count("maybe_autotarget"), 2)              # after the one that raised, every tick
        self.assertEqual(self.state.tail_error, "highway_heavy_check: KeyError: 'fuel_main'")
        self.assertEqual(err.getvalue().count("Traceback"), 1)          # printed once, not every second

    # ---- F43 / F44 / F38 / F52: call-outs ----
    def test_login_on_foot_names_your_ship(self):   # F43
        self.j.ship = {"name": "Wanderer", "ship_id": 39}
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:05:00Z", "Commander": "X", "Ship": "ExplorationSuit_Class1",
                       "Ship_Localised": "Artemis Suit", "ShipID": 4293000001, "ShipName": ""})
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:06:00Z", "Commander": "X", "Ship": "TestBuggy",
                       "Ship_Localised": "SRV Scarab", "ShipID": 33})
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:07:00Z", "Commander": "X", "Ship": "Explorer_NX",
                       "Ship_Localised": "Caspian Explorer", "ShipID": 39, "ShipName": "Wanderer II"})
        self.assertEqual([m["ship"] for m in self.j.moments if m["kind"] == "game_start"], ["Wanderer", "Wanderer", "Wanderer II"])

    def test_login_in_the_nomad_names_your_ship(self):   # F26
        self.assertTrue(ed_outrider.not_a_ship("Lander01"))
        self.j.ship = {"name": "Wanderer", "ship_id": 39}
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:05:00Z", "Commander": "X", "Ship": "Lander01",
                       "Ship_Localised": "Nomad", "ShipID": 49, "ShipName": ""})
        self.assertEqual([m["ship"] for m in self.j.moments if m["kind"] == "game_start"], ["Wanderer"])

    def test_relog_then_honk_gives_no_second_briefing(self):   # F44
        self.jump("2026-01-01T00:10:00Z", 5, 30)
        self.honk("2026-01-01T00:10:05Z", 5, 3)
        self.j.handle({"event": "Location", "timestamp": "2026-01-01T00:20:00Z", "StarSystem": "S5", "SystemAddress": 5,
                       "StarPos": [30, 0, 0]})
        self.assertEqual(self.j.pos["ts"], "2026-01-01T00:10:00Z")   # still the arrival
        self.honk("2026-01-01T00:20:05Z", 5, 3)
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "arrival_brief"]), 1)

    def test_all_found_after_the_briefing_is_still_said(self):   # F38
        self.jump("2026-01-01T00:10:00Z", 5, 30)
        self.honk("2026-01-01T00:10:05Z", 5, 3, progress=1.0)
        self.assertFalse(self.moments("arrival_brief")[0]["all_found"])    # the page got it before the next line
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:10:06Z", "SystemName": "S5",
                       "SystemAddress": 5, "Count": 3})
        self.assertEqual([m["system"] for m in self.moments("fss_done")], ["5"])

    def test_briefing_after_a_honk_that_gave_up_late(self):   # F52
        now = time.time()
        self.jump(ed_outrider.iso_ts(now - 70), 7, 40)
        a = self.j.jump_arrival
        self.state._honk_done = (a, now - 1)             # the honk task waited ~70 s for the cockpit, then gave up
        self.state.maybe_brief(now)
        self.assertEqual([m["source"] for m in self.moments("arrival_brief")], ["spansh"])

    # ---- F5 / F2 / F18: facts ----
    def test_arrival_bio_counts_mapped_bodies_and_skips_done_species(self):   # F5
        self.sampling_body = voice_sampling_body.__get__(self)
        self.sampling_body()                              # A 4: DSS'd (so mapped), Stratum + Bacterium
        self.organic("2026-01-01T00:04:00Z", "Analyse", "Bacterium Aurasus", "Bacterium")
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            f = self.state.arrival_facts(1)
        self.assertEqual(f["bio"], {"body": "A 4", "value": 19_010_800})   # Stratum left, Bacterium done
        self.organic("2026-01-01T00:05:00Z", "Analyse", "Stratum Tectonicas", "Stratum")
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            self.assertIsNone(self.state.arrival_facts(1)["bio"])

    def test_a_composition_scans_codex_entry_names_the_species(self):
        """The author, 2026-10-23: a composition scan from the ship logged "Bacterium Vesicula - Red" in the codex, and
        the body's Bacterium still showed the guess (Aurasus) and its colours until a sample on foot. The codex entry on
        the body names the species: that, its value and its colour replace the guess, in Here and the leaving summary."""
        if not outrider.bio or not outrider.bio.species_by_name("Bacterium Vesicula"):
            self.skipTest("no bio_rules.json")
        voice_sampling_body(self)                                      # A 4: Stratum and Bacterium, no samples
        guess = lambda: {x["genus"]: x for x in next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == "A 4")["bio_guess"]}
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            self.assertEqual((guess()["Bacterium"]["best"], guess()["Bacterium"]["seen"]), ("Bacterium Aurasus", False))
            self.db.execute("INSERT INTO codex (ts, entry_id, name, category, subcategory, system, body_id) VALUES "
                            "('2026-01-01T00:03:00Z', 2310901, 'Bacterium Vesicula - Red', '$Codex_Category_Biology;', "
                            "'$Codex_SubCategory_Organic_Structures;', 1, 4)")
            self.db.commit()
            g = guess()["Bacterium"]
            v = outrider.bio.species_value("Bacterium Vesicula")
            self.assertEqual((g["best"], g["seen"], g["variants"], g["value"]), ("Bacterium Vesicula", True, ["Bacterium Vesicula - Red"], v))
            self.assertEqual(guess()["Stratum"]["best"], "Stratum Tectonicas")   # another genus keeps its guess
            pot = next(p for p in self.state.leaving_summary(1)["bio_pending"] if p["body"] == "A 4")["potential"]
            self.assertEqual(pot, v + next(c["value"] for c in self.CANDS if c["genus"] == "Stratum"))

    def test_codex_new_per_variant_in_the_summaries(self):   # P11
        region = outrider.bio.region_name(0, 0, 0)
        if not region:
            self.skipTest("no bio_rules.json")
        voice_sampling_body(self)
        for i, name in enumerate(("Stratum Tectonicas - Green", "Bacterium Aurasus - Teal")):
            self.db.execute("INSERT INTO codex (ts, entry_id, name, region) VALUES ('t', ?, ?, ?)", (i, name, region))
        self.db.commit()
        cands = lambda colour: [dict(self.CANDS[0], variants=[f"Stratum Tectonicas - {colour}"]), dict(self.CANDS[1], variants=[])]
        new_of = lambda: {p["body"]: p["codex_new"] for p in self.state.leaving_summary(1)["bio_pending"]}
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=cands("Teal")):
            self.assertEqual(new_of(), {"A 4": True})                  # Teal Stratum is new here, Green is logged
            g = {x["genus"]: x for x in next(b for b in self.state.system_detail(1)["bodies"] if b["name"] == "A 4")["bio_guess"]}
            self.assertEqual((g["Stratum"]["variant"], g["Stratum"]["codex_new"]), ("Stratum Tectonicas - Teal", True))
            self.assertEqual((g["Bacterium"]["variants"], g["Bacterium"]["codex_new"]), ([], False))   # species logged
            # the journal logged Green on the first sample: that, not the guess, is what the codex gets
            self.j.handle({"event": "ScanOrganic", "timestamp": "2026-01-01T00:04:00Z", "ScanType": "Log", "SystemAddress": 1,
                           "Body": 4, "Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum",
                           "Species": "$Codex_Ent_Stratum_07_Name;", "Species_Localised": "Stratum Tectonicas",
                           "Variant": "$Codex_Ent_Stratum_07_M_Name;", "Variant_Localised": "Stratum Tectonicas - Green"})
            self.db.commit()
            self.assertEqual(new_of(), {"A 4": False})
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=cands("Green")):
            self.assertEqual(new_of(), {"A 4": False})

    def test_leaving_skips_a_finished_body_without_dss(self):   # F2
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", Landable=True, PlanetClass="Rocky body", MassEM=0.2)
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyName": "S1 A 4",
                       "BodyID": 4, "Signals": [{"Type": ed_outrider.BIO, "Count": 2}]})
        self.organic("2026-01-01T00:04:00Z", "Analyse", "Bacterium Aurasus", "Bacterium")
        self.db.commit()
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            pend = self.state.leaving_summary(1)["bio_pending"]
            self.assertEqual([(p["body"], p["signals"], p["potential"]) for p in pend], [("A 4", 1, 19_010_800)])
            self.organic("2026-01-01T00:05:00Z", "Analyse", "Stratum Tectonicas", "Stratum")
            self.assertEqual(self.state.leaving_summary(1)["bio_pending"], [])

    def test_return_visit_is_visited(self):   # F18
        self.jump("2026-01-01T01:00:00Z", 2, 10)
        self.jump("2026-01-01T02:00:00Z", 1, 0)
        rows = self.db.execute("SELECT id64, verdict FROM jumps ORDER BY ts").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(1, None), (2, None), (1, "visited")])
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 28)

    # ---- G1.2 / F36: speech ----
    def test_long_lines_are_cut_at_a_boundary(self):   # G1.2
        import outrider.tts
        line = "Leaving with unfinished work: bio on C 2 (Osseus, Tussock), up to 3.1M. " * 20
        cut = outrider.tts.clip_text(line)
        self.assertLessEqual(len(cut), outrider.tts.SAY_MAX)
        self.assertTrue(cut.endswith("up to 3.1M."))
        self.assertEqual(outrider.tts.clip_text("short   line "), "short line")
        words = outrider.tts.clip_text("word " * 400, 50)
        self.assertTrue(words.endswith("word") and len(words) <= 50)
        self.assertEqual(outrider.tts.clip_text("one, two " * 10, 30)[-1], ".")

    def test_failed_switch_keeps_the_old_voice_and_is_not_saved(self):   # F36
        import contextlib, io, tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            for v in ("en_GB-a-low", "en_GB-b-low"):
                for ext in (".onnx", ".onnx.json"):
                    open(os.path.join(d, v + ext), "w").close()
            switched = []
            sp = outrider.tts.Speaker("en_GB-a-low", "en_GB-b-low", voices_dir=d, on_switched=switched.append)
            sp.PiperVoice = unittest.mock.Mock()
            sp.PiperVoice.load = lambda path: (_ for _ in ()).throw(RuntimeError("damaged")) if "b-low" in path else path
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                sp._prepare(None)                         # start-up: not a choice to remember
                self.assertEqual(switched, [])
                sp._prepare("en_GB-b-low")
            self.assertEqual(sp.voice_name, "en_GB-a-low")
            self.assertTrue(sp.status.startswith("could not switch to en_GB-b-low"))
            self.assertTrue(sp.status.endswith("still using en_GB-a-low"))
            self.assertEqual(switched, [])
        self.state.remember_voice("en_GB-a-low")
        self.db.rollback()
        self.assertEqual(ed_outrider.meta_get(self.db, "voice_choice"), "en_GB-a-low")

    # ---- F20 / F67 / F68: outrider.bio ----
    @unittest.skipUnless(outrider.bio.available(), "bio_rules.json not downloaded")
    def test_star_rule_waits_for_every_star(self):   # F20
        body = {"class": "Rocky body", "atmosphere": "Hot thin Sulphur dioxide", "gravity": 0.3, "temperature": 420}
        system = dict(BIO_M_SYSTEM)
        names = lambda s: [x["name"] for x in outrider.bio.predict(body, s)]
        self.assertIn("Prasinum Bioluminescent Anemone", names(dict(system, complete=False)))   # a companion may be the one
        self.assertNotIn("Prasinum Bioluminescent Anemone", names(dict(system, complete=True)))

    def test_species_value_of_nothing(self):   # F67
        self.assertIsNone(outrider.bio.species_value(None))

    @unittest.skipUnless(outrider.bio.available(), "bio_rules.json not downloaded")
    def test_backtest_skips_a_corrupt_line(self):   # F68
        import contextlib, io, tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Journal.2026-01-01T000000.01.log"), "w") as f:
                f.write('{"timestamp":"2026-01-01T00:00:00Z","event":"Scan","BodyName":"X 1","Planet\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                outrider.bio.backtest([d])
        self.assertNotIn("Traceback", out.getvalue())

    # ---- F37: outrider.honk ----
    def test_joystick_modifier_slot_is_skipped(self):   # F37
        import tempfile
        import outrider.honk
        with tempfile.TemporaryDirectory() as root:
            journals, binds = make_controls(self, root)
            with open(os.path.join(binds, "My X56.4.2.binds"), "w") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" ?><Root PresetName="My X56"><PrimaryFire>'
                        '<Primary Device="Keyboard" Key="Key_K"><Modifier Device="231D0200" Key="Joy_3" /></Primary>'
                        '<Secondary Device="Keyboard" Key="Key_Space" /></PrimaryFire></Root>')
            self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_SPACE"])
            with open(os.path.join(binds, "My X56.4.2.binds"), "w") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" ?><Root PresetName="My X56"><PrimaryFire>'
                        '<Primary Device="Keyboard" Key="Key_K"><Modifier Device="231D0200" Key="Joy_3" /></Primary>'
                        '</PrimaryFire></Root>')
            keys, what = outrider.honk.primary_fire_binding([journals])
        self.assertIsNone(keys)
        self.assertIn("joystick modifier", what)


class FableServer(unittest.TestCase):
    """Fourth review (Fable audit), batch 2: server state, call-outs and robustness."""

    CANDS = CANDS

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.jump("2026-01-01T00:00:00Z", 1, 0)

    jump, honk, planet, moments, organic, sampling_body = (
        voice_jump, voice_honk, voice_planet, voice_moments, voice_organic,
        voice_sampling_body)

    def sell(self, ts, systems):
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": ts, "TotalEarnings": 1000, "BaseValue": 1000,
                       "Bonus": 0, "Discovered": [{"SystemName": s, "NumBodies": 1} for s in systems]})

    def test_old_relog_read_late_is_still_a_relog(self):
        """Review 2026-10-08 #9: a legacy folder imported after the live journals: its login Location in the system
        that session quit in was judged against today's position, so it counted a visit and broke the flown path."""
        loc = lambda ts, i: self.j.handle({"event": "Location", "timestamp": ts, "StarSystem": f"S{i}", "SystemAddress": i,
                                           "StarPos": [float(i), 0, 0]})
        self.jump("2026-03-01T00:00:00Z", 50, 10)                         # today: live data first
        self.jump("2025-06-01T10:00:00Z", 7, 20)                          # then the old folder: a jump to 7
        loc("2025-06-02T09:00:00Z", 7)                                    # the next day's login there: a relog
        loc("2025-06-03T09:00:00Z", 8)                                    # a login elsewhere: an arrival
        visits = lambda i: self.db.execute("SELECT count FROM visits WHERE id64=?", (i,)).fetchone()[0]
        kinds = [r[0] for r in self.db.execute("SELECT kind FROM jumps WHERE id64 IN (7, 8) ORDER BY ts")]
        self.assertEqual((visits(7), visits(8)), (1, 1))
        self.assertEqual(kinds, ["FSDJump", "Location"])
        self.assertEqual(self.j.pos["id64"], 50)                          # today's position untouched

    # ---- F5: the first jump of a session starts where you logged in ----
    def test_first_jump_counts_its_light_years(self):   # F5
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T10:00:00Z", "Commander": "X"})
        self.j.handle({"event": "Location", "timestamp": "2026-01-02T10:00:12Z", "StarSystem": "S1", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})                          # a relog: no jumps row
        for i in range(3):
            self.jump(f"2026-01-02T10:0{i + 1}:00Z", 2 + i, 40 * (i + 1))
        st = self.state.span_stats("2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z")
        self.assertEqual((st["jumps"], st["ly"]), (3, 120.0))
        latest = self.state.sessions("")[0]                            # two sessions: day 1's arrival, then day 2
        self.assertEqual((latest["jumps"], latest["ly"]), (3, 120.0))
        self.assertEqual(self.state.sessions("2026-01-02T00:00:00Z")[0]["ly"], 120.0)
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-02T11:00:00Z"})
        self.db.commit()
        self.assertEqual(self.state.last_session()["ly"], 120.0)
        self.assertEqual(self.moments("game_exit")[-1]["session"]["ly"], 120.0)

    # ---- F21: a launch that never loaded a commander ends no session ----
    def test_menu_only_launch_keeps_the_last_session(self):   # F21
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T09:00:00Z", "Commander": "X"})
        for i in range(3):
            self.jump(f"2026-01-01T09:0{i + 1}:00Z", 2 + i, 10 * (i + 1))
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T12:00:00Z"})
        self.db.commit()
        first = self.state.last_session()
        self.assertEqual((first["start"], first["end"], first["jumps"]), ("2026-01-01T09:00:00Z", "2026-01-01T12:00:00Z", 3))
        self.assertIsNotNone(self.moments("game_exit")[-1]["session"])
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T18:03:00Z"})   # quit from the main menu
        self.db.commit()
        self.assertEqual(self.state.last_session()["end"], "2026-01-01T12:00:00Z")
        self.assertIsNone(self.moments("game_exit")[-1]["session"])                # no recap said again
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T09:00:00Z", "Commander": "X"})
        self.jump("2026-01-02T09:01:00Z", 9, 90)
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-02T10:00:00Z"})
        self.db.commit()
        self.assertEqual(self.state.last_session()["start"], "2026-01-02T09:00:00Z")   # a real session again

    # ---- F4: "Repair Basic" is the SRV's repair ----
    def test_srv_repair_leaves_the_ship_hull(self):   # F4
        self.j.handle({"timestamp": "2026-01-01T00:00:30Z", "event": "HullDamage", "Health": 0.62, "PlayerPilot": True, "Fighter": False})
        self.j.handle({"event": "Materials", "timestamp": "2026-01-01T00:00:40Z", "Raw": [{"Name": "iron", "Count": 9},
                       {"Name": "nickel", "Count": 9}], "Manufactured": [], "Encoded": []})
        self.j.handle({"timestamp": "2026-01-01T00:01:00Z", "event": "Synthesis", "Name": "Repair Basic",
                       "Materials": [{"Name": "iron", "Count": 2}, {"Name": "nickel", "Count": 1}]})
        self.assertEqual(self.j.hull["pct"], 62)
        self.assertNotIn("repairs", self.state.materials_summary())    # no "basic repairs can be synthesised"
        self.assertNotIn("Repair basic", outrider.materials.SYNTH)

    # ---- F6: an Apex shuttle or another commander's ship ----
    def test_taxi_and_multicrew_are_not_your_ship(self):   # F6
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-01-01T00:00:30Z", "BoostValue": 4.0})
        hist = list(self.j.fuel_hist)
        self.j.jump_arrival = None
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:01:00Z", "StarSystem": "S2", "SystemAddress": 2,
                       "StarPos": [20, 0, 0], "Taxi": True, "Multicrew": False, "FuelUsed": 0.3, "JumpDist": 20})
        self.assertEqual(self.j.fuel_hist, hist)                         # not a pace sample for your ship
        self.assertIsNone(self.j.jump_arrival)                           # no auto honk in a taxi
        self.assertIsNotNone(self.j.boost)                               # your ship's charge is still there
        self.assertEqual(self.j.pos["id64"], 2)                          # but you are there
        self.assertEqual(self.db.execute("SELECT count(*) FROM jumps WHERE id64 = 2").fetchone()[0], 1)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:02:00Z", "StarSystem": "S3", "SystemAddress": 3,
                       "StarPos": [40, 0, 0], "Multicrew": True, "FuelUsed": 2.0, "JumpDist": 20})
        self.assertIsNone(self.j.jump_arrival)
        self.j.handle({"event": "Docked", "timestamp": "2026-01-01T00:03:00Z", "StationName": "Port", "StationType": "Coriolis",
                       "MarketID": 5, "StarSystem": "S3", "Taxi": True, "StationServices": ["exploration"]})
        self.assertIsNone(self.j.docked)                                 # no "docked, N cr to sell"
        self.j.handle({"event": "Docked", "timestamp": "2026-01-01T00:04:00Z", "StationName": "Port", "StationType": "Coriolis",
                       "MarketID": 5, "StarSystem": "S3", "Taxi": False, "StationServices": ["exploration"]})
        self.assertEqual(self.j.docked["station"], "Port")
        self.j.handle({"event": "Undocked", "timestamp": "2026-01-01T00:05:00Z", "StationName": "Port", "Taxi": True})
        self.assertIsNone(self.j.docked)                                 # you left the station, in the shuttle
        self.assertEqual(self.moments("undocked"), [])                   # but no undock alert
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:06:00Z", "StarSystem": "S4", "SystemAddress": 4,
                       "StarPos": [60, 0, 0], "Taxi": False, "Multicrew": False, "FuelUsed": 2.0, "JumpDist": 20})
        self.assertEqual(self.j.jump_arrival["id64"], 4)                 # your own jumps as before
        self.assertIsNone(self.j.boost)

    # ---- F10 / F51: when a rescan or remap is sold data ----
    def first_body(self, ts, name="S1 A 1"):
        ev = scan(ts, "S1", 1, 5, name)[2]
        self.j.handle(ev)

    def mapped(self, ts):
        self.j.handle({"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": 1, "BodyName": "S1 A 1", "BodyID": 5})

    def test_remap_after_a_sale_is_sold(self):   # F10
        self.first_body("2026-01-01T00:01:00Z")
        self.mapped("2026-01-01T00:02:00Z")
        self.sell("2026-01-01T01:00:00Z", ["S1"])
        self.mapped("2026-01-01T02:00:00Z")                                # a second DSS on a return visit
        f = ed_outrider.own_firsts(self.db, 1, "S1")
        self.assertEqual((f["mapped_by"]["sold"], f["mapped_by"]["unsold"]), (1, 0))
        row = self.db.execute("SELECT ts, first_ts FROM own_mapped").fetchone()
        self.assertEqual(tuple(row), ("2026-01-01T02:00:00Z", "2026-01-01T00:02:00Z"))

    def test_first_map_after_a_scan_sale_is_unsold(self):   # F10: the first map, not the first scan
        self.first_body("2026-01-01T00:01:00Z")
        self.sell("2026-01-01T01:00:00Z", ["S1"])
        self.mapped("2026-01-01T02:00:00Z")
        f = ed_outrider.own_firsts(self.db, 1, "S1")
        self.assertEqual(f["mapped_by"]["unsold"], 1)

    def test_sale_after_a_loss_did_not_buy_the_lost_scan(self):   # F51
        for e in death("2026-01-01T00:30:00Z"):
            self.j.handle(e[2])
        self.sell("2026-01-01T01:00:00Z", ["S1"])
        judge = ed_outrider.pickup_judge(self.db, "S1")
        # first scanned 00:10, ship lost 00:30, a sale naming S1 (other bodies) 01:00, rescanned 02:00
        self.assertEqual(judge("2026-01-01T02:00:00Z", "2026-01-01T00:10:00Z")[0], "unsold")
        self.assertEqual(judge("2026-01-01T02:00:00Z", "2026-01-01T00:40:00Z")[0], "sold")   # no loss in between

    # ---- F14: the approach briefing knows what you already sampled ----
    def test_approach_skips_finished_species(self):   # F14
        self.sampling_body()
        self.organic("2026-01-01T00:02:30Z", "Analyse", "Stratum Tectonicas", "Stratum")
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X"})   # a later session
        self.j.handle({"event": "ApproachBody", "timestamp": "2026-01-01T01:05:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            a = self.moments("approach")[-1]
        self.assertEqual((a["genera"], a["signals"], a["bio_value"]), (["Bacterium"], 1, 1_000_000))

    def test_approach_options_leave_out_a_sampled_genus(self):   # F14: no DSS
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", Landable=True, PlanetClass="Rocky body", MassEM=0.2)
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyName": "S1 A 4",
                       "BodyID": 4, "Signals": [{"Type": ed_outrider.BIO, "Count": 2}]})
        self.organic("2026-01-01T00:03:00Z", "Log", "Stratum Tectonicas", "Stratum")
        self.j.handle({"event": "ApproachBody", "timestamp": "2026-01-01T00:05:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            a = self.moments("approach")[-1]
        self.assertNotIn("Stratum", a["bio_options"]["genera"])

    # ---- F31: a run under way on a body with no DSS keeps its unidentified signals ----
    def test_leaving_keeps_unidentified_signals_during_a_run(self):   # F31
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", Landable=True, PlanetClass="Rocky body", MassEM=0.2)
        self.j.handle({"event": "FSSBodySignals", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyName": "S1 A 4",
                       "BodyID": 4, "Signals": [{"Type": ed_outrider.BIO, "Count": 3}]})
        self.organic("2026-01-01T00:03:00Z", "Log", "Stratum Tectonicas", "Stratum")
        self.db.commit()
        with unittest.mock.patch.object(outrider.bio, "predict", return_value=self.CANDS):
            p = self.state.leaving_summary(1)["bio_pending"]
        self.assertEqual([(b["genera"], b["signals"], b["partial"]) for b in p], [(None, 2, {"Stratum": 1})])
        self.assertEqual(p[0]["potential"], 19_010_800 + 16_777_215 + 3_703_200)   # the run plus the two best left

    # ---- F25 / G1.1: the arrival verdict ----
    def star(self, ts, id64, disc):
        self.j.handle(scan(ts, f"S{id64}", id64, 0, f"S{id64}", disc=disc, star=True)[2])

    def test_failed_lookup_is_no_announcement(self):   # F25
        self.jump("2026-01-01T00:01:00Z", 2, 10)
        self.state.target_verdicts[2] = "lookup failed"
        self.star("2026-01-01T00:01:05Z", 2, disc=False)
        self.state.reconcile_arrival()
        a = self.state.arrival
        self.assertEqual((a["announced"], a["undiscovered"], a["wrong"], a["sound"]), (None, True, False, None))

    def test_failed_verdict_is_reconciled_again(self):   # G1.1
        self.jump("2026-01-01T00:01:00Z", 2, 10)
        self.star("2026-01-01T00:01:05Z", 2, disc=True)
        self.state.target_verdicts[2] = "explored"
        with unittest.mock.patch.object(self.state, "fix_verdict", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                self.state.reconcile_arrival()
        self.assertIsNone(self.state.arrival)                           # not marked reconciled
        self.state.reconcile_arrival()                                  # the next tick
        self.assertEqual(self.state.arrival["verdict"], "complete")
        self.assertIsNotNone(self.state.arrival["streak"])

    # ---- F3: a cancelled charge during a flicker ----
    def test_scoop_end_after_a_cancelled_charge(self):   # F3
        W, S, C = ed_outrider.ScoopWatch, ed_outrider.FLAG_SCOOPING, ed_outrider.FLAG_FSD_CHARGING
        w, out = W(), []
        steps = [(t, S, 10 + t) for t in range(10)] + [(10, C, 20)] + [(t, S, 10 + t) for t in range(11, 20)] + \
            [(20, 0, 25), (23, 0, 25)]
        for t, flags, fuel in steps:
            r = w.update({"live": True, "flags": flags, "fuel_main": fuel}, 32.0, 1000 + t)
            if r:
                out.append(r)
        self.assertEqual(out, [{"pct": 78, "full": False}])

    # ---- F12: a malformed NavRoute.json ----
    def test_malformed_route_is_skipped(self):   # F12
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for route in ({"timestamp": "2026-01-01T00:05:00Z", "Route": [{"SystemAddress": 7, "StarPos": [1, 2, 3]}, "junk",
                                                                          {"StarSystem": "X", "SystemAddress": 8, "StarPos": 5}]},
                          ["not", "an", "object"], {"Route": 5}):
                with open(os.path.join(d, "NavRoute.json"), "w") as f:
                    json.dump(route, f)
                self.j.read_navroute(d)                                 # no exception
            self.assertEqual([tuple(r) for r in self.db.execute("SELECT id64, name FROM route_systems")], [(7, None)])

    # ---- F62: every moment the server holds ----
    def test_moments_payload_sends_the_whole_deque(self):   # F62
        for i in range(14):
            self.j.handle({"event": "Interdicted", "timestamp": f"2026-01-01T00:{i + 10:02d}:00Z", "Interdictor": "x"})
        self.assertEqual(len(self.moments("interdicted")), 14)

    # ---- F27: /api/say from another site ----
    def test_say_refused_cross_site(self):   # F27
        guard = guard_status
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path="/api/say"), 403)
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="same-site", path="/api/say"), 403)
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="same-origin", path="/api/say"), 200)   # the page
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", path="/api/say"), 200)                      # curl
        # R20: every other read under /api/ too, but the overlays' status, a page and its static files stay open
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path="/api/nearby"), 403)
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path="/api/status"), 200)
        self.assertEqual(guard(self, "GET", "127.0.0.1:8025", site="cross-site", path="/"), 200)

    # ---- F18 / F19: backups ----
    def test_backup_of_a_missing_database_fails(self):   # F18
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "backups")
            os.makedirs(out)
            with open(os.path.join(out, "outrider-x-20200101-000000Z.zip"), "w") as f:
                f.write("a good old one")
            self.state.db_path = os.path.join(d, "x.sqlite")            # moved away while the server runs
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 1):
                with self.assertRaises(sqlite3.OperationalError):
                    self.state.make_backup()
            self.assertFalse(os.path.exists(self.state.db_path))          # not created
            self.assertEqual(os.listdir(out), ["outrider-x-20200101-000000Z.zip"])   # nothing rotated out

    def test_rotation_failure_is_a_warning(self):   # F19
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "backups")
            os.makedirs(out)
            for i in (1, 2):
                with open(os.path.join(out, f"outrider-x-2020010{i}-000000Z.zip"), "w") as f:
                    f.write("old")
            dbp = os.path.join(d, "x.sqlite")
            sqlite3.connect(dbp).close()
            self.state.db_path = dbp
            real = os.remove

            def remove(p):
                if p.endswith(".zip"):
                    raise PermissionError(13, "Permission denied", p)
                return real(p)
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 1), \
                    unittest.mock.patch.object(ed_outrider.os, "remove", remove):
                res = self.state.make_backup()
            self.assertTrue(os.path.exists(res["path"]))
            self.assertEqual(res["kept"], 3)
            self.assertIn("old backups not rotated", res["warning"])
            self.assertIn("Permission denied", res["warning"])

    # ---- F16 / F17 / F15: the Spansh cache ----
    def spansh(self, dump):
        calls = []

        class FakeSpansh(ed_outrider.Spansh):
            async def lookup(self, id64, interactive=True):
                calls.append(id64)
                return dump

            async def sphere(self, pos, r):
                return [{"id64": 7, "name": "S7", "x": 1, "y": 0, "z": 0, "updated_at": "u1", "body_count": 2,
                         "bodies": [{"name": "S7 1", "type": "Planet", "subtype": "Icy body"}]}]
        sp = FakeSpansh(self.db)
        self.state.spansh = sp
        self.state.center = self.j.pos
        return sp, calls

    def test_dump_404_is_asked_again_later(self):   # F16
        import asyncio
        sp, calls = self.spansh(None)
        asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(calls, [7])
        asyncio.run(self.state._refresh(self.j.pos))                    # at once: the 404 is remembered
        self.assertEqual(calls, [7])
        self.db.execute("UPDATE spansh_systems SET fetched_ts = ? WHERE id64 = 7", (time.time() - ed_outrider.NO_DUMP_RETRY - 1,))
        asyncio.run(self.state._refresh(self.j.pos))                    # an hour on: asked again
        self.assertEqual(calls, [7, 7])

    def test_cached_system_without_bodies_is_not_refetched(self):   # F17
        import asyncio
        sp, calls = self.spansh({"system": {"bodyCount": 0, "bodies": [{"name": "S9 A Belt Cluster 1", "type": "Belt"}]}})
        self.db.execute("INSERT INTO visits VALUES (9, 'S9', 500, 0, 0, 't', 't', 1)")
        asyncio.run(self.state.ensure_records(9))
        asyncio.run(self.state.ensure_records(9))
        self.assertEqual(calls, [9])

    def test_on_demand_dump_is_current_for_the_refresh(self):   # F15
        import asyncio
        sp, calls = self.spansh({"system": {"bodyCount": 2, "bodies": [{"name": "S7 1", "type": "Planet", "subType": "Icy body",
                                                                          "bodyId": 1}]}})
        self.db.execute("INSERT INTO visits VALUES (7, 'S7', 1, 0, 0, 't', 't', 1)")
        asyncio.run(self.state.ensure_records(7))                       # a bookmark opened before it is in range
        self.assertEqual(calls, [7])
        asyncio.run(self.state._refresh(self.j.pos))                    # then the sphere: no second fetch
        self.assertEqual(calls, [7])

    def spansh2(self, dump, updated="u1", fail=None):
        """A fake Spansh whose sphere lists S7 (updated_at `updated`), or raises while fail["sphere"]; its dump lookup
        raises while fail["dump"]."""
        calls, fail = [], fail if fail is not None else {}

        class FakeSpansh(ed_outrider.Spansh):
            async def lookup(self, id64, interactive=True):
                calls.append(id64)
                if fail.get("dump"):
                    raise ed_outrider.ClientError("down")
                return dump

            async def sphere(self, pos, r):
                if fail.get("sphere"):
                    raise ed_outrider.ClientError("down")
                return [{"id64": 7, "name": "S7", "x": 1, "y": 0, "z": 0, "updated_at": fail.get("updated", updated),
                         "body_count": 2, "bodies": [{"name": "S7 1", "type": "Planet", "subtype": "Icy body"},
                                                     {"name": "S7 2", "type": "Planet", "subtype": "Icy body"}]}]

            async def edsm_sphere(self, pos, r):
                return []
        sp = FakeSpansh(self.db)
        self.state.spansh, self.state.center = sp, self.j.pos
        return sp, calls, fail

    DUMP2 = {"system": {"bodyCount": 2, "bodies": [{"name": "S7 1", "type": "Planet", "subType": "Icy body", "bodyId": 1},
                                                   {"name": "S7 2", "type": "Planet", "subType": "Icy body", "bodyId": 2}]}}

    def test_spansh_down_keeps_cached_spansh_records_as_spansh(self):   # F27
        import asyncio, contextlib, io
        sp, calls, fail = self.spansh2(self.DUMP2)
        asyncio.run(self.state._refresh(self.j.pos))
        sp.store(8, None, ed_outrider.base_from_edsm({"name": "S8", "coords": {"x": 2, "y": 0, "z": 0},
                                                       "primaryStar": {"type": "K", "isScoopable": True}}))
        self.db.commit()
        fail["sphere"] = True
        with contextlib.redirect_stderr(io.StringIO()):   # "Spansh search failed (...)": the log's line
            asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual((self.state.bases[7][0], self.state.systems[7]["in_spansh"]), ("spansh", True))
        self.assertEqual(self.state.bases[8][0], "edsm")   # an EDSM record stays EDSM's

    def test_failed_refetch_keeps_the_cached_dump(self):   # F28
        import asyncio
        sp, calls, fail = self.spansh2(self.DUMP2)
        asyncio.run(self.state._refresh(self.j.pos))
        full = self.state.bases[7][1]["records"]
        fail.update(updated="u2", dump=True)               # Spansh updated it, and its dump fails now
        asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(calls, [7, 7])
        self.assertEqual(self.state.bases[7][1]["records"], full)

    def test_no_dump_answer_gives_way_to_the_search(self):   # F29
        import asyncio
        sp, calls, fail = self.spansh2(self.DUMP2)
        sp.store(7, None, {"v": ed_outrider.CACHE_VERSION, "name": "S7", "x": 1, "y": 0, "z": 0, "body_count": None,
                           "records": [], "no_dump": True})   # Find asked an hour ago: no dump then
        self.db.commit()
        asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(calls, [])                          # not asked again within the hour
        self.assertEqual(len(self.state.bases[7][1]["records"]), 2)   # but the search's bodies show

    def test_refresh_shows_the_cache_while_it_asks(self):   # S6
        import asyncio
        sp, calls, fail = self.spansh2(self.DUMP2)
        asyncio.run(self.state._refresh(self.j.pos))         # S7 cached
        seen = []
        real = type(sp).sphere

        async def sphere(self_, pos, r):
            seen.append(sorted(self.state.systems))           # what the page has while Spansh is asked
            return await real(self_, pos, r)
        with unittest.mock.patch.object(type(sp), "sphere", sphere):
            asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(seen, [[7]])
        self.assertEqual(self.state.bases[7][0], "spansh")

    def test_edsm_sphere_is_cut_to_its_limit(self):   # F48
        import asyncio
        sent = []

        class Resp:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def raise_for_status(self):
                pass

            async def json(self):
                return []
        sp = ed_outrider.Spansh(self.db)
        sp.session = type("S", (), {"get": lambda self_, url, params=None: sent.append(params["radius"]) or Resp()})()
        asyncio.run(sp.edsm_sphere({"x": 0, "y": 0, "z": 0}, 150))
        asyncio.run(sp.edsm_sphere({"x": 0, "y": 0, "z": 0}, 40))
        self.assertEqual(sent, [100, 40])

    # ---- F23: History refetches on jumps and sales, not scans ----
    def test_history_version(self):   # F23
        self.state.apply_own_changes()
        v = self.state.history_version
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4")
        self.state.apply_own_changes()
        self.assertEqual(self.state.history_version, v)                 # a scan: History is not fetched again
        self.jump("2026-01-01T00:02:00Z", 2, 10)
        self.state.apply_own_changes()
        self.assertEqual(self.state.history_version, v + 1)
        self.sell("2026-01-01T00:03:00Z", ["S2"])
        self.state.apply_own_changes()
        self.assertEqual(self.state.history_version, v + 2)
        self.assertEqual(self.state.payload()["history_version"], v + 2)

    # ---- F24: a sale is stamped with the estimate made before it ----
    def test_sale_estimate_is_the_one_before_the_sale(self):   # F24
        now = time.time()
        pre = {"carto": {"estimated_payout": 40}, "bio": {"estimated_value": 7}}
        post = {"carto": {"estimated_payout": 0}, "bio": {"estimated_value": 0}}
        self.sell(ed_outrider.iso_ts(now - 600), ["S1"])              # read at start, before any estimate
        self.state.unsold_log = [(ed_outrider.iso_ts(now - 300), post)]
        self.state.note_sale_estimates()
        self.assertEqual(self.db.execute("SELECT count(*) FROM sale_estimates").fetchone()[0], 0)
        # a later bio sale does not stamp the old carto sale with today's post-sale figure
        self.state.unsold_log = [(ed_outrider.iso_ts(now - 300), pre), (ed_outrider.iso_ts(now - 5), post)]
        self.j.handle({"event": "SellOrganicData", "timestamp": ed_outrider.iso_ts(now - 60),
                       "BioData": [{"Species_Localised": "X", "Value": 7, "Bonus": 0}]})
        self.state.note_sale_estimates()
        rows = [tuple(r) for r in self.db.execute("SELECT kind, estimate FROM sale_estimates")]
        self.assertEqual(rows, [("bio", 7)])                            # the estimate finished before the sale


class SchemaUpgrade(unittest.TestCase):
    """A database made by the first public ED Outrider (tests/fixtures/schema_0046634.sql, frozen) opens with today's
    open_db: every table, column and index of a fresh database is there afterwards, and the cached Spansh systems get
    their x/y/z from the stored summary. Catches a new column that SCHEMA also indexes (the indexes are created before
    the missing columns are added) and a migration that breaks on old rows."""

    def test_oldest_database_upgrades_to_the_current_schema(self):
        import sqlite3
        import tempfile
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "fixtures", "schema_0046634.sql"), encoding="utf-8") as f:
            old_schema = f.read()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.sqlite")
            old = sqlite3.connect(path)
            old.executescript(old_schema)
            old.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts) VALUES (?, ?, ?, ?)",
                        (42, "2026-09-01 00:00:00", json.dumps({"name": "Old Sys", "x": 1.5, "y": -2.0, "z": 300.25}), 1.0))
            old.commit()
            old.close()
            db = ed_outrider.open_db(path)
            self.addCleanup(db.close)
            fresh = ed_outrider.open_db(":memory:")
            self.addCleanup(fresh.close)

            def tables(conn):
                return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

            def columns(conn, table):
                return {(r[1], (r[2] or "").upper()) for r in conn.execute(f"PRAGMA table_info({table})")}

            def indexes(conn):
                return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")}

            self.assertLessEqual(tables(fresh), tables(db))
            for t in sorted(tables(fresh)):
                missing = columns(fresh, t) - columns(db, t)
                self.assertFalse(missing, f"{t} lacks {sorted(missing)} after the upgrade")
            self.assertLessEqual(indexes(fresh), indexes(db))
            row = db.execute("SELECT x, y, z FROM spansh_systems WHERE id64 = 42").fetchone()
            self.assertEqual(tuple(row), (1.5, -2.0, 300.25))
            self.assertEqual(ed_outrider.meta_get(db, "parser_version"), ed_outrider.PARSER_VERSION)


class RereadNote(unittest.TestCase):
    """The start-up log says when and why every journal is read again (the author, 2026-10-11)."""

    def test_message_and_when_it_is_said(self):
        V = ed_outrider.PARSER_VERSION
        self.assertIn(V, ed_outrider.PARSER_CHANGES)   # every bump says why in the player's words
        m = ed_outrider.reread_message(V - 1)
        self.assertIn(f"the journal reader changed (version {V - 1} -> {V}: {ed_outrider.PARSER_CHANGES[V]})", m)
        self.assertIn("older change", ed_outrider.reread_message(V - 9))   # three reasons at most, the rest counted
        self.assertIn("a new database", ed_outrider.reread_message(None))
        self.assertIn("--rescan", ed_outrider.reread_message(V, rescan=True))
        self.assertIn("newer Outrider", ed_outrider.reread_message(V + 1))
        with tempfile.TemporaryDirectory() as d:
            path, said = os.path.join(d, "x.sqlite"), []
            ed_outrider.open_db(path, on_reread=said.append).close()
            ed_outrider.open_db(path, on_reread=said.append).close()          # up to date: nothing said
            self.assertEqual(len(said), 1)
            self.assertIn("a new database", said[0])
            db = ed_outrider.open_db(path)
            ed_outrider.meta_set(db, "parser_version", V - 1)
            db.commit(), db.close()
            ed_outrider.open_db(path, on_reread=said.append).close()
            self.assertIn(f"version {V - 1} -> {V}", said[-1])


class JournalsRegistry(unittest.TestCase):
    """AGENT_GUIDE's hand-kept rules as checks. (1) Journals state that reading journals changes must survive a failed
    tick: it is in checkpoint()/restore(), reloaded from the database by reload(), or listed below as safe on a retry,
    with the reason. (2) Every meta key Journals writes is cleared by RESET_JOURNAL_DATA (journal-derived) or listed
    below as kept through a re-read, with the reason. A new attribute or meta key fails here until it is placed."""

    # attribute -> why re-handling the same lines after a rolled-back tick leaves it right
    SAFE_ON_RETRY = {
        "arrival_scan": "the latest arrival-star Scan: overwritten, so the retry sets the same value",
        "unsold_touched": "a flag the tick clears once read: the retry reads the lines again and sets it again; a stray "
                          "True only re-runs the estimate once",
        "bad_json_said": "which files a not-JSON line was said of: a retry says nothing again, which is the point",
        "jump_arrival": "the latest hyperspace arrival: overwritten",
        "supercruise_entry": "the latest SupercruiseEntry (auto-target's danger wait): overwritten, newest wins",
        "last_all_found": "the latest FSSAllBodiesFound: overwritten",
        "last_honk": "the latest discovery scan: overwritten",
        "last_shutdown": "the latest Shutdown read: overwritten",
        "last_start_jump": "the latest hyperspace StartJump: overwritten",
        "target": "the latest FSDTarget (cleared on arrival): overwritten",
        "dirty": "systems whose scans changed: a set the retry adds the same systems to; consumed after the commit",
        "sales_changed": "a flag set by handling, consumed after the commit: setting it twice is harmless",
        "bio_sales_changed": "a flag set by handling, consumed after the commit",
        "materials_changed": "a flag set by handling, consumed after the commit",
        "cmdr_changed": "a flag set by handling, consumed after the commit",
        "commander_version": "a counter the Commander view's lines bump (the page's cue to ask again): a retry only bumps it more",
        "status_json": "the latest Status.json reading: live, re-read from the file, nothing in the database",
    }
    # meta key -> why it is NOT cleared by RESET_JOURNAL_DATA
    KEPT_THROUGH_REREAD = {
        "docking": "live-only: the pad a station gave you just now (#3), written for live lines only; a re-read writes "
                   "nothing to it",
        "docking_said": "live-only: grants counted this session for #12's green-lights cadence, live lines only",
        "highway": "live-only: the Highway route (DESIGN_NOTES), cannot be rebuilt from journals",
        "riches": "live-only: the Road to Riches route (Spansh's plot), cannot be rebuilt from journals",
        "carrier_trip": "live-only: the carrier trip (#19, Spansh's carrier router), cannot be rebuilt from journals",
        "next_stop": "live-only: the player's chosen next stop (stamp_next_stop keeps it through the re-read)",
        "plan_first": "live-only: the first stop picked where you are (S30); an arrival elsewhere after it clears it, "
                      "the re-read's older ones do not (stamp_next_stop)",
        "docked": "kept so the docked state is not blank while the re-read runs: older Docked/Undocked lines leave it "
                  "(fresh()), but an older Docked at your carrier still sets the carrier's services",
        "last_event_ts": "only ever raised (written when a line is newer), so replayed older lines leave it right",
        "last_play_ts": "rebuilt by the re-read (it ends on the newest playing event); kept meanwhile",
        "commodity_names": "a cache of the journal's commodity display names: a re-read only learns them again",
    }

    @staticmethod
    def _attrs(method):
        import inspect
        import re
        return set(re.findall(r"self\.(\w+)", inspect.getsource(method)))

    def test_changed_state_survives_a_failed_tick(self):
        import copy
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)

        def snap():
            out = {}
            for k, v in vars(j).items():
                try:
                    out[k] = copy.deepcopy(v)
                except Exception:   # noqa: BLE001 -- the database connection and the like: compared by identity
                    out[k] = ("<object>", id(v))
            return out
        before = snap()
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "journals")
        j.scan_dir(d)
        j.read_status(d)
        j.read_navroute(d)
        after = snap()
        changed = {k for k in after if k not in before or before[k] != after[k]}
        self.assertGreater(len(changed), 20)   # the fixtures exercise the reader
        covered = self._attrs(ed_outrider.Journals.checkpoint) | self._attrs(ed_outrider.Journals.reload) | set(self.SAFE_ON_RETRY)
        self.assertFalse(changed - covered,
                         "add these to checkpoint()/restore(), reload(), or SAFE_ON_RETRY with the reason")
        self.assertFalse(set(self.SAFE_ON_RETRY) - set(vars(j)), "SAFE_ON_RETRY names attributes that no longer exist")

    def test_meta_keys_are_reset_or_kept_on_purpose(self):
        import inspect
        import re
        src = inspect.getsource(ed_outrider.Journals)
        written = set(re.findall(r'meta_set\(\s*(?:self\.)?db,\s*"([^"]+)"', src))
        reset = set(re.findall(r"'([^']+)'", ed_outrider.RESET_JOURNAL_DATA))
        self.assertIn("legacy:%", reset)   # legacy:<folder> keys go by LIKE
        self.assertFalse(written - reset - set(self.KEPT_THROUGH_REREAD),
                         "add these to RESET_JOURNAL_DATA (journal-derived) or KEPT_THROUGH_REREAD with the reason")
        self.assertFalse(set(self.KEPT_THROUGH_REREAD) & reset, "a key cannot be both reset and kept")
        loaded = set(re.findall(r'meta_get\(db,\s*"([^"]+)"', inspect.getsource(ed_outrider.Journals.reload)))
        self.assertFalse(loaded - reset - set(self.KEPT_THROUGH_REREAD), "reload() reads a key neither reset nor kept")
