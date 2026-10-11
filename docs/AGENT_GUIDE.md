# Working on ED Outrider (for contributors and their coding agents)

Read this before changing anything. It covers the code map, how data moves, how to test safely, and the
rules that keep the journal data, the page and the voice consistent. See also `JOURNAL_REFERENCE.md`
(what the game writes and its traps), `DESIGN_NOTES.md` (decisions and known limits) and `CHANGELOG.md`.

## What it is

- A local web app for Elite Dangerous explorers. It reads the player's own journal files as they are written,
  keeps what it learns in SQLite, asks Spansh (and EDSM as a fallback) about nearby systems, and serves one
  page on `http://127.0.0.1:8025/` that updates live, with sounds and optional spoken alerts. The same page in a
  touch layout at `/tablet` (wrapped by the separate ED Outrider for Android app), questions by voice
  (`/api/ask`), read-only tools for AI clients (MCP), and a server mode for Docker with the game-PC parts off.
- Python 3.11+, aiohttp, no framework. The page is plain HTML/CSS/JS, no build step. Linux first; Windows runs
  everything but the co-pilot button (`launch_outrider.bat`), less tested; its key presses are experimental.
- Optional parts: Piper voices (`piper-tts`), and on Linux auto honk, auto-target, the control rail and the co-pilot
  button (`evdev`); on Windows the first three through `outrider/winkeys.py` (experimental, no dependency).
- Licence GPL-3.0-or-later (GPL-2.0-or-later until the overlay brought in EDMC Modern Overlay's GPL-3 window code:
  `outrider/overlay_tracking.py`, parts of `outrider/overlay_window.py`, each with its notice). Bundled data keeps its
  own licence (see the README footer).

## Code map

| File | What it holds |
|---|---|
| `outrider/__init__.py` | `ROOT` (the repository), `RESOURCES_DIR` (`resources/`), `DATA_DIR` (`data/`): every default path starts from these. Modules with a CLI run as `python3 -m outrider.<name>` from the repository root |
| `ed_outrider.py` | Almost everything: config (`settings_from`, `config_text`), the schema (`SCHEMA`, `RESET_JOURNAL_DATA`, `open_db`), the journal reader (`class Journals`), Spansh/EDSM (`class Spansh`), the live state and every summary the page shows (`class State`), Search (`class Searcher`), backups, the web app (`make_app`, `request_guard`) and `run()`/`main()`. The Neutron Highway's state and orchestration (its maths and route helpers are in `outrider/fsd.py` and `outrider/highway.py`, imported here): `Spansh.plot`, `State.highway_id64` (the exact plotter takes id64s, not names: where you are, `find_local`, else `Spansh.system_id64`, Spansh's name search), `Journals.note_fleet`/`highway_arrival` (fleet rows, progress and detours), `State.highway_*` (summary, view, plot, store, clear, copy, background, `highway_heavy_check`: too much fuel for the next jump) and auto-target (`maybe_autotarget` the trigger, `_autotarget` the delay / honk-first wait / run on a worker thread, `start_autotarget_test` with `autotarget_test_target` (the nearest known system a plain jump away, no route needed), `start_autotarget_run(kind, countdown)` (a run the page asks for: "test", or "next" for Target next / Retry against `autotarget_target(manual=True)`, the next route system or off the route the closest one), `cancel_autotarget(route)` (the toggle off, a cleared or replaced route), `set_autotarget`, `autotarget_info`). Vehicles: `read_status` keeps the ship's fuel and cargo while you are in the SRV, the Nomad or a fighter (Status.json reports the vehicle's) and `fuel_summary` adds `vehicle` {label, fuel} |
| `outrider/core.py` | Small shared helpers with no dependencies: `iso_ts`, `ts_seconds` (journal timestamps) |
| `outrider/fsd.py` | The frame shift drive's maths, pure: the drive tables (`FSD_DATA`, `FSD_POWER`, `GUARDIAN_BOOST`...), `fsd_range`, `hop_fuel`, the fuel model fitted to your jumps (`fuel_model`, `jumps_left`), a fleet ship's plotter inputs (`fleet_figures`/`fleet_range`/`fleet_model`), `max_fuel_for_jump`/`jump_in_reach`, `conservative_range`/`conservative_optimal_mass` |
| `outrider/highway.py` | The Highway's route helpers: `highway_rows` (Spansh's answer as rows), `stand_in`/`splice_route` (an end Spansh does not know yet: plotted
from a Spansh system near it, nearest the other end within the ship's reach, the real end put back as a leg of its own;
`State.highway_ends` looks both ends up with `Spansh.system_record`, `highway_stand_in` picks from the neighbourhood's
Spansh systems, else a sphere search around it), `highway_match`, `highway_refuel_in`, `highway_text` (the spoken line), `highway_bg_file`, `HighwayError`, `class Clipboard` (wl-copy/xclip; `winkeys.set_clipboard` on Windows). The route's state and auto-target stay in `ed_outrider.State` (their constants are patched by verify.sh and the tests on `ed_outrider`, the Spansh URLs among them) |
| `outrider/riches.py` | The survey routes, Road to Riches (thshurka's PR #1) and Exomastery, pure: `riches_rows` (Spansh's answer as rows, both kinds; the body's `body_id` is its id64's top 9 bits, the game's BodyID; an Exomastery body's `species` from its `landmarks`), `exo_todo`/`exo_left`/`exo_text` (species sampled by BodyID and name from `own_organic`), `riches_match`, `todo` (what is left, from the journal's `own_bodies`/`own_mapped` by name), `riches_text`. The route's state, `riches_route`/`riches_bodies`/`riches_species`/`trade_stops` and meta `riches` (live-only; `kind` "riches" | "exo" | "trade": one slot, a trade route's stops in `trade_stops` and what you did there in meta `riches` "trade"), the plot, `riches_arrival`/`riches_progress` and `route_newest` (with a Highway route too, only the newer copies to the clipboard) are in `ed_outrider.py`; `scripts/riches_probe.py` re-checks Spansh's undocumented API (checked 2026-10-06; `tests/fixtures/spansh_riches.json` is a real answer) |
| `outrider/cargo.py` | Cargo, pure: `cid` (the journal's commodity ids), `learn`/`display` (names), `ship_apply`/`ship_snapshot` (the ship's hold with average cost: `avg`, `priced`, `lots`, `avg_text`), `carrier_fold` (your carrier's hold from its history in time order: `cargo_events`, the `carrier_markets` snapshots, your `carrier_counts`; the rules in its docstring), `carrier_total`/`carrier_reported`, `carrier_burn`/`carrier_jumps` (the carrier's fuel, checked against real jumps), `SHIP_PAD`, the Sell / Buy lookup (`market_query`, `market_rows`, `STATION_TYPES` without fleet carriers) and trade routes (`TRADE`, `trade_rows`, `trade_left` (by tonnes: `trade_counts`, an old record's list of names read as traded in full), `trade_short`,
`trade_text`, `trade_done_text`). `Journals.trade_progress` counts each journal line once (`lines`, by `line_source`);
`trade_left_stop` (Undocked) marks a part-traded stop `left`; `trade_stop_done` says it. In `ed_outrider.py`: `Journals.handle_cargo` (stores the carrier's events, folds the ship's), `read_cargo_file`/`read_market` (the live files, by mtime in `tick`), `trade_progress`; `State.carrier_cargo` (the fold, cached on `cargo_version`/`counts_version`), `cargo_summary`, `carrier_tritium`, `cargo_recount`, `cargo_lookup`, `commodity_list` (Spansh's names, a week), `trade_start_plot`/`trade_defaults`. The carrier itself (meta `carrier`, `Journals.handle_ship`): `CarrierBuy` or a `CarrierStats` of another id starts it afresh; `CarrierDecommission` / `CarrierCancelDecommission` set or clear `decommission`, which `State.carrier_decommission` turns into the tile's red line (done once `ScrapTime` has passed: the scrapping writes nothing); the payload's `carrier.carrier_id` tells the page it is another carrier (no "arrived"). No carrier at all: the page hides the tile (`#tCarrier`, `.tiles.nocarrier`) |
| `outrider/dock.py` | The nearest place to dock, pure: `dssa_rows` (EDAstro's DSSA-carriers.json; its services are split words), `spansh_rows` (the station search's stations and carriers), `own_row` (your carrier, its services from its last Docked), `merge` (by callsign: the DSSA badge, the fresher place), `nearest` (the filters and the counts they hid; docking other than "All" a warning, `ACCESS`), `spoken` (the voice's answer). In `ed_outrider.py`: `Spansh.dock_search`, `permit_ids` (Spansh's system records), `get_if_changed` (a conditional GET); `State.dssa_list` (meta `dssa`, live-only: fetched at most hourly, `DSSA_URL`), `State.nearest_dock` and GET `/api/nearest` (`cached=1`: never fetches the DSSA list, which the AI's `nearest_dock` tool and the voice's "nearest station"... always use) |
| `outrider/uploads.py` | Uploads' foundation (EDDN, EDSM; opt-in, off by default; user guide docs/guide/uploads.md): `Session` (the line's game session: each file's gameversion/build from its Fileheader, a continuation file's (`continued`, part 2+) carrying the session on, the commander, Horizons/Odyssey from LoadGame only, the place triple from Location/FSDJump/CarrierJump only, crew, body, docked market, ship, `pending` (EDDN's waits), `source`/`now` (set by the hub); `blocked()`: beta, legacy, crew, version, commander), `live_line` (the age gate), journal names in time order (`name_key`, `pos_key`: the old Journal.YYMMDDhhmmss form mapped; every comparison of marks and every sort of files), `UploadHub` (every live-folder line before the WANTED filter, via `Journals.scan_dir(upload="catchup"|"live")` while `active()`; `prime` reads a file met part way through, and the file a continuation goes on from (`continued_from`); `forget` when no service wants lines; per-service hooks: `builders`, `holds` (EDSM's batches; `deadline`/`release`), `max_ages` (EDDN's hour), `idlers` (`idle()` on the tick), `quiet` (lines a service does not build), `follow` (a wanted service another uploader has: its mark moves, nothing queued); marks `[file, offset, ts]` per service, `catch_up`, whose `_catch_up_tail` runs the idle step at its end and hands a batch of signals not yet located to the live session), the outbox (`upload_queue`, live-only: `enqueue` in the tick's transaction, `due`, `settle`, `prune`, `counts`), `upload_settings`, `upload_loop` (a raised send or a retry answer pauses the whole queue by `BACKOFF_S`; sqlite errors do not end it), the leases (`write_lease`, `Leases`: `.outrider/uploads-<id>.json` in each live journal folder, judged by the reader's own clock, one first seen untouched for `LEASE_ABANDONED_S` stale at once; `lease_marks`; `lease_owners`: who sends each service when several want it, the one already sending, else the lowest
instance id, and a legacy lease (no `wanted`) always given way to; a lease's `services` is what it sends, `wanted` what
it is switched on for) and `edmc_uploads` (EDMC's config.toml on this PC). In `ed_outrider.py`: `State.upload_wanted` (the switch) / `upload_queueing` (wanted and no other uploader: a held service still queues) / `upload_on` (sending: not held either) / `upload_conflict` / `check_upload_start`, `set_upload` (the page's switch: `upload_cfg` at once, `[eddn]`/`[edsm] enabled` written with `config_save(hidden=True)`; those sections are `config_edit.HIDDEN_SECTIONS`, left out of the Server settings and refused by `POST /api/config`), `upload_start_mark`, `catch_up_uploads` (skips a service another uploader has), `refresh_leases(edmc)` (sets `lease_hold`: service -> the host given way to)/`watch_leases` (finds EDMC on a worker thread; also prunes hourly)/`drop_leases` (marks of wanted services only), the instance id (meta `instance_id` tied to `instance_where`: host, db file and inode; a new id removes this host's old leases), `forget_upload_position` (a restored database starts from now), `edsm_accounts` (never served); `POST /api/uploads`, `POST /api/uploads/edsm`; the payload's `uploads`. Tests: `support.py` blanks `LIVE_DIRS`, points `CONFIG_PATH` at a throwaway file and stubs `edmc_uploads`, so nothing touches the player's folders |
| `outrider/eddn.py` | EDDN's messages, pure: `build(ev, session, version, test)` -> [(schema, envelope)]; `envelope` (header: uploaderID = the session's commander, softwareName "ED Outrider", the file's gameversion/gamebuild; horizons/odyssey only when LoadGame said them), `unlocalised`, `journal_message` (journal/1: `JOURNAL_DROP`, `FACTION_DROP`, StarSystem/StarPos only after the SystemAddress cross-check), the FSS family, codex, settlement, `organic_message` (scanorganic/1, from EDDN's develop branch: Log and Sample only, Body renamed BodyID, BodyName when the approached body has that id, Latitude/Longitude from `Session.status_pos` within `ORGANIC_SYNC_S` of the scan), `navroute_message` and the station files (commodity/3 with `_bracket` keeping "", outfitting/2, shipyard/2, fcmaterials_journal/1; `_station_message`, sent once per visit: `_changed`, reset by `VISIT_ENDS`) behind waits on companion files (`_wait_start`/`_wait_check`: the file's time and MarketID; tried by later lines and by the server's tick through `idle()`, given up after `NAVROUTE_TRIES` lines or `FILE_WAIT_S`), signals batched (`signals_message`; `idle()` sends a batch `SIGNAL_QUIET_S` after its last line when you are in that system, drops one older than `SIGNAL_MAX_S`), `quiet` (lines EDDN does not build: its waits dropped), `CATCHUP_MAX_S` (an hour: catch-up and send), docking. EDDN's test schemas only under the developer's `OUTRIDER_EDDN_TEST=1` (`uploads.eddn_test_mode`; deliberately not a setting). `outcome(status)` (200 sent; 400/413/426 dropped, never retried; else again after a minute), `SchemaHold` (three refusals of a schema in an hour, or one 426: held until a restart). The server's `State.eddn_build`/`eddn_idle`/`eddn_send` (one gzip message per POST, rows over `CATCHUP_MAX_S` old dropped, `UPLOAD_URL` offline in verify.sh). Tests validate every message against `tests/fixtures/eddn` (EDDN's own schemas, BSD; `jsonschema` in requirements-dev.txt) |
| `outrider/edsm.py` | EDSM's journal upload, pure: `build(ev, session, discard)` -> [(event, the event + EDSM's transient fields `_systemAddress` ... `_shipId` from the Session)], `DISCARD` (EDSM's list as served 2026-10-08; the server's `watch_edsm_discard` fetches the live one while EDSM is on, every 2 h), Cargo/ShipLocker/Backpack contents from their .json when the timestamps match, `hold` (events wait for a `RELEASE` event: jump, docking, Location, Shutdown, or `HOLD_S` after the first waiting one; the hub's `holds`, `uploads.deadline`/`release`), `same_batch` (one commander and game version per request, up to `BATCH`), `request`, `answer` (msgnum: 201-205/207 held, 206/208 dropped, per-event 3xx/4xx dropped, 500/501 kept). Server: `State.edsm_build`, `edsm_send` (the commander's account from meta `edsm_accounts`; none: dropped with the reason; HTTP not 200 raises), `edsm_dry_log`, `edsm_account_list` (the key's ends as `hint`, never the key). Developer switch `OUTRIDER_EDSM_DRYRUN=1` (`edsm.dry_run`): nothing sent, rows end `dry`, requests logged to data/edsm-dryrun.jsonl without the key. Offline in verify.sh |
| `outrider/unsold.py` | The unsold cartographic + exobiology estimate (its own journal pass, run in a thread); also journal-folder auto-detection. Works alone from the command line |
| `outrider/bio.py` | Exobiology predictor: spawn rules, colour variants, values; `--backtest`, `--update-rules`; `region_layer` (the region map for the Highway map: the run-length grid, names, label points) |
| `outrider/overlay.py` | The in-game overlay, Outrider's side, pure (project/PLAN-overlay-build-2026-10-10.md): panels as draw lists on a 1280x960 canvas (`text`, `rect`, `circle`, `line`, `marker` items in the panel's own coordinates; the module docstring has the format), `text_panel` (title, rule, rows of coloured segments with a right-aligned value; texts cut with … to the width: `fit`, `CHAR_W`), the panels' builders (`system_panel`, `body_panel`, `radar_panel`, `strip_panel`, `now_panel`, `bio_panel`; `now_panel`'s Next comes from `plan_items`/`plan_parts`, a Python copy of page.js's `worthLeavingFor` + `planItems` + `planText` with the config's levels: change both together), `test_panels`, `palette(theme)`, `[overlay]` settings (`overlay_settings`), the layout (`LAYOUT_DEFAULT`, `clean_layout`, `layout_update`: per panel a corner, an offset as a share of the game window, a scale, the background's and the panel's opacity; meta `overlay_layout`, live-only). Server: `State.overlay_view` (GET `/api/overlay?since=<version>`: `{same}` when unchanged), `overlay_set` (POST `/api/overlay`: the switches into `[overlay]`, test panels for `TEST_SECONDS`, Arrange mode for at most `ARRANGE_SECONDS`), `overlay_layout_set` (POST `/api/overlay/layout`), `overlay_info` (the payload's `overlay`: whether a window asked within `OVERLAY_SEEN_S`). The window that draws them runs on the game PC: `outrider/overlay_window.py` |
| `outrider/overlay_window.py` | The overlay's window, on the game PC (`python3 -m outrider.overlay_window`, PyQt6 from `requirements-overlay.txt`, never in Docker): `Client` (GET `/api/overlay`, POST the layout, to this PC's Outrider only: the overlay is a game-PC feature, POST routes `pc_only`), `Feed` (a thread asking once a second with `since`; Outrider gone: nothing stale stays drawn), `paint` (every panel per the layout: background at its opacity, items, the whole at its alpha; `runs` laid out with the font's real widths on one baseline), `render_png` (one frame into a picture: tests and `--render`), `run_window` (frameless, on top, translucent, click-through; follows Elite's window every `FOLLOW_MS`, hidden when the game is not in front; Wayland sessions run it through XWayland: `QT_QPA_PLATFORM=xcb`). Pure and tested without Qt: `panel_rect` / `place` (a panel's corner and offsets in window pixels and back: the nearest corner), `rgba`, `screen_for`, `config_url`; Arrange mode's `hit` (a panel and move or resize: its corner handle `HANDLE_PX`),
`dragged`, `wheeled`, `done_rect` (the window takes the mouse only while `arrange` is on; edits are drawn locally and
sent when the drag ends or the wheel stops, kept until Outrider's answer carries them). Page: Settings -> In-game overlay
(`overlayHtml`, `renderOverlay`, `overlayPost`). Its window flags and the Windows click-through call are adapted from EDMC Modern Overlay (GPL-3, notice in the docstring) |
| `outrider/overlay_runner.py` | Outrider runs the overlay window itself on the game PC: `OverlayRunner` (`tick(want)` starts `python -m outrider.overlay_window --url` this Outrider while `State.overlay_wanted()` (the overlay on, or test panels / Arrange mode; not when a window started by hand is drawing), stops it otherwise and at shutdown, restarts it after a crash with `BACKOFF_S`, gives up after `CRASHES_MAX`; `install()` pip-installs requirements-overlay.txt by itself, once per switching on, when the window is wanted and PyQt6 is missing: no button; `setup()` / `python -m outrider.overlay_runner --setup`, run by launch_outrider.sh/.bat before Outrider starts, does it when `[overlay] enabled` is true in the config). Never on a server, under --simulate or with `OUTRIDER_NO_OVERLAY_WINDOW` (verify.sh sets it); tests use a fake popen, pip and clock. The window forces XWayland (`QT_QPA_PLATFORM=xcb`) with `GDK_BACKEND=x11` on a Wayland session |
| `outrider/overlay_tracking.py` | Finding Elite's window, adapted from EDMC Modern Overlay (GPL-3; its notice and the changes in the docstring): `X11Tracker` (wmctrl -lGx, xprop's active window, xwininfo; an injectable `run` so tests need no X), `WindowsTracker` (Win32, untried against the game), `create_tracker`, `native_rect_to_qt` (a scaled desktop), `title_bar_offset` |
| `outrider/checklist.py` | The exobiology checklist, pure: `table(species, region, region_ok, runs, codex, region_count)` -> genus boxes of species rows (`possible` "yes"/"parts"/None from the rules: `possibility`, a species with no rules is "yes"; `state` sold > aboard > lost > logged; `variants` from the colour tables, `colours`, each with what gives it), and a summary; region None = All regions. `merge_species` merges the rules' duplicates by game id (BioScan's "Stratum Aranaemus"); runs match by species id. `outrider.bio.ruleset_region_ok` is the region test it shares with `region_allows`. Server: `State.checklist(region)` (every run with its Samples fate, every codex entry, placed by region; `region` here / all / 1-42), GET `/api/checklist?region=` (`kind=geo`: the geology checklist, `geo_table`/`geo_completion` over `resources/geo_codex.json` (built by `scripts/build_geo_codex.py` from Canonn), `State.checklist_geo` for its panel (both panels carry Canonn's picture links: `State.codex_images` via `outrider/codex_images.py`: the copy refreshed daily into data/ when sound, else the shipped resources/codex_images.json from `scripts/build_codex_images.py`; tests point `codex_images.CACHE` into a scratch folder; the page's `clFigure`); the page's third Bio/Geo mode "geo") (and `?species=<id>`: `State.checklist_species`, the regions it grows in and your runs' x, z for the panel's map). Page: the Bio/Geo tab's My Samples | Exo-Biology | Geology switch (`data-view="bio"`, labels only renamed from Samples / Runs / Checklist) (`setBioMode`, store "bioMode"; `#bioView.check` shows `.checkonly`, hides `.runonly`), `loadChecklist`/`renderChecklist`, the side panel `clDrawSide`, `clDrawMap` (the region grid `RG` as Plot Route's, lit regions in their tints) |
| `outrider/log.py` | The Log view: one-line summaries, read straight from the journal files on request |
| `outrider/materials.py` | Material names, grades, caps, synthesis recipes, and folding material events into an inventory |
| `outrider/speech.py` | Loads and checks `speech.json`; `KEYS` (every alert and its placeholders), `SAMPLES`, bans (`banned_path`: `data/speech_banned.json` for the shipped file, beside a copy of your own) |
| `outrider/tts.py` | Piper synthesis (`Speaker`; `body_letters` turns a body name's letters into Piper's raw phonemes, `LETTER_SOUNDS`, for an English voice: `_synth` and the voice lab), voice downloads (into `data/piper-voices/`), Piper's catalogue (`fetch_catalogue`, cached a week; `catalogue_summary` for GET `/api/voices/catalogue` and Settings → Voice → More voices; the voice lab reads the same copy), and playing lines/sounds on the PC (`LinePlayer`); `SoundBank` (the alert sounds, with your own `<name>.wav` from `[speech] sound_dir`, WAV only, up to `SOUND_FILE_MAX_S` 3 s), `scale_wav` (the page's per-device Volume applied to the WAV the PC's player gets) |
| `outrider/honk.py` | Auto honk (Linux; Windows experimental): `keyboard_backend()` picks evdev on Linux, `outrider.winkeys` on Windows; reads Primary Fire's binding (`keyboard_bindings` reads any controls) and presses it through a uinput virtual keyboard (`Honker`: its `owners`, "honk", "target" and "target-test", keep it open; its `lock` is held for a whole press or auto-target sequence; `press(check, cancel)` runs `check` under the lock just before the first key (a reason raises `NotNow`, nothing pressed) and `cancel` is that feature's own token, so switching one feature off stops its run while the other keeps the device open) |
| `outrider/winkeys.py` | Windows' stand-in for the part of evdev the key code uses: `ecodes.ecodes` (evdev key names -> scan codes, `EXTENDED` 0xE000 for extended keys), `EV_KEY`, `UInput` (`write` -> `SendInput` in scan-code mode); `SEND` is what tests replace (never reaching Windows). `set_clipboard` for `highway.Clipboard` on Windows |
| `outrider/target.py` | The Highway's auto-target: `build_steps` (the sequence; its configurable parts are `DEFAULT_SEARCH`, `DEFAULT_SUBMIT` and `DEFAULT_PLOT`, lists of `parse_step` strings found in game, see `DESIGN_NOTES.md`), `guard` (when it must not start; the game's own in-danger after an FSD use is waited out server-side:
`State.arrival_danger_until`, from `Journals.jump_arrival` / `supercruise_entry`) / `targeted` (already the target: Status.json's `Destination.System`, or NavRoute.json ending at it for a waypoint several jumps away), `Targeter` (resolves keys from the preset and `autotarget_keys`, `run`: the step runner on honk's device and lock, aborts, a cancel token, dry run), `US_KEYMAP` (typing), `ACTIONS` (the controls it may read, galaxy map camera included) |
| `outrider/button.py` | Co-pilot button (Linux): reads one HOTAS/keyboard button from `/dev/input`, read-only: `Gestures` ("status" a tap, "again" a double tap, "hush" a hold; `double_ms` 400), `ButtonWatch` (`on_gesture`, and `on_press` for every press as it happens). What each does is `State.copilot_gesture`: flying the ship a tap is `copilot_target` (Target next on `copilot_next`: the survey / trade route's next first, then the Highway's; a moment "autotarget" with what "nothing" or "refused" otherwise, spoken from `autotarget_nothing`), a double the status report, a hold the hush; `copilot_press` cancels a tap's run still counting down (a slow double tap) and the next tap is then the status report; the Rhino marks rigs |
| `outrider/rail.py` | The tablet's control rail, pure: `SHORT_LABELS`/`short_label` (a small tablet's names; a player's own name is kept), `CONTEXTS` and `context_of(status, vehicle_type)`, `CATALOGUE` (each context's buttons: action, Status.json state spec, amber) and `DEFAULT_IDS` (the agreed sets), `state_of`, `check_set` (the editor's input). `State.rail_info`/`rail_press`/`rail_save`/`rail_device` and `/api/rail*` use it; `Honker.tap` presses; `keyboard_bindings(..., category=)` reads the SRV and on-foot presets |
| `outrider/tools.py` | The AI's read-only tools, defined once: `TOOLS` (name, description, JSON-schema params, an async handler `(get, args, rows)`), `READ_ROUTES` (the GETs a handler may read; `guarded()` refuses the rest; `/api/nearest` only ever with `cached=1`, which never fetches the DSSA list), `listing()`, `call(name, args, get, rows)`, `Unavailable` -> `NOT_RUNNING` |
| `outrider/ask.py` | The voice (`POST /api/ask`, `State.ask`): `load_phrases`/`match` (resources/ask.json, in its order), `fixed_answer` (from the tools registry, in-process through `make_app`'s `local_get`; it gets the question's text too: `nearest_query` reads "nearest Vista", "nearest carrier"... for `nearest_dock`), `assistant_settings` and `ai_answer` (OpenAI-compatible chat with the registry as tools; `AIError` codes `ai_off`/`ai_timeout`/`ai_error`; every step of the provider's answer is shape-checked, and `State.ask` turns any other exception into `ai_error`). The answer goes out as a co-pilot action (`say`, or `caption` for hush/unhush) |
| `outrider/config_edit.py` | Settings' Server settings: `entries()` (every key, its value, kind and help, read from `config_text`'s output), `set_key()` (one key changed in the file in place: comments kept, a commented-out key switched on, a missing one appended after the last key's whole value, a `[section.key]` sub-table folded into the inline form), `coerce()`; `CHOICES` (plus `config_choices()` in ed_outrider.py) makes a key a pick-list. `State.config_info`/`config_save` and GET/POST `/api/config` use it (save: validated with settings_from, written atomically through a symlink to its target, the file's mode kept (0600 when new), the old file kept as `.bak`). `config_text` quotes text with `basic_string` (TOML escapes); only path keys get backslashes turned into slashes |
| `outrider/mcp.py` | The MCP bridge (`python3 -m outrider.mcp`): MCP's stdio JSON-RPC written directly (`handle`, `serve`; no SDK), `http_get` to the running server on 127.0.0.1, `mcp_settings` (`[mcp]`, also read by `settings_from`) |
| `outrider/auth.py` | `[server] password`: session tokens (`make_token`/`check_token`, HMAC, no list kept), `password_ok`, `is_loopback`, `from_this_pc` (loopback and no forwarding header), `client_key` (the sign-in rate limit's key), `request_token` (Bearer, then the `outrider_session` cookie), `version_tuple`, `RateLimit`. The guard itself is `session_guard` in `make_app`, the sessions `State.session_secret`/`new_session`/`session_ok`/`end_session` |
| `voice_lab.py` | A separate Tk window for trying voices and lines; not needed by the server |
| `static/page.html`, `page.css`, `page.js` | The page. `page.js` holds settings, polling, rendering, alerts and the speech queue; the Plot Route tab (formerly Highway; `view` "hwy") is its `hwy*` section, Road to Riches its `rich*` part (`loadRich`, `routeKind`: the route shown, `richMapRoute` for the map; the server's API unchanged) (`loadHwy`, `renderHwyList`, `drawHwyAuto` the auto-target box from `data.autotarget`, the plot form, the map's pure `hwyFit`/`hwyToScreen`, its background `drawHwyBackground` with the region layer `hwyRegionsSet`/`hwyRegionLayer`/`hwyRegionAt`, `renderHwyLine` for the strip); `hwyAutoStart(kind)` (test now, and Target next / Retry via POST `/api/highway/target`), `hwyAimBtn` (🎯 beside "Next:"), `hwySpoken` (the Highway clause of the status report); `linkState`/`drawLinkPill` (the link pill); `outVolume` (Volume, per device); `ownSounds` (your own sound files); drawn bodies: `bodyLook` (pure: kind, colours, rim, rings, size, seed from the ids) and `drawBodyArt` (the body panel's picture, `bodyArtHtml` its caption), `paintBody`/`bodyArtUrl` (the same drawing as cached data URLs for Here's schematic, seeded by `schemSystem`); `deskTheme` (this browser's desktop theme); the maps' touch: `pinchStep` (pure) |
| `static/tablet.css`, `static/themes/`, `static/fonts/` | The tablet layout (`GET /tablet`: the same page with `body.tablet`; `load_page(tablet=True)` adds `TABLET_STYLES` and `data-theme`; the desktop page links only the themes, `DESKTOP_STYLES`). `tablet.css` is structure only: the shell's grid and its neutral parts (`.tb-head`, `.tb-nav`, `.tb-main`, `.tb-rail`, `.tb-foot`, `.tb-banner`, `.tb-sheet`), every colour, font and radius a `--tb-*` custom property; each theme (`themes/lcars.css`) sets them and page.css's colours under its `[data-theme]`, and may dress a part's shape. `fonts/`: OFL fonts only, each with its `OFL-<Family>.txt`. `page.js`'s tablet section is at its end ("---- the tablet layout": `tabSetup` moves header, Now and main into `#tabMain`; `tabAutoView` the surface map's switch to Now and back; `tabRender` the status strip; `tabDrawLink`/`tabLinkText`; `tabBanner` for alerts; `tabRowTap`/`tabRowFacts`/`tabOpenRow` the row sheet over `TAB_SHEET_TABLES`; `tabOpenSettings`), its state in `TB` at the top beside `TABLET` |
| `static/emblems/` | The faction emblems under the tablet's page list (Elite, Babylon 5, Star Wars themes; `TB_EMBLEMS`, Settings' Show the theme's emblem), each credited in `CREDITS.txt` (`test_tablet.py` checks) |
| `static/sounds.json` | The alert sounds (synthesised note lists), shared by the page and the PC player |
| `resources/speech.json` | Spoken lines per alert and personality (business, sarcastic, sweet, plus `_profane` lists) |
| `resources/bio_rules.json` | Spawn rules and region map data fetched from upstream projects (refreshed at start when upstream changed); ships with every species' `colors` None. ExploData's colour tables go to `resources/bio_colours.json` beside it (git- and docker-ignored: downloaded on the first start, never shipped; `load_rules` merges them, `colours_available()`; a missing one makes the rules out of date). Tests needing the real colours skip without it |
| `resources/mining_odds.json` | Planetary mining survey odds per ground type (EDFM, CC BY-SA 4.0); read only, never edit by hand |
| `ed_outrider.toml.example` | Every config key, commented. The real `ed_outrider.toml` is git-ignored |
| `data/` | The player's own files, git-ignored as a whole: `ed_outrider.sqlite` (default `db`), `browser_defaults.json` (beside the database), `speech_banned.json`, `backups/` (default `backup_dir`), `piper-voices/` (with `voices.json`, Piper's catalogue cached a week), `fonts/` (the player's own theme fonts, served at `/userfonts/`). Created on first start |
| `docs/` | These notes; `docs/guide/` the user guide (the README links each page); `docs/images/` its screenshots (how they are taken: the author's private notes, `project/screenshots/`) |
| `tests/test_*.py`, `tests/support.py` | Unit tests by subject (`test_state`, `test_values`, `test_spansh`, `test_speech`, `test_devices`, `test_fuel`, `test_highway`, `test_config`, `test_pages`, `test_tablet` (themes, emblems, fonts, contrast), `test_rail`, `test_ask`, `test_mcp`, `test_auth`, `test_settings`, `test_server_mode` (server mode, Docker packaging, the launchers), `test_docs` (every doc link and anchor; `user_docs()` in support.py is the README and the guide as one text, for tests of what the docs say); unittest, in-memory SQLite). `support.py` holds the shared fixtures and fakes (`FakeGame`, `_fake_evdev`, `_HwSession`, `scan`, `T`...) and the helpers test classes share; import from it, never import a test class into another file (it would run twice). One file runs alone as `python3 -m unittest tests.test_highway` |
| `tests/page_smoke.js` | Loads the page in jsdom from a running server, opens every view, drives many page functions |
| `tests/fixtures/journals/` | Synthetic sample journals, `Status.json` and `NavRoute.json` (made-up commander and systems) |
| `scripts/verify.sh` | Runs everything below in one go against a throwaway server |
| `launch_outrider.sh` | The player's start script: makes `.venv` and installs `requirements.txt` when missing, changed (a sha256 stamp in `.venv/.requirements.sha256`) or broken (no aiohttp), then `exec`s `ed_outrider.py` with its arguments (Ctrl-C reaches Outrider directly) |
| `launch_outrider.bat` | The same for Windows: the stamp is a copy of `requirements.txt` (`.venv\.requirements.txt`) compared in Python with the aiohttp check (not `fc`: Wine's called identical files different); pauses on an error so a double-clicked window stays open. Windows line endings, kept by `.gitattributes`. Tested under Wine 10 with Windows Python 3.12: first run, the fast path and the page smoke test (Piper aside: Wine lacks `ucrtbase.crealf`, which numpy calls, so it crashes there; a Wine gap, not Windows) |
| `scripts/install.sh` | The older one-off setup (`.venv`, requirements, the voices up front), local to the author's checkout: git-ignored, so never in the published repository (never point players at it); `launch_outrider.sh` does the same when needed and starts Outrider |
| `scripts/dark_icons.py` | Writes the dark theme's icon masks into `themes/dark.css` from `static/icons/lucide/` |
| `scripts/docker_bundle.sh` | Builds the image and saves it into `dist/ed-outrider-docker-<version>-<arch>.tgz` with a compose file for it (`image:` and `pull_policy: never` instead of `build:`, rewritten from `docker-compose.yml`), `.env.example` and INSTALL.txt; also the release's `dist/docker-compose.yml` (running `ghcr.io/weslocke/ed-outrider:latest`) and `dist/env.example`. Publishes nothing |

## How data flows

1. **Journals.** `State.tick()` runs every second. For each live folder `Journals.scan_dir()` reads new bytes
   of every `Journal.*.log` from the stored offset (`journal_files`), complete lines only.
2. **Prefilter.** A line is parsed only if it contains `"event":"<Name>"` for a name in `WANTED` (built from
   the `*_EVENTS` tuples) or `Fixed_Event_Life`. `outrider/unsold.py` has its own filter (`INTERESTING`).
3. **Handling.** `Journals.handle(ev)` dispatches by event group (`handle_scan`, `handle_ship`, `handle_cmdr`,
   `handle_body`, `track_srv`...). It writes rows (visits, jumps, own_bodies, own_organic, sale_events...) and
   JSON state in `meta` (position, ship, carrier, fuel history...), and appends **moments**
   (`Journals.moment(kind, ts, ...)`) to a 16-entry deque with a growing `seq`.
4. **Status.json / NavRoute.json / Cargo.json / Market.json** are read when their mtime changes (`read_status`,
   `read_navroute`, `read_cargo_file`, `read_market`: only your carrier's Market.json is kept, as the game
   overwrites it at the next market).
5. **Commit, then follow-up.** After the commit the tick runs the follow-ups, each on its own (one that raises is
   reported by `follow_up_failed` and the rest still run; a database error stops them): `watch_status` (scoop, FSS,
   the hyperspace tunnel `watch_tunnel`, surface map, rig leash), `maybe_refresh` (the local cache at once, then the
   Spansh sphere on arrival), `apply_own_changes`, `maybe_classify_target`, `maybe_unsold`, `maybe_sale_left`,
   carrier, sellers, the quit backup, `highway_copy_next`, `highway_heavy_check`, `maybe_autotarget`.
   `State.bump()` wakes every waiting page request.
6. **Payload.** `GET /api/nearby?since=<run>:<version>` is a long poll (25 s, 204 when nothing changed; gzipped when the browser takes it) that
   returns `State.payload()`: position, systems, target, moments (priced by `moments_summary`), fuel,
   surface map, speech info and more. Other views fetch their own endpoints: `/api/system/{id64}`,
   `/api/body`, `/api/history`, `/api/organics`, `/api/log`, `/api/materials`, `/api/map`, `/api/search`,
   `/api/firsts`, `/api/left`, `/api/find`, `/api/export` (`what=system&id=`: one system's bodies, `State.export_system`), `/api/nearest` (the Nearest finder), `/api/cargo/lookup` (Spansh's markets, read only; POST
   `/api/cargo/recount` {counts} for your carrier's untracked lines; `/api/materials` carries `cargo`), `/api/highway` (+ `/systems?q=`, `/background`; POST `/plot`,
   `/clear`, `/autotarget` {enabled, delay}, `/autotarget/test`, `/target` {countdown?}: Target next / Retry), `/api/regions` (the Highway map's region grid), `/api/status` and `/api/status.txt`, `/api/version`, `/api/auth/signin`
   and `/signout` (see the app's contract below). The pages: `/`, `/tablet` (the same page, tablet layout), `/signin`;
   `/userfonts/{name}` serves a font from `data/fonts/`. The payload carries only the highway line's facts
   (`highway_summary`); the Plot Route tab fetches the route itself (`/api/highway`, and `/api/riches` with POST `/api/riches/plot` {kind: "riches" | "exo" | "trade"} and `/clear` for the slot). The payload's `survey` (`State.survey_summary`) is the survey route's line, as `highway` the Highway's. POST `/api/highway/target` {route: "highway" | "survey", index} targets any route system (`State.route_target`; no body: Target next). The payload's `update` ({version, current, url, kind}
   or null) is a newer GitHub release (`State.watch_updates`, `newer_release`, `install_kind`): the Update pill.
7. **Page.** `poll()` in `page.js` calls `onData()` (alerts) and `render()` (views). Moments with
   `seq > lastMomentSeq` become `alertOut(kind, title, body, {say})`: sound, desktop notification and a
   spoken line from `line(key, vars, plain)`.
8. **Speech.** `speak()` queues lines by priority (danger first; stale lines dropped; the queue clears when
   the FSD charges; a line can be held: the jump line waits for the "hyperspace" moment, at most `JUMP_LINE_WAIT`
   8 s). One window speaks (Web Locks). Audio is Piper via `/api/say`, the PC via `/api/say/play`, or the browser's
   own voice; the next line is synthesised while one plays (the PC's play request names it, the browser's Piper path
   posts it to `/api/say/prefetch`). Your own sounds come from `/api/sound/file/{name}`.

Ids: a system id64 can exceed 2^53, so the page compares the string `id` fields, never the number.

## Setup, run, test

- `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`
  (piper-tts and evdev are optional: delete their lines if you don't want them).
- `npm install` in the repo root (Node.js 22.22.2+ or 24.15+ for jsdom 30; jsdom runs the smoke test,
  playwright is only for optional screenshots and downloads no browser by itself).
- **One command:** `scripts/verify.sh`. It runs the unit tests (a ResourceWarning, such as a database a test never
  closes, fails the run: `self.addCleanup(db.close)`), pyflakes (any warning fails), `node
  --check static/page.js`, then starts a scratch server on a free port with a fresh database built from
  `tests/fixtures/journals`, a temporary config and no network, runs `tests/page_smoke.js`, and stops the
  server by its PID. All of it happens in a `mktemp` folder that is deleted afterwards. `VERBOSE=1` prints
  every smoke line and the server log.
- By hand: `python3 -m unittest discover tests` (one file: `python3 -m unittest tests.test_highway`);
  `node tests/page_smoke.js <port> [node_modules]` against a scratch server only: it clicks and POSTs, needs the port
  and refuses 8025. Waits in it: `settle(maxMs)` (the page's requests answered and quiet) rather than a fixed sleep,
  except where the page itself is on a timer. Runner (auto-target) tests can run on fake time: `use_fake_time`
  (`tests/support.py`).
- **The sample journals** (`tests/fixtures/journals`) are synthetic: commander "Sample Pilot", made-up systems
  Hesperine (a station; a sale), Corvane (a Rhino mining run) and Talvik Reach (honk, scans, a mapped body, bio
  signals, a completed and an in-progress sample run; the current system), a plotted route to Ossia, and a
  `Status.json` in supercruise. Two sessions, the first ending in `Shutdown`. Extend them by hand (keep the
  game's `{ "timestamp":"...", "event":"Name", ... }` spacing so the prefilter matches); never add real
  commander names or copy real journals.
- **A scratch server of your own** (to look at a change in a browser):
  - copy a database (`--db /tmp/x/copy.sqlite`), or let it build a fresh one from journals;
  - use a scratch config (`--config /tmp/x/scratch.toml`) with `[journals] live = [...]`,
    `[server] backup_dir` (or `backup_every_days = 0`) and `speech_file` pointing into the scratch folder,
    `[speech] server_player = "off"`, `[spansh] watch_firsts = false`, `[autohonk] enabled = false`,
    `[copilot] enabled = false`;
  - pick a spare port (`--port 8939 --host 127.0.0.1`) and stop the server by its PID, never with
    `pkill -f` (which can match your own shell);
  - for screenshots add `--simulate`: the panels read as if the game were running, with the last known values
    (`State.shown_status`, used only by the display: the fuel tile, the range, the Data tile's freshness), and the
    virtual keyboard, the co-pilot button and the clipboard are off whatever the config or the page says.
- **Never** point tests or scratch servers at your own running Outrider (port 8025 by default) or at your real
  `data/` (`ed_outrider.sqlite`, backups) / `ed_outrider.toml`. Use copies and a spare port.
- A scratch server reads journals read-only. If you point it at your real journal folder while the game is
  running, it reacts live: that is exactly why auto honk and the co-pilot must stay off.
- After a change to `outrider/bio.py`, run `python3 -m outrider.bio --backtest` on real journals; recall must not drop.

## Rules you must follow

- **`PARSER_VERSION`** (ed_outrider.py): bump it when the journal handler learns something that must be
  rebuilt from past journals (a new event, a new column filled from old lines). On the next start
  `open_db` runs `RESET_JOURNAL_DATA` and re-reads every journal once. Add a comment line saying why.
- **`CACHE_VERSION`**: bump it when the layout of cached Spansh records changes; cached systems in the old
  layout are ignored and fetched again.
- **Journal-derived vs live-only tables.** Journal-derived tables (visits, jumps, own_*, sales, codex,
  sale_events...) and meta keys must be cleared in `RESET_JOURNAL_DATA`, or a re-read doubles them.
  Live-only data (positions from Status.json, button presses, Spansh answers, estimates made at the time:
  `sample_points`, `bio_tags`, `upload_queue`, `surface_rigs`, `surface_sites`, `mining_locations`, `arrival_verdicts`, `sale_estimates`,
  `firsts_watch`, `bookmarks`, `highway_route` with its meta `highway`, `riches_route` / `riches_bodies` / `trade_stops` with meta `riches`,
  `carrier_markets` (each Market.json read at your carrier), `carrier_counts` (your Recount), the Spansh cache) cannot be rebuilt and
  must **stay out** of it (backups carry them). `fleet_loadouts` (the latest Loadout per ShipID) and `cargo_events` (your
  carrier's history, per journal line) with meta `ship_cargo` and `cargo_dock` are journal-derived.
  Say which kind a new table is in its schema comment.
- **Out-of-order and replayed lines.** Legacy folders are imported late and a re-read replays everything:
  guard current-state updates with `self.fresh(key, ts, ...)`, and anything that should only happen during
  live play (spoken moments about losses, positions, sales in progress) with `live_event(ts)`.
- **Failed ticks.** A tick that raises is rolled back and `Journals.reload()` restores memory from the
  database; `checkpoint()`/`restore()` cover what lives only in memory (moments, sets of bodies touched,
  the collection under way...). New in-memory state changed by handling lines must be added to both, or a
  retry announces things twice. A journal line that lacks a field is skipped with a log line
  (`KeyError`/`TypeError` are caught per line); database errors must propagate so the tick is retried. The
  follow-ups after the commit run one by one: an exception is reported (`follow_up_failed`: the traceback once, the
  error on the page) and the next one still runs; `sqlite3.Error` propagates.
- **Per-browser settings** go in **both** `SETTINGS_KEYS` (top of `page.js`) and `BROWSER_SETTINGS`
  (ed_outrider.py), in the same order; a unit test compares them. Per-device things (view, layouts, which
  screen speaks, `volume`, `tilesMode`, Settings' `alertSection` and `settingsOpen` (its open sections), `desktopTheme`, `updateSkip` (the release the Update pill was dismissed for), `hwyShow` (the route Plot Route shows with both), `nearest` (the Nearest finder's filters), `hereBio` (Here's bio column: finished species and few-signal bodies left out), the tablet's `tabletView`, `tabletTheme`,
  `tabletDim`, `tabletEmblem`, `tabletRail` (Show the game controls) and `tabletAudio` (Play alerts here)) go in neither. Object or list values need an entry in `SETTING_SHAPES`.
- **An open page reloads itself on newer page files:** the payload's `page_stamp` (`page_stamp()`: sizes and
  modification times of `PAGE_FILES`) against the `__PAGE_STAMP__` it was served with; `pageStampTick` reloads once
  nothing was touched for `RELOAD_IDLE_MS` and nothing is said, open or typed in. A new file the page loads goes in
  `PAGE_FILES` (a theme in `TABLET_STYLES` is in it already). State worth keeping across that reload belongs in
  per-device storage, as the view is. `page_stamp` and `restart_needed` come from one cached refresh (`stamps()`), so
  they always agree; the served page takes a fresh one (`stamps(fresh=True)`).
- **The tablet layout** (`body.tablet`, `TABLET` in page.js) is the same views in another shell, never a copy of them:
  a view change works on both. The tablet never joins the one-speaker lock, and it is silent (`speakMode()` "never")
  unless its Settings' Play alerts here is ticked (`tabletSpeaks()`, per tablet: then "always", whatever a PC window
  does); keep any new sound or speech path behind `speakerHere()`. The browser's own voice is used only when
  the server has no Piper (`data.tts.available` false); while the browser holds audio back (`audioBlocked()`), the
  speaking window shows `#audioPill`, posts `/api/speaker/audio` (the payload's `speaker_audio_blocked`, on the
  tablet's caption line) and `sayNow` holds its line until the click (`audioUnlocked`), dropping it if stale. It has no Overview. The desktop page must
  not change: tablet-only rules go under `body.tablet` in `tablet.css`, themes only under their `[data-theme]` (`/tablet`
  sets one; the desktop page only when its browser chose one in Settings > Display: `desktopTheme`, `deskTheme()`, set
  in `<head>` before the first paint; the Default is no `data-theme` at all). The dark theme's icons are CSS masks written into `themes/dark.css` by `scripts/dark_icons.py` from
  `static/icons/lucide/` (run it after changing its `ICONS`). A new theme: its stylesheet in `TABLET_STYLES` (the desktop page links it too: `DESKTOP_STYLES`), its name in
  `TABLET_THEMES` and `TB.themes`, an `<option>` in `#tabTheme` (the desktop picker copies it), and a desktop section in
  its file under `[data-theme="…"] body:not(.tablet)` with `--desk-pill`, `--desk-radius`, `--desk-pill-size` (and
  `--desk-pill-font`/`-case` for a very wide display face); `test_tablet.py` checks the section, the selected pill's
  contrast and every text colour against the background and panels (4.5:1). Keep the pill row about the Default's width. A font: OFL only, with its licence file (`test_tablet.py` checks); a fan font is the
  player's drop-in in `data/fonts/` (`/userfonts/`, `USER_FONT_RE`), listed first in the theme's `@font-face`.
  Every `<button>` in a `<form method="dialog">` has a `type` (`test_tablet.py` checks): a ✕ or Done is
  `type="button" data-close` (closed by one page-wide handler), since an untyped one is what Enter in a field presses.
- **Page layout: scroll the pane, not the window.** On a window of at least 900 × 600 (`appWanted`; not Now) the
  body gets `app`: it is the window's height with no page scroll, the header stays, the view fills the rest (flex
  columns with `min-height: 0` down the chain) and each `.pane` (a bordered box, tabindex in app mode) scrolls on its
  own, its `thead th` sticky. A view's controls sit above its pane. A new list goes in a `.pane` with an id (and in
  `VIEW_PANE` if it is the view's main one). Scroll with `revealIn(el)` (a row into view, under the sticky heading),
  `scrollMark`/`keepPlace` (rows added above) and `paneOf(el)`, never `window.scrollTo`/`scrollIntoView` directly;
  size things to their box in app mode, not to `innerHeight` (only Now and page mode use the window). App-mode CSS is
  the `body.app` block at the end of `page.css`; below the size nothing of it applies, so check both.
- **Loaders that can overlap** (a forced refetch, a new radius while the last answer is still on its way) take a
  `newRequest(kind)` token and drop their answer unless `isNewest(kind, token)`: a late older answer must never
  overwrite a newer one (`loadHwy`, `loadLeft`).
- **Compact tables.** The tables in `FIT_TABLES` get `compact` (then `compact2`) when they do not fit their box
  (`fitTable`, decided by `compactLevel` from the min-content width at each level; ResizeObserver plus a
  MutationObserver on the rows). A cell holds both forms: `dual(full, short, {s2})` / `sfText(kind, text)` give
  `.lf` + `.sf` (or `.sf1`/`.sf2`), the short one titled with the full text; `.c1hide`/`.c2hide` drop a column. Put
  abbreviations in `SHORT_FORMS` / `shortForm(kind, text)` (headings: `SHORT_FORMS.head`, applied at start), never
  ad hoc, and only in those tables (outside them both forms would show). Speech and notifications keep the full words.
- **Spoken lines.** Every alert key must agree across `speech.json`, `outrider.speech.KEYS` (with its placeholders),
  `outrider.speech.SAMPLES` (a value for every placeholder), a `line("key", ...)` call in `page.js` and a
  `LINE_SAMPLES` entry in `page.js`. The shipped lists hold 50 lines each for business, sarcastic, sweet and
  the two `_profane` lists for most keys (a newer key, `autotarget_nothing`, about 15); unit tests check coverage, placeholders and at least 10 per list. Danger keys
  (`DANGER` in page.js) are spoken only from business lines by default.
- **Config keys.** A new key needs: parsing in `settings_from` (with a sane default and a warning on a bad
  value), `config_text` (so `--write-config` writes it, WITH a `# help` comment on its line: Settings' Server
  settings lists every key from `config_text` through `outrider/config_edit.py` and shows that comment as its help;
  `test_settings.py` checks every key has one and can be written back), `ed_outrider.toml.example`, and the guide's
  Settings page (`docs/guide/settings.md`). Server defaults for browser settings also go in `payload()["defaults"]` and `run()`.
- **Endpoints.** Every request passes `request_guard`: unknown Host names are refused, and a request another
  site's page sends is refused (Origin / `Sec-Fetch-Site`; `http://` or `https://` of the same Host, for an HTTPS proxy
  on the LAN; an `allowed_hosts` name is also answered without a port). The sign-in page's `next` passes `safe_next`
  (server) and `safeNext` (page) or becomes "/". Only `OPEN_GETS` (`/api/status`,
  `/api/status.txt`) may be read cross-site. Anything that changes state must be a POST. Don't widen
  `OPEN_GETS`; validate every input (ids with `parse_id64`, JSON with `json_object`). Then `session_guard`: with
  `[server] password` set, a request not from this PC (`outrider.auth.from_this_pc`: loopback without a proxy's
  forwarding header) needs a session, except `AUTH_OPEN` and `OPEN_GETS`; without
  one, 401 `signin_required` for `/api/`, `/static/` and the app's User-Agent (`OutriderApp/`), else a redirect to
  `/signin`. Don't add to `AUTH_OPEN`. Tests reach "another device" by patching `outrider.auth.is_loopback`
  (`tests/test_auth.py`).
- **Docker** (`Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `.dockerignore`): the image sets
  `OUTRIDER_CONTAINER=1` (so `game_pc` auto is off), writes a first-run config into `/config`, and is checked by
  `test_server_mode.Packaging` without Docker; build and run it by hand (`docker build`, `docker run` with scratch
  folders) after changing it. verify.sh never needs Docker. The entrypoint is PID 1: anything it waits on must trap
  SIGTERM, or `docker stop` hangs for the whole grace period. The compose project is named `ed-outrider` (one
  project for a checkout and every bundle). A release, after bumping `outrider.__version__` and pushing: `scripts/docker_bundle.sh`; tag the image
  `ghcr.io/weslocke/ed-outrider:<version>` and `:latest` and push both; then a GitHub Release `v<version>` on that
  commit with `dist/docker-compose.yml`, `dist/env.example` and the bundle attached (the install guide fetches the first two
  from `releases/latest/download/`, so every release must carry them), its notes leading with the registry. The
  guide's Docker section (`docs/guide/install.md`) and the bundle's INSTALL.txt (written by the script) must agree on the install and update steps.
  Each release also gets a section at the top of `docs/guide/whats-new.md` (before the version bump's commit): the
  player's view of what changed since the last release, not the changelog. New features, settings, and anything to do
  or know before updating (a journal re-read, a Docker change), short and plain, with a screenshot where one helps.
  A withdrawn release has no section; its changes go into the next one's.
- **Stopping.** SIGTERM (docker stop, systemd) sets `run()`'s stop event: the same cleanup as Ctrl-C (tasks
  cancelled, commit, the quit backup, "stopped cleanly", exit 0). `verify.sh` stops its scratch server that way and
  fails if it does not stop cleanly.
- **Server mode** (`[server] game_pc`, `State.game_pc`; `resolve_game_pc`: auto is off inside a container). Off: no
  virtual keyboard (`simulate_keyboard_off`), no co-pilot button or clipboard (`simulate_settings`), the PC player off;
  every route that presses keys or plays on this PC is registered through `pc_only()` and answers 409 `not_game_pc`.
  A new such route goes through `pc_only()` too; the payload's `game_pc` tells the page what to leave out: the page sets
  `body.notgamepc`, which hides every `.pcOnly` element and `[data-aim]` button (mark a new game-PC control `pcOnly`).
- **The rail presses keys** (like auto honk and auto-target): one tap of one bound key combination per press
  (`Honker.tap`), only for a button in the CURRENT context's set, only while the game is live, never with --simulate,
  and refused (not queued) while auto honk or auto-target hold the keyboard. Never a sequence. Tests use
  `_fake_evdev()` and a recording UI (`tests/test_rail.py`), never `Honker.open()`. Its sets are live-only meta
  (`rail_sets`), out of `RESET_JOURNAL_DATA`. `close()` never waits for the lock: whoever holds it (`tap`, `press`,
  auto-target) closes the device on its way out when `stop` is set, whichever way it leaves.
- **The AI's tools are read-only, by rule** (`outrider/tools.py`). A handler reads only through the `get` it is given,
  and only `READ_ROUTES` (GET routes that change nothing; `/api/find` is out because it can store a system). Never add
  a POST route or a tool that acts (presses, plots, bookmarks, hushes): `test_mcp.py` walks every tool and checks.
  A new tool goes in the registry once; the MCP bridge and the voice's AI layer both serve it. Keep answers compact
  (`capped`, the fields that answer the question).
- **The Android app's contract** (the app is its own repository, ED-Outrider-Android). `GET /api/version` answers exactly
  `{outrider, api, min_app, password, signed_in}`; `POST /api/auth/signin` {password} gives `{ok, token}` and the
  cookie; `POST /api/auth/signout`; `POST /api/ask` {text, source?} gives exactly `{answer, spoken, matched, command}`; `/api/version` also has `game_pc`
  (added 2026-10-04);
  errors are `{error, code}` (`signin_required`, `bad_password`, `rate_limited`,
  `bad_request`, `app_too_old`, `server_error`, `ai_off`, `ai_timeout`, `ai_error`). Bump `API_VERSION` when an endpoint the app uses changes shape
  incompatibly, `MIN_APP_VERSION` when an older app can no longer work (426 `app_too_old` for its
  `X-Outrider-App` header), and `outrider.__version__` with each release. The app's tests depend on these shapes.
  The other way, the page calls the app's JavaScript bridge `window.OutriderApp` (bridgeVersion 1): `listen()`,
  `setTheme(name)`, `appVersion()`, and from app 1.2 `openServer()`, `openVoice()`, `openMenu()` (the tablet's
  Settings → Tablet app). Feature-detect every call (`typeof OutriderApp.x === "function"`): an older app lacks them.
- **Devices.** Never exercise auto honk (uinput key presses: they go to whatever window has focus, including
  a running game) or the co-pilot button (reads `/dev/input`) against a real game or device from tests or a
  scratch server, and the same for auto-target (it opens the galaxy map and types): tests use `FakeGame` (a fake
  device that plays the galaxy map) with `_fake_evdev()` (key codes, no `UInput`), never `Honker.open()` on real evdev.
  Never POST to `/api/highway/autotarget/test` or `/api/highway/target` on a server that sees a live game. Use the existing fakes: `FakeGame`, `_fake_evdev()`,
  `button_fake_evdev`, `FakeClock`/`use_fake_time` in `tests/support.py`, and the local `FakeHonker`/`FakeUI` classes
  in `test_devices.py` and `test_config.py` as patterns. Never POST to `/api/autohonk` or `/api/autohonk/test` on a server that sees a live game.
- **No stray side effects.** Don't download Piper voices into the real `data/piper-voices/`, don't let a test
  rewrite `resources/bio_rules.json`, and don't write the real `data/speech_banned.json` (use a speech file in a
  temp folder: its bans go beside it).
- **Every fix gets a test that fails without it.** Unit tests feed synthetic events to `Journals.handle()` on
  `open_db(":memory:")`; page behaviour goes in `page_smoke.js`, injecting the data it needs through
  `window.eval` rather than relying on anyone's real database.

## Recipes

**A new alert (moment).**
1. In the handler, `self.moment("my_kind", ts, ...)` with plain JSON fields (ids as ints; `live_event(ts)` if
   it must not fire on a re-read).
2. If it needs pricing or names, add them in `State.moments_summary()` / `moment_extra()`.
3. In `onData()` (page.js), a branch for `m.kind === "my_kind"` calling `alertOut(...)`; reuse an `ALERTS` row
   or add one (its id is the per-alert sound/notify/speak switch).
4. A spoken line: see below. Tests: a unit test for the moment, a smoke check for the page's reaction.

**A new column.** Add it to the `CREATE TABLE` in `SCHEMA`; `open_db` adds missing columns to old databases.
If it is filled from journals, write it in the handler and bump `PARSER_VERSION`; if from Spansh records,
bump `CACHE_VERSION`. Old rows have NULL: code must cope.

**A new setting.** Page-only: a `store.get(key, default)`/`store.set` pair, the key in `SETTINGS_KEYS` and
`BROWSER_SETTINGS` (same position), a control in the Settings dialog (in the section it belongs to). With a config default: the four config
places above plus `data.defaults`.

**A new spoken line.** `outrider.speech.KEYS["key"] = "when it is said: {placeholders}"`, `SAMPLES["key"]`, an entry
in `speech.json` (`"when"` plus five lists), `line("key", vars, "plain fallback")` in page.js, and
`LINE_SAMPLES.key`. Run the unit tests: they name what is missing.

**A Spansh job (the Highway's plotters).** Spansh answers a plot with `{job}`; `Spansh.plot(url, params)` asks
`SPANSH_RESULTS` every `HIGHWAY_POLL_S` (1.5 s) until `result` comes, gives up after `HIGHWAY_PLOT_TIMEOUT` (180 s),
runs one plot at a time (`sem_plot`) and raises `HighwayError` in words for the page. The POST handler validates the
body, starts the job as a background task (`State.highway_task`, cancelled by clear and at shutdown) and answers
202 at once; the page polls `GET /api/highway` while `plotting.state` is `running`. Unit tests use a fake session,
never Spansh; `verify.sh` points every `SPANSH_*` URL at a closed port and sets `Clipboard.TOOLS = ()`, so a
scratch server neither plots nor touches the desktop clipboard. Moments about the route are kind `highway`
(`what`: next, back, off_route, complete, heavy; plain `text`, no `speech.json` keys yet), only for `live_event` arrivals.

**A new icon in Here's rows or schematic.** Add a `HERE_LEGEND` entry in page.js (a test on what is shown, the icon,
what it means); the footer lists only the icons shown, so a missing entry leaves the icon unexplained. The smoke
test's Here check shows the pattern.

**A new journal event.** Add its name to the right `*_EVENTS` tuple (or `WANTED` never lets the line through),
handle it, decide journal-derived vs live-only, bump `PARSER_VERSION` if past journals matter, add a
summary in `outrider/log.py` if the Log should word it, and add the event to `tests/fixtures/journals` if the page
should show it. Check `JOURNAL_REFERENCE.md` for the event's quirks.

## Design principles

- Everything comes from the player's own journals and public community data. Nothing is tuned to one ship,
  one commander or one machine: the fuel model fits the player's own jumps, thresholds are settings.
- Never present a guess as a fact. Predictions say "up to", "could be", "odds, not contents",
  "probably full"; Outrider's own record (rig marks) is labelled as such, not as the game's.
- Alerts are for the out of the ordinary. Routine systems stay quiet.
- Nothing is uploaded unless the player switches EDDN or EDSM on (Settings → Uploads). Other outside calls are read-only lookups (Spansh, EDSM, GitHub for rules and the update check
  (`[server] update_check`), Hugging Face for voices, EDAstro for the DSSA carrier list, on demand; Canonn's codex reference once a day for the
  checklists' picture links, `State.watch_codex_images` into data/codex_images.json).
- The README is the front page: what Outrider is, a short start and the guide's index. The user guide is
  `docs/guide/` (one page per topic, a nav bar on each); keep it user-facing, short bullets. A new feature goes on its
  topic's page; a section moved between pages keeps an `<a id>` for its old anchor in the README's index (old links
  still land). `test_docs.py` checks every relative link and anchor. Implementation detail belongs in code comments.
- Per-player defaults (names the voice uses, thresholds, voice) are only defaults; never hard-code a
  player's preference.
- Keep optional parts optional: the server must run without Piper, evdev, network or journals.
