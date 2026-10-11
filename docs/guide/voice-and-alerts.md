[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · **Voice and alerts** · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Voice and alerts

## 🔔 Alerts

Alerts fire only for something out of the ordinary. Each can play a sound (🔊), show a desktop
notification and be spoken (🗣), chosen per alert in **⚙ Settings → Alerts**:

- a new discovery targeted, or arriving somewhere nobody has been
- leaving with mapping or bio over your levels undone, or a first-discovered Earth-like, water, ammonia or
  terraformable world unmapped
- a valuable body the moment the FSS resolves it, and a new codex entry. A body someone else has already mapped is
  never pointed out (nor warned about when you leave): the first one in a system gets one line instead, "Already
  mapped, but there are still valuable bodies to map if you want to jump on the train"
- low fuel where you cannot scoop, and a top-up worth taking before a dry stretch
- docking where the station buys your data, and what you banked when you sold
- a sale that left data aboard (Universal Cartographics sells 50 systems a page; at Vista Genomics, the species
  you kept back), said 90 seconds after the last page
- hull damage, heat damage, interdiction, and unsold data past a threshold
- your carrier arriving somewhere new or leaving without you
- a Rhino mining rig nearing the 5 km leash (see The surface map)

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
| Unsold data | 50M / 250M | When the header turns amber and red, or as a multiple of your rebuy. |
| Body highlights | 500k / 10M | Here's row turns green (scan + map) or its bio violet (species) over these. Bonuses left out. |
| Approach warning | 2 g | Gravity at which orbital cruise at a landable body warns you, with data over the amber level. |
| Max with bonuses | on | Whether Here's Max column counts first-discovery, mapping and footfall bonuses. |
| Codex finds count | on | A body whose likeliest species is new to your codex in this region (✦) is worth stopping for, whatever its value. |
| Discovery streak | 10 / 5 | Known or undiscovered systems in a row for a spoken line (0 turns it off). |
| Suggested order | 100k/min | Supercruise credits per minute under which Here marks "skip?". |
| Fuel alerts under N jumps | off | Warns once when jumps left at your pace fall under N; also sets the top-up level. |
| Core modules | 80% | A core module under this shows under hull and is said in the status report. |
| Surface map | 1,000 m / 500 m / 50 m / 3,500 m | Altitude it shows below, narrowest view, rig spacing ring (0 = none), rig leash warning. |

**Export settings** and **Import settings** move them to another browser profile. **Use these for new
browsers** keeps a copy on the server (`data/browser_defaults.json`, included in backups), so a tablet running
Now starts with your voice, names and alert choices. The view and layouts stay per device.

Targeting a system plays its sound; arriving is announced by the voice. Walking about a station counts
as docked. A carrier jump booked just before you quit shows as "not yet confirmed" until your next login.

## 🗣 The voice

Alerts are spoken when 🗣 in the header is on. **Piper**, a neural voice running on your CPU, sounds far
better than the browser's own voice. The voice is Cori (`en_GB-cori-medium`) unless you pick another, and it
downloads into `data/piper-voices/` the first time. ⚙ Settings → Voice switches between installed voices, and its
**More voices** lists every Piper voice by language: pick one and Outrider downloads it and switches to it (on a
Docker server too).

Without Piper installed, the browser's own voice speaks. With Piper, the browser's voice is never used: a line Piper
can't say is not said (what you asked for is still shown as a caption).

**Body names are said letter by letter.** With an English Piper voice, "A 1" is "ay one" (not "uh one") and "ABC 3 a"
is "ay, bee, see, three, ay", each letter clearly. Only a body's letters are spelled out: system, station and carrier
names are read as they are written.

**"Click Here To Allow Audio".** A browser plays no sound on a page until you click on it, and Outrider reloads the
page itself after an update. When the window that speaks is held back like this, a red **🔇 Click Here To Allow
Audio** pill appears on the menu bar (and 🔇 in the tab's title), the tablet's caption line says the PC's page needs a
click, and the lines wait: they play once you click, or are dropped if they are no longer news. "Play speech and
sounds on this PC" needs no click. To never be asked, allow sound for the page in the browser (Chrome: Site settings →
Sound: Allow; Firefox: Autoplay: Allow Audio and Video).

**Choosing how it sounds**

- **Personalities.** Down to business, sarcastic and sweet, up to fifty lines per alert each (fifty for most); tick
  any mix.
  **With profanity** uses the swearing versions the share of the time you set (50% by default). **One personality per system** holds one character a system.
- **Danger alerts always down to business** (on by default): danger is said plainly, never sworn.
- **Your names.** Commander names are often unpronounceable, so the voice calls you by the names in
  **Call me** (default "Boss, Hefay, Sir").
- **Speed.** 1× is the voice's own pace. Some Piper voices respond to it less than others.
- **Your own lines.** Edit `resources/speech.json` (or a copy named by `speech_file`) to change lines or add a personality; no restart needed.
- **A voice per personality.** In `speech.json`, a personality can name its own installed Piper voice and
  speed: `"sarcastic": {"label": "Sarcastic", "voice": "en_US-ryan-high", "speed": 1.1}`. Each extra voice
  takes 60–100 MB of memory.

**What it says**

- **Arrival briefing.** One sentence after the honk: "Known. 12 bodies. Scoopable M star. The Earth-like
  world at A 2 is unmapped, 1.4 million." Entering a new galactic region opens it ("Entering the Norma Arm.").
- **Routine systems: sound only** (a tick, off by default) plays a soft two-note sound instead of the
  briefing where there is nothing to do.
- **FSS debrief:** what is worth doing once every body is found. **Signals** as the FSS finds them.
  **The jump line** in the hyperspace tunnel, with whether the star ahead is scoopable, and any hazard.
- **Greeting and goodbye:** what is at stake after a long break (and any core module under your level), and a
  session recap when you quit.
- **Exobiology:** leaving a body mid-run warns; the third sample says what it paid and what is left; within 100 m of
  a plant you tagged where the next sample would count, it says so ("Tagged Tussock, 80 metres").
- **Approach:** "2.6 g. 480 million aboard, 3.2 rebuys. Land gently."
- **Fuel:** low fuel where you can't scoop, and the **top-up warning** before a likely dry stretch.
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
  you ask for still speak. The hush is kept by Outrider, so a hush from a tablet or the co-pilot button
  quiets the PC too.
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

**Spoken lines: what was said, and banning lines**

Open ⚙ Settings and its **Spoken lines** section (the last one). It lists this
window's last 100 alerts and what became of each: said, cut short, dropped or silent, and why. **copy**
puts it on the clipboard.

- Above the list, **This session** counts each alert's lines, noisiest first ("Arrival brief 42 · FSD charge
  40 (3 dropped)"). **🔇** beside one stops speaking that alert (its 🗣 tick), with an undo.
- Press **👎** beside a line to never hear that wording again, in any browser or in the voice lab.
- "3 lines banned · review / undo" above the list lets you take a ban back.
- Bans live in `data/speech_banned.json` (beside your own copy when `speech_file` names one), so editing
  `speech.json` never loses them.
- The last line of a list can't be banned, so no alert ever goes quiet.

**The voice lab.** `python3 voice_lab.py` opens a small window for trying voices before you settle on one.
Play a random line from any alert and personality, or type your own; Save WAV keeps it. **✂ Cut this line**
bans it, like 👎. **▶ Audition** plays eight key alerts in a row. The lower half lists every Piper voice on
Hugging Face: double-click one to download it for Outrider too.

## 🎙️ Ask Outrider by voice

The Android app asks Outrider a question out loud, after its wake word or a tap on Ask. The answer is said in your
Piper voice by the window that speaks (a PC browser, or the tablet with Play alerts here) and shown as a caption on
every open page. Outrider knows these without any AI: **status report, fuel, unsold, next jump, what's left here,
nearest unvisited, nearest station** (or carrier, Vista, cartographics, repair, refuel, shipyard, "where can I
sell": see
[Nearest place to dock](plot-route.md#-nearest-place-to-dock)), **hush** and **unhush**. Their phrases are in `resources/ask.json`; edit them freely.

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
to run or switch on in Outrider), which reads your running Outrider and answers through eleven read-only tools: current
status, this system, nearby systems, the nearest unvisited system, the nearest place to dock, one body, unsold data,
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

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · **Voice and alerts** · [Automation](automation.md) · [On a tablet](tablet.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
