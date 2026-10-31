"""Unit tests: the pronunciation table (outrider/pronounce.py; a review suggestion the author picked, 2026-10-12): the
respelling's phonemes, whole words only, the files merged with yours on top, bad entries ignored, Piper given the
blocks, the API.

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import json
import os
import tempfile
import types
import unittest

from support import ed_outrider  # noqa: F401  (puts the repository root on sys.path)
import outrider.pronounce as P  # noqa: E402

# a stand-in for espeak: each syllable read as itself, stressed the way espeak marks a word read alone
FAKE = {"fon": "fˈɒn", "tik": "tˈɪk", "yoo": "jˈuː", "loo": "lˈuː", "uh": "ˈʌ", "oss": "ˈɒs", "ee": "ˈiː", "uss": "ˈʌs",
        "tut": "tˈʌt", "set": "sˈɛt", "dit": "dˈɪt", "ar": "ˈɑːɹ", "ruh": "ɹˈʌ", "rut": "ɹˈʌt", "kak": "kˈæk", "toy": "tˈɔɪ"}


def fake(voice, text):
    return FAKE.get(text, text)


def table(d, shipped=None, own=None):
    paths = []
    for name, words in (("shipped.json", shipped), ("own.json", own)):
        p = os.path.join(d, name)
        if words is not None:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"words": words}, f)
        paths.append(p)
    return P.Table(*paths)


class Respelling(unittest.TestCase):
    def setUp(self):
        P._cache.clear()

    def test_phonemes(self):
        """Every syllable read alone, the stress only on the capital one, an unstressed "uh" sound a schwa; "tuh",
        "seh", "dih" as "tut", "set", "dit" less the t; a lone "ay" its own sound; one r where two syllables meet."""
        self.assertEqual(P.to_phonemes("fon-TIK-yoo-loo-uh", "en-gb-x-rp", fake), "fɒntˈɪkjuːluːə")
        self.assertEqual(P.to_phonemes("OSS-ee-uss", "en-gb-x-rp", fake), "ˈɒsiːəs")
        self.assertEqual(P.to_phonemes("kak-TOY-tuh", "en-us", fake), "kæktˈɔɪtə")
        self.assertEqual(P.to_phonemes("set-SEH-dih", "en-us", fake), "sɛtsˈɛdɪ")
        self.assertEqual(P.to_phonemes("AY-ee", "en-us", fake), "ˈeɪiː")
        self.assertEqual(P.to_phonemes("ar-ruh-TOY", "en-us", fake), "ɑːɹətˈɔɪ")
        self.assertEqual(P.to_phonemes("[[ˈɒsiəs]]", "en-us", fake), "ˈɒsiəs")             # raw phonemes as they are
        self.assertEqual(P.to_phonemes("fon-tik", "en-us", lambda v, t: "fˈɒntɪk:" + t), "fˈɒntɪk:fontik")   # no stress said: one word

    def test_apply(self):
        with tempfile.TemporaryDirectory() as d:
            t = table(d, {"Osseus": "OSS-ee-uss", "Fonticulua": "fon-TIK-yoo-loo-uh"})
            say = lambda text, v="en-gb-x-rp": P.apply(text, v, t, fake)
            self.assertEqual(say("Osseus Fonticulua on A 2."), "[[ˈɒsiːəs]] [[fɒntˈɪkjuːluːə]] on A 2.")
            self.assertEqual(say("an osseus, then FONTICULUA."), "an [[ˈɒsiːəs,]] then [[fɒntˈɪkjuːluːə.]]")   # any case; punctuation inside
            self.assertEqual(say("Osseusx and Osseus-like"), "Osseusx and Osseus-like")                      # whole words only
            self.assertEqual(say("[[ˈeɪ]] 2 Osseus"), "[[ˈeɪ]] 2 [[ˈɒsiːəs]]")                              # a block already there kept
            self.assertEqual(say("say {OSS-ee-uss} now"), "say [[ˈɒsiːəs]] now")                           # the lab's try
            self.assertEqual(say("Osseus", "de"), "Osseus")                                                # another language
            self.assertEqual(P.apply("Osseus", "en-us", None, fake), "Osseus")                             # no table

    def test_files_merged_and_bad_entries(self):
        """Yours on top of the shipped words (any case); a bad entry (two words, digits, not a respelling) left out;
        save writes your file and takes an entry back out."""
        with tempfile.TemporaryDirectory() as d:
            t = table(d, {"Osseus": "OSS-ee-uss", "Two words": "TOO", "Tubus": "too bus", "Clypeus": 7, "Cerbrus": "ser{x}"},
                      {"osseus": "[[ˈɒsjəs]]", "Jameson": "JAYM-sun"})
            self.assertEqual(t.words(), {"osseus": "[[ˈɒsjəs]]", "jameson": "JAYM-sun"})
            self.assertEqual([(e["word"], e["source"]) for e in t.entries()], [("Jameson", "yours"), ("osseus", "yours")])
            self.assertEqual(next(e for e in t.entries() if e["word"] == "osseus")["shipped"], "OSS-ee-uss")
            self.assertFalse(t.save("Two words", "TOO"))
            self.assertFalse(t.save("Tubus", "too bus"))
            self.assertTrue(t.save("Tubus", "TOO-buss"))
            self.assertTrue(t.save("OSSEUS", None))   # yours removed: the shipped one again
            self.assertEqual(t.words(), {"osseus": "OSS-ee-uss", "jameson": "JAYM-sun", "tubus": "TOO-buss"})
            with open(os.path.join(d, "own.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["words"], {"Jameson": "JAYM-sun", "Tubus": "TOO-buss"})
            with open(os.path.join(d, "shipped.json"), "w") as f:
                f.write("{not json")
            self.assertEqual(t.words(), {"jameson": "JAYM-sun", "tubus": "TOO-buss"})   # a broken file: nothing from it

    def test_shipped_table(self):
        """Every shipped entry is a usable one-word respelling with one stressed syllable; with Piper here, espeak gives
        each phonemes in both accents, one stress mark each."""
        with open(P.SHIPPED, encoding="utf-8") as f:
            words = json.load(f)["words"]
        self.assertGreaterEqual(len(words), 100)
        for w, s in words.items():
            self.assertTrue(P.valid(w, s), w)
            self.assertEqual(sum(p.isupper() for p in s.split("-")), 1, w)
        import importlib.util
        if importlib.util.find_spec("piper") is None:
            self.skipTest("no Piper")
        for voice in ("en-gb-x-rp", "en-us"):
            for w, s in words.items():
                ph = P.to_phonemes(s, voice)
                self.assertTrue(ph and ph.count("ˈ") == 1 and " " not in ph, (voice, w, ph))


class Sectors(unittest.TestCase):
    """Procedural sector names read by rule (the author's ask, 2026-10-12): every sector seen on EDDN and in the
    author's journals reads, the readings the author heard, where the rule applies and where it does not."""

    def test_every_sector_seen_reads(self):
        """Each of the ~1,600 sectors seen splits into syllables: 1 to 5 a word, one stress mark, only the sounds the
        tables give (no letter dropped as unknown), British and American alike; the Dark Regions are not sectors."""
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "sector_names.txt"), encoding="utf-8") as f:
            names = [n.strip() for n in f if n.strip() and not n.startswith("#")]
        self.assertGreater(len(names), 1500)
        sounds = {c for v in P.SECTOR_SOUNDS.values() for c in v[1] + v[2]} | {c for v in P.SECTOR_CONSONANTS.values() for c in v[1]} | {"ˈ", "ʌ"}
        regions = [n for n in names if not P.sector_name(n)]
        self.assertTrue(regions and all(n.endswith(" Dark Region") for n in regions), regions)
        for n in names:
            if n in regions:
                continue
            for w in n.split():
                syl = P.sector_word(w)
                self.assertTrue(syl and 1 <= len(syl) <= 6, w)
                self.assertTrue(P.RESPELLING.match(P.sector_respelling(w)), w)
                for voice in ("en-gb-x-rp", "en-us"):
                    ph = P.sector_phonemes(w, voice)
                    self.assertEqual(ph.count("ˈ"), 1, (w, ph))
                    self.assertEqual(set(ph) - sounds, set(), (w, ph))

    def test_readings(self):
        """The rule's readings: a lone vowel short in a closed syllable and long at its end, a y after a consonant a
        vowel (a last -y after another vowel "ee"), consonants between two sounds split one before and the rest after,
        c before e/i/y soft, a first x a z, r and w colouring the vowel before them, the stress on the first of two
        syllables and else the second last; British and American phonemes."""
        cases = {"Smojooe": "SMOH-joo", "Flyeia": "fligh-AY-uh", "Hypa": "HIGH-puh", "Synuefe": "sigh-NOO-fee",
                 "Wredguia": "red-GWEE-uh", "Gludgooe": "GLUD-goo", "Phrauq": "FROWK", "Euq": "YOOK", "Eurl": "YOORL",
                 "Phylur": "FIGH-ler", "Outotz": "OW-tots", "Kyloasly": "kigh-LOHS-lee", "Fly": "FLIGH",
                 "Cyoagea": "sigh-oh-GEE-uh", "Xeeheou": "zee-HAY-oo", "Oochorrs": "OO-chors", "Aaeyoea": "ah-ay-yoh-EE-uh"}
        self.assertEqual({w: P.sector_respelling(w) for w in cases}, cases)
        self.assertEqual(P.sector_phonemes("Smojooe", "en-gb-x-rp"), "smˈəʊdʒuː")
        self.assertEqual(P.sector_phonemes("Smojooe", "en-us"), "smˈoʊdʒuː")
        self.assertEqual(P.sector_phonemes("Eurl", "en-gb-x-rp"), "jˈʊəl")      # British: no r after the vowel
        self.assertEqual(P.sector_phonemes("Eurl", "en-us"), "jˈʊɹl")
        # the stress mark after a glide, right before the vowel, as espeak writes it ("ɡˈwiː" came out garbled: the
        # author heard Wredguia as "fedcoyahua")
        self.assertEqual(P.sector_phonemes("Wredguia", "en-gb-x-rp"), "ɹɛdɡwˈiːə")
        self.assertEqual(P.sector_phonemes("Euq", "en-us"), "jˈuːk")
        self.assertEqual(P.sector_phonemes("Hypa", "en-us"), "hˈaɪpə")         # an unstressed "uh" a schwa
        for bad in ("", "A", "Col 285", "Smojooe2", None, "Austr."):
            self.assertIsNone(P.sector_word(bad), bad)
        self.assertFalse(P.sector_name("Hyades Sector"))
        self.assertFalse(P.sector_name("Musca Dark Region"))
        self.assertFalse(P.sector_name("Eol Prou Lio"))   # three words: no procedural sector has them

    def test_apply(self):
        """Only the words right before a system's code (as written or as spoken letter by letter) are read by rule;
        a hand-named sector, an English word leading the name ("Leaving"), a word anywhere else and another language's
        voice are left alone; a word in the table (yours) is said the table's way; the lab's {{name}} reads a name."""
        with tempfile.TemporaryDirectory() as d:
            t = table(d, {"Osseus": "OSS-ee-uss"}, {"Drojau": "DROH-jow"})
            say = lambda text, v="en-gb-x-rp": P.apply(text, v, t, fake)
            self.assertEqual(say("Next: Smojooe A R E, b 25 8."), "Next: [[smˈəʊdʒuː]] A R E, b 25 8.")
            self.assertEqual(say("Nearest: Flyeia Hypa ZC-D c12-2"), "Nearest: [[flaɪˈeɪə]] [[hˈaɪpə]] ZC-D c12-2")
            self.assertEqual(say("Leaving Smojooe A R E, b 25 8 A 3"), "Leaving [[smˈəʊdʒuː]] A R E, b 25 8 A 3")
            self.assertEqual(say("Pro Eurl AB-C d1"), "Pro [[jˈʊəl]] AB-C d1")   # "Pro": English as it is
            # complete review 2026-10-30: a shipped personality's word is English too (Vulcan's "Selecting {system}")
            P._english = None
            self.assertTrue(say("Selecting Smojooe AR-E b25-8 skips the plan.").startswith("Selecting [[smˈəʊdʒuː]]"))
            self.assertEqual(say("Col 285 Sector AB-C d1, Hyades Sector AB-C d1, Musca Dark Region PJ-P b6-1"),
                             "Col 285 Sector AB-C d1, Hyades Sector AB-C d1, Musca Dark Region PJ-P b6-1")
            self.assertEqual(say("Smojooe is far, Hypa too"), "Smojooe is far, Hypa too")      # no code after it: as it was
            self.assertEqual(say("Drojau LL-O b26-3"), say("{DROH-jow}") + " LL-O b26-3")   # yours, not the rule
            self.assertEqual(say("{{Synuefe}} and {{Flyeia Hypa}}"), "[[saɪnˈuːfiː]] and [[flaɪˈeɪə]] [[hˈaɪpə]]")
            self.assertEqual(say("Smojooe A R E, b 25 8", "de"), "Smojooe A R E, b 25 8")
            # a voice whose phoneme map lacks a sound the rule needs: that word as text (Piper would drop the sound)
            known = set("smˈəʊdʒuː ")
            self.assertEqual(P.apply("Smojooe Hypa AB-C d1", "en-gb-x-rp", t, fake, known=known), "[[smˈəʊdʒuː]] Hypa AB-C d1")


class Server(unittest.TestCase):
    def test_piper_gets_the_blocks(self):
        import outrider.tts
        sent = []

        def synth(text, wf, syn_config=None):
            sent.append(text)
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000); wf.writeframes(b"\0\0")
        with tempfile.TemporaryDirectory() as d:
            t = table(d, {"Osseus": "[[ˈɒsiəs]]"})
            keep, outrider.tts.PRONOUNCE = outrider.tts.PRONOUNCE, t
            try:
                sp = outrider.tts.Speaker("en_GB-main-low", None, voices_dir=d)
                sp._voice = types.SimpleNamespace(synthesize_wav=synth, config=types.SimpleNamespace(espeak_voice="en-gb-x-rp"))
                self.assertTrue(sp.say("Osseus on A 2 a, done"))
                t.save("Osseus", "[[ˈɒsjəs]]")
                self.assertTrue(sp.say("Osseus on A 2 a, done"))   # said again, not from the cache
                self.assertTrue(sp.say("Smojooe AR-E b25-8"))       # a sector by rule
                sp._voice.config.phoneme_id_map = {c: [i] for i, c in enumerate("smˈdʒuː")}   # a voice without "əʊ"
                self.assertTrue(sp.say("Smojooe AR-E b25-9"))
            finally:
                outrider.tts.PRONOUNCE = keep
        self.assertEqual(sent[:2], ["[[ˈɒsiəs]] on [[ˈeɪ]] 2 [[ˈeɪ,]] done", "[[ˈɒsjəs]] on [[ˈeɪ]] 2 [[ˈeɪ,]] done"])
        self.assertTrue(sent[2].startswith("[[smˈəʊdʒuː]] "), sent[2])
        self.assertTrue(sent[3].startswith("Smojooe "), sent[3])   # the voice's map lacks a sound: as text

    def test_api(self):
        import asyncio
        from aiohttp.test_utils import TestClient, TestServer
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        for i, (name, n) in enumerate((("Smojooe AR-E b25-8", 3), ("Smojooe ZC-D c12-2", 2), ("Flyeia Hypa ZC-D c12-2", 4),
                                       ("Hyades Sector AB-C d1", 9), ("Sol", 20))):
            db.execute("INSERT INTO visits (id64, name, x, y, z, first_ts, last_ts, count) VALUES (?, ?, 0, 0, 0, '', '', ?)",
                       (i + 1, name, n))
        with tempfile.TemporaryDirectory() as d:
            t = table(d, {"Osseus": "OSS-ee-uss"}, {"Hypa": "HIP-uh"})
            import outrider.tts
            keep, outrider.tts.PRONOUNCE = outrider.tts.PRONOUNCE, t
            try:
                async def go():
                    async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
                        got = await (await c.get("/api/pronounce")).json()
                        out = {"list": got["words"], "sectors": got["sectors"]}
                        r = await c.post("/api/pronounce", json={"word": "Jameson", "say": "JAYM-sun"})
                        out["saved"] = [(e["word"], e["source"]) for e in (await r.json())["words"]]
                        out["bad"] = [(await c.post("/api/pronounce", json=b)).status for b in
                                      ({"word": "two words", "say": "TOO"}, {"word": "Tubus", "say": "too bus"}, {"say": "TOO"}, {"word": "Tubus"})]
                        r = await c.post("/api/pronounce", json={"word": "Jameson", "say": None})
                        out["removed"] = [e["word"] for e in (await r.json())["words"]]
                        return out
                out = asyncio.run(go())
            finally:
                outrider.tts.PRONOUNCE = keep
        self.assertEqual(out["list"][0], {"word": "Hypa", "say": "HIP-uh", "source": "yours", "shipped": None})
        # the sectors you visited most, as the voice says them (yours over the rule); hand-named ones and Sol not
        self.assertEqual(out["sectors"], [{"name": "Smojooe", "visits": 5, "say": "SMOH-joo"},
                                          {"name": "Flyeia Hypa", "visits": 4, "say": "fligh-AY-uh HIP-uh"}])
        self.assertEqual(out["saved"], [("Hypa", "yours"), ("Jameson", "yours"), ("Osseus", "shipped")])
        self.assertEqual(out["bad"], [400, 400, 400, 400])
        self.assertEqual(out["removed"], ["Hypa", "Osseus"])


if __name__ == "__main__":
    unittest.main()
