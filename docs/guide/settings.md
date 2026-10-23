[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · **Settings and good to know** · [For the curious](for-developers.md)

# Settings and good to know

## ⚙️ Settings

<details>
<summary>Outrider needs no configuration — but everything can be changed.</summary>
<br>

**⚙ Settings** (top right) holds everything, in folding sections: Alerts, Voice, What is said, Sounds, Values, Risk
& warnings, Surface map, Auto honk, Uploads, In-game overlay, Display, Sharing, **Server**, Spoken lines and Questions asked.
**Find a setting…** at the top leaves only what matches the words typed (a setting's name, its help or its config key,
`speech_speed` finds the Speed slider too), in every section at once, Server's keys included; clear it and every
section is back as it was. A section's name shows all of it, and so does a block's heading inside one: "crew" shows the
whole Crew block (every member, the switches, the note on the XO), "backups" the whole Backups fold, "inara" all of
Inara's part of Uploads. A table is never cut down to one row: when a row of it matches, the whole table shows with the
matching rows marked ("tactical" shows every crew member, Tactical's row marked). Most are this browser's
own (Sharing exports them or makes them the defaults for new browsers). **Server** is the config file
itself, every key of it but the upload switches (`[eddn]`, `[edsm]`, `[inara]`: Settings → Uploads): the network and the client password, the journal folders, paths, backups, Spansh, the
Highway, the voice's AI layer and more. Saving there writes `ed_outrider.toml` (only the keys you changed; its
comments stay, and the previous file is kept as `ed_outrider.toml.bak`), and Outrider uses them from its next start:
**Restart now** beside "Saved" does that at once. A few keys take effect at once instead: `[speech] voices_loaded` and
`voices_preload` (Settings → Voice writes them too: **Keep loaded** and **Load them at start** under Voices kept
loaded, shown whenever a voice besides the main one is in use), `[speech] pad_delay` (the next docking grant) and
every `[highway] autotarget_*` key (auto-target's next run, so a sequence can be tried without restarting). **Find a setting** finds them by those words, by
"memory" or by their keys, and the crew by "crew" (all of it), "xo" or a role's name ("navigator").
The passwords (`[server]`'s and `[mcp]`'s) and the AI key are never shown, only whether they are set.

**Server**'s top row says which Outrider is running and has **Restart** and **Show log**. **Restart** stops Outrider
cleanly (a backup running finishes first) and starts it again, from any device the page answers (signed in when a
password is set); every window reconnects by itself (and says "starting" while it reads the journals). It works when
Outrider was started by `launch_outrider.sh` (started again in the same window, its setup included), `python
ed_outrider.py`, `launch_outrider.bat`, as a service (systemd starts it again) or in Docker (compose's restart policy);
otherwise the button is greyed out and says why. "Outrider has been updated: restart it"
under the header has the same button. **Show log** shows what Outrider has printed in its terminal
since it started (its last 2,000 lines, newest at the bottom, following along while it is open; problems in amber),
with **Copy** for a bug report. It works from any device, a server's too. The same lines are saved beside the database
in `outrider.log` (`data/outrider.log` by default; the older part in `outrider.log.1`). Passwords and API keys never
appear in it. Below it, **Backups** lists the backup zips with the command that restores one, and **Start with this
computer** installs Outrider as a service (a systemd user service on Linux, a Startup entry on Windows; see [Install
and run](install.md#start-with-your-computer)), or removes it; only from the browser on that PC, elsewhere it shows
the command.

**Notices.** What Outrider finds wrong when it starts (a journal folder not found, problems in the config file or the
spoken lines file, listening on your network with no password, journals on a share that shows them late, the in-game
overlay's address taken) shows as a line under the header, in every window and on the tablet, with a button where one
helps (Server settings, Show log). ✕ hides it everywhere until Outrider restarts, or until the message changes.

You can also edit the file by hand: copy `ed_outrider.toml.example` to `ed_outrider.toml` next to the script and
edit the lines you need. The example explains every key. Relative paths in it (`db`, `backup_dir`, `speech_file`, `sound_dir`,
`background_image`) are relative to the Outrider folder; the first three default to `data/ed_outrider.sqlite`, `data/backups`
and `resources/speech.json`.
`python3 ed_outrider.py --write-config` writes one with the settings in effect. Switches take a bare `true` or
`false`; a wrong value is reported at start and the default kept.

> [!IMPORTANT]
> **Windows paths in the file:** use forward slashes, `"C:/Users/you/Saved Games/..."`, or single quotes,
> `'C:\Users\you\Saved Games\...'`. In double quotes a backslash starts an escape (`"C:\Users"` is an error),
> and a file that cannot be read is ignored as a whole: every setting back at its default, with one line in the
> console saying why. Settings → Server takes paths either way and writes them correctly.

| Section | What it holds (default) |
|---|---|
| `[journals]` | `live` and `legacy` folders, when auto-detection misses them (both auto-detected when absent; setting `live` turns off legacy auto-detection: list `legacy` too, `[]` for none) |
| `[server]` | `host` ("127.0.0.1"), `port` (8025), `password` ("": none), `game_pc` ("auto": off inside a container), `update_check` (true), `allowed_hosts` ([]), `radius` (25 ly), `radius_choices` ([20, 25, 30, 40, 50]), `db` ("data/ed_outrider.sqlite"), `backup_dir` ("data/backups"), `backup_keep` (7), `backup_every_days` (1), `speech_file` ("resources/speech.json") |
| `[defaults]` | What a new browser starts with: the thresholds `unsold_warn` (50000000), `unsold_urgent` (250000000), `bio_min` (10000000), `body_highlight_level` (500000), `biology_highlight_value` (10000000), `body_max_value_include_bonus` (true), `high_gravity` (2.0 g), `module_warn` (80 %); `sounds` (true), `voice` ("en_GB-cori-medium"), `voice_fallback` ("en_GB-jenny_dioco-medium"), `speech_styles` (["business"]), `speech_profanity` (false), `speech_profanity_pct` (50), `speech_danger_business` (true), `speak_bio_signals` (true), `speak_geo_signals` (true), `speak_mapped` (false), `codex_interesting` (true), `speech_speed` (1.0), `speech_names` ("Boss, Hefay, Sir"); the surface map's `surface_alt` (1000 m), `rig_spacing` (50 m), `surface_map_min` (500 m), `surface_map_strip` (false), `rig_warn` (3500 m) |
| `[spansh]` | `concurrency` (4), `map_max_radius` (250 ly), `map_max_pages` (6), `watch_firsts` (true) |
| `[autohonk]` | `enabled` (false), `key` ("auto": read from your controls preset), `delay` (2.0 s), `hold` (6.0 s), `skip_honked` (true), `announce` (true) |
| `[speech]` | `server_player` ("auto"), for **Play speech and sounds on this PC**; `pad_delay` (5: seconds after a docking grant before your landing pad is said, Settings → Voice); `sound_dir` (none), your own alert sounds; `voices_loaded` (unset: the voices in use up to 4; a number, or "all"), how many voices besides the main one stay loaded (each about 1.6 times its file's size in memory, about 100 MB for a medium voice; one set aside waits about a second the next time it speaks); `voices_preload` (false), load them when Outrider starts instead of on their first line (both also in Settings → Voice → Voices kept loaded, used at once) |
| `[copilot]` | `enabled` (false), `device` (""), `button` (""), `hold_ms` (600), `double_ms` (400) |
| `[assistant]` | `enabled` (false), `base_url` (""), `api_key` (""), `model` (""), `timeout` (20 s), `max_rounds` (4): the voice's optional AI layer |
| `[mcp]` | `url` (this PC at `[server] port`), `max_rows` (25), `password` (""): for the MCP bridge (see Ask an AI about your game) |
| `[eddn]`, `[edsm]`, `[inara]` | `enabled` (false): written by the switches in Settings → Uploads (the only place to change them) |
| `[overlay]` | `enabled` (false), `theme` ("default"; or lcars, elite, babylon5, narn, minbari, centauri, vorlon, shadow, sith, alliance, dark), `text_size` ("normal"; a panel can have its own in Settings), `panel_scale` (100: all panels' size in %, 20 to 250, Settings' All Panels: Scale, multiplied with each panel's own Size %; text is never drawn under 9 px), `system_panel` (true), `body_panel` (true: the Target panel), `radar` (true), `strip_panel` (false), `now_panel` (false), `bio_panel` (false), `alerts_panel` (false: the page's alerts for a few seconds), `system_seconds` (0: while in supercruise there), `radar_range` (800 m), `analysis_only` ([]: the panels shown in your ship only while the HUD is in analysis mode), `hide_docked` (["system", "body", "now", "bio"]: the panels hidden while docked), `show_inactive` (false: keep showing when Elite is not the active window), `pad_diagram` (true: while docking at a starport or carrier, a diagram of where your pad is, in the Surface radar's place and on Now), `hide_on_foot` ([]: the panels hidden on foot), `hide_mouse_lock` (false: no overlay at all on foot and in the DSS, where Elite locks the mouse) (the overlay is a game-PC feature: see In-game overlay) |
| `[highway]` | `clipboard` (true), `efficiency` (60 %), `conservative` (false), `conservative_ly` (5 ly), `voice_plot` (true: the voice's "nearest station"... also plots a neutron route there past `voice_plot_ly`, 500 ly), `background_image` ("": none), `background_extent` ([-45000, 45000, -20000, 70000]), `background_opacity` (0.6); auto-target: `autotarget` (false), `autotarget_delay` (5 s), `autotarget_entry` ("type"), `autotarget_map_wait` (5 s), `autotarget_search_wait` (2 s), `autotarget_key_delay` (0.05 s), `autotarget_keys` ({}: read from your controls preset), `autotarget_search`, `autotarget_submit`, `autotarget_plot` (the galaxy map's steps: see the example file), `autotarget_dry_run` (false) |

Command-line flags override the file for a single run:

| Flag | |
|---|---|
| `--radius`, `--host`, `--port` | Search radius, address and port |
| `--db PATH` | Database file (for a second copy) |
| `--config PATH` | Config file to use |
| `--write-config` | Write the settings in effect to the config file (never overwrites) |
| `--journals PATH`, `--legacy PATH` | Journal folders to follow, or older ones to import once (repeatable) |
| `--rescan` | Rebuild from the journals, keeping the Spansh cache |
| `--restore [ZIP]`, `--list-backups` | See Backups |
| `--simulate` | For screenshots and demos: the panels show the last known values (fuel...) as if the game were running; auto honk, auto-target, the co-pilot button, the clipboard and the in-game overlay's window are off |

</details>

## 🧭 Good to know

> [!NOTE]
> **"Not on the page" means "nobody with an uploader has reported it."** Players who don't run
> EDMC or a similar tool never reach Spansh or EDSM, so a missing system is *almost* certainly
> undiscovered. A second after you arrive, the arrival star's scan settles it — and the page
> (and the voice) says which it was.

- **Exobiology guesses are possibilities, not promises.** They come from each species' known spawn
  conditions, as maintained by the [BioScan](https://github.com/Silarn/EDMC-BioScan) project, including
  its check on which star types a species appears around. Until every body is found, nothing is ruled out
  on what isn't known yet. The genus is usually right, the species sometimes not, so values show as
  "up to". The ✦ "new to your codex" mark checks the colour variant when it can be told, and names it ("✦ Grey");
  ✪ is a species or colour in your codex nowhere at all ("✪ Cobalt"), worth more effort. A Bacterium's colour
  comes from a rare element in each body's own materials, so bodies in one system can differ. Each start checks GitHub for newer rules. Settings → Display can
  leave out of Here's bio column the species you have finished and the bodies with few signals, and show each species'
  colour word in that colour ("Red" in red; this device). A finished species is one line in Here: its codex entry with what it
  pays ("📖 Bacterium Alcyoneum - Red ✦ 8.3M").
- **Values are estimates** using the community tools' formula, bonuses included (the full-scan bonus too: 1,000 cr
  per body of a system you found complete while all of it was undiscovered). An NPC crew member's cut
  comes off automatically, based on what your past sales paid.
- **Losing your ship loses your data.** Discoveries and samples that went down show as *lost* until you scan
  them again. Scanning a body you've already sold adds nothing; only mapping it still pays.
- **New versions.** Once a day Outrider asks GitHub whether a newer release is out (only that request: nothing
  about you is sent; `[server] update_check = false` turns it off). When there is one, a small **⬆ Update** pill
  appears beside the link pill (on the tablet, beside "linked"), in the theme's colours. It opens what's new and how
  to update this copy: Docker, a git clone or a downloaded release. **Skip this version** hides it until the next
  one (per browser).
- **Small things worth knowing:** the pill at the top right says whether the page is linked to Outrider:
  "linked", "linked · no game" (the game is not running), "unlinked · retrying" (after 30 s without an answer); Here's Dist, Grav, Now and Max headings sort the bodies; a genus's tooltip gives
  its colony distance; Search's mining list includes minerals you have refined, with those bodies first; the
  Settings' chips jump to its sections; and Settings → Display chooses this browser's theme, whether the header tiles fold to one line on a
  small window, and which header tiles show, on this device.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · **Settings and good to know** · [For the curious](for-developers.md)
