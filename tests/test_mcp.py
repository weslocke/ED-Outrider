"""The read-only tool registry (outrider/tools.py) and its MCP bridge (outrider/mcp.py), tablet plan phase 2: every tool
reads GET routes only, answers compactly with capped lists, says when Outrider isn't running, and the stdio transport
speaks MCP's JSON-RPC. Never port 8025: a fake `get`, or a test server on a free port."""
import asyncio
import contextlib
import io
import json
import tomllib
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path

import outrider.auth  # noqa: E402
import outrider.mcp as mcp  # noqa: E402
import outrider.tools as tools  # noqa: E402

SYS = "18207037532889"
FIX = {
    "/api/status": {"system": "Start", "id64": SYS, "region": "Inner Orion Spur", "fuel_pct": 41, "fuel_jumps": 6,
                    "jump_range": 72.5, "boost": None, "target": "Next One", "unsold": 1234567, "on_body": None,
                    "sampling": None, "carrier": None, "commander": "Smoke", "coords": [0, 0, 0]},
    "/api/nearby": {"radius": 25, "sphere_cut": None, "position": {"id": SYS, "name": "Start"},
                    "unsold": {"total": 900, "carto": {"estimated_payout": 600, "systems": 2, "bodies": 9,
                                                       "first_discoveries": 2, "mapped": 1}, "bio": {"estimated_value": 300, "samples": 1}},
                    "since_sale": {"days": 3.5, "jumps": 40},
                    # highway_summary's shape (S9-S2's route_next reads the payload's routes)
                    "highway": {"destination": "Colonia", "created_ts": "2026-10-01T00:00:00Z", "complete": False, "off_route": False,
                                "next": {"name": "Neu", "distance": 400.2, "neutron": True, "refuel": False},
                                "jumps_left": 42, "refuel_in": 3},
                    "systems": [{"id": SYS, "name": "Start", "distance": 0, "visited": True},
                                {"id": "2", "name": "Far Rich", "distance": 20.5, "visited": False, "value_max": 9000000, "main_class": "K",
                                 "main_scoopable": True, "bodies_known": 4, "body_count": 9, "status": "partial"},
                                {"id": "3", "name": "Near Seen", "distance": 3.25, "visited": True, "value_max": 10},
                                {"id": "4", "name": "Near New", "distance": 7.0, "visited": False, "firsts": {"sale": "unsold"}},
                                {"id": "5", "name": "Route Only", "distance": 1.0, "visited": False, "source": "route"}]},
    f"/api/system/{SYS}": {"name": "Start", "region": "Inner Orion Spur", "value_now": 5, "value_max": 50,
                           "leaving": {"honked": True, "scanned": 3, "body_count": 4, "unscanned": 1, "bio_pending": [{"body": "A 1"}],
                                       # the real shapes (leaving_summary): short labels, and the detailed list
                                       "unmapped_valuable": ["A 2 (HMC T)"],
                                       "unmapped": [{"body": "A 2", "subtype": "High metal content world", "increment": 500000,
                                                     "special": True},
                                                    {"body": "A 3", "subtype": "Icy body", "increment": 900, "special": False}]},
                           "bodies": [{"name": "A", "type": "Star", "subtype": "K (Yellow-Orange) Star", "value_max": 10},
                                      {"name": "A 1", "type": "Planet", "subtype": "Rocky body", "value_max": 30, "bio": 2, "landable": True,
                                       "gravity": 0.123, "organics": [{"species": "Bacterium Volu", "samples": 2, "done": False, "state": "aboard"}]},
                                      {"name": "A 2", "type": "Planet", "subtype": "High metal content world", "value_max": 40}]},
    "/api/body": {"system": "Start", "full_name": "Start A 1", "row": {"name": "A 1", "subtype": "Rocky body", "gravity": 0.123,
                  "landable": True, "bio": 2, "bio_guess": [{"genus": "Bacterium", "best": "Bacterium Volu", "value": 19000000}],
                  "mining_odds": {"top": [{"name": "Platinum", "pct": 30}]}, "radius_km": 1500.4, "temperature": 180.2}},
    "/api/firsts": {"firsts": [{"name": "Unsold One", "state": "unsold", "value": 100, "distance": 3},
                               {"name": "Unsold Two", "state": "unsold", "value": 300, "distance": 9},
                               {"name": "Lost One", "state": "lost"}, {"name": "Sold One", "state": "sold"}]},
    "/api/left": {"systems": [{"name": f"Left {i}", "distance": i, "unfound": 1, "bio": [], "maps": [], "maps_total": 0} for i in range(30)]},
    "/api/highway": {"route": {"to": "Colonia", "summary": {"next": {"name": "Neu", "distance": 400.2, "neutron": True, "refuel": False},
                                                           "jumps_left": 42, "ly_left": 17301.3, "refuel_in": 3, "off_route": False},
                               "ahead": [{"system": f"Hop {i}", "distance": 100 + i, "neutron": i % 2 == 0, "refuel": False} for i in range(8)]}},
    "/api/history": {"all_time": {"jumps": 9}, "sessions": [{"start": "2026-10-01T00:00:00Z", "end": "2026-10-01T01:00:00Z", "jumps": 3,
                                                             "ly": 120.44, "firsts": 1, "mapped": 0, "samples": 0,
                                                             "systems": [{"name": "Start"}, {"name": "Next One"}]}]},
    "/api/materials": {"rows": [{"name": "Polonium", "grade": 4, "category": "Raw", "count": 30, "cap": 150},
                                {"name": "Carbon", "grade": 1, "category": "Raw", "count": 290, "cap": 300},
                                {"name": "Tellurium", "grade": 4, "category": "Raw", "count": 0, "cap": 150}],
                       "snapshot_ts": "2026-10-01T00:00:00Z",
                       "synthesis": [{"name": "FSD injection premium", "group": "fsd", "grade": "premium", "craftable": 2, "limit": "Polonium"},
                                     {"name": "FSD injection standard", "group": "fsd", "grade": "standard", "craftable": 5, "limit": "Cadmium"},
                                     {"name": "FSD injection basic", "group": "fsd", "grade": "basic", "craftable": 31, "limit": "Vanadium"},
                                     {"name": "AFMU refill premium", "group": "ship", "grade": "premium", "craftable": 0, "limit": "Ruthenium"}]},
    "/api/nearest": {"rows": [{"kind": "carrier", "name": "", "callsign": "KBT-B8Z", "system": "Smojooe QI-T d3-37", "ly": 711.5,
                               "ls": 235, "services": ["UC", "Vista"], "pads": "L M", "dssa": False, "own": False, "warn": [],
                               "age_s": 1000000}], "hidden": {"old": 6}, "pad": "L"},
    "/api/ggg": {"origin": "Start", "radius": 500.0, "searched": 40, "more": 0,
                 "bodies": [{"system": "Far Green", "id": "77", "body": "B 3", "chance": "likely", "distance": 30.04},
                            {"system": "Further", "id": "78", "body": "1", "chance": "possible", "distance": 120.0}]},
}
ARGS = {"body_detail": {"name": "Start A 1"}, "left_behind": {"radius_ly": 50}, "travel_history": {"days": 2},
        "materials": {"name": "polo"}, "nearby_systems": {"sort": "value"}}


def fake_get(calls=None, down=False):
    async def get(path, params):
        if calls is not None:
            calls.append((path, dict(params)))
        if down:
            raise tools.Unavailable("connection refused")
        return json.loads(json.dumps(FIX[path]))
    return get


def run(name, args=None, rows=25, **kw):
    return asyncio.run(tools.call(name, args if args is not None else ARGS.get(name, {}), fake_get(**kw), rows))


class Registry(unittest.TestCase):
    def test_listing(self):
        names = [t["name"] for t in tools.listing()]
        self.assertEqual(len(names), len(set(names)))
        for want in ("current_status", "this_system", "nearby_systems", "nearest_unvisited", "nearest_scoopable", "body_detail", "unsold_data",
                     "left_behind", "highway_route", "travel_history", "materials"):
            self.assertIn(want, names)
        for t in tools.listing():
            self.assertTrue(len(t["description"]) > 40, t["name"])
            self.assertEqual((t["inputSchema"]["type"], t["inputSchema"]["additionalProperties"]), ("object", False))
            self.assertTrue(set(t["inputSchema"]["required"]) <= set(t["inputSchema"]["properties"]))

    def test_every_tool_is_read_only(self):
        """A safety rule (PLAN-mcp addendum): a tool reads GET routes the server serves, never a POST route, never
        /api/find (which can store a system)."""
        calls = []
        for name in tools.TOOLS:
            out = asyncio.run(tools.call(name, ARGS.get(name, {}), fake_get(calls)))
            self.assertNotIn("error", out, name)
        self.assertTrue(calls)
        self.assertTrue(all(tools.allowed(p) for p, _ in calls))
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        app = ed_outrider.make_app(ed_outrider.State(db, ed_outrider.Journals(db), None, 25))
        gets, posts = set(), set()
        for r in app.router.routes():
            info = r.resource.get_info() if r.resource else {}
            path = info.get("path") or info.get("formatter") or ""
            (gets if r.method == "GET" else posts if r.method == "POST" else set()).add(path)
        for route in tools.READ_ROUTES:
            served = {g for g in gets if g == route or (route.endswith("/") and g.startswith(route))}
            self.assertTrue(served, f"{route} is not a GET route")
            self.assertFalse({p for p in posts if p == route.rstrip("/")}, f"{route} is also a POST route")
        for path in sorted(posts) + ["/api/find", "/api/export", "/api/say", "/api/system/1/x"]:
            self.assertFalse(tools.allowed(path), path)
        with self.assertRaises(tools.NotAllowed):
            asyncio.run(tools.guarded(fake_get())("/api/hush"))

    def test_answers(self):
        st = run("current_status")
        self.assertEqual((st["system"], st["fuel_jumps"], st["unsold"]), ("Start", 6, 1234567))
        self.assertEqual((st["near_body"], st["target_body"]), (None, None))   # S14: asked for, none in the fixture
        self.assertNotIn("commander", st)
        ts = run("this_system")
        self.assertEqual([b["name"] for b in ts["bodies"]], ["A 2", "A 1", "A"])   # most valuable first
        self.assertEqual(ts["to_do"]["worth_mapping"], [{"body": "A 2", "type": "High metal content world", "adds": 500000}])
        self.assertEqual((ts["to_do"]["bio_to_sample"], ts["bodies"][1]["bio_sampled"][0]["samples"]), (["A 1"], 2))
        near = run("nearby_systems")
        self.assertEqual([x["name"] for x in near["systems"]], ["Far Rich", "Near Seen", "Near New"])   # by value; not here, not route-only
        self.assertEqual([x["name"] for x in run("nearby_systems", {})["systems"]], ["Near Seen", "Near New", "Far Rich"])
        self.assertEqual([x["name"] for x in run("nearby_systems", {"unvisited_only": True})["systems"]], ["Near New", "Far Rich"])
        ns = run("nearest_scoopable")   # the review's #7: from you, the jump range said; not here
        self.assertEqual((ns["nearest"]["name"], ns["nearest"]["one_jump"], ns["jump_range_ly"], ns["next_ones"]), ("Far Rich", True, 72.5, []))
        nu = run("nearest_unvisited")
        self.assertEqual((nu["nearest"]["name"], nu["nearest"]["distance_ly"], nu["next_ones"][0]["name"]), ("Near New", 7.0, "Far Rich"))
        calls = []
        bd = asyncio.run(tools.call("body_detail", {"name": "Start A 1"}, fake_get(calls)))
        self.assertIn(("/api/body", {"system": SYS, "name": "A 1"}), calls)   # the system's name taken off
        self.assertEqual((bd["bio_predicted"][0]["likeliest"], bd["gravity_g"], bd["mining_odds"]["top"][0]["name"]),
                         ("Bacterium Volu", 0.12, "Platinum"))
        self.assertIn("error", run("body_detail", {"name": "A 1", "system_id64": "12; drop"}))
        # a name that matches no body: said, not an empty record (review 2026-10-11)
        empty = {"system": "Start", "full_name": "Start A 9", "row": None, "own": None, "spansh": None}

        async def no_body(path, params):
            return empty if path == "/api/body" else json.loads(json.dumps(FIX[path]))
        bd = asyncio.run(tools.call("body_detail", {"name": "A 9"}, no_body))
        self.assertIn("no body called 'A 9'", bd.get("error", ""))
        us = run("unsold_data")
        self.assertEqual(([x["name"] for x in us["unsold_firsts"]], us["lost_firsts_systems"], us["cartographic"]["estimated_payout"]),
                         (["Unsold Two", "Unsold One"], 1, 600))
        hw = run("highway_route", rows=3)
        self.assertEqual((hw["next"]["system"], hw["jumps_left"], hw["refuel_in_jumps"], len(hw["ahead"]), hw["more"]),
                         ("Neu", 42, 3, 3, 5))   # leads with the next system (Vespa's "next jump")
        th = run("travel_history")
        self.assertEqual((th["days"], th["sessions"][0]["systems"], th["sessions"][0]["ly"]), (2, ["Start", "Next One"], 120.0))
        gg = run("nearest_ggg", rows=1)   # S27
        self.assertEqual((gg["giants"], gg["more"], gg["radius_ly"]),
                         ([{"system": "Far Green", "body": "B 3", "distance_ly": 30.0, "chance": "likely"}], 1, 500.0))
        mt = run("materials")
        self.assertEqual(([r["name"] for r in mt["held"]], mt["synthesis"][0]["limited_by"]), (["Polonium"], "Polonium"))
        # S14: the recipes' group and grade (the voice picks the injections by them) and when the counts were read
        self.assertEqual((mt["synthesis"][0]["group"], mt["synthesis"][0]["grade"], mt["counts_from"]),
                         ("fsd", "premium", "2026-10-01T00:00:00Z"))
        self.assertEqual([r["name"] for r in run("materials", {})["held"]], ["Carbon", "Polonium"])   # held only, fullest first

    def test_left_behind_values(self):
        """S14: the tool passes on what each item could pay (bio up to, what a map adds) and adds each system's worth;
        it filters nothing (the voice does, at the server's thresholds)."""
        left = {"systems": [{"name": "Back", "distance": 4.04, "unfound": 0, "maps_total": 2,
                             "bio": [{"body": "B 1", "genera": ["Stratum"], "value": 19_000_000}, {"body": "B 2", "genera": None,
                                                                                                 "signals": 1, "value": 0}],
                             "maps": [{"body": "B 3", "subtype": "Water world", "terraformable": False, "increment": 700_000},
                                      {"body": "B 4", "subtype": "Icy body", "increment": 1_200}]}]}

        async def get(path, params):
            return left
        x = asyncio.run(tools.call("left_behind", {}, get))["systems"][0]
        self.assertEqual((x["bio"], x["map"][0], x["worth"], x["worth_mapping"], "bodies_not_found" in x),
                         ([{"body": "B 1", "up_to": 19_000_000}, {"body": "B 2", "up_to": 0}],
                          {"body": "B 3", "type": "Water world", "adds": 700_000}, 19_701_200, 2, False))

    def test_lists_are_capped_and_arguments_clamped(self):
        calls = []
        lb = asyncio.run(tools.call("left_behind", {"radius_ly": 9000}, fake_get(calls), rows=10))
        self.assertEqual((len(lb["systems"]), lb["more"], lb["radius_ly"]), (10, 20, 500))
        self.assertEqual(calls, [("/api/left", {"radius": "500"})])
        self.assertEqual(run("travel_history", {"days": "x"})["days"], 7)
        self.assertNotIn("more", run("left_behind", rows=30))

    def test_outrider_not_running(self):
        for name in tools.TOOLS:
            self.assertEqual(run(name, down=True), {"error": tools.NOT_RUNNING}, name)
        self.assertIn("error", run("no_such_tool"))
        self.assertIn("error", asyncio.run(tools.call("current_status", [1], fake_get())))


class Bridge(unittest.TestCase):
    def talk(self, lines, run_=None):
        out = io.StringIO()
        with contextlib.redirect_stderr(io.StringIO()):
            mcp.serve(io.StringIO("\n".join(lines) + "\n"), out, run_ or (lambda n, a: {"tool": n, "args": a}))
        return [json.loads(x) for x in out.getvalue().splitlines()]

    def test_protocol(self):
        msgs = [json.dumps(m) for m in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "materials", "arguments": {"name": "x"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}},
            {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 6, "method": "ping"},
            {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})] + ["{not json"]
        r = self.talk(msgs)
        self.assertEqual([x.get("id") for x in r], [1, 2, 3, 4, 5, 6, 7, None])   # the notification gets no answer
        self.assertEqual((r[0]["result"]["protocolVersion"], r[0]["result"]["serverInfo"]["name"], r[0]["result"]["capabilities"]["tools"]),
                         ("2025-03-26", "outrider", {"listChanged": False}))
        self.assertEqual({t["name"] for t in r[1]["result"]["tools"]}, set(tools.TOOLS))
        self.assertEqual(json.loads(r[2]["result"]["content"][0]["text"]), {"tool": "materials", "args": {"name": "x"}})
        self.assertFalse(r[2]["result"]["isError"])
        self.assertEqual((r[3]["error"]["code"], r[4]["error"]["code"], r[5]["result"], r[6]["result"]["protocolVersion"],
                          r[7]["error"]["code"]), (-32602, -32601, {}, mcp.PROTOCOLS[0], -32700))
        # an error answer is flagged, and one failing call does not end the session
        r = self.talk([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "materials"}}),
                       json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"})], run_=lambda n, a: 1 / 0)
        self.assertEqual((r[0]["error"]["code"], r[1]["result"]), (-32603, {}))
        r = self.talk([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "materials"}})],
                      run_=lambda n, a: {"error": tools.NOT_RUNNING})
        self.assertTrue(r[0]["result"]["isError"])

    def test_settings(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(mcp.mcp_settings({}), {"mcp_url": "", "mcp_rows": 25, "mcp_password": ""})
            self.assertEqual(mcp.mcp_settings({"mcp": {"url": "http://pc:9000/", "max_rows": 7, "password": "pw"}}),
                             {"mcp_url": "http://pc:9000", "mcp_rows": 7, "mcp_password": "pw"})
            self.assertEqual(mcp.mcp_settings({"mcp": {"url": "ftp://x", "max_rows": 0}}), {"mcp_url": "", "mcp_rows": 25, "mcp_password": ""})
        self.assertIn("[mcp] url", err.getvalue())
        self.assertIn("[mcp] max_rows", err.getvalue())
        self.assertEqual((mcp.default_url({}), mcp.default_url({"server": {"port": 8931}})), ("http://127.0.0.1:8025", "http://127.0.0.1:8931"))
        import argparse
        a = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({"mcp": {"url": "http://127.0.0.1:8931", "max_rows": 12}}, a, None, ([], []))
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["mcp"], {"url": "http://127.0.0.1:8931", "max_rows": 12, "password": ""})
        st = ed_outrider.settings_from({}, a, None, ([], []))
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["mcp"], {"max_rows": 25, "password": ""})

    def test_against_a_server_with_a_password(self):
        """The bridge talks to 127.0.0.1: it passes request_guard like curl, and [server] password never applies."""
        from aiohttp.test_utils import TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        state.password = "hunter2"

        async def go():
            async with TestServer(ed_outrider.make_app(state)) as srv:
                get = mcp.http_get(str(srv.make_url("")).rstrip("/"))
                ok = await tools.call("nearest_unvisited", {}, get)
                with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
                    try:   # the same from another device needs the password (status is open)
                        away = await get("/api/nearby", {})
                    except tools.Refused as e:
                        away = {"code": "signin_required", "why": str(e)}
                return ok, away
        ok, away = asyncio.run(go())
        self.assertNotIn("error", ok)
        self.assertIn("nearest", ok)
        self.assertEqual(away.get("code"), "signin_required")

    def test_a_server_elsewhere_with_a_password(self):
        """An Outrider on another computer (Docker): nothing is loopback, so the bridge signs in with [mcp] password
        and sends the session as a Bearer token; without one it says what to set."""
        from aiohttp.test_utils import TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        state.password = "hunter2"

        async def go():
            with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
                async with TestServer(ed_outrider.make_app(state)) as srv:
                    url = str(srv.make_url("")).rstrip("/")
                    good = await tools.call("nearest_unvisited", {}, mcp.http_get(url, password="hunter2"))
                    again = await tools.call("nearest_unvisited", {}, mcp.http_get(url, password="hunter2"))
                    none = await tools.call("nearest_unvisited", {}, mcp.http_get(url))
                    wrong = await tools.call("nearest_unvisited", {}, mcp.http_get(url, password="nope"))
                    return good, again, none, wrong
        good, again, none, wrong = asyncio.run(go())
        self.assertIn("nearest", good)
        self.assertIn("nearest", again)
        self.assertIn("[mcp] password", none["error"])
        self.assertIn("[mcp] password", wrong["error"])


if __name__ == "__main__":
    unittest.main()
