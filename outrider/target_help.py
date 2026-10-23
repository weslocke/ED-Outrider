"""The auto-target steps' cheatsheet (GET /help/autotarget, linked from Settings -> Auto-target): what a step may say,
built from outrider.target itself (the verbs and their limits, the controls, the fixed keys, the defaults) and the
key names outrider.winkeys knows (the ones that work on Windows as well as Linux), so it cannot drift from what the
steps accept. With the controls preset read (the game PC), each control shows the key it is bound to.

Pure: cheatsheet_html(binds) -> a whole page. binds: Targeter.bindings()'s {control: (evdev names or None, why)},
or None where nothing can be pressed (a server, Docker): the "your key" column is left out then.
"""
import html

from outrider import honk, target, winkeys

# the keys by name, grouped for reading (every name in winkeys' table is in one group: a test checks it)
KEY_GROUPS = (
    ("Arrows and moving", ("UP", "DOWN", "LEFT", "RIGHT", "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE")),
    ("Enter, space and the like", ("ENTER", "KPENTER", "SPACE", "TAB", "BACKSPACE", "ESC")),
    ("Modifiers", ("LEFTALT", "RIGHTALT", "LEFTCTRL", "RIGHTCTRL", "LEFTSHIFT", "RIGHTSHIFT", "LEFTMETA", "RIGHTMETA",
                   "COMPOSE")),
    ("Letters", tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
    ("Digits", tuple("1234567890")),
    ("Function keys", tuple(f"F{n}" for n in range(1, 25))),
    ("Numpad", ("KP0", "KP1", "KP2", "KP3", "KP4", "KP5", "KP6", "KP7", "KP8", "KP9", "KPDOT", "KPPLUS", "KPMINUS",
                "KPASTERISK", "KPSLASH", "KPEQUAL", "KPCOMMA", "NUMLOCK")),
    ("Punctuation", ("MINUS", "EQUAL", "LEFTBRACE", "RIGHTBRACE", "SEMICOLON", "APOSTROPHE", "GRAVE", "BACKSLASH",
                     "COMMA", "DOT", "SLASH", "102ND")),
    ("Other", ("CAPSLOCK", "SCROLLLOCK", "PAUSE", "SYSRQ", "MUTE", "VOLUMEDOWN", "VOLUMEUP", "PLAYPAUSE", "STOPCD",
               "PREVIOUSSONG", "NEXTSONG", "CALC", "HOMEPAGE")),
)
# the words parse_combo takes for a modifier
ALIASES = (("alt", "KEY_LEFTALT"), ("ctrl", "KEY_LEFTCTRL"), ("control", "KEY_LEFTCTRL"), ("shift", "KEY_LEFTSHIFT"))
# where each editable part starts, and what that means for its keys
BOXES = (
    ("search", 2, "into the search field",
     "The galaxy map has just opened, sometimes on the side panel it last showed. These steps put the cursor in "
     "\"Search the Galaxy\"."),
    ("submit", 4, "submit the search",
     "The cursor is in the search box with the name in it. <b>A control bound to a letter key types that letter here</b> "
     "(UI_Down on S adds an S to the name), so use keys that type nothing: the arrow keys by name, Enter. The results "
     "list a moment after the name goes in: wait first."),
    ("plot", 5, "plot the route",
     "The map has flown to the system, but the focus is still in the search panel: a short camera move gives it back "
     "to the map, then UI_Select held plots the route."),
)

CSS = """
:root { color-scheme: dark light; --bg: #12100e; --fg: #e9e2d8; --muted: #a49a8c; --line: #3a332c; --accent: #ff8c1a;
  --code: #1f1b17; --warn: #e3b341; }
@media (prefers-color-scheme: light) { :root { --bg: #fbf8f4; --fg: #221c16; --muted: #6b6157; --line: #ddd3c7;
  --accent: #b55a00; --code: #f0e9e0; --warn: #8a6100; } }
body { background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; padding: 16px;
  max-width: 980px; }
h1 { font-size: 1.5em; margin: .2em 0 .1em; } h2 { font-size: 1.15em; margin: 1.6em 0 .4em; color: var(--accent); }
p, li { max-width: 72ch; } .muted { color: var(--muted); } .warn { color: var(--warn); }
code, kbd { background: var(--code); border-radius: 4px; padding: 0 .3em; font: .92em ui-monospace, monospace; }
pre { background: var(--code); border-radius: 6px; padding: .5em .8em; margin: .3em 0; font: .92em/1.45 ui-monospace, monospace; }
table { border-collapse: collapse; width: 100%; } th, td { text-align: left; vertical-align: top; padding: 4px 8px;
  border-bottom: 1px solid var(--line); } th { color: var(--muted); font-weight: 600; }
.keys { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 2px 12px; margin: 0; padding: 0;
  list-style: none; } .keys.compact { display: flex; flex-wrap: wrap; gap: 4px 10px; }   /* names that need no label */
.boxes { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.box { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; } .box h3 { margin: 0 0 .3em; font-size: 1em; }
"""


def _e(text):
    return html.escape(str(text), quote=True)


def your_key(binds, name):
    """The key a control is bound to, in words ("Space", "Left Alt + Right Alt + T"), or why there is none."""
    keys, why = (binds or {}).get(name, (None, "not read"))
    return " + ".join(honk.key_label(k) for k in keys) if keys else None, why


# the character a punctuation key types (US layout, unshifted): the typing's own keymap, read backwards
CHARS = {k[4:]: c for c, (k, shift) in target.US_KEYMAP.items() if not shift and not c.isalnum() and c != " "}


def key_names():
    """Every key name the steps can use on both systems: winkeys' table, without its KEY_ prefix."""
    return [n[4:] for n in winkeys.ecodes.ecodes]


def cheatsheet_html(binds=None):
    defaults = {"search": target.DEFAULT_SEARCH, "submit": target.DEFAULT_SUBMIT, "plot": target.DEFAULT_PLOT}
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
           "<title>Auto-target steps: cheatsheet</title><style>", CSS, "</style></head><body>",
           "<h1>Auto-target steps: cheatsheet</h1>",
           "<p class=\"muted\">What the three boxes of ⚙ Settings → Auto-target may say. Every 🎯 button, Target next, the "
           "co-pilot button and the Highway's auto-target press these steps in the galaxy map. Opening the map, entering "
           "the name, closing the map and checking the target are always done by Outrider.</p>",
           "<h2>A step</h2><p>One per line, words in any case:</p><table><tr><th>Step</th><th>Does</th></tr>",
           "<tr><td><code>press &lt;key&gt;</code></td><td>taps the key</td></tr>",
           "<tr><td><code>hold &lt;key&gt; &lt;seconds&gt;</code></td><td>holds it down, more than 0 and up to 10 s "
           "(<code>hold UI_Select 1</code>)</td></tr>",
           "<tr><td><code>wait &lt;seconds&gt;</code></td><td>waits, 0 to 30 s (<code>wait 1.5</code>)</td></tr></table>",
           "<p>After each <code>press</code> and <code>hold</code>, Outrider pauses for <b>pause between keys</b> (0.25 s "
           "to start): the galaxy map can miss a key pressed straight after another, so no <code>wait</code> is needed "
           "between keys. The search wait is at least 5 s for a system over 300 ly away.</p>"
           "<p>A <code>&lt;key&gt;</code> is a game control below (pressed with the keyboard key it is bound to in your "
           "controls), <code>Enter</code> or <code>Paste</code>, or keyboard keys by name.</p>",
           "<h2>The three boxes</h2><div class=\"boxes\">"]
    for key, phase, title, where in BOXES:
        out.append(f"<div class=\"box\"><h3>{phase} · {_e(title)}</h3><p>{where}</p><div class=\"muted\">Outrider's own "
                   f"(↺ default):</div><pre>{_e(chr(10).join(defaults[key]))}</pre></div>")
    out.append("</div>")
    out.append("<h2>Game controls</h2><p>Named as in the game's controls file, in any case (<code>UI_SELECT</code> is "
               "<code>UI_Select</code>). Outrider presses the <b>keyboard</b> key a control is bound to (a HOTAS button "
               "cannot be pressed for you): a control with no keyboard binding needs one, in the game or in "
               "<code>[highway] autotarget_keys</code>.</p>")
    out.append("<table><tr><th>Name</th><th>In the galaxy map</th>" + ("<th>Your key</th>" if binds is not None else "") +
               "</tr>")
    for name in target.ACTIONS:
        cell = ""
        if binds is not None:
            label, why = your_key(binds, name)
            cell = f"<td>{_e(label)}</td>" if label else f"<td class=\"warn\">{_e(why or 'no keyboard binding')}</td>"
        out.append(f"<tr><td><code>{_e(name)}</code></td><td>{_e(target.KEY_HELP[name])}</td>{cell}</tr>")
    for name, keys in target.FIXED_KEYS.items():
        cell = f"<td>{_e(' + '.join(honk.key_label(k) for k in keys))}</td>" if binds is not None else ""
        out.append(f"<tr><td><code>{_e(name)}</code></td><td>{_e(target.KEY_HELP[name])}</td>{cell}</tr>")
    out.append("</table>")
    out.append("<h2>Keyboard keys by name</h2><ul>"
               "<li>Any name below, in any case, with or without <code>KEY_</code>: <code>press down</code>, "
               "<code>press KEY_DOWN</code> and <code>press Down</code> are the down arrow.</li>"
               "<li>Keys pressed together are joined with <code>+</code>: <code>press alt+t</code>, "
               "<code>press KEY_LEFTALT+KEY_RIGHTALT+KEY_T</code>.</li>"
               "<li>Short words: " + ", ".join(f"<code>{a}</code> is {_e(honk.key_label(k))}" for a, k in ALIASES) + ".</li>"
               "<li>A control's name always means the control: name the key instead when you want the key itself.</li>"
               "<li>A control can be given its own key, whatever the game's controls say: <code>[highway] autotarget_keys = "
               "{ UI_Select = \"KEY_SPACE\", Enter = \"KEY_KPENTER\" }</code> (Settings → Server).</li>"
               "<li>Linux takes any key name the system knows (<code>evtest</code> lists them); these work on Windows too.</li></ul>")
    names = set(key_names())
    for group, keys in KEY_GROUPS:
        items, plain = [], True
        for k in keys:
            if k not in names:
                continue
            label = CHARS.get(k) or honk.key_label("KEY_" + k)
            same = label.replace(" ", "").upper() == k
            plain = plain and same
            items.append(f"<li><code>{_e(k)}</code>" + ("" if same else f" <span class=\"muted\">{_e(label)}</span>") + "</li>")
        out.append(f"<h3>{_e(group)}</h3><ul class=\"keys{' compact' if plain else ''}\">{''.join(items)}</ul>")
    out.append("<h2>Trying them</h2><ul>"
               "<li><b>▶ test now</b> in Settings → Auto-target runs the whole sequence once, against the system typed "
               "beside it (a short name such as <code>Sol</code> lists several systems: a good test of the submit steps) "
               "or the nearest one a jump away. A far system gets a route plotted: clear it in game afterwards.</li>"
               "<li>Each step's line in Outrider's log (Settings → Server → Show log) names the keys it pressed.</li>"
               "<li><code>[highway] autotarget_dry_run = true</code> goes through the steps without pressing anything.</li>"
               "</ul></body></html>")
    return "".join(out)


def ungrouped():
    """Key names winkeys knows that no group lists (a test keeps it empty)."""
    return sorted(set(key_names()) - {k for _, keys in KEY_GROUPS for k in keys})
