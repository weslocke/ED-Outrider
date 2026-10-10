#!/usr/bin/env python3
"""
ed_outrider.py -- ED Outrider: a live web page for exploring Elite Dangerous: what is around you, what you have
found, and what is still on board.

Reads every Elite Dangerous journal into a local SQLite database (visited systems, jump history,
your scans, DSS ring hotspots, first discoveries, mapping, footfalls, exobiology sampling, codex
entries, sales, deaths, fuel, your fleet carrier), then tails the live journal and Status.json.
Whenever you arrive somewhere new it asks Spansh for every known system within --radius light
years (EDSM as a fallback when Spansh is down) and serves http://127.0.0.1:8025/ with:

  Nearby     known systems sorted by distance / name / value, with scan status, main star and
             scoopability, body and ring icons, notable bodies (ELW/WW/AW/terraformable), Spansh's
             credit estimate, your 🏁 first-discovery markers (sold / unsold / lost), bookmarks
  Here       every body in the current system: value as scanned and if mapped, gravity, atmosphere,
             bio genera with 0/3..3/3 sampling progress and which species they could be (outrider/bio.py
             spawn rules plus BioScan's colour check, with credit values; "one of these" with a range
             when a body has fewer signals than possible genera), ring hotspots, codex entries,
             curiosities (ringed landables, close orbits, planet pairs...), your firsts, planetary mining
             locations (⛏, with the EDFM survey's odds per ground and what your SRV mined there); as a
             list, a tree in orbital order, or a schematic of stars, planets, moons and barycentres
  Bio/Geo    My Samples (every exobiology sample run, aboard / sold / lost, with value, and codex entry), the
             Exo-Biology checklist and the Geology one, by galactic region
  Bookmarks  systems you starred, with a note each
  Search     local database or Spansh: star classes (scoopable shortcut), planet types, ring types,
             ring hotspot minerals, unfinished exobiology, planetary mining locations (local only, optionally
             by likely mineral, or a mineral your SRV refined, those bodies first); and any system by name
             (GET /api/find)
  Map        3D canvas of the neighbourhood with your path, first discoveries, boost stars
             (neutron / white dwarf) and your carrier; fills the window; left-drag rotates,
             right-drag moves, the wheel zooms
  Plot Route a route plotted with Spansh and followed as you fly: the Neutron Highway (the exact plotter from a
             flown ship's Loadout, or the neutron plotter from a range), and in one slot of its own a Road to Riches,
             an Expressway to Exomastery (outrider/riches.py) or a trade route (outrider/cargo.py: station to station,
             what to sell and buy); next stop, detour, back on it, complete: the
             jump list, a top-down map on the galactic regions (or your own galaxy image), a line under the tiles on
             Overview / Nearby / Here, 🎯 on any route system, "📍 Nearest…" (the nearest station or fleet carrier
             you can dock at and use: Spansh, the DSSA's carriers, your own; outrider/dock.py), the next system put on
             the desktop clipboard (wl-copy / xclip, or Windows') and said on arrival; optionally (Linux, Windows experimental;
             off by default) the
             next system targeted after a supercharge, or on demand with 🎯 Target next / ⟳ Retry, by key
             presses in the galaxy map (outrider/target.py, the same keyboard as auto honk); the drive
             maths in outrider/fsd.py, the route helpers in outrider/highway.py; [highway] in the config
  History   your sessions: jumps, light-years, firsts, mapped, footfalls, samples, codex, plus an
             all-time row and the Last session card; trips from sale to sale (paid vs estimated, what
             each death cost including exobiology), your most valuable finds; exports
  Log        every journal event with a one-line summary (outrider/log.py), filtered by category, time and
             text, read straight from the journal files and updated live
  Materials  Cargo: your ship's hold with what you paid and your fleet carrier's hold, tracked from sell orders and
             the journal (outrider/cargo.py), with Sell / Buy from Spansh's markets; then
             engineering materials against their caps, and how many FSD injections and other
             syntheses (limpets, SRV refuel and repair, Rhino rig restocks) you can make (outrider/materials.py);
             Mining sites: each body your SRV mined, with minerals and tons, saved rig spots, mining locations
  My firsts  unsold first discoveries, and visited systems nearby with work worth going back for
             (Left behind, including bio signals never probed); a daily Spansh check flags unsold
             firsts someone else has scanned since ([spansh] watch_firsts)
  Now        big text for a second monitor (also ?mode=now): the system, the target, fuel, what to do
             next here, the discovery count, the unreported horizon, the data at risk, this session, the
             last lines spoken and a button bar; ↗ opens it in its own window, which stays on Now. On a planet (below
             surface_alt, or down) a heading-up surface map: you, the ship, bio sample rings, Rhino rigs (marked
             by the co-pilot button; collections placed from Status.json), saved sites and mining locations

The header shows the current system (coordinates, visit count), the commander (credits at login plus
sales since, ship), fuel (jumps left simulated from your ship's mass and your own jumps, the laden range, how
scoopable your recent stars were, jumps since the last scoop and FSD boosts on hand), core modules under
module_warn health, your
carrier (distance, UC / Vista services, its tritium and 500 ly jumps while tritium is on a sell order; decommissioning
in red), the latest codex first, unsold firsts, and the unsold
cartographic + exobiology estimate from outrider/unsold.py. Targeting a system plays a sound: fanfare if
neither Spansh nor EDSM has heard of it, upbeat if it is not fully scanned, thud if you have been
there or it is fully scanned, plus an alert if you are leaving unfinished work behind. Arriving
somewhere undiscovered is announced by the voice (a sound only corrects a targeting call that was
wrong). Desktop notifications are optional (🔔 alerts). A link pill says whether the page is linked to Outrider
(linked / stale / no link), and the last line said sits beside the header's icons with ▶ to hear it again.

Alerts can be spoken (🗣): with Piper (outrider/tts.py; Cori by default, any Piper voice from Settings > Voice > More
voices) when it is installed, else the browser's voice (never alongside Piper: a line Piper cannot say is not said;
while the browser holds audio back until a click, a red "Click Here To Allow Audio" pill asks for it), in
the personalities of resources/speech.json (outrider/speech.py: business, sarcastic, sweet, with swearing versions at
a chosen rate), calling you by the names you choose. Besides the alerts the voice can say signal
counts as the FSS finds them, where the frame shift drive is taking you (said in the hyperspace tunnel, not
over the game's countdown call) and whether that star is scoopable, brief you on arrival, after the FSS, on approach and on leaving a body, welcome you back
after a break, debrief a ship loss and recap the session on quit, and it names the galactic region you cross into. Lines you tire of can be
banned from the Spoken lines list (data/speech_banned.json). Lines go through a priority queue in
one browser window (danger first; the queue clears when the FSD charges). voice_lab.py is a separate
window for trying voices and lines. Optionally the server plays the speech and the alert sounds itself
(POST /api/say/play, /api/sound/play; static/sounds.json, or your own <name>.wav files from [speech] sound_dir,
served to the page by GET /api/sound/file/{name}), so no click on the page is needed; the next line is
synthesised while one plays (POST /api/say/prefetch), and Volume is set per device. When Outrider stops
answering for 30 s, the page says "Lost contact with Outrider" in the Piper voice (made in advance; else the alert
sound). Auto honk (outrider/honk.py, optional; Linux, Windows experimental) holds Primary Fire's
keyboard binding on arriving by hyperspace so the Discovery Scanner fires, and says how many bodies
it found. The voice can be hushed for a while (the page, or POST /api/hush: the state is the server's, so
every window and device sees it), and a co-pilot button (outrider/button.py, Linux, optional, read-only) asks the
speaking window for a status report or a hush until the next jump, and a tap in the ship targets the next route system.

Other devices: /tablet is the same pages in a touch layout with nine themes (static/tablet.css, static/themes/), a
control rail of game buttons (outrider/rail.py) and, ticked in its Settings, the voice and sounds on the tablet itself;
ED Outrider for Android (a separate repository) wraps it with a wake word that asks POST /api/ask (outrider/ask.py:
fixed phrases, then an optional OpenAI-compatible AI with the read-only tools of outrider/tools.py). [server] password
signs devices in (outrider/auth.py). python3 -m outrider.mcp serves the same read-only tools to an AI client over MCP.
In Docker ([server] game_pc auto: off in a container) everything that presses keys, reads devices or plays on this
PC is off and left out of the pages; see docs/guide/install.md and scripts/docker_bundle.sh.

The database backs itself up (a dated zip, the newest kept) at start when a day old and after quitting
the game (each copy checked with quick_check and the zip with testzip before older ones rotate out), and
every live journal is archived once into data/backups/journals/; --restore puts a zip back and --list-backups
lists them. Every request goes through a Host/Origin guard (request_guard), and a GET another site's page
sends (Sec-Fetch-Site) is refused except OPEN_GETS (/api/status and /api/status.txt, for overlays, which alone
send Access-Control-Allow-Origin: *), so another web site cannot
read the journals or trigger actions.

Body data is Spansh's merged with your own journal scans, so what you scan shows up immediately,
even for systems Spansh has never heard of. Your own data wins where both exist. Spansh bodies last reported by a pre-Odyssey client are marked
"old data" where thin-atmosphere worlds may hold unsampled life.

Each row shows how much is known about the system:

  unreported    only seen in your own NavRoute.json, nobody has reported any bodies
  no scan data  the system is known (route plot or a jump) but nothing scanned
  NN% scanned   some bodies known, fewer than the system's FSS body count
  fully scanned every body known
  N mapped      bodies DSS-mapped, as far as your own journal knows (Spansh doesn't record it)

A system that the galaxy map shows within range but this page does not list is one nobody has
reported to Spansh or EDSM -- almost certainly undiscovered.

Journal folders are auto-detected (Windows save folder, every Steam library's Proton prefix,
mounted Windows drives for older journals); --journals / --legacy / ED_JOURNALS override. Files
are remembered by path and byte offset, so a restart only reads what is new; legacy folders are
imported once. Pass --rescan to rebuild everything from scratch. --simulate (screenshots, demos) shows the
panels as if the game were running, with the last known values, and keeps every key-pressing part off.

Settings come from ed_outrider.toml next to this script (see ed_outrider.toml.example; make one with
--write-config); flags and ED_JOURNALS override it, and nothing is required. Relative paths in it are
relative to this folder. The layout: outrider/ the modules, resources/ the shipped data (bio_rules.json,
mining_odds.json, speech.json), data/ your own files (the database, browser_defaults.json,
speech_banned.json, backups/, piper-voices/; git-ignored), docs/ the notes and screenshots.
The page itself is static/page.html + page.css + page.js next to this script (edit and reload).
Tests: scripts/verify.sh runs them all (python3 -m unittest discover tests, one subject file per
tests/test_*.py, shared fakes in tests/support.py); python3 -m outrider.bio --backtest scores the bio rules against
your journals.

Requires Python 3.11+ (for reading the config file; 3.9/3.10 need `pip install tomli`) and aiohttp;
piper-tts (spoken alerts) and evdev (auto honk, Linux; Windows needs nothing extra) are optional, as are wl-copy or
xclip (the Highway's clipboard copy, Linux).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import functools
import hashlib
import io
import json
import math
import mimetypes
import os
import random
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
from glob import glob, escape as glob_escape

from aiohttp import ClientError, ClientSession, ClientTimeout, web

import outrider  # the package beside this script: ROOT, RESOURCES_DIR, DATA_DIR and the modules below
try:  # the unsold-data estimate (and journal-folder detection)
    import outrider.unsold
except ImportError:
    outrider.unsold = None
try:  # exobiology spawn rules: which species a body could host
    import outrider.bio
except ImportError:
    outrider.bio = None
import outrider.materials  # engineering materials and synthesis recipes (no dependencies)
import outrider.cargo      # the ship's hold and your carrier's, folded from the journal (no dependencies)
import outrider.dock       # the nearest place to dock: stations and carriers from Spansh, the DSSA list, your carrier
import outrider.tts        # spoken alerts; Piper itself is optional (the page falls back to browser speech)
import outrider.speech     # the words for spoken alerts, per personality (resources/speech.json)
import outrider.honk       # auto honk: holds Primary Fire on arrival (optional; Linux with evdev, Windows experimental)
import outrider.target     # the Highway's auto-target: targets the next route system in the galaxy map (same keyboard)
import outrider.button     # the co-pilot button: tap, double tap, hold on a HOTAS button (optional; Linux, read-only)
import outrider.auth       # [server] password: sign-in for devices on the network (the tablet and its app)
import outrider.rail       # the tablet's control rail: contexts, default sets, button states
import outrider.ask        # questions by voice (POST /api/ask): fixed phrases, then an optional AI layer
import outrider.config_edit  # the Settings dialog's Server settings: every config key, edited in place
import outrider.mcp        # the MCP bridge's [mcp] settings (the bridge itself runs as python3 -m outrider.mcp)
import outrider.uploads    # EDDN / EDSM uploads (opt-in): the session, the live gate, the outbox
import outrider.eddn       # EDDN's messages from journal events, and what its answers mean
import outrider.edsm       # EDSM's journal upload: the events with where you were, and what its answers mean
import outrider.checklist  # the exobiology checklist: every species by region, with your state (pure)
import outrider.codex_images  # the checklists' pictures: Canonn's links and credits, refreshed once a day
from outrider.core import iso_ts, ts_seconds   # journal timestamps
from outrider.fsd import (   # the frame shift drive's maths: range, fuel per jump, the fuel model, fleet figures
    FSD_RANGE_MODS, GUARDIAN_BOOST, conservative_optimal_mass, conservative_range, fleet_figures, fleet_range, fsd_range,
    fsd_supercharge, fuel_model, hop_fuel, jumps_left, max_fuel_for_jump,
)
from outrider.highway import (   # the Neutron Highway's route helpers and the desktop clipboard
    HIGHWAY_BG_TYPES, Clipboard, HighwayError, highway_bg_file, highway_match, highway_refuel_in, highway_rows,
    highway_text, splice_route, stand_in,
)
from outrider.cargo import trade_counts, trade_done_text, trade_left, trade_rows, trade_text   # the slot's third type: trade routes
from outrider.riches import (   # Road to Riches / Exomastery: Spansh's survey routes (systems with valuable bodies / life)
    RichesError, body_value, exo_left, exo_text, exo_todo, norm_name, riches_match, riches_rows, riches_text, splice_survey,
    todo,
)
try:  # one-line summaries of every journal event, for the Log view
    import outrider.log
except ImportError:
    outrider.log = None


# Which deaths cost the ship (and its cartographic data): shared with outrider.unsold so the
# header and the per-system markers can never disagree about the same death.
SHIP_SURVIVED_OPTIONS = outrider.unsold.SHIP_SURVIVED_OPTIONS if outrider.unsold else ("recover", "rejoin")
SHIP_LOSS_SQL = ("coalesce(option, 'rebuy') NOT IN (" +
                 ",".join("'%s'" % o for o in SHIP_SURVIVED_OPTIONS) + ")")

# --------------------------------------------------------------------------
# Journal locations. LIVE_DIRS are tailed; LEGACY_DIRS are imported once.
# --------------------------------------------------------------------------

# Auto-detected (see outrider.unsold.find_journal_dirs); --journals / --legacy / ED_JOURNALS override.
LIVE_DIRS, LEGACY_DIRS = outrider.unsold.find_journal_dirs() if outrider.unsold else ([], [])

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))   # the repository: relative config paths start here
DB_PATH = os.path.join(outrider.DATA_DIR, "ed_outrider.sqlite")   # data/ holds your own files (git-ignored)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "ed_outrider.toml")   # optional; see ed_outrider.toml.example

SPANSH_SEARCH = "https://spansh.co.uk/api/systems/search"
SPANSH_DUMP = "https://spansh.co.uk/api/dump/{id64}"
SPANSH_BODY_SEARCH = "https://spansh.co.uk/api/bodies/search"
SPANSH_STATION_SEARCH = "https://spansh.co.uk/api/stations/search"
DOCK_CACHE_S = 120   # s: the Nearest finder reuses its last search this long (a filter change re-filters it)
# Spansh's commodity names (its min_max keys): the Sell / Buy lookup asks by them; cached a week (meta spansh_commodities)
SPANSH_COMMODITIES = "https://spansh.co.uk/api/stations/field_values/commodities"
COMMODITIES_MAX_AGE_S = 7 * 86400
# The Deep Space Support Array's carrier list (EDAstro, read only): asked for when the Nearest finder opens, at most
# hourly and conditionally; the last copy is kept (meta dssa). verify.sh points it at a closed port.
DSSA_URL = outrider.dock.DSSA_URL
# The Neutron Highway's plotters: each answers {job} and the route is fetched from the results URL once done
SPANSH_ROUTE = "https://spansh.co.uk/api/route"                  # the neutron plotter: from, to, range, efficiency
SPANSH_GENERIC_ROUTE = "https://spansh.co.uk/api/generic/route"  # the exact plotter: the ship's figures, fuel too
SPANSH_RESULTS = "https://spansh.co.uk/api/results/{job}"
# Road to Riches: answers {job} like the plotters above; the route (systems with their bodies) is in the results
SPANSH_RICHES = "https://spansh.co.uk/api/riches/route"
SPANSH_EXO = "https://spansh.co.uk/api/exobiology/route"   # Expressway to Exomastery: the same job, bodies with species
SPANSH_TRADE = "https://spansh.co.uk/api/trade/route"      # the trade planner: the same job, station-to-station hops
TRADE_PLOT_TIMEOUT = 600    # s: the trade planner is slow (4 hops from Sol took 136 s on 2026-10-07)
RICHES_METHOD = "POST"      # form fields (checked against the live API 2026-10-06; scripts/riches_probe.py checks it again)
RICHES = {"radius": 25, "max_results": 25, "max_distance": 50000, "min_value": 100000,   # defaults of the plot form
          "use_mapping_value": True, "avoid_thargoids": True, "loop": False}
RICHES_AHEAD = 100          # route systems GET /api/riches lists from where you are...
RICHES_DONE = 10            # ...and done systems above them (the most recent)
SPANSH_SYSTEM_NAMES = "https://spansh.co.uk/api/systems/field_values/system_names"   # system names as you type
SPANSH_SYSTEM_SEARCH = "https://spansh.co.uk/api/search/systems"   # ?q=name: {results: [{id64, name, x, y, z}]}
HIGHWAY = {"clipboard": True, "autotarget": False, "autotarget_delay": 5.0, "efficiency": 60,   # [highway] defaults
           "conservative": False, "conservative_ly": 5.0,
           # auto-target's key sequence (outrider/target.py): how the name goes in, the waits, per-step key overrides,
           # the search, submit and plot-route steps (found in game 2026-10-02) and a dry run that only logs
           "autotarget_entry": "type", "autotarget_map_wait": 5.0, "autotarget_search_wait": 2.0,
           "autotarget_key_delay": 0.05, "autotarget_keys": {}, "autotarget_plot": list(outrider.target.DEFAULT_PLOT),
           "autotarget_search": list(outrider.target.DEFAULT_SEARCH), "autotarget_submit": list(outrider.target.DEFAULT_SUBMIT),
           "autotarget_dry_run": False}
AUTOTARGET_TEST_COUNTDOWN = 5   # s: the Plot Route tab's "test now": time to click into the game before the sequence
AUTOTARGET_HONK_WAIT = 60       # s an auto-target waits for an auto honk on the same arrival to finish (honk first)
AUTOTARGET_DANGER_WAIT = 60     # s after an arrival a run waits for the game's own in-danger flag to clear (see arrival_danger_until)
# The Highway map's optional background image ([highway] background_image): only the configured file is served
# (GET /api/highway/background), and only one of these image types, checked by its first bytes too (no SVG: it can
# carry script). The extent [xmin, xmax, zmin, zmax] in ly says where its edges are in the galaxy's plane; the
# default is the bounds the community's top-down galaxy images use (EDAstro's charts, the galaxy map texture):
# X -45000 to 45000, Z -20000 to 70000 (40 ly per pixel at 2250 px, Sol at pixel 1125, 1750).
HIGHWAY_BG_EXTENT = [-45000.0, 45000.0, -20000.0, 70000.0]
HIGHWAY_BG_OPACITY = 0.6
HIGHWAY_POLL_S = 1.5        # s between two asks for a plot job's result (Spansh politeness: 1-2 s)
HIGHWAY_PLOT_TIMEOUT = 180  # s a plot may take before we give up on it
HIGHWAY_AHEAD = 200         # route rows GET /api/highway lists ahead of you...
HIGHWAY_DONE = 20           # ...and done rows above them (the most recent)
HIGHWAY_LIVE_S = 120        # s: an arrival or a supercharge older than this is catch-up (no clipboard, no auto-target)
HIGHWAY_SUGGEST_CACHE = 200  # system-name suggestions kept (per typed prefix)
HIGHWAY_HEAVY_SLACK = 0.5    # t: fuel over the most the next jump allows by more than this is "too heavy" (Spansh plans
#                              some jumps right at the limit, so a hair over is the model's error, not yours)
HIGHWAY_HEAVY_EVERY_S = 3.0  # s between two looks at it while the fuel changes in a route system (scooping)
HIGHWAY_CONSERVATIVE_MAX = 50.0   # ly: the largest conservative margin taken
GEO_CODEX_FILE = os.path.join(outrider.RESOURCES_DIR, "geo_codex.json")
CODEX_IMAGES_START = 120     # s after the server starts before the picture list is first refreshed
CODEX_IMAGES_EVERY = 86400   # s between refreshes of the picture list (Canonn's codex reference, about 650 KB)
CODEX_IMAGES_RETRY = 3600    # s to wait after a failed refresh   # the geology checklist's entries (scripts/build_geo_codex.py)
HIGHWAY_STAND_IN_LY = 150.0   # ly: how far around an end Spansh does not know yet its stand-in is looked for
NEAR_BODY_ALT = 5000         # m: below this over a body in your ship, the on-body strip shows its bio card
LEASE_EVERY_S = 60           # s: this instance's upload lease rewritten, the others' read, EDMC's switches checked
BIO_TAGS_SHOWN = 40          # the surface map draws at most this many tagged plants (nearest first)
SELLER_REFRESH_LY = 100      # look for the nearest places to sell again after moving this far
SELLER_REFRESH_S = 6 * 3600  # ...or this long (carriers move)
EDSM_SYSTEM = "https://www.edsm.net/api-v1/system"
EDSM_SPHERE = "https://www.edsm.net/api-v1/sphere-systems"
EDSM_BODIES = "https://www.edsm.net/api-system-v1/bodies"   # ?systemName=: {name, bodyCount, bodies: [{type...}]}
BOOST_STARS = ["Neutron Star"] + [f"White Dwarf ({c}) Star" for c in
                                  ("D", "DA", "DAB", "DAZ", "DAV", "DB", "DBZ", "DBV", "DQ", "DC", "DCV")]
SPANSH_PAGE = 500          # largest page size the search endpoint honours
SPANSH_MAX_PAGES = 10
SPANSH_CONCURRENCY = 4     # body-detail fetches after an arrival
SPANSH_INTERACTIVE = 2     # separate lane for target/body lookups so they never queue behind the above
LONG_POLL_SECONDS = 25     # s: how long /api/nearby holds a request with nothing new before answering 204
EDSM_SPHERE_MAX = 100     # ly: EDSM's sphere-systems answers no further out ("radius", max 100, in its API docs)
ON_DEMAND_MAX_AGE = 86400  # s: a system fetched for Search/bookmarks/pins is fetched again after a day
UNSOLD_LOG = 3             # recent unsold estimates kept to stamp a sale with the one made before it
NO_DUMP_RETRY = 3600       # s: a dump 404 for a system whose search lists bodies is asked again after this
DUMP_MAX_TRIES = 5         # body-detail fetches for one system before we stop asking (this stay)
USER_AGENT = "ED Outrider (personal exploration helper)"

POLL_SECONDS = 1.0
CARRIER_RETRY_S = 600      # s: a carrier system Spansh could not place is looked up again after this
RUN_ID = int(time.time())  # identifies this server process to the page

# 3D map: how far out it can look, and how many Spansh pages (of 500 systems) it will fetch.
# Spansh returns at most 10,000 systems per search; near the bubble each page is several MB.
MAP_MAX_RADIUS = 250
MAP_MAX_PAGES = 6

# The firsts watch: a background check of your unsold first discoveries on Spansh, to see whether someone else has
# scanned them since: systems never checked first, most valuable first, then the one checked longest ago, so all of
# them get their turn when more are due than the day's cap (firsts_watch_due). Politely: one dump request every 10 to
# 30 s at most, each system at most once a day while its firsts are under a month old and once a week after that or
# once someone else has been seen (that never clears), at most FIRSTS_WATCH_DAY_CAP checks a day (a failed one
# included: that system then waits a day), and none in the first minutes after a start (the arrival's own fetches go
# first). Systems whose only unsold firsts are first-mapped bodies are left out (firsts_watched).
WATCH_FIRSTS = True
FIRSTS_WATCH_GAP = (10.0, 30.0)   # s between two checks (a random pick in this range)
FIRSTS_WATCH_EVERY = 86400        # s: a system is checked again after this
FIRSTS_WATCH_SLOW = 7 * 86400     # s: ... or after this, once seen by others or once its firsts are FIRSTS_WATCH_YOUNG old
FIRSTS_WATCH_YOUNG = 30 * 86400   # s after your first scan there
FIRSTS_WATCH_DAY_CAP = 150        # checks in any 24 h, however many unsold firsts there are
FIRSTS_WATCH_START = 120          # s after the server starts before the first check
FIRSTS_WATCH_BACKOFF = 600        # s to wait after a failed request (Spansh down, a timeout)
# The update check ([server] update_check): GitHub's latest release against the running version
RELEASES_LATEST = "https://api.github.com/repos/weslocke/ED-Outrider/releases/latest"
RELEASES_PAGE = "https://github.com/weslocke/ED-Outrider/releases/latest"
UPDATE_CHECK_START = 60           # s after the server starts before the first check
UPDATE_CHECK_EVERY = 86400        # s between checks
UPDATE_CHECK_RETRY = 3600         # s to wait after a failed check (offline, GitHub down or throttled)
FIRSTS_OWN_GRACE = 120            # s: a body Spansh updated this soon after your own scan or map of it is your own upload

# Unsold data: recompute at most this often while the journal is growing (a full pass is ~1 s).
UNSOLD_MIN_SECONDS = 15
# s with no further sale page before a sale's leftovers are said (a 'Sell all' is still going): Universal
# Cartographics writes its 50-system pages 7 to 67 s apart (one player's 18 multi-page sales, 2023-2026)
SALE_QUIET_S = 90
SALE_LEFT_GIVE_UP_S = 300  # s after a sale with no fresh estimate (a failing one): say nothing rather than wait on
# Header colour thresholds for "how much are you risking by not selling" (credits).
UNSOLD_WARN = 50_000_000
UNSOLD_URGENT = 250_000_000
# Defaults a browser adopts until its user changes them (page settings live in the browser).
BIO_MIN = 10_000_000
SOUNDS_DEFAULT = True
# Rows in Here stand out when a body's data is worth this much, bonuses left out: cartographic (scan +
# map, no first-discovery / first-mapped / efficiency bonus) and exobiology (no first-footfall x5).
BODY_HIGHLIGHT = 500_000
BIO_HIGHLIGHT = 10_000_000
# Whether Here's Max column counts first-discovery / first-mapped / first-footfall bonuses (Now always does:
# it is what a sale would pay).
MAX_INCLUDE_BONUS = True
# The approach briefing warns about landing at this surface gravity (g) or more when the data aboard is over the
# amber level or the rebuy multiple.
HIGH_GRAVITY = 2.0
# Core module health (S5): a line next to hull, in the welcome back and the co-pilot's status report when any core
# module is under this (%). The page's alerts dialog can set its own.
MODULE_WARN = 80
# The Nearby radius choices offered on the page (ly). Bigger spheres cost Spansh requests and page redraws:
# ~1,500 systems at 100 ly out in the black, far more near the bubble.
RADIUS_CHOICES = (20, 25, 30, 40, 50)
# Spoken alerts: the Piper voice, and the one used when it is missing (see outrider/tts.py).
VOICE, VOICE_FALLBACK = outrider.tts.DEFAULT_VOICE, outrider.tts.DEFAULT_FALLBACK
BACKUP_DIR = os.path.join(outrider.DATA_DIR, "backups")   # where backups go (in data/, git-ignored); journals are archived in its journals/
BACKUP_KEEP = 7            # dated database zips kept (outrider-<db name>-*.zip); the journal archive is never pruned
BACKUP_EVERY_DAYS = 1.0    # an automatic backup at start when the last is older than this, and when the game quits (0 = off)
SHUTDOWN_BACKUP_DELAY = 10  # s after a live Shutdown before its backup (the game is still closing its files)
SHUTDOWN_LIVE_S = 300      # s: a Shutdown older than this is a journal being caught up on, not a quit just now
# Page settings saved on the server for browsers that have not set them ("use these for new browsers"):
# only these localStorage keys, at most this size. Per-device keys (the view, layouts, the search form, which
# screen speaks) stay out. The page has the same list (SETTINGS_KEYS in page.js).
BROWSER_SETTINGS = ("alerts", "alertSound", "alertSpeak", "speech", "speechStyles", "speechNames", "speechSpeed",
                    "speechProfanity", "speechProfanityPct", "speechDangerBusiness", "speechShift", "sayBio", "sayGeo", "sayHazard",
                    "sayMapped", "honkAnnounce", "sound", "unsoldCfg", "highlightCfg", "bioMinCfg", "maxBonus", "codexNewCounts",
                    "highG", "streakCfg", "skipFloor", "sort", "sorts", "showVisited", "showExplored", "oneJump", "map",
                    "log", "lbRadius", "fShowLost", "fWithin", "mHeld", "bioSort", "bState", "bDays", "hDays", "routineQuiet", "fuelJumps",
                    "surfaceCfg", "moduleWarn", "tilesCollapsed", "highway")
BROWSER_DEFAULTS_MAX = 64 * 1024   # bytes
BROWSER_DEFAULTS_FILE = "browser_defaults.json"   # next to the database
# Spoken alerts' wording: the lines file, and the personalities a browser starts with (see outrider/speech.py).
SPEECH_FILE = os.path.join(outrider.RESOURCES_DIR, "speech.json")
SPEECH_STYLES, SPEECH_PROFANITY = ("business",), False
SPEECH_PROFANITY_PCT = 50   # with profanity on: how often (%) a line comes from the swearing versions
SPEECH_DANGER_BUSINESS = True   # hull, heat, interdiction, fuel and carrier-departure lines only from the business lists
SPEECH_NAMES = "Boss, Hefay, Sir"   # what the voice calls you ({name}), one at random per line
# Auto honk (see outrider/honk.py): on arriving by hyperspace, hold a key bound to Primary Fire so the Discovery
# Scanner fires. The D-Scanner MUST be on PRIMARY FIRE in the active fire group when you jump.
AUTOHONK = {"enabled": False, "key": outrider.honk.DEFAULT_KEY, "delay": 2.0, "hold": 6.0, "skip_honked": True,
            "announce": True}   # announce: say the body count (or "all bodies were found") when it completes
AUTOHONK_MAX_AGE = 30   # s: an arrival older than this is a journal being caught up on, not a live jump
AUTOHONK_WAIT_MAX = 90  # s: how long the honk waits for you to close the galaxy map / FSS / a panel
AUTOHONK_TEST_COUNTDOWN = 5   # s: the Test button's time to click into the game before the press
BACKUP_MIN_GAP = 60     # s: a manual backup is refused this soon after the last one finished
# Status.json GuiFocus: what has the game's focus other than the cockpit (0). Primary Fire does nothing there.
GUI_FOCUS = outrider.target.GUI_FOCUS
FLAG_IN_MAIN_SHIP = 1 << 24   # Status.json Flags: in your own ship (not the SRV, a fighter or on foot)
VEHICLE_SETTLE_S = 60        # s after an SRV launch before Status.json alone may say you are back aboard
FLAG_FSD_JUMP = 1 << 30   # Status.json Flags: in the hyperspace tunnel
FLAG_SCOOPING = 1 << 11   # Status.json Flags: fuel scooping
FLAG_FSD_CHARGING = 1 << 17
FLAG_HUD_ANALYSIS = 1 << 27   # Status.json Flags: HUD in analysis mode (clear: combat mode, Primary Fire fires weapons)
SCOOP_MIN_RUN = 5.0       # s: a scoop shorter than this (skimming the edge of the zone) is not worth a word
SCOOP_SETTLE = 2.5        # s: the flag must stay off this long before the scoop counts as over (it flickers)
SCOOP_JUMP_GRACE = 10     # s: a scoop that ends this soon after a hyperspace StartJump was left on purpose
BRIEF_WAIT = 12           # s after a hyperspace arrival with no honk: the arrival briefing from Spansh data alone
FSS_SETTLE = 2.0          # s after the FSS closes before judging it: the journal's last Scan lines may still be coming


class ScoopWatch:
    """Fuel scooping from Status.json, polled every tick: the end of each scoop, once. The flag must stay off
    SCOOP_SETTLE s (it flickers at the edge of the scoop zone) and the scoop must have run SCOOP_MIN_RUN s.
    A scoop cut short by a jump (FSD charging, or a hyperspace StartJump just now) says nothing, and nor does
    one whose tank capacity is unknown (no Loadout yet)."""

    def __init__(self):
        self.start = self.off_since = None
        self.jumping = False

    def update(self, st, capacity, now, jump_ts=None):
        """-> {"pct", "full"} when a scoop has just ended, else None."""
        st = st or {}
        if not st.get("live"):
            self.start = self.off_since = None
            return None
        flags = st.get("flags") or 0
        if flags & FLAG_SCOOPING:
            if self.start is None:
                self.start = now
            # scooping again: a charge seen during a flicker was cancelled (a real jump ends the scoop for good)
            self.off_since, self.jumping = None, False
            return None
        if self.start is None:
            return None
        if flags & (FLAG_FSD_CHARGING | FLAG_FSD_JUMP):
            self.jumping = True
        if self.off_since is None:
            self.off_since = now
            return None
        if now - self.off_since < SCOOP_SETTLE:
            return None
        ran, self.start, self.off_since = self.off_since - self.start, None, None
        fuel = st.get("fuel_main")
        if ran < SCOOP_MIN_RUN or not capacity or fuel is None:
            return None
        try:
            jumped = self.jumping or (jump_ts is not None and 0 <= now - ts_seconds(jump_ts) <= SCOOP_JUMP_GRACE + SCOOP_SETTLE)
        except (TypeError, ValueError):
            jumped = self.jumping
        full = fuel >= capacity - 0.05
        if not full and jumped:
            return None
        return {"pct": min(100, round(100 * fuel / capacity)), "full": full}


def fire_group_letter(group):
    """Status.json FireGroup (0, 1, ...) as the letter the game shows (A, B, ...); None when unknown."""
    return chr(65 + group) if isinstance(group, int) and not isinstance(group, bool) and 0 <= group < 26 else None


def simulate_settings(st):
    """--simulate (screenshots and demos): the settings with the co-pilot button and the clipboard off."""
    return dict(st, copilot=dict(st["copilot"], enabled=False), highway=dict(st["highway"], clipboard=False))


def simulate_keyboard_off(honker, why="--simulate"):
    """--simulate, and a server away from the game PC: no virtual keyboard at all, so every open, press, test and
    auto-target run is refused (nothing may press a key into whatever window has focus)."""
    honker.evdev, honker.status = None, f"off ({why})"
    return honker


NOT_GAME_PC = "needs Outrider on the PC the game runs on (this one is a server: [server] game_pc)"


def in_container(dockerenv="/.dockerenv", env=None):
    """Whether this runs inside a container: Docker's /.dockerenv, or OUTRIDER_CONTAINER=1 (the image sets it)."""
    env = os.environ if env is None else env
    return os.path.exists(dockerenv) or env.get("OUTRIDER_CONTAINER") == "1"


def resolve_game_pc(setting, container=None):
    """[server] game_pc -> (whether this is the game PC, why): true / false as set; auto: not inside a container."""
    if setting is True or setting is False:
        return setting, "set in the config ([server] game_pc)"
    inside = in_container() if container is None else container
    return (False, "running in a container ([server] game_pc = auto)") if inside else (True, "auto")


def status_fresh(status, now):
    """A live Status.json written in the last 30 s."""
    st = status or {}
    try:
        return bool(st.get("live") and st.get("ts") and now - ts_seconds(st["ts"]) < 30)
    except (TypeError, ValueError):
        return False


def honk_decision(status, now, groups=None):
    """Whether the auto honk can press now: ("press", None) or ("wait", why). Waits while the jump is still
    running, something other than the cockpit has focus (the galaxy map straight after arriving, say), since
    Primary Fire does nothing there, or the HUD is in combat mode (Primary Fire would fire the weapons). With
    this ship's learned fire groups (honk_learn: {"good": [...], "bad": [...]}) it also waits while a group
    where honks missed before is selected; an unknown group still gets the press. Without a live, recent
    Status.json it presses, as before."""
    st = status or {}
    if not status_fresh(st, now):
        return "press", None
    flags = st.get("flags")
    if (flags or 0) & FLAG_FSD_JUMP:
        return "wait", "still in the jump"
    focus = st.get("gui_focus") or 0
    if focus:
        return "wait", GUI_FOCUS.get(focus, "a panel is open")
    if isinstance(flags, int) and not flags & FLAG_HUD_ANALYSIS:
        return "wait", "the HUD is in combat mode"
    group = fire_group_letter(st.get("fire_group"))
    if group and groups and group in (groups.get("bad") or []):
        good = ", ".join(groups.get("good") or [])
        return "wait", f"fire group {group} selected; honks missed there before" + (f" (worked on {good})" if good else "")
    return "press", None


HONK_MISSES_BAD = 2   # auto-honk misses in a row in one fire group, with no success anywhere between, before it is bad


def honk_learn(record, group, ok):
    """One ship's fire-group record ({"good": [letters], "bad": [letters]}, plus "miss": {letter: misses in a row}
    while a group has missed without being bad yet) after an auto-honk press made with fire group `group` selected:
    a confirmed scan puts the group in good (and clears it from bad) and ends every run of misses; a miss puts it in
    bad on its HONK_MISSES_BAD-th in a row, unless it has worked there before. One miss is not enough: the caller only
    passes misses nothing it can see explains (the cockpit had focus, the HUD was in analysis mode, no screen opened
    during the press), but a press sent while another window had the keyboard (an alt-tab: the game cannot tell)
    looks the same, and a group marked bad is never pressed in again until "forget"."""
    good, bad = set((record or {}).get("good") or []), set((record or {}).get("bad") or [])
    miss = dict((record or {}).get("miss") or {})
    if group:
        if ok:
            good.add(group)
            bad.discard(group)
            miss = {}
        elif group not in good and group not in bad:
            miss[group] = miss.get(group, 0) + 1
            if miss[group] >= HONK_MISSES_BAD:
                bad.add(group)
                del miss[group]
    out = {"good": sorted(good), "bad": sorted(bad)}
    if miss:
        out["miss"] = miss
    return out


SPEAK_BIO_SIGNALS = SPEAK_GEO_SIGNALS = True   # say "2 Biological Signals on body A 3" as the FSS finds them
CODEX_INTERESTING = True   # a body whose likeliest species is new to your codex here is worth stopping for, whatever its value
SPEAK_MAPPED = False   # the "mapped" call-out after each planet's DSS mapping (what it pays, the efficiency, what is next)
SPEECH_SPEED = 1.0   # spoken alerts' pace: 1 is the voice's own, 1.3 is 30% faster (0.5 to 2)
# the player for the page's "Play speech and sounds on this PC" tick: auto (the first found), one by name, or off
SERVER_PLAYER = "auto"
# The co-pilot button (see outrider/button.py): tap (in the ship) target the next route system, double tap a status
# report, hold hush until the next jump.
COPILOT = {"enabled": False, "device": "", "button": "", "hold_ms": outrider.button.HOLD_MS, "double_ms": outrider.button.DOUBLE_MS}
COPILOT_ACTIONS = ("status", "again", "hush", "replay")
HUSH_MODES = {"10m": 600, "30m": 1800, "jump": None}   # s a timed hush lasts; "jump" lasts until you leave the system

# The surface map and Rhino mining rigs (Batch M1). The game writes nothing when a rig is placed or picked up, so the
# co-pilot button marks them (in the Rhino on a body every gesture does); collections are the journal's MiningRefined.
SURFACE_ALT = 1000        # m: the surface map shows below this altitude...
SURFACE_HIDE_PAD = 100    # ...and hides above SURFACE_ALT + this (nothing flickers in between)
RIG_SPACING = 50          # m: the ring drawn round a rig: the game allowed two rigs ~44-51 m apart (author's test, 30 Sep) and draws a 50 m ring
SURFACE_MAP_MIN = 500     # m across: the map never zooms in tighter than this
SURFACE_MAP_STRIP = False  # a small copy of the map in the on-body strip too
RIG_WARN = 3500           # m from the Rhino: the leash warning (a rig is lost at RIG_LOST_M)
RIG_WARN_AGAIN = 4500     # m: said once more here
RIG_LOST_M = 5000         # m: the game destroys a rig this far from its Rhino (the community guide, tested twice)
RIG_BEHIND_M = 7          # m: a rig lands this far behind the cockpit, along the heading (SrvSurvey)
RIG_TAP_M = 5             # m: a tap this close to a rig that is out picks it up (the game's pickup range is under 5 m)
RIG_MATCH_M = 10          # m: a collection this close to a rig is that rig's (5 m pickup range plus GPS slack)
RIG_SLOTS = 6             # rigs out at once, numbered 1-6 like the game's HUD
RIG_FULL_S = 480          # s after placing or the last collection: "probably full" (a rig refills in 5.5-8 min)
BURST_START_GAP = 60      # s with no MiningRefined before one starts a new collection...
BURST_END_GAP = 30        # s: ...and a collection is over after this quiet (a later ton inside BURST_START_GAP joins it)
BURST_RETARGET_S = 2      # s: a position read this soon after a collection's first ton can still move it onto a rig
LOCATION_NEAR_M = 2000    # m: a saved site this close to a mining location's marker belongs to that location
SURFACE_BUMP_M, SURFACE_BUMP_DEG, SURFACE_BUMP_S = 5, 10, 0.5   # the map's position updates: a move, a turn, at most 2/s
FLAG_LANDED = 1 << 1      # Status.json Flags: landed (the ship on the ground)
FLAG_IN_SRV = 1 << 26
FLAG_IN_FIGHTER = 1 << 25   # with FLAG_IN_SRV: Status.json's Fuel and Cargo are the vehicle's, not the ship's
FLAG_ALT_AVG = 1 << 29    # Altitude is from the average radius (high up: a rough reading)
RHINO = "mev_rhino"
# Status.json Destination.Name of a targeted planetary mining location: "...#type=$PlanetaryMiningLocation_Name;:#index=3;"
MINING_LOCATION_RE = re.compile(r"#type=\$PlanetaryMiningLocation_Name;:#index=(\d+);")


# --------------------------------------------------------------------------
# Configuration: command-line flag > environment (ED_JOURNALS) > ed_outrider.toml > auto-detection.
# Every key is optional; with no file at all the defaults above and auto-detection apply.
# --------------------------------------------------------------------------

def load_config(path):
    """The TOML config as a dict ({} if there is no file); a broken file is reported, not fatal."""
    try:
        import tomllib
    except ImportError:  # Python < 3.11: the tomli package is the same reader under another name
        try:
            import tomli as tomllib
        except ImportError:
            if os.path.exists(path):
                print(f"config {path} ignored: reading it needs Python 3.11+ (or pip install tomli)", file=sys.stderr)
            return {}
    raw = b""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        return tomllib.loads(raw.decode("utf-8-sig"))   # -sig: Notepad's and PowerShell's "UTF-8 with BOM" too
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:   # UnicodeDecodeError: not saved as UTF-8
        # the likeliest slip on Windows: a path in double quotes, where a backslash starts an escape ("C:\Users")
        hint = (CONFIG_BACKSLASH_HINT if isinstance(e, tomllib.TOMLDecodeError) and re.search(rb'"[^"\n]*\\[^"\n]*"', raw)
                else "")
        print(f"config {path}: {e} (ignored: every setting is at its default){hint}", file=sys.stderr)
        return {}


CONFIG_BACKSLASH_HINT = ("\n  a path in double quotes cannot hold single backslashes: write C:/Users/... or 'C:\\Users\\...'"
                         " (single quotes), or set it in Settings > Server")


def _config_folders(value, key):
    """A [journals] live/legacy value as a list of folders: a single string is one folder."""
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)) and all(isinstance(x, str) for x in value):
        return list(value)
    print(f"config: [journals] {key} must be a list of folders, e.g. {key} = [\"C:/...\"]; ignored", file=sys.stderr)
    return None


def _config_value(section, key, value, conv, default):
    """A config value converted with `conv`; a value of the wrong type is reported and the default used."""
    if value is None:
        return default
    try:
        out = conv(value)
        if isinstance(out, float) and not math.isfinite(out):   # TOML allows inf and nan
            raise ValueError("not a finite number")
        return out
    except (TypeError, ValueError, OverflowError):   # OverflowError: int(inf)
        print(f"config: [{section}] {key} = {value!r} is not valid here, using {default!r}", file=sys.stderr)
        return default


def _config_bool(v):
    """A strict config boolean: true/false (or 1/0). bool("false") is True, so a quoted "false" or "no" must be
    reported and the default kept, never read as on (it could switch auto honk on)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    raise TypeError("not a boolean")


def _config_str(v):
    """A config value that must be a string (host = 0, with the quotes dropped, would crash the start later)."""
    if isinstance(v, str):
        return v
    raise TypeError("not a string")


def _config_player(v):
    """[speech] server_player: one of outrider.tts.PLAYER_CHOICES."""
    if isinstance(v, str) and v.strip().lower() in outrider.tts.PLAYER_CHOICES:
        return v.strip().lower()
    raise ValueError("not a player: " + ", ".join(outrider.tts.PLAYER_CHOICES))


def config_choices():
    """The config keys with a fixed set of values, for the Settings dialog (config_edit.CHOICES and the PC players)."""
    return {**outrider.config_edit.CHOICES, ("speech", "server_player"): outrider.tts.PLAYER_CHOICES}


def _config_entry(v):
    """[highway] autotarget_entry: "type" or "paste"."""
    if isinstance(v, str) and v.strip().lower() in ("type", "paste"):
        return v.strip().lower()
    raise ValueError('not "type" or "paste"')


def _config_target_keys(v):
    """[highway] autotarget_keys: {step key name: "KEY_A+KEY_B"} for the controls auto-target presses (and Enter,
    Paste); each value as evdev names."""
    if not isinstance(v, dict):
        raise TypeError("not a table")
    names = set(outrider.target.ACTIONS) | set(outrider.target.FIXED_KEYS)
    out = {}
    for k, val in v.items():
        keys = outrider.honk.parse_combo(val) if isinstance(val, str) else []
        if k not in names or not keys or not all(re.fullmatch(r"KEY_[A-Z0-9_]+", x) for x in keys):
            raise ValueError(f"{k} = {val!r} (names: {', '.join(sorted(names))}; values like \"KEY_LEFTALT+KEY_T\")")
        out[k] = "+".join(keys)
    return out


def _config_plot_steps(v):
    """[highway] autotarget_plot: a list of steps ("press UI_Select", "hold UI_Select 1", "wait 0.5")."""
    if not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v):
        raise TypeError("not a list of steps")
    for x in v:
        outrider.target.parse_step(x)
    return [" ".join(x.split()) for x in v]


def _config_button(v):
    """[copilot] button: an evdev name or code, as a string or a bare number (a switch is not a button)."""
    if isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
        return str(v).strip()
    raise TypeError("not a button name or number")


def _config_bg_image(v):
    """[highway] background_image: "" (none) or a path to an image file (relative to the repository, ~ allowed)
    with one of HIGHWAY_BG_TYPES' extensions; returned absolute."""
    if not isinstance(v, str):
        raise TypeError("not a path")
    if not v.strip():
        return ""
    if os.path.splitext(v.strip())[1].lower() not in HIGHWAY_BG_TYPES:
        raise ValueError("not an image: " + ", ".join(HIGHWAY_BG_TYPES))
    return os.path.join(SCRIPT_DIR, os.path.expanduser(v.strip()))


def _config_extent(v):
    """[highway] background_extent: [xmin, xmax, zmin, zmax] in ly, each min below its max."""
    if not isinstance(v, (list, tuple)) or len(v) != 4 or any(isinstance(x, bool) for x in v):
        raise TypeError("not a list of four numbers")
    out = [float(x) for x in v]
    if not all(math.isfinite(x) for x in out) or not (out[0] < out[1] and out[2] < out[3]):
        raise ValueError("not [xmin, xmax, zmin, zmax]")
    return out


def _config_port(v):
    """A TCP port: a whole number from 1 to 65535 (70000 or -1 would crash the start with an OverflowError, and
    port = true would read as port 1). A quoted number ("9000") still works."""
    if isinstance(v, str):
        v = int(v.strip())
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError("not a whole number")
    if not 1 <= v <= 65535:
        raise ValueError("not a port from 1 to 65535")
    return v


def _cli_port(text):
    """--port: as _config_port, reported by argparse (not a traceback) when out of range."""
    try:
        return _config_port(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"{text!r} is not a port from 1 to 65535") from None


def _config_radius(v):
    """A sphere radius: a number of at least 1 ly (0 or a negative one would ask Spansh for nothing)."""
    out = float(v)
    if not out >= 1:
        raise ValueError("under 1 ly")
    return out


def _config_section(cfg, name):
    """A [section] of the config file: {} (reported) when the file gives that name a plain value instead of a
    table (`journals = "C:/..."`), so a broken file is reported, not fatal."""
    sec = cfg.get(name, {})
    if isinstance(sec, dict):
        return sec
    print(f"config: {name} = {sec!r} must be a [{name}] section (a table of settings); ignored", file=sys.stderr)
    return {}


def settings_from(cfg, args, env_journals=None, detected=((), ())):
    """Resolve every setting with the precedence flag > env > config > default/auto-detect."""
    j, sv, df, sp = (_config_section(cfg, s) for s in ("journals", "server", "defaults", "spansh"))
    ah, spk, cp = _config_section(cfg, "autohonk"), _config_section(cfg, "speech"), _config_section(cfg, "copilot")
    hw = _config_section(cfg, "highway")
    j = dict(j, live=_config_folders(j.get("live"), "live"), legacy=_config_folders(j.get("legacy"), "legacy"))
    num = lambda sec, table, key, conv, default: _config_value(sec, key, table.get(key), conv, default)
    flag = lambda sec, table, key, default: _config_value(sec, key, table.get(key), _config_bool, default)
    styles = df.get("speech_styles")
    if isinstance(styles, str):   # speech_styles = "sarcastic": one style, not a list of them
        styles = [styles]
    elif styles is not None and not isinstance(styles, list):
        print(f"config: [defaults] speech_styles = {styles!r} must be a list, e.g. [\"business\", \"sarcastic\"]; "
              f"using {SPEECH_STYLES!r}", file=sys.stderr)
        styles = None
    choices = sv.get("radius_choices", RADIUS_CHOICES)
    if not isinstance(choices, (list, tuple)):
        print(f"config: [server] radius_choices = {choices!r} must be a list, e.g. [20, 25, 30]; using the defaults",
              file=sys.stderr)
        choices = RADIUS_CHOICES
    radius_choices = sorted({x for x in (_config_value("server", "radius_choices", c, float, None) for c in choices)
                             if x and x > 0}) or [float(x) for x in RADIUS_CHOICES]
    pick = lambda flag, key, default: flag if flag is not None else key if key is not None else default
    hosts = sv.get("allowed_hosts", [])
    if isinstance(hosts, str):
        hosts = [hosts]
    if not (isinstance(hosts, (list, tuple)) and all(isinstance(x, str) for x in hosts)):
        print(f"config: [server] allowed_hosts = {hosts!r} must be a list of names, e.g. [\"mypc.lan\", \"192.168.1.20\"]; "
              "ignored", file=sys.stderr)
        hosts = []
    game_pc = sv.get("game_pc", "auto")   # "auto": off inside a container (see resolve_game_pc)
    if isinstance(game_pc, str) and game_pc.strip().lower() in ("auto", "true", "false", "on", "off", "yes", "no"):
        game_pc = {"auto": "auto", "true": True, "on": True, "yes": True}.get(game_pc.strip().lower(), False)
    elif not isinstance(game_pc, bool):
        print(f"config: [server] game_pc = {game_pc!r} must be auto, true or false; using auto", file=sys.stderr)
        game_pc = "auto"
    password = sv.get("password", "")
    if isinstance(password, (int, float)) and not isinstance(password, bool):
        print(f"config: [server] password = {password!r} should be in quotes; taken as {str(password)!r}", file=sys.stderr)
        password = str(password)
    elif not isinstance(password, str):
        # never "no password": the server could be open to the network. An unknown one instead: devices on the
        # network cannot sign in until the file is fixed (this PC needs none)
        print("config: [server] password must be text in quotes; until it is, nobody can sign in from another device",
              file=sys.stderr)
        password = secrets.token_hex(24)
    if args.journals:
        live = list(args.journals)
    elif env_journals:
        live = [d for d in env_journals.split(os.pathsep) if d]
    elif j.get("live") is not None:   # present, even as [], turns auto-detection off (only a missing key detects)
        live = list(j["live"])
    else:
        live = list(detected[0])
    if args.legacy:
        legacy = list(args.legacy)
    elif j.get("legacy") is not None:   # legacy = [] means no legacy folders, not the auto-detected ones
        legacy = list(j["legacy"])
    else:
        legacy = [] if (args.journals or env_journals or j.get("live") is not None) else list(detected[1])
    return {
        "live": [os.path.expanduser(d) for d in live], "legacy": [os.path.expanduser(d) for d in legacy],
        "host": pick(args.host, num("server", sv, "host", _config_str, None), "127.0.0.1"),
        "port": pick(args.port, num("server", sv, "port", _config_port, None), 8025),
        "allowed_hosts": [h.strip() for h in hosts if h.strip()],
        "password": password, "game_pc": game_pc,
        "update_check": flag("server", sv, "update_check", True),
        # at least 1 ly: a bad config value is reported above; a --radius 0 flag is clamped
        "radius": max(1.0, pick(args.radius, num("server", sv, "radius", _config_radius, None), 25.0)),
        "radius_choices": radius_choices,
        # a relative --db is relative to the current folder, like every other path flag; a relative db in the
        # config file is relative to the repository folder (where this script is), so a copied folder keeps working
        "db": (os.path.abspath(os.path.expanduser(args.db)) if args.db
               else os.path.join(SCRIPT_DIR, os.path.expanduser(str(sv.get("db") or DB_PATH)))),
        "unsold_warn": num("defaults", df, "unsold_warn", int, UNSOLD_WARN),
        "unsold_urgent": num("defaults", df, "unsold_urgent", int, UNSOLD_URGENT),
        "bio_min": num("defaults", df, "bio_min", int, BIO_MIN),
        "sounds": flag("defaults", df, "sounds", SOUNDS_DEFAULT),
        "body_highlight": num("defaults", df, "body_highlight_level", int, BODY_HIGHLIGHT),
        "bio_highlight": num("defaults", df, "biology_highlight_value", int, BIO_HIGHLIGHT),
        "max_include_bonus": flag("defaults", df, "body_max_value_include_bonus", MAX_INCLUDE_BONUS),
        # at least 0.1 g: the page reads 0 (or less) as "not set" and uses 2 g, so 0 could not mean "every body"
        "high_gravity": max(0.1, num("defaults", df, "high_gravity", float, HIGH_GRAVITY)),
        "module_warn": min(100, max(1, num("defaults", df, "module_warn", int, MODULE_WARN))),
        "surface_alt": max(10.0, num("defaults", df, "surface_alt", float, SURFACE_ALT)),
        "rig_spacing": max(0.0, num("defaults", df, "rig_spacing", float, RIG_SPACING)),
        "surface_map_min": max(50.0, num("defaults", df, "surface_map_min", float, SURFACE_MAP_MIN)),
        "surface_map_strip": flag("defaults", df, "surface_map_strip", SURFACE_MAP_STRIP),
        # under the 5 km at which the game destroys a rig, or the warning would come too late
        "rig_warn": min(RIG_LOST_M - 100.0, max(100.0, num("defaults", df, "rig_warn", float, RIG_WARN))),
        "voice": str(df.get("voice") or VOICE), "voice_fallback": str(df.get("voice_fallback") or VOICE_FALLBACK),
        "speech_styles": [str(x) for x in (styles if styles is not None else SPEECH_STYLES)],
        "speech_profanity": flag("defaults", df, "speech_profanity", SPEECH_PROFANITY),
        "speech_profanity_pct": min(100, max(0, num("defaults", df, "speech_profanity_pct", int, SPEECH_PROFANITY_PCT))),
        "speech_danger_business": flag("defaults", df, "speech_danger_business", SPEECH_DANGER_BUSINESS),
        "speak_bio_signals": flag("defaults", df, "speak_bio_signals", SPEAK_BIO_SIGNALS),
        "speak_geo_signals": flag("defaults", df, "speak_geo_signals", SPEAK_GEO_SIGNALS),
        "speak_mapped": flag("defaults", df, "speak_mapped", SPEAK_MAPPED),
        "codex_interesting": flag("defaults", df, "codex_interesting", CODEX_INTERESTING),
        "speech_speed": min(2.0, max(0.5, num("defaults", df, "speech_speed", float, SPEECH_SPEED))),
        "speech_names": ", ".join(str(x) for x in df["speech_names"]) if isinstance(df.get("speech_names"), list)
                        else str(df.get("speech_names", SPEECH_NAMES)),
        "speech_file": speech_file_path(sv.get("speech_file")),
        "server_player": num("speech", spk, "server_player", _config_player, SERVER_PLAYER),
        # your own alert sounds: <name>.wav files replacing sounds.json's (review S16); "" for none
        "sound_dir": os.path.join(SCRIPT_DIR, os.path.expanduser(str(spk["sound_dir"])))
                     if isinstance(spk.get("sound_dir"), str) and spk["sound_dir"].strip() else "",
        "backup_dir": os.path.join(SCRIPT_DIR, os.path.expanduser(str(sv.get("backup_dir") or BACKUP_DIR))),
        "backup_keep": max(1, num("server", sv, "backup_keep", int, BACKUP_KEEP)),
        "backup_every_days": max(0.0, num("server", sv, "backup_every_days", float, BACKUP_EVERY_DAYS)),
        # at least 1 (a Semaphore(0) would hang every body fetch, a negative one fails at start), and a map of
        # at least the 5 ly the map endpoint asks for anyway
        "concurrency": max(1, num("spansh", sp, "concurrency", int, SPANSH_CONCURRENCY)),
        "map_max_radius": max(5.0, num("spansh", sp, "map_max_radius", float, MAP_MAX_RADIUS)),
        "map_max_pages": max(1, num("spansh", sp, "map_max_pages", int, MAP_MAX_PAGES)),
        "watch_firsts": flag("spansh", sp, "watch_firsts", WATCH_FIRSTS),
        "autohonk": {"enabled": flag("autohonk", ah, "enabled", AUTOHONK["enabled"]),
                     "key": str(ah.get("key") or AUTOHONK["key"]),
                     "delay": max(0.0, num("autohonk", ah, "delay", float, AUTOHONK["delay"])),
                     "hold": min(20.0, max(0.5, num("autohonk", ah, "hold", float, AUTOHONK["hold"]))),
                     "skip_honked": flag("autohonk", ah, "skip_honked", AUTOHONK["skip_honked"]),
                     "announce": flag("autohonk", ah, "announce", AUTOHONK["announce"])},
        "copilot": {"enabled": flag("copilot", cp, "enabled", COPILOT["enabled"]),
                    "device": num("copilot", cp, "device", _config_str, COPILOT["device"]),
                    # a name (BTN_TRIGGER_HAPPY5) or the number --listen prints, bare or quoted
                    "button": str(num("copilot", cp, "button", _config_button, COPILOT["button"])),
                    "hold_ms": min(3000, max(200, num("copilot", cp, "hold_ms", int, COPILOT["hold_ms"]))),
                    "double_ms": min(1000, max(100, num("copilot", cp, "double_ms", int, COPILOT["double_ms"])))},
        "highway": {"clipboard": flag("highway", hw, "clipboard", HIGHWAY["clipboard"]),
                    "autotarget": flag("highway", hw, "autotarget", HIGHWAY["autotarget"]),
                    "autotarget_delay": min(60.0, max(0.0, num("highway", hw, "autotarget_delay", float,
                                                               HIGHWAY["autotarget_delay"]))),
                    # the neutron plotter's efficiency (%): Spansh takes 1 to 100
                    "efficiency": min(100, max(1, num("highway", hw, "efficiency", int, HIGHWAY["efficiency"]))),
                    # the plot form's "Conservative range" tick and its margin (ly), as the page starts them
                    "conservative": flag("highway", hw, "conservative", HIGHWAY["conservative"]),
                    "conservative_ly": min(HIGHWAY_CONSERVATIVE_MAX, max(0.5, num("highway", hw, "conservative_ly", float,
                                                                                HIGHWAY["conservative_ly"]))),
                    # the map's own background image (absolute path, or "" for none), where its edges are, how opaque
                    "background_image": num("highway", hw, "background_image", _config_bg_image, ""),
                    "background_extent": num("highway", hw, "background_extent", _config_extent, list(HIGHWAY_BG_EXTENT)),
                    "background_opacity": min(1.0, max(0.05, num("highway", hw, "background_opacity", float,
                                                                 HIGHWAY_BG_OPACITY))),
                    "autotarget_entry": num("highway", hw, "autotarget_entry", _config_entry, HIGHWAY["autotarget_entry"]),
                    "autotarget_map_wait": min(30.0, max(1.0, num("highway", hw, "autotarget_map_wait", float,
                                                                  HIGHWAY["autotarget_map_wait"]))),
                    "autotarget_search_wait": min(30.0, max(0.0, num("highway", hw, "autotarget_search_wait", float,
                                                                     HIGHWAY["autotarget_search_wait"]))),
                    "autotarget_key_delay": min(1.0, max(0.0, num("highway", hw, "autotarget_key_delay", float,
                                                                  HIGHWAY["autotarget_key_delay"]))),
                    "autotarget_keys": num("highway", hw, "autotarget_keys", _config_target_keys, {}),
                    "autotarget_plot": num("highway", hw, "autotarget_plot", _config_plot_steps,
                                           list(HIGHWAY["autotarget_plot"])),
                    "autotarget_search": num("highway", hw, "autotarget_search", _config_plot_steps,
                                             list(HIGHWAY["autotarget_search"])),
                    "autotarget_submit": num("highway", hw, "autotarget_submit", _config_plot_steps,
                                             list(HIGHWAY["autotarget_submit"])),
                    "autotarget_dry_run": flag("highway", hw, "autotarget_dry_run", HIGHWAY["autotarget_dry_run"])},
        # [mcp]: read by the MCP bridge (python3 -m outrider.mcp), not the server; here so --write-config writes it
        **outrider.mcp.mcp_settings(cfg),
        "assistant": outrider.ask.assistant_settings(cfg),   # the voice's optional AI layer (off by default)
        **outrider.uploads.upload_settings(cfg),              # [eddn], [edsm]: written by Settings -> Uploads
    }


def _root_relative(path):
    """A path inside the repository as the config file writes it: relative to it (resources/speech.json,
    data/ed_outrider.sqlite); anything elsewhere stays absolute."""
    try:
        rel = os.path.relpath(path, SCRIPT_DIR)
    except ValueError:   # another drive (Windows)
        return path
    return path if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel) else rel


def config_text(st):
    """The effective settings as a TOML document (what --write-config writes)."""
    q = lambda v: outrider.config_edit.basic_string(str(v))   # a TOML string, properly escaped
    p = lambda v: q(str(v).replace("\\", "/"))                # a path: Windows' backslashes written as slashes
    lst = lambda vs: "[" + ", ".join(q(v) for v in vs) + "]"
    plst = lambda vs: "[" + ", ".join(p(v) for v in vs) + "]"
    # a number by its type: a decimal setting stays a TOML float even when whole ("1.0", not "1"), so the Server
    # settings editor offers it as a decimal (a whole value read back as an int refused 1.3: the sweep of 2026-10-09)
    n = outrider.config_edit.number
    return f"""# ED Outrider configuration. Every key is optional; command-line flags and the ED_JOURNALS
# environment variable override this file, and journal folders are auto-detected when absent.

[journals]
{"live = " + plst(st["live"]) if st["live"] else "# live = []"}      # folders holding Journal.*.log that are tailed live (auto-detected when absent)
{"" if st["live"] else "# "}legacy = {plst(st["legacy"])}  # folders of older journals, imported once and never re-read ([] = none; auto-detected only when live is absent too)

[server]
host = {q(st["host"])}   # "0.0.0.0" to reach the page from another device on your network
port = {st["port"]}   # the page's port: http://<this PC>:<port>/
allowed_hosts = {lst(st["allowed_hosts"])}   # extra names the page may be opened by (a LAN setup; see docs/guide/install.md)
password = {q(st["password"])}   # devices on your network sign in with it ("" = none); this PC itself never needs it
game_pc = {q(st["game_pc"] if st["game_pc"] == "auto" else ("true" if st["game_pc"] else "false"))}   # is this the PC the game runs on? "auto" (off inside a container, e.g. Docker), "true" or "false". Off: no auto honk, auto-target, tablet rail, co-pilot button, clipboard or playing on this PC
update_check = {"true" if st["update_check"] else "false"}   # once a day, ask GitHub whether a newer Outrider release is out, and say so on the page (only the request: nothing about you is sent)
radius = {n(st["radius"])}      # ly: the sphere of nearby systems the page lists
radius_choices = [{", ".join(n(x) for x in st["radius_choices"])}]   # ly: what the page's radius dropdown offers
backup_dir = {p(st["backup_dir"])}   # backups: dated database zips, and every live journal copied once into its journals/
backup_keep = {st["backup_keep"]}   # dated database zips kept (the journal archive is never pruned)
backup_every_days = {n(st["backup_every_days"])}   # automatic backup at start when the last is older than this, and when the game quits (0 = off)
speech_file = {p(_root_relative(st["speech_file"]))}   # the spoken alerts' lines, per personality
db = {p(_root_relative(st["db"]))}   # the database: everything Outrider knows (relative paths start at the Outrider folder)

[defaults]   # what a browser uses until its user changes it (page settings stay per browser)
unsold_warn = {st["unsold_warn"]}     # amber "worth selling soon", credits on board
unsold_urgent = {st["unsold_urgent"]}   # red "go sell"
bio_min = {st["bio_min"]}         # a body only counts as unfinished bio if it could pay over this
sounds = {"true" if st["sounds"] else "false"}   # the alert sounds on (the page's 🔊)
body_highlight_level = {st["body_highlight"]}     # Here: a body's row turns green if scan + map pays this, no bonuses
biology_highlight_value = {st["bio_highlight"]}  # Here: a body's bio turns violet if it could pay this, no x5 bonus
body_max_value_include_bonus = {"true" if st["max_include_bonus"] else "false"}  # Here: Max counts first-discovery/mapped/footfall bonuses
high_gravity = {n(st["high_gravity"])}   # g: the approach briefing warns about landing here or higher with a lot of data aboard
module_warn = {st["module_warn"]}   # %: show core module health (FSD, power plant, thrusters, life support, sensors, fuel scoop, AFMU) when one is under this
surface_alt = {n(st["surface_alt"])}   # m: the surface map on Now shows below this altitude (hides 100 m higher)
rig_spacing = {n(st["rig_spacing"])}   # m: the ring round a Rhino mining rig (an estimate: rigs closer than this may not deploy; 0 = no ring)
surface_map_min = {n(st["surface_map_min"])}   # m: the surface map never shows less than this across
surface_map_strip = {"true" if st["surface_map_strip"] else "false"}   # also a small copy of the map in the on-body strip
rig_warn = {n(st["rig_warn"])}   # m: say so when a mining rig is this far from the Rhino (again at 4,500; the game destroys it at 5,000)
voice = {q(st["voice"])}          # spoken alerts: Piper voice (downloaded into data/piper-voices/ on first use; one picked on the page wins)
voice_fallback = {q(st["voice_fallback"])}  # used while the voice above is missing
speech_styles = [{", ".join(q(x) for x in st["speech_styles"])}]   # spoken alerts' personalities: any of the styles in the speech file
speech_profanity = {"true" if st["speech_profanity"] else "false"}   # also use the swearing versions (sarcastic, sweet)
speech_profanity_pct = {st["speech_profanity_pct"]}   # with profanity on: how often (%) a line is a swearing one
speech_danger_business = {"true" if st["speech_danger_business"] else "false"}   # danger lines (hull, heat, interdiction, fuel, carrier leaving) only from business, never swearing
speak_bio_signals = {"true" if st["speak_bio_signals"] else "false"}   # say biological signal counts as the FSS finds them
speak_geo_signals = {"true" if st["speak_geo_signals"] else "false"}   # and geological ones
speak_mapped = {"true" if st["speak_mapped"] else "false"}   # after mapping a planet: what it pays, whether the efficiency bonus landed, what is next
codex_interesting = {"true" if st["codex_interesting"] else "false"}   # a codex find (✦) makes a body worth stopping for: on Now's next stops and in the leaving warnings
speech_speed = {n(st["speech_speed"])}   # spoken alerts' pace: 1 is the voice's own, 1.3 is 30% faster (0.5 to 2)
speech_names = {q(st["speech_names"])}   # what the voice calls you, comma separated: one is picked at random each time

[spansh]
concurrency = {st["concurrency"]}          # body-detail fetches in flight after an arrival
map_max_radius = {n(st["map_max_radius"])}    # ly: the largest 3D map the page may ask for
map_max_pages = {st["map_max_pages"]}        # pages of 500 systems fetched for the map
watch_firsts = {"true" if st["watch_firsts"] else "false"}   # check your unsold first discoveries on Spansh in the background (one request every 10-30 s; each system daily for a month, then weekly; at most 150 a day) for someone else's scans

[speech]   # for the page's "Play speech and sounds on this PC" tick (per browser, off until ticked)
server_player = {q(st["server_player"])}   # auto (the first of pw-play, paplay, aplay, ffplay found), one of those, or off (Linux)
{"" if st["sound_dir"] else "# "}sound_dir = {p(_root_relative(st["sound_dir"]) if st["sound_dir"] else "my-sounds")}   # your own alert sounds: <name>.wav (fanfare, thud, chime, alert...), up to 3 s each

[autohonk]   # hold Primary Fire on arriving by hyperspace, so the Discovery Scanner fires (Linux; Windows experimental; see outrider/honk.py)
# IMPORTANT: the Discovery Scanner MUST be on PRIMARY FIRE in the fire group that is active when you jump,
# and Primary Fire needs a keyboard binding (key = "auto" reads it, modifiers too, from your controls preset).
enabled = {"true" if st["autohonk"]["enabled"] else "false"}   # the page's Settings can switch it on and off too
key = {q(st["autohonk"]["key"])}   # "auto": Primary Fire's keyboard binding from your controls preset; or e.g. KEY_KP0, KEY_LEFTALT+KEY_K
delay = {n(st["autohonk"]["delay"])}   # seconds after arriving before the press (the jump tunnel ignores input)
hold = {n(st["autohonk"]["hold"])}    # seconds to hold the trigger (the scanner fires once charged)
skip_honked = {"true" if st["autohonk"]["skip_honked"] else "false"}   # leave systems you have already honked alone
announce = {"true" if st["autohonk"]["announce"] else "false"}   # say "System scan completed, 12 bodies discovered" (or all found) afterwards

[copilot]   # one HOTAS or keyboard button (Linux, read-only; see outrider/button.py): tap (flying the ship) target the next route system, double tap a status report, hold hush until the next jump
# Unbind the button in Elite's controls. On an X-56 avoid the latching toggles and the mode wheel (they read as held).
# Joysticks are readable through uaccess; a keyboard or mouse needs the input group.
enabled = {"true" if st["copilot"]["enabled"] else "false"}   # read the button below
device = {q(st["copilot"]["device"])}   # a part of the device's name, or a /dev/input/by-id/... path (python3 -m outrider.button --listen lists them)
button = {q(st["copilot"]["button"])}   # the button's evdev name (e.g. BTN_TRIGGER_HAPPY5) or code number, as --listen prints it
hold_ms = {st["copilot"]["hold_ms"]}   # ms held (or more) that make a hold
double_ms = {st["copilot"]["double_ms"]}   # ms between a tap's release and the next press that make a double tap

[highway]   # the Neutron Highway: a Spansh route that Outrider follows as you fly
clipboard = {"true" if st["highway"]["clipboard"] else "false"}   # on arriving at a route system, copy the next one's name to the desktop clipboard (wl-copy or xclip on Linux; built in on Windows)
# Auto-target (Linux, Windows experimental; off by default; the Plot Route tab can switch it): after a neutron supercharge on the route, press keys
# in the galaxy map to make the next route system the target (outrider/target.py; python3 -m outrider.target --show
# prints the steps with your keys). The keys go to whichever window has focus. It is key-press automation of the same
# kind as auto honk: check Frontier's rules for yourself.
autotarget = {"true" if st["highway"]["autotarget"] else "false"}   # auto-target the next route system after a supercharge (the Plot Route tab switches it too)
autotarget_delay = {n(st["highway"]["autotarget_delay"])}   # seconds after the supercharge (0 to 60)
autotarget_entry = {q(st["highway"]["autotarget_entry"])}   # "type" the name on the virtual keyboard (US layout), or "paste" it (wl-copy/xclip, then Ctrl+V)
autotarget_map_wait = {n(st["highway"]["autotarget_map_wait"])}   # seconds to wait for the galaxy map to open (and close) before giving up
autotarget_search_wait = {n(st["highway"]["autotarget_search_wait"])}   # seconds after submitting the search for the map to fly to the system
autotarget_key_delay = {n(st["highway"]["autotarget_key_delay"])}   # seconds between typed characters
autotarget_keys = {{{", ".join(f"{k} = {q(v)}" for k, v in st["highway"]["autotarget_keys"].items())}}}   # override a step's keys, e.g. {{ GalaxyMapOpen = "KEY_LEFTALT+KEY_RIGHTALT+KEY_T", Enter = "KEY_KPENTER" }}; otherwise read from your controls preset
autotarget_search = {lst(st["highway"]["autotarget_search"])}   # from the opened galaxy map into its search field (a camera turn first: the map reopens on its last panel)
autotarget_submit = {lst(st["highway"]["autotarget_submit"])}   # select the search's suggestion once the name is in (it lists it after a moment)
autotarget_plot = {lst(st["highway"]["autotarget_plot"])}   # the "plot route" step after the search (a short zoom gives the map the focus): "press <key>", "hold <key> <s>", "wait <s>"
autotarget_dry_run = {"true" if st["highway"]["autotarget_dry_run"] else "false"}   # only log the steps it would take (nothing is pressed)
efficiency = {st["highway"]["efficiency"]}   # the neutron plotter's efficiency (%): lower takes longer neutron detours
conservative = {"true" if st["highway"]["conservative"] else "false"}   # the plot form starts with "Conservative range" ticked: plot jumps a margin shorter than the ship's range
conservative_ly = {n(st["highway"]["conservative_ly"])}   # that margin (ly, 0.5 to 50): about this many ly shorter jumps, times the supercharge on a neutron jump
background_image = {p(_root_relative(st["highway"]["background_image"])) if st["highway"]["background_image"] else '""'}   # a top-down galaxy image you downloaded (PNG, JPEG, WebP or GIF) under the map; Outrider ships none
background_extent = [{", ".join(n(x) for x in st["highway"]["background_extent"])}]   # ly: the image's edges, [xmin, xmax, zmin, zmax] (the usual galaxy images: -45000, 45000, -20000, 70000)
background_opacity = {n(st["highway"]["background_opacity"])}   # 0.05 to 1

[assistant]
enabled = {"true" if st["assistant"]["enabled"] else "false"}   # the voice's AI layer for questions the fixed phrases do not match (resources/ask.json); nothing is sent anywhere while false
base_url = {q(st["assistant"]["base_url"])}   # an OpenAI-compatible endpoint, e.g. "http://localhost:11434/v1" (Ollama), "https://api.openai.com/v1"
api_key = {q(st["assistant"]["api_key"])}   # stays on this PC ("" for a local model)
model = {q(st["assistant"]["model"])}   # one that can call tools
timeout = {n(st["assistant"]["timeout"])}   # seconds for the whole answer
max_rounds = {st["assistant"]["max_rounds"]}   # tool rounds before it must answer

[mcp]
{"url = " + q(st["mcp_url"]) if st["mcp_url"] else "# url = " + q("http://127.0.0.1:8025")}   # the running Outrider for the MCP bridge (python3 -m outrider.mcp); default: this PC at [server] port
max_rows = {st["mcp_rows"]}   # how many rows a list in a tool's answer holds (the rest are counted)
password = {q(st["mcp_password"])}   # an Outrider on another computer (a server) asks for its [server] password: the bridge signs in with this ("" on this PC)

[eddn]
# EDDN uploads: switched on and off in the page's Settings -> Uploads, which writes this. Off by default.
enabled = {"true" if st["uploads"]["eddn"]["enabled"] else "false"}   # send to EDDN as you play

[edsm]
# EDSM uploads: switched on and off in the page's Settings -> Uploads, which writes this (the key is set there too).
enabled = {"true" if st["uploads"]["edsm"]["enabled"] else "false"}   # send your flight log and scans to EDSM

"""

POSITION_EVENTS = ("FSDJump", "CarrierJump", "Location")
STAR_CLASS_EVENTS = ("FSDTarget", "StartJump")
SCAN_EVENTS = ("Scan", "FSSDiscoveryScan", "FSSAllBodiesFound", "SAASignalsFound", "FSSBodySignals",
               "SAAScanComplete", "Disembark", "ScanOrganic", "CodexEntry", "ScanBaryCentre")
# Your fleet carrier, and fuel: where it is, what it carries, how much is in the tank.
SHIP_EVENTS = ("FuelScoop", "RefuelAll", "RefuelPartial", "CarrierStats", "CarrierJump", "CarrierJumpRequest",
               "CarrierJumpCancelled", "CarrierLocation", "Docked", "Undocked",
               "CarrierBuy", "CarrierDecommission", "CarrierCancelDecommission",   # a new carrier; giving one up
               "Cargo",   # the hold's tonnage: the ship's mass, for the fuel model
               # hull and danger: live alerts only (hull % is kept; the rest are moments, not state)
               "HullDamage", "RepairAll", "Repair", "RepairDrone", "HeatDamage", "Interdicted",
               "JetConeBoost",   # a neutron / white dwarf charge: the next jump's range is multiplied
               "AfmuRepairs",    # a module repaired in flight: its new health (core module health, S5)
               "NavRouteClear")  # the plotted route was cleared
# Core modules whose health is kept per ship (S5): by Loadout slot, and the fuel scoop and AFMU by item (they sit in
# any optional slot). Hardpoints and utilities are left out: noise for an explorer.
CORE_SLOTS = {"FrameShiftDrive": "FSD", "PowerPlant": "Power plant", "MainEngines": "Thrusters",
              "LifeSupport": "Life support", "Radar": "Sensors"}
CORE_ITEMS = {"int_fuelscoop": "Fuel scoop", "int_repairer": "AFMU"}
CORE_ORDER = list(CORE_SLOTS.values()) + list(CORE_ITEMS.values())


def core_label(slot, item):
    """What to call a Loadout module if it is a core one (CORE_SLOTS / CORE_ITEMS), else None."""
    item = (item or "").lower()
    return CORE_SLOTS.get(slot) or next((v for k, v in CORE_ITEMS.items() if item.startswith(k)), None)


# Selling or losing exploration data decides whether your discoveries were credited.
DATA_EVENTS = ("MultiSellExplorationData", "SellExplorationData", "SellOrganicData", "Died", "Resurrect")
# Who is playing and what they had at login: name, credits.
CMDR_EVENTS = ("LoadGame", "Commander", "Rank", "Progress", "Promotion", "Statistics")
# written while the game loads (at the main menu, before LoadGame): not play, so not where a session ended
LOGIN_EVENTS = frozenset(CMDR_EVENTS) | {"Fileheader", "Materials"}
RANK_KEYS = ("Combat", "Trade", "Explore", "Soldier", "Exobiologist", "Empire", "Federation", "CQC")
RANK_NAMES = {   # the two ranks an explorer cares about
    "Explore": ["Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer",
                "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"],
    "Exobiologist": ["Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist",
                     "Ecologist", "Geneticist", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"],
}
# Engineering materials: the login snapshot and everything that adds or spends them (see outrider.materials).
# Flying to and from a body: the approach briefing, the leaving-a-body warning (and what you touched down on).
BODY_EVENTS = ("ApproachBody", "LeaveBody", "Touchdown")
# The SRV on a body, and what its refinery collects (1 t per MiningRefined): "Mined previously" per body (own_mined).
# These are read for that alone; the body comes from SRV_TRACKED (see Journals.track_srv).
# Liftoff: only for the surface map's ship marker (a Liftoff while aboard takes it away).
SRV_EVENTS = ("LaunchSRV", "LaunchVessel", "DockSRV", "SRVDestroyed", "MiningRefined", "SupercruiseExit", "SupercruiseEntry", "Liftoff")
SRV_TRACKED = frozenset(SRV_EVENTS) | {"ApproachBody", "LeaveBody", "Touchdown", "Location", "LoadGame",
                                       "FSDJump", "CarrierJump", "Died"}
MATERIAL_EVENTS = ("Materials", "MaterialCollected", "MaterialDiscarded", "Synthesis", "EngineerCraft",
                   "MaterialTrade", "TechnologyBroker", "ScientificResearch", "MissionCompleted",
                   "EngineerContribution")
# Cargo (outrider/cargo.py): the ship's hold and your carrier's. Cargo, Docked, Undocked, CarrierStats (SHIP_EVENTS)
# and MiningRefined (SRV_EVENTS) are read here too; these are only for cargo.
CARGO_ONLY = ("MarketBuy", "MarketSell", "CargoTransfer", "CarrierTradeOrder", "CarrierDepositFuel", "CollectCargo",
              "EjectCargo")
CARGO_EVENTS = frozenset(CARGO_ONLY) | {"Cargo", "Docked", "Undocked", "CarrierStats", "MiningRefined"}
CARRIER_CARGO_EVENTS = ("CarrierStats", "CarrierTradeOrder", "CargoTransfer", "MarketBuy", "MarketSell")
WANTED = tuple(f'"event":"{e}"'.encode()
               for e in POSITION_EVENTS + STAR_CLASS_EVENTS + SCAN_EVENTS + DATA_EVENTS + SHIP_EVENTS
               + CMDR_EVENTS + MATERIAL_EVENTS + BODY_EVENTS + SRV_EVENTS + CARGO_ONLY + ("Loadout", "Shutdown"))

# Bump when the journal parser learns new events: forces a one-off re-read of every journal.
# 27: sale pages keyed by journal position (same-second 'Sell all' pages were dropped before); logins.
# 28: return visits get the 'visited' streak verdict on the jump itself.
# 30: body records keep pressure_raw (the bio rules compare finer than the rounded pressure).
# 31: Vista Genomics sales keep the x5 sale check (x5_check: the runs predicted x5 against those paid it).
# 32: body signals keep the planetary mining location count (own_signals.mining).
# 33: what the SRV's refinery collected on each body (own_mined: "Mined previously").
# 34: nav-beacon scans make no own_firsts rows; Vista Genomics sales keep their BioData species (bio_sales.bio_data).
# 35: every ship's latest Loadout (fleet_loadouts: the Highway's ship list and the exact plotter's figures).
# 36: fleet_loadouts' figures again: a MaxJumpRange without the Guardian booster keeps the drive's optimal mass.
# 37: the Nomad's LaunchVessel keeps the body you are on: a Rhino launched after it records its mining (own_mined).
# 38: bio_sales keyed by journal line (two Vista sales in one second); a Vista visit's x5 check made as one.
# 39: the vehicle you are in rebuilt from the journals (a live fallback forgot the Rhino at every launch).
# 40: cargo: the ship's hold (ship_cargo) and your carrier's history (cargo_events).
# 41: your carrier bought (CarrierBuy) or decommissioned (CarrierDecommission, CarrierCancelDecommission); a new one's
#     CarrierStats starts its state afresh instead of inheriting the old one's place.
# 42: a Location that says Docked (a login or respawn docked) counts as a dock: carrier transfers made straight after
#     were dropped; the SRV's refinery and scoop stay out of the ship's hold; an older Location's relog is judged
#     against the arrival before it (a legacy folder read late counted every login as a visit).
# 43: a system's population (system_population) and own_firsts.bio_x5: no x5 bio bonus in populated systems.
PARSER_VERSION = 44
# Scans read off a nav beacon (as outrider.unsold.NAV_BEACON_SCANS): their Was* flags are not the game's record of the body.
NAV_BEACON_SCANS = ("NavBeaconDetail", "NavBeacon")

SCOOPABLE = set("OBAFGKM")
ON_FOOT_DOCKED = (1 << 3) | (1 << 13) | (1 << 14)   # Status.json Flags2: on foot in a station, hangar, social space
HEAT_QUIET = 30            # s: at most one heat alert in this long
FUEL_HISTORY = 20          # recent jumps used to estimate fuel per jump
JUMP_CARGO_S = 120         # s: a Status.json hold this close to a jump stands in for a Cargo not read yet
SCOOP_RATE_OF = 20         # arrivals the scoopable share is taken over
SCOOP_RATE_MIN = 8         # fewer known arrival stars than this: no share (carrier jumps and journal gaps have none)
# Planet classes worth a detour (plus anything terraformable).
NOTABLE_PLANETS = {"Earth-like world": "ELW", "Water world": "WW", "Ammonia world": "AW"}
BIO = "$SAA_SignalType_Biological;"
GEO = "$SAA_SignalType_Geological;"
MINING = "$PlanetaryMiningLocation_Name;"   # planetary mining locations (Rhino mining sites), counted like bio/geo

# Planetary mining odds (mining_odds.json, from the Elite Dangerous Field Manual's survey by CMDR Grumlop, CC BY-SA 4.0):
# the share of each ground type's surveyed mining locations that carried each material. Odds, not a body's contents.
MINING_ODDS_FILE = os.path.join(outrider.RESOURCES_DIR, "mining_odds.json")
MINING_TOP = 6             # materials a tooltip lists
MINING_FEW = 30            # fewer surveyed locations than this: "few reports"
# a body record's planet class (Spansh's names, which own scans are normalised to; the journal's too) -> ground
MINING_GROUNDS = {"Metal-rich body": "metal-rich", "Metal rich body": "metal-rich",
                  "High metal content world": "high-metal-content", "High metal content body": "high-metal-content",
                  "Rocky Ice world": "rocky-ice", "Rocky ice body": "rocky-ice", "Icy body": "icy"}


def mining_ground(subtype, volcanism):
    """The survey's ground type for a planet class and volcanism (a Scan's or a Spansh record's), or None.
    A rocky body splits by its volcanism: any magma is 'volcanic magma', silicate vapour geysers 'volcanic
    silicate', anything else (none included) 'rocky'."""
    if subtype in MINING_GROUNDS:
        return MINING_GROUNDS[subtype]
    if subtype != "Rocky body":
        return None
    v = (volcanism or "").lower()
    return "volcanic magma" if "magma" in v else "volcanic silicate" if "silicate vapour" in v else "rocky"


def load_mining_odds(path=MINING_ODDS_FILE):
    """mining_odds.json -> {ground: {"surveyed": locations, "materials": [(name, share %)] highest first}};
    {} when the file is missing or unreadable (the count still shows, without the tooltip)."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    game_names = {"Low Temp Diamonds": "Low Temperature Diamonds"}   # the survey's spelling -> the journal's
    for m in d.get("materials") or []:
        for o in m.get("observations") or []:
            g, pct = o.get("ground"), o.get("observed_percentage")
            if not g or pct is None or not m.get("name"):
                continue
            e = out.setdefault(g, {"surveyed": 0, "materials": []})
            e["surveyed"] = max(e["surveyed"], o.get("locations_surveyed") or 0)
            e["materials"].append((game_names.get(m["name"], m["name"]), pct))
    for e in out.values():
        e["materials"].sort(key=lambda x: (-x[1], x[0]))
    return out


MINING_ODDS = load_mining_odds()


# Grounds a Rhino goes for (S4): the metals and the magma-volcanic rocky bodies. Icy and rocky-ice ground yields mostly
# deuterium, diamonds and helium-3, so Nearby's ⛏ count leaves it out (Search still finds it).
RHINO_GROUNDS = frozenset({"metal-rich", "high-metal-content", "volcanic magma"})
MINING_SHARE_MIN = 10      # %: Search keeps a body for a mineral when the survey found it at this share of its ground's locations


def mining_share(ground, mineral, odds=None):
    """The survey's share (%) of `ground`'s mining locations that carried `mineral`, or None when not surveyed."""
    e = (MINING_ODDS if odds is None else odds).get(ground) if ground else None
    return next((p for n, p in (e or {}).get("materials") or [] if n == mineral), None)


def mining_minerals(odds=None):
    """Every material the survey names, for Search's mineral list."""
    return sorted({n for e in (MINING_ODDS if odds is None else odds).values() for n, _ in e["materials"]})


def searchable_minerals(db):
    """Search's mineral list: the survey's minerals, and every one you have refined (own_mined): the survey names only
    some, so Gold, water or methanol you mined could not be searched for (review S38)."""
    names = set(mining_minerals())
    names |= {r[0] for r in db.execute("SELECT DISTINCT name FROM own_mined WHERE name IS NOT NULL AND tons > 0")}
    return sorted(names)


def rhino_mining(records):
    """(locations, bodies) of planetary mining locations on Rhino-worthy ground (RHINO_GROUNDS) among `records`."""
    hits = [r["mining"] for r in records if r.get("mining") and r.get("type") == "Planet"
            and mining_ground(r.get("subtype"), r.get("volcanism")) in RHINO_GROUNDS]
    return sum(hits), len(hits)


def mining_odds(ground, odds=None):
    """What a body's mining-count tooltip lists: {ground, surveyed, few, top: [{name, pct}], more}, or None. The survey
    tracks the valuable commodities only (no water or methanol crystals): the tooltip says so."""
    e = (MINING_ODDS if odds is None else odds).get(ground) if ground else None
    if not e or not e["materials"]:
        return None
    return {"ground": ground, "surveyed": e["surveyed"], "few": e["surveyed"] < MINING_FEW,
            "top": [{"name": n, "pct": p} for n, p in e["materials"][:MINING_TOP]], "more": len(e["materials"]) > MINING_TOP}

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS journal_files (
    path TEXT PRIMARY KEY, offset INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS visits (
    id64 INTEGER PRIMARY KEY, name TEXT, x REAL, y REAL, z REAL,
    first_ts TEXT, last_ts TEXT, count INTEGER NOT NULL DEFAULT 0);
-- Every arrival, in order: the path you flew. kind is the event (FSDJump, CarrierJump, or Location
-- for a login/respawn somewhere new, which breaks the path). star_class comes from StartJump.
-- verdict (the discovery streak): new / visited / known, fixed by the arrival star's scan (see note_verdict).
-- ride is 1 for an Apex shuttle or multicrew jump: not your ship's tank (no scoop count, no scoopable share).
CREATE TABLE IF NOT EXISTS jumps (
    ts TEXT, id64 INTEGER, name TEXT, x REAL, y REAL, z REAL, star_class TEXT, kind TEXT, verdict TEXT, ride INTEGER,
    PRIMARY KEY (ts, id64));
-- What Spansh knew about a known system when you arrived (partial / complete): the streak strip's amber and
-- blue. Live only, so it is kept through a journal re-read (not in RESET_JOURNAL_DATA): colours never change.
CREATE TABLE IF NOT EXISTS arrival_verdicts (ts TEXT, id64 INTEGER, verdict TEXT, PRIMARY KEY (ts, id64));
CREATE TABLE IF NOT EXISTS route_systems (
    id64 INTEGER PRIMARY KEY, name TEXT, x REAL, y REAL, z REAL,
    star_class TEXT, seen_ts TEXT);
CREATE TABLE IF NOT EXISTS star_classes (
    id64 INTEGER PRIMARY KEY, star_class TEXT);
CREATE TABLE IF NOT EXISTS spansh_systems (
    id64 INTEGER PRIMARY KEY, updated_at TEXT, summary TEXT, fetched_ts REAL);
-- Your own scans, straight from the journal.
CREATE TABLE IF NOT EXISTS own_systems (
    id64 INTEGER PRIMARY KEY, name TEXT, body_count INTEGER, all_found INTEGER);
CREATE TABLE IF NOT EXISTS own_bodies (
    system INTEGER, body_id INTEGER, name TEXT, record TEXT, ts TEXT, raw TEXT,
    PRIMARY KEY (system, body_id));
-- Barycentres (the Null entries in a body's Parents): their orbit, from ScanBaryCentre.
CREATE TABLE IF NOT EXISTS own_barycentres (
    system INTEGER, body_id INTEGER, record TEXT, ts TEXT,
    PRIMARY KEY (system, body_id));
CREATE TABLE IF NOT EXISTS own_signals (
    system INTEGER, name TEXT, bio INTEGER, geo INTEGER, ts TEXT, mining INTEGER,
    PRIMARY KEY (system, name));
-- Discovery flags from your *first* scan of each body (later rescans say "discovered" once you've sold).
-- bio_x5: whether Vista Genomics pays the x5 first-footfall bonus for its samples: nobody had set foot there when you
-- scanned it AND its system has no population (1 / 0, NULL unknown). Populated systems never pay it: checked on the
-- author's sales, 0 of 8 runs there against 208 of 208 elsewhere (plugin gaps A; BioScan's rule).
CREATE TABLE IF NOT EXISTS own_firsts (
    system INTEGER, body_id INTEGER, name TEXT, is_main INTEGER,
    was_discovered INTEGER, was_mapped INTEGER, was_footfalled INTEGER,
    first_ts TEXT, undisc_ts TEXT, bio_x5 INTEGER, PRIMARY KEY (system, body_id));
-- A system's population, from its FSDJump / Location / CarrierJump (the newest kept): whether bio pays x5 there.
CREATE TABLE IF NOT EXISTS system_population (id64 INTEGER PRIMARY KEY, population INTEGER, ts TEXT);
-- What the SRV's refinery collected on each body (MiningRefined, 1 t each, while in the SRV on that body).
-- source: the journal line last counted (file:offset), so a line handled twice is not counted twice.
CREATE TABLE IF NOT EXISTS own_mined (
    system INTEGER, body_id INTEGER, commodity TEXT, name TEXT, tons INTEGER, first_ts TEXT, last_ts TEXT,
    source TEXT, PRIMARY KEY (system, body_id, commodity));
CREATE TABLE IF NOT EXISTS own_mapped (system INTEGER, body_id INTEGER, ts TEXT, first_ts TEXT, PRIMARY KEY (system, body_id));
CREATE TABLE IF NOT EXISTS own_footfall (system INTEGER, body_id INTEGER, ts TEXT, PRIMARY KEY (system, body_id));
CREATE TABLE IF NOT EXISTS sales (name TEXT, ts TEXT, bodies INTEGER);
-- Vista Genomics sales: bio_data the species each BioData entry named with whether it paid the bonus, JSON
-- [[species, bonus], ...] (lower case codex keys), for organic_replay; NULL on a row stored before it was kept.
-- source: the journal line ("file:offset"), so two Vista Genomics sales in one second stay two (Codex C1)
CREATE TABLE IF NOT EXISTS bio_sales (ts TEXT, species INTEGER, bio_data TEXT, source TEXT, PRIMARY KEY (ts, source));
CREATE INDEX IF NOT EXISTS sales_name ON sales (name);
-- Every login (LoadGame): History starts a session's window at the login before its first jump.
CREATE TABLE IF NOT EXISTS logins (ts TEXT PRIMARY KEY);
-- option is the Resurrect choice that followed: "rebuy" means the ship (and its data) was lost.
CREATE TABLE IF NOT EXISTS deaths (ts TEXT PRIMARY KEY, option TEXT);
-- Exobiology: genera a DSS found on a body, and your sampling progress per species.
CREATE TABLE IF NOT EXISTS own_genera (
    system INTEGER, body_id INTEGER, genus TEXT, genus_name TEXT, ts TEXT,
    PRIMARY KEY (system, body_id, genus));
CREATE TABLE IF NOT EXISTS own_organic (
    system INTEGER, body_id INTEGER, species TEXT, genus_name TEXT, species_name TEXT, variant_name TEXT,
    samples INTEGER NOT NULL DEFAULT 0, done_ts TEXT, ts TEXT,
    PRIMARY KEY (system, body_id, species));
-- Codex entries: is_new = new to your codex for that region; voucher = codex credits paid (not a galactic first).
CREATE TABLE IF NOT EXISTS codex (
    ts TEXT, entry_id INTEGER, name TEXT, category TEXT, subcategory TEXT, region TEXT,
    system INTEGER, system_name TEXT, body_id INTEGER, is_new INTEGER, new_traits TEXT, voucher INTEGER,
    PRIMARY KEY (ts, entry_id));
CREATE INDEX IF NOT EXISTS codex_system ON codex (system);
CREATE INDEX IF NOT EXISTS jumps_ts ON jumps (ts);
CREATE INDEX IF NOT EXISTS own_firsts_system ON own_firsts (system);
CREATE TABLE IF NOT EXISTS own_ring_signals (
    system INTEGER, name TEXT, hotspots TEXT, ts TEXT,
    PRIMARY KEY (system, name));
-- Where each exobiology sample of the current run was taken (from Status.json at the time, live play only):
-- the sample-spacing readout measures from these. n = 1 (Log), 2 (Sample). Live only, so a journal re-read
-- keeps them (not in RESET_JOURNAL_DATA): a replay has no position to rebuild them from.
CREATE TABLE IF NOT EXISTS sample_points (
    system INTEGER, body_id INTEGER, species TEXT, genus TEXT, n INTEGER, lat REAL, lon REAL, ts TEXT,
    PRIMARY KEY (system, body_id, species, n));
-- Plants tagged with the composition scanner (a biology CodexEntry), BioScan's waypoints: where to go for the next
-- sample. The position is the event's Latitude/Longitude when it has them (on foot), else Status.json's at that
-- moment (the ship's or SRV's scanner: "scan as close to the plant as you can"). Live only, like sample_points: a
-- journal re-read keeps them (not in RESET_JOURNAL_DATA), and the ones with the event's own position come back as
-- the same rows.
CREATE TABLE IF NOT EXISTS bio_tags (
    system INTEGER, body_id INTEGER, species TEXT, genus TEXT, name TEXT, lat REAL, lon REAL, ts TEXT,
    PRIMARY KEY (system, body_id, species, ts));
-- The surface map's mining records (Batch M1). Live only, like sample_points: the positions come from Status.json
-- and a rig from a co-pilot press, none of which a journal holds, so a journal re-read keeps them (not in
-- RESET_JOURNAL_DATA) and the backup zip carries them with the rest of the database.
-- surface_rigs: Rhino mining rigs. n = its slot (1-6) while out; lat/lon = RIG_BEHIND_M behind the cockpit at the
-- press; site_lat/site_lon = where its first collection was refined (you drive over the rig for it). minerals =
-- JSON {name: tons} over every collection, tons their sum, last_ts the latest collection. picked_ts = picked up (a
-- tap by it) or lost (lost = 1: the 5 km leash, leaving the body); a rig that ends with tons is a saved site.
CREATE TABLE IF NOT EXISTS surface_rigs (
    id INTEGER PRIMARY KEY, system INTEGER, body_id INTEGER, body TEXT, n INTEGER, lat REAL, lon REAL,
    placed_ts TEXT, picked_ts TEXT, lost INTEGER, site_lat REAL, site_lon REAL, minerals TEXT,
    tons INTEGER NOT NULL DEFAULT 0, last_ts TEXT);
-- surface_sites: a collection with no rig marked near it (an unmarked site), kept so a good spot is not lost.
CREATE TABLE IF NOT EXISTS surface_sites (
    id INTEGER PRIMARY KEY, system INTEGER, body_id INTEGER, body TEXT, lat REAL, lon REAL, minerals TEXT,
    tons INTEGER NOT NULL DEFAULT 0, first_ts TEXT, last_ts TEXT);
-- mining_locations: where you arrived at a targeted Planetary Mining Location (Status.json Destination #index=N),
-- the map's marker LN; saved sites are grouped by the nearest within LOCATION_NEAR_M.
CREATE TABLE IF NOT EXISTS mining_locations (
    system INTEGER, body_id INTEGER, idx INTEGER, body TEXT, lat REAL, lon REAL, ts TEXT,
    PRIMARY KEY (system, body_id, idx));
-- Every sale, with what it actually paid (the trip ledger). One row per sale event: 'Sell all' writes one
-- MultiSellExplorationData per page, often in the same second, so source (journal file name:byte offset of
-- the line) tells the pages apart while a line handled twice still hits the same key. x5_check (bio sales): JSON
-- {sold, predicted, matched, paid, unknown, used}, the runs aboard predicted x5 against the entries paid the bonus (sale_check).
CREATE TABLE IF NOT EXISTS sale_events (
    ts TEXT, kind TEXT, base INTEGER, bonus INTEGER, total INTEGER, systems INTEGER, species INTEGER, source TEXT,
    x5_check TEXT, PRIMARY KEY (ts, kind, source));
-- Outrider's estimate just before a sale (recorded live, none for sales before the tool saw them). Live only,
-- so a journal re-read keeps it (not in RESET_JOURNAL_DATA); the ledger joins it to sale_events by (ts, kind).
CREATE TABLE IF NOT EXISTS sale_estimates (ts TEXT, kind TEXT, estimate INTEGER, PRIMARY KEY (ts, kind));
-- Notable stellar phenomena (the FSS "Codex" signals $Fixed_Event_Life_Cloud/Ring): kind cloud|ring;
-- reached_ts is set when you drop out of supercruise at one.
CREATE TABLE IF NOT EXISTS phenomena (
    system INTEGER, kind TEXT, ts TEXT, reached_ts TEXT, PRIMARY KEY (system, kind));
-- The firsts watch: what Spansh showed of a system holding your unsold first discoveries when last checked (see
-- firsts_reported). reported_ts is the earliest report by someone else of a body you discovered (the first sighting);
-- bodies how many of yours Spansh has from others, spansh_bodies of body_count the bodies it has in all. Live only
-- (Spansh's answers then cannot be rebuilt from journals), so a journal re-read keeps it (not in RESET_JOURNAL_DATA);
-- the backup zip carries it with the rest of the database.
CREATE TABLE IF NOT EXISTS firsts_watch (
    id64 INTEGER PRIMARY KEY, checked_ts REAL, reported_ts TEXT, bodies INTEGER, spansh_bodies INTEGER,
    body_count INTEGER, first_ts TEXT);
-- Bookmarks made on the page (the game's own bookmarks never reach the journal).
CREATE TABLE IF NOT EXISTS bookmarks (
    id64 INTEGER PRIMARY KEY, name TEXT, x REAL, y REAL, z REAL, note TEXT, created_ts TEXT);
-- Every ship you have flown, as its latest Loadout (one row per ShipID, an older Loadout read later never replaces a
-- newer one): the Highway's ship list and the exact plotter's inputs. figures: JSON from fleet_figures (drive, masses,
-- tanks, booster, range). Journal-derived: RESET_JOURNAL_DATA clears it and the re-read rebuilds it.
CREATE TABLE IF NOT EXISTS fleet_loadouts (
    ship_id INTEGER PRIMARY KEY, name TEXT, ship_type TEXT, ident TEXT, ts TEXT, figures TEXT);
-- The Neutron Highway: the one active route Spansh plotted (idx 0 is where it starts), with its plot in meta
-- 'highway' (plotter, ship, options, created_ts, and the progress: at, furthest, off_route, arrival_ts, done_ts).
-- distance: the jump into this system; remaining: ly left to the destination from here; jumps: jumps from the row
-- before (the neutron plotter's waypoints can be several); fuel_used/fuel_left only from the exact plotter. Live only
-- (a plot cannot be rebuilt from journals), so a journal re-read keeps it (not in RESET_JOURNAL_DATA); backups carry it.
CREATE TABLE IF NOT EXISTS highway_route (
    idx INTEGER PRIMARY KEY, system TEXT, id64 INTEGER, x REAL, y REAL, z REAL, distance REAL, fuel_used REAL,
    fuel_left REAL, neutron INTEGER, refuel INTEGER, jumps INTEGER, remaining REAL);
-- Road to Riches: the one active route Spansh plotted (idx 0 is where it starts) with the bodies it names per system,
-- and its plot and progress in meta 'riches' (options, created_ts, since_ts, at, furthest, off_route, arrival_ts, done_ts,
-- said_done: the row whose "all done" was said). Which bodies you have done is never stored here: it is read from
-- own_bodies / own_mapped (the journal) when asked. Live only (a plot cannot be rebuilt from journals), so a journal
-- re-read keeps it (not in RESET_JOURNAL_DATA); backups carry it.
CREATE TABLE IF NOT EXISTS riches_route (
    idx INTEGER PRIMARY KEY, system TEXT, id64 INTEGER, x REAL, y REAL, z REAL, jumps INTEGER);
CREATE TABLE IF NOT EXISTS riches_bodies (
    idx INTEGER, n INTEGER, name TEXT, type TEXT, subtype TEXT, ls REAL, scan INTEGER, map INTEGER,
    terraformable INTEGER, body_id INTEGER, PRIMARY KEY (idx, n));
-- Exomastery (the same slot, meta riches kind "exo"): the species Spansh lists on each route body. Live only, as above.
CREATE TABLE IF NOT EXISTS riches_species (
    idx INTEGER, n INTEGER, k INTEGER, genus TEXT, species TEXT, value INTEGER, count INTEGER, PRIMARY KEY (idx, n, k));
-- Cargo (outrider/cargo.py). Your carrier's history, one row per journal line (src "file:offset"): CarrierStats,
-- CarrierTradeOrder, CargoTransfer (with "_at", the market you were docked at), MarketBuy and MarketSell; market is
-- the carrier or market it concerns. Journal-derived: cleared by RESET_JOURNAL_DATA.
CREATE TABLE IF NOT EXISTS cargo_events (src TEXT PRIMARY KEY, ts TEXT, event TEXT, market INTEGER, data TEXT);
-- Your carrier's Market.json, each one read (the game overwrites the file at the next market). Live only: a journal
-- re-read keeps them (not in RESET_JOURNAL_DATA); backups carry them.
CREATE TABLE IF NOT EXISTS carrier_markets (ts TEXT, market_id INTEGER, items TEXT, PRIMARY KEY (ts, market_id));
-- The counts you entered for your carrier's lines (Recount; count 0 removes a line). Live only, as above.
CREATE TABLE IF NOT EXISTS carrier_counts (
    ts TEXT, carrier INTEGER, commodity TEXT, count INTEGER, name TEXT, PRIMARY KEY (ts, carrier, commodity));
CREATE INDEX IF NOT EXISTS cargo_events_market ON cargo_events (market, ts);
-- A trade route (the same slot, meta riches kind "trade"; outrider/cargo.py trade_rows): each stop's station and what to
-- sell and buy there (JSON lists). What you have done is in meta riches' "trade". Live only, as above.
CREATE TABLE IF NOT EXISTS trade_stops (
    idx INTEGER PRIMARY KEY, station TEXT, market_id INTEGER, ls REAL, updated REAL, distance REAL, sell TEXT, buy TEXT,
    profit INTEGER, cumulative INTEGER);
CREATE INDEX IF NOT EXISTS route_xyz ON route_systems (x, y, z);
CREATE INDEX IF NOT EXISTS visits_xyz ON visits (x, y, z);
"""

RESET_JOURNAL_DATA = """
DELETE FROM meta WHERE key IN ('hull', 'modules', 'last_sale', 'boost', 'statistics', 'route');
DELETE FROM journal_files; DELETE FROM visits; DELETE FROM jumps;
DELETE FROM own_systems; DELETE FROM own_bodies; DELETE FROM own_signals; DELETE FROM own_ring_signals;
DELETE FROM own_firsts; DELETE FROM own_mapped; DELETE FROM own_footfall; DELETE FROM sales; DELETE FROM deaths;
DELETE FROM own_genera; DELETE FROM own_organic; DELETE FROM codex; DELETE FROM bio_sales;
DELETE FROM own_barycentres; DELETE FROM phenomena; DELETE FROM sale_events; DELETE FROM logins;
DELETE FROM own_mined; DELETE FROM meta WHERE key IN ('srv_state', 'vehicle', 'ship_marker', 'body_here');
DELETE FROM fleet_loadouts; DELETE FROM cargo_events; DELETE FROM system_population;
DELETE FROM meta WHERE key IN ('ship_cargo', 'cargo_dock');
DELETE FROM meta WHERE key IN ('ship', 'carrier', 'fuel_hist', 'last_scoop', 'commander', 'materials', 'last_session', 'cargo');
DELETE FROM meta WHERE key LIKE 'legacy:%' OR key IN ('pos', 'prev', 'jump_range', 'state_ts');
"""


def open_db(path, rescan=False):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA + outrider.uploads.SCHEMA)
    migrate_sale_events(db)
    migrate_bio_sales(db)
    # Columns added to an existing table since the database was created: add them.
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);", SCHEMA + outrider.uploads.SCHEMA, re.S):
        table, body = m.group(1), m.group(2)
        have = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
        for col in re.split(r",\s*(?![^()]*\))", body):
            col = col.strip()
            name = col.split()[0] if col else ""
            if name and name.upper() not in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN") and name not in have \
                    and not col.upper().startswith("PRIMARY KEY"):
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col.split(',')[0]}")
    cols = {r["name"] for r in db.execute("PRAGMA table_info(spansh_systems)")}
    if "x" not in cols:
        db.executescript("ALTER TABLE spansh_systems ADD COLUMN x REAL;"
                         "ALTER TABLE spansh_systems ADD COLUMN y REAL;"
                         "ALTER TABLE spansh_systems ADD COLUMN z REAL;")
        for r in db.execute("SELECT id64, summary FROM spansh_systems").fetchall():
            b = json.loads(r["summary"])
            db.execute("UPDATE spansh_systems SET x=?, y=?, z=? WHERE id64=?",
                       (b.get("x"), b.get("y"), b.get("z"), r["id64"]))
        db.execute("CREATE INDEX IF NOT EXISTS spansh_xyz ON spansh_systems (x, y, z)")
        db.commit()
    if rescan or meta_get(db, "parser_version") != PARSER_VERSION:
        stamp_next_stop(db)
        db.executescript(RESET_JOURNAL_DATA)
        meta_set(db, "parser_version", PARSER_VERSION)
        db.commit()
    return db


def not_a_ship(kind):
    """True for a journal 'Ship' value that is not a ship of yours: a suit (ExplorationSuit_Class1), an SRV
    (TestBuggy, Combat_Multicrew_SRV_01), the Nomad (Lander01) or an Apex/Frontline shuttle (adder_taxi)."""
    k = (kind or "").lower()
    return "suit_class" in k or k.endswith("_taxi") or k == "testbuggy" or "_srv_" in k or k.startswith("lander")


def stamp_next_stop(db):
    """A next stop chosen before set_ts was stored: stamp it with the last arrival before the reset deletes 'pos',
    so the re-read that follows does not clear it on an earlier visit to that system."""
    ns = meta_get(db, "next_stop")
    if ns and not ns.get("set_ts"):
        ns["set_ts"] = (meta_get(db, "pos") or {}).get("ts") or iso_ts(time.time())
        meta_set(db, "next_stop", ns)


def unique_dirs(dirs):
    """Folders with the same folder listed twice dropped (a symlink, a trailing slash, the Windows save folder
    next to its Proton prefix): the first spelling is kept, so its stored offsets still apply."""
    seen, out = set(), []
    for d in dirs:
        real = os.path.realpath(d)
        if real not in seen:
            seen.add(real)
            out.append(d)
    return out


def migrate_sale_events(db):
    """sale_events from before the source column: key (ts, kind), with the estimate in the row. Its estimates
    move to sale_estimates first (they are live only: the journal re-read that follows cannot rebuild them),
    then the table is rebuilt with the new key; old rows get source '' (a re-read rebuilds them anyway).
    Runs before any RESET_JOURNAL_DATA, and in one transaction so a failure leaves the old table as it was."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(sale_events)")}
    if "source" in cols:
        return
    create = re.search(r"CREATE TABLE IF NOT EXISTS sale_events \(.*?\);", SCHEMA, re.S).group(0)
    keep = ("INSERT OR IGNORE INTO sale_estimates SELECT ts, kind, max(estimate) FROM sale_events_old"
            " WHERE estimate IS NOT NULL GROUP BY ts, kind;" if "estimate" in cols else "")
    db.executescript(f"""BEGIN;
        ALTER TABLE sale_events RENAME TO sale_events_old;
        {keep}
        {create}
        INSERT OR IGNORE INTO sale_events (ts, kind, base, bonus, total, systems, species, source)
            SELECT ts, kind, base, bonus, total, systems, species, '' FROM sale_events_old;
        DROP TABLE sale_events_old;
        COMMIT;""")


def migrate_bio_sales(db):
    """bio_sales from before the source column (keyed by ts alone, so two sales in one second were one): rebuilt
    empty with the new key. Journal-derived: the re-read PARSER_VERSION 38 asks for fills it again."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(bio_sales)")}
    if "source" in cols:
        return
    create = re.search(r"CREATE TABLE IF NOT EXISTS bio_sales \(.*?\);", SCHEMA, re.S).group(0)
    db.executescript(f"BEGIN; DROP TABLE bio_sales; {create} COMMIT;")


AWAY_MIN_S = 2 * 3600   # s: a break shorter than this (a relog, a mode switch) gets the plain greeting


def away_text(seconds):
    """A break as the login greeting says it ("5 hours", "3 days"), None when under AWAY_MIN_S."""
    if seconds is None or seconds < AWAY_MIN_S:
        return None
    if seconds < 36 * 3600:
        return f"{round(seconds / 3600)} hours"
    days = round(seconds / 86400)
    return f"{days} day{'' if days == 1 else 's'}"


def live_event(ts, now=None):
    """Whether a journal event happened just now (within SHUTDOWN_LIVE_S), not in a journal being caught up on."""
    try:
        return (time.time() if now is None else now) - ts_seconds(ts) <= SHUTDOWN_LIVE_S
    except (TypeError, ValueError):
        return False


def second_before(ts):
    """The journal timestamp one second earlier: an inclusive upper bound for "before ts"."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_seconds(ts) - 1))


def overlap(a, b, lo, hi):
    """How much of the span a..b lies inside lo..hi (0 if none)."""
    return max(0, min(b, hi) - max(a, lo))


def meta_get(db, key, default=None):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def meta_set(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, json.dumps(value)))


# --------------------------------------------------------------------------
# Body records
#
# Every body, whether from Spansh or your own journal, is reduced to one shape:
#   {name (short, e.g. "A 4"), type "Star"|"Planet", subtype (Spansh wording), main,
#    scoopable, terraformable, landable, rings [{name, type, hotspots}], belts [type],
#    bio, geo, full}
# "full" is False for Spansh search results, which lack rings, belts and signals.
# --------------------------------------------------------------------------

TERRAFORMABLE = {"Candidate for terraforming", "Terraforming", "Terraformable"}

JOURNAL_STARS = {
    "O": "O (Blue-White) Star", "B": "B (Blue-White) Star", "A": "A (Blue-White) Star",
    "F": "F (White) Star", "G": "G (White-Yellow) Star", "K": "K (Yellow-Orange) Star",
    "M": "M (Red dwarf) Star", "L": "L (Brown dwarf) Star", "T": "T (Brown dwarf) Star",
    "Y": "Y (Brown dwarf) Star", "TTS": "T Tauri Star", "AeBe": "Herbig Ae/Be Star",
    "W": "Wolf-Rayet Star", "WN": "Wolf-Rayet N Star", "WNC": "Wolf-Rayet NC Star",
    "WC": "Wolf-Rayet C Star", "WO": "Wolf-Rayet O Star",
    "CS": "CS Star", "C": "C Star", "CN": "CN Star", "CJ": "CJ Star", "CH": "CH Star",
    "CHd": "CHd Star", "MS": "MS-type Star", "S": "S-type Star",
    "N": "Neutron Star", "H": "Black Hole", "SupermassiveBlackHole": "Supermassive Black Hole",
    "A_BlueWhiteSuperGiant": "A (Blue-White super giant) Star",
    "B_BlueWhiteSuperGiant": "B (Blue-White super giant) Star",
    "F_WhiteSuperGiant": "F (White super giant) Star",
    "G_WhiteSuperGiant": "G (White-Yellow super giant) Star",
    "K_OrangeGiant": "K (Yellow-Orange giant) Star",
    "M_RedGiant": "M (Red giant) Star", "M_RedSuperGiant": "M (Red super giant) Star",
}

JOURNAL_PLANETS = {
    "Metal rich body": "Metal-rich body", "High metal content body": "High metal content world",
    "Rocky ice body": "Rocky Ice world", "Earthlike body": "Earth-like world",
    "Gas giant with water based life": "Gas giant with water-based life",
    "Gas giant with ammonia based life": "Gas giant with ammonia-based life",
    "Helium rich gas giant": "Helium-rich gas giant",
}

RING_CLASSES = {"eRingClass_Icy": "Icy", "eRingClass_Rocky": "Rocky",
                "eRingClass_MetalRich": "Metal Rich", "eRingClass_Metalic": "Metallic"}


def journal_star(code):
    if code in JOURNAL_STARS:
        return JOURNAL_STARS[code]
    if code and code.startswith("D"):
        return f"White Dwarf ({code}) Star"
    return code


def journal_planet(cls):
    if cls in JOURNAL_PLANETS:
        return JOURNAL_PLANETS[cls]
    m = re.match(r"^Sudarsky class (\w+) gas giant$", cls or "")
    return f"Class {m.group(1)} gas giant" if m else cls


# Spansh's names back to the journal's, for pricing Spansh bodies with the same formula as your scans.
SPANSH_STARS = {v: k for k, v in JOURNAL_STARS.items()}
SPANSH_PLANETS = {v: k for k, v in JOURNAL_PLANETS.items()}
# Spansh's terraformingState as the journal's TerraformState. Its dumps now say "Terraformable" (the older spelling was
# "Candidate for terraforming"): unknown here, it priced every Spansh-only terraformable body as a plain one (a
# terraformable high metal content world at 59k, 2026-10-09)
SPANSH_TERRAFORM = {"Candidate for terraforming": "Terraformable", "Terraformable": "Terraformable",
                    "Terraforming": "Terraforming", "Terraformed": "Terraformed"}


def ed_from_dump(b):
    """The fields outrider.unsold.body_value prices by, from a Spansh dump body; None if it cannot be priced
    (a star or planet class, or a mass, missing)."""
    st = b.get("subType") or ""
    if b.get("type") == "Star":
        code = SPANSH_STARS.get(st)
        if not code:
            m = re.match(r"^White Dwarf \((\w+)\) Star$", st)
            code = m.group(1) if m else None
        if not code or b.get("solarMasses") is None:
            return None
        return {"StarType": code, "StellarMass": b["solarMasses"], "PlanetClass": None, "TerraformState": None,
                "MassEM": None}
    if b.get("type") == "Planet":
        m = re.match(r"^Class (\w+) gas giant$", st)
        cls = SPANSH_PLANETS.get(st) or (f"Sudarsky class {m.group(1)} gas giant" if m else st)
        if not cls or b.get("earthMasses") is None:
            return None
        return {"StarType": None, "StellarMass": None, "PlanetClass": cls,
                "TerraformState": SPANSH_TERRAFORM.get(b.get("terraformingState"), ""), "MassEM": b["earthMasses"]}
    return None


def carto_values(r, scanned, f, scan_state, map_state, odyssey=True):
    """Cartographic credits for one body, as pairs of (with bonuses, bonus-free):

    now   what the data you hold would pay if sold now
    left  what is still there to add: an unscanned or lost scan, and an unmapped or lost map

    `scan_state` / `map_state` are pickup_judge verdicts (unsold / sold / lost) for your latest scan
    and your latest map; None when you have not scanned or mapped. Lost data counts as recoverable
    (scan and map it again); sold data is done. Bodies with pricing fields ("ed", from your scan or a
    Spansh dump) use outrider.unsold.body_value; the rest fall back to Spansh's search estimates.
    """
    planet = r.get("type") == "Planet"
    first_disc = bool(f and f["was_discovered"] == 0)
    first_map = bool(f and f["was_mapped"] == 0)
    if r.get("ed") and outrider.unsold:
        def price(bonus):
            body = dict(r["ed"], first_discovered=first_disc and bonus, first_mapped=first_map and bonus)
            return (outrider.unsold.body_value(body, False, False, odyssey),
                    outrider.unsold.body_value(body, True, False, odyssey) if planet else None)
        (scan_b, map_b), (scan_p, map_p) = price(True), price(False)
    else:   # Spansh's search-level estimates (scan, scan + map), no bonuses in them
        scan_b = scan_p = r.get("scan_value") or 0
        map_b = map_p = (r.get("value") or scan_b) if planet else None

    def split(scan, mapped):
        extra = max(0, (mapped or scan) - scan) if planet else 0     # what the map adds on top of the scan
        now = (scan if scan_state == "unsold" else 0) + (extra if map_state == "unsold" else 0)
        left = (scan if scan_state in (None, "lost") else 0) + (extra if planet and map_state in (None, "lost") else 0)
        return now, left
    (now, left), (now_nb, left_nb) = split(scan_b, map_b), split(scan_p, map_p)
    did_map = map_state in ("unsold", "sold")
    return {"now": now, "left": left, "now_nb": now_nb, "left_nb": left_nb,
            "value": (map_b if did_map else scan_b) if scanned else scan_b,
            "value_if_mapped": map_b if planet and not did_map else None,
            "base_value": map_p if planet else scan_p,
            "mapped": did_map, "first_mapped": did_map and first_map}


def short_name(parent, name):
    """'Smojoo AL-P c5-27 A 4' -> 'A 4' under the system; a lone main star keeps its name."""
    if name and parent and name.startswith(parent + " "):
        return name[len(parent) + 1:]
    return name


def split_ring_name(system, ring):
    """'Sys A 3 B Ring' -> ('A 3', 'B Ring')."""
    parts = short_name(system, ring).rsplit(" ", 2)
    if len(parts) == 3:
        return parts[0], f"{parts[1]} {parts[2]}"
    if len(parts) == 2:  # "Sys A Ring": a ring around the lone main star, whose record is named "Sys"
        return system, f"{parts[0]} {parts[1]}"
    return None, ring


# Journal and Spansh dumps say "LowTemperatureDiamond"/"Opal"; Spansh's search API and the
# game's UI say "Low Temperature Diamonds"/"Void Opal". Everything here uses the latter.
MINERAL_NAMES = {"LowTemperatureDiamond": "Low Temperature Diamonds", "Opal": "Void Opal"}
HOTSPOT_MINERALS = ["Alexandrite", "Benitoite", "Bromellite", "Grandidierite",
                    "Low Temperature Diamonds", "Monazite", "Musgravite", "Painite", "Platinum",
                    "Rhodplumsite", "Serendibite", "Tritium", "Void Opal"]
_MINERAL_BY_LOWER = {m.lower(): m for m in HOTSPOT_MINERALS} | {k.lower(): v for k, v in MINERAL_NAMES.items()}


def mineral_name(k):
    """The canonical hotspot name, whatever the case: the game writes both "tritium" and "Tritium"."""
    return MINERAL_NAMES.get(k) or _MINERAL_BY_LOWER.get((k or "").lower(), k)


def minerals(signals):
    """Ring hotspots, dropping any non-mineral $SAA_... entries."""
    return {mineral_name(k): v for k, v in (signals or {}).items() if not k.startswith("$")}


LIGHT_SPEED = 299792458.0       # m/s: journal distances are metres
AU_LS = 499.00478384            # light-seconds in an AU (Spansh orbits are in AU)
SOLAR_RADIUS_KM = 695700.0


def parents_full(parents):
    """A journal/Spansh Parents list -> [{kind: Star|Planet|Null|Ring, id}], nearest first. None if unknown."""
    if parents is None:
        return None
    return [{"kind": k, "id": v} for p in parents for k, v in p.items()]


def build_tree(system, bodies):
    """The system's hierarchy for the schematic view.

    `bodies` are rows with name (short), type, main, body_id and parents_full. Trust order: the
    Parents chain (Null entries are barycentres), then the body's name ('A 6 a' orbits 'A 6'; 'AB 1'
    orbits the A-B barycentre), then the main star. Returns nested nodes:
    {kind: body|barycentre|unknown, name|id, label, children: [...]}, children in orbital order.
    """
    names = {b["name"]: b for b in bodies}
    by_id = {b["body_id"]: b["name"] for b in bodies if b.get("body_id") is not None}
    parent = {}
    ref = lambda kind, i: ("n", i) if kind == "Null" else (("b", by_id[i]) if i in by_id else ("u", i))
    for b in bodies:
        chain = [p for p in b.get("parents_full") or [] if p["kind"] != "Ring"]
        cur = ("b", b["name"])
        for p in chain:
            k = ref(p["kind"], p["id"])
            if k == cur or cur in parent:
                break
            parent[cur] = k
            cur = k
    # direct star children of each barycentre give it its label ("A+B") and let names like "AB 1" find it
    kids = {}
    for c, par in parent.items():
        kids.setdefault(par, []).append(c)
    star_letters = lambda key: sorted(c[1] for c in kids.get(key, []) if c[0] == "b" and names[c[1]]["type"] == "Star")
    groups = {}
    for key in kids:
        if key[0] == "n":
            letters = star_letters(key)
            if letters and all(len(x) == 1 and x.isupper() for x in letters):
                groups.setdefault("".join(letters), key)
    main = next((b["name"] for b in bodies if b.get("main")), None)
    for b in bodies:
        k = ("b", b["name"])
        if k in parent or b.get("parents_full") == [] or b["name"] == main:
            continue    # placed by its Parents chain, or known to orbit nothing
        tokens = b["name"].split()
        found = None
        for i in range(len(tokens) - 1, 0, -1):
            cand = " ".join(tokens[:i])
            if cand in names and cand != b["name"]:
                found = ("b", cand)
                break
        if not found and len(tokens) > 1 and len(tokens[0]) > 1 and tokens[0].isalpha() and tokens[0].isupper():
            found = groups.get(tokens[0]) or ("g", tokens[0])   # 'AB 1': around the A-B barycentre
        if not found and b["type"] != "Star" and main and main != b["name"]:
            found = ("b", main)
        if found:
            parent[k] = found
    # assemble, guarding against cycles in odd data
    kids = {}
    for c, par in parent.items():
        kids.setdefault(par, []).append(c)
    everything = {("b", n) for n in names} | set(parent.values())
    def order(key):   # orbital order: body id, then distance from arrival, then the name
        b = names.get(key[1]) if key[0] == "b" else None
        bid = b.get("body_id") if b else key[1] if key[0] in "nu" else None
        return (bid if bid is not None else 10 ** 6, (b or {}).get("dist_ls") or 0, natural(str(key[1])))
    seen = set()

    def node(key):
        seen.add(key)
        children = [node(c) for c in sorted(kids.get(key, []), key=order) if c not in seen]
        if key[0] == "b":
            return {"kind": "body", "name": key[1], "children": children}
        if key[0] == "n":
            letters = star_letters(key)
            members = [c["name"] for c in children if c["kind"] == "body"]
            nested = [f"({c['label']})" for c in children if c["kind"] == "barycentre"]   # a pair inside this one
            if letters and all(len(x) == 1 and x.isupper() for x in letters):
                # lettered stars name the centre (A+B); planets circling the pair (AB 1) are not part of it
                parts = ["+".join(letters)]
            else:
                parts = [" + ".join(members)] if members else []
            label = "+".join(parts + nested) if parts or nested else f"barycentre #{key[1]}"
            return {"kind": "barycentre", "id": key[1], "label": label, "children": children}
        if key[0] == "g":
            return {"kind": "barycentre", "id": None, "label": "+".join(key[1]), "children": children}
        return {"kind": "unknown", "id": key[1], "label": f"body #{key[1]}", "children": children}

    roots = sorted((k for k in everything if k not in parent), key=order)
    tree = [node(k) for k in roots]
    tree += [node(k) for k in sorted(everything - seen, key=order) if k not in seen]  # cycle leftovers
    return tree, {c[1]: p for c, p in parent.items() if c[0] == "b"}


def record_from_search(system, b):
    st = b.get("subtype")
    return {"name": short_name(system, b.get("name")), "type": b.get("type"), "subtype": st,
            "main": bool(b.get("is_main_star")), "scoopable": subtype_scoopable(st),
            "terraformable": b.get("terraforming_state") in TERRAFORMABLE, "full": False,
            # Spansh's own credit estimates: what a scan is worth, and what scan+map is worth.
            "value": b.get("estimated_mapping_value"), "scan_value": b.get("estimated_scan_value"),
            "dist_ls": b.get("distance_to_arrival")}


def genus_label(g):
    """A genus from a Spansh dump ({name: ...} or '$Codex_Ent_..._Genus_Name;') -> its display name."""
    name = g.get("name") or g.get("genus") if isinstance(g, dict) else g
    return outrider.bio.genus_from_id(name) if outrider.bio else name


def record_from_dump(system, b):
    st = b.get("subType")
    signals = (b.get("signals") or {}).get("signals") or {}
    return {
        "name": short_name(system, b.get("name")), "type": b.get("type"), "subtype": st,
        "main": bool(b.get("mainStar")), "scoopable": subtype_scoopable(st),
        "terraformable": b.get("terraformingState") in TERRAFORMABLE,
        "landable": bool(b.get("isLandable")),
        "rings": [{"name": short_name(b.get("name"), r.get("name")), "type": r.get("type"),
                   "hotspots": minerals((r.get("signals") or {}).get("signals")), "mapped": "signals" in r,
                   "mass": r.get("mass"), "inner": r.get("innerRadius"), "outer": r.get("outerRadius")}
                  for r in b.get("rings") or []],
        "pressure": round(b["surfacePressure"], 4) if b.get("surfacePressure") is not None else None,
        "pressure_raw": b.get("surfacePressure"),   # the spawn rules' limits are finer than 0.0001 atm
        "belts": [r.get("type") for r in b.get("belts") or []],
        "bio": signals.get(BIO, 0), "geo": signals.get(GEO, 0), "mining": signals.get(MINING, 0), "full": True,
        "gravity": round(b["gravity"], 2) if b.get("gravity") is not None else None,
        "gravity_raw": b.get("gravity"),   # the spawn rules' limits are finer than 0.01 g
        "atmosphere": b.get("atmosphereType"), "dist_ls": b.get("distanceToArrival"),
        "temperature": b.get("surfaceTemperature"), "volcanism": b.get("volcanismType"),
        # Spansh lists the DSS's genera as objects in some dumps and as bare genus codes in others
        "genera": [genus_label(g) for g in (b.get("signals") or {}).get("genuses") or [] if g],
        # what the exobiology rules ask about beyond the basics (see outrider.bio)
        "body_id": b.get("bodyId"), "luminosity": b.get("luminosity"),
        "parents": [p["Star"] for p in b.get("parents") or [] if "Star" in p],
        "orbital_period_s": round(b["orbitalPeriod"] * 86400) if b.get("orbitalPeriod") else None,
        "atmo_comp": b.get("atmosphereComposition"),
        "materials": surface_materials(b.get("materials")),   # some bios' colours (and so their chances) depend on them
        # the system schematic: hierarchy, size, orbit
        "parents_full": parents_full(b.get("parents")),
        "radius_km": b.get("radius") or (b["solarRadius"] * SOLAR_RADIUS_KM if b.get("solarRadius") else None),
        "sma_ls": b["semiMajorAxis"] * AU_LS if b.get("semiMajorAxis") else None,
        "ed": ed_from_dump(b),   # priced with the same formula as your own scans (see carto_values)
        # when the body was last reported, and whether Spansh has a signals block for it at all: a pre-Odyssey
        # client reported no bio signals and marked thin-atmosphere worlds not landable (see stale_bio_body)
        "updated": b.get("updateTime"), "signals_known": "signals" in b,
    }


def record_from_scan(ev):
    """Journal Scan event -> body record (names still full; shortened when merged)."""
    name = ev.get("BodyName")
    if ev.get("StarType"):
        kind, subtype = "Star", journal_star(ev["StarType"])
    elif ev.get("PlanetClass"):
        kind, subtype = "Planet", journal_planet(ev["PlanetClass"])
    else:
        return None  # belt clusters and the like
    rings, belts = [], []
    for r in ev.get("Rings") or []:
        rtype = RING_CLASSES.get(r.get("RingClass"), r.get("RingClass"))
        if r.get("Name", "").endswith("Belt"):
            belts.append(rtype)
        else:
            rings.append({"name": short_name(name, r.get("Name")), "type": rtype, "hotspots": {},
                          "mass": r.get("MassMT"), "inner": r.get("InnerRad"), "outer": r.get("OuterRad")})
    g = ev.get("SurfaceGravity")
    return {
        "name": name, "type": kind, "subtype": subtype,
        "main": kind == "Star" and not ev.get("DistanceFromArrivalLS"),
        "scoopable": kind == "Star" and class_scoopable(ev["StarType"]),
        "terraformable": ev.get("TerraformState") in TERRAFORMABLE,
        "landable": bool(ev.get("Landable")),
        "rings": rings, "belts": belts, "bio": 0, "geo": 0, "full": True,
        "gravity": round(g / 9.80665, 2) if g else None,
        "gravity_raw": g / 9.80665 if g else None,   # the spawn rules' limits are finer than 0.01 g
        # "" is the journal's "no volcanism"; None (no key) is "not known", which rules nothing out
        "atmosphere": ev.get("AtmosphereType") or None, "volcanism": ev["Volcanism"] if "Volcanism" in ev else None,
        "dist_ls": ev.get("DistanceFromArrivalLS"), "temperature": ev.get("SurfaceTemperature"),
        "pressure": round(ev["SurfacePressure"] / 101325, 4) if ev.get("SurfacePressure") else (0 if "SurfacePressure" in ev else None),
        # the spawn rules' limits (0.00289 atm, 0.0161 ...) are finer than the 4 places kept above
        "pressure_raw": ev["SurfacePressure"] / 101325 if ev.get("SurfacePressure") else None,
        "was_discovered": ev.get("WasDiscovered"), "was_mapped": ev.get("WasMapped"),
        "scan_type": ev.get("ScanType"),
        "body_id": ev.get("BodyID"), "luminosity": ev.get("Luminosity"),
        "parents": [p["Star"] for p in ev.get("Parents") or [] if "Star" in p],
        "orbital_period_s": ev.get("OrbitalPeriod"),
        "parents_full": parents_full(ev.get("Parents")),
        "radius_km": ev["Radius"] / 1000 if ev.get("Radius") else None,
        "sma_ls": ev["SemiMajorAxis"] / LIGHT_SPEED if ev.get("SemiMajorAxis") else None,
        "atmo_comp": ({c["Name"]: c["Percent"] for c in ev.get("AtmosphereComposition") or []}
                      if "AtmosphereComposition" in ev else None),
        "materials": surface_materials(ev.get("Materials")),
        # what outrider.unsold.body_value needs to price it
        "ed": {k: ev.get(k) for k in ("StarType", "StellarMass", "PlanetClass", "TerraformState", "MassEM")},
    }


def own_data(db, id64, system):
    """Your own scans of a system: (records keyed by short name, ring hotspots, FSS body count)."""
    records = {}
    for row in db.execute("SELECT record FROM own_bodies WHERE system=?", (id64,)):
        r = json.loads(row["record"])
        r["name"] = short_name(system, r["name"])
        records[r["name"]] = r
    for row in db.execute("SELECT * FROM own_signals WHERE system=?", (id64,)):
        r = records.get(short_name(system, row["name"]))
        if r:
            r["bio"], r["geo"], r["mining"] = row["bio"], row["geo"], row["mining"] or 0
            r["signals_seen"] = True   # an FSS or DSS of yours counted its signals
    hotspots = {}
    for row in db.execute("SELECT * FROM own_ring_signals WHERE system=?", (id64,)):
        hotspots[split_ring_name(system, row["name"])] = json.loads(row["hotspots"])
    sysrow = db.execute("SELECT body_count FROM own_systems WHERE id64=?", (id64,)).fetchone()
    return records, hotspots, sysrow["body_count"] if sysrow else None


def merge_records(spansh, own, hotspots):
    """Spansh records overlaid with your own; your DSS ring hotspots win over Spansh's."""
    own_main = any(r.get("main") for r in own.values())
    out = {r["name"]: dict(r) for r in spansh if not (own_main and r.get("placeholder"))}
    for name, r in own.items():
        base = out.get(name)
        if base and not r.get("bio") and not r.get("geo"):
            # Your scan may predate the DSS that gave Spansh its signal counts.
            r = dict(r, bio=base.get("bio", 0), geo=base.get("geo", 0))
        if base and not r.get("mining") and base.get("mining"):
            r = dict(r, mining=base["mining"])   # Spansh has the count from someone else's FSS
        if base and base.get("signals_known"):
            r = dict(r, signals_known=True)      # someone's FSS counted its signals (unknown_bio_groups)
        if base:
            spansh_rings = {x["name"]: x for x in base.get("rings") or []}
            r = dict(r, rings=[dict(x, hotspots=x["hotspots"] or
                                    (spansh_rings.get(x["name"]) or {}).get("hotspots") or {},
                                    mapped=x.get("mapped") or (spansh_rings.get(x["name"]) or {}).get("mapped", False))
                               for x in r["rings"]],
                     value=base.get("value"), scan_value=base.get("scan_value"),
                     genera=r.get("genera") or base.get("genera"))
        out[name] = r
    for (body, ring), hs in hotspots.items():
        r = out.get(body)
        if not r:
            continue
        for x in r.get("rings") or []:
            if x["name"] == ring:
                x["hotspots"] = hs or x.get("hotspots") or {}
                x["mapped"] = True
    return sorted(out.values(), key=lambda r: natural(r["name"] or ""))


# --------------------------------------------------------------------------
# Journal reading
# --------------------------------------------------------------------------

CARRIER_SETTLE = 300   # s after a booked carrier jump's departure: by then it has arrived


def carrier_seen(c, system, id64, ts, jumped=False):
    """The journal says where your carrier is (CarrierLocation, docking at it, CarrierJump aboard).

    moved_ts changes only when it is somewhere new: the page announces an arrival on that, so the
    CarrierLocation written at every login and every dock at the carrier stay quiet. A booked jump
    survives both (the carrier is still there, waiting to go); it ends when the carrier has moved, when
    you ride the jump, or when the carrier is still here well after the departure (it did not go).
    """
    pl = c.get("planned")
    try:
        gone = bool(pl and pl.get("departure")) and ts_seconds(ts) > ts_seconds(pl["departure"]) + CARRIER_SETTLE
    except (TypeError, ValueError):
        gone = False
    if id64 != c.get("id64"):
        c.update(system=system, id64=id64, x=None, y=None, z=None, moved_ts=ts, planned=None)
    elif jumped or gone:
        c["planned"] = None
    c.update(ts=ts, assumed=False)


def surface_m(lat1, lon1, lat2, lon2, radius):
    """Great-circle metres between two latitude/longitude points on a body of `radius` m."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


# A biology codex entry's variant name: $Codex_Ent_<Genus>_<NN>_<variant>_Name; (the species is $Codex_Ent_<Genus>_<NN>_Name;)
BIO_CODEX_RE = re.compile(r"^\$Codex_Ent_([A-Za-z]+)_(\d+)(?:_\w+)?_Name;$")


def surface_bearing(lat1, lon1, lat2, lon2):
    """The initial great-circle bearing, degrees from north, from the first point to the second."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


REL_SECTORS = ("ahead", "ahead on your right", "on your right", "behind on your right", "behind you",
               "behind on your left", "on your left", "ahead on your left")
COMPASS = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")


def which_way(bearing, heading=None):
    """Where something at `bearing` is, in eight sectors: relative to your `heading` when it is known ("behind on
    your left"), else by the compass ("to the north-east")."""
    if heading is None:
        return "to the " + COMPASS[int(((bearing % 360) + 22.5) // 45) % 8]
    return REL_SECTORS[int((((bearing - heading) % 360) + 22.5) // 45) % 8]


def surface_offset(lat, lon, bearing, dist, radius):
    """The point `dist` m from lat/lon along `bearing` (degrees from north) on a body of `radius` m."""
    p1, l1, b, d = math.radians(lat), math.radians(lon), math.radians(bearing), dist / radius
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def lose_rigs(db, ts, where, args=()):
    """Rigs out that the game has taken away (left behind on a body, or past the 5 km leash): picked up as lost.
    One that collected nothing is forgotten; one with tons stays as a saved site. The ids lost."""
    ids = [r[0] for r in db.execute(f"SELECT id FROM surface_rigs WHERE picked_ts IS NULL AND {where}", args)]
    for i in ids:
        db.execute("UPDATE surface_rigs SET picked_ts=?, lost=1 WHERE id=?", (ts, i))
    db.execute("DELETE FROM surface_rigs WHERE picked_ts IS NOT NULL AND tons = 0")
    return ids


def rig_full(rig, now):
    """Whether a rig out is probably full: RIG_FULL_S since it was placed or last collected from."""
    try:
        return now - ts_seconds(rig["last_ts"] or rig["placed_ts"]) >= RIG_FULL_S
    except (TypeError, ValueError):
        return False


class Journals:
    """Incremental reader: each file is read from where the last pass stopped."""

    def __init__(self, db):
        self.db = db
        self.jump_class = {}       # id64 -> StarClass from the StartJump heading there
        self.arrival_scan = None   # the latest arrival-star Scan: {id64, was_discovered, ts}
        self.status_json = None    # live Status.json: {fuel_main, fuel_reservoir, ts}
        self.bio_sales_changed = False
        self.target = None         # latest FSDTarget, cleared on arrival
        self.dirty = set()         # systems whose own scan data changed since last looked
        self.sales_changed = False  # a sale or death: every row's discovery status may change
        self.new_sales = []        # (ts, kind) of the sales read since State last stamped their estimates
        self.materials_changed = False
        self.cmdr_changed = False
        self.bad_files = set()     # journals that could not be read (reported once each)
        # recent moments the page may announce: {seq, ts, kind, ...}; kinds: scan, bio (a body worth a
        # look, priced by State), heat, interdicted, undocked (the undock warning). seq only grows; the page remembers the last it saw.
        self.moments = collections.deque(maxlen=16)
        self.jump_arrival = None   # the latest hyperspace arrival {id64, name, ts} (auto honk)
        self.supercruise_entry = None   # the latest SupercruiseEntry {id64, ts} (auto-target's danger wait)
        self.last_honk = None      # the latest discovery scan {id64, ts, bodies, progress}
        self.last_all_found = None # the latest FSSAllBodiesFound {id64, ts}
        self.moment_seq = 0
        self.last_heat = None      # seconds of the latest heat moment (HeatDamage within HEAT_QUIET adds none)
        # in memory only (a restart forgets them, which errs on the quiet side):
        self.body_touched = set()  # (system, body_id) touched down, disembarked or sampled on since arriving there
        self.approached = set()    # (system, body_id) briefed on approach this game session (once each)
        self.brief_key = None      # (id64, arrival ts) of the latest arrival briefing: one per arrival
        self.last_start_jump = None  # ts of the latest hyperspace StartJump (a scoop cut short by a jump is not news)
        self.last_shutdown = None  # ts of the latest Shutdown read (the quit backup)
        self.line_source = ""      # "file:offset" of the journal line being handled (read_file sets it)
        self.uploads = None        # the uploaders' hub (outrider.uploads.UploadHub), set by the server
        self.upload_mode = None    # what scan_dir lets the hub do with the lines it reads ("catchup", "live")
        self.regions_said = set()  # galactic regions announced (or left) this game session: see note_region
        self.region_entered = None  # the latest region crossing {id64, ts, region, spoken, count}
        self.jumponium = None      # this system's best jumponium body so far {system, body, material, pct, said}
        # a live sale still coming in (a 'Sell all' writes a page every 10 s to a minute or so): State.maybe_sale_left
        # says what it left aboard once the pages stop. {carto, systems, bio, species, read_at (wall clock)}
        self.sale_run = None
        # the Rhino collection under way (live lines only, see note_burst): {system, body_id, body, start, last,
        # lat, lon, target: ("rig" | "site", id), n, minerals {name: tons}, tons, said}
        self.burst = None
        self._hw_rows = (None, [])   # (route id, highway_route rows): the Highway's route, read once per plot
        self._rc_rows = (None, [])   # (route id, riches_route rows with their bodies): Road to Riches, read once per plot
        self.cargo_version = 0     # bumped by every cargo change (the ship's hold, a carrier event or market read)
        self.reload()

    def moment(self, kind, ts, **kw):
        self.moment_seq += 1
        self.moments.append(dict(kw, seq=self.moment_seq, ts=ts, kind=kind))

    def fresh(self, key, ts, current=None):
        """False for an event older than the newest one already applied to `key` (docked, carrier, boost...).
        Journals can be read out of order: a legacy folder mounted or configured later is imported after
        the live data, and a re-read goes through each live folder in turn. `current` is the timestamp the
        state itself carries, so a database from before this watermark existed is guarded too."""
        if ts < max(self.state_ts.get(key, ""), current or ""):
            return False
        if ts > self.state_ts.get(key, ""):
            self.state_ts[key] = ts
            meta_set(self.db, "state_ts", self.state_ts)
        return True

    def engineer_craft(self, ev, ts):
        """An EngineerCraft: the game writes no Loadout until the next login or outfitting visit, so a craft that
        changes a module's mass (lightweight, heavy duty...) or the drive's optimal mass or MaxFuelPerJump moves
        the range and the unladen mass now, worked out from its modifiers (a value the last Loadout didn't list was
        at the craft's OriginalValue). The older pace samples are dropped as on a refit. A modifier the
        module had that the new blueprint doesn't list is back to a stock value the event doesn't give: then
        nothing changes until the next Loadout (the old behaviour)."""
        ship, slot = self.ship, ev.get("Slot")
        if not ship or "mod_mass" not in ship or not ship.get("unladen") or not ship.get("max_range") or not slot:
            return
        fsd = slot == "FrameShiftDrive"
        if fsd and (ev.get("Module") or "").lower() != (ship.get("fsd") or "").lower():
            return
        mods = {m["Label"]: m for m in ev.get("Modifiers") or [] if m.get("Label") in (FSD_RANGE_MODS if fsd else ("Mass",))
                and isinstance(m.get("Value"), (int, float)) and isinstance(m.get("OriginalValue"), (int, float))}
        had = set(ship["fsd_mods"] if fsd else ()) | ({"Mass"} if slot in ship["mod_mass"] else set())
        if not mods and not had:
            return   # nothing that moves the range (a faster boot, a clean drive...)
        new = {k: m["Value"] for k, m in mods.items()}
        old = {k: m["OriginalValue"] for k, m in mods.items()}
        old.update({k: v for k, v in (ship["fsd_mods"] if fsd else {}).items() if k in new})
        if "Mass" in new and slot in ship["mod_mass"]:
            old["Mass"] = ship["mod_mass"][slot]
        if had - set(new) or not all(old.values()) or ts <= (ship.get("ts") or "") or not self.fresh("fuel_hist", ts):
            return
        model = fuel_model(ship, self.fuel_hist) or {}
        mf0 = old.get("MaxFuelPerJump") or ship.get("max_fuel") or model.get("max_fuel") or 0
        mf1 = new.get("MaxFuelPerJump", mf0)
        p = model.get("power")
        if mf1 != mf0 and not (p and mf0):
            return
        u0 = ship["unladen"]
        u1 = u0 + new.get("Mass", 0) - old.get("Mass", 0)
        b = ship.get("booster_ly") or 0
        # the range (booster apart) goes as optimal mass × MaxFuelPerJump^(1/p) / mass, at the unladen mass plus
        # one max jump's fuel (see fsd_range)
        r = (ship["max_range"] - b) * new.get("FSDOptimalMass", 1) / old.get("FSDOptimalMass", 1) \
            * (u0 + mf0) / (u1 + mf1) * ((mf1 / mf0) ** (1 / p) if mf1 != mf0 else 1) + b
        if "Mass" in new:
            ship["mod_mass"][slot] = new["Mass"]
        if fsd:
            ship.update(fsd_mods={k: v for k, v in new.items() if k != "Mass"},
                        max_fuel=new.get("MaxFuelPerJump", ship.get("max_fuel")))
        fit_key = [ship.get("fsd"), round(u1, 3), round(r, 4), bool((ship.get("fit_key") or [0] * 4)[3])]
        refit = fsd or refitted(ship.get("fit_key"), fit_key)
        ship.update(max_range=round(r, 4), unladen=round(u1, 3), fit_key=fit_key)
        meta_set(self.db, "ship", ship)
        if ts >= (self.jump_range or {}).get("ts", ""):
            self.jump_range = {"ly": ship["max_range"], "ts": ts}
            meta_set(self.db, "jump_range", self.jump_range)
        if refit:   # as a Loadout's refit: the older jumps were made at another mass or with another drive
            self.fuel_hist = []
            meta_set(self.db, "fuel_hist", [])

    def jump_cargo(self, ts):
        """The ship's hold (t) at a jump at ts: the journal's Cargo, else, before any Cargo was read, a live
        Status.json reading within JUMP_CARGO_S of the jump (the hold can't change in hyperspace), else None."""
        if self.cargo:
            return self.cargo.get("count")
        st = self.status_json or {}
        try:
            near = st.get("live") and abs(ts_seconds(st["ts"]) - ts_seconds(ts)) <= JUMP_CARGO_S
        except (KeyError, TypeError, ValueError):
            near = False
        return st.get("cargo") if near else None

    def spend_boost(self, ts):
        """A jet-cone charge is gone at ts (used by a jump, or lost with the ship)."""
        if self.fresh("boost", ts, (self.boost or {}).get("ts")) and self.boost:
            self.boost = None
            meta_set(self.db, "boost", None)

    def note_modules(self, ev, ts):
        """A Loadout: the core modules' health for its ship (a Loadout older than the one kept is ignored)."""
        sid = ev.get("ShipID")
        if sid is None or ts < (self.modules.get(str(sid)) or {}).get("ts", ""):
            return
        mods = {}
        for m in ev.get("Modules") or []:
            label = core_label(m.get("Slot"), m.get("Item"))
            if label and isinstance(m.get("Health"), (int, float)) and m.get("Slot"):
                mods[m["Slot"]] = {"label": label, "item": (m.get("Item") or "").lower(), "health": m["Health"],
                                   "ts": ts, "boosts": 0}
        self.modules[str(sid)] = {"ts": ts, "mods": mods}
        meta_set(self.db, "modules", self.modules)

    def note_fleet(self, ev, ts):
        """A Loadout: that ship's row in fleet_loadouts (the Highway's ship list), unless a newer Loadout is kept."""
        sid = ev.get("ShipID")
        if sid is None or not ev.get("Ship") or not_a_ship(ev.get("Ship")):
            return
        self.db.execute("""INSERT INTO fleet_loadouts (ship_id, name, ship_type, ident, ts, figures) VALUES (?, ?, ?, ?, ?, ?)
                           ON CONFLICT(ship_id) DO UPDATE SET name=excluded.name, ship_type=excluded.ship_type,
                             ident=excluded.ident, ts=excluded.ts, figures=excluded.figures
                           WHERE excluded.ts >= fleet_loadouts.ts""",
                        (sid, ev.get("ShipName") or None, ev.get("Ship"), ev.get("ShipIdent") or None, ts,
                         json.dumps(fleet_figures(ev))))

    def highway_route(self, hw):
        """The active route's rows (cached per plot: a new plot has a new id)."""
        if not hw:
            return []
        if self._hw_rows[0] != hw.get("id"):
            self._hw_rows = (hw.get("id"), [dict(r) for r in self.db.execute("SELECT * FROM highway_route ORDER BY idx")])
        return self._hw_rows[1]

    def riches_route(self, rc):
        """The active Road to Riches route's systems, each with its `bodies` (cached per plot: a new plot has a new id)."""
        if not rc:
            return []
        if self._rc_rows[0] != rc.get("id"):
            rows = [dict(r, bodies=[]) for r in self.db.execute("SELECT * FROM riches_route ORDER BY idx")]
            by = {r["idx"]: r for r in rows}
            bodies = {}
            for b in self.db.execute("SELECT * FROM riches_bodies ORDER BY idx, n"):
                if b["idx"] in by:
                    bodies[(b["idx"], b["n"])] = d = dict(b, species=[])
                    by[b["idx"]]["bodies"].append(d)
            for x in self.db.execute("SELECT * FROM riches_species ORDER BY idx, n, k"):
                if (x["idx"], x["n"]) in bodies:
                    bodies[(x["idx"], x["n"])]["species"].append(
                        {"genus": x["genus"], "species": x["species"], "value": x["value"], "count": x["count"]})
            for t in self.db.execute("SELECT * FROM trade_stops ORDER BY idx") if rc.get("kind") == "trade" else ():
                if t["idx"] in by:
                    by[t["idx"]].update(station=t["station"], market_id=t["market_id"], ls=t["ls"], updated=t["updated"],
                                        distance=t["distance"], sell=json.loads(t["sell"] or "[]"),
                                        buy=json.loads(t["buy"] or "[]"), profit=t["profit"], cumulative=t["cumulative"])
            self._rc_rows = (rc.get("id"), rows)
        return self._rc_rows[1]

    def riches_marks(self, id64):
        """(scanned, mapped): the norm_name'd names of the bodies of a system you have scanned / mapped, from the
        journal (own_bodies, own_mapped)."""
        scanned = {norm_name(r[0]) for r in self.db.execute("SELECT name FROM own_bodies WHERE system=?", (id64,))}
        mapped = {norm_name(r[0]) for r in self.db.execute(
            "SELECT b.name FROM own_mapped m JOIN own_bodies b ON b.system = m.system AND b.body_id = m.body_id "
            "WHERE m.system=?", (id64,))}
        return scanned, mapped

    def exo_sampled(self, id64):
        """{(BodyID, species name lower-cased)}: the species you have finished sampling in a system (the journal's)."""
        return {(r[0], (r[1] or "").lower()) for r in self.db.execute(
            "SELECT body_id, species_name FROM own_organic WHERE system=? AND done_ts IS NOT NULL", (id64,))}

    def riches_left(self, rc, rows, i):
        """What route row i still has to do, from the journal: Road to Riches, its bodies (scan, and the map when the
        route counts mapping); Exomastery, its (body, species) pairs not yet sampled, best first."""
        r = rows[i]
        if rc.get("kind") == "trade":   # the sales and purchases still to make at that stop (your MarketSell / MarketBuy)
            return trade_left(r, (rc.get("trade") or {}).get(str(i)))
        if rc.get("kind") == "exo":
            return exo_left(r["bodies"], self.exo_sampled(r["id64"]) if r["id64"] is not None else set())
        scanned, mapped = self.riches_marks(r["id64"]) if r["id64"] is not None else (set(), set())
        mapping = bool((rc.get("options") or {}).get("use_mapping_value"))
        return [b for b in todo(r["bodies"], scanned, mapped, mapping) if not b["done"]]

    def riches_arrival(self, id64, name, ts):
        """A jump into a system with a Road to Riches route active: progress (the row you are at, the furthest
        reached), the detour when the system is not on the route, back on it, and the end (the last system with nothing
        left to do there). Only arrivals newer than the position the route was plotted at (since_ts) and than the last
        one applied count, so a journal re-read never moves it; the spoken moments only for a jump just now
        (live_event). Same rules as highway_arrival."""
        rc = meta_get(self.db, "riches")
        if not rc:
            return
        since = rc.get("since_ts")
        if (ts < since if since else ts <= (rc.get("created_ts") or "")) or ts <= (rc.get("arrival_ts") or ""):
            return
        rows = self.riches_route(rc)
        if not rows:
            return
        exo, kind = rc.get("kind") == "exo", rc.get("kind") or "riches"
        text = trade_text if kind == "trade" else exo_text if exo else riches_text
        at, furthest, done = rc.get("at"), rc.get("furthest"), bool(rc.get("done_ts"))
        i = riches_match(rows, id64, name, at if at is not None else furthest or 0)
        rc["arrival_ts"] = ts
        say = None
        if i is None:
            rc["at"] = None
            if not done and furthest is not None and not rc.get("off_route"):
                rc["off_route"] = {"ts": ts, "system": name, "id64": id64}
                say = ("off_route", "Off route: detour.", 0)
        else:
            back = bool(rc.get("off_route"))
            rc.update(at=i, furthest=max(i, furthest if furthest is not None else i), off_route=None)
            left = self.riches_left(rc, rows, i)
            if done:
                pass   # finished: the route stays visible, quietly, until cleared
            elif not left and i == len(rows) - 1:
                rc.update(done_ts=ts, said_done=i)
                say = ("complete", trade_done_text(rows, i, (rc.get("trade") or {}).get(str(i))) if kind == "trade"
                       else text(rows, i, left), 0)
            else:
                if not left:
                    rc["said_done"] = i   # nothing to do here: no "all done" to say later
                say = ("back" if back else "next", ("Back on the route. " if back else "") + text(rows, i, left), len(left))
        meta_set(self.db, "riches", rc)
        if say and live_event(ts):
            nxt = rows[i + 1]["system"] if i is not None and i + 1 < len(rows) else None
            self.moment(kind, ts, what=say[0], text=say[1], system=name, index=i, next=nxt, left=say[2])

    def trade_progress(self, ev, ts):
        """A MarketSell or MarketBuy at the trade route's stop you are at: the trades made there, and once they are all
        made the hop's profit and the next stop, or the route's end (once; marked in meta whether or not it is spoken,
        so a re-read says nothing later)."""
        rc = meta_get(self.db, "riches")
        if not rc or rc.get("kind") != "trade" or rc.get("at") is None or rc.get("done_ts"):
            return
        since = rc.get("since_ts") or rc.get("created_ts") or ""
        if ts < since:
            return
        rows = self.riches_route(rc)
        i = rc["at"]
        if i >= len(rows):
            return
        if ev.get("MarketID") != rows[i].get("market_id"):
            # the next stop in the same system: no jump moves the route there (riches_arrival), so a trade at its
            # station does (review 2026-10-08 #5: a route with two stops in one system stalled at the first)
            j = i + 1
            while j < len(rows) and rows[j].get("system") == rows[i].get("system") \
                    and rows[j].get("market_id") != ev.get("MarketID"):
                j += 1
            if j >= len(rows) or rows[j].get("system") != rows[i].get("system"):
                return
            rc.update(at=j, furthest=max(j, rc.get("furthest") if rc.get("furthest") is not None else j))
            i = j
        sold = ev.get("event") == "MarketSell"
        wanted = {outrider.cargo.norm(c["name"]): c["name"] for c in rows[i].get("sell" if sold else "buy") or []}
        names = {outrider.cargo.norm(n) for n in (ev.get("Type_Localised"), ev.get("Type"), self.commodity_names.get(
            outrider.cargo.cid(ev.get("Type")))) if n}
        hit = next((wanted[n] for n in names if n in wanted), None)
        if not hit:
            return
        done = rc.setdefault("trade", {}).setdefault(str(i), {})
        # the tonnes, not just the name: one tonne of a hundred ticked the commodity off and could end the route
        # (Codex F4). Each journal line counts once: a re-read meets the same lines again
        line = self.line_source or f"{ts}|{ev.get('event')}|{ev.get('Type')}|{ev.get('Count')}"
        if line in done.setdefault("lines", []):
            return
        done["lines"].append(line)
        for k in ("sold", "bought"):
            done[k] = outrider.cargo.trade_counts(rows[i], done, k)
        key = "sold" if sold else "bought"
        done[key][hit] = done[key].get(hit, 0) + max(0, int(ev.get("Count") or 0))
        self.trade_stop_done(rc, rows, i, ts)

    def trade_left_stop(self, ev, ts):
        """Undocked from the trade route's stop you are at with part of its trades made: you moved on (the station had
        less than Spansh said, or you chose to), so the stop is done, said with what fell short."""
        rc = meta_get(self.db, "riches")
        if not rc or rc.get("kind") != "trade" or rc.get("at") is None or rc.get("done_ts"):
            return
        if ts < (rc.get("since_ts") or rc.get("created_ts") or ""):
            return
        rows = self.riches_route(rc)
        i = rc["at"]
        done = (rc.get("trade") or {}).get(str(i))
        if i >= len(rows) or ev.get("MarketID") != rows[i].get("market_id") or not done or done.get("left"):
            return
        if not any(outrider.cargo.trade_counts(rows[i], done, k) for k in ("sold", "bought")):
            return   # nothing traded here: not a stop you finished
        done["left"] = True
        self.trade_stop_done(rc, rows, i, ts)

    def trade_stop_done(self, rc, rows, i, ts):
        """Stop i's record changed: stored, and once nothing is left there the hop's profit (or what fell short) and the
        next stop are said, or the route's end (once)."""
        done = (rc.get("trade") or {}).get(str(i))
        if trade_left(rows[i], done) or rc.get("said_done") == i:
            meta_set(self.db, "riches", rc)
            return
        rc["said_done"] = i
        last = i == len(rows) - 1
        if last:
            rc["done_ts"] = ts
        meta_set(self.db, "riches", rc)
        if live_event(ts):
            self.moment("trade", ts, what="complete" if last else "done", system=rows[i]["system"], index=i,
                        next=None if last else rows[i + 1]["system"], left=0, text=trade_done_text(rows, i, done))

    def riches_progress(self, id64, ts):
        """After a Scan or a mapping in the system you are at on a Road to Riches route: when that was the last body
        to do, say so once (the next stop, or the end of the route). Marked in meta whether or not it is spoken, so a
        re-read says nothing later."""
        rc = meta_get(self.db, "riches")
        if not rc or rc.get("at") is None or rc.get("done_ts"):
            return
        rows = self.riches_route(rc)
        i = rc["at"]
        if i >= len(rows) or rows[i]["id64"] is None or rows[i]["id64"] != id64 or rc.get("said_done") == i:
            return
        exo = rc.get("kind") == "exo"
        if not (any(b.get("species") for b in rows[i]["bodies"]) if exo else rows[i]["bodies"]) or self.riches_left(rc, rows, i):
            return
        rc["said_done"] = i
        last = i == len(rows) - 1
        if last:
            rc["done_ts"] = ts
        meta_set(self.db, "riches", rc)
        if live_event(ts):
            nxt = None if last else rows[i + 1]["system"]
            done_text = "Every species here is sampled. " if exo else "Everything here is done. "
            self.moment("exo" if exo else "riches", ts, what="complete" if last else "done", system=rows[i]["system"], index=i,
                        next=nxt, left=0, text=done_text + (("Exomastery complete." if exo else "Road to Riches complete.") if last
                                                            else f"Next stop: {nxt}."))

    def highway_arrival(self, id64, name, ts):
        """A jump into a system with a Highway route active: progress (the row you are at, the furthest reached),
        the detour when the system is not on the route, back on it at any route system (neutron or not), and the
        end. Only arrivals newer than the position the route was plotted at (since_ts, a journal time: a jump the
        game wrote while the plot finished, not read yet, still counts) and than the last one applied count, so a
        journal re-read or a late legacy folder never moves it; the spoken moments only for a jump just now
        (live_event). A route stored before since_ts existed keeps the old rule (after created_ts, the wall clock)."""
        hw = meta_get(self.db, "highway")
        if not hw:
            return
        since = hw.get("since_ts")
        if (ts < since if since else ts <= (hw.get("created_ts") or "")) or ts <= (hw.get("arrival_ts") or ""):
            return
        rows = self.highway_route(hw)
        if not rows:
            return
        at, furthest, done = hw.get("at"), hw.get("furthest"), bool(hw.get("done_ts"))
        i = highway_match(rows, id64, name, at if at is not None else furthest or 0)
        hw["arrival_ts"] = ts
        say = None
        if i is None:
            hw["at"] = None
            # a detour once the route was joined (flying to its start is not one), said once until back on it
            if not done and furthest is not None and not hw.get("off_route"):
                hw["off_route"] = {"ts": ts, "system": name, "id64": id64}
                say = ("off_route", "Off route: detour.")
        else:
            back = bool(hw.get("off_route"))
            hw.update(at=i, furthest=max(i, furthest if furthest is not None else i), off_route=None)
            if done:
                pass   # finished: the route stays visible, quietly, until cleared
            elif i == len(rows) - 1:
                hw["done_ts"] = ts
                say = ("complete", "Highway complete.")
            else:
                say = ("back" if back else "next", ("Back on the highway. " if back else "") + highway_text(rows, i))
        meta_set(self.db, "highway", hw)
        if say and live_event(ts):
            nxt = rows[i + 1]["system"] if i is not None and i + 1 < len(rows) else None
            self.moment("highway", ts, what=say[0], text=say[1], system=name, index=i, next=nxt)

    def ship_modules(self):
        """The current ship's core module record ({slot: {...}}), or None."""
        sid = (self.ship or {}).get("ship_id")
        return (self.modules.get(str(sid)) or {}).get("mods") if sid is not None else None

    def modules_touch(self, ts, fn):
        """fn(module) for each core module of the current ship read before ts; saved when any changed."""
        mods = self.ship_modules()
        if mods and any([fn(m) for m in mods.values() if m["ts"] <= ts]):
            meta_set(self.db, "modules", self.modules)

    def modules_repaired(self, ts, items=None):
        """A repair: every core module (items None) or those whose item is in `items` are back to full health."""
        def fix(m):
            if items is None or m["item"] in items:
                m.update(health=1.0, ts=ts, boosts=0)
                return True
        self.modules_touch(ts, fix)

    def hull_repaired(self, ts):
        """Repair limpets: the journal does not say the new percentage (RepairDrone
        gives hull points, not a fraction), so the hull is unknown until the next Loadout or HullDamage
        rather than a guess. Also re-arms the page's hull alert."""
        h = self.hull
        if h and h.get("pct") is not None and h["pct"] < 100 and ts >= h.get("ts", ""):
            self.hull = {"pct": None, "ts": ts, "repaired": True}
            meta_set(self.db, "hull", self.hull)

    def settle_carrier(self, now):
        """A booked carrier jump CARRIER_SETTLE past its departure with no word from the journal (the game
        writes a CarrierLocation at the departure time, but only while it is running) has happened: the
        carrier is where it was booked to go, marked assumed until the next CarrierLocation confirms or
        corrects it. True when that changed anything."""
        c = self.carrier
        pl = c and c.get("planned")
        if not (pl and pl.get("departure") and pl.get("id64")):
            return False
        try:
            if now < ts_seconds(pl["departure"]) + CARRIER_SETTLE:
                return False
        except (TypeError, ValueError):
            return False
        c.update(system=pl.get("system"), id64=pl["id64"], x=None, y=None, z=None,
                 moved_ts=pl["departure"], planned=None, assumed=True)
        meta_set(self.db, "carrier", c)
        return True

    def checkpoint(self):
        """What handling lines changes in memory only. A failed tick restores it along with the database
        rollback and reload(), or the retry would announce its moments twice."""
        return (self.moment_seq, list(self.moments), self.last_heat,
                set(self.body_touched), set(self.approached), self.brief_key,
                set(self.regions_said), self.region_entered, self.jumponium, dict(self.sale_run or {}) or None,
                json.loads(json.dumps(self.burst)), self.uploads.snapshot() if self.uploads else None)

    def restore(self, cp):
        (self.moment_seq, moments, self.last_heat, touched, approached, self.brief_key,
         regions, self.region_entered, self.jumponium, self.sale_run, self.burst, uploads) = cp
        if self.uploads and uploads:
            self.uploads.restore(uploads)
        self.body_touched, self.approached, self.regions_said = set(touched), set(approached), set(regions)
        self.moments = collections.deque(moments, maxlen=self.moments.maxlen)

    def reload(self):
        """(Re)load everything the reader keeps in the database: file offsets and the meta state.

        Called at start, and after a failed tick is rolled back: memory must go back to what the
        database holds, or the retry would skip lines whose rows were rolled back (offsets already
        advanced) and count additive things twice (materials, fuel history, credits earned).
        """
        db = self.db
        self.new_sales = []   # a rolled-back tick reads its sales again
        self.offsets = {r["path"]: r["offset"] for r in db.execute("SELECT * FROM journal_files")}
        # the same journal in two folders (a legacy copy of the live folder, two Proton prefixes) is one
        # file: basename -> the path read furthest, so a copy continues where the other stopped
        self.twins = {}
        for path, off in self.offsets.items():
            b = os.path.basename(path)
            if off > self.offsets.get(self.twins.get(b), -1):
                self.twins[b] = path
        # key -> newest event applied to that piece of state (see fresh())
        self.state_ts = meta_get(db, "state_ts", {})
        self.pos = meta_get(db, "pos")
        self.prev = meta_get(db, "prev")  # the system you were in before this one
        self.ship = meta_get(db, "ship")            # {name, type, fuel_main, fuel_reserve, max_range, ts}
        self.fuel_hist = meta_get(db, "fuel_hist", [])   # recent [jump ly, fuel t, fuel left t, cargo t] (older: pairs)
        self.cargo = meta_get(db, "cargo")               # {count, ts}: tonnes in the ship's hold, from Cargo
        self.last_scoop = meta_get(db, "last_scoop")     # ts of the last FuelScoop
        self.carrier = meta_get(db, "carrier")      # your fleet carrier, see handle_ship
        self.last_event_ts = meta_get(db, "last_event_ts")  # newest journal line handled (freshness)
        # newest event that is not part of loading into the game (the menu's Commander, Materials, Rank...):
        # where the last session ended, crash or not, for the login's "away 3 days"
        self.last_play_ts = self._play_saved = meta_get(db, "last_play_ts")
        self.docked = meta_get(db, "docked")    # {station, type, services, market_id, ts} while docked
        self.jump_range = meta_get(db, "jump_range")
        # {name, fid, credits (at the last LoadGame), login_ts, earned (exploration sales since)}
        self.commander = meta_get(db, "commander")
        self.materials = meta_get(db, "materials") or outrider.materials.new_state()
        self.hull = meta_get(db, "hull")            # {pct, ts}: your ship's hull, from Loadout / HullDamage
        # core module health per ShipID (S5): {ship id: {"ts": the Loadout, "mods": {slot: {label, item, health, ts,
        # boosts: jet-cone boosts since that reading}}}}, from Loadout, AfmuRepairs and repairs
        self.modules = meta_get(db, "modules", {})
        self.boost = meta_get(db, "boost")          # {value, ts}: a jet-cone charge, until the next FSDJump
        self.last_sale = meta_get(db, "last_sale")  # {ts, carto, bio, systems, species} of the latest sale
        # per game session (see session_key): {"at": the body you are at, "srv": the body your SRV is out on}
        self.srv_state = meta_get(db, "srv_state", {})
        # the SRV you are in ({srv_type, ts}: mev_rhino is the Rhino; srv_type None after a login in an SRV whose
        # launch the journals never showed), the body you are at ({system, body_id, name, ts}), and your ship's
        # landing spot ({system, body_id, lat, lon, ts}): the surface map and the co-pilot's rig marking
        self.vehicle = meta_get(db, "vehicle")
        self.body_here = meta_get(db, "body_here")
        self.ship_marker = meta_get(db, "ship_marker")
        # the last hop of the route the game plotted (NavRoute.json): a plain attribute, so auto-target's worker thread
        # can read it (it counts a multi-hop plot to the next Highway system as targeted, review F2)
        self.navroute_end = route_end(meta_get(db, "route"))
        # cargo (outrider/cargo.py): the ship's hold folded as it is read; the market you are docked at, for a
        # CargoTransfer (it names no carrier). Kept here, not taken from self.docked: a re-read replays the docks in
        # order, where docked keeps its newest. commodity_names: the journal's display names, learned (a cache, never
        # cleared: a re-read only learns them again).
        self.ship_cargo = meta_get(db, "ship_cargo") or outrider.cargo.new_ship()
        self.cargo_dock = meta_get(db, "cargo_dock")
        self.commodity_names = meta_get(db, "commodity_names", {})
        self.cargo_version += 1

    def import_legacy(self):
        for d in LEGACY_DIRS:
            if meta_get(self.db, f"legacy:{d}"):
                continue
            if not os.path.isdir(d):
                print(f"legacy journal dir not found, skipping: {d}", file=sys.stderr)
                continue
            n = self.scan_dir(d)
            meta_set(self.db, f"legacy:{d}", True)
            self.db.commit()
            print(f"imported {n} journal files from {d}")

    def scan_dir(self, d, commit_each=False, upload=None):
        """Read new data from every journal in d. Returns the number of files touched. commit_each: commit after every
        file (the start-up import: a stop part way keeps the files already read; review R13). upload: what the
        uploaders' hub may do with these lines: None (a legacy folder: nothing), "catchup" (the start-up scan: the
        session's state only) or "live" (the running tail: it may queue)."""
        self.upload_mode = upload
        try:
            return self._scan_dir(d, commit_each)
        finally:
            self.upload_mode = None

    def _scan_dir(self, d, commit_each):
        touched = 0
        # in time order: the old names (Journal.YYMMDDhhmmss.NN.log, before 2023) sort after every new one as text
        for path in sorted(glob(os.path.join(glob_escape(d), "Journal.*.log")), key=outrider.uploads.name_key):
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > self.start_offset(path):
                try:
                    self.read_file(path)
                except OSError as e:   # unreadable (permissions, a disk error): skip it, keep tailing the rest
                    if path not in self.bad_files:
                        self.bad_files.add(path)
                        print(f"journal skipped, cannot read it ({e.strerror or e}): {path}", file=sys.stderr)
                    continue
                self.bad_files.discard(path)
                touched += 1
                if commit_each:
                    self.db.commit()
        return touched

    def start_offset(self, path):
        """Where reading `path` starts: its own offset, or where another folder's copy of the same file was read
        up to when that is further (its events must not count twice). The furthest of the two, not just the
        twin's for a file first seen here: one file reachable by two paths, growing between the two reads,
        would otherwise get two offsets and be tailed twice from then on."""
        twin = self.twins.get(os.path.basename(path))
        return max(self.offsets.get(path, 0), self.offsets.get(twin, 0) if twin else 0)

    def read_file(self, path):
        start = self.start_offset(path)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read()
        # Only consume complete lines; the game may be mid-write on the last one.
        end = data.rfind(b"\n") + 1
        b = os.path.basename(path)
        pos = 0
        while pos < end:
            nl = data.index(b"\n", pos, end)
            line, at, pos = data[pos:nl], start + pos, nl + 1
            if self.uploads is not None and self.upload_mode and self.uploads.active():
                try:
                    self.uploads.line(path, at, line, self.upload_mode)   # before the filter: uploads want every event
                except sqlite3.Error:
                    raise                                              # the tick is rolled back and retried
                except Exception as e:                                 # never let it stop the tailing
                    print(f"uploads: a line was skipped ({type(e).__name__}: {e})", file=sys.stderr)
            elif self.uploads is not None and self.upload_mode:
                self.uploads.forget()   # not following now: switched on again, it reads the file from its top
            if any(w in line for w in WANTED) or b"Fixed_Event_Life" in line:
                # where the line is (the file's name, so a twin copy in another folder gives the same key):
                # tells apart sale pages written in the same second (sale_events)
                self.line_source = f"{b}:{at}"
                try:
                    self.handle(json.loads(line))
                except ValueError:
                    pass
                except (KeyError, TypeError, AttributeError, IndexError) as e:
                    # an event missing a field we index: skip it, not the file (database errors
                    # propagate so the tick is rolled back and retried with the offset unchanged)
                    print(f"journal line skipped ({type(e).__name__}: {e}): {line[:200]!r}", file=sys.stderr)
                finally:
                    self.line_source = ""
        if self.uploads is not None and self.upload_mode == "live":
            self.uploads.flush()   # the uploads' marks moved with these lines: stored in the same transaction
        self.db.execute("INSERT OR REPLACE INTO journal_files (path, offset) VALUES (?, ?)",
                        (path, start + end))
        self.offsets[path] = start + end
        if start + end > self.offsets.get(self.twins.get(b), -1):
            self.twins[b] = path
        if self.last_play_ts != self._play_saved:   # saved once per file read, not per line
            meta_set(self.db, "last_play_ts", self.last_play_ts)
            self._play_saved = self.last_play_ts
        if end and b'"timestamp":"' in data[:end]:
            ts = data[:end].rsplit(b'"timestamp":"', 1)[-1][:20].decode("ascii", "replace")
            if ts > (self.last_event_ts or ""):
                self.last_event_ts = ts
                meta_set(self.db, "last_event_ts", ts)

    def handle(self, ev):
        ts = ev.get("timestamp", "")
        name = ev.get("event")
        if name not in LOGIN_EVENTS and ts > (self.last_play_ts or ""):
            self.last_play_ts = ts
        if name in ("FSSSignalDiscovered", "SupercruiseDestinationDrop"):
            self.handle_phenomenon(name, ev, ts)
            return
        if name in CARGO_EVENTS:
            self.handle_cargo(name, ev, ts)
            if name in CARGO_ONLY:
                return
        if name == "SupercruiseEntry" and ts > (self.supercruise_entry or {}).get("ts", ""):
            self.supercruise_entry = {"id64": ev.get("SystemAddress"), "ts": ts}
        if name in SRV_TRACKED:
            self.track_srv(name, ev, ts)
            if name in SRV_EVENTS:
                return
        if name == "Loadout":
            if not_a_ship(ev.get("Ship")):
                return   # an Apex shuttle's: not your ship (it wiped the fuel model and replaced ship, range, hull)
            self.note_modules(ev, ts)
            self.note_fleet(ev, ts)
            if ev.get("HullHealth") is not None and ts >= (self.hull or {}).get("ts", ""):
                self.hull = {"pct": round(ev["HullHealth"] * 100), "ts": ts}
                meta_set(self.db, "hull", self.hull)
            if ev.get("MaxJumpRange") and ts >= (self.jump_range or {}).get("ts", ""):
                self.jump_range = {"ly": ev["MaxJumpRange"], "ts": ts}
                meta_set(self.db, "jump_range", self.jump_range)
                cap = ev.get("FuelCapacity") or {}
                mods = ev.get("Modules") or []
                fsd_mod = next((m for m in mods if m.get("Slot") == "FrameShiftDrive"), {})
                fsd = fsd_mod.get("Item", "")
                size = re.search(r"size(\d)", fsd)
                # an engineered drive may say its MaxFuelPerJump; otherwise the fuel model fits it from your jumps
                max_fuel = next((x.get("Value") for x in (fsd_mod.get("Engineering") or {}).get("Modifiers") or []
                                 if x.get("Label") == "MaxFuelPerJump"), None)
                # what engineering changed that moves the range, for an EngineerCraft before the next Loadout
                # (engineer_craft): the drive's optimal mass and MaxFuelPerJump, and each engineered module's mass
                fsd_mods = {x["Label"]: x["Value"] for x in (fsd_mod.get("Engineering") or {}).get("Modifiers") or []
                            if x.get("Label") in FSD_RANGE_MODS[:2] and isinstance(x.get("Value"), (int, float))}
                mod_mass = {m["Slot"]: x["Value"] for m in mods if m.get("Slot")
                            for x in (m.get("Engineering") or {}).get("Modifiers") or []
                            if x.get("Label") == "Mass" and isinstance(x.get("Value"), (int, float))}
                # a Guardian FSD booster adds a flat number of light years to every jump, while it is powered (one
                # switched off in the right-hand panel adds nothing: Codex F3, as fsd.py's fitting already had it)
                booster = next((re.search(r"size(\d)", m.get("Item", "").lower()) for m in mods
                                if "guardianfsdbooster" in m.get("Item", "").lower() and m.get("On") is not False), None)
                fit_key = [fsd, ev.get("UnladenMass") or 0, ev["MaxJumpRange"], bool(booster)]
                if self.ship and self.ship.get("ship_id") not in (None, ev.get("ShipID")):
                    # a different ship burns differently; its jumps count from the swap (None would count every
                    # FSD jump ever made as 'since the last scoop')
                    self.fuel_hist, self.last_scoop = [], ts
                    meta_set(self.db, "fuel_hist", []); meta_set(self.db, "last_scoop", ts)
                    self.fresh("fuel_hist", ts); self.fresh("last_scoop", ts)   # older samples are the old ship's
                elif self.ship and refitted(self.ship.get("fit_key"), fit_key):
                    # the same ship refitted (another drive, booster or mass): its older jumps would skew the fit
                    self.fuel_hist = []
                    meta_set(self.db, "fuel_hist", [])
                    self.fresh("fuel_hist", ts)
                self.ship = {"name": ev.get("ShipName") or ev.get("Ship"), "type": ev.get("Ship"),
                             "ship_id": ev.get("ShipID"),
                             "fuel_main": cap.get("Main"), "fuel_reserve": cap.get("Reserve"),
                             "max_range": ev["MaxJumpRange"], "fsd_size": int(size.group(1)) if size else None,
                             # the fuel model's inputs (see fuel_model): the mass without fuel or cargo, the drive
                             "unladen": ev.get("UnladenMass"), "fsd": fsd, "max_fuel": max_fuel, "fsd_mods": fsd_mods,
                             "mod_mass": mod_mass,
                             "booster_ly": GUARDIAN_BOOST.get(int(booster.group(1)), 0) if booster else 0,
                             "fit_key": fit_key,
                             "rebuy": ev.get("Rebuy"), "hull_value": ev.get("HullValue"), "modules_value": ev.get("ModulesValue"),
                             "cargo_capacity": ev.get("CargoCapacity"),
                             "ts": ts}
                meta_set(self.db, "ship", self.ship)
            return
        if name in CMDR_EVENTS:
            self.handle_cmdr(name, ev, ts)
            return
        if name == "Shutdown":   # a clean quit to the desktop (a crash writes nothing)
            # the session it ends (State adds the recap: jumps, light-years, firsts over login..now)
            c = self.commander or {}
            login = c.get("login_ts")
            if login and login <= (c.get("shutdown_ts") or ""):
                # no LoadGame since the last quit (quit from the main menu, a launcher check): this ends no
                # session, so no recap, and the Last session card stays on the one that did end
                login = None
            self.moment("game_exit", ts, login_ts=login)
            # the Last session card (History, Now) until the next login; State adds the numbers
            if login and ts >= (meta_get(self.db, "last_session") or {}).get("ts", ""):
                meta_set(self.db, "last_session", {"login_ts": login, "ts": ts})
            if self.commander is not None and ts > (c.get("shutdown_ts") or ""):
                c["shutdown_ts"] = ts
                meta_set(self.db, "commander", c)
            self.last_shutdown = ts   # an automatic backup, if this quit is live (State decides)
            return
        if name in BODY_EVENTS:
            self.handle_body(name, ev, ts)
            return
        if name == "EngineerCraft":
            self.engineer_craft(ev, ts)
        if name in MATERIAL_EVENTS:
            if outrider.materials.apply(self.materials, ev):
                meta_set(self.db, "materials", self.materials)
                self.materials_changed = True
            # no Synthesis mends the ship's hull: "Repair Basic" is the SRV's repair (only limpets and stations
            # repair the ship), so it must not make a known hull unknown or re-arm the hull alert
            return
        if name in SHIP_EVENTS and name != "CarrierJump":  # CarrierJump is also a position event
            self.handle_ship(name, ev, ts)
            return
        if name == "Location" and ev.get("Docked") and not ev.get("Taxi") and not ev.get("Multicrew"):
            # a session that starts docked (a login, a respawn after a death) writes no Docked event: the Location
            # line says Docked with the station's name, type, MarketID and services instead. It is a dock for the
            # hold's market and the docked state (review 2026-10-08 #2: a carrier transfer straight after logging in
            # at your carrier was dropped for want of a market). The position itself is handled below.
            self.handle_cargo("Docked", ev, ts)
            self.handle_ship("Docked", ev, ts)
        if name in STAR_CLASS_EVENTS:
            # Targeting a system reveals its main star class, even if nobody has scanned it.
            if ev.get("SystemAddress") and ev.get("StarClass"):
                self.db.execute("INSERT OR REPLACE INTO star_classes VALUES (?, ?)",
                                (ev["SystemAddress"], ev["StarClass"]))
            if name == "StartJump" and ev.get("SystemAddress"):
                self.jump_class = {ev["SystemAddress"]: ev.get("StarClass")}
            if name == "StartJump" and ev.get("JumpType") == "Hyperspace":   # the FSD is charging (not supercruise)
                self.flush_jumponium(ts)   # leaving with a jumponium body the FSS debrief never got to say
                self.moment("fsd_charge", ts, system=ev.get("StarSystem") or "", star_class=ev.get("StarClass") or "")
                self.last_start_jump = ts
            if name == "FSDTarget" and ev.get("SystemAddress") and self.fresh("target", ts, (self.target or {}).get("ts")):
                self.target = {"id64": ev["SystemAddress"], "name": ev.get("Name"),
                               "star_class": ev.get("StarClass"), "ts": ts}
            return
        if name in SCAN_EVENTS:
            self.handle_scan(name, ev, ts)
            if name in ("Scan", "SAAScanComplete", "ScanOrganic"):   # a body scanned / mapped, a species sampled
                self.riches_progress(ev.get("SystemAddress"), ts)
            return
        if name in DATA_EVENTS:
            if name == "Died":
                self.db.execute("INSERT OR IGNORE INTO deaths VALUES (?, NULL)", (ts,))
                # any sample in progress dies with you (not one begun after it: a journal read out of order)
                self.drop_runs("done_ts IS NULL AND (ts IS NULL OR ts <= ?)", (ts,), ts)
                self.bio_sales_changed = True
            elif name == "SellOrganicData":
                check = sale_check(self.db, ts, ev.get("BioData") or [], self.line_source)   # before this sale is stored
                self.db.execute("INSERT OR IGNORE INTO bio_sales (ts, species, bio_data, source) VALUES (?, ?, ?, ?)",
                                (ts, len(ev.get("BioData") or []), json.dumps(sale_species(ev.get("BioData") or [])),
                                 self.line_source))
                self.bio_sales_changed = True
                paid = sum((b.get("Value") or 0) + (b.get("Bonus") or 0) for b in ev.get("BioData") or [])
                self.add_earnings(ts, paid)
                self.db.execute("INSERT OR IGNORE INTO sale_events VALUES (?, 'bio', ?, ?, ?, 0, ?, ?, ?)",
                                (ts, sum(b.get("Value") or 0 for b in ev.get("BioData") or []),
                                 sum(b.get("Bonus") or 0 for b in ev.get("BioData") or []), paid, len(ev.get("BioData") or []),
                                 self.line_source, check and json.dumps(check)))
                self.new_sales.append((ts, "bio"))
                self.note_sale(ts, bio=paid, species=len(ev.get("BioData") or []))
                self.note_live_sale(ts, "bio", bio=paid, species=len(ev.get("BioData") or []))
            elif name == "Resurrect":
                death = self.db.execute("SELECT max(ts) FROM deaths WHERE ts <= ?", (ts,)).fetchone()[0]
                self.db.execute("UPDATE deaths SET option = ? WHERE ts = ?", (ev.get("Option"), death))
                # the ship-loss debrief (State works out what died with it at poll time; nothing when it cost
                # nothing). Only a Resurrect just now: a journal re-read or catch-up must not narrate old deaths.
                if death and live_event(ts):
                    self.moment("loss", ts, death_ts=death, option=ev.get("Option") or "")
                if ev.get("Option") not in SHIP_SURVIVED_OPTIONS:   # a replacement ship comes with a full tank
                    self.spend_boost(ts)   # and no jet-cone charge
                    if self.fresh("last_scoop", ts, self.last_scoop):
                        self.last_scoop = ts
                        meta_set(self.db, "last_scoop", ts)
                    if ts >= (self.hull or {}).get("ts", ""):
                        self.hull = {"pct": 100, "ts": ts}
                        meta_set(self.db, "hull", self.hull)
                    self.modules_repaired(ts)
            elif name == "MultiSellExplorationData":
                self.add_earnings(ts, ev.get("TotalEarnings") or 0)
                # one row per page (source): 'Sell all' writes several pages in the same second
                self.db.execute("INSERT OR IGNORE INTO sale_events VALUES (?, 'carto', ?, ?, ?, ?, 0, ?, NULL)",
                                (ts, ev.get("BaseValue"), ev.get("Bonus"), ev.get("TotalEarnings"), len(ev.get("Discovered") or []),
                                 self.line_source))
                self.new_sales.append((ts, "carto"))
                self.note_sale(ts, carto=ev.get("TotalEarnings") or 0, systems=len(ev.get("Discovered") or []))
                self.note_live_sale(ts, "carto", carto=ev.get("TotalEarnings") or 0, systems=len(ev.get("Discovered") or []))
                for d in ev.get("Discovered") or []:
                    self.db.execute("INSERT INTO sales VALUES (?, ?, ?)",
                                    (d.get("SystemName"), ts, d.get("NumBodies")))
            else:  # the pre-3.3 sale event: just a list of system names
                self.add_earnings(ts, ev.get("TotalEarnings") or 0)
                self.db.execute("INSERT OR IGNORE INTO sale_events VALUES (?, 'carto', ?, ?, ?, ?, 0, ?, NULL)",
                                (ts, ev.get("BaseValue"), ev.get("Bonus"), ev.get("TotalEarnings"), len(ev.get("Systems") or []),
                                 self.line_source))
                self.new_sales.append((ts, "carto"))
                self.note_live_sale(ts, "carto", carto=ev.get("TotalEarnings") or 0, systems=len(ev.get("Systems") or []))
                for sysname in ev.get("Systems") or []:
                    self.db.execute("INSERT INTO sales VALUES (?, ?, NULL)", (sysname, ts))
            self.sales_changed = True
            return
        id64, star_pos = ev.get("SystemAddress"), ev.get("StarPos")
        if id64 is None or not star_pos:
            return
        if isinstance(ev.get("Population"), int):
            self.db.execute("INSERT INTO system_population VALUES (?, ?, ?) ON CONFLICT(id64) DO UPDATE SET "
                            "population = excluded.population, ts = excluded.ts WHERE excluded.ts >= ts",
                            (id64, ev["Population"], ts))
        current = ts >= (self.pos or {}).get("ts", "")   # not an old arrival read after newer ones
        # A Location in the system you're already in (a relog) is not an arrival: not a visit, not movement. An older
        # line (a legacy folder imported after the live ones) is judged against the arrival before it, not against
        # where you are today (review 2026-10-08 #9: every old login counted as a visit and broke the flown path).
        if ev.get("event") != "Location":
            relog = False
        elif current:
            relog = bool(self.pos) and self.pos["id64"] == id64
        else:
            before = self.db.execute("SELECT id64 FROM jumps WHERE ts < ? ORDER BY ts DESC LIMIT 1", (ts,)).fetchone()
            relog = bool(before) and before["id64"] == id64
        # an Apex shuttle or another commander's ship (multicrew) moved you: where you are and the jump row
        # still count, but its fuel, its jump and its charge are not your ship's (no pace sample, no auto honk)
        ride = bool(ev.get("Taxi") or ev.get("Multicrew"))
        x, y, z = star_pos
        # a jump uses any charge taken before it: an older JetConeBoost read later is spent already. Arriving
        # without a jump (a respawn elsewhere) means the charged ship is gone too.
        if not ride and (name == "FSDJump" or (name == "Location" and not relog)):
            self.spend_boost(ts)
        if not ride and name == "FSDJump" and ev.get("FuelUsed") and ev.get("JumpDist") and not ev.get("BoostUsed") \
                and self.fresh("fuel_hist", ts):
            # boosted jumps (neutron cone, FSD injection) go further for the same fuel: not a pace sample.
            # [ly, fuel used, fuel left, cargo t] (the cargo from the journal's Cargo, None before any): the fuel
            # left and the cargo give the ship's mass at the jump, which the MaxFuelPerJump fit needs
            self.fuel_hist = (self.fuel_hist + [[ev["JumpDist"], ev["FuelUsed"], ev.get("FuelLevel"),
                                                 self.jump_cargo(ts)]])[-FUEL_HISTORY:]
            meta_set(self.db, "fuel_hist", self.fuel_hist)
        if name == "CarrierJump" and self.carrier and ev.get("MarketID") == self.carrier.get("id") \
                and self.fresh("carrier", ts, self.carrier_ts()):
            carrier_seen(self.carrier, ev.get("StarSystem"), id64, ts, jumped=True)
            self.carrier.update(x=x, y=y, z=z, services=ev.get("StationServices") or self.carrier.get("services"))
            meta_set(self.db, "carrier", self.carrier)
        self.db.execute(
            """INSERT INTO visits (id64, name, x, y, z, first_ts, last_ts, count)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(id64) DO UPDATE SET
                 count = count + ?,
                 first_ts = min(first_ts, excluded.first_ts),
                 last_ts = max(last_ts, excluded.last_ts)""",
            (id64, ev.get("StarSystem"), x, y, z, ts, ts, 0 if relog else 1))
        self.dirty.add(id64)
        if not relog:
            star = self.jump_class.pop(id64, None)
            if not star:
                row = self.db.execute("SELECT star_class FROM star_classes WHERE id64=?", (id64,)).fetchone()
                star = row["star_class"] if row else None
            # a return visit is 'visited' now: the game rarely writes an arrival-star Scan for a system you have
            # scanned before, so note_verdict (new / known, from that Scan) would never get to say it
            verdict = None
            if name in ("FSDJump", "CarrierJump") and self.db.execute(
                    "SELECT 1 FROM jumps WHERE id64=? AND ts < ? LIMIT 1", (id64, ts)).fetchone():
                verdict = "visited"
            self.db.execute("INSERT OR IGNORE INTO jumps (ts, id64, name, x, y, z, star_class, kind, verdict, ride) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (ts, id64, ev.get("StarSystem"), x, y, z, star, ev.get("event"), verdict, 1 if ride else None))
        if self.target and self.target["id64"] == id64 and current:
            self.target = None
        ns = meta_get(self.db, "next_stop")
        # arrived at the chosen next stop: an arrival after it was chosen, not an earlier visit being re-read
        if ns and ns.get("id64") == id64 and not relog and current and ts > (ns.get("set_ts") or ""):
            meta_set(self.db, "next_stop", None)
        if current:
            if name in ("FSDJump", "CarrierJump") and self.pos and self.pos["id64"] != id64:
                self.note_region(self.pos, id64, x, y, z, ts)
            if self.pos and self.pos["id64"] != id64:
                self.prev = self.pos
                meta_set(self.db, "prev", self.prev)
            # a relog keeps the arrival's ts: the briefing and the FSS warning are once per arrival, not per login
            self.pos = {"name": ev.get("StarSystem"), "id64": id64, "x": x, "y": y, "z": z,
                        "ts": self.pos["ts"] if relog else ts}
            meta_set(self.db, "pos", self.pos)
        if ev.get("event") == "FSDJump" and current and not ride:
            self.jump_arrival = {"id64": id64, "name": ev.get("StarSystem"), "ts": ts}
        # the Highway: a jump, or a Location that moves you (a respawn after a death, a login somewhere else: review
        # F10), not a relog where you already were
        if name in ("FSDJump", "CarrierJump", "Location") and current and not relog:
            self.highway_arrival(id64, ev.get("StarSystem"), ts)
            self.riches_arrival(id64, ev.get("StarSystem"), ts)

    def note_region(self, prev, id64, x, y, z, ts):
        """A jump from `prev` into a galactic region not announced this session: the arrival briefing opens with it
        (region_entered, read by State.arrival_facts) and a "region" moment speaks it when the briefing does not.
        Both regions join regions_said, so hopping back and forth along a border says nothing more. Nothing
        outside the region map, or when the previous position has no coordinates."""
        if not outrider.bio or prev.get("x") is None or x is None:
            return
        old, new = outrider.bio.region_name(prev["x"], prev["y"], prev["z"]), outrider.bio.region_name(x, y, z)
        if not new or new == old:
            return
        said, self.regions_said = new in self.regions_said, self.regions_said | {r for r in (old, new) if r}
        if said:
            return
        count = region_codex_count(self.db, new, outrider.bio.region_number(x, y, z))
        self.region_entered = {"id64": id64, "ts": ts, "region": new, "spoken": region_spoken(new), "count": count}
        self.moment("region", ts, system=str(id64), region=new, spoken=region_spoken(new), count=count)   # str: JSON rounds ids past 2^53

    def note_jumponium(self, system, ev, ts):
        """A new landable body carrying a material your FSD injections are short of (outrider.materials.jumponium_short),
        if it beats this system's best so far (a scarcer material, or a richer share of the same). Said with the
        FSS debrief (take_jumponium), or alone once the FSS is already done here, or when you leave or close the
        FSS unfinished (flush_jumponium). Nothing while the material counts are stale."""
        m = self.materials or {}
        if not m.get("snapshot_ts") or materials_stale(m, self.commander):
            return
        short = outrider.materials.jumponium_short(m.get("counts") or {})
        pick = outrider.materials.jumponium_pick(ev.get("Materials"), short)
        if not pick:
            return
        j = self.jumponium
        if j and j["system"] == system and (short.get(j["material"], 1e9), -j["pct"]) <= (short[pick["material"]], -pick["pct"]):
            return   # a body as good or better was already found here
        self.jumponium = dict(pick, system=system, body_id=ev["BodyID"], said=False,
                              body=short_name(ev.get("StarSystem") or (self.pos or {}).get("name"), ev.get("BodyName") or ""),
                              name=outrider.materials.display_name(m, pick["material"]))
        la = self.last_all_found
        if la and la["id64"] == system:   # the FSS debrief has been and gone: say it alone
            self.flush_jumponium(ts)

    def take_jumponium(self, system):
        """This system's jumponium body for the FSS debrief ({body, material, name, pct}), marked said; else None."""
        j = self.jumponium
        if not j or j["system"] != system or j["said"]:
            return None
        self.jumponium = dict(j, said=True)
        return {k: j[k] for k in ("body", "material", "name", "pct")}

    def flush_jumponium(self, ts, system=None):
        """A jumponium body not yet said (the FSS never completed): its own moment now."""
        j = self.jumponium
        if j and not j["said"] and (system is None or j["system"] == system):
            self.moment("jumponium", ts, system=j["system"], jumponium=self.take_jumponium(j["system"]))

    def handle_body(self, name, ev, ts):
        """ApproachBody (orbital cruise begins: the approach briefing, once per body per session), LeaveBody
        (back to supercruise: the unfinished-sampling warning) and Touchdown (you were on that body).
        LeaveBody, not Liftoff: Liftoff fires for every hop between sample sites, and when the ship is
        dismissed with you on foot."""
        system, body = ev.get("SystemAddress"), ev.get("BodyID")
        if system is None or body is None:
            return
        key = (system, body)
        if name == "Touchdown":
            self.body_touched.add(key)
        elif name == "ApproachBody":
            if key not in self.approached:
                self.approached.add(key)
                self.moment("approach", ts, system=system, body_id=body, body_name=ev.get("Body") or "")
        else:   # LeaveBody: untouched genera only nag when you were down on this body this visit
            # the Rhino's rigs stay behind and are gone (not rigs placed after this line: a journal re-read)
            lose_rigs(self.db, ts, "system=? AND body_id=? AND placed_ts <= ?", (system, body, ts))
            self.moment("left_body", ts, system=system, body_id=body, body_name=ev.get("Body") or "",
                        touched=key in self.body_touched)
            self.body_touched.discard(key)

    def session_key(self):
        """The game session the line being read belongs to: its journal's name without the part number
        (Journal.2026-09-30T023726 for Journal.2026-09-30T023726.01.log:1234). The SRV state is kept per session,
        so journals read out of order (a legacy folder imported later) never lend one session's SRV to another."""
        return re.sub(r"\.\d+\.log:\d*$", "", self.line_source)

    def track_srv(self, name, ev, ts):
        """Which body your SRV is out on, for MiningRefined (which names neither body nor position).
        The body you are at comes from ApproachBody, Touchdown, a SupercruiseExit at a planet or a Location on
        one; LaunchSRV puts the SRV on it, and a Location that says InSRV (a login in the SRV) does too.
        DockSRV, SRVDestroyed, supercruise, a login, a death, leaving the body or the system end it."""
        key = self.session_key()
        st = self.srv_state.get(key) or {"at": None, "srv": None}
        at, srv = st["at"], st["srv"]
        system, body = ev.get("SystemAddress"), ev.get("BodyID")
        here = {"system": system, "body_id": body} if system is not None and body is not None else None
        if name == "MiningRefined":
            self.mining_refined(srv, ev, ts)
            return
        self.track_vehicle(name, ev, ts)
        if name == "Liftoff":
            return
        if name in ("SRVDestroyed", "Died", "LoadGame"):
            # the Rhino's rigs go with it: destroyed, a death or a relog (not rigs placed after this line: a re-read)
            lose_rigs(self.db, ts, "placed_ts <= ?", (ts,))
        if name in ("ApproachBody", "Touchdown"):
            at = here or at
        elif name in ("SupercruiseExit", "Location"):
            at = here if ev.get("BodyType") == "Planet" else None
            if name == "Location":
                srv = dict(at, ts=ts) if at and ev.get("InSRV") else None
        elif name in ("LaunchSRV", "LaunchVessel"):   # the Nomad (LaunchVessel) too: it must not forget the body (F5)
            srv = dict(at, ts=ts) if at else None
        elif name in ("DockSRV", "SRVDestroyed", "SupercruiseEntry"):
            if name == "DockSRV":   # DockSRV names no body: the SRV's, before it is cleared
                here_now = self.body_here if (self.body_here or {}).get("system") is not None else None
                self.rigs_still_out(srv or at or here_now, ev, ts)
            srv = None
        else:   # LeaveBody, FSDJump, CarrierJump, LoadGame, Died
            at = srv = None
        if ts >= (self.body_here or {}).get("ts", "") and name != "SupercruiseEntry" and \
                (at or {}) != {k: v for k, v in (self.body_here or {}).items() if k in ("system", "body_id")}:
            self.body_here = dict(at, name=ev.get("Body") or ev.get("BodyName") or "", ts=ts) if at else None
            meta_set(self.db, "body_here", self.body_here)
        if st != {"at": at, "srv": srv}:
            self.srv_state[key] = {"at": at, "srv": srv}
            # this session and the latest few others only (journals read out of order)
            for old in [k for k in sorted(self.srv_state) if k != key][:-3]:
                del self.srv_state[old]
            meta_set(self.db, "srv_state", self.srv_state)

    def rigs_still_out(self, where, ev, ts):
        """Docking the Rhino with rigs still marked out on its body: a rigs_out moment (live only, so a re-read stays
        quiet) naming them and those probably full. It is Outrider's record, not the game's: the game writes nothing
        when a rig is picked up, so a rig picked up without a tap still counts (the surface map can remove it)."""
        if not where or (ev.get("SRVType") or "").lower() != RHINO or not live_event(ts):
            return
        rigs = [dict(r) for r in self.db.execute(
            "SELECT n, placed_ts, last_ts FROM surface_rigs WHERE system=? AND body_id=? AND picked_ts IS NULL "
            "AND placed_ts <= ? ORDER BY n", (where["system"], where["body_id"], ts))]
        if not rigs:
            return
        now = ts_seconds(ts)
        nums, full = [r["n"] for r in rigs], [r["n"] for r in rigs if rig_full(r, now)]
        names = lambda ns: (f"rig {ns[0]}" if len(ns) == 1 else
                            f"rigs {', '.join(str(n) for n in ns[:-1])} and {ns[-1]}")
        text = f"{names(nums).capitalize()} still marked out" + \
            ("." if not full else "; it is probably full." if len(nums) == 1 else
             f"; {names(full)} {'is' if len(full) == 1 else 'are'} probably full.")
        self.moment("rigs_out", ts, system=str(where["system"]), body_id=where["body_id"], rigs=nums, full=full, text=text)

    def track_vehicle(self, name, ev, ts):
        """The SRV you are in and your ship's landing spot, for the surface map and the co-pilot's rig marking.
        LaunchSRV names the SRV (mev_rhino is the Rhino); DockSRV, SRVDestroyed, a death or a Location outside an
        SRV end it. A login in an SRV (Location InSRV; LoadGame names the ship, not the SRV) keeps the type of the
        last SRV launched and never docked, else the type is unknown and the button keeps its usual gestures.
        The ship marker is your own ship's last Touchdown (not an Apex shuttle's, nor multicrew); a Liftoff clears it
        only when you are aboard (PlayerControlled): a ship dismissed from the ground is still recalled to you."""
        own = not (ev.get("Taxi") or ev.get("Multicrew"))
        if ts >= (self.vehicle or {}).get("ts", ""):
            v = self.vehicle
            if name in ("LaunchSRV", "LaunchVessel") and ev.get("PlayerControlled", True):   # the Nomad is a "vessel"
                v = {"srv_type": (ev.get("SRVType") or ev.get("VesselType") or "").lower() or None,
                     "label": ev.get("SRVType_Localised") or ev.get("VesselType_Localised"), "ts": ts}
            elif name in ("DockSRV", "SRVDestroyed", "Died"):
                v = None
            elif name == "Location":
                v = {"srv_type": (self.vehicle or {}).get("srv_type"), "label": (self.vehicle or {}).get("label"),
                     "ts": ts} if ev.get("InSRV") else None
            if v != self.vehicle:
                self.vehicle = v
                meta_set(self.db, "vehicle", v)
        m = self.ship_marker
        if ts < (m or {}).get("ts", ""):
            return
        if name == "Touchdown" and own and ev.get("Latitude") is not None and ev.get("SystemAddress") is not None:
            m = {"system": ev["SystemAddress"], "body_id": ev.get("BodyID"), "lat": ev["Latitude"],
                 "lon": ev["Longitude"], "ts": ts}
        elif name == "Liftoff" and own and ev.get("PlayerControlled", True):
            m = None
        elif name in ("LaunchSRV", "LaunchVessel") and live_event(ts):
            # an SRV (or the Nomad) leaves from the ship on the ground: its spot when no Touchdown on this body was seen (the
            # journals began after it, or the game wrote none)
            st, here = self.status_json or {}, self.body_here
            if here and st.get("live") and st.get("lat") is not None and st.get("body") == here.get("name") and \
                    not (m and (m["system"], m["body_id"]) == (here["system"], here["body_id"])):
                m = {"system": here["system"], "body_id": here["body_id"], "lat": st["lat"], "lon": st["lon"], "ts": ts}
        elif name in ("LeaveBody", "FSDJump", "CarrierJump", "Died"):
            m = None
        if m != self.ship_marker:
            self.ship_marker = m
            meta_set(self.db, "ship_marker", m)

    def mining_refined(self, srv, ev, ts):
        """1 t of a commodity refined by the SRV on the body it is out on; nothing when that body is unknown
        (a ship in a ring refines too, and an SRV launched before the journals being read began)."""
        commodity = re.sub(r"^\$|_name;$|;$", "", (ev.get("Type") or "").lower())
        if not srv or not commodity or ts < srv.get("ts", ""):
            return
        src = self.line_source
        cur = self.db.execute(
            """INSERT INTO own_mined VALUES (?, ?, ?, ?, 1, ?, ?, ?)
               ON CONFLICT (system, body_id, commodity) DO UPDATE SET tons = tons + 1, name = excluded.name,
                   first_ts = min(first_ts, excluded.first_ts), last_ts = max(last_ts, excluded.last_ts),
                   source = excluded.source
               WHERE excluded.source = '' OR own_mined.source IS NOT excluded.source""",
            (srv["system"], srv["body_id"], commodity, ev.get("Type_Localised") or commodity.title(), ts, ts, src))
        self.dirty.add(srv["system"])
        if cur.rowcount and live_event(ts):   # the same ton, placed on the surface map (live play only)
            self.note_burst(srv, ev.get("Type_Localised") or commodity.title(), ts)

    def note_burst(self, srv, mineral, ts):
        """One refined ton of a Rhino collection, counted where it was collected (the tons themselves are own_mined's,
        this only says where they came from). A ton after BURST_START_GAP s of quiet, or away from the collection
        under way (another rig), starts a collection, placed at the Status.json position of that moment and kept
        up to date while it runs (the Rhino settles over the rig as its refinery works): the nearest rig out on this
        body within RIG_MATCH_M is its rig, else it is an unmarked site (one within RIG_MATCH_M is reused), so good
        spots are kept without a press. Its tons add to that rig or site; State.watch_surface says them once
        BURST_END_GAP s pass with no more. The journal is read before Status.json in a tick, so the first ton can be
        placed from a reading taken while the Rhino was still driving onto the rig: a site this collection made from
        a reading older than its first ton moves onto a rig when a reading from within BURST_RETARGET_S of that ton
        finds one."""
        t = ts_seconds(ts)
        here, st = self.body_here or {}, self.status_json or {}
        name = here.get("name") if (here.get("system"), here.get("body_id")) == (srv["system"], srv["body_id"]) else None
        fix = fix_t = None
        try:
            if st.get("live") and st.get("lat") is not None and st.get("planet_radius") and \
                    (not name or st.get("body") == name) and abs(t - ts_seconds(st["ts"])) <= 90:
                fix, fix_t = (st["lat"], st["lon"], st["planet_radius"]), ts_seconds(st["ts"])
        except (TypeError, ValueError):
            fix = fix_t = None
        b = self.burst
        same = b and (b["system"], b["body_id"]) == (srv["system"], srv["body_id"]) and 0 <= t - b["last"] <= BURST_START_GAP
        if same and fix and b["placed"] and (b["target"] or ("",))[0] == "surface_sites" and \
                b.get("fix_t") is not None and b["fix_t"] < b["start"] and b["fix_t"] < fix_t <= b["start"] + BURST_RETARGET_S:
            rig = self.rig_near(b["system"], b["body_id"], fix[0], fix[1], fix[2])
            if rig:   # the site was the stale reading's: its tons go to the rig
                self.db.execute("DELETE FROM surface_sites WHERE id=?", (b["target"][1],))
                got = json.loads(rig["minerals"] or "{}")
                for m, n in b["minerals"].items():
                    got[m] = got.get(m, 0) + n
                self.db.execute("UPDATE surface_rigs SET minerals=?, tons=tons+?, last_ts=? WHERE id=?",
                                (json.dumps(got), b["tons"], ts, rig["id"]))
                b["target"], b["n"], b["placed"] = ("surface_rigs", rig["id"]), rig["n"], rig["site_lat"] is None
                b["lat"], b["lon"], b["fix_t"] = fix[0], fix[1], fix_t
        if same and fix and b["lat"] is not None and surface_m(fix[0], fix[1], b["lat"], b["lon"], fix[2]) > RIG_MATCH_M:
            same = False   # moved on to another rig within the minute
        if not same:
            if b and not b["said"]:
                self.end_burst(t, force=True)
            b = self.burst = {"system": srv["system"], "body_id": srv["body_id"], "body": name or st.get("body"),
                              "start": t, "last": t, "lat": fix and fix[0], "lon": fix and fix[1], "target": None,
                              "n": None, "minerals": {}, "tons": 0, "said": False, "placed": False, "fix_t": fix_t}
            if fix:
                b["target"], b["n"], b["placed"] = self.burst_target(b, fix[2], ts)
        elif fix:
            b["lat"], b["lon"] = fix[0], fix[1]
            if not b["target"]:   # no position when it began: placed now, with the tons so far
                b["target"], b["n"], b["placed"] = self.burst_target(b, fix[2], ts)
                table, rid = b["target"]
                row = self.db.execute(f"SELECT minerals FROM {table} WHERE id=?", (rid,)).fetchone()
                got = json.loads(row["minerals"] or "{}")
                for m, n in b["minerals"].items():
                    got[m] = got.get(m, 0) + n
                self.db.execute(f"UPDATE {table} SET minerals=?, tons=tons+? WHERE id=?", (json.dumps(got), b["tons"], rid))
        b["last"] = t
        b["minerals"][mineral] = b["minerals"].get(mineral, 0) + 1
        b["tons"] += 1
        if b["target"]:
            table, rid = b["target"]
            row = self.db.execute(f"SELECT minerals FROM {table} WHERE id=?", (rid,)).fetchone()
            if row:
                got = json.loads(row["minerals"] or "{}")
                got[mineral] = got.get(mineral, 0) + 1
                self.db.execute(f"UPDATE {table} SET minerals=?, tons=tons+1, last_ts=? WHERE id=?",
                                (json.dumps(got), ts, rid))
                if b["placed"]:   # this collection placed it: where the Rhino settled
                    cols = "site_lat=?, site_lon=?" if table == "surface_rigs" else "lat=?, lon=?"
                    self.db.execute(f"UPDATE {table} SET {cols} WHERE id=?", (b["lat"], b["lon"], rid))

    def rig_near(self, system, body_id, lat, lon, radius):
        """The nearest rig out on this body within RIG_MATCH_M of lat/lon (as marked, or where it was collected from),
        or None."""
        near = lambda rows: min(((min(surface_m(lat, lon, r[la], r[lo], radius)
                                      for la, lo in (("lat", "lon"), ("site_lat", "site_lon")) if r[la] is not None), r)
                                 for r in rows), key=lambda x: x[0], default=(None, None))
        d, rig = near(self.db.execute("SELECT id, n, lat, lon, site_lat, site_lon, minerals FROM surface_rigs "
                                      "WHERE system=? AND body_id=? AND picked_ts IS NULL", (system, body_id)).fetchall())
        return rig if rig is not None and d <= RIG_MATCH_M else None

    def burst_target(self, b, radius, ts):
        """The rig (or unmarked site) a collection at b's position belongs to: (table, id), the rig's number, and
        whether this collection places it (a rig's first collection, a new site)."""
        near = lambda rows: min(((surface_m(b["lat"], b["lon"], r["lat"], r["lon"], radius), r) for r in rows),
                                key=lambda x: x[0], default=(None, None))
        rig = self.rig_near(b["system"], b["body_id"], b["lat"], b["lon"], radius)
        if rig is not None:
            return ("surface_rigs", rig["id"]), rig["n"], rig["site_lat"] is None
        d, site = near(self.db.execute("SELECT id, lat, lon FROM surface_sites WHERE system=? AND body_id=?",
                                       (b["system"], b["body_id"])).fetchall())
        if site is not None and d <= RIG_MATCH_M:
            return ("surface_sites", site["id"]), None, False
        cur = self.db.execute("INSERT INTO surface_sites (system, body_id, body, lat, lon, minerals, tons, first_ts, last_ts) "
                              "VALUES (?, ?, ?, ?, ?, '{}', 0, ?, ?)", (b["system"], b["body_id"], b["body"], b["lat"], b["lon"], ts, ts))
        return ("surface_sites", cur.lastrowid), None, True

    def end_burst(self, now, force=False):
        """A collection quiet for BURST_END_GAP s (or cut short by the next): said once ("Rig 3: 12 tons of Water.").
        True when that happened."""
        b = self.burst
        if not b or (now - b["last"] <= BURST_END_GAP and not force):
            return False
        if now - b["last"] > BURST_START_GAP:
            self.burst = None
        if b["said"]:
            return False
        b["said"] = True
        what = " and ".join(f"{t} {'ton' if t == 1 else 'tons'} of {m}" for m, t in b["minerals"].items())
        if b["n"]:
            text = f"Rig {b['n']}: {what}."
        elif b["target"]:
            text = f"{what[0].upper()}{what[1:]}. No rig marked here; site saved."
        else:
            text = f"{what[0].upper()}{what[1:]}."
        self.moment("rig", iso_ts(now), what="collected", n=b["n"], tons=b["tons"], minerals=dict(b["minerals"]),
                    lat=b["lat"], lon=b["lon"], text=text)
        return True

    def drop_runs(self, where, args, ts):
        """Sample runs in progress that are gone (abandoned by a new species' Log, or died with you), with the surface
        map's points of each (those taken before ts: a later run of the same species keeps its own)."""
        for r in self.db.execute(f"SELECT system, body_id, species FROM own_organic WHERE {where}", args).fetchall():
            self.db.execute("DELETE FROM sample_points WHERE system=? AND body_id=? AND species=? AND ts <= ?",
                            (r["system"], r["body_id"], r["species"], ts))
        self.db.execute(f"DELETE FROM own_organic WHERE {where}", args)

    def note_sample_point(self, system, body, species, genus, kind, n, ts):
        """Remember where a sample was taken, from the live Status.json reading (at most a second old at
        walking pace). Only live play records positions: a journal read later has no position to pair with."""
        # Only points older than this line: a journal re-read replays the Log that began the run you are on,
        # and the points (kept through the re-read) must survive it.
        if kind == "Log":   # a new run: forget the old one's points
            self.db.execute("DELETE FROM sample_points WHERE system=? AND body_id=? AND species=? AND ts < ?",
                            (system, body, species, ts))
            # the codex entry the game writes with a first Log (the same second, just before it) is where you are
            # sampling, not a plant to go to (review #9): without its sample point it would point at your own feet
            try:
                since = iso_ts(ts_seconds(ts) - 5)
            except ValueError:
                since = ts
            self.db.execute("DELETE FROM bio_tags WHERE system=? AND body_id=? AND species=? AND ts BETWEEN ? AND ?",
                            (system, body, species, since, ts))
        if kind == "Analyse":   # the run is complete: nothing left to space
            self.db.execute("DELETE FROM sample_points WHERE system=? AND body_id=? AND species=? AND ts <= ?",
                            (system, body, species, ts))
            return
        st = self.status_json or {}
        if not st.get("live") or st.get("lat") is None or st.get("lon") is None or not st.get("ts"):
            return
        try:
            if abs(ts_seconds(ts) - ts_seconds(st["ts"])) > 90:   # the reading is not from this moment
                return
        except ValueError:
            return
        self.db.execute("INSERT OR REPLACE INTO sample_points VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (system, body, species, genus, n, st["lat"], st["lon"], ts))

    def note_bio_tag(self, ev, system, ts):
        """A biology CodexEntry (the composition scanner, or a first Log) is a waypoint for that species on that body
        (bio_tags): at the event's own position, else at yours from the live Status.json if it is this moment's
        reading over that same body. Nothing is stored without a position."""
        if ev.get("Category") != "$Codex_Category_Biology;" or ev.get("BodyID") is None or system is None:
            return
        name = str(ev.get("Name_Localised") or "").split(" - ")[0].strip() or None
        # the species and genus by name from the rules (the older variant-less species have no number in their codex
        # code: review #1), else from the code's own shape
        sp = outrider.bio.species_by_name(name) if outrider.bio else None
        m = BIO_CODEX_RE.match(ev.get("Name") or "")
        if sp:
            species, genus = sp["id"], sp["genus_id"]
        elif m:
            species, genus = f"$Codex_Ent_{m.group(1)}_{m.group(2)}_Name;", f"$Codex_Ent_{m.group(1)}_Genus_Name;"
        else:
            return
        lat, lon = ev.get("Latitude"), ev.get("Longitude")
        if lat is None or lon is None:
            st = self.status_json or {}
            row = self.db.execute("SELECT name FROM own_bodies WHERE system=? AND body_id=?", (system, ev["BodyID"])).fetchone()
            if not st.get("live") or st.get("lat") is None or not row or st.get("body") != row["name"] or not st.get("ts"):
                return
            try:
                if abs(ts_seconds(ts) - ts_seconds(st["ts"])) > 90:
                    return
            except ValueError:
                return
            lat, lon = st["lat"], st["lon"]
        self.db.execute("INSERT OR IGNORE INTO bio_tags VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (system, ev["BodyID"], species, genus, name, lat, lon, ts))

    def handle_phenomenon(self, name, ev, ts):
        """Notable stellar phenomena: found by the FSS, reached by dropping out of supercruise at one."""
        code = ev.get("SignalName") if name == "FSSSignalDiscovered" else ev.get("Type")
        m = re.match(r"^\$Fixed_Event_Life_(\w+?);?$", code or "")
        if not m:
            return
        kind = m.group(1).lower()
        if name == "FSSSignalDiscovered":
            system = ev.get("SystemAddress")
            if system is None:
                return
            self.db.execute("INSERT OR IGNORE INTO phenomena VALUES (?, ?, ?, NULL)", (system, kind, ts))
        elif self.pos and ts >= self.pos.get("ts", ""):   # the drop happens in the system you are in (not an old one read later)
            system = self.pos["id64"]
            self.db.execute("INSERT INTO phenomena VALUES (?, ?, ?, ?) ON CONFLICT(system, kind) "
                            "DO UPDATE SET reached_ts = coalesce(reached_ts, excluded.reached_ts)", (system, kind, ts, ts))
        else:
            return
        self.dirty.add(system)

    def handle_cmdr(self, name, ev, ts):
        c = self.commander or {}
        if name == "LoadGame":   # every login, old ones read out of order too (History's session windows)
            self.db.execute("INSERT OR IGNORE INTO logins VALUES (?)", (ts,))
        if ts < c.get("login_ts", ""):
            return   # an older login read out of order (legacy folders are imported after the fact)
        if name in ("Rank", "Progress", "Promotion"):
            key = "progress" if name == "Progress" else "rank"
            c[key] = dict(c.get(key) or {}, **{k: v for k, v in ev.items() if k in RANK_KEYS})
            if name == "Promotion":     # a new rank starts at 0%
                c["progress"] = dict(c.get("progress") or {}, **{k: 0 for k in ev if k in RANK_KEYS})
        elif name == "Statistics":
            meta_set(self.db, "statistics", {"ts": ts, "Exploration": ev.get("Exploration") or {},
                                             "Exobiology": ev.get("Exobiology") or {}})
            return
        elif name == "Commander":
            c.update(name=ev.get("Name") or c.get("name"), fid=ev.get("FID") or c.get("fid"))
        else:  # LoadGame: the credit balance at login is the baseline; sales since are added to it
            self.approached.clear()   # a new session: each body gets its approach briefing again
            self.regions_said = set()   # ... and each region crossing its line
            ship = ev.get("ShipName") or ev.get("Ship_Localised") or ev.get("Ship") or ""
            if not_a_ship(ev.get("Ship")):   # logged in on foot, in the SRV or a shuttle: your ship is still yours
                ship = (self.ship or {}).get("name") or ""
            # how long since the last session ended (its last event, the Shutdown or wherever a crash stopped it):
            # over AWAY_MIN_S the page greets you with what is at stake; a relog or mode switch gets the plain line
            since = max([t for t in (self.last_play_ts, c.get("shutdown_ts")) if t and t < ts], default=None)
            self.moment("game_start", ts, cmdr=ev.get("Commander") or c.get("name") or "", ship=ship,
                        mode=ev.get("GameMode") or "", away=away_text(ts_seconds(ts) - ts_seconds(since)) if since else None)
            c.update(name=ev.get("Commander") or c.get("name"), fid=ev.get("FID") or c.get("fid"),
                     credits=ev.get("Credits"), loan=ev.get("Loan"), login_ts=ts, earned=0,
                     mode=ev.get("GameMode"))
        self.commander = c
        self.cmdr_changed = True
        meta_set(self.db, "commander", c)

    def note_sale(self, ts, carto=0, bio=0, systems=0, species=0):
        """The latest sale, for the page's "what did I bank" line. Sales within ten minutes of each other
        (cartographics and exobiology at the same station) are one sale."""
        last = self.last_sale
        if last and ts < last["ts"]:
            return   # an older sale read out of order: the latest one stays the latest
        if last and ts_seconds(ts) - ts_seconds(last["ts"]) < 600:
            last = dict(last, ts=ts, carto=last["carto"] + carto, bio=last["bio"] + bio,
                        systems=last["systems"] + systems, species=last["species"] + species)
        else:
            last = {"ts": ts, "carto": carto, "bio": bio, "systems": systems, "species": species}
        self.last_sale = last
        meta_set(self.db, "last_sale", last)

    def note_live_sale(self, ts, kind, carto=0, bio=0, systems=0, species=0):
        """A sale just made (not one in a journal being re-read or caught up on): add it to the run of pages
        State.maybe_sale_left waits out before saying what is still aboard."""
        if not live_event(ts):
            return
        r = self.sale_run or {"carto": 0, "systems": 0, "bio": 0, "species": 0, "kinds": []}
        self.sale_run = dict(r, carto=r["carto"] + carto, systems=r["systems"] + systems, bio=r["bio"] + bio,
                             species=r["species"] + species, kinds=sorted(set(r["kinds"]) | {kind}), read_at=time.time())

    def add_earnings(self, ts, amount):
        c = self.commander
        if c and amount and ts >= c.get("login_ts", ""):
            c["earned"] = (c.get("earned") or 0) + int(amount)
            self.cmdr_changed = True
            meta_set(self.db, "commander", c)

    def handle_cargo(self, name, ev, ts):
        """The ship's hold (folded now, outrider.cargo.ship_apply) and your carrier's history (stored per journal line
        in cargo_events, folded when asked: State.cargo_summary). Docked and Undocked only keep the market you are at."""
        self.learn_names([ev] + (ev.get("Inventory") if name == "Cargo" and isinstance(ev.get("Inventory"), list) else []))
        if name in ("Docked", "Undocked"):
            if name == "Undocked" and not ev.get("Taxi") and not ev.get("Multicrew"):
                self.trade_left_stop(ev, ts)   # a trade stop left with part of its trades made
            at = ev.get("MarketID") if name == "Docked" and not ev.get("Taxi") and not ev.get("Multicrew") else None
            if at != self.cargo_dock:
                self.cargo_dock = at
                meta_set(self.db, "cargo_dock", at)
            return
        if name in ("MarketBuy", "MarketSell"):
            self.trade_progress(ev, ts)   # a trade route's stop: the trades made there
        if name in CARRIER_CARGO_EVENTS:
            market = ev.get("MarketID") if name in ("MarketBuy", "MarketSell") else \
                self.cargo_dock if name == "CargoTransfer" else ev.get("CarrierID")
            if name in ("CarrierStats", "CarrierTradeOrder") and ev.get("CarrierType", "FleetCarrier") != "FleetCarrier":
                market = None   # a squadron's carrier: not yours to track
            if market is not None:
                data = dict(ev, _at=self.cargo_dock) if name == "CargoTransfer" else ev
                if self.db.execute("INSERT OR IGNORE INTO cargo_events VALUES (?, ?, ?, ?, ?)",
                                   (self.line_source or f"{ts}:{name}", ts, name, market, json.dumps(data))).rowcount:
                    self.cargo_version += 1
        if name == "CarrierDepositFuel" and self.carrier and ev.get("CarrierID") == self.carrier.get("id") \
                and isinstance(ev.get("Total"), int) and self.fresh("carrier", ts, self.carrier_ts()):
            self.carrier["fuel"] = ev["Total"]   # the depot after it (the tile's tritium)
            self.carrier["stats_ts"] = max(self.carrier.get("stats_ts") or "", ts)
            meta_set(self.db, "carrier", self.carrier)
        sc = self.ship_cargo
        if ts < (sc.get("ts") or "") and name != "Cargo":
            return   # older than the hold already folded (a legacy folder read late)
        if name == "Cargo" and ts < (sc.get("snap_ts") or ""):
            return
        if name in ("MiningRefined", "CollectCargo", "EjectCargo") and self.vehicle \
                and ts >= (self.vehicle.get("ts") or ""):
            return   # the SRV's refinery and scoop (its own Cargo says Vessel SRV): not the ship's hold (review #8)
        if outrider.cargo.ship_apply(sc, ev):
            meta_set(self.db, "ship_cargo", sc)
            self.cargo_version += 1

    def learn_names(self, items):
        """Keep the commodity display names these events or inventory items give (outrider.cargo.learn)."""
        if any([outrider.cargo.learn(self.commodity_names, x) for x in items if isinstance(x, dict)]):
            meta_set(self.db, "commodity_names", self.commodity_names)

    def read_cargo_file(self, d):
        """Cargo.json: the ship's whole hold, rewritten with every Cargo event (which then lists only the count). True if
        it changed the hold. A file older than what is folded (another live folder's) is ignored."""
        try:
            with open(os.path.join(d, "Cargo.json"), encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            return False
        sc, ts = self.ship_cargo, c.get("timestamp") if isinstance(c, dict) else None
        if not isinstance(ts, str) or c.get("Vessel", "Ship") != "Ship" or not isinstance(c.get("Inventory"), list) \
                or ts < (sc.get("ts") or "") or ts < (sc.get("snap_ts") or ""):
            return False
        if ts == sc.get("snap_ts"):
            # the game rewrites the file for every change within the second: one with the snapshot's time is new when
            # it holds something else (a second canister collected in that second was lost)
            now = {outrider.cargo.cid(it.get("Name")): it.get("Count") for it in c["Inventory"] if isinstance(it, dict)}
            held = {i: line["count"] for i, line in (sc.get("lines") or {}).items() if line.get("count")}
            if now == held:
                return False
        self.learn_names(c["Inventory"])
        outrider.cargo.ship_snapshot(sc, c["Inventory"], c.get("Count"), ts)
        meta_set(self.db, "ship_cargo", sc)
        self.cargo_version += 1
        return True

    def read_market(self, d):
        """Market.json: kept when it is your carrier's (it lists the commodities with orders: a sell order's Stock is
        the holding). The game overwrites it at the next market, so each one is stored as it is read. True if new."""
        try:
            with open(os.path.join(d, "Market.json"), encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            return False
        c = self.carrier or {}
        if not isinstance(m, dict) or m.get("StationType") != "FleetCarrier" or m.get("MarketID") is None \
                or m.get("MarketID") != c.get("id") or not isinstance(m.get("Items"), list) \
                or not isinstance(m.get("timestamp"), str):
            return False
        if not self.db.execute("INSERT OR IGNORE INTO carrier_markets VALUES (?, ?, ?)",
                               (m["timestamp"], m["MarketID"], json.dumps(m["Items"]))).rowcount:
            return False
        self.cargo_version += 1
        return True

    def handle_ship(self, name, ev, ts):
        if name == "HullDamage":
            # your own ship only: the same event reports fighters (PlayerPilot false or Fighter true) and the SRV or the
            # Nomad you drive, whose lines carry no Fighter key at all (every ship line in the author's journals has
            # "Fighter": false; review F25)
            if ev.get("PlayerPilot") is False or ev.get("Fighter") or "Fighter" not in ev or ev.get("Health") is None:
                return
            if ts >= (self.hull or {}).get("ts", ""):
                self.hull = {"pct": round(ev["Health"] * 100), "ts": ts}
                meta_set(self.db, "hull", self.hull)
            return
        if name in ("RepairAll", "Repair"):
            # current journals list what was repaired (Items: ["Hull"], ["Wear"], ["Paint"]...); older ones say Item
            items = ev.get("Items") if isinstance(ev.get("Items"), list) else [ev["Item"]] if ev.get("Item") else []
            if (name == "RepairAll" or any(str(i).lower() in ("hull", "all", "wear") for i in items)) \
                    and ts >= (self.hull or {}).get("ts", ""):
                self.hull = {"pct": 100, "ts": ts}
                meta_set(self.db, "hull", self.hull)
            # the modules too: all of them on a RepairAll (or "All"), else the ones named ($int_..._name; or plain)
            names = {re.sub(r"^\$|_name;$", "", str(i).lower()) for i in items}
            self.modules_repaired(ts, None if name == "RepairAll" or "all" in names else names)
            return
        if name == "AfmuRepairs":
            item = re.sub(r"^\$|_name;$", "", str(ev.get("Module") or "").lower())
            if isinstance(ev.get("Health"), (int, float)):
                self.modules_touch(ts, lambda m: m["item"] == item and (m.update(health=ev["Health"], ts=ts, boosts=0) or True))
            return
        if name == "RepairDrone":
            if ev.get("HullRepaired"):
                self.hull_repaired(ts)
            return
        if name == "HeatDamage":
            # the game can log it every few seconds while overheating: at most one alert per HEAT_QUIET, not a
            # queue of danger sounds and speeches
            t = ts_seconds(ts)
            if self.last_heat is None or not 0 <= t - self.last_heat < HEAT_QUIET:
                self.moment("heat", ts)
                self.last_heat = t
            return
        if name == "NavRouteClear":
            if self.fresh("route", ts, (meta_get(self.db, "route") or {}).get("ts")):
                meta_set(self.db, "route", None)
                self.navroute_end = None
            return
        if name == "JetConeBoost":
            if self.fresh("boost", ts, (self.boost or {}).get("ts")):
                self.boost = {"value": ev.get("BoostValue") or 4.0, "ts": ts}   # the journal says how much (x4, x1.5...)
                meta_set(self.db, "boost", self.boost)
                self.moment("supercharged", ts, mult=self.boost["value"])
            # the module readings grow stale with every boost (the wear itself is only in the next Loadout)
            self.modules_touch(ts, lambda m: m["ts"] < ts and (m.update(boosts=m["boosts"] + 1) or True))
            return
        if name == "Interdicted":
            self.moment("interdicted", ts, by=ev.get("Interdictor_Localised") or ev.get("Interdictor") or "",
                        submitted=bool(ev.get("Submitted")), player=bool(ev.get("IsPlayer")))
            return
        if name == "Cargo":   # the hold's total (the SRV's hold is its own): the ship's mass, for the fuel model
            if ev.get("Vessel", "Ship") == "Ship" and isinstance(ev.get("Count"), (int, float)) \
                    and self.fresh("cargo", ts, (self.cargo or {}).get("ts")):
                self.cargo = {"count": ev["Count"], "ts": ts}
                meta_set(self.db, "cargo", self.cargo)
            return
        if name in ("FuelScoop", "RefuelAll", "RefuelPartial"):
            if self.fresh("last_scoop", ts, self.last_scoop):
                self.last_scoop = ts
                meta_set(self.db, "last_scoop", ts)
            return
        if name in ("Docked", "Undocked") and (ev.get("Taxi") or ev.get("Multicrew")):
            # an Apex shuttle or another commander's ship docking: nothing of yours to sell or repair there, so
            # no docked state and no dock or undock alerts. Riding one out of the station you were docked at
            # still means you have left it.
            if name == "Undocked" and self.docked and ev.get("StationName") == self.docked.get("station") \
                    and self.fresh("docked", ts, self.docked.get("ts")):
                self.docked = None
                meta_set(self.db, "docked", None)
            return
        # an older dock or undock read after newer ones (a legacy folder imported late, or a re-read: meta docked is
        # kept through it) does not change the docked state; an older Docked at your carrier still tells its services
        docked_fresh = name not in ("Docked", "Undocked") or self.fresh("docked", ts, (self.docked or {}).get("ts"))
        if name == "Undocked" and not docked_fresh:
            return
        if name == "Undocked":
            # the page's undock alert keys on this, not on Status.json (which reads 'not docked' on foot)
            d = self.docked or {}
            self.moment("undocked", ts, station=ev.get("StationName") or d.get("station") or "", dock_ts=d.get("ts"),
                        has_uc=bool(d.get("has_uc")), has_vista=bool(d.get("has_vista")))
            self.docked = None
            meta_set(self.db, "docked", None)
            return
        c = self.carrier or {}
        stale = lambda: not self.fresh("carrier", ts, self.carrier_ts())
        if name == "CarrierStats":
            if ev.get("CarrierType", "FleetCarrier") != "FleetCarrier" or stale():
                return
            if c.get("id") not in (None, ev.get("CarrierID")):
                c = {}   # another carrier (the old one decommissioned): nothing of the old one's place or plans
            c.update(id=ev.get("CarrierID"), name=ev.get("Name"), callsign=ev.get("Callsign"),
                     fuel=ev.get("FuelLevel"), jump_range=ev.get("JumpRangeCurr"), stats_ts=ts)
        elif name == "CarrierBuy":
            # a new carrier: its state starts here (its name comes with its first CarrierStats)
            if stale() or ev.get("CarrierID") is None:
                return
            c = {"id": ev.get("CarrierID"), "callsign": ev.get("Callsign"), "system": ev.get("Location"),
                 "id64": ev.get("SystemAddress"), "x": None, "y": None, "z": None, "ts": ts, "bought_ts": ts}
        elif name in ("CarrierDecommission", "CarrierCancelDecommission"):
            # decommissioning takes about a week (ScrapTime, epoch s) and can be cancelled until then; the scrapping
            # itself writes nothing, so after ScrapTime it is gone (the tile says so in red rather than vanish)
            if ev.get("CarrierID") != c.get("id") or stale():
                return
            scrap = ev.get("ScrapTime")
            c["decommission"] = None if name == "CarrierCancelDecommission" else {
                "ts": ts, "refund": ev.get("ScrapRefund"),
                "scrap_ts": iso_ts(scrap) if isinstance(scrap, (int, float)) and not isinstance(scrap, bool) else None}
            c["stats_ts"] = max(c.get("stats_ts") or "", ts)
        elif name == "CarrierLocation":
            # written at every login, and (since 2025) at the departure time of a booked jump
            if ev.get("CarrierType", "FleetCarrier") != "FleetCarrier" or ev.get("CarrierID") != c.get("id") or stale():
                return
            carrier_seen(c, ev.get("StarSystem"), ev.get("SystemAddress"), ts)
        elif name == "Docked":
            services = ev.get("StationServices") or []
            if docked_fresh:
                # a login (Location, Docked) at the station you were docked at: the same docking, its time kept, so the
                # page does not announce it again at every relog or mode switch
                same = ev.get("event") == "Location" and self.docked is not None and ev.get("MarketID") is not None \
                    and self.docked.get("market_id") == ev.get("MarketID")
                self.docked = {"station": ev.get("StationName"), "type": ev.get("StationType"),
                               "market_id": ev.get("MarketID"), "system": ev.get("StarSystem"),
                               "ts": self.docked["ts"] if same else ts,
                               "has_uc": "exploration" in services, "has_vista": "vistagenomics" in services}
                meta_set(self.db, "docked", self.docked)
            if ev.get("StationType") != "FleetCarrier" or ev.get("MarketID") != c.get("id") or stale():
                return
            carrier_seen(c, ev.get("StarSystem"), ev.get("SystemAddress"), ts)
            c.update(services=ev.get("StationServices") or c.get("services"))
        elif name == "CarrierJumpRequest":
            if ev.get("CarrierID") != c.get("id") or stale():
                return
            c["planned"] = {"system": ev.get("SystemName"), "id64": ev.get("SystemAddress"),
                            "departure": ev.get("DepartureTime"), "ts": ts}
        elif name == "CarrierJumpCancelled":
            if ev.get("CarrierID") != c.get("id") or stale():
                return
            c["planned"] = None
        elif name == "CarrierJump":
            return  # handled with the position events (it carries StarPos)
        if c:
            self.carrier = c
            meta_set(self.db, "carrier", c)

    def carrier_ts(self):
        """The newest journal time the carrier state carries (a database from before the watermark)."""
        c = self.carrier or {}
        return max(c.get("ts") or "", c.get("stats_ts") or "", (c.get("planned") or {}).get("ts") or "")

    def handle_scan(self, name, ev, ts):
        system = ev.get("SystemAddress")
        if system is None:
            return
        if name == "ScanOrganic":
            body, species, kind = ev.get("Body"), ev.get("Species"), ev.get("ScanType")
            if body is None or not species or kind not in ("Log", "Sample", "Analyse"):
                return
            row = self.db.execute("SELECT samples, done_ts FROM own_organic WHERE system=? AND body_id=? AND species=?",
                                  (system, body, species)).fetchone()
            samples, done = (row["samples"], row["done_ts"]) if row else (0, None)
            if kind == "Log":            # first sample of a run (a new run if this species was already done)
                samples, done = 1, None
                # a run at 2 of 3 elsewhere that this Log discards: a card (never spoken), only when read live, so a
                # re-read or catch-up does not bring back old losses
                if live_event(ts):
                    lost = self.db.execute(
                        "SELECT system, body_id, species_name, genus_name FROM own_organic WHERE done_ts IS NULL AND samples = 2"
                        " AND NOT (system=? AND body_id=? AND species=?) AND (ts IS NULL OR ts <= ?)",
                        (system, body, species, ts)).fetchone()
                    if lost:
                        b = self.db.execute("SELECT b.name, v.name AS sys FROM own_bodies b LEFT JOIN visits v ON v.id64 = b.system"
                                            " WHERE b.system=? AND b.body_id=?", (lost["system"], lost["body_id"])).fetchone()
                        self.moment("bio_dropped", ts, system=lost["system"], body_id=lost["body_id"],
                                    body=short_name(b["sys"], b["name"]) if b else "", elsewhere=lost["system"] != system,
                                    species=lost["species_name"] or "", genus=lost["genus_name"] or "")
                # only one sample run exists at a time: starting this one abandons any other (begun before it:
                # a journal read out of order must not abandon the run you are on)
                self.drop_runs("done_ts IS NULL AND NOT (system=? AND body_id=? AND species=?) AND (ts IS NULL OR ts <= ?)",
                               (system, body, species, ts), ts)
            elif kind == "Sample":
                samples = min(3, samples + 1)
            else:                        # Analyse: the run is complete
                samples, done = 3, ts
            self.db.execute(
                """INSERT OR REPLACE INTO own_organic VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (system, body, species, ev.get("Genus_Localised"), ev.get("Species_Localised"),
                 ev.get("Variant_Localised"), samples, done, ts))
            self.note_sample_point(system, body, species, ev.get("Genus"), kind, samples, ts)
            self.body_touched.add((system, body))
            if kind == "Analyse":   # "Stratum Tectonicas complete, 19.2 million; two left here" (priced by State)
                self.moment("bio_done", ts, system=system, body_id=body,
                            species=ev.get("Species_Localised") or "", genus=ev.get("Genus_Localised") or "")
            self.dirty.add(system)
            return
        if name == "CodexEntry":
            self.db.execute(
                "INSERT OR IGNORE INTO codex VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, ev.get("EntryID"), ev.get("Name_Localised") or ev.get("Name"),
                 ev.get("Category_Localised"), ev.get("SubCategory_Localised"), ev.get("Region_Localised"),
                 system, ev.get("System"), ev.get("BodyID"), int(bool(ev.get("IsNewEntry"))),
                 ev.get("NewTraitsDiscovered") and json.dumps(ev["NewTraitsDiscovered"]),
                 ev.get("VoucherAmount")))
            self.note_bio_tag(ev, system, ts)
            self.dirty.add(system)
            return
        if name == "ScanBaryCentre":
            if ev.get("BodyID") is not None:
                rec = {k: ev.get(k) for k in ("SemiMajorAxis", "Eccentricity", "OrbitalInclination",
                                              "OrbitalPeriod", "Periapsis", "AscendingNode", "MeanAnomaly")}
                self.db.execute("INSERT OR REPLACE INTO own_barycentres VALUES (?, ?, ?, ?)",
                                (system, ev["BodyID"], json.dumps(rec), ts))
                self.dirty.add(system)
            return
        if name == "Scan":
            record = record_from_scan(ev)
            if record and record["main"] and "WasDiscovered" in ev:
                self.arrival_scan = {"id64": system, "was_discovered": bool(ev["WasDiscovered"]), "ts": ts}
                self.note_verdict(system, ts, bool(ev["WasDiscovered"]))
            if record and ev.get("BodyID") is not None:
                # A body is news once: the Detailed rescan the game writes after mapping it (SAAScanComplete)
                # and AutoScans on a return visit replace the row but must not announce it again.
                known = self.db.execute("SELECT record FROM own_bodies WHERE system=? AND body_id=?",
                                        (system, ev["BodyID"])).fetchone()
                # an FSS (Detailed) of the body said its signals; a later AutoScan or nav-beacon read replacing the row
                # must not make them "not counted" again (review: "bio possible" on a body already checked)
                if known and record.get("scan_type") in NO_SIGNAL_SCANS:
                    try:
                        was = json.loads(known["record"]).get("scan_type")
                    except (TypeError, ValueError):
                        was = None
                    if was and was not in NO_SIGNAL_SCANS:
                        record["scan_type"] = was
                self.db.execute("INSERT OR REPLACE INTO own_bodies (system, body_id, name, record, ts, raw) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (system, ev["BodyID"], ev["BodyName"], json.dumps(record), ts, json.dumps(ev)))
                flag = lambda k: None if k not in ev else int(bool(ev[k]))
                undisc = ts if ev.get("WasDiscovered") is False else None
                if record["type"] == "Planet" and not known:
                    self.moment("scan", ts, system=system, body_id=ev["BodyID"])
                    if ev.get("Landable") and ev.get("Materials"):
                        self.note_jumponium(system, ev, ts)
                # a nav-beacon scan's Was* flags are not the game's record of the body (outrider.unsold skips them too):
                # it must not make a first discovery, a footfall flag or an unsold rescan time
                if ev.get("ScanType") not in NAV_BEACON_SCANS:
                    ff = flag("WasFootfalled")
                    pop = self.db.execute("SELECT population FROM system_population WHERE id64=?", (system,)).fetchone()
                    x5 = None if ff is None else int(ff == 0 and not (pop and (pop["population"] or 0) > 0))
                    self.db.execute(
                        """INSERT INTO own_firsts (system, body_id, name, is_main, was_discovered, was_mapped,
                                                   was_footfalled, first_ts, undisc_ts, bio_x5)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(system, body_id) DO UPDATE SET
                             undisc_ts = coalesce(excluded.undisc_ts, undisc_ts)""",
                        (system, ev["BodyID"], ev["BodyName"], int(record["main"]),
                         flag("WasDiscovered"), flag("WasMapped"), ff, ts, undisc, x5))
        elif name == "SAAScanComplete":
            if (ev.get("BodyName") or "").endswith(" Ring"):
                # A ring with no hotspots never gets an SAASignalsFound: this is the only record of the probe.
                self.db.execute("INSERT OR IGNORE INTO own_ring_signals VALUES (?, ?, '{}', ?)",
                                (system, ev["BodyName"], ts))
            elif ev.get("BodyID") is not None:
                # the "mapped" call-out (the page says it only with speak_mapped ticked): news once, so a remap
                # of a body already mapped adds no moment, as a rescan adds no "scan"
                known = self.db.execute("SELECT 1 FROM own_mapped WHERE system=? AND body_id=?",
                                        (system, ev["BodyID"])).fetchone()
                if not known:
                    self.moment("mapped", ts, system=system, body_id=ev["BodyID"], probes=ev.get("ProbesUsed"),
                                target=ev.get("EfficiencyTarget"))
                # first_ts: the first map, so a sale after it makes a later remap sold data (pickup_judge)
                self.db.execute("INSERT INTO own_mapped (system, body_id, ts, first_ts) VALUES (?, ?, ?, ?) "
                                "ON CONFLICT(system, body_id) DO UPDATE SET ts = excluded.ts, "
                                "first_ts = min(coalesce(first_ts, excluded.first_ts), excluded.first_ts)",
                                (system, ev["BodyID"], ts, ts))
        elif name == "Disembark":
            if not ev.get("OnPlanet") or ev.get("BodyID") is None:
                return
            self.db.execute("INSERT OR IGNORE INTO own_footfall VALUES (?, ?, ?)", (system, ev["BodyID"], ts))
            self.body_touched.add((system, ev["BodyID"]))
        elif name == "FSSDiscoveryScan":
            self.last_honk = {"id64": system, "ts": ts, "bodies": ev.get("BodyCount"), "progress": ev.get("Progress")}
            self.db.execute(
                """INSERT INTO own_systems (id64, name, body_count, all_found) VALUES (?, ?, ?, 0)
                   ON CONFLICT(id64) DO UPDATE SET body_count = excluded.body_count""",
                (system, ev.get("SystemName"), ev.get("BodyCount")))
            # the arrival briefing, once per arrival (a second honk here says nothing new); State adds the facts
            pos = self.pos
            if pos and pos["id64"] == system and self.brief_key != (system, pos["ts"]):
                self.brief_key = (system, pos["ts"])
                self.moment("arrival_brief", ts, system=system, source="honk")
        elif name == "FSSAllBodiesFound":
            # the FSS debrief. When the honk itself found everything (FSSAllBodiesFound follows such a honk within
            # a second or two) State leaves it out, but only if the arrival briefing the page got did say
            # 'all found': this line often lands a tick after the briefing was sent without it
            h = self.last_honk
            by_honk = bool(h and h["id64"] == system and ((h.get("progress") or 0) >= 0.999
                                                        or 0 <= ts_seconds(ts) - ts_seconds(h["ts"]) <= 5))
            self.moment("fss_done", ts, system=system, count=ev.get("Count"), by_honk=by_honk,
                        jumponium=self.take_jumponium(system))
            self.last_all_found = {"id64": system, "ts": ts}
            self.db.execute(
                """INSERT INTO own_systems (id64, name, body_count, all_found) VALUES (?, ?, ?, 1)
                   ON CONFLICT(id64) DO UPDATE SET all_found = 1,
                     body_count = coalesce(body_count, excluded.body_count)""",
                (system, ev.get("SystemName"), ev.get("Count")))
        else:  # SAASignalsFound / FSSBodySignals
            body = ev.get("BodyName") or ""
            signals = {s.get("Type"): s.get("Count", 0) for s in ev.get("Signals") or []}
            if body.endswith(" Ring"):
                self.db.execute("INSERT OR REPLACE INTO own_ring_signals VALUES (?, ?, ?, ?)",
                                (system, body, json.dumps(minerals(signals)), ts))
            else:
                self.db.execute("INSERT OR REPLACE INTO own_signals (system, name, bio, geo, ts, mining) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (system, body, signals.get(BIO, 0), signals.get(GEO, 0), ts, signals.get(MINING, 0)))
                if name == "FSSBodySignals" and (signals.get(BIO) or signals.get(GEO)):   # the FSS just found them
                    self.moment("signals", ts, system=system, body_name=body, bio=signals.get(BIO, 0), geo=signals.get(GEO, 0))
                if signals.get(BIO) and ev.get("BodyID") is not None and name == "FSSBodySignals":
                    self.moment("bio", ts, system=system, body_id=ev["BodyID"], signals=signals[BIO])
                for g in ev.get("Genuses") or []:
                    if g.get("Genus") and ev.get("BodyID") is not None:
                        self.db.execute("INSERT OR IGNORE INTO own_genera VALUES (?, ?, ?, ?, ?)",
                                        (system, ev["BodyID"], g["Genus"], g.get("Genus_Localised"), ts))
        self.dirty.add(system)

    def note_verdict(self, system, ts, was_discovered):
        """The discovery streak's verdict on an arrival, fixed by its arrival-star scan and never changed after:
        visited (you had been here before this arrival), new (nobody had discovered the star; your own unsold
        find on a return visit reads as visited), else known (State.fix_verdict adds what Spansh knew then).
        Only for the arrival you are still in: a main star scanned later on a return visit is not an arrival."""
        row = self.db.execute("SELECT ts, id64, kind, verdict FROM jumps WHERE ts <= ? ORDER BY ts DESC LIMIT 1",
                              (ts,)).fetchone()
        if not row or row["id64"] != system or row["kind"] not in ("FSDJump", "CarrierJump") or row["verdict"]:
            return
        before = self.db.execute("SELECT 1 FROM jumps WHERE id64=? AND ts < ? LIMIT 1", (system, row["ts"])).fetchone()
        verdict = "visited" if before else "known" if was_discovered else "new"
        self.db.execute("UPDATE jumps SET verdict=? WHERE ts=? AND id64=?", (verdict, row["ts"], system))

    def read_status(self, d):
        """Status.json: the live fuel gauge (rewritten by the game every few seconds)."""
        try:
            with open(os.path.join(d, "Status.json"), encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            return
        # with two live folders, a stale Status.json in one (an old Proton prefix) must not replace the reading
        # just taken from the other
        old = (self.status_json or {}).get("ts")
        if isinstance(st.get("timestamp"), str) and isinstance(old, str) and st["timestamp"] < old:
            return
        fuel = st.get("Fuel") or {}
        if "FuelMain" in fuel or st.get("Flags2") is not None:   # on foot there is no Fuel block, but the game is live
            prev = self.status_json or {}
            flags = st.get("Flags") if isinstance(st.get("Flags"), int) else 0
            # in the SRV (the Nomad counts as one) or a fighter, Fuel and Cargo are the vehicle's: keep the ship's
            away = "SRV" if flags & FLAG_IN_SRV else "fighter" if flags & FLAG_IN_FIGHTER else None
            vehicle_fuel = None
            if away:   # the vehicle's own tank (an SRV's fuel is all in its reservoir)
                vehicle_fuel = round((fuel.get("FuelMain") or 0) + (fuel.get("FuelReservoir") or 0), 2) if fuel else None
                fuel = {}
            self.status_json = {"fuel_main": fuel.get("FuelMain", prev.get("fuel_main")),
                                "fuel_reservoir": fuel.get("FuelReservoir", prev.get("fuel_reservoir")), "away": away,
                                "vehicle_fuel": vehicle_fuel,
                                "ts": st.get("timestamp"), "flags": st.get("Flags"), "flags2": st.get("Flags2"),
                                # where you are on a body (the on-body strip, sample spacing) and the target
                                "body": st.get("BodyName"), "lat": st.get("Latitude"), "lon": st.get("Longitude"),
                                "alt": st.get("Altitude"), "planet_radius": st.get("PlanetRadius"),
                                "heading": st.get("Heading"),   # degrees (the surface map is heading-up)
                                "cargo": prev.get("cargo") if away else st.get("Cargo"),   # tonnes aboard (the fuel model's mass)
                                "destination": st.get("Destination"), "gui_focus": st.get("GuiFocus"),
                                "fire_group": st.get("FireGroup"), "selected_weapon": st.get("SelectedWeapon"),   # the rail's Bio Scanner
                                "live": True}
        elif self.status_json:  # game closed or at the menu: keep the last reading, mark it stale
            self.status_json = dict(self.status_json, live=False)
        else:
            self.status_json = {"live": False, "ts": st.get("timestamp")}

    def read_navroute(self, d):
        path = os.path.join(d, "NavRoute.json")
        try:
            with open(path, encoding="utf-8") as f:
                route = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(route, dict):
            return   # malformed: skipped like unparseable JSON (a crash here would stall every tick)
        # only well-formed hops: a KeyError here would roll back the tick, and the unchanged file fail it again
        raw = [h for h in route.get("Route") or [] if isinstance(h, dict) and isinstance(h.get("StarPos"), list)
               and len(h["StarPos"]) == 3 and h.get("SystemAddress")] if isinstance(route.get("Route"), list) else []
        # older than the route already applied (a stale NavRoute.json in another live folder, or one written
        # before a NavRouteClear): ignored
        ts = route.get("timestamp")
        if isinstance(ts, str) and ts and not self.fresh("route", ts, (meta_get(self.db, "route") or {}).get("ts")):
            return
        hops = [{"id64": h["SystemAddress"], "name": h.get("StarSystem"), "star_class": h.get("StarClass"),
                 "x": h["StarPos"][0], "y": h["StarPos"][1], "z": h["StarPos"][2]} for h in raw]
        # the plotted route in order (the route strip); an empty file means the route was cleared
        meta_set(self.db, "route", {"ts": route.get("timestamp"), "hops": hops} if hops else None)
        self.navroute_end = hops[-1]["id64"] if hops else None
        for hop in raw:
            x, y, z = hop["StarPos"]
            self.db.execute(
                "INSERT OR REPLACE INTO route_systems VALUES (?, ?, ?, ?, ?, ?, ?)",
                (hop["SystemAddress"], hop.get("StarSystem"), x, y, z,
                 hop.get("StarClass"), route.get("timestamp")))
            if hop.get("StarClass"):
                self.db.execute("INSERT OR REPLACE INTO star_classes VALUES (?, ?)",
                                (hop["SystemAddress"], hop["StarClass"]))


def route_end(route):
    """The id64 of the last hop of a stored NavRoute ({"ts", "hops"}), or None."""
    hops = (route or {}).get("hops") or []
    return hops[-1].get("id64") if hops and isinstance(hops[-1], dict) else None


def materials_stale(materials, commander):
    """A login whose Materials line was never seen: the counts predate it."""
    login, snap = (commander or {}).get("login_ts"), (materials or {}).get("snapshot_ts")
    return bool(login and snap and ts_seconds(login) - ts_seconds(snap) > 120)


def region_spoken(name):
    """A region's name as said in a sentence: "the Norma Arm", "the Veils", but "Ryker's Hope", "Izanami"."""
    if not name:
        return name
    if name.startswith("The "):
        return "the " + name[4:]
    if "'" in name or " " not in name or name == "Mare Somnia":
        return name
    return "the " + name


def region_codex_count(db, region, number):
    """Species logged in your codex in other regions, not yet in this one, that the bio rules let grow here (a
    species the rules do not know is left out): what a crossing into `region` could add. 0 when none or unknown."""
    if not outrider.bio or not region:
        return 0
    logged = {(r[0] or "").strip().lower().split(" - ")[0].strip()
              for r in db.execute("SELECT DISTINCT name FROM codex WHERE region IS NOT NULL AND region != ?", (region,))}
    here = codex_species(db, region)[1]
    return sum(1 for sp in logged - here if sp and outrider.bio.region_allows(sp, number))


def codex_species(db, region):
    """Your codex entries in `region` as (full names, species), both lower-cased. Codex bio entries are per
    colour variant ("bacterium aurasus - teal"); the species set ("bacterium aurasus") counts a species as known
    once any of its variants is logged there, for when the colour cannot be told."""
    if not region:
        return set(), set()
    names = {(r[0] or "").strip().lower() for r in db.execute("SELECT name FROM codex WHERE region = ?", (region,))}
    return names, {n.split(" - ")[0].strip() for n in names}


def codex_species_all(db):
    """Your codex entries in every region, as codex_species gives one region's: a species in none of them is new to
    your codex anywhere (worth more effort than one new only in this region; BioScan's 🌌 against its 📝)."""
    names = {(r[0] or "").strip().lower() for r in db.execute("SELECT DISTINCT name FROM codex")}
    return names, {n.split(" - ")[0].strip() for n in names}


def codex_new_group(g, known):
    """Would the likeliest species of a genus group earn a new codex entry? `known` is codex_species().
    Per colour variant when the variant candidates are settled (any one unlogged counts: a new colour of a
    logged species pays a voucher too), else at species level, which never over-flags."""
    names, species = known
    if g.get("variants"):
        return any(v.lower() not in names for v in g["variants"])
    return bool(g.get("best")) and g["best"].lower() not in species


def codex_have(g, known):
    """The colours of a group's likeliest species already in your codex in the region (`known` is codex_species()),
    title-cased and sorted: what a ✦ on another colour of the same species says you have ("Lime", "Aquamarine")."""
    best = (g.get("best") or "").lower()
    return sorted(n.split(" - ", 1)[1].strip().title() for n in known[0]
                  if best and " - " in n and n.split(" - ", 1)[0].strip() == best)


def with_logged_variants(groups, logged):
    """Groups with the colour the journal logged for a genus on this body (own_organic's variant_name, known
    from the first sample) in place of the predicted candidates. `logged`: {genus: variant name}."""
    return [dict(g, variants=[logged[g["genus"]]], variant=logged[g["genus"]]) if logged.get(g["genus"]) else g
            for g in groups]


SALE_SESSION_S = 300   # s: Vista Genomics sales this close together are one visit (you sold in several goes)


def sale_species(bio_data):
    """A SellOrganicData's BioData as bio_sales keeps it: [[species (lower case codex key), bonus paid], ...]."""
    return [[(b.get("Species") or "").lower(), bool(b.get("Bonus"))] for b in bio_data]


def organic_replay(db, until=None):
    """Every completed sample run's fate, replayed in time order against the Vista Genomics sales and deaths (all
    of them, or those before `until`), by outrider.unsold's rule: each BioData entry of a sale takes one run of its species
    out (a paid bonus takes an x5 run first, one where your first scan of the body said nobody had set foot there,
    no bonus an x1 run first; the earliest done of those), the runs a sale does not name stay aboard, and any death
    takes every run aboard (exobiology data dies with you, ship or not). A sale stored before bio_sales kept its
    BioData takes every run aboard, as before. A sale or death in the same second as a run's completion comes
    before it. -> ({(system, body_id, species): (state, ts)}: sold with the sale's time, lost with the death's,
    aboard with None; [the runs aboard at the end: rows of system, body_id, species, done_ts, was_footfalled])."""
    cut = "" if until is None else " AND o.done_ts < ?"
    args = () if until is None else (until,)
    events = [(r["done_ts"], 2, r) for r in db.execute(
        "SELECT o.system, o.body_id, o.species, o.done_ts, (1 - f.bio_x5) AS was_footfalled FROM own_organic o "
        "LEFT JOIN own_firsts f ON f.system = o.system AND f.body_id = o.body_id "
        f"WHERE o.done_ts IS NOT NULL{cut} ORDER BY o.done_ts", args)]
    cut = "" if until is None else " WHERE ts < ?"
    events += [(r["ts"], 1, json.loads(r["bio_data"]) if r["bio_data"] else None)
               for r in db.execute(f"SELECT ts, bio_data FROM bio_sales{cut} ORDER BY ts, rowid", args)]   # journal order
    events += [(r["ts"], 0, None) for r in db.execute(f"SELECT ts FROM deaths{cut}", args)]
    events.sort(key=lambda e: (e[0], e[1]))
    key = lambda r: (r["system"], r["body_id"], r["species"])
    fates, aboard = {}, []
    for ts, kind, x in events:
        if kind == 2:
            aboard.append(x)
        elif kind == 0 or x is None:   # a death, or a sale whose entries are not known: everything aboard goes
            for r in aboard:
                fates[key(r)] = ("lost" if kind == 0 else "sold", ts)
            aboard = []
        else:
            for sp, bonus in x:
                order = (0, None, 1) if bonus else (1, None, 0)
                runs = [r for r in aboard if (r["species"] or "").lower() == sp]
                if runs:   # min keeps the earliest of equals; an entry with no run on record takes nothing
                    pick = min(runs, key=lambda r: order.index(r["was_footfalled"]))
                    aboard.remove(pick)
                    fates[key(pick)] = ("sold", ts)
    for r in aboard:
        fates[key(r)] = ("aboard", None)
    return fates, aboard


_ORGANIC_FATES = {}


def organic_fates(db):
    """organic_replay's fates over everything, kept until the database changes (db.total_changes moves with every
    write): organic_state asks once per run, in loops over many."""
    c = _ORGANIC_FATES
    if c.get("db") is not db or c.get("changes") != db.total_changes:
        c.update(db=db, changes=db.total_changes, fates=organic_replay(db)[0])
    return c["fates"]


def sale_check(db, ts, bio_data, source=None):
    """A Vista Genomics sale at ts against the prediction. The visit (sales under SALE_SESSION_S apart, as the ledger
    groups them, since the last death) is checked as one: the completed runs aboard before its first sale (organic_replay),
    each predicted x5 where your first scan of its body said nobody had set foot there (own_firsts), against
    everything the visit sold so far, matched by species counts alone (a BioData entry names no body). Each sale
    stores what it adds to the visit's check, so the ledger's sum over the visit is that one check, whatever order
    the entries came in (selling an x1 run first no longer leaves the x5 run "aboard" to be predicted again: review
    F21). {sold, predicted (runs predicted x5, at most the entries sold of the species), matched (of those, paid the
    bonus), paid (entries paid the bonus), unknown (runs sold whose footfall is not known), used ({species: [predicted,
    unknown]} this sale adds)}, or None for an empty sale. source: this sale's journal line (bio_sales' key), so a
    line handled twice is not its own earlier sale. Journal state only: a re-read rebuilds it."""
    if not bio_data:
        return None
    death = db.execute("SELECT max(ts) FROM deaths WHERE ts <= ?", (ts,)).fetchone()[0] or ""
    visit, last = [], ts
    for r in db.execute("SELECT ts, source, bio_data FROM bio_sales WHERE ts <= ? AND ts > ? ORDER BY ts DESC, rowid DESC",
                        (ts, death)):
        if r["ts"] == ts and r["source"] == source:
            continue
        if r["bio_data"] is None or ts_seconds(last) - ts_seconds(r["ts"]) >= SALE_SESSION_S:
            break   # another visit (or an old sale whose entries are not known): the visit starts after it
        visit.append(r)
        last = r["ts"]
    start = visit[-1]["ts"] if visit else ts
    pool = list(organic_replay(db, start)[1]) + list(db.execute(
        "SELECT o.system, o.body_id, o.species, o.done_ts, (1 - f.bio_x5) AS was_footfalled FROM own_organic o "
        "LEFT JOIN own_firsts f ON f.system = o.system AND f.body_id = o.body_id "
        "WHERE o.done_ts >= ? AND o.done_ts < ?", (start, ts)))
    x5, unknown = collections.Counter(), collections.Counter()
    for r in pool:
        sp = (r["species"] or "").lower()
        if r["was_footfalled"] == 0:
            x5[sp] += 1
        elif r["was_footfalled"] is None:
            unknown[sp] += 1

    def tally(entries):
        """Per species: [sold, paid, predicted, matched, unknown] for these [species, bonus] entries."""
        sold, paid = collections.Counter(), collections.Counter()
        for sp, bonus in entries:
            sold[sp] += 1
            paid[sp] += bool(bonus)
        out = {}
        for sp, n in sold.items():
            pred = min(x5[sp], n)
            out[sp] = [n, paid[sp], pred, min(pred, paid[sp]), min(unknown[sp], n - pred)]
        return out
    earlier = [e for r in reversed(visit) for e in json.loads(r["bio_data"])]
    mine = sale_species(bio_data)
    before, after = tally(earlier), tally(earlier + mine)
    add = {sp: [a - b for a, b in zip(v, before.get(sp, [0] * 5))] for sp, v in after.items()}
    total = lambda i: sum(v[i] for v in add.values())
    return {"sold": total(0), "predicted": total(2), "matched": total(3), "paid": total(1), "unknown": total(4),
            "used": {sp: [add[sp][2], add[sp][4]] for sp, _b in mine}}


def organic_state(db, done_ts, run=None):
    """Was a completed sample banked? sold, lost or aboard. With `run` (system, body_id, species) by organic_replay's
    per-species rule; without it, or for a run it does not know, by time alone: sold if a Vista Genomics sale
    followed it before any death, lost if a death came first, else aboard."""
    if not done_ts:
        return None
    if run is not None:
        fate = organic_fates(db).get((int(run[0]), int(run[1]), run[2]))
        if fate:
            return fate[0]
    sale = db.execute("SELECT min(ts) FROM bio_sales WHERE ts > ?", (done_ts,)).fetchone()[0]
    death = db.execute("SELECT min(ts) FROM deaths WHERE ts > ?", (done_ts,)).fetchone()[0]
    if sale and (not death or sale < death):
        return "sold"
    return "lost" if death else "aboard"


def pickup_judge(db, system):
    """A function pickup_ts -> (state, ts): sold / lost / unsold, for cartographic data from `system`."""
    sales = [r[0] for r in db.execute("SELECT ts FROM sales WHERE name = ? ORDER BY ts", (system,))]
    losses = [r[0] for r in db.execute(f"SELECT ts FROM deaths WHERE {SHIP_LOSS_SQL} ORDER BY ts")]

    def state(pickup, first=None):
        """`first`: when you first scanned (or mapped) the body. A sale between that and `pickup` already bought
        the body, so a later rescan (an arrival AutoScan, a return visit) is sold data, not new data -- unless
        the ship was lost between the first scan and that sale: the data died with it and the sale could not
        include it (as outrider.unsold judges it)."""
        if not pickup:
            return "unsold", None
        earlier = next((t for t in sales if first and first < t < pickup
                        and not any(first < l < t for l in losses)), None)
        if earlier:
            return "sold", earlier
        sale = next((t for t in sales if t > pickup), None)
        loss = next((t for t in losses if t > pickup), None)
        if sale and (not loss or sale < loss):
            return "sold", sale
        if loss:
            return "lost", loss
        return "unsold", None
    state.losses = losses   # own_firsts' rescan check: was the data lost between two pickups?
    return state


def own_firsts(db, id64, system):
    """What you were first to: discovery, mapping, footfall -- and whether the data was sold.

    Discovery and mapping only count once sold to Universal Cartographics, and unsold data is
    lost if you die; footfall is credited on the spot.
    """
    rows = db.execute(
        """SELECT f.*, m.ts AS mapped_ts, m.first_ts AS map_first_ts, ff.ts AS foot_ts, b.record AS body_record
           FROM own_firsts f
           LEFT JOIN own_mapped m ON m.system = f.system AND m.body_id = f.body_id
           LEFT JOIN own_footfall ff ON ff.system = f.system AND ff.body_id = f.body_id
           LEFT JOIN own_bodies b ON b.system = f.system AND b.body_id = f.body_id
           WHERE f.system = ?""", (id64,)).fetchall()
    disc = [r for r in rows if r["was_discovered"] == 0]
    mapped = [r for r in rows if r["was_mapped"] == 0 and r["mapped_ts"]]
    foot = [r for r in rows if r["was_footfalled"] == 0 and r["foot_ts"]]
    if not (disc or mapped or foot):
        return None

    # Each body is judged on its own pickup time: the data must reach a cartographer after
    # that, and a lost ship in between loses it (a rescan picks it up again, and undisc_ts
    # advances with every unsold rescan).
    state = pickup_judge(db, system)

    disc_states = [state(r["undisc_ts"] or r["first_ts"]) for r in disc]
    map_states = [state(r["mapped_ts"], r["map_first_ts"]) for r in mapped]   # a remap after a sale is sold
    arrival = next((st for r, st in zip(disc, disc_states) if r["is_main"]), None)
    counts = lambda states: {k: sum(1 for st, _ in states if st == k) for k in ("sold", "unsold", "lost")}
    out = {"system": arrival is not None, "system_state": arrival[0] if arrival else None,
           "system_ts": arrival[1] if arrival else None,
           "bodies": len(disc), "bodies_by": counts(disc_states),
           "mapped": len(mapped), "mapped_by": counts(map_states),
           "footfall": len(foot)}
    # One headline state for the marker: unsold needs your attention, lost is bad news,
    # sold is settled. Footfall alone has no sale to wait for.
    all_states = [st for st, _ in disc_states + map_states]
    out["sale"] = ("unsold" if "unsold" in all_states else "lost" if "lost" in all_states
                   else "sold" if all_states else None)
    if out["sale"] == "sold":
        out["sold_ts"] = max(t for st, t in disc_states + map_states if st == "sold")
    elif out["sale"] == "lost":
        out["lost_ts"] = max(t for st, t in disc_states + map_states if st == "lost")
    out["recover"] = firsts_recovery(disc, disc_states, mapped, map_states, state.losses, system)
    return out


def firsts_body_value(row, mapped):
    """What a body on the rescan checklist pays (an own_firsts row with its own_bodies record as body_record), as
    top_finds and lost_bodies value it: outrider.unsold.body_value with the first-discovery and first-mapped bonuses you
    earned there, without the efficiency bonus. 0 with no scan record (or no outrider.unsold)."""
    raw = row["body_record"] if "body_record" in row.keys() else None
    rec = json.loads(raw) if raw else {}
    if not outrider.unsold or not rec.get("ed"):
        return 0
    body = dict(rec["ed"], first_discovered=row["was_discovered"] == 0, first_mapped=row["was_mapped"] == 0)
    return outrider.unsold.body_value(body, mapped, False, True)


def firsts_recovery(disc, disc_states, mapped, map_states, losses, system=None):
    """The rescan checklist for one system (own_firsts' rows and states): {lost_bodies, rescanned, maps_lost,
    maps_redone, todo_scan, todo_map, lost_scan, lost_map, lost_total} over the discoveries and first maps that died
    with a ship and are not banked again -- still lost, or picked up again by a later scan (a new DSS for a map:
    own_mapped's ts after the loss) and not sold since.
    None when nothing is. From the journals alone: the latest unsold pickup (undisc_ts, which only moves while the
    game still calls the body undiscovered; own_mapped.ts) with a ship loss between it and your first scan (first
    map) is data that was lost and rescanned; a sale in between would have banked it, and a rescan after that sale
    reads as discovered, so undisc_ts never passes it. todo_scan / todo_map: [{name, value}] (short_name, in natural
    order) for the bodies still to scan in the FSS and whose lost first map still wants a DSS; empty once done.
    Values (firsts_body_value, with the bonuses earned): a scan is the body's unmapped value, a map what mapping adds
    on top (mapped minus unmapped, as Left behind counts it), so a body whose scan and map are both lost shows its
    scan under one and the rest under the other, adding up to its mapped value. lost_scan / lost_map: their sums
    (what is still lost; 0 once everything is back), lost_total both."""
    def tally(rows, states, first, pickup, worth):
        lost = back = 0
        todo = []
        for r, (st, _) in zip(rows, states):
            a, b = r[first], r[pickup] or r[first]
            if st == "lost":
                lost += 1
                todo.append({"name": short_name(system, r["name"]) or f"body {r['body_id']}", "value": worth(r)})
            elif st == "unsold" and a and b and any(a < t < b for t in losses):
                lost += 1
                back += 1
        return lost, back, sorted(todo, key=lambda t: natural(t["name"]))
    lost_bodies, rescanned, todo_scan = tally(disc, disc_states, "first_ts", "undisc_ts",
                                              lambda r: firsts_body_value(r, False))
    maps_lost, maps_redone, todo_map = tally(mapped, map_states, "map_first_ts", "mapped_ts",
                                             lambda r: max(0, firsts_body_value(r, True) - firsts_body_value(r, False)))
    if not (lost_bodies or maps_lost):
        return None
    lost_scan, lost_map = sum(t["value"] for t in todo_scan), sum(t["value"] for t in todo_map)
    return {"lost_bodies": lost_bodies, "rescanned": rescanned, "maps_lost": maps_lost, "maps_redone": maps_redone,
            "todo_scan": todo_scan, "todo_map": todo_map,
            "lost_scan": lost_scan, "lost_map": lost_map, "lost_total": lost_scan + lost_map}


def spansh_seconds(t):
    """A Spansh time ('2026-09-28T03:15:00Z', or with a space and '+00') -> seconds since the epoch; None if unreadable."""
    try:
        return ts_seconds(str(t).replace(" ", "T"))
    except (TypeError, ValueError):
        return None


def firsts_watch_gap(row, now):
    """Seconds before a checked firsts_watch row is due again: FIRSTS_WATCH_SLOW once someone else has been seen there
    (a sighting never clears, so a daily look only moves the body count) or once your first scan there is
    FIRSTS_WATCH_YOUNG old; FIRSTS_WATCH_EVERY before that."""
    first = ts_seconds(row["first_ts"]) if row["first_ts"] else None
    if row["reported_ts"] or (first is not None and now - first >= FIRSTS_WATCH_YOUNG):
        return FIRSTS_WATCH_SLOW
    return FIRSTS_WATCH_EVERY


def firsts_watched(entry):
    """Whether the firsts watch looks at a firsts_list entry: unsold (its sale headline: a system rescanned after a
    loss, or part rescanned, holds unsold data again), with at least one body you discovered. A system
    whose only unsold firsts are first-mapped bodies (someone else discovered them) is left out: firsts_mine and
    firsts_reported only look at your discoveries, so its check could never find anything and, with no first scan
    of yours to age by, would come round daily for as long as the data stays unsold."""
    return entry.get("sale", entry["state"]) == "unsold" and sum((entry.get("bodies_by") or {}).values()) > 0


def firsts_reported(records, mine, body_count=None, system_times=()):
    """Whether someone else has reported bodies you were first to discover: `records` are a system's Spansh body
    records (record_from_dump: short name, type, updated), `mine` {short name: [your journal timestamps for that body:
    scans, map]} for the bodies you discovered, `system_times` your other journal times there (every arrival: a jump
    in updates the arrival star; footfall, samples, codex). A body counts when Spansh last had it updated later than
    all your own times for it and not at one of your system times (each plus FIRSTS_OWN_GRACE, so your own upload
    through EDDN, stamped with your event's time, does not count; one dated before your scan was in the arrival
    snapshot, which a first discovery never has anyway). ->
    None when no body of yours counts, else {reported_ts (the earliest such update: the first sighting), bodies (yours
    that count), spansh_bodies (every star and planet Spansh has), body_count (the system's, when known)}."""
    seen = []
    visits = [ts_seconds(t) for t in system_times if t]
    for r in records:
        times = mine.get(r.get("name"))
        if not times or r.get("type") not in ("Star", "Planet"):
            continue
        up = spansh_seconds(r.get("updated")) if r.get("updated") else None
        own = [ts_seconds(t) for t in times if t]
        if up is None or not own or up <= max(own) + FIRSTS_OWN_GRACE \
                or any(v - FIRSTS_OWN_GRACE <= up <= v + FIRSTS_OWN_GRACE for v in visits):
            continue
        seen.append(up)
    if not seen:
        return None
    return {"reported_ts": iso_ts(min(seen)), "bodies": len(seen),
            "spansh_bodies": sum(1 for r in records if r.get("type") in ("Star", "Planet") and not r.get("placeholder")),
            "body_count": body_count}


def firsts_seen(row):
    """A firsts_watch row as My firsts shows it: {reported_ts, days (after your first scan), bodies, spansh_bodies,
    body_count}, or None when nobody else is known to have scanned there."""
    if not row or not row.get("reported_ts"):
        return None
    days = None
    if row.get("first_ts"):
        days = max(0, round((ts_seconds(row["reported_ts"]) - ts_seconds(row["first_ts"])) / 86400))
    return {"reported_ts": row["reported_ts"], "days": days, "bodies": row.get("bodies"),
            "spansh_bodies": row.get("spansh_bodies"), "body_count": row.get("body_count")}


# --------------------------------------------------------------------------
# Summaries: what the page shows for a system, computed from merged records
# --------------------------------------------------------------------------

def dist(a, b):
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def with_id(d):
    """A system dict for the page with `id`, its id64 as a string: JavaScript numbers hold 53 bits, and an id64
    above 2^53 (a high in-boxel index) would lose its last digits there and no longer match the exact ids."""
    return dict(d, id=str(d["id64"])) if d and d.get("id64") is not None else d


def star_short(subtype):
    """'K (Yellow-Orange giant) Star' -> 'K', 'White Dwarf (DA) Star' -> 'DA', etc."""
    if not subtype:
        return None
    m = re.match(r"^([OBAFGKMLTY]) \(", subtype)
    if m:
        return m.group(1)
    m = re.match(r"^White Dwarf \((\w+)\)", subtype)
    if m:
        return m.group(1)
    fixed = {"Neutron Star": "N", "Black Hole": "BH", "Supermassive Black Hole": "SMBH",
             "T Tauri Star": "TTS", "Herbig Ae/Be Star": "AeBe", "MS-type Star": "MS",
             "S-type Star": "S", "C Star": "C", "CN Star": "CN", "CJ Star": "CJ"}
    if subtype in fixed:
        return fixed[subtype]
    if subtype.startswith("Wolf-Rayet"):
        return "W"
    return subtype.split()[0]


def subtype_scoopable(subtype):
    return bool(subtype) and re.match(r"^[OBAFGKM] \(", subtype) is not None


def class_scoopable(star_class):
    """NavRoute StarClass codes: 'K', 'M_RedGiant', 'DA', 'TTS', ..."""
    return bool(star_class) and star_class.split("_")[0] in SCOOPABLE


def natural(s):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]


# ---- the fuel model: laden range, fuel per hop, jumps left ----

def refitted(old, new):
    """True when a Loadout's [drive, unladen t, max range ly, booster] differs from the last one's by more than the
    game's float jitter (the same ship logs 323.150024 t and 323.149994 t)."""
    return bool(old) and (old[0] != new[0] or old[3] != new[3] or abs(old[1] - new[1]) > 0.5 or abs(old[2] - new[2]) > 0.05)


def tally(items):
    out = {}
    for i in items:
        if i:
            out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def ring_stats(rings):
    """Rings with width and surface density (megatonnes per km^2), for miners' eyes."""
    out = []
    for x in rings or []:
        d = dict(x)
        inner, outer, mass = x.get("inner"), x.get("outer"), x.get("mass")
        if inner is not None and outer is not None:
            d["width_km"] = round((outer - inner) / 1000)
            area_km2 = math.pi * (outer ** 2 - inner ** 2) / 1e6
            d["density"] = round(mass / area_km2, 5) if mass and area_km2 > 0 else None
            d["inner_km"], d["outer_km"] = round(inner / 1000), round(outer / 1000)
        out.append(d)
    return out


def curiosities(r, parent=None, raw=None, binary=False):
    """Observatory-style "interesting body" flags: [(tag, why)]. `parent` is the record this body orbits
    (if a body), `raw` your own Scan event (rotation, tidal lock), `binary` true when it circles a shared
    centre with another planet. Only facts that are known are tested: nothing is flagged on a guess."""
    out = []
    planet = r.get("type") == "Planet"
    g, landable = r.get("gravity"), r.get("landable")
    # a page row keeps its rings under ring_details (rings is a count there); a stored record has the list
    rings = r["ring_details"] if isinstance(r.get("ring_details"), list) else r["rings"] if isinstance(r.get("rings"), list) else []
    if planet and landable and rings:
        out.append(("ringed landable", "a landable body with rings: the view from the surface"))
    if planet and landable and g and g > 3:
        out.append(("high g", f"{g:.1f} g and landable"))
    raw = raw or {}
    rot = raw.get("RotationPeriod")
    if planet and rot and abs(rot) < 7200 and not raw.get("TidalLock"):
        out.append(("fast spin", f"a day of {abs(rot) / 60:.0f} minutes"))
    if planet and landable and raw.get("TidalLock") and r.get("atmosphere") and r.get("atmosphere") != "None":
        out.append(("locked, with air", "tidally locked, landable and with an atmosphere"))
    sma_km = (r.get("sma_ls") or 0) * LIGHT_SPEED / 1000
    if parent and sma_km and parent.get("radius_km") and sma_km < 3 * parent["radius_km"]:
        out.append(("close orbit", f"orbits {sma_km / parent['radius_km']:.1f} radii from {parent['name']}"))
    rk = r.get("radius_km")
    for x in ring_stats(rings):
        if rk and x.get("width_km") and x["width_km"] > 5 * rk:
            out.append(("wide rings", f"{x['name']}: {x['width_km']:,} km wide, {x['width_km'] / rk:.0f}x the body's radius"))
            break
    if planet and "gas giant" in (r.get("subtype") or "").lower() and parent and parent.get("type") == "Star" \
            and r.get("sma_ls") and r["sma_ls"] < 50:
        out.append(("hot Jupiter", f"a gas giant {r['sma_ls']:.0f} ls from its star"))
    pf = [p for p in r.get("parents_full") or [] if p["kind"] != "Ring"]
    if planet and len(pf) >= 2 and pf[0]["kind"] == "Planet" and pf[1]["kind"] == "Planet":
        out.append(("moon of a moon", "a moon orbiting a moon"))
    if planet and binary:
        out.append(("planet pair", "circles a shared centre with another planet"))
    return out


def system_curiosities(system, records, raws=None):
    """{short body name: [(tag, why)]} for a system, the same for Here and Nearby. A body's parent is the
    body it directly orbits (never through a barycentre: an orbit around a shared centre is measured from
    that centre, so comparing it with a star's radius would be meaningless); planets that share a
    barycentre with only other planets are a planet pair."""
    raws = raws or {}
    by_id = {x.get("body_id"): x for x in records if x.get("body_id") is not None}
    first = lambda x: next((q for q in x.get("parents_full") or [] if q["kind"] != "Ring"), None)
    centres = {}
    for x in records:
        f = first(x)
        if f and f["kind"] == "Null":
            centres.setdefault(f["id"], []).append(x)
    out = {}
    for x in records:
        f = first(x)
        parent = by_id.get(f["id"]) if f and f["kind"] in ("Star", "Planet") else None
        members = centres.get(f["id"], []) if f and f["kind"] == "Null" else []
        # planets named after a star pair ("BC 1", "BC 2") circle those stars' shared centre: without the
        # stars' own scans only the planets are seen at it, which is not a planet pair
        binary = len(members) >= 2 and all(m.get("type") == "Planet" for m in members) \
            and not any(re.fullmatch(r"[A-Z]{2,} \d+", m.get("name") or "") for m in members)
        c = curiosities(x, parent, raws.get(x["name"]), binary)
        if c:
            out[x["name"]] = c
    return out


def bio_context(name, records, x=None, y=None, z=None, star=None, body_count=None):
    """What the exobiology rules want to know about a system as a whole: where it is (region,
    nebulae), its stars, and which planet classes it holds. `star` is the arrival star class
    from the journal, used when no star has been scanned yet.

    `body_count` (FSS or Spansh) says whether the bodies known are all there are. Until they are,
    the planet list is passed as unknown: a water giant not scanned yet must not rule out the
    species that need one, and a star not scanned yet may be the one a planet orbits."""
    records = list(records)
    stars, planet_types, star_types = [], [], {}
    for r in records:
        if r.get("type") == "Star":
            stars.append({"type": r.get("subtype"), "luminosity": r.get("luminosity"), "main": r.get("main")})
            if r.get("body_id") is not None:
                star_types[r["body_id"]] = r.get("subtype")
        elif r.get("type") == "Planet":
            planet_types.append(r.get("subtype"))
    complete = bool(body_count) and len(stars) + len(planet_types) >= body_count
    if not any(s.get("main") for s in stars) and star:
        stars.append({"type": star, "luminosity": None, "main": True})
    return {"name": name, "x": x, "y": y, "z": z, "stars": stars, "planet_types": planet_types if complete else None,
            "complete": complete, "star_types": star_types}


def surface_materials(m):
    """A body's surface materials as lower-case names, from a journal list ([{Name, Percent}]), a Spansh
    dump dict ({Iron: 20.1}) or a search list ([{name, share}]); None when not known."""
    if isinstance(m, dict):
        return sorted(str(k).lower() for k in m)
    if isinstance(m, list) and m:
        return sorted(str(x.get("Name") or x.get("name") or "").lower() for x in m if isinstance(x, dict)) or None
    return None


def _bio_body(r, star, ctx):
    star_types = (ctx or {}).get("star_types") or {}
    parents = r.get("parent_star_types")
    if not parents and r.get("parents") and all(p in star_types for p in r["parents"]):
        # every star it orbits has been scanned; with one still unknown the parents stay unknown, so the
        # colour check cannot judge by the wrong star (the arrival star, a grandparent)
        parents = [star_types[p] for p in r["parents"]]
    gravity = r.get("gravity_raw") if r.get("gravity_raw") is not None else r.get("gravity")
    pressure = r.get("pressure_raw") if r.get("pressure_raw") is not None else r.get("pressure")
    body = {"class": r.get("subtype"), "atmosphere": r.get("atmosphere"), "gravity": gravity,
            "temperature": r.get("temperature"), "volcanism": r.get("volcanism"), "dist_ls": r.get("dist_ls"),
            "pressure": pressure, "orbital_period_s": r.get("orbital_period_s"),
            "atmosphere_composition": r.get("atmo_comp"), "parents": parents or None, "star": star,
            "materials": r.get("materials")}
    return body


def bio_guess(r, star=None, genera=None, ctx=None):
    """What a body's bio signals could be: (upper-bound credits, genus groups) or (None, [])."""
    if not outrider.bio or r.get("type") != "Planet":
        return None, []
    cands = outrider.bio.predict(_bio_body(r, star, ctx), ctx)
    if not cands and not genera:
        return None, []
    val, groups = outrider.bio.potential(cands, signals=r.get("bio") or None, genera=genera)
    return (val if any(g.get("value") for g in groups) else None), groups


def bio_left_groups(r, star, known, ctx, done):
    """The genus groups still to sample on a body. With the DSS's genera: those not analysed yet. Before
    the DSS: every genus the rules allow less the ones analysed, and the most valuable of the rest, one
    per signal still left (a finished genus outside the rules' top N must not leave N priced)."""
    if known:
        _, groups = bio_guess(r, star, known, ctx)
        return [g for g in groups if g["genus"] not in done]
    left_n = (r.get("bio") or 0) - len(done)
    if left_n <= 0:
        return []
    _, groups = bio_guess(dict(r, bio=None), star, None, ctx)
    return [g for g in groups if g["genus"] not in done][:left_n]


def bio_options(r, star=None, ctx=None, known=()):
    """Before the DSS, when a body has fewer signals than genera the rules allow, which genus it is cannot
    be told: {low, high, genera} -- every possible genus (most valuable first) and the range the signals
    could pay, from the cheapest to the most valuable. None when the signals already cover the choices.
    `known`: genera you sampled there without a DSS; each accounts for one signal and is no longer an option."""
    known = set(known or ())
    n = (r.get("bio") or 0) - len(known)
    if not outrider.bio or r.get("type") != "Planet" or n <= 0:
        return None
    groups = [g for g in outrider.bio.by_genus(outrider.bio.predict(_bio_body(r, star, ctx), ctx)) if g["genus"] not in known]
    if len(groups) <= n:
        return None
    lows = sorted(g.get("min_value") or 0 for g in groups)
    return {"low": sum(lows[:n]), "high": sum(g.get("value") or 0 for g in groups[:n]),
            "genera": [{"genus": g["genus"], "best": g["best"], "value": g["value"],
                        "species": [outrider.bio.short_species(x["name"], g["genus"]) for x in g["species"]]} for g in groups]}


# Odyssey's legacy/live split (29 Nov 2022): body data reported before it came from pre-Odyssey clients, which marked
# thin-atmosphere worlds not landable and reported no biological signals.
LEGACY_CUTOFF = "2022-11-29"


def stale_bio_groups(r, star=None, ctx=None):
    """The genus groups the exobiology rules allow on a Spansh body whose record is too old to say: a planet with a
    thin atmosphere, marked not landable, with no signals block, last reported before LEGACY_CUTOFF. [] for any
    other body, and for one where the rules allow nothing (an atmosphere or gravity no Odyssey life takes). Your own
    scan replaces the Spansh record (it has no `updated`), so a body you have scanned is never one of these."""
    if not stale_bio_candidate(r):
        return []
    return outrider.bio.by_genus(outrider.bio.predict(_bio_body(r, star, ctx), ctx))


def stale_bio_candidate(r):
    """stale_bio_groups' checks short of the rules: cheap, so a caller can skip building the bio context."""
    if not outrider.bio or r.get("type") != "Planet" or r.get("landable") or r.get("signals_known") is not False:
        return False
    updated = r.get("updated")
    if not isinstance(updated, str) or not updated[:10] or updated[:10] >= LEGACY_CUTOFF:
        return False
    return str(r.get("atmosphere") or "").lower().startswith("thin")


NO_SIGNAL_SCANS = ("AutoScan", "NavBeaconDetail", "NavBeacon")   # scans that never count a body's signals


def unknown_bio_groups(r, star=None, ctx=None):
    """The genera the rules allow on a landable planet whose signals nobody has counted: you have it only from an
    AutoScan or a nav beacon (no FSS of it, which says its signals), and Spansh has none either. [] otherwise.
    BioScan's "Bios possible, check FSS for signals": a quick honk-and-go leaves such bodies unchecked."""
    if not outrider.bio or r.get("type") != "Planet" or not r.get("landable") or r.get("bio") or r.get("signals_seen"):
        return []
    if r.get("scan_type") not in NO_SIGNAL_SCANS or r.get("signals_known"):
        return []
    if not r.get("atmosphere") or str(r.get("atmosphere")).lower() in ("none", "no atmosphere"):
        return []
    return outrider.bio.by_genus(outrider.bio.predict(_bio_body(r, star, ctx), ctx))


def stale_bio_body(r, star=None, ctx=None):
    """Whether a Spansh body may hold life its pre-Odyssey record could not report (see stale_bio_groups)."""
    return bool(stale_bio_groups(r, star, ctx))


def stale_bio_summary(records, star=None, ctx=None):
    """{bodies, genera_top, up_to, reported} for the bodies stale_bio_groups flags, or None when none are. up_to
    prices one genus per body, the median of those the rules allow (not the most valuable), so the figure is not
    absurd; it is kept apart from bio_potential and the value columns. reported: the latest of their Spansh dates."""
    n, up_to, genera, last = 0, 0, collections.Counter(), ""
    for r in records:
        groups = stale_bio_groups(r, star, ctx)
        if not groups:
            continue
        n += 1
        vals = sorted(g.get("value") or 0 for g in groups)
        up_to += vals[len(vals) // 2]
        genera.update(g["genus"] for g in groups)
        last = max(last, r["updated"][:10])
    if not n:
        return None
    return {"bodies": n, "genera_top": [g for g, _ in genera.most_common(3)], "up_to": up_to, "reported": last}


def summarise(records, body_count, star=None, ctx=None, genera=None):
    """`genera`: {body name: [genus]} your own DSS found; they win over Spansh's list (as in system_value)."""
    genera = genera or {}
    stars = [r for r in records if r["type"] == "Star"]
    planets = [r for r in records if r["type"] == "Planet"]
    main = next((r for r in stars if r.get("main")), stars[0] if len(stars) == 1 else None)
    full = all(r.get("full") for r in records)
    s = {
        "body_count": body_count,
        "bodies_known": len(stars) + len(planets),
        "stars": len(stars),
        "scoopable_stars": sum(bool(r.get("scoopable")) for r in stars),
        "main_star": main["subtype"] if main else None,
        "main_scoopable": bool(main.get("scoopable")) if main else None,
        "planets": len(planets),
        "star_types": tally(r["subtype"] for r in stars),
        "planet_types": tally(r["subtype"] for r in planets),
        "terraformable": sum(bool(r.get("terraformable")) for r in planets),
        "notable": tally([NOTABLE_PLANETS[r["subtype"]] for r in planets if r["subtype"] in NOTABLE_PLANETS] +
                         ["T" for r in planets if r.get("terraformable")]),
        # Spansh's estimate of scanning and mapping everything known here (None if unknown)
        "est_value": sum(r["value"] for r in records if r.get("value")) or None,
        # exobiology: an upper bound on what the bio-signal bodies could pay, from spawn rules
        "bio_potential": None, "bio_bodies_guessed": 0,
        "ringed": None, "detail": None,
    }
    pot, n = 0, 0
    for r in records:
        known = genera.get(r["name"]) or r.get("genera") or None
        if r.get("bio") or known:
            val, groups = bio_guess(r, star, known, ctx)
            if val:
                pot += val
                n += 1
    if n:
        s["bio_potential"], s["bio_bodies_guessed"] = pot, n
    s["stale_bio"] = stale_bio_summary(records, star, ctx)   # old Spansh data: a mark only, never in the values
    s["bio_unknown"] = sum(1 for r in planets if unknown_bio_groups(r, star, ctx)) or None   # check them in the FSS
    if not full:
        return s  # rings, belts and signals arrive with the Spansh dump
    ringed = [r for r in planets if r.get("rings")]
    all_rings = [(r, x) for r in records for x in r.get("rings") or []]
    ring_types = tally(x["type"] for _, x in all_rings)
    s["ringed"] = len(ringed)
    mining = rhino_mining(records)
    s["detail"] = {
        "rings": ring_types,
        # Ring type -> the bodies (planets or stars) carrying a ring of that type.
        "ring_bodies": {t: sorted({r["name"] for r, x in all_rings if x["type"] == t}, key=natural)
                        for t in ring_types},
        "ringed_types": tally(r["subtype"] for r in ringed),
        "ringed_stars": sum(1 for r in stars if r.get("rings")),
        "belts": tally(t for r in records for t in r.get("belts") or []),
        "landable": sum(1 for r in planets if r.get("landable")),
        "bio": sum(r.get("bio") or 0 for r in records),
        "bio_bodies": sum(1 for r in records if r.get("bio")),
        "geo": sum(r.get("geo") or 0 for r in records),
        "geo_bodies": sum(1 for r in records if r.get("geo")),
        # planetary mining locations on Rhino-worthy ground only (metal-rich, high metal content, rocky with magma)
        "mining": mining[0], "mining_bodies": mining[1],
        "hotspots": [{"ring": f"{r['name']} {x['name']}", "type": x["type"], "minerals":
                      dict(sorted(minerals(x["hotspots"]).items(), key=lambda kv: (-kv[1], kv[0])))}
                     for r, x in all_rings if x.get("hotspots")],
        "rings_mapped": sum(1 for _, x in all_rings if x.get("hotspots") or x.get("mapped")),
        "ring_count": len(all_rings),
    }
    return s


# --------------------------------------------------------------------------
# Spansh
# --------------------------------------------------------------------------

FIND_NAME_MAX = 100   # /api/find: the longest system name taken (real ones are far shorter)

# Bump when the cached record layout changes so cached systems get re-fetched.
CACHE_VERSION = 17   # 14: pressure_raw; 15: updated, signals_known (stale_bio_body); 16: mining; 17: "Terraformable" priced


def cached_base(db, id64):
    """(updated_at, base) of a system's cached Spansh record, or (None, None) if none in this layout."""
    row = db.execute("SELECT * FROM spansh_systems WHERE id64=?", (id64,)).fetchone()
    if not row:
        return None, None
    base = json.loads(row["summary"])
    return (row["updated_at"], base) if base.get("v") == CACHE_VERSION else (None, None)


def highway_not_yet(name):
    """The plot error for a start neither Spansh nor Outrider can place (a system Spansh does not know yet is stood in
    for when Outrider knows where it is: State.highway_ends)."""
    return f"Spansh doesn't know {name} yet, and Outrider doesn't know where it is: check the name, or plot from where you are"


class Spansh:
    def __init__(self, db):
        self.db = db
        self.session = None
        self.sem = asyncio.Semaphore(SPANSH_CONCURRENCY)
        self.sem_fast = asyncio.Semaphore(SPANSH_INTERACTIVE)
        self.sem_search = asyncio.Semaphore(SPANSH_INTERACTIVE)   # online Search: never queues behind a refresh
        self.sem_plot = asyncio.Semaphore(1)   # the Highway's plots: one at a time

    async def start(self):
        self.session = ClientSession(timeout=ClientTimeout(total=60),
                                     headers={"User-Agent": USER_AGENT})

    async def close(self):
        await self.session.close()

    async def sphere(self, pos, radius, max_pages=SPANSH_MAX_PAGES):
        """Every system Spansh knows within radius of pos (search-level detail), nearest first."""
        results, page = [], 0
        while page < max_pages:
            body = {
                "filters": {"distance": {"min": "0", "max": str(radius + 0.5)}},
                "reference_coords": {"x": pos["x"], "y": pos["y"], "z": pos["z"]},
                "sort": [{"distance": {"direction": "asc"}}],
                "size": SPANSH_PAGE, "page": page,
            }
            async with self.session.post(SPANSH_SEARCH, json=body) as r:
                r.raise_for_status()
                d = await r.json()
            results += d.get("results") or []
            if len(results) >= d.get("count", 0) or not d.get("results"):
                break
            page += 1
        return results

    async def body_search(self, filters, pos, radius, max_pages):
        """Bodies matching filters within radius, nearest first.

        Returns (bodies, cut): cut is None if every match was fetched, otherwise the distance
        of the last body fetched -- results are only complete out to there.
        """
        results, page = [], 0
        while page < max_pages:
            body = {
                "filters": dict(filters, distance={"min": "0", "max": str(radius)}),
                "reference_coords": {"x": pos["x"], "y": pos["y"], "z": pos["z"]},
                "sort": [{"distance": {"direction": "asc"}}],
                "size": SPANSH_PAGE, "page": page,
            }
            async with self.sem_search:
                async with self.session.post(SPANSH_BODY_SEARCH, json=body) as r:
                    r.raise_for_status()
                    d = await r.json()
            batch = d.get("results") or []
            results += batch
            if len(results) >= d.get("count", 0) or not batch:
                return results, None
            page += 1
        return results, results[-1]["distance"]

    def fetched_age(self, id64):
        """Seconds since a system's cached record was fetched, or None if it is not cached."""
        row = self.db.execute("SELECT fetched_ts FROM spansh_systems WHERE id64=?", (id64,)).fetchone()
        return time.time() - row["fetched_ts"] if row and row["fetched_ts"] else None

    async def stations(self, service, pos, size=20):
        """The stations nearest `pos` offering `service` (e.g. "Universal Cartographics"), nearest first. Spansh's
        services filter is a list of {name} (each one required); the {"value": [...]} shape was ignored without a
        word, so these were simply the nearest stations, offering the service or not (found 2026-10-08 with the
        review's #6). The answer is checked as well."""
        body = {"filters": {"services": [{"name": service}], "distance": {"min": "0", "max": "20000"}},
                "reference_coords": {"x": pos["x"], "y": pos["y"], "z": pos["z"]},
                "sort": [{"distance": {"direction": "asc"}}], "size": size, "page": 0}
        async with self.sem_fast:
            async with self.session.post(SPANSH_STATION_SEARCH, json=body) as r:
                r.raise_for_status()
                d = await r.json()
        return [{"name": x.get("name"), "system": x.get("system_name"), "id64": str(x.get("system_id64")),
                 "distance": round(x.get("distance") or 0, 1), "type": x.get("type"), "updated_at": x.get("updated_at"),
                 "ls": round(x.get("distance_to_arrival") or 0), "large_pad": bool(x.get("has_large_pad")),
                 "x": x.get("system_x"), "y": x.get("system_y"), "z": x.get("system_z")}
                for x in d.get("results") or []
                if service in {v.get("name") for v in x.get("services") or [] if isinstance(v, dict)}]

    async def market_search(self, body):
        """The Sell / Buy lookup: one page of Spansh's station search (outrider.cargo.market_query's body)."""
        if self.session is None:
            raise ClientError("no network session")
        async with self.sem_fast:
            async with self.session.post(SPANSH_STATION_SEARCH, json=body) as r:
                r.raise_for_status()
                d = await r.json()
        if not isinstance(d, dict):
            raise ClientError("Spansh's answer is not a station list")
        return d

    async def dock_search(self, pos, need=()):
        """Stations and fleet carriers nearest `pos` (two pages of the station search, each nearest first, out to
        outrider.dock.SEARCH_LY) that offer every service in `need` (outrider.dock's names). Without that filter the
        50 nearest were all there was to choose from: near the bubble a Vista station 40 ly away went unseen (review
        2026-10-08 #6). outrider.dock.nearest still checks each row's own list."""
        if self.session is None:
            raise ClientError("no network session")
        ref = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
        types = [t for t in outrider.cargo.STATION_TYPES if "Construction" not in t]
        spansh_names = {short: name for name, short in outrider.dock.SPANSH_SERVICES.items()}
        services = [{"name": spansh_names[n]} for n in need if n in spansh_names]
        out = []
        for kinds in (types, [outrider.cargo.CARRIER_TYPE]):
            filters = {"type": {"value": kinds}, "distance": {"min": "0", "max": str(outrider.dock.SEARCH_LY)}}
            if services:
                filters["services"] = services   # a list of {name}: each one required
            body = {"filters": filters, "sort": [{"distance": {"direction": "asc"}}], "reference_coords": ref,
                    "size": outrider.dock.SEARCH_SIZE, "page": 0}
            async with self.sem_fast:
                async with self.session.post(SPANSH_STATION_SEARCH, json=body) as r:
                    r.raise_for_status()
                    d = await r.json()
            out += (d.get("results") or []) if isinstance(d, dict) else []
        return out

    async def permit_ids(self, ids):
        """Which of these systems need a permit (Spansh's system records say; its station records do not)."""
        ids = sorted({int(i) for i in ids if isinstance(i, int) or str(i).isdigit()})
        if not ids or self.session is None:
            return set()
        body = {"filters": {"id64": {"value": ids}}, "size": len(ids), "page": 0}
        async with self.sem_fast:
            async with self.session.post(SPANSH_SEARCH, json=body) as r:
                r.raise_for_status()
                d = await r.json()
        return {x.get("id64") for x in (d.get("results") or []) if isinstance(x, dict) and x.get("needs_permit")}

    async def get_if_changed(self, url, etag=None, modified=None):
        """A conditional GET: (304, None, etag, modified) when unchanged, else (200, json, its etag, its date)."""
        if self.session is None:
            raise ClientError("no network session")
        headers = {k: v for k, v in (("If-None-Match", etag), ("If-Modified-Since", modified)) if v}
        async with self.sem_fast:
            async with self.session.get(url, headers=headers) as r:
                if r.status == 304:
                    return 304, None, etag, modified
                r.raise_for_status()
                return 200, await r.json(content_type=None), r.headers.get("ETag"), r.headers.get("Last-Modified")

    async def commodity_names(self):
        """Spansh's commodity names, as it spells them (the keys of its min_max)."""
        if self.session is None:
            raise ClientError("no network session")
        async with self.sem_fast:
            async with self.session.get(SPANSH_COMMODITIES) as r:
                r.raise_for_status()
                d = await r.json()
        names = sorted(k for k in (d.get("min_max") if isinstance(d, dict) else None) or {} if isinstance(k, str) and k)
        if not names:
            raise ClientError("Spansh sent no commodity names")
        return names

    async def plot(self, url, params, poll=None, timeout=None, method="GET"):
        """A Spansh route job (the neutron or the exact plotter): submit it, then ask for its result every `poll` s
        (HIGHWAY_POLL_S) until it is done or `timeout` s (HIGHWAY_PLOT_TIMEOUT) pass. One plot at a time. The result
        dict, or HighwayError in words for the page (Spansh's own error, unreachable, timed out). method: how the job
        is submitted ("GET" with the query, "POST" with form fields); the results are always asked with GET."""
        poll = HIGHWAY_POLL_S if poll is None else poll
        timeout = HIGHWAY_PLOT_TIMEOUT if timeout is None else timeout
        if self.session is None:
            raise HighwayError("Spansh cannot be reached (no network session)")
        async with self.sem_plot:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            d = await self._plot_get(url, params, method)
            while d.get("result") is None:
                job = d.get("job")
                if not isinstance(job, str) or not re.fullmatch(r"[\w-]{1,100}", job):
                    raise HighwayError("Spansh sent neither a route nor a job to wait for")
                if loop.time() + poll > deadline:
                    raise HighwayError(f"Spansh had not finished the route after {timeout:g} s: try again later")
                await asyncio.sleep(poll)
                d = await self._plot_get(SPANSH_RESULTS.format(job=job), None)
            return d["result"]

    async def _plot_get(self, url, params, method="GET"):
        """One request of a plot: Spansh's JSON answer (queued, or the result), or HighwayError."""
        try:
            call = (self.session.post(url, data={k: str(v) for k, v in (params or {}).items()}) if method == "POST"
                    else self.session.get(url, params=params))
            async with call as r:
                try:
                    d = await r.json(content_type=None)
                except ValueError:
                    d = None
                why = d.get("error") if isinstance(d, dict) else None
                if why:
                    raise HighwayError(f"Spansh: {why}")
                if r.status >= 400 or not isinstance(d, dict):
                    raise HighwayError(f"Spansh answered HTTP {r.status}: it may be down, try again later"
                                       if r.status >= 400 else "Spansh's answer was not JSON")
                return d
        except (ClientError, asyncio.TimeoutError) as e:
            raise HighwayError(f"Spansh cannot be reached ({type(e).__name__}): try again later") from e

    async def system_names(self, q):
        """Spansh's system names starting with `q` (the Highway's to field, as you type)."""
        async with self.sem_fast:
            async with self.session.get(SPANSH_SYSTEM_NAMES, params={"q": q}) as r:
                r.raise_for_status()
                d = await r.json(content_type=None)
        return [v for v in (d.get("values") or []) if isinstance(v, str)][:20] if isinstance(d, dict) else []

    async def system_id64(self, name):
        """A system's id64 from Spansh's search by name (the exact name, any case), or None when Spansh has none:
        the exact plotter takes id64s, not names (found 2026-10-03)."""
        rec = await self.system_record(name)
        return rec["id64"] if rec else None

    async def system_record(self, name):
        """{name, id64, x, y, z} of a system Spansh knows by this exact name (any case), or None."""
        if self.session is None:
            raise HighwayError("Spansh cannot be reached (no network session)")
        async with self.sem_fast:
            async with self.session.get(SPANSH_SYSTEM_SEARCH, params={"q": name}) as r:
                r.raise_for_status()
                d = await r.json(content_type=None)
        for x in (d.get("results") or []) if isinstance(d, dict) else []:
            if isinstance(x, dict) and str(x.get("name") or "").lower() == name.lower() \
                    and isinstance(x.get("id64"), int) and not isinstance(x.get("id64"), bool):
                return {"name": x["name"], "id64": x["id64"], "x": x.get("x"), "y": x.get("y"), "z": x.get("z")}
        return None

    def cached(self, id64):
        return cached_base(self.db, id64)

    def store(self, id64, updated_at, base):
        self.db.execute("INSERT OR REPLACE INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (id64, updated_at, json.dumps(base), time.time(), base["x"], base["y"], base["z"]))
        self.db.commit()

    async def lookup(self, id64, interactive=True):
        """The full Spansh record for one system, or None if Spansh has never heard of it."""
        async with (self.sem_fast if interactive else self.sem):
            async with self.session.get(SPANSH_DUMP.format(id64=id64)) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.json()

    async def edsm_system(self, name):
        """EDSM's record for a system by name, or None if EDSM doesn't know it either."""
        params = {"systemName": name, "showId": 1, "showCoordinates": 1, "showPrimaryStar": 1}
        async with self.sem_fast:
            async with self.session.get(EDSM_SYSTEM, params=params) as r:
                r.raise_for_status()
                d = await r.json()
        return d if isinstance(d, dict) and d.get("name") else None

    async def edsm_bodies(self, name):
        """EDSM's view of a system's bodies: {known: stars and planets it has, count: its body count (None unknown)},
        or {known: 0, count: None, missing: True} when EDSM has no record of it."""
        async with self.sem_fast:
            async with self.session.get(EDSM_BODIES, params={"systemName": name}) as r:
                r.raise_for_status()
                d = await r.json()
        if not isinstance(d, dict) or not d.get("name"):
            return {"known": 0, "count": None, "missing": True}
        bodies = [b for b in d.get("bodies") or [] if isinstance(b, dict) and b.get("type") in ("Star", "Planet")]
        return {"known": len(bodies), "count": d.get("bodyCount") if isinstance(d.get("bodyCount"), int) else None}

    async def edsm_sphere(self, pos, radius):
        """EDSM's systems within `radius` (at most EDSM_SPHERE_MAX: its API's documented limit; a larger radius is
        cut to it, and the refresh's status says so: review F48)."""
        params = {"x": pos["x"], "y": pos["y"], "z": pos["z"], "radius": min(radius, EDSM_SPHERE_MAX),
                  "showId": 1, "showCoordinates": 1, "showPrimaryStar": 1}
        async with self.sem:
            async with self.session.get(EDSM_SPHERE, params=params) as r:
                r.raise_for_status()
                d = await r.json()
        return d if isinstance(d, list) else []

    async def full_records(self, id64, updated_at, base, interactive=False):
        """Fetch a system's dump and cache its body records. `interactive` uses the fast lane: something
        on the page is waiting for this one (the bulk lane is for a refresh's many fetches)."""
        dump = await self.lookup(id64, interactive=interactive)
        if dump is None:
            # search knew the system but Spansh has no dump for it: remember that (until its updated_at
            # changes, or ON_DEMAND_MAX_AGE for on-demand lookups) instead of asking on every refresh or view
            base = dict(base, no_dump=True)
            self.store(id64, updated_at, base)
            return base
        system = dump.get("system") or {}
        values = {r["name"]: r for r in base.get("records") or []}  # search-level credit estimates
        records = []
        for b in system.get("bodies") or []:
            if b.get("type") not in ("Star", "Planet"):
                continue
            r = record_from_dump(base["name"], b)
            v = values.get(r["name"]) or {}
            r.update(value=v.get("value"), scan_value=v.get("scan_value"))
            records.append(r)
        base = dict(base, records=records, body_count=system.get("bodyCount") or base.get("body_count"))
        base.pop("no_dump", None)
        self.store(id64, updated_at, base)
        return base


def base_known(base, source=None):
    """Bodies Spansh/EDSM have on record in a base (stars and planets, as the honk counts them; not EDSM's
    placeholder star): the honk's count less this is how many are not on Spansh. None with no base, or with a
    stand-in base (source "own" or "route": a system nobody has reported, which knows nothing about bodies)."""
    if base is None or source in ("own", "route"):
        return None
    return sum(1 for r in base.get("records") or [] if r.get("type") in ("Star", "Planet") and not r.get("placeholder"))


def base_from_edsm(d):
    """An EDSM sphere/system record as a base: coordinates plus the primary star if given."""
    c, ps = d.get("coords") or {}, d.get("primaryStar") or {}
    records = []
    if ps.get("type"):
        # named after the system, not "A" (EDSM does not say): a placeholder merge_records drops once your
        # own scans have the main star, or a binary would list it twice
        records.append({"name": d["name"], "type": "Star", "subtype": ps["type"], "main": True,
                        "scoopable": bool(ps.get("isScoopable")), "terraformable": False, "full": False,
                        "placeholder": True})
    return {"v": CACHE_VERSION, "name": d["name"], "x": c.get("x"), "y": c.get("y"), "z": c.get("z"),
            "body_count": None, "records": records, "edsm": True}


def cached_source(b):
    """Whose a cached base is: "edsm" for one made from EDSM (find_system's fallback; an older cache entry is told by
    its placeholder-only records and unknown body count), else "spansh" (review F27)."""
    if b.get("edsm") or (b.get("body_count") is None and all((r or {}).get("placeholder") for r in b.get("records") or [])
                         and b.get("records")):
        return "edsm"
    return "spansh"


def base_from_search(s):
    """What we keep per Spansh system: position, FSS count and (maybe partial) body records."""
    return {"v": CACHE_VERSION, "name": s["name"], "x": s["x"], "y": s["y"], "z": s["z"],
            "body_count": s.get("body_count"),
            "records": [record_from_search(s["name"], b) for b in s.get("bodies") or []
                        if b.get("type") in ("Star", "Planet")]}


# --------------------------------------------------------------------------
# App state: the list the page shows, rebuilt on every arrival
# --------------------------------------------------------------------------

def browser_defaults_path(db_path):
    """browser_defaults.json: next to the database, so a copied folder or --db keeps its own."""
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), BROWSER_DEFAULTS_FILE)


def check_browser_defaults(doc):
    """(the settings document to save, None) or (None, why not): {version: 1, settings: {key: value}} with only
    BROWSER_SETTINGS keys (per-device keys and anything unknown are refused, not quietly dropped)."""
    if not isinstance(doc, dict) or doc.get("version") != 1 or not isinstance(doc.get("settings"), dict):
        return None, "expected {\"version\": 1, \"settings\": {...}}"
    unknown = sorted(k for k in doc["settings"] if k not in BROWSER_SETTINGS)
    if unknown:
        return None, "not a shared setting: " + ", ".join(unknown[:5]) + (" …" if len(unknown) > 5 else "")
    return {"version": 1, "settings": doc["settings"], "saved": iso_ts(time.time())}, None


def read_browser_defaults(path):
    """The saved browser defaults, or None (none saved, or a file that is not a valid settings document)."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if isinstance(doc, dict) and isinstance(doc.get("settings"), dict):
        # a key a later version renamed or dropped costs only that key, not every other saved setting (the
        # strict refusal of unknown keys is for a save, where it catches a bad upload)
        stale = sorted(k for k in doc["settings"] if k not in BROWSER_SETTINGS)
        if stale:
            print(f"{path}: ignoring settings no longer shared: {', '.join(stale)}", file=sys.stderr)
            doc = dict(doc, settings={k: v for k, v in doc["settings"].items() if k in BROWSER_SETTINGS})
    ok, _ = check_browser_defaults(doc)
    if not ok:   # null, [], 42, a string: valid JSON, but no settings document (Codex F9: the page must still load)
        return None
    # 'saved' is shown as a date on the page: a hand-edited number or object there would stop the page's script
    saved = doc.get("saved") if isinstance(doc.get("saved"), str) else None
    return dict(ok, saved=saved)


def write_browser_defaults(path, doc):
    """Save atomically: a .part file renamed over the old one, so a crash never leaves half a file."""
    with open(path + ".part", "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(path + ".part", path)


# The dated zips of builds before they were named after the database (local time): rotated only for the
# default database name, as older than any new one. Rotation deletes nothing else.
LEGACY_BACKUP_NAME = re.compile(r"outrider-\d{8}-\d{6}\.zip")
ARCHIVE_HEAD = 4096   # bytes of an archived journal that must match the live one before it is replaced


class _BackupRestarted(Exception):
    pass


def copy_database(src, dst, pages=256, pause=0.005, restarts=5):
    """Copy the database `src` into `dst` with SQLite's backup API, `pages` at a time with a short pause
    between: the read lock is held for one step, not the whole copy, so the tailer's commits (the main
    connection, rollback journal) wait milliseconds instead of the whole copy on a slow backup disk. A write in
    between restarts the copy (SQLite starts over to stay consistent); after `restarts` of those it is done in
    one step after all, so a busy writer cannot keep the backup from ever finishing."""
    last = [None, 0]

    def progress(status, remaining, _total):
        # a successful step always lowers `remaining`: one that did not (higher, or the same right after another
        # restart) was a restart; a busy step (SQLITE_BUSY / LOCKED) leaves it the same and is not counted
        if last[0] is not None and remaining >= last[0] and status in (sqlite3.SQLITE_OK, sqlite3.SQLITE_DONE):
            last[1] += 1
            if last[1] >= restarts:
                raise _BackupRestarted
        last[0] = remaining
    try:
        src.backup(dst, pages=pages, sleep=pause, progress=progress)
    except _BackupRestarted:
        src.backup(dst)


def backup_name(db_path, t=None):
    """The dated zip for a backup of db_path: outrider-<database name>-YYYYMMDD-HHMMSSZ.zip, in UTC (a clock
    going back an hour or a timezone change must not make a new zip sort before older ones). Named after the
    database so a second instance run with --db, sharing the backups folder, rotates only its own zips."""
    stem = os.path.splitext(os.path.basename(db_path))[0]
    return f"outrider-{stem}-{time.strftime('%Y%m%d-%H%M%S', time.gmtime(t))}Z.zip"


def _same_journal(src, out):
    """Is the archived `out` the start of `src`? Journals only grow, so a smaller copy of the same file matches
    it byte for byte at the start (the Fileheader line names the game session)."""
    try:
        with open(src, "rb") as a, open(out, "rb") as b:
            head, have = a.read(ARCHIVE_HEAD), b.read(ARCHIVE_HEAD)
    except OSError:
        return False
    return head[:len(have)] == have


def archive_journals(dirs, dest):
    """Copy every Journal.*.log in `dirs` into `dest` when the copy is missing, or when the live file has grown
    past it (journals are only ever appended to, so this brings the journal being written up to date too, and
    a closed one is copied once). An archived file is never replaced by a smaller one or by one that starts
    differently: another instance sharing the folder must not overwrite a journal with a different one.
    Plain files, never deleted: restoring is pointing --legacy at `dest`. A copy goes through a .part file of its
    own (another instance's copy of the same journal has its own), so an interrupted one never looks like a journal,
    and the archive is looked at again just before the copy replaces it: another instance that archived as much or
    more meanwhile keeps its copy (Codex F8: a lagging mirror's shorter copy replaced a fuller one). One file that cannot be copied (unreadable, a full disk)
    is skipped and reported, not the rest. Returns (files copied, the date of the newest journal in the
    archive or None, [(file name, why) for each one that failed])."""
    import shutil
    os.makedirs(dest, exist_ok=True)
    copied, failed = 0, []
    for d in dirs:
        for src in sorted(glob(os.path.join(glob_escape(d), "Journal.*.log"))):
            out = os.path.join(dest, os.path.basename(src))
            try:
                size = os.path.getsize(src)
            except OSError:
                continue   # gone since the listing
            try:
                have = os.path.getsize(out)
            except OSError:
                have = None   # not archived yet
            if have is not None and (size <= have or not _same_journal(src, out)):
                continue
            part = f"{out}.{os.getpid()}-{secrets.token_hex(3)}.part"
            try:
                shutil.copy2(src, part)
                try:
                    now = os.path.getsize(out)
                except OSError:
                    now = None
                if now is not None and now >= os.path.getsize(part):
                    os.remove(part)   # archived meanwhile, as far or further
                    continue
                os.replace(part, out)
            except OSError as e:
                failed.append((os.path.basename(src), e.strerror or str(e)))
                try:
                    os.remove(part)
                except OSError:
                    pass
                continue
            copied += 1
    newest = max((os.path.getmtime(f) for f in glob(os.path.join(glob_escape(dest), "Journal.*.log"))), default=None)
    return copied, time.strftime("%Y-%m-%d", time.gmtime(newest)) if newest else None, failed


def backup_zips(folder, db_path):
    """db_path's dated zips in `folder` (see backup_name; for the default database also the older
    outrider-YYYYMMDD-HHMMSS.zip names), oldest first. Raises OSError when the folder cannot be listed."""
    stem = os.path.splitext(os.path.basename(db_path))[0]
    mine = re.compile(re.escape(f"outrider-{stem}-") + r"\d{8}-\d{6}Z\.zip")
    legacy = os.path.basename(db_path) == os.path.basename(DB_PATH)
    return sorted((f for f in os.listdir(folder)
                   if (mine.fullmatch(f) or (legacy and LEGACY_BACKUP_NAME.fullmatch(f)))
                   and os.path.isfile(os.path.join(folder, f))),
                  key=lambda f: (not LEGACY_BACKUP_NAME.fullmatch(f), f))   # the old local-time names first


def check_zip(path):
    """None when every member of the zip reads back with its CRC, else what is wrong with it."""
    import zipfile
    import zlib
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
    except (zipfile.BadZipFile, OSError, zlib.error, EOFError) as e:   # zlib/EOF: a member's compressed data damaged
        return str(e) or type(e).__name__
    return f"{bad} is damaged" if bad is not None else None


def check_database(path):
    """None when SQLite's quick_check passes on the database file at `path` (opened read-only), else its first
    complaint."""
    try:
        con = sqlite3.connect(f"file:{urllib.parse.quote(os.path.abspath(path))}?mode=ro", uri=True)
        try:
            res = con.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        return str(e)
    return None if res == "ok" else res


def rotate_backups(folder, keep, db_path, current=None):
    """Delete db_path's dated zips (see backup_name) in `folder` beyond the newest `keep`, never `current` (the
    one just written). Nothing else is touched: not another database's zips, not the journal archive, not a
    zip you renamed, not any other file. Returns how many remain."""
    current = current and os.path.basename(current)
    zips = backup_zips(folder, db_path)
    keep = max(1, int(keep))
    old = [f for f in zips if f != current]
    drop = old[:max(0, len(zips) - keep)]
    for f in drop:
        os.remove(os.path.join(folder, f))
    return len(zips) - len(drop)


def backup_due(last, every_days, now=None):
    """Is an automatic backup due at start? `last` is the last_backup meta ({ts} of the last one that worked)."""
    if every_days <= 0:
        return False
    try:
        age = (time.time() if now is None else now) - ts_seconds((last or {}).get("ts") or "")
    except (TypeError, ValueError):
        return True   # never backed up
    return age >= every_days * 86400


class State:
    def __init__(self, db, journals, spansh, radius):
        self.db, self.journals, self.spansh, self.radius = db, journals, spansh, radius
        self.version = 0
        self.changed = asyncio.Event()   # set (and replaced) by bump(): long-polling pages wait on it
        self.bases = {}            # id64 -> (source, base) for systems in the current sphere
        self.systems = {}          # id64 -> row dict for the page
        self.visited = set()
        self.status = "starting"
        self.center = None
        self.refresh_task = None
        self.target = None         # classified FSD target for the page
        self.target_key = None
        self.target_seq = 0
        self.target_task = None
        self.searcher = None       # set once the Searcher exists
        self.speaker = None        # outrider.tts.Speaker, set at start (None in tests)
        self.player = None         # outrider.tts.LinePlayer: the tick that plays speech and sounds here (None in tests)
        self.sounds = outrider.tts.SoundBank()   # static/sounds.json rendered to WAV for it
        self.speech = None         # outrider.speech.SpeechLines, set at start (None in tests)
        self.honker = None         # outrider.honk.Honker, set at start (None in tests)
        self.simulate = False      # --simulate: the panels act as if the game were running (shown_status)
        self.game_pc = True        # [server] game_pc: False on a server away from the game PC (no keys, devices, clipboard, PC sound)
        self.button = None         # outrider.button.ButtonWatch when [copilot] enabled (None otherwise and in tests)
        # the voice's hush ({mode, until, sys}): here, not per browser, so the co-pilot button, a tablet and the
        # window that is speaking all see the same one. In memory only: a restart ends it
        self.hush = None
        self.firsts_watch_on = False   # [spansh] watch_firsts, set at start (off in tests)
        self.update_available = None   # a newer release on GitHub ({version, url, published}): watch_updates sets it
        self.firsts_watch_seq = 0      # bumps with each check (firsts_cached keys on it)
        self.firsts_watch_failed = {}  # {id64: time of its last failed check}: skipped for a day (in memory only)
        self._firsts_cache = None
        # the co-pilot channel ({seq, action, words}): the button and the Now bar ask the speaking window for a
        # status report, the last line again or a replay. Kept out of Journals.moments, whose checkpoint and
        # rollback during a journal re-read could replay or drop it
        self.copilot = {"seq": 0, "action": None, "words": None}
        # the voice (POST /api/ask): its phrases, the AI layer's settings (set by run()), and when a window that speaks
        # last asked for the payload (S24: whether an answer will be said on the PC)
        self.ask_phrases = outrider.ask.load_phrases()
        self.assistant = dict(outrider.ask.ASSISTANT)
        self.speaker_seen = None
        self.speaker_audio_blocked = False   # the speaking window's browser holds audio back until a click (the tablet says so)
        self.autohonk = dict(AUTOHONK)
        self._honk_arrival = None  # the arrival the auto honk last looked at
        self.honk_confirm = 10.0   # s to wait for the journal's discovery scan after the press
        self.honk_test = None      # the Test button's latest run: {seq, state, what, error}, shown in the dialog
        self.honk_test_task = None
        self.honk_test_countdown = AUTOHONK_TEST_COUNTDOWN
        self.db_path = None        # for backups (a second connection reads it on a worker thread)
        # the user's own files, also put in each backup zip: nothing rebuilds them from the journals (the config
        # is gitignored, speech.json is edited in place). The paths actually in use, set at start (None in tests)
        self.speech_path = None
        self.config_path = None
        self.backup_task = None
        self.backup_done_at = None  # time.monotonic() when the last backup ended
        self.seller_task = None
        self.seller_retry_at = None
        self._sampling_key = None
        self.unsold = None         # compute_unsold() result
        self.unsold_log = []       # [(finished at, result)]: the last few good estimates (sale estimates)
        self.unsold_dirty = outrider.unsold is not None
        self.unsold_at = 0.0
        self.unsold_from = 0.0     # when the estimate in self.unsold was started (wall clock): maybe_sale_left
        self.unsold_task = None
        self.map_cache = {}        # (id64, radius) -> Spansh systems, so reopening the map is instant
        self.dump_cache = {}       # id64 -> (time, Spansh dump) for the body detail panel
        self.carrier_task = None
        self.carrier_retry = {}    # carrier system id64 -> time.time() before which Spansh is not asked again
        self.value_dirty = set()   # systems whose unsold value changed: rows rebuilt, scan_version left alone
        self.row_failed = set()    # systems whose row failed to build (traceback printed once, retried each tick)
        self.retry_at = None       # when to ask Spansh again after a failed refresh
        self.retry_backoff = 30
        self.failed_dumps = set()  # systems whose body details failed last time
        self.sphere_cut = None     # ly: Nearby is complete only to here (Spansh had more than we fetch)
        self.dump_updated = {}     # id64 -> Spansh updated_at from the sphere search (for retries)
        self.dump_tries = {}       # id64 -> failed body-detail fetches this stay
        self.last_target = None    # the target we announced, kept after arrival clears it
        self.target_verdicts = {}  # id64 -> status for recent targets: a route re-targets on arrival
        self.arrival = None        # reconciliation of that announcement with the arrival scan
        self.arrival_seq = 0
        self.tail_error = None     # last journal-tailing exception, shown on the page
        self.materials_version = 0  # bumps when the materials inventory changes (Materials view keys on it)
        self._copilot_run = (None, None)   # (the run a tap started, its cancel token): a press while it counts cancels it
        self._copilot_cancelled = False    # that press's own gesture is the double press it meant
        self.counts_version = 0     # bumps with every Recount (the carrier's fold is cached on it and cargo_version)
        self._carrier_fold = (None, None)   # (key, outrider.cargo.carrier_fold's answer)
        # Spansh's commodity names ({ts, norm: {letters-only: name}}): the lookup asks by these; cached a week (meta,
        # live-only)
        self.spansh_commodities = meta_get(db, "spansh_commodities")
        self.scan_version = 0      # bumps only when your own scan data changes (Here/History views key on it)
        # bumps on a jump, a sale or a death: History refetches on this, not on every scan (its ledger is a
        # full pass over your bodies, run on the event loop)
        self.history_version = 0
        self._history_jump = None
        self.system_values = {}    # system name -> unsold cartographic value, from the last estimate
        t = journals.target        # whatever was targeted before we started: no sound for it
        self.startup_target_key = t and (t["id64"], t["ts"])
        self.scoop = ScoopWatch()  # fuel scooping: "tank full" / "scooping stopped at 64 percent"
        self._honk_running = None  # the arrival an auto honk is working on (the briefing waits for it)
        self._honk_cancel = None   # threading.Event: the running auto honk's own token (set by switching it off)
        self.honk_run_task = None  # the running auto honk (cancelled at shutdown with the State's other tasks)
        self._honk_done = None     # (arrival, time.time()) the last auto honk task ended
        self._fss_focus = None     # Status.json GuiFocus at the last tick (9 = the FSS)
        self._in_tunnel, self._tunnel_for = False, None   # in the hyperspace tunnel at the last tick; the charge it was for
        self._fss_closed = None    # (id64, arrival ts, time) the FSS was closed: judged FSS_SETTLE s later
        self._fss_warned = None    # (id64, arrival ts): "bodies still hidden" once per visit
        self._moment_extra = {}    # seq -> (key, fields): what moments_summary adds, kept while the key holds
        self._brief_all_found = {}  # arrival_brief seq -> all_found as first sent (the page reads each moment once)
        self.backup_wait_task = None   # the quit backup, waiting SHUTDOWN_BACKUP_DELAY
        self._shutdown_seen = journals.last_shutdown   # read before we started: not a quit to back up now
        self._last_session = (None, None)   # (key, numbers) for the Last session card
        self._this_session = (None, None)   # (key, numbers) for Now's This session line (S10)
        self.unsold_login = (None, None)    # (login_ts, the unsold estimate over the journals before that login)
        self._streak = (None, None)         # (key, strip) for the discovery streak
        # the surface map (Batch M1): show/hide with hysteresis, the last position the page was sent (the 5 m / 10°
        # bump), each rig's leash warning level said (1 at RIG_WARN, 2 at RIG_WARN_AGAIN), the last landing a
        # mining location marker was taken from
        self._surface_show = False
        self._surface_sent = None
        self._surface_told = False   # whether the page was last told the surface map shows (a flip either way wakes it)
        self._follow_up_seen = set()   # tick follow-up errors already printed (each traceback once)
        self._rig_leash = {}
        self._location_landing = None
        # the Neutron Highway: [highway] settings, the plot under way ({state: running | failed | done, plotter, from,
        # to, started, error}), the desktop clipboard (an outrider Clipboard, set at start; None in tests), the arrival
        # whose next system was copied, auto-target (the supercharge it last looked at, its task, what it did)
        self.highway_cfg = dict(HIGHWAY, background_image="", background_extent=list(HIGHWAY_BG_EXTENT),
                                background_opacity=HIGHWAY_BG_OPACITY)
        self.highway_plotting = None
        self.highway_task = None
        self.clipboard = None
        self._hw_copied = (meta_get(db, "highway") or {}).get("arrival_ts")   # copied before a restart: not again
        self._autotarget_boost = (journals.boost or {}).get("ts")
        self.autotarget_task = None
        self._autotarget_cancel = None   # threading.Event: the automatic run's own token (switch-off, route cleared/replaced)
        self._autotarget_next_cancel = None   # the same for a Target next / Retry run (route cleared/replaced only)
        self._autotarget_next_route = "highway"   # the route that run aims at: "highway" or "survey" (🎯 on a survey row)
        self.autotarget_last = None   # {system, ts, done, phase, label, why, dry_run, test}: the latest run's result
        self.targeter = None          # outrider.target.Targeter, set at start (None in tests)
        self.autotarget_running = None   # the target a sequence is pressing keys for now
        # the page's own run ("test now", or Target next / Retry): {seq, kind: test | next, state: counting | running |
        # done | failed, system, why, in: its countdown}
        self.autotarget_test = None
        self.autotarget_test_task = None
        self.autotarget_test_countdown = AUTOTARGET_TEST_COUNTDOWN
        self.password = ""   # [server] password: "" asks no device for one (set by run())
        self.signin_limit = outrider.auth.RateLimit()
        self._suggest = collections.OrderedDict()   # typed name -> Spansh's system names (HIGHWAY_SUGGEST_CACHE kept)
        self._hw_near = (None, None)   # ((route id, position id64), the nearest route row) while off the route
        # too much fuel for the next jump (highway_heavy_check): {key: (route id, row, arrival), live, said, t, look,
        # heavy: {need_t, have_t, distance, boost, next} or None}
        self._hw_heavy = {"key": None, "live": False, "said": False, "t": None, "look": None, "heavy": None}
        # Road to Riches: the plot under way (as highway_plotting), its task, the arrival whose next system was copied
        self.riches_plotting = None
        self.riches_task = None
        self.dock_cache = {}   # the Nearest finder's last Spansh search and permit check (DOCK_CACHE_S)
        # uploads (EDDN, EDSM: opt-in, off by default; outrider/uploads.py): switched in Settings -> Uploads, which
        # writes [eddn]/[edsm] enabled into the config file. senders: {service: async fn(rows)} (the services add theirs).
        self.upload_cfg = json.loads(json.dumps(outrider.uploads.DEFAULTS))
        self.upload_senders, self.upload_tasks, self.upload_session = {}, {}, None
        self.upload_status = {}   # service -> {error, at, held}: the last round's outcome for the status view
        self.uploads_hub = outrider.uploads.UploadHub(db, {"eddn": self.eddn_build, "edsm": self.edsm_build},
                                                      enabled=self.upload_queueing, holds={"edsm": outrider.edsm.hold},
                                                      max_ages={"eddn": outrider.eddn.CATCHUP_MAX_S},
                                                      idlers={"eddn": self.eddn_idle}, follow=self.upload_wanted,
                                                      quiet={"eddn": outrider.eddn.quiet},
                                                      save=lambda marks: meta_set(self.db, "upload_marks", marks))
        marks = meta_get(db, "upload_marks")   # how far each service has queued (live-only: a re-read keeps it)
        self.uploads_hub.marks = {k: v for k, v in marks.items() if isinstance(v, list)} if isinstance(marks, dict) else {}
        self.upload_senders["eddn"] = self.eddn_send
        self.upload_senders["edsm"] = self.edsm_send
        self.eddn_hold = outrider.eddn.SchemaHold()
        self.edsm_discard = outrider.edsm.DISCARD   # EDSM's list of unwanted events: the built-in copy until fetched
        self.edsm_discard_task = None
        self.edsm_dry_path = None                   # OUTRIDER_EDSM_DRYRUN: where the requests are logged (run(): data/)
        journals.uploads = self.uploads_hub
        # one uploader at a time (PLAN-edmc-functionality "One uploader at a time"): leases in the journal folders,
        # and EDMC on this PC. Refreshed by watch_leases every LEASE_EVERY_S.
        self.lease_others, self.lease_writable, self.edmc = {}, {}, None
        # service -> the host this instance gives way to (uploads.lease_owners); None until the others' leases are read
        self.lease_hold = None
        self.leases, self.lease_task = None, None
        self._rc_copied = (meta_get(db, "riches") or {}).get("arrival_ts")

    def bump(self):
        self.version += 1
        changed, self.changed = self.changed, asyncio.Event()
        changed.set()      # wakes every page request waiting in /api/nearby

    def payload(self):
        pos, jr, stamp = self.journals.pos, self.journals.jump_range, stamps()
        return {
            "version": self.version, "run_id": RUN_ID, "page_stamp": stamp["page"], "restart_needed": stamp["restart_needed"],
            "game_pc": self.game_pc,   # False: the page leaves out what needs the game PC
            "outrider": outrider.__version__,   # Settings' line beside the GitHub link
            # a newer release ({version, current, url, kind}: kind says how to update this install), else None
            "update": dict(self.update_available, current=outrider.__version__, kind=install_kind())
            if self.update_available else None,
            # the speaking window waits for a click before it can make a sound (it lapses with the window itself)
            "speaker_audio_blocked": bool(self.speaker_audio_blocked and self.speaker_present()),
            "status": self.status, "radius": self.radius,
            "radius_choices": sorted({float(x) for x in RADIUS_CHOICES} | {self.radius}),
            "sphere_cut": self.sphere_cut,
            "tts": self.speaker.info() if self.speaker else None,
            "sound_files": self.sounds.info() if self.sounds and self.sounds.own_dir else None,   # your own sounds (S16)
            "player": self.player.info() if self.player else None,
            "speech": self.speech.info() if self.speech else None,
            "autohonk": self.autohonk_info(),
            "autotarget": self.autotarget_info(), "rail": self.rail_info(),   # the tablet's game buttons
            "hush": self.hush_info(),
            "firsts_watch": self.firsts_watch_info(),
            "copilot": dict(self.copilot, button=self.button.status if self.button else None),
            "region": self.region_info(),
            "boost": (self.journals.boost or {}).get("value"),
            "on_body": self.on_body(),
            "near_body": self.near_body(),
            "uploads": self.uploads_summary(),
            "sampling": self.sampling_summary(),
            "surface": self.surface_summary(),
            # metres between samples per genus (a shipped table), shown before you land (review S1)
            "colony": outrider.bio.colony_table() if outrider.bio else None,
            "since_sale": self.since_sale(),
            "sellers": self.sellers_summary(),
            "next_stop": self.next_stop_summary(),
            "route": self.route_summary(),
            "highway": self.highway_summary(),
            "survey": self.survey_summary(),   # Road to Riches / Exomastery: the line under the tiles, as the Highway's
            "backup": dict(meta_get(self.db, "last_backup") or {}, running=bool(self.backup_task and not self.backup_task.done()),
                           every_days=BACKUP_EVERY_DAYS, keep=BACKUP_KEEP),
            "last_session": self.last_session(),
            "this_session": self.this_session(),
            "streak": self.streak(),
            "destination": self.destination(),
            "moments": self.moments_summary(),
            "hull": self.journals.hull,
            "modules": self.modules_summary(),
            "last_sale": self.journals.last_sale,
            # id: the exact id64 as a string (a JSON number above 2^53 loses digits in the browser), as rows have
            "position": dict(pos, id=str(pos["id64"]), visits=self.visit_count(pos["id64"])) if pos else pos,
            "previous": with_id(self.journals.prev),
            "commander": self.commander_summary(),
            "materials": self.materials_summary(), "jump_range": jr["ly"] if jr else None,
            # the range with the fuel and cargo aboard now (the fuel model), None without the Loadout's mass
            "jump_range_now": self.range_now(),
            "systems": list(self.systems.values()),
            "target": dict(with_id(self.target), leaving=self.leaving_summary(pos["id64"]), hop=self.target_hop(self.target))
                      if self.target and pos else with_id(self.target),
            "arrival": self.arrival,
            "scan_version": self.scan_version, "history_version": self.history_version,
            "cargo_version": f"{self.journals.cargo_version}.{self.counts_version}",   # the Materials tab's Cargo
            # read: moves with every journal line consumed (the Log tails on it; journal is to the second)
            "freshness": {"journal": self.journals.last_event_ts, "read": sum(self.journals.offsets.values()),
                          "status": (self.journals.status_json or {}).get("ts"),
                          "live": bool(self.shown_status().get("live")),
                          "simulated": bool(self.shown_status().get("simulated")),   # --simulate: an old journal is no fault
                          "dirs": LIVE_DIRS, "legacy": LEGACY_DIRS},
            "docked": self.docked_summary(),
            # the last Docked event's ts even while Status.json says you are not docked (out in the SRV at a
            # planetary port): a page that baselines then must not take the same dock as new when you board
            "docked_ts": (self.journals.docked or {}).get("ts"),
            "defaults": {"unsold_warn": UNSOLD_WARN, "unsold_urgent": UNSOLD_URGENT, "bio_min": BIO_MIN, "sounds": SOUNDS_DEFAULT,
                         "body_highlight": BODY_HIGHLIGHT, "bio_highlight": BIO_HIGHLIGHT,
                         "max_include_bonus": MAX_INCLUDE_BONUS, "high_gravity": HIGH_GRAVITY, "module_warn": MODULE_WARN,
                         "speech_styles": list(SPEECH_STYLES), "speech_profanity": SPEECH_PROFANITY,
                         "speech_profanity_pct": SPEECH_PROFANITY_PCT, "speech_danger_business": SPEECH_DANGER_BUSINESS,
                         "speech_names": SPEECH_NAMES, "speech_speed": SPEECH_SPEED,
                         "speak_bio_signals": SPEAK_BIO_SIGNALS, "speak_geo_signals": SPEAK_GEO_SIGNALS,
                         "speak_mapped": SPEAK_MAPPED, "codex_interesting": CODEX_INTERESTING,
                         "surface_alt": SURFACE_ALT, "rig_spacing": RIG_SPACING, "surface_map_min": SURFACE_MAP_MIN,
                         "surface_map_strip": SURFACE_MAP_STRIP, "rig_warn": RIG_WARN},
            "bio_rules": outrider.bio.rules_info() if outrider.bio else None,
            "fuel": self.fuel_summary(),
            "ship": self.journals.ship,
            "carrier": self.carrier_summary(),
            "here_star": self.here_star(),
            "codex_recent": self.codex_recent(),
            "tail_error": self.tail_error,
            "bookmarks": self.bookmarks(),
            "unsold": self.unsold,
        }

    # ---- the voice's hush and the co-pilot channel ----

    # ---- the config file from the page (the Settings dialog's Server settings; GET/POST /api/config) ----
    def config_file(self):
        return self.config_path or CONFIG_PATH

    @staticmethod
    def _config_settings(cfg, path=None):
        """settings_from on a parsed config alone (no flags, no environment, no auto-detected folders): what the file
        says, and the problems settings_from reports on stderr (as a list). With `path`, the file is read here, inside
        the same capture, so a file that does not parse says so (it showed defaults and no problem: the sweep)."""
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            if path is not None:
                cfg = load_config(path) if os.path.exists(path) else {}
            st = settings_from(cfg, args, None, ([], []))
        # only the config layer's own lines: redirect_stderr swaps sys.stderr for the whole process, so another
        # thread's warning (the unsold pass, a backup) printed meanwhile must not count as a config problem
        mine, ours = [], False
        for x in err.getvalue().splitlines():
            if x.startswith(("config", "[server]")) or (ours and x[:1].isspace()):   # an indented line goes on the last
                mine.append(x)
                ours = True
            else:
                ours = False
                if x.strip():
                    print(x, file=sys.stderr)   # someone else's line: on to the real log
        return st, mine

    def config_info(self):
        """Every config key the server knows, with its value (as the file has it, or the default), its kind and help;
        the password and the AI key only as set or not. Applied at the next start."""
        path = self.config_file()
        st, problems = self._config_settings(None, path)
        # [eddn]/[edsm] are switched in Settings -> Uploads only (one place): not listed among the Server settings
        secs = [s for s in outrider.config_edit.entries(config_text(st), config_choices())
                if s["section"] not in outrider.config_edit.HIDDEN_SECTIONS]
        for sec in secs:
            for k in sec["keys"]:
                if (sec["section"], k["key"]) in outrider.config_edit.SECRETS:
                    k.update(secret=True, set=bool(k["value"]), value=None)
        return {"path": path, "exists": os.path.exists(path), "sections": secs, "problems": problems}

    def config_save(self, changes, hidden=False):
        """POST /api/config {section: {key: value}}: those keys written into the config file in place (comments kept,
        the old file kept as .bak), only if the result reads back and settings_from finds nothing new wrong with it.
        (answer, status); the server uses the new values at its next start. hidden: the sections the page's own
        switches write (config_edit.HIDDEN_SECTIONS: Settings -> Uploads) may be written; the Server list never can."""
        if not isinstance(changes, dict) or not changes or not all(isinstance(v, dict) for v in changes.values()):
            return {"error": "expected {section: {key: value}}"}, 400
        if not hidden and set(changes) & outrider.config_edit.HIDDEN_SECTIONS:
            sec = min(set(changes) & outrider.config_edit.HIDDEN_SECTIONS)
            return {"error": f"[{sec}] is switched in Settings -> Uploads"}, 400
        path = self.config_file()
        st, before = self._config_settings(None, path)
        existed = os.path.exists(path)
        kinds = {(s["section"], k["key"]): (k["kind"], k.get("choices", ()))
                 for s in outrider.config_edit.entries(config_text(st), config_choices()) for k in s["keys"]}
        try:
            with open(path, encoding="utf-8-sig") as f:   # a BOM is dropped (and not written back)
                text = f.read()
        except FileNotFoundError:
            text = config_text(st)
        except OSError as e:
            return {"error": f"cannot read {path}: {e}"}, 500
        n = 0
        for sec, keys in changes.items():
            for key, value in keys.items():
                kind, choices = kinds.get((sec, key), (None, ()))
                if kind is None:
                    return {"error": f"[{sec}] {key} is not a setting"}, 400
                try:
                    text = outrider.config_edit.set_key(text, sec, key, outrider.config_edit.coerce(kind, value, choices))
                except ValueError as e:
                    return {"error": f"[{sec}] {key} {e}"}, 400
                n += 1
        try:
            cfg = outrider.config_edit.tomllib.loads(text)
        except (outrider.config_edit.tomllib.TOMLDecodeError, ValueError) as e:
            return {"error": f"the change would not read back ({e}); nothing written"}, 400
        _, after = self._config_settings(cfg)
        new = [x for x in after if x not in before]
        if new:
            return {"error": "nothing written: " + "; ".join(x.removeprefix("config: ") for x in new), "problems": new}, 400
        real = os.path.realpath(path)   # a config that is a symlink: the file it points to is written, the link kept
        try:
            if os.path.exists(real):
                shutil.copy2(real, real + ".bak")
            tmp = real + ".new"
            # the new file only readable by this user while written (it may hold passwords), then given the old one's mode
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
            if os.path.exists(real):
                shutil.copymode(real, tmp)
            else:
                os.chmod(tmp, 0o600)
            os.replace(tmp, real)
        except OSError as e:
            return {"error": f"cannot write {path}: {e}"}, 500
        return {"ok": True, "path": path, "changed": n, "backup": real + ".bak" if existed or os.path.exists(real + ".bak") else None,
                "restart": True}, 200

    SPEAKER_SEEN_S = 60   # a window that speaks asks for the payload at least every 25 s (the long poll)

    def speaker_present(self, now=None):
        """Whether a window with speech on speaks now (it says so in its long poll): an answer will be said."""
        now = time.monotonic() if now is None else now
        return self.speaker_seen is not None and now - self.speaker_seen < self.SPEAKER_SEEN_S

    async def ask(self, text, get):
        """POST /api/ask: a question in words -> (answer, status). A fixed command first (resources/ask.json), then the
        AI layer when [assistant] enabled. The answer goes to every window through the co-pilot channel: the window
        that speaks says it (an asked line: it speaks through a hush), the others (the tablet) show it as a caption.
        get: the in-process GET for the read-only tools."""
        cmd = outrider.ask.match(text, self.ask_phrases)
        matched, action = "fixed", "say"
        if cmd in ("hush", "unhush"):
            self.set_hush("30m" if cmd == "hush" else "off")
            words, action = ("Quiet for 30 minutes." if cmd == "hush" else "Voice back on."), "caption"   # the page says these
        elif cmd:
            words = await outrider.ask.fixed_answer(cmd, get, text=text)
        elif self.assistant.get("enabled"):
            matched = "ai"
            try:
                async with ClientSession(timeout=ClientTimeout(total=self.assistant["timeout"] + 5),
                                         headers={"User-Agent": USER_AGENT}) as session:
                    words = await outrider.ask.ai_answer(text, self.assistant, get, session)
            except outrider.ask.AIError as e:
                return {"error": e.why, "code": e.code}, {"ai_timeout": 504, "ai_off": 503}.get(e.code, 502)
            except Exception as e:  # noqa: BLE001 -- a backstop (R4): the AI layer's own failure, never a 500
                import traceback
                traceback.print_exc()
                return {"error": f"the AI layer failed ({type(e).__name__})", "code": "ai_error"}, 502
        else:
            matched = "none"
            words = ("I only know a few questions so far: a status report, fuel, unsold data, the next jump, what's left "
                     "here, the nearest unvisited system, hush and unhush.")
        words = outrider.tts.clip_text(words)
        self.copilot_action(action, words)
        return {"answer": words, "spoken": self.speaker_present(), "matched": matched, "command": cmd}, 200

    def set_hush(self, mode):
        """Hush the voice ("10m", "30m", "jump": until the position changes) or end it ("off"). Danger lines and
        the lines you ask for still speak; the page does the silencing."""
        pos = self.journals.pos
        if mode == "off":
            self.hush = None
        elif HUSH_MODES.get(mode):
            self.hush = {"mode": mode, "until": time.time() + HUSH_MODES[mode], "sys": None}
        else:
            self.hush = {"mode": "jump", "until": None, "sys": pos["id64"] if pos else None}
        self.bump()

    def hush_info(self):
        """The hush for the payload, or None once it has run out or you have jumped. `left` (s) lets a browser with
        its clock off count down right; `sys` is the id64 as a string, like position.id."""
        h, pos = self.hush, self.journals.pos
        if h and ((h["until"] is not None and time.time() >= h["until"])
                  or (h["mode"] == "jump" and pos and pos["id64"] != h["sys"])):
            self.hush = h = None
        if not h:
            return None
        return {"mode": h["mode"], "until": h["until"], "left": round(h["until"] - time.time(), 1) if h["until"] else None,
                "sys": str(h["sys"]) if h["sys"] is not None else None}

    def copilot_action(self, action, words=None):
        """A co-pilot request for the speaking window. "hush" is done here: a hold starts a hush until the next jump,
        and another hold (while any hush runs) ends it."""
        if action == "hush":
            self.set_hush("off" if self.hush_info() else "jump")
        self.copilot = {"seq": self.copilot["seq"] + 1, "action": action, "words": words}
        self.bump()

    COPILOT_TARGET_DELAY_S = 0.5   # after a single press is known to be one, before the keys (your hands off the controls)

    def copilot_gesture(self, gesture):
        """A gesture of the co-pilot button (the author's layout, 2026-10-08): a single press targets the next route
        system while you fly the ship (anywhere else it does nothing), a double press is the status report, a hold
        hushes. In the Rhino on a body every gesture marks a mining rig and does nothing else. button.py's names:
        "status" is the single press, "again" the double, "hush" the hold."""
        if self.in_rhino():
            self.mark_rig(time.time())
            return
        if self._copilot_cancelled:
            # this press stopped a tap's targeting while it counted down: a double press too slow for double_ms.
            # What was meant was the double press, so a tap now is the status report, not another target.
            self._copilot_cancelled = False
            if gesture == "status":
                self.copilot_action("status")
                return
        if gesture == "status":
            ctx, _ = outrider.rail.context_of(self.journals.status_json, (self.journals.vehicle or {}).get("srv_type"))
            if ctx == "ship":
                self.copilot_target()
            return
        self.copilot_action("status" if gesture == "again" else gesture)

    def copilot_press(self):
        """Every press of the co-pilot button as it happens (before its gesture is known): one during a tap's targeting
        countdown, or while the run still waits with no key pressed (the arrival's danger flag, an auto honk: state
        "running" before the Targeter has it; the Fable review of 2026-10-10, #4), cancels that run before any key is
        pressed (silently: the run sees its token), and its own gesture is then read as the double press it was meant
        to be (copilot_gesture)."""
        run, cancel = self._copilot_run
        if run is not None and run.get("state") in ("counting", "running") and self.autotarget_running is None \
                and cancel is not None and not cancel.is_set():
            cancel.set()
            self._copilot_cancelled = True
            self.bump()

    def copilot_next(self):
        """(start_autotarget_run's kind and aim, None) for the co-pilot button's press, or (None, why there is nothing to
        target). The author's order (2026-10-08): the next system of the survey / trade route (the slot's) first; with
        none there (no such route, complete, at its end), the Highway's next; with neither, the last reason found."""
        why = "no route is plotted"
        rc, rows = self.riches_state()
        if rc:
            nx = self.riches_next(rc, rows)
            if rc.get("done_ts"):
                why = "the route is complete"
            elif nx is None:
                why = "you are at the end of the route"
            else:
                tgt, why = self.route_target("survey", nx)
                if tgt:
                    return ("next", ("survey", nx)), None
        if meta_get(self.db, "highway"):
            tgt, why = self.autotarget_target(manual=True)
            if tgt:
                return ("next", None), None
        return None, why

    def copilot_target(self):
        """The co-pilot button's single press in the ship: Target next on the route the line shows, after
        COPILOT_TARGET_DELAY_S. Its result is spoken as Target next's always is; nothing to target, or a run that
        cannot start, is said too (an "autotarget" moment: what "nothing" has the personality lines)."""
        ts = iso_ts(time.time())
        nxt, why = self.copilot_next()
        if nxt is None:
            self.journals.moment("autotarget", ts, ok=False, what="nothing", why=why, text=f"Nothing to target: {why}.")
            self.bump()
            return
        kind, aim = nxt
        try:
            out, status = self.start_autotarget_run(kind, countdown=self.COPILOT_TARGET_DELAY_S, aim=aim)
        except RuntimeError:   # no event loop (a test calling it bare): nothing can run
            out, status = {"error": "auto-target is not running"}, 500
        if status < 400:
            self._copilot_run = (self.autotarget_test, self._autotarget_next_cancel)
        if status >= 400:
            self.journals.moment("autotarget", ts, ok=False, what="refused", why=out.get("error"),
                                 text=f"Not targeting: {out.get('error') or 'auto-target is not available'}.")
            self.bump()

    # ---- the surface map and Rhino mining rigs (Batch M1) ----

    def surface_here(self):
        """Where you are over a body, from the live Status.json: {system, body_id, name, lat, lon, heading, alt,
        radius, flags, flags2}; None with no body under you, or when which body it is is unknown."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        if not st.get("live") or not st.get("body") or st.get("lat") is None or not st.get("planet_radius") or not pos:
            return None
        here = self.journals.body_here
        if here and here.get("system") == pos["id64"] and here.get("name") == st["body"]:
            bid = here["body_id"]
        else:
            row = self.db.execute("SELECT body_id FROM own_bodies WHERE system=? AND name=?", (pos["id64"], st["body"])).fetchone()
            bid = row["body_id"] if row else None
        if bid is None:
            return None
        return {"system": pos["id64"], "body_id": bid, "name": st["body"], "lat": st["lat"], "lon": st["lon"],
                "heading": st.get("heading"), "alt": st.get("alt"), "radius": st["planet_radius"],
                "flags": st.get("flags") or 0, "flags2": st.get("flags2") or 0}

    @staticmethod
    def _settled_after(ts, launch_ts):
        """Whether the Status.json reading at ts is VEHICLE_SETTLE_S or more after the vehicle's launch."""
        try:
            return ts_seconds(ts) - ts_seconds(launch_ts) >= VEHICLE_SETTLE_S
        except (TypeError, ValueError):
            return False

    def in_rhino(self, h=None):
        """In the Rhino (the SRV the journal's LaunchSRV named mev_rhino) on a body, with a position."""
        h = h or self.surface_here()
        v = self.journals.vehicle or {}
        return bool(h and h["flags"] & FLAG_IN_SRV and v.get("srv_type") == RHINO)

    def surface_show(self, h):
        """Whether the surface map shows: below SURFACE_ALT, hidden above SURFACE_ALT + SURFACE_HIDE_PAD, unchanged in
        between (no flicker); always in the SRV, on foot or landed, never while the altitude is from the average
        radius (high up)."""
        if h is None:
            show = False
        elif h["flags"] & FLAG_ALT_AVG:
            show = False
        elif h["flags"] & (FLAG_IN_SRV | FLAG_LANDED) or h["flags2"] & 1:
            show = True
        elif h["alt"] is None:
            show = False
        elif h["alt"] < SURFACE_ALT:
            show = True
        elif h["alt"] > SURFACE_ALT + SURFACE_HIDE_PAD:
            show = False
        else:
            show = self._surface_show
        self._surface_show = show
        return show

    def rigs_out(self, system, body_id):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM surface_rigs WHERE system=? AND body_id=? AND picked_ts IS NULL ORDER BY n", (system, body_id))]

    def mark_rig(self, now):
        """The co-pilot's press in the Rhino: a tap within RIG_TAP_M of a rig that is out picks it up (its number is
        free again); anywhere else it places the next rig, RIG_BEHIND_M behind the cockpit along your heading, at the
        lowest free number (1-6), or says six are out. Spoken as a moment. Returns what it did, or None."""
        h = self.surface_here()
        if not self.in_rhino(h):
            return None
        ts, r = iso_ts(now), h["radius"]
        spot = (surface_offset(h["lat"], h["lon"], (h["heading"] + 180) % 360, RIG_BEHIND_M, r)
                if h["heading"] is not None else (h["lat"], h["lon"]))
        rigs = self.rigs_out(h["system"], h["body_id"])

        def gap(rig):   # from you or the new rig's spot to the rig (as marked, or where it was collected from)
            pts = [(rig["lat"], rig["lon"])] + ([(rig["site_lat"], rig["site_lon"])] if rig["site_lat"] is not None else [])
            return min(surface_m(a, b, la, lo, r) for a, b in ((h["lat"], h["lon"]), spot) for la, lo in pts)
        near = min(rigs, key=gap, default=None)
        if near and gap(near) <= RIG_TAP_M:
            self.db.execute("UPDATE surface_rigs SET picked_ts=?, lost=0 WHERE id=?", (ts, near["id"]))
            self.db.execute("DELETE FROM surface_rigs WHERE id=? AND tons = 0", (near["id"],))
            self._rig_leash.pop(near["id"], None)
            out = {"what": "picked", "n": near["n"], "id": near["id"], "text": f"Rig {near['n']} picked up."}
        elif len(rigs) >= RIG_SLOTS:
            out = {"what": "full", "n": None, "text": "Six rigs out."}
        else:
            n = min(set(range(1, RIG_SLOTS + 1)) - {x["n"] for x in rigs})
            cur = self.db.execute("INSERT INTO surface_rigs (system, body_id, body, n, lat, lon, placed_ts, minerals, tons) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0)", (h["system"], h["body_id"], h["name"], n, spot[0], spot[1], ts))
            out = {"what": "placed", "n": n, "id": cur.lastrowid, "lat": spot[0], "lon": spot[1], "text": f"Rig {n} placed."}
        self.db.commit()
        self.journals.moment("rig", ts, **out)
        self.bump()
        return out

    def watch_surface(self, now):
        """Each tick, from the live Status.json: the SRV left (its in-SRV flag gone), a Rhino collection gone quiet
        (said), the rigs' leash (a warning past RIG_WARN, again past RIG_WARN_AGAIN, lost past RIG_LOST_M), and a
        targeted mining location reached (its marker). True when anything was said or changed."""
        j = self.journals
        st, said = j.status_json or {}, j.moment_seq
        wrote = False
        # A fallback for a DockSRV the journals never showed: Status.json says you are back in your ship (InMainShip,
        # not merely "not in the SRV"), and a minute after the launch. While the SRV deploys from the bay Status.json
        # is written without the SRV flag for a while, and taking that for "out of it" lost the Rhino at every launch
        # (the button then gave the status report instead of marking a rig: found in game 2026-10-03). Never while on
        # foot (Flags2 bit 0): out of the SRV on foot, it waits on the ground for you to get back in.
        if st.get("live") and st.get("flags") is not None and not st["flags"] & FLAG_IN_SRV and \
                st["flags"] & FLAG_IN_MAIN_SHIP and j.vehicle and not (st.get("flags2") or 0) & 1 and \
                self._settled_after(st.get("ts"), j.vehicle.get("ts")):
            j.vehicle = None
            meta_set(self.db, "vehicle", None)
            wrote = True
        j.end_burst(now)
        h = self.surface_here()
        if self.in_rhino(h):
            for rig in self.rigs_out(h["system"], h["body_id"]):
                d = surface_m(h["lat"], h["lon"], rig["lat"], rig["lon"], h["radius"])
                level = self._rig_leash.get(rig["id"], 0)
                if d > RIG_LOST_M:
                    lose_rigs(self.db, iso_ts(now), "id=?", (rig["id"],))
                    self._rig_leash.pop(rig["id"], None)
                    j.moment("rig_leash", iso_ts(now), n=rig["n"], dist=round(d), lost=True,
                             text=f"Rig {rig['n']} lost: over {RIG_LOST_M / 1000:g} kilometres from the Rhino.")
                    wrote = True
                elif (d > RIG_WARN_AGAIN and level < 2 and RIG_WARN < RIG_WARN_AGAIN) or (d > RIG_WARN and level < 1):
                    self._rig_leash[rig["id"]] = 2 if d > RIG_WARN_AGAIN else 1
                    # which way it is, in eight sectors (review S9): the way back, in a short danger line
                    way = which_way(surface_bearing(h["lat"], h["lon"], rig["lat"], rig["lon"]), h.get("heading"))
                    j.moment("rig_leash", iso_ts(now), n=rig["n"], dist=round(d), lost=False, way=way,
                             text=f"Rig {rig['n']} is {d / 1000:.1f} kilometres away, {way}; it is lost at {RIG_LOST_M / 1000:g}.")
                elif d < RIG_WARN - 200 and level:
                    self._rig_leash[rig["id"]] = 0   # back in range: warn again next time
        wrote |= self.note_location(h)
        if wrote:
            self.db.commit()
        return wrote or j.moment_seq != said

    def note_location(self, h):
        """Arrived at a targeted planetary mining location (Status.json Destination #index=N, in this system): your
        position becomes its marker LN on this body, the first time you are down there with it targeted, and again
        at each landing of your ship with it targeted (where the ship set down is the location). True when stored."""
        st = self.journals.status_json or {}
        d = st.get("destination") if st.get("live") else None
        m = MINING_LOCATION_RE.search((d or {}).get("Name") or "")
        landed = bool(h and h["flags"] & FLAG_LANDED and not h["flags"] & FLAG_IN_SRV)
        if not landed:
            self._location_landing = None
        if not (m and h and d.get("System") == h["system"]):
            return False
        if d.get("Body") not in (None, h["body_id"]) and self.db.execute(
                "SELECT 1 FROM own_bodies WHERE system=? AND body_id=?", (h["system"], d["Body"])).fetchone():
            return False   # a location on another body of this system
        if not (landed or h["flags"] & FLAG_IN_SRV or h["flags2"] & 1):
            return False
        idx = int(m.group(1))
        key = (h["system"], h["body_id"], idx)
        have = self.db.execute("SELECT 1 FROM mining_locations WHERE system=? AND body_id=? AND idx=?", key).fetchone()
        if have and not (landed and self._location_landing != key):
            return False
        if landed:
            self._location_landing = key
        self.db.execute("INSERT OR REPLACE INTO mining_locations VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (*key, h["name"], h["lat"], h["lon"], st.get("ts")))
        return True

    def remove_rig(self, rid):
        """The page's remove: a rig still out is picked up, as a tap by it would (one picked up without a tap: the game
        writes nothing), its number free and its tons kept as a saved site; a saved rig site is forgotten. False when
        there is no such rig."""
        gone = self.db.execute("UPDATE surface_rigs SET picked_ts=?, lost=0 WHERE id=? AND picked_ts IS NULL",
                               (iso_ts(time.time()), rid)).rowcount
        if gone:
            self.db.execute("DELETE FROM surface_rigs WHERE id=? AND tons = 0", (rid,))
        else:
            gone = self.db.execute("DELETE FROM surface_rigs WHERE id=?", (rid,)).rowcount
        self.db.commit()
        self._rig_leash.pop(rid, None)
        if gone:
            self.bump()
        return bool(gone)

    def forget_sites(self, system, body_id):
        """Forget a body's saved sites (rigs picked up or lost, unmarked sites) and its location markers; rigs still
        out stay. How many rows went."""
        n = sum(self.db.execute(q, (system, body_id)).rowcount for q in (
            "DELETE FROM surface_rigs WHERE system=? AND body_id=? AND picked_ts IS NOT NULL",
            "DELETE FROM surface_sites WHERE system=? AND body_id=?",
            "DELETE FROM mining_locations WHERE system=? AND body_id=?"))
        self.db.commit()
        self.bump()
        return n

    def surface_moved(self, now):
        """True when the page should hear of your new position on the surface map: a move of SURFACE_BUMP_M or a turn
        of SURFACE_BUMP_DEG since the last one it was sent, at most every SURFACE_BUMP_S, and only while it shows; and
        once when it stops showing (climbing past the altitude changes nothing else the tick watches: review F24)."""
        h = self.surface_here()
        show = self.surface_show(h)
        told, self._surface_told = self._surface_told, show
        if not show:
            self._surface_sent = None
            return told
        last = self._surface_sent
        if last:
            if now - last[3] < SURFACE_BUMP_S:
                return False
            turn = abs(((h["heading"] or 0) - (last[2] or 0) + 180) % 360 - 180)
            if surface_m(h["lat"], h["lon"], last[0], last[1], h["radius"]) < SURFACE_BUMP_M and turn < SURFACE_BUMP_DEG:
                return False
        self._surface_sent = (h["lat"], h["lon"], h["heading"], now)
        return True

    def surface_sites(self, system, body_id, h=None):
        """The saved mining sites on a body: rigs picked up (or lost) with tons, and unmarked sites, each with its
        mining location (the nearest marker within LOCATION_NEAR_M) and, given where you are, its distance."""
        locs = [dict(r) for r in self.db.execute("SELECT idx, lat, lon FROM mining_locations WHERE system=? AND body_id=?",
                                                   (system, body_id))]
        radius = h["radius"] if h else None
        out = []
        rows = [dict(r, kind="rig") for r in self.db.execute(
            "SELECT id, n, coalesce(site_lat, lat) AS lat, coalesce(site_lon, lon) AS lon, minerals, tons, "
            "coalesce(last_ts, picked_ts) AS last_ts, lost FROM surface_rigs WHERE system=? AND body_id=? AND picked_ts IS NOT NULL",
            (system, body_id))]
        rows += [dict(r, kind="site", n=None, lost=0) for r in self.db.execute(
            "SELECT id, lat, lon, minerals, tons, last_ts FROM surface_sites WHERE system=? AND body_id=?", (system, body_id))]
        for r in rows:
            loc = None
            if radius and locs:
                dl, near = min((surface_m(r["lat"], r["lon"], x["lat"], x["lon"], radius), x["idx"]) for x in locs)
                loc = near if dl <= LOCATION_NEAR_M else None
            out.append({"id": r["id"], "kind": r["kind"], "n": r["n"], "lat": r["lat"], "lon": r["lon"],
                        "minerals": json.loads(r["minerals"] or "{}"), "tons": r["tons"], "last_ts": r["last_ts"],
                        "location": loc, "lost": bool(r["lost"]),   # a rig past the leash or left behind (F43)
                        "dist": round(surface_m(h["lat"], h["lon"], r["lat"], r["lon"], radius)) if h else None})
        # in a stable order (the page numbers the tags U1, S1... from it): not by the latest ton, which moves as you mine
        return sorted(out, key=lambda x: (x["location"] is None, x["location"] or 0, x["kind"], x["id"]))

    def mining_sites(self):
        """The Materials view's Mining sites: one entry per body with saved sites (rigs with tons, out or picked up,
        and unmarked sites) or tons in own_mined, nearest first. Tons per mineral are the larger of own_mined's
        (journal-derived: every ton the SRV refined there) and the saved sites' sum (live, the same tons placed), so
        a ton is never counted twice; `saved` says whether forget has anything to remove (a rig still out is not: it
        stays until picked up)."""
        bodies = {}

        def entry(system, body_id):
            return bodies.setdefault((system, body_id), {"mined": {}, "placed": {}, "rigs": 0, "picked": 0, "unmarked": 0,
                                                          "locations": [], "last": "", "name": None})
        for r in self.db.execute("SELECT system, body_id, name, tons, last_ts FROM own_mined WHERE tons > 0"):
            e = entry(r["system"], r["body_id"])
            e["mined"][r["name"]] = e["mined"].get(r["name"], 0) + r["tons"]
            e["last"] = max(e["last"], r["last_ts"] or "")
        for table, kind, picked in (("surface_rigs", "rigs", "picked_ts IS NOT NULL"), ("surface_sites", "unmarked", "1")):
            for r in self.db.execute(f"SELECT system, body_id, body, minerals, last_ts, {picked} AS picked FROM {table} WHERE tons > 0"):
                e = entry(r["system"], r["body_id"])
                e[kind] += 1
                e["picked"] += bool(r["picked"])
                e["name"] = e["name"] or r["body"]
                e["last"] = max(e["last"], r["last_ts"] or "")
                for m, n in json.loads(r["minerals"] or "{}").items():
                    e["placed"][m] = e["placed"].get(m, 0) + n
        for r in self.db.execute("SELECT system, body_id, idx, body FROM mining_locations ORDER BY idx"):
            if (r["system"], r["body_id"]) in bodies:   # a location marker alone (nothing mined there) is not a site
                e = bodies[(r["system"], r["body_id"])]
                e["locations"].append(r["idx"])
                e["name"] = e["name"] or r["body"]
        if not bodies:
            return []
        systems = sorted({s for s, _ in bodies})
        marks = ",".join("?" * len(systems))
        where = {r["id64"]: r for r in self.db.execute(f"SELECT id64, name, x, y, z FROM visits WHERE id64 IN ({marks})", systems)}
        names = {(r["system"], r["body_id"]): r["name"] for r in self.db.execute(
            f"SELECT system, body_id, name FROM own_bodies WHERE system IN ({marks})", systems)}
        pos = self.journals.pos
        out = []
        for (system, body_id), e in bodies.items():
            v = where.get(system)
            sname = v["name"] if v else None
            full = names.get((system, body_id)) or e["name"]
            minerals = {m: max(e["mined"].get(m, 0), e["placed"].get(m, 0)) for m in set(e["mined"]) | set(e["placed"])}
            d = dist(pos, v) if pos and v and v["x"] is not None and pos.get("x") is not None else None
            out.append({"system": sname, "id": str(system), "body_id": body_id,
                        "body": short_name(sname, full) if full else f"body {body_id}", "body_name": full,
                        "minerals": [{"name": m, "tons": t} for m, t in sorted(minerals.items(), key=lambda x: (-x[1], x[0]))],
                        "tons": sum(minerals.values()), "rigs": e["rigs"], "unmarked": e["unmarked"],
                        "locations": e["locations"], "last": e["last"] or None,
                        "saved": bool(e["picked"] or e["locations"]),
                        "distance": round(d, 1) if d is not None else None})
        return sorted(out, key=lambda x: (x["distance"] is None, x["distance"] or 0, x["system"] or "", x["body"]))

    def surface_bio(self, h):
        """The sample points of unfinished runs on this body, per species, with the colony distance: the run in
        progress is `current`, any other still in progress (journals read out of order) is drawn faint. Points of a
        run that is gone (abandoned, died with you) are not shown."""
        run = self.db.execute("SELECT system, body_id, species FROM own_organic WHERE done_ts IS NULL ORDER BY ts DESC LIMIT 1").fetchone()
        cur = (run["system"], run["body_id"], run["species"]) if run else None
        out = {}
        for p in self.db.execute(
                "SELECT sp.species, sp.genus, sp.n, sp.lat, sp.lon, o.species_name, o.genus_name, o.samples FROM sample_points sp "
                "JOIN own_organic o ON o.system = sp.system AND o.body_id = sp.body_id AND o.species = sp.species "
                "WHERE sp.system=? AND sp.body_id=? AND o.done_ts IS NULL ORDER BY sp.species, sp.n", (h["system"], h["body_id"])):
            s = out.get(p["species"])
            if not s:
                s = out[p["species"]] = {"species": p["species_name"] or p["species"], "genus": p["genus_name"],
                                         "samples": p["samples"], "current": cur == (h["system"], h["body_id"], p["species"]),
                                         "need": outrider.bio.colony_distance(p["genus"], p["genus_name"]) if outrider.bio else None,
                                         "points": []}
            d = surface_m(h["lat"], h["lon"], p["lat"], p["lon"], h["radius"])
            s["points"].append({"n": p["n"], "lat": p["lat"], "lon": p["lon"], "dist": round(d)})
        for s in out.values():
            near = min((p["dist"] for p in s["points"]), default=None)
            s["clear"] = bool(s["need"] and near is not None and near >= s["need"])
        return sorted(out.values(), key=lambda s: not s["current"])

    def surface_summary(self, now=None):
        """The surface map's block of the payload while you are over a body (None otherwise): where you are, whether
        the map shows, the ship, the rigs out, the saved sites, the mining locations and the bio sample points."""
        h = self.surface_here()
        if not h:
            self._surface_show = False
            return None
        now = time.time() if now is None else now
        dist = lambda lat, lon: round(surface_m(h["lat"], h["lon"], lat, lon, h["radius"]))
        m = self.journals.ship_marker
        ship = ({"lat": m["lat"], "lon": m["lon"], "dist": dist(m["lat"], m["lon"])}
                if m and (m["system"], m["body_id"]) == (h["system"], h["body_id"]) else None)
        rigs = [{"id": r["id"], "n": r["n"], "lat": r["lat"], "lon": r["lon"], "placed_ts": r["placed_ts"],
                 "last_ts": r["last_ts"], "minerals": json.loads(r["minerals"] or "{}"), "tons": r["tons"],
                 "dist": dist(r["lat"], r["lon"]), "full": rig_full(r, now)} for r in self.rigs_out(h["system"], h["body_id"])]
        locs = [{"n": r["idx"], "lat": r["lat"], "lon": r["lon"], "dist": dist(r["lat"], r["lon"])} for r in self.db.execute(
            "SELECT idx, lat, lon FROM mining_locations WHERE system=? AND body_id=? ORDER BY idx", (h["system"], h["body_id"]))]
        return {"body": short_name(self.journals.pos["name"], h["name"]), "system": str(h["system"]), "body_id": h["body_id"],
                "lat": h["lat"], "lon": h["lon"], "heading": h["heading"], "alt": h["alt"], "radius": h["radius"],
                "show": self.surface_show(h), "rhino": self.in_rhino(h), "ship": ship, "rigs": rigs,
                # for a browser's own show/hide altitude (the page's surface_alt setting): down on the ground (landed,
                # SRV, on foot: always shows) and an altitude from the average radius (never shows)
                "down": bool(h["flags"] & (FLAG_IN_SRV | FLAG_LANDED) or h["flags2"] & 1), "alt_avg": bool(h["flags"] & FLAG_ALT_AVG),
                "sites": self.surface_sites(h["system"], h["body_id"], h), "locations": locs, "bio": self.surface_bio(h),
                "tags": self.bio_tags_here(h)[:BIO_TAGS_SHOWN]}

    def bio_tags_here(self, h):
        """Plants tagged on this body (bio_tags) for species not finished here, nearest first: {species, genus,
        lat, lon, dist, bearing, way, current (the run in progress is this species), usable (outside the colony
        distance of every sample of that run: a sample there would count)}. h: surface_here()."""
        # matched to the sample runs by species code or name: a run's code for the older species need not be the rules'
        same = lambda t, r: t["species"] == r["species"] or (t["name"] or "").lower() == (r["species_name"] or "").lower()
        done = [dict(r) for r in self.db.execute("SELECT species, species_name FROM own_organic WHERE system=? AND body_id=? "
                                                 "AND done_ts IS NOT NULL", (h["system"], h["body_id"]))]
        run = self.db.execute("SELECT system, body_id, species, species_name FROM own_organic WHERE done_ts IS NULL "
                              "ORDER BY ts DESC LIMIT 1").fetchone()
        run = dict(run) if run and (run["system"], run["body_id"]) == (h["system"], h["body_id"]) else None
        pts = [dict(r) for r in self.db.execute("SELECT lat, lon FROM sample_points WHERE system=? AND body_id=? AND species=?",
                                                (h["system"], h["body_id"], run["species"]))] if run else []
        out = []
        for t in self.db.execute("SELECT species, genus, name, lat, lon FROM bio_tags WHERE system=? AND body_id=? ORDER BY ts",
                                 (h["system"], h["body_id"])):
            if any(same(t, r) for r in done):
                continue
            sp = outrider.bio.species_by_name(t["name"]) if outrider.bio else None
            genus = (sp or {}).get("genus") or (t["name"] or "").split(" ")[0] or None
            need = outrider.bio.colony_distance(t["genus"], genus) if outrider.bio else None
            cur = bool(run and same(t, run))
            usable = not (cur and need and any(surface_m(p["lat"], p["lon"], t["lat"], t["lon"], h["radius"]) < need for p in pts))
            bearing = surface_bearing(h["lat"], h["lon"], t["lat"], t["lon"])
            out.append({"species": t["name"], "genus": genus, "lat": t["lat"], "lon": t["lon"],
                        "dist": round(surface_m(h["lat"], h["lon"], t["lat"], t["lon"], h["radius"])),
                        "bearing": round(bearing), "way": which_way(bearing, h.get("heading")),
                        "current": cur, "usable": usable, "code": t["species"]})
        return sorted(out, key=lambda t: t["dist"])

    # ---- commander, materials, fuel, carrier, current system ----

    def make_backup(self):
        """A backup in BACKUP_DIR: a dated zip holding a consistent copy of the database (SQLite's backup API,
        safe while the tailer writes) and the browser defaults if saved; then every live journal archived into
        BACKUP_DIR/journals (copied once, see archive_journals); then this database's dated zips beyond
        BACKUP_KEEP deleted (see backup_name). A failure before the zip is written stops it before the rotation,
        so nothing is ever deleted for a backup that did not work; once the zip is good, a journal that could
        not be archived is reported (warning: the backup itself worked) but the rotation still runs, so a lasting
        failure cannot pile up zips. Legacy folders stay out of the archive: they are a copy of something already
        and never change. The zip also holds the speech file and the config file in use when they exist, and the lines you banned (see
        State.speech_path); one of those that cannot be read is a warning too. Runs on a worker thread; returns
        {path, size, kept, journals_to, copied, files, verified} (+ warning), files being the names inside the
        zip. The database copy must pass SQLite's quick_check and the zip testzip() before the zip replaces
        anything or the rotation runs; a copy or zip that fails raises (and the bad zip is deleted)."""
        import zipfile
        os.makedirs(BACKUP_DIR, exist_ok=True)
        name = backup_name(self.db_path)
        path = os.path.join(BACKUP_DIR, name)
        tmp_db = os.path.join(BACKUP_DIR, f".db-{name[:-4]}.sqlite")
        try:
            # read-only, and never created: a database moved or renamed while the server runs must fail the
            # backup, not copy a new empty file and rotate a good zip out for it
            src = sqlite3.connect(f"file:{urllib.parse.quote(os.path.abspath(self.db_path))}?mode=ro", uri=True)
            dst = sqlite3.connect(tmp_db)
            try:
                copy_database(src, dst)
                # the copy must read back before it goes in the zip: a bad backup never rotates a good one out
                problem = dst.execute("PRAGMA quick_check").fetchone()[0]
                if problem != "ok":
                    raise RuntimeError(f"the database copy failed its check: {problem}")
            finally:
                dst.close(); src.close()
            with zipfile.ZipFile(path + ".part", "w", zipfile.ZIP_DEFLATED) as z:
                z.write(tmp_db, os.path.basename(self.db_path))
                defaults = browser_defaults_path(self.db_path)
                files = [os.path.basename(self.db_path)]
                if os.path.exists(defaults):
                    z.write(defaults, BROWSER_DEFAULTS_FILE)
                    files.append(BROWSER_DEFAULTS_FILE)
                # your lines and your settings: extras, so one that cannot be read is a warning, never a failed
                # backup (the database is what the zip is for)
                extra_failed = []
                banned = outrider.speech.banned_path(self.speech_path) if self.speech_path else None
                for src_path, arc in ((self.speech_path, "speech.json"), (banned, outrider.speech.BANNED_FILE),
                                      (self.config_path, "ed_outrider.toml")):
                    if not src_path or not os.path.exists(src_path):
                        continue
                    try:
                        z.write(src_path, arc)
                        files.append(arc)
                    except OSError as e:
                        extra_failed.append(f"{arc} not backed up ({e.strerror or e})")
            # every member read back with its CRC before the zip counts (the finally deletes a bad one)
            bad = check_zip(path + ".part")
            if bad:
                raise RuntimeError(f"the zip failed its check: {bad}")
            os.replace(path + ".part", path)
        finally:
            # never leave the database copy or a half-written zip behind (a full disk would only get fuller)
            for leftover in (tmp_db, path + ".part"):
                try:
                    os.remove(leftover)
                except FileNotFoundError:
                    pass
        size = os.path.getsize(path)
        extra_warning = "; ".join(extra_failed) or None
        try:
            copied, journals_to, failed = archive_journals(LIVE_DIRS, os.path.join(BACKUP_DIR, "journals"))
            warning = (f"{len(failed)} journal{'' if len(failed) == 1 else 's'} not archived ({failed[0][0]}: {failed[0][1]}"
                       + (", …" if len(failed) > 1 else "") + ")") if failed else None
        except OSError as e:   # the archive folder itself (cannot be made, a full disk): the zip still counts
            copied, journals_to, warning = 0, None, f"journal archive: {e.strerror or e}"
        if extra_warning:
            warning = f"{extra_warning}; {warning}" if warning else extra_warning
        try:
            kept = rotate_backups(BACKUP_DIR, BACKUP_KEEP, self.db_path, current=path)
        except OSError as e:   # an old zip that cannot be removed: this one is still good and still the latest
            msg = f"old backups not rotated ({os.path.basename(e.filename) + ': ' if e.filename else ''}{e.strerror or e})"
            warning = f"{warning}; {msg}" if warning else msg
            try:
                kept = rotate_backups(BACKUP_DIR, 10 ** 9, self.db_path)   # deletes nothing: just the count
            except OSError:
                kept = None
        out = {"path": path, "size": size, "kept": kept, "journals_to": journals_to, "copied": copied, "files": files,
               "verified": True}   # the database copy passed quick_check and the zip testzip()
        # not an error: the database zip was written and counts as the latest backup (the Data tile goes amber)
        return dict(out, warning=warning) if warning else out

    async def backup(self, auto=False):
        try:
            out = await asyncio.get_running_loop().run_in_executor(None, self.make_backup)
            meta_set(self.db, "last_backup", dict(out, ts=iso_ts(time.time()), auto=auto,
                                                  journals_dir=os.path.join(BACKUP_DIR, "journals")))
            self.db.commit()
            print(f"backup written{' (automatic)' if auto else ''}: {out['path']} ({out['size'] / 1e6:.1f} MB, "
                  f"{out['kept']} kept; {out['copied']} journal{'' if out['copied'] == 1 else 's'} archived)")
            if out.get("warning"):
                print(f"backup: {out['warning']}", file=sys.stderr)
        except Exception as e:
            # the last good backup's fields stay (its time and path); the error turns the Data tile red
            meta_set(self.db, "last_backup", dict(meta_get(self.db, "last_backup") or {}, auto=auto,
                                                  error=f"{type(e).__name__}: {e}", error_ts=iso_ts(time.time())))
            self.db.commit()
            print(f"backup failed: {type(e).__name__}: {e}", file=sys.stderr)
        self.backup_done_at = time.monotonic()
        self.bump()

    def start_backup(self, auto=False):
        """The header's "back up now", and the automatic ones: (response, HTTP status). One at a time, and not
        again within BACKUP_MIN_GAP of the last, so a stuck key or a looping script cannot fill the disk with
        copies (an automatic one that close to a manual one is not needed either)."""
        if not self.db_path:
            return {"error": "no database path"}, 500
        if self.backup_task and not self.backup_task.done():
            return {"running": True}, 200
        if self.backup_done_at is not None and time.monotonic() - self.backup_done_at < BACKUP_MIN_GAP:
            return {"error": f"the last backup finished under {BACKUP_MIN_GAP} s ago; try again in a minute"}, 429
        self.backup_task = asyncio.create_task(self.backup(auto))
        self.bump()
        return {"running": True}, 200

    def maybe_backup_on_quit(self, now=None):
        """The game just quit (a live Shutdown): an automatic backup SHUTDOWN_BACKUP_DELAY s later. A Shutdown
        read from an old journal (a fresh import, a restart after the game closed) is not a quit just now:
        otherwise an import would back up once for every evening in the journals."""
        ts = self.journals.last_shutdown
        if ts == self._shutdown_seen:
            return
        self._shutdown_seen = ts
        if BACKUP_EVERY_DAYS <= 0 or not ts:
            return
        try:
            age = (time.time() if now is None else now) - ts_seconds(ts)
        except (TypeError, ValueError):
            return
        if age > SHUTDOWN_LIVE_S:
            return

        async def later():
            await asyncio.sleep(SHUTDOWN_BACKUP_DELAY)
            self.start_backup(auto=True)
        self.backup_wait_task = asyncio.create_task(later())

    def since_sale(self):
        """Days, jumps and light-years since your last cartographic sale (the Unsold tile's turn-back line)."""
        key = (self.scan_version, self.version // 50)
        if getattr(self, "_since_sale_key", None) != key:
            last = self.db.execute("SELECT max(ts) FROM sale_events WHERE kind = 'carto'").fetchone()[0]
            if not last:
                self._since_sale = None
            else:
                st = self.span_stats(last, "~")
                self._since_sale = {"ts": last, "days": round((time.time() - ts_seconds(last)) / 86400, 1),
                                    "jumps": st["jumps"], "ly": st["ly"]}
            self._since_sale_key = key
        return self._since_sale

    def sampling_summary(self):
        """While you are on a body with a sample run in progress: how far you are from the samples you have
        taken, against the genus's colony distance. None otherwise (or when positions are unknown).
        On a body while the run in progress is on another body (in this system or any other): {"elsewhere":
        {species, genus, samples, body, system, value}}, since the first Log of a new species here discards it
        (the page shows it at 2 of 3, or when the run is worth your bio threshold)."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        ob = self.on_body()
        if not ob or not outrider.bio:
            return None
        run = self.db.execute("SELECT system, body_id, species, genus_name, species_name, samples FROM own_organic "
                              "WHERE done_ts IS NULL ORDER BY ts DESC LIMIT 1").fetchone()
        if not run:
            return None
        # The run must be on the body you are on: an abandoned run elsewhere in the system would give a
        # distance across two planets (and a false "clear to sample"). A body you never scanned cannot be
        # told apart by name, so a run in this system is kept then.
        here = self.db.execute("SELECT body_id FROM own_bodies WHERE system=? AND name=?", (pos["id64"], ob["full"])).fetchone()
        if run["system"] != pos["id64"] or (here and here["body_id"] != run["body_id"]):
            return {"elsewhere": self.run_elsewhere(run)}
        if st.get("lat") is None or not st.get("planet_radius"):
            return None
        pts = [dict(r) for r in self.db.execute("SELECT genus, lat, lon, n FROM sample_points WHERE system=? AND body_id=? AND species=?",
                                                (run["system"], run["body_id"], run["species"]))]
        need = outrider.bio.colony_distance(pts[0]["genus"] if pts else None, run["genus_name"])
        out = {"genus": run["genus_name"], "species": run["species_name"], "samples": run["samples"], "need": need,
               "points": len(pts), "nearest": None, "to_go": None, "clear": None, "tag": None}
        if pts and need:
            nearest = min(outrider.bio.surface_distance(st["lat"], st["lon"], p["lat"], p["lon"], st["planet_radius"]) for p in pts)
            out.update(nearest=round(nearest), to_go=max(0, round(need - nearest)), clear=nearest >= need)
        # the nearest plant of this species you tagged with the composition scanner where a sample would count (BioScan's
        # waypoint): how far, and which way to turn (heading-relative, degrees right positive)
        h = {"system": run["system"], "body_id": run["body_id"], "lat": st["lat"], "lon": st["lon"],
             "radius": st["planet_radius"], "heading": st.get("heading")}
        tag = next((t for t in self.bio_tags_here(h) if t["current"] and t["usable"]), None)
        if tag:
            turn = None if h["heading"] is None else round(((tag["bearing"] - h["heading"] + 540) % 360) - 180)
            out["tag"] = {"dist": tag["dist"], "bearing": tag["bearing"], "turn": turn, "way": tag["way"],
                          "lat": tag["lat"], "lon": tag["lon"]}
        return out

    def run_elsewhere(self, run):
        """A sample run in progress on another body, for the on-body strip: what it is, where, and what it pays
        (with the x5 first footfall)."""
        body = self.db.execute("SELECT name FROM own_bodies WHERE system=? AND body_id=?", (run["system"], run["body_id"])).fetchone()
        where = self.locate(run["system"])
        sysname = where[0] if where else None
        f = self.db.execute("SELECT 1 - bio_x5 AS was_footfalled FROM own_firsts WHERE system=? AND body_id=?", (run["system"], run["body_id"])).fetchone()
        v = outrider.bio.species_value(run["species_name"])
        return {"species": run["species_name"], "genus": run["genus_name"], "samples": run["samples"],
                "body": short_name(sysname, body["name"]) if body and sysname else body["name"] if body else None,
                "system": sysname if run["system"] != self.journals.pos["id64"] else None,
                "value": v * (5 if f and f["was_footfalled"] == 0 else 1) if v else None}

    def on_body(self):
        """The body you are landed on, driving on or walking on (Status.json), else None."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        if not st.get("live") or not st.get("body") or not pos:
            return None
        flags, flags2 = st.get("flags") or 0, st.get("flags2") or 0
        how = "on foot" if flags2 & 1 else "in the SRV" if flags & (1 << 26) else "landed" if flags & 2 else None
        if not how:
            return None
        # which vehicle: Status.json's SRV flag is the same for the Nomad, the Rhino and the Scarab; the journal's
        # launch says which ("SRV Rhino" -> "Rhino"; None when it is not known, the page then says "the SRV")
        label = (self.journals.vehicle or {}).get("label") if how == "in the SRV" else None
        vehicle = re.sub(r"^SRV ", "", label) if isinstance(label, str) and label.strip() else None
        return {"body": short_name(pos["name"], st["body"]), "full": st["body"], "how": how, "vehicle": vehicle,
                "system": str(pos["id64"])}

    def near_body(self):
        """In your ship over a body below NEAR_BODY_ALT m (orbital cruise or flying, not landed): the on-body strip shows
        that body's bio card already (BioScan's "near surface" focus), to pick where to land. None otherwise, and
        whenever on_body() applies (landed, SRV, on foot)."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        if not st.get("live") or not st.get("body") or not pos or st.get("lat") is None:
            return None
        flags, flags2 = st.get("flags") or 0, st.get("flags2") or 0
        if not flags & FLAG_IN_MAIN_SHIP or flags & (FLAG_LANDED | FLAG_IN_SRV | FLAG_ALT_AVG) or flags2 & 1:
            return None
        alt = st.get("alt")
        if not isinstance(alt, (int, float)) or alt >= NEAR_BODY_ALT:
            return None
        return {"body": short_name(pos["name"], st["body"]), "full": st["body"], "how": "flying low", "alt": round(alt),
                "system": str(pos["id64"])}

    def destination(self):
        """The in-game destination when it is a body in the system you are in (Status.json), else None."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        d = st.get("destination") if st.get("live") else None
        if not d or not pos or d.get("System") != pos["id64"] or d.get("Body") is None:
            return None
        # near: the body you are flying near (Status.json BodyName), for Now's heading-to line: its supercruise time
        # is from the arrival star, so it is shown only while you are near nothing or near that star
        return {"body_id": d["Body"], "name": short_name(pos["name"], d.get("Name") or ""),
                "near": short_name(pos["name"], st["body"]) if st.get("body") else None}

    def region_info(self):
        """The galactic region you are in (codex entries are per region) and whether it is a nebula zone."""
        pos = self.journals.pos
        if not pos or not outrider.bio:
            return None
        name = outrider.bio.region_name(pos["x"], pos["y"], pos["z"])
        return {"name": name, "nebula": bool(outrider.bio.in_nebula({"name": pos["name"], "x": pos["x"], "y": pos["y"], "z": pos["z"]}))}

    def moments_summary(self):
        """The latest journal moments for the page's alerts, with scans and bio signals priced: the page
        compares them with your (per-browser) highlight levels and announces only what crosses them."""
        out, ctxs = [], {}
        # all of them (the deque holds 16): the page announces those past the last seq it saw, so a burst
        # between two polls (a throttled tab, a reconnect) must not drop the oldest
        for m in list(self.journals.moments):
            m = dict(m)
            if m["kind"] == "signals":
                where = self.locate(m["system"])
                m.update(system=str(m["system"]), body=short_name(where[0], m["body_name"]) if where else m["body_name"])
            if m["kind"] in ("scan", "bio"):
                row = self.db.execute("SELECT name, record FROM own_bodies WHERE system=? AND body_id=?",
                                      (m["system"], m["body_id"])).fetchone()
                where = self.locate(m["system"])
                if not row or not where:
                    continue
                rec = json.loads(row["record"])
                sysname = where[0]
                m.update(system=str(m["system"]), system_name=sysname, body=short_name(sysname, rec["name"]),
                         subtype=rec.get("subtype"), terraformable=bool(rec.get("terraformable")),
                         landable=bool(rec.get("landable")), first_discovered=rec.get("was_discovered") is False,
                         mapped_before=rec.get("was_mapped") is True,   # someone else mapped it (your scan says)
                         notable=NOTABLE_PLANETS.get(rec.get("subtype")))
                if rec.get("ed") and outrider.unsold:
                    m["base_value"] = outrider.unsold.body_value(dict(rec["ed"], first_discovered=False, first_mapped=False),
                                                           True, False, True)
                if m["kind"] == "bio":
                    if m["system"] not in ctxs:
                        recs = [json.loads(r["record"]) for r in self.db.execute(
                            "SELECT record FROM own_bodies WHERE system=?", (int(m["system"]),))]
                        star = self.db.execute("SELECT star_class FROM jumps WHERE id64=? ORDER BY ts DESC LIMIT 1",
                                               (int(m["system"]),)).fetchone()
                        cnt = self.db.execute("SELECT body_count FROM own_systems WHERE id64=?", (int(m["system"]),)).fetchone()
                        ctxs[m["system"]] = (bio_context(sysname, recs, where[1], where[2], where[3],
                                                         star["star_class"] if star else None, cnt and cnt[0]),
                                             star["star_class"] if star else None)
                    ctx, star = ctxs[m["system"]]
                    m["bio_value"], _ = bio_guess(dict(rec, bio=m.get("signals") or 1), star, None, ctx)
            if m["kind"] in self.MOMENT_EXTRA:
                extra = self.moment_extra(m)
                if extra is None:
                    continue
                m.update(extra)
            out.append(m)
        seqs = {m["seq"] for m in self.journals.moments}
        for seq in [k for k in self._moment_extra if k not in seqs]:
            del self._moment_extra[seq]
        for seq in [k for k in self._brief_all_found if k not in seqs]:
            del self._brief_all_found[seq]
        return out

    def brief_said_all_found(self, system, seq):
        """True when the latest arrival briefing for this system before moment `seq` was sent saying every body
        was found (so an FSS debrief right after the honk would only repeat it)."""
        for m in reversed(self.journals.moments):
            if m["seq"] < seq and m["kind"] == "arrival_brief" and m.get("system") == system:
                return bool(self._brief_all_found.get(m["seq"]))
        return False

    # the moments whose facts moments_summary adds (the page words them against your thresholds)
    MOMENT_EXTRA = ("fss_done", "fss_unfinished", "left_body", "bio_done", "approach", "arrival_brief", "game_exit", "loss",
                    "mapped")

    def moment_extra(self, m):
        """The facts a moment is spoken from, or None to leave it out (a body nobody scanned). Worked out once
        per moment and kept while your scans and the system's Spansh data stay the same: /api/nearby builds
        the moments on every poll, and leaving_summary and the bio rules are not cheap."""
        kind, sid = m["kind"], m.get("system")
        if kind == "fss_done" and m.get("by_honk") and self.brief_said_all_found(sid, m["seq"]):
            # the arrival briefing already said 'all found' (a jumponium body it carried is said alone)
            return {"kind": "jumponium", "system": str(sid)} if m.get("jumponium") else None
        key = (self.scan_version, sid in self.bases, (self.systems.get(sid) or {}).get("status"))
        hit = self._moment_extra.get(m["seq"])
        if hit and (hit[0] == key or kind in ("game_exit", "loss")):   # these two are worked out once
            return hit[1]
        where = self.locate(sid) if sid is not None else None
        extra = {"system": str(sid), "system_name": where[0]} if where else {"system": str(sid) if sid is not None else None}
        if kind == "fss_done":
            extra["leaving"] = self.leaving_summary(sid)
        elif kind in ("left_body", "bio_done"):
            bb = self.body_bio(sid, m["body_id"])
            if bb is None:
                extra = None
            else:
                extra.update(bb)
                if kind == "bio_done":
                    v = outrider.bio.species_value(m.get("species")) if outrider.bio else None
                    extra["value"] = v * bb["factor"] if v else None
        elif kind == "approach":
            extra.update(self.approach_facts(sid, m["body_id"], m.get("body_name")))
        elif kind == "mapped":
            facts = self.mapped_facts(sid, m["body_id"])
            if facts is None:
                extra = None
            else:
                extra.update(facts, leaving=self.leaving_summary(sid))
        elif kind == "arrival_brief":
            extra.update(self.arrival_facts(sid) or {})
            self._brief_all_found.setdefault(m["seq"], bool(extra.get("all_found")))   # what the page is told first
        elif kind == "loss":   # at poll time, not in the journal handler: the respawn's Location has set where you are
            extra = self.loss_facts(m["death_ts"])
        elif kind == "game_exit":
            login = m.get("login_ts")
            extra = {"session": None}
            if login and login <= m["ts"]:
                extra["session"] = dict(self.span_stats(login, m["ts"]), **self.range_counts(login, m["ts"] + "~"))
        self._moment_extra[m["seq"]] = (key, extra)
        return extra

    def mapped_facts(self, id64, body_id):
        """A planet just mapped, for the "mapped" call-out: its short name and what its data pays now it is mapped
        (with its first-discovery and first-mapped bonuses, as Here prices it; the efficiency bonus stays out, as
        in every estimate). None for a body nobody scanned or one that is not a planet."""
        row = self.db.execute("SELECT name, record FROM own_bodies WHERE system=? AND body_id=?", (id64, body_id)).fetchone()
        if not row:
            return None
        rec = json.loads(row["record"])
        if rec.get("type") != "Planet":
            return None
        where = self.locate(id64)
        f = self.db.execute("SELECT was_discovered, was_mapped FROM own_firsts WHERE system=? AND body_id=?",
                            (id64, body_id)).fetchone()
        value = None
        if rec.get("ed") and outrider.unsold:
            value = outrider.unsold.body_value(dict(rec["ed"], first_discovered=bool(f and f["was_discovered"] == 0),
                                              first_mapped=bool(f and f["was_mapped"] == 0)), True, False, True)
        return {"body": short_name(where[0], row["name"]) if where else row["name"], "value": value}

    def merged_records(self, id64):
        """A system's bodies as Here sees them: the Spansh records (live sphere or cache) overlaid with your own
        scans, signals and DSS genera, with its star class, bio context and body count. None when unknown."""
        where = self.locate(id64)
        if not where:
            return None
        name = where[0]
        source, base = self.bases.get(id64) or (None, None)
        if base is None:
            source, base = None, cached_base(self.db, id64)[1]
        own, hot, own_count = own_data(self.db, id64, name)
        for r_ in self.db.execute("SELECT b.name, g.genus_name FROM own_genera g JOIN own_bodies b "
                                  "ON b.system = g.system AND b.body_id = g.body_id WHERE g.system=?", (id64,)):
            rec = own.get(short_name(name, r_["name"]))
            if rec is not None:
                rec["genera"] = sorted(set(rec.get("genera") or []) | {r_["genus_name"]})
        records = merge_records((base or {}).get("records") or [], own, hot)
        star_row = self.db.execute("SELECT star_class FROM jumps WHERE id64=? AND star_class IS NOT NULL ORDER BY ts DESC LIMIT 1",
                                   (id64,)).fetchone() or \
            self.db.execute("SELECT star_class FROM star_classes WHERE id64=?", (id64,)).fetchone()
        star = star_row["star_class"] if star_row else None
        counts = [c for c in ((base or {}).get("body_count"), own_count) if c]
        count = max(counts) if counts else None
        return {"name": name, "records": records, "star": star, "body_count": count, "own_count": own_count,
                "base": base is not None, "base_known": base_known(base, source), "ctx": bio_context(name, records, where[1], where[2], where[3], star, count)}

    def body_bio(self, id64, body_id):
        """One body's exobiology, for the sampling lines: runs under way ({genus: samples}), the DSS's genera
        not started (each with what it could pay, bonus-free), signals no DSS has identified, and the x5
        first-footfall factor. None for a body you have not scanned."""
        mr = self.merged_records(id64)
        row = self.db.execute("SELECT name FROM own_bodies WHERE system=? AND body_id=?", (id64, body_id)).fetchone()
        if not mr or not row:
            return None
        short = short_name(mr["name"], row["name"])
        rec = next((r for r in mr["records"] if r["name"] == short), None)
        if rec is None:
            return None
        genera = {r[0] for r in self.db.execute("SELECT genus_name FROM own_genera WHERE system=? AND body_id=?", (id64, body_id))}
        done, partial = set(), {}
        for r in self.db.execute("SELECT genus_name, species, samples, done_ts FROM own_organic WHERE system=? AND body_id=?",
                                 (id64, body_id)):
            if r["done_ts"] and organic_state(self.db, r["done_ts"], (id64, body_id, r["species"])) != "lost":
                done.add(r["genus_name"])
            elif not r["done_ts"]:
                partial[r["genus_name"]] = r["samples"]
        left = sorted(genera - done - set(partial))
        _, groups = bio_guess(rec, mr["star"], left, mr["ctx"]) if left else (None, [])
        value = {g["genus"]: g.get("value") for g in groups}
        f = self.db.execute("SELECT 1 - bio_x5 AS was_footfalled FROM own_firsts WHERE system=? AND body_id=?", (id64, body_id)).fetchone()
        return {"body": short, "partial": partial, "untouched": [{"genus": g, "value": value.get(g)} for g in left],
                "unidentified": 0 if genera else max(0, (rec.get("bio") or 0) - len(done | set(partial))),
                "factor": 5 if f and f["was_footfalled"] == 0 else 1}

    def approach_facts(self, id64, body_id, body_name):
        """The body you are dropping into orbital cruise at: gravity, landable, and what its bio could be."""
        mr = self.merged_records(id64)
        short = short_name(mr["name"], body_name) if mr else body_name
        rec = next((r for r in (mr or {}).get("records") or [] if r.get("name") == short), None) or \
            next((r for r in (mr or {}).get("records") or [] if r.get("body_id") == body_id), None)
        out = {"body": short or "", "gravity": None, "landable": None, "signals": 0, "genera": None,
               "bio_value": None, "bio_options": None, "factor": 1}
        if not rec:
            return out
        sig, genera = rec.get("bio") or 0, rec.get("genera") or None
        # what you already did there (a return in a later session): finished species (not lost) are neither
        # listed nor priced, and anything sampled is no longer one of the options (as body_bio / system_detail)
        done, sampled = set(), set()
        bid = rec.get("body_id") if rec.get("body_id") is not None else body_id
        for r in self.db.execute("SELECT genus_name, species, done_ts FROM own_organic WHERE system=? AND body_id=?", (id64, bid)):
            if not r["done_ts"]:
                sampled.add(r["genus_name"])
            elif organic_state(self.db, r["done_ts"], (id64, bid, r["species"])) != "lost":
                done.add(r["genus_name"])
                sampled.add(r["genus_name"])
        left = [g for g in genera if g not in done] if genera else None
        sig_left = max(0, sig - len(done)) if sig else 0
        f = self.db.execute("SELECT 1 - bio_x5 AS was_footfalled FROM own_firsts WHERE system=? AND body_id=?", (id64, bid)).fetchone()
        out.update(body=rec["name"], gravity=rec.get("gravity"), landable=rec.get("landable"), signals=sig_left, genera=left,
                   factor=5 if f and f["was_footfalled"] == 0 else 1)
        if sig_left or left:
            groups = bio_left_groups(rec, mr["star"], genera, mr["ctx"], done)
            out["bio_value"] = sum((g.get("value") or 0) for g in groups) or None
            opts = None if genera else bio_options(rec, mr["star"], mr["ctx"], sampled)
            if opts:
                out["bio_options"] = {"low": opts["low"], "high": opts["high"], "genera": [g["genus"] for g in opts["genera"]]}
        return out

    def arrival_facts(self, id64):
        """The arrival briefing's facts: discovered or not, the body count, the star, the most valuable planet
        you have not mapped (Spansh's or your own) and the richest bio. The page words it and applies your
        thresholds. Only what is known now: with no Spansh data yet it is the verdict and the star alone."""
        mr = self.merged_records(id64)
        if not mr:
            return None
        scan = self.journals.arrival_scan
        sysrow = self.db.execute("SELECT body_count, all_found FROM own_systems WHERE id64=?", (id64,)).fetchone()
        row = self.systems.get(id64) or {}
        judge = pickup_judge(self.db, mr["name"])
        mapped = {short_name(mr["name"], r["name"]) for r in self.db.execute(
            "SELECT b.name, m.ts, m.first_ts FROM own_mapped m JOIN own_bodies b ON b.system = m.system AND b.body_id = m.body_id "
            "WHERE m.system=?", (id64,)) if judge(r["ts"], r["first_ts"])[0] != "lost"}
        # species you have finished (and not lost) on each body: the briefing prices only what is left
        got = {}
        for r in self.db.execute("SELECT b.name, o.body_id, o.species, o.genus_name, o.done_ts FROM own_organic o JOIN own_bodies b "
                                 "ON b.system = o.system AND b.body_id = o.body_id WHERE o.system=? AND o.done_ts IS NOT NULL",
                                 (id64,)):
            if organic_state(self.db, r["done_ts"], (id64, r["body_id"], r["species"])) != "lost":
                got.setdefault(short_name(mr["name"], r["name"]), set()).add(r["genus_name"])
        worth, bio = [], None
        for r in mr["records"]:
            if r.get("type") != "Planet":
                continue
            if r.get("bio") or r.get("genera"):   # mapped or not: mapping says nothing about the sampling
                groups = bio_left_groups(r, mr["star"], r.get("genera") or None, mr["ctx"], got.get(r["name"], set()))
                val = sum((g.get("value") or 0) for g in groups)
                if val and (not bio or val > bio["value"]):
                    bio = {"body": r["name"], "value": val}
            if r["name"] in mapped or r.get("was_mapped") is True:
                continue   # mapped by you, or (your scan says) by someone else: not pointed out (the author, 2026-10-09)
            value = outrider.unsold.body_value(dict(r["ed"], first_discovered=False, first_mapped=False), True, False, True) \
                if r.get("ed") and outrider.unsold else r.get("value")
            worth.append({"body": r["name"], "subtype": r.get("subtype"), "terraformable": bool(r.get("terraformable")),
                          "notable": NOTABLE_PLANETS.get(r.get("subtype")), "value": value})
        worth.sort(key=lambda w: -(w["value"] or 0))
        special = [w for w in worth if w["notable"] or w["terraformable"]]
        return {"undiscovered": (scan["was_discovered"] is False) if scan and scan["id64"] == id64 else None,
                "visits": self.visit_count(id64), "status": row.get("status"),
                "in_spansh": row["in_spansh"] if "in_spansh" in row else mr["base"],
                "body_count": (sysrow["body_count"] if sysrow else None) or mr["body_count"],
                "honked": bool(sysrow), "all_found": bool(sysrow and sysrow["all_found"]), "star_class": mr["star"],
                "base_known": mr["base_known"],
                "worth": special[:3] + [w for w in worth[:3] if w not in special[:3]], "bio": bio,
                "region": self.region_crossed(id64)}

    def region_crossed(self, id64):
        """The region this arrival crossed into ({region, spoken, count}), when it was the first crossing into it
        this session and you are still on that arrival; else None."""
        re_, pos = self.journals.region_entered, self.journals.pos
        if not re_ or re_["id64"] != id64 or not pos or pos["id64"] != id64 or pos.get("ts") != re_["ts"]:
            return None
        return {"region": re_["region"], "spoken": re_["spoken"], "count": re_["count"]}

    def visit_count(self, id64):
        row = self.db.execute("SELECT count FROM visits WHERE id64=?", (id64,)).fetchone()
        return row["count"] if row else 0

    def commander_summary(self):
        c = self.journals.commander
        if not c:
            return None
        cr = c.get("credits")
        rank, prog = c.get("rank") or {}, c.get("progress") or {}
        ranks = {k: {"rank": rank[k], "name": RANK_NAMES[k][rank[k]] if 0 <= rank[k] < len(RANK_NAMES[k]) else str(rank[k]),
                     "progress": prog.get(k)} for k in RANK_NAMES if isinstance(rank.get(k), int)}
        return {"name": c.get("name"), "credits": cr + (c.get("earned") or 0) if cr is not None else None,
                "credits_login": cr, "earned": c.get("earned") or 0, "login_ts": c.get("login_ts"),
                "loan": c.get("loan"), "mode": c.get("mode"), "ranks": ranks}

    def materials_summary(self):
        m = self.journals.materials
        if not m or not m.get("snapshot_ts"):
            return None
        return {"ts": m.get("ts"), "snapshot_ts": m["snapshot_ts"], "version": self.materials_version,
                "boosts": outrider.materials.boosts(m["counts"]), "count": sum(m["counts"].values()),
                "stale": materials_stale(m, self.journals.commander)}

    def shown_status(self):
        """Status.json as the panels show it. With --simulate (screenshots, demos) and the game not running: the last
        known values as if it were, in the ship's seat, with the fuel of the last reading, else of the last jump, else
        a full tank. Only the display reads this; auto honk, auto-target, the scoop and surface checks and every other
        guard read the real Status.json (and --simulate turns the virtual keyboard off besides)."""
        j = self.journals
        st = j.status_json or {}
        if not self.simulate or st.get("live"):
            return st
        fuel = st.get("fuel_main")
        if fuel is None:   # the last jump's FuelLevel: fuel_hist rows are [jump ly, fuel t, fuel left t, cargo t]
            fuel = next((h[2] for h in reversed(j.fuel_hist) if len(h) > 2 and h[2] is not None), None)
        if fuel is None:
            fuel = (j.ship or {}).get("fuel_main")
        return dict(st, live=True, simulated=True, fuel_main=fuel, away=None, vehicle_fuel=None,
                    flags=st.get("flags") or (1 << 24))   # InMainShip

    def fuel_now(self):
        """(model, fuel t, cargo t) for the fuel model right now, or None: no Loadout mass, no reading, or no cargo
        figure (Status.json's, else the journal's Cargo). The cargo counts, since a hold of 700 t cuts the range."""
        j = self.journals
        st = self.shown_status()
        model = fuel_model(j.ship, j.fuel_hist)
        cargo = st.get("cargo") if st.get("cargo") is not None else (j.cargo or {}).get("count")
        if not model or st.get("fuel_main") is None or cargo is None:
            return None
        return model, st["fuel_main"], cargo

    def range_now(self):
        """The longest jump with the fuel and cargo aboard (a tank under one max jump's fuel caps it)."""
        now = self.fuel_now()
        return round(fsd_range(now[0], now[0]["unladen"] + now[1] + now[2], now[1]), 2) if now else None

    def scoop_rate(self):
        """{scoopable, of, dry_run} over your last SCOOP_RATE_OF hyperspace arrivals with a known star (dry_run: the
        unscoopable ones in a row up to now), or None with fewer than SCOOP_RATE_MIN of them."""
        rows = [r["star_class"] for r in self.db.execute(
            "SELECT star_class FROM jumps WHERE kind='FSDJump' AND ride IS NULL AND star_class IS NOT NULL "
            "ORDER BY ts DESC LIMIT ?",
            (SCOOP_RATE_OF,))]
        if len(rows) < SCOOP_RATE_MIN:
            return None
        dry = next((k for k, c in enumerate(rows) if class_scoopable(c)), len(rows))
        return {"scoopable": sum(class_scoopable(c) for c in rows), "of": len(rows), "dry_run": dry}

    def here_scoop(self):
        """Where the arrival star cannot be scooped: the nearest other scoopable star here ({name, subtype, dist_ls},
        name None when none is known) and whether the system's star list is complete (every body found, or Spansh
        has them all), so "none here" can be said. None where the arrival star scoops or is unknown."""
        pos, hs = self.journals.pos, self.here_star()
        if not pos or not hs or class_scoopable(hs):
            return None
        id64 = pos["id64"]
        key = (id64, self.scan_version, id64 in self.bases, (self.systems.get(id64) or {}).get("status"))
        if getattr(self, "_here_scoop", (None,))[0] == key:
            return self._here_scoop[1]
        mr = self.merged_records(id64)
        out = None
        if mr:
            stars = sorted((r for r in mr["records"] if r.get("type") == "Star" and r.get("scoopable") and not r.get("main")
                            and r.get("dist_ls") is not None), key=lambda r: r["dist_ls"])
            own = self.db.execute("SELECT all_found FROM own_systems WHERE id64=?", (id64,)).fetchone()
            spansh = (self.bases.get(id64) or (None, cached_base(self.db, id64)[1]))[1] or {}
            complete = bool(own and own["all_found"]) or (spansh.get("body_count") is not None
                                                          and spansh["body_count"] <= len(mr["records"]))
            best = stars[0] if stars else {}
            out = {"name": best.get("name"), "subtype": best.get("subtype"),
                   "dist_ls": round(best["dist_ls"]) if best else None, "complete": complete}
        self._here_scoop = (key, out)
        return out

    def target_hop(self, t):
        """The targeted jump's cost: {ly, fuel, left (max-range jumps after it)} when its position is known, fuel and
        left None without the fuel model; reach False past the range (a jet-cone charge counts)."""
        pos = self.journals.pos
        if not t or not pos or pos.get("x") is None:
            return None
        row = self.systems.get(t["id64"])
        if row and row.get("distance") is not None:
            d = row["distance"]
        else:
            where = self.locate(t["id64"])
            if not where or where[1] is None:
                return None
            d = dist(pos, {"x": where[1], "y": where[2], "z": where[3]})
        out = {"ly": round(d, 2), "fuel": None, "left": None, "reach": None}
        now = self.fuel_now()
        if now:
            model, fuel, cargo = now
            mass = model["unladen"] + fuel + cargo
            eff = d / ((self.journals.boost or {}).get("value") or 1)   # a charge multiplies this jump's range
            out["reach"] = eff <= fsd_range(model, mass, fuel) + 0.01   # fuel under one max jump's shortens it
            need = hop_fuel(model, eff, mass)
            if need is not None:
                after = jumps_left(model, fuel - need, cargo) if need <= fuel else None
                out.update(fuel=round(need, 2), left=after[0] if after else 0)
        return out

    def fuel_summary(self):
        j = self.journals
        st, ship = self.shown_status(), j.ship or {}
        if not st:   # no reading yet
            return {"live": False}
        if st.get("fuel_main") is None:
            if not st.get("live"):
                return {"live": False}
            # the game is running but the first reading is on foot or in the SRV, which carry no ship fuel: say so,
            # with the vehicle's own tank (review F9)
            return {"live": True, "main": None, "ts": st.get("ts"), "in_ship": False,
                    "vehicle": {"label": (j.vehicle or {}).get("label") or st["away"], "fuel": st.get("vehicle_fuel")}
                    if st.get("away") else None}
        cap = ship.get("fuel_main")
        # Fuel per jump at your recent pace, and per max-range jump (fuel use ~ dist^2.x, so a
        # max jump costs far more than a short hop): both are shown.
        hist = j.fuel_hist[-FUEL_HISTORY:]
        per_jump = sum(h[1] for h in hist) / len(hist) if hist else None
        max_range = (j.jump_range or {}).get("ly")
        per_max = None
        if hist and max_range:
            # scale the biggest recent jump up to max range with the game's ~2.5 exponent
            d, f = max(hist, key=lambda h: h[0])[:2]
            per_max = f * (max_range / d) ** 2.5 if d else None
        jumps_recent = int(st["fuel_main"] / per_jump) if per_jump else None
        jumps_max = int(st["fuel_main"] / per_max) if per_max else None
        # the fuel model, where the Loadout gives the mass: the range with this fuel and cargo aboard, and jumps left
        # simulated jump by jump (at max range, and at your pace: hops as long, in fuel terms, as your recent ones)
        now, model_out = self.fuel_now(), None
        if now:
            model, fuel, cargo = now
            at_max = jumps_left(model, fuel, cargo)
            model_out = {"range_now": self.range_now(), "max_fuel": model["max_fuel"], "fitted": model["fitted"],
                         "power": model["power"], "cargo": cargo, "ly_max": at_max[1] if at_max else None,
                         "need": model["need"]}
            if at_max:
                jumps_max = at_max[0]
                dists = [h[0] for h in hist if h[0] > 0]
                if dists:
                    p = model["power"]
                    pace = (sum(x ** p for x in dists) / len(dists)) ** (1 / p)
                    jumps_recent = jumps_left(model, fuel, cargo, d=pace)[0]
        since_scoop = self.db.execute("SELECT count(*) FROM jumps WHERE kind='FSDJump' AND ride IS NULL AND ts > ?",
                                      (j.last_scoop or "",)).fetchone()[0]
        vehicle = {"label": (j.vehicle or {}).get("label") or st["away"], "fuel": st.get("vehicle_fuel")} if st.get("away") else None
        return {"main": st["fuel_main"], "reservoir": st.get("fuel_reservoir"), "capacity": cap, "vehicle": vehicle,
                "pct": round(100 * st["fuel_main"] / cap) if cap else None,
                "jumps_recent": jumps_recent, "jumps_max": jumps_max, "model": model_out,
                "since_scoop": since_scoop, "last_scoop": j.last_scoop, "ts": st.get("ts"),
                "scoop_rate": self.scoop_rate(), "here_scoop": self.here_scoop(),
                "live": bool(st.get("live")),
                "low_flag": bool((st.get("flags") or 0) & (1 << 19)),   # Status.json LowFuel: the game's own warning
                # in the ship's seat (Flags InMainShip): on foot or in the SRV the LowFuel bit says nothing
                "in_ship": bool((st.get("flags") or 0) & (1 << 24))}

    def carrier_summary(self):
        c = self.journals.carrier
        if not c or not c.get("id64"):
            return None
        if c.get("x") is None:
            where = self.locate(c["id64"])
            if where:
                c.update(x=where[1], y=where[2], z=where[3])
        pos = self.journals.pos
        d = dist(pos, c) if pos and c.get("x") is not None else None
        services = c.get("services") or []
        planned = dict(c["planned"]) if c.get("planned") else None
        if planned and planned.get("id64") and pos:   # how far the booked jump takes it from you
            where = self.locate(int(planned["id64"])) if str(planned["id64"]).isdigit() else None
            if where:
                planned["distance_from_you"] = round(dist(pos, {"x": where[1], "y": where[2], "z": where[3]}), 1)
                planned["jump_ly"] = round(dist(c, {"x": where[1], "y": where[2], "z": where[3]}), 1) if c.get("x") is not None else None
        docked = self.journals.docked
        return {"name": c.get("name"), "callsign": c.get("callsign"), "system": c.get("system"),
                "carrier_id": str(c["id"]) if c.get("id") is not None else None,   # which carrier (a new one: no "arrived")
                "aboard": bool(docked and c.get("id") and docked.get("market_id") == c.get("id")),
                "id64": str(c["id64"]), "distance": round(d, 1) if d is not None else None,
                "fuel": c.get("fuel"), "jump_range": c.get("jump_range"), "planned": planned,
                "has_uc": "exploration" in services, "has_vista": "vistagenomics" in services,
                "x": c.get("x"), "y": c.get("y"), "z": c.get("z"),
                "ts": c.get("ts"), "here": bool(pos and pos["id64"] == c["id64"]),
                # when it last arrived somewhere new (the page's arrival alert), and whether that is only
                # the booked jump's destination, not yet confirmed by the journal
                "moved_ts": c.get("moved_ts"), "assumed": bool(c.get("assumed")),
                # decommissioning: {ts, refund, scrap_ts, done (scrap time passed)}, shown in red
                "decommission": self.carrier_decommission(),
                # only while tritium is on a sell order at your carrier (confirmed): else the tile is as before
                "tritium": None if (self.carrier_decommission() or {}).get("done") else self.carrier_tritium()}

    def carrier_decommission(self):
        """Your carrier's decommissioning, if requested and not cancelled: {ts, refund, scrap_ts, done}."""
        d = (self.journals.carrier or {}).get("decommission")
        if not d:
            return None
        try:
            done = bool(d.get("scrap_ts")) and time.time() >= ts_seconds(d["scrap_ts"])
        except (TypeError, ValueError):
            done = False
        return dict(d, done=done)

    def carrier_cargo(self):
        """Your carrier's hold, folded from its history (outrider.cargo.carrier_fold): cached until a cargo change."""
        cid = (self.journals.carrier or {}).get("id")
        key = (cid, self.journals.cargo_version, self.counts_version)
        if self._carrier_fold[0] == key:
            return self._carrier_fold[1]
        events, markets, counts = [], [], []
        if cid is not None:
            events = [(r["ts"], json.loads(r["data"])) for r in
                      self.db.execute("SELECT ts, data FROM cargo_events WHERE market = ? ORDER BY ts", (cid,))]
            markets = [(r["ts"], json.loads(r["items"])) for r in
                       self.db.execute("SELECT ts, items FROM carrier_markets WHERE market_id = ?", (cid,))]
            counts = [(r["ts"], r["commodity"], r["count"], r["name"]) for r in
                      self.db.execute("SELECT * FROM carrier_counts WHERE carrier = ?", (cid,))]
        st = outrider.cargo.carrier_fold(cid, events, markets, counts)
        self._carrier_fold = (key, st)
        return st

    def commodity_name(self, i, extra=None):
        """A commodity's display name: the journal's, else Spansh's list (the lookup's names), else the id's."""
        names = dict(extra or {}, **self.journals.commodity_names)
        return outrider.cargo.display(i, names, (self.spansh_commodities or {}).get("norm"))

    def cargo_summary(self):
        """The Materials tab's Cargo: the ship's hold (exact, with what you paid) and your carrier's (tracked)."""
        j, sc = self.journals, self.journals.ship_cargo
        ship = j.ship or {}
        lines = [{"id": i, "name": self.commodity_name(i), "count": x["count"], "avg": round(x["avg"]) if x.get("avg") else None,
                  "priced": x["priced"], "lots": x["lots"], "avg_text": outrider.cargo.avg_text(x),
                  "stolen": x.get("stolen") or 0, "mission": x.get("mission") or 0}
                 for i, x in sc["lines"].items()]
        lines.sort(key=lambda x: (-x["count"], x["name"]))
        out = {"ship": {"name": ship.get("name"), "type": ship.get("type"), "lines": lines,
                        "count": sc["count"] if sc.get("count") is not None else sum(x["count"] for x in lines),
                        "capacity": ship.get("cargo_capacity"), "pad": outrider.cargo.SHIP_PAD.get((ship.get("type") or "").lower()),
                        "ts": sc.get("ts") or None},
               "carrier": None}
        c = j.carrier or {}
        if c.get("id") is None:
            return out
        st = self.carrier_cargo()
        lines = []
        for i, x in st["lines"].items():
            order = st["orders"].get(i) or {}
            lines.append({"id": i, "name": self.commodity_name(i, st["names"]), "count": x["count"], "state": x["state"],
                          "ts": x["ts"], "order": order.get("kind"),
                          "moves": [outrider.cargo.move_text(m) for m in x["moves"]]})
        lines.sort(key=lambda x: (-x["count"], x["name"]))
        total, reported = outrider.cargo.carrier_total(st), outrider.cargo.carrier_reported(st)
        out["carrier"] = {"name": c.get("name"), "callsign": c.get("callsign"), "lines": lines, "total": total,
                          "reported": reported, "reported_ts": (st["stats"] or {}).get("ts"),
                          "gap": reported - total if reported is not None else None, "market_ts": st["market_ts"],
                          "decommission": self.carrier_decommission(),
                          "aboard": bool((j.docked or {}).get("market_id") == c.get("id") and c.get("id") is not None)}
        return out

    async def commodity_list(self):
        """Spansh's commodity names by their letters ({norm: name}), fetched once a week; the last copy if Spansh
        cannot be reached (None without one)."""
        sc = self.spansh_commodities or {}
        if sc.get("norm") and time.time() - (sc.get("ts") or 0) < COMMODITIES_MAX_AGE_S:
            return sc["norm"]
        try:
            names = await self.spansh.commodity_names()
        except (ClientError, asyncio.TimeoutError, ValueError) as e:
            print(f"Spansh's commodity names could not be read: {e}", file=sys.stderr)
            return sc.get("norm")
        self.spansh_commodities = {"ts": time.time(), "norm": {outrider.cargo.norm(n): n for n in names}}
        meta_set(self.db, "spansh_commodities", self.spansh_commodities)
        self.db.commit()
        return self.spansh_commodities["norm"]

    async def cargo_lookup(self, q):
        """GET /api/cargo/lookup: where to sell (or buy) tons of a commodity, from Spansh's station search (read only).

        q: commodity (a journal id or a name), mode sell | buy, tons, from ship | carrier | here (where the distances
        are measured from, and whose hold the profit and "also buys" read), sort price | near, within (ly), age (days),
        carriers (1: fleet carriers too), pad auto | L | M | any. Returns ({...rows}, 200) or ({error}, status)."""
        mode, src = q.get("mode"), q.get("from") or "here"
        if mode not in ("sell", "buy") or src not in ("ship", "carrier", "here"):
            return {"error": "expected mode sell or buy, from ship, carrier or here"}, 400
        text = str(q.get("commodity") or "").strip()[:80]
        try:
            tons = int(q.get("tons") or 1)
            within = int(q.get("within") or 500)
            age = int(q.get("age") or 14)
        except ValueError:
            return {"error": "tons, within and age are whole numbers"}, 400
        if not text or not 1 <= tons <= 100000 or within not in outrider.cargo.LOOKUP_WITHIN or not 1 <= age <= 365:
            return {"error": f"a commodity, 1 to 100,000 t, within one of {outrider.cargo.LOOKUP_WITHIN} ly, 1 to 365 days"}, 400
        names = await self.commodity_list()
        if not names:
            return {"error": "Spansh's commodity list cannot be read just now: try again later"}, 502
        i = outrider.cargo.cid(text)
        name = names.get(outrider.cargo.norm(self.commodity_name(i))) or names.get(outrider.cargo.norm(text))
        if not name:
            return {"error": f"Spansh has no market data for {text!r}"}, 404
        c = self.carrier_summary() or {}
        if src == "carrier":
            ref, where = (c if c.get("x") is not None else None), c.get("system")
        else:
            ref, where = self.journals.pos, (self.journals.pos or {}).get("name")
        if not ref or ref.get("x") is None:
            return {"error": "your carrier's position is not known yet" if src == "carrier" else "your position is not known yet"}, 409
        cg = self.cargo_summary()
        ship = cg["ship"]
        pad = q.get("pad") or "auto"
        if pad == "auto":
            pad = ship.get("pad")
        elif pad not in (outrider.cargo.LARGE, outrider.cargo.MEDIUM):
            pad = None
        body = outrider.cargo.market_query(name, mode, tons, ref, within=within, age_days=age, pad=pad,
                                           carriers=q.get("carriers") in ("1", "true"),
                                           sort="near" if q.get("sort") == "near" else "price")
        try:
            d = await self.spansh.market_search(body)
        except (ClientError, asyncio.TimeoutError, ValueError) as e:
            return {"error": f"Spansh's station search failed: {e}"}, 502
        lines = (cg["carrier"] or {}).get("lines", []) if src == "carrier" else ship["lines"]
        holding = [(names.get(outrider.cargo.norm(x["name"])) or x["name"], x["count"]) for x in lines]
        own = next((x for x in ship["lines"] if x["id"] == i), None) if src == "ship" else None
        avg = own["avg"] if own and own.get("avg") else None
        rows = outrider.cargo.market_rows(d.get("results"), name, mode, tons, holding=holding, avg=avg,
                                          laden=self.range_now() or (self.journals.ship or {}).get("max_range"))
        return {"commodity": name, "mode": mode, "tons": tons, "from": src, "where": where, "avg": avg,
                "sort": "near" if q.get("sort") == "near" else "price", "within": within, "age": age,
                "carriers": q.get("carriers") in ("1", "true"), "pad": pad, "pad_known": bool(ship.get("pad")),
                "count": d.get("count"), "rows": rows}, 200

    async def dssa_list(self, fetch=True):
        """The DSSA carrier list as outrider.dock rows, with {checked, modified, error}: asked for again (conditionally)
        only when `fetch` and the copy is over an hour old; the last copy is kept (meta dssa, live-only)."""
        d = meta_get(self.db, "dssa") or {}
        err = None
        if fetch and time.time() - (d.get("checked") or 0) > outrider.dock.DSSA_MAX_AGE_S:
            try:
                status, data, etag, modified = await self.spansh.get_if_changed(DSSA_URL, d.get("etag"), d.get("modified"))
                if status == 200 and not isinstance(data, list):
                    # an answer of another shape (an error object, a maintenance notice): a failed check, so the old
                    # copy is kept and asked for again next time (review 2026-10-08 #14: it counted as a fresh check)
                    raise ValueError("it answered in an unexpected shape")
                d = dict(d, checked=time.time(), error=None)
                if status == 200:
                    d.update(data=data, etag=etag, modified=modified)
                meta_set(self.db, "dssa", d)
                self.db.commit()
            except (ClientError, asyncio.TimeoutError, ValueError) as e:
                err = f"the DSSA list could not be read ({e})"
        return outrider.dock.dssa_rows(d.get("data")), {"checked": d.get("checked"), "modified": d.get("modified"),
                                                        "count": len(d.get("data") or []), "error": err}

    async def nearest_dock(self, q):
        """GET /api/nearest: the nearest places to dock (outrider/dock.py). q: stations, carriers ("0"/"1"), need
        (uc,vista,repair,refuel,shipyard,outfitting), age (days), permit ("1": keep permit systems), pad (auto, L, M,
        any), cached ("1": no new fetch of the DSSA list; the AI's tools and the voice ask that way). Read only but for
        the DSSA copy kept."""
        pos = self.journals.pos
        if not pos or pos.get("x") is None:
            return {"error": "your position is not known yet"}, 409
        names = {s.lower(): s for s in outrider.dock.SERVICES}
        need = [names[n] for n in str(q.get("need") or "").lower().replace(" ", "").split(",") if n in names]
        try:
            age = int(q.get("age") or outrider.dock.DEFAULT_AGE_DAYS)
        except ValueError:
            return {"error": "age is a whole number of days"}, 400
        if not 1 <= age <= 3650:
            return {"error": "age: 1 to 3,650 days"}, 400
        ship = self.journals.ship or {}
        pad = q.get("pad") or "auto"
        pad = outrider.cargo.SHIP_PAD.get((ship.get("type") or "").lower()) if pad == "auto" else pad if pad in ("L", "M") else None
        errors = []
        # the same place and services asked again within DOCK_CACHE_S (each tick of the finder's other filters) is
        # answered from the last search instead of two more requests (review 2026-10-08 #13)
        key = (pos.get("id64"), pos.get("x"), pos.get("y"), pos.get("z"), tuple(sorted(need)))
        hit = self.dock_cache.get("search")
        try:
            if hit and hit[0] == key and time.time() - hit[1] < DOCK_CACHE_S:
                found = hit[2]
            else:
                found = await self.spansh.dock_search(pos, need)
                self.dock_cache["search"] = (key, time.time(), found)
            spansh = outrider.dock.spansh_rows(found)
        except (ClientError, asyncio.TimeoutError, ValueError) as e:
            spansh = []
            errors.append(f"Spansh could not be reached ({e})")
        dssa, dinfo = await self.dssa_list(fetch=q.get("cached") != "1")
        if dinfo["error"]:
            errors.append(dinfo["error"])
        c = self.carrier_summary() or {}
        own = outrider.dock.own_row(dict(self.journals.carrier or {}, **{k: c.get(k) for k in ("x", "y", "z", "has_uc", "has_vista")},
                                         decommission=self.carrier_decommission()))
        rows = outrider.dock.merge(spansh, dssa, own)
        permits = set()
        if q.get("permit") != "1":
            ids = sorted({r["id64"] for r in rows if r.get("id64") is not None})
            hit = self.dock_cache.get("permits")
            try:
                if hit and hit[0] == ids and time.time() - hit[1] < DOCK_CACHE_S:
                    permits = hit[2]
                else:
                    permits = await self.spansh.permit_ids(ids)
                    self.dock_cache["permits"] = (ids, time.time(), permits)
            except (ClientError, asyncio.TimeoutError, ValueError) as e:
                errors.append(f"permit systems could not be checked ({e})")
        laden = self.range_now() or ship.get("max_range")
        out = outrider.dock.nearest(rows, pos, need=need, stations=q.get("stations") != "0", carriers=q.get("carriers") != "0",
                                    pad=pad, age_days=age, permit=q.get("permit") == "1", permits=permits, laden=laden)
        for r in out["rows"]:
            r.update(id64=str(r["id64"]) if r.get("id64") is not None else None, seen=None)
        return dict(out, need=need, age=age, pad=pad, pad_known=bool(outrider.cargo.SHIP_PAD.get((ship.get("type") or "").lower())),
                    ship=ship.get("type"), laden=round(laden, 1) if laden else None, where=pos.get("name"), dssa=dinfo,
                    errors=errors), 200

    def carrier_tritium(self):
        """The Carrier tile's tritium, only while tritium is on a sell order at your carrier (a confirmed line): the
        depot, the depot plus the hold, and how many 500 ly jumps that gives (outrider.cargo.carrier_jumps)."""
        c = self.journals.carrier or {}
        if c.get("id") is None:
            return None
        st = self.carrier_cargo()
        line, stats = st["lines"].get("tritium"), st["stats"] or {}
        if not line or line["state"] != "confirmed" or not isinstance(c.get("fuel"), int):
            return None
        used = stats["used"] + st["after_stats"] if isinstance(stats.get("used"), int) else None
        return {"depot": c["fuel"], "total": c["fuel"] + line["count"],
                "jumps": outrider.cargo.carrier_jumps(c["fuel"], line["count"], used)}

    def cargo_recount(self, counts):
        """POST /api/cargo/recount {counts: {commodity: tons}}: your counts for carrier lines Outrider cannot confirm.
        A name not seen yet ("Add a commodity") is matched to a known one, letters only. Confirmed lines (a sell order
        at your carrier) are left as the market says."""
        cid = (self.journals.carrier or {}).get("id")
        if cid is None:
            return {"error": "no carrier in your journals"}, 409
        if not isinstance(counts, dict) or not counts or len(counts) > 300:
            return {"error": "expected {counts: {commodity: tons}}"}, 400
        st = self.carrier_cargo()
        known = {outrider.cargo.norm(i): i for i in set(st["lines"]) | set(self.journals.commodity_names) | set(st["names"])}
        known.update({outrider.cargo.norm(n): i for i, n in {**st["names"], **self.journals.commodity_names}.items()})
        rows, skipped = [], []
        for key, n in counts.items():
            if not isinstance(key, str) or not key.strip() or len(key) > 80 or isinstance(n, bool) \
                    or not isinstance(n, int) or not 0 <= n <= 100000:
                return {"error": f"bad count for {str(key)[:80]!r}: whole tons, 0 to 100,000"}, 400
            i = known.get(outrider.cargo.norm(key)) or outrider.cargo.norm(key)
            if not i:
                return {"error": f"not a commodity name: {key[:80]!r}"}, 400
            if (st["lines"].get(i) or {}).get("state") == "confirmed":
                skipped.append(i)
                continue
            rows.append((i, n, None if i in st["lines"] or i in self.journals.commodity_names else key.strip()))
        ts = iso_ts(time.time())
        self.db.executemany("INSERT OR REPLACE INTO carrier_counts VALUES (?, ?, ?, ?, ?)",
                            [(ts, cid, i, n, name) for i, n, name in rows])
        self.db.commit()
        self.counts_version += 1
        self.bump()
        return {"ok": True, "saved": len(rows), "skipped": skipped, "cargo": self.cargo_summary()}, 200

    def docked_summary(self):
        """Where you are docked, if anywhere, and whether it buys exploration data."""
        d, st = self.journals.docked, self.journals.status_json or {}
        flags = st.get("flags") or 0
        # On foot the ship's Docked flag is clear, but walking to the Vista Genomics counter is still being
        # docked: Flags2 OnFootInStation, OnFootInHangar and OnFootSocialSpace say you are inside.
        here = bool(flags & 1) or bool((st.get("flags2") or 0) & ON_FOOT_DOCKED)
        if not d or (st.get("live") and not here):
            return None
        return dict(d, docked_now=here if st.get("live") else None)

    JUMPONIUM = ("carbon", "vanadium", "germanium", "cadmium", "niobium", "arsenic", "yttrium", "polonium")

    def material_sources(self, radius=300.0, per=3):
        """For each FSD-injection material, the nearest landable bodies you have scanned that carry it (your
        Scan events list surface materials), richest first among the near ones. Unscanned bodies are unknown.
        The body list is built once and then only takes own_bodies rows stored since (a Scan's INSERT OR REPLACE
        gives the row a new rowid), not every body again on each scan_version bump: the full build parses every
        landable body's raw Scan (~0.15 s on a big database) on the event loop, and the Materials tab refetches after
        every jump and scan. A table emptied or rolled back below the last rowid seen (a journal re-read) is built
        again."""
        pos = self.journals.pos
        if not pos:
            return {}
        top = self.db.execute("SELECT max(rowid) FROM own_bodies").fetchone()[0] or 0
        since = getattr(self, "_mat_rowid", None)
        if since is None or top < since:
            self._mat_bodies, since = {}, 0
        if top > since:
            where = {}
            # the first build reads only the rows listing materials; after it every new row, since a rescan that
            # lost them must drop the body
            for r in self.db.execute("SELECT system, body_id, name, raw FROM own_bodies "
                                     "WHERE rowid > ? AND (? OR raw LIKE '%\"Materials\"%')", (since, since > 0)):
                ev = json.loads(r["raw"])
                mats = {m.get("Name", "").lower(): m.get("Percent") for m in ev.get("Materials") or []}
                if not (ev.get("Landable") and mats):
                    self._mat_bodies.pop((r["system"], r["body_id"]), None)
                    continue
                if r["system"] not in where:
                    where[r["system"]] = self.db.execute("SELECT name, x, y, z FROM visits WHERE id64=?",
                                                         (r["system"],)).fetchone()
                v = where[r["system"]]
                if v:
                    self._mat_bodies[(r["system"], r["body_id"])] = {
                        "system": v["name"], "id": str(r["system"]), "body": short_name(v["name"], r["name"]),
                        "x": v["x"], "y": v["y"], "z": v["z"], "mats": {k: val for k, val in mats.items() if k in self.JUMPONIUM}}
        self._mat_rowid = top
        out = {}
        near = [(dist(pos, b), b) for b in self._mat_bodies.values()]
        near = [(d, b) for d, b in near if d <= radius]
        near.sort(key=lambda t: t[0])
        for m in self.JUMPONIUM:
            hits = [(d, b) for d, b in near if b["mats"].get(m)]
            out[m] = [{"system": b["system"], "id": b["id"], "body": b["body"], "distance": round(d, 1), "pct": round(b["mats"][m], 1)}
                      for d, b in hits[:per]]
        return out

    def left_behind(self, radius=100.0):
        """Visited systems within `radius` ly with work still to do: bodies not found after a honk, genera the
        DSS found but you never sampled, bio signals the FSS found on a body you never DSS'd (priced as
        leaving_summary prices them: genera None, an upper bound), unmapped planets with what mapping would add
        (bonus-free). Batched queries over all candidates at once; the page applies your thresholds."""
        pos = self.journals.pos
        if not pos:
            return {"radius": radius, "systems": []}
        key = (self.scan_version, pos["id64"], radius)
        if getattr(self, "_left_key", None) == key:
            return self._left
        box = (pos["x"] - radius, pos["x"] + radius, pos["y"] - radius, pos["y"] + radius, pos["z"] - radius, pos["z"] + radius)
        cands = {r["id64"]: dict(r) for r in self.db.execute(
            "SELECT id64, name, x, y, z FROM visits WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND z BETWEEN ? AND ?", box)
            if r["id64"] != pos["id64"] and dist(pos, r) <= radius}
        if not cands:
            self._left, self._left_key = {"radius": radius, "systems": []}, key
            return self._left
        ids = list(cands)
        marks = ",".join("?" * len(ids))
        q = lambda sql: self.db.execute(sql.format(marks=marks), ids)
        honk = {r["id64"]: r for r in q("SELECT id64, body_count, all_found FROM own_systems WHERE id64 IN ({marks})")}
        bodies = {}
        for r in q("SELECT system, body_id, name, ts, record FROM own_bodies WHERE system IN ({marks})"):
            bodies.setdefault(r["system"], {})[r["body_id"]] = r
        genera = {}
        for r in q("SELECT system, body_id, genus_name FROM own_genera WHERE system IN ({marks})"):
            genera.setdefault((r["system"], r["body_id"]), set()).add(r["genus_name"])
        done = {}
        for r in q("SELECT system, body_id, species, genus_name, done_ts FROM own_organic WHERE system IN ({marks}) AND done_ts IS NOT NULL"):
            if organic_state(self.db, r["done_ts"], (r["system"], r["body_id"], r["species"])) != "lost":
                done.setdefault((r["system"], r["body_id"]), set()).add(r["genus_name"])
        mapped = {(r["system"], r["body_id"]): (r["ts"], r["first_ts"])
                  for r in q("SELECT system, body_id, ts, first_ts FROM own_mapped WHERE system IN ({marks})")}
        # FSS bio signals (by body name, as own_signals keys them) and each system's latest star, for the bodies
        # nobody DSS'd: the leaving alert counts those, so the list does too
        signals = {(r["system"], r["name"]): r["bio"]
                   for r in q("SELECT system, name, bio FROM own_signals WHERE system IN ({marks}) AND bio > 0")}
        stars = {r["id64"]: r["star_class"] for r in q("SELECT id64, star_class FROM jumps WHERE id64 IN ({marks}) ORDER BY ts")}
        # Spansh's cached records of the bodies you never scanned: a pre-Odyssey one may hide life (stale_bio_groups)
        spansh = {r["id64"]: r["summary"] for r in q("SELECT id64, summary FROM spansh_systems WHERE id64 IN ({marks})")}
        out = []
        for id64, c in cands.items():
            bs = bodies.get(id64, {})
            h = honk.get(id64)
            recs = {bid: json.loads(r["record"]) for bid, r in bs.items()}
            ctx = None
            old_data = None
            if id64 in spansh:
                base = json.loads(spansh[id64])
                mine = {short_name(c["name"], r["name"]) for r in recs.values()}
                stale = [r for r in base.get("records") or [] if base.get("v") == CACHE_VERSION
                         and r.get("name") not in mine and stale_bio_candidate(r)]
                if stale:
                    ctx = bio_context(c["name"], base.get("records") or [], c["x"], c["y"], c["z"], stars.get(id64),
                                      base.get("body_count") or (h and h["body_count"]))
                    old_data = stale_bio_summary(stale, stars.get(id64), ctx)
                    ctx = None   # the bio below builds its own, from your scans
            unfound = (h["body_count"] - len(bs)) if h and h["body_count"] and not h["all_found"] else 0
            bio, maps = [], []
            for (sid, bid), gs in genera.items():
                if sid != id64:
                    continue
                left = sorted(gs - done.get((sid, bid), set()))
                if left and bid in bs:
                    bio.append({"body": short_name(c["name"], bs[bid]["name"]), "genera": left,
                                "value": sum((outrider.bio.genus_value(g) or 0) if outrider.bio else 0 for g in left)})
            for bid, rec in recs.items():
                n_sig = signals.get((id64, rec.get("name")), 0)
                if not n_sig or (id64, bid) in genera:   # a DSS'd body is listed above (its genera win)
                    continue
                done_set = done.get((id64, bid), set())
                n_left = n_sig - len(done_set)
                if n_left <= 0:
                    continue
                if ctx is None:   # only for a system with such a body: the common case stays free
                    ctx = bio_context(c["name"], list(recs.values()), c["x"], c["y"], c["z"], stars.get(id64),
                                      h and h["body_count"])
                groups = bio_left_groups(dict(rec, bio=n_sig), stars.get(id64), None, ctx, done_set)
                bio.append({"body": short_name(c["name"], bs[bid]["name"]), "genera": None, "signals": n_left,
                            "value": sum((g.get("value") or 0) for g in groups)})
            judge = None
            for bid, r in bs.items():
                rec = recs[bid]
                if rec.get("type") != "Planet" or not rec.get("ed") or not outrider.unsold:
                    continue
                m = mapped.get((id64, bid))
                if m:
                    judge = judge or pickup_judge(self.db, c["name"])
                    if judge(*m)[0] != "lost":
                        continue
                plain = dict(rec["ed"], first_discovered=False, first_mapped=False)
                inc = outrider.unsold.body_value(plain, True, False, True) - outrider.unsold.body_value(plain, False, False, True)
                maps.append({"body": short_name(c["name"], r["name"]), "subtype": rec.get("subtype"),
                             "terraformable": bool(rec.get("terraformable")), "increment": inc})
            if unfound or bio or maps or old_data:
                maps.sort(key=lambda m: -m["increment"])
                out.append({"id": str(id64), "name": c["name"], "distance": round(dist(pos, c), 1),
                            "unfound": unfound, "bio": bio, "maps": maps[:6], "maps_total": len(maps),
                            "old_data": old_data})
        out.sort(key=lambda r: r["distance"])
        self._left, self._left_key = {"radius": radius, "systems": out}, key
        return self._left

    def firsts_list(self):
        """Every visited system holding first-discovery data, with its sale state and value (and, for unsold ones,
        `seen`: what the firsts watch found of someone else's scans there, or None). `recover` (firsts_recovery) is
        the rescan checklist for data lost with a ship."""
        pos = self.journals.pos
        watch = self.firsts_watch_rows()
        out = []
        for r in self.db.execute(
                "SELECT DISTINCT f.system AS id64, v.name, v.x, v.y, v.z FROM own_firsts f "
                "JOIN visits v ON v.id64 = f.system"):
            f = own_firsts(self.db, r["id64"], r["name"])
            if not f or f["sale"] == "sold":
                continue
            rec = f["recover"]
            # state: unsold, lost (data still to rescan, whatever else is aboard) or rescanned (every lost body and
            # map scanned again, not yet sold); sale: own_firsts' headline (unsold whenever any of it is aboard),
            # which the firsts watch and the unsold count go by
            done = rec and rec["rescanned"] == rec["lost_bodies"] and rec["maps_redone"] == rec["maps_lost"]
            out.append({"id": str(r["id64"]), "name": r["name"],
                        "state": "rescanned" if done else "lost" if rec else f["sale"], "sale": f["sale"],
                        "recover": rec, "system": f["system"],
                        "system_state": f["system_state"], "bodies_by": f["bodies_by"], "mapped_by": f["mapped_by"],
                        "distance": round(dist(pos, r), 2) if pos else None,
                        "value": self.system_values.get(r["name"]),
                        "seen": firsts_seen(watch.get(r["id64"])) if f["sale"] == "unsold" else None})
        out.sort(key=lambda x: (-(x["value"] or 0), x["distance"] or 0))
        return out

    # ---- the firsts watch: has someone else scanned your unsold first discoveries since? ----

    def firsts_watch_rows(self):
        return {r["id64"]: dict(r) for r in self.db.execute("SELECT * FROM firsts_watch")}

    def firsts_cached(self):
        """firsts_list(), kept until the unsold estimate (recomputed after every scan, sale or loss that changes it)
        or the watch's table changes: the watch and the payload ask often, and each list is ~0.1 s on a big database."""
        key = ((self.unsold or {}).get("computed"), self.unsold_at, self.firsts_watch_seq)
        if self._firsts_cache is None or self._firsts_cache[0] != key:
            self._firsts_cache = (key, self.firsts_list())
        return self._firsts_cache[1]

    def firsts_watch_info(self):
        """For the Unsold tile: {on, seen, checked, of}, systems with unsold firsts someone else has scanned since
        (seen), checked at least once (checked), in all (of: the ones the watch looks at, see firsts_watched).
        None with the watch off and nothing ever found."""
        unsold = [x for x in self.firsts_cached() if firsts_watched(x)]
        seen = sum(1 for x in unsold if x["seen"])
        if not self.firsts_watch_on and not seen:
            return None
        rows = self.firsts_watch_rows() if unsold else {}
        checked = sum(1 for x in unsold if int(x["id"]) in rows)
        return {"on": self.firsts_watch_on, "seen": seen, "checked": checked, "of": len(unsold)}

    def firsts_watch_due(self, now):
        """(id64, name) of the next system to check among those not checked within firsts_watch_gap: one never
        checked first, most valuable first, then the one checked longest ago (value breaking a tie), so with more
        systems due than FIRSTS_WATCH_DAY_CAP a day the same top ones don't take every slot back as they come due
        again. A system whose check failed is skipped for FIRSTS_WATCH_EVERY (its failure counts as a check), so one
        broken dump does not hold up the rest. None when none is due, or FIRSTS_WATCH_DAY_CAP checks were made in the
        last 24 h."""
        rows = self.firsts_watch_rows()
        failed = {i: t for i, t in self.firsts_watch_failed.items() if now - t < FIRSTS_WATCH_EVERY}
        self.firsts_watch_failed = failed
        made = sum(1 for r in rows.values() if r["checked_ts"] and now - r["checked_ts"] < 86400) + len(failed)
        if made >= FIRSTS_WATCH_DAY_CAP:
            return None
        due = []
        for x in self.firsts_cached():   # most valuable first
            id64 = int(x["id"])
            r = rows.get(id64)
            if firsts_watched(x) and id64 not in failed and (
                    r is None or r["checked_ts"] is None or now - r["checked_ts"] >= firsts_watch_gap(r, now)):
                due.append(((r["checked_ts"] or 0) if r else -1, len(due), id64, x["name"]))
        if not due:
            return None
        return min(due)[2:]

    def firsts_mine(self, id64, name):
        """({short name: [your journal times for it]}, your first scan there, [your other times there]) for the bodies
        you discovered in a system: every scan, the map, the signals and the rings' maps, since any of them sent
        through EDDN updates the body on Spansh at that time; and the system-wide ones (arrivals, footfall, samples,
        codex entries: a jump in updates the arrival star, which need not be the body you scanned first; and every
        login, whose Location names the body you are at without a system in the table)."""
        mine, first = {}, None
        for r in self.db.execute(
                """SELECT f.name, f.first_ts, f.undisc_ts, b.ts AS scan_ts, m.ts AS map_ts, s.ts AS sig_ts FROM own_firsts f
                   LEFT JOIN own_bodies b ON b.system = f.system AND b.body_id = f.body_id
                   LEFT JOIN own_mapped m ON m.system = f.system AND m.body_id = f.body_id
                   LEFT JOIN own_signals s ON s.system = f.system AND s.name = f.name
                   WHERE f.system = ? AND f.was_discovered = 0""", (id64,)):
            mine[short_name(name, r["name"])] = [t for t in (r["first_ts"], r["undisc_ts"], r["scan_ts"], r["map_ts"], r["sig_ts"]) if t]
            if r["first_ts"] and (first is None or r["first_ts"] < first):
                first = r["first_ts"]
        for r in self.db.execute("SELECT name, ts FROM own_ring_signals WHERE system=?", (id64,)):
            body = split_ring_name(name, r["name"])[0]
            if body in mine and r["ts"]:
                mine[body].append(r["ts"])
        times = [r[0] for r in self.db.execute(
            "SELECT ts FROM jumps WHERE id64 = ? UNION SELECT ts FROM own_footfall WHERE system = ? "
            "UNION SELECT ts FROM own_organic WHERE system = ? UNION SELECT ts FROM codex WHERE system = ? "
            "UNION SELECT ts FROM logins", (id64, id64, id64, id64)) if r[0]]
        return mine, first, times

    async def firsts_watch_step(self, now=None):
        """Check the next system due (firsts_watch_due) against Spansh and record it in firsts_watch: at most one
        dump request, none when the cached record was fetched within FIRSTS_WATCH_EVERY. Returns what
        firsts_reported found (None: nothing, or nothing was due)."""
        now = time.time() if now is None else now
        due = self.firsts_watch_due(now)
        if not due:
            return None
        try:
            return await self.firsts_watch_check(*due, now)
        except Exception:
            self.firsts_watch_failed[due[0]] = now   # the next check moves on to the next system due
            raise

    async def firsts_watch_check(self, id64, name, now):
        """firsts_watch_step's check of one system."""
        mine, first, times = self.firsts_mine(id64, name)
        updated_at, base = self.spansh.cached(id64)
        age = self.spansh.fetched_age(id64) if base else None
        if base and age is not None and age < FIRSTS_WATCH_EVERY and (
                base.get("no_dump") or any(r.get("full") for r in base.get("records") or [])):
            records, count = base.get("records") or [], base.get("body_count")   # fresh enough: no request
        elif base:   # cached for Nearby: refresh it the usual way, so Nearby gets the new bodies too
            base = await self.spansh.full_records(id64, updated_at, base)
            records, count = base.get("records") or [], base.get("body_count")
        else:        # never cached: the dump alone (a system Spansh does not know is not stored as one it does)
            system = ((await self.spansh.lookup(id64, interactive=False)) or {}).get("system") or {}
            records = [record_from_dump(name, b) for b in system.get("bodies") or [] if b.get("type") in ("Star", "Planet")]
            count = system.get("bodyCount")
        own = self.db.execute("SELECT body_count FROM own_systems WHERE id64=?", (id64,)).fetchone()
        got = firsts_reported(records, mine, (own["body_count"] if own else None) or count, times)
        old = self.db.execute("SELECT * FROM firsts_watch WHERE id64=?", (id64,)).fetchone()
        old_seen = old["reported_ts"] if old else None
        if got:   # the first sighting stays the first
            row = (min(t for t in (old_seen, got["reported_ts"]) if t), got["bodies"], got["spansh_bodies"], got["body_count"])
        elif old_seen:   # seen before, and a report does not go away
            row = (old_seen, old["bodies"], old["spansh_bodies"], old["body_count"])
        else:
            row = (None, 0, sum(1 for r in records if r.get("type") in ("Star", "Planet")), (own["body_count"] if own else None) or count)
        self.db.execute("INSERT OR REPLACE INTO firsts_watch VALUES (?, ?, ?, ?, ?, ?, ?)", (id64, now) + row + (first,))
        self.db.commit()
        self.firsts_watch_seq += 1
        if row[0] != old_seen:
            self.bump()   # the Unsold tile's count
        return got

    async def watch_updates(self):
        """[server] update_check: GitHub's latest release, at start and once a day; a newer one goes in the payload
        (the page's Update pill). Only the request is made: nothing about the player is sent."""
        await asyncio.sleep(UPDATE_CHECK_START)
        said = None
        while True:
            try:
                async with self.spansh.session.get(RELEASES_LATEST, headers={"Accept": "application/vnd.github+json"},
                                                   timeout=ClientTimeout(total=30)) as r:
                    r.raise_for_status()
                    found = newer_release(await r.json(content_type=None), outrider.__version__)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 -- offline, GitHub down or throttled: try again later, quietly
                print(f"update check: could not ask GitHub ({type(e).__name__}); trying again in an hour", file=sys.stderr)
                await asyncio.sleep(UPDATE_CHECK_RETRY)
                continue
            if found != self.update_available:
                self.update_available = found
                self.bump()
            if found and found["version"] != said:
                said = found["version"]
                print(f"update available: Outrider {found['version']} (this is {outrider.__version__}): {found['url']}")
            await asyncio.sleep(UPDATE_CHECK_EVERY)

    async def watch_firsts(self):
        """The firsts watch's loop (only with [spansh] watch_firsts on): one check every FIRSTS_WATCH_GAP."""
        await asyncio.sleep(FIRSTS_WATCH_START)
        while True:
            try:
                await self.firsts_watch_step()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 -- Spansh down, a timeout, a bad answer: try again later
                print(f"firsts watch: {type(e).__name__}: {e}", file=sys.stderr)
                await asyncio.sleep(FIRSTS_WATCH_BACKOFF)
            await asyncio.sleep(random.uniform(*FIRSTS_WATCH_GAP))

    def here_star(self):
        pos = self.journals.pos
        if not pos:
            return None
        row = self.db.execute("SELECT star_class FROM jumps WHERE id64=? ORDER BY ts DESC LIMIT 1",
                              (pos["id64"],)).fetchone()
        return (row["star_class"] if row else None) or (self.systems.get(pos["id64"]) or {}).get("main_class")

    def codex_recent(self, n=5):
        return [dict(r) for r in self.db.execute(
            "SELECT ts, name, category, subcategory, region, system_name, is_new, voucher FROM codex "
            "WHERE is_new = 1 OR voucher IS NOT NULL ORDER BY ts DESC LIMIT ?", (n,))]

    def leaving_summary(self, id64):
        """What is unfinished in a system: unscanned bodies, unsampled bio, unmapped valuables."""
        sysrow = self.db.execute("SELECT body_count, all_found FROM own_systems WHERE id64=?", (id64,)).fetchone()
        star_row = self.db.execute("SELECT star_class FROM jumps WHERE id64=? ORDER BY ts DESC LIMIT 1", (id64,)).fetchone()
        star = star_row["star_class"] if star_row else None
        bodies = {r["body_id"]: json.loads(r["record"]) for r in
                  self.db.execute("SELECT body_id, record FROM own_bodies WHERE system=?", (id64,))}
        if not sysrow and not bodies:
            return None
        where = self.locate(id64) or ("", None, None, None)
        count = sysrow["body_count"] if sysrow else None
        ctx = bio_context(where[0], bodies.values(), where[1], where[2], where[3], star, count)
        name_of = lambda bid: short_name(where[0], bodies[bid]["name"])
        unscanned = (count - len(bodies)) if count else None
        judge = pickup_judge(self.db, where[0])
        mapped = {r[0] for r in self.db.execute("SELECT body_id, ts, first_ts FROM own_mapped WHERE system=?", (id64,))
                  if judge(r[1], r[2])[0] != "lost"}   # a map that died with the ship needs doing again
        # bio: genera the DSS found vs species you've completed on that body
        genera = {}
        for r in self.db.execute("SELECT body_id, genus_name FROM own_genera WHERE system=?", (id64,)):
            genera.setdefault(r["body_id"], set()).add(r["genus_name"])
        done, logged = {}, {}
        for r in self.db.execute("SELECT body_id, species, genus_name, variant_name, done_ts, samples FROM own_organic WHERE system=?",
                                 (id64,)):
            if r["variant_name"]:
                logged.setdefault(r["body_id"], {})[r["genus_name"]] = r["variant_name"]
            d = done.setdefault(r["body_id"], {"done": set(), "partial": {}})
            if r["done_ts"] and organic_state(self.db, r["done_ts"], (id64, r["body_id"], r["species"])) != "lost":
                d["done"].add(r["genus_name"])   # a sample that died with you needs doing again
            elif not r["done_ts"]:
                d["partial"][r["genus_name"]] = r["samples"]
        bio_signals = {r["name"]: r["bio"] for r in self.db.execute(
            "SELECT name, bio FROM own_signals WHERE system=? AND bio > 0", (id64,))}
        region = outrider.bio.region_name(where[1], where[2], where[3]) if outrider.bio and where[1] is not None else None
        known_codex, known_all = codex_species(self.db, region), codex_species_all(self.db)
        codex_new = lambda bid, groups: any(codex_new_group(g, known_codex) for g in with_logged_variants(groups, logged.get(bid, {}))) \
            if region else False
        codex_galaxy = lambda bid, groups: any(codex_new_group(g, known_all) for g in with_logged_variants(groups, logged.get(bid, {})))
        # the x5 first-footfall bonus per body, as body_bio / approach_facts apply it. A separate factor: potential
        # stays bonus-free, so the bio threshold compares what it always did
        footfalled = {r["body_id"]: r["was_footfalled"] for r in self.db.execute(
            "SELECT body_id, 1 - bio_x5 AS was_footfalled FROM own_firsts WHERE system=?", (id64,))}
        # what the suggested order shows beside each bio body, to decide on the landing before the supercruise
        extra = lambda bid, rec: {"factor": 5 if footfalled.get(bid) == 0 else 1,
                                  "gravity": rec.get("gravity"), "atmosphere": rec.get("atmosphere")}
        bio_pending = []
        for bid, rec in bodies.items():
            n_sig = bio_signals.get(rec["name"], 0)
            if not n_sig and bid not in genera:
                continue
            left = genera.get(bid, set()) - done.get(bid, {}).get("done", set())
            partial = done.get(bid, {}).get("partial", {})
            if bid not in genera:
                # no DSS: the runs under way plus the signals nobody has identified (less the species finished
                # and the runs started there), priced as system_detail does. genera stays None with a run under
                # way too: the page words the unidentified signals from that.
                done_set = done.get(bid, {}).get("done", set())
                n_left = max(0, n_sig - len(done_set) - len(partial))
                if n_left <= 0 and not partial:
                    continue
                groups = bio_left_groups(dict(rec, bio=n_sig), star, None, ctx, done_set | set(partial))
                if partial:
                    groups = bio_guess(rec, star, sorted(partial), ctx)[1] + groups
                val = sum((g.get("value") or 0) for g in groups) or None
                bio_pending.append({"body": name_of(bid), "signals": n_left, "genera": None, "partial": partial, "potential": val,
                                    "codex_new": codex_new(bid, groups), "codex_galaxy": codex_galaxy(bid, groups),
                                    "dist_ls": rec.get("dist_ls"), **extra(bid, rec)})
            elif left or partial:
                left_val, left_groups = bio_guess(rec, star, sorted(left), ctx) if left else (None, [])
                bio_pending.append({"body": name_of(bid), "signals": n_sig, "genera": sorted(left),
                                    "partial": partial, "potential": left_val, "codex_new": codex_new(bid, left_groups),
                                    "codex_galaxy": codex_galaxy(bid, left_groups),
                                    "dist_ls": rec.get("dist_ls"), **extra(bid, rec)})
        unmapped, unmapped_all = [], []
        for bid, rec in bodies.items():
            if bid in mapped or rec.get("type") != "Planet":
                continue
            # first-mapping pays 8x even on a body someone else discovered: either flag counts
            special = (rec.get("was_discovered") is False or rec.get("was_mapped") is False) and \
                (rec["subtype"] in NOTABLE_PLANETS or bool(rec.get("terraformable")))
            if special:
                tag = NOTABLE_PLANETS.get(rec["subtype"], "")
                unmapped.append(f"{name_of(bid)} ({tag or rec['subtype']}{' T' if rec.get('terraformable') else ''}"
                                f"{', first map' if rec.get('was_mapped') is False and rec.get('was_discovered') else ''})")
            # what mapping would add, bonus-free (the green-row level is bonus-free too); the page keeps
            # only the ones over that level, so ordinary bodies never sound the leaving alert
            inc = total = total_bonus = None
            if rec.get("ed") and outrider.unsold:
                plain = dict(rec["ed"], first_discovered=False, first_mapped=False)
                total = outrider.unsold.body_value(plain, True, False, True)
                inc = total - outrider.unsold.body_value(plain, False, False, True)
                # what the page says (the author's choice, review Q5): the body's whole mapped value, without and with
                # your own first-discovery / first-mapped bonuses (never the efficiency bonus, as everywhere)
                mine = dict(rec["ed"], first_discovered=rec.get("was_discovered") is False, first_mapped=rec.get("was_mapped") is False)
                total_bonus = outrider.unsold.body_value(mine, True, False, True)
            unmapped_all.append({"body": name_of(bid), "subtype": rec["subtype"], "terraformable": bool(rec.get("terraformable")),
                                 "increment": inc, "value_mapped": total, "value_mapped_bonus": total_bonus,
                                 "special": special, "dist_ls": rec.get("dist_ls"),
                                 # someone else mapped it (your scan says): no alert points it out (the author, 2026-10-09)
                                 "mapped_before": rec.get("was_mapped") is True})   # the suggested order (by increment)
        unmapped_all.sort(key=lambda u: -(u["increment"] or 0))
        return {"body_count": count, "scanned": len(bodies), "unscanned": unscanned,
                "honked": bool(sysrow), "all_found": bool(sysrow and sysrow["all_found"]),
                "bio_pending": bio_pending, "unmapped_valuable": unmapped, "unmapped": unmapped_all,
                "clean": not unscanned and not bio_pending and not unmapped}

    def system_detail(self, id64):
        """Every body known in a system, valued, with your firsts, mapping, bio and codex."""
        where = self.locate(id64)
        if not where:
            return None
        name = where[0]
        source, base = self.bases.get(id64, (None, None))
        if source in ("own", "route", "edsm"):
            # a stand-in (past Spansh's sphere, or Spansh unreachable): Spansh's bodies once fetched on demand win
            _, fetched = self.spansh.cached(id64)
            if fetched and fetched.get("records"):
                source, base = None, fetched
        if base is None:
            source, (_, base) = None, self.spansh.cached(id64)
        own, own_hotspots, own_count = own_data(self.db, id64, name)
        records = merge_records((base or {}).get("records") or [], own, own_hotspots)
        body_count = max([c for c in ((base or {}).get("body_count"), own_count) if c] or [0]) or None
        own_ids = {short_name(name, r["name"]): r["body_id"] for r in
                   self.db.execute("SELECT body_id, name FROM own_bodies WHERE system=?", (id64,))}
        firsts = {r["body_id"]: dict(r) for r in self.db.execute(
            """SELECT f.body_id, f.was_discovered, f.was_mapped, f.was_footfalled, f.bio_x5, f.undisc_ts, f.first_ts,
                      m.ts AS mapped_ts, m.first_ts AS map_first_ts, ff.ts AS foot_ts FROM own_firsts f
               LEFT JOIN own_mapped m ON m.system = f.system AND m.body_id = f.body_id
               LEFT JOIN own_footfall ff ON ff.system = f.system AND ff.body_id = f.body_id
               WHERE f.system = ?""", (id64,))}
        organics = {}
        for r in self.db.execute("SELECT * FROM own_organic WHERE system=? ORDER BY genus_name", (id64,)):
            st = organic_state(self.db, r["done_ts"], (id64, r["body_id"], r["species"]))
            organics.setdefault(r["body_id"], []).append(
                {"genus": r["genus_name"], "species": r["species_name"], "variant": r["variant_name"],
                 "samples": r["samples"], "done": bool(r["done_ts"]) and st != "lost", "state": st,
                 "lost": st == "lost",
                 "value": outrider.bio.species_value(r["species_name"]) if outrider.bio and r["species_name"] else None})
        genera = {}
        for r in self.db.execute("SELECT body_id, genus_name FROM own_genera WHERE system=?", (id64,)):
            genera.setdefault(r["body_id"], []).append(r["genus_name"])
        mined = {}   # what the SRV's refinery collected on each body, most first
        for r in self.db.execute("SELECT body_id, name, tons, last_ts FROM own_mined WHERE system=?"
                                 " ORDER BY tons DESC, name", (id64,)):
            mined.setdefault(r["body_id"], []).append({"name": r["name"], "tons": r["tons"], "last": r["last_ts"]})
        codex = {}
        for r in self.db.execute("SELECT body_id, name, is_new, voucher, entry_id, subcategory FROM codex WHERE system=?", (id64,)):
            codex.setdefault(r["body_id"], []).append({"name": r["name"], "new": bool(r["is_new"]), "voucher": r["voucher"],
                                                       # an organic entry's id: Canonn Bioforge's statistics for it (the
                                                       # category is "Biological and Geological" for both: the
                                                       # subcategory tells a plant from a geyser)
                                                       "entry_id": r["entry_id"] if "organic" in (r["subcategory"] or "").lower() else None})
        odyssey = True
        star_row = self.db.execute("SELECT star_class FROM jumps WHERE id64=? ORDER BY ts DESC LIMIT 1", (id64,)).fetchone()
        star = star_row["star_class"] if star_row else None
        ctx = bio_context(name, records, where[1], where[2], where[3], star, body_count)
        region = outrider.bio.region_name(where[1], where[2], where[3]) if outrider.bio and where[1] is not None else None
        known_codex, known_all = codex_species(self.db, region), codex_species_all(self.db)
        judge = pickup_judge(self.db, name)
        # your latest scan of each body: data re-collected after a loss or a sale counts again
        latest = {r["body_id"]: r["ts"] for r in self.db.execute("SELECT body_id, ts FROM own_bodies WHERE system=?", (id64,))}
        out = []
        for r in records:
            bid = own_ids.get(r["name"])
            known_genera = genera.get(bid) or r.get("genera") or []
            bio_val, bio_groups = bio_guess(r, star, known_genera or None, ctx) if (r.get("bio") or known_genera) else (None, [])
            # a genus you have sampled here shows the colour the journal logged, not the guess
            bio_groups = with_logged_variants(bio_groups, {o["genus"]: o["variant"] for o in organics.get(bid, []) if o["variant"]})
            f = firsts.get(bid) if bid is not None else None
            first_disc = bool(f and f["was_discovered"] == 0)
            scan_state = judge(latest[bid], f and f["first_ts"])[0] if bid in latest else None
            # a map dies with the ship too; a remap after a sale is sold data
            map_state = judge(f["mapped_ts"], f["map_first_ts"])[0] if f and f["mapped_ts"] else None
            cv = carto_values(r, bid is not None, f, scan_state, map_state, odyssey)
            value, value_if_mapped, base_value = cv["value"], cv["value_if_mapped"], cv["base_value"]
            is_mapped, first_map = cv["mapped"], cv["first_mapped"]
            held = organics.get(bid, [])
            bio_factor = 5 if f and f["bio_x5"] == 1 else 1   # x5 where nobody had set foot when you scanned (not populated)
            # on board: samples not yet sold (sold ones are banked, like sold cartographics)
            bio_now = sum((o.get("value") or 0) for o in held if o["state"] == "aboard") * bio_factor
            got = {o["genus"] for o in held if o["done"] and not o["lost"]}   # sold ones are done too
            left_groups = bio_left_groups(r, star, known_genera, ctx, got) if (r.get("bio") or known_genera) else []
            bio_left = sum((g.get("value") or 0) for g in left_groups) * bio_factor
            carto_now, carto_left = cv["now"], cv["left"]
            # Max without any bonus: no first-discovery / first-mapped multipliers, bio at x1
            max_nb = cv["now_nb"] + cv["left_nb"] + (bio_now + bio_left) / bio_factor
            out.append({
                "value_now": int(carto_now + bio_now), "value_max": int(carto_now + bio_now + carto_left + bio_left),
                "value_max_base": int(max_nb),
                "value_parts": {"carto_now": int(carto_now), "bio_now": int(bio_now), "carto_left": int(carto_left),
                                "bio_left": int(bio_left), "scan_state": scan_state, "bio_factor": bio_factor},
                "name": r["name"], "type": r["type"], "subtype": r["subtype"], "main": r.get("main"),
                "dist_ls": r.get("dist_ls"), "gravity": r.get("gravity"), "atmosphere": r.get("atmosphere"),
                "temperature": r.get("temperature"), "volcanism": r.get("volcanism"), "pressure": r.get("pressure"),
                "ring_details": ring_stats(r.get("rings")),
                "landable": r.get("landable"), "terraformable": r.get("terraformable"),
                # a pre-Odyssey Spansh record: "not landable" may be wrong and bio unreported (your scan replaces it)
                "stale_bio": stale_bio_body(r, star, ctx), "updated": r.get("updated"),
                # your AutoScan or a nav beacon only, no signal count: life is possible, the FSS would tell
                "bio_unknown": bool(unknown_bio_groups(r, star, ctx)),
                # why the other genera are not expected here (the body panel's "why not"), for a body with life
                "ruled_out": outrider.bio.ruled_out(_bio_body(r, star, ctx), ctx) if outrider.bio and r.get("bio") else [],
                "notable": NOTABLE_PLANETS.get(r["subtype"]), "scoopable": r.get("scoopable"),
                "rings": len(r.get("rings") or []), "hotspots": sum(1 for x in r.get("rings") or [] if x.get("hotspots")),
                "belts": r.get("belts") or [],   # belt types: the schematic marks a body with belts
                "rings_mapped": sum(1 for x in r.get("rings") or [] if x.get("hotspots") or x.get("mapped")),
                "bio": r.get("bio") or 0, "geo": r.get("geo") or 0,
                # planetary mining locations, and the survey's odds for this ground (a tooltip on the count)
                "mining": r.get("mining") or 0,
                "mining_odds": mining_odds(mining_ground(r["subtype"], r.get("volcanism"))) if r.get("mining") else None,
                # "Mined previously": [{name, tons, last}] from your SRV's refinery here
                "mined": mined.get(bid if bid is not None else r.get("body_id"), []),
                "genera": known_genera,
                "bio_guess": [{"genus": g["genus"], "best": g["best"], "value": g["value"], "min_value": g["min_value"],
                               "species": [outrider.bio.short_species(x["name"], g["genus"]) for x in g["species"]],
                               "unruled": bool(g.get("unruled")),
                               # the colour candidates of the likeliest species ([] when it cannot be told)
                               "variants": g.get("variants") or [], "variant": g.get("variant"),
                               # the likeliest species (its colour variant, when settled) has no codex entry of
                               # yours in this region yet
                               "codex_new": bool(region and g["genus"] not in got and codex_new_group(g, known_codex)),
                               # ...and none anywhere: new to your codex outright (a stronger mark)
                               "codex_galaxy_new": bool(g["genus"] not in got and codex_new_group(g, known_all)),
                               # the colours of that species you have logged in this region, for the ✦'s tooltip
                               # ("new to your codex here: Bacterium Acies - White; you have Lime")
                               "codex_have": codex_have(g, known_codex)}
                              for g in bio_groups],
                "bio_potential": bio_val,
                # undecided before the DSS: every genus it could be, and the range ("Stratum or Bacterium")
                "bio_options": bio_options(r, star, ctx, {o["genus"] for o in held}) if r.get("bio") and not known_genera else None,
                "organics": organics.get(bid, []), "codex": codex.get(bid, []),
                "scanned": bid is not None, "first_discovered": first_disc, "mapped": is_mapped,
                "first_mapped": first_map, "map_state": map_state, "footfall": bool(f and f["foot_ts"]),
                "first_footfall": bool(f and f["was_footfalled"] == 0 and f["foot_ts"]),
                "value": value, "value_if_mapped": value_if_mapped,
                "base_value": base_value,
                "body_id": r.get("body_id"), "radius_km": r.get("radius_km"), "sma_ls": r.get("sma_ls"),
                "parents_full": r.get("parents_full"),
            })
        out.sort(key=lambda b: -(b["value_max"] or 0))
        tree, parent_of = build_tree(name, out)
        types = {b["name"]: b["type"] for b in out}
        raws = {}
        for r_ in self.db.execute("SELECT name, raw FROM own_bodies WHERE system=?", (id64,)):
            if r_["raw"]:
                raws[short_name(name, r_["name"])] = json.loads(r_["raw"])
        cur = system_curiosities(name, out, raws)
        for b in out:
            p = parent_of.get(b["name"])
            b["is_moon"] = bool(p and p[0] == "b" and types.get(p[1]) == "Planet")
            b["curiosities"] = [{"tag": t, "why": w} for t, w in cur.get(b["name"], [])]
            del b["parents_full"]
        # Spansh knows bodies here but their details have not landed yet (a refresh is fetching them):
        # the page asks again until they have, instead of keeping search-level rows and a guessed tree
        spansh_recs = (base or {}).get("records") or []
        partial = bool(spansh_recs) and not any(x.get("full") for x in spansh_recs) \
            and self.dump_tries.get(id64, 0) < DUMP_MAX_TRIES and not (base or {}).get("no_dump")
        phenomena = [dict(r) for r in self.db.execute("SELECT kind, ts, reached_ts FROM phenomena WHERE system=?", (id64,))]
        leaving = self.leaving_summary(id64)
        if leaving is not None:   # the checklist's "N not on Spansh" (leaving_summary itself runs on every poll)
            leaving["base_known"] = base_known(base, source)
        return {"id64": str(id64), "name": name, "bodies": out, "tree": tree, "partial": partial, "region": region,
                "phenomena": phenomena,
                "leaving": leaving,
                "firsts": own_firsts(self.db, id64, name),
                "value_now": sum(b["value_now"] for b in out), "value_max": sum(b["value_max"] for b in out),
                "value_max_base": sum(b["value_max_base"] for b in out)}

    async def ensure_records(self, id64):
        """Make sure a system's bodies are known before showing it: a search result or pinned system with
        no cached Spansh dump gets one fetched (and cached) now. Failures leave things as they were."""
        if (self.bases.get(id64) or (None,))[0] == "spansh":
            return      # a Spansh entry of the sphere: the refresh fetches it (system_detail says "partial" until then)
        _, base = self.spansh.cached(id64)
        if base:   # any cached answer (a dump, a 404, a search that listed no bodies): not asked again for a day
            age = self.spansh.fetched_age(id64)
            if age is None or age < ON_DEMAND_MAX_AGE:
                return  # fetched on demand recently enough; older snapshots are fetched again below
        where = self.locate(id64)
        if not where:
            return
        name, x, y, z = where
        try:
            await self.spansh.full_records(id64, None, {"v": CACHE_VERSION, "name": name, "x": x, "y": y, "z": z,
                                                        "body_count": (base or {}).get("body_count"),
                                                        "records": (base or {}).get("records") or []},
                                           interactive=True)
        except Exception as e:
            # counted: after DUMP_MAX_TRIES the system is no longer "partial", and the page stops asking every 4 s
            self.dump_tries[id64] = self.dump_tries.get(id64, 0) + 1
            if self.dump_tries[id64] in (1, DUMP_MAX_TRIES):
                print(f"body lookup for {name} failed: {type(e).__name__}: {e}", file=sys.stderr)

    async def body_detail(self, id64, body_name):
        """Everything known about one body: your raw Scan, Spansh's record, and the merged row."""
        detail = self.system_detail(id64)
        if not detail:
            return None
        row = next((b for b in detail["bodies"] if b["name"] == body_name), None)
        # The short name is the full one minus the system prefix, except for named bodies (Earth, a
        # catalogue star in a named system) whose names never carried it: try both forms.
        prefixed = f"{detail['name']} {body_name}" if body_name != detail["name"] else body_name
        raw = self.db.execute("SELECT name, raw FROM own_bodies WHERE system=? AND name IN (?, ?) "
                              "ORDER BY name = ? DESC LIMIT 1", (id64, prefixed, body_name, prefixed)).fetchone()
        full = raw["name"] if raw else prefixed
        own = json.loads(raw["raw"]) if raw and raw["raw"] else None
        spansh = None
        cached = self.dump_cache.get(id64)
        if cached and time.time() - cached[0] < 600:
            dump = cached[1]
        else:
            try:
                dump = await self.spansh.lookup(id64)
                self.dump_cache[id64] = (time.time(), dump)
                if len(self.dump_cache) > 20:
                    self.dump_cache.clear()
            except Exception as e:
                dump, lookup_error = None, f"{type(e).__name__}: {e}"
        if dump:
            names = {full, prefixed, body_name}
            spansh = next((b for b in (dump.get("system") or {}).get("bodies") or [] if b.get("name") == full), None) \
                or next((b for b in (dump.get("system") or {}).get("bodies") or [] if b.get("name") in names), None)
            if spansh and not raw:
                full = spansh.get("name") or full
        rings = ring_stats([{"name": r.get("Name"), "type": RING_CLASSES.get(r.get("RingClass"), r.get("RingClass")),
                             "mass": r.get("MassMT"), "inner": r.get("InnerRad"), "outer": r.get("OuterRad")}
                            for r in (own or {}).get("Rings") or [] if not r.get("Name", "").endswith("Belt")]) \
            if own else ring_stats([{"name": r.get("name"), "type": r.get("type"), "mass": r.get("mass"),
                                     "inner": r.get("innerRadius"), "outer": r.get("outerRadius"),
                                     "hotspots": minerals((r.get("signals") or {}).get("signals"))}
                                    for r in (spansh or {}).get("rings") or []])
        if row:
            for x in rings:  # your DSS: hotspots and the mapped flag
                for y in row.get("ring_details") or []:
                    if y.get("name") and x.get("name", "").endswith(y["name"]):
                        if y.get("hotspots"):
                            x["hotspots"] = y["hotspots"]
                        x["mapped"] = bool(y.get("mapped") or y.get("hotspots") or x.get("hotspots"))
        return {"system": detail["name"], "id64": str(id64), "name": body_name, "full_name": full,
                "row": row, "own": own, "spansh": spansh, "rings": rings,
                "spansh_error": locals().get("lookup_error")}

    COUNT_QUERIES = {
        # by the first scan: undisc_ts moves on with every rescan of your own unsold discovery (still reads as
        # undiscovered), which is not a new first
        "firsts": "SELECT count(DISTINCT system) FROM own_firsts WHERE is_main=1 AND was_discovered=0 AND first_ts BETWEEN ? AND ?",
        "bodies_first": "SELECT count(*) FROM own_firsts WHERE was_discovered=0 AND first_ts BETWEEN ? AND ?",
        "mapped": "SELECT count(*) FROM own_mapped WHERE ts BETWEEN ? AND ?",
        "footfalls": "SELECT count(*) FROM own_footfall WHERE ts BETWEEN ? AND ?",
        "samples": "SELECT count(*) FROM own_organic WHERE done_ts BETWEEN ? AND ?",
        "codex_new": "SELECT count(*) FROM codex WHERE is_new=1 AND ts BETWEEN ? AND ?",
    }

    def export_system(self, id64):
        """One system's bodies as rows (Pioneer's per-system export): (columns, rows, system name), or (None, None,
        None) for a system Outrider knows nothing of."""
        d = self.system_detail(id64)
        if not d:
            return None, None, None
        cols = ["body", "type", "subtype", "distance_ls", "landable", "terraformable", "bio_signals", "geo_signals",
                "genera", "first_discovered", "mapped", "pays_now", "could_pay"]
        rows = [{"body": b["name"], "type": b["type"], "subtype": b.get("subtype"), "distance_ls": b.get("dist_ls"),
                 "landable": b.get("landable"), "terraformable": b.get("terraformable"), "bio_signals": b.get("bio"),
                 "geo_signals": b.get("geo"), "genera": " / ".join(b.get("genera") or []),
                 "first_discovered": b.get("first_discovered"), "mapped": b.get("mapped"),
                 "pays_now": b.get("value_now"), "could_pay": b.get("value_max")} for b in d["bodies"]]
        return cols, rows, d.get("name")

    def range_counts(self, a, b):
        """What you achieved between two timestamps (inclusive): the per-session and all-time numbers."""
        return {k: self.db.execute(sql, (a, b)).fetchone()[0] for k, sql in self.COUNT_QUERIES.items()}

    def note_sale_estimates(self):
        """Sales were just read: record what Outrider estimated just before each, so the trip ledger can say how
        close the estimate was. Only the sales read now (journals.new_sales), and only with an estimate that
        was finished before the sale's line (an estimate running while you sold may already include it; one
        made after a sale read late, at start, is post-sale). Only recent sales (read live) get one; history
        and a sale with no such estimate keep NULL rather than a guess."""
        sales = self.journals.new_sales
        since = iso_ts(time.time() - 3600)
        for ts, kind in sales:
            u = next((u for done, u in reversed(self.unsold_log) if done < ts), None)
            if ts < since or not u or "carto" not in u:
                continue
            value = u["carto"]["estimated_payout"] if kind == "carto" else u["bio"]["estimated_value"]
            # kept apart from sale_events (sale_estimates): a journal re-read rebuilds the sales but not these
            self.db.execute("INSERT OR IGNORE INTO sale_estimates SELECT DISTINCT ts, kind, ? FROM sale_events"
                            " WHERE kind = ? AND ts = ?", (int(value), kind, ts))
        self.journals.new_sales = []   # only once they are in: a failure above leaves them for the retry

    def span_stats(self, a, b):
        """Jumps, light-years and farthest distance from Sol between two timestamps."""
        jumps = [dict(r) for r in self.db.execute(
            "SELECT ts, x, y, z, kind FROM jumps WHERE ts > ? AND ts <= ? ORDER BY ts", (a, b))]
        # the first jump starts where you were at `a`: the row before the window (a relog Location writes no row,
        # so a session's origin is the previous session's last arrival)
        prev = self.db.execute("SELECT x, y, z FROM jumps WHERE ts <= ? ORDER BY ts DESC LIMIT 1", (a,)).fetchone()
        n, ly, far = 0, 0.0, 0.0
        for j in jumps:
            if j["kind"] != "Location":
                n += 1
                if prev:   # a jump after a Location (login, respawn) starts from there
                    ly += dist(prev, j)
            far = max(far, math.sqrt(j["x"] ** 2 + j["y"] ** 2 + j["z"] ** 2))
            prev = j
        systems = self.db.execute("SELECT count(DISTINCT id64) FROM jumps WHERE ts > ? AND ts <= ?", (a, b)).fetchone()[0]
        return {"jumps": n, "ly": round(ly, 1), "max_sol": round(far), "systems": systems}

    def modules_summary(self):
        """The current ship's core modules for the page (S5): [{label, pct, ts, boosts}] in CORE_ORDER, or None
        before a Loadout. pct is rounded down, so a module at 79.6% is under an 80% level. The page applies the
        level; the values are as of each module's last reading (a Loadout, an AfmuRepairs or a repair)."""
        mods = self.journals.ship_modules()
        if not mods:
            return None
        order = {k: i for i, k in enumerate(CORE_ORDER)}
        return [{"label": m["label"], "pct": math.floor(m["health"] * 100 + 1e-9), "ts": m["ts"], "boosts": m["boosts"]}
                for _, m in sorted(mods.items(), key=lambda kv: (order.get(kv[1]["label"], 99), kv[0]))]

    def last_session(self):
        """The Last session card (top of History, and Now): the session the latest quit ended, over login..quit,
        shown until the next login. None while you play, before any quit, after a crash (no Shutdown: the
        next login hides the older card), or when nothing happened in it (a quick relog)."""
        m = meta_get(self.db, "last_session")
        login = (self.journals.commander or {}).get("login_ts")
        if not m or not m.get("login_ts") or m["login_ts"] > m["ts"] or (login and login > m["ts"]):
            return None
        key = (m["login_ts"], m["ts"], self.scan_version)
        if self._last_session[0] != key:
            st = dict(self.span_stats(m["login_ts"], m["ts"]), **self.range_counts(m["login_ts"], m["ts"] + "~"),
                      start=m["login_ts"], end=m["ts"])
            busy = any(st[k] for k in ("jumps", "firsts", "bodies_first", "mapped", "footfalls", "samples", "codex_new"))
            self._last_session = (key, st if busy else None)
        return self._last_session[1]

    def this_session(self):
        """Now's This session line (S10): the Last session card's numbers over login..now, while you play. None
        before a login, in the menus after a quit, or before anything counted has happened. found: what was found
        since the login in credits, an estimate: the unsold estimate now less the one over the journals before the
        login (worked out once per login, beside the next estimate), plus what was sold since (commander.earned).
        Left out until that baseline exists; never below 0 (a death takes data, not what you found)."""
        c = self.journals.commander or {}
        login = c.get("login_ts")
        if not login or login <= (c.get("shutdown_ts") or ""):
            return None
        # a jump moves the position (scan data moves scan_version): the line keeps up with both at once
        pos = self.journals.pos or {}
        key = (login, self.scan_version, self.version // 50, pos.get("id64"), pos.get("ts"))
        if self._this_session[0] != key:
            st = dict(self.span_stats(login, "~"), **self.range_counts(login, "~"), start=login)
            busy = any(st[k] for k in ("jumps", "firsts", "bodies_first", "mapped", "footfalls", "samples", "codex_new"))
            self._this_session = (key, st if busy else None)
        st, u = self._this_session[1], self.unsold or {}
        if st is None:
            return None
        found = None
        if self.unsold_login[0] == login and self.unsold_login[1] is not None and isinstance(u.get("total"), (int, float)):
            found = max(0, int(u["total"] - self.unsold_login[1] + (c.get("earned") or 0)))
        return dict(st, found=found)

    STREAK_SHOWN = 20    # arrivals in the streak strip
    STREAK_RUNS = 100    # arrivals looked at for the runs (the spoken streak thresholds go up to 99)
    SPANSH_VERDICT = {"explored": "complete", "partial": "partial", "no bodies": "partial",
                      "unreported": "partial"}   # Spansh had not heard of it, but the game says it was discovered

    def spansh_verdict(self, id64):
        """What Spansh knew about a known system before your own scans: complete (every body reported) or
        partial (bodies still unreported), from the target lookup when you plotted it, else the sphere or the
        cache. None when nothing is known."""
        v = self.SPANSH_VERDICT.get(self.target_verdicts.get(id64))
        if v:
            return v
        source, base = self.bases.get(id64) or (None, None)
        if base is None or source == "route":
            source, base = "cache", cached_base(self.db, id64)[1]
        if not base or source in ("edsm", "own") or base.get("edsm"):
            return None   # a stand-in (Spansh unreachable, or past its sphere): not what Spansh knew
        known = sum(1 for r in base.get("records") or [] if r.get("type") in ("Star", "Planet"))
        return "complete" if known and base.get("body_count") and known >= base["body_count"] else "partial"

    def fix_verdict(self, scan):
        """The arrival's colour in the streak strip, final from now on: the journal's verdict (new, visited,
        known), with known turned into partial or complete by what Spansh knew at this moment and stored."""
        row = self.db.execute("SELECT j.ts, j.verdict, v.verdict AS fixed FROM jumps j LEFT JOIN arrival_verdicts v "
                              "ON v.ts = j.ts AND v.id64 = j.id64 WHERE j.id64 = ? AND j.ts <= ? "
                              "AND j.kind IN ('FSDJump', 'CarrierJump') ORDER BY j.ts DESC LIMIT 1",
                              (scan["id64"], scan["ts"])).fetchone()
        if not row:
            return None
        if row["fixed"] or row["verdict"] != "known":
            return row["fixed"] or row["verdict"]
        v = self.spansh_verdict(scan["id64"])
        if v:
            self.db.execute("INSERT OR IGNORE INTO arrival_verdicts VALUES (?, ?, ?)", (row["ts"], scan["id64"], v))
            self.db.commit()
        return v or "known"

    @staticmethod
    def streak_runs(verdicts):
        """(new in a row, known in a row) counted back from the newest arrival. Known in a row is fully reported
        systems (complete, or known with no Spansh word): a new or partly reported system (still work for you)
        ends it, and so does one you had visited (a way back is not a heading to change)."""
        new = next((i for i, v in enumerate(verdicts) if v != "new"), len(verdicts))
        known = next((i for i, v in enumerate(verdicts) if v not in ("complete", "known")), len(verdicts))
        return new, known

    def streak(self):
        """The discovery streak: the last STREAK_SHOWN hyperspace and carrier arrivals, oldest first, each with
        its fixed verdict (None until its arrival star is scanned), your firsts there and the value you
        scanned; the count of new ones and the current runs."""
        last = self.db.execute("SELECT max(ts) FROM jumps").fetchone()[0]
        key = (last, self.arrival_seq, self.scan_version)
        if self._streak[0] == key:
            return self._streak[1]
        rows = [dict(r) for r in self.db.execute(
            "SELECT j.ts, j.id64, j.name, coalesce(v.verdict, j.verdict) AS verdict FROM jumps j "
            "LEFT JOIN arrival_verdicts v ON v.ts = j.ts AND v.id64 = j.id64 "
            "WHERE j.kind IN ('FSDJump', 'CarrierJump') ORDER BY j.ts DESC LIMIT ?", (self.STREAK_RUNS,))]
        if not rows:
            self._streak = (key, None)
            return None
        run_new, run_known = self.streak_runs([r["verdict"] for r in rows])
        shown = rows[:self.STREAK_SHOWN]
        ids = list({r["id64"] for r in shown})
        marks = ",".join("?" * len(ids))
        firsts = {r[0]: r[1] for r in self.db.execute(
            f"SELECT system, count(*) FROM own_firsts WHERE was_discovered = 0 AND system IN ({marks}) GROUP BY system", ids)}
        value = dict.fromkeys(ids, 0)
        if outrider.unsold:
            mapped = {(r[0], r[1]) for r in self.db.execute(f"SELECT system, body_id FROM own_mapped WHERE system IN ({marks})", ids)}
            fl = {(r[0], r[1]): r for r in self.db.execute(
                f"SELECT system, body_id, was_discovered, was_mapped FROM own_firsts WHERE system IN ({marks})", ids)}
            for r in self.db.execute(f"SELECT system, body_id, record FROM own_bodies WHERE system IN ({marks})", ids):
                ed = json.loads(r["record"]).get("ed")
                if ed:
                    f = fl.get((r["system"], r["body_id"]))
                    body = dict(ed, first_discovered=bool(f and f["was_discovered"] == 0), first_mapped=bool(f and f["was_mapped"] == 0))
                    value[r["system"]] += outrider.unsold.body_value(body, (r["system"], r["body_id"]) in mapped, False, True)
        arrivals = [{"ts": r["ts"], "id": str(r["id64"]), "name": r["name"], "verdict": r["verdict"],
                     "firsts": firsts.get(r["id64"], 0), "value": value.get(r["id64"], 0)} for r in reversed(shown)]
        out = {"arrivals": arrivals, "new": sum(1 for a in arrivals if a["verdict"] == "new"), "total": len(arrivals),
               "run_new": run_new, "run_known": run_known}
        self._streak = (key, out)
        return out

    def ledger(self):
        """The turn-back numbers: since your last sale, each sale-to-sale trip with what it actually paid,
        what each ship loss cost, the game's own career statistics and your most valuable finds."""
        key = (self.scan_version, self.db.execute("SELECT count(*) FROM sale_events").fetchone()[0],
               self.db.execute("SELECT count(*) FROM sale_estimates").fetchone()[0])
        if getattr(self, "_ledger_key", None) == key:
            return self._ledger
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        sales = [dict(r) for r in self.db.execute(
            """SELECT e.*, s.estimate FROM sale_events e
               LEFT JOIN sale_estimates s ON s.ts = e.ts AND s.kind = e.kind ORDER BY e.ts, e.source""")]
        # selling in several batches at one station is one sale: merge carto sales within an hour
        carto_sales = []
        for x in (x for x in sales if x["kind"] == "carto"):
            last = carto_sales[-1] if carto_sales else None
            if last and ts_seconds(x["ts"]) - ts_seconds(last["ts"]) < 3600:
                last.update(ts=x["ts"], total=(last["total"] or 0) + (x["total"] or 0),
                            systems=(last["systems"] or 0) + (x["systems"] or 0),
                            estimate=last["estimate"] if last["estimate"] is not None else x["estimate"])
            else:
                carto_sales.append(dict(x))
        last_carto = carto_sales[-1]["ts"] if carto_sales else ""
        last_bio = next((x["ts"] for x in reversed(sales) if x["kind"] == "bio"), None)
        since = dict(self.span_stats(last_carto, now), **self.range_counts(last_carto, "~"),
                     since=last_carto or None, last_bio=last_bio,
                     days=round((time.time() - ts_seconds(last_carto)) / 86400, 1) if last_carto else None)
        losses = self.ship_losses()
        spans = [(ts_seconds(s_["start"]), ts_seconds(s_["end"])) for s_ in self.sessions("")]

        def trip(start, end, x):
            bio_in = [y for y in sales if y["kind"] == "bio" and start < y["ts"] <= end]
            paid_bio = sum(y["total"] or 0 for y in bio_in)
            # the bio estimate against what those sales paid, and the x5 check. A visit sold in several goes (sales
            # under SALE_SESSION_S apart) is one sale: its first estimate was for everything aboard, the later ones
            # are stamped with the same one or made after part was sold, so only the first counts, against what
            # the whole visit paid (a visit whose first sale has no estimate is left out)
            visits = []
            for y in bio_in:
                if visits and ts_seconds(y["ts"]) - ts_seconds(visits[-1][-1]["ts"]) < SALE_SESSION_S:
                    visits[-1].append(y)
                else:
                    visits.append([y])
            est_bio = [v for v in visits if v[0]["estimate"] is not None]
            checks = [json.loads(y["x5_check"]) for y in bio_in if y.get("x5_check")]
            x5 = {k: sum(c.get(k) or 0 for c in checks) for k in ("sold", "predicted", "matched", "paid", "unknown")} \
                if checks else None
            # flying time: each session clipped to the trip, so one that spans the sale counts on both sides
            lo, hi = ts_seconds(start) if start else float("-inf"), ts_seconds(end)
            hours = sum(overlap(a, b, lo, hi) for a, b in spans) / 3600
            st = self.span_stats(start, end)
            counts = self.range_counts(start, end)
            paid = (x["total"] or 0) + paid_bio
            return dict(st, **counts, start=start or None, end=end,
                        days=round((ts_seconds(end) - ts_seconds(start)) / 86400, 1) if start else None,
                        paid_carto=x["total"], paid_bio=paid_bio, paid=paid, estimate=x["estimate"],
                        estimate_bio=sum(v[0]["estimate"] for v in est_bio) if est_bio else None,
                        paid_bio_estimated=sum(y["total"] or 0 for v in est_bio for y in v) if est_bio else None, x5=x5,
                        hours=round(hours, 1),
                        per_hour=round(paid / hours) if hours >= 0.5 else None,
                        per_jump=round(paid / st["jumps"]) if st["jumps"] else None,
                        per_ly=round(paid / st["ly"]) if st["ly"] else None,
                        first_rate=round(100 * counts["firsts"] / st["jumps"]) if st["jumps"] else None,
                        losses=[l for l in losses if start < l["ts"] <= end])

        trips, start = [], ""
        for x in carto_sales:
            trips.append(trip(start, x["ts"], x))
            start = x["ts"]
        # the trip under way: Vista Genomics sales since the last cartographic one (all of them, for a player who
        # sells only exobiology) belong to no closed trip yet, so their payout and x5 check show here until the
        # next cartographic sale ends it
        current = None
        if last_bio and last_bio > last_carto:
            current = dict(trip(last_carto, now, {"total": None, "estimate": None}), end=None)
        trips.reverse()
        stats = meta_get(self.db, "statistics")
        self._ledger = {"since_last_sale": since, "trips": trips, "current": current, "career": stats, "losses": losses,
                        "top_finds": self.top_finds()}
        self._ledger_key = key
        return self._ledger

    def lost_bodies(self, deaths):
        """(death ts, system, value, first discovery) for each scanned body that died with the ship at one of
        `deaths` (the ship losses, oldest first): scanned since the previous loss, not sold before this one and
        not scanned again since, valued with the bonuses. ship_losses totals them; loss_facts groups them by system."""
        if not outrider.unsold or not deaths:
            return
        sales = {}
        for r in self.db.execute("SELECT name, ts FROM sales"):
            sales.setdefault(r["name"], []).append(r["ts"])
        mapped = {(r[0], r[1]): r[2] for r in self.db.execute("SELECT system, body_id, ts FROM own_mapped")}
        firsts = {(r[0], r[1]): r for r in self.db.execute(
            "SELECT system, body_id, was_discovered, was_mapped, first_ts FROM own_firsts")}
        names = {r[0]: r[1] for r in self.db.execute("SELECT id64, name FROM visits")}
        for r in self.db.execute("SELECT system, body_id, ts, record FROM own_bodies"):
            i = next((k for k, d in enumerate(deaths) if d > r["ts"]), None)   # the first loss after your latest scan
            if i is None or (i > 0 and r["ts"] < deaths[i - 1]):
                continue
            sold = sales.get(names.get(r["system"]), [])
            if any(r["ts"] < t < deaths[i] for t in sold):
                continue      # sold before the loss
            f = firsts.get((r["system"], r["body_id"]))
            if f and f["first_ts"] and any(f["first_ts"] < t < r["ts"] and not any(f["first_ts"] < l < t for l in deaths)
                                           for t in sold):
                continue      # sold already, then rescanned (a return visit): pickup_judge's 'sold' rule
            rec = json.loads(r["record"])
            if not rec.get("ed"):
                continue
            m = mapped.get((r["system"], r["body_id"]))
            # a map made before the previous ship loss died with that ship, not this one
            m_aboard = bool(m and m < deaths[i] and (i == 0 or m > deaths[i - 1]))
            body = dict(rec["ed"], first_discovered=bool(f and f["was_discovered"] == 0),
                        first_mapped=bool(f and f["was_mapped"] == 0))
            yield deaths[i], r["system"], outrider.unsold.body_value(body, m_aboard, False, True), bool(f and f["was_discovered"] == 0)

    def ship_losses(self):
        """What each death cost: the cartographic data that died with the ship (bodies scanned since the previous
        ship loss, not sold before it, and not scanned again since; valued with the bonuses), plus the
        exobiology aboard (completed sample runs not sold before the death, valued as Bio/Geo's My Samples does,
        with the x5 first footfall). Every ship loss is listed; a death that kept the ship (on foot) only when
        it cost exobiology. ship: whether the ship was lost."""
        ship_deaths = [r[0] for r in self.db.execute(f"SELECT ts FROM deaths WHERE {SHIP_LOSS_SQL} ORDER BY ts")]
        all_deaths = [r[0] for r in self.db.execute("SELECT ts FROM deaths ORDER BY ts")]
        if not all_deaths:
            return []
        out = {d: {"ts": d, "bodies": 0, "value": 0, "firsts": 0, "bio_value": 0, "bio_runs": 0, "ship": d in ship_deaths}
               for d in all_deaths}
        for death, _system, value, first in self.lost_bodies(ship_deaths):
            row = out[death]
            row["bodies"] += 1
            row["value"] += value
            row["firsts"] += int(first)
        # exobiology: any death takes the samples aboard (organic_replay: the first death after a run was completed,
        # unless a Vista Genomics sale took that run first)
        fates = organic_fates(self.db)
        for r in self.db.execute("""SELECT o.system, o.body_id, o.species, o.species_name, (1 - f.bio_x5) AS was_footfalled FROM own_organic o
                                    LEFT JOIN own_firsts f ON f.system = o.system AND f.body_id = o.body_id
                                    WHERE o.done_ts IS NOT NULL"""):
            state, death = fates.get((r["system"], r["body_id"], r["species"])) or (None, None)
            if state != "lost" or death not in out:
                continue
            base = outrider.bio.species_value(r["species_name"]) if outrider.bio and r["species_name"] else None
            out[death]["bio_runs"] += 1
            out[death]["bio_value"] += (base or 0) * (5 if r["was_footfalled"] == 0 else 1)
        return [x for x in out.values() if x["ship"] or x["bio_runs"]]

    def loss_facts(self, death_ts):
        """The ship-loss debrief for the death at death_ts: ship_losses()'s totals for it (the numbers History
        shows), and the systems its lost scans were in (the five most valuable, and the nearest) measured from
        where you are now, the station you respawned at. None when that death cost nothing."""
        row = next((r for r in self.ship_losses() if r["ts"] == death_ts), None)
        if not row or not (row["value"] or row["bio_value"]):
            return None
        per = {}
        for death, system, value, _first in self.lost_bodies([r[0] for r in self.db.execute(
                f"SELECT ts FROM deaths WHERE {SHIP_LOSS_SQL} ORDER BY ts")]):
            if death == death_ts:
                per[system] = per.get(system, 0) + value
        pos, systems = self.journals.pos, []
        for sid, value in per.items():
            v = self.db.execute("SELECT name, x, y, z FROM visits WHERE id64=?", (sid,)).fetchone()
            systems.append({"id": str(sid), "name": v["name"] if v else str(sid), "value": round(value),
                            "distance": round(dist(pos, v), 1) if pos and v and v["x"] is not None else None})
        systems.sort(key=lambda x: -x["value"])
        nearest = min((x for x in systems if x["distance"] is not None), key=lambda x: x["distance"], default=None)
        return {"ship": row["ship"], "value": round(row["value"] + row["bio_value"]), "carto": round(row["value"]),
                "bio": round(row["bio_value"]), "bio_runs": row["bio_runs"], "bodies": row["bodies"],
                "firsts": row["firsts"], "systems": len(systems), "nearest": nearest, "top": systems[:5]}

    def top_finds(self, n=25):
        """Your most valuable bodies ever (cartographics, with the bonuses you earned), and what became of them."""
        if not outrider.unsold:
            return []
        judges, best = {}, []
        names = {r[0]: r[1] for r in self.db.execute("SELECT id64, name FROM visits")}
        mapped = {(r[0], r[1]): r[2] for r in self.db.execute("SELECT system, body_id, ts FROM own_mapped")}
        firsts = {(r[0], r[1]): r for r in self.db.execute(
            "SELECT system, body_id, was_discovered, was_mapped, first_ts FROM own_firsts")}
        for r in self.db.execute("SELECT system, body_id, name, ts, record FROM own_bodies"):
            rec = json.loads(r["record"])
            if not rec.get("ed"):
                continue
            f = firsts.get((r["system"], r["body_id"]))
            m = mapped.get((r["system"], r["body_id"]))
            body = dict(rec["ed"], first_discovered=bool(f and f["was_discovered"] == 0),
                        first_mapped=bool(f and f["was_mapped"] == 0))
            v = outrider.unsold.body_value(body, bool(m), False, True)
            if len(best) < n or v > best[-1][0]:
                best.append((v, r, rec, bool(m), body))
                best.sort(key=lambda t: -t[0])
                del best[n:]
        out = []
        for v, r, rec, is_mapped, body in best:
            sysname = names.get(r["system"]) or ""
            if sysname not in judges:
                judges[sysname] = pickup_judge(self.db, sysname)
            f = firsts.get((r["system"], r["body_id"]))   # the first scan: a sale since then bought it (a rescan is not new data)
            out.append({"body": r["name"], "system": sysname, "id": str(r["system"]), "type": rec.get("subtype"),
                        "value": v, "mapped": is_mapped, "first_discovered": body["first_discovered"],
                        "state": judges[sysname](r["ts"], f and f["first_ts"])[0], "ts": r["ts"]})
        return out

    def history(self, days):
        """Your sessions (gaps of 2 h+ split them), newest first, with what each one achieved,
        plus an all-time row that ignores `days`."""
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))
        sessions = self.sessions(since)
        for s_ in sessions:
            # a session owns everything from its login (or first jump) until the next session's window starts
            # (scans and samples after its last jump, a long stay with no jump); the latest runs on ("~" sorts
            # after any time)
            s_.update(self.range_counts(s_["from"], second_before(s_["until"]) if s_["until"] else "~"))
        everything = self.sessions("")
        all_time = {"jumps": sum(x["jumps"] for x in everything), "ly": round(sum(x["ly"] for x in everything), 1),
                    "max_sol": max((x["max_sol"] for x in everything), default=0), "sessions": len(everything),
                    "since": everything[-1]["start"] if everything else None}
        all_time.update(self.range_counts("", "~"))
        return {"days": days, "sessions": sessions, "all_time": all_time, "ledger": self.ledger()}

    def sessions(self, since):
        """Jumps since `since` grouped into sessions, newest first (no achievement counts). start/end are the
        first and last jump; from is where its window for counting what you did starts (the latest login at or
        before the first jump and after the previous session's last one, else the first jump: work done after
        logging in, before jumping, belongs to this session, as on the Last session card); until is the next
        session's from. A login that no jump followed, 2 h+ after anything else, opens a session with no jumps."""
        jumps = [dict(r) for r in self.db.execute(
            "SELECT ts, id64, name, x, y, z, kind FROM jumps WHERE ts >= ? ORDER BY ts", (since,))]
        sessions, cur = [], None
        # a session's first jump starts from the previous row (the last session's arrival; a relog Location
        # writes no row), and the window's first from the row before it
        last = self.db.execute("SELECT x, y, z FROM jumps WHERE ts < ? ORDER BY ts DESC LIMIT 1", (since,)).fetchone()
        for j in jumps:
            t = ts_seconds(j["ts"])   # UTC: a local DST change must not move the 2 h split
            if not cur or t - cur["_last"] > 7200:
                cur = {"start": j["ts"], "end": j["ts"], "_last": t, "jumps": 0, "ly": 0.0, "systems": [],
                       "max_sol": 0.0, "_prev": last}
                sessions.append(cur)
            cur["end"], cur["_last"] = j["ts"], t
            if j["kind"] != "Location":
                cur["jumps"] += 1
                if cur["_prev"]:   # from a Location (login, respawn) too: that is where the jump started
                    cur["ly"] += dist(cur["_prev"], j)
            cur["max_sol"] = max(cur["max_sol"], math.sqrt(j["x"] ** 2 + j["y"] ** 2 + j["z"] ** 2))
            cur["systems"].append({"ts": j["ts"], "id": str(j["id64"]), "name": j["name"], "kind": j["kind"]})
            cur["_prev"] = last = j
        prev_end = self.db.execute("SELECT max(ts) FROM jumps WHERE ts < ?", (since,)).fetchone()[0] or ""
        logins = [r[0] for r in self.db.execute("SELECT ts FROM logins WHERE ts > ? ORDER BY ts", (prev_end,))]
        for s_ in sessions:
            s_["from"] = next((t for t in reversed(logins) if prev_end < t <= s_["start"]), s_["start"])
            prev_end = s_["end"]
        # a login 2 h+ after anything else that no jump followed (a sampling or Rhino evening in one system) is a
        # session of its own, not more of the one before it (review F31); logins within 2 h of it join it
        idle = []
        for t in logins:
            if t < since or any(s_["from"] <= t <= s_["end"] for s_ in sessions):
                continue
            nxt = next((s_ for s_ in sessions if s_["from"] > t), None)
            if nxt and ts_seconds(nxt["from"]) - ts_seconds(t) <= 7200:
                nxt["from"] = t   # a relog shortly before that session's first jump: it started here
                continue
            last = max([s_["end"] for s_ in sessions if s_["end"] < t] + [x["end"] for x in idle], default="")
            if last and ts_seconds(t) - ts_seconds(last) <= 7200:
                if idle and idle[-1]["end"] == last:
                    idle[-1]["end"] = t
                continue
            at = self.db.execute("SELECT ts, id64, name, x, y, z FROM jumps WHERE ts <= ? ORDER BY ts DESC LIMIT 1",
                                 (t,)).fetchone()
            idle.append({"start": t, "end": t, "from": t, "jumps": 0, "ly": 0.0,
                         "max_sol": math.sqrt(at["x"] ** 2 + at["y"] ** 2 + at["z"] ** 2) if at else 0.0,
                         "systems": [{"ts": t, "id": str(at["id64"]), "name": at["name"], "kind": "Location"}] if at else []})
        sessions = sorted(sessions + idle, key=lambda x: x["start"])
        for s_, nxt in zip(sessions, sessions[1:] + [None]):
            s_["ly"] = round(s_["ly"], 1); s_["max_sol"] = round(s_["max_sol"])
            s_["until"] = nxt and nxt["from"]   # where the next session's window starts (None: the latest)
            s_.pop("_last", None); s_.pop("_prev", None)
        sessions.reverse()
        return sessions

    def system_names(self, ids):
        """id64 -> name for systems you have visited or scanned."""
        ids = list(set(ids))
        names = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for table, col in (("own_systems", "id64"), ("visits", "id64")):
                for r in self.db.execute(f"SELECT {col} AS id, name FROM {table} WHERE {col} IN ({marks})", chunk):
                    if r["name"]:
                        names[r["id"]] = r["name"]
        return names

    def geo_codex(self):
        """The geology checklist's entries (resources/geo_codex.json), read once; [] when the file is missing."""
        if getattr(self, "_geo_codex", None) is None:
            try:
                with open(GEO_CODEX_FILE, encoding="utf-8") as f:
                    self._geo_codex = json.load(f).get("entries") or []
            except (OSError, ValueError, AttributeError):
                self._geo_codex = []
        return self._geo_codex

    def codex_images(self):
        """{entry's English name lower-cased: [image url, commander]}: the list fetched today (data/codex_images.json)
        when it is sound, else the shipped one (outrider.codex_images.load). Read once, and again after a refresh."""
        if getattr(self, "_codex_images", None) is None:
            self._codex_images = outrider.codex_images.load()
        return self._codex_images

    async def refresh_codex_images(self):
        """Fetch Canonn's codex reference and keep its picture links in data/ (outrider.codex_images). True when the
        list was replaced; raises when Canonn cannot be reached or its answer is not a sound list."""
        async with self.spansh.session.get(outrider.codex_images.REF, timeout=ClientTimeout(total=120)) as r:
            r.raise_for_status()
            images = outrider.codex_images.parse(await r.json(content_type=None))
        await asyncio.get_running_loop().run_in_executor(None, outrider.codex_images.save, outrider.codex_images.CACHE, images)
        self._codex_images = None   # read again at the next panel
        return True

    async def watch_codex_images(self):
        """The checklists' picture list, refreshed from Canonn once a day (a few minutes after the start when today's
        copy is missing or a day old). Only the request is made: nothing about the player is sent."""
        await asyncio.sleep(CODEX_IMAGES_START)
        while True:
            age = outrider.codex_images.cache_age()
            if age is not None and age < CODEX_IMAGES_EVERY:
                await asyncio.sleep(CODEX_IMAGES_EVERY - age)
            try:
                await self.refresh_codex_images()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 -- offline, Canonn down, a changed answer: the list kept, tried again later
                print(f"codex pictures: could not refresh the list from Canonn ({type(e).__name__}); trying again in an hour",
                      file=sys.stderr)
                await asyncio.sleep(CODEX_IMAGES_RETRY)

    def checklist(self, region="here", kind="bio"):
        """GET /api/checklist?kind=bio|geo&region=here|all|<1-42>: a checklist for a galactic region, where you are by
        default, with the regions to choose from and each one's completion. bio: the exobiology one
        (outrider.checklist.table) from every run you have made (its fate as My Samples has it) and every codex entry;
        geo: the codex's Geology and Anomalies entries (geo_table) from your codex. (answer, HTTP status)."""
        R = outrider.bio.load_rules() if outrider.bio else None
        if not R or not R.get("region_names"):
            return {"error": "the exobiology rules are not loaded"}, 503
        if kind not in ("bio", "geo"):
            return {"error": "kind is bio or geo"}, 400
        names = R["region_names"]
        count = len(names) - 1
        pos = self.journals.pos or {}
        here = outrider.bio.region_number(pos.get("x"), pos.get("y"), pos.get("z")) if pos.get("x") is not None else None
        if region in (None, "", "here"):
            region = here
        elif region == "all":
            region = None
        else:
            try:
                region = int(region)
            except (TypeError, ValueError):
                return {"error": "region is here, all or a region number"}, 400
            if not 1 <= region <= count:
                return {"error": f"region is 1 to {count}"}, 400
        placed = {}
        number = {n.lower(): i for i, n in enumerate(names) if n}   # the codex says its region by name
        if kind == "geo":
            entries = self.geo_codex()
            if not entries:
                return {"error": "the geology list is missing (resources/geo_codex.json)"}, 503
            ids = {e["id"] for e in entries}
            codex = [{"entry_id": c["entry_id"], "region": number.get((c["region"] or "").lower())}
                     for c in self.db.execute("SELECT entry_id, region FROM codex") if c["entry_id"] in ids]
            out = outrider.checklist.geo_table(entries, region, codex, count)
            done = outrider.checklist.geo_completion(entries, codex, count)
            return dict(out, kind="geo", regions=[{"id": i, "name": n, "completion": done.get(i)} for i, n in enumerate(names) if n],
                        completion_all=done["all"], here=here, region=region, region_name=names[region] if region else None), 200

        def region_of(system):
            if system not in placed:
                loc = self.locate(system)
                placed[system] = outrider.bio.region_number(loc[1], loc[2], loc[3]) if loc and loc[1] is not None else None
            return placed[system]
        fates = organic_fates(self.db)
        runs = []
        for r in self.db.execute("SELECT system, body_id, species, species_name, variant_name, done_ts FROM own_organic"):
            fate = fates.get((r["system"], r["body_id"], r["species"])) if r["done_ts"] else None
            state = fate[0] if fate else (organic_state(self.db, r["done_ts"]) if r["done_ts"] else None) or "in progress"
            runs.append({"species_id": r["species"], "species": r["species_name"], "variant": r["variant_name"],
                         "region": region_of(r["system"]), "state": state})
        codex = [{"name": c["name"], "region": number.get((c["region"] or "").lower())}
                 for c in self.db.execute("SELECT name, region FROM codex")]
        out = outrider.checklist.table(R["species"], region, outrider.bio.ruleset_region_ok, runs, codex, count)
        done = outrider.checklist.completion(R["species"], outrider.bio.ruleset_region_ok, runs, codex, count)
        return dict(out, kind="bio", regions=[{"id": i, "name": n, "completion": done.get(i)} for i, n in enumerate(names) if n],
                    completion_all=done["all"], here=here, region=region, region_name=names[region] if region else None), 200

    def checklist_geo(self, entry_id):
        """GET /api/checklist?kind=geo&species=<entry id>: one geology entry for the panel: the regions it has been
        reported in ("yes"), the sites per region, and where you logged it ({x, z, state, system})."""
        e = next((x for x in self.geo_codex() if str(x["id"]) == str(entry_id)), None)
        if e is None:
            return {"error": "no such entry"}, 404
        runs = []
        for c in self.db.execute("SELECT system FROM codex WHERE entry_id = ?", (e["id"],)):
            loc = self.locate(c["system"]) if c["system"] else None
            if loc and loc[1] is not None:
                runs.append({"x": loc[1], "z": loc[3], "state": "logged", "system": loc[0]})
        regions = e.get("regions") or {}
        img = self.codex_images().get(e["name"].lower())
        return {"id": str(e["id"]), "name": e["name"], "kind": e.get("kind"), "group": e.get("group"),
                "image": {"url": img[0], "cmdr": img[1]} if img else None,
                "regions": {r: "yes" for r, n in regions.items() if n}, "sites": regions, "sites_total": sum(regions.values()),
                "runs": runs}, 200

    def checklist_species(self, species_id):
        """GET /api/checklist?species=<id>: one species for the checklist's panel: the regions it can grow in ("yes",
        "parts") and where you have sampled it ({x, z, state} per run). (answer, HTTP status)."""
        R = outrider.bio.load_rules() if outrider.bio else None
        if not R:
            return {"error": "the exobiology rules are not loaded"}, 503
        merged, _ = outrider.checklist.merge_species(R["species"])
        sp = next((s for s in merged if (s.get("id") or s["name"]) == species_id), None)
        if sp is None:
            return {"error": "no such species"}, 404
        fates, runs = organic_fates(self.db), []
        for r in self.db.execute("SELECT system, body_id, species, done_ts FROM own_organic WHERE species = ? OR species_name = ?",
                                 (sp.get("id"), sp["name"])):
            loc = self.locate(r["system"])
            if not loc or loc[1] is None:
                continue
            fate = fates.get((r["system"], r["body_id"], r["species"])) if r["done_ts"] else None
            state = fate[0] if fate else (organic_state(self.db, r["done_ts"]) if r["done_ts"] else None) or "in progress"
            runs.append({"x": loc[1], "z": loc[3], "state": state, "system": loc[0]})
        regions = outrider.checklist.where(sp, outrider.bio.ruleset_region_ok, len(R["region_names"]) - 1)
        # its pictures (Canonn's, linked): one per colour ("" for a species with no colour table), by the codex's names
        imgs, have = {}, self.codex_images()
        for colour, _ in outrider.checklist.colours(sp) or [("", None)]:
            hit = have.get(f"{sp['name']} - {colour}".lower() if colour else sp["name"].lower())
            if not hit and not colour and sp.get("genus"):   # Canonn keys Bark Mound as the game does: "bark mounds"
                hit = have.get(sp["genus"].lower())
            if hit:
                imgs[colour.lower()] = {"url": hit[0], "cmdr": hit[1]}
        return {"id": species_id, "name": sp["name"], "regions": {str(k): v for k, v in regions.items()}, "runs": runs,
                "images": imgs}, 200

    def organics(self, days):
        """Every exobiology sample run (newest first) with what it is worth and whether it was banked,
        plus your codex entries over the same period."""
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))
        runs = [dict(r) for r in self.db.execute(
            """SELECT o.*, b.name AS body_name, (1 - f.bio_x5) AS was_footfalled FROM own_organic o
               LEFT JOIN own_bodies b ON b.system = o.system AND b.body_id = o.body_id
               LEFT JOIN own_firsts f ON f.system = o.system AND f.body_id = o.body_id
               WHERE coalesce(o.done_ts, o.ts) >= ? ORDER BY coalesce(o.done_ts, o.ts) DESC""", (since,))]
        codex = [dict(r) for r in self.db.execute("SELECT * FROM codex WHERE ts >= ? ORDER BY ts DESC", (since,))]
        names = self.system_names([r["system"] for r in runs] + [c["system"] for c in codex if c["system"]])
        fates = organic_fates(self.db)   # a sale takes one run per BioData entry of its species (organic_replay)
        rows, totals = [], {"aboard": 0, "sold": 0, "lost": 0, "in progress": 0}
        counts = dict.fromkeys(totals, 0)
        for r in runs:
            sysname = names.get(r["system"]) or f"#{r['system']}"
            fate = fates.get((r["system"], r["body_id"], r["species"])) if r["done_ts"] else None
            st = fate[0] if fate else organic_state(self.db, r["done_ts"]) or "in progress"
            factor = 5 if r["was_footfalled"] == 0 else 1
            base = outrider.bio.species_value(r["species_name"]) if outrider.bio and r["species_name"] else None
            value = base * factor if base else None
            body = short_name(sysname, r["body_name"]) if r["body_name"] else f"body #{r['body_id']}"
            rows.append({"ts": r["done_ts"] or r["ts"], "system": {"id": str(r["system"]), "name": sysname},
                         "body": body, "genus": r["genus_name"], "species": r["species_name"],
                         "variant": r["variant_name"], "samples": r["samples"], "state": st,
                         "value": value, "factor": factor,
                         "sold_ts": fate[1] if fate and st == "sold" else None})
            counts[st] += 1
            totals[st] += value or 0
        return {"days": days, "rows": rows, "totals": totals, "counts": counts,
                "codex": [{"ts": c["ts"], "name": c["name"], "category": c["category"], "subcategory": c["subcategory"],
                           "region": c["region"], "new": bool(c["is_new"]), "voucher": c["voucher"],
                           "system": {"id": str(c["system"]), "name": c["system_name"] or names.get(c["system"])}
                           if c["system"] else None} for c in codex]}

    def _unsold_rows(self):
        args = argparse.Namespace(commander=None, since=None, ignore_deaths=False, bonus_rate=None,
                                  efficiency_bonus=False, no_odyssey=False, top=0)
        return outrider.unsold.analyse(outrider.unsold.read_events(LIVE_DIRS + LEGACY_DIRS), args)["exploration"]["rows"]

    def export_rows(self, what):
        """Rows for the export endpoint: (columns, rows)."""
        if what == "bookmarks":
            rows = [dict(r) for r in self.db.execute("SELECT * FROM bookmarks ORDER BY created_ts")]
            return ["id64", "name", "x", "y", "z", "note", "created_ts"], rows
        if what == "jumps":
            rows = [dict(r) for r in self.db.execute("SELECT * FROM jumps ORDER BY ts")]
            return ["ts", "id64", "name", "x", "y", "z", "star_class", "kind"], rows
        if what == "trips":
            rows = [dict({k: v for k, v in t.items() if k not in ("losses", "x5")}, losses=len(t["losses"]),
                         lost_value=sum(l["value"] + l["bio_value"] for l in t["losses"]),
                         lost_bio=sum(l["bio_value"] for l in t["losses"]),
                         **{f"x5_{k}": (t.get("x5") or {}).get(k) for k in ("sold", "predicted", "matched")})
                    for t in self.ledger()["trips"]]
            return ["start", "end", "days", "jumps", "ly", "systems", "firsts", "bodies_first", "mapped", "footfalls",
                    "samples", "codex_new", "paid_carto", "paid_bio", "paid", "estimate", "estimate_bio", "hours", "per_hour",
                    "per_jump", "per_ly", "first_rate", "losses", "lost_value", "lost_bio", "x5_sold", "x5_predicted",
                    "x5_matched"], rows
        if what == "route":   # every jump with what it found: for write-ups and maps
            rows, prev = [], None
            firsts = {r[0]: r[1] for r in self.db.execute(
                "SELECT system, count(*) FROM own_firsts WHERE was_discovered = 0 GROUP BY system")}
            mapped = {r[0]: r[1] for r in self.db.execute("SELECT system, count(*) FROM own_mapped GROUP BY system")}
            samples = {r[0]: r[1] for r in self.db.execute(
                "SELECT system, count(*) FROM own_organic WHERE done_ts IS NOT NULL GROUP BY system")}
            for r in self.db.execute("SELECT ts, id64, name, x, y, z, star_class, kind FROM jumps ORDER BY ts"):
                r = dict(r)
                # a Location row (login, respawn) is no jump; the jump after it starts from there
                r["ly"] = round(dist(prev, r), 2) if prev and r["kind"] != "Location" else None
                r.update(bodies_first=firsts.get(r["id64"], 0), mapped=mapped.get(r["id64"], 0), samples=samples.get(r["id64"], 0))
                rows.append(r)
                prev = r
            return ["ts", "id64", "name", "x", "y", "z", "star_class", "kind", "ly", "bodies_first", "mapped", "samples"], rows
        if what == "organics":
            rows = []
            for r in self.organics(3650)["rows"]:
                rows.append(dict(r, system=r["system"]["name"], system_id=r["system"]["id"]))
            return ["ts", "system", "system_id", "body", "genus", "species", "variant", "samples", "state",
                    "value", "factor", "sold_ts"], rows
        if what == "codex":
            rows = [dict(r) for r in self.db.execute("SELECT * FROM codex ORDER BY ts")]
            return ["ts", "entry_id", "name", "category", "subcategory", "region", "system", "system_name",
                    "body_id", "is_new", "new_traits", "voucher"], rows
        if what == "firsts":
            rows = []
            for r in self.db.execute(
                    "SELECT DISTINCT f.system AS id64, v.name, v.x, v.y, v.z FROM own_firsts f "
                    "JOIN visits v ON v.id64 = f.system ORDER BY v.name"):
                f = own_firsts(self.db, r["id64"], r["name"])
                if not f:
                    continue
                rows.append({"id64": r["id64"], "name": r["name"], "x": r["x"], "y": r["y"], "z": r["z"],
                             "system_first_discovered": int(bool(f["system"])), "system_state": f["system_state"],
                             "system_state_ts": f["system_ts"], "bodies_first_discovered": f["bodies"],
                             "bodies_sold": f["bodies_by"]["sold"], "bodies_unsold": f["bodies_by"]["unsold"],
                             "bodies_lost": f["bodies_by"]["lost"], "first_mapped": f["mapped"],
                             "first_footfalls": f["footfall"]})
            return ["id64", "name", "x", "y", "z", "system_first_discovered", "system_state", "system_state_ts",
                    "bodies_first_discovered", "bodies_sold", "bodies_unsold", "bodies_lost", "first_mapped",
                    "first_footfalls"], rows
        if what == "unsold" and outrider.unsold:
            rows = self._unsold_rows()
            return ["system", "body", "type", "first_discovered", "first_mapped", "mapped", "efficient", "value"], rows
        return None, None

    # ---- bookmarks ----

    def bookmarks(self):
        pos = self.journals.pos
        out = []
        for b in self.db.execute("SELECT * FROM bookmarks"):
            out.append({"id": str(b["id64"]), "name": b["name"], "note": b["note"] or "",
                        "created": b["created_ts"],
                        "distance": round(dist(pos, b), 2) if pos else None})
        return out

    def locate(self, id64):
        """Name and coordinates for a system, from wherever we know it."""
        if id64 in self.bases:
            b = self.bases[id64][1]
            return b["name"], b["x"], b["y"], b["z"]
        if self.searcher and id64 in self.searcher.found:
            return self.searcher.found[id64]
        for table in ("visits", "route_systems"):
            r = self.db.execute(f"SELECT name, x, y, z FROM {table} WHERE id64=?", (id64,)).fetchone()
            if r:
                return tuple(r)
        r = self.db.execute("SELECT summary FROM spansh_systems WHERE id64=?", (id64,)).fetchone()
        if r:
            b = json.loads(r["summary"])
            return b["name"], b["x"], b["y"], b["z"]
        # a bookmark keeps its own name and position: one made from an online search result or EDSM's list
        # (neither is cached) must still be found after a restart or once you have moved away
        r = self.db.execute("SELECT name, x, y, z FROM bookmarks WHERE id64=?", (id64,)).fetchone()
        if r:
            return tuple(r)
        return None

    def find_local(self, name):
        """(id64, name, x, y, z, source) of a system known here by name (any case), or None. Checked in the order
        the answers are most trusted: your visits, your bookmarks, Spansh's cached records, your route plots,
        then whatever the current neighbourhood holds."""
        for table, source in (("visits", "visited"), ("bookmarks", "bookmark")):
            r = self.db.execute(f"SELECT id64, name, x, y, z FROM {table} WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
            if r and r["x"] is not None:
                return (r["id64"], r["name"], r["x"], r["y"], r["z"], source)
        # the cached summaries are JSON: a LIKE on the name as json.dumps writes it narrows them before parsing
        # (it may also hit a body record named like the system, hence the check on the parsed name)
        pat = '%"name": ' + json.dumps(name).replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        for r in self.db.execute("SELECT id64, summary FROM spansh_systems WHERE summary LIKE ? ESCAPE '!'", (pat,)):
            b = json.loads(r["summary"])
            if (b.get("name") or "").lower() == name.lower() and b.get("x") is not None:
                return (r["id64"], b["name"], b["x"], b["y"], b["z"], "spansh")
        r = self.db.execute("SELECT id64, name, x, y, z FROM route_systems WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if r and r["x"] is not None:
            return (r["id64"], r["name"], r["x"], r["y"], r["z"], "route")
        for id64, (source, b) in list(self.bases.items()):
            if (b.get("name") or "").lower() == name.lower() and b.get("x") is not None:
                return (id64, b["name"], b["x"], b["y"], b["z"], source)
        return None

    async def find_system(self, name):
        """A system by name, for the page's name box: (status, answer). Known here first; otherwise EDSM (one
        call gives id64 and coordinates; the bodies come from Spansh by id64 when the system is opened). An
        EDSM-only hit is cached before answering, so locate() finds it after a restart: bookmarking it, making
        it the next stop and opening it all go by id64."""
        hit = self.find_local(name)
        if hit is None:
            try:
                d = await self.spansh.edsm_system(name)
            except Exception as e:  # noqa: BLE001 -- network trouble is the answer, not a crash
                return 502, {"error": f"EDSM lookup failed ({type(e).__name__}); try again"}
            if d is None:
                return 404, {"error": f"No system called {name!r} is known here or to EDSM."}
            c = d.get("coords") or {}
            if not d.get("id64") or c.get("x") is None:
                return 404, {"error": f"EDSM knows {d.get('name') or name} but not where it is."}
            id64 = int(d["id64"])
            # kept unless a table locate() reads already has it (searcher.found is not one: the next search replaces it)
            if not any(self.db.execute(f"SELECT 1 FROM {t} WHERE id64 = ?", (id64,)).fetchone()
                       for t in ("visits", "route_systems", "spansh_systems", "bookmarks")):
                self.spansh.store(id64, None, base_from_edsm(d))
                # stale on purpose: opening it fetches Spansh's bodies at once instead of trusting this for a day
                self.db.execute("UPDATE spansh_systems SET fetched_ts = 1 WHERE id64 = ?", (id64,))
                self.db.commit()
            hit = (id64, d["name"], c["x"], c["y"], c["z"], "edsm")
        id64, sname, x, y, z, source = hit
        v = self.db.execute("SELECT first_ts, last_ts, count FROM visits WHERE id64 = ?", (id64,)).fetchone()
        pos, ns = self.journals.pos, meta_get(self.db, "next_stop")
        return 200, {"id": str(id64), "name": sname, "x": x, "y": y, "z": z, "source": source,
                     "distance": round(dist(pos, {"x": x, "y": y, "z": z}), 2) if pos and pos.get("x") is not None else None,
                     "visited": {"first_ts": v["first_ts"], "last_ts": v["last_ts"], "count": v["count"]} if v else None,
                     "bookmarked": bool(self.db.execute("SELECT 1 FROM bookmarks WHERE id64 = ?", (id64,)).fetchone()),
                     "next_stop": bool(ns and ns.get("id64") == id64)}

    def set_bookmark(self, id64, note):
        existing = self.db.execute("SELECT created_ts FROM bookmarks WHERE id64=?", (id64,)).fetchone()
        where = self.locate(id64)
        if not where:
            return False
        created = existing["created_ts"] if existing else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.db.execute("INSERT OR REPLACE INTO bookmarks VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (id64, *where, note, created))
        self.db.commit()
        self.bump()
        return True

    def remove_bookmark(self, id64):
        self.db.execute("DELETE FROM bookmarks WHERE id64=?", (id64,))
        self.db.commit()
        self.bump()

    def system_value(self, id64, name, records, star, ctx=None):
        """Credits from a system: what selling now would pay for data you hold from it, and the
        most it could pay once everything there is scanned, mapped and sampled.

        Cartographics use the same formula as the unsold estimate for every body (first-discovery and
        first-mapping bonuses from your own scans; Spansh dump fields for bodies you have not
        scanned), through carto_values, the rules Here uses too. Exobiology pays x5 on a body nobody had set foot on when you scanned it (or
        where you took first footfall); a body you have not scanned counts at x1, since its
        footfall state is unknown.
        """
        own_ids = {short_name(name, r["name"]): r["body_id"] for r in
                   self.db.execute("SELECT body_id, name FROM own_bodies WHERE system=?", (id64,))}
        firsts = {r["body_id"]: r for r in self.db.execute(
            """SELECT f.body_id, f.was_discovered, f.was_mapped, f.was_footfalled, f.bio_x5, f.first_ts, m.ts AS mapped_ts,
                      m.first_ts AS map_first_ts FROM own_firsts f LEFT JOIN own_mapped m ON m.system = f.system AND m.body_id = f.body_id
               WHERE f.system = ?""", (id64,))}
        genera = {}  # body_id -> genera your DSS found there (limits the guess to what is really present)
        for r in self.db.execute("SELECT body_id, genus_name FROM own_genera WHERE system=?", (id64,)):
            genera.setdefault(r["body_id"], []).append(r["genus_name"])
        done = {}   # body_id -> {genus: species value} for finished samples (not lost): aboard or sold
        aboard = {}  # body_id -> {genus: species value} for those still on board (not yet sold)
        for r in self.db.execute("SELECT body_id, species, genus_name, species_name, done_ts FROM own_organic "
                                 "WHERE system=? AND done_ts IS NOT NULL", (id64,)):
            st = organic_state(self.db, r["done_ts"], (id64, r["body_id"], r["species"]))
            if st != "lost":
                v = (outrider.bio.species_value(r["species_name"]) if outrider.bio else 0) or 0
                done.setdefault(r["body_id"], {})[r["genus_name"]] = v
                if st == "aboard":
                    aboard.setdefault(r["body_id"], {})[r["genus_name"]] = v
        now_c = self.system_values.get(name, 0)   # on board: the unsold estimate's own figure for this system
        rem_c = now_b = rem_b = 0
        judge = pickup_judge(self.db, name)
        latest = {r["body_id"]: r["ts"] for r in self.db.execute("SELECT body_id, ts FROM own_bodies WHERE system=?", (id64,))}
        for r in records:
            bid = own_ids.get(r["name"])
            f = firsts.get(bid) if bid is not None else None
            scan_state = judge(latest[bid], f and f["first_ts"])[0] if bid in latest else None
            map_state = judge(f["mapped_ts"], f["map_first_ts"])[0] if f and f["mapped_ts"] else None
            rem_c += carto_values(r, bid is not None, f, scan_state, map_state)["left"]   # same rules as Here
            if r.get("bio") or r.get("genera"):
                factor = 5 if f and f["bio_x5"] == 1 else 1
                got = done.get(bid, {}) if bid is not None else {}
                now_b += sum((aboard.get(bid) or {}).values()) * factor
                known = (genera.get(bid) if bid is not None else None) or r.get("genera") or None
                rem_b += sum((g.get("value") or 0) for g in bio_left_groups(r, star, known, ctx, got)) * factor
        return {"value_now": int(now_c + now_b), "value_max": int(now_c + now_b + rem_c + rem_b),
                "value_parts": {"carto_now": int(now_c), "bio_now": int(now_b), "carto_left": int(rem_c), "bio_left": int(rem_b)}}

    def row(self, id64):
        """Page row for a system: its Spansh base merged with your own scans."""
        source, base = self.bases[id64]
        own, hotspots, own_count = own_data(self.db, id64, base["name"])
        records = merge_records(base.get("records") or [], own, hotspots)
        counts = [c for c in (base.get("body_count"), own_count) if c]
        star_row = self.db.execute("SELECT star_class FROM star_classes WHERE id64=?", (id64,)).fetchone()
        star = star_row["star_class"] if star_row else None
        body_count = max(counts) if counts else None
        ctx = bio_context(base["name"], records, base.get("x"), base.get("y"), base.get("z"), star, body_count)
        own_genera = {}
        for r_ in self.db.execute("SELECT b.name, g.genus_name FROM own_genera g JOIN own_bodies b "
                                  "ON b.system = g.system AND b.body_id = g.body_id WHERE g.system=?", (id64,)):
            own_genera.setdefault(short_name(base["name"], r_["name"]), []).append(r_["genus_name"])
        s = summarise(records, body_count, star, ctx, own_genera)
        s.update(id64=id64, id=str(id64), name=base["name"], source=source, in_spansh=source == "spansh",
                 visited=id64 in self.visited, distance=round(dist(self.center, base), 2),
                 own_scans=len(own), firsts=own_firsts(self.db, id64, base["name"]),
                 mapped=self.db.execute(
                     """SELECT count(*) FROM own_firsts f LEFT JOIN own_mapped m
                          ON m.system = f.system AND m.body_id = f.body_id
                        WHERE f.system = ? AND (f.was_mapped = 1 OR m.ts IS NOT NULL)""",
                     (id64,)).fetchone()[0])
        s.update(self.system_value(id64, base["name"], records, star, ctx))
        s["no_dump"] = bool(base.get("no_dump"))   # Spansh has no body details: the popup stops saying "loading"
        s["phenomena"] = [dict(r) for r in self.db.execute("SELECT kind, reached_ts FROM phenomena WHERE system=?", (id64,))]
        raws = {short_name(base["name"], r_["name"]): json.loads(r_["raw"]) for r_ in self.db.execute(
            "SELECT name, raw FROM own_bodies WHERE system=? AND raw IS NOT NULL", (id64,))}
        cur = system_curiosities(base["name"], records, raws)
        s["curiosity_list"] = [{"body": bn, "tag": t, "why": w} for bn, lst in cur.items() for t, w in lst]
        s["curiosities"] = len(s["curiosity_list"])
        if not s["bodies_known"]:
            s["status"] = "unreported" if source == "route" else "no bodies"
        elif s["body_count"] is None or s["bodies_known"] < s["body_count"]:
            s["status"] = "partial"
        else:
            s["status"] = "explored"
        if s["main_star"]:
            s["main_class"] = star_short(s["main_star"])
        else:
            # Nothing scanned: fall back to a star class seen in your own FSDTarget/NavRoute.
            row = self.db.execute("SELECT star_class FROM star_classes WHERE id64=?",
                                  (id64,)).fetchone()
            sc = (row["star_class"] if row else None) or base.get("star_class")
            s.update(main_star=sc, main_class=sc, main_scoopable=class_scoopable(sc) if sc else None)
        return s

    def set_row(self, id64):
        self.systems[id64] = self.row(id64)

    def safe_row(self, id64):
        """set_row, but one bad system must not stall the others: the traceback is printed once, the row is
        left out and tried again next tick (as a plain rebuild), and the error shows on the page meanwhile.
        True when the row was built."""
        try:
            self.set_row(id64)
        except Exception as e:
            if id64 not in self.row_failed:   # the traceback once, not every retry
                import traceback
                traceback.print_exc()
            self.row_failed.add(id64)
            self.value_dirty.add(id64)
            self.tail_error = f"{type(e).__name__} while updating {id64}: {e}"
            return False
        self.row_failed.discard(id64)
        return True

    def maybe_classify_target(self):
        t = self.journals.target
        key = t and (t["id64"], t["ts"])
        if key == self.target_key:
            return
        self.target_key = key
        if not t:
            if self.target:
                self.last_target = self.target
            elif self.target_task and not self.target_task.done():
                self.last_target = None   # classify_target will fill it in when the lookup lands
            self.target = None
            self.bump()
            return
        # Keep a reference: asyncio only holds tasks weakly.
        self.target_task = asyncio.create_task(self.classify_target(t, key))

    async def classify_target(self, t, key):
        """Decide which sound a newly targeted system gets.

        fanfare  Spansh has never heard of it: a brand-new discovery
        upbeat   known, but not fully scanned
        thud     you've been there, or every body is already known
        """
        id64 = t["id64"]
        source = "spansh"
        known = count = None   # how many of its bodies Spansh knows, of how many (Now's target line: "3/12 known")
        visited = self.db.execute("SELECT 1 FROM visits WHERE id64=?", (id64,)).fetchone()
        if id64 in self.systems:
            known, count = self.systems[id64].get("bodies_known"), self.systems[id64].get("body_count")
        if visited:
            status = "visited"
        elif id64 in self.systems and self.systems[id64]["source"] == "spansh":
            status = self.systems[id64]["status"]
        else:
            try:
                dump = await self.spansh.lookup(id64)
            except Exception:
                dump = False
            if dump is None or dump is False:
                # Spansh doesn't have it (or is down): EDSM is a separate database with its
                # own reporters, so it may still know the system exists.
                try:
                    e_sys = await self.spansh.edsm_system(t["name"])
                except Exception:
                    e_sys = False
                if e_sys:
                    status, source = "no bodies", "edsm"
                elif dump is None and e_sys is None:
                    status = "unreported"
                else:
                    status = "lookup failed"
            else:
                system = dump.get("system") or {}
                known = sum(1 for b in system.get("bodies") or [] if b.get("type") in ("Star", "Planet"))
                count = system.get("bodyCount")
                status = ("no bodies" if not known
                          else "explored" if count and known >= count else "partial")
        # Spansh unreachable and EDSM answered: no verdict on what Spansh knew (it was "partial" for good)
        self.target_verdicts[id64] = "spansh unreachable" if source == "edsm" and dump is False else status
        while len(self.target_verdicts) > 50:
            self.target_verdicts.pop(next(iter(self.target_verdicts)))
        if key != self.target_key:
            # A newer target, or we already arrived: no sound, but keep the verdict so the
            # arrival star can still be checked against it.
            pos = self.journals.pos
            if pos and pos["id64"] == id64 and self.last_target is None:
                self.last_target = dict(t, status=status, source=source)
                self.reconcile_arrival()
            return
        sound = {"unreported": "fanfare", "no bodies": "upbeat", "partial": "upbeat",
                 "explored": "thud", "visited": "thud"}.get(status)
        self.target_seq += 1
        self.target = dict(t, status=status, sound=sound, seq=self.target_seq,
                           fresh=key != self.startup_target_key, source=source, known=known, count=count, edsm=None,
                           leaving=self.leaving_summary(self.journals.pos["id64"]) if self.journals.pos else None)
        self.bump()
        # EDSM beside Spansh (SystemStatusOverlay's two columns): its own reporters may know more bodies. After the
        # sound, so it never delays it; one request, and only for a system Spansh knows (else EDSM was asked above)
        if source == "spansh" and status in ("no bodies", "partial", "explored"):
            try:
                e = await self.spansh.edsm_bodies(t["name"])
            except Exception:
                return
            if key == self.target_key and self.target and self.target.get("id64") == id64:
                self.target = dict(self.target, edsm=e)
                self.bump()

    def maybe_refresh(self):
        pos = self.journals.pos
        if not pos:
            return
        retry = False
        if self.center and self.center["id64"] == pos["id64"]:
            if not (self.retry_at and time.time() >= self.retry_at
                    and (not self.refresh_task or self.refresh_task.done())):
                return
            retry = True
        self.center = pos
        self.retry_at = None
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()
        self.refresh_task = asyncio.create_task(self.refresh(pos, retry))

    def set_radius(self, r):
        """Change the Nearby sphere from the page: remembered in the database and fetched at once."""
        if r == self.radius:
            return
        self.radius = r
        meta_set(self.db, "radius_choice", r)
        self.db.commit()
        self.center = None          # forces a fresh Spansh sphere around where you are
        self.maybe_refresh()
        self.bump()

    def schedule_retry(self):
        delay = self.retry_backoff
        self.retry_at = time.time() + delay
        self.retry_backoff = min(self.retry_backoff * 2, 300)
        return int(delay)

    def near(self, table, pos, r):
        return self.db.execute(
            f"SELECT * FROM {table} WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND z BETWEEN ? AND ?",
            (pos["x"] - r, pos["x"] + r, pos["y"] - r, pos["y"] + r, pos["z"] - r, pos["z"] + r))

    async def refresh(self, pos, retry=False):
        try:
            await self._refresh(pos, retry)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # anything else: say so on the page and try again later
            import traceback
            traceback.print_exc()
            delay = self.schedule_retry()
            self.status = f"refresh failed: {type(e).__name__}: {e} — retrying in {delay}s"
            self.bump()

    def dump_failed(self, id64, e):
        """A body-detail fetch failed: retry it later unless it has failed DUMP_MAX_TRIES times."""
        n = self.dump_tries[id64] = self.dump_tries.get(id64, 0) + 1
        if n == 1 or n == DUMP_MAX_TRIES:   # say why once, and again when giving up (not every retry)
            name = self.bases.get(id64, (None, {}))[1].get("name", id64)
            print(f"body details for {name} failed ({type(e).__name__}: {e})"
                  + (" - giving up until you move" if n >= DUMP_MAX_TRIES else ""), file=sys.stderr)
        if n < DUMP_MAX_TRIES:
            self.failed_dumps.add(id64)

    async def retry_dumps(self, pos):
        """Spansh's search worked but some body-detail fetches failed: fetch just those again."""
        ids = [i for i in self.failed_dumps if i in self.bases and self.bases[i][0] == "spansh"]
        self.failed_dumps = set()
        self.status = f"fetching body details again for {len(ids)} systems…"
        self.bump()
        failed = 0
        for id64 in ids:
            _, base = self.bases[id64]
            try:
                base = await self.spansh.full_records(id64, self.dump_updated.get(id64), base)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed += 1
                self.dump_failed(id64, e)
                continue
            self.bases[id64] = ("spansh", base)
            self.safe_row(id64)
            self.bump()
        if failed and self.failed_dumps:
            self.status = f"ok ({failed} body lookups failed again, retrying in {self.schedule_retry()}s)"
        elif failed:   # every failure has used up its tries: stop retrying, but say so
            self.status = f"ok ({failed} body lookups failed; giving up on them until you move)"
        else:
            self.retry_backoff = 30
            self.status = "ok"
        self.bump()

    async def _refresh(self, pos, retry=False):
        r = self.radius
        self.visited = {row[0] for row in self.db.execute("SELECT id64 FROM visits")}
        if retry and self.failed_dumps and self.status.startswith("ok ("):
            return await self.retry_dumps(pos)
        if not retry:
            self.bases, self.systems = {}, {}
            # what the local cache already holds around the new position shows at once, while the search runs (a
            # short hop is mostly cached: no blank "loading…" for it; review S6). The answer replaces it row by row.
            for row in self.near("spansh_systems", pos, r):
                b = json.loads(row["summary"])
                if b.get("v") == CACHE_VERSION and dist(pos, b) <= r:
                    self.bases[row["id64"]] = (cached_source(b), b)
            for id64 in self.bases:
                self.safe_row(id64)
        self.status = (f"asking Spansh again about systems near {pos['name']}…" if retry
                       else f"asking Spansh about systems near {pos['name']}…")
        self.bump()
        edsm, spansh_failed = [], None
        try:
            results = await self.spansh.sphere(pos, r)
            # a dense region (near the bubble or Colonia): Spansh has more than we fetch, so the list is
            # only complete out to the last system returned; say so rather than call it every system
            self.sphere_cut = round(results[-1]["distance"], 1) \
                if len(results) >= SPANSH_PAGE * SPANSH_MAX_PAGES and results else None
        except Exception as e:  # network trouble shouldn't kill the server
            spansh_failed = e
            results = []
            self.sphere_cut = None   # the last good search's limit was for another position or radius
            try:  # second opinion: EDSM's list has no body data but says what exists
                edsm = await self.spansh.edsm_sphere(pos, r)
            except Exception:
                pass
        if retry:
            self.bases, self.systems = {}, {}
        if spansh_failed:
            # What we already know about this neighbourhood is better than EDSM's bare list.
            cached_n = 0
            for row in self.near("spansh_systems", pos, r):
                b = json.loads(row["summary"])
                if b.get("v") == CACHE_VERSION and dist(pos, b) <= r:
                    # Spansh's own record, from an earlier search: still Spansh's (not "not in Spansh", F27)
                    self.bases[row["id64"]] = (cached_source(b), b)
                    cached_n += 1
            delay = self.schedule_retry()
            self.status = (f"Spansh search failed ({spansh_failed}); showing {cached_n} cached systems"
                           f"{(' plus EDSM’s list' + (f' (to {EDSM_SPHERE_MAX} ly, its limit)' if r > EDSM_SPHERE_MAX else '')) if edsm else ''}"
                           f" — retrying in {delay}s")
        for d in edsm:
            if d.get("id64") and d.get("coords") and d["id64"] not in self.bases:
                self.bases[d["id64"]] = ("edsm", base_from_edsm(d))

        need_dump = []
        for s in results:
            if dist(pos, s) > r:
                continue
            id64 = s["id64"]
            base = base_from_search(s)
            cached_at, cached = self.spansh.cached(id64)
            age = self.spansh.fetched_age(id64) if cached else None
            # current: fetched for this updated_at, or fetched on demand (no updated_at) within the day
            current = cached and (cached_at == s.get("updated_at")
                                  or (cached_at is None and age is not None and age < ON_DEMAND_MAX_AGE))
            if current and cached.get("no_dump") and base["records"] and (age is None or age >= NO_DUMP_RETRY):
                # the search lists bodies but the dump said 404: an index lagging, a proxy's 404. Not for good:
                # asked again once NO_DUMP_RETRY has passed (every refresh before that reuses the answer)
                current = False
            if current:
                if not (cached.get("no_dump") and len(cached.get("records") or []) < len(base["records"])):
                    base = cached   # (a no-dump answer with fewer bodies than the search lists now: the search's, F29)
            elif base["records"]:
                need_dump.append((id64, s.get("updated_at"), base))
                # a full dump cached for an older updated_at shows meanwhile, and stays if the new one fails (F28)
                if cached and not cached.get("no_dump") and len(cached.get("records") or []) >= len(base["records"]):
                    base = cached
            else:
                self.spansh.store(id64, s.get("updated_at"), base)
            self.bases[id64] = ("spansh", base)

        # Systems you've been to that Spansh doesn't have (e.g. your own fresh discoveries).
        for v in self.near("visits", pos, r):
            if v["id64"] not in self.bases and dist(pos, v) <= r:
                self.bases[v["id64"]] = ("own", {"name": v["name"], "x": v["x"], "y": v["y"],
                                                 "z": v["z"], "body_count": None, "records": []})
        # Systems from your own route plots that nobody has reported.
        for rs in self.near("route_systems", pos, r):
            if rs["id64"] not in self.bases and dist(pos, rs) <= r:
                self.bases[rs["id64"]] = ("route", {"name": rs["name"], "x": rs["x"], "y": rs["y"],
                                                    "z": rs["z"], "body_count": None, "records": [],
                                                    "star_class": rs["star_class"]})
        for id64 in self.bases:
            self.safe_row(id64)

        if not spansh_failed:
            self.status = (f"fetching body details for {len(need_dump)} systems…"
                           if need_dump else "ok")
            if not need_dump:
                self.retry_backoff = 30
        self.bump()

        # Nearest first, so the rows you care about fill in soonest.
        need_dump.sort(key=lambda t: self.systems.get(t[0], {}).get("distance", math.inf))   # a failed row: last
        failed = 0
        self.failed_dumps = set()
        self.dump_updated = {i: u for i, u, _ in need_dump}   # Spansh's updated_at, kept for retries
        self.dump_tries = {}

        async def one(id64, updated_at, base):
            nonlocal failed
            try:
                base = await self.spansh.full_records(id64, updated_at, base)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed += 1
                self.dump_failed(id64, e)
                return
            self.bases[id64] = ("spansh", base)
            self.safe_row(id64)
            self.bump()

        await asyncio.gather(*(one(*t) for t in need_dump))
        if need_dump:
            if failed and self.failed_dumps:
                self.status = f"ok ({failed} body lookups failed, retrying in {self.schedule_retry()}s)"
            elif failed:
                self.status = f"ok ({failed} body lookups failed; giving up on them until you move)"
            else:
                self.retry_backoff = 30
                self.status = "ok"
            self.bump()

    def reconcile_arrival(self):
        """Check the sound we played for a target against the arrival star's WasDiscovered."""
        scan, t, pos = self.journals.arrival_scan, self.last_target, self.journals.pos
        if not (scan and pos) or pos["id64"] != scan["id64"]:
            return
        # one arrival per visit (pos ts is the arrival's, kept through a relog): a second Scan of the arrival star (a
        # Detailed one after the honk, a nav beacon's) must not announce it again (review F30)
        if self.arrival and (self.arrival["ts"] == scan["ts"] or (
                self.arrival.get("visit") == pos.get("ts") and self.arrival["id64"] == str(scan["id64"]))):
            # Already reconciled, unless the target's lookup was slower than the jump: its verdict lands after
            # the arrival scan. Fill it in so the page can say "Spansh just hadn't heard of it", but in place
            # (same seq, no sound): nothing was announced when you targeted it, so there is no call to correct.
            late = self.target_verdicts.get(scan["id64"])
            if self.arrival["announced"] is None and late and late != "lookup failed":
                self.arrival.update(announced=late, wrong=(late == "unreported") != self.arrival["undiscovered"])
                self.bump()
            return
        # what was announced when this system was targeted (a plotted route has already targeted the next
        # hop by now, so the current target is no guide); a jump nobody announced still gets its verdict
        t = t if t and t["id64"] == scan["id64"] else None
        announced = self.target_verdicts.get(scan["id64"]) or (t or {}).get("status")
        if announced == "lookup failed":
            announced = None   # no sound and no claim was made: nothing to correct ("actually undiscovered")
        expected_new = announced == "unreported"
        actually_new = not scan["was_discovered"]
        # a new seq first (the streak's cache keys on it); the arrival is only kept once its verdict and streak
        # are in: if either fails (the database busy during a backup), the next tick reconciles it again
        self.arrival_seq += 1
        arrival = {"name": pos.get("name") or (t or {}).get("name"), "id64": str(scan["id64"]),
                        "ts": scan["ts"], "seq": self.arrival_seq, "visit": pos.get("ts"),
                        "announced": announced, "undiscovered": actually_new,
                        # your own unsold discovery still reads as undiscovered: only the first visit is news
                        "first_visit": self.visit_count(scan["id64"]) <= 1,
                        "wrong": bool(announced) and expected_new != actually_new,
                        # sounds belong to targeting: on arrival only a wrong call is corrected (a thud for
                        # a fanfare that was not deserved, the fanfare for a surprise); the voice does the rest
                        "sound": None if not announced
                                 else "thud" if expected_new and not actually_new
                                 else "fanfare" if actually_new and not expected_new
                                 and self.visit_count(scan["id64"]) <= 1 else None}
        # the streak strip's colour for this arrival is decided now and kept; the runs let the page say
        # "ten known systems in a row" or "fifth undiscovered system in a row" once per streak
        arrival["verdict"] = self.fix_verdict(scan)
        st = self.streak()
        arrival["streak"] = {"new": st["run_new"], "known": st["run_known"]} if st else None
        self.arrival = arrival
        self.bump()

    def maybe_brief(self, now=None):
        """The arrival briefing when no honk came: BRIEF_WAIT s after a live hyperspace arrival, from Spansh and
        what you already hold (auto honk off, or skip_honked on a revisit). Waits while an auto honk is working
        on that arrival; a honk later on the same visit adds no second briefing."""
        j, now = self.journals, time.time() if now is None else now
        a = j.jump_arrival
        if not a or j.brief_key == (a["id64"], a["ts"]) or self._honk_running is a:
            return
        try:
            age = now - ts_seconds(a["ts"])
        except (TypeError, ValueError):
            return
        if age < BRIEF_WAIT:
            return
        j.brief_key = (a["id64"], a["ts"])
        # the cutoff runs from the arrival, or from when an auto honk on it ended without a scan (it may wait
        # up to AUTOHONK_WAIT_MAX s for the cockpit): still here, the briefing is still news
        done = self._honk_done
        since = now - done[1] if done and done[0] is a else age
        if since > BRIEF_WAIT + AUTOHONK_MAX_AGE or not j.pos or j.pos["id64"] != a["id64"]:
            return   # a journal being caught up on, or already gone again: nothing to say
        j.moment("arrival_brief", iso_ts(now), system=a["id64"], source="spansh")
        self.bump()

    # ---- live call-outs from Status.json (polled every tick, never from old journals) ----
    def watch_status(self, now):
        """The end of a fuel scoop ("tank full", "scooping stopped at 64 percent"), and the FSS closed with
        bodies still hidden."""
        j = self.journals
        st = j.status_json or {}
        end = self.scoop.update(st, (j.ship or {}).get("fuel_main"), now, j.last_start_jump)
        if end:
            jumps = self.fuel_summary().get("jumps_max") if end["full"] else None
            j.moment("scoop_end", st.get("ts") or iso_ts(now), jumps=jumps, **end)
            self.bump()
        self.watch_fss(now)
        self.watch_tunnel(now)
        if self.watch_surface(now):
            self.bump()

    def watch_tunnel(self, now):
        """Into the hyperspace tunnel: Status.json's FSD-jump flag coming on after a hyperspace StartJump (its
        fsd_charge moment, within a minute). A "hyperspace" moment then lets the page say the jump line now, in the
        quiet of the tunnel, not over the game's own countdown call (review S14). Once per charge."""
        st = self.journals.status_json or {}
        on = bool(st.get("live") and (st.get("flags") or 0) & FLAG_FSD_JUMP)
        was, self._in_tunnel = self._in_tunnel, on
        if not on or was:
            return
        m = next((x for x in reversed(self.journals.moments) if x["kind"] == "fsd_charge"), None)
        if not m or m["seq"] == self._tunnel_for:
            return
        try:
            if not 0 <= now - ts_seconds(m["ts"]) <= 60:
                return
        except (TypeError, ValueError):
            return
        self._tunnel_for = m["seq"]
        self.journals.moment("hyperspace", st.get("ts") or iso_ts(now), system=m.get("system"), charge=m["seq"])
        self.bump()

    def watch_fss(self, now):
        """GuiFocus 9 (the FSS) closing: FSS_SETTLE s later (the journal's last Scan lines may lag the status
        file), a system you honked with bodies still unresolved says so, once per visit."""
        st, pos = self.journals.status_json or {}, self.journals.pos
        focus = (st.get("gui_focus") or 0) if st.get("live") else None
        prev, self._fss_focus = self._fss_focus, focus
        if prev == 9 and focus is not None and focus != 9 and pos:
            self._fss_closed = (pos["id64"], pos["ts"], now)
        c = self._fss_closed
        if not c or now - c[2] < FSS_SETTLE:
            return
        self._fss_closed = None
        if not pos or pos["id64"] != c[0] or self._fss_warned == c[:2]:
            return
        l = self.leaving_summary(c[0])
        if l and l["honked"] and not l["all_found"] and (l["unscanned"] or 0) > 0:
            self._fss_warned = c[:2]
            self.journals.moment("fss_unfinished", iso_ts(now), system=c[0], left=l["unscanned"])
            self.journals.flush_jumponium(iso_ts(now), c[0])
            self.bump()

    # ---- auto honk ----
    def autohonk_info(self):
        h = self.honker
        return {"available": bool(h and h.available), "enabled": bool(self.autohonk["enabled"] and h and h.ready),
                "wanted": bool(self.autohonk["enabled"]), "status": h.status if h else "not started",
                "key": self.autohonk["key"], "hold": self.autohonk["hold"], "announce": bool(self.autohonk.get("announce", True)),
                "pressing": (h.combo()[1] if h and h.available else None), "test": self.honk_test,
                "groups": self.honk_groups()}

    # the fire groups auto honk has worked and missed in, per ship (meta honk_groups: {ShipID: {good, bad}}),
    # learned from its own presses only (a manual or FSS honk does not say which trigger or group it used)
    def honk_groups(self, ship_id=None):
        """The current (or given) ship's record, or None."""
        sid = (self.journals.ship or {}).get("ship_id") if ship_id is None else ship_id
        return (meta_get(self.db, "honk_groups") or {}).get(str(sid)) if sid is not None else None

    def note_honk_group(self, ship_id, group, ok):
        if ship_id is None or not group:
            return
        groups = meta_get(self.db, "honk_groups") or {}
        rec = honk_learn(groups.get(str(ship_id)), group, ok)
        if rec == groups.get(str(ship_id)):
            return
        groups[str(ship_id)] = rec
        meta_set(self.db, "honk_groups", groups)
        self.db.commit()   # now, like the toggle: a failing watcher tick must not roll it back

    def forget_honk_groups(self):
        """The auto honk section's "forget": clear the current ship's record."""
        sid = (self.journals.ship or {}).get("ship_id")
        groups = meta_get(self.db, "honk_groups") or {}
        if sid is not None and groups.pop(str(sid), None) is not None:
            meta_set(self.db, "honk_groups", groups or None)
            self.db.commit()
        self.bump()

    # ---- uploads (EDDN, EDSM) ----

    def upload_wanted(self, service):
        """The page's switch for `service` (Settings -> Uploads, the only one; off until switched on): what this
        instance means to do."""
        if self.simulate or service not in outrider.uploads.SERVICES:
            return False
        return bool(self.upload_cfg.get(service, {}).get("enabled"))

    def upload_conflict(self, service):
        """Why `service` must not send from here now although wanted: another Outrider's live lease claims it, or
        EDMC on this PC is running with its own upload of it on. None when nothing stands in the way."""
        other = (self.lease_hold or {}).get(service)
        if other:
            return f"also uploading from {other}"
        e = self.edmc or {}
        if e.get("running") and e.get(service):
            return f"EDMC on this PC sends to {service.upper()} too: switch its {service.upper()} off (or this one)"
        return None

    def upload_queueing(self, service):
        """Whether `service` queues what the journal says (the hub): wanted, never in --simulate, not while another
        uploader has it (that one sends it). A hold (a key EDSM refused) stops only the sending: what is played meanwhile
        waits in the outbox and goes once the key is fixed (the author's EDSM 203s, 2026-10-08: the held stretch was
        skipped)."""
        return self.upload_wanted(service) and self.upload_conflict(service) is None

    def upload_on(self, service):
        """Whether `service` uploads now: wanted (the page's switch, else the config), never in --simulate, not while
        another uploader has it (upload_conflict), not while it waits on the player (a key EDSM refused)."""
        if not self.upload_wanted(service) or (self.upload_status.get(service) or {}).get("held"):
            return False
        return self.upload_conflict(service) is None

    def check_upload_start(self, service, confirmed):
        """Before the page switches `service` on: None to go ahead, else (code, words). Another live lease claiming it
        refuses (worded for a read-only folder too); a folder this instance cannot write asks first, since other
        instances cannot see this one (the author's rules, 2026-10-08)."""
        self.refresh_leases()
        readonly = bool(self.lease_writable) and not any(self.lease_writable.values())
        other = next((o for o in self.lease_others.values() if service in o["services"]), None)
        if other:
            return ("other_instance", "Filesystem is read-only and another instance is set for upload" if readonly
                    else f"Already uploading from {other['host']}: switch it off there first")
        e = self.edmc or {}
        if e.get("running") and e.get(service):
            return ("edmc", f"EDMC on this PC is sending to {service.upper()}: switch its {service.upper()} off first")
        if readonly and not confirmed:
            return ("confirm_needed", "Is this the only Outrider uploading? Other instances can't see this one")
        return None

    def refresh_leases(self, edmc=...):
        """Write this instance's lease (the services it means to send) in every live journal folder it can write, and
        read the others' (and EDMC's switches on the game PC). Cheap: a few small files."""
        if self.leases is None:
            iid = meta_get(self.db, "instance_id")
            # the id belongs to this computer and this database file (its path and inode: a copy has another inode,
            # even in Docker where every container has the same name and path); a database copied or restored gets
            # its own, since two Outriders sharing one id would not see each other's leases
            host = socket.gethostname()
            where = f"{host}|{self.db_file()}|{self.db_inode()}"
            was = meta_get(self.db, "instance_where")
            valid = isinstance(iid, str) and re.fullmatch(r"[A-Za-z0-9_-]{6,40}", iid)
            if valid and was is None:   # a database from before the id was tied to its file: it keeps its id
                meta_set(self.db, "instance_where", where)
                self.db.commit()
            elif not valid or was != where:
                old, iid = iid if valid else None, secrets.token_hex(6)
                meta_set(self.db, "instance_id", iid)
                meta_set(self.db, "instance_where", where)
                self.db.commit()
                # the old id's notes on this computer were this Outrider's (a moved or restored database): gone, so
                # they are not read as another instance's. On another computer that id may still be running: kept
                if old and isinstance(was, str) and re.split(r"[|:]", was)[0] == host:
                    for d in LIVE_DIRS:
                        outrider.uploads.write_lease(d, old, None)
            self.leases = outrider.uploads.Leases(iid)
            self._lease_beat = 0
        self._lease_beat += 1
        wanted = [s for s in outrider.uploads.SERVICES if self.upload_wanted(s)]
        self._lease_wanted = wanted

        def write():
            # services: what this instance sends (an Outrider before 2026.10.19.1 holds whenever another lease names one);
            # wanted: what it is switched on for. Only the marks of what it wants: a switched-off service's mark is old,
            # and another instance switched on would start there and send that history
            # nothing claimed before the others are read: one already sending keeps its service
            sending = [] if self.lease_hold is None else [s for s in wanted if s not in self.lease_hold]
            info = {"host": socket.gethostname(), "services": sending, "wanted": wanted, "beat": self._lease_beat,
                    "version": outrider.__version__, "marks": {s: m for s, m in self.uploads_hub.marks.items() if s in wanted}}
            self.lease_writable = {d: outrider.uploads.write_lease(d, self.leases.instance, info) for d in LIVE_DIRS}
            return sending
        sending = write()
        self.lease_others = self.leases.others(LIVE_DIRS)
        # who sends each service: two Outriders switched on for it at once both held for good before (Codex F1, 2026-10-09),
        # each following the journal as if the other sent it, so that stretch was never sent
        owners = outrider.uploads.lease_owners(self.leases.instance, wanted, sending, self.lease_others)
        held_before, self.lease_hold = self.lease_hold, {s: host for s, host in owners.items() if host}
        # a service another instance was sending and this one takes over now (it stopped, or its lease went stale):
        # meanwhile this one followed the journal, moving its mark past every line as the other's. Back to where the
        # other stopped (its handover note, or a crashed one's last marks) and caught up from there, so the stretch
        # between its stop and this refresh is sent (the Fable review of 2026-10-10, #1; the outbox's UNIQUE keeps a
        # line both queued from going twice). Not at the first read (start-up is catch_up_uploads') nor for a service
        # switched off (it leaves the hold because it is not wanted)
        took = [s for s in wanted if held_before and s in held_before and s not in self.lease_hold]
        if took:
            theirs_all = outrider.uploads.lease_marks(LIVE_DIRS, self.leases.instance)
            for s in took:
                theirs, mine = theirs_all.get(s), self.uploads_hub.marks.get(s)
                if theirs and (mine is None or outrider.uploads.pos_key(theirs) < outrider.uploads.pos_key(mine)):
                    self.uploads_hub.set_mark(s, (theirs[0], theirs[1]), theirs[2] if len(theirs) > 2 else None)
                    self.uploads_hub.flush()
                    n = self.uploads_hub.catch_up(s, LIVE_DIRS, dict(self.journals.offsets))
                    if n:
                        print(f"uploads: {s}: took over from another Outrider, {n} message{'s' if n != 1 else ''} "
                              "from after it stopped queued")
            self.db.commit()
        if [s for s in wanted if s not in self.lease_hold] != sending:
            write()   # the others see the change now, not a minute later
        # EDMC on this PC: given by watch_leases (found on a worker thread: on Windows `tasklist` takes a second or two,
        # and it stalled the loop every minute), else looked up here (a switch from the page, the start)
        self.edmc = edmc if edmc is not ... else (outrider.uploads.edmc_uploads() if self.game_pc else None)

    def drop_leases(self):
        """At shutdown: this instance's leases claim nothing any more (another may take over at once), but keep its
        marks as a handover note: an instance switched on later starts where this one stopped."""
        if self.leases:
            wanted = [s for s in outrider.uploads.SERVICES if self.upload_wanted(s)]   # what it uploads as it stops
            info = {"host": socket.gethostname(), "services": [], "stopped": True, "version": outrider.__version__,
                    "marks": {s: m for s, m in self.uploads_hub.marks.items() if s in wanted}}
            for d in LIVE_DIRS:
                outrider.uploads.write_lease(d, self.leases.instance, info)

    async def watch_leases(self):
        """The leases every LEASE_EVERY_S, and once an hour the outbox's old rows (sent or dropped a week ago) pruned."""
        pruned = 0.0
        while True:
            try:
                edmc = await asyncio.get_running_loop().run_in_executor(None, outrider.uploads.edmc_uploads) \
                    if self.game_pc else None
                self.refresh_leases(edmc)
                if time.time() - pruned > 3600:
                    outrider.uploads.prune(self.db, time.time())
                    self.db.commit()
                    pruned = time.time()
            except Exception as e:   # never stop watching
                print(f"uploads: lease check failed ({type(e).__name__}: {e})", file=sys.stderr)
            await asyncio.sleep(LEASE_EVERY_S)

    def db_file(self):
        """The database's file (its real path), or "" for an in-memory one."""
        try:
            f = self.db.execute("PRAGMA database_list").fetchone()[2]
        except (sqlite3.Error, TypeError, IndexError):
            return ""
        return os.path.realpath(f) if f else ""

    def db_inode(self):
        """The database file's inode (0 for an in-memory one): a copy of the file has another."""
        try:
            return os.stat(self.db_file()).st_ino if self.db_file() else 0
        except OSError:
            return 0

    def journal_end(self):
        """Where the reader has got to in the live journals, as a mark: (file name, the byte before the next line)
        (a mark is the last line handled; the next line starts at the offset the reader has reached)."""
        live = {os.path.normpath(d) for d in LIVE_DIRS}
        ends = [outrider.uploads.position(p, o) for p, o in self.journals.offsets.items()
                if os.path.normpath(os.path.dirname(p)) in live]
        last = max(ends, key=outrider.uploads.pos_key) if ends else None   # by time: old-format names too
        return (last[0], last[1] - 1) if last else None

    def upload_start_mark(self, service):
        """Where a service switched on starts: another instance's handover mark when one is visible (it stopped
        there: no gap, nothing twice), else where the reader is now (switching on never uploads your history)."""
        theirs = outrider.uploads.lease_marks(LIVE_DIRS, self.leases.instance if self.leases else "").get(service)
        end = self.journal_end()
        if theirs and (end is None or outrider.uploads.pos_key(theirs) <= outrider.uploads.pos_key(end)):
            return (theirs[0], theirs[1]), theirs[2] if len(theirs) > 2 else None
        return end, None

    def set_upload(self, service, on):
        """The page's switch for one service, applied at once and written into the config file ([eddn]/[edsm]
        enabled) for the next start. Switching it on again clears a hold; switching it on from off sets its starting
        mark (upload_start_mark) and catches up from there. A note when the file could not keep it, else None."""
        was = self.upload_wanted(service)
        self.upload_cfg.setdefault(service, {})["enabled"] = bool(on)
        out, status = self.config_save({service: {"enabled": bool(on)}}, hidden=True)
        note = None
        if status != 200:
            note = (f"{service.upper()} is {'on' if on else 'off'} until Outrider stops, but the config file could not "
                    f"keep it: {out.get('error')}")
            print(f"uploads: {note}", file=sys.stderr)
        self.upload_status.pop(service, None)
        if on and not was:
            pos, ts = self.upload_start_mark(service)
            if pos:
                self.uploads_hub.set_mark(service, pos, ts)
                self.uploads_hub.flush()
                self.uploads_hub.catch_up(service, LIVE_DIRS, dict(self.journals.offsets))
        self.db.commit()
        self.bump()
        return note

    def upload_report(self, service, outcome):
        """A sending round's outcome (outrider.uploads.upload_loop): the last error, and a hold (stop until the player
        acts: a refused key) when one of its rows says so."""
        held = next((status for _, state, status, _ in outcome["results"] if state == "held"), None)
        dropped = next((status for _, state, status, _ in outcome["results"] if state == "dropped"), None)
        self.upload_status[service] = {"error": outcome["error"] or held or dropped, "at": outcome["at"], "held": held}
        self.bump()

    BLOCKED_WORDS = {"beta": "the game's beta: nothing is uploaded from it", "legacy": "the Legacy game (3.8): nobody takes its data",
                     "crew": "crew in another commander's ship", "version": "the game version is not known yet",
                     "commander": "no commander yet"}

    def uploads_summary(self):
        """The page's Uploads section: per service on, why it cannot send now (blocked), its queue, the last error."""
        blocked = self.uploads_hub.session.blocked()
        out = {}
        for service in outrider.uploads.SERVICES:
            st = self.upload_status.get(service) or {}
            out[service] = dict(outrider.uploads.counts(self.db, service), on=self.upload_on(service),
                                wanted=self.upload_wanted(service),   # the page's box: what the player switched
                                available=service in self.upload_senders, error=st.get("error"),
                                held=st.get("held") or (self.upload_conflict(service) if self.upload_wanted(service) else None),
                                blocked=self.BLOCKED_WORDS.get(blocked) if blocked in ("beta", "legacy", "crew") else None)
        out["eddn"]["test"] = outrider.uploads.eddn_test_mode()
        out["edsm"]["dry_run"] = outrider.edsm.dry_run()
        out["edsm"]["accounts"] = self.edsm_account_list()
        out["readonly"] = bool(self.lease_writable) and not any(self.lease_writable.values())
        out["simulate"] = bool(self.simulate)
        return out

    def eddn_build(self, ev, session):
        """What a live journal line sends to EDDN (outrider.eddn.build), to its test schemas when the developer's
        OUTRIDER_EDDN_TEST is set."""
        return outrider.eddn.build(ev, session, outrider.__version__, test=outrider.uploads.eddn_test_mode())

    def eddn_idle(self, session):
        """What EDDN can send on the tick with no new line (outrider.eddn.idle): late companion files, quiet signals."""
        return outrider.eddn.idle(session, outrider.__version__, test=outrider.uploads.eddn_test_mode())

    async def eddn_send(self, rows):
        """Send one queued EDDN message (EDDN takes one per request): gzip, both content headers, a 20 s timeout. The
        answer settles it (outrider.eddn.outcome); a network failure raises, and the loop waits a minute or more."""
        import gzip
        r = rows[0]
        name = r["schema"]
        held = self.eddn_hold.is_held(name)
        if held:
            return [(r["id"], "dropped", f"not sent: {name} refused repeatedly ({held})", None)]
        # an hour late is not news for anything: EDDN's readers take what arrives as current (a market most of all). Rows
        # left waiting by an outage, or queued before EDDN was switched off and on again, are dropped
        try:
            if time.time() - ts_seconds(r["created"]) > outrider.eddn.CATCHUP_MAX_S:
                return [(r["id"], "dropped", "not sent: over an hour old", None)]
        except (TypeError, ValueError):
            pass
        async with self.upload_session.post(outrider.eddn.UPLOAD_URL, data=gzip.compress(r["message"].encode("utf-8")),
                                            headers={"Content-Encoding": "gzip", "Content-Type": "application/json"}) as resp:
            text = (await resp.text())[:300]
            status = resp.status
        state, retry = outrider.eddn.outcome(status)
        if state == "dropped":
            self.eddn_hold.refused(name, time.time(), f"{status} {text}", status)
            print(f"EDDN refused a {name} message: {status} {text}", file=sys.stderr)
        return [(r["id"], state, f"{status} {text}".strip(), retry)]

    def edsm_build(self, ev, session):
        """What a live journal line sends to EDSM (outrider.edsm.build, minus EDSM's discard list)."""
        return outrider.edsm.build(ev, session, self.edsm_discard)

    async def edsm_send(self, rows):
        """Send the leading rows of one commander and one game version (outrider.edsm.same_batch) to EDSM with that
        commander's account, in one request. A commander with no account: dropped, and the status says so. Under the
        developer's OUTRIDER_EDSM_DRYRUN the request is logged (the key left out) and nothing is sent."""
        batch = outrider.edsm.same_batch(rows)
        cmdr = batch[0]["cmdr"]
        account = self.edsm_accounts().get(cmdr or "")
        if not account or not account.get("key"):
            why = f"not sent: no EDSM account for CMDR {cmdr} (Settings -> Uploads)"
            return [(r["id"], "dropped", why, None) for r in batch]
        body = outrider.edsm.request(batch, account, outrider.__version__)
        if outrider.edsm.dry_run():
            self.edsm_dry_log(body)
            return [(r["id"], "dry", "dry run: not sent", None) for r in batch]
        async with self.upload_session.post(outrider.edsm.UPLOAD_URL, json=body) as resp:
            if resp.status != 200:
                raise ConnectionError(f"EDSM answered HTTP {resp.status}")
            reply = await resp.json(content_type=None)
        results = outrider.edsm.answer(batch, reply)
        bad = next((status for _, state, status, _ in results if state in ("held", "dropped")), None)
        if bad:
            print(f"EDSM: {bad}", file=sys.stderr)
        return results

    def edsm_dry_log(self, body):
        """A dry run's request: one line on the console, the whole request (never the key) appended to edsm_dry_path."""
        names = collections.Counter(e.get("event") for e in body["message"])
        print(f"EDSM dry run: {len(body['message'])} event{'' if len(body['message']) == 1 else 's'} for "
              f"{body['commanderName']} (" + ", ".join(f"{n} x{c}" if c > 1 else n for n, c in names.items()) + "), not sent")
        if self.edsm_dry_path:
            try:
                with open(self.edsm_dry_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(body, apiKey="(not logged)"), separators=(",", ":")) + "\n")
            except OSError as e:
                print(f"EDSM dry run: cannot write {self.edsm_dry_path}: {e}", file=sys.stderr)

    async def watch_edsm_discard(self):
        """EDSM's discard list, fetched while EDSM is switched on: at start, then every DISCARD_EVERY_S (ten minutes
        after a failure; the built-in copy is used meanwhile)."""
        while True:
            wait = 60
            if self.upload_wanted("edsm") and self.upload_session is not None:
                try:
                    async with self.upload_session.get(outrider.edsm.DISCARD_URL) as resp:
                        got = outrider.edsm.discard_list(await resp.json(content_type=None)) if resp.status == 200 else None
                except Exception as e:   # unreachable, not JSON: the copy we have stays
                    print(f"EDSM: discard list not fetched ({type(e).__name__}: {e})", file=sys.stderr)
                    got = None
                if got:
                    self.edsm_discard = got
                wait = outrider.edsm.DISCARD_EVERY_S if got else 600
            await asyncio.sleep(wait)

    def edsm_accounts(self):
        """{in-game commander: {name: EDSM commander name, key: API key}} (meta edsm_accounts, live-only: kept through a
        journal re-read, in the backups with the rest of the database). Never served: edsm_accounts_view says only
        which commanders have one."""
        a = meta_get(self.db, "edsm_accounts")
        return {k: v for k, v in a.items() if isinstance(v, dict)} if isinstance(a, dict) else {}

    def set_edsm_account(self, commander, name=None, key=None, remove=False):
        """Add, change or remove one in-game commander's EDSM account. An empty key keeps the one stored. (answer,
        status)."""
        commander = str(commander or "").strip()
        if not commander or len(commander) > 64:
            return {"error": "commander: the in-game commander's name"}, 400
        accounts = self.edsm_accounts()
        if remove:
            accounts.pop(commander, None)
        else:
            old = accounts.get(commander) or {}
            name = str(name or "").strip()[:64] or old.get("name") or commander
            key = str(key or "").strip() or old.get("key")
            if not key or not re.fullmatch(r"[0-9a-fA-F]{20,64}", key):
                return {"error": "api_key: the key from www.edsm.net/settings/api (40 hexadecimal characters)"}, 400
            accounts[commander] = {"name": name, "key": key}
        meta_set(self.db, "edsm_accounts", accounts)
        self.upload_status.pop("edsm", None)   # a new key: try again
        self.db.commit()
        self.bump()
        return {"ok": True, "accounts": self.edsm_account_list()}, 200

    def edsm_account_list(self):
        """For the page: [{commander, name, set, hint}], the commander in the journals first if missing. Never the key:
        hint is its first and last four characters and its length, enough to compare with EDSM's settings page (the
        page may be open to the whole network without a password)."""
        accounts = self.edsm_accounts()
        hint = lambda k: f"{k[:4]}…{k[-4:]} ({len(k)} characters)" if k and len(k) >= 16 else None
        out = [{"commander": c, "name": a.get("name") or c, "set": bool(a.get("key")), "hint": hint(a.get("key"))}
               for c, a in sorted(accounts.items())]
        cur = (self.journals.commander or {}).get("name")
        if cur and cur not in accounts:
            out.insert(0, {"commander": cur, "name": cur, "set": False, "hint": None})
        return out

    def catch_up_uploads(self):
        """At start: each service that is on queues what was played while Outrider was not running (from its mark to
        where the start-up scan got to, at most a week back); one with no mark yet starts where the reader is."""
        n = 0
        for service in self.uploads_hub.builders:
            if not self.upload_wanted(service):
                continue
            if self.upload_conflict(service):
                # another uploader has it (EDMC, another Outrider): what was played meanwhile is theirs to send. The
                # mark moves to where they are (their lease's mark) or to the end of what was read
                theirs = outrider.uploads.lease_marks(LIVE_DIRS, self.leases.instance if self.leases else "").get(service)
                ends = [m for m in (theirs and (theirs[0], theirs[1]), self.journal_end()) if m]
                if ends:
                    end = max(ends, key=outrider.uploads.pos_key)
                    self.uploads_hub.set_mark(service, end, theirs[2] if theirs and len(theirs) > 2 and tuple(end) == (theirs[0], theirs[1]) else None)
                continue
            if service not in self.uploads_hub.marks:
                pos, ts = self.upload_start_mark(service)
                if pos:
                    self.uploads_hub.set_mark(service, pos, ts)
                continue
            n += self.uploads_hub.catch_up(service, LIVE_DIRS, dict(self.journals.offsets))
        self.uploads_hub.flush()
        self.db.commit()
        if n:
            print(f"uploads: {n} message{'' if n == 1 else 's'} from while Outrider was not running, queued")
        return n

    def uploads_line(self):
        """The start-up line: each upload on or off, and EDDN's test schemas when the developer's OUTRIDER_EDDN_TEST
        is set (said even while EDDN is off, so a test run is never mistaken for a live one)."""
        parts = [f"{s.upper()} {'on' if self.upload_wanted(s) else 'off'}" for s in outrider.uploads.SERVICES]
        if outrider.uploads.eddn_test_mode():
            parts[0] += f" (TEST: EDDN's test schemas only, {outrider.uploads.TEST_ENV} is set)"
        if outrider.edsm.dry_run():
            parts[1] += f" (DRY RUN: built and logged, nothing sent, {outrider.edsm.DRY_ENV} is set)"
        return "uploads: " + ", ".join(parts) + ("" if self.simulate else " (switched in Settings -> Uploads)")

    def start_uploads(self):
        """The sending loops (one per service with a sender), and the lease watch, started in run()."""
        self.refresh_leases()
        self.catch_up_uploads()
        if self.lease_task is None:
            self.lease_task = asyncio.get_running_loop().create_task(self.watch_leases())
        if self.edsm_discard_task is None:
            self.edsm_discard_task = asyncio.get_running_loop().create_task(self.watch_edsm_discard())
        for service, send in self.upload_senders.items():
            if service not in self.upload_tasks:
                self.upload_tasks[service] = asyncio.get_running_loop().create_task(outrider.uploads.upload_loop(
                    service, self.db, send, self.upload_on, report=self.upload_report,
                    batch=1 if service == "eddn" else outrider.edsm.BATCH))   # EDDN takes one message per request

    def set_autohonk(self, enabled):
        """Switch auto honk on or off (the page's toggle; remembered over restarts)."""
        self.autohonk["enabled"] = bool(enabled)
        meta_set(self.db, "autohonk_enabled", bool(enabled))
        self.db.commit()   # now: a failing watcher tick would roll it back, and it must survive a restart
        if not enabled and self._honk_cancel is not None:
            self._honk_cancel.set()   # a hold under way ends now, though auto-target may keep the device open
        if self.honker:
            if enabled:
                self.honker.open()
            elif not (self.honk_test_task and not self.honk_test_task.done()):   # a pending test closes it itself
                self.honker.close()
                self.honker.status = "off"
            else:
                self.honker.status = "off"   # the test keeps the device until it ends; the status is off now
        self.bump()

    def start_honk_test(self):
        """The dialog's Test button: hold Primary Fire once after a countdown (time to click into the game),
        whether or not auto honk is on. (response, HTTP status). One test at a time: a second one's cleanup
        would close the virtual keyboard under the first one's press."""
        h = self.honker
        if not h or not h.available:
            return {"error": h.status if h else "not started"}, 400
        if self.honk_test_task and not self.honk_test_task.done():
            return {"error": "a test is already running"}, 409
        keys, what = h.combo()
        if not keys:
            return {"error": what}, 400
        if not h.open():
            return {"error": h.status}, 400
        test = {"seq": (self.honk_test or {}).get("seq", 0) + 1, "state": "counting", "what": what, "error": None}
        self.honk_test = test
        self.honk_test_task = asyncio.get_running_loop().create_task(self._honk_test(test))
        self.bump()
        return {"pressing": what, "in": self.honk_test_countdown, "seq": test["seq"]}, 200

    async def _honk_test(self, test):
        h = self.honker
        try:
            await asyncio.sleep(self.honk_test_countdown)
            test["state"] = "holding"
            self.bump()
            pressed = await asyncio.get_running_loop().run_in_executor(None, h.press)
            test["state"] = "done" if pressed else "stopped"
        except Exception as e:  # noqa: BLE001 -- show it in the dialog rather than lose it in a task
            test.update(state="failed", error=str(e) if isinstance(e, ValueError) else f"{type(e).__name__}: {e}")
        finally:
            if not self.autohonk["enabled"]:   # the device only stays open for auto honk itself
                h.close()
                h.status = "off"
            self.bump()

    def maybe_honk(self):
        """A live hyperspace arrival: hold Primary Fire (after `delay`), unless you honked here before."""
        a = self.journals.jump_arrival
        if not a or a is self._honk_arrival:
            return
        self._honk_arrival = a
        if not (self.autohonk["enabled"] and self.honker and self.honker.ready):
            return
        if time.time() - ts_seconds(a["ts"]) > AUTOHONK_MAX_AGE:
            return   # catching up on journals, not a jump happening now
        if self.autohonk["skip_honked"] and self.db.execute(
                "SELECT 1 FROM own_systems WHERE id64=?", (a["id64"],)).fetchone():
            return
        self._honk_running = a   # the arrival briefing waits for its result
        self.honk_run_task = asyncio.get_running_loop().create_task(self.honk_task(a))

    async def honk_task(self, a):
        self._honk_running = a
        self._honk_cancel = cancel = threading.Event()
        try:
            await self._honk(a, cancel)
        finally:
            self._honk_done = (a, time.time())   # a honk that gave up late still leaves time for the briefing
            if self._honk_running is a:
                self._honk_running = None
            if self._honk_cancel is cancel:
                self._honk_cancel = None

    async def _honk(self, a, cancel=None):
        honked = lambda: (self.journals.last_honk or {}).get("id64") == a["id64"] \
            and self.journals.last_honk["ts"] >= a["ts"]
        # switched off meanwhile (the toggle closed the device and set the status, or set this honk's token while
        # auto-target keeps the device open): drop it quietly
        switched_off = lambda: (cancel is not None and cancel.is_set()) or \
            not (self.autohonk["enabled"] and self.honker and self.honker.ready)
        await asyncio.sleep(self.autohonk["delay"])
        if switched_off():
            return
        # wait for the cockpit: pressing with the galaxy map, FSS or a panel open does nothing
        deadline, shown, ready_status = time.time() + AUTOHONK_WAIT_MAX, None, self.honker.status
        while True:
            while True:
                if switched_off():
                    return
                if honked() or self.journals.jump_arrival is not a:   # you beat it to it, or already elsewhere
                    if shown:
                        self.honker.status = ready_status
                        self.bump()
                    return
                groups = self.honk_groups()
                action, why = honk_decision(self.journals.status_json, time.time(), groups)
                if action == "press":
                    break
                if time.time() > deadline:
                    self.honker.status = ready_status
                    self.journals.moment("honk", a["ts"], ok=False, system=a["name"], why=f"gave up waiting: {why}")
                    self.bump()
                    return
                if why != shown:
                    shown = why
                    self.honker.status = f"waiting: {why}"
                    self.bump()
                await asyncio.sleep(0.25)
            # what was selected at the press (a fresh reading only), for the miss message and the fire-group record
            press_st, ship_id = dict(self.journals.status_json or {}), (self.journals.ship or {}).get("ship_id")
            group = fire_group_letter(press_st.get("fire_group")) if status_fresh(press_st, time.time()) else None

            def check(groups=groups):
                """Again under the keyboard's lock, just before the key (auto-target may have held it for its whole
                sequence meanwhile, review CX-F3): on a worker thread, so attributes only, no database."""
                if not self.autohonk["enabled"]:
                    return "switched off"
                if honked() or self.journals.jump_arrival is not a:
                    return "nothing to do now"
                act, w = honk_decision(self.journals.status_json, time.time(), groups)
                return w if act != "press" else None
            try:
                pressed = await asyncio.get_running_loop().run_in_executor(
                    None, functools.partial(self.honker.press, check=check, cancel=cancel))
                if pressed is None or switched_off():   # switched off during the hold: cut short, nothing to report
                    return
                break
            except outrider.honk.NotNow:   # it changed while the keyboard was busy: nothing pressed, wait again
                await asyncio.sleep(0.25)
                continue
            except ValueError as e:   # nothing to press: Primary Fire has no keyboard binding, say
                if switched_off():
                    return
                self.journals.moment("honk", a["ts"], ok=False, system=a["name"], why=str(e))
                self.bump()
                return
            except Exception as e:  # noqa: BLE001 -- say so on the page rather than die quietly
                self.journals.moment("honk", a["ts"], ok=False, system=a["name"], why=f"{type(e).__name__}: {e}")
                self.bump()
                return
        deadline = time.time() + self.honk_confirm   # the journal confirms a discovery scan within a few seconds
        focus_seen = None   # a screen that opened during the press would explain a miss better than the fire group
        # your own jump started during the hold or the wait for the scan (review F42): the miss is nobody's fault
        jumped = lambda: (self.journals.jump_arrival is not a or (self.journals.last_start_jump or "") > a["ts"]
                          or bool(((self.journals.status_json or {}).get("flags") or 0) & FLAG_FSD_JUMP))
        cut = False
        while not honked() and time.time() < deadline:
            cut = cut or bool(jumped())
            action, why = honk_decision(self.journals.status_json, time.time())
            if action == "wait" and why != "still in the jump":
                focus_seen = why
            await asyncio.sleep(0.1)
        cut = cut or bool(jumped())
        info, all_found = self.journals.last_honk or {}, False
        if honked():   # a honk that finds everything is followed by FSSAllBodiesFound (a lone star, say)
            found = lambda: (self.journals.last_all_found or {}).get("id64") == a["id64"] \
                and self.journals.last_all_found["ts"] >= a["ts"] or (info.get("progress") or 0) >= 0.999
            end = time.time() + min(1.5, self.honk_confirm)
            while not (all_found := found()) and time.time() < end:
                await asyncio.sleep(0.1)
        ok = honked()
        if not ok and cut:   # you jumped before the scan could land: no failure to report, no mark against the group
            self.bump()
            return
        # a miss only counts against the group when nothing else explains it: the cockpit had focus and the HUD
        # was in analysis mode at the press (honk_decision saw to both), and no screen opened during it
        if ok or (not focus_seen and isinstance(press_st.get("flags"), int) and press_st["flags"] & FLAG_HUD_ANALYSIS
                  and not press_st.get("gui_focus")):
            self.note_honk_group(ship_id, group, ok)
        with_group = f" with fire group {group} selected" if group else ""
        # brief: the discovery scan also gave the arrival briefing (the page then leaves this one unspoken)
        self.journals.moment("honk", a["ts"], ok=ok, system=a["name"], brief=ok,
                             bodies=info.get("bodies") if ok else None, all_found=all_found,
                             why="" if ok else f"no discovery scan followed{with_group}: {focus_seen}" if focus_seen
                             else f"no discovery scan followed{with_group}: is the D-Scanner on primary fire"
                             + (" there?" if group else "?"))
        self.bump()

    def apply_own_changes(self):
        """Re-merge rows whose systems you just scanned, so the page updates as you go."""
        self.maybe_honk()
        self.maybe_brief()
        self.reconcile_arrival()
        sold = self.journals.sales_changed
        if sold:
            self.note_sale_estimates()   # before anything is taken: a failure here leaves it all for the retry
            self.db.commit()
            self.journals.sales_changed = False
        dirty, self.journals.dirty = self.journals.dirty, set()
        values, self.value_dirty = self.value_dirty - dirty, set()   # value-only rebuilds
        if sold:
            dirty |= set(self.bases)
            values = set()
        changed = False
        for id64 in dirty | values:
            if id64 in self.bases:
                if self.db.execute("SELECT 1 FROM visits WHERE id64=?", (id64,)).fetchone():
                    self.visited.add(id64)
                # a failure is retried next tick as a plain rebuild: this tick already told the views about the scan
                if self.safe_row(id64):
                    changed = changed or id64 in dirty
        if values - self.value_dirty:
            self.bump()   # new values in Nearby rows; nothing of your own scans changed
        bio_sold = self.journals.bio_sales_changed
        if bio_sold:
            self.journals.bio_sales_changed = False
            pos = self.journals.pos
            if pos and pos["id64"] in self.bases:
                dirty.add(pos["id64"])
        if changed or dirty or bio_sold:   # a sale changes My Samples even far from any row
            self.scan_version += 1
            self.bump()
        last_jump = self.db.execute("SELECT max(ts) FROM jumps").fetchone()[0]
        if sold or bio_sold or last_jump != self._history_jump:
            self._history_jump = last_jump
            self.history_version += 1
            self.bump()
        if self.journals.materials_changed or self.journals.cmdr_changed:
            if self.journals.materials_changed:
                self.materials_version += 1
            self.journals.materials_changed = self.journals.cmdr_changed = False
            self.bump()

    # ---- 3D map ----

    async def boost_points(self, pos, radius):
        """Neutron stars and white dwarfs (as arrival stars) within radius, for jet-cone boosting."""
        key = ("boost", pos["id64"], radius)
        if key in self.map_cache:
            return self.map_cache[key]
        filters = {"subtype": {"value": BOOST_STARS}, "is_main_star": {"value": True}}
        try:
            bodies, cut = await self.spansh.body_search(filters, pos, radius, 2)
        except Exception as e:
            return {"points": [], "complete_to": None, "error": f"boost-star lookup failed: {e}"}
        out = {}
        for b in bodies:
            out[b["system_id64"]] = {"name": b["system_name"], "x": b["system_x"], "y": b["system_y"],
                                     "z": b["system_z"], "id": str(b["system_id64"]),
                                     "boost": "N" if b.get("subtype") == "Neutron Star" else "D",
                                     "distance": round(dist(pos, {"x": b["system_x"], "y": b["system_y"],
                                                                  "z": b["system_z"]}), 2)}
        res = {"points": sorted(out.values(), key=lambda p: p["distance"]), "complete_to": cut}
        self.map_cache[key] = res
        return res

    async def map_payload(self, radius, path_len, boost=False):
        """Every system within radius for the map: Spansh's plus your visits and route plots."""
        pos = self.journals.pos
        if not pos:
            return {"error": "no current position yet"}
        key = (pos["id64"], radius)
        note, failed = None, False
        if key not in self.map_cache:
            try:
                results = await self.spansh.sphere(pos, radius, MAP_MAX_PAGES)
            except Exception as e:
                results, note, failed = [], f"Spansh lookup failed: {e}", True
            if len(results) >= SPANSH_PAGE * MAP_MAX_PAGES:
                note = (f"Spansh has more systems in range than the map fetches; showing the nearest "
                        f"{len(results):,} (out to {results[-1]['distance']:.0f} ly)")
            known = {}
            for r in results:
                bodies = [b for b in r.get("bodies") or [] if b.get("type") in ("Star", "Planet")]
                main = next((b for b in bodies if b.get("is_main_star")), None)
                known[r["id64"]] = {"name": r["name"], "x": r["x"], "y": r["y"], "z": r["z"],
                                    "scanned": bool(bodies),
                                    "star": star_short(main.get("subtype")) if main else None}
            if len(self.map_cache) > 4:
                self.map_cache.clear()
            if not failed:
                self.map_cache[key] = (known, note)
        else:
            known, note = self.map_cache[key]

        points = {}
        for id64, k in known.items():
            points[id64] = dict(k, kind="known")
        for v in self.near("visits", pos, radius):
            points.setdefault(v["id64"], {"name": v["name"], "x": v["x"], "y": v["y"], "z": v["z"],
                                          "kind": "own", "scanned": True})["visited"] = True
        for rs in self.near("route_systems", pos, radius):
            points.setdefault(rs["id64"], {"name": rs["name"], "x": rs["x"], "y": rs["y"], "z": rs["z"],
                                           "kind": "route", "scanned": False})
        firsts = {r[0] for r in self.db.execute(
            "SELECT DISTINCT system FROM own_firsts WHERE is_main = 1 AND was_discovered = 0")}
        classes = dict(self.db.execute("SELECT id64, star_class FROM star_classes").fetchall())
        out = []
        for id64, pt in points.items():
            d = dist(pos, pt)
            if d > radius:
                continue
            out.append(dict(pt, id=str(id64), distance=round(d, 2), visited=bool(pt.get("visited")),
                            first=id64 in firsts, star=pt.get("star") or classes.get(id64)))
        path = [dict(r) for r in self.db.execute(
            "SELECT ts, id64, name, x, y, z, star_class, kind FROM jumps ORDER BY ts DESC LIMIT ?",
            (path_len,))][::-1]
        for j in path:
            j["id"] = str(j.pop("id64"))
        boosts = await self.boost_points(pos, radius) if boost else None
        return {"center": with_id(pos), "radius": radius, "points": out, "note": note, "path": path,
                # a failed lookup is not cached: the page asks again after a while instead of keeping the gap
                "partial": failed or bool(boosts and boosts.get("error")),
                "boost": boosts, "here_star": self.here_star(),
                "jump_range": (self.journals.jump_range or {}).get("ly"),
                "carrier": self.carrier_summary()}

    def maybe_locate_carrier(self):
        c = self.journals.carrier
        if not c or not c.get("id64") or c.get("x") is not None or self.locate(c["id64"]):
            return
        if self.carrier_task and not self.carrier_task.done():
            return
        id64 = c["id64"]
        if time.time() < self.carrier_retry.get(id64, 0):
            return

        async def go():
            try:
                dump = await self.spansh.lookup(id64)
            except Exception:
                dump = None
            co = ((dump or {}).get("system") or {}).get("coords") or {}
            cur = self.journals.carrier
            if cur is not c or cur.get("id64") != id64 or cur.get("x") is not None:
                # the carrier moved (carrier_seen changes this same dict in place) or was reloaded while Spansh
                # answered: these are another system's coordinates. The next tick looks the new place up.
                return
            if "x" in co:
                c.update(x=co["x"], y=co["y"], z=co["z"])
                meta_set(self.db, "carrier", c)
                self.db.commit()
                self.bump()
            else:   # Spansh does not know the system (yet) or is down: not again for 10 minutes, not every tick
                self.carrier_retry[id64] = time.time() + CARRIER_RETRY_S
        self.carrier_task = asyncio.create_task(go())

    def maybe_find_sellers(self):
        """Keep the nearest Universal Cartographics / Vista Genomics stations known (Spansh), refreshed after
        SELLER_REFRESH_LY of travel or SELLER_REFRESH_S. One small request per service."""
        pos = self.journals.pos
        if not pos or (self.seller_task and not self.seller_task.done()):
            return
        cur = meta_get(self.db, "sellers")
        if cur and dist(pos, cur["pos"]) < SELLER_REFRESH_LY and time.time() - cur["fetched"] < SELLER_REFRESH_S:
            return
        if self.seller_retry_at and time.time() < self.seller_retry_at:
            return

        async def go():
            try:
                uc = await self.spansh.stations("Universal Cartographics", pos)
                vista = await self.spansh.stations("Vista Genomics", pos)
            except Exception as e:
                self.seller_retry_at = time.time() + 600
                print(f"nearest sellers lookup failed ({type(e).__name__}: {e}); trying again in 10 min", file=sys.stderr)
                return
            meta_set(self.db, "sellers", {"pos": {k: pos[k] for k in ("x", "y", "z", "name")}, "fetched": time.time(),
                                          "uc": uc, "vista": vista})
            self.db.commit()
            self.bump()
        self.seller_task = asyncio.create_task(go())

    def route_summary(self):
        """The plotted route from where you are: each hop's star (scoopable or not), whether you have been
        there, and the longest stretch without a scoopable star (where fuel runs out)."""
        route, pos = meta_get(self.db, "route"), self.journals.pos
        if not route or not pos:
            return None
        hops = route["hops"]
        i = next((k for k, h in enumerate(hops) if h["id64"] == pos["id64"]), None)
        left = hops[i + 1:] if i is not None else hops
        if not left:
            return None
        visited = {r[0] for r in self.db.execute(
            f"SELECT id64 FROM visits WHERE id64 IN ({','.join('?' * len(left))})", [h["id64"] for h in left])}
        out, prev, dry, longest, total = [], pos, 0, 0, 0.0
        for h in left:
            d = dist(prev, h)
            total += d
            scoop = class_scoopable(h["star_class"]) if h.get("star_class") else None
            dry = 0 if scoop else dry + 1
            longest = max(longest, dry)
            known = h["id64"] in self.systems or bool(self.spansh.cached(h["id64"])[1]) if self.spansh else False
            out.append({"id": str(h["id64"]), "name": h["name"], "star_class": h.get("star_class"), "scoopable": scoop,
                        "ly": round(d, 1), "visited": h["id64"] in visited, "known": known})
            prev = h
        next_scoop = next((k + 1 for k, h in enumerate(out) if h["scoopable"]), None)
        return {"hops": out, "ly": round(total, 1), "longest_dry": longest, "next_scoop": next_scoop, "ts": route.get("ts")}

    def next_stop_summary(self):
        ns, pos = meta_get(self.db, "next_stop"), self.journals.pos
        if not ns:
            return None
        return dict(ns, id=str(ns["id64"]), distance=round(dist(pos, ns), 1) if pos else None)

    def remember_voice(self, name):
        """The voice picked in the alerts dialog, once it has loaded: preferred at the next start (a choice that
        never loaded is not saved, so a broken voice does not replace the working one after a restart)."""
        meta_set(self.db, "voice_choice", name)
        self.db.commit()

    def set_next_stop(self, id64):
        """Make a system (a bookmark, usually) the next stop: its distance shows in the header until you arrive."""
        if id64 is None:
            meta_set(self.db, "next_stop", None)
        else:
            where = self.locate(id64)
            if not where:
                return False
            # set_ts: arrivals up to now do not clear it (a journal re-read replays your earlier visits there)
            meta_set(self.db, "next_stop", {"id64": id64, "name": where[0], "x": where[1], "y": where[2], "z": where[3],
                                            "set_ts": (self.journals.pos or {}).get("ts") or iso_ts(time.time())})
        self.db.commit()
        self.bump()
        return True

    # ---- the Neutron Highway ----

    def fleet_list(self):
        """Every ship you have flown (its latest Loadout), the newest first: the Highway's ship list."""
        out = []
        for r in self.db.execute("SELECT * FROM fleet_loadouts ORDER BY ts DESC"):
            fig = json.loads(r["figures"] or "{}")
            out.append({"ship_id": r["ship_id"], "name": r["name"], "type": r["ship_type"], "ident": r["ident"],
                        "ts": r["ts"], "range": fleet_range(fig), "figures": fig})
        return out

    def fleet_ship(self, ship_id):
        r = self.db.execute("SELECT * FROM fleet_loadouts WHERE ship_id=?", (ship_id,)).fetchone()
        return dict(r, figures=json.loads(r["figures"] or "{}")) if r else None

    def highway_state(self):
        """(meta, rows) of the active route, or (None, [])."""
        hw = meta_get(self.db, "highway")
        rows = self.journals.highway_route(hw) if hw else []
        return (hw, rows) if hw and rows else (None, [])

    @staticmethod
    def highway_next(hw, rows):
        """The index of the next route system to fly to (None once you are at the end)."""
        at, furthest = hw.get("at"), hw.get("furthest")
        i = at + 1 if at is not None else furthest + 1 if furthest is not None else 0
        return i if i < len(rows) else None

    def highway_nearest(self, hw, rows):
        """While off the route: the CLOSEST route system, passed or not {name, id, index, distance}, or None. Getting
        back on the highway is the fastest way on (the author's rule, 2026-10-03); arriving there resumes the route.
        The answer depends only on the route and where you are, which is the cache key."""
        pos = self.journals.pos
        if not pos or not hw.get("off_route"):
            return None
        key = (hw["id"], pos["id64"])
        if self._hw_near[0] != key:
            best = min(((dist(pos, r), i) for i, r in enumerate(rows) if None not in (r["x"], r["y"], r["z"])),
                       default=None)
            self._hw_near = (key, best and {"name": rows[best[1]]["system"], "id": str(rows[best[1]]["id64"])
                                            if rows[best[1]]["id64"] is not None else None,
                                            "index": best[1], "distance": round(best[0], 1)})
        return self._hw_near[1]

    def highway_summary(self):
        """The highway line's facts for /api/nearby (Overview, Nearby, Here), or None with no route: the next system
        (neutron, refuel, ly from here), where you are on the route, the refuel coming up, and the detour."""
        hw, rows = self.highway_state()
        if not hw:
            return None
        pos, n = self.journals.pos, len(rows)
        at, nx = hw.get("at"), self.highway_next(hw, rows)
        base = at if at is not None else nx - 1 if nx is not None else n - 1   # -1: not on it yet (before its start)
        nxt = rows[nx] if nx is not None else None
        here = rows[at] if at is not None else None
        return {
            "id": hw["id"], "plotter": hw.get("plotter"), "created_ts": hw.get("created_ts"),
            "destination": rows[-1]["system"], "total": n - 1,
            "index": nx, "at": at, "furthest": hw.get("furthest"), "complete": bool(hw.get("done_ts")),
            "off_route": bool(hw.get("off_route")), "nearest": self.highway_nearest(hw, rows),
            "jumps_total": sum(r["jumps"] or 0 for r in rows),
            "jumps_left": sum(r["jumps"] or 0 for r in rows[nx:]) if nx is not None else 0,
            "ly_left": rows[base]["remaining"] if base >= 0 else None,
            "refuel_here": bool(here and here["refuel"]),
            "refuel_in": highway_refuel_in(rows, base) if base >= 0 else None,
            "next": nxt and {"name": nxt["system"], "id": str(nxt["id64"]) if nxt["id64"] is not None else None,
                             "neutron": bool(nxt["neutron"]), "refuel": bool(nxt["refuel"]), "jumps": nxt["jumps"],
                             "distance": round(dist(pos, nxt), 1) if pos and None not in (nxt["x"], nxt["y"], nxt["z"])
                             else nxt["distance"]},
            "boost_here": bool(here and here["neutron"]),
            "heavy": self.highway_heavy(hw),
        }

    @staticmethod
    def _hw_heavy_key(hw):
        return (hw.get("id"), hw.get("at"), hw.get("arrival_ts") or hw.get("created_ts"))

    def highway_heavy(self, hw):
        """The too-heavy warning for where you are on the route now (highway_heavy_check's), or None."""
        c = self._hw_heavy
        return c.get("heavy") if hw and c.get("key") == self._hw_heavy_key(hw) else None

    def highway_heavy_check(self, now=None):
        """Too much fuel for the next jump: Spansh's exact plotter simulates the fuel, so a long neutron jump may be in
        range only with about the fuel the plan expects aboard (a full tank weighs the ship down). Looked at on a live
        arrival in a route system (or a plot made where you are) and again while Status.json's fuel changes there (at
        most every HIGHWAY_HEAVY_EVERY_S), only for the ship the route was plotted for, with the game running. The
        next jump's distance (one jump: every exact-plotter row, a neutron-plotter waypoint only when one jump away), the
        current ship's fuel model (fuel_now: the main tank, the cargo; the reservoir counted as mass), its supercharge
        when this is a neutron system on the route (or a charge you hold): over the most fuel that still reaches it by
        HIGHWAY_HEAVY_SLACK, the warning ({need_t, have_t, distance, boost, next}) and one spoken moment per system.
        Cleared when the fuel drops enough, or you leave. True when the warning changed."""
        now = time.time() if now is None else now
        j, c = self.journals, self._hw_heavy
        hw, rows = self.highway_state()
        key = self._hw_heavy_key(hw) if hw else None
        st = j.status_json or {}
        if key != c.get("key"):
            ts = key and key[2]
            try:
                live = bool(ts and live_event(ts, now) and now - ts_seconds(ts) <= HIGHWAY_LIVE_S)
            except (TypeError, ValueError):
                live = False
            before = c.get("heavy")
            c.clear()
            c.update(key=key, live=live, said=False, t=None, look=None, heavy=None)
            changed = before is not None
        else:
            changed = False
        look = (round(st.get("fuel_main") or 0, 1), round(st.get("fuel_reservoir") or 0, 2), st.get("cargo"),
                (j.boost or {}).get("ts"), (j.ship or {}).get("ship_id"), bool(st.get("live")))
        due = key and c["live"] and look != c["look"] and (c["t"] is None or now - c["t"] >= HIGHWAY_HEAVY_EVERY_S)
        heavy = c["heavy"]
        if due:
            c.update(look=look, t=now)
            heavy = self._highway_heavy_now(hw, rows, st)
            if heavy != c["heavy"]:
                c["heavy"], changed = heavy, True
        if heavy and not c["said"]:
            c["said"] = True
            need = int(heavy["need_t"])
            j.moment("highway", iso_ts(now), what="heavy", system=rows[hw["at"]]["system"], index=hw["at"],
                     next=heavy["next"], need_t=heavy["need_t"], have_t=heavy["have_t"],
                     text="Too much fuel for the next jump. " +
                          (f"It needs about {need} tons aboard" if need >= 1 else "It needs under a ton aboard") +
                          f"; you have {round(heavy['have_t'])}.")
        if changed:
            self.bump()
        return changed

    def _highway_heavy_now(self, hw, rows, st):
        j = self.journals
        at = hw.get("at")
        if at is None or hw.get("done_ts") or hw.get("off_route") or at + 1 >= len(rows) or not st.get("live"):
            return None
        ship, pos = j.ship or {}, j.pos
        if (hw.get("ship") or {}).get("ship_id") is None or hw["ship"]["ship_id"] != ship.get("ship_id"):
            return None   # plotted for another ship (or from a typed range): its plan says nothing of this one
        here, nxt = rows[at], rows[at + 1]
        if not pos or (here["id64"] is not None and here["id64"] != pos["id64"]):
            return None
        if (nxt["jumps"] or 1) != 1:
            return None   # a neutron-plotter waypoint several jumps away: the first jump's length is not known
        d = nxt["distance"]
        if not d and None not in (here["x"], here["y"], here["z"], nxt["x"], nxt["y"], nxt["z"]):
            d = dist(here, nxt)
        now = self.fuel_now()
        if not d or not now:
            return None
        model, fuel, cargo = now
        mult = max((j.boost or {}).get("value") or 1, fsd_supercharge(ship.get("fsd")) if here["neutron"] else 1)
        other = cargo + (st.get("fuel_reservoir") or 0)
        need = max_fuel_for_jump(model, d, other, mult)
        if need is None or fuel <= need + HIGHWAY_HEAVY_SLACK:
            return None   # light enough (or out of reach whatever the fuel: not a weight problem)
        return {"need_t": math.floor(need * 10) / 10, "have_t": round(fuel, 1), "distance": round(d, 1), "boost": mult,
                "next": nxt["system"]}

    @staticmethod
    def highway_row_out(i, r):
        return {"i": i, "system": r["system"], "id": str(r["id64"]) if r["id64"] is not None else None,
                "x": r["x"], "y": r["y"], "z": r["z"], "distance": r["distance"], "fuel_used": r["fuel_used"],
                "fuel_left": r["fuel_left"], "neutron": bool(r["neutron"]), "refuel": bool(r["refuel"]),
                "jumps": r["jumps"], "remaining": r["remaining"]}

    def highway_view(self):
        """GET /api/highway: the route with its progress (the next HIGHWAY_AHEAD rows and the HIGHWAY_DONE most recent
        done above them), the plot under way, the fleet, the clipboard and auto-target."""
        hw, rows = self.highway_state()
        route = None
        if hw:
            nx = self.highway_next(hw, rows)
            start = nx if nx is not None else len(rows)
            route = dict({k: hw.get(k) for k in ("id", "plotter", "ship", "options", "created_ts", "at", "furthest",
                                                  "off_route", "arrival_ts", "done_ts", "stand_in")},
                         **{"from": rows[0]["system"], "to": rows[-1]["system"], "count": len(rows),
                            "total_ly": rows[0]["remaining"], "summary": self.highway_summary(),
                            "done": [self.highway_row_out(i, rows[i]) for i in range(max(0, start - HIGHWAY_DONE), start)],
                            "ahead": [self.highway_row_out(i, rows[i]) for i in range(start, min(len(rows), start + HIGHWAY_AHEAD))],
                            # every point for the map: [x, z] in the galaxy's plane, and the neutron flags
                            "points": [[r["x"], r["z"]] for r in rows], "neutrons": [i for i, r in enumerate(rows) if r["neutron"]]})
        cb = self.clipboard.info() if self.clipboard else {"enabled": self.highway_cfg["clipboard"], "available": False,
                                                           "tool": None, "why": "not started", "last": None}
        pos = self.journals.pos
        return {"route": route, "plotting": self.highway_plotting, "fleet": self.fleet_list(),
                "ship_id": (self.journals.ship or {}).get("ship_id"), "cargo": (self.journals.cargo or {}).get("count"),
                "position": with_id(pos), "clipboard": cb,
                "autotarget": self.autotarget_info(),
                "defaults": {k: self.highway_cfg[k] for k in ("efficiency", "conservative", "conservative_ly")},
                "background": self.highway_background()}

    def highway_background(self):
        """The map's background image as the page needs it: image (one is configured and can be served now), its
        extent [xmin, xmax, zmin, zmax], opacity, v (changes with the file: the image's URL carries it), name, why
        (when it is configured but cannot be served)."""
        cfg = self.highway_cfg
        path = cfg.get("background_image") or ""
        out = {"image": False, "extent": cfg.get("background_extent") or list(HIGHWAY_BG_EXTENT),
               "opacity": cfg.get("background_opacity", HIGHWAY_BG_OPACITY), "v": None,
               "name": os.path.basename(path) or None, "why": None}
        if path:
            try:
                _, st = highway_bg_file(path)
                out.update(image=True, v=f"{int(st.st_mtime)}-{st.st_size}")
            except ValueError as e:
                out["why"] = str(e)
        return out

    def highway_start_plot(self, body):
        """POST /api/highway/plot: check the request, start the Spansh job in the background, (answer, HTTP status).
        {plotter: exact | neutron, from (default: where you are), to, ship_id (default: the current ship), cargo,
        injections, exclude_secondary, supercharged, no_neutrons (exact: regular jumps only, no neutron boost); range, efficiency, supercharge_multiplier (neutron);
        conservative, conservative_ly (both: jumps that many ly shorter than the ship's range)}."""
        if self.highway_task and not self.highway_task.done():
            return {"error": "a route is being plotted already"}, 409
        plotter = body.get("plotter", "exact")
        if plotter not in ("exact", "neutron"):
            return {"error": "plotter must be exact or neutron"}, 400
        name = lambda v: " ".join(v.split()) if isinstance(v, str) else ""
        frm = name(body.get("from")) or (self.journals.pos or {}).get("name") or ""
        to = name(body.get("to"))
        if not frm or not to or len(frm) > FIND_NAME_MAX or len(to) > FIND_NAME_MAX:
            return {"error": f"give the from and to systems' names (up to {FIND_NAME_MAX} characters)"}, 400
        flag = lambda k: body.get(k) is True

        def number(k, lo, hi, conv=float, default=None):
            v = body.get(k)
            if v is None or v == "":
                return default
            try:
                if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                    raise ValueError(k)
                v = conv(float(v))
            except (ValueError, OverflowError):
                raise ValueError(f"{k} is not a number") from None
            if not (lo <= v <= hi):
                raise ValueError(f"{k} is out of range ({lo:g} to {hi:g})")
            return v
        sid = body.get("ship_id", (self.journals.ship or {}).get("ship_id"))
        ship = self.fleet_ship(sid) if isinstance(sid, int) and not isinstance(sid, bool) else None
        fig = (ship or {}).get("figures") or {}
        same = ship and ship["ship_id"] == (self.journals.ship or {}).get("ship_id")
        try:
            cargo = number("cargo", 0, 100000, int, (self.journals.cargo or {}).get("count") if same else 0) or 0
            # conservative range: plot jumps `margin` ly shorter than the ship's normal range (the page's tick, else
            # [highway] conservative), so a jump planned at the limit still has room for more fuel or cargo aboard
            cons = body.get("conservative", self.highway_cfg.get("conservative", False))
            if not isinstance(cons, bool):
                raise ValueError("conservative must be true or false")
            margin = number("conservative_ly", 0.5, HIGHWAY_CONSERVATIVE_MAX, float,
                            self.highway_cfg.get("conservative_ly", HIGHWAY["conservative_ly"])) if cons else None
            if plotter == "exact":
                if not ship:
                    return {"error": "pick a ship you have flown (it needs a Loadout in your journals)"}, 400
                if not fig.get("exact"):
                    return {"error": f"Outrider does not know this ship's frame shift drive ({fig.get('fsd') or 'none'}): "
                                     "use the neutron plotter with its range"}, 400
                reserve = fig.get("fuel_reserve") or 0
                # conservative: a smaller optimal mass, so the normal (unboosted, full tank) range is `margin` ly
                # shorter at every step of Spansh's fuel simulation; the booster's ly are left as they are
                short = conservative_optimal_mass(fig, cargo, margin) if margin else None
                params = {"source": frm, "destination": to, "is_supercharged": int(flag("supercharged")),
                          "use_supercharge": int(not flag("no_neutrons")), "use_injections": int(flag("injections")),
                          "exclude_secondary": int(flag("exclude_secondary")), "fuel_power": fig["fuel_power"],
                          "fuel_multiplier": fig["fuel_multiplier"], "optimal_mass": short[0] if short else fig["optimal_mass"],
                          "supercharge_multiplier": fig["supercharge"], "base_mass": round(fig["unladen"] + reserve, 3),
                          "tank_size": fig["fuel_main"], "internal_tank_size": reserve,
                          "max_fuel_per_jump": fig["max_fuel"], "range_boost": fig.get("booster_ly") or 0, "cargo": cargo}
                options = {"cargo": cargo, "injections": flag("injections"), "exclude_secondary": flag("exclude_secondary"),
                           "supercharged": flag("supercharged"), "no_neutrons": flag("no_neutrons")}
                if short:
                    options.update(conservative_ly=margin, range_full=round(short[1], 2), range=round(short[2], 2))
                reach = short[2] if short else fleet_range(fig, cargo)
                url = SPANSH_GENERIC_ROUTE
            else:
                rng = number("range", 1, 1000, float, fleet_range(fig, cargo) if ship else None)
                if not rng:
                    return {"error": "give the jump range (ly), or pick a ship you have flown"}, 400
                eff = number("efficiency", 1, 100, int, self.highway_cfg["efficiency"])
                mult = number("supercharge_multiplier", 4, 6, int, fig.get("supercharge") or 4)
                if mult not in (4, 6):
                    raise ValueError("supercharge_multiplier must be 4 or 6")
                full = rng
                if margin:   # never cut the drive's own part by more than half; a ship's booster ly stay (a typed
                    rng = conservative_range(rng, margin, (fig.get("booster_ly") or 0) if ship else 0)   # range, no ship: 0)
                params = {"from": frm, "to": to, "range": round(rng, 2), "efficiency": eff, "supercharge_multiplier": mult}
                reach = rng
                options = {"range": round(rng, 2), "efficiency": eff, "supercharge_multiplier": mult, "cargo": cargo}
                if margin:
                    options.update(conservative_ly=margin, range_full=round(full, 2))
                url = SPANSH_ROUTE
        except ValueError as e:
            return {"error": str(e)}, 400
        meta = {"plotter": plotter, "options": options,
                "ship": ship and {"ship_id": ship["ship_id"], "name": ship["name"], "type": ship["ship_type"], "ts": ship["ts"]}}
        self.highway_plotting = {"state": "running", "plotter": plotter, "from": frm, "to": to,
                                 "started": iso_ts(time.time()), "error": None}
        self.highway_task = asyncio.get_running_loop().create_task(self._highway_plot(url, params, plotter, meta, reach))
        self.bump()
        return {"ok": True, "plotting": self.highway_plotting}, 202

    def highway_local(self, name):
        """{system, id64, x, y, z} of a system known here by name (where you are, a visit, a bookmark...), or None."""
        pos = self.journals.pos or {}
        if (pos.get("name") or "").lower() == name.lower() and None not in (pos.get("x"), pos.get("y"), pos.get("z")):
            return {"system": pos["name"], "id64": pos.get("id64"), "x": pos["x"], "y": pos["y"], "z": pos["z"]}
        hit = self.find_local(name)
        if not hit:
            return None
        return {"system": hit[1], "id64": int(hit[0]) if hit[0] is not None else None, "x": hit[2], "y": hit[3], "z": hit[4]}

    async def highway_stand_in(self, real, toward, reach):
        """Spansh's {name, id64, x, y, z} to plot with in place of `real`, a system it does not know yet: from what it
        sent about where you are (the neighbourhood), else asked around `real`; HighwayError when it knows none near."""
        pos = self.journals.pos or {}
        cands = []
        if real.get("id64") is not None and real["id64"] == pos.get("id64"):
            cands = [dict(b, id64=i) for i, (src, b) in list(self.bases.items()) if src == "spansh" and i != real["id64"]]
        pick = stand_in(real, toward, cands, reach)
        if pick is None or (reach and math.dist((real["x"], real["y"], real["z"]), (pick["x"], pick["y"], pick["z"])) > reach):
            try:
                found = await self.spansh.sphere(real, max(reach or 0, HIGHWAY_STAND_IN_LY), max_pages=1)
            except (ClientError, asyncio.TimeoutError, ValueError) as e:
                raise HighwayError(f"Spansh cannot be reached ({type(e).__name__}): try again later") from e
            cands += [{"name": s.get("name"), "id64": s.get("id64"), "x": s.get("x"), "y": s.get("y"), "z": s.get("z")}
                      for s in found if isinstance(s, dict) and s.get("id64") != real.get("id64")]
            pick = stand_in(real, toward, cands, reach)
        if pick is None:
            raise HighwayError(f"Spansh knows no system within {max(reach or 0, HIGHWAY_STAND_IN_LY):g} ly of "
                               f"{real['system']} to plot with")
        return {"name": pick["name"], "id64": int(pick["id64"]), "x": pick["x"], "y": pick["y"], "z": pick["z"]}

    async def highway_ends(self, frm, to, reach):
        """The plot's two ends as Spansh knows them, ({name, id64, x, y, z} to plot from, ... to, the real start or None,
        the real end or None, a note in words or None). A system Spansh does not know yet (a fresh discovery), known
        here, is stood in for by a system near it that Spansh knows: the route is plotted from (or to) that one and the
        real end is put back as a jump of its own. No `to` (a survey route's is optional): no destination, (..., None)."""
        try:
            src = await self.spansh.system_record(frm)
            dst = await self.spansh.system_record(to) if to else None
        except (ClientError, asyncio.TimeoutError, ValueError) as e:
            raise HighwayError(f"Spansh cannot be reached ({type(e).__name__}): try again later") from e
        start = end = None
        notes = []
        far = lambda d: f" (longer than this ship's {reach:.1f} ly range: check it in the galaxy map)" if reach and d > reach else ""
        if src is None:
            start = self.highway_local(frm)
            if start is None:
                raise HighwayError(highway_not_yet(frm))
            src = await self.highway_stand_in(start, dst or (self.highway_local(to) if to else None), reach)
            d = math.dist((start["x"], start["y"], start["z"]), (src["x"], src["y"], src["z"]))
            notes.append(f"Spansh doesn't know {start['system']} yet: the route starts with a {d:.1f} ly jump to "
                         f"{src['name']}, the nearest system it knows on the way{far(d)}.")
        if dst is None and to:
            end = self.highway_local(to)
            if end is None:
                raise HighwayError(f"Spansh knows no system called {to}")
            dst = await self.highway_stand_in(end, src, reach)
            d = math.dist((end["x"], end["y"], end["z"]), (dst["x"], dst["y"], dst["z"]))
            notes.append(f"Spansh doesn't know {end['system']} yet: the route ends with a {d:.1f} ly jump from "
                         f"{dst['name']}{far(d)}.")
        return src, dst, start, end, " ".join(notes) or None

    async def _highway_plot(self, url, params, plotter, meta, reach=None):
        p = self.highway_plotting
        try:
            ends = ("source", "destination") if plotter == "exact" else ("from", "to")
            src, dst, start, end, note = await self.highway_ends(params[ends[0]], params[ends[1]], reach)
            if (start or end) and src["id64"] == dst["id64"]:
                # both ends stand in for the same system: no Spansh route, just the jumps to and from it
                rows = [dict(system=src["name"], id64=src["id64"], x=src["x"], y=src["y"], z=src["z"], distance=None,
                             fuel_used=None, fuel_left=None, neutron=0, refuel=0, jumps=0, remaining=0.0)]
            else:
                # the exact plotter takes id64s (it answers "Unable to find route" to names, found in game 2026-10-03);
                # the neutron plotter names
                params = dict(params, **({"source": src["id64"], "destination": dst["id64"]} if plotter == "exact"
                                         else {"from": src["name"], "to": dst["name"]}))
                rows = highway_rows(plotter, await self.spansh.plot(url, params))
            rows = splice_route(rows, plotter, reach, start, end)
            if note:
                meta = dict(meta, stand_in=note)
            self.highway_store(rows, meta)
            p.update(state="done", note=note)
            self.highway_copy_next(force=True)   # you are usually at its start: the first hop is ready to paste
        except HighwayError as e:
            p.update(state="failed", error=str(e))
        except Exception as e:  # noqa: BLE001 -- say it on the page rather than lose it in a task
            import traceback
            traceback.print_exc()
            p.update(state="failed", error=f"{type(e).__name__}: {e}")
        finally:
            p["ended"] = iso_ts(time.time())
            self.bump()

    def highway_store(self, rows, meta):
        """A new route replaces the old one: its rows, and its meta with where you are on it now."""
        self.cancel_autotarget(route=True)   # a pending run would target the old route's next system (CX-F2)
        self.db.execute("DELETE FROM highway_route")
        self.db.executemany("INSERT INTO highway_route (idx, system, id64, x, y, z, distance, fuel_used, fuel_left, neutron,"
                            " refuel, jumps, remaining) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            [(i, r["system"], r["id64"], r["x"], r["y"], r["z"], r["distance"], r["fuel_used"],
                              r["fuel_left"], r["neutron"], r["refuel"], r["jumps"], r["remaining"]) for i, r in enumerate(rows)])
        pos = self.journals.pos
        i = highway_match(rows, pos["id64"], pos["name"]) if pos else None
        now = time.time()
        # since_ts: the journal time of the position matched here; arrivals after it count, read yet or not (F8)
        hw = dict(meta, id=f"{now:.6f}", created_ts=iso_ts(now), since_ts=(pos or {}).get("ts"), at=i, furthest=i,
                  off_route=None, arrival_ts=None, done_ts=None)
        meta_set(self.db, "highway", hw)
        self.db.commit()
        self._hw_copied = None
        return hw

    def highway_clear(self):
        """POST /api/highway/clear: forget the route (and stop a plot under way)."""
        if self.highway_task and not self.highway_task.done():
            self.highway_task.cancel()
            if self.highway_plotting:
                self.highway_plotting.update(state="failed", error="cancelled")
        self.cancel_autotarget(route=True)   # its target belonged to the route just forgotten (CX-F2)
        self.db.execute("DELETE FROM highway_route")
        meta_set(self.db, "highway", None)
        self.db.commit()
        self.bump()

    def highway_copy_next(self, force=False):
        """After an arrival on the route (live, HIGHWAY_LIVE_S), or a new plot (force): copy the next system's name to
        the desktop clipboard, once per arrival. Off the event loop when there is one (the tool forks, but a stuck
        one must not stall the journal tailing)."""
        hw, rows = self.highway_state()
        cb = self.clipboard
        if not hw or not cb or not cb.enabled or not cb.tool:
            return False
        key = hw.get("arrival_ts") or hw.get("created_ts")
        if key == self._hw_copied and not force:
            return False
        self._hw_copied = key
        if self.route_newest() != "highway":   # a Road to Riches plotted since has the clipboard
            return False
        if hw.get("at") is None or hw.get("done_ts"):
            return False
        if not force and not (hw.get("arrival_ts") and live_event(hw["arrival_ts"]) and
                              time.time() - ts_seconds(hw["arrival_ts"]) <= HIGHWAY_LIVE_S):
            return False
        nx = self.highway_next(hw, rows)
        if nx is None:
            return False
        name = rows[nx]["system"]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop:
            fut = loop.run_in_executor(None, cb.copy, name)
            fut.add_done_callback(lambda _f: self.bump())
        else:
            cb.copy(name)
        return True

    # ---- Road to Riches (outrider/riches.py): Spansh's route of systems with valuable bodies ----

    def riches_state(self):
        """(meta, rows) of the active route, or (None, [])."""
        rc = meta_get(self.db, "riches")
        rows = self.journals.riches_route(rc) if rc else []
        return (rc, rows) if rc and rows else (None, [])

    @staticmethod
    def riches_next(rc, rows):
        """The index of the next route system after where you are (None once you are at the end)."""
        at, furthest = rc.get("at"), rc.get("furthest")
        i = at + 1 if at is not None else furthest + 1 if furthest is not None else 0
        return i if i < len(rows) else None

    def riches_system_out(self, rc, rows, i):
        """Route row i for the page: the system, and its bodies with what you have scanned and mapped (Road to Riches)
        or its species with what you have sampled and what would be new to your codex there (Exomastery: by species,
        in the system's region, which never over-flags), from the journal."""
        r = rows[i]
        if rc.get("kind") == "trade":   # a stop: its station, what to sell and buy there, with what your journal shows done
            done = (rc.get("trade") or {}).get(str(i)) or {}
            left = trade_left(r, done)
            still = {"sell": {c["name"] for k, c in left if k == "sell"}, "buy": {c["name"] for k, c in left if k == "buy"}}
            return {"i": i, "system": r["system"], "id": str(r["id64"]) if r["id64"] is not None else None,
                    "x": r["x"], "y": r["y"], "z": r["z"], "jumps": None, "station": r.get("station"), "ls": r.get("ls"),
                    "distance": r.get("distance"), "profit": r.get("profit") or 0, "cumulative": r.get("cumulative") or 0,
                    "age_s": round(time.time() - r["updated"]) if r.get("updated") else None, "left": len(left),
                    "value": r.get("profit") or 0, "value_left": 0, "bodies": [],
                    # done: its planned tonnes traded (a stop you moved on from leaves the rest undone); traded: so far
                    **{kind: [dict(c, traded=got.get(c["name"], 0), done=c["name"] not in still[kind] and (
                        not done.get("left") or got.get(c["name"], 0) >= (c.get("amount") or 1))) for c in r.get(kind) or []]
                       for kind, got in (("sell", trade_counts(r, done, "sold")), ("buy", trade_counts(r, done, "bought")))}}
        if rc.get("kind") == "exo":
            region = (outrider.bio.region_name(r["x"], r["y"], r["z"])
                      if outrider.bio and None not in (r["x"], r["y"], r["z"]) else None)
            known = codex_species(self.db, region)[1] if region else None
            bodies = exo_todo(r["bodies"], self.journals.exo_sampled(r["id64"]) if r["id64"] is not None else set())
            sp_all = [x for b in bodies for x in b["species"]]
            return {"i": i, "system": r["system"], "id": str(r["id64"]) if r["id64"] is not None else None,
                    "x": r["x"], "y": r["y"], "z": r["z"], "jumps": r["jumps"], "left": sum(b["left"] for b in bodies),
                    "value": sum(x["value"] or 0 for x in sp_all), "value_left": sum(x["value"] or 0 for x in sp_all if not x["done"]),
                    "bodies": [{"name": b["name"], "type": b["type"], "subtype": b["subtype"], "ls": b["ls"], "done": b["done"],
                                "left": b["left"], "species": [dict(x, new=known is not None and x["species"].lower() not in known)
                                                               for x in b["species"]]}
                               for b in bodies if b["species"]]}
        mapping = bool((rc.get("options") or {}).get("use_mapping_value"))
        scanned, mapped = self.journals.riches_marks(r["id64"]) if r["id64"] is not None else (set(), set())
        bodies = todo(r["bodies"], scanned, mapped, mapping)
        left = [b for b in bodies if not b["done"]]
        return {"i": i, "system": r["system"], "id": str(r["id64"]) if r["id64"] is not None else None,
                "x": r["x"], "y": r["y"], "z": r["z"], "jumps": r["jumps"], "left": len(left),
                "value": sum(body_value(b, mapping) or 0 for b in bodies),
                "value_left": sum(body_value(b, mapping) or 0 for b in left),
                "bodies": [{k: b[k] for k in ("name", "type", "subtype", "ls", "scan", "map", "terraformable", "scanned",
                                              "mapped", "done")} for b in bodies]}

    def riches_view(self):
        """GET /api/riches: the route with its progress (RICHES_AHEAD systems from where you are and the RICHES_DONE
        before), the plot under way, and what the plot form needs (position, range, defaults, clipboard)."""
        rc, rows = self.riches_state()
        route = None
        if rc:
            nx = self.riches_next(rc, rows)
            at = rc.get("at")
            base = at if at is not None else (nx if nx is not None else len(rows))
            first = max(0, base - RICHES_DONE)
            route = dict({k: rc.get(k) for k in ("id", "options", "created_ts", "at", "furthest", "off_route",
                                                  "arrival_ts", "done_ts")},
                         **{"kind": rc.get("kind") or "riches", "from": rows[0]["system"], "to": rows[-1]["system"],
                            "count": len(rows), "first": first,
                            "next": nx, "points": [[r["x"], r["z"]] for r in rows], "systems": [self.riches_system_out(rc, rows, i)
                                                    for i in range(first, min(len(rows), first + RICHES_DONE + RICHES_AHEAD))]})
        cb = self.clipboard.info() if self.clipboard else {"enabled": self.highway_cfg["clipboard"], "available": False,
                                                           "tool": None, "why": "not started", "last": None}
        ship = self.fleet_ship((self.journals.ship or {}).get("ship_id"))
        fig = (ship or {}).get("figures") or {}
        cargo = (self.journals.cargo or {}).get("count") or 0
        return {"route": route, "plotting": self.riches_plotting, "position": with_id(self.journals.pos),
                "range": round(fleet_range(fig, cargo), 2) if ship and fleet_range(fig, cargo) else None,
                "defaults": dict(RICHES), "trade": self.trade_defaults(), "clipboard": cb}

    def trade_defaults(self):
        """The trade plot form's defaults: outrider.cargo.TRADE, and from your journal the station you are docked at,
        your credits, your ship's hold and whether it needs a large pad."""
        j, ship = self.journals, self.journals.ship or {}
        dk = self.docked_summary() or {}
        pos = j.pos or {}
        return dict(outrider.cargo.TRADE, station=dk.get("station") if dk.get("system") in (None, pos.get("name")) else None,
                    capital=(self.commander_summary() or {}).get("credits"), max_cargo=ship.get("cargo_capacity"),
                    requires_large_pad=outrider.cargo.SHIP_PAD.get((ship.get("type") or "").lower()) == outrider.cargo.LARGE)

    def riches_start_plot(self, body):
        """POST /api/riches/plot: check the request, start the Spansh job in the background, (answer, HTTP status).
        {from (default: where you are), to (optional), range (default: the current ship's), radius, max_results,
        max_distance, min_value, use_mapping_value, avoid_thargoids, loop}."""
        if self.riches_task and not self.riches_task.done():
            return {"error": "a route is being plotted already"}, 409
        kind = body.get("kind", "riches")   # the slot's route type: Road to Riches, Expressway to Exomastery, or trade
        if kind not in ("riches", "exo", "trade"):
            return {"error": "kind must be riches, exo or trade"}, 400
        if kind == "trade":
            return self.trade_start_plot(body)
        name = lambda v: " ".join(v.split()) if isinstance(v, str) else ""
        frm = name(body.get("from")) or (self.journals.pos or {}).get("name") or ""
        to = name(body.get("to"))
        if not frm or len(frm) > FIND_NAME_MAX or len(to) > FIND_NAME_MAX:
            return {"error": f"give the start system's name (up to {FIND_NAME_MAX} characters)"}, 400

        def number(k, lo, hi, conv=float, default=None):
            v = body.get(k)
            if v is None or v == "":
                return default
            try:
                if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                    raise ValueError(k)
                v = conv(float(v))
            except (ValueError, OverflowError):
                raise ValueError(f"{k} is not a number") from None
            if not (lo <= v <= hi):
                raise ValueError(f"{k} is out of range ({lo:g} to {hi:g})")
            return v

        def flag(k):
            v = body.get(k, RICHES[k])
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be true or false")
            return v
        ship = self.fleet_ship((self.journals.ship or {}).get("ship_id"))
        cargo = (self.journals.cargo or {}).get("count") or 0
        try:
            rng = number("range", 1, 1000, float, fleet_range((ship or {}).get("figures") or {}, cargo) if ship else None)
            if not rng:
                return {"error": "give the jump range (ly), or fly a ship Outrider has seen a Loadout of"}, 400
            opts = {"range": round(rng, 2), "radius": number("radius", 1, 1000, float, RICHES["radius"]),
                    "max_results": number("max_results", 1, 500, int, RICHES["max_results"]),
                    "max_distance": number("max_distance", 1, 1000000, float, RICHES["max_distance"]),
                    "min_value": number("min_value", 0, 1000000000, int, RICHES["min_value"]),
                    "use_mapping_value": flag("use_mapping_value"), "avoid_thargoids": flag("avoid_thargoids"),
                    "loop": flag("loop")}
        except ValueError as e:
            return {"error": str(e)}, 400
        if kind == "exo":   # Exomastery has no mapping value; its life is what counts
            opts.pop("use_mapping_value")
        params = dict(opts, **{"from": frm}, **({"to": to} if to else {}))
        for k in ("use_mapping_value", "avoid_thargoids", "loop"):
            if k in params:
                params[k] = int(params[k])
        self.riches_plotting = {"state": "running", "kind": kind, "from": frm, "to": to or None, "started": iso_ts(time.time()),
                                "error": None}
        self.riches_task = asyncio.get_running_loop().create_task(self._riches_plot(params, {"options": opts, "kind": kind}))
        self.bump()
        return {"ok": True, "plotting": self.riches_plotting}, 202

    def trade_start_plot(self, body):
        """POST /api/riches/plot {kind: "trade"}: Spansh's trade planner from a station (default: the one you are docked
        at), with your capital and hold (defaults from your journal), hops, hop distance (ly), distance from the star
        (ls), data age (days) and the pad and allow flags. The route takes the survey slot, as a survey route does."""
        d = self.trade_defaults()
        name = lambda v: " ".join(v.split()) if isinstance(v, str) else ""
        frm = name(body.get("from")) or (self.journals.pos or {}).get("name") or ""
        station = name(body.get("station")) or (d["station"] if not name(body.get("from")) else "") or ""
        if not frm or not station or len(frm) > FIND_NAME_MAX or len(station) > FIND_NAME_MAX:
            return {"error": "give the system and the station to start from (docked, they are filled in)"}, 400

        def whole(k, lo, hi, default):
            v = body.get(k)
            if v is None or v == "":
                v = default
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(f"{k} is not a number")
            try:
                v = int(float(v))
            except (ValueError, OverflowError):
                raise ValueError(f"{k} is not a number") from None
            if not lo <= v <= hi:
                raise ValueError(f"{k} is out of range ({lo:,} to {hi:,})")
            return v

        def flag(k, default):
            v = body.get(k, default)
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be true or false")
            return v
        try:
            if d["capital"] is None and body.get("capital") in (None, ""):
                raise ValueError("give your capital (credits): no LoadGame read yet")
            if d["max_cargo"] is None and body.get("max_cargo") in (None, ""):
                raise ValueError("give the hold (t): no Loadout read yet")
            opts = {"station": station, "capital": whole("capital", 0, 10 ** 13, d["capital"]),
                    "max_cargo": whole("max_cargo", 1, 10000, d["max_cargo"]),
                    "max_hops": whole("max_hops", 1, 20, d["max_hops"]),
                    "max_hop_distance": whole("max_hop_distance", 1, 1000, d["max_hop_distance"]),
                    "max_system_distance": whole("max_system_distance", 1, 1000000, d["max_system_distance"]),
                    "max_price_age_days": whole("max_price_age_days", 1, 365, d["max_price_age_days"]),
                    "requires_large_pad": flag("requires_large_pad", d["requires_large_pad"])}
            opts.update({k: flag(k, d[k]) for k in ("allow_planetary", "allow_player_owned", "allow_prohibited", "permit", "unique")})
        except ValueError as e:
            return {"error": str(e)}, 400
        params = {"system": frm, "station": station, "starting_capital": opts["capital"], "max_cargo": opts["max_cargo"],
                  "max_hops": opts["max_hops"], "max_hop_distance": opts["max_hop_distance"],
                  "max_system_distance": opts["max_system_distance"], "max_price_age": opts["max_price_age_days"] * 86400,
                  **{k: int(opts[k]) for k in ("requires_large_pad", "allow_planetary", "allow_player_owned",
                                               "allow_prohibited", "permit", "unique")}}
        self.riches_plotting = {"state": "running", "kind": "trade", "from": f"{station}, {frm}", "to": None,
                                "started": iso_ts(time.time()), "error": None}
        self.riches_task = asyncio.get_running_loop().create_task(self._riches_plot(params, {"options": opts, "kind": "trade"}))
        self.bump()
        return {"ok": True, "plotting": self.riches_plotting}, 202

    async def _riches_plot(self, params, meta):
        p = self.riches_plotting
        kind = meta.get("kind")
        try:
            start = end = note = None
            if kind != "trade":
                # an end Spansh does not know yet is stood in for, as the Highway's are (State.highway_ends). Not a
                # trade route: it starts at a station's market as Spansh has it, which no stand-in replaces
                src, dst, start, end, note = await self.highway_ends(params["from"], params.get("to"), params["range"])
                params = dict(params, **{"from": src["name"]}, **({"to": dst["name"]} if dst else {}))
            result = await self.spansh.plot(SPANSH_TRADE if kind == "trade" else SPANSH_EXO if kind == "exo" else SPANSH_RICHES,
                                            params, method=RICHES_METHOD, timeout=TRADE_PLOT_TIMEOUT if kind == "trade" else None)
            rows = trade_rows(result) if kind == "trade" else splice_survey(riches_rows(result), params["range"], start, end)
            if kind == "trade" and not rows:
                raise RichesError("Spansh found no trade route from there with these limits")
            self.riches_store(rows, dict(meta, stand_in=note) if note else meta)
            p.update(state="done", note=note)
            self.riches_copy_next(force=True)   # you are usually at its start: the first hop is ready to paste
        except (HighwayError, RichesError) as e:
            p.update(state="failed", error=str(e))
        except Exception as e:  # noqa: BLE001 -- say it on the page rather than lose it in a task
            import traceback
            traceback.print_exc()
            p.update(state="failed", error=f"{type(e).__name__}: {e}")
        finally:
            p["ended"] = iso_ts(time.time())
            self.bump()

    def riches_store(self, rows, meta):
        """A new route replaces the old one: its rows and bodies, and its meta with where you are on it now."""
        self.cancel_autotarget(route="survey")   # a 🎯 run aimed at the old route's system
        self.db.execute("DELETE FROM riches_route")
        self.db.execute("DELETE FROM riches_bodies")
        self.db.executemany("INSERT INTO riches_route (idx, system, id64, x, y, z, jumps) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [(i, r["system"], r["id64"], r["x"], r["y"], r["z"], r["jumps"]) for i, r in enumerate(rows)])
        self.db.executemany(
            "INSERT INTO riches_bodies (idx, n, name, type, subtype, ls, scan, map, terraformable, body_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(i, n, b["name"], b["type"], b["subtype"], b["ls"], b["scan"], b["map"], b["terraformable"], b["body_id"])
             for i, r in enumerate(rows) for n, b in enumerate(r["bodies"])])
        self.db.execute("DELETE FROM trade_stops")
        self.db.executemany(
            "INSERT INTO trade_stops (idx, station, market_id, ls, updated, distance, sell, buy, profit, cumulative)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(i, r["station"], r["market_id"], r["ls"], r["updated"], r["distance"], json.dumps(r["sell"]),
              json.dumps(r["buy"]), r["profit"], r["cumulative"]) for i, r in enumerate(rows) if "station" in r])
        self.db.execute("DELETE FROM riches_species")
        self.db.executemany(
            "INSERT INTO riches_species (idx, n, k, genus, species, value, count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(i, n, k, x["genus"], x["species"], x["value"], x["count"])
             for i, r in enumerate(rows) for n, b in enumerate(r["bodies"]) for k, x in enumerate(b.get("species") or [])])
        pos = self.journals.pos
        i = riches_match(rows, pos["id64"], pos["name"]) if pos else None
        now = time.time()
        rc = dict(meta, id=f"{now:.6f}", created_ts=iso_ts(now), since_ts=(pos or {}).get("ts"), at=i, furthest=i,
                  off_route=None, arrival_ts=None, done_ts=None, said_done=None)
        meta_set(self.db, "riches", rc)
        self.db.commit()
        self._rc_copied = None
        return rc

    def riches_clear(self):
        """POST /api/riches/clear: forget the route (and stop a plot under way)."""
        if self.riches_task and not self.riches_task.done():
            self.riches_task.cancel()
            if self.riches_plotting:
                self.riches_plotting.update(state="failed", error="cancelled")
        self.cancel_autotarget(route="survey")
        self.db.execute("DELETE FROM riches_route")
        self.db.execute("DELETE FROM riches_bodies")
        self.db.execute("DELETE FROM riches_species")
        self.db.execute("DELETE FROM trade_stops")
        meta_set(self.db, "riches", None)
        self.db.commit()
        self.bump()

    def survey_summary(self):
        """The survey route's (Road to Riches, Exomastery) facts for the line under the tiles, or None with no route:
        as highway_summary, the next system (jumps, ly from here), where you are on it, and what is left where you are."""
        rc, rows = self.riches_state()
        if not rc:
            return None
        pos, n = self.journals.pos, len(rows)
        at, nx = rc.get("at"), self.riches_next(rc, rows)
        nxt = rows[nx] if nx is not None else None
        return {
            "kind": rc.get("kind") or "riches", "id": rc.get("id"), "created_ts": rc.get("created_ts"),
            "destination": rows[-1]["system"], "total": n - 1, "index": nx, "at": at,
            "complete": bool(rc.get("done_ts")), "off_route": bool(rc.get("off_route")),
            "left_here": len(self.journals.riches_left(rc, rows, at)) if at is not None else None,
            "next": nxt and {"name": nxt["system"], "id": str(nxt["id64"]) if nxt["id64"] is not None else None,
                             "jumps": nxt["jumps"], "station": nxt.get("station"),
                             "distance": round(dist(pos, nxt), 1) if pos and None not in (nxt["x"], nxt["y"], nxt["z"])
                             else None},
        }

    def route_newest(self):
        """"highway" or "riches": of the two routes, the one plotted last (None without either). With both, only that
        one copies its next system to the clipboard on arrival: one copy per jump, not two racing for it."""
        hw, rc = meta_get(self.db, "highway"), meta_get(self.db, "riches")
        if not (hw and rc):
            return "highway" if hw else "riches" if rc else None
        return "riches" if (rc.get("created_ts") or "") > (hw.get("created_ts") or "") else "highway"

    def riches_copy_next(self, force=False):
        """After an arrival on the route (live, HIGHWAY_LIVE_S), or a new plot (force): copy the next system's name to
        the desktop clipboard, once per arrival (the same clipboard and switch as the Highway's)."""
        rc, rows = self.riches_state()
        cb = self.clipboard
        if not rc or not cb or not cb.enabled or not cb.tool:
            return False
        key = rc.get("arrival_ts") or rc.get("created_ts")
        if key == self._rc_copied and not force:
            return False
        self._rc_copied = key
        if self.route_newest() != "riches":   # a Highway route plotted since has the clipboard
            return False
        if rc.get("at") is None or rc.get("done_ts"):
            return False
        if not force and not (rc.get("arrival_ts") and live_event(rc["arrival_ts"]) and
                              time.time() - ts_seconds(rc["arrival_ts"]) <= HIGHWAY_LIVE_S):
            return False
        nx = self.riches_next(rc, rows)
        if nx is None:
            return False
        name = rows[nx]["system"]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop:
            fut = loop.run_in_executor(None, cb.copy, name)
            fut.add_done_callback(lambda _f: self.bump())
        else:
            cb.copy(name)
        return True

    # ---- auto-target (outrider/target.py): after a supercharge on the route, target the next system with key presses ----
    def autotarget_target(self, manual=False):
        """({name, id64, here, route, index}, None) when you are at a route system with a next one, else (None, why
        not). manual (Target next, Retry: review Q4): also off the route, where it is the CLOSEST route system (the
        line's "nearest", passed or not), and before the route's start, where it is the start."""
        hw, rows = self.highway_state()
        pos = self.journals.pos
        if not hw:
            return None, "no route is plotted"
        if not pos or pos.get("id64") is None:
            return None, "your position is not known yet"
        if hw.get("done_ts"):
            return None, "the highway is complete"
        if manual and hw.get("off_route"):
            near = self.highway_nearest(hw, rows)
            if not near or near.get("index") is None:
                return None, "no route system to get back to"
            nx = near["index"]
        else:
            at = hw.get("at")
            if (at is None and not manual) or (at is not None and rows[at]["id64"] not in (None, pos["id64"])):
                return None, "you are not at a system on the route"
            nx = self.highway_next(hw, rows)
            if nx is None:
                return None, "you are at the end of the route"
        r = rows[nx]
        if r["id64"] is None:
            return None, f"{r['system']} has no id64 to check the target against"
        return {"name": r["system"], "id64": r["id64"], "here": pos["id64"], "route": hw.get("id"), "index": nx}, None

    def route_target(self, route, index):
        """({name, id64, here, route, index}, None) for 🎯 on a system of a route ("highway" or "survey": Road to Riches /
        Exomastery), or (None, why not): a row of the route plotted now, not the system you are in, with an id64 (the
        target is checked against Status.json's Destination by id64)."""
        if route not in ("highway", "survey"):
            return None, "route must be highway or survey"
        if isinstance(index, bool) or not isinstance(index, int):
            return None, "index must be a whole number"
        meta, rows = self.highway_state() if route == "highway" else self.riches_state()
        if not meta:
            return None, "no route is plotted"
        if not 0 <= index < len(rows):
            return None, f"the route has no system {index}"
        pos = self.journals.pos
        if not pos or pos.get("id64") is None:
            return None, "your position is not known yet"
        r = rows[index]
        if r["id64"] is None:
            return None, f"{r['system']} has no id64 to check the target against"
        if r["id64"] == pos["id64"]:
            return None, f"you are in {r['system']} already"
        return {"name": r["system"], "id64": r["id64"], "here": pos["id64"], "route": meta.get("id"), "index": index}, None

    def autotarget_test_target(self):
        """({name, id64, here}, None) for "test now": the nearest system in the Nearby list within 90% of the range
        you have now (a plain jump, no neutron needed, no route needed), else (None, why not)."""
        pos = self.journals.pos
        if not pos or pos.get("id64") is None:
            return None, "your position is not known yet"
        rng = self.range_now() or (self.journals.jump_range or {}).get("ly")
        if not rng:
            return None, "your jump range is not known yet (no Loadout seen)"
        best = None
        for key, row in self.systems.items():
            d, id64 = row.get("distance"), row.get("id64", key)
            try:
                id64 = int(id64)
            except (TypeError, ValueError):
                continue
            if id64 == pos["id64"] or d is None or not 0 < d <= 0.9 * rng or not row.get("name"):
                continue
            if best is None or d < best[0]:
                best = (d, row["name"], id64)
        if not best:
            return None, f"no known system within {0.9 * rng:.1f} ly (90% of your {rng:.1f} ly range)"
        return {"name": best[1], "id64": best[2], "here": pos["id64"]}, None

    def autotarget_cfg(self):
        """The Targeter's settings from [highway] (autotarget_entry -> entry, ...)."""
        return {k[len("autotarget_"):]: v for k, v in self.highway_cfg.items()
                if k.startswith("autotarget_") and k[len("autotarget_"):] in outrider.target.DEFAULTS}

    def autotarget_info(self):
        """The Plot Route tab's auto-target block (in the payload, so the result shows as it comes)."""
        cfg, t, h = self.highway_cfg, self.targeter, self.honker
        info = {"enabled": bool(cfg["autotarget"]), "delay": cfg["autotarget_delay"], "entry": cfg.get("autotarget_entry"),
                "dry_run": bool(cfg.get("autotarget_dry_run")), "available": bool(t and t.available),
                "last": self.autotarget_last, "test": self.autotarget_test, "running": self.autotarget_running is not None,
                "missing": [], "steps": [], "countdown": self.autotarget_test_countdown}
        if not t:
            info["status"] = "not started"
            return info
        if not t.available:
            info["status"] = h.status if h else "not started"
            return info
        steps, missing = t.plan()
        info["missing"] = [{"key": n, "why": w} for n, w in missing]
        info["steps"] = t.describe(steps)
        info["status"] = ("off" if not cfg["autotarget"] else "dry run: logs the steps, presses nothing" if info["dry_run"]
                          else h.device_error or "the virtual keyboard is not open" if not h.ready
                          else "not ready: a key has no keyboard binding" if missing
                          else "ready" + outrider.honk.EXPERIMENTAL)   # "ready (experimental on Windows)" there
        return info

    # ---- the tablet's control rail (outrider/rail.py; tablet plan phase 4) ----
    def rail_sets(self):
        """Each context's buttons, [{id, label}], as edited on the tablet (meta "rail_sets", live-only), else the
        agreed defaults."""
        saved = meta_get(self.db, "rail_sets") or {}
        out = {}
        for c in outrider.rail.CONTEXTS:
            ok, _ = outrider.rail.check_set(c, saved.get(c)) if c in saved else (None, None)
            out[c] = ok if ok is not None else outrider.rail.default_set(c)
        return out

    def rail_save(self, context, buttons=None, reset=False):
        """POST /api/rail/sets: a context's edited set (or its defaults back): (answer, status)."""
        if context not in outrider.rail.CONTEXTS:
            return {"error": "unknown context"}, 400
        saved = dict(meta_get(self.db, "rail_sets") or {})
        if reset:
            saved.pop(context, None)
        else:
            ok, why = outrider.rail.check_set(context, buttons)
            if why:
                return {"error": why}, 400
            saved[context] = ok
        meta_set(self.db, "rail_sets", saved)
        self.db.commit()
        self.bump()
        return self.rail_info(full=True), 200

    def rail_why_not(self):
        """Why no button can be pressed now (None: they can), whatever the context: the keyboard's side."""
        if not self.game_pc:
            return NOT_GAME_PC
        if self.simulate:
            return "not with --simulate (nothing is pressed)"
        h = self.honker
        if not h or not h.available:
            return (h.status if h else "the virtual keyboard is not available") + " (the rail presses keys through it)"
        return None

    def rail_info(self, full=False):
        """The rail as the tablet draws it: the context you are in (or why there is no rail), its buttons with their
        bindings and the state Status.json gives each, and whether a press can be sent now. full: also every
        context's set and catalogue, for the editor (GET /api/rail)."""
        st = self.journals.status_json or {}
        ctx, why = outrider.rail.context_of(st, (self.journals.vehicle or {}).get("srv_type"))
        if not self.game_pc:
            ctx, why = None, NOT_GAME_PC
        out = {"context": ctx, "label": outrider.rail.CONTEXT_LABEL.get(ctx), "why": why, "buttons": [],
               "can_press": False, "why_not": None, "confirm_s": outrider.rail.RAIL_CONFIRM_S, "max": outrider.rail.RAIL_MAX}
        if ctx:
            sets = self.rail_sets()
            items = [dict(outrider.rail.catalogue_entry(ctx, b["id"]), label=b["label"]) for b in sets[ctx]]
            dirs = self.honker.journal_dirs if self.honker else LIVE_DIRS
            binds = outrider.honk.keyboard_bindings(dirs, [b["action"] for b in items], hint=None,
                                                    category=outrider.rail.CATEGORY[ctx])
            for b in items:
                keys, text = binds.get(b["action"], (None, "not read"))
                out["buttons"].append({"id": b["id"], "label": b["label"], "short": outrider.rail.short_label(b["label"]),
                                       "action": b["action"],
                                       "action_label": outrider.honk.action_label(b["action"]), "bound": bool(keys),
                                       "keys": text if keys else None, "why": None if keys else text,
                                       # where an unbound one is now (a HOTAS button), for the tablet's short line
                                       "now_on": (re.search(r"now only (.+?) on ", text or "") or [None, None])[1] if not keys else None,
                                       "state": outrider.rail.state_of(b, st), "reported": b["state"] is not None,
                                       "na": outrider.rail.NA_WHY.get(b["id"]) if outrider.rail.state_of(b, st) == "na" else None,
                                       "states": 3 if b["state"] == "headlights" else 2, "amber": b["amber"]})
            out["why_not"] = self.rail_why_not()
            out["can_press"] = out["why_not"] is None
        if full:
            sets = self.rail_sets()
            out["edit"] = {c: {"label": outrider.rail.CONTEXT_LABEL[c], "set": sets[c],
                               "catalogue": [{"id": b["id"], "label": b["label"], "action": b["action"]}
                                             for b in outrider.rail.CATALOGUE[c]]} for c in outrider.rail.CONTEXTS}
        return out

    def rail_device(self):
        """The virtual keyboard is kept open for the rail while the game is live (a device created at the moment of a
        press can be missed by the game), and let go when it is not. Never with --simulate."""
        h = self.honker
        if not h or not h.available or self.simulate:
            return
        live = bool((self.journals.status_json or {}).get("live"))
        if live and "rail" not in h.owners:
            h.open("rail")
        elif not live and "rail" in h.owners:
            h.close("rail")

    async def rail_press(self, context, id_):
        """POST /api/rail/press: one tap of that button's binding, only if it is in the CURRENT context's set, bound,
        and the game is live; refused with words otherwise (a press while auto honk or auto-target hold the keyboard
        too: never queued). (answer, status); the answer says the state before, for the tablet's SENT."""
        why = self.rail_why_not()
        if why:
            return {"error": why}, 409
        st = self.journals.status_json or {}
        ctx, why = outrider.rail.context_of(st, (self.journals.vehicle or {}).get("srv_type"))
        if not ctx:
            return {"error": f"no rail now: {why}"}, 409
        if ctx != context:
            return {"error": f"you are not in the {context} now ({outrider.rail.CONTEXT_LABEL[ctx]})"}, 409
        b = next((x for x in self.rail_info()["buttons"] if x["id"] == id_), None)
        if not b:
            return {"error": "no such button in this set"}, 404
        if not b["bound"]:
            return {"error": b["why"]}, 409
        keys, _ = outrider.honk.keyboard_bindings(self.honker.journal_dirs, [b["action"]], hint=None,
                                                  category=outrider.rail.CATEGORY[ctx])[b["action"]]
        if not self.honker.ready and not self.honker.open("rail"):
            return {"error": self.honker.device_error or "the virtual keyboard could not be opened"}, 409

        def still():   # under the keyboard's lock, just before the key: still in that context, game still live
            c, w = outrider.rail.context_of(self.journals.status_json, (self.journals.vehicle or {}).get("srv_type"))
            return None if c == context else f"no longer in the {context}" + (f" ({w})" if w else "")
        try:
            await asyncio.get_running_loop().run_in_executor(None, lambda: self.honker.tap(keys, check=still))
        except outrider.honk.NotNow as e:
            return {"error": str(e)}, 409
        except ValueError as e:
            return {"error": str(e)}, 409
        return {"ok": True, "id": id_, "label": b["label"], "before": b["state"], "confirm_s": outrider.rail.RAIL_CONFIRM_S}, 200

    def set_autotarget(self, enabled=None, delay=None):
        """The Plot Route tab's toggle and delay (remembered over restarts, like auto honk's toggle)."""
        if enabled is not None:
            self.highway_cfg["autotarget"] = bool(enabled)
        if delay is not None:
            self.highway_cfg["autotarget_delay"] = min(60.0, max(0.0, float(delay)))
        meta_set(self.db, "autotarget", {"enabled": self.highway_cfg["autotarget"], "delay": self.highway_cfg["autotarget_delay"]})
        self.db.commit()   # now: a failing watcher tick would roll it back
        if enabled is False:
            self.cancel_autotarget()   # a run under way stops now (the device may stay open for auto honk, CX-F1)
        if self.honker and self.honker.available and enabled is not None:
            if enabled and not self.highway_cfg.get("autotarget_dry_run"):   # a dry run presses nothing: no keyboard
                self.honker.open("target")
            elif not enabled:
                self.honker.close("target")
        self.bump()

    def cancel_autotarget(self, route=False):
        """Stop the automatic run, wherever it is: the delay, the wait for auto honk, or between two keys. route: the
        route was cleared or replaced ("survey" for Road to Riches / Exomastery; True or "highway" for the Highway's),
        which also stops a Target next / 🎯 run aimed at a system of that route. A "test now" run needs no route and is
        left alone."""
        which = "highway" if route is True else route
        aimed = self._autotarget_next_route
        for tok in (self._autotarget_cancel if which != "survey" else None,
                    self._autotarget_next_cancel if which and which == aimed else None):
            if tok is not None:
                tok.set()

    def maybe_autotarget(self, now=None):
        """A live FSD supercharge (JetConeBoost) in a route system with [highway] autotarget on: after autotarget_delay
        s, target the next system (one attempt per supercharge; nothing repeats on its own)."""
        b = self.journals.boost
        if not b or b.get("ts") == self._autotarget_boost:
            return False
        self._autotarget_boost = b.get("ts")
        now = time.time() if now is None else now
        if not self.highway_cfg["autotarget"]:
            return False
        try:
            if now - ts_seconds(b["ts"]) > HIGHWAY_LIVE_S:
                return False
        except (KeyError, TypeError, ValueError):
            return False
        tgt, _why = self.autotarget_target()
        if not tgt:
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:   # no event loop (a test driving tick() by hand): nothing to schedule
            return False
        if self.autotarget_busy():
            return False   # one sequence at a time: an automatic one, or a run the page or the button asked for
        self._autotarget_cancel = cancel = threading.Event()
        self.autotarget_task = loop.create_task(self._autotarget(tgt, cancel=cancel))
        return True

    def background_tasks(self):
        """The State's own background tasks, all cancelled at shutdown before the database closes (a survey or trade
        plot can run up to TRADE_PLOT_TIMEOUT: review 2026-10-08 #7, it was left running into the closed session)."""
        return [t for t in (self.refresh_task, self.target_task, self.unsold_task, self.seller_task, self.carrier_task,
                            self.searcher.task, self.honk_test_task, self.honk_run_task, self.highway_task, self.riches_task,
                            self.autotarget_task, self.autotarget_test_task, self.lease_task, self.edsm_discard_task,
                            *self.upload_tasks.values()) if t]

    def arrival_danger_until(self, now=None):
        """The game sets Status.json's in-danger flag on every use of the FSD, from the charge until some 15-26 s after
        a hyperspace arrival or entering supercruise (lifting off a planet...; logged in game 2026-10-09, any star,
        nothing near): no threat, but auto-target's guard refuses it. When that is all it can be (in danger, not
        interdicted, no jump charging, one of those here under AUTOTARGET_DANGER_WAIT s ago): the time a run may wait
        until for it to clear; else None. After a restart the arrival is only in pos (whose ts is the arrival's)."""
        st = self.journals.status_json or {}
        flags, T = st.get("flags") or 0, outrider.target
        if not flags & T.FLAG_IN_DANGER or flags & (T.FLAG_INTERDICTED | T.FLAG_FSD_CHARGING | T.FLAG_FSD_JUMP):
            return None
        pos = self.journals.pos or {}
        uses = [u["ts"] for u in (self.journals.jump_arrival or pos, self.journals.supercruise_entry)
                if u and u.get("id64") is not None and u.get("id64") == pos.get("id64") and isinstance(u.get("ts"), str)]
        try:
            until = ts_seconds(max(uses)) + AUTOTARGET_DANGER_WAIT if uses else None
        except (TypeError, ValueError):
            return None
        return until if until and (time.time() if now is None else now) < until else None

    def autotarget_busy(self):
        """A galaxy-map sequence is pending or running: the automatic one (after a supercharge) or one the page or the
        co-pilot button asked for. Only one may run at a time (review 2026-10-08 #1: a supercharge during Target next
        started a second run that overwrote the first's cancel token)."""
        return any(t and not t.done() for t in (self.autotarget_task, self.autotarget_test_task))

    def start_autotarget_test(self):
        """The Highway tab's "test now": one run against the nearest system a plain jump away (autotarget_test_target),
        whether or not auto-target is on. (response, HTTP status)."""
        return self.start_autotarget_run("test")

    def start_autotarget_run(self, kind="test", countdown=None, aim=None):
        """A run the page asked for, after a countdown (time to click back into the game: the click took the keyboard
        focus), whether or not auto-target is on. kind "test": "test now", against a system a plain jump away (no
        route needed); "next": Target next / Retry (review Q4), against the next route system or, off the route, the
        closest one; with `aim` (route, index): 🎯 on that system of that route (route_target). Refused, saying why,
        when it could not run. (response, HTTP status)."""
        t, h = self.targeter, self.honker
        if not t or not t.available:
            return {"error": (h.status if h else "not started")}, 400
        if self.autotarget_busy():
            return {"error": "auto-target is already running"}, 409
        tgt, why = (self.autotarget_test_target() if kind == "test" else self.route_target(*aim) if aim
                    else self.autotarget_target(manual=True))
        if not tgt:
            return {"error": why}, 400
        _steps, missing = t.plan()
        if missing:
            return {"error": "no keyboard binding for " + ", ".join(f"{n} ({w})" for n, w in missing)}, 400
        st, end = self.journals.status_json, lambda: self.journals.navroute_end
        g = outrider.target.guard(st, tgt["id64"], end)
        if g and g[0] == "danger" and self.arrival_danger_until():   # the arrival's own flag: the run waits it out,
            g = outrider.target.guard(dict(st, flags=st["flags"] & ~outrider.target.FLAG_IN_DANGER), tgt["id64"], end)
        if g and g[0] != "already":   # already the target: the run says so (and costs no key)
            return {"error": g[1]}, 400
        dry = bool(self.highway_cfg.get("autotarget_dry_run"))
        if not dry and not h.open("target-test"):
            return {"error": h.device_error or h.status}, 400
        wait = self.autotarget_test_countdown if countdown is None else countdown
        test = {"seq": (self.autotarget_test or {}).get("seq", 0) + 1, "kind": kind, "state": "counting",
                "system": tgt["name"], "why": None, "in": wait}
        cancel = None
        if kind == "next":   # a cleared or replaced route stops it (cancel_autotarget)
            self._autotarget_next_cancel = cancel = threading.Event()
            self._autotarget_next_route = aim[0] if aim else "highway"
        self.autotarget_test = test
        self.autotarget_test_task = asyncio.get_running_loop().create_task(self._autotarget_test(tgt, test, dry, cancel))
        self.bump()
        return {"system": tgt["name"], "in": wait, "seq": test["seq"], "dry_run": dry, "kind": kind}, 200

    async def _autotarget_test(self, tgt, test, dry, cancel=None):
        try:
            await self._autotarget(tgt, test, cancel)
        finally:
            if not dry and self.honker:
                self.honker.close("target-test")
            if test["state"] in ("counting", "running"):
                test.update(state="failed", why=test.get("why") or "stopped")
            self.bump()

    def _autotarget_stale(self, tgt, test, cancel):
        """Why an automatic run decided earlier should not go ahead now, or None: switched off, its token set, or the
        route it was decided on cleared or replaced. A test run only stops for its own token."""
        if cancel is not None and cancel.is_set():
            return "stopped"
        if test:
            return None
        if not self.highway_cfg["autotarget"]:
            return "switched off"
        if (meta_get(self.db, "highway") or {}).get("id") != tgt.get("route"):
            return "the route changed"
        return None

    async def _autotarget(self, tgt, test=None, cancel=None):
        """Wait (the delay, or the test's countdown), check again, let a running auto honk finish (honk first), then
        run the sequence on a worker thread and say how it went. cancel: the automatic run's token (cancel_autotarget)."""
        await asyncio.sleep(test.get("in", self.autotarget_test_countdown) if test else self.highway_cfg["autotarget_delay"])
        if test:
            test["state"] = "running"
            self.bump()
        if self._autotarget_stale(tgt, test, cancel):
            return   # switched off or the route changed meanwhile: nothing to say
        # pressed in the first seconds after a jump or entering supercruise: the game's in-danger flag is still on
        # (arrival_danger_until). Said once, then waited out
        until = self.arrival_danger_until()
        if until and (self.journals.pos or {}).get("id64") == tgt["here"]:
            secs = max(1, round(until - time.time()))
            self.journals.moment("autotarget", iso_ts(time.time()), ok=False, what="waiting", system=tgt["name"], secs=secs,
                                 text="Not targeting due to danger. I will keep trying until you are out of danger, "
                                      f"for up to {secs} seconds.")
            self.bump()
        while self.arrival_danger_until() and (self.journals.pos or {}).get("id64") == tgt["here"]:
            if self._autotarget_stale(tgt, test, cancel):
                return
            await asyncio.sleep(0.25)
        if (self.journals.pos or {}).get("id64") != tgt["here"]:   # jumped (or left) meanwhile: nothing to target
            return self._autotarget_done(tgt, {"ok": False, "phase": 0, "label": "wait", "why": "you had jumped"}, test, say=False)
        end = time.time() + AUTOTARGET_HONK_WAIT
        while self._honk_running is not None and time.time() < end:   # auto honk is due or holding: it goes first
            if self._autotarget_stale(tgt, test, cancel):
                return
            await asyncio.sleep(0.25)
        if self._autotarget_stale(tgt, test, cancel):
            return
        if self._honk_running is not None:
            return self._autotarget_done(tgt, {"ok": False, "phase": 0, "label": "wait for auto honk",
                                               "why": "auto honk was still running"}, test)
        if (self.journals.pos or {}).get("id64") != tgt["here"]:   # jumped during the honk wait
            return self._autotarget_done(tgt, {"ok": False, "phase": 0, "label": "wait", "why": "you had jumped"}, test, say=False)
        self.autotarget_running = tgt
        self.bump()
        try:
            res = await asyncio.get_running_loop().run_in_executor(None, functools.partial(
                self.targeter.run, tgt["name"], tgt["id64"], lambda: self.journals.status_json,
                lambda: (self.journals.pos or {}).get("id64"), cancel=cancel, origin=tgt["here"],
                route_end=lambda: self.journals.navroute_end))
        except Exception as e:  # noqa: BLE001 -- say so on the page rather than lose it in a task
            res = {"ok": False, "phase": 0, "label": "run", "why": f"{type(e).__name__}: {e}"}
        finally:
            self.autotarget_running = None
        # stopped on purpose (switched off, the route cleared or replaced): recorded, not spoken
        self._autotarget_done(tgt, res, test, say=not self._autotarget_stale(tgt, test, cancel))

    def _autotarget_done(self, tgt, res, test=None, say=True):
        name, ok = tgt["name"], bool(res.get("ok"))
        already = res.get("code") == "already"
        why = "already the target" if already else res.get("why")
        kind = (test.get("kind") or "test") if test else "auto"
        # route and index: the route row the run was for (its Retry button, while it is still the one to target)
        self.autotarget_last = {"system": name, "ts": iso_ts(time.time()), "done": ok or already, "phase": res.get("phase"),
                                "label": res.get("label"), "why": why, "dry_run": bool(res.get("dry_run")),
                                "test": kind == "test", "kind": kind, "route": tgt.get("route"), "index": tgt.get("index")}
        if test:
            test.update(state="done" if ok or already else "failed", why=why)
        print(f"highway auto-target{' test' if kind == 'test' else ' (target next)' if kind == 'next' else ''}: " + (
            f"targeted {name}" + (" (dry run, nothing pressed)" if res.get("dry_run") else "") if ok else
            f"{name} {why}" if already else f"failed to target {name} at step {res.get('phase')} ({res.get('label')}): {why}"))
        if say and not already and not res.get("dry_run"):
            wrong = res.get("wrong") if res.get("code") == "wrong" else None   # said by name: you must not jump to it (Q3)
            self.journals.moment("autotarget", iso_ts(time.time()), ok=ok, system=name, phase=res.get("phase"), why=why,
                                 text=(f"Successfully targeted neutron jump target {name}" if ok
                                       else f"Targeted the wrong system: {wrong}. Check before you jump." if wrong
                                       else f"Failed to target neutron jump target {name}"))
        self.bump()

    async def highway_suggest(self, q):
        """System names starting with q, from Spansh (cached per q)."""
        key = q.lower()
        if key in self._suggest:
            self._suggest.move_to_end(key)
            return self._suggest[key]
        names = await self.spansh.system_names(q)
        self._suggest[key] = names
        while len(self._suggest) > HIGHWAY_SUGGEST_CACHE:
            self._suggest.popitem(last=False)
        return names

    def sellers_summary(self):
        """Nearest places to sell from here: the nearest of each kind, preferring fresh entries (a carrier
        seen by Spansh weeks ago may be long gone), and the nearest permanent station."""
        cur, pos = meta_get(self.db, "sellers"), self.journals.pos
        if not cur or not pos:
            return None
        c = self.journals.carrier or {}
        def pick(lst):
            now = time.time()
            out = []
            for x in lst:
                if x.get("x") is not None:   # from where you are now, not where the list was fetched
                    x = dict(x, distance=round(dist(pos, x), 1))
                age = (now - ts_seconds(x["updated_at"])) / 86400 if x.get("updated_at") else None
                x["age_days"] = round(age, 1) if age is not None else None
                x["carrier"] = "Carrier" in (x.get("type") or "")
                x["yours"] = bool(c.get("callsign") and x.get("name") == c.get("callsign"))
                out.append(x)
            out.sort(key=lambda x: x["distance"])
            # a carrier reported under ~an hour ago has age_days 0.0: only None (no date) means unknown
            fresh = next((x for x in out if x["yours"] or not x["carrier"]
                          or (x["age_days"] if x["age_days"] is not None else 99) <= 14), None)
            station = next((x for x in out if not x["carrier"]), None)
            return {"nearest": out[0] if out else None, "fresh": fresh, "station": station}
        return {"from": cur["pos"].get("name"), "moved": round(dist(pos, cur["pos"]), 1),
                "uc": pick(cur["uc"]), "vista": pick(cur["vista"])}

    def maybe_unsold(self):
        """Re-estimate unsold data in a worker thread once the journal has settled a little."""
        if not self.unsold_dirty or time.time() - self.unsold_at < UNSOLD_MIN_SECONDS:
            return
        if self.unsold_task and not self.unsold_task.done():
            return
        self.unsold_dirty, self.unsold_at = False, time.time()
        started = self.unsold_at

        # the estimate before this login, once per login (This session's credits found; S10)
        login = (self.journals.commander or {}).get("login_ts")
        want = login if login and self.unsold_login[0] != login else None

        def work():
            return compute_unsold(), unsold_total_at(want) if want else None

        async def run():
            try:
                self.unsold, at_login = await asyncio.get_running_loop().run_in_executor(None, work)
                if want and at_login is not None:
                    self.unsold_login = (want, at_login)
                # when it was finished: an estimate finished before a sale's line cannot have seen that sale
                self.unsold_log = (self.unsold_log + [(iso_ts(time.time()), self.unsold)])[-UNSOLD_LOG:]
                old, self.system_values = self.system_values, self.unsold.pop("system_values", {})
                # rows carry per-system values: rebuild those whose value moved (usually none, as most
                # journal lines change nothing on board), without calling it new scan data
                moved = {n for n in set(old) | set(self.system_values) if old.get(n) != self.system_values.get(n)}
                if moved:
                    self.value_dirty |= {i for i, (_, b) in self.bases.items() if b.get("name") in moved}
            except (Exception, SystemExit) as e:  # read_events() fails if it finds no journals
                self.unsold = {"error": str(e)}
            self.unsold_from = started
            self.bump()
        self.unsold_task = asyncio.create_task(run())

    def maybe_sale_left(self, now=None):
        """Once a live sale's pages have stopped coming (SALE_QUIET_S with no further page: Universal
        Cartographics sells 50 systems a page) and an estimate started after the last page has finished, say
        what it left aboard: a sale_left moment when cartographic data is still unsold after a cartographic
        sale, bio_left when completed samples are after a Vista Genomics one. The run is only ever filled by
        live sales (Journals.note_live_sale), so a re-read or catch-up says nothing."""
        run = self.journals.sale_run
        now = time.time() if now is None else now
        if not run or now - run["read_at"] < SALE_QUIET_S:
            return
        if self.unsold_from <= run["read_at"]:   # no estimate yet that began after the last page was read
            if now - run["read_at"] > SALE_LEFT_GIVE_UP_S:
                self.journals.sale_run = None
            return
        self.journals.sale_run = None
        u = self.unsold or {}
        if "error" in u:
            return
        c, b, ts = u.get("carto") or {}, u.get("bio") or {}, iso_ts(now)
        if "carto" in run["kinds"] and (c.get("systems") or 0) > 0 and (c.get("estimated_payout") or 0) > 0:
            self.journals.moment("sale_left", ts, sold_systems=run["systems"], sold_value=run["carto"],
                                 left_systems=c["systems"], left_value=c["estimated_payout"],
                                 left_firsts=c.get("first_discoveries") or 0)
        if "bio" in run["kinds"] and (b.get("samples") or 0) > 0 and (b.get("estimated_value") or 0) > 0:
            self.journals.moment("bio_left", ts, sold_species=run["species"], sold_value=run["bio"],
                                 left_samples=b["samples"], left_value=b["estimated_value"])

    async def watch(self):
        """Tail the live journals and NavRoute.json forever."""
        route_mtimes = {}
        while True:
            self.tick(route_mtimes)
            await asyncio.sleep(POLL_SECONDS)

    def tick(self, route_mtimes):
        """One pass of watch(): read what is new, commit, then the follow-up work."""
        cp, committed = self.journals.checkpoint(), False
        # a NavRoute.json read inside a tick that is rolled back must be read again (its rows went with it)
        mtimes_before = dict(route_mtimes)
        # the error shown is this tick's: a row that failed to build sets it again below, and stays visible
        last_error, self.tail_error = self.tail_error, None
        seq_before = self.journals.moment_seq
        try:
            for d in LIVE_DIRS:
                if self.journals.scan_dir(d, upload="live"):
                    self.unsold_dirty = True
                nr = os.path.join(d, "NavRoute.json")
                try:
                    m = os.path.getmtime(nr)
                except OSError:
                    m = None
                if m and route_mtimes.get(nr) != m:
                    route_mtimes[nr] = m
                    self.journals.read_navroute(d)
                for fname, read in (("Cargo.json", self.journals.read_cargo_file), ("Market.json", self.journals.read_market)):
                    fp = os.path.join(d, fname)
                    try:
                        m = os.path.getmtime(fp)
                    except OSError:
                        m = None
                    if m and route_mtimes.get(fp) != m:
                        route_mtimes[fp] = m
                        if read(d):
                            self.bump()
                sj = os.path.join(d, "Status.json")
                try:
                    m = os.path.getmtime(sj)
                except OSError:
                    m = None
                if m and route_mtimes.get(sj) != m:
                    route_mtimes[sj] = m
                    before = self.journals.status_json
                    self.journals.read_status(d)
                    self.uploads_hub.status(self.journals.status_json)   # EDDN's codex entries name the body from it
                    gist = lambda st: st and (round(st.get("fuel_main") or 0, 1), st.get("flags"), st.get("flags2"),
                                              st.get("body"), json.dumps(st.get("destination")), st.get("live"),
                                              st.get("selected_weapon"))
                    if gist(self.journals.status_json) != gist(before):
                        self.bump()
                    sm = self.sampling_summary()
                    skey = sm and (sm.get("clear"), (sm.get("to_go") or 0) // 10, sm.get("samples"), bool(sm.get("elsewhere")))
                    if skey != self._sampling_key:   # walking away from a sample: keep the countdown moving
                        self._sampling_key = skey
                        self.bump()
                    if self.surface_moved(time.monotonic()):   # the surface map follows you (5 m, 10°, 2/s at most)
                        self.bump()
            if self.journals.settle_carrier(time.time()):
                self.bump()
            self.uploads_hub.idle()   # EDDN: a companion file written after its line, signals after a quiet spell
            self.rail_device()
            self.db.commit()
            committed = True
            # after the commit: its moments (scoop ended, FSS closed early) are live only and it consumes what
            # raised them, so a rollback of this tick must not take them away (the retry could not raise them again)
            # each follow-up on its own: one that keeps raising (a bug, stored state of an unexpected shape) must not
            # starve the ones after it, several of which only fire within a short window (review S5). A database
            # error stops the rest (they would fail the same way) and goes to the handler below.
            for name, step in (("watch_status", lambda: self.watch_status(time.time())), ("maybe_refresh", self.maybe_refresh),
                               ("apply_own_changes", self.apply_own_changes), ("maybe_classify_target", self.maybe_classify_target),
                               ("maybe_unsold", self.maybe_unsold), ("maybe_sale_left", self.maybe_sale_left),
                               ("maybe_locate_carrier", self.maybe_locate_carrier), ("maybe_find_sellers", self.maybe_find_sellers),
                               ("maybe_backup_on_quit", self.maybe_backup_on_quit), ("highway_copy_next", self.highway_copy_next), ("riches_copy_next", self.riches_copy_next),
                               ("highway_heavy_check", self.highway_heavy_check), ("maybe_autotarget", self.maybe_autotarget)):
                try:
                    step()
                except sqlite3.Error:
                    raise
                except Exception as e:  # noqa: BLE001 -- reported on the page; the next follow-up still runs
                    self.follow_up_failed(name, e)
            # a new moment (approach, left body, FSD supercharged...) is a call-out: the long poll answers now,
            # not at the next unrelated bump
            if self.tail_error != last_error or self.journals.moment_seq != seq_before:
                self.bump()
        except Exception as e:
            # Never let one bad line, a locked database or a malformed NavRoute stop the
            # tailing for good: report it on the page and try again next tick.
            import traceback
            traceback.print_exc()
            # the sales of a committed tick are not read again: keep them for note_sale_estimates on the retry
            sales = self.journals.new_sales if committed else []
            try:
                self.db.rollback()
                self.journals.reload()   # memory back to what the database holds, so the retry is exact
            except sqlite3.Error:
                pass
            if committed:
                self.journals.new_sales = sales
            if not committed:   # the lines are read again: their moments and codex counts must not double
                self.journals.restore(cp)
                route_mtimes.clear()
                route_mtimes.update(mtimes_before)
            self.tail_error = f"{type(e).__name__}: {e}"
            self.bump()

    # ---- [server] password: sessions for devices on the network (outrider/auth.py) ----
    def session_secret(self):
        """The per-install secret session tokens are signed with (kept in the database, made on first use)."""
        sec = meta_get(self.db, "session_secret")
        if not (isinstance(sec, str) and len(sec) >= 32):
            sec = outrider.auth.new_secret()
            meta_set(self.db, "session_secret", sec)
            self.db.commit()
        return sec

    def new_session(self):
        return outrider.auth.make_token(self.session_secret(), self.password)

    def session_ok(self, token):
        """Whether a request's token is a live session (the password set, the token signed for it, not signed out)."""
        if not self.password or not token:
            return False
        return outrider.auth.check_token(self.session_secret(), self.password, token,
                                         set(meta_get(self.db, "revoked_sessions") or []))

    def end_session(self, token):
        """Sign out: that token's id joins the revoked list (kept over restarts), the others stay signed in."""
        sid = outrider.auth.token_id(token)
        if not sid or not self.session_ok(token):
            return False
        revoked = [x for x in meta_get(self.db, "revoked_sessions") or [] if x != sid] + [sid]
        meta_set(self.db, "revoked_sessions", revoked[-REVOKED_KEEP:])
        self.db.commit()
        return True

    def follow_up_failed(self, name, e):
        """One of tick()'s follow-ups raised: its traceback printed once (not every second), what it wrote rolled
        back and the reader's memory reloaded (the sales already read are kept for note_sale_estimates), and the
        error shown on the page, as a failed tick does."""
        import traceback
        key = (name, type(e).__name__, str(e))
        if key not in self._follow_up_seen:
            self._follow_up_seen.add(key)
            traceback.print_exc()
        sales = self.journals.new_sales
        try:
            self.db.rollback()
            self.journals.reload()
        except sqlite3.Error:
            pass
        self.journals.new_sales = sales
        self.tail_error = f"{name}: {type(e).__name__}: {e}"


def unsold_total_at(ts):
    """outrider.unsold's total estimate over the journal events before ts (the unsold data aboard at a login), or None."""
    try:
        cut = outrider.unsold.parse_ts(ts)
        args = argparse.Namespace(commander=None, since=None, ignore_deaths=False, bonus_rate=None,
                                  efficiency_bonus=False, no_odyssey=False, top=0)
        result = outrider.unsold.analyse([e for e in outrider.unsold.read_events(LIVE_DIRS + LEGACY_DIRS) if e[0] < cut], args)
    except (Exception, SystemExit):
        return None
    return result["exploration"]["estimated_payout"] + result["exobiology"]["estimated_value"]


def compute_unsold():
    """outrider.unsold's estimate of the cartographic and exobiology data on board, trimmed for the page."""
    args = argparse.Namespace(commander=None, since=None, ignore_deaths=False, bonus_rate=None,
                              efficiency_bonus=False, no_odyssey=False, top=0)
    started = iso_ts(time.time())   # before the journals are read: a sale stamped after it may not be counted
    result = outrider.unsold.analyse(outrider.unsold.read_events(LIVE_DIRS + LEGACY_DIRS), args)
    ex, bio = result["exploration"], result["exobiology"]
    total = ex["estimated_payout"] + bio["estimated_value"]
    system_values = {}
    for r in ex["rows"]:
        system_values[r["system"]] = system_values.get(r["system"], 0) + r["value"]
    return {
        "carto": {k: ex[k] for k in ("estimated_value", "estimated_payout", "payout_ratio", "payout_note", "npc_crew",
                                     "bodies", "systems", "first_discoveries", "mapped", "last_sold", "cutoff",
                                     "full_scan_bonus", "full_scan_systems")},
        "system_values": system_values,
        "bio": {k: bio[k] for k in ("estimated_value", "base_value", "max_value", "samples",
                                    "x5_runs", "x1_runs", "unknown_runs", "bonus_rate", "bonus_rate_source", "unknown_species",
                                    "last_sold", "cutoff")},
        "species": [{"species": r["species"], "count": r["count"], "value": r["value"]}
                    for r in bio["rows"][:8]],
        # the ten most valuable bodies aboard: the finds of this trip
        "top_bodies": [{"body": r["body"], "system": r["system"], "type": r["type"], "value": r["value"],
                        "first_discovered": r["first_discovered"], "mapped": r.get("mapped")}
                       for r in sorted(ex["rows"], key=lambda r: -r["value"])[:10]],
        "firsts": {
            "systems": sum(1 for r in ex["rows"] if r["first_discovered"] and r.get("arrival")),
            "stars": sum(1 for r in ex["rows"] if r["first_discovered"] and r.get("star")),
            "planets": sum(1 for r in ex["rows"] if r["first_discovered"] and r.get("planet")),
            "mapped": sum(1 for r in ex["rows"] if r.get("first_mapped")),
        },
        "total": total,
        "level": "urgent" if total >= UNSOLD_URGENT else "warn" if total >= UNSOLD_WARN else "ok",
        "thresholds": [UNSOLD_WARN, UNSOLD_URGENT],
        "computed": time.strftime("%H:%M:%S"),
        "computed_at": started,   # comparable with journal times: the page knows an estimate from before a sale (F39)
    }


# --------------------------------------------------------------------------
# Search: systems within a radius that have given stars, planets, rings or hotspots
# --------------------------------------------------------------------------

_SCOOP = [
    ("O", ["O (Blue-White) Star"]),
    ("B", ["B (Blue-White) Star", "B (Blue-White super giant) Star"]),
    ("A", ["A (Blue-White) Star", "A (Blue-White super giant) Star"]),
    ("F", ["F (White) Star", "F (White super giant) Star"]),
    ("G", ["G (White-Yellow) Star", "G (White-Yellow super giant) Star"]),
    ("K", ["K (Yellow-Orange) Star", "K (Yellow-Orange giant) Star"]),
    ("M", ["M (Red dwarf) Star", "M (Red giant) Star", "M (Red super giant) Star"]),
]
_OTHER_STARS = [
    ("wd", "White dwarf", [f"White Dwarf ({c}) Star" for c in
                           ("D", "DA", "DAB", "DAZ", "DAV", "DB", "DBZ", "DBV", "DQ", "DC", "DCV")]),
    ("n", "Neutron star", ["Neutron Star"]),
    ("bh", "Black hole", ["Black Hole", "Supermassive Black Hole"]),
    ("bd", "Brown dwarf (L/T/Y)", ["L (Brown dwarf) Star", "T (Brown dwarf) Star", "Y (Brown dwarf) Star"]),
    ("tts", "T Tauri", ["T Tauri Star"]),
    ("aebe", "Herbig Ae/Be", ["Herbig Ae/Be Star"]),
    ("wr", "Wolf-Rayet", ["Wolf-Rayet Star", "Wolf-Rayet N Star", "Wolf-Rayet NC Star",
                          "Wolf-Rayet C Star", "Wolf-Rayet O Star"]),
    ("c", "Carbon star", ["C Star", "CN Star", "CJ Star"]),
    ("ms", "MS / S-type", ["MS-type Star", "S-type Star"]),
]
STAR_GROUPS = {k: v for k, v in _SCOOP} | {k: v for k, _, v in _OTHER_STARS}
PLANET_TYPES = [
    "Earth-like world", "Water world", "Ammonia world", "Metal-rich body", "High metal content world",
    "Rocky body", "Rocky Ice world", "Icy body", "Water giant", "Gas giant with water-based life",
    "Gas giant with ammonia-based life", "Class I gas giant", "Class II gas giant", "Class III gas giant",
    "Class IV gas giant", "Class V gas giant", "Helium-rich gas giant", "Helium gas giant",
]
RING_TYPES = ["Icy", "Rocky", "Metal Rich", "Metallic"]

# Exobiology you have not finished sampling, by what the rest could pay (plain Vista Genomics prices,
# no first-footfall x5): key -> (label, credits threshold).
BIO_SEARCH = {"any": ("Unscanned bio signals", 0), "1m": ("Unscanned bio signals, > 1 mil", 1_000_000),
              "5m": ("Unscanned bio signals, > 5 mil", 5_000_000), "10m": ("Unscanned bio signals, > 10 mil", 10_000_000)}

SEARCH_OPTIONS = {
    "scoopable": [k for k, _ in _SCOOP],
    "other_stars": [[k, label] for k, label, _ in _OTHER_STARS],
    "planets": PLANET_TYPES, "rings": RING_TYPES, "hotspots": HOTSPOT_MINERALS,
    "bio": [[k, label] for k, (label, _) in BIO_SEARCH.items()],
    "mining": mining_minerals(),
}

SEARCH_MAX_RADIUS = {"local": 5000, "spansh": 500}
SEARCH_PAGES_PER_QUERY = 6        # 3000 bodies per Spansh query before we call it truncated
SEARCH_MAX_RESULTS = 1000


def record_from_body_search(b):
    """A Spansh /bodies/search result -> body record (with what the exobiology rules can use: the
    search leaves out volcanism, so species guesses from it are broader than from a full dump)."""
    rings = []
    for r in b.get("rings") or []:
        rings.append({"name": short_name(b.get("name"), r.get("name")), "type": r.get("type"),
                      "hotspots": minerals({s["name"]: s["count"] for s in r.get("signals") or []})})
    st = b.get("subtype")
    signals = {s.get("name"): s.get("count", 0) for s in b.get("signals") or []}
    return {"name": short_name(b.get("system_name"), b.get("name")), "type": b.get("type"),
            "subtype": st, "main": bool(b.get("is_main_star")), "main_known": True, "scoopable": subtype_scoopable(st),
            "rings": rings, "full": True,
            "bio": signals.get("Biological", 0), "geo": signals.get("Geological", 0),
            "body_id": b.get("body_id"), "landable": bool(b.get("is_landable")),
            "gravity": b.get("gravity"), "atmosphere": b.get("atmosphere"), "temperature": b.get("surface_temperature"),
            "pressure": b.get("surface_pressure"), "dist_ls": b.get("distance_to_arrival"),
            # the search names parent stars directly ([{type, subtype, id64}]) rather than by body id
            "parent_star_types": [p.get("subtype") for p in b.get("parents") or [] if p.get("type") == "Star" and p.get("subtype")],
            "orbital_period_s": round(b["orbital_period"] * 86400) if b.get("orbital_period") else None,
            "atmo_comp": ({a.get("name"): a.get("share") for a in b["atmosphere_composition"]}
                          if isinstance(b.get("atmosphere_composition"), list) else b.get("atmosphere_composition")),
            "materials": surface_materials(b.get("materials"))}


def bio_hits(db, id64, system, x, y, z, records, threshold):
    """Bodies in a system with exobiology you have not finished, worth at least `threshold` for what is
    left (plain prices, no x5). A body the rules cannot price only counts when threshold is 0."""
    got, genera = {}, {}
    for r in db.execute("SELECT body_id, species, genus_name, done_ts FROM own_organic WHERE system=? AND done_ts IS NOT NULL", (id64,)):
        if organic_state(db, r["done_ts"], (id64, r["body_id"], r["species"])) != "lost":
            got.setdefault(r["body_id"], set()).add(r["genus_name"])
    for r in db.execute("SELECT body_id, genus_name FROM own_genera WHERE system=?", (id64,)):
        genera.setdefault(r["body_id"], []).append(r["genus_name"])
    row = db.execute("SELECT star_class FROM star_classes WHERE id64=?", (id64,)).fetchone()
    star = row["star_class"] if row else None
    cnt = db.execute("SELECT body_count FROM own_systems WHERE id64=?", (id64,)).fetchone()
    ctx = bio_context(system, records, x, y, z, star, cnt and cnt[0])
    hits = []
    for r in records:
        bid = r.get("body_id")
        known = genera.get(bid) or r.get("genera") or []
        signals = r.get("bio") or len(known)
        if r.get("type") != "Planet" or not signals:
            continue
        done = got.get(bid, set())
        left_n = signals - len(done)
        if left_n <= 0:
            continue                      # every species here analysed
        rest = bio_left_groups(r, star, known, ctx, done)
        priced = [g for g in rest if g.get("value")]
        left = sum(g["value"] for g in priced) if priced else None
        if (left or 0) < threshold or (left is None and threshold):
            continue
        hits.append((left or 0, {"t": f"{r['name']} · {left_n} of {signals} unscanned"
                                 + (f" · up to {left / 1e6:.1f}M" if left else " · value unknown"), "body": r["name"]}))
    return [h for _, h in sorted(hits, key=lambda t: -t[0])]


def match_system(system, records, crit):
    """Which of the ticked criteria this system satisfies: {section: [descriptions]}."""
    stars = [r for r in records if r["type"] == "Star"]
    out = {}
    if crit["stars"]:
        hits = []
        for r in stars:
            # a lone star is the arrival star, unless the record says otherwise (online search results
            # carry only the bodies that matched, so a lone secondary must not be called the arrival)
            is_main = r.get("main") or (len(stars) == 1 and not r.get("main_known"))
            if r["subtype"] in crit["stars"] and (is_main or not crit["main_only"]):
                label = "arrival star" if r["name"] == system else r["name"]
                hits.append({"t": f"{label} · {r['subtype']}" + (" (arrival)" if is_main and r["name"] != system else ""),
                             "body": r["name"]})
        if hits:
            out["stars"] = hits
    if crit["planets"]:
        hits = [{"t": f"{r['name']} · {r['subtype']}", "body": r["name"]} for r in records
                if r["type"] == "Planet" and r["subtype"] in crit["planets"]]
        if hits:
            out["planets"] = hits
    if crit["rings"]:
        hits = [{"t": f"{r['name']} {x['name']} · {x['type']}", "body": r["name"]} for r in records
                for x in r.get("rings") or [] if x["type"] in crit["rings"]]
        if hits:
            out["rings"] = hits
    if crit["hotspots"]:
        hits = []
        for r in records:
            for x in r.get("rings") or []:
                found = {m: n for m, n in minerals(x.get("hotspots")).items() if m in crit["hotspots"]}
                if found:
                    hits.append({"t": f"{r['name']} {x['name']} ({x['type']}): " +
                                 ", ".join(f"{m} {n}" for m, n in sorted(found.items(), key=lambda kv: -kv[1])),
                                 "body": r["name"]})
        if hits:
            out["hotspots"] = hits
    if crit.get("mining") is not None:
        mineral, hits = crit["mining"]["mineral"], []
        for r in records:
            n = r.get("mining")
            if not n or r.get("type") != "Planet":
                continue
            ground = mining_ground(r.get("subtype"), r.get("volcanism"))
            if not mineral:
                hits.append((n, {"t": f"{r['name']} · {ground or 'ground unknown'}: ⛏ {n}", "body": r["name"], "here": True}))
                continue
            pct = mining_share(ground, mineral)
            if pct is None or pct < MINING_SHARE_MIN:
                continue
            few = (MINING_ODDS.get(ground) or {}).get("surveyed", 0) < MINING_FEW
            # the share is the ground's, the same for every body of it: the count makes the expected number
            hits.append((n * pct / 100, {"t": f"{r['name']} · {ground}: ⛏ {n}, {mineral} {pct:.0f}% of surveyed locations"
                                              f" (~{n * pct / 100:.0f} expected){' · few reports' if few else ''}",
                                         "body": r["name"], "here": True}))
        if hits:
            out["mining"] = [h for _, h in sorted(hits, key=lambda t: -t[0])]
    return out


class Searcher:
    def __init__(self, state):
        self.state, self.db, self.spansh = state, state.db, state.spansh
        self.seq = 0
        self.task = None
        self.found = {}            # id64 -> (name, x, y, z) for bookmarking results
        self.result = {"seq": 0, "running": False, "status": "", "results": [], "params": None}

    def start(self, params):
        if self.task and not self.task.done():
            self.task.cancel()
        self.seq += 1
        self.result = {"seq": self.seq, "running": True, "status": "searching…",
                       "results": [], "params": params}
        self.task = asyncio.create_task(self.run(self.seq, params))

    def update(self, seq, **kw):
        if seq != self.seq:
            return
        if not self.result.get("running") and "running" not in kw:
            return  # a late progress message from a sibling of a failed query
        self.result.update(kw)

    async def run(self, seq, params):
        try:
            await self._run(seq, params)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.update(seq, running=False, status=f"search failed: {e}")

    async def _run(self, seq, params):
        pos = self.state.journals.pos
        if not pos:
            return self.update(seq, running=False, status="no current position yet")
        source = "spansh" if params.get("source") == "spansh" else "local"
        radius = max(1.0, min(float(params.get("radius") or 100), SEARCH_MAX_RADIUS[source]))
        crit = {
            "stars": {st for k in params.get("stars") or [] for st in STAR_GROUPS.get(k, [])},
            "main_only": bool(params.get("main_only", True)),
            "planets": set(params.get("planets") or []) & set(PLANET_TYPES),
            "rings": set(params.get("rings") or []) & set(RING_TYPES),
            "hotspots": set(params.get("hotspots") or []) & set(HOTSPOT_MINERALS),
            # ticked bio thresholds are OR'd like any other section: the lowest one decides
            "bio": min((BIO_SEARCH[k][1] for k in params.get("bio") or [] if k in BIO_SEARCH), default=None),
            # planetary mining locations (S4), with an optional mineral from the survey (an unknown name counts as none)
            "mining": {"mineral": params.get("mining_mineral") if params.get("mining_mineral") in searchable_minerals(self.db) else None}
                      if params.get("mining") is True else None,
        }
        sections = [k for k in ("stars", "planets", "rings", "hotspots", "bio", "mining") if crit[k] is not None and crit[k] != set()]
        if not sections:
            return self.update(seq, running=False, status="tick at least one star, planet, ring, hotspot, exobiology or mining option")
        if source == "spansh" and crit["mining"] is not None:
            # sections are ANDed: dropping this one would list systems without any mining location
            return self.update(seq, running=False, status="Spansh's search can't filter on planetary mining locations:"
                                                          " search your Local database for them")

        systems, coverage, note = (None, radius, None) if source == "local" else await self.online(seq, pos, radius, crit)
        # the matching (and for a local search, reading every cached system in the box) can take seconds
        # over a big radius: a worker thread with its own read-only connection, so tailing, long polls and
        # the auto honk carry on meanwhile
        results, coverage, note, sparse, found = await self.off_loop(
            lambda db: self.match(db, pos, source, radius, crit, sections, systems, coverage, note))
        self.found.update(found)
        results.sort(key=lambda r: r["distance"])
        total = len(results)
        where = "your local database" if source == "local" else "Spansh"
        status = (f"{total} system{'s' if total != 1 else ''} within {coverage:g} ly of {pos['name']}"
                  f" ({where})")
        if total > SEARCH_MAX_RESULTS:
            status += f", showing the nearest {SEARCH_MAX_RESULTS}"
        if note:
            status += " · " + note
        self.update(seq, running=False, status=status, results=results[:SEARCH_MAX_RESULTS],
                    radius=coverage, source=source, origin=pos["name"], sparse=sparse)

    async def off_loop(self, fn):
        """fn(db) on a worker thread with its own read-only connection to the database (a connection is
        never shared between threads). Without a database file (tests) it runs here on the loop's."""
        path = self.state.db_path
        if not path or path == ":memory:":
            return fn(self.db)

        def work():
            db = sqlite3.connect(f"file:{urllib.parse.quote(os.path.abspath(path))}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            try:
                return fn(db)
            finally:
                db.close()
        return await asyncio.get_running_loop().run_in_executor(None, work)

    def match(self, db, pos, source, radius, crit, sections, systems, coverage, note):
        """The systems meeting every ticked section: (results, coverage, note, sparse, found). A local
        search reads its systems from `db` first. Runs on a worker thread: only `db`, no shared state."""
        sparse = False
        if source == "local":
            systems = self.local(pos, radius, db)
            n = sum(1 for *_, recs in systems.values() if recs)
            n_rings = sum(1 for *_, recs in systems.values() if any(r.get("rings") for r in recs))
            n_hot = sum(1 for *_, recs in systems.values()
                        if any(minerals(x.get("hotspots")) for r in recs for x in r.get("rings") or []))
            note = (f"searched {n} system{'s' if n != 1 else ''} with body data ({n_rings} with ring data, "
                    f"{n_hot} with mapped hotspots); the local database only holds systems you've visited or "
                    f"passed within {self.state.radius:g} ly of — Spansh (online) covers everything reported")
            sparse = bool(sections) and (("hotspots" in sections and n_hot < 5) or ("rings" in sections and n_rings < 10) or n < 20)
        visited = {r[0] for r in db.execute("SELECT id64 FROM visits")}
        # a mineral you have refined somewhere: those bodies first ("Gold 22 t mined here before"), surveyed for it or
        # not, whatever its share of the ground's locations (review S38)
        mineral, mined = (crit.get("mining") or {}).get("mineral"), {}
        if source == "local" and mineral:
            for r in db.execute("SELECT system, body_id, tons FROM own_mined WHERE lower(name) = lower(?) AND tons > 0",
                                (mineral,)):
                mined.setdefault(r[0], []).append((r[1], r[2]))
        results, found = [], {}
        for id64, (name, x, y, z, records) in systems.items():
            d = dist(pos, {"x": x, "y": y, "z": z})
            if d > coverage:
                continue
            m = match_system(name, records, crit)
            if id64 in mined:
                by_id = {r.get("body_id"): r["name"] for r in records if r.get("body_id") is not None}
                mine = []
                for bid, tons in sorted(mined[id64], key=lambda t: -t[1]):
                    bname = by_id.get(bid) or (db.execute("SELECT name FROM own_bodies WHERE system=? AND body_id=?",
                                                          (id64, bid)).fetchone() or [f"body {bid}"])[0]
                    mine.append({"t": f"{bname} · {mineral} {tons} t mined here before", "body": bname, "here": True})
                ours = {h["body"] for h in mine}
                m["mining"] = mine + [h for h in m.get("mining", []) if h["body"] not in ours]
            if crit["bio"] is not None and all(k in m for k in sections if k != "bio"):
                # price from the fullest record we have: a cached Spansh dump plus your scans beats the
                # search result (which lacks volcanism and the system's stars)
                bio_recs = records if source == "local" else (self.local_records(id64, name, db) or records)
                hits = bio_hits(db, id64, name, x, y, z, bio_recs, crit["bio"])
                if hits:
                    m["bio"] = hits
            if all(k in m for k in sections):
                results.append({"id": str(id64), "name": name, "distance": round(d, 2),
                                "visited": id64 in visited, "matches": m,
                                "firsts": own_firsts(db, id64, name) if id64 in visited else None})
                found[id64] = (name, x, y, z)
        return results, coverage, note, sparse, found

    def local(self, pos, r, db):
        """Every system in the database within r: cached Spansh data merged with your own scans."""
        box = (pos["x"] - r, pos["x"] + r, pos["y"] - r, pos["y"] + r, pos["z"] - r, pos["z"] + r)
        found = {}
        # fetched in one go: a read held open while decoding would keep the tailer's commit waiting
        for row in db.execute(
                "SELECT id64, summary FROM spansh_systems WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? "
                "AND z BETWEEN ? AND ?", box).fetchall():
            b = json.loads(row["summary"])
            if b.get("records") is not None:  # any cache layout that carries body records is searchable
                found[row["id64"]] = (b["name"], b["x"], b["y"], b["z"], b.get("records") or [])
        for v in db.execute(
                "SELECT id64, name, x, y, z FROM visits WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? "
                "AND z BETWEEN ? AND ?", box).fetchall():
            if v["id64"] not in found:
                found[v["id64"]] = (v["name"], v["x"], v["y"], v["z"], [])
        out = {}
        for id64, (name, x, y, z, records) in found.items():
            if dist(pos, {"x": x, "y": y, "z": z}) > r:
                continue
            own, hotspots, _ = own_data(db, id64, name)
            out[id64] = (name, x, y, z, merge_records(records, own, hotspots))
        return out

    def local_records(self, id64, name, db):
        """A system's cached Spansh dump merged with your scans, or None if nothing full is cached."""
        _, base = cached_base(db, id64)
        own, hotspots, _ = own_data(db, id64, name)
        recs = (base or {}).get("records") or []
        if not (any(r.get("full") for r in recs) or own):
            return None
        return merge_records(recs, own, hotspots)

    async def online(self, seq, pos, radius, crit):
        """One Spansh body search per OR'd value (its lists are AND'd), merged per system."""
        queries = []
        if crit["stars"]:
            f = {"subtype": {"value": sorted(crit["stars"])}}
            if crit["main_only"]:
                f["is_main_star"] = {"value": True}
            queries.append(("stars", f))
        if crit["planets"]:
            queries.append(("planets", {"subtype": {"value": sorted(crit["planets"])}}))
        for t in sorted(crit["rings"]):
            queries.append(("rings", {"rings": [{"type": t}]}))
        for m in sorted(crit["hotspots"]):
            queries.append(("hotspots", {"ring_signals": [{"name": m, "value": [1, 9999], "comparison": "<=>"}]}))
        if crit["bio"] is not None:
            queries.append(("bio", {"signals": [{"name": "Biological", "value": [1, 999], "comparison": "<=>"}]}))

        done = 0
        truncated_at = []

        async def one(filters):
            nonlocal done
            bodies, cut = await self.spansh.body_search(filters, pos, radius, SEARCH_PAGES_PER_QUERY)
            done += 1
            self.update(seq, status=f"asking Spansh… {done} of {len(queries)} queries done")
            if cut is not None:
                truncated_at.append(cut)
            return bodies

        self.update(seq, status=f"asking Spansh… 0 of {len(queries)} queries done")
        tasks = [asyncio.create_task(one(f)) for _, f in queries]
        try:
            batches = await asyncio.gather(*tasks)
        except BaseException:
            for t in tasks:
                t.cancel()
            raise
        systems = {}
        for bodies in batches:
            for b in bodies:
                id64 = b["system_id64"]
                entry = systems.setdefault(id64, (b["system_name"], b["system_x"], b["system_y"],
                                                  b["system_z"], {}))
                entry[4][b["name"]] = record_from_body_search(b)
        systems = {k: (n, x, y, z, list(recs.values())) for k, (n, x, y, z, recs) in systems.items()}
        coverage, note = radius, None
        if truncated_at:
            coverage = round(min(truncated_at), 1)
            note = (f"Spansh had too many matches to fetch them all, so results are only complete out to "
                    f"{coverage:g} ly. Tick fewer items or shrink the radius to see further.")
        return systems, coverage, note


# --------------------------------------------------------------------------
# Web
# --------------------------------------------------------------------------

# The page lives in static/ next to this script (page.html, page.css, page.js). page.html is read
# on every request so edits show up on reload; __SEARCH_OPTIONS__ is filled in when it is served.
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def sounds_json():
    """static/sounds.json for inlining into the page (the alert sounds, which the server can also play), or
    "null" when it cannot be read: the page then plays no sounds."""
    try:
        return json.dumps(outrider.tts.load_sounds()).replace("<", "\\u003c")
    except (OSError, ValueError) as e:
        print(f"sounds: {e}", file=sys.stderr)
        return "null"


# The tablet layout (GET /tablet): the same page in a tablet mode (body.tablet: page.js draws its shell), with the
# shell's stylesheet and every theme's (each scoped to its data-theme, so the per-device picker switches without a
# reload). Fonts a theme lists first may come from data/fonts/ (fan fonts never committed: FONT_DIR, /userfonts/).
# File types the static files need that an older Python's mimetypes lacks (3.12, the Docker image's, has no .webp:
# the themes' emblems were served as application/octet-stream). aiohttp keeps a table of its own for static files.
STATIC_TYPES = {".webp": "image/webp", ".woff2": "font/woff2"}


def register_static_types():
    import aiohttp.web_fileresponse
    tables = [mimetypes, getattr(aiohttp.web_fileresponse, "CONTENT_TYPES", None)]
    for ext, typ in STATIC_TYPES.items():
        for table in tables:
            if table is not None:
                table.add_type(typ, ext)


register_static_types()
TABLET_STYLES = ("tablet.css", "themes/lcars.css", "themes/elite.css", "themes/babylon5.css", "themes/narn.css",
                 "themes/minbari.css", "themes/centauri.css", "themes/sith.css", "themes/alliance.css", "themes/dark.css")
DESKTOP_STYLES = tuple(n for n in TABLET_STYLES if n.startswith("themes/"))   # the themes, without the tablet's shell
TABLET_THEMES = ("lcars", "elite", "babylon5", "narn", "minbari", "centauri", "sith", "alliance", "dark")
FONT_DIR = os.path.join(outrider.DATA_DIR, "fonts")
USER_FONT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,80}\.(ttf|otf|woff2?)")


# The page's files: an open page compares their stamp (in every payload) with the one it was served with, and reloads
# itself when Outrider has newer ones (a tablet runs for hours; a restart after an update must reach it). Statted at
# most every PAGE_STAMP_S seconds (the payload is built often), together with the server's code (restart_needed below):
# one refresh for both, so a payload never pairs new page files with a stale "no restart needed" (review R3).
PAGE_FILES = ("page.html", "page.js", "page.css", "sounds.json") + TABLET_STYLES
PAGE_STAMP_S = 5.0
_stamps = {"at": None, "page": None, "code": None}


def page_stamp(static_dir=None, now=None):
    """A short stamp of the page's files (their sizes and modification times): changes when any of them does."""
    if static_dir is None:
        return stamps(now)["page"]
    parts = []
    for name in PAGE_FILES:
        try:
            st = os.stat(os.path.join(static_dir, name))
            parts.append(f"{name}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{name}:-")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


# The server's own code (this file and outrider/*.py) as it was when it started: when the files on disk differ, Outrider
# was updated but not restarted, and an open page must not reload onto new page files that need the new server (the
# tablet once showed Ask against a server without /api/ask): the payload says restart_needed instead.
def code_stamp(root=None):
    root = root or SCRIPT_DIR
    files = [os.path.join(root, "ed_outrider.py")] + sorted(glob(os.path.join(glob_escape(os.path.join(root, "outrider")), "*.py")))
    parts = []
    for p in files:
        try:
            st = os.stat(p)
            parts.append(f"{os.path.basename(p)}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{os.path.basename(p)}:-")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


CODE_STAMP_START = code_stamp()


def stamps(now=None, fresh=False):
    """{"page": the page files' stamp, "restart_needed": the code on disk differs from the code running}, both from
    one refresh made at most every PAGE_STAMP_S (fresh: now; a page being served carries its files' own stamp)."""
    now = time.monotonic() if now is None else now
    if fresh or _stamps["at"] is None or not 0 <= now - _stamps["at"] < PAGE_STAMP_S:
        _stamps.update(at=now, page=page_stamp(STATIC_DIR), code=code_stamp())
    return {"page": _stamps["page"], "restart_needed": _stamps["code"] != CODE_STAMP_START}


def restart_needed(now=None):
    """Whether the server's code on disk differs from the code running (checked at most every PAGE_STAMP_S)."""
    return stamps(now)["restart_needed"]


def load_page(tablet=False):
    """page.html with its script and stylesheet links stamped by modification time, so a browser fetches
    the new copy as soon as either file changes instead of running a cached one. tablet: the /tablet layout. The
    desktop page links the themes too (not the tablet's shell): a browser may choose one (Settings > Display)."""
    with open(os.path.join(STATIC_DIR, "page.html"), encoding="utf-8") as f:
        html = f.read()
    styles = TABLET_STYLES if tablet else DESKTOP_STYLES
    links = "".join(f'<link rel="stylesheet" href="static/{n}">' for n in styles)
    html = html.replace("</head>", links + "</head>", 1)
    if tablet:
        html = html.replace("<body>", '<body class="tablet">', 1)
        html = html.replace('<html lang="en">', f'<html lang="en" data-theme="{TABLET_THEMES[0]}">', 1)
    for name in ("page.js", "page.css") + styles:
        try:
            stamp = int(os.path.getmtime(os.path.join(STATIC_DIR, name)))
        except OSError:
            continue
        html = html.replace(f'"static/{name}"', f'"static/{name}?v={stamp}"')
    return html


# The Android app's contract (project notes: PLAN-tablet): API_VERSION goes up only on a breaking change to the
# native-facing endpoints (/api/version, /api/auth/*) or the page <-> app bridge; MIN_APP_VERSION is the oldest app
# this Outrider still serves (an older one gets 426 app_too_old and says "update the app").
API_VERSION = 1
MIN_APP_VERSION = "1.0.0"
# open from the network without a session: what the app needs before signing in, the sign-in itself, the tab icon
AUTH_OPEN = ("/api/version", "/api/auth/signin", "/api/auth/signout", "/signin", "/static/favicon.svg")
SESSION_COOKIE_AGE = 10 * 365 * 86400   # s: a session lasts until the password changes or you sign out
REVOKED_KEEP = 500   # signed-out session ids remembered (the oldest forgotten first)

# The sign-in page a browser on the network is sent to without a session: self-contained (no script or style from
# /static/, which needs the session), the page's dark colours, back to where it was going once signed in.
SIGNIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ED Outrider · sign in</title>
<link rel="icon" type="image/svg+xml" href="static/favicon.svg">
<style>
body { background: #0b0d12; color: #d8dbe2; font: 15px system-ui, sans-serif; display: grid; place-items: center; min-height: 90vh; margin: 0; }
form { background: #151922; border: 1px solid #2a3040; border-radius: 10px; padding: 24px 28px; width: min(340px, 86vw); }
h1 { color: #ff7100; font-size: 20px; margin: 0 0 6px; } p { color: #8a93a6; font-size: 13px; margin: 0 0 16px; }
input { width: 100%; box-sizing: border-box; padding: 9px 10px; font: inherit; color: inherit; background: #0b0d12;
  border: 1px solid #2a3040; border-radius: 6px; } input:focus { outline: 1px solid #ff7100; }
button { margin-top: 14px; width: 100%; padding: 9px; font: inherit; font-weight: 600; color: #0b0d12; background: #ff7100;
  border: 0; border-radius: 6px; cursor: pointer; } #msg { color: #e05555; font-size: 13px; min-height: 1.2em; margin-top: 10px; }
</style></head><body>
<form id="f"><h1>ED Outrider</h1><p>This Outrider asks devices on the network for its password ([server] password in
ed_outrider.toml).</p><input type="password" id="pw" autocomplete="current-password" placeholder="password" autofocus>
<button type="submit">Sign in</button><div id="msg" role="status"></div></form>
<script>
// where to go once signed in: only a page of this Outrider ("/\\evil.com" is "//evil.com" to a browser)
function safeNext(nxt, origin) {
  try {
    const u = new URL(nxt, origin);
    return u.origin === origin && nxt.startsWith("/") && !/[\\\\\\s]/.test(nxt) ? u.pathname + u.search + u.hash : "/";
  } catch { return "/"; }
}
const safe = safeNext(new URLSearchParams(location.search).get("next") || "/", location.origin);
document.getElementById("f").onsubmit = async e => {
  e.preventDefault();
  const msg = document.getElementById("msg"); msg.textContent = "";
  try {
    const r = await fetch("api/auth/signin", {method: "POST", headers: {"Content-Type": "application/json"},
                                               body: JSON.stringify({password: document.getElementById("pw").value})});
    const j = await r.json();
    if (r.ok) location.href = safe; else msg.textContent = j.error || "could not sign in";
  } catch { msg.textContent = "could not reach Outrider"; }
};
</script></body></html>"""

WILDCARD_HOSTS = ("0.0.0.0", "::", "")


def safe_next(nxt):
    """Is `nxt` a path on this site to go to after signing in? Not "//evil.com", nor "/\\evil.com" (a browser reads
    a backslash as a slash), nor a whitespace trick (review R6)."""
    return isinstance(nxt, str) and nxt.startswith("/") and not nxt.startswith("//") \
        and not any(c == "\\" or c.isspace() or ord(c) < 32 for c in nxt)


LAN_SUFFIXES = (".lan", ".local", ".home", ".internal", ".home.arpa", ".localdomain")


def public_name(name):
    """Does a host name (maybe with a port) look like an internet one rather than a LAN one? LAN: no dot, a LAN
    suffix (.lan, .local, .home, .internal, .home.arpa), or a private, loopback or link-local address."""
    import ipaddress
    n = str(name).strip().lower()
    n = n[1:n.index("]")] if n.startswith("[") and "]" in n else n.rsplit(":", 1)[0] if n.count(":") == 1 else n
    try:
        ip = ipaddress.ip_address(n)
    except ValueError:
        return "." in n.rstrip(".") and not n.rstrip(".").endswith(LAN_SUFFIXES)
    return not (ip.is_private or ip.is_loopback or ip.is_link_local)


NFS_CACHE_OK = 2   # s: the longest attribute caching (acregmax) that keeps alerts on time over NFS


def _read_mounts():
    with open("/proc/self/mounts", encoding="utf-8", errors="replace") as f:
        return f.read()


def nfs_cache_warnings(dirs, mounts=None, realpath=os.path.realpath, read=_read_mounts):
    """Warnings for journal folders on NFS that cache a file's attributes for longer than NFS_CACHE_OK. Outrider
    sees a journal grow by its size; NFS keeps the size it knows for up to acregmax (60 s by default), and a
    minute of alerts then comes at once (found on the author's Docker server). actimeo=1 or noac fixes it. CIFS
    caches for 1 s by default and is left alone. mounts: /proc/self/mounts' text (read() when None; Linux only)."""
    if mounts is None:
        try:
            mounts = read()
        except OSError:
            return []
    table = []
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), parts[1])   # "\040" is a space
            table.append((point, parts[2], parts[3].split(",")))
    out = []
    for d in dirs:
        path = realpath(d)
        inside = [m for m in table if path == m[0] or path.startswith(m[0].rstrip("/") + "/")]
        if not inside:
            continue
        point, fstype, opts = max(inside, key=lambda m: len(m[0]))   # the mount the folder is actually on
        if not fstype.startswith("nfs") or "noac" in opts:
            continue
        acregmax = next((int(o.split("=", 1)[1]) for o in opts if o.startswith("acregmax=") and o.split("=", 1)[1].isdigit()), 60)
        if acregmax > NFS_CACHE_OK:
            out.append(f"warning: the journal folder {d} is on NFS ({point}), which may show a journal's growth up to "
                       f"{acregmax} s late: alerts then come late and all at once. Mount it with actimeo=1 (see "
                       "docs/guide/install.md, \"Running as a server\"), then restart Outrider.")
    return out


def exposure_warnings(host, password, extra):
    """Start-up warnings when the config looks like Outrider is reachable from the internet (the author: do not):
    an allowed_hosts name that is not a LAN one, or listening on the network with no password."""
    out = []
    public = [x for x in extra if public_name(x)]
    if public:
        out.append(f"warning: [server] allowed_hosts has {', '.join(public)}, which looks like an internet name. Do not "
                   "expose Outrider to the internet: it serves your journals, its password only stops accidents on your "
                   "own network, and it gets no security updates (see docs/guide/install.md).")
    if host not in ("127.0.0.1", "localhost", "::1") and not password:
        out.append("warning: listening on your network with no [server] password: anyone who can reach this computer can "
                   "read your journals' contents and edit bookmarks. Set one, and never forward this port to the internet.")
    return out
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
# The only reads under /api/ another site may make (request_guard): the small read-only status an OBS browser
# source or a stream overlay page (another origin, or a file://) polls. Cheap, and they change nothing.
OPEN_GETS = ("/api/status", "/api/status.txt")


def _host_name(name):
    """A host as it appears in a Host header: lower case, IPv6 addresses in brackets."""
    name = str(name).strip().lower()
    return f"[{name}]" if ":" in name and not name.startswith("[") else name


def ip_literal_host(host):
    """Is the name part of a Host header an IP address ("192.168.1.20:8025", "[fe80::1]:8025")? DNS rebinding
    always needs a host name, so an address is safe to answer whatever it is: own_addresses() misses some (a
    VPN holding the default route hides the LAN address)."""
    import ipaddress
    host = str(host).strip()
    if host.startswith("["):
        name = host[1:host.find("]")] if "]" in host else ""
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def own_addresses():
    """This machine's names and addresses, for a server listening on every interface (host = "0.0.0.0").
    Best effort: a name missing here goes into [server] allowed_hosts."""
    import socket
    names = set()
    try:
        hn = socket.gethostname()
        names |= {hn, hn + ".local", socket.getfqdn()}
        names |= {ai[4][0] for ai in socket.getaddrinfo(hn, None)}
    except OSError:
        pass
    try:   # the address other machines reach us on; a UDP connect sends nothing
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            names.add(s.getsockname()[0])
    except OSError:
        pass
    return {n for n in names if n and "%" not in n}   # a link-local address with a scope never appears in Host


def allowed_hosts(host, port, extra=(), own=own_addresses):
    """The Host header values the server answers (DNS rebinding: a page on attacker.example that re-resolves
    to 127.0.0.1 would otherwise read everything): loopback names and the configured host, each with the
    port; with host = "0.0.0.0" also this machine's own names; plus [server] allowed_hosts (a bare name
    gets the port added; on port 80 also without it). request_guard answers any IP address as well."""
    names = {"127.0.0.1", "localhost", "[::1]"}
    names |= set(own()) if host in WILDCARD_HOSTS else {host}
    out = set()
    for n in names:
        n = _host_name(n)
        out.add(f"{n}:{port}")
        if port == 80:   # browsers leave the default port out of Host
            out.add(n)
    for x in extra:
        x = str(x).strip().lower()
        has_port = "]:" in x if x.startswith("[") else x.count(":") == 1   # "name:8025"; a bare IPv6 has several
        x = x if has_port else _host_name(x)
        out.add(x if has_port else f"{x}:{port}")
        # browsers leave the default port out of Host, and an HTTPS reverse proxy on the LAN forwards it so: a name
        # you configured is answered bare too (and "name:80" / "name:443" mean the bare name)
        bare = x.rsplit(":", 1)[0] if has_port and x.endswith((":80", ":443")) else None if has_port else x
        if bare:
            out.add(bare)
    return out


def request_guard(allowed):
    """Middleware: answer only the expected Host names (`allowed`; None skips that check), and refuse a
    state-changing request sent by another site. A plain cross-origin form POST or sendBeacon needs no
    CORS preflight, so without this any web page could press auto honk's key or start backups. Browsers
    always send Origin on a POST; curl sends none and passes."""
    @web.middleware
    async def guard(request, handler):
        host = (request.headers.get("Host") or "").strip().lower()
        if allowed is not None and host not in allowed and not ip_literal_host(host):
            return web.Response(status=403, text=f"ED Outrider does not answer to the host name {host!r}. To reach it by "
                                "that name, add it to [server] allowed_hosts in ed_outrider.toml.\n")
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("Origin")
            site = request.headers.get("Sec-Fetch-Site")
            # http, or https through a reverse proxy on the LAN (review R7): the same host either way
            if (origin is not None and origin.strip().lower() not in (f"http://{host}", f"https://{host}")) or \
                    (site and site not in ("same-origin", "none")):
                return web.json_response({"error": "refused: the request came from another web site"}, status=403)
        elif request.path.startswith("/api/") and request.path not in OPEN_GETS:
            # a GET, but many are real work: Piper synthesis on the shared executor (/api/say), an EDSM call and a
            # cache write (/api/find), every journal read again (/api/log), the History sums on the event loop
            # (/api/history), a Spansh sphere fetch per new radius (/api/map). Another site's <img>, <audio> or
            # no-cors fetch could keep them busy and stall the voice and the journal tailing, and nothing else
            # under /api/ is meant for other sites either. Browsers label those cross-site; the page's own fetch
            # is same-origin, and curl sends no Sec-Fetch-Site. OPEN_GETS stay open to overlays.
            site = request.headers.get("Sec-Fetch-Site")
            if site and site not in ("same-origin", "none"):
                return web.json_response({"error": "refused: the request came from another web site"}, status=403)
        return await handler(request)
    return guard


def make_app(state, hosts=None):
    """The web app. `hosts`: the Host header values to answer (see allowed_hosts); None answers any."""
    @web.middleware
    async def json_errors(request, handler):
        """Any unhandled exception in an API handler comes back as JSON, not an HTML traceback."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except (Exception, SystemExit) as e:
            import traceback
            traceback.print_exc()
            if request.path.startswith("/api/"):
                return web.json_response({"error": f"{type(e).__name__}: {e}", "code": "server_error"}, status=500)
            raise

    def signin_needed(request):
        """No session: the app (its User-Agent says OutriderApp/) and every /api/ or /static/ call get 401
        signin_required, so the app shows its own sign-in; a browser is sent to the sign-in page (never a resource:
        /userfonts/ is one too)."""
        if request.path.startswith(("/api/", "/static/", "/userfonts/")) or "OutriderApp/" in (request.headers.get("User-Agent") or ""):
            return web.json_response({"error": "sign in first: this Outrider asks devices on the network for its password",
                                      "code": "signin_required"}, status=401)
        nxt = request.path_qs if safe_next(request.path_qs) else "/"
        raise web.HTTPFound("/signin?next=" + urllib.parse.quote(nxt, safe=""))

    @web.middleware
    async def session_guard(request, handler):
        """[server] password: a request from another device needs a session (a cookie, or the app's Bearer token)
        except AUTH_OPEN and the overlays' OPEN_GETS. This PC itself (loopback) never needs one: the desktop page,
        curl, OBS and the MCP bridge work as before; a request a reverse proxy on this PC forwarded is another device's
        (outrider.auth.from_this_pc). request_guard's checks run first, whatever the session."""
        if not state.password or outrider.auth.from_this_pc(request.remote, request.headers) or request.path in AUTH_OPEN \
                or request.path in OPEN_GETS:
            return await handler(request)
        if state.session_ok(outrider.auth.request_token(request.headers, request.cookies)):
            return await handler(request)
        return signin_needed(request)

    app = web.Application(middlewares=[request_guard(hosts), session_guard, json_errors])

    def app_too_old(request):
        """A 426 for an app older than MIN_APP_VERSION (its X-Outrider-App header), else None."""
        v = request.headers.get("X-Outrider-App")
        if v is not None and outrider.auth.version_tuple(v) < outrider.auth.version_tuple(MIN_APP_VERSION):
            return web.json_response({"error": f"this app ({v}) is too old for this Outrider: update the app "
                                               f"(at least {MIN_APP_VERSION})", "code": "app_too_old"}, status=426)
        return None

    def signed_in(request):
        """What /api/version reports: whether this request may use Outrider now (no password asked of it, or a
        live session)."""
        return not state.password or outrider.auth.from_this_pc(request.remote, request.headers) or \
            state.session_ok(outrider.auth.request_token(request.headers, request.cookies))

    async def version_view(request):
        """GET /api/version, open: what the app needs before signing in ("update the app", "update Outrider", "sign
        in"), and nothing else."""
        return web.json_response({"outrider": outrider.__version__, "api": API_VERSION, "min_app": MIN_APP_VERSION,
                                  "password": bool(state.password), "signed_in": bool(signed_in(request)),
                                  "game_pc": bool(state.game_pc)})

    async def signin_view(request):
        """POST /api/auth/signin {password} -> {ok, token} and the same token as an HttpOnly cookie. 401 bad_password,
        429 rate_limited (Retry-After), 400 bad_request, 426 app_too_old."""
        old = app_too_old(request)
        if old:
            return old
        body = await json_object(request)
        if body is None or not isinstance(body.get("password"), str):
            return web.json_response({"error": "expected {\"password\": \"...\"}", "code": "bad_request"}, status=400)
        if not state.password:   # nothing to sign in to: every device may use it
            return web.json_response({"ok": True, "token": ""})
        who = outrider.auth.client_key(request.remote, request.headers)
        wait = state.signin_limit.wait(who)
        if wait:
            return web.json_response({"error": f"too many wrong passwords: try again in {wait} s", "code": "rate_limited"},
                                     status=429, headers={"Retry-After": str(wait)})
        if not outrider.auth.password_ok(body["password"], state.password):
            state.signin_limit.failed(who)
            return web.json_response({"error": "wrong password", "code": "bad_password"}, status=401)
        state.signin_limit.clear(who)
        token = state.new_session()
        resp = web.json_response({"ok": True, "token": token})
        resp.set_cookie(outrider.auth.COOKIE, token, max_age=SESSION_COOKIE_AGE, path="/", httponly=True, samesite="Strict")
        return resp

    async def signout_view(request):
        """POST /api/auth/signout: that session stops working (others stay signed in); the cookie is cleared."""
        old = app_too_old(request)
        if old:
            return old
        state.end_session(outrider.auth.request_token(request.headers, request.cookies))
        resp = web.json_response({"ok": True})
        resp.del_cookie(outrider.auth.COOKIE, path="/")
        return resp

    async def signin_page(request):
        """GET /signin: the password form a browser on the network is sent to (the app has its own). A `next` that
        leaves this site is dropped (the page checks it too)."""
        if "next" in request.query and not safe_next(request.query["next"]):
            raise web.HTTPFound("/signin")
        return web.Response(text=SIGNIN_PAGE, content_type="text/html")

    def parse_id64(raw):
        if isinstance(raw, bool) or isinstance(raw, float) and not raw.is_integer():
            # JSON's 1e999 is float inf: int() would raise OverflowError, which no caller expects (review #12)
            raise ValueError("id64 must be a whole number")
        v = int(raw)
        if not 0 <= v < 2 ** 63:
            raise ValueError("id64 out of range")
        return v

    async def index(request):
        # the mineral list is the survey's plus what you have refined (S38): read for each page load
        options = json.dumps(dict(SEARCH_OPTIONS, mining=searchable_minerals(state.db)))
        # the browser defaults go into the page itself, so they are there before page.js reads its settings
        # ("<" escaped: a value holding "</script>" cannot end the script element)
        saved = read_browser_defaults(browser_defaults_path(state.db_path)) if state.db_path else None
        return web.Response(text=load_page(tablet=request.path == "/tablet").replace("/*SEARCH_OPTIONS*/null", options)
                            .replace("/*SERVER_DEFAULTS*/null", json.dumps(saved).replace("<", "\\u003c"))
                            .replace("/*SOUNDS*/null", sounds_json())
                            .replace("/*PAGE_STAMP*/null", json.dumps(stamps(fresh=True)["page"])),
                            content_type="text/html")

    async def defaults_get(_):
        return web.json_response(read_browser_defaults(browser_defaults_path(state.db_path)) if state.db_path else None)

    async def defaults_post(request):
        """'Use these for new browsers': the page's shared settings saved next to the database (or {clear: true}
        to stop). Behind request_guard like every POST: another web site cannot write it."""
        if not state.db_path:
            return web.json_response({"error": "no database path"}, status=500)
        raw = b""   # read no further than the cap (a read returns what has arrived, so loop)
        while len(raw) <= BROWSER_DEFAULTS_MAX:
            chunk = await request.content.read(BROWSER_DEFAULTS_MAX + 1 - len(raw))
            if not chunk:
                break
            raw += chunk
        if len(raw) > BROWSER_DEFAULTS_MAX:
            return web.json_response({"error": f"over {BROWSER_DEFAULTS_MAX // 1024} KB"}, status=413)
        try:
            doc = json.loads(raw)
        except ValueError:
            return web.json_response({"error": "not JSON"}, status=400)
        path = browser_defaults_path(state.db_path)
        if isinstance(doc, dict) and doc.get("clear") is True:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            return web.json_response({"ok": True, "saved": None})
        ok, why = check_browser_defaults(doc)
        if not ok:
            return web.json_response({"error": why}, status=400)
        await asyncio.get_running_loop().run_in_executor(None, write_browser_defaults, path, ok)
        return web.json_response({"ok": True, "saved": ok["saved"]})

    async def nearby(request):
        # Long poll: a page that already has the current version waits here until something changes
        # (or 25 s pass: 204, and it asks again), so a target verdict reaches it in well under a second.
        if request.query.get("speaker") == "1":   # a window with speech on that speaks: answers will be said (S24)
            state.speaker_seen = time.monotonic()
        if request.query.get("since") == f"{RUN_ID}:{state.version}":
            changed = state.changed
            try:
                await asyncio.wait_for(changed.wait(), LONG_POLL_SECONDS)
            except asyncio.TimeoutError:
                return web.Response(status=204)
            await asyncio.sleep(0.15)   # let a burst of changes (a refresh landing dumps) settle into one payload
        resp = web.json_response(state.payload())
        # gzip when the browser takes it (every one does): the payload shrinks about 4x, which a tablet on WiFi
        # notices with a big Nearby radius (review S20). gzip only, never deflate (browsers disagree on what it means)
        if "gzip" in request.headers.get("Accept-Encoding", "").lower():
            resp.enable_compression(web.ContentCoding.gzip)
        return resp

    async def left_view(request):
        try:
            radius = max(10.0, min(float(request.query.get("radius", 100)), 500.0))
        except ValueError:
            radius = 100.0
        return web.json_response(state.left_behind(radius))   # the database connection belongs to this thread

    async def firsts_view(_):
        return web.json_response({"firsts": state.firsts_list(), "computed": (state.unsold or {}).get("computed")})

    async def user_font(request):
        """GET /userfonts/{name}: a font file you dropped into data/fonts/ (a theme lists it before its own OFL font;
        a missing one is a 404 and the browser falls back)."""
        name = request.match_info["name"]
        path = os.path.join(FONT_DIR, name)
        if not USER_FONT_RE.fullmatch(name) or not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "max-age=86400"})

    app.router.add_get("/", index)
    app.router.add_get("/tablet", index)
    app.router.add_get("/userfonts/{name}", user_font)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    async def bookmark(request):
        try:
            body = await request.json()
            id64 = parse_id64(body["id"])
        except (ValueError, KeyError, TypeError):
            return web.json_response({"error": "bad request"}, status=400)
        if body.get("remove"):
            state.remove_bookmark(id64)
        elif not state.set_bookmark(id64, str(body.get("note") or "")[:2000]):
            return web.json_response({"error": "unknown system"}, status=404)
        return web.json_response({"ok": True})

    async def rigs_remove_view(request):
        """{id}: a mining rig still out picked up (its number free, its tons a saved site); a saved rig site forgotten."""
        body = await json_object(request)
        rid = body.get("id") if body else None
        if not json_row_id(rid):
            return web.json_response({"error": "expected {id: a rig's id}"}, status=400)
        if not state.remove_rig(rid):
            return web.json_response({"error": "no such rig"}, status=404)
        return web.json_response({"ok": True})

    async def sites_forget_view(request):
        """{system, body}: forget a body's saved mining sites and location markers (rigs still out stay)."""
        body = await json_object(request)
        try:
            system, body_id = parse_id64((body or {})["system"]), body["body"]
        except (ValueError, KeyError, TypeError, OverflowError):   # OverflowError: int(1e400)
            system = body_id = None
        if system is None or not json_row_id(body_id):
            return web.json_response({"error": "expected {system: id64, body: body id}"}, status=400)
        return web.json_response({"ok": True, "forgot": state.forget_sites(system, body_id)})

    async def search_start(request):
        try:
            params = await request.json()
        except ValueError:
            return web.json_response({"error": "bad request"}, status=400)
        state.searcher.start(params)
        return web.json_response({"seq": state.searcher.seq})

    async def search_get(_):
        return web.json_response(state.searcher.result)

    async def map_view(request):
        try:
            radius = max(5.0, min(float(request.query.get("radius", 50)), MAP_MAX_RADIUS))
            path_len = max(0, min(int(request.query.get("path", 100)), 5000))
        except ValueError:
            radius, path_len = 50.0, 100
        boost = request.query.get("boost") in ("1", "true")
        return web.json_response(await state.map_payload(radius, path_len, boost))

    async def system_view(request):
        try:
            id64 = parse_id64(request.match_info["id64"])
        except ValueError:
            return web.json_response({"error": "bad id"}, status=400)
        await state.ensure_records(id64)
        d = state.system_detail(id64)
        if not d:
            return web.json_response({"error": "unknown system"}, status=404)
        return web.json_response(d)

    async def find_view(request):
        """GET /api/find?name=: one system by name (see State.find_system); the page then opens it by id."""
        name = " ".join((request.query.get("name") or "").split())
        if not name or len(name) > FIND_NAME_MAX:
            return web.json_response({"error": f"give a system name of up to {FIND_NAME_MAX} characters"}, status=400)
        status, d = await state.find_system(name)
        return web.json_response(d, status=status)

    async def body_view(request):
        try:
            id64 = parse_id64(request.query["system"])
            name = request.query["name"][:200]
        except (KeyError, ValueError):
            return web.json_response({"error": "bad request"}, status=400)
        d = await state.body_detail(id64, name)
        if not d:
            return web.json_response({"error": "unknown system"}, status=404)
        return web.json_response(d)

    async def history_view(request):
        try:
            days = max(1, min(int(request.query.get("days", 30)), 3650))
        except ValueError:
            days = 30
        return web.json_response(state.history(days))

    async def checklist_view(request):
        kind = request.query.get("kind", "bio")
        if "species" in request.query:
            out, status = (state.checklist_geo if kind == "geo" else state.checklist_species)(request.query["species"])
            return web.json_response(out, status=status)
        out, status = state.checklist(request.query.get("region", "here"), kind)
        return web.json_response(out, status=status)

    async def organics_view(request):
        try:
            days = max(1, min(int(request.query.get("days", 30)), 3650))
        except ValueError:
            days = 30
        return web.json_response(state.organics(days))

    def status_small():
        """A compact status for overlays and other tools (the page itself uses /api/nearby)."""
        p = state.payload()
        pos, f, t, u, c = p["position"], p["fuel"] or {}, p["target"], p["unsold"] or {}, p["carrier"]
        ob, sm = p["on_body"], p["sampling"]
        return {"system": pos and pos["name"], "id64": pos and str(pos["id64"]),
                "coords": pos and [pos["x"], pos["y"], pos["z"]], "region": (p["region"] or {}).get("name"),
                "fuel_pct": f.get("pct"), "fuel_jumps": f.get("jumps_max"), "jump_range": p["jump_range"], "boost": p["boost"],
                "target": t and {"name": t.get("name"), "status": t.get("status"), "star_class": t.get("star_class")},
                "unsold": u.get("total"), "on_body": ob and ob["body"],
                "sampling": sm and "elsewhere" not in sm and {k: sm.get(k) for k in ("genus", "samples", "to_go", "clear")} or None,
                "carrier": c and {"name": c.get("name"), "system": c.get("system"), "distance": c.get("distance")},
                "commander": (p["commander"] or {}).get("name")}

    STATUS_FIELDS = {
        "system": lambda s: s["system"] or "",
        "fuel": lambda s: f"fuel {s['fuel_pct']}%" if s["fuel_pct"] is not None else "",
        "target": lambda s: f"-> {s['target']['name']} ({s['target']['status']})" if s["target"] else "",
        "unsold": lambda s: f"unsold {s['unsold'] / 1e6:.1f}M cr" if s["unsold"] else "",
        "region": lambda s: s["region"] or "",
        "body": lambda s: f"on {s['on_body']}" if s["on_body"] else "",
        "sampling": lambda s: (f"{s['sampling']['genus']} {s['sampling']['samples']}/3 " +
                               ("clear" if s["sampling"]["clear"] else f"{s['sampling']['to_go']} m to go")) if s["sampling"] and s["sampling"]["to_go"] is not None else "",
    }

    # readable by another site's page (a stream overlay): the only responses that say so (review F6); no credentials
    OPEN_HEADERS = {"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"}

    async def status_view(_):
        return web.json_response(status_small(), headers=OPEN_HEADERS)

    async def status_txt_view(request):
        """One line for an OBS text source: /api/status.txt?fields=system,fuel,target (the default set)."""
        s_ = status_small()
        fields = [f for f in (request.query.get("fields") or "system,fuel,target,unsold").split(",") if f in STATUS_FIELDS]
        line = " · ".join(x for x in (STATUS_FIELDS[f](s_) for f in fields) if x)
        return web.Response(text=line + "\n", content_type="text/plain", headers=OPEN_HEADERS)

    async def next_stop_view(request):
        try:
            body = await request.json()
            if not isinstance(body, dict):   # [1], "x", null: a bad request, not a 500
                raise TypeError("expected a JSON object")
            id64 = None if body.get("clear") else parse_id64(body["id"])
        except (ValueError, KeyError, TypeError):
            return web.json_response({"error": "bad request"}, status=400)
        if not state.set_next_stop(id64):
            return web.json_response({"error": "unknown system"}, status=404)
        return web.json_response({"ok": True})

    async def backup_view(_):
        body, status = state.start_backup()
        return web.json_response(body, status=status)

    async def highway_view(_):
        return web.json_response(state.highway_view())

    async def rail_view(_):
        """GET /api/rail: the tablet's rail now, with every context's set and catalogue for its editor."""
        return web.json_response(state.rail_info(full=True))

    async def rail_press_view(request):
        """POST /api/rail/press {context, id}: one tap of that button's key binding (see State.rail_press)."""
        body = await json_object(request)
        if body is None or not isinstance(body.get("context"), str) or not isinstance(body.get("id"), str):
            return web.json_response({"error": "expected {context, id}"}, status=400)
        out, status = await state.rail_press(body["context"], body["id"])
        return web.json_response(out, status=status)

    async def rail_sets_view(request):
        """POST /api/rail/sets {context, buttons: [{id, label?}]} or {context, reset: true}: the editor's save."""
        body = await json_object(request)
        if body is None or not isinstance(body.get("context"), str):
            return web.json_response({"error": "expected {context, buttons} or {context, reset: true}"}, status=400)
        out, status = state.rail_save(body["context"], body.get("buttons"), reset=body.get("reset") is True)
        return web.json_response(out, status=status)

    async def highway_plot_view(request):
        """Plot a Neutron Highway route with Spansh (in the background: GET /api/highway shows how it went)."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        out, status = state.highway_start_plot(body)
        return web.json_response(out, status=status)

    async def highway_clear_view(_):
        state.highway_clear()
        return web.json_response({"ok": True})

    async def riches_view(_):
        return web.json_response(state.riches_view())

    async def riches_plot_view(request):
        """Plot a Road to Riches route with Spansh (in the background: GET /api/riches shows how it went)."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        out, status = state.riches_start_plot(body)
        return web.json_response(out, status=status)

    async def riches_clear_view(_):
        state.riches_clear()
        return web.json_response({"ok": True})

    async def highway_autotarget_view(request):
        """The Highway tab's auto-target toggle and delay: {enabled?: bool, delay?: seconds 0-60}."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        enabled, delay = body.get("enabled"), body.get("delay")
        if enabled is not None and not isinstance(enabled, bool):
            return web.json_response({"error": "enabled must be true or false"}, status=400)
        if delay is not None and (isinstance(delay, bool) or not isinstance(delay, (int, float))
                                  or not math.isfinite(delay) or not 0 <= delay <= 60):
            return web.json_response({"error": "delay must be 0 to 60 seconds"}, status=400)
        state.set_autotarget(enabled, delay)
        return web.json_response(state.autotarget_info())

    async def highway_autotarget_test_view(_):
        """"Test now": one auto-target run against a system a plain jump away after a countdown, or why it cannot run."""
        body, status = state.start_autotarget_test()
        return web.json_response(body, status=status)

    async def highway_target_view(request):
        """Target next / Retry (review Q4): the next route system (off the route: the closest one) after a countdown,
        whether or not auto-target is on. {countdown?: 0-10 s} (default 5: the desktop page; the tablet sends 0)."""
        body = {}
        if request.can_read_body:
            body = await json_object(request)
            if body is None:
                return web.json_response({"error": "expected a JSON object"}, status=400)
        cd = body.get("countdown")
        if cd is not None and (isinstance(cd, bool) or not isinstance(cd, (int, float)) or not math.isfinite(cd)
                               or not 0 <= cd <= 10):
            return web.json_response({"error": "countdown must be 0 to 10 seconds"}, status=400)
        aim = None
        if "route" in body or "index" in body:   # 🎯 on a system of a route: {route: "highway" | "survey", index}
            aim = (body.get("route"), body.get("index"))
            if aim[0] not in ("highway", "survey") or isinstance(aim[1], bool) or not isinstance(aim[1], int):
                return web.json_response({"error": "route must be highway or survey, index a whole number"}, status=400)
        out, status = state.start_autotarget_run("next", cd, aim)
        return web.json_response(out, status=status)

    async def highway_background_view(_):
        """GET /api/highway/background: the image [highway] background_image names, and only that file (nothing in
        the request picks a path), only an image type checked by its extension and first bytes (highway_bg_file)."""
        path = state.highway_cfg.get("background_image") or ""
        if not path:
            return web.json_response({"error": "no [highway] background_image in the config"}, status=404)
        try:
            ctype, _ = highway_bg_file(path)
        except ValueError as e:
            return web.json_response({"error": f"background_image: {e}"}, status=404)
        return web.FileResponse(path, headers={"Content-Type": ctype, "Cache-Control": "no-cache",
                                               "X-Content-Type-Options": "nosniff"})

    regions_cache = {"rules": None, "body": None, "etag": None}

    async def regions_view(request):
        """GET /api/regions: the galactic region map for the Highway tab's galaxy map (outrider.bio.region_layer:
        klightspeed's run-length grid, the names and a label point per region), built once per rules file and
        answered with an ETag (304 when the page already has it), compressed (185 KB, about 40 KB gzipped)."""
        rules = outrider.bio.load_rules() if outrider.bio else None
        if rules is not regions_cache["rules"] or regions_cache["body"] is None:
            layer = outrider.bio.region_layer() if rules else None
            body = json.dumps(layer, separators=(",", ":")).encode() if layer else None
            regions_cache.update(rules=rules, body=body, etag=body and '"' + hashlib.sha1(body).hexdigest()[:20] + '"')
        if not regions_cache["body"]:
            return web.json_response({"error": "no region map (resources/bio_rules.json is missing)"}, status=404)
        headers = {"ETag": regions_cache["etag"], "Cache-Control": "no-cache"}
        if request.headers.get("If-None-Match") == regions_cache["etag"]:
            return web.Response(status=304, headers=headers)
        resp = web.Response(body=regions_cache["body"], content_type="application/json", headers=headers)
        resp.enable_compression()
        return resp

    async def highway_systems_view(request):
        """GET /api/highway/systems?q=: Spansh's system names starting with q (the to field as you type)."""
        q = " ".join((request.query.get("q") or "").split())
        if not 2 <= len(q) <= FIND_NAME_MAX:
            return web.json_response({"error": f"give 2 to {FIND_NAME_MAX} characters"}, status=400)
        try:
            return web.json_response({"q": q, "values": await state.highway_suggest(q)})
        except (ClientError, asyncio.TimeoutError, ValueError) as e:
            return web.json_response({"error": f"Spansh cannot be reached ({type(e).__name__})"}, status=502)

    async def synth(sp, text, speed, voice):
        """A line as WAV from Piper, or None (the page then uses browser speech for it). `speed` and `voice` as
        the page sent them: a personality's own voice only if installed, so a name from the page never downloads."""
        try:
            speed = float(speed or SPEECH_SPEED)
        except (TypeError, ValueError):
            speed = SPEECH_SPEED
        voice = str(voice) if voice else None
        if voice and voice not in sp.installed():
            voice = None
        if voice and state.speech:   # room for every personality voice, so none is reloaded before each line
            sp.size_extra(outrider.speech.style_voices(state.speech.lines()["styles"]))
        try:
            return await asyncio.get_running_loop().run_in_executor(None, sp.say, text, speed, voice)
        except Exception as e:  # noqa: BLE001 -- a line Piper cannot speak: the page uses browser speech for it
            print(f"spoken alerts: could not speak {text[:60]!r}: {type(e).__name__}: {e}", file=sys.stderr)
            return None

    async def say_view(request):
        """A spoken alert as WAV (Piper). 503 while no voice is ready: the page then uses browser speech."""
        text = outrider.tts.clip_text(request.query.get("text"))   # a long line is cut at a boundary, not mid-word
        sp = state.speaker
        if not sp or not sp.ready or not text.strip():
            return web.json_response({"error": "no Piper voice ready" if text.strip() else "no text"}, status=503)
        audio = await synth(sp, text, request.query.get("speed"), request.query.get("voice"))
        if not audio:
            return web.json_response({"error": "no Piper voice ready"}, status=503)
        return web.Response(body=audio, content_type="audio/wav", headers={"Cache-Control": "no-store"})

    prefetching = set()   # the warm-up tasks (kept so they are not collected mid-way)

    def prefetch(sp, d):
        """Synthesise the next queued line ({text, voice, speed}) into Speaker's cache while the current one plays, so
        it starts at once (review S11). Called only once the current line's audio exists: a warm-up that took the
        voice's lock first would make the line being said wait for it. Fire and forget: a failure costs nothing."""
        if not isinstance(d, dict) or not isinstance(d.get("text"), str) or not d["text"].strip() or not sp or not sp.ready:
            return None
        t = asyncio.get_running_loop().create_task(synth(sp, outrider.tts.clip_text(d["text"]), d.get("speed"), d.get("voice")))
        prefetching.add(t)
        t.add_done_callback(lambda x: (prefetching.discard(x), x.cancelled() or x.exception()))
        return t

    async def say_prefetch_view(request):
        """{text, voice, speed}: warm the cache with the line the page will say next (its own Piper path calls this once
        the current line's audio is in hand). 202 at once."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        prefetch(state.speaker, body)
        return web.json_response({"ok": True}, status=202)

    def no_player():
        """The 503 for "Play speech and sounds on this PC" when this machine has no player to use, or None."""
        pl = state.player
        if pl and pl.player:
            return None
        why = ("[speech] server_player is off" if pl and pl.choice == "off" else
               f"{pl.choice} is not installed" if pl and pl.choice != "auto" else
               "no audio player found (pw-play, paplay, aplay or ffplay)")
        return web.json_response({"error": why}, status=503)

    def json_row_id(v):
        """A JSON number that can be a rig or body id: a whole number (not true/false, not 1.0) SQLite can hold, from
        0 to 2**63 - 1; anything else (a 23-digit number) would fail in the query as a 500, not a 400."""
        return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 2 ** 63

    async def json_object(request):
        """The request's JSON body as a dict, or None."""
        try:
            body = await request.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    # "Play speech and sounds on this PC": the page still picks and queues the lines, and this machine's player
    # (outrider.tts.LinePlayer) says them, so no click on the page is needed. POSTs, so request_guard refuses another
    # site's request (the same Origin and Sec-Fetch-Site check GET /api/say gets).
    async def say_play_view(request):
        """{text, voice, speed, id}: speak a line here, answering only once it has played to the end or been
        stopped, so the page's queue (priority, expiry, danger cutting a find short) works unchanged. 409 while
        another line plays (two browsers never talk over each other), 503 with no Piper voice or no player: the
        page then says the line itself."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        refused = no_player()
        if refused:
            return refused
        text, sp = outrider.tts.clip_text(str(body.get("text") or "")), state.speaker
        if not text.strip():
            return web.json_response({"error": "no text"}, status=400)
        if not sp or not sp.ready:
            return web.json_response({"error": "no Piper voice ready"}, status=503)
        line = state.player.claim(str(body["id"])[:64] if body.get("id") else None)
        if line is None:
            return web.json_response({"error": "another line is playing"}, status=409)
        try:
            audio = await synth(sp, text, body.get("speed"), body.get("voice"))
            if not audio:
                return web.json_response({"error": "no Piper voice ready"}, status=503)
            prefetch(sp, body.get("next"))   # the page's next line, made while this one plays
            result = await state.player.play_line(line, outrider.tts.scale_wav(audio, body.get("volume")))
        finally:
            state.player.release(line)
        if result == "failed":
            return web.json_response({"error": f"{state.player.name} could not play it"}, status=503)
        if result == "capped":   # it played up to the time limit, not to its end: the page logs it as cut
            return web.json_response({"ok": True, "stopped": True, "capped": True})
        return web.json_response({"ok": True, "stopped": result == "stopped"})

    async def say_stop_view(request):
        """{id}: cut that line short (without an id, whatever is playing). A stop that arrives before its line
        is remembered, so the line is not then played."""
        body = await json_object(request) if request.can_read_body else {}
        line_id = str(body["id"])[:64] if body and body.get("id") else None
        return web.json_response({"ok": True, "stopped": state.player.stop(line_id) if state.player else False})

    async def sound_play_view(request):
        """{name}: start one of sounds.json's sounds here and answer at once (a sound may overlap a line, as in
        the browser). 503 with no player: the page plays it itself."""
        body = await json_object(request)
        if body is None or not isinstance(body.get("name"), str):
            return web.json_response({"error": "expected {name}"}, status=400)
        refused = no_player()
        if refused:
            return refused
        try:
            wav = await asyncio.get_running_loop().run_in_executor(None, state.sounds.wav, body["name"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            return web.json_response({"error": f"sounds: {e}"}, status=503)
        if wav is None:
            return web.json_response({"error": "no such sound"}, status=404)
        state.player.play_sound(outrider.tts.scale_wav(wav, body.get("volume")))
        return web.json_response({"ok": True})

    async def sound_file_view(request):
        """GET /api/sound/file/<name>: your own file for that sound ([speech] sound_dir), for the page to decode
        ahead of time; 404 when there is none."""
        data = state.sounds.own_file(request.match_info["name"]) if state.sounds else None
        if not data:
            return web.json_response({"error": "no such sound file"}, status=404)
        return web.Response(body=data, content_type="audio/wav", headers={"Cache-Control": "no-store"})

    async def speech_view(_):
        """The spoken alerts' lines (speech.json, less the banned ones): the page asks again when the payload's
        version changes."""
        return web.json_response(state.speech.lines() if state.speech else {"styles": {}, "lines": {}, "version": None})

    async def speech_ban_view(request):
        """{alert, template}: /api/speech/ban leaves that line out from now on (in data/speech_banned.json, or next to
        a speech file of your own), /api/speech/unban brings it back. Only a line that is in the speech file is accepted, and the
        last line of a list cannot be banned. Behind request_guard like every POST."""
        body = await json_object(request)
        if body is None or not isinstance(body.get("alert"), str) or not isinstance(body.get("template"), str):
            return web.json_response({"error": "expected {alert, template}"}, status=400)
        if not state.speech:
            return web.json_response({"error": "no speech file"}, status=503)
        status, out = state.speech.set_ban(body["alert"], body["template"], request.path.endswith("/ban"))
        if status == 200:
            state.bump()   # the new version sends every page for the trimmed lines
        return web.json_response(out, status=status)

    async def hush_view(request):
        """{mode: "10m" | "30m" | "jump" | "off"}: hush the voice (danger lines still speak) or end the hush."""
        body = await json_object(request)
        if body is None or body.get("mode") not in (*HUSH_MODES, "off"):
            return web.json_response({"error": "expected {mode: 10m, 30m, jump or off}"}, status=400)
        state.set_hush(body["mode"])
        return web.json_response({"ok": True, "hush": state.hush_info()})

    def local_get():
        """The read-only tools' `get` inside the server: the GET route's own handler, called in-process (no HTTP back to
        this server, no session needed; outrider.tools allows only its READ_ROUTES)."""
        from aiohttp.test_utils import make_mocked_request

        async def get(path, params):
            url = outrider.tools.query(path, params)
            probe = make_mocked_request("GET", url, app=app)
            match = await app.router.resolve(probe)
            if match.http_exception is not None:
                return {"error": f"no route {path}"}
            req = make_mocked_request("GET", url, app=app, match_info=dict(match))
            resp = await match.handler(req)
            try:
                return json.loads(resp.body if isinstance(resp.body, (bytes, str)) else resp.text)
            except (TypeError, ValueError):
                return {"error": f"{path} answered no JSON"}
        return get

    def pc_only(handler):
        """A route that presses keys or plays on this PC: refused on a server away from the game PC ([server] game_pc)."""
        async def guarded(request):
            if not state.game_pc:
                return web.json_response({"error": NOT_GAME_PC, "code": "not_game_pc"}, status=409)
            return await handler(request)
        return guarded

    async def config_get_view(_):
        """GET /api/config: every config key for the Settings dialog's Server settings (secrets only as set or not)."""
        return web.json_response(state.config_info())

    async def config_post_view(request):
        """POST /api/config {section: {key: value}}: written into the config file (applied at the next start)."""
        body = await json_object(request)
        out, status = state.config_save(body)
        return web.json_response(out, status=status)

    async def ask_view(request):
        """POST /api/ask {text, source?} (the tablet app's voice; native-facing contract): {answer, spoken, matched,
        command}; errors {error, code}: bad_request, app_too_old, ai_off / ai_timeout / ai_error."""
        old = app_too_old(request)
        if old:
            return old
        body = await json_object(request)
        text = body.get("text") if body else None
        if not isinstance(text, str) or not text.strip() or len(text) > outrider.ask.TEXT_MAX:
            return web.json_response({"error": f"expected {{text}}: the question, 1 to {outrider.ask.TEXT_MAX} characters",
                                      "code": "bad_request"}, status=400)
        out, status = await state.ask(" ".join(text.split()), local_get())
        return web.json_response(out, status=status)

    async def copilot_view(request):
        """{action: "status" | "again" | "hush" | "replay", words?}: the speaking window does it (the button and a
        tablet's Now bar post here, so a tap anywhere speaks through the window that is speaking)."""
        body = await json_object(request)
        if body is None or body.get("action") not in COPILOT_ACTIONS:
            return web.json_response({"error": "expected {action: " + ", ".join(COPILOT_ACTIONS) + "}"}, status=400)
        words = body.get("words")
        if body["action"] == "replay" and not (isinstance(words, str) and words.strip()):
            return web.json_response({"error": "replay needs the words"}, status=400)
        state.copilot_action(body["action"], outrider.tts.clip_text(words) if body["action"] == "replay" else None)
        return web.json_response({"ok": True, "seq": state.copilot["seq"]})

    async def autohonk_test_view(_):
        body, status = state.start_honk_test()
        return web.json_response(body, status=status)

    async def autohonk_forget_view(_):
        state.forget_honk_groups()   # the current ship's learned fire groups
        return web.json_response(state.autohonk_info())

    async def uploads_view(request):
        """POST /api/uploads {service: "eddn" | "edsm", on: bool}: the page's switch for one uploader."""
        body = await json_object(request)
        if body is None or body.get("service") not in outrider.uploads.SERVICES or not isinstance(body.get("on"), bool):
            return web.json_response({"error": "expected {service: \"eddn\" or \"edsm\", on: true or false}"}, status=400)
        if body["on"]:
            why = state.check_upload_start(body["service"], body.get("confirm") is True)
            if why:
                return web.json_response({"error": why[1], "code": why[0]}, status=409)
        note = state.set_upload(body["service"], body["on"])
        state.refresh_leases()   # the lease says so at once
        return web.json_response(dict(state.uploads_summary(), **({"note": note} if note else {})))

    async def edsm_account_view(request):
        """POST /api/uploads/edsm {commander, name?, api_key?, remove?}: an in-game commander's EDSM account (the key
        stays here; nothing answers with it)."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected a JSON object"}, status=400)
        out, status = state.set_edsm_account(body.get("commander"), body.get("name"), body.get("api_key"),
                                             remove=body.get("remove") is True)
        return web.json_response(out, status=status)

    async def autohonk_view(request):
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"error": "expected JSON"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "expected a JSON object"}, status=400)
        if not isinstance(body.get("enabled"), bool):   # "false" (a string) would switch it on (CX-F10)
            return web.json_response({"error": "enabled must be true or false"}, status=400)
        state.set_autohonk(body["enabled"])
        return web.json_response(state.autohonk_info())

    async def voice_view(request):
        try:
            name = str((await request.json())["voice"])[:100]
        except (ValueError, KeyError, TypeError):
            return web.json_response({"error": "bad request"}, status=400)
        if not state.speaker or not state.speaker.available:
            return web.json_response({"error": "Piper is not installed"}, status=503)
        if not state.speaker.use(name):
            return web.json_response({"error": "not a Piper voice name"}, status=400)
        # remembered (over restarts, like the radius and auto honk) once it loads: see remember_voice
        return web.json_response({"ok": True})

    async def speaker_audio_view(request):
        """POST /api/speaker/audio {blocked}: the speaking window's browser holds audio back until a click (true) or
        plays again (false). The payload's speaker_audio_blocked tells the tablet, which asks for that click."""
        body = await json_object(request)
        if body is None or not isinstance(body.get("blocked"), bool):
            return web.json_response({"error": "expected {blocked: true or false}"}, status=400)
        state.speaker_seen = time.monotonic()
        if state.speaker_audio_blocked != body["blocked"]:
            state.speaker_audio_blocked = body["blocked"]
            state.bump()
        return web.json_response({"ok": True})

    async def voice_catalogue_view(request):
        """GET /api/voices/catalogue[?refresh=1]: Piper's voices for Settings > Voice > More voices, {voices: [{name,
        language, language_name, quality, speakers, size_mb, installed}], current}. One is fetched and used with POST
        /api/voice (the server downloads it): a Docker install has no voice lab. 503 without Piper, 502 offline."""
        if not state.speaker or not state.speaker.available:
            return web.json_response({"error": "Piper is not installed", "code": "no_piper"}, status=503)
        try:
            doc = await asyncio.get_running_loop().run_in_executor(
                None, lambda: outrider.tts.fetch_catalogue(force=request.query.get("refresh") == "1"))
        except (OSError, ValueError) as e:
            return web.json_response({"error": f"Piper's voice list cannot be fetched ({e})", "code": "catalogue_unavailable"}, status=502)
        return web.json_response({"voices": outrider.tts.catalogue_summary(doc, state.speaker.installed()),
                                  "current": state.speaker.voice_name})

    async def radius_view(request):
        try:
            r = float((await request.json())["radius"])
        except (ValueError, KeyError, TypeError):
            return web.json_response({"error": "bad request"}, status=400)
        if r not in RADIUS_CHOICES and r != state.radius:
            return web.json_response({"error": "radius must be one of " + ", ".join(f"{x:g}" for x in RADIUS_CHOICES)}, status=400)
        state.set_radius(r)
        return web.json_response({"radius": state.radius})

    async def materials_view(_):
        inv = outrider.materials.inventory(state.journals.materials)
        inv["stale"] = bool((state.materials_summary() or {}).get("stale"))
        inv["sources"] = state.material_sources()
        inv["mining_sites"] = state.mining_sites()
        inv["cargo"] = state.cargo_summary()
        return web.json_response(inv)

    async def cargo_lookup_view(request):
        """GET /api/cargo/lookup?commodity=&mode=sell|buy&tons=&from=ship|carrier|here&sort=&within=&age=&carriers=&pad=:
        Spansh's stations for it (State.cargo_lookup). Read only: nothing is stored but Spansh's name list."""
        out, status = await state.cargo_lookup(dict(request.query))
        return web.json_response(out, status=status)

    async def nearest_view(request):
        """GET /api/nearest?stations=&carriers=&need=&age=&permit=&pad=&cached=: the nearest places to dock."""
        out, status = await state.nearest_dock(dict(request.query))
        return web.json_response(out, status=status)

    async def cargo_recount_view(request):
        """POST /api/cargo/recount {counts: {commodity: tons}}: your counts for your carrier's untracked lines."""
        body = await json_object(request)
        if body is None:
            return web.json_response({"error": "expected {counts: {commodity: tons}}"}, status=400)
        out, status = state.cargo_recount(body.get("counts"))
        return web.json_response(out, status=status)

    async def log_view(request):
        if not outrider.log:
            return web.json_response({"error": "outrider/log.py is missing"}, status=500)
        qs = request.query
        try:
            days = max(1, min(int(qs.get("days", 7)), 3650))
            limit = max(1, min(int(qs.get("limit", 200)), 500))
        except ValueError:
            return web.json_response({"error": "bad request"}, status=400)
        cats = {c for c in qs["cat"].split(",") if c in outrider.log.CATEGORIES} if "cat" in qs else None  # empty: nothing
        kw = dict(days=days, limit=limit, cats=cats, q=(qs.get("q") or "").strip()[:200] or None,
                  noise=qs.get("noise") in ("1", "true"), before=qs.get("before"), after=qs.get("after"))
        dirs = LIVE_DIRS + LEGACY_DIRS
        out = await asyncio.get_running_loop().run_in_executor(None, lambda: outrider.log.read_log(dirs, **kw))
        return web.json_response(out)

    async def export_view(request):
        what, fmt = request.query.get("what", "firsts"), request.query.get("format", "csv")
        if what == "system":   # one system's bodies and values (Pioneer's export), from Here
            try:
                id64 = parse_id64(request.query.get("id"))
            except (ValueError, TypeError):
                return web.json_response({"error": "id: a system id64"}, status=400)
            cols, rows, name = state.export_system(id64)
            if cols is None:
                return web.json_response({"error": "unknown system"}, status=404)
            what = "system-" + re.sub(r"[^A-Za-z0-9_-]+", "_", name or str(id64)).strip("_")
        elif what == "unsold":  # a full journal pass: keep it off the event loop
            cols, rows = await asyncio.get_running_loop().run_in_executor(None, state.export_rows, what)
        else:
            cols, rows = state.export_rows(what)
        if cols is None:
            return web.json_response({"error": "unknown export"}, status=400)
        stamp = time.strftime("%Y%m%d")
        if fmt == "json":
            return web.json_response(rows, headers={"Content-Disposition": f'attachment; filename="{what}-{stamp}.json"'})
        import csv
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
        return web.Response(text=buf.getvalue(), content_type="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{what}-{stamp}.csv"'})

    app.router.add_get("/api/nearby", nearby)
    app.router.add_get("/api/version", version_view)
    app.router.add_post("/api/auth/signin", signin_view)
    app.router.add_post("/api/auth/signout", signout_view)
    app.router.add_get("/signin", signin_page)
    app.router.add_get("/api/map", map_view)
    app.router.add_get("/api/system/{id64}", system_view)
    app.router.add_get("/api/history", history_view)
    app.router.add_get("/api/organics", organics_view)
    app.router.add_get("/api/checklist", checklist_view)
    app.router.add_get("/api/log", log_view)
    app.router.add_get("/api/materials", materials_view)
    app.router.add_post("/api/cargo/recount", cargo_recount_view)
    app.router.add_get("/api/cargo/lookup", cargo_lookup_view)
    app.router.add_get("/api/nearest", nearest_view)
    app.router.add_post("/api/radius", radius_view)
    app.router.add_get("/api/say", say_view)
    app.router.add_post("/api/say/play", pc_only(say_play_view))
    app.router.add_post("/api/say/prefetch", say_prefetch_view)
    app.router.add_get("/api/sound/file/{name}", sound_file_view)
    app.router.add_post("/api/say/stop", say_stop_view)
    app.router.add_post("/api/sound/play", pc_only(sound_play_view))
    app.router.add_get("/api/speech", speech_view)
    app.router.add_post("/api/speech/ban", speech_ban_view)
    app.router.add_post("/api/speech/unban", speech_ban_view)
    app.router.add_post("/api/hush", hush_view)
    app.router.add_post("/api/copilot", copilot_view)
    app.router.add_post("/api/backup", backup_view)
    app.router.add_get("/api/highway", highway_view)
    app.router.add_get("/api/rail", rail_view)
    app.router.add_post("/api/ask", ask_view)
    app.router.add_get("/api/config", config_get_view)
    app.router.add_post("/api/config", config_post_view)
    app.router.add_post("/api/rail/press", pc_only(rail_press_view))
    app.router.add_post("/api/rail/sets", pc_only(rail_sets_view))
    app.router.add_get("/api/highway/systems", highway_systems_view)
    app.router.add_get("/api/highway/background", highway_background_view)
    app.router.add_get("/api/regions", regions_view)
    app.router.add_post("/api/highway/plot", highway_plot_view)
    app.router.add_get("/api/riches", riches_view)
    app.router.add_post("/api/riches/plot", riches_plot_view)
    app.router.add_post("/api/riches/clear", riches_clear_view)
    app.router.add_post("/api/highway/clear", highway_clear_view)
    app.router.add_post("/api/highway/autotarget", pc_only(highway_autotarget_view))
    app.router.add_post("/api/highway/autotarget/test", pc_only(highway_autotarget_test_view))
    app.router.add_post("/api/highway/target", pc_only(highway_target_view))
    app.router.add_get("/api/defaults", defaults_get)
    app.router.add_post("/api/defaults", defaults_post)
    app.router.add_post("/api/nextstop", next_stop_view)
    app.router.add_get("/api/status", status_view)
    app.router.add_get("/api/status.txt", status_txt_view)
    app.router.add_post("/api/voice", voice_view)
    app.router.add_get("/api/voices/catalogue", voice_catalogue_view)
    app.router.add_post("/api/speaker/audio", speaker_audio_view)
    app.router.add_post("/api/autohonk", pc_only(autohonk_view))
    app.router.add_post("/api/uploads", uploads_view)
    app.router.add_post("/api/uploads/edsm", edsm_account_view)
    app.router.add_post("/api/autohonk/test", pc_only(autohonk_test_view))
    app.router.add_post("/api/autohonk/forget", pc_only(autohonk_forget_view))
    app.router.add_get("/api/firsts", firsts_view)
    app.router.add_get("/api/left", left_view)
    app.router.add_get("/api/body", body_view)
    app.router.add_get("/api/find", find_view)
    app.router.add_get("/api/export", export_view)
    app.router.add_post("/api/search", search_start)
    app.router.add_get("/api/search", search_get)
    app.router.add_post("/api/bookmark", bookmark)
    app.router.add_post("/api/rigs/remove", rigs_remove_view)
    app.router.add_post("/api/sites/forget", sites_forget_view)
    return app


def newer_release(answer, current):
    """GitHub's latest-release answer as {version, url, published} when it is newer than `current`, else None (the same
    or older, a draft or pre-release, or an answer that is not a release). Tags look like v2026.10.13."""
    if not isinstance(answer, dict) or answer.get("draft") or answer.get("prerelease"):
        return None
    tag = answer.get("tag_name")
    if not isinstance(tag, str):
        return None
    version = tag.strip().lstrip("vV")
    have, new = outrider.auth.version_tuple(current), outrider.auth.version_tuple(version)
    if not new or new <= have:
        return None
    url = answer.get("html_url")
    return {"version": version, "published": str(answer.get("published_at") or "")[:10],
            "url": url if isinstance(url, str) and url.startswith("https://github.com/") else RELEASES_PAGE}


def install_kind(root=None, env=None):
    """How this copy of Outrider was installed, for the update's instructions: "docker" (the image sets
    OUTRIDER_CONTAINER), "git" (a clone: git pull), else "download" (a release's source: download the new one)."""
    env = os.environ if env is None else env
    if env.get("OUTRIDER_CONTAINER"):
        return "docker"
    return "git" if os.path.exists(os.path.join(root or outrider.ROOT, ".git")) else "download"


async def check_bio_rules(state):
    """Keep the exobiology spawn rules current. A copy ships with Outrider (without ExploData's colour tables, which
    are downloaded on the first start into resources/bio_colours.json); each start asks GitHub whether BioScan,
    ExploData or the region map changed and fetches the new data if so (offline just keeps the copy). Rows carry bio
    estimates, so they are rebuilt after an update."""
    try:
        updated = await asyncio.get_running_loop().run_in_executor(None, lambda: outrider.bio.update_if_newer(log=print))
    except Exception as e:  # noqa: BLE001 -- no shipped copy and no network: the page works without predictions
        print(f"exobiology rules: none available ({e}); no species guesses until "
              f"python3 -m outrider.bio --update-rules  succeeds.", file=sys.stderr)
        return
    info = outrider.bio.rules_info()
    if updated:
        print(f"exobiology rules: updated from BioScan ({info['species']} species)")
        state.journals.dirty |= set(state.bases)
    elif updated is None:   # could not check or update: update_if_newer said why
        print(f"exobiology rules: {info['species']} species from BioScan (copy from {(info.get('generated') or '')[:10]})")
    else:
        print(f"exobiology rules: {info['species']} species from BioScan, up to date")


def speech_file_path(name, root=None, resources=None):
    """[server] speech_file, resolved: relative to the repository folder, ~ expanded; the shipped file when unset.
    A relative name missing there but present in resources/ (a config written before the layout move, with
    speech_file = "speech.json") is taken from resources/, with a warning (review F22)."""
    return outrider.speech.resolve_speech_file(name, root or SCRIPT_DIR, SPEECH_FILE, resources or outrider.RESOURCES_DIR,
                                               warn=lambda text: print(text, file=sys.stderr))


def migrate_old_layout(db_path, root=None, data=None, log=print):
    """Before the data/ folder (2026-10-01) your files sat in the repository folder: the database, its
    browser_defaults.json, speech_banned.json, backups/ and piper-voices/. When the database is the default one in
    data/ and missing there, but the old one is at the root, they move into data/, each once, saying so (review
    F22). Nothing is overwritten: what already exists in data/ stays, and the old copy with it. -> what moved."""
    import shutil
    root, data = root or SCRIPT_DIR, data or outrider.DATA_DIR
    old_db = os.path.join(root, os.path.basename(db_path))
    if os.path.exists(db_path) or not os.path.isfile(old_db) or \
            os.path.normcase(os.path.abspath(os.path.dirname(db_path))) != os.path.normcase(os.path.abspath(data)):
        return []
    os.makedirs(data, exist_ok=True)
    moved = []
    names = [os.path.basename(db_path) + x for x in ("", "-wal", "-shm")] + \
        [BROWSER_DEFAULTS_FILE, "speech_banned.json", "backups", "piper-voices"]
    for n in names:
        src, dst = os.path.join(root, n), os.path.join(data, n)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.move(src, dst)
            moved.append(n)
    if moved:
        log(f"moved from the repository folder into {data} (the new layout): {', '.join(moved)}")
    return moved


def listen_problem(host, port):
    """Why we cannot listen on host:port, in words, or None. Checked before the journal import so a second copy fails
    fast. A port in use says "already running?"; an address that is not this machine's (a LAN address DHCP has
    changed, a typo, a name that does not resolve) says so, not that the port is taken (review F20)."""
    import errno
    import socket
    here = f"cannot listen on {host}:{port}"
    not_mine = (' (is [server] host this machine\'s address or name? "127.0.0.1" is this PC only, '
                '"0.0.0.0" every address it has)')
    try:
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as sock:
            # on Windows SO_REUSEADDR lets a bind share a port another socket listens on (the check never found a
            # running Outrider there); exclusive use is what tells. Elsewhere it only skips TIME_WAIT, as the server does
            if os.name == "nt":
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return None
    except socket.gaierror as e:
        return f"{here}: {e.strerror or e}{not_mine}"
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return (f"port {port} is already in use: is ED Outrider already running? "
                    f"(open http://127.0.0.1:{port}/, or start this one with --port N)")
        if e.errno == errno.EADDRNOTAVAIL:
            return f"{here}: {e.strerror or e}{not_mine}"
        return f"{here}: {e.strerror or e}"


def port_free(host, port):
    """Can we listen on host:port?"""
    return listen_problem(host, port) is None


def list_backups(folder, db_path):
    """--list-backups: one line per zip of db_path's (see backup_zips), oldest first."""
    try:
        zips = backup_zips(folder, db_path)
    except OSError as e:
        return [f"no backups: {folder}: {e.strerror or e}"]
    if not zips:
        return [f"no backups of {os.path.basename(db_path)} in {folder}"]
    out = []
    for f in zips:
        st = os.stat(os.path.join(folder, f))
        out.append(f"{f}  {st.st_size / 1e6:8.1f} MB  {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}")
    return out


def forget_upload_position(path):
    """A restored database's uploads start from where the journals are now, not from the backup's marks: what was
    sent since the backup is not sent again, nor the backup's own unsent rows (EDDN's are stale by now)."""
    con = sqlite3.connect(path)
    try:
        con.execute("DELETE FROM meta WHERE key = 'upload_marks'")
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='upload_queue'").fetchone():
            con.execute("DELETE FROM upload_queue WHERE state = 'queued'")
        con.commit()
    except sqlite3.Error:   # an older backup without these tables: nothing to forget
        pass
    finally:
        con.close()


def restore_backup(zip_path, db_path, host, port, now=None):
    """--restore: put the database (and browser_defaults.json, when the zip holds it) from a backup zip back in
    place. Refuses while host:port is bound (a running Outrider holds the database open); checks the zip
    (testzip) and the database in it (quick_check, extracted to a temp file next to the target) before
    touching anything; the current database moves aside to <db>.pre-restore-<stamp> (with its -journal, when
    one is left over), and browser_defaults.json the same way. Returns the lines to print; raises
    RuntimeError with the reason when it will not restore."""
    import shutil
    import zipfile
    problem = listen_problem(host, port)
    if problem and "already in use" in problem:   # only a port in use means a running Outrider may hold the database
        raise RuntimeError(f"port {port} is in use: stop ED Outrider first (a running one holds the database open)")
    bad = check_zip(zip_path)
    if bad:
        raise RuntimeError(f"{zip_path} failed its check: {bad}")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    defaults = browser_defaults_path(db_path)
    n = 1
    while any(os.path.exists(f"{p}.pre-restore-{stamp}") for p in (db_path, defaults)):   # never replace one
        n += 1
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{n}"
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        dbs = [n for n in names if n.endswith(".sqlite") and "/" not in n]
        # the zip names the database after the file it was made from, whatever its extension (--db mydata.db: F33)
        member = os.path.basename(db_path) if os.path.basename(db_path) in names else dbs[0] if len(dbs) == 1 else None
        if not member:
            raise RuntimeError(f"{zip_path} holds no single database ({', '.join(names) or 'empty'})")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        tmp = f"{db_path}.restore-{stamp}.part"
        try:
            with z.open(member) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            problem = check_database(tmp)
            if problem:
                raise RuntimeError(f"the database in {zip_path} failed its check: {problem}")
            forget_upload_position(tmp)
            doc = None
            if BROWSER_DEFAULTS_FILE in names:
                doc = z.read(BROWSER_DEFAULTS_FILE)
                try:
                    parsed = json.loads(doc)
                except ValueError:
                    raise RuntimeError(f"{BROWSER_DEFAULTS_FILE} in {zip_path} is not JSON") from None
                if not (isinstance(parsed, dict) and isinstance(parsed.get("settings"), dict)):   # Codex F9
                    raise RuntimeError(f"{BROWSER_DEFAULTS_FILE} in {zip_path} is not a settings document")
            lines = []
            if os.path.exists(db_path):
                aside = f"{db_path}.pre-restore-{stamp}"
                os.replace(db_path, aside)
                # a leftover rollback journal belongs to the old file: it goes with it (SQLite finds it by name)
                for ext in ("-journal", "-wal", "-shm"):
                    if os.path.exists(db_path + ext):
                        os.replace(db_path + ext, aside + ext)
                lines.append(f"the old database is kept as {aside}")
            os.replace(tmp, db_path)
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
    lines.insert(0, f"restored {db_path} from {zip_path} ({member})")
    if doc is not None:
        # the new file first, then the old one aside: a write that fails (a full disk) leaves the old defaults in
        # place, and the database, already restored, is reported as restored (review F34)
        try:
            with open(defaults + ".part", "wb") as f:
                f.write(doc)
        except OSError as e:
            lines.append(f"the database is restored, but {defaults} could not be written ({e.strerror or e}); "
                         + ("the old one stays" if os.path.exists(defaults) else "there is none"))
            try:
                os.remove(defaults + ".part")
            except OSError:
                pass
        else:
            if os.path.exists(defaults):
                os.replace(defaults, f"{defaults}.pre-restore-{stamp}")
                lines.append(f"restored {defaults} (the old one is kept as {defaults}.pre-restore-{stamp})")
            else:
                lines.append(f"restored {defaults}")
            os.replace(defaults + ".part", defaults)
    rest = [n for n in names if n not in (member, BROWSER_DEFAULTS_FILE)]
    if rest:
        lines.append(f"also in the zip, not restored: {', '.join(rest)} (unzip one by hand if you want it back)")
    return lines


async def run(args, st):
    global LIVE_DIRS, LEGACY_DIRS, UNSOLD_WARN, UNSOLD_URGENT, BIO_MIN, SOUNDS_DEFAULT, BODY_HIGHLIGHT, BIO_HIGHLIGHT, MAX_INCLUDE_BONUS, RADIUS_CHOICES, VOICE, VOICE_FALLBACK, BACKUP_DIR
    global SPEECH_STYLES, SPEECH_PROFANITY, SPEECH_NAMES, SPEECH_SPEED, SPEAK_BIO_SIGNALS, SPEAK_GEO_SIGNALS, SPEECH_PROFANITY_PCT
    global SPEAK_MAPPED, CODEX_INTERESTING
    global SPEECH_DANGER_BUSINESS, HIGH_GRAVITY, MODULE_WARN, BACKUP_KEEP, BACKUP_EVERY_DAYS
    global SPANSH_CONCURRENCY, MAP_MAX_RADIUS, MAP_MAX_PAGES
    global SURFACE_ALT, RIG_SPACING, SURFACE_MAP_MIN, SURFACE_MAP_STRIP, RIG_WARN
    LIVE_DIRS = unique_dirs(d for d in st["live"] if os.path.isdir(d))
    LEGACY_DIRS = [d for d in st["legacy"] if os.path.isdir(d)]
    for d in st["live"] + st["legacy"]:
        if not os.path.isdir(d):
            print(f"journal folder not found, skipping: {d}", file=sys.stderr)
    UNSOLD_WARN, UNSOLD_URGENT, BIO_MIN, SOUNDS_DEFAULT = st["unsold_warn"], st["unsold_urgent"], st["bio_min"], st["sounds"]
    BODY_HIGHLIGHT, BIO_HIGHLIGHT, MAX_INCLUDE_BONUS = st["body_highlight"], st["bio_highlight"], st["max_include_bonus"]
    HIGH_GRAVITY, MODULE_WARN = st["high_gravity"], st["module_warn"]
    SURFACE_ALT, RIG_SPACING, SURFACE_MAP_MIN = st["surface_alt"], st["rig_spacing"], st["surface_map_min"]
    SURFACE_MAP_STRIP, RIG_WARN = st["surface_map_strip"], st["rig_warn"]
    RADIUS_CHOICES = tuple(st["radius_choices"])
    VOICE, VOICE_FALLBACK = st["voice"], st["voice_fallback"]
    SPEECH_STYLES, SPEECH_PROFANITY, SPEECH_NAMES = tuple(st["speech_styles"]), st["speech_profanity"], st["speech_names"]
    SPEECH_SPEED, SPEECH_PROFANITY_PCT = st["speech_speed"], st["speech_profanity_pct"]
    SPEECH_DANGER_BUSINESS = st["speech_danger_business"]
    SPEAK_BIO_SIGNALS, SPEAK_GEO_SIGNALS = st["speak_bio_signals"], st["speak_geo_signals"]
    SPEAK_MAPPED, CODEX_INTERESTING = st["speak_mapped"], st["codex_interesting"]
    BACKUP_DIR, BACKUP_KEEP, BACKUP_EVERY_DAYS = st["backup_dir"], st["backup_keep"], st["backup_every_days"]
    SPANSH_CONCURRENCY, MAP_MAX_RADIUS, MAP_MAX_PAGES = st["concurrency"], st["map_max_radius"], st["map_max_pages"]
    radius_flag = args.radius   # --radius on the command line beats a radius chosen on the page
    args.host, args.port, args.radius, args.db = st["host"], st["port"], st["radius"], st["db"]
    if outrider.unsold:
        outrider.unsold.LIVE_DIRS, outrider.unsold.LEGACY_DIRS = LIVE_DIRS, LEGACY_DIRS
        outrider.unsold.DEFAULT_DIRS = LIVE_DIRS + LEGACY_DIRS
    if not LIVE_DIRS:
        print("No Elite Dangerous journal folder found. Pass --journals PATH (the folder holding "
              "Journal.*.log, usually '<Saved Games>/Frontier Developments/Elite Dangerous') or set "
              "ED_JOURNALS.", file=sys.stderr)
    else:
        print("journals: " + ", ".join(LIVE_DIRS) + (f"  (legacy: {', '.join(LEGACY_DIRS)})" if LEGACY_DIRS else ""))
        for line in nfs_cache_warnings(LIVE_DIRS):
            print(line, file=sys.stderr)
    problem = listen_problem(args.host, args.port)
    if problem:
        print(problem, file=sys.stderr)
        raise SystemExit(1)
    migrate_old_layout(args.db)   # an upgrade from before data/: your database and files come along
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)   # data/ on a fresh copy
    db = open_db(args.db, rescan=args.rescan)
    journals = Journals(db)

    # a stop (SIGTERM: docker stop, systemd) during the import, which is synchronous: end at once with what is read
    # kept (each journal file is committed as it is read) instead of being killed with it all rolled back (review R13);
    # once serving, the event loop's handler below takes over and stops through the usual cleanup
    def stop_during_start(signum, frame):
        # the files read whole are committed already (commit_each); the one part way through is dropped, not kept
        # without its offset (the next start would read it again and double what it counts)
        db.rollback()
        print("stopped during start-up (the journals not read yet are read at the next start)")
        raise SystemExit(0)
    try:
        signal.signal(signal.SIGTERM, stop_during_start)
    except ValueError:   # not the main thread (a test): no handler
        pass
    sweep_backup_leftovers(BACKUP_DIR, db.execute("PRAGMA database_list").fetchone()[2] or DB_PATH)
    t = time.time()
    journals.import_legacy()
    for d in LIVE_DIRS:
        journals.scan_dir(d, commit_each=True, upload="catchup")
        journals.read_navroute(d)
        journals.read_status(d)
    db.commit()
    if journals.last_event_ts is None:   # first run on an already-read database: look at the newest file's tail
        for d in LIVE_DIRS:
            files = sorted(glob(os.path.join(glob_escape(d), "Journal.*.log")))
            if files:
                with open(files[-1], "rb") as f:
                    f.seek(max(0, os.path.getsize(files[-1]) - 4096))
                    tail = f.read()
                if b'"timestamp":"' in tail:
                    journals.last_event_ts = tail.rsplit(b'"timestamp":"', 1)[-1][:20].decode("ascii", "replace")
                    meta_set(db, "last_event_ts", journals.last_event_ts)
    n = db.execute("SELECT count(*) FROM visits").fetchone()[0]
    print(f"journals up to date in {time.time() - t:.1f}s: {n} systems visited")
    if journals.pos:
        print(f"current system: {journals.pos['name']}")
    elif LIVE_DIRS:
        print("no jump found in the journals yet: the page fills in after your first FSD jump")

    spansh = Spansh(db)
    await spansh.start()
    chosen = meta_get(db, "radius_choice")   # picked from the page's Where tile; survives a restart
    usable = chosen and radius_flag is None and float(chosen) in RADIUS_CHOICES   # the config may have dropped it
    state = State(db, journals, spansh, float(chosen) if usable else args.radius)
    state.password = st["password"]
    state.assistant = st["assistant"]
    state.searcher = Searcher(state)
    state.db_path = args.db
    state.speech_path, state.config_path = st["speech_file"], args.config
    loop = asyncio.get_running_loop()
    voice = meta_get(db, "voice_choice")   # picked in the alerts dialog: beats the config file once used
    # a Piper name, or any voice installed in piper-voices/ (a self-made one: the dialog lets you pick it, and it was
    # forgotten at every restart)
    if not (isinstance(voice, str) and (outrider.tts.VOICE_NAME.fullmatch(voice)
                                        or voice in outrider.tts.installed_voices(outrider.tts.VOICES_DIR))):
        voice = VOICE
    # the voice picked in the dialog is remembered once it loads, on the loop thread (not Piper's)
    state.speaker = outrider.tts.Speaker(voice, VOICE_FALLBACK, on_change=lambda: loop.call_soon_threadsafe(state.bump),
                                   on_switched=lambda name: loop.call_soon_threadsafe(state.remember_voice, name))
    print("spoken alerts: " + ("Piper found, preparing a voice" if state.speaker.available else
                               "Piper not installed, the page uses browser speech (see outrider/tts.py)"))
    state.speaker.start()
    state.game_pc, why = resolve_game_pc(st["game_pc"])
    if not state.game_pc:   # a server away from the game PC: no keys, devices, clipboard or sound on it
        st = dict(simulate_settings(st), server_player="off")
        print(f"server mode ({why}): auto honk, auto-target, the tablet's rail, the co-pilot button, the clipboard and "
              "playing on this PC are off")
    state.player = outrider.tts.LinePlayer(st["server_player"])
    state.sounds.own_dir = st["sound_dir"] or None
    print("playing on this PC (the page's tick): " + (state.player.name or (
        "off ([speech] server_player)" if state.player.choice == "off" else
        f"{st['server_player']} not found" if state.player.choice != "auto" else
        "no player found (pw-play, paplay, aplay or ffplay)")))
    state.simulate = bool(getattr(args, "simulate", False))
    if state.simulate:
        st = simulate_settings(st)
        print("simulate: the panels show the last known values as if the game were running; auto honk, auto-target, "
              "the co-pilot button and the clipboard are off")
    state.autohonk = dict(st["autohonk"])
    saved = meta_get(db, "autohonk_enabled")   # the page's toggle beats the config file once used
    if saved is not None:
        state.autohonk["enabled"] = bool(saved)
    if not state.game_pc:
        state.autohonk["enabled"] = False
    state.honker = outrider.honk.Honker(state.autohonk["key"], state.autohonk["hold"], LIVE_DIRS)
    if state.simulate or not state.game_pc:
        simulate_keyboard_off(state.honker, "--simulate" if state.simulate else "server mode")
    if state.autohonk["enabled"]:
        state.honker.open()
    print("auto honk: " + (state.honker.status if state.autohonk["enabled"] else "off")
          + (" (the D-Scanner must be on primary fire)" if state.honker.ready else ""))
    button_task = None
    if st["copilot"]["enabled"]:   # read-only: never grabs the device, never presses anything
        cp = st["copilot"]
        state.button = outrider.button.ButtonWatch(cp["device"], cp["button"], lambda g: state.copilot_gesture(g),
                                             cp["hold_ms"], cp["double_ms"], on_press=lambda: state.copilot_press())
        button_task = asyncio.create_task(state.button.run())
    print("co-pilot button: " + (f"{st['copilot']['button'] or '?'} on {st['copilot']['device'] or '?'}"
                                 if st["copilot"]["enabled"] else "off ([copilot] enabled)"))
    state.highway_cfg = dict(st["highway"])
    state.upload_cfg = json.loads(json.dumps(st["uploads"]))   # [eddn]/[edsm] enabled, as Settings -> Uploads wrote them
    state.edsm_dry_path = os.path.join(outrider.DATA_DIR, "edsm-dryrun.jsonl")   # OUTRIDER_EDSM_DRYRUN's log
    saved = meta_get(db, "autotarget")   # the Highway tab's toggle and delay beat the config file once used
    if isinstance(saved, dict):
        if isinstance(saved.get("enabled"), bool):
            state.highway_cfg["autotarget"] = saved["enabled"]
        if isinstance(saved.get("delay"), (int, float)) and not isinstance(saved.get("delay"), bool):
            state.highway_cfg["autotarget_delay"] = min(60.0, max(0.0, float(saved["delay"])))
    state.clipboard = Clipboard(st["highway"]["clipboard"])
    state.targeter = outrider.target.Targeter(state.honker, LIVE_DIRS, state.autotarget_cfg(),
                                              copy=lambda text: state.clipboard.copy(text, force=True))
    if not state.game_pc:
        state.highway_cfg["autotarget"] = False
    if state.highway_cfg["autotarget"] and state.honker.available and not state.highway_cfg["autotarget_dry_run"]:
        state.honker.open("target")
    print("highway clipboard: " + (f"{state.clipboard.tool} (the next system is copied on arriving at a route system)"
                                   if state.clipboard.tool and state.clipboard.enabled else
                                   "off ([highway] clipboard)" if not state.clipboard.enabled else
                                   "neither wl-copy nor xclip found"))
    print("highway auto-target: " + ("off" if not state.highway_cfg["autotarget"] else state.autotarget_info()["status"]))
    bg = state.highway_background()
    if bg["name"]:
        print(f"highway map background: {st['highway']['background_image']}" +
              (f" cannot be shown: {bg['why']}" if bg["why"] else ""))
    state.speech =outrider.speech.SpeechLines(st["speech_file"])
    sp = state.speech.info()
    print(f"spoken alerts: wording from {sp['file']}" if sp["version"] else f"spoken alerts: {sp['error']}")
    for msg in sp["problems"]:
        print(f"  {sp['file']}: {msg}", file=sys.stderr)
    rules_task = asyncio.create_task(check_bio_rules(state)) if outrider.bio else None
    watcher = asyncio.create_task(state.watch())
    state.firsts_watch_on = st["watch_firsts"]
    firsts_task = asyncio.create_task(state.watch_firsts()) if st["watch_firsts"] else None
    update_task = asyncio.create_task(state.watch_updates()) if st["update_check"] else None
    images_task = asyncio.create_task(state.watch_codex_images())   # the checklists' picture links, once a day
    # uploads: their own session (never queued behind Spansh), named and versioned as EDDN asks of a sender
    state.upload_session = ClientSession(timeout=ClientTimeout(total=20),
                                         headers={"User-Agent": f"ED-Outrider/{outrider.__version__}"})
    state.start_uploads()
    print("update check: " + ("on (GitHub's latest release, once a day)" if st["update_check"] else "off ([server] update_check)"))
    print("firsts watch: " + ("on (your unsold firsts on Spansh: one request every 10-30 s, each system once a day)"
                              if st["watch_firsts"] else "off ([spansh] watch_firsts)"))
    print(state.uploads_line())

    hosts = allowed_hosts(args.host, args.port, st["allowed_hosts"])
    runner = web.AppRunner(make_app(state, hosts))
    await runner.setup()
    try:
        await web.TCPSite(runner, args.host, args.port).start()
    except OSError as e:   # taken in the moment since port_free() said it was free
        print(f"cannot listen on {args.host}:{args.port}: {e.strerror or e}", file=sys.stderr)
        await spansh.close()
        await state.upload_session.close()
        raise SystemExit(1)
    # a wildcard address is not a place a browser can go (and not a name the Host check answers): loopback is
    shown = "127.0.0.1" if args.host in WILDCARD_HOSTS else _host_name(args.host)
    print(f"serving on http://{shown}:{args.port}/  (Ctrl-C to stop)")
    # the automatic backup that covers crashes (no Shutdown event, so no quit backup): at start, when due
    if backup_due(meta_get(db, "last_backup"), BACKUP_EVERY_DAYS):
        print(f"backup: the last one is older than {BACKUP_EVERY_DAYS:g} day{'' if BACKUP_EVERY_DAYS == 1 else 's'}, "
              f"backing up to {BACKUP_DIR}")
        state.start_backup(auto=True)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("note: the page is reachable from other machines on your network" + (
            " (they sign in with [server] password)" if state.password else " (no password set: see below)"))
        print("  it answers to any IP address, and by name only to these (add others to [server] allowed_hosts): "
              + ", ".join(sorted(h for h in hosts if h.endswith(f":{args.port}"))))
    for line in exposure_warnings(args.host, state.password, st["allowed_hosts"]):
        print(line, file=sys.stderr)
    # stop as on Ctrl-C when asked to (SIGTERM: docker stop, systemd, verify.sh): the same cleanup below, exit code 0
    stop = asyncio.Event()
    try:
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    except (NotImplementedError, RuntimeError, ValueError):   # Windows has no such handler: Ctrl-C only
        pass
    try:
        await stop.wait()
    finally:
        if state.targeter:
            state.targeter.cancel.set()   # a sequence pressing keys lets go and stops now
        if state._honk_cancel is not None:
            state._honk_cancel.set()      # an auto honk holding Primary Fire lets go now (it held on for up to 20 s)
        if state.honker:
            state.honker.shutdown()       # ...and a press still waiting for the keyboard is refused
        tasks = [t for t in (watcher, rules_task, button_task, firsts_task, update_task, images_task,   # the quit backup: finish_backup
                             *state.background_tasks()) if t]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        db.commit()      # first: an impatient second Ctrl-C must not lose what the page changed
        await finish_backup(state)
        state.bump()     # answer the pages' pending long polls now, or cleanup waits them out (up to 25 s)
        if state.player:
            await state.player.close()   # a line playing here ends now, and its request with it
        await runner.cleanup()
        await spansh.close()
        state.drop_leases()   # another Outrider may take the uploads over at once
        await state.upload_session.close()
        db.commit()
        db.close()
        print("stopped cleanly")


BACKUP_SHUTDOWN_WAIT = 300   # s a backup running at shutdown (the quit backup) gets to finish and be recorded
# (docker-compose.yml's stop_grace_period must be longer than this, or Docker kills the backup part way: review R14)


def sweep_backup_leftovers(folder, db_path=None):
    """At start (no backup runs yet): remove what a backup killed part way left behind (a .zip.part and its .db-*.sqlite
    copy), which rotation never touches (review R14). Only this database's (db_path): a backups folder shared with an
    instance run with another --db may hold its backup in progress right now (the sweep of 2026-10-09). Returns the
    names removed."""
    removed = []
    try:
        names = os.listdir(folder)
    except OSError:
        return removed
    stem = re.escape(os.path.splitext(os.path.basename(db_path or DB_PATH))[0])
    mine = re.compile(rf"^(outrider-{stem}-\d{{8}}-\d{{6}}Z\.zip\.part|\.db-outrider-{stem}-\d{{8}}-\d{{6}}Z.*\.sqlite)$")
    for name in names:
        if mine.match(name):
            try:
                os.remove(os.path.join(folder, name))
                removed.append(name)
            except OSError:
                pass
    if removed:
        print(f"backup: removed what an interrupted backup left: {', '.join(sorted(removed))}")
    return removed


async def finish_backup(state, wait=None):
    """At shutdown: a quit backup still in its SHUTDOWN_BACKUP_DELAY starts now (closing Outrider right after the
    game used to drop it: review F32); a running backup finishes and its result is recorded before the database
    closes. Left alone, its worker thread still writes the zip and rotates old ones, but last_backup is never updated
    (the next start then backs up again at once and rotates out one more good zip). Past the wait it says so and
    keeps waiting: the process waits for that thread to end whatever is done here, so giving up would only lose the
    result (review F35)."""
    w = state.backup_wait_task
    if w is not None and not w.done():
        w.cancel()
        await asyncio.gather(w, return_exceptions=True)
        state.start_backup(auto=True)
    t = state.backup_task
    if not t or t.done():
        return
    print("waiting for the backup to finish…")
    try:
        await asyncio.wait_for(asyncio.shield(t), BACKUP_SHUTDOWN_WAIT if wait is None else wait)
    except asyncio.TimeoutError:
        print("the backup is still running: waiting for it (the program cannot end before it does)", file=sys.stderr)
        await asyncio.gather(t, return_exceptions=True)


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--radius", type=float, help="Search radius in ly (default 25).")
    p.add_argument("--host", help="Address to serve on (default 127.0.0.1).")
    p.add_argument("--port", type=_cli_port, help="Port to serve on (default 8025).")
    p.add_argument("--db", help=f"SQLite database path, relative to the current folder (default {DB_PATH}).")
    p.add_argument("--config", default=CONFIG_PATH, metavar="PATH",
                   help=f"TOML config file (default {CONFIG_PATH}; see ed_outrider.toml.example).")
    p.add_argument("--write-config", action="store_true",
                   help="Write the effective settings to --config as a starting point (never overwrites) and exit.")
    p.add_argument("--journals", action="append", metavar="PATH",
                   help="Journal folder to tail (repeatable). Default: auto-detected.")
    p.add_argument("--legacy", action="append", metavar="PATH",
                   help="Folder of older journals to import once (repeatable). Default: auto-detected, unless "
                        "--journals, ED_JOURNALS or [journals] live names the live folders.")
    p.add_argument("--rescan", action="store_true",
                   help="Forget which journals were read and rebuild visits from scratch, "
                        "including the legacy directories. Spansh cache is kept.")
    p.add_argument("--restore", nargs="?", const="", metavar="ZIP",
                   help="Put the database (and browser_defaults.json) back from a backup zip, the newest in "
                        "backup_dir if none is given, and exit. Refuses while Outrider is running; the current "
                        "database is kept as <db>.pre-restore-<stamp>.")
    p.add_argument("--simulate", action="store_true",
                   help="For screenshots and demos: the panels show the last known values (fuel...) as if the game "
                        "were running. Auto honk, auto-target, the co-pilot button and the clipboard are off.")
    p.add_argument("--list-backups", action="store_true",
                   help="List this database's backup zips in backup_dir (name, size, time) and exit.")
    args = p.parse_args(argv)
    # the log's first line says which Outrider this is (the author, 2026-10-10): before the config is read, so before any
    # of its warnings; not for the commands that print something and exit
    if not (args.write_config or args.list_backups or args.restore is not None):
        print(f"ED Outrider {outrider.__version__}")
    detected = (outrider.unsold.LIVE_DIRS, outrider.unsold.LEGACY_DIRS) if outrider.unsold else ([], [])
    st = settings_from(load_config(args.config), args, os.environ.get("ED_JOURNALS"), detected)
    if args.write_config:
        if os.path.exists(args.config):
            print(f"{args.config} already exists; the effective settings are:\n")
            print(config_text(st))
        else:
            with open(args.config, "w", encoding="utf-8") as f:
                f.write(config_text(st))
            print(f"wrote {args.config}")
        return
    if args.list_backups:
        print("\n".join(list_backups(st["backup_dir"], st["db"])))
        return
    if args.restore is not None:
        zip_path = os.path.expanduser(args.restore)
        if not zip_path:
            try:
                zips = backup_zips(st["backup_dir"], st["db"])
            except OSError:
                zips = []
            if not zips:
                print(f"no backups of {os.path.basename(st['db'])} in {st['backup_dir']}", file=sys.stderr)
                raise SystemExit(1)
            zip_path = os.path.join(st["backup_dir"], zips[-1])
        elif not os.path.exists(zip_path) and os.path.exists(os.path.join(st["backup_dir"], zip_path)):
            zip_path = os.path.join(st["backup_dir"], zip_path)   # a bare name from --list-backups
        try:
            print("\n".join(restore_backup(zip_path, st["db"], st["host"], st["port"])))
        except (RuntimeError, OSError) as e:
            print(f"not restored: {e}", file=sys.stderr)
            raise SystemExit(1)
        return
    try:
        asyncio.run(run(args, st))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
