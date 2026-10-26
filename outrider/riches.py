"""The survey slot's routes: Road to Riches (spansh.co.uk/riches), Expressway to Exomastery (spansh.co.uk/exobiology),
Earth-like, ammonia and terraformable worlds (spansh.co.uk/earth, /ammonia, /rocky: the Road to Riches router for body types), a sweep
(spansh.co.uk/tourist: ticked systems in the order to fly them) and a trade route (outrider/cargo.py). `SURVEY_KINDS`
holds what differs by kind; the rest is shared: Spansh's answer as route rows, which row a system is, which of a
system's bodies (or species) are still to do, and the lines said on arriving. Exomastery's answer is Road to Riches'
layout with each body's species added (`landmarks`: {type: genus, subtype: species, value, count}, and
`landmark_value`): bodies where life is already reported, so the values are base values (first footfall is unlikely).
Pure helpers: the route's state, its tables and the plot under way live in ed_outrider.State, as the Neutron Highway's
do (outrider/highway.py).

Spansh publishes no description of this API. Checked against the live site on 2026-10-06 (tests/fixtures/
spansh_riches.json is that answer, trimmed): POST /api/riches/route with form fields, then /api/results/{job}; each
system has name, id64, x, y, z, jumps and bodies, each body name, type, subtype, distance_to_arrival,
estimated_scan_value, estimated_mapping_value, is_terraformable and id64 (a string). scripts/riches_probe.py checks it
again; scripts/route_probe.py the worlds' and the tourist router's (2026-10-13). Fields are read leniently: a missing field is a missing value, a body or system that is not a dict or has no
name is skipped, and an answer with no usable system is a RichesError."""
import math
import re
from dataclasses import dataclass

from outrider.cargo import trade_rows, trade_text
from outrider.highway import number_words

RICHES_MAX_SYSTEMS = 2000   # a route longer than this is refused (Spansh's own cap is far lower)
RICHES_MAX_BODIES = 300     # bodies kept per system
SWEEP_MAX = 100             # systems a sweep takes (S51: Spansh's tourist router publishes no cap; a trip, not a list)


@dataclass(frozen=True)
class SurveyKind:
    """One kind of route the survey slot holds (G4 / the review's F4): every place that differs by kind reads it here
    (the plot, its answer, what a stop asks of you, the lines, the alert, the overlay; page.js `SURVEY` is the page's
    copy, kept in step by a test)."""
    name: str            # its name: the line's glyph title, the overlay, the tab's switch
    glyph: str
    what: str            # the route as "Plot (replaces your …)" and the Map's legend name it
    a: str               # as "Asking Spansh for …" and "Plotted: …" say it
    url: str             # the Spansh endpoint: the NAME of ed_outrider's constant (verify.sh and the tests patch those)
    parser: str          # its answer as rows: "riches" (riches_rows), "tourist" (tourist_rows), "trade" (cargo.trade_rows)
    work: str | None     # what a stop asks of you: "bodies" (scan, and map), "species" (sample), "trade", None (arrive)
    alert: str           # the moments' kind: the page's alerts row (and its sound, notification and speech switches)
    complete: str        # said at its end
    left: tuple          # (one, many, what): "2 bodies to do here"
    fields: tuple = ()   # the plot's options taken from the request, checked, kept with the route and sent to Spansh
    send: tuple = ()     # fixed (field, value) pairs sent as well (a value that is a tuple: a repeated form field)
    mapping: bool | None = None   # whether a body needs its map too: None as the route's use_mapping_value says


_SURVEY_FIELDS = ("radius", "max_results", "max_distance", "min_value", "use_mapping_value", "avoid_thargoids", "loop")
# Earth-like and ammonia worlds (S52, probe P3/U3 2026-10-13: tests/fixtures/spansh_body_types.json): Spansh's own pages
# ask the Road to Riches router for one body type with min_value 1 (there is no /api/earth/route or /api/ammonia/route),
# and its answer is Road to Riches'. Their worth is the map, so the map always counts
_WORLD_FIELDS = ("radius", "max_results", "max_distance", "avoid_thargoids", "loop")
SURVEY_KINDS = {
    "riches": SurveyKind("Road to Riches", "💰", "Road to Riches route", "a Road to Riches route", "SPANSH_RICHES", "riches",
                         "bodies", "riches", "Road to Riches complete.", ("body", "bodies", "to do here"), _SURVEY_FIELDS),
    # Exomastery: the plot form shows no Thargoid box, but the server has always sent its default
    "exo": SurveyKind("Exomastery", "🧬", "Exomastery route", "an Exomastery route", "SPANSH_EXO", "riches", "species", "exo",
                      "Exomastery complete.", ("species", "species", "to sample here"),
                      tuple(f for f in _SURVEY_FIELDS if f != "use_mapping_value")),
    "elw": SurveyKind("Earth-like worlds", "🌍", "Earth-like route", "an Earth-like world route", "SPANSH_RICHES", "riches",
                      "bodies", "riches", "Earth-like route complete.", ("body", "bodies", "to do here"), _WORLD_FIELDS,
                      (("min_value", 1), ("body_types", ("Earth-like world",))), True),
    "aw": SurveyKind("Ammonia worlds", "🧪", "ammonia route", "an ammonia world route", "SPANSH_RICHES", "riches", "bodies",
                     "riches", "Ammonia route complete.", ("body", "bodies", "to do here"), _WORLD_FIELDS,
                     (("min_value", 1), ("body_types", ("Ammonia world",))), True),
    # Terraformable rocky and high metal content worlds (NEXT-VERSION #18, the author 2026-10-17; probe 2026-10-17:
    # tests/fixtures/spansh_body_types.json "tf"): Spansh's Rocky/HMC page asks for both body types with min_value 1,
    # which answers every rocky body (2 thousand mapped) and plain HMC (50 thousand) too. Spansh tests min_value
    # against the SCAN value: terraformables scan for 127 to 186 thousand, plain HMC under 20: TF_MIN_VALUE keeps the
    # terraformables alone (300 thousand answered nothing)
    "tf": SurveyKind("Terraformable worlds", "🪨", "terraformable route", "a terraformable world route", "SPANSH_RICHES",
                     "riches", "bodies", "riches", "Terraformable route complete.", ("body", "bodies", "to do here"),
                     _WORLD_FIELDS, (("min_value", 100_000), ("body_types", ("Rocky body", "High metal content world"))), True),
    # S51: the ticked systems of Left behind, My firsts and Bookmarks in the order Spansh's tourist router flies them
    # (probe P2/U2 2026-10-13: tests/fixtures/spansh_tourist.json); arriving is the whole of a stop
    "sweep": SurveyKind("Sweep", "🧹", "sweep", "a sweep", "SPANSH_TOURIST", "tourist", None, "riches", "Sweep complete.",
                        ("stop", "stops", "here"), ("loop",)),
    "trade": SurveyKind("Trade route", "💱", "trade route", "a trade route", "SPANSH_TRADE", "trade", "trade", "trade",
                        "Trade route complete.", ("trade", "trades", "to make here")),
}


def survey_kind(kind):
    """The SurveyKind of a route's kind (a route stored before kinds were named is Road to Riches)."""
    return SURVEY_KINDS.get(kind) or SURVEY_KINDS["riches"]


def kind_of(rc):
    """The survey slot's route kind from its meta (None: Road to Riches, as before kinds were stored)."""
    k = (rc or {}).get("kind") or "riches"
    return k if k in SURVEY_KINDS else "riches"


def left_words(kind, n):
    """What is left where you are, in words: "2 bodies to do here", "3 species to sample here"."""
    one, many, what = survey_kind(kind).left
    return f"{n} {one if n == 1 else many} {what}"


def survey_mapping(kind, options):
    """Whether a body of this route needs its map as well as its scan."""
    m = survey_kind(kind).mapping
    return bool((options or {}).get("use_mapping_value")) if m is None else m


def survey_rows(kind, result):
    """Spansh's answer for a route of this kind as the slot's rows ([] for a trade answer that is no route). A body
    route with no body anywhere is refused: from inside the bubble (Sol, Lave) Spansh answers the start system alone
    (probed 2026-10-26), which stored would be a route already complete."""
    parser = survey_kind(kind).parser
    if parser == "trade":
        return trade_rows(result)
    if parser == "tourist":
        return tourist_rows(result)
    rows = riches_rows(result)
    if not any(r["bodies"] for r in rows):
        raise RichesError("Spansh found nothing to visit with those settings: try starting further out from the bubble, "
                          "a larger radius or a lower minimum value")
    return rows


class RichesError(Exception):
    """A plot that failed, or an answer that cannot be used, in words for the page."""


def _num(v, conv=float):
    """A number from Spansh's answer, or None (a missing or broken field)."""
    try:
        out = conv(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if not isinstance(out, float) or math.isfinite(out) else None


def norm_name(name):
    """A body or system name as compared: spaces collapsed, case folded."""
    return " ".join(name.split()).casefold() if isinstance(name, str) else ""


def riches_rows(result):
    """Spansh's finished route as a list of systems (dicts), in route order. Each: {system, id64, x, y, z, jumps,
    bodies: [{name, type, subtype, ls, scan, map, terraformable, body_id}]}. `result` is the list itself or a dict
    holding it under "result" or "systems". Bodies without a name are dropped; a system without one is skipped."""
    if isinstance(result, dict):
        result = result.get("result") if isinstance(result.get("result"), list) else result.get("systems")
    if not isinstance(result, list):
        raise RichesError("Spansh sent a route in a shape Outrider does not know")
    rows = []
    for s in result:
        if not isinstance(s, dict):
            continue
        name = s.get("name") if isinstance(s.get("name"), str) else s.get("system")
        if not isinstance(name, str) or not name.strip():
            continue
        id64 = _num(s.get("id64"), int)
        bodies = []
        for b in (s.get("bodies") if isinstance(s.get("bodies"), list) else [])[:RICHES_MAX_BODIES]:
            if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b["name"].strip():
                continue
            bid = _num(b.get("id64"), int)
            bodies.append({
                "name": " ".join(b["name"].split()), "type": b.get("type") if isinstance(b.get("type"), str) else None,
                "subtype": b.get("subtype") if isinstance(b.get("subtype"), str) else None,
                "ls": _num(b.get("distance_to_arrival")),
                "scan": _num(b.get("estimated_scan_value"), int), "map": _num(b.get("estimated_mapping_value"), int),
                "terraformable": 1 if b.get("is_terraformable") or b.get("terraforming_state") in ("Candidate for terraforming", "Terraformable")
                else 0,
                # the game's BodyID, as body_id is everywhere else: a body id64's top 9 bits
                "body_id": bid >> 55 if bid is not None and 0 <= bid < 2 ** 64 else None,
                # Exomastery: the species Spansh lists on it (none on a Road to Riches body)
                "species": _species(b.get("landmarks"))})
        rows.append({"system": name.strip(), "id64": id64 if id64 is not None and 0 <= id64 < 2 ** 63 else None,
                     "x": _num(s.get("x")), "y": _num(s.get("y")), "z": _num(s.get("z")),
                     "jumps": max(0, _num(s.get("jumps"), int) or 0) if rows else 0, "bodies": bodies})
    if not rows:
        raise RichesError("Spansh found no route with those settings: try a larger radius or a lower minimum value")
    if len(rows) > RICHES_MAX_SYSTEMS:
        raise RichesError(f"a route of {len(rows)} systems is longer than Outrider keeps ({RICHES_MAX_SYSTEMS})")
    return rows


def splice_survey(rows, reach, start=None, end=None):
    """A survey route plotted between stand-ins (systems Spansh knows, for ends it does not know yet) with the real ends
    put back: `start` before the first system and `end` after the last ({system, id64, x, y, z}), nothing to survey in
    either, each `reach`'s jumps from its stand-in."""
    rows = [dict(r) for r in rows]

    def jumps(a, b):
        d = math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
        return max(1, math.ceil(d / reach)) if reach else 1
    if end:
        rows.append(dict(end, jumps=jumps(rows[-1], end), bodies=[]))
    if start:
        rows[0] = dict(rows[0], jumps=jumps(start, rows[0]))
        rows.insert(0, dict(start, jumps=0, bodies=[]))
    return rows


def _species(landmarks):
    """A body's `landmarks` (Exomastery) as [{genus, species, value, count}], best first; lenient (a broken entry
    is skipped)."""
    out = []
    for x in landmarks if isinstance(landmarks, list) else []:
        if not isinstance(x, dict) or not isinstance(x.get("subtype"), str) or not x["subtype"].strip():
            continue
        out.append({"genus": x["type"].strip() if isinstance(x.get("type"), str) else None,
                    "species": " ".join(x["subtype"].split()), "value": _num(x.get("value"), int),
                    "count": _num(x.get("count"), int)})
    return sorted(out, key=lambda x: -(x["value"] or 0))


def riches_match(rows, id64, name, near=0):
    """The route row a system is, or None: by id64 (by name when a row has none). A system on the route twice gives
    the occurrence at or after `near` (where you were), else the latest before it."""
    low = norm_name(name)
    hits = [i for i, r in enumerate(rows)
            if (r["id64"] == id64 if r["id64"] is not None and id64 is not None else norm_name(r["system"]) == low)]
    if not hits:
        return None
    ahead = [i for i in hits if i >= near]
    return ahead[0] if ahead else hits[-1]


def body_value(body, mapping):
    """What a body is worth to Spansh's estimate: the scan, plus the map when `mapping`. None when it has no figure."""
    scan, mapped = body.get("scan"), body.get("map")
    if scan is None and (mapped is None or not mapping):
        return None
    return (scan or 0) + ((mapped or 0) if mapping else 0)


def todo(bodies, scanned, mapped, mapping):
    """The bodies of a system still to do: not scanned, or (with `mapping`) not mapped. `scanned` and `mapped` are
    sets of norm_name'd body names read from the journal (the player's own record). Each body gains `scanned` and
    `mapped` flags; the list keeps Spansh's order."""
    out = []
    for b in bodies:
        key = norm_name(b["name"])
        out.append(dict(b, scanned=key in scanned, mapped=key in mapped,
                        done=(key in scanned) and (key in mapped or not mapping)))
    return out


def money(n):
    """A credit amount as said aloud: 1.2 million, 800 thousand."""
    if n is None:
        return None
    if n >= 999_500:   # rounds to a million: "1 million", never "1000 thousand"
        v = round(n / 1_000_000, 1)
        return f"{v:g} million"
    if n >= 1000:
        return f"{round(n / 1000):d} thousand"
    return str(int(n))


def had_work(kind, row):
    """Whether a survey route row came with work to do (S12): bodies (Road to Riches, the worlds' routes); a body with
    species (Exomastery). A row without (a route's real end carries `bodies: []`) is never skipped as finished. Trade
    routes and sweeps never skip."""
    work = survey_kind(kind).work
    if work == "species":
        return any(b.get("species") for b in row.get("bodies") or [])
    return work == "bodies" and bool(row.get("bodies"))


def next_stop(rows, i, skip=0):
    """The next stop after row i in words, `skip` finished rows passed over on the way (S12): "Next stop: X." or
    "Next stop: X, skipping 2 systems you've finished."."""
    nxt = rows[i + 1 + skip]["system"]
    return f"Next stop: {nxt}" + (f", skipping {skip} system{'' if skip == 1 else 's'} you've finished." if skip else ".")


def riches_text(rows, i, left, skip=0, complete="Road to Riches complete."):
    """The line said on arriving at route row i: how many bodies are worth the stop and what they are, then where
    next. `left` is the system's bodies still to do (todo() output, not done); `skip` the finished rows after i the
    next stop passes over (S12); `complete` the kind's end. Plain words (the page's personality lines can replace them
    later). A sweep's stops have no bodies: only where next."""
    here = rows[i]
    last = i + skip >= len(rows) - 1
    if not left:
        return (f"Nothing left to do in {here['system']}. " if here["bodies"] else "") + (
            complete if last else next_stop(rows, i, skip))
    n = len(left)
    best = max(left, key=lambda b: b.get("scan") or 0)
    what = best.get("subtype") or best.get("type") or "body"
    val = money(best.get("scan"))
    text = f"{number_words(n).capitalize()} {'body' if n == 1 else 'bodies'} here" if n < 11 else f"{n} bodies here"
    text += f": the best is a {what.lower()}" + (f", about {val} credits" if val else "")
    if best.get("ls") is not None:
        text += f", {round(best['ls']):d} light seconds out"
    return text + "."


def exo_todo(bodies, sampled):
    """Exomastery: the bodies with their species marked `done` (a completed sample of it on that body: `sampled` is a
    set of (BodyID, species name lower-cased) from the journal), each body `done` once all its species are, and
    `left` (its species not done)."""
    out = []
    for b in bodies:
        sp = [dict(x, done=(b.get("body_id"), x["species"].lower()) in sampled) for x in b.get("species") or []]
        left = [x for x in sp if not x["done"]]
        out.append(dict(b, species=sp, left=len(left), done=bool(sp) and not left))
    return out


def exo_left(bodies, sampled):
    """The species still to sample in a system: [(body, species)], best first."""
    return sorted(((b, x) for b in exo_todo(bodies, sampled) for x in b["species"] if not x["done"]),
                  key=lambda bx: -(bx[1]["value"] or 0))


def body_short(name, system):
    """A body's name without its system's ("Eol Prou PX-T d3-813 ABC 2 e" -> "ABC 2 e")."""
    return name[len(system) + 1:] if name.lower().startswith(system.lower() + " ") else name


def exo_text(rows, i, left, skip=0, complete="Exomastery complete."):
    """The line said on arriving at an Exomastery route row: how many species on how many bodies are left to sample,
    the best of them and its body, then nothing more (the next stop is said once they are sampled). `left` is
    exo_left()'s, `skip` and `complete` as riches_text's. Plain words, as riches_text."""
    here = rows[i]
    last = i + skip >= len(rows) - 1
    if not left:
        return (f"Every species in {here['system']} is sampled. " if any(b.get("species") for b in here["bodies"]) else "") + (
            complete if last else next_stop(rows, i, skip))
    n, bodies = len(left), len({b["name"] for b, _x in left})
    b, best = left[0]
    words = lambda k, one, many: f"{number_words(k) if k < 11 else k} {one if k == 1 else many}"
    text = f"{words(n, 'species', 'species').capitalize()} on {words(bodies, 'body', 'bodies')} here: the best, {best['species']}"
    text += f" on {body_short(b['name'], here['system'])}"
    val = money(best.get("value"))
    return text + (f", about {val} credits." if val else ".")


def arrival_text(kind, rows, i, left, skip=0):
    """The line said on arriving at route row i of a route of this kind (riches_text, exo_text, cargo.trade_text)."""
    k = survey_kind(kind)
    if k.work == "trade":
        return trade_text(rows, i, left)
    return (exo_text if k.work == "species" else riches_text)(rows, i, left, skip, k.complete)


def done_text(kind, rows, i, skip=0):
    """Said once the last of route row i's work is done: that, then the next stop (`skip` finished rows passed over),
    or the end of the route at its last row."""
    k = survey_kind(kind)
    head = "Every species here is sampled. " if k.work == "species" else "Everything here is done. "
    return head + (k.complete if i == len(rows) - 1 else next_stop(rows, i, skip))


def tourist_rows(result):
    """Spansh's tourist route (S51, a sweep) as the slot's rows: `system_jumps`, the start then each system to visit in
    the order to fly them, each with its jumps from the one before ({system, id64, x, y, z, jumps, bodies: []}; a loop
    ends back at the start). `result` is the result dict or the list itself. A RichesError when nothing usable came."""
    sj = result.get("system_jumps") if isinstance(result, dict) else result
    if not isinstance(sj, list):
        raise RichesError("Spansh sent a sweep in a shape Outrider does not know")
    rows = []
    for s in sj:
        name = s.get("system") if isinstance(s, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        id64 = _num(s.get("id64"), int)
        rows.append({"system": " ".join(name.split()), "id64": id64 if id64 is not None and 0 <= id64 < 2 ** 63 else None,
                     "x": _num(s.get("x")), "y": _num(s.get("y")), "z": _num(s.get("z")),
                     "jumps": max(0, _num(s.get("jumps"), int) or 0) if rows else 0, "bodies": []})
    if len(rows) < 2:
        raise RichesError("Spansh found no sweep through those systems")
    if len(rows) > RICHES_MAX_SYSTEMS:
        raise RichesError(f"a route of {len(rows)} systems is longer than Outrider keeps ({RICHES_MAX_SYSTEMS})")
    return rows


def unknown_systems(error, names):
    """The names of a sweep's systems Spansh refused not knowing (its "Could not find destination systems [A, B]", as
    probed), out of `names`; [] for any other error."""
    m = re.search(r"Could not find destination systems \[(.*)\]", error or "")
    if not m:
        return []
    said = {norm_name(x) for x in m.group(1).split(", ")}
    return [n for n in names if norm_name(n) in said] or [n for n in names if n in m.group(1)]
