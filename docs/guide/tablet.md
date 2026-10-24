[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · **On a tablet** · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# On a tablet

## 📱 On a tablet

Open `http://<your PC>:8025/tablet` on a tablet in landscape (made for a larger tablet, about 1280 × 800 CSS pixels):
the same pages in a cockpit layout, in one of eleven themes: LCARS (below), Elite (the cockpit HUD's orange, with cut
corners), six from Babylon 5 (Earthforce: navy and steel; Narn: rust and ochre, wedge-cut; Minbari: indigo, lilac and
pearl, soft arches and thin double lines; Centauri: gold on royal purple, ornate notched double borders; Vorlon: sea
green and gold on deep green-black, soft arcs with a faint glow; Shadows: violet and light grey on black and dark purple,
thorn-cut corners and spiked lettering), Sith (black,
crimson, thin hard lines), Rebel Alliance (cockpit orange and sand, blue for what is chosen) or Dark (a modern app's dark mode: slate
cards, switches and line icons beside the words). Settings picks one per tablet. The Elite, Babylon 5 and Star Wars
themes show their emblem in the free space under the page list (credits at the bottom of this page). Outrider must listen on your network
for this: see [Other devices on your network](install.md#-other-devices-on-your-network).

<p align="center">
  <img src="../images/tablet.png" alt="The tablet layout on Now, with the surface map: the status strip on top, the pages on the left, the game controls on the right" width="900">
</p>

- **The strip on top** shows the system, fuel and unsold data, and the link to Outrider in words ("LINKED",
  "LINKED · NO GAME", "UNLINKED · RETRYING").
- **The pages** are on the left in three groups: Explore (Now, Nearby, Here, Bio/Geo), Navigate (Bookmarks,
  Search, Map, Plot Route) and Records (History, Log, Materials, CMDR, My firsts). There is no Overview.
- **Tap a row** in a table for all of its facts, including the columns too narrow to show, with Show in Here,
  Bookmark and, on a route's row, a bookmark or a Nearby row (game PC), **Target** (the galaxy map's destination marker). On the galaxy map a tap on a system shows its card,
  with **Target** when auto-target works on the game PC, Copy name and **Plot route**.
- **The maps by touch:** on the galaxy map one finger rotates, two fingers move it and a pinch zooms; on Plot Route's
  map two fingers move and pinch.
- **On a planet** the tablet switches to Now when the surface map appears (the Now button says MAP) and back to your
  page when it goes.
- **Docking**: when a station or carrier gives you a pad, the tablet switches to Now (PAD 34, where it is, its
  diagram) and back to your page once you have docked, unless you chose a page meanwhile.
- **By voice**: "show Nearby", "open Bio", "go to the map", "back to Now" switch the tablet to that page, as a tap in
  its nav would (the PC's windows stay where they are).
- **Alerts** are a banner across the top (red for danger), and the footer has Hush, Status report and the last line
  said.
- **The voice stays on the PC,** unless you tick **Play alerts here** in the tablet's Settings. Then the tablet speaks
  (in Piper, from Outrider) and plays the alert sounds itself, whether or not a PC browser does too: just the thing
  with a Docker server and no browser open (turn one off if you hear both). **Choose alerts…** under it picks which
  alerts the tablet says (🗣) and plays (🔊), apart from the PC's choices, in the same groups and with the same names as
  Settings → Alerts; it starts from what the PC saved as defaults for new browsers.
- **Target next** on Plot Route and every 🎯 (a route's systems, a boxel's) run at once (no countdown), since
  tapping the tablet leaves the game focused; Outrider still brings the game to the front first where it can, and
  counts down 5 s when the game is not the active window (see [auto-target](plot-route.md)). Auto honk, auto-target's switch and test, backups and the voice
  settings stay on the PC.
- **Settings** (bottom right): the theme, a dim switch, the theme's emblem, **Show the game controls** (off: no rail
  on this tablet and the pages take its width, for a second tablet), Play alerts here and Choose alerts…, **Voice
  commands…** (a big sheet listing what you can ask by voice without any AI: what each command does, the phrases that
  ask it and the words that narrow it, such as "nearest Vista" or "hush until the next jump"), the screen size in CSS
  pixels, the app's version and, in the Android app, its own screens (Server…, Voice…, App menu…), and Sign out when
  Outrider asks for a password.
- **A smaller tablet** (under 1200 × 700 CSS pixels) gets a compact layout: a narrower page
  list, and a narrower rail whose eight buttons fit without scrolling, with short names (Gear, Scoop, Night vis.…).
- **The control rail** on the right (on the game PC only; not in Docker): up to eight game buttons for where you are
  (ship, SRV, Nomad, fighter, on foot), each pressing that control's keyboard binding on the PC once. The defaults are
  landing gear, cargo scoop, night vision, ship lights, flight assist, silent running, hardpoints and analysis mode;
  the SRV, the Nomad and fighters, and on foot have their own. A button shows the game's state (Status.json), SENT
  until the game confirms a press, and "not confirmed" if it doesn't. Hardpoints, landing gear and cargo scoop show
  N/A in supercruise, where they can't be used (the game even reports hardpoints deployed there after a jump). A control with no keyboard binding says "bind a
  key" (give it a second, keyboard binding in Elite's controls). Edit chooses, renames and orders each set (stored on
  the PC). The rail presses keys only while the game runs, through auto honk's keyboard (Linux; Windows experimental), and never
  while auto honk or auto-target is pressing; one tap per button, never a sequence.

**The Android app.** [ED Outrider for Android](https://github.com/weslocke/ED-Outrider-Android) shows the tablet layout
full screen with the screen kept on, signs in once, listens for a wake word ("Hey Vespa", "OK Vespa"; the word and
its sensitivity are in the app's Voice screen) or a tap on Ask, and can read answers aloud when nothing else speaks.
The app opens no file picker, so the controls that would (Bookmarks → **Import…**, Settings → **Import settings…**)
are not shown there; a note in their place says to import from a browser on the PC. Nor can it save a file the page
makes itself, so Settings → **Export settings** and the voice lab's **⬇ Save WAV** are not shown there either (a note
says to do it from a browser on the PC). Every other export (the CSV and JSON links on Bookmarks, History and the
other pages) downloads in the app as anywhere.
Any browser at `/tablet` works too, without the wake word and Ask, and with every control.

The fonts are Antonio and Barlow Condensed, both under the SIL Open Font License and shipped with Outrider, as are the
other themes' (Michroma, Saira, Orbitron, Exo 2, Russo One, Marcellus, Cinzel, Cormorant Garamond, Share Tech Mono, Rajdhani,
Oxanium, Inter, Metal Mania); Dark's icons
are Lucide's (ISC licence, in `static/icons/`). A heading font of your own goes in your git-ignored `data/` folder and
is never shared: `data/fonts/<theme>-display.ttf`: `lcars-display.ttf`, `elite-display.ttf` (a Eurostile-style
face), `babylon5-display.ttf`, `narn-display.ttf`, `minbari-display.ttf`, `centauri-display.ttf`, `vorlon-display.ttf`, `shadow-display.ttf`, `sith-display.ttf` or
`alliance-display.ttf`.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · **On a tablet** · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
