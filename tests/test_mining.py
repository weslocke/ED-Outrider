"""Mining (branch `mining`, project/PLAN-mining-2026-10-18.md): the limpet reminder on undocking (A). The page's side
(Settings → Mining's switch and its alerts table): tests/page_smoke.js ("mining alerts"). Fakes only."""
import time
import unittest

from support import ed_outrider  # also puts the repository root on sys.path


class LimpetReminder(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 120 + s)

    def loadout(self, s, *items, ship_id=7):
        self.j.handle({"event": "Loadout", "timestamp": self.at(s), "Ship": "python", "ShipID": ship_id, "ShipName": "Digger",
                       "ShipIdent": "DG-01", "CargoCapacity": 128, "MaxJumpRange": 20.0,
                       "Modules": [{"Slot": f"Slot0{i}", "Item": it} for i, it in enumerate(items)]})

    def cargo(self, s, **counts):
        self.j.handle({"event": "Cargo", "timestamp": self.at(s), "Vessel": "Ship", "Count": sum(counts.values()),
                       "Inventory": [{"Name": k, "Count": v, "Stolen": 0} for k, v in counts.items()]})

    def undock(self, s, **kw):
        self.j.handle(dict({"event": "Undocked", "timestamp": self.at(s), "StationName": "Hub", "StationType": "Coriolis",
                            "MarketID": 1, "Taxi": False, "Multicrew": False}, **kw))

    def said(self):
        return [m["what"] for m in self.j.moments if m["kind"] == "limpets"]

    def test_mining_ship_without_limpets(self):
        self.loadout(0, "int_refinery_size4_class5", "int_dronecontrol_collection_size5_class5")
        self.cargo(1, platinum=4)
        self.undock(2)
        self.assertEqual(self.said(), ["none"])
        # limpets aboard: nothing; a taxi or multicrew: nothing
        self.cargo(3, drones=20)
        self.undock(4)
        self.cargo(5)
        self.undock(6, Taxi=True)
        self.undock(7, Multicrew=True)
        self.assertEqual(self.said(), ["none"])

    def test_which_ships_count(self):
        """A refinery, a prospector controller, or a multi-limpet mining or universal one makes a mining ship; a ship
        without them (a collector alone included), or whose loadout or hold is not known, says nothing."""
        for i, item in enumerate(("int_refinery_size1_class1", "int_dronecontrol_prospector_size1_class4",
                                  "int_multidronecontrol_mining_size3_class3", "int_multidronecontrol_universal_size7_class5")):
            self.j.moments.clear()
            self.loadout(10 * i, item)
            self.cargo(10 * i + 1)
            self.undock(10 * i + 2)
            self.assertEqual(self.said(), ["none"], item)
        self.j.moments.clear()
        self.loadout(50, "int_fuelscoop_size5_class5", "int_dronecontrol_repair_size3_class5")
        self.cargo(51)
        self.undock(52)
        self.assertEqual(self.said(), [])
        # a collector controller alone is an explorer's (materials, salvage), not a miner's (the author's Caspian,
        # 2026-10-20: repair, collector and research controllers, warned "no limpets" on undocking)
        self.loadout(60, "int_dronecontrol_repair_size3_class2", "int_dronecontrol_collection_size1_class1",
                     "int_dronecontrol_unkvesselresearch", ship_id=39)
        self.cargo(61)
        self.undock(62)
        self.assertEqual(self.said(), [])

    def test_hold_counted_but_not_listed(self):
        """2026-10-19: the game's Cargo said 200 t aboard with no list and Cargo.json still empty: what is in the hold
        is not known, so no warning (the limpets themselves are now followed by BuyDrones, tests/test_cargo.py)."""
        self.loadout(0, "int_refinery_size4_class5")
        self.cargo(1)
        self.j.handle({"event": "Cargo", "timestamp": self.at(2), "Vessel": "Ship", "Count": 200})
        self.undock(3)
        self.assertEqual(self.said(), [])
        self.j.handle({"event": "Cargo", "timestamp": self.at(4), "Vessel": "Ship", "Count": 0})   # sold it all
        self.undock(5)
        self.assertEqual(self.said(), ["none"])

    def test_hold_or_ship_unknown_and_old_lines(self):
        j2 = ed_outrider.Journals(self.db)
        self.j = j2
        self.loadout(0, "int_refinery_size4_class5")
        self.undock(1)                      # no Cargo snapshot yet: the hold is not known
        self.assertEqual(self.said(), [])
        self.cargo(2)
        self.j.handle({"event": "Undocked", "timestamp": "2020-01-01T00:00:00Z", "StationName": "Hub", "MarketID": 1})
        self.assertEqual(self.said(), [])   # a journal caught up on: never said


class Stints(unittest.TestCase):
    """B: a drop into a ring until leaving it, with what was prospected and refined there; the hotspot from a live
    drop's Status.json Destination (none: the ring; unknown: an older journal)."""
    def setUp(self):
        import types
        import unittest.mock
        # a stint spans half an hour: every line in it is live here (an older journal's are years old)
        p = unittest.mock.patch.object(ed_outrider, "SHUTDOWN_LIVE_S", 10 ** 6)
        p.start()
        self.addCleanup(p.stop)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()
        self.j.handle({"event": "Loadout", "timestamp": self.at(0), "Ship": "python", "ShipID": 7, "ShipName": "Digger",
                       "ShipIdent": "DG", "CargoCapacity": 128, "MaxJumpRange": 20.0, "Modules": []})

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 3000 + s)

    def drop(self, s, ring="Sys 4 B Ring", body=18, dest=None, ts=None):
        self.j.status_json = {"live": True, "destination": dest}
        self.j.handle({"event": "SupercruiseExit", "timestamp": ts or self.at(s), "StarSystem": "Sys", "SystemAddress": 9,
                       "Body": ring, "BodyID": body, "BodyType": "PlanetaryRing"})

    def prospect(self, s, ts=None, remaining=100.0, lode=None, **mats):
        ev = {"event": "ProspectedAsteroid", "timestamp": ts or self.at(s), "Content": "$AsteroidMaterialContent_High;",
              "Remaining": remaining, "Materials": [{"Name": k, "Proportion": v} for k, v in mats.items()]}
        if lode:
            ev.update(MotherlodeMaterial=lode, MotherlodeMaterial_Localised="Void Opal" if lode == "Opal" else lode)
        self.j.handle(ev)

    def refine(self, s, kind, ts=None):
        self.j.handle({"event": "MiningRefined", "timestamp": ts or self.at(s), "Type": f"${kind}_name;",
                       "Type_Localised": {"opal": "Void Opal"}.get(kind, kind.title())})   # as the game names them

    def leave(self, s, ts=None):
        self.j.handle({"event": "SupercruiseEntry", "timestamp": ts or self.at(s), "StarSystem": "Sys", "SystemAddress": 9})

    def groups(self):
        return {(g["ring"], g["hotspot"]): g for g in self.state.mining_hotspots()["hotspots"]}

    def test_a_hotspot_stint(self):
        hot = {"System": 9, "Body": 18, "Name": "$SAA_RingHotspot:#type=$Alexandrite_name;;", "Name_Localised": "Alexandrite Hotspot"}
        self.drop(0, dest=hot)
        self.j.handle({"event": "LaunchDrone", "timestamp": self.at(5), "Type": "Prospector"})
        self.prospect(10, platinum=31.5, Painite=4.2)
        self.prospect(20, remaining=60.0, gold=40.0)
        self.prospect(30, lode="Opal", water=12.0)
        for i in range(6):
            self.refine(40 + i, "platinum")
        self.j.handle({"event": "AsteroidCracked", "timestamp": self.at(50), "Body": "Sys 4 B Ring"})
        self.refine(1800, "opal")
        self.leave(1900)
        g = self.groups()[("4 B Ring", "alexandrite")]
        self.assertEqual((g["stints"], g["tons"], g["refined"], g["motherlodes"], g["cracked"], g["seconds"], g["open"]),
                         (1, 7, {"platinum": 6, "opal": 1}, 1, 1, 1800, False))
        self.assertEqual(g["prospects"], [[{"platinum": 31.5, "painite": 4.2}, 1], [{"gold": 40.0}, 0], [{"water": 12.0}, 1]])
        self.assertEqual([(x["name"], x["tons"]) for x in g["ships"]], [("Digger", 7)])
        names = self.state.mining_hotspots()["names"]
        self.assertEqual((names["opal"], names["painite"]), ("Void Opal", "Painite"))
        # live prospects are moments for the page's call-out, with the minerals' names
        p = [m for m in self.j.moments if m["kind"] == "prospect"]
        self.assertEqual([(m["untouched"], m["motherlode"], m["content"]) for m in p], [(True, None, "High"), (False, None, "High"), (True, "opal", "High")])
        self.assertEqual((p[2]["motherlode_name"], p[0]["names"]), ("Void Opal", {"platinum": "Platinum", "painite": "Painite"}))

    def test_no_hotspot_unknown_and_empty(self):
        ring = {"System": 9, "Body": 18, "Name": "Sys 4 B Ring"}
        self.drop(0, dest=ring)                       # aimed at the ring itself: no hotspot
        self.refine(10, "platinum")
        self.leave(20)
        self.drop(100, ring="Sys 4 A Ring", body=17)  # a drop with nothing done there: not kept
        self.leave(150)
        self.drop(0, ts="2020-01-01T00:00:00Z")       # an older journal: the hotspot is not known
        self.refine(0, "platinum", ts="2020-01-01T00:05:00Z")
        self.leave(0, ts="2020-01-01T00:10:00Z")
        self.assertEqual({k: g["tons"] for k, g in self.groups().items()}, {("4 B Ring", ""): 1, ("4 B Ring", None): 1})

    def relog(self, s, ring="Sys 4 B Ring"):
        """A relog as the game writes it: Shutdown (to the desktop) or not, then LoadGame, then the login's Location."""
        self.j.handle({"event": "Shutdown", "timestamp": self.at(s)})
        self.j.handle({"event": "LoadGame", "timestamp": self.at(s + 20), "Commander": "Tester", "Ship": "python", "ShipID": 7})
        self.j.handle({"event": "Location", "timestamp": self.at(s + 25), "StarSystem": "Sys", "SystemAddress": 9, "Body": ring,
                       "BodyID": 18, "BodyType": "PlanetaryRing", "StarPos": [0, 0, 0]})

    def test_relog_in_the_ring_and_a_reread(self):
        """Review 2026-10-20 M3: the LoadGame the game writes before the login's Location closed the stint, so a relog to
        respawn the rocks split it and filed the rest under an unknown hotspot (the test had sent the Location alone)."""
        hot = {"System": 9, "Body": 18, "Name": "$SAA_RingHotspot:#type=$Platinum_name;;"}
        self.drop(0, dest=hot)
        self.refine(10, "platinum")
        self.relog(35)
        self.refine(70, "platinum")
        g = self.groups()[("4 B Ring", "platinum")]
        self.assertEqual((g["stints"], g["tons"], g["open"]), (1, 2, True))   # still the same stint, still open
        # a journal re-read rebuilds the stints; the hotspot a live drop was aimed at is kept
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual(self.db.execute("SELECT count(*) FROM mining_stints").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT hotspot FROM mining_hotspot_drops").fetchall()[0][0], "platinum")

    def test_sessions_say_where(self):
        """CMDR → Sessions' Where (the author, 2026-10-20): a mining session keeps the ring it mined in (the open stint)
        and the body the SRV mined on, the most tons first."""
        self.j.handle({"event": "LoadGame", "timestamp": self.at(-5), "Commander": "Tester", "Ship": "python", "ShipID": 7})
        self.j.handle({"event": "FSDJump", "timestamp": self.at(-2), "StarSystem": "Sys", "SystemAddress": 9, "StarPos": [0, 0, 0]})
        self.drop(0)
        self.prospect(5, platinum=20.0)
        for s in (10, 20, 30):
            self.refine(s, "platinum")
        self.leave(40)
        self.j.handle({"event": "ApproachBody", "timestamp": self.at(50), "StarSystem": "Sys", "SystemAddress": 9, "Body": "Sys A 1", "BodyID": 3})
        self.j.handle({"event": "Touchdown", "timestamp": self.at(60), "SystemAddress": 9, "Body": "Sys A 1", "BodyID": 3,
                       "PlayerControlled": True, "Latitude": 0, "Longitude": 0})
        self.j.handle({"event": "LaunchSRV", "timestamp": self.at(70), "SRVType": "testbuggy", "ID": 1, "PlayerControlled": True})
        self.refine(80, "gold")
        s = self.state.commander_sessions(now=ed_outrider.ts_seconds(self.at(100)))["sessions"][0]["mining"]
        self.assertEqual(s["places"], [{"id64": "9", "system": "Sys", "body": "4 B Ring", "tons": 3},
                                       {"id64": "9", "system": "Sys", "body": "A 1", "tons": 1}])

    def test_back_in_the_ring_after_a_long_break(self):
        """Over MINING_RELOG_GAP_S away (logged out for the night in the ring): a new stint, still the hotspot you
        dropped on; logging in elsewhere ends it at its last ton."""
        self.drop(0, dest={"System": 9, "Body": 18, "Name": "$SAA_RingHotspot:#type=$Platinum_name;;"})
        self.refine(10, "platinum")
        self.relog(10 + ed_outrider.MINING_RELOG_GAP_S + 60)
        self.refine(ed_outrider.MINING_RELOG_GAP_S + 200, "platinum")
        g = self.groups()[("4 B Ring", "platinum")]
        self.assertEqual((g["stints"], g["tons"]), (2, 2))
        self.j.handle({"event": "LoadGame", "timestamp": self.at(ed_outrider.MINING_RELOG_GAP_S + 300), "Commander": "Tester"})
        self.j.handle({"event": "Location", "timestamp": self.at(ed_outrider.MINING_RELOG_GAP_S + 305), "StarSystem": "Sys",
                       "SystemAddress": 9, "Body": "Sys", "BodyID": 0, "BodyType": "Star", "StarPos": [0, 0, 0]})   # elsewhere
        self.assertEqual(self.db.execute("SELECT count(*), max(end_ts) FROM mining_stints WHERE open = 0").fetchone()[:],
                         (2, self.at(ed_outrider.MINING_RELOG_GAP_S + 200)))   # ended at its last ton

    def test_a_legacy_stint_is_not_todays_ship(self):
        """Review 2026-10-20 L3: a stint from a legacy folder read after the live one was credited to the ship flown now
        (self.ship), where the rest of the reader takes a line older than the Loadout as an unknown ship."""
        old = "2024-03-01T09:00:00Z"
        self.drop(0, ts=old)
        self.refine(0, "platinum", ts="2024-03-01T09:01:00Z")
        self.leave(0, ts="2024-03-01T09:30:00Z")
        row = self.db.execute("SELECT ship_id, ship FROM mining_stints WHERE start_ts=?", (old,)).fetchone()
        self.assertEqual(tuple(row), (None, None))

    def test_the_mining_strip(self):
        """D: while you mine in a ring (an open stint, normal space, a mining ship): the ring and hotspot, t/h, the hold,
        limpets, minutes to full, and the line in words (Now and the overlay's system strip); nothing otherwise."""
        self.j.handle({"event": "Loadout", "timestamp": self.at(1), "Ship": "python", "ShipID": 7, "ShipName": "Digger",
                       "ShipIdent": "DG", "CargoCapacity": 64, "MaxJumpRange": 20.0, "Modules": [{"Slot": "Slot01", "Item": "int_refinery_size4_class5"}]})
        self.j.handle({"event": "Cargo", "timestamp": self.at(2), "Vessel": "Ship", "Count": 10,
                       "Inventory": [{"Name": "drones", "Count": 10, "Stolen": 0}]})
        self.drop(10, dest={"System": 9, "Body": 18, "Name": "$SAA_RingHotspot:#type=$Platinum_name;;"})
        for i in range(30):
            self.refine(20 + i * 60, "platinum")
        now = ed_outrider.ts_seconds(self.at(10)) + 1800   # half an hour after the drop: 30 t, 60 t/h
        self.j.status_json = {"live": True, "flags": 0}
        m = self.state.mining_live(now=now)
        self.assertEqual((m["ring"], m["hotspot"], m["tons"], m["tph"], m["count"], m["free"], m["limpets"], m["full_min"]),
                         ("4 B Ring", "platinum", 30, 60.0, 40, 24, 10, 24))
        self.assertEqual(m["text"], "⛏ 4 B Ring · Platinum · 60 t/h · hold 40/64 t (Platinum 30) · limpets 10 · full in ~24 min")
        # in supercruise, Status.json not live, or a ship with no mining kit: nothing
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_SUPERCRUISE}
        self.assertIsNone(self.state.mining_live(now=now))
        self.j.status_json = {"live": False, "flags": 0}
        self.assertIsNone(self.state.mining_live(now=now))
        # the overlay's system strip: a third line while mining
        import outrider.overlay as O
        pal = O.palette("elite") if hasattr(O, "palette") else None
        if pal:
            info = {"name": "Sys", "mining": m["text"]}
            texts = [r[0] for it in O.strip_panel(info, pal)["items"] for r in it.get("runs", [])]
            self.assertIn(m["text"], texts)

    def test_what_mined_ore_sold_for(self):
        self.db.execute("INSERT INTO mining_sales (ts, source, commodity, tons, mined_tons, total, mined_total, own_carrier) "
                        "VALUES ('t1', 's', 'platinum', 10, 10, 2000000, 2000000, 0), ('t2', 's', 'platinum', 10, 10, 1000000, 1000000, 0), "
                        "('t3', 's', 'painite', 5, 5, 9000000, 9000000, 1)")
        self.assertEqual(self.state.mining_hotspots()["per_ton"], {"platinum": 150000})   # your own carrier left out


if __name__ == "__main__":
    unittest.main()
