"""The questions Outrider answers for an AI: one registry of read-only tools (tablet plan phase 2, PLAN-mcp).

Each tool has a name, a description and JSON-schema parameters (what the AI sees), and an async handler that builds a
compact answer from Outrider's read-only GET routes through the `get(path, params)` it is given. Two callers share it:
the MCP bridge (outrider/mcp.py: `get` is an HTTP GET to the running server) and, later, the voice's AI layer inside
Outrider (an in-process `get`). Neither copies a tool.

Read-only is a safety rule: a handler can only reach READ_ROUTES (GETs that change no player data; a known system's
lookup may fill Spansh's cache, as the page's own reads do), never a POST route (no rail,
auto honk, auto-target, Highway plot, bookmark or hush): `guarded()` refuses anything else before it is asked.
Answers are trimmed to what answers the question, lists capped at max_rows with how many were left out.
"""
import math
import re
import urllib.parse

import outrider.dock as dock
import outrider.riches as riches

# the GET routes a tool may read (path prefixes); /api/find is left out on purpose: it can store an EDSM hit
READ_ROUTES = ("/api/status", "/api/nearby", "/api/system/", "/api/body", "/api/firsts", "/api/left", "/api/highway",
               "/api/history", "/api/materials", "/api/nearest",   # /api/nearest only ever with cached=1 (no DSSA fetch)
               "/api/ggg")   # S27: Outrider's cache only, never Spansh
DEFAULT_ROWS = 25
NOT_RUNNING = "Outrider isn't running (start it, then ask again)"


class Unavailable(Exception):
    """The running Outrider could not be reached (the tool answers NOT_RUNNING)."""


class Refused(Exception):
    """The running Outrider refused the read (a password it asks for): the tool answers with the reason."""


class NotAllowed(Exception):
    """A tool asked for a route outside READ_ROUTES (a bug: never sent)."""


def allowed(path):
    """Whether `path` is one of the read-only routes (exactly, or under a prefix ending in "/")."""
    return any(path == r or (r.endswith("/") and path.startswith(r) and "/" not in path[len(r):]) for r in READ_ROUTES)


def guarded(get):
    """`get` refusing anything outside READ_ROUTES before it is called."""
    async def g(path, params=None):
        if not allowed(path):
            raise NotAllowed(path)
        return await get(path, params or {})
    return g


TOOLS = {}


def tool(name, description, params=None, required=()):
    """Register `fn(get, args, rows) -> dict` as a tool."""
    def wrap(fn):
        TOOLS[name] = {"name": name, "description": description, "handler": fn,
                       "schema": {"type": "object", "properties": params or {}, "required": list(required),
                                  "additionalProperties": False}}
        return fn
    return wrap


def capped(items, rows, key="items"):
    """{key: the first `rows`, "more": how many were left out} (no "more" when nothing was)."""
    items = list(items)
    out = {key: items[:rows]}
    if len(items) > rows:
        out["more"] = len(items) - rows
    return out


def rnd(x, n=1):
    return None if x is None else round(x, n)


def _int(args, key, default, lo, hi):
    v = args.get(key, default)
    try:
        v = int(v)
    except (TypeError, ValueError, OverflowError):   # OverflowError: 1e999 parses as inf
        v = default
    return max(lo, min(hi, v))


# ---- the tools ----

@tool("current_status", "Where the commander is now: system, region, fuel and jumps left, jump range, the target, "
      "unsold data value, the body they are on (or flying near, or have targeted in this system) and any exobiology "
      "sample under way, their carrier and their squadron's.")
async def current_status(get, args, rows):
    s = await get("/api/status")
    return {k: s.get(k) for k in ("system", "region", "fuel_pct", "fuel_jumps", "jump_range", "boost", "target", "unsold",
                                  "on_body", "near_body", "target_body", "sampling", "carrier", "squadron_carrier")}


def _body_brief(b):
    bio = [{"species": o.get("species") or o.get("genus"), "samples": o.get("samples"), "done": o.get("done"), "state": o.get("state")}
           for o in b.get("organics") or [] if isinstance(o, dict)]
    out = {"name": b.get("name"), "type": b.get("subtype") or b.get("type"), "distance_ls": rnd(b.get("dist_ls"), 0),
           "gravity_g": rnd(b.get("gravity"), 2), "landable": b.get("landable"), "terraformable": b.get("terraformable") or None,
           "atmosphere": b.get("atmosphere") or None, "value_now": b.get("value_now"), "value_max": b.get("value_max"),
           "scanned": b.get("scanned"), "mapped": b.get("mapped"), "first_discovered": b.get("first_discovered") or None,
           "bio_signals": b.get("bio") or None, "geo_signals": b.get("geo") or None, "mining_locations": b.get("mining") or None,
           "bio_genera": b.get("genera") or None, "bio_sampled": bio or None, "rings": b.get("rings") or None}
    return {k: v for k, v in out.items() if v is not None}


@tool("this_system", "The system the commander is in: what is left to do (honk, bodies to find, biology to sample, "
      "planets worth mapping) and its bodies, most valuable first, with value, gravity, landability, signals and status.")
async def this_system(get, args, rows):
    s = await get("/api/status")
    if not s.get("id64"):
        return {"error": "no position yet (no jump in the journals)"}
    d = await get(f"/api/system/{s['id64']}")
    l = d.get("leaving") or {}
    bodies = sorted((b for b in d.get("bodies") or [] if b.get("type") != "Barycentre"),
                    key=lambda b: -(b.get("value_max") or 0))
    todo = {"honked": l.get("honked"), "bodies_known": l.get("scanned"), "body_count": l.get("body_count"),
            "bodies_to_find": l.get("unscanned"),
            "bio_to_sample": [x.get("body") for x in l.get("bio_pending") or []],
            # the detailed list (unmapped_valuable is short labels like "A 2 (ELW T)": .get on them crashed the tool)
            "worth_mapping": [{"body": x.get("body"), "type": x.get("subtype"), "adds": x.get("increment")}
                              for x in l.get("unmapped") or [] if isinstance(x, dict) and x.get("special")]}
    return {"system": d.get("name"), "region": (d.get("region") or {}).get("name") if isinstance(d.get("region"), dict) else d.get("region"),
            "value_now": d.get("value_now"), "value_max": d.get("value_max"), "to_do": todo,
            **capped((_body_brief(b) for b in bodies), rows, "bodies")}


def _sys_brief(x):
    out = {"name": x.get("name"), "distance_ly": rnd(x.get("distance"), 2), "visited": x.get("visited"),
           "main_star": x.get("main_class") or x.get("main_star"), "scoopable": x.get("main_scoopable"),
           "bodies_known": x.get("bodies_known"), "body_count": x.get("body_count"), "value_max": x.get("value_max") or None,
           "bio_potential": x.get("bio_potential"), "notable": x.get("notable") or None, "scan_status": x.get("status"),
           "your_first_discovery": (x.get("firsts") or {}).get("sale") if x.get("firsts") else None}
    return {k: v for k, v in out.items() if v is not None}


def _from_you(p):
    """Nearby's rows with `distance` from the commander, and the system the list is around when it is not them (the
    page's Around, near_around: its rows' own distance is from there); rows with no position are left out then."""
    xs, a, pos = p.get("systems") or [], p.get("near_around") or {}, p.get("position") or {}
    if a.get("around", "here") == "here" or a.get("why") or a.get("x") is None:
        return xs, None
    if pos.get("x") is None:
        return [], a.get("name")
    here = (pos["x"], pos["y"], pos["z"])
    return [dict(x, distance=round(math.dist(x["xyz"], here), 2)) for x in xs if x.get("xyz")], a.get("name")


@tool("nearby_systems", "Systems known around the commander within the page's radius, nearest first (or by value), "
      "with distance, main star and whether it can be scooped, bodies known, value and biology potential.",
      {"sort": {"type": "string", "enum": ["distance", "value"], "description": "nearest first (default) or most valuable first"},
       "unvisited_only": {"type": "boolean", "description": "only systems never visited"}})
async def nearby_systems(get, args, rows):
    p = await get("/api/nearby")
    here = (p.get("position") or {}).get("id")
    xs, around = _from_you(p)
    xs = [x for x in xs if x.get("id") != here and x.get("source") != "route"]
    if args.get("unvisited_only"):
        xs = [x for x in xs if not x.get("visited")]
    xs.sort(key=(lambda x: -(x.get("value_max") or 0)) if args.get("sort") == "value" else (lambda x: x.get("distance") or 0))
    # the page's Nearby set around another system: its sphere is there, the distances are still from the commander
    where = {"list_around": around, "distance_from": "the commander"} if around else {}
    return {"radius_ly": p.get("radius"), "complete_to_ly": p.get("sphere_cut"), **where,
            **capped(map(_sys_brief, xs), rows, "systems")}


@tool("nearest_unvisited", "The nearest system Spansh or EDSM know that the commander has never visited (any unvisited "
      "star closer than it on the galaxy map has never been reported).")
async def nearest_unvisited(get, args, rows):
    p = await get("/api/nearby")
    here = (p.get("position") or {}).get("id")
    xs, around = _from_you(p)
    if around:   # the list is around another system: it says nothing of the stars around the commander
        return {"nearest": None, "note": f"Nearby is set around {around}, not around you: set its Around back to you "
                                         "to find the nearest unvisited system."}
    xs = sorted((x for x in xs if x.get("id") != here and not x.get("visited") and x.get("source") != "route"),
                key=lambda x: x.get("distance") or 0)
    cut = p.get("sphere_cut")
    if not xs or (cut is not None and xs[0].get("distance", 0) > cut):
        return {"nearest": None, "note": f"no known unvisited system within {cut if cut is not None else p.get('radius')} ly"}
    return {"nearest": _sys_brief(xs[0]), "next_ones": [_sys_brief(x) for x in xs[1:min(len(xs), 1 + max(0, min(rows, 5) - 1))]]}


@tool("nearest_scoopable", "The nearest known system whose main star can be scooped for fuel (KGBFOAM), from the "
      "commander, and whether it is within one jump at the range they have now (fuel and cargo aboard); `here` when the "
      "star they are at scoops; any unreported star nearer could be scoopable too (most are).")
async def nearest_scoopable(get, args, rows):
    p = await get("/api/nearby")
    here = (p.get("position") or {}).get("id")
    xs, around = _from_you(p)
    # the star you are at, when it scoops (review 8: it was skipped, and a low-fuel player sent on elsewhere)
    at = next((x for x in xs if x.get("id") == here and x.get("main_scoopable")), None)
    xs = sorted((x for x in xs if x.get("id") != here and x.get("main_scoopable") and x.get("distance") is not None),
                key=lambda x: x["distance"])
    s = await get("/api/status")
    jr = s.get("jump_range_now") or s.get("jump_range")   # with the fuel and cargo aboard (review 8: not the best case)
    # the page's Nearby set around another system: its stars, measured from the commander; nearer ones may be missing
    where = {"note": f"Nearby is set around {around}, not around you: a nearer scoopable star may be missing"} if around else {}
    if at:
        where["here"] = {"name": at.get("name"), "main_star": at.get("main_class") or at.get("main_star")}
    if not xs:
        return {"nearest": None, "radius_ly": p.get("radius"), "jump_range_ly": jr, **where}
    one = lambda x: None if not jr else x["distance"] <= jr
    return {"nearest": dict(_sys_brief(xs[0]), one_jump=one(xs[0])), "jump_range_ly": jr, **where,
            "next_ones": [dict(_sys_brief(x), one_jump=one(x)) for x in xs[1:min(len(xs), 1 + max(0, min(rows, 5) - 1))]]}


@tool("nearest_dock", "The nearest stations and fleet carriers the commander can dock at (pad size, docking access, "
      "recent reports), from Spansh, the Deep Space Support Array's list, their own carrier and their squadron's; "
      "optionally only those with given services, a material trader among them.",
      {"need": {"type": "array", "items": {"type": "string", "enum": list(dock.SERVICES)},
                "description": "services every place must have (UC: Universal Cartographics, Vista: Vista Genomics; "
                               "Trader: a material trader of any kind, Raw / Manufactured / Encoded: a material trader of "
                               "that kind, at stations only)"},
       "kind": {"type": "string", "enum": ["any", "station", "carrier"], "description": "stations, carriers or both (default)"},
       "age_days": {"type": "integer", "description": "leave out reports older than this (default 30)"}})
async def nearest_dock(get, args, rows):
    need = args.get("need") or []
    if isinstance(need, str):   # one service sent as a string (models often do): not its letters
        need = [need]
    need = [n for n in need if isinstance(n, str)]
    kind = args.get("kind") if args.get("kind") in ("station", "carrier") else "any"
    q = {"need": ",".join(need), "age": str(_int(args, "age_days", 30, 1, 3650)), "cached": "1",
         "stations": "0" if kind == "carrier" else "1", "carriers": "0" if kind == "station" else "1"}
    d = await get("/api/nearest", q)
    if d.get("error"):
        return {"error": d["error"]}
    def brief(r):
        return {"name": r.get("name") or r.get("callsign"), "callsign": r.get("callsign") or None, "kind": r.get("kind"),
                "station_type": r.get("station_type"),
                "system": r.get("system"), "distance_ly": r.get("ly"), "from_star_ls": rnd(r.get("ls"), 0),
                "services": r.get("services"), "pads": r.get("pads"), "dssa": bool(r.get("dssa")),
                "yours": bool(r.get("own")) and not r.get("squadron"), "your_squadrons": bool(r.get("own") and r.get("squadron")),
                "squadron_carrier": bool(r.get("squadron")),
                "warnings": r.get("warn") or [], "report_age_days": rnd((r.get("age_s") or 0) / 86400) if r.get("age_s") is not None else None}
    # errors: Spansh could not be reached, say (the places are then only the DSSA list and your carrier): passed on,
    # so the answer can say so rather than call a far carrier the nearest place
    return {"hidden": d.get("hidden"), "pad": d.get("pad"), "errors": d.get("errors") or None,
            **capped(map(brief, d.get("rows") or []), min(rows, 10), "places")}


@tool("nearest_ggg", "The nearest potential green gas giants in what Outrider has cached (Spansh's records and the "
      "commander's scans): the community's ladder model on each giant's temperature, mass and radius, a guess to check "
      "in the system map, never a fact.",
      {"radius_ly": {"type": "integer", "description": "how far to look in light years (default 500, at most 1000)"}})
async def nearest_ggg(get, args, rows):
    d = await get("/api/ggg", {"radius": str(_int(args, "radius_ly", 500, 1, 1000))})
    if d.get("error"):
        return {"error": d["error"]}
    giants = [{"system": b.get("system"), "body": b.get("body"), "distance_ly": rnd(b.get("distance")), "chance": b.get("chance")}
              for b in d.get("bodies") or []]
    out = {"radius_ly": d.get("radius"), "systems_searched": d.get("searched"), **capped(giants, min(rows, 10), "giants")}
    if d.get("more"):
        out["more"] = out.get("more", 0) + d["more"]
    return out


@tool("body_detail", "One body in the current system (or another system by its id64): its values, signals, biology "
      "(predicted and sampled), mining odds and surface facts.",
      {"name": {"type": "string", "description": "the body's name, e.g. \"A 2\" or the full \"Synuefe XR-H d11-102 A 2\""},
       "system_id64": {"type": "string", "description": "the system's id64 (default: the system the commander is in)"}},
      required=("name",))
async def body_detail(get, args, rows):
    name = " ".join(str(args.get("name") or "").split())
    sid = str(args.get("system_id64") or "")
    if not sid:
        s = await get("/api/status")
        sid, sysname = s.get("id64"), s.get("system") or ""
        if not sid:
            return {"error": "no position yet"}
        if sysname and name.lower().startswith(sysname.lower() + " "):
            name = name[len(sysname) + 1:]
    if not re.fullmatch(r"\d{1,20}", str(sid)) or not name:
        return {"error": "give the body's name (and a numeric system_id64 for another system)"}
    d = await get("/api/body", {"system": sid, "name": name})
    if d.get("error"):
        return {"error": d["error"]}
    if not (d.get("row") or d.get("own") or d.get("spansh")):   # the name matched nothing: say so, not an empty body
        return {"error": f"no body called {name!r} is known in {d.get('system') or 'that system'}"}
    b = d.get("row") or {}
    out = _body_brief(b)
    out.update({"system": d.get("system"), "full_name": d.get("full_name"), "radius_km": rnd(b.get("radius_km"), 0),
                "temperature_k": rnd(b.get("temperature"), 0), "volcanism": b.get("volcanism") or None,
                "bio_predicted": [{"genus": g.get("genus"), "likeliest": g.get("best"), "up_to": g.get("value")}
                                  for g in b.get("bio_guess") or [] if isinstance(g, dict)][:rows] or None,
                "mining_odds": b.get("mining_odds"), "value_if_mapped": b.get("value_if_mapped")})
    return {k: v for k, v in out.items() if v is not None}


@tool("unsold_data", "What the commander carries unsold: the cartographic and exobiology estimates, the systems "
      "with unsold first discoveries (most valuable first), and how many systems have lost firsts to rescan.")
async def unsold_data(get, args, rows):
    p = await get("/api/nearby")
    f = await get("/api/firsts")
    u = p.get("unsold") or {}
    c, b = u.get("carto") or {}, u.get("bio") or {}
    firsts = f.get("firsts") or []
    unsold = sorted((x for x in firsts if x.get("state") == "unsold"), key=lambda x: -(x.get("value") or 0))
    return {"total": u.get("total"),
            "cartographic": {"estimated_payout": c.get("estimated_payout"), "systems": c.get("systems"), "bodies": c.get("bodies"),
                             "first_discoveries": c.get("first_discoveries"), "mapped": c.get("mapped")},
            "exobiology": {"estimated_value": b.get("estimated_value"), "samples": b.get("samples")},
            "since_last_sale": p.get("since_sale"),
            "lost_firsts_systems": sum(1 for x in firsts if x.get("state") == "lost"),
            **capped(({"name": x.get("name"), "distance_ly": rnd(x.get("distance"), 1), "value": x.get("value")} for x in unsold),
                     rows, "unsold_firsts")}


@tool("left_behind", "Visited systems within a radius that still have work worth going back for, nearest first: bodies "
      "never found, biology never sampled (with what it could pay, an upper bound), planets worth mapping (with what "
      "mapping adds), and each system's worth (those values added up).",
      {"radius_ly": {"type": "integer", "minimum": 10, "maximum": 500, "description": "how far around (default 100)"}})
async def left_behind(get, args, rows):
    r = _int(args, "radius_ly", 100, 10, 500)
    d = await get("/api/left", {"radius": str(r)})
    xs = []
    for x in d.get("systems") or []:
        # S14: the values /api/left carries per item, passed on (the voice filters them at the server's thresholds)
        bio = [{"body": b.get("body"), "up_to": b.get("value") or 0} if isinstance(b, dict) else {"body": b, "up_to": 0}
               for b in x.get("bio") or []]
        maps = [{"body": m.get("body"), "type": m.get("subtype"), "adds": m.get("increment") or 0}
                for m in x.get("maps") or [] if isinstance(m, dict)]
        xs.append({"name": x.get("name"), "distance_ly": rnd(x.get("distance"), 1), "bodies_not_found": x.get("unfound") or None,
                   "bio": bio or None, "map": maps or None, "worth_mapping": x.get("maps_total") or None,
                   "worth": sum(b["up_to"] for b in bio) + sum(m["adds"] for m in maps)})
    return {"radius_ly": r, **capped(({k: v for k, v in x.items() if v is not None} for x in xs), rows, "systems")}


@tool("highway_route", "The Neutron Highway route being flown: the next system (distance, neutron star, refuel), "
      "jumps and light years left, refuel in how many jumps, whether the commander is off the route, and the jumps ahead.")
async def highway_route(get, args, rows):
    h = await get("/api/highway")
    rt = h.get("route")
    if not rt:
        return {"route": None, "note": "no Highway route plotted"}
    s = rt.get("summary") or {}
    nx = s.get("next") or {}
    ahead = [{"system": r.get("system"), "distance_ly": rnd(r.get("distance"), 1), "neutron": r.get("neutron") or None,
              "refuel": r.get("refuel") or None} for r in rt.get("ahead") or []]
    return {"next": {"system": nx.get("name"), "distance_ly": nx.get("distance"), "neutron": nx.get("neutron"),
                     "refuel_there": nx.get("refuel")} if nx else None,
            "destination": rt.get("to"), "jumps_left": s.get("jumps_left"), "ly_left": rnd(s.get("ly_left"), 0),
            "refuel_in_jumps": s.get("refuel_in"), "refuel_here": s.get("refuel_here"), "boost_here": s.get("boost_here"),
            "off_route": s.get("off_route"), "nearest_route_system": (s.get("nearest") or {}).get("name") if s.get("off_route") else None,
            "complete": s.get("complete"),
            **capped(({k: v for k, v in x.items() if v is not None} for x in ahead), rows, "ahead")}


def _newer(a, b):
    """The route of two summaries (the Highway's, the survey slot's) plotted last that is not finished, else None."""
    live = [x for x in (a, b) if x and not x.get("complete")]
    return max(live, key=lambda x: x.get("created_ts") or "") if live else None


@tool("route_next", "The next stop of whichever route the commander follows: the Neutron Highway, a Road to Riches, "
      "Exomastery, world, sweep or trade route (the one plotted last), else the header's next stop (a bookmark), else the "
      "route plotted in the game; its distance, jumps, how much is left and whether the commander is off it.")
async def route_next(get, args, rows):
    p = await get("/api/nearby")
    hw, sv = p.get("highway"), p.get("survey")
    pick = _newer(hw, sv)
    if pick is not None:
        nx = pick.get("next") or {}
        kind = "highway" if pick is hw else "survey"
        sk = riches.survey_kind(pick.get("kind")) if kind == "survey" else None
        out = {"kind": kind, "route": "Neutron Highway" if kind == "highway" else sk.what, "destination": pick.get("destination"),
               "next": {"system": nx.get("name"), "distance_ly": nx.get("distance"), "jumps": nx.get("jumps"),
                        "neutron": nx.get("neutron"), "refuel_there": nx.get("refuel")} if nx else None,
               "off_route": pick.get("off_route"),
               "nearest_route_system": (pick.get("nearest") or {}).get("name") if pick.get("off_route") else None}
        if kind == "highway":
            out.update(jumps_left=pick.get("jumps_left"), refuel_in_jumps=pick.get("refuel_in"))
        else:
            index, total = pick.get("index"), pick.get("total")
            out["stops_left"] = total - index + 1 if index is not None and total is not None else None
        return out
    done = [x for x in (hw, sv) if x and x.get("complete")]
    ns = p.get("next_stop")
    if ns and ns.get("name"):
        return {"kind": "next_stop", "route": "your next stop", "next": {"system": ns["name"], "distance_ly": ns.get("distance")},
                "complete_route": bool(done)}
    gr = p.get("route") or {}
    hops = gr.get("hops") or []
    if hops:
        return {"kind": "game_route", "route": "the route plotted in the game", "destination": hops[-1].get("name"),
                "next": {"system": hops[0].get("name"), "distance_ly": hops[0].get("ly"), "scoopable": hops[0].get("scoopable")},
                "jumps_left": len(hops), "ly_left": gr.get("ly"), "complete_route": bool(done)}
    return {"kind": None, "next": None, "complete_route": bool(done)}


@tool("travel_history", "The commander's play sessions in the last N days: jumps, light years, first discoveries, "
      "mapped bodies, samples and the systems visited, plus all-time totals.",
      {"days": {"type": "integer", "minimum": 1, "maximum": 365, "description": "how far back (default 7)"}})
async def travel_history(get, args, rows):
    days = _int(args, "days", 7, 1, 365)
    d = await get("/api/history", {"days": str(days)})
    sess = [{"start": x.get("start"), "end": x.get("end"), "jumps": x.get("jumps"), "ly": rnd(x.get("ly"), 0),
             "first_discoveries": x.get("firsts"), "mapped": x.get("mapped"), "samples": x.get("samples"),
             "systems": [y.get("name") if isinstance(y, dict) else y for y in x.get("systems") or []][:10]}
            for x in d.get("sessions") or []]
    return {"days": days, "all_time": d.get("all_time"), **capped(sess, rows, "sessions")}


@tool("materials", "The commander's engineering materials: what each synthesis (FSD injection, SRV refuel...) can be "
      "made how many times from what is held, and the materials held, fullest first (count against cap).",
      {"name": {"type": "string", "description": "only materials whose name contains this (e.g. \"polonium\")"}})
async def materials(get, args, rows):
    d = await get("/api/materials")
    want = str(args.get("name") or "").strip().lower()
    held = [r for r in d.get("rows") or [] if (r.get("count") or 0) > 0 or want]
    if want:
        held = [r for r in held if want in (r.get("name") or "").lower()]
    held.sort(key=lambda r: -((r.get("count") or 0) / (r.get("cap") or 1)))
    # group and grade: the voice's "FSD injections" picks the three by group (S14), never by a recipe's name
    return {"synthesis": [{"name": s.get("name"), "group": s.get("group"), "grade": s.get("grade"), "can_make": s.get("craftable"),
                           "limited_by": s.get("limit") or None} for s in d.get("synthesis") or []],
            "counts_from": d.get("snapshot_ts"), "stale": d.get("stale") or None,
            **capped(({"name": r.get("name"), "grade": r.get("grade"), "category": r.get("category"), "count": r.get("count"),
                       "cap": r.get("cap")} for r in held), rows, "held")}


# ---- calling them ----

def listing():
    """The tools as an AI client sees them: [{name, description, inputSchema}]."""
    return [{"name": t["name"], "description": t["description"], "inputSchema": t["schema"]} for t in TOOLS.values()]


async def call(name, args, get, rows=DEFAULT_ROWS):
    """Run one tool: its compact answer, or {"error": ...} (an unknown tool, Outrider not running)."""
    t = TOOLS.get(name)
    if not t:
        return {"error": f"no tool called {name!r}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be an object"}
    try:
        return await t["handler"](guarded(get), args, max(1, int(rows)))
    except Unavailable:
        return {"error": NOT_RUNNING}
    except Refused as e:
        return {"error": str(e)}


def query(path, params):
    """`path?params` (for an HTTP `get`)."""
    return path + ("?" + urllib.parse.urlencode(params) if params else "")
