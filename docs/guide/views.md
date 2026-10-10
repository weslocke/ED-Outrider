[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · **The views** · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# The views

## 🖥️ The views

<table>
<tr>
<td width="50%" valign="top">
<b>Nearby</b> — every known system within range (20–50 ly, the Where tile's dropdown): distance, how much
is scanned, the main star and whether it scoops, notable bodies, curiosities (🔭) and a credit estimate. Sort,
or hide visited and fully scanned systems. A dashed <i>old data</i> mark flags Spansh records from before
Odyssey (thin-atmosphere planets there may hold unsampled life). ⛏ N counts planetary mining locations on
ground worth a Rhino.
<br><br><img src="../images/nearby.png" alt="Nearby systems">
</td>
<td width="50%" valign="top">
<b>Here</b> — the current system body by body: values, bio and geo signals, 🌋 volcanism, and before the
DSS the genera each bio signal could be. Hover a body for a summary, click it for everything, with a picture of
it drawn from its scan data (an impression: class colours, bands, clouds, atmosphere, rings, size). ⛏ gives a
community survey's mineral odds for that ground (odds, not contents) and what your SRV mined there before.
The to-do line ticks itself off as you honk, map and sample, in a suggested order with supercruise time and
credits per minute ("~2 min · 450k/min"; "skip?" when not worth the trip). Bio nobody has set foot on is
valued with the ×5 first-footfall bonus, except in a populated system: Vista Genomics never pays it there.
A footer under the list says what each icon means, for the icons that system's list shows (none, no footer); it
stays in view while the list scrolls.
"🧬? check in the FSS" marks a landable body you have only from an AutoScan or a nav beacon, whose signals nobody
counted, where life is possible. The body panel lists why each other genus is not expected ("pressure too
low"). Flying low over a body in your ship (under 5 km), the on-body strip already shows its bio card. A star's
panel says its kind in words ("main sequence", "white dwarf (hydrogen-rich)"), a biology codex entry links to
Canonn's Bioforge (where it grows, and in what conditions), and **⬇ CSV** in the heading saves the system's bodies
and values as a spreadsheet.
<br><br><img src="../images/here.png" alt="The current system">
</td>
</tr>
<tr>
<td width="50%" valign="top">
<b>Map</b> — a 3D view: left-drag to rotate, right-drag to move, scroll to zoom. Your path in orange,
your first discoveries in gold, visited systems in blue (by touch: one finger rotates, two move, pinch zooms); tick <i>boost stars</i> for neutron stars and
white dwarfs.
<br><br><img src="../images/map.png" alt="The 3D map">
</td>
<td width="50%" valign="top">
<b>History</b> — sessions (jumps, light-years, discoveries, mapping, samples), an all-time row, "since
your last sale" and the game's career statistics. Below: every trip from sale to sale with what it paid
against Outrider's estimate, the exobiology ×5 checked against the prediction, credits per hour and per jump,
what each death cost, and your 25 most valuable finds.
<br><br><img src="../images/history.png" alt="History">
</td>
</tr>
<tr>
<td width="50%" valign="top">
<b>Bio/Geo</b> — <b>My Samples</b>: every exobiology sample run: species, variant, body, value, and whether it is
<i>aboard</i>, <i>sold</i> or <i>lost</i>. Filter, sort, export; codex entries underneath. Unsold runs are
priced one by one ("x5 on 42 of 47 runs"). Beside it, the <a href="#-the-exobiology-checklist">Exo-Biology and Geology
checklists</a>.
<br><br><img src="../images/samples.png" alt="Bio/Geo: My Samples">
</td>
<td width="50%" valign="top">
<b>Log</b> — every journal event, newest first, one readable line each. Filter by category and time,
search any text, click a row for the raw event.
<br><br><img src="../images/log.png" alt="The log">
</td>
</tr>
<tr>
<td width="50%" valign="top">
<b>Materials</b> — your <b>Cargo</b> (the ship's hold and your carrier's, with Sell and Buy: see <a href="cargo-and-trading.md">Cargo and trading</a>), materials against their caps, and how many FSD injections, limpets, SRV refuels and
repairs and Rhino rig restocks you can make now. <b>Mining sites</b> lists each body your SRV mined: minerals
and tons, saved spots, the last date and the distance.
<br><br><img src="../images/materials.png" alt="Materials">
</td>
<td width="50%" valign="top">
<b>Schematic</b> — Here switches between <i>list</i>, <i>tree</i> (orbital order) and <i>schematic</i>: stars
with their planets left to right, moons underneath, barycentres boxed, each scanned body drawn from its scan data (as
in the body panel: class colours, bands, oceans, clouds, atmosphere, rings). <i>Split</i> (on by default)
keeps the schematic under the list or tree.
<br><br><img src="../images/schematic.png" alt="The system schematic">
</td>
</tr>
<tr>
<td width="50%" valign="top">
<b>Search</b> — systems with particular stars (or just <i>scoopable</i>), planets, rings, hotspots,
unfinished exobiology or planetary mining locations (one mineral, if you like) within a radius, from what
Outrider knows (<i>Local</i>) or everything reported (<i>Spansh</i>). The name box finds any system and opens
it in Here, where ☆ bookmarks it or makes it the next stop.
<br><br><img src="../images/search.png" alt="Search">
</td>
<td width="50%" valign="top">
<b>My firsts</b> — visited systems with first-discovery data you haven't sold. The <b>firsts watch</b>
checks them on Spansh in the background and marks any someone else has scanned since you ("👁 8 d after you");
selling first still keeps your name if nobody sold before you. <b>Show lost</b> with <b>within N ly</b> is a
rescan checklist for data lost with a ship, nearest first, priced by what is left to scan and map. <b>Left
behind</b> lists nearby systems with work over your thresholds; <b>Bookmarks</b> hold notes and your <b>next
stop</b>.
<br><br><img src="../images/firsts.png" alt="My firsts">
</td>
</tr>
</table>

The **Overview** at the top shows Here and Nearby together: drag the divider, swap sides or stack them.

On a window of at least about 900 × 600 the page fits the window: the header stays put and each list scrolls
in its own box. **▴** folds the tiles into one line (remembered on this device; Settings → Display can fold
them only on a small window). A table too wide for its box
switches to short forms ("HMC", "G star"; hover for the full text) rather than scroll sideways.

**Themes.** ⚙ Settings → Display → **Theme on this browser** dresses the page in one of the tablet's themes: LCARS,
Elite, Babylon 5 (Earthforce, Narn, Minbari, Centauri), Sith, Rebel Alliance or Dark, each with its colours, its
lettering on the title, tabs and labels, and its shapes. **Default - Outrider** is the look above, and the only one that
follows your system's light mode. Each browser keeps its own choice, and the tablet has its own.

<p align="center">
  <img src="../images/themes.png" alt="The desktop page in four themes: LCARS, Elite, Minbari and Centauri" width="900">
</p>

**Now** is the cockpit view for a second monitor or a tablet, in big text: the system, the target, fuel,
what to do next, the body you have targeted, and the nearest unvisited system. The target says how much of it is
known ("3/12 known", Spansh's bodies of its count) and what EDSM has ("EDSM 5/12", or "not logged"): two databases
with different reporters.

- An **at-risk line** shows what is aboard against your rebuy ("🗺 380M · 🧬 412M aboard · 3.2× rebuy").
- **This session** since your login: "2 h 14 · 74 jumps · 612 ly · 6 new systems · 11 mapped · 4 samples ·
  ~38.0M found" (the unsold estimate's change plus what you sold). After you quit, the last session.
- **Captions** show the last three lines said; tap one to hear it again. A corner bar has 🗣, hush 30 min,
  status report and ✕ back.
- **↗** beside the Now button opens Now in its own window, or open `http://127.0.0.1:8025/?mode=now`,
  which stays on Now even after a stray click or a reload.
- It keeps the screen awake on localhost or HTTPS. On a tablet over plain http, set its screen timeout.
- On a planet, the **surface map** appears under the lines (see below).

The **header** shows the galactic region, ranks, fuel, hull, any core module under your level (`module_warn`,
80%; as of the last Loadout or repair, since the journal logs nothing in between), your carrier's jump countdown
(and its tritium while it is on a sell order: see [Cargo and trading](cargo-and-trading.md)), the nearest places to
sell, and the last backup.

The **fuel tile** counts jumps as the ship gets lighter ("≈6 jumps at max range (484 ly), 3,500 at your pace"),
for any drive, engineered or not, from your own Loadout and jumps. Nearby shows laden range and the targeted
jump's cost ("38.2 ly · 0.9 t · leaves 5 max jumps"). "scoopable: 9 of last 20" turns amber when your fuel is
short for the gaps between scoopable stars. In the SRV or the Nomad it keeps the ship's tank and adds the
vehicle's own fuel.

Under the Where tile, the **discovery streak** is a dot per arrival for your last 20 (gold: first discovery,
amber: bodies nobody had reported, blue: known, grey: revisited), and the **unreported horizon**: "nearest
known unvisited: Xyz 4.8 ly". Any unvisited star closer than that on the galaxy map is one nobody has reported.

## 🧬 The exobiology checklist

**Bio/Geo → Exo-Biology** shows every species the rules know, one box per genus, for a galactic region: where you
are (the default), any other, or **All regions**. Each species shows your best there, in colour:

- <b>sold</b> (green), <b>aboard</b> (amber: sampled, not sold yet), <b>lost</b> (red: sampled, lost with the ship),
  <b>logged</b> (blue: in your codex, no finished run);
- *elsewhere*: none here, but you have found it in another region (the line above the boxes counts them);
- greyed: not here, the rules say it cannot grow in this region. That is the rules' prediction, not proof that
  nobody has found it there;
- ◐: only in parts of the region (near Guardian sites, in tuber zones, by nebulae);
- a green **✓** beside a genus: complete there, every colour of every species that can grow in the region found;
- the colours you have found out of those it comes in (**3 / 12**). Anemones, brain trees and the like are their own
  one colour.

Click a species to drop its colours down under it, each with what gives it ("Teal: M stars", or a material on the
body for some bacteria) and your state; click it again to fold them up. The column beside the boxes shows its
picture and a map of the galaxy with the regions it can grow in lit and your samples as dots; hover a lit region
for its name and your completion there. The line above the boxes counts it up: "Inner Orion Spur: 45 of 101 possible species found ·
11.70% complete for the species in this region · 43 sold · …".

**Completion** counts what you have done, not only what is finished: each species that can grow in the region scores
the share of its colours you have found there (sold, aboard, lost or logged), averaged over those species, so half of
every species is 50% with none complete. The region list shows each region's figure. The tablet's Bio/Geo page has it
all too, with the species and a species' details scrolling separately.

<p align="center">
  <img src="../images/checklist.png" alt="The exobiology checklist: genus boxes with each species' state and colours found, and a species' colours and galaxy map beside them" width="900">
</p>

**Bio/Geo → Geology** is the same for the codex's **Geology and Anomalies** entries: fumaroles, gas vents, geysers and
lava spouts, then Lagrange clouds and the lettered anomalies. Each is logged in your codex for the region, or not;
beside it, how many sites players have reported in that region (from [Canonn](https://canonn.science)), greyed where
none have been reported yet (which is not to say there are none). Completion is the share of the entries reported in
the region that you have logged. Click one for its picture, its sites in the galaxy, where you logged it, and the map
of the regions it has been reported in.

The pictures are [Canonn](https://canonn.science)'s screenshots, each credited to the commander who took it: Outrider
links to them (they load from Canonn when you open an entry; click one for full size) and keeps no copy. Click a
colour under a species for that colour's picture. A few entries have none yet; Outrider asks Canonn for its latest
list once a day, so new pictures appear as they are added.

Journals from before a 2023 game update don't name a sample's colour, so those samples count the species but not a
colour.

## 🗺️ The surface map

On a planet, Now shows a map under its lines: on the ground, in the SRV, on foot, or flying below 1,000 m
(it hides again 100 m higher). Hiding deletes nothing.

<p align="center">
  <img src="../images/surface.png" alt="The surface map on Now: rigs, samples, a mining location and the ship" width="900">
</p>

- **Heading-up:** the way you face is the top, you are the arrow in the middle, N on the rim is north. It
  zooms to fit everything within 3 km, never narrower than 500 m, with a scale bar.
- **What is drawn:** your ship (a landing-pad H), the samples of unfinished bio runs with each species' colony ring (the
  current run solid), plants you tagged (below), your rigs 1–6 with a faint spacing ring, saved sites (U1…
  unmarked, S1… rigs picked up) and mining locations (L3). Anything off the map is a chevron on the rim.
- **Tagged plants** (as BioScan's waypoints): point the composition scanner at a plant, from the ship flying low,
  the SRV or on foot, and Outrider remembers where it is, as a hollow ring in the species' colour. Faint means a
  sample there would not count (it is inside the colony of one you took). While sampling, the strip says the
  nearest one that would count and which way to turn ("tagged: 524 m, turn 90° right"), and the voice says so
  within 100 m. From the ship or SRV the scanner logs no position, so it is yours at that moment: scan as close
  to the plant as you can. A species you have finished on the body drops its tags.
- **The legend** names each tag, nearest first. Six rig slots mirror the game's HUD: mineral (or
  "placed"), tons so far, distance and bearing. A solid rig is **probably full**: 8 minutes since it was
  placed or last collected from.
- **The leash:** the game destroys a rig 5 km from its Rhino. Past 3.5 km it turns red and the voice warns,
  again at 4.5 km ("Rig 3 is 3.8 kilometres away, behind you; it is lost at 5.": which way, in eight sectors).
- **Strip copy:** a tick in the dialog adds a small copy to the on-body strip, with a one-line legend.

**Marking rigs.** The game logs nothing when you deploy or pick up a rig, so you tell Outrider with the
co-pilot button. In the Rhino on a planet:

- **Tap away from your rigs:** the next rig (lowest free number, 1–6) is placed 7 m behind you, where the
  game drops it. "Rig 3 placed."
- **Tap within 5 m of a rig:** it is picked up and its number is free again.
- The button does nothing else in the Rhino. Anywhere else it works as usual. Getting out on foot and back in
  keeps it marking rigs.
- **Forgot to tap?** The ✕ by a rig's slot in the legend marks it picked up.
- **Rigs still out:** docking the Rhino with rigs still marked out on the body says so, and a card shows it
  ("Rigs 2 and 5 still marked out; rig 5 is probably full."). It is Outrider's record, not the game's, so a
  rig picked up without a tap counts until you ✕ it.

**Automatic:** collections (the tons go to the rig under you, or an unmarked site, and are said once you
stop: "Rig 3: 12 tons of Water."), your ship's landing spot, mining locations you targeted from the ship, and
rigs lost at 5 km, on leaving the body, or with the Rhino destroyed, a death or a relog. **Not automatic:**
placing and picking up rigs, and what a deposit holds. A rig that collected anything is kept as a saved site
for your next visit and listed under Materials' **Mining sites**.

The map's sizes and the leash distance are in the thresholds table under Alerts; the spoken leash warning
always uses the config file's `rig_warn`.

---

[ED Outrider](../../README.md) · [Install and run](install.md) · **The views** · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
