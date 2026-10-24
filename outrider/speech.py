"""The words for spoken alerts: speech.json, several versions of every line in each personality.

The file maps each alert to lists of lines per personality ("business", "sarcastic", "sweet", or any you
add under "styles"). A list named "<style>_profane" holds that style's swearing versions. The page picks a
line at random from every personality you ticked, not one of the last few heard; with the profanity box
ticked it first rolls whether this line comes from the swearing versions (the percentage beside the box,
50% by default) or the clean ones. It fills in the {placeholders}: each alert's own (see KEYS) plus {name}
(one of the names in "Call me", picked afresh for every {name}), {cmdr}, {ship} and {here}, and the crew's
({engineer} and the like: CREW_WORDS), which name another crew member and are said only while the crew is on. Numbers
are spoken to a tenth at most ("52.0M" is "52 million"). If the file is missing or broken it falls back to
plain wording.

The file is re-read whenever it changes, so an edit takes effect without restarting Outrider.

More personalities come as files of their own, one each, in the same format (a small speech.json holding one
personality: its "styles" entry and its lists under each alert, no "when" notes): resources/personalities/ for the
shipped ones, and personalities/ beside the bans (data/personalities/ for the shipped speech.json) for your own, which
an update never touches. They are merged into the lines here (merge_personalities): one of your own with a shipped
one's name replaces it; none can replace a base personality. A personality's "names" ({"label", "names": ["Captain",
"Sir"]}) are how it calls you: its {name}, else one of yours from "Call me".

Lines you never want to hear again go in data/speech_banned.json, or next to a speech file of your own
({alert: [line, ...]}, written by the 👎 in the page's "Spoken lines" list and the voice lab's "✂ Cut this line").
They are left out here, so the page (and its voice lab) gets the trimmed lists; a ban never empties a list (the last line of one cannot be banned, and a
list whose every line is banned by hand is used whole), nor leaves it only lines that name a crew member (said only
while the crew is on): its last plain line cannot be banned either.
"""
import hashlib
import json
import os
import re

from . import DATA_DIR, RESOURCES_DIR
from . import chatter as _chatter

# every line the page speaks, and the {placeholders} it fills for it. Always available: {name} (one of the
# names you asked to be called, at random: game commander names are often unpronounceable), {cmdr} (the
# commander name itself), {ship} and {here}.
KEYS = {
    "speech_on": "spoken alerts were just switched on",
    "game_start": "you loaded into the game",
    "game_exit": "you quit the game",
    "arrival_undiscovered": "you jumped into a system nobody has discovered: {system}",
    "arrival_discovered": "a system announced as new turned out to be known: {system}",
    "leaving": "jumping away with work left behind: {text} (what is left)",
    "find_body": "a valuable or special planet was scanned: {what} (its class and flags), {body}, {value}",
    "mapped_before": "a valuable planet was scanned that someone else had already mapped (said once per system, "
                     "instead of the scan's alert)",
    "find_bio": "a body with biology worth your threshold: {body}, {value}",
    "sample_clear": "far enough from the last sample to take the next: {genus}",
    "bio_tag_near": "within 100 m of a plant you tagged with the composition scanner where the next sample of the "
                    "species you are sampling would count: {genus}, {distance} (metres)",
    "codex": "a new codex entry: {entry} (the entry's name), {what} (voucher or new to the region)",
    "docking_granted": "docking granted, said every time: {pad} (the landing pad's number), {station} (the station or carrier)",
    "docking_denied": "docking denied for a reason that is not obvious (no pad free, ship too big, access restricted, "
                      "hostile, your offences, a fighter out; never for distance): {reason} (the reason in words), "
                      "{station} (the station or carrier)",
    "phenomena": "the FSS found notable stellar phenomena in a system where you have none on record (said with delight, in "
                 "every style: the co-pilot loves new things): {what} (already phrased, e.g. 'three notable stellar "
                 "phenomena, all in rings')",
    "limpets_none": "you just undocked in a mining ship (a refinery, a collector or prospector limpet controller fitted) "
                    "with no limpets in the hold: a reminder to turn back for some (Settings → Mining's reminder, said by "
                    "the Mining Officer)",
    "limpets_low": "limpets running low while you mine in a ring (Settings → Mining's number, once a stint): {count} (how "
                   "many are left, 2 or more)",
    "hold_nearly_full": "the hold will be full in about {minutes} minutes at your mining rate (once a stint; {minutes} 2 to 5): "
                        "{free} (tonnes still free)",
    "hold_full": "the hold is full while mining: time to go and sell (the page may add the best price nearby after it)",
    "prospect_hit": "a prospector reported a rock (not mined before) over your threshold of the minerals ticked in Settings → "
                    "Mining (the call-out, said by the Mining Officer; short: they come every few seconds): {what} (already "
                    "phrased, e.g. 'Platinum, 34 percent', 'Combined 52 percent: Platinum 31, Gold 21')",
    "motherlode": "a prospector found a motherlode, a core to crack (Settings → Mining's call-out): {mineral} (e.g. 'Void Opal')",
    "ring_found": "a body just scanned has a ring of a type you watch for (Settings → Mining: the miner's call-out, said "
                  "by the Mining Officer): {body} (short name like 'A 3'), {ring} (the ring, already phrased with its "
                  "article and its reserves when pristine or depleted, e.g. 'a metallic ring', 'a pristine icy ring', "
                  "'metallic and icy rings')",
    "ring_found_many": "several bodies scanned together (a nav beacon, the arrival's own scan) have rings of types you watch "
                       "for: {count} (how many bodies, a number), {bodies} (their short names, already phrased, e.g. "
                       "'A 3, A 5 and B 1'), {types} (the ring types among them, already phrased, e.g. 'metallic and icy')",
    "old_data": "after the arrival briefing, in a system whose Spansh data predates Odyssey (thin-atmosphere worlds marked "
                "not landable, life never reported) and that you have not resolved yourself: worth a rescan (Kurbo26's idea, "
                "discussion #11): {year} (the year it was last reported, e.g. '2019')",
    "rare_star": "a rare star resolved, by the arrival's own scan or the FSS (said with delight, in every style): {what} "
                 "(already phrased, e.g. 'a black hole at B', 'a Wolf-Rayet star, the main star')",
    "surface_site": "surface sites found on a body: Guardian or Thargoid sites (the DSS's map says them) or an unknown "
                    "planetary anomaly (the FSS says it), said with delight in every style: {what} (already phrased, e.g. "
                    "'Guardian sites on B 3')",
    "signal_poi": "the FSS found a signal worth a detour, new to this system: a Titan, a Guardian beacon, a generation ship "
                  "or a listening post (said with delight, in every style): {what} (already phrased, e.g. 'the Titan "
                  "Cocijo', 'a Guardian beacon')",
    "curious": "the system you are in shows curiosities for the first time (rare planet classes, odd orbits, ringed "
               "landables...): one line that there is something to look at on the panels, never the list",
    "ggg": "one of your own scans predicts a green gas giant (the community's seven-layer ladder model: a guess, said "
           "with delight, never a fact): {body} (the body's short name, e.g. 'B 3')",
    "fuel_low": "the game's low fuel warning: {pct}",
    "fuel_star": "arrived under 30% fuel at a star you cannot scoop: {pct}, {star}",
    "fuel_target": "targeted a star you cannot scoop with under 30% fuel: {pct}, {system}",
    "fuel_topup": "at a scoopable star, targeting onward, with the tank lowish and scoopable stars scarce locally: "
                  "{rate} (e.g. '8 of the last 20 stars were scoopable'), {jumps} (jumps of fuel left, e.g. 'about 6 jumps')",
    "fuel_short": "on a Highway route plotted with the exact plotter, the fuel aboard won't reach the next refuel stop (said "
                  "once per system, not at a refuel stop itself): {system} (the refuel stop, or the destination), {jumps} "
                  "(how far, e.g. '4 jumps'), {need} (the fuel to scoop to, e.g. '24 tonnes')",
    "fuel_last_scoop": "at the last scoopable star before stars on your route you can't scoop, which the fuel aboard won't "
                       "cover (any route Outrider follows; said once per stretch, with two or more such stars): {count} (how "
                       "many, a number, e.g. 3)",
    "hull": "hull fell below half or a quarter: {pct}",
    "heat": "heat damage",
    "interdicted": "interdicted: {by}",
    "docked_sell": "docked where you can sell a worthwhile haul: {value}, {station}",
    "undocked_unsold": "undocked with a red-level haul unsold: {value}",
    "sold": "you sold data: {sold} (what was sold), {still} (what is still aboard, may be empty)",
    "unsold_warn": "unsold data reached the amber level: {value}",
    "unsold_urgent": "unsold data reached the red level: {value}",
    "firsts_seen": "the firsts watch found, for the first time, that someone else's scans of a system holding your unsold "
                   "first discoveries reached Spansh (said at most once in 30 minutes; never 'stolen'): {system} (its name), "
                   "{value} (its unsold cartographic value, e.g. '14.2M')",
    "bookmarked": "you asked the voice to bookmark the system you are in (a whole spoken phrase such as 'bookmark this "
                  "system'), and it did: {system} (its name)",
    "upkeep_low": "your fleet carrier's balance, counted down week by week from its last stats (an estimate), now covers "
                  "less than four weeks of upkeep (once per stats reading): {carrier} (its name), {weeks} (the weeks of "
                  "upkeep left, in words, e.g. '3 weeks')",
    "suit_low": "on foot on a planet, your suit's oxygen or health just ran low while unsold data or samples are aboard "
                "that dying would lose (a danger line, once each time it drops low): {what} ('oxygen' or 'health'), {value} "
                "(what a death would lose, in credits, e.g. '412M'), {distance} (how far the ship is, e.g. '640 metres')",
    "upload_held": "an upload went on hold and stays stopped until you act (a card at the top of the page says why; "
                   "Settings -> Uploads has Try again): {service} (EDDN, EDSM or Inara)",
    "carrier_departs": "your carrier leaves in under five minutes without you: {minutes}, {carrier}",
    "carrier_arrived": "your carrier arrived: {carrier}, {system}",
    "autotarget_nothing": "the co-pilot button asked to target the next route system with none to target: {why} (e.g. "
                          "'no route is plotted', 'the route is complete')",
    "wrong_target": "on a route you follow (the Highway, a survey or trade route), the system targeted in game is not its "
                    "next stop (said once per target, not while off the route, nor for a later stop of the route): {system} "
                    "(the system targeted), {next} (the route's next stop)",
    "fss_done": "you finished the FSS, every body is found, and some are worth your time: {count} (how many bodies), "
                "{text} (what is worth doing, e.g. 'B 1, Earth-like world, 3.1M to map, and biology on C 2, up to 19M')",
    "fss_nothing": "you finished the FSS, every body is found, and nothing is worth staying for: {count} (how many bodies)",
    "fss_unfinished": "you closed the FSS with bodies still unresolved: {left} (how many, e.g. '3 bodies')",
    "jumponium": "a landable body just scanned carries the material your FSD injections are short of, when the FSS debrief "
                 "does not say it: {body} (e.g. 'B 4'), {material} (e.g. 'polonium'), {pct} (its share, e.g. '1.3 percent')",
    "left_body": "you left a body (back to supercruise) with exobiology unfinished: {body}, "
                 "{text} (what is unfinished, e.g. 'Stratum 2 of 3, and Tussock untouched, up to 4.1M')",
    "bio_done_more": "the third sample of a species, and more remain on this body: {species}, {value}, "
                     "{left} (what is left here, e.g. 'Bacterium and Fungoida')",
    "bio_done_last": "the third sample of the last species worth sampling on this body: {species}, {value}",
    "tank_full": "fuel scooping filled the tank: {jumps} (max-range jumps a full tank gives; may be missing)",
    "scoop_stopped": "fuel scooping stopped before the tank was full: {pct}",
    "supercharged": "the frame shift drive was supercharged by a neutron star or white dwarf cone: {mult} (e.g. '4 times')",
    "fsd_charge": "the jump line, said in the hyperspace tunnel (the game itself announces the charge): {system} (where you "
                  "are jumping to). Whether the star there is scoopable and any hazard are said after it, outside these lines",
    "body_brief": "approaching a body with biological signals: {body}, "
                  "{text} (what they could be, e.g. '3 biological signals, one of Stratum, Bacterium or Fungoida, 1M to 19M')",
    "high_g": "approaching a landable high-gravity body with a lot of unsold data aboard: {gravity} (in g), "
              "{value} (the unsold total), {rebuys} (how many rebuys that is; may be missing)",
    "arrival_brief": "a briefing on the system you just entered, after the honk: "
                     "{text} (e.g. 'Undiscovered. 14 bodies. Scoopable K star.')",
    "region": "the first jump into a new galactic region this trip, when the arrival briefing is not spoken (it opens "
              "with the region then): {region} (e.g. 'the Norma Arm'), {count} (e.g. '31 species you have logged elsewhere "
              "are new to your codex here'; may be empty, so it ends the line as its own sentence)",
    "session_recap": "you quit the game after a session of at least three jumps, in place of the plain goodbye: "
                     "{text} (e.g. '142 jumps, 3,100 light-years, 12 systems nobody had seen')",
    # the discovery streak: once per streak, when a run reaches its threshold (the page's alerts dialog)
    "streak_known": "several systems in a row were already known to others: {count} (how many in a row)",
    "streak_new": "several undiscovered systems in a row: {count} (how many in a row)",
    "welcome_back": "you loaded into the game after a break of over about two hours, in place of the plain greeting: "
                    "{text} (e.g. 'Away 3 days. 412 million aboard, unsold for 5 days. Fuel 64 percent.')",
    "ship_lost": "your ship was destroyed with data aboard and you paid the rebuy: "
                 "{text} (e.g. 'Lost 212 million: 148 million cartographics, 64 million exobiology, 31 systems.')",
    "sale_left": "a sale's pages stopped with data still unsold (Universal Cartographics sells 50 systems a page), or "
                 "completed samples still unsold after a Vista Genomics sale: {text} (e.g. 'Sold 50 systems for 14.8 million. "
                 "43 systems are still unsold, 2 million, 270 first discoveries: sell the next page.')",
}
# space chatter's lines (outrider/chatter.py, #15): the monologues, a dialogue's asks and answers per topic, the last word
KEYS.update(_chatter.KEYS)
CHATTER_KEYS = tuple(_chatter.KEYS)


def spoken_keys():
    """The alerts a personality is expected to have lines for: every key, the chatter's only once its lines are written
    (outrider.chatter.LINES_WRITTEN), so a personality covering every alert is not shown as incomplete meanwhile."""
    return [k for k in KEYS if _chatter.LINES_WRITTEN or k not in CHATTER_KEYS]


# keys with lines in speech.json that nothing speaks yet (the shipped-lines test allows them); none now
RESERVED = ()
ALWAYS = ("name", "cmdr", "ship", "here")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# a Piper voice name (the same rule as outrider.tts.VOICE_NAME: nothing that could leave piper-voices/)
VOICE_NAME = re.compile(r"^[a-z]{2,3}_[A-Z]{2}-[A-Za-z0-9_]+-(x_low|low|medium|high)$")


def resolve_speech_file(name, root, default, resources=RESOURCES_DIR, warn=None):
    """[server] speech_file, resolved: relative to `root`, ~ expanded; `default` when unset. A relative name missing
    there but present in resources/ (a config written before the layout move, speech_file = "speech.json") is taken
    from resources/, and warn(text) says so (review F22). The server resolves it here, so it and the tests
    always speak from the same file."""
    if not name:
        return default
    raw = os.path.expanduser(str(name))
    path = os.path.join(root, raw)
    moved = os.path.join(resources, raw)
    if not os.path.isabs(raw) and not os.path.exists(path) and os.path.exists(moved):
        if warn:
            warn(f"[server] speech_file = {name!r}: not found in {root}; using {moved} (it moved to resources/). "
                 f"Change the config to say so.")
        return moved
    return path


def style_voice(styles, style):
    """(voice, speed) a personality asks for in "styles" ({"label", "voice", "speed"}), (None, None) for a plain
    label. A personality's voice wins over the one picked in the dialog; its speed multiplies yours."""
    st = (styles or {}).get((style or "").removesuffix("_profane"))
    if not isinstance(st, dict):
        return None, None
    voice = st.get("voice") if isinstance(st.get("voice"), str) and VOICE_NAME.fullmatch(st["voice"]) else None
    speed = st.get("speed") if isinstance(st.get("speed"), (int, float)) and 0.5 <= st.get("speed") <= 2 else None
    return voice, speed


def style_voices(styles):
    """The distinct voices the personalities in "styles" ask for (see style_voice)."""
    return {v for v in (style_voice(styles, k)[0] for k in (styles or {})) if v}


def speaker_number(v):
    """A speaker of a several-person voice (S40): a whole number from 0, never true/false; anything else None."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def style_speaker(styles, style):
    """The person of a several-person voice a personality asks for in "styles" ({"speaker": 12}, S40), or None: of
    its own voice when it names one, else of the main voice. A number the voice does not have is the voice's own pick
    (outrider.tts.Speaker.say checks it). style_voice's (voice, speed) is unchanged."""
    st = (styles or {}).get((style or "").removesuffix("_profane"))
    return speaker_number(st.get("speaker")) if isinstance(st, dict) else None


def style_names(st):
    """A personality's own forms of address ({"names": ["Captain", "Sir"]}): the list, or None when it has none (a
    plain label, no "names") or they are not a list of words."""
    v = st.get("names") if isinstance(st, dict) else None
    names = [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []
    return names if names and len(names) == len(v) else None


def fills(key):
    """The placeholders a line of alert `key` may hold: its own (KEYS), the ones always there and the crew's."""
    return set(PLACEHOLDER.findall(KEYS.get(key, ""))) | set(ALWAYS) | set(CREW_WORDS)


def check(doc):
    """Problems with a speech document, as readable strings (empty when it is fine)."""
    problems = []
    if not isinstance(doc, dict):
        return ["the file must hold one JSON object"]
    styles, lines = doc.get("styles"), doc.get("lines")
    if not isinstance(styles, dict) or not styles:
        problems.append('"styles" must map each personality to its label')
        styles = {}
    for name, st in styles.items():   # a label, or {label, voice, speed, speaker}: a Piper voice of its own (see style_voice)
        if isinstance(st, str):
            continue
        if not isinstance(st, dict):
            problems.append(f'"styles" / "{name}" must be a label or an object {{"label", "voice", "speed", "speaker"}}')
            continue
        if "voice" in st and not (isinstance(st["voice"], str) and VOICE_NAME.fullmatch(st["voice"])):
            problems.append(f'"styles" / "{name}": "voice" must be a Piper voice name such as "en_US-ryan-high"')
        if "speed" in st and not (isinstance(st["speed"], (int, float)) and not isinstance(st["speed"], bool)
                                  and 0.5 <= st["speed"] <= 2):
            problems.append(f'"styles" / "{name}": "speed" must be a number from 0.5 to 2')
        if "speaker" in st and speaker_number(st["speaker"]) is None:
            problems.append(f'"styles" / "{name}": "speaker" must be a whole number from 0 (one person of a several-person voice)')
        if "names" in st and style_names(st) is None:
            problems.append(f'"styles" / "{name}": "names" must be a list of what it calls you, e.g. ["Captain", "Sir"]')
    if not isinstance(lines, dict):
        return problems + ['"lines" must map each alert to its versions']
    known_lists = set(styles) | {s + "_profane" for s in styles}
    unknown = []   # one short line for all of them (they used to repeat every known alert's name each: the author)
    for key, entry in lines.items():
        if key not in KEYS:
            unknown.append(key)
            continue
        if not isinstance(entry, dict):
            problems.append(f'"{key}" must be an object of personality lists')
            continue
        allowed, speakers = fills(key), crew_speakers(key)
        for style, versions in entry.items():
            if style.startswith("_") or style in ("when",):
                continue
            if style not in known_lists:
                problems.append(f'"{key}" has a list "{style}" for a personality not under "styles"')
                continue
            if not isinstance(versions, list) or not all(isinstance(v, str) for v in versions):
                problems.append(f'"{key}" / "{style}" must be a list of strings')
                continue
            for v in versions:
                bad = set(PLACEHOLDER.findall(v)) - allowed
                if bad:
                    problems.append(f'"{key}" / "{style}": {{{"}, {".join(sorted(bad))}}} is not filled for this alert in "{v}"')
                own = [r for r in crew_named(v) if r in speakers]   # a crew member never names itself
                if own:
                    problems.append(f'"{key}" / "{style}": {{{own[0]}}} names the crew member who says this alert in "{v}"')
            if versions and all(crew_named(v) for v in versions):
                problems.append(f'"{key}" / "{style}": every line names a crew member, so with the crew off this alert has '
                                f'none: keep lines without one too')
    if unknown:
        n = len(unknown)
        problems.append(f'{n} line{"s are" if n > 1 else " is"} for {"alerts" if n > 1 else "an alert"} this Outrider does not know '
                        f'yet: {", ".join(unknown)}. Restart Outrider after an update; otherwise check the '
                        f'name{"s" if n > 1 else ""} (the voice lab lists every alert).')
    return problems


BANNED_FILE = "speech_banned.json"   # your own choice of lines: in data/ (git-ignored)


def banned_path(speech_path):
    """Where the bans for a speech file live: data/speech_banned.json for the shipped resources/speech.json,
    and next to the file for a copy of your own (so each lines file keeps its own bans)."""
    folder = os.path.dirname(os.path.abspath(speech_path))
    if os.path.normcase(folder) == os.path.normcase(os.path.abspath(RESOURCES_DIR)):
        folder = DATA_DIR
    return os.path.join(folder, BANNED_FILE)


def read_bans(path):
    """speech_banned.json as {alert: [line, ...]}; {} when it is missing or broken (a broken file bans nothing)."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {k: [t for t in v if isinstance(t, str)] for k, v in doc.items() if isinstance(v, list)}


def shape_ok(doc):
    """Whether a speech document can be used at all: "styles" an object of labels or objects, "lines" an object of
    alert objects whose lists hold strings only. A placeholder or an unknown alert is a problem to report, not a reason
    to refuse it; a list holding an object would break the bans and the page (Codex F7)."""
    if not (isinstance(doc, dict) and isinstance(doc.get("styles"), dict) and isinstance(doc.get("lines"), dict)):
        return False
    if not all(isinstance(v, (str, dict)) for v in doc["styles"].values()):
        return False
    for entry in doc["lines"].values():
        if not isinstance(entry, dict):
            return False
        for style, versions in entry.items():
            if not style.startswith("_") and style != "when" and not (
                    isinstance(versions, list) and all(isinstance(v, str) for v in versions)):
                return False
    return True


def _is_list(style, versions):
    """A personality's list of lines in an alert's entry (not "_comment" or "when")."""
    return isinstance(versions, list) and not style.startswith("_") and style != "when"


def apply_bans(lines, bans):
    """speech.json's "lines" without the banned lines: (lines, whole), `whole` naming each "alert/list" kept whole
    because every line in it is banned (the guard: a ban never empties a list, so an alert never goes quiet)."""
    out, whole = {}, []
    for key, entry in (lines or {}).items():
        cut = set(bans.get(key) or ())
        if not cut or not isinstance(entry, dict):
            out[key] = entry
            continue
        new = {}
        for style, versions in entry.items():
            if _is_list(style, versions):
                kept = [v for v in versions if v not in cut]
                # every line banned, or every plain one (the crew's lines alone would leave the alert nothing with it off)
                if versions and (not kept or (not all(map(crew_named, versions)) and all(map(crew_named, kept)))):
                    whole.append(f"{key}/{style}")
                    kept = versions
                new[style] = kept
            else:
                new[style] = versions
        out[key] = new
    return out, whole


PERSONALITIES = "personalities"   # the folder of personality files, in resources/ (shipped) and beside the bans (yours)


def personality_dirs(speech_path, resources=RESOURCES_DIR):
    """(shipped, yours): resources/personalities/, and personalities/ where the speech file's bans live (data/ for the
    shipped speech.json, beside a speech file of your own: a test or scratch server keeps its own)."""
    return (os.path.join(resources, PERSONALITIES),
            os.path.join(os.path.dirname(banned_path(speech_path)), PERSONALITIES))


def merge_personalities(base, addons):
    """The base speech document with the personality files merged in: (doc, notes, info). `addons`: [(source "shipped"
    or "yours", file name, doc)], the shipped first, each a usable document (shape_ok). A file's personality joins
    "styles" and its lists ("<id>", "<id>_profane") join each alert it has; anything else in it is left out (check()
    reports it). One of your own replaces a shipped one of the same name; a base personality is never replaced, and a
    name already taken in the same folder is not taken again (each said in `notes`). `info`: [{id, file, source,
    covers, of}] per personality merged, `covers` the alerts it has a line for."""
    styles = dict(base.get("styles") or {})
    lines = dict(base.get("lines") or {})
    owner, notes = {}, []
    for source, fname, doc in addons:   # who owns each name: your own after the shipped replaces it
        for sid in doc.get("styles") or {}:
            if sid in styles:
                notes.append(f'{fname}: "{sid}" is one of the base personalities: left out')
            elif sid in owner and owner[sid][0] == source:
                notes.append(f'{fname}: "{sid}" is already in {owner[sid][1]}: left out')
            else:
                owner[sid] = (source, fname)
    info = []
    for source, fname, doc in addons:
        for sid in [k for k, o in owner.items() if o == (source, fname)]:
            styles[sid] = doc["styles"][sid]
            for key, entry in (doc.get("lines") or {}).items():
                got = {k: v for k, v in entry.items() if k in (sid, sid + "_profane")} if isinstance(entry, dict) else {}
                if key not in KEYS or not got:
                    continue
                lines[key] = {**(lines.get(key) if isinstance(lines.get(key), dict) else {}), **got}
            counted = spoken_keys()
            covers = sum(1 for k in counted if isinstance(lines.get(k), dict)
                         and any(lines[k].get(lst) for lst in (sid, sid + "_profane")))
            info.append({"id": sid, "file": fname, "source": source, "covers": covers, "of": len(counted)})
    return dict(base, styles=styles, lines=lines), notes, info


class SpeechLines:
    """speech.json, re-read when its modification time changes. A broken edit keeps the last good copy
    in use and reports what is wrong, so a typo never silences the alerts. Its speech_banned.json (see banned_path) is
    re-read the same way, and its lines are left out of lines(). The personality files in `dirs` (personality_dirs:
    shipped, yours) are merged in (merge_personalities), each re-read on its own the same way; one added or removed
    counts as a change too."""

    def __init__(self, path, dirs=None):
        self.path = path
        self.doc, self.error, self.problems, self._mtime = None, None, [], None
        self.bans_path = banned_path(path)
        self.bans, self._bans_mtime, self._bans_gen = {}, None, 0
        self.dirs = tuple(dirs) if dirs is not None else personality_dirs(path)
        # each personality file: {path: {mtime, doc (its last good copy), error, problems}}; the listing's signature
        self._files, self._files_sig = {}, None
        self.merged, self.notes, self.info_list, self._merged_for = None, [], [], None

    def _refresh_bans(self):
        try:
            mtime = os.stat(self.bans_path).st_mtime_ns
        except OSError:
            mtime = None
        if mtime != self._bans_mtime:
            self._bans_mtime = mtime
            self.bans = read_bans(self.bans_path) if mtime is not None else {}

    def _listing(self):
        """[(source, path, mtime)] of the personality files now: the shipped folder's, then yours, by name."""
        out = []
        for source, folder in zip(("shipped", "yours"), self.dirs):
            try:
                names = sorted(n for n in os.listdir(folder) if n.endswith(".json") and not n.startswith("."))
            except OSError:
                continue
            for n in names:
                path = os.path.join(folder, n)
                try:
                    out.append((source, path, os.stat(path).st_mtime_ns))
                except OSError:
                    continue
        return out

    def _refresh_files(self):
        listing = self._listing()
        sig = tuple(listing)
        if sig == self._files_sig:
            return False
        self._files_sig = sig
        files = {}
        for _source, path, mtime in listing:
            old = self._files.get(path)
            if old and old["mtime"] == mtime:
                files[path] = old
                continue
            f = {"mtime": mtime, "doc": (old or {}).get("doc"), "error": None, "problems": []}
            name = os.path.basename(path)
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, ValueError) as e:
                f["error"] = f"{name} could not be read ({e}); " + \
                    ("its last good copy is still in use" if f["doc"] else "its personality is left out")
            else:
                f["problems"] = [f"{name}: {p}" for p in check(doc)]
                if shape_ok(doc):
                    f["doc"] = doc
                else:
                    f["error"] = f"{name}: not a personality file (\"styles\" and \"lines\" as in speech.json); " + \
                        ("its last good copy is still in use" if f["doc"] else "its personality is left out")
            files[path] = f
        self._files = files
        return True

    def _merge(self):
        """The base document with the personality files merged in, worked out again only when either changed."""
        key = (self._mtime, self._files_sig)
        if self.doc is None:
            self.merged, self.notes, self.info_list = None, [], []
        elif key != self._merged_for:
            addons = [(source, os.path.basename(path), self._files[path]["doc"])
                      for source, path, _m in self._files_sig or () if self._files.get(path, {}).get("doc")]
            self.merged, self.notes, self.info_list = merge_personalities(self.doc, addons)
        self._merged_for = key

    def _doc(self):
        return self.merged or self.doc or {}

    def file_problems(self):
        """The personality files' problems and errors, and the merge's notes, as readable strings."""
        out = []
        for f in self._files.values():
            out += ([f["error"]] if f["error"] else []) + f["problems"]
        return out + self.notes

    def refresh(self):
        self._refresh_bans()
        self._refresh_files()
        self._refresh_base()
        self._merge()

    def _refresh_base(self):
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except OSError:
            self.doc, self.error, self.problems, self._mtime = None, f"{self.path} not found: plain wording is used", [], None
            return
        if mtime == self._mtime:
            return
        self._mtime = mtime
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError) as e:
            self.error = f"{os.path.basename(self.path)} could not be read ({e}); " + \
                ("the last good copy is still in use" if self.doc else "plain wording is used")
            return
        self.problems = check(doc)
        if shape_ok(doc):
            self.doc, self.error = doc, None
        else:   # the last good document stays in use, and the bans keep working on it
            self.error = "; ".join(self.problems or ["the file's shape is not a speech document"]) + \
                ("; the last good copy is still in use" if self.doc else "; plain wording is used")

    def version(self):
        self.refresh()
        # the bans are part of it: a 👎 (or the voice lab's ✂) makes every page fetch the trimmed lines; and the
        # personality files (a hash of their listing: one added, edited or removed, even while Outrider was stopped)
        files = hashlib.sha1(repr(self._files_sig).encode()).hexdigest()[:10]
        return f"{self._mtime}-{self._bans_mtime}-{self._bans_gen}-{files}" if self.doc else None

    def info(self):
        """The payload's small summary: the page fetches the lines themselves when the version changes."""
        self.refresh()
        return {"version": self.version(), "error": self.error, "problems": (self.problems + self.file_problems())[:20],
                "file": os.path.basename(self.path)}

    def banned(self):
        """The bans that still match a line in the speech file, {alert: [line, ...]} (an edited line's old ban does
        nothing, so it is not listed)."""
        lines = self._doc().get("lines") or {}
        out = {}
        for key, cut in self.bans.items():
            entry = lines.get(key)
            have = {v for st, vs in entry.items() if _is_list(st, vs) for v in vs} if isinstance(entry, dict) else set()
            hit = [t for t in cut if t in have]
            if hit:
                out[key] = hit
        return out

    def lines(self):
        self.refresh()
        trimmed, whole = apply_bans(self._doc().get("lines") or {}, self.bans)
        return {"styles": self._doc().get("styles") or {}, "lines": trimmed,
                "banned": self.banned(), "banned_whole": whole,
                "version": self.version(), "error": self.error, "problems": (self.problems + self.file_problems())[:20],
                # the personality files merged in: {id, file, source (shipped or yours), covers, of} each
                "personalities": list(self.info_list),
                "crew_roles": crew_roles_info(),   # the crew's roles and their alert rows, for the page
                "chatter": _chatter.page_info()}   # space chatter's topics, timings and sample values (#15)

    def set_ban(self, alert, template, ban=True):
        """Ban (or unban) one line of an alert: (HTTP status, answer). Only a line that is in the speech file is
        accepted, and a ban that would leave one of its lists empty is refused (409)."""
        self.refresh()
        entry = (self._doc().get("lines") or {}).get(alert)
        if not isinstance(alert, str) or not isinstance(template, str) or not isinstance(entry, dict):
            return 400, {"error": "no such alert in the speech file"}
        homes = [vs for st, vs in entry.items() if _is_list(st, vs) and template in vs]
        if not homes:
            return 400, {"error": "that line is not in the speech file"}
        cut = list(self.bans.get(alert) or [])
        if ban and template not in cut:
            for vs in homes:
                if all(v == template or v in cut for v in vs):
                    return 409, {"error": "that is the last line left in its list: an alert never goes quiet"}
                if not crew_named(template) and all(v == template or v in cut for v in vs if not crew_named(v)):
                    return 409, {"error": "that is the last line in its list that names no crew member: with the crew off "
                                          "the alert would have nothing to say"}
            cut.append(template)
        elif not ban:
            cut = [t for t in cut if t != template]
        bans = dict(self.bans)
        if cut:
            bans[alert] = cut
        else:
            bans.pop(alert, None)
        tmp = self.bans_path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.bans_path), exist_ok=True)   # data/ on a fresh copy
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(bans, f, indent=1, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, self.bans_path)
        except OSError as e:
            return 500, {"error": f"{BANNED_FILE} could not be written ({e.strerror or e})"}
        self.bans, self._bans_gen = bans, self._bans_gen + 1
        try:
            self._bans_mtime = os.stat(self.bans_path).st_mtime_ns
        except OSError:
            pass
        return 200, {"ok": True, "banned": sum(len(v) for v in self.banned().values())}


def ban_line(speech_path, alert, template, ban=True):
    """set_ban on the speech file at `speech_path` (a script's or a test's way to cut a line)."""
    return SpeechLines(speech_path).set_ban(alert, template, ban)


# ---- filling and tidying lines outside the page (a Python mirror of page.js's, kept in step by the tests) ----

# made-up values for trying lines out, already phrased the way the page phrases them
SAMPLES = {
    "arrival_undiscovered": {"system": "Drojau LL-O b26-3"}, "arrival_discovered": {"system": "Drojau LL-O b26-3"},
    "leaving": {"text": "A 2, a class two gas giant, plus 1.4M to map"},
    "find_body": {"what": "Water world, terraformable, undiscovered", "body": "A 3", "value": "2.3M"}, "mapped_before": {},
    "find_bio": {"body": "B 7", "value": "19.0M"}, "sample_clear": {"genus": "Stratum"}, "bio_tag_near": {"genus": "Tussock", "distance": 80},
    "codex": {"entry": "Stratum Tectonicas", "what": "new to your codex for this region"},
    "docking_granted": {"pad": 34, "station": "Jameson Memorial"},
    "docking_denied": {"reason": "no pad free for your ship: try again shortly", "station": "Jameson Memorial"},
    "phenomena": {"what": "three notable stellar phenomena, all in rings"},
    "rare_star": {"what": "a black hole at B"}, "old_data": {"year": "2019"},
    "ring_found": {"body": "A 3", "ring": "a pristine metallic ring"}, "limpets_none": {}, "limpets_low": {"count": 5}, "hold_nearly_full": {"minutes": 5, "free": 12}, "hold_full": {},
    "prospect_hit": {"what": "Platinum, 34 percent"}, "motherlode": {"mineral": "Void Opal"},
    "ring_found_many": {"count": 3, "bodies": "A 3, A 5 and B 1", "types": "metallic and icy"},
    "surface_site": {"what": "Guardian sites on B 3"},
    "signal_poi": {"what": "a Guardian beacon"},
    "curious": {},
    "ggg": {"body": "B 3"},
    "fuel_low": {"pct": 18}, "fuel_star": {"pct": 22, "star": "white dwarf"},
    "fuel_target": {"pct": 22, "system": "Drojau LL-O b26-3"},
    "fuel_topup": {"rate": "8 of the last 20 stars were scoopable", "jumps": "about 6 jumps"}, "hull": {"pct": 42}, "interdicted": {"by": "someone"},
    "fuel_short": {"system": "Smojooe AR-E b25-8", "jumps": "4 jumps", "need": "24 tonnes"},
    "fuel_last_scoop": {"count": 3},
    "docked_sell": {"value": "114.1M", "station": "Jaques Station"}, "undocked_unsold": {"value": "260.4M"},
    "sold": {"sold": "12.6M cr cartographics and 4.1M cr exobiology", "still": ""},
    "unsold_warn": {"value": "52.0M"}, "unsold_urgent": {"value": "251.3M"},
    "firsts_seen": {"system": "Drojau LL-O b26-3", "value": "14.2M"},
    "upload_held": {"service": "EDSM"},
    "suit_low": {"what": "oxygen", "value": "412M", "distance": "640 metres"},
    "upkeep_low": {"carrier": "Deep Wanderer", "weeks": "3 weeks"},
    "bookmarked": {"system": "Drojau LL-O b26-3"},
    "carrier_departs": {"minutes": 4, "carrier": "Out Of The Blue"},
    "autotarget_nothing": {"why": "no route is plotted"},
    "wrong_target": {"system": "Smojooe AR-E b25-8", "next": "Pru Aim XY-Z d1"},
    "carrier_arrived": {"carrier": "Out Of The Blue", "system": "Smojooe AR-E b25-8"},
    "fss_done": {"count": 14, "text": "B 1, Earth-like world, 3.1M to map, and biology on C 2, up to 19.0M"},
    "fss_nothing": {"count": 14}, "fss_unfinished": {"left": "3 bodies"},
    "jumponium": {"body": "B 4", "material": "polonium", "pct": "1.3 percent"},
    "region": {"region": "the Norma Arm", "count": "31 species you have logged elsewhere are new to your codex here"},
    "left_body": {"body": "A 3", "text": "Stratum 2 of 3, and Tussock untouched, up to 4.1M"},
    "bio_done_more": {"species": "Stratum Tectonicas", "value": "19.2M", "left": "Bacterium and Fungoida"},
    "bio_done_last": {"species": "Stratum Tectonicas", "value": "19.2M"},
    "tank_full": {"jumps": 8}, "scoop_stopped": {"pct": 64}, "supercharged": {"mult": "4 times"},
    "fsd_charge": {"system": "Drojau LL-O b26-3"},
    "body_brief": {"body": "B 7", "text": "3 biological signals, one of Stratum, Bacterium or Fungoida, 1.0M to 19.0M"},
    "high_g": {"gravity": "2.6", "value": "480.2M", "rebuys": "3.2"},
    "arrival_brief": {"text": "Undiscovered. 14 bodies. Scoopable K star."},
    "session_recap": {"text": "142 jumps, 3,100 light-years, 12 systems nobody had seen, 9 species sampled"},
    "streak_known": {"count": 10}, "streak_new": {"count": 5},
    "welcome_back": {"text": "Away 3 days. 412.0M aboard, unsold for 5 days. Fuel 64 percent. Docked at Jaques Station."},
    "ship_lost": {"text": "Lost 212.4M: 148.1M cartographics, 64.3M exobiology, 31 systems and 9 first discoveries. "
                          "The nearest lost system is Drojau LL-O b26-3, 42 light-years."},
    "sale_left": {"text": "Sold 50 systems for 14.8M. 43 systems are still unsold, 2.0M, 270 first discoveries: "
                          "sell the next page."},
    **_chatter.SAMPLES,
}
# The crew (the author's plan of 2026-10-13): the spoken alerts split among crew members, each with its own personality
# and voice, so you know who is talking (and so what about) before the sentence ends. Each alert row of Settings ->
# Alerts (page.js ALERTS) belongs to one role by default: (id, title in Settings, short name in the server log, rows).
# The XO / Co-pilot is the main voice and personality (the voice answers, the status report, the co-pilot's lines, any
# line that is no alert row's) and stands in for a role that cannot speak; Tactical has no row of its own: it speaks
# the danger lines (page.js DANGER) while the crew's Danger switch is on. The one source: the page gets it from GET
# /api/speech (`crew_roles`), and a test keeps the rows in step with page.js ALERTS (every row exactly once).
CREW_ROLES = (
    ("xo", "XO / Co-pilot", "XO", ()),
    ("navigator", "Navigator", "Navigator",
     ("jump", "highway", "riches", "trade", "refuelshort", "lastscoop", "autotarget", "wrongtarget", "supercharge", "pins")),
    ("science", "Science Officer", "Science Officer",
     ("discovery", "arrival", "honk", "brief", "fss", "mapped", "approach", "bodybrief", "leaving", "codex", "phenomena",
      "ggg", "rare_star", "surface_site", "signal_poi", "curious")),
    ("exobiologist", "Exobiologist", "Exobiologist", ("exo", "find", "sampling")),
    ("engineer", "Chief Engineer", "Engineer", ("fuel", "scoop", "scoopstop", "jumponium", "hull", "suit")),
    ("quartermaster", "Quartermaster", "Quartermaster", ("sell", "saleleft", "unsold", "carrier", "upkeep", "carriertrip", "loss")),
    ("comms", "Comms Officer", "Comms", ("uploads", "uploadheld", "firstsseen", "game", "docking", "chat")),
    ("tactical", "Tactical", "Tactical", ()),
    ("mining", "Mining Officer", "Mining Officer", ("rigs", "rigleash", "rigsout", "ring", "limpets", "prospect")),
)
CREW_IDS = tuple(r[0] for r in CREW_ROLES)
CREW_SHORT = {r[0]: r[2] for r in CREW_ROLES}
CREW_ROW_ROLE = {row: r[0] for r in CREW_ROLES for row in r[3]}   # an alert row -> its role by default
# The speech keys each alert row says (page.js ROW_KEYS) and the danger keys (page.js DANGER: Tactical's while the
# Danger switch is on), so the checks know who says a line on the default table; tests/test_crew.py keeps both in step
# with the page. (rig_leash: a danger tag with plain words, no lines of its own.)
ROW_KEYS = {
    "arrival": ("arrival_undiscovered", "arrival_discovered", "region", "streak_new", "streak_known"),
    "game": ("game_start", "welcome_back", "game_exit", "session_recap"), "jump": ("fsd_charge",), "brief": ("arrival_brief", "old_data"),
    "fss": ("fss_done", "fss_nothing", "fss_unfinished"), "leaving": ("leaving",),
    "fuel": ("fuel_low", "fuel_star", "fuel_target", "fuel_topup"), "scoop": ("tank_full",), "scoopstop": ("scoop_stopped",),
    "supercharge": ("supercharged",), "refuelshort": ("fuel_short",), "lastscoop": ("fuel_last_scoop",),
    "autotarget": ("autotarget_nothing",), "wrongtarget": ("wrong_target",),
    "find": ("find_body", "find_bio", "mapped_before", "sample_clear"), "jumponium": ("jumponium",),
    "sampling": ("bio_done_last", "bio_done_more", "bio_tag_near", "left_body"), "approach": ("high_g",),
    "bodybrief": ("body_brief",), "docking": ("docking_granted", "docking_denied"), "sell": ("docked_sell", "sold", "undocked_unsold"), "saleleft": ("sale_left",),
    "unsold": ("unsold_warn", "unsold_urgent"), "firstsseen": ("firsts_seen",), "hull": ("hull", "heat", "interdicted"),
    "carrier": ("carrier_arrived", "carrier_departs"), "codex": ("codex",), "phenomena": ("phenomena",), "ggg": ("ggg",),
    "rare_star": ("rare_star",), "surface_site": ("surface_site",), "signal_poi": ("signal_poi",), "curious": ("curious",),
    "loss": ("ship_lost",), "rigleash": ("rig_leash",), "ring": ("ring_found", "ring_found_many"), "limpets": ("limpets_none", "limpets_low", "hold_nearly_full", "hold_full"), "prospect": ("prospect_hit", "motherlode"),
    "uploadheld": ("upload_held",), "suit": ("suit_low",), "upkeep": ("upkeep_low",),
}
DANGER = ("hull", "heat", "interdicted", "fuel_low", "fuel_star", "fuel_target", "fuel_topup", "fuel_short", "fuel_last_scoop",
          "carrier_departs", "ship_lost", "rig_leash", "suit_low")
# The crew placeholders (crew batch 3, the author's idea of 2026-10-13): a line may name another crew member, one
# placeholder per role ("...ask {engineer} whether the tank can take that stretch"). Filled with the member's name when
# Settings gives it one (the name in every position: "Mira", never "the Mira"), else these words, with a capital at a
# sentence's start (the line's start, or after ". ", "! ", "? ", "... ", as filled: "{text} {engineer}" after a {text}
# ending in a full stop starts one). "the Engineer", not "the Chief Engineer";
# Comms and Tactical take no article, as crews say them. Optional in every alert's lines. A line holding any of them is
# said only while the crew is on, and never by the member it names: check() rejects that on the default table
# (crew_speakers), and the page skips it at pick time for a row moved to another member.
CREW_WORDS = {"xo": "the XO", "navigator": "the Navigator", "science": "the Science Officer",
              "exobiologist": "the Exobiologist", "engineer": "the Engineer", "quartermaster": "the Quartermaster",
              "comms": "Comms", "tactical": "Tactical", "mining": "the Mining Officer"}
CREW_PLACEHOLDER = re.compile(r"\{(" + "|".join(CREW_WORDS) + r")\}")
# made-up names for trying the crew's lines (the voice lab's Audition: crew lines, for a member with no name of its own)
CREW_SAMPLES = {"xo": "Kade", "navigator": "Rook", "science": "Ada", "exobiologist": "Ines", "engineer": "Mira",
                "quartermaster": "Bram", "comms": "Tess", "tactical": "Vance", "mining": "Dov"}


def crew_roles_info():
    """CREW_ROLES for the page: [{id, title, short, rows, words, sample}], the XO first (`words`: its placeholder's
    words without a name, `sample`: a made-up name for trying lines)."""
    return [{"id": i, "title": t, "short": s, "rows": list(rows), "words": CREW_WORDS[i], "sample": CREW_SAMPLES[i]}
            for i, t, s, rows in CREW_ROLES]


def crew_speakers(key):
    """The crew members who say alert `key` on the default table: its rows' roles, Tactical for a danger key (the
    Danger switch is on by default, and off the row's member says it), the XO for a key no row says (speech on)."""
    roles = {CREW_ROW_ROLE[row] for row, keys in ROW_KEYS.items() if key in keys and row in CREW_ROW_ROLE}
    if key in DANGER:
        roles.add("tactical")
    return roles or {"xo"}


def crew_named(text):
    """The crew members a line names ({engineer}...), in order, each once; [] for a plain line."""
    return list(dict.fromkeys(CREW_PLACEHOLDER.findall(text)))


def sentence_start(before):
    """Whether a placeholder after `before` (the line up to it, as filled) opens a sentence: the line's start, or after
    ". ", "! ", "? " or "... " (and "… ")."""
    return not before.strip() or before.endswith((". ", "! ", "? ", "… "))


def crew_says(role, names=None, start=False):
    """What a crew placeholder says: the member's name from `names` ({role: name}) when it has one, else its words
    ("the Engineer"), with a capital at a sentence's start ("The Engineer")."""
    name = (names or {}).get(role)
    w = name.strip() if isinstance(name, str) and name.strip() else CREW_WORDS[role]
    return w[:1].upper() + w[1:] if start else w


# the voice lab's Audition (page.js AUDITION_KEYS): one personality across the alerts that matter, in a session's order
AUDITION = ("game_start", "arrival_brief", "find_body", "leaving", "fuel_low", "sold", "bio_done_last", "session_recap")
DEFAULT_NAMES = "Boss, Hefay, Sir"
# values already phrased in lower case ("a metallic ring", "metallic and icy"): a capital when one starts a sentence
# (page.js START_CAPS), so the caption reads "Metallic rings at A 3"
START_CAPS = ("ring", "types")


def names_list(text):
    return [x.strip() for x in str(text or "").split(",") if x.strip()]


def fill(text, values, names=DEFAULT_NAMES, rng=None, crew=None):
    """A line with its {placeholders} filled: every {name} is its own random pick from `names`; a crew placeholder
    ({engineer}) is the member's name from `crew` ({role: name}) or its words (crew_says, page.js fillLine)."""
    import random
    rng = rng or random
    pool = names_list(names) or ["Commander"]

    out, last = [], 0
    for m in PLACEHOLDER.finditer(text):   # in order: a crew placeholder looks at the line as filled so far
        out.append(text[last:m.start()])
        last, k = m.end(), m.group(1)
        if k == "name":
            out.append(rng.choice(pool))
        elif k in CREW_WORDS:
            out.append(crew_says(k, crew, sentence_start("".join(out))))
        else:
            v = "" if values.get(k) is None else str(values.get(k))
            out.append(v[:1].upper() + v[1:] if k in START_CAPS and sentence_start("".join(out)) else v)
    return "".join(out) + text[last:]


_PROC_NAME = re.compile(r"\b([A-Z])([A-Z])-([A-Z]) ([a-h])(\d+)(?:-(\d+))?\b")
_EMOJI = re.compile("[☀-➿\U0001f300-\U0001faff⭐✨⚠️]")


def spoken_text(text):
    """Text as the page hands it to the voice: markup and emoji out, 2.3M as "2.3 million", cr as credits."""
    t = re.sub(r"<[^>]+>", "", str(text))
    t = _EMOJI.sub("", t)
    # numbers to a tenth at most, and "52.0" as "52" (12.64B is "12.6 billion", 52.0M "52 million")
    # (fixed-point, not :g, which goes to "1.23457e+06" from a million and drops the tenths from 100000)
    t = re.sub(r"(?<![\d.])\d+\.\d+(?![\d.])", lambda m: f"{float(m.group()):.1f}".removesuffix(".0"), t)
    t = re.sub(r"(\d+(?:\.\d+)?)M\b", r"\1 million", t)
    t = re.sub(r"(\d+(?:\.\d+)?)k\b", r"\1 thousand", t)
    t = re.sub(r"(\d+(?:\.\d+)?)B\b", r"\1 billion", t)
    t = re.sub(r"\bcr\b", "credits", t)
    t = re.sub(r"\s·\s", ", ", t)
    # a procedural system name's sector suffix letter by letter ("Drojau LL-O b26-3" -> "Drojau L L O, b 26 3"),
    # as the page's spokenText does; a carrier id (K7F-3XZ) or a hand-named system does not match
    t = _PROC_NAME.sub(lambda m: f"{m[1]} {m[2]} {m[3]}, {m[4]} {m[5]}" + (f" {m[6]}" if m[6] else ""), t)
    return re.sub(r"\s+", " ", t).strip()


# ---- S9-S17: a personality skeleton to start your own from (python3 -m outrider.speech --skeleton "Pirate") ----

def skeleton(label, profane=False, names=None):
    """A personality file with every spoken alert (spoken_keys) as an empty list to fill: {"_readme", "styles",
    "lines": {key: {"_when": what it is said for and its {placeholders}, <id>: [], <id>_profane: []}}}. check() reads
    it clean (its "_when" is skipped as "when" is); Settings shows it 0 % covered until lines are written."""
    sid = re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_") or "mine"
    lists = [sid] + ([sid + "_profane"] if profane else [])
    readme = [f"{label}: your own personality. Write lines under each alert, in its own voice: one or two sentences, "
              "said aloud, no emoji or markdown.",
              "Placeholders in {braces} are filled in when the line is said: each alert's own (its _when names them), "
              "and always {name} (what you asked to be called), {ship} and {here}; {" + "}, {".join(CREW_WORDS) +
              "} name another crew member (never the one who says the alert).",
              "Ten lines or more an alert keeps them from repeating. See docs/guide/voice-and-alerts.md, Your own personality."]
    style = {"label": str(label)}
    if names:
        style["names"] = list(names)
    return sid, {"_readme": readme, "styles": {sid: style},
                 "lines": {k: dict({"_when": KEYS[k]}, **{x: [] for x in lists}) for k in spoken_keys()}}


def shipped_style_ids(resources=RESOURCES_DIR):
    """{style id: where it comes from} of the base personalities (resources/speech.json) and the shipped ones
    (resources/personalities/*.json): ids a file of your own cannot take."""
    out = {}
    try:
        with open(os.path.join(resources, "speech.json"), encoding="utf-8") as f:
            out.update({k: "a base personality" for k in (json.load(f).get("styles") or {})})
    except (OSError, ValueError):
        pass
    folder = os.path.join(resources, "personalities")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                out.update({k: f"the shipped personality {name}" for k in (json.load(f).get("styles") or {})})
        except (OSError, ValueError):
            continue
    return out


def write_skeleton(label, profane=False, names=None, folder=None):
    """S9-S17: the skeleton written to <folder>/<id>.json (data/personalities/ by default), never over a file there.
    (path, None) or (None, why not)."""
    sid, doc = skeleton(label, profane, names)
    taken = shipped_style_ids()
    if sid in taken:   # bug check #10: merge_personalities leaves out a file taking a base or shipped personality's id
        return None, (f"{label!r} is the id of {taken[sid]}: Outrider would leave your file out. Pick another name "
                      "(or copy that personality's own file into data/personalities/ to change it)")
    folder = folder or os.path.join(DATA_DIR, "personalities")
    path = os.path.join(folder, f"{sid}.json")
    if os.path.exists(path):
        return None, f"{path} is there already: nothing written (move it, or pick another name)"
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return path, None


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m outrider.speech", description="ED Outrider's spoken lines: start a "
                                 "personality file of your own (S9-S17).")
    ap.add_argument("--skeleton", metavar="NAME", required=True, help='the personality\'s name, e.g. "Pirate"')
    ap.add_argument("--profane", action="store_true", help="a swearing list too (<id>_profane)")
    ap.add_argument("--names", help='what it calls you, comma separated (e.g. "Captain, Skipper")')
    ap.add_argument("--folder", help="where to write it (default: data/personalities/)")
    a = ap.parse_args(argv)
    names = [x.strip() for x in a.names.split(",") if x.strip()] if a.names else None
    path, why = write_skeleton(a.skeleton, a.profane, names, a.folder)
    if why:
        print(why, file=__import__("sys").stderr)
        return 1
    print(f"written: {path} ({len(spoken_keys())} alerts to fill in; Outrider reads it at its next start)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
