"""Potential green gas giants (the author's ask, 2026-10-12). Pure.

A green gas giant looks like any other in the FSS: nothing flags it. The community's "seven-layer ladder" model says
which ones render green: from a giant's surface temperature, mass and radius come seven evenly spaced cloud-layer
temperatures; when one lands exactly on a colour border of its class, the giant is green. Exactly means in the game's
32-bit float arithmetic: some green windows are 0.00002 K wide, so only a journal's full-precision temperature will do
(never Spansh's rounded one).

The model is CMDR Regza's (with AI assistance), from a hint by Dr. K. Ross and CMDR Arcanic (whose edGGG catalogue it
was fitted to), as published by Canonn (github.com/canonn-science/EDMC-Canonn issue 222, 2026-10-05). It is a
reconstruction, not the game's own code: a prediction is "potential", and a codex entry always beats it. Written here
from those published rules; the class rules are a table so corrections can land without touching the arithmetic.
"""
import math
import struct

M_EARTH_KG = 5.9722e24
UNCAPPED_TOLERANCE_K = 0.0002   # an uncapped ladder's hit (its arithmetic is not known to the bit): this close counts
RUNGS = 7

# (class, lowest K or None, highest K (exclusive) or None, rule). A rule: ceiling (the ladder's top, K; None: uncapped),
# min_step (K or None), borders (K), sure (the rule confirmed by catalogue bodies, else derived). "nudged": the game
# moves the bottom rung by an unexplained offset there, so nothing can be said. A class or range not listed: unknown.
RULES = [
    ("class1", None, 80, {"ceiling": 340, "borders": (115, 250, 270), "sure": True}),
    ("class1", 80, 113, "nudged"),
    ("class1", 113, 330, {"ceiling": 340, "borders": (115, 250, 270), "sure": True}),
    ("ammonia_life", None, 80, {"ceiling": 340, "borders": (175, 250, 270), "sure": True}),
    ("ammonia_life", 80, 113, "nudged"),
    ("ammonia_life", 113, None, {"ceiling": 340, "borders": (175, 250, 270), "sure": True}),
    ("water_life", 150, 250, {"ceiling": 340, "borders": (210, 270), "sure": True}),
    ("water_giant", 157.999, 158.001, {"ceiling": 340, "borders": (210,), "sure": True}),
    ("class2", None, None, "nudged"),
    ("class3", None, 370, "nudged"),
    ("class3", 370, 370.0001, {"ceiling": None, "borders": (370,), "sure": True}),
    ("class3", 370.0001, 415, "nudged"),
    ("class3", 490, 680, {"ceiling": 700, "min_step": 30, "borders": (700,), "sure": True}),
    ("class3", 680, 900, {"ceiling": 1200, "min_step": 30, "borders": (700, 900), "sure": False}),
    ("class3", 900, None, {"ceiling": 1500, "min_step": 30, "borders": (1400,), "sure": False}),
    ("class4", 900, None, {"ceiling": 1500, "borders": (900, 1400), "sure": True}),
    ("class5", None, None, "nudged"),
    ("helium", None, None, "nudged"),
]
# the game's codex names for a green one (Tourist): a body with one of these is green, no guess needed
CODEX_GREEN = ("Green Gas Giant", "Green Class I Gas Giant", "Green Class II Gas Giant", "Green Class III Gas Giant",
               "Green Class IV Gas Giant", "Green Class V Gas Giant", "Green Water Giant", "Green Gas Giant with Ammonia Life")
SPOKEN_CLASS = {"class1": "a class one gas giant", "class3": "a class three gas giant", "class4": "a class four gas giant",
                "water_life": "a gas giant with water-based life", "ammonia_life": "a gas giant with ammonia-based life",
                "water_giant": "a water giant"}


def f32(v):
    """v rounded through a 32-bit float, as the game computes."""
    return struct.unpack("f", struct.pack("f", float(v)))[0]


def gas_class(planet_class):
    """The rule table's class for a journal PlanetClass ("Sudarsky class I gas giant" -> "class1"), or None."""
    s = str(planet_class or "").lower().replace("-", " ")
    if "helium" in s:
        return "helium"
    if "water giant" in s:
        return "water_giant"
    if "life" in s:
        return "ammonia_life" if "ammonia" in s else "water_life" if "water" in s else None
    for roman, key in (("class v ", "class5"), ("class iv ", "class4"), ("class iii ", "class3"), ("class ii ", "class2"),
                       ("class i ", "class1")):
        if roman in s + " ":
            return key
    return None


def rule_for(cls, temp):
    for c, lo, hi, rule in RULES:
        if c == cls and (lo is None or temp >= lo) and (hi is None or temp < hi):
            return rule
    return None


def predict(scan):
    """A journal Scan (PlanetClass, SurfaceTemperature, MassEM, Radius in metres) -> None (not green, or nothing can
    be said) or {"chance": "likely" (a confirmed rule) | "possible" (a derived one), "class", "rung" (1..7),
    "border" (K), "temperature"}."""
    if not isinstance(scan, dict):
        return None
    cls, t = gas_class(scan.get("PlanetClass")), scan.get("SurfaceTemperature")
    mass, radius = scan.get("MassEM"), scan.get("Radius")
    if cls is None or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (t, mass, radius)) \
            or mass <= 0 or radius <= 0:
        return None
    rule = rule_for(cls, float(t))
    if not isinstance(rule, dict):
        return None
    density = mass * M_EARTH_KG / (4.0 / 3.0 * math.pi * float(radius) ** 3)   # kg/m³
    depth = 5.0 / 9.0 * 1300.0 * (t / 1300.0) ** 1.2 * density ** 0.2      # the ladder's span above the surface (K)
    ceiling, min_step = rule.get("ceiling"), rule.get("min_step")
    capped = ceiling is not None and t + depth >= ceiling
    hit = None
    if capped or min_step is not None:   # exact, in the game's float32 arithmetic
        t32, top32 = f32(t), f32(ceiling if capped else t + depth)
        step = f32(f32(top32 - t32) / f32(RUNGS))
        if min_step is not None:
            step = max(step, f32(min_step))
        for k in range(RUNGS):
            rung = f32(t32 + f32(f32(k) * step))
            hit = hit or next(((k + 1, b) for b in rule["borders"] if rung == f32(b)), None)
    else:                                # an uncapped ladder: within a hair of a border
        step = depth / RUNGS
        for k in range(RUNGS):
            hit = hit or next(((k + 1, b) for b in rule["borders"] if abs(t + k * step - b) <= UNCAPPED_TOLERANCE_K), None)
    if not hit:
        return None
    return {"chance": "likely" if rule["sure"] else "possible", "class": cls, "rung": hit[0], "border": hit[1],
            "temperature": t}


def confirmed(codex_names):
    """Whether a body's codex entries say it is green."""
    return any(str(n or "").strip() in CODEX_GREEN for n in codex_names or ())


# A green giant's codex entry is its type's entry id + 1 ("Sudarsky class I gas giant" 1200501, its green one 1200502:
# EDDN's codex entries, 2026-10-25), and its BodyID is the system's main star, never the giant (4 of 4 green entries
# in a capture of every player's EDDN traffic): which giant is green is told by its class, not by the body.
TYPE_ENTRY = {"class1": 1200501, "class2": 1200601, "class3": 1200701, "class4": 1200801, "class5": 1200901,
              "helium": 1201001, "water_giant": 1200101, "water_life": 1200301, "ammonia_life": 1200401}
GREEN_ENTRY = {i + 1: cls for cls, i in TYPE_ENTRY.items()}


def green_class(entry_id, name=None):
    """A codex entry's green giant class ("class1"...), "" for a green one of no class named ("Green Gas Giant"), or
    None when it is not a green giant's entry."""
    if entry_id in GREEN_ENTRY:
        return GREEN_ENTRY[entry_id]
    n = str(name or "").strip()
    if n in CODEX_GREEN or n.lower().startswith("$codex_ent_green_"):
        return gas_class(n.lower().replace("$codex_ent_green_", "").replace("_", " ").replace("sudarsky ", "")) or ""
    return None


def record_class(r):
    """A body record's gas giant class (gas_class of its journal PlanetClass, else its subtype), or None."""
    ed = r.get("ed") if isinstance(r.get("ed"), dict) else {}
    return gas_class(ed.get("PlanetClass") or r.get("subtype"))


def match_green(entries, records):
    """Which of a system's bodies its green giant codex entries mean: {body name: {"confirmed": True, "of": n}} (n > 1:
    one of n giants of that class, the journal never says which). entries: (entry_id, name, body_id) of the system's
    codex lines. A giant of the class the entry names, at the entry's own body (an older journal, a test) first;
    else the only one of that class; else the ones the model flags among them; else all of them."""
    out = {}
    for entry_id, name, body_id in entries:
        cls = green_class(entry_id, name)
        if cls is None:
            continue
        giants = [r for r in records if r.get("type") == "Planet" and record_class(r) and (not cls or record_class(r) == cls)]
        own = [r for r in giants if body_id is not None and r.get("body_id") == body_id]
        flagged = [r for r in giants if predict_record(r)]
        pick = own or (giants if len(giants) == 1 else flagged or giants)
        for r in pick:
            if r.get("name"):
                had = out.get(r["name"])
                out[r["name"]] = {"confirmed": True, "of": min(len(pick), had["of"]) if had else len(pick)}
    return out


def green_count(entries, records):
    """How many green giants a system's codex lines confirm: each line that matches a giant counts once (review
    2026-10-25: a line naming no class over two giants of different classes was counted once per class, x2), never
    more than the giants matched."""
    matched = [e for e in entries if match_green([e], records)]
    return min(len(matched), len(match_green(entries, records)))


def predict_record(r):
    """predict() for one of Outrider's body records (yours from the journal, or Spansh's from someone else's scan:
    both keep the journal's own temperature): the class from ed.PlanetClass (or subtype), the mass from ed.MassEM (a
    Spansh body search's record: mass_em), radius_km back to metres."""
    if not isinstance(r, dict) or r.get("type") != "Planet":
        return None
    ed = r.get("ed") if isinstance(r.get("ed"), dict) else {}
    km = r.get("radius_km")
    return predict({"PlanetClass": ed.get("PlanetClass") or r.get("subtype"), "SurfaceTemperature": r.get("temperature"),
                    "MassEM": ed.get("MassEM") if ed.get("MassEM") is not None else r.get("mass_em"),
                    "Radius": km * 1000 if isinstance(km, (int, float)) else None})


def searchable_classes():
    """The classes a prediction can be made for (a rule other than "nudged" somewhere in their temperatures)."""
    return sorted({c for c, _, _, rule in RULES if isinstance(rule, dict)})
