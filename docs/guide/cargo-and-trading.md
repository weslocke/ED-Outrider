[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)

# Cargo and trading

## 📦 Cargo and your carrier

The **Materials** tab starts with your **Cargo**: your ship's hold and your fleet carrier's. The **Carrier tile**
shows your carrier's tritium, its trip to you, its services and its upkeep.

### Your ship's hold

- **Exact:** the game writes it whole, and Outrider follows the changes in between. That includes limpets bought,
  sold, synthesised and launched, which the game counts without writing the list again.
- **What you paid:** each commodity shows the game's own average over your purchases ("Avg 45,210 cr/t (2 lots)").
  Mined or transferred tons have no price.

### Your carrier's hold

Your fleet carrier's hold is not written anywhere whole, so Outrider tracks it. Each line carries a mark:

- ✓ **confirmed**: a commodity on a **sell order** at your carrier. Opening its commodity market lists every sell
  order with its stock, and that stock is the count.
  - Put a sell order (at a price nobody will pay) on everything you want counted.
  - From a day on, the mark says how old that count is ("✓ 9 d", amber after a week). After a week the carrier's
    heading asks you to open its commodity market while docked there to refresh them.
- ◷ **last seen**: everything else, followed from your journal (transfers, your own buying and selling there, orders
  set and cancelled).
  - Other players' trades with your carrier are written nowhere in your journal: a buy order's filled part is worked
    out the next time you open the market.
  - When a market read finds the carrier holding less than is tracked, a last-seen line with no news for 30 days is
    dropped. **Recount…** puts back one that is really there.
- ✎ **entered**: a count you typed in.
  - **Recount…** lists the lines Outrider cannot confirm; the game's Inventory screen at your carrier shows them all.
  - **+ Add a commodity** takes the names your journal has given and those Spansh lists. Anything else (a typo) is
    refused with the closest names: "Not a commodity: “Titanum”. Did you mean: Titanium Tritium", and a click puts one
    in.
  - A new line with no name, or no tons, is said on Save ("the new line needs a commodity name"), not dropped.
- **The total** is checked against the carrier's own ("✓ in sync: 16,085 t", or the tons not accounted for).
- **Why this way:** it is the only way to track a carrier's cargo without signing in to Frontier's servers (their
  companion API, as EDMC and Inara do). Outrider deliberately never does that: it reads your own journal files and
  queries only public, read-only services, so your Frontier account is never involved.

### The Carrier tile and tritium

- **Tritium:** the tile shows the tritium in its depot ("Tritium: 1,000t"). While tritium is on a sell order, the
  total with the hold is beside it ("Tritium: 1,000t/14,199t").
- **Its hover** says how many 500 ly jumps that gives. It is worked out jump by jump with the game's fuel formula,
  the depot topped up from the hold as it runs low. The carrier's cargo weighs; the space a buy order only reserves
  does not.
- **Between readings:** the journal reads the depot only when you open the carrier's management (or deposit
  tritium). After a jump since, the tile shows "≈534t", the reading less the jumps' burn, until you open it again.
- **Checked against your carrier:** the game's fuel formula is checked against your carrier's own jumps, from what
  the depot held before and after each one (its stats and your tritium deposits).
  - Once three are measured, their median scales the figures (at most ±20%), and the hover says so ("checked against
    your carrier's last 12 jumps: no correction needed").
  - Tritium other players donate is not in your journal, so such a jump reads low; the median rides over it.
- **No carrier** of yours or your squadron's, no tile.
- **Decommissioning:** a carrier being decommissioned says so in red with the scrap date. Once it is gone, the tile
  says "Decommissioned" and the date; a carrier bought since takes its place.
- **Your squadron's carrier** shows on the tile too, with an **FC | SC** switch when you have both (see
  [the header and its tiles](views.md#-the-header-and-its-tiles)). A member's journal holds no cargo or balance of it,
  so what follows is your own carrier's.

### The trip to you

While your carrier is elsewhere (and no jump or carrier trip is under way), the tile says what meeting takes, short:
"To it 5 jumps · to you 3, ≈340 t". That is your jumps to it (amber when your tank covers fewer), then its carrier
jumps to you and their tritium.

- **Short of tritium:** when the depot holds less, "140 t short" shows in red.
  - It is amber when tritium on a sell order in its hold covers it. The hover then says whether to move it into the
    depot before the jumps, or top it up again on the way when it needs more than the 1,000 t depot takes at once.
  - "(aboard)" when the tritium in your ship's hold covers it: deposit it when you dock.
  - Still short, a **buy** button opens the Buy lookup for what is missing.
- **How it is figured:** equal jumps of up to 500 ly in a straight line, each lighter than the last. The real trip is
  never shorter.
- **A booked jump** says its own: "(432 ly jump ≈ 96 t; depot after ≈ 572 t)".
  - "⚠ last jump it can pay" shows when the depot after it (with a tritium sell order in its hold) cannot pay a full
    500 ly jump more.
  - It is red with no tritium in its hold, amber when moving it in would.

### Services and upkeep

- **Services:** Universal Cartographics and Vista Genomics, the services that buy what an explorer carries. They come
  from its last stats, or the newer of them and your last docking there.
  - "UC ✓" for one that is on.
  - Its name and a red ✗ for one suspended in the carrier's management ("UC ✗"; "suspended" on hover).
  - "no Vista" for one not installed.
- **Balance and upkeep:** under them, "Balance 1.33B · ~83 wks upkeep now". It is counted down a week of upkeep for
  each week since its stats. That is an estimate: the market moves the balance too. The hover has the stats' own
  figure and how old they are.
- **Low upkeep:** the line is amber under 4 weeks. Then a card says so too, and the **Carrier upkeep low** alert row
  (off until you tick it) adds a notification and a line. None of it while the carrier is being decommissioned.
- **The week's upkeep:** the journal has no upkeep figure. It is worked out from the services installed at the
  **published rates** (the core and each service, a suspended one at its lower rate), not yet checked against the
  game's Finance screen. Hover for the figure.
- **Refreshing:** opening the carrier's management refreshes the stats. A deposit into its bank, or a withdrawal,
  refreshes the balance.

### Your carrier among the nearest places to sell

The Unsold tile's "sell:" line and its details list your carrier while it has Universal Cartographics (or Vista
Genomics) on.

- It is placed where it is now from your journal, never an old report of it, with "≈ 3 carrier jumps to you".
- Not while the service is suspended, nor once it is decommissioned.
- **Your squadron's carrier** is among them the same way, as "your squadron's carrier". It is placed where the
  Carrier tile places it (your journal's word at your last login, or Spansh's newer report), with no carrier jumps:
  it cannot come to you.

### 🎯 and 🛣 to your carrier

- **🎯 beside your carrier's system** on the Carrier tile, when it is elsewhere: auto-target puts that system in the
  galaxy map, as 🎯 on a route's row does (see [Targeting and
  auto-target](plot-route.md#-targeting-and-auto-target)). On the game PC only; none while you are aboard or in its
  system.
- **🛣 beside it**, when your carrier is 250 ly or more away: plots an exact route to its system at once, with Plot
  Route's exact options, without leaving the page you are on.
  - The tile says "⏳ plotting a route there…" until it is in; then the route line and its 🎯 take over.
  - Following a Highway route already, it asks "replace your route to …?" first (Replace / Keep).

## 💱 Trading

Outrider is an explorer's tool first, so trading stays small: where to sell or buy what you carry, and a trade route
to follow. Both come from [Spansh](https://spansh.co.uk)'s market data, read only. Prices and demand are what players
last reported, so the newer the data, the safer the trip.

<p align="center">
  <img src="../images/cargo.png" alt="The Materials tab's Cargo with a Sell lookup open: the carrier's platinum, stations that take all of it, one opened" width="900">
</p>

### Sell / Buy

**Sell / Buy** on any line of your Cargo asks where to sell all of it (or buy that much).

- **What it asks for:** best price or closest, within a distance, data under an age, your ship's pad size. Fleet
  carriers are left out unless ticked: their orders are often years old.
- **Only the tons you can sell** count: the legal ones. Sell's hover says what is left out.
  - Stolen cargo needs a black market, so a line with only stolen tons asks for those, with only black markets
    listed, at the legal market's price.
  - Mission cargo is not yours to sell, so a line of only that has its Sell greyed out.
- **Each station shows** how far it is (and how far from its star), the price, demand or supply, what your load
  earns and the profit over what you paid.
- **Opened,** it lists what else it buys from your hold and its services (and whether it buys exploration data and
  samples too). It has Copy, Bookmark and **Plot route here**: a route there, as **Plot route** beside a bookmark
  plots one (see [🎯 and Plot route anywhere](plot-route.md#-and-plot-route-anywhere)).
- **Buy something else** looks up any commodity.
- **Any language:** a game in another language is fine, since each line is matched to Spansh's name by the game's
  own id. When Spansh's commodity list cannot be read, the lookup goes on with the journal's own name for it and says
  so.
- **While mining,** a full hold runs this lookup for the most you carry and says where to sell it
  ([Voice and alerts](voice-and-alerts.md#-alerts)).
- **Hotspot minerals:** the same lookup prices a ring's hotspot minerals. A body panel with hotspots shows each one's
  best sell price within 100 ly, highest first (**Best nearby**, see [Here](views.md#-here)).

### Sell all

With two lines or more you can sell, **Sell all** on the ship's line ranks stations by what they pay for the whole
hold. Each one prices every line it buys (your tons, or its demand when that is less), so one that takes three of
your four lines can come first.

- **Each station shows** "Takes 3/4 lines, 85 t of 98 t", what it pays and the profit over what you paid (bought
  lines only: mined ore cost you nothing).
- **Opened,** it lists each line ("Gold 1 t × 49,178 cr (demand 1 of your 10 t)") and what it doesn't buy.
- **The candidates** are Spansh's best buyers of your four largest lines; the nearest ones with **Closest**. With
  carriers ticked, they are the stations as without, and carriers whose market is under a week old. So a station that
  is good for all of them but best for none can be missed.
- **Left out, and said:** limpets, mission cargo and stolen tons.
- **Carriers:** your own carrier is never one (unload it there yourself). Other carriers only when ticked, and only
  with a market at most a week old.

### One shipload or all of it

When a line is more than your ship's hold (its size, not what is free), the bar switches between "All 16,000 t" and
"One shipload 720 t" ("≈ 23 shiploads for all of it").

- A shipload asks for stations that take (or have) that much: "Sell 720 t of 16,000 t".
- Not shown before the game has written your ship's loadout.

### Trade routes

Plot Route's **Trade** plotter asks Spansh's [trade planner](https://spansh.co.uk/trade) for station-to-station hops
from the station you are docked at, and follows them as you fly. Its options, and how it is followed, are under
[Trade routes](plot-route.md#-trade-routes) on Plot Route.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Now](now.md) · [Exploring](exploration.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings](settings.md) · [For the curious](for-developers.md)
