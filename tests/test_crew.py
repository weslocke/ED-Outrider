"""The crew (crew batch 1, the author's plan of 2026-10-13): the spoken alerts split among crew members, each with its own
personality and voice. The row -> role table (outrider.speech.CREW_ROLES) against the page's alert rows, meta crew and POST
/api/voice/crew, the XO speaking for any member who cannot (logged once per voice and reason), the voices kept loaded
([speech] voices_loaded / voices_preload: the Speaker's LRU) and the memory estimate. Fake voices only, in a scratch folder."""
import asyncio
import contextlib
import io
import json
import os
import re
import tempfile
import types
import unittest

from support import ed_outrider

import outrider.speech  # noqa: E402
import outrider.tts  # noqa: E402

PAGE_JS = os.path.join(ed_outrider.STATIC_DIR, "page.js")
STYLES = {"business": "Down to business", "sarcastic": {"label": "Sarcastic", "voice": "en_US-plain-low"}, "sweet": "Sweet"}


class Voice:
    """A loaded fake voice: its WAV's frames are its name and the synthesis config, so a test hears who spoke."""

    def __init__(self, name):
        self.name = name

    def synthesize_wav(self, text, wf, syn_config=None):
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000)
        wf.writeframes(f"{self.name}:{syn_config}".encode())


def voices_dir(test, voices):
    """A scratch piper-voices folder: {name: (.onnx size in bytes, its .onnx.json)}."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    for name, (size, cfg) in voices.items():
        with open(os.path.join(tmp.name, name + ".onnx"), "wb") as f:
            f.write(b"x" * size)
        with open(os.path.join(tmp.name, name + ".onnx.json"), "w") as f:
            json.dump(cfg, f)
    return tmp.name


def fake_speaker(d, main="en_GB-cori-medium", bad=()):
    """A Speaker over folder `d` whose voices load as fakes (those in `bad` raise), the main one ready."""
    sp = outrider.tts.Speaker(main, None, voices_dir=d)
    loads = []

    def load(path):
        name = os.path.basename(path)[:-5]
        loads.append(name)
        if name in bad:
            raise RuntimeError("damaged")
        return Voice(name)
    sp.PiperVoice = types.SimpleNamespace(load=load)
    sp.SynthesisConfig = lambda **kw: json.dumps(kw, sort_keys=True)
    sp._voice, sp.voice_name, sp.status = Voice(main), main, "ready"
    sp.loads = loads
    return sp


class CrewTable(unittest.TestCase):
    def test_rows_in_step_with_the_page(self):
        """Every alert row of Settings -> Alerts (page.js ALERTS) belongs to exactly one role, and no role names a row the
        page lacks; the XO and Tactical have none of their own (the XO speaks what no row is, Tactical the danger lines)."""
        with open(PAGE_JS, encoding="utf-8") as f:
            js = f.read()
        block = js[js.index("const ALERTS = ["):js.index("// never spoken, and why")]
        page_rows = re.findall(r'\["(\w+)", "', block)
        self.assertEqual(len(page_rows), len(set(page_rows)))
        table_rows = [row for _, _, _, rows in outrider.speech.CREW_ROLES for row in rows]
        self.assertEqual(sorted(table_rows), sorted(page_rows))        # each once, none missing, none extra
        self.assertEqual(outrider.speech.CREW_IDS, ("xo", "navigator", "science", "exobiologist", "engineer",
                                                    "quartermaster", "comms", "tactical", "mining"))
        self.assertEqual([r["rows"] for r in outrider.speech.crew_roles_info() if r["id"] in ("xo", "tactical")], [[], []])
        self.assertIn("const DANGER = new Set(", js)                  # Tactical's lines: the page's danger keys

    def test_default_rows(self):
        """The approved defaults (the author, 2026-10-13): the Navigator keeps every route line, trade too; low fuel with
        the Chief Engineer; the rigs with the Mining Officer; the game's start and quit with Comms."""
        role = outrider.speech.CREW_ROW_ROLE
        want = {"jump": "navigator", "highway": "navigator", "riches": "navigator", "trade": "navigator",
                "refuelshort": "navigator", "lastscoop": "navigator", "wrongtarget": "navigator",
                "arrival": "science", "brief": "science", "codex": "science", "exo": "exobiologist", "sampling": "exobiologist",
                "fuel": "engineer", "hull": "engineer", "scoop": "engineer", "sell": "quartermaster", "carrier": "quartermaster",
                "loss": "quartermaster", "game": "comms", "firstsseen": "comms", "rigs": "mining", "rigleash": "mining"}
        self.assertEqual({k: role[k] for k in want}, want)
        self.assertEqual(outrider.speech.CREW_SHORT["engineer"], "Engineer")   # the log's (and later the lines') name

    def test_served_with_the_lines(self):
        """GET /api/speech carries the table (crew_roles), with or without a lines file."""
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)

        async def go():
            from aiohttp.test_utils import TestClient, TestServer
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                return await (await c.get("/api/speech")).json()
        got = asyncio.run(go())
        self.assertEqual(got["crew_roles"], outrider.speech.crew_roles_info())
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "speech.json")
            with open(path, "w") as f:
                json.dump({"styles": STYLES, "lines": {}}, f)
            self.assertEqual(outrider.speech.SpeechLines(path).lines()["crew_roles"][0]["id"], "xo")


class CrewSettingsPage(unittest.TestCase):
    """Crew batch 2: Settings' crew table, memory note and Alerts' Crew column (page.js ROW_WORDS, ROW_KEYS)."""

    @classmethod
    def setUpClass(cls):
        with open(PAGE_JS, encoding="utf-8") as f:
            cls.js = f.read()
        block = cls.js[cls.js.index("const ALERTS = ["):cls.js.index("// never spoken, and why")]
        cls.rows = re.findall(r'\["(\w+)", "', block)

    def table(self, name):
        """A page.js object literal of words or lists, {key: value}."""
        start = self.js.index(f"const {name} = {{")
        text = self.js[start:self.js.index("};", start)]
        return {k: (re.findall(r'"(\w+)"', v) if v.startswith("[") else v.strip('"'))
                for k, v in re.findall(r'(\w+): ("[^"]*"|\[[^\]]*\])', text)}

    def test_row_words_and_keys_in_step(self):
        """Every alert row has its words for "Speaks for"; every row's speech keys are real keys (outrider.speech.KEYS) of
        a real row; every danger key (DANGER) is in the row whose alertOut says it, so the Alerts table's "spoken by
        Tactical (danger)" and Tactical's ▶ follow the lines."""
        words, keys = self.table("ROW_WORDS"), self.table("ROW_KEYS")
        self.assertEqual(sorted(words), sorted(self.rows))
        self.assertTrue(set(keys) <= set(self.rows), set(keys) - set(self.rows))
        danger = re.findall(r'"(\w+)"', self.js[self.js.index("const DANGER = new Set("):].split(")", 1)[0])
        # (rig_leash: a danger tag with plain words, no lines of its own)
        self.assertEqual([k for ks in keys.values() for k in ks if k not in outrider.speech.KEYS and k not in danger], [])
        self.assertIn("fuel_low", danger)
        for key in danger:
            said = set()
            for m in (list(re.finditer(r'tag: "%s"' % key, self.js)) or re.finditer(r'line\("%s"' % key, self.js)):
                said.add(re.findall(r'alertOut\("(\w+)"', self.js[:m.start()])[-1])   # the alertOut this tag is part of
            self.assertTrue(said, key)
            for row in said:
                self.assertIn(key, keys.get(row, []), f"{key} is said by the row {row}")

    def test_tablet_settings_have_no_crew(self):
        """The crew is set on the PC: the tablet's own Settings sheet has none of it."""
        with open(os.path.join(ed_outrider.STATIC_DIR, "page.html"), encoding="utf-8") as f:
            html = f.read()
        start = html.index('<dialog id="tabSettings"')
        sheet = html[start:html.index("</dialog>", start)]
        self.assertNotIn("crew", sheet.lower())
        self.assertNotIn("voices kept loaded", sheet.lower())
        self.assertIn('id="crewTable"', html)
        self.assertIn('data-find="speech.voices_loaded"', html)
        self.assertIn('data-find="speech.voices_preload"', html)


class KeepLoadedSaved(unittest.TestCase):
    """Settings -> Voice's Keep loaded and Load them at start are written into the config file (POST /api/config) and,
    being about the machine that speaks, applied at once: no restart."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "ed_outrider.toml")
        with open(os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "ed_outrider.toml.example"), encoding="utf-8") as f:
            text = f.read()
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        self.dir = voices_dir(self, {"en_GB-cori-medium": (64, {"num_speakers": 1}), "en_GB-alan-low": (50, {"num_speakers": 1}),
                                     "en_US-plain-low": (20, {"num_speakers": 1})})
        self.sp = fake_speaker(self.dir)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.config_path = self.path
        self.state.speaker = self.sp
        self.state.speech = types.SimpleNamespace(lines=lambda: {"styles": STYLES}, info=lambda: None)

    def post(self, *bodies):
        async def go():
            from aiohttp.test_utils import TestClient, TestServer
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for b in bodies:
                    r = await c.post("/api/config", json=b)
                    out.append((r.status, await r.json()))
            return out
        return asyncio.run(go())

    def test_pad_delay_applied_at_once(self):
        """Settings -> Voice's landing pad delay ([speech] pad_delay): written to the config, applied to the next grant at
        once, in the payload; anything but 0-20 s refused by the config's own checks."""
        (status, answer), = self.post({"speech": {"pad_delay": 12}})
        self.assertEqual((status, answer["live"]), (200, ["speech.pad_delay"]))
        self.assertEqual((self.state.journals.pad_delay, self.state.payload()["pad_delay"]), (12, 12))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(__import__("tomllib").loads(f.read())["speech"]["pad_delay"], 12)

    def test_applied_at_once(self):
        ed_outrider.meta_set(self.db, "crew", {"on": True, "members": {"navigator": {"voice": "en_GB-alan-low"}}})
        self.sp.size_extra(self.state.voices_in_use())   # the sarcastic personality's voice and the Navigator's
        self.sp.extra_voice("en_GB-alan-low"); self.sp.extra_voice("en_US-plain-low")
        self.assertEqual(len(self.sp._extra), 2)
        v0 = self.state.version
        (st1, a1), (st2, a2), (st3, a3) = self.post({"speech": {"voices_loaded": "1"}}, {"speech": {"voices_preload": True}},
                                                    {"speech": {"voices_loaded": "all"}, "server": {"port": "8931"}})
        self.assertEqual((st1, a1["live"], a1["restart"]), (200, ["speech.voices_loaded"], False))
        self.assertEqual((st2, a2["live"], a2["restart"]), (200, ["speech.voices_preload"], False))
        self.assertEqual((st3, a3["live"], a3["restart"]), (200, ["speech.voices_loaded"], True))   # the port waits for a start
        self.assertEqual((self.sp.voices_loaded, self.sp.voices_preload), ("all", True))
        with open(self.path, encoding="utf-8") as f:
            cfg = __import__("tomllib").loads(f.read())
        self.assertEqual((cfg["speech"]["voices_loaded"], cfg["speech"]["voices_preload"]), ("all", True))
        self.assertGreater(self.state.version, v0)   # the pages hear of it at once
        # the number lowered: the loaded voices over it are set aside at once, and the payload says so
        self.post({"speech": {"voices_loaded": "1"}})
        self.assertEqual(len(self.sp._extra), 1)
        m = self.state.voice_memory()
        self.assertEqual((m["loaded"], m["kept"], m["set_aside"], m["default"], m["preload"]), (1, 1, 1, 4, True))


class CrewState(unittest.TestCase):
    def setUp(self):
        self.dir = voices_dir(self, {"en_GB-cori-medium": (64, {"num_speakers": 1}),
                                     "en_GB-vctk-medium": (75, {"num_speakers": 3, "speaker_id_map": {"p225": 0, "p226": 1, "p227": 2}}),
                                     "en_US-plain-low": (20, {"num_speakers": 1}),
                                     "en_GB-alan-low": (50, {"num_speakers": 1}),
                                     "en_GB-broken-low": (10, {"num_speakers": 1})})
        self.sp = fake_speaker(self.dir, bad=("en_GB-broken-low",))
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.speaker = self.sp
        self.styles = dict(STYLES)
        self.state.speech = types.SimpleNamespace(lines=lambda: {"styles": self.styles}, info=lambda: None)

    def post(self, *bodies):
        """POST each body to /api/voice/crew: [(status, answer)]."""
        async def go():
            from aiohttp.test_utils import TestClient, TestServer
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for b in bodies:
                    r = await c.post("/api/voice/crew", json=b)
                    out.append((r.status, await r.json()))
            return out
        return asyncio.run(go())

    def test_off_by_default(self):
        """A new install: the crew off, the Danger switch on, every member "as the XO"; the XO is the main voice."""
        c = self.state.payload()["crew"]
        self.assertEqual((c["on"], c["danger"], c["rows"]), (False, True, {}))
        self.assertEqual(list(c["members"]), list(outrider.speech.CREW_IDS))
        self.assertEqual(c["members"]["xo"], {"name": None, "personality": None, "voice": "en_GB-cori-medium", "speaker": None, "fill": None})
        self.assertTrue(all(m == {"name": None, "personality": None, "voice": None, "speaker": None, "fill": None}
                            for r, m in c["members"].items() if r != "xo"))

    def test_storage_and_validation(self):
        """POST /api/voice/crew keeps one change at a time in meta crew (for every browser): the switches, a member (name,
        personality, voice, speaker), a row moved, ↺; refuses what the lines file or the installed voices cannot give;
        a journal re-read keeps it (live-only, like style_picks)."""
        out = self.post({"on": True}, {"danger": False},
                        {"role": "engineer", "name": "  Mira  ", "personality": "sarcastic", "voice": "en_GB-vctk-medium", "speaker": 2},
                        {"role": "navigator", "voice": "en_US-plain-low"},
                        {"role": "navigator", "personality": "sweet"},            # the voice kept
                        {"row": "trade", "role": "quartermaster"}, {"row": "fuel", "role": "engineer"},   # the default: not kept
                        {"role": "science", "voice": "en_GB-alan-low"}, {"role": "science", "reset": True},
                        {"role": "comms", "name": "Ash"}, {"role": "comms", "name": ""})
        self.assertEqual([s for s, _ in out], [200] * 11)
        c = out[-1][1]["crew"]
        self.assertEqual((c["on"], c["danger"], c["rows"]), (True, False, {"trade": "quartermaster"}))
        self.assertEqual(c["members"]["engineer"], {"name": "Mira", "personality": "sarcastic", "voice": "en_GB-vctk-medium", "speaker": 2, "fill": None})
        self.assertEqual(c["members"]["navigator"], {"name": None, "personality": "sweet", "voice": "en_US-plain-low", "speaker": None, "fill": None})
        self.assertEqual(c["members"]["science"]["voice"], None)
        self.assertEqual(c["members"]["comms"]["name"], None)
        bad = self.post({"on": "yes"}, {"row": "nope", "role": "xo"}, {"row": "fuel", "role": "chef"}, {"role": "chef"},
                        {"role": "engineer", "personality": "dry"}, {"role": "engineer", "voice": "en_GB-nope-low"},
                        {"role": "engineer", "voice": "en_GB-vctk-medium", "speaker": 3}, {"role": "engineer", "voice": "en_US-plain-low", "speaker": 0},
                        {"role": "science", "speaker": 1},                       # "as the personality" has no speaker
                        {"role": "engineer", "speaker": True}, {"role": "engineer", "name": "x" * 41}, {"role": "engineer", "name": 5},
                        {"role": "xo", "personality": "sweet"}, {"role": "xo", "voice": None}, {},
                        {"row": ["fuel"], "role": "xo"})                         # not a row's name (was a 500)
        self.assertEqual([s for s, _ in bad], [400] * 16)
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.assertEqual(self.state.crew_summary()["members"]["engineer"]["name"], "Mira")
        self.state.speaker = None
        self.assertEqual(self.post({"role": "engineer", "voice": "en_GB-alan-low"})[0][0], 503)   # no Piper: no voice to pick
        self.assertEqual(self.post({"role": "engineer", "personality": "sweet"})[0][0], 200)      # its lines still

    def test_the_xo_is_the_main_voice(self):
        """The XO row and the main voice are one setting: a voice (and person) given to the XO switches the main voice as
        POST /api/voice does; only the XO's name is kept in the crew."""
        used, picked = [], []
        self.sp.use = lambda name: used.append(name) or True
        real = self.sp.set_speaker
        self.sp.set_speaker = lambda name, sid: picked.append((name, sid)) or real(name, sid)
        out = self.post({"role": "xo", "voice": "en_GB-vctk-medium", "speaker": 1, "name": "Kit"}, {"role": "xo", "speaker": None})
        self.assertEqual([s for s, _ in out], [200, 200])
        self.assertEqual((used, picked), (["en_GB-vctk-medium"], [("en_GB-vctk-medium", 1), ("en_GB-cori-medium", None)]))
        self.assertEqual(ed_outrider.meta_get(self.db, "crew")["members"]["xo"],
                         {"name": "Kit", "personality": None, "voice": None, "speaker": None})

    def test_the_xo_fills_in(self):
        """A member who cannot speak is said by the XO (the payload's `fill`, why), for each kind: its voice not installed,
        failing to load, a speaker the voice lacks, a personality the lines file no longer has; logged once per voice (or
        personality) and reason while the crew is on, never while it is off; the XO itself never fills in."""
        crew = {"on": False, "members": {
            "navigator": {"voice": "en_GB-gone-medium"}, "science": {"voice": "en_GB-broken-low"},
            "engineer": {"voice": "en_GB-vctk-medium", "speaker": 7}, "quartermaster": {"personality": "dry"},
            "comms": {"voice": "en_GB-gone-medium"}, "mining": {"voice": "en_GB-vctk-medium", "speaker": 2, "personality": "sweet"}}}
        ed_outrider.meta_set(self.db, "crew", crew)
        with contextlib.redirect_stderr(io.StringIO()):
            self.sp.extra_voice("en_GB-broken-low")   # tried once: it failed to load
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            off = self.state.crew_summary()
            ed_outrider.meta_set(self.db, "crew", dict(crew, on=True))
            on = self.state.crew_summary()
            self.state.crew_summary()   # again: nothing logged twice
        fills = {r: m["fill"] for r, m in on["members"].items()}
        self.assertEqual(fills, {"xo": None, "navigator": "voice en_GB-gone-medium not installed",
                                 "science": "voice en_GB-broken-low failed to load", "engineer": "voice en_GB-vctk-medium has no speaker 7",
                                 "quartermaster": "personality dry is not in the lines file",
                                 "comms": "voice en_GB-gone-medium not installed", "exobiologist": None, "mining": None, "tactical": None})
        self.assertEqual({r: m["fill"] for r, m in off["members"].items()}, fills)   # said off too, just not logged
        self.assertEqual(log.getvalue().splitlines(), [
            "crew: Navigator's voice en_GB-gone-medium not installed: the XO speaks for it",   # Comms' same voice: once
            "crew: Science Officer's voice en_GB-broken-low failed to load: the XO speaks for it",
            "crew: Engineer's voice en_GB-vctk-medium has no speaker 7: the XO speaks for it",
            "crew: Quartermaster's personality dry is not in the lines file: the XO speaks for it"])

    def test_a_voice_that_will_not_load_never_lends_its_person_number(self):
        """Review 2026-10-23 S6-B2: a personality's voice that would not load fell back to the main voice with the
        personality's speaker number, which on a several-person main voice is a stranger; it is the main voice's own pick."""
        sp = fake_speaker(self.dir, main="en_GB-vctk-medium", bad=("en_GB-broken-low",))
        with contextlib.redirect_stderr(io.StringIO()):
            got = sp.say("Hello.", voice="en_GB-broken-low", speaker=2)[44:].decode()
        own = sp.say("Hello.")[44:].decode()
        self.assertTrue(got.startswith("en_GB-vctk-medium:"), got)
        self.assertEqual(got, own)                                        # the main voice's own person, not person 2
        self.assertNotIn('"speaker_id": 2', got)

    def test_a_line_said_by_the_xo_on_the_server(self):
        """A crew member's line (the page sends the role with its voice): said in that voice and person when it can be,
        else by the XO, in the main voice and its own person (never that number of another voice), the log saying so
        once; a line without a role keeps S40's way (a voice gone: the main voice)."""
        async def go():
            from aiohttp.test_utils import TestClient, TestServer
            out = []
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                for q in ({"voice": "en_GB-vctk-medium", "speaker": "2", "role": "engineer"},
                          {"voice": "en_GB-gone-medium", "speaker": "2", "role": "engineer"},
                          {"voice": "en_GB-broken-low", "role": "science"},
                          {"voice": "en_GB-vctk-medium", "speaker": "9", "role": "engineer"},
                          {"voice": "en_GB-vctk-medium", "speaker": "9"},           # no role: the voice's own pick (S40)
                          {"voice": "en_GB-vctk-medium", "speaker": "1", "role": "xo"},
                          {"voice": "not a voice " * 50, "role": "engineer"}):       # any text a caller sends: not logged
                    r = await c.get("/api/say", params=dict(q, text=f"Line {len(out)}."))
                    out.append((await r.read())[44:].decode())
            return out
        log = io.StringIO()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(io.StringIO()):
            got = asyncio.run(go())
        self.assertEqual(got, ['en_GB-vctk-medium:{"speaker_id": 2}', "en_GB-cori-medium:None", "en_GB-cori-medium:None",
                               "en_GB-cori-medium:None", "en_GB-vctk-medium:None", 'en_GB-vctk-medium:{"speaker_id": 1}',
                               "en_GB-cori-medium:None"])
        self.assertEqual(log.getvalue().splitlines(), [
            "crew: Engineer's voice en_GB-gone-medium not installed: the XO speaks for it",
            "crew: Science Officer's voice en_GB-broken-low failed to load: the XO speaks for it",
            "crew: Engineer's voice en_GB-vctk-medium has no speaker 9: the XO speaks for it"])

    def test_voices_in_use_and_memory(self):
        """The voices besides the main one in use (the personalities', the picks, the crew's while it is on; never the
        main voice) and their memory: each installed .onnx × 1.6, the number kept by voices_loaded and the memory of
        that many of the largest, how many are set aside."""
        ed_outrider.meta_set(self.db, "style_picks", {"sweet": {"voice": "en_GB-cori-medium", "speaker": None}})   # the main voice
        ed_outrider.meta_set(self.db, "crew", {"on": False, "members": {"engineer": {"voice": "en_GB-vctk-medium"},
                                                                       "navigator": {"voice": "en_GB-alan-low"},
                                                                       "xo": {"voice": "en_GB-alan-low"},       # never kept for the XO
                                                                       "comms": {"voice": "en_GB-gone-medium"}}})
        self.assertEqual(self.state.voices_in_use(), {"en_US-plain-low"})
        ed_outrider.meta_set(self.db, "crew", dict(ed_outrider.meta_get(self.db, "crew"), on=True))
        self.assertEqual(self.state.voices_in_use(), {"en_US-plain-low", "en_GB-vctk-medium", "en_GB-alan-low", "en_GB-gone-medium"})
        mb = lambda n: round(n * 1.6 / 1e6)   # noqa: E731
        with contextlib.redirect_stdout(io.StringIO()):   # Comms' voice not installed: logged
            m = self.state.payload()["voice_memory"]
        self.assertEqual(m["voices"], [{"voice": "en_GB-alan-low", "mb": mb(50)}, {"voice": "en_GB-vctk-medium", "mb": mb(75)},
                                       {"voice": "en_US-plain-low", "mb": mb(20)}])   # not installed: never loads, not counted
        self.assertEqual({k: m[k] for k in ("count", "loaded", "kept", "set_aside", "preload", "on_server")},
                         {"count": 3, "loaded": None, "kept": 3, "set_aside": 0, "preload": False, "on_server": False})
        self.sp.voices_loaded = 2
        m = self.state.voice_memory()
        self.assertEqual((m["kept"], m["kept_mb"], m["set_aside"]), (2, mb(75) + mb(50), 1))   # the two largest
        self.sp.voices_loaded = "all"
        self.assertEqual(self.state.voice_memory()["kept"], 3)
        self.state.speaker = None
        self.assertIsNone(self.state.voice_memory())   # no Piper: nothing is loaded


class VoicesLoaded(unittest.TestCase):
    def test_estimate(self):
        """voice_memory_estimate: the installed .onnx's size × 1.6 in MB; a voice not installed (or a path) left out."""
        d = voices_dir(self, {"en_GB-cori-medium": (64_000_000, {}), "en_GB-cori-high": (114_000_000, {})})
        self.assertEqual(outrider.tts.voice_memory_estimate(["en_GB-cori-medium", "en_GB-cori-high", "en_GB-nope-low", "../x", None], d),
                         {"en_GB-cori-high": 182, "en_GB-cori-medium": 102})

    def test_slots(self):
        """[speech] voices_loaded: a number is exactly that many, whatever is in use; "all" no limit; unset the voices in
        use up to 4; never under 1."""
        s = outrider.tts.loaded_slots
        self.assertEqual([s(None, n) for n in (0, 1, 3, 4, 9)], [1, 1, 3, 4, 4])
        self.assertEqual([s(6, 2), s(1, 9), s("all", 9), s(0, 2), s(True, 2)], [6, 1, None, 2, 2])

    def test_lru(self):
        """Never more voices loaded beside the main one than chosen; the least recently used set aside first; the main
        voice never among them (loaded on its own: a pick of the main voice takes no place and is never set aside); "all"
        keeps every one."""
        names = [f"en_GB-v{i}-low" for i in range(6)]
        d = voices_dir(self, {n: (10, {}) for n in names + ["en_GB-main-low"]})
        sp = fake_speaker(d, main="en_GB-main-low")
        sp.voices_loaded = 2
        sp.size_extra(names)
        for n in names + ["en_GB-main-low"]:
            sp.say("Hello.", voice=n)
            self.assertLessEqual(len(sp._extra), 2)
        self.assertEqual(list(sp._extra), names[-2:])
        self.assertEqual(sp.say("Hi.")[44:], b"en_GB-main-low:None")   # the main voice still speaks
        sp._extra["en_GB-main-low"] = (Voice("en_GB-main-low"), None)   # e.g. a personality voice that became the main one
        sp.size_extra(names)
        self.assertNotIn("en_GB-main-low", sp._extra)
        sp.voices_loaded = None   # unset: the voices in use (6), up to 4
        for n in names:
            sp.say("Again.", voice=n)
        self.assertEqual(len(sp._extra), 4)
        sp.size_extra(names[:1])  # fewer in use now: the extra ones are set aside at once
        self.assertEqual(list(sp._extra), names[-1:])
        sp.voices_loaded = "all"
        sp.size_extra(names)
        for n in names:
            sp.say("All.", voice=n)
        self.assertEqual(sorted(sp._extra), sorted(names))

    def test_preload(self):
        """voices_preload: once the main voice is ready, the voices in use load one at a time, up to the number kept, the
        main voice, one not installed and one that would not load left out; nothing before the main voice is ready."""
        names = ["en_GB-a-low", "en_GB-b-low", "en_GB-c-low", "en_GB-bad-low"]
        d = voices_dir(self, {n: (10, {}) for n in names + ["en_GB-main-low"]})
        sp = fake_speaker(d, main="en_GB-main-low", bad=("en_GB-bad-low",))
        sp.voices_loaded = 2
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sp._preload(sorted(names + ["en_GB-main-low", "en_GB-gone-low"]), wait=0), ["en_GB-a-low", "en_GB-b-low"])
        self.assertEqual((sp.loads, list(sp._extra)), (["en_GB-a-low", "en_GB-b-low"], ["en_GB-a-low", "en_GB-b-low"]))
        self.assertIn("loaded at start ([speech] voices_preload): en_GB-a-low, en_GB-b-low", out.getvalue())
        sp2 = fake_speaker(d, main="en_GB-main-low")
        sp2._voice = None   # still loading its main voice
        self.assertEqual(sp2._preload(names, wait=0.05, step=0.01), [])
        self.assertEqual(sp2.loads, [])
        sp2.PiperVoice = None
        self.assertIsNone(sp2.preload(names))   # no Piper: no thread

    def test_config_keys(self):
        """[speech] voices_loaded (a number, "all", or unset) and voices_preload: read, written back by --write-config with
        their help, a pick-list in Server settings, in the example config and the guide's Settings page; a value it cannot
        read is 4, said."""
        import argparse
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        read = lambda spk: ed_outrider.settings_from({"speech": spk}, args, None, ([], []))   # noqa: E731
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = [read(spk)["voices_loaded"] for spk in ({}, {"voices_loaded": "all"}, {"voices_loaded": 6}, {"voices_loaded": "12"},
                                                           {"voices_loaded": 0}, {"voices_loaded": "lots"}, {"voices_loaded": True})]
            pre = [read(spk)["voices_preload"] for spk in ({}, {"voices_preload": True}, {"voices_preload": "yes"})]
        self.assertEqual(got, [None, "all", 6, 12, 4, 4, 4])
        self.assertEqual(pre, [False, True, False])
        self.assertIn("voices_loaded = 'lots' is not valid here, using 4", err.getvalue())
        import outrider.config_edit as ce
        for spk in ({}, {"voices_loaded": "all", "voices_preload": True}, {"voices_loaded": 6}):
            with contextlib.redirect_stderr(io.StringIO()):
                st = read(spk)
            keys = {k["key"]: k for s in ce.entries(ed_outrider.config_text(st), ed_outrider.config_choices())
                    if s["section"] == "speech" for k in s["keys"]}
            self.assertEqual(keys["voices_loaded"]["kind"], "choices")
            self.assertEqual(keys["voices_loaded"]["value"], str(st["voices_loaded"] or 4))
            self.assertEqual(keys["voices_loaded"]["set"], st["voices_loaded"] is not None)
            self.assertTrue(keys["voices_loaded"]["help"] and keys["voices_preload"]["help"])
            import tomllib
            back = tomllib.loads(ed_outrider.config_text(st))["speech"]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(read(back)["voices_loaded"], st["voices_loaded"])
        self.assertIn("all", ed_outrider.config_choices()[("speech", "voices_loaded")])
        root = os.path.dirname(ed_outrider.STATIC_DIR)
        for doc in ("ed_outrider.toml.example", os.path.join("docs", "guide", "settings.md")):
            with open(os.path.join(root, doc), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("voices_loaded", text, doc)
            self.assertIn("voices_preload", text, doc)


class CrewLines(unittest.TestCase):
    """Crew batch 3: lines naming another crew member ({engineer}...): the placeholders and their words, said only with the
    crew on and never by the member they name (the checks on the default table), the ban guard, the shipped lines, "XO"."""

    def test_placeholders(self):
        """One per role, the role's id; the plan's words (Comms and Tactical without an article, "the Engineer" not "the
        Chief Engineer"); optional in every alert; none clashes with an alert's own; served with the roles."""
        S = outrider.speech
        self.assertEqual(set(S.CREW_WORDS), set(S.CREW_IDS))
        self.assertEqual(set(S.CREW_SAMPLES), set(S.CREW_IDS))
        self.assertEqual([S.CREW_WORDS[r] for r in ("engineer", "comms", "tactical", "xo", "science", "mining")],
                         ["the Engineer", "Comms", "Tactical", "the XO", "the Science Officer", "the Mining Officer"])
        for key in S.KEYS:
            self.assertEqual(set(S.PLACEHOLDER.findall(S.KEYS[key])) & set(S.CREW_IDS), set(), key)
            self.assertLessEqual(set(S.CREW_IDS), S.fills(key), key)
        info = {r["id"]: r for r in S.crew_roles_info()}
        self.assertEqual((info["engineer"]["words"], info["engineer"]["sample"]), ("the Engineer", "Mira"))

    def test_fill(self):
        """The name when one is set, in every position; else the words, capitalised at a sentence's start (the line's,
        or after ". ", "! ", "? ", "... " as filled: a {text} ending in a full stop counts)."""
        fill = outrider.speech.fill
        line = "{engineer} wants a star. Ask {engineer}! {navigator}? Fine... {comms} and {tactical}, then {xo}."
        self.assertEqual(fill(line, {}), "The Engineer wants a star. Ask the Engineer! The Navigator? Fine... Comms and "
                                         "Tactical, then the XO.")
        self.assertEqual(fill(line, {}, crew={"engineer": "Mira", "navigator": " ", "xo": "Kade"}),
                         "Mira wants a star. Ask Mira! The Navigator? Fine... Comms and Tactical, then Kade.")
        self.assertEqual(fill("{text} {engineer} agrees.", {"text": "Known. 4 bodies."}), "Known. 4 bodies. The Engineer agrees.")
        self.assertEqual(fill("{text} {engineer} agrees.", {"text": "4 bodies"}), "4 bodies the Engineer agrees.")
        self.assertEqual(fill("{name}, {exobiologist}'s turn.", {}, "Boss"), "Boss, the Exobiologist's turn.")

    def test_who_says_a_key(self):
        """The default table: a key's rows' member, Tactical for a danger key, the XO for speech on."""
        sp = outrider.speech.crew_speakers
        self.assertEqual([sp("fuel_low"), sp("tank_full"), sp("speech_on"), sp("game_start"), sp("find_body"),
                          sp("carrier_departs"), sp("carrier_arrived")],
                         [{"engineer", "tactical"}, {"engineer"}, {"xo"}, {"comms"}, {"exobiologist"},
                          {"quartermaster", "tactical"}, {"quartermaster"}])

    def test_row_keys_and_danger_in_step_with_the_page(self):
        """outrider.speech.ROW_KEYS and DANGER (who says a key, for the checks) are page.js ROW_KEYS and DANGER."""
        with open(PAGE_JS, encoding="utf-8") as f:
            js = f.read()
        start = js.index("const ROW_KEYS = {")
        text = js[start:js.index("};", start)]
        page = {k: tuple(re.findall(r'"(\w+)"', v)) for k, v in re.findall(r'(\w+): (\[[^\]]*\])', text)}
        self.assertEqual(page, outrider.speech.ROW_KEYS)
        danger = tuple(re.findall(r'"(\w+)"', js[js.index("const DANGER = new Set("):].split(")", 1)[0]))
        self.assertEqual(danger, outrider.speech.DANGER)

    def test_checks(self):
        """A line naming the member who says its alert (the row's, Tactical for a danger line, the XO for speech on) is a
        problem; naming another is fine; a list whose every line names a crew member is a problem (nothing with it off)."""
        doc = {"styles": {"business": "B"}, "lines": {
            "fuel_low": {"business": ["Fuel low.", "Ask {engineer}.", "Tell {tactical}.", "Ask {navigator}."]},
            "tank_full": {"business": ["Full.", "Tell {tactical}.", "Tell {engineer}."]},
            "speech_on": {"business": ["On.", "{xo} here."]},
            "sold": {"business": ["{science} says hi. {still}"]}}}
        probs = outrider.speech.check(doc)
        self.assertEqual(len(probs), 5, probs)
        for want in ('"fuel_low" / "business": {engineer} names the crew member', '"fuel_low" / "business": {tactical} names',
                     '"tank_full" / "business": {engineer} names', '"speech_on" / "business": {xo} names',
                     '"sold" / "business": every line names a crew member'):
            self.assertTrue(any(p.startswith(want) for p in probs), want)

    def test_a_ban_leaves_a_plain_line(self):
        """The last line naming no crew member cannot be banned (with the crew off the alert would have none); a list
        whose plain lines are all banned by hand is used whole."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "speech.json")
            with open(path, "w") as f:
                json.dump({"styles": {"business": "B"}, "lines": {"hull": {"business": [
                    "Hull {pct}.", "Hull {pct}, ask {navigator}.", "Hull {pct}, ask {quartermaster}."]}}}, f)
            sl = outrider.speech.SpeechLines(path)
            self.assertEqual(sl.set_ban("hull", "Hull {pct}.")[0], 409)
            self.assertEqual(sl.set_ban("hull", "Hull {pct}, ask {navigator}.")[0], 200)
            with open(os.path.join(d, "speech_banned.json"), "w") as f:
                json.dump({"hull": ["Hull {pct}."]}, f)
            got = sl.lines()
            self.assertEqual(len(got["lines"]["hull"]["business"]), 3)
            self.assertEqual(got["banned_whole"], ["hull/business"])

    def test_shipped_lines(self):
        """resources/speech.json: every list keeps its plain lines (the shorter alerts' as many as before), and every
        personality list has crew lines for at least 25 alerts, none a vocative ("The Navigator, plot...")."""
        root = os.path.dirname(ed_outrider.STATIC_DIR)
        with open(os.path.join(root, "resources", "speech.json"), encoding="utf-8") as f:
            doc = json.load(f)
        S = outrider.speech
        self.assertEqual(S.check(doc), [])
        short = {"mapped_before": 12, "bio_tag_near": 15, "autotarget_nothing": 15, "wrong_target": 15,
                 "docking_granted": 15, "docking_denied": 15, "ring_found_many": 30,   # several ringed bodies at once: rarer
                 # mining's short warnings and call-outs (2026-10-18): 15 a list
                 "limpets_none": 15, "prospect_hit": 15, "motherlode": 15, "limpets_low": 15, "hold_nearly_full": 15,
                 "hold_full": 15, "old_data": 15}   # old_data (#11): a clause after the briefing
        crew_keys, said = {}, []
        for key, entry in doc["lines"].items():
            for lst, vs in entry.items():
                if lst == "when":
                    continue
                plain = [v for v in vs if not S.crew_named(v)]
                want = 12 if key == "autotarget_nothing" and lst.endswith("_profane") else short.get(key, 50)
                if key in ("fuel_short", "fuel_last_scoop") and lst != "business":
                    want = 15
                if key in S.CHATTER_KEYS:   # space chatter's own sizes (2026-10-17): 60 alone in space, 30 on a planet,
                    want = {"chatter_space": 55, "chatter_planet_landed": 27, "chatter_planet_orbit": 27,   # 20 last words,
                            "chatter_react": 18}.get(key, 11)                                              # a dozen asks
                self.assertGreaterEqual(len(plain), want, f"{key}/{lst}")
                crew = [v for v in vs if S.crew_named(v)]
                if crew:
                    crew_keys.setdefault(lst, set()).add(key)
                said += crew
        self.assertEqual(set(crew_keys), {"business", "sarcastic", "sarcastic_profane", "sweet", "sweet_profane"})
        for lst, keys in crew_keys.items():
            self.assertGreaterEqual(len(keys), 25, lst)
        self.assertEqual(len(said), len(set(said)))
        vocative = re.compile(r"(^|[.!?] )\{(%s)\}," % "|".join(S.CREW_IDS))
        self.assertEqual([v for v in said if vocative.search(v)], [])

    def test_xo_said_ex_oh(self):
        """"XO" has a shipped respelling ("ex-OH"): espeak alone reads it "zo"."""
        import outrider.pronounce as P
        with tempfile.TemporaryDirectory() as d:
            t = P.Table(P.SHIPPED, os.path.join(d, "none.json"))
            self.assertEqual(t.words()["xo"], "ex-OH")
            P._cache.clear()
            self.addCleanup(P._cache.clear)
            fake = lambda v, text: {"ex": "ɛks", "oh": "oʊ"}.get(text, text)   # noqa: E731
            self.assertEqual(P.apply("Ask the XO.", "en-us", t, fake), "Ask the [[ɛksˈoʊ.]]")


if __name__ == "__main__":
    unittest.main()
