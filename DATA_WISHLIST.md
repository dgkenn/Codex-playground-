# DATA_WISHLIST — high-leverage missing data for a Kalshi-only stack (timestamp-joinable → new strategies)

**Core principle (operator's insight):** an edge = a **timestamped** feed that (a) **LEADS** Kalshi's retail-driven price, or (b) is a **sharper "truth"** than the market — then joined to Kalshi price(t). Kalshi is calibrated *on average* (our nulls), but a slow retail venue can **LAG fast external info** → that latency is the unexplored edge, distinct from static mispricing. Deep history also fixes our recurring thin-n weakness.

## 1. Deep Kalshi microstructure (powers every backtest with real n; enables flow/latency edges)
- **Want:** L2 order-book depth over time, full trade tape (taker_side + size + ts), exact settlement timestamps, market list/first-quote times, maker-reward config per market.
- **Enables:** proper-powered t-stats; informed-flow detection; fill modeling; new-listing mispricing; settlement-latency capture.
- **Leads:** PCeltide/snapevent (fwd L2→Parquet), Jon-Becker (retro trades+markets), vcorp-dev DepthFeed, Kalshi WS.

## 2. Cross-venue lead-lag — OBSERVE Polymarket Global (legal to READ) → TRADE Kalshi (legal). Biggest "combine" unlock.
- **Want:** timestamped price history for the SAME real-world event on BOTH Kalshi + Polymarket Global, aligned by event.
- **Edge:** Global is often faster/deeper (politics, news, crypto); if it moves first, Kalshi lags → trade the lag on Kalshi.
- **Leads:** Jon-Becker (has BOTH venues → align same events), dino.markets, OddsAPI aggregators. (Static convergence was null on crypto; the TIMING/lead-lag angle on liquid news/politics events is untested.)

## 3. Timestamped LEADING feeds per Kalshi category — join to Kalshi price(t)
| Kalshi category | Leading timestamped feed (the "combine") | Edge mechanism |
|---|---|---|
| **Weather** (KXHIGH temp, rain) | real-time **METAR/ASOS** station obs (intraday temp) + NBM/MOS/GFS/ECMWF forecast archives | intraday observed temp LEADS the daily-high settlement; Kalshi retail slow to update |
| **Econ** (CPI/NFP/Fed/GDP/claims) | release **timestamps** (BLS/BEA/Fed) + nowcasts (Cleveland Fed inflation, Atlanta Fed GDPNow) + **CME FedWatch / fed-funds & SOFR futures** | settlement-latency at release; nowcast/rate-futures lead the Fed/econ markets |
| **Index/Financial** (SPX/NDX daily brackets, crypto EOD) | intraday **1-min/tick index** + **SPX/NDX options chain** (implied dist) + VIX; crypto = Binance Vision (have) | live index level + option-implied prob lead the bracket; pinning/gamma |
| **Sports** | **sharp/consensus odds history** (Pinnacle/consensus via TheRundown/OddsAPI/SBR) + injury/lineup feeds + ESPN PBP | sharp line-move leads; injury news gaps |
| **Politics/Events** | poll archives (538/RCP), **GDELT** news-event timestamps, Polymarket Global history | news/poll shock lead; cross-venue |

## 4. New strategies unlocked purely by timestamp joins (no new signal needed — just alignment)
- Weather: `METAR_obs(t)` vs `Kalshi_hightemp_price(t)` → obs leads.
- Econ: `nowcast/release(t)` vs `Kalshi(t)` → latency + info.
- Index: `live_index / option_implied(t)` vs `bracket_price(t)` → pinning/gamma.
- Sports: `sharp_line_move(t)` vs `Kalshi(t)` → line-move lead.
- Cross-venue: `PolyGlobal(t)` vs `Kalshi(t)` → lead-lag.
- **Meta:** with ≥2 timestamped series we can build divergence/lead-lag/cointegration signals we can't build from Kalshi alone.

## Discipline for anything found
NET of Kalshi fees; executable prices; cluster t; multiple-testing; realistic latency (can WE act before Kalshi reprices? our infra is GH-Actions/slow → favor day-scale leads, not sub-second); flag paid-vs-free + history depth + timestamp granularity. Honest nulls.
