[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Plot Route

## 🛣 The Neutron Highway

The **Plot Route** tab plots a route with [Spansh](https://spansh.co.uk), using neutron stars as boosts (or a
Road to Riches, an Exomastery or a trade route, below), and follows it as you fly. One route of each kind is kept (following it needs no network)
until you plot another or **Clear route**.

<p align="center">
  <img src="../images/highway.png" alt="The Plot Route tab: the jump list, and the route on a map of the galaxy's regions" width="900">
</p>

- **Two plotters.** **Exact** (the default) plans every jump with its fuel and refuel stops from your ship's own
  figures (drive, masses, tanks, Guardian booster, engineering) and your cargo; tick **no neutron boosts** for a
  route of regular jumps only (no neutron stars to fly past). **Neutron** plans waypoints only,
  from a range, the supercharge (×4, or ×6 with the SCO Mk II) and an efficiency: for a ship you haven't flown, or
  a quick plot.
- **Ship.** Any ship you have flown, as of its latest Loadout. The neutron plotter's **Range** starts at that
  ship's laden range; type another to override it.
- **Conservative range** (off by default): jumps a margin (5 ly) shorter than the ship's range, leaving room for a
  fuller tank.
- **A system Spansh doesn't know yet.** Spansh can only plot between systems it has heard of, and a system you
  have just discovered may not be one of them. Outrider then plots from (or to) a system Spansh knows close by, on
  the way, and puts yours back as the route's first (or last) jump: "Spansh doesn't know Drojau SL-D a53-5 yet: the
  route starts with a 12.4 ly jump to Smojooe XY-Z a1-2". That jump's fuel isn't figured, and if it is longer than
  your range the message says so. A destination works the same way when Outrider knows where it is (a system you
  have visited or bookmarked). Road to Riches and Exomastery do the same; a trade route can't, since it starts from a
  station's market as Spansh has it.
- **Too much fuel.** A long neutron jump may be in range only with the fuel the plotter expected. On arrival, and
  as you scoop, Outrider checks the next jump against the fuel aboard and warns ("⚠ too much fuel for the next
  jump: ≤ 36 t, you have 140 t").
- **The list** shows the next 200 jumps with distance, ⚡ neutron, fuel and ⛽ refuel stops (the exact plotter's: the
  neutron plotter has none, scoop as you go); click a name to copy
  it. The map beside it draws the route on the galactic regions with landmarks and your carrier. You can put your
  own galaxy image under it (`background_image`, an EDAstro chart say).
- **Following.** Arriving at any route system moves you along, forwards or back; anywhere else (a respawn
  included) is **Off Route: Detour** until you are back on it, with the closest route system marked. A line under
  the tiles shows the next stop ("🛣 Next: Hwy Stop 38 · ⚡ neutron · 4.2 ly · 38 of 399 · refuel in 3 jumps").
- **Clipboard.** On arrival the next system's name goes on the desktop clipboard for the galaxy map (Linux:
  `wl-copy` or `xclip`, see [Getting started](install.md#-getting-started); Windows: built in; on the game PC only).
- **The voice:** "Next Neutron Highway Stop: Hwy Stop 38, with three jumps left to refuel. Boost your FSD to
  continue.", plus refuel stops, detours, "Back on the highway", "Highway complete" and the fuel warning.

**Road to Riches.** The third plotter, **Road to Riches**, asks Spansh for a chain of systems whose planets are worth
scanning (and mapping): from where you are (or From), with your ship's range, and Spansh's own options (radius, number
of systems, maximum distance, minimum value, mapping value, avoiding Thargoid systems, a loop back). The list then
shows each system with what is left to do there, the bodies by name under the one you are at and the next, ✔ scanned
and ✔✔ mapped from your journal; on arrival the voice says how many bodies are worth the stop and the best of them,
and once they are done, the next system. It is not auto-targeted on its own: a Road to Riches is for stopping, not hurrying past.
With a Highway route as well, a switch above the heading picks which one the tab shows; only the one plotted last
copies its next system to the clipboard. (Road to Riches is thshurka's contribution.)

**Exomastery.** The fourth plotter, Spansh's **Expressway to Exomastery**, plots systems whose bodies carry valuable
life already reported by other commanders, with the same options as Road to Riches (no mapping value). It shares Road
to Riches' place (and a trade route's): one of them at a time, a new plot replaces it. Each body lists its species with their
value, ✓ once you have sampled them and ✦ when one would be new to your codex in that region; the voice says on
arrival how many species are left on how many bodies and the best of them, and the next stop once they are sampled.
It is known life, so first footfall (×5) is unlikely: the values shown are the base ones.

**Trade.** The fifth plotter: Spansh's trade planner, station-to-station hops from where you are docked, in the
same place as Road to Riches and Exomastery (one of the three at a time). See [Trading](cargo-and-trading.md#-trading).

**The route line and 🎯.** The line under the tiles shows the next stop of whichever route the tab shows (🛣 the
Highway, 💰 Road to Riches, 🧬 Exomastery, 💱 a trade route). A 🎯 beside that next system, and beside every system in the tab's lists,
targets it in the galaxy map for you (game PC only, after a 5 s countdown to click back into the game; on the tablet,
the row's sheet has 🎯 Target).

**Auto-target** (Linux, Windows experimental; on the game PC only, off by default; the tab's **Auto-target the next system** box). After an FSD supercharge
in a route system it waits 5 s, then presses keys to make the next route system your target: it opens the galaxy
map, searches for the system, plots the route, closes the map and checks the target took. It says "Successfully
targeted neutron jump target Hwy Stop 38" (or "Failed to…") under its own alerts row.

- **Keyboard bindings:** Galaxy Map Open, UI Up, UI Select and the galaxy map's Camera Yaw Right and Camera Zoom
  Out need one (the box lists any missing; a built-in preset can't be read). It shares auto honk's virtual keyboard;
  honk goes first.
- Switching it off, clearing the route or plotting a new one stops a run at once, even mid-way. If the game targets
  a different system it says so by name ("Targeted the wrong system: …. Check before you jump."). A waypoint the
  game reaches by a plotted route of several jumps counts as targeted.
- It never runs docked, landed, in a vehicle or on foot, in danger, with the FSD charging or a panel open. The game
  flags you "in danger" for every jump, and on entering supercruise, until some 15-26 s after: pressed in those
  seconds, it says so ("Not targeting due to danger. I will keep trying until you are out of danger, for up to 55
  seconds"), waits for that to clear and then runs (up to a minute after the jump or the supercruise entry; being
  interdicted is never waited out). It stops
  if anything unexpected happens, closing the map only if it opened it. Once the route is plotted you can start
  the FSD charge without waiting for its last check: the target is set, so that counts as targeted.
- **The keys go to whichever window has focus**: stay in the game until it is done.
- The log gets one line per run ("highway auto-target: targeted Hwy Stop 38"); every step is printed only when it
  fails.
- **🎯 Target next** (in the box, and beside "Next:" in the route line on Overview, Nearby and Here) does the same
  on demand, whether or not auto-target is on: the next route system, or off the route the closest one, after a
  5-second countdown to click back into the game. A failed run puts **⟳ Retry** on its route row.
- **Test now** in the box targets the nearest known system a plain jump away, after a 5-second countdown.
  `python3 -m outrider.target --show` prints the steps with your keys.
- Every step can be changed under `[highway]` (`autotarget_search`, `autotarget_submit`, `autotarget_plot`…) if a
  game update moves things; `autotarget_entry = "paste"` pastes the name instead of typing it. Pasting (also how
  it enters a name a US keyboard layout can't type) needs the clipboard: `wl-copy` or `xclip` on Linux.
- **Frontier's rules:** this is key-press automation like auto honk (and tools such as Auto_Neutron). Whether to
  use it is your call.

## 📍 Nearest place to dock

**📍 Nearest…** beside To finds the nearest stations and fleet carriers you can dock at and use, and plots there.

<p align="center">
  <img src="../images/nearest.png" alt="Nearest place to dock: stations and carriers with UC and Vista, nearest first, with their docking and how old each report is" width="900">
</p>

- **Filters:**
  - stations and/or fleet carriers;
  - what it must have (Universal Cartographics, Vista Genomics, repair, refuel, shipyard);
  - your ship's pad size (from its type);
  - **Data under** N days (30 by default);
  - permit systems, left out unless ticked.

  They are remembered on this device.
- **Each row shows** how far it is (and a rough jump count), how far from its star (far ones marked), what it has, its
  pads, its docking, and where the report came from and how old it is.
- **Plot here** puts the system in To and plots it with the plotter chosen above. Following the route works as usual.
- **Docking:**
  - "yours" for your own carrier, "open to all";
  - a **⚠ warning** for carriers set to friends or squadron only (Outrider cannot see the owner's list), and for those
    with no docking setting reported at all.

  None of these are hidden: the warning is there so you can decide.
- **Where the data comes from:**
  - [Spansh](https://spansh.co.uk) for stations and carriers, as players last reported them. A carrier is only where
    someone with an uploader last docked: that is why every row says how old its report is, and why older reports are
    hidden (raise Data under to see them).
  - The **[Deep Space Support Array](https://inara.cz/elite/squadron-about/13586/)'s** carrier list, as
    [EDAstro](https://edastro.com) publishes it. These are carriers stationed for years in the black for explorers,
    open to all, each marked **🛰 DSSA** with how long it stays. The list is fetched only when you open the finder, at
    most once an hour, and only downloaded when it has changed. The last copy is kept, so the finder works offline.
  - Your own carrier, from your journal.
- **By voice** (the Android app): "nearest station", "nearest carrier", "nearest Vista", "nearest cartographics",
  "nearest repair", "where can I dock". The voice uses the DSSA list Outrider already has; it never fetches it.

<p align="center">
  <img src="../images/nearest-dssa.png" alt="A DSSA carrier in the list: its badge, how long it is stationed, and when it was last seen docked" width="900">
</p>

---

[ED Outrider](../../README.md) · [Install and run](install.md) · [The views](views.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
