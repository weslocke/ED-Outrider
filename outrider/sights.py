"""Catalogued sights (explorer ideas, item 9, 2026-10-25): EDAstro's Galactic Encyclopedia Catalog (GEC), the
community's curated list of places worth seeing (sights and scenery, planetary and stellar features, green gas giants,
nebulae...). Fetched at runtime by the server, once a day and only when changed (never shipped: CC BY-NC-SA 3.0,
credited and linked where shown). Pure: the server hands in the answer and your position.

    compact(data)   -> [{id, id64, name, type, summary, url, system, x, y, z}]
    nearest(entries, pos, within) -> the nearest entry within `within` ly of pos, with its distance, or None
"""
import math

URL = "https://edastro.com/gec/json/all"
PAGE = "https://edastro.com/gec/"
SUMMARY_MAX = 300   # the hover's text: their summaries run to 200 characters (2026-10-25)


def compact(data):
    """GEC's JSON (a list of entries) cut to what the page shows; entries without an id64 or coordinates left out.
    Raises ValueError for an answer of another shape (an error object, a maintenance page)."""
    if not isinstance(data, list):
        raise ValueError("it answered in an unexpected shape")
    out = []
    for e in data:
        if not isinstance(e, dict):
            continue
        xyz = e.get("coordinates")
        if not isinstance(e.get("id64"), int) or not (isinstance(xyz, list) and len(xyz) == 3
                                                     and all(isinstance(v, (int, float)) for v in xyz)):
            continue
        out.append({"id": e.get("id"), "id64": str(e["id64"]), "name": str(e.get("name") or "").strip() or None,
                    "type": str(e.get("type") or "").strip() or None,
                    "summary": (str(e.get("summary") or "").strip()[:SUMMARY_MAX]) or None,
                    "url": e.get("poiUrl") if isinstance(e.get("poiUrl"), str) and e["poiUrl"].startswith("https://") else None,
                    "system": str(e.get("galMapSearch") or "").strip() or None,
                    "x": float(xyz[0]), "y": float(xyz[1]), "z": float(xyz[2])})
    return out


def by_system(entries):
    """{id64: [entries]}: a system can hold several sights."""
    out = {}
    for e in entries or []:
        out.setdefault(e["id64"], []).append(e)
    return out


def nearest(entries, pos, within):
    """The entry nearest `pos` ({x, y, z}) within `within` ly, as a copy with `distance`; None for none, no position
    or a range of 0 (the feature off)."""
    if not within or not pos or pos.get("x") is None:
        return None
    best = None
    for e in entries or []:
        d = math.dist((pos["x"], pos["y"], pos["z"]), (e["x"], e["y"], e["z"]))
        if d <= within and (best is None or d < best[0]):
            best = (d, e)
    return dict(best[1], distance=round(best[0], 1)) if best else None
