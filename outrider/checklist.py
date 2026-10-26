"""The exobiology checklist: every species the rules know, by galactic region, with what you have done with it there.
Pure: the rules (outrider.bio's), your runs and your codex entries come in; the page's table goes out.

For each species and region:
  possible  "yes" when one of its rulesets lets it grow in the region, "parts" when every one that does also needs
            a place within it (near a Guardian site, in a tuber zone, by a nebula, one system), None when the rules
            rule it out ("not here": the rules' prediction, not proof nobody found it there)
  state     your best there: "sold" > "aboard" > "lost" > "logged" (in your codex, no finished run: a first sample, a
            composition scan) > None
  variants  its colours (ExploData's tables: by the star's class or by a material on the body), each with your best
            state there and what gives it ("F, G stars", "polonium"); a species with no colour table (anemones, brain
            trees, tubers...) is its own one variant
"""
import re

STATES = ("sold", "aboard", "lost", "logged")   # best first
RANK = {s: i for i, s in enumerate(STATES)}
# a ruleset key that ties the species to a place inside a region, with the value that means "no such tie"
LOCAL = {"guardian": (None, False, "", [], {}), "tuber": (None, False, "", [], {}), "system": (None, ""),
         "nebula": (None, False, "", "none")}


def best(a, b):
    """The better of two states (None: nothing)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if RANK[a] <= RANK[b] else b


def _local(ruleset):
    return any(k in ruleset and ruleset[k] not in empty for k, empty in LOCAL.items())


def possibility(species, region, region_ok):
    """"yes", "parts" or None for one species in region number `region`. `region_ok(ruleset, region)`: whether a
    ruleset lets it grow there (outrider.bio.ruleset_region_ok). A species with no rules at all is "yes": unknown is
    not "not here"."""
    if not species.get("rulesets"):
        return "yes"
    allowing = [r for r in species["rulesets"] if region_ok(r, region)]
    if not allowing:
        return None
    return "parts" if all(_local(r) for r in allowing) else "yes"


def colours(species):
    """[(colour, [conditions])] for a species, in the colour's first appearance in its table; [] when it has none."""
    c = species.get("colors") or {}
    table = c.get("star") or c.get("element") or {}
    out = {}
    for cond, colour in table.items():
        if isinstance(colour, str) and colour:
            out.setdefault(colour, []).append(cond)
    return list(out.items())


def colour_of(variant, species_name):
    """The colour in a journal or codex variant name ("Bacterium Aurasus - Teal" -> "teal"), lower-cased; None when
    it has none (a run from before the 2023 patch, or a species with no colours)."""
    v = (variant or "").strip()
    if " - " not in v:
        return None
    head, colour = v.rsplit(" - ", 1)
    return colour.strip().lower() or None if head.strip().lower() == (species_name or "").lower() else None


def variant_colour(species, variant_id=None, name=None):
    """A sample's colour as its species' table names it (English, whatever the game's language): from its variant's
    codex code ("$Codex_Ent_Tussocks_01_F_Name;": the star class F; "..._Bacterial_10_Polonium_Name;": polonium), else
    the colour at the end of its name ("Bacterium Bullaris - Yellow") when the table has it. "" for a species with no
    colours (one picture for all), None when it cannot be told."""
    known = colours(species)
    if not known:
        return ""
    c = species.get("colors") or {}
    m = re.match(r"^\$Codex_Ent_[A-Za-z]+_\d+_(\w+)_Name;$", str(variant_id or ""))
    if m:
        key = m.group(1).lower()
        for table in (c.get("star") or {}, c.get("element") or {}):
            hit = next((v for k, v in table.items() if str(k).lower() == key and isinstance(v, str) and v), None)
            if hit:
                return hit
    said = colour_of(name, species.get("name"))
    return next((colour for colour, _ in known if colour.lower() == said), None) if said else None


def merge_species(species_list):
    """The rules' species, one per game species id ($Codex_Ent_..._Name;), in their order, and {name lower-cased: id}
    for every name met (a duplicate under a misspelled name is merged into the one with rules: BioScan lists
    $Codex_Ent_Stratum_04_Name; as "Stratum Aranaemus" with none and "Stratum Araneamus" with its rules)."""
    by_id, names = {}, {}
    for sp in species_list:
        sid = sp.get("id") or sp["name"]
        names[sp["name"].lower()] = sid
        # the game's (and Canonn's) name when it is the rules' in the plural: the codex logs "Bark Mounds", the rules
        # say "Bark Mound" (their genus has the plural; the Fable review of 2026-10-10, #2)
        genus, name = (sp.get("genus") or "").lower(), sp["name"].lower()
        if genus and genus != name and genus.rstrip("s") == name:
            names.setdefault(genus, sid)
        have = by_id.get(sid)
        if have is None or (not have.get("rulesets") and sp.get("rulesets")):
            by_id[sid] = sp
    return list(by_id.values()), names


def _records(species_list, names, runs, codex):
    """(species key, colour or None, region, state, is a run) for each of your runs and codex entries the rules know;
    a run under way counts as logged."""
    ids = {s.get("id") for s in species_list}
    for run in runs:
        name = run.get("species") or ""
        key = run.get("species_id") if run.get("species_id") in ids else names.get(name.lower())
        state = {"in progress": "logged"}.get(run.get("state"), run.get("state"))
        if state in RANK and key is not None:
            yield key, colour_of(run.get("variant"), name), run.get("region"), state, True
    for entry in codex:
        full = (entry.get("name") or "").strip()
        name = full.rsplit(" - ", 1)[0] if " - " in full else full
        key = names.get(name.lower())
        if key is not None:
            yield key, colour_of(full, name), entry.get("region"), "logged", False


def _share(found, total):
    """A species' completion: the share of its colours found (a species with no colour table: found or not)."""
    return found / total if total else 0.0


def completion(species_list, region_ok, runs, codex, region_count):
    """{region number: % complete (0-100, 2 places) or None (nothing can grow there), "all": % over every region}.
    A region's completion is the average, over the species that can grow there, of the share of each one's colours you
    have found there (any state: sold, aboard, lost or logged), so half of every species is 50% with none finished."""
    species_list, names = merge_species(species_list)
    col_found, sp_found = {}, {}   # region (None: anywhere) -> {(key, colour)} / {key}
    for key, colour, r, _, _ in _records(species_list, names, runs, codex):
        for where_ in {r, None}:
            sp_found.setdefault(where_, set()).add(key)
            if colour:
                col_found.setdefault(where_, set()).add((key, colour))
    cols = {(s.get("id") or s["name"]): [c.lower() for c, _ in colours(s)] for s in species_list}

    def share(key, r):
        cs = cols[key]
        if not cs:
            return 1.0 if key in sp_found.get(r, ()) else 0.0
        return _share(sum((key, c) in col_found.get(r, ()) for c in cs), len(cs))
    out, anywhere = {}, set()
    for r in range(1, region_count + 1):
        keys = [s.get("id") or s["name"] for s in species_list if possibility(s, r, region_ok)]
        anywhere.update(keys)
        out[r] = round(100 * sum(share(k, r) for k in keys) / len(keys), 2) if keys else None
    out["all"] = round(100 * sum(share(k, None) for k in anywhere) / len(anywhere), 2) if anywhere else None
    return out


def table(species_list, region, region_ok, runs, codex, region_count, value_of=None):
    """The checklist for region number `region` (None: All regions).

    species_list  the rules' species ({name, genus, value, rulesets, colors})
    region_ok     (ruleset, region) -> bool
    runs          your runs: [{species_id ($Codex_Ent_..._Name;), species (name), variant (name or None), region
                  (number or None), state}], state one of "sold", "aboard", "lost", "in progress"
    codex         your codex entries: [{name ("Bacterium Aurasus - Teal" or "Luteolum Anemone"), region (number)}]
    region_count  the number of regions (their numbers run 1..region_count)
    value_of      name -> credits from the price list (outrider.bio.species_value), else the rules' value

    -> {"genera": [{genus, species: [row]}], "summary": {...}}; a row: {id, name, short, value, possible, state,
    elsewhere (your best in other regions, when none here), runs, variants: {total, found, list: [{colour, where, state}]}}."""
    regions = range(1, region_count + 1) if region is None else (region,)
    here = lambda r: region is None or r == region   # noqa: E731

    species_list, names = merge_species(species_list)
    got, got_colour, n_runs, anywhere = {}, {}, {}, {}
    carried = set()   # species with samples aboard here, whatever else you did with them (a colour sold before)

    def note(key, colour, r, state):
        if key is None:
            return
        anywhere[key] = best(anywhere.get(key), state)   # for "found elsewhere" beside a region's row
        if not here(r):
            return
        got[key] = best(got.get(key), state)
        if state == "aboard":
            carried.add(key)
        if colour:
            got_colour[(key, colour)] = best(got_colour.get((key, colour)), state)

    for key, colour, r, state, is_run in _records(species_list, names, runs, codex):
        note(key, colour, r, state)
        if is_run and here(r):
            n_runs[key] = n_runs.get(key, 0) + 1

    genera, totals = {}, {"possible": 0, "found": 0, "sold": 0, "aboard": 0, "lost": 0, "logged": 0,
                          "colours": 0, "colours_found": 0, "elsewhere": 0}
    done = 0.0   # the sum of each possible species' share of its colours found (completion's numerator)
    for sp in species_list:
        key = sp.get("id") or sp["name"]
        poss = None
        for r in regions:
            p = possibility(sp, r, region_ok)
            poss = "yes" if "yes" in (poss, p) else (p or poss)
            if poss == "yes":
                break
        cols = colours(sp)
        state = got.get(key)
        if cols:
            stars = bool((sp.get("colors") or {}).get("star"))   # by the star's class, else by a material on the body
            vlist = [{"colour": c, "where": ", ".join(w) + (" stars" if stars else ""), "state": got_colour.get((key, c.lower()))}
                     for c, w in cols]
        else:   # its own one variant: found when the species is
            vlist = [{"colour": None, "where": None, "state": state}]
        found = sum(1 for v in vlist if v["state"])
        # the price list's figure when it has one (value_of: outrider.bio.species_value), as My Samples and the
        # predictions use: the rules carry BioScan's, a placeholder for some (Concha Biconcavis 16,777,215)
        value = (value_of(sp["name"]) if value_of else None) or sp.get("value")
        row = {"id": key, "name": sp["name"], "short": short_name(sp), "value": value, "possible": poss, "state": state,
               "elsewhere": anywhere.get(key) if region is not None and not state else None,
               "runs": n_runs.get(key, 0), "variants": {"total": len(vlist), "found": found, "list": vlist}}
        genera.setdefault(sp.get("genus") or "?", []).append(row)
        totals["elsewhere"] += 1 if row["elsewhere"] and poss else 0
        if poss:
            done += _share(found, len(vlist))
        if poss or state:
            totals["possible"] += 1 if poss else 0
            totals["colours"] += len(vlist) if poss else 0
            totals["colours_found"] += found
            if state:
                totals["found"] += 1
                totals[state] += 1 if state != "aboard" else 0
            # aboard: every species you carry unsold samples of, not only those with nothing better (a new colour of
            # a species sold before is aboard too: the author, 2026-10-11); sold, lost and logged stay best-state counts
            totals["aboard"] += 1 if key in carried else 0
    totals["completion"] = round(100 * done / totals["possible"], 2) if totals["possible"] else None
    out = [{"genus": g, "species": sorted(rows, key=lambda x: x["short"])} for g, rows in sorted(genera.items())]
    return {"genera": out, "summary": totals}


def where(species, region_ok, region_count):
    """{region number: "yes" | "parts"} for the regions a species can grow in (the species panel's map)."""
    out = {}
    for r in range(1, region_count + 1):
        p = possibility(species, r, region_ok)
        if p:
            out[r] = p
    return out


def short_name(species):
    """A species' name inside its genus box: "Arcus" for Aleoida Arcus; a species named after its genus with a
    prefix ("Luteolum Anemone", "Roseum Brain Tree") keeps the prefix; one alone in its genus keeps its name."""
    name, genus = species["name"], species.get("genus") or ""
    if genus and name.lower().startswith(genus.lower() + " "):
        return name[len(genus) + 1:]
    if genus and name.lower().endswith(" " + genus.lower()):
        return name[: -len(genus) - 1]
    return name


# ---- the geology checklist: the codex's Geology and Anomalies entries (resources/geo_codex.json, from Canonn) ----
# Nothing to sell and no colours: an entry is logged in your codex for a region, or not. "Possible" is "reported":
# someone has logged it in that region (Canonn's sites); one not reported there is not ruled out, only not seen yet.

def geo_short(entry):
    """An entry's name inside its group's box: "Sulphur Dioxide" (Fumarole), "Caeruleum" (Lagrange Cloud), "K01"
    (K-Type Anomaly)."""
    name, group = entry["name"], entry.get("group") or ""
    if name.endswith("-Type Anomaly"):
        return name[: -len("-Type Anomaly")]
    for tail in (" Lagrange " + group, " " + group):
        if group and name.endswith(tail) and len(name) > len(tail):
            return name[: -len(tail)]
    return name


def geo_table(entries, region, codex, region_count):
    """The geology checklist for region number `region` (None: All regions), in the shape table() gives: boxes by group
    (Fumarole, Geyser, ... Lagrange Cloud, K-Type Anomaly), rows {id, name, short, kind, possible ("yes" when reported
    there), sites (reported there), state ("logged" or None), elsewhere, runs (your entries there), variants (one)}.
    codex: your entries [{entry_id, region}]. Completion: logged / reported, over the reported entries."""
    regions = range(1, region_count + 1) if region is None else (region,)
    mine, anywhere = {}, set()
    for c in codex:
        eid = c.get("entry_id")
        anywhere.add(eid)
        if region is None or c.get("region") == region:
            mine[eid] = mine.get(eid, 0) + 1
    groups, totals = {}, {"possible": 0, "found": 0, "logged": 0, "sold": 0, "aboard": 0, "lost": 0, "elsewhere": 0,
                          "colours": 0, "colours_found": 0}
    for e in entries:
        sites = sum((e.get("regions") or {}).get(str(r), 0) for r in regions)
        state = "logged" if e["id"] in mine else None
        row = {"id": str(e["id"]), "name": e["name"], "short": geo_short(e), "kind": e.get("kind"), "value": None,
               "possible": "yes" if sites else None, "sites": sites, "state": state,
               "elsewhere": "logged" if region is not None and not state and e["id"] in anywhere else None,
               "runs": mine.get(e["id"], 0),
               "variants": {"total": 1, "found": 1 if state else 0, "list": [{"colour": None, "where": None, "state": state}]}}
        groups.setdefault(e.get("group") or e.get("kind") or "?", []).append(row)
        if sites:
            totals["possible"] += 1
            totals["colours"] += 1
            totals["elsewhere"] += 1 if row["elsewhere"] else 0
        if state:
            totals["found"] += 1
            totals["logged"] += 1
            totals["colours_found"] += 1 if sites else 0
    totals["completion"] = round(100 * totals["colours_found"] / totals["possible"], 2) if totals["possible"] else None
    kind_order = {"Geology": 0, "Cloud": 1, "Anomaly": 2}
    out = [{"genus": g, "kind": rows[0]["kind"], "species": sorted(rows, key=lambda x: x["short"])}
           for g, rows in sorted(groups.items(), key=lambda kv: (kind_order.get(kv[1][0]["kind"], 9), kv[0]))]
    return {"genera": out, "summary": totals}


def geo_completion(entries, codex, region_count):
    """{region number: % of the entries reported there that you have logged there, "all": over every region}."""
    logged = {}
    for c in codex:
        logged.setdefault(c.get("region"), set()).add(c.get("entry_id"))
    anywhere = set().union(*logged.values()) if logged else set()
    out = {}
    for r in range(1, region_count + 1):
        known = [e["id"] for e in entries if (e.get("regions") or {}).get(str(r))]
        out[r] = round(100 * sum(1 for i in known if i in logged.get(r, ())) / len(known), 2) if known else None
    known = [e["id"] for e in entries if e.get("regions")]
    out["all"] = round(100 * sum(1 for i in known if i in anywhere) / len(known), 2) if known else None
    return out
