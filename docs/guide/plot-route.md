[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Plot Route

## 🛣 The Neutron Highway

The **Plot Route** tab plots a route with [Spansh](https://spansh.co.uk), using neutron stars as boosts (or a
Road to Riches, an Exomastery, an Earth-like, ammonia or terraformable world route, a sweep or a trade route, below), and follows it as
you fly. Two routes are kept (following them needs no network): one Highway route (Exact or Neutron) and one survey
route (any of the others but Carrier), each until you plot another of its kind or **Clear route**; a carrier trip is
kept apart from both.

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
- **📋 paste** beside From, To and a trade route's Station fills the field with the name on the **game PC's**
  clipboard (copied from EDSM, Spansh or anywhere), for a window that never takes focus (a touchscreen beside the game)
  or the Android app, where typing is awkward. It only fills: nothing is plotted until you press Plot. Shown in the game
  PC's own browser and the Android app only (not in other browsers on your network), and only for one short line of
  text (a paragraph or a link is refused). Linux needs `wl-paste` (Wayland) or `xclip` (X11), the same packages that
  copy the next system; Search's Find a system by name and the Nearby Focus/Lock, Search and Nearest "a system…"
  boxes have one too.
- **Conservative range** (off by default): jumps a margin (5 ly) shorter than the ship's range, leaving room for a
  fuller tank.
- **A system Spansh doesn't know yet.** Spansh can only plot between systems it has heard of, and a system you
  have just discovered may not be one of them. Outrider then plots from (or to) a system Spansh knows close by, on
  the way, and puts yours back as the route's first (or last) jump: "Spansh doesn't know Drojau SL-D a53-5 yet: the
  route starts with a 12.4 ly jump to Smojooe XY-Z a1-2". That jump's fuel isn't figured, and if it is longer than
  your range the message says so. A destination works the same way when Outrider knows where it is (a system you
  have visited or bookmarked). Road to Riches and Exomastery do the same; a trade route can't, since it starts from a
  station's market as Spansh has it.
- **Too much fuel, or too little.** A long neutron jump may be in range only with the fuel the plotter expected,
  and a tank not filled at a refuel stop may not reach the next one. On arrival, and as you scoop, Outrider burns the
  jumps to the next ⛽ stop one by one with the fuel aboard (the exact plotter's route; the neutron plotter's, only the
  next jump) and says one of: "⚠ too much fuel for the next jump: ≤ 36 t, you have 140 t", or "⚠ fuel won't reach the
  refuel stop: Hwy Stop 42 in 4 jumps · scoop to ≥ 24.3 t, at most 36.0 t" (both limits in one line, from the same
  sum). Spoken once per system. At a ⛽ stop itself it only shows how much to scoop ("⛽ scoop to ≥ 24.3 t to reach
  Hwy Stop 46 in 3 jumps"), since you scoop there anyway. Not on a route plotted with FSD injections.
- **Last scoopable star.** On any route Outrider follows (the game's plotted route too, and a survey route's legs), at a
  scoopable star with stars ahead you can't scoop and not enough fuel to get past them, it warns once each time you
arrive there: "The next 3
  stars on your route are not scoopable. This is your last chance to top off before you need to call the Fuel Rats."
  The In-Game Route line (else the route line under the tiles) and Now show "⛽ last scoop before 3 dry" with how much
  to scoop. Only stars known not to scoop count
  (the game's star class, a neutron on the route, Spansh's record); not while you are scooping. On an exact-plotter
  route the refuel-stop warning above says it instead.
- **The list** shows the next 200 jumps with distance, ⚡ neutron, fuel and ⛽ refuel stops (the exact plotter's: the
  neutron plotter has none, scoop as you go); click a name to copy
  it. The map beside it draws the route on the galactic regions with landmarks and your carrier. You can put your
  own galaxy image under it (`background_image`, an EDAstro chart say).
- **Following.** Arriving at any route system moves you along, forwards or back; anywhere else (a respawn
  included) is **Off Route: Detour** until you are back on it, with the closest route system marked. A line under
  the tiles (and on Now) shows the next stop ("🛣 Next: Hwy Stop 38 · ⚡ neutron · 4.2 ly · 38 of 399 · refuel in 3 jumps").
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
Systems ahead that you have already finished (an earlier trip, or out of order) are passed over: the next stop is the
first one with work left, "Next: Pru Aim XY-Z d1 · 3 jumps · 6 of 22 · skipping 2 done" (hover for their names; the jumps count from where you are, through the systems passed
over), and
the voice says "Next stop: Pru Aim XY-Z d1, skipping 2 systems you've finished." The route's last system is never
passed over (arriving there ends it). Exomastery and the world routes do the same; a sweep or a trade route never
skips a stop.
With a Highway route as well, a switch above the heading picks which one the tab shows; only the one plotted last
copies its next system to the clipboard (once it is finished, the other one copies again). (Road to Riches is thshurka's contribution.)

**Exomastery.** The fourth plotter, Spansh's **Expressway to Exomastery**, plots systems whose bodies carry valuable
life already reported by other commanders, with the same options as Road to Riches but for the mapping value and
avoiding Thargoid-hit systems. It shares Road
to Riches' place (and the other survey routes'): one of them at a time, a new plot replaces it. Each body lists its species with their
value, ✓ once you have sampled them and ✦ when one would be new to your codex in that region; the voice says on
arrival how many species are left on how many bodies and the best of them, and the next stop once they are sampled.
It is known life, so first footfall (×5) is unlikely: the values shown are the base ones.

**Earth-like, Ammonia and Terraformable.** Three more plotters ask Spansh for a chain of systems with Earth-like worlds
(🌍), ammonia worlds (🧪) or terraformable rocky and high metal content worlds (🪨) nobody has mapped yet: Road to Riches
limited to those kinds of planet, as Spansh's own pages plot them, with the same options but for the minimum value and
the mapping value. Terraformable asks only for the terraformable ones (worth about 460 thousand or more mapped; Spansh's
own rocky and HMC page lists every plain rocky body too, worth a couple of thousand). These worlds are worth mapping, so
a body is done once it is scanned and mapped. Followed like Road to Riches; the end is "Earth-like route complete."
(or "Ammonia route complete.", "Terraformable route complete.").

**A sweep.** Tick systems in **Left behind**, **My firsts** (with show lost: the systems whose data was lost) or
**Bookmarks**, then **🧹 Plot a sweep (N)** beside any of the three lists (the ticks are one set across them, kept until
the page reloads). Spansh's tourist router puts them in the order to fly them, from where you are with your ship's range,
and Plot Route shows the route: on each arrival the voice says the next stop, and "Sweep complete." at the last. A system
Spansh doesn't know yet (a fresh discovery among your lost firsts, say) is left out, and the plot's message and the
route's heading name it. A sweep takes up to 100 systems and replaces the survey route there is.

**Trade.** Spansh's trade planner: station-to-station hops from where you are docked, in the
same place as the survey routes (one of them at a time). See [Trading](cargo-and-trading.md#-trading).

**Carrier.** Your fleet carrier's trip, from Spansh's carrier router. It is planning only: the game books one carrier
jump at a time, so you still set each in the carrier's galaxy map. Its own form: the depot, the tritium in the hold
and the cargo in use (filled in from your journal, all changeable), the carrier's type, **To me** (your system as the
destination) and **+ via** for a stop on the way. The plan, folded under the form: each leg with its light years and
tritium, and what to do first ("move 300 t from the hold into the depot first", "buy 400 t here"); at the top, the
legs, about how long (20 minutes a leg: the countdown and the cooldown; longer in busy systems) and the tritium
needed against what you have. It never replaces your ship's route, and 🎯 never targets it.

Following it, on the **Carrier tile**: "Leg 2/6 → the next system 📋 · departs 12:30 ✕". 📋 copies the system to
paste in the carrier map (only when you click it); after a jump the line counts the cooldown down, then says
**ready** (or **ready?** when you are away: only the booked jump says the carrier moved, and a busy system can delay
it). A jump onto a later leg skips ahead; one anywhere else says "off the trip", with **re-plot from here**; ✕ ends the
trip, and the last leg ends it. The Quartermaster says "Carrier ready to jump. Next leg: …" when the cooldown should be
over (the **Carrier trips** row in Settings → Alerts) and adds "Leg 3 of 6, 3 to go" to the carrier's arrival line.

**The route line and 🎯.** The line under the tiles (on every tab) shows the next stop of whichever route the tab shows (🛣 the
Highway, 💰 Road to Riches, 🧬 Exomastery, 🌍 Earth-like worlds, 🧪 ammonia worlds, 🪨 terraformable worlds, 🧹 a sweep, 💱 a trade route), its
"Next:" after the galaxy map's **waypoint** marker. The page draws the target button (🎯 in these notes and in
notifications) as the galaxy map's own **destination** marker, in the text's colour. The
**In-Game Route:** line above it is the game's own
route, the one plotted in the galaxy map: it can differ from Outrider's until 🎯 targets the next stop, which has the
game plot its route there. A 🎯 beside that next system, and beside every system in the tab's lists,
targets it in the galaxy map for you (Outrider brings the game to the front itself where it can, else
after a 5 s countdown to click back into the game; on the tablet, the row's sheet has **Target**). The same 🎯 sits beside your carrier's system on the Carrier tile while it is elsewhere,
and beside a boxel's Next and its rows (see [Boxel exploration](views.md#-boxel-exploration), whose opt-in **auto-target
the next on arrival** uses the same run).

**Where a 🎯 shows.** Every 🎯, wherever it is, follows one rule: it shows only on the game PC and only when
auto-target can work there (the virtual keyboard open and every key it needs bound; whether **Auto-target after a
supercharge** is ticked does not matter). Anywhere else there is no 🎯 at all, rather than a button that cannot work:
on a server, without the keyboard, or while the box below lists a missing binding (then **target next** in the box
is greyed out too, and a failed row gets no ⟳ Retry).

**🎯 and Plot route anywhere.** A 🎯 also sits beside each bookmark, the header's next stop, the Nearest finder's rows,
Search's results and the Exo-Biology checklist's "🔍 nearby" rows (never your own system), and left of each system's name in Nearby
(the Overview's too, in a column of their own). **Plot route** beside a bookmark or
the next stop puts the system in To and opens the form; it plots at once when you follow no route, and with one it
waits for your Plot (a new plot replaces the route you follow). A click on a system in the Map tab targets it the same
way when auto-target can work on this PC, else copies its name (see [the Map](views.md)).

**Is the right system targeted?** The route line (under the tiles, on Now and in the tab) checks what the game has
targeted against the next stop: "✓ targeted"; "⚠ targeted Ossia, not the next stop Pru Aim XY-Z d1"; or, for a later
stop of the same route (on purpose, say to skip one), "↷ targeted Ossia, 2 stops ahead". A route plotted in the galaxy
map counts by where it ends. A wrong target is said once ("You've targeted Ossia. The next stop is Pru Aim XY-Z d1.")
under its own alerts row, **Wrong target** (spoken, no notification by default), after you close the galaxy map; never
while you are off the route, for a later stop, or for a body or station in the system you are in. The overlay's Target
panel shows the same check.

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
  flags you "in danger" for every jump, and on entering supercruise, until some 16-26 s after: pressed in those
  seconds, it says so ("Not targeting due to danger. I will keep trying until you are out of danger, for up to 55
  seconds"), waits for that to clear and then runs (up to a minute after the jump or the supercruise entry; being
  interdicted is never waited out). It stops
  if anything unexpected happens, closing the map only if it opened it. Once the route is plotted you can start
  the FSD charge without waiting for its last check: the target is set, so that counts as targeted.
- **It brings the game to the front itself** before the keys, and presses no key unless Elite is the active window
  (checked before every key): click into the browser mid-way and it stops at once. This needs **`wmctrl`** and
  `xprop` on Linux (`sudo apt install wmctrl x11-utils`, as for the [overlay](overlay.md)); it works with the game
  under X11, and under XWayland on a Wayland desktop (tried on GNOME; KDE Plasma should work, untried). On Windows it
  is untried. The box says whether it does, or why not.
  - When the game does not come to the front, 🎯, Target next and Test now count down 5 s instead ("Elite is not the
    active window: click into the game") and still check before the first key; the automatic run and the co-pilot
    button's say so and press nothing.
  - Where it cannot see the game's window (no `wmctrl`; the game as a native Wayland window, Proton's Wayland driver;
    Sway, Hyprland and window managers that refuse focus stealing ignore it): the 5 s countdown as before, and then
    **the keys go to whichever window has focus**: stay in the game until it is done.
- The log gets one line per run ("highway auto-target: targeted Hwy Stop 38"); every step is printed only when it
  fails, each with the key it pressed ("5 plot the route: hold Space … for 1 s: done").
- **🎯 Target next** (in the box, and beside "Next:" in the route line under the tiles, on every tab, and on Now) does the same
  on demand, whether or not auto-target is on: the next route system, or off the route the closest one, at once when
  it brings the game to the front, else after a 5-second countdown to click back into the game. A failed run puts
  **⟳ Retry** on its route row.
- **Test now** in the box targets the nearest known system a plain jump away, the same way.
  `python3 -m outrider.target --show` prints the steps with your keys.
- Every step can be changed under `[highway]` (`autotarget_search`, `autotarget_submit`, `autotarget_plot`…) if a
  game update moves things, in Settings → Server: a change applies to the next run, no restart needed. Steps are
  `press <key>`, `hold <key> <seconds>` or `wait <seconds>`, one per line; a key is one of the game's controls
  (`UI_Select`, `UI_Up`, `CamZoomOut`…, in any case), `Enter`, or keyboard keys such as `KEY_LEFTALT+KEY_T`. After the
  search the focus stays in its panel: the default plot moves the camera first (`hold CamZoomOut 0.2`), and only then
  does holding `UI_Select` plot the route. `autotarget_entry = "paste"` pastes the name instead of typing it. Pasting (also how
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
  - a **material trader**: any, raw, manufactured or encoded (stations only: fleet carriers never have one). Spansh says
    each trader's kind; the few it lists with no kind (some Colonia outposts) count only for "any", shown as "⇄ trader";
  - your ship's pad size (from its type);
  - **Data under** N days (30 by default);
  - permit systems, left out unless ticked;
  - **Around**: you, your destination in game, your carrier, your next stop or a system you name. The distances are
    from there (a row's hover says how far from you) and there is no jump count.

  They are remembered on this device.
- **Each row shows** how far it is (and a rough jump count), how far from its star (far ones marked), what it has, its
  pads, its docking, and where the report came from and how old it is.
- **Plot here** puts the system in To and plots it with the plotter chosen above (Exact when Trade or Carrier is chosen). Following the route works as usual.
  Where auto-target can work, a **🎯** beside it targets the system in the galaxy map.
- **By voice** ("nearest station", "nearest Vista"...), a place further than 500 ly also gets a neutron route plotted
  there, unless you are following a route ("You're following a route, so I didn't plot one"). `[highway] voice_plot`
  switches it off, `voice_plot_ly` sets the distance (Settings → Server).
- **Docking:**
  - "yours" for your own carrier, "open to all";
  - a **⚠ warning** for carriers set to friends, squadron, or squadron and friends only (Outrider cannot see the
    owner's list), for those closed to visitors, and for those with no docking setting reported at all; a DSSA carrier
    last seen away from its post gets "last seen at" the system it was seen in.

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
- **From the Materials tab:** a material you are short of offers **⇄ nearest raw trader** (or manufactured, encoded):
  it opens the finder with that trader asked for, and leaves your own saved filters as they were.
- **By voice** (the Android app): "nearest station", "nearest carrier", "nearest Vista", "nearest cartographics",
  "nearest repair", "nearest refuel", "nearest shipyard", "nearest material trader", "nearest raw material trader" (or
  manufactured, encoded), "where can I dock", "where can I sell". The voice uses the DSSA list Outrider already has; it never fetches it.

<p align="center">
  <img src="../images/nearest-dssa.png" alt="A DSSA carrier in the list: its badge, how long it is stationed, and when it was last seen docked" width="900">
</p>

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
