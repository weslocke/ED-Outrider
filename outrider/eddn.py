"""EDDN, the Elite Dangerous Data Network: the messages Outrider sends (opt-in; PLAN-edmc-functionality parts B-F).
Pure: build(ev, session) turns one journal event into EDDN messages; outcome() says what an EDDN answer means. The
sending (gzip, one message per POST, the outbox) is outrider/uploads.py's loop with the server's sender.

The rules are EDDN's own (docs/Developers.md and each schema's README on its `live` branch; research notes in
project/research-edmc-2026-10-08/eddn.md). Some of the logic follows EDMarketConnector's plugins/eddn.py (Copyright (c)
EDCD, GPL v2 or later), whose rules these are.

Every message:
- carries the header EDDN asks for: uploaderID (the session's commander), softwareName "ED Outrider", its version,
  and the journal file's own gameversion / gamebuild (never left out: "" when unknown);
- has every *_Localised key removed, at any depth, and each schema's personal fields;
- adds StarSystem / StarPos only when the event's SystemAddress is where the session last jumped or logged in to
  (EDDN's location cross-check), else is not sent at all;
- adds horizons / odyssey only when LoadGame said them (a key LoadGame left out stays out);
- is never built for the beta, the Legacy game or a crew session (UploadHub checks that before asking).
"""
import json
import re

UPLOAD_URL = "https://eddn.edcd.io:4430/upload/"
SOFTWARE = "ED Outrider"
SCHEMA_BASE = "https://eddn.edcd.io/schemas"

# journal/1: the events it takes, and the keys it refuses (personal data; schema "disallowed")
JOURNAL_EVENTS = ("Docked", "FSDJump", "Scan", "Location", "SAASignalsFound", "CarrierJump")
JOURNAL_DROP = ("ActiveFine", "CockpitBreach", "BoostUsed", "FuelLevel", "FuelUsed", "JumpDist", "Latitude",
                "Longitude", "Wanted", "IsNewEntry", "NewTraitsDiscovered", "Traits", "VoucherAmount")
FACTION_DROP = ("HappiestSystem", "HomeSystem", "MyReputation", "SquadronFaction")
# stations on a planet's surface: their Docked gets the body you approached (Body, BodyType), as EDMC adds it (the
# journal's Docked has no body; the author, 2026-10-11)
PLANETARY_STATIONS = ("CraterOutpost", "CraterPort", "SurfaceStation", "OnFootSettlement", "PlanetaryConstructionDepot")


def schema_ref(name, version=1, test=False):
    return f"{SCHEMA_BASE}/{name}/{version}" + ("/test" if test else "")


def unlocalised(obj):
    """A copy without any key ending _Localised, at any depth."""
    if isinstance(obj, dict):
        return {k: unlocalised(v) for k, v in obj.items() if not k.endswith("_Localised")}
    if isinstance(obj, list):
        return [unlocalised(v) for v in obj]
    return obj


def envelope(name, message, session, software_version, version=1, test=False):
    """The whole EDDN message: $schemaRef, header, message (horizons / odyssey added when LoadGame said them)."""
    msg = dict(message)
    if session.horizons is not None:
        msg["horizons"] = session.horizons
    if session.odyssey is not None:
        msg["odyssey"] = session.odyssey
    return {"$schemaRef": schema_ref(name, version, test),
            "header": {"uploaderID": session.cmdr or "", "softwareName": SOFTWARE, "softwareVersion": software_version,
                       "gameversion": session.gameversion or "", "gamebuild": session.gamebuild or ""},
            "message": msg}


def journal_message(ev, session):
    """journal/1 for FSDJump, Location, CarrierJump, Docked, Scan, SAASignalsFound; None when it must not be sent
    (another system than the session's: a stalled journal, a delayed Scan)."""
    name = ev.get("event")
    if name not in JOURNAL_EVENTS:
        return None
    addr = ev.get("SystemAddress")
    if not session.located(addr):
        return None
    m = unlocalised({k: v for k, v in ev.items() if k not in JOURNAL_DROP})
    if isinstance(m.get("Factions"), list):
        m["Factions"] = [{k: v for k, v in f.items() if k not in FACTION_DROP} if isinstance(f, dict) else f
                         for f in m["Factions"]]
    m.setdefault("StarSystem", session.system)
    if name == "Docked" and m.get("StationType") in PLANETARY_STATIONS and session.body and "Body" not in m:
        m["Body"], m["BodyType"] = session.body, "Planet"
    if not m.get("StarPos"):
        m["StarPos"] = list(session.pos)
    if not m.get("StarSystem"):
        return None
    return m


# The FSS family (part C): schemas that take nothing they do not list, so each message is built from that list. event
# -> (schema, the key naming the system there, the keys it takes besides horizons/odyssey)
_PLACE = ("timestamp", "event", "StarPos", "SystemAddress")
FSS = {"FSSDiscoveryScan": ("fssdiscoveryscan", "SystemName", _PLACE + ("SystemName", "BodyCount", "NonBodyCount")),
       "FSSAllBodiesFound": ("fssallbodiesfound", "SystemName", _PLACE + ("SystemName", "Count")),
       "FSSBodySignals": ("fssbodysignals", "StarSystem", _PLACE + ("StarSystem", "BodyID", "BodyName", "Signals")),
       "ScanBaryCentre": ("scanbarycentre", "StarSystem", _PLACE + ("StarSystem", "BodyID", "SemiMajorAxis", "Eccentricity",
                                                                   "OrbitalInclination", "Periapsis", "OrbitalPeriod",
                                                                   "AscendingNode", "MeanAnomaly")),
       "NavBeaconScan": ("navbeaconscan", "StarSystem", _PLACE + ("StarSystem", "NumBodies"))}


def fss_message(ev, session):
    """(schema, message) for an FSS-family event, or None (not one; another system than the session's)."""
    spec = FSS.get(ev.get("event"))
    if not spec or not session.located(ev.get("SystemAddress")):
        return None
    schema, name_key, keys = spec
    m = {k: ev[k] for k in keys if k in ev}
    m[name_key] = ev.get(name_key) or session.system
    m["StarPos"] = list(session.pos)
    if "Signals" in m:   # each signal only its Type and Count (no Type_Localised)
        m["Signals"] = [{"Type": x.get("Type"), "Count": x.get("Count")} for x in m["Signals"] if isinstance(x, dict)]
    if not m[name_key]:
        return None
    return schema, m


NAVROUTE_WINDOW_S = 5     # NavRoute.json must be the one this NavRoute event wrote (EDMC's check)
NAVROUTE_TRIES = 11       # ...asked again on the lines after it while it is not (written late, NFS)
FILE_WAIT_S = 10          # ...and on the server's tick (idle()) when no line comes: given up after this long
SIGNAL_QUIET_S = 3        # a batch of FSSSignalDiscovered lines goes this long after its last line with none after it
SIGNAL_MAX_S = 300        # ...and dropped on the tick when it waited this long (EDDN stopped building meanwhile)


def _seconds(ts):
    from outrider.core import ts_seconds
    try:
        return ts_seconds(str(ts))
    except (TypeError, ValueError):
        return None


def _wait_start(session, key, ts, market_id=None):
    """A wait for the companion file an event wrote (NavRoute.json, Market.json...): the event's time, the MarketID the
    file must have (None: any), the lines tried, the line that started it (session.source: the idle() message's
    source) and when (session.now, the server's clock)."""
    session.pending[key] = {"ts": ts, "market": market_id, "tries": 0, "origin": session.source, "since": session.now}


def _wait_check(session, key, filename, line=True):
    """The file a wait is for, once it is that one: its time within NAVROUTE_WINDOW_S of the event's and the same
    MarketID (EDMC checks neither; NFS can serve an older file). None while waiting; the wait ends after
    NAVROUTE_TRIES later lines (line=True: a journal line asks) or FILE_WAIT_S by the server's clock."""
    import os
    wait = session.pending.get(key)
    if not wait or not session.dir:
        return None
    if line:
        wait["tries"] += 1
    try:
        with open(os.path.join(session.dir, filename), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = None
    a, b = _seconds((data or {}).get("timestamp")) if isinstance(data, dict) else None, _seconds(wait["ts"])
    if a is None or b is None or abs(a - b) > NAVROUTE_WINDOW_S or (wait["market"] is not None
                                                                       and data.get("MarketID") != wait["market"]):
        late = wait["since"] is not None and session.now is not None and session.now - wait["since"] > FILE_WAIT_S
        if wait["tries"] >= NAVROUTE_TRIES or late:
            session.pending.pop(key, None)
        return None
    session.pending.pop(key, None)
    return data


def navroute_message(ev, session):
    """navroute/1: the route NavRoute.json holds, once the file is the one this NavRoute event wrote (_wait_check). A
    NavRoute event starts the wait; later lines and the server's tick (idle) try the file again. None while waiting,
    and for a cleared route (NavRouteClear, no Route)."""
    if ev.get("event") == "NavRoute":
        _wait_start(session, "navroute", ev.get("timestamp"))
    elif ev.get("event") == "NavRouteClear":
        session.pending.pop("navroute", None)
        return None
    data = _wait_check(session, "navroute", "NavRoute.json")
    return _navroute_from(data) if data else None


def _navroute_from(data):
    route = [{"StarSystem": h.get("StarSystem"), "SystemAddress": h.get("SystemAddress"), "StarPos": h.get("StarPos"),
              "StarClass": h.get("StarClass")} for h in (data.get("Route") or []) if isinstance(h, dict)]
    route = [h for h in route if h["StarSystem"] and isinstance(h["SystemAddress"], int)
             and isinstance(h["StarPos"], list) and len(h["StarPos"]) == 3 and isinstance(h["StarClass"], str)]
    if not route:
        return None
    return {"timestamp": data.get("timestamp"), "event": "NavRoute", "Route": route}


CODEX_KEYS = ("timestamp", "event", "System", "StarPos", "SystemAddress", "Name", "Region", "EntryID", "Category",
              "Latitude", "Longitude", "SubCategory", "NearestDestination", "VoucherAmount", "Traits", "BodyID", "BodyName")


def codex_message(ev, session):
    """codexentry/1: the entry, the position after the cross-check; BodyName only from Status.json and BodyID only
    when that is the body you approached (close binaries: EDMC's rule). None when a required name is empty."""
    if ev.get("event") != "CodexEntry" or not session.located(ev.get("SystemAddress")):
        return None
    m = {k: ev[k] for k in CODEX_KEYS if k in ev}
    m["System"] = ev.get("System") or session.system
    m["StarPos"] = list(session.pos)
    if not all(m.get(k) for k in ("System", "Name", "Region", "Category", "SubCategory")) or \
            any(not t for t in m.get("Traits") or []):
        return None
    if "BodyName" not in m and session.status_body:
        m["BodyName"] = session.status_body
        if "BodyID" not in m and session.body == session.status_body and session.body_id is not None:
            m["BodyID"] = session.body_id
    return m


SETTLEMENT_KEYS = ("timestamp", "event", "StarSystem", "StarPos", "StationGovernment", "StationAllegiance",
                   "StationEconomies", "StationFaction", "StationServices", "StationEconomy", "SystemAddress", "Name",
                   "MarketID", "BodyID", "BodyName", "Latitude", "Longitude")


def settlement_message(ev, session):
    """approachsettlement/1 (MarketID when the event has one); None without a position on the body (a login at a
    port) or a place."""
    if ev.get("event") != "ApproachSettlement" or not session.located(ev.get("SystemAddress")):
        return None
    if ev.get("Latitude") is None or ev.get("Longitude") is None:
        return None
    m = unlocalised({k: ev[k] for k in SETTLEMENT_KEYS if k in ev})
    m["StarSystem"] = ev.get("StarSystem") or session.system
    m["StarPos"] = list(session.pos)
    if isinstance(m.get("StationFaction"), dict):
        m["StationFaction"] = {k: v for k, v in m["StationFaction"].items() if k in ("Name", "FactionState")}
    if isinstance(m.get("StationEconomies"), list):
        m["StationEconomies"] = [{k: v for k, v in e.items() if k in ("Name", "Proportion")}
                                 for e in m["StationEconomies"] if isinstance(e, dict)]
    return m


# ---- station data (part F): the journal folder's files, read when their event comes ----

STATION_FILES = {"Market": ("commodity", "Market.json"), "Outfitting": ("outfitting", "Outfitting.json"),
                 "Shipyard": ("shipyard", "Shipyard.json"), "FCMaterials": ("fcmaterials_journal", "FCMaterials.json")}
STATION_SCHEMAS = ("commodity", "outfitting", "shipyard", "fcmaterials_journal")
CATCHUP_MAX_S = 3600       # a line older than this never goes to EDDN, even caught up after a gap: its listeners take
#                            what arrives as current (the author's choice, 2026-10-09; EDSM keeps uploads.MAX_AGE_S)
COMMODITY_NAME = re.compile(r"^\$(.+)_name;$", re.I)
MODULE_PREFIX = re.compile(r"^Hpt_|^Int_|Armour_", re.I)
MODULE_OK = re.compile(r"(^Hpt_|^hpt_|^Int_|^int_|_Armour_|_armour_)")


def _station_file(ev, session, schema, filename):
    """The file a Market / Outfitting / Shipyard / FCMaterials event wrote, once it is that one (_wait_check). The event
    starts the wait; later lines and the server's tick (idle) try again. None while waiting."""
    if ev.get("event") in STATION_FILES and STATION_FILES[ev["event"]][0] == schema:
        _wait_start(session, schema, ev.get("timestamp"), ev.get("MarketID"))
    return _wait_check(session, schema, filename)


VISIT_ENDS = ("Docked", "Undocked", "Location", "CarrierJump", "LoadGame")


def _changed(session, schema, market_id, key):
    """Station data is sent once per visit: the same screen opened again in one docking, unchanged, is not sent twice
    (EDMC's dedup); every new docking sends it again, changed or not, since EDDN's readers date a station's data by
    it (the bug check of 2026-10-09: an unchanged market was never sent again while Outrider ran)."""
    sent = session.pending.setdefault("sent", {})
    k = f"{schema}:{market_id}"
    if sent.get(k) == key:
        return False
    sent[k] = key
    return True


def station_messages(ev, session):
    """[(schema, message)] for station data whose file is ready on this line (commodity/3, outfitting/2, shipyard/2,
    fcmaterials_journal/1), each only when it changed."""
    out = []
    if ev.get("event") in VISIT_ENDS:   # a new visit: its station data goes again, unchanged or not
        session.pending.pop("sent", None)
    for event, (schema, filename) in STATION_FILES.items():
        if schema not in session.pending and ev.get("event") != event:
            continue
        data = _station_file(ev, session, schema, filename)
        m = _station_message(schema, data, session) if data else None
        if m:
            out.append((schema, m))
    return out


def _bracket(v):
    """A market's stock / demand bracket: 0 to 3, or "" as the game writes it ("not normally sold here, but for sale
    now": EDDN's schema takes it as it is)."""
    return "" if v == "" else int(v or 0)


def _station_message(schema, data, session):
    """The message for one station file's contents, or None (nothing to say, or unchanged since the last one)."""
    mid, ts = data.get("MarketID"), data.get("timestamp")
    base = {"systemName": data.get("StarSystem") or session.system, "stationName": data.get("StationName"),
            "marketId": mid, "timestamp": ts}
    if schema == "commodity":
        items = []
        for it in data.get("Items") or []:
            m = COMMODITY_NAME.match(str(it.get("Name") or ""))
            if not m or "nonmarketable" in str(it.get("Category") or "").lower() or it.get("Legality"):
                continue
            try:
                items.append({"name": m.group(1), "meanPrice": int(it["MeanPrice"]), "buyPrice": int(it["BuyPrice"]),
                              "stock": int(it["Stock"]), "stockBracket": _bracket(it.get("StockBracket")),
                              "sellPrice": int(it["SellPrice"]), "demand": int(it["Demand"]),
                              "demandBracket": _bracket(it.get("DemandBracket"))})
            except (KeyError, TypeError, ValueError):
                continue
        msg = dict(base, commodities=items)
        if data.get("StationType"):
            msg["stationType"] = data["StationType"]
        if data.get("CarrierDockingAccess"):
            msg["carrierDockingAccess"] = data["CarrierDockingAccess"]
        key = sorted(json.dumps(i, sort_keys=True) for i in items)
    elif schema == "outfitting":
        mods = sorted({MODULE_PREFIX.sub(lambda x: x.group(0).capitalize(), str(it.get("Name") or ""))
                       for it in data.get("Items") or [] if isinstance(it, dict)}
                      - {"Int_PlanetApproachSuite", "Int_planetapproachsuite"})
        mods = [x for x in mods if MODULE_OK.search(x) and x.lower() != "int_planetapproachsuite"]
        if not mods:
            return None
        msg, key = dict(base, modules=mods), mods
    elif schema == "shipyard":
        ships = sorted({str(x.get("ShipType")) for x in data.get("PriceList") or [] if isinstance(x, dict) and x.get("ShipType")})
        if not ships:
            return None
        # no allowCobraMkIV: the schema has it, but it is about the commander (the pre-order), not the station, and
        # EDMC, EDDiscovery and EDDLite leave it out (the author, 2026-10-11)
        msg, key = dict(base, ships=ships), ships
    else:   # fcmaterials_journal
        items = [{k: it[k] for k in ("id", "Name", "Price", "Stock", "Demand") if k in it}
                 for it in data.get("Items") or [] if isinstance(it, dict)]
        msg = {"timestamp": ts, "event": "FCMaterials", "MarketID": mid, "CarrierName": data.get("CarrierName"),
               "CarrierID": data.get("CarrierID"), "Items": items}
        key = items
    if not msg.get("stationName", msg.get("CarrierName")) or mid is None:
        return None
    return msg if _changed(session, schema, mid, json.dumps(key, sort_keys=True)) else None


DOCKING = {"DockingGranted": ("dockinggranted", ("timestamp", "event", "MarketID", "StationName", "StationType", "LandingPad")),
           "DockingDenied": ("dockingdenied", ("timestamp", "event", "MarketID", "StationName", "StationType", "Reason"))}


def docking_message(ev):
    spec = DOCKING.get(ev.get("event"))
    if not spec or ev.get("MarketID") is None or not ev.get("StationName"):
        return None
    return spec[0], {k: ev[k] for k in spec[1] if k in ev}


SIGNAL_KEYS = ("timestamp", "SignalName", "SignalType", "IsStation", "USSType", "SpawningState", "SpawningFaction",
               "SpawningPower", "OpposingPower", "ThreatLevel")


def signals_message(ev, session):
    """fsssignaldiscovered/1: a run of FSSSignalDiscovered lines is gathered and sent as one message when the next
    other line comes (Odyssey writes them before the jump that takes you there, Horizons after it: either way the
    session is in that system by then). Signals of another system are dropped, the whole batch when its first is;
    mission targets never go (EDDN refuses them). This is how Spansh learns where fleet carriers are. A batch with no
    line after it goes on the server's tick after SIGNAL_QUIET_S (idle)."""
    if ev.get("event") == "FSSSignalDiscovered":
        if "signals" not in session.pending:
            session.pending["signals_since"] = {"origin": session.source, "at": session.now}
        session.pending.setdefault("signals", []).append(ev)
        if session.now is not None:
            session.pending["signals_since"]["at"] = session.now   # quiet counts from the last one
        return None
    batch = session.pending.pop("signals", None)
    session.pending.pop("signals_since", None)
    return _signals_from(batch, session)


def _signals_from(batch, session):
    if not batch or not session.located(batch[0].get("SystemAddress")):
        return None
    signals = [{k: x[k] for k in SIGNAL_KEYS if k in x} for x in batch
               if x.get("SystemAddress") == session.addr and x.get("USSType") != "$USS_Type_MissionTarget;"
               and x.get("SignalName")]
    if not signals:
        return None
    return {"event": "FSSSignalDiscovered", "timestamp": signals[0]["timestamp"], "SystemAddress": session.addr,
            "StarSystem": session.system, "StarPos": list(session.pos), "signals": signals}


def build(ev, session, software_version, test=False):
    """The EDDN messages a journal event makes: [(schema name, envelope)]."""
    out = []
    sig = signals_message(ev, session)   # first: a waiting batch goes out with the line that ends it
    if sig is not None:
        out.append(("fsssignaldiscovered", envelope("fsssignaldiscovered", sig, session, software_version, 1, test)))
    m = journal_message(ev, session)
    if m is not None:
        out.append(("journal", envelope("journal", m, session, software_version, 1, test)))
    f = fss_message(ev, session)
    if f is not None:
        out.append((f[0], envelope(f[0], f[1], session, software_version, 1, test)))
    for schema, make in (("codexentry", codex_message), ("approachsettlement", settlement_message),
                         ("navroute", navroute_message)):
        m = make(ev, session)
        if m is not None:
            out.append((schema, envelope(schema, m, session, software_version, 1, test)))
    d = docking_message(ev)
    if d is not None:
        out.append((d[0], envelope(d[0], d[1], session, software_version, 1, test)))
    versions = {"commodity": 3, "outfitting": 2, "shipyard": 2}
    for schema, m in station_messages(ev, session):
        out.append((schema, envelope(schema, m, session, software_version, versions.get(schema, 1), test)))
    return out


def idle(session, software_version, test=False):
    """What can go without a new journal line, on the server's tick: [(schema, envelope, the line it comes from)]. A
    companion file that arrived after its event's line (the game or NFS wrote it late, and nothing came after), and a
    batch of signals SIGNAL_QUIET_S after its last line, if you are in that system by then (Odyssey writes a jump's
    signals just before its FSDJump: a batch for the system you are jumping to waits for that line instead)."""
    out = []
    files = dict(STATION_FILES.values(), navroute="NavRoute.json")
    versions = {"commodity": 3, "outfitting": 2, "shipyard": 2}
    for key, filename in files.items():
        wait = session.pending.get(key)
        if not wait or not wait.get("origin"):
            continue
        if wait["since"] is not None and session.now is not None and session.now - wait["since"] > FILE_WAIT_S:
            session.pending.pop(key, None)   # waited too long (EDDN stopped building meanwhile): not sent late
            continue
        origin = wait["origin"]
        data = _wait_check(session, key, filename, line=False)
        if not data:
            continue
        m = _navroute_from(data) if key == "navroute" else _station_message(key, data, session)
        if m:
            out.append((key, envelope(key, m, session, software_version, versions.get(key, 1), test), origin))
    since = session.pending.get("signals_since") or {}
    if session.pending.get("signals") and since.get("at") is not None and session.now is not None \
            and session.now - since["at"] > SIGNAL_MAX_S:   # left over from before EDDN stopped building: not sent
        session.pending.pop("signals", None)
        session.pending.pop("signals_since", None)
    if session.pending.get("signals") and since.get("origin") and since.get("at") is not None and session.now is not None \
            and session.now - since["at"] >= SIGNAL_QUIET_S \
            and session.located(session.pending["signals"][0].get("SystemAddress")):
        m = _signals_from(session.pending.pop("signals"), session)
        session.pending.pop("signals_since", None)
        if m:
            out.append(("fsssignaldiscovered", envelope("fsssignaldiscovered", m, session, software_version, 1, test),
                        since["origin"]))
    return out


def quiet(ev, session):
    """A live line EDDN does not build (another uploader sends EDDN now): what EDDN waited on is theirs to send, and a
    docking here is a visit EDDN did not see. Dropped, so none of it goes late once EDDN builds again."""
    for key in ("signals", "signals_since", "navroute", *STATION_SCHEMAS):
        session.pending.pop(key, None)
    if ev.get("event") in VISIT_ENDS:
        session.pending.pop("sent", None)


# ---- EDDN's answers (docs/Developers.md "Server responses") ----

def outcome(status):
    """(state, retry_in) for an EDDN answer: 200 sent; 400 / 426 / 413 dropped for good (never retried: EDDN's rule);
    408 / 429 / 5xx and anything else queued again after a minute or more."""
    if status == 200:
        return "sent", None
    if status in (400, 413, 426):
        return "dropped", None
    return "queued", 60 if status not in (429, 503) else 120


SCHEMA_RE = re.compile(r"/schemas/([a-z_]+)/")


def schema_of(ref):
    m = SCHEMA_RE.search(ref or "")
    return m.group(1) if m else None


class SchemaHold:
    """EDMC's killswitch, ours: a schema EDDN refused three times within an hour is not sent again until Outrider
    restarts (a game update EDDN does not take yet; its new release must catch up first). Rows of it are dropped."""

    def __init__(self, limit=3, window=3600):
        self.limit, self.window, self.refusals, self.held = limit, window, {}, {}

    def refused(self, schema, now, why, status=None):
        """A refusal of `schema`. 426 (EDDN no longer takes that schema version) holds it at once: every message of
        it would be refused the same way."""
        times = [t for t in self.refusals.get(schema, []) if now - t < self.window] + [now]
        self.refusals[schema] = times
        if len(times) >= self.limit or status == 426:
            self.held[schema] = why

    def is_held(self, schema):
        return self.held.get(schema)

