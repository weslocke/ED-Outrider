# What Outrider reads from the game, and the traps

The game writes a journal (`Journal.<date>T<time>.<part>.log`, one JSON object per line, UTC timestamps
to the second) plus a few companion files that it rewrites in place. This lists what Outrider uses and for
what, then the behaviour of the game that the code has to work around. Everything here was checked against
the code; the constants named are in `ed_outrider.py` unless another file is given.

## Line format

- The game writes `"event":"Name"` with no space after the colon. `Journals.read_file` only parses lines containing
  one of the `WANTED` byte strings built from the `*_EVENTS` tuples (plus `Fixed_Event_Life` and `POI_BYTES`, the
  FSS signals worth a detour), so **an event that is not in one of those tuples is never seen**.
  `outrider/unsold.py` has its own list (`INTERESTING`); `outrider/log.py` reads every line for the Log. The uploads
  (`outrider/uploads.py`) see every line of a live folder before this filter (`self.uploads.line(...)` in
  `read_file`), so EDDN, EDSM and Inara get events Outrider itself never parses.
- Only complete lines are consumed (the game may be mid-write). Offsets are stored per file in
  `journal_files`; the same file seen in two folders (a copied legacy folder, two Proton prefixes) is read
  once (`twins`).
- A line missing a field the handler indexes is skipped with a message, not the whole file.

## Journal events used

| Events | What for |
|---|---|
| `FSDJump`, `CarrierJump`, `Location` | `Population` (`system_population`: no x5 bio bonus where people live). Visits, the jump path (`jumps`), current and previous position, region crossings. `FSDJump` `JumpDist`/`FuelUsed`/`FuelLevel` feed the fuel model (not when `BoostUsed`). `Taxi`/`Multicrew` mark rides that are not your ship's fuel or honk. A `Location` in the system you are already in is a relog, not an arrival (an older line, from a legacy folder read late, is judged against the arrival before it, not today's position). A session that starts docked (a login, a respawn) writes no `Docked`: its `Location` has `Docked: true` with `StationName`, `StationType`, `MarketID` and `StationServices`, and counts as the dock (the docked state, the hold's market for `CargoTransfer`). `FSDJump`/`CarrierJump`, and a `Location` that moves you (a respawn, a login elsewhere; not a relog), also move the Neutron Highway along its route (`highway_arrival`). |
| `Fileheader` | A game launch (its `part` 1; a later part continues the session): from it, or a `LoadGame`, until the session's `Location` the game is loading (meta `game_load`, `Journals.loading`) and the overlay shows nothing. Never counts as play (`LOGIN_EVENTS`). |
| `FSDTarget` | The targeted system (sound verdict, "leaving unfinished work" check) and its star class. `RemainingJumpsInRoute`: the route plotted in game's jumps left, this one included (1 for a lone target): the overlay's Target panel says "next jump of your route · N to go" above 1. |
| `StartJump` | Star class of the destination. `JumpType: Hyperspace` is written as the FSD starts charging, at the start of the countdown (before the game's own countdown call): the jump card and the speech queue clearing happen here, but the jump line's words wait for Status.json's FsdJump flag (bit 30, the tunnel: a "hyperspace" moment) or 8 s. |
| `Scan` | Bodies (`own_bodies`, the record used everywhere; rare stars and rare planet classes from `StarType`/`PlanetClass`; the green gas giant model from `PlanetClass`, `SurfaceTemperature` at full precision, `MassEM` and `Radius`: `outrider/ggg.py`), the arrival star's `WasDiscovered` (discovery streak verdict), first-scan `WasDiscovered`/`WasMapped`/`WasFootfalled` (`own_firsts`), landable `Materials` (jumponium), valuable finds. Nav-beacon scans (`ScanType` NavBeaconDetail/NavBeacon) never count as your discoveries. The arrival star can be scanned twice (the auto scan, then a Detailed one after the honk, or a nav beacon's): one arrival per visit. |
| `FSSDiscoveryScan` | The honk: `BodyCount`, `Progress`; triggers the arrival briefing. |
| `FSSAllBodiesFound` | All bodies found: the FSS debrief. |
| `FSSBodySignals` | Bio, geo and planetary mining location counts found by the FSS (spoken signal counts, bio finds), and a planetary anomaly (`$SAA_SignalType_PlanetAnomaly;`): the FSS names no Guardian or Thargoid site, so its line adds to what the DSS found, never replaces it (`own_signals.sites`, `SITE_SIGNALS`). |
| `SAASignalsFound` | DSS results: signal counts, `Genuses` (which genera are on the body), ring hotspots, and Guardian, Thargoid and "other" sites (named only once the DSS has mapped the body). |
| `SAAScanComplete` | A body mapped (`own_mapped`, the "mapped" call-out); for a ring, the only record that it was probed. |
| `ScanBaryCentre` | Barycentre orbits for the schematic. |
| `ScanOrganic` | Sample runs: `Log` starts (and abandons any other run), `Sample`, `Analyse` completes. `Body` is the body id. It carries no position: a sample point is the live Status.json's within 90 s (`note_sample_point`). The game writes a biology `CodexEntry` in the same second just before a first `Log`: that is where you stand, not a plant. |
| `CodexEntry` | Codex entries, "new to your codex", vouchers (one with no `BodyID`, a phenomenon in space, is no body's), a green gas giant confirmed (`outrider.ggg.CODEX_GREEN`). A biology one (`Category` `$Codex_Category_Biology;`, `Name` `$Codex_Ent_<Genus>_<NN>_<variant>_Name;`, the species being `$Codex_Ent_<Genus>_<NN>_Name;`) is written each time the composition scanner reads a plant: it carries `Latitude`/`Longitude` on foot only (21 of the author's 23), so from the ship or SRV the position is Status.json's at that moment (`bio_tags`, BioScan's waypoints). A star or planet type (`$Codex_Category_StellarBodies;`) is logged once per region, the first time you scan one there: its `Name_Localised` is ambiguous for planets ("Terraformable", "Non Terraformable", "Standard gas giant" for many entries), so key on `EntryID` (`outrider/codex_bodies.py`); a planet's `BodyID` is not that planet's (usually the star you are near). Its "Ter" entries are the solid bodies with an atmosphere, thin ones too. The type is logged only the first time (109 of the author's 111 such lines say new), so a type you have scanned in a region counts as logged there even with no line in the journals kept. |
| `Disembark` | Footfall on a planet (`OnPlanet`). |
| `ApproachBody`, `LeaveBody`, `Touchdown` | Approach briefing, leaving a body mid-run, the body you are at; your ship's landing spot. |
| `LaunchSRV`, `LaunchVessel`, `DockSRV`, `SRVDestroyed`, `SupercruiseExit`, `SupercruiseEntry`, `Liftoff` | Which body your SRV is out on and which SRV (`SRVType` `mev_rhino` is the Rhino); the ship marker; rigs lost with the Rhino. The Nomad launches with `LaunchVessel` (`VesselType` `lander01`, `VesselType_Localised` "Nomad") but docks with `DockSRV`, and Status.json reports it as an SRV (bit 26). `LaunchVessel` must keep the body you are on, as `LaunchSRV` does (PARSER_VERSION 37). |
| `MiningRefined` | 1 t of a commodity refined, by the ship's refinery (asteroids) or the SRV's: every one adds to the mined stock (meta `mined_stock`, `Journals.note_mined`); the SRV's alone are "Mined previously" (`own_mined`) and the Rhino's collections. Its `Type` is the symbol (`$painite_name;`), the market events' the plain id (`painite`): `outrider.cargo.cid` makes them one key. |
| `MultiSellExplorationData`, `SellExplorationData` | Cartographic sales (one row per page, keyed by file:offset), which systems were sold. They name no station or market: the sale's place is where you are docked (`sale_events`' station, market_id, station_type from meta `sale_dock`), its ship the latest `Loadout`'s `ShipID` (`Journals.ship_at`). `TotalEarnings` is what you were paid: `BaseValue` + `Bonus` less a hired NPC crew member's share (91 % of it on every page in the author's journals while one was hired, until `CrewFire`); `SellOrganicData`'s entries had no such cut (`outrider.earnings.crew_share`). |
| `SellOrganicData` | Vista Genomics sales, each `BioData` entry with its `Bonus` (the x5 check); `MarketID` is the market sold at (the station's name and type are the dock's). Two sales can share a second, so `bio_sales` rows are keyed by journal line (PARSER_VERSION 38); a visit sold in several goes (sales under 5 minutes apart) is one x5 check. |
| `Died`, `Resurrect` | Deaths and whether the ship (and its data) was lost (`Option`). |
| `LoadGame`, `Commander`, `Rank`, `Progress`, `Promotion`, `Statistics`, `Shutdown` | Logins and sessions, credits at login, ranks, career statistics, the quit (recap, quit backup). |
| `Loadout` | Ship, jump range, fuel capacity, unladen mass, FSD and Guardian booster, engineering modifiers, hull and core module health, rebuy, `HullValue`/`ModulesValue`. An Arx-bought ship's Loadout has `ModulesValue` but no `HullValue`, and its `Rebuy` covers the modules only, so the risk figures leave its rebuy out ("N× rebuy", the rebuy-multiple levels: `risk_rebuy`, page.js `riskRebuy`). Also the latest one per `ShipID` goes to `fleet_loadouts` (`note_fleet`, `fleet_figures` in `outrider/fsd.py`): the Highway's ship list and the exact plotter's inputs. |
| `EngineerCraft` | Engineering that moves the jump range before the next `Loadout`. |
| `Cargo` (`Vessel: Ship`) | Tonnes in the hold: the ship's mass for the fuel model. With `Inventory` (at login) the whole hold (`outrider.cargo.ship_snapshot`); otherwise only the count, the list being in Cargo.json. |
| `MarketBuy`, `MarketSell` | What you paid (`BuyPrice`; `MarketSell.AvgPricePaid` is the game's own average cost, 0 when unknown). At your carrier's `MarketID`, your own trades there (`cargo_events`). At a trade route's stop, its progress. `MarketSell` has `Type` (the plain lower-case id), `Count`, `SellPrice`, `TotalSale` and `MarketID`, no station name and nothing that says whether the tons were mined or bought: it counts as mining up to what the mined stock holds of it, min(`Count`, stock), its share of `TotalSale` (`mining_sales`; at your own carrier's market flagged `own_carrier`, your own money), the rest is trade. |
| `CargoTransfer` | `Transfers[]` of `Type`, `Count`, `Direction` (`tocarrier`, `toship`, `tosrv`). It names no carrier: it counts for yours only while docked at it (`Journals.cargo_dock`, replayed in order). A `tocarrier` transfer moves the mined part of its tons from the ship's mined stock to the carrier's (meta `mined_carrier`), `toship` / `tosrv` moves up to what the carrier's holds back aboard, capped first at what the carrier held of it (its fold up to then: other players' purchases show only in your Market.json reads): ore stored on the carrier and sold later is still mined. |
| `CarrierTradeOrder` | Your carrier's orders: `SaleOrder` n, `PurchaseOrder` n or `CancelTrade`, with `Price`; `BlackMarket` orders are left out. |
| `CarrierDepositFuel` | Tritium from the **ship's** hold into the carrier's depot (`Amount`, `Total`: the depot after). |
| `CollectCargo`, `EjectCargo` | Cargo scooped or jettisoned (the ship's hold; no price). `EjectCargo` takes its tons off the mined stock, as a `Died` empties it (the hold is lost). |
| `FuelScoop`, `RefuelAll`, `RefuelPartial` | Last refuel. |
| `HullDamage`, `Repair`, `RepairAll`, `RepairDrone`, `AfmuRepairs`, `HeatDamage`, `Interdicted`, `JetConeBoost` | Hull and module health, danger alerts. A `Repair` lists what was repaired (`Items`; older lines `Item`): "Wear" is the ship's integrity, not the hull, so only "Hull" (or "All", or a `RepairAll`) sets the hull to 100 %. `JetConeBoost` is the FSD supercharge signal (neutron or white dwarf cone, `BoostValue` the multiplier): the next jump's range, the "supercharged" moment, and the Highway's auto-target trigger. |
| `Docked`, `Undocked` | Docked state and services (`exploration` = Universal Cartographics, `vistagenomics`), dock/undock alerts. The sales' place too, followed line by line in meta `sale_dock` (journal-derived, replayed in order by a re-read; meta `docked` is kept through one), an Apex shuttle's dock included: you can sell your data where it took you. |
| `CarrierBuy`, `CarrierDecommission`, `CarrierCancelDecommission` | A new carrier (`CarrierID`, `Callsign`, `Location`, `SystemAddress`: its state starts afresh), and giving one up (`ScrapRefund`, `ScrapTime` in epoch seconds; the scrapping writes nothing). Per Frontier's manual; not yet seen in a real journal. |
| `CarrierStats`, `CarrierLocation`, `CarrierJumpRequest`, `CarrierJumpCancelled` | Your fleet carrier. `CarrierStats` also gives its cargo total (`SpaceUsage.Cargo`: the cargo check), the capacity in use (`TotalCapacity - FreeSpace - CargoSpaceReserved`: a buy order's reserved space weighs nothing) and the depot (`FuelLevel`): the tritium's jumps. These, `CarrierJump` (keyed by its `MarketID`) and `CarrierDepositFuel` are kept in `cargo_events` for the carrier's measured jumps (S13 B). |
| `NavRouteClear` | The plotted route was cleared. |
| `NavRoute` | A route was plotted: NavRoute.json should follow, with the same timestamp. **The game does not always write it** (2026-10-14: three plots in a row left the file as the NavRouteClear before them wrote it; clearing and plotting a different destination wrote it again). Kept as meta `navroute_event` {ts, written}: an older NavRoute.json is not that route (`Journals.game_route`). |
| `FSSSignalDiscovered`, `SupercruiseDestinationDrop` | Notable stellar phenomena (`$Fixed_Event_Life_*`): the FSS lists a system's phenomena as identical lines in one second, so a kind keeps the most one listing had (`phenomena.n`, `NSP_BURST_S`); a drop names only the kind ("a ring phenomenon"), not which site, so each drop is one site visited (`phenomena_sites`). `FSSSignalDiscovered` also gives the signals worth a detour (`poi`, `poi_kind`): a Titan (`SignalType` `Titan`), Guardian beacons, generation ships, listening posts, number stations, tourist beacons, memorials; ordinary megaships are left out. Two listening posts in one system are both "Listening Post" in the game's words (`#index=` in `SignalName` tells them apart), and some are named ("Listening Post Pollux D568"). |
| `Materials`, `MaterialCollected`, `MaterialDiscarded`, `Synthesis`, `MaterialTrade`, `TechnologyBroker`, `ScientificResearch`, `MissionCompleted`, `EngineerContribution` | The materials inventory (`outrider.materials.apply`; each login's `Materials` is a full snapshot). `Synthesis` also teaches its recipe (`Name`, `Materials`: a list of `{Name, Count}`, in the oldest journals a `{name: count}` object), kept in the state's `recipes` (S15). Names seen: Limpet Basic, Fuel Basic and Repair Basic (the SRV's), Ammo Basic/Standard (multi-cannon), AX Remote Flak Ammo Basic. |
| `CrewHire`, `CrewFire`, `Statistics.Crew` | `outrider/unsold.py`: an NPC crew member's cut of payouts. |
| `StoredShips`, `ShipyardBuy`/`Sell`/`Swap`/`New`/`Transfer`, `SellShipOnRebuy`, `SetUserShipName`, `StoredModules`, `ShipLocker`, `SuitLoadout`, `CreateSuitLoadout` (and the loadouts' other changes), `EngineerProgress`, `Reputation`, `Powerplay*`, `Squadron*`, `Missions`, `MissionAccepted` and the missions' endings, `CargoDepot` | The CMDR tab (`outrider/commander.py`), checked against real journals on 2026-10-14. A `Missions` list's `Expires` is the seconds left, but a colonisation mission's is the time itself (a Unix time: `"Expires":1745159181`), its `Name` a `$...;` symbol with `Name_Localised`. `PowerplayRank` (0) comes just before `PowerplayJoin`, at the same second, and the join names only the power. `ShipLocker` lines carry the lists at login and at most changes during play, but some carry none (ShipLocker.json has them). `ShipyardSwap`'s `StoreOldShip` is the type in the journal's mixed case (`Explorer_NX`), `SellShipOnRebuy` writes `SellShipId`. Every `StoredShips` entry has `Hot`; no real `Loadout` has it (none was hot: Frontier's manual has it "if wanted at startup"). |
| `ModuleStore`, `MassModuleStore`, `ModuleBuy`, `ModuleRetrieve`, `FetchRemoteModule`, `ModuleSellRemote` | The CMDR tab's stored modules between two `StoredModules` lists (`commander.modules_apply`), checked against real journals on 2026-10-14. `ModuleStore` names the module `StoredItem` (with `Hot` and its engineering; no `StorageSlot`, no value); `ModuleBuy` has `StoredItem` when the old module was stored rather than sold (`SellItem`); `ModuleRetrieve` has `RetrievedItem` and, when the slot held one, `SwapOutItem`, which is stored, except, it seems, a module that came free with the ship (twice in the author's journals: the line does not say so); `FetchRemoteModule` names the list's `StorageSlot` and the `TransferTime`, and its `ServerId` is not a market. A module in transit is listed with `InTransit` and no place or cost. The game writes `StoredModules` again a second or two after most of these. `ModuleSell` sells from the ship, not storage. `ModuleSellRemote` (`StorageSlot`) and `MassModuleStore` (`Items`) had no real line: Frontier's manual. |

## Companion files

- **Status.json** (read on mtime change, `read_status`): `Fuel.FuelMain`/`FuelReservoir`, `Flags`, `Flags2`,
  `BodyName`, `Latitude`, `Longitude`, `Altitude`, `PlanetRadius`, `Heading`, `Cargo`, `Destination`,
  `GuiFocus`, `FireGroup`, `timestamp`. Flags used: docked (bit 0; the overlay's Now panel hides, `FLAG_DOCKED`),
  landed (1), supercruise (4, `FLAG_SUPERCRUISE`: the overlay's system panel shows only then), scooping (11), FSD
  charging (17), in your main ship (24, `FLAG_IN_MAIN_SHIP`: the overlay's Target panel shows only then, outside the galaxy map), in SRV
  (26), HUD analysis mode (27, `FLAG_HUD_ANALYSIS`: the overlay's analysis-only panels show only then), altitude from average radius (29), in the hyperspace tunnel (30, FsdJump: the jump line is said once it
  comes on after a hyperspace StartJump; auto honk waits while it is set; the overlay hides every panel); `GuiFocus`
  7-11 (system map, orrery, FSS, SAA, codex) hide the overlay too (`OVERLAY_HIDE_FOCUS`), 6 (the galaxy map) all but
  its Target panel; `BodyName` with `Altitude` is the Target panel's near-body zone (the point ApproachBody is written); Flags2
  bit 0 on foot, bits 3/13/14 on foot in a station, hangar or social space (counted as docked). In the SRV, the
  Nomad or a fighter (bits 25, 26), `Fuel` and `Cargo` are the vehicle's, not the ship's: the fuel tile keeps the
  ship's last figures and shows the vehicle's separately.
- **NavRoute.json** (`read_navroute`): `Route[]` of `StarSystem`, `SystemAddress`, `StarPos`, `StarClass`; the
  route strip, star classes and "unreported" systems. An empty route means it was cleared, unless it is older than the
  journal's last `NavRoute` line: then the game has not written the new route (late, or never). The last hop is the
  system plotted to (`navroute_end`: auto-target's check for a waypoint beyond one jump).
- **Cargo.json** (`read_cargo_file`): the ship's whole hold (`Inventory[]` of `Name`, `Name_Localised`, `Count`,
  `Stolen`, `MissionID`), rewritten with every `Cargo` event (whose own line then has only the count). **Not
  always:** after `BuyDrones` the game wrote a count-only `Cargo` and left the file as it was (2026-10-19, 200 limpets
  bought, the file still empty), so limpets are moved by `BuyDrones` / `SellDrones` / `LaunchDrone` themselves.
- **Market.json** (`read_market`): the market you last opened, with `MarketID`, `StationType` and `Items[]`
  (`Name` as `$platinum_name;`, `Name_Localised`, `BuyPrice`, `SellPrice`, `Stock`, `Demand`). Only your own
  carrier's is kept (`carrier_markets`): the game overwrites the file at the next market.
- **Controls bindings** (`outrider/honk.py`): the active preset's `.binds` file in the game's Options/Bindings folder,
  for Primary Fire's keyboard binding and auto-target's (`GalaxyMapOpen`, `UI_Right`/`Left`/`Up`/`Down`, `UI_Select`,
  `UI_Back`, `CycleNextPanel`, and the galaxy map camera's `CamYaw*`, `CamZoom*`, `CamTranslate*`). `StartPreset.4.start` names a preset per line (General, Ship, SRV, On foot): the `UI_*`
  controls are read from the General one, the rest from Ship. Each control has `Primary` and `Secondary` slots; only a
  `Device="Keyboard"` slot whose `Modifier`s are all keyboard keys can be pressed.

## Traps and facts learned

**Your fleet carrier's cargo** (checked in game with the author, 2026-10-07)
- Its Market.json lists only commodities with an order. A sell order shows `Stock` (the holding) and `BuyPrice` (what
  a visitor pays); a buy order shows `Stock` 0 and `Demand` (what it still wants), hiding what is aboard (silver:
  Stock 0, Demand 1, with 7 t there). Commodities with no order are not listed at all.
- The in-game Inventory screen at the carrier lists everything, but viewing it writes nothing.
- Opening the carrier's management or market writes `CarrierStats` just before Market.json.
- `CargoTransfer` names no carrier; `CarrierDepositFuel` takes from the ship's hold (moving tritium from the carrier
  to the depot is a transfer to the ship, then a deposit).
- Other players' trades with your carrier write nothing in your journal.
- A carrier jump burns `round(5 + ly × (25000 + used + depot) / 200000)` t (`used` = TotalCapacity - FreeSpace -
  CargoSpaceReserved, the cargo included; `depot` = FuelLevel before the jump): exact on 26 of the author's 27 recorded
  jumps. **Reserved space is not cargo:** a buy order holds space that weighs nothing. The 27 jumps all had none
  reserved; CarrierStats' own `JumpRangeCurr` (the jump the depot pays for in full) matches the formula on every line
  under 500 ly only with the reserved space left out (4,500 t reserved: 198.6 ly, not 180.7).
- `CarrierStats.Finance`: `CarrierBalance`, `ReserveBalance`, `AvailableBalance` (balance less reserve: can be
  negative, seen -1,051,595,783), `ReservePercent` (sometimes missing). No upkeep figure anywhere in the journal. The
  weekly upkeep comes out of the balance: on the author's carrier the balance fell 13,579,218 cr over a Thursday and the
  reserve stayed put.
- `CarrierStats.Crew`: one entry per role (`CrewRole`: Captain, Refuel, Repair, Rearm, Commodities, CarrierFuel,
  Exploration (Universal Cartographics), VistaGenomics, VoucherRedemption, BlackMarket, Shipyard, Outfitting,
  PioneerSupplies, Bartender); `Activated` false = not installed (no `Enabled`, no `CrewName`); `Activated` true with
  `Enabled` false = suspended. A suspended service is also left out of the next `Docked`'s `StationServices`.
  `CarrierCrewServices` (`CrewRole`, `Operation`: Activate, Deactivate, Pause, Resume, Replace) says a change between two
  CarrierStats; none in the author's journals yet.
- A carrier's jump in the journal (S13 B): `CarrierJumpRequest` (`SystemAddress`, `DepartureTime`), then at the
  departure time a `CarrierLocation` (only while the game runs; otherwise the next login's) and, only when you are
  aboard, a `CarrierJump` a minute later. `CarrierJump` has **no CarrierID** (its `MarketID` is the carrier's, with
  `StationType` FleetCarrier) and carries `StarPos`; `CarrierLocation` has none. Of the author's 248 requests, 172 have
  a CarrierJump. A squadron's carrier writes `CarrierLocation` too (`CarrierType` SquadronCarrier, at every login).
  The depot changes only by a jump and a `CarrierDepositFuel` (`Amount`, `Total` the depot after) or tritium donated by
  other players (not in your journal).

**Docking** (#3, 2026-10-14)
- `DockingGranted` has `LandingPad` (the number), `StationName`, `StationType`, `MarketID`; `DockingDenied` has `Reason`.
  Reasons in the author's journals: NoSpace 50, Distance 16, RestrictedAccess 4, TooLarge 2, Hostile 1 (Frontier's docs
  also list Offences, ActiveFighter, NoReason). A grant ends with `Docked`, `DockingCancelled` or `DockingTimeout`.
- The journal never says which layout a station uses (outposts, ports and Odyssey settlements come in several models), so
  there Outrider gives the pad number only. Starports (StationType Coriolis, Orbis, Ocellus or Bernal, AsteroidBase,
  Dodec) and carriers have one layout each (#12, after the LandingPad plugin); a squadron carrier is a FleetCarrier with a
  four-letter name, a colonisation ship a SurfaceStation (or unknown) with one of seven MarketIDs.
- The docking computer taking over writes `Music` with `MusicTrack` "DockingComputer", 2 to 10 s after DockingGranted
  in the author's journals; its module is `int_dockingcomputer_advanced` (or `_standard`) in the Loadout.
- `SendText` (your own chat) carries `To`, `Message`, `Sent`: Outrider reads only the LandingPad plugin's test
  commands from it ("!sppad 34").

**Status.json**
- It is rewritten only when something in it changes. A player standing still (a stopped Rhino included)
  produces no new reading, so "fresh" means "the game is live and this is the latest reading", not "written
  in the last second". Positions are paired with journal events only within 90 s of the event.
- With two live folders a stale Status.json in the other one must not replace the newer reading (compare
  `timestamp`).
- `Destination` appears only for navigation targets locked from the ship. A planetary mining location shows as
  `Name: "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=3;"` (`MINING_LOCATION_RE`), with
  `System` and `Body`. Targets selected from an SRV (a rig, a deposit) write nothing at all.
- The on-foot-in-station bits come from the documented flags and have not been confirmed in a live file.
- `GuiFocus` values auto-target relies on: 0 the cockpit (no panel), 6 the galaxy map (the full list is
  `outrider.target.GUI_FOCUS`). `Destination.System` is the targeted system's id64 (the check that auto-target worked); when the galaxy map plots a route of several jumps it is the first hop, and NavRoute.json's last hop is the system chosen, which auto-target also accepts.
  Flags auto-target's guards read: docked (bit 0), landed (1), FSD charging (17), in danger (22), being interdicted
  (23), in SRV (26), in the hyperspace tunnel (30); Flags2 bit 0 on foot.
- **In danger (bit 22) is set on every jump**, no threat needed: on from the FSD charge (5-7 s before StartJump) until
  some 16-26 s after the FSDJump, any star class, nothing near (logged in game 2026-10-09: 16, 16 and 26 s). The
  same on entering supercruise (lifting off a planet: on until 16 s after the SupercruiseEntry). A guard
  on it refuses everything in those seconds; Target next waits it out (`State.arrival_danger_until`, up to
  `AUTOTARGET_DANGER_WAIT` after the arrival).

**Mining and the Rhino**
- `MiningRefined` is 1 t and names neither body nor position. The body comes from the SRV state (per game
  session, `track_srv`); the position must come from Status.json at that moment. Ship-based ring mining writes
  it too: left out of the bodies' records (no SRV out), counted in the mined stock (mining income).
- Nothing in a sale says whether its tons were mined: the mined stock (refined, minus moved to your carrier, ejected
  or lost in a death) decides, so ore bought and sold with mined ore of the same kind is trade for the part over it.
- The game logs nothing when a Rhino mining rig is deployed, picked up or targeted (preparing one only opens a
  panel: `GuiFocus` 2). Outrider therefore marks rigs with the co-pilot button (`State.mark_rig`). Frontier
  usually adds journal events some weeks after a feature ships, so rig events are expected eventually: route
  them into `mark_rig` and the pickup path and make the button optional.
- Collecting from a rig writes one `MiningRefined` per ton (plus an SRV `Cargo`) at a fixed spot right over the
  rig. One rig can give several collections; an empty rig gives nothing. Rig numbers are the lowest free slot
  1-6 and a collection leaves the rig deployed.
- A rig lands about 7 m behind the cockpit along the heading (`RIG_BEHIND_M`, from SrvSurvey; a replayed run
  put the collection within 0.3 m of that point). Pickup range is under 5 m (`RIG_TAP_M`).
- The game allowed two rigs about 44-51 m apart and draws a 50 m ring (`RIG_SPACING` default 50).
- Leash: a community guide ("Rhino Planetary Mining", CMDR Dunn Actual) found a warning at 4 km and the rig
  destroyed at 5 km (`RIG_LOST_M`). Outrider warns earlier by default (`rig_warn` 3.5 km, again at 4.5 km).
- A rig refills in about 5.5-8 minutes (same guide), hence "probably full" after 8 (`RIG_FULL_S`).
- `LoadGame` inside an SRV names the ship, but inside the Nomad its `Ship` is `Lander01` (`Ship_Localised` "Nomad"), which
  is not a ship of yours (`not_a_ship`); `Location` only says `InSRV`. The SRV type is carried over from the
  last `LaunchSRV` that was never docked. While an SRV deploys from the ship's bay, Status.json is written for some
  seconds without the in-SRV flag: never take that for "back in the ship" (only InMainShip, bit 24, a minute on).
- `Liftoff` fires for every hop between sample sites and when the ship is dismissed with you on foot; use
  `LeaveBody` for "left the body".

**Selling**
- Universal Cartographics sells 50 systems per page and writes one `MultiSellExplorationData` per page. Pages
  of one "sell all" came 7 to 67 s apart in one player's journals, so the "data still aboard" line waits 90 s
  after the last page (`SALE_QUIET_S`). Several pages can share a second, so sale rows are keyed by the
  journal file and byte offset.
- Vista Genomics pays x5 when nobody had set foot on the body; the `WasFootfalled` of your first scan decides
  (a rescan after your own landing says footfalled). A sale can sell some species and keep others aboard.

**Discovery flags**
- `WasDiscovered`, `WasMapped` and `WasFootfalled` are kept from your *first* scan of a body: after you sell,
  a rescan says "discovered". Older journals lack `WasFootfalled`; treat it as unknown, not false.

**Spansh and EDSM**
- Spansh stamps bodies uploaded through EDDN with the journal's own event time. Your own upload therefore looks
  like an update at the moment of your scan; the firsts watch allows `FIRSTS_OWN_GRACE` (120 s) for that.
- Spansh's body search cannot filter on planetary mining locations, and Spansh stores only the mining
  location count, not what a location holds or where it is. Search for them in the Local database.
- Bodies last reported by a pre-Odyssey client (before `LEGACY_CUTOFF`, 2022-11-29) have no signals block and
  thin-atmosphere worlds marked not landable: shown as "old data", never added to values.
- A system Spansh lists may still 404 on its dump for a while (`NO_DUMP_RETRY`).

**Fuel and the frame shift drive**
- Fuel per jump = `MaxFuelPerJump` x (distance / range at this mass) ^ p. `FSD_POWER` (`outrider/fsd.py`) holds p per drive size
  (size 2 = 2.00 ... size 8 = 2.90, standard and SCO alike); the Caspian's Mk II SCO drive
  (`FSD_POWER_ITEM`, `outrider/fsd.py`) is 2.5025. Guardian boosters add `GUARDIAN_BOOST` (`outrider/fsd.py`) light years. Sources: EDCD
  coriolis-data (`frame_shift_drive.json` "fuelpower", `guardian_fsd_booster.json` "jumpboost") and
  EDDiscovery's EliteDangerousCore (`ModuleList.cs` "PowerConstant", which rounds the Mk II to 2.503).
- The Caspian's **SCO Mk II** drive (`int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii`): fuel multiplier
  0.011 (coriolis-data; Auto_Neutron's table says 0.004), power 2.5025, a neutron supercharge of ×6 (every other
  drive ×4), 6.8 t MaxFuelPerJump. Checked against the author's real Loadout: FSDOptimalMass 7238.5 (engineered),
  MaxFuelPerJump 6.8 and a size 5 Guardian booster (10.5 ly) give 82.97 ly, the Loadout's own `MaxJumpRange` and the
  game's. `fleet_figures` still checks every drive's figures against `MaxJumpRange` (within 1%) and, when they miss,
  plots with the optimal mass that range implies.
- `JetConeBoost` says a supercharge happened, not where: the Highway takes it as "boosted in this route system" only
  when you are at a route system (`maybe_autotarget`), and only within `HIGHWAY_LIVE_S` of the line.
- `Loadout` is only written at login and at outfitting, so an `EngineerCraft` in between is applied by hand (the
  fuel model does; `fleet_loadouts` rows stay as of their Loadout).
  Jet-cone boosts wear modules but health only updates at the next `Loadout`.

**Uploads** (EDDN, EDSM and Inara: `outrider/uploads.py`, `outrider/eddn.py`, `outrider/inara.py`)
- Logged in docked, `Location` names the station as its `Body` (`BodyType` "Station"): the session takes a body from
  it only when it is a planet or a star (or the line has no `BodyType`), as EDMC does.
- `Docked` names no body. A station on a planet's surface (`eddn.PLANETARY_STATIONS`) gets the body you approached as
  EDDN's `Body`/`BodyType`, as EDMC adds it.
- `ScanOrganic` has no position. EDDN's `Latitude`/`Longitude` come from a live Status.json on that body read 90 s
  before to 10 s after the scan (`ORGANIC_SYNC_S`), else are left out. `Analyse` is never sent: it can be written in
  another system.
- Crew in another commander's ship is told by `JoinACrew`'s `Captain` not being the commander: nothing is uploaded
  then.
- `horizons` / `odyssey` come from `LoadGame` only: a key it leaves out stays out.
- Market.json, Outfitting.json, Shipyard.json, FCMaterials.json and NavRoute.json are sent only when their timestamp is
  from 5 s before the event's to `FILE_LATE_S` (30 s) after it and their `MarketID` is the event's (`_wait_check`): NFS
  can serve an older file, and the game can write the file well after its line (a fleet carrier's first market of a
  docking, 2026-10-11: no commodity went with the old 5 s window). A live wait ends after `FILE_WAIT_S` and says so.
- Inara: a login's start-up lines (ranks, inventory, the ship...) end with the ship's `Cargo`, which sends them as one
  batch. A login docked (`Location` with `Docked`) or a ship swap may be followed by a `Docked` that is no new
  docking, and docking again where you undocked without leaving is none either; a hyperspace jump can start from
  normal space (off a carrier) with no `SupercruiseEntry`. The game writes `SuitLoadout` at every disembark and
  `CommunityGoal` often while you are signed up, so each goes only when it changed.

**Other**
- `Shutdown` is written only on a clean quit; a crash writes nothing, so the last event is where a session
  ended. It also leaves Status.json saying live with the dead session's flags, and the relaunched game does not
  rewrite it until the new session is in (hence `game_load`: the overlay waits for the `Location`).
- `CarrierLocation` is written at login and at a booked jump's departure, but only while the game runs; a
  booked jump is assumed done 300 s after departure until confirmed (`CARRIER_SETTLE`).
- `HullDamage` also reports fighters (`PlayerPilot` false or `Fighter` true) and the SRV or Nomad you drive, whose
  lines carry no `Fighter` key at all (every ship line in the author's journals has `"Fighter": false`), and `HeatDamage` can repeat every few
  seconds (one alert per 30 s).
- A replay (re-read, legacy import, catch-up after a restart) delivers old events; anything spoken or
  position-based must check `live_event(ts)`.
