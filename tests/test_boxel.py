"""Unit tests: boxels (outrider/boxel.py, the author's boxel exploration, 2026-10-11). Names, positions and system
addresses are real ones from the author's journals (in-game data).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import time
import unittest

from support import ed_outrider  # noqa: F401  (puts the repository root on sys.path)
import outrider.boxel as B  # noqa: E402

# (id64, name, x, y, z) as the journals have them
REAL = [(76873176434, "Drojau TF-H c13-0", -4179.0625, -64.25, 3339.21875),
        (1451262711154, "Drojau TF-H c13-5", -4184.53125, -58.1875, 3339.8125),
        (112650603179, "Drojau AB-U d4-3", -4354.125, -35.46875, 3217.125),
        (614582987473, "Smojooe XF-G b24-0", -4185.1875, -6.21875, 3304.59375),
        (614851226337, "Drojau OG-O b26-0", -4184.53125, -66.9375, 3347.78125),
        (2000682980690, "Drojau YG-O c9-7", -4348.4375, -36.625, 3205.59375),
        (1868772118155, "Nuekaae NX-A d1-54", 13663.09375, -144.71875, 13135.4375)]


class Names(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(B.parse("Smojooe XF-G b24-0"), {"sector": "Smojooe", "letters": "XF-G", "mc": "b", "n1": 24, "n2": 0,
                                                         "prefix": "Smojooe XF-G b24-", "label": "Smojooe XF-G b24"})
        p = B.parse("Drojau AB-U d4-3")
        self.assertEqual((p["prefix"], B.name_of(p["prefix"], 4)), ("Drojau AB-U d4-", "Drojau AB-U d4-4"))
        p = B.parse("Pyriveae AA-A h12")   # no overflow number: the number follows the code
        self.assertEqual((p["mc"], p["n1"], p["n2"], p["prefix"]), ("h", 0, 12, "Pyriveae AA-A h"))
        self.assertEqual(B.parse("Col 285 Sector WG-B c14-0")["sector"], "Col 285 Sector")   # a hand-authored sector parses
        for name in ("Sol", "Shinrarta Dezhra", "HIP 22460", "Smojooe XF-G 24", "Smojooe XF b24-0", ""):
            self.assertIsNone(B.parse(name), name)
        self.assertEqual([B.number_of("Drojau AB-U d4-", n) for n in ("Drojau AB-U d4-12", "Drojau AB-U d4-x", "Drojau AB-U d41-2",
                                                                     "Drojau AB-U d4-012", "Drojau AB-U d4-0")], [12, None, None, None, 0])
        self.assertEqual([B.size(c) for c in "abcdefgh"], [10, 20, 40, 80, 160, 320, 640, 1280])


class Geometry(unittest.TestCase):
    def test_real_systems(self):
        """The letters and the system address from a position: as the game has them (2,763 of 2,763 in the author's
        journals; these few kept here)."""
        for id64, name, x, y, z in REAL:
            b = B.of_system(name, {"x": x, "y": y, "z": z})
            self.assertTrue(b["standard"], name)
            self.assertEqual(B.id64(b["sector_index"], b["boxel"], b["mc"], b["n2"]), id64, name)
            self.assertEqual(B.boxel_index(b["letters"], b["n1"]), tuple(b["boxel"]), name)
            half = B.size(b["mc"]) / 2
            self.assertTrue(all(abs(v - b["center"][k]) <= half for k, v in zip("xyz", (x, y, z))), name)   # inside its cube
        # system 6 of the TF-H boxel: an address for a system nobody has visited
        b = B.of_system("Drojau TF-H c13-0", {"x": -4179.0625, "y": -64.25, "z": 3339.21875})
        self.assertEqual(B.id64(b["sector_index"], b["boxel"], "c", 5), 1451262711154)
        self.assertEqual(B.boxel_of("Drojau", b["sector_index"], b["boxel"], "c")["prefix"], "Drojau TF-H c13-")

    def test_hand_authored_sector(self):
        """Their own origins: the name parses, the geometry is not claimed."""
        b = B.of_system("Col 285 Sector WG-B c14-0", {"x": -141.125, "y": 56.28125, "z": 215.0625})
        self.assertFalse(b["standard"])
        self.assertNotIn("center", b)

    def test_nearby(self):
        """The boxels nearest you per mass code, only in sectors whose name is known."""
        here = {"x": -4185.1875, "y": -6.21875, "z": 3304.59375}   # Smojooe XF-G b24-0
        smojooe = tuple(B.of_system("Smojooe XF-G b24-0", here)["sector_index"])
        got = B.nearby(here, {smojooe: "Smojooe"}, codes="bd", per_code=2)
        self.assertEqual([b["mc"] for b in got], ["b", "b", "d", "d"])
        self.assertEqual(got[0]["prefix"], "Smojooe XF-G b24-")   # the one you are in comes first
        self.assertTrue(all(b["sector"] == "Smojooe" for b in got))
        self.assertLessEqual(got[0]["distance"], got[1]["distance"])
        self.assertEqual(B.nearby(here, {}), [])                  # no sector named: nothing guessed
        self.assertEqual(set(B.KINDS), set(B.CODES))


class Server(unittest.TestCase):
    """The State's side: the list of the boxel you are in (filled in as you visit), Spansh's systems, a pick, targeting
    by computed id64, a boxel's probable end, the recommendations, the API."""

    def setUp(self):
        import time
        import types
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.now = time.time()

    def jump(self, s, row):
        id64, name, x, y, z = row
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(self.now - 600 + s), "StarSystem": name,
                       "SystemAddress": id64, "StarPos": [x, y, z]})

    def test_the_list_targets_and_end(self):
        self.jump(0, REAL[0])   # Drojau TF-H c13-0
        self.jump(5, REAL[1])   # ... c13-5
        v = self.state.boxel_view()
        self.assertEqual((v["boxel"]["label"], v["boxel"]["mc"], v["boxel"]["size"], v["boxel"]["standard"]), ("Drojau TF-H c13", "c", 40, True))
        self.assertEqual([r["n"] for r in v["rows"]], list(range(0, 5 + ed_outrider.outrider.boxel.TRY_ABOVE + 1)))
        self.assertEqual([r["n"] for r in v["rows"] if r["visited"]], [0, 5])
        self.assertEqual(v["rows"][5]["id"], "1451262711154")        # the computed address is the game's
        self.assertEqual(v["rows"][5]["summary"]["name"], "Drojau TF-H c13-5")   # your scans' row, as Nearby's
        self.assertEqual(v["next"], 1)
        tgt, why = self.state.boxel_target()
        self.assertEqual((tgt["name"], tgt["index"], tgt["boxel"]), ("Drojau TF-H c13-1", 1, "Drojau TF-H c13-"))
        self.assertEqual(self.state.route_target("boxel", 5)[1], "you are in Drojau TF-H c13-5 already")
        # a name the galaxy map cannot find, above every known one: probably the end
        t9 = self.state.boxel_target(9)[0]
        self.assertFalse(self.state.boxel_not_found(self.state.boxel_target(3)[0], {"ok": False, "why": "no system was targeted"}))   # below the known 5
        self.assertTrue(self.state.boxel_not_found(t9, {"ok": False, "why": "no system was targeted"}))
        v = self.state.boxel_view()
        self.assertEqual((v["end"], v["rows"][-1]["n"]), (9, 8))
        self.state.boxel_clear_end()
        self.assertIsNone(self.state.boxel_view()["end"])
        # ✓ complete by itself: the end known (-6 not found) and every number below it visited
        for s, n in ((10, 1), (11, 2), (12, 3), (13, 4)):
            self.jump(s, (n, f"Drojau TF-H c13-{n}", -4180.0, -60.0, 3339.0))
        self.assertTrue(self.state.boxel_not_found(self.state.boxel_target(6)[0], {"ok": False, "code": "wrong"}))
        v = self.state.boxel_view()
        self.assertEqual((v["complete"], v["done"], v["next"]), (True, False, None))
        self.assertEqual(self.state.boxel_target()[1], "Drojau TF-H c13 is complete")
        self.assertEqual(self.state.boxel_finished("Drojau TF-H c13-"), "complete")
        self.state.boxel_clear_end()
        # an empty boxel (-0 not found, nothing known): complete, out of the recommendations (review 2026-10-12)
        self.state.boxel_set("Drojau QQ-Z c13-", self.state.boxel_active()["sector_index"])
        self.assertTrue(self.state.boxel_not_found(self.state.boxel_target(0)[0], {"ok": False, "why": "no system was targeted"}))
        v = self.state.boxel_view()
        self.assertEqual((v["complete"], v["end"], v["rows"], v["next"]), (True, 0, [], None))
        self.assertEqual(self.state.boxel_finished("Drojau QQ-Z c13-"), "complete")
        self.state.boxel_set(None)
        # done, your call: Next stops, a kept boxel is let go, undone again
        self.state.boxel_set("Drojau TF-H c13-", self.state.boxel_active()["sector_index"])
        self.assertTrue(self.state.boxel_mark_done(True))
        self.assertIsNone(ed_outrider.meta_get(self.db, "boxel_active"))        # let go
        v = self.state.boxel_view()
        self.assertEqual((v["done"], v["next"]), (True, None))
        self.assertEqual(self.state.boxel_finished("Drojau TF-H c13-"), "done")
        self.state.boxel_mark_done(False)
        self.assertFalse(self.state.boxel_view()["done"])
        # Spansh knows -12: the list runs past it (and an end below a known number is no end)
        ed_outrider.meta_set(self.db, "boxel_spansh", {"Drojau TF-H c13-": {"ts": ed_outrider.iso_ts(self.now), "systems": {"12": {"id64": 1, "x": -4180.0, "y": -60.0, "z": 3340.0}}}})
        v = self.state.boxel_view()
        self.assertEqual((v["top"], v["spansh"], v["rows"][12]["spansh"], v["rows"][-1]["n"]), (12, 1, True, 12 + ed_outrider.outrider.boxel.TRY_ABOVE))
        self.assertIsNotNone(v["rows"][12]["distance"])
        # skip the fully scanned (opt-in): Next passes over Spansh's -6 (every body reported), not -7 (honked only) or
        # -8 (3 of 14): their first discoveries are open (review suggestion, 2026-10-12)
        ed_outrider.meta_set(self.db, "boxel_spansh", {"Drojau TF-H c13-": {"ts": ed_outrider.iso_ts(self.now), "systems": {
            "6": {"body_count": 9, "bodies_known": 9}, "7": {"body_count": 14, "bodies_known": 0}, "8": {"body_count": 14, "bodies_known": 3},
            "12": {}}}})
        self.assertEqual(self.state.boxel_view()["next"], 6)
        ed_outrider.meta_set(self.db, "boxel_skip_known", True)
        v = self.state.boxel_view()
        self.assertEqual((v["next"], v["skip_known"], self.state.boxel_target()[0]["index"]), (7, True, 7))
        self.assertEqual([(r["n"], r["scanned"], r["known"]) for r in v["rows"] if r["n"] in (6, 7, 8)],
                         [(6, True, {"bodies": 9, "count": 9}), (7, False, {"bodies": 0, "count": 14}), (8, False, {"bodies": 3, "count": 14})])
        ed_outrider.meta_set(self.db, "boxel_skip_known", False)
        self.assertFalse(self.state.boxel_spansh_due("Drojau TF-H c13-", self.now))

        # a stale end (a hiccup at -13, then -13 found) blocks no later end and makes nothing "complete" (review 2026-10-12)
        self.assertTrue(self.state.boxel_not_found(self.state.boxel_target(13)[0], {"ok": False, "why": "no system was targeted"}))
        self.jump(40, (13, "Drojau TF-H c13-13", -4180.0, -60.0, 3339.0))
        self.assertIsNone(self.state.boxel_view()["end"])
        self.assertIsNone(self.state.boxel_finished("Drojau TF-H c13-"))
        self.assertTrue(self.state.boxel_not_found(self.state.boxel_target(15)[0], {"ok": False, "why": "no system was targeted"}))
        self.assertEqual(self.state.boxel_view()["end"], 15)

    def test_a_failure_is_kept_when_the_cache_is_full(self):
        """Bug check #24: with BOXEL_SPANSH_KEEP boxels cached, a failed ask of a new one was the entry evicted (no ts:
        it sorted first), so it was due again at once. The oldest other entry goes instead."""
        import asyncio
        from aiohttp import ClientError

        class Down:
            def post(self, *a, **k):
                raise ClientError("down")
        self.state.spansh.session, self.state.spansh.sem_fast = Down(), asyncio.Semaphore(1)
        full = {f"Old Sector AB-C d{i}-": {"ts": f"2026-10-01T00:{i:02d}:00Z", "systems": {}, "error": None, "error_ts": None}
                for i in range(ed_outrider.BOXEL_SPANSH_KEEP)}
        ed_outrider.meta_set(self.db, "boxel_spansh", full)
        prefix = "Drojau TF-H c13-"
        asyncio.run(self.state.boxel_spansh_fetch(prefix))
        cache = ed_outrider.meta_get(self.db, "boxel_spansh")
        self.assertIn(prefix, cache)
        self.assertNotIn("Old Sector AB-C d0-", cache)   # the oldest went
        self.assertEqual(len(cache), ed_outrider.BOXEL_SPANSH_KEEP)
        self.assertFalse(self.state.boxel_spansh_due(prefix))

    def test_a_failed_spansh_ask_waits_before_the_next(self):
        """Review 2026-10-23 S3-B1: with Spansh unreachable a failed ask kept the boxel due (the failure keeps the old,
        missing ts) and moved the payload's boxel key there and back, so the page looked again and the look asked again,
        round after round. A failure now waits BOXEL_SPANSH_RETRY_S, and only an answer moves the key."""
        import asyncio
        from aiohttp import ClientError
        posts = []

        class Down:
            def post(self, *a, **k):
                posts.append(a)
                raise ClientError("down")
        self.state.spansh.session, self.state.spansh.sem_fast = Down(), asyncio.Semaphore(1)
        self.jump(0, REAL[0])
        prefix = "Drojau TF-H c13-"
        key0 = self.state.payload()["boxel"]["key"]
        self.assertTrue(self.state.boxel_spansh_due(prefix))
        asyncio.run(self.state.boxel_spansh_fetch(prefix))
        self.assertEqual(len(posts), 1)
        c = ed_outrider.meta_get(self.db, "boxel_spansh")[prefix]
        self.assertEqual((c["ts"], c["systems"], bool(c["error"]), bool(c["error_ts"])), (None, {}, True, True))
        key1 = self.state.payload()["boxel"]["key"]
        self.assertNotEqual(key1, key0)                                   # the answer (a failure) shows once
        self.assertFalse(self.state.boxel_spansh_due(prefix))            # and is not asked again at once
        self.assertTrue(self.state.boxel_spansh_due(prefix, time.time() + ed_outrider.BOXEL_SPANSH_RETRY_S + 1))
        self.state._boxel_fetching.add(prefix)                            # asking moves no key
        self.assertEqual(self.state.payload()["boxel"]["key"], key1)
        self.state._boxel_fetching.discard(prefix)

    def test_the_recommendations_read_each_sector_once(self):
        """Review 2026-10-23 S3-S2: boxel_nearby asked the visits and the EDSM log once per candidate boxel; one pass
        per sector gives the same answer."""
        for k, row in enumerate(REAL):
            self.jump(k, row)
        near = self.state.boxel_nearby()
        prefixes = [b["prefix"] for b in near["boxels"]] + ["Drojau TF-H c13-", "Smojooe XF-G b24-"]
        many = self.state.boxel_visited_many(prefixes)
        self.assertEqual(many, {p: self.state.boxel_visited(p) for p in prefixes})
        self.assertTrue(any(many.values()))
        from unittest import mock
        with mock.patch.object(self.state, "boxel_visited", side_effect=AssertionError("asked per boxel")):
            self.assertEqual(self.state.boxel_nearby()["boxels"], near["boxels"])

    def test_next_for_now(self):
        """The payload's boxel Next (for Now and the overlay's Now panel) is the list's, worked out without the list,
        and only when the boxel key changes; the overlay shows it for a kept boxel only (review suggestion 2026-10-12)."""
        self.jump(0, REAL[0])   # Drojau TF-H c13-0
        nx = lambda: self.state.payload()["boxel"]["next"]
        self.assertEqual((nx()["name"], nx()["n"], nx()["picked"], nx()["spansh"]), ("Drojau TF-H c13-1", 1, False, False))
        self.assertIsNone(self.state.overlay_boxel())                   # followed, not kept: nothing on the overlay
        ed_outrider.meta_set(self.db, "boxel_spansh", {"Drojau TF-H c13-": {"ts": ed_outrider.iso_ts(self.now), "systems": {
            "1": {"body_count": 9, "bodies_known": 9}, "2": {"body_count": 14, "bodies_known": 3}}}})
        self.assertEqual((nx()["n"], nx()["known"], nx()["scanned"]), (1, {"bodies": 9, "count": 9}, True))
        ed_outrider.meta_set(self.db, "boxel_skip_known", True)
        self.assertEqual((nx()["n"], nx()["known"]), (2, {"bodies": 3, "count": 14}))
        self.assertEqual(nx()["n"], self.state.boxel_view()["next"])
        self.state.boxel_set("Drojau TF-H c13-", self.state.boxel_active()["sector_index"])
        self.assertEqual(self.state.overlay_boxel()["name"], "Drojau TF-H c13-2")   # kept: on the overlay too
        self.assertEqual(self.state.overlay_now_info(self.j.pos, self.now)["boxel"]["n"], 2)
        self.state.boxel_mark_done(True)                                  # done lets it go
        self.assertEqual((nx()["done"], nx()["name"], nx()["picked"]), (True, None, False))
        self.state.boxel_set(None)
        self.jump(30, (77, "Sol", 0.0, 0.0, 0.0))                         # a hand-made name: in no boxel
        self.assertIsNone(nx())

    def test_sector_grid(self):
        """The sector map: your visits by boxel in one Y layer of the sector you are in, the done and complete marks,
        Spansh's lists, you and the kept boxel; the layers with visits; the API's checks (review suggestion E)."""
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        self.assertEqual(self.state.boxel_sector()["why"], "your position is not known yet")
        self.jump(0, REAL[0])   # Drojau TF-H c13-0
        self.jump(5, REAL[1])   # ... c13-5
        at = B.boxel_index("TF-H", 13)
        g = self.state.boxel_sector("c")
        self.assertEqual((g["mc"], g["n"], g["sector"], g["layer"], g["you"]), ("c", 32, "Drojau", at[1], list(at)))
        self.assertEqual(g["cells"], [{"x": at[0], "z": at[2], "visited": 2, "spansh": 0, "state": None}])
        self.assertEqual(g["layers"], {str(at[1]): 1})
        self.assertIsNone(g["kept"])
        self.assertEqual(self.state.boxel_sector("c", (at[1] + 1) % 32)["cells"], [])                  # another layer
        self.assertEqual(self.state.boxel_sector("c", 99)["layer"], 31)                         # held in the sector
        self.assertEqual(self.state.boxel_sector()["mc"], "c")                                  # the active boxel's code
        self.assertEqual(self.state.boxel_sector("d")["cells"], [])                             # no d system visited
        # kept, Spansh's list, then done
        self.state.boxel_set("Drojau TF-H c13-", self.state.boxel_active()["sector_index"])
        ed_outrider.meta_set(self.db, "boxel_spansh", {"Drojau TF-H c13-": {"ts": ed_outrider.iso_ts(self.now), "systems": {"7": {}, "8": {}}}})
        g = self.state.boxel_sector("c")
        self.assertEqual((g["kept"], g["cells"][0]["spansh"]), (list(at), 2))
        self.state.boxel_mark_done(True)
        self.assertEqual(self.state.boxel_sector("c")["cells"][0]["state"], "done")
        self.jump(30, (77, "Sol", 0.0, 0.0, 0.0))   # a sector with no standard system of yours: nothing to name it by
        self.assertIn("no name", self.state.boxel_sector("c")["why"])

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return [(await c.get(u)).status for u in ("/api/boxel/sector?mc=a", "/api/boxel/sector?layer=-1",
                                                          "/api/boxel/sector?mc=d&layer=5", "/api/boxel/sector")]
        self.assertEqual(asyncio.run(go()), [400, 400, 200, 200])

    def test_pick_nearby_and_api(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        self.jump(0, REAL[3])   # Smojooe XF-G b24-0
        near = self.state.boxel_nearby()
        self.assertTrue(near["boxels"])
        self.assertEqual(set(near["codes"]), set("abcdefgh"))
        self.assertEqual(near["codes"]["b"]["yours"]["systems"], 1)
        mine = next(b for b in near["boxels"] if b["prefix"] == "Smojooe XF-G b24-")
        self.assertEqual((mine["visited"], mine["top"], mine["spansh_asked"]), (1, 0, False))
        ed_outrider.meta_set(self.db, "boxel_spansh", {"Smojooe XF-G b24-": {"ts": ed_outrider.iso_ts(self.now), "systems": {"41": {}}}})
        mine = next(b for b in self.state.boxel_nearby()["boxels"] if b["prefix"] == "Smojooe XF-G b24-")
        self.assertEqual((mine["top"], mine["spansh_asked"]), (41, True))   # the highest known, yours or Spansh's
        self.state.boxel_mark_done(True)   # the one you are in, done: out of the recommendations, listed apart
        near = self.state.boxel_nearby()
        self.assertNotIn("Smojooe XF-G b24-", [b["prefix"] for b in near["boxels"]])
        self.assertEqual([(f["prefix"], f["state"]) for f in near["finished"]], [("Smojooe XF-G b24-", "done")])
        self.assertEqual(len([b for b in near["boxels"] if b["mc"] == "b"]), ed_outrider.BOXEL_NEAR_SHOW)   # the next nearest fills in
        self.state.boxel_mark_done(False)
        d = next(b for b in near["boxels"] if b["mc"] == "d")
        self.assertTrue(self.state.boxel_set(d["prefix"], d["sector_index"]))
        v = self.state.boxel_view()
        self.assertEqual((v["boxel"]["prefix"], v["boxel"]["here"], v["boxel"]["standard"]), (d["prefix"], False, True))
        self.assertEqual(self.state.boxel_target(0)[0]["id64"],
                         ed_outrider.outrider.boxel.id64(d["sector_index"], d["boxel"], "d", 0))
        self.assertFalse(self.state.boxel_set("Smojooe XF-G"))   # no boxel's name

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                out = {}
                out["auto"] = (await (await c.post("/api/boxel", json={"auto": True})).json())["auto"]
                out["back"] = (await (await c.post("/api/boxel", json={"prefix": None})).json())["boxel"]["prefix"]
                out["bad"] = [(await c.post("/api/boxel", json=b)).status for b in ({}, {"auto": "yes"}, {"prefix": "x"})]
                out["near"] = (await c.get("/api/boxel/nearby")).status
                out["target_bad"] = (await c.post("/api/highway/target", json={"route": "boxel", "index": "3"})).status
                return out
        out = asyncio.run(go())
        self.assertEqual(out, {"auto": True, "back": "Smojooe XF-G b24-", "bad": [400, 400, 400], "near": 200, "target_bad": 400})
        self.assertTrue(self.state.payload()["boxel"]["auto"])

    def test_auto_on_arrival_only_in_the_boxel_and_once(self):
        """The opt-in: one attempt per live arrival in a system of the boxel being explored; nothing without it."""
        import types
        started = []
        self.state.targeter = types.SimpleNamespace(available=True)
        self.state.autotarget_busy = lambda: False
        self.jump(0, REAL[0])
        self.assertFalse(self.state.maybe_boxel_autotarget(self.now - 595))   # off
        ed_outrider.meta_set(self.db, "boxel_auto", True)
        self.jump(3, REAL[1])
        self.assertFalse(self.state.maybe_boxel_autotarget(self.now - 590))   # on, but no boxel kept: not followed
        self.state.boxel_set("Drojau TF-H c13-", self.state.boxel_active()["sector_index"])   # 📌 kept
        self.jump(5, REAL[0])

        async def go():
            async def fake(tgt, test=None, cancel=None):
                started.append(tgt["name"])
            self.state._autotarget = fake
            first = self.state.maybe_boxel_autotarget(self.now - 590)
            again = self.state.maybe_boxel_autotarget(self.now - 590)   # the same arrival: not twice
            await asyncio.sleep(0)
            return first, again
        import asyncio
        self.assertEqual(asyncio.run(go()), (True, False))
        self.assertEqual(started, ["Drojau TF-H c13-1"])   # the lowest you have not visited
        self.jump(9, REAL[2])   # another boxel's system: no run
        self.assertFalse(asyncio.run(self._call()))

    async def _call(self):
        return self.state.maybe_boxel_autotarget(self.now - 590)
