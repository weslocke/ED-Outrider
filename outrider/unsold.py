#!/usr/bin/env python3
"""
outrider/unsold.py -- How much unsold exploration and exobiology data are you carrying?

Scans Elite Dangerous journal files across one or more save directories, finds
the most recent time you sold cartographic data and the most recent time you
sold organic data, and totals up everything scanned since.

Values are ESTIMATES computed from the published exploration value formula and
the Vista Genomics species price list. Run --help for the accuracy notes,
or --calibrate to check the estimator against your own past sales.

Requires Python 3.9+. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from glob import glob, escape as glob_escape

# --------------------------------------------------------------------------
# Default journal locations. Override or extend with --dir.
# --------------------------------------------------------------------------

ED_SUFFIX = os.path.join("Saved Games", "Frontier Developments", "Elite Dangerous")


def find_journal_dirs():
    """(live, legacy) journal directories on this machine.

    ED_JOURNALS (os.pathsep-separated) overrides everything. Otherwise: the Windows save
    folder, every Steam library's Proton prefix for Elite (app 359320, found through
    libraryfolders.vdf), and, as legacy folders, any mounted Windows drive (Users/*/Saved
    Games (older journals copied from another install)."""
    import re
    env = os.environ.get("ED_JOURNALS")
    if env:
        return [d for d in env.split(os.pathsep) if os.path.isdir(d)], []
    live, legacy = [], []
    home = os.path.expanduser("~")
    win = os.path.join(os.environ.get("USERPROFILE", home), ED_SUFFIX)
    if os.path.isdir(win):
        live.append(win)
    seen = {os.path.realpath(win)}   # the same folder twice would be tailed twice (a symlinked save folder)
    roots = [os.path.expanduser(r) for r in ("~/.local/share/Steam", "~/.steam/steam", "~/.steam/root",
                                             "~/.var/app/com.valvesoftware.Steam/.local/share/Steam")]
    libs = []
    for r in roots:
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="replace") as fh:
                libs += re.findall(r'"path"\s+"([^"]+)"', fh.read())
        except OSError:
            pass
        libs.append(r)
    for lib in libs:
        lib = os.path.realpath(lib.replace("\\\\", "/"))
        p = os.path.join(lib, "steamapps", "compatdata", "359320", "pfx", "drive_c", "users", "steamuser", ED_SUFFIX)
        if os.path.isdir(p) and os.path.realpath(p) not in seen:
            seen.add(os.path.realpath(p))
            live.append(p)
    for base in ("/windows", "/mnt", "/media", "/run/media"):
        for pat in (os.path.join(base, "*", "Users", "*", ED_SUFFIX), os.path.join(base, "*", "*", "Users", "*", ED_SUFFIX)):
            for p in sorted(glob(pat)):
                if os.path.isdir(p) and p not in live and p not in legacy:
                    legacy.append(p)
    return live, legacy


LIVE_DIRS, LEGACY_DIRS = find_journal_dirs()
DEFAULT_DIRS = LIVE_DIRS + LEGACY_DIRS

# --------------------------------------------------------------------------
# Exploration value model
#
# Ported from EDDiscovery's EstimatedValues.cs (the 3.3-and-later branch),
# which is the reference implementation the community back-tests against.
# --------------------------------------------------------------------------

Q = 0.56591828

WHITE_DWARF_TYPES = {
    "D", "DA", "DAB", "DAO", "DAZ", "DAV", "DB", "DBZ", "DBV",
    "DO", "DOV", "DQ", "DC", "DCV", "DX",
}

FIRST_DISCOVERY_MULT = 2.6
EFFICIENT_MAPPING_MULT = 1.25
MAP_MULT_FIRST_DISCOVERED_AND_MAPPED = 3.699622554
MAP_MULT_FIRST_MAPPED_ONLY = 8.0956
MAP_MULT_ALREADY_KNOWN = 3.3333333

TERRAFORM_STATES = {"terraformable", "terraforming", "terraformed"}


FULL_SCAN_BONUS = 1000   # cr per body of a fully found, wholly undiscovered system (paid as the sale's Bonus)


def star_base_value(star_type: str, stellar_mass: float) -> float:
    st = (star_type or "").upper()
    if st in WHITE_DWARF_TYPES:
        k = 14057.0
    elif st in ("N", "H"):
        k = 22628.0
    elif st in ("SUPERMASSIVEBLACKHOLE", "SUPERMASSIVE_BLACK_HOLE"):
        k = 33.5678
    else:
        k = 1200.0
    return k + (stellar_mass * k / 66.25)


def planet_k_value(planet_class: str, terraformable: bool) -> float:
    pc = (planet_class or "").lower()
    if pc == "metal rich body":
        return 21790.0 + (65631.0 if terraformable else 0.0)
    if pc == "ammonia world":
        return 96932.0
    if pc == "sudarsky class i gas giant":
        return 1656.0
    if pc in ("sudarsky class ii gas giant", "high metal content body"):
        return 9654.0 + (100677.0 if terraformable else 0.0)
    if pc == "water world":
        return 64831.0 + (116295.0 if terraformable else 0.0)
    if pc == "earthlike body":
        # Always terraformable, so water world + the terraforming bonus.
        return 64831.0 + 116295.0
    return 300.0 + (93328.0 if terraformable else 0.0)


def planet_base_value(k: float, mass_em: float) -> float:
    return max(k + (k * (mass_em ** 0.2) * Q), 500.0)


def _odyssey_uplift(value: float, odyssey: bool) -> float:
    """Odyssey adds 30% (minimum 555 Cr) on top of mapped values."""
    return value + (max(value * 0.3, 555.0) if odyssey else 0.0)


def body_value(body: dict, mapped: bool, efficient: bool, odyssey: bool,
               efficiency_bonus: bool = False) -> int:
    """Estimated credits for selling this body's scan data.

    efficiency_bonus applies the 1.25x reference multiplier for mapping within
    the probe efficiency target. It is OFF by default: back-testing against this
    account's own sale history showed it overshooting real payouts by ~23%,
    while leaving it off lands within a few percent. See --calibrate.
    """
    star_type = body.get("StarType")
    planet_class = body.get("PlanetClass")

    if star_type:
        base = star_base_value(star_type, body.get("StellarMass") or 1.0)
        return int(base * FIRST_DISCOVERY_MULT) if body.get("first_discovered") else int(base)

    if not planet_class:
        # Belt clusters, barycentres and rings carry no cartographic value.
        return 0

    terraformable = (body.get("TerraformState") or "").lower() in TERRAFORM_STATES
    k = planet_k_value(planet_class, terraformable)
    base = planet_base_value(k, body.get("MassEM") or 1.0)

    first_disc = body.get("first_discovered", False)
    first_map = body.get("first_mapped", False)

    if not mapped:
        return int(base * FIRST_DISCOVERY_MULT) if first_disc else int(base)

    if first_disc and first_map:
        value = _odyssey_uplift(base * MAP_MULT_FIRST_DISCOVERED_AND_MAPPED, odyssey)
        value *= FIRST_DISCOVERY_MULT
    elif first_map:
        value = _odyssey_uplift(base * MAP_MULT_FIRST_MAPPED_ONLY, odyssey)
    else:
        value = _odyssey_uplift(base * MAP_MULT_ALREADY_KNOWN, odyssey)

    if efficient and efficiency_bonus:
        value *= EFFICIENT_MAPPING_MULT
    return int(value)

# --------------------------------------------------------------------------
# Vista Genomics species prices (post Update 14).
# Keyed by the codex prefix that appears in ScanOrganic/SellOrganicData.
# --------------------------------------------------------------------------

ORGANIC_VALUES = {
    '$Codex_Ent_Aleoids_01': (7252500, 'Aleoida Arcus'),
    '$Codex_Ent_Aleoids_02': (6284600, 'Aleoida Coronamus'),
    '$Codex_Ent_Aleoids_03': (3385200, 'Aleoida Spica'),
    '$Codex_Ent_Aleoids_04': (3385200, 'Aleoida Laminiae'),
    '$Codex_Ent_Aleoids_05': (12934900, 'Aleoida Gravis'),
    '$Codex_Ent_Bacterial_01': (1000000, 'Bacterium Aurasus'),
    '$Codex_Ent_Bacterial_02': (5289900, 'Bacterium Nebulus'),
    '$Codex_Ent_Bacterial_03': (4934500, 'Bacterium Scopulum'),
    '$Codex_Ent_Bacterial_04': (1000000, 'Bacterium Acies'),
    '$Codex_Ent_Bacterial_05': (1000000, 'Bacterium Vesicula'),
    '$Codex_Ent_Bacterial_06': (1658500, 'Bacterium Alcyoneum'),
    '$Codex_Ent_Bacterial_07': (1949000, 'Bacterium Tela'),
    '$Codex_Ent_Bacterial_08': (8418000, 'Bacterium Informem'),
    '$Codex_Ent_Bacterial_09': (7774700, 'Bacterium Volu'),
    '$Codex_Ent_Bacterial_10': (1152500, 'Bacterium Bullaris'),
    '$Codex_Ent_Bacterial_11': (4638900, 'Bacterium Omentum'),
    '$Codex_Ent_Bacterial_12': (1689800, 'Bacterium Cerbrus'),
    '$Codex_Ent_Bacterial_13': (3897000, 'Bacterium Verrata'),
    '$Codex_Ent_Cactoid_01': (3667600, 'Cactoida Cortexum'),
    '$Codex_Ent_Cactoid_02': (2483600, 'Cactoida Lapis'),
    '$Codex_Ent_Cactoid_03': (16202800, 'Cactoida Vermis'),
    '$Codex_Ent_Cactoid_04': (3667600, 'Cactoida Pullulanta'),
    '$Codex_Ent_Cactoid_05': (2483600, 'Cactoida Peperatis'),
    '$Codex_Ent_Clypeus_01': (8418000, 'Clypeus Lacrimam'),
    '$Codex_Ent_Clypeus_02': (11873200, 'Clypeus Margaritus'),
    '$Codex_Ent_Clypeus_03': (16202800, 'Clypeus Speculumi'),
    '$Codex_Ent_Conchas_01': (4572400, 'Concha Renibus'),
    '$Codex_Ent_Conchas_02': (7774700, 'Concha Aureolas'),
    '$Codex_Ent_Conchas_03': (2352400, 'Concha Labiata'),
    '$Codex_Ent_Conchas_04': (19010800, 'Concha Biconcavis'),
    '$Codex_Ent_Cone': (1471900, 'Bark Mound'),
    '$Codex_Ent_Electricae_01': (6284600, 'Electricae Pluma'),
    '$Codex_Ent_Electricae_02': (6284600, 'Electricae Radialem'),
    '$Codex_Ent_Fonticulus_01': (19010800, 'Fonticulua Segmentatus'),
    '$Codex_Ent_Fonticulus_02': (1000000, 'Fonticulua Campestris'),
    '$Codex_Ent_Fonticulus_03': (5727600, 'Fonticulua Upupam'),
    '$Codex_Ent_Fonticulus_04': (3111000, 'Fonticulua Lapida'),
    '$Codex_Ent_Fonticulus_05': (20000000, 'Fonticulua Fluctus'),
    '$Codex_Ent_Fonticulus_06': (1804100, 'Fonticulua Digitos'),
    '$Codex_Ent_Fumerolas_01': (6284600, 'Fumerola Carbosis'),
    '$Codex_Ent_Fumerolas_02': (16202800, 'Fumerola Extremus'),
    '$Codex_Ent_Fumerolas_03': (7500900, 'Fumerola Nitris'),
    '$Codex_Ent_Fumerolas_04': (6284600, 'Fumerola Aquatis'),
    '$Codex_Ent_Fungoids_01': (1670100, 'Fungoida Setisis'),
    '$Codex_Ent_Fungoids_02': (2680300, 'Fungoida Stabitis'),
    '$Codex_Ent_Fungoids_03': (3703200, 'Fungoida Bullarum'),
    '$Codex_Ent_Fungoids_04': (3330300, 'Fungoida Gelata'),
    '$Codex_Ent_Ground_Struct_Ice': (1628800, 'Crystalline Shards'),
    '$Codex_Ent_Osseus_01': (4027800, 'Osseus Fractus'),
    '$Codex_Ent_Osseus_02': (12934900, 'Osseus Discus'),
    '$Codex_Ent_Osseus_03': (2404700, 'Osseus Spiralis'),
    '$Codex_Ent_Osseus_04': (3156300, 'Osseus Pumice'),
    '$Codex_Ent_Osseus_05': (1483000, 'Osseus Cornibus'),
    '$Codex_Ent_Osseus_06': (9739000, 'Osseus Pellebantus'),
    '$Codex_Ent_Recepta_01': (12934900, 'Recepta Umbrux'),
    '$Codex_Ent_Recepta_02': (16202800, 'Recepta Deltahedronix'),
    '$Codex_Ent_Recepta_03': (14313700, 'Recepta Conditivus'),
    '$Codex_Ent_Seed': (1593700, 'Roseum Brain Tree'),
    '$Codex_Ent_SeedABCD_01': (1593700, 'Gypseeum Brain Tree'),
    '$Codex_Ent_SeedABCD_02': (1593700, 'Ostrinum Brain Tree'),
    '$Codex_Ent_SeedABCD_03': (1593700, 'Viride Brain Tree'),
    '$Codex_Ent_SeedEFGH_01': (1593700, 'Aureum Brain Tree'),
    '$Codex_Ent_SeedEFGH_02': (1593700, 'Puniceum Brain Tree'),
    '$Codex_Ent_SeedEFGH_03': (1593700, 'Lindigoticum Brain Tree'),
    '$Codex_Ent_SeedEFGH': (1593700, 'Lividum Brain Tree'),
    '$Codex_Ent_Shrubs_01': (1808900, 'Frutexa Flabellum'),
    '$Codex_Ent_Shrubs_02': (7774700, 'Frutexa Acus'),
    '$Codex_Ent_Shrubs_03': (1632500, 'Frutexa Metallicum'),
    '$Codex_Ent_Shrubs_04': (10326000, 'Frutexa Flammasis'),
    '$Codex_Ent_Shrubs_05': (1632500, 'Frutexa Fera'),
    '$Codex_Ent_Shrubs_06': (5988000, 'Frutexa Sponsae'),
    '$Codex_Ent_Shrubs_07': (1639800, 'Frutexa Collum'),
    '$Codex_Ent_Sphere': (1499900, 'Luteolum Anemone'),
    '$Codex_Ent_SphereABCD_01': (1499900, 'Croceum Anemone'),
    '$Codex_Ent_SphereABCD_02': (1499900, 'Puniceum Anemone'),
    '$Codex_Ent_SphereABCD_03': (1499900, 'Roseum Anemone'),
    '$Codex_Ent_SphereEFGH_01': (1499900, 'Rubeum Bioluminescent Anemone'),
    '$Codex_Ent_SphereEFGH_02': (1499900, 'Prasinum Bioluminescent Anemone'),
    '$Codex_Ent_SphereEFGH_03': (1499900, 'Roseum Bioluminescent Anemone'),
    '$Codex_Ent_SphereEFGH': (1499900, 'Blatteum Bioluminescent Anemone'),
    '$Codex_Ent_Stratum_01': (2448900, 'Stratum Excutitus'),
    '$Codex_Ent_Stratum_02': (1362000, 'Stratum Paleas'),
    '$Codex_Ent_Stratum_03': (2788300, 'Stratum Laminamus'),
    '$Codex_Ent_Stratum_04': (2448900, 'Stratum Araneamus'),
    '$Codex_Ent_Stratum_05': (1362000, 'Stratum Limaxus'),
    '$Codex_Ent_Stratum_06': (16202800, 'Stratum Cucumisis'),
    '$Codex_Ent_Stratum_07': (19010800, 'Stratum Tectonicas'),
    '$Codex_Ent_Stratum_08': (2637500, 'Stratum Frigus'),
    '$Codex_Ent_Tube': (1514500, 'Roseum Sinuous Tubers'),
    '$Codex_Ent_TubeABCD_01': (1514500, 'Prasinum Sinuous Tubers'),
    '$Codex_Ent_TubeABCD_02': (1514500, 'Albidum Sinuous Tubers'),
    '$Codex_Ent_TubeABCD_03': (1514500, 'Caeruleum Sinuous Tubers'),
    '$Codex_Ent_TubeEFGH_01': (1514500, 'Lindigoticum Sinuous Tubers'),
    '$Codex_Ent_TubeEFGH_02': (1514500, 'Violaceum Sinuous Tubers'),
    '$Codex_Ent_TubeEFGH_03': (1514500, 'Viride Sinuous Tubers'),
    '$Codex_Ent_TubeEFGH': (1514500, 'Blatteum Sinuous Tubers'),
    '$Codex_Ent_Tubus_01': (2415500, 'Tubus Conifer'),
    '$Codex_Ent_Tubus_02': (5727600, 'Tubus Sororibus'),
    '$Codex_Ent_Tubus_03': (11873200, 'Tubus Cavas'),
    '$Codex_Ent_Tubus_04': (2637500, 'Tubus Rosarium'),
    '$Codex_Ent_Tubus_05': (7774700, 'Tubus Compagibus'),
    '$Codex_Ent_Tussocks_01': (5853800, 'Tussock Pennata'),
    '$Codex_Ent_Tussocks_02': (3227700, 'Tussock Ventusa'),
    '$Codex_Ent_Tussocks_03': (1849000, 'Tussock Ignis'),
    '$Codex_Ent_Tussocks_04': (1766600, 'Tussock Cultro'),
    '$Codex_Ent_Tussocks_05': (1766600, 'Tussock Catena'),
    '$Codex_Ent_Tussocks_06': (1000000, 'Tussock Pennatis'),
    '$Codex_Ent_Tussocks_07': (4447100, 'Tussock Serrati'),
    '$Codex_Ent_Tussocks_08': (3252500, 'Tussock Albata'),
    '$Codex_Ent_Tussocks_09': (1000000, 'Tussock Propagito'),
    '$Codex_Ent_Tussocks_10': (1766600, 'Tussock Divisa'),
    '$Codex_Ent_Tussocks_11': (3472400, 'Tussock Caputus'),
    '$Codex_Ent_Tussocks_12': (7774700, 'Tussock Triticum'),
    '$Codex_Ent_Tussocks_13': (19010800, 'Tussock Stigmasis'),
    '$Codex_Ent_Tussocks_14': (14313700, 'Tussock Virgam'),
    '$Codex_Ent_Tussocks_15': (7025800, 'Tussock Capillum'),
    '$Codex_Ent_Vents': (1628800, 'Amphora Plant'),
    '$Codex_Ent_Thargoid_Coral_Tree_Name': (1896800, 'Coral Tree'),
    '$Codex_Ent_Thargoid_Coral_Root_Name': (1924600, 'Coral Root'),
    '$Codex_Ent_Thargoid_Tower_High_Name': (2247100, 'Major Thargoid Spire'),
    '$Codex_Ent_Thargoid_Tower_Low_Name': (2247100, 'Minor Thargoid Spire'),
    '$Codex_Ent_Thargoid_Tower_ExtraHigh_Name': (2247100, 'Primary Thargoid Spire'),
    '$Codex_Ent_Thargoid_Tower_Med_Name': (2247100, 'Thargoid Spire'),
    '$Codex_Ent_Thargoid_Tower_Name': (2247100, 'Thargoid Spires'),
    '$Codex_Ent_Thargoid_Barnacle_Matrix_Name': (2313500, 'Thargoid Barnacle Matrix'),
}

# --------------------------------------------------------------------------
# Journal reading
# --------------------------------------------------------------------------

SELL_EXPLORATION = ("MultiSellExplorationData", "SellExplorationData")
SELL_ORGANIC = ("SellOrganicData",)
RESET_EVENTS = ("Died",)

# Cartographic data lives in the ship: it is lost only when the ship is, i.e. when the
# Resurrect that follows a Died is a rebuy. Dying on foot or in an SRV puts you back in
# an intact ship. These Resurrect options mean the ship survived.
SHIP_SURVIVED_OPTIONS = ("recover", "rejoin")
# Exobiology data is carried by the commander and is lost on ANY death.


def is_ship_loss(resurrect_option):
    """Did this death cost the ship (and its cartographic data)?"""
    return (resurrect_option or "rebuy") not in SHIP_SURVIVED_OPTIONS


# Only these lines are worth the cost of json.loads().
INTERESTING = (
    '"Scan"', '"SAAScanComplete"', '"ScanOrganic"',
    '"MultiSellExplorationData"', '"SellExplorationData"', '"SellOrganicData"',
    '"Died"', '"Resurrect"', '"LoadGame"', '"Commander"',
    '"Statistics"', '"CrewHire"', '"CrewFire"',
    '"FSDJump"', '"Location"', '"CarrierJump"',   # a system's Population: no x5 bio bonus where people live
    '"FSSAllBodiesFound"',                         # every body found: the full-scan bonus
)

SCAN_KEEP = (
    "BodyName", "BodyID", "StarSystem", "SystemAddress", "StarType", "StellarMass",
    "PlanetClass", "TerraformState", "MassEM", "WasDiscovered", "WasMapped", "WasFootfalled", "ScanType",
    "DistanceFromArrivalLS",
)
# Scans read off a nav beacon: Universal Cartographics neither lists nor buys them, and their Was* flags are not
# the game's record of the body (a beacon in a system surveyed for centuries can say WasDiscovered false).
NAV_BEACON_SCANS = ("NavBeaconDetail", "NavBeacon")


def journal_files(dirs):
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            print(f"warning: not a directory, skipping: {d}", file=sys.stderr)
            continue
        # Journal.*.log only, as everything else reads: not the beta / alpha branches' JournalBeta.* (review L4)
        files.extend(glob(os.path.join(glob_escape(d), "Journal.*.log")))
    return files


def parse_ts(s):
    # Journal timestamps are "2026-09-20T19:00:29Z".
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# Parsed events per journal file, keyed by path -> (size, mtime, [(ts, commander, line hash, ev)]).
# Old journals never change, so a long-running caller (ed_outrider) only re-reads the file
# that is still growing.
_FILE_CACHE = {}


def _read_file(path):
    events = []
    commander = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not any(marker in line for marker in INTERESTING):
                continue
            key = line.strip()
            if not key:
                continue
            try:
                ev = json.loads(key)
            except ValueError:
                continue
            name = ev.get("event")
            if name in ("LoadGame", "Commander"):
                commander = ev.get("Name") or ev.get("Commander") or commander
                continue
            try:
                ts = parse_ts(ev["timestamp"])
            except (KeyError, ValueError):
                continue
            if name == "Scan":   # most of the volume: keep only what analyse() prices and judges by
                ev = {k: ev[k] for k in ("event", "timestamp") + SCAN_KEEP if k in ev}
            elif name in ("FSDJump", "Location", "CarrierJump"):
                ev = {k: ev[k] for k in ("event", "timestamp", "StarSystem", "SystemAddress", "Population") if k in ev}
            elif name == "FSSAllBodiesFound":
                ev = {k: ev[k] for k in ("event", "timestamp", "SystemName", "SystemAddress", "Count") if k in ev}
            # a hash, not the line itself, de-duplicates across folders: the cache lives as long as the server
            events.append((ts, commander, hash(key), ev))
    return events


def read_events(dirs):
    """Yield (timestamp, commander, event_dict) for every event we care about,
    sorted by timestamp, de-duplicated across directories."""
    files = journal_files(dirs)
    if not files:
        raise FileNotFoundError("no Journal.*.log files found in: " + (", ".join(dirs) or "(no journal directory)"))

    events = []
    seen = set()
    for path in files:
        try:
            st = os.stat(path)
            cached = _FILE_CACHE.get(path)
            if cached and cached[0] == st.st_size and cached[1] == st.st_mtime:
                parsed = cached[2]
            else:
                parsed = _read_file(path)
                _FILE_CACHE[path] = (st.st_size, st.st_mtime, parsed)
        except OSError as exc:
            print(f"warning: cannot read {path}: {exc}", file=sys.stderr)
            continue
        for ts, commander, key, ev in parsed:
            if key in seen:
                continue
            seen.add(key)
            events.append((ts, commander, ev))

    events.sort(key=lambda t: t[0])
    return events


# --------------------------------------------------------------------------
# Accumulation
# --------------------------------------------------------------------------

def species_value(codex_species_name):
    """Longest-prefix match against the Vista Genomics price list."""
    best = None
    lowered = (codex_species_name or "").lower()
    for prefix, (value, name) in ORGANIC_VALUES.items():
        if lowered.startswith(prefix.lower()):
            if best is None or len(prefix) > best[0]:
                best = (len(prefix), value, name)
    if best is None:
        return None, None
    return best[1], best[2]


def rules_value(name):
    """A species' value from the bio rules (outrider.bio.species_value's fallback), or None: imported here, since bio
    imports this module, and optional, since this file also runs on its own."""
    try:
        from . import bio
    except ImportError:
        return None
    try:
        return bio.species_value(name) if name else None
    except Exception:   # noqa: BLE001 -- unreadable rules: unpriced, as before
        return None


def analyse(events, args):
    odyssey = not args.no_odyssey

    # --- Pass 1: find the cut-off for each data type ------------------------
    explo_sales, bio_sales = [], []
    commanders = {c for _ts, c, _ev in events if c}
    deaths = []                     # [ts, resurrect option or None]
    bio_rows = bio_rows_with_bonus = 0

    for ts, cmdr, ev in events:
        if args.commander and cmdr and cmdr.lower() != args.commander.lower():
            continue
        name = ev.get("event")
        if name in SELL_EXPLORATION:
            explo_sales.append((ts, ev))
        elif name in SELL_ORGANIC:
            bio_sales.append((ts, ev))
            # Calibrate the x5 rate on the whole sale history, not just the last
            # one -- a bigger sample is a better prior (for runs whose footfall is unknown).
            for b in ev.get("BioData", []):
                bio_rows += 1
                if b.get("Bonus"):
                    bio_rows_with_bonus += 1
        elif name in RESET_EVENTS:
            deaths.append([ts, None])
        elif name == "Resurrect" and deaths and deaths[-1][1] is None:
            deaths[-1][1] = ev.get("Option")

    # --- What the game actually paid, under the crew you have NOW ---------------
    # NPC crew take a share of every payout. Their state is read from the journals: the
    # login Statistics event carries lifetime hired/fired counts, CrewHire/CrewFire move it
    # between logins. Only sales made with the same crew count as today predict today's cut.
    crew = None                     # NPC crew currently employed (None until a Statistics event)
    sale_crew = []                  # (paid, base+bonus, crew count) per sale
    for ts, cmdr, ev in events:
        if args.commander and cmdr and cmdr.lower() != args.commander.lower():
            continue
        name = ev.get("event")
        if name == "Statistics":
            c = ev.get("Crew") or {}
            if "NpcCrew_Hired" in c:
                crew = max(0, c.get("NpcCrew_Hired", 0) - c.get("NpcCrew_Fired", 0))
        elif name == "CrewHire":
            crew = (crew or 0) + 1
        elif name == "CrewFire":
            crew = max(0, (crew or 0) - 1)
        elif name in SELL_EXPLORATION and ev.get("TotalEarnings") and (ev.get("BaseValue") or ev.get("Bonus")):
            sale_crew.append((ev["TotalEarnings"], ev.get("BaseValue", 0) + ev.get("Bonus", 0), crew))
    same = [(p, b) for p, b, c in sale_crew if c == crew]
    if same:
        payout_ratio = sum(p for p, _ in same) / sum(b for _, b in same)
        payout_note = (f"{len(same)} past sale{'s' if len(same) != 1 else ''} with "
                       f"{'no NPC crew' if crew == 0 else f'{crew} NPC crew'} paid {payout_ratio:.1%} of base+bonus")
    elif crew == 0:
        payout_ratio, payout_note = 1.0, "no NPC crew hired: full payout expected"
    elif sale_crew:
        payout_ratio = sum(p for p, _, _ in sale_crew) / sum(b for _, b, _ in sale_crew)
        payout_note = (f"{crew} NPC crew hired but no sale on record with that crew; using the "
                       f"lifetime average of {payout_ratio:.1%}")
    else:
        payout_ratio, payout_note = 1.0, "no past sale to calibrate against"

    last_ship_loss = max((ts for ts, opt in deaths if is_ship_loss(opt)), default=None)
    last_death = deaths[-1][0] if deaths else None

    # "Sell all data" emits one event per 50 systems, so the last sale is the
    # trailing run of events, not just the final one.
    def trailing_batch(sales, window=300):
        if not sales:
            return []
        batch = [sales[-1]]
        for ts, ev in reversed(sales[:-1]):
            if (batch[0][0] - ts).total_seconds() <= window:
                batch.insert(0, (ts, ev))
            else:
                break
        return batch

    explo_batch, bio_batch = trailing_batch(explo_sales), trailing_batch(bio_sales)
    last_explo_sell = explo_batch[-1][0] if explo_batch else None
    last_bio_sell = bio_batch[-1][0] if bio_batch else None
    sold_explo_total = sum(ev.get("TotalEarnings", 0) for _ts, ev in explo_batch)
    sold_bio_total = sum(b.get("Value", 0) + b.get("Bonus", 0)
                         for _ts, ev in bio_batch for b in ev.get("BioData", []))

    # Cartographic data is matched per SYSTEM: a sale lists every system it paid for
    # (in pages of 50), so a scan is sold only once a later sale names its system, and lost
    # if the ship went first. Exobiology sales do not say where the samples came from, only
    # which species: each sale takes out one run per entry of its species, and a death takes
    # them all (see pass 2; bio_cut is only the report's "counting from").
    hard_cut = parse_ts(args.since) if args.since else None
    sales_by_system = {}
    for ts, ev in explo_sales:
        names = ev.get("Systems") or [d.get("SystemName") if isinstance(d, dict) else d
                                          for d in ev.get("Discovered") or []]   # pre-3.3: Systems lists them all
        for n in names:
            sales_by_system.setdefault(n, []).append(ts)
    losses = [] if args.ignore_deaths else sorted(ts for ts, opt in deaths if is_ship_loss(opt))

    def fate(system, t):
        """What became of data picked up in `system` at time t: sold, lost or aboard."""
        sale = next_sale(system, t)
        loss = next((x for x in losses if x > t), None)
        if sale and (not loss or sale < loss):
            return "sold"
        return "lost" if loss else "aboard"

    def next_sale(system, t):
        return next((x for x in sales_by_system.get(system, ()) if x > t), None)

    if args.since:
        explo_cut = bio_cut = hard_cut
    else:
        explo_cut, bio_cut = last_explo_sell, last_bio_sell   # only for the report's "counting from"
        if not args.ignore_deaths:
            if last_ship_loss:
                explo_cut = max(x for x in (explo_cut, last_ship_loss) if x)
            if last_death:
                bio_cut = max(x for x in (bio_cut, last_death) if x)

    # --- Pass 2: collect what is still aboard ----------------------------------
    bodies = {}                     # (system, bodyid) -> latest scan still aboard
    paid = {}                       # (system, bodyid) -> last scan that was sold
    sold_at = {}                    # (system, bodyid) -> when that scan was sold
    map_sold_at = {}                # (system, bodyid) -> when its mapping was sold
    mapped = {}                     # (system, bodyid) -> efficient?  (mapping still aboard)
    system_name = {}                # SystemAddress -> name, for events that carry only the address
    organics = []                   # completed (Analyse) samples still aboard: not in a sale, not lost to a death
    footfalled = {}                 # (system, bodyid) -> no x5: WasFootfalled from your first Scan of it that says, or
    #                                 the system is populated (Vista Genomics pays no x5 there: 0 of 8 runs, 208 of 208
    #                                 elsewhere in the author's sales)
    populated = {}                  # SystemAddress -> Population > 0, from the newest jump or login there
    all_found = {}                  # system name -> FSSAllBodiesFound's Count (the bodies, belt clusters not included)
    saa = []                        # (key, ts, efficient): mappings, judged once every system name is known
    death_in_window = None

    for ts, cmdr, ev in events:
        if args.commander and cmdr and cmdr.lower() != args.commander.lower():
            continue
        name = ev.get("event")
        if ev.get("StarSystem") and ev.get("SystemAddress") is not None:   # any line naming it (a nav beacon's too)
            system_name[ev["SystemAddress"]] = ev["StarSystem"]

        if name == "FSSAllBodiesFound":
            if ev.get("SystemName") and isinstance(ev.get("Count"), int):
                all_found[ev["SystemName"]] = ev["Count"]
            continue
        if name in ("FSDJump", "Location", "CarrierJump"):
            if isinstance(ev.get("Population"), int):
                populated[ev.get("SystemAddress")] = ev["Population"] > 0
            continue
        if name == "Scan":
            if ev.get("ScanType") in NAV_BEACON_SCANS:
                continue
            if "WasFootfalled" in ev:
                # Vista Genomics pays x5 where nobody had set foot when you scanned the body (the first scan
                # counts: a rescan after your own landing says footfalled), and never in a populated system
                footfalled.setdefault((ev.get("SystemAddress"), ev.get("BodyID")),
                                      bool(ev["WasFootfalled"]) or populated.get(ev.get("SystemAddress"), False))
            if not (ev.get("StarType") or ev.get("PlanetClass")):
                continue  # belt clusters and rings: no cartographic value, don't count them
            key = (ev.get("SystemAddress"), ev.get("BodyID"))
            if hard_cut and ts <= hard_cut:
                continue
            if key in sold_at and sold_at[key] < ts:
                # Universal Cartographics already bought this body: a rescan after that sale (an
                # arrival AutoScan, a return visit) pays nothing; only a new mapping adds value.
                continue
            body = {k: ev.get(k) for k in SCAN_KEEP}
            f = fate(ev.get("StarSystem"), ts)
            if f == "aboard":
                prev = bodies.get(key)
                # A Detailed scan supersedes the AutoScan of the same body.
                if prev is None or (prev.get("ScanType") != "Detailed"
                                    and body.get("ScanType") == "Detailed"):
                    bodies[key] = body
            else:
                bodies.pop(key, None)
                if f == "sold":
                    paid[key] = body
                    sold_at[key] = next_sale(ev.get("StarSystem"), ts)

        elif name == "SAAScanComplete":
            if (ev.get("BodyName") or "").endswith(" Ring"):
                continue  # probing a ring is not mapping a body
            if hard_cut and ts <= hard_cut:
                continue
            # judged after the loop: a body mapped before any line named its system (a carrier jump, then the DSS
            # straight away) would otherwise find no sale for it and stay "aboard" for good (review F36)
            probes, target = ev.get("ProbesUsed"), ev.get("EfficiencyTarget")
            saa.append(((ev.get("SystemAddress"), ev.get("BodyID")), ts, bool(probes and target and probes <= target)))

        elif name == "ScanOrganic":
            if ev.get("ScanType") != "Analyse":
                continue
            if hard_cut and ts <= hard_cut:
                continue
            organics.append(ev)

        elif name in SELL_ORGANIC:
            # Vista Genomics lets you sell some species and keep the rest: each BioData entry takes one run of its
            # species out (a paid bonus takes an x5 run first, no bonus an x1 run), and the runs it does not name
            # stay aboard. An entry with no run on record (sampled before your journals start) takes nothing.
            for b in ev.get("BioData") or []:
                sp = (b.get("Species") or "").lower()
                order = (False, None, True) if b.get("Bonus") else (True, None, False)
                runs = [o for o in organics if (o.get("Species") or "").lower() == sp]
                runs.sort(key=lambda r: order.index(footfalled.get((r.get("SystemAddress"), r.get("Body")))))
                if runs:
                    organics.remove(runs[0])

        elif name in RESET_EVENTS:
            if not args.ignore_deaths:
                organics = []   # exobiology data dies with you, whether or not the ship survives
            earliest_cut = min([c for c in (explo_cut, bio_cut) if c], default=None)
            if earliest_cut and ts > earliest_cut:
                death_in_window = ts

    for key, ts, efficient in saa:
        if key in map_sold_at and map_sold_at[key] < ts:
            continue   # the mapping was already sold: Universal Cartographics pays nothing for a remap
        sysname = system_name.get(key[0])
        if sysname is None:
            continue   # never named in these journals: neither aboard nor sold, so not counted
        f = fate(sysname, ts)
        if f == "aboard":
            mapped[key] = efficient
        else:
            mapped.pop(key, None)
            if f == "sold":
                map_sold_at[key] = next_sale(sysname, ts)

    # A body whose scan was already sold but which you mapped afterwards is worth the
    # mapping alone.
    map_only = {key: paid[key] for key in mapped if key not in bodies and key in paid}

    # --- Value it up --------------------------------------------------------
    explo_rows = []
    for key, body in bodies.items():
        body["first_discovered"] = body.get("WasDiscovered") is False
        body["first_mapped"] = body.get("WasMapped") is False
        is_mapped = key in mapped
        value = body_value(body, is_mapped, mapped.get(key, False), odyssey,
                           args.efficiency_bonus)
        explo_rows.append({
            "body": body.get("BodyName"),
            "system": body.get("StarSystem"),
            "type": body.get("StarType") or body.get("PlanetClass") or "belt/cluster",
            "first_discovered": body["first_discovered"],
            "first_mapped": is_mapped and body["first_mapped"],
            "star": bool(body.get("StarType")),
            "planet": bool(body.get("PlanetClass")),
            # The arrival star: first-discovering it is what puts your name on the system.
            "arrival": bool(body.get("StarType")) and not body.get("DistanceFromArrivalLS"),
            "mapped": is_mapped,
            "efficient": mapped.get(key, False),
            "value": value,
        })
    for key, body in map_only.items():
        # Scan already paid: value the mapping alone (mapped value minus unmapped value).
        body["first_discovered"] = False
        body["first_mapped"] = body.get("WasMapped") is False
        value = (body_value(body, True, mapped.get(key, False), odyssey, args.efficiency_bonus)
                 - body_value(body, False, False, odyssey, args.efficiency_bonus))
        explo_rows.append({
            "body": body.get("BodyName"), "system": body.get("StarSystem"),
            "type": body.get("StarType") or body.get("PlanetClass") or "belt/cluster",
            "first_discovered": False, "first_mapped": body["first_mapped"],
            "star": bool(body.get("StarType")), "planet": bool(body.get("PlanetClass")),
            "arrival": False, "mapped": True, "efficient": mapped.get(key, False),
            "value": max(value, 0), "map_only": True,
        })
    explo_rows.sort(key=lambda r: r["value"], reverse=True)

    # Vista Genomics pays 5x for a sample from a body nobody had set foot on when you scanned it. Each run is
    # priced by its body's WasFootfalled (x5 when False, x1 when True); a run whose body's Scan is not in the
    # journals is priced at the rate your own past sales earned the bonus. Range: base total .. 5x base total.
    if args.bonus_rate is not None:
        bonus_rate = args.bonus_rate
        rate_source = "supplied with --bonus-rate"
    elif bio_rows:
        bonus_rate = bio_rows_with_bonus / bio_rows
        rate_source = (f"your sale history: {bio_rows_with_bonus} of {bio_rows} "
                       "sold entries earned it")
    else:
        bonus_rate = 0.0
        rate_source = "no prior sale to calibrate against"

    bio_by_species = {}
    bio_unknown = []
    bio_base_total = 0
    bio_estimate = 0.0
    factors = {5: 0, 1: 0, None: 0}   # runs priced x5 / x1 / at the sale-history rate
    for ev in organics:
        value, name = species_value(ev.get("Species", ""))
        label = ev.get("Species_Localised") or name or ev.get("Species", "?")
        if value is None:   # not in the price list (Radicoida Unicus): the bio rules' figure, as My Samples prices it
            value = rules_value(ev.get("Species_Localised"))
        if value is None:
            bio_unknown.append(label)
            value = 0
        ff = footfalled.get((ev.get("SystemAddress"), ev.get("Body")))
        factor = None if ff is None else 1 if ff else 5
        factors[factor] += 1
        bio_base_total += value
        bio_estimate += value * (factor if factor else 1 + 4 * bonus_rate)
        row = bio_by_species.setdefault(label, {"species": label, "count": 0, "unit_value": value, "value": 0,
                                                "x5": 0, "x1": 0, "unknown": 0})
        row["count"] += 1
        row["value"] += value
        row["x5" if factor == 5 else "x1" if factor == 1 else "unknown"] += 1
    bio_rows_out = sorted(bio_by_species.values(), key=lambda r: r["value"], reverse=True)
    bio_estimate = int(bio_estimate)

    # The full-scan bonus (the sale's Bonus, apart from BaseValue): 1,000 cr per body of a system where you found
    # every body (FSSAllBodiesFound's Count) and every star and planet was undiscovered. Pioneer counts non-bodies
    # and the main star's discovery only; the author's sales fit this narrower form (13 of 15 within 0.86-1.11,
    # typically 7% over: project/value-checks/RESULTS-2026-10-08.md).
    full_scan, full_scan_systems = 0, 0
    by_system = {}
    for r in explo_rows:
        if not r.get("map_only"):
            by_system.setdefault(r["system"], []).append(r)
    for sysname, rows in by_system.items():
        count = all_found.get(sysname)
        if count and len(rows) >= count and all(r["first_discovered"] for r in rows):
            full_scan += FULL_SCAN_BONUS * count
            full_scan_systems += 1

    return {
        "commanders_seen": sorted(commanders),
        "commander_filter": args.commander,
        "odyssey": odyssey,
        "efficiency_bonus": args.efficiency_bonus,
        "exploration": {
            "last_sold": last_explo_sell.isoformat() if last_explo_sell else None,
            "last_sale_earnings": sold_explo_total,
            "cutoff": explo_cut.isoformat() if explo_cut else None,
            "bodies": len(explo_rows),
            "systems": len({r["system"] for r in explo_rows}),
            "first_discoveries": sum(1 for r in explo_rows if r["first_discovered"]),
            "mapped": sum(1 for r in explo_rows if r["mapped"]),
            "estimated_value": sum(r["value"] for r in explo_rows),
            "payout_ratio": payout_ratio,
            "payout_note": payout_note,
            "npc_crew": crew,
            "full_scan_bonus": full_scan,
            "full_scan_systems": full_scan_systems,
            "estimated_payout": int((sum(r["value"] for r in explo_rows) + full_scan) * payout_ratio),
            "rows": explo_rows,
        },
        "exobiology": {
            "last_sold": last_bio_sell.isoformat() if last_bio_sell else None,
            "last_sale_earnings": sold_bio_total,
            "cutoff": bio_cut.isoformat() if bio_cut else None,
            "samples": len(organics),
            "base_value": bio_base_total,
            "max_value": bio_base_total * 5,
            "estimated_value": bio_estimate,
            "x5_runs": factors[5],
            "x1_runs": factors[1],
            "unknown_runs": factors[None],
            "bonus_rate": bonus_rate,
            "bonus_rate_source": rate_source,
            "unknown_species": sorted(set(bio_unknown)),
            "rows": bio_rows_out,
        },
        "death_in_window": death_in_window.isoformat() if death_in_window else None,
        "last_ship_loss": last_ship_loss.isoformat() if last_ship_loss else None,
        "last_death": last_death.isoformat() if last_death else None,
    }


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def cr(n):
    return f"{n:,} Cr"


def report(result, args):
    ex, bio = result["exploration"], result["exobiology"]

    seen = result["commanders_seen"]
    if args.commander and not any(c.lower() == args.commander.lower() for c in seen):
        print(f"\nwarning: no events for commander {args.commander!r}."
              f" Journals contain: {', '.join(seen) or 'no named commander'}",
              file=sys.stderr)

    print()
    print("=" * 66)
    print(" UNSOLD DATA ON BOARD")
    if result["commander_filter"]:
        print(f" Commander: {result['commander_filter']}")
    print("=" * 66)

    print("\nEXPLORATION (cartographic data)")
    print(f"  last sold     : {ex['last_sold'] or 'never'}"
          + (f"  ({cr(ex['last_sale_earnings'])})" if ex["last_sale_earnings"] else ""))
    print(f"  counting from : {ex['cutoff'] or 'the beginning of your journals'}")
    print(f"  bodies        : {ex['bodies']:,} across {ex['systems']:,} systems")
    print(f"  first found   : {ex['first_discoveries']:,}   mapped: {ex['mapped']:,}")
    if ex.get("full_scan_bonus"):   # paid on top of the bodies (the sale's Bonus): in the estimate and the total too
        print(f"  full-scan bonus: {cr(ex['full_scan_bonus'])}   ({ex['full_scan_systems']} system"
              f"{'' if ex['full_scan_systems'] == 1 else 's'} found complete, all undiscovered)")
    print(f"  ESTIMATED     : {cr(ex['estimated_value'] + ex.get('full_scan_bonus', 0))}")
    if ex["payout_ratio"] < 0.999:
        print(f"  after crew cut: {cr(ex['estimated_payout'])}   ({ex['payout_note']})")
    else:
        print(f"  payout        : {ex['payout_note']}")

    print("\nEXOBIOLOGY (Vista Genomics data)")
    print(f"  last sold     : {bio['last_sold'] or 'never'}"
          + (f"  ({cr(bio['last_sale_earnings'])})" if bio["last_sale_earnings"] else ""))
    print(f"  counting from : {bio['cutoff'] or 'the beginning of your journals'}")
    print(f"  samples       : {bio['samples']:,} completed"
          f" ({len(bio['rows'])} distinct species)")
    print(f"  base value    : {cr(bio['base_value'])}")
    print(f"  ESTIMATED     : {cr(bio['estimated_value'])}"
          f"   (range {cr(bio['base_value'])} .. {cr(bio['max_value'])})")
    print(f"  x5 runs       : {bio['x5_runs']:,} of {bio['samples']:,} (no footfall when you scanned the body)")
    if bio["unknown_runs"]:
        print(f"  footfall unknown: {bio['unknown_runs']:,}, priced at {bio['bonus_rate']:.0%} x5"
              f" -- {bio['bonus_rate_source']}")
    if bio["unknown_species"]:
        print(f"  NOT PRICED    : {', '.join(bio['unknown_species'])}"
              " (species missing from the built-in table; counted as 0)")

    print("\n" + "-" * 66)
    print(f"  TOTAL ESTIMATED  {cr(ex['estimated_value'] + ex.get('full_scan_bonus', 0) + bio['estimated_value'])}")
    print("-" * 66)

    if not args.since and not (ex["last_sold"] and bio["last_sold"]):
        missing = [n for n, v in (("exploration", ex["last_sold"]),
                                  ("exobiology", bio["last_sold"])) if not v]
        print(f"\n!! No past {' or '.join(missing)} sale found in these journals, so the")
        print("   totals above count everything on record and are probably too high.")
        print("   Point --dir at the save folder that holds your older journals, or use")
        print("   --since to set the cut-off by hand.")

    if result["death_in_window"]:
        print(f"\n!! You died at {result['death_in_window']}, after the last sale.")
        print("   Cartographic data counts from the last time the ship was lost (a rebuy);")
        print("   exobiology data from the last death of any kind. Use --ignore-deaths to")
        print("   count from the sale instead.")

    if args.top:
        print(f"\nTop {args.top} bodies by value:")
        for r in ex["rows"][:args.top]:
            flags = []
            if r["first_discovered"]:
                flags.append("first")
            if r["mapped"]:
                flags.append("mapped-eff" if r["efficient"] else "mapped")
            print(f"  {cr(r['value']):>18}  {r['body']}  [{r['type']}]"
                  f"{'  (' + ', '.join(flags) + ')' if flags else ''}")

        print(f"\nTop {args.top} species by value:")
        for r in bio["rows"][:args.top]:
            print(f"  {cr(r['value']):>18}  {r['species']} x{r['count']}"
                  f"  @ {cr(r['unit_value'])}")
    print()


# --------------------------------------------------------------------------
# Calibration: replay past sales and compare the estimate to what you were paid
# --------------------------------------------------------------------------

def sale_batches(events):
    """A single 'sell all data' emits several MultiSellExplorationData events
    (50 systems each). Group events that land within five minutes."""
    batches = []
    for ts, _cmdr, ev in events:
        if ev.get("event") not in SELL_EXPLORATION:
            continue
        if batches and (ts - batches[-1][-1][0]).total_seconds() <= 300:
            batches[-1].append((ts, ev))
        else:
            batches.append([(ts, ev)])
    return batches


def calibrate(events, args):
    """Replay each past sale: scan everything sold between the previous sale and
    this one, value it, and compare against the BaseValue the game recorded.

    Only sales where every sold system is fully accounted for in the journals are
    reported -- if you sold data gathered before your journals start, or before a
    gap, the comparison is meaningless rather than wrong."""
    import collections

    # the commander filter applies to the sales too, not only to the scans (Codex F8): another commander's sale in the
    # same five minutes would be counted into this one's batch
    mine = lambda cmdr: not (args.commander and cmdr and cmdr.lower() != args.commander.lower())
    batches = sale_batches([e for e in events if mine(e[1])])
    if len(batches) < 2:
        print("Not enough past exploration sales in these journals to calibrate.")
        return

    print()
    print(f"{'sale date':12s} {'systems':>7s} {'bodies':>7s} {'mapped':>6s} "
          f"{'game base value':>16s} {'estimate':>16s} {'ratio':>7s}")
    print("-" * 76)

    est_total = base_total = 0
    for i in range(1, len(batches)):
        prev_ts, end_ts = batches[i - 1][-1][0], batches[i][-1][0]
        num_bodies, base = {}, 0
        if any(not isinstance(d, dict) for _ts, ev in batches[i] for d in ev.get("Discovered") or []):
            continue   # a pre-3.3 SellExplorationData (body names, no per-system counts): nothing to account against
        for _ts, ev in batches[i]:
            for d in ev.get("Discovered", []):
                num_bodies[d["SystemName"]] = d["NumBodies"]
            base += ev.get("BaseValue", 0)
        if not base:
            continue

        bodies, mapped = {}, {}
        for ts, cmdr, ev in events:
            if not (prev_ts < ts <= end_ts):
                continue
            if args.commander and cmdr and cmdr.lower() != args.commander.lower():
                continue
            name = ev.get("event")
            if name == "Scan" and ev.get("StarSystem") in num_bodies and ev.get("ScanType") not in NAV_BEACON_SCANS:
                key = (ev.get("SystemAddress"), ev.get("BodyID"))
                if key not in bodies or ev.get("ScanType") == "Detailed":
                    bodies[key] = ev
            elif name == "SAAScanComplete":
                probes, target = ev.get("ProbesUsed"), ev.get("EfficiencyTarget")
                mapped[(ev.get("SystemAddress"), ev.get("BodyID"))] = bool(
                    probes and target and probes <= target)

        # Skip sales we cannot fully account for.
        counted = collections.Counter(b["StarSystem"] for b in bodies.values())
        if any(counted[s] != n for s, n in num_bodies.items()):
            continue

        est = 0
        for key, body in bodies.items():
            body = dict(body)
            body["first_discovered"] = body.get("WasDiscovered") is False
            body["first_mapped"] = body.get("WasMapped") is False
            est += body_value(body, key in mapped, mapped.get(key, False),
                              not args.no_odyssey, args.efficiency_bonus)

        est_total += est
        base_total += base
        print(f"{end_ts:%Y-%m-%d}   {len(num_bodies):7d} {len(bodies):7d} "
              f"{sum(1 for k in bodies if k in mapped):6d} {base:>16,} {est:>16,} "
              f"{est / base:>7.3f}")

    print("-" * 76)
    if base_total:
        ratio = est_total / base_total
        print(f"{'AGGREGATE':12s} {'':7s} {'':7s} {'':6s} {base_total:>16,} "
              f"{est_total:>16,} {ratio:>7.3f}")
        print()
        print(f"The estimator runs {abs(1 - ratio):.1%} "
              f"{'high' if ratio > 1 else 'low'} against your own sale history.")
        print("Multiply the exploration figure by "
              f"{1 / ratio:.3f} if you want it de-biased.")
    else:
        print("No fully-accounted sale found to compare against.")
    print()
    print("Note: what you actually bank can be lower than the game's base value")
    print("if you sell at a fleet carrier that charges a cut.")


NOTES = """\
Accuracy
--------
Exploration uses the published value formula (the one EDDiscovery implements),
fed with the real WasDiscovered / WasMapped / mass fields from your journal.
Bodies you scanned before your last sale are excluded even if you flew past and
re-scanned them. Run --calibrate to replay your own past sales and see how close
the estimate lands; on the journals this was written against it comes out about
1.4% high in aggregate.

One deviation from the reference implementation: the 1.25x bonus for mapping
inside the probe efficiency target is NOT applied by default. Including it
overshot real recorded payouts by ~23% consistently across fifteen sales, while
leaving it off lands within a few percent. --efficiency-bonus turns it back on,
and --calibrate will show you the difference.

Exobiology uses the post-Update-14 Vista Genomics price list, which matched
every organic sale in these journals exactly. What the journal CANNOT tell you
in advance is whether you are the first commander to log a species -- that pays
5x and is only revealed in the sale event. So exobiology is given as a range,
with a point estimate calibrated on how often your own sales earned that bonus.

Caveats
-------
* Cartographic data is lost when your ship is destroyed: a Died followed by a
  rebuy Resurrect resets the count. Dying on foot or in an SRV keeps the ship's
  data but loses your exobiology samples, so those reset on any death. Use
  --ignore-deaths to count from the last sale regardless.
* Bodies re-scanned after a sale are only counted for a new mapping; bodies
  re-scanned after a ship loss count in full (that data was never sold).
* Belt clusters and rings are not counted as bodies; ring probes are not
  counted as mapping. Nav beacon scans are not counted either: Universal
  Cartographics does not buy them.
* Vista Genomics lets you sell some species and keep the rest: each sold
  entry takes one completed run of its species out, and the others stay
  aboard until they are sold or you die.
* Cartographic data is matched per system: a sale event names every system it
  paid for, so a scan counts as sold only once a later sale names its system
  (partial "sell 50 systems" sales are handled), and as lost if the ship went
  first.
* NPC crew take a cut of every sale. The crew you have now is read from the
  journals (the login Statistics counters plus CrewHire/CrewFire), and the
  "after crew cut" figure uses only past sales made with that same crew count;
  with no crew hired the full base value is expected.
* If your journals do not reach back to your last sale the script says so, and
  the totals will be too high because they count data you have already sold.
* Selling cartographic data does not clear organic data or vice versa, so the
  two cut-off dates are tracked separately and will usually differ.
* What you actually bank can be below the estimate if you sell at a fleet
  carrier that charges a cut.
"""


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Total up unsold exploration and exobiology data in Elite Dangerous journals.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=NOTES,
    )
    p.add_argument("--dir", action="append", metavar="PATH",
                   help="Journal directory; repeatable. Default: auto-detected "
                        f"({', '.join(DEFAULT_DIRS) or 'none found — set ED_JOURNALS or pass --dir'}).")
    p.add_argument("--commander", metavar="NAME",
                   help="Only count events for this commander.")
    p.add_argument("--since", metavar="ISO8601",
                   help="Ignore the detected sale and count from this timestamp instead, "
                        "e.g. 2026-09-01T00:00:00Z")
    p.add_argument("--ignore-deaths", action="store_true",
                   help="Do not treat a Died event as a reset point.")
    p.add_argument("--bonus-rate", type=float, metavar="0.0-1.0",
                   help="Assumed fraction of organic samples that earn the 5x first-footfall bonus, "
                        "for runs whose body's footfall is not in the journals (the rest are priced x5 or x1 "
                        "from the body's scan). Default: calibrated from your past sales.")
    p.add_argument("--efficiency-bonus", action="store_true",
                   help="Apply the 1.25x bonus for mapping inside the probe efficiency "
                        "target. Off by default -- see --calibrate.")
    p.add_argument("--calibrate", action="store_true",
                   help="Replay your past sales and report how close the estimator is.")
    p.add_argument("--no-odyssey", action="store_true",
                   help="Drop the Odyssey mapping uplift (only for a Horizons-era account).")
    p.add_argument("--top", type=int, default=10, metavar="N",
                   help="Show the N most valuable bodies and species (0 to hide). Default 10.")
    p.add_argument("--json", action="store_true", help="Emit the full result as JSON instead.")
    args = p.parse_args(argv)
    if args.since:
        if "T" not in args.since:
            args.since += "T00:00:00Z"   # a bare date: from its start
        try:
            parse_ts(args.since)
        except ValueError:
            p.error("--since must look like 2026-09-01 or 2026-09-01T00:00:00Z")

    dirs = args.dir or DEFAULT_DIRS
    events = read_events(dirs)

    if args.calibrate:
        calibrate(events, args)
        return 0

    result = analyse(events, args)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        report(result, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
