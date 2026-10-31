"""Unit tests: the nearest place to dock (outrider/dock.py, State.nearest_dock / dssa_list, the voice's "nearest
station"...): real Spansh and DSSA data near the author (tests/fixtures/spansh_dock.json, dssa_carriers.json), fakes
for every request.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import calendar
import json
import os
import time
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.ask as ask  # noqa: E402
import outrider.dock as dock  # noqa: E402
import outrider.materials as materials  # noqa: E402
import outrider.tools as tools  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = calendar.timegm(time.strptime("2026-10-08T15:30:00", "%Y-%m-%dT%H:%M:%S"))
HERE = {"id64": 1, "name": "Smojooe AR-E b25-8", "x": -4177.09, "y": -1.0, "z": 3324.53}


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def spansh():
    return dock.spansh_rows(fixture("spansh_dock.json")["results"])


def dssa():
    return dock.dssa_rows(fixture("dssa_carriers.json")["carriers"])


class Rows(unittest.TestCase):

    def test_dssa_list(self):
        rows = {r["callsign"]: r for r in dssa()}
        self.assertEqual(len(rows), 6)
        k = rows["K3K-L1N"]
        self.assertEqual((k["name"], k["access"], k["dssa"], k["until"]), ("[IGAU] Paradox Destiny", "All", True, "September 1, 2032"))
        self.assertEqual(k["services"], {"UC", "Vista", "Repair", "Refuel", "Shipyard", "Outfitting"})   # split words
        self.assertIn("UC", rows["TFF-34Z"]["services"])   # written "UC" there
        self.assertNotIn("Vista", rows["TFF-34Z"]["services"])
        self.assertEqual((rows["V8Z-06T"]["away"], rows["V8Z-06T"]["system"]), ("Procyon", "Preou Auscs PI-T C3-8"))
        self.assertEqual(dock.dssa_rows({"not": "a list"}), [])
        self.assertEqual(dock.dssa_rows([{"callsign": "X", "coords": {"x": "a"}}]), [])

    def test_spansh_answer(self):
        rows = spansh()
        st = [r for r in rows if r["kind"] == "station"]
        ca = {r["callsign"]: r for r in rows if r["kind"] == "carrier"}
        self.assertEqual(len(st) + len(ca), 24)
        may = next(r for r in st if r["name"] == "May Terminal")
        self.assertEqual((may["large"], may["services"] >= {"UC", "Vista"}, may["access"]), (True, True, "All"))
        self.assertFalse(next(r for r in st if r["name"] == "Skov Drilling Exploration")["large"])   # a settlement
        self.assertEqual(ca["KBT-B8Z"]["access"], "All")
        self.assertIsNone(ca["JBK-48M"]["access"])   # Spansh has none recorded
        self.assertEqual(ca["Q5B-2PZ"]["access"], "Squadron Friends")

    def test_merge_by_callsign(self):
        """A carrier in both: the DSSA badge, the fresher place, both lists of services."""
        sp = [{"kind": "carrier", "callsign": "K3K-L1N", "name": "", "system": "Old Place", "id64": 5, "x": 0.0, "y": 0.0,
               "z": 0.0, "ls": 12.0, "services": {"Shipyard"}, "pads": "L M", "large": True, "medium": True, "access": None,
               "seen": NOW - 400 * 86400, "source": "Spansh", "dssa": False, "until": "", "away": None}]
        rows = dock.merge(sp, dssa())
        k = next(r for r in rows if r["callsign"] == "K3K-L1N")
        self.assertEqual(len([r for r in rows if r["callsign"] == "K3K-L1N"]), 1)
        self.assertTrue(k["dssa"])
        self.assertEqual(k["system"], "Prai Hypoo TX-B d4")   # the DSSA sighting is fresher
        self.assertEqual((k["access"], k["source"]), ("All", "DSSA + Spansh"))
        own = dock.own_row({"id": 1, "callsign": "g0x-85z", "name": "OUT OF THE BLUE", "system": "Here", "x": 1, "y": 2, "z": 3,
                            "services": ["dock", "exploration", "vistagenomics", "refuel"]})
        self.assertEqual(own["services"], {"UC", "Vista", "Refuel"})   # what its last Docked listed
        # UC paused since (the carrier summary's word, from its crew: S55 B): not offered, though its last Docked listed it
        paused = dock.own_row({"id": 1, "callsign": "g0x-85z", "x": 1, "y": 2, "z": 3, "has_uc": False, "has_vista": True,
                               "services": ["dock", "exploration", "vistagenomics"]})
        self.assertEqual(paused["services"], {"Vista"})
        rows = dock.merge(spansh(), [], own)
        self.assertEqual([r["access"] for r in rows if r["callsign"] == "G0X-85Z"], ["yours"])   # not Spansh's copy
        self.assertIsNone(dock.own_row({"id": 1, "x": 1, "y": 2, "z": 3, "decommission": {"done": True}}))
        # complete review 2026-10-30: "aboard" only when docked at it, not when in its system
        self.assertEqual((own["aboard"], dock.own_row({"id": 1, "x": 1, "y": 2, "z": 3, "aboard": True})["aboard"]), (False, True))
        self.assertTrue(dock.squadron_row({"id": 5, "x": 1, "y": 2, "z": 3, "aboard": True})["aboard"])
        near = dock.nearest([dock.own_row({"id": 1, "callsign": "X", "system": "Here", "x": 0.0, "y": 0.0, "z": 0.0})],
                            {"x": 0.0, "y": 0.0, "z": 0.0})["rows"]
        self.assertEqual([r["aboard"] for r in near], [False])


    def test_missing_coordinate(self):
        """Review 2026-10-08 #20: a Spansh row with system_x but no y or z crashed the whole answer."""
        raw = [dict(r) for r in fixture("spansh_dock.json")["results"][:3]]
        raw[0]["system_y"] = None
        rows = dock.spansh_rows(raw)
        self.assertEqual((rows[0]["x"], rows[0]["y"], rows[0]["z"]), (None, None, None))
        out = dock.nearest(rows, HERE, age_days=36500, now=NOW)
        self.assertNotIn(rows[0]["name"], [r["name"] for r in out["rows"] if r["kind"] == rows[0]["kind"]])
        rows[1]["z"] = None   # a row built elsewhere with a hole: skipped, not a TypeError
        dock.nearest(rows, HERE, age_days=36500, now=NOW)

    def test_merge_away_only_from_the_fresher(self):
        """Review 2026-10-08 #21: a newer Spansh report placing a DSSA carrier home kept the older DSSA sighting's
        "last seen at" warning."""
        v = next(r for r in dssa() if r["callsign"] == "V8Z-06T")   # away at Procyon in the list
        sp = [{"kind": "carrier", "callsign": "V8Z-06T", "name": "", "system": "Preou Auscs PI-T C3-8", "id64": 9,
               "x": 1.0, "y": 2.0, "z": 3.0, "ls": 1.0, "services": set(), "pads": "L M", "large": True, "medium": True,
               "access": "All", "seen": (v["seen"] or 0) + 86400, "source": "Spansh", "dssa": False, "until": "", "away": None}]
        k = next(r for r in dock.merge(sp, dssa()) if r["callsign"] == "V8Z-06T")
        self.assertEqual((k["system"], k["away"]), ("Preou Auscs PI-T C3-8", None))
        sp[0]["seen"] = (v["seen"] or 0) - 86400   # the DSSA sighting fresher: the warning stays
        k = next(r for r in dock.merge(sp, dssa()) if r["callsign"] == "V8Z-06T")
        self.assertEqual(k["away"], "Procyon")


class Nearest(unittest.TestCase):

    def rows(self):
        own = dock.own_row({"id": 1, "callsign": "G0X-85Z", "name": "OUT OF THE BLUE", "system": "Smojooe AR-E b25-8",
                            "x": HERE["x"], "y": HERE["y"], "z": HERE["z"], "services": ["exploration", "vistagenomics"]})
        return dock.merge(spansh(), dssa(), own)

    def test_selling_data(self):
        out = dock.nearest(self.rows(), HERE, need={"UC", "Vista"}, pad="L", age_days=30, laden=76.2, now=NOW)
        r = out["rows"]
        self.assertEqual((r[0]["callsign"], r[0]["here"], r[0]["warn"]), ("G0X-85Z", True, []))   # yours, here
        names = [x["callsign"] or x["name"] for x in r]
        self.assertEqual(names[1:3], ["KBT-B8Z", "JBK-48M"])
        self.assertEqual(r[2]["warn"], ["docking not reported"])
        self.assertIn("May Terminal", names)
        self.assertIn("K3K-L1N", names)   # the DSSA list
        self.assertGreater(out["hidden"]["old"], 3)   # reports older than 30 days (carriers move)
        k = r[1]
        self.assertEqual((k["jumps"], k["ls"], k["services"][:2]), (10, 235, ["UC", "Vista"]))

    def test_filters_and_warnings(self):
        out = dock.nearest(self.rows(), HERE, need={"Repair"}, pad="L", age_days=120, now=NOW)
        q5b = next(x for x in out["rows"] if x["callsign"] == "Q5B-2PZ")
        self.assertEqual(q5b["warn"], ["squadron and friends only"])
        self.assertGreater(out["hidden"]["pad"], 0)   # settlements without a large pad
        self.assertEqual(dock.nearest(self.rows(), HERE, need={"Repair"}, pad=None, age_days=120, now=NOW)["hidden"]["pad"], 0)
        only = dock.nearest(self.rows(), HERE, stations=False, age_days=3650, now=NOW)["rows"]
        self.assertTrue(all(x["kind"] == "carrier" for x in only))
        st = dock.nearest(self.rows(), HERE, carriers=False, age_days=3650, now=NOW)["rows"]
        self.assertEqual([x["callsign"] for x in st if x["kind"] == "carrier"], ["G0X-85Z"])   # yours stays
        may = next(x for x in self.rows() if x["name"] == "May Terminal")
        out = dock.nearest(self.rows(), HERE, age_days=3650, permits={may["id64"]}, now=NOW)
        self.assertNotIn("May Terminal", [x["name"] for x in out["rows"]])
        self.assertGreater(out["hidden"]["permit"], 0)
        away = dock.nearest(self.rows(), HERE, age_days=3650, now=NOW, limit=200)["rows"]
        self.assertIn("last seen at Procyon", next(x for x in away if x["callsign"] == "V8Z-06T")["warn"])

    def test_spoken(self):
        out = dock.nearest(self.rows(), HERE, need={"Vista"}, pad="L", age_days=30, laden=76.2, now=NOW)
        self.assertEqual(dock.spoken(out, ["Vista"]), "Nearest place to dock with Vista Genomics: KBT-B8Z, a fleet carrier, "
                                                      "712 light years away, in Smojooe QI-T d3-37.")
        # Review 2026-10-08 #4: a place in your own system is the nearest of all (only your own carrier, where you
        # are, is skipped: you are at it)
        here = dict(next(r for r in self.rows() if r["name"] == "May Terminal"), x=HERE["x"], y=HERE["y"], z=HERE["z"],
                    system=HERE["name"])
        out = dock.nearest(self.rows() + [here], HERE, need={"Vista"}, age_days=36500, now=NOW)
        self.assertEqual(dock.spoken(out, ["Vista"], "station"),
                         "Nearest station with Vista Genomics: May Terminal, a coriolis starport, here in Smojooe AR-E b25-8.")
        out = dock.nearest(self.rows(), HERE, carriers=False, need={"UC"}, age_days=30, now=NOW)
        self.assertTrue(dock.spoken(out, ["UC"], "station").startswith(
            "Nearest station with Universal Cartographics: May Terminal, a coriolis starport, 2,111 light years away"))
        self.assertEqual(dock.spoken({"rows": []}, [], "carrier"), "No carrier is known nearby with recent enough reports.")


class Traders(unittest.TestCase):
    """S54: material traders, from Spansh's real answers (scripts/trader_probe.py, tests/fixtures/spansh_traders.json):
    the kind is the station's `material_trader` field; a few traders (Colonia's outposts) have none."""
    SOL = {"id64": 10477373803, "name": "Sol", "x": 0.0, "y": 0.0, "z": 0.0}
    SEEN = calendar.timegm(time.strptime("2026-10-12T23:00:00", "%Y-%m-%dT%H:%M:%S"))

    def rows(self, which):
        return dock.spansh_rows(fixture("spansh_traders.json")[which]["results"])

    def test_kinds(self):
        rows = {r["name"]: r for r in self.rows("sol_by_service")}
        self.assertTrue({"Trader", "Manufactured"} <= rows["Patterson Enterprise"]["services"])
        self.assertTrue({"Trader", "Raw"} <= rows["Broglie Terminal"]["services"])
        self.assertNotIn("Raw", rows["Patterson Enterprise"]["services"])
        col = {r["name"]: r for r in self.rows("colonia_by_service")}
        self.assertIn("Trader", col["The Divine Apparatus"]["services"])   # the service listed, no kind: never guessed
        self.assertFalse(set(dock.TRADER_KINDS) & col["The Divine Apparatus"]["services"])
        self.assertIn("Raw", col["TolaGarf's Junkyard"]["services"])
        self.assertTrue(all(r["services"] >= {"Trader", "Raw"} for r in self.rows("sol_raw_by_kind")))
        # a carrier never has one, whatever a report says
        carrier = dict(fixture("spansh_traders.json")["sol_by_service"]["results"][0], type="Drake-Class Carrier", name="X1X-11X")
        self.assertFalse({"Trader", "Manufactured"} & dock.spansh_rows([carrier])[0]["services"])

    def test_nearest_of_a_kind(self):
        rows = self.rows("sol_by_service")
        out = dock.nearest(rows, self.SOL, need={"Raw"}, age_days=30, now=self.SEEN)
        self.assertEqual([r["name"] for r in out["rows"]], ["Broglie Terminal"])
        self.assertEqual(out["rows"][0]["services"][-2:], ["Trader", "Raw"])   # in SERVICES' order
        self.assertEqual(out["hidden"]["service"], 4)
        col = self.rows("colonia_by_service")
        colonia = {"x": -9530.5, "y": -910.28125, "z": 19808.125}
        anyk = dock.nearest(col, colonia, need={"Trader"}, age_days=30, now=self.SEEN)["rows"]
        self.assertEqual(anyk[1]["name"], "The Divine Apparatus")   # a trader of no reported kind: still a trader
        self.assertNotIn("The Divine Apparatus", [r["name"] for r in dock.nearest(col, colonia, need={"Encoded"},
                                                                                 age_days=30, now=self.SEEN)["rows"]])

    def test_spoken(self):
        out = dock.nearest(self.rows("sol_by_service"), self.SOL, need={"Raw"}, age_days=30, now=self.SEEN)
        self.assertEqual(dock.spoken(out, ["Raw"]),
                         "Nearest raw material trader: Broglie Terminal, an ocellus starport, 11 light years away, in 61 Cygni.")
        out = dock.nearest(self.rows("sol_by_service"), self.SOL, need={"Trader"}, age_days=30, now=self.SEEN)
        self.assertEqual(dock.spoken(out, ["Trader"]), "Nearest material trader: Patterson Enterprise, a coriolis starport "
                                                       "trading manufactured materials, 9 light years away, in Sirius.")
        col = self.rows("colonia_by_service")
        out = dock.nearest(col[1:], {"x": -9530.5, "y": -910.28125, "z": 19808.125}, need={"Trader"}, age_days=30, now=self.SEEN)
        self.assertIn("a planetary outpost whose trader's kind is not reported", dock.spoken(out, ["Trader"]))
        self.assertEqual(dock.spoken({"rows": []}, ["Encoded"]), "No encoded material trader is known nearby with recent enough reports.")
        self.assertEqual(dock.spoken({"rows": []}, ["UC", "Trader"], "station"),
                         "No material trader with Universal Cartographics is known nearby with recent enough reports.")

    def test_short_materials_carry_their_kind(self):
        """The Materials tab's "⇄ nearest raw trader" needs each recipe material's category (None for a commodity)."""
        inv = materials.inventory({"counts": {"iron": 10}, "names": {},
                                   "recipes": {"Odd Basic": {"materials": {"tritium": 1}, "ts": "2026-10-12T00:00:00Z", "n": 1}}})
        cats = {m["id"]: m["category"] for r in inv["synthesis"] for m in r["materials"]}
        self.assertEqual((cats["iron"], cats["mechanicalequipment"], cats["tritium"]), ("Raw", "Manufactured", None))

    def test_ai_tool(self):
        spec = tools.TOOLS["nearest_dock"]["schema"]["properties"]
        self.assertTrue({"Trader", "Raw", "Manufactured", "Encoded"} <= set(spec["need"]["items"]["enum"]))
        seen = []

        async def get(path, params=None):
            seen.append(dict(params or {}))
            return {"rows": [], "hidden": {}}
        asyncio.run(tools.call("nearest_dock", {"need": ["Raw"]}, get, 5))
        self.assertEqual(seen[0]["need"], "Raw")


class FakeSpansh:
    """dock_search / permit_ids / get_if_changed without a network: each call recorded."""

    def __init__(self, dssa_answers):
        self.dssa_answers, self.calls = list(dssa_answers), []

    async def dock_search(self, pos, need=()):
        self.calls.append("search")
        self.needs = getattr(self, "needs", []) + [list(need)]
        return fixture("spansh_dock.json")["results"]

    async def permit_ids(self, ids):
        self.calls.append("permits")
        return set()

    async def get_if_changed(self, url, etag=None, modified=None):
        self.calls.append(("dssa", etag))
        a = self.dssa_answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


class Endpoint(unittest.TestCase):

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.sp = FakeSpansh([(200, fixture("dssa_carriers.json")["carriers"], '"e1"', "Thu"),
                              (304, None, '"e1"', "Thu"), ed_outrider.ClientError("down")])
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.spansh = self.sp

    def ask(self, **q):
        return asyncio.run(self.state.nearest_dock({k: str(v) for k, v in q.items()}))

    def test_rows_can_be_targeted(self):
        """S31: 🎯 on a Nearest row targets its system by id64: the systems the finder listed are located (route "system"),
        those without an id64 (a DSSA carrier Spansh has not placed) have no 🎯; the list kept is bounded."""
        self.j.pos = dict(HERE)
        out, _ = self.ask(age=3650)
        row = next(r for r in out["rows"] if r["id64"] and not r.get("here"))
        tgt, why = self.state.route_target("system", int(row["id64"]))
        self.assertIsNone(why)
        self.assertEqual((tgt["name"], tgt["id64"], tgt["route"]), (row["system"], int(row["id64"]), None))
        self.assertTrue(any(r["id64"] is None for r in out["rows"]))   # the DSSA list's: nothing to aim at
        with unittest.mock.patch.object(ed_outrider, "NEAREST_FOUND_KEEP", 2):
            self.ask(age=3650, need="repair")
        self.assertEqual(len(self.state.nearest_found), 2)

    def test_validation(self):
        self.assertEqual(self.ask()[1], 409)   # no position yet
        self.j.pos = dict(HERE)
        self.assertEqual(self.ask(age="soon")[1], 400)
        self.assertEqual(self.ask(age=0)[1], 400)

    def test_dssa_on_demand(self):
        """Fetched when asked, at most hourly, conditionally; an error keeps the copy; cached=1 never fetches."""
        self.j.pos = dict(HERE)
        out, status = self.ask(need="uc,vista", age=3650)
        self.assertEqual(status, 200)
        self.assertEqual(self.sp.calls.count(("dssa", None)), 1)
        self.assertTrue(any(r["callsign"] == "K3K-L1N" and r["dssa"] for r in out["rows"]))
        self.assertEqual(out["dssa"]["count"], 6)
        self.ask()   # within the hour: no request
        self.assertEqual(len([c for c in self.sp.calls if c[0] == "dssa"]), 1)
        d = ed_outrider.meta_get(self.db, "dssa")
        ed_outrider.meta_set(self.db, "dssa", dict(d, checked=time.time() - 7200))
        out, _ = self.ask(age=3650)   # an hour on: asked again with its etag, unchanged (304), the copy kept
        self.assertIn(("dssa", '"e1"'), self.sp.calls)
        self.assertEqual(out["dssa"]["count"], 6)
        ed_outrider.meta_set(self.db, "dssa", dict(ed_outrider.meta_get(self.db, "dssa"), checked=0))
        out, _ = self.ask(age=3650)   # EDAstro unreachable: the copy kept, the error said
        self.assertEqual(out["dssa"]["count"], 6)
        self.assertTrue(out["errors"])
        n = len(self.sp.calls)
        ed_outrider.meta_set(self.db, "dssa", dict(ed_outrider.meta_get(self.db, "dssa"), checked=0))
        self.ask(cached=1)   # the voice and the AI never fetch
        self.assertNotIn("dssa", [c[0] for c in self.sp.calls[n:]])


    def test_filter_changes_reuse_the_search(self):
        """Review 2026-10-08 #13: every tick in the finder made the same three Spansh requests again. The search and
        the permit check are reused for DOCK_CACHE_S; a different set of services is a new search (it is in the
        request since #6)."""
        self.j.pos = dict(HERE)
        self.ask(age=30)
        self.ask(age=90, pad="M")
        self.ask(age=90, stations=0)
        self.assertEqual((self.sp.calls.count("search"), self.sp.calls.count("permits")), (1, 1))
        self.ask(need="vista")
        self.assertEqual(self.sp.calls.count("search"), 2)
        self.assertEqual(self.sp.needs[-1], ["Vista"])
        self.state.dock_cache["search"] = (self.state.dock_cache["search"][0], time.time() - 999,
                                           self.state.dock_cache["search"][2])
        self.ask(need="vista")   # stale: asked again
        self.assertEqual(self.sp.calls.count("search"), 3)
        out, _ = self.ask(need="raw,uc")   # S54: the trader kinds are needs like the services
        self.assertEqual((self.sp.needs[-1], out["need"]), (["Raw", "UC"], ["Raw", "UC"]))

    def test_dssa_odd_answer_is_a_failed_check(self):
        """Review 2026-10-08 #14: a 200 that is not a list (an error object, a notice) was stamped as a fresh check
        with no error, so nothing asked again for an hour and the footer said all was well."""
        self.j.pos = dict(HERE)
        self.sp.dssa_answers = [(200, {"error": "maintenance"}, '"e2"', "Fri"),
                                (200, fixture("dssa_carriers.json")["carriers"], '"e1"', "Thu")]
        out, _ = self.ask(age=3650)
        self.assertEqual(out["dssa"]["count"], 0)
        self.assertTrue(out["errors"])
        self.assertIsNone((ed_outrider.meta_get(self.db, "dssa") or {}).get("checked"))
        out, _ = self.ask(age=3650)   # asked again at once, not an hour later
        self.assertEqual(out["dssa"]["count"], 6)


class SpanshRequests(unittest.TestCase):
    """The station search's body: Spansh's services filter is a list of {name}, each required. The {"value": [...]}
    shape was ignored without a word (found 2026-10-08 with the review's #6): the finder saw only the 50 nearest, and
    the Unsold tile's nearest Universal Cartographics / Vista sellers were just the nearest stations."""

    def setUp(self):
        from support import _HwSession
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.sp = ed_outrider.Spansh(self.db)
        self.Session = _HwSession

    def test_dock_search_sends_the_services(self):
        self.sp.session = self.Session([(200, {"results": []})])
        asyncio.run(self.sp.dock_search(HERE, ["UC", "Vista"]))
        bodies = [c[2] for c in self.sp.session.calls]
        self.assertEqual(len(bodies), 2)   # stations, then carriers
        for b in bodies:
            self.assertEqual(b["filters"]["services"], [{"name": "Universal Cartographics"}, {"name": "Vista Genomics"}])
        self.sp.session = self.Session([(200, {"results": []})])
        asyncio.run(self.sp.dock_search(HERE))
        self.assertNotIn("services", self.sp.session.calls[0][2]["filters"])

    def test_trader_search(self):
        """S54: a trader of one kind is Spansh's material_trader filter, any kind the Material Trader service; stations
        only (carriers never have one); two kinds at once can match nothing and are not asked."""
        def bodies(need):
            self.sp.session = self.Session([(200, {"results": []})])
            out = asyncio.run(self.sp.dock_search(HERE, need))
            return out, [c[2]["filters"] for c in self.sp.session.calls]
        _, f = bodies(["Raw"])
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["material_trader"], f[0].get("services")), ({"value": ["Raw"]}, None))
        self.assertNotIn(ed_outrider.outrider.cargo.CARRIER_TYPE, f[0]["type"]["value"])
        _, f = bodies(["Trader"])
        self.assertEqual((len(f), f[0]["services"], "material_trader" in f[0]), (1, [{"name": "Material Trader"}], False))
        _, f = bodies(["UC", "Trader", "Encoded"])
        self.assertEqual((f[0]["services"], f[0]["material_trader"]), ([{"name": "Universal Cartographics"}], {"value": ["Encoded"]}))
        out, f = bodies(["Raw", "Encoded"])
        self.assertEqual((out, f), ([], []))

    def test_sellers_offer_the_service(self):
        uc = {"name": "Has UC", "system_name": "A", "system_id64": 1, "distance": 5, "services": [{"name": "Universal Cartographics"}]}
        none = {"name": "Settlement", "system_name": "B", "system_id64": 2, "distance": 3, "services": [{"name": "Refuel"}]}
        self.sp.session = self.Session([(200, {"results": [none, uc]})])
        got = asyncio.run(self.sp.stations("Universal Cartographics", HERE))
        self.assertEqual([x["name"] for x in got], ["Has UC"])
        self.assertEqual(self.sp.session.calls[0][2]["filters"]["services"], [{"name": "Universal Cartographics"}])


class Voice(unittest.TestCase):

    def test_phrases(self):
        phrases = ask.load_phrases()
        for text, cmd in (("nearest station", "nearest_dock"), ("Vespa, nearest vista", "nearest_dock"),
                          ("where can I dock", "nearest_dock"), ("nearest carrier with repair", "nearest_dock"),
                          ("nearest unvisited", "nearest_unvisited"), ("nearest", None)):
            self.assertEqual(ask.match(text, phrases), cmd, text)
        self.assertEqual(ask.nearest_query("nearest carrier with vista genomics and repair"), (["Vista", "Repair"], "carrier"))
        self.assertEqual(ask.nearest_query("nearest station"), ([], "station"))
        self.assertEqual(ask.nearest_query("nearest UC"), (["UC"], None))
        # S54: material traders
        for text in ("nearest raw material trader", "Vespa, nearest material trader", "where's an encoded trader",
                     "nearest data trader", "nearest manufactured material traders"):
            self.assertEqual(ask.match(text, phrases), "nearest_dock", text)
        self.assertEqual(ask.nearest_query("nearest raw material trader"), (["Raw"], None))
        self.assertEqual(ask.nearest_query("nearest material trader"), (["Trader"], None))
        self.assertEqual(ask.nearest_query("nearest data trader"), (["Encoded"], None))
        self.assertEqual(ask.nearest_query("nearest station with raw materials"), ([], "station"))   # no trader asked

    def test_answer(self):
        seen = []

        async def get(path, params=None):
            seen.append((path, dict(params or {})))
            return {"rows": [{"kind": "carrier", "name": "", "callsign": "KBT-B8Z", "system": "Smojooe QI-T d3-37", "ly": 711.5,
                              "ls": 235, "services": ["UC", "Vista"], "pads": "L M", "dssa": False, "own": False, "warn": [],
                              "age_s": 86400}], "hidden": {}, "pad": "L"}
        words = asyncio.run(ask.fixed_answer("nearest_dock", get, text="nearest carrier with vista"))
        self.assertEqual(words, "Nearest carrier with Vista Genomics: KBT-B8Z, a fleet carrier, 712 light years away, "
                                "in Smojooe QI-T d3-37.")
        self.assertEqual(seen[0][0], "/api/nearest")
        self.assertEqual((seen[0][1]["cached"], seen[0][1]["need"], seen[0][1]["stations"]), ("1", "Vista", "0"))

    def test_far_places_get_a_route(self):
        """D4 (option A): the voice's "nearest ..." also plots a neutron route to the place it named when that is further
        than [highway] voice_plot_ly (on, 500 ly by default): to its system; never while a route you have not finished is
        followed or a plot runs; the answer's shape unchanged, a sentence added."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        plots, answer = [], [({"ok": True}, 202)]
        state.highway_start_plot = lambda body: plots.append(body) or answer[0]

        def ask_at(ly, text="nearest carrier with vista"):
            async def get(path, params=None):
                return {"rows": [{"kind": "carrier", "name": "", "callsign": "KBT-B8Z", "system": "Smojooe QI-T d3-37", "ly": ly,
                                  "ls": 235, "services": ["UC", "Vista"], "pads": "L M", "dssa": False, "own": False, "warn": [],
                                  "age_s": 86400}], "hidden": {}, "pad": "L"}
            body, status = asyncio.run(state.ask(text, get))
            self.assertEqual((status, set(body), body["command"]), (200, {"answer", "spoken", "matched", "command"}, "nearest_dock"))
            return body["answer"]
        said = "Nearest carrier with Vista Genomics: KBT-B8Z, a fleet carrier, 712 light years away, in Smojooe QI-T d3-37."
        self.assertEqual(ask_at(711.5), said + " Plotting a neutron route there.")
        self.assertEqual(plots, [{"plotter": "neutron", "to": "Smojooe QI-T d3-37"}])   # the system, never the station
        self.assertEqual(ask_at(420), said.replace("712", "420"))   # within 500 ly: nothing plotted
        state.highway_cfg = dict(state.highway_cfg, voice_plot_ly=1000.0)
        self.assertEqual(ask_at(711.5), said)
        state.highway_cfg = dict(state.highway_cfg, voice_plot_ly=500.0, voice_plot=False)
        self.assertEqual(ask_at(711.5), said)
        state.highway_cfg = dict(state.highway_cfg, voice_plot=True)
        self.assertEqual(len(plots), 1)
        # a route you follow (the Highway, or the survey / trade slot): never replaced by voice; a finished one is
        with unittest.mock.patch.object(state, "highway_state", lambda: ({"id": 1}, [{}])):
            self.assertEqual(ask_at(711.5), said + " You're following a route, so I didn't plot one.")
        with unittest.mock.patch.object(state, "riches_state", lambda: ({"id": 2}, [{}])):
            self.assertEqual(ask_at(711.5), said + " You're following a route, so I didn't plot one.")
        with unittest.mock.patch.object(state, "highway_state", lambda: ({"id": 1, "done_ts": "2026-10-13T00:00:00Z"}, [{}])):
            self.assertTrue(ask_at(711.5).endswith("Plotting a neutron route there."))
        self.assertEqual(len(plots), 2)
        # the plot refused: a plot under way (409), no ship's range known (400), anything else said as it is
        answer[0] = ({"error": "a route is being plotted already"}, 409)
        self.assertTrue(ask_at(711.5).endswith("A route is being plotted already, so I didn't plot another."))
        answer[0] = ({"error": "give the jump range (ly), or pick a ship you have flown"}, 400)
        self.assertTrue(ask_at(711.5).endswith("I didn't plot a route there: I don't know your ship's jump range yet."))
        answer[0] = ({"error": "to is too long"}, 400)
        self.assertTrue(ask_at(711.5).endswith("I didn't plot a route there: to is too long."))

    def test_voice_plot_config(self):
        import argparse
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual((st["highway"]["voice_plot"], st["highway"]["voice_plot_ly"]), (True, 500.0))
        st = ed_outrider.settings_from({"highway": {"voice_plot": False, "voice_plot_ly": 800}}, args, None, ([], []))
        back = tomllib.loads(ed_outrider.config_text(st))["highway"]
        self.assertEqual((back["voice_plot"], back["voice_plot_ly"]), (False, 800))


if __name__ == "__main__":
    unittest.main()
