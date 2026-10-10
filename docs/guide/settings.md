[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · **Settings and good to know** · [For the curious](for-developers.md)

# Settings and good to know

## ⚙️ Settings

<details>
<summary>Outrider needs no configuration — but everything can be changed.</summary>
<br>

**⚙ Settings** (top right) holds everything, in folding sections: Alerts, Voice, What is said, Sounds, Values, Risk
& warnings, Surface map, Auto honk, Uploads, Display, Sharing, **Server** and Spoken lines. Most are this browser's
own (Sharing exports them or makes them the defaults for new browsers). **Server** is the config file
itself, every key of it: the network and the client password, the journal folders, paths, backups, Spansh, the
Highway, the voice's AI layer and more. Saving there writes `ed_outrider.toml` (only the keys you changed; its
comments stay, and the previous file is kept as `ed_outrider.toml.bak`), and Outrider uses them from its next start.
The password and the AI key are never shown, only whether they are set.

You can also edit the file by hand: copy `ed_outrider.toml.example` to `ed_outrider.toml` next to the script and
edit the lines you need. The example explains every key. Relative paths in it (`db`, `backup_dir`, `speech_file`) are relative to the
Outrider folder; they default to `data/ed_outrider.sqlite`, `data/backups` and `resources/speech.json`.
`python3 ed_outrider.py --write-config` writes one with the settings in effect. Switches take a bare `true` or
`false`; a wrong value is reported at start and the default kept.

> [!IMPORTANT]
> **Windows paths in the file:** use forward slashes, `"C:/Users/you/Saved Games/..."`, or single quotes,
> `'C:\Users\you\Saved Games\...'`. In double quotes a backslash starts an escape (`"C:\Users"` is an error),
> and a file that cannot be read is ignored as a whole: every setting back at its default, with one line in the
> console saying why. Settings → Server takes paths either way and writes them correctly.

| Section | What it holds |
|---|---|
| `[journals]` | `live` and `legacy` folders, when auto-detection misses them (setting `live` turns off legacy auto-detection: list `legacy` too) |
| `[server]` | `host`, `port`, `password`, `game_pc`, `update_check`, `allowed_hosts`, `radius`, `radius_choices`, `db`, `backup_dir`, `backup_keep`, `backup_every_days`, `speech_file` |
| `[defaults]` | What a new browser starts with (`voice` defaults to `en_GB-cori-medium`): thresholds (`unsold_warn`, `unsold_urgent`, `bio_min`, `body_highlight_level`, `biology_highlight_value`, `body_max_value_include_bonus`, `high_gravity`, `module_warn`), `sounds`, `voice`, `voice_fallback`, `speech_styles`, `speech_profanity`, `speech_profanity_pct`, `speech_danger_business`, `speak_bio_signals`, `speak_geo_signals`, `speak_mapped`, `codex_interesting`, `speech_speed`, `speech_names`; the surface map's `surface_alt`, `rig_spacing`, `surface_map_min`, `surface_map_strip`, `rig_warn` |
| `[spansh]` | `concurrency`, `map_max_radius`, `map_max_pages`, `watch_firsts` |
| `[autohonk]` | `enabled`, `key`, `delay`, `hold`, `skip_honked`, `announce` |
| `[speech]` | `server_player`, for **Play speech and sounds on this PC**; `sound_dir`, your own alert sounds |
| `[copilot]` | `enabled`, `device`, `button`, `hold_ms`, `double_ms` |
| `[assistant]` | `enabled`, `base_url`, `api_key`, `model`, `timeout`, `max_rounds`: the voice's optional AI layer |
| `[mcp]` | `url`, `max_rows`, `password`: for the MCP bridge (see Ask an AI about your game) |
| `[eddn]`, `[edsm]` | `enabled`: written by the switches in Settings → Uploads (the only place to change them; off by default) |
| `[overlay]` | `enabled`, `theme`, `text_size`, `system_panel`, `body_panel`, `radar`, `strip_panel`, `system_seconds`, `radar_range` (the overlay is a game-PC feature: see In-game overlay) |
| `[highway]` | `clipboard`, `efficiency`, `conservative`, `conservative_ly`, `background_image`, `background_extent`, `background_opacity`; auto-target: `autotarget`, `autotarget_delay`, `autotarget_entry`, `autotarget_map_wait`, `autotarget_search_wait`, `autotarget_key_delay`, `autotarget_keys`, `autotarget_search`, `autotarget_submit`, `autotarget_plot`, `autotarget_dry_run` |

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
| `--simulate` | For screenshots and demos: the panels show the last known values (fuel...) as if the game were running; auto honk, auto-target, the co-pilot button and the clipboard are off |

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
  leave out of Here's bio column the species you have finished and the bodies with few signals (this device).
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
- **Small things worth knowing:** the pill at the top right says whether the page is linked to Outrider ("stale"
  after 30 s without an answer; on the tablet just "linked"); Here's Dist, Grav, Now and Max headings sort the bodies; a genus's tooltip gives
  its colony distance; Search's mining list includes minerals you have refined, with those bodies first; the
  Settings' chips jump to its sections; and Settings → Display chooses this browser's theme and whether the header tiles fold to one line on a
  small window, on this device.

---

[ED Outrider](../../README.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · **Settings and good to know** · [For the curious](for-developers.md)
