"""Questions to Outrider by voice (tablet plan phase 6): the tablet app hears "hey Vespa ..." (or a tap), turns the
question into text and sends it to POST /api/ask; the answer is said on the PC and shown as a caption everywhere.

First the fixed commands, matched without any AI (resources/ask.json: editable phrases): status report, fuel,
unsold, next jump, what's left here, nearest unvisited, nearest station (or carrier, Vista, repair...), nearest
green gas giant, FSD injections, how far today, this body, left behind nearby, hush (for a set time: S32), unhush.
Their answers come from the same read-only tools
the MCP bridge serves (outrider/tools.py), called in-process. Then, only when [assistant] enabled is true, an optional
AI layer for anything else: an OpenAI-compatible chat-completions endpoint (Ollama, Venice.ai, OpenAI...) given those
same tools. It runs on the PC; the key never leaves it. Nothing is sent anywhere unless it is configured.
"""
import asyncio
import json
import os
import re
import sys
import time

import outrider
import outrider.dock as dock
from outrider.core import iso_ts, ts_seconds
import outrider.materials as materials
import outrider.tools as tools

ASK_FILE = os.path.join(outrider.RESOURCES_DIR, "ask.json")
TEXT_MAX = 500
# in the order questions are matched: nearest_dock before fuel, unsold, next_jump and whats_left, whose single words
# ("fuel") are in its questions too ("nearest station with fuel" asked for the fuel gauge: the sweep of 2026-10-09)
# S14's four before next_jump and status_report ("status of this body" is this_body; "what's left behind" is not whats_left)
COMMANDS = ("unhush", "hush", "nearest_ggg", "nearest_dock", "fsd_injection", "travel_today", "left_behind", "this_body",
            "next_jump", "status_report", "fuel", "unsold", "whats_left", "nearest_unvisited")
# what the voice says it knows when nothing matched: one label per command, in the order said (a test checks every
# command has one, so a new command is never left out of the list)
LABELS = {"status_report": "a status report", "fuel": "fuel", "unsold": "unsold data", "next_jump": "the next jump",
          "whats_left": "what's left here", "nearest_unvisited": "the nearest unvisited system",
          "nearest_dock": "the nearest station, carrier or material trader",
          "nearest_ggg": "the nearest potential green gas giant", "fsd_injection": "FSD injections",
          "travel_today": "how far today", "this_body": "this body", "left_behind": "what's left behind nearby",
          "hush": "hush", "unhush": "unhush"}


def known_questions():
    """'I only know a few questions so far: ...' from LABELS."""
    labels = list(LABELS.values())
    return f"I only know a few questions so far: {', '.join(labels[:-1])} and {labels[-1]}."


# "nearest station", "nearest Vista"...: the words of the question narrow the search (a whole phrase is needed in
# ask.json, never a bare "nearest": the author, 2026-10-08)
NEAREST_WORDS = {"vista": "Vista", "genomics": "Vista", "cartographics": "UC", "cartographic": "UC", "repair": "Repair",
                 "repairs": "Repair", "refuel": "Refuel", "fuel": "Refuel", "shipyard": "Shipyard", "outfitting": "Outfitting"}
# a material trader (S54): "trader" asks for one, a kind's word narrows it only beside "trader" ("nearest station
# with raw..." is no trader question)
TRADER_WORDS = {"raw": "Raw", "manufactured": "Manufactured", "encoded": "Encoded", "data": "Encoded"}
TRADER_ASK = ("trader", "traders")
# "nearest station" / "nearest carrier": only that kind of place
STATION_WORDS = ("station", "stations", "starport", "outpost")
CARRIER_WORDS = ("carrier", "carriers")
WAKE = re.compile(r"^(hey|hi|ok|okay)?\s*vespa\b[\s,]*")
ASSISTANT = {"enabled": False, "base_url": "", "api_key": "", "model": "", "timeout": 20.0, "max_rounds": 4}
SYSTEM_PROMPT = ("You are Vespa, the co-pilot voice of ED Outrider, an exploration companion for the game Elite Dangerous. "
                 "Answer the commander's question in one or two short spoken sentences: no lists, no markdown, numbers "
                 "rounded the way a person says them. Use the tools for facts about their game; never invent them. "
                 "If the tools cannot answer, say so briefly.")


def read_file(path=ASK_FILE):
    """ask.json as written: ({command: [phrases]}, {command: description}), the known commands only, in the file's
    order; a missing or broken file falls back to the command names themselves (reported on stderr), no descriptions."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        cmds = doc.get("commands") if isinstance(doc, dict) else None   # a list or a string: broken too, not a crash
        if not isinstance(cmds, dict):
            raise ValueError("no \"commands\" object")
        desc = doc.get("descriptions")
        return ({name: [x for x in phrases if isinstance(x, str)] for name, phrases in cmds.items()
                 if name in COMMANDS and isinstance(phrases, list)},
                {k: v for k, v in desc.items() if isinstance(v, str)} if isinstance(desc, dict) else {})
    except (OSError, ValueError) as e:
        print(f"ask: {path}: {e}; using the command names as phrases", file=sys.stderr)
        return {c: [c.replace("_", " ")] for c in COMMANDS}, {}


def phrases_of(cmds):
    """{command: [phrases]} as matched: each one normalised (norm), the empty ones dropped."""
    return {name: [p for p in (norm(x) for x in phrases) if p] for name, phrases in cmds.items()}


def load_phrases(path=ASK_FILE):
    """{command: [phrases]} from resources/ask.json, in its order (read_file's fallback for a missing or broken one)."""
    return phrases_of(read_file(path)[0])


def norm(text):
    """Lower case, apostrophes dropped, other punctuation as spaces, single spaces."""
    t = str(text or "").lower().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def match(text, phrases):
    """The fixed command a question is (the first in `phrases`' order with a phrase as whole words in it), or None."""
    return match_phrase(text, phrases)[0]


def match_phrase(text, phrases):
    """(command, the ask.json phrase that matched it), or (None, None): S35's "Questions asked" says which phrase."""
    t = WAKE.sub("", norm(text)).strip()
    padded = f" {t} "
    for name, ps in phrases.items():
        for p in ps:
            if f" {p} " in padded:
                return name, p
    return None, None


# ---- hush for a set time (S32) ----

# what the page says for each hush: a copy of page.js's HUSH_SAID, the words the voice's answer gives (test_hush_mode keeps
# the two the same); the server's HUSH_MODES are the only lengths there are
HUSH_SAID = {"10m": "Quiet for 10 minutes.", "30m": "Quiet for 30 minutes.", "jump": "Quiet until the next jump."}
HUSH_MINUTES = {"10m": 10, "30m": 30}
HUSH_JUMP = re.compile(r"\b(jump|jumps|jumping|next system|leave|leaving|arrive|arriving|arrival)\b")
NUMBER_WORDS = {w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                           "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS_WORDS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
TIME_UNITS = {"minute": 1, "minutes": 1, "min": 1, "mins": 1, "hour": 60, "hours": 60, "hr": 60, "hrs": 60}


def hush_minutes(text):
    """The minutes a hush is asked for ("ten minutes", "10 min", "twenty five minutes", "half an hour", "an hour"), or
    None when the question names no time."""
    w = norm(text).split()
    for i, unit in enumerate(w):
        if unit not in TIME_UNITS or i == 0:
            continue
        before, n = w[i - 1], None
        if before.isdigit():
            n = int(before)
        elif before in NUMBER_WORDS:
            n = NUMBER_WORDS[before] + (TENS_WORDS.get(w[i - 2], 0) if i >= 2 else 0)
        elif before in TENS_WORDS:
            n = TENS_WORDS[before]
        elif before == "quarter":
            n = 0.25
        elif before in ("a", "an"):
            lead = w[i - 3:i - 1] if i >= 3 else w[:i - 1]
            n = 0.5 if w[i - 2:i - 1] == ["half"] else 0.25 if "quarter" in lead else 1
        if n is not None:
            return n * TIME_UNITS[unit]
    return None


def hush_mode(text):
    """The hush a question asks for: "jump" (until the next jump: jump, next system, leave, arrive), "10m" or "30m"
    (the nearest of the two to the time asked for, 30 minutes when none is), never anything else: set_hush reads any
    other mode as "jump" (review)."""
    if HUSH_JUMP.search(norm(text)):
        return "jump"
    m = hush_minutes(text)
    return "30m" if m is None or m > 20 else "10m"


def hush_words(text):
    """(mode, the answer): the page's words for the hush set, and for a time it does not offer ("five minutes", "an
    hour") the three it does first, so the nearest one is no surprise (the author's default, 2026-10-12)."""
    mode, m = hush_mode(text), hush_minutes(text)
    said = HUSH_SAID[mode]
    if mode != "jump" and m is not None and m != HUSH_MINUTES[mode]:
        said = "I can hush for 10 or 30 minutes, or until the next jump. " + said
    return mode, said


# ---- the fixed answers, from the read-only tools ----

def words_cr(n):
    """Credits as said aloud: 1234567 -> "1.2 million"."""
    n = n or 0
    # the thresholds are where the unit below would round up to 1000 of itself (review 2026-10-20 L6: "1000 thousand",
    # "1000 million"), as riches.money
    if n >= 999_950_000:
        return f"{n / 1e9:.1f} billion".replace(".0 ", " ")
    if n >= 999_500:
        return f"{n / 1e6:.1f} million".replace(".0 ", " ")
    if n >= 1e3:
        return f"{round(n / 1e3)} thousand"
    return str(int(n))


def ly(x):
    return f"{x:,.0f}" if x is not None and x >= 100 else f"{x:.1f}" if x is not None else "?"


def jumps(n):
    """'1 jump', '6 jumps'."""
    return f"{n} jump{'' if n == 1 else 's'}"


def nearest_query(text):
    """What a "nearest ..." question asks for: (services, "station" | "carrier" | None)."""
    words = norm(text).split()
    need = []
    for w in words:
        s = NEAREST_WORDS.get(w)
        if s and s not in need:
            need.append(s)
    if "uc" in words and "UC" not in need:
        need.append("UC")
    if any(w in TRADER_ASK for w in words):
        kinds = [TRADER_WORDS[w] for w in words if w in TRADER_WORDS]
        need.append(kinds[0] if kinds else "Trader")
    kind = "station" if any(w in STATION_WORDS for w in words) else \
        "carrier" if any(w in CARRIER_WORDS for w in words) else None
    return need, kind


async def nearest_dock(get, text, rows=10):
    """The voice's "nearest station"... (the words of `text` narrow it): (words, the place said or None). The place is
    the nearest_dock tool's row the answer names ({system, distance_ly, ...}), for D4's plot there (State.ask)."""
    need, kind = nearest_query(text)
    d = await tools.call("nearest_dock", {"need": need, "kind": kind or "any"}, get, rows)
    if d.get("error"):
        return d["error"], None
    rows_ = [dict(p, ly=p["distance_ly"], here=not p["distance_ly"], warn=p["warnings"],
                  station_type=p.get("station_type"), own=bool(p.get("yours"))) for p in d.get("places") or []]
    said = dock.spoken({"rows": rows_}, need, kind)
    # the row dock.spoken names: your own carrier where you are is no answer
    place = next((p for p in rows_ if not (p["here"] and p["own"])), None)
    if any("spansh" in str(e).lower() for e in d.get("errors") or []):
        said = "Spansh could not be reached, so stations are missing. " + said
    return said, place


# ---- S14: FSD injections, how far today, this body, left behind nearby ----

GRADES = ("premium", "standard", "basic")


async def fsd_injection(get, rows):
    """"Premium injections: 2, short of polonium. Standard: 5. Basic: 31.": the materials tool's FSD recipes, picked
    by group and grade (a learned recipe keeps them: S15), the material that runs out first named for a grade you can
    make at most materials.JUMPONIUM_MAX times (the Materials tab's jumponium call-out)."""
    m = await tools.call("materials", {}, get, rows)
    if m.get("error"):
        return m["error"]
    if not m.get("counts_from"):
        return "I have no materials reading yet: the game writes one at login."
    fsd = {x.get("grade"): x for x in m.get("synthesis") or [] if x.get("group") == "fsd"}
    parts = []
    for g in GRADES:
        x = fsd.get(g)
        if not x:
            continue
        n = x.get("can_make") or 0
        part = f"{g.capitalize()}{' injections' if not parts else ''}: {n or 'none'}"
        if x.get("limited_by") and n <= materials.JUMPONIUM_MAX:
            part += f", short of {x['limited_by'].lower()}"
        parts.append(part + ".")
    if not parts:
        return "I don't know the FSD injection recipes."
    # counts from before this login: the game wrote no Materials line since (review)
    return " ".join(parts) + (" Counts from before this login." if m.get("stale") else "")


def local_midnight(now=None):
    """The start of today on this computer's clock, as the journals' UTC timestamp ("today" = local midnight: the
    author's default, 2026-10-12)."""
    lt = time.localtime(time.time() if now is None else now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return iso_ts(midnight)


SESSION_WORD = "session"   # "how far this session": the latest session alone


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else many or one + 's'}"


async def travel_today(get, rows, text="", now=None):
    """How far today: the sessions (travel_history, 2 days) that ended since local midnight, a session that began
    before it counted whole; with "session" in the question the latest session alone ("this session", or "your last
    session" when it ended over 2 h ago, History's split)."""
    h = await tools.call("travel_history", {"days": 2}, get, max(rows, 20))
    if h.get("error"):
        return h["error"]
    sessions = h.get("sessions") or []
    now = time.time() if now is None else now
    if SESSION_WORD in norm(text).split():
        if not sessions:
            return "No session in the last two days."
        x = sessions[0]
        old = bool(x.get("end")) and now - ts_seconds(x["end"]) > 7200
        lead, picked = ("Your last session" if old else "This session"), [x]
    else:
        midnight = local_midnight(now)
        lead, picked = "Today", [x for x in sessions if (x.get("end") or "") >= midnight]
        if not picked:
            return "No jumps yet today."
    total = {k: sum(x.get(k) or 0 for x in picked) for k in ("jumps", "ly", "first_discoveries", "mapped", "samples")}
    out = [plural(total["jumps"], "jump") if total["jumps"] else "no jumps"]
    if total["jumps"]:
        out[0] += f", {ly(total['ly'])} light years"
    if total["first_discoveries"]:
        out.append(plural(total["first_discoveries"], "first discovery", "first discoveries"))
    if total["mapped"]:
        out.append(plural(total["mapped"], "body", "bodies") + " mapped")
    if total["samples"]:
        out.append(plural(total["samples"], "sample"))
    return f"{lead}: {', '.join(out)}."


def a_or_an(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


async def this_body(get, rows):
    """The body you are on, else the one whose near-body zone you are in, else the one targeted in this system
    (/api/status: on_body, near_body, target_body), from body_detail: its type, landable and gravity, terraformable,
    its value now and if mapped, the biology (the likeliest, "up to") and geology signals."""
    s = await tools.call("current_status", {}, get, rows)
    if s.get("error"):
        return s["error"]
    name, lead = next(((s[k], lead) for k, lead in (("on_body", ""), ("near_body", ""), ("target_body", "Targeted: "))
                       if s.get(k)), (None, ""))
    if not name:
        return "You're not on or near a body, and no body is targeted."
    b = await tools.call("body_detail", {"name": name}, get, rows)
    if b.get("error"):
        return f"{lead}{name}: nothing known about it yet."
    kind = b.get("type") or "body"
    if kind[1:2].islower():   # "Rocky body" -> "rocky body"; "K (Yellow-Orange) Star", "Class I gas giant" kept
        kind = kind[0].lower() + kind[1:]
    first = f"{lead}{name}, {a_or_an(kind)} {kind}"
    if b.get("landable"):
        first += f", landable at {b['gravity_g']:.2f} g" if b.get("gravity_g") is not None else ", landable"
    if b.get("terraformable"):
        first += ", terraformable"
    out = [first + "."]
    worth = [f"{words_cr(b['value_now'])} credits now" if b.get("value_now") else "",
             f"{words_cr(b['value_if_mapped'])} if mapped" if b.get("value_if_mapped") else ""]
    if any(worth):
        out.append("Worth " + ", ".join(w for w in worth if w) + ".")
    if b.get("bio_signals"):
        bio = plural(b["bio_signals"], "biological signal")
        top = (b.get("bio_predicted") or [None])[0]
        if top and (top.get("likeliest") or top.get("genus")):
            bio += f": likeliest {top.get('likeliest') or top['genus']}" + (f", up to {words_cr(top['up_to'])}" if top.get("up_to") else "")
        out.append(bio + ".")
    if b.get("geo_signals"):
        out.append(plural(b["geo_signals"], "geological signal") + ".")
    return " ".join(out)


LEFT_RADIUS = 100


async def left_behind(get, limits=None):
    """The nearest one or two systems within LEFT_RADIUS ly with work worth going back for: bodies not found, planets
    worth mapping and biology over `limits` (body, bio: the server's body_highlight_level and bio_min, never a
    browser's: the page's Left behind keeps its own), what it is worth "up to"."""
    d = await tools.call("left_behind", {"radius_ly": LEFT_RADIUS}, get, 500)
    if d.get("error"):
        return d["error"]
    body_min, bio_min = limits or (0, 0)
    said = []
    for x in d.get("systems") or []:
        maps = [m for m in x.get("map") or [] if (m.get("adds") or 0) >= body_min]
        bio = [b for b in x.get("bio") or [] if (b.get("up_to") or 0) >= bio_min]
        unfound = x.get("bodies_not_found") or 0
        if not (maps or bio or unfound):
            continue
        bits = [plural(unfound, "body", "bodies") + " not found" if unfound else "",
                "map " + ", ".join(m["body"] for m in maps[:3]) if maps else "",
                "biology on " + ", ".join(b["body"] for b in bio[:3]) if bio else ""]
        worth = sum(m.get("adds") or 0 for m in maps) + sum(b.get("up_to") or 0 for b in bio)
        said.append(f"{x['name']}, {ly(x.get('distance_ly'))} light years: " + "; ".join(b for b in bits if b)
                    + (f", worth up to {words_cr(worth)}" if worth else "") + ".")
        if len(said) == 2:
            break
    if not said:
        return f"Nothing worth going back for within {LEFT_RADIUS} light years."
    return "Left behind nearby: " + said[0] + (" Then " + said[1] if len(said) > 1 else "")


async def fixed_answer(command, get, rows=10, text="", limits=None):
    """The words for a fixed command (hush and unhush are the caller's: they change state, the tools cannot).
    `limits`: (body, bio) credits, the server's thresholds for left_behind."""
    if command == "fsd_injection":
        return await fsd_injection(get, rows)
    if command == "travel_today":
        return await travel_today(get, rows, text)
    if command == "this_body":
        return await this_body(get, rows)
    if command == "left_behind":
        return await left_behind(get, limits)
    if command == "fuel":
        s = await tools.call("current_status", {}, get, rows)
        if s.get("error"):
            return s["error"]
        if s.get("fuel_pct") is None:
            return "I have no fuel reading yet."
        return f"Fuel at {s['fuel_pct']} percent" + (f", about {jumps(s['fuel_jumps'])} at max range." if s.get("fuel_jumps") is not None else ".")
    if command == "unsold":
        u = await tools.call("unsold_data", {}, get, rows)
        if u.get("error"):
            return u["error"]
        c, b = (u.get("cartographic") or {}).get("estimated_payout") or 0, (u.get("exobiology") or {}).get("estimated_value") or 0
        if not (u.get("total") or c or b):
            return "Nothing unsold aboard."
        parts = [f"{words_cr(c)} cartographic" if c else "", f"{words_cr(b)} exobiology" if b else ""]
        return f"About {words_cr(u.get('total') or c + b)} credits unsold: {' and '.join(p for p in parts if p)}."
    if command == "next_jump":
        h = await tools.call("highway_route", {}, get, rows)
        if h.get("error"):
            return h["error"]
        if not h.get("route", True) or not h.get("next"):
            return "No highway route plotted." if not h.get("complete") else "The highway route is complete."
        nx = h["next"]
        out = f"Next highway stop: {nx['system']}, {ly(nx.get('distance_ly'))} light years" + (", a neutron star" if nx.get("neutron") else "") + "."
        if h.get("off_route"):
            out = f"You are off the route; the nearest route system is {h.get('nearest_route_system')}. " + out
        if h.get("jumps_left") is not None:
            out += f" {jumps(h['jumps_left'])} left"
            out += f", refuel in {h['refuel_in_jumps']}." if h.get("refuel_in_jumps") else "."
        return out
    if command == "nearest_dock":
        return (await nearest_dock(get, text, rows))[0]
    if command == "nearest_ggg":   # S27: Outrider's cache only, a guess from the ladder model (said so)
        g = await tools.call("nearest_ggg", {}, get, rows)
        if g.get("error"):
            return g["error"]
        x = (g.get("giants") or [None])[0]
        if not x:
            return f"None within {ly(g.get('radius_ly'))} light years in what Outrider has cached."
        return (f"Nearest potential green gas giant: {x['body']} in {x['system']}, {ly(x.get('distance_ly'))} light years. "
                "A guess from the ladder model: check it in the system map.")
    if command == "nearest_unvisited":
        n = await tools.call("nearest_unvisited", {}, get, rows)
        if n.get("error"):
            return n["error"]
        x = n.get("nearest")
        if not x:
            return n.get("note") or "No known unvisited system nearby."
        return f"Nearest unvisited: {x['name']}, {ly(x.get('distance_ly'))} light years" + (", scoopable." if x.get("scoopable") else ".")
    if command == "whats_left":
        s = await tools.call("this_system", {}, get, rows)
        if s.get("error"):
            return s["error"]
        t = s.get("to_do") or {}
        bits = []
        if t.get("honked") is False:
            bits.append("honk the system")
        if t.get("bodies_to_find"):
            bits.append(f"find {t['bodies_to_find']} more bod{'y' if t['bodies_to_find'] == 1 else 'ies'} in the FSS")
        if t.get("bio_to_sample"):
            bits.append("biology on " + ", ".join(t["bio_to_sample"][:3]))
        if t.get("worth_mapping"):
            bits.append("map " + ", ".join(x["body"] for x in t["worth_mapping"][:3]))
        return ("Still to do here: " + "; ".join(bits) + ".") if bits else "Nothing worth staying for here."
    if command == "status_report":
        s = await tools.call("current_status", {}, get, rows)
        if s.get("error"):
            return s["error"]
        out = [f"{s.get('system') or 'Position unknown'}."]
        if s.get("fuel_pct") is not None:
            out.append(f"Fuel {s['fuel_pct']} percent" + (f", {jumps(s['fuel_jumps'])}." if s.get("fuel_jumps") is not None else "."))
        if s.get("unsold"):
            out.append(f"{words_cr(s['unsold'])} credits unsold.")
        h = await tools.call("highway_route", {}, get, rows)
        if h.get("next"):
            out.append(f"Highway: next {h['next']['system']}, {jumps(h.get('jumps_left'))} left.")
        return " ".join(out)
    raise ValueError(command)


# ---- the list of voice commands (Settings → Voice, the tablet's Voice commands…: GET /api/ask/commands) ----

# how the list groups the commands (a test checks each command is in exactly one)
GROUPS = (("Where you are", ("status_report", "fuel", "unsold", "whats_left", "this_body")),
          ("Where to go", ("next_jump", "nearest_unvisited", "nearest_dock", "nearest_ggg", "left_behind")),
          ("Your trip and your materials", ("travel_today", "fsd_injection")),
          ("The voice", ("hush", "unhush")))
# hush's times as they can be said (S32): (the mode, what it gives, examples); a test checks hush_mode reads each one so
HUSH_EXAMPLES = (("10m", "10 minutes", ("for ten minutes", "for 10 min", "for a quarter of an hour")),
                 ("30m", "30 minutes (also when no time is said)", ("for half an hour", "for thirty minutes")),
                 ("jump", "until the next jump", ("until the next jump", "until we leave", "till the next system")))
SERVICE_NAMES = {"UC": "Universal Cartographics", "Vista": "Vista Genomics"}


def title(command):
    """A command's name in the list, from LABELS: "a status report" -> "Status report"."""
    t = re.sub(r"^(a|an|the) ", "", LABELS.get(command) or command.replace("_", " "))
    return t[:1].upper() + t[1:]


def narrowing(command):
    """The words that narrow a command once one of its phrases matched, from the tables its answer reads: [{words,
    means}] (nearest_dock's services, stations or carriers, a trader and its kind; hush's times; travel_today's
    "session"); [] for the others."""
    if command == "nearest_dock":
        by = {}
        for w, svc in NEAREST_WORDS.items():
            by.setdefault(svc, []).append(w)
        by.setdefault("UC", []).append("uc")   # nearest_query's own: "uc" is not a NEAREST_WORDS key
        kinds = {}
        for w, k in TRADER_WORDS.items():
            kinds.setdefault(k, []).append(w)
        return ([{"words": ws, "means": f"with {SERVICE_NAMES.get(svc, svc)}"} for svc, ws in by.items()]
                + [{"words": list(STATION_WORDS), "means": "stations only"},
                   {"words": list(CARRIER_WORDS), "means": "fleet carriers only"},
                   {"words": list(TRADER_ASK), "means": "a material trader of any kind"}]
                + [{"words": ws, "means": f"beside \"trader\": {a_or_an(k)} {dock.trader_words(k)}"} for k, ws in kinds.items()])
    if command == "hush":
        return [{"words": list(ex), "means": means} for _, means, ex in HUSH_EXAMPLES]
    if command == "travel_today":
        return [{"words": [SESSION_WORD], "means": "the latest session alone, not all of today"}]
    return []


def command_list(file=None):
    """GET /api/ask/commands: every fixed command, by GROUPS: {command, title, description (ask.json's
    "descriptions"), phrases (as the file writes them, one spelling of each), narrowing}. `file`: read_file's answer (the server passes the
    one it matches with, read at start); a command with no phrase left is left out (nothing asks it)."""
    cmds, desc = file or read_file()

    def said(phrases):   # each phrase once as it is heard ("what's left" and "whats left" are one), the first spelling
        seen = {}
        for p in phrases:
            seen.setdefault(norm(p), " ".join(p.split()))
        return [p for k, p in seen.items() if k]
    groups = []
    for name, members in GROUPS:
        rows = [{"command": c, "title": title(c), "description": desc.get(c), "narrowing": narrowing(c),
                 "phrases": said(cmds.get(c) or [])} for c in members]
        rows = [r for r in rows if r["phrases"]]
        if rows:
            groups.append({"name": name, "commands": rows})
    return groups


# ---- the optional AI layer ----

class AIError(Exception):
    """The AI provider failed: code "ai_timeout", "ai_error" or "ai_off" (not configured), and words for a person."""

    def __init__(self, code, why):
        super().__init__(why)
        self.code, self.why = code, why


def assistant_settings(cfg):
    """[assistant] from a parsed config (wrong values reported on stderr, defaults kept): enabled, base_url, api_key,
    model, timeout (s), max_rounds (tool rounds)."""
    a = cfg.get("assistant") if isinstance(cfg.get("assistant"), dict) else {}
    out = dict(ASSISTANT)
    for k in ("base_url", "api_key", "model"):
        v = a.get(k, out[k])
        if isinstance(v, str):
            out[k] = v.strip()
        else:
            print(f"config: [assistant] {k} must be text; ignored", file=sys.stderr)
    if isinstance(a.get("enabled"), bool):
        out["enabled"] = a["enabled"]
    elif "enabled" in a:
        print("config: [assistant] enabled must be true or false; using false", file=sys.stderr)
    for k, lo, hi in (("timeout", 2, 120), ("max_rounds", 1, 8)):
        v = a.get(k, out[k])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            print(f"config: [assistant] {k} must be {lo} to {hi}; using {ASSISTANT[k]}", file=sys.stderr)
        else:
            out[k] = float(v) if k == "timeout" else int(v)
    if out["base_url"] and not out["base_url"].startswith(("http://", "https://")):
        print("config: [assistant] base_url must be an http(s) address; the AI layer stays off", file=sys.stderr)
        out["base_url"] = ""
    return out


MALFORMED = "the AI provider's answer was malformed"


def message_text(content):
    """A message's words: a string, or a list of text parts ({"type": "text", "text": ...}) joined. AIError else."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(p, dict) for p in content):
        return "".join(p["text"] for p in content if isinstance(p.get("text"), str))
    raise AIError("ai_error", MALFORMED)


def call_arguments(fn):
    """A tool call's arguments: a JSON object in a string (OpenAI), or already an object (some providers)."""
    args = fn.get("arguments")
    if isinstance(args, dict):
        return args
    try:
        args = json.loads(args or "{}")
    except (TypeError, ValueError):
        return {}
    return args if isinstance(args, dict) else {}


def openai_tools():
    """The registry as OpenAI-style function tools (the same tools the MCP bridge serves)."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}}
            for t in tools.listing()]


async def ai_answer(text, cfg, get, session, rows=10, trace=None):
    """Ask the configured chat-completions endpoint, running its tool calls through the read-only registry, until it
    answers in words (at most max_rounds tool rounds). Raises AIError. trace (a dict, S35's "Questions asked"): its
    `rounds` counts the requests made and `tools` lists the tools run, kept up to a failure too (never the key)."""
    trace = {} if trace is None else trace
    trace.setdefault("rounds", 0)
    trace.setdefault("tools", [])
    if not cfg.get("base_url") or not cfg.get("model"):
        raise AIError("ai_off", "the AI layer needs [assistant] base_url and model")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
    import aiohttp

    async def round_trip():
        for n in range(cfg["max_rounds"] + 1):
            last = n == cfg["max_rounds"]   # the rounds of tools are used up: this request is for the answer
            body = {"model": cfg["model"], "messages": messages, "tools": openai_tools()}
            if last:
                body["tool_choice"] = "none"
            trace["rounds"] += 1
            try:
                async with session.post(url, json=body, headers=headers) as r:
                    if r.status in (401, 403):
                        raise AIError("ai_error", f"the AI provider refused the key (HTTP {r.status})")
                    if r.status >= 400:
                        raise AIError("ai_error", f"the AI provider answered HTTP {r.status}")
                    d = await r.json(content_type=None)
            except aiohttp.ClientError as e:
                raise AIError("ai_error", f"the AI provider cannot be reached ({type(e).__name__})") from e
            except ValueError as e:
                raise AIError("ai_error", "the AI provider's answer was not JSON") from e
            try:
                msg = d["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                raise AIError("ai_error", "the AI provider's answer had no message") from None
            # every step's shape checked (review R4): a provider's odd answer is ai_error, never a crash
            if not isinstance(msg, dict):
                raise AIError("ai_error", MALFORMED)
            calls = msg.get("tool_calls") or []
            if not isinstance(calls, list) or not all(isinstance(c, dict) and isinstance(c.get("function") or {}, dict) for c in calls):
                raise AIError("ai_error", MALFORMED)
            content = message_text(msg.get("content"))
            if not calls:
                words = content.strip()
                if not words:
                    raise AIError("ai_error", "the AI gave no answer")
                return words
            if last:   # asked for more tools anyway (a provider that ignores tool_choice): none run (Codex F7)
                break
            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            for c in calls:
                fn = c.get("function") or {}
                trace["tools"].append(str(fn.get("name")))
                out = await tools.call(str(fn.get("name")), call_arguments(fn), get, rows)
                messages.append({"role": "tool", "tool_call_id": c.get("id"), "name": fn.get("name"),
                                 "content": json.dumps(out, separators=(",", ":"))})
        raise AIError("ai_error", f"the AI was still calling tools after {cfg['max_rounds']} rounds")

    try:
        return await asyncio.wait_for(round_trip(), cfg["timeout"])
    except asyncio.TimeoutError:
        raise AIError("ai_timeout", f"the AI took longer than {cfg['timeout']:g} s") from None
