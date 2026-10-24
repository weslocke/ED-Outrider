"""The carrier's warnings (the full Fable review of 2026-10-23, batch G): the booked jump that leaves the depot unable to
pay the next one (S9-S11), the tritium aboard your ship counted toward a shortfall (S9-S12), the upkeep counted down to
today with its card and moment (S9-S13), how old the depot reading is (S4-S4). Fakes only."""
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.cargo as cargo  # noqa: E402

WEEK = 7 * 86400


class CarrierWarnings(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.carrier = {"id": 7, "id64": 1, "name": "Deep Wanderer", "system": "Home", "x": 0.0, "y": 0.0, "z": 0.0,
                          "planned": {"id64": "2", "name": "Far"}}
        self.j.pos = {"id64": 9, "name": "Me", "x": 3000.0, "y": 0.0, "z": 0.0}
        self.lines = {}

    def summary(self, depot, tritium=None, ship_tritium=0):
        st = {"stats": {"used": 1000}, "after_stats": 0, "lines": {}, "orders": {}, "names": {}, "finance": None}
        if tritium is not None:
            st["lines"]["tritium"] = {"count": tritium, "state": "confirmed"}
        self.j.ship_cargo = {"lines": {"tritium": {"count": ship_tritium}} if ship_tritium else {}, "count": ship_tritium}
        where = {2: ("Far", 480.0, 0.0, 0.0)}
        with unittest.mock.patch.multiple(self.state, carrier_cargo=lambda: st, carrier_burn_factor=lambda: None,
                                          carrier_depot=lambda used, k=1.0: {"fuel": depot, "estimated": False, "read": depot, "read_ts": None},
                                          locate=lambda i: where.get(i), carrier_services=lambda c, s: (False, False, []),
                                          carrier_decommission=lambda: None, carrier_tritium=lambda: None):
            return self.state.carrier_summary()

    def test_a_booked_jump_that_leaves_too_little_for_the_next(self):
        """S9-S11: after this jump the depot cannot pay a full 500 ly one; tritium on a sell order in its hold counts."""
        pl = self.summary(130)["planned"]   # a 480 ly jump burns about 68 t: 62 t left, a 500 ly one wants about 70
        self.assertTrue(pl["last"])
        self.assertEqual(pl["next_burn"], round(cargo.carrier_burn(cargo.CARRIER_JUMP_LY, 1000, pl["depot_after"])))
        self.assertEqual(pl["hold_tritium"], 0)
        self.assertFalse(self.summary(130, tritium=400)["planned"]["last"])    # 400 t on a sell order: it can be moved in
        self.assertFalse(self.summary(900)["planned"]["last"])

    def test_the_tritium_in_your_ship_covers_a_shortfall(self):
        """S9-S12: the carrier's trip to you is short; what your ship carries covers it ("aboard")."""
        t = self.summary(100)["trip"]
        self.assertGreater(t["short"], 0)
        self.assertFalse(t["covered"])
        t = self.summary(100, ship_tritium=t["short"] + 10)["trip"]
        self.assertEqual((t["covered"], t["top_up"], t["ship"]), (True, "aboard", t["short"] + 10))

    def test_upkeep_counted_down_to_today(self):
        """S9-S13: 12 weeks of balance read 10 weeks ago is about 2 weeks now: the warning, a card and one moment per
        reading; the same stats a day old: no warning."""
        roles = {"Refuel": "on"}
        upkeep = cargo.carrier_upkeep(roles)
        now = 2_000_000_000
        st = {"finance": {"balance": 12 * upkeep, "reserve": 0, "available": 0, "ts": ed_outrider.iso_ts(now - 10 * WEEK - 60)},
              "crew": {"roles": roles}}
        fi = self.state.carrier_finance(st, now)
        self.assertEqual((fi["weeks"], fi["weeks_now"], fi["weeks_since"], fi["warn"]), (12.0, 2.0, 10, True))
        fresh = dict(st, finance=dict(st["finance"], ts=ed_outrider.iso_ts(now - 86400)))
        self.assertFalse(self.state.carrier_finance(fresh, now)["warn"])
        with unittest.mock.patch.object(self.state, "carrier_cargo", lambda: st):
            self.state.check_upkeep(now)
            self.state.check_upkeep(now + 60)
        said = [m for m in self.j.moments if m["kind"] == "upkeep_low"]
        self.assertEqual([(m["carrier"], m["weeks"]) for m in said], [("Deep Wanderer", 2.0)])   # once per reading
        [card] = [n for n in self.state.notices.active() if n["key"] == "carrier_upkeep"]
        self.assertIn("Deep Wanderer has about 2 weeks of upkeep left", card["text"])
        with unittest.mock.patch.object(self.state, "carrier_cargo", lambda: fresh):
            self.state.check_upkeep(now)
        self.assertFalse([n for n in self.state.notices.active() if n["key"] == "carrier_upkeep"])

    def test_aboard_only_when_it_really_covers(self):
        """Bug check #20: the ship's tritium counts as covering the trip only by trip_top_up's own rules."""
        t = self.summary(100, ship_tritium=1)["trip"]
        need = t["short"]
        with unittest.mock.patch.object(cargo, "trip_top_up", lambda trip, ly, hold, used, k=1.0: None):
            t = self.summary(100, ship_tritium=need + 5)["trip"]
        self.assertEqual((t["covered"], t["top_up"]), (False, None))

    def test_no_upkeep_warning_for_a_carrier_decommissioned(self):
        """Bug check #19."""
        roles = {"Refuel": "on"}
        upkeep = cargo.carrier_upkeep(roles)
        now = 2_000_000_000
        st = {"finance": {"balance": 2 * upkeep, "reserve": 0, "available": 0, "ts": ed_outrider.iso_ts(now - 60)}, "crew": {"roles": roles}}
        with unittest.mock.patch.object(self.state, "carrier_cargo", lambda: st), \
                unittest.mock.patch.object(self.state, "carrier_decommission", lambda: {"done": True}):
            self.state.check_upkeep(now)
        self.assertEqual(([m for m in self.j.moments if m["kind"] == "upkeep_low"], self.state.notices.active()), ([], []))

    def test_a_rolled_back_tick_says_the_upkeep_again(self):
        """Bug check #21: check_upkeep writes with the tick, not on its own: after a rollback its moment comes again."""
        roles = {"Refuel": "on"}
        upkeep = cargo.carrier_upkeep(roles)
        now = 2_000_000_000
        st = {"finance": {"balance": 2 * upkeep, "reserve": 0, "available": 0, "ts": ed_outrider.iso_ts(now - 60)}, "crew": {"roles": roles}}
        with unittest.mock.patch.object(self.state, "carrier_cargo", lambda: st):
            self.state.check_upkeep(now)
            self.db.rollback()
            self.assertIsNone(ed_outrider.meta_get(self.db, "upkeep_said"))
            self.state.check_upkeep(now)
        self.assertEqual(len([m for m in self.j.moments if m["kind"] == "upkeep_low"]), 2)

    def test_a_bank_deposit_counts(self):
        """Bug check #22: CarrierBankTransfer's balance replaces the stats' (the deposit the card asks for)."""
        stats = {"timestamp": "2026-10-01T00:00:00Z", "event": "CarrierStats", "CarrierID": 7, "FuelLevel": 500,
                 "Finance": {"CarrierBalance": 1000, "ReserveBalance": 100, "AvailableBalance": 900}}
        dep = {"timestamp": "2026-10-02T00:00:00Z", "event": "CarrierBankTransfer", "CarrierID": 7, "Deposit": 5000,
               "PlayerBalance": 1, "CarrierBalance": 6000}
        st = cargo.carrier_fold(7, [(stats["timestamp"], stats), (dep["timestamp"], dep)])
        self.assertEqual(st["finance"], {"balance": 6000, "reserve": 100, "available": 5900, "ts": "2026-10-02T00:00:00Z"})
        self.assertIn("CarrierBankTransfer", ed_outrider.CARRIER_CARGO_EVENTS)

    def test_the_request_names_the_reading(self):
        """S4-S4: a trip planned from the depot reading carries the reading's time (a typed depot: none)."""
        d = {"from": "Home", "fuel": 800, "hold": 0, "fuel_estimated": False, "fuel_read_ts": "2026-10-01T10:00:00Z",
             "used": 1000, "type": "fleet"}
        got = []
        with unittest.mock.patch.object(self.state, "carrier_trip_defaults", lambda: d), \
                unittest.mock.patch.object(self.state, "_carrier_trip_plot", lambda params, request: got.append(request)), \
                unittest.mock.patch("asyncio.get_running_loop") as loop:
            loop.return_value.create_task = lambda x: None
            self.state.carrier_trip_plot({"to": "Far"})
            self.state.carrier_trip_task = None
            self.state.carrier_trip_plot({"to": "Far", "fuel": 700})
        self.assertEqual([r["fuel_read_ts"] for r in got], ["2026-10-01T10:00:00Z", None])   # a typed depot: no reading


if __name__ == "__main__":
    unittest.main()
