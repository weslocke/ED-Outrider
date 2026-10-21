[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · **Uploads** · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Uploads: EDDN, EDSM and Inara

Outrider can send what your journals say to three community services, as EDMC does, so you need not run EDMC just to
upload. **All are off unless you switch them on**, in Settings → Uploads. The switch applies at once and is kept in
the config file (`[eddn] enabled`, `[edsm] enabled`, `[inara] enabled`) for the next start; it is the only place to
switch them (they are not among the Server settings).

- **EDDN**, the Elite Dangerous Data Network: systems, scans, signals, codex entries, biology samples, settlement
  approaches, docking answers, markets, outfitting, shipyards, carrier materials, plotted routes, sent as they happen.
  Spansh, EDSM, Inara and others read it. EDDN gets your
  commander name and hashes it before anyone else sees it; personal details (fines, fuel, wanted, where your ship is)
  are taken out first. Codex entries and biology samples keep where on the planet they were found: that is the data
  (a sample's place only when it was read live, at the moment of the scan).
  Station data goes once per visit: each docking sends it again, changed or not, since the sites date a station's
  data by it.
- **EDSM**, the Elite Dangerous Star Map: your flight log, scans, materials, ship and cargo, to your own EDSM account.
  It goes in batches: each jump or docking sends what waited, and nothing waits more than five minutes. EDSM says
  which events it does not want, and those are not sent.
  - It needs your EDSM commander name and API key ([edsm.net → Settings → API key](https://www.edsm.net/en/settings/api)),
    per in-game commander, set in Settings → Uploads. The key stays on this Outrider: the page shows only its first
    and last four characters, to compare with edsm.net.
  - A commander with no key sends nothing, and Settings says so.
  - A key EDSM refuses stops the sending (not the recording) until you change the key, press **Try again** in
    Settings → Uploads, or switch EDSM off and on: what you played meanwhile then goes.
  - **Check** beside the key asks EDSM whether it takes that name and key (the one typed, else the one saved), without
    sending anything: "✓ EDSM accepts CMDR … with this key", or "✗ EDSM: 203 commander name or API key not found". A
    check that works with the saved key ends a hold at once. One check every 10 seconds.
  - If EDSM keeps refusing a key you know is right, make a new key on edsm.net and paste that one.
- **Inara**: keeps your commander profile there current, as EDMC's Inara upload does, so a player who uses Outrider
  alone loses nothing on it:
  - your flight log and location (jumps, carrier jumps, dockings, landings), credits (once per session, the game's own
    figures at login), the game's statistics;
  - every rank and its progress (Combat, Trade, Exploration, CQC, Mercenary, Exobiologist, the two navies), Powerplay,
    the engineers;
  - reputation with the superpowers and the factions you meet;
  - materials, your ship's cargo and the ship locker; the ship you fly and its loadout, your fleet (bought, sold,
    swapped, sent elsewhere, renamed, where each one is) and your stored modules;
  - community goals you take part in, missions, the combat log, friends and suit loadouts.

  Never anything about your fleet carrier (Inara's API has no carrier hold) or the SRV's cargo.
  - It goes in batches (each jump or docking, the end of your login, at most five minutes' wait), at most one request
    every 35 seconds, and only what changed since your profile last got it: the game rewrites your ranks, cargo and
    loadout often, and Inara asks apps not to send the same thing twice.
  - It needs your Inara API key ([inara.cz → Settings → API key](https://inara.cz/elite/cmdr-settings-api/)), per
    in-game commander, set in Settings → Uploads. The key stays on this Outrider: the page shows only its first and
    last four characters.
  - A commander with no key sends nothing, and Settings says so. Once you enter a key (or another one), your ranks,
    ship, inventory and the rest go whole again the next time the game writes them, most of it at your next login.
  - **Switch Inara off in any other app first** (EDMC, EDDI, EDDiscovery, EDDLite): two apps sending can get your key
    revoked. Outrider sees EDMC's setting on this PC and holds its own while EDMC sends; it cannot see the others.
  - A key or app Inara refuses stops the sending (not the recording) with Inara's words in Settings, until you change
    the key, press **Try again** or switch Inara off and on. A refusal for sending too often waits an hour by itself.
  - **Check** beside the key asks Inara for that commander's profile with the key (the one typed, else the one saved),
    without sending anything: "✓ Inara: CMDR …" with a link to the profile, "✗ Inara refused the key: …", or "Couldn't
    reach Inara: timeout". It keeps to the same 35-second pace as the sending, so it can take a moment.

## Catching up, and what is never sent

Each upload remembers how far through your journals it has got. If Outrider was not running while you played (or the
server was down), the next start sends what you played meanwhile: to EDSM and Inara up to a week back, to EDDN only the last
hour, since EDDN's readers take what arrives as current. For the same reason an EDDN message that could not go for an
hour (EDDN unreachable) is dropped, not sent late. A journal re-read sends nothing twice, a restored backup starts
from where your journals are now, and switching an upload on starts from that moment: your history is never uploaded.

Markets, outfitting, shipyards, carrier materials and plotted routes come from files the game rewrites each time, so a
catch-up can send one only while the file is still the one that visit wrote (the last one, after a short gap). Live,
Outrider waits up to about half a minute for the game to write the file (it can write a fleet carrier's market well
after the line); if it never comes, that one is not sent, and Outrider's log says so with what the file held. A codex
entry caught up late has no body name, and a biology sample caught up late no position: both come from the live
Status.json.

Never sent:

- Anything older than a week (an hour for EDDN), or from a legacy folder (journals imported once). The one exception
  is a range you send to EDSM yourself ([Fill gaps in EDSM's flight log](#fill-gaps-in-edsms-flight-log)).
- Anything from the game's beta, or from the Legacy game (3.8): Settings says so ("unavailable: the Legacy game").
- Anything while you are crew in another commander's ship.
- Anything under `--simulate`.

## One uploader at a time

Two Outriders reading the same journals (the game PC's and a server's), or Outrider and EDMC, would send everything
twice: EDDN has no way to tell. So:

- **A note in the journal folder.** Each uploading Outrider leaves one (`.outrider/uploads-<id>.json`, rewritten every
  minute). Another Outrider that sees a fresh note will not start the same upload ("Already uploading from
  erangel"). If two are switched on for the same upload anyway (both started with it on), the one already sending
  keeps it and the other gives way and says so; started together, they agree on one. An Outrider older than
  2026.10.19.1 is always given way to.
  - A note left by a crash goes stale after five minutes; one untouched for an hour is ignored at once.
  - When an Outrider stops, its note stays with how far it got: switch the upload on in another one and it starts
    there, with nothing missed and nothing sent twice. An Outrider that was giving way takes over from there too
    (it notices within a minute, then sends what was played since the stop). After a crash it takes over from
    the crashed one's last note, once that has gone stale.
- **While another uploader has it.** While EDMC or another Outrider sends a service, this one follows the journal
  without sending, and catches none of that up later.
- **Catching up cannot know everything.** If EDMC, or a read-only Outrider (which leaves no note), sent while this
  one was not running, it is sent again. Keep one uploader.
- **A read-only journal folder.** An Outrider that cannot write there (a read-only share) still reads the others'
  notes. If another one already uploads, it refuses ("Filesystem is read-only and another instance is set for
  upload"); otherwise it asks first: "Is this the only Outrider uploading? Other instances can't see this one".
- **In Docker** the journals are mounted read-only.
  - To give the server its note folder, create it on the share (`mkdir -p "$JOURNALS/.outrider"`, as the share's
    owner) and uncomment the `.outrider` line in `docker-compose.yml`.
  - If the share itself is read-only on the server (an `ro` export or mount), leave that line commented: Docker
    cannot create the folder there and the container would not start. Outrider then works as a read-only instance.
    It sees the game PC's note, but the game PC cannot see its own, so if the server uploads, keep the game PC's
    uploads off yourself (that is what the "only Outrider" question is about).
  - Its note names it "outrider-docker"; set `OUTRIDER_HOST` in `.env` for another name.
- **EDMC on the same PC.** If it runs with its own EDDN, EDSM or Inara upload on, Outrider holds that upload and says
  so. Switch EDMC's off (its File → Settings → EDDN / EDSM / Inara tabs) before switching Outrider's on. EDMC on another
  computer cannot be seen: switch it off there yourself, as in EDDI or EDDiscovery for Inara.

## Status

The header's Data tile shows, live, a line per upload in use: what it sent, has waiting and had refused in the last
day. Settings → Uploads shows the same per service, with why nothing can be sent now (held by another uploader, a key
EDSM or Inara refused, the beta or Legacy game) and the last message (a refusal, "saved"). Under each service:

- **Recent**: its last sends, newest first. Sends in a row are one line ("12:04 sent 37 (11:58–12:04)"); a failure says
  what kind and the service's or the network's own words, and when it tries again ("11:58 ✗ no network: Cannot connect
  to host … · trying again at 12:00"). Kept until Outrider stops.
- **At start**: what it did when Outrider started: "12 messages from while Outrider was off", "nothing missed", "EDMC
  was sending EDSM" (then nothing of that stretch is sent), or "nothing from before" (no earlier mark: it starts from
  your journals' end).
- **On hold**, with **Try again**: a key EDSM or Inara refused (Try again sends with the stored key now), or a kind of
  EDDN message (below).

If EDDN refuses one kind of message (markets, say) three times within an hour, or once with 426 (a version it no
longer takes), Outrider stops sending that kind until it restarts or you press Try again: usually a game update EDDN
does not take yet. The other kinds still go. The refused ones are gone; Try again lets new ones go.

**When a service is down.** If an upload that is on has failed for 15 minutes with messages waiting, a card says so at
the top of the page ("EDDN unreachable for 15 min: 42 messages waiting, they drop after an hour (the oldest in 38
min)"; for EDSM and Inara "kept until it answers") and, with notifications on, a desktop notification. It is never
spoken. ✕ hides the card; it goes by itself when the service takes messages again, with a notification ("EDDN sending
again after 37 min: sending the 40 waiting (2 were over an hour old and dropped)"). Its row in Settings → Alerts
switches the notification. Inara asking Outrider to slow down (its hour's pause) is said that way. What waits keeps its
order: while a batch waits to be tried again, nothing newer goes ahead of it.

A developer's switch shows next to the service in Settings → Uploads: "(test schemas only)" when `OUTRIDER_EDDN_TEST`
is set, "(dry run: nothing sent)" when `OUTRIDER_EDSM_DRYRUN` or `OUTRIDER_INARA_DRYRUN` is (the requests go to
`data/edsm-dryrun.jsonl` / `data/inara-dryrun.jsonl`, never the key), "(development mode)" when `OUTRIDER_INARA_DEV`
is (Inara's `isBeingDeveloped`: for a test account).

## Upload marks in the Log

With an upload on, each line of the **Log** says what the uploads made of it, beside its summary: **✓ EDDN · ✓ EDSM**
(sent), **⏳** (waiting: for the next jump or docking, or to try again), **⏸** (on hold: a key refused, a kind of
message EDDN keeps refusing, the upload switched off) and **✗** (not taken, or dropped). Hover a mark for why, in the
service's own words. A line with no mark had nothing to send; a line sent as several messages shows the worst of them.

- Marks cover the last 7 days: Outrider forgets what it sent after a week.
- **not sent** (beside "show noise", while an upload is in use) shows only the lines with a message waiting, on hold or
  not taken, whatever the category boxes say: some "noise" (a signal source, a market) goes to EDDN too.

## Fill gaps in EDSM's flight log

EDSM's flight log has what was sent to it. If you played before you switched EDSM on in Outrider, or while it was off,
that stretch is missing there. Settings → Uploads → **Fill gaps in EDSM's flight log** sends it, once you have looked:

- **Check EDSM's log** asks EDSM (reading only) where its flight log ends before Outrider took over: "EDSM's flight log
  ends 2026-10-09 21:14 UTC at …; Outrider has sent since 2026-10-11 08:00 UTC; your journals have 412 jumps between".
  It fills **From** and **To** with that stretch. If EDSM was switched on in Outrider before this version, when it
  started sending is not known ("unknown"): then the range runs to now, and you set the end yourself.
- **Preview** rebuilds, from your journals (the live folders, the legacy ones and the backups' journal archive), what
  Outrider would send EDSM for that range, sending nothing: "312 events (41 jumps) in 2 requests, about 1 min". Times
  are UTC.
- **Send** (only for the range just previewed, after you confirm) first asks EDSM for its flight log over the range:
  if EDSM has anything there, nothing is sent (never twice what EDSM has); pick a range around it. Then it sends one
  request every 10 seconds. Its line counts what EDSM did with each event: stored, already
  there, older than its log (not taken). If EDSM takes none of the first request because each event is older than what
  its log has, the backfill stops by itself: EDSM does not take back-dated events then.
- **Stop** ends it (what still waits is not sent). A key EDSM refuses holds it until you fix the key and press **Go on**.
  It waits ("paused") under `--simulate` and while another Outrider uploads to EDSM: only one talks to EDSM.
- If EDSM does not answer the Check or Send's first look at its log (a timeout, no connection, EDSM failing or asking
  to slow down), Outrider asks again after 30 seconds, 1, 2, 5 and 10 minutes, and the line says when ("EDSM not
  answering: trying again at 21:30 (attempt 2 of 6)"); only then does it give up. **Stop** on that line ends the wait.
  A refused key stops it at once.
- What EDSM stores cannot be taken back from here. Try a small range first (a jump or two), and look at your flight
  log on edsm.net before sending a long one.

## Import your EDSM flight log from before your journals

If EDSM has your travels from before your oldest journal (sent by another app, or journals since deleted), Outrider can
bring them in once, reading only: Settings → Uploads → **Import your EDSM flight log from before your journals**, pick
the commander (one with an EDSM key saved) and press **Import**.

- It reads EDSM's flight log one week at a time, back from your first journal to the game's launch, one read every
  10 seconds: several years take an hour or more. Nothing is sent to EDSM. **Stop** keeps what was read; **Go on**
  carries on from there (also after Outrider was stopped).
- A week EDSM does not answer (a timeout, no connection, EDSM failing) is asked again after 30 seconds, then 1, 2, 5
  and 10 minutes: "EDSM not answering: trying week 203 again at 21:30 (attempt 2 of 6)". Only when EDSM stays silent
  through all of that (about 20 minutes) does the import stop, saying why; **Go on** then carries on from that week.
  The same goes for the lookups of places at the end (Spansh or EDSM). A refused key (EDSM's "commander name or API key
  not found") or an answer Outrider cannot read stops it at once, with no retry.
- Then: "1,288 visits from EDSM, 2016-03-02 to 2019-11-30 · **Remove them**". Remove forgets them all (your journals'
  visits are not touched) and you can import again.
- Those systems count as **visited**: Nearby's marks, Search's visited filter, the target's verdict, Find ("visited 3×
  by your EDSM flight log"), the boxel lists, the Map (its hover says so) and History, whose sessions show "from EDSM"
  with a From EDSM line beside All time.
- They never count as first discoveries, sales, scans or anything else you did there: EDSM's log says where you went,
  your journals say what you did. Your journals always win: an entry within a minute of a journal arrival, or from after
  your first journal, is left out (and if you add an older journal folder later, what it covers becomes the journal's).
- Every commander whose log you import counts as you.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · [Cargo and trading](cargo-and-trading.md) · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · **Uploads** · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
