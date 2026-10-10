[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · **In-game overlay** · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# In-game overlay

Outrider can draw a few panels right over the game: what is worth your time in the system, the body you are heading
to, and a radar on a body's surface. A small window on the game PC draws them; it sits over Elite's window and lets
every click through, so you play as before.

## What it shows

- **The system panel**, in supercruise: each body worth your time, nearest first, with what is left to do (TO MAP,
  TO LAND, a sample run under way such as "Bacterium 1/3") and what it pays, the codex mark with the new colour
  ("✪ Lime"), then the valuable bodies you have finished (MAPPED, SAMPLED); curiosities on an "Also here" line; what
  is left in the whole system, and how many bodies are under your levels. It uses the levels in your config
  (`body_highlight_level`, `bio_min`), as Here's to-do line does.
- **The body panel**, flying your ship: the body you have targeted in this system (or the one you are near):
  landable, gravity (amber at your high-gravity level), atmosphere, temperature, what mapping is still worth, first
  discovered; its life, each likely species with its codex mark, colony distance and value, the runs under way and
  the species finished; and whether it is worth landing (with the ×5 first-footfall note).
- **The surface radar**, on a body (landed, in the SRV, on foot) or low over it: heading up, you in the middle, N on
  the rim; the sample points of your run with their colony rings, red while you are inside one and green once you are
  clear; tagged plants, the ship and your rigs. Underneath: how far the next sample must be, or "Clear: sample here".

- **The system strip** (optional, off until you tick it), made for the top of the screen: two short lines. The first
  says where you are: the system, its region, the distance from Sol, the star (⛽ scoopable, ⚡ a neutron star or white
  dwarf), what its data pays now and at most, and 🏁 when you discovered it. The second, condensed: how many bodies,
  how many found of them, 🏁 how many you discovered, 🗺 the planets you mapped of all of them, and whether Spansh knows
  the system ("Spansh ✗ (new to it)" when it does not).

No panel covers the galaxy or system map, the orrery, the FSS, the SAA or the codex.

## Starting it

1. In Outrider's **⚙ Settings → In-game overlay**, tick **Show the overlay**. Outrider starts the overlay window itself
   on the game PC (and closes it when you untick it or stop Outrider): one application, nothing else to run.
2. The first time, Settings says the window needs PyQt6 (about 100 MB): press **Install PyQt6**, and it goes into
   Outrider's own environment. On Linux the window finds Elite's with `wmctrl` and `xprop` / `xwininfo` (Debian and
   Ubuntu: `sudo apt install wmctrl x11-utils`).
3. Play Elite **borderless or windowed**; exclusive fullscreen hides anything drawn over it.

Settings → In-game overlay says how the window is doing (starting, drawing, waiting for the game's window). **Show
test panels** draws all three with made-up contents for a minute, without flying anywhere, even while Outrider's page is in front of the game. Start Outrider from your
desktop (the launcher, or a terminal in your session): the window needs your screen.

**Outrider on a server (Docker):** a container has no screen, so the window runs on the game PC instead, pointed at
the server: in a copy of Outrider's folder there, `./launch_overlay.sh --url http://192.168.1.81:8025 --password ...`
(its `[server]` password; Windows: `launch_overlay.bat`), which offers to install PyQt6 the first time. If Outrider
also runs on the game PC, nothing is needed: that one runs the window.

## Arranging the panels

**Arrange panels** (in Settings → In-game overlay) frames each panel over the game. Then:

- **drag** a panel to move it; it is kept from the nearest corner of the game window (or, dropped about the middle,
  centred along the top or bottom edge), so it stays there when the window or resolution changes;
- **drag its corner** (the square handle) to make it bigger or smaller;
- **mouse wheel** over it: its background, from solid to text only; **Shift and wheel**: the whole panel's
  transparency;
- **Done**, at the top of the game window (or the button in Settings), ends it. Arranging ends by itself after ten
  minutes, so the overlay never stays in the way of the mouse.

While arranging, the overlay takes the mouse: do it with the game paused or in a menu. The same settings are in
Settings → In-game overlay as fields for each panel (where it is placed from, how far in, its size and the two
transparencies), with a **reset**.

## Settings

Each panel can be switched off, and the **theme** colours and frames the panels as the page's themes do (Elite's
orange with cut corners, LCARS's bars, ...); **text** is small, normal or large. In the config file (`[overlay]`):
`system_seconds` keeps the system panel only that long after arriving (0: while you are in supercruise there), and
`radar_range` is the radar's edge in metres (it widens to fit a colony ring).

## Good to know

- **Linux** (X11, and Wayland sessions through XWayland, as Elite under Proton runs) is where it is made and tried.
  **Windows** has the same window but is not yet tried against the game.
- Native Wayland compositors (KDE's, Hyprland, sway), gamescope and exclusive fullscreen are not supported.
- The window's code for finding and following the game's window, and drawing over it, is adapted from
  [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay); neither EDMC nor Modern Overlay is
  needed.
