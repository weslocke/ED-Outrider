"""Questions by voice (tablet plan phase 6): POST /api/ask matches the fixed phrases (resources/ask.json), answers
from the read-only tools in-process, sends the answer to every window through the co-pilot channel, and only with
[assistant] enabled asks an OpenAI-compatible endpoint: here always a fake one on a free port, never a real provider."""
import asyncio
import contextlib
import io
import json
import os
import re
import tempfile
import time
import tomllib
import unittest
import unittest.mock

from support import ed_outrider
from test_mcp import fake_get   # the same fixture payloads as the MCP tools

import outrider.ask as ask  # noqa: E402
import outrider.auth  # noqa: E402
from outrider.core import ts_seconds  # noqa: E402


class Phrases(unittest.TestCase):
    def test_starter_phrases(self):
        ph = ask.load_phrases()
        self.assertEqual(set(ph), set(ask.COMMANDS))
        cases = {"Hey Vespa, status report.": "status_report", "vespa what's my fuel": "fuel", "How much am I carrying?": "unsold",
                 "next jump": "next_jump", "how many jumps left on the highway": "next_jump", "What's left here?": "whats_left",
                 "nearest unvisited system": "nearest_unvisited", "hush": "hush", "Vespa, be quiet!": "hush",
                 "any green gas giants near here": "nearest_ggg",
                 "unhush": "unhush", "voice back please": "unhush", "jumps left": "fuel",
                 "what's the weather like": None, "": None, "hushpuppies": None,
                 # S14, and the phrases around them still where they were
                 "Can I still make an FSD injection?": "fsd_injection", "how much jumponium have I got": "fsd_injection",
                 "how far have I gone today": "travel_today", "how far this session": "travel_today",
                 "how many jumps today": "travel_today", "how far can I go": "fuel",
                 "anything left behind nearby": "left_behind", "what's left behind": "left_behind",
                 "what's left here": "whats_left", "anything else in this system": "whats_left",
                 "status of this body": "this_body", "is this planet worth landing on": "this_body",
                 "tell me about the targeted body": "this_body", "status": "status_report",
                 # S32: a time in the hush, and the batches before (S54 traders, S27, D4) unchanged
                 "hush for ten minutes": "hush", "be quiet until the next jump": "hush", "stop talking": "hush",
                 "nearest raw trader": "nearest_dock", "nearest station with a shipyard": "nearest_dock",
                 "nearest green gas giant": "nearest_ggg"}
        for text, want in cases.items():
            self.assertEqual(ask.match(text, ph), want, text)

    def test_hush_mode(self):
        """S32: the hush a question asks for, only ever one of the server's three (set_hush reads any other as "jump"):
        a time it does not offer gets the nearest, and the answer names the three."""
        table = {"hush": "30m", "hush for ten minutes": "10m", "quiet for 10 min": "10m", "mute for 30 minutes": "30m",
                 "be quiet for half an hour": "30m", "hush for five minutes": "10m", "quiet for a quarter of an hour": "10m",
                 "hush for twenty five minutes": "30m", "shut up for an hour": "30m", "hush for 2 hours": "30m",
                 "hush until the next jump": "jump", "quiet until we leave": "jump", "hush until we arrive": "jump",
                 "silence till the next system": "jump", "hush for ten minutes or until I jump": "jump"}
        for text, want in table.items():
            self.assertEqual(ask.hush_mode(text), want, text)
        self.assertTrue(set(ask.HUSH_SAID) == set(ed_outrider.HUSH_MODES))   # the page's words for each mode the server has
        # ask.py's copy of page.js's HUSH_SAID: the same words, so the voice, a caption and Questions asked agree
        with open(os.path.join(os.path.dirname(ed_outrider.__file__), "static", "page.js"), encoding="utf-8") as f:
            obj = re.search(r"^const HUSH_SAID = (\{.*?\});", f.read(), re.M)[1]
        self.assertEqual(json.loads(re.sub(r"([{,]\s*)(\w+):", r'\1"\2":', obj)), ask.HUSH_SAID)
        self.assertEqual(ask.hush_words("hush for ten minutes"), ("10m", "Quiet for 10 minutes."))
        self.assertEqual(ask.hush_words("hush until the next jump"), ("jump", "Quiet until the next jump."))
        self.assertEqual(ask.hush_words("hush for five minutes"),
                         ("10m", "I can hush for 10 or 30 minutes, or until the next jump. Quiet for 10 minutes."))
        self.assertEqual(ask.hush_words("hush")[1], "Quiet for 30 minutes.")   # no time said: no list of choices

    def test_broken_phrase_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ask.json")
            with open(p, "w") as f:
                f.write("{not json")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                ph = ask.load_phrases(p)
        self.assertIn("ask.json", err.getvalue())
        self.assertEqual(ask.match("status report", ph), "status_report")

    def test_fixed_answers(self):
        go = lambda c: asyncio.run(ask.fixed_answer(c, fake_get()))   # noqa: E731
        self.assertEqual(go("fuel"), "Fuel at 41 percent, about 6 jumps at max range.")
        self.assertEqual(go("unsold"), "About 900 credits unsold: 600 cartographic and 300 exobiology.")
        self.assertEqual(go("next_jump"), "Next highway stop: Neu, 400 light years, a neutron star. 42 jumps left, refuel in 3.")
        self.assertEqual(go("nearest_unvisited"), "Nearest unvisited: Near New, 7.0 light years.")
        self.assertEqual(go("nearest_ggg"), "Nearest potential green gas giant: B 3 in Far Green, 30.0 light years. "
                                            "A guess from the ladder model: check it in the system map.")   # S27
        self.assertEqual(go("whats_left"), "Still to do here: find 1 more body in the FSS; biology on A 1; map A 2.")
        self.assertEqual(go("status_report"), "Start. Fuel 41 percent, 6 jumps. 1.2 million credits unsold. Highway: next Neu, 42 jumps left.")
        self.assertEqual(asyncio.run(ask.fixed_answer("fuel", fake_get(down=True))), "Outrider isn't running (start it, then ask again)")
        # one jump is "1 jump" (the tablet's Now header said "1 jumps", and so did these)
        async def one(name, args, get, rows):
            return {"current_status": {"system": "Sol", "fuel_pct": 9, "fuel_jumps": 1},
                    "highway_route": {"route": True, "next": {"system": "Neu", "distance_ly": 40}, "jumps_left": 1}}[name]
        with unittest.mock.patch.object(ask.tools, "call", one):
            self.assertEqual(go("fuel"), "Fuel at 9 percent, about 1 jump at max range.")
            self.assertEqual(go("status_report"), "Sol. Fuel 9 percent, 1 jump. Highway: next Neu, 1 jump left.")
            self.assertEqual(go("next_jump"), "Next highway stop: Neu, 40.0 light years. 1 jump left.")
        self.assertEqual([ask.words_cr(x) for x in (0, 950, 12_400, 1_000_000, 2_350_000_000)],
                         ["0", "950", "12 thousand", "1 million", "2.4 billion"])
        # at the unit boundaries (review 2026-10-20 L6: "1000 thousand", "1000 million")
        self.assertEqual([ask.words_cr(x) for x in (999_499, 999_999, 999_950_000)], ["999 thousand", "1 million", "1 billion"])

    def test_fsd_injection(self):
        """S14: the three injections picked by group and grade (never by a recipe's name: S15's learned recipes), the
        material that runs out first for one you can make at most twice, and stale counts said."""
        go = lambda get: asyncio.run(ask.fixed_answer("fsd_injection", get))   # noqa: E731
        self.assertEqual(go(fake_get()), "Premium injections: 2, short of polonium. Standard: 5. Basic: 31.")

        def with_materials(**change):
            async def get(path, params):
                d = await fake_get()(path, params)
                return dict(d, **change) if path == "/api/materials" else d
            return get
        renamed = [{"name": "Jump boost " + g, "group": "fsd", "grade": g, "craftable": n, "limit": "Arsenic"}
                   for g, n in (("basic", 4), ("standard", 0), ("premium", 1))] + \
                  [{"name": "FSD injection premium", "group": "other", "grade": None, "craftable": 99, "limit": None}]
        self.assertEqual(go(with_materials(synthesis=renamed)),
                         "Premium injections: 1, short of arsenic. Standard: none, short of arsenic. Basic: 4.")
        self.assertEqual(go(with_materials(stale=True)),
                         "Premium injections: 2, short of polonium. Standard: 5. Basic: 31. Counts from before this login.")
        self.assertIn("no materials reading", go(with_materials(snapshot_ts=None)))

    def test_travel_today(self):
        """S14: the sessions that ended since local midnight (a session that began before it counted whole); "this
        session" the latest one alone."""
        now = ts_seconds("2026-10-13T15:00:00Z")
        sessions = [{"start": "2026-10-13T12:00:00Z", "end": "2026-10-13T14:30:00Z", "jumps": 20, "ly": 900.4, "firsts": 3,
                     "mapped": 1, "samples": 0},
                    {"start": "2026-10-13T02:00:00Z", "end": "2026-10-13T05:00:00Z", "jumps": 1, "ly": 40.0, "firsts": 0,
                     "mapped": 0, "samples": 6},
                    {"start": "2026-10-12T20:00:00Z", "end": "2026-10-12T23:00:00Z", "jumps": 50, "ly": 3000.0}]

        async def get(path, params):
            self.assertEqual((path, params), ("/api/history", {"days": "2"}))
            return {"sessions": sessions, "all_time": {}}
        go = lambda text, t=now: asyncio.run(ask.travel_today(get, 10, text, now=t))   # noqa: E731
        with unittest.mock.patch.object(ask, "local_midnight", lambda now=None: "2026-10-13T04:00:00Z"):
            self.assertEqual(go("how far today"), "Today: 21 jumps, 940 light years, 3 first discoveries, 1 body mapped, 6 samples.")
            self.assertEqual(go("how far this session"), "This session: 20 jumps, 900 light years, 3 first discoveries, 1 body mapped.")
            self.assertEqual(go("this session", now + 3 * 3600), "Your last session: 20 jumps, 900 light years, 3 first discoveries, "
                                                                 "1 body mapped.")
            self.assertEqual(go("how far today", ts_seconds("2026-10-14T15:00:00Z")), "Today: 21 jumps, 940 light years, "
                                                                                       "3 first discoveries, 1 body mapped, 6 samples.")
        with unittest.mock.patch.object(ask, "local_midnight", lambda now=None: "2026-10-14T04:00:00Z"):
            self.assertEqual(go("how far today"), "No jumps yet today.")
        # local midnight on this computer's clock, as a UTC timestamp
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/New_York"
            time.tzset()
            self.assertEqual(ask.local_midnight(now), "2026-10-13T04:00:00Z")
            self.assertEqual(ask.local_midnight(ts_seconds("2026-10-13T03:00:00Z")), "2026-10-12T04:00:00Z")
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()

    def test_this_body(self):
        """S14: the body you are on, else the one you fly near, else the one targeted here; from body_detail."""
        def with_status(**change):
            async def get(path, params):
                d = await fake_get()(path, params)
                if path == "/api/body":
                    d["row"].update(value_now=30, value_if_mapped=40_000, geo=1, terraformable=True)
                return dict(d, **change) if path == "/api/status" else d
            return get
        go = lambda **c: asyncio.run(ask.fixed_answer("this_body", with_status(**c)))   # noqa: E731
        full = ("A 1, a rocky body, landable at 0.12 g, terraformable. Worth 30 credits now, 40 thousand if mapped. "
                "2 biological signals: likeliest Bacterium Volu, up to 19 million. 1 geological signal.")
        self.assertEqual(go(on_body="A 1", near_body="B 2", target_body="C 3"), full)
        self.assertEqual(go(near_body="A 1", target_body="C 3"), full)
        self.assertEqual(go(target_body="A 1"), "Targeted: " + full)
        self.assertEqual(go(), "You're not on or near a body, and no body is targeted.")

        async def unknown(path, params):
            if path == "/api/body":
                return {"system": "Start", "row": None}
            return dict(await fake_get()(path, params), target_body="Jameson Memorial")
        self.assertEqual(asyncio.run(ask.fixed_answer("this_body", unknown)), "Targeted: Jameson Memorial: nothing known about it yet.")

    def test_left_behind(self):
        """S14: the nearest one or two systems with work over the server's thresholds (body, bio), worth "up to"."""
        left = {"systems": [
            {"name": "Small Fry", "distance": 2.0, "unfound": 0, "bio": [{"body": "1", "value": 1_000_000}],
             "maps": [{"body": "2", "increment": 9_000}], "maps_total": 1},
            {"name": "Back There", "distance": 4.04, "unfound": 2, "bio": [{"body": "B 1", "value": 19_000_000}],
             "maps": [{"body": "B 3", "increment": 700_000}, {"body": "B 4", "increment": 1_200}], "maps_total": 2},
            {"name": "Lost Bodies", "distance": 9.5, "unfound": 1, "bio": [], "maps": [], "maps_total": 0},
            {"name": "Too Far Down", "distance": 12.0, "unfound": 3, "bio": [], "maps": [], "maps_total": 0}]}
        calls = []

        async def get(path, params):
            calls.append((path, params))
            return left
        go = lambda limits: asyncio.run(ask.fixed_answer("left_behind", get, limits=limits))   # noqa: E731
        self.assertEqual(go((500_000, 10_000_000)),
                         "Left behind nearby: Back There, 4.0 light years: 2 bodies not found; map B 3; biology on B 1, "
                         "worth up to 19.7 million. Then Lost Bodies, 9.5 light years: 1 body not found.")
        self.assertEqual(calls[0], ("/api/left", {"radius": "100"}))
        self.assertTrue(go(None).startswith("Left behind nearby: Small Fry, 2.0 light years: map 2; biology on 1, worth up to "
                                            "1 million. Then Back There"))
        left["systems"] = left["systems"][:1]
        self.assertEqual(go((500_000, 10_000_000)), "Nothing worth going back for within 100 light years.")

    def test_settings(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(ask.assistant_settings({}), ask.ASSISTANT)
            a = ask.assistant_settings({"assistant": {"enabled": True, "base_url": "http://localhost:11434/v1", "model": "qwen3",
                                                      "timeout": 30, "max_rounds": 2, "api_key": " k "}})
            bad = ask.assistant_settings({"assistant": {"enabled": "yes", "base_url": "ftp://x", "timeout": 999}})
        self.assertEqual((a["enabled"], a["model"], a["timeout"], a["max_rounds"], a["api_key"]), (True, "qwen3", 30.0, 2, "k"))
        self.assertEqual((bad["enabled"], bad["base_url"], bad["timeout"]), (False, "", 20.0))
        self.assertIn("[assistant] enabled", err.getvalue())
        import argparse
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({"assistant": {"enabled": True, "model": "m", "base_url": "http://h/v1"}}, args, None, ([], []))
        back = tomllib.loads(ed_outrider.config_text(st))["assistant"]
        self.assertEqual((back["enabled"], back["model"], back["base_url"], back["max_rounds"]), (True, "m", "http://h/v1", 4))


class Endpoint(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)

    def client(self, go):
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return await go(c)
        return asyncio.run(run())

    def test_contract(self):
        async def go(c):
            out = {}
            r = await c.post("/api/ask", json={"text": "Hey Vespa, nearest unvisited?", "source": "vespa"})
            out["fixed"] = (r.status, await r.json())
            out["copilot"] = dict(self.state.copilot)
            await c.get("/api/nearby?speaker=1")   # a window that speaks (S24)
            r = await c.post("/api/ask", json={"text": "what is the meaning of life"})
            out["none"] = await r.json()
            r = await c.post("/api/ask", json={"text": "hush"})
            out["hush"] = (await r.json(), self.state.hush and self.state.hush["mode"], self.state.copilot["action"], self.state.copilot["hush"])
            # S32: a hush for a set time
            timed = []
            for text in ("Vespa, hush for ten minutes", "be quiet until the next jump", "hush for five minutes"):
                r = await c.post("/api/ask", json={"text": text})
                h = dict(self.state.hush)
                timed.append(((await r.json())["answer"], h["mode"], h["until"] and round(h["until"] - time.time())))
            out["timed"] = timed
            await c.post("/api/ask", json={"text": "voice back"})
            out["unhush"] = self.state.hush
            out["bad"] = [(r.status, (await r.json())["code"]) for r in
                          [await c.post("/api/ask", json=b) for b in ({}, {"text": ""}, {"text": "x" * 501}, {"text": 5})]]
            r = await c.post("/api/ask", json={"text": "fuel"}, headers={"X-Outrider-App": "0.1.0"})
            out["old"] = (r.status, (await r.json())["code"])
            with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
                self.state.password = "pw"
                r = await c.post("/api/ask", json={"text": "fuel"})
                out["lan"] = (r.status, (await r.json())["code"])
                self.state.password = ""
            return out
        out = self.client(go)
        status, body = out["fixed"]
        self.assertEqual((status, set(body), body["matched"], body["command"], body["spoken"]),
                         (200, {"answer", "spoken", "matched", "command"}, "fixed", "nearest_unvisited", False))
        self.assertEqual((out["copilot"]["action"], out["copilot"]["words"]), ("say", body["answer"]))   # every window's caption
        self.assertEqual((out["none"]["matched"], out["none"]["command"], out["none"]["spoken"]), ("none", None, True))
        self.assertIn("status report", out["none"]["answer"])
        # said by the speaking window in place of its own news of the hush (the copilot's hush), not only captioned
        self.assertEqual((out["hush"][0]["command"], out["hush"][1], out["hush"][2], out["hush"][3]), ("hush", "30m", "say", "30m"))
        self.assertEqual(out["timed"], [("Quiet for 10 minutes.", "10m", 600), ("Quiet until the next jump.", "jump", None),
                                        ("I can hush for 10 or 30 minutes, or until the next jump. Quiet for 10 minutes.", "10m", 600)])
        self.assertIsNone(out["unhush"])
        self.assertEqual(out["bad"], [(400, "bad_request")] * 4)
        self.assertEqual((out["old"], out["lan"]), ((426, "app_too_old"), (401, "signin_required")))

    def test_questions_asked(self):
        """S35: every question goes into Settings' "Questions asked" (GET /api/ask/log, newest first): what was heard,
        where from, what it matched (the command, its label and the ask.json phrase), the answer, a hush's length;
        a question no phrase matched with the AI off; refusals (400, 426) with their code. In memory, the last 50."""
        async def go(c):
            seq0 = (await (await c.get("/api/nearby")).json())["ask_seq"]
            for body in ({"text": "Hey Vespa, status report", "source": "vespa"}, {"text": "hush for ten minutes"},
                         {"text": "how far have I gone today"}, {"text": "can I still make an FSD injection"},
                         {"text": "what is the meaning of life"}, {"text": ""}):
                await c.post("/api/ask", json=body)
            await c.post("/api/ask", json={"text": "fuel"}, headers={"X-Outrider-App": "0.1.0"})
            log = await (await c.get("/api/ask/log")).json()
            seq1 = (await (await c.get("/api/nearby")).json())["ask_seq"]
            return seq0, seq1, log
        seq0, seq1, log = self.client(go)
        q = log["questions"]
        self.assertEqual((seq0, seq1, log["seq"], log["max"], log["ai"], len(q)), (0, 7, 7, 50, "off", 7))
        self.assertEqual([x["seq"] for x in q], [7, 6, 5, 4, 3, 2, 1])   # newest first
        old, bad, none, fsd, today, hush, status = q
        self.assertEqual({k: status[k] for k in ("text", "source", "matched", "command", "label", "phrase", "code")},
                         {"text": "Hey Vespa, status report", "source": "vespa", "matched": "fixed", "command": "status_report",
                          "label": "a status report", "phrase": "status report", "code": None})
        self.assertTrue(status["answer"] and isinstance(status["ms"], int) and status["spoken"] is False and status["ts"] > 0)
        self.assertEqual((hush["command"], hush["hush"], hush["answer"]), ("hush", "10m", "Quiet for 10 minutes."))
        self.assertEqual((today["command"], today["label"], fsd["command"], fsd["label"]),
                         ("travel_today", "how far today", "fsd_injection", "FSD injections"))
        self.assertEqual((none["matched"], none["command"], none["phrase"], none["ai"]), ("none", None, None, None))
        self.assertIn("status report", none["answer"])
        self.assertEqual((bad["matched"], bad["code"], bad["text"]), ("error", "bad_request", ""))
        self.assertEqual((old["matched"], old["code"], old["text"], old["source"]), ("error", "app_too_old", "fuel", "app"))
        self.assertIn("too old", old["error"])
        # the last 50 only
        for i in range(60):
            self.state.ask_record(f"q{i}", "none")
        self.assertEqual((len(self.state.ask_log), self.state.ask_log[0]["text"]), (50, "q10"))
        self.assertFalse(ask.tools.allowed("/api/ask/log"))   # what was said is not one of the AI's tools

    def test_questions_asked_ai(self):
        """S35: the AI's answers and failures are kept with its rounds and the tools it ran; never the key."""
        call = {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "nearest_unvisited", "arguments": "{}"}}]}}]}
        done = {"choices": [{"message": {"content": "Nothing unvisited is known nearby."}}]}
        self.ai_run([call, done], text="tell me something interesting")
        self.ai_run([401], text="sing")
        self.ai_run([("sleep", 1.0)], text="sing slowly", timeout=0.2)
        timeout, refused, ok = list(self.state.ask_log)[::-1]
        self.assertEqual((ok["matched"], ok["answer"], ok["ai"]), ("ai", "Nothing unvisited is known nearby.",
                                                                   {"rounds": 2, "tools": ["nearest_unvisited"]}))
        self.assertEqual((refused["matched"], refused["code"], refused["error"], refused["ai"]),
                         ("error", "ai_error", "the AI provider refused the key (HTTP 401)", {"rounds": 1, "tools": []}))
        self.assertEqual((timeout["matched"], timeout["code"], timeout["text"]), ("error", "ai_timeout", "sing slowly"))
        self.assertNotIn("sk-test", json.dumps(list(self.state.ask_log)))
        self.assertEqual(self.state.ask_log_info()["ai"], "on")
        self.state.assistant = dict(ask.ASSISTANT, enabled=True)   # switched on, never set up
        self.assertEqual(self.client(lambda c: self._post(c, "sing")), (503, "ai_off"))
        self.assertEqual((self.state.ask_log[-1]["code"], self.state.ask_log_info()["ai"]), ("ai_off", "unset"))

    def test_this_body_from_the_status(self):
        """S14: /api/status says the body whose near-body zone you are in and the body targeted in this system (game
        facts, like on_body); the voice's "this body" reads them."""
        import types
        self.state.spansh = types.SimpleNamespace(cached=lambda i: (None, None))   # nothing known of the system
        self.state.journals.handle({"event": "FSDJump", "timestamp": "2026-10-13T10:00:00Z", "StarSystem": "Sys",
                                    "SystemAddress": 1, "StarPos": [0, 0, 0]})
        self.state.journals.status_json = {"live": True, "ts": "2026-10-13T10:05:00Z", "flags": ed_outrider.FLAG_IN_MAIN_SHIP,
                                           "flags2": 0, "body": "Sys 4", "lat": 1.0, "lon": 2.0, "alt": 48_000,
                                           "destination": {"System": 1, "Body": 7, "Name": "Sys 7 a"}}

        async def go(c):
            st = await (await c.get("/api/status")).json()
            r = await c.post("/api/ask", json={"text": "tell me about this planet"})
            self.state.journals.status_json.update(body=None, alt=None)
            st2 = await (await c.get("/api/status")).json()
            return st, await r.json(), st2
        st, said, st2 = self.client(go)
        self.assertEqual((st["on_body"], st["near_body"], st["target_body"]), (None, "4", "7 a"))
        self.assertEqual((said["command"], said["answer"]), ("this_body", "4: nothing known about it yet."))
        self.assertEqual((st2["near_body"], st2["target_body"]), (None, "7 a"))

    def test_speaker_seen_expires(self):
        self.state.speaker_seen = time.monotonic() - 61
        self.assertFalse(self.state.speaker_present())
        self.state.speaker_seen = time.monotonic()
        self.assertTrue(self.state.speaker_present())

    # ---- the AI layer, against a fake OpenAI-compatible server ----
    def fake_ai(self, script):
        """An aiohttp app answering POST /v1/chat/completions from `script` (one answer per request, the last repeats):
        a dict (the JSON), an int (that status), or ("sleep", s). Records each request's body and headers."""
        from aiohttp import web
        seen = []

        async def chat(request):
            seen.append((await request.json(), dict(request.headers)))
            item = script.pop(0) if len(script) > 1 else script[0]
            if isinstance(item, tuple):
                await asyncio.sleep(item[1])
                item = {"choices": [{"message": {"content": "late"}}]}
            if isinstance(item, int):
                return web.json_response({"error": "nope"}, status=item)
            return web.json_response(item)
        app = web.Application()
        app.router.add_post("/v1/chat/completions", chat)
        return app, seen

    def ai_run(self, script, text="how far is the nearest unvisited system", **cfg):
        from aiohttp.test_utils import TestClient, TestServer
        ai_app, seen = self.fake_ai(script)

        async def run():
            async with TestServer(ai_app) as ai:
                self.state.assistant = dict(ask.ASSISTANT, enabled=True, base_url=str(ai.make_url("/v1")), model="tiny",
                                            api_key="sk-test", **cfg)
                async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                    r = await c.post("/api/ask", json={"text": text})
                    return r.status, await r.json()
        status, body = asyncio.run(run())
        return status, body, seen

    def test_ai_tool_round_trip(self):
        call = {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "nearest_unvisited", "arguments": "{}"}}]}}]}
        done = {"choices": [{"message": {"content": "Nothing unvisited is known nearby."}}]}
        status, body, seen = self.ai_run([call, done], text="tell me something interesting")
        self.assertEqual((status, body["matched"], body["answer"], body["command"]), (200, "ai", "Nothing unvisited is known nearby.", None))
        first, second = seen[0][0], seen[1][0]
        self.assertEqual((first["model"], seen[0][1].get("Authorization")), ("tiny", "Bearer sk-test"))
        self.assertIn("nearest_unvisited", {t["function"]["name"] for t in first["tools"]})
        self.assertEqual(second["messages"][-1]["role"], "tool")
        self.assertIn("nearest", json.loads(second["messages"][-1]["content"]))   # the tool ran in-process
        self.assertEqual(self.state.copilot["words"], "Nothing unvisited is known nearby.")

    def test_ai_failures(self):
        self.assertEqual(self.ai_run([401], text="sing")[:2], (502, {"error": "the AI provider refused the key (HTTP 401)", "code": "ai_error"}))
        status, body, _ = self.ai_run([("sleep", 1.0)], text="sing", timeout=0.2)
        self.assertEqual((status, body["code"]), (504, "ai_timeout"))
        loop = {"choices": [{"message": {"tool_calls": [{"id": "x", "function": {"name": "current_status", "arguments": "{}"}}]}}]}
        ran, real = [], ask.tools.call

        async def counted(*a, **k):
            ran.append(a[0])
            return await real(*a, **k)
        with unittest.mock.patch.object(ask.tools, "call", counted):
            status, body, seen = self.ai_run([loop], text="sing", max_rounds=2)
        self.assertEqual((status, body["code"], len(seen)), (502, "ai_error", 3))
        # two rounds of tools, then a request for the answer only; a tool asked for then is not run (Codex F7)
        self.assertEqual((len(ran), "tool_choice" in seen[1][0], seen[2][0].get("tool_choice")), (2, False, "none"))
        self.assertEqual(self.ai_run([{"choices": [{"message": {"content": ""}}]}], text="sing")[1]["code"], "ai_error")
        # enabled but not set up: says so (503), and a fixed phrase never goes to the AI at all
        self.state.assistant = dict(ask.ASSISTANT, enabled=True)
        out = self.client(lambda c: self._post(c, "sing"))
        self.assertEqual(out, (503, "ai_off"))
        status, body, seen = self.ai_run([401], text="fuel")
        self.assertEqual((status, body["matched"], seen), (200, "fixed", []))

    def test_ai_malformed_replies(self):
        """R4: an AI provider's answer of an unexpected shape gives 502 ai_error (or, where the meaning is plain, an
        answer), never a 500 with a traceback."""
        msg = lambda m: {"choices": [{"message": m}]}   # noqa: E731
        call = lambda args: msg({"tool_calls": [{"id": "c1", "function": {"name": "current_status", "arguments": args}}]})   # noqa: E731
        done = msg({"content": "All quiet."})
        for script in ([{"choices": ["not a dict"]}], [{"choices": [{"message": "text"}]}], [msg({"tool_calls": "x"})],
                       [msg({"tool_calls": ["not a dict"]})], [msg({"content": 5})], [{"choices": {"0": 1}}], [["a list"]]):
            with contextlib.redirect_stderr(io.StringIO()):
                status, body, _ = self.ai_run(list(script), text="sing")
            self.assertEqual((status, body.get("code")), (502, "ai_error"), script)
        # plain meanings accepted: arguments already an object, content as a list of text parts
        status, body, seen = self.ai_run([call({}), done], text="sing")
        self.assertEqual((status, body["answer"]), (200, "All quiet."))
        self.assertEqual(seen[1][0]["messages"][-1]["role"], "tool")
        status, body, _ = self.ai_run([msg({"content": [{"type": "text", "text": "All"}, {"type": "text", "text": " quiet."}]})], text="sing")
        self.assertEqual((status, body["answer"]), (200, "All quiet."))

    def test_ai_backstop(self):
        """R4: anything else going wrong in the AI layer is ai_error with the exception's name, not a 500."""
        async def broken(*a, **k):
            raise KeyError("surprise")
        with unittest.mock.patch.object(ask, "ai_answer", broken), contextlib.redirect_stderr(io.StringIO()) as err:
            status, body, _ = self.ai_run([{}], text="sing")
        self.assertIn("surprise", err.getvalue())   # the traceback is in the log
        self.assertEqual((status, body["code"]), (502, "ai_error"))
        self.assertIn("KeyError", body["error"])

    async def _post(self, c, text):
        r = await c.post("/api/ask", json={"text": text})
        return r.status, (await r.json()).get("code")


if __name__ == "__main__":
    unittest.main()


class VoiceCommands(unittest.TestCase):
    """The list of voice commands (GET /api/ask/commands: Settings → Voice, the tablet's Voice commands…): every fixed
    command with what it does and the phrases that ask it, from resources/ask.json, and the words that narrow one."""

    def test_every_command_has_a_description(self):
        cmds, desc = ask.read_file()
        self.assertEqual(set(cmds), set(ask.COMMANDS))
        self.assertEqual(set(desc), set(ask.COMMANDS))
        for c, d in desc.items():
            self.assertTrue(d.strip() and d.endswith("."), c)

    def test_every_command_in_one_group(self):
        listed = [c for _, members in ask.GROUPS for c in members]
        self.assertEqual(sorted(listed), sorted(ask.COMMANDS))

    def test_the_list_is_the_file(self):
        cmds, desc = ask.read_file()
        groups = ask.command_list()
        rows = {r["command"]: r for g in groups for r in g["commands"]}
        self.assertEqual([g["name"] for g in groups], [name for name, _ in ask.GROUPS])
        self.assertEqual(set(rows), set(ask.COMMANDS))
        phrases = ask.load_phrases()
        for c, r in rows.items():
            self.assertEqual(r["description"], desc[c])
            self.assertEqual((r["title"], r["title"][:1].isupper()), (ask.title(c), True))
            # every phrase of the file, once as it is heard ("what's left" stands for "whats left" too)
            self.assertEqual(sorted({ask.norm(p) for p in r["phrases"]}), sorted(set(phrases[c])), c)
            self.assertEqual(len(r["phrases"]), len(set(phrases[c])), c)
            for p in r["phrases"]:   # and each one asks this command, not an earlier one: the list never misleads
                self.assertEqual(ask.match(p, phrases), c, p)
        self.assertIn("what's left", rows["whats_left"]["phrases"])
        self.assertNotIn("whats left", rows["whats_left"]["phrases"])
        # an edited file: a new phrase shows, a command with none left is not listed, no description is None
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ask.json")
            with open(path, "w") as f:
                json.dump({"commands": {"fuel": ["fuel", "gas tank"], "unsold": [], "hush": ["hush"]}}, f)
            got = {r["command"]: r for g in ask.command_list(ask.read_file(path)) for r in g["commands"]}
        self.assertEqual(set(got), {"fuel", "hush"})
        self.assertEqual((got["fuel"]["phrases"], got["fuel"]["description"]), (["fuel", "gas tank"], None))

    def test_narrowing_words(self):
        """The narrowing words listed are the ones the answers read: each service, kind and trader word makes
        nearest_query ask for what the list says, each hush example gives its mode, "session" the latest session."""
        rows = {r["command"]: r for g in ask.command_list() for r in g["commands"]}
        dockw = rows["nearest_dock"]["narrowing"]
        said = {w: n["means"] for n in dockw for w in n["words"]}
        for w, svc in list(ask.NEAREST_WORDS.items()) + [("uc", "UC")]:
            self.assertEqual(ask.nearest_query(f"nearest station with {w}")[0], [svc], w)
            self.assertIn(ask.SERVICE_NAMES.get(svc, svc), said[w])
        for w in ask.STATION_WORDS + ask.CARRIER_WORDS:
            self.assertEqual(ask.nearest_query(f"nearest {w}")[1], "station" if w in ask.STATION_WORDS else "carrier", w)
            self.assertIn(w, said)
        for w, kind in ask.TRADER_WORDS.items():
            self.assertEqual(ask.nearest_query(f"nearest {w} trader")[0], [kind], w)
            self.assertIn(kind.lower() + " material trader", said[w])
        self.assertEqual(said["data"], 'beside "trader": an encoded material trader')
        self.assertEqual(ask.nearest_query("nearest trader")[0], ["Trader"])
        hush = rows["hush"]["narrowing"]
        self.assertEqual([n["means"].split()[0] for n in hush], ["10", "30", "until"])
        for (mode, _, examples), n in zip(ask.HUSH_EXAMPLES, hush):
            self.assertEqual(n["words"], list(examples))
            for ex in examples:
                self.assertEqual(ask.hush_mode(f"hush {ex}"), mode, ex)
                self.assertEqual(ask.match(f"hush {ex}", ask.load_phrases()), "hush", ex)
        self.assertEqual(ask.hush_mode("hush"), "30m")   # no time said: what the 30 minutes row says
        self.assertEqual(rows["travel_today"]["narrowing"][0]["words"], ["session"])
        self.assertEqual(rows["fuel"]["narrowing"], [])

    def test_endpoint(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), None, 25)
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                r = await c.get("/api/ask/commands")
                out = (r.status, await r.json())
                state.assistant.update(enabled=True, base_url="http://127.0.0.1:9", model="m")
                return out, (await (await c.get("/api/ask/commands")).json())["ai"]
        (status, body), ai_on = asyncio.run(run())
        self.assertEqual((status, set(body), body["ai"], ai_on), (200, {"groups", "ai"}, "off", "on"))
        self.assertEqual(body["groups"], ask.command_list(state.ask_file))
        self.assertEqual(sum(len(g["commands"]) for g in body["groups"]), len(ask.COMMANDS))
        self.assertFalse(ask.tools.allowed("/api/ask/commands"))   # not one of the AI's tools: nothing it needs


class KnownQuestions(unittest.TestCase):
    def test_every_command_is_named(self):
        """What the voice says it knows lists every command it answers: "the nearest station" was left out
        (review 2026-10-11)."""
        import outrider.ask as ask
        self.assertEqual(set(ask.LABELS), set(ask.COMMANDS))
        said = ask.known_questions()
        for label in ask.LABELS.values():
            self.assertIn(label, said)
