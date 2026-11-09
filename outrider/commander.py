"""The Commander view: who you are in the game (ranks, assets, the fleet), what you own, what engineering takes, the
missions you hold, and how your combat and mining sessions went. All of it from the journals as Outrider reads them:
`Journals.handle_commander` (ed_outrider.py) folds each line it is given into the meta keys of `COMMANDER_META` and the
`play_activity` table (one row per login), with the `*_apply` functions here; the GETs render what is kept with the
other functions here. Everything is pure. Journal-derived: a re-read rebuilds it. The blueprints come from
resources/blueprints.json.

What the journal does not state is not shown: a stored ship appears once the game has listed it (the shipyard's
StoredShips; ships bought, sold, swapped, sent for or renamed since are folded in), stored modules as outfitting last
listed them (modules stored, taken, sent for or sold from storage since are folded in), suit loadouts once created or worn (deleted ones go), and a mission's progress only where the game logs
it (cargo deliveries) or the journal's own kills count it (a massacre mission's: worded "counted", the game's redirect
overrides it).
"""
import json
import os
import re
import time

from . import RESOURCES_DIR, materials, shipyard_links
from .core import iso_ts, ts_seconds

BLUEPRINTS_FILE = os.path.join(RESOURCES_DIR, "blueprints.json")
SESSIONS_MAX = 40   # the sessions listed, the newest...
SESSIONS_DAYS = 30  # ...of those whose login is at most this old (as History's default)

# ---- what is folded, from which events (Journals.handle_commander) ----

# meta key -> the events folded into it (each fresh()-guarded on "cmdr:<key>": a line older than the newest folded is
# ignored, as a legacy folder read late would otherwise put back a sold ship or a mission handed in). A line may feed
# several folds (a Bounty: a massacre mission's kills and the vouchers) and a login's counts too (ACTIVITY_EVENTS)
FOLD_EVENTS = {
    "reputation": ("Reputation",),
    "powerplay": ("Powerplay", "PowerplayJoin", "PowerplayLeave", "PowerplayDefect", "PowerplayRank", "PowerplayMerits"),
    "squadron": ("SquadronStartup", "JoinedSquadron", "LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"),
    "stored_ships": ("StoredShips", "ShipyardBuy", "ShipyardNew", "ShipyardSell", "ShipyardSwap", "ShipyardTransfer",
                     "SellShipOnRebuy", "SetUserShipName", "Loadout"),
    "stored_modules": ("StoredModules", "ModuleStore", "MassModuleStore", "ModuleBuy", "ModuleRetrieve", "FetchRemoteModule",
                       "ModuleSellRemote"),
    "ship_locker": ("ShipLocker",),
    "suit_loadouts": ("SuitLoadout", "CreateSuitLoadout", "DeleteSuitLoadout", "RenameSuitLoadout", "LoadoutEquipModule",
                      "LoadoutRemoveModule", "UpgradeSuit", "UpgradeWeapon"),
    "engineers": ("EngineerProgress",),
    "missions": ("Missions", "MissionAccepted", "MissionCompleted", "MissionFailed", "MissionAbandoned", "MissionRedirected",
                 "CargoDepot", "Bounty", "FactionKillBond"),
    # round 10's S9: the bounty vouchers and combat bonds you hold, per faction (lost at a death)
    "vouchers": ("Bounty", "FactionKillBond", "CapShipBond", "RedeemVoucher", "Died"),
    # round 10's S19: the Community Goals you have joined (each CommunityGoal line lists them all)
    "community_goals": ("CommunityGoal", "CommunityGoalDiscard", "CommunityGoalReward"),
}
COMMANDER_META = tuple(FOLD_EVENTS)
FOLD_OF = {}   # event -> the meta keys it is folded into, in FOLD_EVENTS' order
for _key, _names in FOLD_EVENTS.items():
    for _e in _names:
        FOLD_OF[_e] = FOLD_OF.get(_e, ()) + (_key,)
# fighting and mining, counted per login in play_activity (a LoadGame opens the row)
ACTIVITY_EVENTS = ("Bounty", "FactionKillBond", "PVPKill", "CapShipBond", "Died", "Interdicted", "RedeemVoucher",
                   "MiningRefined", "ProspectedAsteroid", "AsteroidCracked", "LaunchDrone", "MarketSell")
# read by other handlers (the login, ranks, statistics), shown here: they only move commander_version (a ship's Loadout,
# read by others too, is folded: the hot flag)
SHOWN_EVENTS = ("LoadGame", "Rank", "Progress", "Promotion", "Statistics")
EVENTS = tuple(dict.fromkeys(tuple(FOLD_OF) + ACTIVITY_EVENTS + SHOWN_EVENTS))
# written as the game loads, around LoadGame: not play (ed_outrider's LOGIN_EVENTS), so not where a session ended.
# CommunityGoal too: within two minutes of the login in 73 of the author's 78 journals that hold one, then every few
# minutes while you are signed up to a goal, whatever you do
LOGIN_SNAPSHOTS = ("Missions", "Reputation", "EngineerProgress", "Powerplay", "SquadronStartup", "ShipLocker", "CommunityGoal")
# the Statistics sections the profile reads (meta statistics keeps them beside Exploration and Exobiology)
STAT_SECTIONS = ("Bank_Account", "Exploration", "Exobiology", "Trading", "Mining", "Combat")


def apply(key, state, ev, here=None):
    """One line folded into the meta key's state: the new state (None: nothing kept). here: {system, station, market,
    login} where you are (the ships and modules stored or sent for here, a massacre kill's system) and the login on
    record (Journals.commander's: the merits gained this login, and the Loadout written at it says whether the ship is
    hot)."""
    if key == "stored_ships":
        return fleet_apply(state, ev, here)
    if key == "stored_modules":
        return modules_apply(state, ev, here)
    if key in ("missions", "powerplay"):   # a kill's system; the login a merit is gained in
        return _APPLY[key](state, ev, here)
    return _APPLY[key](state, ev)


def reputation_apply(state, ev):
    """Reputation (at login): the superpowers' standing, %."""
    return dict({k: ev[k] for k in ("Federation", "Empire", "Alliance", "Independent") if isinstance(ev.get(k), (int, float))},
                ts=ev["timestamp"])


# Powerplay's weekly cycle ends Thursday 07:00 UTC (Frontier's weekly tick). No journal line marks it: none of the 59
# Powerplay, 335 PowerplayMerits and 10 PowerplayRank lines in the author's journals (2025-11 to 2026-07) says
# anything about a cycle, so it is a constant here: seconds after a Thursday's midnight (1970-01-01 was a Thursday)
PP_CYCLE_TICK = 7 * 3600
PP_CYCLE_S = 7 * 86400


def pp_cycle_start(t):
    """The start of the Powerplay cycle a time (epoch s) is in: the last Thursday 07:00 UTC at or before it."""
    return (int(t) - PP_CYCLE_TICK) // PP_CYCLE_S * PP_CYCLE_S + PP_CYCLE_TICK


def power_apply(state, ev, here=None):
    """Powerplay: the login's pledge, then joining, leaving, defecting, a new rank, merits gained. None unpledged.
    Round 10's S19: PowerplayMerits' MeritsGained are summed for the cycle they fall in (`merits_cycle` since
    `cycle_start`, pp_cycle_start) and for the login on record (`merits_login` since `login_ts`: here's login); a pledge
    to another power starts both again."""
    name, st = ev["event"], dict(state or {})
    if name == "PowerplayLeave":
        return None
    if name in ("Powerplay", "PowerplayJoin", "PowerplayDefect"):
        # a join names the power alone, and the game writes its PowerplayRank (0) just before it, at the same second
        # (real journals, 2025-11-30): what the line leaves out stays, for the same power
        power = ev.get("ToPower") if name == "PowerplayDefect" else ev.get("Power")
        same = power == st.get("power")
        st = dict({k: st[k] for k in ("merits_cycle", "cycle_start", "merits_login", "login_ts") if same and k in st},
                  power=power, rank=ev.get("Rank", st.get("rank") if same else None),
                  merits=ev.get("Merits", st.get("merits") if same else None))
    elif name == "PowerplayRank" and isinstance(ev.get("Rank"), int):
        st["rank"] = ev["Rank"]
    elif name == "PowerplayMerits":
        if isinstance(ev.get("TotalMerits"), int):
            st["merits"] = ev["TotalMerits"]
        gained = ev.get("MeritsGained")
        if isinstance(gained, int) and not isinstance(gained, bool):
            start = iso_ts(pp_cycle_start(ts_seconds(ev["timestamp"])))
            if st.get("cycle_start") != start:
                st.update(cycle_start=start, merits_cycle=0)
            st["merits_cycle"] = (st.get("merits_cycle") or 0) + gained
            login = (here or {}).get("login")
            if st.get("login_ts") != login:
                st.update(login_ts=login, merits_login=0)
            st["merits_login"] = (st.get("merits_login") or 0) + gained
    if not st.get("power"):
        st["power"] = ev.get("Power")
    return dict(st, ts=ev["timestamp"]) if st.get("power") else None


def power_gains(pp, login_ts, now=None):
    """The merits gained this cycle and this login ({cycle, login}: None when none is on record for the cycle now or
    for that login), from power_apply's state."""
    now = time.time() if now is None else now
    pp = pp or {}
    cycle = pp.get("merits_cycle") if pp.get("cycle_start") == iso_ts(pp_cycle_start(now)) else None
    login = pp.get("merits_login") if login_ts and pp.get("login_ts") == login_ts else None
    return {"cycle": cycle or None, "login": login or None}


def squadron_apply(state, ev):
    """Your squadron: the login's, one joined; None once left, kicked or disbanded."""
    if ev["event"] in ("SquadronStartup", "JoinedSquadron") and ev.get("SquadronName"):
        return {"name": ev["SquadronName"], "ts": ev["timestamp"]}
    return None


def locker_apply(state, ev):
    """The ship locker whole: a ShipLocker line with its lists (the game writes them at login and at most changes, but
    not always: ShipLocker.json, Journals.read_locker_file, has them then) or the file itself. A line without the lists
    keeps what is kept."""
    if not any(isinstance(ev.get(k), list) for k, _ in LOCKER_KINDS):
        return state
    return dict({k: ev[k] for k, _ in LOCKER_KINDS if isinstance(ev.get(k), list)}, ts=ev["timestamp"])


def _text(ev, key):
    """A journal text: its localised form when the game gave one, else the symbol tidied ("$x_name;" -> "x")."""
    v = ev.get(key + "_Localised") or ev.get(key)
    if not isinstance(v, str):
        return None
    return re.sub(r"^\$|_name;$|;$", "", v, flags=re.I) if v.startswith("$") else v


# ---- inventory: ships, stored modules, the ship locker, suit loadouts ----

LOCKER_KINDS = (("Items", "Goods"), ("Components", "Assets"), ("Data", "Data"), ("Consumables", "Consumables"))


def fleet_apply(state, ev, here=None):
    """Your stored ships (not the one you fly: State takes it from fleet_loadouts), as inara._fleet reads the same
    events: the shipyard's StoredShips lists them whole (where each is, its value, what moving it costs); a ship
    bought (the old one stored here or sold), swapped (the old one stored here), sold (also on a rebuy), sent for
    (ShipyardTransfer: here when it arrives) or renamed is folded in since. {listed: {ts, system, station} (the last
    list), ships: {id: {id, type, type_name, name, ident, system, station, value, value_ts, hot, transfer_cost,
    transfer_s, in_transit, arrive_ts}}, hot: {id: bool}, hot_login}.

    hot: whether the game marks each ship hot (wanted), the one you fly too, by the latest line that says it: a
    StoredShips entry's `Hot` (every entry has it: real journals, 2026-10-14) and, for the ship you fly, the Loadout's
    `Hot`, which no real journal had (none was hot): by Frontier's journal manual it is there "if wanted at startup", so
    the login's Loadout without it says not hot (hot_login: the login whose Loadout was read), a later one only when it
    is there."""
    st = state or {"listed": None, "ships": {}}
    ships, name, ts = st["ships"], ev["event"], ev["timestamp"]
    hot = st.setdefault("hot", {})
    here = here or {}

    def store(sid, kind, kind_name=None, **kw):
        if sid is None:
            return
        row = ships.setdefault(str(sid), {"id": sid, "name": None, "ident": None, "value": None, "value_ts": None})
        row.update(type=kind or row.get("type"), type_name=kind_name or row.get("type_name"), system=here.get("system"),
                   station=here.get("station"), market=here.get("market"), transfer_cost=None, transfer_s=None, in_transit=False, arrive_ts=None,
                   hot=hot.get(str(sid), False))
        row.update(kw)
    if name == "Loadout" and ev.get("ShipID") is not None:
        login, sid = here.get("login"), str(ev["ShipID"])
        at_login = bool(login) and ts >= login and st.get("hot_login") != login
        if isinstance(ev.get("Hot"), bool):
            hot[sid] = ev["Hot"]
        elif at_login:
            hot[sid] = False                  # the login's Loadout without it: not wanted at startup
        if at_login:
            st["hot_login"] = login
    elif name == "StoredShips":
        old, ships = ships, {}
        st.update(listed={"ts": ts, "system": ev.get("StarSystem"), "station": ev.get("StationName")}, ships=ships)
        for key, local in (("ShipsHere", True), ("ShipsRemote", False)):
            for s in ev.get(key) or []:
                if not isinstance(s, dict) or s.get("ShipID") is None:
                    continue
                ships[str(s["ShipID"])] = {
                    "id": s["ShipID"], "type": s.get("ShipType"), "type_name": s.get("ShipType_Localised"),
                    "name": (s.get("Name") or "").strip() or None, "ident": (old.get(str(s["ShipID"])) or {}).get("ident"),
                    "system": ev.get("StarSystem") if local else s.get("StarSystem"),
                    "station": ev.get("StationName") if local else None, "value": s.get("Value"), "value_ts": ts,
                    # a remote ship's station: by its market (State.with_stations; the list names none)
                    "market": ev.get("MarketID") if local else s.get("ShipMarketID"),
                    "hot": bool(s.get("Hot")), "transfer_cost": None if local else s.get("TransferPrice"),
                    "transfer_s": None if local else s.get("TransferTime"), "in_transit": bool(s.get("InTransit")), "arrive_ts": None}
                was = old.get(str(s["ShipID"])) or {}
                if s.get("InTransit") and was.get("arrive_ts"):
                    # the list says in transit only: the fold's transfer knows where to and when (as StoredModules;
                    # review 2026-10-20 L5: else it stayed "on its way" until another shipyard was opened)
                    ships[str(s["ShipID"])].update({k: was.get(k) for k in ("system", "station", "market", "arrive_ts")})
                hot[str(s["ShipID"])] = bool(s.get("Hot"))
    elif name in ("ShipyardBuy", "ShipyardSwap", "ShipyardSell", "SellShipOnRebuy"):
        if ev.get("StoreShipID") is not None:
            store(ev["StoreShipID"], ev.get("StoreOldShip"))
        sold = ev.get("SellShipID", ev.get("SellShipId"))   # SellShipOnRebuy writes "SellShipId"
        if sold is not None:
            ships.pop(str(sold), None)
            hot.pop(str(sold), None)
        if name == "ShipyardSwap" and ev.get("ShipID") is not None:
            ships.pop(str(ev["ShipID"]), None)              # the one you fly now
    elif name == "ShipyardNew" and ev.get("NewShipID") is not None:
        ships.pop(str(ev["NewShipID"]), None)
    elif name == "ShipyardTransfer" and ev.get("ShipID") is not None:
        wait = ev.get("TransferTime") if isinstance(ev.get("TransferTime"), (int, float)) else 0
        store(ev["ShipID"], ev.get("ShipType"), ev.get("ShipType_Localised"), in_transit=wait > 0,
              arrive_ts=iso_ts(ts_seconds(ts) + wait) if wait > 0 else None)
    elif name == "SetUserShipName" and str(ev.get("ShipID")) in ships:
        ships[str(ev["ShipID"])].update(name=(ev.get("UserShipName") or "").strip() or None, ident=ev.get("UserShipId") or None)
    return st


def ships(fleet, loadouts=(), now=None):
    """Your ships: the one you fly (the newest Loadout: loadouts are fleet_loadouts' rows {ship_id, name, ship_type,
    ident, ts, value, loadout}, the newest first) and those stored (fleet_apply's), each worth its newest figure (a
    Loadout newer than the list gives it), each with `links` {edsy, coriolis}: its latest Loadout's build
    (shipyard_links), None for a ship never boarded since the journals begin. {ts (of the last list), here (where it
    was made), ships: [...]}."""
    now = time.time() if now is None else now
    fleet = fleet or {"listed": None, "ships": {}}
    hot = fleet.get("hot") or {}   # fleet_apply's: the latest the game said of each ship, the one you fly too
    worth = {r["ship_id"]: r for r in loadouts if r.get("value")}
    # a stored ship's name and ident from its latest Loadout when the list has none: a swap or a purchase stores the
    # ship you leave with neither, and StoredShips has no ident (complete review 2026-10-30); loadouts are newest first
    named = {}
    for r in loadouts:
        named.setdefault(r["ship_id"], r)
    builds = {r["ship_id"]: r["loadout"] for r in loadouts if r.get("loadout")}

    def links(sid):
        try:
            return shipyard_links.links(json.loads(builds[sid])) if sid in builds else None
        except ValueError:
            return None
    cur = loadouts[0] if loadouts else None
    rows = []
    if cur:
        rows.append({"id": cur["ship_id"], "type": cur["ship_type"], "name": cur["name"] or None, "ident": cur["ident"] or None,
                     "current": True, "system": None, "station": None, "value": cur.get("value") or None,
                     "hot": bool(hot.get(str(cur["ship_id"]))),
                     "transfer_cost": None, "transfer_s": None, "in_transit": False, "links": links(cur["ship_id"])})
    for s in fleet["ships"].values():
        if cur and s["id"] == cur["ship_id"]:
            continue
        lo = worth.get(s["id"])
        value = lo["value"] if lo and lo["ts"] >= (s.get("value_ts") or "") else s.get("value")
        arriving = s.get("in_transit") and (not s.get("arrive_ts") or ts_seconds(s["arrive_ts"]) > now)
        lo_n = named.get(s["id"]) or {}
        rows.append({"id": s["id"], "type": s.get("type"), "type_name": s.get("type_name"), "name": s.get("name") or lo_n.get("name") or None,
                     "ident": s.get("ident") or lo_n.get("ident") or None, "current": False, "system": s.get("system"), "station": s.get("station"),
                     "market": s.get("market"),
                     "value": value, "hot": bool(hot.get(str(s["id"]), s.get("hot"))), "transfer_cost": s.get("transfer_cost"),
                     "transfer_s": s.get("transfer_s"), "in_transit": bool(arriving), "links": links(s["id"])})
    listed = fleet.get("listed")
    return {"ts": listed and listed["ts"], "ships": rows,
            "here": {"system": listed["system"], "station": listed["station"]} if listed else None}


_RATING = {1: "E", 2: "D", 3: "C", 4: "B", 5: "A"}
_HARDPOINT = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4}
_MOUNT = {"fixed": "Fixed", "gimbal": "Gimballed", "turret": "Turreted"}


def module_label(symbol, localised=None):
    """A stored module from its journal symbol ("$int_hyperdrive_size5_class5_name;"): (name, size, rating, mount).
    The name is the game's own when it gave one, else the symbol's words; size and rating are the symbol's
    (_size5 _class5: 5A), a weapon's size its mount point's (small 1 to huge 4), the mount fixed, gimballed or
    turreted."""
    it = re.sub(r"^\$|_name;$", "", str(symbol or ""), flags=re.I).lower()
    size = rating = mount = None
    m = re.search(r"_size(\d)", it)
    if m:
        size = int(m.group(1))
    m = re.search(r"_class(\d)", it)
    if m:
        rating = _RATING.get(int(m.group(1)))
    m = re.search(r"_(fixed|gimbal|turret)(?:_|$)", it)
    if m:
        mount = _MOUNT[m.group(1)]
    m = re.search(r"_(tiny|small|medium|large|huge)(?:_|$)", it)
    if m and it.startswith("hpt_"):
        size = _HARDPOINT[m.group(1)]
    if isinstance(localised, str) and localised.strip():
        return localised.strip(), size, rating, mount
    words = re.sub(r"^(int|hpt)_|_size\d|_class\d|_(fixed|gimbal|turret|tiny|small|medium|large|huge)(?=_|$)", "", it)
    return " ".join(words.split("_")).strip().capitalize() or "?", size, rating, mount


# what a stored module keeps of the line that stored it (ModuleStore, MassModuleStore's items, ModuleRetrieve's swapped-out
# one, ModuleBuy's old one): its engineering and hot flag, when the line has them
_MODULE_KEEP = ("Hot", "EngineerModifications", "Level", "Quality")


def _arrived(m, ts):
    """A stored module that can be taken from where it is at `ts` (not on its way: in transit with no arrival known, or
    arriving after it)."""
    return not m.get("InTransit") or bool(m.get("_arrive")) and m["_arrive"] <= ts


def modules_apply(state, ev, here=None):
    """Your stored modules: the StoredModules list whole (outfitting writes it when you open it, and again after most
    changes), then what is stored, taken, sent for or sold from storage until the next list replaces it. {Items: the
    list's items (the journal's own keys; a module stored since has no StorageSlot nor BuyPrice, one sent for keeps
    `_arrive`, its arrival), ts (the last list), changed (the last line folded since, None when none)}.

    Field names checked against real journals (2026-10-14): ModuleStore (StoredItem, MarketID, Hot, the engineering),
    ModuleRetrieve (RetrievedItem, MarketID, SwapOutItem: the module it replaced, stored), ModuleBuy's StoredItem (the
    old module stored, not sold; SellItem is sold, and ModuleSell sells from the ship: neither touches storage) and
    FetchRemoteModule (StorageSlot, TransferTime). ModuleSellRemote (StorageSlot) and MassModuleStore (Items) had no
    real line: they follow Frontier's journal manual."""
    name, ts, here = ev["event"], ev["timestamp"], here or {}
    if name == "StoredModules":
        # one sent for before the list: the list says in transit only, the fold knows where to and when it arrives
        sent = {m["StorageSlot"]: m for m in (state or {}).get("Items") or [] if m.get("_arrive") and m.get("StorageSlot") is not None}
        items = []
        for m in ev.get("Items") or []:
            if isinstance(m, dict):
                was = sent.get(m.get("StorageSlot")) if m.get("InTransit") else None
                items.append(dict(m, **{k: was.get(k) for k in ("StarSystem", "MarketID", "_arrive")}) if was else m)
        return {"Items": items, "ts": ts, "changed": None}
    st = dict(state or {"Items": [], "ts": None})
    items = list(st.get("Items") or [])
    market = ev.get("MarketID") or here.get("market")

    def stored(symbol, localised, src):
        if not symbol:
            return False
        m = {"Name": symbol, "StarSystem": here.get("system"), "MarketID": market, "TransferCost": 0, "TransferTime": 0}
        if localised:
            m["Name_Localised"] = localised
        m.update({k: src[k] for k in _MODULE_KEEP if k in src})
        items.append(m)
        return True

    def slot(n):
        return next((i for i, m in enumerate(items) if n is not None and m.get("StorageSlot") == n), None)
    changed = False
    if name == "ModuleStore":
        changed = stored(ev.get("StoredItem"), ev.get("StoredItem_Localised"), ev)
    elif name == "MassModuleStore":
        for m in ev.get("Items") or []:
            if isinstance(m, dict):
                changed = stored(m.get("Name"), m.get("Name_Localised"), m) or changed
    elif name == "ModuleBuy":
        changed = stored(ev.get("StoredItem"), ev.get("StoredItem_Localised"), {})
    elif name == "ModuleRetrieve":
        want = str(ev.get("RetrievedItem") or "").lower()
        here_ = [i for i, m in enumerate(items) if str(m.get("Name") or "").lower() == want and m.get("MarketID") == market
                 and _arrived(m, ts)]
        # the same module when several match: the same engineering first
        same = [i for i in here_ if all(items[i].get(k) == ev.get(k) for k in ("EngineerModifications", "Level"))]
        if same or here_:
            items.pop((same or here_)[0])
            changed = True
        changed = stored(ev.get("SwapOutItem"), ev.get("SwapOutItem_Localised"), {}) or changed
    elif name == "FetchRemoteModule":
        i = slot(ev.get("StorageSlot"))
        if i is not None:
            wait = ev.get("TransferTime") if isinstance(ev.get("TransferTime"), (int, float)) else 0
            m = {k: v for k, v in items[i].items() if k not in ("TransferCost", "TransferTime")}
            # on its way here: shown in transit until it arrives, then here
            m.update(StarSystem=here.get("system"), MarketID=market, InTransit=wait > 0, _arrive=iso_ts(ts_seconds(ts) + wait))
            items[i], changed = m, True
    elif name == "ModuleSellRemote":
        i = slot(ev.get("StorageSlot"))
        if i is not None:
            items.pop(i)
            changed = True
    if not changed:
        return state
    return dict(st, Items=items, changed=ts)


def stored_modules(snap, now=None):
    """Your stored modules (snap: modules_apply's): name (class, rating, mount), where, the engineering, what moving it
    here costs. {ts (the last list), changed (a line folded since), modules: [...]}, the engineered first, then by
    name. One sent for since the list is in transit until it arrives (`_arrive`), then where it was sent."""
    now = time.time() if now is None else now
    at = iso_ts(now)
    rows = []
    for m in (snap or {}).get("Items") or []:
        if not isinstance(m, dict):
            continue
        name, size, rating, mount = module_label(m.get("Name"), m.get("Name_Localised"))
        # "FSD_LongRange" -> "Long range": the blueprint's own words, without the module it is for
        blueprint = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", re.sub(r"^[A-Za-z]+_", "", str(m.get("EngineerModifications") or ""))).capitalize() or None
        moving = not _arrived(m, at)
        rows.append({"name": name, "size": size, "rating": rating, "mount": mount,
                     "system": None if moving else m.get("StarSystem"), "in_transit": moving, "hot": bool(m.get("Hot")),
                     "market": None if moving else m.get("MarketID"),   # its station: State.with_stations
                     "value": m.get("BuyPrice"), "transfer_cost": m.get("TransferCost"), "transfer_s": m.get("TransferTime"),
                     "blueprint": blueprint,
                     "level": m.get("Level"), "quality": m.get("Quality")})
    rows.sort(key=lambda r: (r["blueprint"] is None, r["name"], -(r["size"] or 0)))
    return {"ts": (snap or {}).get("ts"), "changed": (snap or {}).get("changed"), "modules": rows}


def locker(snap):
    """The ship locker (Odyssey) as last written whole (snap: locker_apply's): each kind's items with their counts, a
    mission's own kept apart. {ts, kinds: [{name, items: [{name, count, mission}]}]}."""
    kinds = []
    for key, title in LOCKER_KINDS:
        tally = {}
        for it in (snap or {}).get(key) or []:
            if isinstance(it, dict) and isinstance(it.get("Count"), int):
                k = (_text(it, "Name") or "?", it.get("MissionID") is not None)
                tally[k] = tally.get(k, 0) + it["Count"]
        kinds.append({"name": title, "items": [{"name": n, "count": c, "mission": ms} for (n, ms), c in sorted(tally.items())]})
    return {"ts": (snap or {}).get("ts"), "kinds": kinds}


def _weapon(m):
    return {"id": m.get("SuitModuleID"), "slot": m.get("SlotName"), "name": m.get("ModuleName"),
            "name_l": m.get("ModuleName_Localised"), "class": m.get("Class"), "mods": list(m.get("WeaponMods") or [])}


def suit_apply(state, ev):
    """Odyssey suit loadouts, as inara._suits reads the same events: one created or worn (SuitLoadout comes at every
    disembark) is kept whole; a module equipped or removed, a rename, an upgraded suit or weapon (UpgradeSuit,
    UpgradeWeapon: its new class) change it; a deleted one goes. {loadout id: {id, loadout, suit_id, suit, suit_l,
    class, mods, weapons: [_weapon], ts}}."""
    st, name, ts = dict(state or {}), ev["event"], ev["timestamp"]
    if name == "UpgradeSuit" and ev.get("SuitID") is not None and isinstance(ev.get("Class"), int):
        for row in st.values():
            if row.get("suit_id") == ev["SuitID"]:
                row["class"] = ev["Class"]
        return st
    if name == "UpgradeWeapon" and ev.get("SuitModuleID") is not None and isinstance(ev.get("Class"), int):
        for row in st.values():
            for w in row["weapons"]:
                if w.get("id") == ev["SuitModuleID"]:
                    w["class"] = ev["Class"]
        return st
    lid = ev.get("LoadoutID")
    if lid is None:
        return st
    key = str(lid)
    if name in ("SuitLoadout", "CreateSuitLoadout"):
        cls = re.search(r"_class(\d)", str(ev.get("SuitName") or ""))
        st[key] = {"id": lid, "loadout": ev.get("LoadoutName"), "suit_id": ev.get("SuitID"), "suit": ev.get("SuitName"),
                   "suit_l": ev.get("SuitName_Localised"), "class": int(cls.group(1)) if cls else None,
                   "mods": list(ev.get("SuitMods") or []),
                   "weapons": [_weapon(m) for m in ev.get("Modules") or [] if isinstance(m, dict)], "ts": ts}
    elif name == "DeleteSuitLoadout":
        st.pop(key, None)
    elif key not in st:
        pass   # a loadout the journals never showed whole: nothing to change
    elif name == "RenameSuitLoadout":
        st[key].update(loadout=ev.get("LoadoutName") or st[key]["loadout"], ts=ts)
    elif name in ("LoadoutEquipModule", "LoadoutRemoveModule") and ev.get("SlotName"):
        ws = [w for w in st[key]["weapons"] if w.get("slot") != ev["SlotName"]]
        if name == "LoadoutEquipModule":
            ws.append(_weapon(ev))
        st[key].update(weapons=ws, ts=ts)
    return st


def suits(state):
    """The suit loadouts (suit_apply's): suit, its class and mods, the weapons with theirs. The latest changed first."""
    rows = []
    for e in sorted((state or {}).values(), key=lambda e: e.get("ts") or "", reverse=True):
        suit = _text({"S": e.get("suit"), "S_Localised": e.get("suit_l")}, "S") or "?"
        rows.append({"loadout": e.get("loadout"), "suit": suit, "class": e.get("class"),
                     "mods": [_mod(m) for m in e.get("mods") or []], "ts": e.get("ts"),
                     "weapons": [{"name": _text({"N": w.get("name"), "N_Localised": w.get("name_l")}, "N") or "?",
                                  "class": w.get("class"), "slot": w.get("slot"), "mods": [_mod(m) for m in w.get("mods") or []]}
                                 for w in e.get("weapons") or []]})
    return rows


def _mod(symbol):
    """A suit or weapon mod's symbol in words: "suit_increasedsprintduration" -> "Increased sprint duration"."""
    s = re.sub(r"^(suit|weapon)_", "", str(symbol or ""), flags=re.I)
    s = re.sub(r"(increased|improved|reduced|added|extra|night|quieter|faster|greater|higher|stowed|combat|damage|"
               r"backpack|ammo|magazine|scope|range|stability|handling|reload|battery|shield|sprint|jump|melee|tool|"
               r"duration|capacity|assist|vision|size|rate|accuracy|speed|headshot)", r" \1", s)
    return " ".join(s.split()).capitalize() or "?"


# ---- engineering: the blueprints against your materials, and where the engineers stand ----

_BLUEPRINTS = {}


def load_blueprints(path=BLUEPRINTS_FILE):
    """resources/blueprints.json's list (read once per file time), None when it cannot be read."""
    try:
        stamp = os.path.getmtime(path)
        if _BLUEPRINTS.get("key") != (path, stamp):
            with open(path, encoding="utf-8") as f:
                rows = json.load(f)["blueprints"]
            _BLUEPRINTS.update(key=(path, stamp), rows=rows)
        return _BLUEPRINTS["rows"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _plain(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def engineer_apply(state, ev):
    """EngineerProgress: the login's list, then each change since. {name: {progress ("Known", "Invited",
    "Unlocked"...), rank (the highest grade they craft for you, 1 to 5; None until unlocked)}}."""
    out = dict(state or {})
    for row in (ev["Engineers"] if isinstance(ev.get("Engineers"), list) else [ev]):
        if isinstance(row, dict) and row.get("Engineer"):
            had = out.get(row["Engineer"]) or {}
            out[row["Engineer"]] = {"progress": row.get("Progress") or had.get("progress"),
                                    "rank": row.get("Rank") if row.get("Rank") is not None else had.get("rank")}
    return out


def blueprints(counts, known=None, name=None, rows=None):
    """Every blueprint with what each grade takes against the materials you hold: [{id, module, name, grades:
    [{grade, materials: [{id, name, need, have, category (Raw, Manufactured, Encoded: its trader's kind)}], rolls (how many times you could craft it now), engineers:
    [{name, progress, rank, ready (unlocked far enough for this grade)}]}]}]. counts: {material id: held};
    known: engineer_apply's; name: fn(material id) -> its name."""
    known = {_plain(k): v for k, v in (known or {}).items()}
    name = name or (lambda mid: materials.MATERIALS.get(mid, (mid,))[0])
    out = []
    for b in (load_blueprints() or []) if rows is None else rows:
        grades = []
        for g, v in sorted(b["grades"].items()):
            need = [{"id": mid, "name": name(mid), "need": n, "have": int(counts.get(mid, 0)),
                 "category": materials.MATERIALS.get(mid, (None, None))[1]} for mid, n in v["materials"].items()]
            who = []
            for e in v.get("engineers") or []:
                st = known.get(_plain(e)) or {}
                rank = st.get("rank")
                # EngineerProgress' Rank is the highest grade the engineer crafts for you (checked on real journals,
                # 2026-10-14: every EngineerCraft's Level was at most the Rank then, and a rank-up follows the roll
                # that earned it: G4 at rank 4, then Rank 5)
                who.append({"name": e, "progress": st.get("progress"), "rank": rank,
                            "ready": st.get("progress") == "Unlocked" and isinstance(rank, int) and rank >= int(g)})
            grades.append({"grade": int(g), "materials": need, "engineers": who,
                           "rolls": min((m["have"] // m["need"] for m in need if m["need"]), default=0)})
        out.append({"id": b["id"], "module": b["module"], "name": b["name"], "grades": grades})
    return out


def engineering(material_state, known):
    """The Engineering tab: the blueprints against the materials held (Journals.materials) and the engineers;
    `unreadable` when resources/blueprints.json could not be read (the page says so rather than "nothing matches")."""
    counts = (material_state or {}).get("counts") or {}
    rows = load_blueprints()
    return {"blueprints": blueprints(counts, known, lambda mid: materials.display_name(material_state, mid), rows=rows or []),
            "engineers": [dict(v, name=k) for k, v in sorted((known or {}).items())], "unreadable": rows is None}


# ---- missions ----

MISSION_SOON_S = 1800   # an expiry within this is marked
EXPIRES_IS_TIME = 10 ** 9   # a Missions list's Expires this large is a Unix time, not seconds left (2001 on)


def mission_apply(state, ev, here=None):
    """The missions you hold, as cargo.ship_apply folds the hold: {mission id: row}. The login's Missions line says
    which are still active and which are done, waiting to be handed in (`Complete`: still held; one the journals never
    saw accepted is kept by its name alone); accept, redirect, a cargo depot and the endings follow in order, and a
    Bounty counts for the massacre missions (mission_kill; here: where you are, its `system`)."""
    held, name, mid = dict(state or {}), ev["event"], ev.get("MissionID")
    if name in KILL_LINES:
        return mission_kill(held, ev, (here or {}).get("system"))
    if name == "Missions":
        listed = {which: {str(m.get("MissionID")): m for m in ev.get(which) or [] if isinstance(m, dict) and m.get("MissionID") is not None}
                  for which in ("Active", "Complete")}
        at = ts_seconds(ev["timestamp"])
        held = {k: v for k, v in held.items() if k in listed["Active"] or k in listed["Complete"]}
        for k, m in {**listed["Complete"], **listed["Active"]}.items():
            row = held.setdefault(k, _mission({"MissionID": m["MissionID"], "Name": m.get("Name"), "LocalisedName": m.get("Name_Localised")}))
            if k in listed["Complete"] and k not in listed["Active"]:   # done: the panel's "redirected" / "✓ done", no more kills counted
                row["redirected"] = True
            exp = m.get("Expires")
            if not row["expiry"] and isinstance(exp, (int, float)) and exp > 0:
                # the seconds left; a colonisation mission's is the time itself (real journals, 2026-10-14:
                # "Expires":1745159181 on its login lists, where every other mission's counts down from ~86400)
                row["expiry"] = iso_ts(exp if exp >= EXPIRES_IS_TIME else at + exp)
            row["passengers"] = row["passengers"] or bool(m.get("PassengerMission"))
            # round 10's S4: whether it is an on-foot one, from the list's own Name (the symbol: a row accepted before
            # rows kept it is set at the next login, with no re-read)
            row["on_foot"] = _on_foot(m.get("Name")) or bool(row.get("on_foot"))
        return held
    if mid is None:
        return held
    key = str(mid)
    if name == "MissionAccepted":
        held[key] = _mission(ev)
    elif name in ("MissionCompleted", "MissionFailed", "MissionAbandoned"):
        held.pop(key, None)
    elif key in held and name == "MissionRedirected":
        held[key] = dict(held[key], system=ev.get("NewDestinationSystem") or held[key]["system"],
                         station=ev.get("NewDestinationStation") or held[key]["station"], redirected=True)
    elif key in held and name == "CargoDepot" and isinstance(ev.get("TotalItemsToDeliver"), int):
        held[key] = dict(held[key], count=ev["TotalItemsToDeliver"], delivered=ev.get("ItemsDelivered") or 0)
    return held


# the kill lines a massacre mission counts: a Bounty, or a combat bond (a conflict zone's kill and a Thargoid's write a
# FactionKillBond and no Bounty: review round 11 I)
KILL_LINES = ("Bounty", "FactionKillBond")


def counts_kills(state):
    """Whether a kill line (KILL_LINES) has a mission to count for: a massacre mission held and not yet redirected.
    Without one the missions fold leaves the line alone (Journals.handle_commander), so a kill does not move its fresh()
    mark."""
    return any(r.get("massacre") and not r.get("redirected") for r in (state or {}).values())


def mission_kill(held, ev, system):
    """Round 10's S8: a kill line (a Bounty or a FactionKillBond) counted for the massacre missions you hold (held
    changed in place, and returned). It counts for one mission per giving faction: of those whose target faction is the
    victim's (VictimFaction as TargetFaction, compared by faction_key: a Thargoid mission's may be a symbol) and whose
    target system is where you are (when both are known), the oldest accepted that is not yet done; a mission the game
    has redirected is done whatever the count. Only your own kills are in your journal: a wing mission's count leaves
    out the wing's (the page says so). A combat bond counts as a Bounty does (review round 11 I: a conflict zone's
    massacre, "Mission_Massacre_Conflict_War", and a Thargoid one, get bonds only, and showed "0/30 counted"); a kill
    writes one or the other, and should the game ever write both for one kill (a wanted ship in a conflict zone), the
    second line at the same second, of the other kind, is not counted again (`kill_line`). The rule is the community's;
    the author's journals hold three massacre missions, none with a kill of its target nor a redirect, so it is
    unconfirmed: the figure is worded "counted"."""
    victim = faction_key(ev.get("VictimFaction"))
    if not victim:
        return held
    here = (system or "").lower()
    done = set()
    ts, kind = ev.get("timestamp"), ev.get("event")
    for key, row in sorted(held.items(), key=lambda kv: (kv[1].get("accepted") or "", kv[0])):
        if not row.get("massacre") or row.get("redirected") or row.get("faction") in done or faction_key(row.get("target_faction")) != victim:
            continue
        if here and row.get("target_system") and row["target_system"].lower() != here:
            continue
        last = row.get("kill_line") or {}
        if last.get("ts") == ts and last.get("event") != kind:
            done.add(row.get("faction"))
            continue   # the same kill's other line: counted already
        if (row.get("kills") or 0) >= (row.get("count") or 0):
            continue   # counted out: the faction's next one takes the kill
        held[key] = dict(row, kills=(row.get("kills") or 0) + 1, kill_line={"ts": ts, "event": kind})
        done.add(row.get("faction"))
    return held


def missions(state, now=None):
    """The missions you hold (mission_apply's), the soonest to expire first: [{id, name, faction, system, station,
    target, commodity, count, delivered, reward, expiry (ISO or None), expires_in (s; None without one), soon, expired,
    wing, passengers, redirected, influence, reputation, mining, commodity_id, collect, massacre, kills (a massacre
    mission's counted, else None), on_foot}]."""
    now = time.time() if now is None else now
    out = []
    for row in (state or {}).values():
        left = ts_seconds(row["expiry"]) - now if row["expiry"] else None
        out.append(dict({"collect": False, "massacre": False, "kills": None, "on_foot": False}, **row,   # a row from before PARSER 73
                        expires_in=None if left is None else int(left), soon=left is not None and 0 <= left <= MISSION_SOON_S,
                        expired=left is not None and left < 0))
    out.sort(key=lambda r: (r["expires_in"] is None, r["expires_in"] or 0, r["name"] or ""))
    return out


def _mission(e):
    # the game's own words, else its symbol tidied: "Mission_Courier_War_name" and "$Mission_Colonisation_Initial_Name;"
    name = e.get("LocalisedName") or re.sub(r"_name;?$", "", re.sub(r"^\$?Mission_", "", str(e.get("Name") or "?")), flags=re.I).replace("_", " ")
    return {"id": e.get("MissionID"), "name": name, "faction": e.get("Faction"), "system": e.get("DestinationSystem"),
            "station": e.get("DestinationStation") or e.get("DestinationSettlement"),
            "target": _text(e, "Target") or e.get("TargetFaction"), "commodity": _text(e, "Commodity"),
            "count": e.get("Count") if e.get("Count") is not None else e.get("KillCount") or e.get("PassengerCount"),
            "delivered": None, "reward": e.get("Reward"), "expiry": e.get("Expiry"), "wing": bool(e.get("Wing")),
            "passengers": e.get("PassengerCount") is not None, "redirected": False,
            "influence": e.get("Influence"), "reputation": e.get("Reputation"), "accepted": e.get("timestamp"),
            # a mining mission (Mission_Mining..., wing ones too) and its commodity's journal id ("$Bertrandite_Name;" ->
            # "bertrandite"): CMDR -> Missions' search for where to mine it, by the id so a translated game works too
            # (ideas from EliteMining's feature list, 2026-10-24). A mission whose MissionAccepted is in no journal read
            # has neither: no search
            "mining": bool(re.match(r"\$?Mission_Mining", str(e.get("Name") or ""), re.I)), "commodity_id": _symbol(e.get("Commodity")),
            # round 10's S15: a Collect mission ("Mission_Collect_RankEmp": source goods and hand them in; not an on-foot
            # one, Mission_OnFoot_Collect..., nor a Delivery): CMDR -> Missions' 🔍 opens Materials -> Cargo's Buy
            "collect": bool(re.match(r"\$?Mission_Collect", str(e.get("Name") or ""), re.I)),
            # round 10's S4: an on-foot mission (Mission_OnFoot_...): the wrong-suit warning keeps quiet while one is held
            "on_foot": _on_foot(e.get("Name")),
            # round 10's S8: a massacre mission's target (TargetFaction, in the system it was given for) and the kills
            # counted for it (mission_kill)
            **_massacre(e)}


def _on_foot(name):
    """Whether a mission's Name symbol is an on-foot (Odyssey) one: "Mission_OnFoot_Collect_name"."""
    return bool(re.match(r"\$?Mission_OnFoot", str(name or ""), re.I))


def _massacre(e):
    """A massacre mission's fields (Mission_Massacre..., with a KillCount): its target faction and system, and the kills
    counted so far (0); none for any other mission (kills None)."""
    if not (re.match(r"\$?Mission_Massacre", str(e.get("Name") or ""), re.I) and isinstance(e.get("KillCount"), int)
            and e.get("TargetFaction")):
        return {"massacre": False, "target_faction": None, "target_system": None, "kills": None}
    return {"massacre": True, "target_faction": e["TargetFaction"], "target_system": e.get("DestinationSystem"), "kills": 0}


def _symbol(v):
    """A journal symbol's id: "$Bertrandite_Name;" -> "bertrandite" (None for none)."""
    if not isinstance(v, str) or not v.strip():
        return None
    return re.sub(r"_name;?$", "", re.sub(r"^\$", "", v.strip()), flags=re.I).rstrip(";").lower() or None


# ---- Community Goals (round 10's S19) ----

def cg_apply(state, ev):
    """The Community Goals you have joined: {goals: {CGID: row}, ts}. Each CommunityGoal line lists every one you are
    signed up to (CurrentGoals: one or two at a time in the author's 1,593 lines; a goal joined is listed seconds after
    its CommunityGoalJoin), so it replaces the list; CommunityGoalReward and CommunityGoalDiscard drop one. A finished
    goal stays listed, IsComplete true, for days after its Expiry (until its reward is collected): community_goals
    shows the current ones only. None when there are none."""
    name = ev["event"]
    if name == "CommunityGoal":
        goals = {str(g["CGID"]): _goal(g) for g in ev.get("CurrentGoals") or [] if isinstance(g, dict) and g.get("CGID") is not None}
    else:
        goals = dict((state or {}).get("goals") or {})
        goals.pop(str(ev.get("CGID")), None)
    return {"goals": goals, "ts": ev["timestamp"]} if goals else None


def _goal(g):
    top = g.get("TopTier") if isinstance(g.get("TopTier"), dict) else {}
    tier = lambda v: int(m.group(1)) if isinstance(v, str) and (m := re.search(r"(\d+)\s*$", v)) else None
    return {"id": g["CGID"], "title": str(g.get("Title") or "").strip() or None, "system": g.get("SystemName"),
            "station": g.get("MarketName"), "expiry": g.get("Expiry"), "complete": bool(g.get("IsComplete")),
            "contribution": g.get("PlayerContribution"), "contributors": g.get("NumContributors"),
            # "Tier 2" of "Tier 5" (TierReached is missing before the first tier); the band is the top N % of
            # contributors you are in (100: not placed yet)
            "tier": tier(g.get("TierReached")), "top_tier": tier(top.get("Name")), "band": g.get("PlayerPercentileBand"),
            "top_rank": bool(g.get("PlayerInTopRank"))}


def community_goals(state, now=None):
    """The Community Goals you are signed up to that are still running (their Expiry ahead; one with none counts), the
    soonest to end first: [{id, title, system, station, expiry, expires_in, complete, contribution, contributors, tier,
    top_tier, band, top_rank}]."""
    now = time.time() if now is None else now
    out = []
    for g in ((state or {}).get("goals") or {}).values():
        left = ts_seconds(g["expiry"]) - now if g.get("expiry") else None
        if left is None or left > 0:
            out.append(dict(g, expires_in=None if left is None else int(left)))
    out.sort(key=lambda g: (g["expires_in"] is None, g["expires_in"] or 0, g["title"] or ""))
    return out


# ---- bounty vouchers and combat bonds (round 10's S9) ----

def vouchers_apply(state, ev):
    """The vouchers you hold, per faction: {bounties: {faction: cr}, bonds: {faction: cr}, ts}; None when none. Checked
    against the author's journals (2024-10 to 2026-03: 52 Bounty, 139 FactionKillBond, 20 RedeemVoucher lines):
    - a Bounty's Rewards[] pays each faction its Reward (one kill can pay two);
    - a FactionKillBond (and a CapShipBond) pays its AwardingFaction a bond;
    - Died loses them all: the next redemption paid only what was earned after the death, every time;
    - RedeemVoucher Type "bounty" lists Factions[] {Faction, Amount}: each named faction is paid. A blank Faction ("")
      stands for the factions it does not name: in every case it matched one held faction's amount (or that x1.2: a
      bonus can be added, as on named ones), and each of the six bounty redemptions paid everything held, so a blank
      clears the rest. Type "CombatBond" names one Faction per line (a second line with Amount 0 follows; in a
      Powerplay zone a "PilotsFederation" one pays a bonus nothing earned): that faction's bonds are paid. Other Types
      (codex, trade...) are not vouchers held here. No real redemption had a BrokerPercentage (Interstellar Factors').
    A faction is held by its bare name (faction_name): a Thargoid kill's bond names the Pilots' Federation by its
    symbol, "$faction_PilotsFederation;", its redemption "PilotsFederation" (review round 11 E: the bonds were never
    paid off), so a redemption pays the held faction whose faction_key is its own; `names` keeps the game's words for
    one held by a symbol ({bare name: "Pilots' Federation"}, else the name spaced out), for the tile."""
    name = ev["event"]
    if name == "Died":
        return None
    st = {k: dict((state or {}).get(k) or {}) for k in ("bounties", "bonds", "names")}

    def add(kind, faction, cr, shown=None):
        if isinstance(cr, (int, float)) and not isinstance(cr, bool) and cr > 0 and isinstance(faction, str):
            bare = faction_name(faction)
            st[kind][bare] = st[kind].get(bare, 0) + cr
            if bare != faction.strip():   # a symbol: the game's words (kept from an earlier line), else its name spaced out
                st["names"][bare] = shown.strip() if isinstance(shown, str) and shown.strip() else st["names"].get(bare) or _spaced(bare)

    if name == "Bounty":
        if isinstance(ev.get("Rewards"), list):
            for r in ev["Rewards"]:
                if isinstance(r, dict):
                    add("bounties", r.get("Faction"), r.get("Reward"), r.get("Faction_Localised"))
        else:   # a skimmer's (Frontier's manual): one Faction and Reward
            add("bounties", ev.get("Faction"), ev.get("Reward"), ev.get("Faction_Localised"))
    elif name in ("FactionKillBond", "CapShipBond"):
        add("bonds", ev.get("AwardingFaction"), ev.get("Reward"), ev.get("AwardingFaction_Localised"))
    elif name == "RedeemVoucher":
        kind = {"bounty": "bounties", "CombatBond": "bonds"}.get(ev.get("Type"))
        if not kind:
            return state
        paid = [f.get("Faction") for f in ev.get("Factions") or [] if isinstance(f, dict)] if isinstance(ev.get("Factions"), list) \
            else [ev.get("Faction")] if isinstance(ev.get("Faction"), str) else []
        if not paid or "" in paid:
            st[kind] = {}   # a blank: the factions it does not name were paid too
        keys = {faction_key(f) for f in paid if isinstance(f, str)}
        st[kind] = {f: cr for f, cr in st[kind].items() if faction_key(f) not in keys}
    held = set(st["bounties"]) | set(st["bonds"])
    st["names"] = {f: n for f, n in st["names"].items() if f in held}
    if not st["bounties"] and not st["bonds"]:
        return None
    return dict(st, ts=ev["timestamp"])


def faction_name(v):
    """A faction as the journal names it, bare: a symbol's name ("$faction_PilotsFederation;" -> "PilotsFederation"),
    any other name as it is."""
    v = str(v or "").strip()
    m = re.match(r"^\$faction_(.*?);?$", v, re.I)
    return m.group(1) if m else v


def _spaced(name):
    """A symbol's name in words: "PilotsFederation" -> "Pilots Federation"."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def faction_key(v):
    """What tells two spellings of a faction apart, or not: the bare name lower-cased with only its letters and digits
    ("$faction_PilotsFederation;", "PilotsFederation" and "Pilots' Federation" are one)."""
    return re.sub(r"[^0-9a-z]", "", faction_name(v).lower())


def vouchers(state):
    """The vouchers held (vouchers_apply's), for the Unsold tile: {total, bounties, bonds, factions: [{name, bounties,
    bonds, total}] the most first}; None when there are none. A faction held by its symbol is named in the game's
    words (`names`), never as the raw symbol."""
    b, k = (state or {}).get("bounties") or {}, (state or {}).get("bonds") or {}
    names = (state or {}).get("names") or {}
    total_b, total_k = round(sum(b.values())), round(sum(k.values()))
    if total_b + total_k <= 0:
        return None
    shown = lambda f: names.get(f) or (_spaced(faction_name(f)) if f.startswith("$") else f)   # "$...;": a fold before round 11
    factions = [{"name": shown(f), "bounties": round(b.get(f, 0)), "bonds": round(k.get(f, 0)), "total": round(b.get(f, 0) + k.get(f, 0))}
                for f in sorted(set(b) | set(k))]
    factions.sort(key=lambda x: (-x["total"], x["name"]))
    return {"total": total_b + total_k, "bounties": total_b, "bonds": total_k, "factions": factions}


# ---- sessions: combat and mining, per login ----

_KILLS = ("Bounty", "FactionKillBond", "PVPKill", "CapShipBond")
_MINING = ("MiningRefined", "ProspectedAsteroid", "AsteroidCracked")


def _span(first, last):
    """Seconds between two ISO stamps, a minute at least (a rate over one event means nothing)."""
    return max(60, ts_seconds(last) - ts_seconds(first)) if first and last else None


def _seen(acc, ts, first="first", last="last"):
    acc[first] = min(acc[first] or ts, ts)
    acc[last] = max(acc[last] or ts, ts)


def _mining_counts():
    """A login's mining counts before its first mining line (play_activity's mining)."""
    return {"n": 0, "refined": {}, "srv": {}, "prospected": 0, "content": {}, "motherlodes": 0, "cracked": 0,
            "prospectors": 0, "collectors": 0, "sold": 0, "first": None, "last": None,
            "srv_first": None, "srv_last": None, "seen": None, "places": {}}


def _ship_line(acc, ship, ts):
    """One counted line's ship into a login's counts (`ships`: {name: {n, first, last}}, its lines and the earliest and
    latest of them, so a line read out of order still counts at its place; an older row has none yet)."""
    if ship:
        x = acc.setdefault("ships", {}).setdefault(ship, {"n": 0, "first": None, "last": None})
        x["n"] += 1
        _seen(x, ts)


def _ships(acc):
    """The ships a login's fighting or mining was done in, in the order first flown, and the one it ended in (its
    latest line's): ([names], last), ([], None) when none was known."""
    ships = acc.get("ships") or {}
    order = sorted(ships, key=lambda k: (ships[k]["first"], k))
    return order, max(order, key=lambda k: (ships[k]["last"], k)) if order else None


def activity_apply(acts, ev, srv=False, mined=None, place=None, ship=None):
    """One fighting or mining line into a login's counts (play_activity's combat and mining, created when first
    needed): acts {combat, mining}, changed in place; True if it counted. srv: you are in an SRV (Journals.vehicle),
    whose refinery is kept apart from the ship's (`srv`; the Rhino's surface mining). first / last (and srv_first /
    srv_last) are the earliest and latest such line, so a line read out of order still counts once at its place.
    mined: a MarketSell's mining income, as the reader's mined stock worked it out (Journals.note_mined, the rule
    mining_sales follows: the tons you mined still aboard, whenever you mined them; nothing at your own carrier): it is
    the sale's "sold", in the login the sale was made in, which may have no mining line of its own. place: where a
    mining line happened ({id64, system, body}: the ring, the SRV's body; Journals.mining_place), its tons and lines
    kept per place (the Sessions table's Where, the author 2026-10-20). ship: the ship you were in (the reader's
    latest Loadout), kept per kill, death or mining line with when it was first and last flown (`ships`): a swap after the
    login moves the Sessions' Ship (#23)."""
    name, ts = ev["event"], ev["timestamp"]
    if name in _KILLS + ("Died", "Interdicted", "RedeemVoucher"):
        if name == "RedeemVoucher" and ev.get("Type") not in ("bounty", "CombatBond"):
            return False
        c = acts["combat"] = acts.get("combat") or {"n": 0, "kills": 0, "bounties": 0, "bonds": 0, "by_ship": {}, "deaths": 0,
                                                    "interdicted": 0, "redeemed": 0, "first": None, "last": None, "seen": None}
        c["seen"] = max(c["seen"] or ts, ts)
        if name in _KILLS:
            c["n"] += 1
            c["kills"] += 1
            _seen(c, ts)
            _ship_line(c, ship, ts)
            if name == "Bounty":
                c["bounties"] += ev.get("TotalReward") or sum((r.get("Reward") or 0) for r in ev.get("Rewards") or [] if isinstance(r, dict)) \
                    or ev.get("Reward") or 0
                ship = _text(ev, "Target") or "?"
                c["by_ship"][ship] = c["by_ship"].get(ship, 0) + 1
            elif name in ("FactionKillBond", "CapShipBond"):
                c["bonds"] += ev.get("Reward") or 0
        elif name == "Died":
            c["n"] += 1
            c["deaths"] += 1
            _ship_line(c, ship, ts)   # the ship you died in: a session with a death alone names it too
        elif name == "Interdicted":
            c["interdicted"] += 1
        else:
            c["redeemed"] += ev.get("Amount") or 0
        return True
    m = acts.get("mining")
    if name == "MarketSell":
        if not mined:
            return False
        m = acts["mining"] = m or _mining_counts()
        m["sold"] += mined
        m["seen"] = max(m["seen"] or ts, ts)
        return True
    if name == "LaunchDrone" and ev.get("Type") not in ("Prospector", "Collection"):
        return False
    if name not in _MINING + ("LaunchDrone",):
        return False
    m = acts["mining"] = m or _mining_counts()
    m["seen"] = max(m["seen"] or ts, ts)
    if name == "LaunchDrone":
        m["prospectors" if ev["Type"] == "Prospector" else "collectors"] += 1
        return True
    m["n"] += 1
    _ship_line(m, ship, ts)
    if place and place.get("id64"):
        key = f"{place['id64']}|{place.get('body') or ''}"
        p = m.setdefault("places", {}).setdefault(key, {"id64": place["id64"], "system": place.get("system"),
                                                        "body": place.get("body"), "tons": 0, "n": 0})
        p["n"] += 1
        p["tons"] += name == "MiningRefined"
        p["system"] = p["system"] or place.get("system")
    if name == "MiningRefined":
        what = _text(ev, "Type") or "?"
        into = m["srv"] if srv else m["refined"]
        into[what] = into.get(what, 0) + 1
        _seen(m, ts, *(("srv_first", "srv_last") if srv else ("first", "last")))
        return True
    _seen(m, ts)
    if name == "AsteroidCracked":
        m["cracked"] += 1
    else:
        m["prospected"] += 1
        level = re.sub(r"^\$AsteroidMaterialContent_|;$", "", str(ev.get("Content") or "?"))
        m["content"][level] = m["content"].get(level, 0) + 1
        m["motherlodes"] += bool(ev.get("MotherlodeMaterial"))
    return True


def session(row):
    """A play_activity row as the Sessions tab lists it, None without fighting or mining: {start (the login), end (its
    last such line), commander, ship (the login's), combat: {ships (flown in its kills and deaths, in the order first flown; []
    when not known: the login's ship stands in), ship_last (the latest line's), kills, bounties, bonds, by_ship, deaths, interdicted, redeemed, seconds,
    per_hour} or None, mining: {ships, ship_last (as combat's, by mining lines), tons, refined: {name: t} (the ship's), srv_tons, srv_refined (the SRV's
    refinery), prospected, content: {High, Medium, Low}, motherlodes, cracked, prospectors, collectors, sold, seconds,
    per_hour (the ship's), srv_seconds} or None}. A login with nothing mined but ore sold that was mined before (sold
    only) lists its mining too."""
    c = row.get("combat") if (row.get("combat") or {}).get("n") else None
    m = row.get("mining") if (row.get("mining") or {}).get("n") or (row.get("mining") or {}).get("sold") else None
    if not c and not m:
        return None
    combat = mining = None
    if c:
        secs = _span(c["first"], c["last"])
        ships, last = _ships(c)
        combat = {"ships": ships, "ship_last": last, "kills": c["kills"], "bounties": c["bounties"], "bonds": c["bonds"], "deaths": c["deaths"],
                  "interdicted": c["interdicted"], "redeemed": c["redeemed"], "seconds": secs,
                  "by_ship": dict(sorted(c["by_ship"].items(), key=lambda kv: (-kv[1], kv[0]))),
                  "per_hour": round(c["kills"] * 3600 / secs, 1) if secs and c["kills"] > 1 else None}
    if m:
        secs, tons, srv = _span(m["first"], m["last"]), sum(m["refined"].values()), sum(m["srv"].values())
        order = lambda d: dict(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))
        ships, last = _ships(m)
        mining = {"ships": ships, "ship_last": last, "tons": tons, "refined": order(m["refined"]), "srv_tons": srv, "srv_refined": order(m["srv"]),
                  "prospected": m["prospected"], "content": m["content"], "motherlodes": m["motherlodes"],
                  "cracked": m["cracked"], "prospectors": m["prospectors"], "collectors": m["collectors"], "sold": m["sold"],
                  "seconds": secs, "per_hour": round(tons * 3600 / secs, 1) if secs and tons > 1 else None,
                  "srv_seconds": _span(m["srv_first"], m["srv_last"]),
                  # where: the most tons first (then the most lines: prospected only)
                  "places": sorted(({k: p[k] for k in ("id64", "system", "body", "tons")} for p in (m.get("places") or {}).values()),
                                   key=lambda p: -p["tons"])}
    end = max(x["seen"] for x in (row.get("combat"), row.get("mining")) if x and x.get("seen"))
    return {"start": row["login_ts"], "end": end, "commander": row.get("commander"), "ship": row.get("ship"),
            "combat": combat, "mining": mining}


def sessions_since(now=None):
    """The oldest login the Sessions tab lists: SESSIONS_DAYS before now (ISO)."""
    return iso_ts((time.time() if now is None else now) - SESSIONS_DAYS * 86400)


def sessions(rows, limit=SESSIONS_MAX):
    """The logins with fighting or mining (play_activity's rows, the newest first: State reads those of the last
    SESSIONS_DAYS, sessions_since), at most `limit`."""
    out = []
    for r in rows:
        s = session(r)
        if s:
            out.append(s)
            if len(out) >= limit:
                break
    return out


def totals(rows):
    """The listed sessions summed: {combat: {sessions, kills, bounties, bonds, deaths}, mining: {sessions, tons,
    srv_tons, prospected, sold}}."""
    c, m = [r["combat"] for r in rows if r["combat"]], [r["mining"] for r in rows if r["mining"]]
    return {"combat": {"sessions": len(c), **{k: sum(x[k] for x in c) for k in ("kills", "bounties", "bonds", "deaths")}},
            "mining": {"sessions": len(m), **{k: sum(x[k] for x in m) for k in ("tons", "srv_tons", "prospected", "sold")}}}


# ---- the commander: ranks with what the next one takes, assets, the fleet, the career ----

_PILOT = ("Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V")
# the journal's rank keys in the order shown: (title, the ranks' names by number)
RANKS = (
    ("Combat", "Combat", ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly") + _PILOT),
    ("Trade", "Trade", ("Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant", "Broker", "Entrepreneur", "Tycoon") + _PILOT),
    ("Explore", "Exploration", ("Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer") + _PILOT),
    ("Exobiologist", "Exobiology", ("Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist",
                                    "Ecologist", "Geneticist") + _PILOT),
    ("Soldier", "Mercenary", ("Defenceless", "Mostly Defenceless", "Rookie", "Soldier", "Gunslinger", "Warrior", "Gladiator",
                              "Deadeye") + _PILOT),
    ("CQC", "CQC", ("Helpless", "Mostly Helpless", "Amateur", "Semi Professional", "Professional", "Champion", "Hero", "Legend") + _PILOT),
    ("Federation", "Federal Navy", ("None", "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer", "Warrant Officer",
                                    "Ensign", "Lieutenant", "Lieutenant Commander", "Post Commander", "Post Captain", "Rear Admiral",
                                    "Vice Admiral", "Admiral")),
    ("Empire", "Imperial Navy", ("None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord", "Baron", "Viscount", "Count", "Earl",
                                 "Marquis", "Duke", "Prince", "King")),
)
# What a rank's step takes, in credits earned in that career: what is left to the next rank is the step times the share
# of it still to go, by the game's own percentage. Exobiology only: the post-Update-14 thresholds (total Organic Data
# profit; Aunty Sledge's post of 2 Jan 2023 in the Frontier forum's "Exobiology rank threshold rebalance information"
# thread, https://forums.frontier.co.uk/threads/elite-dangerous-exobiology-rank-threshold-rebalance-information.611830/,
# as the wiki copies it, https://elite-dangerous.fandom.com/wiki/Exobiologist, read 2026-10-14: "most confirmed, some
# estimated"; Elite IV and V are estimates, RANK_UNCERTAIN). Checked 2026-10-14 against a player's journals since 2023
# (each login's Progress beside its Statistics): Organic_Data_Profits moves through the Cataloguer, Taxonomist,
# Ecologist and Geneticist bands at these steps within 3 %, but not from these totals (Geneticist 64 % at 7.28B, where
# the totals say 74 %): so the step times the game's percentage, never the counter against the totals. The trade and
# exploration figures once here could not be confirmed the same way (trade progress moved with Market_Profits still;
# exploration has no published steps past Elite): their percentage only, as Combat, Mercenary, CQC and the navies.
RANK_CREDITS = {
    "Exobiologist": (0, 22_500_000, 83_475_000, 210_560_000, 532_800_000, 1_144_000_000, 2_262_600_000, 3_996_000_000,
                     8_425_000_000, 12_969_000_000, 17_425_000_000, 21_925_000_000, 26_320_000_000, 30_917_860_900),
}
RANK_UNCERTAIN = {"Exobiologist": {12, 13}}   # the ranks whose threshold is an estimate (Elite IV, Elite V)
RANK_EARNED_BY = {"Exobiologist": "exobiology data sold"}
# the career figures shown, from the login's Statistics: (section, key, label, kind)
CAREER = (
    ("Exploration", "Time_Played", "Time played", "time"), ("Exploration", "Systems_Visited", "Systems visited", "n"),
    ("Exploration", "Total_Hyperspace_Jumps", "Jumps", "n"), ("Exploration", "Total_Hyperspace_Distance", "Distance jumped", "ly"),
    ("Exploration", "Greatest_Distance_From_Start", "Farthest from the start", "ly"),
    ("Exploration", "Exploration_Profits", "Exploration profits", "cr"), ("Exobiology", "Organic_Data_Profits", "Exobiology profits", "cr"),
    ("Trading", "Market_Profits", "Trade profits", "cr"), ("Mining", "Mining_Profits", "Mining profits", "cr"),
    ("Combat", "Bounty_Hunting_Profit", "Bounty profits", "cr"), ("Combat", "Combat_Bond_Profits", "Combat bond profits", "cr"),
    ("Combat", "Bounties_Claimed", "Bounties claimed", "n"), ("Bank_Account", "Insurance_Claims", "Insurance claims", "n"),
    ("Bank_Account", "Spent_On_Ships", "Spent on ships", "cr"), ("Bank_Account", "Spent_On_Outfitting", "Spent on outfitting", "cr"),
)


def rank_rows(rank, progress):
    """The ranks as rows: {key, title, rank, name, progress (% of the way to the next, None at the top or unknown),
    next (its name, None at the top), to_next (credits still to earn in that career, about; None where no step is
    known), uncertain (the step's figure is itself an estimate), earned_by}."""
    out = []
    for key, title, names in RANKS:
        n = (rank or {}).get(key)
        if not isinstance(n, int):
            continue
        top = n >= len(names) - 1
        pct = (progress or {}).get(key)
        pct = None if top or not isinstance(pct, (int, float)) else max(0, min(100, pct))
        steps = RANK_CREDITS.get(key)
        left = None
        if steps and pct is not None and 0 <= n and n + 1 < len(steps):
            left = int(round((steps[n + 1] - steps[n]) * (100 - pct) / 100))
        out.append({"key": key, "title": title, "rank": n, "name": names[n] if 0 <= n < len(names) else str(n), "progress": pct,
                    "next": None if top or n + 1 >= len(names) else names[n + 1], "to_next": left,
                    "uncertain": left is not None and bool({n, n + 1} & RANK_UNCERTAIN.get(key, set())),
                    "earned_by": RANK_EARNED_BY.get(key) if left is not None else None})
    return out


def profile(commander, stats=None, reputation=None, power=None, squadron=None, fleet=None, modules=None, now=None):
    """The commander as the journals last said: {commander, ts (the login it is from), ranks (rank_rows), reputation
    {Federation, Empire, Alliance, Independent: %}, power {name, rank, merits, cycle, login (power_gains': merits
    gained this cycle and this login, None for none)}, squadron, assets {wealth (the game's
    own total at login), fleet (your ships' value), ships, modules (stored modules' value)}, fleet (ships()'s rows:
    the one you fly first), career [{label, value, kind}]}. None before any login is on record. commander: Journals'
    meta commander (name, login_ts, rank and progress with promotions since); stats: meta statistics; the others the
    folds' states (fleet: ships()'s answer). Credits and the carrier are not here: the page shows the Commander
    tile's credits (State.commander_summary: the login's plus sales since) and the Carrier tile's carrier
    (State.carrier_summary), one owner each."""
    c = commander or {}
    if not c.get("login_ts"):
        return None
    stats, rep, pp = stats or {}, reputation or {}, power or {}
    bank = stats.get("Bank_Account") if isinstance(stats.get("Bank_Account"), dict) else {}
    ships_ = (fleet or {}).get("ships") or []
    stored = stored_modules(modules)["modules"]
    career = []
    for section, key, label, kind in CAREER:
        v = (stats.get(section) or {}).get(key) if isinstance(stats.get(section), dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v:
            career.append({"label": label, "value": v, "kind": kind})
    return {
        "commander": c.get("name"), "ts": c["login_ts"],
        "ranks": rank_rows(c.get("rank"), c.get("progress")),
        "reputation": {k: round(rep[k], 1) for k in ("Federation", "Empire", "Alliance", "Independent") if isinstance(rep.get(k), (int, float))},
        "power": dict({"name": pp.get("power"), "rank": pp.get("rank"), "merits": pp.get("merits")},
                      **power_gains(pp, c.get("login_ts"), now)) if pp.get("power") else None,
        "squadron": (squadron or {}).get("name"),
        "assets": {"wealth": bank.get("Current_Wealth"), "ships": len(ships_), "fleet": sum(s["value"] or 0 for s in ships_) or None,
                   "modules": sum(m["value"] or 0 for m in stored) or None},
        "fleet": sorted(ships_, key=lambda s: (not s["current"], -(s["value"] or 0))),
        "career": career,
    }


_APPLY = {"reputation": reputation_apply, "powerplay": power_apply, "squadron": squadron_apply,
          "ship_locker": locker_apply, "suit_loadouts": suit_apply,
          "engineers": engineer_apply, "missions": mission_apply, "vouchers": vouchers_apply, "community_goals": cg_apply}
