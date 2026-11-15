[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)

# Plot Route

The **Plot Route** tab plots a route with [Spansh](https://spansh.co.uk), then follows it as you fly: the next stop
in the tab, under the tiles and on Now, its name on the clipboard and a 🎯 to target it. It plots the Neutron Highway,
survey routes, sweeps, trade routes and carrier trips. Following a route needs no network.

Two routes are kept: one Highway route (Exact or Neutron) and one survey route (any of the others but Carrier). Each
stays until you plot another of its kind, press **Clear route**, or jump out of the system where it finished. A
carrier trip is kept apart from both.

<p align="center">
  <img src="../images/highway.png" alt="The Plot Route tab: the jump list, and the route on a map of the galaxy's regions" width="900">
</p>

## 🛣 The Neutron Highway

The Neutron Highway uses neutron stars as boosts. One form serves every plotter, showing the rows each one uses:
Exact, Neutron and the survey plotters take a ship, From and To; Trade starts from a station (no To, no ship); the
carrier trip has fields of its own.

### The plotters

- **Exact** (the default) and **Neutron**: the Neutron Highway, [below](#exact-and-neutron).
- **Road to Riches** (the third plotter), **Exomastery** (the fourth), **Earth-like**, **Ammonia** and
  **Terraformable**: [Survey routes](#-survey-routes).
- **Trade**: [Trade routes](#-trade-routes).
- **Carrier**: [Carrier trips](#-carrier-trips).

A [sweep](#-a-sweep) is plotted from **🧹 Plot a sweep** beside other tabs' lists, and **📍 Nearest…** beside To finds
a [place to dock](#-nearest-place-to-dock).

### The form

- **Ship.** Any ship you have flown, as of its latest Loadout. A ship with no fuel scoop on the exact plotter is
  warned, since its refuel stops are scoopable stars it cannot use. **plot anyway** plots it, and the route's head
  says so after.
- **← destination** beside To fills it with the system targeted in the game (the galaxy map has no copy). Nothing
  is plotted until you press Plot.
- **📋 paste** beside From, To and a trade route's Station fills the field with the name on the **game PC's**
  clipboard (copied from EDSM, Spansh or anywhere). It is for a window that never takes focus (a touchscreen beside
  the game) or the Android app, where typing is awkward.
  - It only fills: nothing is plotted until you press Plot.
  - It shows in the game PC's own browser and the Android app only, not in other browsers on your network. It takes
    only one short line of text: a paragraph or a link is refused.
  - Linux needs `xclip` (X11 or XWayland) or `wl-paste` (Wayland), the same packages that copy the next system.
  - Search's Find a system by name and the Nearby Focus/Lock, Search and Nearest "a system…" boxes have one too.
- **Conservative range** (Exact and Neutron only; off by default): jumps a margin (5 ly, in the **by** box beside it) shorter than the ship's
  range, leaving room for a fuller tank. A neutron jump is shorter by the margin times the supercharge. The note
  beside it says both: "≈ 5 ly shorter jumps, about 20 ly on a ×4 neutron jump".

### Exact and Neutron

- **Exact** (the default) plans every jump with its fuel and refuel stops from your ship's own figures (drive,
  masses, tanks, Guardian booster, engineering) and your cargo.
  - Tick **no neutron boosts** for a route of regular jumps only, with no neutron stars to fly past.
  - Tick **use injections**, **exclude secondary stars** or **already supercharged** as you need them.
- **Neutron** plans waypoints only, from a range, the supercharge (×4, or ×6 with the SCO Mk II) and an efficiency:
  for a ship you haven't flown, or a quick plot.
  - Its **Range** starts at the ship's laden range; type another to override it.
  - For a ship you have never flown, **another ship: type its range** plots from the range and supercharge you give,
    with no ship behind them.

### A system Spansh doesn't know yet

Spansh can only plot between systems it has heard of, and a system you have just discovered may not be one of them.
Outrider then plots from (or to) a system Spansh knows close by, on the way, and puts yours back as the route's first
(or last) jump: "Spansh doesn't know Drojau SL-D a53-5 yet: the route starts with a 12.4 ly jump to Smojooe XY-Z
a1-2".

- That jump's fuel isn't figured. If it is longer than your range, the message says so.
- A destination works the same way when Outrider knows where it is (a system you have visited or bookmarked).
- Road to Riches and Exomastery do the same. A trade route can't, since it starts from a station's market as Spansh
  has it.

### Too much fuel, or too little

A long neutron jump may be in range only with the fuel the plotter expected, and a tank not filled at a refuel stop
may not reach the next one. On arrival, and as you scoop, Outrider burns the jumps to the next ⛽ stop one by one with
the fuel aboard. On the exact plotter's route it burns them all; on the neutron plotter's, only the next jump.

- It says one of: "⚠ too much fuel for the next jump: ≤ 36 t, you have 140 t", or "⚠ fuel won't reach the refuel
  stop: Hwy Stop 42 in 4 jumps · scoop to ≥ 24.3 t, at most 36.0 t" (both limits in one line, from the same sum).
  Spoken once per system.
- At a ⛽ stop itself it only shows how much to scoop ("⛽ scoop to ≥ 24.3 t to reach Hwy Stop 46 in 3 jumps"), since
  you scoop there anyway.
- Not on a route plotted with FSD injections.

## 💰 Survey routes

The survey plotters (Road to Riches, Exomastery, and the Earth-like, Ammonia and Terraformable routes) ask Spansh for
a chain of systems worth stopping at. Their route is kept in the one survey place, which a sweep or a trade route
takes too: one of them at a time, and a new plot replaces it.

### Road to Riches

**Road to Riches** asks Spansh for a chain of systems whose planets are worth scanning (and mapping). It plots from
where you are (or From), with your ship's range and Spansh's own options: radius, number of systems, maximum
distance, minimum value, mapping value, avoiding Thargoid systems, a loop back. (Road to Riches is thshurka's
contribution.)

- **The list** shows each system with what is left to do there, and the bodies by name under the one you are at and
  the next, ✔ scanned and ✔✔ mapped from your journal.
- **The voice** says on arrival how many bodies are worth the stop and the best of them, and once they are done, the
  next system.
- **Not auto-targeted** on its own: a Road to Riches is for stopping, not hurrying past.
- **Loop back to the start:** a route plotted with it ends where it began. Back at the start partway round (to
  refuel, to sell) is the start again, not the end, and Next is the first stop left after the furthest you reached.
- **With a Highway route as well,** a switch above the heading picks which one the tab shows. Only the one plotted
  last copies its next system to the clipboard; once it is finished, the other one copies again.

### Exomastery

**Exomastery**, Spansh's **Expressway to Exomastery**, plots systems whose bodies carry valuable life already
reported by other commanders. It has the same options as Road to Riches but for the mapping value and avoiding
Thargoid-hit systems.

- **Each body** lists its species with their value, ✓ once you have sampled them and ✦ when one would be new to your
  codex in that region.
- **The voice** says on arrival how many species are left on how many bodies and the best of them, and the next stop
  once they are sampled.
- **Codex finds count:** while it is ticked (⚙ Settings, see [Voice and alerts](voice-and-alerts.md#-alerts)), the
  arrival line adds the species new to your codex there ("two would be new to your codex: the best, Frutexa
  Flammasis"), and Next counts them ("3 species to sample there, 2 new ✦").
- It is known life, so first footfall (×5) is unlikely: the values shown are the base ones.

### Earth-like, Ammonia and Terraformable

Three more plotters ask Spansh for a chain of systems with Earth-like worlds (🌍), ammonia worlds (🧪) or terraformable
rocky and high metal content worlds (🪨) nobody has mapped yet. They are Road to Riches limited to those kinds of
planet, as Spansh's own pages plot them, with the same options but for the minimum value and the mapping value.

- **Terraformable** asks only for the terraformable ones, worth about 460 thousand or more mapped. Spansh's own rocky
  and HMC page lists every plain rocky body too, worth a couple of thousand.
- These worlds are worth mapping, so a body is done once it is scanned and mapped.
- Followed like Road to Riches. The end is "Earth-like route complete." (or "Ammonia route complete.",
  "Terraformable route complete.").

### What these five routes do

- **Nothing to visit:** when Spansh finds nothing (from inside the bubble, Sol or Lave, it answers the start system
  alone), the plot is refused with what to change: "Spansh found nothing to visit with those settings: try starting
  further out from the bubble, a larger radius or a lower minimum value". The world routes leave out the lower
  minimum value: they have none to lower.
- **Finished systems are passed over:** systems ahead that you have already finished (an earlier trip, or out of
  order) are skipped, and the next stop is the first one with work left: "Next: Pru Aim XY-Z d1 · 3 jumps · 6 of 22 ·
  skipping 2 done". Hover for their names. The jumps count from where you are, through the systems passed over.
  - The voice says "Next stop: Pru Aim XY-Z d1, skipping 2 systems you've finished."
  - The route's last system is never passed over: arriving there ends it.
  - A sweep or a trade route never skips a stop.

## ☑ A sweep

A sweep is one trip to systems you tick in other tabs, put in the order to fly them by Spansh's tourist router.

- **Tick systems** in **Left behind**, **My firsts** (with show lost: the systems whose data was lost),
  **Bookmarks**, **Search**'s results or the Bio/Geo checklists' **🔍 nearby** lists. The ticks are one set across
  them, kept until the page reloads.
- **From a checklist,** tick a body for each species you are missing, then plot one trip to them all. The route's
  stops don't say which body or species each was for.
- **🧹 Plot a sweep (N)** beside any of those lists plots it, from where you are with your ship's range, and Plot
  Route shows the route.
- **On each arrival** the voice says the next stop, and "Sweep complete." at the last.
- **A system Spansh doesn't know yet** (a fresh discovery among your lost firsts, say) is left out, and the plot's
  message and the route's heading name it.
- A sweep takes up to 100 systems and replaces the survey route there is.

## 💱 Trade routes

Plot Route's **Trade** plotter asks Spansh's [trade planner](https://spansh.co.uk/trade) for station-to-station hops
from the station you are docked at. It takes the [survey place](#-survey-routes): one route there at a time. Selling and buying what you carry are under
[Trading](cargo-and-trading.md#-trading).

- **The plot** uses your credits and hold (from the journal) and its options: hops, hop distance, distance from the
  star, data age, pad, planetary and player-owned stations, prohibited goods, permit systems, unique stops (no
  station twice). It can take a few minutes to plot.

<p align="center">
  <img src="../images/trade.png" alt="Plot Route with a trade route: each stop with what to sell and buy there, and the route on the map" width="900">
</p>

- **Following it:** each stop lists what to sell and buy there, the hop's profit and the total so far.
- **On arrival** the voice says where to dock and what to trade. Your sales and purchases there count towards each
  commodity's tonnes ("60 of 100 t" until it is all traded), from your journal, matched by the game's id in any
  language. Then it says the hop's profit and the next stop (its own alert, Trade route).
- **Undocking with only part traded** (the station had less than Spansh said) moves on: the voice says what fell
  short instead of the profit.
- **💱** in the line under the tiles, with 🎯 on the next system.

## 🚀 Carrier trips

The **Carrier** plotter plans your fleet carrier's trip with Spansh's carrier router. It is planning only: the game
books one carrier jump at a time, so you still set each in the carrier's galaxy map. It never replaces your ship's
route, and 🎯 never targets it.

### The form

- **Its own fields:** the depot, the tritium in the hold and the cargo in use (filled in from your journal, all
  changeable), the carrier's type, **To me** (your system as the destination) and **+ via** for a stop on the way.
- **The depot field's hover** says when the depot was read. It moves only when you open the carrier's management
  panel. The field gets a red edge once the reading is over a week old, and the trip's head says it too ("· depot
  read 3 d ago").
- With no depot read yet and none typed, the plot is refused: "open the carrier's management panel once".

### The plan

- **Folded under the form:** each leg with its light years and tritium, and what to do first ("move 300 t from the
  hold into the depot first", "buy 400 t here").
- **At the top:** the legs, the tritium needed against what you have, and about how long the legs still to go take
  ("about 2 h to go"). That is 20 minutes a leg, the countdown and the cooldown; longer in busy systems; none once the
  trip is done.

### Following it on the Carrier tile

- **The line:** "Leg 2/6 → the next system 📋 · departs 12:30 ✕". 📋 copies the system to paste in the carrier map
  (only when you click it).
- **After a jump** the line counts the cooldown down, then says **ready**. It says **ready?** when you are away: only
  the booked jump says the carrier moved, and a busy system can delay it.
- **A jump onto a later leg** skips ahead. One anywhere else says "off the trip", with **re-plot from here** (from the
  depot as it is now, without a via already passed).
- **✕** ends the trip, and the last leg ends it.
- **The Quartermaster** says "Carrier ready to jump. Next leg: …" when the cooldown should be over (the **Carrier
  trip** row in Settings → Alerts), and adds "Leg 3 of 6, 3 to go" to the carrier's arrival line.

## 🧭 Following a route

Outrider follows the route from your journal as you fly: each arrival moves you along, and the next stop shows in the
tab, in the line under the tiles and on Now.

### The list

- **The list** shows the next 200 jumps with distance, ⚡ neutron, fuel and ⛽ refuel stops. Refuel stops are the
  exact plotter's: the neutron plotter has none, so scoop as you go. Click a name to copy it.
- **The map** beside it draws the route on the galactic regions with landmarks and your carrier. You can put your own
  galaxy image under it (`background_image`, an EDAstro chart say).

### Following

- **Arriving at any route system** moves you along, forwards or back.
- **Anywhere else** (a respawn included) is **Off Route: Detour** until you are back on it, with the closest route
  system marked.
- **↻ Re-plot from here** plots the same route again from where you are: the same plotter and options, the ship you
  fly now and its own neutron boost. A neutron route plotted from a typed range keeps that range.
- **The same button** shows when the route was plotted for another ship than the one you fly ("plotted for your
  Krait; you fly the Anaconda: its fuel stops and warnings don't apply").
- **Time left:** the route's head says how long the jumps left take at this login's pace ("about 1 h 40 at your
  pace": the median gap of your last jumps, breaks left out). The status report says it too.

### The route line under the tiles

The line under the tiles, on every tab and on Now, shows the next stop of whichever route the tab shows: 🛣 the
Highway, 💰 Road to Riches, 🧬 Exomastery, 🌍 Earth-like worlds, 🧪 ammonia worlds, 🪨 terraformable worlds, 🧹 a
sweep, 💱 a trade route. Its "Next:" comes after the galaxy map's **waypoint** marker: "🛣 Next: Hwy Stop 38 · ⚡
neutron · 4.2 ly · 38 of 399 · refuel in 3 jumps".

The **In-Game Route:** line above it is the game's own route, the one plotted in the galaxy map (see
[the route lines](views.md#-the-route-lines-and-the-plotted-route-pane), which also covers Nearby's **🛣 Show route**
for the systems ahead on either route). It can differ from Outrider's until 🎯 targets the next stop, which has the
game plot its route there.

### Permits, the clipboard and the voice

- **Permits.** Each Highway route (Exact or Neutron) is checked against Spansh's records. A stop or destination that
  needs a permit is marked 🔒, and the head says so ("Sol needs a permit you may not have: the route ends there").
- **Clipboard.** On arrival the next system's name goes on the desktop clipboard for the galaxy map, on the game PC
  only. Linux needs `wl-copy` or `xclip` (see [Clipboard and window tools on Linux](install.md#clipboard-and-window-tools-on-linux)); on Windows it is built
  in.
  - A screenshot set to go on the clipboard ([Screenshots](automation.md#-screenshots)) takes its place; the next
    arrival copies the next system again.
- **The voice:** "Next Neutron Highway Stop: Hwy Stop 38, with three jumps left to refuel. Boost your FSD to
  continue.", plus refuel stops, detours, "Back on the highway", "Highway complete" and the fuel warning.

### Last scoopable star

On any route Outrider follows (the game's plotted route too, and a survey route's legs), it warns at a scoopable star
when the stars ahead can't be scooped and you have not enough fuel to get past them. It warns once each time you
arrive there: "The next 3 stars on your route are not scoopable. This is your last chance to top off before you need
to call the Fuel Rats."

- The In-Game Route line (else the route line under the tiles) and Now show "⛽ last scoop before 3 dry" with how much
  to scoop.
- Only stars known not to scoop count: the game's star class, a neutron on the route, Spansh's record.
- Not while you are scooping.
- On an exact-plotter route the [refuel-stop warning](#too-much-fuel-or-too-little) says it instead.

### A finished route clears itself

A finished route clears itself when you jump out of its last system, so the next plot starts clean. This is so for any
route: the Highway, Road to Riches, Exomastery, a sweep, a trade route. Until then it stays, marked complete.

## 🎯 Targeting and auto-target

A 🎯 targets a system in the galaxy map for you. The page draws it as the galaxy map's own **destination** marker, in
the text's colour (🎯 in these notes and in notifications).

- **On a route,** a 🎯 sits beside the next system and beside every system in the tab's lists. Outrider brings the
  game to the front itself where it can, else 🎯 runs after a 5 s countdown to click back into the game. On the
  tablet, the row's sheet has **Target**.
- **The Carrier tile** has the same 🎯 beside your carrier's system while it is elsewhere.
- **A boxel's** Next and its rows have one too (see [Boxel exploration](exploration.md#-boxel-exploration), whose
  opt-in **auto-target the next on arrival** uses the same run).

### Where a 🎯 shows

Every 🎯, wherever it is, follows one rule: it shows only on the game PC and only when auto-target can work there.
That means the virtual keyboard open and every key it needs bound; whether **Auto-target after a supercharge** is
ticked does not matter.

Anywhere else there is no 🎯 at all, rather than a button that cannot work: on a server, without the keyboard, or
while the box below lists a missing binding. Then **target next** in the box is greyed out too, and a failed row gets
no ⟳ Retry.

### 🎯 and Plot route anywhere

- **A 🎯 also sits** beside each bookmark, the header's next stop, the Nearest finder's rows, Search's results, the
  Exo-Biology, Geology and Phenomena checklists' "🔍 nearby" rows, and Now's nearest catalogued sight.
  - It sits beside a mining session's place and each ring of Hotspots in CMDR → Sessions (never your own system).
  - In Nearby it sits left of each system's name (the Overview's too, in a column of their own).
- **Plot route** beside a bookmark or the next stop (or on the Map's tapped card) puts the system in To and opens the
  form. It plots at once when you follow no route. With one, it waits for your Plot: a new plot replaces the route
  you follow.
- **A click on a system in the Map tab** targets it the same way when auto-target can work on this PC, else copies its
  name (see [the Map](views.md#-map)).

### Is the right system targeted?

The route line (under the tiles, on Now and in the tab) checks what the game has targeted against the next stop:

- "✓ targeted";
- "⚠ targeted Ossia, not the next stop Pru Aim XY-Z d1";
- for a later stop of the same route (on purpose, say to skip one): "↷ targeted Ossia, 2 stops ahead".

A route plotted in the galaxy map counts by where it ends. A wrong target is said once, after you close the galaxy
map: "You've targeted Ossia. The next stop is Pru Aim XY-Z d1." It has its own alerts row, **Not the next stop
targeted** (spoken, no notification by default). It is never said while you are off the route, for a later stop, or
for a body or station in the system you are in. The overlay's Target panel shows the same check.

### Auto-target

**Auto-target** is the tab's **Auto-target the next system** box: Linux, Windows experimental; on the game PC only;
off by default. After an FSD supercharge in a route system it waits 5 s, then presses keys to make the next route
system your target. It opens the galaxy map, searches for the system, plots the route, closes the map and checks the
target took. It says "Successfully targeted neutron jump target Hwy Stop 38" (or "Failed to…") under its own alerts
row.

- **Keyboard bindings:** Galaxy Map Open, UI Up, UI Select and the galaxy map's Camera Yaw Right and Camera Zoom Out
  need one. The box and Settings → Auto-target list any missing; a built-in preset can't be read.
  - Galaxy Map Open is read from the preset your Ship controls use, the UI and galaxy map camera controls from your
    General Controls' preset (the game lets the two differ).
  - It shares auto honk's virtual keyboard; honk goes first.
- **Stopping:** switching it off, clearing the route or plotting a new one stops a run at once, even mid-way. It stops
  if anything unexpected happens, closing the map only if it opened it.
- **A wrong system:** if the game targets a different system it says so by name ("Targeted the wrong system: ….
  Check before you jump."). A waypoint the game reaches by a plotted route of several jumps counts as targeted.
- **When it never runs:** docked, landed, in a vehicle or on foot, in danger, with the FSD charging or a panel open,
  nor while another commander plays ([Two commanders on one PC](install.md#two-commanders-on-one-pc)).
- **Danger after a jump:** the game flags you "in danger" for every jump, and on entering supercruise, until some
  16-26 s after. Pressed in those seconds, it says so ("Not targeting due to danger. I will keep trying until you are
  out of danger, for up to 55 seconds"), waits for that to clear and then runs. That is up to a minute after the jump
  or the supercruise entry; being interdicted is never waited out.
- **Once the route is plotted** you can start the FSD charge without waiting for its last check: the target is set,
  so that counts as targeted.
- **It brings the game to the front itself** before the keys, and presses no key unless Elite is the active window
  (checked before every key): click into the browser mid-way and it stops at once. The box says whether this works,
  or why not.
  - This needs **`wmctrl`** and `xprop` on Linux (`sudo apt install wmctrl x11-utils`, as for the
    [overlay](overlay.md)). It works with the game under X11, and under XWayland on a Wayland desktop (tried on GNOME;
    KDE Plasma should work, untried). On Windows it is untried.
  - When the game does not come to the front, 🎯, Target next and Test now count down 5 s instead ("Elite is not the
    active window: click into the game", or "no game window found" when there is none to bring forward) and still
    check before the first key. The automatic run and the co-pilot button's say so and press nothing.
  - With `wmctrl` working but no game window to be found (the game has crashed, or runs as a native Wayland window,
    Proton's Wayland driver): no key at all, "no game window found".
  - Where nothing can look for the window (no `wmctrl` or `xprop`; Sway, Hyprland and window managers that refuse
    focus stealing ignore it): the 5 s countdown as before, and then **the keys go to whichever window has focus**.
    Stay in the game until it is done.
- **The log** gets one line per run ("highway auto-target: targeted Hwy Stop 38"). Every step is printed when a run
  fails, and for every ▶ test now, each with the key it pressed ("5 plot the route: hold Space … for 1 s: done").
- **🎯 Target next** does the same on demand, whether or not auto-target is on. It is in the box, beside "Next:" in
  the route line under the tiles (on every tab) and on Now. It targets the next route system, or off the route the
  closest one: at once when it brings the game to the front, else after a 5-second countdown to click back into the
  game. A failed run puts **⟳ Retry** on its route row.
- **Test now** in the box targets the nearest known system a plain jump away, the same way.
  `python3 -m outrider.target --show` prints the steps with your keys.

### Setting up the steps

**Settings → Auto-target** holds the galaxy map's steps, and **every 🎯 uses them**, not only the Highway: a
bookmark's, Nearby's, Search's, the Map's, a checklist find's, the header's next stop, the boxel's Next and the
co-pilot button's tap.

- **Also there:** the Highway's **Auto-target after a supercharge** switch and delay (the same as this tab's), a
  **dry run** box (the steps logged, nothing pressed), and **your own keys** for a control whatever your controls
  preset says (`{"UI_Select": "KEY_SPACE"}`).
- **Always done:** opening the map, entering the name, closing the map and checking the target.
- **Yours to change,** each with **↺ default** to put Outrider's own back: **into the search field**, **submit the
  search** and **plot the route**, with the timings and whether the name is typed or pasted.
- **Typed or pasted:** a line under the choice says whether each can work on this PC. Typing presses US key
  positions, so another keyboard layout should paste; on GNOME only `xclip` leaves the game focused.
  - A pasted name that finds nothing is typed once more: the clipboard can come out empty.
  - Pasting the name (also how it enters a name a US keyboard layout can't type) needs the clipboard: `xclip` (used
    first, where there is an X display) or `wl-copy` on Linux.
- **The timings:**
  - **pause between keys** (0.25 s) follows every key of the three parts, since the galaxy map can miss a key pressed
    straight after another. So no `wait` is needed between keys.
  - **typing delay** is only between the name's characters, when it is typed.
  - the **search wait** (3 s to start) grows by a second for each 200 ly to the system, up to 7 s: the map's flight
    there is longer, and a close jump needs less.
- **Save the steps** writes them into the config file (`[highway] autotarget_search`, `autotarget_submit`,
  `autotarget_plot`…), and the next run uses them, no restart needed. A step it cannot read is refused in words, and
  your text stays to be corrected.
- **Below them:** the whole sequence with your keys, and **▶ test now**. It runs against the system typed beside it,
  or, left empty, the nearest known system a plain jump away. A short name such as `Sol` lists several systems: a good
  test of the submit steps. A far one plots a route there, so clear it afterwards.
- **Macro cheatsheet ↗** at the top of the section opens, in a new tab, everything the boxes take: the commands, each
  game control with what it does in the galaxy map and (on the game PC) the key it is bound to, `Enter` and `Paste`,
  every keyboard key by name and the short forms (`KEY_` optional, any case, `alt`, `ctrl`, `shift`, `+` for keys
  pressed together).
- **Steps** are `press <key>`, `hold <key> <seconds>` or `wait <seconds>`, one per line. A key is one of the game's
  controls (`UI_Select`, `UI_Up`, `CamZoomOut`…, in any case), `Enter`, `Paste`, or keyboard keys such as
  `KEY_LEFTALT+KEY_T`.
- **The submit steps** run while the cursor is in the search box, where a control bound to a letter key types that
  letter into the box (UI_Down on **S** types "S"). So they need keys that type nothing.
  - The default is `wait 1.5`, `press KEY_DOWN` (the arrow key by name: into the results list, the first one
    highlighted) and `press UI_Select` (picks it and flies there).
  - It works for a name with one result and for one with several (Sol, Solati…), where Enter only moves the focus out
    of the box.
- **The plot step:** after the search the focus stays in its panel. The default plot moves the camera first (`hold
  CamZoomOut 0.2`), and only then does holding `UI_Select` plot the route. For a system in jump range that route is
  one jump, so the system is simply your target; for one further away the game plots a route of several jumps ending
  there.
- **A route's next stop is targeted, not plotted** (**Target a route's next stop instead of plotting a route to it**,
  on to start), when the route makes it one jump.
  - This is for the Neutron Highway's (after a supercharge too), Road to Riches', Exomastery's and a sweep's next
    stop. Never a trade route's hops, and never any other 🎯: a far system needs a route.
  - Its own box, **5 · target the system**, presses the system panel's **Target System** icon: two UI_Rights reach the
    icon column, eight UI_Downs reach the icon. Where UI_Right or UI_Down has no keyboard key, the stop is plotted.
  - Plotting leaves the route to the game's planner, and **with Use Jet-Cone Boost off in the galaxy map's Route
    Settings it ignores your supercharge**: six jumps where the supercharged one would do. If you switch targeting
    off, tick Use Jet-Cone Boost.
  - Either way a one-jump stop must end up the target itself: a longer route there fails, saying so, rather than
    "targeted".
  - Targeting can close the galaxy map by itself: Outrider waits a moment for that and then leaves the map alone.

### Frontier's rules

This is key-press automation like auto honk (and tools such as Auto_Neutron). Whether to use it is your call.

## 📍 Nearest place to dock

**📍 Nearest…** beside To finds the nearest stations and fleet carriers you can dock at and use, and plots there.

<p align="center">
  <img src="../images/nearest.png" alt="Nearest place to dock: stations and carriers with UC and Vista, nearest first, with their docking and how old each report is" width="900">
</p>

- **Filters,** remembered on this device:
  - stations and/or fleet carriers;
  - what it must have (Universal Cartographics, Vista Genomics, repair, refuel, shipyard);
  - a **material trader**: any, raw, manufactured or encoded (stations only: fleet carriers never have one). Spansh
    says each trader's kind; the few it lists with no kind (some Colonia outposts) count only for "any", shown as
    "⇄ trader";
  - your ship's pad size (from its type; a small ship fits every pad);
  - **Data under** N days (30 by default);
  - permit systems, left out unless ticked;
  - **Around**: you, your destination in game, your carrier, your next stop or a system you name. The distances are
    from there (a row's hover says how far from you) and there is no jump count.
- **Each row shows** how far it is (and a rough jump count), how far from its star (far ones marked), what it has,
  its pads, its docking, and where the report came from and how old it is.
- **Plot here** puts the system in To and plots it with the plotter chosen above (Exact when Trade or Carrier is
  chosen). Following the route works as usual.
  - A place in your own system says "here" instead ("aboard" for the carrier you are docked at).
  - Where auto-target can work, a **🎯** beside it targets the system in the galaxy map.
- **Docking:**
  - "yours" for your own carrier, "your squadron's" for your squadron's carrier (no warning: you may dock there),
    "open to all". A carrier whose callsign is four characters (a squadron's tag) is listed as a squadron carrier.
  - A **⚠ warning** for carriers set to friends, squadron, or squadron and friends only (Outrider cannot see the
    owner's list), for those closed to visitors, and for those with no docking setting reported at all.
  - A DSSA carrier last seen away from its post gets "last seen at" the system it was seen in.
  - None of these are hidden: the warning is there so you can decide.
- **Where the data comes from:**
  - [Spansh](https://spansh.co.uk) for stations and carriers, as players last reported them. A carrier is only where
    someone with an uploader last docked: that is why every row says how old its report is, and why older reports are
    hidden (raise Data under to see them).
  - The **[Deep Space Support Array](https://inara.cz/elite/squadron-about/13586/)'s** carrier list, as
    [EDAstro](https://edastro.com) publishes it. These are carriers stationed for years in the black for explorers,
    open to all, each marked **🛰 DSSA** with how long it stays. The list is fetched only when you open the finder, at
    most once an hour, and only downloaded when it has changed. The last copy is kept, so the finder works offline.
  - Your own carrier, and your squadron's, from your journal (your squadron's name and services from Spansh too).
- **From the Materials tab:** a material you are short of offers **⇄ nearest raw trader** (or manufactured,
  encoded). It opens the finder with that trader asked for, and leaves your own saved filters as they were.
- **By voice** (the Android app): "nearest station", "nearest carrier", "nearest Vista", "nearest cartographics",
  "nearest repair", "nearest refuel", "nearest shipyard", "nearest material trader", "nearest raw material trader"
  (or manufactured, encoded), "where can I dock", "where can I sell".
  - A place further than 500 ly also gets a neutron route plotted there, unless you are following a route ("You're
    following a route, so I didn't plot one"). `[highway] voice_plot` switches it off, `voice_plot_ly` sets the
    distance (Settings → Server).
  - The voice uses the DSSA list Outrider already has; it never fetches it.

<p align="center">
  <img src="../images/nearest-dssa.png" alt="A DSSA carrier in the list: its badge, how long it is stationed, and when it was last seen docked" width="900">
</p>

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · **Plot Route** · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)
