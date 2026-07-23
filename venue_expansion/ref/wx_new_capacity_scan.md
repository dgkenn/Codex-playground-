# New-capacity scan for K-WX — cross-venue (Polymarket) + new Kalshi families

**Date:** 2026-07-19. **Script:** `wx_new_capacity_scan.py` (read-only, reruns live — numbers below are one
snapshot; rerun for current state). **Context:** the confirmed K-WX edge (buy a rung once the observed
temperature has mechanically locked the settlement outcome) is capacity-capped at ~$1.1-1.6k/wk by real
order-book depth (`wx_capacity_probe.py`), on a 20-city Kalshi `KXHIGH*`/`KXLOWT*` set that is already
100% traded (`wx_market_coverage.py`). Reaching the $4k/mo goal needs either deeper fills on the existing
edge (Synoptic feed — tracked separately) or a genuinely new pool of markets with the same mechanical-lock
structure. This scan looked in two places for that pool, with real API pulls, and reports what it found —
including the honest negatives.

## Ranked shortlist (candidates worth a real study)

| # | Candidate | Why it clears the bar for a study | What a study would need to answer first |
|---|---|---|---|
| 1 | **Polymarket daily high/low temperature bracket ladders** (cross-venue, Q1) | Same mechanical shape as the confirmed Kalshi edge — an 11-rung bracket ladder per city-day that converges to ~$1 once the day's extreme is effectively decided (directly observed: a Hong Kong rung sitting at bestBid 0.999/bestAsk 1.0 with an *empty* ask book mid-day — the "lock" state). 141 open city-day events today across 51 cities, 40 of which Kalshi doesn't list at all (Hong Kong, Shanghai, London, Paris, Tokyo, Moscow, Mexico City, Sao Paulo, ...). Real CLOB order-book depth exists (hundreds-to-low-thousands $ per rung — same order of magnitude as Kalshi's already-thin weather books, not proven deeper, but a *second, additive* pool). | (a) Settlement source is a **Wunderground station-history scrape**, not the NWS CLI report Kalshi uses — the false-lock rate against that specific source is **unmeasured** (Kalshi's own ASOS-vs-CLI tail is a measured 2.5%; Polymarket's basis risk could be better, worse, or about the same — nobody has checked). (b) Whether Polymarket's own retail reprices **as slowly** as Kalshi's — the whole edge lives in that lag, and Polymarket's user base / market-maker behavior is unverified. (c) Withdrawal/custody mechanics (this is a crypto-settled CLOB, not Kalshi's cash account) are out of scope for this scan and need separate operational vetting. |

**Nothing else in this scan clears the bar.** Every other family checked (Q2, and Polymarket's non-temperature
weather markets) is either illiquid right now, structurally a one-shot/seasonal bet with no resting book, or
shares the exact failure mode that already killed the Rain Sleeve and Daily Rain studies (the settlement
bulletin *is* the observable — there's no independently-faster feed to front-run it with, unlike ASOS vs
Kalshi's own book on temperature). Details below.

---

## Q1 — Polymarket (Gamma API `gamma-api.polymarket.com`, CLOB API `clob.polymarket.com`)

Prior state: the repo's only Polymarket work is BTC/ETH crypto (copy-trade, box, lead-lag — all archived
NULL/closed, see `DECISION_MAP.md` F13/D5/PMKT-*). Weather was never scanned. This scan used the `Weather`
tag (`tag_id=84`) plus `public-search?q=weather` to enumerate everything currently open.

| Metric | Value (2026-07-19 snapshot) |
|---|---|
| Open events under the `Weather` tag | 186 |
| Daily high/low temperature city-day events | 141 |
| Unique cities covered | 51 |
| Overlap with our Kalshi 20 | 11 (Atlanta, Austin, Chicago, Dallas, Denver, Houston, LA, Miami, NYC, San Francisco, Seattle) |
| Cities Kalshi does NOT have at all | 40 (Amsterdam, Ankara, Beijing, Buenos Aires, Busan, Cape Town, Chengdu, Chongqing, Guangzhou, Helsinki, Hong Kong, Istanbul, Jeddah, Jinan, Karachi, Kuala Lumpur, London, Lucknow, Madrid, Manila, Mexico City, Milan, Moscow, Munich, Panama City, Paris, Qingdao, Sao Paulo, Seoul, Shanghai, ... — 40 total) |
| Low-temperature coverage | thin — only 2 cities (NYC, Miami) currently list a low-temp ladder; high-temp is the real product |
| Settlement source (sampled: NYC) | `wunderground.com/history/daily/us/ny/new-york-city/KLGA` — a station-history **page scrape**, not the NWS CLI report |
| Sample order book (NYC 80-81°F rung, ask=0.96) | 22 bid levels ($905 total), 4 ask levels ($439 total) via `clob.polymarket.com/book` |
| Lock behavior confirmed live | Hong Kong 30°C rung: bestBid 0.999 / bestAsk 1.0, **ask book empty** mid-day-HK-time — i.e. already in the same "converged, no one selling the lock" state our Kalshi edge buys into |

Other weather-tag families present but NOT temperature ladders (45 events): annual/seasonal one-shots —
"How many 7.0+ earthquakes in 2026", "Category 4/5 hurricane landfall in the US before 2027", "Major
volcano eruption (VEI≥6) in 2026", "Min Arctic sea ice extent", monthly "Precipitation in [city]" (same
family, same accumulation problem, as the killed Kalshi Rain Sleeve), AQI-below-100 markets for 4 US
cities. None of these inspected further here — they're the same low-liquidity/one-shot/no-faster-feed shape
as the Q2 Kalshi negatives below, not the ladder product that matters.

**Read:** the daily temperature ladder is a real, structurally-matching, *much larger* (51 vs 20 cities)
product on a second venue. It is the one finding in this scan that's actually new. It is NOT validated —
basis risk against Wunderground and Polymarket's own repricing speed are both unmeasured — but it's the
right shape for a real study, which none of the other candidates are.

---

## Q2 — New Kalshi families (`/series`, `/events`, `/markets`, `/orderbook`)

`GET /trade-api/v2/series?limit=200` returns Kalshi's **entire** series catalog in one unpaginated call —
12,000 series across 18 categories (Sports 2944, Entertainment 2469, Politics 2058, Elections 1488,
Financials 649, Economics 605, Mentions 379, **Climate and Weather 289**, Science and Tech 281, Crypto 253,
Companies 173, World 143, Health 96, Commodities 71, Social 52, Transportation 39, Exotics 10, Education 1).
A keyword sweep of every OTHER category for stray physical-observable series (river/flood/snowpack/
reservoir/wind speed/tide/hail/seismic/wildfire/storm surge) found **12 hits, none genuine** (false
positives like "Philip Rivers NFL", "Drivers License #1 song", "Trump visits wildfires") — Kalshi's own
category tagging is complete for this kind of product; there's no hidden pocket outside "Climate and
Weather."

Inside the 289 Climate-and-Weather series, 269 are outside our 20 daily-high tickers. Sorting them by
ticker prefix into families and checking each family's `frequency`, live `/series` rules, and open-event
count:

| Family (ticker pattern) | Settlement source | Live now? | Verdict |
|---|---|---|---|
| Deprecated naming variants (`HIGHAUS`, `HOUHIGH`, `DENHIGH`, `KXLOWNY` w/o T, etc.) | NWS CLI | 0 open events | Already identified and excluded by `wx_market_coverage.py` — same stations we trade, dead tickers |
| `KX*SNOWM` (monthly snowfall, ~11 cities) | NWS CLI monthly | 0 open events (July — off-season) | Same accumulation-vs-repricing failure as the killed Rain Sleeve (`DECISION_MAP.md` "RAIN SLEEVE — NULL"); nothing new shown here to reopen it |
| `KXRAIN*` (daily + monthly rain, ~10 cities) | NWS CLI | mixed | Already studied and KILLED twice — Daily Rain (book reprices via retail radar access in ~1-2min, faster than our detection) and Rain Sleeve (96.5% DOA on the clean CLI-MTD trigger). Not re-tested here per the task's instruction not to re-recommend without a new angle — none found |
| `KXAQICITY` (AQI-below-threshold, custom, e.g. NYC/Chicago/Philadelphia/Columbus) | AirNow (EPA real-time feed, city-specific) | **0 open events** at scan time | Structurally interesting (AirNow *is* a fast official feed) but currently untradeable — no open market to even inspect a book on. Not a study candidate until it reopens |
| `KXEARTHQUAKECALIFORNIA` / `KXEARTHQUAKEJAPAN` / `KXBIGGESTQUAKE` (magnitude threshold) | USGS | 3 / 1 / 0 open events | Multi-year single-strike "before 20XX" markets — `yes_bid`/`yes_ask` both `None`, **zero resting book**. Even if a qualifying quake hit, USGS's auto-report is itself the fastest public feed — no lag to exploit, and no liquidity to fill into anyway |
| `KXTORNADO` (monthly count) | NOAA | 1 open event | 11-rung count ladder, but every rung shows `yes_bid`/`yes_ask` = `None` — no book. Also a slow monthly accumulator, same shape as rain |
| `KXNAMEDSTORM` / `KXFIRSTHURRICANE` / `KXHURCLAND` (seasonal hurricane props) | NOAA / NWS | 2 / 3 / 0 open events | Annual/seasonal one-shot bets (which named storm, how many total); no resting book on sampled markets; settles on an NHC advisory that IS the observable — nothing to front-run |
| `KXMEAD` (Lake Mead elevation) | U.S. Bureau of Reclamation | 1 open event | Monthly reservoir-level bracket, no resting book on sampled rung; elevation changes gradually and is reported monthly — no intraday lock moment exists |
| `KXDROUGHTLEVEL` (drought category by state) | U.S. Drought Monitor | 1 open event | Weekly categorical update, no resting book; the Monitor's release IS the observable, no faster feed |
| `KXTEMPNYCH` (hourly directional temp) | **The Weather Company** | 1 open event | Already the excluded family flagged in `wx_market_coverage.py` (KXHIGHNYD note) — settles on a different, non-CLI source our lock edge can't track |
| `KXDVHIGH` (Death Valley daily high) | NWS | **0 open events** | The one genuinely new-city candidate with the *right* settlement source (NWS, same mechanism as our 20) — but currently not listed as an open market. Worth a periodic recheck (cheap: this script already checks it), not a study today |
| `KXHOLIDAYTMAX`/`TMIN` (holiday-specific temp, same 20-ish cities) | The Weather Company | 0 open events (off-cycle) | Same cities we already trade under a different, non-CLI-sourced holiday product; even if reopened this is a ~10-days/year volume dribble on an already-covered city, not a new family |

**Read:** every live-checked candidate either has **zero resting order book** (the sampled rung's `yes_bid`/
`yes_ask` are `None` across earthquake, tornado, named-storm, Lake Mead, and drought markets — there is
simply nothing to fill into), is **currently closed** (AQI, Death Valley, holiday temp), or settles on a
bulletin that is itself the fastest available feed (USGS, NHC, Drought Monitor) — the structural condition
our edge needs (an independent observable that's faster than the *book*, not just faster than the
*headline*) doesn't exist for any of them. This is the same root cause that killed Rain and closed
US-Aggregate Temp, just rediscovered across ten more families.

---

## Bottom line

- **Q1 is a real, not-previously-checked finding**: Polymarket runs the same daily-temperature bracket-ladder
  mechanic across 51 cities (40 net-new vs Kalshi), with a real resting CLOB book. It is the one candidate
  in this scan worth a genuine study — gated on measuring its settlement-source basis risk (Wunderground vs
  the station's official record) and its actual book-repricing speed, neither of which this scan measured.
- **Q2 found nothing new**: every Kalshi family outside the already-complete 20-city temp set is either
  illiquid, seasonal/one-shot with no book, or shares the settlement-IS-the-observable structure that
  already killed rain and closed US-aggregate temp. No new Kalshi family clears the bar for a study.
- Absent a green light on the Polymarket study, **capacity growth has to come from depth on the existing
  edge (Synoptic HF-ASOS feed) and per-fire fill quality**, not from a wider market set — matching what
  `wx_capacity_probe.py` and `wx_market_coverage.py` already concluded on the Kalshi side alone.

Rerun `wx_new_capacity_scan.py` periodically — Kalshi lists/delists series and Polymarket's open-event set
rolls daily, so the specific numbers above (and `KXDVHIGH`/`KXAQICITY`'s open/closed state) will drift.
