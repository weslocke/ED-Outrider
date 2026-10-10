"""The config file from the page: every key with its help, and changing keys in place (the Settings dialog's Server
settings). Pure: ed_outrider.py serves it (GET/POST /api/config) and checks a change with settings_from.

The keys and their help come from config_text() (what --write-config writes), so every key the server knows is listed
without a second list to keep in step. A change edits the file itself, key by key: its comments, order and any keys
this version does not know stay as they were; a key the file lacks goes at the end of its section.
"""
import json
import math
import re

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib

SECTION_TITLES = {"journals": "Journal folders", "server": "Server: network, password, paths, backups",
                  "defaults": "Defaults for new browsers", "spansh": "Spansh", "speech": "Speech on this PC",
                  "autohonk": "Auto honk", "copilot": "Co-pilot button", "highway": "Neutron Highway and auto-target",
                  "assistant": "Voice: the AI layer", "mcp": "MCP bridge (AI clients)", "overlay": "In-game overlay"}
HIDDEN_SECTIONS = {"eddn", "edsm"}   # written by their own page sections (Settings -> Uploads), not the Server list
SECRETS = {("server", "password"), ("assistant", "api_key"), ("mcp", "password"), ("overlay", "password")}   # never sent to the page, only "set" or not
# keys with a fixed set of values, shown as a choice (ed_outrider.py adds [speech] server_player's, from outrider.tts)
CHOICES = {("server", "game_pc"): ("auto", "true", "false"), ("highway", "autotarget_entry"): ("type", "paste"),
           ("overlay", "theme"): ("default", "lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance",
                                  "dark"),
           ("overlay", "text_size"): ("small", "normal", "large")}
HEADER = re.compile(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]")
KEYLINE = re.compile(r"^(\s*)(#\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def split_value(rest):
    """'"a # b" ]   # help' -> ('"a # b" ]', '# help'): a value and its trailing comment (a # inside quotes or
    brackets is the value's). Also the bracket depth left open at the end (a list going on to the next lines)."""
    depth, quote, i = 0, None, 0
    while i < len(rest):
        c = rest[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "#" and depth <= 0:
            return rest[:i].rstrip(), rest[i:], depth
        i += 1
    return rest.rstrip(), "", depth


def basic_string(s):
    """A TOML basic string: JSON's escapes are TOML's, and DEL, which JSON leaves alone, escaped too."""
    return json.dumps(s, ensure_ascii=False).replace("\x7f", "\\u007f")


def kind_of(value):
    """The editor a value needs: bool, int, float, text, lines (a list of text), numbers (a list of numbers), table."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "numbers" if value and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value) else "lines"
    if isinstance(value, dict):
        return "table"
    return "text"


def entries(text, choices=None):
    """[{section, title, keys: [{key, value, kind, help, set}]}] from a config text (config_text's): set is False for a
    commented-out key (its default shown). A key in `choices` (default CHOICES) is kind "choices", with its list."""
    choices = CHOICES if choices is None else choices
    out, cur = [], None
    for line in text.splitlines():
        h = HEADER.match(line)
        if h and not line.lstrip().startswith("#"):
            cur = {"section": h.group(1), "title": SECTION_TITLES.get(h.group(1), h.group(1)), "keys": []}
            out.append(cur)
            continue
        m = KEYLINE.match(line)
        if not m or cur is None:
            continue
        value_text, comment, _ = split_value(m.group(4))
        try:
            value = tomllib.loads("v = " + value_text)["v"]
        except (tomllib.TOMLDecodeError, ValueError):
            continue   # a comment line that only looks like a key
        if any(k["key"] == m.group(3) for k in cur["keys"]):
            continue
        k = {"key": m.group(3), "value": value, "kind": kind_of(value), "set": not m.group(2), "help": comment.lstrip("#").strip()}
        if (cur["section"], m.group(3)) in choices:
            k.update(kind="choices", choices=list(choices[cur["section"], m.group(3)]),
                     value=("true" if value else "false") if isinstance(value, bool) else str(value))
        cur["keys"].append(k)
    return out


def number(v):
    """A TOML number for v by its type: an int as written, a float exactly (repr: the shortest form that reads back as
    the same value) and always as a float ("2.0", never "2"), so a decimal setting reads back as a decimal."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    return str(v) if isinstance(v, int) else repr(float(v))


def literal(v):
    """A TOML literal for a value from the page."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return number(v)
    if isinstance(v, str):
        return basic_string(v)
    if isinstance(v, list):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    if isinstance(v, dict):
        key = lambda k: k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k)   # noqa: E731
        return "{ " + ", ".join(f"{key(k)} = {literal(x)}" for k, x in v.items()) + " }" if v else "{}"
    raise ValueError(f"cannot write {type(v).__name__}")


def value_end(lines, i, depth, end):
    """The last line of a value starting on line i with `depth` brackets left open (a list over several lines)."""
    while depth > 0 and i + 1 < end:
        i += 1
        depth += split_value(lines[i])[2]
    return i


def set_key(text, section, key, value):
    """`text` with section.key set to `value`, in place: an active line's value replaced (its comment kept), else a
    commented-out one switched on, else a new line at the end of the section, else a new section at the end. A
    [section.key] table of its own (written by hand) is dropped for the inline form, so the table is not declared twice."""
    lines = text.split("\n")
    sub = next((i for i, ln in enumerate(lines) if (h := HEADER.match(ln)) and not ln.lstrip().startswith("#")
                and h.group(1) == f"{section}.{key}"), None)
    if sub is not None:
        after = next((i for i in range(sub + 1, len(lines)) if HEADER.match(lines[i]) and not lines[i].lstrip().startswith("#")), len(lines))
        lines = lines[:sub] + lines[after:]
    start = next((i for i, ln in enumerate(lines) if (h := HEADER.match(ln)) and not ln.lstrip().startswith("#")
                  and h.group(1) == section), None)
    if start is None:
        return "\n".join(lines).rstrip("\n") + f"\n\n[{section}]\n{key} = {literal(value)}\n"
    end = next((i for i in range(start + 1, len(lines)) if HEADER.match(lines[i]) and not lines[i].lstrip().startswith("#")), len(lines))
    commented, last_key, i = None, None, start
    while i + 1 < end:
        i += 1
        m = KEYLINE.match(lines[i])
        if not m:
            continue
        value_text, comment, depth = split_value(m.group(4))
        if m.group(2):   # "# key = default   # help": switched on, the help kept
            if m.group(3) == key:
                commented = commented if commented is not None else (i, comment)
            continue
        j = value_end(lines, i, depth, end)   # a list spread over several lines: up to its closing bracket
        if m.group(3) != key:
            last_key = i = j   # a new key goes after the last one's whole value
            continue
        if j > i:
            comment = split_value(lines[j])[1]
        new = f"{m.group(1)}{key} = {literal(value)}" + (f"   {comment}" if comment else "")
        return "\n".join(lines[:i] + [new] + lines[j + 1:])
    if commented is not None:
        i, comment = commented
        lines[i] = f"{key} = {literal(value)}" + (f"   {comment}" if comment else "")
        return "\n".join(lines)
    at = (last_key if last_key is not None else start) + 1
    return "\n".join(lines[:at] + [f"{key} = {literal(value)}"] + lines[at:])


def coerce(kind, value, choices=()):
    """A value from the page as the key's kind wants it, or ValueError with words for a person. choices: the
    "choices" kind's values."""
    if kind == "choices":
        if isinstance(value, str) and value.strip().lower() in choices:
            return value.strip().lower()
        raise ValueError("must be one of " + ", ".join(choices))
    if kind == "bool":
        if isinstance(value, bool):
            return value
        raise ValueError("must be on or off")
    if kind in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)) or str(value).strip() == "":
            raise ValueError("must be a number")
        try:
            x = float(value)
        except ValueError:
            raise ValueError("must be a number") from None
        if x != x or x in (float("inf"), float("-inf")):
            raise ValueError("must be a number")
        if kind == "int":
            if x != int(x):
                raise ValueError("must be a whole number")
            return int(x)
        return x
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError("must be text")
        return value
    if kind == "lines":
        items = value.splitlines() if isinstance(value, str) else value
        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            raise ValueError("must be text, one per line")
        return [x.strip() for x in items if x.strip()]
    if kind == "numbers":
        items = re.split(r"[\s,]+", value.strip()) if isinstance(value, str) else value
        try:
            nums = [float(x) for x in items if str(x).strip()]
        except (TypeError, ValueError):
            raise ValueError("must be numbers, separated by commas") from None
        if not all(math.isfinite(x) for x in nums):   # inf, 1e999: int() of it raised OverflowError (a 500)
            raise ValueError("must be numbers, separated by commas")
        return [int(x) if x == int(x) else x for x in nums]
    if kind == "table":
        if isinstance(value, str):
            try:
                value = json.loads(value) if value.strip() else {}
            except ValueError:
                raise ValueError('must be a JSON object, e.g. {"Enter": "KEY_KPENTER"}') from None
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise ValueError("must be names and text")
        return value
    raise ValueError(f"unknown kind {kind}")
