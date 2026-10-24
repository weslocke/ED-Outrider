"""Unit tests: the Exo-Biology checklist's "🔍 nearby" (S29): the nearest bodies where commanders reported a species
(and a colour) to Spansh, from its body search's landmark filter (tests/fixtures/spansh_landmarks.json: real answers,
the colour filter among them), each hit checked, with visited and ☆; GET /api/checklist/find.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import copy
import json
import os
import unittest
import unittest.mock

from support import ed_outrider, _HwSession  # also puts the repository root on sys.path
import outrider.bio
import outrider.checklist

with open(os.path.join(os.path.dirname(__file__), "fixtures", "spansh_landmarks.json"), encoding="utf-8") as f:
    FIX = json.load(f)
VES = "Bacterium Vesicula"


def species_id(name):
    merged, _ = outrider.checklist.merge_species(outrider.bio.load_rules()["species"])
    s = next(s for s in merged if s["name"] == name)
    return s.get("id") or s["name"]


class Rows(unittest.TestCase):
    def test_real_answers(self):
        # the probe's colour filter: every result of that colour (Spansh applied it)
        for colour in ("Mulberry", "Lime"):
            d = FIX[f"filter_landmarks_variant_{colour.lower()}"]
            rows = ed_outrider.species_find_rows(d["results"], VES, colour)
            self.assertEqual(len(rows), len(d["results"]))
            self.assertTrue(all(colour in r["colours"] for r in rows))
        rows = ed_outrider.species_find_rows(FIX["filter_landmarks_subtype_list"]["results"], VES)
        first = rows[0]
        self.assertEqual({k: first[k] for k in ("id", "system", "body", "body_id", "gravity", "dist_ls", "colours")},
                         {"id": "89128321720906", "system": "Eol Prou LW-L c8-324", "body": "4 b", "body_id": 32,
                          "gravity": 0.34, "dist_ls": 1196, "colours": ["Mulberry"]})
        self.assertEqual([r["ly"] for r in rows], sorted(r["ly"] for r in rows))

    def test_hits_are_checked(self):
        """Spansh ignores a filter shape it does not know: a body without the species (or the colour) is left out."""
        good = copy.deepcopy(FIX["filter_landmarks_variant_mulberry"]["results"][0])
        other = copy.deepcopy(good)
        other["landmarks"] = [dict(good["landmarks"][0], subtype="Bacterium Aurasus")]
        lime = copy.deepcopy(good)
        lime["landmarks"] = [dict(good["landmarks"][0], variant="Lime")]
        broken = dict(good, system_x=None)
        got = ed_outrider.species_find_rows([other, good, lime, broken, None, "x"], VES, "Mulberry")
        self.assertEqual([r["colours"] for r in got], [["Mulberry"]])
        self.assertEqual(len(ed_outrider.species_find_rows([other, good, lime], " bacterium  vesicula ")), 2)   # any colour
        self.assertEqual(ed_outrider.species_find_rows(None, VES), [])


class Server(unittest.TestCase):
    def setUp(self):
        if not outrider.bio.load_rules():
            self.skipTest("no bio rules")
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.spansh = ed_outrider.Spansh(self.db)
        self.state = ed_outrider.State(self.db, self.j, self.spansh, 25)
        self.sid = species_id(VES)

    def at_colonia(self):
        self.j.handle({"event": "FSDJump", "timestamp": "2026-10-01T00:00:00Z", "StarSystem": "Colonia", "SystemAddress": 3238296097059,
                       "StarPos": [-9530.5, -910.28125, 19808.125]})
        self.db.commit()

    def find(self, *a, **kw):
        return asyncio.run(self.state.checklist_find(*a, **kw))

    def test_find(self):
        answer = FIX["filter_landmarks_variant_mulberry"]
        self.spansh.session = _HwSession([(200, answer)])
        self.assertEqual(self.find(self.sid, "Mulberry")[1], 409)   # no position yet
        self.at_colonia()
        out, status = self.find(self.sid, "mulberry", now=1000)
        self.assertEqual(status, 200)
        (method, url, body), = self.spansh.session.calls
        self.assertEqual((method, url), ("POST", ed_outrider.SPANSH_BODY_SEARCH))
        self.assertEqual(body["filters"]["landmarks"], [{"subtype": VES, "variant": "Mulberry"}])
        self.assertEqual(body["reference_coords"], {"x": -9530.5, "y": -910.28125, "z": 19808.125})
        self.assertEqual(body["sort"], [{"distance": {"direction": "asc"}}])
        self.assertEqual((out["species"], out["colour"], out["where"], out["count"]), (VES, "Mulberry", "Colonia", 144))
        self.assertEqual(len(out["rows"]), 3)
        row = out["rows"][0]
        self.assertEqual((row["system"], row["visited"], row["bookmarked"]), ("Eol Prou LW-L c8-324", False, False))
        # ☆ on a row: its system is located (it is in no table Outrider keeps), so the bookmark is made
        self.assertTrue(self.state.set_bookmark(int(row["id"]), "Vesicula here"))
        # asked again within CHECKLIST_FIND_KEEP_S from the same place: from memory, the bookmark seen
        out, _ = self.find(self.sid, "Mulberry", now=1000 + ed_outrider.CHECKLIST_FIND_KEEP_S - 1)
        self.assertEqual(len(self.spansh.session.calls), 1)
        self.assertTrue(out["rows"][0]["bookmarked"])
        self.find(self.sid, "Mulberry", now=1000 + ed_outrider.CHECKLIST_FIND_KEEP_S)
        self.assertEqual(len(self.spansh.session.calls), 2)
        # any colour: no variant in the filter
        self.find(self.sid, None, now=5000)
        self.assertEqual(self.spansh.session.calls[-1][2]["filters"]["landmarks"], [{"subtype": VES}])

    def test_geology_entries_are_found_the_same_way(self):
        """S9-S6: a Geology checklist entry (its codex id) is asked for by its name as the landmark subtype, no colour;
        only bodies whose landmarks name it are kept."""
        e = next(x for x in self.state.geo_codex() if x["name"] == "Nitrogen Ice Geyser")
        answer = {"count": 49, "results": [
            {"system_id64": 5, "system_name": "Geyser Land", "system_x": 1.0, "system_y": 2.0, "system_z": 3.0,
             "name": "Geyser Land A 1", "distance": 12.5, "landmarks": [{"subtype": "Nitrogen Ice Geyser", "type": "Geyser"}]},
            {"system_id64": 6, "system_name": "Other", "system_x": 1.0, "system_y": 2.0, "system_z": 3.0,
             "name": "Other 1", "distance": 13.0, "landmarks": [{"subtype": "Water Geyser", "type": "Geyser"}]}]}
        self.spansh.session = _HwSession([(200, answer)])
        self.at_colonia()
        out, status = self.find(str(e["id"]), kind="geo")
        self.assertEqual(status, 200)
        self.assertEqual(self.spansh.session.calls[0][2]["filters"]["landmarks"], [{"subtype": "Nitrogen Ice Geyser"}])
        self.assertEqual([(r["system"], r["body"]) for r in out["rows"]], [("Geyser Land", "A 1")])
        self.assertEqual(self.find(str(e["id"]), "Blue", kind="geo")[1], 400)   # no colours
        self.assertEqual(self.find(self.sid, kind="geo")[1], 404)               # a species id is not a geology entry

    def test_refused(self):
        self.at_colonia()
        self.spansh.session = _HwSession([ed_outrider.ClientError("down")])
        self.assertEqual(self.find("$Nope;")[1], 404)
        out, status = self.find(self.sid, "Plaid")
        self.assertEqual((status, out["error"]), (400, f"{VES} has no colour Plaid"))
        self.assertEqual(self.spansh.session.calls, [])
        with unittest.mock.patch("sys.stderr"):
            out, status = self.find(self.sid)
        self.assertEqual(status, 502)
        self.assertIn("Spansh could not be asked", out["error"])
        self.assertEqual(self.state.checklist_finds, {})   # nothing kept: asked again next time

    def test_endpoint(self):
        from aiohttp.test_utils import TestClient, TestServer
        self.at_colonia()
        self.spansh.session = _HwSession([(200, FIX["filter_landmarks_variant_lime"])])

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                bad = (await c.get("/api/checklist/find")).status
                r = await c.get("/api/checklist/find", params={"species": self.sid, "colour": "Lime"})
                return bad, r.status, await r.json()
        bad, status, out = asyncio.run(go())
        self.assertEqual((bad, status, out["colour"], len(out["rows"])), (400, 200, "Lime", 3))

    def test_not_an_ai_tool(self):
        import outrider.tools
        self.assertFalse(outrider.tools.allowed("/api/checklist/find"))


if __name__ == "__main__":
    unittest.main()
