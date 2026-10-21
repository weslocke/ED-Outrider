[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Cargo and trading

## 📦 Cargo and your carrier

The **Materials** tab starts with your **Cargo**.

- **Your ship's hold** is exact (the game writes it whole), and Outrider follows the changes in between, limpets
  bought, sold and launched included (the game counts those without writing the list again). Each commodity shows
  what you paid: the game's own average over your purchases ("Avg 45,210 cr/t (2 lots)"; mined or transferred tons
  have no price).
- **Your fleet carrier's hold** is not written anywhere whole, so Outrider tracks it:
  - ✓ **confirmed**: a commodity on a **sell order** at your carrier. Opening its commodity market lists every sell
    order with its stock, and that stock is the count. Put a sell order (at a price nobody will pay) on everything
    you want counted. From a day on the mark says how old that count is ("✓ 9 d", amber after a week), and after a
    week the carrier's heading asks you to open its commodity market while docked there to refresh them.
  - ◷ **last seen**: everything else, followed from your journal (transfers, your own buying and selling there,
    orders set and cancelled). Other players' trades with your carrier are written nowhere in your journal: a buy
    order's filled part is worked out the next time you open the market. When a market read finds the carrier holding
    less than is tracked, a last-seen line with no news for 30 days is dropped; **Recount…** puts back one that is
    really there.
  - ✎ **entered**: a count you typed in. **Recount…** lists the lines Outrider cannot confirm; the game's Inventory
    screen at your carrier shows them all. **+ Add a commodity** takes the names your journal has given and those
    Spansh lists; anything else (a typo) is refused with the closest names: "Not a commodity: “Titanum”. Did you mean:
    Titanium Tritium", a click puts one in.
  - The total is checked against the carrier's own ("✓ in sync: 16,085 t", or the tons not accounted for).
  - This is the only way to track a carrier's cargo without signing in to Frontier's servers (their companion API,
    as EDMC and Inara do). Outrider deliberately never does that: it reads your own journal files and queries only
    public, read-only services, so your Frontier account is never involved.
- **The Carrier tile** shows its tritium while tritium is on a sell order: the depot, the total with the hold, and
  how many 500 ly jumps that gives ("Total Tritium: 14,199 t (151 jumps)", worked out jump by jump with the game's
  fuel formula: the carrier's cargo weighs, the space a buy order only reserves does not). Without one the tile is as
  before. No carrier, no tile; a carrier being decommissioned says so in red with the scrap date, and once it is gone,
  "Decommissioned" and the date (a carrier bought since takes its place).
- **The trip to you:** while your carrier is elsewhere (and no jump or carrier trip is under way), the tile says what
  meeting takes, short: "To it 5 jumps · to you 3, ≈340 t" (your jumps to it, amber when your tank covers fewer; its
  carrier jumps to you and their tritium), and when the depot holds less, "140 t short" in red (amber when tritium on a
  sell order in its hold covers it: the hover says whether to move it into the depot before the jumps, or top it up
  again on the way when it needs more than the 1,000 t depot takes at once). Equal jumps of up to 500 ly in a straight
  line, each lighter than the last (the real trip is never shorter). A booked jump says its own: "(432 ly jump ≈ 96 t;
  depot after ≈ 572 t)". The game's fuel formula is checked against your carrier's own jumps (what the depot held
  before and after each one, from its stats and your tritium deposits): once three are measured, their median scales
  the figures (at most ±20%), and the hover says so ("checked against your carrier's last 12 jumps: no correction
  needed"). Tritium other players donate is not in your journal, so such a jump reads low; the median rides over it.
- **Services and upkeep:** a service suspended in the carrier's management shows as its name and a red ✗ ("UC ✗",
  "Redemption office ✗"; "suspended" on hover), beside "Vista ✓" for one that is on, from its last stats or the newer of them and your last docking there. Under them,
  "balance 1.33B · ~96 wks upkeep" (amber under 4 weeks; the hover says how old the stats are). The
  journal has no upkeep figure: the week's upkeep is worked out from the services installed at the **published rates**
  (the core and each service, a suspended one at its lower rate), not yet checked against the game's Finance screen;
  hover for the figure. Opening the carrier's management refreshes the stats.
- **Your carrier among the nearest places to sell** (the Unsold tile's "sell:" line and its details): while it has
  Universal Cartographics (or Vista Genomics) on, where it is now from your journal, never an old report of it, with
  "≈ 3 carrier jumps to you"; not while the service is suspended, nor once it is decommissioned.
- **🎯 beside your carrier's system** on the Carrier tile, when it is elsewhere: auto-target puts that system in the
  galaxy map, as 🎯 on a route's row does (see [the Neutron Highway](plot-route.md#-the-neutron-highway)). On the
  game PC only; none while you are aboard or in its system.
- **🛣 beside it**, when your carrier is 250 ly or more away: plots an exact route to its system at once, with Plot
  Route's exact options, without leaving the page you are on; the tile says "⏳ plotting a route there…" until it is in,
  then the route line and its 🎯 take over. Following a Highway route already, it asks "replace your route to …?"
  first (Replace / Keep).

## 💱 Trading

Outrider is an explorer's tool first, so trading stays small: where to sell or buy what you carry, and a trade
route to follow. Both come from [Spansh](https://spansh.co.uk)'s market data, read only; prices and demand are what
players last reported, so the newer the data, the safer the trip.

<p align="center">
  <img src="../images/cargo.png" alt="The Materials tab's Cargo with a Sell lookup open: the carrier's platinum, stations that take all of it, one opened" width="900">
</p>

- **Sell / Buy** on any line of your Cargo asks where to sell all of it (or buy that much): best price or closest,
  within a distance, data under an age, your ship's pad size, fleet carriers left out unless ticked (their orders
  are often years old). Each station shows how far it is (and how far from its star), the price, demand or supply,
  what your load earns and the profit over what you paid. Opened, it lists what else it buys from your hold and its
  services (and whether it buys exploration data and samples too), with Copy, Bookmark and **Plot route here**.
  **Buy something else** looks up any commodity.
- **One shipload or all of it:** when a line is more than your ship's hold (its size, not what is free), the bar
  switches between "All 16,000 t" and "One shipload 720 t" ("≈ 23 shiploads for all of it"); a shipload asks for
  stations that take (or have) that much: "Sell 720 t of 16,000 t". Not shown before the game has written your ship's
  loadout.
- **Trade routes.** Plot Route's **Trade** plotter asks Spansh's [trade planner](https://spansh.co.uk/trade) for
  station-to-station hops from the station you are docked at, with your credits and hold (from the journal), and its
  options: hops, hop distance, distance from the star, data age, pad, planetary and player-owned stations,
  prohibited goods, permit systems, unique stops (no station twice). It can take a few minutes to plot. It shares a
  place with the survey routes (Road to Riches, Exomastery, the world routes, a sweep: one of them at a time).

<p align="center">
  <img src="../images/trade.png" alt="Plot Route with a trade route: each stop with what to sell and buy there, and the route on the map" width="900">
</p>

- **Following it:** each stop lists what to sell and buy there, the hop's profit and the total so far. On arrival
  the voice says where to dock and what to trade; your sales and purchases there count towards each commodity's
  tonnes (your journal: "60 of 100 t" until it is all traded), then it says the hop's profit and the next stop (its
  own alert, Trade route). Undocking with only part traded (the station had less than Spansh said) moves on: the
  voice says what fell short instead of the profit. 💱 in the line under the tiles, with
  🎯 on the next system.

---

[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
