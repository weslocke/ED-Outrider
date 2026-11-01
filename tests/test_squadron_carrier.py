"""Your squadron's carrier (plan 2026-10-30, Hiner399 in discussion #3): the reader's record beside your fleet carrier,
Spansh's word on it, the summary, the dock finder's and the sell lists' "your squadron's". Line shapes from the author's
journals (a member's: CarrierLocation at each login); the officers' lines from Hiner399's journal as his squadron's
leader (issue #16, tests/fixtures/squadron_carrier_officer.jsonl: its carrier and dock lines). Fakes only."""
import asyncio
import json
import os
import time
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.dock as dock  # noqa: E402

SC_ID, FC_ID = 3713298944, 3700251648
HAJANGAI = 7780366815938


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


def login(ts, squadron_carrier=True, docked_at=None, squadron=True, late=False):
    """A login's lines in one of the game's orders (the author's journals): LoadGame, the fleet carrier's
    CarrierLocation, SquadronStartup, the squadron carrier's CarrierLocation, Location (2026-07-19); `late`: the two
    squadron lines after Location (2025-12-07); `squadron` False: neither (2026-07-01, still a member)."""
    lines = [ev(ts + ":40Z", "LoadGame", Commander="Wes Locke", FID="F1"),
             ev(ts + ":42Z", "CarrierLocation", CarrierType="FleetCarrier", CarrierID=FC_ID,
                StarSystem="Col 285 Sector KM-V d2-106", SystemAddress=3652643195227, BodyID=5)]
    sq = [ev(ts + ":51Z", "SquadronStartup", SquadronID=102140, SquadronName="THE FATHERHOOD", CurrentRank=5,
             CurrentRankName="member")] if squadron else []
    if squadron and squadron_carrier:
        sq.append(ev(ts + ":52Z", "CarrierLocation", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                     StarSystem="Hajangai", SystemAddress=HAJANGAI, BodyID=2))
    loc = dict(StarSystem="Hajangai", SystemAddress=HAJANGAI, StarPos=[-28.125, 4.90625, -68.28125])
    if docked_at:
        loc.update(Docked=True, StationName="7738", StationType="FleetCarrier", MarketID=docked_at,
                   StationServices=["dock", "exploration", "vistagenomics", "refuel"])
    location = [ev(ts + ":53Z" if not late else ts + ":45Z", "Location", **loc)]
    return lines + (location + sq if late else sq + location)


class Reader(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)

    def feed(self, lines):
        for e in lines:
            self.j.handle(e)

    def test_a_login_keeps_both_carriers_apart(self):
        self.feed(login("2026-07-19T20:44"))
        sc = self.j.squadron_carrier
        self.assertEqual((sc["id"], sc["system"], sc["id64"], sc["moved_ts"]),
                         (SC_ID, "Hajangai", HAJANGAI, "2026-07-19T20:44:52Z"))
        self.assertNotIn("moves", sc)
        self.assertEqual(ed_outrider.meta_get(self.db, "squadron_carrier")["id"], SC_ID)
        # your fleet carrier's record is untouched by it (its own CarrierLocation names a carrier it has no record of)
        self.assertNotEqual((self.j.carrier or {}).get("id"), SC_ID)

    def test_the_next_login_is_no_move(self):
        self.feed(login("2026-07-19T20:44"))
        self.feed(login("2026-07-20T08:00"))
        self.assertEqual(self.j.squadron_carrier["moved_ts"], "2026-07-19T20:44:52Z")
        self.assertEqual(self.j.squadron_carrier["ts"], "2026-07-20T08:00:52Z")

    def test_a_session_without_its_line_drops_it(self):
        """SquadronStartup but no carrier line by the session's end (Shutdown, or the next LoadGame): the squadron has
        no carrier (any more). Not before: the line can come after Location, up to 17 s after SquadronStartup."""
        self.feed(login("2026-07-19T20:44"))
        self.feed(login("2026-07-20T08:00", squadron_carrier=False))
        self.assertEqual(self.j.squadron_carrier["id"], SC_ID)   # still within the login
        self.j.handle(ev("2026-07-20T09:00:00Z", "Shutdown"))
        self.assertIsNone(self.j.squadron_carrier)
        self.assertIsNone(ed_outrider.meta_get(self.db, "squadron_carrier"))
        self.feed(login("2026-07-21T08:00"))
        self.feed(login("2026-07-22T08:00", squadron_carrier=False) + login("2026-07-22T09:00", squadron=False))
        self.assertIsNone(self.j.squadron_carrier)   # the next LoadGame ends the session too

    def test_its_line_after_location_is_no_drop(self):
        """The 2025-12-07 order: Location, then SquadronStartup and the carrier's line."""
        self.feed(login("2026-07-19T20:44", late=True))
        self.feed(login("2026-07-20T08:00", late=True))
        self.j.handle(ev("2026-07-20T09:00:00Z", "Shutdown"))
        self.assertEqual(self.j.squadron_carrier["system"], "Hajangai")

    def test_a_login_with_neither_line_says_nothing(self):
        """2026-07-01 and -04: no SquadronStartup and no carrier line, still a member, the carrier where it was."""
        self.feed(login("2026-07-19T20:44"))
        self.feed(login("2026-07-20T08:00", squadron=False))
        self.j.handle(ev("2026-07-20T09:00:00Z", "Shutdown"))
        self.assertEqual(self.j.squadron_carrier["id"], SC_ID)

    def test_a_location_in_play_drops_nothing(self):
        self.feed(login("2026-07-19T20:44"))
        self.j.handle(ev("2026-07-19T21:00:00Z", "Location", StarSystem="Sol", SystemAddress=10477373803))
        self.assertEqual(self.j.squadron_carrier["id"], SC_ID)

    def test_leaving_the_squadron_drops_it(self):
        self.feed(login("2026-07-19T20:44"))
        self.j.handle(ev("2026-07-19T21:00:00Z", "LeftSquadron", SquadronName="THE FATHERHOOD"))
        self.assertIsNone(self.j.squadron_carrier)

    def test_an_older_login_read_late_changes_nothing(self):
        """A legacy folder imported after the live one: its old place, or its login with no carrier yet, must not win."""
        self.feed(login("2026-07-19T20:44"))
        old = login("2025-01-02T10:00", squadron_carrier=False)
        self.feed(old)
        self.assertEqual(self.j.squadron_carrier["system"], "Hajangai")
        moved = [dict(e, StarSystem="Elsewhere", SystemAddress=1) if e.get("CarrierType") == "SquadronCarrier" else e
                 for e in login("2025-06-02T10:00")]
        self.feed(moved)
        self.assertEqual(self.j.squadron_carrier["system"], "Hajangai")

    def test_a_new_carrier_starts_afresh(self):
        self.feed(login("2026-07-19T20:44"))
        self.j.handle(ev("2026-07-19T20:50:00Z", "CarrierJumpRequest", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         SystemName="Sol", SystemAddress=10477373803, DepartureTime="2026-07-19T21:05:00Z"))
        self.assertEqual(self.j.squadron_carrier["planned"]["system"], "Sol")
        self.j.handle(ev("2026-07-21T10:00:00Z", "CarrierLocation", CarrierType="SquadronCarrier", CarrierID=99,
                         StarSystem="Shinrarta Dezhra", SystemAddress=3932277478106))
        sc = self.j.squadron_carrier
        self.assertEqual((sc["id"], sc["system"], sc.get("planned")), (99, "Shinrarta Dezhra", None))

    def test_docked_at_it(self):
        """Docked by MarketID (the line names no carrier type), its services kept; a login docked there is a Location."""
        self.feed(login("2026-07-19T20:44", docked_at=SC_ID))
        self.assertEqual(self.j.squadron_carrier["services"], ["dock", "exploration", "vistagenomics", "refuel"])
        self.j.handle(ev("2026-07-19T21:30:00Z", "Docked", StationName="7738", StationType="FleetCarrier",
                         StarSystem="Hajangai", SystemAddress=HAJANGAI, MarketID=SC_ID, StationServices=["dock"]))
        self.assertEqual((self.j.squadron_carrier["services"], self.j.squadron_carrier["services_ts"]),
                         (["dock"], "2026-07-19T21:30:00Z"))
        # docked at your own fleet carrier: not the squadron's
        self.j.handle(ev("2026-07-19T22:00:00Z", "Docked", StationName="G0X-85Z", StationType="FleetCarrier",
                         StarSystem="X", SystemAddress=5, MarketID=FC_ID, StationServices=["dock", "shipyard"]))
        self.assertEqual(self.j.squadron_carrier["services"], ["dock"])

    def test_riding_its_jump(self):
        self.feed(login("2026-07-19T20:44", docked_at=SC_ID))
        self.j.handle(ev("2026-07-19T21:00:00Z", "CarrierJumpRequest", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         SystemName="Sol", SystemAddress=10477373803, DepartureTime="2026-07-19T21:15:00Z"))
        self.j.handle(ev("2026-07-19T21:16:00Z", "CarrierJump", Docked=True, StationName="7738", StationType="FleetCarrier",
                         MarketID=SC_ID, StarSystem="Sol", SystemAddress=10477373803, StarPos=[0.0, 0.0, 0.0]))
        sc = self.j.squadron_carrier
        self.assertEqual((sc["system"], sc["x"], sc["planned"], sc["moved_ts"]), ("Sol", 0.0, None, "2026-07-19T21:16:00Z"))

    def test_the_officers_lines(self):
        """CarrierStats, a booking, its cancelling and a tritium deposit (the real deposit has no CarrierType: Officer)."""
        self.feed(login("2026-07-19T20:44"))
        self.j.handle(ev("2026-07-19T21:00:00Z", "CarrierStats", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         Callsign="7738", Name="THE WINCHESTER", FuelLevel=812, JumpRangeCurr=500.0))
        sc = self.j.squadron_carrier
        self.assertEqual((sc["name"], sc["callsign"], sc["fuel"], sc["stats_ts"], sc["system"]),
                         ("THE WINCHESTER", "7738", 812, "2026-07-19T21:00:00Z", "Hajangai"))
        self.j.handle(ev("2026-07-19T21:01:00Z", "CarrierJumpRequest", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         SystemName="Sol", SystemAddress=10477373803, DepartureTime="2026-07-19T21:15:00Z"))
        self.assertEqual(self.j.squadron_carrier["planned"]["departure"], "2026-07-19T21:15:00Z")
        self.j.handle(ev("2026-07-19T21:02:00Z", "CarrierJumpCancelled", CarrierType="SquadronCarrier", CarrierID=SC_ID))
        self.assertIsNone(self.j.squadron_carrier["planned"])
        self.j.handle(ev("2026-07-19T21:03:00Z", "CarrierDepositFuel", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         Amount=100, Total=912))
        self.assertEqual(self.j.squadron_carrier["fuel"], 912)
        # your fleet carrier is not touched by any of them
        self.assertIsNone(self.j.carrier)

    def test_its_lines_never_reach_your_carriers_cargo(self):
        """In their real shapes (#16): the deposit has no CarrierType, nor do a transfer there and its jump aboard."""
        self.feed(login("2026-07-19T20:44", docked_at=SC_ID))
        self.j.handle(ev("2026-07-19T21:00:00Z", "Docked", StationName="7738", StationType="FleetCarrier", MarketID=SC_ID,
                         StarSystem="Hajangai", SystemAddress=HAJANGAI))
        self.j.handle(ev("2026-07-19T21:02:00Z", "CargoTransfer", Transfers=[{"Type": "tritium", "Count": 5, "Direction": "toship"}]))
        self.j.handle(ev("2026-07-19T21:03:00Z", "CarrierDepositFuel", CarrierID=SC_ID, Amount=5, Total=912))
        self.j.handle(ev("2026-07-19T21:30:00Z", "CarrierJump", Docked=True, StationName="7738", StationType="FleetCarrier",
                         MarketID=SC_ID, StarSystem="Sol", SystemAddress=10477373803, StarPos=[0.0, 0.0, 0.0]))
        self.assertEqual(self.db.execute("SELECT count(*) FROM cargo_events WHERE market = ?", (SC_ID,)).fetchone()[0], 0)
        self.assertEqual((self.j.squadron_carrier["fuel"], self.j.squadron_carrier["system"]), (912, "Sol"))

    def mine(self, ts, n, what="$platinum_name;"):
        for i in range(n):
            self.j.handle(ev(f"{ts}:{10 + i}Z", "MiningRefined", Type=what))

    def dock(self, ts, market, name):
        self.j.handle(ev(ts, "Docked", StationName=name, StationType="FleetCarrier", MarketID=market,
                         StarSystem="Hajangai", SystemAddress=HAJANGAI))

    def test_mined_ore_given_to_it_is_not_on_your_carrier(self):
        """Ore moved to your squadron's carrier leaves the ship's mined stock, and is not your own carrier's (#16)."""
        self.feed(login("2026-07-19T20:44"))
        self.mine("2026-07-19T20:50", 3)
        self.dock("2026-07-19T21:00:00Z", SC_ID, "7738")
        self.j.handle(ev("2026-07-19T21:01:00Z", "CargoTransfer", Transfers=[{"Type": "platinum", "Count": 3, "Direction": "tocarrier"}]))
        self.assertEqual((self.j.mined_stock, self.j.mined_carrier), ({}, {}))

    def test_cargo_from_it_is_no_mined_ore(self):
        """Your own carrier's mined stock stays when cargo comes aboard at your squadron's carrier (#16)."""
        self.feed(login("2026-07-19T20:44"))
        self.mine("2026-07-19T20:50", 3)
        self.dock("2026-07-19T21:00:00Z", FC_ID, "G0X-85Z")
        self.j.handle(ev("2026-07-19T21:01:00Z", "CargoTransfer", Transfers=[{"Type": "platinum", "Count": 3, "Direction": "tocarrier"}]))
        self.assertEqual(self.j.mined_carrier, {"platinum": 3})   # your own carrier: still your mined ore
        self.j.handle(ev("2026-07-19T21:05:00Z", "Undocked", StationName="G0X-85Z", StationType="FleetCarrier", MarketID=FC_ID))
        self.dock("2026-07-19T21:10:00Z", SC_ID, "7738")
        self.j.handle(ev("2026-07-19T21:11:00Z", "CargoTransfer", Transfers=[{"Type": "platinum", "Count": 3, "Direction": "toship"}]))
        self.assertEqual((self.j.mined_stock, self.j.mined_carrier), ({}, {"platinum": 3}))

    def test_a_reread_clears_it(self):
        self.feed(login("2026-07-19T20:44"))
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertIsNone(ed_outrider.meta_get(self.db, "squadron_carrier"))


OFFICER = os.path.join(os.path.dirname(__file__), "fixtures", "squadron_carrier_officer.jsonl")
CURY, HIS_FC = 3714858752, 3712901888


class Officer(unittest.TestCase):
    """Hiner399's session as his squadron's leader (2026-11-01, #16), its carrier and dock lines as the game wrote them:
    docked at it, tritium out and back in, three bookings (two flown, one aboard, one cancelled), Refuel paused and
    resumed, trade orders and bank transfers. He owns a fleet carrier too."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        # his own fleet carrier, known from an earlier session: its stats and a booked jump of its own
        self.j.handle(ev("2026-10-31T10:00:00Z", "CarrierStats", CarrierType="FleetCarrier", CarrierID=HIS_FC,
                         Callsign="ABC-12X", Name="HIS OWN", FuelLevel=500, JumpRangeCurr=500.0))
        self.j.handle(ev("2026-10-31T10:01:00Z", "CarrierLocation", CarrierType="FleetCarrier", CarrierID=HIS_FC,
                         StarSystem="HIP 102929", SystemAddress=39957030076, BodyID=18))
        self.j.handle(ev("2026-10-31T10:02:00Z", "CarrierJumpRequest", CarrierType="FleetCarrier", CarrierID=HIS_FC,
                         SystemName="Sol", SystemAddress=10477373803, DepartureTime="2026-11-02T10:00:00Z"))
        with open(OFFICER, encoding="utf-8") as f:
            for line in f:
                self.j.handle(json.loads(line))

    def test_the_squadron_carriers_record(self):
        sc = self.j.squadron_carrier
        self.assertEqual((sc["id"], sc["name"], sc["callsign"], sc["fuel"], sc["system"], sc["planned"]),
                         (CURY, "THE CURRY MONSTER", "CURY", 986, "Synuefai MD-I c26-19", None))
        self.assertEqual(sc["crew"]["roles"]["Refuel"], "on")   # paused, then resumed
        self.assertEqual(sc["crew"]["ts"], "2026-11-01T12:57:29Z")   # the last CarrierStats

    def test_his_fleet_carrier_untouched(self):
        c = self.j.carrier
        self.assertEqual((c["id"], c["name"], c["fuel"], c["planned"]["system"]), (HIS_FC, "HIS OWN", 500, "Sol"))
        self.assertEqual(c["system"], "HIP 102929")   # its own CarrierLocation at the login

    def test_none_of_its_lines_in_your_carriers_history(self):
        self.assertEqual(self.db.execute("SELECT count(*) FROM cargo_events WHERE market = ?", (CURY,)).fetchone()[0], 0)

    def test_a_pause_after_the_stats(self):
        self.j.handle(ev("2026-11-01T13:05:00Z", "CarrierCrewServices", CarrierID=CURY, CarrierType="SquadronCarrier",
                         CrewRole="Refuel", Operation="Pause", CrewName="Celia Bryan"))
        self.assertEqual(self.j.squadron_carrier["crew"]["roles"]["Refuel"], "suspended")
        # another carrier's line (your own fleet carrier's) changes nothing here
        self.j.handle(ev("2026-11-01T13:06:00Z", "CarrierCrewServices", CarrierID=HIS_FC, CarrierType="FleetCarrier",
                         CrewRole="Refuel", Operation="Resume", CrewName="X"))
        self.assertEqual(self.j.squadron_carrier["crew"]["roles"]["Refuel"], "suspended")


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "spansh_squadron_carrier.json")


def spansh_record(**kw):
    """Spansh's /api/station answer for the author's squadron carrier (2026-10-30, trimmed), its record changed by kw."""
    with open(FIXTURE, encoding="utf-8") as f:
        return dict(json.load(f)["record"], **kw)


class Summary(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        for e in login("2026-07-19T20:44"):
            self.j.handle(e)
        self.j.pos = {"id64": 1, "name": "Me", "x": -28.125, "y": 4.90625, "z": -168.28125}
        self.where = {HAJANGAI: ("Hajangai", -28.125, 4.90625, -68.28125)}
        self.state.locate = lambda i: self.where.get(i)

    def spansh(self, rec, moved=None):
        """maybe_squadron_spansh run once against a fake Spansh answering `rec` (an exception: it fails)."""
        async def station(cid):
            self.asked.append(cid)
            if isinstance(rec, Exception):
                raise rec
            return rec
        self.asked = []
        self.state.spansh = types.SimpleNamespace(station=station)

        async def go():
            self.state.maybe_squadron_spansh()
            if self.state.sc_task:
                await self.state.sc_task
        asyncio.run(go())

    def test_from_the_journal_alone(self):
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["system"], s["distance"], s["source"], s["name"], s["callsign"], s["squadron"]),
                         ("Hajangai", 100.0, "journal", "", "", "THE FATHERHOOD"))
        self.assertEqual((s["services"], s["has_uc"], s["here"], s["aboard"], s["fuel"]), ([], False, False, False, None))

    def test_spansh_names_it(self):
        self.spansh(spansh_record())
        self.assertEqual(self.asked, [SC_ID])
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["name"], s["callsign"], s["ls"], s["source"]), ("THE WINCHESTER", "7738", 337.110597, "journal"))
        self.assertEqual(s["services"], ["UC", "Vista", "Repair", "Refuel", "Shipyard", "Outfitting"])
        # asked again only a day later, or when the journal says it moved
        self.spansh(spansh_record())
        self.assertEqual(self.asked, [])
        self.j.squadron_carrier["moved_ts"] = "2026-07-20T00:00:00Z"
        self.spansh(spansh_record())
        self.assertEqual(self.asked, [SC_ID])

    def test_a_failed_lookup_keeps_the_last_copy(self):
        self.spansh(spansh_record())
        self.j.squadron_carrier["moved_ts"] = "2026-07-20T00:00:00Z"
        self.spansh(ed_outrider.ClientError("down"))
        self.assertEqual(self.state.squadron_carrier_summary()["name"], "THE WINCHESTER")
        self.assertGreater(self.state.sc_retry_at, 0)
        self.spansh(spansh_record())
        self.assertEqual(self.asked, [])   # not again until CARRIER_RETRY_S

    def test_a_newer_spansh_report_elsewhere_wins(self):
        """A member hears of a move only at the next login: Spansh's newer report of it elsewhere is shown, said so."""
        self.spansh(spansh_record(system_name="Sol", system_id64=10477373803, system_x=0.0, system_y=0.0, system_z=0.0,
                                  updated_at="2026-08-01T00:00:00Z"))
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["system"], s["id64"], s["source"], s["spansh_ts"]), ("Sol", "10477373803", "Spansh", "2026-08-01T00:00:00Z"))
        # an older report elsewhere: the journal's place
        self.spansh(spansh_record(system_name="Sol", system_id64=10477373803, system_x=0.0, system_y=0.0, system_z=0.0,
                                  updated_at="2026-01-01T00:00:00Z"))
        self.j.squadron_carrier["moved_ts"] = "x"   # asked again
        self.spansh(spansh_record(system_name="Sol", system_id64=10477373803, system_x=0.0, system_y=0.0, system_z=0.0,
                                  updated_at="2026-01-01T00:00:00Z"))
        self.assertEqual(self.state.squadron_carrier_summary()["source"], "journal")

    def test_a_dock_there_is_newer_than_spansh(self):
        self.spansh(spansh_record())
        self.j.handle(ev("2026-11-01T10:00:00Z", "Docked", StationName="7738", StationType="FleetCarrier", StarSystem="Hajangai",
                         SystemAddress=HAJANGAI, MarketID=SC_ID, StationServices=["dock", "exploration", "refuel"]))
        self.j.docked = {"market_id": SC_ID}
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["services"], s["has_vista"], s["aboard"]), (["UC", "Refuel"], False, True))

    def stats(self, ts, **roles):
        crew = [{"CrewRole": r, "Activated": v != "off", "Enabled": v == "on"} for r, v in roles.items()]
        self.j.handle(ev(ts, "CarrierStats", CarrierType="SquadronCarrier", CarrierID=SC_ID, Callsign="7738",
                         Name="THE WINCHESTER", FuelLevel=800, Crew=crew))

    def crew(self, ts, role, op):
        self.j.handle(ev(ts, "CarrierCrewServices", CarrierType="SquadronCarrier", CarrierID=SC_ID, CrewRole=role, Operation=op))

    def test_an_officers_crew_says_its_services(self):
        """A service an officer pauses is off for the sell lists, and the tile says so (#16), as your own carrier's."""
        self.stats("2026-11-01T10:00:00Z", Exploration="on", VistaGenomics="on", Refuel="on")
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["services"], s["has_uc"], s["has_vista"], s["suspended"]), (["UC", "Vista", "Refuel"], True, True, []))
        self.crew("2026-11-01T10:05:00Z", "VistaGenomics", "Pause")
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["has_uc"], s["has_vista"], s["suspended"]), (True, False, ["Vista"]))
        self.assertEqual(dock.squadron_row(s)["services"], {"UC", "Refuel"})
        self.crew("2026-11-01T10:06:00Z", "VistaGenomics", "Resume")
        self.assertTrue(self.state.squadron_carrier_summary()["has_vista"])
        # a dock there after it is newer: its list wins
        self.j.handle(ev("2026-11-01T11:00:00Z", "Docked", StationName="7738", StationType="FleetCarrier", StarSystem="Hajangai",
                         SystemAddress=HAJANGAI, MarketID=SC_ID, StationServices=["dock", "exploration", "refuel"]))
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["has_uc"], s["has_vista"]), (True, False))

    def test_a_booked_jump_has_its_length(self):
        sol = (0.0, 0.0, 0.0)
        self.where[10477373803] = ("Sol",) + sol
        self.j.handle(ev("2026-07-19T21:00:00Z", "CarrierJumpRequest", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         SystemName="Sol", SystemAddress=10477373803, DepartureTime="2099-01-01T00:00:00Z"))
        pl = self.state.squadron_carrier_summary()["planned"]
        self.assertEqual(pl["jump_ly"], round(ed_outrider.dist({"x": -28.125, "y": 4.90625, "z": -68.28125},
                                                                dict(zip("xyz", sol))), 1))
        self.assertEqual(pl["distance_from_you"], round(ed_outrider.dist(self.j.pos, dict(zip("xyz", sol))), 1))
        self.assertNotIn("burn", pl)   # the fleet carrier's formula does not fit it

    def test_a_long_gone_booking_is_dropped(self):
        self.j.squadron_carrier["planned"] = {"system": "Sol", "id64": 10477373803, "departure": "2026-07-19T21:00:00Z",
                                              "ts": "2026-07-19T20:50:00Z"}
        self.assertIsNone(self.state.squadron_carrier_summary()["planned"])

    def test_in_the_status_and_the_payload(self):
        self.spansh(spansh_record())
        self.assertEqual(self.state.payload()["squadron_carrier"]["name"], "THE WINCHESTER")

    def test_among_the_sellers(self):
        """In the UC and Vista lists as your squadron's (Spansh's report of it replaced), and a place you may fly to."""
        self.spansh(spansh_record())
        uc = [{"name": "7738", "type": "Drake-Class Carrier", "system": "Old Place", "updated_at": "2026-01-01T00:00:00Z",
               "x": 900.0, "y": 0.0, "z": 0.0, "distance": 10},
              {"name": "Far Port", "type": "Coriolis Starport", "system": "Far", "updated_at": "2026-10-01T00:00:00Z",
               "x": 2500.0, "y": 0.0, "z": 0.0, "distance": 1300}]
        ed_outrider.meta_set(self.db, "sellers", {"pos": {"x": 0.0, "y": 0.0, "z": 0.0, "name": "Me"},
                                                  "fetched": time.time(), "uc": uc, "vista": []})
        s = self.state.sellers_summary()
        x = s["uc"]["nearest"]
        self.assertEqual((x["name"], x["carrier_name"], x["system"], x["squadron"], x["yours"]),
                         ("7738", "THE WINCHESTER", "Hajangai", True, False))
        self.assertEqual((s["uc"]["sell"]["name"], s["vista"]["sell"]["name"]), ("7738", "7738"))
        self.assertEqual(len([y for y in [s["uc"]["nearest"], s["uc"]["station"]] if y["name"] == "7738"]), 1)
        # no UC there: not in the UC list, and Spansh's report of it is not either
        self.spansh_services(["Vista Genomics"])
        s = self.state.sellers_summary()
        self.assertEqual((s["uc"]["nearest"]["name"], s["vista"]["nearest"]["name"]), ("Far Port", "7738"))

    def spansh_services(self, names):
        sp = ed_outrider.meta_get(self.db, "squadron_carrier_spansh")
        sp["row"]["services"] = [dock.SPANSH_SERVICES[n] for n in names]
        ed_outrider.meta_set(self.db, "squadron_carrier_spansh", sp)

    def test_in_the_dock_finder(self):
        self.spansh(spansh_record())
        spansh = dock.spansh_rows([spansh_record(updated_at="2025-01-01T00:00:00Z"),
                                   dict(spansh_record(), name="ABC-12Z", carrier_name="A STRANGER", market_id=1)])
        self.assertEqual([r["squadron"] for r in spansh], [True, False])   # a four-letter callsign: a squadron's
        rows = dock.merge(spansh, [], None, dock.squadron_row(self.state.squadron_carrier_summary()))
        mine = [r for r in rows if r["callsign"] == "7738"]
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["own"], mine[0]["squadron"], mine[0]["source"]), (True, True, "journal"))
        out = dock.nearest(rows, self.j.pos, need=("UC",), age_days=30)
        got = {r["callsign"]: r for r in out["rows"]}
        # never hidden as an old report, and no "squadron only" warning: you may dock there
        self.assertEqual(got["7738"]["warn"], [])
        self.assertEqual(got["ABC-12Z"]["warn"], ["squadron only"])
        said = dock.spoken(out, ["UC"], None)
        self.assertIn("THE WINCHESTER, your squadron's carrier", said)


class ReviewEight(unittest.TestCase):
    """The Opus review of 2026-10-30 (round 8): each through the State's real path."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        for e in login("2026-07-19T20:44"):
            self.j.handle(e)

    def finder(self, q=None):
        """State.nearest_dock with test_dock's fake Spansh (its stations and carriers) and the DSSA list."""
        import test_dock
        self.state.spansh = test_dock.FakeSpansh([(200, test_dock.fixture("dssa_carriers.json")["carriers"], '"e1"', "Thu")])
        return asyncio.run(self.state.nearest_dock({"age": "3650", **(q or {})}))

    def test_the_finder_with_it_located(self):
        """[0] Its id64 was a string among ints: the default (permit) path sorted them and raised TypeError."""
        out, status = self.finder()
        self.assertEqual(status, 200)
        mine = [r for r in out["rows"] if r.get("squadron") and r.get("own")]
        self.assertEqual([(r["system"], r["id64"]) for r in mine], [("Hajangai", str(HAJANGAI))])   # the page's string
        self.assertEqual(self.state.locate(HAJANGAI)[0], "Hajangai")   # its 🎯 resolves (nearest_found by int)

    def test_no_name_yet(self):
        """[1] Before Spansh names it: no blank spoken name, Spansh's row of it dropped by market id, a name in the
        status; a dock there names its callsign."""
        rows = dock.spansh_rows([spansh_record()])
        row = dock.squadron_row(self.state.squadron_carrier_summary())
        self.assertEqual((row["name"], row["callsign"]), ("", ""))
        merged = dock.merge(rows, [], None, row)
        self.assertEqual([(r["callsign"], r.get("own")) for r in merged if r["kind"] == "carrier"], [("", True)])
        said = dock.spoken(dock.nearest(merged, {"x": 0.0, "y": 0.0, "z": 0.0}), ["UC"])
        self.assertTrue(said.startswith("Nearest place to dock with Universal Cartographics: your squadron's carrier, "), said)
        self.j.handle(ev("2026-07-19T21:00:00Z", "Docked", StationName="7738", StationType="FleetCarrier", StarSystem="Hajangai",
                         SystemAddress=HAJANGAI, MarketID=SC_ID, StationServices=["dock"]))
        self.assertEqual(self.state.squadron_carrier_summary()["callsign"], "7738")

    def test_moved_somewhere_never_visited(self):
        """[2] A member's CarrierLocation has no coordinates: the system is placed from Spansh, as your own carrier's."""
        self.j.handle(ev("2026-07-21T10:00:52Z", "CarrierLocation", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         StarSystem="Far Away", SystemAddress=999))
        asked = []

        async def lookup(id64, interactive=True):
            asked.append(id64)
            return {"system": {"coords": {"x": 10.0, "y": 0.0, "z": 0.0}}}
        self.state.spansh = types.SimpleNamespace(lookup=lookup)

        async def go():
            self.state.maybe_locate_squadron_carrier()
            await self.state.sc_locate_task
        asyncio.run(go())
        s = self.state.squadron_carrier_summary()
        self.assertEqual((asked, s["system"], s["x"]), ([999], "Far Away", 10.0))
        self.assertEqual(ed_outrider.meta_get(self.db, "squadron_carrier")["x"], 10.0)

    def test_distance_from_the_star_only_for_the_place_shown(self):
        """[3] After a move the journal's place wins over Spansh's older report: its ls was the old system's."""
        ed_outrider.meta_set(self.db, "squadron_carrier_spansh", {"id": SC_ID, "moved_ts": None, "fetched": time.time(),
                             "row": dict(dock.spansh_rows([spansh_record(updated_at="2026-01-01T00:00:00Z")])[0], services=[])})
        self.assertEqual(self.state.squadron_carrier_summary()["ls"], 337.110597)
        self.j.handle(ev("2026-07-21T10:00:52Z", "CarrierLocation", CarrierType="SquadronCarrier", CarrierID=SC_ID,
                         StarSystem="Far Away", SystemAddress=999))
        s = self.state.squadron_carrier_summary()
        self.assertEqual((s["system"], s["ls"]), ("Far Away", None))

    def test_an_old_open_login_drops_nothing(self):
        """[4] An older folder read after the live one ends mid-login (SquadronStartup, no carrier line): the next live
        LoadGame must not drop the carrier seen since, nor what a dock there kept."""
        self.j.handle(ev("2026-10-26T12:00:00Z", "Docked", StationName="7738", StationType="FleetCarrier",
                         StarSystem="Hajangai", SystemAddress=HAJANGAI, MarketID=SC_ID, StationServices=["dock", "exploration"]))
        for e in login("2026-07-01T10:00", squadron_carrier=False)[:3]:   # LoadGame, CarrierLocation, SquadronStartup
            self.j.handle(e)
        self.j.handle(ev("2026-10-31T08:00:40Z", "LoadGame", Commander="Wes Locke"))
        sc = self.j.squadron_carrier
        self.assertIsNotNone(sc)
        self.assertEqual((sc["services"], sc["moved_ts"]), (["dock", "exploration"], "2026-07-19T20:44:52Z"))


if __name__ == "__main__":
    unittest.main()
