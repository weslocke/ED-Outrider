"""Known surface sites from Canonn (the pins follow-up, the author 2026-10-26): the Guardian ruins and structures and the
geology other commanders reported on a body, each one tap from a pin in the body panel's Pins section. Asked at
runtime from Canonn's cloud functions (the same service as the checklists' pictures), only the request: nothing
about you is sent. Pure: the server hands in the answers.

    guardian_sites(rows, body_id, radius_km) -> [{kind: "guardian", name, lat, lon}]   (GET SETTLEMENT_URL)
    geology_sites(poi, short)                -> [{kind: "geology", name, n, points: [[lat, lon]...]}]   (GET POI_URL)

Canonn's older sites API (api.canonn.tech: Guardian, Thargoid and crash-site tables) no longer answers (checked
2026-10-26); wrecks and Thargoid sites have no live source, so they stay pins you place yourself.
"""
import math
import re

BASE = "https://us-central1-canonn-api-236217.cloudfunctions.net/query"
SETTLEMENT_URL = BASE + "/settlement/{}"   # a system's ApproachSettlement reports: {bodyid, name, lat, lon, market_id}
POI_URL = BASE + "/getSystemPoi"           # ?system=<name>&odyssey=Y: codex reports with positions, among other things
MERGE_M = 200          # reports of one Guardian site this close together are one site (other languages, a few metres)
GEO_POINTS_MAX = 40    # a formation's reported positions kept (the page pins the nearest to you)
DEFAULT_RADIUS_KM = 1500   # a body's radius when neither your scan nor Spansh gives one (for the merge distance only)
# the game's own names: "$Ancient:#index=2;" a ruin, "$Ancient_Small_001:#index=1;" a structure ("None": an old client)
ANCIENT = re.compile(r"^\$Ancient(?:_(Tiny|Small|Medium|Huge)_\d+)?:#index=(\d+|None);$")
# a ruin reported by a client in another language carries only its localised name
RUINS_WORDS = {"ancient ruins", "antike ruinen", "ruines anciennes", "ruinas antiguas", "ruínas antigas", "древние руины"}


def _num(v, lim):
    """A coordinate from Canonn's answer (a string or a number), or None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and -lim <= x <= lim else None


def _metres(a, b, radius_km):
    """The great-circle distance in metres between two [lat, lon]."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * radius_km * 1000 * math.asin(min(1.0, math.sqrt(h)))


def _guardian_name(name):
    """(sort key, words) for a Guardian report's name, or None when it is not one (a human settlement, anything else)."""
    m = ANCIENT.match(name)
    if m:
        size, index = m.group(1), m.group(2)
        i = int(index) if index != "None" else None
        key = (1 if size else 0, size or "", 999 if i is None else i)
        # a structure is nearly always index 1: numbered only from 2
        return (key, f"Guardian structure ({size.lower()}){f' {i}' if i and i > 1 else ''}") if size \
            else (key, f"Guardian ruins{'' if i is None else f' {i}'}")
    if name.strip().lower() in RUINS_WORDS:
        return (0, "", 999), "Guardian ruins"
    return None


def guardian_sites(rows, body_id, radius_km=None):
    """Canonn's settlement reports on body `body_id` (its BodyID) as Guardian sites, one per place: reports within
    MERGE_M of each other are one site, named by the game's own name when one of them has it (an "Ancient Ruins"
    from another language takes the ruin's number). Human settlements (a market id) and other names are left out.
    Raises ValueError for an answer that is not a list (an error object)."""
    if not isinstance(rows, list):
        raise ValueError("Canonn answered in an unexpected shape")
    radius = radius_km if isinstance(radius_km, (int, float)) and radius_km > 0 else DEFAULT_RADIUS_KM
    groups = []   # [{key, name, own (the game's own name), lat, lon}]
    for r in rows:
        if not isinstance(r, dict) or r.get("bodyid") != body_id or r.get("market_id") is not None or not isinstance(r.get("name"), str):
            continue
        named, lat, lon = _guardian_name(r["name"]), _num(r.get("lat"), 90), _num(r.get("lon"), 180)
        if not named or lat is None or lon is None:
            continue
        own = r["name"].startswith("$")
        g = next((g for g in groups if _metres((g["lat"], g["lon"]), (lat, lon), radius) <= MERGE_M), None)
        if g is None:
            groups.append({"key": named[0], "name": named[1], "own": own, "lat": lat, "lon": lon})
        elif own and not g["own"]:   # the game's own name (and its position) over a localised one
            g.update(key=named[0], name=named[1], own=True, lat=lat, lon=lon)
    groups.sort(key=lambda g: (g["key"], g["lat"], g["lon"]))
    return [{"kind": "guardian", "name": g["name"], "lat": round(g["lat"], 6), "lon": round(g["lon"], 6)} for g in groups]


def geology_sites(poi, short):
    """The geology Canonn has positions for on body `short` (its name without the system's), one entry per formation
    with its reported positions (GEO_POINTS_MAX, the first ones reported), most reported first. Reports with no
    position are left out. Raises ValueError for an answer of another shape (every answer names its system: an error
    object does not)."""
    if not isinstance(poi, dict) or "system" not in poi or not isinstance(poi.get("codex") or [], list):
        raise ValueError("Canonn answered in an unexpected shape")   # a codex not a list too (review 8: it raised a 500)
    out = {}
    for c in poi.get("codex") or []:
        if not isinstance(c, dict) or c.get("hud_category") != "Geology" or c.get("body") != short:
            continue
        name, lat, lon = c.get("english_name"), _num(c.get("latitude"), 90), _num(c.get("longitude"), 180)
        if not isinstance(name, str) or not name.strip() or lat is None or lon is None:
            continue
        e = out.setdefault(name.strip(), {"kind": "geology", "name": name.strip(), "n": 0, "points": []})
        e["n"] += 1
        if len(e["points"]) < GEO_POINTS_MAX:
            e["points"].append([round(lat, 6), round(lon, 6)])
    return sorted(out.values(), key=lambda e: (-e["n"], e["name"]))
