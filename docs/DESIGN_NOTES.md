# Design notes: deliberate decisions and known limits

Each line is a choice the project made on purpose, or a limit it knows about, with the reason. Don't
"fix" these as bugs without reading the reason. A fork is free to decide differently: these are the
upstream project's choices, not rules of the game.

## Deliberate decisions

- **No keyboard shortcuts.** A deliberate upstream choice, declined more than once; clickable things are reachable with
  Tab and act on Enter/Space instead.
- **No VoiceAttack integration.** Not used upstream; the co-pilot button and the page cover the same ground.
- **Nothing is uploaded unless the player switches it on.** EDDN and EDSM (Settings → Uploads, off by default) are the
  only uploads. Every other outside call is a read-only lookup: Spansh, EDSM, GitHub (the bio rules, ExploData's colour
  tables and the update check), Hugging Face for voices, Canonn (its codex reference once a day; the page loads the
  checklists' pictures from Canonn's storage), EDAstro for the DSSA carrier list when the Nearest finder opens. The
  one exception is the AI layer (off by default, `[assistant]`): it sends the question and the read-only tools'
  answers to the endpoint the player configures, so it is not a read-only lookup. This is the one full list.
- **EDSM has no test endpoint**, so its developer switch is a dry run (`OUTRIDER_EDSM_DRYRUN=1`: requests built and
  logged to `data/edsm-dryrun.jsonl` without the key, nothing sent; the rows end as `dry` and are never sent later).
  EDDN's is its `/test` schemas (`OUTRIDER_EDDN_TEST=1`). Neither is a setting.
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
  none), a double tap is the status report, a hold the hush; out of the ship a tap does nothing; the Rhino keeps rig
  marking. "Say again" left the button (the page keeps it). A tap is only known once `double_ms` (400 ms, was 350)
  passes, then 0.5 s more before any key; a press in that half second cancels the run and counts as the slow double
  tap it was (the status report), so a slow double tap never opens the galaxy map.
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
  and it can be switched off.
- **The suggested order is not a route planner:** a fixed supercruise time curve; its first stop is said ("Next: …") only
  in the mapped call-out and the status report.
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
- **Auto-target presses keys in the galaxy map** (opt-in, Linux, Windows experimental since 2026-10-05; decided with the author 2026-10-01): open the map,
  the search box (UI_Up highlights "Search the Galaxy", UI_Select puts the cursor in it; found in game 2026-10-02 — UI_Right, Auto_Neutron's older step, moves along the tab column to Trade Routes, and UI_Select alone opens the current system; `autotarget_search` changes it), type the name (US keymap; a name it cannot type is pasted when a
  clipboard tool exists), Enter twice after short waits (the search lists its suggestion a moment after the name goes in, and an Enter before that selects nothing; found in game 2026-10-02; `autotarget_submit`), the plot-route step (configurable: the map's focus after a search varies), close the
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
- **ExploData's colour tables are downloaded, never shipped** (the author, 2026-10-10). EDMC-ExploData's repository
  carries the GPL v2 text without "or later", so its tables are kept out of the repository and the Docker image, and
  Outrider's own licence does not depend on them: `resources/bio_colours.json` is fetched on the first start (and refreshed with the
  rules) and merged in at load. A first start offline has no colour check, which costs nothing: the game cannot be
  played offline either. BioScan's rules (GPL v2 or later) and the region map (MIT) still ship. The colony distances
  are the game's (the Genetic Sampler shows them), kept in `outrider/bio.py`.
- **The in-game overlay is our own window** (the author, 2026-10-08 and 2026-10-10; the author's plan,
  project/PLAN-overlay-build-2026-10-10.md, is private and git-ignored).
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
  tried (X11, and XWayland on a Wayland session, as Modern Overlay runs on GNOME); Windows has the code, untried;
  native Wayland compositors, gamescope and exclusive fullscreen are out of scope.
- **The overlay uses the config's levels.** The panels are built on the server, which cannot see a browser's levels:
  the system panel `body_highlight_level` and `bio_min`; the body panel `high_gravity`; Now `body_highlight_level`,
  `bio_min`, `high_gravity`, `codex_interesting`, `unsold_warn` and `unsold_urgent`; Bio signals `bio_min`,
  `high_gravity` and `codex_interesting`. Now leaves out what only the page knows (the skip floor, the high-g approach
  stakes, captions).
- **The overlay copies some of the page's rules in Python:** Now's suggested order (`overlay.plan_items`; the page's
  `worthLeavingFor` + `planItems`), the supercruise time (`overlay.sc_seconds`, `SC_KNEE`; the page's `scSeconds`),
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
- **The panels hide over the maps, the FSS, the SAA and the codex, and in the hyperspace tunnel; the Now panel also
  while docked** (the author, 2026-10-10, for docked). GuiFocus 6-11 (`OVERLAY_HIDE_FOCUS`) and the FSD-jump flag hide
  every panel; the ship's docked flag, or on foot in a station, hangar or social space (`FLAG_DOCKED`,
  `ON_FOOT_DOCKED`), hides Now. The test panels and Arrange mode are the exception: they show over the game's window
  whatever is in front.
- **No rebuy multiple for a ship whose hull has no credit value** (the author, 2026-10-10). An Arx-bought ship's
  Loadout carries ModulesValue but no HullValue, and its rebuy is 5% of the modules alone, so "N× rebuy" said ~110
  on any trip and a rebuy-multiple level would always fire. Such a ship gets no rebuy in the risk figures (`risk_rebuy`,
  page.js `riskRebuy`); the credit levels still warn. A Loadout with neither value keeps the rebuy as before.
- **Here's icon legend lists only what is shown.** The footer under Here's list (`HERE_LEGEND` in page.js) names the
  icons the list or schematic shows now, not every icon there is (the author's call, 2026-10-10), and is absent when
  there are none; sticky to the bottom of the scrolling pane so it stays in view. The codex marks write the new
  colour after them ("✪ Cobalt"): their tooltip never shows under the body summary that pops up over a row.
- **Too much fuel for the next jump.** Spansh's exact plotter simulates the fuel, so a long neutron jump may be in
  range only with about the fuel it expects aboard (the Caspian's 487.9 ly ×6 jump: at most about 36 t; a full 160 t
  tank gives 75.3 × 6 = 452 ly). Checked on a live arrival in a route system (or a plot made where you are) and again
  as Status.json's fuel changes there (every 3 s at most), against the fuel actually aboard (the main tank, with the
  reservoir and cargo counted as mass), the current ship's fuel model and its supercharge in a neutron route system.
  The most fuel that still reaches the jump is found by bisection on `fsd_range` past one max jump's fuel (below that
  the fuel itself limits the jump). Warned past that by more than 0.5 t (Spansh plans at the limit), said once per
  system, cleared when the fuel drops or you leave. Only for the ship the route was plotted for; the neutron plotter
  only when the next waypoint is one jump away (the first jump of several has no known length).
- **Conservative range** shortens the plan, not the ship: the neutron plotter gets the range less the margin, the
  exact plotter a smaller optimal mass, scaled so the normal full-tank range is the margin shorter (the range less the
  booster's ly goes as the optimal mass at every mass, so Spansh's fuel simulation stays consistent; the booster is
  untouched). Neither cuts the drive's own range by more than half. The margin is recorded in the route's options.
- **The Highway's spoken lines are plain text** carried by the moment, not `speech.json` keys yet (personality later).
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
- **EDDN station data goes once per visit**, not once per change: the sites date a station's data by what arrives, so
  each docking sends it again; only the same screen reopened in one docking is skipped (`VISIT_ENDS`).
- **EDDN sends what EDMC, EDDiscovery and EDDLite send, field for field** (compared on EDDN's relay, the author,
  2026-10-10). A Docked at a station on a planet's surface gets `Body` and `BodyType` "Planet" from the body you
  approached (`eddn.PLANETARY_STATIONS`), as EDMC adds them. shipyard/2 leaves out `allowCobraMkIV`: it describes the
  commander, not the station, and the other three leave it out. commodity/3's optional `statusFlags` is not sent (the
  author's call, 2026-10-10: not needed). outfitting/3 is not used (the author's call: the three main apps send
  outfitting/2).
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
  populated system paid it, 208 of 208 elsewhere (`project/value-checks/RESULTS-2026-10-08.md`). A system's
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
- **Two status reports** (review S23, done): Vespa's "status report" is composed on the server (`outrider/ask.py`:
  the system, fuel, unsold, the Highway's next stop); the co-pilot button's double tap and the Now bar ask the window
  that speaks for the page's, which depends on each browser's thresholds and plan logic.
- **Header tiles: tooltips on cut lines, no wrapping yet** (review S17): wrapping or click-to-expand would change the
  header's height and the app layout; left for the author. The tiles' fold has a per-device mode (S44): auto (a
  small window), six, line, or none, which follows the shared `tilesCollapsed` that ▴/▾ sets; ▴/▾ also makes its
  choice this device's.
- **The link pill's "stale" is the long poll's limit, not quiet** (review S41): the server answers within 25 s even
  with nothing new, so "stale" starts at 30 s without an answer; the desktop's "linked · N s" counts up to that in
  quiet play. The tablet's pill says just "linked" (the ticking seconds distracted the author; 2026-10-04) and shows
  the age only once stale. A long poll with no answer by `POLL_TIMEOUT_MS` (40 s) is aborted: a hung link (the PC
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
  1 to 2 t low), jump by jump at 500 ly with the hold topping the depot up.
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

## Known limits

- **New versions: a notice, never an update** (`[server] update_check`, on by default). GitHub's latest release at
  start (after a minute) and daily; a newer one is a quiet pill in the theme's accent, not an alert or a spoken
  line, with the steps for this install (Docker, a git clone, a download). No self-update: a container cannot
  replace its own image, a download cannot safely replace its own files, and a clone's pull and restart was left
  until someone wants it. Watchtower, the usual Docker auto-updater, is archived (2025), so the README names none.
- **Key presses on Windows are a stand-in for evdev** (`outrider/winkeys.py`): the same evdev key names mapped to
  scan codes and sent with `SendInput` (scan-code mode, extended flag for arrows, right Ctrl, numpad Enter...), so
  auto honk, auto-target and the rail run unchanged above it. Chosen by platform at start (`honk.keyboard_backend`).
  Experimental: checked under Wine (a low-level hook saw the right scan codes and flags; Wine reports right Ctrl's
  virtual key as left Ctrl, the scan code and flag being right), never yet against the game on Windows. Windows
  drops keys sent to an elevated window, without an error. The co-pilot button (reading a HOTAS) is still Linux
  only: Windows' simple joystick API stops at 32 buttons.
- **Windows runs the rest** (`launch_outrider.bat`): journals found in the Windows save folder, every file read and
  written as UTF-8, no SIGTERM handler there (Ctrl-C). Less tested than Linux: under Wine, not a real Windows.
- **Core module health is as of the last Loadout or repair;** the journal logs nothing in between, so jet-cone
  boosts since are only counted.
- **Status.json does not update while you stand still,** so positions can be up to a reading old.
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
  or market was opened.
- **Market.json is read only when it changes and only kept for your own carrier;** a market opened while Outrider
  was not running is gone (the game overwrites the file at the next market), so the next one confirms instead.
- **Trade prices are what players last reported** (Spansh, via EDDN): a stop's price or demand can have moved on, and
  a route from a station Spansh does not know fails with Spansh's own words.
- **The Highway's ship list is as of each ship's latest Loadout;** an `EngineerCraft` after it is not applied, and a
  ship never flown (no Loadout) can only be plotted with the neutron plotter and a typed range.
- **The in-game overlay's reach:** on Linux under X11 its transparency needs a compositor (a bare window manager shows
  black around the panels); on Wayland it runs through XWayland, tried on GNOME, not with Proton's native Wayland mode
  (`PROTON_ENABLE_WAYLAND=1`: Elite becomes a Wayland window the overlay cannot find); fractional display scaling is
  untried; Windows has the code, untried against the game. Native Wayland compositors, gamescope and exclusive
  fullscreen are out of scope.

## Not yet tried in a live game

These were built and tested with synthetic events, recorded files, fakes or headless browsers, but not
confirmed while playing. Treat reports about them as likely real.

- `CarrierBuy`, `CarrierDecommission` and `CarrierCancelDecommission`: written to Frontier's journal manual, never seen
  in the author's journals (the carrier was bought before them).
- Status.json Flags2 on-foot-in-station bits (3, 13, 14) counting as docked.
- Auto honk end to end since it reads the binding from the controls preset; the fire-group and combat-mode waits.
- The co-pilot button on a real device (`python3 -m outrider.button --listen`), including rig marking in a live Rhino,
  and its tap targeting the next route system in a live game (the slow double tap's cancel included).
- The Nearest finder's Plot here and the "nearest station" voice answer from the app in a live session (checked against
  live Spansh and DSSA data on a scratch server only).
- Rig leash warnings, rigs lost on SRVDestroyed, death or relog, the rigs-still-out warning's timing, and
  `Destination.Body` for a mining location (assumed to be the planet).
- The rig restock recipe (3 Iron, 2 Nickel, 1 Mechanical Equipment), taken from a community guide.
- Playing lines and sounds on the PC (pw-play, paplay, aplay, ffplay) with real audio.
- Piper in the browser and the one-speaker logic across real windows (headless Chromium only).
- Many spoken call-outs (FSS debrief, leaving a body, approach, welcome back, ship-loss debrief, session recap).
- The fuel model against a live Status.json and a laden ship; EngineerCraft at a real engineer.
- Colour-variant prediction against a fresh in-game codex entry (backtested only).
- The firsts watch's rotation against live Spansh; an OBS source on `/api/status` after the guard change.
- `--restore` and `--list-backups` against a real database (temp files only).
- The Highway's plots against live Spansh (both plotters send the requests Spansh's site and Auto_Neutron send;
  tested with a mocked Spansh), following a route in game, and whether a name copied by `wl-copy`/`xclip` pastes
  into the galaxy map under Proton. The too-heavy warning and a conservative plot against a real route.
- Auto-target in game: the first default sequence targeted a system end to end with "test now" (2026-10-02), and the
  current one (a camera yaw before the search, 1.5 s before Enter, a zoom in the plot step) is what worked on
  2026-10-03 (the author's bindings, Linux/Proton). Not yet tried: a run triggered by a real supercharge on a route,
  Target next and Retry from the page, other keyboard layouts and presets, and both entry modes side by side.
- EDDN: ApproachSettlement, CarrierJump and FCMaterials messages have not been seen live on EDDN's relay yet, nor a
  planetary station's Docked with its Body.
- The in-game overlay's real panels in live play (only the test panels have been seen over the game), Arrange mode
  over the game, PyQt6 installed by the launcher and by Outrider, the window's restart after a crash, and the overlay
  on Windows.
- The jump line's wait for Status.json's FsdJump flag (bit 30) in a live jump; your own sound files and Volume
  through the real players; the co-pilot button choosing the throttle of a real two-part X-56.
