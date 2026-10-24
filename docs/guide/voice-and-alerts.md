[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · **Voice and alerts** · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Voice and alerts

## 🔔 Alerts

Alerts fire only for something out of the ordinary. Each can play a sound (🔊), show a desktop
notification and be spoken (🗣), chosen per alert in **⚙ Settings → Alerts**. The table is in groups (jumps and
arrivals, exploring a system, discoveries, exobiology and the surface, fuel, routes and targeting, docking and selling,
danger and risk, your carrier, the game and comms); each row gives the alert's name and when it fires, and
a dotted line has more in its hover. On the game PC the [in-game overlay](overlay.md)'s Alerts panel can show them over
the game too, for a few seconds each:

- a new discovery targeted, or arriving somewhere nobody has been
- leaving with mapping or bio over your levels undone, or a first-discovered Earth-like, water, ammonia or
  terraformable world unmapped
- a valuable body the moment the FSS resolves it, and a new codex entry. A body someone else has already mapped is
  never pointed out (nor warned about when you leave): the first one in a system gets one line instead, "Already
  mapped, but there are still valuable bodies to map if you want to jump on the train"
- **discoveries**, their own group in Settings → Alerts, each with its own switches, said with delight in every
  personality (the sarcastic and profane ones included: the co-pilot likes new things):
  - notable stellar phenomena the FSS finds in a system where you have none on record ("three notable stellar
    phenomena, all in rings")
  - a rare star resolved by the arrival's own scan or the FSS ("a black hole, the main star", "a Wolf-Rayet star at
    B": black holes, Wolf-Rayet, carbon, MS- and S-type, O-type and Herbig Ae/Be stars, supergiants, the rarer white
    dwarfs, exotic stars; neutron stars and ordinary giants are too common to count)
  - a potential green gas giant: one of your own scans fits the community's ladder model, a guess to check in the
    system map (see [Potential green gas giants](views.md#-potential-green-gas-giants))
  - surface sites on a body: Guardian or Thargoid sites (said once the DSS has mapped the body: the journal names them
    only then) or an unknown planetary anomaly (said when the FSS finds it)
  - an FSS signal worth a detour, new to the system: a Titan, a Guardian beacon, a generation ship, a listening post
    (tourist beacons, number stations and memorials are shown on the page, not said)
  - curiosities (the 🔭 marks: rare planet classes, odd orbits, ringed landables...; planets sharing a centre are not one) in the system you are in, once per
    system: one line to check your panels ("You might be interested in some curious things I found here"), not the list
- low fuel where you cannot scoop, and a top-up worth taking before a dry stretch
- on a Neutron Highway route from the exact plotter, fuel that won't reach the next refuel stop (its own row, **Fuel
  short of the refuel stop**; see [Plot Route](plot-route.md))
- on any route Outrider follows, the last scoopable star before stars you can't scoop that the fuel won't cover (its
  own row, **Last scoopable star**)
- on a route you follow in Outrider, a system targeted in game that is not the next stop (its own row, **Not the next stop targeted**;
  spoken once per target, no notification by default; see [Plot Route](plot-route.md))
- **docking** (its own row, **Docking pad and refusals**, spoken by Comms): the pad the station gave you, said every time, even while
  hushed ("Pad 34."), 5 seconds after the grant so it doesn't talk over the station's own voice (**Settings → Voice → Say your landing pad … s after docking is granted**, 0 to 20: `[speech] pad_delay`, for a chattier station), and why it refused when that isn't obvious: no pad free, ship too big, access restricted, hostile,
  your offences, a fighter still out (too far away is not said). No notification by default. The pad also shows large on
  Now and in the overlay (where the Surface radar goes). At a starport or carrier the pad's place follows: "Pad 34. At the back, up on
  your right." The words assume you come through the slot with the **green lights on your right**, and the first docking
  of each game session (then every fourth) says so: "With the green lights on your right, it's at the back, up on your
  right." **With a docking computer fitted** the pad is shown at once but said only if the computer hasn't taken over
  within 12 seconds (it flies you in; you switched it off: it is said then). To try a pad without docking, type the
  LandingPad plugin's commands in the game's chat: `!sppad 34` (a starport), `!fcpad 7` (a fleet carrier), `!scpad 23`
  (a squadron carrier), `!cspad 3` (a colonisation ship). Local chat reaches other players: use Solo or a private group.
- docking where the station buys your data, and what you banked when you sold
- a sale that left data aboard (Universal Cartographics sells 50 systems a page; at Vista Genomics, the species
  you kept back), said 90 seconds after the last page
- hull damage, heat damage, interdiction, and unsold data past a threshold
- someone else's scans of a system holding your unsold first discoveries reached Spansh (the firsts watch, see
  [My firsts](views.md)): a card and a notification each time, "👁 Someone else scanned your unsold Drojau LL-O
  b26-3: 3 bodies reached Spansh 12 days after you (your scan 15 days ago) · 14.2M cr at stake", and spoken at most
  once in 30 minutes ("Heads up, someone else is scanning your unsold systems. Time to head back to sell before they
  poach your discoveries!"); a first look through many systems adds "3 systems so far today"
- your carrier arriving somewhere new or leaving without you
- a Rhino mining rig nearing the 5 km leash (see The surface map)
- **rings to mine**: a body you scan has a ring of a type you watch for, "A 3 has a pristine metallic ring" (Settings
  → Mining: tick Icy, Rocky, Metallic or Metal Rich, and **pristine only** if you laser-mine). Said as the FSS resolves
  the body, or with the arrival's own scan or a nav beacon; once per body each time you come to the system, bodies
  scanned together in one line ("3 bodies with rings you're watching for: A 3, A 5 and B 1"). Off until you tick a type.
  Hover a type (or tap it on a touch screen) for a table of what lasers and cores give in that ring (laser counting
  abrasion blasting and sub-surface deposits; from the Elite Dangerous Wiki)
- **no limpets aboard** as you undock in a mining ship (a refinery, a prospector limpet controller, or a mining or universal multi-limpet controller; a collector alone, as explorers carry, is not one)
  with none in the hold, while you can still turn back: **Remind me to take limpets** in Settings → Mining, off by
  default. Mining's alerts, ring and Rhino, have their sound, notification, voice and crew switches in Settings →
  Mining's own table (grouped Ring mining and Rhino mining), not under Alerts
- **the prospector call-out**: as each prospector limpet reports, a rock with your threshold (30 % to start) of the
  minerals ticked in Settings → Mining is said ("Platinum, 34 percent"), or with **combined**, their sum ("Combined
  52 percent: Platinum 31, Gold 21": tick Platinum, Palladium, Gold, Silver and Osmium with 50 for a rock half precious
  metals); a **motherlode** always (its own box). Duds and rocks mined before stay silent, and "Material content:
  High" (engineering materials, not the commodity) only when ticked. None ticked: only motherlodes
- **while mining in a ring** (a mining ship, in normal space): Now and the overlay's system strip show the mining line
  (the ring and hotspot, tons an hour, the hold and what it holds, limpets, minutes to full), and the Mining Officer
  says, once a stint: **limpets low** (at the number in Settings → Mining, 5 to start), **hold nearly full** (about 5
  minutes at your rate) and **hold full**, then where to sell the most you carry (the Sell lookup): the best price
  within 100 ly; out in the black, with none that close, the nearest buyer within 500, 2,500 or 10,000 ly (fleet
  carriers reported in the last week among them). Your own carrier is never named as a place to sell (it pays you
  nothing), but when it is within your laden jump range it is named as somewhere to unload
- an upload (EDDN, EDSM, Inara) failing for 15 minutes with messages waiting, and sending again: a card at the top of
  the page and a notification, never spoken (see [Uploads](uploads.md#status))
- an upload going on hold until you act (a key refused or not saved, a kind of EDDN message refused): the card at the
  top of the page always; the notification and a spoken line (Comms) only once you tick its row, **Upload on hold**

Spoken but not notified unless you tick it: the arrival briefing, the FSS debrief, leaving a body with
sampling unfinished, each species completed, tank full, a high-gravity approach with a lot aboard, the
Neutron Highway's next stop, auto-target's result, the jump line, auto honk's result, and the Rhino's rigs (the
co-pilot button's confirmations, what a rig collected, rigs still marked out when you dock the Rhino). Discovery
streaks (ten known systems in a row, or five undiscovered) are part of the arrival alert, which is notified. Not
spoken until ticked: scooping stopped early, supercharge and the body brief on approach (they repeat what the game or
another alert already said). Off until ticked: **jumponium** (see the voice, below).

⚙ Settings also holds the thresholds. Your browser remembers them; the config file sets what a new
browser starts with.

| Setting | Default | What it does |
|---|---|---|
| Exobiology | 10M | A body only counts as unfinished bio if one body could pay over this. |
| Unsold data | 50M / 250M | When the header turns amber and red, or as a multiple of your rebuy (none for a ship bought with Arx: its hull has no credit value). |
| Body highlights | 500k / 10M | Here's row turns green (scan + map) or its bio violet (species) over these. Bonuses left out. |
| Approach warning | 2 g | Gravity at which orbital cruise at a landable body warns you, with data over the amber level. |
| Max with bonuses | on | Whether Here's Max column counts first-discovery, mapping and footfall bonuses. |
| Codex finds count | on | A body whose likeliest species is new to your codex in this region (✦) is worth stopping for, whatever its value. |
| Discovery streak | 10 / 5 | Known or undiscovered systems in a row for a spoken line (0 turns it off). |
| Suggested order | 100k/min | Supercruise credits per minute under which Here marks "skip?". |
| Fuel alerts under N jumps | off | Warns once when jumps left at your pace fall under N; also sets the top-up level. |
| Core modules | 80% | A core module under this shows under hull and is said in the status report. |
| Surface map | 1,000 m / 500 m / 50 m / 3,500 m | Altitude it shows below, narrowest view, rig spacing ring (0 = none), rig leash warning. |
| Mining | none ticked, off; 30 %; 5 | The ring types said when a scanned body has one (Icy, Rocky, Metallic, Metal Rich), and pristine only; the limpet reminder on undocking; the prospector call-out's minerals, threshold, combined, motherlodes (on) and High material content (off); limpets low at (2 to 50). |

**Export settings** and **Import settings** move them to another browser profile (both are a browser's: the Android app opens no file picker and saves no file the page makes). **Use these for new
browsers** keeps a copy on the server (`data/browser_defaults.json`, included in backups), so a tablet running
Now starts with your voice, names and alert choices. The view and layouts stay per device.

Targeting a system plays its sound; arriving is announced by the voice. Walking about a station counts
as docked. A carrier jump booked just before you quit shows as "not yet confirmed" until your next login.

## 🗣 The voice

Alerts are spoken when 🗣 in the header is on. **Piper**, a neural voice running on your CPU, sounds far
better than the browser's own voice. The voice is Cori (`en_GB-cori-medium`) unless you pick another, and it
downloads into `data/piper-voices/` the first time. ⚙ Settings → Voice's **Main voice** switches between installed
voices.

**🎙 Voice lab** (⚙ Settings → Voice) is where you try them out first. It plays in the browser you are using, wherever
Outrider runs (a Docker server too):
- **Voice**: pick an installed voice and a speed, then **▶ Hear it**. **Use this voice** makes it Outrider's voice
  (with that speed).
- **Speakers**: some Piper voices are many people in one download (`en_GB-vctk-medium` has 109, `en_US-libritts_r-medium`
  about 900). The lab shows a speaker list for those: **‹ ›** step through them and **🎲** picks one at random, each
  played as you go. The speaker you use is kept for that voice, and Settings → Voice shows it beside the voice, where
  you can change it too. **Give to this personality** (beside Use this voice) makes the voice and speaker picked
  there one personality's own instead (see Personality voices below), and **Assign to a crew member** one crew
  member's (see The crew below).
- **More voices** lists every Piper voice by language, sorted by name, quality or size. **▶ sample** plays Piper's own
  recording of a voice (from its website) before you download anything. **Download** fetches it without switching:
  when it is ready it is picked above, so you can ▶ Hear it (and its speakers) and press Use this voice if you like it.
  **Select** picks one you already have.
- **Lines**: pick an alert and a personality for **▶ Random line** (filled with made-up values), or **▶ Audition** for
  eight key alerts in a row. A personality with a voice or speaker of its own speaks in it. **▶ Audition: by crew**
  has each crew member say one of its own lines in its own voice and personality. **▶ Audition: crew lines** plays one
  line where a crew member mentions another for each alert that has them, in each personality (or the one picked),
  with your crew's names and made-up ones for a member without. **✂ Cut this line** bans the line just played, like 👎.
- **Your own words**: type anything for **▶ Speak**, or **⬇ Save WAV** to keep it (in a browser: the Android app saves
  no file the page makes).
- **How is it said**: a word the voice says wrong, said your way. Pick or type the word, write how it sounds as
  syllables joined by "-" with the stressed one in capitals (**fon-TIK-yoo-loo-uh**; "uh", "eh", "ih" are short
  sounds, the rest spelled plainly as English says it: kew, few, NIGH), **▶ this way** to hear it, **Save** to keep it.
  **▶ as now** plays the word as it is said today, **↺ mine out** takes yours back out. **▶ as a sector** plays a
  word (or two) read as a sector's name, and below the box are the sectors you have visited most: ▶ plays one, a click
  on one of its words puts it in the box with the rule's reading, ready to change.

Without Piper installed, the browser's own voice speaks. With Piper, the browser's voice is never used: a line Piper
can't say is not said (what you asked for is still shown as a caption).

**Body names are said letter by letter.** With an English Piper voice, "A 1" is "ay one" (not "uh one") and "ABC 3 a"
is "ay, bee, see, three, ay", each letter clearly. Only a body's letters are spelled out: system, station and carrier
names are read as they are written.

**The exobiology names are said the usual way.** espeak's English rules mangle their Latin ("Fonticulua", "Osseus",
"Clypeus Lacrimam"), so Outrider ships how each genus and species word is said, a first pass in the community's usual
(anglicised) reading: "fon-TIK-yoo-loo-uh", "OSS-ee-uss", "KLIP-ee-uss LAK-rim-am". Yours go on top, in
`data/pronounce.json` (the voice lab's How is it said box writes it): a station, a carrier, a system name, your commander
name, or a shipped word said differently. Piper voices in English only; the browser's own speech reads as it always has.

**Sector names are read by rule.** The game builds the names of procedural sectors (Smojooe, Flyeia Hypa, Synuefe)
from a fixed set of pieces, so Outrider reads every one the same way instead of listing them: it splits the word into
syllables and says each as English would ("SMOH-joo", "fligh-AY-uh HIGH-puh", "sigh-NOO-fee"), the stress on the
first of two syllables and on the second last of more. Only a sector right before a system's code is read this way
(Smojooe AR-E b25-8); hand-named sectors (Col 285 Sector, Hyades Sector) and the Dark Regions are read as written. A
sector word of yours in How is it said wins over the rule. There is no official way to say these: the rule aims to be
consistent and natural, and yours can say any of them your way.

**"Click Here To Allow Audio".** A browser plays no sound on a page until you click on it, and Outrider reloads the
page itself after an update. When the window that speaks is held back like this, a red **🔇 Click Here To Allow
Audio** pill appears on the menu bar (and 🔇 in the tab's title), the tablet's caption line says the PC's page needs a
click, and the lines wait: they play once you click, or are dropped if they are no longer news. "Play speech and
sounds on this PC" needs no click. To never be asked, allow sound for the page in the browser (Chrome: Site settings →
Sound: Allow; Firefox: Autoplay: Allow Audio and Video).

**Choosing how it sounds**

- **Personalities.** Down to business, sarcastic and sweet, up to fifty lines per alert each (fifty for most), and
  **US Navy** and **Royal Navy** ("by the book": professional alerts, crisp reports, a friendlier "Skipper" between
  watches; they call you Captain or Sir), and **Vulcan** (dry, precise, never excited, never swears, a little
  disappointed in its human captain), and **Ivanova (Station Cmdr)** (temperamental, fatalistic, bored by routine
  exploration and eager for action, full of tall tales; it calls you Commander or Sir), and the southern pair **Good Ol'
  Boy** and **Southern Belle** (warm, playful, slow to anger, full of family sayings, the old days and food; buddy and
  partner, or sugar and darlin'), and **Klingon** (loud, honour-bound, exploration as the hunt; it calls you Captain,
  Sir, Commander or My Lord), and **Scoundrel** (a cocky smuggler who cares about credits, calls you buddy and pal,
  and tells stories about the Hutton twins).
- **Main personality** (beside **Main voice**) picks one of them. Its last entry, **A mix…**, shows a box per
  personality: tick several and the lines come from all of them, and **One personality per system** holds one
  character a system. With the crew off, the main voice and personality say every alert; with it on, they are the
  XO's (see The crew below).
- **With profanity** uses the swearing versions the share of the time you set (50% by default). It names the
  personalities that never swear ("all but Down to business, Vulcan").
- **Danger alerts always down to business** (on by default): danger is said plainly, never sworn.
- **Your names.** Commander names are often unpronounceable, so the voice calls you by the names in
  **Call me** (default "Boss, Hefay, Sir"); a personality with forms of address of its own (a naval one's "Captain")
  uses those instead.
- **Speed.** 1× is the voice's own pace. Some Piper voices respond to it less than others.
- **Your own lines.** Edit `resources/speech.json` (or a copy named by `speech_file`) to change lines; no restart needed.
- <a id="your-own-personality"></a>**Your own personality.** A personality is a file of its own, in the same format
  as `speech.json` but holding one personality: its entry under `"styles"` (a label, and optionally `"names"`: how it
  calls you, e.g. `["Captain", "Sir"]`, plus a voice of its own as below) and, under `"lines"`, its lists for each
  alert: `"pirate"` and, if it swears, `"pirate_profane"`. Each alert's `"when"` in `speech.json` says when it is spoken
  and which `{placeholders}` it can fill. Put the file in `data/personalities/` (beside a speech file of your own:
  `personalities/` next to it). It shows in Settings → Voice at once, with how many of the alerts it covers while
  it is incomplete (the other personalities ticked, else business, say the rest), and in the voice lab, where you can
  hear its lines and cut the ones you don't like. Outrider's own personality files are in `resources/personalities/`:
  a copy of one in `data/personalities/` under the same name replaces it, so an update never overwrites your changes.
  A problem in a file is shown in Settings, and the file's last good copy stays in use. To share a personality, share
  its file.
- **A voice per personality.** ⚙ Settings → Voice → **Personality voices** gives each personality a voice of its own,
  or another person of a several-person voice: pick the voice (and the speaker, for a voice of many people), **▶** to
  hear one of its lines, **reset** for what the lines file says again. Outrider keeps them, so every browser and the
  tablet say each personality the same way. In `speech.json`, a personality can also name its own installed Piper voice,
  speaker and speed: `"sarcastic": {"label": "Sarcastic", "voice": "en_US-ryan-high", "speed": 1.1}`, or
  `"sweet": {"label": "Sweet", "speaker": 12}` for person 12 of the main voice; a pick in Settings wins over the file's
  voice and speaker. Each extra voice takes memory: see Voices kept loaded below.
- **Voices kept loaded.** Every different voice besides the main one is loaded on its own: about 100 MB of memory for
  a medium voice, 170 MB for a high one (the people of one many-speaker voice, vctk's 109 say, share a single load).
  Whenever such a voice is in use (a personality's or a crew member's), ⚙ Settings → Voice says how many and what they
  cost on the machine that speaks (amber above 500 MB, red above 1 GB). **Keep loaded** picks how many stay loaded
  beside the main voice (1 up to the voices in use, or all; by default the voices in use, up to 4): a voice set aside
  waits about a second when it speaks again. **Load them at start** (off by default) loads them when Outrider starts,
  so even the first line of each has no delay. Both are written into the config file (`[speech] voices_loaded` and
  `voices_preload`), since they are about that machine, and take effect at once.

**The crew**

Off by default: one voice for everything. Tick **Split the alerts among a crew** in ⚙ Settings → Voice → Crew and each
alert is said by a crew member in its own personality and voice, so you know who is talking (and what about) before
the sentence ends:

| Crew member | Speaks for |
|---|---|
| XO / Co-pilot | the main voice: voice answers, the status report, the co-pilot, the hush and speech on |
| Navigator | jumps and every route line (the Highway, survey and trade routes), fuel short of a refuel, last scoop, auto-target, wrong target, supercharges, surface pins |
| Science Officer | target verdicts, arrivals, the honk, briefings, the FSS, mapped planets, high-g approaches, bio bodies ahead, leaving with work left, codex, phenomena, green gas giants, rare stars, surface sites, signals, curiosities |
| Exobiologist | valuable bodies, sampling, Exomastery routes |
| Chief Engineer | fuel, tank full, scooping stopped, jumponium, hull and heat |
| Quartermaster | sales, unsold data, your carrier and its trips, losses |
| Comms Officer | the game's start and exit, someone scanning your firsts, docking pads and refusals, other players' chat (read aloud, below) |
| Tactical | every danger line (while Danger lines always in Tactical's voice is on) |
| Mining Officer | the Rhino's rigs, rings to mine, limpets and the hold (nearly full, full, where to sell), the prospector call-out and motherlodes |

- **The table.** A row per crew member: an optional **Name** (shown in Settings and the voice lab, and said when another
  crew member mentions it: see Crew lines below), its
  **Personality** (whose lines it says) and **Voice** (and **Speaker**, for a voice of many people), **Chatter** (whether it
  takes part in Space chatter, below), what it **speaks for**, **▶** to hear one of its lines and **↺** to put it back to "as the XO". The XO row is the main voice and the
  personalities you ticked: changing its voice changes the main voice.
- **The XO stands in.** A new crew starts with everyone "as the XO", so switching it on changes nothing you hear until
  you give a member a voice of its own. A member left "as the personality" speaks in that personality's voice
  (Personality voices). Whenever a member cannot speak (its voice not installed or failing to load), the XO says the
  line instead, so no line is ever lost; the table says why under its name, and Show log says it once.
- **Danger lines always in Tactical's voice** (on by default): hull, heat, interdiction, the fuel warnings, your carrier
  leaving without you, a ship lost, a rig too far, so a danger line is never mistaken for chatter. Off, they stay with
  their alert's crew member. Danger still comes first either way.
- **Who says which alert:** ⚙ Settings → Alerts has a **Crew** column while the crew is on: move any alert to another
  member there. A danger alert says "spoken by Tactical (danger)" while that switch is on.
- Outrider keeps the crew, so every browser and the tablet (with Play alerts here) speak with it. The tablet's own
  Settings has none of this: the crew is set on the PC.
- **Crew lines.** With the crew on, some lines have one crew member mention another: "Fuel 18 percent. Ask the Navigator
  for the nearest scoopable star." (about 3 per alert in each personality, for 26 alerts: arrivals, briefings, bodies,
  biology, fuel, the hull, sales, your carrier, the session's end). A member with a name is called by it ("Ask Mira");
  without one, by its role. They are said only while the crew is on (with it off you hear exactly the lines you heard
  before), and never by the member they mention: move the fuel alerts to the Navigator and the lines that mention the
  Navigator are left out for them. **▶ Audition: crew lines** (here and in the voice lab) plays them.
- **Writing your own** (in `speech.json`): any line may name a crew member with these placeholders. Each says the
  member's name when it has one, else its role, with a capital when it starts a sentence (the line's start, or after
  ". ", "! ", "? " or "... "):

  | Placeholder | Says (mid-sentence) | At a sentence's start |
  |---|---|---|
  | `{navigator}` | the Navigator | The Navigator |
  | `{science}` | the Science Officer | The Science Officer |
  | `{exobiologist}` | the Exobiologist | The Exobiologist |
  | `{engineer}` | the Engineer | The Engineer |
  | `{quartermaster}` | the Quartermaster | The Quartermaster |
  | `{comms}` | Comms | Comms |
  | `{tactical}` | Tactical | Tactical |
  | `{mining}` | the Mining Officer | The Mining Officer |
  | `{xo}` | the XO (said "ex-OH") | The XO |

  Talk about the member, never to it ("ask {navigator}", not "{navigator}, plot a course": that would be "the
  Navigator, plot a course"). A line may not mention the member who says its alert (the Engineer never says
  `{engineer}`; danger lines, Tactical's, never `{tactical}`), and every alert keeps lines that mention nobody, for when
  the crew is off: Settings → Voice reports either mistake, and a 👎 that would leave an alert only crew lines is refused.

**What it says**

- **Arrival briefing.** One sentence after the honk: "Known. 12 bodies. Scoopable M star. The Earth-like
  world at A 2 is unmapped, 1.4 million." Entering a new galactic region opens it ("Entering the Norma Arm.").
- **Routine systems: sound only** (a tick, off by default) plays a soft two-note sound instead of the
  briefing where there is nothing to do. A system whose Spansh data predates Odyssey is never routine until your own
  scans have every body: its briefing ends "Spansh's data here is from February 2019, before Odyssey: worth a
  rescan" (and how many thin-atmosphere worlds may hold life), since "everything known" there means little.
- **FSS debrief:** what is worth doing once every body is found. **Signals** as the FSS finds them.
  **The jump line** in the hyperspace tunnel, with whether the star ahead is scoopable, and any hazard.
- **Greeting and goodbye:** what is at stake after a long break (and any core module under your level), and a
  session recap when you quit.
- **Exobiology:** leaving a body mid-run warns; the third sample says what it paid and what is left; within 100 m of
  a plant you tagged where the next sample would count, it says so ("Tagged Tussock, 80 metres").
- **Approach:** "2.6 g. 480 million aboard, 3.2 rebuys. Land gently." (no rebuys for a ship bought with Arx, whose
  hull has no credit value)
- **Fuel:** low fuel where you can't scoop, and the **top-up warning** before a likely dry stretch; on a Highway
  route, "Fuel won't reach Hwy Stop 42, 4 jumps out. Scoop to at least 25 tonnes." (a danger line: business wording
  unless you untick that); at the last scoopable star before a dry stretch, "The next 3 stars on your route are not
  scoopable. This is your last chance to top off before you need to call the Fuel Rats." (a danger line too).
- **Jumponium** (off by default): the best landable body with a material your FSD injections are short
  of ("B 4 has polonium, 1.3 percent.").
- **Mapped** (off by default: **Say when a planet is mapped**, or `speak_mapped`): after each DSS mapping,
  "A 2 mapped efficiently, 3.4 million. Next: biology on C 2, up to 19 million." It says so when you went
  over the probe target, and "Nothing else here over your levels" when the system is done. A map to do next gives
  the body's value without and with your bonuses: "Next: map 7, 771 thousand, 2.2 million with bonuses".
- **Ship-loss debrief:** what went down with the ship and the nearest lost system to go back to.
- **System names said properly:** "Drojau LL-O b26-3" is said "Drojau L L O, b 26 3".

**How it behaves**

- **Most urgent first.** Danger jumps the queue. Lines that waited over 20 seconds, or are about a system
  you've left, are dropped. Charging the frame shift drive clears the queue.
- **No repeats too soon.** Each alert goes through every line in your personalities before any comes round
  again. The browser remembers what you have heard across reloads.
- **Hush.** The **▾** beside 🗣 hushes for 10 minutes, 30 minutes or until the next jump. Danger and anything
  you ask for still speak. The hush is kept by Outrider, so a hush from a tablet, the co-pilot button or a
  [question by voice](#-ask-outrider-by-voice) ("hush for ten minutes") quiets the PC too.
- **One window speaks.** With the page open in several windows, only one speaks and plays sounds, so nothing
  is said twice. **Speak from this window** takes over; **This screen speaks: auto / always / never** sets it
  per browser. A tablet with **Play alerts here** speaks as well, whatever the PC does (see On a tablet).
- **Play speech and sounds on this PC.** Ticked in the dialog, the PC running Outrider plays the voice and
  sounds itself: no click to allow audio, and the voice comes from the PC even with the page on a tablet (a page
  must still be open). Linux only: `pw-play`, `paplay`, `aplay` or `ffplay` (`[speech] server_player`). Not in
  Docker: a server has no speakers to play on.
- **Volume** (in the dialog, per device) sets Outrider's own voice and sounds, in the browser or on the PC.
- **Your own sounds:** `[speech] sound_dir` names a folder of `<name>.wav` files (fanfare, thud, chime, alert… the
  names in `static/sounds.json`), up to 3 seconds each; each replaces that sound in the browser and on the PC. The
  dialog lists the ones it uses and why any file is not used.
- **The jump line** ("Jumping to Hwy Stop 38") is said once you are in the hyperspace tunnel, not over the game's
  own countdown call; it has its own varied lines in `speech.json` (`fsd_charge`). The scoop and hazard warnings
  are said after it.
- **The last line said** shows beside the header's icons, with ▶ to hear it again.
- **Lost contact.** If Outrider stops answering for 30 seconds, the speaking window says "Lost contact with
  Outrider. No alerts until it is back." in your Piper voice (made in advance while the link was up; without Piper,
  the alert sound), and "Back in contact" when it returns.

**Space chatter**

Off by default. Tick **Talk in quiet moments** in ⚙ Settings → Voice → Space chatter and, after a while with no alert,
someone says something: in supercruise, or while you are on foot or in the SRV on a planet.

- **What it says:** every personality has its own. On its own, about 60 lines for supercruise (some knowing the
  system, how long you have been in supercruise, the session's jumps and first discoveries) and 30 each for a planet
  with the ship landed nearby or up in orbit. Between stations, a question and an answer on 18 topics, mostly their
  own work (fuel, the route, the drive, the ship, biology, the stars, the money, mining, threats, traffic, the
  captain, a quiet watch) and sometimes something personal (family, home, food, the best day, a fortune, life
  before this ship), about a dozen of each per personality, with swearing versions for the personalities that swear.
  **▶ Try chatter** says one now.
- **When:** never while you are docked or on foot in a station, in a taxi or multicrew, in danger, overheating, low on fuel, charging the
  FSD, low on oxygen or health on foot, or with a map, the FSS, the DSS or the codex open. The data you carry never stops
  it. It waits a minute after you enter supercruise or step out on a planet. It never talks over anything said or
  waiting to be said, and an alert always comes first.
- **How often**, five steps from quietest: Rare, Occasional, Normal, Chatty and Non-stop. Each sets the quiet before
  it talks: no alert for 15, 10, 7, 4 or 2 minutes, and 15 to 30, 10 to 20, 7 to 14, 4 to 8 or 2 to 4 minutes since
  the last chatter. Rare also stops at 3 an hour.
- **With the crew on,** the stations talk among themselves. Now and then one asks another about its work (fuel, the
  route, the stars, the money, the life you sample...) or, about a quarter of the time, something personal, and
  gets an answer, sometimes with a last word back. Two stations of the same personality, or with the same voice,
  never talk to each other. They call each other by name when you gave one, else by station. The Crew table's **Chatter** column leaves any of them out.
- **Name the speaker in captions** (per browser) puts "Engineer (Mira):" before each line.
- If an alert comes in mid-conversation, the rest of the conversation is dropped. Chatter lines can be banned in
  Spoken lines like any other.

**Chat read aloud**

Off by default. Tick **Read aloud** on the **Chat** line in ⚙ Settings → Voice and Comms reads other players'
messages to you: squadron, wing and direct messages by default, local and voice chat if you tick them, NPCs never.

- **How it starts:** `<CommanderName>: …` (the default), `Commander <CommanderName> on <Channel>: …` (say,
  "Commander Kurbo on Squadron: …"), or the message alone. The caption strip always shows `<CommanderName>: …`.
- **The pace:** several messages from one commander in a row are read as one; at most one every 15 seconds; with
  more waiting, the first is read and the rest summed up ("And 3 more on Squadron"); anything waiting over a minute is
  shown in the captions but not read. A message that mentions your commander name is read at once, even from a
  channel you did not tick.
- **As written:** a link is said "a link", emoji are left out; their words, swearing included, are read as they wrote
  them (your profanity setting is about Outrider's own lines). Up to about 300 characters, then "and more".
- **When:** after any alert, never while hushed; only what arrives while the page is open (never a backlog).
- **🔇 in Spoken lines** beside a chat line mutes that commander; the Chat line lists the muted ones with ✕ to undo.
- It is the **Players' chat** row of ⚙ Settings → Alerts (speak only, by default): the overlay's Alerts panel shows it there.
- **Private:** other players' words are never written to Outrider's log or its database, and never kept in the
  voice's cache.

**Spoken lines: what was said, and banning lines**

Open ⚙ Settings and its **Spoken lines** section. It lists this
window's last 100 alerts and what became of each: said, cut short, dropped or silent, and why. **copy**
puts it on the clipboard.

- Above the list, **This session** counts each alert's lines, noisiest first ("Arrival brief 42 · FSD charge
  40 (3 dropped)"). **🔇** beside one stops speaking that alert (its 🗣 tick), with an undo.
- Press **👎** beside a line to never hear that wording again, in any browser.
- "3 lines banned · review / undo" above the list lets you take a ban back.
- Bans live in `data/speech_banned.json` (beside your own copy when `speech_file` names one), so editing
  `speech.json` never loses them.
- The last line of a list can't be banned, so no alert ever goes quiet.

## 🎙️ Ask Outrider by voice

The Android app asks Outrider a question out loud, after its wake word or a tap on Ask. The answer is said in your
Piper voice by the window that speaks (a PC browser, or the tablet with Play alerts here) and shown as a caption on
every open page. Outrider knows these without any AI: **status report, fuel, unsold, next jump, what's left here,
nearest unvisited, nearest station** (or carrier, Vista, cartographics, repair, refuel, shipyard, material trader,
raw material trader, "where can I sell": see
[Nearest place to dock](plot-route.md#-nearest-place-to-dock); a place further than 500 ly also gets a neutron route
plotted there while you follow none), **nearest green gas giant** (a guess from what
Outrider has cached: see [Potential green gas giants](views.md#-potential-green-gas-giants)), **FSD injections**
("can I still make an FSD injection?": how many of each grade, and what runs out first when it is two or fewer),
**how far today** (jumps, light years, first discoveries, maps and samples since midnight; "how far this session"
for the latest session), **this body** (the body you are on, fly near or have targeted: its type, gravity, value,
biology and geology), **left behind** (the nearest one or two systems within 100 ly with work over your
`body_highlight_level` and `bio_min`), **hush** and **unhush**. A hush can take a time: "hush for ten minutes",
"quiet until the next jump" (30 minutes when you say none; another time gets the nearest of 10, 30 minutes or the
next jump). Their phrases are in `resources/ask.json`; edit them freely (Outrider reads them at start).

**Voice commands** (⚙ Settings → Voice, the fold at the end; on the tablet, Settings → **Voice commands…**) lists
them all, grouped, from that file: what each one does, every phrase that asks it, and the words that narrow it ("vista",
"repair", "carrier", "raw" beside "trader"; "for ten minutes", "until the next jump"; "session"). Find a setting finds
it by "voice commands" or "phrases", and by a phrase's own words ("nearest vista").

**Questions asked** (⚙ Settings, the last section) shows what the voice heard, newest first: the words, which phrase
they matched and what that asks for ("matched “status report” → a status report"), or "no phrase matched (AI off)",
or what the AI did (its rounds and the tools it looked at, or why it failed), then the answer. A misheard word or two
phrases that clash show up there; **copy** puts it on the clipboard. Outrider keeps the last 50 questions from every
device in its memory only (a restart clears them), behind the password like the rest of the page, and never the AI's
key.

Anything else goes to an optional AI layer, off by default (`[assistant] enabled = false`, also in ⚙ Settings →
Server). It sends nothing anywhere until you set it up: an OpenAI-compatible endpoint (`base_url`: Ollama on your PC,
Venice.ai, OpenAI, OpenRouter...), a `model` that can call tools, and an `api_key` that never leaves Outrider. The AI
gets the same read-only tools as the MCP bridge, so it can look things up but never act. Privacy: with a cloud
provider, your question and what the tools answer go to that provider; a local model keeps everything at home. Try
your model with real questions: tool calling varies, and a slow model runs into `timeout`.

## 🤖 Ask an AI about your game

An AI client you already use (Claude Code, the Claude desktop app, or any other MCP client) can ask Outrider questions
in plain language: "what's worth landing on here?", "how much am I carrying unsold?", "what's left within 50 ly?",
"how far to the next refuel on the highway?". Your client starts `python3 -m outrider.mcp` when it needs it (nothing
to run or switch on in Outrider), which reads your running Outrider and answers through twelve read-only tools: current
status, this system, nearby systems, the nearest unvisited system, the nearest place to dock, the nearest potential
green gas giants, one body, unsold data,
work left behind, the Highway route, travel history and materials. It can only read: it never presses keys, plots, bookmarks or hushes
anything. Nothing extra to install.

- **Claude Code**, from the Outrider folder: `claude mcp add --transport stdio outrider -- python3 -m outrider.mcp`
  (add `--scope user` to have it in every project). Use the venv's python if Outrider runs in one.
- **Claude desktop app:** add to `claude_desktop_config.json` under `mcpServers`:
  `"outrider": {"command": "python3", "args": ["-m", "outrider.mcp"], "cwd": "/path/to/Outrider"}`.
- **An Outrider elsewhere** (a Docker server): the bridge runs on the computer with your AI client, from a checkout
  of this repository; set `[mcp] url` (`"http://server:8025"`) and `[mcp] password` (its `[server] password`; or
  `--url` and `--password`), and it signs in.
- If Outrider isn't running, the tools say so. `[mcp] max_rows` caps how many rows a list answers with (25).
  `python3 -m outrider.mcp --list` shows the tools.
- **Privacy:** Outrider uploads nothing, but what the tools answer goes to your AI client's provider like anything
  else you type into it. A client running a local model keeps everything on your PC.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · **Voice and alerts** · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
