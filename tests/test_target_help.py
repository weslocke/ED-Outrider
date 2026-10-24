"""The auto-target steps' cheatsheet (outrider/target_help.py, GET /help/autotarget): built from outrider.target, so
it lists what the steps accept and nothing else."""
import asyncio
import types
import unittest

import ed_outrider
import outrider.target as T
import outrider.target_help as H
from outrider import honk


class Cheatsheet(unittest.TestCase):
    def test_every_control_and_key_is_explained(self):
        self.assertEqual(set(T.KEY_HELP), set(T.ACTIONS) | set(T.FIXED_KEYS))   # in step with the controls
        self.assertEqual(H.ungrouped(), [])                                       # every key name is listed

    def test_the_page(self):
        page = H.cheatsheet_html({"UI_Select": (["KEY_SPACE"], "binding"), "GalaxyMapOpen": (["KEY_LEFTALT", "KEY_RIGHTALT", "KEY_T"], "b"),
                                  "UI_Down": (None, "UI Down has no keyboard binding")})
        for name in T.ACTIONS + tuple(T.FIXED_KEYS):
            self.assertIn(f"<code>{name}</code>", page)
        for step in T.DEFAULT_SEARCH + T.DEFAULT_SUBMIT + T.DEFAULT_PLOT + T.DEFAULT_TARGET:        # each box's default, as ↺ puts it
            self.assertIn(step, page)
        self.assertIn("<th>Your key</th>", page)
        self.assertIn("<td>Space</td>", page)
        self.assertIn("<td>Left Alt + Right Alt + T</td>", page)
        self.assertIn('<td class="warn">UI Down has no keyboard binding</td>', page)
        self.assertIn("<code>DOWN</code>", page)
        self.assertIn("<code>LEFTBRACE</code> <span class=\"muted\">[</span>", page)   # the character it types
        self.assertIn("<code>alt</code> is Left Alt", page)
        self.assertIn("autotarget_keys", page)
        # each alias the page names is one the steps take: parse_combo reads it as that key
        for word, key in H.ALIASES:
            self.assertEqual(honk.parse_combo(word), [key])
        self.assertEqual(honk.parse_combo("down"), ["KEY_DOWN"])
        self.assertEqual(T.parse_step("PRESS ui_select"), {"do": "press", "keys": "UI_Select"})
        # no preset read (a server, Docker): no column
        self.assertNotIn("Your key", H.cheatsheet_html(None))

    def test_the_route(self):
        from aiohttp.test_utils import TestClient, TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        state.targeter = types.SimpleNamespace(available=True, bindings=lambda: {"UI_Select": (["KEY_SPACE"], "b")})

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                r = await c.get("/help/autotarget")
                return r.status, r.headers["Content-Type"], await r.text()
        status, ctype, text = asyncio.run(go())
        self.assertEqual((status, ctype.split(";")[0]), (200, "text/html"))
        self.assertIn("<title>Auto-target steps: cheatsheet</title>", text)
        self.assertIn("<td>Space</td>", text)



class EntryCheck(unittest.TestCase):
    """S7-S1: the Auto-target box says whether typing (US key positions) and paste (the clipboard tool) can work here."""

    def test_the_words(self):
        E = T.entry_check
        self.assertEqual(E("us", "xclip"), {"typing": "typing: US layout ✓", "paste": "paste: xclip ✓"})
        self.assertEqual(E("de,us", "wl-copy")["typing"], "typing: US key positions are typed and your layout is de,us: prefer paste")
        self.assertIn("takes the keyboard focus", E("de", "wl-copy")["paste"])
        self.assertIn("layout unknown", E(None, None)["typing"])
        self.assertIn("install xclip", E(None, None)["paste"])

    def test_the_layout_is_read_not_pressed(self):
        import subprocess
        import support
        calls = []

        def run(argv, **kw):
            calls.append(argv[0])
            if argv[0] == "setxkbmap":
                raise FileNotFoundError(argv[0])
            return subprocess.CompletedProcess(argv, 0, stdout="   System Locale: LANG=de_DE.UTF-8\n       X11 Layout: de\n")
        self.assertEqual(support.REAL_KEYBOARD_LAYOUT(run=run, platform="linux"), "de")
        self.assertEqual(calls, ["setxkbmap", "localectl"])
        ok = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout="rules:      evdev\nlayout:     us\n")
        self.assertEqual(support.REAL_KEYBOARD_LAYOUT(run=ok, platform="linux"), "us")


if __name__ == "__main__":
    unittest.main()

