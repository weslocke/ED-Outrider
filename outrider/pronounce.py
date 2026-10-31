"""How Piper says the words its English voices get wrong (a review suggestion the author picked, 2026-10-12).

Piper reads text with espeak's English rules, which mangle the Latin of the exobiology names ("Fonticulua",
"Osseus", "Clypeus Lacrimam"). resources/pronounce.json says them in a respelling: syllables joined by "-", the
stressed one in capitals ("fon-TIK-yoo-loo-uh"). Your own data/pronounce.json goes on top (never committed): stations,
carriers, system names, your commander name, or a shipped word said differently. An entry may also be raw Piper
phonemes ("[[fɒntˈɪkjuːluːə]]").

At speaking time each word found (whole words, any case) becomes Piper's raw phonemes: every syllable read by
espeak on its own in the voice's own accent, the stress marks taken off but the capital one's, and an unstressed
"uh" sound reduced to a schwa. The voice lab's "how is it said" box tries a respelling before it is saved:
"{fon-TIK-yoo-loo-uh}" in a line is said the same way. English voices only: another language's voice reads as it did.
"""
import json
import os
import re
import tempfile
import threading
import unicodedata

from . import DATA_DIR, RESOURCES_DIR

SHIPPED = os.path.join(RESOURCES_DIR, "pronounce.json")
OWN = os.path.join(DATA_DIR, "pronounce.json")
RESPELLING = re.compile(r"^[A-Za-z]+(?:-[A-Za-z]+)*$")
RAW = re.compile(r"^\[\[[^\[\]{}]+\]\]$")
WORD = re.compile(r"^[^\W\d_][\w'’-]*$")   # a key: one word (letters first; apostrophes and dashes inside)
VOWELS = set("aeiouyɑɒæɐəɛɜɪʊʌɔɚɝœøɯɤ")
INLINE = re.compile(r"\{([A-Za-z]+(?:-[A-Za-z]+)*)\}")
BLOCK = re.compile(r"(\[\[.*?\]\])")


def valid(word, say):
    """Whether (word, say) is an entry that can be used: one word, and a respelling or raw phonemes."""
    return isinstance(word, str) and bool(WORD.match(word.strip())) and isinstance(say, str) \
        and bool(RESPELLING.match(say.strip()) or RAW.match(say.strip()))


def read(path):
    """{word: say} from one file ({"words": {...}}), bad entries left out; {} when it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    words = doc.get("words") if isinstance(doc, dict) else None
    return {w.strip(): s.strip() for w, s in (words or {}).items() if valid(w, s)} if isinstance(words, dict) else {}


class Table:
    """The shipped words with yours on top, read again when either file changes. entries(): [{word, say, source}]."""

    def __init__(self, shipped=SHIPPED, own=OWN):
        self.shipped, self.own = shipped, own
        self._stamp, self._words, self._pattern, self._lock = None, {}, None, threading.Lock()

    def _mtime(self, p):
        try:
            return os.stat(p).st_mtime_ns
        except OSError:
            return None

    def words(self):
        """{lower-case word: say}, yours winning."""
        stamp = (self._mtime(self.shipped), self._mtime(self.own))
        with self._lock:
            if stamp != self._stamp:
                merged = {w.lower(): s for w, s in read(self.shipped).items()}
                merged.update({w.lower(): s for w, s in read(self.own).items()})
                self._stamp, self._words = stamp, merged
                self._pattern = re.compile(r"(?<![\w'’-])(" + "|".join(re.escape(w) for w in sorted(merged, key=len, reverse=True))
                                           + r")(?![\w'’-])([,.;:!?](?=\s|$))?", re.IGNORECASE) if merged else None
            return self._words

    def stamp(self):
        """The files' version (changes when either is written)."""
        self.words()
        return self._stamp

    def pattern(self):
        self.words()
        return self._pattern

    def entries(self):
        shipped, own = read(self.shipped), read(self.own)
        out = {w.lower(): {"word": w, "say": s, "source": "shipped"} for w, s in shipped.items()}
        for w, s in own.items():
            out[w.lower()] = {"word": w, "say": s, "source": "yours", "shipped": shipped.get(w) or next(
                (v for k, v in shipped.items() if k.lower() == w.lower()), None)}
        return sorted(out.values(), key=lambda e: e["word"].lower())

    def save(self, word, say):
        """Your file with `word` said as `say` (None: yours removed, the shipped one, if any, applies again). False for
        an entry that cannot be used. Written to a temporary file moved into place."""
        word = (word or "").strip() if isinstance(word, str) else ""
        if say is not None and not valid(word, say):
            return False
        if not WORD.match(word):
            return False
        mine = read(self.own)
        for k in [k for k in mine if k.lower() == word.lower()]:
            del mine[k]
        if say is not None:
            mine[word] = say.strip()
        os.makedirs(os.path.dirname(self.own) or ".", exist_ok=True)
        doc = {"about": "Your own pronunciations for Outrider's Piper voice (the voice lab's How is it said box): "
                        "syllables joined by '-', the stressed one in capitals, or raw phonemes in [[ ]].",
               "words": dict(sorted(mine.items(), key=lambda kv: kv[0].lower()))}
        fd, part = tempfile.mkstemp(dir=os.path.dirname(self.own) or ".", prefix="pronounce.json.", suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
                f.write("\n")
            os.replace(part, self.own)
        except BaseException:
            try:
                os.remove(part)
            except OSError:
                pass
            raise
        return True


_cache, _cache_lock = {}, threading.Lock()


def piper_phonemize(espeak_voice, text):
    """espeak's phonemes for `text` in `espeak_voice`, as Piper reads text (its own phonemizer and lock, so this
    never runs beside a synthesis's)."""
    from piper import voice as pv   # Piper itself: only with a Piper voice in use
    from piper.phonemize_espeak import EspeakPhonemizer
    with pv._ESPEAK_PHONEMIZER_LOCK:
        if pv._ESPEAK_PHONEMIZER is None:
            pv._ESPEAK_PHONEMIZER = EspeakPhonemizer()
        return "".join("".join(s) for s in pv._ESPEAK_PHONEMIZER.phonemize(espeak_voice, text)).strip()


def _stress(ph):
    for i, c in enumerate(ph):
        if unicodedata.normalize("NFD", c)[0] in VOWELS:
            return ph[:i] + "ˈ" + ph[i:]
    return "ˈ" + ph


def to_phonemes(say, espeak_voice, phonemize=piper_phonemize):
    """A respelling's raw phonemes for `espeak_voice` (cached), or a raw entry's own; None when espeak gives nothing."""
    say = say.strip()
    if RAW.match(say):
        return say[2:-2].strip()
    key = (say, espeak_voice)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    parts = say.split("-")
    loud = [p for p in parts if p.isupper()]
    if not loud or len(loud) == len(parts):   # no stress said (or all of it): espeak reads it as one word
        out = phonemize(espeak_voice, "".join(parts).lower()) or None
    else:
        out = ""
        for p in parts:
            ph = _syllable(p, espeak_voice, phonemize)
            if out and ph.lstrip("ˈ")[:1] == out[-1:] and out[-1:] not in VOWELS:   # "ar-ruh": one r, not two
                ph = ph.replace(out[-1], "", 1)
            out += ph
        out = out or None
    with _cache_lock:
        _cache[key] = out
    return out


# a syllable that is only a vowel sound: espeak would read these as a word or as letters ("ay" is "aye")
LONE_VOWELS = {"uh": "ʌ", "eh": "ɛ", "ih": "ɪ", "ay": "eɪ"}


def _syllable(p, espeak_voice, phonemize):
    """One syllable's phonemes: stressed when written in capitals; an unstressed "uh" sound a schwa."""
    low = p.lower()
    if low in LONE_VOWELS:
        ph = LONE_VOWELS[low]
    elif low[-2:] in ("uh", "eh", "ih") and len(low) > 2:   # "tuh", "seh", "dih": read as "tut", "set", "dit", less the t
        ph = re.sub(r"[ˈˌ\s]", "", phonemize(espeak_voice, low[:-1] + "t") or "")
        ph = ph[:-1] if ph.endswith("t") else ph
    else:
        ph = re.sub(r"[ˈˌ\s]", "", phonemize(espeak_voice, low) or "")
    if p.isupper():
        return _stress(ph)
    return ph.replace("ʌ", "ə").replace("ɐ", "ə")


def apply(text, espeak_voice, table, phonemize=piper_phonemize, known=None):
    """`text` with the table's words (and any {respelling}) as Piper's raw phonemes, punctuation right after one moved
    inside its block (Piper drops a comma that starts the text after a block); a procedural sector's words right
    before a system's code (and the voice lab's {{Smojooe}}) read by rule (sector_phonemes): with `known` (the voice's
    phoneme map), a word whose rule needs a sound the voice lacks is left as text (a voice Piper trained another way
    would drop the sound). Raw blocks already there are left as they are. Only for an English voice (espeak "en...");
    anything else gets the text unchanged."""
    if not str(espeak_voice or "").startswith("en"):
        return text
    pat = table.pattern() if table else None
    words = table.words() if table else {}

    def block(say, punct):
        ph = to_phonemes(say, espeak_voice, phonemize)
        return f"[[{ph}{punct or ''}]]" if ph else None

    def one(m):
        return block(words[m.group(1).lower()], m.group(2)) or m.group(0)

    def inline(m):
        return block(m.group(1), "") or m.group(1).replace("-", "")

    def sector(m):   # a sector's words by rule, a word of the table as the table says
        names = m.group(1).split()
        lead = names[0] + " " if len(names) == 2 and names[0].lower() in english_words() else ""
        if lead:
            names = names[1:]
        if not sector_name(" ".join(names)):
            return m.group(0)
        out = []
        for w in names:
            if w.lower() in words:
                ph = to_phonemes(words[w.lower()], espeak_voice, phonemize)
            else:
                ph = sector_phonemes(w, espeak_voice)
                ph = None if ph and known is not None and not set(ph) <= known else ph
            out.append(f"[[{ph}]]" if ph else w)
        return lead + " ".join(out)
    out = []
    for part in BLOCK.split(text):
        if not part.startswith("[["):
            part = SECTOR_IN_TEXT.sub(sector, SECTOR_INLINE.sub(sector, part))
            part = "".join(p if p.startswith("[[") else INLINE.sub(inline, p) for p in BLOCK.split(part))
            parts = BLOCK.split(part)   # the inline ones are blocks now: the table's words only between them
            part = "".join(p if p.startswith("[[") or not pat else pat.sub(one, p) for p in parts)
        out.append(part)
    return "".join(out)


# ---- procedural sector names ("Smojooe", "Flyeia Hypa"; the author's ask, 2026-10-12) ----
# The game builds them from fixed pieces, so they are read by rule, not listed: a word splits into consonant and
# vowel clusters ("sm" "o" "j" "ooe"), the vowel runs into sounds (SECTOR_VOWELS, longest first), the consonants
# between two sounds go one to the syllable before and the rest to the one after ("Wred-guia"; one alone starts the
# next: "Smo-jooe"). A lone vowel is short before a consonant of its own syllable, long at its end ("Smo": smoh), a y
# after a consonant a vowel ("Fly", "Syn"; a last -y after another vowel "ee"); c before e, i, y is s, a first x z. Stress: the first syllable of a word of two, else the second last. The
# phonemes are written here (espeak guesses made-up spellings: "ligh" is "lig"), British or American by the voice.
# A word in the table (shipped or yours) wins; only words right before a system's code ("Smojooe AR-E b25-8", or
# spoken "Smojooe A R E, b 25 8") are read this way, never a hand-named "… Sector" or "… Dark Region".
SECTOR_SOUNDS = {   # sound: (respelling, British, American)
    "a": ("a", "æ", "æ"), "e": ("e", "ɛ", "ɛ"), "i": ("i", "ɪ", "ɪ"), "o": ("o", "ɒ", "ɑː"), "u": ("u", "ʌ", "ʌ"),
    "ah": ("ah", "ɑː", "ɑː"), "eh": ("eh", "ɛ", "ɛ"), "ee": ("ee", "iː", "iː"), "oh": ("oh", "əʊ", "oʊ"),
    "oo": ("oo", "uː", "uː"), "uh": ("uh", "ə", "ə"), "igh": ("igh", "aɪ", "aɪ"), "ay": ("ay", "eɪ", "eɪ"),
    "ow": ("ow", "aʊ", "aʊ"), "oy": ("oy", "ɔɪ", "ɔɪ"), "yoo": ("yoo", "juː", "juː"), "aw": ("aw", "ɔː", "ɔː"),
    "ar": ("ar", "ɑː", "ɑːɹ"), "or": ("or", "ɔː", "ɔːɹ"), "er": ("er", "ɜː", "ɜːɹ"), "yoor": ("yoor", "jʊə", "jʊɹ"),
    "air": ("air", "eə", "ɛɹ"), "ire": ("ire", "aɪə", "aɪɹ"), "our": ("our", "aʊə", "aʊɹ"), "wee": ("wee", "wiː", "wiː")}
SINGLE = {"a": ("a", "ah", "uh"), "e": ("e", "eh", "ee"), "i": ("i", "ee", "ee"), "o": ("o", "oh", "oh"),
          "u": ("u", "oo", "oo"), "y": ("i", "igh", "igh")}   # a lone vowel: (closed, open, at the word's end)
SECTOR_VOWELS = {   # a vowel run: (its sounds in a word, at the word's end)
    "aa": (["ah"], ["ah"]), "ae": (["ay"], ["ay"]), "ai": (["ay"], ["ay"]), "ao": (["ow"], ["ow"]), "au": (["ow"], ["ow"]),
    "ea": (["ee"], ["ee", "uh"]), "ee": (["ee"], ["ee"]), "ei": (["ay"], ["ay"]), "eo": (["ee", "oh"], ["ee", "oh"]),
    "eu": (["yoo"], ["yoo"]), "ia": (["ee", "uh"], ["ee", "uh"]), "ie": (["ee"], ["ee"]), "io": (["ee", "oh"], ["ee", "oh"]),
    "iu": (["ee", "oo"], ["ee", "oo"]), "oa": (["oh"], ["oh", "uh"]), "oe": (["oh"], ["oh"]), "oi": (["oy"], ["oy"]),
    "oo": (["oo"], ["oo"]), "ou": (["ow"], ["ow"]), "ua": (["oo", "uh"], ["oo", "uh"]), "ue": (["oo"], ["oo"]),
    "ui": (["oo", "ee"], ["oo", "ee"]), "aae": (["ah", "ay"], ["ah", "ay"]), "aea": (["ay", "uh"], ["ay", "uh"]),
    "aei": (["ah", "ay"], ["ah", "ay"]), "eae": (["ee", "ay"], ["ee", "ay"]), "eau": (["oh"], ["oh"]),
    "eia": (["ay", "uh"], ["ay", "uh"]), "eou": (["ay", "oo"], ["ay", "oo"]), "iae": (["ee", "ay"], ["ee", "ay"]),
    "oae": (["oh", "ay"], ["oh", "ay"]), "oea": (["oh", "ee", "uh"], ["oh", "ee", "uh"]), "ooe": (["oo"], ["oo"]),
    "uae": (["oo", "ay"], ["oo", "ay"]), "uia": (["wee", "uh"], ["wee", "uh"])}
SECTOR_CONSONANTS = {   # a consonant piece: (respelling, phonemes); doubled letters are one
    "sch": ("sk", "sk"), "tz": ("ts", "ts"), "chr": ("kr", "kɹ"), "tch": ("ch", "tʃ"), "ch": ("ch", "tʃ"), "ph": ("f", "f"), "th": ("th", "θ"),
    "sh": ("sh", "ʃ"), "wr": ("r", "ɹ"), "wh": ("w", "w"), "rh": ("r", "ɹ"), "ck": ("k", "k"), "kh": ("k", "k"),
    "gh": ("g", "ɡ"), "b": ("b", "b"), "c": ("k", "k"), "d": ("d", "d"), "f": ("f", "f"), "g": ("g", "ɡ"), "h": ("h", "h"),
    "j": ("j", "dʒ"), "k": ("k", "k"), "l": ("l", "l"), "m": ("m", "m"), "n": ("n", "n"), "p": ("p", "p"), "q": ("k", "k"),
    "r": ("r", "ɹ"), "s": ("s", "s"), "t": ("t", "t"), "v": ("v", "v"), "w": ("w", "w"), "x": ("ks", "ks"), "y": ("y", "j"),
    "z": ("z", "z")}
R_SOUND = {"a": "ar", "ah": "ar", "o": "or", "oh": "or", "e": "er", "i": "er", "u": "er", "eh": "er", "ee": "er", "oo": "or",
           "yoo": "yoor", "ay": "air", "igh": "ire", "ow": "our"}   # a vowel before r (British: no r said after it)
W_SOUND = {"a": "aw", "ah": "aw", "o": "ow", "oh": "ow", "e": "yoo", "eh": "yoo"}
_SECTOR_WORD = re.compile(r"[A-Za-z]{2,}")
_SECTOR_BEFORE = (r"(?=\s+(?:[A-Z][A-Z]-[A-Z]\s+[a-h]\d|[A-Z]\s[A-Z]\s[A-Z],?\s[a-h]\s\d))")
SECTOR_IN_TEXT = re.compile(r"(?<![\w'’-])([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)" + _SECTOR_BEFORE)
SECTOR_INLINE = re.compile(r"\{\{([A-Za-z]+(?: [A-Za-z]+)?)\}\}")   # the voice lab's "say this as a sector name"
NOT_SECTOR = {"sector", "region", "dark"}
SPEECH = os.path.join(RESOURCES_DIR, "speech.json")
_english = None


def english_words():
    """Every word Outrider's spoken lines use (resources/speech.json), lower case: a capitalised one right before a
    sector ("Leaving Smojooe AR-E b25-8 A 3") is English, not a two-word sector's first word ("Pro Eurl" keeps "Pro" as
    English says it, its second word by rule)."""
    global _english
    if _english is None:
        _english = set()
        # the shipped personality files too (complete review 2026-10-30: Vulcan's "Selecting {system}" read "Selecting"
        # as a sector's first word, said seh-LEK-ting)
        import glob
        for path in [SPEECH] + sorted(glob.glob(os.path.join(os.path.dirname(SPEECH), "personalities", "*.json"))):
            try:
                with open(path, encoding="utf-8") as f:
                    _english |= {w.lower() for w in re.findall(r"[A-Za-z]{2,}", f.read())}
            except OSError:
                pass
    return _english


def _pieces(text, table):
    out, i = [], 0
    longest = max(len(k) for k in table)
    while i < len(text):
        for n in range(min(longest, len(text) - i), 0, -1):
            if text[i:i + n] in table:
                out.append(text[i:i + n])
                i += n
                break
        else:   # a letter no table knows: skipped
            i += 1
    return out


def _runs(word):
    """[(kind, letters)]: "c" consonant runs and "v" vowel runs; a y is a vowel after a consonant, a consonant first
    or between vowels, and a vowel y is a run of its own ("Fly" "eia")."""
    out = []
    for i, ch in enumerate(word):
        if ch == "y":
            before, after = word[i - 1] if i else "", word[i + 1] if i + 1 < len(word) else ""
            kind = "c" if (not before or before in "aeiou") and after in "aeiou" and after else "y"
        else:
            kind = "v" if ch in "aeiou" else "c"
        if out and out[-1][0] == kind and kind != "y":
            out[-1][1] += ch
        else:
            out.append([kind, ch])
    return [("v" if k == "y" else k, s) for k, s in out]


def sector_word(word):
    """A procedural sector word's syllables: [{"onset", "sound", "coda"}] (consonant pieces and a SECTOR_SOUNDS key),
    or None for anything that is not one plain word of letters."""
    if not isinstance(word, str) or not _SECTOR_WORD.fullmatch(word):
        return None
    word = re.sub(r"c(?=[eiy])", "s", re.sub(r"^x", "z", word.lower()))   # English habits: "Cyoa" sigh, "Xee" zee
    runs = _runs(word)
    nuclei, between = [], [[]]   # the sounds, and the consonant pieces before each (and after the last)
    for k, (kind, letters) in enumerate(runs):
        if kind == "c":
            between[-1] += _pieces(re.sub(r"(.)\1", r"\1", letters), SECTOR_CONSONANTS)
            continue
        last = k == len(runs) - 1
        if len(letters) == 1:
            nuclei.append(letters)
            between.append([])
            continue
        for part in _pieces(letters, {**SECTOR_VOWELS, **{v: 0 for v in "aeiouy"}}):
            if part in SECTOR_VOWELS:
                for s in SECTOR_VOWELS[part][1 if last and part == letters[-len(part):] else 0]:
                    nuclei.append(s)
                    between.append([])
            else:
                nuclei.append(part)
                between.append([])
    if not nuclei:
        return None
    syl = [{"onset": [], "sound": n, "coda": []} for n in nuclei]
    syl[0]["onset"] = between[0]
    for i in range(1, len(nuclei)):
        cons = between[i]
        if len(cons) == 1:
            syl[i]["onset"] = cons
        elif cons:
            syl[i - 1]["coda"], syl[i]["onset"] = cons[:1], cons[1:]
    syl[-1]["coda"] = between[-1]
    for i, s in enumerate(syl):
        if s["sound"] in SINGLE:
            closed, open_, end = SINGLE[s["sound"]]
            s["sound"] = closed if s["coda"] else end if i == len(syl) - 1 else open_
            if s["sound"] == "igh" and i == len(syl) - 1 and i and not s["coda"]:   # "Kyloasly": -lee ("Fly" stays)
                s["sound"] = "ee"
        if s["coda"][:1] == ["r"] and s["sound"] in R_SOUND:
            s["sound"], s["coda"] = R_SOUND[s["sound"]], s["coda"][1:]
        elif s["coda"][:1] == ["w"] and s["sound"] in W_SOUND:
            s["sound"], s["coda"] = W_SOUND[s["sound"]], s["coda"][1:]
        elif s["coda"][:1] == ["h"]:   # "Hahm", "Bluehn": the h is not said
            s["coda"] = s["coda"][1:]
    return syl


def sector_stress(syl):
    """The stressed syllable's index: the first of a word of one or two, else the second last."""
    return 0 if len(syl) <= 2 else len(syl) - 2


def sector_respelling(word):
    """"Smojooe" -> "SMOH-joo" (the voice lab shows it), or None."""
    syl = sector_word(word)
    if not syl:
        return None
    loud = sector_stress(syl)
    parts = ["".join(SECTOR_CONSONANTS[c][0] for c in s["onset"]) + SECTOR_SOUNDS[s["sound"]][0]
             + "".join(SECTOR_CONSONANTS[c][0] for c in s["coda"]) for s in syl]
    return "-".join(p.upper() if i == loud else p for i, p in enumerate(parts))


def sector_phonemes(word, espeak_voice):
    """A sector word's raw Piper phonemes (British, or American for an en-us voice), or None."""
    syl = sector_word(word)
    if not syl:
        return None
    us = str(espeak_voice or "").startswith("en-us")
    loud = sector_stress(syl)
    out = ""
    for i, s in enumerate(syl):
        vowel = SECTOR_SOUNDS[s["sound"]][2 if us else 1]
        if i == loud and s["sound"] == "uh":
            vowel = "ʌ"
        if i == loud:   # the mark right before the vowel, after a glide (espeak's "ɡwˈiː", "jˈuːk"; "ɡˈwiː" garbles)
            vowel = re.sub(r"^([jw]?)", r"\1ˈ", vowel, count=1)
        out += "".join(SECTOR_CONSONANTS[c][1] for c in s["onset"]) + vowel \
            + "".join(SECTOR_CONSONANTS[c][1] for c in s["coda"])
    return out


def sector_name(name):
    """Whether a run of one or two words can be a procedural sector's name (not "Hyades Sector", "Musca Dark Region")."""
    words = name.split()
    return 0 < len(words) <= 2 and not any(w.lower() in NOT_SECTOR for w in words) and all(sector_word(w) for w in words)
