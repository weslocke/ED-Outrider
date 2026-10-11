[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · **On a tablet** · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# On a tablet

## 📱 On a tablet

Open `http://<your PC>:8025/tablet` on a tablet in landscape (made for a larger tablet, about 1280 × 800 CSS pixels):
the same pages in a cockpit layout, in one of nine themes: LCARS (below), Elite (the cockpit HUD's orange, with cut
corners), four from Babylon 5 (Earthforce: navy and steel; Narn: rust and ochre, wedge-cut; Minbari: indigo, lilac and
pearl, soft arches and thin double lines; Centauri: gold on royal purple, ornate notched double borders), Sith (black,
crimson, thin hard lines), Rebel Alliance (cockpit orange and sand, blue for what is chosen) or Dark (a modern app's dark mode: slate
cards, switches and line icons beside the words). Settings picks one per tablet. The Elite, Babylon 5 and Star Wars
themes show their emblem in the free space under the page list (credits at the bottom of this page). Outrider must listen on your network
for this: see [Other devices on your network](install.md#-other-devices-on-your-network).

<p align="center">
  <img src="../images/tablet.png" alt="The tablet layout on Now, with the surface map: the status strip on top, the pages on the left, the game controls on the right" width="900">
</p>

- **The strip on top** shows the system, fuel and unsold data, and the link to Outrider in words ("LINKED",
  "STALE · 48 S AGO", "NO LINK · RETRYING").
- **The pages** are on the left in three groups of four: Explore (Now, Nearby, Here, Bio/Geo), Navigate (Bookmarks,
  Search, Map, Plot Route) and Records (History, Log, Materials, My firsts). There is no Overview.
- **Tap a row** in a table for all of its facts, including the columns too narrow to show, with Show in Here and
  Bookmark.
- **The maps by touch:** on the galaxy map one finger rotates, two fingers move it and a pinch zooms; on Plot Route's
  map two fingers move and pinch.
- **On a planet** the tablet switches to Now when the surface map appears (the Now button says MAP) and back to your
  page when it goes. Nothing else switches pages by itself.
- **Alerts** are a banner across the top (red for danger), and the footer has Hush, Status report and the last line
  said.
- **The voice stays on the PC,** unless you tick **Play alerts here** in the tablet's Settings. Then the tablet speaks
  (in Piper, from Outrider) and plays the alert sounds itself, whether or not a PC browser does too: just the thing
  with a Docker server and no browser open (turn one off if you hear both). **Choose alerts…** under it picks which
  alerts the tablet says (🗣) and plays (🔊), apart from the PC's choices; it starts from what the PC saved as defaults
  for new browsers.
- **Target next** on Plot Route runs at once (no countdown), since tapping the tablet leaves the game focused. Auto
  honk, auto-target's switch and test, backups and the voice settings stay on the PC.
- **Settings** (bottom right): the theme, a dim switch, the theme's emblem, **Show the game controls** (off: no rail
  on this tablet and the pages take its width, for a second tablet), Play alerts here and Choose alerts…, the screen size in CSS
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
Any browser at `/tablet` works too, without the wake word and Ask.

The fonts are Antonio and Barlow Condensed, both under the SIL Open Font License and shipped with Outrider, as are the
other themes' (Michroma, Saira, Orbitron, Exo 2, Russo One, Marcellus, Cinzel, Cormorant Garamond, Share Tech Mono, Rajdhani,
Oxanium, Inter); Dark's icons
are Lucide's (ISC licence, in `static/icons/`). A heading font of your own goes in your git-ignored `data/` folder and
is never shared: `data/fonts/<theme>-display.ttf`: `lcars-display.ttf`, `elite-display.ttf` (a Eurostile-style
face), `babylon5-display.ttf`, `narn-display.ttf`, `minbari-display.ttf`, `centauri-display.ttf`, `sith-display.ttf` or
`alliance-display.ttf`.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · **On a tablet** · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
