"""The Log view: every journal event, newest first, with a one-line summary.

Read straight from the journal files on request, not from the database: the files are the source
of truth, they are already local, and their names carry the time they were started, so a time
window only opens the files that can hold it.

    read_log(dirs, days=7, before=None, after=None, limit=200, cats=None, q=None, noise=False, only=None)

A cursor is "<file name>|<line index>": stable while the newest file is still being written. Each row also has `at`,
its line's byte offset in the file: with the file's name, the key the uploads' outbox keeps (the server's upload marks,
S68). `only` ({file name: set of offsets}) keeps just those lines, whatever `cats` says (the Log's "not sent").
"""
import json
import os
import re
import threading
import time
from collections import ChainMap, OrderedDict
from glob import glob, escape as glob_escape

C = 299792458.0

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORIES = ("travel", "exploration", "phenomena", "bio", "ship", "carrier", "other", "noise")

_CAT_EVENTS = {
    "travel": "FSDJump StartJump FSDTarget Location CarrierJump SupercruiseEntry SupercruiseExit "
              "SupercruiseDestinationDrop ApproachBody LeaveBody Touchdown Liftoff Docked Undocked FuelScoop "
              "JetConeBoost NavRoute DockingRequested DockingGranted DockingDenied DockingCancelled DockingTimeout "
              "ApproachSettlement USSDrop Interdicted EscapeInterdiction FSDJumpCancelled",
    "exploration": "Scan FSSDiscoveryScan FSSAllBodiesFound FSSBodySignals SAASignalsFound SAAScanComplete "
                   "ScanBaryCentre NavBeaconScan MultiSellExplorationData SellExplorationData DiscoveryScan "
                   "BuyExplorationData",
    "bio": "ScanOrganic SellOrganicData CodexEntry Disembark Embark LaunchSRV DockSRV",
    "ship": "Loadout RefuelAll RefuelPartial RepairAll Repair Resurrect Died HullDamage HeatWarning HeatDamage "
            "Synthesis EngineerCraft MaterialCollected MaterialDiscarded MaterialDiscovered MaterialTrade LoadGame Shutdown Materials "
            "ShipyardSwap ShipyardBuy ShipyardSell ModuleBuy ModuleSell ModuleSwap ModuleStore ModuleRetrieve "
            "AfmuRepairs RebootRepair SelfDestruct FuelUsed",
    "noise": "Music ReceiveText SendText ShipLocker Backpack SuitLoadout Cargo FSSSignalDiscovered "
             "ReservoirReplenished Fileheader Rank Progress Reputation Statistics NpcCrewPaidWage Friends "
             "SquadronStartup Powerplay ShipTargeted UnderAttack NavRouteClear CommunityGoal Commander Passengers "
             "Missions EngineerProgress LoadoutEquipModule BackpackChange ModuleInfo Outfitting Shipyard Market "
             "StoredShips StoredModules CargoTransfer SwitchSuitLoadout FSSSignalDiscovered CrewMemberJoins "
             "CrewMemberQuits CrewMemberRoleChange WingJoin WingLeave WingAdd",
}
LOG_CAT = {e: cat for cat, events in _CAT_EVENTS.items() for e in events.split()}


def category(event):
    if event in LOG_CAT:
        return LOG_CAT[event]
    if event.startswith("Carrier"):
        return "carrier"
    return "other"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _num(v, fmt="{:,.0f}"):
    try:
        return fmt.format(v)
    except (TypeError, ValueError):
        return "?"


def _loc(ev, key):
    """The localised form of a field when the journal gave one."""
    v = ev.get(key + "_Localised")
    if v and not str(v).startswith("$"):
        return v
    v = ev.get(key)
    return v if v is not None and not str(v).startswith("$") else (str(v).strip("$;").replace("_", " ") if v else "")


_SYSTEMS = {}   # SystemAddress -> name, learned from the files read so far (for events that lack it)


def _short(ev, body):
    """A body name without its system prefix ('Sys A 1' -> 'A 1')."""
    system = ev.get("StarSystem") or ev.get("SystemName") or _SYSTEMS.get(ev.get("SystemAddress")) or ""
    if body and system and body.startswith(system + " "):
        return body[len(system) + 1:]
    return body or ""


def _words(event):
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", event).capitalize()


_SKIP = {"timestamp", "event", "SystemAddress", "MarketID", "BodyID", "ShipID", "MissionID", "EngineerID",
         "BlueprintID", "CarrierID", "ID", "StationFaction", "SystemFaction", "Factions", "Conflicts"}


def fallback(ev):
    """Event name in words plus up to four scalar fields, localised names preferred."""
    parts = [_words(ev.get("event") or "event")]
    for k, v in ev.items():
        if k in _SKIP or k.endswith("_Localised") or k.endswith("ID") or isinstance(v, (dict, list)) or v in (None, ""):
            continue
        if isinstance(v, str) and v.startswith("$"):
            v = ev.get(k + "_Localised") or v.strip("$;").replace("_", " ")
        elif k + "_Localised" in ev:
            v = ev[k + "_Localised"]
        if isinstance(v, float):
            v = f"{v:,.2f}"
        elif isinstance(v, bool):
            v = "yes" if v else "no"
        elif isinstance(v, int):
            v = f"{v:,}"
        parts.append(f"{k}: {v}")
        if len(parts) == 5:
            break
    return " · ".join(parts)


def _scan(ev):
    body = _short(ev, ev.get("BodyName")) or ev.get("BodyName", "")
    auto = "" if ev.get("ScanType") == "Detailed" else f" ({ev.get('ScanType', '').replace('NavBeaconDetail', 'nav beacon').lower()})" if ev.get("ScanType") else ""
    if ev.get("StarType"):
        s = (f"{body}: {ev['StarType']}{ev.get('Subclass', '')}{ev.get('Luminosity', '')} star"
             f" · {_num(ev.get('StellarMass'), '{:.2f}')} SM · {_num(ev.get('Age_MY'))} MY")
    elif ev.get("PlanetClass"):
        s = f"{body}: {ev['PlanetClass']}"
        if ev.get("MassEM") is not None:
            s += f" · {ev['MassEM']:.2f} EM"
        if ev.get("Landable"):
            g = ev.get("SurfaceGravity")
            s += " · landable" + (f" {g / 9.80665:.2f} g" if g else "")
        if ev.get("Atmosphere"):
            s += f" · {ev['Atmosphere']}"
        if ev.get("TerraformState") in ("Terraformable", "Terraforming", "Terraformed"):
            s += " · terraformable"
        if ev.get("Rings"):
            s += f" · {len(ev['Rings'])} ring{'s' if len(ev['Rings']) != 1 else ''}"
    else:
        return f"{body}{auto}"
    if ev.get("WasDiscovered") is False:
        s += " · 🏁 undiscovered"
    elif ev.get("WasDiscovered"):
        s += " · discovered"
    if ev.get("PlanetClass") and ev.get("WasMapped") is False:
        s += " · unmapped"
    return s + auto


def _signals(ev):
    body = _short(ev, ev.get("BodyName")) or ev.get("BodyName", "")
    sig = ", ".join(f"{s.get('Count', 0)} {_loc(s, 'Type').replace('Biological', 'bio').replace('Geological', 'geo').lower() if 'SAA_SignalType' in s.get('Type', '') else _loc(s, 'Type')}"
                    for s in ev.get("Signals") or [])
    gen = ", ".join(_loc(g, "Genus") for g in ev.get("Genuses") or [])
    return f"{body}: {sig or 'no signals'}" + (f" · {gen}" if gen else "")


def _organic(ev, bodies):
    system = _SYSTEMS.get(ev.get("SystemAddress"))
    body = bodies.get((ev.get("SystemAddress"), ev.get("Body"))) \
        or f"body #{ev.get('Body')}" + (f" in {system}" if system else "")
    var = _loc(ev, "Variant")
    var = var.split(" - ")[-1] if var else ""
    return f"{ev.get('ScanType', '')}: {_loc(ev, 'Species') or _loc(ev, 'Genus')}{' – ' + var if var else ''} on {body}"


def _sale(ev):
    n = len(ev.get("Discovered") or ev.get("Systems") or [])
    bonus = ev.get("Bonus")
    return f"Sold data from {n} system{'s' if n != 1 else ''} · {_num(ev.get('TotalEarnings'))} cr" + (f" (+{_num(bonus)} bonus)" if bonus else "")


def _bio_sale(ev):
    data = ev.get("BioData") or []
    total = sum((b.get("Value") or 0) + (b.get("Bonus") or 0) for b in data)
    return f"Sold {len(data)} sample{'s' if len(data) != 1 else ''} · {_num(total)} cr"


def _materials(ev):
    n = {k: sum(m.get("Count", 0) for m in ev.get(k) or []) for k in ("Raw", "Manufactured", "Encoded")}
    return f"Materials: {n['Raw']:,} raw · {n['Manufactured']:,} manufactured · {n['Encoded']:,} encoded"


def _trade(ev):
    p, r = ev.get("Paid") or {}, ev.get("Received") or {}
    return f"Traded {p.get('Quantity')} {_loc(p, 'Material')} for {r.get('Quantity')} {_loc(r, 'Material')}"


def _where(ev):
    s = f"At {ev.get('StarSystem', '?')}"
    if ev.get("Docked"):
        s += f", docked at {ev.get('StationName', '?')}"
    elif ev.get("Body") and ev.get("BodyType") != "Star":
        s += f", near {_short(ev, ev['Body'])}"
    return s


LOG_FORMAT = {
    # travel
    "FSDJump": lambda e: f"→ {e.get('StarSystem')} · {_num(e.get('JumpDist'), '{:.2f}')} ly · "
                         f"{_num(e.get('FuelUsed'), '{:.2f}')} t" + (" · boosted" if e.get("BoostUsed") else ""),
    "StartJump": lambda e: (f"Jumping to {e.get('StarSystem')} ({e.get('StarClass', '?')})"
                            if e.get("JumpType") == "Hyperspace" else "Entering supercruise"),
    "FSDTarget": lambda e: f"Targeted {e.get('Name')} ({e.get('StarClass', '?')})"
                           + (f" · {e['RemainingJumpsInRoute']} jump{'' if e['RemainingJumpsInRoute'] == 1 else 's'} left"
                              if e.get("RemainingJumpsInRoute") else ""),
    "Location": _where,
    "CarrierJump": lambda e: f"Carrier jumped to {e.get('StarSystem')}" + (" · aboard" if e.get("Docked") else ""),
    "SupercruiseEntry": lambda e: f"Supercruise in {e.get('StarSystem')}",
    "SupercruiseExit": lambda e: f"Dropped at {_short(e, e.get('Body'))} ({e.get('BodyType', '?')})",
    "SupercruiseDestinationDrop": lambda e: f"Dropped at {_loc(e, 'Type')}",
    "ApproachBody": lambda e: f"Approaching {_short(e, e.get('Body'))}",
    "LeaveBody": lambda e: f"Leaving {_short(e, e.get('Body'))}",
    "Touchdown": lambda e: f"Touched down on {_short(e, e.get('Body'))} · {_num(e.get('Latitude'), '{:.4f}')}, {_num(e.get('Longitude'), '{:.4f}')}",
    "Liftoff": lambda e: f"Lifted off {_short(e, e.get('Body'))}",
    "Docked": lambda e: f"Docked at {e.get('StationName')} ({e.get('StationType', '?')}) in {e.get('StarSystem')}",
    "Undocked": lambda e: f"Undocked from {e.get('StationName')}",
    "FuelScoop": lambda e: f"Scooped {_num(e.get('Scooped'), '{:.2f}')} t → {_num(e.get('Total'), '{:.2f}')} t",
    "JetConeBoost": lambda e: f"Neutron boost ×{_num(e.get('BoostValue'), '{:g}')}",
    "NavRoute": lambda e: "Route plotted",
    # exploration
    "Scan": _scan,
    "FSSDiscoveryScan": lambda e: f"Honk: {e.get('BodyCount')} bodies, {e.get('NonBodyCount')} other signals"
                                  + (f" · {e['Progress']:.0%} known" if isinstance(e.get("Progress"), (int, float)) else ""),
    "FSSAllBodiesFound": lambda e: f"All {e.get('Count')} bodies found in {e.get('SystemName')}",
    "FSSBodySignals": _signals,
    "SAASignalsFound": _signals,
    "SAAScanComplete": lambda e: f"Mapped {_short(e, e.get('BodyName'))} · {e.get('ProbesUsed')}/{e.get('EfficiencyTarget')} probes"
                                 + (" · efficient" if (e.get("ProbesUsed") or 99) <= (e.get("EfficiencyTarget") or 0) else ""),
    "ScanBaryCentre": lambda e: f"Barycentre #{e.get('BodyID')} · orbit {_num((e.get('SemiMajorAxis') or 0) / C, '{:,.1f}')} ls",
    "NavBeaconScan": lambda e: f"Nav beacon: {e.get('NumBodies')} bodies",
    "MultiSellExplorationData": _sale,
    "SellExplorationData": lambda e: (f"Sold data from {len(e.get('Systems') or [])} system"
                                      f"{'s' if len(e.get('Systems') or []) != 1 else ''}"
                                      + (f" ({len(e['Discovered'])} new)" if e.get("Discovered") else "")
                                      + f" · {_num(e.get('TotalEarnings'))} cr"
                                      + (f" (+{_num(e['Bonus'])} bonus)" if e.get("Bonus") else "")),
    "FSSSignalDiscovered": lambda e: _loc(e, "SignalName") or "Signal",
    # bio
    "SellOrganicData": _bio_sale,
    "CodexEntry": lambda e: f"📖 {_loc(e, 'Name')} ({_loc(e, 'SubCategory') or _loc(e, 'Category')})"
                            + (" · new" if e.get("IsNewEntry") else "")
                            + (f" · {_num(e['VoucherAmount'])} cr voucher" if e.get("VoucherAmount") else ""),
    # which craft: the SRV, a taxi, another commander's ship (multicrew), else your own (review 2026-10-23 S6-B4)
    "Disembark": lambda e: "Disembarked" + (f" on {_short(e, e.get('Body'))}" if e.get("OnPlanet") else "")
                           + (" from SRV" if e.get("SRV") else " from a taxi" if e.get("Taxi")
                              else " from another commander's ship" if e.get("Multicrew") else ""),
    "Embark": lambda e: "Embarked in " + ("SRV" if e.get("SRV") else "a taxi" if e.get("Taxi")
                                          else "another commander's ship" if e.get("Multicrew") else "your ship"),
    "LaunchSRV": lambda e: f"Launched {_loc(e, 'SRVType') or 'SRV'}",
    "DockSRV": lambda e: f"Docked {_loc(e, 'SRVType') or 'SRV'}",
    # ship
    "Loadout": lambda e: f"{(e.get('ShipName') or '').strip() or 'Ship'} ({e.get('Ship')}) · {_num(e.get('MaxJumpRange'), '{:.2f}')} ly"
                         + (f" · rebuy {_num(e['Rebuy'])} cr" if e.get("Rebuy") else ""),
    "RefuelAll": lambda e: f"Refuelled {_num(e.get('Amount'), '{:.1f}')} t for {_num(e.get('Cost'))} cr",
    "RefuelPartial": lambda e: f"Refuelled {_num(e.get('Amount'), '{:.1f}')} t for {_num(e.get('Cost'))} cr",
    "RepairAll": lambda e: f"Repaired for {_num(e.get('Cost'))} cr",
    "Resurrect": lambda e: f"Resurrected ({e.get('Option')}) · {_num(e.get('Cost'))} cr",
    "Died": lambda e: "Ship destroyed" + (f" by {e.get('KillerName_Localised') or e.get('KillerName')}" if e.get("KillerName") else ""),
    "HullDamage": lambda e: f"Hull at {_num(e.get('Health'), '{:.0%}')}",
    "HeatWarning": lambda e: "Heat warning",
    "HeatDamage": lambda e: "Heat damage",
    "Synthesis": lambda e: f"Synthesised {e.get('Name')}",
    "EngineerCraft": lambda e: f"{e.get('Engineer')}: {e.get('BlueprintName', '').replace('_', ' ')} G{e.get('Level')} on {e.get('Slot')}",
    "MaterialCollected": lambda e: f"+{e.get('Count')} {_loc(e, 'Name')}",
    "MaterialDiscarded": lambda e: f"−{e.get('Count')} {_loc(e, 'Name')}",
    "MaterialTrade": _trade,
    "Materials": _materials,
    "LoadGame": lambda e: f"Logged in as Cmdr {e.get('Commander')} · {e.get('ShipName') or e.get('Ship')}"
                          f" · {_num(e.get('Credits'))} cr" + (f" · {e['GameMode']}" if e.get("GameMode") else ""),
    "Shutdown": lambda e: "Game closed",
    # carrier
    "CarrierJumpRequest": lambda e: f"Carrier jump booked to {e.get('SystemName')}"
                                    + (f" / {e['Body']}" if e.get("Body") else "")
                                    + (f" at {e['DepartureTime'][11:16]} UTC" if e.get("DepartureTime") else ""),
    "CarrierJumpCancelled": lambda e: "Carrier jump cancelled",
    "CarrierStats": lambda e: f"{e.get('Name')} ({e.get('Callsign')}) · {e.get('FuelLevel')} t tritium"
                              + (f" · balance {_num((e.get('Finance') or {}).get('CarrierBalance'))} cr" if e.get("Finance") else ""),
    "CarrierLocation": lambda e: f"Carrier at {e.get('StarSystem')}",
    "CarrierDepositFuel": lambda e: f"Deposited {e.get('Amount')} t tritium · {e.get('Total')} t aboard",
    "CarrierCrewServices": lambda e: f"Carrier service {e.get('CrewRole')}: "
                                     + {"Activate": "installed", "Deactivate": "removed", "Pause": "suspended",
                                        "Resume": "resumed", "Replace": "crew replaced"}.get(e.get("Operation"), str(e.get("Operation"))),
}


def summary(ev, bodies=None):
    """One line describing a journal event; never raises."""
    name = ev.get("event", "")
    try:
        if name == "ScanOrganic":
            return _organic(ev, bodies or {})
        f = LOG_FORMAT.get(name)
        if f:
            return f(ev)
    except Exception:  # a missing or odd field: fall back rather than lose the row
        pass
    return fallback(ev)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

_NEW = re.compile(r"Journal\.(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})\.(\d+)\.log$")
_OLD = re.compile(r"Journal\.(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.(\d+)\.log$")


def file_key(path):
    """Sort key from a journal file name: ('2026-09-27T22:06:10', part). The name is in local time."""
    base = os.path.basename(path)
    m = _NEW.search(base)
    if m:
        return (f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}", int(m.group(5)))
    m = _OLD.search(base)
    if m:
        y, mo, d, h, mi, s, part = m.groups()
        return (f"20{y}-{mo}-{d}T{h}:{mi}:{s}", int(part))
    return None


def _utc_key(path, name_key):
    """A file's place in time as UTC 'YYYY-MM-DDTHH:MM:SS': its first line's timestamp, or its name's
    local time converted to UTC when the file is still empty."""
    ts = _FIRST_TS.get(path)
    if ts is None:
        try:
            with open(path, "rb") as f:
                head = f.read(512)
            m = re.search(rb'"timestamp":\s*"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', head)
            if m:
                ts = _FIRST_TS[path] = m.group(1).decode()
        except OSError:
            pass
    if ts:
        return ts
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.mktime(time.strptime(name_key, "%Y-%m-%dT%H:%M:%S"))))
    except (ValueError, OverflowError):
        return name_key


def journal_files(dirs):
    """Every journal file in `dirs`, oldest first by UTC start time, one per file name."""
    seen, out = set(), []
    for d in dirs:
        for p in glob(os.path.join(glob_escape(d), "Journal.*.log")):
            base = os.path.basename(p)
            k = file_key(p)
            if k and base not in seen:
                seen.add(base)
                out.append(((_utc_key(p, k[0]), k[1]), p))
    out.sort()
    return out


def window(files, days, now=None):
    """The files that can hold events from the last `days`: every file started since then (with a
    day of slack) plus the one before, which may run into the window."""
    now = time.time() if now is None else now
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - days * 86400 - 86400))
    first = next((i for i, (k, _) in enumerate(files) if k[0] >= since), len(files))
    return files[max(0, first - 1):]


_CACHE = OrderedDict()   # (path, size) -> {"lines": [...], "bodies": {...}}
_CACHE_MAX = 16
_SYSTEM_EVENTS = (b'"event":"FSDJump"', b'"event":"Location"', b'"event":"CarrierJump"', b'"event":"FSDTarget"')
_BODY_EVENTS = (b'"event":"Scan"', b'"event":"FSSBodySignals"', b'"event":"SAASignalsFound"',
                b'"event":"SAAScanComplete"', b'"event":"Touchdown"', b'"event":"Liftoff"', b'"event":"Disembark"',
                b'"event":"Embark"', b'"event":"ApproachBody"', b'"event":"LeaveBody"', b'"event":"Location"',
                b'"event":"SupercruiseExit"')
_BODIES = {}   # (SystemAddress, BodyID) -> short body name, learned from every file read so far
_FIRST_TS = {}   # path -> timestamp of its first line (file order), read once
# read_log runs in the server's thread pool and Log requests overlap (tail, scroll, a filter change, two
# tabs): the cache's check-then-act, iteration and eviction must not interleave ("OrderedDict mutated
# during iteration"). Held only around the cache, not while a file is read.
_LOCK = threading.Lock()


def _load(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return {"lines": [], "offsets": [], "bodies": {}}
    key = (path, size)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    try:
        with open(path, "rb") as f:
            data = f.read(size)
    except OSError:     # unreadable (permissions, a legacy folder gone): no rows from it, not a failed Log
        return {"lines": [], "offsets": [], "bodies": {}}
    end = data.rfind(b"\n") + 1       # the game may be mid-write on the last line
    # split on "\n" only, as the journal reader does (Journals.read_file), so each line's byte offset (its start) is
    # the uploader's source key ("<file>:<offset>"): the Log's upload marks join on it (S68). splitlines() would also
    # break on a stray "\r" and the offsets would drift. A "\r\n" line keeps its "\r": JSON allows it as whitespace.
    lines = data[:end].split(b"\n")[:-1] if end else []
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1
    for line in lines:
        if any(e in line for e in _SYSTEM_EVENTS):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("SystemAddress") and (ev.get("StarSystem") or ev.get("Name")):
                _SYSTEMS[ev["SystemAddress"]] = ev.get("StarSystem") or ev.get("Name")
    bodies = {}
    if b'"event":"ScanOrganic"' in data:  # ScanOrganic names its body by id only: learn the names
        for line in lines:
            if any(e in line for e in _BODY_EVENTS):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                name = ev.get("BodyName") or (ev.get("Body") if isinstance(ev.get("Body"), str) else None)
                if ev.get("BodyID") is not None and name:
                    bodies[(ev.get("SystemAddress"), ev["BodyID"])] = _short(ev, name)
        with _LOCK:
            _BODIES.update(bodies)
    # a session that starts on the planet names the body in an older file: fall back to what we know
    entry = {"lines": lines, "offsets": offsets, "bodies": ChainMap(bodies, _BODIES)}
    with _LOCK:
        for k in [k for k in _CACHE if k[0] == path]:
            del _CACHE[k]
        _CACHE[key] = entry
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return entry


_EVENT = re.compile(rb'"event"\s*:\s*"([^"]*)"')


def _event_name(line):
    """The event name without parsing the whole line (most lines are filtered out on this alone)."""
    i = line.find(b'"event":"')
    if i >= 0:
        j = line.find(b'"', i + 9)
        return line[i + 9:j].decode("ascii", "replace")
    m = _EVENT.search(line)
    return m.group(1).decode("ascii", "replace") if m else ""


def _values_text(ev):
    """Every value in an event (nested too) as one lower-case string, keys left out."""
    out = []
    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif v is not None:
            out.append(str(v))
    walk(ev)
    return " ".join(out).lower()


def parse_cursor(cursor):
    try:
        base, idx = cursor.rsplit("|", 1)
        return base, int(idx)
    except (AttributeError, ValueError):
        return None


def _row(ev, cursor, bodies):
    name = ev.get("event", "")
    system = (ev.get("StarSystem") or ev.get("SystemName") or (ev.get("System") if isinstance(ev.get("System"), str) else None)
              or _SYSTEMS.get(ev.get("SystemAddress")))
    body = ev.get("BodyName") or (ev.get("Body") if isinstance(ev.get("Body"), str) else None)
    if name == "ScanOrganic":
        body = bodies.get((ev.get("SystemAddress"), ev.get("Body")))
    elif body:
        body = _short(ev, body)
    return {"id": cursor, "ts": ev.get("timestamp", ""), "event": name, "cat": category(name),
            "summary": summary(ev, bodies), "id64": str(ev["SystemAddress"]) if ev.get("SystemAddress") else None,
            "system": system, "body": body,
            "raw": ev}


def read_log(dirs, days=7, before=None, after=None, limit=200, cats=None, q=None, noise=False, now=None, only=None):
    """Journal events newest first. `before`/`after` are cursors; `cats` a set of categories; `only` {file name: set of
    byte offsets}: those lines alone, in any category (the search still applies)."""
    files = journal_files(dirs)
    order = {os.path.basename(p): k for k, p in files}
    want = set(cats) if cats is not None else set(CATEGORIES) - {"noise"}
    if noise:
        want.add("noise")
    ql = q.lower().encode() if q else None
    # The tail continues from the last line AS SCANNED here: reading the file again afterwards could see
    # lines the game wrote in between, and they would never be returned. It is the last complete line of
    # the newest file that has one: a just-created journal with no complete line yet must not send the
    # tail back to an older cursor (rows returned twice) or leave it with none (never tailing).
    seen_newest = None
    rows, truncated = [], False

    def accept(entry, base, i):
        line, cursor, at = entry["lines"][i], f"{base}|{i}", entry["offsets"][i]
        if only is not None and at not in only.get(base, ()):
            return None
        name = _event_name(line)
        # notable stellar phenomena ride on FSS signal lines, which are otherwise noise
        cat = "phenomena" if b"Fixed_Event_Life" in line else category(name)
        if only is None and cat not in want:
            return None
        try:
            ev = json.loads(line)
        except ValueError:
            return None
        r = _row(ev, cursor, entry["bodies"])
        r["at"] = at
        if cat == "phenomena":
            r["cat"] = cat
            kind = re.search(r"Fixed_Event_Life_(\w+?);?\"", line.decode("utf-8", "replace"))
            kind = kind.group(1).lower() if kind else "?"
            r["summary"] = f"🌀 Notable stellar phenomena ({kind}) " + ("found by the FSS" if name == "FSSSignalDiscovered" else "reached")
        if ql:
            q = ql.decode()
            # the summary, the event name and every value (not the keys: "star" would match every
            # StarSystem field, "mapped" every WasMapped)
            if q not in r["summary"].lower() and q not in name.lower() and \
                    (q.encode() not in line.lower() or q not in _values_text(ev)):
                return None
        return r

    if after:
        cur = parse_cursor(after)
        if not cur or cur[0] not in order:
            return {"rows": [], "next": None, "newest": after, "reset": True}
        ck = order[cur[0]]
        cap = max(limit, 1000)
        for k, p in files:
            if k < ck:
                continue
            base, entry = os.path.basename(p), _load(p)
            seen_newest = _cursor_of(p, entry) or seen_newest    # files run oldest to newest
            start = cur[1] + 1 if base == cur[0] else 0
            for i in range(start, len(entry["lines"])):
                r = accept(entry, base, i)
                if r:
                    rows.append(r)
        if len(rows) > cap:
            rows, truncated = rows[-cap:], True
        rows.reverse()
        newest = seen_newest or after
        return {"rows": rows, "next": None, "newest": newest, "reset": truncated}

    chosen = window(files, days, now)
    cur = parse_cursor(before) if before else None
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime((time.time() if now is None else now) - days * 86400))
    done = False
    for k, p in reversed(chosen):
        base = os.path.basename(p)
        if cur and cur[0] in order and k > order[cur[0]]:
            continue
        entry = _load(p)
        if not cur and seen_newest is None:     # newest first: the first file with a complete line
            seen_newest = _cursor_of(p, entry)
        lines = entry["lines"]
        top = max(0, min(cur[1], len(lines))) if cur and base == cur[0] else len(lines)
        for i in range(top - 1, -1, -1):
            r = accept(entry, base, i)
            if not r:
                continue
            if r["ts"] and r["ts"] < since:
                done = True
                break
            rows.append(r)
            if len(rows) >= limit:
                break
        if done or len(rows) >= limit:
            break
    more = len(rows) >= limit and not done
    return {"rows": rows, "next": rows[-1]["id"] if more and rows else None,
            "newest": seen_newest or _newest(files), "reset": False}


def _cursor_of(path, entry):
    return f"{os.path.basename(path)}|{len(entry['lines']) - 1}" if entry["lines"] else None


def _newest(files):
    """The cursor of the last complete line in the newest file that has one (where a live tail continues from)."""
    for _, p in reversed(files):
        c = _cursor_of(p, _load(p))
        if c:
            return c
    return None
