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
                          "assistant", "mcp", "eddn", "edsm", "inara"])
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


class FindASetting(unittest.TestCase):
    def test_data_find_names_real_keys(self):
        """S39: a browser row whose default comes from the config file names that key (data-find="section.key"), so
        Find a setting finds it by the key too: every one named is a key the config file has, and the Voice row's
        speech_speed is among them."""
        import re
        with open(os.path.join(ed_outrider.STATIC_DIR, "page.html"), encoding="utf-8") as f:
            html = f.read()
        named = [k for v in re.findall(r'data-find="([^"]*)"', html) for k in v.split()]
        keys = {f"{s['section']}.{k['key']}" for s in ce.entries(ed_outrider.config_text(settings({}))) for k in s["keys"]}
        self.assertGreaterEqual(len(named), 20)
        self.assertEqual([k for k in named if k not in keys], [])
        self.assertIn("defaults.speech_speed", named)
        self.assertIn('id="setFind"', html)

    def test_server_list_by_purpose(self):
        """The author, 2026-10-23: Settings -> Server lists only the keys with no section of their own, grouped by purpose
        (config_edit.GROUPS); every other key is homed (its section's data-find finds it: the smoke test checks the
        page), Uploads' are hidden. Every key the file has is one or the other, and none falls into "Other"."""
        sections = ce.entries(ed_outrider.config_text(settings({})))
        groups = ce.server_groups(sections)
        listed = {(k["section"], k["key"]) for g in groups for k in g["keys"]}
        homed = {(s["section"], k["key"]) for s in sections for k in s["keys"] if ce.homed(s["section"], k["key"])}
        hidden = {(s["section"], k["key"]) for s in sections if s["section"] in ce.HIDDEN_SECTIONS for k in s["keys"]}
        every = {(s["section"], k["key"]) for s in sections for k in s["keys"]}
        self.assertEqual(listed | homed | hidden, every)
        self.assertFalse(listed & homed)
        self.assertNotIn(ce.OTHER[0], [g["group"] for g in groups])            # each listed key in a named group
        self.assertEqual([g["group"] for g in groups], [g[0] for g in ce.GROUPS])
        self.assertLess(len(listed), 50)
        for k in (("defaults", "bio_min"), ("highway", "autotarget"), ("autohonk", "enabled"), ("overlay", "radar_range"),
                  ("copilot", "device"), ("speech", "pad_delay")):
            self.assertIn(k, homed)
        for k in (("server", "port"), ("journals", "live"), ("highway", "clipboard"), ("assistant", "model")):
            self.assertIn(k, listed)


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
        pw = next(k for g in d["groups"] for k in g["keys"] if (k["section"], k["key"]) == ("server", "password"))
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


class ReviewConfigFixes(unittest.TestCase):
    """The full review of 2026-10-11: values of the wrong type are reported and the default kept, as the example file
    promises; backup_dir is written relative to the Outrider folder, like db."""

    def test_wrong_types_are_reported(self):
        cfg = {"defaults": {"module_warn": True, "unsold_warn": True, "voice": True},
               "server": {"radius": True, "db": 5, "backup_dir": 5}, "autohonk": {"key": 5}}
        with contextlib.redirect_stderr(io.StringIO()) as err:
            st = ed_outrider.settings_from(cfg, ARGS, None, ([], []))
        d = settings({})
        for k in ("module_warn", "unsold_warn", "voice", "radius", "db", "backup_dir"):
            self.assertEqual(st[k], d[k], k)
        self.assertEqual(st["autohonk"]["key"], d["autohonk"]["key"])
        said = err.getvalue()
        for k in ("module_warn", "unsold_warn", "voice", "radius", "db", "backup_dir", "key"):
            self.assertIn(f"] {k} = ", said, k)

    def test_the_temp_config_is_ignored(self):
        """Server settings write through ed_outrider.toml.new, which holds the password while it exists: git ignores it as
        .dockerignore does (a whole line: .gitignore has no comments after a pattern)."""
        root = os.path.dirname(ed_outrider.STATIC_DIR)
        for name in (".gitignore", ".dockerignore"):
            with open(os.path.join(root, name), encoding="utf-8") as f:
                self.assertIn("ed_outrider.toml.new", [line.strip() for line in f], name)

    def test_backup_dir_written_relative(self):
        text = ed_outrider.config_text(settings({}))
        self.assertIn('backup_dir = "data/backups"', text)


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



class DialogLayout(unittest.TestCase):
    def test_wide_sections_span_the_columns(self):
        """On a big screen Settings runs in columns; Server settings, Spoken lines and Voice (the author, 2026-10-16:
        its crew and voice tables need the room), Alerts and Questions asked (2026-10-23) span them all."""
        import re
        with open(os.path.join(ed_outrider.STATIC_DIR, "page.css"), encoding="utf-8") as f:
            css = f.read()
        with open(os.path.join(ed_outrider.STATIC_DIR, "page.html"), encoding="utf-8") as f:
            html = f.read()
        rule = re.search(r"([^{}]*)\{\s*column-span:\s*all;\s*\}", css)
        wide = set(re.findall(r"#alertDialog #(\w+)", rule.group(1)))
        self.assertEqual(wide, {"serverSettings", "speechLogBox", "voiceSettings", "alertsSettings", "askLogBox"})
        for sid in wide:
            self.assertRegex(html, r'<details[^>]*class="[^"]*setsec[^"]*"[^>]*id="%s"|<details id="%s"[^>]*setsec' % (sid, sid), sid)
        # the author, 2026-10-23: there the Alerts table's Crew column does not wrap (the member's name, the danger note)
        # ...under the layout's own condition, Alerts' table only (review 2026-10-23 L3)
        wide_crew = re.search(r"@media \(min-width: 1280px\) and \(min-height: 700px\) \{\s*#alertDialog #alertsSettings \.alerttable td\.acrew \{([^}]*)\}\s*"
                              r"#alertDialog #alertsSettings \.alerttable td\.acrew select \{([^}]*)\}", css)
        self.assertTrue(wide_crew, "the wide Crew column's rule")
        self.assertIn("white-space: nowrap", wide_crew.group(1))
        self.assertIn("max-width: none", wide_crew.group(2))


if __name__ == "__main__":
    unittest.main()


class HomedKeys(TempConfig):
    """The author, 2026-10-23: the keys taken out of the Server list got fields in their own sections. Auto honk's wait
    and skip are read on every honk, so a save applies them at once; its key and hold, and the co-pilot button, wait for
    the next start. The overlay's system-panel time and radar range go through POST /api/overlay like its other fields."""

    def test_auto_honk_and_copilot_fields(self):
        s = self.state
        out, status = s.config_save({"autohonk": {"delay": 3.5, "skip_honked": False}})
        self.assertEqual((status, out["restart"], sorted(out["live"])), (200, False, ["autohonk.delay", "autohonk.skip_honked"]))
        self.assertEqual((s.autohonk["delay"], s.autohonk["skip_honked"]), (3.5, False))
        out, status = s.config_save({"autohonk": {"hold": 4.0}, "copilot": {"enabled": True, "device": "X56", "button": "BTN_TRIGGER_HAPPY5"}})
        self.assertEqual((status, out["restart"]), (200, True))         # the Honker and the button are built at start
        homed = {(x["section"], k["key"]): k["value"] for x in s.config_info()["homed"] for k in x["keys"]}
        self.assertEqual((homed["autohonk", "hold"], homed["copilot", "device"], homed["copilot", "enabled"]), (4.0, "X56", True))
        # review 2026-10-23 L5: out of range is refused in words, not written and then clamped silently
        with open(self.path, encoding="utf-8") as f:
            before = f.read()
        for change, why in (({"copilot": {"hold_ms": 100}}, "[copilot] hold_ms must be 200 to 3000 ms"),
                            ({"copilot": {"double_ms": 2000}}, "[copilot] double_ms must be 100 to 1000 ms"),
                            ({"autohonk": {"hold": 25.0}}, "[autohonk] hold must be 0.5 to 20 s"),
                            ({"autohonk": {"delay": 45.0}}, "[autohonk] delay must be 0 to 30 s")):
            self.assertEqual(s.config_save(change), ({"error": why}, 400))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_every_clamped_number_is_refused_out_of_range(self):
        """Review 2026-10-23 S1-B1: out of range was refused for four keys only; every other number was written and then
        clamped silently, the field coming back with a number nobody typed. CONFIG_RANGES is the one list, and it must
        match settings_from's own clamps (a hand-edited file is still clamped, as documented)."""
        import argparse
        import contextlib
        import io
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)

        def read(section, key, value):
            with contextlib.redirect_stderr(io.StringIO()):
                st = ed_outrider.settings_from({section: {key: value}}, args, None, ([], []))
            return st[section][key] if isinstance(st.get(section), dict) and key in st[section] else st[key]
        for (section, key), (lo, hi, _unit) in ed_outrider.CONFIG_RANGES.items():
            self.assertEqual(read(section, key, lo - (1 if lo >= 1 else 0.01 if lo else 1)), lo, (section, key))
            if hi is not None:
                self.assertEqual(read(section, key, hi + 1), hi, (section, key))
        s = self.state
        with open(self.path, encoding="utf-8") as f:
            before = f.read()
        for change, why in (({"highway": {"efficiency": 150}}, "[highway] efficiency must be 1 to 100 %"),
                            ({"highway": {"autotarget_map_wait": 0.2}}, "[highway] autotarget_map_wait must be 1 to 30 s"),
                            ({"spansh": {"concurrency": 0}}, "[spansh] concurrency must be at least 1"),
                            ({"speech": {"pad_delay": 25}}, "[speech] pad_delay must be 0 to 20 s")):
            self.assertEqual(s.config_save(change), ({"error": why}, 400), change)
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_overlay_system_seconds_and_radar_range(self):
        s = self.state
        out, status = s.overlay_set({"system_seconds": 30, "radar_range": 50})
        self.assertEqual(status, 200, out)
        self.assertEqual((out["system_seconds"], out["radar_range"]), (30, 100))   # the radar's range clamped to 100..20000
        with open(self.path, encoding="utf-8") as f:
            self.assertIn("system_seconds = 30", f.read())
        self.assertEqual(s.overlay_set({"radar_range": "far"})[1], 400)


class SweepConfigFixes(TempConfig):
    """The full sweep of 2026-10-09 (the config file and Server settings)."""

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_decimal_settings_take_decimals(self):
        """A decimal setting whose value is whole (speech_speed 1, autohonk delay 2) takes 1.3 and stays a decimal
        after a whole value is saved (it was offered and checked as a whole number)."""
        os.remove(self.path)                                   # the file Outrider would write
        info = self.state.config_info()   # the Server list's groups and the homed keys (Voice's speech_speed, auto honk's delay)
        kinds = {(k["section"], k["key"]): k["kind"] for g in info["groups"] for k in g["keys"]}
        kinds.update({(s["section"], k["key"]): k["kind"] for s in info["homed"] for k in s["keys"]})
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
