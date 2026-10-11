[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Automation

## 🎯 Auto honk

Outrider can fire the Discovery Scanner for you, on Linux (and on Windows as an experiment). It runs on the game PC
only (never in Docker). On arriving by hyperspace it waits a moment,
holds Primary Fire, and says how it went ("System Scan Completed, 12 Bodies discovered"). It is off until
you tick it in ⚙ Settings.

- It waits while a map or panel is open, and while the HUD is in combat mode (switch to analysis mode).
- It learns which fire groups the scanner is in, per ship, and waits on a group where it has missed twice in a
  row (one miss can be an alt-tab, which sends the key to another window).
  The dialog's **forget** clears that after you move the scanner.
- It skips systems you've already honked, Apex shuttles and multicrew.

Setting it up:

- **The Discovery Scanner must be on primary fire** in the fire group active when you jump.
- **Primary Fire needs a keyboard binding** in Elite's controls (as its second binding, if your trigger is
  the first). Outrider reads it from your active controls preset, modifiers too. A built-in preset can't be
  read: save it as a custom preset, or set `[autohonk] key`. A binding that needs a joystick modifier can't
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
  half a second after the press, so keep your hands off the controls). It targets the next system of your Road to
  Riches, Exomastery or trade route first, then the Highway's. Success or failure is said as for auto-target; with
  nothing to target, the voice says so in its personality. Out of the ship (the SRV, on foot, a fighter) a tap does
  nothing. A press during that half second cancels it before any key (a double tap that came a little slow) and
  gives the status report instead; so does a press while the run is still waiting with no key pressed (waiting out
  the game's danger flag after a jump, or an auto honk). A double tap's second press must come within 400 ms of the first release
  (`double_ms` under `[copilot]`; a tap waits that long to be sure it is one). It needs auto-target's key bindings
  (see [auto-target](plot-route.md)). It works whether or not
  auto-target after a supercharge is on: leave that off and tap the button when you are ready instead.
- **Double tap:** a status report: fuel and jumps (and any core module under your level), on a Highway route the
  boost and the next route system, the next stop, what is aboard against your rebuy (only what is aboard for a ship
  bought with Arx, whose hull has no credit value), and the nearest unvisited
  system (left out while you follow a route). With a body targeted it leads with that body
  ("A 3: 2.4 g, thin ammonia, 3 bio signals, up to 19 million, about 2 minutes, worth it"); mid-run on a body, the
  sampling. A double tap mid-line cuts it short.
- **Hold:** hush until the next jump; hold again to end it.
- **In the Rhino** on a planet, any press marks rigs instead (see The surface map).

Set it up under `[copilot]` in `ed_outrider.toml`: `enabled = true`, the `device` (part of its name, such
as `"X-56 Rhino Throttle"`, or a `/dev/input/by-id/…` path; of several devices that match, the one that has the
button is used) and the `button`. Run
`python3 -m outrider.button --listen` to find the button's name. `hold_ms` and `double_ms` tune the gestures. The
Settings shows whether it is listening.

- **Unbind the button in Elite's controls.** Outrider only reads it, so the game would act on it too.
- **X-56 users:** avoid the latching toggles and the mode wheel. They report as buttons held down, which
  reads as one endless hold.
- **Access:** joysticks and throttles are readable by the logged-in user on most distributions (`uaccess`).
  A keyboard or mouse needs your user in the `input` group, which lets every program read your typing, so a
  joystick button is the better choice.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
