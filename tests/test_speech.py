"""Unit tests: Spoken lines, voices, speakers and audio played on the PC.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import json
import os
import sys
import time
import unittest
import unittest.mock

from support import (  # also puts the repository root on sys.path
    scan, voice_honk, voice_jump, voice_moments, voice_organic, voice_planet, voice_sampling_body, user_docs,
)
import outrider.bio  # noqa: E402
import ed_outrider  # noqa: E402
import outrider.unsold  # noqa: E402
import outrider.speech  # noqa: E402
import outrider.chatter  # noqa: E402


class Speech(unittest.TestCase):
    """Spoken alerts: the lines file, and the game / arrival triggers."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def test_game_moments(self):
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T00:00:00Z", "Commander": "Briadin",
                       "ShipName": "Out There", "Ship": "krait_light", "GameMode": "Solo", "Credits": 5})
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T02:00:00Z"})
        kinds = [(m["kind"], m.get("cmdr"), m.get("ship")) for m in self.state.moments_summary()]
        self.assertEqual(kinds, [("game_start", "Briadin", "Out There"), ("game_exit", None, None)])
        self.assertTrue(any(b'"event":"Shutdown"' == w for w in ed_outrider.WANTED))

    def test_arrival_on_a_route(self):
        # targeted and announced as new, then the route re-targets the next hop before the arrival star scan:
        # the arrival must not play the fanfare again
        self.state.target_verdicts = {5: "unreported", 6: "partial"}
        self.state.last_target = {"id64": 99, "name": "next hop", "status": "partial"}
        self.jump("2026-01-01T00:05:00Z", 5, 10)
        self.j.handle(scan("2026-01-01T00:05:05Z", "S5", 5, 0, "S5", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        a = self.state.arrival
        self.assertEqual((a["undiscovered"], a["wrong"], a["sound"]), (True, False, None))
        # announced as known but nobody had been there: the surprise gets its fanfare on arrival
        self.jump("2026-01-01T00:06:00Z", 6, 20)
        self.j.handle(scan("2026-01-01T00:06:05Z", "S6", 6, 0, "S6", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        a = self.state.arrival
        self.assertEqual((a["undiscovered"], a["wrong"], a["sound"]), (True, True, "fanfare"))

    def test_fsd_charge_moment(self):
        # hyperspace jumps only (supercruise also writes StartJump), with the destination's star class
        self.j.handle({"event": "StartJump", "timestamp": "2026-01-01T00:00:00Z", "JumpType": "Supercruise"})
        self.j.handle({"event": "StartJump", "timestamp": "2026-01-01T00:00:10Z", "JumpType": "Hyperspace",
                       "StarSystem": "Drojau LL-O b26-3", "SystemAddress": 7, "StarClass": "K"})
        got = [(m["kind"], m.get("system"), m.get("star_class")) for m in self.state.moments_summary()]
        self.assertEqual(got, [("fsd_charge", "Drojau LL-O b26-3", "K")])

    def test_signals_moment(self):
        self.jump("2026-01-01T00:00:00Z", 9, 0)
        sig = lambda body, bio, geo: {"event": "FSSBodySignals", "timestamp": "2026-01-01T00:01:00Z", "BodyName": body,
                                      "BodyID": 3, "SystemAddress": 9, "Signals": [
                                          {"Type": ed_outrider.BIO, "Count": bio}, {"Type": ed_outrider.GEO, "Count": geo}]}
        self.j.handle(sig("S9 A 3", 2, 1))
        self.j.handle(sig("S9 B 1", 0, 0))   # nothing found: nothing to say
        got = [(m["kind"], m["body"], m["bio"], m["geo"]) for m in self.state.moments_summary() if m["kind"] == "signals"]
        self.assertEqual(got, [("signals", "A 3", 2, 1)])

    def test_autohonk(self):
        import asyncio, datetime as _dt
        now = lambda s=0: (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ")
        j = self.j

        class FakeHonker:
            ready, available, status, presses = True, True, "ready", []

            def __init__(self, game_answers):
                self.game_answers = game_answers

            def press(self, check=None, cancel=None):
                self.presses.append(j.jump_arrival["id64"])
                if self.game_answers:   # the game writes FSSDiscoveryScan (set directly: sqlite is per thread)
                    j.last_honk = {"id64": j.jump_arrival["id64"], "ts": now(), "bodies": 12,
                                   "progress": 1.0 if self.game_answers == "all" else 0.2}
                return True

        def arrive(id64, age=0, answers=True):
            FakeHonker.presses = []
            self.state.honker = FakeHonker(answers)
            self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
            self.state.honk_confirm = 0.3
            self.j.handle({"event": "FSDJump", "timestamp": now(age), "StarSystem": f"S{id64}", "SystemAddress": id64,
                           "StarPos": [id64, 0, 0]})

            async def go():
                self.state.maybe_honk()
                await asyncio.sleep(0.5)
            asyncio.run(go())
            honks = [m for m in self.state.moments_summary() if m["kind"] == "honk" and m["system"] == f"S{id64}"]
            self.last_honks = honks
            return FakeHonker.presses, [(m["ok"], bool(m["why"])) for m in honks]

        self.assertEqual(arrive(21), ([21], [(True, False)]))            # live arrival: pressed, confirmed
        self.assertEqual((self.last_honks[0]["bodies"], self.last_honks[0]["all_found"]), (12, False))
        self.assertEqual(arrive(25, answers="all"), ([25], [(True, False)]))   # the honk found everything
        self.assertTrue(self.last_honks[0]["all_found"])
        self.assertEqual(arrive(22, age=120), ([], []))                  # an old journal line: never pressed
        self.assertEqual(arrive(23, answers=False), ([23], [(False, True)]))   # no scan followed: says so
        self.j.handle({"event": "FSSDiscoveryScan", "timestamp": now(), "SystemName": "S24", "SystemAddress": 24,
                       "BodyCount": 3, "Progress": 1.0})
        self.assertEqual(arrive(24), ([], []))                           # honked here before: left alone

    def test_honk_decision(self):
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        live = lambda **kw: dict({"live": True, "ts": ts, "flags": 1 << 4 | 1 << 27, "gui_focus": 0}, **kw)
        t = now.timestamp()
        d = ed_outrider.honk_decision
        self.assertEqual(d(live(), t), ("press", None))
        self.assertEqual(d(live(gui_focus=6), t), ("wait", "the galaxy map is open"))
        self.assertEqual(d(live(gui_focus=9), t), ("wait", "the FSS is open"))
        self.assertEqual(d(live(flags=1 << 30), t), ("wait", "still in the jump"))
        self.assertEqual(d(live(gui_focus=6), t + 120), ("press", None))   # stale reading: behave as before
        # quit to the menu or the desktop (or closed) during the wait: never a key into another window (review 2026-10-11)
        self.assertEqual(d(dict(live(gui_focus=6), live=False), t), ("wait", "the game is not live"))
        self.assertEqual(d({"live": False, "ts": ts}, t + 120), ("wait", "the game is not live"))
        self.assertEqual(d(None, t), ("press", None))

    def test_autohonk_waits_for_cockpit(self):
        import asyncio, datetime as _dt
        now = lambda: _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        presses = []

        class FakeHonker:
            ready, available, status = True, True, "ready"

            def press(self, check=None, cancel=None):
                presses.append(time.time())
                return True
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.state.honk_confirm = 0.2
        self.j.status_json = {"live": True, "ts": now(), "flags": 1 << 4 | 1 << 27, "gui_focus": 6}   # galaxy map open
        self.j.handle({"event": "FSDJump", "timestamp": now(), "StarSystem": "S31", "SystemAddress": 31, "StarPos": [1, 0, 0]})

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.6)
            waiting = (list(presses), self.state.honker.status)
            self.j.status_json = dict(self.j.status_json, gui_focus=0)   # map closed
            await asyncio.sleep(0.8)
            return waiting
        waiting = asyncio.run(go())
        self.assertEqual(waiting, ([], "waiting: the galaxy map is open"))
        self.assertEqual(len(presses), 1)

    def test_autohonk_waits_while_the_game_is_at_its_menu_and_a_failed_press_resets_the_status(self):
        """Quit to the menu during the cockpit wait: nothing pressed (the key would reach another window); a press that
        raises leaves Settings saying ready, not "waiting: ..." (review 2026-10-11)."""
        import asyncio, datetime as _dt
        now = lambda: _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        presses = []

        class FakeHonker:
            ready, available, status, fail = True, True, "ready", False

            def press(self, check=None, cancel=None):
                if check and check():
                    raise outrider.honk.NotNow()
                presses.append(time.time())
                if self.fail:
                    raise OSError("uinput gone")
                return True
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0)
        self.state.honk_confirm = 0.2
        self.j.status_json = {"live": True, "ts": now(), "flags": 1 << 4 | 1 << 27, "gui_focus": 6}   # galaxy map open
        self.j.handle({"event": "FSDJump", "timestamp": now(), "StarSystem": "S41", "SystemAddress": 41, "StarPos": [1, 0, 0]})

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.5)
            self.j.status_json = {"live": False, "ts": now()}             # quit to the main menu
            await asyncio.sleep(0.8)
            return list(presses), self.state.honker.status
        self.assertEqual(asyncio.run(go()), ([], "waiting: the game is not live"))
        # a press that raises: the moment says why, and the status is ready again
        self.state.honker.fail, self.state.honker.status = True, "ready"   # (the first run was cancelled mid-wait)
        self.j.status_json = {"live": True, "ts": now(), "flags": 1 << 4 | 1 << 27, "gui_focus": 6}
        self.j.handle({"event": "FSDJump", "timestamp": now(), "StarSystem": "S42", "SystemAddress": 42, "StarPos": [2, 0, 0]})

        async def again():
            self.state.maybe_honk()
            await asyncio.sleep(0.5)
            self.j.status_json = dict(self.j.status_json, gui_focus=0)   # map closed: the press goes and fails
            await asyncio.sleep(0.8)
        asyncio.run(again())
        self.assertEqual((len(presses), self.state.honker.status), (1, "ready"))

    def test_arrival_without_target(self):
        self.jump("2026-01-01T00:01:00Z", 2, 30)
        self.j.handle(scan("2026-01-01T00:01:05Z", "S2", 2, 0, "S2", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        a = self.state.arrival
        self.assertEqual((a["name"], a["undiscovered"], a["first_visit"], a["wrong"], a["sound"]),
                         ("S2", True, True, False, None))   # never announced: voice only, no fanfare
        # back again before selling: still undiscovered in the journal, but no longer news
        self.jump("2026-01-01T00:02:00Z", 3, 60)
        self.jump("2026-01-01T00:03:00Z", 2, 30)
        self.j.handle(scan("2026-01-01T00:03:05Z", "S2", 2, 0, "S2", disc=False, star=True)[2])
        self.state.reconcile_arrival()
        a = self.state.arrival
        self.assertEqual((a["undiscovered"], a["first_visit"], a["sound"]), (True, False, None))

    def test_lines_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "speech.json")
            sl = outrider.speech.SpeechLines(path)
            self.assertIsNone(sl.info()["version"])
            doc = {"styles": {"business": "Business"}, "lines": {"hull": {"business": ["Hull {pct} percent."]}}}
            with open(path, "w") as f:
                json.dump(doc, f)
            self.assertTrue(sl.info()["version"])
            self.assertEqual(sl.lines()["lines"]["hull"]["business"], ["Hull {pct} percent."])
            with open(path, "w") as f:
                f.write("{ broken")
            os.utime(path, ns=(1, 1))   # a new modification time, whatever the clock's resolution
            info = sl.info()
            self.assertIn("last good copy", info["error"])
            self.assertEqual(sl.lines()["lines"]["hull"]["business"], ["Hull {pct} percent."])
        bad = {"styles": {"business": 1}, "lines": {"hull": {"business": ["{body} is hot"], "pirate": ["arr"]}, "nope": {}}}
        probs = " ".join(outrider.speech.check(bad))
        self.assertIn("{body}", probs)
        self.assertIn('"pirate"', probs)
        self.assertIn("does not know yet: nope.", probs)
        # several unknown alerts (a lines file newer than the running Outrider): one short line, not the whole list each
        probs = outrider.speech.check({"styles": {"business": "B"}, "lines": {"nope": {}, "never": {}, "hull": {"business": ["Hull."]}}})
        self.assertEqual(probs, ["2 lines are for alerts this Outrider does not know yet: nope, never. Restart Outrider after an "
                                 "update; otherwise check the names (the voice lab lists every alert)."])

    def test_fill_and_spoken_text(self):
        import random
        rng = random.Random(3)
        got = {outrider.speech.fill("{name}", {}, "Boss, Hefay, Sir", rng) for _ in range(60)}
        self.assertEqual(got, {"Boss", "Hefay", "Sir"})   # each {name} is its own random pick
        self.assertEqual(outrider.speech.fill("{name}, hull {pct}. {missing}", {"pct": 40}, " , "), "Commander, hull 40. ")
        self.assertEqual(outrider.speech.spoken_text("⚠ Sold 12.6M cr · 3k left <b>now</b>"),
                         "Sold 12.6 million credits, 3 thousand left now")
        self.assertEqual(outrider.speech.spoken_text("52.0M unsold, 12.64B banked, 1.96M left, 0.04M, 7.25 ly, 1.4M to map"),
                         "52 million unsold, 12.6 billion banked, 2 million left, 0 million, 7.2 ly, 1.4 million to map")
        for key in outrider.speech.KEYS:   # the voice lab's sample values fill every placeholder an alert has (the crew's: names)
            self.assertLessEqual(outrider.speech.fills(key) - set(outrider.speech.ALWAYS),
                                 set(outrider.speech.SAMPLES.get(key, {})) | set(outrider.speech.CREW_SAMPLES), key)

    def test_shipped_lines(self):
        # speech.json covers every alert in every personality, and the page asks for exactly those alerts
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "resources", "speech.json"), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(outrider.speech.check(doc), [])
        # space chatter's keys (#15) only once its lines are written (outrider.chatter.LINES_WRITTEN)
        required = [k for k in outrider.speech.KEYS if outrider.chatter.LINES_WRITTEN or k not in outrider.speech.CHATTER_KEYS]
        self.assertEqual(outrider.speech.spoken_keys(), required)
        for key in required:
            for style in list(doc["styles"]) + [s + "_profane" for s in ("sarcastic", "sweet")]:
                self.assertGreaterEqual(len(doc["lines"].get(key, {}).get(style, [])), 10, f"{key}/{style}")
        # every shipped personality file (resources/personalities/) is clean and covers every alert as the base ones do,
        # its swearing list too when it has one; none takes a base personality's name
        folder = os.path.join(here, "resources", "personalities")
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                pdoc = json.load(f)
            self.assertEqual(outrider.speech.check(pdoc), [], name)
            for sid in pdoc["styles"]:
                self.assertNotIn(sid, doc["styles"], name)
                swears = any(sid + "_profane" in e for e in pdoc["lines"].values())
                for key in required:
                    for lst in [sid] + ([sid + "_profane"] if swears else []):
                        self.assertGreaterEqual(len(pdoc["lines"].get(key, {}).get(lst, [])), 10, f"{name}: {key}/{lst}")
            # and Settings shows it complete: no "(60/100 alerts)" for the chatter not written yet (sweep 2026-10-16)
            _, notes, info = outrider.speech.merge_personalities(doc, [("shipped", name, pdoc)])
            self.assertEqual((notes, [i["covers"] == i["of"] == len(required) for i in info]), ([], [True] * len(pdoc["styles"])), name)
            doc["lines"] = {k: {**v, **pdoc["lines"].get(k, {})} for k, v in doc["lines"].items()}   # for the checks below
        # the voice calls you by your chosen names ({name}): commander names are often unpronounceable
        said = [x for e in doc["lines"].values() for k, v in e.items() if k != "when" for x in v]
        self.assertEqual([x for x in said if "{cmdr}" in x], [])
        with open(os.path.join(here, "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        import re
        used = set(re.findall(r'line\("(\w+)"', js)) | set(re.findall(r'"(unsold_\w+)"', js))
        # every key is spoken by the page (RESERVED would list any with lines written ahead of their trigger); the
        # chatter's by their names (the monologues, the last word) and the topics' asks and answers from the server's list
        chatter = set(outrider.speech.CHATTER_KEYS)
        for key in ("chatter_space", "chatter_planet_orbit", "chatter_planet_landed", "chatter_react"):
            self.assertIn(f'"{key}"', js, key)
        self.assertIn("`chat_${topic}_ask`", js)
        self.assertIn("`chat_${topic}_answer`", js)
        self.assertEqual(used - chatter, set(outrider.speech.KEYS) - chatter - set(outrider.speech.RESERVED))
        self.assertLessEqual(set(outrider.speech.RESERVED), set(outrider.speech.KEYS))
        samples = js[js.index("const LINE_SAMPLES = {"):]
        samples = samples[:samples.index("\n};")]
        for key in set(outrider.speech.KEYS) - chatter:   # the ▶ try button has sample values for every alert
            self.assertRegex(samples, r"\b%s: \{" % key, key)   # (the chatter's come with the lines: speechLib.chatter)


class PersonalityFiles(unittest.TestCase):
    """Drop-in personalities (the author, 2026-10-16): one file each, in speech.json's format, from
    resources/personalities/ (shipped) and personalities/ beside the bans (yours), merged into the base lines."""

    BASE = {"styles": {"business": "Business"},
            "lines": {"hull": {"when": "hull below 50%", "business": ["Hull {pct} percent."]},
                      "heat": {"business": ["Heat {pct} percent."]}}}

    @staticmethod
    def naval(**over):
        doc = {"styles": {"naval": {"label": "Naval", "names": ["Captain", "Sir"]}},
               "lines": {"hull": {"naval": ["Hull integrity {pct} percent, {name}."], "naval_profane": ["Hull's at {pct}, damn it."]}}}
        doc.update(over)
        return doc

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        self.base = os.path.join(d, "speech.json")
        self.write(self.base, self.BASE)
        self.shipped, self.yours = os.path.join(d, "shipped"), os.path.join(d, "personalities")
        os.makedirs(self.shipped)
        self.sl = outrider.speech.SpeechLines(self.base, dirs=(self.shipped, self.yours))

    @staticmethod
    def write(path, doc):
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        os.utime(path, ns=(time.time_ns(), time.time_ns()))

    def test_merged(self):
        """A personality file joins styles and each alert it has; the base keeps its own; its coverage is counted."""
        merged, notes, info = outrider.speech.merge_personalities(self.BASE, [("shipped", "naval.json", self.naval())])
        self.assertEqual(list(merged["styles"]), ["business", "naval"])
        self.assertEqual(sorted(merged["lines"]["hull"]), ["business", "naval", "naval_profane", "when"])
        self.assertEqual(merged["lines"]["heat"], {"business": ["Heat {pct} percent."]})
        self.assertEqual((notes, info), ([], [{"id": "naval", "file": "naval.json", "source": "shipped", "covers": 1,
                                               "of": len(outrider.speech.spoken_keys())}]))
        self.assertNotIn("naval", self.BASE["styles"])   # the base document is left as it was
        self.assertEqual(sorted(self.BASE["lines"]["hull"]), ["business", "when"])

    def test_who_wins(self):
        """Yours replaces a shipped one of the same name; a base personality is never replaced; a name taken twice in
        one folder is taken once; lists for other personalities or unknown alerts are left out."""
        mine = self.naval(lines={"hull": {"naval": ["Mine, {name}."]}})
        merged, notes, info = outrider.speech.merge_personalities(self.BASE, [
            ("shipped", "naval.json", self.naval()), ("shipped", "naval2.json", self.naval()),
            ("shipped", "bad.json", {"styles": {"business": "Mine"}, "lines": {"hull": {"business": ["Hijacked."]}}}),
            ("yours", "naval.json", mine),
            ("yours", "odd.json", {"styles": {"odd": "Odd"}, "lines": {"hull": {"odd": ["Odd."], "naval": ["Sneaky."]},
                                                                       "nope": {"odd": ["Not an alert."]}}})])
        self.assertEqual(merged["lines"]["hull"]["naval"], ["Mine, {name}."])
        self.assertNotIn("naval_profane", merged["lines"]["hull"])                 # yours replaces the shipped one whole
        self.assertEqual(merged["lines"]["hull"]["business"], ["Hull {pct} percent."])
        self.assertEqual(merged["styles"]["business"], "Business")
        self.assertEqual(merged["lines"]["hull"]["odd"], ["Odd."])
        self.assertNotIn("nope", merged["lines"])
        self.assertEqual(notes, ['naval2.json: "naval" is already in naval.json: left out',
                                 'bad.json: "business" is one of the base personalities: left out'])
        self.assertEqual([(i["id"], i["file"], i["source"]) for i in info], [("naval", "naval.json", "yours"), ("odd", "odd.json", "yours")])

    def test_files_read_and_reread(self):
        """Picked up when added, edited or removed (the version moves); a broken edit keeps its last good copy; a file
        that is not a personality file is left out, said; bans work on its lines."""
        v0 = self.sl.version()
        self.assertEqual(self.sl.lines()["personalities"], [])
        self.write(os.path.join(self.shipped, "naval.json"), self.naval())
        lines = self.sl.lines()
        self.assertNotEqual(lines["version"], v0)
        self.assertEqual(lines["lines"]["hull"]["naval"], ["Hull integrity {pct} percent, {name}."])
        self.assertEqual(lines["styles"]["naval"]["names"], ["Captain", "Sir"])
        self.assertEqual(lines["personalities"][0]["covers"], 1)
        os.makedirs(self.yours)
        self.write(os.path.join(self.yours, "naval.json"), "{ broken")
        info = self.sl.info()
        self.assertTrue(any("naval.json could not be read" in p and "left out" in p for p in info["problems"]), info)
        self.assertEqual(self.sl.lines()["lines"]["hull"]["naval"], ["Hull integrity {pct} percent, {name}."])   # the shipped one
        self.write(os.path.join(self.shipped, "naval.json"), "{ broken too")
        self.assertTrue(any("last good copy" in p for p in self.sl.info()["problems"]))
        self.assertIn("naval", self.sl.lines()["styles"])
        self.write(os.path.join(self.shipped, "naval.json"), self.naval(lines={"hull": {"naval": ["One.", "Two."]}}))
        self.assertEqual(self.sl.lines()["lines"]["hull"]["naval"], ["One.", "Two."])
        self.assertEqual(self.sl.set_ban("hull", "One.")[0], 200)                    # a ban on a personality file's line
        self.assertEqual(self.sl.lines()["lines"]["hull"]["naval"], ["Two."])
        self.write(os.path.join(self.yours, "list.json"), "[1, 2]")
        self.assertTrue(any("list.json: not a personality file" in p for p in self.sl.info()["problems"]))
        os.remove(os.path.join(self.shipped, "naval.json")); os.remove(os.path.join(self.yours, "naval.json"))
        self.assertNotIn("naval", self.sl.lines()["styles"])

    def test_the_naval_sample(self):
        """tests/fixtures/personalities/naval-sample.json (four alerts, for trying the format): a clean personality file
        that merges, says "Captain" or "Sir", and swears in its own list only."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "personalities", "naval-sample.json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(outrider.speech.check(doc), [])
        self.assertEqual(outrider.speech.style_names(doc["styles"]["naval"]), ["Captain", "Sir"])
        with open(os.path.join(outrider.RESOURCES_DIR, "speech.json"), encoding="utf-8") as f:
            base = json.load(f)
        merged, notes, info = outrider.speech.merge_personalities(base, [("yours", "naval-sample.json", doc)])
        self.assertEqual((notes, info[0]["covers"]), ([], 4))
        self.assertTrue(all(len(merged["lines"][k]["naval"]) == 5 and len(merged["lines"][k]["naval_profane"]) == 5
                            for k in ("game_start", "arrival_undiscovered", "hull", "fuel_low")))

    def test_names(self):
        """A personality's "names": a list of words, checked; style_names reads them (none for a plain label)."""
        sn = outrider.speech.style_names
        self.assertEqual([sn({"names": ["Captain", " Sir "]}), sn("Naval"), sn({"label": "x"}), sn({"names": []}),
                          sn({"names": ["Captain", 5]}), sn({"names": "Captain"})], [["Captain", "Sir"], None, None, None, None, None])
        self.assertEqual(outrider.speech.check(self.naval()), [])
        probs = outrider.speech.check(self.naval(styles={"naval": {"label": "Naval", "names": "Captain"}}))
        self.assertTrue(any('"names" must be a list' in p for p in probs), probs)

    def test_the_folders(self):
        """Shipped: resources/personalities/; yours: personalities/ where the bans go (data/ for the shipped file)."""
        shipped, yours = outrider.speech.personality_dirs(os.path.join(outrider.RESOURCES_DIR, "speech.json"))
        self.assertEqual((shipped, yours), (os.path.join(outrider.RESOURCES_DIR, "personalities"),
                                            os.path.join(outrider.DATA_DIR, "personalities")))
        self.assertEqual(outrider.speech.personality_dirs(self.base)[1], self.yours)
        with open(os.path.join(os.path.dirname(outrider.RESOURCES_DIR), ".gitignore"), encoding="utf-8") as f:
            self.assertIn("data/", f.read())   # yours are never in the repository

    def test_served_gzipped(self):
        """GET /api/speech gzipped when the browser takes it (1 MB and more; about a fifth gzipped)."""
        import asyncio
        import types
        from aiohttp.test_utils import TestClient, TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        state.speech = self.sl

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                r = await c.get("/api/speech", headers={"Accept-Encoding": "gzip"})
                return r.status, r.headers.get("Content-Encoding"), (await r.json())["lines"]["hull"]["business"]
        self.assertEqual(asyncio.run(go()), (200, "gzip", ["Hull {pct} percent."]))


class Batch6Voice(unittest.TestCase):
    """Batch 6 part 2: the FSS debrief, leaving a body, species complete, flight call-outs, the approach and
    arrival briefings, and the session recap (server-side triggers and the facts they carry)."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.jump("2026-01-01T00:00:00Z", 1, 0)

    jump = voice_jump

    honk = voice_honk

    planet = voice_planet

    moments = voice_moments

    def test_events_wanted(self):
        for e in ("ApproachBody", "LeaveBody", "Touchdown"):
            self.assertIn(f'"event":"{e}"'.encode(), ed_outrider.WANTED)
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 25)

    def test_fss_done(self):   # P1: after a manual FSS, with the leaving summary; not after a honk that found everything
        self.honk("2026-01-01T00:00:10Z", 1, 3)
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", PlanetClass="Water world", TerraformState="Terraformable", MassEM=0.5)
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:02:00Z", "SystemName": "S1", "SystemAddress": 1, "Count": 3})
        done = self.moments("fss_done")
        self.assertEqual(len(done), 1)
        self.assertEqual((done[0]["count"], done[0]["system_name"], done[0]["leaving"]["all_found"]), (3, "S1", True))
        self.assertEqual(done[0]["leaving"]["unmapped"][0]["body"], "A 4")
        self.jump("2026-01-01T00:10:00Z", 2, 10)
        self.honk("2026-01-01T00:10:10Z", 2, 1, progress=1.0)
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:10:10Z", "SystemName": "S2", "SystemAddress": 2, "Count": 1})
        self.jump("2026-01-01T00:20:00Z", 3, 20)
        self.honk("2026-01-01T00:20:10Z", 3, 2, progress=0.5)
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:20:12Z", "SystemName": "S3", "SystemAddress": 3, "Count": 2})
        self.assertEqual([m["system"] for m in self.moments("fss_done")], ["1"])   # the honk said it: no debrief

    def test_fss_closed_unfinished(self):   # P1: GuiFocus 9 -> 0 with bodies hidden, judged 2 s later, once per visit
        live = lambda focus: {"live": True, "ts": "2026-01-01T00:05:00Z", "flags": 0, "gui_focus": focus}
        self.honk("2026-01-01T00:00:10Z", 1, 5)
        self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4")
        self.db.commit()
        for t, focus in ((0, 9), (1, 0), (2, 0)):
            self.j.status_json = live(focus)
            self.state.watch_fss(1000 + t)
        self.assertEqual(self.moments("fss_unfinished"), [])          # not yet: the journal may still be catching up
        self.state.watch_fss(1003.5)
        got = self.moments("fss_unfinished")
        self.assertEqual([(m["left"], m["system_name"]) for m in got], [(4, "S1")])
        for t, focus in ((10, 9), (11, 0), (20, 0)):                  # closed again on the same visit: said once
            self.j.status_json = live(focus)
            self.state.watch_fss(1000 + t)
        self.assertEqual(len(self.moments("fss_unfinished")), 1)
        # all found, or a system never honked: nothing to say
        self.jump("2026-01-01T00:10:00Z", 2, 10)
        self.db.commit()
        for t, focus in ((30, 9), (31, 0), (40, 0)):
            self.j.status_json = live(focus)
            self.state.watch_fss(1000 + t)
        self.honk("2026-01-01T00:10:10Z", 2, 5)
        self.j.handle({"event": "FSSAllBodiesFound", "timestamp": "2026-01-01T00:11:00Z", "SystemName": "S2", "SystemAddress": 2, "Count": 5})
        self.db.commit()
        for t, focus in ((50, 9), (51, 0), (60, 0)):
            self.j.status_json = live(focus)
            self.state.watch_fss(1000 + t)
        self.assertEqual(len(self.moments("fss_unfinished")), 1)
        # not live (the game at the menu): no edge
        self.j.status_json = dict(live(9), live=False)
        self.state.watch_fss(2000)
        self.assertIsNone(self.state._fss_closed)

    sampling_body = voice_sampling_body

    organic = voice_organic

    def test_left_body_and_species_complete(self):   # P4: LeaveBody (not Liftoff); untouched genera only once you landed
        self.sampling_body()
        self.j.handle({"event": "Liftoff", "timestamp": "2026-01-01T00:02:30Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        self.j.handle({"event": "LeaveBody", "timestamp": "2026-01-01T00:03:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        first = self.moments("left_body")
        self.assertEqual(len(first), 1)                                  # Liftoff says nothing
        self.assertEqual((first[0]["body"], first[0]["touched"], first[0]["partial"]), ("A 4", False, {}))
        self.assertEqual(sorted(u["genus"] for u in first[0]["untouched"]), ["Bacterium", "Stratum"])
        self.organic("2026-01-01T00:04:00Z", "Log")
        self.organic("2026-01-01T00:05:00Z", "Sample")
        self.j.handle({"event": "LeaveBody", "timestamp": "2026-01-01T00:06:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        second = self.moments("left_body")[-1]
        self.assertEqual((second["touched"], second["partial"], second["factor"]), (True, {"Stratum": 2}, 5))
        self.assertEqual([u["genus"] for u in second["untouched"]], ["Bacterium"])
        self.organic("2026-01-01T00:07:00Z", "Analyse")
        done = self.moments("bio_done")
        self.assertEqual(len(done), 1)
        self.assertEqual((done[0]["species"], done[0]["body"], done[0]["partial"]), ("Stratum Tectonicas", "A 4", {}))
        self.assertEqual([u["genus"] for u in done[0]["untouched"]], ["Bacterium"])
        self.assertEqual(done[0]["value"], outrider.bio.species_value("Stratum Tectonicas") * 5)   # first footfall x5
        self.j.handle({"event": "Touchdown", "timestamp": "2026-01-01T00:08:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4,
                       "PlayerControlled": True, "OnPlanet": True})
        self.assertIn((1, 4), self.j.body_touched)

    def test_approach_once_per_body_per_session(self):   # P13: ApproachBody only, once per body until the next login
        self.sampling_body()
        for ts in ("2026-01-01T00:03:00Z", "2026-01-01T00:04:00Z"):
            self.j.handle({"event": "ApproachBody", "timestamp": ts, "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        got = self.moments("approach")
        self.assertEqual(len(got), 1)
        a = got[0]
        self.assertEqual((a["body"], a["gravity"], a["landable"], a["signals"], a["factor"]), ("A 4", 2.6, True, 2, 5))
        self.assertEqual(a["genera"], ["Bacterium", "Stratum"])
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X"})
        self.j.handle({"event": "ApproachBody", "timestamp": "2026-01-01T01:05:00Z", "SystemAddress": 1, "Body": "S1 A 4", "BodyID": 4})
        self.assertEqual(len(self.moments("approach")), 2)

    def test_scoop_watch(self):   # P8: debounced end of a scoop; a jump cutting it short says nothing
        W = ed_outrider.ScoopWatch
        S = ed_outrider.FLAG_SCOOPING

        def run(steps, cap=32.0, jump_ts=None):
            w, out = W(), []
            for t, flags, fuel in steps:
                r = w.update({"live": True, "flags": flags, "fuel_main": fuel}, cap, 1000 + t, jump_ts)
                if r:
                    out.append((t, r))
            return out
        scoop = [(t, S, 10 + t) for t in range(0, 20)]
        self.assertEqual(run(scoop + [(20, 0, 32), (21, 0, 32), (23, 0, 32)]), [(23, {"pct": 100, "full": True})])
        self.assertEqual(run(scoop + [(20, 0, 20), (23, 0, 20)]), [(23, {"pct": 62, "full": False})])   # stopped early
        flicker = scoop[:10] + [(10, 0, 20), (11, S, 21)] + scoop[12:] + [(20, 0, 32), (23, 0, 32)]
        self.assertEqual(len(run(flicker)), 1)                                       # the edge of the zone: one scoop
        self.assertEqual(run([(0, S, 10), (3, S, 11), (4, 0, 11), (8, 0, 11)]), [])  # skimmed for 4 s: nothing
        charging = scoop + [(20, ed_outrider.FLAG_FSD_CHARGING, 20), (23, 0, 20)]
        self.assertEqual(run(charging), [])                                          # left early on purpose
        self.assertEqual(run(scoop + [(20, 0, 20), (23, 0, 20)], jump_ts=ed_outrider.iso_ts(1019)), [])
        self.assertEqual(len(run(scoop + [(20, ed_outrider.FLAG_FSD_CHARGING, 32), (23, 0, 32)])), 1)   # full is still full
        self.assertEqual(run(scoop + [(20, 0, 32), (23, 0, 32)], cap=None), [])      # capacity unknown: silent
        # through the state: a moment with the jumps a full tank gives
        self.j.ship = {"fuel_main": 32.0}
        for t, flags, fuel in scoop + [(20, 0, 32), (23, 0, 32)]:
            self.j.status_json = {"live": True, "flags": flags, "fuel_main": fuel, "ts": "2026-01-01T00:05:00Z"}
            self.state.watch_status(1000 + t)
        got = self.moments("scoop_end")
        self.assertEqual([(m["full"], m["pct"]) for m in got], [(True, 100)])

    def test_supercharged(self):   # P8: JetConeBoost
        self.j.handle({"event": "JetConeBoost", "timestamp": "2026-01-01T00:01:00Z", "BoostValue": 1.5})
        self.assertEqual([m["mult"] for m in self.moments("supercharged")], [1.5])

    def test_arrival_brief_from_the_honk(self):   # P7: once per arrival, with the facts known at the time
        self.j.handle({"event": "StartJump", "timestamp": "2026-01-01T00:09:50Z", "JumpType": "Hyperspace", "StarSystem": "S5",
                       "SystemAddress": 5, "StarClass": "K"})
        self.jump("2026-01-01T00:10:00Z", 5, 30)
        self.j.handle(scan("2026-01-01T00:10:02Z", "S5", 5, 0, "S5", disc=False, star=True)[2])
        self.planet("2026-01-01T00:10:03Z", 5, 3, "A 3", PlanetClass="Earthlike body", MassEM=1.0)
        self.planet("2026-01-01T00:10:03Z", 5, 4, "A 4", PlanetClass="Water world", MassEM=0.5)
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:10:04Z", "SystemAddress": 5, "BodyName": "S5 A 4", "BodyID": 4})
        self.honk("2026-01-01T00:10:05Z", 5, 14)
        self.honk("2026-01-01T00:11:05Z", 5, 14)                         # a second honk: no second briefing
        got = self.moments("arrival_brief")
        self.assertEqual(len(got), 1)
        b = got[0]
        self.assertEqual((b["source"], b["undiscovered"], b["body_count"], b["star_class"], b["system_name"]), ("honk", True, 14, "K", "S5"))
        self.assertEqual([w["body"] for w in b["worth"]], ["A 3"])        # the mapped water world is left out
        self.assertEqual(b["worth"][0]["notable"], "ELW")
        # a honk in a system you are not in (read late) gives none
        self.honk("2026-01-01T00:12:00Z", 6, 3)
        self.assertEqual(len(self.moments("arrival_brief")), 1)

    def test_arrival_brief_fallback(self):   # P7: 12 s after a live arrival with no honk; not for old journals or mid-honk
        now = time.time()
        self.jump(ed_outrider.iso_ts(now - 5), 7, 40)
        self.state.maybe_brief(now)
        self.assertEqual(self.moments("arrival_brief"), [])               # too soon
        self.state._honk_running = self.j.jump_arrival
        self.state.maybe_brief(now + 10)
        self.assertEqual(self.moments("arrival_brief"), [])               # the auto honk is working on it
        self.state._honk_running = None
        self.state.maybe_brief(now + 10)
        self.state.maybe_brief(now + 11)
        got = self.moments("arrival_brief")
        self.assertEqual([(m["source"], m["system"]) for m in got], [("spansh", "7")])
        self.honk(ed_outrider.iso_ts(now + 20), 7, 5)                    # a honk later on the same visit adds none
        self.assertEqual(len(self.moments("arrival_brief")), 1)
        self.jump(ed_outrider.iso_ts(now - 600), 8, 50)                  # a journal being caught up on
        self.state.maybe_brief(now)
        self.assertEqual(len(self.moments("arrival_brief")), 1)

    def test_session_recap(self):   # P19: game_exit carries the session's numbers over login..quit
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X"})
        for i in range(4):
            self.jump(f"2026-01-01T01:0{i + 1}:00Z", 10 + i, 10 * (i + 1))
        self.j.handle(scan("2026-01-01T01:04:05Z", "S13", 13, 0, "S13", disc=False, star=True)[2])
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T01:30:00Z"})
        s = self.moments("game_exit")[0]["session"]
        self.assertEqual((s["jumps"], s["ly"], s["firsts"]), (4, 40.0, 1))   # F5: the first jump starts where you logged in
        self.j.commander = None
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T02:00:00Z"})
        self.assertIsNone(self.moments("game_exit")[-1]["session"])

    def test_high_gravity_setting(self):
        import tomllib
        args = argparse.Namespace(**{k: None for k in ("journals", "legacy", "host", "port", "radius", "db", "config")})
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual(st["high_gravity"], 2.0)
        st = ed_outrider.settings_from({"defaults": {"high_gravity": 2.5}}, args, None, ([], []))
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["defaults"]["high_gravity"], 2.5)

    def test_style_voice(self):   # P10(b): a personality may name its own Piper voice and pace
        doc = {"styles": {"business": "Business", "sarcastic": {"label": "Sarcastic", "voice": "en_US-ryan-high", "speed": 1.1},
                          "sweet": {"label": "Sweet", "voice": "../../etc/passwd", "speed": 9}}, "lines": {}}
        probs = " ".join(outrider.speech.check(doc))
        self.assertIn('"sweet": "voice"', probs)
        self.assertIn('"sweet": "speed"', probs)
        self.assertNotIn("sarcastic", probs)
        self.assertEqual(outrider.speech.style_voice(doc["styles"], "sarcastic_profane"), ("en_US-ryan-high", 1.1))
        self.assertEqual(outrider.speech.style_voice(doc["styles"], "business"), (None, None))
        self.assertEqual(outrider.speech.style_voice(doc["styles"], "sweet"), (None, None))   # never a path

    def test_style_speaker(self):   # S40: a personality may be one person of a several-person voice
        doc = {"styles": {"business": "Business", "sarcastic": {"label": "Sarcastic", "voice": "en_GB-vctk-medium", "speaker": 12},
                          "sweet": {"label": "Sweet", "speaker": 3}, "dry": {"label": "Dry", "speaker": -1},
                          "odd": {"label": "Odd", "speaker": True}, "wry": {"label": "Wry", "speaker": "2"}}, "lines": {}}
        probs = " ".join(outrider.speech.check(doc))
        for bad in ("dry", "odd", "wry"):
            self.assertIn(f'"{bad}": "speaker"', probs)
        for good in ("sarcastic", "sweet", "business"):
            self.assertNotIn(f'"{good}"', probs)
        speaker = outrider.speech.style_speaker
        self.assertEqual([speaker(doc["styles"], k) for k in ("sarcastic_profane", "sweet", "business", "dry", "odd", "wry", "nope")],
                         [12, 3, None, None, None, None, None])
        self.assertEqual(outrider.speech.style_voice(doc["styles"], "sarcastic"), ("en_GB-vctk-medium", None))   # its tuple unchanged

    def test_voice_pool(self):   # P10(b): installed personality voices load on first use, at most voices_loaded kept
        import io, tempfile, contextlib, wave as _wave
        import outrider.tts
        loads = []

        class FakeVoice:
            def __init__(self, name):
                self.name = name

            def synthesize_wav(self, text, wf, syn_config=None):
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000)
                wf.writeframes(self.name.encode())
        with tempfile.TemporaryDirectory() as d:
            for v in ("en_GB-main-low", "en_US-a-low", "en_US-b-low", "en_US-c-low"):
                for ext in (".onnx", ".onnx.json"):
                    open(os.path.join(d, v + ext), "w").close()
            sp = outrider.tts.Speaker("en_GB-main-low", None, voices_dir=d)
            sp.voices_loaded = 2   # [speech] voices_loaded
            sp.PiperVoice = unittest.mock.Mock()
            sp.PiperVoice.load = lambda path: loads.append(os.path.basename(path)) or FakeVoice(os.path.basename(path))
            with contextlib.redirect_stdout(io.StringIO()):
                sp._prepare(None)
            said = lambda text, voice=None: _wave.open(io.BytesIO(sp.say(text, 1.0, voice))).readframes(99).decode()
            self.assertEqual(said("hi"), "en_GB-main-low.onnx")
            self.assertEqual(said("hi", "en_US-a-low"), "en_US-a-low.onnx")   # same words, its own voice (and cache entry)
            self.assertEqual(said("hi", "en_US-zz-low"), "en_GB-main-low.onnx")   # not installed: the main voice, no download
            said("x", "en_US-b-low"); said("x", "en_US-c-low")
            self.assertEqual(list(sp._extra), ["en_US-b-low", "en_US-c-low"])   # the least recently used went
            said("y", "en_US-c-low")
            self.assertEqual(loads.count("en_US-c-low.onnx"), 1)             # loaded once

    def test_body_letters_for_piper(self):   # a body's letters as letters ("ay one", not "uh one"); names as they are
        import outrider.tts
        b = lambda t, v="en-gb-x-rp": outrider.tts.body_letters(t, v)
        for text, want in (
                ("A 1", "[[ˈeɪ]] 1"),
                ("ABC 3 a, a gas giant", "[[ˈeɪ bˈiː sˈiː]] 3 [[ˈeɪ,]] a gas giant"),   # the comma inside: kept as a pause
                ("A 2 a has 3 signals", "[[ˈeɪ]] 2 [[ˈeɪ]] has 3 signals"),
                ("biology on 2 a, up to 19 million", "biology on 2 [[ˈeɪ,]] up to 19 million"),   # a one-star system
                ("Landed on A 1 c. Three signals.", "Landed on [[ˈeɪ]] 1 [[sˈiː.]] Three signals."),
                ("B 3 A Ring", "[[bˈiː]] 3 [[ˈeɪ]] Ring"), ("3 A Ring", "3 [[ˈeɪ]] Ring"),
                ("A A Belt Cluster 3", "[[ˈeɪ ˈeɪ]] Belt Cluster 3"), ("A Belt Cluster 3", "[[ˈeɪ]] Belt Cluster 3"),
                ("Smojooe A R E, b 25 8 A 1", "Smojooe A R E, b 25 8 [[ˈeɪ]] 1"),   # the system's own letters are its name
                ("Z 1", "[[zˈɛd]] 1"),
                # four stars' letters (the author's ABCD 3 a and ABCD 3 b a, 2026-10-11: said "abd"), and more
                ("ABCD 3 a", "[[ˈeɪ bˈiː sˈiː dˈiː]] 3 [[ˈeɪ]]"), ("ABCD 3 b a", "[[ˈeɪ bˈiː sˈiː dˈiː]] 3 [[bˈiː ˈeɪ]]"),
                ("ABCDE 1", "[[ˈeɪ bˈiː sˈiː dˈiː ˈiː]] 1"), ("ABCD Belt Cluster 2", "[[ˈeɪ bˈiː sˈiː dˈiː]] Belt Cluster 2")):
            self.assertEqual(b(text), want, text)
        for name in ("Jaques Station", "HIP 12345", "LHS 21", "UC 3", "G 139-21", "a class two gas giant", "found 3 a day", "ABBA 2",
                     "ABCDEFGHI 1",
                     "A 2.5 percent", "A 1,000 credits", "Out Of The Blue"):
            self.assertEqual(b(name), name)
        self.assertEqual(b("Z 1", "en-us"), "[[zˈiː]] 1")
        self.assertEqual(b("A 1", "de"), "A 1")     # another language's voice: its own reading
        self.assertEqual(b("A 1", None), "A 1")     # a voice that does not say its language

    def test_say_sends_body_letters_to_piper(self):
        import tempfile, types
        import outrider.tts
        sent = []

        def synth(text, wf, syn_config=None):
            sent.append(text)
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000); wf.writeframes(b"\0\0")
        with tempfile.TemporaryDirectory() as d:
            sp = outrider.tts.Speaker("en_GB-main-low", None, voices_dir=d)
            sp._voice = types.SimpleNamespace(synthesize_wav=synth, config=types.SimpleNamespace(espeak_voice="en-gb-x-rp"))
            self.assertTrue(sp.say("Leaving A 2 a, a gas giant"))
        self.assertEqual(sent, ["Leaving [[ˈeɪ]] 2 [[ˈeɪ,]] a gas giant"])

    def test_letter_sounds_are_espeaks_own(self):   # the sounds espeak gives each letter read on its own
        try:
            from piper.phonemize_espeak import EspeakPhonemizer
        except ImportError:
            self.skipTest("no Piper")
        import outrider.tts
        p = EspeakPhonemizer()
        for voice, sounds in (("en-gb-x-rp", outrider.tts.LETTER_SOUNDS), ("en-us", outrider.tts.LETTER_SOUNDS_US)):
            for letter, sound in sounds.items():
                said = "".join("".join(s) for s in p.phonemize(voice, letter + ".")).strip(" .")
                self.assertEqual(said, sound, (voice, letter))

    def test_say_voice_only_if_installed(self):   # P10(b): /api/say?voice= never names a voice to download
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        got = []

        class FakeSpeaker:
            ready = available = True

            def installed(self):
                return ["en_US-ryan-high"]

            def say(self, text, speed, voice=None):
                got.append(voice)
                return b"RIFF"
        self.state.speaker = FakeSpeaker()

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for v in ("en_US-ryan-high", "en_US-nope-high", ""):
                    self.assertEqual((await c.get("/api/say", params={"text": "hi", "voice": v})).status, 200)
        asyncio.run(go())
        self.assertEqual(got, ["en_US-ryan-high", None, None])


class BatchS2Voice(unittest.TestCase):
    """Batch S2: procedural names said properly, the welcome back after a break, the ship-loss debrief, the audition."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def jump(self, ts, id64, x):
        self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def test_procedural_names_spoken(self):   # P4
        st = outrider.speech.spoken_text
        self.assertEqual(st("Drojau LL-O b26-3 is undiscovered."), "Drojau L L O, b 26 3 is undiscovered.")
        self.assertEqual(st("Syreadiae JX-F c0, 42 ly"), "Syreadiae J X F, c 0, 42 ly")
        self.assertEqual(st("Lost 212.4M near Smojooe AR-E b25-8."), "Lost 212.4 million near Smojooe A R E, b 25 8.")
        self.assertEqual(st("Docked at Jaques Station."), "Docked at Jaques Station.")             # hand-named: untouched
        self.assertEqual(st("Out Of The Blue (K7F-3XZ) arrived"), "Out Of The Blue (K7F-3XZ) arrived")  # a carrier id too

    def test_away_text(self):   # P7
        self.assertIsNone(ed_outrider.away_text(None))
        self.assertIsNone(ed_outrider.away_text(90 * 60))
        self.assertEqual(ed_outrider.away_text(5 * 3600 + 600), "5 hours")
        self.assertEqual(ed_outrider.away_text(3 * 86400 + 600), "3 days")

    def login(self, ts):
        self.j.handle({"event": "LoadGame", "timestamp": ts, "Commander": "J", "Credits": 1})
        return [m for m in self.j.moments if m["kind"] == "game_start"][-1]

    def test_away_from_the_last_session_end(self):   # P7: Shutdown, a crash without one, a relog
        self.assertIsNone(self.login("2026-01-01T00:00:00Z")["away"])   # nothing before it: plain greeting
        self.jump("2026-01-01T01:00:00Z", 1, 0)
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T02:00:00Z"})
        # the game's menu writes Commander and Materials minutes before LoadGame: not where the break ended
        self.j.handle({"event": "Commander", "timestamp": "2026-01-04T01:50:00Z", "Name": "J", "FID": "F1"})
        self.j.handle({"event": "Materials", "timestamp": "2026-01-04T01:50:01Z", "Raw": [], "Manufactured": [], "Encoded": []})
        self.assertEqual(self.login("2026-01-04T02:00:00Z")["away"], "3 days")
        self.jump("2026-01-04T05:00:00Z", 2, 10)                          # then the game crashed: no Shutdown
        self.assertEqual(self.login("2026-01-04T10:20:00Z")["away"], "5 hours")
        self.jump("2026-01-04T10:21:00Z", 3, 20)
        self.assertIsNone(self.login("2026-01-04T10:30:00Z")["away"])    # a relog or mode switch: plain greeting

    def scan_star(self, ts, id64):
        self.j.handle(scan(ts, f"S{id64}", id64, 0, f"S{id64}", star=True)[2])

    def test_ship_loss_debrief(self):   # P15
        base = time.time() - 3600
        t = lambda minutes: ed_outrider.iso_ts(base + minutes * 60)
        self.jump(t(0), 1, 0)
        self.scan_star(t(1), 1)
        self.jump(t(5), 2, 10)
        self.scan_star(t(6), 2)
        self.j.handle(scan(t(7), "S2", 2, 1, "S2 1")[2])
        self.j.handle({"event": "MultiSellExplorationData", "timestamp": t(10), "TotalEarnings": 1, "BaseValue": 1, "Bonus": 0,
                       "Discovered": [{"SystemName": "S1", "NumBodies": 1}]})   # S1 sold before the loss
        self.jump(t(15), 3, 20)
        self.scan_star(t(16), 3)
        self.j.handle({"event": "Died", "timestamp": t(58)})
        self.j.handle({"event": "Resurrect", "timestamp": t(58), "Option": "rebuy"})
        self.jump(t(59), 4, 100)                                          # respawned elsewhere
        self.db.commit()
        loss = self.state.ship_losses()[0]
        (m,) = [x for x in self.state.moments_summary() if x["kind"] == "loss"]
        self.assertEqual((m["carto"], m["bodies"], m["firsts"], m["ship"]), (round(loss["value"]), loss["bodies"], loss["firsts"], True))
        self.assertEqual(m["value"], round(loss["value"] + loss["bio_value"]))
        self.assertEqual(sorted(x["name"] for x in m["top"]), ["S2", "S3"])   # the sold system is not lost
        self.assertEqual(m["systems"], 2)
        self.assertEqual(sum(x["value"] for x in m["top"]), m["carto"])
        self.assertEqual((m["nearest"]["name"], m["nearest"]["distance"]), ("S3", 80.0))   # from where you respawned

    def test_no_debrief_when_the_ship_survived_or_the_death_is_old(self):   # P15
        now = ed_outrider.iso_ts(time.time() - 30)
        self.jump(now, 1, 0)
        self.scan_star(now, 1)
        self.j.handle({"event": "Died", "timestamp": now})
        self.j.handle({"event": "Resurrect", "timestamp": now, "Option": "recover"})   # on foot, nothing lost
        self.db.commit()
        self.assertEqual([x for x in self.state.moments_summary() if x["kind"] == "loss"], [])
        # a death read from an old journal (a catch-up, a re-read) is never narrated
        self.j.handle({"event": "Died", "timestamp": "2026-01-02T00:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-02T00:00:00Z", "Option": "rebuy"})
        self.assertEqual(len([x for x in self.j.moments if x["kind"] == "loss"]), 1)   # only the live one above

    def test_audition_alerts_exist(self):   # P19
        self.assertEqual(len(outrider.speech.AUDITION), 8)
        self.assertLessEqual(set(outrider.speech.AUDITION), set(outrider.speech.KEYS))
        for key in outrider.speech.AUDITION:   # every one has sample values for its placeholders (the crew's: names)
            self.assertLessEqual(outrider.speech.fills(key) - set(outrider.speech.ALWAYS),
                                 set(outrider.speech.SAMPLES.get(key, {})) | set(outrider.speech.CREW_SAMPLES), key)


class BatchAAudio(unittest.TestCase):
    """Batch A: speech and sounds played on the server (the page's "Play speech and sounds on this PC" tick).
    Only fake players (small Python scripts) run here: nothing ever plays on the speakers."""

    def setUp(self):
        import tempfile
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.addCleanup(self.db.close)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "played")

        class FakeSpeaker:
            ready = available = True

            def installed(self):
                return []

            def say(self, text, speed, voice=None):
                return b"RIFF" + text.encode()
        self.state.speaker = FakeSpeaker()

    def fake(self, seconds=0.0, rc=0, stdin=True):
        """A LinePlayer whose player is a Python script: it appends what it was given to self.log (the WAV on
        stdin, or the file it was handed and whether it existed), sleeps, and exits with `rc`."""
        import outrider.tts
        code = ("import os, sys, time\n"
                "data = sys.stdin.buffer.read() if len(sys.argv) < 2 else open(sys.argv[1], 'rb').read()\n"
                f"open({self.log!r}, 'a').write(data.hex() + '|' + (sys.argv[1] if len(sys.argv) > 1 else '-') + '\\n')\n"
                f"time.sleep({seconds}); sys.exit({rc})\n")
        cmd = [sys.executable, "-c", code]
        pl = outrider.tts.LinePlayer("auto", which=lambda n: None)
        pl.player = ("fake", cmd, cmd if stdin else None)
        return pl

    def played(self):
        """[(the WAV bytes played, "-" for stdin or the file's path)]"""
        try:
            with open(self.log) as f:
                return [(bytes.fromhex(a), b) for a, b in (x.split("|") for x in f.read().splitlines())]
        except FileNotFoundError:
            return []

    def client(self, go):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return await go(c)
        return asyncio.run(run())

    def test_player_choice(self):
        import outrider.tts
        have = lambda *names: (lambda n: f"/usr/bin/{n}" if n in names else None)
        self.assertEqual(outrider.tts.find_player("auto", have("paplay", "aplay"))[0], "paplay")   # the first in order
        self.assertEqual(outrider.tts.find_player("auto", have("pw-play", "aplay"))[0], "pw-play")
        self.assertEqual(outrider.tts.find_player("aplay", have("pw-play", "aplay"))[0], "aplay")   # named: that one
        self.assertIsNone(outrider.tts.find_player("ffplay", have("pw-play")))                       # named, missing
        self.assertIsNone(outrider.tts.find_player("auto", have()))
        self.assertIsNone(outrider.tts.find_player("off", have("pw-play")))
        self.assertIsNone(outrider.tts.find_player("vlc", have("vlc", "pw-play")))
        self.assertIsNone(outrider.tts.find_player("auto", have("pw-play"))[2])   # pw-play gets a file, not stdin
        self.assertIsNone(outrider.tts.LinePlayer("off", have("pw-play")).name)
        self.assertEqual(outrider.tts.LinePlayer("nonsense", have("aplay")).choice, "auto")
        self.assertEqual(outrider.tts.LinePlayer("auto", have("aplay")).name, "aplay")

    def test_config_server_player(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = lambda cfg: ed_outrider.settings_from(cfg, args, None, ([], []))["server_player"]
        self.assertEqual(st({}), "auto")
        self.assertEqual(st({"speech": {"server_player": "PaPlay"}}), "paplay")
        self.assertEqual(st({"speech": {"server_player": "off"}}), "off")
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(st({"speech": {"server_player": "vlc"}}), "auto")   # reported, default kept
            self.assertEqual(st({"speech": {"server_player": 1}}), "auto")
            self.assertEqual(st({"speech": "off"}), "auto")
        full = ed_outrider.settings_from({"speech": {"server_player": "aplay"}}, args, None, ([], []))
        self.assertEqual(tomllib.loads(ed_outrider.config_text(full))["speech"]["server_player"], "aplay")
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ed_outrider.toml.example"),
                  encoding="utf-8") as f:
            example = f.read()
        self.assertIn("speech", tomllib.loads(example))   # the section, with the key shown commented out
        self.assertRegex(example.split("[speech]", 1)[1], r'# server_player = "auto"')

    def test_play_waits_and_refuses_a_second_line(self):
        import asyncio
        self.state.player = self.fake(seconds=0.6)

        async def go(c):
            first = asyncio.ensure_future(c.post("/api/say/play", json={"text": "one", "speed": 1.2}))
            await asyncio.sleep(0.25)
            second = await c.post("/api/say/play", json={"text": "two"})   # the first is still playing
            t0 = time.monotonic()
            r1 = await first
            return r1.status, await r1.json(), second.status, time.monotonic() - t0
        s1, b1, s2, _ = self.client(go)
        self.assertEqual((s1, b1, s2), (200, {"ok": True, "stopped": False}, 409))
        self.assertEqual(self.played(), [(b"RIFFone", "-")])   # on stdin; the refused line never played
        self.assertFalse(self.state.player.busy)

    def test_your_own_sound_files(self):   # S16
        import wave
        import outrider.tts
        d = os.path.join(self.tmp, "my-sounds")
        os.makedirs(d)

        def write(name, secs):
            with wave.open(os.path.join(d, name), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
                w.writeframes(b"\x00\x01" * int(8000 * secs))
        write("fanfare.wav", 1.5)
        write("thud.wav", 5)                                  # too long: the voice would wait for it
        write("kazoo.wav", 1)                                 # not one of the sounds
        with open(os.path.join(d, "chime.wav"), "w") as f:
            f.write("not audio")
        bank = outrider.tts.SoundBank(own_dir=d)
        info = bank.info()
        self.assertEqual(info["own"], {"fanfare": 1.5})
        self.assertEqual(len(info["problems"]), 3)
        self.assertTrue(any("thud.wav" in p and "over 3 s" in p for p in info["problems"]))
        with open(os.path.join(d, "fanfare.wav"), "rb") as f:
            mine = f.read()
        self.assertEqual(bank.wav("fanfare"), mine)            # the PC plays your file
        self.assertTrue(bank.wav("alert").startswith(b"RIFF"))   # the others are Outrider's own
        self.assertNotEqual(bank.wav("thud"), outrider.tts.SoundBank(own_dir=d).own_file("thud"))
        self.state.sounds, self.state.speaker = bank, None   # (no voice: the payload needs no Piper here)

        async def go(c):
            r = await c.get("/api/sound/file/fanfare")
            body = await r.read()
            gone = (await c.get("/api/sound/file/thud")).status
            payload = (await (await c.get("/api/nearby")).json())["sound_files"]
            return r.status, body == mine, gone, payload["own"]
        self.assertEqual(self.client(go), (200, True, 404, {"fanfare": 1.5}))

    def test_volume_scales_what_the_pc_plays(self):   # S12
        import array, io, wave
        import outrider.tts
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(array.array("h", [1000, -2000, 32767]).tobytes())
        wav = buf.getvalue()
        half = outrider.tts.scale_wav(wav, 0.5)
        with wave.open(io.BytesIO(half)) as r:
            self.assertEqual(list(array.array("h", r.readframes(3))), [500, -1000, 16383])
        for same in (1, 1.5, None, "loud", float("nan")):
            self.assertIs(outrider.tts.scale_wav(wav, same), wav)
        self.assertEqual(outrider.tts.scale_wav(b"RIFFnot a wav", 0.5), b"RIFFnot a wav")   # not a WAV: as it was
        # the line played on the PC is the scaled one
        self.state.player = self.fake()
        self.state.speaker.say = lambda text, speed, voice=None: wav

        async def go(c):
            return (await c.post("/api/say/play", json={"text": "x", "volume": 0.5})).status
        self.assertEqual(self.client(go), 200)
        self.assertEqual(self.played()[0][0], half)

    def test_next_line_is_made_while_this_one_plays(self):   # S11
        import asyncio
        self.state.player = self.fake(seconds=0.3)
        made, sp = [], self.state.speaker
        real = type(sp).say
        type(sp).say = lambda self_, text, speed, voice=None: (made.append(text), real(self_, text, speed, voice))[1]
        self.addCleanup(setattr, type(sp), "say", real)

        async def go(c):
            r = await c.post("/api/say/play", json={"text": "one", "next": {"text": "two", "speed": 1.0}})
            p = await c.post("/api/say/prefetch", json={"text": "three"})
            await asyncio.sleep(0.2)
            bad = (await c.post("/api/say/prefetch", json=[1])).status
            return r.status, p.status, bad
        self.assertEqual(self.client(go), (200, 202, 400))
        self.assertEqual(made, ["one", "two", "three"])   # "two" after "one"'s audio existed, never before it

    def test_stop(self):
        import asyncio
        self.state.player = self.fake(seconds=10)

        async def go(c):
            t0 = time.monotonic()
            first = asyncio.ensure_future(c.post("/api/say/play", json={"text": "long", "id": "a1"}))
            await asyncio.sleep(0.4)
            other = await (await c.post("/api/say/stop", json={"id": "zz"})).json()   # another page's line: not this
            mine = await (await c.post("/api/say/stop", json={"id": "a1"})).json()
            r = await first
            took = time.monotonic() - t0
            # a stop that overtakes its line: the line is then not played at all
            await c.post("/api/say/stop", json={"id": "b2"})
            early = await (await c.post("/api/say/play", json={"text": "late", "id": "b2"})).json()
            return other, mine, r.status, await r.json(), took, early
        other, mine, status, body, took, early = self.client(go)
        self.assertEqual((other["stopped"], mine["stopped"], status, body), (False, True, 200, {"ok": True, "stopped": True}))
        self.assertLess(took, 5)
        self.assertEqual(early, {"ok": True, "stopped": True})
        self.assertEqual([x[0] for x in self.played()], [b"RIFFlong"])

    def test_503_and_file_players(self):
        import outrider.tts

        async def go(c):
            out = []
            self.state.player = None                                  # tests / no LinePlayer
            out.append((await c.post("/api/say/play", json={"text": "x"})).status)
            self.state.player = outrider.tts.LinePlayer("off")              # server_player = "off"
            r = await c.post("/api/say/play", json={"text": "x"})
            out.append((r.status, (await r.json())["error"]))
            out.append((await c.post("/api/sound/play", json={"name": "chime"})).status)
            self.state.player = self.fake()
            self.state.speaker.ready = False                          # no Piper voice ready
            out.append((await c.post("/api/say/play", json={"text": "x"})).status)
            self.state.speaker.ready = True
            self.state.player = self.fake(rc=1)                       # the player fails: the browser says it
            out.append((await c.post("/api/say/play", json={"text": "x"})).status)
            self.state.player = self.fake(stdin=False)                # pw-play style: a temporary file
            out.append((await c.post("/api/say/play", json={"text": "file"})).status)
            out.append((await c.post("/api/say/play", json=[1])).status)
            out.append((await c.post("/api/say/play", json={"text": "  "})).status)
            return out
        with unittest.mock.patch("sys.stderr"):
            got = self.client(go)
        self.assertEqual(got, [503, (503, "[speech] server_player is off"), 503, 503, 503, 200, 400, 400])
        data, path = self.played()[-1]
        self.assertEqual(data, b"RIFFfile")
        self.assertTrue(path.endswith(".wav"))
        self.assertFalse(os.path.exists(path))   # removed once played

    def test_cap(self):
        import asyncio
        pl = self.fake(seconds=30)
        pl.cap = 0.5
        line = pl.claim()
        t0 = time.monotonic()
        with unittest.mock.patch("sys.stderr"):
            result = asyncio.run(pl.play_line(line, b"RIFF"))
        self.assertEqual(result, "capped")   # played up to the cap: not failed, or the browser says it again
        self.assertTrue(line.stopped)
        self.assertLess(time.monotonic() - t0, 5)

    @staticmethod
    def wav(seconds, rate=8000):
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\0\0" * int(seconds * rate))
        return buf.getvalue()

    def test_a_long_line_plays_to_its_end_and_a_capped_one_is_reported_as_cut(self):
        """R11/R21: the time limit is the line's own length plus some slack (the fixed cap only a floor), so a line
        longer than the cap is heard to its end; a player that hangs past it is cut and the page is told so."""
        import asyncio
        import outrider.tts
        self.assertAlmostEqual(outrider.tts.wav_seconds(self.wav(1.5)), 1.5, places=3)
        self.assertIsNone(outrider.tts.wav_seconds(b"RIFFnot a wav"))
        pl = self.fake(seconds=1.2)
        pl.cap = 0.4                                     # a floor shorter than the line (as 20 s is for a long one)
        self.assertAlmostEqual(pl.line_cap(self.wav(1.0)), 1.0 + outrider.tts.PLAY_SLACK)
        self.assertEqual(pl.line_cap(b"RIFF"), 0.4)      # its length unknown: the cap
        self.assertEqual(pl.line_cap(self.wav(0.1)), max(0.4, 0.1 + outrider.tts.PLAY_SLACK))
        line = pl.claim()
        self.assertEqual(asyncio.run(pl.play_line(line, self.wav(1.0))), "done")   # played on past the 0.4 s floor
        pl.release(line)
        # the endpoint: a hung player (unknown length, past the cap) answers capped, which the page logs as cut
        self.state.player = self.fake(seconds=30)
        self.state.player.cap = 0.3

        async def go(c):
            r = await c.post("/api/say/play", json={"text": "a hung player"})
            return r.status, await r.json()
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(self.client(go), (200, {"ok": True, "stopped": True, "capped": True}))

    def test_sound_play(self):
        import asyncio
        self.state.player = self.fake()

        async def go(c):
            r = await c.post("/api/sound/play", json={"name": "chime"})
            bad = await c.post("/api/sound/play", json={"name": "nope"})
            none = await c.post("/api/sound/play", json={})
            cross = await c.post("/api/sound/play", json={"name": "chime"}, headers={"Sec-Fetch-Site": "cross-site"})
            for _ in range(50):   # it answers at once and plays behind
                if self.played():
                    break
                await asyncio.sleep(0.1)
            await self.state.player.close()
            return r.status, bad.status, none.status, cross.status
        self.assertEqual(self.client(go), (200, 404, 400, 403))
        self.assertEqual(len(self.played()), 1)
        self.assertEqual(self.played()[0][0], self.state.sounds.wav("chime"))

    def test_render_sound(self):
        import io
        import wave
        import outrider.tts
        doc = outrider.tts.load_sounds()
        for name, spec in doc["sounds"].items():
            wav = outrider.tts.render_sound(spec, doc["gain"])
            with wave.open(io.BytesIO(wav)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, outrider.tts.SOUND_RATE), name)
                frames = w.readframes(w.getnframes())
                length = w.getnframes() / w.getframerate()
            end = max(t.get("start", 0) + t["dur"] for t in spec["tones"])
            self.assertAlmostEqual(length, end + 0.05, delta=0.01, msg=name)
            peak = max(abs(v) for v in __import__("struct").unpack(f"<{len(frames) // 2}h", frames))
            self.assertGreater(peak, 1000, name)   # audible
            self.assertLessEqual(peak, 32767, name)
        # the lowpass does something, and a dry tone is left out of it
        fan = doc["sounds"]["fanfare"]
        self.assertNotEqual(outrider.tts.render_sound(fan), outrider.tts.render_sound(dict(fan, lowpass=None)))
        bank = outrider.tts.SoundBank()
        self.assertIsNone(bank.wav("nope"))
        self.assertIs(bank.wav("chime"), bank.wav("chime"))   # rendered once

    def test_sound_names_match_the_page(self):
        import re
        import outrider.tts
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(root, "static", "page.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(root, "ed_outrider.py"), encoding="utf-8") as f:
            py = f.read()
        names = set(outrider.tts.load_sounds()["sounds"])
        alerts = js[js.index("const ALERTS = "):js.index("const UNSPOKEN")]
        used = set(re.findall(r', "(\w+)"\]', alerts))                    # the alerts table's sound column
        used |= set(re.findall(r'\bsound: "(\w+)"', js))                     # alertOut(..., {sound: "upbeat"})
        lead = re.search(r"const SOUND_LEAD = \{([^}]*)\}", js).group(1)
        used |= set(re.findall(r"(\w+):", lead))
        used |= set(re.findall(r'"(thud|fanfare|upbeat)"', py))              # the target and arrival sounds
        tries = set(re.findall(r'data-try="(\w+)"', html))                   # the ▶ buttons
        self.assertTrue(used, "no sound names found in page.js")
        self.assertLessEqual(used, names, used - names)
        self.assertEqual(tries, names)   # every sound can be tried, and every button has a sound
        self.assertNotIn("fanfare(ctx", js)   # the page's own table is gone: it builds from sounds.json
        self.assertIn("/*SOUNDS*/null", html)
        self.assertEqual(set(json.loads(ed_outrider.sounds_json())["sounds"]), names)


# The author's Rhino run of 2026-09-30 on Smojooe AR-E b25-8 ABC 3 d: the journal lines (Journal.2026-09-29T223726.01.log)
# and the Status.json changes recorded during it (Pips, Fuel, FireGroup, LegalState and Balance left out), trimmed to the
# presses and the collections. "S " = Status.json, "J " = a journal line.
class MappedCallout(unittest.TestCase):
    """S8 (review 2026-10-01): the "mapped" call-out's moment and facts (the page says it only with speak_mapped
    ticked), and its config key."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        voice_jump(self, "2026-01-01T00:00:00Z", 1, 0)
        voice_honk(self, "2026-01-01T00:00:10Z", 1, 3)

    def mapped(self, ts, body_id, name, probes=5, target=6):
        self.j.handle({"event": "SAAScanComplete", "timestamp": ts, "SystemAddress": 1, "BodyID": body_id,
                       "BodyName": f"S1 {name}", "ProbesUsed": probes, "EfficiencyTarget": target})

    def moments(self):
        self.db.commit()
        return [m for m in self.state.moments_summary() if m["kind"] == "mapped"]

    def test_a_first_map_is_a_moment_with_its_value_and_what_is_left(self):
        voice_planet(self, "2026-01-01T00:01:00Z", 1, 1, "A 1", MassEM=2.0)
        voice_planet(self, "2026-01-01T00:01:10Z", 1, 2, "A 2", MassEM=3.0)
        self.mapped("2026-01-01T00:05:00Z", 1, "A 1", probes=8, target=6)
        got = self.moments()
        self.assertEqual(len(got), 1)
        m = got[0]
        want = outrider.unsold.body_value({"PlanetClass": "High metal content body", "MassEM": 2.0, "TerraformState": "",
                                     "StarType": None, "StellarMass": None, "first_discovered": True, "first_mapped": True},
                                    True, False, True)
        self.assertEqual((m["body"], m["probes"], m["target"], m["value"], m["system"]), ("A 1", 8, 6, want, "1"))
        self.assertEqual([u["body"] for u in m["leaving"]["unmapped"]], ["A 2"])   # A 1 is done: A 2 is what is next
        # a remap of a body already mapped, and a ring's probe, add no moment
        self.mapped("2026-01-01T00:09:00Z", 1, "A 1")
        self.j.handle({"event": "SAAScanComplete", "timestamp": "2026-01-01T00:10:00Z", "SystemAddress": 1, "BodyID": 9,
                       "BodyName": "S1 A 2 A Ring", "ProbesUsed": 1, "EfficiencyTarget": 0})
        self.assertEqual(len(self.moments()), 1)
        # a body nobody scanned is left out (nothing to say about it)
        self.mapped("2026-01-01T00:11:00Z", 7, "B 7")
        self.assertEqual([m["body"] for m in self.moments()], ["A 1"])

    def test_config_key(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = lambda cfg: ed_outrider.settings_from(cfg, args, None, ([], []))
        self.assertIs(st({})["speak_mapped"], False)
        self.assertIs(st({"defaults": {"speak_mapped": True}})["speak_mapped"], True)
        with unittest.mock.patch("sys.stderr"):
            self.assertIs(st({"defaults": {"speak_mapped": "true"}})["speak_mapped"], False)   # a quoted switch stays off
        back = tomllib.loads(ed_outrider.config_text(st({"defaults": {"speak_mapped": True}})))["defaults"]
        self.assertIs(back["speak_mapped"], True)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "ed_outrider.toml.example"), encoding="utf-8") as f:
            self.assertIn("# speak_mapped = false", f.read().split("[defaults]", 1)[1].split("\n[", 1)[0])
        self.assertIn("`speak_mapped`", user_docs())
        self.assertIn("sayMapped", ed_outrider.BROWSER_SETTINGS)
        self.assertIn("speak_mapped", self.state.payload()["defaults"])


class PlausibleFixes(unittest.TestCase):
    """Third review: the verified plausible findings."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_carrier_lookup_does_not_stamp_a_moved_carrier(self):   # F51
        import asyncio, types
        self.j.handle({"event": "CarrierStats", "timestamp": "2026-09-30T10:00:00Z", "CarrierType": "FleetCarrier",
                       "CarrierID": 7, "Name": "C", "Callsign": "ABC-123"})
        self.j.handle({"event": "CarrierLocation", "timestamp": "2026-09-30T10:00:01Z", "CarrierType": "FleetCarrier",
                       "CarrierID": 7, "StarSystem": "Old", "SystemAddress": 111, "BodyID": 0})
        self.assertEqual(self.j.carrier["id64"], 111)

        async def lookup(id64, interactive=True):
            await asyncio.sleep(0.2)
            return {"system": {"coords": {"x": 1.0, "y": 2.0, "z": 3.0}}}   # the OLD system's coordinates
        self.state.spansh = types.SimpleNamespace(cached=lambda i: (None, None), lookup=lookup)

        async def race():
            self.state.maybe_locate_carrier()
            await asyncio.sleep(0.05)
            self.j.handle({"event": "CarrierLocation", "timestamp": "2026-09-30T10:00:10Z", "CarrierType": "FleetCarrier",
                           "CarrierID": 7, "StarSystem": "New", "SystemAddress": 222, "BodyID": 0})
            await self.state.carrier_task
        asyncio.run(race())
        self.assertEqual(self.j.carrier["id64"], 222)
        self.assertIsNone(self.j.carrier.get("x"))
        saved = ed_outrider.meta_get(self.db, "carrier") or {}
        self.assertIsNone(saved.get("x"))

    def test_non_object_json_body_is_a_400(self):   # F55
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        called = []
        self.state.set_autohonk = lambda on: called.append(on)   # never reached; auto honk is never switched on here

        async def go():
            got = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for path in ("/api/nextstop", "/api/autohonk"):
                    for body in ([1], "x", 5, None) + (({"enabled": "false"}, {"enabled": 1}, {}) if path == "/api/autohonk" else ()):
                        r = await c.post(path, data=json.dumps(body), headers={"Content-Type": "application/json"})
                        got.append((path, body, r.status))
            return got
        for path, body, status in asyncio.run(go()):
            self.assertEqual(status, 400, (path, body))
        self.assertEqual(called, [])

    def test_two_downloads_of_one_voice_do_not_collide(self):   # F69
        import hashlib, io, tempfile, threading
        import outrider.tts
        payload = os.urandom(300_000)

        class Slow(io.BytesIO):
            def read(self, n=-1):
                time.sleep(0.002)
                return super().read(8192)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.close()
        files = [("en/en_GB/x/low/en_GB-x-low.onnx", {"size_bytes": len(payload), "md5_digest": hashlib.md5(payload).hexdigest()}),
                 ("en/en_GB/x/low/en_GB-x-low.onnx.json", {})]
        errs = []
        with tempfile.TemporaryDirectory() as d:
            def dl():
                try:
                    outrider.tts.download_voice_files(files, d)
                except Exception as e:   # noqa: BLE001 -- collected for the assertion
                    errs.append(f"{type(e).__name__}: {e}")
            with unittest.mock.patch.object(outrider.tls.urllib.request, "urlopen",
                                            lambda url, timeout, **k: Slow(b"{}" if url.split("?")[0].endswith(".json") else payload)):
                threads = [threading.Thread(target=dl) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
            self.assertEqual(errs, [])
            self.assertEqual(sorted(os.listdir(d)), ["en_GB-x-low.onnx", "en_GB-x-low.onnx.json"])
            with open(os.path.join(d, "en_GB-x-low.onnx"), "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_three_personality_voices_stay_loaded(self):   # F72
        import tempfile
        import outrider.tts
        loads = []

        class FakeVoice:
            @staticmethod
            def load(path):
                loads.append(os.path.basename(path))
                return FakeVoice()

            def synthesize_wav(self, text, wf, syn_config=None):
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\0\0" * 10)
        names = ("en_GB-a-low", "en_GB-b-low", "en_GB-c-low")
        styles = {"business": "Down to business", "sweet": {"label": "Sweet", "voice": names[0]},
                  "sarcastic": {"label": "Sarcastic", "voice": names[1], "speed": 1.3}, "dry": {"label": "Dry", "voice": names[2]}}
        self.assertEqual(outrider.speech.style_voices(styles), set(names))
        with tempfile.TemporaryDirectory() as d:
            for n in names + ("en_GB-main-low",):
                for ext in (".onnx", ".onnx.json"):
                    with open(os.path.join(d, n + ext), "w") as f:
                        f.write("{}")
            sp = outrider.tts.Speaker("en_GB-main-low", "en_GB-main-low", voices_dir=d)
            sp.PiperVoice, sp._voice, sp.voice_name = FakeVoice, FakeVoice(), "en_GB-main-low"
            if sp.SynthesisConfig is None:
                sp.SynthesisConfig = lambda **kw: None
            sp.size_extra(outrider.speech.style_voices(styles))
            for i in range(9):
                sp.say(f"line {i}", voice=names[i % 3])
        self.assertEqual(sorted(loads), [n + ".onnx" for n in names])   # each loaded once
        sp.size_extra(["x"] * 9 + [f"en_GB-v{i}-low" for i in range(9)])
        self.assertEqual(sp.slots(), outrider.tts.VOICES_LOADED_DEFAULT)   # bounded
        # the server sizes the cache from speech.json's personalities when a line asks for one of their voices
        import asyncio, types
        from aiohttp.test_utils import TestClient, TestServer
        sized = []
        self.state.speaker = types.SimpleNamespace(ready=True, installed=lambda: list(names), size_extra=lambda n: sized.append(set(n)),
                                                   say=lambda text, speed, voice: b"RIFF")
        self.state.speech = types.SimpleNamespace(lines=lambda: {"styles": styles})

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return (await c.get("/api/say", params={"text": "Hello.", "voice": names[1]})).status
        self.assertEqual(asyncio.run(go()), 200)
        self.assertEqual(sized, [set(names)])

    def test_backup_copies_in_steps(self):   # F48
        import sqlite3, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "live.sqlite")
            live = sqlite3.connect(path)
            live.execute("CREATE TABLE t (x)")
            live.executemany("INSERT INTO t VALUES (?)", [(os.urandom(400),) for _ in range(8000)])   # ~800 pages
            live.commit()
            writer = sqlite3.connect(path, timeout=0)   # a commit that had to wait would fail at once
            wrote = []

            class Src:   # the live database, with the tailer committing between every step of the copy
                def backup(self, dst, **kw):
                    if kw.get("progress"):
                        inner = kw["progress"]

                        def progress(*a):
                            writer.execute("INSERT INTO t VALUES (1)")
                            writer.commit()
                            wrote.append(1)
                            return inner(*a)
                        kw["progress"] = progress
                    return live.backup(dst, **kw)
            dst = sqlite3.connect(os.path.join(d, "copy.sqlite"))
            ed_outrider.copy_database(Src(), dst)
            self.assertGreater(len(wrote), 1)                                  # writes got through meanwhile
            self.assertEqual(dst.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(dst.execute("SELECT count(*) FROM t").fetchone()[0],    # and it finished, complete
                             live.execute("SELECT count(*) FROM t").fetchone()[0])
            quiet = sqlite3.connect(os.path.join(d, "quiet.sqlite"))
            ed_outrider.copy_database(live, quiet)                             # no writer: an identical copy
            self.assertEqual(list(quiet.iterdump()), list(live.iterdump()))
            for c in (writer, dst, quiet, live):
                c.close()


class VoiceCatalogue(unittest.TestCase):
    """More voices (2026-10-04): Piper's catalogue from the server, for Settings > Voice (a Docker install has no voice
    lab); a voice is fetched and used through POST /api/voice as before. Cori Medium is the default voice."""
    DOC = {"en_GB-cori-medium": {"language": {"code": "en_GB", "name_english": "English", "country_english": "Great Britain"},
                                 "quality": "medium", "num_speakers": 1,
                                 "files": {"en/en_GB/cori/medium/en_GB-cori-medium.onnx": {"size_bytes": 63_000_000},
                                           "en/en_GB/cori/medium/en_GB-cori-medium.onnx.json": {"size_bytes": 5_000},
                                           "en/en_GB/cori/medium/MODEL_CARD": {"size_bytes": 300}}},
           "de_DE-thorsten-high": {"language": {"code": "de_DE", "name_english": "German", "country_english": "Germany"},
                                   "quality": "high", "num_speakers": 1,
                                   "files": {"de/de_DE/thorsten/high/de_DE-thorsten-high.onnx": {"size_bytes": 114_000_000}}},
           "en_US-libritts-high": {"language": {"code": "en_US", "name_english": "English", "country_english": "United States"},
                                   "quality": "high", "num_speakers": 904, "files": {}},
           "../evil-x-low": {"language": {"code": "en_GB"}, "quality": "low", "files": {}},
           "not a dict": 5}

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_default_voice(self):
        import outrider.tts
        self.assertEqual(outrider.tts.DEFAULT_VOICE, "en_GB-cori-medium")
        st = ed_outrider.settings_from({}, argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None),
                                       None, ([], []))
        self.assertIn('voice = "en_GB-cori-medium"', ed_outrider.config_text(st))
        with open(os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "ed_outrider.toml.example"), encoding="utf-8") as f:
            self.assertIn('voice = "en_GB-cori-medium"', f.read())

    def test_summary(self):
        import outrider.tts
        got = outrider.tts.catalogue_summary(self.DOC, installed=["en_GB-cori-medium"])
        self.assertEqual([v["name"] for v in got], ["de_DE-thorsten-high", "en_GB-cori-medium", "en_US-libritts-high"])   # bad names out
        cori = got[1]
        self.assertEqual((cori["language"], cori["language_name"], cori["quality"], cori["size_mb"], cori["installed"], cori["speakers"]),
                         ("en_GB", "English (Great Britain)", "medium", 63, True, 1))
        self.assertEqual((got[0]["installed"], got[2]["speakers"]), (False, 904))
        # Piper's own recording of each, to hear before downloading (the author, 2026-10-11)
        self.assertEqual(cori["sample"], "https://rhasspy.github.io/piper-samples/samples/en/en_GB/cori/medium/speaker_0.mp3")

    def test_endpoint(self):
        import asyncio
        import types
        import outrider.tts
        from aiohttp.test_utils import TestClient, TestServer
        self.state.speaker = speaker = types.SimpleNamespace(available=True, installed=lambda: ["en_GB-cori-medium"], voice_name="en_GB-cori-medium")
        calls = []

        def fetch(force=False):
            calls.append(force)
            if len(calls) == 3:
                raise OSError("no network")
            return self.DOC

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = []
                for q in ("", "?refresh=1", ""):
                    r = await c.get("/api/voices/catalogue" + q)
                    out.append((r.status, await r.json()))
                speaker.available = False
                r = await c.get("/api/voices/catalogue")
                out.append((r.status, await r.json()))
                return out
        with unittest.mock.patch.object(outrider.tts, "fetch_catalogue", fetch):
            out = asyncio.run(go())
        self.assertEqual(calls, [False, True, False])
        status, d = out[0]
        self.assertEqual((status, d["current"], [v["name"] for v in d["voices"] if v["installed"]]), (200, "en_GB-cori-medium", ["en_GB-cori-medium"]))
        self.assertEqual((out[2][0], out[2][1]["code"]), (502, "catalogue_unavailable"))
        self.assertEqual(out[3][0], 503)   # no Piper: nothing to download for

    def test_catalogue_cut_off_is_an_os_error(self):
        """A connection cut mid-body raises http.client.IncompleteRead, which is no OSError: the server answered a bare
        500 instead of its 502 catalogue_unavailable (review 2026-10-11)."""
        import http.client
        import tempfile
        import outrider.tts

        class Cut:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                raise http.client.IncompleteRead(b"{")
        with tempfile.TemporaryDirectory() as d, \
                unittest.mock.patch.object(outrider.tls.urllib.request, "urlopen", lambda *a, **k: Cut()):
            with self.assertRaises(OSError):
                outrider.tts.fetch_catalogue(force=True, cache=os.path.join(d, "voices.json"))

    def test_fetch_catalogue_shared(self):
        """The server reads Piper's catalogue from its cache (tts.fetch_catalogue), refetched after a week."""
        import io
        import tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "voices.json")
            with unittest.mock.patch.object(outrider.tls.urllib.request, "urlopen", lambda url, timeout, **k: io.BytesIO(b'{"en_GB-a-low": {}}')):
                self.assertEqual(outrider.tts.fetch_catalogue(cache=cache), {"en_GB-a-low": {}})
            with unittest.mock.patch.object(outrider.tls.urllib.request, "urlopen", lambda url, timeout, **k: io.BytesIO(b'{"x": 1}')):
                self.assertEqual(outrider.tts.fetch_catalogue(cache=cache), {"en_GB-a-low": {}})          # cached
                os.utime(cache, (1, time.time() - outrider.tts.CATALOGUE_MAX_AGE - 5))
                self.assertEqual(outrider.tts.fetch_catalogue(cache=cache), {"x": 1})                     # a week old


class AudioBlocked(unittest.TestCase):
    """The browser holds audio back until a click (2026-10-04, the author's Docker server: the page then spoke in the
    browser's voice). The speaking window tells the server (POST /api/speaker/audio) and the payload carries it, so
    the tablet can say the PC's page needs a click; it lapses with the speaking window itself."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_reported_and_lapses(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = [self.state.payload()["speaker_audio_blocked"]]
                v = self.state.version
                out.append((await c.post("/api/speaker/audio", json={"blocked": True})).status)
                out += [self.state.payload()["speaker_audio_blocked"], self.state.version > v]
                out.append((await c.post("/api/speaker/audio", json={"blocked": "yes"})).status)
                out.append((await c.post("/api/speaker/audio", json={"blocked": False})).status)
                out.append(self.state.payload()["speaker_audio_blocked"])
                return out
        self.assertEqual(asyncio.run(go()), [False, 200, True, True, 400, 200, False])
        self.state.speaker_audio_blocked = True
        self.state.speaker_seen = time.monotonic() - self.state.SPEAKER_SEEN_S - 1   # the window went away
        self.assertFalse(self.state.payload()["speaker_audio_blocked"])


class SweepVoiceFixes(unittest.TestCase):
    """The full sweep of 2026-10-09 (Piper)."""

    def test_one_rule_for_the_lines_file(self):
        """An old speech_file = "speech.json" resolves to resources/ (the voice lab, since retired, showed no lines)."""
        import tempfile, shutil
        root, res = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, res)
        with open(os.path.join(res, "speech.json"), "w") as f:
            f.write("{}")
        said = []
        got = outrider.speech.resolve_speech_file("speech.json", root, "DEFAULT", res, warn=said.append)
        self.assertEqual(got, os.path.join(res, "speech.json"))
        self.assertTrue(said)
        self.assertEqual(outrider.speech.resolve_speech_file("", root, "DEFAULT", res), "DEFAULT")

    def test_piper_in_a_windows_venv(self):
        import tempfile, shutil, sys
        import outrider.tts as T
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, ".venv"))
        ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        with open(os.path.join(root, ".venv", "pyvenv.cfg"), "w") as f:
            f.write(f"home = C:\\Python\nversion = {ver}.4\n")
        self.assertIn(os.path.join(root, ".venv", "Lib", "site-packages"), T._venv_site_packages(root, nt=True))
        self.assertNotIn(os.path.join(root, ".venv", "Lib", "site-packages"), T._venv_site_packages(root, nt=False))
        with open(os.path.join(root, ".venv", "pyvenv.cfg"), "w") as f:
            f.write("version = 2.7.18\n")                       # another Python's packages: not taken
        self.assertEqual(len(T._venv_site_packages(root, nt=True)), 1)

    def test_abandoned_downloads_are_swept(self):
        import tempfile, shutil, time
        import outrider.tts as T
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        old, fresh, voice = (os.path.join(d, n) for n in ("v.onnx.ab12.part", "v.onnx.cd34.part", "v.onnx"))
        for p in (old, fresh, voice):
            open(p, "w").close()
        t = time.time() - 2 * T.PART_STALE_S
        os.utime(old, (t, t))
        os.utime(voice, (t, t))
        self.assertEqual(T.sweep_parts(d), 1)
        self.assertEqual(sorted(os.listdir(d)), ["v.onnx", "v.onnx.cd34.part"])   # a download under way is left alone


class Speakers(unittest.TestCase):
    """Several-person voices (the author, 2026-10-11): a Piper voice trained on many people speaks as the one picked for
    it (its "speaker"), each voice keeping its own, remembered over restarts; the voice lab tries one without
    switching. Outrider used to ignore them (always the first person)."""

    def setUp(self):
        import tempfile
        import types
        import outrider.tts
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        for name, cfg in (("en_GB-vctk-medium", {"num_speakers": 3, "speaker_id_map": {"p225": 0, "p226": 1, "p227": 2}}),
                          ("en_GB-cori-medium", {"num_speakers": 1, "speaker_id_map": {}}),
                          ("en_US-plain-low", {"num_speakers": 2})):
            with open(os.path.join(self.dir, name + ".onnx"), "w") as f:
                f.write("x")
            with open(os.path.join(self.dir, name + ".onnx.json"), "w") as f:
                json.dump(cfg, f)
        self.configs = []

        class Voice:
            def __init__(v, name):
                v.name = name

            def synthesize_wav(v, text, wf, syn_config=None):
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000)
                wf.writeframes(f"{v.name}:{syn_config}".encode())
        self.remembered = []
        sp = self.sp = outrider.tts.Speaker("en_GB-vctk-medium", None, voices_dir=self.dir, speakers={"en_GB-vctk-medium": 9, "x": "no"},
                                            on_speaker=self.remembered.append)
        sp.PiperVoice = types.SimpleNamespace(load=lambda path: Voice(os.path.basename(path)[:-5]))
        sp.SynthesisConfig = lambda **kw: json.dumps(kw, sort_keys=True)
        sp._voice, sp.voice_name = Voice("en_GB-vctk-medium"), "en_GB-vctk-medium"
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.speaker = sp

    def heard(self, *a, **kw):
        import io
        import wave
        return wave.open(io.BytesIO(self.sp.say(*a, **kw))).readframes(999).decode()

    def test_speakers_picked_kept_and_used(self):
        sp = self.sp
        self.assertEqual(sp.voice_speakers("en_GB-vctk-medium"), [{"id": 0, "name": "p225"}, {"id": 1, "name": "p226"}, {"id": 2, "name": "p227"}])
        self.assertEqual(sp.voice_speakers("en_GB-cori-medium"), [])                           # one person
        self.assertEqual([p["name"] for p in sp.voice_speakers("en_US-plain-low")], ["0", "1"])   # no names: numbers
        self.assertIsNone(sp.speaker_for("en_GB-vctk-medium"))   # the remembered 9 is no speaker of it: its first
        self.assertEqual(self.heard("Hello."), "en_GB-vctk-medium:None")
        self.assertTrue(sp.set_speaker("en_GB-vctk-medium", 2))
        self.assertEqual(self.remembered[-1], {"en_GB-vctk-medium": 2})
        self.assertEqual(self.heard("Hello."), 'en_GB-vctk-medium:{"speaker_id": 2}')       # not the cached first person
        self.assertEqual(self.heard("Hello.", 1.5), 'en_GB-vctk-medium:{"length_scale": 0.6666666666666666, "speaker_id": 2}')
        self.assertEqual(self.heard("Hello.", speaker=1), 'en_GB-vctk-medium:{"speaker_id": 1}')   # the lab's try
        self.assertEqual(self.heard("Hello.", speaker=7), 'en_GB-vctk-medium:{"speaker_id": 2}')   # no such: the picked one
        self.assertEqual(self.heard("Hi.", voice="en_US-plain-low", speaker=1), 'en_US-plain-low:{"speaker_id": 1}')   # another voice
        info = sp.info()
        self.assertEqual((info["speaker"], info["speakers"], info["speaker_name"]), (2, 3, "p227"))
        for bad in (("en_GB-vctk-medium", 3), ("en_GB-vctk-medium", True), ("en_GB-cori-medium", 0), ("en_GB-nope-low", 0)):
            self.assertFalse(sp.set_speaker(*bad), bad)
        self.assertTrue(sp.set_speaker("en_GB-vctk-medium", None))
        self.assertEqual(self.remembered[-1], {})

    def test_the_lines_banner_follows_the_file(self):
        """Review 2026-10-20 L8: the speech banner was set once at start: it stayed after the file was fixed, and a file
        that broke later raised none (Settings showed the error, the banner did not)."""
        import inspect
        import types
        info = {"version": 1, "error": None, "file": "speech.json", "problems": []}
        self.state.speech = types.SimpleNamespace(info=lambda: dict(info))
        self.assertIn("self.speech_status()", inspect.getsource(ed_outrider.State.payload))   # with every payload
        self.state.speech_status()
        self.assertNotIn("speech", self.state.notices.items)
        info["problems"] = ['"mine": line 3: unknown placeholder {sistem}']   # broke after start
        self.state.speech_status()
        self.assertIn("1 problem", self.state.notices.items["speech"]["text"])
        info["problems"] = []                                                # fixed
        self.state.speech_status()
        self.assertNotIn("speech", self.state.notices.items)

    def test_a_self_made_voice_for_a_personality(self):
        """Review 2026-10-20 L7: a voice installed under its own name (not language_REGION-name-quality) was accepted for a
        personality, then dropped by style_picks (the main voice and the crew take it)."""
        import types
        for ext, body in ((".onnx", "x"), (".onnx.json", "{}")):
            with open(os.path.join(self.dir, "myvoice" + ext), "w") as f:
                f.write(body)
        self.state.speech = types.SimpleNamespace(lines=lambda: {"styles": {"naval": "Naval"}})
        self.assertIsNone(self.state.set_style_pick("naval", "myvoice"))
        self.assertEqual(self.state.style_picks(), {"naval": {"voice": "myvoice", "speaker": None}})
        os.remove(os.path.join(self.dir, "myvoice.onnx"))   # gone from the PC: left out again
        self.assertEqual(self.state.style_picks(), {})

    def test_picking_a_speaker_never_waits_for_a_line_being_made(self):
        """Review 2026-10-20 M5: set_speaker runs on the event loop and waited on the synthesis lock, stalling the whole
        server for the rest of a line; the cache clear is skipped then (the speaker is in every line's key)."""
        import threading
        import time as _t
        self.heard("Hello.")
        with self.sp._lock:   # a line being made on the speech thread
            t0 = _t.monotonic()
            done = []
            th = threading.Thread(target=lambda: done.append(self.sp.set_speaker("en_GB-vctk-medium", 1)))
            th.start()
            th.join(2)
            self.assertEqual((done, _t.monotonic() - t0 < 1), ([True], True))
        self.assertEqual(self.heard("Hello."), 'en_GB-vctk-medium:{"speaker_id": 1}')   # the new person, not the cached clip

    def test_the_api(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        self.sp.on_speaker = self.state.remember_speakers
        self.used = []

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = {}
                r = await c.get("/api/voices/speakers", params={"voice": "en_GB-vctk-medium"})
                out["list"] = (r.status, await r.json())
                out["missing"] = (await c.get("/api/voices/speakers", params={"voice": "en_GB-nope-low"})).status
                out["set"] = (await c.post("/api/voice", json={"speaker": 1})).status            # the voice in use's
                # the voice in use picked by name: still use()d, so it is remembered and wins over a background switch
                self.sp.use = lambda name: self.used.append(name) or True
                out["same"] = (await c.post("/api/voice", json={"voice": "en_GB-vctk-medium"})).status
                out["bad"] = [(await c.post("/api/voice", json=b)).status for b in
                              ({"speaker": 5}, {"speaker": "1"}, {"voice": "en_GB-cori-medium", "speaker": 0}, {})]
                r = await c.get("/api/say", params={"text": "Hello.", "speaker": "2"})
                out["say"] = await r.read()
                return out
        out = asyncio.run(go())
        self.assertEqual(out["list"], (200, {"voice": "en_GB-vctk-medium", "speaker": None,
                                             "speakers": [{"id": 0, "name": "p225"}, {"id": 1, "name": "p226"}, {"id": 2, "name": "p227"}]}))
        self.assertEqual((out["missing"], out["set"], out["bad"]), (404, 200, [400, 400, 400, 400]))
        self.assertEqual((out["same"], self.used), (200, ["en_GB-vctk-medium"]))   # review 2026-10-12
        self.assertEqual(ed_outrider.meta_get(self.db, "voice_speakers"), {"en_GB-vctk-medium": 1})   # kept over restarts
        self.assertIn(b'{"speaker_id": 2}', out["say"])                                         # the lab's try of another


    def test_a_voice_per_personality(self):
        """S40: Settings' Personality voices (and the voice lab's Give to this personality) keep a personality's voice and
        person on the server (meta style_picks, for every browser), refuse what cannot be said, and leave it through a
        journal re-read; a line sent with a voice that is not installed is said in the main voice by its own person,
        never by that number of the main voice; the voices kept loaded count the picks."""
        import asyncio
        import types
        from aiohttp.test_utils import TestClient, TestServer
        styles = {"business": "Business", "sarcastic": {"label": "Sarcastic", "voice": "en_US-plain-low"}, "sweet": "Sweet"}
        self.state.speech = types.SimpleNamespace(lines=lambda: {"styles": styles}, info=lambda: None)
        post = lambda c, b: c.post("/api/voice/style", json=b)   # noqa: E731

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = {}
                r = await post(c, {"style": "sweet", "voice": "en_GB-vctk-medium", "speaker": 2})
                out["set"] = (r.status, await r.json())
                out["plain"] = (await post(c, {"style": "business", "voice": "en_GB-cori-medium"})).status
                out["bad"] = [(await post(c, b)).status for b in (
                    {"style": "dry", "voice": "en_GB-cori-medium"}, {"style": "sweet", "voice": "en_GB-nope-low"},
                    {"style": "sweet", "voice": "en_GB-vctk-medium", "speaker": 3}, {"style": "sweet", "voice": "en_GB-cori-medium", "speaker": 0},
                    {"style": "sweet", "voice": "en_GB-vctk-medium", "speaker": "1"}, {"style": "sweet", "voice": "en_GB-vctk-medium", "speaker": True},
                    {"style": "sweet"}, {"style": "sweet", "voice": "../x"})]
                out["picks"] = self.state.payload()["style_picks"]
                out["voices"] = self.state.personality_voices()
                out["reset"] = (await (await post(c, {"style": "business", "voice": None})).json())["style_picks"]
                # a personality's voice gone from the PC: its number is not the main voice's person
                out["gone"] = await (await c.get("/api/say", params={"text": "Gone.", "voice": "en_GB-nope-low", "speaker": "1"})).read()
                out["main"] = await (await c.get("/api/say", params={"text": "Main.", "speaker": "1"})).read()
                return out
        out = asyncio.run(go())
        want = {"sweet": {"voice": "en_GB-vctk-medium", "speaker": 2}, "business": {"voice": "en_GB-cori-medium", "speaker": None}}
        self.assertEqual(out["set"][0], 200)
        self.assertEqual(out["set"][1]["style_picks"], {"sweet": want["sweet"]})
        self.assertEqual((out["plain"], out["bad"]), (200, [400] * 8))
        self.assertEqual(out["picks"], want)
        self.assertEqual(out["voices"], {"en_US-plain-low", "en_GB-vctk-medium", "en_GB-cori-medium"})
        self.assertEqual(out["reset"], {"sweet": want["sweet"]})
        self.assertIn(b"en_GB-vctk-medium:None", out["gone"])
        self.assertIn(b'en_GB-vctk-medium:{"speaker_id": 1}', out["main"])   # a speaker of the main voice still works
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)                # live-only: a re-read keeps it
        self.assertEqual(self.state.style_picks(), {"sweet": want["sweet"]})
        self.state.speaker = None
        self.assertEqual(asyncio.run(self._post_once({"style": "sweet", "voice": "en_GB-vctk-medium"})), 503)

    async def _post_once(self, body):
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
            return (await c.post("/api/voice/style", json=body)).status


class LabInThePage(unittest.TestCase):
    def test_audition_keys_in_step(self):
        """The voice lab's Audition (page.js AUDITION_KEYS, 2026-10-11) is outrider.speech.AUDITION."""
        import re
        with open(os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "static", "page.js"), encoding="utf-8") as f:
            m = re.search(r"const AUDITION_KEYS = \[([^\]]*)\]", f.read())
        self.assertEqual(tuple(re.findall(r'"(\w+)"', m.group(1))), outrider.speech.AUDITION)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "voice_lab.py")))   # retired


class LabDownload(unittest.TestCase):
    def test_download_without_switching(self):
        """The voice lab's More voices downloads a voice without switching to it (the author, 2026-10-11): fetching is
        listed meanwhile, the voice in use stays, a failure is said."""
        import asyncio
        import tempfile
        import types
        import outrider.tts
        from aiohttp.test_utils import TestClient, TestServer
        with tempfile.TemporaryDirectory() as d:
            sp = outrider.tts.Speaker("en_GB-cori-medium", None, voices_dir=d)
            sp.PiperVoice = types.SimpleNamespace(load=lambda p: object())
            sp._voice, sp.voice_name, sp.status = object(), "en_GB-cori-medium", "ready"
            got = []

            def fake_download(name, status=None):
                got.append((name, sp.info()["fetching"]))
                if name == "en_GB-bad-low":
                    return False
                for ext in (".onnx", ".onnx.json"):
                    with open(os.path.join(d, name + ext), "w") as f:
                        f.write("{}")
                return True
            sp._download = fake_download
            self.assertFalse(sp.fetch("../etc-x-low"))
            self.assertTrue(sp.fetch("en_GB-alan-low"))
            for _ in range(100):
                if not sp.fetching:
                    break
                time.sleep(0.01)
            self.assertEqual(got, [("en_GB-alan-low", ["en_GB-alan-low"])])
            self.assertIn("en_GB-alan-low", sp.info()["voices"])
            self.assertEqual((sp.voice_name, sp.status), ("en_GB-cori-medium", "ready"))   # not switched
            sp.fetch("en_GB-bad-low")
            for _ in range(100):
                if not sp.fetching:
                    break
                time.sleep(0.01)
            self.assertEqual(sp.info()["fetch_failed"], {"en_GB-bad-low": "the download failed"})
            # a switch's status set during the lab's download is not wiped when the download ends (review 2026-10-12)
            def busy(name, status=None):
                sp.status = "downloading en_US-other-low (about 63 MB)"
                return False
            sp._download = busy
            sp.fetch("en_GB-busy-low")
            for _ in range(100):
                if not sp.fetching:
                    break
                time.sleep(0.01)
            self.assertEqual(sp.status, "downloading en_US-other-low (about 63 MB)")
            db = ed_outrider.open_db(":memory:")
            self.addCleanup(db.close)
            state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
            state.speaker = sp

            async def go():
                async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                    return [(await c.post("/api/voices/download", json=b)).status for b in ({"voice": "en_GB-alan-low"}, {"voice": "x"}, {})]
            self.assertEqual(asyncio.run(go()), [200, 400, 400])
