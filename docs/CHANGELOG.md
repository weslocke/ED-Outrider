# Changelog

Newest first, one entry per commit.

## 2026-10-19 · Limpets bought, sold and launched move the hold
- 200 limpets bought, yet the hold (Materials → Cargo) had none (the author): the game wrote a Cargo line with only
  the count and never rewrote Cargo.json, and limpet purchases were not read at all. `BuyDrones` now adds limpets,
  `SellDrones` and `LaunchDrone` take them away (`outrider.cargo.ship_apply`; `LaunchDrone` still counted in CMDR →
  Sessions too).

## 2026-10-19 · 🎯 on Search's results
- Search's results had no target button (the author): each now has 🎯 after its name, as Bookmarks and Nearby do,
  where auto-target can work and never on the system you are in (`sysAimBtn`).

## 2026-10-19 · The geology a body's signals could be, in its card and details
- The ✪ beside a body's name (geology its volcanism could show, new to your codex) said nothing in the body card,
  which read only "3 geological signals" (the author). The card now names the kinds its volcanism allows ("from its
  major rocky magma, one of: Sulphur Dioxide Fumarole · Silicate Magma Lava Spout ✪ · ..."), each new one marked ✪
  (anywhere) or ✦ (this region), and how one is logged; the details panel gets a 🪨 section saying the same
  (`geoCandidatesHtml`).

## 2026-10-19 · "Neutron jump target" only for the Highway
- 🎯 on a Nearby row said "Successfully targeted neutron jump target Smojoo DL-Y d8" (the author): every target but a
  boxel's took the Highway's wording. Now only the Highway's (Target next, the auto-target after a supercharge, 🎯 on a
  Highway row: the target's `neutron`); Nearby, bookmarks, your carrier, a survey or trade route and the auto-target test say "Targeted X.".

## 2026-10-19 · Lines for alerts Outrider does not know: one short line
- A lines file newer than the running Outrider (after an update, before a restart) listed every unknown alert with
  the names of all 150 known ones, once each (the author's Settings → Voice). Now one line: "3 lines are for alerts
  this Outrider does not know yet: old_data, limpets_low, hold_nearly_full. Restart Outrider after an update;
  otherwise check the names" (`outrider.speech.check`).

## 2026-10-19 · Pre-Odyssey: Spansh dates as YYYY-MM-DD
- Here's header, Now's line, the 🪦 and old data hovers and the briefing's card write the date Spansh last heard of
  the system as YYYY-MM-DD ("Spansh: pre-Odyssey, 2019-02-14"; the author: "Feb 2019" read like the cutoff). The
  voice still says "February 2019" (`spanshDay`, `spanshMonth`).

## 2026-10-19 · Pre-Odyssey Spansh data called out (Kurbo26, discussion #11)
- A system whose Spansh records all predate the legacy split (`LEGACY_CUTOFF`, 29 Nov 2022: thin-atmosphere worlds
  marked not landable, life never reported) is "pre-Odyssey" (`spansh_date`, `spansh_old`; in the Spansh summaries,
  CACHE_VERSION 18, and in `system_detail`, `merged_records`, `arrival_facts`), whatever its bodies (the old data tag
  needed a thin-atmosphere world the rules allow life on).
- **Nearby:** "🪦 pre-Odyssey" in the Status column beside "fully scanned", in the warning colour (🪦 when narrow;
  `spanshOldBadge`; first in Notable, too quiet there: the author missed it in the mockup). Its hover: when, and the
  thin-atmosphere worlds that may hold life by name (`stale_bio_summary`'s `names`), what the rules allow, about what
  one genus each pays. **Here:** the header says when Spansh last heard ("Spansh: pre-Odyssey, 2019-02-14", or the
  plain date). **The overlay's system strip:** "Spansh ✓ (pre-Odyssey)".
- **Never routine** (`isRoutine`) until your own scans have every body; **the arrival briefing** ends with the clause
  ("Spansh's data here is from February 2019, before Odyssey: worth a rescan." and the worlds that may hold life), a
  line of its own (`old_data`, 15 a list, under the briefing's row). **Now:** a 🪦 line until every body is yours, and
  "Next: rescan in the FSS" in place of "nothing worth staying for" (Spansh knowing every body left nothing "to find").
  The 🪦 line reads "Spansh data pre-Odyssey (2019-02-14): Rescan for Bio" (the author: one line in Now's type).

## 2026-10-19 · Hold full out in the black: the nearest buyer, never your own carrier
- After "Hold full", the best price within 100 ly found nothing 1,500 ly from the bubble and said nothing (the
  author). Now (`holdFullSell`): the best price within 100 ly (stations); with none, the nearest buyer within 500,
  2,500, then 10,000 ly (`HOLD_SELL_WIDER`, sort near, markets up to 90 days old), fleet carriers among them only if
  reported in the last 7 days (`CARRIER_FRESH_S`).
- Your own carrier (its callsign or name) is never a place to sell in either search (it pays nothing: Earnings
  leaves those sales out); within your laden jump range it is named as somewhere to unload ("Or your carrier, 12
  light-years").

## 2026-10-19 · Mining D: the mining line and its warnings
- **The mining line** (the author): `State.mining_live()` while you mine in a ring (an open stint, normal space,
  Status.json live, a mining ship): the ring and hotspot, the stint's t/h (from 5 minutes on), the hold (its lines,
  else the Cargo count; capacity from the Loadout), what it holds most, limpets, minutes to full, and `text`: in the
  payload (`mining_live`) for **Now**, and the overlay's **system strip**'s third line (`strip_panel`'s `mining`).
- **Spoken, once a stint** (`miningWarn`, this window's memory): `limpets_low` at Settings → Mining's number (5;
  2 to 50: "1 limpets" reads wrong), `hold_nearly_full` at 2 to 5 minutes, `hold_full` and then the best price within
  100 ly for the most you carry (`holdFullSell`, GET /api/cargo/lookup). Under the Limpets row, Mining's alerts table.
  15 lines a list, 969 in all.

## 2026-10-18 · Mining B and C: the hotspot record and the prospector call-out
- **The hotspot record** (B, the author): `mining_stints` (journal-derived, PARSER_VERSION 56): each drop into a ring
  (SupercruiseExit or a login with BodyType PlanetaryRing) until leaving it (MINING_CLOSE, a Location elsewhere), with
  every prospect's percentages raw, tons refined by mineral, motherlodes, cores cracked, limpets launched; a stint
  with no mining dropped; `Journals.handle_mining`, before the Commander view's early returns. The hotspot a live drop
  was aimed at: `mining_hotspot_drops` (Status.json's Destination, `RING_HOTSPOT`; live only, kept through a re-read):
  a mineral, "" for none, no row for unknown (older journals).
- `State.mining_hotspots()` (GET `/api/mining/hotspots`, and in `/api/commander/sessions`): stints by ring and
  hotspot, ships by t/h, per_ton (what your mined ore sold for, mining_sales, your own carrier left out), the
  minerals' names (`MINED_NAMES`). The page reads it again on the payload's `mining_version`.
- **The page:** CMDR → Sessions' **Hotspots** table (hit rate against the call-out, best ship's t/h, ≈ cr/h, refined,
  last; sorted by t/h, hit rate or last visit; 🎯); Here's ring hover and body card add "you, Alexandrite: 3 stints ·
  38 t/h · 41 % hits" under each ring (`ringRecord`; the body card now knows its system).
- **The prospector call-out** (C): a live ProspectedAsteroid is a "prospect" moment (materials by commodity id with
  names, untouched, content, motherlode). Settings → Mining: the minerals (the common ones, the rest under "more"),
  one threshold % (30), combined, motherlodes (on), High material content (off); `prospectHit`, `prospectOut`; a
  newer call-out replaces one waiting (tag "prospect"). Lines `prospect_hit`, `motherlode`, 15 a list, 652 in all.

## 2026-10-18 · Mining A: a reminder to take limpets; mining's alerts in Settings → Mining
- **Remind me to take limpets** (Settings → Mining, off by default; the author): undocking (a station or a carrier,
  not a taxi or multicrew) in a ship with a refinery or a collector, prospector, mining or universal limpet controller
  (`MINING_KIT`, its last Loadout) and no limpets in the hold (the Cargo snapshot known) is a "limpets" moment; the
  Mining Officer says it when the box is ticked. Live only. 15 lines a list (`limpets_none`).
- **Mining's alerts have their switches in Settings → Mining** (the author: until Alerts is cleaned up): Rings to mine
  and Limpets leave the Alerts table for a table of their own there (notify, sound, speak, crew), `MINING_ALERTS`.
- `Journals.ship_items()` (the ship's Loadout items) under `docking_computer()` and the new `mining_ship()`. The
  "mining" setting (`miningCfg`) joins SETTINGS_KEYS and BROWSER_SETTINGS.

## 2026-10-18 · Here's rings: the count once when every ring is mapped
- "2" over "2🗺/20" read as the rings listed twice (the author): with every ring mapped the cell is "2🗺/20" alone;
  partly mapped, the count over "1🗺/5"; none mapped, the count (`ringsCell`).

## 2026-10-18 · Here's rings: "1🗺/5" and each ring's hotspots under it, with the reserves
- **The Rings cell** (the author): the count, then "1🗺/5" once a ring is mapped (rings mapped, hotspots in them) in
  place of "1 mapped" and "N hotspots". Its hover lists each ring with its hotspots, and the body's reserves.
- **The body card** (hover a body): each ring on its line (type, width, density), its hotspots under it, the most
  first, "not mapped" or "mapped, no hotspots" otherwise; the reserves with the heading ("Rings · Pristine reserves").
  The details panel's ring table gets the same heading.
- **Reserves kept:** a body record's `reserve` from your Scan's ReserveLevel or Spansh's reserveLevel
  (`spansh_reserve`). PARSER_VERSION 55 (one journal re-read at the next start) and CACHE_VERSION 18 (Spansh records
  fetched again as you go). Hotspot size or position is in neither the journal nor Spansh: not shown.
- A test helper put its events at live_event's very edge (300 s): a slow run read them as old. Now 120 s.

## 2026-10-18 · Settings → Mining: each ring type's table of what lasers and cores give
- Hovering a ring type (or focusing it: a tap on a touch screen) shows a table of the commodities found in that ring
  type, ticked for laser (laser mining, abrasion blasting, sub-surface deposits) and core (the author): Painite and
  Platinum by laser only in metallic rings, cores only in metal-rich ones, and so on.
- The data: the Elite Dangerous Wiki's Miner page ("Resource availability"), retyped into `RING_MINERALS` (page.js),
  credited in the README. Four of its rows are a cell short (Liquid Oxygen, Methane Clathrate, Methanol Monohydrate,
  Tritium): read as icy laser mining, where the game has them.

## 2026-10-18 · Rings to mine: a new Mining section in Settings
- **Settings → Mining** (new, the author): tick the ring types you watch for (Icy, Rocky, Metallic, Metal Rich) and
  **pristine only**. A body you scan with one of them is said by the Mining Officer: "A 3 has a pristine metallic ring".
  - Said as the FSS resolves it, or with the arrival's own scan or a nav beacon.
  - Once per body each time you come to the system: the rescan after mapping it says nothing.
  - Bodies scanned together come in one line ("3 bodies with rings you're watching for: A 3, A 5 and B 1").
  - Off until a type is ticked. Its row in Alerts (Rings to mine) chooses the sound, notification and voice.
- **The lines:** `ring_found` and `ring_found_many` in every personality, 1,384 in all (52 a list for the built-in
  personalities' main line, 32 for the others), checked for both "a metallic ring" and "metallic and icy rings".
- **A capital where a ring starts a sentence:** "{ring} at A 3" shows as "A metallic ring at A 3" (page.js and
  outrider.speech: START_CAPS).
## 2026-10-18 · Version 2026.10.26, The Release with Personality
- The eight new personalities and over 70,000 lines, the crew as characters, space chatter, chat read aloud, surface
  pins, carrier trips, the terraformable worlds route, the fixes since 2026.10.25. What's new has its section. No
  journal re-read. The mining work (branch `mining`) waits for the next release.

## 2026-10-18 · Chat's header choices name no real commander
- Settings → Voice → Chat's "as" list showed a real commander's name as its example ("Kurbo: …"). It now shows
  `<CommanderName>: …` and `Commander <CommanderName> on <Channel>: …` (the author), and the guide likewise.

## 2026-10-18 · A species scanned twice is one bio line
- The game logs a CodexEntry for each composition scan of a species, not only the first one. Two scans of Tussock
  Cultro on one body (the author) showed it twice in the body's bio list: once with its value, once as a bare 📖
  line.
- A body's codex list now has one line per entry. It keeps the "new" flag and the voucher from whichever scan had
  them.

## 2026-10-18 · The Carrier tile's meeting line, short
- "you → it ≈ 1 jump (tank 22) · it → you ≈ 1 carrier jump · ≈ 21 t tritium" was too long for the tile (the author).
  It now reads "To it 1 jump · to you 1, ≈21 t", and "· 632 t short" when the depot cannot cover it.
- The tank's count, the fuel formula and how the hold covers a shortfall moved into the hovers. "To it" turns amber
  when your tank covers fewer jumps than you need.

## 2026-10-17 · The game closed means quiet; the Fable sweep's nine fixes
- **Chatter with the game closed** (the author): the game quit in supercruise wrote its Shutdown but no "empty"
  Status.json after it, so the last reading stayed live and chatter went on talking (and pin guidance would have
  too).
  - A Shutdown now makes the reading stale at once.
  - A Status.json from before the last Shutdown is never live, after a restart too (meta commander shutdown_ts).
  - Chatter's place is checked every tick, not only when Status.json changes.
- **The Fable sweep of everything since 4710250** (4 areas, each finding verified): 9 confirmed, all fixed.
  - **Pins:**
    - 📍 on a site in the legend works on a body with no pins yet (the payload names the body you are on, pins or
      not);
    - after arriving, the next pin's way is said once, not again a tick later;
    - Here's 📍 shows only for the system you are in;
    - a failed tick rolls the pins' spoken state back with its moments.
  - **Carrier trips:**
    - a finished trip says "complete" once, then is gone at the carrier's next move;
    - reaching the trip's own start (a typed From) or coming back to the current leg after a detour is not "off
      the trip": every leg is checked.
  - **Chat:**
    - a replayed chat line stays private: ▶ last said, a Now caption tapped (through the co-pilot's replay, which now
      carries `private`) and the co-pilot's "say again";
    - a tick that reads only a chat message wakes the page.
  - **Chatter:** the XO, which speaks as the one personality picked, is compared as that personality and its voice,
    so it never chatters with a station of the same personality.

## 2026-10-17 · Surface pins: body bookmarks with fly-to guidance (NEXT-VERSION #16)
- **Pins:** named points on a body (table `surface_pins`, live-only; GET/POST `/api/pins`).
  - **Added:** in a body panel's folded 📍 Pins section (typed or pasted coordinates in any common layout,
    `parsePinCoords`, shown as read before adding; also before you reach the body), with 📍 Pin here and 📋 copy by the
    legend title, or with 📍 on a site, mining location or the ship.
  - **One active:** the one tapped, else the first not reached, in order (▲ ▼).
- **Guided from orbital cruise down:**
  - the strip and Now, "📍 Wreck: 12.4 km, turn 30° right";
  - the map (on the rim when off it) and the legend's Pins (tap to go there);
  - the overlay's radar (a diamond and a line).
- **Said by the Navigator** (the new "pins" row, `State.pin_watch`): set, at 10 km, 1 km and 100 m, and arrived (50 m
  on foot or in the SRV, 250 m in the ship), then the next pin's way. The status report starts with it.
- **Found again:** 📍 on a body with pins in Here and Overview, and Bookmarks' Pins list.
- **The follow-up** (the author asked to remember it): Canonn's known sites per body, with "pin it".
- **Tests:** `tests/test_pins.py`, and the smoke test's "surface pins".

## 2026-10-17 · Carrier trips (NEXT-VERSION #19) and a tighter Carrier tile
- **Plot Route → Carrier:** your carrier's trip, from Spansh's carrier router (`SPANSH_FC`, POST /api/carrier/trip,
  probed 2026-10-17: names accepted; the cargo in use must include the hold's tritium).
  - The form: depot, hold, cargo in use and type, from the journal; To me; + via.
  - The plan: the legs with their tritium and what to do first (`outrider.cargo.carrier_route_legs` follows the real
    depot), the time, and the tritium needed against what you have.
  - Planning only, in its own slot (meta `carrier_trip`, kept through a re-read): it never replaces your ship's route.
- **Followed on the tile:** one line, "Leg 2/6 → system 📋 · departs / cooldown / ready / ready? ✕", from the
  carrier's position (`State.carrier_trip_follow`: the next leg, a later one skipped to, off the trip with re-plot from
  here, the end).
- **The Quartermaster:** "Carrier ready to jump. Next leg: …" once, and "should be" when away (the new "carriertrip"
  row). The arrival line adds "Leg 3 of 6, 3 to go", "Carrier trip complete." or "off the planned trip".
- **The Carrier tile tightened** (the author): the name; where it is; one movement line (a trip, else a booked jump,
  else the meeting line); "UC ✓ · Vista ✓ · Tritium: 668t/14,199t" (with ⚠ when the depot cannot pay for the next leg);
  "Balance … · ~N wks upkeep". At most five lines from eight. Other suspended services left off the tile.
- **Tests:** `tests/test_carrier_trip.py` (with the probed answer as a fixture) and the smoke test's "carrier trips";
  the tile's checks follow the new wording.

## 2026-10-17 · Chat read aloud by Comms (NEXT-VERSION #17)
- **Settings → Voice → Chat** (off by default): Read aloud, a tick per channel (Squadron, Wing and Direct ticked;
  Local and Voice chat not; NPCs never), and how a message starts ("Kurbo: …", "Commander Kurbo on Squadron: …", the
  message alone). Browser settings chatRead, chatChannels, chatHeader and chatMuted, shared like the others.
- **The server** keeps live ReceiveText, never an NPC's or your own, in memory only (`Journals.chat`, the payload's
  `chat`; `chat_sender` tidies "$cmdr_decorate" and "CMDR"), marking a mention of your commander name.
- **The page** reads it in Comms' voice (the new "chat" alert row; Comms' by default), last in the queue, never while
  hushed:
  - one sender's run of messages as one line;
  - one line per 15 s at most, a mention at once;
  - past 3 waiting, "And 3 more on Squadron";
  - over a minute old, shown in the captions only;
  - a link said "a link", emoji dropped;
  - 🔇 in Spoken lines mutes a commander (✕ on the Chat line to undo).
- **Private:** api/say and api/say/play take `private`. The voice neither caches nor prefetches the line, and a
  failure is logged without its words.
- **Tests:** `tests/test_chat.py`, and the smoke test's "chat read aloud" block.

## 2026-10-17 · A Terraformable worlds route (🪨, NEXT-VERSION #18)
- **What:** Plot Route has a seventh plotter, Terraformable, beside Earth-like and Ammonia. It is the Road to Riches
  router asked for rocky and high metal content worlds, kind `tf` in `outrider.riches.SURVEY_KINDS` and in page.js
  SURVEY.
- **The floor:** Spansh's own Rocky/HMC page sends min_value 1, which answers every plain rocky body (2 thousand
  mapped) and plain HMC (50 thousand) too. Probing showed Spansh tests min_value against the scan value, so a floor of
  100,000 keeps the terraformables alone (scans of 127 to 186 thousand, maps of 460 thousand or more). At 300,000 it
  answered nothing.
- **Tests:** the probed answer is a fixture (`tests/fixtures/spansh_body_types.json` "tf"), with a test for the plot's
  fields.
- **Also:** `scripts/route_probe.py` no longer probes when imported.

## 2026-10-17 · A Fable review of every spoken line: 464 lines replaced
- **What was read:** all 70,258 lines, both alerts and chatter, for all eleven personalities. The review ran as 43
  chunks, each read by a Fable reviewer against its personality's style sheet, then checked by a second Fable
  reader that kept only real problems with better replacements.
- **What came of it:** 551 lines flagged, 464 confirmed.
  - **226 wrong:** the line said something false for its alert. Examples: "critical" for a hull at just under half,
    "the codex will confirm" a green gas giant (it has no entry), "mapping complete" for an anomaly found by the FSS,
    "frame shift complete" inside the tunnel, "leaving the no fire zone" at undock.
  - **198 quality:** a placeholder that reads badly when filled ("Tank at about 6 jumps"), a bare count, an image
    that does not parse.
  - **37 tone:** two Southern Belle lines assumed the player's gender ("worth her salt").
  - **3 content:** a disability jibe, a crude sexual idiom, an unintended double meaning.
- **How they went in:** each replacement went in only where the line was unchanged, its placeholders were allowed and
  a clean list stayed clean. Every personality's own validator and the chatter validator still pass.

## 2026-10-17 · Space chatter: five chattiness steps with their timings, the section on one line
- **How often:** Rare, Occasional, Normal, Chatty, Non-stop (`outrider.chatter.LEVELS`: 15, 10, 7, 4, 2 minutes).
  Each option says its timing ("Chatty: every 4 to 8 min"); a test keeps the options in step with LEVELS and
  LEVEL_WORDS.
- **Tighter:** the switch, How often, Name the speaker in captions and ▶ Try chatter on one line, with the
  explanation as one short hint under them.

## 2026-10-17 · Space chatter's lines: all eleven personalities (11,443 lines)
- **What each personality has** (in `resources/speech.json` for Down to business, Sarcastic and Sweet, and in each
  file in `resources/personalities/`):
  - talking alone: about 60 lines in supercruise, 30 on a planet with the ship landed nearby, 30 with it in orbit
    (the author: double the first plan);
  - about 20 last words after an answer;
  - a dozen questions and a dozen answers for each of the 18 topics;
  - a swearing version of every list for the nine that swear.
- **How they were written:** a writer per personality and group, from each personality's style sheet, checked by a
  validator:
  - the placeholders each key fills, with no `{ship_dist}` in orbit, no `{name}` in crew-to-crew talk, and `{to}` in
    questions and answers;
  - the line counts, duplicates across keys, and anything Piper cannot say;
  - each personality's own rules (Vulcan's style, Klingon spellings, the southern pair's avoided words, the
    Scoundrel's limits, the swearing rates);
  - no swearing line a near-copy of a clean one: nine parts were sent back for fresh lines.
- **Switched on:** `outrider.chatter.LINES_WRITTEN` is True, so the shipped-lines tests require the lines. The crew
  lines test knows chatter's sizes. Each chatter key in `speech.json` has its "when".
- **The guide:** what chatter says, instead of "not yet".

## 2026-10-17 · The crew table: narrower Personality and Voice, a Chatter column
- **Narrower columns:** Personality and Voice are capped (15em and 17em) instead of stretching across the full-width
  Voice section.
- **A Chatter column:** each station's "takes part in space chatter" box is on its own crew line, dimmed while Space
  chatter is off.
- **A fix:** Space chatter's "Stations that take part" list is gone. It was drawn with the voice status, which could
  come before the crew's roles arrived, so it showed its heading with no boxes. The crew table redraws when the lines
  load.

## 2026-10-16 · Settings: Main voice and personality on one line, Voice beside the other wide sections
- **One line:** Main voice and Main personality share a line (wrapping on a narrow screen), the explanation under
  them.
- **The voice's status:** it shows only when it says something (loading, downloading, a failure), not "ready".
- **Voice moved down**, just above Server settings, so the full-width sections are together. The chips follow.
- **Uploads' note:** "(off by default)".

## 2026-10-16 · Settings → Voice: Main personality beside Main voice, profanity's "all but", the section full width
- **Main personality = XO:** a dropdown under Main voice picks one personality. Its last entry, **A mix…**, shows the
  boxes and One personality per system (moved up from further down).
  - A new shared setting, `speechMix`, is in both SETTINGS_KEYS and BROWSER_SETTINGS. Never set, it follows what is
    ticked: exactly one shows the dropdown, several show the mix, so no browser's setup changes.
- **An explanation under the two:** with the crew on, they are the XO's (answers, reports, the co-pilot, members "as
  the XO", the stand-in); with it off, they say every alert.
- **With profanity:** it names the personalities by their names, the short way round: "(all but Down to business,
  Vulcan)", or the ones that swear when they are fewer.
- **Voice spans the columns** on a big screen, as Server settings and Spoken lines do.

## 2026-10-16 · Space chatter: two stations that sound alike never talk, by what is heard
- **The comparison:** two stations are kept apart by the voice and person you really hear (`chatVoiceKey`), not by
  the settings as written. These now count as the same person:
  - the main voice named explicitly, and left as the main voice;
  - a person left unset on the main voice, and the main voice's own person picked;
  - a personality's voice that is not installed (heard in the main voice), and the main voice.
- **Unchanged:** one voice's two different people still talk to each other.
- **A limit:** on a voice other than the main one, an unset person is "the one picked for that voice", which the page
  does not know, so it counts as different from a number.

## 2026-10-16 · The terminal's lines: times first, subjects lined up, clearer start-up wording
- **The terminal** (`outrider.serverlog.Console`, on the Tees main() already installs):
  - each line starts with the time, and a date line comes first and again when the day changes;
  - a line's subject ("auto honk:") is padded so what follows lines up;
  - on a real terminal, a long line wraps under its text.
- **Left as before:** Show log and `outrider.log` keep each line as printed, with their own times. Under systemd
  (`JOURNAL_STREAM`), whose journal adds its own times, the times are left out.
- **The start-up lines reworded:**
  - the older journals on a line of their own ("imported once");
  - "open … to watch the start-up";
  - the systems visited with a thousands comma;
  - "played on this PC with pw-play" under spoken alerts;
  - the clipboard, auto-target and uploads lines in plainer words;
  - the network note as two "network:" lines;
  - the overlay window's own "overlay: " no longer doubled.
  - "serving on" is unchanged: the install guide points to it.

## 2026-10-16 · Sweep fixes: personalities shown complete, chatter's clocks and ▶, every tagged species on the map
- A Fable sweep of everything since 99759e4 (four areas, each finding verified; the overlay's came back clean).
- **Settings → Voice → Personalities:** every shipped personality showed "(60/100 alerts)". The 40 chatter keys
  counted, though no chatter lines are written yet. Coverage now counts them only once `LINES_WRITTEN` is True
  (`outrider.speech.spoken_keys`).
- **The voice lab:** it filled a chatter line with blanks ("Quiet in ."). It now uses chatter's own sample values
  (`lineSample`).
- **Chatter's place:** the server skipped its watcher on exactly the Status.json reads where the flags changed, such
  as leaving supercruise. It now watches every read.
- **Chatter's grace and {minutes}:** these compared the PC's clock with the browser's, so they were off on a tablet
  whose clock differs. The server now sends `since_ago` and the page puts it on its own clock.
- **How often:** changing it now applies at once, not after the next line.
- **▶ Try chatter:** it now plays like the other ▶ buttons, in any window and through a hush. Before, it was silent
  in a window that was not the speaking one.
- **The surface map and the overlay radar:** past 40 tagged plants on a body, a species beyond the nearest 40 lost its
  ring and legend row again. Each species' nearest usable tag is now always sent (`tags_shown`).

## 2026-10-16 · Space chatter on a planet: the temperature alone never stops it, a planetary port's concourse does
- The suit's very cold and very hot no longer keep chatter quiet: they are common on the worlds you sample, and once
  the temperature hurts, low health (still a blocker, with low oxygen) says so.
- On foot in a hangar or a social space now counts as docked for chatter, as it does for the rest of the server
  (`ON_FOOT_DOCKED`): a planetary port's concourse also sets on-foot-on-planet, so chatter could have started there,
  talking about the ship "up there".

## 2026-10-16 · Space chatter, the code (#15; the lines come later)
- **Settings → Voice → Space chatter** (off by default):
  - Talk in quiet moments, and how often (rare, normal, chatty).
  - With the crew on, the stations that take part.
  - Say who is talking in the captions (per browser).
  - ▶ Try chatter.
  - The server keeps the settings in meta `chatter` (POST `/api/voice/chatter`).
- **`outrider/chatter.py`:**
  - `where()`: supercruise in your ship, or on foot or in the SRV on a planet; quiet in danger, heat, low fuel, the
    FSD, suit trouble, or with a map, the FSS, the DSS or the codex open. Never for unsold data.
  - The timings and the topics: 12 station topics, 6 personal ones, who asks and who answers.
  - The speech keys: `chatter_space`, `chatter_planet_orbit` / `_landed`, `chatter_react`, and
    `chat_<topic>_ask` / `_answer`.
- **The server** follows Status.json for it: where you are, what keeps it quiet, since when.
- **The page** keeps two clocks in the speaking window:
  - no alert for N minutes, and N to 2N since the last chatter;
  - a minute's grace after entering supercruise or stepping out on a planet;
  - rare stops at 3 an hour.
- **What it says:**
  - A monologue, or with the crew on, a dialogue: an ask, an answer, sometimes a last word back.
  - Two stations of one personality or one voice never talk to each other.
  - It is last in the queue and never talks over anything; an alert drops the rest of a dialogue.
  - A line that is missing a value is never said.
- **No lines yet:** they are written per personality once the author has listened to the personalities.
  `LINES_WRITTEN` stays False until then, and the shipped-lines test does not ask for them.
- **Tests:** `tests/test_chatter.py` and the smoke test's "space chatter" block.
- **Docs:** the guide's Space chatter section and DESIGN_NOTES.

## 2026-10-16 · Two fixes from Kurbo26: a tagged plant walked away from, and the tablet's Map pill
- **The surface map:** a plant tagged with the composition scanner, of a species you had not sampled yet, vanished
  from the map (and its legend row) once you were over 3 km from it; it came back at the rim only after you sampled
  that species by hand. Each species' nearest usable tag now stays, at the rim when off the map (`surfaceLayout`; the
  overlay's radar always drew them).
- **The tablet's Map pill on Now:** it swapped the selected page's colours, and in the Elite and Sith themes that
  colour is see-through, so the text was faint on solid cyan (or steel). Those themes now set `--tb-maptag-bg` /
  `--tb-maptag-fg`, and so does Dark (blue on white was 3.2:1). A test checks the pill in every theme (solid
  colours, 4.5:1).
- Kurbo26 also confirmed the mouse-lock fix on Fedora with KDE on Wayland.

## 2026-10-16 · Version 2026.10.25, a bug fix release
- Released from d5c1f9d plus the install guide's Updating section (the personalities on main wait for the next release).
- Since 2026.10.24:
  - the overlay no longer breaks the game's mouse lock on Linux (a window per panel, none while nothing is drawn),
    with Foot boxes and "Hide the overlay on foot and in the DSS";
  - the landing pad's delay as a setting;
  - the carrier diagram's pads 7 and 8;
  - Nearby's middle fit step; Settings wider, in two columns;
  - the Fable sweep's fixes;
  - the install guide's Updating section;
  - screenshots back at 1600x1000.
- What's new has its section. No journal re-read.

## 2026-10-16 · A Scoundrel personality
- `resources/personalities/scoundrel.json` ("Scoundrel"): every alert, ~50 clean and ~50 swearing versions each (5,948
  lines), from the author's brief:
  - **The character:** an adventure-seeking loudmouth, a smuggler, small-time thief and grifter, never a killer,
    more interested in credits than anything. It shows little respect, treats you as its buddy, and is serious for
    a moment in danger (Sir), where the advice is to run.
  - **Stories:** petty-crime tall tales (Robigo, Sothis, black markets, the cops at Lave) and PG-13 innuendo (the
    Hutton twins). It never mentions its own anatomy or assumes yours, so any voice fits.
  - **Swearing:** none in the clean list; every word on about half the swearing list's lines.
  - **Address:** buddy, pal or friend.
- Han Solo's lines the author approved, each twice: "Never tell me the odds!", "I've got a bad feeling about this.",
  "It's not my fault!", "Don't get cocky.", "Laugh it up."

## 2026-10-16 · The install guide: updating a plain install
- docs/guide/install.md "Updating": what an update never touches (`data/`, which holds the EDSM and Inara keys, and
  `ed_outrider.toml`), and the steps for a `git clone` and for a downloaded ZIP (a new folder of the old name, `data` and
  the config copied over). Only Docker had update steps before (a player's question).

## 2026-10-16 · A Klingon personality
- `resources/personalities/klingon.json` ("Klingon"): every alert, ~50 clean and ~50 swearing versions each (5,977
  lines), after research into Klingon culture and the author's brief:
  - **The character:** loud, aggressive and exuberant, always saying what it thinks. A subordinate who acts as your
    partner, cares for honour over credits, and treats exploration as the hunt and the conquest. In danger it gives
    sound advice and hates running.
  - **Insults:** Klingon insults in English in both lists ("son of a targ", "Ferengi-hearted coward"); the swearing
    list adds human swear words on about a quarter of its lines. The two lists share no line.
  - **Klingon words:** a few, spelled for the voice (Kapla, batleth, Sto-vo-kor, gak, bloodwine, Kahless).
  - **Address and gender:** gender neutral; it calls you Captain, Sir, Commander or My Lord.
- Quotes the author approved, each twice: "Today is a good day to die.", "Revenge is a dish best served cold.", "Only
  a fool fights in a burning house."; "Kapla!" as a sign-off.

## 2026-10-16 · Two southern personalities: Good Ol' Boy and Southern Belle
- `resources/personalities/good_ol_boy.json` ("Good Ol' Boy", 5,998 lines) and `southern_belle.json` ("Southern
  Belle", 5,987 lines): every alert, ~50 clean and ~50 swearing versions each, from one brief:
  - **Positive southern:** slang, contractions and style (y'all, fixin' to, ain't, reckon, bless your heart). Never
    "redneck" or "hick", nothing racist, political or demeaning (the Confederacy, poverty, drinking and disability
    jokes are left out). The one exception, the author's pick: "happier than a tornado in a trailer park", twice
    each.
  - **Temper:** slow to anger and slow to joke, very playful, wordy; everyone is a friend.
  - **Stories and food:** Grandma and Grandpa, the old days, and tall tales in famous Elite places; food comparisons
    everywhere (biscuits and gravy, cornbread, grits, sweet tea).
  - **Address:** Sir, "y'all" and "hey you"; endearments by personality (buddy, partner, pal; sugar, darlin',
    honey). Rare in danger alerts, most in conversation.
  - **Swearing:** the clean list keeps to minced oaths (dang, dadgum, shoot, Lord have mercy); the swearing list
    swears on about a third of its lines, when riled or excited.

## 2026-10-16 · Ivanova (Station Cmdr), a personality
- `resources/personalities/ivanova.json` ("Ivanova (Station Cmdr)"): every alert, ~50 clean and ~50 swearing versions
  each (5,916 lines), after research into the Babylon 5 character and the author's brief:
  - **The character:** a temperamental subordinate of Russian ancestry, quick to anger and quick to joke,
    fatalistic. Bored by routine exploration, won over by big money and the rare, eager for action; in danger it
    grumbles and gives the right advice.
  - **Shared-history tall tales** set in famous places (the bars on Jameson Memorial, the Hutton Orbital run, the
    Fuel Rats), never your real log, plus a grandmother's sayings.
  - **Russian:** about one line in sixty has a Russian word.
  - **Swearing:** none in the clean list; the swearing list swears often, every word.
  - **Gender neutral.** It calls you Commander or Sir.
- Babylon 5 quotes the author approved, each at most twice (four for "Ivanova is God", alone and ending the
  mantra): "No boom today. Boom tomorrow. There's always a boom tomorrow.", the "Ivanova is always right" mantra,
  "I am death incarnate…", "I've always had a hard time getting up when it's dark outside.", "Boom. Boom, boom,
  boom…", "Let's try not to get killed."

## 2026-10-16 · A Vulcan personality
- `resources/personalities/vulcan.json` ("Vulcan"): every alert, ~50 versions each (3,003 lines), after research
  into Vulcan speech and the author's brief:
  - **The character:** a subordinate, haughty and proud, serving under a human. It never says so, but it is
    passive-aggressive in a completely emotionless way. It never lies and is never excited, though it can be
    insistent.
  - **Speech:** no contractions, no exclamation marks, no swearing (so no swearing list).
  - **Humour,** always unintentional: human idioms tried and taken literally, clinical understatement, ludicrous
    precision about people (never invented game facts).
  - **Words:** "Fascinating", "logical" and "illogical" are frequent.
  - **How it addresses you:** Captain or Sir.
- Quotes the author approved, each at most twice: "Live long and prosper.", "Peace and long life.", "Logic is the
  beginning of wisdom, not the end.", "Insufficient facts always invite danger.", "Change is the essential process
  of all existence.", "Nowhere am I so desperately needed as among a shipload of illogical humans."

## 2026-10-16 · Two naval personalities: US Navy and Royal Navy, by the book
- `resources/personalities/naval_us.json` ("US Navy: by the book") and `naval_rn.json` ("Royal Navy: by the book",
  British usage and spelling, for English voices): every alert, ~50 clean and ~50 swearing versions each (5,946 and
  6,001 lines), after research into US and Royal Navy usage and the author's brief:
  - **Alerts:** completely professional in both lists. No swearing in the danger alerts; a rare "damn" in the less
    urgent ones.
  - **Reports:** crisp, with light swearing.
  - **Conversation:** game start and exit, welcome back, the recap, streaks and the voice switched on are friendly
    and call you "Skipper", and are saltier; the f-word appears now and then (21 and 22 lines in all).
  - **How they address you:** Captain or Sir (`"names"`).
- Naval words: Bravo Zulu, plank owner, crossing the line, scuttlebutt, general quarters (US); show a leg, splice the
  mainbrace, a brew, action stations (RN). The style sheet is in the author's notes.

## 2026-10-16 · Personalities as drop-in files, and the speech lines compressed
- A personality can now be a file of its own (speech.json's format, one personality): `resources/personalities/` for
  Outrider's, `data/personalities/` (beside the bans) for your own; merged into the lines (`merge_personalities`),
  re-read when added, edited or removed, a broken file keeping its last good copy. Yours replaces a shipped one of the
  same name; the base three cannot be replaced. Settings → Voice shows an incomplete one's coverage ("1/60 alerts"),
  and an alert none of the ticked personalities has is said by business. Problems show where speech.json's do.
- A personality's own forms of address: `"names"` in its styles entry (`["Captain", "Sir"]`) say its {name}, in
  alerts and the voice lab; the "Call me" names otherwise.
- GET /api/speech gzipped (1.05 MB, about 230 KB gzipped).
- tests/fixtures/personalities/naval-sample.json: four alerts in a naval voice, for trying the format (copy it into
  data/personalities/ to hear it). The guide: "Your own personality". Plan: the naval, Vulcan, Ivanova (Station
  Cmdr), southern, space pirate and Klingon personalities follow, one at a time.

## 2026-10-16 · Screenshots back at 1600x1000, the Overview also on a 27-inch monitor
- Every full-page desktop shot in `docs/images/` retaken at 1600x1000: the README shows them 900 px wide, where a
  2560x1440 shot's text came out about 4.5 px (unreadable) and a 1600 one's about 7 px; most players' screens are
  closer to it too, and it shows Nearby's new middle fit step (Jumps and Known dropped, status and notable kept).
  Retaken: overview nearby here schematic map highway history samples log materials firsts search cargo trade cmdr
  earnings ship-card boxel boxel-grid nearest checklist (same pins and plots as before).
- `docs/images/overview-27in.png` (2560x1440): the same Overview on the author's 27-inch monitors, in a fold under the
  README's main shot ("On a 27-inch monitor").

## 2026-10-15 · Nearby keeps its status and notable columns until they really do not fit
- In a narrow pane (the Overview's half) Nearby went from its short forms straight to compact2, which drops Jumps and
  Known and puts the status pills and notable tags under the name and the bodies all at once, leaving much of the row
  empty (the author). A fourth fit level, `compact3` (`COMPACT_LEVELS`; `.c3hide` / `.sf3`): Nearby's compact2 now only
  drops Jumps and Known, and compact3 moves the pills and tags, for the whole table, never row by row. Other tables have
  no compact3 forms, so they look as before.

## 2026-10-15 · The landing pad's delay after a docking grant is a setting
- Kurbo26 (discussion #3): 5 s suits him, but with EDCopilot some stations' controllers needed up to 13 s. **Settings →
  Voice → Say your landing pad [5] s after docking is granted** (`[speech] pad_delay`, 0 to 20, `PAD_DELAY_MAX`):
  written to the config and applied to the next grant at once (`LIVE_CONFIG` → `Journals.pad_delay`), in the payload as
  `pad_delay`. With a docking computer fitted the wait stays AUTO_DOCK_WAIT_S (12 s) unless it takes over.

## 2026-10-15 · The fleet carrier diagram: pads 7 and 8 inside the bow
- Kurbo26 (discussion #3) saw pads 7 and 8's outer corners poke out of the carrier's outline: its bow ran from (0, -44)
  to (26, -30), crossing x = 12 at y = -37.5, above the pads' top at -38. One outline now, `pads.CARRIER_OUTLINE` (the
  bow at -46, the shoulders at -34), sent with the map and drawn by Now and the overlay alike; a test keeps every pad of
  every carrier layout inside it by a unit.

## 2026-10-15 · A flaky uploads test made steady
- tests/test_uploads.py made up system addresses with `hash(name) % 1000`, and Python seeds a str's hash per process: in
  about one run in a thousand two names shared an address (seed 1311: "Before" and "There"), so a jump's signals
  counted as the system you were in and went early, failing `test_signals_before_their_jump_go_with_the_live_jump`
  (it failed verify once, 2026-10-15). Now `addr(name)`: crc32, the same in every run (the file's 17 names all differ).

## 2026-10-15 · Overlay: a window per panel on Linux, Foot boxes, "Hide the overlay on foot and in the DSS", wider Settings
- On Linux every overlay panel has its own window, only as big as the panel (`window_plan`, `window_rect`), so panels at
  opposite edges no longer make one window over the middle of the game, where Elite locks the mouse (#1); no window with
  nothing to draw, on Windows too; the one window over the whole game only in Arrange mode (and on Windows).
- Settings → In-game overlay: a **Foot** box per panel under Hide in mode (`[overlay] hide_on_foot`, none by default:
  the author has no use for Now on foot, others may), and **Hide the overlay on foot and in the DSS** (`hide_mouse_lock`,
  off): "overlays can break mouse lock in these situations on some systems".
- Settings is 80 % of the screen's width on a big screen (it was at most 1560 px), in two columns of sections; three
  only from 3200 px wide (a 4K screen at 100 %; it was from 1900 px).

## 2026-10-15 · The overlay no longer breaks the game's mouse lock (DSS, on foot) on Linux (#1)
- The author's trials (GNOME on Wayland) found it: on Linux the overlay window is now only as big as its panels
  together (`window_rect`: their bounding box plus 6 px; drawn at the game window's layout through an offset, following
  a panel that grows, moves or appears after each paint), and off the screen when it has nothing to draw (the DSS, the
  FSS...); the whole game window only in Arrange mode. Windows unchanged. DESIGN_NOTES says what was tried and why.
- The trial switches (Settings → In-game overlay → Mouse-lock trials, POST /api/overlay {trial}) are gone again.

## 2026-10-15 · Mouse lock (#1): a "small" trial, the window only as big as its panels
- The author's first trial (in the DSS): only **hide_empty** keeps the lock; **fit** does not, although in the DSS it
  shaped the window to one corner pixel. So either XWayland counts a window's whole rectangle whatever its shape, or any
  mapped overlay window breaks the lock. A fourth trial, **small** (`small_rect`: the window's own rectangle only
  around its panels, painted at the game window's layout through an offset; 1x1 in the corner with none), tells the
  two apart, and is the candidate for on foot, where the radar keeps the window up.

## 2026-10-15 · The overlay and the game's mouse lock (#1): trials to find the fix in game
- The author's tests (GNOME on Wayland, Elite under Proton): with the overlay on, the mouse is not captured on foot or
  in the DSS (the camera turns until the cursor leaves the monitor onto the next one); off, it is. The overlay window
  covers the whole game window and stays mapped in the DSS with nothing drawn; its X input shape is empty (clicks
  pass), so the likely cause is Wayland's pointer lock, given only over the focused game's own surface.
- **Settings → In-game overlay → Mouse-lock trials**, live only (POST /api/overlay {trial}, in GET /api/overlay; never
  written to the config, forgotten at a restart): **fit** shapes the window to its panels (`fit_rects`: each panel
  as drawn plus 6 px; the middle of the game is Elite's alone), **no_raise** raises it only as it shows,
  **hide_empty** takes it away while it has no panel (`empty_hidden`). The one that keeps the lock becomes the default
  and the switches go.

## 2026-10-15 · Sweep fixes: the CMDR tab's places after a re-read, Nearby's Focus/Lock, crew checks, two page fixes
A Fable sweep of everything since the last one (70156ee..c5ea3c2, 7 areas, each finding verified): 6 confirmed, 0
refuted; all fixed here, with the Nearest dialog's labels.
- **Commander folds** (a ship stored by ShipyardSwap/Buy/Transfer, a module fetched) took their place from the live dock
  state, which a journal re-read keeps: a re-read run while docked (the v54 one) stamped them with that station.
  They now use the dock state replayed in order (meta sale_dock, which also keeps the Docked line's system) and the
  position; the next StoredShips/StoredModules list corrected them anyway, so no re-read for it.
- **Nearby's Focus/Lock** on a carrier or target Outrider could not place yet kept saying "doesn't know where" after it
  learnt the place under the same id64 (a carrier that jumped without you): the failure is now worked out again after
  `NEAR_MISS_RETRY_S` (10 s).
- POST /api/voice/crew with a row that is not a string answers 400 (was a 500); /api/say notes a crew voice that is
  not installed in the log only for a well-formed voice name (any text a caller sent was kept and printed).
- CMDR → Engineering: a short material's link now filters a Materials tab drawn already (its grid kept every material);
  the held-only switch it clears is saved too.
- Overview in Boxel mode: Focus/Lock on the Overview's bar is hidden there as on Nearby (picking it moved Nearby's
  centre for every window, unseen).
- The Nearest dialog's Must have labels are spaced ("shipyardmaterial trader" ran together).

## 2026-10-15 · Screenshots at 2560x1440: every page view as on a 27-inch monitor
- Every full-page desktop shot in `docs/images/` retaken at 2560x1440 to match overview.png (Elite theme, the Highway's
  route line, a route to Colonia plotted): nearby, here, schematic, map, highway, history, samples, log, materials,
  firsts, search, cargo (Sell on the carrier's platinum), trade, cmdr, earnings, ship-card, boxel, boxel-grid, nearest
  and checklist. here.png and schematic.png now view Lysood TS-U d2-58 as the overview does (here.png with body 6 g's
  panel open); boxel-grid.png folds Boxels nearby so whole rows of the boxel table sit above the sector map.
- Not retaken: tablet.png (1920x1200, LCARS), themes.png (the 2x2 composite), overlay.png and the overlay-pad shots
  (Qt renders), and the crops (overlay-settings, nearest-dssa, surface, banner, datatile, uploads).

## 2026-10-15 · The overview shot at 2560x1440
- `docs/images/overview.png` retaken at 2560x1440 (the author's 27-inch monitors): at that width Nearby's rows keep their
  Status, Notable and Known columns on one line, as the page really looks on a big monitor; still pinned on Lysood
  TS-U d2-58.

## 2026-10-15 · The overview shot pinned on Lysood TS-U d2-58: a list with more in it
- `docs/images/overview.png` retaken as before (Overview, Elite theme, 1600x1000, Here in its list view beside Nearby,
  the route line shown) but viewing Lysood TS-U d2-58: three bio bodies with sampled species (a Stratum among them),
  ringed bodies and a 17.5M max, where the old shot's list had little in it.

## 2026-10-15 · The docking pad shot, cropped
- `docs/images/overlay-pad-crop.png` (760x465: the starport and carrier pad panels side by side) and
  `overlay-pad-starport.png` (the starport panel alone), cut from overlay-pad.png, for listings that crop or shrink.

## 2026-10-15 · Inara uploads: confirmed live
- The author's live trial on his test account works (2026-10-15): DESIGN_NOTES' "Inara uploads: not yet tried live"
  line goes.

## 2026-10-15 · The overlay on Windows: confirmed by players
- Kurbo26 and weidercs report the in-game overlay working over the game on Windows: overlay.md's Windows line and
  DESIGN_NOTES no longer call it untried ("keep showing when Elite is not the active window"'s Windows z-order walk
  stays marked not yet tried).

## 2026-10-15 · Checked in game: a carrier's pad
- The author landed at his carrier (2026-10-15): the pad's words and the carrier diagram (bow at the top) are right,
  as the starport's were. DESIGN_NOTES' "Not yet tried in a live game" line for the pad's place goes.

## 2026-10-15 · ⛽ keeps a 5 % reserve and says when it is learning; the pad said after the station's voice
- **The In-Game Route's ⛽** counts a hop only while it leaves `FUEL_REACH_RESERVE` (5 %) of the tank aboard: the
  author's Caspian "made" a 27-jump route with 0.1 t left (the fuel figures are a fit to his jumps, and a little cargo
  or a longer hop undoes 0.1 t); now "⛽ 25", 9.9 t left after it. `route_fuel_reach` gives `spare` and `reserve`, the
  hovers say them ("keeping 8.0 t in reserve", "with 31.4 t to spare"). While the fuel model is not complete it gives
  `{learning: n}` and the strip shows **⛽ ?** with how many more jumps (Kurbo26 saw no ⛽ at all in such a ship).
- **The pad is said 5 s after the grant** with no docking computer fitted (`GRANT_SAY_DELAY_S`, the author; Kurbo26: it
  talked over the station's own voice); with one fitted the 12 s hold stays (silent when it takes over); the chat
  test commands at once. Both through `docking_hold` / `State.docking_release`.
- Tests: the reach with the reserve, spare, learning; the delay, the test command at once; the strip's hovers and ⛽ ?.
  Guides: views.md, voice-and-alerts.md; What's new.

## 2026-10-15 · The pad's diagram sized to fit Now; the tablet to Now while docking
From Kurbo26's try of the build (discussion #3).
- Now's pad diagram is sized by its **height** (`min(32vh, 300px)`, width following): a carrier, drawn tall, ran off a
  1920x1200 tablet's Now when it was sized by width; PAD's number a little smaller (`clamp(40px, 7vw, 96px)`).
- **The tablet switches to Now when a pad is granted** and back to the page you were on once docked (the author: yes
  to Kurbo26's idea, and back after): `tabAutoView`, the surface map's switch, now also for `data.docking.pad`; a
  refusal does not switch, a page chosen meanwhile stays.
- Smoke: the diagram's height rule; the tablet's switch to Now and back on a grant, none on a refusal. Guide: tablet.md;
  What's new.

## 2026-10-15 · Version 2026.10.24
- The CMDR tab (weidercs's PR #5, reworked) with **Earnings** (exploration, exobiology and mining income by month and
  year, every sale's place and ship, species, stations, ships, mining from the mined stock, labelled estimates, CSV) and
  ship pictures on Inventory; **docking** (the pad said and shown, where it is and a diagram at starports and carriers,
  quiet on auto-dock, non-obvious refusals); **routes** (🛣 to the carrier, the In-Game Route's copying chips and ⛽
  reach, no line for one jump, the route line on every tab, 📋 paste); **Nearby's Focus/Lock** and filters (PR #8's
  ideas); the **overlay** for big screens (All Panels, down to 20 %, a 9 px text floor, text per panel), the strip's
  security and reputation; the game's own **icons**; certifi and plain certificate errors (issue #9); the header tile
  picker, upkeep weeks, the voice commands list, the launcher's header; docs (every route in the agent guide).
  What's new has its section; the first start re-reads the journals once (PARSER_VERSION 54), after a backup.

## 2026-10-15 · Docs: every route in the agent guide, checked by a test; the CMDR tab by its name
- NEXT-VERSION #11 (small docs debt). `docs/AGENT_GUIDE.md` now names every path `make_app` registers (107, the
  Commander loop's `/api/commander/<part>` as one): 23 were missing or written only as a relative shorthand
  ("`/api/highway` (+ `/systems`)"). Its "How data flows" step 6 has each with its body and the State method behind
  it: `/api/radius`, `/api/hush`, `/api/copilot`, `/api/nextstop`, `/api/bookmark`, `/api/backup`, `/api/defaults`
  (GET and POST), `/api/rigs/remove`, `/api/sites/forget`, `/api/speech/ban` and `/unban`, `/api/say/stop`,
  `/api/sound/play`, `/api/autohonk/forget`, `/api/rail`, `/api/rail/press`, `/api/rail/sets`, `/api/riches/clear`
  and the Highway's `systems`, `background`, `plot`, `clear` and `autotarget` written whole; then which routes are
  `pc_only`. The Commander parts are listed by name.
- `tests/test_docs.py` `RoutesInTheGuide` reads the registered paths from `make_app`'s source (every
  `add_get`/`add_post`/`add_route`/`add_static`; the Commander loop's f-string read explicitly, any other f-string or
  non-literal path refused) and fails naming each one the guide does not name whole (placeholders `{x}`/`<x>`
  normalised; a family only as `<prefix>/*`); `test_the_rule` pins the rule.
- "The Commander view" is "the CMDR tab" in the agent guide and the design notes, and the tab's sub-tab switch is
  labelled "CMDR tab" for screen readers, as the tab reads. Code names (`commander_view`, `cmdrTab`, meta keys) unchanged.

## 2026-10-15 · Game-style icons: the galaxy map's destination, carrier, Titan, waypoint, engineer and mission markers
- NEXT-VERSION #13 (the author's list): the page draws the game's own galaxy-map markers where it had emoji. Every
  target button (a route's rows and line, Nearby's rows, bookmarks, the next stop, the Carrier tile, Nearest, a
  checklist find, a boxel's, the Map's card, the tablet's row sheet, Plot Route's Target next) shows the **destination**
  marker instead of 🎯, its words ("target", "Target", "in 5 s") kept; an icon-only one is named by an `aria-label`
  ("target <system>"), where 🎯 alone was its name before. The **fleet carrier** marker before the Carrier tile's name,
  in the folded tiles' line, on Nearest's carrier rows and on History's carrier jumps; Now's pad line names a carrier
  after the fleet or **squadron carrier** marker by the pad layout's kind. A **Titan** among the signals worth a detour
  (Here's and Nearby's tag, Now's line) shows the Titan marker; the other signals keep 📍. The route lines' "Next:" (and
  "Start:") follow the **waypoint** marker; the kind glyphs (🛣 💰 🧬...) stay. The CMDR tab's Engineering and Missions
  switch labels carry the **engineer** and **mission** markers. ☆/★ stay; speech, notifications, toasts, the Log, CSV,
  titles and the overlay keep their emoji (the Map's canvas keeps its 🚢 too: it is drawn, not markup). The Settings
  alert row's words say "a target button", and the Map's touch hint "Target", without the emoji.
- How: `mk(symbol, {gap, label})` (page.js, `MARKERS`), an empty span page.css's `.mk` paints in `currentColor` through
  the marker file as a CSS mask (`mask-image: url(icons/elite/<symbol>.svg)` and `-webkit-`), so it takes the text's
  colour in every theme and the tablet's, and grows with the font; `aria-hidden` beside words, `role="img"` with a label
  alone (History's carrier jump). `carrierMk(layout)`, `poiGlyphs`, `poiLineHtml`.
- The markers: Elite Dangerous Almanac's `assets/galaxy-map/` (hand-drawn 64 x 64 vectors of the in-game markers),
  seven of them copied unchanged at the ship pictures' pinned commit `5da3bfc` into `static/icons/elite/`; Frontier's
  designs under its media usage rules with its notice, Almanac's MIT notice kept: `static/icons/elite/CREDITS.txt`, not
  under the GPL; a row in the README's credits. Not in `PAGE_FILES` (pictures, not page code).
- Tests: test_tablet's `test_galaxy_map_markers` (the seven files and `MARKERS` agree, each a small 64 x 64 SVG with
  currentColor and nothing fetched, a `.mk-<symbol>` rule each, page.html's labels and no 🎯 left there, the credits
  naming Almanac, Frontier, MIT and the commit, served as SVG). Smoke: `markText` reads a marker as `[symbol]`; the
  route line, Highway tab, target next, too heavy and batch 25 checks now expect the waypoint and destination markers
  where they had 🎯; new: the riches rows' and Nearby's buttons (the marker, no words, the aria-label), the tablet
  sheet's and the Map card's Target, the one-rule block (every kind of target button, Target next), the Carrier tile,
  tiles line and Nearest's carrier rows, Now's pad (fleet and squadron), History's carrier jump, the Titan's tag and
  Now line, the CMDR switch's labels. Docs: plot-route.md, views.md, tablet.md, AGENT_GUIDE (`static/icons/`).

## 2026-10-15 · The route line on every tab
- The "🛣 Next:" / survey route line under the tiles shows on every tab (History, Plot Route, Materials, CMDR...), as the
  target and arrival lines do: the header is the header (the author). It showed on Overview, Nearby and Here only
  (`renderHwyLine`). Smoke: the line on six other views. Guide: plot-route.md.

## 2026-10-15 · CMDR Inventory: a ship's picture on a 2 s hover (tap on the tablet)
- The CMDR tab's **Inventory**: a mouse resting 2 s on a ship's row shows a card with its type's three-quarter picture,
  its name and type, beside the row and inside the window (`#shipCard`, fixed: the page never scrolls); it goes when the
  pointer leaves the row, on Escape or on another sub-tab. On the tablet (no hover) a tap on the ship's name (dotted
  underline) opens or closes it and a tap anywhere else closes it. A finger's pointer never starts the hover. A type
  with no picture (a hull newer than `SHIP_NAMES`) shows nothing. Inventory only. `shipPicture`, `SHIP_CARD_MS`, `SC`,
  `shipCardShow`/`shipCardHide`; the row's `data-shipimg`, the name's `.cmshipname`; a fade-in, none with reduced motion.
- The pictures: `static/ships/<symbol>.webp`, one per `SHIP_NAMES` key (48, about 2.1 MB in all), rendered by
  `scripts/build_ship_images.py` from Elite Dangerous Almanac's `illustration.svg` (Almanac-Core at its pinned commit
  `5da3bfc`) with PyQt6 offscreen, 600 x 400, transparent, WebP: the SVGs themselves (up to 2 MB each) are never shipped,
  nor any of Almanac's data. Frontier's ship designs, used under Frontier's media usage rules with its notice;
  Almanac's MIT notice kept: `static/ships/CREDITS.txt`, not under the GPL; a row in the README's credits.
- Tests: test_tablet's `test_ship_pictures` (a picture for every `SHIP_NAMES` type and none other, WebP, each under
  100 kB and 4 MB in all, the credits naming Frontier, Almanac and the build's commit, served as image/webp); smoke
  "ship pictures" (nothing before 2 s, the card after, gone on leaving, nothing for a touch or an unknown hull, Escape
  and another sub-tab) and the tablet's `tabShip` (tap to open and close, a tap elsewhere). Docs: views.md (Inventory),
  AGENT_GUIDE.

## 2026-10-15 · Checked in game: the starport pad's place, the auto-dock silence, 📋 paste, Earnings
- DESIGN_NOTES' "Not yet tried in a live game": the author checked at a station that the pad's words and diagram are
  right and that the pad is said or kept quiet with the docking computer on or off; 📋 paste and the Earnings tab work
  on his setup. Still to see: a carrier's pad (its bow), a live mining run through Earnings.

## 2026-10-14 · 🛣 on the Carrier tile: a route to your carrier at once
- Beside the carrier's 🎯 (the author's ask): **🛣** plots an exact route to its system at once (POST
  `api/highway/plot`, Plot Route's saved exact options: injections, no neutron boosts, conservative range), without
  opening Plot Route; shown only from 250 ly away (`CARRIER_PLOT_MIN_LY`, the author), not aboard, in its system or
  for a decommissioned carrier. A Highway route you follow is replaced only after "replace your route to …?" →
  Replace (`CP.ask`; Keep leaves it). While it runs the tile says "⏳ plotting a route there…" (Plot Route's own poll,
  `loadHwy`/`hwyPoll`); a failed plot's reason is a toast. `carrierPlot`, `plotToCarrier`.
- Smoke: hidden under 250 ly, the exact plot sent, plotting shown, a failure said, the ask with Keep and Replace.
  Guide: cargo-and-trading.md.

## 2026-10-14 · The pad in the Surface radar's place; the launcher's version line once
- The overlay's pad (#3, #12: PAD 34, where it is, its diagram, or a refusal's words) takes the **Surface radar's**
  place, size and switch instead of the Target panel's (the author: the radar's place is free in space); at a
  planetary port the pad comes first until you touch down. `overlay.pad_panel(..., pid="radar")`, `State.overlay_panels`;
  the Target panel keeps to your target.
- Started by `launch_outrider.sh`, whose header names the version, Outrider's own "ED Outrider 2026.10.x" first line goes
  into the log only (Show log, outrider.log), not the terminal again (the author: the same line twice); started any
  other way it is printed as before. The header's rules run past the address's end.
- Tests: the radar's place showing the pad (its switch, not over the galaxy map, the Target panel without it), the
  version line under the launcher, the banner's width. Docs: overlay.md (Docking under the radar), voice-and-alerts,
  settings, the example config.

## 2026-10-14 · The system strip: security and your reputation
- The overlay's system strip shows, in a populated system, its security level and your reputation with its controlling
  faction on the top row's right, in the region's font (the author's ask; Hostile in red): `system_standing` keeps
  them with the position (`pos.standing` {security, faction, rep}) from FSDJump / Location / CarrierJump
  (`SystemSecurity_Localised`, else `SECURITY_WORDS`; the `SystemFaction`'s `MyReputation` in `Factions`);
  `overlay.rep_level` gives the game's words (Hostile to -90, Unfriendly -35, Neutral +4, Cordial +35, Friendly +90,
  Allied); nothing in an unpopulated system (Anarchy everywhere in the black). The window right-aligns a `runs` item
  (`align: "right"`). Shown from the next arrival (no re-read needed).
- Tests: the strip with and without it, Hostile's colour, the levels' edges, `system_standing` and the position.
  Guide: overlay.md.

## 2026-10-14 · The launcher's header at every start
- `launch_outrider.sh` opens every start, and Settings' Restart (which runs it again), with a blank line and a header:
  "ED Outrider v2026.10.23" and the GitHub address between two rules (the author's layout), the version read from
  `outrider/__init__.py`, so each run stands out in the terminal and a service's log. Test: `LauncherBanner` runs only
  its `banner()` function.

## 2026-10-14 · No In-Game Route line for a route of one jump
- The author: targeting a system next door showed "In-Game Route: 1 jump" (the game writes a one-jump route for it).
  `State.route_summary` gives no route when the plotted one has a single jump (NavRoute.json's Route lists where you
  were plus one), and `route_minimal` none for one jump left with no jump since the plot; a longer route keeps its line
  down to its last jump. The target line says the rest.
- Tests: test_navroute (a one-jump file, a two-jump one, flown to its last jump; the unwritten file's one jump left
  with and without a jump since the plot). Guide: views.md.

## 2026-10-14 · The carrier's mined stock capped at what it holds
- When mined ore comes back aboard from your carrier, the carrier's mined stock of it is first capped at what the
  carrier held then (`Journals.carrier_holding`: `outrider.cargo.carrier_fold` over its events, your Market.json reads
  and Recounts up to that moment). Other players' purchases from your carrier write nothing in your journal, so the
  stock ran high (the author's platinum: about 5,006 t counted, about 1,018 t on the carrier): bought tons taken back
  aboard could have counted as mined. Re-read on the author's journals: osmium's 176 t capped to the 34 t his market
  showed; the income figures unchanged (1.72B: no affected sale yet).
- Test: no market read (no cap), a read showing others bought most, one showing a little gone.

## 2026-10-14 · Mined ore stored on your carrier still counts; the Lynx and Kestrel's pads
- **Your carrier keeps a mined stock of its own** (meta `mined_carrier`, the author's call after the real-data check:
  about half his mined ore went through the carrier, so Earnings and Sessions showed 0.89B of about 1.72B): a transfer
  to the carrier moves the mined tons there, one back to the ship or SRV moves them back aboard (then sold: mining),
  mined ore sold to your own carrier joins it (still left out of the income), a death empties only the ship's, a new
  carrier (CarrierBuy) starts empty. Ore other players buy from your carrier is not in the journal. PARSER_VERSION 54
  (still unreleased: one re-read for players; the author's database re-reads again if it ran 53).
- `outrider/cargo.SHIP_PAD`: the Lynx Highliner `mediumtransport01` medium (the author checked), the Kestrel Mk II
  `smallcombat01_nx` small (Frontier's ship page): the nearest-place-to-dock filter knows their pads.
- Tests: stored and sold later, part kept on the carrier through a death and a new carrier, sold to your carrier then
  taken back and sold elsewhere, the re-read clearing the carrier's stock, the two pads. Docs: views.md, DESIGN_NOTES,
  JOURNAL_REFERENCE.

## 2026-10-14 · Earnings: the guide, design notes, and fixes from a check on real data
NEXT-VERSION #7, batch D. A copy of the author's database, rebuilt from his journals (read only), through the summary:
the cartography and exobiology totals equal History's Ledger (its trips' paid figures summed) and the raw sales, mining
equals the Sessions' Sold, the species add up to exobiology, the months, years, ships and sales to the total. Fixes:
- **The crew's share**: a hired NPC crew member takes a share of each cartographic sale (`TotalEarnings` 91 % of
  `BaseValue` + `Bonus` in those journals until the crew was fired), so Cartography's base and bonus did not add up to
  its total. `totals` carries each data kind's `crew` (`crew_share`); the figure says "− … crew", a note says why.
- **A mining sale's station type** came only from data sales at that market: a station where you only sold ore had
  none (8 of 10 in that database). `mining_sales.station_type`, from `sale_place`. PARSER_VERSION stays 53 (unreleased:
  the release's one re-read fills it; until then the data sales' type, as before).
- **The CSV's ships**: a ship whose name was cleared (the game keeps " ") was written "  (corsair)": now its type; a
  ship gone from the stored ships' list takes its type's name from another ship of that type.
- **The Lynx Highliner** read "MediumTransport01" in the ship lists (the author, in game): page.js' `SHIP_NAMES` gains
  `mediumtransport01`.
- Docs: the guide's CMDR section (Earnings; Sessions' Sold in its new meaning), the README's CMDR line, DESIGN_NOTES
  (Earnings' scope, exact figures and labelled estimates, UTC months, the Ledger's ownership; the mined-stock rule and
  its gaps; not yet tried live), JOURNAL_REFERENCE (`TotalEarnings` and the crew), AGENT_GUIDE (and its scratch server:
  never a real journal folder as `live`, since every server writes its uploads lease there).
- Tests: test_earnings' `FromRealData` (each fix; `crew` 0 without crew); the smoke block "earnings" (the year's
  Cartography figure with a crew's share); test_pages' `ShipNames` (the newer ships' symbols named, the Lynx's too).

## 2026-10-14 · Earnings tab: figures, period picker, monthly chart, sales, stations, species, ships, mining, estimates, CSV
NEXT-VERSION #7, batch C: the page for batch B's answer. The CMDR tab's 6th sub-tab, **Earnings**, desktop and tablet.
- **Figures**: total earned (and the sales), cartography and exobiology (each base + bonus), mining (tons mined), and
  "Lost (estimate)": the data you died with, as History's Ledger values it, with the deaths. Exact figures are the
  game's; the credits as the page writes them elsewhere (`credits()`), the exact sum in each one's title.
- **Period** (above the pane): All time, a year with a sale, a month of that year; kept per device (store
  `cmEarnPeriod`, in neither settings list, as `cmdrTab`). A change asks again (`?year=`, `&month=`); an older
  period's answer arriving late is dropped (`newRequest`). Asked again too when the payload's `history_version` moves.
- **Monthly chart** (inline SVG, no library): every month of all time, cartography / exobiology / mining stacked to one
  scale, 3 or 4 axis steps reaching the highest month, the month labels thinned to the box's width (calendar-aligned:
  every 2nd, 3rd... month, then years), the period's months highlighted and the rest dimmed, a title per bar with its
  three figures; a bar picks its month. Sized to its box (bars in % of the width, a fixed height). Its colours are new
  tokens `--earn-carto`/`--earn-bio`/`--earn-mine` (page.css: info, good, accent); Babylon 5, Centauri, Dark, Elite,
  Minbari, Narn, Sith and Vorlon set their own where their info, accent and warn are one colour or too alike.
- **Tables** (fitted: `FIT_TABLES`, compact short forms): Sales (when, kind, where, ship, what, base, bonus, total; "N
  more not shown"), Where you sold, Species (exact), Ships (jumps, ly, bodies scanned, species sampled, earned, active
  days), Mining (per commodity refined by ship / SRV, mined tons sold, earned, cr/t; where sold; best sales; the sales
  to your own carrier left out, in a line), Most common (star classes, planet types, species found), Estimates (the
  systems sold by Outrider's value of your scans and the data lost to deaths, the word "estimate" on every value).
  Then the answer's notes and a line to History › Trips (the Ledger) for each trip's figures.
- **⬇ CSV** above the pane: `api/export?what=earnings`, a server link (the Android app saves it).
- **No sales at all**: said plainly, no chart, no figures.
- Tablet: the same sub-tab; the CMDR sub-tabs finger-sized and wrapping, the chart's text larger (`body.tablet` rules in
  tablet.css). The desktop's CMDR switch wraps on a narrow window instead of running off it.
- Tests: the smoke block "earnings" (the sub-tab, the figures, the picker's years and months and their queries, kept
  per device, an older answer overtaken, bars to scale and the empty month, the ticks, the labels, the highlight, a bar's
  click, each table, the short forms, the CSV link, the estimates labelled, History's Trips, the empty database, the axis
  and the labels' thinning); the tablet block (the sub-tab from Records, chart, tables, sub-tab size); `test_tablet`'s
  chart colours (told apart in every theme, 3:1 on the background and panels). Docs: AGENT_GUIDE.

## 2026-10-14 · Earnings summary: totals, months, sales, species, stations, ships, mining, estimates; CSV
NEXT-VERSION #7, batch B of the CMDR tab's Earnings: the answer the page will show (batch C), nothing on the page yet.
PARSER_VERSION 52 → 53 (both unreleased: one journal re-read either way).
- **`outrider/earnings.py`**: `period` (all time, a year or a month, UTC as the journal), `read` (the period's rows, SQL
  only) and the pure folds: `totals` (cartography and exobiology base, bonus, total; mining; sales), `month_series` (all
  time whatever the period, the empty months between included), `sales` (every sale, the newest first; a mining sale is
  its mined part), `species` (exact), `stations`, `per_ship` (its own jumps and ly, measured from the arrival before each;
  bodies first scanned, sample runs, sales, active days), `mining` (refined per commodity by ship and SRV, sold, cr/t,
  where, the best sales, and your own carrier's sales as the line left out), `common` (star classes, planet types,
  species), `estimates` (labelled: the systems sold by Outrider's value of your scans, `State.sold_system_values` with
  `outrider.unsold.body_value` as the Ledger's top finds; the data lost to deaths taken from the Ledger's losses, not
  counted again) and `notes`.
- **GET `/api/commander/earnings?year=&month=`** (`State.commander_earnings`, kept per period until the reader's data
  moves): year four digits, month 1 to 12 only with a year, else 400 `{error, code: bad_request}`. At most 500 sales
  listed, `more` says how many were left out. Not an AI tool yet.
- **`/api/export?what=earnings`**: every sale as CSV (when, kind, station, station type, ship, what, base, bonus,
  total), sales of mined ore to your own carrier left out.
- **Exact species pay**: `bio_sales`' bio_data kept only each species and whether it paid the bonus; it now keeps each
  entry's Value, Bonus and name (`sale_species`), so the species list is the game's figures, not an estimate. Its readers
  (`organic_replay`, `sale_check`) take the first two by position, so an older row still reads.
- Tests: `tests/test_earnings.py` (a year of made-up lines: the totals, a year and a month, the months with a gap, the
  years, the sales and the cap, species, stations, ships, mining with a partial sale and one to your own carrier, the
  most common, the estimates labelled with the Ledger's loss, the cache, an older bio sale, the route's good and bad
  queries, the CSV); `test_spansh`'s bio_data check. Docs: AGENT_GUIDE.

## 2026-10-14 · Earnings data: where and with which ship each sale, jump, scan and sample; mined stock
NEXT-VERSION #7 (javeliuswt, GitHub discussion #7), batch A of the CMDR tab's Earnings: the data, nothing shown yet.
PARSER_VERSION 51 → 52 (51 is unreleased: one journal re-read either way).
- **Where and with which ship**: `sale_events` keeps `station`, `market_id`, `station_type` (where you were docked) and
  `ship_id`; `jumps`, `own_bodies` (the first scan's ship: a rescan keeps it) and `own_organic` (the ship flown at the
  run's last sample: on foot or in the SRV, the one you came in) keep `ship_id`. The ship is the latest `Loadout`'s
  (`Journals.ship_at`); the place is meta `sale_dock` (`note_sale_dock`, `sale_place`), followed line by line and
  journal-derived, not meta `docked`, which a re-read keeps at its newest. A line read out of order (a legacy folder read
  late) gets NULL for both; old databases get the columns from `open_db`, NULL until the re-read. The sale_events,
  own_organic and own_bodies writes name their columns.
- **Mined stock** (meta `mined_stock` {commodity: t}, `Journals.note_mined`): every `MiningRefined` adds 1 t (the ship's
  refinery or the SRV's), a `CargoTransfer` to your carrier and an `EjectCargo` take theirs off (never below 0), a death
  empties it. A `MarketSell` counts as mining up to what it holds of that commodity: a new table **`mining_sales`** (ts,
  source, commodity, tons, mined_tons, price, total, mined_total = total × mined_tons / tons, station, market_id,
  ship_id, own_carrier: your own carrier's market, your own money), the rest of the sale is trade. Both journal-derived
  (RESET_JOURNAL_DATA); lines older than the stock are left out (`fresh`).
- **Sessions' Sold** (the CMDR tab) uses the same rule: the reader hands each sale's mining income to the fold
  (`commander.activity_apply(..., mined)`), so ore mined in one session and sold in the next counts in the one it was
  sold in (that login lists its mining with 0 t refined), bought tons sold with it no longer count, and sales to your own
  carrier do not. Before, a sale counted whole when its commodity was refined in the same login.
- Tests: `tests/test_earnings_data.py` (the place and ship of sales at a station, at your carrier after a docked login,
  by Apex shuttle and out of order; a jump's and a ride's, a rescan keeping the first ship, a sample run's; the fixtures
  read and read again; an old database's columns; the stock through refining by ship and SRV, a transfer, ejects, a
  death; a partial sale, two sessions, your own carrier, Sessions' Sold, an older line read late, a rolled-back tick,
  the re-read's clearing). Docs: JOURNAL_REFERENCE (MarketSell, MiningRefined, CargoTransfer, EjectCargo, the sales'
  place), AGENT_GUIDE.

## 2026-10-14 · Where your pad is: words, diagrams, quiet on auto-dock
NEXT-VERSION #12 (the author liked the mockup), on #3's pad number. After bgol's LandingPad plugin for EDMC (GPL-2+,
credited in `outrider/pads.py` and the README).
- **Words**: at a starport (Coriolis, Orbis, Ocellus, asteroid base, Dodec) "at the back · up on your right" (the
  author's wording, not a clock), at a carrier "port side, toward the bow" (a squadron carrier names the deck); shown
  under PAD on Now and the Target panel, and said after the personality's pad line as a plain sentence. The words assume
  the green lights on your right; the first docking of a session, then every 4th, says so ("With the green lights on
  your right, it's …"; meta `docking_said`, live-only).
- **Diagrams**: the starport seen from the slot looking in (12 sectors, 3 depths, the slot's red and green lights) or
  the carrier from above, bow up, your pad filled in: the overlay's Target panel (`overlay.pad_map_items`) and Now
  (`padMapSvg`). `[overlay] pad_diagram` (Settings → In-game overlay, on by default) turns them off; the words stay.
- **Quiet on auto-dock** (the author): with a docking computer fitted the grant's moment is held (`docking_hold`,
  checkpointed) and said by `State.docking_release` after 12 s (`AUTO_DOCK_WAIT_S`) unless the `Music` line
  "DockingComputer" came first (2-10 s after the grant in the author's journals); shown at once either way.
- **Test commands** (the plugin's): `!sppad 34`, `!fcpad 7`, `!scpad 23`, `!cspad 3` typed in game chat act as a grant
  at a test station of that layout, said at once; any other chat is never read.
- Tests: `tests/test_pads.py` (layouts, the 45-pad pattern, the words, carriers and squadron decks, the spoken
  sentence, the commands), test_docking (the place, the green-lights cadence, the commands, the diagram switch, the
  panel's drawing and the slot's lights, the docking computer's hold, a cancel, a rollback); the smoke block (the words
  and diagram on Now, a carrier's, number only at an outpost, the setting, the sentence said). Docs: overlay.md,
  voice-and-alerts.md, views.md, settings.md, the example config, JOURNAL_REFERENCE, AGENT_GUIDE, DESIGN_NOTES, README.

## 2026-10-14 · The overlay's docking refusal wraps instead of being cut
- `overlay.pad_panel`'s reason is flowed word by word: "no pad free for your ship: try ag…" was cut at the panel's edge
  (seen in an offscreen render). Test: every reason at every text size, no "…".

## 2026-10-14 · Docking: the pad number, big and spoken; why a station refused
NEXT-VERSION #3 (Kurbo26, GitHub discussion #3; an EDMC plugin's job). The pad number only, no map: the journal never
says which layout a station uses (the author: "just say pad number").
- **DockingGranted**: the pad, said every time by the Comms Officer ("Pad 34."; speech priority 1, as an answer to your
  own press: even while hushed), on Now in very large letters under the system (`.now-pad`, with the station), and in the
  overlay's **Target panel** (the author: the existing panel, not a new one): "PAD 34" in a new `huge` canvas size
  (`overlay.pad_panel`, FONT_PX 48) under the station's name, from the grant until you dock.
- **DockingDenied**: the reason in words when it is not obvious (`DENIED_WORDS`: NoSpace, TooLarge, RestrictedAccess,
  Hostile, Offences, ActiveFighter; never Distance), said, on Now and in the Target panel for a minute.
- `Journals.handle_docking` (live lines only; meta `docking`, live-only), cleared by Docked, DockingCancelled,
  DockingTimeout, SupercruiseEntry, FSDJump, LoadGame, Shutdown or Died (a moment "clear" redraws the page);
  `State.docking_summary` (the payload's `docking`; a grant 15 min at most, none while docked).
- A new alert row **Docking** (Comms; notify off by default; bound to the system), speech keys `docking_granted` and
  `docking_denied`, 15 lines in each list for the author's ears.
- Tests: `tests/test_docking.py` (granted and docked, a carrier's pad and every way it ends, the reasons said and not,
  how long it shows, a re-read says nothing, live-only, the panel, the Target panel while docking); the smoke block
  (PAD on Now, a refusal, the lines said, the row's tables); test_crew's short-list counts, test_state's kept keys.
  Docs: overlay.md, voice-and-alerts.md, views.md, JOURNAL_REFERENCE, AGENT_GUIDE.

## 2026-10-14 · 📋 on Search's Find a system by name
- The seventh name field (a `type="search"` box, missed by the first count): 📋 fills it, Find still looks it up. Smoke
  and plot-route.md follow.

## 2026-10-14 · 📋 paste: system name fields filled from the game PC's clipboard
NEXT-VERSION #5 (Kurbo26, GitHub discussion #3: a touchscreen browser window that never takes focus cannot be typed or
pasted into, and a browser reads its own clipboard only while focused).
- **📋** beside Plot Route's From, To and Station, and the "a system…" boxes of Nearby's Focus/Lock, Search's and the
  Nearest finder's Around. A tap fills the field as typing would (input, then change): Plot Route only fills (no plot by
  itself), the "a system…" boxes act on it as before.
- The server reads the game PC's clipboard: `Clipboard.paste` (wl-paste / xclip -o, `READ_TOOLS`; Windows'
  `winkeys.get_clipboard`), only one line of at most 100 characters with no link (`paste_name`). GET `/api/clipboard`
  {can, why}, POST `/api/clipboard/paste` {text} | {error, code}. For this PC's own browser and the Android app (its
  `OutriderApp/` User-Agent; the author's choice: a filter, not a lock), 403 `not_this_device` for other browsers; 409
  on a server, under --simulate, with no tool, an empty clipboard or not a name. Not an AI tool. verify.sh blanks
  `READ_TOOLS` too.
- Tests: `test_clipboard_paste` (each tool's command, the filter, empty, binary, a failure, Windows),
  `test_clipboard_paste_state`, `test_auth.Paste` (this PC, another browser, the app, a server); the smoke block (shown
  only when allowed, the six fields, To fills without plotting, Focus/Lock acts, a refusal said). Guide: plot-route.md.

## 2026-10-14 · In-Game Route: chips copy their name, ⛽ where the tank's fuel runs out
NEXT-VERSION #4 (Kurbo26, GitHub discussion #3; the Route Scoop idea, scaled down).
- A chip copies its system's name (the page-wide click-to-copy).
- **Fuel reach**: the payload's `route.fuel_reach` {hops, whole} (`State.route_fuel_reach`): the hops the fuel in the
  main tank makes without scooping, burned hop by hop as the ship lightens (`fsd.fuel_run`), a held charge on the first
  hop only; worked out with each payload, so a scoop on the way moves it. None (no mark) while the fuel model is
  incomplete, when the failing hop is out of the drive's reach at any fuel (a range matter), or past
  `FUEL_RUN_MAX_HOPS` hops all going. The page draws ⛽ with a bar before the first hop it does not make, ⛽✓ at the end
  when it makes them all, "⛽ N" after the chips when the reach is past the 24 shown.
- Tests: `test_route_fuel_reach` (a short tank, a scoop, none, the whole route, further along, a hop out of range, the
  look-ahead's cap); the smoke block (the copy, each mark's place). Guide: views.md.

## 2026-10-14 · Nearby's Around reads "Focus/Lock"
- The label beside the Standard / Boxel switch, and Boxel mode's hint ("Nearby's Focus/Lock (…) is for Standard"). Search's
  and the Nearest finder's Around keep their name. Smoke and views.md follow.

## 2026-10-14 · Nearby's bars: Around beside Standard / Boxel, the filters on the checkboxes' row, no ▾ This system
- **Around** sits beside the Standard / Boxel switch: on the Overview's bar, and on Nearby's own top bar (`#nearHead`)
  on the Nearby tab (`.nearhead` moves between them, `placeOverview`).
- One row of options under it: **Mass** first, then **visited**, **fully explored**, **1 jump** (were "show visited",
  "show fully explored", "one jump only"), **no scan data** (was "No scan data only") and **⧉ Copy visible**; the
  separate filters row (`#nearFilters`) is gone.
- The Overview's **▾ This system** fold is gone: the system pane always shows (`ovState.collapsed` dropped, a stored
  one deleted on load).
- Smoke: the bar's contents and the row's order, the fold's checks removed. Guide: views.md.

## 2026-10-14 · Overlay settings: "Text Size", a wider Scale box, the buttons on their own line
- The All Panels row reads "Text Size" instead of "Text Sz" (the Text column's hover and the overlay guide too).
- The Scale box is wide enough for "100" beside its spinner (5em, was 3.4em).
- Show test panels and Arrange panels sit on a line of their own under the row, at its left, instead of its far right.
- Smoke: the label, the buttons' line and the box's width.

## 2026-10-14 · Docs brought up to date
A sweep over the commits since 2026.10.23 for what fell between the batches.
- **For the curious**: the file table lists every module again (`tls.py`, `service.py`, `serverlog.py`,
  `notices.py`, `health.py`, `game_window.py`, `readclient.py`, `backfill.py`, `edsmlog.py`) and the scripts
  (`install.sh`, `build_blueprints.py`, `trader_probe.py`, `exact_probe.py`); the launchers' weekly certifi check; the
  CMDR tab by its label.
- **README**: the CMDR tab (with its EDSY / Coriolis builds), Nearby around another system, the list of voice commands.
- **Views and settings guides**: the In-Game Route's ✦ is not asked in the bubble or around Colonia; Settings → Display
  chooses the header tiles; "~96 wks upkeep"; `panel_scale` is multiplied with each panel's Size % (the example config
  too).
- **DESIGN_NOTES' "Not yet tried in a live game"**: the EDSY / Coriolis links, the hot ⚖ and the stored-module fold,
  Nearby's Around, the overlay's px figures, certifi on Windows, the route's hop lookups.

## 2026-10-14 · "All Panels: Theme · Text Sz · Scale"
- The overlay settings' top row reads "All Panels: Theme [ ] Text Sz [ ] Scale [100 %]" (the author's wording) instead
  of "Theme · Text size · All panels"; the hovers and the guide say the Scale is multiplied with each panel's own Size %
  (100 %: each panel at its own size; 50 % and 50 %: 25 %), not added. The panel table's "Hide when mode" heading reads
  "Hide in mode".

## 2026-10-14 · Overlay sizes: all panels at once, down to 20 %, a 9 px text floor, text size per panel
Answers a GitHub report: "the in-game overlay is too large on my 4K TV … below 50 % it resets to 50 %". Panels follow
the game window's height, so the same % is tiny at 1080p and big at 4K: the floor is now in readable pixels.
- **All panels** (`[overlay] panel_scale`, 100 %, 20 to 250): one size on top of each panel's own, in Settings → In-game
  overlay, and **Ctrl + wheel** over any panel in Arrange mode (the wheel alone and Shift + wheel keep the two
  opacities; the help and the window's hint say so).
- **A panel's Size % goes down to 20 %** (`LIMITS["scale"]` 0.2; the page's field too); the window never draws text
  under **9 px** (`overlay.MIN_TEXT_PX`): `overlay.effective_scale` raises a panel's scale to keep its smallest text
  there, in paint and in Arrange mode's resizing.
- **Settings says what you get**: the overlay window sends the game window's height with its requests (`&h=`); each
  Size % cell shows "≈ 11 px text", or "held at 9 px" with a line naming those panels ("your screen is too small to go
  lower"). No window drawing: no figure.
- **Text size, clearer and per panel**: the lone "text" dropdown is now **Text size**, and the panel table has a
  **Text** column (small, normal, large or as all panels), kept in the layout beside the size (an old layout reads
  unchanged); each panel is built at its own size.
- **One control row**: Theme, Text size and All panels, with Show test panels and Arrange panels at its far right
  (under it on a narrow window).
- Tests: `effective_scale` (1080p, 4K, each text size, the floor), `text_px`, `smallest_font` against `panel_font`,
  `panel_scale` (config, POST, the window's GET), LIMITS at 20 %, the layout's `text`, the per-panel size reaching the
  builders, the height kept from the window only, the Ctrl + wheel (`wheel_key`, `wheeled_all`), resizing with all
  panels and the floor, a 4K frame at 25 % drawing no text under 9 px (with PyQt6); the smoke block (the figures, the
  Text column, the one row, the posts). Docs: the overlay guide (Sizes and text), settings, the example config,
  AGENT_GUIDE, DESIGN_NOTES.

## 2026-10-14 · Nearby around another system ("Lock System") and Nearby's filters
The ideas of Rainmangames' pull request #8 ("Nearby exploration: area locking, filters, auto-refresh"; closed, not
merged), rebuilt on 2026.10.23's Around (S49). Thanks to Rainmangames, PR #8.
- **Around on Nearby's bar**: you (the default: Nearby follows your ship as before), your destination, your carrier, your
  next stop (followed: a new sphere when they change), lock this system (the sphere stays where you are now) or a
  system by name (GET `/api/find` first, as Search's). Saved on the server (POST `/api/nearby/around`, meta
  `near_around`, live-only: a restart and a journal re-read keep it), so every window, the Overview and the tablet agree.
  One that names nothing now (no target, no carrier) says why and leaves the list around you.
- **Away from you**: a strip above the list, "⌖ Around Smojooe GW-W c1-4 (locked) · 31.2 ly from you · 25 ly sphere ·
  ↻ refresh · ✕ back to you" (the name copies); Dist is from the centre, a **From you** column and **Jumps** from you
  (S49 kept "from you" apart); the Where tile says "known within 25 ly around …". The target line, the scoop hints and
  the auto-target test's nearest system stay from you; the horizon line and the AI's nearest unvisited say nothing then
  (their claim holds only around you), the AI's nearby systems measure from you and say where the list is.
- **Spansh is asked when the centre changes, and on ↻ refresh only** (POST `/api/nearby/refresh`: never while a search
  runs, no sooner than 2 minutes after the last ask): no timed refresh (the PR's every 10 minutes). A system you visit
  inside a pinned sphere joins the list at once as your own; your scans fill the rows as always.
- **Filters on Nearby's second row**, per device: Mass (all, a … h), No scan data only, ⧉ Copy visible (the names of the
  rows shown, one per line).
- **Spansh's cut sphere in plain words**: "Spansh returned its maximum: the list is complete only to N ly — a smaller
  radius shows them all", in the strip above the list (and the Where tile's "complete to N ly" hover).
- Boxel mode: Around is for Standard (the select goes; a hint says so while one is set). Not built: the PR's 75 and
  100 ly radii (until Spansh's maintainer agrees; `[server] radius_choices` can still offer them) and its timed refresh.
- Tests: `tests/test_nearby_around.py` (the saved choice and its checks, the centre per option, no Spansh ask without a
  change, ↻'s pace, Dist and From you, the routes, the AI's tools); smoke blocks (the strip, the columns, the filters,
  Copy visible, the posts, Boxel's hint; the tablet's strip and row sheet). Docs: the Views guide, DESIGN_NOTES,
  AGENT_GUIDE.

## 2026-10-14 · No route lookups in the bubble
- The game route's hops are no longer looked up on Spansh within 1,000 ly of Sol or 500 ly of Colonia (the author's
  ask): Spansh knows every system there and their records are heavy (Sol and Colonia alone ~190 KB), so a route
  through the bubble pulled megabytes for an answer already known. Out in the black, where an unreported system matters,
  nothing changes. Those hops' chips claim nothing, as for any hop not asked.

## 2026-10-14 · Route chips say "not reported to Spansh" only when Spansh was asked
Reported by Kurbo26 in GitHub discussion #3: Sol's chip on the In-Game Route line showed ✦ "not reported to Spansh".
A hop counted as known only if it was in the Nearby list or Outrider's Spansh cache, so every system Outrider had
never looked up (anything far away) was called unreported.
- **Three states** (`State.spansh_knows`): known (listed by the Nearby search, or Spansh's record cached), unreported
  (Spansh was asked and has no record: inside a Nearby search it answered, the route lookup below, the target's lookup)
  and not looked up (no ✦, nothing said about Spansh in the hover). An EDSM stand-in in the cache is not Spansh's.
- **The route's hops are looked up when a route is plotted**: the first 24 hops (the chips the line shows) that nothing
  has answered yet, in one Spansh search by id64 (`Spansh.records_by_id`, the same request the permit check makes;
  probed 2026-10-14, `tests/fixtures/spansh_ids.json`). One at a time, a failure retried after 5 minutes, each answer
  kept in memory for a day. So the ✦ now means what it says.
- **The same mistake elsewhere**: the arrival briefing said "Known, not in Spansh." for a system the Nearby list did not
  have yet (it read the cache), and the overlay's strip, the Nearby badges and statuses said Spansh lacked a system
  whenever its search had failed or a busy region's answer stopped short of it. These read the same three states: the
  briefing says "Known.", the strip says nothing, and a route-plot system Spansh's answer did not cover shows "not
  looked up" (never "unreported"; its "yours only" badge no longer says Spansh doesn't have it).
- **Launcher tests that passed by luck**: three launcher tests (`test_server_mode.py` FableScriptFixes'
  `test_no_sha256sum_needed` and `test_relative_arguments_are_the_callers`, and `test_restart.py`'s
  `test_shell_launcher_exports_itself`) wrote their fake venv Python with the real Python's path unquoted. This checkout's
  path has spaces, so every `-c` call failed, the requirements hash came out empty and each run went through a reinstall
  the tests say cannot happen, while their assertions still matched. The path is quoted (as CertifiWeekly's is), the
  fake answers `import aiohttp` itself, and each test now asserts no install ran. The launcher itself was fine.
- Tests: `tests/test_route_spansh.py` (the three states, the lookup's one search and pacing, the briefing and strip, the
  Nearby stand-ins after a failed or cut search); a page smoke block (chips and their titles, the briefing, the "not
  looked up" pill). Docs: DESIGN_NOTES, AGENT_GUIDE, the Views guide.

## 2026-10-14 · "wks upkeep"
- The Carrier tile (and the CMDR tab's carrier line) say "~96 wks upkeep" instead of "~96 weeks of upkeep (as of
  Oct 12)" (the author's ask): how old the carrier's stats are moved into the hover.

## 2026-10-14 · The launchers keep certifi current, checking once a week
Follow-up to issue #9 (the HTTPS fix): pip never upgrades an installed certifi that meets `requirements.txt`'s floor,
so the root certificates Outrider trusts would age with the environment (the author's decision, 2026-10-14).
- **`launch_outrider.sh` and `launch_outrider.bat`**, after the requirements step, run `pip install --upgrade --quiet
  certifi` when `.venv/.certifi-checked` (the date of the last check, compared in Python) is missing, 7 days old or
  more, or unreadable, then write today's date. Offline (or PyPI down) they say "certifi: could not check for a newer
  certificate bundle (offline?); using the installed one", write no stamp (the next start tries again) and start
  Outrider anyway; pip tries once with a short timeout. The .bat keeps its Windows line endings; its check sits at the
  top of `:run`, reached after an install and on the fast path.
- **Docker**: the image needs no weekly check (each release builds it), but Docker's layer cache kept the certifi of
  the first build. The Dockerfile now upgrades certifi in a step after `ARG CERTIFI_CHECKED`, and
  `scripts/docker_bundle.sh` passes the day's date, so a release's image always has the newest.
- Why weekly (DESIGN_NOTES): certifi holds root certificates, which change rarely; a site's own certificate (Let's
  Encrypt's 90-day ones) is checked live against those roots and needs no new bundle.
- Tests (`tests/test_server_mode.py` CertifiWeekly): the shell launcher in a scratch checkout with a fake venv Python
  (a missing stamp checks and stamps, a fresh one skips, an 8-day or future one checks, a failing pip says the line,
  keeps no stamp and still starts); the .bat's lines checked as text and its Python run against real stamps (the same
  lines as the shell's); the Dockerfile's ARG and the bundle's build argument. Docs: install guide, DESIGN_NOTES,
  AGENT_GUIDE.

## 2026-10-14 · CMDR tab: each ship's build in EDSY and Coriolis
The author's request of 2026-10-14.
- **EDSY ↗ and Coriolis ↗** beside each ship in the CMDR tab's Fleet (the ship you fly included) and Inventory's
  Ships: they open the ship designer in a new tab with that ship's exact build loaded (in the Android app, in the
  browser, as the page's other outside links). A ship not boarded since the journals begin says "no build", titled
  "board it once to record its build".
- **Each ship's latest Loadout kept whole**: `fleet_loadouts` has a `loadout` column (the line as JSON), filled by the
  same Loadout handling and guarded the same way (an older Loadout read later changes nothing); journal-derived, in
  `RESET_JOURNAL_DATA` with the rest of the row. PARSER_VERSION stays 51: it is unreleased, and the release's one
  re-read fills the column (its re-read reason now names the builds).
- **The links built on the server** (`outrider/shipyard_links.py`, pure), in the format EDMC uses: EDMC's own plugins
  (plugins/edsy.py, plugins/coriolis.py and common_coreutils.py's `shipyard_url_common`, EDMarketConnector, read on
  2026-10-14) were the reference, matched step by step, nothing copied. The Loadout reshaped as EDMC's
  `monitor.ship()` does, then compact sorted JSON, gzip, URL-safe base64 with '=' as `%3D`; the gzip header's time is
  0 and the build keeps the Loadout's own timestamp, so a build always gives the same link. EDSY's link keeps the
  build in the URL's fragment (never sent to a server), Coriolis's sends it as a query parameter (DESIGN_NOTES).
- Tests (`tests/test_shipyard_links.py`): a real Loadout from the author's journals, both links decoded (base64url,
  gunzip, JSON) back to it as EDMC shapes it, EDMC's reshaping (lasers' ammo, symbols, blank names, slot order), the
  fixed gzip header, the line kept whole and the older one ignored, a ship never boarded without links, an older
  database given the column; smoke: the links in the Fleet and Ships lists (new tab, escaped, "no build" titled).
  Docs: the views guide's CMDR section, DESIGN_NOTES, AGENT_GUIDE, for-developers.

## 2026-10-14 · HTTPS: the system's certificates plus certifi's, and a plain certificate error
Reported by Aerics84, issue #9: on Windows every lookup failed with `CERTIFICATE_VERIFY_FAILED … certificate has
expired` for spansh.co.uk. Python verifies against the Windows store, which fetches a new root only when something asks
it to (a browser does, Python does not).
- **certifi in `requirements.txt`** (`certifi>=2024.7.4`): the launchers install it on the next start (the file
  changed), the Docker image too.
- **One TLS context for every outgoing HTTPS connection** (`outrider/tls.py`): `ssl.create_default_context()` (the
  system store, so a corporate or self-added root keeps working) with certifi's bundle loaded into it; without certifi
  the system store alone, said once in the log. Cached. The lookups' session, the assistant's, the uploads', the MCP
  bridge's (`tls.connector()`), and the urllib downloads (the bio rules and colour tables, Piper's voice list and voices:
  `tls.urlopen`). A test walks the source so a new session or urlopen cannot leave it out.
- **A certificate failure said plainly**: `outrider.health.classify` has a "certificate" kind (aiohttp's
  ClientConnectorCertificateError, ssl's SSLCertVerificationError, urllib's URLError around one); the Data tile says
  "Spansh: couldn't verify spansh.co.uk's certificate (expired): check this PC's date and time; if they are right,
  update Outrider" (a wrong clock gives the same error), a banner card says it at once (one card for every source
  failing so) and so does Show log; Settings → Uploads' Recent lines and the upload outage card use the same words; a
  failed voice or bio download says it too.
- Tests (`tests/test_tls.py`): the context loads both sources (certifi faked, a test root in tests/fixtures), the
  fallback without certifi or with a broken bundle, classify and the words, the tile and the banner, the uploads'
  Recent entry, the source walk; smoke: the tile's and the Recent line's words. No network in any of them.
  Docs: install (Windows: certificate errors), the views guide's Data tile, DESIGN_NOTES, AGENT_GUIDE.

## 2026-10-14 · CMDR tab: sessions by days, hot ships, stored modules followed
Batch 4 of the PR #5 review's plan, with the author's answers of 2026-10-14.
- **Sessions by days**, like everything else: the Sessions tab lists the logins of the last 30 days with fighting or
  mining, 40 at most (`commander.SESSIONS_DAYS`, `sessions_since`), and says "your sessions of the last 30 days".
- **Hot ships**: a small red ⚖ (the theme's `--bad`, titled "hot: this ship is wanted") beside the ship you fly when the
  game marks it hot, and beside a stored ship or module the same way (it was the word "hot" in amber). The author's
  journals (read only) carry `Hot` on every StoredShips entry and never on a Loadout (none was hot), so a ship's flag is
  the latest line that says it: its StoredShips entry, and for the ship you fly the Loadout's `Hot` as Frontier's
  manual describes it ("if wanted at startup": the login's Loadout without it says not hot). The stored ships' fold
  keeps it per ship (`hot`), Loadout joined its events.
- **Stored modules followed between Outfitting lists**: ModuleStore, MassModuleStore, ModuleBuy's `StoredItem` (stored,
  not sold), ModuleRetrieve (its `SwapOutItem` stored), FetchRemoteModule (in transit until it arrives, then where you
  sent for it, kept through a list written meanwhile) and ModuleSellRemote are folded into meta stored_modules,
  `fresh()`-guarded, until the next StoredModules list replaces it (`commander.modules_apply`); the heading says as of
  the last change. Field names checked on the author's journals; replayed through the fold, they matched the game's next
  list 341 times in 345 (two modules the game threw away when swapped out, two lists after a gap in the journals).
  ModuleSellRemote and MassModuleStore had no real line: Frontier's manual. ModuleSell sells from the ship and leaves
  storage alone.
- No journal re-read: version 51 is unreleased and stays, though what it keeps changed shape (the ships' hot flags, the
  modules' fold); an Outrider already on 51 picks them up from the next shipyard or outfitting visit.
- Tests from real lines (`RealLines`: the hot flags, the modules between two lists, ModuleStore), the manual's events,
  the 30 days; smoke: the ⚖ in both tables, its title and colour, the stored modules' heading, the sessions' wording.
  Docs: the guide's CMDR section, DESIGN_NOTES, JOURNAL_REFERENCE, AGENT_GUIDE.

## 2026-10-14 · CMDR tab: checked against real journals, links out, blueprints by module, tiles to choose
Batch 3 of the PR #5 review's plan, with the author's answers of 2026-10-14.
- **The field names checked against real journals** (the author's live and legacy folders, read only): every event the
  tab folds that has lines there matched (StoredShips, ShipyardBuy/Swap/New/Transfer, SetUserShipName, StoredModules,
  ShipLocker and ShipLocker.json, SuitLoadout, CreateSuitLoadout, EngineerProgress both forms, Reputation, Powerplay,
  PowerplayMerits/Rank, SquadronStartup, JoinedSquadron, Missions, MissionAccepted/Completed/Abandoned/Redirected,
  CargoDepot, Bounty, FactionKillBond, Died, Interdicted, RedeemVoucher, MiningRefined, ProspectedAsteroid,
  AsteroidCracked, LaunchDrone, MarketSell); the events with no line there (DeleteSuitLoadout, RenameSuitLoadout,
  LoadoutEquip/RemoveModule, UpgradeSuit/Weapon, ShipyardSell, SellShipOnRebuy, PowerplayLeave/Defect, leaving a
  squadron) follow Frontier's manual. Three fixes, each with a test built from the real lines (`RealLines`): a
  colonisation mission's `Expires` is a Unix time, not seconds left (it showed 2080); a mission on the login's list
  only is named from its `Name_Localised` ("$Mission_Colonisation_Initial_Name;" before); `PowerplayRank` 0 comes just
  before `PowerplayJoin`, at the same second, and the join no longer wipes the rank. ShipLocker lines carry their lists
  at most changes, not only at login: the wording follows; ShipLocker.json is read in the tick only when its
  modification time moves (a test). No journal re-read: version 51 is not released and stays.
- **Links out of the tab, the tiles informational** (should 5): the career's History › opens History at its Career
  row; a material Engineering is short of opens the Materials tab filtered to it, its ⇄ the nearest trader of its kind
  (`openNearest({need})`; the blueprint rows carry each material's `category`). The Commander tile does not open it.
- **"CMDR"** is the tab's label: the header, its ↗ window and the tablet's nav (Records). The header row at 1280 px in
  the Default and all 11 themes (headless, a throwaway server): one row beside the title everywhere, 32-44 px
  narrower than with "Commander".
- **Blueprints by kind of module** (should 7): one row per kind and blueprint, each grade's engineers that kind's (a
  pulse laser's Overcharged is Broo Tarquin's, a cannon's Tod McQuinn's; a heat sink's Lightweight is no longer filed
  under the chaff launcher): 185 rows for 43 kinds. `scripts/build_blueprints.py` fetches coriolis-data itself at a
  pinned commit (0db9234, 2026-04-24), records it with the licence (Frontier's terms for the data; only coriolis.io's
  code is MIT) in the file's `_readme` and `source` and in the README's credits; FDevIDs (no licence) is dropped: the
  material names are matched by `outrider.materials`' own table (every material the same as before).
- **An unreadable blueprint table says so** (should 8): "Blueprint table unreadable", not "Nothing matches"
  (`engineering`'s `unreadable`; `load_blueprints` gives None).
- **The tablet**: `TABLET_VIEWS` in the nav's order, and a test that every nav page is in it and in exactly one
  `TB.groups` list (should 11); the Missions and Sessions tables are fitted tables (`FIT_TABLES`, drawn into
  `FIT_HOSTS`): short dates, spans and credits, then the faction, the lists by ship and of minerals and the limpets
  left out.
- **Choose the header tiles** (the author's request): Settings → Display → Header tiles shown on this device, a box
  per tile (Where I am, Commander, Fuel, Carrier, Unsold, Data). An unticked tile is left out on this device, from the
  one line too; the wide grid gets a column per tile shown; the last one cannot be unticked; per device (`tilesHidden`,
  not a shared setting); one line / six tiles work as before.
- Docs: DESIGN_NOTES, JOURNAL_REFERENCE (the traps above), AGENT_GUIDE, the guide's CMDR section and tablet page.
  Smoke: the links, the label, the unreadable table, the fitted tables' short forms, the tile choice.

## 2026-10-14 · Commander tab: read from the database
Batch 2 of the PR #5 review's plan: the Commander tab no longer scans journal files (each read whole, the live folder
only, a year at a time) but reads what the journal reader keeps, like every other view. A journal re-read (journal
reader version 51) fills it from all your journals, legacy folders included.
- **Folded as the lines are read**: `Journals.handle_commander` keeps meta reputation, powerplay, squadron,
  stored_ships, stored_modules, ship_locker, suit_loadouts, engineers and missions (`outrider/commander.py`'s
  `*_apply` folds, each `fresh()`-guarded: a legacy line older than the latest Missions list cannot bring a mission
  back), and a journal-derived `play_activity` table (one row per login: its fighting and mining). All of it is in
  `RESET_JOURNAL_DATA`; meta statistics keeps the career's sections; `fleet_loadouts` keeps each ship's value.
  `outrider/jscan.py` is gone; the GETs are `State.commander_*`, quick reads on the event loop, registered in `make_app`.
- **The login's snapshots are not play**: Missions, Reputation, EngineerProgress, Powerplay, SquadronStartup and
  ShipLocker joined `LOGIN_EVENTS`, so reading them does not move `last_play_ts` (History's session end, the "away"
  greeting).
- **The fleet follows the shipyard** (should 1): the last StoredShips, then ships bought, sold (also on a rebuy),
  swapped, sent for and renamed, as the Inara uploader reads them; the ship you fly is the newest Loadout, and each
  ship's value its latest Loadout's when that is newer than the list.
- **Suit loadouts** (should 2): created, changed (a weapon equipped or removed), upgraded, renamed and deleted, not
  only the ones worn.
- **The ship locker** (should 3): the login line, then ShipLocker.json whenever it is newer (read in the tick, as
  Cargo.json), since the later journal lines carry no contents.
- **Mining in the SRV** (should 4): the Rhino's refinery is counted apart from the ship's (its tons beside the
  ship's, not in t/h); the Sessions tab lists the latest 40 logins with fighting or mining, not the last 30 days.
- Tests (`tests/test_commander.py`, through `Journals.handle` on a scratch database): a legacy line older than the
  latest Missions line is ignored, a re-read doubles nothing, the login snapshots leave `last_play_ts`, a sold ship and
  a deleted suit loadout disappear, the SRV's mining apart, ShipLocker.json when newer; smoke: the SRV's tons.

## 2026-10-14 · Commander tab: the review's fixes
The fixes the review of PR #5 asked for before a release (batch 1 of its plan; the database move is next).
- **One owner for credits and the carrier.** The CMDR tab shows the Commander tile's credits (the login's plus sales
  since, with the tile's hover) and the Carrier tile's carrier (balance, weeks of upkeep, or its decommissioning in
  red) from the payload, live; `commander.profile` no longer reads its own credits, loan or CarrierStats.
- **Rank estimates.** Exobiology uses the post-Update-14 thresholds (Aunty Sledge's Frontier forum post of 2 Jan 2023,
  as the wiki copies it), worded "in about N cr", Elite IV and V marked uncertain. Checked on the author's journals
  since 2023 (each login's Progress beside its Statistics): Organic_Data_Profits moves through the Cataloguer,
  Taxonomist, Ecologist and Geneticist bands at the table's steps within 3 %, but not from its totals (Geneticist 64 %
  at 7.28B, where the totals give 74 %; the review's 64.1 % paired the 10-11 statistics with the 10-12 percentage), so
  it stays the step times the game's own percentage. The trade and exploration figures could not be checked (trade
  progress moved while Market_Profits did not; exploration has no published steps past Elite): those ranks, like
  combat, show their percentage only.
- **Engineering "ready"**: EngineerProgress' Rank is the highest grade the engineer crafts for you (the author's
  journals: 944 crafts, none above the rank then; a rank-up follows the roll that earns it), so ready is rank >=
  grade, not one past it.
- **The page's rules**: the tab switch (the themed `.seg`), Refresh and Engineering's filter sit above the pane; green
  and red are the theme's `--good` / `--bad` (`#cmdrView .ok` / `.short`, the Materials tab's classes; there was no
  `.ok` colour, and `--panel2` did not exist); a tab is asked for again only when the payload's new
  `commander_version` moves (a journal line naming an event the view reads: `COMMANDER_VIEW_EVENTS`, which also wakes
  the page) or, for Engineering, the materials' version, instead of a 30 s timer; the missions' time left is counted
  at each draw; the tab is kept with `store.set("cmdrTab")`; four unescaped values (Powerplay rank, G levels, a
  material's need, rates) go through `cmNum`.
- **Errors and threads**: no local "500 with the error" any more (it hid the traceback from Show log): `json_errors`
  logs and answers; the engineering worker gets a copy of the materials made on the event loop.
- **A 14th header tab** at 1280 and 1366 px in the Default and all 11 themes (measured headless on a throwaway server):
  nothing overflows, but at 1280 px Centauri's and Alliance's rows went below the title (+41 px of header); their pills
  are 12 px now (Centauri 8 px a side: its own padding never applied), and every row stays beside the title.
- Smoke: the Commander block waits with `settle()` under `holdPayloads()`, checks the controls are outside the pane,
  the colours resolve, no refetch on an unchanged payload, and reads the real `/api/commander/profile` once.

## 2026-10-14 · Commander: who you are, what you own, engineering, missions, sessions (weidercs, PR #5)
Contributed by weidercs (GitHub PR #5, written 2026-10-12), merged as is; the review's fixes follow in their own entry.
- A new **Commander** tab (Records on the tablet), five parts, each read from the journal files when opened
  (`outrider/commander.py`, `outrider/jscan.py`): nothing is stored, nothing is asked of anyone.
- **CMDR**: credits, net worth, the value of your fleet and stored modules and your carrier's balance, as of your last
  login; every rank with a bar to the next and, for trade, exploration and exobiology, about how many credits it still
  takes (the community's figures for each rank's step: an estimate, said as one); reputation, Powerplay, squadron;
  every ship; career figures from the game's Statistics.
- **Inventory**: your ships (where each is, its value, what bringing it here costs), stored modules with their
  engineering, the ship locker, the suit loadouts you have worn. Stored ships and modules are as of the last shipyard
  or outfitting you opened: the game writes those lists then.
- **Engineering**: 80 ship-module blueprints, grade by grade: what a roll takes against what you hold, how many rolls
  you could make now, the engineers offering the grade and whether yours are unlocked far enough. A filter (module,
  blueprint, material) and "only what I can craft now". `resources/blueprints.json`, built by
  `scripts/build_blueprints.py` from EDCD's coriolis-data and FDevIDs (materials by the journal's names). No
  experimental effects, suits or weapons.
- **Missions**: those you hold, the soonest to expire first: where, what (and how much is delivered), the reward, the
  time left, marked under half an hour. The login's Missions line decides what is still held.
- **Sessions**: combat and mining of the last 30 days, each from login to logout: kills, by ship, bounties, bonds,
  kills an hour, deaths; tons refined and of what, tons an hour, asteroids prospected and their content, limpets, and
  what the haul sold for.
- GET `/api/commander/profile`, `/inventory`, `/engineering`, `/missions`, `/sessions`. Not in the smoke test's
  every-page loops (one more page there shifts later batches' timing); its own batch runs last. `__version__` is
  left for the release.

## 2026-10-14 · No page-made saves in the Android app, the list of voice commands
The author's requests of 2026-10-14, relayed by the Android app's session.
- The app's WebView downloads same-origin http(s) links (every `api/export?what=…` link: kept) but cannot save a
  `blob:` or `data:` URL. The page has two such saves, both now through `saveBlob` (which refuses in the app):
  Settings → Sharing → **Export settings** and the voice lab's **⬇ Save WAV**. In the app both are hidden with a muted
  note in their place ("Export settings from a browser on the PC", "Save WAV from a browser on the PC"), as the file
  pickers are: `data-blobsave` marks the control, `.nosave` its note, `drawBlobSaves()` sets them. The lab's other
  blob URL plays a sound (no download); the copy buttons use the clipboard; nothing else makes a blob or data download.
- **Voice commands**: every fixed command the voice answers without the AI, grouped (where you are, where to go, your
  trip and materials, the voice), each with what it does, every phrase that asks it and the words that narrow it
  ("nearest Vista / repair / carrier / raw … trader", "hush for ten minutes / for half an hour / until the next jump",
  "this session"). From GET `/api/ask/commands` (`outrider.ask.command_list`): the phrases from resources/ask.json as
  the server read it at start (one spelling of each), a new `descriptions` object there for what each does, the
  narrowing words from the tables the answers read. On the PC: Settings → Voice's **Voice commands** fold (Find a
  setting finds it by "voice commands", "phrases" or a phrase's words); on the tablet: Settings → **Voice commands…**,
  a big scrolling sheet like Choose alerts….
- Tests: test_ask's VoiceCommands (a description per command, each command in one group, the list the file's phrases
  with each one asking its own command, the narrowing words read as listed, the endpoint); smoke checks for the app's
  hidden saves (no visible blob:/data: download with `OutriderApp`, shown without, Export settings saving a blob), the
  desktop list and its filter, and the tablet's sheet. Docs: tablet.md, voice-and-alerts.md, AGENT_GUIDE.

## 2026-10-14 · No file picker in the Android app
The author's decision of 2026-10-14: the Android app's WebView has no file picker and will not get one.
- In the app (`window.OutriderApp` exists) the two controls that open a file input, Bookmarks → **Import…** and
  Settings → Sharing → **Import settings…**, are hidden, and a muted note in their place says to import from a browser
  on the PC. Any browser, a tablet's included, keeps both. They are the page's only file inputs (no sound, font or
  voice control picks a file). `data-picker` marks such a control, `.nopicker` its note, `drawFilePickers()` sets them.
- Smoke check: one control and one note per file input; hidden / shown with `OutriderApp`, the other way round without.
  Docs: tablet.md (the app), views.md (Bookmarks), voice-and-alerts.md (settings import), AGENT_GUIDE (the app's contract).

## 2026-10-14 · Version 2026.10.23
- The Massive Tweak Update: the crew of voices (nine roles, names, crew lines, voices kept loaded, a voice per
  personality), 🎯 on every system with the game brought forward, the overlay's Target and Alerts panels, its pill and
  per-panel hiding in combat or docked, fuel and route checks (one fuel window, the last scoopable star, wrong target,
  finished systems skipped, Earth-like / ammonia routes, sweeps, Around, the Map's route, the In-Game Route the game did
  not write), exobiology (value from sample 1, geology ✦, reported species, your own runs, 🔍 nearby), the carrier's
  upkeep and trip, material traders, uploads' Recent / Try again / outage card / key checks / Log marks / EDSM gap fill
  and import, Show log, Restart, Backups, start with this computer, sector names, hush times, Find a setting, view
  windows, bookmark import, the Shadows theme, and the review fixes. What's new has its section. PARSER_VERSION 50:
  the first start re-reads the journals once, after a backup.

## 2026-10-14 · Overlay panels hidden while docked, one rule for every 🎯, the In-Game Route the game did not write
The author's requests of 2026-10-14, and a game quirk seen on his PC the same morning.
- **Hide while docked, per overlay panel**: Settings → In-game overlay's table has a **Docked** box per panel (none for
  the radar: a dash, it shows only on a body's surface), kept in a new `[overlay] hide_docked` list as `analysis_only`
  is (`overlay.docked_list`, POST `/api/overlay` {hide_docked}). Default, also for a config without the key: System,
  Target, Now and Bio hidden, the strip and the alerts shown. It replaces the fixed rules (Now hidden docked, the Target
  panel since D1); the Target panel still shows over the galaxy map while docked.
- **A narrower panel table**: short headings with the full wording on hover ("Hide when mode" over "Combat" and
  "Docked", "Corner", "X %", "Y %", "Size %", "BG %", "Opac. %"), the panels' names in plain case (wrapped when the
  dialog is narrow), narrower number fields and corner list, ↺ for reset; every control kept. Checked headless at the
  Settings dialog's width (1280, 1400, 1920 px windows), Default and Elite themes: no sideways scroll any more.
- **One rule for every 🎯**: a 🎯 shows only on the game PC and where auto-target can work (the virtual keyboard
  available, no binding missing: `canAim`, the Map's old `mapCanTarget`), checked once in `hwyAimBtn`. Changed: S31's
  🎯 (bookmarks, the next stop, Nearest rows, checklist finds), the carrier's and a boxel's checked only for the game PC;
  a route's rows and line not at all (CSS hid them on a server); a failed row's ⟳ Retry now follows it too, and Plot
  Route's "🎯 target next" is disabled by it. Nearby and the Map already used it.
- **Nearby's 🎯 left of the name**, in a slot every row has, so the 🎯 make one column and the names stay in line; none
  where auto-target cannot work.
- **Carrier tile**: a suspended service reads as its name and a red ✗ ("Redemption office ✗", "suspended" on hover),
  like "UC ✓ · Vista ✓" beside it.
- **NavRoute.json the game did not write**: after a `NavRoute` journal line (now read: meta `navroute_event`,
  journal-derived, reset on a re-read) an older NavRoute.json is not taken for the route nor for a cleared one; the file
  is read again every 2 s for a minute (`NAVROUTE_RETRY_S`, `NAVROUTE_LATE_S`), then when it changes. Meanwhile the
  In-Game Route line says "2 jumps left to Smojooe SJ-I b23-0 · the game didn't write the route's stars"
  (`State.route_minimal`: FSDTarget's RemainingJumpsInRoute, Status.json's Destination; no hops), until NavRouteClear or
  arriving. The look-ahead (S1, S2), S11's game target and the Map's route read `Journals.game_route()`, so they see no
  game route rather than the previous one. The guide says to clear and plot a different destination if it stays so.
- Tests: test_overlay (hide_docked's parsing, default, config round trip, POST, each panel docked, the galaxy-map
  exception; the old docked expectations follow the default), new test_navroute.py with tests/fixtures/navroute_late
  (that morning's sequence: the minimal line, a late write, an older file never taken, the file before its line, clear
  and arrival, the re-read timing and a tick); page smoke: the overlay table (Docked boxes, headings and hovers, the
  post), "one 🎯 rule", "nearby 🎯" (left of the name, the slots), the carrier's ✗, "in-game route, not written"; the
  smoke blocks that check 🎯 make auto-target available first (`aimReady`).
- Docs: overlay.md, settings.md, plot-route.md, views.md, cargo-and-trading.md, DESIGN_NOTES, JOURNAL_REFERENCE,
  AGENT_GUIDE, the example config.

## 2026-10-14 · 🎯 on Nearby's rows
The author noticed Nearby had no 🎯, while bookmarks, the header's next stop, the Nearest finder, checklist finds (S31)
and the Map (S72) all target by a click.
- **Nearby (the Overview's pane too)**: a small 🎯 beside each system's name targets it in the galaxy map, by the row's
  exact id64 string (route "system", POST `/api/highway/target`). Shown where auto-target can work (the game PC,
  available: `mapCanTarget`, as a Map click), never on your own system's row. A click on it targets only: it neither
  opens the system (S73's row click) nor copies the name. Its countdown shows on the row (`renderSysAims` redraws Nearby).
- **Tablet**: a Nearby row's sheet now offers 🎯 Target; a tap on the 🎯 itself targets.
- `static/page.js`: `nearAimBtn`. Docs: views.md, plot-route.md, tablet.md, DESIGN_NOTES, AGENT_GUIDE.
- Tests: page smoke "nearby 🎯" (the id, none on your own row, the post and no pin or copy, none without auto-target or
  off the game PC, the tablet sheet's Target).

## 2026-10-14 · EDSM flight log import rides out a timeout
The author's import of his EDSM flight log stopped for good at week 203 of 438: "failed, Couldn't reach EDSM: timeout".
One timeout ended a walk of over an hour.
- **Import (S67)**: a week EDSM does not answer (a timeout, no connection, no DNS, an HTTP 5xx, EDSM's own msgnum 5xx)
  is asked again, the same week, after 30 s, 1, 2, 5 and 10 min (`readclient.RETRY_WAITS_S`, about 20 min), the 10 s
  pace and the slow-down wait unchanged. The progress says "EDSM not answering: trying week 203 again at 21:30
  (attempt 2 of 6)". Only then does it stop "failed", the reason ending "(tried 6 times)"; Go on resumes from the
  cursor. A refused key (203), any other refusal, an HTTP 4xx or a malformed answer still stops at once.
- **The lookups by name at the end**: the same rule. Spansh or EDSM down past the retries stops the import "failed"
  ("Couldn't reach Spansh: timeout (tried 6 times)") instead of finishing with the names silently unplaced; Go on looks
  up the names still without a place.
- **Backfill (S47)**: the Check and Send's guard had the same weakness (one timeout failed the job): their reads now
  retry the same way, the job's line saying when, and **Stop** on that line ends the wait. Reads only, so a retry
  repeats nothing EDSM stored. The sender itself was already retried by the upload loop.
- `outrider/readclient.py`: `retrying`, `transient`, `try_later` (an EDSM answer saying slow down or failing), `Unreachable`.
- Tests: a timeout, a 503 and a msgnum 500 then success (the week kept once, the progress during each wait); refused
  every time (six tries, then failed with the reason); a 203, a malformed answer and a 403 at once; a lookup's timeouts,
  failed, then Go on finds it; the Check and the guard retrying; Stop during a Check's wait; smoke: the retry line and
  its Stop.

## 2026-10-13 · Find a setting keeps the context: whole blocks and whole tables
The author's report: "crew" showed only the XO's row of the crew table (its description says "crew member"), hiding
the rest of the table, the switches and the note on the XO.
- **Blocks**: a word of a titled block's heading shows the whole block, as a section's name shows the whole section.
  Such blocks are marked `data-find-block="its words"` (a folding block's summary counts too): Voices kept loaded, Crew,
  Personality voices, Server's Backups and Start with this computer, each upload service (EDDN, EDSM, Inara, now each
  in its own `div.upsvc`) and the overlay's panels table. A block's `<h4>` stays shown with any part of it.
- **Tables**: any table in a section (Alerts, the crew, Personality voices, the overlay's panels) shows whole when one
  of its rows matches, the matching rows marked (`tr.sfmark`, the theme's accent on its cells); when a word names rows
  in their first cell only those are marked ("tactical" marks Tactical, not the members whose danger lines it says).
  Personality voices' selects count by their choice alone (`data-sfone`), as the crew's do.
- Unchanged: the "N sections match" count, Server's config sections as context (not blocks), and nothing the filter
  opens is remembered; clearing also closes Backups / Start with this computer again if they were closed (`SF.folds`).
- Smoke: "navigator" shows both tables whole, the Navigator's and the jump alert's rows marked; "crew" all nine members,
  the switches and the XO note, none marked; "tactical" all nine, only Tactical marked; "backups" and "zips" the Backups
  fold, opened, and not Start with this computer; "inara" all of Inara's block; cleared, the fold is back as it was.

## 2026-10-13 · The crew, batch 3: crew members mention each other, "XO" said right, Audition: crew lines
The last of three batches of the crew: lines where one crew member mentions another ("Fuel 18 percent. Ask the
Navigator for the nearest scoopable star."). With the crew off nothing changes: you hear exactly the lines you did.
- **The placeholders**: `{navigator}`, `{science}`, `{exobiologist}`, `{engineer}`, `{quartermaster}`, `{comms}`,
  `{tactical}`, `{mining}`, `{xo}`, optional in every alert's lines. Each says the member's name when Settings gives it
  one ("Mira", in every position), else its role as a crew says it ("the Engineer", not "the Chief Engineer"; "Comms"
  and "Tactical" without an article), with a capital at a sentence's start (the line's start, or after ". ", "! ",
  "? ", "... ", judged on the line as filled, so a briefing's full stop counts). Filled the same way on the page
  (`lineVars`, `fillLine`) and in `outrider.speech.fill`; the page reads the words from GET `/api/speech`'s `crew_roles`.
- **The rules**: such a line is picked only while the crew is on, and never by the member it names. The checks reject a
  line naming whoever says its alert on the default table (the row's member, Tactical for a danger line, the XO for
  speech on: `crew_speakers`, from Python copies of page.js `ROW_KEYS` and `DANGER` that a test keeps in step) and a list
  holding only crew lines; at pick time a row moved to another member, a danger line with its switch off and the XO
  standing in skip the lines naming themselves. A 👎 that would leave a list no plain line is refused (409), and a list
  whose plain lines are all banned by hand is used whole.
- **The new lines**: 390, 78 in each personality list (business, sarcastic, sarcastic_profane, sweet, sweet_profane):
  3 per list for 26 alerts where one member mentioning another is natural (the undiscovered arrival, the briefing, the
  FSS done, leaving, a bio body ahead, a new region, codex, rare stars, high-g approaches, valuable bodies, biology
  found, a body's last species, a body left unfinished, low fuel, an unscoopable star, tank full, jumponium, hull,
  supercharged, docked to sell, sold, unsold at the red level, the carrier arrived, someone scanning your firsts, the
  session recap, welcome back), each in its list's tone and about another member, never to it. Every list keeps all
  its old plain lines.
- **"XO"** is said "ex-OH" (resources/pronounce.json): espeak alone reads it "zo".
- **Audition: crew lines** (Settings → Voice → Crew and the voice lab): one crew line per alert that has them, in each
  personality (the lab's picked one, if any), with your crew's names and made-up ones for a member without. The XO note
  now says names are spoken when another member mentions them; the lab's lines take crew lines as the alerts would.
- Docs: the voice guide's crew section (crew lines, the placeholder table for writing your own), DESIGN_NOTES,
  AGENT_GUIDE, and speech.json's own readme.
- Tests: `tests/test_crew.py` (the placeholders and words, the fill in both positions and after a filled {text}, who says
  a key, `ROW_KEYS`/`DANGER` against the page, the own-role and crew-only checks, the ban guard, the shipped lines: every
  list's plain lines kept, crew lines for 25+ alerts in each list, none a vocative; "XO" through the respelling path); a
  smoke check that a crew line is never picked with the crew off, that `{engineer}` says "the Engineer" and "Mira" when
  named, a moved row never names its new member, and the lab's crew lines and their audition.

## 2026-10-13 · The crew, batch 2: Settings' crew table, the voices kept loaded, the Alerts Crew column
The second of three batches of the crew: the screen the author approved (the mockup of 2026-10-13), built with the
page's own parts so it works in every theme and at phone width. The crew's own lines (and "Audition: crew lines") come
in batch 3.
- **Settings → Voice, top to bottom.** The main voice, labelled "= XO" with "the XO's voice: answers, status reports, the
  co-pilot, and the stand-in for everyone" while the crew is on; **Voices kept loaded**; **Crew**; the crew table; the XO
  note; then Personality voices, whose heading says crew members "as the personality" use it.
- **Voices kept loaded** (shown whenever a voice besides the main one is in use, a personality's too): the memory note
  from the payload's `voice_memory` ("This setup uses 4 different voices besides the XO: about 527 MB of memory on this
  PC", or "on the server"; amber over 500 MB, red over 1 GB, with the hint that the people of one voice cost no more
  than one), then **Keep loaded [N] of the M voices in use · about X MB** (the N largest), what fewer costs ("1 voice
  is set aside when not in use: its next line waits about a second") or "nothing waits", and **Load them at start**.
  Both write `[speech] voices_loaded` / `voices_preload` through POST `/api/config`, which now applies those two at once
  (`State.LIVE_CONFIG`, `config_live`: the loaded voices over the new number set aside now; the answer's `live`, and
  `restart` only when another key waits for a start; Server settings says "in use now" for them).
- **Crew**: Split the alerts among a crew, Danger lines always in Tactical's voice, ▶ Audition: by crew (each member
  says one of its own lines in its own voice). With the crew off only the switch shows.
- **The crew table**: the XO row first and tinted ("the main voice"; its voice select switches the main voice, its
  personality the ones ticked), then each role: Name ("no name"), Personality and Voice ("as the XO" / "as the
  personality" in italics), Speaker (a voice of several people only), Speaks for in words (Tactical's "every danger line"
  in red while that switch is on; a member's danger rows "(their danger lines: Tactical)"), ▶ one of its lines, ↺ back
  to "as the XO" (none on the XO row); why the XO speaks for a member under its name. Each change is one POST to
  `/api/voice/crew`.
- **Settings → Alerts' Crew column** (while the crew is on): a select per row; a danger row keeps its owner with "·
  spoken by Tactical (danger)" while the switch is on (the carrier's: "its danger lines by Tactical").
- **The voice lab**: Assign to a crew member beside Use this voice and Give to this personality, ✓ crew members using the
  voice picked, and ▶ Audition: by crew.
- **Find a setting** finds the new rows: "crew", "xo", a role's name, "memory", "keep loaded", "load at start" and the two
  keys; the crew's selects count by their choice alone (`data-sfone`), and rows inside a hidden box (the table with the
  crew off) are never matches. The tablet's Settings sheet has none of it.
- Tests: `tests/test_crew.py` (`ROW_WORDS` and `ROW_KEYS` in step with the alert rows, every danger key in the row that
  says it; the two keys applied at once with no restart, the LRU trimmed, a port change still waiting; no crew on the
  tablet's sheet); a smoke check of the note's bands and figures, Keep loaded and Load at start posting, the table's
  rows, a speaker, ↺ and a name, the Alerts column and its danger hint, a moved row, everything hidden with the crew off
  and Find a setting.

## 2026-10-13 · The crew, batch 1: who says each line, the XO standing in, the voices kept loaded
The first of three batches of the crew (the spoken alerts split among crew members, each with its own personality and
voice). This one is the resolution and storage; Settings' crew table and the new lines come in the next two. Off by
default, and with it off everything is said exactly as before.
- **The roles and their rows.** `outrider.speech.CREW_ROLES`: the XO / Co-pilot, Navigator (every route line, trade
  routes too), Science Officer, Exobiologist, Chief Engineer (low fuel too), Quartermaster, Comms Officer, Tactical (the
  danger lines while the Danger switch is on, its default) and Mining Officer, each with the alert rows it speaks for.
  One table: the page reads it from GET `/api/speech` (`crew_roles`); a test fails when an alert row is missing or twice.
- **Kept on the server.** Meta `crew` (live-only: a journal re-read keeps it, backups carry it): the crew switch, the
  Danger switch, each member {name, personality, voice, speaker} and any row moved to another member. POST
  `/api/voice/crew`, one change at a time, checked against the lines file's personalities and the voices installed;
  the payload's `crew`. The XO is the main voice: giving it a voice switches the main voice; only its name is kept.
- **Who says a line.** The page resolves it (`crewMember`, `crewVoice`): Tactical for a danger line while the switch is
  on, else the row's member; its personality's lines and its own voice and person, "as the personality" falling back
  to the personality's own voice (S40's pick, then speech.json's), then the main voice. Every member starts "as the XO".
- **The XO stands in.** A member whose voice is not installed, failed to load or lacks that speaker, or whose
  personality the lines file no longer has, and any alert row no role covers: the XO says the line, never dropping it.
  The payload says why for each member; the server checks again when it says a member's line (the page sends the role
  with the voice), and writes it once per voice and reason to the log: "crew: Engineer's voice en_GB-x not installed:
  the XO speaks for it".
- **Voices kept loaded.** `[speech] voices_loaded` (a number, "all", or unset: the voices in use up to 4) replaces the
  fixed 2..4: never more loaded beside the main voice than chosen, the main voice never set aside; a value it cannot
  read is 4, said at start. `[speech] voices_preload` (off) loads them at start, one at a time after the journals are
  read. Both in Server settings (a pick-list), the example config and the guide's Settings page.
- **Memory.** The payload's `voice_memory`: each voice in use besides the main one with its memory (the installed
  .onnx × 1.6, measured), how many are kept and what that costs, how many are set aside; for Settings' note in batch 2.
- Tests: `tests/test_crew.py` (the table against the page, storage and checks, the XO for each failure kind and the log
  once, a member's line on the server, the LRU never above the number chosen with the main voice never in it, "all",
  the preload, the estimate, the config keys); a smoke check that with the crew on a tank-full and a fuel line are the
  Engineer's voice, a fuel line Tactical's with the Danger switch on, a moved row its new member's, the XO for one who
  cannot speak, and that with the crew off nothing changes.

## 2026-10-13 · No payload for a Spansh retry that changed nothing, and the smoke test holds payloads mid-block
- **A Nearby retry that failed again redrew every open page for nothing.** With Spansh unreachable (the network down),
  the sphere search is asked again after 30 s, 60 s, 2 min, 4 min, then every 5 min; each retry failed at once and
  bumped the payload twice ("asking Spansh again", then "Spansh unavailable" again) with the same cached rows. Now a
  retry says "asking again" only once its search has been out a second (`RETRY_SAY_S`), and bumps at the end only when
  the status, the rows or the sphere's cut changed. Measured on a scratch server with every outside service offline:
  3 payloads in 240 s before (all with nothing changed), 0 after. Test: a retry failing at once sends no payload, a slow
  one still says so, a successful one sends its rows.
- **The page smoke test's late blocks failed now and then** (EDSM flight log import, the backfill, S30's first stop):
  that retry's payload landed while a block had injected state into the page and replaced it. `holdPayloads()` /
  `releasePayloads()` hold the long poll's answers while a block that injects state and waits runs (39 blocks; not
  the hush block, which needs its payload), with a check of its own; the put-backs added as stop-gaps (S31's next stop
  and bookmark, the import's account) and the speech queue's three attempts are gone.

## 2026-10-13 · Review fixes: the overlay on a workspace per monitor, the first stop, S12's jumps, S2's top-up, the hush answer, the voice's window, the exposure warning
From the Fable review sweep of the last 33 commits (areas overlay, routes, voice, security):
- **Keep showing when Elite is not the active window** hid the overlay on window managers with a workspace per monitor
  (i3 and the like): the browser clicked on the other screen made its workspace the "current desktop". Another desktop
  counts only when xwininfo says the game's window is not viewable (GNOME and KDE unmap a window on a workspace not
  shown; the desktop alone when the map state cannot be read). Test: a fake desktop with a workspace per monitor.
- **The first stop picked on Here's schematic** (S30) was only ignored elsewhere, never forgotten: it came back on a
  return to that system. An arrival elsewhere after it was picked drops it now (stamped like the next stop, so a
  journal re-read's older arrivals keep it).
- **A survey route's next stop past finished systems** (S12) showed the last skipped row's leg as its jumps: now the
  legs from where you are, through the systems passed over.
- **The fuel top-up card was silenced where the last-scoop line would never be said again** (S2 remembered a stretch
  as said for the life of the process): a stretch is said once per arrival now, the payload's `dry_stretch.said` says
  it was said on this stay, and the page keeps the top-up card quiet only then and with that alert row speaking.
- **Find a system** said "Spansh doesn't know it" when EDSM had the name without a position and Spansh could not be
  reached: a 502 saying Spansh could not be reached, try again.
- **"Hush for five minutes"** said only "Quiet for 10 minutes.": the answer naming the three lengths was only captioned.
  It is the spoken news of that hush now (a `say` with the copilot's `hush`; `onHush` leaves it the news), once.
  `outrider.ask.HUSH_SAID` is checked word for word against page.js's (the guide said it was page.js's alone).
- **A view window (S37) or the Now window kept the voice for good** after the main window reloaded: given the voice
  while the main window that opened it waits in line, it hands it back within a second and queues again; "Speak from
  this window" there still keeps it.
- **The no-password warning** (start-up, the example config, the install guide) said a device on your network could
  read journals and edit bookmarks; it can do whatever the page does: change the settings (the password and journal
  folders too), restart Outrider, use the stored EDSM and Inara keys and, on the game PC, press keys. The words say so.
- The smoke test's next-stop step puts its injected next stop back before clicking (a payload from a Spansh retry could
  replace it).

## 2026-10-13 · Review fixes: the service's start limit, Recount's names, the depot cap, the EDSM backfill and import
From the Fable review sweep of the last 33 commits (areas server, carrier, uploads, exo):
- **The systemd service's start limit** counted every Settings Restart: ten in five minutes left the unit failed. Now
  30 starts in 10 minutes (`outrider/service.py` `START_LIMIT_*`: a crash loop at `RestartSec=5` still stops in
  minutes), and the page's "not back yet" words under systemd name `systemctl --user reset-failed ed-outrider`. An
  installed unit takes the new limit when installed again. Tests: the unit's limits; the smoke test's words.
- **Recount's Spansh names** were stored under their letters: "Occupied Escape Pod" made a line `occupiedescapepod`
  that no journal event (`occupiedcryopod`) would ever move. `outrider.cargo.SPANSH_IDS` (113 names, from EDCD's
  commodity tables, checked against Spansh's list) gives the journal's id; "Void Opal" is singular in Spansh's list, so
  its alias was right. The test now uses Spansh's real list (`tests/fixtures/spansh_commodities.json`, fetched once).
- **"enough after topping up"** ignored the depot's 1,000 t: `trip_top_up` says "before" the jumps only while the depot
  can take it all, else "on the way" when topping up as it runs down still covers it, and the tile says "enough if
  topped up on the way". Tests: both cases, the tile and the page.
- **The EDSM backfill never sends under `--simulate`** (a backfill interrupted, then a `--simulate` start on the same
  data, sent it) nor while another Outrider's lease sends EDSM: `edsm_bf_paused`, said beside its progress.
- **A key Check with a typed EDSM name** cleared the hold although the sender sends the stored name: only the stored
  name and key clear it now; another name EDSM accepts says "save this name first".
- **The EDSM import's name lookups are paced**: 3 s apart (`IMPORT_LOOKUP_GAP_S`), EDSM's through its gate too, with
  "N of M" on the Settings line (`edsm_import_resolve`); back to back, up to 500 made a burst.
- **The overlay's system panel** counted a scanned body someone else mapped as "under your levels": it is neither listed
  nor counted now, as on the page.
- The guide and `backup_before_reread`'s docstring said run() backs up through open_db's `before_reset`; they describe
  run()'s own steps now (that hook is the one-step open the tests use).

## 2026-10-13 · Bookmarks import
- **Import…** beside Bookmarks' Export (S53): pick a file and its bookmarks are added to yours, "12 added, 3 already
  there". The author's default, a merge: a system already bookmarked keeps its own name, note and date (INSERT OR
  IGNORE), so the same file twice adds nothing. POST `/api/bookmarks/import` {text} parses on the server (the pure
  `parse_bookmarks`; JavaScript would round an id64 above 2^53): Outrider's own export as CSV (a byte-order mark and a
  spreadsheet's ";" with decimal commas too) or JSON; id64, name and x/y/z needed, a note kept to 2,000 characters, a
  date it cannot read is today's. Bad rows are left out and counted with their line and reason ("id64 not a whole
  number (a spreadsheet may have rounded it)"), the first 20 described; more than 10,000 rows, or a request over 8 MB
  (read with its own limit, past aiohttp's 1 MiB), refuses the file in words. The imported rows get the sweep tick, 🎯
  and Plot route like any bookmark. Tests: export → import round trips (CSV, JSON) with an id64 over 2^53 exact, the
  merge, bad rows, the limits, a cross-site POST refused; the smoke test picks a file on the page.

## 2026-10-13 · Find a setting, and a voice per personality
- **Find a setting** (S39): a box at the top of Settings. Each word typed leaves only the rows that match it (their
  label, help, a Server settings key, or the config key a browser row defaults from: `data-find="section.key"` on 22
  rows, `test_settings.FindASetting` checks each is a real key), with their sections opened and "N sections match" (or
  "Nothing matches"); the other sections and their chips hide (`.sfhide`, so a game-PC-only part stays hidden on a
  server). A word naming a section shows all of it. It covers the Alerts table's rows, the Uploads and overlay boxes'
  parts, the overlay's panels, Backups, Start with this computer, Show log / Restart and Server settings' keys (loaded
  on the first word without opening the section), and filters again what redraws meanwhile. Nothing is remembered:
  `settingsOpen` and the config sections' folds are untouched, and clearing the box (Esc clears it first) or closing
  Settings puts every section back as it was. The smoke test finds every section by a word of its own rows and by name.
- **A voice per personality** (S40, both halves): speech.json's styles may name `"speaker": N` (checked;
  `outrider.speech.style_speaker`), one person of the personality's own voice or of the main voice. Settings → Voice →
  **Personality voices** gives each personality a voice and, for a several-person voice, a speaker (▶ plays one of its
  lines as it is heard, reset goes back to the file); the voice lab's **Give to this personality** does it from the
  lab's voice and person. Kept by the server for every browser and the tablet: POST `/api/voice/style` {style, voice,
  speaker?} (voice null resets), meta `style_picks` (live-only), the payload's `style_picks`; a pick wins over the
  file's voice and speaker, the pace stays the file's. The page carries the speaker with every line (the PC's player,
  `/api/say`, the next line, "say again"); the lab's lines and Audition speak each personality in its own. A line whose
  voice is not installed is said in the main voice by its own person, no longer by that number of the main voice; the
  voices kept loaded count the picks.

## 2026-10-13 · Questions asked, and any view in its own window
- **Questions asked** (S35): Settings' new last section shows what the voice heard, newest first: the words, where they
  came from, the ask.json phrase they matched and what it asks for ("matched “status report” → a status report", a
  hush with its length, the four questions of S14 by name), "no phrase matched (AI off)", or what the AI did (its
  rounds and the tools it ran, or why it failed), then the answer and whether it was said on the PC; **copy** puts it
  on the clipboard. The server keeps the last 50 in memory only (`State.ask_log`, `ASK_LOG_MAX`), every way out of
  POST `/api/ask` included (refusals 400 and 426, the AI's failures with their code, never its key); GET
  `/api/ask/log` serves them (behind the sign-in; not one of the AI's tools), the payload's `ask_seq` says when one
  came. `outrider.ask.match_phrase` names the phrase; `ai_answer` takes a `trace`. POST `/api/ask`'s shape is
  unchanged.
- **Any view in its own window** (S37): hovering a tab shows a small ↗ in its corner (or Shift+Enter on the tab) that
  opens that view alone in a window of its own (`?view=bm`...; pressed again it brings that window forward). Such a
  window has no tab row, never saves the view (the main window keeps its own) and its title starts with the view's
  name; ⌖ or a body opened from it goes to Here in the main window while that is open, otherwise it shows Here itself
  with ↩ back. The main window speaks: a view window joins the one-speaker queue a second late, like the Now window,
  which keeps its own ↗ and `?mode=now`. A bad `?view=` is ignored; the tablet has none.

## 2026-10-13 · Hush by voice for a set time, and four more questions without AI
- **A hush by voice takes a time** (S32, the server half): "hush for ten minutes", "quiet for half an hour", "hush until
  the next jump" (or next system, leave, arrive); no time is 30 minutes as before. `outrider.ask.hush_mode` gives only
  the server's three ("10m", "30m", "jump"): another time gets the nearest, and the answer names the three first ("I
  can hush for 10 or 30 minutes, or until the next jump. Quiet for 10 minutes."). "stop talking" hushes too. The
  tablet's hush buttons wait for the new tablet layout.
- **Four more questions without AI** (S14), matched before next jump and status report: **FSD injections** ("can I
  still make an FSD injection": "Premium injections: 2, short of polonium. Standard: 5. Basic: 31.", the recipes picked
  by group and grade, which the three FSD recipes in `materials.SYNTH` now carry; "Counts from before this login." when
  stale), **how far today** (the sessions ended since local midnight; "this session" the latest), **this body** (on it,
  else in its near-body zone, else targeted in this system: type, gravity, terraformable, value now and if mapped, the
  likeliest biology "up to", geology) and **left behind** (the nearest one or two systems within 100 ly with work over
  the server's `body_highlight_level` / `bio_min`, worth "up to"). Their phrases are in `resources/ask.json`.
- `/api/status` (and the AI's `current_status`) has `near_body` (`State.zone_body`) and `target_body`; the AI's
  `left_behind` gives each item's value (`up_to`, `adds`, the maps listed) and a system's `worth`; its `materials` gives
  each recipe's `group` and `grade` and `counts_from`. POST `/api/ask`'s shape is unchanged; its `command` can now be
  `fsd_injection`, `travel_today`, `this_body` or `left_behind`.

## 2026-10-13 · One table of survey route kinds, Earth-like and ammonia world routes, and a sweep
- **The survey slot's kinds are one table** (G4 / F4): `outrider.riches.SURVEY_KINDS` (a `SurveyKind` per kind: name,
  glyph, words, the Spansh URL by its constant's name, parser, what a stop asks of you, alert row, the plot's fields and
  fixed parameters, whether the map counts) replaces the "riches" / "exo" / "trade" checks in the server (the plot and
  its validation, the rows, what is left, the arrival and done lines, the moments), the overlay's route line
  (`SURVEY_WORDS` gone) and the page (`SURVEY` with each kind on one line, a test keeping it in step; the plot form's
  fields shown per kind by `data-field`, `RICH_FIELDS`; the status, "Plotted: …", the Map's route words). Every
  existing kind behaves as before. A Spansh POST's list value is sent as a repeated form field.
- **Earth-like and ammonia world routes** (S52): two more plotters, kinds "elw" and "aw". Probe P3 (U3,
  `scripts/route_probe.py`, answers in `tests/fixtures/spansh_body_types.json`): Spansh has no `/api/earth/route` or
  `/api/ammonia/route`; its own pages POST `/api/riches/route` with `body_types` and min_value 1, and the answer is Road
  to Riches', so they are parsed and followed as Road to Riches with the map always counted (no minimum value or mapping
  box), "Earth-like route complete." / "Ammonia route complete." at the end. Their moments use Road to Riches' alerts
  row (now "Survey routes"), the moment's `route` naming the kind.
- **A sweep** (S51): ticks in Left behind, My firsts (lost systems) and Bookmarks, one set across the three, and
  "🧹 Plot a sweep (N)" beside each list: POST `/api/riches/plot` {kind: "sweep", systems} plots them with Spansh's
  tourist router (probe P2 / U2: `/api/tourist/route`, `source`, `range`, `loop`, `destination` repeated; answers in
  `tests/fixtures/spansh_tourist.json`; `riches.tourist_rows`), from where you are with your ship's range, up to
  `SWEEP_MAX` (100) systems, in the survey slot. A system Spansh doesn't know yet is refused by name: plotted again
  without it, the note and the route's heading name it (`unknown_systems`). Followed by arrival alone: the next stop on
  each arrival, "Sweep complete." at the last.
- The smoke test's S31 check puts its bookmark back before its second Plot route (a payload arriving meanwhile replaced
  it and the check failed, at HEAD too).

## 2026-10-13 · Search and Nearest around another system, and the route on the Map
- **Search and the Nearest finder around another system** (S49): an Around select (you, your destination in game, your
  carrier, your next stop, a system by name) in Search's "Within N ly of" and in the Nearest dialog, kept on this
  device with each one's other choices (stores `search` and `nearest`). POST `/api/search` and GET `/api/nearest` take
  `around` = destination / carrier / next_stop or an id64, resolved read-only by `State.search_origin` (`locate`, then
  `listed_system`; the destination is `game_target`'s); a typed name is found by GET `/api/find` first, so
  `/api/nearest` stays read-only for the AI's tools. Distances are from the origin; each row's `from_you` is the
  hover's "N ly from you"; the finder's search cache keys on the origin, "here" stays where you are and no jump count
  is given from elsewhere.
- **The Map draws the route** (S50): `map_payload`'s `route` (`State.map_route`): the game's plotted route after you
  (`navroute_ahead`, shared with `route_ahead`) and the followed route's rows from where you are (the survey / trade
  route's or the Highway's, `route_newest` with both; from its next stop while off it), at most `MAP_ROUTE_MAX` (300)
  points, with its next stop (S12's for a survey route), else the header's next stop; worked out at each fetch outside
  the cached systems. The page draws the legs dashed (the game's in the path's colour, the route's green), ◎ on the
  next stop, the legend's entries and a card line for each stop (`mapRouteMarks`); a new plot or next stop refetches
  (`mapRouteKey` in the map's key). Map clicks on route stops target them as any point (S72).

## 2026-10-13 · 🎯 and Plot route anywhere, a click on the Map targets, and the voice plots far places
- **🎯 anywhere** (S31): POST `/api/highway/target` takes {route: "system", id} (the id64 as a string: over 2^53 a JSON
  number rounds), `State.system_target` (route_target's "system"): any system Outrider can name by id64 (`locate`, else
  `listed_system`: the Map's cached points and boost stars, the next stop, your carrier), never your own. 🎯 (game PC)
  beside each bookmark, the header's next stop, the Nearest finder's rows (their systems kept in `nearest_found` for
  `locate`, bounded) and the Exo-Biology checklist's "🔍 nearby" rows (S29's 🎯); the tablet's row sheet passes it on.
- **Plot route** beside a bookmark and the next stop: To filled, Plot Route opened on its form, plotted at once only
  when no route is followed (with one, Plot is your click).
- **The co-pilot button** falls back to the header's next stop after the survey route, the Highway and the boxel; a
  complete route counts as none.
- **A click on the Map** (S72) targets the system in game when auto-target can work on this PC (its keyboard and
  bindings, on the game PC), else copies its name; the card's last line and the hint under the map say which; your own
  system is copied; a run under way is said, not doubled. A tap shows the card with 🎯 Target and Copy name (the card
  takes taps then: `#pop.taps`).
- **The voice plots far places** (D4, option A): "nearest station" (or carrier, Vista, a trader...) also plots a
  neutron route to the place's system when it is further than `[highway] voice_plot_ly` (500 ly; `voice_plot` on by
  default); never while a route you have not finished is followed or a plot runs, said in a sentence added to the
  answer (`outrider.ask.nearest_dock`, `State.voice_plot`). The answer's shape is unchanged.

## 2026-10-13 · Survey routes skip finished systems, and a wrong-target check on the route line
- **Survey routes skip finished systems** (S12): a Road to Riches or Exomastery route's next stop passes over the
  systems after where you are that came with work and have none left by your journal (`riches.had_work`,
  `Journals.riches_open`, `State.riches_next_open`, cached on the route, the place on it and `data_seq`). Every "next"
  follows it: the line ("Next: Pru Aim XY-Z d1 · 3 jumps · 6 of 22 · skipping 2 done", the names in the hover; the
  summary's `skipped` / `skipped_names`), the tab's next row and heading, the clipboard copy, the co-pilot button, 🎯
  Target next, the overlay's Now line, and the voice ("Next stop: Pru Aim XY-Z d1, skipping 2 systems you've
  finished.", from arriving and from finishing a system). A row without bodies and the route's last row are never
  passed over; a trade route never skips. The co-pilot button now aims a trade route at its first stop in another
  system, as its clipboard copy does (`survey_jump_next`).
- **The game's jump target** (F3): `outrider.target.game_target(status, here, route, fsd)`, beside `targeted()`:
  Status.json's Destination, the end of the NavRoute it is a hop of (a route plotted in the galaxy map), or with no
  live Status.json the journal's FSDTarget; nothing locked, or a body or station in this system, is none.
  `State.game_target` feeds it.
- **Wrong-jump check** (S11): the summaries' `target_check` {ok, name, id, next, ahead} compares the followed route's
  next stop (the Highway's next row; a survey route's past finished systems; a trade route's first stop elsewhere)
  with the game's target. On every copy of the route line (under the tiles, Now, the Plot Route tab's heading):
  "✓ targeted", "⚠ targeted X, not the next stop Y", or for a later stop of the route "↷ targeted X, 2 stops ahead"
  (the plan's default: on purpose, not wrong). Silent off the route, once complete, with nothing targeted and for a
  target in this system. On the overlay, the Target panel's own row (its one overlay place): "✓ the next stop of
  your route" / "↷ 2 stops ahead on your route" / "⚠ not the next stop: Y".
- **Said once per new wrong target** (`wrong_target_watch`, a follow-up): a `wrong_target` moment {system, next} per
  (route, next stop, target), for the route the line shows server-side, only once the galaxy map is closed and never
  during an auto-target run. Its own alerts row `wrongtarget` ("Wrong target", spoken, not notified by default, in
  `SPEECH_SYS_BOUND`) and speech key `wrong_target` (15 lines in each list).

## 2026-10-13 · The last scoopable star before a stretch you can't cover
- **The route ahead, whatever route you follow** (F2, S2's groundwork): `State.route_ahead()` gives the hops from where
  you are: the game's plotted route (NavRoute.json, from where you are on it; a survey route's legs come this way),
  then, when it ends on a row of the Highway route you follow, that route's one-jump rows after it, or the Highway's rows
  from where you are with no plotted route; a neutron-plotter waypoint several jumps away, a hop of unknown length or 50
  hops end it. Each hop's star is scoopable True / False / None from what is known (`_star_scoopable`: the game's star
  class, else the row's facts, a neutron False and an exact route's refuel row True as P1 showed, else the cached Spansh
  record); None stops any claim. Multipliers only for facts (the Fable review): the charge you hold on the first hop,
  and a hop leaving a neutron row of an exact-plotter route.
- **Last scoopable star** (S2): `State.last_scoop_check`, a follow-up after the heavy check, on arriving and as the
  fuel, cargo, charge, route or target change (every 3 s at most in one system), never while scooping (Status.json's
  flag), with the game running. At a scoopable star, when the stars ahead are known not to scoop up to the next that is
  (or may be) and the fuel aboard won't carry the ship over them (`fuel_window` over those hops: under its low end, or no
  level the tank holds: `full`), the payload's `dry_stretch` {count, system, next, need_t, full, have_t, source, first}
  and a `last_scoop` moment once per stretch (its route source and first dry star). Silent when a hop is beyond the
  ship's best jump at any fuel (not a fuel matter), when the fuel is too much rather than too little, while the fuel
  model is incomplete, and where S1's `short` stands on an exact-plotter route (the plan's default: S1 suppresses S2).
- **The page:** its own alerts row `lastscoop` ("Last scoopable star", in `SPEECH_SYS_BOUND`) and the speech key
  `fuel_last_scoop` {count} (danger: business by default) with the author's line first: "The next 3 stars on your route
  are not scoopable. This is your last chance to top off before you need to call the Fuel Rats." (50 business lines, 15
  each for the others); one star and the no-amount case are plain sentences. The bit "⛽ last scoop before 3 dry" on the
  In-Game Route line (else the route line under the tiles) and under Now's fuel, with how much to scoop
  (`dryStretchText`/`dryStretchHtml`); the top-up card (`fuel_topup`) stays quiet in a system where S2 speaks.

## 2026-10-13 · One fuel window for the Highway, Now's jump cost, and Find by name through Spansh
- **Fuel won't reach the refuel stop** (S1, with the fuel groundwork F1): `outrider/fsd.py` `fuel_run(model, fuel,
  other, hops)` burns (ly, multiplier) hops one by one, the ship lightening (reach capped as `target_hop` does, the
  reservoir as mass), and `fuel_window` finds the starting fuel that makes a whole run from a grid of levels every
  0.25 t (the Fable correction: the range falls with the mass, so a run succeeds on an interval, and a full tank may
  fail where a part one passes; a bisection of the tank would be fooled), each end refined. `highway_heavy_check` now
  works through `_highway_fuel_window` on an exact-plotter route: the hops to the next refuel row (or the end, 50 at
  most), the held charge or this neutron's on the first, Spansh's neutron rows after; over the high end by
  `HIGHWAY_HEAVY_SLACK` is `heavy` (with `hop`: "too much fuel for the jump to X" when a later one fails), under the low
  end is the summary's new `short` {need_t, max_t, have_t, refuel_at, jumps, end, here_refuel}: "⚠ fuel won't reach the
  refuel stop: X in N jumps · scoop to ≥ A t, at most B t", too little and too much in one line from one sum, never two.
  Said once per system as a `highway` moment `short` under its own alerts row `refuelshort` with the speech key
  `fuel_short` {system, jumps, need} (danger: 50 business lines, 15 each for the others); at a refuel stop itself only
  "⛽ scoop to ≥ A t to reach …" on the line, never spoken. In the strip and Now (`hwyShortText`), the spoken status
  clause (`hwySpoken`) and the overlay's route line (`overlay.short_text`). The neutron plotter, and a route plotted
  with injections, keep the one-jump heavy check (`_highway_heavy_now`).
- **Probe P1 (U1):** `scripts/exact_probe.py` asked Spansh's exact plotter for three routes (read-only, saved as
  `tests/fixtures/spansh_exact.json`): every jump carries `is_scoopable`, but it equals `must_refuel` on all 45 (the
  plan tops up at every scoopable star) and is False at both ends whatever the star, so no `highway_route.scoopable`
  column: an exact route's `refuel` flag says the same (for S2).
- **Now: the targeted jump's cost and the scoopable share** (S19): `hopCostHtml(hop)` ("56.7 ly · 0.9 t · leaves 20
  max jumps", or out of range) and `scoopRateWarn(f)` ("scoopable: 9 of last 20", amber under two usual gaps), shared
  by the header's target line, the fuel tile and Now (under the target and the fuel). Page only (the overlay's copy is
  D1's Target panel, as the review settled).
- **Find by name asks Spansh when EDSM fails** (S48): `find_system` tries `Spansh.system_record` after an EDSM error,
  an unknown name or one without a position, and keeps the hit as a minimal stale base (`_find_keep`, shared with
  EDSM's; no cache change). "No system called … is known here, to EDSM or to Spansh."; one source unreachable says so;
  both: 502. The FindSystem tests mock the Spansh call.

## 2026-10-13 · The overlay's Alerts panel, and a steady colour-tables test
- **An Alerts panel on the overlay** (S26): `[overlay] alerts_panel` (false), the seventh panel (`overlay.PANELS`
  "alerts", "Alerts"), placed top centre under the system strip (`LAYOUT_DEFAULT`; `clean_layout` fills it into an
  older layout) and moved in Arrange mode like the others; its own row in Settings → In-game overlay with an Analysis
  only box. The page words and switches the alerts, so it posts each alert it shows (`overlayAlert` from `alertOut`,
  POST `/api/overlay/alert` {kind, title, body, danger}, `pc_only`) while the overlay and the panel are on, on the
  game PC, and the kind is switched on in that browser (`alertOn`: any of notify with notifications on, its sound,
  speak; the plan's recommended default; `jumponiumOn` is now `alertOn("jumponium")`). Every window posts, the tablet
  too: the server (`State.overlay_alert`, `overlay.alert_entry` / `alert_add`, in memory) keeps the last
  `ALERT_KEEP` (6) and drops the same title and text within `ALERT_SAME_S` (10 s). `overlay.alerts_panel`: newest
  first, three at most, each `ALERT_SECONDS` (8 s), danger (the speech queue's danger rank or the danger sound)
  `ALERT_DANGER_SECONDS` (15 s) with its title in red, a red frame round it and the panel's frame red. It shows
  wherever the overlay shows panels, docked and on foot too, and over the galaxy map beside the Target panel; never
  over the system map, the FSS, the SAA, the codex or in the tunnel. No page open anywhere: no alerts on the overlay
  (DESIGN_NOTES' known limits). The test panels add a sample (all seven).
- **A flaky test made steady:** `test_values.ColourTablesRetry.test_the_banner_and_retry` shared one `hold` event
  between its two runs; set by the first, it let the second run's download finish before its second POST, which then
  started another download and bumped `bio_rules_gen` twice (2 of 4 full runs failed). Each run has its own event now,
  and the second run checks the one-at-a-time 409 too. The server's guard was sound: the check and the task's start
  have no await between them, and a Retry after a finished download is meant to start a new one.

## 2026-10-13 · The overlay pill, and keeping the overlay when Elite is not the active window
- **The overlay pill** (S8): `#ovPill` beside the link pill while the overlay is on (game PC only): "overlay ✓"
  drawing, "overlay …" starting, Elite not running or loading, behind this page, minimised or covered, "overlay ✗"
  with the reason on hover (wmctrl or xprop not installed, Elite's window not found, the window not answering for
  `QUIET_S` 15 s, a PyQt6 install that failed, exclusive fullscreen). The window sends what it sees with each GET
  (`&w=`, `overlay_window.track_code`, `overlay.TRACK_CODES`), kept for its User-Agent only in `State.overlay_track`
  (the page woken on a change); `overlay.health` adds the runner, the game live / loading from the journals and
  DisplaySettings.xml's `<FullScreen>` (`display_settings_paths` from the live journal folders, `display_mode`, read every
  `OVERLAY_DISPLAY_CHECK_S`); `overlay_info.pill`; `overlay_window_tick` wakes the page when the pill changes on its
  own (a window gone quiet). "Not the active window" is amber only while the page has the focus ("Elite is behind this
  page"), red otherwise. The tablet's link line adds it ("linked · overlay ✓"); Settings → In-game overlay says the
  same while the window runs. The X11 tracker notes a missing xprop (`xprop_missing`), which used to keep the game
  silently never "in front". The plan's game-process check was left out: the journals say whether the game runs.
- **Keep showing when Elite is not the active window** (S25 with S25b): `[overlay] show_inactive` (false), a switch in
  Settings → In-game overlay, in GET `/api/overlay`'s answer. With it on the window still hides when the game is
  minimised or on another desktop (X11 `_NET_WM_STATE_HIDDEN` / `_NET_CURRENT_DESKTOP`, Windows cloaked) or covered
  by other windows over a quarter of it (`overlay_tracking.covered_share`, `COVERED_SHARE`: X11 from
  `_NET_CLIENT_LIST_STACKING` and wmctrl's geometries, Windows' z-order walk `win_rects_above`, untried), asked only
  while the switch is on and the game is not in front (`inactive_checks`), kept `INACTIVE_EVERY_S`. A native Wayland
  window is not seen covering the game: the guide says so.

## 2026-10-13 · The overlay's Target panel, and panels shown only in analysis mode
- **One Target panel** (D1): the overlay's body panel became the Target panel (same id `body`, `body_panel` switch and
  layout key: an existing arrangement and config carry over; PANEL_NAMES, Settings' row and help say "Target"). Inside a
  body's near-body zone (Status.json BodyName with an Altitude, ApproachBody's point) it shows that body, even over a
  target, and keeps it `TARGET_ZONE_LINGER_S` (5 s) after leaving the zone (`overlay_zone_body`, `State.overlay_zone`);
  outside, the body targeted in this system, else the system targeted (`overlay.target_system_panel`: the verdict, Spansh's
  and EDSM's counts, "checking…" until the lookup for THIS target is in, the star with ⛽ / ✕ not scoopable / ⚠ throttle
  down, the jump from `target_hop`, the Nearby row's value and notables, "next jump of your route · N to go" from
  FSDTarget's `RemainingJumpsInRoute`, now kept in `Journals.target["remaining"]`), else nothing (the fallback to the
  body you fly near is gone). It is the one panel over the galaxy map (`OVERLAY_GALAXY_MAP`; `OVERLAY_HIDE_FOCUS` is
  7-11 now), docked too, and off while docked elsewhere. `overlay.star_hazard` (page.js `hazardNote`) adds the black
  hole to the Now panel's ⚠ as well. The "body" test panel shows the Target panel's system.
- **Analysis only** (D2a): `[overlay] analysis_only` (a list of panel ids, `overlay.analysis_list`: unknown ones dropped
  with a warning) keeps those panels off in your ship while the HUD is in combat mode; ignored in the SRV, on foot,
  over the galaxy map and for the test panels. POST `/api/overlay` takes the whole list, `overlay_info` returns it,
  Settings → In-game overlay has an "Analysis only" column. D2b (a radar gate) was dropped by the author.
- A smoke check that wrote a fixed day (Oct 12) for the Inara key check read a date from the next day on: today now.

## 2026-10-12 · Numbered stops on Here's schematic and the overlay's system panel
- **The first stop, kept on the server** (S30, the shared piece): POST `/api/plan/first` {id64, body | null}
  (`State.set_plan_first`: the system you are in only, else 409; meta `plan_first`, live-only, forgotten in another
  system), the payload's `plan_first`; every leaving summary carries its `id64`. The page's `planItems` (`planFirstFor`)
  and the overlay's `plan_items` (`first`) move that body's items to the front, so Here's to-do line, Now, the mapped
  call-out, the status report and the overlay give one order.
- **Here's schematic numbers the stops** (S30, page): ①②③ on each body in the suggested order of the system you are in
  (two on a body with mapping and bio; a stop under your credits-per-minute level tinted, as "skip?"), the to-do line
  numbered alike, a faint SVG path from the arrival star between the stops with rough leg times (the supercruise curve
  over the difference of the distances to the arrival star: not a route), legend rows. A tap on a number makes that body
  the first stop; "↺ order" puts the suggested order back.
- **The overlay's system panel numbers them too** (S30, overlay): `system_rows` lists the bodies you scanned by
  `plan_items` (with `codex_interesting` and the first stop), the numbers before each name (`stop_glyph`: ① to ⑳,
  then (21)), the rows by their first number; a body known to Spansh only stays unnumbered after them, the done ones
  last. Now's panel follows the first stop as well.

## 2026-10-12 · Your own runs in the guess's hover, and finding a missing species nearby
- **Your runs rank a genus's species** (S24, the hover only): `species_history(db)` counts your completed runs by genus,
  the body's class, atmosphere and 25 K band (your scan) and region (your visit), the region dropped under 5 such runs
  (`outrider.bio.SpeciesHistory`, `history_shape`, `history_label`; `State.species_history` cached on your completed
  runs). Here's bodies gain `bio_guess[].history`; the guess's hover (Here's, its "likely:" list, the body panel's
  "likely") adds "yours on bodies like this (Icy body, thin N2, 75–100 K, Inner Orion Spur): Informem 11 of 14, Acies
  3 of 14", the "likeliest by value" prefix kept. `--backtest` replays runs in time order across the journal folders
  and compares the two picks: on the author's journals both were right 20 of 32 times, so `HISTORY_PICK` stays off
  (`bio_pick`: the pick and the "up to" value unchanged).
- **The Exo-Biology checklist finds a missing species nearby** (S29): 🔍 on a species not found, 🔍 nearby on a colour
  not found and in the species' column; GET `/api/checklist/find?species=&colour=` (`State.checklist_find`,
  `Spansh.species_search`: the body search's landmark filter, by colour too, nearest first, 25 bodies, kept 10 minutes
  per place; `species_find_rows` checks every hit) lists them in the side panel with ly, gravity, the colours reported,
  ✓ visited, ☆ (its systems are located through `checklist_found`) and Copy. Not an AI tool. The colour filter was
  checked live (2 requests, saved in `tests/fixtures/spansh_landmarks.json`; `scripts/landmarks_probe.py` gains the
  case). Not built: 🎯 on its rows (S31's route "system" comes later) and the Geology checklist's half.

## 2026-10-12 · Geology new to your codex, finding green gas giants, and species other commanders reported
- **Geology ✦** (S22): new pure `outrider/codex_geo.py`, `entries_for(record)`: the SET of geology entries a landable
  body with geological signals could log, keyed on its volcanism's material and icy or not, verified on EDDN's codex
  traffic joined to the scans of the same bodies (284 entries on 81 bodies, every one inside the sets; rocky magma
  also logged the silicate vapour gas vent on 2 of its 6 bodies, so it is in that set). Unseen combinations (non-Ice
  water and CO2 entries, rocky ice bodies, SO2/silicate vapour Ice forms) give no mark. `codex_types_logged` takes the
  geology lines 1400000-1400499 (not the anomalies); Here's bodies gain `codex_geo`; the page's ✦ / ✪ (class `cxgeo`)
  in the name cell when any candidate is new in the region / anywhere, the new ones named in the title, its own legend
  row (the other codex rows now exclude `.cxgeo`), and the approach card names them (never spoken).
- **The Spansh landmarks probe** (P5): `scripts/landmarks_probe.py`, run on 2026-10-12, the answers trimmed into
  `tests/fixtures/spansh_landmarks.json`. Search results carry `landmarks` with the colour (`variant`), `earth_masses`,
  `radius` and the journal's temperature; dumps carry no landmarks; the landmark filter is `{landmarks: [{subtype}]}`;
  `surface_temperature` needs `{value, comparison: "<=>"}` ({min, max} is silently ignored); one system's bodies are the
  search out to 1 ly of it (a max of 0 and a system_name filter are ignored).
- **Find potential green gas giants** (S27): Search's Planets gains "Potential green gas giant" (`GGG_OPTION`): Local
  runs the ladder model over the cache, Spansh is asked for every giant of the classes the model can judge
  (`GGG_SPANSH`) and its answer checked by the model (`record_from_body_search` keeps `mass_em` and `radius_km`). GET
  `/api/ggg` (`State.nearest_ggg`, `ggg_nearest`: the cache only, on a worker, 500 ly by default), the AI tool
  `nearest_ggg` (in READ_ROUTES) and the voice's "nearest green gas giant" ("Nearest potential green gas giant: B 3 in
  …, 42 light years. A guess from the ladder model: check it in the system map.").
- **Species reported on a body** (S23): dumps lack landmarks, so the system you are in is asked once a day, only when
  its bodies have life (`State.maybe_reported`, a follow-up; `Spansh.reported_search`; `reported_life`), kept in the
  live-only table `spansh_reported`; Here's bodies gain `reported` and the bio cell shows "👥 Bacterium Vesicula -
  Mulberry 1.0M" beside the guess (titled "reported to Spansh by commanders' uploads"; a genus not named yet gets a line
  of its own, an analysed one none), with a legend row. Not built yet: the arrival brief, the FSS debrief and the
  overlay's body panel naming them.

## 2026-10-12 · What a sample run pays from sample 1, a Retry for the colour tables, and someone else scanning your unsold firsts
- **What a sample run pays, from sample 1** (S62): `sampling_summary` gains `value` (the species') and `factor` (×5 where
  nobody had set foot, `own_firsts.bio_x5`), apart, so nothing multiplies twice (the run elsewhere's `value` keeps its
  ×5 folded in). The on-body strip and Now's card: "🧬 Bacterium Aurasus · 1.0M (×5: 5.0M) · sample 1/3 · 500 m to go"
  (page `runPays`); the overlay's Now on-body rows and the body panel's runs under way the same (`overlay.run_pays`).
- **The colour tables missing** (S7): a failed first download no longer writes a bio_colours.json with no colours
  (judged by `colours_available()`, never by the file); `bio.update_colours` fetches only ExploData's table (one
  request; the colour builder shared with the rules update) and reloads the rules; POST `/api/bio/colours` (one at a
  time, not pc_only) runs it on a worker, then bumps `bio_rules_gen` and dirties the bases, so variant guesses show
  at once, not after a restart. A banner card while they are missing ("not downloaded", "Downloading…", "could not be
  downloaded (<why>)") with **Retry** (`retry:bio_colours`), and "colours unavailable: tables not downloaded · Retry" /
  "downloading…" / "failed: <why> · Retry" on the Exo-Biology checklist's line, the body panel's Bio section and Here's
  legend. The payload's `bio_rules` gains `colours` and `colours_job`. verify.sh points ExploData offline.
- **Someone else scanned your unsold firsts** (S6): the firsts watch's first sighting in a system (once per system: a
  report never goes away) is a `firsts_seen` moment {system, bodies, first_ts, reported_ts, value, today, speak}: a card
  and a notification each time, "👁 Someone else scanned your unsold Drojau LL-O b26-3 · 3 bodies reached Spansh 12
  days after you (your scan 15 days ago) · 14.2M cr at stake · see My firsts" (the notification opens My firsts),
  "N systems so far today" on a run of them; its own alerts row (Firsts scanned by others). Spoken at most once in 30
  minutes (`FIRSTS_SEEN_SAY_S`, decided on the server): speech key `firsts_seen` {system, value}, 50 lines in each list,
  the author's own among the business ones ("Heads up, someone else is scanning your unsold systems…"). The watch's
  INSERT now names its columns. Its real sighting in game is for the author to see.

## 2026-10-12 · Import your EDSM flight log from before your journals
- **Import your EDSM flight log from before your journals** (S67, Settings → Uploads, under the EDSM accounts; POST
  `/api/uploads/edsm/import` {action: start, stop, remove}): once, reading only, get-logs a week at a time back from the
  oldest journal arrival to the game's launch (`backfill.windows`, `readclient`'s paced POST reads, one every 10 s; EDSM
  asking to slow down waits 10 min), each week kept as it comes (table `edsm_log`, live-only), **Stop** and **Go on**
  from where it stopped (meta `edsm_import`; also after a restart), then the systems EDSM gave no position for looked up
  by name (here, Spansh, EDSM). After: "N visits from EDSM, <from> to <to> · **Remove them**" (your journals' visits
  untouched; then it can be imported again).
- **Which entries count is decided at every read** (`outrider/edsmlog.py`, the review's correction: no VIEW over visits,
  a second small query where visits are shown): before the oldest journal arrival and no journal arrival within 60 s,
  so a re-read or an older legacy folder moves it and journal data always wins; an index on its x, y, z; a timing test
  on 20,000 entries.
- **Where they show**: Nearby's and Search's visited marks, the target's verdict, Find ("visited 3× by your EDSM flight
  log", and `locate` for a bookmark of it), the route's hops, the boxel lists and sector grid, the Map (its hover says
  so), History's sessions "from EDSM" (no counts of what you did there) with a From EDSM line beside All time. **Never**
  firsts, sales, discoveries, the codex or your scans. Tested with fakes in get-logs' documented shape only: the live
  import is the author's.

## 2026-10-12 · Upload marks in the Log, and filling gaps in EDSM's flight log
- **Upload marks in the Log** (S68, the Log only): each line of the last 7 days shows what the uploads made of it,
  "✓ EDDN · ✓ EDSM", "⏳ EDSM" (waiting for the next jump or docking, or trying again), "⏸" (a refused key, an EDDN kind
  on hold, the upload switched off), "✗" (not taken), the reason in each mark's hover; per service the worst of the
  line's messages wins, the backfill's rows count as EDSM's, a line with no outbox row has no mark. log.py now splits
  lines on "\n" as the journal reader does (splitlines also broke on a bare "\r") and gives each row its byte offset,
  the outbox's source key (`uploads.line_marks`, a new index on the outbox's source).
- **"not sent"** beside "show noise" (while an upload is in use; kept in the Log's own filters): only the lines with a
  message waiting or refused, whatever the category boxes say (some "noise" goes to EDDN), GET `/api/log?unsent=1`.
- **Fill gaps in EDSM's flight log** (S47, Settings → Uploads; POST `/api/uploads/edsm/backfill`, `outrider/backfill.py`):
  **Check EDSM's log** (get-position, then get-logs a week at a time back from when EDSM was switched on here, meta
  `edsm_since`, "unknown" before this version) says where EDSM's log ends and fills From / To; **Preview** rebuilds the
  range's EDSM events from the live, legacy and archived journals, nothing sent (events by name, jumps, requests, time);
  **Send**, only for the previewed range and after a confirm, first checks EDSM's log is empty over the range (else
  nothing is queued), then queues the events as service `edsm_bf` (once per line) and sends one request every 10 s;
  **Stop**, and **Go on** after a refused key. EDSM's answers are read strictly (`edsm.backfill_answer`: 102 "older than
  what EDSM has" is not taken, counted apart from stored, already there, duplicates); a first request taken by none
  stops it. The one exception to the 7-day cap (DESIGN_NOTES). Tested with fakes only: the first live send, on a range
  of a jump or two, is the author's.

## 2026-10-12 · "Spansh unavailable", and Check buttons for the EDSM and Inara keys
- **The lookups' health** (G2, `outrider/health.py`'s `Health`): every request of the lookups' session (Spansh, EDSM,
  GitHub, EDAstro, Canonn) reports through an aiohttp TraceConfig, no call site touched; a failure counts only when
  that source answered nothing since the request began; "No internet connection" when two or more fail by DNS or no
  route with no answer between; forgotten after 30 minutes with nothing asked. The payload's `health` {down, offline}.
- **The Data tile says only "Spansh unavailable"** (S42, the author's answer: no secondary text), "EDSM unavailable",
  "No internet connection"; a failed search's status is that short form too, its error in the log (Show log). The page
  keys the tile off `health` (it matched "failed" in the status before: "Spansh unavailable" matched nothing, so the
  tile stayed green and the horizon claimed a complete list); "ok (3 Spansh body lookups failed …)" is shown plainly,
  not as a fault. A card on the banner when it lasts: Spansh or EDSM 10 minutes, no network or an address not found at
  once; it goes when they answer.
- **The EDSM and Inara read client** (G3, `outrider/readclient.py`): requests and parsers for EDSM's get-credits,
  get-position and get-logs and Inara's getCommanderProfile, keys in POST bodies only; EDSM's reads paced 2 s apart;
  `uploads.Gate`, an awaitable pace that Inara's sender (upload_loop's `gate`, its `min_gap` was a sleep) and its key
  Check share. verify.sh's offline server now also points Inara, these reads and Canonn at a closed port.
- **Check beside each EDSM and Inara key** (S45, Settings → Uploads; POST `/api/uploads/{edsm,inara}/check`): the typed
  key, else the stored one; "✓ 12:04 EDSM accepts CMDR … with this key", "✗ EDSM: 203 commander name or API key not
  found", "✓ Inara: CMDR … · profile", "Couldn't reach Inara: timeout". Reads only, one check per 10 s; a success with
  the stored key ends its hold through `clear_key_hold`. Never the key in an answer or the log. Built on the APIs'
  documented answers (`tests/fixtures/account_checks.json`): the live replies are for the author to check.

## 2026-10-12 · Planets sharing a centre are no curiosity
- Two planets circling a shared centre (a barycentre: "A 4 and A 5 orbit a shared centre") no longer count as a
  "planet pair" curiosity (the author: such pairs are common, the 🔭 mark and the curiosity alert were noise). The other
  curiosities stay (close orbits, moons of moons, ringed or heavy landables, fast spin, rare classes, green gas giants),
  and Here's tree still names the pairs.

## 2026-10-12 · Uploads: what each sent lately, Try again on a hold, and a card when one is down
- **Each service's last rounds, in memory** (G1, `uploads.Recent`): per service the last 50 sending rounds, sends in a
  row merged ("sent 37, 11:58–12:04") and the same failure repeated merged, with each failure's kind
  (`outrider/health.py`'s `classify`: dns, offline, refused, timeout, tls, http5xx, rate, http4xx, bad_answer) and its
  raw text; the outage under way (a raised or retry-only round starts it, a round the service answered ends it, a held
  key or a row settled here neither); what each did at start. `upload_loop`'s report carries the exception and the
  wait; EDSM's and Inara's non-200 raise `health.HttpError` (still a ConnectionError). `SchemaHold` gains `since`,
  `release` and `held_list`.
- **Settings → Uploads: Recent, holds, catch-up** (S16): under each service, always shown, its last 10 entries ("12:04
  sent 37 (11:58–12:04)", "11:58 ✗ no network: <the error> · trying again at 12:00"), "At start 09:14: 12 messages from
  while Outrider was off" / "nothing missed" / "EDMC was sending EDSM", and what is on hold with **Try again** (POST
  `/api/uploads/retry` {service, schema?}): a key EDSM or Inara refused is tried again now (a key hold is never
  retried by itself: a new key or the switch cleared it, and the sender saw that within 30 s; a wake now ends the
  sender's wait at once, Inara's 35 s still kept), and an EDDN kind on hold is released with its
  refusals (new messages only: the refused ones were dropped). A new key and Try again clear a hold through one helper,
  `State.clear_key_hold` (S45 will use it too). The hover-only "last error" is gone.
- **Upload outage alert** (S3, the author's default: a card and a notification only): an upload that is on, has
  messages waiting and has failed for 15 minutes puts a card on the notices banner (✕ or its recovery closes it; its
  Uploads button opens Settings → Uploads) and a desktop notification, once per outage: "EDDN unreachable (no network)
  for 15 min: 42 messages waiting, they drop after an hour (the oldest in 38 min)", "EDSM … kept until it answers",
  "Inara asked Outrider to slow down …". The first round the service answers: "EDDN sending again after 37 min: sending
  the 40 waiting (2 were over an hour old and dropped)". Never spoken: plain text, no speech.json key, a new alerts row
  `uploads` (notify only).
- The smoke test's voice lab leaves a stand-in `URL.revokeObjectURL` (jsdom has none): Save's revoke 10 s later failed
  whichever block was running then.

## 2026-10-12 · Material traders in the Nearest finder, from Materials and by voice
- **Spansh probed first** (S54, `scripts/trader_probe.py`, the answers in `tests/fixtures/spansh_traders.json`): a
  station's trader kind is Spansh's `material_trader` field (Raw, Manufactured, Encoded) and its station search filters
  on it; 7 of the galaxy's 1,639 traders (Colonia's outposts, a megaship) list the Material Trader service with no kind.
  No economy-based guess: those count for "any material trader" only.
- **The Nearest finder's Must have gains a material trader** (any, raw, manufactured, encoded): `dock.SERVICES` gains
  Trader, Raw, Manufactured, Encoded; `Spansh.dock_search` asks for a kind with the `material_trader` filter (near the
  author only 5 of the 50 nearest traders were raw), any kind with the service, and skips the carrier search (carriers
  never have one). Each row's Has says "⇄ raw" (or "⇄ trader" with no kind); the footer's hidden count names the trader.
- **Materials: "⇄ nearest raw trader"** on a limiting FSD-injection material and "⇄" beside each short material of a
  recipe (its category now in `/api/materials`' synthesis): the finder opens with that trader asked for, the saved
  filters untouched (`NR.over`); Plot here from there brings Plot Route forward.
- **Voice and AI:** "nearest material trader", "nearest raw material trader" (manufactured, encoded, "data trader")
  in `resources/ask.json`; the answer says the kind ("Nearest raw material trader: Broglie Terminal, an ocellus
  starport, 11 light years away, in 61 Cygni."; "a"/"an" now by the word). The AI's `nearest_dock` tool takes the
  four new needs.

## 2026-10-12 · The carrier's own jumps check the tritium, and the synthesis recipes you have made
- **A journal re-read (PARSER_VERSION 50)**, the plan's one: your carrier's movements and tritium deposits
  (CarrierJumpRequest, CarrierJumpCancelled, CarrierLocation, CarrierJump by its MarketID, CarrierDepositFuel) are now
  kept in `cargo_events`, each Synthesis's recipe in the materials state, and the CarrierCrewServices lines stored
  since the last update without a re-read come back from the older journals too. A squadron's carrier is never kept.
- **The tritium formula checked by your carrier's own jumps** (S13 B): `carrier_burns` measures each jump booked and
  confirmed with one depot reading on each side (CarrierStats' FuelLevel, or a deposit's Total − Amount before it and
  Total after) and no other jump between, the mass as it left (the stats plus your own moves since), distances from
  the CarrierJumps' StarPos else wherever Outrider knows the system; `burn_factor` is the median of the last 12
  burned ÷ formula, from 3 on, held to 0.8–1.2. It scales the trip to you, a booked jump's burn and the tile's jumps
  of all your tritium; the hover says "checked against your carrier's last 12 jumps: no correction needed" (or the
  scale, and what it measured when held). On the author's journals 193 of 214 measured jumps are exact and the last
  12 all are. Jumps over 500 ly (a move missed between) are dropped; tritium others donate reads low (said too).
- **Synthesis recipes learned, and folded into groups** (S15): the Materials tab keeps the FSD injections' three
  cards open and folds the rest into one line each, "Ship upkeep ▸ AFMU refill B×4 S×1 P×0 · Heat sink B×12 S×0 P×0
  · Life support ×7 · Limpets ×3", "SRV ▸ …" and "Other recipes you have made ▸ Ammo Basic ×2", opened on a click and
  remembered per device (`synthOpen`). New recipes: AFMU refill and heat sink (three grades each) and life support,
  from EDEngineer's and EDDiscovery's tables (they agree), each with its journal name. A recipe you have made is ✓
  "checked against your synthesis on <date> (made 3×)", your materials winning where the published recipe differs;
  one the table lacks is listed under Other instead of dropped. The oldest journals' `{name: count}` Materials read too.

## 2026-10-12 · The carrier's trip to you, its balance in weeks of upkeep, suspended services, and your carrier as a place to sell
- **The carrier's stats folded whole** (the fold's `finance` and `crew`): CarrierStats' Finance (balance, reserve,
  available) and Crew (each role on, suspended or not installed), then each `CarrierCrewServices` (a service installed,
  removed, paused or resumed; now kept in `cargo_events` and worded in the Log) until the next CarrierStats. No re-read:
  every CarrierStats was already stored whole; a CarrierCrewServices before this update comes with the next re-read.
- **Balance and weeks of upkeep** (S61): "balance 1.33B · ~96 weeks of upkeep" on the Carrier tile, amber under 4
  weeks, "as of" the date when the stats are over a day old. The journal has no upkeep figure: the week's upkeep is the
  core (5M) and each service's rate, active or suspended (`CARRIER_UPKEEP`), the community wiki's **published rates**,
  not yet checked against the game's Finance screen; the title says so. Weeks are the balance's (upkeep is drawn from
  it; the reserve stays put).
- **Suspended services in red** (S55 B): "UC suspended", "Redemption office suspended". UC and Vista on or off come
  from the newer of the carrier's crew and your last docking there (a suspended service is not in its services).
- **Your carrier among the nearest places to sell** (S55 A): the journal's carrier (where it is now) instead of
  Spansh's report of your callsign, in the Universal Cartographics list while UC is on and Vista's while Vista is, with
  "≈ 3 carrier jumps to you"; not while suspended, never once decommissioned; there even before Spansh answers. The
  Nearest finder's own row drops a suspended UC or Vista too.
- **The tritium for the trip to you** (S13 A): "it → you ≈ 3 carrier jumps · ≈ 340 t tritium · depot 200 t: 140 t
  short" (red; amber with "enough after topping up" when a confirmed tritium line in the hold covers it): equal legs of
  up to 500 ly, each burned by the fitted formula with the depot lighter each leg (`carrier_trip`; its `k` waits for
  S13 B's history). A booked jump: "(432 ly jump ≈ 96 t; depot after ≈ 572 t; then … ly from you)".

## 2026-10-12 · History's sold and ✗, how fresh a confirmed count is, one shipload, Recount refuses typos
- **History: sold and ✗** (S63): a "sold" column after 🧬 (what Universal Cartographics and Vista Genomics paid in that
  session, every sale; the all-time and "since your last sale" rows too, the career row from the game's exploration
  and organic data profits), and ✗ in a session's cell for a death, its hover each one with what it was ("died 14:32:
  ship lost (rebuy)", "the ship survived (recover)"; a death with no Resurrect yet counts as a loss, as everywhere);
  the all-time row's ✗ says the deaths and the ships lost. `COUNT_QUERIES` gain `sold`, `died`, `lost`
  (`SHIP_LOSS_SQL`); each session carries `deaths`. A Resurrect now has History ask again (it waited for the next jump
  or sale, so the ✗ said "ship lost" after a recover).
- **How fresh "confirmed" is** (S58): a sell order's count says its age from a day on ("✓ 9 d"), amber after a week,
  and then the carrier's heading says "Sell-order counts read 12 days ago: open your carrier's commodity market while
  docked there to refresh them".
- **One shipload or all of it** (S56): a Sell / Buy lookup for more than the ship's hold (its capacity, not what is
  free) switches between "All 16,000 t" and "One shipload 720 t" ("≈ 23 shiploads for all of it"), asking Spansh for
  that much: "Sell 720 t of 16,000 t". Not shown before a Loadout gives the hold. Page only.
- **Recount refuses typos** (S57): a name added in Recount must be one your journal has given or one Spansh lists (the
  copy the lookup keeps; fetched once by Recount when there is none), stored by Spansh's spelling, Low Temperature
  Diamonds and Void Opal by the journal's id; anything else is refused with up to three close names, "Not a commodity:
  “Titanum”. Did you mean: [Titanium] [Tritium]", a click putting one in the row. A typo used to make a line of its own
  that nothing would ever move.

## 2026-10-12 · Progress while reading journals, and Outrider as a service
- **The page answers while Outrider starts** (S9): a small starting app takes the port before the database is opened,
  so a long first start or journal re-read shows "ED Outrider is starting · Reading your journals: March 2024, 41%"
  (bytes read of those to read, the month from the file's name), "Backing up your database before reading every
  journal again" as its own phase, why it re-reads, and Show log; it reloads into the real page when that is ready.
  GET `/api/starting` (the real app answers "ready"); `/api/version` keeps its shape; every other `/api/` answers 503
  `{error, code: "starting"}`: an open page says "starting · 41%" (and "Restarting… Reading your journals…") instead of
  "not connected", and no "Lost contact" during a long re-read. A device on the network that is not signed in learns only
  that it is starting. The import runs one file at a time on the event loop (`import_journals`,
  `Journals.import_steps`/`scan_steps`), the backup on a worker (`open_db(reset=False)`, `reread_due`,
  `reset_journal_data`); legacy folders are committed per file too. A SIGTERM during the start ends between two files
  (each read whole and committed) or after the backup, instead of raising mid-file. verify.sh waits for `/api/starting`
  "ready"; Docker's health check is healthy during the import (start period 2 minutes, was 30).
- **Start with this computer** (S70): `./launch_outrider.sh --install-service` (or `launch_outrider.bat`), or Settings →
  Server → Start with this computer from the browser on that PC: on Linux a systemd user service
  (`~/.config/systemd/user/ed-outrider.service`, running the launcher with the arguments given, at login; on a server
  with the user's systemd), on Windows `ED Outrider.cmd` in the Startup folder (the .bat, minimised). Enabled, not
  started (this Outrider holds the port: the words say how to switch). `--uninstall-service` and Remove take it away.
  Refused with the reason in Docker (compose's restart policy is the service) and on macOS. New `outrider/service.py`.
- **Restart and the service agree**: the unit sets `OUTRIDER_SERVICE=systemd`; Restart then exits 75 and the unit's
  `RestartForceExitStatus=75` starts it again (`Restart=on-failure` for a crash; `TimeoutStopSec=330`, over the
  backup Outrider waits for at shutdown). Tests and verify.sh write the unit into a scratch folder and never run
  systemctl.

## 2026-10-12 · Restart from Settings, and whether auto honk can work here
- **Restart** (S10): Settings → Server's top row ("Outrider <version> · Show log · Restart"), "Saved 2 settings. Restart
  now", and the "Outrider has been updated: restart it" line. A confirm, then POST `/api/restart`: the usual clean stop
  (a backup running finishes first, "Restarting… (finishing a backup first)"), then Outrider starts again and every
  window reconnects (the page waits for a new `run_id`). From any device the page answers, with the guard of POST
  `/api/config` (the author's decision): never cross-site, signed in from another device when a password is set. How:
  `launch_outrider.sh` now exports `OUTRIDER_LAUNCHER` and Outrider execs it in its own place (same PID, terminal and
  Ctrl-C; the setup runs again after a `git pull`); without it, ed_outrider.py again with the same arguments;
  `launch_outrider.bat` sets it too and loops when Outrider exits 75 (Windows has no real exec); Docker exits 75 and
  compose's `restart: unless-stopped` starts it again (refused in its first 15 s: Docker skips a container that ran
  under 10 s). Never `--rescan` again. A process that is not ed_outrider.py itself (verify.sh's `python -`, the tests)
  cannot restart: the button is greyed out and says why. The payload's `restart` {can, how, why, note, restarting}.
- **Is auto honk ready?** (S69): Settings → Auto honk says it at the top: "Ready: evdev ✓ · /dev/uinput ✓ · /dev/uinput
  writable ✓ · Primary Fire: Left Alt + K ✓", or what is missing with the fix and its commands (Copy): `sudo modprobe
  uinput` (and at every boot), a udev `uaccess` rule for `/dev/uinput` (the input group only mentioned), evdev in the
  .venv, a keyboard binding for Primary Fire; "off (--simulate)" when it is. It only looks: no virtual keyboard is
  created, nothing pressed (`outrider.honk.readiness`). GET `/api/autohonk/check`, game-PC only (409 `not_game_pc` on a
  server).

## 2026-10-12 · A backup before every journal re-read, Backups in Settings, the first run with no journals
- **A backup before a journal re-read** (S4): when an update (or `--rescan`) makes Outrider read every journal again, the
  database is backed up first, before any row is cleared, even with `backup_every_days = 0` (the one destructive step
  Outrider takes by itself). The zip is `outrider-<db>-<stamp>Z-pre-reread.zip` (the tag after the stamp: it sorts
  and rotates with the others; `--restore`, `--list-backups` and the leftover sweep know it); the Data tile's backup
  line is not changed by it. A failed one does not stop the re-read: the terminal and the banner say so. More than
  half the journal files the database was read from gone (an uninstall under Steam/Proton): the banner says so, with
  `--legacy <backups>/journals`. `write_backup` is lifted out of `make_backup`; `open_db(before_reset=)` runs it.
- **Settings → Server → Backups** (S44): the zips, newest first, size and time, "before a re-read" from the name, and
  "automatic" or "by hand" for the latest only (a zip's name does not say it; the others say nothing); Back up now;
  the command that restores the one you click for this install, with Copy: `./launch_outrider.sh --restore NAME`,
  `launch_outrider.bat --restore NAME` (with `--config`/`--db` when Outrider was started with them), or for Docker
  `docker compose stop && docker compose run --rm outrider --restore NAME && docker compose up -d`. No restore button
  (Outrider must be stopped). GET `/api/backups`. The install guide's Backups section and the Data tile's title give
  the working commands (they said `python3 ed_outrider.py --restore`).
- **`--restore` refuses while Outrider is running, from any port or container** (S44): a running Outrider holds an OS
  lock on `<db>.lock` beside the database for its whole run (gone with the process, however it ends); the port check
  could not see a Docker container. A second Outrider started on the same database is said on the banner.
- **A first run with no journals** (S43): the Data tile says "no journals found · set the journal folder", which opens
  Settings → Server with `[journals] live` focused (the banner's Journal folders button too); in Docker instead "no
  journals in /journals: is the game PC's journal folder mounted? (JOURNALS in .env)". A banner says the same while
  the folder holds no journal and goes with the first one read. With journals but no jump yet the views say "No FSD
  jump yet: the page fills in after your first jump". The payload's `freshness` carries `missing` and `install`.

## 2026-10-12 · Show log, and start-up problems on a banner
- **Show log** (S5b): Settings → Server's top row says "Outrider <version> · Show log". The log is what Outrider prints
  in its terminal, kept from the first line (its last 2,000 lines, GET `/api/serverlog`, behind the sign-in), in a
  dialog that follows along while open, the error stream in amber, with Copy. The same lines go to `outrider.log` beside
  the database (rotated at 2 MB to `outrider.log.1`). New `outrider/serverlog.py`: a tee on stdout/stderr for the
  server's run only, put back when it ends. The overlay window's own output is now piped into Outrider's ("overlay
  window: …"), so its errors are in the log too.
- **No secrets in it:** the config warning for an unquoted `[server] password` printed the number itself (and GET
  `/api/config` replayed it): it no longer does. The log also hides the passwords, the AI key and the EDSM / Inara keys
  wherever they would appear.
- **The notices banner** (S5a): what Outrider finds wrong at start (a journal folder not found, the config file's
  problems, the spoken lines file's, no password while listening on the network, NFS caching, the overlay's address
  taken) is now a line under the header in every window and on the tablet, with a button where one helps (Server
  settings, Show log), as well as in the terminal. ✕ hides it everywhere until Outrider restarts or the message changes
  (the author's choice). New `outrider/notices.py`, the payload's `notices`, POST `/api/notices/dismiss`.

## 2026-10-12 · Less work every second: journals over a share, the carrier, what's left here
- **Journal files over a network share** (S18): every second Outrider still lists the journal folder (a new journal is
  read at once) but checks the size of only the newest two files and those still changing; a file whose size stayed
  the same three checks in a row is settled, and every file is checked once a minute (a sync tool adding to an older
  journal is read within the minute). A journal cut without its last newline settles too (it used to be re-read every
  second); an unreadable one never does. A rolled-back tick forgets what settled. The install guide's share section
  says so.
- **The carrier's hold is folded again only when its history changes** (S66): its own events and Market.json reads
  (`carrier_version`), no longer every canister scooped or ton bought into the ship's hold.
- **"What's left here" is worked out once** (S17): `leaving_summary`, asked for on every poll while a target is set
  (and by the moments, Here and the FSS check), is cached per system until the journal writes something it reads
  (`Journals.data_seq`: scans, codex, deaths, both sales tables; the seven `dirty.add` sites are now `mark()`), the
  system's place changes, or the exobiology rules are updated (`State.bio_rules_gen`, new). Each caller gets its own
  copy.

## 2026-10-12 · 🎯 brings the game to the front itself
- Every auto-target run (🎯, Target next, Test now, the automatic one after a supercharge, the co-pilot button's) now
  finds Elite's window, brings it to the front (`wmctrl -i -a` on Linux, the game under X11 or XWayland; Windows
  untried) and runs at once: no 5 s countdown to click back into the game (S74, the author's ask). The window is
  matched by the game's whole title, "Elite - Dangerous (CLIENT)", never a browser tab about the game.
- No key is pressed unless Elite's window is the active one, checked before every key, the map's close on the way
  out included: click into the browser mid-way and the run stops at once. When the game does not come forward, the
  page's runs count down 5 s after all with "Elite is not the active window: click into the game" (the button and
  the box follow); the automatic run and the co-pilot's say so and press nothing.
- Where it cannot see the game's window (no wmctrl or xprop, the game as a native Wayland window) it does as before:
  the countdown, keys unchecked. The Plot Route tab's auto-target box says whether it brings the game forward or why
  not; the start-up log too. New `outrider/game_window.py`; the overlay's tracker takes a title match.

## 2026-10-12 · Co-pilot targets the boxel, Nearby rows open, header tiles tidied
- The co-pilot button's tap targets the Next of the boxel being explored too, as 🎯 beside it does (the author's ask
  while testing boxels; S76). The order: the survey / trade route's next; the Highway's while you are on it (at a route
  system); the boxel's Next; the Highway's off the route (its closest system). A Highway route you left for a detour into
  a boxel no longer hides the boxel. The same run as 🎯: a name the galaxy map cannot find marks the boxel's probable
  end. With nothing to target, the voice gives the last reason found ("Drojau TF-H c13 is complete"). DESIGN_NOTES has
  the order.
- Nearby (and the Overview's Nearby pane): a click anywhere on a row shows that system beside the list, not only on its
  bodies cell; again closes it (S73). The name still copies, ☆ still bookmarks, a drag that selects text opens nothing.
  The row lights up under the mouse. The tablet is unchanged (a tap opens the row's sheet).
- Header tiles (S75): the jump range moved to the Commander tile, right under the ship ("max jump 83.0 ly · 75.9
  laden", and the boosted reach). "from X (Y ly)" sits beside the system's name in the Where tile, in the lines'
  smaller muted font, without "came". "nearest known unvisited" left the Where tile; Now and the voice keep it.

## 2026-10-12 · "In-Game Route:"
- The line with the game's own route (the one plotted in the galaxy map, NavRoute.json: jumps, light years, next scoop
  and the star chips) said only "Route:", easy to take for Outrider's route on the "Next:" line just below it (the
  author's 6-jump plot showed "Route: 3 jumps": an older in-game route). It now says **"In-Game Route:"** (the
  author's wording). The two differ until 🎯 targets Outrider's next stop, which plots the game's route there.

## 2026-10-12 · Sector names said by rule
- The voice now says procedural sector names the same natural way everywhere (the author's ask): Smojooe as
  "SMOH-joo", Flyeia Hypa as "fligh-AY-uh HIGH-puh", Synuefe as "sigh-NOO-fee", not espeak's guesses. The game builds
  them from a fixed set of pieces, so they are read by rule, not listed: every sector in the galaxy is covered. A
  word splits into syllables at its consonant and vowel clusters, each said as English would; stress on the first of
  two syllables, else the second last. The phonemes are written directly for British and American voices.
- Only words right before a system's code (Smojooe AR-E b25-8) are read this way; hand-named sectors (Col 285
  Sector, Hyades Sector), the Dark Regions and an English word leading the name ("Leaving Smojooe ...") are left as
  they were. Your own word in How is it said wins over the rule.
- The voice lab's How is it said box: **▶ as a sector**, and the sectors you have visited most listed below it (▶ to
  hear one, a click on a word to change it). GET /api/pronounce gives them as `sectors`.
- Tested on every sector seen on EDDN in two days of all apps' traffic plus the author's journals (1,612 names,
  `tests/fixtures/sector_names.txt`): each reads, with one stress and only known sounds; every sound is in the
  installed Piper voices' phoneme maps, and a voice added later whose map lacks one says that word as plain text
  (Piper would drop the sound).

## 2026-10-12 · Babylon 5 - Shadows theme
- An eleventh theme for the tablet, the desktop page (Settings → Display) and the overlay's panels (the author's ask):
  **Babylon 5 - Shadows**, the Shadows' ships evoked, not copied. Black with a purple floor, dark purple panels, light
  grey text, the emblem's violet for what is chosen and pale lilac for headings; thorn-cut corners (a long slant at top
  right and bottom left), a faint purple shadow; the overlay's panels cut-cornered. Metal Mania (spiked serifs, the
  author asked for a jagged face) for headings, newly shipped with its SIL OFL licence, and Exo 2 for text; your own
  heading font as `data/fonts/shadow-display.ttf`.
- Its emblem under the tablet's page list: an AI-generated image the author made, loosely based on the Shadows' ships,
  recoloured from black to the theme's purples so it shows on a dark page, credited in `static/emblems/CREDITS.txt`.

## 2026-10-12 · The link pill says states only
- The link pill counted seconds ("linked · 2 s", "stale · 48 s", "no link · retrying since 14:02"); it now says only
  the state (the author's ask): "linked", "linked · no game" when Outrider answers but the game is not running, and
  "unlinked · retrying" (amber after 30 s without an answer, red once the link is down). The tablet's pill says the
  same.

## 2026-10-12 · Version 2026.10.22
- Boxel exploration (the list, Next with 🎯, complete/done, keep, auto-target, skip fully scanned, known counts, boxels
  nearby, the sector map), rare finds (rare stars, phenomena, surface sites, signals worth a detour, potential green
  gas giants, ✦ body types new to your codex, rarer curiosities), Inara uploads, the voice lab in the page with
  speakers, More voices and the pronunciation table, the Vorlon theme, Now's next-stop line, the carrier 🎯, and the
  review fixes. What's new has its section. PARSER_VERSION 49: the first start re-reads the journals once.

## 2026-10-12 · Docs sweep, screenshots in the Elite theme
- Every guide page, the README and the developer notes checked against the code and the work since 2026.10.21: Inara,
  the carrier's 🎯, boxel mode and its sector map, the rare finds, the ✦ body-type marks, the voice lab's speakers and
  How is it said, every config key with its default in Settings, and stale details fixed.
- Every page screenshot retaken in the Elite theme (the overlay's too), the tablet in its LCARS; Overview and Here
  show a system with work left; new: Boxel mode and its sector map in the guide.

## 2026-10-12 · ✦ on body types: your scans count as logged; pronunciations backed up
- The ✦ / ✪ on star and planet types marked nearly every body in the regions explored before the journals kept (the
  author's go back to May 2023, their codex further: Inner Orion Spur held 2 body-type codex lines, so 42 types read as
  new; found in the release screenshots). The game logs a type only the first time you scan one in a region (109 of the
  author's 111 such lines say new), so a type you have scanned there without a line was logged before: your own scans
  (not a nav beacon's) now count. Read once (25,874 scans in 0.2 s), then only the new ones.
- Your own pronunciations (`data/pronounce.json`, the voice lab's How is it said) go into the dated backups with your
  lines and the config (found by the docs sweep).

## 2026-10-12 · Carrier tritium: reserved space weighs nothing
- The carrier's tritium jumps counted the space a buy order reserves as cargo, so with a buy order open each jump read
  heavier than it is (found by the Fable review of the suggestion plan, checked on the author's journals). The game's
  own JumpRangeCurr in CarrierStats matches the fitted formula on every line under 500 ly only with the reserved space
  left out: 4,500 t reserved, 198.6 ly, where counting it gave 180.7. `used` is now TotalCapacity − FreeSpace −
  CargoSpaceReserved. No re-read needed (the fold is worked out from the stored events).

## 2026-10-12 · How the voice says the exobiology names
- Piper's English voices read the Latin of the exobiology names by espeak's English rules and mangled most of them
  ("Fonticulua", "Osseus", "Clypeus Lacrimam"; a Fable suggestion the author picked). `resources/pronounce.json` now
  says the 120 genus and species words in a respelling ("fon-TIK-yoo-loo-uh", the stressed syllable in capitals), a
  first pass for the author's ears; `outrider/pronounce.py` turns each into Piper's raw phonemes in the voice's own
  accent (each syllable through Piper's own espeak, under its lock) and swaps whole words in a line for them. Your own
  `data/pronounce.json` goes on top: the voice lab's new **How is it said** box tries a respelling (▶ this way), saves
  it, or takes yours out (GET/POST `/api/pronounce`). The phrase cache's key carries the table's version, so a change
  is heard at once. verify.sh's scratch server writes its own file, never yours.

## 2026-10-12 · Boxels: the sector map
- Boxels nearby listed the nearest three per mass code, with no picture of progress across a sector (a Fable
  suggestion the author picked). Boxel mode now has a **Sector map**: the sector you are in as a grid of one mass
  code's boxels (b to h), one Y layer at a time with ▲ ▼: visited, ✓ complete, done, Spansh knows, you and the kept
  boxel marked; a tap explores that boxel. All local (your visits, the done and end marks, the Spansh lists asked for):
  GET `/api/boxel/sector?mc=d&layer=5`. A cell's tooltip is made on hover (a b grid has 4,096 cells).

## 2026-10-12 · ✦ on star and planet types new to your codex
- ✦ / ✪ marked only species new to your codex, though the codex logs every star and planet type once per region too (a
  Fable suggestion the author picked; shown only, not spoken). `outrider/codex_bodies.py` says which codex entry a
  body's type logs, by EntryID: the localised names are ambiguous for planets ("Terraformable", "Standard gas giant").
  The table is from the author's journals and EDDN's codex traffic (giants by luminosity class III, supergiants by I,
  a solid planet's "Ter" entries the ones with an atmosphere). Here marks the body (✦ not in this region's codex, ✪ in
  none), Nearby's row gets one tag naming each type, Spansh's bodies included; the payload carries your codex's types
  per region so the marks are always current.

## 2026-10-12 · Now says where the next jump goes
- Now (and the overlay's Now panel) never said where the next jump goes: the route's next stop showed only in the
  strip on Overview, Nearby and Here, a kept boxel's Next only in Boxel mode (a Fable suggestion the author picked).
  Both now sit under the target: "🛣 Next: Stop 38 · 4.2 ly · 38 of 120 · refuel in 3 jumps" (or the survey route's)
  and "▦ Boxel: next Smojooe KL-P d5-41 · to try", with 🎯 on the page. The payload carries the active boxel's Next,
  worked out only when the boxel's key changes; the overlay shows a kept boxel's only, and the unfinished route plotted
  last.

## 2026-10-12 · Boxels: how much of a known system was found
- A boxel row Spansh knows said only "known", and "skip systems someone has visited" passed over all of them, though
  most were only honked or partly scanned in passing and keep their bodies' first discoveries (a Fable suggestion the
  author picked). The Spansh request the boxel already makes returns each system's bodies: the row now says "known · 3
  of 14 bodies", "known · honked only" or "known · all 38 bodies", and the switch, now **skip systems already fully
  scanned**, passes over only the ones with every body reported. (A list fetched before keeps Next on them until it is
  asked again, within a day.)

## 2026-10-12 · Review fixes: the overnight check
A Fable check of 2cb1e60..9af0984 (and the EDDN listener tool): 8 bugs in the repository, all fixed with a test each.
- Voice: picking the voice already speaking (Settings or the lab's Use this voice) answered ok but did nothing: it was
  neither remembered nor did it stop a background switch to the configured voice. A voice named is always used now.
- Voice lab: a voice not in use opened on speaker #0, and Use this voice then overwrote the speaker kept for it; it
  opens on its kept speaker now. A lab download ending no longer wipes a switch's or another download's status.
- Boxels: a stale end mark (a hiccup, then that number found) blocked every later end and made the recommendations call
  the boxel complete; one place now says a boxel's end. An empty boxel (-0 not found) is complete ("✓ empty").
- Boxel mode refetched its list and the recommendations on every journal line; now on a jump, a scan here, or a change.
- Overview: bringing your body into view scrolled the whole window when the list was short; only the list moves now.
- EDDN: a catch-up's companion-file wait was timed like a live one, re-read the file on every catch-up line and logged
  a misleading "not written"; a catch-up's wait ends after its lines again, quietly.

## 2026-10-12 · Potential green gas giants
- The community's seven-layer ladder model (CMDR Regza, from a hint by Dr. K. Ross and CMDR Arcanic; published by
  Canonn on 2026-10-05) predicts which gas giants render green from the journal's own temperature, mass and radius
  (`outrider/ggg.py`, written from the published rules: the same verdict as Canonn's code on 21,747 giants). Not a
  curiosity, where it would blend in (the author): its own **green planet with "?"** on the body in Here and on the
  system's row in Nearby (from Spansh's records of other people's scans too, which keep the journal's temperature:
  a system to go to), a **Now line**, and a **"Potential green gas giant"** alert when your own scan fits, with its
  own lines in every personality (`ggg`, 50 a list) and its own switch under Discoveries. A codex entry confirms one:
  the "?" goes. Class II, V and helium giants, and the model's "nudged" temperatures, cannot be predicted: nothing said.

## 2026-10-12 · Boxels: skip the systems someone has visited
- Next (and the auto-target on arrival) went to the lowest number you had not visited, including ones Spansh knows
  (someone has been there). An opt-in, **skip systems someone has visited** (meta `boxel_skip_known`, off by default),
  passes over those for first discoveries only; the list dims them while it is on (the author agreed).

## 2026-10-11 · Boxels: complete and done
- A boxel is **✓ complete** by itself once its end is known (a name the galaxy map could not find) and you have visited
  every system below it; **✓ Done with this boxel** marks one finished, complete or not (the author agreed; meta
  `boxel_done`, undo any time). Either way Next (and the auto-target on arrival) offers nothing more, a kept boxel is
  let go, and it leaves the recommendations: the next nearest of its kind takes its place (12 looked through per kind,
  3 shown), and "done or complete nearby" lists the ones left out.

## 2026-10-11 · Boxel mode: the switch beside This system, the highest known number
- The Standard / Boxel switch sits on the Overview's own bar, left of "This system" (back in Nearby's options on the
  Nearby tab); the warning that Outrider cannot know a boxel's size sits on the "you have visited · Spansh knows" line
  (the author).
- The boxel's head and every recommended boxel show the **highest known number** (yours or Spansh's, whichever is
  higher: the author). Spansh is asked about the recommended boxels it has no list of yet, one after another in the
  background, kept a day like the explored one's (meta `boxel_spansh` now keeps 60 boxels).

## 2026-10-11 · Babylon 5 - Vorlon theme
- A tenth theme for the tablet, the desktop page (Settings → Display) and the overlay's panels (the author's ask):
  **Babylon 5 - Vorlon**, the Vorlon Empire's living ships evoked, not copied. Deep sea-green dark, the emblem's sea
  greens and golden tendrils, a pale glowing core; soft arcs like the emblem's crescents and a faint inner glow.
  Marcellus and Inter (already shipped, SIL OFL); your own heading font as `data/fonts/vorlon-display.ttf`.
- Its emblem under the tablet's page list: the Vorlon Empire's, a public-domain fan redrawing by Blind Wolf on the
  Babylon 5 Wiki (Category:User-created public domain images, as the Narn, Minbari and Centauri ones), credited in
  `static/emblems/CREDITS.txt`.

## 2026-10-11 · Boxel exploration
- **Nearby → Boxel** (the author's idea; a switch in Nearby's bar, shared by the Overview pane and the Nearby tab, per
  browser) lists the boxel you are in by number: your visits with your scans (Nearby's cells), Spansh's known systems
  (asked automatically with an exact list of the boxel's names, 300 a request, kept a day), the numbers to try, the
  warning that Outrider cannot know a boxel's size. **Next** and every row's 🎯 auto-target by number (POST
  `/api/highway/target` {route: "boxel", index}); a name the galaxy map cannot find above every known number marks
  "probably the end" (meta `boxel_ends`, **retry**). **📌 Keep this boxel**; opt-in **auto-target the next on arrival**
  (meta `boxel_auto`, a kept boxel only). **Boxels nearby**: the nearest of each mass code in sectors you have been to,
  what each tends to hold and your own figures per code; **Explore this boxel**.
- `outrider/boxel.py` computes a boxel and any of its systems' id64 from a known position: checked against the author's
  journals, 2,763 of 2,763 standard-sector systems (hand-authored sectors differ: list only).

## 2026-10-11 · More voices in columns
- More voices' rows did not line up: ▶ sample sat wherever the text before it ended (the author's screenshot). Each row
  is a grid of four columns now (name, quality/speakers/size, ▶ sample, the action), with an empty cell where a voice
  has no sample.

## 2026-10-11 · More voices: download first, then try
- More voices' "Download and use" switched Outrider to a voice before you had heard it, and a downloaded voice only
  showed in the lab's list after reopening it (the author agreed to change both). Now **Download** fetches it without
  switching (POST `/api/voices/download`, `Speaker.fetch`; the payload's `tts.fetching` / `tts.fetch_failed`), and when it
  is here the lab picks it in its voice list, ready for ▶ Hear it and Use this voice. A voice already installed is
  **Select** (picked in the list). The lab's voice list follows new voices while it is open.

## 2026-10-11 · More voices: sorted, and Piper's samples
- More voices (in the voice lab) sorts by name, quality (best first) or size either way (the author; per browser), and
  each voice has **▶ sample**: Piper's own recording of it from the project's samples site (rhasspy.github.io/
  piper-samples, its first speaker), heard before downloading anything. The catalogue gains `sample` (`SAMPLE_URL`);
  25 voices picked at random from all 176, plus three newer ones, all had theirs. It plays through the lab's player:
  ■ Stop stops it.

## 2026-10-11 · The voice lab moves into the page, with speakers
- **🎙 Voice lab** in ⚙ Settings → Voice replaces `voice_lab.py` (a separate Tk window, now removed with its tests;
  the author's ask). It plays in the browser you are using, from the server's Piper (`api/say`), so it works on a
  Docker server and the tablet and needs no python3-tk: try a voice and speed without switching (**▶ Hear it**), **Use
  this voice**; More voices (download any of Piper's) moved into it; any alert's lines in any personality (**▶ Random
  line**, **▶ Audition**: eight key alerts, `AUDITION_KEYS` kept equal to `outrider.speech.AUDITION` by a test), **✂
  Cut this line**; your own words (**▶ Speak**, **⬇ Save WAV**). It never goes through the alert queue, hush or "play
  on this PC".
- **Speakers**: a Piper voice trained on many people (`en_GB-vctk-medium` 109, `en_US-libritts_r-medium` ~900) now
  speaks as the one picked for it; Outrider always used the first. The lab steps through them (‹ › 🎲, each played);
  Settings → Voice shows the voice in use's speaker beside it. Each voice keeps its own (meta `voice_speakers`, over
  restarts), personality voices too. `Speaker.voice_speakers` reads the names from the voice's `.onnx.json`; POST
  `/api/voice` takes `{voice, speaker}` (or `{speaker}` alone); GET `/api/voices/speakers?voice=`; `/api/say` (and
  play, prefetch) take `speaker`; the payload's `tts` gains `speaker`, `speakers` (a count) and `speaker_name`.

## 2026-10-11 · EDDN: a carrier's market written late still goes
- Docked at the carrier and opened the market: no commodity message; the second visit's went (the author). The EDDN
  builder is right (a replay of the journal sends it); the file was not: Outrider took Market.json only when stamped
  within 5 s of the Market line and gave up after 10 s, and the game seems to write a carrier's first market of a docking
  late (the data comes from its server). A companion file stamped up to 30 s after its line now counts (`FILE_LATE_S`),
  the live wait lasts 35 s (`FILE_WAIT_S`; a catch-up keeps its line count), and a wait that ends unsent says so on the
  console with what the file held ("EDDN: Market.json was not written for the line of ... (the file says ...)"), so
  the next miss can be told apart.

## 2026-10-11 · 🎯 beside your carrier; Here's heading stands down for the map
- The Carrier tile (and the folded tiles line) has a 🎯 beside your carrier's system when it is elsewhere (the author):
  auto-target puts that system in the galaxy map, through the same countdown run as a route's 🎯 (POST
  api/highway/target {route: "carrier"}; a route cleared does not stop it). Game PC only; none aboard, in its system or
  decommissioned.
- Here's firsts no longer end in "sell at Universal Cartographics to claim what's unsold": players know (the author).
- With the surface map up in the Overview, the firsts and the checklist under the system's name are hidden, so the
  room goes to the bodies; they come back with the map.

## 2026-10-11 · Overview: the map brings your body into view; a shorter Here legend
- When the surface map comes up in the Overview's system pane, the body you are on is scrolled to the top of the list
  above it (the author); again when you are on another body, never while you scroll the list yourself. Only the list
  moves, not the window.
- Here's icon legend drops the explanations in brackets ("something unusual (hover it)", "samples of a species taken
  (3 analyses it)", "planetary mining locations (hover for the likely minerals)"...): the line got too long (the
  author). The cells' own hovers still explain.

## 2026-10-11 · Here: Rings before ⛏
- Here's long bio lines ran into the ⛏ column next to them (the author). Rings now comes first: few bodies with bio have
  rings, so the cell beside the bio column is usually empty and gives it room.

## 2026-10-11 · Exo-Biology checklist: "aboard" counts what you carry
- The checklist's header counted each species once by its best state, so a new colour of a species sold before (Gold
  Vesicula aboard, Cyan sold) was not "aboard": it said "0 aboard" with eleven species' samples in the hold (the
  author). "Aboard" now counts every species you carry unsold samples of in the region (its hover says so); sold, lost
  and logged stay as they were.

## 2026-10-11 · The start-up log says why the journals are read again
- A start that reads every journal again said nothing about it, only a slower "journals up to date in ..." (the
  author). It now says so first, with why: "re-reading every journal once: the journal reader changed (version 48 ->
  49: named listening posts are kept, and two in one system count as two). This can take a few minutes."; or a new
  database, `--rescan`, or a database written by a newer Outrider. The reasons are `PARSER_CHANGES`, in the player's
  words (three at most, the rest counted); every PARSER_VERSION bump adds its line (a test checks).

## 2026-10-11 · Here: one line per finished species, in its colour
- Here listed a finished species twice: "Bacterium 3/3 ✓ 8.3M" and its codex line "📖 Bacterium Alcyoneum - Red ✦"
  (the author). Now one line, the codex entry with what it pays ("📖 Bacterium Alcyoneum - Red ✦ 8.3M"; compact: the
  genus); a species still being sampled keeps its "1/3" line and its codex line.
- In codex lines the colour's word is drawn in that colour ("Bacterium Alcyoneum - Red": "Red" in red), mixed with the
  theme's text colour so it reads on light and dark, and kept on a highlighted row; to try: Settings → Display → "Here:
  species in their colour" turns it off (this device).
- The Rings column stacks "2", "2 mapped", "1 hotspot" (the whole sentence on hover), so it is about as wide as its
  heading and the bio column gets the room.

## 2026-10-11 · Review fixes: today's code
A Fable review of everything written since v2026.10.21 (d7be805..2cb1e60): six bugs confirmed, all fixed.
- Inara: snapshots dropped because the commander had no API key yet were still recorded as sent, so ranks, reputation,
  the ship and friends never reached the profile once the key was entered (until each changed). A drop for no key now
  forgets that commander's record, and so does a new or removed key (maybe another Inara profile).
- Inara: a dock after a hyperspace jump charged straight from normal space (no SupercruiseEntry, the usual way off a
  carrier) was taken for docking again where you undocked and left out of the flight log; a login's dock suppression
  also outlived the undocking when the game wrote no Docked. Both cleared by the jump and the undocking now.
- Surface sites: a later FSS line for a body (it names only the anomaly) wiped the DSS's Guardian and Thargoid sites, and
  mapping it again announced them again. The FSS now adds to what is known.
- FSS signals: named listening posts ("Listening Post Pollux D568") never passed the reader's filter, and two indexed
  ones in a system were one row ("Listening Post #1", "#2" now; said once per system and kind). PARSER_VERSION 49: the
  next start re-reads the journals.
- Curiosities: the systems already told (meta `curious_said`) were trimmed to the 2000 largest id64s, not the 2000 most
  recent: kept in the order said now.
- Launchers: the PyQt6 step ran in the repository while Outrider runs in the caller's folder, so a relative `--config`
  named two different files and the early install was skipped. It runs in the caller's folder too (the repository on
  PYTHONPATH); the .bat is untested on Windows.

## 2026-10-11 · Tidier bio lists for bodies not DSS'd
- Here's bio cell for signals not identified yet read "3 signals, not DSS'd", then "3 of these, 24.8M to 64.6M:", then
  each genus on a line ending in "or" (the author: clean it up). Now one line for the count and the range ("3 signals,
  not DSS'd · 24.8M–64.6M:"), then the genera with their best price dimmed, without "or" between them.

## 2026-10-11 · No overlay while the game loads
- After a crash the game writes no Shutdown and leaves Status.json saying live with the dead session's flags; the
  relaunched game does not rewrite it until the session is in, so the overlay drew the old panels over the loading
  screens, before the main menu and after it (the author). The reader now notes the newest game launch (a journal's
  first part) or LoadGame and the newest Location (meta `game_load`, journal-derived): from one to the other the game is
  loading and the overlay shows nothing.

## 2026-10-11 · Rare planet classes, and one line for curiosities
- Rare planet classes are 🔭 curiosities now: water giants, helium-rich and helium gas giants, Sudarsky class V gas
  giants, and green gas giants (from their codex entry: the game says it nowhere else).
- A new alert under Discoveries, "Curiosities": the first time the system you are in shows curiosities while the game is
  live, one line to look at the panels, never the list ("You might be interested in some curious things I found here.
  Check your panels.": the author's idea), with its own `curious` lines in every personality (50 a list). Once per
  system ever (meta `curious_said`, live-only): a revisit stays quiet.

## 2026-10-11 · FSS signals worth a detour
- The reader's filter threw away every FSS signal but the phenomena: Titans, Guardian beacons, generation ships,
  listening posts, number stations, tourist beacons and memorials now pass and are kept per system (`poi`;
  PARSER_VERSION 48: the next start re-reads the journals). Ordinary megaships are traffic, not destinations: left out.
- A new alert under Discoveries, "Signals worth a detour": "the Titan Cocijo", "a Guardian beacon", "a generation ship,
  the Thetis", "a listening post", the first time a system has it, with its own `signal_poi` lines in every
  personality, all delighted (50 a list). Tourist beacons, number stations and memorials (common in the bubble) are
  shown, not said.
- 📍 on Nearby and Here counts them (which, on hover), and Now has a line ("📍 Titan Cocijo · 2 tourist beacons").

## 2026-10-11 · Surface sites: Guardian, Thargoid, planetary anomalies
- Body signals other than biology, geology and mining were dropped: Guardian and Thargoid sites (the journal names them
  only once the DSS has mapped the body), the new planetary anomaly (the FSS names it; nobody has documented what it is
  yet) and "other" signals are kept now (`own_signals.sites`; PARSER_VERSION 47: the next start re-reads the journals).
- A new alert under Discoveries, "Surface sites": "Guardian and Thargoid sites on 10 b", "an unknown planetary anomaly
  on C 2", once per body and kind, with its own `surface_site` lines in every personality, all delighted (50 a list).
  "Other" is shown, never said.
- Here tags the body (🏛 Guardian, 👾 Thargoid, ❔ anomaly, 📡 other; the legend explains them), Nearby marks the system,
  and Now has a line.

## 2026-10-11 · Notable stellar phenomena: which ones you have visited
- The journal says only "a ring phenomenon" when you drop at one, not which of the system's three, and two sites can
  share a ring (the author found two in one ring with different things), so each drop counts as a site visited
  (`phenomena_sites`, journal-derived; dropping twice at one site counts twice): Now says "1 of 3 visited" (then "all
  visited"), the 🌀's hover the same, and it dims only once every one is visited. PARSER_VERSION 46: the next start
  re-reads the journals once (for the drops already made). Asked by the author, 2026-10-11.

## 2026-10-11 · Rare stars, announced and marked
- A new alert, "Rare star": a black hole, Wolf-Rayet, carbon, MS/S-type, O-type or Herbig Ae/Be star, a supergiant, a
  rarer white dwarf (pulsating DAV/DBV..., DO, DX...) or an exotic type, resolved live by the arrival's own scan or the
  FSS, once per star ("a black hole, the main star", "a Wolf-Rayet star at B"), with its own `rare_star` lines in
  every personality, all delighted (50 a list). Neutron stars and ordinary giants are too common to count.
- ⭐ on Nearby and Here marks rare stars, Spansh's records included (a black hole nearby shows before you go); Now has
  a line for them.
- Settings -> Alerts groups the discoveries under one heading ("Discoveries"), each still with its own sound,
  notification and voice switches (the author: a toggle per type, together in the list).

## 2026-10-11 · Notable stellar phenomena: counted, in Now, and announced
- The FSS lists a system's phenomena as identical lines (the author's Smojooe XF-G b24-0: three rings in one second),
  and the (system, kind) key folded them into one: each kind now keeps how many (`phenomena.n`, the most one FSS
  listing had; opening the FSS again never adds up). PARSER_VERSION 45: **the next start re-reads the journals** once,
  so past systems get their counts.
- A new alert, "Stellar phenomena": the first time the FSS finds phenomena in a system with none on record, live, "three
  notable stellar phenomena, all in rings" (a cloud, rings, or both, in words), with its own `phenomena` lines in every
  personality: all delighted, the sarcastic and profane ones too (50 a list). Nothing was said before.
- Nearby's and Here's 🌀 shows the count ("🌀 3", what they are on hover; it showed one 🌀 for any number), and Now has
  a line: "🌀 Three notable stellar phenomena, all in rings · none visited yet".

## 2026-10-11 · Piper spells four star letters too
- A body round four stars' barycentre ("ABCD 3 a", "ABCD 3 b a": the author's, today) was said "abd three ay": the
  letters were spelled only up to three. Up to eight now, under the same rule that keeps words out (the letters in
  alphabetical order, none twice: "ABBA 2" stays a word). Belts the same.

## 2026-10-11 · Inara uploads, part G: the docs
- The Uploads guide covers Inara: what goes, never the carrier, the batching and the change-only rule, the API key,
  switching Inara off in any other app first (EDMC, EDDI, EDDiscovery, EDDLite: two senders can get the key revoked),
  refusals, the developer switches. README, the Settings and Install guides, DESIGN_NOTES (why the whole profile, why
  change-only, login-only credits) and AGENT_GUIDE's code map (`outrider/inara.py`, the hub's TRACKERS and keep).
- Inara still has to accept "ED Outrider" before anything reaches it: until then it refuses, and Settings shows its
  words.

## 2026-10-11 · Inara uploads, part E2: missions, combat, friends and suits (parity with EDMC's plugin)
- So a player using Outrider as their only connector loses nothing on their Inara profile (the author, 2026-10-11):
  the mission log (accepted: where, for whom, what; completed: rewards, permits, the factions' gains; failed;
  abandoned) and a mission's permits; the combat log (deaths with the killer or the wing's names, interdictions both
  ways, escapes, PvP kills: Inara records only those); friends (added or seen online once, removed when declined or
  lost; adding sends a friend request on Inara, as the game's does); Odyssey suit loadouts (whole when worn, changed
  ones only: the game writes SuitLoadout at every disembark; equipped, renamed, deleted).
- An NPC's code name ("$LUASC_..._SpecOps_A;") goes as its readable one ("Spec Ops Wing Alpha"). Unlike EDMC's
  plugin, a renamed suit loadout sends its new name.

## 2026-10-11 · Inara uploads, part E: community goals
- Every community goal you take part in (exploration and biology goals too: the author, 2026-10-11): the goal (name,
  place, expiry, tier reached and the top tier, contributors, total; Inara keeps each goal's page from what the apps
  send) then your progress (contribution, percentile band and its reward, top rank). The game writes CommunityGoal often
  while you are signed up (1,593 times in the author's journals): each goal goes only when its figures changed.

## 2026-10-11 · Inara uploads, part D: the fleet and stored modules
- Ships bought (the old one stored where you are, or sold), sold (on a rebuy too), swapped (the old one stored; the
  Loadout that follows marks the new one current), sent elsewhere (with the transfer time) and renamed.
- The fleet's places when the shipyard lists it (StoredShips: changed ships only; a ship in transit has no place yet)
  and the stored modules whole (StoredModules, engineering included; an emptied store is sent empty).

## 2026-10-11 · Inara uploads, part C2: reputation and inventory
- Reputation with the superpowers (at login) and with each arrival system's factions, as Inara's -1..1, changed ones.
- The inventories as whole snapshots, which Inara replaces whole: materials (the Materials tab's own fold), the
  ship's hold (from Cargo.json when the line is the short form) and the Odyssey ship locker (reset, then set, so an
  emptied kind empties there too). Taken when a batch goes (a jump, a docking, the end of the login's lines, a
  shut-down) and only when changed: never on every pickup (the author's journals hold 14,049 Cargo and 19,467
  ShipLocker lines). An emptied hold is sent empty.
- Never the SRV's hold, and never anything about the fleet carrier (transfers, its market, trade orders): Inara's
  API has no carrier inventory, and the carrier tracker's figures stay in Outrider.

## 2026-10-11 · Inara uploads, part C: ranks, credits, statistics and the ship flown
- Every rank and its progress (Combat, Trade, Exploration, CQC, Mercenary, Exobiologist, Federation, Empire; a
  promotion at 0 %), the engineers (stage, rank), Powerplay (power, rank, merits at login; joining, leaving, defecting,
  a new rank).
- Credits once per session as the game says them at login (LoadGame's credits and loan, Statistics' wealth as the
  assets): never Outrider's own sums, which Inara warns against; the game's statistics whole.
- The ship flown (name, ident, values, rebuy, jump range, cargo; marked current) and its loadout with the engineering.
- Only what changed since the commander's profile last got it (meta `inara_sent`): the game writes Rank, Progress,
  Loadout and Statistics at every login and Loadout often, which would otherwise all go again.

## 2026-10-11 · Inara uploads, part B: the foundation and travel (project/PLAN-inara-2026-10-11.md)
- A third uploader beside EDDN and EDSM, off by default: Settings -> Uploads switches it (`[inara] enabled`, hidden from
  the Server settings like the others) and takes an Inara API key per in-game commander (kept here; the page sees its
  ends only). `outrider/inara.py` builds the events, batches them (a jump, a docking, the end of the login's lines, or
  5 minutes) and paces the requests (one every 35 s at most: `upload_loop`'s new `min_gap`); Inara's answers: a refused
  batch holds the service with Inara's words, a rate refusal waits an hour, a refused event is dropped.
- So far the flight log and location: jumps, carrier jumps, dockings (not the one a login or a ship swap writes, nor
  re-docking without leaving), landings (Touchdown, a dropship's deployment) and the location (login, supercruise exit,
  settlements), with the ship flown or the taxi. Ranks, credits, ships, inventory and the rest follow in the next parts.
- EDMC sending to Inara on this PC holds Outrider's (two senders can get the key revoked); the page asks for Inara to be
  off in EDDI and EDDiscovery too, which Outrider cannot see.
- Developer switches (environment, never settings): `OUTRIDER_INARA_DRYRUN=1` builds and logs the requests into
  data/inara-dryrun.jsonl (no key) and sends nothing; `OUTRIDER_INARA_DEV=1` marks them `isBeingDeveloped`.
- The upload hub: a service may follow the session itself (`uploads.TRACKERS`, kept in the session's snapshot) and keep
  its own memory in the tick's checkpoint (`UploadHub(keep=...)`: Inara's record of what each profile has, meta
  `inara_sent`, live-only); a service's hold sees the session.

## 2026-10-11 · Review fixes: Mining sites opens its body in Here
- Materials -> Mining sites' 🔍 opened the body under its full name ("Smojooe AR-E b25-8 ABC 3 d") while Here and the
  body panel go by the short one ("ABC 3 d"): the row was not marked, the panel missed Here's facts and did not
  refresh after a scan. It passes the short name, as the Log's 🔍 does. (A lead from the review's re-check.)

## 2026-10-11 · Review fixes: uploads
- EDDN: logged in docked, the game's Location names the station as the Body ("Thorn Port", BodyType "Station"); a
  later Docked at a planetary port then sent the station's name as its planet. A Location's body is now taken only
  when it is a planet or a star, as EDMC does.
- Switching an upload off forgets its mark: when the config file could not keep the switch, the next start found it
  on and caught up everything played while it was off (up to a week for EDSM).
- Three Outriders on one journal folder: the one taking over from a stopped sender rewinds to the sender's handover
  mark, not to a third instance's that only followed (its mark at the journal's end skipped the stretch nobody sent).

## 2026-10-11 · Review fixes: voice and AI
- The voice's answer when nothing matched ("I only know a few questions so far: ...") names the nearest station or
  carrier too; the list is built from one label per command (`outrider.ask.LABELS`), so a new one is never left out.
- The AI's `body_detail` tool says when no body by that name is known, instead of answering an empty body.
- Spoken lines: with this screen set never to speak (or a tablet not playing alerts), a line's fate says so; it
  blamed "another window".
- The voice lab opens on a speech file whose top level is not an object (it said so and stopped).

## 2026-10-11 · Review fixes: routes
- Plot Route: Clear route while a Road to Riches, Exomastery or trade plot runs into an empty slot stops that plot. It
  posted to the Highway's clear instead: "Route cleared." while the plot ran on, or your Highway route deleted.
- A finished survey or trade route left on screen no longer keeps the clipboard from the Highway (nothing was copied
  for the rest of the Highway until it was cleared); a finished Highway likewise gives it back.
- A trade route's clipboard copies the first stop in another system: with two stops in one system it copied the
  system you were in, and the one after them never.

## 2026-10-11 · Review fixes: journal data and values
- A station repair of "Wear" alone no longer sets the hull to 100 %: wear is the ship's integrity, and a damaged
  hull's repair names "Hull" beside it (checked against the author's journals, 2023-2025).
- A jumponium body found in a system you left without an FSD charge (a carrier jump, a respawn) is no longer
  announced at the next charge, in another system.
- A codex entry with no body (a phenomenon found in space) is no longer shown, voucher and all, on every body of the
  system you have not scanned yourself.
- A system first found through EDSM and later filled from Spansh's data is Spansh's: it kept EDSM's mark, so the
  arrival verdict was never refined from it.
- `--restore` with the database file gone but its rollback journal left sets the journal aside: SQLite would have
  rolled it into the restored database.
- An older Docked read late (a legacy folder imported after the live one) no longer moves the market a carrier
  transfer is filed under.
- Exo-Biology checklist: Concha Biconcavis shows 19,010,800 cr (the price list), not BioScan's placeholder 16,777,215;
  the unsold estimate prices a species missing from the price list (Radicoida Unicus) from the bio rules, as My Samples
  does, instead of "not priced".
- No journal re-read: the fixes apply from the next lines read.

## 2026-10-11 · Review fixes: config and launchers
- A config value of the wrong type is reported at start and the default kept, as the example file says: a boolean
  for a number (`module_warn = true` read as 1, `radius = true` as 1 ly) and a non-text `db`, `backup_dir`, `voice`,
  `voice_fallback` or `[autohonk] key` (`db = 5` became a database called "5") were taken silently.
- `--write-config` and the first Server settings save write `backup_dir` relative to the Outrider folder
  ("data/backups"), as `db` is: an absolute path kept pointing at the old folder after a move or rename.
- `ed_outrider.toml.new` (Server settings write through it; it holds the password while it exists) is git-ignored.
- launch_outrider.sh and .bat start Outrider in the folder they were run from, so relative paths in the arguments
  (`--config my.toml`, `--journals .`) are the caller's, not the repository's. The Linux launcher no longer stops
  when pip's own upgrade fails (offline): the requirements' install after it says what matters, as on Windows.

## 2026-10-11 · Review fixes: auto honk and the server
- Auto honk no longer presses Primary Fire when Status.json says the game is at its menu or closed: quitting during
  its wait for the cockpit (galaxy map open after arriving, say) sent the key into whatever window had focus. It waits,
  then gives up as the other waits do. A press that fails puts its status back to ready (it stayed "waiting: ...").
- Sign-in: a proxy that sends only RFC 7239 `Forwarded` gets each device its own count of wrong passwords (all shared
  one before); addresses that stopped trying are forgotten, not kept for the life of the process.
- Failed body-detail lookups say "Spansh body lookups failed", so the Data tile names Spansh, not "server error".
- More voices: a catalogue download cut off mid-way answers the page's "cannot be fetched" (502), not a bare 500.
- With `[server] host` set to one LAN address, Outrider also listens on 127.0.0.1 for the overlay window, which
  always talks to loopback: it drew nothing.

## 2026-10-11 · Review fixes: the overlay
- The overlay's figures are written as the page writes them: 999,999 was "1000k" (the page: "1.0M"), 999.95M
  "1000.0M", 1.25B "1.2B" (`overlay.credits` follows page.js `credits`).
- A station or a mining site targeted in game is no body: the body panel kept to the body you are near (it vanished),
  and Now no longer says "➜ Harper Dock · nothing to do here" or a raw `$SAA_Unknown_Signal` name; a mining site's
  planet is matched by its id, as the page's Now view does.
- The overlay window's feed survives a connection cut mid-answer (an `http.client` error is not an OSError): it ended
  and the last panels stayed drawn over the game.
- The runner: a window that drew for a minute or more and then stopped starts a new count (five stops over days of
  play no longer gave up for good: "five times in a row"); a pip run that succeeds while this Python still cannot
  import PyQt6 is reported once, not run again every few seconds.
- Settings -> In-game overlay: the answer to a switch (theme, text size, on/off, test panels) was taken for a layout
  answer and dropped until the next poll; and after a pick from a list the server's note was never drawn (the list
  kept the focus, which holds the redraw off).

## 2026-10-11 · Version 2026.10.21
- The in-game overlay (six panels, Arrange mode, themes, PyQt6 installed automatically; game PC only), GPL-3.0-or-later,
  the Exo-Biology genus ✓, EDDN's biology samples (scanorganic/1) and parity with EDMC (planetary Docked's body, no
  allowCobraMkIV), no rebuy multiple for an Arx-bought ship, whole days since you sold, the launcher's clipboard note,
  ExploData's colours downloaded instead of shipped, the version in the log's first line, the docs review. No journal
  re-read. What's new has its section; new screenshots overlay.png and overlay-settings.png, checklist.png retaken
  (seven genera shown complete for the ✓, the page's copy of the data only: project/screenshots/extra.js DEMO_COMPLETE).

## 2026-10-11 · Overlay: long rows wrap; Settings: the placement table fits its section
- The Now panel's Next detail and the Bio signals footer were cut with … when too long ("7.1M/min…", "5 m…"): they
  now go on to the next line, broken between their parts (`overlay.flow`).
- The table was wider than Settings -> In-game overlay (726 px in 711 at a 1600 px window, its reset links cut off):
  narrower number boxes and padding make it fit, and on a narrow window it scrolls sideways inside the section
  instead of spilling out (`.ovwrap`).

## 2026-10-11 · The launcher's clipboard note says which program serves which session
- The block says wl-copy (wl-clipboard) is for Wayland sessions and xclip for X11 ones, and what is lost without it:
  the copy, and auto-target's paste (it types the name by default, which still works).

## 2026-10-11 · The launcher says which clipboard program to install
- launch_outrider.sh checks the desktop session at every start (Wayland: wl-copy, X11: xclip, as Outrider picks them)
  and, while the one it needs is missing, prints a marked block (coloured in a terminal) with the command for this
  system's package manager (apt, dnf, pacman or zypper; otherwise the package's name) and the one that installs both.
  Nothing without a desktop session (a server) or on macOS. It was a one-line hint after an install only.

## 2026-10-10 · Docs: the overlay's side brought up to date (branch EDMC-Functionality)
- The README and the overlay guide name all six panels (system, body, radar, the system strip, Now (To-Do & Info), Bio
  signals). The overlay guide: the test panels draw every panel, none shows in the hyperspace tunnel, Now's target
  words and at-risk line (the rebuy multiple, none for an Arx-bought ship, and how long since you sold), how PyQt6 is
  installed (by the launcher and by Outrider, into `.venv`, and what happens when that fails), the crash give-up, where
  each panel's tick box is and which start on, the layout kept in the database (copy `data/ed_outrider.sqlite` to carry
  it), and a bottom nav line.
- Install: the launcher's PyQt6 step, wmctrl and x11-utils on Linux, the overlay off in Docker. Settings: the In-game
  overlay section, and `--simulate` keeps the overlay window off. For the curious: the overlay's files. Views, Voice and
  alerts, Automation: no rebuy multiple for an Arx-bought ship.
- The config's comments (and the example config, the page's panel tip): the system strip is two short lines; the
  system panel's `system_seconds` counts from arriving, not the honk. The overlay window's docstring: PyQt6 is
  installed while the overlay is on, not from Settings.
- AGENT_GUIDE, DESIGN_NOTES and JOURNAL_REFERENCE: the overlay's modules, state, tests and limits, its config levels
  and the page rules it copies, the new decisions (PyQt6 installed when the overlay is on, whole days since you sold,
  where the panels hide), the Status.json flags and GuiFocus values it reads, and Loadout's HullValue/ModulesValue.
  The changelog gains the missing entry for "the hint says Outrider runs the window" and O2's entry is corrected (the
  ExploData tables were already downloaded, not shipped).
- package.json's licence: GPL-3.0-or-later. `test_server_mode`'s guide check expects In-game overlay in the Settings list.

## 2026-10-10 · Days since you sold: whole days on the page too (branch EDMC-Functionality)
- Now's at-risk line ("6 d unsold") and the spoken welcome back ("unsold for 6 days") count whole days passed, as the
  overlay's Now panel does, instead of rounding 6.7 days up to 7.

## 2026-10-10 · Overlay: no Now panel while docked (branch EDMC-Functionality)
- The Now (To-Do & Info) panel hides while you are docked: the ship's docked flag, or on foot in a station, hangar or
  social space (`FLAG_DOCKED`, `ON_FOOT_DOCKED`), and comes back when you undock.

## 2026-10-10 · Docs brought up to date
- The guide: every page's bottom nav matches its top (What's new and Uploads included; Uploads and What's new gain
  one); the README's tab list has Overview, Bookmarks and Plot Route. Views: Bookmarks is its own tab, Search's mining
  filter is Local only, Now's at-risk line as it is (shown over your levels, "sell here", the high-g stakes, days
  unsold), the surface map's sizes in Settings → Surface map. Voice and alerts: which alerts notify and which speak by
  default, the Codex finds count row, the profanity share, the nearest-dock phrases. Plot Route: the two route slots,
  Exomastery's options, Plot here with Trade chosen, the new voice phrases; the tablet's Plot Route; unique stops for
  trade routes; the co-pilot press that cancels a waiting run. Uploads: every kind EDDN gets, what a catch-up cannot
  send, a schema EDDN keeps refusing held until a restart, the developer switches' marks. Settings: the upload
  switches are not among the Server settings. For the curious: the newer modules and scripts, where ExploData's
  colours come from, what verify.sh checks.
- The in-danger wait is 16 to 26 s (measured 16, 16, 26), not 15 to 26, in the guide, DESIGN_NOTES and a docstring.
- ed_outrider.toml.example names ⚙ Settings and its sections instead of the old alerts dialog, the clipboard on
  Windows, and biology samples among EDDN's data; launch_outrider.bat says which game-PC parts run on Windows.
- DESIGN_NOTES: one full list of outside calls (Canonn, GitHub's update check and colour tables, EDAstro, and the AI
  layer, which is not read-only), EDDN's field-for-field match with EDMC, EDDiscovery and EDDLite, biology samples on
  scanorganic/1, the two status reports, one note for the survey / trade slot, duplicates cut. JOURNAL_REFERENCE:
  the uploads see every line before the filter, and the uploads' traps. AGENT_GUIDE: `State.highway_ends`, the
  newer tests, modules and scripts, the shorter speech keys, the live-only tables, the per-device keys.
- The SCHEMA comments say `route_systems` and `star_classes` are kept through a journal re-read.
- verify.sh takes SPANSH_SYSTEM_SEARCH offline too.

## 2026-10-10 · EDDN: biology samples (scanorganic/1)
- Each ScanOrganic Log and Sample goes to EDDN's scanorganic/1 (EDDI, EDO Materials Helper and EDEXO-Compare send it;
  the schema is on EDDN's develop branch and the gateway takes it). Analyse never does (it can come in another system,
  so the schema leaves it out). StarSystem and StarPos after the location cross-check, Body renamed BodyID, the
  internal genus, species and variant names. BodyName only when the body you approached has that id; Latitude and
  Longitude only from the live Status.json on that body, read between 90 s before and 10 s after the scan, so a
  journal caught up later sends no position (`organic_message`, `Session.status_pos`).
- The uploads guide says what is taken out more exactly: codex entries and samples keep where they were found.
- tests/fixtures/eddn gains EDDN's scanorganic-v1.0.json (it starts with a BOM: the tests read the schemas with
  utf-8-sig).

## 2026-10-10 · The example config names Settings -> In-game overlay for [overlay] (branch EDMC-Functionality)
- Its heading's list of where each setting is changed in the page gains the overlay's (whose switches apply at once).

## 2026-10-10 · The example config says the page can change every setting
- ed_outrider.toml.example's heading says every setting can be changed in the web page's Settings (Server settings,
  Uploads), which writes ed_outrider.toml itself (comments kept, a .bak of the old copy).

## 2026-10-10 · EDDN: planetary docks name their body; no allowCobraMkIV
- Compared with EDMC, EDDiscovery and EDDLite on EDDN's relay (45 hours, 1.8 million of their messages): Outrider
  sends every journal schema they do (ApproachSettlement, CarrierJump and FCMaterials not seen live yet), field for
  field, with two differences, both now gone:
- A Docked at a station on a planet's surface (crater outposts and ports, surface stations, settlements, planetary
  construction depots) carries the body you approached, `Body` and `BodyType` "Planet", as EDMC adds them (the journal's
  Docked has no body). An orbital station's never does.
- shipyard/2 no longer carries `allowCobraMkIV`: it is about the commander, not the station, and the other three
  leave it out.

## 2026-10-10 · Overlay: the PyQt6 messages say "in Outrider's venv" (branch EDMC-Functionality)
- The install popup, Settings' status, the launcher's line and the guide say PyQt6 goes into Outrider's own venv, so
  nobody takes it for a system-wide install.

## 2026-10-10 · Overlay: a popup while PyQt6 installs (branch EDMC-Functionality)
- While Outrider installs PyQt6 for the overlay window, a popup at the top of the page says so ("Installing PyQt6 for
  the in-game overlay…", with a spinner), in every window of the page; when it finishes it says "PyQt6 installed: the
  overlay window is starting" or that it failed (Settings has why) for five seconds, then goes (`renderOverlayInstall`).

## 2026-10-10 · No rebuy multiple for a ship whose hull has no value (branch EDMC-Functionality)
- An Arx-bought ship's Loadout has ModulesValue but no HullValue, and its rebuy covers the modules only (the author's
  ship: 1.09M), so any trip's data read as ~110 rebuys. For such a ship Outrider leaves the rebuy out of the risk
  figures: no "× rebuy" on the unsold tile, Now's at-risk line, the overlay's Now panel or the status report; the
  rebuy-multiple warning levels do not apply (the credit levels still do); the approach warning speaks a line without
  rebuys. `risk_rebuy` (server) and `riskRebuy` (page). Settings says so beside the rebuy levels.

## 2026-10-10 · Overlay: how long since you sold, in words (branch EDMC-Functionality)
- The Now panel's data-at-risk line says "3 days unsold" (was "3 d unsold"), and from a week "2 weeks 2 days since
  sold", or "2wk2d since sold" when the written-out form would not fit on the line (`overlay.unsold_age`). Whole days
  passed, no longer rounded up.

## 2026-10-10 · Settings: the overlay's help as three short points (branch EDMC-Functionality)
- Settings -> In-game overlay: the paragraph under the table becomes a list (game PC only and PyQt6, borderless or
  windowed, Arrange panels), without the Install PyQt6 button it still mentioned.

## 2026-10-10 · Overlay: PyQt6 installed when the overlay is on; each panel's switch in its row (branch EDMC-Functionality)
- No Install PyQt6 button any more (the author's call: not a menu option). launch_outrider.sh / .bat install PyQt6
  before Outrider starts when `[overlay] enabled = true` is in the config and it is missing
  (`python -m outrider.overlay_runner --setup`; on Linux they also say when wmctrl is missing), and Outrider installs
  it itself, once per switching on, when the overlay (or the test panels, or Arrange mode) is switched on without it.
  POST `/api/overlay/install` is gone.
- Settings -> In-game overlay: each panel's on/off box is in its own row of the table, beside its place, size and
  opacity (the list above the table is gone, so the section is smaller); what a panel shows is its name's hover tip,
  and a panel switched off is dimmed.

## 2026-10-10 · Overlay: the Now panel named "Now (To-Do & Info)" (branch EDMC-Functionality)
- Its name in Settings -> In-game overlay, Arrange mode's labels, the config's comment and the guide (the key stays
  `now_panel`). Settings writes the panels' names escaped.

## 2026-10-10 · Overlay: the Now and Bio signals panels (branch EDMC-Functionality)
- Two more optional panels, off by default (`[overlay] now_panel`, `bio_panel`; Settings -> In-game overlay).
- **Now**, the page's Now view condensed: the system (and the arrival verdict for 20 s), the target, fuel, the data at
  risk past `unsold_warn`, the on-body card with the sample spacing, or Next (the first of the suggested order, with the
  supercruise time and per-minute value) and the targeted body, this session. Now's plan is ported to Python
  (`overlay.plan_items`, the page's `worthLeavingFor` + `planItems`) with the config's levels.
- **Bio signals**: every body with bio in the system, worth it or not. The ones meeting your levels (`bio_min`, a run
  started, new to your codex, unpriced) are highlighted, the rest muted, the finished ones ticked; per species: the
  samples, the colour, the codex mark and the value; not-DSS'd signals show what they could be.

## 2026-10-10 · Overlay: the system strip's lines rearranged and centred (branch EDMC-Functionality)
- Line 1 is the system, its region and the star; the distance from Sol, now, max and first discovered move to line 2,
  before the body counts; both lines are centred in the box (a `runs` line can be centred: `align` "center", measured
  with the window's real fonts).

## 2026-10-10 · Overlay: a game-PC feature only (branch EDMC-Functionality)
- The overlay joins the key presses as a game-PC feature (the author's call): Outrider on the game PC runs the window,
  and an Outrider on a server has no overlay. Gone: launch_overlay.sh / .bat (a window drawn from a server),
  `[overlay] url` and `password`, the window's sign-in; Settings -> In-game overlay is left out on a server (as Auto
  honk is), and POST `/api/overlay` and `/api/overlay/layout` answer 409 there.

## 2026-10-10 · Overlay: Windows' click-through both ways; where it works (branch EDMC-Functionality)
- On Windows the window only ever added the click-through style (WS_EX_TRANSPARENT), so Arrange mode would never have
  had the mouse there: it is taken away again for Arrange mode (`win_exstyle`).
- The guide's "Good to know" says where the overlay works: X11 (a compositor needed), Wayland through XWayland (tried
  on GNOME), not with Proton's native Wayland mode, fractional scaling untried, Windows untried, never exclusive
  fullscreen or gamescope.

## 2026-10-10 · Overlay: the system strip (branch EDMC-Functionality)
- A fourth panel, optional (`[overlay] strip_panel`, off by default), made for the top of the screen: line 1 where you
  are (system, region, distance from Sol, the star in words with ⛽ / ⚡, now and max, 🏁 first discovered), line 2
  condensed (bodies, found of total, 🏁 discovered by you, 🗺 mapped of the planets, Spansh ✓ or ✗). It shows wherever
  you are (ship, SRV, on foot). The author's EDMC had BioScan's line along the top.
- Panels can be centred along the top or bottom edge (layout corners `n`, `s`; "top centre" and "bottom centre" in
  Settings): Arrange mode centres a panel dropped about the middle. Star words name giants and supergiants.

## 2026-10-10 · Overlay: test panels for a minute, whatever is in front (branch EDMC-Functionality)
- The test panels showed only once you were back in the game (the overlay draws while the game is in front, and they
  are pressed from Outrider's page), so most of their 20 s went by unseen. They now stay a minute and show over the
  game's window whatever is in front, as Arrange mode does (`overlay_window.should_show`).

## 2026-10-10 · Overlay settings: the hint says Outrider runs the window (branch EDMC-Functionality)
- Settings -> In-game overlay's hint said to start the window by hand (`python3 -m outrider.overlay_window`, PyQt6
  installed with pip). It now says Outrider runs the window itself on the game PC while the overlay is on, and gives
  the command for the game PC when Outrider runs on a server (`./launch_overlay.sh --url ... --password ...`).

## 2026-10-10 · Overlay: Outrider runs the window itself (branch EDMC-Functionality)
- On the game PC, Outrider starts the overlay window while the overlay is on (or for the test panels and Arrange mode),
  closes it when it is switched off and when Outrider stops, and starts it again after a crash (a growing wait; it
  gives up after five in a row and says so). One application: launch_overlay.sh is only for an Outrider on a server.
  It does not start a second window when one started by hand is drawing.
- Without PyQt6, Settings -> In-game overlay says so with an **Install PyQt6** button (into Outrider's own
  environment); the window's state is shown there (starting, drawing, restarting, failed).
- The window sets GDK_BACKEND=x11 when it runs through XWayland: Qt's GNOME theme starts Gtk, which followed the
  session's GDK_BACKEND=wayland and could exit the window.

## 2026-10-10 · Overlay: say when no window is running (branch EDMC-Functionality)
- Show test panels (or Arrange panels) with no overlay window running looked like it did nothing: the panels are drawn
  by the window on the game PC. Settings -> In-game overlay now says so with the command to start it
  (`./launch_overlay.sh`, Windows `launch_overlay.bat`), and pressing either button says nothing can show until it
  runs. "An overlay window is drawing" counts only the window's own requests (its User-Agent), not any visitor's GET.

## 2026-10-10 · Overlay: nothing in the hyperspace tunnel (branch EDMC-Functionality)
- The panels hide while Status.json's FSD jump flag is on (BioScan's "hidden during FSD jumps"): the system is
  changing under them.

## 2026-10-10 · Overlay: the launchers and the guide (branch EDMC-Functionality)
- `launch_overlay.sh` / `launch_overlay.bat` start the overlay window with Outrider's .venv and offer to install PyQt6
  into it the first time (only on a yes); on Linux they warn when wmctrl, xprop or xwininfo is missing. Windows has
  the code and the launcher but is not yet tried against the game.
- The guide's new page, In-game overlay (docs/guide/overlay.md): what the panels show, starting the window (and
  pointing it at a server), arranging, the settings; in every page's links and the README's index. DESIGN_NOTES: why
  our own window, Modern Overlay's code and GPL-3, the layout kept by Outrider, the config's levels.

## 2026-10-10 · Overlay O7: themes (branch EDMC-Functionality)
- `[overlay] theme` colours the panels from the theme's own stylesheet (static/themes/<name>.css: its title, text,
  muted, good, warn, bad, accent, panel and line colours, `var()` chains resolved; anything missing: the Default's,
  which are the page's dark colours) and frames them as the 10-05 plan drew them: cut corners (Elite, Narn), a double
  line (Centauri, Minbari), LCARS's bars, rounded for the rest.

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

## 2026-10-10 · Overlay O2: the window on the game PC, and GPL-3 (branch EDMC-Functionality)
- `python3 -m outrider.overlay_window` (PyQt6: `pip install -r requirements-overlay.txt`; never in the Docker image):
  a frameless, translucent, always-on-top window that lets clicks through, follows Elite's window (X11, and XWayland
  on a Wayland session as Elite under Proton is; Windows untried), hides when the game is not in front, and paints the
  panels from GET `/api/overlay` (once a second; signs in to a server with `[overlay] password`). `--render PNG` draws
  one frame into a picture instead.
- Finding the game's window (`outrider/overlay_tracking.py`) and the window's flags are adapted from EDMC Modern
  Overlay (GPL v3), so **ED Outrider is now GPL v3 or later** (LICENSE, README, the Docker label). The README credits
  Modern Overlay, and EDMarketConnector for the upload rules. EDMC-ExploData's colour tables (its repository has only
  the GPL v2 text) do not stand in the way: since the commit before O1 they are downloaded, never shipped.

## 2026-10-10 · Overlay O1: the panels' server side (branch EDMC-Functionality)
- `outrider/overlay.py`: the in-game overlay's panels as draw lists on a 1280x960 canvas (text, rectangles, circles,
  lines, markers), a text-panel builder, test panels, the `[overlay]` settings (enabled, theme, text_size, each panel
  on/off, system_seconds, radar_range; url and password for the window on the game PC) and the panels' layout (per
  panel a corner, an offset, a size, the background's and the whole panel's opacity; meta `overlay_layout`).
- GET `/api/overlay` (with `since=<version>`: just `{same}` when nothing changed), POST `/api/overlay` (the switches,
  written into the config; test panels for 20 s; Arrange mode for at most 10 minutes), POST `/api/overlay/layout`.
  The real panels come in O4-O6; nothing draws them until the window (O2).

## 2026-10-10 · Docs: the ExploData notes without the licence change still to come
- The CHANGELOG and DESIGN_NOTES entries for the downloaded colour tables no longer say Outrider's licence changed.

## 2026-10-10 · ExploData's colour tables downloaded, not shipped; the README's credits
- The colour tables (EDMC-ExploData: its repository carries only the GPL v2 text, without "or later") leave the
  repository: `resources/bio_rules.json` ships with no colours, and they are downloaded on the first
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
