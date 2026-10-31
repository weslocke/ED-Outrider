"""S53: Bookmarks import (merge). POST /api/bookmarks/import {text} reads Outrider's own export (CSV or JSON) on the
server, where an id64 above 2^53 stays exact, and adds what is new: a system already bookmarked keeps its note."""
import asyncio
import io
import json
import re
import unittest
import unittest.mock

from support import ed_outrider

BIG = 2 ** 60 + 1   # above 2^53: a JavaScript number would round it


class Base(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)

    def client(self, go):
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(ed_outrider.make_app(self.state))) as c:
                return await go(c)
        return asyncio.run(run())

    def marks(self):
        return [tuple(r) for r in self.db.execute("SELECT * FROM bookmarks ORDER BY id64")]

    def add(self, id64, name, note, created="2026-01-02T03:04:05Z"):
        self.db.execute("INSERT INTO bookmarks VALUES (?, ?, ?, ?, ?, ?, ?)", (id64, name, 1.5, -2.25, 30000.125, note, created))
        self.db.commit()


class RoundTrip(Base):
    def test_export_then_import_csv_and_json(self):
        self.add(BIG, "Far Out AB-C d1-2", 'a note, with "quotes"\nand a second line')
        self.add(10477373803, "Sol", "")
        self.add(7, "Seven", "é ✓", "2025-12-31T23:59:59Z")
        original = self.marks()

        async def go(c):
            out = {}
            for fmt in ("csv", "json"):
                text = await (await c.get(f"/api/export?what=bookmarks&format={fmt}")).text()
                self.db.execute("DELETE FROM bookmarks")
                self.db.commit()
                r = await c.post("/api/bookmarks/import", json={"text": "\ufeff" + text if fmt == "csv" else text})
                first = (r.status, await r.json(), self.marks())
                r = await c.post("/api/bookmarks/import", json={"text": text})   # again: nothing new
                out[fmt] = first, (r.status, await r.json())
            return out
        for fmt, (first, again) in self.client(go).items():
            self.assertEqual(first[:2], (200, {"added": 3, "already": 0, "bad": 0, "problems": []}), fmt)
            self.assertEqual(first[2], original, fmt)   # every field, the id64 above 2^53 exact
            self.assertEqual(again, (200, {"added": 0, "already": 3, "bad": 0, "problems": []}), fmt)

    def test_merge_keeps_your_own(self):
        self.add(5, "Mine", "my note")
        text = "id64,name,x,y,z,note,created_ts\n5,Theirs,9,9,9,their note,2020-01-01T00:00:00Z\n6,New One,1,2,3,,\n"

        async def go(c):
            r = await c.post("/api/bookmarks/import", json={"text": text})
            return r.status, await r.json()
        self.assertEqual(self.client(go), (200, {"added": 1, "already": 1, "bad": 0, "problems": []}))
        rows = {r[0]: r for r in self.marks()}
        self.assertEqual(rows[5], (5, "Mine", 1.5, -2.25, 30000.125, "my note", "2026-01-02T03:04:05Z"))
        self.assertEqual(rows[6][:6], (6, "New One", 1.0, 2.0, 3.0, ""))
        self.assertRegex(rows[6][6], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")   # no date in the file: today's
        self.assertIn("6", {b["id"] for b in self.state.bookmarks()})   # the page's list has it

    def test_a_merge_bumps_the_page_only_when_something_was_added(self):
        rows, _, _ = ed_outrider.parse_bookmarks("id64,name,x,y,z\n5,Five,0,0,0\n")
        v = self.state.version
        self.assertEqual(self.state.import_bookmarks(rows), (1, 0))
        v2 = self.state.version
        self.assertGreater(v2, v)
        self.assertEqual(self.state.import_bookmarks(rows), (0, 1))
        self.assertEqual(self.state.version, v2)


class Parse(unittest.TestCase):
    def test_big_id64_stays_exact(self):
        for text in (f'[{{"id64": {BIG}, "name": "A", "x": 1, "y": 2, "z": 3}}]', f"id64,name,x,y,z\n{BIG},A,1,2,3\n",
                     f'[{{"id64": "{BIG}", "name": "A", "x": "1", "y": "2", "z": "3"}}]'):
            rows, bad, problems = ed_outrider.parse_bookmarks(text)
            self.assertEqual((rows[0][:5], bad, problems), ((BIG, "A", 1.0, 2.0, 3.0), 0, []), text)

    def test_huge_coordinates_are_refused_per_row(self):
        """Complete review 2026-10-30: a 400-digit coordinate raised OverflowError (the import's 500); 1e200 was taken,
        and from then on every payload raised. Each is a bad row now, with its reason; the pins import too."""
        huge = "1" * 400
        rows, bad, problems = ed_outrider.parse_bookmarks(f'[{{"id64": 5, "name": "A", "x": {huge}, "y": 0, "z": 0}}, '
                                                          '{"id64": 6, "name": "B", "x": 1, "y": 2, "z": 3}]')
        self.assertEqual(([r[0] for r in rows], bad, problems), ([6], 1, ["item 1: x is not a number"]))
        rows, bad, problems = ed_outrider.parse_bookmarks("id64,name,x,y,z\n123,Far,1e200,0,0\n")
        self.assertEqual((rows, bad, problems), ([], 1, ["line 2: x is outside the galaxy"]))
        rows, bad, _ = ed_outrider.parse_pins(f'[{{"system_id64": 1, "body": "Sys A 1", "name": "P", "lat": {huge}, "lon": 0}}]')
        self.assertEqual((rows, bad), ([], 1))

    def test_bad_rows_are_counted_with_reasons(self):
        text = ("id64,name,x,y,z,note,created_ts\n"
                "1.15292E+18,Rounded,1,2,3,,\n"     # line 2: what a spreadsheet does to a long number
                "12,No X,,2,3,,\n"
                "13,Bad Y,1,north,3,,\n"
                "14,,1,2,3,,\n"
                "-15,Negative,1,2,3,,\n"
                "\n"                                   # a blank line is no row
                f"16,Long Note,1,2,3,{'n' * 2500},yesterday\n"
                "99999999999999999999,Huge,1,2,3,,\n"
                "17,Short\n")
        rows, bad, problems = ed_outrider.parse_bookmarks(text)
        self.assertEqual(bad, 7)
        self.assertEqual(problems, ["line 2: id64 not a whole number (a spreadsheet may have rounded it)", "line 3: no x",
                                    "line 4: y is not a number", "line 5: no name",
                                    "line 6: id64 out of range",
                                    "line 9: id64 out of range", "line 10: no x"])
        self.assertEqual([r[:2] for r in rows], [(16, "Long Note")])
        self.assertEqual(len(rows[0][5]), ed_outrider.BOOKMARK_NOTE_MAX)   # a note kept to the page's own limit
        self.assertNotEqual(rows[0][6], "yesterday")                       # a date it cannot read: now

    def test_json_bad_items(self):
        rows, bad, problems = ed_outrider.parse_bookmarks(
            '[{"id64": 1.5e15, "name": "F", "x": 0, "y": 0, "z": 0}, "Sol", {"id64": true, "name": "T", "x": 0, "y": 0, "z": 0},'
            ' {"id64": 3, "name": "N", "x": NaN, "y": 0, "z": 0}, {"id64": 4, "name": "OK", "x": 0, "y": 0, "z": false}]')
        self.assertEqual((rows, bad), ([], 5))
        self.assertEqual([p.split(":")[0] for p in problems], ["item 1", "item 2", "item 3", "item 4", "item 5"])
        self.assertIn("rounded", problems[0])
        self.assertEqual(problems[3:], ["item 4: x is not a number", "item 5: z is not a number"])

    def test_problems_shown_are_capped(self):
        text = "id64,name,x,y,z\n" + "x,A,1,2,3\n" * 50
        rows, bad, problems = ed_outrider.parse_bookmarks(text)
        self.assertEqual((len(rows), bad, len(problems)), (0, 50, ed_outrider.BOOKMARK_PROBLEMS_SHOWN))

    def test_a_spreadsheets_semicolons_and_decimal_commas(self):
        rows, bad, _ = ed_outrider.parse_bookmarks("\ufeffID64;Name;X;Y;Z;Note\r\n12;Comma;1,5;-2,25;3;a, b\r\n")
        self.assertEqual((rows[0][:6], bad), ((12, "Comma", 1.5, -2.25, 3.0, "a, b"), 0))

    def test_files_it_cannot_read(self):
        for text, words in (("", "empty"), ("  \ufeff ", "empty"), ("[1, 2", "not a JSON file"),
                            ('{"id64": 1}', "expected a list of bookmarks"), ("name,x,y,z\nA,1,2,3", "no id64 column"),
                            ("id64,name,x,y,z\n" + "1,A,1,2,3\n" * (ed_outrider.BOOKMARK_IMPORT_ROWS + 1), "more than 10,000"),
                            (json.dumps([{"id64": 1}] * (ed_outrider.BOOKMARK_IMPORT_ROWS + 1)), "more than 10,000")):
            with self.assertRaises(ValueError, msg=text[:30]) as e:
                ed_outrider.parse_bookmarks(text)
            self.assertIn(words, str(e.exception))
        # exactly the limit is fine
        rows, _, _ = ed_outrider.parse_bookmarks("id64,name,x,y,z\n" + "".join(
            f"{i},A,1,2,3\n" for i in range(ed_outrider.BOOKMARK_IMPORT_ROWS)))
        self.assertEqual(len(rows), ed_outrider.BOOKMARK_IMPORT_ROWS)


class Requests(Base):
    def test_refusals(self):
        async def go(c):
            out = []
            for raw in ("not json", '{"text": 5}', "[]", '{"text": "[1"}'):
                r = await c.post("/api/bookmarks/import", data=raw, headers={"Content-Type": "application/json"})
                out.append((r.status, (await r.json())["error"]))
            # another web site's form post: refused before it is read (request_guard)
            r = await c.post("/api/bookmarks/import", json={"text": "id64,name,x,y,z\n5,A,1,2,3\n"},
                             headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
            out.append((r.status, (await r.json())["error"]))
            # over the size limit: 413, without reading the rest
            with unittest.mock.patch.object(ed_outrider, "BOOKMARK_IMPORT_BYTES", 1000):
                r = await c.post("/api/bookmarks/import", json={"text": "id64,name,x,y,z\n" + "5,A,1,2,3\n" * 200})
                out.append((r.status, (await r.json())["error"]))
            return out
        got = self.client(go)
        self.assertEqual([s for s, _ in got], [400, 400, 400, 400, 403, 413])
        self.assertTrue(got[1][1].startswith("expected {text"))
        self.assertTrue(got[3][1].startswith("not a JSON file"))
        self.assertIn("another web site", got[4][1])
        self.assertEqual(self.marks(), [])

    def test_over_aiohttps_own_limit(self):
        """10,000 rows can pass aiohttp's 1 MiB body limit: the import reads with its own."""
        text = "id64,name,x,y,z,note\n" + "".join(f"{i},System Name {i},1000.5,-20.25,30000.125,{'n' * 120}\n"
                                                    for i in range(1, ed_outrider.BOOKMARK_IMPORT_ROWS + 1))
        self.assertGreater(len(text), 2 ** 20)

        async def go(c):
            body = io.BytesIO(json.dumps({"text": text}).encode())   # raw bytes this large make aiohttp warn
            r = await c.post("/api/bookmarks/import", data=body, headers={"Content-Type": "application/json"})
            return r.status, await r.json()
        self.assertEqual(self.client(go), (200, {"added": 10000, "already": 0, "bad": 0, "problems": []}))

    def test_the_page_limit_matches_the_servers(self):
        import os
        with open(os.path.join(os.path.dirname(ed_outrider.__file__), "static", "page.js"), encoding="utf-8") as f:
            js = f.read()
        m = re.search(r"const BM_IMPORT_MAX = (\d+) \* (\d+) \* (\d+);", js)
        self.assertEqual(int(m[1]) * int(m[2]) * int(m[3]), ed_outrider.BOOKMARK_IMPORT_BYTES)


if __name__ == "__main__":
    unittest.main()
