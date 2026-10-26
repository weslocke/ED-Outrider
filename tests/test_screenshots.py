"""Screenshots (a player's request, 2026-10-25: to drop EDDiscovery's): the game's F10 / Alt+F10 shots converted as they
are taken (outrider/screenshots.py, State.shot_convert), what a surface shot shows (geo_tags, sample spots, tags), the
backlog, the endpoints. Fakes only: a tiny BMP made here, temp folders, never the player's."""
import asyncio
import datetime
import io
import json
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock
import urllib.parse

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.screenshots as S  # noqa: E402

Image = S.pillow()


def bmp(path, w=64, h=36, colour=(200, 120, 40)):
    Image.new("RGB", (w, h), colour).save(path, "BMP")
    return path


class _Fn:
    """A stand-in Win32 function: callable, and takes the argtypes / restype a ctypes function is given."""
    def __init__(self, f):
        self.f = f

    def __call__(self, *a):
        return self.f(*a)


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
        subs = [{"kind": "bio", "name": "Stratum Tectonicas - Lime", "lat": 0.0, "lon": 0.001,          # ~17 m
                 "group": "Stratum", "entry": "Stratum Tectonicas"},
                {"kind": "geo", "name": "Water Ice Geyser", "entry_id": 1400258, "lat": 0.0, "lon": 0.002}]   # ~35 m
        self.assertEqual(S.nearest_subject(0.0, 0.0, R, subs, 50), {"kind": "bio", "name": "Stratum Tectonicas - Lime", "entry_id": None,
                                                                    "group": "Stratum", "entry": "Stratum Tectonicas", "colour": None,
                                                                    "dist": 17})
        self.assertIsNone(S.nearest_subject(0.0, 0.0, R, subs, 10))     # none that close
        self.assertIsNone(S.nearest_subject(None, None, R, subs, 50))   # a shot from the air
        self.assertIsNone(S.nearest_subject(0.0, 0.0, R, subs, 0))      # off
        events = [(1000.0, "Screenshot_0001.bmp", {"n": "old"}), (5000.0, "Screenshot_0001.bmp", {"n": "new"})]
        got = S.match_backlog([("Screenshot_0001.bmp", 5002.0), ("Screenshot_0009.bmp", 5000.0)], events)
        self.assertEqual(got, {"Screenshot_0001.bmp": {"n": "new"}, "Screenshot_0009.bmp": None})   # a reused name: by time

    def test_codex_dir(self):
        """[screenshots] codex: Biology/<genus>/<species> or Geology/<group>/<name> under the export folder; never filed
        by a guess (no group or entry, another kind, no subject)."""
        root = os.path.join("x", "out")
        self.assertEqual(S.codex_dir(root, {"kind": "bio", "name": "Tussock Albata - Green", "group": "Tussock", "entry": "Tussock Albata",
                                            "colour": "Green"}), os.path.join(root, "Biology", "Tussock", "Tussock Albata", "Green"))
        # a species with no colours: no colour folder; one whose colour cannot be told: not filed
        self.assertEqual(S.codex_dir(root, {"kind": "bio", "group": "Anemone", "entry": "Luteolum Anemone", "colour": ""}),
                         os.path.join(root, "Biology", "Anemone", "Luteolum Anemone"))
        self.assertIsNone(S.codex_dir(root, {"kind": "bio", "group": "Tussock", "entry": "Tussock Albata", "colour": None}))
        self.assertIsNone(S.codex_dir(None, {"kind": "geo", "group": "Geyser", "entry": "Water Geyser"}))
        self.assertEqual(S.codex_dir(root, {"kind": "geo", "name": "Geysir d'eau", "group": "Geyser", "entry": "Water Geyser"}),
                         os.path.join(root, "Geology", "Geyser", "Water Geyser"))   # the English name, whatever the game's
        self.assertEqual(S.codex_dir(root, {"kind": "geo", "group": "A/B", "entry": "C:D"}), os.path.join(root, "Geology", "A_B", "C_D"))
        for subj in (None, {"kind": "bio", "name": "X", "group": None, "entry": "X"}, {"kind": "bio", "group": "G"},
                     {"kind": "other", "group": "G", "entry": "E"}):
            self.assertIsNone(S.codex_dir(root, subj), subj)
        # the pictures in one: images only, files only, not hidden
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for n in ("b.JPG", "a.png", "c.webp", ".hidden.png", "notes.txt", "x.bmp"):
            open(os.path.join(d, n), "w").close()
        os.mkdir(os.path.join(d, "sub.png"))
        self.assertEqual(S.codex_pictures(d), ["a.png", "b.JPG", "c.webp"])
        self.assertEqual(S.codex_pictures(os.path.join(d, "none")), [])

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
        # a long session's part 2 has no LoadGame: it keeps part 1's commander; a new session's part 1 starts afresh
        # (review 2026-10-25: part 2's shots were filed under "Unknown commander")
        p2, p3 = os.path.join(d, "Journal.2026-10-25T150000.02.log"), os.path.join(d, "Journal.2026-10-26T150000.01.log")
        with open(p2, "w") as f:
            f.write('{"timestamp":"2026-10-25T23:00:00Z", "event":"Fileheader", "part":2}\n'
                    '{"timestamp":"2026-10-25T23:01:00Z", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_0003.bmp"}\n')
        with open(p3, "w") as f:
            f.write('{"timestamp":"2026-10-26T15:00:00Z", "event":"Fileheader", "part":1}\n'
                    '{"timestamp":"2026-10-26T15:01:00Z", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_0004.bmp"}\n')
        self.assertEqual([x["cmdr"] for x in S.journal_shots([p, p2, p3])], ["Hefay", "Hefay", None])


@unittest.skipIf(Image is None, "Pillow is not installed")
class Convert(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def test_picture_facts(self):
        """When and where a picture was taken, read back from what Outrider wrote into it (the checklists' caption, the
        author 2026-10-26): its own XMP fields in every format; a picture from before them by its keywords; nothing from
        a picture with none of it."""
        src = bmp(os.path.join(self.d, "Screenshot_0001.bmp"), 64, 36)
        shot = {"ts": "2026-10-26T12:51:14Z", "system": "Smojooe UW-E c11-28", "body": "Smojooe UW-E c11-28 7 f",
                "subject": {"kind": "bio", "name": "Tussock Albata - Green", "dist": 3}, "cmdr": "Hefay"}
        local = datetime.datetime(2026, 10, 26, 12, 51, 14, tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d")
        want = {"taken": local, "system": "Smojooe UW-E c11-28", "body": "7 f"}
        for fmt in S.FORMATS:
            p = os.path.join(self.d, f"a.{S.EXT[fmt]}")
            S.convert(src, {"dir": self.d, "full": p}, dict(S.DEFAULTS, format=fmt), shot)
            self.assertEqual(S.picture_facts(p), want, fmt)
        # a picture from before the fields (2026-10-26): its keywords, when the body's name starts with the system's
        real = S.xmp_packet
        old = lambda m, d: real({k: v for k, v in m.items() if k not in ("system", "body")}, d)   # noqa: E731
        with unittest.mock.patch.object(S, "xmp_packet", old):
            S.convert(src, {"dir": self.d, "full": os.path.join(self.d, "old.jpg")}, dict(S.DEFAULTS, format="jpg"), shot)
            S.convert(src, {"dir": self.d, "full": os.path.join(self.d, "earth.jpg")}, dict(S.DEFAULTS, format="jpg"),
                      dict(shot, system="Sol", body="Earth"))
        self.assertEqual(S.picture_facts(os.path.join(self.d, "old.jpg")), want)
        self.assertEqual(S.picture_facts(os.path.join(self.d, "earth.jpg")), {"taken": local, "system": None, "body": None})
        # a body not named after its system: its own name alone, not "Sol Earth" (review 2026-10-26)
        S.convert(src, {"dir": self.d, "full": os.path.join(self.d, "earth2.jpg")}, dict(S.DEFAULTS, format="jpg"),
                  dict(shot, system="Sol", body="Earth"))
        self.assertEqual(S.picture_facts(os.path.join(self.d, "earth2.jpg")), {"taken": local, "system": None, "body": "Earth"})
        # an edit that kept the XMP but not the EXIF: the date from XMP (local); a picture with nothing: {}
        with Image.open(os.path.join(self.d, "a.png")) as im:
            im.save(os.path.join(self.d, "edited.jpg"), "JPEG", xmp=im.info["XML:com.adobe.xmp"].encode())
            im.save(os.path.join(self.d, "bare.png"), "PNG")
        self.assertEqual(S.picture_facts(os.path.join(self.d, "edited.jpg")), want)
        self.assertEqual(S.picture_facts(os.path.join(self.d, "bare.png")), {})
        with open(os.path.join(self.d, "junk.png"), "wb") as f:
            f.write(b"not a picture")
        self.assertEqual(S.picture_facts(os.path.join(self.d, "junk.png")), {})

    def test_picture_facts_never_decodes_nor_stalls(self):
        """Review 2026-10-26: a PNG without EXIF was decoded whole; any decoder Pillow has opened a dropped-in file (an EPS
        named .png ran Ghostscript); a crafted XMP packet took minutes; a date out of range raised."""
        from PIL import PngImagePlugin
        m = S.metadata({"ts": "2026-10-26T12:51:14Z", "system": "Sys", "body": "Sys 2 a"})
        info = PngImagePlugin.PngInfo()
        info.add_itxt("XML:com.adobe.xmp", S.xmp_packet(m, "d"))
        p = os.path.join(self.d, "noexif.png")
        Image.new("RGB", (64, 36)).save(p, "PNG", pnginfo=info)
        with unittest.mock.patch.object(PngImagePlugin.PngImageFile, "load", side_effect=AssertionError("decoded")):
            got = S.picture_facts(p)
        self.assertEqual((got["system"], got["body"], len(got["taken"])), ("Sys", "2 a", 10))   # the date from the XMP
        eps = os.path.join(self.d, "pack.png")
        with open(eps, "w") as f:
            f.write("%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nnewpath 0 0 moveto 10 10 lineto stroke\nshowpage\n")
        with unittest.mock.patch("subprocess.check_call", side_effect=AssertionError("ghostscript ran")), \
                unittest.mock.patch("subprocess.Popen", side_effect=AssertionError("ghostscript ran")):
            self.assertEqual(S.picture_facts(eps), {})
        info = PngImagePlugin.PngInfo()
        info.add_itxt("XML:com.adobe.xmp", "<edo:System>" * 40000 + "<rdf:Bag>" + "<rdf:li>" * 20000)
        p = os.path.join(self.d, "crafted.png")
        Image.new("RGB", (8, 8)).save(p, "PNG", pnginfo=info)
        t = time.monotonic()
        self.assertEqual(S.picture_facts(p), {})
        self.assertLess(time.monotonic() - t, 2)
        for when, xmp in (("0000:00:00 00:00:00", "<xmp:CreateDate>0001-01-01T00:00:00Z</xmp:CreateDate>"),
                          ("2026:13:40 00:00:00", "<xmp:CreateDate>9999-12-31T23:59:59Z</xmp:CreateDate>")):
            e = Image.Exif()
            e.get_ifd(0x8769)[0x9003] = when
            p = os.path.join(self.d, "dates.jpg")
            Image.new("RGB", (8, 8)).save(p, "JPEG", exif=e, xmp=xmp.encode())
            got = S.picture_facts(p)   # never raises
            self.assertNotEqual(got.get("taken"), when[:10].replace(":", "-"))

    def test_a_failed_codex_save_leaves_nothing(self):
        """Review 2026-10-26: a copy or a conversion that failed halfway left a broken picture the checklists picked."""
        src = bmp(os.path.join(self.d, "Screenshot_0001.bmp"), 64, 36)
        shot = {"ts": "2026-10-25T20:33:35Z", "system": "Sys", "body": "Sys 2 a"}
        cfg = dict(S.DEFAULTS, format="jpg")
        paths = S.plan_paths(cfg, S.fields_for(shot), os.path.join(self.d, "out"))
        written = S.convert(src, paths, cfg, shot)["written"]
        folder = os.path.join(self.d, "codex")

        def half(a, b, *k, **kw):
            with open(b, "wb") as f:
                f.write(b"half")
            raise OSError("disk full")
        with unittest.mock.patch.object(S.shutil, "copy2", half), self.assertRaises(OSError):
            S.to_codex(src, written, None, folder, cfg, shot)
        self.assertEqual(os.listdir(folder), [])
        real = S.convert

        def half_convert(src_, paths_, *a, **kw):
            with open(paths_["full"], "wb") as f:
                f.write(b"half")
            raise OSError("disk full")
        with unittest.mock.patch.object(S, "convert", half_convert), self.assertRaises(OSError):
            S.to_codex(src, written, None, folder, dict(cfg, codex_format="png"), shot)
        self.assertEqual(os.listdir(folder), [])
        self.assertIs(S.convert, real)

    def test_to_codex(self):
        """[screenshots] codex_format (the author, 2026-10-26: small everyday shots, fine codex pictures): "" copies the
        first picture written; a format converts the game's BMP again at full size at codex_quality, unless the full
        size written is that already (then a copy)."""
        src = bmp(os.path.join(self.d, "Screenshot_0001.bmp"), 640, 360)
        shot = {"ts": "2026-10-25T20:33:35Z", "system": "Sys", "body": "Sys 2 a", "subject": {"kind": "bio", "name": "Tussock Albata - Green"}}
        out = os.path.join(self.d, "out")
        cfg = dict(S.DEFAULTS, format="jpg", quality=70, full=False, small=320)
        paths = S.plan_paths(cfg, S.fields_for(shot), out)
        written = S.convert(src, paths, cfg, shot)["written"]                 # a small JPG only
        folder = os.path.join(self.d, "codex")
        got = S.to_codex(src, written, None, folder, cfg, shot)                 # "": a copy of it
        with open(got, "rb") as a, open(written[0], "rb") as b:
            self.assertEqual(a.read(), b.read())
        got = S.to_codex(src, written, None, folder, dict(cfg, codex_format="png"), shot)   # the BMP again, full size
        self.assertEqual(os.path.splitext(got)[0], os.path.join(folder, os.path.splitext(os.path.basename(written[0]))[0]))
        with Image.open(got) as im:
            self.assertEqual((im.format, im.size), ("PNG", (640, 360)))
            self.assertIn("Tussock Albata - Green", im.text["Description"])   # what it shows, written in as ever
        self.assertEqual(int(os.path.getmtime(got)), S.when_seconds(shot["ts"]))
        # the full size is that format at that quality already: a copy; another quality: converted again
        cfg = dict(cfg, full=True, small=0)
        paths = S.plan_paths(cfg, S.fields_for(shot), out)
        written = S.convert(src, paths, cfg, shot)["written"]
        same = S.to_codex(src, written, paths["full"], folder, dict(cfg, codex_format="jpg", codex_quality=70), shot)
        finer = S.to_codex(src, written, paths["full"], folder, dict(cfg, codex_format="jpg", codex_quality=98), shot)
        with open(same, "rb") as a, open(paths["full"], "rb") as b, open(finer, "rb") as c:
            full = b.read()
            self.assertEqual(a.read(), full)
            self.assertGreater(len(c.read()), len(full))
        self.assertEqual(len(os.listdir(folder)), 4)   # never over one another: " (2)"...

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
            local = datetime.datetime(2026, 10, 25, 20, 33, 35, tzinfo=datetime.timezone.utc).astimezone()
            self.assertEqual((ex[0x013B], ex.get_ifd(0x8769)[0x9003]), ("CMDR Hefay", local.strftime("%Y:%m:%d %H:%M:%S")))
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

    def test_review_2_files(self):
        """The in-depth review of 2026-10-25: WebP past its 16383 px limit as JPG; every picture decoded whole before
        the original may go; EXIF dates local with their offset; a name with no ASCII form never an empty credit."""
        src = bmp(os.path.join(self.d, "HighResScreenShot_1.bmp"), 16400, 8)
        shot = {"ts": "2026-10-25T20:33:35Z", "system": "Sys", "body": "Sys 2 a", "cmdr": "Сёма"}
        cfg = dict(S.DEFAULTS, format="webp", medium=1920, copies_format="webp")
        paths = S.plan_paths(cfg, S.fields_for(shot), os.path.join(self.d, "out"))
        out = S.convert(src, paths, cfg, shot)
        self.assertTrue(paths["full"].endswith(".jpg") and paths["full"] in out["written"], paths["full"])   # too wide for WebP
        self.assertTrue(paths["medium"].endswith(".webp"))
        with Image.open(paths["full"]) as im:
            ex = im.getexif()
            local = datetime.datetime(2026, 10, 25, 20, 33, 35, tzinfo=datetime.timezone.utc).astimezone()
            z = local.strftime("%z")
            ifd = ex.get_ifd(0x8769)
            self.assertEqual((ifd[0x9003], ifd[0x9011]), (local.strftime("%Y:%m:%d %H:%M:%S"), f"{z[:3]}:{z[3:]}"))
            self.assertNotIn(0x013B, ex)                     # Artist: nothing left of "Сёма" in ASCII, so left out
            self.assertNotIn("CMDR", ex[0x010E])
            self.assertEqual(bytes(ex[0x9C9D]).decode("utf-16-le").rstrip("\0"), "CMDR Сёма")   # XPAuthor has it all
        self.assertEqual(S.ascii_fold("Łukasz Sjöberg °"), "Lukasz Sjoberg")
        # a JPG whose body is bad is caught by the read-back (verify() read its header only)
        small = bmp(os.path.join(self.d, "Screenshot_0002.bmp"), 640, 360)
        jpg = dict(S.DEFAULTS, format="jpg")
        real_save = Image.Image.save

        def broken(im, fp, *a, **k):
            real_save(im, fp, *a, **k)
            if isinstance(fp, str) and fp.endswith(".jpg"):
                with open(fp, "r+b") as f:
                    f.truncate(os.path.getsize(fp) // 2)
        with unittest.mock.patch.object(Image.Image, "save", broken), self.assertRaises(OSError):
            S.convert(small, S.plan_paths(jpg, S.fields_for(shot), os.path.join(self.d, "o2")), jpg, shot)

    def test_review_3_files(self):
        """A formation's picture gets no first-word keyword ("Water"); an empty file settles after a few seconds rather
        than waiting the minute; the clipboard's picture has no DIB on Linux (third in-depth review 2026-10-25)."""
        m = S.metadata({"ts": "2026-10-25T20:00:00Z", "system": "Sol", "body": "Sol 4", "subject": {"kind": "geo", "name": "Water Ice Geyser", "dist": 12}})
        self.assertEqual(m["keywords"], ["Elite Dangerous", "Sol", "Sol 4", "Water Ice Geyser", "Geology"])
        empty = os.path.join(self.d, "e.bmp")
        open(empty, "wb").close()
        t = [0.0]
        def sleep(s):
            t[0] += s
        self.assertTrue(S.wait_ready(empty, timeout=60, poll=0.5, sleep=sleep, clock=lambda: t[0]))
        self.assertLess(t[0], 10)
        src = bmp(os.path.join(self.d, "c.bmp"), 64, 36)
        png, dib = S.clipboard_image(src, dib=False)
        self.assertEqual((bytes(png[:4]), dib), (b"\x89PNG", None))
        self.assertTrue(len(S.clipboard_image(src)[1]) > 0)

    def test_review_4_files(self):
        """Fourth in-depth review 2026-10-25: the clipboard's picture is plain bytes (a kept slice of a live view made
        its buffer un-closeable); a file typed where a folder goes is said to be a file."""
        src = bmp(os.path.join(self.d, "c.bmp"), 64, 36)
        png, dib = S.clipboard_image(src)
        self.assertEqual((type(png), type(dib)), (bytes, bytes))
        r = S.list_folders(src)
        self.assertEqual((r["file"], r["missing"], r["path"]), (src, None, self.d))

    def test_review_4_windows_clipboard(self):
        """The picture is on the Windows clipboard once CF_DIB is set: the PNG format refused after it is no failure."""
        import ctypes
        import types
        import outrider.winkeys as W
        bufs, set_calls = [], []

        def alloc(flags, n):
            bufs.append(ctypes.create_string_buffer(n))
            return len(bufs)
        k32 = types.SimpleNamespace(GlobalAlloc=alloc, GlobalLock=lambda h: ctypes.addressof(bufs[h - 1]),
                                    GlobalUnlock=lambda h: None, GlobalFree=lambda h: None)
        u32 = types.SimpleNamespace(OpenClipboard=lambda h: 1, EmptyClipboard=lambda: 1, CloseClipboard=lambda: 1,
                                    SetClipboardData=lambda fmt, h: (set_calls.append(fmt), fmt == 8)[1],
                                    RegisterClipboardFormatW=lambda n: 49300)
        for ns in (k32, u32):   # the argtypes / restype attributes the real functions take
            for name in vars(ns).copy():
                setattr(ns, name, _Fn(getattr(ns, name)))
        with unittest.mock.patch.object(ctypes, "WinDLL", lambda name, **kw: k32 if name == "kernel32" else u32, create=True), \
                unittest.mock.patch.object(ctypes, "get_last_error", lambda: 5, create=True):
            W.set_clipboard_image(b"DIB", b"PNG")   # no exception: CF_DIB was taken
            self.assertEqual(set_calls, [8, 49300])
            set_calls.clear()
            u32.SetClipboardData = _Fn(lambda fmt, h: (set_calls.append(fmt), False)[1])
            with self.assertRaises(OSError):         # nothing taken at all: a failure
                W.set_clipboard_image(b"DIB", b"PNG")

    def test_crop_text(self):
        self.assertEqual(S.parse_crop("10, 10, 80, 75"), (10, 10, 80, 75))
        self.assertEqual(S.parse_crop("90 0 50 100"), (90, 0, 10, 100))     # cut at the picture's edge
        for bad in ("", "10, 10, 80", "a, b, c, d", "0, 0, 0.5, 50"):
            self.assertIsNone(S.parse_crop(bad))
        self.assertEqual(S.crop_box((3072, 1728), (10, 10, 80, 75)), (307, 173, 2765, 1469))

    def test_moved_to_needs_a_folder_that_is_not_the_games(self):
        src = bmp(os.path.join(self.d, "a.bmp"))
        with self.assertRaisesRegex(ValueError, "no folder"):
            S.finish_original(src, dict(S.DEFAULTS, original="move", move_to=""), "x")
        with self.assertRaisesRegex(ValueError, "own Pictures folder"):
            S.finish_original(src, dict(S.DEFAULTS, original="move", move_to=self.d + os.sep), "x")
        self.assertTrue(os.path.isfile(src))

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
        # never a file outside the folder: a real one there, and a link inside the folder pointing at it (third in-depth
        # review 2026-10-25: the file did not exist, so the test passed without the folder check)
        outside = os.path.join(self.d, "elsewhere.png")
        shutil.copy(r["full"], outside)
        self.db.execute("UPDATE screenshots SET full=? WHERE id=?", (outside, x["id"]))
        self.assertIsNone(asyncio.run(self.st.shot_image(x["id"], "full")))
        link = os.path.join(self.out, "link.png")
        os.symlink(outside, link)
        self.db.execute("UPDATE screenshots SET full=? WHERE id=?", (link, x["id"]))
        self.assertIsNone(asyncio.run(self.st.shot_image(x["id"], "full")))

    def test_codex_copies(self):
        """[screenshots] codex (the author, 2026-10-26: a codex of their own pictures for the Bio/Geo page to show): a shot of
        a formation also copied to Geology/<group>/<name> in the export folder, not per commander; off by default; a
        failed copy is said and the shot is fine."""
        self.shoot()
        self.run_queue()
        self.assertFalse(os.path.exists(os.path.join(self.out, "Geology")))   # off by default
        self.st.shots_cfg["codex"] = True
        self.shoot("Screenshot_0002.bmp")
        self.run_queue()
        r = self.db.execute("SELECT * FROM screenshots WHERE original='Screenshot_0002.bmp'").fetchone()
        subj = json.loads(r["subject"])
        self.assertEqual((subj["group"], subj["entry"]), ("Geyser", "Water Ice Geyser"))
        folder = os.path.join(self.out, "Geology", "Geyser", "Water Ice Geyser")
        copy = os.path.join(folder, os.path.basename(r["full"]))
        self.assertEqual(self.st.shots_last["codex"], copy)
        with open(copy, "rb") as a, open(r["full"], "rb") as b:
            self.assertEqual(a.read(), b.read())   # the full-size picture, as written
        self.assertEqual(int(os.path.getmtime(copy)), int(os.path.getmtime(r["full"])))   # dated when taken
        # a shot with no formation near: no copy
        self.shoot("Screenshot_0003.bmp", lon=0.5)
        self.run_queue()
        self.assertIsNone(self.st.shots_last["codex"])
        self.assertEqual(len(os.listdir(folder)), 1)
        # the folder cannot be made (a file in its place): the shot is converted, a card says why
        shutil.rmtree(os.path.join(self.out, "Geology"))
        with open(os.path.join(self.out, "Geology"), "w"):
            pass
        self.shoot("Screenshot_0004.bmp")
        self.run_queue()
        self.assertTrue(self.st.shots_last["ok"])
        self.assertIsNone(self.st.shots_last["codex"])
        [card] = [n for n in self.st.notices.active() if n["key"] == "screenshots"]
        self.assertIn("codex", card["text"])
        # with the BMP not moved too: both said (review 2026-10-26: the codex failure hid behind the BMP's)
        self.st.shots_cfg.update(original="move", move_to="")
        self.shoot("Screenshot_0006.bmp")
        self.run_queue()
        [card] = [n for n in self.st.notices.active() if n["key"] == "screenshots"]
        self.assertIn("was not moved or deleted", card["text"])
        self.assertIn("not copied to your codex folders", card["text"])
        self.assertTrue(self.st.shots_last["codex_error"])
        self.st.shots_cfg.update(original="keep")
        # a codex format: the game's BMP converted again before it is deleted (small JPGs everyday, a PNG for the codex)
        os.remove(os.path.join(self.out, "Geology"))
        self.st.shots_cfg.update(format="jpg", codex_format="png", original="delete")
        self.shoot("Screenshot_0005.bmp")
        self.run_queue()
        r = self.db.execute("SELECT * FROM screenshots WHERE original='Screenshot_0005.bmp'").fetchone()
        self.assertTrue(r["full"].endswith(".jpg") and self.st.shots_last["codex"].endswith(".png"), self.st.shots_last)
        with Image.open(self.st.shots_last["codex"]) as im:
            self.assertEqual((im.format, im.size), ("PNG", (320, 180)))
        self.assertFalse(os.path.exists(os.path.join(self.pictures, "Screenshot_0005.bmp")))   # deleted after

    def test_checklists_show_your_own_pictures(self):
        """[screenshots] codex_show (the author, 2026-10-26): a checklist entry's picture is one of your own from its codex
        folder (a species' colour, a formation), any picture there, picked at random; Canonn's where there is none; the
        pictures served by name inside that folder only, shrunk for the panel."""
        sid = "$Codex_Ent_Bacterial_10_Name;"
        yellow = os.path.join(self.out, "Biology", "Bacterium", "Bacterium Bullaris", "Yellow")
        geyser = os.path.join(self.out, "Geology", "Geyser", "Water Ice Geyser")
        for folder, names in ((yellow, ("mine.png", "cropped.png")), (geyser, ("g.png",))):
            os.makedirs(folder)
            for n in names:
                Image.new("RGB", (2000, 1000), (200, 180, 20)).save(os.path.join(folder, n))
        canonn = {"bacterium bullaris - yellow": ["https://c/y.jpg", "Someone"], "bacterium bullaris - red": ["https://c/r.jpg", "Other"],
                  "water ice geyser": ["https://c/g.jpg", "Third"]}
        self.st._codex_images = canonn
        sp, _ = self.st.checklist_species(sid)
        self.assertEqual(sp["images"]["yellow"], {"url": "https://c/y.jpg", "cmdr": "Someone"})   # off by default: Canonn's
        self.st.shots_cfg["codex_show"] = True
        seen = set()
        for _ in range(40):
            sp, _ = self.st.checklist_species(sid)
            seen.add(sp["images"]["yellow"]["file"])
        self.assertEqual(seen, {"mine.png", "cropped.png"})                                  # at random, from the folder
        self.assertEqual(sp["images"]["red"], {"url": "https://c/r.jpg", "cmdr": "Other"})  # no folder: Canonn's
        # each click on a colour picks again (the author, 2026-10-26), never the one shown when there is another
        for shown in ("mine.png", "cropped.png") * 5:
            got, status = self.st.checklist_picture(sid, "Yellow", shown)
            self.assertEqual((status, got["image"]["own"]), (200, True))
            self.assertNotEqual(got["image"]["file"], shown)
        self.assertIsNone(self.st.checklist_picture(sid, "red")[0]["image"])     # none of your own: the page keeps Canonn's
        self.assertEqual(self.st.checklist_picture(sid, "Plaid")[1], 400)
        self.assertEqual(self.st.checklist_picture("$Nope;", "yellow")[1], 404)
        img = sp["images"]["yellow"]
        self.assertTrue(img["own"] and img["url"].startswith("api/codex_picture?") and img["full"].endswith("&size=full"))
        q = dict(urllib.parse.parse_qsl(img["url"].split("?", 1)[1]))
        body, ctype = asyncio.run(self.st.codex_picture(q))
        self.assertEqual(ctype, "image/jpeg")
        with Image.open(io.BytesIO(body)) as im:
            self.assertEqual(max(im.size), self.st.CODEX_VIEW_PX)                            # shrunk for the panel
        self.assertEqual(asyncio.run(self.st.codex_picture(dict(q, size="full"))), (os.path.join(yellow, q["file"]), "image/png"))
        geo, _ = self.st.checklist_geo(1400258)
        self.assertEqual((geo["image"]["file"], geo["image"]["own"]), ("g.png", True))
        self.assertNotIn("taken", geo["image"])   # a picture that says nothing of itself: the caption says where it is from
        # one Outrider made says when and where it was taken
        os.remove(os.path.join(geyser, "g.png"))
        shot = {"ts": "2026-10-26T12:51:14Z", "system": "Sys", "body": "Sys 2 a", "subject": {"kind": "geo", "name": "Water Ice Geyser"}}
        S.convert(bmp(os.path.join(self.d, "src.bmp")), {"dir": geyser, "full": os.path.join(geyser, "g.jpg")}, dict(S.DEFAULTS, format="jpg"), shot)
        img = self.st.checklist_geo(1400258)[0]["image"]
        self.assertEqual((img["file"], img["system"], img["body"], len(img["taken"])), ("g.jpg", "Sys", "2 a", 10))
        # never anything but a picture in that folder: a path, a parent, another folder's, a file that is not a picture
        with open(os.path.join(self.out, "secret.png"), "wb") as f:
            f.write(b"x")
        open(os.path.join(yellow, "notes.txt"), "w").close()
        for bad in (dict(q, file="../../../../secret.png"), dict(q, file=os.path.join(self.out, "secret.png")), dict(q, file=".."),
                    dict(q, file="notes.txt"), dict(q, file="none.png"), dict(q, kind="other"), dict(q, colour="Red"),
                    dict(q, group="..", entry="..", colour="..")):
            self.assertIsNone(asyncio.run(self.st.codex_picture(bad)), bad)
        # an empty folder: Canonn's
        shutil.rmtree(geyser)
        os.makedirs(geyser)
        self.assertEqual(self.st.checklist_geo(1400258)[0]["image"], {"url": "https://c/g.jpg", "cmdr": "Third"})
        # review 2026-10-26: the link carries the file's time (an edit in place is not the cached one); a folder linked
        # from outside the export folder is not offered (codex_picture would refuse it): Canonn's; an EPS named .png is
        # never decoded
        Image.new("RGB", (40, 20)).save(os.path.join(geyser, "g.png"))
        img = self.st.checklist_geo(1400258)[0]["image"]
        self.assertIn(f"&v={int(os.path.getmtime(os.path.join(geyser, 'g.png')))}", img["url"])
        self.assertIsNotNone(asyncio.run(self.st.codex_picture(dict(urllib.parse.parse_qsl(img["url"].split("?", 1)[1])))))
        elsewhere = os.path.join(self.d, "elsewhere")
        shutil.move(os.path.join(self.out, "Geology"), elsewhere)
        os.symlink(elsewhere, os.path.join(self.out, "Geology"))
        self.assertEqual(self.st.checklist_geo(1400258)[0]["image"], {"url": "https://c/g.jpg", "cmdr": "Third"})
        with open(os.path.join(yellow, "pack.png"), "w") as f:
            f.write("%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nnewpath 0 0 moveto 10 10 lineto stroke\nshowpage\n")
        q = {"kind": "bio", "group": "Bacterium", "entry": "Bacterium Bullaris", "colour": "Yellow", "file": "pack.png"}
        with unittest.mock.patch("subprocess.check_call", side_effect=AssertionError("ghostscript ran")), \
                unittest.mock.patch("subprocess.Popen", side_effect=AssertionError("ghostscript ran")):
            self.assertIsNone(asyncio.run(self.st.codex_picture(q)))

    def test_a_reread_fills_a_tags_variant(self):
        """Review 2026-10-26: a plant tagged before bio_tags.variant existed kept NULL through a journal re-read (its
        INSERT OR IGNORE), so its shot was never filed by colour."""
        ev = {"event": "CodexEntry", "timestamp": self.at(5), "EntryID": 2370101, "Name": "$Codex_Ent_Tussocks_01_F_Name;",
              "Name_Localised": "Tussock Pennata - Yellow", "Category": "$Codex_Category_Biology;", "System": "Sys",
              "SystemAddress": 9, "BodyID": 6, "Latitude": 0.0, "Longitude": 0.002}
        self.j.handle(ev)
        self.db.execute("UPDATE bio_tags SET variant=NULL")
        self.j.handle(ev)
        self.assertEqual([r[0] for r in self.db.execute("SELECT variant FROM bio_tags")], ["$Codex_Ent_Tussocks_01_F_Name;"])

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
        self.st.shots_cfg.update(filename="{body} {subject}", codex=True)
        self.run_queue()
        [r] = self.db.execute("SELECT * FROM screenshots").fetchall()
        self.assertEqual(json.loads(r["subject"])["name"], "Bacterium Bullaris - Yellow")
        # [screenshots] codex: the rules' genus, species and colour (from the variant's code, kept with each spot)
        self.assertEqual(self.st.shots_last["codex"], os.path.join(self.out, "Biology", "Bacterium", "Bacterium Bullaris", "Yellow",
                                                                   os.path.basename(r["full"])))
        self.assertEqual({x[0] for x in self.db.execute("SELECT variant FROM bio_spots")}, {"$Codex_Ent_Bacterial_10_Polonium_Name;"})
        # another game language: the colour still from the code; a spot from before the code was kept: from the name,
        # when it is an English colour of the species' table, else not filed
        self.db.execute("UPDATE bio_spots SET name='Bakterium Bullaris - Gelb'")
        shot = {"system_id": 9, "body": "Sys 2 a", "lat": 0.0, "lon": 0.0302}
        self.assertEqual(self.st.shot_subject(shot)[1]["colour"], "Yellow")
        self.db.execute("UPDATE bio_spots SET variant=NULL")
        self.assertIsNone(self.st.shot_subject(shot)[1]["colour"])
        self.db.execute("UPDATE bio_spots SET name='Bacterium Bullaris - Yellow'")
        self.assertEqual(self.st.shot_subject(shot)[1]["colour"], "Yellow")
        # the colour tables not loaded yet (a first start offline): every species would look colourless: not filed
        # (review 2026-10-26)
        R = ed_outrider.outrider.bio.load_rules()
        with unittest.mock.patch.object(ed_outrider.outrider.bio, "load_rules", return_value=dict(R, colours=False)):
            self.assertIsNone(self.st.shot_subject(shot)[1]["colour"])
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
        self.assertEqual(self.st.shots_last["clipboard"], "the crop was not made: copied the medium copy")
        self.st.shots_queue.append(dict(self.j.shots_new[0] if self.j.shots_new else {"ts": self.at(32)}, original="Screenshot_0003.bmp",
                                        ts=self.at(32), backlog=True, system="Sys", body="Sys 2 a", system_id=9))
        bmp(os.path.join(self.pictures, "Screenshot_0003.bmp"), 320, 180)
        self.run_queue()
        self.assertEqual(len(copied), 2)   # the backlog's never
        self.assertIsNone(self.st.shots_last["clipboard"])

    def test_review_2_server(self):
        """The in-depth review of 2026-10-25, the server's side of screenshots."""
        # a Screenshot line handled again (a re-read replays the last minutes, a rolled-back tick its line) never
        # converts the shot a second time
        self.st.shots_cfg.update(original="delete")
        self.shoot()
        self.run_queue()
        [good] = [dict(r) for r in self.db.execute("SELECT * FROM screenshots")]
        cp = self.j.checkpoint()
        self.shoot(make=False)
        self.assertEqual(len(self.j.shots_new), 1)
        self.j.restore(cp)
        self.assertEqual(self.j.shots_new, [])                 # the retry's line is noted once, not twice
        self.shoot(make=False)
        self.st.shots_step()
        self.assertEqual(self.st.shots_queue, [])              # converted already: dropped
        self.assertEqual([dict(r) for r in self.db.execute("SELECT * FROM screenshots")], [good])
        # a BMP that cannot be moved: the pictures are recorded, the card says the BMP stayed, the backlog skips it
        self.st.shots_cfg.update(original="move", move_to="")
        self.shoot(name="Screenshot_0005.bmp")
        self.j.shots_new[0]["ts"] = self.at(40)
        self.run_queue()
        r = self.db.execute("SELECT * FROM screenshots WHERE original='Screenshot_0005.bmp'").fetchone()
        self.assertEqual((r["error"], bool(r["full"])), (None, True))
        self.assertIn("no folder", self.st.shots_last["original_error"])
        [card] = [n for n in self.st.notices.active() if n["key"] == "screenshots"]
        self.assertIn("was not moved or deleted", card["text"])
        self.assertTrue(self.st.shot_known(self.at(40), "Screenshot_0005.bmp"))
        # the preview's picture is the latest whole one: a shot with only its crop kept is passed over
        self.db.execute("INSERT INTO screenshots (ts, original, crop) VALUES ('2026-10-25T23:59:00Z', 'x.bmp', '/x/crop/x.jpg')")
        self.assertEqual(self.st.shots_summary()["last_id"], r["id"])
        # a picture Pillow cannot read: no thumbnail (404), never an exception (500)
        bad = os.path.join(self.out, "bad.png")
        with open(bad, "wb") as f:
            f.write(b"\x89PNG not really")
        self.db.execute("UPDATE screenshots SET full=?, medium=NULL, small=NULL WHERE id=?", (bad, r["id"]))
        self.assertIsNone(asyncio.run(self.st.shot_image(r["id"], "thumb")))
        # a Pictures folder that is not there: said, never a raw error
        self.st.shots_cfg.update(pictures=os.path.join(self.d, "nope"))
        self.assertIn("does not exist", self.st.shots_why_off())
        out, status = asyncio.run(self.st.shots_backlog())
        self.assertEqual(status, 409)
        # [screenshots] crop: one cut away at the picture's edge is refused when saved, not stored as ""
        with self.assertRaises(ValueError):
            ed_outrider.CONFIG_CHECKS["screenshots", "crop"]("99.5, 0, 10, 100")
        self.assertEqual(ed_outrider.CONFIG_CHECKS["screenshots", "crop"](""), "")

    def test_review_3_server(self):
        """The third in-depth review of 2026-10-25, the server's side."""
        # an empty BMP is said to be empty, at once, and the backlog leaves it alone
        open(os.path.join(self.pictures, "Screenshot_0009.bmp"), "wb").close()
        with unittest.mock.patch.object(S.wait_ready, "__defaults__", (60, 0.5, lambda s: None, iter(range(0, 1000)).__next__)):
            self.shoot(name="Screenshot_0009.bmp", make=False)
            self.run_queue()
        r = self.db.execute("SELECT error FROM screenshots WHERE original='Screenshot_0009.bmp'").fetchone()
        self.assertIn("is empty", r["error"])
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", []):
            out, status = asyncio.run(self.st.shots_backlog())
        self.assertEqual((out["empty"], out["queued"]), (1, 0))
        # a shot from the start-up catch-up is converted, never put on the clipboard
        copied = []
        self.st.clipboard = type("C", (), {"copy_image": lambda s, png, dib=None: (copied.append(1), (True, None))[1]})()
        self.st.shots_cfg.update(clipboard="medium")
        self.j.importing = True
        self.shoot(name="Screenshot_0010.bmp")
        self.j.importing = False
        self.run_queue()
        self.assertEqual((copied, self.st.shots_last["clipboard"]), ([], None))
        # an id sqlite cannot take: refused (400), never an exception (500)
        with self.assertRaises(ValueError):
            self.st.shots_list("1" * 30)
        # ~ in a typed folder is the home folder, as in every other folder setting
        num = lambda sec, table, key, conv, default: ed_outrider._config_value(sec, key, table.get(key), conv, default)   # noqa: E731
        flag = lambda sec, table, key, default: ed_outrider._config_value(sec, key, table.get(key), ed_outrider._config_bool, default)   # noqa: E731
        st = ed_outrider.screenshots_settings({"pictures": "~/pics", "folder": "~/out", "move_to": "~/kept"}, num, flag)
        self.assertEqual([st[k] for k in ("pictures", "folder", "move_to")],
                         [os.path.expanduser(f"~/{k}") for k in ("pics", "out", "kept")])
        # a crop past the picture's edge is refused when saved, not trimmed into numbers never typed
        for bad in ("10, 10, 95, 75", "-5, 0, 50, 50", "1, 2, 3"):
            with self.assertRaises(ValueError):
                ed_outrider.CONFIG_CHECKS["screenshots", "crop"](bad)
        self.assertEqual(ed_outrider.CONFIG_CHECKS["screenshots", "crop"]("10, 10, 90, 90"), "10, 10, 90, 90")

    def test_review_4_server(self):
        """Fourth in-depth review 2026-10-25: a file still growing after the minute is said to be, not "never appeared";
        a drive or "/" as the export folder served nothing (the guard's prefix had a doubled separator)."""
        self.shoot()
        with unittest.mock.patch.object(S, "wait_ready", lambda *a, **k: False):
            self.run_queue()
        r = self.db.execute("SELECT * FROM screenshots").fetchone()
        self.assertIn("still being written", r["error"])
        self.st.shots_cfg.update(folder=os.path.abspath(os.sep))
        self.db.execute("UPDATE screenshots SET full=?, error=NULL WHERE id=?", (os.path.join(self.pictures, "Screenshot_0001.bmp"), r["id"]))
        self.assertIsNotNone(asyncio.run(self.st.shot_image(r["id"], "full")))

    def test_review_3_backlog_counts(self):
        """matched + unmatched add up to queued: a shot done already is not in them (third in-depth review)."""
        jd = os.path.join(self.d, "journals")
        os.makedirs(jd)
        with open(os.path.join(jd, "Journal.2026-10-25T150000.01.log"), "w") as f:
            for n, sec in (("0002", 35), ("0003", 50)):
                f.write('{"timestamp":"2026-10-25T20:33:%sZ", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_%s.bmp", '
                        '"System":"Sys", "Body":"Sys 2 a"}\n' % (sec, n))
        for n, sec in (("0002", 37), ("0003", 52)):
            p = bmp(os.path.join(self.pictures, f"Screenshot_{n}.bmp"))
            t = ed_outrider.ts_seconds(f"2026-10-25T20:33:{sec}Z")
            os.utime(p, (t, t))
        bmp(os.path.join(self.pictures, "Screenshot_0004.bmp"))   # no line: unknown
        self.db.execute("INSERT INTO screenshots (ts, original, full) VALUES ('2026-10-25T20:33:35Z', 'Screenshot_0002.bmp', 'x')")
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [jd]):
            out, _ = asyncio.run(self.st.shots_backlog())
        self.assertEqual((out["queued"], out["matched"], out["unmatched"], out["skipped"]), (2, 1, 1, 1))

    def test_review_2_samples(self):
        """The Analyse sample's spot is kept, and a spot keeps its name after its run is abandoned (review 2026-10-25:
        a shot at the third sample named nothing; one at an abandoned run's spot was named "$Codex_Ent_...")."""
        def run(species, variant, lon0, kinds):
            ev = {"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Species": species, "Variant": species.replace("_Name;", "_Y_Name;"),
                  "Variant_Localised": variant, "SystemAddress": 9, "Body": 6}
            for i, kind in enumerate(kinds):
                t = self.at(5 + i + (0 if "10" in species else 10))
                self.j.status_json = {"live": True, "ts": t, "body": "Sys 2 a", "lat": 0.0, "lon": lon0 + 0.03 * i}
                self.j.handle(dict(ev, event="ScanOrganic", timestamp=t, ScanType=kind))
        run("$Codex_Ent_Bacterial_10_Name;", "Bacterium Bullaris - Yellow", 0.010, ["Log", "Sample", "Analyse"])
        self.assertIn(0.07, [round(r["lon"], 5) for r in self.db.execute("SELECT lon FROM bio_spots")])   # the Analyse's spot
        run("$Codex_Ent_Bacterial_01_Name;", "Bacterium Aurasus - Green", 0.500, ["Log"])
        run("$Codex_Ent_Bacterial_02_Name;", "Bacterium Nebulus - Teal", 0.900, ["Log"])           # abandons Aurasus' run
        self.assertIsNone(self.db.execute("SELECT 1 FROM own_organic WHERE species='$Codex_Ent_Bacterial_01_Name;'").fetchone())
        _, subj = self.st.shot_subject({"system_id": 9, "body": "Sys 2 a", "lat": 0.0, "lon": 0.5001})
        self.assertEqual(subj["name"], "Bacterium Aurasus - Green")
        _, subj = self.st.shot_subject({"system_id": 9, "body": "Sys 2 a", "lat": 0.0, "lon": 0.0701})
        self.assertEqual(subj["name"], "Bacterium Bullaris - Yellow")

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

    def test_the_backlog_skips_the_shot_being_converted(self):
        """Review 2026-10-25: a HighRes shot mid-conversion (out of the queue, not yet recorded) was queued again by the
        backlog button; with original = delete the second run replaced its good record with an error."""
        jd = os.path.join(self.d, "journals")
        os.makedirs(jd)
        with open(os.path.join(jd, "Journal.2026-10-25T150000.01.log"), "w") as f:
            f.write('{"timestamp":"2026-10-25T20:33:35Z", "event":"Screenshot", "Filename":"\\\\ED_Pictures\\\\Screenshot_0002.bmp", '
                    '"System":"Sys", "Body":"Sys 2 a"}\n')
        p = bmp(os.path.join(self.pictures, "Screenshot_0002.bmp"))
        t = ed_outrider.ts_seconds("2026-10-25T20:33:37Z")
        os.utime(p, (t, t))
        self.st.shots_current = {"ts": "2026-10-25T20:33:35Z", "original": "Screenshot_0002.bmp"}
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [jd]):
            out, status = asyncio.run(self.st.shots_backlog())
        self.assertEqual((status, out["queued"], out["skipped"], self.st.shots_queue), (200, 0, 1, []))

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


class Requirements(unittest.TestCase):
    def test_pillow_writes_jpg_xmp(self):
        """Review 2026-10-25: Pillow writes a JPG's XMP from 11 only (10 drops it without a word)."""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")) as f:
            pin = next(ln for ln in f if ln.lower().startswith("pillow"))
        self.assertGreaterEqual(int(pin.split(">=")[1].split(".")[0]), 11)


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
        st = ed_outrider.screenshots_settings({"codex_format": "tiff", "codex_quality": 20}, num, flag)
        self.assertEqual((st["codex"], st["codex_format"], st["codex_quality"], st["codex_show"]), (False, "", 50, False))
        self.assertEqual(ed_outrider.screenshots_settings({"codex_format": "PNG"}, num, flag)["codex_format"], "png")
        st = ed_outrider.screenshots_settings({"jpg_quality": 70, "resized_quality": 60, "crop": "5,5,200,90", "copies_format": "WEBP",
                                               "clipboard": "Medium", "format": "webp"}, num, flag)
        self.assertEqual((st["quality"], st["copies_quality"], st["crop"], st["copies_format"], st["clipboard"], st["format"], st["full"]),
                         (70, 60, "5, 5, 95, 90", "webp", "medium", "webp", True))   # the names before the release still read
        import outrider.config_edit as C
        self.assertTrue(C.homed("screenshots", "folder"))
        self.assertIn(("screenshots", "folder"), ed_outrider.State.LIVE_CONFIG)


if __name__ == "__main__":
    unittest.main()
