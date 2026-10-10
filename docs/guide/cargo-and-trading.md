[ED Outrider](../../README.md) · [What's new](whats-new.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [In-game overlay](overlay.md) · [Uploads](uploads.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)

# Cargo and trading

## 📦 Cargo and your carrier

The **Materials** tab starts with your **Cargo**.

- **Your ship's hold** is exact (the game writes it whole). Each commodity shows what you paid: the game's own
  average over your purchases ("Avg 45,210 cr/t (2 lots)"; mined or transferred tons have no price).
- **Your fleet carrier's hold** is not written anywhere whole, so Outrider tracks it:
  - ✓ **confirmed**: a commodity on a **sell order** at your carrier. Opening its commodity market lists every sell
    order with its stock, and that stock is the count. Put a sell order (at a price nobody will pay) on everything
    you want counted.
  - ◷ **last seen**: everything else, followed from your journal (transfers, your own buying and selling there,
    orders set and cancelled). Other players' trades with your carrier are written nowhere in your journal: a buy
    order's filled part is worked out the next time you open the market.
  - ✎ **entered**: a count you typed in. **Recount…** lists the lines Outrider cannot confirm; the game's Inventory
    screen at your carrier shows them all.
  - The total is checked against the carrier's own ("✓ in sync: 16,085 t", or the tons not accounted for).
  - This is the only way to track a carrier's cargo without signing in to Frontier's servers (their companion API,
    as EDMC and Inara do). Outrider deliberately never does that: it reads your own journal files and queries only
    public, read-only services, so your Frontier account is never involved.
- **The Carrier tile** shows its tritium while tritium is on a sell order: the depot, the total with the hold, and
  how many 500 ly jumps that gives ("Total Tritium: 14,199 t (151 jumps)", worked out jump by jump with the game's
  fuel formula). Without one the tile is as before. No carrier, no tile; a carrier being decommissioned says so in
  red with the scrap date, and once it is gone, "Decommissioned" and the date (a carrier bought since takes its place).

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
- **Trade routes.** Plot Route's **Trade** plotter asks Spansh's [trade planner](https://spansh.co.uk/trade) for
  station-to-station hops from the station you are docked at, with your credits and hold (from the journal), and its
  options: hops, hop distance, distance from the star, data age, pad, planetary and player-owned stations,
  prohibited goods, permit systems. It can take a few minutes to plot. It shares a place with Road to Riches and
  Exomastery (one of the three at a time).

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

[ED Outrider](../../README.md) · [Install and run](install.md) · [The views](views.md) · [Plot Route](plot-route.md) · **Cargo and trading** · [Voice and alerts](voice-and-alerts.md) · [Automation](automation.md) · [On a tablet](tablet.md) · [Settings and good to know](settings.md) · [For the curious](for-developers.md)
