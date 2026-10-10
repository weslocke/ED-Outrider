"""Unit tests: Configuration, the command line, request security, backups and the test tooling's own safety.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import argparse
import json
import os
import time
import unittest
import unittest.mock
import sqlite3

from support import (  # also puts the repository root on sys.path
    _FakeResponse, guard_status, make_controls, org, scan, user_docs,
)
import outrider.bio  # noqa: E402
import ed_outrider  # noqa: E402
import outrider.unsold  # noqa: E402
import outrider.speech  # noqa: E402


class Config(unittest.TestCase):
    def test_docs_say_when_legacy_is_auto_detected(self):   # F18: the code's rule, in every place that describes it
        import subprocess, sys
        with open(os.path.join(os.path.dirname(ed_outrider.__file__), "ed_outrider.toml.example"), encoding="utf-8") as f:
            self.assertIn("only while live is missing too", f.read())
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({"journals": {"live": ["/mine"]}}, args, None, ([], ["/old"]))
        self.assertEqual(st["legacy"], [])                    # the rule itself, unchanged
        self.assertIn("auto-detected only when live is absent too", ed_outrider.config_text(st))
        out = subprocess.run([sys.executable, ed_outrider.__file__, "--help"], capture_output=True, text=True, timeout=60)
        self.assertIn("[journals] live names the live", " ".join(out.stdout.split()))

    def test_listen_problem_names_the_cause(self):   # F20
        import socket
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            self.assertIn("already in use", ed_outrider.listen_problem("127.0.0.1", port))
        for host in ("10.255.255.254", "no.such.host.invalid"):   # not this machine's address; a name that does not resolve
            msg = ed_outrider.listen_problem(host, port)
            self.assertNotIn("already in use", msg, host)
            self.assertIn(f"cannot listen on {host}:{port}", msg)
            self.assertIn("[server] host", msg)
        self.assertIsNone(ed_outrider.listen_problem("127.0.0.1", port))   # free again

    def test_old_layout_moves_into_data(self):   # F22: temp folders only, never the repository's own
        import contextlib, io, tempfile
        with tempfile.TemporaryDirectory() as root:
            data = os.path.join(root, "data")
            db = ed_outrider.open_db(os.path.join(root, "ed_outrider.sqlite"))
            ed_outrider.meta_set(db, "marker", "old rows")
            db.commit()
            db.close()
            for n in ("browser_defaults.json", "speech_banned.json"):
                with open(os.path.join(root, n), "w") as f:
                    f.write("{}")
            os.makedirs(os.path.join(root, "piper-voices"))
            lines = []
            moved = ed_outrider.migrate_old_layout(os.path.join(data, "ed_outrider.sqlite"), root, data, log=lines.append)
            self.assertEqual(moved, ["ed_outrider.sqlite", "browser_defaults.json", "speech_banned.json", "piper-voices"])
            self.assertEqual(len(lines), 1)
            db = ed_outrider.open_db(os.path.join(data, "ed_outrider.sqlite"))
            try:
                self.assertEqual(ed_outrider.meta_get(db, "marker"), "old rows")   # the old rows, not a fresh file
            finally:
                db.close()
            # once moved (or with a database already in data/), nothing more happens
            self.assertEqual(ed_outrider.migrate_old_layout(os.path.join(data, "ed_outrider.sqlite"), root, data, log=lines.append), [])
            # a database somewhere else (--db) is never touched
            self.assertEqual(ed_outrider.migrate_old_layout(os.path.join(root, "other", "x.sqlite"), root, data), [])
            # an old config's speech_file = "speech.json" finds the moved file in resources/
            res = os.path.join(root, "resources")
            os.makedirs(res)
            with open(os.path.join(res, "speech.json"), "w") as f:
                f.write("{}")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                got = ed_outrider.speech_file_path("speech.json", root, res)
            self.assertEqual(got, os.path.join(res, "speech.json"))
            self.assertIn("moved to resources/", err.getvalue())
            self.assertEqual(ed_outrider.speech_file_path("mine.json", root, res), os.path.join(root, "mine.json"))

    def test_readme_says_what_plain_python_finds(self):   # F47: aiohttp is imported before any .venv lookup
        root = os.path.dirname(ed_outrider.__file__)
        with open(os.path.join(root, "ed_outrider.py"), encoding="utf-8") as f:
            head = f.read().split("from aiohttp import", 1)[0]
        self.assertNotIn(".venv", head.split('"""', 2)[-1])   # no .venv on sys.path before the aiohttp import
        readme = " ".join(user_docs().split())
        self.assertIn("aiohttp must then be installed for that `python3` too", readme)
        self.assertNotIn("is found even when you start Outrider with plain", readme)

    def test_codex_interesting(self):   # a codex find as a reason to stay: on unless the config says otherwise
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        self.assertTrue(ed_outrider.settings_from({}, args, None, ([], []))["codex_interesting"])
        st = ed_outrider.settings_from({"defaults": {"codex_interesting": False}}, args, None, ([], []))
        self.assertFalse(st["codex_interesting"])
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["defaults"]["codex_interesting"], False)

    def test_precedence_flag_env_file_detect(self):
        cfg = {"journals": {"live": ["/from/file"]}, "server": {"port": 9000}, "defaults": {"bio_min": 5}}
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from(cfg, args, None, (["/detected"], ["/detected-legacy"]))
        self.assertEqual((st["live"], st["legacy"], st["port"], st["bio_min"]), (["/from/file"], [], 9000, 5))
        st = ed_outrider.settings_from(cfg, args, "/from/env", (["/detected"], []))
        self.assertEqual(st["live"], ["/from/env"])
        args.journals, args.port = ["/from/flag"], 7000
        st = ed_outrider.settings_from(cfg, args, "/from/env", (["/detected"], []))
        self.assertEqual((st["live"], st["port"]), (["/from/flag"], 7000))
        st = ed_outrider.settings_from({}, argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None),
                                     None, (["/detected"], ["/detected-legacy"]))
        self.assertEqual((st["live"], st["legacy"], st["port"], st["host"]), (["/detected"], ["/detected-legacy"], 8025, "127.0.0.1"))

    def test_config_text_round_trips(self):
        import tomllib
        args = argparse.Namespace(journals=["/a b/c"], legacy=None, host="0.0.0.0", port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        back = tomllib.loads(ed_outrider.config_text(st))
        self.assertEqual(back["journals"]["live"], ["/a b/c"])
        self.assertEqual(back["server"]["host"], "0.0.0.0")
        self.assertEqual(back["defaults"]["unsold_warn"], 50_000_000)

    def test_speech_danger_business(self):   # P10(a): on unless the config turns it off, and written back
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertIs(st["speech_danger_business"], True)
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["defaults"]["speech_danger_business"], True)
        st = ed_outrider.settings_from({"defaults": {"speech_danger_business": False}}, args, None, ([], []))
        self.assertIs(st["speech_danger_business"], False)
        self.assertIs(tomllib.loads(ed_outrider.config_text(st))["defaults"]["speech_danger_business"], False)


class ConfigValidation(unittest.TestCase):
    """Batch 1 (2026-09-30b): a bad config value is reported on stderr and the default kept."""

    def settings(self, cfg, **flags):
        import contextlib, io
        args = argparse.Namespace(**dict(dict(journals=None, legacy=None, host=None, port=None, radius=None, db=None),
                                         **flags))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            st = ed_outrider.settings_from(cfg, args, None, ([], []))
        return st, err.getvalue()

    def test_quoted_false_is_not_true(self):   # G2.1: bool("false") is True; it must not switch auto honk on
        st, err = self.settings({"autohonk": {"enabled": "false"}})
        self.assertIs(st["autohonk"]["enabled"], False)
        self.assertIn("[autohonk] enabled = 'false' is not valid here, using False", err)

    def test_every_boolean_is_strict(self):   # G2.1
        st, err = self.settings({"defaults": {"sounds": "false", "body_max_value_include_bonus": "no",
                                              "speech_profanity": "yes", "speech_danger_business": "off",
                                              "speak_bio_signals": 2, "speak_geo_signals": "false"},
                                 "autohonk": {"skip_honked": "no", "announce": []}})
        self.assertEqual((st["sounds"], st["max_include_bonus"], st["speech_profanity"], st["speech_danger_business"],
                          st["speak_bio_signals"], st["speak_geo_signals"], st["autohonk"]["skip_honked"],
                          st["autohonk"]["announce"]),
                         (ed_outrider.SOUNDS_DEFAULT, ed_outrider.MAX_INCLUDE_BONUS, ed_outrider.SPEECH_PROFANITY,
                          ed_outrider.SPEECH_DANGER_BUSINESS, ed_outrider.SPEAK_BIO_SIGNALS,
                          ed_outrider.SPEAK_GEO_SIGNALS, ed_outrider.AUTOHONK["skip_honked"],
                          ed_outrider.AUTOHONK["announce"]))
        self.assertEqual(err.count("is not valid here"), 8)

    def test_real_booleans_and_0_1_pass(self):   # G2.1
        st, err = self.settings({"defaults": {"speech_profanity": True, "sounds": 0}, "autohonk": {"enabled": 1}})
        self.assertEqual((st["speech_profanity"], st["sounds"], st["autohonk"]["enabled"]), (True, False, True))
        self.assertEqual(err, "")

    def test_radius_at_least_1(self):   # F1
        for bad in (0, -10):
            st, err = self.settings({"server": {"radius": bad}})
            self.assertEqual(st["radius"], 25.0)
            self.assertIn("[server] radius", err)
        self.assertEqual(self.settings({"server": {"radius": 30}})[0]["radius"], 30.0)
        self.assertEqual(self.settings({}, radius=0.0)[0]["radius"], 1.0)   # the --radius flag is clamped

    def test_host_must_be_a_string(self):   # F2
        st, err = self.settings({"server": {"host": 0}})
        self.assertEqual(st["host"], "127.0.0.1")
        self.assertIn("[server] host = 0 is not valid here", err)
        self.assertEqual(self.settings({"server": {"host": "0.0.0.0"}})[0]["host"], "0.0.0.0")

    def test_speech_styles(self):   # G2.3
        st, err = self.settings({"defaults": {"speech_styles": "sarcastic"}})
        self.assertEqual((st["speech_styles"], err), (["sarcastic"], ""))
        st, err = self.settings({"defaults": {"speech_styles": 3}})
        self.assertEqual(st["speech_styles"], list(ed_outrider.SPEECH_STYLES))
        self.assertIn("[defaults] speech_styles = 3 must be a list", err)

    def test_high_gravity_positive(self):   # G2.4: the page reads 0 as unset (2 g), so the server keeps it above 0
        self.assertEqual(self.settings({"defaults": {"high_gravity": 0}})[0]["high_gravity"], 0.1)
        self.assertEqual(self.settings({"defaults": {"high_gravity": 1.5}})[0]["high_gravity"], 1.5)


class ConfigRobustness(unittest.TestCase):
    """Batch 0.3: config mistakes are reported and survived, not tracebacks or silent nonsense."""

    ARGS = dict(journals=None, legacy=None, host=None, port=None, radius=None, db=None)

    def settings(self, cfg):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            st = ed_outrider.settings_from(cfg, argparse.Namespace(**self.ARGS), None, ([], []))
        return st, err.getvalue()

    def test_single_folder_string(self):
        st, _ = self.settings({"journals": {"live": "C:/Games/Elite Dangerous"}})
        self.assertEqual(st["live"], ["C:/Games/Elite Dangerous"])

    def test_wrong_types_fall_back_with_a_message(self):
        st, err = self.settings({"server": {"port": "8025x", "radius": "far", "radius_choices": 25},
                                 "defaults": {"bio_min": "ten million"}})
        self.assertEqual((st["port"], st["radius"], st["bio_min"]), (8025, 25.0, ed_outrider.BIO_MIN))
        self.assertEqual(st["radius_choices"], [20.0, 25.0, 30.0, 40.0, 50.0])
        for key in ("port", "radius", "radius_choices", "bio_min"):
            self.assertIn(key, err)

    def test_quoted_number_still_works(self):
        st, err = self.settings({"server": {"port": "9000"}})
        self.assertEqual((st["port"], err), (9000, ""))


class RadiusChoices(unittest.TestCase):
    def test_radius_choices(self):
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual(st["radius_choices"], [20.0, 25.0, 30.0, 40.0, 50.0])
        st = ed_outrider.settings_from({"server": {"radius_choices": [80, 25, 25, 0, 50]}}, args, None, ([], []))
        self.assertEqual(st["radius_choices"], [25.0, 50.0, 80.0])   # sorted, de-duplicated, zero dropped
        import tomllib
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["server"]["radius_choices"], [25, 50, 80])


class Batch0Security(unittest.TestCase):
    """Batch 0: Host / Origin checks, the backup gap, voice names, and auto honk's switch-off and test races."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.addCleanup(self.db.close)

    guard = guard_status

    def test_allowed_hosts(self):
        a = ed_outrider.allowed_hosts("127.0.0.1", 8025, own=lambda: {"should-not-appear"})
        self.assertEqual(a, {"127.0.0.1:8025", "localhost:8025", "[::1]:8025"})
        a = ed_outrider.allowed_hosts("0.0.0.0", 8025, ["phone.lan", "10.0.0.2:9000", "fe80::1", "[::2]:8025"],
                                      own=lambda: {"MyPC", "192.168.1.5"})
        self.assertTrue({"mypc:8025", "192.168.1.5:8025", "phone.lan:8025", "10.0.0.2:9000", "[fe80::1]:8025",
                         "[::2]:8025", "localhost:8025"} <= a, a)
        self.assertIn("192.168.1.5:8025", ed_outrider.allowed_hosts("192.168.1.5", 8025))
        self.assertIn("localhost", ed_outrider.allowed_hosts("127.0.0.1", 80))   # the default port is left out of Host
        # the config key: a list (or one string) of names, carried through --write-config
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({"server": {"allowed_hosts": ["phone.lan", " "]}}, args, None, ([], []))
        self.assertEqual(st["allowed_hosts"], ["phone.lan"])
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["server"]["allowed_hosts"], ["phone.lan"])
        self.assertEqual(ed_outrider.settings_from({"server": {"allowed_hosts": "pc"}}, args, None, ([], []))["allowed_hosts"], ["pc"])

    def test_origin_check(self):
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", origin="http://evil.example"), 403)   # another site
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", origin="null"), 403)                 # a sandboxed frame
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", origin="http://localhost:8025"), 403)  # not this origin
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", origin="http://127.0.0.1:8025"), 200)  # the page itself
        self.assertEqual(self.guard("POST", "localhost:8025", origin="http://localhost:8025"), 200)
        self.assertEqual(self.guard("POST", "127.0.0.1:8025"), 200)                                  # curl: no Origin
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", site="cross-site"), 403)
        self.assertEqual(self.guard("POST", "127.0.0.1:8025", origin="http://127.0.0.1:8025", site="same-origin"), 200)
        self.assertEqual(self.guard("GET", "127.0.0.1:8025", origin="http://evil.example"), 200)     # reads: the Host check

    def test_host_check(self):
        self.assertEqual(self.guard("GET", "attacker.example:8025"), 403)   # DNS rebinding
        self.assertEqual(self.guard("GET", "mypc.lan:8025"), 403)          # an unknown name
        self.assertEqual(self.guard("GET", ""), 403)
        # F39: any IP address (DNS rebinding needs a name): a LAN address own_addresses() missed behind a VPN
        for ip in ("192.168.1.208:8025", "10.10.10.208:8025", "[fe80::1]:8025", "0.0.0.0:8025", "127.0.0.1:9999"):
            self.assertEqual(self.guard("GET", ip), 200, ip)
        self.assertFalse(ed_outrider.ip_literal_host("192.168.1.208.evil.example:8025"))
        self.assertEqual(self.guard("POST", "attacker.example:8025", origin="http://attacker.example:8025"), 403)
        for good in ("127.0.0.1:8025", "localhost:8025", "LOCALHOST:8025", "[::1]:8025"):
            self.assertEqual(self.guard("GET", good), 200, good)
        # make_app without host names answers any Host (tests), but still refuses other sites' POSTs
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r1 = await c.post("/api/backup", headers={"Origin": "http://evil.example"})
                r2 = await c.post("/api/backup")   # passes the guard: no database path in tests
                self.state.db_path, self.state.backup_done_at = "x.sqlite", time.monotonic()
                r3 = await c.post("/api/backup")   # G1.4: not again within a minute
                r4 = await c.get("/api/speech", headers={"Host": "attacker.example"})
            async with TestClient(TestServer(ed_outrider.make_app(self.state, {"good:1"}))) as c:
                r5 = await c.get("/api/speech", headers={"Host": "bad:1"})   # (the client's own 127.0.0.1 is an IP: answered)
                r6 = await c.get("/api/speech", headers={"Host": "good:1"})
            return [r.status for r in (r1, r2, r3, r4, r5, r6)]
        self.assertEqual(asyncio.run(go()), [403, 500, 429, 200, 403, 200])

    def test_voice_names(self):
        import tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            for ext in (".onnx", ".onnx.json"):   # installed = both files
                open(os.path.join(d, "my-odd.voice" + ext), "w").close()
            sp = outrider.tts.Speaker(voices_dir=d)
            ok = ("en_GB-southern_english_female-low", "zh_CN-huayan-x_low", "en_US-l2arctic-medium", "my-odd.voice")
            bad = ("../x_y-z-low", "/home/u/x_Y-z-low", "en_GB-a/b-low", "en_GB-x-huge", "", "en_GB-x-low\n")
            self.assertEqual([sp.valid_name(v) for v in ok], [True] * len(ok))
            self.assertEqual([sp.valid_name(v) for v in bad], [False] * len(bad))
            started = []
            sp.PiperVoice = object   # "installed", without starting any real work
            with unittest.mock.patch.object(outrider.tts.threading, "Thread", lambda **kw: started.append(kw) or unittest.mock.Mock()):
                self.assertFalse(sp.use("../../etc/x_y-z-low"))
                self.assertTrue(sp.use("en_US-lessac-medium"))
                self.assertTrue(sp.use("en_US-amy-medium"))   # while the first switch runs: queued, no second thread
            self.assertEqual((len(started), sp._switch_to), (1, "en_US-amy-medium"))

    def test_honk_off_during_delay(self):
        # F58: switching auto honk off while it waits out the delay drops the honk without a 'failed' moment
        import asyncio, datetime as _dt
        presses = []

        class FakeHonker:
            available, status = True, "ready"
            ready = True

            def press(self, check=None, cancel=None):
                presses.append(1)
                return "K"

            def close(self):
                self.ready = False
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=True, delay=0.3)
        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.j.handle({"event": "FSDJump", "timestamp": now, "StarSystem": "S41", "SystemAddress": 41, "StarPos": [1, 0, 0]})

        async def go():
            self.state.maybe_honk()
            await asyncio.sleep(0.1)
            self.state.set_autohonk(False)
            await asyncio.sleep(0.5)
        asyncio.run(go())
        self.assertEqual(presses, [])
        self.assertEqual([m for m in self.state.moments_summary() if m["kind"] == "honk"], [])

    def test_honk_test_runs(self):
        # F60: one test at a time; F77: a failed press reaches the dialog; the device closes after (auto honk off)
        import asyncio
        log = []

        class FakeHonker:
            available, status, fail = True, "off", None

            def __init__(self):
                self.ready = False

            def combo(self):
                return ["KEY_K"], "K"

            def open(self):
                self.ready = True
                return True

            def close(self):
                self.ready = False
                log.append("close")

            def press(self, check=None, cancel=None):
                time.sleep(0.1)
                log.append("press")
                if self.fail:
                    raise ValueError(self.fail)
                return "K"
        self.state.honker = FakeHonker()
        self.state.autohonk = dict(ed_outrider.AUTOHONK, enabled=False)
        self.state.honk_test_countdown = 0.05

        async def go():
            first = self.state.start_honk_test()
            second = self.state.start_honk_test()
            self.state.set_autohonk(False)   # unticking during a test leaves the device to the test
            closed_early = list(log)
            await self.state.honk_test_task
            return first, second, closed_early
        first, second, closed_early = asyncio.run(go())
        self.assertEqual((first[1], first[0]["in"], second[1]), (200, 0.05, 409))
        self.assertEqual(closed_early, [])
        self.assertEqual(log, ["press", "close"])
        self.assertEqual(self.state.autohonk_info()["test"]["state"], "done")
        self.state.honker.fail = "no keyboard binding for Primary Fire"
        asyncio.run(self._run_test())
        t = self.state.autohonk_info()["test"]
        self.assertEqual((t["seq"], t["state"], t["error"]), (2, "failed", "no keyboard binding for Primary Fire"))

    async def _run_test(self):
        self.assertEqual(self.state.start_honk_test()[1], 200)
        await self.state.honk_test_task

    def test_honker_close_during_press(self):
        # F86: close() while press() holds the key: the hold ends early, keys are let go, then the device closes
        import threading
        import types
        import outrider.honk
        writes = []

        class FakeUI:
            closed = False

            def write(self, _type, code, value):
                if self.closed:
                    raise AttributeError("closed")
                writes.append((code, value))

            def syn(self):
                pass

            def close(self):
                self.closed = True
        h = outrider.honk.Honker("KEY_K", hold=5)
        h.evdev = types.SimpleNamespace(ecodes=types.SimpleNamespace(EV_KEY=1, ecodes={"KEY_K": 37}))
        h.ui = ui = FakeUI()
        out = []
        t = threading.Thread(target=lambda: out.append(h.press()))
        start = time.time()
        t.start()
        time.sleep(0.2)
        h.close()   # returns at once: the event loop must not wait out the hold
        self.assertLess(time.time() - start, 1)
        self.assertFalse(h.ready)
        t.join(2)
        self.assertLess(time.time() - start, 1.5)
        self.assertEqual((out, writes, ui.closed, h.ui), ([None], [(37, 1), (37, 0)], True, None))
        with self.assertRaises(ValueError):   # closed: a later press says so instead of an AttributeError
            h.press()
        # close with no press running closes at once
        h.ui = ui2 = FakeUI()
        h.close()
        self.assertTrue(ui2.closed and h.ui is None)


    def test_honker_check_and_cancel(self):   # review CX-F3, CX-F1: a check under the lock, and a press's own token
        import threading
        import types
        import outrider.honk
        writes = []

        class FakeUI:
            closed = False

            def write(self, _type, code, value):
                writes.append((code, value))

            def syn(self):
                pass

            def close(self):
                self.closed = True
        h = outrider.honk.Honker("KEY_K", hold=5)
        h.evdev = types.SimpleNamespace(ecodes=types.SimpleNamespace(EV_KEY=1, ecodes={"KEY_K": 37}))
        h.ui = ui = FakeUI()
        seen = []

        def check():
            seen.append(h.lock.locked())   # run under the lock, just before the key
            return "the galaxy map is open"
        with self.assertRaises(outrider.honk.NotNow) as cm:
            h.press(check=check)
        self.assertEqual((str(cm.exception), seen, writes), ("the galaxy map is open", [True], []))
        self.assertFalse(h.lock.locked())
        # an already-set token: nothing pressed
        gone = threading.Event()
        gone.set()
        with self.assertRaises(outrider.honk.NotNow):
            h.press(cancel=gone)
        self.assertEqual(writes, [])
        # set during the hold: the hold ends at once, the key is let go, and the device stays open (auto-target's)
        cancel = threading.Event()
        threading.Timer(0.2, cancel.set).start()
        start = time.time()
        self.assertIsNone(h.press(check=lambda: None, cancel=cancel))
        self.assertLess(time.time() - start, 1)
        self.assertEqual((writes, ui.closed, h.ui is ui), ([(37, 1), (37, 0)], False, True))


class Batch5ConfigCli(unittest.TestCase):
    """Second review, batch 5: config edge cases, the auto honk binding, Piper downloads and the voice lab."""

    ARGS = dict(journals=None, legacy=None, host=None, port=None, radius=None, db=None)

    def settings(self, cfg, detected=([], []), **args):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            st = ed_outrider.settings_from(cfg, argparse.Namespace(**dict(self.ARGS, **args)), None, detected)
        return st, err.getvalue()

    def test_config_not_utf8(self):   # F48
        import contextlib, io, tempfile
        with tempfile.NamedTemporaryFile("wb", suffix=".toml", delete=False) as f:
            f.write('[defaults]\nspeech_names = "Jos\xe9"\n'.encode("cp1252"))
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                self.assertEqual(ed_outrider.load_config(f.name), {})
        finally:
            os.remove(f.name)
        self.assertIn("(ignored: every setting is at its default)", err.getvalue())
        self.assertNotIn("backslashes", err.getvalue())   # not a path slip: no hint about one

    def test_config_windows_backslashes(self):
        """A Windows path typed in double quotes ("C:\\Users\\..."): TOML reads the backslashes as escapes and the whole
        file is ignored, so the message says how to write it; forward slashes and single quotes load."""
        import contextlib, io, tempfile
        def load(text):
            with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
                f.write(text)
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    return ed_outrider.load_config(f.name), err.getvalue()
            finally:
                os.remove(f.name)
        cfg, err = load('[journals]\nlive = ["C:\\Users\\me\\Saved Games"]\n')
        self.assertEqual(cfg, {})
        self.assertIn("C:/Users/", err)
        self.assertIn("single quotes", err)
        self.assertEqual(load('[journals]\nlive = ["C:/Users/me"]\n')[0], {"journals": {"live": ["C:/Users/me"]}})
        self.assertEqual(load("[journals]\nlive = ['C:\\Users\\me']\n")[0], {"journals": {"live": ["C:\\Users\\me"]}})
        cfg, err = load('[server]\nport = "8025\n')   # broken, but no backslash anywhere: no path hint
        self.assertEqual(cfg, {})
        self.assertNotIn("backslashes", err)

    def test_infinite_numbers(self):   # F49
        import tomllib
        cfg = tomllib.loads("[defaults]\nunsold_warn = inf\nspeech_speed = nan\n[server]\nradius = inf\n"
                            "radius_choices = [inf, 30]\n[spansh]\nconcurrency = -inf\n")
        st, err = self.settings(cfg)
        self.assertEqual((st["unsold_warn"], st["speech_speed"], st["radius"], st["radius_choices"], st["concurrency"]),
                         (ed_outrider.UNSOLD_WARN, ed_outrider.SPEECH_SPEED, 25.0, [30.0], ed_outrider.SPANSH_CONCURRENCY))
        for key in ("unsold_warn", "speech_speed", "radius", "concurrency"):
            self.assertIn(key, err)

    def test_empty_folder_lists_turn_detection_off(self):   # F46
        det = (["/live"], ["/mnt/c/old"])
        self.assertEqual(self.settings({"journals": {"legacy": []}}, det)[0]["legacy"], [])
        self.assertEqual(self.settings({"journals": {"legacy": []}}, det)[0]["live"], ["/live"])
        st = self.settings({"journals": {"live": []}}, det)[0]
        self.assertEqual((st["live"], st["legacy"]), ([], []))
        st = self.settings({"journals": {}}, det)[0]
        self.assertEqual((st["live"], st["legacy"]), (["/live"], ["/mnt/c/old"]))
        self.assertEqual(self.settings({"journals": {"legacy": []}}, det, legacy=["/flag"])[0]["legacy"], ["/flag"])

    def test_write_config_keeps_detection_for_an_empty_live_list(self):   # F46: --write-config with nothing found
        import tomllib
        st = self.settings({}, ([], []))[0]
        back = tomllib.loads(ed_outrider.config_text(st))["journals"]
        self.assertNotIn("live", back)          # a written "live = []" would turn detection off for good
        self.assertNotIn("legacy", back)        # F40: nor would "legacy = []" for the legacy folders

    def test_db_flag_is_relative_to_the_current_folder(self):   # F23
        st = self.settings({"server": {"db": "from-config.sqlite"}}, db="scratch.sqlite")[0]
        self.assertEqual(st["db"], os.path.join(os.getcwd(), "scratch.sqlite"))
        st = self.settings({"server": {"db": "from-config.sqlite"}})[0]
        self.assertEqual(st["db"], os.path.join(ed_outrider.SCRIPT_DIR, "from-config.sqlite"))
        self.assertEqual(self.settings({})[0]["db"], ed_outrider.DB_PATH)
        self.assertEqual(self.settings({}, db="/abs/x.sqlite")[0]["db"], "/abs/x.sqlite")

    def test_spansh_limits(self):   # F50
        st = self.settings({"spansh": {"concurrency": 0, "map_max_pages": -2, "map_max_radius": 1}})[0]
        self.assertEqual((st["concurrency"], st["map_max_pages"], st["map_max_radius"]), (1, 1, 5.0))
        st = self.settings({"spansh": {"concurrency": 8, "map_max_pages": 3, "map_max_radius": 400}})[0]
        self.assertEqual((st["concurrency"], st["map_max_pages"], st["map_max_radius"]), (8, 3, 400.0))

    # ---- auto honk binding ----
    controls = make_controls

    @staticmethod
    def binds_file(binds, preset, key="Key_K", mods=()):
        m = "".join(f'<Modifier Device="Keyboard" Key="{k}" />' for k in mods)
        with open(os.path.join(binds, f"{preset}.4.2.binds"), "w") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8" ?><Root PresetName="{preset}"><PrimaryFire>'
                    f'<Primary Device="Keyboard" Key="{key}">{m}</Primary></PrimaryFire></Root>')

    def test_ship_line_of_the_start_preset(self):   # F42
        import tempfile
        import outrider.honk
        with tempfile.TemporaryDirectory() as root:
            journals, binds = self.controls(root, "General One\nShip Two\nSRV Three\nFoot Four")
            self.binds_file(binds, "General One", "Key_G")
            self.binds_file(binds, "Ship Two", "Key_S")
            keys, what = outrider.honk.primary_fire_binding([journals])
            self.assertEqual(keys, ["KEY_S"])
            self.assertIn("Ship Two", what)
        with tempfile.TemporaryDirectory() as root:   # an older single-line file
            journals, binds = self.controls(root, "General One\n")
            self.binds_file(binds, "General One", "Key_G")
            self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_G"])

    def test_built_in_preset_does_not_borrow_a_custom_file(self):   # F43
        import tempfile
        import outrider.honk
        with tempfile.TemporaryDirectory() as root:
            journals, binds = self.controls(root, "KeyboardMouseOnly\n" * 4)
            self.binds_file(binds, "Custom", "Key_C")
            keys, what = outrider.honk.primary_fire_binding([journals])
            self.assertIsNone(keys)
            self.assertIn("built-in", what)
            self.assertIn("KeyboardMouseOnly", what)
        with tempfile.TemporaryDirectory() as root:   # no preset named at all: the newest Custom file
            journals, binds = self.controls(root, None)
            self.binds_file(binds, "Custom", "Key_C")
            self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_C"])

    def test_auto_binding_checked_against_evdev(self):   # F41
        import tempfile, types
        import outrider.honk
        self.assertEqual([outrider.honk.elite_key(k) for k in ("Key_Apps", "Key_Numpad_Equals", "Key_OEM_102", "Key_Hash",
                                                        "Key_PrintScreen", "Key_Numpad_Comma")],
                         ["KEY_COMPOSE", "KEY_KPEQUAL", "KEY_102ND", "KEY_BACKSLASH", "KEY_SYSRQ", "KEY_KPCOMMA"])
        fake = types.SimpleNamespace(ecodes=types.SimpleNamespace(ecodes={"KEY_COMPOSE": 127, "KEY_LEFTALT": 56}))
        with tempfile.TemporaryDirectory() as root:
            journals, binds = self.controls(root)
            h = outrider.honk.Honker("auto", journal_dirs=[journals])
            h.evdev = fake
            self.binds_file(binds, "My X56", "Key_Apps", ["Key_LeftAlt"])
            self.assertEqual(h.combo()[0], ["KEY_LEFTALT", "KEY_COMPOSE"])
            time.sleep(0.01)
            self.binds_file(binds, "My X56", "Key_Frobnicate")
            os.utime(os.path.join(binds, "My X56.4.2.binds"), (time.time() + 5, time.time() + 5))
            keys, what = h.combo()
            self.assertIsNone(keys)
            self.assertIn("no evdev equivalent for KEY_FROBNICATE", what)

    def test_binding_read_errors_and_cache(self):   # F59
        import tempfile
        import outrider.honk
        with tempfile.TemporaryDirectory() as root:
            journals, binds = self.controls(root)
            self.binds_file(binds, "My X56", "Key_K")
            real = outrider.honk.ET.parse
            calls = []
            with unittest.mock.patch.object(outrider.honk.ET, "parse", lambda p: calls.append(p) or real(p)):
                self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_K"])
                self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_K"])
                self.assertEqual(len(calls), 1)            # unchanged files: not parsed again
                self.binds_file(binds, "My X56", "Key_L")
                os.utime(os.path.join(binds, "My X56.4.2.binds"), (time.time() + 5, time.time() + 5))
                self.assertEqual(outrider.honk.primary_fire_binding([journals])[0], ["KEY_L"])   # a rebind is picked up
                self.assertEqual(len(calls), 2)
            os.utime(os.path.join(binds, "StartPreset.4.start"), (time.time() + 9, time.time() + 9))
            with unittest.mock.patch.object(outrider.honk.ET, "parse", side_effect=FileNotFoundError(2, "gone")):
                keys, what = outrider.honk.primary_fire_binding([journals])   # Elite rewriting the file right now
            self.assertIsNone(keys)
            self.assertIn("could not be read", what)

    def test_honk_cli_uses_config_and_detection(self):   # F85
        import contextlib, io, tempfile
        import outrider.honk
        with tempfile.TemporaryDirectory() as root:
            journals, binds = self.controls(root)
            self.binds_file(binds, "My X56", "Key_K")
            here = os.path.join(root, "app")
            os.makedirs(here)
            out = io.StringIO()
            with unittest.mock.patch.object(outrider.honk, "ROOT", here), \
                    unittest.mock.patch.object(outrider.unsold, "find_journal_dirs", return_value=([journals], [])), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(outrider.honk.main(["--show"]), 0)         # no config: auto-detected folders
                with open(os.path.join(here, "ed_outrider.toml"), "w") as f:
                    f.write('[autohonk]\nkey = "KEY_KP0"\n')
                self.assertEqual(outrider.honk.main(["--show"]), 0)         # the configured key
                self.assertEqual(outrider.honk.main(["--show", "--key", "auto"]), 0)
            lines = out.getvalue().splitlines()
            self.assertIn("K (primary binding of Primary Fire in My X56)", lines[0])
            self.assertEqual(lines[1], "Primary Fire: Numpad 0")
            self.assertIn("My X56", lines[2])

    # ---- Piper ----
    def test_speaker_reports_every_status_and_falls_back(self):   # G2.2, F40
        import contextlib, io, tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            for v in ("en_GB-a-low", "en_GB-b-low"):
                for ext in (".onnx", ".onnx.json"):
                    open(os.path.join(d, v + ext), "w").close()
            seen = []
            sp = outrider.tts.Speaker("en_GB-a-low", "en_GB-b-low", voices_dir=d, on_change=lambda: seen.append(sp.status))
            sp.PiperVoice = unittest.mock.Mock()

            def load(path):
                if "en_GB-a-low" in path:
                    raise RuntimeError("truncated model")
                return os.path.basename(path)
            sp.PiperVoice.load = load
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                sp._prepare(None)
            self.assertEqual((sp.voice_name, sp._voice), ("en_GB-b-low", "en_GB-b-low.onnx"))   # the fallback
            self.assertEqual(seen, ["loading en_GB-a-low", "loading en_GB-b-low", "ready"])
            # a voice that fails to download and one that fails to load both reach the page
            seen.clear()
            with unittest.mock.patch.object(outrider.tts, "download_voice_files", side_effect=OSError("offline")), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                sp._prepare("en_GB-c-low")
            self.assertEqual(seen, ["downloading en_GB-c-low (about 63 MB)",   # F36: the loaded voice keeps speaking
                                    "could not switch to en_GB-c-low (download failed); still using en_GB-b-low"])
            seen.clear()
            with contextlib.redirect_stderr(io.StringIO()):
                sp._prepare("en_GB-a-low")
            self.assertEqual(seen[0], "loading en_GB-a-low")
            self.assertIn("could not load en_GB-a-low", seen[-1])

    def test_installed_needs_both_files(self):   # F40
        import tempfile
        import outrider.tts
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "en_GB-a-low.onnx"), "w").close()
            open(os.path.join(d, "en_GB-b-low.onnx"), "w").close()
            open(os.path.join(d, "en_GB-b-low.onnx.json"), "w").close()
            open(os.path.join(d, "en_GB-c-low.onnx.part"), "w").close()
            self.assertEqual(outrider.tts.installed_voices(d), ["en_GB-b-low"])

    def test_voice_paths_match_the_catalogue(self):   # F40: Outrider now downloads itself, like Piper's own tool
        import outrider.tts
        self.assertEqual(outrider.tts.voice_paths("en_GB-jenny_dioco-medium"),
                         ["en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx.json",
                          "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx"])
        with self.assertRaises(ValueError):
            outrider.tts.voice_paths("../x-y-low")
        cat = os.path.join(outrider.tts.VOICES_DIR, "voices.json")
        if os.path.exists(cat):   # the voice lab's cached catalogue, when there is one
            with open(cat, encoding="utf-8") as f:
                doc = json.load(f)
            for name, v in doc.items():
                if outrider.tts.VOICE_NAME.fullmatch(name):
                    want = sorted(p for p in v["files"] if p.endswith((".onnx", ".onnx.json")))
                    self.assertEqual(sorted(outrider.tts.voice_paths(name)), want, name)

    def test_download_moves_files_in_only_when_complete(self):   # F40, F88
        import hashlib, tempfile
        import outrider.tts
        files = [("en/en_GB/x/low/en_GB-x-low.onnx.json", {}), ("en/en_GB/x/low/en_GB-x-low.onnx", {})]
        with tempfile.TemporaryDirectory() as d:
            def run(responses, files=files):
                it = iter(responses)
                with unittest.mock.patch.object(outrider.tts.urllib.request, "urlopen", lambda url, timeout: next(it)):
                    outrider.tts.download_voice_files(files, d)
            # the connection drops 3 bytes into the model: nothing is left, not even the finished config
            with self.assertRaises(ConnectionResetError):
                run([_FakeResponse(b"{}"), _FakeResponse(b"abc", ConnectionResetError("reset"))])
            self.assertEqual(os.listdir(d), [])
            # a short body (the server closed early without an error)
            with self.assertRaises(IOError):
                run([_FakeResponse(b"{}"), _FakeResponse(b"abc", length=10)])
            self.assertEqual(os.listdir(d), [])
            # a checksum mismatch
            with self.assertRaises(IOError):
                run([_FakeResponse(b"model")], [("a/en_GB-x-low.onnx", {"md5_digest": "0" * 32})])
            self.assertEqual(os.listdir(d), [])
            run([_FakeResponse(b"{}"), _FakeResponse(b"model")],
                [files[0], (files[1][0], {"md5_digest": hashlib.md5(b"model").hexdigest()})])
            self.assertEqual(sorted(os.listdir(d)), ["en_GB-x-low.onnx", "en_GB-x-low.onnx.json"])
            self.assertEqual(outrider.tts.installed_voices(d), ["en_GB-x-low"])

    def test_voice_lab_download_and_pump(self):   # F88, F44
        import tempfile, types, queue
        try:
            import voice_lab
        except (ImportError, SystemExit):
            self.skipTest("no tkinter")
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.object(voice_lab, "VOICES_DIR", d):
            entry = {"files": {"en/en_GB/x/low/en_GB-x-low.onnx": {"size_bytes": 10},
                               "en/en_GB/x/low/en_GB-x-low.onnx.json": {"size_bytes": 2},
                               "en/en_GB/x/low/MODEL_CARD": {}}}
            it = iter([_FakeResponse(b"{}"), _FakeResponse(b"abc", OSError("Wi-Fi dropped"))])
            with unittest.mock.patch.object(voice_lab.outrider.tts.urllib.request, "urlopen", lambda url, timeout: next(it)):
                with self.assertRaises(OSError):
                    voice_lab.download(entry, lambda done, total: None)
            self.assertEqual(os.listdir(d), [])
        # a failing callback neither stops the queue nor the pump's re-arming
        ran, status, rearmed = [], [], []
        lab = types.SimpleNamespace(q=queue.Queue(), root=types.SimpleNamespace(after=lambda ms, f: rearmed.append(ms)),
                                    set_status=lambda text, error=False: status.append((text, error)), pump=None)
        lab.q.put(lambda: open("/nonexistent-dir/x.wav", "wb"))
        lab.q.put(lambda: ran.append(1))
        voice_lab.Lab.pump(lab)
        self.assertEqual((ran, rearmed, status[0][1]), ([1], [80], True))
        self.assertIn("FileNotFoundError", status[0][0])

    def test_spoken_numbers_stay_fixed_point(self):   # F82
        self.assertEqual(outrider.speech.spoken_text("Carried 1234567.89 cr"), "Carried 1234567.9 credits")
        self.assertEqual(outrider.speech.spoken_text("123456.78 and 52.0M and 0.96"), "123456.8 and 52 million and 1")


class Batch7Data(unittest.TestCase):
    """Batch 7: rolling backups with the journal archive, exobiology in ship losses, the discovery streak's fixed
    verdicts, the Last session card and the browser defaults saved on the server. Files only in temp folders."""

    def setUp(self):
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.addCleanup(self.db.close)

    def jump(self, ts, id64, x, kind="FSDJump"):
        self.j.handle({"event": kind, "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})

    def star(self, ts, id64, disc):
        self.j.handle(scan(ts, f"S{id64}", id64, 0, f"S{id64}", disc=disc, star=True)[2])

    @staticmethod
    def journal(folder, name, text):
        with open(os.path.join(folder, name), "w") as f:
            f.write(text)

    def test_journal_archive(self):   # P11: copied when missing or a different size, never deleted, via .part files
        import tempfile
        with tempfile.TemporaryDirectory() as live, tempfile.TemporaryDirectory() as out:
            dest = os.path.join(out, "journals")
            self.journal(live, "Journal.2026-09-27T100000.01.log", "a\n")
            self.journal(live, "Journal.2026-09-28T100000.01.log", "b\n")
            self.journal(live, "Status.json", "{}")                      # not a journal
            copied, newest, failed = ed_outrider.archive_journals([live], dest)
            self.assertEqual(failed, [])
            self.assertEqual(copied, 2)
            self.assertRegex(newest, r"^\d{4}-\d{2}-\d{2}$")
            self.assertEqual(sorted(os.listdir(dest)), ["Journal.2026-09-27T100000.01.log", "Journal.2026-09-28T100000.01.log"])
            self.assertEqual(ed_outrider.archive_journals([live], dest)[0], 0)   # unchanged: nothing copied
            self.journal(live, "Journal.2026-09-28T100000.01.log", "b\nc\n")     # the game appended a line
            self.assertEqual(ed_outrider.archive_journals([live], dest)[0], 1)
            with open(os.path.join(dest, "Journal.2026-09-28T100000.01.log")) as f:
                self.assertEqual(f.read(), "b\nc\n")
            os.remove(os.path.join(live, "Journal.2026-09-27T100000.01.log"))  # gone from the game folder: kept here
            ed_outrider.archive_journals([live], dest)
            self.assertIn("Journal.2026-09-27T100000.01.log", os.listdir(dest))

    def test_rotation_keeps_the_newest_and_nothing_else(self):   # P11
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            zips = [f"outrider-2026090{i}-120000.zip" for i in range(1, 10)]   # old names: the default database's
            others = ["outrider-keep-this.zip", "notes.txt", "outrider-20260901-120000.zip.part",
                      "outrider-test-20260901-120000Z.zip"]                    # G2.1: another database's zip
            for f in zips + others:
                self.journal(d, f, "x")
            os.makedirs(os.path.join(d, "journals"))
            self.assertEqual(ed_outrider.rotate_backups(d, 3, ed_outrider.DB_PATH), 3)
            self.assertEqual(sorted(os.listdir(d)), sorted(zips[-3:] + others + ["journals"]))
            self.assertEqual(ed_outrider.rotate_backups(d, 0, ed_outrider.DB_PATH), 1)   # at least one is always kept
            self.assertEqual(ed_outrider.rotate_backups(d, 1, "/x/test.sqlite"), 1)      # only its own zips count

    def test_backup_is_database_only_then_rotates(self):   # P11: zip = db (+ browser defaults), journals archived
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as d:
            live, out = os.path.join(d, "live"), os.path.join(d, "backups")
            os.makedirs(live); os.makedirs(out)
            self.journal(live, "Journal.2026-09-28T100000.01.log", '{"event":"Fileheader"}\n')
            for i in range(1, 4):
                self.journal(out, f"outrider-x-2020010{i}-000000Z.zip", "old")
            self.journal(out, "outrider-20200101-000000.zip", "another database's, from an older build")
            dbp = os.path.join(d, "x.sqlite")
            sqlite3.connect(dbp).close()
            ed_outrider.write_browser_defaults(ed_outrider.browser_defaults_path(dbp), {"version": 1, "settings": {"sound": True}})
            self.state.db_path = dbp
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 2):
                res = self.state.make_backup()
            self.assertEqual(res["kept"], 2)
            self.assertEqual(res["copied"], 1)
            with zipfile.ZipFile(res["path"]) as z:
                self.assertEqual(sorted(z.namelist()), ["browser_defaults.json", "x.sqlite"])   # no journals in the zip
            self.assertEqual(sorted(f for f in os.listdir(out) if f.endswith(".zip")),
                             sorted(["outrider-20200101-000000.zip", "outrider-x-20200103-000000Z.zip",
                                     os.path.basename(res["path"])]))
            self.assertRegex(os.path.basename(res["path"]), r"^outrider-x-\d{8}-\d{6}Z\.zip$")
            self.assertEqual(os.listdir(os.path.join(out, "journals")), ["Journal.2026-09-28T100000.01.log"])
            # a failure before the zip is written deletes nothing
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", out), \
                    unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_KEEP", 1), \
                    unittest.mock.patch.object(zipfile.ZipFile, "write", side_effect=OSError(28, "No space left on device")):
                with self.assertRaises(OSError):
                    self.state.make_backup()
            self.assertEqual(len([f for f in os.listdir(out) if f.endswith(".zip")]), 3)

    def test_when_automatic_backups_run(self):   # P11: at start when due; on a live Shutdown only; 0 turns them off
        import asyncio
        now = time.time()
        self.assertTrue(ed_outrider.backup_due(None, 1, now))
        self.assertTrue(ed_outrider.backup_due({"error": "x"}, 1, now))               # never worked
        self.assertFalse(ed_outrider.backup_due({"ts": ed_outrider.iso_ts(now - 3600)}, 1, now))
        self.assertTrue(ed_outrider.backup_due({"ts": ed_outrider.iso_ts(now - 2 * 86400)}, 1, now))
        self.assertFalse(ed_outrider.backup_due(None, 0, now))
        started = []

        async def go(ts, every=1.0):
            self.state.start_backup = lambda auto=False: started.append(auto)
            with unittest.mock.patch.object(ed_outrider, "SHUTDOWN_BACKUP_DELAY", 0), \
                    unittest.mock.patch.object(ed_outrider, "BACKUP_EVERY_DAYS", every):
                self.j.handle({"event": "Shutdown", "timestamp": ts})
                self.state.maybe_backup_on_quit(now)
                self.state.maybe_backup_on_quit(now)   # the same Shutdown seen again: nothing more
                await asyncio.sleep(0.05)
        asyncio.run(go(ed_outrider.iso_ts(now - 3 * 86400)))    # an old journal read now
        self.assertEqual(started, [])
        asyncio.run(go(ed_outrider.iso_ts(now - 5)))            # the game just quit
        self.assertEqual(started, [True])
        asyncio.run(go(ed_outrider.iso_ts(now - 2), every=0))   # automatic backups off
        self.assertEqual(started, [True])

    def test_backup_settings(self):
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        st = ed_outrider.settings_from({}, args, None, ([], []))
        self.assertEqual((st["backup_keep"], st["backup_every_days"]), (7, 1.0))
        st = ed_outrider.settings_from({"server": {"backup_keep": 0, "backup_every_days": 0.5}}, args, None, ([], []))
        self.assertEqual((st["backup_keep"], st["backup_every_days"]), (1, 0.5))
        back = tomllib.loads(ed_outrider.config_text(st))["server"]
        self.assertEqual((back["backup_keep"], back["backup_every_days"]), (1, 0.5))
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ed_outrider.toml.example")) as f:
            ex = f.read()
        self.assertIn("# backup_keep = 7 ", ex)
        self.assertIn("# backup_every_days = 1 ", ex)

    def test_losses_count_exobiology(self):   # P18
        run = lambda ts, system, body, sp: [self.j.handle(org(ts[:-3] + f"{i}Z", system, body, sp, k))
                                            for i, k in enumerate(("Log", "Sample", "Analyse"))]
        value = outrider.bio.species_value("Bacterium Aurasus")
        self.assertTrue(value)
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        run("2026-01-01T01:00:00Z", 1, 3, "A")                       # sold before any death
        self.j.handle({"event": "SellOrganicData", "timestamp": "2026-01-01T02:00:00Z", "BioData": [{"Species": "$Codex_Ent_A;", "Value": 1}]})
        run("2026-01-01T03:00:00Z", 1, 4, "B")                       # lost on foot: the ship survived
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T04:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T04:00:01Z", "Option": "recover"})
        run("2026-01-01T05:00:00Z", 1, 5, "C")                       # lost with the ship
        self.star("2026-01-01T05:30:00Z", 1, disc=True)
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T06:00:00Z"})
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T06:00:01Z", "Option": "rebuy"})
        self.j.handle({"event": "Died", "timestamp": "2026-01-01T07:00:00Z"})   # on foot again, nothing aboard: no row
        self.j.handle({"event": "Resurrect", "timestamp": "2026-01-01T07:00:01Z", "Option": "recover"})
        self.db.commit()
        losses = self.state.ship_losses()
        self.assertEqual([(l["ts"][11:13], l["ship"], l["bio_runs"], l["bio_value"], l["bodies"]) for l in losses],
                         [("04", False, 1, value, 0), ("06", True, 1, value, 1)])
        self.assertGreater(losses[1]["value"], 0)                    # the carto side is unchanged
        # Bio/Geo's My Samples calls the same runs lost, for the same money
        self.assertEqual(self.state.organics(36500)["totals"]["lost"], 2 * value)
        cols, rows = self.state.export_rows("trips")
        self.assertIn("lost_bio", cols)

    def test_streak_verdicts_are_fixed_at_the_arrival_scan(self):   # P16
        self.jump("2026-01-01T00:00:00Z", 1, 0)
        self.star("2026-01-01T00:00:05Z", 1, disc=False)             # nobody had discovered it
        self.jump("2026-01-01T00:01:00Z", 2, 10)
        self.star("2026-01-01T00:01:05Z", 2, disc=True)              # known: what did Spansh know?
        self.state.target_verdicts[2] = "explored"
        self.db.commit()
        self.state.reconcile_arrival()
        self.assertEqual(self.state.arrival["verdict"], "complete")
        self.jump("2026-01-01T00:02:00Z", 3, 20)
        self.star("2026-01-01T00:02:05Z", 3, disc=True)
        self.state.target_verdicts[3] = "partial"
        self.state.reconcile_arrival()
        self.jump("2026-01-01T00:03:00Z", 1, 0)                      # back to 1: visited, though still "undiscovered"
        self.star("2026-01-01T00:03:05Z", 1, disc=False)
        self.star("2026-01-01T00:04:00Z", 1, disc=True)              # a later scan changes nothing
        self.jump("2026-01-01T00:05:00Z", 4, 30)                     # not scanned yet
        self.db.commit()
        sk = self.state.streak()
        self.assertEqual([a["verdict"] for a in sk["arrivals"]], ["new", "complete", "partial", "visited", None])
        self.assertEqual((sk["new"], sk["total"]), (1, 5))
        self.assertEqual(sk["arrivals"][0]["firsts"], 1)
        # a journal re-read rebuilds the jumps: the journal verdicts come back the same, and what Spansh knew then
        # is kept (it cannot be asked again), so no dot changes colour
        self.db.executescript(ed_outrider.RESET_JOURNAL_DATA)
        self.j.reload()
        self.jump("2026-01-01T00:01:00Z", 2, 10)
        self.star("2026-01-01T00:01:05Z", 2, disc=True)
        self.db.commit()
        self.assertEqual([a["verdict"] for a in self.state.streak()["arrivals"]], ["complete"])

    def test_streak_runs(self):   # P16: what counts as "in a row"
        runs = ed_outrider.State.streak_runs
        self.assertEqual(runs(["new", "new", "known"]), (2, 0))
        self.assertEqual(runs(["complete", "known", "complete", "partial"]), (0, 3))   # amber ends a known run
        self.assertEqual(runs(["complete", "visited", "complete"]), (0, 1))            # so does a way back
        self.assertEqual(runs([None, "new"]), (0, 0))
        self.assertEqual(runs([]), (0, 0))
        for i in range(12):   # the arrival carries the runs, for the page's once-per-streak line
            self.jump(f"2026-01-01T01:{i:02d}:00Z", 100 + i, i)
            self.star(f"2026-01-01T01:{i:02d}:05Z", 100 + i, disc=True)
            self.state.target_verdicts[100 + i] = "explored"
            self.state.reconcile_arrival()
        self.assertEqual(self.state.arrival["streak"], {"new": 0, "known": 12})

    def test_last_session_card(self):   # P19: kept (meta) until the next login
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-01T01:00:00Z", "Commander": "X"})
        self.assertIsNone(self.state.last_session())                          # playing
        for i in range(3):
            self.jump(f"2026-01-01T01:0{i + 1}:00Z", 10 + i, 10 * (i + 1))
        self.star("2026-01-01T01:03:05Z", 12, disc=False)
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-01T02:00:00Z"})
        self.db.commit()
        ls = self.state.last_session()
        self.assertEqual((ls["jumps"], ls["firsts"], ls["start"], ls["end"]), (3, 1, "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"))
        j2 = ed_outrider.Journals(self.db)                                    # a restart: still there
        self.assertEqual(ed_outrider.State(self.db, j2, None, 25).last_session()["jumps"], 3)
        self.j.handle({"event": "LoadGame", "timestamp": "2026-01-02T01:00:00Z", "Commander": "X"})
        self.assertIsNone(self.state.last_session())                          # the next login hides it
        self.j.handle({"event": "Shutdown", "timestamp": "2026-01-02T01:01:00Z"})   # a quick relog: nothing to show
        self.assertIsNone(self.state.last_session())

    def test_browser_defaults(self):   # P20: allow-list, size cap, atomic write, inlined into the page
        import asyncio, re, tempfile
        from aiohttp.test_utils import TestClient, TestServer
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        page_keys = re.findall(r'"(\w+)"', js[js.index("const SETTINGS_KEYS = ["):js.index("];", js.index("const SETTINGS_KEYS = ["))])
        self.assertEqual(page_keys, list(ed_outrider.BROWSER_SETTINGS))       # the page and the server share one list
        for per_device in ("view", "overview", "hereModes", "bodySecs", "search", "speakMode"):
            self.assertNotIn(per_device, ed_outrider.BROWSER_SETTINGS)
        ok, why = ed_outrider.check_browser_defaults({"version": 1, "settings": {"view": "map"}})
        self.assertIsNone(ok)
        self.assertIn("view", why)
        self.assertIsNone(ed_outrider.check_browser_defaults({"version": 2, "settings": {}})[0])
        self.assertIsNone(ed_outrider.check_browser_defaults([])[0])
        with tempfile.TemporaryDirectory() as d:
            self.state.db_path = os.path.join(d, "x.sqlite")
            path = ed_outrider.browser_defaults_path(self.state.db_path)

            async def go():
                async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                    out = [(await c.post("/api/defaults", json={"version": 1, "settings": {"view": "x"}})).status,
                           (await c.post("/api/defaults", data="x" * (ed_outrider.BROWSER_DEFAULTS_MAX + 1))).status,
                           (await c.post("/api/defaults", data="{not json")).status,
                           (await c.post("/api/defaults", json={"version": 1, "settings": {"sound": True}},
                                         headers={"Origin": "http://evil.example"})).status]
                    self.assertFalse(os.path.exists(path))
                    r = await c.post("/api/defaults", json={"version": 1, "settings": {"speechNames": "</script><b>", "sound": False}})
                    out.append(r.status)
                    page = await (await c.get("/")).text()
                    got = await (await c.get("/api/defaults")).json()
                    out.append((await c.post("/api/defaults", json={"clear": True})).status)
                    gone = await (await c.get("/api/defaults")).json()
                    return out, page, got, gone
            out, page, got, gone = asyncio.run(go())
            self.assertEqual(out, [400, 413, 400, 403, 200, 200])
            self.assertEqual(got["settings"], {"speechNames": "</script><b>", "sound": False})
            self.assertIn('window.SERVER_DEFAULTS = {"version": 1, "settings": {"speechNames": "\\u003c/script>', page)
            self.assertNotIn("</script><b>", page)
            self.assertIsNone(gone)
            self.assertEqual(os.listdir(d), [])                                   # no .part left, and cleared


class ToolingSafety(unittest.TestCase):
    """The test tools never reach the player's own Outrider or journals."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_page_smoke_needs_a_port_and_refuses_8025(self):
        """page_smoke.js clicks and POSTs: run without a port it used to default to 8025, a real Outrider's port.
        Network access is intercepted here, so even a broken version cannot reach a server."""
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("node"):
            self.skipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            pre = os.path.join(tmp, "nofetch.js")
            with open(pre, "w") as f:
                f.write("globalThis.fetch = async (u) => { console.log('FETCH ' + u); process.exit(3); };\n")
            for argv in ([], ["8025"], ["abc"]):
                r = subprocess.run(["node", "-r", pre, "tests/page_smoke.js", *argv], cwd=self.ROOT,
                                   capture_output=True, text=True, timeout=60)
                self.assertNotIn("FETCH", r.stdout, argv)
                self.assertEqual(r.returncode, 2, (argv, r.stdout, r.stderr))

    def test_verify_server_reads_the_fixture_journals_whatever_ED_JOURNALS_says(self):
        """verify.sh's scratch server must read its copy of the fixtures even when the shell exports ED_JOURNALS
        (settings rank the flag over the environment over the config). Its own argument list goes through main()
        (--write-config on an existing config prints the effective settings and starts nothing)."""
        import contextlib
        import io
        import re
        import shlex
        import tempfile
        with open(os.path.join(self.ROOT, "scripts", "verify.sh"), encoding="utf-8") as f:
            text = f.read().replace("\\\n", " ")
        line = re.search(r'"\$PY" - (--config .*?) >"\$TMP/server\.log"', text).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "journals"))
            with open(os.path.join(tmp, "scratch.toml"), "w") as f:
                f.write(f'[journals]\nlive = ["{tmp}/journals"]\nlegacy = []\n')
            argv = shlex.split(line.replace("$TMP", tmp).replace("$PORT", "8939")) + ["--write-config"]
            out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")   # main() reconfigures stdout: a real text stream
            with unittest.mock.patch.dict(os.environ, {"ED_JOURNALS": os.path.join(tmp, "elsewhere")}), \
                    contextlib.redirect_stdout(out):
                ed_outrider.main(argv)
            out.flush()
            printed = out.buffer.getvalue().decode("utf-8")
            m = re.search(r"^live = (.*)$", printed, re.M)
            self.assertIsNotNone(m, printed[:500])
            self.assertNotIn("ED Outrider 20", printed)   # --write-config prints the settings only
            # starting the server: its first line is the name and version (the author, 2026-10-10), before anything
            # the config's reading prints (here a warning for an unknown key)
            with open(os.path.join(tmp, "scratch.toml"), "a") as f:
                f.write("\n[nonsense]\nkey = 1\n")
            out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")

            async def no_server(args, st):
                print("server would start")
            with unittest.mock.patch.object(ed_outrider, "run", no_server), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(out):
                ed_outrider.main(argv[:-1])
            out.flush()
            lines = out.buffer.getvalue().decode("utf-8").splitlines()
            self.assertEqual(lines[0], f"ED Outrider {ed_outrider.outrider.__version__}")
            self.assertIn("server would start", lines)
            self.assertIn(f"{tmp}/journals", m.group(1))
            self.assertNotIn("elsewhere", m.group(1))
