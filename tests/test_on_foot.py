"""Round 10's S4 and S22 (batch 7): the wrong-suit warning on a bio body, and a bounty on you with the nearest Interstellar
Factors. The lines are shaped like the author's journals (SuitLoadout 2-10 s after its Disembark; CommitCrime with
Faction, CrimeType and Bounty or Fine; ApproachSettlement with its BodyID). The page's side: tests/page_unit.js."""
import time
import types
import unittest

from support import ed_outrider
import outrider.commander
import outrider.dock

SYS, BODY = 9, 3


def ev(ts, name, **kw):
    return dict({"timestamp": ts, "event": name}, **kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()
        self.j.handle(ev(self.at(0), "FSDJump", StarSystem="Sys", SystemAddress=SYS, StarPos=[0, 0, 0]))

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 240 + s)   # live: within SHUTDOWN_LIVE_S

    def kinds(self, kind):
        return [m for m in self.j.moments if m["kind"] == kind]


class WrongSuit(Base):
    def setUp(self):
        super().setUp()
        # A 3: scanned, two genera found by the DSS
        self.j.handle(ev(self.at(1), "Scan", ScanType="Detailed", StarSystem="Sys", SystemAddress=SYS, BodyID=BODY,
                         BodyName="Sys A 3", PlanetClass="Rocky body", DistanceFromArrivalLS=500.0, Landable=True,
                         SurfaceGravity=2.0, SurfaceTemperature=180.0, AtmosphereType="CarbonDioxide",
                         WasDiscovered=True, WasMapped=False))
        self.j.handle(ev(self.at(2), "SAASignalsFound", SystemAddress=SYS, BodyID=BODY, BodyName="Sys A 3",
                         Signals=[{"Type": "$SAA_SignalType_Biological;", "Count": 2}],
                         Genuses=[{"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Genus_Localised": "Bacterium"},
                                  {"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"}]))

    def step_out(self, s, suit="utilitysuit_class1", body=BODY, srv=True, **kw):
        """A Disembark on the planet, then its SuitLoadout 3 s later (the real order)."""
        self.j.handle(ev(self.at(s), "Disembark", SRV=srv, Taxi=False, Multicrew=False, ID=33, StarSystem="Sys",
                         SystemAddress=SYS, Body=f"Sys A {body}", BodyID=body, OnStation=False, OnPlanet=True, **kw))
        if suit:
            self.j.handle(ev(self.at(s + 3), "SuitLoadout", SuitID=1, SuitName=suit, SuitName_Localised="Maverick Suit",
                             SuitMods=[], LoadoutID=4293000001, LoadoutName="Work", Modules=[]))

    def leave(self, s, body=BODY):
        self.j.handle(ev(self.at(s), "LeaveBody", StarSystem="Sys", SystemAddress=SYS, Body=f"Sys A {body}", BodyID=body))

    def said(self):
        """The wrong_suit moments the page is given (moment_extra: sampling left)."""
        return [m for m in self.state.moments_summary() if m["kind"] == "wrong_suit"]

    def test_a_maverick_on_a_bio_body_once_a_visit(self):
        self.step_out(10)
        got = self.said()
        self.assertEqual([(m["suit"], m["body"], m["left"], m["body_id"]) for m in got], [("Maverick", "A 3", 2, BODY)])
        self.step_out(60)                         # back in the SRV and out again: the same visit
        self.assertEqual(len(self.kinds("wrong_suit")), 1)
        self.leave(100)
        self.step_out(200)                        # a new visit
        self.assertEqual(len(self.kinds("wrong_suit")), 2)

    def test_the_artemis_suit_says_nothing(self):
        self.step_out(10, suit="explorationsuit_class3")
        self.assertEqual(self.kinds("wrong_suit"), [])

    def test_the_suit_line_before_the_disembark_pairs_too(self):
        """Either order within SUIT_PAIR_S (the real journals always have it after)."""
        self.j.handle(ev(self.at(8), "SwitchSuitLoadout", SuitID=2, SuitName="tacticalsuit_class2", LoadoutID=2, LoadoutName="X"))
        self.step_out(10, suit=None)
        self.assertEqual([m["suit"] for m in self.kinds("wrong_suit")], ["Dominator"])

    def test_a_suit_line_from_an_earlier_disembark_is_not_this_one(self):
        """The previous step out's SuitLoadout (minutes before) is no pair: the warning waits for this one's own line."""
        self.step_out(10, body=4, suit="utilitysuit_class1")   # another body, nothing known there: no moment kept
        self.j.handle(ev(self.at(200), "Disembark", SRV=False, Taxi=False, Multicrew=False, ID=1, StarSystem="Sys",
                         SystemAddress=SYS, Body="Sys A 3", BodyID=BODY, OnStation=False, OnPlanet=True))
        self.assertEqual([m["body_id"] for m in self.kinds("wrong_suit")], [4])
        self.j.handle(ev(self.at(203), "SuitLoadout", SuitID=3, SuitName="explorationsuit_class1", LoadoutID=3, LoadoutName="Xeno"))
        self.assertEqual([m["body_id"] for m in self.kinds("wrong_suit")], [4])   # the Artemis, after all

    def test_nothing_left_or_never_scanned(self):
        """moment_extra drops it on a body with nothing left to sample, and on one never scanned."""
        for genus, species in (("Bacterial", "Bacterial_01"), ("Stratum", "Stratum_07")):
            for kind in ("Log", "Sample", "Analyse"):
                self.j.handle(ev(self.at(5), "ScanOrganic", ScanType=kind, Genus=f"$Codex_Ent_{genus}_Genus_Name;",
                                 Species=f"$Codex_Ent_{species}_Name;", SystemAddress=SYS, Body=BODY))
        self.step_out(10)
        self.step_out(20, body=7)
        self.assertEqual(len(self.kinds("wrong_suit")), 2)   # the moments are made...
        self.assertEqual(self.said(), [])                    # ...and the page is given neither

    def test_quiet_at_a_settlement_on_the_body(self):
        """The author's first quiet rule: an ApproachSettlement on that body this visit (another body's does not count)."""
        self.j.handle(ev(self.at(5), "ApproachSettlement", Name="Hamilton Base", MarketID=1, SystemAddress=SYS, BodyID=5,
                         BodyName="Sys A 5", Latitude=1.0, Longitude=2.0))
        self.step_out(10)
        self.assertEqual(len(self.kinds("wrong_suit")), 1)
        self.leave(20)
        self.j.handle(ev(self.at(30), "ApproachSettlement", Name="Perez Silo", MarketID=2, SystemAddress=SYS, BodyID=BODY,
                         BodyName="Sys A 3", Latitude=1.0, Longitude=2.0))
        self.step_out(40)
        self.assertEqual(len(self.kinds("wrong_suit")), 1)
        self.leave(50)
        self.step_out(60)                          # the settlement was last visit's
        self.assertEqual(len(self.kinds("wrong_suit")), 2)

    def test_quiet_while_an_on_foot_mission_is_held(self):
        """The author's second quiet rule: a Mission_OnFoot_... among the missions held; handed in, the warning is back."""
        self.j.handle(ev(self.at(5), "MissionAccepted", Faction="F", Name="Mission_OnFoot_Collect_MB_name",
                         LocalisedName="Collect data", MissionID=77, Expiry=self.at(9000)))
        self.step_out(10)
        self.assertEqual(self.kinds("wrong_suit"), [])
        self.j.handle(ev(self.at(20), "MissionCompleted", Faction="F", Name="Mission_OnFoot_Collect_MB_name", MissionID=77))
        self.leave(30)
        self.step_out(40)
        self.assertEqual(len(self.kinds("wrong_suit")), 1)

    def test_not_in_a_taxi_multicrew_or_a_read_late_line(self):
        for s, taxi, crew in ((10, True, False), (100, False, True)):
            self.j.handle(ev(self.at(s), "Disembark", SRV=False, Taxi=taxi, Multicrew=crew, ID=1, StarSystem="Sys",
                             SystemAddress=SYS, Body="Sys A 3", BodyID=BODY, OnStation=False, OnPlanet=True))
            self.j.handle(ev(self.at(s + 3), "SuitLoadout", SuitID=1, SuitName="utilitysuit_class1", LoadoutID=1, LoadoutName="W"))
        old = "2020-01-01T00:00:"
        self.j.handle(ev(old + "00Z", "Disembark", SRV=False, Taxi=False, Multicrew=False, ID=1, StarSystem="Sys",
                         SystemAddress=SYS, Body="Sys A 3", BodyID=BODY, OnStation=False, OnPlanet=True))
        self.j.handle(ev(old + "03Z", "SuitLoadout", SuitID=1, SuitName="utilitysuit_class1", LoadoutID=1, LoadoutName="W"))
        self.assertEqual(self.kinds("wrong_suit"), [])

    def test_the_on_foot_strip_knows_the_suit(self):
        """on_body carries the suit on foot (the strip's ⚠), and its quiet rules."""
        self.step_out(10)
        self.j.status_json = {"live": True, "body": "Sys A 3", "flags": 0, "flags2": 1}
        ob = self.state.on_body()
        self.assertEqual((ob["how"], ob["suit"], ob["sampler"], ob["suit_quiet"]), ("on foot", "Maverick", False, False))
        self.j.handle(ev(self.at(30), "ApproachSettlement", Name="Perez Silo", MarketID=2, SystemAddress=SYS, BodyID=BODY,
                         BodyName="Sys A 3", Latitude=1.0, Longitude=2.0))
        self.assertTrue(self.state.on_body()["suit_quiet"])
        self.j.status_json = {"live": True, "body": "Sys A 3", "flags": 1 << 26, "flags2": 0}   # in the SRV: no suit
        self.assertNotIn("suit", self.state.on_body())

    def test_the_missions_snapshot_marks_on_foot_missions(self):
        """A mission held from before rows kept on_foot gets it from the next login's Missions list (no re-read)."""
        held = {"5": {"id": 5, "name": "Old", "expiry": None, "passengers": False}}
        got = outrider.commander.mission_apply(held, {"event": "Missions", "timestamp": self.at(0), "Active": [
            {"MissionID": 5, "Name": "Mission_OnFoot_Salvage_MB_name", "PassengerMission": False, "Expires": 600}]})
        self.assertTrue(got["5"]["on_foot"])
        old = {"6": {"id": 6, "name": "Older", "expiry": None, "passengers": False}}   # a row from before, never relisted
        self.assertEqual(outrider.commander.missions(old)[0]["on_foot"], False)

    def test_suit_words(self):
        self.assertEqual([ed_outrider.suit_words(s) for s in ("utilitysuit_class1", "TacticalSuit_Class3", "explorationsuit_class5",
                                                              "flightsuit", "")],
                         ["Maverick", "Dominator", "Artemis", "flight", "unknown"])


class Wanted(Base):
    def crime(self, s, **kw):
        self.j.handle(ev(self.at(s), "CommitCrime", **kw))

    def test_a_bounty_once_per_stay_and_faction(self):
        self.crime(10, CrimeType="dockingMinorBlockingLandingPad", Faction="Brewer Corporation", Fine=500)   # a fine: nothing
        self.crime(30, CrimeType="dockingMajorBlockingLandingPad", Faction="Brewer Corporation", Bounty=500)
        self.crime(40, CrimeType="murder", Faction="Brewer Corporation", Bounty=8000)                         # said already
        self.crime(50, CrimeType="assault", Faction="Other Faction", Bounty=200)
        got = [(m["faction"], m["bounty"], m["crime"], m["system"], m["system_name"]) for m in self.kinds("wanted")]
        self.assertEqual(got, [("Brewer Corporation", 500, "blocking a landing pad", "9", "Sys"),
                               ("Other Faction", 200, "assault", "9", "Sys")])
        self.j.handle(ev(self.at(100), "FSDJump", StarSystem="Next", SystemAddress=10, StarPos=[1, 0, 0]))
        self.j.handle(ev(self.at(200), "FSDJump", StarSystem="Sys", SystemAddress=SYS, StarPos=[0, 0, 0]))
        self.crime(210, CrimeType="dockingMajorTresspass", Faction="Brewer Corporation", Bounty=500)          # a new stay
        self.assertEqual(len(self.kinds("wanted")), 3)
        self.crime(220, CrimeType="x", Faction="New", Bounty=0)
        self.j.handle(ev("2020-01-01T00:00:00Z", "CommitCrime", CrimeType="murder", Faction="Late", Bounty=900))   # read late
        self.assertEqual(len(self.kinds("wanted")), 3)
        self.assertIn("wanted", [m["kind"] for m in self.state.moments_summary()])

    def test_crime_words(self):
        self.assertEqual([ed_outrider.crime_words(k) for k in ("dockingMajorTresspass", "passengerWanted", None)],
                         ["trespass at a station", "passenger wanted", ""])

    def test_interstellar_factors_in_the_finder(self):
        """Spansh's "Interstellar Factors Contact" and the game's "facilitator" are the finder's Factors, asked for as
        need=factors (GET /api/nearest's need names are SERVICES' in lower case)."""
        rows = outrider.dock.spansh_rows([{"name": "Hub", "type": "Coriolis Starport", "system_name": "Sys", "system_x": 0,
                                           "system_y": 0, "system_z": 0, "updated_at": "2026-11-01 00:00:00+00",
                                           "services": [{"name": "Interstellar Factors Contact"}, {"name": "Repair"}]}])
        self.assertEqual(rows[0]["services"], {"Factors", "Repair"})
        self.assertEqual(outrider.dock.game_services(["dock", "facilitator"]), {"Factors"})
        self.assertIn("factors", {s.lower() for s in outrider.dock.SERVICES})
        found = outrider.dock.nearest(rows, {"x": 0, "y": 0, "z": 0}, need=["Factors"], now=ed_outrider.ts_seconds("2026-11-02T00:00:00Z"))
        self.assertEqual([r["name"] for r in found["rows"]], ["Hub"])
        self.assertEqual(outrider.dock.spoken(found, ["Factors"]),
                         "Nearest place to dock with Interstellar Factors: Hub, a coriolis starport, here in Sys.")


if __name__ == "__main__":
    unittest.main()
