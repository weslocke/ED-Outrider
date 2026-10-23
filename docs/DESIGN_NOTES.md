# Design notes: deliberate decisions and known limits

Each line is a choice the project made on purpose, or a limit it knows about, with the reason. Don't
"fix" these as bugs without reading the reason. A fork is free to decide differently: these are the
upstream project's choices, not rules of the game.

## Deliberate decisions

- **No keyboard shortcuts.** A deliberate upstream choice, declined more than once; clickable things are reachable with
  Tab and act on Enter/Space instead.
- **No VoiceAttack integration.** Not used upstream; the co-pilot button and the page cover the same ground.
- **The tick stats only the journals still changing** (2026-10-12, S18, `Journals._scan_dir(quick=True)`). Over a
  network share every stat is a round trip, and a long history is thousands of files a second. The folder is still
  listed every tick (a new journal is read at once); a file is settled when its size was the same for
  `JOURNAL_SETTLE_STATS` stats in a row (not when it reaches its offset: a journal cut without its final newline never
  does), and only the unsettled ones and the newest two are stat'd; every file once per `JOURNAL_FULL_CHECK_S` (60 s).
  So a sync tool that appends to an older journal is read up to a minute late. An unreadable file never settles (it is
  retried every tick, as before); a rolled-back tick forgets what settled.
- **Summaries cached on the reader's own counters** (2026-10-12, S17 and S66). `leaving_summary` (asked for on every
  poll with a target set) is kept per system until `Journals.data_seq` moves (every write it reads: scans, codex,
  deaths, sales; `mark()`), the system's `locate` answer changes (its region decides "new to your codex") or the bio
  rules are updated (`bio_rules_gen`); not on `scan_version`, which moves later in the tick. The carrier's fold is
  kept until its own history changes (`carrier_version`), not on every change to the ship's hold.
- **A ship's build in EDSY and Coriolis** (2026-10-14, `outrider/shipyard_links.py`): EDMC's format, matched step by
  step from its `plugins/edsy.py`, `plugins/coriolis.py` and `plugins/common_coreutils.py` (`shipyard_url_common`),
  nothing copied: the Loadout reshaped as EDMC's `monitor.ship()` (canonical lower-case names, modules one per slot in
  its order, no Health or Value, a laser's 1/1 ammo dropped, a blank ShipName left out, the hull's figures left out),
  then compact JSON with sorted keys, gzip, URL-safe base64, '=' as `%3D`. Two differences, both on purpose: the build
  is stamped with the Loadout's own time, not the moment of the click, and the gzip header's time is 0, so one build
  always gives the same link (tests pin it). The links are built on the server from each ship's latest Loadout, kept
  whole in `fleet_loadouts.loadout` (journal-derived: the release's one re-read fills it, PARSER_VERSION stays 51); a
  ship never boarded since the journals begin has none, as nothing records its modules. Privacy differs by site:
  **EDSY's link keeps the build in the URL's fragment** (after `#`: the browser never sends it to a server; EDSY's
  page reads it), **Coriolis's sends it as a query parameter** (`/import?data=`: it reaches coriolis.io with the page
  request, as with EDMC). Either way only the ship's modules and engineering go, never the commander's name. In the
  Android app a `target="_blank"` link opens in the browser (its WebView hands every other-origin navigation over).
- **The CMDR tab is journal-derived** (2026-10-12, `outrider/commander.py`; read from the database since
  2026-10-14, PARSER_VERSION 51). `Journals.handle_commander` folds its lines as the reader meets them, like every other
  part: meta keys (`COMMANDER_META`: reputation, Powerplay, squadron, the stored ships, stored modules, ship locker,
  suit loadouts, engineers, missions), each `fresh()`-guarded so a legacy folder read late cannot put back a sold ship
  or a handed-in mission, and `play_activity` (the fighting and mining per login). All of it is in `RESET_JOURNAL_DATA`
  and rebuilt on a re-read; none of it is live-only. A tab's GET is a quick read on the event loop, never a scan of the
  journal files (which read each file whole, the live folder only, and missed every older stored module). The view
  snapshots what the game lists whole and folds the changes it logs between: the fleet from the last StoredShips plus
  ships bought, sold, swapped, sent for and renamed (as `outrider/inara.py` reads them), each ship's value from its
  latest Loadout; suit loadouts created, changed, upgraded or deleted; the ship locker from each ShipLocker line that
  carries its lists (the game writes them at login and at most changes; some carry none), then ShipLocker.json whenever
  it is newer, read in the tick only when its modification time moves (as Cargo.json). Stored modules: the last
  StoredModules list, then ModuleStore, MassModuleStore, ModuleBuy's `StoredItem` (the old module stored, not sold),
  ModuleRetrieve (its `SwapOutItem` stored), FetchRemoteModule (in transit until its `TransferTime` has passed, then
  where you sent for it; a list written meanwhile keeps that) and ModuleSellRemote, until the next list replaces the
  fold (`fresh()`-guarded like the rest); ModuleSell and ModuleBuy's `SellItem` sell from the ship and leave storage
  alone. A module stored since the list has no value until outfitting lists it. Checked on the author's journals
  (2026-10-14): replayed, the fold equalled the next list 341 times in 345; of the four, two were modules (probably free with the ship) the game
  threw away when swapped out (the line does not say so) and two lists held a module no line had moved there (a gap in
  the journals). ModuleSellRemote and MassModuleStore had no real line: Frontier's manual. A ship's hot flag (wanted)
  is the latest line that says it, for every ship the same way: a StoredShips entry's `Hot` (always there) and the
  Loadout's `Hot` for the ship you fly, which by Frontier's manual is there "if wanted at startup": the login's Loadout
  without it says not hot, a later one counts only when it has it. No real journal had a hot ship or a Loadout with
  `Hot`; the page marks one with a red ⚖ (the theme's `--bad`). A mission accepted before the journals is kept by its
  name alone. The login-time snapshots (Missions, Reputation, EngineerProgress, Powerplay, SquadronStartup,
  ShipLocker) are in `LOGIN_EVENTS`: loading the game is not play, so they never move `last_play_ts` (History's
  session end, the "away" greeting). So is `Music` (the main menu's track, written at every launch: counted as play,
  it made the time away minutes, review 2026-10-20 M2). Mining in the SRV (the reader knows the vehicle) is counted apart from the ship's.
  The Sessions tab goes by days like the rest (History's default): the logins of the last 30 days, 40 at most.
  Ranks and statistics are as of the last login (the game writes them then); the credits and the carrier
  are the Commander and Carrier tiles' own (one owner each). What exobiology's next rank still takes is an estimate:
  the post-Update-14 step (the Frontier forum, 2 Jan 2023; Elite IV and V uncertain) times the share the game's own
  percentage leaves, never Organic_Data_Profits against the totals (checked on real journals: the bands' steps hold
  within 3 %, the totals not); every other rank shows its percentage only (no trade or exploration figures could be
  checked the same way). EngineerProgress' Rank is the highest grade an engineer crafts for you (real journals: no
  craft above it). A tab is asked for again when a journal line it reads is handled (`commander_version`), not on
  a timer. The blueprint table is a copy of community data (EDCD's coriolis-data at a pinned commit, recorded in the
  file's `_readme` and `source`; the data is Frontier's, under its terms), not the game's own: a recipe Frontier changes
  is wrong until the table is rebuilt. One row per kind of module and blueprint, its engineers that kind's (a pulse
  laser's Overcharged is offered by other engineers than a cannon's); the material names are matched to the journal's
  by Outrider's own `outrider.materials` table (FDevIDs, which has no licence, is not used). A table that cannot be
  read says so on the tab, not "Nothing matches". The field names were checked against real journals (2026-10-14:
  every event with lines on record; DeleteSuitLoadout, RenameSuitLoadout, LoadoutEquip/RemoveModule, UpgradeSuit,
  UpgradeWeapon, ShipyardSell, SellShipOnRebuy, PowerplayLeave/Defect and the squadron's leaving have none there and
  follow Frontier's journal manual). A Missions list's `Expires` is the seconds left, except for a colonisation
  mission, whose `Expires` is the time itself (a Unix time). Links go from the CMDR tab outward only (the career to
  History, a short material to the Materials tab and the nearest trader); the header tiles stay informational. No
  voice lines: a mission about to expire is marked on the page only.
- **The CMDR tab's Earnings: exploration, exobiology and mining, exact** (2026-10-14, NEXT-VERSION #7 from javeliuswt's
  GitHub discussion #7; the author's choices of that day; `outrider/earnings.py`). What Universal Cartographics, Vista
  Genomics and a market for ore you mined paid you: trade, missions and bounties are left out (an explorer's and a
  miner's income; Cargo and trading and the Sessions tab cover the rest). Every figure is the game's own, from each sale
  line, per sale, month, species, station and ship. Outrider's estimates only where nothing else answers, always under
  Estimates or "Lost (estimate)" and labelled: the systems sold by its value of your scans (the game pays per page of
  50 systems, never per system) and the data lost to deaths. A total is `TotalEarnings`, what you were paid: a hired NPC
  crew member's share comes off it (base + bonus − total, the totals' `crew`, said on the figure and in a note; 9 % of
  every cartographic sale in the author's journals until the crew was fired, none of Vista Genomics'). Months are UTC,
  as the journal's times (a local month would move sales across months with the clock and differ between devices).
  History's Ledger stays the owner of per-trip figures and of the losses: Earnings links to History › Trips and takes
  the Ledger's `losses` as they are, never counting them again. The ship of every jump, first scan, sample run and
  sale is the latest `Loadout`'s (a line from before PARSER_VERSION 52 or read out of order has none: "?"). Kept per
  period until the reader's data moves (`data_seq`, `commander_version`): on the author's three years of journals
  (2026-10-14) the first answer took 0.7 s (most of it the Ledger), another period 30 to 80 ms, a repeat nothing.
- **Mining income is the ore you mined, followed until it is sold** (2026-10-14, the author's rule; `Journals.note_mined`,
  meta `mined_stock`, `mining_sales`). The journal's `MarketSell` never says whether the tons were mined or bought, so
  the reader keeps the mined tons aboard: every `MiningRefined` adds 1 t (the ship's refinery or the SRV's), a sale
  counts as mining up to what that holds of its commodity (its share of `TotalSale`) and the rest is trade, left out; a
  jettison takes its tons off, a death empties it. Your carrier keeps a mined stock of its own (meta `mined_carrier`,
  the author's call the same evening: on his journals about half the mined ore went through the carrier, so leaving
  it out halved the figure, 0.89B of about 1.72B): a transfer to the carrier moves the mined tons there, one back to
  the ship moves them back aboard (only while docked: the same event moves cargo between the ship and the SRV on a
  planet, which moves nothing, review M6), mined ore sold to your own carrier joins it, a new carrier starts empty.
  Tritium put in the carrier's depot comes off the mined tritium first (review L2). One rule,
  two places: the Sessions tab's
  Sold reads the same figure, in the login the sale was made in. Sales of mined ore to your own carrier are left out
  (your own money changing pockets); cartographic and exobiology data sold at your carrier counts (the game pays it).
  Known gaps: ore handed in to a mission (`MissionCompleted`, `CargoDepot`) or lost with a destroyed SRV stays counted
  as mined, so bought tons of that commodity sold later can count as mined up to it; ore other players buy from your
  carrier is not in your journal, so the carrier's mined stock is capped, when ore comes back aboard, at what the
  carrier held of it then (`Journals.carrier_holding`: the carrier fold up to that moment, your Market.json reads and
  Recounts included; on the author's journals osmium's 176 t fell to the 34 t his market showed). Between two market
  reads the cap can be too high, and the stock shown between transfers is not capped. A line read out of order (a legacy
  folder read late) changes nothing (what was aboard then is not known).
- **Green gas giants are a guess, said as one** (2026-10-12, `outrider/ggg.py`). The seven-layer ladder model is a
  community reconstruction (Canonn's issue 222, 2026-10-05), not the game's code: a match is "potential", never a fact,
  and a codex entry replaces it. It needs the journal's own temperature (green windows can be 0.00002 K wide): yours
  and Spansh's records keep it (checked: Spansh's equals the journal's); its class rules are a table. Written from the
  published rules; checked against Canonn's implementation on 21,747 giants (the author's 1,735 and 20,000 made up):
  the same verdict every time. The author's 1,017 predictable giants: none called green, none in the codex. Not a
  curiosity (it would blend in there): its own mark, Now line and alert.
- **✦ / ✪ on star and planet types go by EntryID, shown only** (2026-10-12, `outrider/codex_bodies.py`). The codex
  logs each body type once per region, but its localised names are ambiguous for planets ("Terraformable", "Standard
  gas giant"), so the table maps a body's class, luminosity, terraforming and atmosphere to the game's IDs, read from
  the author's journals and EDDN's codex traffic. A type with no ID seen (a class II giant) gets no mark rather than a
  wrong one. Shown on the page, never spoken. Your codex is your journals' codex lines plus every type you have
  scanned in a region (not off a nav beacon): the game logs a type only the first time you scan one there, and a
  commander's codex is often older than the journals kept, so a type scanned without a line was logged before.
- **Geology ✦ marks a set, and only what EDDN showed** (S22, 2026-10-12, `outrider/codex_geo.py`). A volcanism does not
  name one feature: of 284 geology entries EDDN carried on 81 scanned bodies, each volcanism logged one of two to four
  (rocky magma: the sulphur dioxide fumarole or gas vent, the silicate magma lava spout, on 2 of 6 bodies the silicate
  vapour gas vent). So a body's candidates are a set and ✦ means "any of them would be new here". Combinations never
  seen (non-Ice water and CO2 entries, the Ice forms of SO2 and silicate vapour, rocky ice bodies) get no mark rather
  than a wrong one. Your codex's geology is its journal lines only (a scan logs none), so geology logged before your
  journals can show ✦: a known limit, as for biology. The codex range is 1400000-1400499: the anomalies share 14xxxxx.
- **Species reported on a body cost one Spansh search per system a day** (S23, 2026-10-12). The plan hoped Spansh's
  dumps carried each body's `landmarks`: the probe (`scripts/landmarks_probe.py`) found they do not, while its body
  search does, with the colour (`variant`). So the system you are in is asked once a day, only when its bodies have life
  (a search out to 1 ly of it: a max of 0 and a system_name filter were ignored), and the answer kept in
  `spansh_reported` (live-only). Here shows them as facts (👥, the reported colour), never mixed into the guess or its
  value. Not yet: the arrival brief, the FSS debrief and the overlay's Target panel naming them.
- **Your runs rank a genus's species in the hover only** (S24, 2026-10-12). The guess still names the likeliest by value;
  its hover adds which species your completed runs found on bodies of the same class, atmosphere and 25 K band, in the
  same region once you have 5 such runs there (fewer: every region's). The backtest replays your runs in time order
  (the journal folders are read one after another), each ranked only by the runs before it: on the author's journals
  (643 runs, 2026-10-12) the likeliest by value was right 20 of the 32 times a genus had several candidates, your
  runs' favourite also 20 of 32, so `HISTORY_PICK` stays off and the value pick stays (the value is the maximum
  either way, "up to").
- **🔍 nearby on the checklist asks Spansh, nearest first** (S29, 2026-10-12). The body search's
  `{landmarks: [{subtype, variant}]}` filters by species and colour (checked against what came back: 144 Mulberry and
  149 Lime of 741 Bacterium Vesicula near Colonia), and every hit is checked again, since Spansh ignores a filter shape
  it does not know. Reported only: a species nobody uploaded shows "No body within 20,000 ly". Not yet: 🎯 on its rows
  (it waits for S31's route "system") and the Geology checklist's half (Canonn's per-entry site dumps, which
  geo_codex.json does not link).
- **Search's green gas giant option asks Spansh for every giant it can judge** (S27). Spansh cannot filter on the model,
  so one query lists the classes with a usable rule (Class I, III, IV, the life-bearing giants, water giants) and the
  model checks each answer (search results carry the mass, radius and the journal's temperature). Over a big radius that
  is many giants: the usual "only complete out to" note applies. The voice's "nearest green gas giant" reads only
  Outrider's cache (GET `/api/ggg`, also an AI tool): no Spansh request from a question.
- **Discoveries are said once, and only the rare ones** (2026-10-11; Settings → Alerts groups them under
  Discoveries, each with its own switches). Rare stars (black holes, Wolf-Rayet, carbon, O, Herbig Ae/Be,
  supergiants, the rarer white dwarfs; neutron stars and ordinary giants are too common), FSS signals worth a detour
  (Titans, Guardian beacons, generation ships, listening posts; tourist beacons, number stations and memorials are
  shown, not said; ordinary megaships are traffic and left out), surface sites (Guardian, Thargoid, the planetary
  anomaly; "other" is shown, never said: nobody knows what it is), notable stellar phenomena (the first FSS listing
  in a system with none on record). Curiosities get one line per system, never the list ("check your panels"), once
  per system ever (meta `curious_said`, live-only, the last 2,000 in the order said).
- **Rings to mine: the page chooses, the server only reports** (2026-10-18, Settings → Mining). Every live Scan of a
  ringed body is a "ring" moment (its ring types and Scan's ReserveLevel), once per body and visit (`Journals.rings_said`,
  in memory and in the checkpoint, cleared on arriving somewhere: the Detailed rescan after mapping says nothing, a return
  visit's AutoScan says it again); which types matter is the browser's `miningRings`, so the server needs no setting. A
  body re-entered without a new Scan (already resolved in an earlier visit, no AutoScan) is not said: there is no event
  to say it on. Belts are left out (they hold no hotspots). The ringed bodies of one payload are one line (a nav beacon
  resolves a system at once); FSS resolves come seconds apart and are said one by one. The reserves are said only when
  pristine or depleted (they matter for laser mining; major, common and low are on the card). Hotspots have their own
  record (the mining stints, below).
- **Mining stints and their hotspots** (mining B-D, 2026-10-19; the review of 2026-10-20). A stint runs from a drop
  into a ring (`SupercruiseExit` or a login's `Location` with `BodyType: PlanetaryRing`) to leaving it: `MINING_CLOSE`
  is SupercruiseEntry, FSDJump, CarrierJump, Docked and Died, **not a logout or LoadGame**: the login's Location says
  whether you are still in the ring (miners relog to respawn the rocks). Back in the same ring after more than
  `MINING_RELOG_GAP_S` (15 min) is a new stint that keeps the hotspot. `mining_stints` is journal-derived;
  `mining_hotspot_drops` (the hotspot a live drop was aimed at, from Status.json's Destination, which no journal line
  names) is live-only and joined by (system, ring, the stint's start). A stint from a legacy folder read late has no
  ship (not today's). A mining ship is a refinery, a prospector controller or a mining / universal multi-limpet
  controller, never a collector alone (explorers carry one). The page's first payload baselines the mining warnings
  (`miningBaseline`): a new window never repeats "the hold is full". Hold-full's "where to sell" never names your own
  carrier as a place to sell. The limpet reminder stays quiet while the hold's contents are not known (a count-only
  Cargo with more aboard than the lines known). A mining session's **Where** (CMDR → Sessions, the author,
  2026-10-20) is the place it refined the most tons in, the others in a "+N" hover: each mining line's place is set as
  the line is read (the SRV's body, else the open stint's ring, else the system), so it follows the session's own
  counts, and a line older than what is known (a legacy folder read late) has none rather than a guess.
- **Boxels: what can and cannot be known** (2026-10-11, `outrider/boxel.py`). A procedural name's boxel, its centre and
  any of its systems' id64 are computed from a known system's position (checked: 2,763 of 2,763 of the author's
  standard-sector systems), so auto-target checks a never-visited system by id64. A boxel's size (how many systems)
  cannot be known: the list offers TRY_ABOVE numbers past the highest known and marks "probably the end" when a
  higher one cannot be targeted. Sector names are not generated: recommendations cover sectors you have a system in.
  Hand-authored sectors use other origins: their names parse, their geometry is not claimed. The auto-target opt-in
  needs a kept boxel (following whichever boxel you jump into would take over every target). A boxel is complete by
  itself once its end is known and every number below it visited; Done marks one finished either way (meta
  `boxel_done`, undone any time): no Next, out of the recommendations. Skipping systems already fully scanned is
  opt-in (meta `boxel_skip_known`): a system Spansh knows was often only honked in passing and keeps its bodies'
  first discoveries, so only one with every body reported is passed over. The head shows the highest known number,
  yours or Spansh's.
- **Nothing is uploaded unless the player switches it on.** EDDN, EDSM and Inara (Settings → Uploads, off by default)
  are the only uploads. Every other outside call is a read-only lookup: Spansh, EDSM, GitHub (the bio rules, ExploData's
  colour tables and the update check), Hugging Face for voices (the page plays a voice's ▶ sample from Piper's samples
  site), Canonn (its codex reference once a day; the page loads the checklists' pictures from Canonn's storage), EDAstro
  for the DSSA carrier list when the Nearest finder opens. The one exception is the AI layer (off by default,
  `[assistant]`): it sends the question and the read-only tools' answers to the endpoint the player configures, so it is
  not a read-only lookup. This is the one full list.
- **EDSM has no test endpoint**, so its developer switch is a dry run (`OUTRIDER_EDSM_DRYRUN=1`: requests built and
  logged to `data/edsm-dryrun.jsonl` without the key, nothing sent; the rows end as `dry` and are never sent later).
  EDDN's is its `/test` schemas (`OUTRIDER_EDDN_TEST=1`). Neither is a setting.
- **Inara keeps the whole commander profile, as EDMC's Inara upload does** (the author, 2026-10-11; plan in the
  author's notes): a player who uses Outrider as their only connector must lose nothing there, so travel, credits,
  every rank, reputation, inventory, ships and fleet, community goals, missions, combat, friends and suits all go
  (`outrider/inara.py`). Inara asks apps to batch and never send the same thing twice, while the game rewrites ranks,
  cargo, the ship locker, loadouts and suit loadouts constantly: each snapshot goes only when it differs from what that
  commander's profile last got (meta `inara_sent`, live-only, in the tick's checkpoint), and the inventories only when
  a batch goes (a jump, a docking, the end of the login, a shut-down), never on a pickup. Credits are the game's own
  figures at login (LoadGame, Statistics), once per session: Inara warns that sums worked out from the journal are
  wrong (crew wages). Never the fleet carrier (the API has no carrier hold) or the SRV's cargo. One request every 35 s
  at most (EDMC's pace). Its developer switches: `OUTRIDER_INARA_DRYRUN=1` (as EDSM's) and `OUTRIDER_INARA_DEV=1`
  (`isBeingDeveloped`, for a test account). Inara whitelists each app by its name: "ED Outrider".
- **Two apps sending to Inara can get the key revoked**: EDMC's Inara upload on this PC holds Outrider's (as for EDDN
  and EDSM); EDDI, EDDiscovery and EDDLite cannot be seen, so the page and the guide say to switch Inara off there.
- **Survey odds are odds, not contents.** The mining tooltip shows what a community survey found at that kind of
  ground; the game never says what a location holds.
- **No hand-logging of mining location contents.** Considered and left out for now; "Mined previously" records
  what was actually refined.
- **Rhino rigs are marked with the co-pilot button** until the game logs deploy and pickup; the record is
  Outrider's, not the game's, and is labelled so.
- **Exobiology predictions say "up to".** The genus is usually right, the species sometimes not; nothing is
  ruled out on bodies not found yet.
- **Values are estimates** from the community formula (it matches EDDiscovery's), bonuses included; no extra
  clamp on planet values.
- **"Not on the page" means nobody with an uploader reported it,** not "certainly undiscovered".
- **Alerts only for the out of the ordinary.** Routine systems stay quiet (or get a soft two-note sound when
  that is ticked).
- **Danger lines are said plainly** (business personality, no swearing) by default; profanity is opt-in.
- **The voice uses names the player picks,** never the commander name (often unpronounceable).
- **One window speaks** with the page open in several, so nothing is said twice.
- **Auto honk is off until ticked,** because its key presses go to whichever window has focus.
- **The co-pilot button only reads the device,** never grabs it; unbinding it in the game is the player's job.
- **The co-pilot button's layout** (the author, 2026-10-08): flying the ship, a tap targets the next route system
  (the survey / trade route's first, then the Highway's; "nothing to target" said in the personality when there is
  none, with the last reason found), a double tap is the status report, a hold the hush; out of the ship a tap does nothing; the Rhino keeps rig
  marking. "Say again" left the button (the page keeps it). A tap is only known once `double_ms` (400 ms, was 350)
  passes, then 0.5 s more before any key; a press in that half second cancels the run and counts as the slow double
  tap it was (the status report), so a slow double tap never opens the galaxy map.
- **The co-pilot tap targets every "next system"** (the author, 2026-10-12, S76), in this order: the survey / trade
  route's next (past the systems you finished, S12; a trade route's first stop in another system, as its clipboard copy); the Highway's while you are on it (at a route system, its start included); the boxel being explored
  (its Next, the same run as 🎯 beside it, so a name the galaxy map cannot find marks the boxel's probable end); the
  Highway's off the route (its closest system, or its start before you joined it); last, the header's next stop (S31,
  a system you chose: a complete route counts as none, so it comes through). A route you are on stays first;
  one you left for a detour into a boxel does not hide the boxel, and comes back once the boxel has no Next.
- **One rule for every 🎯** (the author, 2026-10-14): a 🎯 shows only on the game PC AND where auto-target can work
  there: the virtual keyboard available and no key it needs without a binding (`canAim`, page.js; not the "target
  automatically" switch). It is checked once, in `hwyAimBtn`, which every 🎯 goes through: a route's rows and its line,
  the carrier's, a boxel's Next and rows, S31's `sysAimBtn` (bookmarks, the next stop, Nearest rows, checklist finds),
  Nearby's rows; the Map's click and card use the same test, a failed row's ⟳ Retry too, and Plot Route's "🎯 target
  next" is disabled by it. Before, S31's 🎯, the carrier's and a boxel's checked only for the game PC, and a route's
  rows not even that (CSS hid them on a server): a 🎯 that could not work was a dead button, and a page full of them
  (Nearby's column) worse than none. Nearby's 🎯 sit left of the names in a slot of their own width, so they make one
  column and the names stay in line.
- **🎯 and Plot route anywhere** (S31): 🎯 on a bookmark, the header's next stop, a Nearest row, a checklist find, a
  Nearby row and a Map point aims at any system Outrider can name by id64 (route "system": `locate`, else the Map's last answer, the next
  stop, your carrier); the id travels as a string, never a JSON number (over 2^53 it would round). Your own system is
  refused. Plot route fills Plot Route's To and opens its form, and plots at once only when no route is followed:
  with one, Plot is your click, since a new plot replaces the route you follow. The Nearest finder's older "Plot here"
  keeps plotting at once with the plotter chosen.
- **A click on the Map targets the system** (S72, the author) when auto-target can work on this PC (the virtual
  keyboard and its bindings, on the game PC: not the "target automatically" switch), else copies its name; the card
  and the hint say which. Your own system is copied; a touch shows the card, with 🎯 Target and Copy name.
- **Search and the Nearest finder around another system** (S49): Around is where you are, the game's destination (the
  end of its plotted route, else its target), your carrier, the header's next stop or a system by name. GET
  `/api/search` and `/api/nearest` take only a kind or an id64 (`State.search_origin`: `locate`, else what the page
  lists; read only), and a typed name is found by GET `/api/find` first, which may ask EDSM or Spansh and cache it:
  `/api/nearest` stays read-only for the AI's tools. The distances are from there, each row's hover says how far from
  you; "here" is still where you are, and the finder gives no jump count from elsewhere (your laden range says nothing
  of jumps from a place you are not in). The choice is per device, with the rest of each one's filters.
- **Nearby around another system** (2026-10-14; the ideas of Rainmangames' PR #8 "Lock System", closed, rebuilt on
  S49's Around). Nearby's sphere is around you, or around a chosen centre: your destination, carrier or next stop
  (followed: a new sphere when they change), "this system" locked where you are, or a system by name (both kept as fixed
  coordinates). The choice is the server's (meta `near_around`, live-only: it survives a restart and a re-read), not the
  browser's like Search's, because the sphere is one per server: every window and the tablet must agree on what it
  lists. Distances keep S49's rule: Dist is from the centre, a From you column and the jump count from you (each row
  carries its xyz, so From you follows your ship without the server rebuilding rows); what reads "from you" elsewhere
  (the target line, scoop hints, the auto-target test's nearest system, the AI's nearby tools) uses that, and the
  horizon line and the AI's nearest unvisited say nothing while the list is elsewhere (their claim, "nothing closer is
  reported", holds only for a sphere around you). A centre that names nothing now (no target, no carrier) falls back to
  you and says why.
- **Spansh is asked when the centre changes, and on ↻ only** (the author: go easy on Spansh). The PR refreshed a locked
  area every 10 minutes; a free service asked again and again about a sphere that rarely changes is the cost we chose
  not to pay. ↻ asks no sooner than 2 minutes after the last ask (`NEAR_REFRESH_GAP_S`) and never while a search runs.
  Arriving in a system inside a pinned sphere asks nothing: Spansh learns of your scans only later, through uploads, so
  the system joins the list at once as your own (Spansh's answer did not list it) and your scans fill its rows as
  anywhere. Known limit: away from the sphere, the system you are in is not one of its rows; Here, the briefing and the
  overlay read it as any system outside the sphere (the cache, the target's lookup, Here's on-demand fetch). The 75 and
  100 ly radii stay out (a 100 ly sphere is up to 64 times a 25 ly one) until Spansh's maintainer agrees;
  `[server] radius_choices` can still offer them.
- **Nearby's filters are per device** (the mass code, "No scan data only"): a view's filter, like show visited.
  "No scan data" means no body reported by anyone (Spansh's "no scan data", never reported, not looked up).
- **The Map draws the route ahead** (S50): the game's plotted route after you, then the rows of the route Outrider
  follows (the survey / trade route's or the Highway's; with both, the one plotted last, as for the clipboard), from
  where you are on it, dashed, with ◎ on its next stop (else the header's next stop). At most 300 points
  (`MAP_ROUTE_MAX`, the game's route first); the map's systems stay cached per place and radius while the route is
  worked out at each fetch, which a new plot or a new next stop asks for.
- **The voice plots far places** (D4, option A, the author): "nearest station" (or carrier, Vista, a trader...) also
  plots a neutron route to the place it names when it is further than `[highway] voice_plot_ly` (on, 500 ly), to its
  system, never the station; never while a route you have not finished is followed or a plot runs ("You're following
  a route, so I didn't plot one"). A fixed command acts, as hush does; the AI's tools stay read-only. A route plotted
  by voice is like one plotted on the page (auto-target follows it the same way).
- **Listens on 127.0.0.1 by default; a password is optional.** Opening it to the network is an explicit setting; the
  Host and cross-site guards stop other web sites, not people on your network. `[server] password` stops those: a
  device that is not this PC needs a session (the `outrider_session` cookie, or `Authorization: Bearer` for the
  Android app's own calls). Loopback never does, so the desktop page, curl, OBS and a local MCP bridge work as before;
  but a loopback request carrying a forwarding header is a reverse proxy on this PC serving another device, so it
  needs a session too (`outrider.auth.from_this_pc`; wrong passwords count against the client the proxy names). No
  setting: nothing on the PC itself sends those headers (review 2026-10-08 #3: the password was bypassed).
  A token is `<id>.<HMAC>` under a key made from the password and a per-install secret (DB meta `session_secret`),
  so sessions survive a restart with nothing kept in memory, all end when the password changes, and signing out
  revokes one id (meta `revoked_sessions`, the last 500). Plain http: the password crosses the network in clear,
  and the docs say so rather than pretending otherwise (TLS on a LAN means certificate pain for little gain). Five
  failed sign-ins a minute per address, then 429. `/api/version`, the sign-in page and calls, the tab icon and
  `OPEN_GETS` stay open (the app must learn whether a password is wanted before it has one).
- **Settings writes the config file** (the author, 2026-10-03: Outrider is becoming an always-on service). Server
  settings lists every key `config_text` knows, so nothing is left out and no second list drifts; a save edits only
  the changed keys in place (the file's comments and unknown keys stay), keeps the old file as `.bak`, and writes
  nothing unless the result reads back and settings_from finds nothing new wrong. Server settings' changes apply at
  the next start (no live reload yet); the Settings → Uploads switches apply at once and are written into the file too. Secrets (the password, the AI key) never leave the server.
- **The tablet layout is the same page, not a second app** (PLAN-tablet phase 3): `/tablet` serves page.html with
  `body.tablet`, and page.js draws a shell round the views it already has (its rendering, most of some 9,000 lines, is
  not worth duplicating). Themes began on the tablet (the author, 2026-10-03); the desktop page has had its own picker
  since 2026-10-04 (the next note). LCARS is a theme, not the structure: the shell's parts are neutral and every look is custom properties, and
  Elite and Babylon 5 are stylesheets of their own (evoked, never a game's or the show's assets), with one exception
  the author chose: an emblem under the page list in the Elite, Babylon 5 and Star Wars themes (static/emblems/,
  each under the terms in its CREDITS.txt: Frontier's media usage rules for Elite, public-domain fan redrawings and
  Wikimedia Commons files for the others). Local copies only: the Android app blocks anything but Outrider.
- **Desktop themes are the tablet's, chosen per browser; the Default stays as it was.** One stylesheet per theme serves
  both (the tablet's rules under `body.tablet`, the desktop's under `body:not(.tablet)`), so a theme cannot drift
  between the two. The themes are dark; only the Default follows the system's light mode. A theme dresses the frame
  (title, tabs, labels, dialogs) in its display face and leaves the tables and lists in a plain one: the condensed and
  wide faces are for a glance, not for reading a dense table. The emblems stay on the tablet (no room on the desktop).
- **The tablet is silent unless asked: Play alerts here.** The PC's voice is the cockpit's; a tablet that also spoke
  would double every line, and on a plain-http LAN address there are no Web Locks to pick one speaker, so alerts are
  a banner there. But a Docker server often has no browser open at all (the author, 2026-10-04), so the tablet's
  Settings can make it speak and play sounds itself, deliberately outside the one-speaker lock: doubling is the
  user's to avoid, by turning one off. It has its own alert choices (Choose alerts…).
- **One automatic page switch on the tablet:** to Now when the surface map shows, back when it hides (only if you
  are still on Now and chose no page meanwhile). Anything more would take the page from under your finger.
- **Fonts are OFL and shipped; fan fonts never are.** Antonio and Barlow Condensed (SIL OFL 1.1) live in
  `static/fonts/` with their licences. Fonts like "Euro Caps" or LCARS fan fonts have unclear redistribution terms:
  the player may drop one into `data/fonts/` (served at `/userfonts/`), and the theme uses it first.
- **A body's picture is an impression, drawn, never an image** (tablet plan phase 7): made in the page from the scan
  (class colours, bands, clouds and continents, the atmosphere's rim, rings by class, size by radius), seeded by the
  ids so it never changes, lit from the left (toward the parent star, as the schematic lays orbits out), and labelled
  "impression from scan data". No image files, no screenshots, no rotating globe: the DSS gives counts, not where
  things are, so anything more would be invented. Marks are text under it, never on it.
- **A question by voice is answered on the PC and captioned everywhere** (tablet plan phase 6). `/api/ask` sends the
  answer through the co-pilot channel: the window that speaks says it (a line you asked for, so it speaks through a
  hush, as the status report does), every other window, the tablet's included, shows it as a caption. Every co-pilot
  line (status report, say again, replay, an answer) is said in Piper or not at all, never in the browser's own voice
  (`speak(..., {piperOnly: true})`; the author's choice, 2026-10-04): the caption is there either way. `spoken` says
  whether a window that speaks has asked for the payload in the last minute (S24: its long poll says `speaker=1`).
  Vespa's "status report" is composed on the server (system, fuel, unsold, the Highway's next stop), not the page's
  report: that one depends on each browser's thresholds (S23). The AI layer is off by default and sees only the
  read-only tools; hush and unhush are fixed commands, never AI tools.
- **The voice's own questions follow the server's settings** (S14, S32, 2026-10-13). "Left behind nearby" keeps what
  is over `body_highlight_level` and `bio_min` from ed_outrider.toml, not a browser's (the page's Left behind keeps
  its own); the AI's left_behind tool filters nothing and gives the values. "How far today" counts the sessions that
  ended since midnight on the server's clock (a Docker server's TZ, so set it there), one that began the evening
  before counted whole: History's sessions are the unit. "FSD injections" picks the three recipes by group and grade,
  so a learned recipe (S15) still answers; the material that runs out first is said only for a grade you can make at
  most twice (the Materials tab's jumponium call-out). "This body": the body you are on, else the one whose near-body
  zone you are in (D1's rule), else the one targeted in this system; `/api/status` says those two (game facts, like
  `on_body`, on an open route knowingly). A hush by voice takes a time, but the hush has only three lengths (10, 30
  minutes, the next jump): another time gets the nearest, and the answer names the three first. That answer is what the
  speaking window says for the hush (the co-pilot channel's `hush`: its own "Quiet for 10 minutes." news stays quiet),
  so the three lengths are heard, not only captioned.
- **"Questions asked" is kept in memory, never in the database** (S35, 2026-10-13). What the voice heard is the
  player's own words, sometimes not meant for Outrider at all (the wake word misfires): the last 50, every device's,
  are kept while Outrider runs, so a misheard word or two phrases that clash can be checked, and a restart clears them.
  GET `/api/ask/log` is behind the sign-in like every route and is not one of the AI's tools (an AI client reading
  what was said to the voice is not what those tools are for). Every way out is kept, refusals (400, 426) and the AI's
  failures with their code included, but never the AI's key; `matched` "error" is the log's value only, POST
  `/api/ask`'s `matched` stays fixed, ai or none (the app's contract).
- **Bookmarks import merges, and the server reads the file** (S53, 2026-10-13; the author's default of 2026-10-12):
  Import… beside Bookmarks' Export adds what is new and never replaces (INSERT OR IGNORE): a system already bookmarked
  keeps its own name, note and date, so importing the same file twice, or a friend's list, is safe; to take their
  note, remove yours first. The file goes to the server as text and is parsed there, because JavaScript rounds an id64
  above 2^53. It reads Outrider's own export (CSV with its header, or JSON), and a spreadsheet's save of it (a
  byte-order mark, ";" with decimal commas); other tools' bookmark files are not read. Each row needs id64, name and
  x/y/z: the position comes from the file, never from a lookup, so 10,000 rows import offline at once. A bad row is
  left out with its reason (a long id64 a spreadsheet turned into 1.15292E+18 is the likely one; a rounded id64 that
  still looks whole cannot be caught); a note is kept to 2,000 characters as ☆'s own; more than 10,000 rows or 8 MB
  refuses the file.
- **Any view in its own window** (S37, 2026-10-13): `?view=<tab>` shows that view without the tab row and never saves
  the view (the main window keeps its own), so a second monitor can hold Bookmarks or the Map. The ↗ is in the tab's
  corner, shown on hover or focus only and drawn over the padding, so the tab row keeps its width; never on a device
  that cannot hover (a hover-only reveal eats a phone's first tap). A jump to Here from such a window (⌖, a body) goes to
  the main window while it is open (the author's default, 2026-10-12): the view window keeps showing what it was opened
  for; with no main window it shows Here itself, unsaved, with ↩ back. The main window speaks: a view window joins the
  one-speaker queue a second late, as the Now window does, and either of them given the voice while the main window that
  opened it waits in line (it reloaded: F5, an update) hands it back within a second (`SPEAKER_YIELD_MS`: the opener's
  `speakerQueued`) and queues again; "Speak from this window" there keeps it. Now keeps its own ↗ and `?mode=now` (`?view=now` is not a
  view window); the tablet has its own shell and no view windows.
- **Outrider presses keys for three things now:** auto honk, auto-target and the tablet's rail. The rail is one key
  per tap, only for signed-in devices (or this PC), only while the game is live, never while one of the other two is
  pressing, and only the binding the game itself has for that control; there are no macros or sequences on it (Board
  ship and Disembark were dropped for that reason). Status.json is the only confirmation; a press that is not
  confirmed says so rather than guessing.
- **The MCP bridge reads the running server, never the database** (PLAN-mcp): every summary lives in `State`, so the
  bridge asks the read-only GET routes over 127.0.0.1 and reuses them; the password never applies to it (loopback).
  Its tools are defined once in `outrider/tools.py`, so the voice's AI layer offers the same ones. MCP's stdio
  transport is a few dozen lines of JSON-RPC, written directly rather than pulling in the SDK (one less dependency;
  the SDK's API has moved before). Read-only is a safety rule: no tool presses, plots, bookmarks or hushes.
- **Only `/api/status` and `/api/status.txt` are readable cross-site,** for stream overlays: they alone send
  `Access-Control-Allow-Origin: *` (no credentials are involved), so a fetch from an overlay page on another origin or
  a local file can read them (review F6).
- **The surface map's altitude in a browser is capped at the server's** (`[defaults] surface_alt`, review F24): the
  server sends positions only below its own altitude, so a browser set higher would show a frozen map. A lower one
  hides sooner, as before. Climbing past the altitude wakes the page once, so the map goes away on time.
- **A HullDamage line with no `Fighter` key is the SRV's or the Nomad's,** not the ship's (review F25): every ship
  line in the author's journals carries `"Fighter": false`, and the vehicle lines never do.
- **The journal archive in backups is never pruned;** database zips rotate. `--restore` leaves `speech.json`,
  bans and the config alone.
- **The firsts watch is gentle to Spansh:** each system daily for a month, then weekly, at most 150 checks a day,
  and it can be switched off. Its first sighting in a system (S6) is a card and a notification every time but spoken
  at most once in 30 minutes (`FIRSTS_SEEN_SAY_S`, decided on the server so every window and a reload agree): a first
  run through hundreds of never-checked systems can find several in a row. The words say their scans reached Spansh,
  never "stolen": someone else's scans do not take a first discovery until they sell before you.
- **The suggested order is not a route planner:** a fixed supercruise time curve; its first stop is said ("Next: …") only
  in the mapped call-out and the status report. Here's schematic numbers its stops and draws a path between them (S30):
  each leg's time is the curve over the difference of the two bodies' distances to the arrival star, which is what the
  journal gives, not the distance between them. The first stop you pick there (one body, meta `plan_first`, live-only)
  applies only in the system you are in and is forgotten after a jump (the arrival elsewhere drops it, so a return to
  that system later does not bring it back; a re-read's older arrivals do not drop it).
- **Discovery streak lines are limited to two kinds,** no records or milestones.
- **The approach warning fires on ApproachBody only** and reuses the unsold amber level rather than a new setting.
- **"Leaving a body unfinished" only nags** if you landed or sampled there this visit.
- **Alternatives to a finished target and a heading-aware neighbourhood were declined:** undiscovered systems
  rarely turn up close by.
- **Parked:** nearest neutron star and a wasted-charge warning (now that the Highway exists, the next candidates).
- **The Highway keeps one active route.** A new plot replaces it; waypoints may come later. It is live-only data
  (`highway_route`), kept through a journal re-read and carried by backups.
- **Detour and resume:** arriving off the route counts as a detour only once the route was joined (flying to its
  start is not one), and arriving at *any* route system resumes it, neutron or not, forwards or back. Said once each.
  A respawn or a login somewhere else (a Location that moves you, not a relog) counts as an arrival too. Off the route
  the nearest route system marked is the CLOSEST one, passed or not (the author's rule, 2026-10-03: getting back on
  the highway is the fastest way on). Arrivals count when newer than the position the route was plotted at (its
  journal time, not the wall clock), so a jump read just after the plot finished still moves the route.
- **The status report and welcome back say the Highway** (review S2): one clause right after the fuel ("Highway: boost
  here, then Hwy Stop 38, 4.2 light-years, refuel in 3 jumps"), led by the too-much-fuel warning when it is set, the
  closest route system when off the route; the report's "Nearest unvisited" is left out while a route is followed.
  No position "38 of 399" (the index and total are easy to say one off).
- **The Highway's cargo is not remembered.** The form takes the cargo aboard from the journals each time (a
  remembered figure would be stale the next day); only the plotter and its options are per-browser settings.
- **Road to Riches is a route type of Plot Route, not a tab** (thshurka's PR #1 gave it its own; moved 2026-10-06):
  both are Spansh routes you plot and follow, and a 15th header button wrapped the header in several themes. The
  server keeps each route on its own (tables, plot, progress, speech); the page shows one, with a switch when both
  exist, and only the newer copies its next system. It is never auto-targeted on its own: a Road to Riches is for
  stopping; 🎯 on any route system is the player's click (2026-10-07).
- **One slot for a survey or trade route: Road to Riches, Exomastery or a trade route** (the author, 2026-10-07; a
  trade route joined it the same day: "one slot is fine"): rarely flown together, a new plot of any replaces it, and
  the route switch stays two-way (Highway and the slot's route). Exomastery's bodies carry life other commanders
  reported: the page says "known life" and never implies first footfall; its progress is the journal's samples by
  BodyID and species name. A trade route's stops are the stations (a hop's straight line, not its jumps: 🎯 targets
  the system and the game plots the way), its progress is your MarketSell / MarketBuy at the stop's market, and its
  plot gets 600 s (Spansh's trade planner is slow).
- **The slot's kinds are one table** (G4, 2026-10-13: `outrider.riches.SURVEY_KINDS`, page.js `SURVEY` its copy, a test
  keeps them in step): what differed by kind at some sixty places (the URL, the parser, the lines, the alert, the glyph,
  the form's fields, what a stop asks of you) is read from it, so a new kind is a row, not a hunt. Earth-like and ammonia
  world routes (S52) are not endpoints of their own (the plan's `/api/earth/route` and `/api/ammonia/route` answer 404):
  Spansh's own pages ask the Road to Riches router for one body type with min_value 1 (probe P3, 2026-10-13), so they
  are Road to Riches rows whose map always counts (their worth is the map). Their moments and a sweep's use Road to
  Riches' alerts row ("Survey routes"), the moment's `route` naming the kind: one switch for the routes you stop and scan
  on, not three more rows.
- **A sweep** (S51) is the slot's route through systems ticked in Left behind, My firsts (lost ones: the rescan trip) and
  Bookmarks, in the order Spansh's tourist router picks (probe P2): one set of ticks across the three lists, in that page
  only (a reload forgets them; they are a trip being put together, not a setting). Its stops ask nothing but arriving:
  the next stop on each arrival, "Sweep complete." at the last row, never a stop passed over. Spansh refuses a sweep
  naming any system it does not know (a fresh discovery among lost firsts is likely): it is plotted again without them
  and the note and the heading name them, rather than a stand-in, since the system is the point of the trip. Known limit:
  as for every survey route, arriving at the last row with nothing left ends it, even with stops skipped on the way.
- **A survey route's next stop skips the systems you finished** (S12): "next" is still the row after where you are,
  walked past the rows that came with work (Road to Riches: bodies; Exomastery: a body with species, `had_work`) and
  have none left by your journal. Every "next" uses it (`riches_next_open` / `Journals.riches_open`): the line ("skipping
  2 done", their names in the hover), the tab, the clipboard, the co-pilot button, 🎯's Target next and the spoken
  "Next stop: X, skipping 2 systems you've finished." A row without bodies (a route's real end: `bodies: []`) is never
  passed over, nor the last row (arriving there is what ends the route); a trade route never skips (its next stop may
  be the same station's neighbour). `at` and `furthest` are unchanged: only what "next" points at moves.
- **The wrong-jump check (S11)** compares the followed route's next stop (the Highway's next row; a survey route's next
  past finished systems; a trade route's first stop in another system) with the game's target: `game_target`
  (`outrider/target.py`, F3) reads Status.json's Destination, and when that is a hop of the route the game plotted
  (NavRoute.json), that route's end; with no live Status.json the journal's FSDTarget. A Destination in the system you
  are in (a body, a station) is no jump target, so the check is silent there, as off the route ("Off Route: Detour"),
  once the route is complete and with nothing targeted. A later stop of the same route is "↷ N stops ahead" (the plan's
  default for targeting one on purpose), not wrong, and not said. A wrong target is said once per (route, next stop,
  target), only after the galaxy map closes (so browsing in the map says nothing), never while an auto-target run is
  choosing the target, for the route the line shows server-side (`route_newest`, the overlay's choice too). Its alerts
  row `wrongtarget` is spoken and not notified by default (key `wrong_target` {system, next}, 15 lines a list). On the
  overlay the mark lives on the Target panel alone (the plan-wide review: one overlay place), not on Now's route line.
- **Auto-target presses keys in the galaxy map** (opt-in, Linux, Windows experimental since 2026-10-05; decided with the author 2026-10-01): open the map,
  the search box (UI_Up highlights "Search the Galaxy", UI_Select puts the cursor in it; found in game 2026-10-02 — UI_Right, Auto_Neutron's older step, moves along the tab column to Trade Routes, and UI_Select alone opens the current system; `autotarget_search` changes it), type the name (US keymap; a name it cannot type is pasted when a
  clipboard tool exists), then the first result picked after a wait (the search lists its results a moment after the name goes in; found in game 2026-10-02): the arrow key by name and UI_Select since 2026-10-23, not Enter twice (discussion #12, checked in game: with several results, Sol and Solati, Enter only moves the focus out of the box, and a control bound to a letter types it into the box; `autotarget_submit`), the plot-route step (configurable: the map's focus after a search varies), close the
  map, then Status.json `Destination.System` must be the next id64. It shares auto honk's virtual keyboard and lock;
  an auto honk running on the arrival goes first. It checks GuiFocus, the system, a jump and danger before every step
  and while waiting, and on an abort closes the map only if it opened it and the map is still the focus. One try per
  supercharge, nothing repeats. Its results are plain spoken lines under their own alerts row; only "nothing to target" is a `speech.json` key
  (`autotarget_nothing`, with each personality's lines).
  The default sequence is what worked in game on 2026-10-03: the map reopens on the panel it last showed, so the
  search starts with a short CamYawRight (a camera move hands the focus back to the map); the first Enter waits
  1.5 s (the suggestion lists late on a long name); the plot step zooms out instead of turning, since a turn after
  the search could swing the cursor onto a neighbouring star and plot to it.
  Target next and Retry (review Q4) are one action, POST /api/highway/target: a run the page asks for, like "test
  now" but against the route (the next system; off the route the closest one, as the line's "nearest"; before the
  start, the start), with or without the toggle; {countdown} 0-10 s, 5 by default for the desktop page (the click
  took the keyboard focus), 0 for the tablet. On the co-pilot button since 2026-10-08 (the author's later call: see the
  button's layout below). Clearing or
  replacing the route stops it like the automatic run; switching the toggle off does not (it is not the toggle's
  run). Retry shows only while the failed run's row (autotarget_last's route and index) is still the one Target next
  would aim at.
  Guards (review batch 4): the keyboard's owners (who keeps the device open) and a run's cancel token are separate,
  so switching auto-target or auto honk off stops that feature's run even while the other keeps the device open;
  clearing or replacing the Highway route stops a pending or running auto-target too. Everything is checked again
  under the keyboard's lock before the first key (the wait for it can be long: one feature holds it for its whole
  sequence), against the system the run was decided in rather than wherever you are when it starts. "Already
  targeted" is checked before anything else (a panel open does not make it an error), and the check after the plot
  also accepts NavRoute.json ending at the next system (a waypoint beyond a plain jump plots a route whose first
  hop differs). A wrong target is said by name. A cancelled run still holds its closing map tap for the full
  TAP_S. Auto honk's miss is not held against the fire group when your own jump started during the hold or the
  wait for the scan.
  The toggle and delay are the server's (meta `autotarget`, beating the config once used), not per browser.
  The game's own "in danger" (Status.json bit 22) is on for every FSD use, from the charge until 16-26 s after a
  hyperspace arrival or a SupercruiseEntry (logged in game 2026-10-09). A run that meets it in that window waits for
  it to clear (`State.arrival_danger_until`, up to `AUTOTARGET_DANGER_WAIT` = 60 s after the arrival or entry; the
  restored position's arrival after a restart), says so once ("Not targeting due to danger ... for up to N
  seconds") and presses nothing meanwhile; the co-pilot button's second press cancels it like the countdown.
  Interdicted, the FSD charging, or still in danger past the minute: refused as a real danger. Once the map's close
  key went down, an FSD charge or a jump is a success when the target is set (you set off before step 7 looked).
  **It brings the game to the front itself, and presses no key into another window** (the author, 2026-10-12, S74;
  `wmctrl -a "Elite - Dangerous (CLIENT)"` tried by the author on GNOME Wayland with the game under XWayland). Every
  run (🎯, Target next, Test now, the automatic one, the co-pilot's) first finds Elite's window with the overlay's
  tracker, by its whole title only (a browser tab about the game, in front, would otherwise pass for it), activates
  it and waits up to a second for the tracker to see it in front; then the Targeter asks before every key, the
  map's closing key on the way out included, and stops (code "window") the moment it is not. The page's runs then
  have no countdown; when the game did not come, they count down 5 s after all ("Elite is not the active window:
  click into the game"), the server telling the page through the test's `note`; the automatic run and the
  co-pilot's (whose short wait is for a cancelling press) stop and say so. Where nothing can be known (no wmctrl
  or xprop, no window with that title: the game as a native Wayland window) it does as before: the countdown, keys
  unchecked; the box says why. On Windows, SetForegroundWindow from a background process needs the usual
  workaround: attaching to the input of the thread in front, not the other usual one, an Alt tap, which would be a
  key into the window in front. Untried there.
  **Its settings apply to the next run, and the controls are named in any case** (a Windows player's report on
  Reddit, 2026-10-22). Every `[highway] autotarget_*` key is in `State.LIVE_CONFIG`: a sequence is tuned by trial and
  error, and a saved change that waited for a restart looked as if it were ignored. A step's or `autotarget_keys`'
  name is matched to the game's control names whatever its case (`canon_key`): `UI_SELECT` was taken for a keyboard
  key that does not exist ("no keyboard binding"). Each step's log line names the keys it pressed, so a log sent in
  shows what happened without `--show`.
  **A pause after every key of the editable parts, and a longer search wait for a far system** (the author's runs,
  2026-10-23): eight UI_Downs pressed back to back lost some (one run pressed the wrong icon and left the map), so
  `step_pause` (0.25 s) follows each key of the search, submit and plot steps rather than relying on `wait` lines; a
  run is about a second slower, a lost key is worse. The map's flight to a system 5,000 ly away outlasted the 2 s
  search wait: over 300 ly it is at least 5 s, from the distance Outrider knows before the run starts. "key delay"
  became "typing delay": it is only ever between typed characters, and a player who pastes had set it to 1 s
  expecting it to pace the steps.
  **A route's next stop one jump away is targeted, not plotted** (discussion #12, the author's checks in game,
  2026-10-23). Plotting hands the route to the game's planner: with Use Jet-Cone Boost off in its Route Settings it
  ignored the supercharge and gave six jumps to a stop the supercharged jump reaches (on: one); Kurbo26 saw a stop
  added with it on. There is no key for "target": the system panel's Target System icon is reached by keys (two
  UI_Rights, one can stop at the system's details; eight UI_Downs), so it is its own box and its own default. Which
  stops: the ones one jump from where you are by the route's own rows (`route_one_jump`: you are at row `at`, and the
  legs from there to the stop, each row's `jumps`, come to one; review 2026-10-23 H1: the stop's own leg alone made a
  🎯 five stops ahead, or the closest row off the route, "one jump"), never by a range Outrider would estimate (at the edge of the range a wrong guess is a target you
  cannot jump to), never a trade hop (no jumps), never any other 🎯 (a far bookmark needs a route; even supercharged).
  On by default: it does not depend on the player's Route Settings. Two guards: a one-jump stop must end up the
  target itself (no NavRoute-end shortcut, in the "already" check too), so a miscounted icon or a multi-jump plot
  fails with its fix said; and without UI_Right / UI_Down on keyboard keys the stop is plotted after all.
- **Settings → Server lists only the keys with no section of their own** (the author, 2026-10-23; project plan
  PLAN-settings-cleanup). It had 112 keys, most set in other sections, and some contradicted them: auto honk's and
  auto-target's switches live in the database (meta `autohonk_enabled`, `autotarget`), so the file's value it showed
  was stale (`autotarget = off` while it was on). Now `config_edit.homed` keys are left out ([defaults]: every one
  has a browser row, and Sharing sets new browsers' defaults; [speech], [overlay], [autohonk], [copilot], [highway]
  autotarget*), and the rest (about 45) are grouped by purpose rather than by the file's sections, each row showing
  its [section]. Every homed key had to get a control first: auto honk's key, wait, hold and skip and the co-pilot
  button's five in Settings → Auto honk (the wait and the skip are read on every honk: live; the rest at the next
  start), the overlay's system-panel time and radar range, and in Settings → Auto-target the Highway's switch and
  delay (mirroring Plot Route's), the dry run and the key overrides. The file keeps every key. Two tests keep it so:
  every key is listed or homed (none in "Other"), and every homed key is found by Find a setting in the page.
  **The steps have their own Settings section, not a place in Plot Route** (discussion #12, the author, 2026-10-23):
  one sequence serves every 🎯 (bookmarks, Nearby, Search, the Map, the co-pilot button) as well as the Highway, so
  editing it in the Highway's box would read as Highway-only. One shared sequence, not one per use, until a test in game
  shows a use that needs other steps. The section writes the same `[highway]` keys as Server settings (no second store),
  and a step list is checked as it is saved (`CONFIG_CHECKS`) so the refusal names the bad step.
- **ExploData's colour tables are downloaded, never shipped** (the author, 2026-10-10). EDMC-ExploData's repository
  carries the GPL v2 text without "or later", so its tables are kept out of the repository and the Docker image, and
  Outrider's own licence does not depend on them: `resources/bio_colours.json` is fetched on the first start (and refreshed with the
  rules) and merged in at load. A first start offline has no colour check until the next start or the Retry (S7:
  the banner's card and a note where colours would show; `bio.update_colours` fetches only ExploData's table, then the
  rules are reloaded and the bases' guesses worked out again). Whether they are there is judged by
  `colours_available()`, never by the file, and a failed fetch no longer writes one with no colours in it. BioScan's rules (GPL v2 or later) and the region map (MIT) still ship. The colony distances
  are the game's (the Genetic Sampler shows them), kept in `outrider/bio.py`.
- **The in-game overlay is our own window** (the author, 2026-10-08 and 2026-10-10; the author's plan,
  project/done/plans/PLAN-overlay-build-2026-10-10.md, is private and git-ignored).
  EDMC will not be running, so Modern Overlay (an EDMC plugin) is not used; its code for finding Elite's window,
  following it, letting clicks through and its window flags is adapted instead (`outrider/overlay_tracking.py`,
  parts of `outrider/overlay_window.py`), which made ED Outrider GPL-3.0-or-later. Outrider builds the panels as draw
  lists (`outrider/overlay.py`, GET `/api/overlay`) and runs the window that draws them itself on the game PC
  (`outrider/overlay_runner.py`). The overlay is a game-PC feature, as the key presses are (the author, 2026-10-10):
  an Outrider on a server has none (no window drawn from a server: the game PC's Status.json reached a server a second
  late over the share, and one application on the game PC is simpler). `--simulate` never starts the overlay window
  either. The layout lives in the database (meta `overlay_layout`), not the config (the author agreed, 2026-10-10):
  Arrange mode writes it on every drag, which would rewrite the toml again and again; copying the toml does not carry
  it, copying the database does. A panel's place is kept from the window corner nearest it, or from the middle of the
  top or bottom edge, as a share of the window, so a resolution change keeps the arrangement. Linux is where it is
  tried (X11, and XWayland on a Wayland session, as Modern Overlay runs on GNOME); Windows works too, seen over the game
  by two players (Kurbo26 and weidercs, reported 2026-10-15);
  native Wayland compositors, gamescope and exclusive fullscreen are out of scope.
- **The overlay's sizes have a floor in pixels, not a percentage** (a GitHub report, 2026-10-14: too large on a 4K TV,
  and a size under 50 % was put back to 50 %). Panels scale with the game window's height, so a panel takes the same
  share of the screen at 4K as at 1080p, and the same percentage is unreadable on one screen and big on another (small
  text at 50 % is about 7 px at 1080p, 13 px at 4K). So a panel's size goes down to 20 %, all panels have one size on
  top of their own (`[overlay] panel_scale`, in the config: a setting, not an arrangement), and the window raises a
  panel's scale so its smallest text is never under `MIN_TEXT_PX` (9 px, `overlay.effective_scale`). Settings shows the
  figure only from a window drawing now (it alone knows the game window's height). A panel's own text size lives in
  the layout beside its size (`text`, "" as all panels), not in an `[overlay]` list: it is per panel like the size,
  Settings and Arrange write the layout, and an old layout reads unchanged.
- **The overlay uses the config's levels.** The panels are built on the server, which cannot see a browser's levels:
  the system panel `body_highlight_level` and `bio_min`; the Target panel's body `high_gravity`; Now `body_highlight_level`,
  `bio_min`, `high_gravity`, `codex_interesting`, `unsold_warn` and `unsold_urgent`; Bio signals `bio_min`,
  `high_gravity` and `codex_interesting`. Now leaves out what only the page knows (the skip floor, the high-g approach
  stakes, captions).
- **The overlay copies some of the page's rules in Python:** Now's suggested order (`overlay.plan_items`; the page's
  `worthLeavingFor` + `planItems`, with the first stop you picked: `first` / `planFirstFor`; the stop numbers
  `stop_glyph` / `stopGlyph`), the supercruise time (`overlay.sc_seconds`, `SC_KNEE`; the page's `scSeconds`),
  the session figures (`overlay.session_bits`; the page's `sessionLine`), and the rebuy the risk figures use
  (`risk_rebuy` in ed_outrider.py; the page's `riskRebuy`). Two copies of one rule: a change to either is made to both.
- **PyQt6 is installed when the overlay is on, never from a button** (the author, 2026-10-10: not a menu option).
  It is not one of Outrider's requirements (about 100 MB, and only the game PC's overlay window needs it). The
  launchers run `python -m outrider.overlay_runner --setup`, which installs `requirements-overlay.txt` before Outrider
  starts when `[overlay] enabled = true` and PyQt6 is missing (on Linux it also warns when wmctrl is missing) and never
  stops the start. Outrider itself installs it once per switching on whenever the window is wanted (the overlay, the
  test panels or Arrange mode), into the Python it runs with (the launcher's `.venv`), with a popup in every page
  window; after a failure Settings says why and it waits until the overlay is switched off and on. There is no
  Install button and no `/api/overlay/install`. A window that crashes is started again after a growing wait, and
  given up after `CRASHES_MAX` (5) in a row until the overlay is switched off and on.
- **Time since you sold counts whole days passed** (the author, 2026-10-10): 6.7 days is "6 days", never rounded up,
  on the page (Now's at-risk line, the welcome back) and on the overlay's Now panel (`overlay.unsold_age`: "3 days
  unsold", from a week "2 weeks 2 days since sold", or "2wk2d since sold" when the written-out form would not fit).
- **The panels hide over the system map, the orrery, the FSS, the SAA and the codex, and in the hyperspace tunnel; the
  ones ticked Docked while docked** (the author, 2026-10-10 for Now, 2026-10-14 for the setting). GuiFocus 7-11
  (`OVERLAY_HIDE_FOCUS`) and the FSD-jump flag hide every panel; over the galaxy map (6, `OVERLAY_GALAXY_MAP`) only the
  Target panel shows (D1, below); the ship's docked flag, or on foot in a station, hangar or social space (`FLAG_DOCKED`,
  `ON_FOOT_DOCKED`), hides the panels in `[overlay] hide_docked` (Settings' Docked column). That list replaced the two
  fixed rules (Now hidden docked since 2026-10-10, the Target panel since D1); its default when the key is missing,
  System, Target, Now and Bio (`overlay.HIDE_DOCKED_DEFAULT`), keeps them and adds the two other panels about flying,
  while the strip and the alerts stay: what an older config gets without a word. The radar is never in it (it shows
  only on a body's surface: no box, a dash). The Target panel over the galaxy map is shown docked whatever the list
  says: you pick the next system there before you undock. The test panels and Arrange mode are the exception: they show over the game's window
  whatever is in front. Nothing shows while the game loads (2026-10-11): after a crash the game writes no Shutdown and
  leaves Status.json saying live with the dead session's flags until the new session is in, so from a game launch (a
  journal's first part) or LoadGame to the Location (meta `game_load`, journal-derived) the panels stay off.
- **One Target panel, and its near-body zone** (D1, the author 2026-10-12). The body panel became the Target panel
  (same id `body`, config key `body_panel` and layout key, so nobody's arrangement or config needed moving). Inside a
  body's near-body zone (Status.json names the body and gives an altitude: the point the game writes ApproachBody) it
  shows that body, even over a target; outside, the body targeted in this system, else the system targeted (FSDTarget:
  the galaxy map's pick or a route's next jump), else nothing: the old fallback to the body you fly near (BodyName
  without the zone) is gone. Entering switches at once; leaving switches back only after `TARGET_ZONE_LINGER_S` (5 s)
  out of the zone, a constant: the zone's edge bounces (148 of the author's 468 LeaveBody re-entered the same body
  within 2 minutes, 19 within 15 s), and the author preferred a little flicker to waiting longer for the next
  destination. No altitude setting: the game gives no "within probe range" signal, and a body you probe is the one
  you targeted anyway. A body with nothing to show (a star, one nothing is known of) gives way to the target. The
  panel shows over the galaxy map (the one exception to hiding there: you see what you picked before you jump, docked
  too) with the system targeted, and stays off while landed, in the SRV and on foot (the radar's screen), and docked
  elsewhere while its Docked box is ticked (the default). Its system facts come from the target's lookup when it is for this target (`State.target`, matched on id
  and time: "checking…" until then) and its value from the Nearby row only (`State.target`'s `leaving` is the system
  you are in); the hazard is the page's `hazardNote` (`overlay.star_hazard`: neutron star, white dwarf, black hole).
- **Analysis-only panels** (D2a, 2026-10-12): `[overlay] analysis_only` keeps those panels off in your ship while the
  HUD is in combat mode (Status.json bit 27 clear). The SRV and on foot have no HUD modes, so the mark is ignored
  there, as over the galaxy map and for the test panels and Arrange mode. The radar stays on wherever it applied
  before (D2b, an Artemis-suit or Genetic Sampler gate, was dropped by the author).
- **The overlay pill** (S8, 2026-10-13): the overlay window says what it sees with each GET (`&w=`: drawing, behind,
  hidden, covered, no window, a tool missing), a GET that changes state as `overlay_seen` already did; the server adds
  what only it knows (the runner, the game live or loading from the journals, a window quiet for `QUIET_S`) in
  `overlay.health`. The plan's game-process check in the window was left out: the journals already say whether the game
  runs and loads (the link pill's "no game" comes from the same place), and the window's own "no window" covers the
  rest. "Not the active window" is amber only while the page itself has the focus (the player looking at Outrider on
  purpose), red otherwise. Exclusive fullscreen is out of scope; the pill only warns, from the game's DisplaySettings.xml
  (`<FullScreen>` 1; 0 windowed and 2 borderless are the published values, not yet checked against a real file),
  found from each live journal folder's user folder (Windows and a Proton prefix alike).
- **Keep showing when Elite is not the active window** (S25 with S25b, the author, 2026-10-12): `[overlay]
  show_inactive`, off by default. With it on the overlay still hides when the game's window is out of sight (minimised,
  on another desktop: X11 `_NET_WM_STATE_HIDDEN`, and `_NET_CURRENT_DESKTOP` only with xwininfo's map state not
  IsViewable, since a window manager with a workspace per monitor (i3 and the like) calls the focused monitor's workspace
  the current one while the game's stays in sight on its own (GNOME and KDE unmap a window on a workspace not shown; the
  desktop alone decides when the map state cannot be read); Windows cloaked) or covered by other
  windows over more than a quarter of it (`overlay_tracking.COVERED_SHARE`: X11 from `_NET_CLIENT_LIST_STACKING` and
  wmctrl's geometries, Windows by walking the z-order above the game, click-through and tool windows ignored). These
  checks run only while the setting is on and the game is not in front, kept a second (`INACTIVE_EVERY_S`). A native
  Wayland window is in no X11 list, so it is never seen covering the game (the overlay draws over it): said in the
  guide.
- **On Linux each overlay panel has its own window** (#1, the author's trials in game, 2026-10-15, GNOME on Wayland):
  in the DSS and on foot Elite locks the pointer, and the lock was refused while the overlay window lay over the game,
  although it lets every click through (its X input shape is empty). Shaping it down did not help, even to one pixel in
  the DSS (the window counts with its whole rectangle); not raising it did not; taking it away when empty did, and a window
  only as big as the panels did, on foot too (3 of 3 with it, 0 of 3 without). One window around all the panels would
  still cover the middle with panels at opposite edges, so `overlay_window.window_plan`: a window per panel
  (`window_rect`: its panel plus 6 px, painted at the game window's layout through an offset), none with nothing to draw,
  the one window over the whole game only in Arrange mode (it takes the mouse there). The lock is asked for as the mode
  changes, so a window in the way at that moment loses it until the next change; a panel dragged to the middle would be
  in the way again, so `[overlay] hide_mouse_lock` (Settings: "Hide the overlay on foot and in the DSS") takes the
  overlay away there altogether, and `hide_on_foot` hides chosen panels on foot. Linux only (`FIT_WINDOW`): the Windows
  overlay was confirmed working with one window over the whole game and this was not tried there; with nothing to draw
  its window hides too.
- **Personalities as drop-in files** (the author, 2026-10-16): `resources/speech.json` stays the base (business,
  sarcastic, sweet); every other personality is a file of its own in the same format, `resources/personalities/`
  shipped and `personalities/` beside the bans yours (`data/personalities/`, never in the repository).
  `merge_personalities` folds them in:
  - a file of yours with a shipped one's name replaces it (edits survive an update);
  - a base personality is never replaced, and a name is taken once per folder;
  - each file is checked and re-read on its own, keeping its last good copy.

  A personality's forms of address are in its file (`"names"`), not in Settings: personalities are edited in their
  files. An alert a personality has no line for is said by the others ticked, else business. "Business for danger"
  is the player's choice and decides for every personality alike. /api/speech is gzipped (1 MB and growing).
- **The overlay's Alerts panel comes from the page** (S26, the author's defaults 2026-10-12): the alerts are worded
  and switched in the browser (speech.json's personality lines, each kind's notify / sound / speak ticks in
  localStorage), so the page posts each alert it shows (POST `/api/overlay/alert`, `pc_only`) and the server keeps the
  last `ALERT_KEEP` in memory; a Python copy of every alert's wording would be large and drift. "Switched on" is any of
  the kind's three ticks in the browser that saw it (the plan's recommended default), whatever 🗣, 🔊 or a hush say at
  that moment; every window posts, the tablet too, and the same title and text within `ALERT_SAME_S` counts once. Each
  stays `ALERT_SECONDS` (8 s), danger `ALERT_DANGER_SECONDS` (15 s, in red: the speech queue's danger rank or the
  danger sound), newest first, three at most. It shows over the galaxy map too (beside the Target panel: an alert is
  brief and the galaxy map is where a plotting player sits), never over the system map, the FSS, the SAA, the codex or
  in the tunnel, like every panel; Analysis only applies to it as to the others.
- **No rebuy multiple for a ship whose hull has no credit value** (the author, 2026-10-10). An Arx-bought ship's
  Loadout carries ModulesValue but no HullValue, and its rebuy is 5% of the modules alone, so "N× rebuy" said ~110
  on any trip and a rebuy-multiple level would always fire. Such a ship gets no rebuy in the risk figures (`risk_rebuy`,
  page.js `riskRebuy`); the credit levels still warn. A Loadout with neither value keeps the rebuy as before.
- **Here's icon legend lists only what is shown.** The footer under Here's list (`HERE_LEGEND` in page.js) names the
  icons the list or schematic shows now, not every icon there is (the author's call, 2026-10-10), and is absent when
  there are none; sticky to the bottom of the scrolling pane so it stays in view. The codex marks write the new
  colour after them ("✪ Cobalt"): their tooltip never shows under the body summary that pops up over a row.
- **Too much fuel, or too little: one fuel window (S1).** Spansh's exact plotter simulates the fuel, so a long neutron
  jump may be in range only with about the fuel it expects aboard (the Caspian's 487.9 ly ×6 jump: at most about 36 t;
  a full 160 t tank gives 75.3 × 6 = 452 ly), and a tank not filled at a refuel stop may run dry before the next.
  Checked on a live arrival in a route system (or a plot made where you are) and again as Status.json's fuel changes
  there (every 3 s at most), against the fuel actually aboard (the main tank, with the reservoir and cargo counted as
  mass) and the current ship's fuel model. On an exact-plotter route the hops to the next refuel row (or the end, 50 at
  most) are burned one by one (`fuel_run`), each with only the multipliers that are facts: a held charge or this
  neutron's on the first, Spansh's neutron rows after it (no white-dwarf guess). Since the range falls as the mass
  rises, a run succeeds on an interval of starting fuel, so `fuel_window` tries a grid of levels every 0.25 t (cheap)
  instead of bisecting the tank, which a failing full tank would fool, and refines each end. Over the high end by more
  than 0.5 t (Spansh plans at the limit) is too heavy, naming the jump it fails ("the next jump", or "the jump to X");
  under the low end is short, with both ends in one line ("scoop to ≥ A t, at most B t"); never both, never two lines
  that disagree. Each said once per system, cleared when the fuel comes right or you leave; silent while the fuel model
  lacks MaxFuelPerJump or p. Only for the ship the route was plotted for. The neutron plotter has no fuel plan: its
  next jump alone, when one jump away. A route plotted with FSD injections keeps that one-jump check too (its boosted
  jumps are not marked in the rows).
- **NavRoute.json the game does not write** (2026-10-14, on the author's PC). The journal had NavRouteClear at 09:10:46,
  then NavRoute at 09:11:58, 09:24:08 and 09:25:27, and NavRoute.json stayed the cleared file from 09:10:46 throughout
  (its mtime too): the In-Game Route line showed nothing mid-route, and the EDDN sender rightly refused the stale file
  ("NavRoute.json was not written for the line of …: not sent"). Clearing the route and plotting a different
  destination made the game write it again; the guide tells players so. Outrider now keeps the journal's last
  NavRoute line (meta `navroute_event` {ts, written}, journal-derived): a file older than it is not that route, nor a
  route cleared (`read_navroute` leaves it alone; `Journals.game_route` is None while the stored route is older), and
  the file is read again every `NAVROUTE_RETRY_S` for `NAVROUTE_LATE_S` after the line (`State.navroute_retry`: a late
  write that kept the mtime), then whenever it changes. Meanwhile the payload's route is `route_minimal`: the jumps
  left from the latest FSDTarget after the line (RemainingJumpsInRoute) and the route's end from Status.json's
  Destination, no hops; it ends with NavRouteClear or on arriving (the FSDTarget is dropped there). Nothing else takes
  a route from it: the look-ahead (`navroute_ahead`, S1, S2), S11's game target and the Map read `game_route`, so they
  see no game route rather than the previous one's stars.
- **The last scoopable star before a stretch you can't cover (S2)** works on any route Outrider follows: the hops ahead
  (`route_ahead`) are the game's own plotted route from where you are (a survey route's legs come this way), then the
  Highway's rows after its end. A star counts as not scoopable only when that is KNOWN: the game's star class (NavRoute,
  FSDTarget), else the row's facts (a neutron row; an exact route's refuel row is scoopable, P1), else Spansh's record;
  an unknown star ends the stretch, so the claim "the next N stars are not scoopable" is never a guess. Warned at a
  scoopable star when the fuel aboard won't carry the ship over those stars to the next that is (or may be) scoopable,
  by the same `fuel_window` as S1 (the ship lightening hop by hop); "even a full tank won't" when no level does. Silent
  when a hop is beyond the ship's best jump at any fuel (the game's route alone promises no supercharge: not a fuel
  matter), when the fuel is too much rather than too little, while scooping (Status.json's flag) and while the fuel
  model is incomplete. Said once per stretch and stay (the route it comes from and its first dry star, forgotten on
  leaving), so stopping a scoop a little short is not said twice, and a later arrival at that star (a detour and back,
  days later) says it again. On an exact-plotter Highway route S1's line already says the same stretch, so S2 stays
  quiet where S1 has a `short` (the plan's default, "S1 suppresses S2"); the page's top-up card stays quiet only where
  S2 spoke on this stay (`dry_stretch.said`) and its row speaks: never a stretch shown and nothing said. The spoken line is the author's ("The next 3 stars on your route are not scoopable. This is your last chance
  to top off before you need to call the Fuel Rats."), key `fuel_last_scoop` {count}, a danger key under its own alerts
  row `lastscoop`; one star, and the no-amount case, are plain sentences (the lines are plural).
- **Short of the refuel stop is not said at a refuel stop** (the plan scoops there anyway): the line shows how much to
  scoop instead ("⛽ scoop to ≥ 24.3 t to reach …"), and leaving without it is warned on arrival at the next system.
  Its spoken line is a `speech.json` key (`fuel_short`, a danger key: business wording by default) under its own
  alerts row (`refuelshort`), where the Highway's other lines are plain text.
- **No scoopable column on Highway routes** (P1, 2026-10-13, `scripts/exact_probe.py`): Spansh's exact plotter sends
  `is_scoopable` on every jump, but on all 45 jumps of three routes it equals `must_refuel` (its plan tops the tank up at
  every scoopable star), and the ends say False for scoopable stars (Sol, Polaris). An exact route's `refuel` flag
  already says it.
- **Conservative range** shortens the plan, not the ship: the neutron plotter gets the range less the margin, the
  exact plotter a smaller optimal mass, scaled so the normal full-tank range is the margin shorter (the range less the
  booster's ly goes as the optimal mass at every mass, so Spansh's fuel simulation stays consistent; the booster is
  untouched). Neither cuts the drive's own range by more than half. The margin is recorded in the route's options.
- **The Highway's spoken lines are plain text** carried by the moment, not `speech.json` keys yet (personality later),
  except short of the refuel stop (`fuel_short`, above).
- **Find by name asks Spansh when EDSM fails** (S48): EDSM first (one call gives the id64, position and main star),
  then Spansh's record by exact name when EDSM is down, does not know the name or has no position for it. Either hit is
  cached as a minimal base marked stale, so opening it fetches Spansh's bodies at once; no cache layout change.
- **The Highway map's regions are drawn by the page,** not rendered to an image on the server: `GET /api/regions`
  sends klightspeed's run-length grid as it is shipped (185 KB, about 40 KB gzipped, an ETag so a reload costs a 304)
  and the page colours it with the theme's colours at the zoom it needs. A server PNG would need one per theme, an
  encoder Outrider doesn't have, and the grid again for the borders and names. The tints and borders go into an
  offscreen canvas covering the view plus a margin, redrawn only when the view leaves it, the zoom moves by more than
  1.6×, or the theme or layers change; the names are drawn every frame (crisp, sized by zoom, the biggest regions'
  first, none overlapping). Over your own image the regions are borders only.
- **The map's layer toggles are per device** (`hwyLayers` in this browser's storage, not a shared setting): how one
  screen shows the map is not an alert preference, and a phone may want the names off.
- **The background image is the player's own.** Outrider ships none; only the configured file is served, only as an
  image type checked by extension and first bytes (no SVG), never a path from the request. The default extent
  (X −45000…45000, Z −20000…70000) is the bounds quoted for EDAstro's galaxy charts and the galaxy map texture
  (40 ly per pixel at 2250 px, Sol at pixel 1125, 1750).
- **Landmarks are fixed:** Sol, Sagittarius A*, Colonia and Beagle Point at EDSM's locked coordinates, and your carrier
  where the journals put it.
- **`--simulate` is display only.** For screenshots and demos the panels read as if the game were running, with the
  last known values (fuel from the last reading, else the last jump, else a full tank; the Data tile doesn't flag the
  old journal). Nothing is invented (a target the game cleared stays cleared), every guard still reads the real
  Status.json, and the virtual keyboard, the co-pilot button, the clipboard and the overlay window are off whatever
  the config says.
- **Here's bio items never break inside themselves,** and a compact table shows a codex entry as 📖 ✦ with the name
  in its tooltip (the run beside it already names the species), so a row stays one or two lines beside an open panel.
- **History's sessions are split by 2 h without a jump.** A session's window runs from its login (the latest one
  within 2 h before its first jump) to the next session's; a login no jump followed, 2 h or more after anything
  else, opens a session with no jumps (review F31), whose "end" is its last login (nothing later is known).
- **Uploads catch up from a mark, at most a week back for EDSM and an hour for EDDN** (the author's choices over
  "live lines only"; EDDN's readers take what arrives as current, so an EDDN message over an hour old is dropped even
  at send, while EDSM is the player's own log: `eddn.CATCHUP_MAX_S`, the hub's `max_ages`). Each service's mark is the
  last journal line it handled (file name and byte offset, compared by `uploads.pos_key`), stored in meta
  `upload_marks` (live-only: a re-read sends nothing again) and in the instance's lease file, which stays at shutdown as
  a handover note: switching on starts at another instance's mark, else at the reader's position (never your history).
  Files the game overwrites (Market.json, NavRoute.json...) are caught up only while the file is still the one the
  event wrote (its time and MarketID): the last one after a short gap, older ones never. A restored database forgets
  its marks and unsent rows. Duplicates are possible only if another uploader covered a gap while Outrider was down.
- **Several Outriders switched on for one service: one sends** (`uploads.lease_owners`). The one already sending keeps
  it; with none sending (started together) or two (each started before seeing the other), the lowest instance id has
  it. No clocks are compared (two machines'), and every instance works it out the same way from the same leases.
  Nothing is claimed before the others' leases are read. An Outrider from before the rule (no `wanted` in its lease)
  holds whenever another lease names the service, so it is always given way to. Before this, both held for good and
  each followed as if the other sent (Codex F1, 2026-10-09).
- **What waits keeps its order** (review 2026-10-20 M0, `uploads.due`): while a row already tried waits out its retry,
  nothing newer of that service is sent, on purpose, even when something wakes the sender early (a key's Save or
  Check, Try again): EDSM takes a commander's events in order, and Inara's "slow down" hour holds for every request.
- **The exobiology checklist's states, best first: sold, aboard, lost, logged** (outrider/checklist.py). Lost is a
  state of its own, in red (the author's choice): you found it there, and sampling it again pays. "Not here" is the
  rules' prediction and is worded as one; a species with no rules at all (BioScan does not model it) is possible,
  never ruled out. "Parts" when every ruleset that allows the region also ties it to a place within it. Colours
  come from ExploData's tables; a species with none is its own one variant. Runs match by the game's species id, so a
  misspelled duplicate in the rules (Stratum Aranaemus) cannot split a species. It lives in the Bio/Geo tab
  (My Samples | Exo-Biology | Geology; the tab was Samples), not a tab of its own (the author: no 14th tab). **Completion** (the author's measure): the average,
  over the species possible in the region, of each one's share of its colours found there in any state, so partial
  progress counts (half of every species is 50%); a species with no colour table scores 0 or 1.
- **The geology checklist's "possible" is "reported"** (resources/geo_codex.json, scripts/build_geo_codex.py). Geology
  has no region rules (it follows a body's volcanism), so a region's entries are those players have reported there,
  counted from Canonn's per-entry site dumps; one not reported is greyed but never called impossible. The file is
  built offline and shipped (the dumps are tens of MB; it is 31 KB); run the script again to refresh the counts. Your
  codex entries match by entry id.
- **The checklists' pictures are linked, never copied** (the author's choice, 2026-10-09). Every image is a screenshot
  of Frontier's game, so none is public domain or GPL; Frontier's media rules allow non-commercial fan use with
  attribution, but bundled images would sit outside the GPL and each is a commander's own. So Outrider ships only the
  links and credits (resources/codex_images.json, scripts/build_codex_images.py, from Canonn's codex reference) and the
  page loads a picture from Canonn when an entry is opened, captioned with the commander and Canonn. The running
  server refreshes the link list from Canonn once a day into data/codex_images.json (about 650 KB asked for, nothing
  sent), used when sound (at least 500 entries) and else the shipped copy, so new pictures appear without a release.
- **A plot's end Spansh does not know yet is stood in for** (2026-10-09). Both ends are looked up in Spansh's search
  before every plot (a system known here, even where you are, is not necessarily one Spansh knows). One it does not
  know, but Outrider can place, is replaced by a Spansh system near it: of those within the ship's range, the one
  nearest the route's other end, else the nearest; for where you are, from the neighbourhood Spansh already sent. The
  real end goes back as a leg of its own, its fuel left unknown rather than guessed, and the page says what was done.
  Road to Riches and Exomastery too (`riches.splice_survey`: the real ends survey nothing); never a trade route, which
  starts from a station's market as Spansh has it (no stand-in replaces that).
- **The journal archive has no lock between instances** (Codex F8, 2026-10-09). Two Outriders sharing a backup folder
  each copy through a .part file of their own and look at the archive again just before replacing it, so a lagging
  mirror's shorter copy does not replace a fuller one. A narrow window remains; a lock would not close it on an NFS
  share (where a shared folder is likely, and locks are unreliable), and the next backup copies the fuller journal again.
- **A trade route counts tonnes, and undocking moves on** (Codex F4, the author's choice, 2026-10-09). A commodity is
  done once its planned tonnes are traded; strict counting alone would leave a stop open for good when the station
  had less than Spansh said, so undocking from a stop with anything traded there finishes it, and the voice says what
  fell short instead of the plan's profit. Undocking with nothing traded does not.
- **While another uploader has a service, Outrider follows without sending** (the hub's `follow`): its mark moves with
  the journal and nothing of that stretch is caught up later; EDDN's waits are dropped (`eddn.quiet`). A *held*
  service (a key EDSM refused) is different: it keeps queueing and sends once the key is fixed, since nobody else sent
  that stretch (the author lost twelve events before this).
- **The upload switches live only in Settings → Uploads**, written to `[eddn]`/`[edsm] enabled` (hidden from the Server
  settings).
- **An upload outage gets a card and a notification, never speech** (S3, the author's default, 2026-10-12): an upload
  that is on, has messages waiting and has failed for 15 minutes (`UPLOAD_DOWN_S`; checked each minute by
  `watch_leases`) puts a card on the notices banner and a moment the page notifies under its own alerts row
  (`uploads`, never spoken: no speech.json key, plain words as the Highway's). Once per outage; the first round the
  service answers clears the card and says "sending again after N min", not "reachable again": after a long backoff
  (up to 30 minutes) the service may have been back for a while. An outage starts with a raised round or one the
  service only asked to retry; a held key and a row settled here (no key, an hour old) neither start nor end one
  (`uploads.Recent`). Inara's own hour-long pause after "too many requests" is worded "asked Outrider to slow down".
- **Settings → Uploads' Recent list lives in memory** (`uploads.Recent`, the last 50 rounds per service; a restart
  empties it): the outbox keeps every row a week, but not the rounds, the errors or the backoff. Try again clears a
  refused EDSM or Inara key at once (the hold otherwise lasts until a new key or the switch; `State.clear_key_hold`, the
  one helper a new key also goes through) and releases an EDDN kind on hold with its refusals (else the next refusal
  holds it again); that kind's refused messages were dropped, so only new ones go.
- **"Not reported to Spansh" only for a system Spansh was asked about** (2026-10-14, reported by Kurbo26 in GitHub
  discussion #3: Sol's In-Game Route chip said it). Three states, one place (`State.spansh_knows`): known (the Nearby
  search listed it, or Spansh's record is in the cache), unreported (asked, no record: inside a Nearby search Spansh
  answered, a route hop lookup, the target's lookup), and not looked up (never asked, Spansh unreachable, or past a busy
  region's `sphere_cut`), which claims nothing. The cache holds only what Spansh had, so its silence is not an answer;
  an EDSM stand-in in it is not Spansh's either. The route chips (✦ only when unreported), the Nearby row's `in_spansh`
  (a stand-in the answer did not cover reads "not looked up", never "unreported" or "Spansh doesn't have this
  system"), the arrival briefing ("Known, not in Spansh." only when asked) and the overlay's strip ("Spansh ✗") all
  read it. The route's hops are asked about when a route is plotted (`maybe_route_lookup`): the first 24 (the chips
  shown) that nothing has answered, in one Spansh search by id64 (`Spansh.records_by_id`, the request `permit_ids`
  already made), one at a time, a failure retried after 5 minutes, each answer kept in memory for a day (no table: it
  is a display aid, and a restart asks once more). The positive answers are not cached as bases: a search-level base
  stored for its `updated_at` would stop the refresh from ever fetching that system's bodies. Hops in the populated
  regions are never asked (`ROUTE_LOOKUP_SKIP`, `route_hop_populated`: within 1,000 ly of Sol or 500 ly of Colonia;
  the author, 2026-10-14): Spansh knows every system there, and those records are heavy (Sol and Colonia alone ~190
  KB), so a bubble route would pull megabytes for an answer already known; their chips claim nothing.
- **A lookup that fails says only "Spansh unavailable"** (S42, the author's answer, 2026-10-12): the Data tile names the
  source and nothing more ("EDSM unavailable", "GitHub unavailable"), or "No internet connection" when two or more
  sources failed by DNS or no route with no answer from anywhere between (one source's DNS failure can be that
  service's own trouble). The error itself goes to Show log. Whether a source is down comes from every request of the
  lookups' session (an aiohttp TraceConfig: `outrider.health.Health`), not from the call sites, and a failure counts
  only when that source answered nothing since the request began: fifty body lookups at once with one timing out is
  not an outage. A source nothing has asked for 30 minutes is no longer called down (a daily check that failed once
  would otherwise say so all day). The page keys the tile off the payload's `health`; a failed sphere search's own
  status ("Spansh unavailable") still keeps the unreported horizon quiet until a search answers. A card on the banner
  (the one notices board) only when it lasts: Spansh or EDSM down 10 minutes, or no network / an address not found at
  once; GitHub, EDAstro and Canonn are background checks and get none. bio.py's rules check (urllib) is not counted.
  The one exception to "no detail" is a certificate that cannot be verified (issue #9, below): the tile says
  "Spansh: couldn't verify spansh.co.uk's certificate (expired): check this PC's date and time; if they are right,
  update Outrider", and the banner has one card at once for every source failing so, because the player is the one who
  can fix it and "unavailable" would send them to wait for Spansh instead.
- **HTTPS verifies against the system's store plus certifi's, not certifi alone** (2026-10-14, issue #9, reported by
  Aerics84; `outrider/tls.py`). On Windows Python verifies against the Windows certificate store, and Windows fetches a
  new or renewed root only when something asks it to: a browser does, Python does not. A site whose chain moved to a
  root the store has not fetched yet then fails with "certificate has expired" (or "unable to get local issuer
  certificate") while the browser on the same PC opens it fine. Every outgoing connection (the aiohttp sessions through
  `tls.connector()`, urllib through `tls.urlopen`; a test walks the source so a new one cannot forget) uses one context:
  `ssl.create_default_context()` (the system store) with certifi's bundle loaded into it. Not certifi alone: a
  corporate proxy's root, or one the player added on purpose, lives only in the system store, and dropping it would
  break those PCs instead. Not the system store alone: that is the bug. OpenSSL looks for a trusted issuer among both
  (trusted-first), so a root that only one of them has is enough. Without certifi (an environment installed before it
  was in `requirements.txt`, the launcher not used) it falls back to the system store, with one line in the log. A
  certificate failure is its own kind in `outrider.health.classify` ("certificate", not "tls"), worded with the host
  and the fix: the date and time first, because a wrong clock fails the same way for every site, then an update (an
  Outrider from before this fix has no certifi). The floor in `requirements.txt` is `certifi>=2024.7.4`.
- **The launchers upgrade certifi once a week** (2026-10-14, the author's decision). pip leaves an installed certifi
  that meets the requirements floor alone, so without this the bundle would be as old as the environment.
  `launch_outrider.sh`/`.bat`, after the requirements step, run `pip install --upgrade --quiet certifi` when
  `.venv/.certifi-checked` (the date of the last check, compared in Python, as the .bat compares its requirements stamp)
  is missing, 7 days old or more, unreadable or in the future. Weekly because certifi holds root certificates, which
  change rarely (a few times a year, announced months ahead); a site's own certificate, such as Let's Encrypt's 90-day
  ones, is not in it and is checked live against those roots, so a renewed site certificate needs no new bundle. A
  daily check would only add a PyPI request to most starts. Never in the way of the start: pip's output is hidden, it
  tries once (`--retries 1 --timeout 10`, so an offline start waits seconds, not a minute), a failure says "certifi:
  could not check for a newer certificate bundle (offline?); using the installed one" and leaves the stamp, so the next
  start tries again (a Settings Restart is a start: it may try again too). The Docker image needs no weekly check (a
  release builds a new one, and a container's environment is the image's), but Docker's layer cache would keep the
  certifi of the first build while the Dockerfile's pip line and the base image are unchanged: the Dockerfile upgrades
  certifi in a step after `ARG CERTIFI_CHECKED`, and `scripts/docker_bundle.sh` passes the day's date, so a release's
  build always asks PyPI for the newest (only that step and the source run again). An image built with
  `docker compose up --build` has no date passed and keeps its cached certifi until the Dockerfile changes.
- **A Nearby retry that fails again sends no payload.** A failed sphere search is asked again after 30 s, 60 s, ...
  up to every 5 minutes. With the network down each retry fails at once, the status goes straight back to "Spansh
  unavailable" and the rows are the cached ones again, yet it used to bump the payload twice: every open page (a
  tablet, the Now window) fetched and redrew for nothing. A retry now says "asking Spansh again" only once its search
  has been out `RETRY_SAY_S` (a network that swallows requests still shows it), and bumps at the end only when the
  status, the rows or the sphere's cut changed.
- **The key Check only reads, and one Inara gate paces everything** (S45, G3): EDSM's get-credits (100: the name and key
  go together; 203: they do not) and Inara's getCommanderProfile (the header's 400: the key refused; the event's 204: no
  such commander). The typed key, else the stored one; a success with the stored key ends its hold
  (`clear_key_hold`, the one helper). Keys go in a POST body, and no error's text reaches the answer or the log
  (aiohttp's carries the URL): only its kind ("Couldn't reach Inara: timeout"). One check per 10 s per service; EDSM's
  account reads at least 2 s apart; Inara's check waits on the same `uploads.Gate` as its sender (35 s), because
  Inara's two-a-minute rule counts every request with the key and whether a read counts is not documented.
- **The EDSM backfill is the one exception to the 7-day cap** (S47): uploads never send a line over a week old
  (`uploads.MAX_AGE_S`), except a range the player picks in Settings → Uploads → Fill gaps in EDSM's flight log. It is
  explicit (a range, from a Check of where EDSM's log ends before `edsm_since`, kept when EDSM is switched on), previewed
  (the events rebuilt from the live, legacy and archived journals through a Session of its own: nothing sent), guarded
  (get-logs over the whole range must be empty, else nothing is queued: never resend what EDSM has) and gentle (its own
  outbox service `edsm_bf`, one request every 10 s, UNIQUE per source so a second Send never doubles, and a line EDSM's
  live stream has is skipped). Its answers are read strictly (`edsm.backfill_answer`): the live `answer()` takes 101-104
  as sent, right for the live stream but not here, where 102 "older than what EDSM has" means EDSM did not take it.
  A first request taken by none (every event 102) stops it by itself. Its state and queue are in the database, so
  `edsm_bf_on` also asks `edsm_bf_paused`: never under `--simulate` (a run interrupted, then a `--simulate` start on the
  same data sent it before the Fable sweep of 2026-10-13), nor while another Outrider's lease sends EDSM. Installs that switched EDSM on before
  `edsm_since` existed say "unknown" and the range runs to now. The jumps between are the jumps table's (every
  commander), the events are the commander's.
- **EDSM's flight log from before your journals counts as visits, nothing else** (S67, `outrider/edsmlog.py`): the import
  keeps every entry get-logs gives (table `edsm_log`, live-only: EDSM's answer, carried by backups, out of
  `RESET_JOURNAL_DATA`) and decides at every read which count: before the oldest journal arrival (the first row of
  `jumps`) and with no journal arrival within 60 s. Both move after a re-read or a legacy folder's import, so nothing is
  thrown away at the import and journal data always wins. Not a VIEW over visits (the review's correction: visits is read
  in some 24 places, two of them box queries on its xyz index): the places that show visits ask a second, small query
  (`edsmlog.rows` with a box on its own x, y, z index, `edsmlog.ids` once per Nearby refresh and per search), and only
  those: Nearby's and Search's visited marks, the target's verdict, Find and `locate`, the route's hops, the boxel lists
  and the sector grid, the Map, History's sessions (`edsmlog.sessions`, marked `edsm`, every journal count 0; the
  all-time row stays the journals'). Never firsts, sales, discoveries, the codex or your scans (EDSM's firstDiscover is
  not kept), never `visit_count`, the left-behind list or the boxel code stats (your scans' figures). One-off: a done
  import refuses another until Remove them; a stopped one goes on from its cursor (meta `edsm_import`). Paced at one
  read every 10 s (`IMPORT_GAP_S`; EDSM limits its API per hour) besides the 2 s gate; a slow-down answer waits
  `IMPORT_RATE_WAIT_S`. A failure that passes (a timeout, no connection or DNS, an HTTP 5xx, EDSM's own msgnum 5xx:
  `readclient.transient`, `try_later`) is asked again for the same week after each of `readclient.RETRY_WAITS_S` (30 s,
  1, 2, 5, 10 min: about 20 min in all, then "failed" with the reason and "tried 6 times"; Go on resumes from the
  cursor), because the author's first real import, some 440 weeks, stopped for good at week 203 on a single timeout.
  A refusal (203, any other msgnum under 500, an HTTP 4xx) or a malformed answer stops at once: waiting cannot fix it.
  The lookups by name at the end follow the same rule (`readclient.Unreachable` names Spansh or EDSM; a name refused
  is left unplaced as before). S47's Check and guard ride out the same failures (`State._bf_read`, Stop ends the wait);
  they are reads, so a retry can repeat nothing EDSM stored. S47's sender is not retried here: `upload_loop` already
  retries a raised send (`BACKOFF_S`), and EDSM answers 101 for an event it already holds. Known limits: every imported commander counts as "you"; an entry EDSM gave no position for is
  looked up by name afterwards (here, then Spansh, then EDSM; at most 500, `IMPORT_LOOKUP_GAP_S` 3 s between two
  requests and EDSM's through its gate too, so 500 take up to an hour: back to back they were a burst), else counts
  by name only (the boxel lists, Find).
- **Upload marks in the Log** (S68): the Log only (the author's choice), from the outbox joined on its source key (the
  file and the line's byte offset: log.py splits on "\n" as the reader does, never splitlines, so the offsets agree; a
  line's `#1`, `#2` messages count as that line). Per service the worst of a line's messages wins (✗ over ⏸ over ⏳
  over ✓); a line with no outbox row had nothing to send (no mark), and a line over 7 days old gets none (the outbox
  prunes after a week). "not sent" (rows queued or dropped) overrides the category boxes, since some "noise" events go
  to EDDN; it lives in the Log's own stored filters.
- **EDDN station data goes once per visit**, not once per change: the sites date a station's data by what arrives, so
  each docking sends it again; only the same screen reopened in one docking is skipped (`VISIT_ENDS`).
- **EDDN sends what EDMC, EDDiscovery and EDDLite send, field for field** (compared on EDDN's relay, the author,
  2026-10-10). A Docked at a station on a planet's surface gets `Body` and `BodyType` "Planet" from the body you
  approached (`eddn.PLANETARY_STATIONS`), as EDMC adds them. shipyard/2 leaves out `allowCobraMkIV`: it describes the
  commander, not the station, and the other three leave it out. commodity/3's optional `statusFlags` is not sent (the
  author's call, 2026-10-10: not needed). outfitting/3 is not used (the author's call: the three main apps send
  outfitting/2). A `Location`'s body is taken only when it is a planet or a star, as EDMC does: logged in docked, the
  game names the station as the Body, which a later planetary Docked would have sent as its planet.
- **Biology samples go to scanorganic/1, never the Analyse** (the author, 2026-10-10). The schema is on EDDN's develop
  branch and the gateway takes it. Log and Sample only (Analyse can be written in another system), after the location
  cross-check, `Body` sent as `BodyID`; `BodyName` only when the body you approached has that id; `Latitude` /
  `Longitude` only from a live Status.json on that body read 90 s before to 10 s after the scan (`ORGANIC_SYNC_S`,
  `Session.status_pos`): a journal caught up later sends no position rather than a wrong one. journal/1 still drops
  `Latitude` / `Longitude` (`JOURNAL_DROP`).
- **No "New to EDSM" mark**: EDSM's `systemCreated` usually names EDDN's copy of a jump (sent at once, read by EDSM)
  rather than the player's EDSM batch, so it would almost never show (tried and removed, 2026-10-09).
- **The full-scan bonus is in the payout estimate** (plugin gaps D): 1,000 cr per body of a system you found complete
  (FSSAllBodiesFound's Count) while every star and planet was undiscovered. The sale pays it as `Bonus`, apart from
  `BaseValue`, which the calibration still compares against, so it is added only to `estimated_payout` and shown on
  its own line. Pioneer's form (non-bodies counted, the main star's discovery only) fits the sales worse. No belt
  counter: the honk's Count leaves belt clusters out and the game never says how many a system has.
- **A species missing from the price list is valued at the bio rules' figure** (BioScan's), as the predictions
  already are: Radicoida Unicus (119,037 cr there) is the one known case. Its Vista Genomics price is unconfirmed: no
  sale of it in the author's journals (checked 2026-10-09). Add it to `ORGANIC_VALUES` once a SellOrganicData shows it.
- **No x5 in a populated system** (BioScan's rule; plugin gaps C). The author's Vista sales say so: 0 of 8 runs in a
  populated system paid it, 208 of 208 elsewhere (`project/done/value-checks/RESULTS-2026-10-08.md`). A system's
  Population comes from its FSDJump / Location / CarrierJump (`system_population`); `own_firsts.bio_x5` holds the
  verdict per body, so every x5 reads one flag. Pioneer's other value rules were checked the same way and left
  out where the sales did not support them (full-map bonus, honk value, terraformable ranges).
- **A Vista Genomics visit is one x5 check** (sales under 5 minutes apart): the runs aboard before its first sale
  against everything it sold; each sale stores what it adds, so the ledger's sum is the visit's check whatever order
  the entries came in (review F21).
- **A map's "Next" gives the body's whole mapped value, without and with your bonuses** (the author's choice,
  review Q5): "Next: map 7 (771k/2.2M)", spoken "771 thousand, 2.2 million with bonuses", one number when no bonus
  of yours applies; on Now's Next line, the mapped call-out and the status report. Which bodies make the list and
  their order still go by the bonus-free increment (what mapping adds), as the green-row level does.
- **A malformed speech file is not installed** (Codex F7): valid JSON whose lists hold anything but strings keeps
  the last good document in use, with the problem shown; bans keep working.
- **"Lost contact" is the server's silence only** (review S13): said after 30 s without an answer, by the browser's
  voice. A silent journal while the game runs is not treated as deafness: the game is often quiet that long (carrier
  jumps, long FSS and SRV stretches).
- **The long poll is gzipped, never deflated** (review S20): browsers disagree on what "deflate" means.
- **The jump line waits for the hyperspace tunnel** (review S14): the card shows at the charge (StartJump), the
  words are held and released by a "hyperspace" moment (Status.json's FSD-jump flag after that StartJump, which
  comes about 2 s before the countdown ends: the line starts 2.5 s after it, with the tunnel), or after 8 s when the
  flag never comes. Its `speech.json` lines (S15) carry only `{system}`: the scoop and hazard sentences
  follow outside the template, since check() never requires a placeholder and an edited line must not drop a
  neutron warning.
- **The next line is synthesised while the current one plays** (review S11), and only once the current line's audio
  exists (Speaker's lock taken first by a warm-up would make the line being said wait): the PC's play request names
  the next line; the browser's Piper path posts it to /api/say/prefetch after decoding its own.
- **Volume is per device and scales the samples for the PC** (review S12): the players' own volume flags differ
  (aplay has none), so the server scales the 16-bit WAV it hands them.
- **Your own sounds are WAV only, up to 3 s** (review S16): every player and browser takes WAV, and the voice waits
  for a sound to end (the page holds it for the file's length, at most 3 s).
- **The voice lab is part of the page, outside the alert queue** (the author, 2026-10-11; it was a separate Tk window,
  `voice_lab.py`, now removed). It plays in the browser in use from the server's Piper (`api/say`), so it works on a
  Docker server and the tablet and needs no python3-tk, and never goes through the alert queue, hush or "play on this
  PC". More voices downloads a voice without switching to it: you hear it first, then Use this voice. A voice trained
  on many people speaks as the speaker picked for it, kept per voice (meta `voice_speakers`, live-only); before, the
  first speaker always spoke.
- **A voice per personality is kept by the server** (S40, 2026-10-13; the author's default of 2026-10-12): Settings →
  Voice → Personality voices and the voice lab's Give to this personality store {style: {voice, speaker}} in meta
  `style_picks` (live-only, like the voice itself), so every browser and the tablet say a personality the same way.
  A pick wins over speech.json's own `voice` / `speaker`, which win over the main voice; the pace stays speech.json's.
  The page still sends the voice and speaker with each line (the server never downloads one for it): a picked voice
  deleted later is said in the main voice by that voice's own person, never by the pick's number of another voice.
  Worth having mainly where personalities share one several-person voice; each other voice picked is another loaded
  model (as many kept as `[speech] voices_loaded` says, the least used reloaded).
- **The crew: who says a line** (crew batch 1, 2026-10-13; the author's plan and answers of that day). Off by default:
  one voice for everything, exactly as before. On, each alert row (Settings → Alerts) belongs to a role
  (`outrider.speech.CREW_ROLES`, the one table: the page reads it from GET `/api/speech`, a test keeps it in step with
  page.js `ALERTS`; the Navigator keeps every route line, trade routes too; low fuel is the Chief Engineer's). A line
  is resolved on the page (`crewMember`, `crewVoice`): the crew on → a danger line (`DANGER`) is Tactical's while the
  Danger switch is on (default on, so a danger line is never mistaken for chatter; off, it stays with its row's
  member), else the row's member (a row moved in meta `crew`'s `rows`, else the table's) → that member's personality
  picks the lines (when it has lines for that alert; "as the XO" is the personalities ticked in that browser, the shift
  included) → its voice and speaker; a voice left "as the personality" falls back through S40's pick for the line's
  personality, then speech.json's, then the main voice. "Danger alerts always down to business" still decides a danger
  line's words; the crew only decides whose voice. The priority (danger first) never changes. The words never change
  either: a role only picks whose personality's lines and whose voice.
- **The XO is the main voice and stands in for everyone** (the author, 2026-10-13). The XO / Co-pilot row and the main
  voice are one setting: meta `crew` keeps only the XO's name; giving the XO a voice switches the main voice (as POST
  `/api/voice`). Voice answers, the status report, the co-pilot's lines and any line that is no alert row's are the
  XO's. Whenever a member cannot speak, the XO says the line instead, never dropping it: a voice not installed, one
  that failed to load, a speaker number the voice lacks, a personality speech.json no longer has (the payload's
  `crew.members[role].fill`, `State.crew_fill`), and an alert row no role covers (the page). The server checks again
  when it says a member's line (the page sends `role` with its voice: `synth`). Each fill-in is written to the server
  log once per voice (or personality) and reason ("crew: Engineer's voice en_GB-x not installed: the XO speaks for
  it"), only while the crew is on. The voice lab's lines and the pronunciation tests keep the lab's voice.
- **Voices kept loaded: a number the player picks, not a fixed cap** (crew batch 1; the author: a 64 GB PC could keep
  20, a small machine fewer). `[speech] voices_loaded` is a number (exactly that many beside the main voice, whatever is
  in use), "all", or unset: the voices in use (`State.voices_in_use`: the personalities' and, with the crew on, its
  members'), up to 4 (today's behaviour for anyone who never touches it). A value it cannot read is 4, said at start.
  Never under 1 (a voice tried in the voice lab needs a place). The main voice is loaded on its own: never counted,
  never set aside. A voice set aside waits about a second when it speaks again. `[speech] voices_preload` (off by
  default: a quicker start) loads the voices in use, up to that number, one at a time after the journals are read and
  the main voice is ready. Both are config keys, not per browser: they are about the machine that speaks.
- **The memory rule of thumb** (measured on the author's PC, 2026-10-13, a scratch process, nothing played): a loaded
  voice takes about 1.6 × its `.onnx` file's size (en_GB-cori-medium's 64 MB file: ~100 MB per extra copy; cori-high's
  114 MB: ~170 MB). The people of one several-person voice share a single load (vctk's 109 speakers in one ~75 MB
  model), so a crew made of one many-speaker voice costs no more than one voice. The payload's `voice_memory`
  (`outrider.tts.voice_memory_estimate`) is computed on the server from the installed files, per distinct voice in use,
  never the main voice; the page never guesses it.
- **The crew's Settings screen** (crew batch 2, 2026-10-13; the author's approved mockup of that day). Settings →
  Voice, top to bottom: the main voice (labelled "= XO" with its hint while the crew is on; it stays first, above the
  personalities, as the page had it), Voices kept loaded, the Crew switches and table, the XO note, then Personality
  voices (S40's table, its heading saying crew members "as the personality" use it). Voices kept loaded shows whenever
  any voice besides the main one is in use (a personality's too, not only with the crew on), since `voices_loaded` sizes
  the same LRU either way. Its note is coloured by the whole setup's memory (amber over 500 MB, red over 1 GB); the
  figure beside Keep loaded is the N largest voices' (the worst case, as the plan says), summed in the page from the
  server's per-voice figures so it follows the number picked before the server answers. Keep loaded and Load them at
  start write `[speech] voices_loaded`/`voices_preload` through POST `/api/config` like Server settings, but those two
  keys are applied at once (`State.LIVE_CONFIG`, `config_live`): a selector that only took effect after a restart would
  read as broken, and both only size an LRU or say what the next start does. With the crew off only its switch shows;
  the table, the Danger switch, the audition, the Alerts table's Crew column and the "= XO" label hide, and the Crew
  column's cells are emptied, so Find a setting finds no role names there. The crew's selects are `data-sfone`: Find a
  setting reads only their choice, not every role, voice and personality they list (a search for "navigator" would
  otherwise show every alert row). The mockup was drawn a full screen wide; the dialog's column is about 600 px, so each
  member's row is a grid (the same columns on every row): its name, personality, voice, speaker, ▶ and ↺ on one line,
  Speaks for under them, and at phone width two columns. Speaks for is worded from the page's `ROW_WORDS`, at most six then "and N more";
  a danger row's owner is kept in the Alerts column with "· spoken by Tactical (danger)" beside it (the carrier's row,
  whose departure warning alone is danger: "its danger lines by Tactical"). ▶, the by-crew audition and (batch 3) the
  crew-lines audition play through the voice lab's player, never the alert queue, as S40's ▶ does. The tablet's Settings
  sheet has none of it: the crew is set on the PC.
- **Crew members mention each other** (crew batch 3, 2026-10-13; the author's idea of that day). One placeholder per role,
  named by the role's id (`{engineer}`, `{xo}`...; `outrider.speech.CREW_WORDS`, served as `crew_roles`' `words`):
  the member's name when Settings gives it one (the name in every position: "Mira", never "the Mira"), else the role
  as a crew says it ("the Engineer", not "the Chief Engineer", which stays Settings' title; Comms and Tactical without
  an article), capitalised at a sentence's start. A sentence's start is judged on the line as filled so far, not on the
  template, so "{text} {engineer} agrees." after a briefing ending in a full stop says "The Engineer". Such a line is
  picked only while the crew is on: with it off every alert sounds exactly as before, which is why every list keeps at
  least its old plain lines (the checks report a list of crew lines only, and a 👎 that would leave a list none is
  refused, 409). A member never mentions itself: `check()` rejects a line naming whoever says its alert on the default
  table (`crew_speakers`: the rows' member, Tactical for a danger key since the Danger switch is on by default, the XO
  for speech on), which needs page.js `ROW_KEYS` and `DANGER` in Python too (`outrider.speech.ROW_KEYS`/`DANGER`, kept
  in step by a test); a row moved in Settings → Alerts, a danger line with the switch off, and the XO standing in are
  covered at pick time instead (`crewLineOk` against the member `crewMember` resolved). The placeholders are optional for
  every alert rather than listed per key in `KEYS`, so a player can add them anywhere. The shipped lines (78 per
  personality list, 3 per alert for 26 alerts where one member mentioning another is natural: arrivals, briefings,
  bodies, biology, fuel, the hull, sales, the carrier, the session's end; never the one-word acknowledgements) talk
  about the member, never to it, since a vocative would read "The Navigator, plot a course"; and they claim nothing a
  crew member could not know (opinions and advice, no invented ship faults). "XO" has a shipped respelling, "ex-OH"
  (resources/pronounce.json), since espeak reads it "zo". Audition: crew lines plays one such line per alert in each
  personality with made-up names (`CREW_SAMPLES`) for a member without one, so the author can judge them by ear.
- **Find a setting filters, it does not search a list** (S39, 2026-10-13): the box at the top of Settings hides what
  does not match in place, so a match is the setting itself, ready to change. A row shows when every word is in its
  text, its section's heading or the config key it defaults from (`data-find`), at least one in the row itself; a word
  naming a section shows all of it. What it opens or hides is never remembered: clearing it (or closing Settings) puts
  each section back as it was. Context over precision (the author, 2026-10-13, after "crew" showed only the XO's row):
  a word naming a titled block (`data-find-block`, marked explicitly rather than guessed from the markup) shows the whole
  block, and a table with a row matching shows whole, the matching rows marked (`.sfmark`; those named in their first
  cell when there are such, so "tactical" marks Tactical, not every member whose danger lines Tactical says). Server's
  config sections stay context, not blocks: their titles list their keys ("network, password, paths, backups").
- **Hard words are given as respellings** (2026-10-12, `outrider/pronounce.py`). Piper's English voices read the
  exobiology Latin by espeak's English rules; `resources/pronounce.json` gives each genus and species word as a
  respelling ("fon-TIK-yoo-loo-uh", the stressed syllable in capitals, or raw `[[phonemes]]`), and each syllable goes
  through Piper's own espeak in the voice's own accent. Whole words only, English voices only. Your own
  `data/pronounce.json` goes on top (the voice lab's How is it said box); the phrase cache's key carries the table's
  version, so a change is heard at once. The shipped respellings are a first pass, to be checked by ear.
- **Sector names by rule, phonemes written directly** (2026-10-12, the author's ask; `sector_*` in
  `outrider/pronounce.py`). Procedural sector names are built by the game from a fixed set of pieces, so a list could
  only ever hold the sectors seen: they are read by rule instead (consonant and vowel clusters, vowel runs to sounds
  from `SECTOR_VOWELS`, consonants between two sounds one before and the rest after, stress first of two else the second
  last). The community's piece list was not used (no licence found); the clusters give the same syllables. The rule
  writes its phonemes itself, British or American, not through espeak, which guesses made-up spellings ("ligh" as
  "lig", "loks" as "lokes"). Only words right before a system's code count (a capitalised word of `speech.json` leading
  them is English: "Leaving Smojooe ..."); hand-named "... Sector" and "... Dark Region" names never. Tested against
  every sector seen on EDDN in two days of all apps' traffic and in the author's journals (tests/fixtures/sector_names.txt).
  A voice's own phoneme map is checked at speaking time (`apply(known=...)`): a word needing a sound the voice lacks
  is left as text, so a future voice trained another way never loses a sound silently.
- **Two status reports** (review S23, done): Vespa's "status report" is composed on the server (`outrider/ask.py`:
  the system, fuel, unsold, the Highway's next stop); the co-pilot button's double tap and the Now bar ask the window
  that speaks for the page's, which depends on each browser's thresholds and plan logic.
- **Header tiles: tooltips on cut lines, no wrapping yet** (review S17): wrapping or click-to-expand would change the
  header's height and the app layout; left for the author. The tiles' fold has a per-device mode (S44): auto (a
  small window), six, line, or none, which follows the shared `tilesCollapsed` that ▴/▾ sets; ▴/▾ also makes its
  choice this device's.
- **The link pill's "unlinked" is the long poll's limit, not quiet** (review S41): the server answers within 25 s
  even with nothing new, so "unlinked · retrying" starts at 30 s without an answer (amber; red once the link is down).
  States only, no timer, on the desktop and the tablet alike (the author, 2026-10-12; the ticking seconds distracted
  them): "linked", "linked · no game" (the game not running: `freshness.live`), "unlinked · retrying". A long poll with no answer by `POLL_TIMEOUT_MS` (40 s) is aborted: a hung link (the PC
  suspended) becomes "no link" and "Lost contact" instead of "stale" for good.
- **The README is a front page; the guide is `docs/guide/`** (the author, 2026-10-07: the single README had grown to
  1,000 lines). Plain Markdown in the repository, not a wiki or a docs site: versioned with the code, changed in the
  same commit as a feature, no build step. Implementation detail lives in code comments and these notes.
- **Your carrier's cargo: a sell order confirms it, period** (the author, 2026-10-07). The carrier's Market.json
  lists only commodities with an order: a sell order shows its Stock, the holding; a buy order shows only what it
  still wants (silver: Stock 0, Demand 1, with 7 t aboard). So a sell order's Stock is the count, with no special
  cases for a partial order ("too many eventualities... at least until someone complains"), and the README tells
  players to put a deterrent-priced sell order on what they want counted. The rest is folded from the journal in
  time order (`outrider/cargo.py` `carrier_fold`, rules in its docstring): your transfers and trades there, a sell
  order's amount as a floor (the game sells only what is held), a buy order's filled part worked out at the next
  market, Recount for what nothing shows. Checked on the author's carrier: its whole history (back to 2025) folds
  to 16,076 t against the 16,085 t it reports, the 9 t gap being the two lines no order ever showed. A buy order's
  fill is not added to the carrier's reported total when a CarrierStats came since the market read before it: the
  game writes one just before Market.json, and it already holds the fill (counted twice it made a false gap; Fable
  sweep 2026-10-09, correcting the same night's first fix).
- **Why not Frontier's companion API** (the author, 2026-10-07): it would list the carrier's cargo whole, but it
  means signing in to Frontier (as EDMC and Inara do). Outrider never does: it reads the player's own journal files
  and talks only to the public services listed under "Nothing is uploaded unless the player switches it on" above,
  so the player's Frontier account is never involved. The sell-order method is the price of that, and the README says so.
- **Old carrier history is trusted only while it adds up.** Unjournaled trades (other players buying from an old
  sell order) leave old lines wrong: the author's 2025 colonisation hauling left 34,000 t tracked that was long gone.
  At a market read that finds the carrier holding less than is tracked, tracked lines with no news for 30 days go
  (`SEEN_STALE_DAYS`); a real one that went with them shows as the gap, for Recount.
- **What you paid is the game's average cost** (a purchase reweights it, a sale or transfer leaves it, the game's
  own `AvgPricePaid` on a sale corrects it): "Avg 45,210 cr/t (2 lots)", one purchase without "Avg", "on 40 of 64 t"
  when mined or transferred tons have no price. Only the ship's hold has it; the carrier's lines do not carry it over.
- **The carrier's tritium shows only while tritium is on a sell order** (the author): only then is the hold's count
  confirmed; otherwise the tile is as before. The jumps use the fuel per jump `round(5 + ly × (25000 + used + depot)
  / 200000)`, fitted to the author's 27 recorded carrier jumps (exact on 26; without the depot's own weight it reads
  1 to 2 t low; `used` leaves out a buy order's reserved space, which weighs nothing), jump by jump at 500 ly with
  the hold topping the depot up.
- **The trip to you is the fitted formula, scaled by history later** (S13 A; the author accepted the proposal,
  2026-10-12): `carrier_trip` splits the straight line into equal legs of up to 500 ly, each burned by `carrier_burn`
  with the depot lighter by what the legs before burned (topping up from the hold moves weight, it adds none); its `k`
  is 1 until the carrier's own past jumps give a factor (S13 B). A plain average of past jumps would be worse: the burn
  depends on the distance and the mass. Red when the depot lacks it; amber when a confirmed tritium line covers it
  (`trip_top_up`: "before" the jumps while the 1,000 t depot can take it all, else "on the way" when `carrier_jumps`,
  which tops up as the depot runs down, still reaches the trip's jumps; the Fable sweep, 2026-10-13).
- **The carrier's own jumps scale the formula, never replace it** (S13 B): `carrier_burns` measures each jump booked
  and confirmed (a CarrierJumpRequest, not cancelled, then a CarrierLocation or CarrierJump in that system) that has
  one depot reading on each side (CarrierStats' FuelLevel; a CarrierDepositFuel is a reading too, Total − Amount before
  it and Total after) and no other jump between them; `burn_factor` is the median of the last 12 burned ÷ formula, from
  3 on, held to 0.8–1.2, and scales the trip, a booked jump and the tile's jump count. On the author's journals: 214
  jumps measured, 193 exact and the last 12 all exact (k 1.0); the outliers are 2024's (about ×1.1 throughout: a game
  change, or mass the stats do not show) and jumps with another reading gap. Jumps longer than 500 ly are dropped (a
  move missed between). Tritium donated by others is unjournaled and reads low: the median and the hold are why. The
  fixed reserved-space bug (S13's review) shows why it only scales: a free-floating factor would have hidden that
  error rather than fixed it.
- **Synthesis recipes: published until you make one** (S15): `SYNTH` holds the published recipes (EDEngineer's
  blueprints.json and EDDiscovery's RecipesSynthesis.cs, which agree on each, the journal names EDDiscovery's) with
  the journal's Synthesis `name`; each Synthesis you make is kept (`recipes`: its latest materials, how often), and a
  recipe you have made overrides the table and is shown ✓ with its date, whatever the table says ("the published
  recipe said otherwise" in its title when they differ). A name the table lacks (Ammo Basic, AX Remote Flak Ammo
  Basic...) goes to "Other recipes you have made" rather than being dropped. The names are matched without regard to
  case; only Limpet Basic, Fuel Basic, Repair Basic and those two have been seen in the author's journals.
  Layout: the FSD injections' three cards always open, every other group one folded line (per device).
- **Upkeep at the published rates, said so** (S61): the journal has no upkeep figure, so `CARRIER_UPKEEP` (the core
  5M a week, each service active or suspended) is the community wiki's, not checked against the game's Finance
  screen; the tile's title says "published rates" until the author confirms them. Weeks = the balance ÷ the week's
  upkeep (upkeep is drawn from the balance: the reserve stayed put while the balance fell); amber under 4 weeks (the
  author's default). On the author's carrier the table gives 13.70M a week against a 13.58M fall in the balance over
  an upkeep day: close, not proof (the market moves the balance too).
- **A carrier's services: the newer word wins** (S55 B): the last Docked's StationServices (a suspended service is not
  listed) or the crew (CarrierStats' Crew, then each CarrierCrewServices), whichever is newer; only the crew says
  "suspended". Your carrier among the nearest places to sell (S55 A) is the journal's, never Spansh's report of your
  callsign (it can be weeks old), in a list only while that service is on, never once decommissioned.
- **The Sell / Buy lookup asks Spansh's station search, never its own market data:** best price (the same price
  nearer first) or closest, within a distance (best price needs one), fleet carriers out unless ticked (their orders
  are often years old and top every list), the pad from the ship's type (`SHIP_PAD`; an unknown ship gets no pad
  filter and says so). No commodity analytics or profit-per-hour: a lookup, not a trading tool.
- **A decommissioned carrier is shown in red, never hidden** (the author, 2026-10-07): if Outrider got it wrong, a
  vanished tile would hide the mistake. `CarrierDecommission` (requested, `ScrapTime` about a week on) shows
  "Decommissioning: scrapped <date>" with the refund; after ScrapTime (the scrapping itself writes nothing)
  "Decommissioned <date>", and the tritium lines go. `CarrierCancelDecommission` undoes it. Carriers cannot be sold
  in the game, so there is no "sold". A carrier bought since (`CarrierBuy`, or the first `CarrierStats` of another
  id) starts its state afresh: before PARSER_VERSION 41 a new id inherited the old one's place and booked jump. No
  carrier in the journals at all: no tile.
- **Nearest place to dock is a finder, not a route type** (the author, 2026-10-08): finding the place is a search and
  getting there is just a destination, so "Plot here" fills To and the Highway's plotters, following, 🎯 and auto-target
  do the rest. Docking other than "All" is a warning, never a reason to hide (friends, squadron, or not reported:
  Outrider cannot see the owner's lists, and Spansh has no setting for some carriers). The DSSA list (EDAstro) is
  fetched only when the finder opens, at most hourly and conditionally, its last copy kept; the voice and the AI's tool
  never fetch it (`cached=1`). DSSA carriers carry a badge (the author's ask). Reports older than 30 days are hidden by
  default, with the count said: carriers move, and Spansh keeps reports years old.
- **Material traders are Spansh's word, never a guess** (S54, probed 2026-10-12: `scripts/trader_probe.py`): a station's
  trader kind is Spansh's `material_trader` field (Raw, Manufactured, Encoded), and its search filters on it, so a raw
  trader is asked for as one (near the author only 5 of the 50 nearest traders were raw). The economy is not used as a
  fallback: of the galaxy's 1,639 traders only 7 have no kind (Colonia's outposts with a Colony economy, a megaship),
  and their economy says nothing. They count for "any material trader" only. Materials' "⇄ nearest raw trader" opens
  the finder with that need for that opening only: the player's saved filters are not changed by a link.
- **Start-up problems go on a banner, dismissed until a restart** (S5a, the author, 2026-10-12): what used to be printed
  only in the terminal is a notice in every window and the tablet. The dismissal is the server's, in memory: every
  window agrees, a restart shows it again (still wrong, still worth saying), and a notice whose text changed is a new one.
  One board for every such notice (later the colour tables, outages, a failed backup), never a per-device dismissal.
- **Outrider's log is its terminal, kept** (S5b): the Python output only (the overlay window's piped in); the players and
  the clipboard programs still write to the terminal alone. The file lives beside the database, not in `data/`, so a
  second copy (`--db`) or verify.sh's scratch server keeps its own. Secrets: the code never prints them and the log
  hides them again (`serverlog.hide`), since an exception's text could carry one.
- **A journal re-read is backed up first, always** (S4, 2026-10-12; the recommended default the author accepted): it is
  the one destructive step Outrider takes by itself (journal-derived tables cleared, then rebuilt from journals that
  may be gone: an uninstall under Steam/Proton deletes them), so it is backed up even with `backup_every_days = 0`.
  The zip is tagged after its stamp (`…Z-pre-reread.zip`) so it sorts and rotates with the others: a prefix would
  sort after every dated zip, never rotate out and stay `--restore`'s default. It does not touch `last_backup` (the
  Data tile's line is about the regular backups). A failed one does not stop the re-read (it was asked for): stderr
  and a banner. More than half the journal files the database was read from gone: a banner too, pointing at
  `--legacy <backups>/journals`.
- **Backups are listed, never restored, from the page** (S44): a restore replaces the database Outrider has open, so it
  needs Outrider stopped; the page gives the command for this install (the launcher, the .bat, or Docker's stop, a
  one-off `run --rm`, `up -d`) with Copy. Whether a zip was automatic or by hand is not in its name: only the latest
  is known (`last_backup.auto`), the rest say nothing rather than guess. `--restore` refuses while `<db>.lock` is held
  (an OS lock held by run(), gone with the process however it ends), which the port check cannot see from another
  container or another port; the lock file itself stays (deleting a lock file races whoever opens it next). Two
  Outriders on one database are not refused, only said on the banner.
- **Restart from any device, guarded like the settings** (S10; the author, 2026-10-12): POST `/api/restart` has POST
  `/api/config`'s guard (never cross-site; from another device signed in when a password is set), not `pc_only`: a
  Docker server is always reached from another device. Saving the settings from a device could already change paths
  and the password; the restart only makes it take effect now, and it is not destructive (the clean stop, the quit
  backup first). How it starts again: `launch_outrider.sh` exports `OUTRIDER_LAUNCHER` and Outrider execs it in its
  own place (same PID, terminal and Ctrl-C, and the setup runs again after a `git pull`); started without it, it execs
  `ed_outrider.py` with the same arguments; Windows has no real exec, so it exits 75 and `launch_outrider.bat` loops;
  Docker exits 75 and the restart policy starts the container again (refused in its first 15 s, as Docker skips a
  container that ran under 10 s); the service S70 installs exits 75 too (below). Never `--rescan` twice. A process that
  is not `ed_outrider.py` itself (verify.sh's `python -`, the tests) cannot restart: the button says why.
- **The starting page: a second small app on the same port** (S9): run() starts it before it opens the database, so
  a long re-read (the backup before it, then years of journals) answers at once: `/` and `/tablet` a self-contained
  page ("Reading your journals: March 2024, 41%", Show log), `/api/version` in its usual shape (Docker's health check,
  the Android app), every other `/api/` 503 `{error, code: "starting"}` (no API_VERSION bump: the app shows an unknown
  code's text). The real app takes the port over when it is ready (the starting runner cleaned up, then the real
  site bound: a gap of milliseconds that the page's retries cover). The import stays on the event loop, one journal
  file at a time (`import_journals`; the database connection is the loop thread's: a worker would need its own),
  so each request waits at most for one file; the backup, which copies the database and the journals, runs on a
  worker with `journals_gone` worked out first. Progress is bytes read of bytes to read (a file in two folders
  counted once), the month from the file's name; 99% at most until it serves. A SIGTERM sets the stop event, seen
  between two files (each committed whole: the old handler raised mid-file and had to roll back) or after the
  backup (nothing cleared yet). A device on the network that is not signed in sees only "starting" (the session is
  checked against the database read only; no secret is made before State). Docker's health check is healthy during
  the import now, so its start period is 2 minutes, not 30.
- **Start with this computer: enabled, not started; exit 75 under systemd** (S70): `--install-service` (or Settings,
  from this PC's own browser only: a service is the computer's, not a device's; not `pc_only`, a Linux server has one
  too) writes a systemd user unit running `launch_outrider.sh` with the arguments given (paths absolute) and enables
  it; starting it while this Outrider holds the port would fail, so it starts at the next login (the words say how to
  switch now). It sets `OUTRIDER_SERVICE=systemd`, which makes Restart exit 75 (`RestartForceExitStatus=75`) rather
  than exec in place: systemd then starts the unit as itself, and `Restart=on-failure` covers a crash. Every start
  counts toward systemd's start limit, asked-for restarts too: 30 in 600 s (10 in 300 s locked the service out after a
  run of Settings restarts) still stops a crash loop at `RestartSec=5` in minutes; the page's "not back yet" words for
  systemd name `systemctl --user reset-failed ed-outrider`.
  `TimeoutStopSec=330` is over the 300 s Outrider waits for a backup at shutdown; `KillMode=mixed` leaves the overlay
  window to Outrider's own stop. A game PC's unit is part of `graphical-session.target` (the overlay, the keys and
  the game's window need the desktop), a server's of `default.target`. Windows: a `.cmd` in the Startup folder
  starting the .bat minimised (its loop on 75 already restarts). Docker and macOS are refused with words.
- **Auto honk's readiness only looks** (S69): Settings says before you tick it whether auto honk can work (evdev, the
  `uinput` module, `/dev/uinput` writable, Primary Fire's keyboard binding), with the fix. It never creates the virtual
  keyboard to find out: that is exactly what could press a key. The udev `uaccess` rule is the fix offered first; the
  `input` group works too but lets every program read every keyboard. GET `/api/autohonk/check` is game-PC only.
- **Space chatter** (#15, `outrider/chatter.py`): the server only says where you are for it (`where()` from
  Status.json's flags and GuiFocus: "space" in supercruise in your ship, "planet" on foot or in the SRV on a planet)
  and what keeps it quiet; the speaking window keeps the clocks and picks the lines, so a page that is not speaking
  never chatters and no chatter crosses to another window. It is not an alert: no alert row, no cooldown, no 🗣 tick;
  it goes last in the queue (`speechPrio` 4), never over anything queued or playing, and a dialogue's later lines go
  if an alert came in after it started. Its lines live in the speech files beside the alerts' (keys `chatter_*` and
  `chat_<topic>_ask/answer`), so personality files, bans and the checks work on them unchanged; a chatter line with
  a value it cannot fill is never said (`lineStrict`), unlike an alert's last resort. Unsold data is never a blocker
  (the author always carries a lot), nor is the suit's very cold or very hot, common on the worlds you sample
  (low health says when the temperature hurts); on foot in a hangar or a social space is docked, as everywhere
  else, since a planetary port's concourse also sets on-foot-on-planet. Two stations of one personality ("as the XO" counts as the XO's) or of one voice
  and person never talk to each other, or it would sound like one person talking to themselves. The topics are mostly
  the stations' own work (`PERSONAL_SHARE` 0.25).
- **The terminal's times are the terminal's only** (`outrider.serverlog.Console`): Show log and `outrider.log` keep
  each line as printed (they carry their own times), so a line matched in a test or a guide reads the same there. The
  subject is padded only for a few lower-case words before the first ": " (never a path or an exception's name). Long
  lines wrap only on a real terminal: a pipe (Docker's log, a file) keeps whole lines for grep. Under systemd
  (JOURNAL_STREAM set) the times go, since the journal adds its own.
- **Chat read aloud stays private and polite** (#17, `Journals.handle_chat`, page.js `takeChat` / `chatPump`): other
  players' words are kept in memory only (Journals.chat, CHAT_KEEP; in the checkpoint so a retried tick never reads
  them twice), never in the database, outrider.log or the voice's cache (api/say and api/say/play take `private`:
  Speaker.say's keep=False, no prefetch, an error printed without the words). Live only (live_event), never an NPC's
  or your own. The page paces it (CHAT_GAP, CHAT_SUMMARY, CHAT_STALE) because squadron chat comes in bursts (the
  author's journals: 280 of 394 messages within a minute of the one before); a mention of you skips the pace. Chat is
  no alert for chatter's quiet (lastAlert is left alone).
- **Carrier trips plan, never fly** (#19): the game books one carrier jump at a time, so a trip is a list of legs
  followed on the tile, never a route Outrider targets or presses keys for. Spansh's router assumes the depot full at
  every jump; `carrier_route_legs` follows the real depot instead and marks only the legs that need tritium moved
  across. The leg advances on the carrier's position (`carrier_trip_follow`), which moves on the booked jump's
  departure (settle_carrier) and is corrected by a later CarrierLocation: accurate enough (the author), and "ready?"
  rather than "ready" until the journal confirms. The cooldown is CARRIER_COOLDOWN_S from that arrival: an estimate,
  since busy systems and the servers delay it and only a player docked on the carrier sees the real jump. No automatic
  clipboard: the author found it confusing when not expected.
- **Surface pins live in the places that exist** (#16, the author: UI space matters): no tab or panel of their own.
  A body panel's folded 📍 Pins section, the map's legend (its title holds Pin here and copy), one line in the strip /
  Now only while a pin is active, a one-character 📍 in the body lists, Bookmarks' list only when there are pins. Keyed
  by the system and the body's full name (the panel, the map and Status.json all have it; a body id is not always
  known). Only the active pin is guided or spoken: the others are drawn, never said. The tick refreshes the page as the
  guidance changes (State.pin_watch: a distance step and a 10° turn), so it moves from orbit, above the map's 1,000 m.

## Known limits

- **New versions: a notice, never an update** (`[server] update_check`, on by default). GitHub's latest release at
  start (after a minute) and daily; a newer one is a quiet pill in the theme's accent, not an alert or a spoken
  line, with the steps for this install (Docker, a git clone, a download). No self-update: a container cannot
  replace its own image, a download cannot safely replace its own files, and a clone's pull is left to you (Settings →
  Server's **Restart** then finishes it, S10). Watchtower, the usual Docker auto-updater, is archived (2025), so the README names none.
- **Key presses on Windows are a stand-in for evdev** (`outrider/winkeys.py`): the same evdev key names mapped to
  scan codes and sent with `SendInput` (scan-code mode, extended flag for arrows, right Ctrl, numpad Enter...), so
  auto honk, auto-target and the rail run unchanged above it. Chosen by platform at start (`honk.keyboard_backend`).
  Experimental: checked under Wine (a low-level hook saw the right scan codes and flags; Wine reports right Ctrl's
  virtual key as left Ctrl, the scan code and flag being right), never yet against the game on Windows. Windows
  drops keys sent to an elevated window, without an error. The co-pilot button (reading a HOTAS) is still Linux
  only: Windows' simple joystick API stops at 32 buttons.
- **Windows runs the rest** (`launch_outrider.bat`): journals found in the Windows save folder, every file read and
  written as UTF-8, no SIGTERM handler there (Ctrl-C). Less tested than Linux: players run it on Windows, the
  author does not.
- **Core module health is as of the last Loadout or repair;** the journal logs nothing in between, so jet-cone
  boosts since are only counted.
- **Status.json does not update while you stand still,** so positions can be up to a reading old.
- **Which notable stellar phenomenon you dropped at is not known:** the journal says only "a ring phenomenon", and two
  sites can share a ring, so each drop counts as one site visited (`phenomena_sites`): dropping twice at one site counts
  twice. A system's count is the most one FSS listing had (the game lists several of a kind as identical lines).
- **Streak dots for arrivals before the strip existed are hollow** (Spansh cannot be asked about the past);
  carrier jumps usually have no arrival-star scan.
- **A carrier jump booked just before quitting shows as "not yet confirmed"** until the next login.
- **NPC crew deaths are not subtracted** from the crew count: the evidence showed that would be wrong.
- **Spansh cannot search for planetary mining locations;** that search is Local only.
- **The neutron plotter gives waypoints, not fuel:** no fuel columns or refuel stops; the exact plotter has them.
  The page hides the ⛽ column and the map's refuel legend on a neutron route and says "scoop as you go".
- **A Loadout's MaxJumpRange can leave the Guardian booster out** (powered off, or written in outfitting): the drive's
  figures are kept, the booster counts only when it is on; a typed neutron range keeps the booster floor only with a ship.
- **Region borders follow the grid,** cells of 4096/83 ≈ 49 ly, so close up they are steps, as the region map defines
  them; a name sits at its region's centroid (or the region's cell nearest it), so zoomed in it may be off screen (the
  scale bar's "centre:" says the region under the middle).
- **The too-heavy check needs a live arrival:** after an Outrider restart in a route system it waits for the next
  arrival there (as the clipboard copy does). It trusts the fuel model's range scaling, not Spansh's own code.
- **Your carrier's untracked lines can be wrong** until a market read or a Recount: other players' purchases from a
  sell order are journaled nowhere, nor is a sell order that ends without a CancelTrade (cargo moved out under it).
  The total check against CarrierStats shows the gap; it is only as fresh as the last time the carrier management
  or market was opened. A confirmed count is as fresh as the market read: from a day on its mark says how old ("✓ 9
  d", amber after `CONFIRM_STALE_D` 7 days, when the carrier's heading asks for a market read; S58).
- **Recount takes only commodity names** (S57): the names your journal has given first, then Spansh's commodity list
  (the copy the Sell / Buy lookup keeps, fetched by Recount itself when there is none yet), stored with Spansh's
  spelling under the journal's id: its letters, or for the hundred-odd whose letters are not the id
  (`outrider.cargo.SPANSH_IDS`, from EDCD's commodity tables: Occupied Escape Pod is `occupiedcryopod`, Agri-Medicines
  `agriculturalmedicines`, Void Opal `opal`...) the table's. Anything else is refused with up to three close names: a
  typo used to make a line of its own that no journal event would ever move. With no copy of Spansh's list and no
  network only your journal's names are known. A commodity added to the game after the table, whose letters are not
  its id, would still make a second line once the journal names it (Recount 0 removes it): add it to the table.
- **Market.json is read only when it changes and only kept for your own carrier;** a market opened while Outrider
  was not running is gone (the game overwrites the file at the next market), so the next one confirms instead.
- **Trade prices are what players last reported** (Spansh, via EDDN): a stop's price or demand can have moved on, and
  a route from a station Spansh does not know fails with Spansh's own words.
- **The Highway's ship list is as of each ship's latest Loadout;** an `EngineerCraft` after it is not applied, and a
  ship never flown (no Loadout) can only be plotted with the neutron plotter and a typed range.
- **The in-game overlay's reach:** on Linux under X11 its transparency needs a compositor (a bare window manager shows
  black around the panels); on Wayland it runs through XWayland, tried on GNOME, not with Proton's native Wayland mode
  (`PROTON_ENABLE_WAYLAND=1`: Elite becomes a Wayland window the overlay cannot find); fractional display scaling is
  untried; KDE on Wayland was confirmed by a player (2026-10-16), and Windows by players over the game (2026-10-15).
  Native Wayland compositors, gamescope and exclusive fullscreen are out of scope.
- **No page open, no alerts on the overlay:** the Alerts panel shows what an open Outrider page (a browser window or
  the tablet) posts, so with none open anywhere the panel stays empty (see the decision above).

## Not yet tried in a live game

These were built and tested with synthetic events, recorded files, fakes or headless browsers, but not
confirmed while playing. Treat reports about them as likely real.

- Ring mining: a stint on a live drop with its hotspot from Status.json's Destination, the
  prospector call-out, the ⛏ line and its warnings' timing (limpets low, hold nearly full, hold full with where to
  sell, its wider search out in the black), the limpet reminder (fixed twice: limpets bought, a collector alone).
- The sample spacing while flying the ship low over the body (discussion #3, 2026-10-23): from the point under the
  ship, with Status.json's live Latitude/Longitude in flight; tested on made-up Status.json only.


- `CarrierBuy`, `CarrierDecommission` and `CarrierCancelDecommission`: written to Frontier's journal manual, never seen
  in the author's journals (the carrier was bought before them).
- Status.json Flags2 on-foot-in-station bits (3, 13, 14) counting as docked.
- Surface pins' guidance from orbital cruise down and their arrival distances; carrier trips' following (the leg on
  the booked jump's departure, the cooldown estimate); chat read aloud from real squadron traffic (the pace, mentions).
- Space chatter's places and blockers (`outrider.chatter.where`): the on-foot-on-planet and SRV bits, GuiFocus
  values and the suit warnings, from Frontier's journal manual only.
- Auto honk end to end since it reads the binding from the controls preset; the fire-group and combat-mode waits.
- The co-pilot button on a real device (`python3 -m outrider.button --listen`), including rig marking in a live Rhino,
  and its tap targeting the next route system in a live game (the slow double tap's cancel included).
- The Nearest finder's Plot here and the "nearest station" voice answer from the app in a live session (checked against
  live Spansh and DSSA data on a scratch server only); its material traders (S54) and "nearest raw material trader"
  against a trader the game shows (built on Spansh's recorded answers only).
- The voice's S14 questions ("FSD injections", "how far today", "this body", "left behind") and a timed hush (S32) from
  the app in a live session: Status.json's body zone and a targeted body read for "this body", and the speech-to-text's
  wording of times ("10 minutes", "ten minutes") checked against fixed phrases only.
- Rig leash warnings, rigs lost on SRVDestroyed, death or relog, the rigs-still-out warning's timing, and
  `Destination.Body` for a mining location (assumed to be the planet).
- The rig restock recipe (3 Iron, 2 Nickel, 1 Mechanical Equipment), taken from a community guide.
- Playing lines and sounds on the PC (pw-play, paplay, aplay, ffplay) with real audio.
- Piper in the browser and the one-speaker logic across real windows (headless Chromium only).
- Many spoken call-outs (FSS debrief, leaving a body, approach, welcome back, ship-loss debrief, session recap).
- The fuel model against a live Status.json and a laden ship; EngineerCraft at a real engineer.
- Colour-variant prediction against a fresh in-game codex entry (backtested only).
- The firsts watch's rotation against live Spansh, and its first-sighting card and line (S6) on a real sighting; an OBS source on `/api/status` after the guard change.
- `--restore` and `--list-backups` against a real database (temp files only); the Backups list's restore command run
  as given, for Docker (stop, a one-off `run --rm`, up) and Windows (the .bat); the database's lock on a Docker bind
  mount and on Windows; the backup before a re-read on a real update.
- Settings' Restart (S10) in Docker (exit 75 and compose's restart policy), under `launch_outrider.bat` on Windows (its
  loop on 75 checked under Wine only) and under the systemd service (S70: the unit checked with `systemd-analyze
  verify` only; never installed, started or logged into from a test; the Windows Startup entry not tried);
  the starting page (S9) through a real re-read of years of journals, in the Android app and behind Docker's health
  check (tested on the sample journals and with a slowed import); the launcher and plain `python ed_outrider.py` were restarted
  on a scratch server (the same PID, a new run). Auto honk's readiness (S69) on a PC where `/dev/uinput` is missing or
  not writable.
- The Highway's plots against live Spansh (both plotters send the requests Spansh's site and Auto_Neutron send;
  tested with a mocked Spansh), following a route in game, and whether a name copied by `wl-copy`/`xclip` pastes
  into the galaxy map under Proton. The too-heavy warning, the short-of-the-refuel-stop warning (S1), the last-scoopable-star
  warning (S2, on the game's route and the Highway), the wrong-target check (S11: Status.json's Destination and
  NavRoute.json as the game writes them when a route is plotted, retargeted from the navigation panel, or reached) and a
  conservative plot against a real route.
- Auto-target in game: the first default sequence targeted a system end to end with "test now" (2026-10-02); a camera
  yaw before the search and a zoom in the plot step worked on 2026-10-03, and the current submit (the down arrow and
  UI_Select) on 2026-10-23, against Sol (several results) and a neighbour (one), with ▶ test now (the author's bindings,
  Linux/Proton). Not yet tried: a run triggered by a real supercharge on a route (Kurbo26 saw the game's plot add a
  stop on the way; his Route Settings: Fastest Routes, Jet-Cone Boost), Target next and Retry from the page, other keyboard layouts and presets, and both entry modes side by side; 🎯 on a
  bookmark, the next stop, a Nearest row, a checklist find and a Map click (S31, S72), and the co-pilot button falling
  back to the next stop.
- The voice plotting a far "nearest ..." (D4): a neutron route to the place's system, tested with the plot faked.
- Search and the Nearest finder around your destination (S49) with a target set in a live game, and the Map's route
  (S50) against a real NavRoute.json and a long Highway route (tested on made-up routes and stubbed answers).
- Earth-like and ammonia world routes (S52) and a sweep (S51) flown in game: the plots were probed against Spansh
  (2026-10-13, the answers in tests/fixtures), the following tested on them and on made-up routes; a sweep through more
  than a handful of systems, and Spansh's answer when more than one is unknown, only as probed.
- The EDSM and Inara key Checks (S45): built from the APIs' documentation with their documented example answers
  (`tests/fixtures/account_checks.json`), never sent with a real key: get-credits' 203 for a wrong name or key, the
  fields of getCommanderProfile's answer (its `inaraURL`), and whether a read counts against Inara's limit are still to
  be seen live. Also whether EDSM's account APIs take the key in a POST body as they do in a GET query.
- The EDSM flight log backfill (S47): built from EDSM's API documentation, tested with fakes only. Not yet seen live:
  get-position's and get-logs' real answers (their window limit and date format), and above all whether EDSM inserts
  back-dated events or answers 102 "older than stored" (and whether 101/103 dedupe); to be tried on a range of a jump or
  two, after a Preview, with the author's OK.
- The EDSM flight log import (S67): tested with fakes in get-logs' documented shape only. Not yet seen live: get-logs'
  real answer for old weeks (whether `showId`/`showCoordinates` give every entry its id64 and position, which would make
  the lookups by name unnecessary), its rate limit over some 200-600 weeks, and an import of the author's own log.
- EDDN: ApproachSettlement, CarrierJump and FCMaterials messages have not been seen live on EDDN's relay yet, nor a
  planetary station's Docked with its Body.
- The in-game overlay's real panels in live play, Arrange mode
  over the game, PyQt6 installed by the launcher and by Outrider, and the window's restart after a crash (on Windows the
  overlay itself is confirmed by two players, 2026-10-15). The overlay pill's states over a real game (and whether, under Proton and XWayland, the active window's id
  matches wmctrl's: a mismatch would show as "not the active window" while playing), DisplaySettings.xml's
  `<FullScreen>` values, and "keep showing" with a window over the game (X11 stacking, and Windows' z-order walk).
  The Alerts panel over a real game (its timing beside the voice, and how much a busy arrival puts on it).
  The overlay's sizes on real screens: the Size % cells' "≈ 11 px text" / "held at 9 px" figures and the 9 px floor
  against a real 1080p and 4K game window (tested on rendered frames and a faked window height), and Ctrl + wheel in
  Arrange mode over the game.
- The jump line's wait for Status.json's FsdJump flag (bit 30) in a live jump; your own sound files and Volume
  through the real players; the co-pilot button choosing the throttle of a real two-part X-56.
- The CMDR tab's **EDSY ↗ / Coriolis ↗** links opened in those sites with real builds (the tests decode the links back
  to EDMC's shape only), and in the Android app's hand-over to the browser. Its **hot ⚖** on a wanted ship or module:
  no real journal had a hot ship or a Loadout with `Hot` (Frontier's manual only). The **stored-module fold** between
  Outfitting lists: ModuleSellRemote and MassModuleStore had no real line, and FetchRemoteModule's arrival time is
  taken from its `TransferTime` without a live transfer watched.
- Nearby's **Around** (S49's choice on Nearby, "Lock System") while flying: a locked, destination, carrier or next-stop
  centre against live Spansh, ↻'s pace, the strip and the From you / Jumps columns on the tablet (tested with stubbed
  Spansh answers).
- **certifi on Windows** (issue #9): the fix on a PC that had the error (none was tried), and the .bat's weekly certifi
  check on a real Windows (its lines checked as text, its Python run on Linux); Docker's `CERTIFI_CHECKED` rebuild
  only through `scripts/docker_bundle.sh`.
- The CMDR tab's **Earnings** while playing: a sale made with the tab open (asked again when History's data moves), the
  mined stock through a live mining run (ship and SRV refinery, a transfer to the carrier, a sale), and its ⬇ CSV saved
  from the Android app. Checked on a copy of the author's database rebuilt from his journals (2026-10-14): the
  cartography and exobiology totals equal History's Ledger and the raw sales, mining equals the Sessions' Sold, and
  the species add up to exobiology; the crew's share seen in the journals only. The author looked through it in game
  on his real data (2026-10-15): fine.
- The In-Game Route's **hop lookups**: Spansh's search by id64 was probed (2026-10-14, `tests/fixtures/spansh_ids.json`),
  but not a real plotted route's ✦ chips out in the black, nor the bubble and Colonia skip (`ROUTE_LOOKUP_SKIP`) on a
  route crossing its edge.
