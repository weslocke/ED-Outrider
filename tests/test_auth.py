"""[server] password and the Android app's native-facing contract (tablet plan, phase 1): /api/version, sign in,
sign out, the error shape, and what a device on the network may reach without a session. The test client connects
from 127.0.0.1, so "from the network" patches outrider.auth.is_loopback."""
import asyncio
import unittest
import unittest.mock
import urllib.parse

from support import ed_outrider  # also puts the repository root on sys.path

import outrider  # noqa: E402
import outrider.auth  # noqa: E402


class Base(unittest.TestCase):
    """A State with a password; client() runs a test client against its app."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, None, 25)
        self.state.password = "hunter2"

    def lan(self):
        """Requests as if from another device on the network."""
        p = unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False)
        p.start()
        self.addCleanup(p.stop)

    def client(self, go, state=None):
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(state or self.state))) as c:
                return await go(c)
        return asyncio.run(run())


class Auth(Base):
    # ---- the contract's answers: exact keys and types ----
    def test_version_is_open_and_says_nothing_else(self):
        self.lan()

        async def go(c):
            r = await c.get("/api/version")
            return r.status, await r.json()
        status, body = self.client(go)
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"outrider", "api", "min_app", "password", "signed_in", "game_pc"})   # game_pc: added 2026-10-04
        self.assertEqual((body["outrider"], body["api"], body["min_app"]), (outrider.__version__, 1, "1.0.0"))
        self.assertEqual((body["password"], body["signed_in"]), (True, False))
        self.assertIsInstance(body["outrider"], str)

    def test_signin_signout_and_the_session(self):
        self.lan()

        async def go(c):
            out = {}
            r = await c.get("/api/nearby")
            out["before"] = (r.status, await r.json())
            r = await c.post("/api/auth/signin", json={"password": "wrong"})
            out["wrong"] = (r.status, await r.json())
            r = await c.post("/api/auth/signin", json={"password": "hunter2"})
            body = await r.json()
            out["ok"] = (r.status, set(body), body["ok"])
            out["cookie"] = r.headers.get("Set-Cookie", "")
            token = body["token"]
            out["cookie_works"] = (await c.get("/api/nearby")).status   # the client keeps the cookie, as the WebView does
            c.session.cookie_jar.clear()
            out["bearer"] = (await c.get("/api/nearby", headers={"Authorization": f"Bearer {token}"})).status
            out["version"] = (await (await c.get("/api/version", headers={"Authorization": f"Bearer {token}"})).json())["signed_in"]
            # a second device signs in; the first signs out: only the first stops working
            r2 = await c.post("/api/auth/signin", json={"password": "hunter2"})
            other = (await r2.json())["token"]
            c.session.cookie_jar.clear()
            r = await c.post("/api/auth/signout", headers={"Authorization": f"Bearer {token}"})
            out["signout"] = (r.status, await r.json())
            out["after"] = (await c.get("/api/nearby", headers={"Authorization": f"Bearer {token}"})).status
            out["other"] = (await c.get("/api/nearby", headers={"Authorization": f"Bearer {other}"})).status
            return out, other
        out, other = self.client(go)
        self.assertEqual(out["before"], (401, {"error": out["before"][1]["error"], "code": "signin_required"}))
        self.assertEqual(out["wrong"], (401, {"error": "wrong password", "code": "bad_password"}))
        self.assertEqual(out["ok"], (200, {"ok", "token"}, True))
        for part in ("outrider_session=", "HttpOnly", "SameSite=Strict", "Path=/"):
            self.assertIn(part, out["cookie"])
        self.assertEqual((out["cookie_works"], out["bearer"], out["version"]), (200, 200, True))
        self.assertEqual(out["signout"], (200, {"ok": True}))
        self.assertEqual((out["after"], out["other"]), (401, 200))
        # the session survives an Outrider restart (a new State on the same database)...
        again = ed_outrider.State(self.db, self.j, None, 25)
        again.password = "hunter2"
        self.assertTrue(again.session_ok(other))
        # ...and a changed password ends every session
        again.password = "correct horse"
        self.assertFalse(again.session_ok(other))

    def test_rate_limit(self):
        self.lan()

        async def go(c):
            codes = [(await c.post("/api/auth/signin", json={"password": "no"})).status for _ in range(5)]
            r = await c.post("/api/auth/signin", json={"password": "hunter2"})   # even the right one waits now
            return codes, r.status, await r.json(), r.headers.get("Retry-After")
        codes, status, body, retry = self.client(go)
        self.assertEqual(codes, [401] * 5)
        self.assertEqual((status, body["code"]), (429, "rate_limited"))
        self.assertTrue(retry and int(retry) > 0)

    def test_bad_requests_and_an_old_app(self):
        self.lan()

        async def go(c):
            out = [(await c.post("/api/auth/signin", json=b)).status for b in ([1], {"password": 5}, {})]
            r = await c.post("/api/auth/signin", json={"password": "hunter2"}, headers={"X-Outrider-App": "0.9.0"})
            out.append((r.status, (await r.json())["code"]))
            for v in ("1.0.0", "1.0.0-debug"):
                r = await c.post("/api/auth/signin", json={"password": "hunter2"}, headers={"X-Outrider-App": v})
                out.append(r.status)
            return out
        self.assertEqual(self.client(go), [400, 400, 400, (426, "app_too_old"), 200, 200])

    # ---- what the network reaches without a session ----
    def test_pages_without_a_session(self):
        self.lan()

        async def go(c):
            out = {}
            r = await c.get("/", allow_redirects=False)
            out["browser"] = (r.status, r.headers.get("Location"))
            r = await c.get("/", headers={"User-Agent": "Mozilla/5.0 OutriderApp/1.0.0"}, allow_redirects=False)
            out["app"] = (r.status, (await r.json())["code"])
            out["static"] = (await c.get("/static/page.js")).status
            r = await c.get("/signin")
            out["signin"] = (r.status, "password" in await r.text())
            out["favicon"] = (await c.get("/static/favicon.svg")).status
            out["status"] = [(await c.get(p)).status for p in ed_outrider.OPEN_GETS]   # the overlays stay open
            out["post"] = (await c.post("/api/hush", json={"minutes": 10})).status
            # request_guard still refuses another site's request, signed in or not
            out["cross"] = (await c.post("/api/auth/signin", json={"password": "hunter2"},
                                         headers={"Origin": "http://evil.example"})).status
            return out
        out = self.client(go)
        status, where = out["browser"]
        where = urllib.parse.urlsplit(where)
        self.assertEqual((status, where.path, urllib.parse.parse_qs(where.query)), (302, "/signin", {"next": ["/"]}))
        self.assertEqual(out["app"], (401, "signin_required"))
        self.assertEqual(out["static"], 401)
        self.assertEqual(out["signin"], (200, True))
        self.assertEqual((out["favicon"], out["status"], out["post"], out["cross"]), (200, [200, 200], 401, 403))

    def test_this_pc_and_no_password_need_nothing(self):
        async def go(c):   # from 127.0.0.1, with a password set
            r = await c.get("/api/version")
            return (await c.get("/api/nearby")).status, (await r.json())["signed_in"]
        self.assertEqual(self.client(go), (200, True))
        self.lan()
        self.state.password = ""

        async def go2(c):   # no password: every device, as before
            r = await c.post("/api/auth/signin", json={"password": "anything"})
            v = await (await c.get("/api/version")).json()
            return (await c.get("/api/nearby")).status, r.status, await r.json(), (v["password"], v["signed_in"])
        self.assertEqual(self.client(go2), (200, 200, {"ok": True, "token": ""}, (False, True)))

    def test_a_proxy_on_this_pc_is_not_this_pc(self):
        """Review 2026-10-08 #3: a reverse proxy on the Outrider PC connects from 127.0.0.1 for every phone it serves.
        A loopback request carrying a forwarding header is another device's: it needs a session, and wrong passwords
        count against the client the proxy names, not against the proxy (which would lock everyone out)."""
        async def go(c):
            out = []
            for h in ({"X-Forwarded-For": "192.168.1.50"}, {"Forwarded": "for=192.168.1.50;proto=https"},
                      {"X-Real-IP": "192.168.1.50"}, {}):
                r = await c.get("/api/nearby", headers=h)
                v = await (await c.get("/api/version", headers=h)).json()
                out.append((r.status, v["signed_in"]))
            return out
        self.assertEqual(self.client(go), [(401, False), (401, False), (401, False), (200, True)])
        A = outrider.auth
        self.assertEqual(A.client_key("127.0.0.1", {"X-Forwarded-For": "10.0.0.9, 192.168.1.50"}), "192.168.1.50")
        self.assertEqual(A.client_key("127.0.0.1", {"X-Real-IP": "192.168.1.51"}), "192.168.1.51")
        self.assertEqual(A.client_key("192.168.1.7", {"X-Forwarded-For": "1.2.3.4"}), "192.168.1.7")   # not trusted
        # a proxy that sends only RFC 7239's Forwarded: each device its own count (review 2026-10-11)
        self.assertEqual(A.client_key("127.0.0.1", {"Forwarded": "for=192.168.1.50;proto=https"}), "192.168.1.50")
        self.assertEqual(A.client_key("127.0.0.1", {"Forwarded": 'for=10.0.0.1, for="[2001:db8::7]:4711"'}), "2001:db8::7")
        self.assertEqual(A.client_key("127.0.0.1", {"Forwarded": "proto=https"}), "forwarded")

    def test_inside_a_container_loopback_is_not_this_pc(self):
        """Review 2026-10-23 S4-B2: rootless Docker's and Podman's port forwarding deliver every outside connection from
        127.0.0.1 with no forwarding header, so with a password set every device on the network passed as this PC."""
        async def go(c):
            r = await c.get("/api/nearby")
            v = await (await c.get("/api/version")).json()
            return r.status, v["signed_in"], (await c.get("/api/version")).status
        with unittest.mock.patch.object(ed_outrider, "LOOPBACK_TRUSTED", False):
            self.assertEqual(self.client(go), (401, False, 200))         # signs in like any device; /api/version open
        self.assertEqual(self.client(go), (200, True, 200))              # on a PC: this PC, as before

    def test_pages_cannot_be_framed_and_inlined_values_cannot_end_the_script(self):
        """Review 2026-10-23 S4-B16: no frame-ancestors / X-Frame-Options, so another site could frame the loopback page
        (signed in by being this PC) and steer clicks; S4-B17: the search options were inlined unescaped, so a refined
        mineral's name holding "</script>" ended the page's script."""
        self.db.execute("INSERT INTO own_mined (system, body_id, commodity, name, tons) VALUES (1, 2, 'x', '</script><b>x', 5)")

        async def go(c):
            out = {}
            for path in ("/", "/tablet", "/api/version"):
                r = await c.get(path)
                out[path] = (r.headers.get("Content-Security-Policy"), r.headers.get("X-Frame-Options"),
                             await r.text() if path == "/" else None)
            return out
        got = self.client(go)
        for path in ("/", "/tablet"):
            self.assertEqual(got[path][:2], ("frame-ancestors 'self'", "SAMEORIGIN"))
        self.assertEqual(got["/api/version"][:2], (None, None))
        page = got["/"][2]
        self.assertNotIn("</script><b>x", page)
        self.assertIn("\\u003c/script>\\u003cb>x", page)

    def test_rate_limit_forgets_quiet_addresses(self):
        """Review 2026-10-11: an address that never tries again was kept for the life of the process."""
        now = [0.0]
        rl = outrider.auth.RateLimit(tries=3, window=60, clock=lambda: now[0])
        for i in range(50):
            rl.failed(f"10.0.0.{i}")
        now[0] = 61
        rl.failed("10.0.0.200")
        self.assertEqual(list(rl.failures), ["10.0.0.200"])
        for _ in range(3):
            rl.failed("10.0.0.200")
        self.assertGreater(rl.wait("10.0.0.200"), 0)   # still limited within its window

    def test_odd_tokens_are_refused_as_json(self):
        """Review 2026-10-08 #11: a token whose signature held non-ASCII characters crashed the guard (hmac compares
        ASCII only) with a plain-text 500 instead of the app's JSON 401."""
        self.lan()

        async def go(c):
            out = []
            for token in ("abc." + "é" * 32, "abc." + "z" * 32, "a b." + "0" * 32):
                r = await c.get("/api/nearby", headers={"Authorization": "Bearer " + token})
                out.append((r.status, r.content_type, (await r.json()).get("code")))
            r = await c.get("/api/nearby", cookies={"outrider_session": "abc." + "é" * 32})
            out.append((r.status, r.content_type))
            return out
        got = self.client(go)
        self.assertEqual(got[:3], [(401, "application/json", "signin_required")] * 3)
        self.assertEqual(got[3], (401, "application/json"))

    def test_infinite_ids_are_bad_requests(self):
        """Review 2026-10-08 #12: {"id": 1e999} (float inf in JSON) made int() raise OverflowError: a 500."""
        async def go(c):
            out = []
            for path in ("/api/bookmark", "/api/nextstop"):
                for raw in ('{"id": 1e999}', '{"id": 1.5}', '{"id": true}'):
                    r = await c.post(path, data=raw, headers={"Content-Type": "application/json"})
                    out.append(r.status)
            return out
        self.assertEqual(self.client(go), [400] * 6)

    def test_config_and_helpers(self):
        import argparse
        import contextlib
        import io
        import tomllib
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        self.assertEqual(ed_outrider.settings_from({}, args, None, ([], []))["password"], "")
        st = ed_outrider.settings_from({"server": {"password": "s3cret"}}, args, None, ([], []))
        self.assertEqual(tomllib.loads(ed_outrider.config_text(st))["server"]["password"], "s3cret")
        # an unquoted number is its text (it used to be dropped, leaving the server open: the sweep of 2026-10-09)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(ed_outrider.settings_from({"server": {"password": 1234}}, args, None, ([], []))["password"], "1234")
        self.assertIn("should be in quotes", err.getvalue())
        A = outrider.auth
        self.assertTrue(all(A.is_loopback(x) for x in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "127.0.0.5")))
        self.assertFalse(any(A.is_loopback(x) for x in ("192.168.1.208", "fe80::1", None, "")))
        self.assertEqual((A.version_tuple("1.10.0") > A.version_tuple("1.9.9"), A.version_tuple("x")), (True, ()))
        # a build suffix is not part of the version: a debug build is not "too old" (found by the Android app)
        self.assertEqual([A.version_tuple(v) for v in ("1.0.0-debug", "1.1.0+5", " 2.0 ", "1.0.0-rc.1+b")],
                         [(1, 0, 0), (1, 1, 0), (2, 0), (1, 0, 0)])
        self.assertEqual((A.version_tuple("-1"), A.version_tuple("")), ((), ()))
        t = A.make_token("s" * 64, "pw")
        self.assertTrue(A.check_token("s" * 64, "pw", t))
        self.assertFalse(A.check_token("s" * 64, "pw2", t))
        self.assertFalse(A.check_token("s" * 64, "pw", t, revoked={A.token_id(t)}))
        self.assertFalse(A.check_token("s" * 64, "pw", t[:-1] + ("0" if t[-1] != "0" else "1")))


class Exposure(Base):
    """The review's batch D: the sign-in page's redirect (R6) and an HTTPS reverse proxy on the LAN (R7), plus the
    start-up warning when the config looks exposed to the internet (the author: discouraged plainly)."""
    UNSAFE = ("/\\evil.com", "/\\/evil.com", "//evil.com", "https://evil.com", "/\t/evil.com", "javascript:alert(1)")

    def test_next_stays_on_this_site(self):
        for nxt in self.UNSAFE:
            self.assertFalse(ed_outrider.safe_next(nxt), nxt)
        for nxt in ("/", "/tablet", "/?view=hwy#x", "/tablet?a=%5Cb"):
            self.assertTrue(ed_outrider.safe_next(nxt), nxt)
        self.lan()

        async def go(c):
            out = []
            for nxt in ("/\\evil.com", "/tablet"):
                r = await c.get("/signin?next=" + urllib.parse.quote(nxt, safe=""), allow_redirects=False)
                out.append((r.status, r.headers.get("Location")))
            return out
        self.assertEqual(self.client(go), [(302, "/signin"), (200, None)])

    def test_page_guard(self):
        """The sign-in page's own check, run in node: anything that is not this site goes to "/"."""
        import json
        import re
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node not installed")
        fn = re.search(r"function safeNext\(.*?\n}", ed_outrider.SIGNIN_PAGE, re.S).group(0)
        cases = list(self.UNSAFE) + ["/tablet?x=1", "/settings#s"]
        js = fn + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map(n => safeNext(n, 'http://mypc.lan:8025'))));"
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(out.stdout), ["/"] * len(self.UNSAFE) + ["/tablet?x=1", "/settings#s"], out.stderr)

    def test_https_proxy_on_the_lan(self):
        """A reverse proxy serving https://outrider.lan forwards Host without a port: answered, and its https Origin
        accepted for a change; another site's https Origin still refused."""
        self.state.password = ""
        hosts = ed_outrider.allowed_hosts("0.0.0.0", 8025, ["outrider.lan"], own=lambda: set())

        async def go(c):
            out = []
            for host, origin in (("outrider.lan", "https://outrider.lan"), ("outrider.lan", "https://evil.example"),
                                 ("outrider.lan:8025", "http://outrider.lan:8025"), ("other.lan", "https://other.lan")):
                r = await c.post("/api/hush", json={"mode": "off"}, headers={"Host": host, "Origin": origin})
                out.append(r.status)
            return out

        async def run():
            from aiohttp.test_utils import TestClient, TestServer
            async with TestClient(TestServer(ed_outrider.make_app(self.state, hosts))) as c:
                return await go(c)
        self.assertEqual(asyncio.run(run()), [200, 403, 200, 403])

    def test_exposure_warning(self):
        W = ed_outrider.exposure_warnings
        self.assertTrue(any("internet" in w and "outrider.example.com" in w for w in W("0.0.0.0", "pw", ["outrider.example.com"])))
        self.assertTrue(any("internet" in w for w in W("0.0.0.0", "pw", ["8.8.8.8:8025"])))
        self.assertEqual(W("0.0.0.0", "pw", ["mypc.lan", "tablet", "box.local", "nas.home.arpa", "192.168.1.9", "10.0.0.2:8025",
                                             "[fd00::1]", "pc.internal", "pc.home"]), [])
        self.assertTrue(any("password" in w for w in W("0.0.0.0", "", [])))
        # what a device on the network can do with no password, not only read and edit bookmarks (the review)
        self.assertTrue(any(all(x in w for x in ("settings", "restart", "EDSM", "press keys")) for w in W("0.0.0.0", "", [])))
        self.assertEqual((W("127.0.0.1", "", []), W("0.0.0.0", "pw", [])), ([], []))


if __name__ == "__main__":
    unittest.main()


class SystemExport(Base):
    """Plugin gaps F (Pioneer's export): one system's bodies and values as CSV from Here."""

    def test_export(self):
        import types
        self.state.spansh = types.SimpleNamespace(cached=lambda i: (None, None))
        self.j.handle({"event": "FSDJump", "timestamp": "2026-01-01T00:00:00Z", "StarSystem": "Sol B", "SystemAddress": 5,
                       "StarPos": [0, 0, 0]})
        self.j.handle({"event": "Scan", "timestamp": "2026-01-01T00:01:00Z", "BodyName": "Sol B 1", "BodyID": 1, "StarSystem": "Sol B",
                       "SystemAddress": 5, "PlanetClass": "High metal content body", "MassEM": 1.0, "Landable": True,
                       "ScanType": "Detailed", "WasDiscovered": False, "WasMapped": False, "DistanceFromArrivalLS": 400.0})

        async def go(c):
            r = await c.get("/api/export?what=system&id=5")
            out = [r.status, r.headers.get("Content-Disposition"), (await r.text()).splitlines()]
            out.append((await c.get("/api/export?what=system&id=x")).status)
            out.append((await c.get("/api/export?what=system&id=77")).status)
            return out
        status, disp, lines, bad, unknown = self.client(go)
        self.assertEqual(status, 200)
        self.assertIn('filename="system-Sol_B-', disp)
        self.assertTrue(lines[0].startswith("body,type,subtype,distance_ls,landable"))
        self.assertTrue(lines[1].startswith("1,Planet,High metal content world,400.0,True,False,0,0,,True,False,"))
        self.assertEqual((bad, unknown), (400, 404))


class Paste(Base):
    """#5's 📋 buttons: the game PC's clipboard for this PC's own browser and the Android app (its User-Agent), not for
    another browser on the network (the author, 2026-10-14: a filter, not a lock). Never a real clipboard."""

    APP_UA = "Mozilla/5.0 (Linux; Android 14; wv) AppleWebKit/537.36 Chrome/129.0 Mobile Safari/537.36 OutriderApp/1.3.0"

    def setUp(self):
        super().setUp()
        import types
        self.state.password = ""
        self.state.game_pc = True
        self.state.clipboard = types.SimpleNamespace(read_tool="xclip", paste_why=lambda: None,
                                                     paste=lambda: {"text": "Smojooe GW-W c1-4"})

    def ask(self, ua=None):
        headers = {"User-Agent": ua} if ua else {}

        async def go(c):
            r = await c.get("/api/clipboard", headers=headers)
            can = (await r.json())["can"]
            r = await c.post("/api/clipboard/paste", headers=headers)
            return can, r.status, await r.json()
        return self.client(go)

    def test_this_pc(self):
        self.assertEqual(self.ask(), (True, 200, {"text": "Smojooe GW-W c1-4"}))

    def test_another_browser_is_refused(self):
        self.lan()
        can, status, body = self.ask("Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0")
        self.assertEqual((can, status, body["code"]), (False, 403, "not_this_device"))

    def test_the_android_app(self):
        self.lan()
        self.assertEqual(self.ask(self.APP_UA), (True, 200, {"text": "Smojooe GW-W c1-4"}))

    def test_a_server_has_no_game_pc_clipboard(self):
        self.state.game_pc = False
        can, status, body = self.ask()
        self.assertEqual((can, status, body["code"]), (False, 409, "not_game_pc"))
