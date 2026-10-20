"""Spoken alerts with Piper, a neural text-to-speech engine that runs on the CPU (optional).

Piper is not required: without it the page falls back to the browser's own speech. To use it:

    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install piper-tts

Outrider finds Piper whether it is started with .venv/bin/python or plain python3 (a .venv in the
repository folder is searched when the system Python has no Piper). Voices live in data/piper-voices/; a
configured voice that is missing is downloaded there in the background on first use
(about 63 MB each, from the Piper voices repository on Hugging Face). Installing them beforehand
with `python -m piper.download_voices --download-dir data/piper-voices <voice>` just skips that wait.

"Play speech and sounds on this PC" (a tick on the page) plays the lines and the alert sounds here instead of in
the browser, through the first of pw-play, paplay, aplay or ffplay found (Linux; [speech] server_player picks
one or turns it off). LinePlayer does the playing and render_sound turns static/sounds.json into WAV.
"""
import asyncio
import glob
import hashlib
import http.client
import io
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import threading
import time
import wave
from collections import OrderedDict

from . import DATA_DIR, ROOT
from . import pronounce
from . import tls   # every download verifies with the shared context (issue #9)

VOICES_DIR = os.path.join(DATA_DIR, "piper-voices")
# how the words espeak gets wrong are said (resources/pronounce.json, your data/pronounce.json on top)
PRONOUNCE = pronounce.Table()
DEFAULT_VOICE = "en_GB-cori-medium"   # the author's pick (2026-10-04); Southern English Female before
DEFAULT_FALLBACK = "en_GB-jenny_dioco-medium"
CACHE_PHRASES = 50
# Lines may be spoken in voices besides the main one: a personality's (speech.json's "voice", or one picked in Settings,
# S40) and a crew member's (the crew). Those stay loaded beside the main voice, least recently used dropped first, as
# many as [speech] voices_loaded says (Speaker.voices_loaded: a number, exactly that many; "all"; unset: the voices in
# use, Speaker.size_extra, up to VOICES_LOADED_DEFAULT), so a crew of four does not reload one before every other line.
# The main voice is never among them, so never set aside. They are loaded on first use (or at start with [speech]
# voices_preload) and never downloaded: a voice that is not installed is spoken in the main voice.
VOICES_LOADED_DEFAULT = 4   # also what a [speech] voices_loaded the config cannot read falls back to
# A loaded voice takes about this many times its .onnx file's size in memory (measured on the author's PC, 2026-10-13:
# en_GB-cori-medium's 64 MB file ~100 MB per extra copy, cori-high's 114 MB ~170 MB): voice_memory_estimate
VOICE_MEMORY_FACTOR = 1.6
# A Piper voice name (language_REGION-name-quality). Piper's own pattern also lets '/' and '..' through,
# which would write the download outside piper-voices/.
VOICE_NAME = re.compile(r"^[a-z]{2,3}_[A-Z]{2}-[A-Za-z0-9_]+-(x_low|low|medium|high)$")
FILE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{path}?download=true"
# Piper's list of every voice (the voice lab's More voices), kept beside the voices for a week
CATALOGUE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json?download=true"
CATALOGUE_CACHE = os.path.join(VOICES_DIR, "voices.json")
# Piper's own recording of each voice (its first speaker), on the project's samples site: More voices' ▶ sample
SAMPLE_URL = "https://rhasspy.github.io/piper-samples/samples/{base}/speaker_0.mp3"
CATALOGUE_MAX_AGE = 7 * 86400
# The longest line spoken (about a minute of speech): a cap on the synthesis work one request can ask for.
# A longer line is cut at a sentence or clause boundary, never mid-word (see clip_text).
SAY_MAX = 1000
# Audio players, in the order "auto" tries them: (name, command playing a file (its path is appended), command
# reading a WAV on stdin, or None when it needs a file).
PLAYERS = (("pw-play", ["pw-play"], None),
           ("paplay", ["paplay"], ["paplay"]),
           ("aplay", ["aplay", "-q"], ["aplay", "-q", "-"]),
           ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"]))
PLAYER_CHOICES = ("auto",) + tuple(p[0] for p in PLAYERS) + ("off",)
PLAY_MAX = 20.0   # s: the longest a sound (or a line whose length is unknown) may play on the server before its player is killed
PLAY_SLACK = 5.0  # s: a line may play this much past its own length (player start-up, the feed) before it is killed
SOUNDS_FILE = os.path.join(ROOT, "static", "sounds.json")
SOUND_RATE = 22050


def wav_seconds(wav):
    """How long a WAV plays (frames / rate from its header), or None when it is not a WAV that says."""
    try:
        with wave.open(io.BytesIO(wav)) as w:
            return w.getnframes() / w.getframerate() if w.getframerate() else None
    except (wave.Error, EOFError, TypeError, ValueError):
        return None


def clip_text(text, limit=SAY_MAX):
    """`text` with its whitespace collapsed, and if longer than `limit`, cut back to the last sentence end
    ('. ', '! ', '? '), else the last clause (', ', '; ', ': ', ending the line with '.'), else the last word,
    so the voice never stops mid-word. A boundary in the first half is not used: that would drop too much."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    head = text[:limit + 1]   # one more: a boundary right at the limit counts
    for pattern, keep in ((r"[.!?](?= )", 1), (r"[,;:](?= )", 0)):
        ends = [m.start() for m in re.finditer(pattern, head) if m.start() < limit]
        if ends and ends[-1] >= limit // 2:
            return head[:ends[-1] + keep] + ("" if keep else ".")
    space = head.rfind(" ")
    return head[:space] if space >= limit // 2 else text[:limit]


# How espeak (Piper's reader) says each letter on its own, as Piper's raw phonemes. A body's letters are sent this
# way: read as text, espeak takes "A 1" for the article ("uh one") and runs "ABC 3" into one lightly stressed word
# that the voice slurs ("uh beh ceh"). British and American differ only in O, R and Z.
LETTER_SOUNDS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
    "ˈeɪ", "bˈiː", "sˈiː", "dˈiː", "ˈiː", "ˈɛf", "dʒˈiː", "ˈeɪtʃ", "ˈaɪ", "dʒˈeɪ", "kˈeɪ", "ˈɛl", "ˈɛm", "ˈɛn",
    "ˈəʊ", "pˈiː", "kjˈuː", "ˈɑː", "ˈɛs", "tˈiː", "jˈuː", "vˈiː", "dˈʌbəljˌuː", "ˈɛks", "wˈaɪ", "zˈɛd")))
LETTER_SOUNDS_US = {**LETTER_SOUNDS, "O": "ˈoʊ", "R": "ˈɑːɹ", "Z": "zˈiː"}
# A body's short name in a spoken line: its star letters ("A", "ABC", "ABCD": a planet round four stars' barycentre,
# up to eight) and planet number, then moons ("A 2 a b")
# and a ring ("B 3 A Ring"); a belt ("A Belt Cluster 3", "A A Belt"); or, in a one-star system, a planet's number
# with moons or a ring ("2 a," "3 A Ring"), its moons only at the end of a clause (so "3 a day" stays English).
# Names are left alone: a catalogue number has more digits ("HIP 12345") or a dash ("G 139-21"), and star
# letters run in alphabetical order ("LHS 21" and "UC 3" are not a body's).
# Punctuation right after a name's last letter goes inside its phonemes: Piper drops a comma that starts the text
# after a [[block]] and runs on into the next word ("2 a, up to" said "two ay-up to").
_BODY_NAME = re.compile(r"""
    (?<![\w'’.-])
    (?: (?P<stars>[A-Z]{1,8})\ (?P<num>\d{1,2})(?![.,]\d)
        (?P<moons>(?:\ [a-z](?![\w'’-]))*)
        (?P<ring>\ [A-Z](?=\ (?:Ring|Belt)\b))?
      | (?P<belt>[A-Z]{1,8}(?:\ [A-Z])?)(?=\ Belt\b)
      | (?P<lone>\d{1,2})
        (?=(?:\ [a-z])+(?:$|[,.;:!?)])|\ [A-Z]\ Ring\b)
        (?P<lmoons>(?:\ [a-z])*)
        (?P<lring>\ [A-Z](?=\ Ring\b))? )
    (?![\w'’-])
    (?P<punct>[,.;:!?](?=\s|$))?""", re.VERBOSE)


def body_letters(text, espeak_voice):
    """`text` for Piper with each body name's letters as raw phonemes ([[ˈeɪ bˈiː]]: one stressed word per
    letter), its numbers left as words. Only for an English voice: `espeak_voice` is the voice's espeak language
    (its config's "espeak" voice), and anything else (or None: not known) gets the text unchanged."""
    if not str(espeak_voice or "").startswith("en"):
        return text
    sounds = LETTER_SOUNDS_US if espeak_voice.startswith("en-us") else LETTER_SOUNDS

    def say(letters):
        return "[[" + " ".join(sounds[c.upper()] for c in letters if c.strip()) + "]]"

    def one(m):
        if m["belt"]:
            stars = m["belt"].split(" ")[0]
            return m[0] if list(stars) != sorted(set(stars)) else say(m["belt"])   # followed by " Belt": no punct
        if m["lone"]:
            out = m["lone"]
            moons = m["lmoons"] + (m["lring"] or "")
        else:
            if list(m["stars"]) != sorted(set(m["stars"])):
                return m[0]
            out = f"{say(m['stars'])} {m['num']}"
            moons = m["moons"] + (m["ring"] or "")
        out = f"{out} {say(moons)}" if moons.strip() else out
        punct = m["punct"] or ""
        return out[:-2] + punct + "]]" if punct and out.endswith("]]") else out + punct
    return _BODY_NAME.sub(one, text)


def voice_espeak(voice):
    """A loaded PiperVoice's espeak language ("en-gb-x-rp"), or None when it does not say (a stand-in)."""
    return getattr(getattr(voice, "config", None), "espeak_voice", None)


def installed_voices(voices_dir):
    """Voices in voices_dir that have both files (the model and its .onnx.json config): Piper needs both."""
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(glob.escape(voices_dir), "*.onnx"))
                  if os.path.exists(p + ".json"))


def fetch_catalogue(force=False, cache=None):
    """Piper's voices.json: {voice: {language, quality, num_speakers, files: {path: {size_bytes, md5_digest}}}}.
    Kept in `cache` (data/piper-voices/voices.json) for a week; force: fetched again now."""
    cache = cache or CATALOGUE_CACHE
    if not force and os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CATALOGUE_MAX_AGE:
        try:
            with open(cache, encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, dict):
                return doc
        except (OSError, ValueError):   # a cut-short copy: fetch it again rather than trust it for a week
            pass
    try:
        with tls.urlopen(CATALOGUE_URL, timeout=30) as r:
            data = r.read()
    except http.client.HTTPException as e:   # cut off mid-answer (IncompleteRead) is no OSError: said as one
        raise OSError(f"{type(e).__name__}: {e}") from e
    doc = json.loads(data)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    # a temp file moved into place: an interrupted write never leaves a truncated catalogue behind
    fd, part = tempfile.mkstemp(dir=os.path.dirname(cache), prefix="voices.json.", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(part, 0o644)
        os.replace(part, cache)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return doc


def catalogue_summary(doc, installed=()):
    """The catalogue for the page: [{name, language (en_GB), language_name ("English (Great Britain)"), quality,
    speakers, size_mb (the model), installed, sample (Piper's recording of it)}], by name; entries that are not
    well-formed voices are left out."""
    out, have = [], set(installed)
    for name, v in (doc or {}).items():
        if not isinstance(v, dict) or not VOICE_NAME.fullmatch(name):
            continue
        lang = v.get("language") if isinstance(v.get("language"), dict) else {}
        files = v.get("files") if isinstance(v.get("files"), dict) else {}
        size = sum((m or {}).get("size_bytes") or 0 for p, m in files.items() if p.endswith(".onnx") and isinstance(m, dict))
        out.append({"name": name, "language": lang.get("code") or name.split("-")[0],
                    "language_name": f"{lang.get('name_english') or ''} ({lang.get('country_english') or ''})".replace(" ()", "").strip(),
                    "quality": v.get("quality") or name.rsplit("-", 1)[1],
                    "speakers": v.get("num_speakers") if isinstance(v.get("num_speakers"), int) else 1,
                    "size_mb": round(size / 1e6) if size else None, "installed": name in have,
                    "sample": SAMPLE_URL.format(base=voice_paths(name)[1].rsplit("/", 1)[0])})
    return sorted(out, key=lambda x: x["name"])


def voice_paths(name):
    """A voice's config and model in the Piper voices repository:
    'en_GB-alan-low' -> ['en/en_GB/alan/low/en_GB-alan-low.onnx.json', '.../en_GB-alan-low.onnx']."""
    if not VOICE_NAME.fullmatch(name or ""):
        raise ValueError(f"{name!r} is not a Piper voice name (language_REGION-name-quality)")
    lang, voice, quality = name.split("-")
    base = f"{lang.split('_')[0]}/{lang}/{voice}/{quality}/{name}"
    return [base + ".onnx.json", base + ".onnx"]


PART_STALE_S = 3600   # a .part untouched this long belongs to no download any more


def sweep_parts(voices_dir, now=None):
    """Remove .part files left by downloads that never finished (Outrider stopped mid-way, or the retired voice lab
    closed mid-way). Only ones untouched for PART_STALE_S: another copy of Outrider may be downloading right now.
    Returns how many went."""
    now, n = time.time() if now is None else now, 0
    try:
        names = os.listdir(voices_dir)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(voices_dir, name)
        try:
            if name.endswith(".part") and now - os.path.getmtime(path) > PART_STALE_S:
                os.remove(path)
                n += 1
        except OSError:
            pass
    return n


def download_voice_files(files, voices_dir, progress=None, timeout=60):
    """Download [(repository path, {"size_bytes", "md5_digest"} or {})] into voices_dir. Each file goes to a
    .part first, and they are moved into place only once every one has arrived complete (length and, when
    given, MD5 checked), the model last: an interrupted download never leaves a voice that looks installed,
    or stray .part files. `timeout` is per read, so a stalled connection fails instead of hanging.
    progress(done, total) after each chunk (total is 0 when the sizes are not known)."""
    total, done, parts = sum((m or {}).get("size_bytes") or 0 for _, m in files), 0, []
    os.makedirs(voices_dir, exist_ok=True)
    sweep_parts(voices_dir)
    try:
        for path, meta in sorted(files, key=lambda x: x[0].endswith(".onnx")):   # the small config first
            dest = os.path.join(voices_dir, os.path.basename(path))
            # a .part of its own: two downloads of the same voice at once (two copies of Outrider, or a start-up
            # download while the page picks the same voice) must not write into one file, or one installs a mix and the other finds its file gone
            fd, part = tempfile.mkstemp(dir=voices_dir, prefix=os.path.basename(path) + ".", suffix=".part")
            parts.append((part, dest))
            md5, got = hashlib.md5(), 0
            os.chmod(part, 0o644)   # mkstemp's 0600 would carry over to the installed voice
            with os.fdopen(fd, "wb") as f, tls.urlopen(FILE_URL.format(path=path), timeout=timeout) as r:
                size = r.headers.get("Content-Length") if getattr(r, "headers", None) else None
                while chunk := r.read(1 << 16):
                    f.write(chunk)
                    md5.update(chunk)
                    got += len(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
            name = os.path.basename(path)
            if not got or (size and size.isdigit() and got != int(size)):
                raise IOError(f"{name} did not download completely ({got} bytes); try again")
            if (meta or {}).get("md5_digest") and md5.hexdigest() != meta["md5_digest"]:
                raise IOError(f"{name} did not download correctly (checksum mismatch); try again")
    except BaseException:   # a network error, a full disk, Ctrl-C: nothing half-written stays behind
        for part, _ in parts:
            try:
                os.remove(part)
            except OSError:
                pass
        raise
    for part, dest in sorted(parts, key=lambda x: x[1].endswith(".onnx")):   # config first, model last
        os.replace(part, dest)


def _import_piper():
    """PiperVoice, from this interpreter or from the repository's .venv; None if neither has it."""
    try:
        from piper import PiperVoice
        return PiperVoice
    except ImportError:
        pass
    for venv in _venv_site_packages():
        if os.path.isdir(venv) and venv not in sys.path:
            sys.path.append(venv)
            try:
                from piper import PiperVoice
                return PiperVoice
            except ImportError:
                sys.path.remove(venv)
    return None


def _venv_site_packages(root=None, nt=None):
    """The repository .venv's site-packages for this Python: lib/pythonX.Y/site-packages (Linux, macOS), and on
    Windows Lib/site-packages when the .venv was made by this same Python version (its pyvenv.cfg says)."""
    root, nt = root or ROOT, (os.name == "nt") if nt is None else nt
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    out = [os.path.join(root, ".venv", "lib", f"python{ver}", "site-packages")]
    if nt:
        try:
            with open(os.path.join(root, ".venv", "pyvenv.cfg"), encoding="utf-8") as f:
                same = any(line.split("=", 1)[0].strip() == "version" and line.split("=", 1)[1].strip().startswith(ver + ".")
                           for line in f if "=" in line)
        except OSError:
            same = False
        if same:
            out.append(os.path.join(root, ".venv", "Lib", "site-packages"))
    return out


def loaded_slots(choice, in_use):
    """How many voices besides the main one stay loaded: `choice` as [speech] voices_loaded gives it (a number: exactly
    that many, whatever is in use; "all": None, no limit; None: the `in_use` voices, up to VOICES_LOADED_DEFAULT), never
    under 1 (a voice tried in the voice lab needs a place to load)."""
    if choice == "all":
        return None
    if isinstance(choice, int) and not isinstance(choice, bool) and choice >= 1:
        return choice
    return max(1, min(VOICES_LOADED_DEFAULT, in_use))


def voice_memory_estimate(names, voices_dir=VOICES_DIR):
    """{voice: MB} each of `names` takes in memory once loaded: its installed .onnx file's size times
    VOICE_MEMORY_FACTOR (a rule of thumb, measured; the speakers of one several-person voice share one load). A voice
    that is not installed is left out: it never loads (the main voice speaks for it)."""
    out = {}
    for name in sorted({n for n in names if isinstance(n, str)}):
        if not name or os.path.basename(name) != name or name.startswith("."):
            continue   # a voice's own name only, never a path
        try:
            size = os.path.getsize(os.path.join(voices_dir, name + ".onnx"))
        except OSError:
            continue
        out[name] = round(size * VOICE_MEMORY_FACTOR / 1e6)
    return out


class Speaker:
    """Turns short alert phrases into WAV audio. Loading and downloading happen on a background thread;
    `say()` returns None until a voice is ready, and the page uses browser speech meanwhile."""

    def __init__(self, voice=DEFAULT_VOICE, fallback=DEFAULT_FALLBACK, voices_dir=VOICES_DIR, on_change=None,
                 on_switched=None, speakers=None, on_speaker=None):
        self.on_change = on_change or (lambda: None)   # called (from the thread) when status changes
        # a voice trained on several people speaks as one of them, its "speaker": {voice: speaker id} picked on the
        # page (the voice lab), each voice keeping its own; on_speaker(that dict) remembers it (2026-10-11)
        self.chosen_speakers = {k: v for k, v in (speakers or {}).items()
                                if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
        self.on_speaker = on_speaker or (lambda chosen: None)
        self._speaker_lists = {}   # voice -> (the config's mtime, [{id, name}]): read once per change of its file
        # called (from the thread) with the voice name once a use() switch has it speaking: the place to
        # remember the choice (a choice that never loads must not be tried again at the next start)
        self.on_switched = on_switched or (lambda name: None)
        self.PiperVoice = _import_piper()
        self.SynthesisConfig = None
        if self.PiperVoice:
            from piper import SynthesisConfig   # importable once _import_piper found Piper
            self.SynthesisConfig = SynthesisConfig
        self.preferred, self.fallback, self.dir = voice, fallback, voices_dir
        self.voice_name = None
        self._voice = None
        self._lock = threading.Lock()
        self._cache = OrderedDict()
        self._switch_lock = threading.Lock()
        self._switch_to = None      # the voice use() asked for last
        self.wanted = None          # the voice last asked for by use(): a load of any other is dropped
        self._switching = False     # a use() thread is running: it picks up _switch_to when done
        self._extra = OrderedDict()  # personality voices: name -> (PiperVoice, its own lock), oldest use first
        self._extra_lock = threading.Lock()
        self._extra_bad = set()     # voices that failed to load (not tried again this run)
        self.voices_loaded = None   # [speech] voices_loaded: a number, "all" or None (the voices in use, up to the default)
        self._in_use = 0            # how many voices besides the main one lines may ask for now (size_extra)
        self.fetching = set()       # voices downloading for the voice lab (fetch: not switched to)
        self.fetch_failed = {}      # voice -> why its last fetch failed (the lab says so)
        self.status = "Piper not installed" if not self.PiperVoice else "starting"

    @property
    def available(self):
        return self.PiperVoice is not None

    @property
    def ready(self):
        return self._voice is not None

    def installed(self):
        return installed_voices(self.dir)

    def _set_status(self, text):
        """Change the status and tell the page (the worker thread runs outside the event loop, and a
        waiting long poll only answers when something bumps it)."""
        self.status = text
        self.on_change()

    def info(self):
        sid = self.speaker_for(self.voice_name) if self.voice_name else None
        people = self.voice_speakers(self.voice_name) if self.voice_name else []
        return {"engine": "piper" if self.ready else None, "voice": self.voice_name, "status": self.status,
                "voices": self.installed() if self.available else [], "available": self.available,
                "fetching": sorted(self.fetching), "fetch_failed": dict(self.fetch_failed),
                # the voice's speaker when it has several (the list itself: GET /api/voices/speakers)
                "speaker": sid, "speakers": len(people),
                "speaker_name": next((p["name"] for p in people if p["id"] == sid), None) if sid is not None else None}

    def voice_speakers(self, name):
        """[{id, name}] for an installed voice trained on several people (its .onnx.json's num_speakers and
        speaker_id_map, by id); [] for a one-person voice, one not installed or an unreadable config."""
        path = os.path.join(self.dir, f"{name}.onnx.json") if name else None
        try:
            mtime = os.path.getmtime(path)
        except (OSError, TypeError):
            return []
        hit = self._speaker_lists.get(name)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            cfg = {}
        cfg = cfg if isinstance(cfg, dict) else {}
        ids = cfg.get("speaker_id_map") if isinstance(cfg.get("speaker_id_map"), dict) else {}
        n = cfg.get("num_speakers")
        n = n if isinstance(n, int) and not isinstance(n, bool) else len(ids)
        names = {v: str(k) for k, v in ids.items() if isinstance(v, int) and not isinstance(v, bool)}
        out = [{"id": i, "name": names.get(i, str(i))} for i in range(n)] if n > 1 else []
        self._speaker_lists[name] = (mtime, out)
        return out

    def speaker_for(self, name):
        """The speaker picked for a voice, while it is one of its speakers; None (the voice's first) otherwise."""
        sid = self.chosen_speakers.get(name)
        return sid if sid is not None and sid < len(self.voice_speakers(name)) else None

    def set_speaker(self, name, sid):
        """Pick a voice's speaker (None: its first again). False for a voice that is not installed or has no such
        speaker. Remembered through on_speaker; the cached lines of that voice are dropped."""
        if name not in self.installed():
            return False
        if sid is not None and (isinstance(sid, bool) or not isinstance(sid, int) or not 0 <= sid < len(self.voice_speakers(name))):
            return False
        if sid is None:
            self.chosen_speakers.pop(name, None)
        else:
            self.chosen_speakers[name] = sid
        # only to free memory (each line's key names its speaker, so an old person's clip is never served): skipped
        # while a line is being made, never waited for; this runs on the event loop (review 2026-10-20 M5: the whole
        # server stalled for the rest of the synthesis)
        if self._lock.acquire(blocking=False):
            try:
                self._cache.clear()
            finally:
                self._lock.release()
        self.on_speaker(dict(self.chosen_speakers))
        self.on_change()
        return True

    def start(self):
        if self.available:
            threading.Thread(target=self._prepare, args=(None,), daemon=True, name="piper").start()

    def valid_name(self, name):
        """An installed voice, or a well-formed Piper voice name (so a download stays inside piper-voices/)."""
        return bool(name) and (name in self.installed() or bool(VOICE_NAME.fullmatch(name)))

    def use(self, name):
        """Switch voice (from the alerts dialog): loads, downloading first if it is not installed. One
        switch runs at a time; asking again meanwhile only changes which voice it ends on. False for a
        name that is not a voice."""
        if not (self.available and self.valid_name(name)):
            return False
        with self._switch_lock:
            self._switch_to = self.wanted = name
            if self._switching:
                return True
            self._switching = True
        threading.Thread(target=self._switch_loop, daemon=True, name="piper").start()
        return True

    def fetch(self, name):
        """Download a voice without switching to it (the voice lab's More voices: download, try, then use). True once
        asked (or already there); False without Piper or for a name that is not a Piper voice."""
        if not (self.available and VOICE_NAME.fullmatch(name or "")):
            return False
        if name in self.installed():
            return True
        with self._switch_lock:
            if name in self.fetching:
                return True
            self.fetching.add(name)
        self.fetch_failed.pop(name, None)
        threading.Thread(target=self._fetch_only, args=(name,), daemon=True, name="piper-download").start()
        return True

    def _fetch_only(self, name):
        before, mine = self.status, f"downloading {name} for the voice lab (about 63 MB)"
        try:
            ok = self._download(name, mine)
        except Exception as e:  # noqa: BLE001 -- the lab says it failed, nothing else changes
            ok = False
            print(f"spoken alerts: could not download {name}: {type(e).__name__}: {e}", file=sys.stderr)
        with self._switch_lock:
            self.fetching.discard(name)
        if not ok:
            self.fetch_failed[name] = "the download failed"
        # the status goes back to what it said (the voice in use did not change), unless a switch or another download
        # changed it meanwhile: that one's says what is going on (review 2026-10-12); the page sees the new voice either way
        if self.status == mine:
            self._set_status(before if before.startswith(("ready", "using")) else ("ready" if self.ready else before))
        else:
            self.on_change()

    def _switch_loop(self):
        while True:
            with self._switch_lock:
                name, self._switch_to = self._switch_to, None
                if name is None:
                    self._switching = False
                    return
            if name == self.voice_name:
                self.on_switched(name)   # already speaking: still the choice to remember
                continue
            try:
                self._prepare(name)
            except Exception as e:  # noqa: BLE001 -- keep the loop's flag honest
                print(f"spoken alerts: could not switch to {name}: {type(e).__name__}: {e}", file=sys.stderr)

    def _prepare(self, wanted, remember=True):
        order = [v for v in ([wanted] if wanted else [self.preferred, self.fallback]) if v]
        installed = self.installed()
        # an installed voice first (preferred, then fallback), so speech works at once; only if none of
        # them loads, download the others in the same order
        failed = None   # the last load failure, for the status when nothing works
        for pick in [v for v in order if v in installed] + [v for v in order if v not in installed]:
            if pick not in installed and not self._download(pick):
                continue
            self._set_status(f"loading {pick}")
            try:
                voice = self.PiperVoice.load(os.path.join(self.dir, pick + ".onnx"))
                break
            except Exception as e:   # a damaged file, an onnxruntime problem: try the next voice
                failed = f"could not load {pick}: {type(e).__name__}: {e}"
                print(f"spoken alerts: {failed} (delete {pick}.onnx in {self.dir} to download it again)",
                      file=sys.stderr)
        else:
            if self._voice is not None:   # a switch that failed: the voice already loaded keeps speaking
                self._set_status(f"could not switch to {wanted}"
                                 f" ({failed or 'download failed'}); still using {self.voice_name}")
            else:
                self._set_status(f"{failed} (browser speech is used)" if failed
                                 else "no voice available (download failed; browser speech is used)")
            return
        with self._lock:
            if self.wanted and self.voice_name == self.wanted and pick != self.wanted:
                # the start-up load finished after the voice picked in the dialog was already in use:
                # keep the one asked for (a load that finishes before it is simply replaced by it)
                stale = True
            else:
                stale = False
                self._voice, self.voice_name = voice, pick
                self._cache.clear()
        if not stale:
            print(f"spoken alerts: Piper voice {pick} ready")
        self._set_status("ready")
        if wanted and not stale and remember:
            self.on_switched(pick)
        if not wanted and pick != order[0] and order[0] not in installed and VOICE_NAME.fullmatch(order[0]):
            # the configured (or remembered) voice is not installed: the installed fallback speaks now, and
            # the one asked for is downloaded behind it and takes over once it loads
            threading.Thread(target=self._fetch_preferred, args=(order[0], pick), daemon=True,
                             name="piper-download").start()

    def _fetch_preferred(self, name, speaking):
        """Download the start-up's preferred voice while `speaking` (the fallback) is in use, then switch."""
        if not self._download(name, f"using {speaking}; downloading {name} (about 63 MB), "
                                    "switching to it when it is ready"):
            if self.voice_name == speaking:
                self._set_status(f"using {speaking}; could not download {name}")
            return
        if self.wanted and self.wanted != name:   # another voice was picked in the dialog meanwhile: it wins
            return
        # not remembered as a dialog choice: it is the configured voice (or already the remembered one)
        self._prepare(name, remember=False)

    def _download(self, name, status=None):
        """Download a voice into the voices folder (see download_voice_files); True once it is there."""
        try:
            paths = voice_paths(name)
        except ValueError as e:
            print(f"spoken alerts: {e}", file=sys.stderr)
            return False
        self._set_status(status or f"downloading {name} (about 63 MB)")
        print(f"spoken alerts: downloading Piper voice {name} into {self.dir} (browser speech until it is ready)")
        try:
            download_voice_files([(p, {}) for p in paths], self.dir)
            return True
        except Exception as e:
            print(f"spoken alerts: could not download {name}: {type(e).__name__}: {e}", file=sys.stderr)
            return False

    def slots(self):
        """How many voices besides the main one stay loaded now (None: no limit), from voices_loaded and the voices in use."""
        return loaded_slots(self.voices_loaded, self._in_use)

    def size_extra(self, names):
        """The voices besides the main one that lines may ask for now (`names`: the personalities', the crew's): with
        voices_loaded unset, room for each of them up to VOICES_LOADED_DEFAULT. Sets aside any over the number kept."""
        self._in_use = len({n for n in names if n and n != self.voice_name})
        with self._extra_lock:
            self._trim()

    def _trim(self):
        """Under _extra_lock: the main voice out of the LRU (it is loaded on its own, never counted, never set aside),
        then the least recently used dropped until no more are loaded than slots() says."""
        self._extra.pop(self.voice_name, None)
        cap = self.slots()
        while cap is not None and len(self._extra) > cap:
            self._extra.popitem(last=False)

    def failed(self, name):
        """True for a voice that would not load this run (it is not tried again: the main voice speaks for it)."""
        return name in self._extra_bad

    def extra_voice(self, name):
        """(PiperVoice, lock) for a voice besides the main one (a personality's, a crew member's), loading it now if it
        is installed; None for the main voice, a voice that is not installed (never downloaded from here) or one that
        will not load."""
        if not name or name == self.voice_name or name in self._extra_bad or name not in self.installed():
            return None
        with self._extra_lock:
            if name in self._extra:
                self._extra.move_to_end(name)
                return self._extra[name]
        try:
            voice = self.PiperVoice.load(os.path.join(self.dir, name + ".onnx"))
        except Exception as e:  # noqa: BLE001 -- a damaged file: the main voice speaks those lines instead
            self._extra_bad.add(name)
            print(f"spoken alerts: could not load {name}: {type(e).__name__}: {e}", file=sys.stderr)
            self.on_change()   # the payload says so: a crew member in it is spoken by the XO from now on
            return None
        with self._extra_lock:
            if name not in self._extra:
                self._extra[name] = (voice, threading.Lock())   # the newest: _trim keeps it (slots() is never under 1)
                self._trim()
            return self._extra[name]

    def preload(self, names, wait=600.0):
        """[speech] voices_preload: load the voices in use (`names`) now, up to the number kept, one at a time on a thread
        of their own once the main voice is ready (after the journals are read), so even the first line of each starts
        at once. The thread, or None without Piper."""
        if not self.available:
            return None
        t = threading.Thread(target=self._preload, args=(sorted(set(names)), wait), daemon=True, name="piper-preload")
        t.start()
        return t

    def _preload(self, names, wait=600.0, step=0.5):
        """The voices loaded (see preload), in order; [] when the main voice never became ready within `wait` s."""
        end = time.monotonic() + wait
        while not self.ready and time.monotonic() < end:
            time.sleep(step)
        if not self.ready:
            return []
        self.size_extra(names)
        cap = self.slots()
        todo = [n for n in names if n and n != self.voice_name and n in self.installed() and n not in self._extra_bad]
        done = [n for n in todo[:cap if cap is not None else len(todo)] if self.extra_voice(n)]
        if done:
            print(f"spoken alerts: loaded at start ([speech] voices_preload): {', '.join(done)}")
        return done

    def _synth(self, voice, text, speed, speaker=None):
        """WAV bytes, or None for a line with nothing to pronounce ('...', a lone dash): Piper skips a
        sentence without phonemes, writes no audio and the WAV header is never set (wave.Error). speaker: which of
        a several-person voice's people speaks (None: its first)."""
        buf = io.BytesIO()
        kw = dict({"length_scale": 1.0 / speed} if speed != 1.0 else {}, **({"speaker_id": speaker} if speaker is not None else {}))
        cfg = self.SynthesisConfig(**kw) if kw else None
        try:
            with wave.open(buf, "wb") as wf:
                esv = voice_espeak(voice)
                known = getattr(getattr(voice, "config", None), "phoneme_id_map", None)
                voice.synthesize_wav(pronounce.apply(body_letters(text, esv), esv, PRONOUNCE,
                                                     known=set(known) if isinstance(known, dict) else None), wf, syn_config=cfg)
        except wave.Error:
            return None
        return buf.getvalue() or None

    def _keep(self, key, audio):
        self._cache[key] = audio
        while len(self._cache) > CACHE_PHRASES:
            self._cache.popitem(last=False)

    def say(self, text, speed=1.0, voice=None, speaker=None, keep=True):
        """WAV bytes for `text` at `speed` (1 = the voice's own pace), or None if no voice is ready yet.
        `voice`: a personality's own voice (or one tried in the voice lab), when it is installed (else the main
        voice). `speaker`: one of that voice's people (the lab's try); None: the one picked for it. Recent phrases
        are cached; `keep` False (another player's chat, #17) neither reads nor fills the cache."""
        text = clip_text(text)
        if not text or not self.ready:
            return None
        speed = min(2.0, max(0.5, float(speed or 1.0)))
        extra = self.extra_voice(voice)
        who = voice if extra else self.voice_name
        if speaker is None or isinstance(speaker, bool) or not isinstance(speaker, int) \
                or not 0 <= speaker < len(self.voice_speakers(who)):
            speaker = self.speaker_for(who)
        # the pronunciation table's version too: a word said differently is heard at once, not from the cache
        key = (text, round(speed, 2), voice if extra else None, speaker, PRONOUNCE.stamp())
        with self._lock:
            if keep and key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if not extra:
                audio = self._synth(self._voice, text, speed, speaker)
                if keep:
                    self._keep(key, audio)
                return audio
        with extra[1]:   # its own lock: the main voice keeps speaking meanwhile
            audio = self._synth(extra[0], text, speed, speaker)
        if keep:
            with self._lock:
                self._keep(key, audio)
        return audio


# --------------------------------------------------------------------------
# Playing on the server: the page's "Play speech and sounds on this PC" tick (Linux only).
# --------------------------------------------------------------------------

def find_player(choice="auto", which=None):
    """The PLAYERS entry to use: for "auto" the first one installed, for a player's name that one if it is
    installed; None for "off", an unknown name or nothing found. `which`: shutil.which, or a stand-in (tests)."""
    which = which or shutil.which
    for entry in PLAYERS:
        if choice in ("auto", entry[0]) and which(entry[0]):
            return entry
    return None


class _Line:
    """A spoken line on its way through LinePlayer: stop() may come before its player has even started.
    `capped`: its player was killed at the time limit (a hung player), not stopped by the page."""
    __slots__ = ("id", "stopped", "proc", "capped")

    def __init__(self, line_id):
        self.id, self.stopped, self.proc, self.capped = line_id, False, None, False


class LinePlayer:
    """Plays WAV audio with a local player. One spoken line at a time (claim() refuses a second, so two browsers
    cannot talk over each other); sounds play beside it without waiting, as they do in the browser."""

    def __init__(self, choice="auto", which=None, cap=PLAY_MAX):
        self.choice = choice if choice in PLAYER_CHOICES else "auto"
        self.player = find_player(self.choice, which) if self.choice != "off" else None
        self.cap = cap
        self._line = None          # the _Line playing (or being synthesised) now
        self._stopped = []         # ids a stop named before their line arrived (the page's stop can overtake it)
        self._sounds = set()       # sound tasks still playing (kept, or the loop may drop them half way)

    @property
    def name(self):
        return self.player[0] if self.player else None

    @property
    def busy(self):
        return self._line is not None

    def info(self):
        return {"player": self.name, "choice": self.choice}

    def claim(self, line_id=None):
        """Reserve the voice for a line (before synthesis, so a second request is refused at once); None when
        another line has it."""
        if self._line is not None:
            return None
        self._line = _Line(line_id)
        if line_id is not None and line_id in self._stopped:   # stopped before it got here
            self._line.stopped = True
        return self._line

    def release(self, line):
        if self._line is line:
            self._line = None

    def stop(self, line_id=None):
        """Cut the line short: any line, or only the one with this id (a page stops only its own line)."""
        line = self._line
        if line is None or (line_id is not None and line.id != line_id):
            if line_id is not None:
                self._stopped = (self._stopped + [line_id])[-16:]
            return False
        line.stopped = True
        if line.proc and line.proc.returncode is None:
            try:
                line.proc.terminate()
            except ProcessLookupError:
                pass
        return True

    def line_cap(self, wav):
        """The time limit for a line: its own length plus PLAY_SLACK, never under the cap (a WAV whose length
        is unknown gets the cap), so a long line or a slow voice is heard to its end and only a hung player is cut."""
        length = wav_seconds(wav)
        return self.cap if length is None else max(self.cap, length + PLAY_SLACK)

    async def play_line(self, line, wav):
        """Play a claimed line to its end: "done", "stopped", "capped" (killed at the time limit: it played, but
        not to the end) or "failed" (no player, or it would not play)."""
        if line.stopped:
            return "stopped"
        rc = await self._run(wav, line, self.line_cap(wav))
        return "capped" if line.capped else "stopped" if line.stopped else "done" if rc == 0 else "failed"

    def play_sound(self, wav):
        """Start a sound and return at once (False when there is no player)."""
        if not self.player:
            return False
        task = asyncio.get_running_loop().create_task(self._run(wav))
        self._sounds.add(task)
        task.add_done_callback(self._sounds.discard)
        return True

    async def _run(self, wav, line=None, cap=None):
        """Run the player on `wav`: on stdin where it reads one, else from a temporary file removed afterwards.
        Killed past `cap` s (default the cap). The exit code, or None when it could not start."""
        cap = self.cap if cap is None else cap
        if not self.player:
            return None
        _, file_cmd, stdin_cmd = self.player
        path, proc = None, None
        try:
            if stdin_cmd:
                cmd = stdin_cmd
            else:
                fd, path = tempfile.mkstemp(prefix="outrider-", suffix=".wav")
                with os.fdopen(fd, "wb") as f:
                    f.write(wav)
                cmd = file_cmd + [path]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdin=asyncio.subprocess.PIPE if stdin_cmd else asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            except OSError as e:
                print(f"spoken alerts: could not start {cmd[0]}: {e}", file=sys.stderr)
                return None
            if line is not None:
                line.proc = proc
                if line.stopped:   # stopped while the player started
                    proc.terminate()

            async def feed_and_wait():
                if stdin_cmd:
                    try:
                        proc.stdin.write(wav)
                        await proc.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):   # stopped, or the player gave up
                        pass
                    finally:
                        proc.stdin.close()
                return await proc.wait()
            try:
                return await asyncio.wait_for(feed_and_wait(), cap)
            except asyncio.TimeoutError:
                print(f"spoken alerts: {cmd[0]} still playing after {cap:g} s, stopped", file=sys.stderr)
                if line is not None:   # it did play: a line cut at the cap counts as cut, not as failed
                    line.stopped = line.capped = True   # (a failure would have the browser say the whole line again)
                return None
        finally:
            if proc is not None and proc.returncode is None:   # the cap, or the request went away
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

    async def close(self):
        """At shutdown: stop the line and any sound still playing."""
        self.stop()
        for task in list(self._sounds):
            task.cancel()
        await asyncio.gather(*self._sounds, return_exceptions=True)


def scale_wav(wav, volume):
    """A 16-bit PCM WAV at `volume` (0 to 1, the page's Volume for Outrider's own voice and sounds: review S12),
    for the PC's player, whose own volume flags differ (aplay has none). Anything else, or full volume, unchanged."""
    import array
    try:
        v = float(volume)
    except (TypeError, ValueError):
        return wav
    if not wav or v >= 1 or v != v:
        return wav
    v = max(0.0, v)
    try:
        with wave.open(io.BytesIO(wav)) as r:
            params, frames = r.getparams(), r.readframes(r.getnframes())
    except (wave.Error, EOFError):
        return wav
    if params.sampwidth != 2:
        return wav
    a = array.array("h", frames)
    if sys.byteorder != "little":
        a.byteswap()
    for i, x in enumerate(a):
        a[i] = int(x * v)
    if sys.byteorder != "little":
        a.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        w.writeframes(a.tobytes())
    return out.getvalue()


def load_sounds(path=SOUNDS_FILE):
    """static/sounds.json: {"gain": g, "sounds": {name: {"tones": [...], "lowpass"?: Hz}}}."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict) or not isinstance(doc.get("sounds"), dict):
        raise ValueError(f"{path}: no sounds")
    return doc


def _wave(kind, phase):
    """One oscillator sample at `phase` (cycles), -1 to 1, shaped like WebAudio's (without its band limiting)."""
    x = phase % 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * x)
    if kind == "square":
        return 1.0 if x < 0.5 else -1.0
    if kind == "sawtooth":   # from 0 up to 1, a drop to -1 half way, back up to 0
        return 2 * ((x + 0.5) % 1.0) - 1
    return 1 - 4 * abs((x + 0.25) % 1.0 - 0.5)   # triangle: from 0 up to 1, down to -1, back to 0


def _tone_into(buf, tone, rate):
    """Add one tone to `buf` (a list of floats), with the page's envelope: from 0.0001 up to vol over `attack`,
    then an exponential fade to 0.0001 at `dur`; a glide is an exponential change of pitch over dur."""
    freq, start, dur = float(tone["freq"]), float(tone.get("start", 0)), float(tone["dur"])
    vol, attack = max(float(tone.get("vol", 0.3)), 0.0001), min(float(tone.get("attack", 0.01)), dur)
    kind, glide = tone.get("type", "triangle"), tone.get("glideTo")
    first, n = int(start * rate), int(dur * rate)
    phase, floor = 0.0, 0.0001
    for i in range(n):
        t = i / rate
        if t < attack:
            g = floor * (vol / floor) ** (t / attack)
        else:
            g = vol * (floor / vol) ** ((t - attack) / max(dur - attack, 1e-6))
        f = freq * (float(glide) / freq) ** (t / dur) if glide else freq
        buf[first + i] += g * _wave(kind, phase)
        phase += f / rate


def render_sound(spec, gain=0.8, rate=SOUND_RATE):
    """One sound of sounds.json as 16-bit mono WAV bytes, mixed as the page mixes it: the tones, those not marked
    dry through a one-pole lowpass when the sound has one (the page's biquad is steeper; close enough), times
    `gain`, clipped."""
    tones = spec.get("tones") or []
    length = max((float(t.get("start", 0)) + float(t["dur"]) for t in tones), default=0) + 0.05
    size = int(length * rate) + 1
    wet, dry = [0.0] * size, [0.0] * size
    cut = spec.get("lowpass")
    for t in tones:
        _tone_into(dry if (t.get("dry") or not cut) else wet, t, rate)
    if cut:
        a, y = 1 - math.exp(-2 * math.pi * float(cut) / rate), 0.0
        for i, x in enumerate(wet):
            y += a * (x - y)
            dry[i] += y
    frames = struct.pack(f"<{size}h", *(int(max(-1.0, min(1.0, v * gain)) * 32767) for v in dry))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return buf.getvalue()


SOUND_FILE_MAX_S = 3.0          # s: your own sound file is used up to this long (the voice waits for a sound to end)
SOUND_FILE_MAX_BYTES = 2_000_000


class SoundBank:
    """The alert sounds rendered to WAV on first use, rendered again when sounds.json changes. With `own_dir`
    ([speech] sound_dir: review S16), a <name>.wav there replaces that sound: a name sounds.json has, a WAV (every
    player and browser takes one), at most SOUND_FILE_MAX_S long; anything else is reported, not used."""

    def __init__(self, path=SOUNDS_FILE, own_dir=None):
        self.path, self.own_dir = path, own_dir
        self._stamp, self._doc, self._wavs = None, None, {}
        self._own_key, self._own = None, ({}, [])

    def _load(self):
        stamp = os.path.getmtime(self.path)
        if stamp != self._stamp:
            self._doc, self._wavs, self._stamp = load_sounds(self.path), {}, stamp
        return self._doc

    def names(self):
        return list(self._load()["sounds"])

    def own(self):
        """({name: (path, seconds)}, [problems]) for the sound files in own_dir, looked at again when the folder or
        a file in it changes."""
        d = self.own_dir
        if not d:
            return {}, []
        try:
            files = sorted(f for f in os.listdir(d) if f.lower().endswith(".wav"))
            key = (os.path.getmtime(d), tuple((f, os.path.getmtime(os.path.join(d, f))) for f in files))
        except OSError as e:
            return {}, [f"{d}: {e.strerror or e}"]
        if key == self._own_key:
            return self._own
        names = set(self.names())
        found, problems = {}, []
        for f in files:
            name, path = f[:-4], os.path.join(d, f)
            if name not in names:
                problems.append(f"{f}: not one of the sounds ({', '.join(sorted(names))})")
                continue
            try:
                if os.path.getsize(path) > SOUND_FILE_MAX_BYTES:
                    raise ValueError(f"over {SOUND_FILE_MAX_BYTES // 1_000_000} MB")
                with wave.open(path) as w:
                    secs = w.getnframes() / float(w.getframerate() or 1)
                if secs > SOUND_FILE_MAX_S:
                    raise ValueError(f"{secs:.1f} s long, over {SOUND_FILE_MAX_S:g} s")
            except (OSError, EOFError, wave.Error, ValueError) as e:
                problems.append(f"{f}: not used ({e})")
                continue
            found[name] = (path, round(secs, 2))
        self._own_key, self._own = key, (found, problems)
        return self._own

    def info(self):
        """For the payload: {"own": {name: seconds}, "problems": [...]} (the page fetches and decodes its own copy)."""
        found, problems = self.own()
        return {"own": {n: s for n, (_p, s) in found.items()}, "problems": problems}

    def own_file(self, name):
        """The bytes of your own file for a sound, or None."""
        hit = self.own()[0].get(name)
        if not hit:
            return None
        try:
            with open(hit[0], "rb") as f:
                return f.read()
        except OSError:
            return None

    def wav(self, name):
        """WAV bytes for a sound (your own file when there is one), or None for a name sounds.json does not have
        (call it off the event loop: rendering takes a few tens of milliseconds)."""
        mine = self.own_file(name)
        if mine:
            return mine
        doc = self._load()
        spec = doc["sounds"].get(name)
        if not isinstance(spec, dict):
            return None
        if name not in self._wavs:
            self._wavs[name] = render_sound(spec, float(doc.get("gain", 0.8)))
        return self._wavs[name]
