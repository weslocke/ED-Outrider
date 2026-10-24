"""Carrier trips (NEXT-VERSION #19, the author 2026-10-17): Spansh's carrier router planned in Plot Route (POST
/api/carrier/trip), its answer as legs with the depot topped up from the hold where it runs short
(outrider.cargo.carrier_route_legs; probed answer tests/fixtures/spansh_fleetcarrier.json), and the trip following the
carrier: the next leg, a later one skipped to, off course, the end; the cooldown's end after an arrival. Fakes only."""
import asyncio
import json
import os
import types
import unittest
import unittest.mock

from support import _HwSession  # also puts the repository root on sys.path
import ed_outrider  # noqa: E402
import outrider.cargo as cargo  # noqa: E402


def fixture():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_fleetcarrier.json"), encoding="utf-8") as f:
        return json.load(f)["result"]


class Legs(unittest.TestCase):
    def test_probed_answer(self):
        legs, totals = cargo.carrier_route_legs(fixture(), 1000, 12000)
        self.assertEqual([(x["system"], x["fuel"]) for x in legs[:3]],
                         [("Sol", 0), ("Col 359 Sector MB-A b16-7", 110), ("IC 1287 Sector DB-X c1-18", 110)])
        self.assertEqual((legs[-1]["system"], legs[-1]["ly"]), ("Colonia", 50.6))
        self.assertEqual(totals["need"], sum(x["fuel"] for x in legs))
        self.assertEqual((totals["have"], totals["short"]), (13000, 0))
        self.assertTrue(all(x["top_up"] == 0 for x in legs[:6]))   # a full depot pays the first legs itself

    def test_depot_topped_up_from_the_hold(self):
        """Before the leg the depot cannot pay for, the hold's tritium tops it up (up to 1,000 t); with the hold dry, the
        leg is short; Spansh's restock is the tritium to buy there."""
        res = {"jumps": [{"name": "A", "distance": 0}, {"name": "B", "distance": 500, "fuel_used": 110},
                         {"name": "C", "distance": 500, "fuel_used": 110, "must_restock": 1, "restock_amount": 400},
                         {"name": "D", "distance": 500, "fuel_used": 110}]}
        legs, totals = cargo.carrier_route_legs(res, 150, 60)
        self.assertEqual([(x["system"], x["top_up"], x["short"], x["buy"]) for x in legs],
                         [("A", 0, False, 0), ("B", 0, False, 0), ("C", 60, True, 400), ("D", 0, True, 0)])   # C: 40 + the last 60 < 110
        self.assertEqual(totals, {"need": 330, "have": 210, "short": 120})
        self.assertIsNone(cargo.carrier_route_legs({"jumps": [{"name": "A"}]}, 0, 0))
        self.assertIsNone(cargo.carrier_route_legs([], 0, 0))


class Trip(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.carrier = {"id": 7, "system": "Sol", "id64": 10477373803, "fuel": 900, "moved_ts": "2026-10-17T10:00:00Z"}

    def plot(self, body, answer=None):
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(200, {"job": "c1", "status": "queued"}),
                                 (200, {"job": "c1", "status": "ok", "result": answer or fixture()})])
        self.state.spansh = sp

        async def go():
            with unittest.mock.patch.object(ed_outrider, "HIGHWAY_POLL_S", 0.01):
                out = self.state.carrier_trip_plot(body)
                if self.state.carrier_trip_task:
                    await self.state.carrier_trip_task
            return out
        return asyncio.run(go()), sp.session.calls

    def test_refused(self):
        for body, why in (({}, "destination"), ({"to": "Colonia", "type": "yacht"}, "fleet or squadron"),
                          ({"to": "Colonia", "fuel": 1200}, "fuel"), ({"to": "Colonia", "hold": 500, "used": 100}, "includes the tritium"),
                          ({"to": "Colonia", "fuel": True}, "fuel"),
                          ({"to": "Colonia", "fuel": float("inf")}, "fuel")):   # JSON's Infinity: a 400, not a 500 (L19)
            out, status = self.state.carrier_trip_plot(body)
            self.assertEqual(status, 400, body)
            self.assertIn(why, out["error"], body)

    def test_plot_and_follow(self):
        (out, status), calls = self.plot({"to": "Colonia", "via": "Jaques", "hold": 12000, "used": 16000})
        self.assertEqual(status, 202)
        self.assertEqual(self.state.carrier_trip_plotting["state"], "done", self.state.carrier_trip_plotting)
        method, url, fields = calls[0]
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_FC))
        self.assertEqual(fields, {"source": "Sol", "destinations": ["Jaques", "Colonia"], "capacity": "25000", "mass": "25000",
                                  "capacity_used": "16000", "calculate_starting_fuel": "0", "fuel_loaded": "900",
                                  "tritium_stored": "12000"})
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["n"], t["next"]["system"], t["done"], t["ready_at"]), (0, 7, "Col 359 Sector MB-A b16-7", False, None))
        self.assertEqual(t["hours"], round(7 * ed_outrider.CARRIER_LEG_S / 3600, 1))
        # the carrier jumps to the first leg (the booked jump settled: not yet confirmed)
        legs = t["legs"]
        self.j.carrier.update(system=legs[1]["system"], id64=legs[1]["id64"], moved_ts="2026-10-17T10:20:00Z", assumed=True)
        self.assertTrue(self.state.carrier_trip_follow())
        self.assertFalse(self.state.carrier_trip_follow())   # nothing new
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["next"]["system"], t["sure"]), (1, legs[2]["system"], False))
        self.assertEqual(t["ready_at"], ed_outrider.ts_seconds("2026-10-17T10:20:00Z") + ed_outrider.CARRIER_COOLDOWN_S)
        # a jump onto a later leg skips ahead; somewhere else is off course; back on the plan clears it
        self.j.carrier.update(system=legs[4]["system"], id64=legs[4]["id64"], assumed=False)
        self.state.carrier_trip_follow()
        self.assertEqual(self.state.carrier_trip_summary()["trip"]["at"], 4)
        self.j.carrier.update(system="Elsewhere", id64=99)
        self.state.carrier_trip_follow()
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["off"]), (4, {"system": "Elsewhere", "id64": 99}))
        self.j.carrier.update(system=legs[-1]["system"], id64=legs[-1]["id64"])
        self.state.carrier_trip_follow()
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["done"], t["off"], t["next"], t["ready_at"]), (7, True, None, None, None))
        # kept through a journal re-read; cleared when asked
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertIsNotNone(self.state.carrier_trip_summary()["trip"])
        self.state.carrier_trip_clear()
        self.assertIsNone(self.state.carrier_trip_summary()["trip"])

    def test_sweep_fixes(self):
        """The sweep of 2026-10-17: a trip planned from where the carrier is not yet: arriving at its start is no detour;
        back on the current leg after a detour clears "off"; a finished trip says "complete" once, then goes."""
        self.j.carrier.update(system="Elsewhere", id64=5)   # the carrier is not at the trip's start (a typed From)
        self.plot({"from": "Sol", "to": "Colonia"})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        self.j.carrier.update(system="Sol", id64=legs[0]["id64"])
        self.state.carrier_trip_follow()
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["off"]), (0, None))
        self.j.carrier.update(system=legs[1]["system"], id64=legs[1]["id64"])
        self.state.carrier_trip_follow()
        self.j.carrier.update(system="Detour", id64=77)
        self.state.carrier_trip_follow()
        self.assertEqual(self.state.carrier_trip_summary()["trip"]["off"], {"system": "Detour", "id64": 77})
        self.j.carrier.update(system=legs[1]["system"], id64=legs[1]["id64"])   # back where it was
        self.state.carrier_trip_follow()
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["off"]), (1, None))
        self.j.carrier.update(system=legs[-1]["system"], id64=legs[-1]["id64"])
        self.state.carrier_trip_follow()
        self.assertTrue(self.state.carrier_trip_summary()["trip"]["done"])     # this payload says "complete"
        self.j.carrier.update(system="Later", id64=88)                           # a later jump: the trip is over
        self.assertTrue(self.state.carrier_trip_follow())
        self.assertIsNone(self.state.carrier_trip_summary()["trip"])

    def test_replot_takes_the_figures_as_they_are_now(self):
        """Review 2026-10-23 S4-B1: re-plot sent back the trip's original depot, hold and via; now the depot as it is now
        and no via already passed."""
        via = "Bleia Eohn XE-Y c17-24"
        self.plot({"to": "Colonia", "via": via, "hold": 300, "used": 1000})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        for i in range(1, 6):
            self.j.carrier.update(system=legs[i]["system"], id64=legs[i]["id64"])
            self.state.carrier_trip_follow()
        self.j.carrier.update(system="Elsewhere", id64=99, fuel=410)   # off the trip after the via; a later reading
        self.state.carrier_trip_follow()
        (out, status), calls = self.plot({"replot": True})
        self.assertEqual(status, 202, out)
        fields = calls[0][2]
        self.assertEqual((fields["source"], fields["destinations"], fields["fuel_loaded"]),
                         ("Elsewhere", "Colonia", "410"))   # one destination (the fake keeps it as a string)
        self.state.carrier_trip_clear()                                 # before the via, a re-plot keeps it
        self.j.carrier.update(system="Sol", id64=legs[0]["id64"], fuel=900)
        self.plot({"to": "Colonia", "via": via})
        self.j.carrier.update(system="Detour", id64=77)
        self.state.carrier_trip_follow()
        (out, status), calls = self.plot({"replot": True})
        self.assertEqual(calls[0][2]["destinations"], [via, "Colonia"])

    def test_the_cooldown_after_arriving_at_the_start(self):
        """Review 2026-10-23 S4-B4: plotted from Sol while the carrier is elsewhere; arriving at Sol starts the cooldown."""
        self.j.carrier.update(system="Elsewhere", id64=5)
        self.plot({"from": "Sol", "to": "Colonia"})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        self.j.carrier.update(system="Sol", id64=legs[0]["id64"], moved_ts="2026-10-17T11:00:00Z")
        self.state.carrier_trip_follow()
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["ready_at"]),
                         (0, ed_outrider.ts_seconds("2026-10-17T11:00:00Z") + ed_outrider.CARRIER_COOLDOWN_S))

    def test_an_assumed_last_jump_not_made_keeps_the_trip(self):
        """Review 2026-10-23 S4-B5: the last leg assumed done, then the carrier found on the leg before: the trip goes on."""
        self.plot({"to": "Colonia"})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        for i in range(1, len(legs) - 1):
            self.j.carrier.update(system=legs[i]["system"], id64=legs[i]["id64"], assumed=False)
            self.state.carrier_trip_follow()
        self.j.carrier.update(system=legs[-1]["system"], id64=legs[-1]["id64"], assumed=True)
        self.state.carrier_trip_follow()
        self.assertTrue(self.state.carrier_trip_summary()["trip"]["done"])
        self.j.carrier.update(system=legs[-2]["system"], id64=legs[-2]["id64"], assumed=False)
        self.assertTrue(self.state.carrier_trip_follow())
        t = self.state.carrier_trip_summary()["trip"]
        self.assertEqual((t["at"], t["done"], t["next"]["system"]), (len(legs) - 2, False, "Colonia"))

    def test_a_trip_finished_for_real_stays_finished(self):
        """Bug check #18: a trip whose last arrival the journal confirmed is over: the carrier passing one of its legs
        later does not bring it back (only an assumed last jump not made does)."""
        self.plot({"to": "Colonia"})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        for i in range(1, len(legs)):
            self.j.carrier.update(system=legs[i]["system"], id64=legs[i]["id64"], assumed=False)
            self.state.carrier_trip_follow()
        self.assertTrue(self.state.carrier_trip_summary()["trip"]["done"])
        self.j.carrier.update(system=legs[-2]["system"], id64=legs[-2]["id64"], assumed=False)
        self.state.carrier_trip_follow()
        self.assertIsNone(self.state.carrier_trip_summary()["trip"])

    def test_an_assumed_end_confirmed_is_done(self):
        """#18: an assumed last arrival the journal then confirms (assumed False at the same place) is done for good."""
        self.plot({"to": "Colonia"})
        legs = self.state.carrier_trip_summary()["trip"]["legs"]
        for i in range(1, len(legs)):
            self.j.carrier.update(system=legs[i]["system"], id64=legs[i]["id64"], assumed=i == len(legs) - 1)
            self.state.carrier_trip_follow()
        self.j.carrier["assumed"] = False
        self.state.carrier_trip_follow()
        self.j.carrier.update(system=legs[-2]["system"], id64=legs[-2]["id64"], assumed=False)
        self.state.carrier_trip_follow()
        self.assertIsNone(self.state.carrier_trip_summary()["trip"])

    def test_replot_from_a_typed_depot(self):
        """Bug check #23: a trip planned from a typed depot (no reading in the journals) re-plots from the planned depot
        less the legs flown, said estimated."""
        self.j.carrier.pop("fuel")
        sent = []

        async def plot(params, request):
            sent.append((params, request))
        with unittest.mock.patch.object(self.state, "_carrier_trip_plot", plot), \
                unittest.mock.patch("asyncio.get_running_loop") as loop:
            loop.return_value.create_task = lambda coro: coro.close()
            self.assertEqual(self.state.carrier_trip_plot({"to": "Colonia", "fuel": 700})[1], 202)
        req = {"from": "Sol", "to": "Colonia", "via": None, "fuel": 700, "hold": 0, "used": 0, "type": "fleet", "estimated": False}
        legs = [{"system": "Sol", "fuel": 0}, {"system": "A", "fuel": 110}, {"system": "Colonia", "fuel": 110}]
        ed_outrider.meta_set(self.db, "carrier_trip", {"request": req, "legs": legs, "at": 1, "off": {"system": "Elsewhere"}})
        self.state.carrier_trip_task = None
        with unittest.mock.patch.object(self.state, "_carrier_trip_plot", lambda params, request: sent.append((params, request))), \
                unittest.mock.patch("asyncio.get_running_loop") as loop:
            loop.return_value.create_task = lambda x: None
            out, status = self.state.carrier_trip_plot({"replot": True})
        self.assertEqual(status, 202, out)
        self.assertEqual((sent[-1][1]["fuel"], sent[-1][1]["estimated"]), (590, True))

    def test_a_depot_never_read_is_refused(self):
        """Review 2026-10-23 S4-B3: with no depot reading the plot took the depot as a full 1,000 t."""
        self.j.carrier.pop("fuel")
        out, status = self.state.carrier_trip_plot({"to": "Colonia"})
        self.assertEqual(status, 400)
        self.assertIn("no carrier statistics read yet", out["error"])

    def test_the_depot_after_a_jump_is_estimated(self):
        """Review 2026-10-23 S6-B3: the depot figure stood still after every jump until the carrier's management was
        opened again. Each move since the last reading is kept and its burn taken off, said estimated; a correction of
        an assumed move replaces it; a reading clears them."""
        c = {"id64": 1, "fuel": 900}
        ed_outrider.note_carrier_move(c, 2)
        c["id64"] = 2
        self.assertEqual(c["moves"], [[1, 2]])
        ed_outrider.note_carrier_move(c, 3)                     # settle_carrier's assumed jump to 3
        c.update(id64=3, assumed=True)
        ed_outrider.note_carrier_move(c, 2)                     # it never went: back at 2, no burn for it
        self.assertEqual(c["moves"], [[1, 2]])
        self.j.carrier = dict(c, id=7, assumed=False)
        where = {1: ("A", 0.0, 0.0, 0.0), 2: ("B", 500.0, 0.0, 0.0)}
        with unittest.mock.patch.object(self.state, "locate", lambda i: where.get(i)):
            d = self.state.carrier_depot(used=1000)
            self.assertEqual((d["fuel"], d["read"], d["estimated"], d["unsure"]),
                             (900 - cargo.carrier_burn(500, 1000, 900), 900, True, False))
            self.assertTrue(self.state.carrier_depot(used=None)["unsure"])   # no capacity figure: not taken off
        # a CarrierStats read since: the reading alone
        self.j.carrier = None
        self.j.handle({"timestamp": "2026-10-17T12:00:00Z", "event": "CarrierStats", "CarrierID": 7, "Callsign": "X-1",
                       "Name": "C", "FuelLevel": 640, "JumpRangeCurr": 500, "CarrierType": "FleetCarrier"})
        self.assertEqual((self.j.carrier["fuel"], self.j.carrier["moves"]), (640, []))
        self.assertFalse(self.state.carrier_depot(used=1000)["estimated"])

    def test_spansh_refuses(self):
        sp = ed_outrider.Spansh(self.db)
        sp.session = _HwSession([(400, {"error": "Could not find destination system Nowhere"})])
        self.state.spansh = sp

        async def go():
            self.state.carrier_trip_plot({"to": "Nowhere"})
            await self.state.carrier_trip_task
        asyncio.run(go())
        p = self.state.carrier_trip_plotting
        self.assertEqual((p["state"], p["error"]), ("failed", "Spansh: Could not find destination system Nowhere"))
        self.assertIsNone(self.state.carrier_trip_summary()["trip"])

    def test_route(self):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                a = await c.post("/api/carrier/trip", json={"to": ""})
                b = await c.post("/api/carrier/trip", json={"clear": True})
                return a.status, b.status
        self.assertEqual(asyncio.run(go()), (400, 200))


if __name__ == "__main__":
    unittest.main()
