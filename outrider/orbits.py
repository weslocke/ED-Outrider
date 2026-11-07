"""Where a system's bodies are now, from the orbits in your own scans: the suggested order's legs (Here, Now, the
schematic, the overlay) are timed on the distance between two bodies, not on their distances to the arrival star.

The method was found and checked against the game's own navigation panel (199 readings in nine systems, 2026-11-07;
DESIGN_NOTES "The suggested order by where the bodies are"):

- A body's orbit is in its Scan, a barycentre's in ScanBaryCentre. A barycentre's parent is the next entry in a
  child's Parents chain. The root (barycentre 0, or a star with no orbit) is the origin.
- The mean anomaly is advanced from the scan's own time by elapsed / OrbitalPeriod, then negated (the orbit runs the
  other way from the textbook), and Kepler's equation is solved for E.
- In the orbit's plane x = a(cos E - e), y = a·√(1-e²)·sin E, turned into space by the textbook rotation of Ω
  (AscendingNode), i (OrbitalInclination) and ω (Periapsis).
- The frame rule: a child's offset is turned by its parent's Rz(Ω)·Rx(i)·Rz(ω), one level only, when the parent is a
  star with an orbit or a barycentre whose members are all planets (a planet pair). A barycentre of stars turns
  nothing, nor does a planet.
- Approximate (about 2% across families, up to ~14% in nested multi-star layouts): a body whose chain crosses a
  barycentre of stars that is not the root, or a node with no orbit known (a barycentre with no ScanBaryCentre, a
  parent never scanned: its children are placed at its own parent, never at the origin).

Do not check positions against DistanceFromArrivalLS: once angles are involved it is not the true distance.
Pure functions: no state, no I/O. Distances in light seconds."""
import math

from outrider.core import ts_seconds

C = 299_792_458.0          # m/s: SemiMajorAxis is in metres, positions in light seconds
ELEMENTS = ("SemiMajorAxis", "Eccentricity", "OrbitalInclination", "OrbitalPeriod", "Periapsis", "AscendingNode",
            "MeanAnomaly")


def kepler(m, e):
    """Kepler's equation E - e·sin E = M solved for the eccentric anomaly E (radians), by Newton's method."""
    e = min(max(e or 0.0, 0.0), 0.999)
    m = math.fmod(m, 2 * math.pi)
    big = e >= 0.8
    E = math.pi if big else m
    for _ in range(50):
        d = (E - e * math.sin(E) - m) / (1 - e * math.cos(E))
        E -= d
        if abs(d) < 1e-13:
            break
    return E


def _num(el, key):
    v = el.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def has_orbit(el):
    """Whether the elements place the body on its orbit: a semi-major axis and a mean anomaly (journals before mid
    2021 may lack MeanAnomaly)."""
    return bool(el) and bool(_num(el, "SemiMajorAxis")) and _num(el, "MeanAnomaly") is not None


def turn(el):
    """The orbit's orientation as a 3×3 matrix, Rz(Ω)·Rx(i)·Rz(ω), signs as written: what a star's (or a planet
    pair's) children's offsets are turned by."""
    O, i, w = (math.radians(_num(el, k) or 0.0) for k in ("AscendingNode", "OrbitalInclination", "Periapsis"))
    cO, sO, ci, si, cw, sw = math.cos(O), math.sin(O), math.cos(i), math.sin(i), math.cos(w), math.sin(w)
    return ((cO * cw - sO * ci * sw, -cO * sw - sO * ci * cw, sO * si),
            (sO * cw + cO * ci * sw, -sO * sw + cO * ci * cw, -cO * si),
            (si * sw, si * cw, ci))


def _apply(r, v):
    return tuple(r[k][0] * v[0] + r[k][1] * v[1] + r[k][2] * v[2] for k in range(3))


def offset(el, at):
    """Where the body is on its own orbit at `at` (seconds since the epoch), relative to what it orbits: (x, y, z) in
    light seconds, or None without an orbit. el: the Scan's (or ScanBaryCentre's) elements with its "timestamp"."""
    if not has_orbit(el):
        return None
    a, e = _num(el, "SemiMajorAxis"), min(max(_num(el, "Eccentricity") or 0.0, 0.0), 0.999)
    m = math.radians(_num(el, "MeanAnomaly"))
    period = _num(el, "OrbitalPeriod")
    if period and el.get("timestamp"):
        m += 2 * math.pi * (at - ts_seconds(el["timestamp"])) / period
    E = kepler(-m, e)   # the game's orbits run the other way from the textbook's
    xv, yv = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    r = turn(el)
    return tuple((r[k][0] * xv + r[k][1] * yv) / C for k in range(3))


def _first(entry):
    """A Parents entry ({"Star": 0}, {"Null": 3}, {"Planet": 5}) -> (kind, body id)."""
    (kind, bid), = entry.items()
    return kind, bid


def positions(scans, barycentres, at):
    """Every scanned body's position at `at`: ({body_id: (x, y, z) ls}, {the approximate body ids}).
    scans: Scan events (dicts, the journal's own keys); barycentres: ScanBaryCentre events, or {body_id: elements
    with "timestamp"}. A body with no orbit of its own (old journals: no MeanAnomaly) has no position unless it is the
    root."""
    if isinstance(barycentres, dict):
        bary = {int(k): v for k, v in barycentres.items()}
    else:
        bary = {b["BodyID"]: b for b in barycentres or [] if b.get("BodyID") is not None}
    bodies = {s["BodyID"]: s for s in scans or [] if s.get("BodyID") is not None}
    parent, kind = {}, {}
    for bid, s in bodies.items():
        kind[bid] = "Star" if s.get("StarType") else "Planet"
        chain = [_first(p) for p in s.get("Parents") or []]
        if chain:
            parent[bid] = chain[0][1]
        for k, (knd, node) in enumerate(chain):
            kind.setdefault(node, knd)
            if k + 1 < len(chain):
                parent.setdefault(node, chain[k + 1][1])
    children = {}
    for node, par in parent.items():
        children.setdefault(par, []).append(node)

    def stellar(node, seen=()):
        """a barycentre with a star among its members (or a barycentre of stars among them)"""
        if kind.get(node) != "Null" or node in seen:
            return False
        return any(kind.get(c) == "Star" or stellar(c, seen + (node,)) for c in children.get(node, []))

    def planet_pair(node):
        """a barycentre whose scanned members are all planets (the reference checked: bodies only, barycentres aside)"""
        kids = [c for c in children.get(node, []) if c in bodies]
        return bool(kids) and all(kind.get(c) == "Planet" for c in kids)

    def elements(node):
        return bodies.get(node) or bary.get(node)

    memo = {}

    def place(node, depth=0):
        """(x, y, z) and whether approximate"""
        if node in memo:
            return memo[node]
        par = parent.get(node)
        if par is None or depth > 64:   # the root, or a broken chain
            memo[node] = ((0.0, 0.0, 0.0), False)
            return memo[node]
        base, approx = place(par, depth + 1)
        if kind.get(par) == "Null" and stellar(par) and parent.get(par) is not None:
            approx = True   # a barycentre of stars that is not the root: about, across families
        v = offset(elements(node) or {}, at)
        if v is None:   # no orbit known: placed at what it orbits
            v, approx = (0.0, 0.0, 0.0), True
        else:
            pel = elements(par)
            if pel and has_orbit(pel) and (kind.get(par) == "Star" or (kind.get(par) == "Null" and planet_pair(par))):
                v = _apply(turn(pel), v)
        memo[node] = (tuple(base[k] + v[k] for k in range(3)), approx)
        return memo[node]

    pos, approx = {}, set()
    for bid, s in bodies.items():
        if parent.get(bid) is not None and not has_orbit(s):
            continue   # its own place unknown: the order falls back to its distance from the arrival star
        p, a = place(bid)
        pos[bid] = p
        if a:
            approx.add(bid)
    return pos, approx


def distance(p, q):
    """Light seconds between two positions (the page's and the overlay's legDistance do the same sums)."""
    dx, dy, dz = p[0] - q[0], p[1] - q[1], p[2] - q[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)
