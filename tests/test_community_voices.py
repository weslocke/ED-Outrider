"""Unit tests: community voices (#25), Piper voices made by others listed in the voice lab's More voices.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import asyncio
import contextlib
import copy
import hashlib
import io
import json
import os
import tempfile
import types
import unittest
import unittest.mock

from support import _FakeResponse  # also puts the repository root on sys.path
import ed_outrider  # noqa: E402
import outrider.tls  # noqa: E402
import outrider.tts  # noqa: E402

GOOD = {"language": {"code": "en_AU", "name_english": "English", "country_english": "Australia"}, "quality": "medium",
        "num_speakers": 10, "repo": "someone/piper-voice", "revision": "a" * 40,
        "model": {"path": "voice.onnx", "size_bytes": 77_000_000, "sha256": "b" * 64},
        "config": {"path": "voice.onnx.json", "size_bytes": 5000, "sha256": "c" * 64},
        "sample": "samples/one.wav", "licence": "CC BY 4.0", "credit": "someone", "about": "Ten speakers."}


def write(d, voices):
    path = os.path.join(d, "community_voices.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"voices": voices}, f)
    return path


class ShippedList(unittest.TestCase):
    def test_every_shipped_voice_is_well_formed(self):
        """Every entry of resources/community_voices.json loads: none is dropped as malformed, each pinned to a commit
        of a Hugging Face repository with a sha256 per file, installed under its own Piper-form name, credited."""
        with open(outrider.tts.COMMUNITY_FILE, encoding="utf-8") as f:
            raw = json.load(f)["voices"]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            got = outrider.tts.load_community()
        self.assertEqual((sorted(got), err.getvalue()), (sorted(raw), ""))
        self.assertGreaterEqual(len(got), 4)
        for name, v in got.items():
            self.assertRegex(name, outrider.tts.VOICE_NAME)
            self.assertEqual([dest["dest"] for _p, dest in v["files"]], [name + ".onnx.json", name + ".onnx"])
            for _p, meta in v["files"]:
                self.assertRegex(meta["url"], r"^https://huggingface\.co/[\w.-]+/[\w.-]+/resolve/[0-9a-f]{40}/")
            self.assertTrue(v["licence"] and v["credit"] and v["about"], name)
            self.assertEqual(v["language"]["code"], name.split("-")[0])
            if v["sample"]:
                self.assertRegex(v["sample"], r"^https://huggingface\.co/[\w.-]+/[\w.-]+/resolve/[0-9a-f]{40}/")


class LoadCommunity(unittest.TestCase):
    def test_bad_entries_are_left_out(self):
        bad = {}
        for i, (where, key, value) in enumerate([
                (None, "repo", "../etc"), (None, "repo", "https://evil.example/x"), (None, "revision", "main"),
                ("model", "sha256", "0" * 63), ("model", "path", "../voice.onnx"), ("model", "path", "voice.bin"),
                ("config", "path", "voice.onnx"), ("model", "size_bytes", 0), (None, "licence", " "), (None, "credit", None)]):
            v = copy.deepcopy(GOOD)
            (v[where] if where else v)[key] = value
            bad[f"en_AU-bad{i}-medium"] = v
        bad["../evil-x-low"] = copy.deepcopy(GOOD)
        bad["en_AU-good-medium"] = copy.deepcopy(GOOD)
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()) as err:
            got = outrider.tts.load_community(write(d, bad))
        self.assertEqual(list(got), ["en_AU-good-medium"])
        self.assertEqual(err.getvalue().count("left out"), 11)
        g = got["en_AU-good-medium"]
        self.assertEqual(g["files"], [
            ("voice.onnx.json", {"url": "https://huggingface.co/someone/piper-voice/resolve/" + "a" * 40 + "/voice.onnx.json",
                                 "dest": "en_AU-good-medium.onnx.json", "size_bytes": 5000, "sha256": "c" * 64}),
            ("voice.onnx", {"url": "https://huggingface.co/someone/piper-voice/resolve/" + "a" * 40 + "/voice.onnx",
                            "dest": "en_AU-good-medium.onnx", "size_bytes": 77_000_000, "sha256": "b" * 64})])
        self.assertEqual((g["sample"], g["source"], g["num_speakers"]),
                         ("https://huggingface.co/someone/piper-voice/resolve/" + "a" * 40 + "/samples/one.wav",
                          "https://huggingface.co/someone/piper-voice", 10))

    def test_missing_file(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(outrider.tts.load_community("/nonexistent/community_voices.json"), {})


class Summary(unittest.TestCase):
    DOC = {"en_GB-cori-medium": {"language": {"code": "en_GB", "name_english": "English", "country_english": "Great Britain"},
                                 "quality": "medium", "num_speakers": 1, "files": {}},
           "en_AU-good-medium": {"language": {"code": "en_AU"}, "quality": "medium", "files": {}}}

    def test_merged_into_the_catalogue(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            com = outrider.tts.load_community(write(d, {"en_AU-good-medium": GOOD, "en_US-other-high": dict(GOOD, sample=None)}))
        got = outrider.tts.catalogue_summary(self.DOC, installed=["en_US-other-high"], community=com)
        self.assertEqual([(v["name"], bool(v.get("community"))) for v in got],
                         [("en_AU-good-medium", True), ("en_GB-cori-medium", False), ("en_US-other-high", True)])
        good = got[0]
        self.assertEqual({k: good[k] for k in ("language", "language_name", "quality", "speakers", "size_mb", "installed",
                                               "licence", "credit", "about", "source")},
                         {"language": "en_AU", "language_name": "English (Australia)", "quality": "medium", "speakers": 10,
                          "size_mb": 77, "installed": False, "licence": "CC BY 4.0", "credit": "someone",
                          "about": "Ten speakers.", "source": "https://huggingface.co/someone/piper-voice"})
        # the sample is the maker's; a voice without one has none (no Piper sample URL made up for it)
        self.assertTrue(good["sample"].endswith("/samples/one.wav"))
        self.assertEqual((got[2]["sample"], got[2]["installed"], got[2]["quality"]), (None, True, "high"))
        # Piper's own list unchanged without community voices
        self.assertEqual([v["name"] for v in outrider.tts.catalogue_summary(self.DOC)], ["en_AU-good-medium", "en_GB-cori-medium"])

    def test_endpoint_lists_them(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            com = outrider.tts.load_community(write(d, {"en_AU-good-medium": GOOD}))
        state.speaker = types.SimpleNamespace(available=True, installed=lambda: [], voice_name="en_GB-cori-medium",
                                              community=lambda: com)

        async def go():
            from aiohttp.test_utils import TestClient, TestServer
            async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                r = await c.get("/api/voices/catalogue")
                return r.status, await r.json()
        with unittest.mock.patch.object(outrider.tts, "fetch_catalogue", lambda force=False: {}):
            status, body = asyncio.run(go())
        self.assertEqual((status, [(v["name"], v["community"], v["licence"]) for v in body["voices"]]),
                         (200, [("en_AU-good-medium", True, "CC BY 4.0")]))


class Download(unittest.TestCase):
    def files(self, model=b"model bytes", config=b"{}", sha_model=None):
        return [("voice.onnx.json", {"url": "https://huggingface.co/x/y/resolve/" + "a" * 40 + "/voice.onnx.json",
                                     "dest": "en_AU-good-medium.onnx.json", "sha256": hashlib.sha256(config).hexdigest()}),
                ("voice.onnx", {"url": "https://huggingface.co/x/y/resolve/" + "a" * 40 + "/voice.onnx",
                                "dest": "en_AU-good-medium.onnx", "sha256": sha_model or hashlib.sha256(model).hexdigest()})]

    def run_dl(self, d, files, bodies):
        urls, it = [], iter(bodies)

        def opener(url, timeout, **k):
            urls.append(url)
            return _FakeResponse(next(it))
        with unittest.mock.patch.object(outrider.tls.urllib.request, "urlopen", opener):
            outrider.tts.download_voice_files(files, d)
        return urls

    def test_pinned_url_installed_under_its_name(self):
        with tempfile.TemporaryDirectory() as d:
            urls = self.run_dl(d, self.files(), [b"{}", b"model bytes"])
            self.assertEqual(urls, ["https://huggingface.co/x/y/resolve/" + "a" * 40 + "/voice.onnx.json",
                                    "https://huggingface.co/x/y/resolve/" + "a" * 40 + "/voice.onnx"])
            self.assertEqual(sorted(os.listdir(d)), ["en_AU-good-medium.onnx", "en_AU-good-medium.onnx.json"])
            self.assertEqual(outrider.tts.installed_voices(d), ["en_AU-good-medium"])

    def test_sha256_mismatch_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(IOError, "checksum mismatch"):
                self.run_dl(d, self.files(sha_model="0" * 64), [b"{}", b"model bytes"])
            self.assertEqual(os.listdir(d), [])

    def test_dest_must_be_a_plain_name(self):
        files = self.files()
        files[1][1]["dest"] = "../en_AU-good-medium.onnx"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                self.run_dl(d, files, [b"{}", b"model bytes"])
            self.assertEqual(os.listdir(d), [])


class SpeakerDownload(unittest.TestCase):
    def test_community_name_uses_its_own_files(self):
        """Speaker._download (the lab's Download, a switch, the start-up's configured voice) fetches a community voice
        from its pinned files and any other from Piper's repository."""
        with tempfile.TemporaryDirectory() as d:
            sp = outrider.tts.Speaker("en_GB-a-low", None, voices_dir=d)
            with contextlib.redirect_stderr(io.StringIO()):
                sp.community_file = write(d, {"en_AU-good-medium": GOOD})
            seen = []
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()), \
                    unittest.mock.patch.object(outrider.tts, "download_voice_files", lambda files, dd: seen.append(files)):
                self.assertTrue(sp._download("en_AU-good-medium"))
                self.assertTrue(sp._download("en_GB-alan-low"))
            self.assertEqual([[m.get("dest") for _p, m in f] for f in seen],
                             [["en_AU-good-medium.onnx.json", "en_AU-good-medium.onnx"], [None, None]])
            self.assertEqual([p for p, _m in seen[1]], outrider.tts.voice_paths("en_GB-alan-low"))
            self.assertIn("from https://huggingface.co/someone/piper-voice", out.getvalue())


if __name__ == "__main__":
    unittest.main()
