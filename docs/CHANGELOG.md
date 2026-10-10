# Changelog

Newest first, one entry per commit.

## 2026-10-10 · Overlay O6: the surface radar (branch EDMC-Functionality)
- On a body (landed, in the SRV, on foot) or low over it, as the surface map shows: a heading-up radar from the
  surface summary, you at the centre, N on the rim; the run in progress's sample points with their colony rings (red
  while you are inside one, green once clear), other runs' faint, tagged plants, the ship with its distance, your
  rigs; what lies beyond the edge on the rim in its direction. The edge is `[overlay] radar_range`, widened to fit
  the run's colony ring. Underneath: "Next: 500 m from all · nearest 302 m", or "Clear: sample here".
  The test panels' radar is built the same way.

## 2026-10-10 · Overlay O5: the body panel (branch EDMC-Functionality)
- Flying your ship, the body panel shows the body targeted in game in this system (else the one you are near): landable,
  gravity (amber at your `high_gravity`), atmosphere, temperature; what mapping is still worth, first discovered, geo
  signals; its life: each run under way ("2/3", with the colony distance), each finished species (✓, its value), each
  likely species with its codex mark and colour, colony distance and "up to" value, or before the DSS what it could
  be and pay; and "Worth landing: up to ..." with the ×5 first-footfall note. Landed, in the SRV or on foot it gives
  way to the radar.

## 2026-10-10 · Overlay O4: the system panel (branch EDMC-Functionality)
- In supercruise, the system panel lists what is worth your time in the system you are in, from what Here knows
  (`State.system_detail`, cached on the scan version): each body with mapping or bio left over your levels (the
  config's `body_highlight_level` and `bio_min`), nearest first, as TO MAP, TO LAND, MAP + LAND or a run in progress
  ("Bacterium 1/3") with the credits and the codex mark with its colour ("✪ Lime"); then the valuable ones done
  (MAPPED, SAMPLED); curiosities on an "Also here" line; what is left in the whole system, and how many bodies are
  under your levels. Hidden over the maps, the FSS, the SAA and the codex; `[overlay] system_seconds` limits it to
  that long after arriving.

## 2026-10-10 · Overlay O3: arranging the panels (branch EDMC-Functionality)
- Arrange mode (Settings -> In-game overlay, **Arrange panels**): the overlay window takes the mouse and frames each
  panel. Drag to move it (it is kept from the corner nearest where it lands, so a resolution change keeps it there),
  drag its corner to size it, wheel over it for its background's opacity, Shift and wheel for the whole panel's;
  **Done** at the top (or the page's button) ends it. Edits are sent when the drag ends or the wheel stops.
- Settings -> In-game overlay: the overlay on or off, each panel on or off, the theme and text size, whether an
  overlay window is drawing, Show test panels, Arrange panels, and each panel's corner, offsets, size and the two
  opacities as fields (with a reset).

## 2026-10-10 · Overlay O2: the window on the game PC, and GPL-3 (branch EDMC-Functionality; not to be pushed yet)
- `python3 -m outrider.overlay_window` (PyQt6: `pip install -r requirements-overlay.txt`; never in the Docker image):
  a frameless, translucent, always-on-top window that lets clicks through, follows Elite's window (X11, and XWayland
  on a Wayland session as Elite under Proton is; Windows untried), hides when the game is not in front, and paints the
  panels from GET `/api/overlay` (once a second; signs in to a server with `[overlay] password`). `--render PNG` draws
  one frame into a picture instead.
- Finding the game's window (`outrider/overlay_tracking.py`) and the window's flags are adapted from EDMC Modern
  Overlay (GPL v3), so **ED Outrider is now GPL v3 or later** (LICENSE, README, the Docker label). The README credits
  Modern Overlay, and EDMarketConnector for the upload rules. This commit is not to be pushed before EDMC-ExploData's
  licence is settled (its colour tables ship in resources/bio_rules.json; its repository has only the GPL v2 text).

## 2026-10-10 · Overlay O1: the panels' server side (branch EDMC-Functionality)
- `outrider/overlay.py`: the in-game overlay's panels as draw lists on a 1280x960 canvas (text, rectangles, circles,
  lines, markers), a text-panel builder, test panels, the `[overlay]` settings (enabled, theme, text_size, each panel
  on/off, system_seconds, radar_range; url and password for the window on the game PC) and the panels' layout (per
  panel a corner, an offset, a size, the background's and the whole panel's opacity; meta `overlay_layout`).
- GET `/api/overlay` (with `since=<version>`: just `{same}` when nothing changed), POST `/api/overlay` (the switches,
  written into the config; test panels for 20 s; Arrange mode for at most 10 minutes), POST `/api/overlay/layout`.
  The real panels come in O4-O6; nothing draws them until the window (O2).

## 2026-10-10 · ExploData's colour tables downloaded, not shipped; the README's credits (branch EDMC-Functionality)
- The colour tables (EDMC-ExploData: its repository has the GPL v2 text without "or later", and Outrider is now GPL
  v3) leave the repository: `resources/bio_rules.json` ships with no colours, and they are downloaded on the first
  start into `resources/bio_colours.json` (git- and docker-ignored), merged in when the rules load and refreshed with
  them; a missing colours file makes the rules out of date, so a fresh install or a new container fetches it. If
  ExploData cannot be fetched, the colours already downloaded are kept. BioScan's rules and the region map still
  ship; the colony distances stay in the code, credited to the game (the Genetic Sampler shows them).
- The README's credits are a table: what, from whom, under which licence, and how Outrider holds it.

## 2026-10-10 · The log's first line: the name and version
- Starting the server prints "ED Outrider <version>" first, before the config's reading and its warnings, so a log
  (Docker's included) says which Outrider wrote it. Not for --write-config, --list-backups or --restore.

## 2026-10-10 · Exo-Biology: a green ✓ on a complete genus
- A genus box's heading gets a green ✓ when every species that can grow in the region shown has all its colours
  found (one with no colour table: found at all; All regions asks for every species). Not on Geology (no colours).

## 2026-10-10 · Version 2026.10.20
- Bio/Geo (was Samples): the Exo-Biology and Geology checklists with Canonn's pictures linked; auto-target waiting out
  the game's own danger flag after a jump or supercruise entry (and an early FSD charge no longer a failure); exact
  plots without neutron boosts; plotting from or to a system Spansh doesn't know yet; Here's icon legend and the
  codex marks naming the new colour; bodies already mapped by others not pointed out; the rail's N/A in supercruise;
  Spansh's "Terraformable" priced (CACHE_VERSION 17: Spansh data fetched again as you go); the Fable bug check's
  fixes. No journal re-read. What's new has its section; four screenshots retaken for the legend.

## 2026-10-10 · Docs: the latest changes in the notes, screenshots with the Here legend
- DESIGN_NOTES: the danger wait and the early FSD charge; the Here legend (only the icons shown) and the colour after
  the codex marks. AGENT_GUIDE: target.py's danger wait, and a recipe for a new Here icon (its HERE_LEGEND entry).
  Settings guide: the marks name the colour. overview, here, schematic and themes retaken (the legend).

## 2026-10-10 · Fable review fixes: the page
- The checklist asks for every change (region, list, a scan) and draws only the newest answer: a region picked
  while an answer was on its way was dropped, the picker showing one region and the list another (#6).
- The map reopened while its request was on its way: the older request's failure no longer throws away the newer
  answer ("map failed" over a map that had arrived) (#7).
- The checklist's species rows and picture colour rows are reachable with Tab and open with Enter or Space, and the
  row keeps focus when the list redraws (#8). The map's region tooltip on a tablet tap is left for later (the region
  picker has the same figures).

## 2026-10-10 · Fable review fixes: the checklists
- Bark Mounds: the game and Canonn name it in the plural, the rules "Bark Mound", so a codex entry for it never
  counted on the Exo-Biology checklist (not found, left out of the region's percentage) and its panel had no picture.
  The rules' plural genus name is matched too (#2).
- The status line's "N of M" counts only what M counts: Geology read "3 of 2 entries reported here logged" with an
  entry nobody had reported in the region; now "2 of 2 ... · 1 logged that nobody has reported here yet". The same
  for species found where the rules say they cannot grow, and for each box's "found / possible" (#3).

## 2026-10-10 · Fable review fixes: uploads, the co-pilot button, ExploData
- An Outrider giving way to another for an upload took over when the other stopped (or its lease went stale)
  without looking at where it stopped: what was played between that stop and its next lease refresh (up to a
  minute) was sent by nobody. Taking over now goes back to the other's handover note (or a crashed one's last marks)
  and catches up from there (#1).
- The co-pilot button's second press cancels a Target next that is still waiting with no key pressed (the arrival's
  danger flag, an auto honk), as it did during the countdown; before, it said "auto-target is already running" and
  the keys went down anyway (#4).
- ExploData's genus.py with no `data` table at all (renamed or moved upstream) is a failed fetch, retried at the next
  start, not "no colour variants" recorded as up to date (#9).
- (#5, the danger wait after a restart, is in "Target next: the danger wait after supercruise entry too".)

## 2026-10-10 · The new codex colour is written after ✪ / ✦
- Which colour would be new to your codex ("Bacterium Acies - Cobalt") was only in the mark's tooltip, and that never
  shows: a body's summary pops up over the row first, and the tablet has no hover. The mark now reads "✪ Cobalt"
  (or "✦ Grey") in Here's rows, the body summary and the body panel; Now already names the colour beside its guess.

## 2026-10-10 · Here: a legend for the icons in the list
- A footer under Here's list (the tab, the Overview's pane, Nearby with a system pinned, the tablet) says what each
  icon means: 🔭, ELW/WW/AW, T, ⛽, rings, belts, 🏁, 🗺 (first, or dim: not first), 👣, —, 🧬, 🧬?, n/3, ✓, ✗, ?, ≤,
  ✪, ✦, 📖, 💰, 🪨, 🌋, ⛏. Only the icons the list or schematic shows now are listed, and with none there is no
  footer. It stays in view: sticky to the bottom of the scrolling pane (or the window), below both halves in split.

## 2026-10-10 · Target next: the danger wait after supercruise entry too, and it says it is waiting
- The game sets the in-danger flag on entering supercruise as well (lifting off a planet: logged in game, 16 s), and
  Target next pressed then still refused "you are in danger" (the wait counted only hyperspace arrivals). The window
  now starts at the latest arrival or SupercruiseEntry here; after a restart the saved position's arrival time
  stands in for the arrival, which is not read again (the Fable review of 2026-10-10, #5).
- While it waits it says so once: "Not targeting due to danger. I will keep trying until you are out of danger, for
  up to N seconds" (N: what is left of the minute), then the usual result line.

## 2026-10-10 · Target next waits out the arrival's danger flag
- The game sets Status.json's in-danger flag on every jump, from the FSD charge until some 16-26 s after arriving
  (logged in game: any star, nothing near), so Target next pressed in those seconds refused "you are in danger"
  until it cleared. When that is all it can be (not interdicted, no jump charging, an arrival under
  `AUTOTARGET_DANGER_WAIT` = 60 s ago), the run now waits for the flag to clear and then goes; pressing nothing
  meanwhile. Interdicted, or still in danger a minute after the arrival, it refuses as before.

## 2026-10-10 · Plot a route: exact plots without neutron boosts
- The exact plotter has a **no neutron boosts** tick: Spansh plans regular jumps only (its `use_supercharge` off),
  for a route that never flies past a neutron star. Remembered like the other ticks; the route's line says
  "no neutron boosts" when it was asked for.

## 2026-10-10 · Auto-target: charging the FSD early is no failure
- Starting the FSD charge (or the jump) after auto-target had plotted the route, while it was closing the map and
  before its last check, stopped the run with "an FSD jump started" and said targeting failed, though the target was
  set. Once the map's close key went down, a jump charging, or the system changing, now ends the run as a success
  when the target is the next system (or you arrived there); without a target it is still a failure.

## 2026-10-10 · Screenshots retaken for the Bio/Geo menu
- Every guide image that shows the top menu, taken again (the scratch server, a copy of the database, the journals
  read only): overview, nearby, here, schematic, map, highway (a route to Colonia), history, samples (My Samples),
  log, materials, firsts, search, cargo (the Sell lookup), trade, nearest, checklist (a sold species' colours
  dropped down), the four themes and the tablet (Explore with Bio/Geo, the surface map).

## 2026-10-09 · The Samples tab is now Bio/Geo
- The top menu's (and the tablet's) **Samples** is **Bio/Geo**, and its switch reads **My Samples** (was Runs),
  **Exo-Biology** (was Checklist) and **Geology**: the tab holds the geology checklist too now. Only the words changed
  (the view is still `bio`, your choices and links keep working). The guide, the README and the notes follow; the
  screenshots are taken again with the new menu.

## 2026-10-09 · Exobiology checklist: colours drop down under the species
- Clicking a species drops its colours down under its row in the box (each with what gives it and your state; a
  colour with a picture shows it when clicked), and clicking it again folds them up. The column beside the boxes
  keeps only the species' line, its picture and the map.

## 2026-10-09 · Checklists' pictures: the link list refreshed daily
- The server asks Canonn's codex reference for its picture links once a day (two minutes after a start when its copy
  is missing or a day old; an hour later after a failure) and keeps them in data/codex_images.json, used when sound
  (at least 500 entries) and else the shipped resources/codex_images.json. New pictures appear without a release.
  outrider/codex_images.py holds the parsing both it and scripts/build_codex_images.py use; the tests point its
  cache into a scratch folder.

## 2026-10-09 · Checklists: pictures from Canonn, linked
- A species' and a geology entry's panels show a picture: Canonn's screenshot, loaded from Canonn when the entry is
  opened (never copied), captioned with the commander who took it and Canonn, linked to full size. A species shows a
  colour you have found (else the first with a picture); clicking a colour's row shows that colour's.
- resources/codex_images.json holds only the links and credits (877 entries: 768 of 847 colours, 82 of 88 geology
  and anomalies), built by scripts/build_codex_images.py from Canonn's codex reference. README credits.

## 2026-10-09 · Samples → Geology: a checklist of the codex's Geology and Anomalies entries
- A third Samples view, **Geology**: the 88 entries your codex files under Geology and Anomalies (fumaroles, gas
  vents, geysers, lava spouts, Lagrange clouds and storm clouds, the lettered anomalies), by region: logged in your
  codex there or not (or elsewhere), and how many sites players have reported there, greyed where none have.
  Completion per region is the share of its reported entries you have logged; the region list shows it. Click one
  for its sites in the galaxy, where you logged it, and a map of the regions it has been reported in.
- The data: resources/geo_codex.json, built by scripts/build_geo_codex.py from Canonn's codex reference and its
  per-entry site dumps (each site's region counted). Run it again to refresh the counts.

## 2026-10-09 · Exobiology checklist on the tablet: two scrolling parts
- On the tablet (and in the app) the checklist fills the page, and the species boxes and a species' details with its
  map each scroll on their own (stacked on a narrow tablet, about half each); the page itself no longer scrolls.

## 2026-10-09 · Exobiology checklist: the map names only the regions it grows in
- The species panel's map shows a region's name on hover only over a lit region (one the species can grow in, or in
  parts of); the faint ones say nothing.

## 2026-10-09 · Exobiology checklist: completion by region, region names on the map
- Each region in the list shows its completion ("Dryman's Point — 4.36%"), and the line above the boxes says it for
  the region shown ("… · 11.70% complete for the species in this region"): the average, over the species that can
  grow there, of the share of each one's colours you have found there (any state), so partial progress counts
  (`outrider.checklist.completion`, every region in one pass; `completion` in the table's summary).
- Hovering the species panel's map names the region under the pointer, with whether the species grows there and
  that region's completion.

## 2026-10-09 · Exobiology checklist: the layout, and "elsewhere"
- The genus boxes flow down columns (no holes beside a long box), the species panel is wider with a larger map, and
  a long name ends in … within its box ("not here" ran over the next box: greyed already says it, the tooltip in
  words). A species you have none of in the region but found in another says *elsewhere* (its best there in the
  tooltip), and the summary counts them: a region you never sampled in read all 0 / n with nothing to say you had them.

## 2026-10-09 · Exobiology checklist, part C: the page (and the tablet)
- Samples gets a **Runs | Checklist** switch (kept per device). The checklist: a region picker (where you are, All
  regions, or any of the 42), a summary line, one box per genus with each species' state (sold, aboard, lost,
  logged; greyed "not here"; ◐ in parts) and colours found / possible; click a species for its colours, what gives
  each, and a galaxy map with the regions it can grow in lit (in their tints) and your samples as dots
  (GET /api/checklist?species=). The tablet's Samples page has it as is. Guide: views.md, with a screenshot.
- The page smoke test: the checklist end to end against the scratch server; the riches clear check counts a repeat
  of the same request once (a poll landing in between added one now and then).

## 2026-10-09 · Exobiology checklist, part B: GET /api/checklist
- `State.checklist(region)` and GET `/api/checklist?region=here|all|<1-42>`: the checklist for where you are (or a
  region, or all), from every run (its fate as Samples has it) and every codex entry, placed by region; with the
  regions to choose from. A few milliseconds on a real database. Not on the page yet.

## 2026-10-09 · Exobiology checklist, part A: the table (outrider/checklist.py)
- The checklist's pure core: for a region (or all), every species the rules know, by genus: whether it can grow
  there ("parts" when only near Guardian sites, in tuber zones, by nebulae or in one system; a species with no rules
  is possible, not ruled out), your best state there (sold > aboard > lost > logged), and its colour variants with
  what gives each. The rules' duplicate under a misspelled name (Stratum Aranaemus) is merged by game id, and runs
  match by species id. `outrider.bio.ruleset_region_ok` is shared with `region_allows`. Not on the page yet.

## 2026-10-09 · Spansh's "Terraformable" priced as terraformable (CACHE_VERSION 17)
- Spansh's system dumps now spell a terraformable body's state "Terraformable" (it was "Candidate for terraforming").
  Outrider did not know the new spelling, so every terraformable body known only from Spansh was priced as a plain
  one: the arrival briefing named a terraformable high metal content world (rightly) at 59k instead of 674k. Both
  spellings are known now, and the Road to Riches rows read it too. CACHE_VERSION 17: systems looked up before are
  fetched again as they come up.

## 2026-10-09 · Bodies someone else mapped are not pointed out; gear and scoop N/A in supercruise
- A body your scan says someone else has already mapped (WasMapped) no longer sounds the find alert, is not named in
  the arrival briefing or the FSS debrief, and does not make the leaving alert warn (the author's ask). The first one
  over your levels in a system says one new line instead, in every personality: "Already mapped, but there are still
  valuable bodies to map if you want to jump on the train" (speech key mapped_before). Spansh's records do not say
  who mapped what, so a body you have not scanned yet is still mentioned.
- The tablet's rail: Landing gear and Cargo scoop are N/A in supercruise too, as Hardpoints are.
- The page smoke test's per-view check waits up to 10 s more for a slow view (Overview right after the load failed
  now and then, filled a moment later).

## 2026-10-09 · Hardpoints N/A in supercruise on the tablet's rail
- The tablet's Hardpoints button lit "On" after every jump: the game sets Status.json's hardpoints flag in
  supercruise (read in game, with Analysis mode on), where hardpoints cannot be deployed. In supercruise the button
  is now N/A (greyed, not pressable, "in supercruise"), and follows the flag again in normal space.

## 2026-10-09 · Road to Riches and Exomastery from a system Spansh doesn't know yet
- The survey routes stand in for an end Spansh does not know yet as Plot Route's Highway does: plotted from (or to) a
  Spansh system near it, on the way, with the real system put back as the first (or last) stop, nothing to survey
  there. The plot status says so. Not a trade route: it starts from a station's market as Spansh has it.

## 2026-10-09 · Plotting from a system Spansh doesn't know yet
- Plot Route could not plot from a system Spansh has not heard of (a fresh discovery): the exact plotter said so and
  stopped, the neutron one failed. Now both ends are looked up in Spansh's search first, and one it does not know
  (but Outrider can place: where you are, a visit, a bookmark) is stood in for by a Spansh system near it, on the
  way: within the ship's range, nearest the other end. The route is plotted from (or to) the stand-in and the real
  end is put back as its first (or last) jump, its fuel not figured. The plot status says what was done, and warns
  when that jump is longer than the ship's range. For where you are, the stand-in comes from the neighbourhood
  Spansh already sent; elsewhere one search around it.

## 2026-10-09 · Version 2026.10.19.1
- A bug-fix release on 2026.10.19: body names said letter by letter by Piper ("ay one", not "uh one"); the Codex
  review's fixes (one sender when two Outriders are switched on for an upload, trade routes counting tonnes with
  undocking as moving on, a powered-off Guardian booster not counted, the map asking again when reopened, a late
  companion file after a catch-up, the AI's round limit, the journal archive shared between instances, ExploData's
  colours retried). No journal re-read: nothing stored changed shape. The What's new page is in the guide.

## 2026-10-09 · Codex review fixes: the AI's rounds, the journal archive, the colour tables
- The AI could run one more round of tools than `[assistant] max_rounds` allowed (Codex F7): the request after the
  last round asks for the answer only (`tool_choice: "none"`), and a tool asked for then is not run.
- Two Outriders archiving the same journal into a shared backup folder could leave the shorter copy (a lagging
  mirror's) over the fuller one, and shared one staging file (Codex F8): each copy has its own .part file, and the
  archive is looked at again just before the replace. No lock between instances (DESIGN_NOTES).
- ExploData's colour table written as code upstream (not a plain literal) was taken as "no colours" and its version
  recorded, so it was never fetched again: it now fails like a failed fetch, keeping the colours already there and
  retrying at the next start.

## 2026-10-09 · Codex review fixes: the map
- The map kept what it had for a system while it was closed: leave a system and come back (or scan in it) with the
  map in another tab, and it showed the old trace and markers (Codex F5). Opening the map asks again. Its cache key
  is the system's exact id (`posId()`), not a number JavaScript rounds past 2^53.
- An older map request failing after a newer one had answered said "map failed" over the newer one's map and dropped
  its key, so a third request's answer could be thrown away (Codex F6): an older failure is ignored now.

## 2026-10-09 · Codex review fixes: the booster and trade routes
- A Guardian FSD booster switched off still added its light years to the range, the fuel figures and a route's hops
  (Codex F3): it counts only while powered, as the fleet's fitting already had it.
- A trade route ticked a commodity off at the first sale or purchase of it, whatever the amount: one tonne of a
  planned 400 said the hop's profit and could end the route (Codex F4). Now the tonnes add up (each journal line once,
  so a re-read counts nothing twice), the page shows "60 of 100 t" until it is all traded, and undocking with only
  part traded moves on, said with what fell short ("sold 100 of 400 tonnes of Biowaste") instead of the profit. A
  route in progress keeps what it had ticked.

## 2026-10-09 · Codex review fixes: the uploads
- Two Outriders switched on for the same upload (both started with it on: the game PC and a server sharing the
  journals) both held for good, and each followed the journal as if the other sent, so nothing was sent and that
  stretch was never caught up (Codex F1). Now exactly one sends: the one already sending keeps it, and started
  together the lowest instance id has it. A lease now says what it sends (`services`) and what it is switched on for
  (`wanted`); an Outrider from before (no `wanted`) is always given way to, so it sends.
- A catch-up whose last line was a NavRoute, a docking's market or the like, with its file still on its way (a journal
  share), gave the wait up at once: the catch-up's clock was moved on a minute to flush signals. The file's wait is now
  checked at the real time and handed to the live session, which sends it when the file comes (Codex F2).

## 2026-10-09 · Body names said letter by letter
- Piper said "A 1" as "uh one" (espeak reads a lone A as the article) and ran "ABC 3" into one slurred word ("uh beh
  ceh three"). A body's letters now go to Piper as its raw phonemes, each its own stressed word: "ay one", "ay, bee,
  see, three". Stars, planets' moons, rings and belts ("B 3 A Ring", "A A Belt Cluster 3"), and a one-star system's
  "2 a,". System, station and carrier names are left as they are (a catalogue number has more digits or a dash, and
  star letters run in alphabetical order: "HIP 12345", "LHS 21" stay). English voices only; American ones say Z
  "zee". Punctuation right after a letter goes inside its phonemes (Piper dropped that comma, and the pause with it).
  The voice lab says them the same way.

## 2026-10-09 · Docs: What's new, the version notes for players
- A new guide page, docs/guide/whats-new.md: what each release since 2026.10.11 brings, in the player's words (new
  features, settings, anything to know before updating), with screenshots of Settings → Uploads and the Data tile.
  First in every guide page's nav and in the README's index. The agent guide's release steps now include it.

## 2026-10-09 · Version 2026.10.19
- The first release since 2026.10.16 (2026.10.17 and 2026.10.18 were withdrawn to be tested first). New since 10.16:
  opt-in uploads to EDDN and EDSM (Settings -> Uploads; off by default); the nearest place to dock (Plot Route's
  📍 Nearest..., with the DSSA carriers); the plugin gaps (tagged plants, no ×5 in populated systems, ✪ new to your
  codex anywhere, the full-scan bonus, star kinds, Canonn Bioforge links...); and two whole-codebase bug sweeps, every
  finding fixed with a test. The first start re-reads the journals (parser 44). Docker: the container always listens
  on 8025 (set PORT in .env), and the health check waits for the first import.

## 2026-10-09 · The thresholds followed across windows
- The unsold and highlight thresholds changed (or reset by an import) in another window are followed by this one, as
  the alert ticks now are; it kept its own copy and could write it back over the change.

## 2026-10-09 · Fable sweep fixes: the page
- A voice answer or a co-pilot status report is no longer spoken by a window with spoken alerts off: Outrider told
  the Android app nobody would say it, so the app said it too and it was heard twice.
- A hung connection (the PC suspended, a network path gone silent) now turns into "no link" and "Lost contact" after
  40 s; the page stayed "stale" for good.
- A 🎯 / Target next started on this page ends when another device's run replaced it or Outrider restarted (it showed
  "targeting…" for good).
- Settings changed in another window: the 🔔 button follows the notification switch, and a setting an import reset
  there is reset here too (it was kept, and later written back over the import).
- Uploads: declining "Is this the only Outrider uploading?" no longer leaves the question as the status line; Save
  and remove redraw the section in Safari too (it kept the focus in the field, and nothing was redrawn).

## 2026-10-09 · Fable sweep fixes: the uploads
- Signals (fleet carriers, stations) that were the last lines while Outrider was down are now sent by the catch-up:
  they waited for a next line that never came, and were dropped. Ones written just before their jump (Odyssey) go
  with that jump once it is read.
- On a Windows game PC, looking for EDMC no longer stalls Outrider for a second or two every minute.

## 2026-10-09 · Fable sweep fixes: cargo, biology, voice, auto-target, auto honk
- Carrier cargo: a buy order others filled was counted twice in the carrier's total (a false "+300 t" gap): the
  CarrierStats the game writes just before Market.json already holds it. Last night's fix assumed otherwise; now the
  fill is added only when the last CarrierStats is older than the market read before it.
- Ship's hold: a second canister collected (or a purchase made) in the same second as the hold's snapshot is no
  longer lost, and no 0 t line is shown.
- Biology: a rules update in which a region, nebula or grid table is no longer plain data fails and keeps the
  working file; it wrote empty tables, and Anemone, Brain Trees, Tubers and others were never predicted again.
- Voice: a self-made voice picked in Settings is kept after a restart; an ask.json that is not an object falls back
  to the command names instead of stopping Outrider; "1 million" instead of "1000 thousand" for 999,500 to 999,999.
- Auto-target switched off mid-run with auto honk off closes the galaxy map it opened (it left the game in the map);
  auto honk switched off and auto-target on within one hold keeps the keyboard.
- The unsold command line takes --since 2026-09-01 (a bare date), and says what a bad one should look like.

## 2026-10-09 · Fable sweep fixes: the server
- A relog or game-mode switch while docked no longer repeats "Docked at <station>, N cr to sell" (and its spoken line).
- A backup copy restarted at every step (a busy evening, a slow backup disk) now falls back to one step as meant; it
  missed restarts that came right after restarts and could go on for thousands of steps.
- A Spansh outage no longer makes the page ask for a system's bodies every 4 s for as long as it lasts.
- Server settings no longer take another part's warning, printed at that moment, for a problem with the config (a
  valid save could be refused).
- Auto honk switched off during a Test says "off" at once.

## 2026-10-09 · Fable sweep fixes: scripts, Docker, the guide
- launch_outrider.sh works on macOS: it hashed requirements.txt with sha256sum, which macOS does not have (it stopped
  before anything else). Existing installs keep their stamp. The clipboard-tool hint is no longer shown on macOS.
- An environment whose Python is gone (a system Python upgrade) is made again instead of failing once with advice to
  install python3-venv.
- Docker's health check waits up to 30 minutes for the first start, which reads every journal before the server
  answers (it turned "unhealthy" during a long first import).
- The guide: Settings lists its Uploads section; personalities have up to fifty lines per alert (two have fifteen).

## 2026-10-09 · Docs: the agent guide on scripts/install.sh
- It is local to the author's checkout and git-ignored: never in the published repository.

## 2026-10-09 · Sweep fixes: the page
- Speech: a line the browser cannot play until a click is held only when the red pill asks for that click; with
  "Play on this PC" (after its call failed) or speech off it stalled the whole queue, danger lines included.
- "Back in contact" is said where "Lost contact" was (a tablet with Play alerts here never heard it).
- The tablet shows low fuel, a lost ship, a rig too far and the carrier leaving as danger banners.
- "Undiscovered" is said once when the briefing opens with a region crossing; the region line is no longer lost in
  systems with very large ids.
- Here shows nothing of the last system while another loads (its rows stayed, and clickable); the body panel takes
  only the newest answer; Cargo's "Buy something else" keeps what you typed; a new Sell/Buy lookup does not show the
  last one's commodity and price; an unnamed carrier is "your carrier" on the map, not "null".
- Settings: alert ticks changed in another window are followed by the window that speaks (it overwrote them); a
  section chip shows its heading, not under the sticky header; the route alerts have names on the tablet and in the
  tally; the tablet's footer says "Voice here" with Play alerts here.

## 2026-10-09 · Sweep fixes: cargo, the control rail, Nearest, mining, biology
- Carrier cargo: what other players sell you through a buy order counts in the carrier's total too; it made real old
  lines look stale, and they were dropped.
- The control rail reads the right Status.json bits for on foot in a station: in a planetary port's concourse or
  hangar it showed the on-foot buttons (flashlight, shields).
- Nearest: a DSSA carrier the list places in another system than Spansh's no longer carries the old system's id
  (wrong permit check) and arrival distance.
- Mining Search: "Low Temp Diamonds" (the survey's name) and "Low Temperature Diamonds" (the journal's) are one mineral.
- Biology: a rules update that does not parse is not written over the working copy (and is tried again); Radicoida
  Unicus is valued at the rules' figure (it counted 0). The unsold command-line report: --since now takes later sales
  and deaths off the biology too, and --calibrate no longer crashes on a pre-3.3 sale.

## 2026-10-09 · Sweep fixes: the voice's questions and the AI tools
- "What's left here?" (and the AI tool behind it) no longer fails in a system with a planet worth mapping: exactly
  the systems where the answer matters. The test's fake data had a different shape from the real one.
- "Nearest station with fuel" (or with Vista, repairs...) finds a station instead of reading the fuel gauge.
- When Spansh cannot be reached, "nearest station" says so instead of naming a far carrier as the nearest place.
- The AI tools take a single service given as text, and an infinite number, without losing the filter or failing;
  the MCP bridge talks UTF-8 on Windows too (a carrier name with other characters ended it).

## 2026-10-09 · Sweep fixes: backups, start-up checks, auto honk and auto-target
- Stopping Outrider lets go of Primary Fire at once: an auto honk under way held it for up to 20 s more, and one
  waiting for the keyboard could still press after the stop.
- Auto-target stopped while the galaxy map was closing (danger, the route changed...) no longer presses the map key
  again, which reopened the map.
- --restore of a zip whose compressed data is damaged says it failed its check instead of crashing; with a
  [server] host that is not this machine's any more it no longer says "stop ED Outrider first".
- The start-up clean-up of interrupted backups removes only this database's files: another instance (--db) sharing
  the backups folder could have its backup in progress.
- Windows: a second copy started while one runs stops at once (the port check never saw the running one, so the
  second copy began importing into the same database).

## 2026-10-09 · Sweep fixes: the journal reader (PARSER_VERSION 44: the journals are read again at the next start)
- Journals named the old way (before 2023) are read in time order, before the newer ones; read after them, your own
  first discoveries could keep a later scan. The next start reads every journal again to put this right.
- A journal re-read no longer loses your carrier's services (UC, Vista): the Nearest finder left your own carrier out.
- An Apex shuttle's Loadout is not your ship: it replaced your ship, jump range and hull, and wiped the fuel model.
- Stopping Outrider during its first big import no longer doubles part of a journal at the next start.
- When Spansh was unreachable (EDSM stood in), an arrival is no longer marked "Spansh lacks bodies" for good; a system
  past Spansh's sphere gets Spansh's bodies when you open it.

## 2026-10-09 · Sweep fixes: the config file and Server settings
- A decimal setting whose value is whole (speech speed 1, auto honk delay 2, radius 25...) takes a decimal again in
  Server settings: it was offered and checked as a whole number. Numbers are written by their type ("1.0") and saved
  exactly (a saved -45123.75 came back as -45123.8).
- "inf" or 1e999 in a list of numbers is refused, not a server error.
- `password = 1234` without quotes is taken as "1234"; a password that is not text at all now means nobody signs in
  from another device until it is fixed. Before, both were dropped and the server ran with no password.
- A config saved as "UTF-8 with BOM" (Notepad, PowerShell) is read, and saved back without the BOM; before, every
  setting was at its default and Server settings could not save.
- A config file that does not parse says so in Server settings (it showed the defaults and no problem).

## 2026-10-09 · Sweep fixes: packaging and scripts
- Docker builds leave out the local tools git ignores (eddn_listener/ with its capture database, any .venv, run.sh,
  scripts/install.sh): they would have gone into the published image.
- launch_outrider.sh and .bat: an environment left half made by a failed first setup (no pip, as before
  python3-venv is installed) is made again, and a failed setup leaves nothing behind; before, every later run failed.
- Docker: the container always listens on 0.0.0.0:8025, so a host or port changed in Settings can no longer make the
  server unreachable (set PORT in .env instead).
- Voice lab: it reads the same lines file as the server for an old `speech_file = "speech.json"`; it finds Piper in
  a Windows .venv; a voice download abandoned by closing it no longer leaves its .part file behind for good (swept
  an hour later); its advice names the launchers instead of a script the repository does not contain.

## 2026-10-09 · Docs: uploads brought up to date
- README: uploads are opt-in now (it said "never"). The Uploads guide rewritten for everything since: station data
  once per visit, hour-old EDDN messages dropped, a crash's note ignored after an hour, Docker's note name, the
  message line. Install points the Docker section at it; the agent guide's and design notes' uploads entries match
  the code. (The commit before this one ignores a local tool's folder, eddn_listener/, in .gitignore.)

## 2026-10-09 · Uploads: review of the bug-check fixes (branch EDMC-Functionality)
- The upload note's identity: a database from before keeps its id; a new id (a moved or restored database on this
  computer) removes its own old note, which was otherwise read as another Outrider's and could start an upload from its
  old position. A copy of the database (Docker included, where every container has the same name and path) is told
  apart by the file itself.
- A crash's note is stale at once only when untouched for an hour (a file server's clock can be minutes behind); the
  note written at shutdown includes a service switched on in its last minute; a handover position in an old-format
  journal compares by time.
- While another uploader sends EDDN, what EDDN was waiting on (signals, a market, a route) is dropped, and a docking
  then counts as a new visit; one waiting past its time on the tick is dropped. A batch of signals in a catch-up is no
  longer dropped for coming minutes before its next line.

## 2026-10-09 · Uploads: bug check, the page (branch EDMC-Functionality)
- Settings → Uploads keeps its message line: refusals ("EDMC on this PC is sending..."), EDSM's "saved", and the
  config-file note were wiped by the redraw right after they were written, so they never showed.
- A switch or Save that cannot reach Outrider says so, and the boxes show the server's state again (a failed request
  left the box flipped).
- An upload's box is ticked by what you switched, even while it is held or unavailable.
- An EDSM name or key being typed survives the redraw of the counts.

## 2026-10-09 · Uploads: bug check, EDDN (branch EDMC-Functionality)
- Station data goes once per visit: each docking sends the market, outfitting and shipyard again, changed or not (EDDN's
  readers date a station's data by it); only the same screen opened again in one docking is not sent twice. Before, an
  unchanged market was not sent again while Outrider ran.
- Any EDDN message an hour late (an outage, switched off and on) is dropped, not sent as current; a batch of signals
  left over from before EDDN was switched off is dropped.
- "Outdated schema" (426) stops that kind of message at once instead of after three refusals.

## 2026-10-09 · Uploads: bug check, the upload core (branch EDMC-Functionality)
- Journal files named the old way (before 2023) no longer stop uploads: positions compare by time, not by name.
- While EDMC or another Outrider sends a service, Outrider's position moves with the journal, and a restart does not
  catch up what they sent; with the other uploader still there it catches up nothing.
- With every upload off, the next switch-on reads the current journal from its top, so a jump made meanwhile is
  known (it sent the old system).
- The note in the journal folder lists only the services this Outrider uploads (an old position of a service switched
  off made another Outrider send that history). A note left by a crash long ago no longer blocks uploads for five
  minutes after a start. The note's identity belongs to this computer and database file: a copied database gets its
  own. In Docker the note names "outrider-docker" (OUTRIDER_HOST in .env), not a container ID.
- A service that says "later" (a server error, unreachable) pauses its whole queue, not just that message; a database
  error no longer ends a sender for good. Sent and refused messages are pruned after a week (nothing pruned them).
- A restored backup starts uploading from where the journals are now: what was sent since the backup, and the
  backup's own unsent messages, are not sent again.

## 2026-10-09 · Uploads: long sessions, late files, quiet signals (branch EDMC-Functionality)
- A long session that the game continues in a new journal file (part 2, no login after it) keeps uploading. Before,
  Outrider took the new file for a new session and every upload stopped until the next login.
- A market bracket the game writes as "" (not normally sold there, for sale now) goes to EDDN as "", not 0.
- A market, outfitting, shipyard, bartender or route file written after its journal line now goes on Outrider's next
  tick even when no further line comes (given up after 10 seconds); a batch of signals goes 3 seconds after its last
  one when you are in that system (a jump's batch still waits for the jump line).

## 2026-10-09 · Uploads: EDDN catches up an hour at most (branch EDMC-Functionality)
- After a gap (Outrider not running while you played), EDDN gets only the last hour's lines; EDSM still gets up to a
  week. EDDN's readers take what arrives as current, so day-old scans sent late could mislead them.

## 2026-10-09 · Uploads: "New to EDSM" removed (branch EDMC-Functionality)
- The badge and the Data tile's "new to EDSM" count are gone, with the table behind them (dropped from databases that
  had it). EDDN's copy of a jump, sent at once, usually reaches EDSM before Outrider's own EDSM batch, so EDSM's
  "systemCreated" seldom names your upload (seen on the author's first real uploads).

## 2026-10-08 · Uploads: a held upload still queues (branch EDMC-Functionality)
- While EDSM is held by a refused key, what you play is still queued, and goes once the key is fixed. Before, nothing
  was queued while held, and the held stretch was skipped when the hold cleared (the author lost twelve events this
  way). Another uploader (EDMC, a second Outrider) still stops the queueing: that one sends them.

## 2026-10-08 · Uploads: the stored EDSM key's ends (branch EDMC-Functionality)
- Settings → Uploads shows the stored EDSM key's first and last four characters and its length, to compare with
  edsm.net when EDSM refuses it. Never the whole key: the page may be open to the network without a password.

## 2026-10-08 · Uploads in the Data tile (branch EDMC-Functionality)
- The header's Data tile has a line per upload in use (each its own line), live: sent, waiting and refused in the last day, test and dry
  run marked, held or off said; EDSM's adds how many systems were new to EDSM (the all-time total on hover).

## 2026-10-08 · Uploads: EDSM's batches wait together (branch EDMC-Functionality)
- Events waiting for EDSM now share the first one's five-minute deadline. Before, each waited five minutes from its own
  time, so a long stay in one system sent its scans one request at a time (seen in the author's dry run).

## 2026-10-08 · Uploads: "New to EDSM" (branch EDMC-Functionality)
- When EDSM answers an uploaded jump with "systemCreated" (nobody had sent it that system before), the system's detail
  shows a quiet "New to EDSM" badge, dated. No spoken alert: the game's own first discoveries already have one.

## 2026-10-08 · Uploads, part H: EDSM (branch EDMC-Functionality)
- EDSM's journal upload (`outrider/edsm.py`): your events, minus EDSM's discard list (fetched while EDSM is on, a
  built-in copy until then), each with where you were (system, coordinates, station, ship), to the account of the
  commander who played them. Events wait for a jump, docking or Location (five minutes at most), then go together: one
  commander and game version per request, up to 200 events. Cargo, ShipLocker and Backpack carry their file's contents
  when the file is the one the event wrote.
- EDSM's answers: a refused name or key holds EDSM until it changes; the Legacy game and bad requests are dropped;
  single refused events are dropped; anything else is tried again later. A commander with no account sends nothing,
  and Settings → Uploads says so.
- EDSM has no test endpoint, so the developer's switch is a dry run: `OUTRIDER_EDSM_DRYRUN=1` builds and logs each
  request (to `data/edsm-dryrun.jsonl`, never the key) and sends nothing; the console and Settings say so.

## 2026-10-08 · Uploads: test mode said out loud (branch EDMC-Functionality)
- The console says at start whether EDDN and EDSM are on, and "TEST: EDDN's test schemas only" when
  `OUTRIDER_EDDN_TEST` is set. Settings → Uploads shows "(test schemas only)" whatever EDDN's state; before, the tag
  disappeared while EDDN was held or unavailable.

## 2026-10-08 · Uploads: switched in one place (branch EDMC-Functionality)
- EDDN and EDSM are switched only in Settings → Uploads. The switch applies at once and writes `[eddn] enabled` /
  `[edsm] enabled` into the config file, so the next start keeps it; those two sections are no longer among the Server
  settings, and the database's separate copy of the switch is gone. If the file cannot be written, the page says the
  switch holds only until Outrider stops.
- EDDN's test schemas are a developer's switch, the environment variable `OUTRIDER_EDDN_TEST=1`, not a setting:
  `[eddn] test` in the config is no longer read.

## 2026-10-08 · Uploads, part A4: catching up (branch EDMC-Functionality)
- Each upload remembers how far through the journals it has got (a mark). What was played while Outrider was not
  running is sent at the next start, up to a week back (the author's cap); a journal re-read or a restore sends
  nothing twice; switching an upload on starts from that moment. Lines NFS delivers late are no longer lost either.
- A stopped Outrider's lease file stays with its marks, so another one switched on starts where it stopped.

## 2026-10-08 · Uploads, part F: EDDN's station data (branch EDMC-Functionality)
- Markets (commodity/3), outfitting, shipyards and your carrier's bartender materials, read from the journal folder's
  files when their event comes, only the file that event wrote (its time and MarketID; tried again on the next lines
  while NFS catches up), each sent only when it changed; station data that could not be sent within an hour is
  dropped, not sent late. Docking granted and denied too. With this, EDDN carries everything EDMC sends from the journal.

## 2026-10-08 · Uploads, part E: EDDN's signals (branch EDMC-Functionality)
- The signals the FSS lists (stations, fleet carriers, tourist beacons, combat zones) go to EDDN as one message per
  run, sent with the line that ends it: Spansh learns where fleet carriers are from these. Mission targets never go,
  nor a signal of another system.

## 2026-10-08 · Uploads, part D: EDDN's routes, codex entries, settlements (branch EDMC-Functionality)
- A plotted route (from NavRoute.json, only the file that NavRoute event wrote: checked against its time, tried again on
  the next lines while NFS catches up), codex entries (the body named only from the live Status.json, its id only when
  it is the body you approached), and settlements you approach (not a login at a port, which has no position).

## 2026-10-08 · Uploads, part C: EDDN's FSS family (branch EDMC-Functionality)
- The honk (FSSDiscoveryScan), all bodies found, a body's signals, barycentres and nav beacon scans go to EDDN too,
  each built from only the keys its schema lists (a field Frontier adds later cannot get it refused), the system's
  name and position added after the cross-check.

## 2026-10-08 · Uploads, part B: EDDN's journal messages (branch EDMC-Functionality)
- With EDDN switched on, every jump, login, carrier jump, dock, scan and DSS result (journal/1) goes to EDDN as it
  happens: personal fields out (fuel, fines, your reputation, a position on a planet), every `_Localised` name out,
  the star's position added only when the event is in the system you are in, horizons/odyssey as LoadGame said,
  the journal file's own game version. One message per request, gzipped; EDDN's refusals are never retried, and a
  message type refused three times in an hour is held until Outrider restarts; a network failure waits a minute.
- The tests check every message against EDDN's own schemas (copied into tests/fixtures/eddn, BSD); `jsonschema`
  joins the development requirements.

## 2026-10-08 · Uploads, part A3: one uploader at a time, EDSM accounts, Settings → Uploads (branch EDMC-Functionality)
- Lease files in the journal folder (`.outrider/uploads-<id>.json`): an uploading Outrider says so there every minute;
  another one refuses to start the same upload, both hold if they started together, a crashed one's note goes stale
  after five minutes (by the reader's own clock). A read-only folder refuses when another claims it ("Filesystem is
  read-only and another instance is set for upload") and otherwise asks first. EDMC running on this PC with its own
  EDDN/EDSM upload on holds that upload.
- EDSM's commander name and API key per in-game commander, kept in the database and never served back
  (`POST /api/uploads/edsm`). Settings → Uploads: the switches, what each sent, why it is held.
- Docker: an optional writable `.outrider` mount (commented out: the folder must exist on the share first). The guide
  has an Uploads page. Still nothing is sent: EDDN comes next.
- Tests never touch the real journal folders or EDMC's config any more (support.py blanks them).

## 2026-10-08 · Uploads, part A2: switches, the sending loop, the status (branch EDMC-Functionality)
- `[eddn] enabled / test` and `[edsm] enabled` (off by default), and `POST /api/uploads {service, on}` for the page's
  switch, which wins over the config and is remembered; never in `--simulate`. The payload's `uploads` says, per
  service, whether it is on, what is queued, sent and dropped in the last day, the last error, and why nothing can be
  sent now (the beta, the Legacy game, crew in someone else's ship).
- One sending loop per service on its own HTTP session (`ED-Outrider/<version>`): oldest first, about two a second;
  after a network failure or a 5xx it waits a minute, longer each time. Still no service sends anything: EDDN is next.

## 2026-10-08 · Uploads, part A1: the session, the live gate, the outbox (branch EDMC-Functionality)
- The groundwork for EDDN and EDSM uploads (opt-in, off; nothing is sent yet): `outrider/uploads.py` follows each
  journal line's game session (version and build per file, commander, Horizons/Odyssey, where you are, crew), lets only
  the running tail's recent lines through (never a start-up catch-up, a re-read, a restore or a legacy folder), and
  queues messages in a live-only outbox in the same transaction as their line.

## 2026-10-08 · Version 2026.10.18
- Since 2026.10.17: the review's 21 fixes (a docked login counts as docked, the password behind a reverse proxy on the
  Outrider PC, Spansh's services filter, answers arriving out of order...); tagged plants as waypoints for the next
  sample; no ×5 in populated systems; ✪ new to your codex anywhere; "bio possible: check the FSS"; the bio card while
  flying low; why each other genus is ruled out; the full-scan bonus in the unsold estimate; the target's known bodies
  from Spansh and EDSM; star kinds, Canonn Bioforge links and a system's CSV. The first start re-reads the journals
  (parser 43).

## 2026-10-08 · Fixes from a review of the plugin-gaps work
- A Fable review of batches B-F (each finding checked by a second reader): 10 bugs, all fixed with tests.
- Tagged plants: Brain Trees, Anemones, Sinuous Tubers and the other species without colour variants are now tagged
  (found by name in the rules); the codex entry a first Log writes is no longer a waypoint at your own feet; each tag is
  said once per run (two close together no longer take turns), under the sampling alert's switch rather than "find";
  the strip names the tag when the earlier samples' positions are unknown too; the map's legend colours match the map
  and list the tagged plants.
- "Bio possible: check the FSS" no longer reappears on a body you FSS'd after a later AutoScan of it.
- The unsold CLI's ESTIMATED and TOTAL include the full-scan bonus, and the pop-up's "before the cut" figure too.
- Only an organic codex entry links to Canonn's Bioforge (geysers and the like no longer do).

## 2026-10-08 · Small extras: star kinds, Canonn Bioforge, a system's CSV (plugin gaps F)
- A star's body panel says its kind in words: the luminosity class ("main sequence", "giant", "subdwarf") and, for a
  white dwarf, what its spectrum shows ("hydrogen-rich", "carbon", "variable").
- A biology codex entry in the body panel links to Canonn's Bioforge statistics for it ("stats ↗").
- Here's heading has **⬇ CSV**: the system's bodies and values as a spreadsheet (`/api/export?what=system&id=`).
- Not done: translations (the author: speech.json is there to change), WasLogged (nothing to check it against).

## 2026-10-08 · The targeted system's body counts, Spansh and EDSM (plugin gaps E)
- Targeting a system now shows how much of it is known: Spansh's bodies of its body count ("3/12 known"), on Now's
  target line and the header's, even outside the Nearby sphere; and EDSM's own count beside it ("EDSM 5/12", or "EDSM:
  not logged"), as SystemStatusOverlay showed. EDSM is asked once per target, after the target's sound, so the sound is
  never late.

## 2026-10-08 · The full-scan bonus in the unsold estimate (plugin gaps D)
- The unsold total now counts the bonus Universal Cartographics pays on top of the base value: 1,000 cr per body of
  a system you found complete (every body) while every star and planet in it was undiscovered. It shows on its own
  line in the Unsold pop-up. Checked on your sales first (`project/value-checks`): the paid bonus is 0.86-1.11 of this
  in 13 of 15 sales. Pioneer's other value rules stay out because your sales do not bear them out (the full-map bonus,
  honk-only bodies, terraformable ranges); your own carrier pays in full, as before.

## 2026-10-08 · Bio marks: populated systems, new anywhere, bio possible, flying low, why not (plugin gaps C)
- **No ×5 in populated systems:** Vista Genomics never pays the first-footfall bonus where people live (checked on
  your sales: 0 of 8 runs there, 208 of 208 elsewhere), so bio there is valued ×1 everywhere: Here, Samples, the
  unsold total, "worth landing". A re-read of the journals at the next start fills in each system's population
  (parser 43).
- **✪ new to your codex anywhere**, beside ✦ (new in this region only): worth more effort.
- **"🧬? check in the FSS"**: a landable body you have only from an AutoScan or a nav beacon, whose signals nobody
  counted, where the rules allow life.
- **Flying low over a body** (in your ship, under 5 km) the on-body strip shows its bio card already.
- **Why not:** the body panel lists each genus the rules rule out there, with the reason ("pressure too low").
- **Here's bio column** can leave out finished species and bodies with fewer than N signals (Settings → Display,
  this device).
- From BioScan's options and checks; `WasLogged` is left out (nothing in your journals to check it against).

## 2026-10-08 · Tagged plants: where to go for the next sample (plugin gaps B)
- Point the composition scanner at a plant (from the ship flying low, the SRV or on foot) and Outrider remembers where
  it is, as BioScan's waypoints did: a hollow ring in the species' colour on the surface map, faint where a sample
  would not count. While sampling, the strip names the nearest one that would count and which way to turn
  ("tagged: 524 m, turn 90° right"), and within 100 m the voice says so (a new line, `bio_tag_near`, in every
  personality). On foot the game logs the plant's position; from the ship or SRV it is yours at the moment of the
  scan, so scan close. Tags are kept through a journal re-read; a species finished on the body drops its own.

## 2026-10-08 · The review's fixes (21 bugs) and the Spansh services filter
- From a review of the whole code (five areas, each finding checked by a second reader trying to disprove it): 21
  bugs confirmed, all fixed, each with a test that fails without it.
- **Auto-target and the co-pilot button:** a supercharge while Target next, 🎯 or the button's tap was counting down
  or pressing keys no longer starts a second galaxy-map run (each run keeps its own stop token). A second press that
  comes just after the double-tap window but before the tap was settled now cancels that tap's targeting, as meant.
  A survey or trade plot still running is stopped at shutdown.
- **Journal data (a re-read of the journals at the first start, parser 42):** a session that starts docked (a
  login, a respawn) counts as docked, so a carrier transfer straight after it is no longer lost. The Rhino's
  refinery and scoop stay out of the ship's hold. A legacy folder imported late no longer counts each old login as a
  visit (or breaks the flown path). A market read keeps a carrier line's recent moves.
- **The password and the API:** behind a reverse proxy on the Outrider PC (Caddy, nginx) the password applied to
  nobody: a forwarded request now counts as another device's, and wrong passwords count against that device. An odd
  session token is a JSON 401, not a crash; an id of 1e999 (or 1.5) is a 400. A DSSA answer of the wrong shape is a
  failed check, said in the finder and asked again, not a fresh copy.
- **Nearest and trade routes:** "nearest Vista" (and the rest) by voice no longer skips the places in your own
  system. Spansh's services filter was being sent in a shape Spansh ignores, so the finder saw only the 50 nearest
  stations and **the Unsold tile's nearest Universal Cartographics / Vista Genomics sellers could be stations without
  them**: both now ask in the shape Spansh honours, and the sellers are checked. The finder reuses its search for two
  minutes while you change its other filters. A row with a missing coordinate no longer breaks the answer; a DSSA
  carrier newer reported at home loses the "last seen at" warning. A trade route with two stops in one system moves
  on to the second with your trades there.
- **The page:** answers arriving out of order no longer overwrite newer ones (the on-body strip, Find, My firsts,
  Materials, Biology, History), and pinning another system shows "loading…" rather than the last system's bodies.

## 2026-10-08 · The Nearby tab's table no longer takes the Nearest finder's styles
- The finder's table had the Nearby tab's id (`nearTable`), so since 2026.10.17 its styles (13px text, its cell
  padding and lines) also reached the Nearby tab's table, and on the tablet a tap on a finder row opened the Nearby
  tab's detail sheet. The finder's table is `dockTable` now, and a test keeps every id in the page used once.

## 2026-10-08 · Docs brought up to date
- The README's Automation row, the guide's header-tile and button wording, the program's own description
  (`--help`: Plot Route with its route types and the Nearest finder, Cargo in Materials, the Carrier tile's
  tritium), "Plot Route" where config help and comments still said "the Highway tab", the alerts dialog's auto-target
  description, AGENT_GUIDE (the button's gestures and State methods, the tools' cached nearest read, the voice's
  question text), DESIGN_NOTES (the button's layout replaces the old "not on the button" decision; what is not yet
  tried in a live game).
## 2026-10-08 · The co-pilot button targets the next route system
- The co-pilot button's layout (the author's): flying the ship, a **tap** targets the next route system in the galaxy
  map, half a second after the press: the Road to Riches / Exomastery / trade route's next first, else the Highway's.
  Success or failure is said as for auto-target; with nothing to target, a new line in each personality ("Are you on
  drugs? You don't have a system plotted for me to target."). A **double tap** is the status report (it was the tap),
  a **hold** the hush. "Say the last line again" is no longer on the button. Out of the ship a tap does nothing; in
  the Rhino every press still marks rigs. A press during the half-second wait cancels the targeting before any key
  and counts as the double tap it was meant to be (the status report); the double-tap window's default is now 400 ms
  (`[copilot] double_ms`, was 350), so a slow double tap reads as one. A `double_ms` already in your config stays.

## 2026-10-08 · Version 2026.10.17
- Nearest place to dock (stations and carriers, the DSSA's carriers, "nearest station" by voice), the co-pilot
  button's new layout (tap: target the next route system), and since 2026.10.16: the README split into a front page
  and a guide (`docs/guide/`).

## 2026-10-08 · Nearest place to dock
- **📍 Nearest…** beside Plot Route's To lists the nearest stations and fleet carriers you can dock at and use: what
  each has (UC, Vista, repair, refuel, shipyard), its pads, distance (and from the star), docking (yours, open to all,
  or a ⚠ for friends, squadron or not reported) and how old its report is. Filters for stations / carriers, services,
  data under N days (30), permit systems, remembered per device; **Plot here** fills To and plots. Sources: Spansh,
  the Deep Space Support Array's carriers (EDAstro, fetched when the finder opens, at most hourly; marked 🛰 DSSA) and
  your own carrier. By voice: "nearest station", "nearest carrier", "nearest Vista", "nearest repair"...; for AI
  clients a read-only `nearest_dock` tool.

## 2026-10-07 · The README split into a front page and a guide
- The README (1,000 lines) is now a front page: what Outrider is, at a glance, a short start and an index of the
  guide. The guide is `docs/guide/`: Install and run, The views, Plot Route, Cargo and trading, Voice and alerts,
  Automation, On a tablet, Settings and good to know, For the curious, each with a bar of links to the others. The
  text moved as it was; links into the old README's sections still land on its index. `test_docs.py` checks every
  link and anchor; the config example, Docker files, start-up warnings and the bundle's INSTALL.txt point at the guide.

## 2026-10-07 · From suggests system names too
- Plot Route's **From** field suggests Spansh's system names as you type, as **To** already did (each its own list).

## 2026-10-07 · README: Trading, and fresh screenshots
- A short **💱 Trading** section (Sell / Buy and trade routes) with two new screenshots (`cargo.png`: Cargo with a
  lookup open; `trade.png`: a trade route in Plot Route); Sell / Buy moved there from Cargo and your carrier, and Plot
  Route's Trade paragraph points to it. Every view screenshot, the four-theme sheet and the tablet retaken on the
  current page (Plot Route, the Carrier tile's tritium, Materials' Cargo).

## 2026-10-07 · A carrier decommissioned or replaced
- A carrier being decommissioned shows it in red on its tile and in Cargo ("Decommissioning: scrapped 9 Oct ·
  4.85B cr back"); once scrapped, "Decommissioned" with the date, kept rather than hidden so a mistake shows. A
  carrier bought since replaces it (`CarrierBuy`, or a `CarrierStats` of another id, which before this inherited the
  old carrier's place and booked jump). No carrier at all: no Carrier tile. Trade routes say they can take a few
  minutes to plot. PARSER_VERSION 41.

## 2026-10-07 · Version 2026.10.16
- Cargo and your carrier in the Materials tab, Sell / Buy from Spansh's markets, trade routes in Plot Route; and since
  2026.10.15: Expressway to Exomastery, the route line for every route, 🎯 on any route system, the Settings link to
  GitHub. README, AGENT_GUIDE, DESIGN_NOTES and JOURNAL_REFERENCE cover the cargo and trade parts.

## 2026-10-07 · Trade routes
- Plot Route's fifth plotter, Spansh's trade planner: station-to-station hops from the station you are docked at,
  with your credits and hold from the journal. It shares the slot with Road to Riches and Exomastery. Each stop lists
  what to sell and buy; on arrival the voice says where to dock and what to trade, your sales and purchases there tick
  the goods off, then the hop's profit and the next stop are said (its own alert, Trade route). 💱 in the route line.

## 2026-10-07 · Sell / Buy
- Every ship and carrier line in Cargo has Sell and Buy: Spansh's stations that take all of it (or have that much),
  best price or closest, within a distance, data under an age, fleet carriers out unless ticked, your ship's pad. A
  row gives the distance (and from the star), price, demand or supply, what your load earns and the profit over what
  you paid; opened, what else it buys from your hold, its services, Copy, Bookmark and Plot route here.

## 2026-10-07 · Cargo and your carrier
- The Materials tab's Cargo: your ship's hold with what you paid (the game's average cost), and your fleet carrier's
  hold, tracked: ✓ confirmed by a sell order at the carrier (its market lists each with its stock), ◷ last seen from
  your journal, ✎ entered (Recount). The total is checked against the carrier's own. No Frontier sign-in: this is the
  only way to track it without one, and the README says so.
- The Carrier tile shows the tritium while it is on a sell order: "Tritium in Depot", and "Total Tritium: 14,199 t
  (151 jumps)" (500 ly jumps, by the carrier fuel formula fitted to 27 real jumps).

## 2026-10-07 · Expressway to Exomastery
- Plot Route's fourth plotter, Spansh's Expressway to Exomastery: systems whose bodies carry valuable life already
  reported. It shares Road to Riches' slot (one survey route; a new plot of either replaces it). Each body lists its
  species with value, ✓ sampled (your journal) and ✦ new to your codex in the region; the voice says on arrival how
  many species are left on how many bodies and the best ("14 species on two bodies here: the best, Frutexa Flammasis
  on ABC 2 e, about 10.3 million credits"), and the next stop once all are sampled (its own alert, Exomastery). Known
  life: the page says first footfall is unlikely.

## 2026-10-07 · Settings link to the project on GitHub
- Settings shows **GitHub ↗** (the project's page: source, releases, README, issues) and the version running, at the
  top beside its title; the tablet's Settings sheet lists both projects (Outrider and the Android app). The payload
  carries the version (`outrider`).

## 2026-10-07 · 🎯 on any route system
- A small 🎯 beside every system in Plot Route's lists (Highway and Road to Riches; not the one you are in, passed
  ones included) and beside the next system in the line under the tiles for either route: it targets that system in
  the galaxy map, after the usual 5 s countdown (none from the tablet, whose row sheet has a 🎯 Target button). The
  same run as Target next; game PC only, hidden in server mode. A survey route is still never targeted on its own.
- `POST /api/highway/target` takes `{route: "highway" | "survey", index}` (without it, Target next as before); a
  cleared or replaced route stops only a run aimed at it.

## 2026-10-07 · The route line for every route
- The line under the tiles (Overview, Nearby, Here, and the tablet's strip) shows a Road to Riches route too, not
  only the Highway's: "💰 Next: X · 12.3 ly · 2 of 5 · 2 bodies to do here" (🧬 for Exomastery, coming next). With
  both routes it shows the one Plot Route shows. The payload's `survey` carries it; the Highway's summary its plot time.

## 2026-10-06 · Version 2026.10.15
- Road to Riches (thshurka's contribution), as a route type of the Plot Route tab (formerly Highway).

## 2026-10-06 · Road to Riches: the review's loose ends
- Spansh's Road to Riches API, which publishes no description, checked against the live site: the code's notes say
  what it takes and answers, and `tests/fixtures/spansh_riches.json` is a real answer (trimmed) that a test reads.
  `scripts/riches_probe.py` saves to its own file rather than over that fixture.
- A Road to Riches body's `body_id` is the game's BodyID (from its id64), as everywhere else in Outrider.
- README: Road to Riches is described in the Neutron Highway section (one tab, Plot Route); AGENT_GUIDE and
  DESIGN_NOTES cover it.

## 2026-10-06 · Road to Riches moves into the Plot Route tab (formerly Highway)
- Road to Riches (thshurka's PR #1: a Spansh route of systems with valuable planets, followed as you fly) is a route
  type of the tab now, not a tab of its own: the plotter switch reads Exact / Neutron / **Road to Riches**, which shows
  its options (radius, systems, max distance, min value, mapping, Thargoid systems, loop) and shares From, To, Ship and
  Range. The tab, renamed **Plot Route**, shows the route plotted last; with a Highway route and a Riches route both, a
  switch above the heading picks the one shown (per device) and Clear route clears that one. The Riches systems are a
  table like the Highway's (bodies listed under the system you are at, the next and any with work left, by their short
  names), and the route is drawn on the tab's galaxy map.
- With both routes, only the one plotted last copies its next system to the clipboard on arrival.
- The header is back to one line at 1600 px in every theme, the tablet's Navigate group to four pages, and
  `scripts/verify.sh` passes again. A browser or tablet left on the old Riches tab opens Plot Route.

## 2026-10-05 · Version 2026.10.14
- The Update pill, a second tablet without the rail, the compact layout for smaller tablets, and the clipboard tools
  named in the README, requirements.txt and the launcher.

## 2026-10-05 · A second tablet, and small tablets
- The tablet's Settings: **Show the game controls** (per tablet, on by default; offered when the Outrider has a rail).
  Off, that tablet has no rail and its pages take the width, as on a server, so one tablet can carry the rail and
  another not.
- A smaller tablet (under 1200 x 700 CSS px, e.g. 1006 x 601) gets a compact layout: the page list is
  narrower (136 px) and the rail too (150 px), its buttons a little shorter so all eight fit without scrolling, with
  short names (Gear, Scoop, Night vis., Lights, FA, Silent, Hardpts, Analysis; the SRV and on-foot sets likewise; a
  name you gave a button is kept) and the heading "Ship" / "SRV" / "On foot". A larger tablet's 1280 x 800 is unchanged.

## 2026-10-05 · An Update pill when a new release is out
- Once a day Outrider asks GitHub for its latest release (`[server] update_check`, on by default; only the request is
  made). A newer one shows a small **⬆ Update** pill in the header, or the tablet's head bar, in the theme's colours.
  It opens what's new and how to update this copy (Docker, a git clone or a download); **Skip this version** hides
  it until the next one, per browser. The start-up log says so too.

## 2026-10-05 · The clipboard tools in the README
- Getting started now says the Highway's clipboard copy and auto-target's paste need `wl-copy` (wl-clipboard,
  Wayland) or `xclip` (X11) from the distribution on Linux, how to install them, and that nothing else needs them.
- `requirements.txt` names them in a comment (pip cannot install them), and `launch_outrider.sh` says once, after an
  install, when neither is there.

## 2026-10-05 · Version 2026.10.13
- The Windows launcher, auto honk, auto-target and the control rail on Windows (experimental), the Windows
  clipboard, the config file's Windows path hint and the NFS note in the release's env file.

## 2026-10-05 · The NFS mount option in the release's env file
- `env.example` (the file a Docker server downloads) now says to mount NFS with `actimeo=1`, and why: without it
  NFS caches the journal's size for up to a minute and the alerts arrive late and all at once. The offline bundle's
  INSTALL.txt gave the wrong reason (Status.json); it now gives this one. The v2026.10.12 release's `env.example`
  was replaced with the new text.

## 2026-10-05 · Auto honk, auto-target and the control rail on Windows (experimental)
- On Windows these press keys the Windows way (`SendInput` with scan codes, as VoiceAttack does) through
  `outrider/winkeys.py`, which stands in for evdev, so everything above it is unchanged; Linux keeps evdev. Chosen by
  platform at start, nothing to set. The Highway's clipboard copy (and auto-target's paste) work on Windows too.
  Checked under Wine (the scan codes, extended keys and the clipboard), not yet against the game on Windows: marked
  experimental in the status and the README. Elite must not run as administrator. The co-pilot button stays Linux only.

## 2026-10-05 · Windows paths in the config file
- A path written `"C:\Users\..."` in `ed_outrider.toml` makes the whole file unreadable (in double quotes a TOML
  backslash starts an escape), and Outrider then runs on defaults. The console line now says so and how to write it
  (`C:/Users/...`, or single quotes); the README's Settings section and the example config explain it too.

## 2026-10-05 · The agent notes brought up to date
- AGENT_GUIDE: the per-device keys (`desktopTheme`, `tabletAudio`, `tabletEmblem`), every test file, `static/emblems/`,
  `scripts/install.sh` and `dark_icons.py`, the drawn schematic and desktop theme in page.js, `DESKTOP_STYLES`, what
  `data/` holds now, the bundle's release files and the whole release (ghcr and the GitHub Release), Windows; no more
  pointer to a private plan. AGENTS.md and CLAUDE.md carry the same rules. page.js's tablet comments no longer say it
  never speaks.

## 2026-10-05 · A Windows launcher
- `launch_outrider.bat`: double-click it on Windows (Python 3.11 or newer) and it sets Outrider up and starts it, as
  `launch_outrider.sh` does on Linux: `.venv` and `requirements.txt` the first time and after a change, then straight
  in. Everything but the game-PC automation works on Windows; the README says so. Tried under Wine with Windows
  Python 3.12 (Wine's own gaps aside: Piper's numpy crashes there).

## 2026-10-04 · Version 2026.10.12
- The desktop themes (Settings → Display), with their README picture.

## 2026-10-04 · Each theme's own touch on the desktop page
- A theme on the desktop page now brings more than its colours: its display face on the title, the view pills, the
  tile labels and the dialogs' headings, and its shapes: LCARS's coloured pills and side bars, Elite's and Narn's cut
  corners, Earthforce's angled tabs and steel rules, Minbari's arched tiles and thin double lines, Centauri's notched
  corners and gold double borders, Sith's hard lines and crimson edge, the Alliance's orange and sand, Dark's soft
  cards. The tables and lists keep a plain face, and the view pills fit on one line as with the Default.

## 2026-10-04 · Readable theme colours
- Every theme's text colours are checked against its background and panels (4.5:1). Two fell short and are lifted:
  Sith's red as text (the page's accent, 3.7:1; its fills and the tablet's frame keep the deep crimson) and the Rebel
  Alliance's red for errors.

## 2026-10-04 · Themes for the desktop page
- Settings → Display → **Theme on this browser**: the tablet's nine themes for the desktop page too, or **Default -
  Outrider** (the look so far, the only one that follows your system's light mode). Per browser; the tablet keeps its
  own choice. The maps take the theme's colours as well, and the theme is in place before the page first shows.

## 2026-10-04 · Docker from the registry, in the release and the README
- The release now leads with GitHub's container registry: its `docker-compose.yml` (running
  `ghcr.io/weslocke/ed-outrider:latest`) and `env.example` are attached, at fixed "latest release" addresses, so a
  server needs two downloads and `docker compose up -d`; `docker compose pull` updates it. The bundle stays for an
  offline server. `scripts/docker_bundle.sh` writes those two files into `dist/` too.

## 2026-10-04 · Published: a GitHub release and a container image
- Release v2026.10.11 on GitHub with the Docker bundle attached, and the image on GitHub's container registry as
  `ghcr.io/weslocke/ed-outrider` (2026.10.11 and latest). The Dockerfile's labels link it to the repository.

## 2026-10-04 · Version 2026.10.11; new screenshots
- Every README screenshot retaken at a true 2560 × 1440 (a 1440p screen at 100%): the orange view buttons, the split
  Here, the drawn schematic (Lysood HP-I b9-2: water worlds and ringed gas giants). The tablet's is at its own screen,
  1920 × 1200 (a larger tablet), with its control rail.
- Version 2026.10.11: the drawn schematic, "1 jump", `launch_outrider.sh`.

## 2026-10-04 · launch_outrider.sh
- `./launch_outrider.sh` starts Outrider and sets it up first when needed: it makes `.venv` and installs
  `requirements.txt` on the first run, again when `requirements.txt` has changed or the environment is broken, and
  otherwise starts at once. Arguments go to Outrider.

## 2026-10-04 · The schematic draws each body
- Here's schematic shows each scanned body as a small picture made from its scan data, the same painter as the body
  panel's: class colours, gas-giant bands, oceans and clouds, an atmosphere's rim, rings, a star's glow. Each picture
  is made once and kept. Unscanned bodies stay hollow outlines; landable and selected bodies keep their rings.
- The fuel tile's "1 jumps at max range" reads "1 jump".

## 2026-10-04 · "1 jump", not "1 jumps"
- A count of one jump reads "1 jump" everywhere: Now's fuel line, the History totals, the Highway's figures and plot
  message, the fuel alerts, the Log's FSD target line, and the spoken fuel, status and next-jump answers.

## 2026-10-04 · Version 2026.10.10
- The Narn emblem without an orange box.

## 2026-10-04 · The Narn emblem without an orange box
- In the Narn theme the free space under the page list was painted rust, so its emblem sat on an orange block. While
  the emblem shows, that space is left unpainted and the emblem is stronger (its own colours show); with Show the
  theme's emblem off, the rust fill is back.

## 2026-10-04 · Version 2026.10.9: the emblems' file type on Python 3.12
- The `.webp` emblems are served as `image/webp` in Docker too: aiohttp serves static files from a type table of its
  own, which now gets `.webp` as well (2026.10.8 sent them as `application/octet-stream`).

## 2026-10-04 · Version 2026.10.8
- The Minbari and Centauri themes, the relabelled Babylon 5 family, and the themes' emblems.

## 2026-10-04 · Emblems on the tablet themes
- The Elite (the Explorer "Elite" rank badge), Babylon 5 (Earthforce, Narn, Minbari, Centauri) and Star Wars (Sith,
  Rebel Alliance) themes show their emblem in the free space under the page list: faint, centred, and hidden when the
  column is too short. Sith's and the Alliance's are drawn in the theme's own colour. LCARS and Dark have none.
  **Show the theme's emblem** in the tablet's Settings turns it off (per tablet; on by default, offered only where
  the theme has one).
- Local copies in `static/emblems/` with `CREDITS.txt` (the Elite badge under Frontier's media usage rules; the
  Babylon 5 ones public-domain fan redrawings; Sith CC BY-SA 4.0; Alliance public domain). The README footer and the
  tablet's Settings carry the credits, and Frontier's attribution.

## 2026-10-04 · Two more Babylon 5 tablet themes: Minbari and Centauri
- **Babylon 5 - Minbari:** deep indigo, lilac and pearl with a sea-glass accent, soft arches and thin double lines;
  Marcellus headings, Inter text.
- **Babylon 5 - Centauri:** gold on royal purple and near-black, cream text, crimson for what is chosen, ornate double
  borders with notched corners; Cinzel headings, Cormorant Garamond text (scaled by its x-height so it reads like the
  others).
- The Babylon 5 family is labelled "Babylon 5 - Earthforce", "- Narn", "- Minbari" and "- Centauri" in the picker; the
  ids are unchanged (`babylon5` is Earthforce), so a saved choice keeps working.
- The fonts are SIL OFL 1.1, shipped with their licences; every theme's fonts are now checked to be there.

## 2026-10-04 · Docs: the README reorganised and brought up to date
- The README runs features first (the views, alerts, the voice, the surface map, the Highway, auto honk, the co-pilot
  button, the tablet and its Android app, Ask, backups), then the server-level parts (other devices on your network,
  Docker, the MCP bridge, settings).
- The Docker section has the real install and update steps (a release bundle or a checkout, Compose v2, NFS with
  `actimeo=1`) and a plain warning that auto honk, auto-target, the control rail, the co-pilot button, the clipboard
  copy and playing on the PC are off in Docker.
- Corrected: seven tablet themes, the "linked" pill, Play alerts here and Choose alerts…, the Tablet app buttons, the
  voice (Cori, More voices, the browser's voice only without Piper, the audio pill, "Lost contact" in Piper), and the
  script's own description (`--help`).

## 2026-10-04 · Version 2026.10.7; the tablet chooses its own alerts
- With Play alerts here ticked, the tablet's Settings has **Choose alerts…**: a large sheet with every alert's short
  name and what it is, and big 🗣 Voice and 🔊 Sound toggles. The choices are the tablet's own; the PC's browser keeps
  its. A tablet starts from the choices the PC saved as defaults for new browsers, and "Copy the PC's saved choices"
  takes them again later.

## 2026-10-04 · The tablet's link pill: just "linked"
- The tablet's link pill reads "linked" instead of counting the seconds since the last update, which was distracting.
  A stale link still shows how long ("stale · 48 s ago").

## 2026-10-04 · Play alerts here, on the tablet
- The tablet's Settings has **Play alerts here**: the tablet speaks the alerts (in Piper, from Outrider) and plays their
  sounds itself, whether or not a PC browser does too. With a Docker server there is often no browser open at all.
  When its browser holds audio back, the tablet's caption line says "Tap anywhere to let Outrider speak here".
- With it on, the tablet counts as a window that speaks, so the answers you ask for are said there in Piper.

## 2026-10-04 · "Click Here To Allow Audio"; never the browser's voice with Piper
- When the browser holds audio back until a click (after a page load or Outrider's own reload), the window that
  speaks shows a red **Click Here To Allow Audio** pill on the menu bar and 🔇 in its title. The tablet's caption line
  says the PC's page needs a click. Lines wait for the click and then play in Piper, or are dropped if they're no
  longer news. Before, they were said in the browser's own voice (found on the author's Docker server).
- With Piper on the server, the browser's own voice is never used: a line Piper can't say (or says while its voice
  is still loading) is not said. Without Piper, the browser's voice is still the voice.

## 2026-10-04 · Docker: a container that cannot write its folders stops at once
- When the container cannot write `docker/config` or `docker/data`, it says how to fix it and waits. That wait now
  ends as soon as Docker asks it to stop. It used to ignore the request, so `docker compose down` hung for the whole
  6-minute grace period.

## 2026-10-04 · Version 2026.10.5; Sign out only with a password
- The tablet's Settings shows Sign out only when Outrider asks for a password. Without one there is nothing to sign
  out of, and the greyed-out button read as one that did nothing.
- The version is now 2026.10.5 (since 2026.10.4: the Tablet app section, Docker's fixed project name).

## 2026-10-04 · The tablet's Settings opens the app's own screens
- In the Android app, the tablet's Settings sheet has a **Tablet app** section: Server… (which Outrider it connects
  to), Voice… (the wake word, sensitivity, the headset button) and App menu…, so they no longer need the Back
  gesture. Each button shows only when the app has that screen (app 1.2 or later); in a browser the section is hidden.
- The sheet names the app with its version ("ED Outrider for Android 1.2.0").

## 2026-10-04 · Docker: one project name, and how to update a bundle
- `docker-compose.yml` names its project `ed-outrider`, so a newer bundle's `docker compose up -d` replaces the
  running container instead of failing on its name (and a checkout and a bundle are the same project). A checkout
  started under its old project name: `docker rm -f ed-outrider` once.
- The bundle's INSTALL.txt says how to update from an earlier bundle: stop it, copy its `docker/` and `.env` across,
  load, start. Without `docker/`, a new bundle starts as a new install.

## 2026-10-04 · Version 2026.10.4; a warning for journals over NFS
- Outrider warns at start when the journal folder is on an NFS mount that caches file sizes for more than 2 s (the
  default is up to 60 s). There the journal seems not to grow, and alerts come late and all at once, as on the
  author's Docker server. The fix is `actimeo=1` on the mount.
- The version is now 2026.10.4 (everything since 2026.10.3: the review fixes, Piper-only co-pilot lines, the Docker
  bundle, Cori and More voices).

## 2026-10-04 · Cori by default; more voices from Settings
- The default voice is now Cori (`en_GB-cori-medium`). A voice you picked, or one named in your config, stays.
- Settings → Voice → **More voices** lists every Piper voice by language, with its quality and size. Pick one and
  Outrider downloads it where it runs and switches to it, so a Docker server (which has no voice lab) gets any voice.
- The voice lab and the server share one cached copy of Piper's voice list.

## 2026-10-04 · A Docker bundle without a checkout
- `scripts/docker_bundle.sh` makes `dist/ed-outrider-docker-<version>-<arch>.tgz`: the built image, saved, with a
  compose file that runs it, an `.env` example and INSTALL.txt. A server then needs no clone and no build:
  `docker load`, set the journal folder, `docker compose up -d`. Nothing is published.

## 2026-10-04 · What you ask for is said in Piper only
- A status report, "say again", a replay, and an answer to a question from the tablet are said in Piper (on the PC
  or in the browser, as before) or not at all: never in the browser's own voice. Each is shown as a caption either
  way. Alerts still fall back to the browser's voice when Piper can't speak.

## 2026-10-04 · Review fixes, batch F: the rail's keyboard and the dialogs' buttons
- A rail button pressed just as Outrider let go of the virtual keyboard (auto honk and auto-target off, the rail's
  last use ending) no longer leaves the device open (R12); auto honk's press closes it in the same case too.
- Enter in a rail button's label saves the rail instead of closing the editor and losing the typing (R11). The
  dialogs' ✕ and Done are plain buttons now, so Enter in Settings' fields no longer closes Settings either.

## 2026-10-04 · Review fixes, batch E: the AI layer's odd answers
- An AI provider answering in an unexpected shape now gives "the AI provider's answer was malformed" (502 ai_error)
  instead of a server error (R4). Providers that send a tool call's arguments as an object, or the answer as a list
  of text parts, are understood. Anything else failing in the AI layer is an ai_error too, with its traceback in
  Outrider's log.

## 2026-10-04 · Review fixes, batch D: sign-in and the network
- After signing in, the sign-in page only goes on to a page of this Outrider: a link such as
  `/signin?next=/\evil.com` could send you to another site (R6). The server drops such a `next` too.
- An HTTPS reverse proxy on your own network works: a name in `allowed_hosts` is answered without a port, and a
  change from its `https://` page is accepted (R7). Another site's is still refused.
- Outrider warns at start when `allowed_hosts` holds a name that looks like an internet one, or when it listens on
  your network with no password. The README says plainly not to expose it to the internet (a VPN instead).

## 2026-10-04 · Review fixes, batch C: the self-reloading page after an update
- An open page no longer reloads onto updated page files a few seconds before Outrider notices its own code changed
  too: both are checked in one go, so it waits for the restart instead (R3). A page loaded just after an update
  carries the stamp of the files it got, so it doesn't reload once more for nothing.

## 2026-10-04 · Review fixes, batch B: writing the config file from Settings
- Saving Server settings keeps the config file's permissions (a `chmod 600` file stays private; a new one is made
  private, since it may hold passwords) and writes through a symlinked config instead of replacing the link (R2).
- A key added to a section that ends in a list spread over several lines goes after the list, so the file still reads
  (R5); a hand-written `[highway.autotarget_keys]` table is replaced by the inline form instead of being declared
  twice (R10).
- Whole-number settings refuse a fraction ("must be a whole number") instead of writing a value that was then
  ignored (R9); their boxes step by 1.
- `game_pc`, `server_player` and `autotarget_entry` are a list to pick from; `game_pc` is written as text ("auto",
  "true", "false"), so it can be set back to auto from the page (R8).
- `--write-config` and Settings write passwords and other text with proper escapes: a backslash, quote or line break
  survives (S1). Only paths still have Windows backslashes written as slashes.

## 2026-10-04 · Review fixes, batch A: Docker's first run, stopping during start-up, leftovers
- Docker's first run works on a fresh clone: `docker/data`, `docker/config` and `docker/journals` come with the
  repository (Docker made missing ones owned by root, and the container restarted forever, unable to write its
  config: review R1). If a folder still can't be written, the container says how to fix it and waits.
- Docker gives Outrider 6 minutes to stop, longer than its 5-minute wait for a running backup (R14); leftovers of a
  backup killed part way (`.zip.part`, `.db-*.sqlite`) are removed at the next start.
- A stop during the start-up journal import (docker stop, systemd) ends cleanly and keeps the journal files already
  read: each is saved as it is read (R13).

## 2026-10-04 · Running as a server in Docker (the Docker plan, D4)
- `Dockerfile` and `docker-compose.yml`: Outrider 24/7 on another computer (x86-64 or ARM), built from this checkout
  (`docker compose up -d --build`), Piper included. The journals come from the game PC over NFS or CIFS, read-only;
  the database, backups and voices stay in `docker/data/`, the config in `docker/config/` (written on the first run;
  Settings edits it). Runs as your user, restarts by itself, has a health check, and stops cleanly.
- The README's "Running as a server (Docker)" says what is off there, how to share the journals, and how to update.

## 2026-10-04 · Stopping cleanly on SIGTERM; the MCP bridge signs in (the Docker plan, D3)
- SIGTERM (docker stop, a systemd service) now stops Outrider as Ctrl-C does: its work saved, the quit backup
  finished, exit code 0. It used to end at once.
- The MCP bridge can reach an Outrider on another computer, which asks for its password: `[mcp] password` (or
  `--password`); it signs in and says so when the password is missing or wrong.
- The start-up note no longer says "no authentication" when a password is set.

## 2026-10-04 · Server mode leaves the game PC's controls out (the Docker plan, D2)
- With `game_pc` off, the pages show nothing that needs the game PC: Settings' Auto honk section, "Play speech and
  sounds on this PC", the Highway's auto-target box, its 🎯 / Retry buttons and clipboard line, and on the tablet (and
  so the Android app) the rail column, whose width goes to the page. Settings → Server settings says why.

## 2026-10-04 · Server mode: [server] game_pc (the Docker plan, D1)
- `[server] game_pc` (auto, true or false): whether this Outrider runs on the PC the game runs on. Auto turns it off
  inside a container (Docker). Off, nothing touches a game PC: no auto honk, auto-target, tablet rail, co-pilot button,
  clipboard or sound played on this PC; those routes answer "needs Outrider on the PC the game runs on".
- The payload and /api/version carry `game_pc` (the app's about screen says "Outrider on a server").

## 2026-10-03 · A seventh tablet theme: Dark (modern)
- A modern app's dark mode: slate greys rather than black, flat cards with rounded corners and subtle borders, blue
  for what is on or chosen, switches instead of ticks, Inter (SIL OFL) with tabular figures.
- Line icons (Lucide, ISC licence) beside the words in the nav, the footer and the rail, and in place of the ☆ 🏁 👣
  ⛽ markers and the sort arrows; only in this theme.

## 2026-10-03 · Three more tablet themes: Narn, Sith and Rebel Alliance
- Narn (Babylon 5's Narn Regime): dark red-brown, rust panels with wedge cuts, ochre accents, parchment text.
- Sith (Star Wars' Empire): black, crimson for what is on, steel-white text, thin hard lines with cut corners.
- Rebel Alliance (Star Wars): blue-black, cockpit orange and sand panels, blue for what is chosen, rounded consoles.
- Fonts (SIL OFL, shipped): Russo One, Share Tech Mono, Rajdhani, Oxanium; a heading font of your own as
  data/fonts/narn-display.ttf, sith-display.ttf or alliance-display.ttf.

## 2026-10-03 · Rail: where an unbound control is bound; captions as written; "restart to finish updating"
- A rail button bound only on your HOTAS says so ("On Joy 5 only: add a keyboard key"): the rail presses keys through
  a virtual keyboard, and the game takes a joystick button only from that joystick (found with Night Vision, Ship
  Lights and Analysis Mode on the X-56).
- Captions (Now, the tablet's footer) show names as written ("Smojooe ZC-D c12-2"), not the voice's spelling.
- When Outrider's code was updated but Outrider not restarted, an open page no longer reloads onto new page files that
  need the new server; a line under the header says to restart it, and the page reloads once it has.

## 2026-10-03 · Settings (was the alerts dialog): folding sections, the whole config file, a wider window
- ⚙ Settings replaces 🔔 "Alerts & thresholds" (asked by the author). Its controls are in twelve sections that fold:
  Alerts, Voice, What is said, Sounds, Values, Risk and warnings, Surface map, Auto honk, Display, Sharing, Server
  settings, Spoken lines. Open all and close all are in the head; this device remembers which are open.
- **Server settings**: every key of the config file, from network, password and paths to Spansh, the Highway, the
  voice's AI and the MCP bridge, each with its help. Saving writes ed_outrider.toml, only the changed keys (its
  comments stay; the old file is kept as .bak), after checking the result; Outrider uses them from its next start.
  The password and the AI key are never shown.
- On a big screen Settings is far wider, its sections in two columns (three on a very wide one).

## 2026-10-03 · Two more tablet themes: Elite and Babylon 5
- Elite: the cockpit HUD's orange on black, thin-line panels with cut corners, cyan for what is selected.
- Babylon 5: Earthforce navy, steel-blue panels with angled header tabs, blue-white text, amber for warnings.
- Picked per tablet in Settings; the app's own screens follow, through OutriderApp.setTheme.
- Fonts (SIL OFL, shipped): Michroma and Saira Semi Condensed; Orbitron and Exo 2. Your own heading font can go
  first: data/fonts/elite-display.ttf or babylon5-display.ttf.

## 2026-10-03 · Drawn bodies (tablet plan, phase 7)
- A body's details (Here, Search) have a picture of it, drawn from its scan data:
  - its class's colours, with bands on gas giants and clouds and continents on Earth-likes and water worlds;
  - an atmosphere rim tinted by its main gas, rings by their class, its size by its radius;
  - the same look every time, and labelled "impression from scan data", with landable, terraformable and signals
    noted under it.

## 2026-10-03 · Ask Outrider by voice: POST /api/ask (tablet plan, phase 6, Outrider's side)
- The tablet app sends a question in words. Outrider answers the fixed ones without any AI: status report, fuel,
  unsold, next jump, what's left here, nearest unvisited, hush and unhush. Their phrases are in resources/ask.json
  (editable). The answer is said on the PC by the window that speaks and shown as a caption on every page.
- The tablet's footer has Ask when the app can listen.
- An optional AI layer for everything else (`[assistant]`, off by default): any OpenAI-compatible chat endpoint,
  given the same read-only tools as the MCP bridge. It runs on the PC with your key; nothing is sent while it is off.

## 2026-10-03 · The tablet's control rail (tablet plan, phase 4)
- On the tablet's right: up to eight game buttons for where you are (ship, SRV, Nomad, fighter, on foot), each
  pressing that control's keyboard binding on the PC once. A button shows the game's state from Status.json
  (headlights OFF, ON or HIGH), SENT until the game confirms a press, and "not confirmed" if it doesn't. An unbound
  control says which binding to add. Silent running has an amber ring.
- The agreed default sets, editable on the tablet (choose, rename, order; stored on the PC).
- Presses only while the game runs, through auto honk's virtual keyboard; never while auto honk or auto-target is
  pressing, never with --simulate.
- Bindings for SRV and on-foot controls are now read from those presets (StartPreset.4.start's third and fourth
  lines), not the ship's.

## 2026-10-03 · Ask an AI about your game: the MCP bridge (tablet plan, phase 2)
- `python3 -m outrider.mcp`: an AI client (Claude Code, the Claude desktop app) can ask your running Outrider
  questions through ten read-only tools: current status, this system, nearby systems, the nearest unvisited
  system, one body, unsold data, work left behind, the Highway route, travel history and materials. Answers are
  compact, with long lists capped. If Outrider isn't running, the tools say so.
- Read-only by rule: the tools read GET routes only and never press, plot, bookmark or hush. It talks to this PC,
  so `[server] password` never applies. Nothing extra to install.
- `[mcp] url` and `max_rows` in the config; the README has the connection steps and a privacy note.

## 2026-10-03 · An open page picks up a new Outrider by itself
- After Outrider is updated and restarted, a page left open (the tablet, the Now window) reloads by itself once
  nothing has been touched for a minute and nothing is being said. The page you were on comes back. Before, it went
  on running what it had loaded until someone reloaded it (found on the tablet).
- Tablet Search: a long label (⛏ bodies with mining locations) wraps inside its card instead of being cut off.

## 2026-10-03 · Tablet: a compact Search, Show in Here from results, cards and panels that fit
Found by the author on the tablet:
- Search: its five sections sit side by side in four columns, each scrolling on its own, with the results right under
  them. Before, ring hotspots and mining dropped to a second row far down the page. The form's controls take the
  theme's colours.
- A search result's sheet has Show in Here; it opens the system from its ☆, since the row has no other link.
- The pop-up card (a body's signals, mining odds, a system's bodies) stays on the screen and scrolls by touch. A
  touch inside it keeps it open.
- Here, and Here pinned beside Nearby: the heading and to-do list are capped, the whole view scrolls when it still
  doesn't fit, and a body's details on the right can't end up under the footer.
- From a check of every page at 1280 × 800 by touch: larger text in the Log, Materials and body details, and bigger
  tap areas round ⌖, 🔍 and ☆.

## 2026-10-03 · The view buttons are orange pills
- The row of view buttons (Overview … Now) was the browser's plain white buttons, glaring on the dark page: each is
  now a pill in the HUD's orange, outlined, with the view you are on filled (asked by the author).

## 2026-10-03 · Tablet fixes from the Android app's test
- System-name and search fields (Find, the Highway's from and to, the Log, Materials and Samples filters) are no
  longer capitalised or corrected by a tablet's keyboard.
- Now's "screen may sleep" hint is not shown in the Android app, which keeps the screen on itself.

## 2026-10-03 · The tablet layout (tablet plan, phase 3)
- `http://<PC>:8025/tablet`: the same pages in a layout for a landscape tablet, in its first theme, LCARS. The
  status strip (system, fuel, unsold) and the link in words are on top. The pages are on the left in three groups of
  four, with no Overview. Hush, Status report and the last line said are in the footer. The right-hand column is kept
  for the game buttons of the next phase.
- On the tablet:
  - It never speaks or plays sounds; an alert is a banner (red for danger).
  - A tap on a table row opens all of its facts, with Show in Here and Bookmark.
  - It goes to Now while the surface map shows and back afterwards; the Now button says MAP.
  - Target next runs without a countdown.
  - The settings sheet has the theme, dim, the screen size and Sign out.
- The maps by touch, on any touch screen: one finger rotates the galaxy map, two fingers move it and a pinch zooms; on
  the Highway map two fingers move and pinch.
- The fonts are Antonio and Barlow Condensed (SIL OFL 1.1), shipped in static/fonts/. A font of your own goes in
  data/fonts/lcars-display.ttf.

## 2026-10-03 · Exact plots work again
- The Highway's Exact plots always failed with "Spansh: Unable to find route": Spansh's exact plotter now takes
  systems by id64, not by name (found in game). Outrider sends the id64 of where you are, of a system it already
  knows, or of the one Spansh's search finds by the exact name. The neutron plotter still takes names.
- A start system Spansh has not received yet (a new one; it reaches Spansh a minute or two after your visit) now says
  so: "Spansh has not received ... yet: try again in a minute".

## 2026-10-03 · A password for devices on your network (tablet plan, phase 1)
- `[server] password`: a tablet or phone signs in once on a small sign-in page and stays signed in, across Outrider
  restarts, until the password changes or it signs out. This PC itself never needs it. Empty (the default) asks
  nobody, as before. Five wrong tries a minute per device, then a wait.
- The Android app's side of it: `GET /api/version` (Outrider's version, the API level, the oldest app it works with,
  whether a password is set, whether you are signed in), `POST /api/auth/signin` and `/api/auth/signout`, a Bearer
  token as well as the cookie, and every error as `{error, code}`. An app that is too old gets 426.
- The page sends you to sign in again if its session ends (a changed password) instead of showing a dead link.

## 2026-10-03 · Split Here in halves; every table's sort reverses; Materials side by side
- Here in split: the body list and the schematic each take half the pane and scroll on their own.
- Every sortable table (Nearby, My firsts, Bookmarks, Search, Here): a second click on a heading reverses it, a
  third goes back to the table's default. Here's tree is never sorted (it keeps the orbits' order).
- Materials: Mining sites beside "Where to find FSD-injection materials" (one above the other on a narrow window).
- The lost-contact line is two sentences with a clear pause between them.
- The jump line starts 2.5 s after Status.json says you are entering hyperspace, with the tunnel itself.

## 2026-10-03 · Codex finds as a reason to stay is a config option; a tab icon
- `[defaults] codex_interesting` (on by default; also the alerts dialog's tick, per browser): off, a species new to
  your codex here (✦) no longer puts a body on Now's next stops or in the leaving warnings, nor in the leaving card's
  text, nor exempts it from "skip?"; the ✦ marks stay as facts.
- A tab icon (static/favicon.svg): a ship's arrowhead in a scanner ring, in the HUD's orange; an original drawing.

## 2026-10-03 · Here's sort reverses; "lost contact" in your own voice
- Here's Dist, Grav, Now and Max headings: a second click reverses the order (▴), a third goes back to the default,
  Max (found in game).
- "Lost contact with Outrider" plays in your Piper voice: the page makes the line in advance while Outrider can, and
  plays it when the link drops; without it, the alert sound, never the browser's robotic voice (found in game).

## 2026-10-03 · Docs and screenshots refreshed; the Rhino no longer forgotten at launch
- Launching the Rhino no longer loses track of it: Status.json written while the SRV deploys from the bay lacks the
  SRV flag, and a fallback took that for "back in the ship", so the co-pilot button gave the status report instead
  of marking a rig (found in game). The fallback now needs Status.json to say you are in your ship, a minute after
  the launch. PARSER_VERSION 39: the next start re-reads the journals once, which finds the vehicle you are in again.
- The line under the tiles says which vehicle you are in on a body, "On A 2 (in the Rhino)" or "(in the Nomad)", from
  the journal's launch (Status.json's SRV flag is the same for all of them); "the SRV" when the launch was never seen.
  The welcome back line likewise.
- AGENT_GUIDE, JOURNAL_REFERENCE, DESIGN_NOTES, README, the example config and the program's own description brought
  up to date with batches 4-12; every README screenshot taken again (the Highway one at a refuel stop).

## 2026-10-03 · Page suggestions (fix plan, batch 12)
- Here shows each genus's colony distance (metres between samples) before you land: in the row's tooltip, the
  body pop-up and the body panel (review S1).
- Here's body table sorts by distance, gravity, Now or Max (click the heading); not by bio, which has no single
  value (S19).
- A cut-off line in a header tile shows the whole of it on hover (S17, part a; wrapping is left for later).
- Search's mining: a mineral you have refined is searchable (Gold, water...), and the bodies where you refined it
  come first, "Gold 22 t mined here before", surveyed for it or not (S38).
- A link pill in the top bar: "linked · 2 s", "stale · 48 s" (no answer for longer than a long poll takes), "no link
  · retrying since 14:02"; the page still dims when the link is down (S41).
- The alerts dialog has a sticky row of section chips, and reopens at the last section used on this device (S43).
- Header tiles on this device: one line on a small window (under 800 px high or 1200 wide), always six, always one
  line, or as ▴/▾ sets them (shared, as before) (S44).
- The rig leash warning says which way the rig is: "Rig 1 is 3.6 kilometres away, behind you" (S9).

## 2026-10-03 · Voice (fix plan, batch 11)
- The jump line is said in the hyperspace tunnel, not over the game's countdown call (review S14), and has its own
  varied, bannable lines in speech.json, `fsd_charge`, 50 per personality list (S15).
- The next queued line is synthesised while the current one plays, on the PC and in the browser (S11).
- A Volume for Outrider's own voice and sounds, per device (S12).
- Your own alert sounds: `[speech] sound_dir`, a folder of `<name>.wav` files up to 3 s each (S16).
- The last line said, beside the header's icons, with ▶ to hear it again (S18).
- S23 (the status report composed on the server) is left to PLAN-tablet phase 6, as its review advised.

## 2026-10-03 · Robustness (fix plan, batch 10)
- One of the work steps after each journal read that keeps failing no longer stops the ones after it (auto-target,
  the quit backup, the clipboard copy only work within a short window); its error shows on the page and its
  traceback prints once (review S5).
- When Outrider stops answering for 30 s, the page says so once in the browser's own voice ("Lost contact with
  Outrider"), and again when it is back (S13).
- The page's data (the long poll) is gzipped, about 4x smaller (S20).
- On a jump, Nearby shows what the local cache already knows around you at once, while Spansh is asked (S6).

## 2026-10-03 · Spansh, config, backups and restore, start-up (fix plan, batch 9)
- With Spansh down, systems cached from its earlier searches still read as Spansh's, not "not in Spansh"; EDSM's own
  records stay EDSM's (review F27). A failed body refetch keeps the cached full dump instead of the search's partial
  one (F28); a "no dump" answer gives way to the bodies the search now lists (F29). EDSM's fallback list asks for at
  most 100 ly, its limit, and the status says so (F48).
- The example config, `--write-config` and `--legacy`'s help say what the code does: legacy folders are
  auto-detected only while `live` is unset too (F18). The README says what plain `python3 ed_outrider.py` finds in a
  `.venv` (Piper and evdev, not aiohttp) (F47).
- A `[server] host` that is not this machine's (a changed LAN address, a typo) says so at start, not "port already in
  use" (F20).
- Upgrading from before the data/ folder: the database, browser_defaults.json, speech_banned.json, backups/ and
  piper-voices/ move from the repository folder into data/ once, saying so; an old config's
  `speech_file = "speech.json"` finds resources/speech.json, with a warning (F22).
- Closing Outrider within 10 s of the game quitting still makes the quit backup (F32); a backup still running at
  shutdown past 5 minutes is waited for and recorded, not dropped (F35).
- `--restore` restores a database not named *.sqlite (F33); a browser_defaults.json that cannot be written leaves the
  old one and reports the database as restored (F34); a defaults file of the wrong type is refused by --restore and
  ignored by the page instead of stopping it (Codex F9).
- The co-pilot button picks, of the devices whose names match, the one that can send the button (the throttle of a
  two-part X-56, not the stick) (F41).

## 2026-10-03 · Speech, voice, wording and page details (fix plan, batch 8)
- A map's "Next" says the body's whole mapped value, without and with your bonuses: "Next: map 7 (771k/2.2M)",
  spoken "771 thousand, 2.2 million with bonuses" (one number when no bonus applies), on Now, in the mapped call-out
  and in the status report (review Q5).
- A speech file with valid JSON but the wrong shapes inside keeps the last good lines and says what is wrong; bans
  keep working (Codex F7).
- Voice Lab: Stop drops a line still being synthesised (Codex F6); "Call me" starts from `[defaults] speech_names`
  (F38).
- A browser-voice error is not logged as said, nor repeated by "say again" (F44); a heat or interdiction line that
  was dropped unsaid no longer holds back the next one for 30 s (F46).
- "Your carrier departs in under a minute" instead of "in 1 minutes" (F37).
- The ship-loss card's "My firsts (lost)" link also enables the "within N ly" box (F23).
- Retargeting while reading the schematic no longer scrolls Here to the top (F17); a system whose stars sit under
  nested barycentres, (A+B)+(C+D), gets its star rows (F40).
- Systems are compared by their exact id strings in the speech queue and Nearby (Codex C2).

## 2026-10-03 · Sales, history and unsold estimates (fix plan, batch 7)
- A Vista Genomics visit sold in several goes is checked as one against the x5 prediction: History's trip note no
  longer counts an x5 run twice, or reports a miss when the x1 run was sold first (review F21).
- Two Vista Genomics sales in the same second stay two (bio_sales keyed by journal line: Codex C1).
  PARSER_VERSION 38: the next start re-reads the journals once.
- A login with no jump, two hours or more after anything else (a sampling or Rhino evening in one system), is a
  History session of its own, not more of the one before; a relog shortly before a session's first jump starts
  that session (F31).
- A body mapped before any line named its system (a carrier jump, then the DSS) is sold with the system, not left
  "aboard" (F36).
- The unsold pop-up's headings: a ship loss with no sale before it says "since your ship was lost", and exobiology
  says "since you died" (any death takes it) (F45).
- `python3 -m outrider.unsold --calibrate --commander X` leaves other commanders' sales out of the comparison (Codex F8).

## 2026-10-03 · Play fixes outside the Highway (fix plan, batch 6)
- Launching the Nomad no longer forgets the body you are on: a Rhino launched after it records its mining again
  (review F5). PARSER_VERSION 37: the next start re-reads the journals once to rebuild Mined previously.
- The SRV's and the Nomad's damage is not the ship's hull, nor a spoken danger line (F25); a login in the Nomad names
  your ship (F26).
- Here's "➜ Heading to" line and highlighted row follow the in-game target as it changes, without waiting for a scan
  (F4).
- Climbing past the surface map's altitude hides it at once; a browser's own altitude is capped at the server's
  (F24). A rig lost past the 5 km leash says "rig lost", not "rig picked up" (F43).
- The fuel tile no longer says "game not running" when the first reading is on foot or in the SRV: "ship's tank not
  read yet", with the vehicle's fuel (F9).
- A second scan of the arrival star (after the honk, or a nav beacon) no longer repeats the arrival call-out and its
  sound (F30).
- Undocking within seconds of a sale no longer announces the pre-sale total as still aboard (F39).
- `/api/status` and `/api/status.txt` send `Access-Control-Allow-Origin: *`, so a stream overlay on another origin can
  read them, as documented (F6).

## 2026-10-03 · Target next highway system, Retry, and the Highway in the status report (fix plan, batch 5)
- 🎯 Target next: in the Highway tab's auto-target box and beside "Next:" in the route line, it targets the next route
  system (off the route, the closest one) after a 5-second countdown, whether or not auto-target is on. A failed
  auto-target puts ⟳ Retry on its route row (review Q4). POST /api/highway/target, {countdown: 0-10}; a cleared or
  replaced route stops it.
- The co-pilot's status report and the welcome back line say the Highway: boost here, the next stop, the refuel
  coming up, the too-much-fuel warning first; off the route, the closest route system. "Nearest unvisited" is left
  out of the report while a route is followed (review S2).

## 2026-10-03 · Automation safety (fix plan, batch 4)
- Switching auto-target off stops a run under way, even mid-sequence while auto honk keeps the virtual keyboard
  open; switching auto honk off ends its hold the same way (Codex F1, review F12). Clearing or replacing the Highway
  route stops a pending or running auto-target (Codex F2).
- Both check everything again under the keyboard's lock, just before the first key: a jump, docking, landing, a
  panel opening or the switch-off while they waited for the other to finish means nothing is pressed (Codex F3).
  Auto honk goes back to waiting instead.
- Auto-target: "already targeted" is checked first (F11); a waypoint plotted as a route of several jumps counts when
  NavRoute.json ends at it (F2); a wrong target is said by name: "Targeted the wrong system: X. Check before you
  jump." (Q3); the map-closing tap of a stopped run is held in full (F13); the log has one line per run unless it
  fails (Q6).
- New default sequence, from the in-game tests: a camera turn before the search, 1.5 s before the first Enter, a
  zoom instead of a turn in the plot step (Q2). Camera Zoom Out needs a keyboard binding.
- Auto honk no longer blames the fire group when your own jump cut the honk short (F42).
- POST /api/autohonk takes only a JSON boolean: `"false"` used to switch it on (Codex F10).

## 2026-10-03 · The drive maths and the Highway's helpers in their own modules (fix plan, batch 3)
- outrider/fsd.py: the frame shift drive's maths (drive tables, range, fuel per jump, the fuel model, a fleet ship's
  plotter inputs, the conservative range); outrider/highway.py: the route helpers, HighwayError and the desktop
  clipboard; outrider/core.py: the shared timestamp helpers. ed_outrider.py imports them (about 400 lines lighter).
- No behaviour change: the 533 tests pass unchanged (four test references now point at outrider.fsd). The Highway's
  state and auto-target stay in ed_outrider.State, where verify.sh's offline patches reach their constants.

## 2026-10-03 · Highway page state and requests (fix plan, batch 2)
- The Highway plot form follows the current ship, its Loadout and the cargo aboard: it used to keep its first
  answer and plot with the old ship and cargo after a swap or new cargo (review F3, Codex F4). Opening the tab asks
  again.
- An older Highway or Left behind answer arriving after a newer one is dropped (a cleared route could come back, a
  smaller radius could replace a larger one): a small newest-request guard (Codex F11).
- A failed region-map fetch is asked again after 30 s instead of never; only a missing map (404) is final (review
  F14, Codex F12).

## 2026-10-03 · Highway data fixes (fix plan, batch 1)
- A ship whose Loadout's MaxJumpRange leaves out the Guardian booster (booster off, or an outfitting Loadout) keeps
  its real FSD optimal mass: the exact plotter planned about 1.5x the real fuel per jump and too many refuel stops
  (review F1). PARSER_VERSION 36: the next start re-reads the journals once to rebuild the ships' figures.
- The neutron plotter's conservative range keeps the ship's booster floor (12 ly with a 10.5 ly booster and a 10 ly
  margin plots 11.25 ly, not 6) and never exceeds the full range (Codex F5).
- Off the route, the nearest route system is the closest one, passed or not (the author's rule), and a second detour
  through the same system no longer shows a stale one (review F7).
- A jump read just after a plot finished moves the route (arrivals are compared with the position's journal time,
  not the wall clock: review F8); a respawn or a login elsewhere counts as an arrival, so it shows the detour
  (review F10).
- The map greys the route up to where you are, as the list does, after flying back along it (review F15);
  "refuel in 3 jumps" has its unit (F16); a neutron route hides the ⛽ column and the refuel legend and says "no
  refuel stops: scoop as you go".

## 2026-10-03 · Test safety and test tooling (fix plan, batch 0)
- The page smoke test needs an explicit port and refuses 8025: run bare, it used to default to a real Outrider's
  port, and it clicks and POSTs (found by the Codex review).
- verify.sh's scratch server always reads the fixture journals: an exported ED_JOURNALS used to win over the scratch
  config (review F19).
- verify.sh fails on any ResourceWarning in the unit tests (24 test set-ups left in-memory databases open: now closed)
  and on any pyflakes warning.
- tests/test_units.py (11,200 lines) is split by subject into tests/test_*.py with the shared fixtures and fakes in
  tests/support.py; one file runs alone as `python3 -m unittest tests.test_highway`.
- New guard tests: an old database (the first public schema, frozen in tests/fixtures/schema_0046634.sql) upgrades to
  today's, x/y/z backfill included; every Journals attribute a failed tick could leave wrong, and every meta key a
  re-read could double, is accounted for, with the reasons written down.
- The auto-target runner's tests run on a fake clock (instant instead of seconds), and the smoke test waits for the
  page's requests to settle instead of fixed sleeps: unit tests 46 s -> 34 s, the smoke test about 70 s -> 35 s.

## 2026-10-02 · Highway screenshot with refuel stops; two unused lines removed
- The README's Highway screenshot shows an exact-plotter route: fuel used and left per jump, a ⛽ refuel stop in the
  list and its ring on the map (the old one was a neutron-plotter route, which has no refuel stops).
- Removed an unused import (`outrider/bio.py`) and a dead assignment (`outrider/unsold.py`): pyflakes is clean.

## 2026-10-02 · Here's bio column stays readable; --simulate for screenshots
- Here: a bio item ("Bacterium 3/3 ✓ 38.9M") no longer breaks inside itself, and a compact table shows a codex
  entry as 📖 ✦ (the name in its tooltip), so a body's row no longer grows to seven lines beside an open panel.
- `--simulate`: the panels show the last known values as if the game were running (fuel from the last reading,
  else the last jump, else a full tank), for screenshots and demos. Only the display reads it; the virtual
  keyboard, the co-pilot button and the clipboard are off. Screenshots regenerated with it.

## 2026-10-02 · The Highway: auto-target the next system; vehicle fuel; a shorter README
- **Auto-target** replaces the stub (Linux, off by default): after an FSD supercharge in a route system and
  `autotarget_delay` s, Outrider presses keys through auto honk's virtual keyboard to open the galaxy map, search for
  the next system (typed with a US keymap, or pasted), plot the route, close the map and check Status.json's
  `Destination.System` (`outrider/target.py`). Keys come from the active preset's keyboard bindings (GalaxyMapOpen,
  UI_Up, UI_Select, CamYawRight...) or `autotarget_keys`.
- Guards: never docked, landed, in the SRV or on foot, in danger, with the FSD charging, a map or panel open, the game
  not live, or the next system already targeted; aborts on an unexpected GuiFocus, a timeout, a jump or a changed
  system (closing the map only if it opened it). One try per supercharge; one sequence at a time with auto honk (the
  honk first).
- The Highway tab's **Auto-target the next system** box: toggle, delay (remembered, POST `/api/highway/autotarget`),
  **test now** (POST `/api/highway/autotarget/test`: 5 s countdown, then one run; refused with the reason), the last
  result, missing bindings and the steps. Spoken results under the new alerts row **Auto-target**: "Successfully
  targeted neutron jump target X" / "Failed to target neutron jump target X".
- Config: `autotarget_entry`, `autotarget_map_wait`, `autotarget_search_wait`, `autotarget_key_delay`,
  `autotarget_keys`, `autotarget_search`, `autotarget_submit`, `autotarget_plot`, `autotarget_dry_run`.
  `python3 -m outrider.target --show` prints the steps with your keys.
- The default sequence was tuned in game with the author (2026-10-02) and targets a system end to end: UI Up then
  UI Select into the search box (UI Right went to Trade Routes), Enter twice after half-second waits (the suggestion
  lists late), a short Camera Yaw Right to give the focus back to the map, then UI Select held to plot.
- **Test now** targets the nearest known system within a plain jump, so it needs no route.
- **In the SRV or the Nomad** the fuel tile keeps the ship's tank (it read 0 t, red) and adds "Current vehicle:
  Nomad" with the vehicle's own fuel; `LaunchVessel` (the Nomad) is tracked like `LaunchSRV`.
- README trimmed (views, layout, header and fuel, the Highway) with a new Highway screenshot; every screenshot
  regenerated.

## 2026-10-01 · The Highway: too much fuel for the next jump, conservative range
- **Too much fuel:** on a live arrival in a route system, and as the fuel changes there, the next jump is checked
  against the fuel aboard (the current ship's fuel model, its supercharge in a neutron route system); past the most
  fuel that still reaches it, a warning in the highway line and the Highway header ("⚠ too much fuel for the next
  jump: ≤ 36 t, you have 140 t", summary field `heavy`) and one spoken line per system. Only for the ship the route
  was plotted for; the neutron plotter when the next waypoint is one jump away.
- **Conservative range** in the plot form (off by default; `[highway] conservative`, `conservative_ly = 5`): the
  neutron plotter gets the range less the margin, the exact plotter an optimal mass scaled so the full-tank range is
  the margin shorter. The header says "conservative −5 ly". Stored with the per-browser `highway` form settings.

## 2026-10-01 · The Neutron Highway
- A **Highway** tab (after Map): plot a route with Spansh, the **exact** plotter (every jump with its fuel and refuel
  stops, from the chosen ship's Loadout: drive, masses, tanks, Guardian booster, engineering; cargo, injections,
  exclude secondary stars, already supercharged) or the **neutron** plotter (waypoints from a range, ×4/×6 and an
  efficiency, with a range override). One plot at a time, polled every 1.5 s for up to 180 s, errors in plain words.
- The ship list is every ship flown, as of its latest Loadout (`fleet_loadouts`, journal-derived: PARSER_VERSION 35).
- One active route (`highway_route`, live-only, kept through a re-read and in backups) followed as you fly: progress
  forwards or back, **Off Route: Detour** once joined, resumed at any route system, **Highway complete** at the end.
- The list (the next 200 ahead, done rows folded; off the route the nearest route system is marked and scrolled into
  view in the pane), a top-down map, and a highway line under the tiles on Overview, Nearby and Here.
- On arrival the next system's name goes on the desktop clipboard (`wl-copy` or `xclip`), and a plain spoken line
  ("Next Neutron Highway Stop: …", refuel and boost sentences, off route, back on the highway, complete) under the
  new alerts row **Neutron Highway**, spoken but not notified by default.
- `[highway]` config: `clipboard`, `autotarget` (a stub that only logs "would target …" after an FSD supercharge),
  `autotarget_delay`, `efficiency`. Per browser: `highway` (the plotter and its options).
- The map has a background: the galactic regions (klightspeed's region map, already shipped for the bio rules) as
  soft theme-aware tints with borders and names sized by zoom, a faint glow round Sagittarius A*, and Sol,
  Sagittarius A*, Colonia, Beagle Point and your carrier marked (click to copy); a **galaxy** button; corner toggles
  for regions, names and image (per device). `GET /api/regions` serves the grid (ETag, gzip). Optionally your own
  galaxy image under it: `[highway] background_image`, `background_extent` (default X −45000…45000, Z −20000…70000),
  `background_opacity`, served by `GET /api/highway/background` (that file only, image types only).

## 2026-10-01 · The page fits the window; header tiles fold into one line; compact tables
- On a window of at least 900 × 600 (not Now) the page no longer scrolls: the header stays, the view fills the
  rest, and its lists scroll in bordered panes with sticky column headings. Overview: Nearby and This system each
  the full height, the body table scrolling above the surface map or body panel (stacked: the map or panel beside
  the table). Here: the table and the body panel scroll apart. Nearby, Samples, Bookmarks, History, Log, Materials,
  My firsts: one pane under the view's controls. Search: one pane for the forms and results. Map: the canvas fills
  the view. Smaller windows and phones scroll the page as before; a header too tall for the window falls back too.
- Page Up/Down, Home and End scroll the view's pane when nothing else has the focus; the Log fetches more when its
  pane nears the end; a row brought into view (Here's in-game target) and the Log's new rows scroll the pane.
- ▴ beside the tiles folds them into one line in the tiles' colours (per browser: `tilesCollapsed`).
- Compact tables: a table wider than its box (by fit, not screen size: a pane, the Overview's split, a phone) shows
  short forms (HMC, Rocky ice, G star, WD DA, CO₂; Nearby's status as —, 62%, ✓, ?, 🗺3; shorter headings), and if
  that is not enough, a tighter level that merges or drops low-value columns (Nearby: status under the name, notable
  under the bodies; Here: atmosphere under gravity, ls under the class, firsts under the name, mining in Bio, Now under
  Max; My firsts, Samples, History, Log, Bookmarks likewise). The full text is in the title. A table that fits is unchanged.

## 2026-09-30 · Repository layout: the outrider package, resources/, data/, docs/
- The modules moved into the `outrider/` package without their `ed_` prefix (`outrider/bio.py`, ...); their
  command lines run as `python3 -m outrider.honk --test`, `python3 -m outrider.button --listen`,
  `python3 -m outrider.bio --backtest|--update-rules` and `python3 -m outrider.unsold`.
- Shipped data (`bio_rules.json`, `mining_odds.json`, `speech.json`) is in `resources/`; your own files
  (the database, `browser_defaults.json`, `speech_banned.json`, `backups/`, `piper-voices/`) default to `data/`,
  git-ignored as a whole. Relative config paths are still relative to the repository folder.
- The notes moved from `reference/` to `docs/`, the screenshots to `docs/images/`; local scripts to `scripts/`.

## 2026-09-30 · Rig spacing ring defaults to 50 m (`be16993`)
- The surface map's rig spacing ring is 50 m by default (two rigs were allowed about 44-51 m apart in a test;
  the game draws a 50 m ring). Still a per-browser setting and `[defaults] rig_spacing`.

## 2026-09-30 · My firsts: a rescan checklist for lost first discoveries (`dd66f2e`)
- "within N ly" beside "show lost" lists systems whose data went down with a ship, nearest first.
- Rows stay while you rescan: amber part-way ("rescanned 5 of 12", "1 map to redo"), green when everything is
  back, gone once sold. Hover a part-way row for what is left, with values.
- Lost scan, lost map and lost total columns, sortable.

## 2026-09-30 · Review fixes and additions: Rhino state, sales, fuel, voice, firsts watch, security (`567e7ae`)
- Surface map fixes: the Rhino is remembered when you step out; rigs are lost on death, SRV loss and relog.
- Sales and exobiology: per-run x5 pricing, multi-part Vista visits counted once, the "data still aboard" line
  waits 90 s; fuel constants for every drive size (the Caspian's Mk II included), engineering applied at once.
- Cross-site GETs refused except `/api/status`; a "rigs still out" warning when you dock the Rhino.
- Status report leads with the targeted body; optional "mapped" call-out; mining search (Local); core module
  health under a configurable level; "This session" on Now.

## 2026-09-30 · Surface map on Now; Rhino rig marking with the co-pilot button (`829c786`)
- A heading-up map on Now below 1,000 m: you, the ship, bio samples with spacing rings, rigs 1-6, saved mining
  sites and targeted mining locations, with a legend.
- In the Rhino the co-pilot button places a rig 7 m behind you or picks up the one you are next to; collections
  are added to the rig from the refined tons.
- Rig leash warnings at 3.5 and 4.5 km; mining sites per body in Materials.
- New settings: `surface_alt`, `rig_spacing`, `surface_map_min`, `surface_map_strip`, `rig_warn`.

## 2026-09-30 · Mining locations in Here, what you mined per body, unsold-after-sale alert (`7fa44ec`)
- A ⛏ column in Here with each body's planetary mining locations and a survey-odds tooltip (EDFM, CC BY-SA 4.0).
- "Mined previously": what your SRV refined on each body, rebuilt from the journals.
- A spoken line when a sale leaves data aboard (50 systems per page), and the same after a Vista Genomics sale.

## 2026-09-29 · Server audio, hush and co-pilot button, fuel model, firsts watch, verified backups (`fc9cfcb`)
- Speech and sounds can play on the PC itself; hush for 10/30 minutes or until the next jump; a read-only HOTAS
  co-pilot button; ban lines from the Spoken lines list.
- Fuel: laden range, fuel per hop and jumps left from your own jumps, a top-up warning.
- Exobiology priced run by run with an x5 check at each sale; a watch for unsold firsts someone else scanned.
- Backups checked before rotation; `--restore` and `--list-backups`.

## 2026-09-29 · Three review rounds of fixes, new call-outs, rolling backups and a safer server (`1bc2993`)
- A Host/Origin request guard: no cross-site key presses or journal reads.
- Fixes for repeated or wrong alerts, wrong values after sales and re-scans, and journal state after a failed read.
- One speaking window and a priority speech queue; many new call-outs (FSS debrief, approach, welcome back,
  ship-loss debrief, streaks); rolling automatic backups with a journal archive; portable settings.

## 2026-09-28 · Voice personalities, auto honk, bio colour check and a voice lab (`003c7be`)
- `speech.json` with 50 lines per alert in business, sarcastic and sweet, optional swearing versions, your names.
- Auto honk on Linux, pressing Primary Fire's binding from the controls preset.
- Colour-variant checks for exobiology; `voice_lab.py` for trying voices.

## 2026-09-28 · Review fixes; alerts, speech, ledger and exploration tools (`cac9b24`)
- Fixes for 44 review findings, including values outside the sphere and tailing that could freeze.
- Alerts with sound, notification and speech (Piper or the browser); long-polled updates.
- Trip ledger, top finds, ranks and career stats; Left behind, nearest sellers, jumponium, next stop, Now mode.

## 2026-09-28 · Exploration log, samples, materials and schematic (`a2410fe`)
- New views: Samples, Log, Materials; Here as list, tree or schematic.
- Search for unfinished exobiology; radius dropdown; highlight levels for valuable bodies and bio.
- Fixes for fresh installs failing on the first Scan and for Spansh genus codes.

## 2026-09-28 · Lost firsts hidden by default (`5de0b9f`)
- My firsts hides systems whose firsts were lost with a ship unless "show lost" is ticked.

## 2026-09-28 · README with screenshots; search radius step fixed (`710cfce`)
- A README with screenshots; the Search radius box takes any number.

## 2026-09-28 · Initial commit (`0046634`)
- First public version: Nearby, Here, Map, History, Search and bookmarks from your journals and Spansh, with
  the unsold-data estimate and the exobiology predictor.
