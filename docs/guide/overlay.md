[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · **In-game overlay** · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# In-game overlay

Outrider can draw a few panels right over the game: what is worth your time in the system, your target (the body you
are at or heading to, or the next system), a radar on a body's surface, and (when you tick them) the system strip, Now (To-Do & Info), the bio signals and your alerts. A
small window on the game PC draws them; it sits over Elite's window and lets every click through, so you play as
before.

<p align="center">
  <img src="../images/overlay.png" alt="Five panels over a starfield: the system strip at the top, the system panel top left, the targeted body top right, Now bottom left and Bio signals bottom right" width="900">
  <br><sub>In supercruise in a system with biology: the system strip, the system panel, the body you are heading to, Now
  and Bio signals (real panels from the author's journals; the starfield stands in for the game)</sub>
</p>

## What it shows

- **The system panel**, in supercruise: each body worth your time, numbered in the suggested order as on Here's
  schematic (①②③; the body you tapped to go to first leads), with what is left to do (TO MAP,
  TO LAND, a sample run under way such as "Bacterium 1/3") and what it pays, the codex mark with the new colour
  ("✪ Lime"), then the valuable bodies you have finished (MAPPED, SAMPLED); curiosities on an "Also here" line; what
  is left in the whole system, and how many bodies are under your levels. A body you have not scanned yet (known to
  Spansh only) is listed unnumbered after the stops. It uses the levels in your config
  (`body_highlight_level`, `bio_min`), as Here's to-do line does.
- **The Target panel**, flying your ship (it was the body panel: it keeps that panel's place, size and switch). Close
  to a body (once the game shows its altitude, where the approach begins) it shows **that body**, even when you have
  targeted something else; once you leave, it goes back to your target after 5 seconds out (the edge of that zone
  comes and goes, so it may flick back now and then). Elsewhere it shows **the body you have targeted** in this
  system, or else **the system you have targeted** (in the galaxy map, or the next jump of the route plotted there).
  Nothing targeted: no panel.
  - A body: landable, gravity (amber at your high-gravity level), atmosphere, temperature, what mapping is still
    worth, first discovered; its life, each likely species with its codex mark, colony distance and value, the runs
    under way (what each pays, "1.0M (×5: 5.0M)" with the first-footfall bonus) and the species finished; and whether
    it is worth landing (with the ×5 first-footfall note).
  - A system: "next jump of your route · 5 to go" when a route is plotted; with a route you follow in Outrider, whether
    the target is its next stop ("✓ the next stop of your route", "↷ 2 stops ahead on your route" or "⚠ not the next
    stop: Pru Aim XY-Z d1", see [Plot Route](plot-route.md)); whether anyone reported it (never reported,
    no scan data, partly or fully scanned, visited; "checking…" while Outrider asks), how many bodies Spansh knows of
    how many, and EDSM's; the star with ⛽, or ✕ when it cannot be scooped, and "⚠ throttle down" at a neutron star,
    white dwarf or black hole (⚡ marks a supercharge); the jump: how far, the fuel it burns and the max-range jumps
    left after it, or "out of range"; and, when it is in your Nearby list, what scanning and mapping it could pay, the
    bio up to, and its notable bodies (ELW, WW, AW, T).

  It is the one panel that shows **over the galaxy map**, with the system you target there, so you see what you
  picked before you jump (docked too). Docked, outside the galaxy map, it stays off unless you untick its
  **Docked** box (see [Settings](#settings)).
- **The surface radar**, on a body (landed, in the SRV, on foot) or low over it: heading up, you in the middle, N on
  the rim; the sample points of your run with their colony rings, red while you are inside one and green once you are
  clear; tagged plants, the ship and your rigs. Underneath: how far the next sample must be, or "Clear: sample here".
  **Docking** takes the radar's place (its corner, size and switch: the radar has nothing to show in space; at a
  planetary port the pad comes first until you touch down): from the moment a station gives you a pad until you touch
  down it shows
  **PAD 34** in large letters under the station's name (any station, carrier, outpost, port or settlement); a refusal
  that isn't obvious shows "Docking denied" and why for a minute. At a starport (Coriolis, Orbis, Ocellus, asteroid
  base, Dodec) or a carrier it also says where the pad is ("at the back · up on your right"; a carrier "port side,
  toward the bow") and draws it: the starport as you see it coming through the slot (outer ring near the slot, inner
  ring the back, the slot's lights across the middle, green on the right), the carrier from above with the bow up.
  **Show the pad diagram while docking** (Settings → In-game overlay, `pad_diagram`) turns the drawing off; the words
  stay. Pad positions come from bgol's LandingPad plugin.

  <p align="center">
    <img src="../images/overlay-pad.png" alt="Two docking panels over a starfield: PAD 34 at Jameson Memorial, at the back, up on your right, with the starport seen from the slot; PAD 7 at a fleet carrier, port side, toward the bow, with the deck seen from above" width="900">
  </p>

- **The system strip** (optional, off until you tick it), made for the top of the screen: two short lines, centred.
  The first says where you are: the system, its region and the star (⛽ scoopable, ⚡ a neutron star or white dwarf),
  and in a populated system, on its right, the security level and your reputation with the controlling faction
  (Hostile in red; Unfriendly up to -35, Neutral to +4, Cordial to +35, Friendly to +90, then Allied).
  The second, condensed: the distance from Sol, what its data pays now and at most, 🏁 when you discovered it, how many
  bodies and how many found of them, 🏁 how many you discovered, 🗺 the planets you mapped of all of them, and whether
  Spansh knows the system ("Spansh ✗ (new to it)" when it does not).
  While you mine in a ring in a mining ship, a third line: "⛏ 4 B Ring · Platinum · 38 t/h · hold 112/256 t (Platinum
  80, Painite 32) · limpets 14 · full in ~41 min" (the same line as on Now; Settings → Mining).
- **Now (To-Do & Info)** (optional): the page's Now view in a few lines, anywhere in the system (by default not while
  docked: see [Settings](#settings)). The system (and for 20 s after the jump whether it was
  undiscovered), the system you have targeted next (never reported, no scan data, partly or fully scanned, or visited;
  how many bodies are known; the star with ⛽ or ✕, and ⚠ for a neutron star or white dwarf), where the next jump goes
  (the next stop of the unfinished route you plotted last: the Highway, a survey or trade route;
  and a kept boxel's Next), fuel, and what the data
  aboard stands to lose once it passes your `unsold_warn` level: 🗺 and 🧬, how many times your rebuy it is ("× rebuy";
  none for a ship bought with Arx, whose hull has no credit value) and how long since you sold ("3 days unsold"; from a
  week "2 weeks 2 days since sold", or "2wk2d since sold" when that would not fit; whole days). Then, on a body,
  each genus there with its samples and how far the next sample must be; elsewhere **Next**, the first item of Here's
  suggested order with what it pays, the supercruise time and how many more, and the body you have targeted when it is
  not that one. Last, this session's figures.
- **Bio signals** (optional): every body in the system with bio signals, whether it meets your levels or not. A body
  worth it (over `bio_min`, a run started, new to your codex, or not priced yet) is in bright colours, the rest are
  muted and the finished ones carry a green ✓. Under each body, each species: sampled ✓ with its colour, a run under
  way ("2/3"), lost, or not started with its likeliest species, codex mark and value; signals the DSS has not named yet
  show what they could be. The foot says how many are sampled, what is left and how many bodies are under your level.
- **Alerts** (optional): the page's alerts for a few seconds each, under the system strip at the top: what you
  would hear or see as a notification ("B 1: Earth-like world", "Fuel low", "Interdicted"), its title and a line or two
  of its text, newest first, three at most. Each stays 8 seconds; danger (hull, heat, interdiction, fuel, a rig too far,
  the ship lost, the carrier leaving without you) stays 15 seconds, in red with a red frame. It shows every alert
  switched on in **Settings → Alerts** in the browser that saw it (any of notify, sound or speak ticked), even while
  the voice is off or hushed. The alerts are worded by Outrider's page, so a page must be open somewhere (a browser
  window, the second screen or the tablet): with none open, the panel stays empty. Several windows open count once.

No panel covers the system map, the orrery, the FSS, the SAA or the codex, and over the galaxy map only the Target
panel and the alerts show. While docked (at a station, a carrier or a port, or on foot inside one) the panels ticked
**Docked** in Settings hide: by default the system, Target, Now and Bio signals panels, while the system strip and the
alerts stay. None shows in the hyperspace tunnel or while the game is loading (from its launch, the main menu included, until your session is in), even after a
crash left the old session's status behind.

## Starting it

1. In Outrider's **⚙ Settings → In-game overlay**, tick **Show the overlay**. Outrider starts the overlay window itself
   on the game PC (and closes it when you untick it or stop Outrider): one application, nothing else to run.
2. The overlay window needs PyQt6 (about 100 MB). Nothing to press: whenever the window is wanted (the overlay on,
   the test panels or Arrange mode) and PyQt6 is missing, Outrider installs it once into the Python it runs with (the
   launcher's `.venv`, nothing system-wide; a minute or two, with a popup at the top of every page window until it is
   done). launch_outrider.sh / .bat also install it before Outrider starts whenever `[overlay] enabled = true` is in
   the config (a new PC with your config copied over); a failed install never stops Outrider starting. If installing
   fails, Settings → In-game overlay says why, and Outrider tries again once you switch the overlay off and on. On
   Linux the window finds Elite's with `wmctrl` and `xprop` / `xwininfo`, system programs pip cannot install (Debian
   and Ubuntu: `sudo apt install wmctrl x11-utils`); the launcher says when `wmctrl` is missing.
3. Play Elite **borderless or windowed**; exclusive fullscreen hides anything drawn over it.

Settings → In-game overlay says how the window is doing (starting, drawing, waiting for the game's window), and so
does the **overlay pill** in the page's header, beside the link pill, while the overlay is on:

- **overlay ✓** (green): drawing over Elite;
- **overlay …** (amber): starting, Elite not running or loading, Elite behind this page (you are looking at
  Outrider), minimised or on another desktop, or covered by another window;
- **overlay ✗** (red): something to fix, the reason on hover: wmctrl or xprop not installed, Elite's window not
  found, the overlay window not answering, Elite set to exclusive fullscreen (Outrider reads the game's own
  DisplaySettings.xml), or another window in front of the game while you are not on Outrider's page.

On the tablet the link line says it too ("linked · overlay ✓"). If the window stops by itself, Outrider starts it again after a growing wait; after five times in a row it gives up (Settings
says so) until you switch the overlay off and on. A window that drew for a minute or more before it stopped starts
the count again. **Show test panels** draws every panel (all seven, switched on or
not) with made-up contents for a minute, without flying anywhere, even while Outrider's page is in front of the game.
Start Outrider from your desktop (the launcher, or a terminal in your session): the window needs your screen.

**A game-PC feature.** Like auto honk and auto-target, the overlay needs Outrider running on the game PC: an
Outrider on a server (Docker) has no overlay (its Settings leave the section out). With Outrider on both, the game
PC's draws it.

## Arranging the panels

**Arrange panels** (in Settings → In-game overlay) frames each panel over the game. Then:

- **drag** a panel to move it; it is kept from the nearest corner of the game window (or, dropped about the middle,
  centred along the top or bottom edge), so it stays there when the window or resolution changes;
- **drag its corner** (the square handle) to make it bigger or smaller;
- **mouse wheel** over it: its background, from solid to text only; **Shift and wheel**: the whole panel's
  transparency; **Ctrl and wheel**: the size of all the panels at once (**All Panels: Scale** in Settings);
- **Done**, at the top of the game window (or the button in Settings), ends it. Arranging ends by itself after ten
  minutes, so the overlay never stays in the way of the mouse.

While arranging, the overlay takes the mouse: do it with the game paused or in a menu. The same settings are in
Settings → In-game overlay as fields for each panel (where it is placed from, how far in, its size and the two
transparencies), with a **↺** to reset it.

The arrangement is kept in Outrider's database, not the config file: to take it to another PC, copy
`data/ed_outrider.sqlite` along with `ed_outrider.toml`.

## Settings

Each panel has its tick box at the start of its row in Settings → In-game overlay's table (hover its name for what
it shows; a panel switched off has its row dimmed). The headings are short: hover one for its full meaning.
Under **Hide in mode**, **Combat** keeps a panel off in your ship while the HUD is in combat mode: it shows only
in analysis mode, so the screen stays clear in a fight. In the SRV and on foot (no HUD modes there) and over the
galaxy map it shows as the others. **Docked** hides a panel while you are docked (the ship at a station, a carrier or
a port, or you on foot in a station, hangar or social space); ticked to start with for the system, Target, Now and
Bio signals panels, not for the system strip and the alerts. The radar has no Docked box: it shows only on a body's
surface. The Target panel still shows over the galaxy map while docked, so you see the system you pick. **Foot** hides a
panel on foot, anywhere (in a station or on a planet's surface); none is ticked to start with. The system, Target and radar
panels start on; the system strip, Now, Bio signals
and Alerts start off. The **theme** colours and frames the panels as the page's themes do (Elite's orange with
cut corners, LCARS's bars, ...). In the config file (`[overlay]`):
`system_seconds` keeps the system panel only that long after arriving (0: while you are in supercruise there), and
`radar_range` is the radar's edge in metres (it widens to fit a colony ring); `analysis_only` lists the panels
ticked Combat (`["system", "bio"]`; the Target panel is `body`), `hide_docked` the ones ticked Docked
(`["system", "body", "now", "bio"]` when the key is missing) and `hide_on_foot` the ones ticked Foot.

<a id="mouse-lock"></a>**The mouse on foot and in the DSS.** There Elite locks the mouse to its window, and a window
lying over the game can break that lock on some systems: the cursor runs off the screen while you look around. On
Linux each panel has a window of its own, only as big as the panel, and none shows while there is nothing to draw (the
DSS), so the middle of the screen stays Elite's (a panel you drag to the middle would be in the way again). If the
lock still breaks for you, tick **Hide the overlay on foot and in the DSS** (`hide_mouse_lock`): no overlay at all
there. The game asks for the lock as you step out or open the DSS, so a change counts from the next time.

<a id="sizes"></a>**Sizes and text.** The row at the top reads **All Panels: Theme · Text Size** (small, normal or large,
for every panel: `text_size`) **· Scale** (a %, 100 to start: `panel_scale`), with Show test panels and Arrange panels
on the line under it. Each panel's **Size %** (down to 20 %) is multiplied with the Scale (Scale 100 %: each panel at its own
size; Scale 50 % and a panel at 50 %: 25 %), and its **Text** column gives it a text size of its own, or "as all
panels". Panels follow the game window's height, so a panel takes the same share of the screen at 4K as at 1080p: on a
big TV seen from the sofa, turn the **Scale** down (or Ctrl and wheel over a panel in
Arrange mode). Text is never drawn smaller than **9 pixels**, whatever the sizes say: a small setting on a 1080p screen
stays readable, while a 4K screen can go much smaller. While the overlay window draws, each Size % shows what its
text comes to in the game window ("≈ 11 px text"), or "held at 9 px" when the sizes ask for smaller (the line under the
table names those panels: your screen is too small to go lower). With the game not running there is no figure.

<a id="keep-showing"></a>**Keep showing when Elite is not the active window** (`show_inactive`, off by default): the
overlay normally hides as soon as another window is in front, Outrider's page included. With this on it stays over the
game while you use a window beside it (a browser on another screen, a chat), and still hides when the game is
minimised, on another desktop, or when other windows cover more than a quarter of it (then the pill says "another
window covers Elite's"). On Linux that is judged from the X11 windows' stacking and sizes; a desktop with a workspace
per screen (i3 and the like) counts the game's workspace as in sight while its screen shows it; on Windows from the
windows above the game (not yet tried). **A native Wayland window cannot be seen:** on a Wayland desktop, a program
running as a Wayland window (Firefox and most GNOME and KDE apps do) can sit over the game without the overlay
knowing, so it draws over that window too; an XWayland window (most games, Steam, Discord) is seen.

<p align="center">
  <img src="../images/overlay-settings.png" alt="Settings, In-game overlay: the switch, the window's state, the theme and text size, the test panels and Arrange buttons, and each panel's row with its tick box, corner, offsets, size and opacities" width="740">
</p>

## Good to know

- **Linux on X11** (Xfce, Cinnamon, MATE, KDE on X11...): the native case. Transparency needs a compositor, as every
  modern desktop runs; with a bare window manager the space around the panels shows black.
- **Linux on Wayland**: through XWayland, as Elite under Proton runs. Tried on GNOME. KDE Plasma should behave the same;
  sway and Hyprland treat XWayland windows their own way and are not tried.
- **Proton's native Wayland mode** (`PROTON_ENABLE_WAYLAND=1`) makes Elite a native Wayland window, which the overlay
  cannot find or follow: leave it off. Fractional display scaling on Wayland (125%, 150%) may put the panels a little
  off or blur them: not tried yet.
- **Windows**: the same window (finding Elite's with the Windows API, letting clicks through, always on top), seen
  working over the game by players on Windows (October 2026). Play borderless or windowed.
- Exclusive fullscreen and gamescope (the Steam Deck's game mode) are not supported: nothing can draw over them. The
  overlay pill turns red when the game's DisplaySettings.xml says exclusive fullscreen.
- The window's code for finding and following the game's window, and drawing over it, is adapted from
  [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay); neither EDMC nor Modern Overlay is
  needed.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · **In-game overlay** · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
