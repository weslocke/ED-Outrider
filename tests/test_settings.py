"""The Settings dialog's Server settings: every config key listed (GET /api/config, secrets only as set or not) and
changed in place in the config file (POST /api/config: comments kept, the old file kept as .bak, nothing written when
the result would not read back or settings_from finds something new wrong). Only ever a temporary config file."""
import argparse
import asyncio
import contextlib
import io
import os
import shutil
import tempfile
import tomllib
import unittest
import unittest.mock

from support import ed_outrider

import outrider.auth  # noqa: E402
import outrider.config_edit as ce  # noqa: E402

ARGS = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
EXAMPLE = os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "ed_outrider.toml.example")


def settings(cfg):
    with contextlib.redirect_stderr(io.StringIO()):
        return ed_outrider.settings_from(cfg, ARGS, None, ([], []))


class ConfigEdit(unittest.TestCase):
    def test_every_key_listed_and_writable(self):
        """Every key --write-config writes is listed, and setting each to its own value in an empty file reads back to
        the same setting (so the page can change any of them)."""
        st = settings({})
        secs = ce.entries(ed_outrider.config_text(st))
        self.assertEqual([s["section"] for s in secs],
                         ["journals", "server", "defaults", "spansh", "speech", "autohonk", "copilot", "highway", "overlay",
                          "assistant", "mcp", "eddn", "edsm"])
        keys = [(s["section"], k["key"]) for s in secs for k in s["keys"]]
        self.assertGreaterEqual(len(keys), 80)
        for want in [("server", "password"), ("server", "db"), ("server", "backup_dir"), ("journals", "live"), ("assistant", "api_key"),
                     ("highway", "autotarget_keys"), ("mcp", "url"), ("speech", "sound_dir"), ("defaults", "speech_styles")]:
            self.assertIn(want, keys)
        for s in secs:
            for k in s["keys"]:
                text = ce.set_key("", s["section"], k["key"], k["value"])
                self.assertEqual(tomllib.loads(text)[s["section"]][k["key"]], k["value"], (s["section"], k["key"]))
        self.assertTrue(all(k["help"] for s in secs for k in s["keys"] if (s["section"], k["key"]) != ("server", "db") and k["set"]))

    def test_in_place(self):
        with open(EXAMPLE, encoding="utf-8") as f:
            ex = f.read()
        t = ce.set_key(ex, "server", "port", 8931)                       # a commented-out key switched on, its help kept
        t = ce.set_key(t, "highway", "autotarget_keys", {"Enter": "KEY_KPENTER", "a b": "KEY_A"})
        self.assertIn('port = 8931', t)
        self.assertIn('# (without a password below', t)                 # the comments round it untouched
        self.assertEqual(len(t.splitlines()), len(ex.splitlines()))       # no line added or lost
        self.assertEqual(tomllib.loads(t)["highway"]["autotarget_keys"], {"Enter": "KEY_KPENTER", "a b": "KEY_A"})
        multi = '[server]\nallowed_hosts = [\n  "a",   # one\n  "b",\n]   # the names\nport = 1\n'
        t = ce.set_key(multi, "server", "allowed_hosts", ["x"])         # a list over several lines replaced whole
        self.assertEqual((tomllib.loads(t)["server"], t.count("# the names")), ({"allowed_hosts": ["x"], "port": 1}, 1))
        t = ce.set_key('[server]\nhost = "a # not a comment"   # the real one\n', "server", "host", 'q"uote')
        self.assertEqual((tomllib.loads(t)["server"]["host"], "# the real one" in t), ('q"uote', True))
        t = ce.set_key("[server]\nport = 1\n\n[spansh]\n", "server", "password", "pw")   # a new key: in its own section
        self.assertEqual(tomllib.loads(t), {"server": {"port": 1, "password": "pw"}, "spansh": {}})

    def test_coerce(self):
        self.assertEqual([ce.coerce("int", "8025"), ce.coerce("float", "2.5"), ce.coerce("bool", True), ce.coerce("lines", "a\n\n b \n"),
                          ce.coerce("numbers", "20, 25 30"), ce.coerce("table", '{"Enter": "KEY_KPENTER"}'), ce.coerce("table", "")],
                         [8025, 2.5, True, ["a", "b"], [20, 25, 30], {"Enter": "KEY_KPENTER"}, {}])
        for kind, bad in (("int", "x"), ("int", ""), ("bool", "yes"), ("numbers", "a, b"), ("table", "[1]"), ("text", 5), ("table", '{"a": 1}')):
            with self.assertRaises(ValueError, msg=(kind, bad)):
                ce.coerce(kind, bad)


class TempConfig(unittest.TestCase):
    """A State whose config file is a temporary copy of the example (with a password set)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "ed_outrider.toml")
        with open(EXAMPLE, encoding="utf-8") as f:
            text = f.read().replace('# password = ""        # devices', 'password = "hunter2"   # devices')
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        self.state.config_path = self.path

    def client(self, go):
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return await go(c)
        return asyncio.run(run())


class Endpoint(TempConfig):
    def test_get_hides_secrets(self):
        async def go(c):
            r = await c.get("/api/config")
            return await r.text(), await r.json()
        text, d = self.client(go)
        self.assertNotIn("hunter2", text)
        pw = next(k for s in d["sections"] if s["section"] == "server" for k in s["keys"] if k["key"] == "password")
        self.assertEqual((pw["secret"], pw["set"], pw["value"], d["path"], d["exists"]), (True, True, None, self.path, True))

    def test_save(self):
        async def go(c):
            out = []
            for body in ({"server": {"port": "8931", "password": "new pw"}, "autohonk": {"enabled": True}, "journals": {"live": "/j/a\n/j/b"}},
                         {"server": {"port": "x"}}, {"server": {"nope": 1}}, {"mcp": {"max_rows": "0"}}, {}, [1]):
                r = await c.post("/api/config", json=body)
                out.append((r.status, await r.json()))
            return out
        with open(self.path, encoding="utf-8") as f:
            before = f.read()
        out = self.client(go)
        self.assertEqual((out[0][0], out[0][1]["changed"], out[0][1]["restart"]), (200, 4, True))
        with open(self.path, encoding="utf-8") as f:
            after = f.read()
        cfg = tomllib.loads(after)
        self.assertEqual((cfg["server"]["port"], cfg["server"]["password"], cfg["autohonk"]["enabled"], cfg["journals"]["live"]),
                         (8931, "new pw", True, ["/j/a", "/j/b"]))
        self.assertIn("# The Highway map draws the galactic regions", after)   # the file's comments are kept
        with open(self.path + ".bak", encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        # refused, and nothing written: not a number, not a key, a value settings_from rejects, an empty body, not an object
        self.assertEqual([s for s, _ in out[1:]], [400] * 5)
        self.assertIn("must be a number", out[1][1]["error"])
        self.assertIn("is not a setting", out[2][1]["error"])
        self.assertIn("max_rows", out[3][1]["error"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), after)

    def test_no_file_yet_and_who_may(self):
        os.remove(self.path)

        async def go(c):
            r = await c.post("/api/config", json={"server": {"radius": 40}})
            out = [r.status]
            out.append((await c.post("/api/config", json={"server": {"radius": 30}}, headers={"Origin": "http://evil.example"})).status)
            self.state.password = "pw"
            with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):
                out.append((await c.get("/api/config")).status)
                out.append((await c.post("/api/config", json={"server": {"radius": 30}})).status)
            return out
        self.assertEqual(self.client(go), [200, 403, 401, 401])
        with open(self.path, encoding="utf-8") as f:   # made from the settings in effect, with the change
            cfg = tomllib.loads(f.read())
        self.assertEqual((cfg["server"]["radius"], cfg["server"]["port"]), (40, 8025))


class WritingFixes(unittest.TestCase):
    """The review's batch B (project/REVIEW-2026-10-04.md R2, R5, R8, R9, R10, S1): writing the config file."""

    def test_key_after_a_multiline_list(self):
        """R5: a key new to a section that ends in a list over several lines goes after its closing bracket."""
        t = ce.set_key('[server]\nport = 1\nallowed_hosts = [\n  "a",\n  "b",\n]\n\n[spansh]\n', "server", "radius", 40)
        self.assertEqual(tomllib.loads(t)["server"], {"port": 1, "allowed_hosts": ["a", "b"], "radius": 40})

    def test_whole_numbers(self):
        """R9: a fraction for a whole-number key is refused, not written as a float settings_from then drops."""
        with self.assertRaisesRegex(ValueError, "whole number"):
            ce.coerce("int", 1.5)
        with self.assertRaisesRegex(ValueError, "whole number"):
            ce.coerce("int", "2.5")
        self.assertEqual((ce.coerce("int", "3.0"), ce.coerce("int", 7)), (3, 7))
        with open(os.path.join(os.path.dirname(ed_outrider.STATIC_DIR), "static", "page.js"), encoding="utf-8") as f:
            self.assertIn('step="${k.kind === "int" ? "1" : "any"}"', f.read())   # the page's int inputs step by 1

    def test_autotarget_keys_sub_table(self):
        """R10: [highway.autotarget_keys] written as its own table is replaced by the inline form, not declared twice."""
        text = '[highway]\nautotarget = true\n\n[highway.autotarget_keys]\nEnter = "KEY_ENTER"   # mine\n\n[mcp]\nmax_rows = 9\n'
        t = ce.set_key(text, "highway", "autotarget_keys", {"Enter": "KEY_KPENTER"})
        cfg = tomllib.loads(t)
        self.assertEqual((cfg["highway"], cfg["mcp"]), ({"autotarget": True, "autotarget_keys": {"Enter": "KEY_KPENTER"}}, {"max_rows": 9}))

    def test_choices(self):
        """R8: keys with a fixed set of values are listed as choices (game_pc can go back to auto from true)."""
        secs = ce.entries(ed_outrider.config_text(settings({"server": {"game_pc": True}})), ed_outrider.config_choices())
        k = {(s["section"], k["key"]): k for s in secs for k in s["keys"]}
        self.assertEqual((k["server", "game_pc"]["kind"], k["server", "game_pc"]["value"], k["server", "game_pc"]["choices"]),
                         ("choices", "true", ["auto", "true", "false"]))
        self.assertEqual(k["highway", "autotarget_entry"]["choices"], ["type", "paste"])
        self.assertIn("pw-play", k["speech", "server_player"]["choices"])
        self.assertEqual(ce.coerce("choices", "auto", ["auto", "true", "false"]), "auto")
        with self.assertRaisesRegex(ValueError, "one of"):
            ce.coerce("choices", "maybe", ["auto", "true", "false"])

    def test_strings_round_trip(self):
        """S1: config_text quotes every string properly (a backslash, a newline, a control character); only paths
        have their backslashes turned into slashes."""
        st = settings({"server": {"password": 'a\\b"c'}, "defaults": {"speech_names": "Bob\nAlice"},
                       "assistant": {"model": "m\x7f"}})
        st["backup_dir"] = "C:\\Users\\me\\backups"
        cfg = tomllib.loads(ed_outrider.config_text(st))
        self.assertEqual((cfg["server"]["password"], cfg["defaults"]["speech_names"], cfg["assistant"]["model"], cfg["server"]["backup_dir"]),
                         ('a\\b"c', "Bob\nAlice", "m\x7f", "C:/Users/me/backups"))
        self.assertEqual(tomllib.loads(ce.set_key("", "x", "y", "m\x7f"))["x"]["y"], "m\x7f")


class WritingFile(TempConfig):
    """R2, R8, R9 through POST /api/config: the file's mode and a symlinked config."""

    def save(self, body):
        async def go(c):
            r = await c.post("/api/config", json=body)
            return r.status, await r.json()
        return self.client(go)

    def test_mode_kept(self):
        os.chmod(self.path, 0o600)
        self.assertEqual(self.save({"server": {"radius": 40}})[0], 200)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_new_file_private(self):
        os.remove(self.path)
        self.assertEqual(self.save({"server": {"radius": 40}})[0], 200)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_through_a_symlink(self):
        real = os.path.join(self.tmp, "real", "outrider.toml")
        os.makedirs(os.path.dirname(real))
        os.replace(self.path, real)
        os.symlink(real, self.path)
        self.assertEqual(self.save({"server": {"radius": 40}})[0], 200)
        self.assertTrue(os.path.islink(self.path))
        with open(real, "rb") as f:
            self.assertEqual(tomllib.load(f)["server"]["radius"], 40)
        self.assertTrue(os.path.exists(real + ".bak"))

    def test_fraction_refused(self):
        with open(self.path, encoding="utf-8") as f:
            before = f.read()
        status, d = self.save({"server": {"backup_keep": 1.5}})
        self.assertEqual(status, 400, d)
        self.assertIn("whole number", d["error"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_game_pc_back_to_auto(self):
        self.assertEqual(self.save({"server": {"game_pc": "true"}})[0], 200)
        self.assertEqual(self.save({"server": {"game_pc": "auto"}})[0], 200)
        with open(self.path, "rb") as f:
            self.assertEqual(tomllib.load(f)["server"]["game_pc"], "auto")
        self.assertEqual(self.save({"server": {"game_pc": "maybe"}})[0], 400)


if __name__ == "__main__":
    unittest.main()


class SweepConfigFixes(TempConfig):
    """The full sweep of 2026-10-09 (the config file and Server settings)."""

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_decimal_settings_take_decimals(self):
        """A decimal setting whose value is whole (speech_speed 1, autohonk delay 2) takes 1.3 and stays a decimal
        after a whole value is saved (it was offered and checked as a whole number)."""
        os.remove(self.path)                                   # the file Outrider would write
        kinds = {(s["section"], k["key"]): k["kind"] for s in self.state.config_info()["sections"] for k in s["keys"]}
        self.assertEqual((kinds["defaults", "speech_speed"], kinds["autohonk", "delay"], kinds["server", "port"]),
                         ("float", "float", "int"))
        self.assertEqual(self.state.config_save({"defaults": {"speech_speed": 2.0}})[1], 200)
        self.assertIn("speech_speed = 2.0", self.read())
        self.assertEqual(self.state.config_save({"defaults": {"speech_speed": 1.3}, "autohonk": {"delay": 2.5}})[1], 200)
        self.assertEqual(ed_outrider.load_config(self.path)["defaults"]["speech_speed"], 1.3)

    def test_saved_numbers_are_exact(self):
        self.assertEqual(self.state.config_save({"highway": {"background_extent": "-45123.75, 45000, -20000, 70000"}})[1], 200)
        self.assertEqual(ed_outrider.load_config(self.path)["highway"]["background_extent"], [-45123.75, 45000, -20000, 70000])
        self.assertEqual(ce.literal(123456.7), "123456.7")
        self.assertEqual(ce.literal(2.0), "2.0")

    def test_infinite_numbers_are_refused_not_a_500(self):
        out, status = self.state.config_save({"server": {"radius_choices": "20, inf"}})
        self.assertEqual(status, 400)
        self.assertIn("must be numbers", out["error"])
        with self.assertRaises(ValueError):
            ce.coerce("numbers", "1e999")

    def test_unquoted_password(self):
        """password = 1234 is taken as "1234"; something that is not text at all fails closed (an unknown password),
        never open (it was dropped, leaving the server without one)."""
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(settings({"server": {"password": 1234}})["password"], "1234")
            closed = settings({"server": {"password": True}})["password"]
        self.assertTrue(closed and closed != "true")

    def test_bom_is_read_and_dropped(self):
        text = self.read()
        with open(self.path, "w", encoding="utf-8-sig") as f:   # Notepad's "UTF-8 with BOM"
            f.write(text)
        self.assertEqual(ed_outrider.load_config(self.path)["server"]["password"], "hunter2")
        self.assertEqual(self.state.config_save({"defaults": {"speech_speed": 1.2}})[1], 200)
        with open(self.path, "rb") as f:
            self.assertFalse(f.read().startswith(b"\xef\xbb\xbf"))   # written back without it

    def test_a_file_that_does_not_parse_says_so(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('[server]\nport = 9000\n[journals]\nlive = ["C:\\Users\\me"]\n')   # a backslash escape: invalid
        with contextlib.redirect_stderr(io.StringIO()) as err:
            info = self.state.config_info()
        self.assertTrue(any("ignored" in p for p in info["problems"]), info["problems"])
        self.assertEqual(err.getvalue(), "")                    # said on the page, not only on the console
