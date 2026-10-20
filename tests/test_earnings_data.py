"""The CMDR tab's Earnings, its data (PARSER_VERSION 52): where and with which ship each sale was made (sale_events'
station, market_id, station_type, ship_id), each jump, first scan and sample run's ship, and the mined stock (meta
mined_stock) that tells a sale's mining income (mining_sales) and the Sessions' "sold". Made-up journal lines fed to
Journals.handle on a scratch database."""
import json
import os
import sqlite3
import tempfile
import types
import unittest

from support import ed_outrider

NOW = 1791806400   # 2026-10-12T12:00:00Z
T = lambda hms, day="2026-10-12": f"{day}T{hms}Z"
CARRIER = 3700000099   # your carrier (made up)
STATION = 3228000001   # a station's market (made up)


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


def loadout(ts, ship_id, ship="krait_light"):
    return ev(ts, "Loadout", Ship=ship, ShipID=ship_id, ShipName=f"Ship {ship_id}", HullValue=1, ModulesValue=1,
              MaxJumpRange=50.0, FuelCapacity={"Main": 32, "Reserve": 0.6}, Modules=[])


def docked(ts, name="Keller Relay", market=STATION, kind="Coriolis", **kw):
    return ev(ts, "Docked", StationName=name, StationType=kind, MarketID=market, StarSystem="Hesperine",
              SystemAddress=1111, StationServices=["dock", "exploration", "vistagenomics"], **kw)


def undocked(ts, name="Keller Relay", market=STATION):
    return ev(ts, "Undocked", StationName=name, MarketID=market)


def refined(ts, what="painite"):
    return ev(ts, "MiningRefined", Type=f"${what}_name;", Type_Localised=what.title())


def sell(ts, what, count, total, market=STATION):
    return ev(ts, "MarketSell", MarketID=market, Type=what, Type_Localised=what.title(), Count=count,
              SellPrice=total // count, TotalSale=total, AvgPricePaid=0)


def carto(ts, total=600):
    return ev(ts, "MultiSellExplorationData", Discovered=[{"SystemName": "Old Trip", "NumBodies": 3}], BaseValue=total - 100,
              Bonus=100, TotalEarnings=total)


def bio(ts, market=STATION):
    return ev(ts, "SellOrganicData", MarketID=market, BioData=[
        {"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Species": "$Codex_Ent_Bacterial_01_Name;",
         "Species_Localised": "Bacterium Aurasus", "Value": 1000000, "Bonus": 0}])


def jump(ts, id64, **kw):
    return ev(ts, "FSDJump", StarSystem=f"S{id64}", SystemAddress=id64, StarPos=[id64, 0, 0], JumpDist=10.0, FuelUsed=1.0,
              FuelLevel=20.0, **kw)


def scan(ts, system, body_id, kind="Detailed"):
    return ev(ts, "Scan", ScanType=kind, BodyName=f"S{system} {body_id}", BodyID=body_id, StarSystem=f"S{system}",
              SystemAddress=system, DistanceFromArrivalLS=10.0, PlanetClass="Icy body", MassEM=0.1, Radius=1000000.0,
              SurfaceGravity=1.0, SurfaceTemperature=100.0, Landable=False, WasDiscovered=False, WasMapped=False)


def organic(ts, kind, system=5, body=2):
    return ev(ts, "ScanOrganic", ScanType=kind, Genus="$Codex_Ent_Bacterial_Genus_Name;", Genus_Localised="Bacterium",
              Species="$Codex_Ent_Bacterial_01_Name;", Species_Localised="Bacterium Aurasus", SystemAddress=system, Body=body)


def carrier_stats(ts):
    return ev(ts, "CarrierStats", CarrierID=CARRIER, Callsign="ABC-123", Name="TEST CARRIER", FuelLevel=500,
              JumpRangeCurr=500.0, CarrierType="FleetCarrier")


def setup(test, events=()):
    """A scratch database, its Journals fed `events` and a State over it."""
    db = ed_outrider.open_db(":memory:")
    test.addCleanup(db.close)
    j = ed_outrider.Journals(db)
    for e in events:
        j.handle(e)
    return j, ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)


def rows(db, sql, *args):
    return [tuple(r) for r in db.execute(sql, args)]


class WhereAndWithWhichShip(unittest.TestCase):
    """sale_events, jumps, own_bodies and own_organic keep the place and the ship each happened with."""

    def test_sales_at_a_station(self):
        j, _ = setup(self, [loadout(T("08:00:00"), 7), docked(T("08:01:00")), carto(T("08:02:00")), bio(T("08:03:00")),
                            undocked(T("08:05:00"))])
        self.assertEqual(rows(j.db, "SELECT kind, station, market_id, station_type, ship_id FROM sale_events ORDER BY ts"),
                         [("carto", "Keller Relay", STATION, "Coriolis", 7), ("bio", "Keller Relay", STATION, "Coriolis", 7)])
        self.assertEqual(j.sale_place(T("08:06:00")), (None, None, None))   # left the station: nowhere docked

    def test_sales_at_your_carrier_after_logging_in_there(self):
        """A session that starts docked writes no Docked: its Location says so (the place of a sale straight after)."""
        j, _ = setup(self, [loadout(T("08:00:00"), 9),
                            ev(T("08:00:10"), "Location", Docked=True, StationName="ABC-123", StationType="FleetCarrier",
                               MarketID=CARRIER, StarSystem="Hesperine", SystemAddress=1111, StarPos=[0, 0, 0]),
                            carto(T("08:01:00")), bio(T("08:02:00"), market=CARRIER)])
        self.assertEqual(rows(j.db, "SELECT station, market_id, station_type, ship_id FROM sale_events"),
                         [("ABC-123", CARRIER, "FleetCarrier", 9)] * 2)

    def test_a_sale_by_apex_shuttle(self):
        """Riding an Apex shuttle to a station, you can sell your data there: its dock is the sale's place."""
        j, _ = setup(self, [loadout(T("08:00:00"), 7), docked(T("08:01:00"), Taxi=True), carto(T("08:02:00"))])
        self.assertEqual(rows(j.db, "SELECT station, market_id FROM sale_events"), [("Keller Relay", STATION)])

    def test_a_line_read_out_of_order_is_placed_nowhere(self):
        """A legacy folder read late: its sale is older than the dock and the ship known now, so neither is its own."""
        j, _ = setup(self, [loadout(T("08:00:00"), 7), docked(T("08:01:00")), carto(T("07:00:00"))])
        self.assertEqual(rows(j.db, "SELECT station, market_id, ship_id FROM sale_events"), [(None, None, None)])

    def test_a_jump_keeps_its_ship(self):
        j, _ = setup(self, [loadout(T("08:00:00"), 7), jump(T("08:01:00"), 100), loadout(T("08:10:00"), 9),
                            jump(T("08:11:00"), 101), jump(T("08:12:00"), 102, Taxi=True)])
        self.assertEqual(rows(j.db, "SELECT id64, ship_id FROM jumps ORDER BY ts"), [(100, 7), (101, 9), (102, None)])   # a ride: not yours

    def test_a_rescan_keeps_the_first_scans_ship(self):
        j, _ = setup(self, [loadout(T("08:00:00"), 7), scan(T("08:01:00"), 5, 1, "AutoScan"), loadout(T("09:00:00"), 9),
                            scan(T("09:01:00"), 5, 1), scan(T("09:02:00"), 5, 2)])
        self.assertEqual(rows(j.db, "SELECT body_id, ts, ship_id FROM own_bodies ORDER BY body_id"),
                         [(1, T("09:01:00"), 7), (2, T("09:02:00"), 9)])   # the row is the rescan's, the ship the first's

    def test_a_species_run_has_the_ship_you_came_in(self):
        """On foot or in the SRV, the ship flown is still the one you landed: the run's ship, set by the Analyse."""
        j, _ = setup(self, [loadout(T("08:00:00"), 7), organic(T("08:10:00"), "Log"),
                            ev(T("08:11:00"), "LaunchSRV", SRVType="testbuggy", ID=1, PlayerControlled=True),
                            organic(T("08:12:00"), "Sample"), organic(T("08:14:00"), "Analyse")])
        self.assertEqual(rows(j.db, "SELECT samples, done_ts, ship_id FROM own_organic"), [(3, T("08:14:00"), 7)])

    def test_the_fixtures_read_and_read_again(self):
        """The sample journals: a sale at Keller Relay in the Sample Ship (ShipID 7), its jumps, scans and runs; a
        re-read (RESET_JOURNAL_DATA, then the files again) gives the same."""
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "journals")
        j, _ = setup(self)
        j.scan_dir(d)

        def got():
            return (rows(j.db, "SELECT kind, station, market_id, station_type, ship_id FROM sale_events ORDER BY ts"),
                    rows(j.db, "SELECT DISTINCT ship_id FROM jumps"), rows(j.db, "SELECT DISTINCT ship_id FROM own_bodies"),
                    rows(j.db, "SELECT done_ts IS NOT NULL, ship_id FROM own_organic ORDER BY ts"))
        first = got()
        self.assertEqual(first[0], [("carto", "Keller Relay", 3700000001, "Coriolis", 7),
                                    ("bio", "Keller Relay", 3700000001, "Coriolis", 7)])
        self.assertEqual(first[1:3], ([(7,)], [(7,)]))
        self.assertIn((1, 7), first[3])   # the completed run
        self.assertEqual(ed_outrider.meta_get(j.db, "mined_stock"), {"water": 4, "platinum": 2})   # the Rhino's run, unsold
        j.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        j.reload()
        j.scan_dir(d)
        self.assertEqual(got(), first)
        self.assertEqual(ed_outrider.meta_get(j.db, "mined_stock"), {"water": 4, "platinum": 2})

    def test_an_old_database_gains_the_columns(self):
        """open_db adds the new columns to a database from before them (their rows NULL until the re-read)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.sqlite")
            old = sqlite3.connect(path)
            old.executescript("""
                CREATE TABLE sale_events (ts TEXT, kind TEXT, base INTEGER, bonus INTEGER, total INTEGER, systems INTEGER,
                    species INTEGER, source TEXT, x5_check TEXT, PRIMARY KEY (ts, kind, source));
                CREATE TABLE jumps (ts TEXT, id64 INTEGER, name TEXT, x REAL, y REAL, z REAL, star_class TEXT, kind TEXT,
                    verdict TEXT, ride INTEGER, PRIMARY KEY (ts, id64));
                INSERT INTO jumps (ts, id64) VALUES ('2026-01-01T00:00:00Z', 1);""")
            old.commit()
            old.close()
            db = ed_outrider.open_db(path, reset=False)
            try:
                cols = lambda t: {r["name"] for r in db.execute(f"PRAGMA table_info({t})")}
                self.assertLessEqual({"station", "market_id", "station_type", "ship_id"}, cols("sale_events"))
                self.assertIn("ship_id", cols("jumps"))
                self.assertIn("ship_id", cols("own_bodies"))
                self.assertIn("ship_id", cols("own_organic"))
                self.assertEqual(rows(db, "SELECT id64, ship_id FROM jumps"), [(1, None)])
            finally:
                db.close()


class MinedStock(unittest.TestCase):
    """The tons you mined still aboard (meta mined_stock) and what a sale of them earned (mining_sales)."""

    def stock(self, j):
        return ed_outrider.meta_get(j.db, "mined_stock")

    def sales(self, j):
        return rows(j.db, "SELECT commodity, tons, mined_tons, price, total, mined_total, station, market_id, ship_id,"
                          " own_carrier FROM mining_sales ORDER BY ts")

    def test_refined_by_the_ship_and_by_the_srv(self):
        j, _ = setup(self, [refined(T("08:00:00")), refined(T("08:01:00")),
                            ev(T("08:10:00"), "LaunchSRV", SRVType="mev_rhino", ID=1, PlayerControlled=True),
                            refined(T("08:11:00"), "gold"), ev(T("08:12:00"), "DockSRV", SRVType="mev_rhino", ID=1)])
        self.assertEqual(self.stock(j), {"painite": 2, "gold": 1})

    def test_moved_to_your_carrier_ejected_or_lost(self):
        j, _ = setup(self, [refined(T("08:00:0%d" % i)) for i in range(5)] + [refined(T("08:00:10"), "gold")] + [
            ev(T("08:10:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 2, "Direction": "tocarrier"},
                                                          {"Type": "gold", "Count": 1, "Direction": "toship"}]),
            ev(T("08:11:00"), "EjectCargo", Type="painite", Count=1, Abandoned=True)])
        self.assertEqual(self.stock(j), {"painite": 2, "gold": 1})   # 5 - 2 to the carrier - 1 ejected; a transfer to the ship adds none
        self.assertEqual(self.kept(j), {"painite": 2})                # kept on the carrier; the gold taken back was never mined
        j.handle(ev(T("08:12:00"), "EjectCargo", Type="painite", Count=9, Abandoned=True))
        self.assertEqual(self.stock(j), {"gold": 1})                  # never below 0
        j.handle(ev(T("08:13:00"), "Died"))
        self.assertEqual(self.stock(j), {})                           # the hold is lost

    def kept(self, j):
        return ed_outrider.meta_get(j.db, "mined_carrier")

    def test_stored_on_your_carrier_and_sold_later(self):
        """Ore moved to your carrier keeps counting as mined: back aboard, it is sold as mining (the author, 2026-10-14:
        about half his mining income went through the carrier); bought ore taken from the carrier is not."""
        j, state = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="python"), loadout(T("08:00:05"), 7)]
                         + [refined(T("08:01:0%d" % i)) for i in range(4)] + [
            ev(T("08:10:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 4, "Direction": "tocarrier"}]),
            ev(T("09:00:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 6, "Direction": "toship"}]),
            docked(T("09:30:00")), sell(T("09:31:00"), "painite", 6, 1200000)])
        self.assertEqual((self.stock(j), self.kept(j)), ({}, {}))
        self.assertEqual([(s[0], s[1], s[2], s[5]) for s in self.sales(j)], [("painite", 6, 4, 800000)])   # 4 of the 6 t mined
        self.assertEqual(state.commander_sessions(now=NOW)["sessions"][0]["mining"]["sold"], 800000)

    def test_capped_at_what_the_carrier_holds(self):
        """Ore others bought from your carrier is not journaled, but a Market.json read shows the hold going down: the
        carrier's mined stock is capped at what it held when ore comes back aboard (the author, 2026-10-14)."""
        def run(market_stock):
            j, _ = setup(self, [carrier_stats(T("08:00:00"))] + [refined(T("08:01:%02d" % i)) for i in range(10)] + [
                docked(T("08:20:00"), name="ABC-123", market=CARRIER, kind="FleetCarrier"),
                ev(T("08:21:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 10, "Direction": "tocarrier"}])])
            if market_stock is not None:   # a later read of the carrier's market: a sell order of what is left
                j.db.execute("INSERT INTO carrier_markets VALUES (?, ?, ?)", (T("09:00:00"), CARRIER, json.dumps(
                    [{"Name": "$painite_name;", "Name_Localised": "Painite", "Stock": market_stock, "BuyPrice": 5000000}])))
            for e in (ev(T("10:00:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 5, "Direction": "toship"}]),
                      undocked(T("10:05:00"), "ABC-123", CARRIER), docked(T("10:30:00")), sell(T("10:31:00"), "painite", 5, 1000000)):
                j.handle(e)
            return self.sales(j)[0][2], self.kept(j)
        self.assertEqual(run(None), (5, {"painite": 5}))   # no market read: the carrier still holds all 10 mined
        self.assertEqual(run(3), (3, {}))                  # others bought 7: 3 left, all of them mined, all taken back
        self.assertEqual(run(8), (5, {"painite": 3}))      # others bought 2: 8 held, 5 back aboard

    def test_part_kept_on_the_carrier(self):
        j, _ = setup(self, [refined(T("08:01:0%d" % i)) for i in range(5)] + [
            ev(T("08:10:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 5, "Direction": "tocarrier"}]),
            ev(T("09:00:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 2, "Direction": "toship"}])])
        self.assertEqual((self.stock(j), self.kept(j)), ({"painite": 2}, {"painite": 3}))
        j.handle(ev(T("09:10:00"), "Died"))   # the ship's hold is lost, the carrier's is not
        self.assertEqual((self.stock(j), self.kept(j)), ({}, {"painite": 3}))
        j.handle(ev(T("09:20:00"), "CarrierBuy", CarrierID=99, Callsign="XYZ-987", Location="Sol", Price=5000000000))
        self.assertEqual(self.kept(j), {})   # a new carrier holds none of it

    def test_sold_to_your_carrier_then_taken_back(self):
        """Mined ore sold to your own carrier (left out: your own money) is still yours, in its hold: taken back and sold
        elsewhere, it counts."""
        j, _ = setup(self, [carrier_stats(T("08:00:10"))] + [refined(T("08:01:0%d" % i)) for i in range(3)] + [
            docked(T("08:20:00"), name="ABC-123", market=CARRIER, kind="FleetCarrier"),
            sell(T("08:21:00"), "painite", 3, 600000, market=CARRIER),
            ev(T("08:25:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 3, "Direction": "toship"}]),
            undocked(T("08:30:00"), "ABC-123", CARRIER), docked(T("08:40:00")), sell(T("08:41:00"), "painite", 3, 750000)])
        self.assertEqual([(s[2], s[5], s[9]) for s in self.sales(j)], [(3, 600000, 1), (3, 750000, 0)])
        self.assertEqual((self.stock(j), self.kept(j)), ({}, {}))

    def test_a_partial_sale(self):
        """2 t mined and 3 t bought: a sale of 5 is mining for 2 of them, its share of the total, the rest trade."""
        j, _ = setup(self, [loadout(T("08:00:00"), 7), refined(T("08:01:00")), refined(T("08:02:00")),
                            docked(T("09:00:00")), sell(T("09:01:00"), "painite", 5, 1000003)])
        self.assertEqual(self.sales(j), [("painite", 5, 2, 200000, 1000003, 400001, "Keller Relay", STATION, 7, 0)])
        self.assertEqual(self.stock(j), {})
        j.handle(sell(T("09:02:00"), "painite", 1, 200000))
        self.assertEqual(len(self.sales(j)), 1)                       # nothing mined left: trade, no row

    def test_mined_in_one_session_sold_in_another(self):
        j, state = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="python"), loadout(T("08:00:05"), 7),
                                refined(T("08:10:00")), refined(T("08:11:00")), ev(T("08:30:00"), "Shutdown"),
                                ev(T("10:00:00"), "LoadGame", Commander="Tester", Ship="python"), loadout(T("10:00:05"), 7),
                                docked(T("10:05:00")), sell(T("10:06:00"), "painite", 2, 600000)])
        self.assertEqual(self.sales(j), [("painite", 2, 2, 300000, 600000, 600000, "Keller Relay", STATION, 7, 0)])
        got = state.commander_sessions(now=NOW)
        sold = [(s["start"], s["mining"]["tons"], s["mining"]["sold"]) for s in got["sessions"] if s["mining"]]
        self.assertEqual(sold, [(T("10:00:00"), 0, 600000), (T("08:00:00"), 2, 0)])   # sold in the login it was sold in
        self.assertEqual(got["totals"]["mining"]["sold"], 600000)

    def test_sold_to_your_own_carrier(self):
        """Your own carrier's market: flagged, its stock comes off, and Sessions do not count it (your own money)."""
        j, state = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="python"), carrier_stats(T("08:00:10")),
                                refined(T("08:10:00")), refined(T("08:11:00")), refined(T("08:12:00")),
                                docked(T("08:20:00"), name="ABC-123", market=CARRIER, kind="FleetCarrier"),
                                sell(T("08:21:00"), "painite", 2, 400000, market=CARRIER),
                                undocked(T("08:30:00"), "ABC-123", CARRIER), docked(T("08:40:00")),
                                sell(T("08:41:00"), "painite", 1, 250000)])
        self.assertEqual([(s[0], s[2], s[5], s[6], s[9]) for s in self.sales(j)],
                         [("painite", 2, 400000, "ABC-123", 1), ("painite", 1, 250000, "Keller Relay", 0)])
        self.assertEqual(state.commander_sessions(now=NOW)["sessions"][0]["mining"]["sold"], 250000)

    def test_sessions_sold_follows_the_mined_stock(self):
        """The Sessions' sold is the sale's mined part, not every sale of a commodity refined that login."""
        _, state = setup(self, [ev(T("08:00:00"), "LoadGame", Commander="Tester", Ship="python"),
                                refined(T("08:10:00"), "platinum"), refined(T("08:11:00"), "platinum"),
                                sell(T("08:50:00"), "platinum", 5, 1000000)])
        self.assertEqual(state.commander_sessions(now=NOW)["sessions"][0]["mining"]["sold"], 400000)   # 2 of the 5 t

    def test_an_older_line_read_late_leaves_the_stock(self):
        """A legacy folder read after the live one: what was aboard then is not known, so its lines change nothing."""
        j, _ = setup(self, [refined(T("08:00:00")), refined(T("07:00:00")), sell(T("07:30:00"), "painite", 1, 5)])
        self.assertEqual((self.stock(j), self.sales(j)), ({"painite": 1}, []))

    def test_a_failed_tick_puts_the_stock_back(self):
        """The stock is meta: a rolled-back tick and reload() bring back what the database holds."""
        j, _ = setup(self, [refined(T("08:00:00"))])
        j.db.commit()
        j.handle(refined(T("08:01:00")))
        j.db.rollback()
        j.reload()
        self.assertEqual(j.mined_stock, {"painite": 1})

    def test_a_reread_clears_the_table_and_the_stock(self):
        j, _ = setup(self, [refined(T("08:00:00")), refined(T("08:01:00")), refined(T("08:01:30")), docked(T("08:02:00")),
                            sell(T("08:03:00"), "painite", 1, 5),
                            ev(T("08:04:00"), "CargoTransfer", Transfers=[{"Type": "painite", "Count": 1, "Direction": "tocarrier"}])])
        self.assertTrue(self.sales(j) and self.stock(j) and self.kept(j) and ed_outrider.meta_get(j.db, "sale_dock"))
        j.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual((self.sales(j), self.stock(j), self.kept(j), ed_outrider.meta_get(j.db, "sale_dock")),
                         ([], None, None, None))

    def test_the_newer_ships_pads(self):
        """The Lynx Highliner (medium: the author checked), the Kestrel Mk II (small: Frontier's ship page) and the
        Anaconda Mk II (large: a huge hardpoint; `anacondamkii` in EDDN's shipyards, 2026-10-20)."""
        import outrider.cargo
        self.assertEqual((outrider.cargo.SHIP_PAD["mediumtransport01"], outrider.cargo.SHIP_PAD["smallcombat01_nx"],
                          outrider.cargo.SHIP_PAD.get("anacondamkii")),
                         (outrider.cargo.MEDIUM, outrider.cargo.SMALL, outrider.cargo.LARGE))


if __name__ == "__main__":
    unittest.main()
