"""Unit tests: the read-only lookups' health (S42, outrider/health.py's Health): which source is down, fed by an aiohttp
TraceConfig on the lookups' session; the short form on the page ("Spansh unavailable"); a card on the banner when it
lasts. Nothing here touches the network: the trace is fed by a local server on a free port, or called directly.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import contextlib
import io
import socket
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.health as H  # noqa: E402


class HealthTests(unittest.TestCase):

    def setUp(self):
        self.now = [1000.0]
        self.h = H.Health(clock=lambda: self.now[0])
        self.changes = []
        self.h.on_change = lambda: self.changes.append(self.h.summary())

    def test_down_then_back(self):
        self.h.failed("spansh", TimeoutError(), started=999)
        d = self.h.down()
        self.assertEqual([(x["source"], x["name"], x["kind"], x["user_fix"], x["since"]) for x in d],
                         [("spansh", "Spansh", "timeout", False, 1000.0)])
        self.assertEqual(self.h.text("spansh"), "Spansh unavailable")
        self.now[0] = 1100
        self.h.failed("spansh", TimeoutError(), started=1090)   # the same outage: its start kept, no second change
        self.assertEqual((self.h.down()[0]["since"], len(self.changes)), (1000.0, 1))
        self.h.ok("spansh")
        self.assertEqual((self.h.down(), len(self.changes)), ([], 2))

    def test_a_failure_older_than_an_answer_does_not_count(self):
        """Fifty body lookups at once, one times out after others answered: Spansh is not down."""
        self.h.ok("spansh", at=1005)
        self.assertFalse(self.h.failed("spansh", TimeoutError(), started=1001, at=1060))
        self.assertEqual(self.h.down(), [])
        self.assertTrue(self.h.failed("spansh", TimeoutError(), started=1010, at=1070))

    def test_no_internet_needs_two_sources(self):
        dns = socket.gaierror(-2, "Name or service not known")
        self.h.failed("spansh", dns)
        self.assertFalse(self.h.offline())
        self.assertEqual(self.h.text("spansh"), "Spansh unavailable")
        self.h.failed("github", TimeoutError())       # not a DNS failure: still not "no internet"
        self.assertFalse(self.h.offline())
        self.h.failed("edsm", dns)
        self.assertTrue(self.h.offline())
        self.assertEqual(self.h.text("spansh"), "No internet connection")
        self.h.ok("canonn")                           # anything answering: the network is up
        self.assertFalse(self.h.offline())
        # and the "no network" failures are out of date with it; GitHub's timeout stays until GitHub answers
        self.assertEqual({x["source"] for x in self.h.down()}, {"github"})

    def test_status_codes(self):
        self.h.failed("spansh", status=503)
        self.assertEqual(self.h.down()[0]["kind"], "http5xx")
        self.h.failed("edsm", status=429)
        self.assertEqual(self.h.down()[1]["kind"], "rate")

    def test_forgotten_when_nothing_asks(self):
        self.h.failed("github", TimeoutError())
        self.now[0] += H.DOWN_FRESH_S - 1
        self.assertFalse(self.h.expire())
        self.now[0] += 1
        self.assertTrue(self.h.expire())
        self.assertEqual(self.h.down(), [])

    def test_sources_by_host(self):
        self.assertEqual([H.source_of_host(u) for u in ("https://spansh.co.uk/api/systems/search", "https://www.edsm.net/api-v1/system",
                                                       "https://api.github.com/repos/x/y", "https://edastro.com/json/DSSA-carriers.json",
                                                       ed_outrider.outrider.codex_images.REF, "https://inara.cz/inapi/v1/",
                                                       "not a url")],
                         ["spansh", "edsm", "github", "edastro", "canonn", None, None])

    def test_lookup_source_follows_patched_urls(self):
        """verify.sh and the tests point the URLs elsewhere: the constants still name the source."""
        with unittest.mock.patch.object(ed_outrider, "SPANSH_DUMP", "http://127.0.0.1:9/dump/{id64}"), \
                unittest.mock.patch.object(ed_outrider, "RELEASES_LATEST", "http://127.0.0.1:9/gh"):
            self.assertEqual(ed_outrider.lookup_source("http://127.0.0.1:9/dump/123"), "spansh")
            self.assertEqual(ed_outrider.lookup_source("http://127.0.0.1:9/gh"), "github")
        self.assertIsNone(ed_outrider.lookup_source("https://eddn.edcd.io:4430/upload/"))   # an upload: not a lookup
        self.assertIsNone(ed_outrider.lookup_source("https://inara.cz/inapi/v1/"))


class TraceTests(unittest.TestCase):
    """The TraceConfig on a real aiohttp session against a local server: every request reports, no call site does."""

    def test_trace(self):
        from aiohttp import ClientSession, web

        async def go():
            codes = iter([200, 503, 404])

            async def handler(request):
                return web.Response(status=next(codes), text="x")
            app = web.Application()
            app.router.add_get("/{tail:.*}", handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            h, seen = H.Health(), []
            source = lambda url: "spansh" if str(url).startswith(base) else None
            try:
                async with ClientSession(trace_configs=[h.trace_config(source)]) as s:
                    for _ in range(3):
                        async with s.get(base + "/a") as r:
                            await r.read()
                        seen.append([x["kind"] for x in h.down()])
                    # nothing listening: refused
                    free = socket.socket()
                    free.bind(("127.0.0.1", 0))
                    closed = free.getsockname()[1]
                    free.close()
                    with contextlib.suppress(Exception):
                        async with s.get(f"http://127.0.0.1:{closed}/x"):
                            pass
                    seen.append([x["kind"] for x in h.down()])   # not a lookup source: nothing
                    h2 = H.Health()
                    async with ClientSession(trace_configs=[h2.trace_config(lambda u: "edsm")]) as s2:
                        with contextlib.suppress(Exception):
                            async with s2.get(f"http://127.0.0.1:{closed}/x"):
                                pass
                    seen.append([x["kind"] for x in h2.down()])
            finally:
                await runner.cleanup()
            return seen
        self.assertEqual(asyncio.run(go()), [[], ["http5xx"], [], [], ["refused"]])


class StateTests(unittest.TestCase):
    """The server's side: the short form in the status, the payload's health, the banner's card."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def test_spansh_shares_its_health_with_state(self):
        sp = ed_outrider.Spansh(self.db)
        st = ed_outrider.State(self.db, self.j, sp, 25)
        self.assertIs(st.health, sp.health)
        self.assertEqual(st.payload()["health"], {"down": [], "offline": False})

    def test_short_form_only(self):
        """S42: "Spansh unavailable" or "No internet connection", never the error's text."""
        import outrider.health
        dns = socket.gaierror(-2, "Name or service not known")

        async def down(pos, r):
            self.state.health.failed("spansh", dns)
            raise ed_outrider.ClientError("Cannot connect to host spansh.co.uk:443 ssl:default [Name or service not known]")

        async def nothing(pos, r):
            return []
        self.state.spansh = types.SimpleNamespace(sphere=down, edsm_sphere=nothing, cached=lambda i: (None, None),
                                                  store=lambda *a, **k: None)
        self.j.handle({"event": "FSDJump", "timestamp": "2026-10-12T00:00:00Z", "StarSystem": "Here", "SystemAddress": 1,
                       "StarPos": [0, 0, 0]})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(self.state.status, "Spansh unavailable")
        self.assertIn("Name or service not known", err.getvalue())   # the detail: in the log only
        with contextlib.redirect_stderr(io.StringIO()):
            self.state.health.failed("edsm", dns)
            asyncio.run(self.state._refresh(self.j.pos))
        self.assertEqual(self.state.status, outrider.health.OFFLINE)
        p = self.state.payload()["health"]
        self.assertTrue(p["offline"])
        self.assertEqual([d["source"] for d in p["down"]], ["spansh", "edsm"])

    def test_a_bug_is_not_an_outage(self):
        async def broken(pos, retry=False):
            raise KeyError("x")
        self.state._refresh = broken
        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(self.state.refresh({"name": "Here"}))
        self.assertTrue(self.state.status.startswith("refresh failed — retrying in"))
        self.assertNotIn("KeyError", self.state.status)

    def cards(self):
        return {n["key"]: n["text"] for n in self.state.notices.active()}

    def test_banner(self):
        import time
        st, now = self.state, time.time()
        with contextlib.redirect_stderr(io.StringIO()):
            st.health.failed("spansh", TimeoutError(), at=now)
            self.assertEqual(self.cards(), {})                      # a short outage: the tile only
            st.check_lookup_outages(now + ed_outrider.LOOKUP_DOWN_S - 1)
            self.assertEqual(self.cards(), {})
            st.check_lookup_outages(now + ed_outrider.LOOKUP_DOWN_S)
            text = self.cards()["lookup_down:spansh"]
            self.assertIn("Spansh has been unavailable for over 10 minutes (not answering)", text)
            st.check_lookup_outages(now + ed_outrider.LOOKUP_DOWN_S + 600)
            self.assertEqual(self.cards()["lookup_down:spansh"], text)   # the same words: a dismissal holds
            st.health.failed("github", TimeoutError(), at=now)          # GitHub: no card for a long outage
            st.check_lookup_outages(now + ed_outrider.LOOKUP_DOWN_S + 600)
            self.assertEqual(set(self.cards()), {"lookup_down:spansh"})
            st.health.ok("spansh")                                       # back: the card goes at once (on_change)
            self.assertEqual(set(self.cards()), set())
            st.health.failed("edsm", socket.gaierror(-2, "x"))           # no address: a card at once
            self.assertIn("EDSM unavailable: its address is not found", self.cards()["lookup_down:edsm"])
            st.health.failed("spansh", socket.gaierror(-2, "x"))         # two sources by DNS: no internet, one card
            self.assertEqual(list(self.cards()), ["lookup_down:internet"])
            self.assertTrue(self.cards()["lookup_down:internet"].startswith("No internet connection"))
            st.health.ok("spansh")
            self.assertEqual(self.cards(), {})


if __name__ == "__main__":
    unittest.main()
