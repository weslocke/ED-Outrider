#!/usr/bin/env python3
"""
outrider/bio.py -- Which exobiology species can a planet host, and what are they worth?

The game only spawns each species inside known bands of planet class, atmosphere, gravity,
surface temperature, pressure and volcanism, and some care about the stars in the system, the
galactic region, or whether you are inside a nebula. Given a body's scan data (and a little
about its system) this module lists the species that could be there, grouped by genus with the
most valuable candidate first, so you know before you drop a probe whether a body's bio
signals might be a 19M Stratum Tectonicas or a 1M Bacterium Aurasus.

On top of the spawn rules it applies BioScan's colour check: each species' colour variants depend on
the class of star the body orbits (or, for some genera, on a surface material), so a species with no
variant for this body's star or materials has never been seen in such a place and is ruled out --
Stratum, for instance, has no variant for a G star. When the stars or materials are not known nothing
is ruled out on that account. The colour tables come from EDMC-ExploData
(https://github.com/Silarn/EDMC-ExploData, GPL-2.0: its repository carries the version 2 text): they are downloaded
into resources/bio_colours.json on the first start and refreshed with the rules, never shipped. The colony distances
(COLONY_DISTANCE) are the game's own: the Genetic Sampler shows them.

The spawn conditions are the community's work, maintained in the BioScan plugin for EDMC
(https://github.com/Silarn/EDMC-BioScan, GPL-2.0-or-later), with the galactic region map from
https://github.com/klightspeed/EliteDangerousRegionMap (MIT): both ship in resources/bio_rules.json, which ED Outrider
refreshes on each start when upstream has changed (`--update-rules` does it by hand).

    python3 -m outrider.bio --update-rules     fetch the latest spawn rules
    python3 -m outrider.bio --backtest         check the rules against your own journals
    python3 -m outrider.bio --body '{"class":"Rocky body","atmosphere":"Ammonia","gravity":0.15,"temperature":170}'

A prediction is a possibility, not a promise: the genus is usually reliable, the species within
it (which sets the value) often depends on things the scan does not tell you, so several
species of one genus are commonly listed together. The backtest prints how often your own
finds were on the list.

Body dict used by predict():
    class         journal PlanetClass or Spansh subtype ("Rocky body", "High metal content world")
    atmosphere    journal AtmosphereType ("CarbonDioxide") or Spansh ("Thin Carbon dioxide")
    gravity       g
    temperature   K
    pressure      atmospheres (optional)
    volcanism     journal Volcanism string or Spansh volcanismType ("" or "No volcanism" for none;
                  None or missing when not known, which rules nothing out)
    dist_ls       distance from arrival
    orbital_period_s  seconds (optional; only Sinuous Tubers care)
    atmosphere_composition  {"SulphurDioxide": 1.2, ...} percentages (optional; Recepta care)
    parents       star types of the stars this body orbits, journal codes (optional; leave it out when
                  any of them is not known)
    star          arrival star type (journal code) -- used when `system` gives no stars
    materials     surface materials, lower case ("iron", "polonium", ...) (optional; colour check)

System dict (optional second argument; everything in it is optional too):
    name, x, y, z   coordinates decide the region, nebulae and Guardian/tuber zones
    region          region number 1-42 if you already know it (else derived from x, y, z)
    stars           [{"type": "M", "luminosity": "Va", "main": True}, ...]
    planet_types    PlanetClass of every planet in the system (some species need e.g. a water world);
                    leave it out unless every planet there is known
    complete        True when every body in the system is known (a lone known star is then the one
                    a body orbits)
"""

from __future__ import annotations

import argparse
import ast
import collections
import datetime as dt
import functools
import json
import math
import os
import re
import urllib.request
from glob import glob, escape as glob_escape

try:
    from .unsold import ORGANIC_VALUES, find_journal_dirs
except ImportError:  # standalone use without the price table
    ORGANIC_VALUES = {}
    find_journal_dirs = None

from . import RESOURCES_DIR  # noqa: E402

RULES_FILE = os.path.join(RESOURCES_DIR, "bio_rules.json")
# ExploData's colour tables are kept apart, in bio_colours.json beside the rules (git- and docker-ignored): downloaded on
# the first start and refreshed with the rules, never shipped (its repository carries the GPL v2 text without "or
# later"; the author, 2026-10-10). The shipped bio_rules.json has every species' "colors" None.
COLOURS_NAME = "bio_colours.json"


def colours_path(rules_path=None):
    """The colour tables' file beside a rules file."""
    return os.path.join(os.path.dirname(rules_path or RULES_FILE), COLOURS_NAME)

BIOSCAN = "https://raw.githubusercontent.com/Silarn/EDMC-BioScan/master/src/bio_scan/"
BIOSCAN_API = "https://api.github.com/repos/Silarn/EDMC-BioScan/"
BIOSCAN_PATHS = ["src/bio_scan/bio_data", "src/bio_scan/nebula_data"]  # the parts we take
REGIONMAP = "https://raw.githubusercontent.com/klightspeed/EliteDangerousRegionMap/master/RegionMapData.py"
# Colour variants per species, by parent star class or surface material: BioScan also uses these to rule a
# species out (never seen around that kind of star / without those materials), e.g. Stratum at a G star.
EXPLODATA_PATH = "src/ExploData/explo_data/bio_data/genus.py"
EXPLODATA = "https://raw.githubusercontent.com/Silarn/EDMC-ExploData/master/" + EXPLODATA_PATH
EXPLODATA_API = "https://api.github.com/repos/Silarn/EDMC-ExploData/"
REGIONMAP_API = "https://api.github.com/repos/klightspeed/EliteDangerousRegionMap/"
RULESET_FILES = ["aleoida", "anemone", "bacterium", "brain_tree", "cactoida", "clypeus", "concha", "electricae",
                 "fonticulua", "frutexa", "fumerola", "fungoida", "osseus", "recepta", "shard", "stratum",
                 "tubers", "tubus", "tussock"]  # used if the GitHub directory listing is unavailable

# The DSS's genus names for the Horizons life forms (the Odyssey ones are the species' first word).
GENUS_NAMES = {
    "$Codex_Ent_Brancae_Name;": "Brain Trees", "$Codex_Ent_Sphere_Name;": "Anemone",
    "$Codex_Ent_Tube_Name;": "Sinuous Tubers", "$Codex_Ent_Ground_Struct_Ice_Name;": "Crystalline Shards",
    "$Codex_Ent_Cone_Name;": "Bark Mounds", "$Codex_Ent_Vents_Name;": "Amphora Plant",
    "$Codex_Ent_Ingensradices_Genus_Name;": "Radicoida",
}

# Region map origin (klightspeed's RegionMap.py): the grid has 83 cells per 4096 ly.
REGION_ORIGIN = (-49985, -40985, -24105)

# --------------------------------------------------------------------------
# Normalisation of the different spellings the journal and Spansh use
# --------------------------------------------------------------------------

LANDABLE = {
    "rocky body": "Rocky body", "high metal content body": "High metal content body",
    "high metal content world": "High metal content body",
    "icy body": "Icy body", "rocky ice body": "Rocky ice body", "rocky ice world": "Rocky ice body",
    "metal rich body": "Metal rich body", "metal-rich body": "Metal rich body",
}
OTHER_PLANETS = {
    "earth-like world": "Earthlike body", "earthlike body": "Earthlike body",
    "gas giant with water-based life": "Gas giant with water based life",
    "gas giant with ammonia-based life": "Gas giant with ammonia based life",
}
STAR_NAMES = {  # Spansh subtype -> journal StarType, where the first word is not the code
    "Neutron Star": "N", "Black Hole": "H", "Supermassive Black Hole": "SupermassiveBlackHole",
    "T Tauri Star": "TTS", "Herbig Ae/Be Star": "AeBe", "Wolf-Rayet Star": "W", "MS-type Star": "MS",
    "S-type Star": "S",
}
GIANTS = {"super giant": "SuperGiant", "giant": "Giant"}
COLOURS = {"A": "BlueWhite", "B": "BlueWhite", "F": "White", "G": "White", "K": "Orange", "M": "Red"}


def journal_class(c):
    """Planet class in the journal's spelling, whichever spelling came in."""
    k = (c or "").strip().lower()
    return LANDABLE.get(k) or OTHER_PLANETS.get(k) or (c or "").strip()


def landable_class(c):
    return LANDABLE.get((c or "").strip().lower())


def norm_atmosphere(a):
    """'CarbonDioxide', 'Thin Carbon dioxide', 'carbon dioxide-rich' -> 'carbondioxide' / 'carbondioxiderich'."""
    a = (a or "").strip().lower()
    if a in ("", "none", "no atmosphere"):
        return "none"
    a = re.sub(r"^((thin|thick|hot)\s+)+", "", a)
    a = re.sub(r"\s+atmosphere$", "", a)
    return re.sub(r"[\s\-]", "", a)


def norm_volcanism(v):
    """Journal form: '' for none, else e.g. 'major silicate vapour geysers volcanism'."""
    v = (v or "").strip().lower()
    if v in ("", "none", "no volcanism"):
        return ""
    return v if v.endswith(" volcanism") else v + " volcanism"


def star_code(s):
    """Journal StarType code from either a code ('M', 'DA', 'M_RedGiant') or a Spansh name
    ('M (Red giant) Star', 'White Dwarf (DA) Star')."""
    s = (s or "").strip()
    if not s or " " not in s:
        return s or None
    if s in STAR_NAMES:
        return STAR_NAMES[s]
    m = re.match(r"^White Dwarf \((\w+)\)", s)
    if m:
        return m.group(1)
    m = re.match(r"^Wolf-Rayet (\w+) Star$", s)
    if m:
        return "W" + m.group(1)
    m = re.match(r"^([A-Z]+)(?:-type)? (?:\(([^)]*)\) )?Star$", s)
    if not m:
        return s
    code, detail = m.group(1), (m.group(2) or "").lower()
    for word, suffix in GIANTS.items():
        if detail.endswith(word) and code in COLOURS:
            return f"{code}_{COLOURS[code]}{suffix}"
    return code


def star_matches(query, code):
    """BioScan's star_check: a class letter also covers its giant variants."""
    if not code:
        return False
    if query == "Ae":   # the colour tables' Herbig code; the journal's is AeBe
        return code.startswith("Ae")
    if query in ("A", "B", "F", "G", "K", "M"):
        return code == query or code.startswith(query + "_")
    if query in ("D", "C", "W"):
        return code.startswith(query)
    return code == query


def luminosity_matches(want, have):
    return bool(have) and any(want + flag == have for flag in ("", "a", "b", "ab", "z"))


# --------------------------------------------------------------------------
# Fetching the rules
# --------------------------------------------------------------------------

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ED-Outrider outrider.bio"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def _literals(source, failed=None):
    """Every top-level `name = <literal>` in a Python source file, without importing it. The names assigned something
    that is not a pure literal go into `failed` (a list), when given."""
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        else:
            continue
        try:
            out[name] = ast.literal_eval(value)
        except ValueError:
            if failed is not None:
                failed.append(name)
    return out


def _genus_name(genus_id, species_name):
    return GENUS_NAMES.get(genus_id) or species_name.split()[0]


# How far apart the samples of one species must be (metres): a colony counts as new only beyond this. The game's own
# figures: the Genetic Sampler shows each species' colony range in game. Keyed by the journal's genus code; the Horizons
# life forms have no genus code, so their species code stands in.
COLONY_DISTANCE = {
    "$Codex_Ent_Aleoids_Genus_Name;": 150, "$Codex_Ent_Bacterial_Genus_Name;": 500,
    "$Codex_Ent_Cactoid_Genus_Name;": 300, "$Codex_Ent_Clypeus_Genus_Name;": 150,
    "$Codex_Ent_Conchas_Genus_Name;": 150, "$Codex_Ent_Cone_Name;": 100,
    "$Codex_Ent_Electricae_Genus_Name;": 1000, "$Codex_Ent_Fonticulus_Genus_Name;": 500,
    "$Codex_Ent_Fumerolas_Genus_Name;": 100, "$Codex_Ent_Fungoids_Genus_Name;": 300,
    "$Codex_Ent_Ground_Struct_Ice_Name;": 100, "$Codex_Ent_Osseus_Genus_Name;": 800,
    "$Codex_Ent_Recepta_Genus_Name;": 150, "$Codex_Ent_Brancae_Name;": 100,
    "$Codex_Ent_Shrubs_Genus_Name;": 150, "$Codex_Ent_Sphere_Name;": 100,
    "$Codex_Ent_Stratum_Genus_Name;": 500, "$Codex_Ent_Tube_Name;": 100,
    "$Codex_Ent_Tubus_Genus_Name;": 800, "$Codex_Ent_Tussocks_Genus_Name;": 200,
    "$Codex_Ent_Vents_Name;": 100, "$Codex_Ent_Ingensradices_Genus_Name;": 15,
}
_COLONY_BY_NAME = {"aleoida": 150, "bacterium": 500, "cactoida": 300, "clypeus": 150, "concha": 150, "bark mounds": 100,
                   "bark mound": 100, "electricae": 1000, "fonticulua": 500, "fumerola": 100, "fungoida": 300,
                   "crystalline shards": 100, "osseus": 800, "recepta": 150, "brain trees": 100, "brain tree": 100,
                   "frutexa": 150, "anemone": 100, "stratum": 500, "sinuous tubers": 100, "tubus": 800, "tussock": 200,
                   "amphora plant": 100, "radicoida": 15}


def colony_table():
    """{genus name, lower case: metres between samples} for the page: the distance shows before you land (review S1)."""
    return dict(_COLONY_BY_NAME)


def colony_distance(genus_code=None, genus_name=None):
    """Metres between samples of one species, by the journal's genus code (or its localised name)."""
    return COLONY_DISTANCE.get(genus_code or "") or _COLONY_BY_NAME.get((genus_name or "").lower())


def surface_distance(lat1, lon1, lat2, lon2, radius_m):
    """Great-circle distance in metres between two latitude/longitude points on a body of `radius_m`."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def genus_from_id(genus_id):
    """A DSS genus code ('$Codex_Ent_Bacterial_Genus_Name;', as Spansh dumps list them) -> its name
    ('Bacterium'). Unknown codes come back unchanged."""
    if not isinstance(genus_id, str) or not genus_id.startswith("$"):
        return genus_id
    if genus_id in GENUS_NAMES:
        return GENUS_NAMES[genus_id]
    for sp in (load_rules() or {}).get("species") or []:
        if sp.get("genus_id") == genus_id:
            return sp.get("genus") or genus_id
    return genus_id


def _latest_commit(api, path):
    commits = json.loads(_get(f"{api}commits?path={path}&per_page=1"))
    return commits[0]["sha"] if commits else ""


def remote_versions():
    """The newest upstream commits touching the data we use (three small GitHub API calls)."""
    return {"bioscan": ",".join(_latest_commit(BIOSCAN_API, p) for p in BIOSCAN_PATHS),
            "regionmap": _latest_commit(REGIONMAP_API, "RegionMapData.py"),
            "explodata": _latest_commit(EXPLODATA_API, EXPLODATA_PATH)}


def update_if_newer(path=None, log=print):
    """Refresh bio_rules.json when upstream has changed (or the file is missing). Returns True if
    it was rewritten, False if it was already current, None if it could not check or update (offline,
    rate-limited, a download failing midway): the copy there is kept and used, and the log says so."""
    current = load_rules(path)
    try:
        remote = remote_versions()
    except Exception as e:  # noqa: BLE001 -- no network, GitHub down or throttled
        log(f"bio rules: could not check for updates ({e}); "
            + (f"using the copy from {(current.get('generated') or '')[:10]}" if current else "no rules available"))
        if current:
            return None
        raise
    # without the colour tables (a fresh install: they are never shipped) it is out of date whatever its versions say
    if current and current.get("versions") == remote and os.path.exists(colours_path(path)):
        return False
    try:
        update_rules(path, log=lambda *_: None, versions=remote)
    except Exception as e:  # noqa: BLE001 -- the old file is only replaced once everything has arrived
        if not current:
            raise
        log(f"bio rules: the update failed ({e}); using the copy from {(current.get('generated') or '')[:10]}")
        return None
    return True


def update_rules(path=None, log=print, versions=None):
    """Download BioScan's catalog and the region map and write them to `path`. Returns the rule set."""
    path = path or RULES_FILE
    if versions is None:
        try:
            versions = remote_versions()
        except Exception as e:  # noqa: BLE001
            log(f"bio rules: could not read upstream versions ({e})")
            versions = {}
    # A source whose data did not arrive is recorded with no version, so the next start sees a mismatch
    # and tries again (its current upstream version would make the gap look up to date for good).
    versions = dict(versions)
    try:
        files = [f["name"][:-3] for f in json.loads(_get(BIOSCAN_API + "contents/src/bio_scan/bio_data/rulesets"))
                 if f.get("name", "").endswith(".py") and not f["name"].startswith("_")]
    except Exception as e:  # noqa: BLE001 -- the listing is a nicety; the known file names do
        log(f"bio rules: could not list rulesets ({e}); using the known file names")
        files = RULESET_FILES
        versions["bioscan"] = ""   # a ruleset added upstream since would be missing
    catalog = {}
    for name in files:
        failed = []
        catalog.update(_literals(_get(f"{BIOSCAN}bio_data/rulesets/{name}.py"), failed).get("catalog") or {})
        if "catalog" in failed:   # upstream changed its form: the update fails, the old file stays (and is retried)
            raise ValueError(f"bio rules: {name}.py's catalog is no longer a plain literal")
        log(f"bio rules: {name}")
    catalog.update(_literals(_get(BIOSCAN + "bio_data/species.py")).get("_mound_amphora") or {})
    # every table checked like the catalog: one upstream no longer writes as a plain literal fails the update (the old
    # file stays and is retried), never an empty table written over a working one (the Fable sweep, 2026-10-09)
    def tables(url, *names):
        failed = []
        got = _literals(_get(url), failed)
        bad = [n for n in names if n in failed]
        if bad:
            raise ValueError(f"bio rules: {url.rsplit('/', 1)[-1]}'s {', '.join(bad)} no longer a plain literal")
        return got
    regions = tables(BIOSCAN + "bio_data/regions.py", "region_map", "guardian_nebulae", "tuber_zones")
    stars = tables(BIOSCAN + "nebula_data/reference_stars.py", "coordinates", "named_coordinates", "planetary_coordinates")
    sectors = tables(BIOSCAN + "nebula_data/sectors.py", "data").get("data") or []
    log("bio rules: nebulae and regions")
    grid = tables(REGIONMAP, "regions", "regionmap")
    kept = None   # (genus id, species id) -> colours from the current file, when ExploData did not arrive
    try:
        # its table as code (data = build_colours()) fails like a failed fetch: the colours already there are kept and
        # its version is not recorded, so the next start tries again (Codex, 2026-10-09)
        got = tables(EXPLODATA, "data")
        # and with no table called data at all (renamed or moved upstream): not "no colours" either (the Fable review
        # of 2026-10-10, #9)
        if "data" not in got:
            raise ValueError("bio rules: genus.py has no data table any more")
        genus_data = got["data"] or {}
        log("bio rules: colour variants")
    except Exception as e:  # noqa: BLE001 -- without them species are simply not ruled out by colour
        genus_data = {}
        versions["explodata"] = ""   # still retried at the next start
        # Keep the colour tables already downloaded rather than turning the colour check off until then.
        kept = _read_colours(colours_path(path))
        log(f"bio rules: could not fetch colour variants ({e})"
            + (f"; keeping the {len(kept)} colour tables already there" if kept else ""))

    def colours(genus_id, species_id):
        """{"star": {class: colour}} or {"element": {material: colour}} for a species, or None (no check)."""
        if kept is not None:
            return kept.get((genus_id, species_id))
        c = (genus_data.get(genus_id) or {}).get("colors")
        if not c:
            return None
        if "species" in c:
            return c["species"].get(species_id)
        return {"star": c["star"]} if "star" in c else None

    species = []
    for genus_id, members in catalog.items():
        for species_id, d in members.items():
            species.append({"id": species_id, "genus_id": genus_id, "genus": _genus_name(genus_id, d["name"]),
                            "name": d["name"], "value": d.get("value"), "rulesets": d.get("rulesets") or [],
                            "colors": colours(genus_id, species_id)})
    # the colours apart (never shipped: see COLOURS_NAME); written only when ExploData's arrived, else the file stays
    if kept is None:
        cfile = colours_path(path)
        cdoc = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "source": {"name": "EDMC-ExploData", "url": "https://github.com/Silarn/EDMC-ExploData",
                           "commit": versions.get("explodata", ""), "licence": "GPL-2.0"},
                "colors": {f"{sp['genus_id']}|{sp['id']}": sp["colors"] for sp in species if sp.get("colors")}}
        with open(cfile + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(cdoc, fh, separators=(",", ":"))
        os.replace(cfile + ".tmp", cfile)
    species = [dict(sp, colors=None) for sp in species]
    data = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sources": [
            {"name": "EDMC-BioScan", "url": "https://github.com/Silarn/EDMC-BioScan",
             "commit": versions.get("bioscan", ""), "licence": "GPL-2.0-or-later",
             "what": "species spawn rules, nebula and region tables"},
            {"name": "EDMC-ExploData", "url": "https://github.com/Silarn/EDMC-ExploData",
             "commit": versions.get("explodata", ""), "licence": "GPL-2.0",
             "what": "colour variants by parent star and surface material (in bio_colours.json, downloaded, not shipped)"},
            {"name": "EliteDangerousRegionMap", "url": "https://github.com/klightspeed/EliteDangerousRegionMap",
             "commit": versions.get("regionmap", ""), "licence": "MIT", "what": "galactic region map"},
        ],
        "versions": versions,   # compared with GitHub at each start to know when to refresh
        "species": species,
        "region_map": regions.get("region_map") or {},
        "guardian_nebulae": regions.get("guardian_nebulae") or {},
        "tuber_zones": regions.get("tuber_zones") or {},
        "nebulae_large": {**(stars.get("coordinates") or {}), **(stars.get("named_coordinates") or {})},
        "nebulae_planetary": stars.get("planetary_coordinates") or {},
        "sectors": sectors,
        "region_names": grid.get("regions") or [],
        "region_grid": grid.get("regionmap") or [],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    os.replace(tmp, path)
    log(f"bio rules: {len(species)} species written to {path}")
    return load_rules(path, force=True)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

_rules = None
_rules_path = None


def load_rules(path=None, force=False):
    """The rule set from bio_rules.json (None if it has not been downloaded). Cached."""
    global _rules, _rules_path
    path = path or _rules_path or RULES_FILE
    if _rules is not None and not force and path == _rules_path:
        return _rules
    _rules_path = path
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        _rules = None
        return None
    colours = _read_colours(colours_path(path)) or {}
    try:
        for sp in data.get("species") or []:
            if not sp.get("colors"):
                sp["colors"] = colours.get((sp.get("genus_id"), sp.get("id")))
        data["colours"] = bool(colours)
        return _prepare_rules(data)
    except (KeyError, TypeError, AttributeError, ValueError):
        # parses but is not a rules file this version understands (an older schema, a hand edit):
        # treat it as absent so update_if_newer() fetches a fresh copy instead of every call raising
        _rules = None
        return None


def _read_colours(path):
    """{(genus id, species id): colours} from a bio_colours.json, or None when it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh).get("colors")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(got, dict):
        return None
    return {tuple(k.split("|", 1)): v for k, v in got.items() if isinstance(k, str) and "|" in k and isinstance(v, dict)}


def colours_available():
    """Whether ExploData's colour tables are loaded (downloaded on the first start; tests needing them skip without)."""
    r = load_rules()
    return bool(r and r.get("colours"))


def _prepare_rules(data):
    global _rules
    for key in ("guardian_nebulae", "tuber_zones", "sectors", "region_names", "region_grid"):
        data[key]   # read later by the evaluator: a file without one is incomplete (KeyError)
    for s in data["species"]:
        for r in s["rulesets"]:
            if "region" in r and "regions" not in r:  # a typo in one BioScan file; clearly meant
                r["regions"] = r.pop("region")
            atm = r.get("atmosphere")
            if isinstance(atm, list):
                r["atmosphere"] = {norm_atmosphere(a) for a in atm}
            if isinstance(r.get("volcanism"), list):
                r["volcanism"] = [v.lower() for v in r["volcanism"]]
            if isinstance(r.get("body_type"), list):
                r["body_type"] = {journal_class(b) for b in r["body_type"]}
            if isinstance(r.get("bodies"), list):
                r["bodies"] = {journal_class(b) for b in r["bodies"]}
            if isinstance(r.get("atmosphere_component"), dict):
                r["atmosphere_component"] = {norm_atmosphere(k): v for k, v in r["atmosphere_component"].items()}
    data["nebulae_large"] = {k: tuple(v) for k, v in data["nebulae_large"].items()}
    data["nebulae_planetary"] = {k: tuple(v) for k, v in data["nebulae_planetary"].items()}
    data["region_of"] = {int(i) for ids in data["region_map"].values() for i in ids}
    _rules = data
    _cached_region.cache_clear()
    _cached_nebula.cache_clear()
    return _rules


def available():
    return load_rules() is not None


def rules_info():
    """{"generated", "species", "sources"} for the page and the log, or None."""
    r = load_rules()
    if not r:
        return None
    return {"generated": r.get("generated"), "species": len(r["species"]), "sources": r.get("sources"),
            "path": _rules_path}


# --------------------------------------------------------------------------
# Regions and nebulae
# --------------------------------------------------------------------------

def region_number(x, y, z):
    """Galactic region number (1-42) for a position, or None outside the map."""
    if x is None or z is None or not load_rules():
        return None
    return _cached_region(round(x, 1), round(z, 1))


@functools.lru_cache(maxsize=4096)
def _cached_region(x, z):
    grid = _rules["region_grid"]
    px = int((x - REGION_ORIGIN[0]) * 83 / 4096)
    pz = int((z - REGION_ORIGIN[2]) * 83 / 4096)
    if px < 0 or pz < 0 or pz >= len(grid):
        return None
    rx, pv = 0, 0
    for rl, pv in grid[pz]:
        if px < rx + rl:
            break
        rx += rl
    else:
        pv = 0
    return pv or None


def region_name(x, y, z):
    n = region_number(x, y, z)
    names = _rules["region_names"] if n and _rules else []
    return names[n] if n and n < len(names) else None


REGION_CELL = 4096 / 83   # ly per grid cell (_cached_region's 83 cells per 4096 ly)


def region_layer():
    """The region map for the Plot Route tab's galaxy map, or None without rules: klightspeed's grid as it is shipped
    (`rows`: one list per row of [run length, region number] pairs, row 0 at the smallest Z, each run going +X from
    the origin; 0 is outside the map), the names, and a label point per region (`labels`: n, name, x, z, cells).
    A row's cells are `cell` ly square from `origin` [x, z], so a position's cell is the one region_number() reads.
    A label goes at the region's centroid, or at its cell nearest the centroid when that falls outside it (a curved
    arm), so it always lands inside its region."""
    R = load_rules()
    if not R or not R.get("region_grid"):
        return None
    grid, names = R["region_grid"], R["region_names"]
    acc = {}   # region -> [cells, sum of column centres, sum of row centres]
    for row, runs in enumerate(grid):
        c = 0
        for length, n in runs:
            if n:
                a = acc.setdefault(n, [0, 0.0, 0.0])
                a[0] += length
                a[1] += length * (c + length / 2)   # the run's column centres: c + 0.5 ... c + length - 0.5
                a[2] += length * (row + 0.5)
            c += length
    labels = []
    for n, (cells, sx, sz) in sorted(acc.items()):
        cx, cz = sx / cells, sz / cells
        row, col = int(cz), int(cx)
        if _run_value(grid, row, col) != n:   # outside its own region: the region's cell nearest the centroid
            best = None
            for r, runs in enumerate(grid):
                c = 0
                for length, v in runs:
                    if v == n:
                        nx = min(max(cx, c + 0.5), c + length - 0.5)
                        d = (nx - cx) ** 2 + (r + 0.5 - cz) ** 2
                        if best is None or d < best[0]:
                            best = (d, nx, r + 0.5)
                    c += length
            cx, cz = best[1], best[2]
        labels.append({"n": n, "name": names[n] if n < len(names) else f"Region {n}",
                       "x": round(REGION_ORIGIN[0] + cx * REGION_CELL, 1), "z": round(REGION_ORIGIN[2] + cz * REGION_CELL, 1),
                       "cells": cells})
    src = next((s for s in R.get("sources") or () if s.get("name") == "EliteDangerousRegionMap"), {})
    return {"origin": [REGION_ORIGIN[0], REGION_ORIGIN[2]], "cell": REGION_CELL, "size": len(grid), "rows": grid,
            "names": names, "labels": labels,
            "source": {"name": "klightspeed/EliteDangerousRegionMap", "url": src.get("url"), "licence": src.get("licence", "MIT"),
                       "commit": src.get("commit")}}


def _run_value(grid, row, col):
    """The region number in one grid cell (0 outside the grid or the map)."""
    if not 0 <= row < len(grid) or col < 0:
        return 0
    c = 0
    for length, v in grid[row]:
        if col < c + length:
            return v
        c += length
    return 0


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


@functools.lru_cache(maxsize=1024)
def _cached_nebula(name, x, y, z, kind):
    """BioScan's nebula test: in a nebula sector by name, or within 150 ly of a large nebula's
    reference star (or, for 'all', within 100 ly of a planetary nebula's)."""
    r = _rules
    if name and any(name.startswith(s) for s in r["sectors"]):
        return True
    if x is None:
        return None
    pos = (x, y, z)
    if any(_dist(pos, c) < 150.0 for c in r["nebulae_large"].values()):
        return True
    return kind == "all" and any(_dist(pos, c) < 100.0 for c in r["nebulae_planetary"].values())


def in_nebula(system, kind="all"):
    if not load_rules():
        return None
    return _cached_nebula(system.get("name") or "", system.get("x"), system.get("y"), system.get("z"), kind)


# --------------------------------------------------------------------------
# The evaluator (mirrors BioScan's value_estimate, minus colour variants)
# --------------------------------------------------------------------------

SKIP = object()  # "this body does not tell us" -- the rule neither passes nor fails


def _check(key, want, b, s):
    """True/False, or SKIP when the data needed is unknown (a missing fact never eliminates)."""
    if key == "atmosphere":
        if want == "Any":
            return b["atm"] != "none"
        return b["atm"] in want
    if key == "atmosphere_component":
        comp = b.get("composition")
        if comp is None:
            return SKIP
        return all(comp.get(gas, 0) >= pct for gas, pct in want.items())
    if key == "min_gravity":
        return SKIP if b["g"] is None else b["g"] >= want
    if key == "max_gravity":
        return SKIP if b["g"] is None else b["g"] <= want
    if key == "min_temperature":
        return SKIP if not b["t"] else b["t"] >= want
    if key == "max_temperature":
        return SKIP if not b["t"] else b["t"] <= want
    if key == "min_pressure":
        return SKIP if not b["p"] else b["p"] >= want
    if key == "max_pressure":
        return SKIP if not b["p"] else b["p"] < want
    if key == "max_orbital_period":
        op = b.get("orbital_period_s")
        return SKIP if op is None else op < want
    if key == "volcanism":
        v = b["volc"]
        if v is None:   # not known (a Spansh body search leaves it out): neither none nor some
            return SKIP
        if isinstance(want, list):
            return any((v == w[1:]) if w.startswith("=") else (w in v) for w in want)
        if want == "Any":
            return v != ""
        if want == "None":
            return v == ""
        if want.startswith("!"):  # "not X" assumes there is some volcanism
            return v != "" and want[1:] not in v
        return want in v
    if key == "body_type":
        return b["cls"] in want
    if key == "regions":
        if s["region"] is None:
            return SKIP
        rmap = _rules["region_map"]
        if any(s["region"] in rmap.get(r[1:], ()) for r in want if r.startswith("!")):
            return False
        wanted = [r for r in want if not r.startswith("!")]
        return not wanted or any(s["region"] in rmap.get(r, ()) for r in wanted)
    if key == "guardian":
        if not want:
            return True
        if s["pos"] is None:
            return SKIP
        return any(_dist(s["pos"], tuple(c)) < d for d, c in _rules["guardian_nebulae"].values())
    if key == "tuber":
        if s["pos"] is None:
            return SKIP
        for zone, ((lo, hi), c) in _rules["tuber_zones"].items():
            if (want == "Any" or zone in want) and lo <= _dist(s["pos"], tuple(c)) <= hi:
                return True
        return False
    if key == "bodies":
        if s["planet_types"] is None:
            return SKIP
        return any(t in want for t in s["planet_types"])
    if key == "main_star":
        main = [s["main"]] if s["main"] else []
        if _star_list_matches(want, main):
            return True
        return SKIP if _star_class_only(want, main) else False
    if key == "parent_star":
        if s["main"] and any(star_matches(w, s["main"]["type"]) for w in want):
            return True
        parents = b.get("parents")
        if parents is None:  # BioScan would eliminate here; we may simply not know the parents yet
            return SKIP
        return any(star_matches(w, p) for w in want for p in parents)
    if key == "star":
        if _star_list_matches(want, s["stars"]):
            return True
        # no known star matches: ruled out only once every body (every star) is known; an unscanned
        # companion may be the one (Anemone, Crystalline Shards and Amphora need a particular star).
        # A star of the right class whose luminosity is not known (an EDSM/Spansh record without it,
        # the arrival placeholder) does not tell us either
        if not s["complete"] or _star_class_only(want, s["stars"]):
            return SKIP
        return False
    if key == "nebula":
        if want not in ("all", "large"):
            return True
        found = _cached_nebula(s["name"], *(s["pos"] or (None, None, None)), want)
        return SKIP if found is None else found
    if key == "distance":
        return SKIP if b["dist"] is None else b["dist"] >= want
    if key == "system":
        return s["name"] == want
    return True  # an unknown rule type from a newer BioScan: don't guess


def _star_list_matches(want, stars):
    """`want`: a code, or a list of codes and [code, luminosity] pairs; any star matching passes."""
    for st in stars:
        for w in (want if isinstance(want, list) else [want]):
            if isinstance(w, (list, tuple)):
                if star_matches(w[0], st["type"]) and luminosity_matches(w[1], st.get("luminosity")):
                    return True
            elif star_matches(w, st["type"]):
                return True
    return False


def _star_class_only(want, stars):
    """True when a [code, luminosity] pair in `want` matches a star's class but that star's
    luminosity is unknown: a missing fact, so the rule must not eliminate on it."""
    return any(isinstance(w, (list, tuple)) and star_matches(w[0], st["type"]) and not st.get("luminosity")
               for st in stars for w in (want if isinstance(want, list) else [want]))


def _body_facts(body):
    g = body.get("gravity")
    return {"cls": landable_class(body.get("class")), "atm": norm_atmosphere(body.get("atmosphere")),
            "g": g, "t": body.get("temperature"), "p": body.get("pressure"),
            "volc": norm_volcanism(body["volcanism"]) if body.get("volcanism") is not None else None,
            "dist": body.get("dist_ls"),
            "orbital_period_s": body.get("orbital_period_s"),
            "composition": ({norm_atmosphere(k): v for k, v in body["atmosphere_composition"].items()}
                            if body.get("atmosphere_composition") is not None else None),
            "parents": [star_code(p) for p in body["parents"]] if body.get("parents") is not None else None,
            "materials": ({str(m).lower() for m in body["materials"]} if body.get("materials") is not None else None)}


def _colour_ok(col, b, s):
    """BioScan's colour check: a species with colour variants needs one for this body -- by the star it
    orbits (or the system's main star, which BioScan also counts) or by a surface material. Unknown stars
    or materials rule nothing out; nor does a black hole primary (orbiting stars colour those bios)."""
    if not col:
        return True
    if "star" in col:
        main = (s.get("main") or {}).get("type")
        if main and (main == "H" or main.startswith("SupermassiveBlackHole")):
            return True
        if b["parents"] is not None:
            stars = [c for c in b["parents"] if c] + ([main] if main else [])
        elif s.get("complete") and len(s.get("stars") or []) == 1 and main:
            stars = [main]   # every body known and one star: the body can only orbit that one
        else:
            return True
        if not stars:
            return True
        return any(star_matches(q, c) for q in col["star"] for c in stars)
    if "element" in col:
        return b["materials"] is None or any(e in b["materials"] for e in col["element"])
    return True


def _variants(col, b, s):
    """The colours a species with colour table `col` can take on this body, or [] when unsure."""
    if not col:
        return []
    if "element" in col:
        # the material-keyed genera: one colour per matching material the body has (the game picks one of them)
        if b["materials"] is None:
            return []
        return list(dict.fromkeys(c for e, c in col["element"].items() if e in b["materials"]))
    if "star" not in col:
        return []
    main = (s.get("main") or {}).get("type")
    if main and (main == "H" or main.startswith("SupermassiveBlackHole")):
        return []
    if b["parents"] is not None:
        near = b["parents"][0] if b["parents"] else None
    elif s.get("complete") and len(s.get("stars") or []) == 1 and main:
        near = main   # every body known and one star: the body can only orbit that one
    else:
        near = None
    if not near:
        return []
    colours = lambda code: {c for q, c in col["star"].items() if star_matches(q, code)}
    got = colours(near)
    # Settled only when no other star could colour it. The nearest parent star is not always the one: in the
    # author's journals a Y dwarf parent never gave its own colour (the system's F star did) and an M parent
    # once took a neutron star's. So every star of a complete system must agree, else it stays unsure.
    if len(got) != 1 or not s.get("complete"):
        return []
    if any(colours(st["type"]) - got for st in s.get("stars") or [] if st.get("type")):
        return []
    return sorted(got)


def variant_names(sp, b, s):
    """The colour variants a species could show on this body, as the codex names them ("Bacterium Aurasus -
    Teal"): one for a star-keyed species whose colour is settled, one per matching surface material for a
    material-keyed one, [] whenever it cannot be told (then only the species can be checked)."""
    return [f"{sp['name']} - {c}" for c in _variants(sp.get("colors"), b, s)]


def _system_facts(system, body):
    system = system or {}
    stars = [{"type": star_code(st.get("type")), "luminosity": st.get("luminosity"), "main": st.get("main")}
             for st in system.get("stars") or [] if st.get("type")]
    main = next((st for st in stars if st.get("main")), None)
    if main is None and body.get("star"):
        main = {"type": star_code(body["star"]), "luminosity": None, "main": True}
        if not stars:
            stars = [main]
    x, y, z = system.get("x"), system.get("y"), system.get("z")
    region = system.get("region")
    if region is None and x is not None:
        region = region_number(x, y, z)
    pt = system.get("planet_types")
    return {"name": system.get("name") or "", "pos": (x, y, z) if x is not None else None, "region": region,
            "stars": stars, "main": main, "complete": bool(system.get("complete")),
            "planet_types": [journal_class(t) for t in pt] if pt is not None else None}


def predict(body, system=None):
    """Species that could live on this body, most valuable first.

    Returns [] for a body that cannot host anything (gas giant, not landable) or when the rules
    have not been downloaded. Each entry: {name, genus, value, variants} (variants: see variant_names).
    """
    R = load_rules()
    b = _body_facts(body)
    if not R or not b["cls"]:
        return []
    s = _system_facts(system, body)
    out = []
    for sp in R["species"]:
        for ruleset in sp["rulesets"]:
            if all(_check(k, v, b, s) is not False for k, v in ruleset.items()) and _colour_ok(sp.get("colors"), b, s):
                out.append({"name": sp["name"], "genus": sp["genus"],
                            "value": species_value(sp["name"]) or sp.get("value"),
                            "variants": variant_names(sp, b, s)})
                break
    out.sort(key=lambda x: -(x["value"] or 0))
    return out


_BY_NAME = {}


def species_by_name(name):
    """The rules' entry for a species by its name, case ignored ("Roseum Brain Tree", "Tussock Pennata"): {id, genus_id,
    genus, ...}, or None. A codex entry's localised name (variant cut off at " - ") finds its species this way, the
    variant-less older species (Brain Trees, Anemones, Tubers...) included, whose codex codes carry no number."""
    R = load_rules()
    if not R or not name:
        return None
    if _BY_NAME.get("_rules") is not R:
        _BY_NAME.clear()
        _BY_NAME.update({sp["name"].lower(): sp for sp in R["species"]})
        _BY_NAME["_rules"] = R
    return _BY_NAME.get(str(name).strip().lower())


# why a rule key fails, in words (ruled_out)
WHY_WORDS = {"atmosphere": "the atmosphere", "atmosphere_component": "the atmosphere's make-up", "min_gravity": "gravity too low",
             "max_gravity": "gravity too high", "min_temperature": "too cold", "max_temperature": "too hot",
             "min_pressure": "pressure too low", "max_pressure": "pressure too high", "volcanism": "the volcanism",
             "body_type": "the body type", "regions": "not in this region", "star": "the star", "parent_star": "the parent star",
             "tuber": "no sinuous tubers' zone", "guardian": "no Guardian site nearby", "nebula": "no nebula nearby",
             "bodies": "the system's other bodies", "distance": "the distance from the star",
             "max_orbital_period": "the orbital period", "system": "the system", "colour": "no colour rule fits"}


def ruled_out(body, system=None):
    """Why each genus the rules know is NOT among predict()'s for this body: [{genus, why}], why being the failing
    checks of its species' ruleset that came closest (fewest failures), in words ("too cold, gravity too high").
    [] when the rules are missing or the body hosts nothing at all (predict's own [] cases). BioScan's elimination
    log, for trusting (or doubting) a prediction."""
    R = load_rules()
    b = _body_facts(body)
    if not R or not b["cls"]:
        return []
    s = _system_facts(system, body)
    kept = {x["genus"] for x in predict(body, system)}
    best = {}   # genus -> (number of failures, the failing keys)
    for sp in R["species"]:
        if sp["genus"] in kept:
            continue
        for ruleset in sp["rulesets"]:
            fails = [k for k, v in ruleset.items() if _check(k, v, b, s) is False]
            if not fails and not _colour_ok(sp.get("colors"), b, s):
                fails = ["colour"]
            if fails and (sp["genus"] not in best or len(fails) < best[sp["genus"]][0]):
                best[sp["genus"]] = (len(fails), fails)
    return [{"genus": g, "why": ", ".join(dict.fromkeys(WHY_WORDS.get(k, k) for k in fails))}
            for g, (_, fails) in sorted(best.items())]


def region_allows(name, region):
    """Whether the rules let the species `name` (case ignored) grow in region number `region`: True when one of
    its rulesets has no region filter or passes it, False when every one excludes the region, None when the
    rules or the species are unknown (or the region is)."""
    R = load_rules()
    if not R or region is None or not name:
        return None
    sp = next((s for s in R["species"] if s["name"].lower() == name.lower()), None)
    if sp is None:
        return None
    return any(ruleset_region_ok(r, region) for r in sp["rulesets"])


def ruleset_region_ok(ruleset, region):
    """Whether one ruleset lets its species grow in region number `region` (no region filter: anywhere). The rules
    must be loaded (load_rules)."""
    return "regions" not in ruleset or _check("regions", ruleset["regions"], None, {"region": region}) is not False


# --------------------------------------------------------------------------
# Values and grouping
# --------------------------------------------------------------------------

def genus_value(genus):
    """The most valuable species of a genus in the price table (or the rules), by name."""
    g = genus.lower().rstrip("s")
    best = 0
    for value, vname in ORGANIC_VALUES.values():
        n = vname.lower()
        if n.startswith(g) or n.endswith(" " + g) or n.endswith(" " + g + "s"):
            best = max(best, value)
    if not best and load_rules():
        best = max((sp.get("value") or 0 for sp in _rules["species"] if sp["genus"] == genus), default=0)
    return best or None


def species_value(name):
    """Credits for a species (max over colour variants for the Horizons ones)."""
    if not name:   # a ScanOrganic without Species_Localised
        return None
    # the journal names the Horizons forms in the plural ("Bark Mounds") where the price list has
    # the singular ("Bark Mound"): compare with a trailing s dropped on both sides
    one = lambda t: t[:-1] if t.endswith("s") else t
    name = one(name)
    best = 0
    for value, vname in ORGANIC_VALUES.values():
        vname = one(vname)
        if vname == name or vname.endswith(" " + name):
            best = max(best, value)
    if not best:   # not in the price list (Radicoida Unicus): the rules' figure, as the predictions use
        best = max((sp.get("value") or 0 for sp in (load_rules() or {}).get("species") or []
                    if one(sp.get("name") or "") == name), default=0)
    return best or None


def potential(candidates, signals=None, genera=None):
    """An upper bound on what a body's bio could pay: the best species of each confirmed genus,
    or, before the DSS, of the `signals` most valuable possible genera."""
    groups = by_genus(candidates, genera)
    if genera is None and signals:
        groups = groups[:signals]
    return sum(g["value"] or 0 for g in groups), groups


def short_species(name, genus):
    """'Tussock Capillum' -> 'Capillum'; 'Roseum Brain Tree' stays whole."""
    return name[len(genus) + 1:] if name.startswith(genus + " ") else name


def by_genus(candidates, genera=None):
    """Group candidates by genus: [{genus, best (name), value, species:[...], variants, variant}], most
    valuable first (variants: the best species' colour candidates, variant the first of them or None).

    If `genera` (the DSS's list) is given, only those genera are kept -- and a genus the DSS
    found that no rule predicts is still listed, with no value guess.
    """
    groups = collections.OrderedDict()
    for c in candidates:
        if genera is not None and c["genus"] not in genera:
            continue
        # the best species' colour candidates ride along: the codex is checked per variant when they are settled
        vs = c.get("variants") or []
        gr = groups.setdefault(c["genus"], {"genus": c["genus"], "best": c["name"], "value": c["value"],
                                            "min_value": c["value"], "species": [],
                                            "variants": vs, "variant": vs[0] if vs else None})
        gr["species"].append(c)
        if c["value"] and (gr["min_value"] is None or c["value"] < gr["min_value"]):
            gr["min_value"] = c["value"]
    for g in genera or []:
        if g not in groups:
            # No rule predicts it (a gap in the rules, or unknown system context): bound it by the
            # price table so it still counts, and flag that the rules had nothing to say.
            v = genus_value(g)
            groups[g] = {"genus": g, "best": None, "value": v, "min_value": v, "species": [], "unruled": True,
                         "variants": [], "variant": None}
    return sorted(groups.values(), key=lambda gr: -(gr["value"] or 0))


def body_from_scan(ev, star=None, star_types=None):
    """Journal Scan event -> predict() body. `star_types`: {BodyID: StarType} to resolve Parents."""
    g = ev.get("SurfaceGravity")
    parents = [p["Star"] for p in ev.get("Parents") or [] if "Star" in p]
    return {"class": ev.get("PlanetClass"), "atmosphere": ev.get("AtmosphereType"),
            "gravity": g / 9.80665 if g else None, "temperature": ev.get("SurfaceTemperature"),
            "pressure": ev["SurfacePressure"] / 101325 if ev.get("SurfacePressure") else None,
            "volcanism": ev.get("Volcanism"), "dist_ls": ev.get("DistanceFromArrivalLS"),
            "orbital_period_s": ev.get("OrbitalPeriod"),
            "atmosphere_composition": {c["Name"]: c["Percent"] for c in ev.get("AtmosphereComposition") or []}
            if "AtmosphereComposition" in ev else None,
            # only when every star it orbits is known (an unscanned companion may be the one)
            "parents": ([star_types[p] for p in parents] or None) if star_types and all(p in star_types for p in parents) else None,
            "materials": [m["Name"] for m in ev["Materials"]] if ev.get("Materials") else None,
            "star": star}


# --------------------------------------------------------------------------
# Backtest against the journals
# --------------------------------------------------------------------------

def _json_line(line):
    """A journal line as a dict, or None for a truncated or corrupt one (a game crash mid-write)."""
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    return ev if isinstance(ev, dict) else None


def backtest(dirs, verbose=False, since=None):
    """since: only score samples/DSS results at or after this 'YYYY-MM' (an out-of-sample check)."""
    if not load_rules():
        print(f"no rules at {RULES_FILE}: run  python3 -m outrider.bio --update-rules  first")
        return
    scans, systems, analysed, genera = {}, {}, [], collections.defaultdict(set)
    for d in dirs:
        for path in sorted(glob(os.path.join(glob_escape(d), "Journal*.log"))):
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"event":"Scan"' in line:
                        ev = _json_line(line)
                        if ev is None:
                            continue
                        sysd = systems.setdefault(ev.get("SystemAddress"), {"stars": {}, "planets": set()})
                        if ev.get("PlanetClass"):
                            scans[(ev.get("SystemAddress"), ev.get("BodyID"))] = ev
                            sysd["planets"].add(ev["PlanetClass"])
                            sysd.setdefault("planet_ids", set()).add(ev.get("BodyID"))
                        elif ev.get("StarType"):
                            sysd["stars"][ev.get("BodyID")] = {"type": ev["StarType"], "luminosity": ev.get("Luminosity"),
                                                              "main": not ev.get("DistanceFromArrivalLS")}
                    elif '"event":"FSSDiscoveryScan"' in line:
                        ev = _json_line(line)
                        if ev is None:
                            continue
                        sysd = systems.setdefault(ev.get("SystemAddress"), {"stars": {}, "planets": set()})
                        sysd["body_count"] = ev.get("BodyCount")
                    elif '"StarPos"' in line and ('"FSDJump"' in line or '"Location"' in line or '"CarrierJump"' in line):
                        ev = _json_line(line)
                        if ev is None:
                            continue
                        sysd = systems.setdefault(ev.get("SystemAddress"), {"stars": {}, "planets": set()})
                        sysd["name"] = ev.get("StarSystem")
                        sysd["x"], sysd["y"], sysd["z"] = ev["StarPos"]
                    elif '"event":"ScanOrganic"' in line and '"Analyse"' in line:
                        ev = _json_line(line)
                        if ev is None:
                            continue
                        if not since or ev.get("timestamp", "") >= since:
                            analysed.append(ev)
                    elif '"event":"SAASignalsFound"' in line and "Genuses" in line:
                        ev = _json_line(line)
                        if ev is None:
                            continue
                        if since and ev.get("timestamp", "") < since:
                            continue
                        for g in ev.get("Genuses") or []:
                            genera[(ev["SystemAddress"], ev["BodyID"])].add(g.get("Genus_Localised"))

    def context(addr):
        # as the server does it: the planet list (and a lone star) only counts once every body is known
        sysd = systems.get(addr) or {}
        stars = list(sysd.get("stars", {}).values())
        complete = bool(sysd.get("body_count")) and len(stars) + len(sysd.get("planet_ids", ())) >= sysd["body_count"]
        return ({"name": sysd.get("name"), "x": sysd.get("x"), "y": sysd.get("y"), "z": sysd.get("z"),
                 "stars": stars, "planet_types": sorted(sysd.get("planets", ())) if complete else None,
                 "complete": complete},
                {bid: st["type"] for bid, st in sysd.get("stars", {}).items()})

    def describe(sc):
        b = body_from_scan(sc)
        return (landable_class(b["class"]), norm_atmosphere(b["atmosphere"]), round(b["gravity"] or 0, 2),
                round(b["temperature"] or 0), norm_volcanism(b["volcanism"])[:24])

    seen = set()
    sp_hit = sp_total = 0
    v_total = v_set = v_hit = v_size = 0   # colour variants: logged, predicted (a candidate set), right
    misses = collections.Counter()
    ranks = []
    for o in analysed:
        key = (o["SystemAddress"], o["Body"], o["Species_Localised"])
        if key in seen:
            continue
        seen.add(key)
        sc = scans.get((o["SystemAddress"], o["Body"]))
        if not sc:
            continue
        system, star_types = context(o["SystemAddress"])
        cands = predict(body_from_scan(sc, star_types=star_types), system)
        names = [c["name"] for c in cands]
        sp_total += 1
        if o["Species_Localised"] in names:
            sp_hit += 1
            if o.get("Variant_Localised"):
                v_total += 1
                vs = next(c for c in cands if c["name"] == o["Species_Localised"])["variants"]
                if vs:
                    v_set += 1
                    v_hit += o["Variant_Localised"] in vs
                    v_size += len(vs)
            same = [c["name"] for c in cands if c["genus"] == o["Genus_Localised"]]
            ranks.append(same.index(o["Species_Localised"]) + 1 if o["Species_Localised"] in same else 0)
        else:
            misses[(o["Species_Localised"],) + describe(sc) + (region_name(system.get("x"), system.get("y"), system.get("z")),)] += 1
    g_hit = g_total = 0
    extra = []
    g_misses = collections.Counter()
    for key, gs in genera.items():
        sc = scans.get(key)
        if not sc:
            continue
        system, star_types = context(key[0])
        cands = predict(body_from_scan(sc, star_types=star_types), system)
        pg = {c["genus"] for c in cands}
        for g in gs:
            g_total += 1
            if g in pg:
                g_hit += 1
            else:
                g_misses[(g,) + describe(sc)[:4]] += 1
        extra.append(len(pg - gs))
    print(f"species: {sp_hit}/{sp_total} of your analysed species were on the list "
          f"({100 * sp_hit / max(sp_total, 1):.0f}%)")
    if ranks:
        top = sum(1 for r in ranks if r == 1)
        print(f"         when the genus was right, the actual species was the top-valued candidate of that genus "
              f"{top}/{len(ranks)} times; candidates per genus: {sum(ranks) / len(ranks):.1f} avg rank")
    if v_total:
        print(f"variants: a colour was predicted for {v_set}/{v_total} of those samples; the logged variant was in the "
              f"set {v_hit}/{v_set} times ({100 * v_hit / max(v_set, 1):.0f}%), {v_size / max(v_set, 1):.2f} per set; "
              f"the rest fall back to the species check")
    print(f"genera:  {g_hit}/{g_total} of the genera the DSS found were predicted ({100 * g_hit / max(g_total, 1):.0f}%); "
          f"on average {sum(extra) / max(len(extra), 1):.1f} predicted genera per body did not show up")
    if misses:
        print("\nspecies misses (species, class, atmosphere, g, K, volcanism, region) x n:")
        for k, n in misses.most_common(40):
            print("  ", k, "x", n)
    if g_misses:
        print("\ngenus misses:")
        for k, n in g_misses.most_common(20):
            print("  ", k, "x", n)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--update-rules", action="store_true", help="Download the latest spawn rules to resources/bio_rules.json.")
    p.add_argument("--rules", metavar="PATH", help=f"Rules file to use (default {RULES_FILE}).")
    p.add_argument("--backtest", action="store_true", help="Check the rules against your journals.")
    p.add_argument("--since", metavar="YYYY-MM", help="With --backtest: only score finds from this month on (out-of-sample).")
    p.add_argument("--dir", action="append", help="Journal directory (repeatable).")
    p.add_argument("--body", help='Predict for a body given as JSON, e.g. \'{"class":"Rocky body","atmosphere":"Ammonia","gravity":0.15,"temperature":170}\'')
    p.add_argument("--system", help='With --body: system context as JSON, e.g. \'{"x":-3485,"y":39,"z":7320,"stars":[{"type":"M","main":true}]}\'')
    p.add_argument("--region", nargs=3, type=float, metavar=("X", "Y", "Z"), help="Print the galactic region at these coordinates.")
    a = p.parse_args(argv)
    if a.rules:
        load_rules(a.rules)
    if a.update_rules:
        update_rules(a.rules or RULES_FILE)
        if not (a.body or a.backtest or a.region):
            return
    if not available():
        print(f"no rules at {a.rules or RULES_FILE}: run  python3 -m outrider.bio --update-rules  first")
        return
    if a.region:
        print(region_name(*a.region) or "outside the mapped galaxy")
        return
    if a.body:
        system = json.loads(a.system) if a.system else None
        for gr in by_genus(predict(json.loads(a.body), system)):
            print(f"{gr['genus']:18} up to {gr['value'] or 0:>11,} cr  ({', '.join(short_species(s['name'], gr['genus']) + ' ' + str((s['value'] or 0) // 1000) + 'k' for s in gr['species'])})")
        return
    if a.backtest:
        dirs = a.dir
        if not dirs and find_journal_dirs:
            live, legacy = find_journal_dirs()
            dirs = live + legacy
        backtest(dirs or [], since=a.since)
        return
    p.print_help()


if __name__ == "__main__":
    main()
