[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · **Settings** · [For the curious](for-developers.md)

# Settings

Outrider needs no configuration, but everything can be changed: in ⚙ Settings on the page, in the config file
`ed_outrider.toml`, or with command-line flags for a single run. What each setting does is explained beside its
feature; this page is about the Settings panel itself, the Server section, notices, the config file and the command
line.

## ⚙ Settings

**⚙ Settings** (top right) holds everything, in folding sections; its chips jump to its sections. The sections are
Alerts (with the alert sounds to try), Voice (with what the voice says: signals, routine systems, hazards, mapped
planets), Worth stopping for, Risk & warnings, Surface map, Mining,
Auto honk (and the co-pilot button), Auto-target, In-game overlay, Screenshots, Uploads, Display,
Sharing, **Server**, Spoken lines and Questions asked.

### Find a setting…

**Find a setting…** at the top leaves only what matches the words typed, in every section at once, Server's keys
included. Clear it and every section is back as it was.

- **What it matches:** a setting's name, its help or its config key. `speech_speed` finds the Speed slider too.
- **A whole section or block:** a section's name shows all of it, and so does a block's heading inside one. "backups"
  shows the whole Backups fold, "inara" all of Inara's part of Uploads.
- **The crew:** "crew" shows the whole Crew block (every member, the switches, the note on the XO); "xo" or a role's
  name ("navigator") finds it too.
- **Tables:** a table is never cut down to one row. When a row of it matches, the whole table shows with the matching
  rows marked: "tactical" shows every crew member, Tactical's row marked.
- **The config file's keys:** the keys set in a section of their own (below) are found there by their key too.

### This browser's settings and the server's

Most settings are this browser's own. Sharing exports them or makes them the defaults for new browsers.

**Server** is the config file's keys that have no section of their own, each row with its `[section]` in the file.
They come in six groups:

- **Network and access**
- **Files and backups**
- **Online checks**
- **Nearby**
- **Plot Route**
- **The voice's AI and AI clients**

The rest of the file is set in its own sections:

| In the file | In ⚙ Settings |
|---|---|
| `[defaults]` | The rows it starts new browsers with: Worth stopping for, Risk and warnings, Voice, the surface map. Sharing makes this browser's choices every new browser's defaults. |
| `[speech]` | Voice |
| `[autohonk]` and `[copilot]` | Auto honk |
| `[highway] autotarget_*` | Auto-target |
| `[overlay]` | In-game overlay |
| `[screenshots]` | Screenshots |
| `[eddn]`, `[edsm]` and `[inara]` | Uploads |

The file keeps every key, to edit by hand if you like: see [The config file](#-the-config-file).

### Saving and Restart now

Saving a config-file key in Settings writes `ed_outrider.toml`:

- only the keys you changed;
- its comments stay;
- the previous file is kept as `ed_outrider.toml.bak`.

Outrider uses them from its next start: **Restart now** beside "Saved" does that at once.

### The keys that take effect at once

A few keys take effect at once instead of at the next start:

- **`[speech] voices_loaded` and `voices_preload`.** Settings → Voice writes them too: **Keep loaded** and **Load them
  at start** under Voices kept loaded, shown whenever a voice besides the main one is in use.
- **`[speech] pad_delay`:** the next docking grant.
- **`[autohonk] delay` and `skip_honked`:** the next honk.
- **`[defaults] rig_warn`** (Settings → Surface map's far-rig distance): the leash warning and every window's map.
- **`[defaults] pickup_pins`** (Settings → Surface map's pickup pins tick): the next pickup.
- **Every `[screenshots]` key:** the next shot.
- **Every `[highway] autotarget_*` key:** auto-target's next run, so a sequence can be tried without restarting. The
  galaxy map's steps and timings have their own section, **Auto-target**: see
  [Plot Route](plot-route.md#-targeting-and-auto-target).

**Find a setting** finds them by those words, by "memory" or by their keys.

### Passwords

The passwords (`[server]`'s and `[mcp]`'s) and the AI key are never shown, only whether they are set.

### Not saved yet

The sections with a Save button of their own keep what you type until you save it. They are Auto honk, Auto-target,
Screenshots, Server, and the EDSM and Inara keys in Uploads.

- **The mark:** while a field there differs from what is saved, its section's heading says **· not saved**.
- **Done (or Esc)** keeps Settings open on it once, with "Not saved yet: **Save** keeps it · **Discard**". Discard puts
  the saved values back.
- **A second Done** closes Settings anyway: what you typed stays in its fields, still marked, until you save it,
  discard it or reload the page.

## 🖥 Server: Restart, Show log and Backups

⚙ Settings → **Server**'s top row says which Outrider is running and has **Restart** and **Show log**. Below it are
**Backups** and **Start with this computer**.

### Restart

**Restart** stops Outrider cleanly and starts it again. A backup that is running finishes first.

- **From any device** the page answers (signed in when a password is set). Every window reconnects by itself, and
  says "starting" while it reads the journals.
- **It works when Outrider was started by** `launch_outrider.sh` (started again in the same window, its setup
  included), `python ed_outrider.py`, `launch_outrider.bat`, as a service (systemd starts it again) or in Docker
  (compose's restart policy). Otherwise the button is greyed out and says why.
- **After an update:** "Outrider has been updated: restart it" under the header has the same button.

### Show log

**Show log** shows what Outrider has printed in its terminal since it started: its last 2,000 lines, newest at the
bottom, following along while it is open. Problems are in amber.

- **Copy** copies it for a bug report.
- It works from any device, a server's too.
- The same lines are saved beside the database in `outrider.log` (`data/outrider.log` by default; the older part in
  `outrider.log.1`).
- Passwords and API keys never appear in it.

### Backups

**Backups** lists the backup zips with the command that restores one. How backups work:
[Backups](install.md#-backups).

### Start with this computer

**Start with this computer** installs Outrider as a service, or removes it: a systemd user service on Linux, a Startup
entry on Windows (see [Install and run](install.md#start-with-your-computer)). It does that only from the browser on
that PC; elsewhere it shows the command.

## 📢 Notices

A notice is a line under the header, in every window and on the tablet, saying what is wrong. It has a button where
one helps (Server settings, Show log).

- **At start**, Outrider says what it finds wrong:
  - a journal folder not found;
  - problems in the config file or the spoken lines file;
  - listening on your network with no password;
  - journals on a share that shows them late;
  - the in-game overlay's address taken;
  - a `[server] host` that is no longer this PC's address.
- **While Outrider runs**, others come, and go once the cause does:
  - the journal folder cannot be reached;
  - the backups' disk is nearly full;
  - a second commander in the journal folder (or another commander playing);
  - an upload on hold;
  - your carrier's upkeep running low.
- **✕** hides a notice everywhere until Outrider restarts, or until the message changes.

## 📝 The config file

The server's settings are kept in `ed_outrider.toml`, next to the script by default. ⚙ Settings writes it for you, and you can
also edit it by hand.

### Editing it by hand

Copy `ed_outrider.toml.example` to `ed_outrider.toml` next to the script and edit the lines you need. The example
explains every key.

- **The settings in effect:** `python3 ed_outrider.py --write-config` writes a file with them.
- **Relative paths** in it (`db`, `backup_dir`, `speech_file`, `sound_dir`, `background_image`) are relative to the
  Outrider folder. The first three default to `data/ed_outrider.sqlite`, `data/backups` and `resources/speech.json`.
- **Switches** take a bare `true` or `false`. A wrong value is reported at start and the default kept.
- **A number out of its range** is refused in words when you save it in Settings ("[highway] efficiency must be 1 to
  100 %"). In a file edited by hand it is brought into range.

> [!IMPORTANT]
> **Windows paths in the file:** use forward slashes, `"C:/Users/you/Saved Games/..."`, or single quotes,
> `'C:\Users\you\Saved Games\...'`. In double quotes a backslash starts an escape (`"C:\Users"` is an error),
> and a file that cannot be read is ignored as a whole: every setting back at its default, with one line in the
> console saying why. Settings → Server takes paths either way and writes them correctly.

### Every key

Each section's keys, with their defaults in brackets. `[overlay]` and `[screenshots]` have tables of their own below.

| Section | What it holds (default) |
|---|---|
| `[journals]` | `live` and `legacy` folders, when auto-detection misses them (both auto-detected when absent; setting `live` turns off legacy auto-detection: list `legacy` too, `[]` for none); `commander`: only that commander's journals (the FID or the name; blank for all; **Choose…** beside it lists the commanders the journals hold; see [Two commanders on one PC](install.md#two-commanders-on-one-pc)) |
| `[server]` | `host` ("127.0.0.1"), `port` (8025), `password` ("": none), `game_pc` ("auto": off inside a container), `update_check` (true), `canonn_reports` (true: on arriving in a system, Canonn is asked, with its name only, which notable stellar phenomena have been reported there; the phenomena alert says the ones you have not logged in it), `open_browser` (true: the first start, with no database yet, opens the page in your browser on the game PC; never in Docker, under the service or `--simulate`), `allowed_hosts` ([]), `radius` (25 ly), `radius_choices` ([20, 25, 30, 40, 50]), `sights_range` (500 ly, up to 5000: Now names the nearest of EDAstro's catalogued sights within it; 0 off, nothing fetched), `db` ("data/ed_outrider.sqlite"), `backup_dir` ("data/backups"), `backup_keep` (7), `backup_every_days` (1), `speech_file` ("resources/speech.json") |
| `[defaults]` | What a new browser starts with: the thresholds `unsold_warn` (50000000), `unsold_urgent` (250000000), `bio_min` (10000000), `body_highlight_level` (500000), `biology_highlight_value` (10000000), `body_max_value_include_bonus` (true), `high_gravity` (2.0 g), `module_warn` (80 %); `sounds` (true), `voice` ("en_GB-cori-medium"), `voice_fallback` ("en_GB-jenny_dioco-medium"), `speech_styles` (["business"]), `speech_profanity` (false), `speech_profanity_pct` (50), `speech_danger_business` (true), `speak_bio_signals` (true), `speak_geo_signals` (true), `speak_codex_signals` (true), `speak_mapped` (false), `codex_interesting` (true), `speech_speed` (1.0), `speech_names` ("Boss, Hefay, Sir"); the surface map's `surface_alt` (1000 m), `rig_spacing` (50 m), `surface_map_min` (500 m), `surface_map_strip` (false); and two that are not a browser's default but every window's: `rig_warn` (3500 m, the leash warning, set by Settings → Surface map's far-rig distance) and `pickup_pins` (true: a Guardian or Thargoid pickup on a body drops a pin, set by Settings → Surface map's tick) |
| `[spansh]` | `concurrency` (4), `map_max_radius` (250 ly), `map_max_pages` (6), `watch_firsts` (true) |
| `[autohonk]` | `enabled` (false; once the **Honk automatically** switch in Settings → Auto honk has been used, its last state is kept in the database and this key is no longer read), `key` ("auto": read from your controls preset), `delay` (2.0 s), `hold` (6.0 s), `skip_honked` (true), `announce` (true) |
| `[speech]` | `server_player` ("auto"), for **Play speech and sounds on this PC**; `pad_delay` (5: seconds after a docking grant before your landing pad is said, Settings → Voice); `sound_dir` (none), your own alert sounds; `voices_loaded` (unset: the voices in use up to 4; a number, or "all"), how many voices besides the main one stay loaded (each about 1.6 times its file's size in memory, about 100 MB for a medium voice; one set aside waits about a second the next time it speaks); `voices_preload` (false), load them when Outrider starts instead of on their first line (both also in Settings → Voice → Voices kept loaded, used at once) |
| `[copilot]` | `enabled` (false), `device` (""), `button` (""), `hold_ms` (600), `double_ms` (400) |
| `[assistant]` | `enabled` (false), `base_url` (""), `api_key` (""), `model` (""), `timeout` (20 s), `max_rounds` (4): the voice's optional AI layer |
| `[mcp]` | `url` (this PC at `[server] port`), `max_rows` (25), `password` (""): for the MCP bridge (see [Ask an AI about your game](voice-and-alerts.md#-ask-an-ai-about-your-game)) |
| `[eddn]`, `[edsm]`, `[inara]` | `enabled` (false): written by the switches in Settings → Uploads (the only place to change them) |
| `[overlay]` | The in-game overlay: see [The `[overlay]` keys](#the-overlay-keys) |
| `[screenshots]` | Screenshots: see [The `[screenshots]` keys](#the-screenshots-keys) |
| `[highway]` | `clipboard` (true), `efficiency` (60 %), `conservative` (false), `conservative_ly` (5 ly), `voice_plot` (true: the voice's "nearest station"... also plots a neutron route there past `voice_plot_ly`, 500 ly), `background_image` ("": none), `background_extent` ([-45000, 45000, -20000, 70000]), `background_opacity` (0.6); auto-target: `autotarget` (false), `autotarget_delay` (5 s) (once the Plot Route tab's or Settings → Auto-target's switch or delay has been used, Outrider keeps their last state in the database and these two keys are no longer read), `autotarget_entry` ("type"), `autotarget_map_wait` (5 s), `autotarget_search_wait` (3 s: a second more for each 200 ly to the system, up to 7), `autotarget_key_delay` (0.05 s: the typing delay, between the name's characters when typed), `autotarget_step_pause` (0.25 s: the pause after each key of the steps), `autotarget_target` (the Target System steps) and `autotarget_route_target` (true: a route's next stop one jump away is targeted, not plotted), `autotarget_keys` ({}: read from your controls preset), `autotarget_search`, `autotarget_submit`, `autotarget_plot` (the galaxy map's steps: see the example file), `autotarget_dry_run` (false) |

### The `[overlay]` keys

The overlay is a game-PC feature: see [In-game overlay](overlay.md).

| Key | Default | What it does |
|---|---|---|
| `enabled` | false | |
| `theme` | "default" | Or lcars, elite, babylon5, narn, minbari, centauri, vorlon, shadow, sith, alliance, dark. |
| `text_size` | "normal" | A panel can have its own in Settings. |
| `panel_scale` | 100 | All panels' size in %, 20 to 250 (Settings' All Panels: Scale), multiplied with each panel's own Size %. Text is never drawn under 9 px. |
| `system_panel` | true | |
| `body_panel` | true | The Target panel. |
| `radar` | true | |
| `strip_panel` | false | |
| `now_panel` | false | |
| `bio_panel` | false | |
| `alerts_panel` | false | The page's alerts for a few seconds. |
| `system_seconds` | 0 | 0: while in supercruise there; up to 3600 s. |
| `radar_range` | 800 m | 100 to 20000. |
| `strip_reference` | "" | "": Sol; the system the strip measures its distance to. |
| `analysis_only` | [] | The panels shown in your ship only while the HUD is in analysis mode. |
| `hide_docked` | ["system", "body", "now", "bio"] | The panels hidden while docked. |
| `show_inactive` | false | Keep showing when Elite is not the active window. |
| `pad_diagram` | true | While docking at a starport or carrier, a diagram of where your pad is, in the Surface radar's place and on Now. |
| `hide_on_foot` | [] | The panels hidden on foot. |
| `hide_mouse_lock` | false | No overlay at all on foot and in the DSS, where Elite locks the mouse. |

### The `[screenshots]` keys

Every key takes effect at once. `~/` in a folder is your home folder. Screenshots are a game-PC feature only: see
[Screenshots](automation.md#-screenshots).

| Key | Default | What it does |
|---|---|---|
| `enabled` | false | |
| `pictures` | "" | "": the game's Pictures folder, found beside its journals. |
| `folder` | "" | "": that folder's `Converted`. |
| `by_cmdr` | true | |
| `by_system` | false | |
| `subfolder` | "" | "": the two above; else a pattern such as `{cmdr}/{date}`. |
| `filename` | `{system} {body} {date} {time}{highres}` | Also `{cmdr}` and `{subject}`. |
| `format` | "png" | Or "jpg" or "webp". |
| `quality` | 90 | 50 to 100: JPG and WebP. |
| `full` | true | False keeps only the copies and the crop, or the full size anyway when there are none. |
| `medium` | 0 | 0: none; a long edge in px up to 7680, 1920 when ticked. |
| `small` | 0 | Up to 3840, 1080 when ticked. |
| `crop` | "" | "": none; "left, top, width, height" in %. |
| `crop_px` | 0 | 0: as cut; up to 7680. |
| `copies_format` | "jpg" | Or "webp". |
| `copies_quality` | 85 | 50 to 100. |
| `original` | "keep" | Or "delete" or "move". |
| `move_to` | "" | |
| `subject_m` | 50 m | 0 to 500: a surface shot names the plant or formation this close; 0 never. |
| `clipboard` | "" | "": none; "full", "medium", "small" or "crop" after each shot. |
| `codex` | false | True also saves, in the export folder: a shot of a named plant or formation to `Biology/<genus>/<species>/<colour>` (no colour folder for a species with none) or `Geology/<group>/<name>`; a shot taken at a stellar phenomenon (dropped there, until back in supercruise) to `Phenomena/<group>/<entry>`. |
| `codex_format` | "" | "": a copy of the picture exported; "png", "jpg" or "webp": the shot converted again at full size. |
| `codex_quality` | 90 | 50 to 100: a codex JPG or WebP. |
| `codex_show` | false | True shows a random picture from those folders on the Bio/Geo checklists, Canonn's when there is none. |

## ⌨ Command-line flags

Command-line flags override the file for a single run:

| Flag | |
|---|---|
| `--radius`, `--host`, `--port` | Search radius, address and port |
| `--db PATH` | Database file (for a second copy) |
| `--config PATH` | Config file to use |
| `--write-config` | Write the settings in effect to the config file (never overwrites) |
| `--journals PATH`, `--legacy PATH` | Journal folders to follow, or older ones to import once (repeatable) |
| `--rescan` | Rebuild from the journals, keeping the Spansh cache |
| `--restore [ZIP]`, `--list-backups` | See [Backups](install.md#-backups) |
| `--simulate` | For screenshots and demos: the panels show the last known values (fuel...) as if the game were running; auto honk, auto-target, the co-pilot button, the clipboard, the in-game overlay's window, the screenshot conversion and the uploads (nothing goes to EDDN, EDSM or Inara) are off |
| `--install-service`, `--uninstall-service` | Start Outrider with your computer, or stop doing so: see [Start with your computer](install.md#start-with-your-computer) |

The environment variable `ED_JOURNALS` also names the live journal folders, separated by `:` on Linux and `;` on
Windows. It beats `[journals] live` in the file and, like it, stops the older folders being found by themselves.
`--journals` beats it.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · **Settings** · [For the curious](for-developers.md)
