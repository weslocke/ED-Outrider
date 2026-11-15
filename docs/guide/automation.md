[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)

# Automation

## 🎯 Auto honk

Outrider can fire the Discovery Scanner for you, on Linux (and on Windows as an experiment). It runs on the game PC
only, never in Docker. On arriving by hyperspace it waits a moment, holds Primary Fire, and says how it went ("System
Scan Completed, 12 Bodies discovered"). It is off until you tick it in ⚙ Settings.

- **It waits** while a map or panel is open, and while the HUD is in combat mode (switch to analysis mode). It never
  presses while the game is at its menu or closed, since the key would go to whatever window has focus: it waits, then
  gives up.
- **It learns which fire groups the scanner is in,** per ship. It waits on a group where it has missed twice in a row;
  one miss can be an alt-tab, which sends the key to another window. The dialog's **forget** clears that after you
  move the scanner.
- **It skips** systems you've already honked, Apex shuttles and multicrew. With `[journals] commander` set, it also
  skips another commander's jumps (see [Two commanders on one PC](install.md#two-commanders-on-one-pc)).

### Setting it up

- **Is it ready?** ⚙ Settings → Auto honk says it at the top, before you tick anything: "Ready: evdev ✓ ·
  /dev/uinput ✓ · /dev/uinput writable ✓ · Primary Fire: Left Alt + K ✓". Otherwise it says what is missing, with the
  fix and its commands to copy: load the `uinput` module, a udev rule that lets you write `/dev/uinput`, a keyboard
  binding for Primary Fire. It only looks: nothing is pressed. **check again** after a fix.
- **The Discovery Scanner must be on primary fire** in the fire group active when you jump.
- **Primary Fire needs a keyboard binding** in Elite's controls (as its second binding, if your trigger is the first).
  - Outrider reads it from your active controls preset, modifiers too.
  - A built-in preset can't be read: save it as a custom preset, or give the **key** in Settings → Auto honk
    (`[autohonk] key`).
  - A binding that needs a joystick modifier can't be pressed.
- **Try it first.** The dialog's *test in 5 s* button, or `python3 -m outrider.honk --test 10`, holds Primary Fire
  once. `python3 -m outrider.honk --show` prints the binding it will press.
- **How it presses:** through a virtual keyboard (`evdev`; Steam's controller rule already gives you access), and on
  Windows with `SendInput` as VoiceAttack does. **The keys go to whichever window has focus,** so switch it off before
  alt-tabbing away mid-jump.
- **On Windows (experimental):** don't run Elite as administrator, or Windows silently drops the keys (unless Outrider
  runs as administrator too). It has not been tried against the game on Windows yet: start with the test button, and
  an issue on GitHub saying how it went is very welcome.

## 🕹 The co-pilot button

On Linux, one button on your HOTAS (or a spare key) talks to the voice. It needs Outrider on the game PC (never in
Docker), where the HOTAS is plugged in.

### Tap, double tap and hold

- **Tap, flying your ship:** target the next route system in the galaxy map. It is the same run as 🎯 and Target next,
  half a second after the press, so keep your hands off the controls.
  - It brings the game to the front first where it can. With Elite not the active window, or another commander
    playing, it says so and presses nothing.
  - **What it targets,** in this order: the next system of your survey route (Road to Riches, Exomastery, a world
    route, a sweep) or trade route; then the Highway's while you are on it; then the Next of the boxel you explore (as
    🎯 beside it does: a name the galaxy map cannot find is probably the boxel's end); then, off the Highway, its
    closest system; last, your chosen next stop (the header's, from a bookmark; a finished route counts as none).
  - Success or failure is said as for auto-target. With nothing to target, the voice says so in its personality.
  - Out of the ship (the SRV, on foot, a fighter) a tap does nothing.
  - **A second press cancels it:** a press during that half second cancels it before any key (a double tap that came
    a little slow) and gives the status report instead. So does a press while the run is still waiting with no key
    pressed (waiting out the game's danger flag after a jump, or an auto honk).
  - A double tap's second press must come within 400 ms of the first release (`double_ms` under `[copilot]`). A tap
    waits that long to be sure it is one.
  - It needs auto-target's key bindings (see [auto-target](plot-route.md#-targeting-and-auto-target)). It works
    whether or not auto-target after a supercharge is on: leave that off and tap the button when you are ready
    instead.
- **Double tap:** a status report of four clauses at most, from these in this order:
  - the surface pin you are flying to first;
  - fuel and jumps;
  - on a Highway route, the boost, the next route system and the time left ("about 1 hour 40 to go at your pace");
  - any core module under your level;
  - what to do next here and how far ("Next: map A 1, 50 million, about 1,500 light seconds"). Scans lost with a ship
    and still to redo come first: "Next: 12 lost scans to redo in the FSS";
  - what is aboard against your rebuy (only what is aboard for a ship bought with Arx, whose hull has no credit
    value);
  - the nearest unvisited system (left out while you follow a route).

  With a body targeted that is not the first stop, it leads with that body, after the pin ("A 3: 2.4 g, thin ammonia,
  3 bio signals, up to 19 million, worth it"). Mid-run on a body, it gives the sampling. A double tap mid-line cuts it
  short.
- **Hold:** hush until the next jump; hold again to end it.
- **In the Rhino** on a planet, any press marks rigs instead (see [Rigs in the Rhino](now.md#-rigs-in-the-rhino)).

### Setting it up

Set it up in **Settings → Auto honk → The co-pilot button** (or `[copilot]` in `ed_outrider.toml`):

1. Tick **use it**.
2. Give the **device**: part of its name, such as `"X-56 Rhino Throttle"`, or a `/dev/input/by-id/…` path. Of several
   devices that match, the one that has the button is used; when none of them reports that button, the section says
   so.
3. Give the **button**. Run `python3 -m outrider.button --listen` to find the button's name.
4. Save and Restart now.

**hold** and **double tap** (ms) tune the gestures. The section shows whether it is listening.

Auto honk's own **key**, **wait after arriving**, **hold** and **leave systems already honked alone** are there too.
The wait and the skip are used from the next honk, the key and the hold from the next start.

- **Unbind the button in Elite's controls.** Outrider only reads it, so the game would act on it too.
- **X-56 users:** avoid the latching toggles and the mode wheel. They report as buttons held down, which reads as one
  endless hold.
- **Access:** joysticks and throttles are readable by the logged-in user on most distributions (`uaccess`). A
  keyboard or mouse needs your user in the `input` group, which lets every program read your typing, so a joystick
  button is the better choice.

## 📷 Screenshots

The game saves its screenshots as huge BMP files named `Screenshot_0001.bmp`. With **⚙ Settings → Screenshots →
Convert each screenshot as you take it** ticked, Outrider turns each one, as you take it, into a PNG (or a JPG) named
after where it was taken: `Smojooe UW-E c11-22 2 a 2026-10-25 20-33-35.png`. That is the part of EDDiscovery's
screenshots most players use.

It runs on the game PC (the Pictures folder is there), needs the optional **Pillow** package (see
[Install and run](install.md)), and is off until you tick it.

### Which shots, and where they go

- **Which shots:** the game's own, F10 and Alt+F10 (HighRes: four times the size, a few seconds to convert).
  - On Linux GNOME uses Alt+F10 for "toggle maximisation" until you free it in its keyboard settings.
  - Steam's F12 screenshots are not the game's and are left alone.
  - The **Screenshot** and **HighRes shot** buttons at the end of [the tablet's control rail](tablet.md#-the-control-rail)
    press F10 and Alt+F10 for you.
  - Outrider takes the place and the commander from the journal's line for the shot, so the name is right even after
    you have jumped on.
- **Folders:** **Game's pictures** is where the game saves its BMPs (empty: Outrider finds it beside the journals).
  **Export pictures to** is where the PNGs or JPGs go (empty: a `Converted` folder inside the game's pictures).
  - Type a path, or **📁** beside the field browses the game PC's folders (always the game PC's, whichever browser the
    page is open in).
  - They are sorted into **a folder per commander** (the default) and, ticked, **one per system** inside it.
  - **or your own** takes a pattern instead (`{cmdr}/{date}`, a `/` for a folder inside a folder).
- **File name** builds each name from `{system}`, `{body}`, `{date}`, `{time}` (your local time), `{cmdr}`,
  `{highres}` and `{subject}` ([below](#what-a-shot-shows)). `{body}` is short (`2 a`), and empty for a shot in
  space, where the game names the system's own star. A name already there gets " (2)".
- **Full-size picture as** PNG, JPG or WebP:
  - PNG is lossless and the default: about 8.5 MB for a 3072 x 1728 shot.
  - JPG or WebP at a **quality** (90: about 1.2 MB as JPG, 1 MB as WebP, the smallest at the same quality).
  - WebP takes 16,383 px a side at most, so a bigger HighRes shot is written as JPG.
  - Untick **keep the full-size picture** to keep only the copies and the crop (with none of them, the full size is
    written anyway).
  - Each file's date is when the shot was taken.

### Copies, a crop and the clipboard

- **Copies to post:** tick **medium** (1920 px on the long edge) and/or **small** (1080 px). They go in `medium/` and
  `small/` folders beside the full size, and are never enlarged.
- **A crop** cuts the same part out of every shot into `crop/`, optionally **resized to** a long edge in px.
  - You give left, top, width and height in % of the picture (so it fits a HighRes shot too), drawn on your latest
    shot as you set it.
  - Say, the middle without the HUD's edges, or a square for an avatar.
- **Their format:** the copies and the crop are JPG (posts anywhere) or WebP (smaller; Discord and browsers show it)
  at their own quality (85).
- **The clipboard:** **After each shot, copy** puts the full size, a copy or the crop on the clipboard, ready to paste
  into Discord or a post. Only the shots you take, never the ones converted later.
  - A medium or small copy is made for the clipboard alone, from the full size or a bigger copy kept, when no file of
    it is kept.
  - The picture is never more than 3,840 px on its long edge (a HighRes shot's full size is shrunk), and the status
    line says so.
  - It replaces what was on the clipboard, a system name copied for the galaxy map included.
  - On Linux it needs `xclip` or `wl-copy`, as the Highway's copy does (see
    [Install and run](install.md#-getting-started)). Windows has its own.

### The game's BMP

The game's BMP is kept (the default), deleted, or moved to a folder of your choice (not the game's own). It is only
deleted or moved once every picture has been written and read back whole. If it cannot be moved or deleted, the
pictures are kept and a card says why.

### What a shot shows

A shot taken on a surface near a plant you sampled or tagged with the composition scanner, or a geology formation you
logged in your codex, knows what it shows. How near is **Note the plant or formation a surface shot shows, when it is
within** (50 m to start; 0: never). A shot in space at a stellar phenomenon is told apart by the codex entry instead
(below).

- **It knows** the variant ("Stratum Tectonicas - Lime") or the formation ("Water Ice Geyser"). That is kept with the
  shot, written into the image, and in the name when you add `{subject}` to it.
- **On foot** the game's line has no position, so Outrider takes yours from that moment.
- **In space at a notable stellar phenomenon** (from the drop there until you are back in supercruise, jump or dock),
  a shot knows the codex entry you logged there: the latest before the shot. A shot taken before any knows the first
  one logged in that visit; with none, it knows nothing.
- **Inside every picture:** its title, a description (system, body, what it shows, position, commander, time) and
  keywords, in the places viewers look: XMP (photo managers), EXIF (Windows' Properties → Details, its "Date taken" in
  your local time) and PNG's own text.

### Your own codex folders

With **Also save tagged screenshots into your codex folders** ticked, a shot that knows its plant (and its colour) or
formation is also saved into a folder of your codex, whichever commander took it.

- **Where:** inside the export folder, in `Biology/<genus>/<species>/<colour>/` (a species with no colours, such as
  the anemones, has no colour folder), `Geology/<group>/<formation>/` or `Phenomena/<group>/<entry>/`. For example
  `Biology/Tussock/Tussock Albata/Green/Smojooe UW-E c11-28 7 f 2026-10-26 08-51-14.jpg`. The folders take the English
  names whatever the game's language.
- **As what:** a copy of the picture exported above (the full size, else the first copy made), or its own full-size
  PNG, JPG or WebP at its own quality. That gives small everyday pictures and fine codex ones: the game's shot is
  converted again for it, before the BMP is deleted or moved.
- **Not filed:** a shot of a plant you have not sampled or tagged yet knows no plant, so it is not copied, nor is one
  whose colour cannot be told.
- **What you hear:** each shot filed this way is a notification and a line ("Picture filed in your codex: Bacterium
  Volu."). A plant's is said by the Exobiologist (the alert row **Codex picture: plant**), a formation's or a
  phenomenon's by the Science Officer (**Codex picture: geology**), each with its own switches in Settings → Alerts.
  Shots converted later (at start-up, or with "Convert the screenshots already there") are filed quietly.

**Your pictures on the checklists:** **Show your own pictures on the Bio/Geo checklists** makes the Exo-Biology,
Geology and Phenomena checklists show one of your own pictures of a species' colour, a formation or a phenomenon,
instead of Canonn's: see [the checklists' pictures](exploration.md#your-own-pictures).

### Finding them again

- **In Here,** a 📷 beside a body says you photographed it (with a count when past one). Its hover card shows the
  newest three.
- **The body's panel** lists its shots under **📷 Screenshots**, each with a small picture, the time and what it shows
  (a plant or formation within 50 m). Click the picture to open it larger: the medium copy when there is one, else the
  largest kept.
- **📍** beside a surface shot pins where it was taken.

### The ones already there, and failures

- **Convert the screenshots already there** does the BMPs left in the Pictures folder. Each is matched to its journal
  line by name and time (one with none is converted with no system). It leaves those done already alone, and empty
  ones (the game never wrote them). It works with the switch off.
- **When one fails** (the folder not writable, the file never written), a card says why. The Settings section says
  what keeps it off (Pillow missing, the Pictures folder not found, not the game PC).

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · **Automation** · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)
