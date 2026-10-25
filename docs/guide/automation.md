[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Automation

## 🎯 Auto honk

Outrider can fire the Discovery Scanner for you, on Linux (and on Windows as an experiment). It runs on the game PC
only (never in Docker). On arriving by hyperspace it waits a moment,
holds Primary Fire, and says how it went ("System Scan Completed, 12 Bodies discovered"). It is off until
you tick it in ⚙ Settings.

- It waits while a map or panel is open, and while the HUD is in combat mode (switch to analysis mode). It never
  presses while the game is at its menu or closed (the key would go to whatever window has focus): it waits, then
  gives up.
- It learns which fire groups the scanner is in, per ship, and waits on a group where it has missed twice in a
  row (one miss can be an alt-tab, which sends the key to another window).
  The dialog's **forget** clears that after you move the scanner.
- It skips systems you've already honked, Apex shuttles and multicrew.

Setting it up:

- **Is it ready?** ⚙ Settings → Auto honk says it at the top, before you tick anything: "Ready: evdev ✓ ·
  /dev/uinput ✓ · /dev/uinput writable ✓ · Primary Fire: Left Alt + K ✓", or what is missing with the fix and its
  commands to copy (load the `uinput` module, a udev rule that lets you write `/dev/uinput`, a keyboard binding for
  Primary Fire). It only looks: nothing is pressed. **check again** after a fix.
- **The Discovery Scanner must be on primary fire** in the fire group active when you jump.
- **Primary Fire needs a keyboard binding** in Elite's controls (as its second binding, if your trigger is
  the first). Outrider reads it from your active controls preset, modifiers too. A built-in preset can't be
  read: save it as a custom preset, or give the **key** in Settings → Auto honk (`[autohonk] key`). A binding that needs a joystick modifier can't
  be pressed.
- **Try it first.** The dialog's *test in 5 s* button, or `python3 -m outrider.honk --test 10`, holds Primary Fire
  once. `python3 -m outrider.honk --show` prints the binding it will press.
- It presses keys through a virtual keyboard (`evdev`; Steam's controller rule already gives you access), on
  Windows with `SendInput` as VoiceAttack does, and **the keys go to whichever window has focus**, so switch it off
  before alt-tabbing away mid-jump.
- **On Windows (experimental):** don't run Elite as administrator, or Windows silently drops the keys (unless
  Outrider runs as administrator too). It has not been tried against the game on Windows yet: start with the
  test button, and an issue on GitHub saying how it went is very welcome.

## 🕹️ The co-pilot button

On Linux, one button on your HOTAS (or a spare key) talks to the voice. It needs Outrider on the game PC (never in
Docker), where the HOTAS is plugged in:

- **Tap, flying your ship:** target the next route system in the galaxy map (the same run as 🎯 and Target next,
  half a second after the press, so keep your hands off the controls; it brings the game to the front first where it can, and with
  Elite not the active window it says so and presses nothing). It targets the next system of your survey
  route (Road to Riches, Exomastery, a world route, a sweep) or trade route first, then the Highway's while you are on it, then the Next of the boxel you
  explore (as 🎯 beside it does: a name the galaxy map cannot find is probably the boxel's end), then, off the Highway,
  its closest system, and last your chosen next stop (the header's, from a bookmark; a finished route counts as none).
  Success or failure is said as for auto-target; with
  nothing to target, the voice says so in its personality. Out of the ship (the SRV, on foot, a fighter) a tap does
  nothing. A press during that half second cancels it before any key (a double tap that came a little slow) and
  gives the status report instead; so does a press while the run is still waiting with no key pressed (waiting out
  the game's danger flag after a jump, or an auto honk). A double tap's second press must come within 400 ms of the first release
  (`double_ms` under `[copilot]`; a tap waits that long to be sure it is one). It needs auto-target's key bindings
  (see [auto-target](plot-route.md)). It works whether or not
  auto-target after a supercharge is on: leave that off and tap the button when you are ready instead.
- **Double tap:** a status report: fuel and jumps (and any core module under your level), on a Highway route the
  boost, the next route system and the time left ("about 1 hour 40 to go at your pace"), what to do next here (scans
  lost with a ship and still to redo come first: "Next: 12 lost scans to redo in the FSS"), the next stop, what is
  aboard against your rebuy (only what is aboard for a ship bought with Arx, whose hull has no credit value), and the nearest unvisited
  system (left out while you follow a route). With a body targeted it leads with that body
  ("A 3: 2.4 g, thin ammonia, 3 bio signals, up to 19 million, about 2 minutes, worth it"); mid-run on a body, the
  sampling. A double tap mid-line cuts it short.
- **Hold:** hush until the next jump; hold again to end it.
- **In the Rhino** on a planet, any press marks rigs instead (see The surface map).

Set it up in **Settings → Auto honk → The co-pilot button** (or `[copilot]` in `ed_outrider.toml`): tick **use it**,
give the **device** (part of its name, such as `"X-56 Rhino Throttle"`, or a `/dev/input/by-id/…` path; of several
devices that match, the one that has the button is used; when none of them reports that button, the section says so)
and the **button**, then Save and Restart now. Run
`python3 -m outrider.button --listen` to find the button's name. **hold** and **double tap** (ms) tune the gestures.
The section shows whether it is listening. Auto honk's own **key**, **wait after arriving**, **hold** and **leave
systems already honked alone** are there too (the wait and the skip are used from the next honk, the key and the hold
from the next start).

- **Unbind the button in Elite's controls.** Outrider only reads it, so the game would act on it too.
- **X-56 users:** avoid the latching toggles and the mode wheel. They report as buttons held down, which
  reads as one endless hold.
- **Access:** joysticks and throttles are readable by the logged-in user on most distributions (`uaccess`).
  A keyboard or mouse needs your user in the `input` group, which lets every program read your typing, so a
  joystick button is the better choice.

## 📷 Screenshots

The game saves its screenshots as huge BMP files named `Screenshot_0001.bmp`. With **⚙ Settings → Screenshots →
Convert each screenshot as you take it** ticked, Outrider turns each one, as you take it, into a PNG (or a JPG) named
after where it was taken: `Smojooe UW-E c11-22 2 a 2026-10-25 20-33-35.png`. That is the part of EDDiscovery's
screenshots most players use. It runs on the game PC (the Pictures folder is there), needs the optional **Pillow**
package (see [Install and run](install.md)), and is off until you tick it.

- **Which shots:** the game's own, F10 and Alt+F10 (HighRes: four times the size, a few seconds to convert, and on
  Linux GNOME uses Alt+F10 for "toggle maximisation" until you free it in its keyboard settings). Steam's F12
  screenshots are not the game's and are left alone. Outrider takes the place and the commander from the journal's
  line for the shot, so the name is right even after you have jumped on.
- **Where:** the game's Pictures folder's `Converted` folder unless you pick one, in **a folder per commander** (the
  default) and, ticked, **per system** inside it. **Own folders** takes a pattern of your own instead
  (`{cmdr}/{date}`, a `/` for a folder inside a folder), and **name** sets the file's name from `{system}` `{body}`
  (short: `2 a`) `{date}` `{time}` (your local time) `{cmdr}` `{highres}` and `{subject}` (below). A name already
  there gets " (2)".
- **Smaller copies to post:** tick **medium copy** (1920 px on the long edge) and/or **small copy** (1080 px): JPGs at
  quality 85, in `medium/` and `small/` folders beside the full size, never enlarged. The full size is a PNG (lossless)
  or a JPG at the quality you set.
- **The game's BMP:** kept (the default), deleted or moved to a folder of your choice, and only once every image has
  been written and read back.
- **What it shows:** a shot taken on a surface within 50 m (**names what it shows within**) of a plant you sampled
  or tagged with the composition scanner, or of a geology formation you logged in your codex, knows what it shows: the
  variant ("Stratum Tectonicas - Lime") or the formation ("Water Ice Geyser"), kept with the shot, written into the
  image and in the name when you add `{subject}` to it. Every image also carries where it was taken (system, body,
  coordinates, commander, time) inside it, for a later caption.
- **Finding them again:** a 📷 beside a body you photographed in Here, and the body's panel lists its shots with a
  small picture (click it to open it larger: the medium copy when there is one), the time and what it shows; **📍**
  beside a surface shot pins where it was taken.
- **The ones already there:** **Convert the screenshots already there** does the BMPs left in the Pictures folder,
  each matched to its journal line by name and time (one with none is converted with no system), and leaves those
  done already alone. It works with the switch off.
- When one fails (the folder not writable, the file never written), a card says why; the Settings section says what
  keeps it off (Pillow missing, the Pictures folder not found, not the game PC).

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
