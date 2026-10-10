<p align="center">
  <img src="docs/images/banner.png" alt="ED Outrider" width="800">
</p>

<p align="center">
  <b>Know what's around you, what you're standing on, and what you're carrying — while you fly.</b>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white">
  <img alt="Runs locally" src="https://img.shields.io/badge/runs-on%20your%20PC-2ea44f">
  <img alt="No account" src="https://img.shields.io/badge/account-none%20needed-6aa8ff">
  <img alt="Uploads" src="https://img.shields.io/badge/uploads-opt--in-ff8c1a">
</p>

---

ED Outrider reads your Elite Dangerous journals as you play and keeps one browser tab up to date
with the things an explorer keeps alt-tabbing to find out: **whether anyone has been to the
systems near you, what's in the one you're in, what your unsold data is worth, and whether you're
about to jump away from something you'll regret leaving.**

It runs on your own machine. It asks [Spansh](https://spansh.co.uk) (and
[EDSM](https://www.edsm.net) as a backup) what the community already knows about the systems
around you, then layers your own scans on top. Nothing is uploaded unless you switch on sharing with
[EDDN and EDSM](docs/guide/uploads.md), as EDMC does. A tablet can sit beside you as a cockpit
display ([ED Outrider for Android](https://github.com/weslocke/ED-Outrider-Android), or any browser), and Outrider can
also run 24/7 on a home server in Docker.

<p align="center">
  <img src="docs/images/overview.png" alt="The Overview: the neighbourhood on the left, the system you're in on the right" width="900">
</p>

## ✨ At a glance

| | |
|---|---|
| 🔭 **Find the undiscovered** | Every known system within 25 ly is listed. If the galaxy map shows one that *isn't* on the page, nobody with an uploader has been there. |
| 🔊 **Hear it before you jump** | Target a system and get a fanfare if it's a brand-new discovery, a cheerful note if it's known but unscanned, a thud if it's been done. |
| 🪐 **See the whole system** | Every body: value, gravity, atmosphere, rings and hotspots, curiosities, and which exobiology species it could hold — before you probe or land. |
| ⚠️ **Don't leave money behind** | Target onward with mapping or exobiology worth your while still undone and the page says so, out loud if you like. Ordinary systems stay quiet. |
| 💰 **Know what's on board** | Unsold cartographics and exobiology in credits, bonuses included, and your unsold 🏁 first discoveries. Dock somewhere that buys it and it tells you to sell. |
| 🌿 **On the ground** | What is left to sample on the body, a countdown to the next colony, and a warning when a run elsewhere would be discarded. |
| ⛽ **Fuel you can trust** | Jumps left at max range and at your pace, laden range, fuel per hop, how scoopable your recent stars have been, and a nudge to top up before a dry stretch. |
| 🧭 **Decide where to go** | Unfinished systems nearby, the nearest buyers for your data, bookmarks and a next stop, stellar phenomena, and a search across Spansh. |
| 🛣 **Neutron Highway** | Plot a neutron route with Spansh for any ship you have flown; Outrider follows it as you fly and says the next stop. |
| 💰 **Road to Riches, Exomastery** | Plot a [Spansh Road to Riches](https://spansh.co.uk/riches) or [Expressway to Exomastery](https://spansh.co.uk/exobiology) route in the Plot Route tab; Outrider follows it as you fly, shows what is left to scan and map in each system from your journal, and says it on arrival. |
| 📦 **Cargo and your carrier** | Your hold with what you paid, and your fleet carrier's cargo and tritium tracked from your journal, with no Frontier sign-in. |
| 📍 **Nearest place to dock** | The nearest stations and fleet carriers you can land at and use (UC, Vista, repair...), from Spansh and the Deep Space Support Array's carriers, with how old each report is; one click plots there, or ask "nearest Vista" out loud. |
| 💱 **Trading, kept small** | Where to sell or buy what you carry, from Spansh's markets, and Spansh's trade planner as a route Outrider follows and talks you through. |
| 📜 **Your logbook** | Every journal event in a searchable log, every exobiology sample and what became of it, and a schematic of the system. |
| 📈 **The long view** | Each trip from sale to sale with what it actually paid, what each ship loss cost, your best finds, ranks and career statistics. |
| 🗣 **A voice with personality** | A natural neural voice, down to business, sarcastic or sweet, briefing you on arrival and warning before you leave something unfinished. |
| ⛏️ **Rhino mining** | A heading-up surface map on Now with your rigs, sample points and ship, and every collection kept per body. |
| 📱 **A tablet in the cockpit** | Every page in a touch layout with nine themes, alerts as banners, game buttons on a control rail, and the voice on the tablet if you like. |
| 🎙️ **Ask out loud** | "Hey Vespa, status report": answered in the voice from what Outrider knows, with an optional AI for anything else. |
| 🎯 **Automation (game PC; Linux, Windows experimental)** | Auto honk fires the Discovery Scanner on arrival, auto-target targets the next route system after a supercharge, and one HOTAS button (Linux) targets the next route system with a tap, gives a status report with a double tap and hushes with a hold. |

## 🚀 Getting started

```bash
./launch_outrider.sh   # Linux, Python 3.11 or newer
```

On **Windows**, install [Python](https://www.python.org/downloads/) 3.11 or newer and double-click
**`launch_outrider.bat`**. Then open **<http://127.0.0.1:8025/>** and go fly. The first run sets up a Python
environment; after that it starts at once. On a home server, a Docker image runs it around the clock (the game-PC
automation is off there).

Everything about installing, the optional parts, Docker, other devices and backups is in
**[Install and run](docs/guide/install.md)**.

> [!WARNING]
> Keep Outrider on your home network: never expose it to the internet. Use a VPN to reach it away from home.

## 📖 The guide

| Page | What's in it |
|---|---|
| **[What's new](docs/guide/whats-new.md)** | What each release brings: new things to try, settings worth a look, anything to know before updating |
| <a id="-running-as-a-server-docker"></a><a id="-other-devices-on-your-network"></a><a id="-backups"></a>**[Install and run](docs/guide/install.md)** | Getting started in full (Linux, Windows, the optional parts), running as a server in Docker, other devices on your network, backups |
| <a id="-the-views"></a><a id="-the-surface-map"></a>**[The views](docs/guide/views.md)** | Every tab (Nearby, Here, Map, History, Bio/Geo with the Exo-Biology and Geology checklists, Log, Materials, Search, My firsts, Now), the header tiles, the desktop themes, the surface map |
| <a id="-the-neutron-highway"></a>**[Plot Route](docs/guide/plot-route.md)** | The Neutron Highway (exact and neutron plotters), Road to Riches, Exomastery and trade routes, following a route, 🎯 and auto-target, the nearest place to dock |
| <a id="-cargo-and-your-carrier"></a><a id="-trading"></a>**[Cargo and trading](docs/guide/cargo-and-trading.md)** | Your hold and your fleet carrier's (tracked, no Frontier sign-in), the carrier's tritium, Sell / Buy from Spansh's markets, trade routes |
| <a id="-alerts"></a><a id="-the-voice"></a><a id="-ask-outrider-by-voice"></a><a id="-ask-an-ai-about-your-game"></a>**[Voice and alerts](docs/guide/voice-and-alerts.md)** | What Outrider tells you and when, the voice and its personalities, editing and banning lines, asking by voice, asking an AI |
| <a id="-auto-honk"></a><a id="-the-co-pilot-button"></a>**[Automation](docs/guide/automation.md)** | Auto honk and the co-pilot button (on the game PC) |
| <a id="-on-a-tablet"></a>**[On a tablet](docs/guide/tablet.md)** | The touch layout at /tablet, its nine themes, the control rail, the Android app |
| **[Uploads](docs/guide/uploads.md)** | EDDN and EDSM (opt-in, off by default): what is sent and never sent, one uploader at a time, EDSM's key |
| <a id="-settings"></a><a id="-good-to-know"></a>**[Settings and good to know](docs/guide/settings.md)** | Every setting and config key, and the things worth knowing (what "not on the page" means, estimates, updates) |
| <a id="-for-the-curious"></a>**[For the curious](docs/guide/for-developers.md)** | What's in the box, the code's layout, the status API for overlays; contributors start with the agent guide |

The project's history is in the [changelog](docs/CHANGELOG.md). Contributors and their coding agents start with the
[agent guide](docs/AGENT_GUIDE.md).

---

## Credits and licence

| What | From | Licence | In Outrider |
|---|---|---|---|
| Systems, bodies, stations, routes | [Spansh](https://spansh.co.uk), [EDSM](https://www.edsm.net) | their terms | looked up as you play |
| Exobiology spawn conditions, nebulae | the community's work, gathered by the Canonn Research Group, maintained in [EDMC-BioScan](https://github.com/Silarn/EDMC-BioScan) | GPL v2 or later | `resources/bio_rules.json`, refreshed when it changes |
| Colour variants | [EDMC-ExploData](https://github.com/Silarn/EDMC-ExploData) | GPL v2 | downloaded on the first start, not shipped |
| Colony distances | the game (the Genetic Sampler shows them) | | `outrider/bio.py` |
| Galactic region map | [klightspeed's EliteDangerousRegionMap](https://github.com/klightspeed/EliteDangerousRegionMap) | MIT | in `resources/bio_rules.json` |
| Planetary mining odds | CMDR Grumlop's survey, [Elite Dangerous Field Manual](https://edfieldmanual.com/index.php?title=Module:Data/SurfaceMiningProspecting) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | `resources/mining_odds.json`, unchanged |
| Geology sites; checklist pictures | [Canonn](https://canonn.science)'s codex records and screenshots | Canonn's | site counts in `resources/geo_codex.json`; pictures linked, never copied, credited to the commander who took each |
| EDDN and EDSM upload rules | [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDCD) | GPL v2 or later | followed, with EDCD's notice in `outrider/eddn.py` |
| The overlay window's code | [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) | GPL v3 | adapted, with its notice: `outrider/overlay_tracking.py`, `outrider/overlay_window.py` |

The tablet themes' emblems (`static/emblems/`, each under the terms in its `CREDITS.txt`, not the GPL): the Explorer
Elite badge under Frontier's media usage rules; the Babylon 5 emblems (© Warner Bros.), public-domain redrawings from
the Babylon 5 Wiki; the Sith emblem, Gameposo's, vectorised by Marnanel (Wikimedia Commons, CC BY-SA 4.0); the Rebel
Alliance emblem, a public-domain Wikimedia Commons file (both Lucasfilm trademarks). Unofficial, non-commercial fan use.

ED Outrider is free software under the [GNU GPL v3 or later](LICENSE).

<p align="center"><sub>
ED Outrider was created using assets and imagery from Elite Dangerous, with the permission of Frontier Developments
plc, for non-commercial purposes. It is not endorsed by nor reflects the views or opinions of Frontier Developments and
no employee of Frontier Developments was involved in the making of it.
</sub></p>
