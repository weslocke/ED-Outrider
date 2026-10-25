"""Screenshots (a player's request, 2026-10-25: to drop EDDiscovery's): the game's F10 / Alt+F10 shots converted as they
are taken (outrider/screenshots.py, State.shot_convert), what a surface shot shows (geo_tags, sample spots, tags), the
backlog, the endpoints. Fakes only: a tiny BMP made here, temp folders, never the player's."""
import asyncio
import datetime
import json
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.screenshots as S  # noqa: E402

Image = S.pillow()


def bmp(path, w=64, h=36, colour=(200, 120, 40)):
    Image.new("RGB", (w, h), colour).save(path, "BMP")
    return path


class Names(unittest.TestCase):
    def test_safe_and_render(self):
        self.assertEqual(S.safe_name('Sys: A/B <1>?'), "Sys_ A_B _1__")
        self.assertEqual(S.safe_name("con"), "_con")
        self.assertEqual(S.safe_name("  .. "), "Unknown")
        self.assertEqual(S.render("{system} {body} {nope}{highres}", {"system": "S", "body": "2 a", "highres": ""}), "S 2 a {nope}")
        self.assertEqual(S.short_body("Smojooe UW-E c11-22", "Smojooe UW-E c11-22 2 a"), "2 a")
        self.assertEqual(S.short_body("Sol", "Earth"), "Earth")

    def test_fields_and_folders(self):
        when = datetime.datetime(2026, 10, 25, 16, 33, 35)
        f = S.fields_for({"system": "Sys", "body": "Sys 2 a", "cmdr": "Hefay", "original": "HighResScreenShot_x.bmp",
                          "subject": {"name": "Stratum Tectonicas - Lime"}}, when)
        self.assertEqual((f["date"], f["time"], f["body"], f["highres"], f["subject"]),
                         ("2026-10-25", "16-33-35", "2 a", " (HighRes)", "Stratum Tectonicas - Lime"))
        cfg = dict(S.DEFAULTS)
        self.assertEqual(S.subfolder_parts(cfg, f), ["Hefay"])                                   # by commander (default)
        self.assertEqual(S.subfolder_parts(dict(cfg, by_system=True), f), ["Hefay", "Sys"])
        self.assertEqual(S.subfolder_parts(dict(cfg, by_cmdr=False), f), [])
        self.assertEqual(S.subfolder_parts(dict(cfg, subfolder="{cmdr}/{date}"), f), ["Hefay", "2026-10-25"])
        taken = {os.path.join("/out", "Hefay", "Sys 2 a 2026-10-25 16-33-35 (HighRes).png")}
        p = S.plan_paths(dict(cfg, medium=1920), f, "/out", exists=lambda x: x in taken)
        self.assertEqual(os.path.basename(p["full"]), "Sys 2 a 2026-10-25 16-33-35 (HighRes) (2).png")   # a clash
        self.assertEqual(p["medium"], os.path.join("/out", "Hefay", "medium", "Sys 2 a 2026-10-25 16-33-35 (HighRes) (2).jpg"))
        self.assertIsNone(p["small"])
        self.assertTrue(S.plan_paths(dict(cfg, format="jpg"), f, "/out", exists=lambda x: False)["full"].endswith(".jpg"))

    def test_pictures_folder_and_original(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        user = os.path.join(d, "pfx", "drive_c", "users", "steamuser")
        journals = os.path.join(user, "Saved Games", "Frontier Developments", "Elite Dangerous")
        pictures = os.path.join(user, "Pictures", "Frontier Developments", "Elite Dangerous")
        os.makedirs(journals)
        os.makedirs(pictures)
        with unittest.mock.patch.dict(os.environ, {"USERPROFILE": d}):
            self.assertEqual(S.pictures_from_journals([journals]), pictures)
            self.assertIsNone(S.pictures_from_journals([os.path.join(d, "elsewhere")]))
        self.assertEqual(S.original_path(pictures, "\\ED_Pictures\\Screenshot_0001.bmp"), os.path.join(pictures, "Screenshot_0001.bmp"))

    def test_wait_ready(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "s.bmp")
        clock = [0.0]
        sizes = iter([None, None, 100, 200, 200])   # missing, then growing, then settled

        def sleep(s):
            clock[0] += s
            n = next(sizes, 200)
            if n is not None:
                with open(p, "wb") as f:
                    f.write(b"x" * n)
        self.assertTrue(S.wait_ready(p, timeout=10, poll=0.5, sleep=sleep, clock=lambda: clock[0]))
        self.assertFalse(S.wait_ready(os.path.join(d, "never.bmp"), timeout=2, poll=0.5, sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                      clock=lambda: clock[0]))

    def test_subject_and_backlog(self):
        R = 1_000_000
        subs = [{"kind": "bio", "name": "Stratum Tectonicas - Lime", "lat": 0.0, "lon": 0.001},          # ~17 m
                {"kind": "geo", "name": "Water Ice Geyser", "entry_id": 1400258, "lat": 0.0, "lon": 0.002}]   # ~35 m
        self.assertEqual(S.nearest_subject(0.0, 0.0, R, subs, 50), {"kind": "bio", "name": "Stratum Tectonicas - Lime", "entry_id": None, "dist": 17})
        self.assertIsNone(S.nearest_subject(0.0, 0.0, R, subs, 10))     # none that close
        self.assertIsNone(S.nearest_subject(None, None, R, subs, 50))   # a shot from the air
        self.assertIsNone(S.nearest_subject(0.0, 0.0, R, subs, 0))      # off
        events = [(1000.0, "Screenshot_0001.bmp", {"n": "old"}), (5000.0, "Screenshot_0001.bmp", {"n": "new"})]
        got = S.match_backlog([("Screenshot_0001.bmp", 5002.0), ("Screenshot_0009.bmp", 5000.0)], events)
        self.assertEqual(got, {"Screenshot_0001.bmp": {"n": "new"}, "Screenshot_0009.bmp": None})   # a reused name: by time

    def test_journal_shots(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "Journal.2026-10-25T150000.01.log")
        with open(p, "w") as f:
            f.write('{"timestamp":"2026-10-25T20:00:00Z", "event":"LoadGame", "Commander":"Hefay"}\n')
            f.write('{"timestamp":"2026-10-25T20:33:35Z", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_0002.bmp", '
                    '"Width":3072, "Height":1728, "System":"Sys", "Body":"Sys 2 a", "Latitude":-41.6, "Longitude":-113.8, "Heading":129 }\n')
        [s] = S.journal_shots([p, os.path.join(d, "missing.log")])
        self.assertEqual((s["original"], s["cmdr"], s["body"], s["lat"]), ("Screenshot_0002.bmp", "Hefay", "Sys 2 a", -41.6))


@unittest.skipIf(Image is None, "Pillow is not installed")
class Convert(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def test_full_and_copies_with_what_it_shows(self):
        src = bmp(os.path.join(self.d, "Screenshot_0001.bmp"), 3072, 1728)
        cfg = dict(S.DEFAULTS, medium=1920, small=4000)   # small larger than the shot: never upscaled
        shot = {"ts": "2026-10-25T20:33:35Z", "system": "Sys", "body": "Sys 2 a", "lat": -41.6, "lon": -113.8, "heading": 129,
                "cmdr": "Hefay", "subject": {"kind": "bio", "name": "Stratum Tectonicas - Lime", "dist": 12}}
        paths = S.plan_paths(cfg, S.fields_for(shot), os.path.join(self.d, "out"))
        out = S.convert(src, paths, cfg, shot)
        self.assertEqual((out["width"], out["height"], len(out["written"])), (3072, 1728, 3))
        # the author, 2026-10-25: "almost no metadata, definitely not system and bio information": PNG's own keys, XMP
        # and EXIF (with Windows' XP fields) in every image
        desc = ("Sys 2 a · Stratum Tectonicas - Lime (12 m away) · latitude -41.60000, longitude -113.80000, heading 129° · "
                "CMDR Hefay · 2026-10-25 20:33:35 UTC")
        with Image.open(paths["full"]) as im:
            self.assertEqual((im.format, im.size), ("PNG", (3072, 1728)))
            self.assertEqual((im.text["Description"], im.text["Title"], im.text["Author"]),
                             (desc, "Stratum Tectonicas - Lime · Sys 2 a", "CMDR Hefay"))
            xmp = im.text["XML:com.adobe.xmp"]
            for want in ("<rdf:li>Sys 2 a</rdf:li>", "<rdf:li>Stratum Tectonicas</rdf:li>", "<rdf:li>Exobiology</rdf:li>",
                         "<xmp:CreateDate>2026-10-25T20:33:35Z</xmp:CreateDate>", "<rdf:li>CMDR Hefay</rdf:li>"):
                self.assertIn(want, xmp)
            ex = im.getexif()
            self.assertEqual((ex[0x013B], ex.get_ifd(0x8769)[0x9003]), ("CMDR Hefay", "2026:10:25 20:33:35"))
        with Image.open(paths["medium"]) as im:
            self.assertEqual((im.format, im.size), ("JPEG", (1920, 1080)))
            ex = im.getexif()
            self.assertEqual(ex[0x010E], desc.replace(" · ", " | ").replace("°", ""))   # ASCII: the ° folded away
            self.assertEqual(bytes(ex[0x9C9C]).decode("utf-16-le").rstrip("\0"), desc)
            self.assertIn("Exobiology", bytes(ex[0x9C9E]).decode("utf-16-le"))
            self.assertIn("Stratum Tectonicas - Lime", im.info["xmp"].decode())
        with Image.open(paths["small"]) as im:
            self.assertEqual(im.size, (3072, 1728))   # 4000 asked: kept at its own size
        self.assertTrue(os.path.isfile(src))         # kept by default
        jpg = S.plan_paths(dict(cfg, format="jpg", medium=0, small=0), S.fields_for(shot), os.path.join(self.d, "out2"))
        S.convert(src, jpg, dict(cfg, format="jpg"), shot)
        with Image.open(jpg["full"]) as im:
            self.assertEqual(im.format, "JPEG")

    def test_webp_copies_only_a_crop_and_the_files_date(self):
        """The author, 2026-10-25: WebP with a quality (smaller than JPG at the same), EDDiscovery's crop and its
        "extra images only", and the file's date the shot's."""
        src = bmp(os.path.join(self.d, "Screenshot_0001.bmp"), 3072, 1728)
        shot = {"ts": "2026-10-25T20:33:35Z", "system": "Sys", "body": "Sys 2 a", "cmdr": "Hefay"}
        cfg = dict(S.DEFAULTS, format="webp", quality=80, medium=1920, copies_format="webp", crop="10, 10, 80, 75", crop_px=1000)
        paths = S.plan_paths(cfg, S.fields_for(shot), os.path.join(self.d, "out"))
        self.assertEqual([os.path.basename(os.path.dirname(paths[k])) + "/" + os.path.splitext(paths[k])[1] for k in ("medium", "crop")],
                         ["medium/.webp", "crop/.webp"])
        S.convert(src, paths, cfg, shot)
        with Image.open(paths["full"]) as im:
            self.assertEqual((im.format, im.size), ("WEBP", (3072, 1728)))
            self.assertIn("Sys 2 a", im.info["xmp"].decode())
        with Image.open(paths["crop"]) as im:   # 80 % x 75 % of 3072 x 1728 = 2458 x 1296, then 1000 px on its long edge
            self.assertEqual((im.format, im.size), ("WEBP", (1000, 527)))
        when = datetime.datetime(2026, 10, 25, 20, 33, 35, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual({round(os.path.getmtime(paths[k])) for k in ("full", "medium", "crop")}, {when})
        # copies only: no full size; nothing else asked for: the full size anyway, never no picture at all
        only = S.plan_paths(dict(cfg, full=False), S.fields_for(shot), os.path.join(self.d, "o2"))
        self.assertEqual((only["full"], bool(only["medium"]), bool(only["crop"])), (None, True, True))
        out = S.convert(src, only, dict(cfg, full=False), shot)
        self.assertEqual(len(out["written"]), 2)
        bare = S.plan_paths(dict(S.DEFAULTS, full=False), S.fields_for(shot), os.path.join(self.d, "o3"))
        self.assertTrue(bare["full"].endswith(".png"))

    def test_crop_text(self):
        self.assertEqual(S.parse_crop("10, 10, 80, 75"), (10, 10, 80, 75))
        self.assertEqual(S.parse_crop("90 0 50 100"), (90, 0, 10, 100))     # cut at the picture's edge
        for bad in ("", "10, 10, 80", "a, b, c, d", "0, 0, 0.5, 50"):
            self.assertIsNone(S.parse_crop(bad))
        self.assertEqual(S.crop_box((3072, 1728), (10, 10, 80, 75)), (307, 173, 2765, 1469))

    def test_the_original(self):
        src = bmp(os.path.join(self.d, "a.bmp"))
        self.assertEqual(S.finish_original(src, dict(S.DEFAULTS), "x"), src)
        moved = S.finish_original(src, dict(S.DEFAULTS, original="move", move_to=os.path.join(self.d, "kept")), "x")
        self.assertEqual(moved, os.path.join(self.d, "kept", "a.bmp"))
        src2 = bmp(os.path.join(self.d, "a.bmp"))
        self.assertEqual(S.finish_original(src2, dict(S.DEFAULTS, original="move", move_to=os.path.join(self.d, "kept")), "x"),
                         os.path.join(self.d, "kept", "a (2).bmp"))   # taken: another name
        src3 = bmp(os.path.join(self.d, "b.bmp"))
        self.assertIsNone(S.finish_original(src3, dict(S.DEFAULTS, original="delete"), "x"))
        self.assertFalse(os.path.exists(src3))

    def test_pillow_missing(self):
        with unittest.mock.patch.object(S, "pillow", return_value=None), self.assertRaises(RuntimeError):
            S.convert("x", {"dir": self.d}, {}, {})


@unittest.skipIf(Image is None, "Pillow is not installed")
class Server(unittest.TestCase):
    """The live event queued, converted on a worker, recorded, named after what it shows; the card on a failure."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.pictures, self.out = os.path.join(self.d, "pics"), os.path.join(self.d, "out")
        os.makedirs(self.pictures)
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.st = ed_outrider.State(self.db, self.j, ed_outrider.Spansh(self.db), 25)
        self.st.shots_cfg.update(enabled=True, pictures=self.pictures, folder=self.out, medium=1920)
        now = time.time()
        at = lambda s: ed_outrider.iso_ts(now - 60 + s)
        self.at = at
        self.j.handle({"event": "LoadGame", "timestamp": at(0), "Commander": "Hefay", "FID": "F1"})
        self.j.handle({"event": "FSDJump", "timestamp": at(1), "StarSystem": "Sys", "SystemAddress": 9, "StarPos": [0, 0, 0]})
        self.j.handle({"event": "Scan", "timestamp": at(2), "ScanType": "Detailed", "StarSystem": "Sys", "SystemAddress": 9,
                       "BodyID": 6, "BodyName": "Sys 2 a", "PlanetClass": "Rocky body", "Radius": 1_000_000.0,
                       "Landable": True, "DistanceFromArrivalLS": 100.0})
        # a geology formation logged 17 m from where the shot is taken
        self.j.handle({"event": "CodexEntry", "timestamp": at(3), "EntryID": 1400258, "Name": "$Codex_Ent_IceGeysers_WaterGeysers_Name;",
                       "Name_Localised": "Water Ice Geyser", "SubCategory": "$Codex_SubCategory_Geology_and_Anomalies;",
                       "Category": "$Codex_Category_Biology;", "System": "Sys", "SystemAddress": 9, "BodyID": 6,
                       "Latitude": 0.0, "Longitude": 0.001})
        self.db.commit()

    def shoot(self, name="Screenshot_0001.bmp", lat=0.0, lon=0.0, make=True):
        if make:
            bmp(os.path.join(self.pictures, name), 320, 180)
        self.j.handle({"event": "Screenshot", "timestamp": self.at(30), "Filename": f"\\ED_Pictures\\{name}", "Width": 320,
                       "Height": 180, "System": "Sys", "Body": "Sys 2 a", "Latitude": lat, "Longitude": lon, "Heading": 10})

    def run_queue(self):
        async def go():
            self.st.shots_step()
            if self.st.shots_task:
                await self.st.shots_task
        asyncio.run(go())

    def test_geo_tags(self):
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT system, body_id, entry_id, name, lat, lon FROM geo_tags")],
                         [(9, 6, 1400258, "Water Ice Geyser", 0.0, 0.001)])
        self.assertGreaterEqual(ed_outrider.PARSER_VERSION, 61)

    def test_a_live_shot_converted_and_recorded(self):
        self.shoot()
        self.assertEqual(len(self.j.shots_new), 1)
        self.run_queue()
        [r] = self.db.execute("SELECT * FROM screenshots").fetchall()
        self.assertIsNone(r["error"])
        self.assertEqual(json.loads(r["subject"])["name"], "Water Ice Geyser")
        self.assertTrue(r["full"].startswith(os.path.join(self.out, "Hefay") + os.sep) and os.path.isfile(r["full"]))
        self.assertTrue(os.path.isfile(r["medium"]))
        self.assertIsNone(r["small"])
        self.assertEqual(r["body_id"], 6)
        self.assertTrue(self.st.shots_last["ok"])
        d = self.st.system_detail(9)
        self.assertEqual(next(b for b in d["bodies"] if b["name"] == "2 a")["shots"], 1)   # Here's 📷
        [x] = self.st.shots_list(9, "Sys 2 a")
        self.assertEqual((x["subject"]["name"], x["sizes"]), ("Water Ice Geyser", ["medium", "full"]))
        img = asyncio.run(self.st.shot_image(x["id"], "thumb"))
        self.assertTrue(isinstance(img[0], bytes) and img[1] == "image/jpeg")       # made from the medium copy
        self.assertEqual(asyncio.run(self.st.shot_image(x["id"], "medium"))[0], r["medium"])
        self.db.execute("UPDATE screenshots SET full=? WHERE id=?", (os.path.join(self.d, "elsewhere.png"), x["id"]))
        self.assertIsNone(asyncio.run(self.st.shot_image(x["id"], "full")))         # never a file outside the folder

    def test_on_foot_the_position_is_status_jsons(self):
        """The author, 2026-10-25: three shots of a bacterium on foot named nothing: on foot the Screenshot line has no
        Latitude/Longitude, so the live Status.json's over that body at that moment is the shot's."""
        self.j.status_json = {"live": True, "ts": self.at(29), "body": "Sys 2 a", "lat": 0.0, "lon": 0.0011, "heading": 77}
        self.j.handle({"event": "Screenshot", "timestamp": self.at(30), "Filename": "\\ED_Pictures\\Screenshot_0001.bmp",
                       "System": "Sys", "Body": "Sys 2 a"})
        bmp(os.path.join(self.pictures, "Screenshot_0001.bmp"), 320, 180)
        self.assertEqual([(x["lat"], x["lon"], x["heading"]) for x in self.j.shots_new], [(0.0, 0.0011, 77)])
        self.run_queue()
        [r] = self.db.execute("SELECT * FROM screenshots").fetchall()
        self.assertEqual(json.loads(r["subject"])["name"], "Water Ice Geyser")
        self.assertEqual(self.st.shots_summary()["n"], 1)   # the page's Here reloads on it
        [b] = [b for b in self.st.system_detail(9)["bodies"] if b["name"] == "2 a"]
        self.assertEqual((b["shots"], b["shot_ids"]), (1, [r["id"]]))
        # another body's Status.json, or one from minutes before: no position rather than a wrong one
        for st in ({"live": True, "ts": self.at(29), "body": "Sys 3", "lat": 1.0, "lon": 1.0},
                   {"live": True, "ts": self.at(-200), "body": "Sys 2 a", "lat": 1.0, "lon": 1.0}):
            self.j.status_json, self.j.shots_new = st, []
            self.j.handle({"event": "Screenshot", "timestamp": self.at(30), "Filename": "\\ED_Pictures\\Screenshot_0002.bmp",
                           "System": "Sys", "Body": "Sys 2 a"})
            self.assertEqual([(x["lat"], x["lon"]) for x in self.j.shots_new], [(None, None)])

    def test_a_shot_after_the_run_is_analysed(self):
        """The author, 2026-10-25: the sample spots went when the run completed, so a shot just after the Analyse
        found nothing; bio_spots keeps them, and the name is the variant's, its colour included."""
        bug = {"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Genus_Localised": "Bacterium",
               "Species": "$Codex_Ent_Bacterial_10_Name;", "Species_Localised": "Bacterium Bullaris",
               "Variant": "$Codex_Ent_Bacterial_10_Polonium_Name;", "Variant_Localised": "Bacterium Bullaris - Yellow",
               "SystemAddress": 9, "Body": 6}
        for i, (kind, lon) in enumerate((("Log", 0.010), ("Sample", 0.020), ("Sample", 0.030), ("Analyse", 0.030))):
            self.j.status_json = {"live": True, "ts": self.at(10 + i), "body": "Sys 2 a", "lat": 0.0, "lon": lon}
            self.j.handle(dict(bug, event="ScanOrganic", timestamp=self.at(10 + i), ScanType=kind))
        self.assertEqual(self.db.execute("SELECT count(*) FROM sample_points").fetchone()[0], 0)   # the run is done
        self.j.status_json = {"live": True, "ts": self.at(29), "body": "Sys 2 a", "lat": 0.0, "lon": 0.0302}
        self.j.handle({"event": "Screenshot", "timestamp": self.at(30), "Filename": "\\ED_Pictures\\Screenshot_0001.bmp",
                       "System": "Sys", "Body": "Sys 2 a"})
        bmp(os.path.join(self.pictures, "Screenshot_0001.bmp"), 320, 180)
        self.st.shots_cfg["filename"] = "{body} {subject}"
        self.run_queue()
        [r] = self.db.execute("SELECT * FROM screenshots").fetchall()
        self.assertEqual(json.loads(r["subject"])["name"], "Bacterium Bullaris - Yellow")
        self.assertTrue(os.path.basename(r["full"]).startswith("2 a Bacterium Bullaris - Yellow"), r["full"])
        with Image.open(r["full"]) as im:
            self.assertIn("<rdf:li>Yellow</rdf:li>", im.text["XML:com.adobe.xmp"])   # the colour, a keyword of its own

    def test_the_clipboard_after_a_live_shot_never_the_backlog(self):
        copied = []

        class Clip:
            def copy_image(self, png, dib=None):
                copied.append((png[:8], len(dib or b"")))
                return True, None
        self.st.clipboard = Clip()
        self.st.shots_cfg.update(clipboard="medium")
        self.shoot()
        self.run_queue()
        self.assertEqual([c[0] for c in copied], [b"\x89PNG\r\n\x1a\n"])   # the medium copy, as PNG for the clipboard
        self.assertEqual(self.st.shots_last["clipboard"], "copied the medium copy")
        self.st.shots_cfg.update(clipboard="crop")   # not made: the first picture that was
        self.shoot(name="Screenshot_0002.bmp")
        self.j.shots_new[0]["ts"] = self.at(31)
        self.run_queue()
        self.assertEqual(self.st.shots_last["clipboard"], "copied the medium copy")
        self.st.shots_queue.append(dict(self.j.shots_new[0] if self.j.shots_new else {"ts": self.at(32)}, original="Screenshot_0003.bmp",
                                        ts=self.at(32), backlog=True, system="Sys", body="Sys 2 a", system_id=9))
        bmp(os.path.join(self.pictures, "Screenshot_0003.bmp"), 320, 180)
        self.run_queue()
        self.assertEqual(len(copied), 2)   # the backlog's never
        self.assertIsNone(self.st.shots_last["clipboard"])

    def test_a_catch_up_never_converts_and_off_drops(self):
        self.j.handle({"event": "Screenshot", "timestamp": "2020-01-01T00:00:00Z", "Filename": "\\ED_Pictures\\old.bmp"})
        self.assertEqual(self.j.shots_new, [])               # not live: never
        self.st.shots_cfg["enabled"] = False
        self.shoot()
        self.run_queue()
        self.assertEqual(self.db.execute("SELECT count(*) FROM screenshots").fetchone()[0], 0)
        self.assertIn("off", self.st.shots_why_off())
        self.st.shots_cfg["enabled"] = True
        self.st.game_pc = False
        self.assertEqual(self.st.shots_why_off(), ed_outrider.NOT_GAME_PC)
        self.assertIsNone(self.st.shots_summary())
        self.st.game_pc = True
        with unittest.mock.patch.object(S, "pillow", return_value=None):
            self.assertIn("Pillow", self.st.shots_why_off())

    def test_a_file_never_written_is_said(self):
        self.shoot(make=False)
        with unittest.mock.patch.object(S, "WAIT_S", 0.2), unittest.mock.patch.object(S.wait_ready, "__defaults__", (0.2, 0.1, time.sleep, time.monotonic)):
            self.run_queue()
        [r] = self.db.execute("SELECT * FROM screenshots").fetchall()
        self.assertIn("never appeared", r["error"])
        [card] = [n for n in self.st.notices.active() if n["key"] == "screenshots"]
        self.assertIn("could not be converted", card["text"])
        self.assertFalse(self.st.shots_last["ok"])

    def test_the_backlog(self):
        jd = os.path.join(self.d, "journals")
        os.makedirs(jd)
        with open(os.path.join(jd, "Journal.2026-10-25T150000.01.log"), "w") as f:
            f.write('{"timestamp":"2026-10-25T20:00:00Z", "event":"LoadGame", "Commander":"Hefay"}\n')
            f.write('{"timestamp":"2026-10-25T20:33:35Z", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_0002.bmp", '
                    '"System":"Sys", "Body":"Sys 2 a"}\n')
        p = bmp(os.path.join(self.pictures, "Screenshot_0002.bmp"))
        t = ed_outrider.ts_seconds("2026-10-25T20:33:37Z")
        os.utime(p, (t, t))
        bmp(os.path.join(self.pictures, "Screenshot_0003.bmp"))   # no event: an unknown system
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [jd]):
            out, status = asyncio.run(self.backlog())
        self.assertEqual((status, out["queued"], out["matched"], out["unmatched"]), (200, 2, 1, 1))
        rows = {r["original"]: r for r in self.db.execute("SELECT * FROM screenshots")}
        self.assertEqual((rows["Screenshot_0002.bmp"]["cmdr"], rows["Screenshot_0002.bmp"]["system_name"]), ("Hefay", "Sys"))
        self.assertIsNone(rows["Screenshot_0003.bmp"]["error"])
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [jd]):
            again, _ = asyncio.run(self.backlog())
        self.assertEqual((again["queued"], again["skipped"]), (0, 2))   # converted already: left alone

    def test_the_backlog_with_the_switch_off(self):
        self.st.shots_cfg.update(enabled=False)
        bmp(os.path.join(self.pictures, "Screenshot_0004.bmp"))
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
            out, status = asyncio.run(self.backlog())
        self.assertEqual((status, out["queued"]), (200, 1))         # the button converts with the switch off
        self.st.shots_cfg.update(pictures="")                      # but no Pictures folder: said, never a crash
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
            out, status = asyncio.run(self.backlog())
        self.assertEqual(status, 409)
        self.assertIn("Pictures folder", out["error"])

    async def backlog(self):
        out = await self.st.shots_backlog()
        if self.st.shots_task:
            await self.st.shots_task
        return out


class Folders(unittest.TestCase):
    """Settings' folder picker: a folder's subfolders on the game PC, names only (the author, 2026-10-25)."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        for n in ("b", "A", ".steam", "c"):
            os.makedirs(os.path.join(self.d, n))
        with open(os.path.join(self.d, "a file.bmp"), "w") as f:
            f.write("x")

    def test_listing(self):
        r = S.list_folders(self.d)
        self.assertEqual((r["path"], r["parent"], r["dirs"], r["hidden"], r["missing"], r["error"]),
                         (self.d, os.path.dirname(self.d), ["A", "b", "c"], 1, None, None))   # never a file; dot-folders apart
        self.assertEqual(S.list_folders(self.d, hidden=True)["dirs"], ["A", "b", "c", ".steam"])
        gone = os.path.join(self.d, "b", "not yet", "deeper")
        r = S.list_folders(gone)
        self.assertEqual((r["path"], r["missing"]), (os.path.join(self.d, "b"), gone))   # its nearest folder that is there
        self.assertEqual(S.list_folders("")["path"], os.path.expanduser("~"))
        self.assertIsNone(S.list_folders(os.path.abspath(os.sep))["parent"])
        with unittest.mock.patch.object(S.os, "scandir", side_effect=PermissionError(13, "Permission denied")):
            r = S.list_folders(self.d)
        self.assertEqual((r["path"], r["dirs"]), (self.d, []))
        self.assertIn("cannot be read", r["error"])

    def test_the_route_is_the_game_pcs(self):
        from aiohttp.test_utils import TestClient, TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        st = ed_outrider.State(db, ed_outrider.Journals(db), ed_outrider.Spansh(db), 25)

        async def go():
            async with TestClient(TestServer(ed_outrider.make_app(st))) as c:
                r = await c.get("/api/folders", params={"path": self.d})
                out = [r.status, (await r.json())["dirs"]]
                st.game_pc = False
                out.append((await c.get("/api/folders", params={"path": self.d})).status)   # a server: not its folders
                return out
        self.assertEqual(asyncio.run(go()), [200, ["A", "b", "c"], 409])


class Settings(unittest.TestCase):
    def test_clamped_and_homed(self):
        num = lambda sec, table, key, conv, default: ed_outrider._config_value(sec, key, table.get(key), conv, default)
        flag = lambda sec, table, key, default: ed_outrider._config_value(sec, key, table.get(key), ed_outrider._config_bool, default)
        st = ed_outrider.screenshots_settings({"format": "TIFF", "medium": 99999, "subject_m": -5, "original": "move"}, num, flag)
        self.assertEqual((st["format"], st["medium"], st["subject_m"], st["original"], st["by_cmdr"]), ("png", 7680, 0, "move", True))
        st = ed_outrider.screenshots_settings({"jpg_quality": 70, "resized_quality": 60, "crop": "5,5,200,90", "copies_format": "WEBP",
                                               "clipboard": "Medium", "format": "webp"}, num, flag)
        self.assertEqual((st["quality"], st["copies_quality"], st["crop"], st["copies_format"], st["clipboard"], st["format"], st["full"]),
                         (70, 60, "5, 5, 95, 90", "webp", "medium", "webp", True))   # the names before the release still read
        import outrider.config_edit as C
        self.assertTrue(C.homed("screenshots", "folder"))
        self.assertIn(("screenshots", "folder"), ed_outrider.State.LIVE_CONFIG)


if __name__ == "__main__":
    unittest.main()
