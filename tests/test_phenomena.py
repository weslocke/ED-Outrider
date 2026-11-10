"""Bio/Geo's Phenomena checklist (project/PLAN-phenomena-checklist-2026-11-09.md): the codex entries found in space at
notable stellar phenomena, split from Geology (now the surface only); its 🔍 nearby from Canonn's site list; and a
screenshot taken at a phenomenon filed under the codex entry logged there. The visit's lines are the author's of
2026-11-10 (a destination drop, Prasinum Metallic Crystals logged, a shot with no position). Fakes only: no network."""
import asyncio
import os
import tempfile
import time
import types
import unittest

from support import ed_outrider
import outrider.checklist as C
import outrider.screenshots as S

SYSTEM = 76806100338
CRYSTALS = 2100801            # Prasinum Metallic Crystals (Organic Structures, hud Cloud)
GEYSER = 1400258              # a surface Geology entry


class FakeResp:
    def __init__(self, status, text):
        self.status, self._text = status, text

    def raise_for_status(self):
        if self.status >= 400:
            raise ed_outrider.ClientError(f"HTTP {self.status}")

    async def text(self, errors="strict"):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeSession:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def get(self, url, **kw):
        self.calls.append(url)
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        return FakeResp(*a)


class Lists(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.spansh = types.SimpleNamespace(cached=lambda i: (None, None))
        self.state = ed_outrider.State(self.db, self.j, self.spansh, 25)

    def test_the_shipped_lists(self):
        geo, phen = self.state.codex_list("geo"), self.state.codex_list("phen")
        self.assertEqual({e["kind"] for e in geo}, {"Geology"})              # the surface only now
        self.assertEqual({e["kind"] for e in phen}, {"Cloud", "Anomaly"})
        self.assertGreaterEqual(len(phen), 180)
        self.assertIn(CRYSTALS, {e["id"] for e in phen})
        self.assertTrue(all(e.get("dump", "").startswith("https://") and e.get("section") for e in phen))
        self.assertTrue(all(C.geo_short(e) and len(C.geo_short(e)) <= len(e["name"]) for e in phen))
        self.assertTrue(any(C.geo_short(e) == "Candidum Pod" for e in phen))   # the group's word inside the name

    def test_an_old_file_splits_by_kind(self):
        self.state._geo_codex = [{"id": 1, "name": "Water Geyser", "kind": "Geology"},
                                 {"id": 2, "name": "K01-Type Anomaly", "kind": "Anomaly"}, {"id": 3, "name": "Roseum Lagrange Cloud", "kind": "Cloud"}]
        self.assertEqual([e["id"] for e in self.state.codex_list("geo")], [1])
        self.assertEqual([e["id"] for e in self.state.codex_list("phen")], [2, 3])

    def test_box_order(self):
        out = C.geo_table(self.state.codex_list("phen"), None, [], 42)
        genera = [g["genus"] for g in out["genera"]]
        self.assertEqual(genera[:2], ["Lagrange Cloud", "Storm Cloud"])
        self.assertLess(genera.index("Metallic Crystals"), genera.index("Mollusc"))
        self.assertTrue(all(g.endswith("-Type Anomaly") for g in genera[-6:]))

    def test_checklist_and_panel(self):
        self.db.execute("INSERT INTO codex (ts, entry_id, name, category, subcategory, region, system) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("2026-11-10T00:06:58Z", CRYSTALS, "Prasinum Metallic Crystals", "$Codex_Category_Biology;",
                         "$Codex_SubCategory_Organic_Structures;", "Inner Orion Spur", None))
        out, status = self.state.checklist("all", kind="phen")
        self.assertEqual((status, out["kind"]), (200, "phen"))
        rows = {r["id"]: r for g in out["genera"] for r in g["species"]}
        self.assertEqual(rows[str(CRYSTALS)]["state"], "logged")
        self.assertNotIn(str(GEYSER), rows)
        geo, _ = self.state.checklist("all", kind="geo")
        self.assertNotIn(str(CRYSTALS), {r["id"] for g in geo["genera"] for r in g["species"]})
        one, status = self.state.checklist_geo(str(CRYSTALS), "phen")
        self.assertEqual((status, one["section"], one["group"]), (200, "Organic Structures", "Metallic Crystals"))
        self.assertEqual(self.state.checklist_geo(str(CRYSTALS), "geo")[1], 404)   # not on the other list
        self.assertEqual(self.state.checklist("all", kind="nope")[1], 400)


class Nearby(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.spansh = types.SimpleNamespace(cached=lambda i: (None, None), session=FakeSession((200, "")))
        self.state = ed_outrider.State(self.db, self.j, self.spansh, 25)

    def find(self, *a, **kw):
        return asyncio.run(self.state.checklist_find(*a, kind="phen", **kw))

    def test_sites_parsed_one_per_system(self):
        text = ("Near,10.0,0.0,0.0,2100801,111,5,5\nNear,10.0,0.0,0.0,2100801,111,5,5\nbad line\n"
                "Far,500.5,1.0,2.0,2100801,222,5,5\n,1,2,3,2100801,333,5,5\n")
        self.assertEqual(ed_outrider.phenomena_sites(text), [(111, "Near", 10.0, 0.0, 0.0), (222, "Far", 500.5, 1.0, 2.0)])

    def test_nearest_from_canonn_kept_for_the_session(self):
        self.spansh.session = FakeSession((200, "Far,500,0,0,2100801,222,5,5\nNear,10,0,0,2100801,111,5,5\n"))
        self.assertEqual(self.find(str(CRYSTALS))[1], 409)                   # no position yet
        self.j.pos = {"id64": 1, "name": "Sol", "x": 0.0, "y": 0.0, "z": 0.0, "ts": "2026-11-10T00:00:00Z"}
        out, status = self.find(str(CRYSTALS))
        self.assertEqual(status, 200)
        self.assertEqual(self.spansh.session.calls, [next(e["dump"] for e in self.state.codex_list("phen") if e["id"] == CRYSTALS)])
        self.assertEqual([(r["system"], r["ly"]) for r in out["rows"]], [("Near", 10.0), ("Far", 500.0)])
        self.assertEqual((out["source"], out["count"], out["species"]), ("Canonn", 2, "Prasinum Metallic Crystals"))
        self.find(str(CRYSTALS))
        self.assertEqual(len(self.spansh.session.calls), 1)                  # from memory
        self.assertTrue(self.state.set_bookmark(int(out["rows"][0]["id"]), "crystals"))   # ☆ locates the system

    def test_refused(self):
        self.j.pos = {"id64": 1, "name": "Sol", "x": 0.0, "y": 0.0, "z": 0.0, "ts": "2026-11-10T00:00:00Z"}
        self.assertEqual(self.find("1")[1], 404)
        self.assertEqual(self.find(str(GEYSER))[1], 404)                     # a Geology entry is not here
        self.assertEqual(self.find(str(CRYSTALS), "Blue")[1], 400)
        self.spansh.session = FakeSession(ed_outrider.ClientError("down"))
        out, status = self.find(str(CRYSTALS))
        self.assertEqual(status, 502)
        self.assertIn("Canonn", out["error"])
        self.assertEqual(self.state.phen_sites, {})                          # nothing kept from a failure


class Shots(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.t0 = int(time.time())
        self.j.pos = {"id64": SYSTEM, "name": "Smojooe CJ-B c13-0", "x": 0.0, "y": 0.0, "z": 0.0, "ts": self.iso(-60)}

    def iso(self, off=0):
        return ed_outrider.iso_ts(self.t0 + off)

    def ev(self, off, name, **kw):
        self.j.handle(dict({"timestamp": self.iso(off), "event": name}, **kw))

    def drop(self, off=0):
        self.ev(off, "SupercruiseDestinationDrop", Type="$Fixed_Event_Life_Cloud;", Type_Localised="Notable stellar phenomena", Threat=1)

    def codex(self, off, entry):
        self.ev(off, "CodexEntry", EntryID=entry, Name="$Codex_Ent_L_Cry_MetCry_Gr_Name;", SystemAddress=SYSTEM, System="Smojooe CJ-B c13-0",
                SubCategory="$Codex_SubCategory_Organic_Structures;", Category="$Codex_Category_Biology;", Region="$Codex_RegionName_18;")

    def shot(self, off, n=0):
        self.ev(off, "Screenshot", Filename=f"\\ED_Pictures\\Screenshot_{n:04d}.bmp", Width=3072, Height=1728,
                System="Smojooe CJ-B c13-0", Body="Smojooe CJ-B c13-0 A")

    def subject(self, i=0):
        return self.state.shot_subject(self.j.shots_new[i])[1]

    def test_the_authors_visit(self):
        """2026-11-10: drop at 00:06:12, Prasinum Metallic Crystals at 00:06:58, the shot at 00:08:43."""
        self.drop()
        self.codex(46, CRYSTALS)
        self.shot(151)
        self.assertEqual(self.subject(), {"kind": "phen", "name": "Prasinum Metallic Crystals", "entry_id": CRYSTALS,
                                          "group": "Metallic Crystals", "entry": "Prasinum Metallic Crystals", "colour": None, "dist": None})
        root = tempfile.mkdtemp()
        self.assertEqual(S.codex_dir(root, self.subject()), os.path.join(root, "Phenomena", "Metallic Crystals", "Prasinum Metallic Crystals"))

    def test_the_latest_phenomena_entry_before_the_shot(self):
        silicate = next(e["id"] for e in self.state.codex_list("phen") if e["name"] == "Prasinum Silicate Crystals")
        self.drop()
        self.codex(10, CRYSTALS)
        self.codex(20, silicate)
        self.codex(25, GEYSER)                                                # not a phenomenon: passed over
        self.shot(30)
        self.assertEqual(self.subject()["entry_id"], silicate)

    def test_a_shot_before_the_scan_waits_for_the_visits_end(self):
        self.drop()
        self.shot(5)
        self.assertEqual(self.j.shots_new, [])                                # held: nothing logged yet
        self.codex(40, CRYSTALS)
        self.ev(60, "SupercruiseEntry", StarSystem="Smojooe CJ-B c13-0", SystemAddress=SYSTEM)
        self.assertEqual(len(self.j.shots_new), 1)
        self.assertEqual(self.subject()["entry_id"], CRYSTALS)
        self.assertIsNone(self.j.nsp_drop)

    def test_a_visit_with_nothing_logged_files_nothing(self):
        self.drop()
        self.shot(5)
        self.ev(60, "FSDJump", StarSystem="Elsewhere", SystemAddress=9, StarPos=[1, 2, 3])
        self.assertEqual(len(self.j.shots_new), 1)                           # converted, not filed
        self.assertIsNone(self.subject())

    def test_after_the_visit_a_shot_is_no_phenomenon(self):
        self.drop()
        self.codex(10, CRYSTALS)
        self.ev(20, "SupercruiseEntry", StarSystem="Smojooe CJ-B c13-0", SystemAddress=SYSTEM)
        self.shot(30)
        self.assertNotIn("phen", self.j.shots_new[0])

    def test_a_replayed_drop_is_no_visit(self):
        self.j.pos = dict(self.j.pos, ts="2026-11-10T00:00:00Z")
        self.j.handle({"timestamp": "2026-11-10T00:06:12Z", "event": "SupercruiseDestinationDrop", "Type": "$Fixed_Event_Life_Cloud;"})
        self.assertIsNone(self.j.nsp_drop)

    def test_the_folders_and_keywords(self):
        self.assertEqual(S.CODEX_FOLDERS["phen"], "Phenomena")
        root = tempfile.mkdtemp()
        d = os.path.join(root, "Phenomena", "Metallic Crystals", "Prasinum Metallic Crystals")
        os.makedirs(d)
        open(os.path.join(d, "a.jpg"), "wb").close()
        if S.pillow():
            S.pillow().new("RGB", (4, 4)).save(os.path.join(d, "a.jpg"))
            self.assertIn(os.path.normcase(d), S.codex_folders(root))


if __name__ == "__main__":
    unittest.main()
