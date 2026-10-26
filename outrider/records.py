"""Your records (the author, 2026-10-25): the most extreme bodies among your own scans, from the Scan lines Outrider
keeps (own_bodies.raw), and the system farthest from Sol you have been to. Pure: the server hands in the rows and asks
again only when your scans or jumps change. Nav-beacon reads are left out, as they are from your discoveries.

    records(bodies, jumps) -> [{key, label, value, text, body, system, id64, ts}]

bodies: (id64, system name, body name, ts, raw Scan dict); jumps: (id64, name, x, y, z, ts).
"""
import math

G = 9.80665                 # SurfaceGravity is m/s²
SOLAR_RADIUS_M = 695_700_000
NAV_BEACON = ("NavBeacon", "NavBeaconDetail")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _star(e):
    return bool(e.get("StarType"))


def _planet(e):
    return bool(e.get("PlanetClass"))


def _landable(e):
    return _planet(e) and e.get("Landable") is True


def _solid(e):
    """A planet or moon with a surface: a gas giant's SurfacePressure is no surface's (the author's: 140 million atm)."""
    return _planet(e) and "giant" not in str(e.get("PlanetClass")).lower()


def _ring_width(e):
    widths = [r["OuterRad"] - r["InnerRad"] for r in e.get("Rings") or []
              if _num(r.get("OuterRad")) is not None and _num(r.get("InnerRad")) is not None and "Belt" not in str(r.get("Name"))]
    return max(widths) if widths else None


def _pressure_words(pa):
    """A pressure in words: atm with two figures at least, else Pa, never scientific notation (third and fourth in-depth
    reviews 2026-10-25: a few Pa read "0.0000 atm", 0.06 atm "0.1 atm", a trace "3.5e-05 Pa")."""
    atm = pa / 101325
    if atm >= 10:
        return f"{atm:,.0f} atm"
    if atm >= 1:
        return f"{atm:,.1f} atm"
    if pa >= 1000:
        return f"{atm:.2f} atm" if atm >= 0.1 else f"{atm:.3f} atm"
    if pa >= 1:
        return f"{pa:,.0f} Pa" if pa >= 100 else f"{pa:.1f} Pa"
    return "under 1 Pa"


# (key, label, which bodies, the figure, highest (True) or lowest, its words)
RECORDS = [
    ("hot_star", "Hottest star", _star, lambda e: _num(e.get("SurfaceTemperature")), True, lambda v: f"{v:,.0f} K"),
    ("big_star", "Biggest star", _star, lambda e: _num(e.get("Radius")), True, lambda v: f"{v / SOLAR_RADIUS_M:,.1f} solar radii"),
    ("heavy_star", "Heaviest star", _star, lambda e: _num(e.get("StellarMass")), True, lambda v: f"{v:,.2f} solar masses"),
    ("hot_planet", "Hottest planet", _planet, lambda e: _num(e.get("SurfaceTemperature")), True, lambda v: f"{v:,.0f} K"),
    ("cold_planet", "Coldest planet", _planet, lambda e: _num(e.get("SurfaceTemperature")), False, lambda v: f"{v:,.0f} K"),
    ("big_planet", "Biggest planet", _planet, lambda e: _num(e.get("Radius")), True, lambda v: f"{v / 1000:,.0f} km"),
    ("small_body", "Smallest planet or moon", _planet, lambda e: _num(e.get("Radius")), False, lambda v: f"{v / 1000:,.0f} km"),
    ("heavy_planet", "Heaviest planet", _planet, lambda e: _num(e.get("MassEM")), True, lambda v: f"{v:,.1f} Earth masses"),
    ("high_g", "Highest gravity, landable", _landable, lambda e: _num(e.get("SurfaceGravity")), True, lambda v: f"{v / G:,.2f} g"),
    ("low_g", "Lowest gravity, landable", _landable, lambda e: _num(e.get("SurfaceGravity")), False, lambda v: f"{v / G:,.3f} g"),
    ("elw_g", "Highest-gravity Earth-like", lambda e: e.get("PlanetClass") == "Earthlike body",
     lambda e: _num(e.get("SurfaceGravity")), True, lambda v: f"{v / G:,.2f} g"),
    # an airless body's 0 holds no record (in-depth review 2026-10-25: "Thickest atmosphere 0.0 atm"); a thin one shows
    # its figure, not 0.0
    ("pressure", "Thickest atmosphere", _solid, lambda e: _num(e.get("SurfacePressure")) or None, True, lambda v: _pressure_words(v)),
    ("spin", "Fastest spin", _planet, lambda e: abs(_num(e.get("RotationPeriod")) or 0) or None, False,
     lambda v: f"{v / 3600:,.2f} h" if v >= 3600 else f"{v / 60:,.1f} min"),
    # a retrograde orbit's period is negative (the author's journals): its length is what counts
    ("orbit", "Shortest orbit", _planet, lambda e: abs(_num(e.get("OrbitalPeriod")) or 0) or None, False,
     lambda v: f"{v / 3600:,.1f} h" if v < 172800 else f"{v / 86400:,.1f} days"),
    ("far_out", "Farthest from its arrival star", lambda e: True, lambda e: _num(e.get("DistanceFromArrivalLS")) or None, True,
     lambda v: f"{v:,.0f} ls"),
    ("wide_ring", "Widest ring", _planet, _ring_width, True, lambda v: f"{v / 1000:,.0f} km"),
]


def records(bodies, jumps=()):
    """The records among `bodies` (each the most extreme of its kind; a tie goes to the first scanned) and the system
    farthest from Sol among `jumps`; a record no body has a figure for is left out."""
    best = {}
    for id64, system, body, ts, e in bodies:
        if not isinstance(e, dict) or e.get("ScanType") in NAV_BEACON:
            continue
        for key, _label, which, figure, high, _words in RECORDS:
            if not which(e):
                continue
            v = figure(e)
            if v is None:
                continue
            had = best.get(key)
            if had is None or (v > had[0] if high else v < had[0]):
                best[key] = (v, id64, system, body, ts)
    out = []
    for key, label, _which, _figure, _high, words in RECORDS:
        if key in best:
            v, id64, system, body, ts = best[key]
            out.append({"key": key, "label": label, "value": v, "text": words(v), "body": body, "system": system,
                        "id64": str(id64), "ts": ts})
    far = max(((math.sqrt(x * x + y * y + z * z), id64, name, ts) for id64, name, x, y, z, ts in jumps
               if None not in (x, y, z)), default=None)
    if far:
        out.append({"key": "far_sol", "label": "Farthest from Sol", "value": far[0], "text": f"{far[0]:,.0f} ly",
                    "body": None, "system": far[2], "id64": str(far[1]), "ts": far[3]})
    return out
