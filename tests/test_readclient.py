"""Unit tests: EDSM's and Inara's account reads (G3, outrider/readclient.py) and Settings -> Uploads' Check buttons for
the keys (S45). Fake sessions answer with the documented example replies (tests/fixtures/account_checks.json); nothing
here reaches EDSM or Inara, and no real key is used.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import json
import os
import re
import types
import unittest
import unittest.mock

from support import ed_outrider, _HwSession  # also puts the repository root on sys.path
import outrider.readclient as RC  # noqa: E402
import outrider.uploads as U  # noqa: E402
import outrider.inara  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "fixtures", "account_checks.json"), encoding="utf-8") as _f:
    EX = json.load(_f)
EDSM_KEY = "0123456789abcdef0123456789abcdef01234567"
INARA_KEY = "a1B2c3D4e5F6g7H8i9J0k1L2"


class Parsers(unittest.TestCase):

    def test_edsm_credits(self):
        self.assertEqual(RC.edsm_credits_answer(EX["edsm_credits_ok"]), {"ok": True, "code": 100, "text": "OK", "balance": 1234567890})
        got = RC.edsm_credits_answer(EX["edsm_credits_wrong"])
        self.assertEqual((got["ok"], got["code"], got["text"]), (False, 203, "commander name or API key not found"))
        for bad in ([], {"msg": "OK"}, "x"):
            with self.assertRaises(ValueError):
                RC.edsm_credits_answer(bad)
        # complete review 2026-10-30: a known commander with no credits yet (a new account) is not a refused key
        self.assertEqual(RC.edsm_credits_answer({"msgnum": 208, "msg": "No credits stored"}),
                         {"ok": True, "code": 208, "text": "no credits stored yet", "balance": None})

    def test_edsm_position_and_logs(self):
        p = RC.edsm_position_answer(EX["edsm_position_ok"])
        self.assertEqual((p["system"], p["id64"], p["coords"], p["date"]),
                         ("Sample Reach", 2869708101329, {"x": 12.5, "y": -3.25, "z": 40.0}, "2026-10-09T21:14:05Z"))
        logs = RC.edsm_logs_answer(EX["edsm_logs_ok"])["logs"]
        self.assertEqual([(e["system"], e["date"], e["first_discover"], e["coords"]) for e in logs],
                         [("Sample Gate", "2026-10-08T10:00:00Z", True, {"x": 1.0, "y": 2.0, "z": 3.0}),
                          ("Sample Reach", "2026-10-09T21:14:05Z", False, None)])   # oldest first
        self.assertFalse(RC.edsm_logs_answer(EX["edsm_credits_wrong"])["ok"])
        req = RC.edsm_logs_request("Sample Pilot", EDSM_KEY, 0, 86400)
        self.assertEqual((req["startDateTime"], req["endDateTime"], req["showId"]), ("1970-01-01 00:00:00", "1970-01-02 00:00:00", "1"))
        with self.assertRaises(ValueError):   # EDSM answers a week at most
            RC.edsm_logs_request("Sample Pilot", EDSM_KEY, 0, RC.EDSM_LOGS_WINDOW_S + 1)

    def test_inara_profile(self):
        body = RC.inara_profile_request(INARA_KEY, "Sample Pilot", "1.0", "ED Outrider", when=0)
        self.assertEqual(body["events"], [{"eventName": "getCommanderProfile", "eventTimestamp": "1970-01-01T00:00:00Z",
                                           "eventData": {"searchName": "Sample Pilot"}}])
        self.assertEqual(body["header"]["APIkey"], INARA_KEY)
        ok = RC.inara_profile_answer(EX["inara_profile_ok"])
        self.assertEqual((ok["ok"], ok["name"], ok["url"]), (True, "Sample Pilot", "https://inara.cz/elite/cmdr/1/"))
        none = RC.inara_profile_answer(EX["inara_profile_none"])
        self.assertEqual((none["ok"], none["code"]), (False, 204))
        wrong = RC.inara_profile_answer(EX["inara_key_wrong"], outrider.inara.RATE_WORDS)
        self.assertEqual((wrong["ok"], wrong["code"], wrong["rate"], wrong["text"]), (False, 400, False, "Invalid API key."))
        self.assertTrue(RC.inara_profile_answer(EX["inara_rate"], outrider.inara.RATE_WORDS)["rate"])
        evil = dict(EX["inara_profile_ok"], events=[{"eventStatus": 200, "eventData": {"commanderName": "X", "inaraURL": "javascript:x"}}])
        self.assertIsNone(RC.inara_profile_answer(evil)["url"])   # only Inara's own links are offered


class Retrying(unittest.TestCase):
    """The long reads' retry (S67's import, S47's Check and guard): what passes is asked again, a refusal is not."""

    def test_which_failures_pass(self):
        from outrider.health import HttpError, classify
        ok = RC.edsm_logs_answer(EX["edsm_logs_ok"])
        self.assertIs(RC.try_later(ok), ok)
        wrong = RC.edsm_logs_answer(EX["edsm_credits_wrong"])
        self.assertIs(RC.try_later(wrong), wrong)                      # a refused key is the caller's to read: no retry
        with self.assertRaises(RC.TryLater) as failing:
            RC.try_later(RC.edsm_logs_answer({"msgnum": 500, "msg": "Exception"}))
        self.assertEqual(RC.transient(failing.exception), "http5xx")
        with self.assertRaises(HttpError) as slow:
            RC.try_later(RC.edsm_logs_answer({"msgnum": 299, "msg": "Too many requests, try again later"}))
        self.assertEqual(classify(slow.exception)[0], "rate")
        for exc, kind in ((asyncio.TimeoutError(), "timeout"), (ConnectionResetError(), "refused"), (HttpError(503, "HTTP 503"), "http5xx")):
            self.assertEqual(RC.transient(exc), kind)
        for exc in (ValueError("the answer has no msgnum"), HttpError(403, "HTTP 403")):
            self.assertIsNone(RC.transient(exc))

    def test_asked_again_after_each_wait_then_it_raises(self):
        waited, told = [], []

        async def no_wait(s):
            waited.append(s)

        def run(script):
            calls = []

            async def call():
                calls.append(1)
                item = script.pop(0) if len(script) > 1 else script[0]
                if isinstance(item, Exception):
                    raise item
                return item

            async def go():
                return await RC.retrying(call, lambda *a: told.append(a[:2]))
            with unittest.mock.patch.object(RC, "_sleep", no_wait):
                return asyncio.run(go()), len(calls)
        self.assertEqual(run([asyncio.TimeoutError(), "answer"]), ("answer", 2))
        self.assertEqual((waited, told), ([30], [(2, 6)]))
        waited.clear()
        with self.assertRaises(asyncio.TimeoutError):
            run([asyncio.TimeoutError()])
        self.assertEqual(waited, list(RC.RETRY_WAITS_S))
        waited.clear()
        with self.assertRaises(ValueError):                            # a refusal: at once
            run([ValueError("bad"), "answer"])
        self.assertEqual(waited, [])


class GateTests(unittest.TestCase):
    """One gate paces every caller: Inara's sender and its key Check never make two requests within MIN_GAP_S."""

    def test_shared_gate(self):
        clock, made, slept = [1000.0], [], []

        async def sleep(secs):
            slept.append(secs)
            clock[0] += secs

        async def go():
            gate = U.Gate(35, clock=lambda: clock[0], sleep=sleep)
            db = ed_outrider.open_db(":memory:")
            try:
                sess = types.SimpleNamespace(cmdr="A", gameversion="4.2", gamebuild="r1")
                U.enqueue(db, "inara", "e1", "f#1", "2026-10-12T00:00:00Z", sess, {"eventName": "x"})
                db.commit()

                async def send(rows):
                    made.append(("send", clock[0]))
                    raise asyncio.CancelledError   # one round is enough
                try:
                    await U.upload_loop("inara", db, send, lambda s: True, clock=lambda: clock[0], sleep=sleep, batch=1, gate=gate)
                except asyncio.CancelledError:
                    pass
                clock[0] += 5
                await gate.wait()                 # the Check, 5 s after the sender's request: waits the other 30
                made.append(("check", clock[0]))
                await gate.wait()                 # and the sender's next one waits for the Check's
                made.append(("send", clock[0]))
            finally:
                db.close()
        asyncio.run(go())
        self.assertEqual(made, [("send", 1000.0), ("check", 1035.0), ("send", 1070.0)])
        self.assertEqual(slept, [30, 35])


class KeyChecks(unittest.TestCase):
    """S45: POST /api/uploads/{edsm,inara}/check."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.state.edsm_gate = U.Gate(0)
        self.state.inara_gate = U.Gate(0)
        self.printed = []
        p = unittest.mock.patch("builtins.print", lambda *a, **k: self.printed.append(" ".join(map(str, a))))
        p.start()
        self.addCleanup(p.stop)

    def check(self, service, script, body):
        from aiohttp.test_utils import TestClient, TestServer
        self.state.upload_session = _HwSession(script)

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                r = await c.post(f"/api/uploads/{service}/check", json=body)
                return r.status, (await r.json() if r.content_type == "application/json" else None)
        self.state.key_checked.clear()   # one per KEY_CHECK_S: each call here is a new check
        return asyncio.run(go())

    def test_edsm_no_credits_yet(self):
        """Complete review 2026-10-30: EDSM's 208 (a known commander, no credits stored yet: a new account before its
        first upload) read as a refused key."""
        self.state.set_edsm_account("Sample Pilot", "Sample EDSM", EDSM_KEY)
        status, j = self.check("edsm", [(200, {"msgnum": 208, "msg": "No credits stored"})], {"commander": "Sample Pilot"})
        self.assertEqual((status, j["ok"], j["text"]), (200, True, "EDSM accepts CMDR Sample EDSM with this key (no credits stored yet)"))

    def test_edsm(self):
        st, out = self.state, []
        st.set_edsm_account("Sample Pilot", "Sample EDSM", EDSM_KEY)
        status, j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "Sample Pilot"})
        self.assertEqual((status, j["ok"], j["text"]), (200, True, "EDSM accepts CMDR Sample EDSM with this key"))
        call = st.upload_session.calls[0]
        self.assertEqual(call[:2], ("POST", RC.EDSM_CREDITS_URL))         # the key in the body, never in the URL
        self.assertEqual((call[2]["commanderName"], call[2]["apiKey"]), ("Sample EDSM", EDSM_KEY))
        out.append(j)
        status, j = self.check("edsm", [(200, EX["edsm_credits_wrong"])], {"commander": "Sample Pilot", "name": "Typo"})
        self.assertEqual((j["ok"], j["text"]), (False, "EDSM: 203 commander name or API key not found"))
        out.append(j)
        status, j = self.check("edsm", [ConnectionRefusedError(f"Cannot connect to {RC.EDSM_CREDITS_URL}?apiKey={EDSM_KEY}")],
                               {"commander": "Sample Pilot"})
        self.assertEqual((j["ok"], j["text"]), (False, "Couldn't reach EDSM: the connection was refused"))
        out.append(j)
        status, j = self.check("edsm", [asyncio.TimeoutError()], {"commander": "Sample Pilot"})
        self.assertEqual(j["text"], "Couldn't reach EDSM: timeout")
        status, j = self.check("edsm", [(503, None)], {"commander": "Sample Pilot"})
        self.assertEqual(j["text"], "Couldn't reach EDSM: it is failing (HTTP 5xx)")
        status, j = self.check("edsm", [(200, "<html>")], {"commander": "Sample Pilot"})
        self.assertEqual(j["text"], "EDSM's answer was not understood")
        # never the key: not in any answer, not in the log
        self.assertFalse([x for x in out if EDSM_KEY in json.dumps(x)])
        self.assertFalse([p for p in self.printed if EDSM_KEY in p])

    def test_typed_key_and_refusals(self):
        st = self.state
        self.assertEqual(self.check("edsm", [(200, {})], {"commander": "Nobody"})[0], 400)   # no key stored, none typed
        self.assertEqual(self.check("edsm", [(200, {})], {"commander": "A", "api_key": "not hex"})[0], 400)
        self.assertEqual(self.check("edsm", [(200, {})], {"commander": ""})[0], 400)
        self.assertEqual(self.check("spansh", [(200, {})], {"commander": "A"})[0], 404)
        status, j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "New One", "api_key": EDSM_KEY})
        self.assertEqual((status, j["ok"]), (200, True))                 # a typed key, not saved: checked all the same
        self.assertEqual(st.edsm_accounts(), {})
        self.assertFalse([p for p in self.printed if EDSM_KEY in p])

    def test_one_check_per_ten_seconds(self):
        from aiohttp.test_utils import TestClient, TestServer
        self.state.set_inara_account("Sample Pilot", INARA_KEY)
        self.state.upload_session = _HwSession([(200, EX["inara_profile_ok"])])

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                a = await c.post("/api/uploads/inara/check", json={"commander": "Sample Pilot"})
                b = await c.post("/api/uploads/inara/check", json={"commander": "Sample Pilot"})
                cross = await c.post("/api/uploads/inara/check", json={"commander": "Sample Pilot"},
                                     headers={"Origin": "http://evil.example"})
                return a.status, b.status, (await b.json()).get("retry_in"), cross.status
        a, b, wait, cross = asyncio.run(go())
        self.assertEqual((a, b, cross), (200, 429, 403))
        self.assertTrue(0 < wait <= ed_outrider.KEY_CHECK_S)
        self.assertEqual(len(self.state.upload_session.calls), 1)

    def test_inara(self):
        st = self.state
        st.set_inara_account("Sample Pilot", INARA_KEY)
        status, j = self.check("inara", [(200, EX["inara_profile_ok"])], {"commander": "Sample Pilot"})
        self.assertEqual((j["ok"], j["text"], j["link"]), (True, "Inara: CMDR Sample Pilot", "https://inara.cz/elite/cmdr/1/"))
        call = st.upload_session.calls[0]
        self.assertEqual((call[0], call[1], call[2]["events"][0]["eventName"]), ("POST", outrider.inara.URL, "getCommanderProfile"))
        texts = [self.check("inara", [(200, EX[k])], {"commander": "Sample Pilot"})[1]["text"]
                 for k in ("inara_profile_none", "inara_key_wrong", "inara_rate")]
        self.assertEqual(texts, ["Inara: no commander Sample Pilot for this key", "Inara refused the key: Invalid API key.",
                                 "Inara asked Outrider to slow down: try again later"])
        self.assertFalse([p for p in self.printed if INARA_KEY in p])

    def test_a_success_clears_the_hold_through_the_one_helper(self):
        st = self.state
        st.set_edsm_account("Sample Pilot", "Sample Pilot", EDSM_KEY)
        st.upload_wake["edsm"] = asyncio.Event()

        def hold():
            st.upload_report("edsm", {"error": None, "at": 1.0, "raised": None, "wait": 30,
                                      "results": [(1, "held", "203 EDSM refused the commander name or API key", None)]})
        hold()
        with unittest.mock.patch.object(st, "clear_key_hold", wraps=st.clear_key_hold) as helper:
            j = self.check("edsm", [(200, EX["edsm_credits_wrong"])], {"commander": "Sample Pilot"})[1]
            self.assertTrue(st.upload_status["edsm"]["held"])             # refused: still on hold
            other = "fedcba9876543210fedcba9876543210fedcba98"
            j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "Sample Pilot", "api_key": other})[1]
            self.assertTrue(j["ok"])
            self.assertTrue(st.upload_status["edsm"]["held"])             # another key works: Save it first
            # the stored key with a typed name EDSM accepts: the sender sends the stored name, so the hold stays
            j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "Sample Pilot", "name": "Right Name"})[1]
            self.assertEqual((j["ok"], j.get("cleared"), j["text"]),
                             (True, None, "EDSM accepts CMDR Right Name with this key: save this name first"))
            self.assertTrue(st.upload_status["edsm"]["held"])
            j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "Sample Pilot", "name": "Sample Pilot"})[1]
            self.assertEqual(j.get("cleared"), True)                      # the stored name typed: the same pair
            hold()
            j = self.check("edsm", [(200, EX["edsm_credits_ok"])], {"commander": "Sample Pilot"})[1]
        self.assertEqual((j["ok"], j.get("cleared")), (True, True))
        self.assertEqual([c.args[0] for c in helper.call_args_list], ["edsm", "edsm"])
        self.assertNotIn("edsm", st.upload_status)
        self.assertTrue(st.upload_wake["edsm"].is_set())                  # the sender goes now


class OfflineInVerify(unittest.TestCase):
    """scripts/verify.sh's scratch server stays offline: every outside URL constant is pointed at a closed port."""

    def test_every_url_is_patched(self):
        with open(os.path.join(HERE, "..", "scripts", "verify.sh"), encoding="utf-8") as f:
            text = f.read()
        block = text[text.index('OFF = "http://127.0.0.1:9/offline"'):text.index("ed_outrider.main(")]
        for name in ("outrider.inara.URL", "outrider.readclient.URLS", "outrider.edsm.UPLOAD_URL", "outrider.eddn.UPLOAD_URL",
                     "ed_outrider.RELEASES_LATEST", "ed_outrider.DSSA_URL", "outrider.codex_images.REF"):
            self.assertIn(name, block, name)
        for name in RC.URLS:
            self.assertTrue(getattr(RC, name).startswith("https://"))
        lookups = [c for _, consts in ed_outrider.LOOKUP_URLS for c in consts]
        for c in lookups:
            self.assertTrue(re.search(rf'"{c}"|ed_outrider\.{c}\b', block), c)



class WrappedStatus(unittest.TestCase):
    def test_a_status_under_unreachable(self):
        """Complete review 2026-10-30: Unreachable is raised from the failure so its kind is read through __cause__, but
        an HTTP status there was not: a 503 was "failed" (no "tried 6 times"), a 429 too, an HttpError "refused"."""
        import aiohttp
        from outrider.health import HttpError

        def wrapped(cause):
            try:
                raise RC.Unreachable("Spansh") from cause
            except RC.Unreachable as e:
                return e
        e503 = wrapped(HttpError(503, "HTTP 503"))
        e429 = wrapped(aiohttp.ClientResponseError(None, (), status=429, message="Too Many Requests"))
        self.assertEqual((RC.transient(e503), RC.reach_words(e503)), ("http5xx", "it is failing (HTTP 5xx)"))
        self.assertEqual((RC.transient(e429), RC.reach_words(e429)), ("rate", "it asked Outrider to slow down"))


if __name__ == "__main__":
    unittest.main()
