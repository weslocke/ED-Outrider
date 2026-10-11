[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · **For the curious**

# For the curious

## 🔬 For the curious

Changing Outrider yourself, or with a coding agent? Start with [`docs/AGENT_GUIDE.md`](../AGENT_GUIDE.md).

<details>
<summary>What's in the box</summary>
<br>

| File | What it does |
|---|---|
| `ed_outrider.py` | The server and the journal reader |
| `static/` | The page (HTML, CSS, JS) — edit and reload; `sounds.json` holds the alert sounds; `favicon.svg` the tab icon; `tablet.css`, `themes/` and `fonts/` the tablet layout |
| `outrider/` | The modules below; those with a command line run as `python3 -m outrider.<name>` from this folder |
| `outrider/unsold.py` | The unsold-data estimate; also works on its own (`python3 -m outrider.unsold --help`) |
| `outrider/log.py` | One-line summaries of journal events for the Log view |
| `outrider/materials.py` | Material names, grades and caps, synthesis recipes, and the running inventory |
| `outrider/dock.py` | The nearest place to dock: Spansh's stations and carriers, the DSSA list, your carrier, merged and filtered |
| `outrider/cargo.py` | Cargo: the ship's hold and your carrier's (folded from the journal), the carrier's tritium, the Sell / Buy lookup and trade routes |
| `outrider/tts.py` | Spoken alerts with Piper (optional), and playing lines and sounds on the PC |
| `resources/speech.json` | The spoken lines, yours to edit (bans go in `data/speech_banned.json`) |
| `outrider/speech.py` | Loads and checks `speech.json` |
| `voice_lab.py` | A window for trying voices and lines, and downloading Piper voices |
| `outrider/button.py` | The co-pilot button (Linux, optional); `--listen` |
| `outrider/auth.py` | Sign-in for other devices: `[server] password`, session tokens, the sign-in rate limit |
| `outrider/rail.py` | The tablet's control rail: the contexts (ship, SRV, Nomad, fighter, on foot), the default buttons, their states |
| `outrider/config_edit.py` | Settings' Server settings: every config key, changed in the file in place |
| `outrider/fsd.py`, `outrider/highway.py`, `outrider/core.py` | The frame shift drive's maths and fuel model; the Highway's route helpers; small shared helpers |
| `outrider/tools.py` | The read-only questions an AI may ask (one registry, used by the MCP bridge and the voice) |
| `outrider/ask.py`, `resources/ask.json` | Questions by voice (`POST /api/ask`): the fixed phrases, then the optional AI layer |
| `outrider/mcp.py` | The MCP bridge for AI clients: `python3 -m outrider.mcp` (stdio); `--list` shows the tools |
| `outrider/honk.py` | Auto honk (Linux; Windows experimental; optional); `--show`, `--test` |
| `outrider/winkeys.py` | Key presses and the clipboard on Windows (`SendInput`), standing in for evdev |
| `outrider/target.py` | The Highway's auto-target (Linux; Windows experimental; optional); `--show` |
| `outrider/bio.py` | The exobiology predictor; `--backtest` scores it against your journals, `--update-rules` fetches the rules by hand |
| `resources/bio_rules.json` | Spawn rules, nebulae and regions from BioScan and klightspeed's region map; ExploData's colour variants are downloaded beside it into `bio_colours.json` on the first start, never shipped (`outrider/bio.py`) |
| `outrider/checklist.py` | The Exo-Biology and Geology checklists: every species and site by galactic region, with what you have done with it there |
| `outrider/codex_images.py` | The checklists' pictures: links to Canonn's screenshots and their credits, refreshed from Canonn once a day |
| `resources/geo_codex.json` | The codex's Geology and Anomalies entries and how many sites of each are reported per region, for the Geology checklist |
| `outrider/riches.py` | Road to Riches and Exomastery: Spansh's answer as route rows, what is still to do in a system, the arrival lines |
| `outrider/uploads.py` | Uploads (opt-in, off by default): the session each journal line belongs to, the outbox, what may be sent |
| `outrider/eddn.py` | EDDN: the messages a journal event becomes, and what EDDN's answer means |
| `outrider/edsm.py` | EDSM's journal upload: what a line sends to your own EDSM account, and what EDSM's answer means |
| `resources/mining_odds.json` | Planetary mining odds per ground type, from the Elite Dangerous Field Manual's survey by CMDR Grumlop (CC BY-SA 4.0); read only |
| `tests/` | `python3 -m unittest discover tests`; `node tests/page_smoke.js <port> [path to node_modules with jsdom]` for the page, against a scratch server only (it refuses 8025 and a missing port) |
| `tests/fixtures/` | Synthetic sample journals (a made-up commander and systems) for tests and scratch servers |
| `Dockerfile`, `docker-compose.yml`, `docker/` | Running Outrider as a server in Docker (see [Running as a server](install.md#-running-as-a-server-docker)); `docker/entrypoint.sh` writes the first config and checks the folders can be written |
| `launch_outrider.sh`, `launch_outrider.bat` | Start Outrider (Linux and macOS; Windows), making `.venv` and installing `requirements.txt` first when needed |
| `scripts/verify.sh` | Every check in one go: unit tests, lint, `node --check static/page.js` (the page's JavaScript syntax), the page smoke test on a throwaway server (and a clean stop) |
| `scripts/docker_bundle.sh` | A Docker release bundle in `dist/` (git-ignored): the built image saved with a compose file that runs it (no checkout or build on the server) |
| `scripts/build_codex_images.py`, `scripts/build_geo_codex.py` | Rebuild `resources/codex_images.json` and `resources/geo_codex.json` from Canonn's codex reference (read only) |
| `scripts/riches_probe.py` | A one-off probe of Spansh's Road to Riches API that saves a real answer; not part of the tests |
| `scripts/dark_icons.py` | Writes the tablet's Dark theme icons (Lucide, ISC) into `static/themes/dark.css` |
| `data/` | Your own files, git-ignored: the database, `browser_defaults.json`, `speech_banned.json`, `backups/`, `piper-voices/`, `fonts/` |
| `docs/` | Notes for contributors and their coding agents (code map, rules, journal traps, design notes, changelog); `images/` holds the screenshots |

For overlays, `GET /api/status` returns a compact JSON status and
`GET /api/status.txt?fields=system,region,fuel,target,unsold,body,sampling` one line for an OBS text
source. Both are read-only, and they are the only parts of `/api/` another web site's page may read: every
other request a browser labels as coming from another site is refused (curl and scripts send no such label and
pass).

</details>

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · **For the curious**
