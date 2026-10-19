"""Unit tests: cargo: the ship's hold (exact, with what you paid) and your fleet carrier's (tracked: sell orders confirm,
the journal tracks the rest, Recount fills gaps), the carrier's tritium (outrider/cargo.py, State.cargo_summary).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import json
import os
import shutil
import tempfile
import time
import types
import unittest
import unittest.mock
import asyncio

from support import _HwSession, ed_outrider, hwy_jump, hwy_ts  # also puts the repository root on sys.path
import outrider.cargo as cargo  # noqa: E402

CARRIER = 3700251648
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "carrier_market.json")


def real():
    """The author's carrier on 2026-10-07 (tests/fixtures/carrier_market.json): its journal events and Market.json."""
    with open(FIXTURE, encoding="utf-8") as f:
        fx = json.load(f)
    at, events = None, []
    for ev in fx["events"]:   # the docks give a CargoTransfer its market, as Journals.handle_cargo does
        if ev["event"] == "Docked":
            at = None if ev.get("Taxi") or ev.get("Multicrew") else ev.get("MarketID")
        elif ev["event"] == "Undocked":
            at = None
        else:
            events.append((ev["timestamp"], dict(ev, _at=at) if ev["event"] == "CargoTransfer" else ev))
    return fx, events, [(fx["market"]["timestamp"], fx["market"]["Items"])]


def spansh_commodity_names():
    """Spansh's commodity names as its field_values answered on 2026-10-13 (tests/fixtures/spansh_commodities.json)."""
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_commodities.json"), encoding="utf-8") as f:
        return sorted(json.load(f)["min_max"])


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


def stats(ts, cargo_t, fuel=500, used=None):
    return ev(ts, "CarrierStats", CarrierID=CARRIER, CarrierType="FleetCarrier", FuelLevel=fuel,
              SpaceUsage={"TotalCapacity": 25000, "Cargo": cargo_t, "FreeSpace": 25000 - (used or cargo_t + 1000)})


def item(name, stock=0, demand=0, buy=0, sell=0):
    return {"Name": f"${name}_name;", "Name_Localised": name.title(), "Stock": stock, "Demand": demand,
            "BuyPrice": buy, "SellPrice": sell}


class CarrierFold(unittest.TestCase):
    """carrier_fold: pure."""

    def test_real_carrier(self):
        """The author's carrier: the market's sell orders confirm 15,746 t; the sell orders set earlier that day and
        cancelled (an order means at least that much there) and a transfer of water are tracked; with the two lines
        no order ever showed entered, the total is CarrierStats' 16,085 t, in sync."""
        fx, events, markets = real()
        st = cargo.carrier_fold(CARRIER, events, markets)
        lines = st["lines"]
        self.assertEqual(sum(x["count"] for x in lines.values() if x["state"] == "confirmed"), 15746)
        self.assertEqual((lines["tritium"]["count"], lines["tritium"]["state"]), (13531, "confirmed"))
        self.assertEqual((lines["personalweapons"]["count"], lines["personalweapons"]["state"]), (182, "seen"))
        self.assertEqual(lines["water"]["state"], "seen")
        self.assertEqual(cargo.carrier_reported(st), 16085)
        self.assertEqual(cargo.carrier_total(st), 16076)   # the 9 t no order ever showed
        counts = [("2026-10-07T10:30:00Z", "metaalloys", 3, "Meta-Alloys"),
                  ("2026-10-07T10:30:00Z", "modularterminals", 6, "Modular Terminals")]
        st = cargo.carrier_fold(CARRIER, events, markets, counts)
        self.assertEqual(cargo.carrier_total(st), 16085)
        self.assertEqual(st["lines"]["metaalloys"]["state"], "entered")
        self.assertEqual(st["names"]["metaalloys"], "Meta-Alloys")
        # another carrier's id: none of these events are its (its markets are the caller's to pick)
        self.assertEqual(cargo.carrier_fold(123, events)["lines"], {})

    def test_buy_order_filled_by_others(self):
        """A buy order shows only what it still wants: what others sold you is the order minus that, your own sales
        into it taken off first."""
        events = [(t, e) for t, e in [
            ("2026-10-01T10:00:00Z", ev("2026-10-01T10:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER, Commodity="silver",
                                        PurchaseOrder=10, Price=5000)),
            ("2026-10-01T10:05:00Z", ev("2026-10-01T10:05:00Z", "MarketSell", MarketID=CARRIER, Type="silver", Count=2,
                                        SellPrice=5000))]]
        st = cargo.carrier_fold(CARRIER, events, [("2026-10-01T12:00:00Z", [item("silver", demand=5, sell=5000)])])
        line = st["lines"]["silver"]
        self.assertEqual(line["count"], 5)   # 2 you sold + 3 others did
        self.assertEqual([m[2] for m in line["moves"]], ["sold", "others"])
        self.assertEqual(st["orders"]["silver"]["amount"], 5)
        # filled: the market no longer lists it; the last 5 came in
        st = cargo.carrier_fold(CARRIER, events, [("2026-10-01T12:00:00Z", [item("silver", demand=5, sell=5000)]),
                                                  ("2026-10-01T13:00:00Z", [])])
        self.assertEqual(st["lines"]["silver"]["count"], 10)
        self.assertNotIn("silver", st["orders"])

    def test_market_keeps_a_confirmed_line_moves(self):
        """Review 2026-10-08 #10: a market read confirmed the count but emptied the line's moves (the hover text)."""
        t0, t1 = "2026-10-01T10:00:00Z", "2026-10-01T10:05:00Z"
        events = [(t0, ev(t0, "CarrierTradeOrder", CarrierID=CARRIER, Commodity="gold", SaleOrder=10, Price=9000)),
                  (t1, ev(t1, "CargoTransfer", _at=CARRIER, Transfers=[{"Type": "gold", "Count": 4, "Direction": "tocarrier"}]))]
        st = cargo.carrier_fold(CARRIER, events, [("2026-10-01T11:00:00Z", [item("gold", stock=14, buy=9000)])])
        line = st["lines"]["gold"]
        self.assertEqual((line["count"], line["state"]), (14, "confirmed"))
        self.assertEqual([m[1] for m in line["moves"]], [4])

    def test_entered_line_moves(self):
        """A count you entered keeps its mark through your journaled moves, which say what changed it."""
        events = [("2026-10-08T09:00:00Z", ev("2026-10-08T09:00:00Z", "CargoTransfer", _at=CARRIER,
                                              Transfers=[{"Type": "modularterminals", "Count": 2, "Direction": "toship"}])),
                  ("2026-10-08T09:30:00Z", ev("2026-10-08T09:30:00Z", "CargoTransfer", _at=999,   # another station
                                              Transfers=[{"Type": "modularterminals", "Count": 1, "Direction": "toship"}]))]
        st = cargo.carrier_fold(CARRIER, events, (), [("2026-10-07T10:30:00Z", "modularterminals", 6, "Modular Terminals")])
        line = st["lines"]["modularterminals"]
        self.assertEqual((line["count"], line["state"]), (4, "entered"))
        self.assertEqual(cargo.move_text(line["moves"][0]), "−2 t moved to your ship (2026-10-08)")
        # a count of 0 removes the line
        st = cargo.carrier_fold(CARRIER, events, (), [("2026-10-07T10:30:00Z", "modularterminals", 6, None),
                                                      ("2026-10-09T10:30:00Z", "modularterminals", 0, None)])
        self.assertNotIn("modularterminals", st["lines"])

    def test_sell_orders(self):
        """A sell order the market no longer lists sold out; a cancelled one leaves the line seen at its last count."""
        m1 = [item("platinum", stock=100, buy=9999), item("gold", stock=20, buy=9999)]
        cancel = ev("2026-10-01T11:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER, Commodity="gold", CancelTrade=True)
        st = cargo.carrier_fold(CARRIER, [("2026-10-01T11:00:00Z", cancel)],
                                [("2026-10-01T10:00:00Z", m1), ("2026-10-01T12:00:00Z", [])])
        self.assertNotIn("platinum", st["lines"])
        self.assertEqual((st["lines"]["gold"]["count"], st["lines"]["gold"]["state"], st["lines"]["gold"]["ts"]),
                         (20, "seen", "2026-10-01T10:00:00Z"))

    def test_stale_lines_when_over(self):
        """The author's 2025 history left 34,000 t tracked that others had bought unjournaled: when the carrier holds
        less than is tracked, lines with no news for 30 days go (a real one shows as the gap); a fresh sell order
        resets a tracked line; an open sell order the market does not list sold out."""
        def transfer(ts, typ, n):
            return (ts, ev(ts, "CargoTransfer", _at=CARRIER, Transfers=[{"Type": typ, "Count": n, "Direction": "tocarrier"}]))
        events = [transfer("2025-01-01T10:00:00Z", "aluminium", 500), transfer("2025-01-01T10:00:00Z", "steel", 80),
                  transfer("2026-09-30T10:00:00Z", "water", 10), transfer("2025-01-02T10:00:00Z", "gold", 300),
                  ("2025-01-03T10:00:00Z", ev("2025-01-03T10:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER,
                                              Commodity="gold", SaleOrder=50, Price=1)),
                  ("2025-01-04T10:00:00Z", ev("2025-01-04T10:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER,
                                              Commodity="steel", SaleOrder=80, Price=1))]
        market = [("2026-10-07T10:00:01Z", [item("platinum", stock=100, buy=9)])]
        over = cargo.carrier_fold(CARRIER, events + [("2026-10-07T10:00:00Z", stats("2026-10-07T10:00:00Z", 110))], market)
        self.assertEqual(sorted(over["lines"]), ["platinum", "water"])   # gold 50 (the order's count) sold out too
        kept = cargo.carrier_fold(CARRIER, events + [("2026-10-07T10:00:00Z", stats("2026-10-07T10:00:00Z", 610))], market)
        self.assertEqual(kept["lines"]["aluminium"]["count"], 500)   # nothing says it is wrong
        self.assertNotIn("steel", kept["lines"])   # its open sell order is not listed: sold out
        before = cargo.carrier_fold(CARRIER, events)
        self.assertEqual(before["lines"]["gold"]["count"], 50)   # the order's count: newer news than the transfer

    def test_buy_order_fill_counted_once(self):
        """Others filling your buy order: the line grows by what they sold. The CarrierStats the game writes just before
        Market.json already holds the fill, so the reported total is not raised again (the Fable sweep, 2026-10-09: it
        was, a false +300 t gap); a market read with no newer CarrierStats than the read before it does raise it, so an
        old untouched line is not taken for stale and dropped."""
        old_gold = ("2025-01-01T10:00:00Z", ev("2025-01-01T10:00:00Z", "CargoTransfer", _at=CARRIER,
                                                Transfers=[{"Type": "gold", "Count": 500, "Direction": "tocarrier"}]))
        order = ("2026-10-01T10:05:00Z", ev("2026-10-01T10:05:00Z", "CarrierTradeOrder", CarrierID=CARRIER,
                                            Commodity="silver", PurchaseOrder=300, Price=1))
        # the game's order: CarrierStats (the fill in it) just before the Market.json that shows the order filled
        st = cargo.carrier_fold(CARRIER, [old_gold, ("2026-10-01T10:00:00Z", stats("2026-10-01T10:00:00Z", 500)), order,
                                          ("2026-10-02T10:00:00Z", stats("2026-10-02T10:00:00Z", 800))],
                                [("2026-10-02T10:00:01Z", [item("silver", demand=0, sell=1)])])
        self.assertIn("gold", st["lines"])
        self.assertEqual((cargo.carrier_total(st), cargo.carrier_reported(st)), (800, 800))   # in step: no gap
        # a market read with no CarrierStats since the read before it: that one could not hold the fill
        st = cargo.carrier_fold(CARRIER, [old_gold, ("2026-10-01T10:00:00Z", stats("2026-10-01T10:00:00Z", 500)), order],
                                [("2026-10-01T10:06:00Z", [item("silver", demand=300, sell=1)]),
                                 ("2026-10-02T10:00:00Z", [item("silver", demand=0, sell=1)])])
        self.assertIn("gold", st["lines"])
        self.assertEqual((cargo.carrier_total(st), cargo.carrier_reported(st)), (800, 800))

    def test_reported_follows_your_moves(self):
        """The carrier's own total moves with your transfers after its CarrierStats (no false gap until the next)."""
        events = [("2026-10-01T10:00:00Z", stats("2026-10-01T10:00:00Z", 100)),
                  ("2026-10-01T10:05:00Z", ev("2026-10-01T10:05:00Z", "CargoTransfer", _at=CARRIER,
                                              Transfers=[{"Type": "gold", "Count": 30, "Direction": "tocarrier"}]))]
        st = cargo.carrier_fold(CARRIER, events, [("2026-10-01T10:00:00Z", [item("platinum", stock=100, buy=1)])])
        self.assertEqual((cargo.carrier_total(st), cargo.carrier_reported(st)), (130, 130))


class CarrierLife(unittest.TestCase):
    """A carrier decommissioned (shown in red, never hidden) and a new one bought: Journals.handle_ship's carrier
    state, State.carrier_summary / carrier_decommission. Frontier's documented events: not yet seen in a real journal."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.handle(stats("2026-10-01T10:00:00Z", 100))
        self.j.handle(ev("2026-10-01T10:00:01Z", "CarrierLocation", CarrierType="FleetCarrier", CarrierID=CARRIER,
                         StarSystem="Old Place", SystemAddress=111))
        self.j.handle(ev("2026-10-01T10:00:02Z", "CarrierJumpRequest", CarrierID=CARRIER, SystemName="Far",
                         SystemAddress=222, DepartureTime="2026-10-01T10:20:00Z"))

    def test_decommission(self):
        future = time.time() + 7 * 86400
        self.j.handle(ev("2026-10-02T10:00:00Z", "CarrierDecommission", CarrierID=CARRIER, ScrapRefund=4850000000,
                         ScrapTime=future))
        d = self.state.carrier_summary()["decommission"]
        self.assertEqual((d["done"], d["refund"], d["scrap_ts"]), (False, 4850000000, ed_outrider.iso_ts(future)))
        self.j.handle(ev("2026-10-03T10:00:00Z", "CarrierCancelDecommission", CarrierID=CARRIER))
        self.assertIsNone(self.state.carrier_summary()["decommission"])
        self.j.handle(ev("2026-10-04T10:00:00Z", "CarrierDecommission", CarrierID=CARRIER, ScrapRefund=1, ScrapTime=1000))
        c = self.state.carrier_summary()
        self.assertTrue(c["decommission"]["done"])   # scrapped: still shown (in red), its tritium no longer
        self.assertIsNone(c["tritium"])
        self.assertEqual(c["carrier_id"], str(CARRIER))
        self.assertTrue(self.state.cargo_summary()["carrier"]["decommission"]["done"])

    def test_new_carrier(self):
        self.j.handle(ev("2026-10-04T10:00:00Z", "CarrierDecommission", CarrierID=CARRIER, ScrapRefund=1, ScrapTime=1000))
        self.j.handle(ev("2026-10-20T10:00:00Z", "CarrierBuy", CarrierID=999, Callsign="ABC-123", Location="New Place",
                         SystemAddress=333, BoughtAtMarket=1, Price=5000000000, Variant="CarrierDockB"))
        c = self.state.carrier_summary()
        self.assertEqual((c["carrier_id"], c["callsign"], c["system"], c["decommission"], c["planned"]),
                         ("999", "ABC-123", "New Place", None, None))
        self.assertEqual(self.state.cargo_summary()["carrier"]["lines"], [])   # the old one's cargo is not its

    def test_new_carrier_from_its_stats(self):
        """No CarrierBuy read (an older journal gone): the first CarrierStats of another id starts afresh."""
        self.j.handle(dict(stats("2026-10-20T10:00:00Z", 0), CarrierID=999, Name="NEW ONE"))
        self.assertEqual((self.j.carrier["id"], self.j.carrier.get("system"), self.j.carrier.get("planned")), (999, None, None))
        self.assertIsNone(self.state.carrier_summary())   # where it is comes with its CarrierLocation


class ShipHold(unittest.TestCase):
    """ship_apply: the hold and what you paid (average cost)."""

    def test_average_over_lots(self):
        st = cargo.new_ship()
        cargo.ship_apply(st, ev("2026-10-01T10:00:00Z", "Cargo", Vessel="Ship", Count=0, Inventory=[]))
        cargo.ship_apply(st, ev("2026-10-01T10:01:00Z", "MarketBuy", Type="platinum", Count=40, BuyPrice=44000))
        self.assertEqual(cargo.avg_text(st["lines"]["platinum"]), "44,000 cr/t")
        cargo.ship_apply(st, ev("2026-10-01T10:30:00Z", "MarketBuy", Type="platinum", Count=24, BuyPrice=47227))
        line = st["lines"]["platinum"]
        self.assertEqual((line["count"], line["lots"], round(line["avg"])), (64, 2, 45210))
        self.assertEqual(cargo.avg_text(line), "Avg 45,210 cr/t (2 lots)")
        # mined tons carry no price
        cargo.ship_apply(st, ev("2026-10-01T11:00:00Z", "MiningRefined", Type="$platinum_name;"))
        self.assertEqual(cargo.avg_text(st["lines"]["platinum"]), "Avg 45,210 cr/t on 64 of 65 t")
        # a sale: the game's own average corrects it; the rest stays
        cargo.ship_apply(st, ev("2026-10-01T12:00:00Z", "MarketSell", Type="platinum", Count=5, SellPrice=60000,
                                AvgPricePaid=45300))
        line = st["lines"]["platinum"]
        self.assertEqual((line["count"], line["priced"], line["avg"]), (60, 60, 45300))

    def test_snapshot_same_second(self):
        """A Cargo.json read before its purchase line: the count is not added twice, the price is kept."""
        st = cargo.new_ship()
        cargo.ship_snapshot(st, [{"Name": "gold", "Count": 10, "Stolen": 0}], 10, "2026-10-01T10:00:05Z")
        cargo.ship_apply(st, ev("2026-10-01T10:00:05Z", "MarketBuy", Type="gold", Count=10, BuyPrice=9000))
        line = st["lines"]["gold"]
        self.assertEqual((line["count"], line["priced"], line["avg"]), (10, 10, 9000))
        # a later Inventory keeps what it cost
        cargo.ship_apply(st, ev("2026-10-01T11:00:00Z", "Cargo", Vessel="Ship", Count=10,
                                Inventory=[{"Name": "gold", "Count": 10, "Stolen": 0}]))
        self.assertEqual(st["lines"]["gold"]["avg"], 9000)

    def test_deposit_and_transfer(self):
        """Depositing tritium takes it from the ship's hold (the carrier's only falls with the transfer before)."""
        st = cargo.new_ship()
        cargo.ship_apply(st, ev("2026-09-26T23:41:26Z", "CargoTransfer",
                                Transfers=[{"Type": "tritium", "Count": 934, "Direction": "toship"}]))
        cargo.ship_apply(st, ev("2026-09-26T23:41:34Z", "CarrierDepositFuel", CarrierID=CARRIER, Amount=906, Total=1000))
        self.assertEqual(st["lines"]["tritium"]["count"], 28)
        cargo.ship_apply(st, ev("2026-09-26T23:50:00Z", "CargoTransfer",
                                Transfers=[{"Type": "tritium", "Count": 28, "Direction": "tocarrier"}]))
        self.assertNotIn("tritium", st["lines"])


class CarrierFuel(unittest.TestCase):

    def test_burn_matches_real_jumps(self):
        """The author's recorded jumps (ly, tritium burned, capacity used, depot before the jump)."""
        for ly, burned, used, depot in ((491.8, 121, 21504, 509), (34.14, 13, 20832, 101), (494.63, 125, 22399, 1000),
                                        (348.35, 89, 22399, 875), (497.2, 118, 20112, 385)):
            self.assertEqual(cargo.carrier_burn(ly, used, depot), burned, (ly, used, depot))

    def test_reserved_space_weighs_nothing(self):
        """Space a buy order reserves is not cargo: the game's own JumpRangeCurr (the jump the depot pays for in full)
        matches the formula only without it. The author's CarrierStats (in-game data), 4,500 t and 2,065 t reserved:
        counted as cargo, the first read 54 t for a 50 t jump of 198.6 ly (the review, 2026-10-12)."""
        for fuel, reach, space in ((50, 198.627258, {"TotalCapacity": 25000, "Crew": 6150, "Cargo": 13399, "CargoSpaceReserved": 4500,
                                                     "ShipPacks": 0, "ModulePacks": 712, "FreeSpace": 239}),
                                   (11, 27.241772, {"TotalCapacity": 25000, "Crew": 4270, "Cargo": 14769, "CargoSpaceReserved": 2065,
                                                    "ShipPacks": 0, "ModulePacks": 0, "FreeSpace": 3896})):
            st = cargo.carrier_fold(CARRIER, [("2026-01-01T00:00:00Z", {"event": "CarrierStats", "CarrierID": CARRIER,
                                                                        "FuelLevel": fuel, "JumpRangeCurr": reach, "SpaceUsage": space})])
            self.assertEqual(st["stats"]["used"], space["TotalCapacity"] - space["FreeSpace"] - space["CargoSpaceReserved"])
            self.assertEqual(cargo.carrier_burn(reach, st["stats"]["used"], fuel), fuel, (fuel, reach))

    def test_jumps(self):
        # the author's carrier on 2026-10-07: depot 668 t, 13,531 t in the hold, 17,355 t of capacity used
        self.assertEqual(cargo.carrier_jumps(668, 13531, 17355), 151)
        self.assertEqual(cargo.carrier_jumps(100, 0, 20000), 0)   # not even one jump
        self.assertIsNone(cargo.carrier_jumps(668, 100, None))


class CargoState(unittest.TestCase):
    """Journals.handle_cargo, read_market, read_cargo_file and State.cargo_summary / carrier_tritium / cargo_recount."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def feed(self, j, fx):
        for n, e in enumerate(fx["events"]):
            j.line_source = f"Journal.test.log:{n}"
            j.handle(e)
        j.line_source = ""

    def write_market(self, fx):
        with open(os.path.join(self.dir, "Market.json"), "w", encoding="utf-8") as f:
            json.dump(dict(fx["market"], event="Market"), f)

    def test_an_older_dock_read_late_does_not_move_the_market(self):
        """A legacy folder's old Docked imported after the live one (review 2026-10-11): the market a CargoTransfer is
        filed under stays the newer dock's."""
        dock = lambda ts, mid: {"timestamp": ts, "event": "Docked", "StationName": "S", "StationType": "FleetCarrier",
                                "MarketID": mid, "StarSystem": "X", "SystemAddress": 1}
        self.j.handle(dock("2026-10-01T00:00:00Z", 7))
        self.j.handle(dock("2025-01-01T00:00:00Z", 99))   # read late, from long ago
        self.assertEqual(self.j.cargo_dock, 7)
        self.j.handle(dock("2026-10-02T00:00:00Z", 8))    # a newer one still moves it
        self.assertEqual(self.j.cargo_dock, 8)

    def test_summary_rereads_the_same(self):
        fx, _, _ = real()
        self.feed(self.j, fx)
        self.write_market(fx)
        self.assertTrue(self.j.read_market(self.dir))
        self.assertFalse(self.j.read_market(self.dir))   # read once
        # names your journal has not given: known from Spansh's list (S57)
        self.state.spansh_commodities = {"ts": time.time(), "norm": {"metaalloys": "Meta-Alloys", "modularterminals": "Modular Terminals"}}
        out, status = self.state.cargo_recount({"Meta-Alloys": 3, "Modular Terminals": 6, "Tritium": 5})
        self.assertEqual(status, 200)
        self.assertEqual(out["skipped"], ["tritium"])   # confirmed by the market: left as it says
        c = self.state.cargo_summary()["carrier"]
        self.assertEqual((c["total"], c["reported"], c["gap"]), (16085, 16085, 0))
        self.assertEqual(next(x for x in c["lines"] if x["id"] == "metaalloys")["state"], "entered")
        # a journal re-read (cargo_events cleared, the market and counts kept) gives the same lines
        before = c["lines"]
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual(self.db.execute("SELECT count(*) FROM cargo_events").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM carrier_markets").fetchone()[0], 1)
        j2 = ed_outrider.Journals(self.db)
        self.feed(j2, fx)
        s2 = ed_outrider.State(self.db, j2, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.assertEqual(s2.cargo_summary()["carrier"]["lines"], before)

    def test_login_docked_counts_as_a_dock(self):
        """Review 2026-10-08 #2: a session that starts docked (a login, a respawn) writes a Location with Docked, not a
        Docked event. A transfer to the carrier straight after it was dropped for want of a market, for good."""
        self.j.line_source = "Journal.test.log:1"
        self.j.handle(ev("2026-10-08T09:00:00Z", "Undocked", StationName="Somewhere", MarketID=5))
        self.j.line_source = "Journal.test.log:2"
        self.j.handle(ev("2026-10-08T10:00:00Z", "Location", Docked=True, StationName="OUT OF THE BLUE",
                         StationType="FleetCarrier", MarketID=CARRIER, StarSystem="Smojooe AR-E b25-8",
                         SystemAddress=1, StarPos=[1.0, 2.0, 3.0], StationServices=["exploration", "vistagenomics"]))
        self.j.line_source = "Journal.test.log:3"
        self.j.handle(ev("2026-10-08T10:01:00Z", "CargoTransfer",
                         Transfers=[{"Type": "tritium", "Count": 100, "Direction": "tocarrier"}]))
        rows = self.db.execute("SELECT event, market FROM cargo_events").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("CargoTransfer", CARRIER)])
        self.assertEqual((self.j.docked["market_id"], self.j.docked["has_vista"]), (CARRIER, True))
        # a ride in someone else's ship is no dock of yours
        self.j.handle(ev("2026-10-08T11:00:00Z", "Location", Docked=True, Multicrew=True, StationName="Elsewhere",
                         StationType="Coriolis", MarketID=77, StarSystem="X", SystemAddress=2, StarPos=[0, 0, 0]))
        self.assertEqual(self.j.cargo_dock, CARRIER)

    def test_srv_mining_stays_out_of_the_ship(self):
        """Review 2026-10-08 #8: the Rhino's refinery (MiningRefined) and scoop (CollectCargo) are the SRV's hold."""
        self.j.handle(ev("2026-10-08T09:00:00Z", "MarketBuy", MarketID=1, Type="gold", Count=10, BuyPrice=9000))
        self.j.handle(ev("2026-10-08T09:10:00Z", "LaunchSRV", SRVType="mev_rhino", SRVType_Localised="Rhino",
                         PlayerControlled=True, ID=1))
        for n in range(3):
            self.j.handle(ev(f"2026-10-08T09:1{n + 1}:00Z", "MiningRefined", Type="$lowtemperaturediamond_name;"))
        self.j.handle(ev("2026-10-08T09:15:00Z", "CollectCargo", Type="gold", Stolen=False))
        self.assertEqual({k: v["count"] for k, v in self.j.ship_cargo["lines"].items()}, {"gold": 10})
        self.j.handle(ev("2026-10-08T09:20:00Z", "DockSRV", SRVType="mev_rhino", ID=1))
        self.j.handle(ev("2026-10-08T09:30:00Z", "CollectCargo", Type="gold", Stolen=False))   # the ship's scoop again
        self.assertEqual(self.j.ship_cargo["lines"]["gold"]["count"], 11)

    def test_tile_tritium(self):
        """The tile's tritium only while tritium is on a sell order (confirmed); else the tile is as before."""
        fx, _, _ = real()
        self.feed(self.j, fx)
        self.assertIsNone(self.state.carrier_summary() and self.state.carrier_tritium())   # no market read yet
        self.write_market(fx)
        self.j.read_market(self.dir)
        t = self.state.carrier_tritium()
        self.assertEqual(t, {"depot": 668, "total": 14199, "jumps": 151})
        self.j.line_source = "Journal.test.log:9999"
        self.j.handle(ev("2026-10-07T11:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER, CarrierType="FleetCarrier",
                         BlackMarket=False, Commodity="tritium", CancelTrade=True))
        self.assertIsNone(self.state.carrier_tritium())

    def test_the_carrier_is_folded_again_only_when_its_history_changes(self):   # S66
        """The carrier's fold is keyed on its own history (carrier_version), not on every change to the ship's hold:
        mining, scooping or buying moved cargo_version and folded the whole carrier history again each time."""
        fx, _, _ = real()
        self.feed(self.j, fx)
        folds, fold = [], cargo.carrier_fold
        with unittest.mock.patch.object(cargo, "carrier_fold", lambda *a: folds.append(1) or fold(*a)):
            first = self.state.carrier_cargo()
            self.assertIs(self.state.carrier_cargo(), first)
            self.assertEqual(len(folds), 1)
            before = self.j.cargo_version
            self.j.line_source = "Journal.test.log:9000"
            self.j.handle(ev("2026-10-07T10:30:00Z", "CollectCargo", Type="gold", Stolen=False))   # the ship's hold only
            self.assertGreater(self.j.cargo_version, before)
            self.state.carrier_cargo()
            self.assertEqual(len(folds), 1)
            self.write_market(fx)
            self.assertTrue(self.j.read_market(self.dir))   # a Market.json read at your carrier
            self.state.carrier_cargo()
            self.assertEqual(len(folds), 2)
            self.j.line_source = "Journal.test.log:9999"   # one of the carrier's own events
            self.j.handle(ev("2026-10-07T11:00:00Z", "CarrierTradeOrder", CarrierID=CARRIER, CarrierType="FleetCarrier",
                             BlackMarket=False, Commodity="tritium", CancelTrade=True))
            self.state.carrier_cargo()
            self.assertEqual(len(folds), 3)
            self.j.reload()                                # a rolled-back tick: folded from what the database holds
            self.state.carrier_cargo()
            self.assertEqual(len(folds), 4)

    def test_market_elsewhere_ignored(self):
        fx, _, _ = real()
        self.feed(self.j, fx)
        with open(os.path.join(self.dir, "Market.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-10-07T12:00:00Z", "event": "Market", "MarketID": 128016896,
                       "StationType": "Coriolis", "Items": [item("gold", stock=5, buy=1)]}, f)
        self.assertFalse(self.j.read_market(self.dir))

    def test_cargo_json(self):
        """Cargo.json is the ship's whole hold (the journal's Cargo then lists only the count)."""
        self.j.line_source = "Journal.test.log:1"
        self.j.handle(ev("2026-10-07T09:00:00Z", "MarketBuy", MarketID=1, Type="gold", Count=10, BuyPrice=9000))
        with open(os.path.join(self.dir, "Cargo.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-10-07T09:00:02Z", "event": "Cargo", "Vessel": "Ship", "Count": 12,
                       "Inventory": [{"Name": "gold", "Count": 10, "Stolen": 0},
                                     {"Name": "drones", "Name_Localised": "Limpet", "Count": 2, "Stolen": 0}]}, f)
        self.assertTrue(self.j.read_cargo_file(self.dir))
        self.assertFalse(self.j.read_cargo_file(self.dir))   # not again
        ship = self.state.cargo_summary()["ship"]
        self.assertEqual([(x["name"], x["count"], x["avg"]) for x in ship["lines"]], [("Gold", 10, 9000), ("Limpet", 2, None)])
        self.assertEqual(ship["count"], 12)

    def test_limpets_bought_sold_and_launched(self):
        """2026-10-19: 200 limpets bought, the game wrote a Cargo with only the count and left Cargo.json as it was
        (the hold empty), so the hold had no limpets. BuyDrones / SellDrones / LaunchDrone move them themselves."""
        with open(os.path.join(self.dir, "Cargo.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-10-18T22:56:48Z", "event": "Cargo", "Vessel": "Ship", "Count": 0,
                       "Inventory": []}, f)
        self.assertTrue(self.j.read_cargo_file(self.dir))
        self.j.handle(ev("2026-10-18T23:08:55Z", "BuyDrones", Type="Drones", Count=200, BuyPrice=101, TotalCost=20200))
        self.j.handle(ev("2026-10-18T23:08:55Z", "Cargo", Vessel="Ship", Count=200))
        self.assertFalse(self.j.read_cargo_file(self.dir))   # the file is older than the purchase: kept out
        held = lambda: {k: v["count"] for k, v in self.j.ship_cargo["lines"].items() if v["count"]}
        self.assertEqual(held(), {"drones": 200})
        with unittest.mock.patch.object(self.j, "handle_commander", wraps=self.j.handle_commander) as cmdr:
            self.j.handle(ev("2026-10-18T23:12:00Z", "LaunchDrone", Type="Prospector"))
            self.j.handle(ev("2026-10-18T23:13:00Z", "LaunchDrone", Type="Collection"))
        self.assertEqual(held(), {"drones": 198})
        self.assertEqual(cmdr.call_count, 2)   # still counted in CMDR → Sessions as well
        self.j.handle(ev("2026-10-18T23:40:00Z", "SellDrones", Type="Drones", Count=8, SellPrice=101, TotalSale=808))
        self.assertEqual(held(), {"drones": 190})
        self.j.handle(ev("2026-10-18T23:00:00Z", "BuyDrones", Type="Drones", Count=5, BuyPrice=101, TotalCost=505))
        self.assertEqual(held(), {"drones": 190})   # older than the hold folded (a legacy folder read late)

    def test_recount_errors(self):
        self.assertEqual(self.state.cargo_recount({"gold": 1})[1], 409)   # no carrier yet
        fx, _, _ = real()
        self.feed(self.j, fx)
        for bad in (None, {}, {"gold": -1}, {"gold": 1.5}, {"gold": True}, {"": 3}, {"gold": 10 ** 6}):
            self.assertEqual(self.state.cargo_recount(bad)[1], 400, bad)

    def test_recount_refuses_typos(self):   # S57
        """A name that is no commodity is refused with up to three close names (it made a line of its own, never moved
        again); Spansh's list (the copy kept: its real names) adds the commodities your journal has not named, by
        Spansh's spelling under the journal's id (Occupied Escape Pod: occupiedcryopod, not occupiedescapepod, which no
        journal event would move). Without that list only your journal's."""
        fx, _, _ = real()
        self.feed(self.j, fx)
        out, status = self.state.cargo_recount({"Tritum": 5})
        self.assertEqual(status, 400)
        self.assertEqual(out["suggestions"][0], "Tritium")
        self.assertIn("Did you mean: Tritium", out["error"])
        self.assertIn("only names from your journal", out["error"])   # no Spansh list yet
        self.assertEqual(self.state.cargo_recount({"Grandidierite": 5})[1], 400)   # not in this journal
        self.state.spansh_commodities = {"ts": time.time(), "norm": {cargo.norm(n): n for n in spansh_commodity_names()}}
        out, status = self.state.cargo_recount({"Titanum": 5, "Grandidierite": 2})
        self.assertEqual(status, 400)   # nothing saved: one bad name refuses the lot
        self.assertEqual(out["name"], "Titanum")
        self.assertEqual(out["suggestions"][:2], ["Titanium", "Tritium"])
        self.assertLessEqual(len(out["suggestions"]), 3)
        self.assertNotIn("only names from your journal", out["error"])
        self.assertEqual(self.db.execute("SELECT count(*) FROM carrier_counts").fetchone()[0], 0)
        out, status = self.state.cargo_recount({"grandidierite": 2, "Low Temperature Diamonds": 3, "void opal": 4,
                                                "Occupied Escape Pod": 1, "Agri-Medicines": 6, "Micro-Weave Cooling Hoses": 7})
        self.assertEqual(status, 200)
        rows = {r[0]: r[1] for r in self.db.execute("SELECT commodity, name FROM carrier_counts")}
        # Spansh's spelling kept, under the journal's id (outrider.cargo.SPANSH_IDS where the letters differ)
        self.assertEqual(rows, {"grandidierite": "Grandidierite", "lowtemperaturediamond": "Low Temperature Diamonds",
                                "opal": "Void Opal", "occupiedcryopod": "Occupied Escape Pod",
                                "agriculturalmedicines": "Agri-Medicines", "coolinghoses": "Micro-weave Cooling Hoses"})
        lines = {x["id"]: x["name"] for x in self.state.cargo_summary()["carrier"]["lines"]}
        self.assertEqual(lines["lowtemperaturediamond"], "Low Temperature Diamonds")

    def test_spansh_ids_name_real_commodities(self):
        """SPANSH_IDS' names are Spansh's own (its list, kept as a fixture), each one's letters differ from its id, and
        spansh_id gives the letters for every other name."""
        real_names = {cargo.norm(n) for n in spansh_commodity_names()}
        for name, i in cargo.SPANSH_IDS.items():
            self.assertIn(cargo.norm(name), real_names, name)
            self.assertNotEqual(cargo.norm(name), cargo.norm(i), name)
        self.assertEqual(cargo.spansh_id("Occupied Escape Pod"), "occupiedcryopod")
        self.assertEqual(cargo.spansh_id("Void Opal"), "opal")
        self.assertEqual(cargo.spansh_id("Meta-Alloys"), "metaalloys")

    def test_recount_route_fetches_spansh_list_once(self):   # S57
        """POST /api/cargo/recount: a name your journal does not know and no copy of Spansh's list yet: the list is
        fetched and the counts asked again; a typo is still refused, with its suggestions."""
        from aiohttp.test_utils import TestClient, TestServer
        fx, _, _ = real()
        self.feed(self.j, fx)
        fetched = []

        async def commodity_list():
            fetched.append(1)
            self.state.spansh_commodities = {"ts": time.time(), "norm": {"grandidierite": "Grandidierite", "tritium": "Tritium"}}
            return self.state.spansh_commodities["norm"]
        self.state.commodity_list = commodity_list

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r1 = await c.post("/api/cargo/recount", json={"counts": {"Grandidierite": 2}})
                r2 = await c.post("/api/cargo/recount", json={"counts": {"Grandiderite": 2}})
                return r1.status, r2.status, await r2.json()
        s1, s2, body = asyncio.run(go())
        self.assertEqual((s1, s2, len(fetched)), (200, 400, 1))
        self.assertEqual(body["suggestions"], ["Grandidierite"])


STATS_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "carrier_stats.json")


def real_stats():
    """The author's CarrierStats of 2026-10-12 (in-game data): Finance and Crew whole, the Redemption office suspended."""
    with open(STATS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def crew_service(ts, role, op, carrier=CARRIER):
    return ev(ts, "CarrierCrewServices", CarrierID=carrier, CrewRole=role, Operation=op, CrewName="Someone")


class CarrierStatsFold(unittest.TestCase):
    """The carrier's balance, crew and the trip's tritium (S61, S55 B, S13 A): carrier_fold's finance and crew,
    carrier_upkeep, carrier_trip. Pure."""

    def test_finance_and_crew(self):
        s = real_stats()
        st = cargo.carrier_fold(CARRIER, [(s["timestamp"], s)])
        self.assertEqual(st["finance"], {"balance": 1328648923, "reserve": 1000001263, "available": 328647660,
                                         "ts": "2026-10-12T20:11:21Z"})
        roles = st["crew"]["roles"]
        self.assertEqual((roles["Exploration"], roles["VistaGenomics"], roles["VoucherRedemption"], roles["Shipyard"]),
                         ("on", "on", "suspended", "off"))   # Activated without Enabled would be on; not Activated, off
        # the core 5M + refuel, repair, rearm 1.5M each + UC 1.85M + Vista 1.5M + the suspended Redemption office 0.85M
        # (published rates; the balance fell 13,579,218 cr over the author's upkeep day of 2026-10-08)
        self.assertEqual(cargo.carrier_upkeep(roles), 13_700_000)
        self.assertEqual(cargo.upkeep_weeks(st["finance"]["balance"], 13_700_000), 96.9)
        self.assertEqual(cargo.upkeep_weeks(-5, 13_700_000), 0.0)   # AvailableBalance can be negative: the balance too
        self.assertIsNone(cargo.upkeep_weeks(None, 13_700_000))

    def test_crew_services_between_stats(self):
        """CarrierCrewServices (paused, resumed, removed, installed) changes the crew until the next CarrierStats; another
        carrier's says nothing about yours."""
        s = real_stats()
        events = [(s["timestamp"], s), ("2026-10-12T21:00:00Z", crew_service("2026-10-12T21:00:00Z", "Exploration", "Pause")),
                  ("2026-10-12T21:01:00Z", crew_service("2026-10-12T21:01:00Z", "VistaGenomics", "Pause", carrier=999)),
                  ("2026-10-12T21:02:00Z", crew_service("2026-10-12T21:02:00Z", "Shipyard", "Activate")),
                  ("2026-10-12T21:03:00Z", crew_service("2026-10-12T21:03:00Z", "Refuel", "Replace"))]
        st = cargo.carrier_fold(CARRIER, events)
        roles = st["crew"]["roles"]
        self.assertEqual((roles["Exploration"], roles["VistaGenomics"], roles["Shipyard"], roles["Refuel"]),
                         ("suspended", "on", "on", "on"))
        self.assertEqual(st["crew"]["ts"], "2026-10-12T21:02:00Z")   # Replace (another crew member) changes nothing
        self.assertEqual(cargo.carrier_upkeep(roles), 13_700_000 - 1_850_000 + 700_000 + 6_500_000)
        later = dict(s, timestamp="2026-10-13T00:00:00Z")   # the next CarrierStats says it whole again
        st = cargo.carrier_fold(CARRIER, events + [(later["timestamp"], later)])
        self.assertEqual((st["crew"]["roles"]["Exploration"], st["crew"]["roles"]["Shipyard"]), ("on", "off"))

    def test_trip(self):
        # one leg: the author's recorded jump of 491.8 ly (121 t burned, 21,504 t used, a depot of 509 t)
        self.assertEqual(cargo.carrier_trip(491.8, 509, 21504),
                         {"jumps": 1, "burn": 121, "depot": 509, "short": 0, "depot_after": 388})
        # 1,200 ly: three equal legs of 400 ly, each lighter than the last by what it burned
        t = cargo.carrier_trip(1200, 600, 20000)
        self.assertEqual((t["jumps"], t["burn"], t["short"], t["depot_after"]), (3, 288, 0, 312))
        self.assertLess(cargo.carrier_trip(3000, 1000, 20000)["burn"], 6 * cargo.carrier_burn(500, 20000, 1000))
        t = cargo.carrier_trip(3000, 300, 20000)   # six 500 ly jumps on a 300 t depot
        self.assertEqual((t["jumps"], t["short"], t["depot_after"]), (6, t["burn"] - 300, 0))
        self.assertEqual(cargo.carrier_trip(500, 1000, 0)["jumps"], 1)   # exactly one jump's reach is one jump
        self.assertEqual(cargo.carrier_trip(491.8, 509, 21504, k=1.1)["burn"], round(1.1 * 121))   # scaled by history
        self.assertIsNone(cargo.carrier_trip(0, 509, 21504))
        self.assertIsNone(cargo.carrier_trip(100, 509, None))

    def test_trip_top_up(self):
        """The hold's tritium covers what the depot lacks before the jumps only while the depot (1,000 t) can take it all;
        past that, only topped up again on the way; with too little in the hold, not at all."""
        t = cargo.carrier_trip(3000, 300, 20000)   # six 500 ly jumps on a 300 t depot: a few hundred t short
        self.assertEqual(cargo.trip_top_up(t, 3000, 2000, 22000), "before")
        self.assertIsNone(cargo.trip_top_up(t, 3000, t["short"] - 1, 22000))
        self.assertIsNone(cargo.trip_top_up(cargo.carrier_trip(500, 1000, 0), 500, 2000, 2000))   # nothing short
        t = cargo.carrier_trip(9000, 40, 22000)   # eighteen jumps: short well over the 960 t one top-up gives
        self.assertGreater(t["short"], cargo.CARRIER_DEPOT_MAX - 40)
        self.assertEqual(cargo.trip_top_up(t, 9000, 4000, 22000), "on_the_way")
        self.assertIsNone(cargo.trip_top_up(t, 9000, t["short"] // 2, 22000))


class CarrierTile(unittest.TestCase):
    """State.carrier_summary's trip, booked jump, services and finance, and your carrier among the nearest places to
    sell (S13 A, S55, S61)."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.n = 0
        self.feed(real_stats())
        self.feed(ev("2026-10-12T20:12:00Z", "CarrierLocation", CarrierType="FleetCarrier", CarrierID=CARRIER,
                     StarSystem="Home", SystemAddress=111))
        self.j.carrier.update(x=0.0, y=0.0, z=0.0)
        self.j.pos = {"id64": 9, "name": "Here", "x": 1200.0, "y": 0.0, "z": 0.0, "ts": "2026-10-12T20:13:00Z"}

    def feed(self, e):
        self.n += 1
        self.j.line_source = f"Journal.test.log:{self.n}"
        self.j.handle(e)
        self.j.line_source = ""

    def test_trip_to_you(self):
        """'it → you ≈ 3 carrier jumps · ≈ T t tritium · depot 668 t: X t short': the capacity used is the CarrierStats'
        (25,000 − 7,645 free, nothing reserved), the depot its FuelLevel."""
        c = self.state.carrier_summary()
        want = cargo.carrier_trip(1200.0, 668, 25000 - 7645)
        self.assertEqual(c["trip"], dict(want, hold=None, covered=False, top_up=None))
        self.assertEqual(c["trip"]["jumps"], 3)
        self.j.pos = dict(self.j.pos, x=4000.0)   # far: the depot runs short, and nothing confirmed in the hold covers it
        t = self.state.carrier_summary()["trip"]
        self.assertTrue(t["short"] > 0 and not t["covered"])
        self.j.pos = dict(self.j.pos, id64=111, x=0.0)   # in its system: no trip
        self.assertIsNone(self.state.carrier_summary()["trip"])

    def test_trip_covered_by_the_hold(self):
        """A confirmed tritium line (a sell order at your carrier) that covers what the depot lacks: amber, 'enough
        after topping up'."""
        self.j.pos = dict(self.j.pos, x=4000.0)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, "Market.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-10-12T20:20:00Z", "event": "Market", "MarketID": CARRIER, "StationType": "FleetCarrier",
                       "Items": [item("tritium", stock=5000, buy=50000)]}, f)
        self.assertTrue(self.j.read_market(d))
        t = self.state.carrier_summary()["trip"]
        self.assertEqual((t["hold"], t["covered"], t["top_up"]), (5000, True, "before"))
        self.assertGreater(t["short"], 0)
        # the depot holds 1,000 t: a 40 t depot 5,000 ly away lacks more than one top-up gives; the hold still covers it,
        # topped up again on the way
        self.j.carrier.update(fuel=40)
        self.j.pos = dict(self.j.pos, x=5000.0)
        t = self.state.carrier_summary()["trip"]
        self.assertGreater(t["short"], cargo.CARRIER_DEPOT_MAX - 40)
        self.assertEqual((t["covered"], t["top_up"]), (True, "on_the_way"))

    def test_booked_jump_burn(self):
        """'(432 ly jump ≈ T t; depot after ≈ D t)': the booked jump's burn from the carrier's place to its destination."""
        self.state.bases[222] = ("spansh", {"name": "Far", "x": 432.0, "y": 0.0, "z": 0.0})
        self.feed(ev("2026-10-12T20:14:00Z", "CarrierJumpRequest", CarrierID=CARRIER, SystemName="Far", SystemAddress=222,
                     DepartureTime="2026-10-12T20:30:00Z"))
        pl = self.state.carrier_summary()["planned"]
        self.assertEqual((pl["jump_ly"], pl["burn"], pl["depot_after"]),
                         (432.0, cargo.carrier_burn(432.0, 25000 - 7645, 668), 668 - cargo.carrier_burn(432.0, 25000 - 7645, 668)))

    def test_services_and_finance(self):
        c = self.state.carrier_summary()
        self.assertEqual((c["has_uc"], c["has_vista"], c["suspended"]), (True, True, ["Redemption office"]))
        f = c["finance"]
        self.assertEqual((f["balance"], f["upkeep"], f["weeks"], f["warn"], f["rates"]),
                         (1328648923, 13_700_000, 96.9, False, "published"))
        # UC paused in the carrier's management: suspended, in red, and gone from the services
        self.feed(crew_service("2026-10-12T21:00:00Z", "Exploration", "Pause"))
        c = self.state.carrier_summary()
        self.assertEqual((c["has_uc"], c["suspended"]), (False, ["UC", "Redemption office"]))
        # a newer Docked listing it (resumed since) wins over the crew's older word
        self.feed(ev("2026-10-12T22:00:00Z", "Docked", StationName="OUT OF THE BLUE", StationType="FleetCarrier",
                     MarketID=CARRIER, StarSystem="Home", SystemAddress=111, StationServices=["dock", "exploration", "vistagenomics"]))
        c = self.state.carrier_summary()
        self.assertEqual((c["has_uc"], c["suspended"]), (True, ["Redemption office"]))
        # under four weeks of upkeep: amber
        low = dict(real_stats(), timestamp="2026-10-12T23:00:00Z")
        low["Finance"] = dict(low["Finance"], CarrierBalance=40_000_000)
        self.feed(low)
        f = self.state.carrier_summary()["finance"]
        self.assertEqual((f["weeks"], f["warn"]), (2.9, True))

    def sellers(self):
        uc = [{"name": "G0X-85Z", "type": "Drake-Class Carrier", "system": "Old Place", "updated_at": "2026-01-01T00:00:00Z",
               "x": 1190.0, "y": 0.0, "z": 0.0, "distance": 10},   # Spansh's stale report of your carrier
              {"name": "Far Port", "type": "Coriolis Starport", "system": "Far", "updated_at": "2026-10-01T00:00:00Z",
               "x": 2500.0, "y": 0.0, "z": 0.0, "distance": 1300}]
        ed_outrider.meta_set(self.db, "sellers", {"pos": {"x": 1200.0, "y": 0.0, "z": 0.0, "name": "Here"},
                                                  "fetched": time.time(), "uc": uc, "vista": []})
        return self.state.sellers_summary()

    def test_your_carrier_among_the_sellers(self):
        """S55 A: your carrier from the journal (where it is now, 1,200 ly away: 3 carrier jumps), never Spansh's stale
        report of it; in the Vista list too while Vista is on."""
        s = self.sellers()
        uc = s["uc"]
        self.assertEqual([x["name"] for x in [uc["nearest"]]], ["G0X-85Z"])
        self.assertEqual((uc["nearest"]["distance"], uc["nearest"]["system"], uc["nearest"]["yours"],
                          uc["nearest"]["carrier_jumps"]), (1200.0, "Home", True, 3))
        self.assertEqual(uc["fresh"]["name"], "G0X-85Z")
        self.assertEqual(s["vista"]["nearest"]["name"], "G0X-85Z")
        # UC paused: neither your carrier nor Spansh's report of it sells UC
        self.feed(crew_service("2026-10-12T21:00:00Z", "Exploration", "Pause"))
        s = self.sellers()
        self.assertEqual(s["uc"]["nearest"]["name"], "Far Port")
        self.assertEqual(s["vista"]["nearest"]["name"], "G0X-85Z")
        # decommissioned: gone from both
        self.feed(ev("2026-10-13T10:00:00Z", "CarrierDecommission", CarrierID=CARRIER, ScrapRefund=1, ScrapTime=1000))
        s = self.sellers()
        self.assertIsNone(s["vista"]["nearest"])
        self.assertEqual(s["uc"]["nearest"]["name"], "Far Port")

    def test_your_carrier_without_spansh(self):
        """No Spansh answer yet (offline): your carrier is still a place to sell."""
        s = self.state.sellers_summary()
        self.assertEqual((s["uc"]["nearest"]["name"], s["vista"]["nearest"]["name"]), ("G0X-85Z", "G0X-85Z"))


MOVES_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "carrier_moves.json")


def real_moves():
    """The author's carrier on 2026-09-26/27 (in-game data, its CarrierStats cut to the fields used): eleven jumps booked
    and made, nine of them aboard (CarrierJump with StarPos), a deposit before the ninth, a squadron carrier's line."""
    with open(MOVES_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


SMOJOO = 16013114550881   # the tenth jump's system: reached while not aboard (no StarPos in the carrier's lines)


class CarrierBurns(unittest.TestCase):
    """S13 B: the carrier's measured jumps (carrier_burns) and its factor on the formula (burn_factor). Pure."""

    def test_real_jumps(self):
        """The author's nine jumps aboard, each between two depot readings: burned exactly what the formula says; the
        ninth's reading before it is the deposit's Total (the depot filled from the ship)."""
        events = [(e["timestamp"], e) for e in real_moves()]
        s = cargo.carrier_burns(CARRIER, events)
        self.assertEqual([(x["burned"], x["formula"]) for x in s],
                         [(115, 115), (112, 112), (113, 113), (114, 114), (114, 114), (113, 113), (112, 112), (113, 113), (111, 111)])
        self.assertEqual((s[0]["ts"], s[0]["ly"]), ("2026-09-26T20:26:10Z", 496.29))   # the departure time
        # the tenth system known elsewhere (where: the server's locate), its jump measured too
        s = cargo.carrier_burns(CARRIER, events, lambda i: (-3791.21875, -2.4375, 3026.75) if i == SMOJOO else None)
        self.assertEqual((len(s), s[-1]["burned"], s[-1]["formula"]), (10, 111, 111))
        self.assertEqual(cargo.burn_factor(s), {"k": 1.0, "n": 10, "raw": 1.0})
        self.assertEqual(cargo.carrier_burns(999, events), [])   # another carrier's history says nothing

    def jump(self, ts, frm, to, ly=None):
        """A booked jump from `frm` to `to` (positions on the x axis, ids = x), confirmed by a CarrierLocation."""
        return [(ts + ":00Z", ev(ts + ":00Z", "CarrierJumpRequest", CarrierID=CARRIER, SystemAddress=to,
                                 DepartureTime=ts + ":30Z")),
                (ts + ":30Z", ev(ts + ":30Z", "CarrierLocation", CarrierID=CARRIER, CarrierType="FleetCarrier", SystemAddress=to))]

    def test_what_is_not_a_sample(self):
        where = lambda i: (float(i), 0.0, 0.0)   # noqa: E731
        burn = cargo.carrier_burn(400, 1000, 900)
        start = [("2026-01-01T00:00:00Z", ev("2026-01-01T00:00:00Z", "CarrierLocation", CarrierID=CARRIER, SystemAddress=1000))]
        one = start + [("2026-01-01T00:01:00Z", stats("2026-01-01T00:01:00Z", 0, fuel=900, used=1000))] + \
            self.jump("2026-01-01T00:02", 1000, 1400) + [("2026-01-01T00:03:00Z", stats("2026-01-01T00:03:00Z", 0, fuel=900 - burn, used=1000))]
        self.assertEqual([(x["ly"], x["burned"]) for x in cargo.carrier_burns(CARRIER, one, where)], [(400.0, burn)])
        # cancelled before it left: no move, no sample
        cancelled = one[:3] + [("2026-01-01T00:02:10Z", ev("2026-01-01T00:02:10Z", "CarrierJumpCancelled", CarrierID=CARRIER))] + one[3:]
        self.assertEqual(cargo.carrier_burns(CARRIER, cancelled, where), [])
        # two jumps between the same two readings: neither is one jump's burn
        two = one[:-1] + self.jump("2026-01-01T00:02:40", 1400, 1700) + one[-1:]
        two.sort(key=lambda x: x[0])
        self.assertEqual(cargo.carrier_burns(CARRIER, two, where), [])
        # no reading after it yet, or a system nowhere known: nothing measured
        self.assertEqual(cargo.carrier_burns(CARRIER, one[:-1], where), [])
        self.assertEqual(cargo.carrier_burns(CARRIER, one), [])
        # longer than a carrier jumps (a move missed between): not a sample
        far = lambda i: (float(i) * 2, 0.0, 0.0)   # noqa: E731
        self.assertEqual(cargo.carrier_burns(CARRIER, one, far), [])
        # your own cargo moved aboard before the jump weighs: the mass is the stats' plus it
        moved = one[:2] + [("2026-01-01T00:01:30Z", ev("2026-01-01T00:01:30Z", "CargoTransfer", _at=CARRIER,
                                                         Transfers=[{"Type": "gold", "Count": 2000, "Direction": "tocarrier"}]))] + one[2:]
        self.assertEqual(cargo.carrier_burns(CARRIER, moved, where)[0]["formula"], cargo.carrier_burn(400, 3000, 900))

    def test_factor(self):
        mk = lambda ks: [{"k": k} for k in ks]   # noqa: E731
        self.assertIsNone(cargo.burn_factor(mk([1.1, 1.1])))   # fewer than three: the formula alone
        self.assertEqual(cargo.burn_factor(mk([1.0, 1.1, 1.2])), {"k": 1.1, "n": 3, "raw": 1.1})
        self.assertEqual(cargo.burn_factor(mk([1.0, 1.1, 1.2, 1.3])), {"k": 1.15, "n": 4, "raw": 1.15})
        self.assertEqual(cargo.burn_factor(mk([0.3, 0.4, 0.5])), {"k": 0.8, "n": 3, "raw": 0.4})   # held to 0.8-1.2
        self.assertEqual(cargo.burn_factor(mk([2.0] * 3 + [1.05] * 12)), {"k": 1.05, "n": 12, "raw": 1.05})   # the last 12
        # scaled: the trip and the jumps all the tritium gives
        self.assertEqual((cargo.carrier_jumps(1000, 0, 20000), cargo.carrier_jumps(1000, 0, 20000, k=1.2)), (8, 6))
        self.assertEqual((cargo.carrier_jumps(1000, 3000, 20000), cargo.carrier_jumps(1000, 3000, 20000, k=1.2)), (34, 28))


class CarrierHistory(unittest.TestCase):
    """S13 B through the reader: the carrier's movements and deposits kept in cargo_events (CarrierJump by its MarketID,
    never a squadron carrier's or a station's), and State.carrier_summary's tritium scaled by its own jumps."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        for n, e in enumerate(real_moves()):
            self.j.line_source = f"Journal.test.log:{n}"
            self.j.handle(e)
        self.j.line_source = ""

    def test_kept_and_measured(self):
        rows = self.db.execute("SELECT event, count(*) FROM cargo_events WHERE market = ? GROUP BY event", (CARRIER,)).fetchall()
        self.assertEqual(dict((r[0], r[1]) for r in rows),
                         {"CarrierStats": 23, "CarrierJumpRequest": 11, "CarrierLocation": 11, "CarrierJump": 10,
                          "CarrierDepositFuel": 2})
        self.assertEqual(self.db.execute("SELECT count(*) FROM cargo_events WHERE market != ?", (CARRIER,)).fetchone()[0], 0)
        self.assertEqual(self.state.carrier_burn_factor(), {"k": 1.0, "n": 9, "raw": 1.0})
        # a squadron carrier's line and a jump at a station that is not a fleet carrier: not stored
        self.j.handle(ev("2026-09-28T00:00:00Z", "CarrierLocation", CarrierType="SquadronCarrier", CarrierID=5, SystemAddress=7))
        self.j.handle(ev("2026-09-28T00:01:00Z", "CarrierJump", Docked=True, StationType="Coriolis", MarketID=6,
                         StarSystem="X", SystemAddress=8, StarPos=[0, 0, 0]))
        self.assertEqual(self.db.execute("SELECT count(*) FROM cargo_events WHERE market IN (5, 6)").fetchone()[0], 0)

    def test_summary_scaled(self):
        """The trip to you, a booked jump's burn and the tile's jumps all scaled by the carrier's factor."""
        self.j.carrier.update(x=0.0, y=0.0, z=0.0)
        self.j.pos = {"id64": 9, "name": "Here", "x": 1200.0, "y": 0.0, "z": 0.0, "ts": "2026-09-28T00:00:00Z"}
        self.assertEqual(self.state.carrier_summary()["burn_factor"], {"k": 1.0, "n": 9, "raw": 1.0})
        self.state._carrier_k = ((CARRIER, self.j.carrier_version), {"k": 1.1, "n": 12, "raw": 1.1})
        c = self.state.carrier_summary()
        used = self.state.carrier_cargo()["stats"]["used"]
        self.assertEqual(c["trip"]["burn"], cargo.carrier_trip(1200.0, c["fuel"], used, k=1.1)["burn"])
        self.assertGreater(c["trip"]["burn"], cargo.carrier_trip(1200.0, c["fuel"], used)["burn"])
        self.assertEqual(c["burn_factor"]["k"], 1.1)
        self.state.bases[222] = ("spansh", {"name": "Far", "x": 432.0, "y": 0.0, "z": 0.0})
        self.j.handle(ev("2026-09-28T00:10:00Z", "CarrierJumpRequest", CarrierID=CARRIER, CarrierType="FleetCarrier",
                         SystemName="Far", SystemAddress=222, DepartureTime="2026-09-28T00:30:00Z"))
        self.state._carrier_k = ((CARRIER, self.j.carrier_version), {"k": 1.1, "n": 12, "raw": 1.1})
        pl = self.state.carrier_summary()["planned"]
        self.assertEqual(pl["burn"], round(1.1 * cargo.carrier_burn(432.0, used, c["fuel"])))


class Lookup(unittest.TestCase):
    """The Sell / Buy lookup: Spansh's station search (outrider.cargo.market_query / market_rows, State.cargo_lookup)."""

    def test_query(self):
        ref = {"x": 1, "y": 2, "z": 3}
        q = cargo.market_query("Platinum", "sell", 64, ref, within=500, age_days=14, now=1791000000, pad="L")
        f = q["filters"]
        self.assertEqual(f["market"], [{"name": "Platinum", "demand": {"value": [64, 999999999], "comparison": "<=>"}}])
        self.assertNotIn(cargo.CARRIER_TYPE, f["type"]["value"])   # fleet carriers left out
        self.assertEqual(f["has_large_pad"], {"value": True})
        self.assertEqual(f["market_updated_at"]["value"][0], "2026-09-19T04:00:00Z")   # 14 days before
        self.assertEqual(f["distance"], {"min": "0", "max": "500"})
        self.assertEqual(q["sort"], [{"market_sell_price": [{"name": "Platinum", "direction": "desc"}]},
                                     {"distance": {"direction": "asc"}}])   # the same price nearer first
        self.assertEqual(q["reference_coords"], ref)
        q = cargo.market_query("Tritium", "buy", 500, ref, pad="M", carriers=True, sort="near")
        self.assertEqual(list(q["filters"]["market"][0]), ["name", "supply"])
        self.assertNotIn("type", q["filters"])
        self.assertIn("medium_pads", q["filters"])
        self.assertEqual(q["sort"], [{"distance": {"direction": "asc"}}])
        self.assertEqual(cargo.market_query("Gold", "buy", 1, ref)["sort"][0],
                         {"market_buy_price": [{"name": "Gold", "direction": "asc"}]})

    def test_rows_from_a_real_answer(self):
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_market.json"), encoding="utf-8") as f:
            answer = json.load(f)
        rows = cargo.market_rows(answer["results"], "Platinum", "sell", 64, holding=[("Gold", 10), ("Platinum", 64)],
                                 avg=45210, laden=50, now=1791400000)
        self.assertEqual([r["carrier"] for r in rows], [True, True, False, False, False])
        jung = rows[2]
        self.assertEqual((jung["station"], jung["system"], jung["price"], jung["far"], jung["jumps"]),
                         ("Jung Base", "HIP 11402", 302844, True, 7))
        self.assertEqual(jung["profit"], (302844 - 45210) * 64)
        self.assertEqual(jung["value"], 302844 * 64)
        self.assertEqual([a["name"] for a in jung["also"]], ["Gold"])   # what else it buys from your hold
        self.assertTrue(rows[4]["uc"])
        self.assertEqual(rows[4]["services"][:2], ["Refuel", "Repair"])   # the ones that matter, not every desk
        self.assertNotIn("Dock", rows[4]["services"])
        self.assertGreater(jung["age_s"], 0)

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_market.json"), encoding="utf-8") as f:
            answer = json.load(f)
        self.bodies = []

        async def market_search(body):
            self.bodies.append(body)
            return answer

        async def commodity_names():
            return ["Gold", "Meta-Alloys", "Platinum", "Silver", "Tritium"]
        self.sp = types.SimpleNamespace(cached=lambda i: (None, None), market_search=market_search,
                                        commodity_names=commodity_names)
        self.state = ed_outrider.State(self.db, self.j, self.sp, 25)

    def look(self, **q):
        import asyncio
        return asyncio.run(self.state.cargo_lookup({k: str(v) for k, v in q.items()}))

    def test_state_lookup(self):
        self.assertEqual(self.look(commodity="platinum", mode="steal")[1], 400)
        self.assertEqual(self.look(commodity="platinum", mode="sell", within=123)[1], 400)
        self.assertEqual(self.look(commodity="platinum", mode="sell")[1], 409)   # no position yet
        self.j.pos = {"id64": 10477373803, "name": "Sol", "x": 0, "y": 0, "z": 0}
        self.assertEqual(self.look(commodity="unobtainium", mode="sell")[1], 404)
        self.j.ship = {"name": "Sample", "type": "explorer_nx", "cargo_capacity": 64}
        self.j.ship_cargo = cargo.new_ship()
        cargo.ship_apply(self.j.ship_cargo, ev("2026-10-07T09:00:00Z", "MarketBuy", Type="platinum", Count=64, BuyPrice=45210))
        out, status = self.look(commodity="platinum", mode="sell", tons=64, **{"from": "ship"})
        self.assertEqual(status, 200)
        self.assertEqual((out["commodity"], out["pad"], out["avg"], len(out["rows"])), ("Platinum", "L", 45210, 5))
        self.assertEqual(self.bodies[-1]["filters"]["has_large_pad"], {"value": True})   # the ship needs a large pad
        self.assertEqual(out["rows"][2]["profit"], (302844 - 45210) * 64)
        # a journal name matched to Spansh's spelling, letters only; Spansh's list is fetched once
        self.j.commodity_names["metaalloys"] = "Meta Alloys"
        out, status = self.look(commodity="metaalloys", mode="buy", pad="any", carriers=1)
        self.assertEqual((status, out["commodity"], out["pad"]), (200, "Meta-Alloys", None))
        self.assertNotIn("type", self.bodies[-1]["filters"])


def trade_answer():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_trade.json"), encoding="utf-8") as f:
        return json.load(f)


class TradeRoute(unittest.TestCase):
    """Spansh's trade planner as the survey slot's third type (outrider.cargo.trade_rows / trade_text, State
    trade_start_plot, Journals.trade_progress). A real answer: tests/fixtures/spansh_trade.json (from Sol, 2026-10-07)."""
    ts = hwy_ts
    jump = hwy_jump

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()
        self.rows = cargo.trade_rows(trade_answer()["result"])

    def moments(self):
        return [(m["what"], m["text"]) for m in self.j.moments if m["kind"] == "trade"]

    def market(self, s, name, stop, commodity):
        self.j.line_source = f"Journal.test.log:{s}"
        self.j.handle({"event": name, "timestamp": self.ts(s), "MarketID": stop["market_id"],
                       "Type": cargo.norm(commodity), "Type_Localised": commodity, "Count": 400,
                       "BuyPrice" if name == "MarketBuy" else "SellPrice": 100})

    def test_rows(self):
        r = self.rows
        self.assertEqual([x["station"] for x in r], ["Abraham Lincoln", "Titus City", "Shimizu Hub", "Gareth Edwards Park"])
        self.assertEqual((r[0]["buy"][0]["name"], r[0]["buy"][0]["amount"], r[0]["sell"]), ("Biowaste", 400, []))
        self.assertEqual((r[1]["sell"][0]["name"], r[1]["buy"][0]["name"], r[1]["profit"]), ("Biowaste", "Silver", 15200))
        self.assertEqual((r[3]["cumulative"], r[3]["buy"], round(r[3]["distance"], 1)), (14691200, [], 8.4))
        self.assertEqual(cargo.trade_rows({"error": "x"}), [])
        self.assertEqual(cargo.trade_text(r, 1, cargo.trade_left(r[1], {"sold": ["Biowaste"]})),
                         "Dock at Titus City: buy 400 tonnes of Silver for Shimizu Hub.")

    def test_progress(self):
        """Docked at the start: buying the hop's goods says the next stop; arriving says what to sell and buy; the
        trades made say the hop's profit; the last sale ends the route. Each once."""
        r = self.rows
        self.jump(-100, r[0]["id64"], r[0]["system"], 0)
        self.state.riches_store(r, {"options": {}, "kind": "trade"})
        self.market(-90, "MarketBuy", r[0], "Biowaste")
        self.assertEqual(self.moments()[-1], ("done", "Next stop: Titus City in Yin Sector GW-W c1-26, 27 light years."))
        self.jump(-80, r[1]["id64"], r[1]["system"], 27)
        self.assertEqual(self.moments()[-1], ("next", "Dock at Titus City: sell 400 tonnes of Biowaste, then buy 400 tonnes of Silver for Shimizu Hub."))
        s = self.state.survey_summary()
        self.assertEqual((s["kind"], s["at"], s["left_here"], s["next"]["station"]), ("trade", 1, 2, "Shimizu Hub"))
        self.market(-70, "MarketSell", r[1], "Biowaste")
        self.market(-69, "MarketSell", r[1], "Biowaste")   # a second page of the same sale: nothing new
        self.market(-60, "MarketBuy", r[2], "Silver")      # another market: not this stop's
        self.assertEqual(self.state.survey_summary()["left_here"], 1)
        self.market(-50, "MarketBuy", r[1], "Silver")
        self.assertEqual(self.moments()[-1], ("done", "Hop 1 done, about 15,200 credits. Next stop: Shimizu Hub in Chara, 28 light years."))
        view = self.state.riches_view()["route"]["systems"][1]
        self.assertEqual((view["station"], view["left"], view["sell"][0]["done"], view["buy"][0]["done"]), ("Titus City", 0, True, True))
        for k, (s1, s2) in enumerate(((-40, -35), (-30, -25)), start=2):
            self.jump(s1, r[k]["id64"], r[k]["system"], 30 * k)
            self.market(s2, "MarketSell", r[k], r[k]["sell"][0]["name"])
            if r[k]["buy"]:
                self.market(s2 + 1, "MarketBuy", r[k], r[k]["buy"][0]["name"])
        self.assertEqual(self.moments()[-1], ("complete", "Trade route complete: about 14,691,200 credits in all."))
        self.assertTrue(self.state.survey_summary()["complete"])
        self.assertEqual(len([m for m in self.moments() if m[0] == "done"]), 3)   # stops 0, 1 and 2, once each

    def trade(self, s, name, stop, commodity, count, line=None):
        self.j.line_source = line or f"Journal.test.log:{s}"
        self.j.handle({"event": name, "timestamp": self.ts(s), "MarketID": stop["market_id"],
                       "Type": cargo.norm(commodity), "Type_Localised": commodity, "Count": count,
                       "BuyPrice" if name == "MarketBuy" else "SellPrice": 100})

    def test_partial_trades(self):
        """Codex F4: one tonne of a planned 400 ticked the commodity off, said the hop's profit and could end the route.
        The tonnes add up now, each journal line once; undocking with part traded is moving on, said with the shortfall."""
        r = self.rows
        self.jump(-100, r[0]["id64"], r[0]["system"], 0)
        self.state.riches_store(r, {"options": {}, "kind": "trade"})
        self.trade(-95, "MarketBuy", r[0], "Biowaste", 1)
        self.trade(-95, "MarketBuy", r[0], "Biowaste", 1)                 # the same line again (a re-read): once
        self.trade(-94, "MarketBuy", r[0], "Biowaste", 199)
        self.assertEqual(self.moments(), [])                              # 200 of 400: not done
        view = self.state.riches_view()["route"]["systems"][0]["buy"][0]
        self.assertEqual((view["traded"], view["done"]), (200, False))
        self.trade(-93, "MarketBuy", r[0], "Biowaste", 200)
        self.assertEqual(self.moments()[-1][0], "done")                   # 400: done
        self.jump(-80, r[1]["id64"], r[1]["system"], 27)
        self.assertIn("sell 400 tonnes of Biowaste", self.moments()[-1][1])
        self.trade(-70, "MarketSell", r[1], "Biowaste", 100)
        self.assertEqual(self.state.survey_summary()["left_here"], 2)
        self.j.handle({"event": "Undocked", "timestamp": self.ts(-65), "MarketID": r[1]["market_id"], "StationName": "x"})
        self.assertEqual(self.moments()[-1], ("done", "Hop 1 done, sold 100 of 400 tonnes of Biowaste; bought none of "
                                                      "400 tonnes of Silver. Next stop: Shimizu Hub in Chara, 28 light years."))
        view = self.state.riches_view()["route"]["systems"][1]
        self.assertEqual((view["left"], view["sell"][0]["done"], view["sell"][0]["traded"], view["buy"][0]["done"]),
                         (0, False, 100, False))
        n = len(self.moments())
        self.j.handle({"event": "Undocked", "timestamp": self.ts(-64), "MarketID": r[1]["market_id"], "StationName": "x"})
        self.assertEqual(len(self.moments()), n)                          # said once
        self.assertFalse(self.state.survey_summary().get("complete"))
        last = r[-1]
        self.jump(-30, last["id64"], last["system"], 90)
        self.j.handle({"event": "Undocked", "timestamp": self.ts(-29), "MarketID": last["market_id"]})   # nothing traded:
        self.assertNotEqual(self.moments()[-1][0], "complete")                                            # not moving on
        self.trade(-25, "MarketSell", last, last["sell"][0]["name"], 10)
        self.j.handle({"event": "Undocked", "timestamp": self.ts(-20), "MarketID": last["market_id"]})
        self.assertEqual(self.moments()[-1][0], "complete")
        self.assertIn(f"sold 10 of {last['sell'][0]['amount']:,} tonnes", self.moments()[-1][1])
        self.assertTrue(self.state.survey_summary()["complete"])

    def test_two_stops_in_one_system(self):
        """Review 2026-10-08 #5: the route moved on only with a jump, so a hop to another station in the same system
        stalled at the first stop for good. A trade at the next stop's station (same system) moves it there."""
        r = [dict(x) for x in self.rows]
        r[2].update(system=r[1]["system"], id64=r[1]["id64"])   # Shimizu Hub moved into Titus City's system
        self.jump(-100, r[0]["id64"], r[0]["system"], 0)
        self.state.riches_store(r, {"options": {}, "kind": "trade"})
        self.market(-90, "MarketBuy", r[0], "Biowaste")
        self.jump(-80, r[1]["id64"], r[1]["system"], 27)
        self.market(-70, "MarketSell", r[1], "Biowaste")
        self.market(-60, "MarketBuy", r[1], "Silver")
        self.assertEqual(self.state.survey_summary()["at"], 1)
        self.market(-50, "MarketSell", r[2], r[2]["sell"][0]["name"])   # the next stop, no jump between
        s = self.state.survey_summary()
        self.assertEqual(s["at"], 2)
        if r[2]["buy"]:
            self.market(-49, "MarketBuy", r[2], r[2]["buy"][0]["name"])
        self.assertEqual(self.moments()[-1][0], "done")
        self.assertIn("Hop 2 done", self.moments()[-1][1])
        self.market(-40, "MarketSell", r[0], "Biowaste")   # a stop in another system: never jumps the route back
        self.assertEqual(self.state.survey_summary()["at"], 2)

    def test_two_stops_in_one_system_copy_the_next_system(self):
        """Two stops in one system then one in another: arriving at the first copies the other system (it copied its own
        system's name, and moving on by a trade never copied the next one: review 2026-10-11)."""
        r = [dict(x) for x in self.rows]
        r[1].update(system=r[0]["system"], id64=r[0]["id64"])   # the second stop in the first stop's system
        copied = []
        self.state.clipboard = types.SimpleNamespace(enabled=True, tool="wl-copy", copy=lambda text: copied.append(text) or True)
        self.jump(-10, r[0]["id64"], r[0]["system"], 0)
        self.state.riches_store(r, {"options": {}, "kind": "trade"})
        self.state.riches_copy_next(force=True)
        self.assertEqual(copied, [r[2]["system"]])

    def test_plot(self):
        self.jump(-100, self.rows[0]["id64"], "Sol", 0)
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(200, {"job": "t1", "status": "queued"}),
                                 (200, {"job": "t1", "status": "ok", "result": trade_answer()["result"]})])
        self.state.spansh = sp
        self.assertEqual(self.state.riches_start_plot({"kind": "trade", "station": "Abraham Lincoln"})[1], 400)   # no capital
        self.assertEqual(self.state.riches_start_plot({"kind": "trade", "capital": 5, "max_cargo": 400})[1], 400)  # no station
        self.j.ship = {"name": "Hauler", "type": "Type9", "cargo_capacity": 400}

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.riches_start_plot({"kind": "trade", "station": "Abraham Lincoln", "capital": 50000000,
                                                    "max_hops": 3, "allow_planetary": True})
                await self.state.riches_task
            return out
        out = asyncio.run(go())
        self.assertEqual(out[1], 202)
        method, url, fields = sp.session.calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_TRADE))
        self.assertGreater(ed_outrider.TRADE_PLOT_TIMEOUT, ed_outrider.HIGHWAY_PLOT_TIMEOUT)   # a 4-hop plot took 136 s
        self.assertEqual({k: fields[k] for k in ("system", "station", "starting_capital", "max_cargo", "max_hops",
                                                 "max_price_age", "requires_large_pad", "allow_planetary")},
                         {"system": "Sol", "station": "Abraham Lincoln", "starting_capital": "50000000", "max_cargo": "400",
                          "max_hops": "3", "max_price_age": str(14 * 86400), "requires_large_pad": "1", "allow_planetary": "1"})
        meta, rows = self.state.riches_state()
        self.assertEqual((meta["kind"], len(rows), rows[1]["station"], meta["at"]), ("trade", 4, "Titus City", 0))
        # one slot: a Road to Riches plot replaces it, its stops with it
        self.state.riches_store([dict(rows[0], bodies=[])], {"options": {}})
        self.assertEqual(self.state.riches_state()[0].get("kind"), None)
        self.state.riches_clear()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM trade_stops").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
