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

## FOUND — hunt-3 (sports/index/politics), Sonnet, 2026-07-18
- **Kalshi historical API = the price(t) backbone (free+key):** `/historical/markets/{ticker}/candlesticks` (1/60/1440-min), `/historical/trades`, `/historical/orders`; cursor-paginated, history beyond the ~3mo live window. FETCH FIRST — it's the join key for every lead below. (Partly fixes our thin-n problem for Kalshi itself.)
- **Cross-venue (biggest combine): Polymarket CLOB `/prices-history`** — free, no key, startTs/endTs, 1-min agg → lead-lag vs Kalshi on same events (elections/Fed). Deep L2 backfill only via paid 3rd-party (DepthFeed back to Aug2025).
- **Sports sharp lines: TheRundown API** free tier (20k dp/day, 3 books, opener→close per-line-change ts). Backfill pre-2021 via GitHub `FinnedAI/sportsbookreview-scraper` (2011-21). The-Odds-API has clean 5-min snapshots but historical is PAID. Pinnacle-pure deep = bettingiscool (paid).
- **Index/vol: CBOE `VIX_History.csv`** free daily since 1990 (also FRED VIXCLS); **Stooq** 5-min SPX/NDX free (~1mo/pull → poll-and-archive); ORATS free samples (options IV surface; full=paid); dolthub/options free SQL (verify freshness).
- **Politics/news: GDELT 2.0** free, 15-min news events (news-gap lead; Doc API 3mo, BigQuery to 1979); **538 polls** GitHub CSV (backtest, day/wk granularity).
- **Injury/live: ESPN hidden API** (free, unofficial: scoreboard/PBP/injuries); RotoBaller feeds.
- BUILD ORDER: Kalshi candlesticks (price backbone) → Polymarket prices-history (cross-venue) + GDELT (news) → TheRundown (sports) → VIX+Stooq (index). All free-tier except ORATS-full / Odds-API-historical / Databento-premium / bettingiscool.

## FOUND — hunt-1 (Kalshi microstructure + cross-venue) + hunt-2 (weather+econ), Sonnet, 2026-07-18
### Kalshi price/tape backbone (FREE, full history):
- Kalshi `/historical/trades` (trade_id,ticker,count,yes/no_price,taker_outcome_side,taker_book_side,created_time,is_block) + `/historical/markets/{ticker}/candlesticks` (1/60/1440min) + `/historical/cutoff`. Full history to inception. NO L2 book ever (Kalshi doesn't retain it).
- Incentive/maker-reward config: `/incentive-programs/get-incentives` (period_reward, target_size_fp, discount_bps) → for K1.
- L2 depth (if needed): Predexon (FREE, since Jan2026 ~6mo), PCeltide/snapevent (self-host fwd), michael3vili/Kalshi-Sports-Market-Data (FREE GitHub CSV, 1-sec depth+OFI, sports in-game only). Paid: DepthFeed/Lychee/OddPool.
### Cross-venue (Global↔Kalshi lead-lag): Jon-Becker (free, both venues, DIY title-match) / dino-markets (free, does matching, immature) / DIY Kalshi-hist + Polymarket prices-history + matcher. HARD PART = event matching across venues.
### WEATHER (top actionable lead — day-scale, observable):
- Kalshi KXHIGH/KXLOW settle on NWS CLI, ONE ASOS station/city, LOCAL STANDARD TIME, ~20 cities (Chicago=KMDW, Dallas=KDFW, Houston=KHOU).
- Live obs: Synoptic HF-ASOS (2-5min latency, free tier) = best tradeable; aviationweather.gov METAR (1min,free,15d rolling); IEM ASOS archive (deep to 2000, but real-time lags 1-2d → BACKTEST only). mostlyright-sdk + wethr.net = prebuilt Kalshi-weather tooling (solve station/DST/CLI mapping).
- Forecast: NOAA NBM (best), GFS ensemble (Open-Meteo/AWS 30d).
### ECON: release times fixed 8:30ET/sec (edge=scrape-speed race → NOT actionable on our slow infra, FLAG OUT). Nowcasts: Cleveland Fed inflation (daily), Atlanta Fed GDPNow (FRED/ALFRED), ALFRED vintages (no-lookahead). Rate-futures: Atlanta Fed Market Prob Tracker (free SOFR) / CME FedWatch (paid intraday).

## ACTIONABLE RANKING (our GH-Actions infra = day/hours-scale only, sub-second races excluded)
1. **WEATHER settlement-nowcast (KXHIGH):** observed running-max leads settlement; once max clears strike, outcome ~decided → is Kalshi still mispriced net of fees? Day-scale, observable, backtestable (IEM obs + Kalshi candlesticks). TOP.
2. **Cross-venue lead-lag** (Global→Kalshi on politics/Fed/news). Hours-scale.
3. **Nowcast lead** on CPI/GDP Kalshi markets (Cleveland Fed/GDPNow daily). Day-scale.
