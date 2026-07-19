# Kalshi Weather Nowcast Edge -- EXPANSION (Task A: history depth / Task B: more market types)

## Task A -- is longer backtest history obtainable?

**BLUNT VERDICT: YES.** The 67-day floor in `kalshi_weather_nowcast.py` was an artifact of using Kalshi's LIVE `/markets` endpoint, which silently drops settled markets older than a moving cutoff (`GET /historical/cutoff` -> `{'market_settled_ts': '2026-05-19T00:00:00Z', 'orders_updated_ts': '2026-05-19T00:00:00Z', 'trades_created_ts': '2026-05-19T00:00:00Z'}` as of this run). Kalshi's own `GET /historical/markets` / `/historical/markets/{ticker}/candlesticks` / `/historical/trades` endpoints (same cursor pagination, no auth, free) serve the FULL record for markets settled before that cutoff -- verified directly, not assumed.

**Verification:** `HIGHNY-21AUG06-T86` (a pre-"KX"-rename ticker) returned **119** 1-min candlesticks and **5** sample trades from `/historical/*` -- i.e. real price/trade data, not just market metadata, for a market from the `KXHIGHNY` series' earliest era.

**ASOS-side depth (the other half of "obtainable"):**

- NYC @ 2021-08-06: 120 1-min obs in a 2-hour window (should be ~120 if truly minute-resolution that far back -- confirms IEM's free archive is not the constraint).
- MDW @ 2021-08-19: 120 1-min obs in a 2-hour window (should be ~120 if truly minute-resolution that far back -- confirms IEM's free archive is not the constraint).

### Per-series TRUE floor (deep-paginated `/historical/markets`, not assumed)

| series | settled markets (all-time) | unique dates | floor date | ceiling date | true history (days) |
|---|---|---|---|---|---|
| KXHIGHNY | 9208 | 1803 | 2021-08-06 | 2026-07-17 | 1807 |
| KXHIGHCHI | 9205 | 1790 | 2021-08-19 | 2026-07-17 | 1794 |
| KXRAINNYC | 895 | 869 | 2021-09-08 | 2026-07-15 | 1772 |
| KXHIGHMIA | 6976 | 1163 | 2023-05-11 | 2026-07-17 | 1164 |
| KXHIGHAUS | 6957 | 1160 | 2023-05-11 | 2026-07-17 | 1164 |
| KXHIGHDEN | 3630 | 605 | 2024-11-20 | 2026-07-17 | 605 |
| KXHIGHPHIL | 3630 | 605 | 2024-11-20 | 2026-07-17 | 605 |
| KXHIGHLAX | 3354 | 559 | 2025-01-05 | 2026-07-17 | 559 |
| KXLOWTDEN | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTMIA | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTCHI | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTAUS | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTNYC | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTPHIL | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXLOWTLAX | 1302 | 217 | 2025-12-13 | 2026-07-17 | 217 |
| KXHIGHTSEA | 1110 | 185 | 2026-01-14 | 2026-07-17 | 185 |
| KXHIGHTSFO | 1110 | 185 | 2026-01-14 | 2026-07-17 | 185 |
| KXHIGHTDC | 1092 | 182 | 2026-01-14 | 2026-07-17 | 185 |
| KXHIGHTLV | 1110 | 185 | 2026-01-14 | 2026-07-17 | 185 |
| KXHIGHTNOLA | 1110 | 185 | 2026-01-14 | 2026-07-17 | 185 |
| KXHIGHTMIN | 984 | 164 | 2026-02-04 | 2026-07-17 | 164 |
| KXHIGHTATL | 984 | 164 | 2026-02-04 | 2026-07-17 | 164 |
| KXHIGHTPHX | 984 | 164 | 2026-02-04 | 2026-07-17 | 164 |
| KXHIGHTBOS | 978 | 163 | 2026-02-05 | 2026-07-17 | 163 |
| KXHIGHTDAL | 942 | 157 | 2026-02-11 | 2026-07-17 | 157 |
| KXHIGHTSATX | 942 | 157 | 2026-02-11 | 2026-07-17 | 157 |
| KXHIGHTOKC | 942 | 157 | 2026-02-11 | 2026-07-17 | 157 |
| KXHIGHTHOU | 942 | 157 | 2026-02-11 | 2026-07-17 | 157 |
| KXLOWTBOS | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTSEA | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTSFO | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTMIN | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTDC | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTATL | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTDAL | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTSATX | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTOKC | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTLV | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTPHX | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTHOU | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXLOWTNOLA | 636 | 106 | 2026-04-03 | 2026-07-17 | 106 |
| KXRAIN | 20 | 1 | 2026-07-15 | 2026-07-15 | 1 |

Key pattern: **KXHIGH's floor varies by city** (KXHIGHNY/KXHIGHCHI back to 2021-08; KXHIGHMIA to 2023-05; KXHIGHDEN to 2024-11; KXHIGHLAX to 2025-01 -- i.e. real, staggered per-city product launches, not a single 'all weather markets are new' story). **KXLOW's floor is uniform and recent across every city** (2025-12-13) -- the LOW-temp product itself is genuinely new (~7 months old as of this run), independent of the HIGH product's age. This matters directly for Task B: KXLOW cannot get a multi-year backtest no matter which endpoint is used, because the product itself hasn't existed that long -- but it already has ~3x the 67-day sample available if extended (not done in this run; see caveat below).

### Third-party archives (checked read-only, not downloaded)

- **Jon-Becker/prediction-market-analysis (GitHub)** (https://github.com/jon-becker/prediction-market-analysis): Free, public dataset of Kalshi + Polymarket market/trade data, ~33GB compressed. README/ANALYSIS.md describe the collection framework and Parquet schema but do NOT publish a per-series or per-category (e.g. weather) coverage-start-date table -- would require downloading/inspecting the actual data/kalshi/ Parquet files to confirm KXHIGH*/KXLOW* coverage depth, which the task explicitly said not to do (36GB). Plausible it has weather history given it's a general Kalshi crawl, but UNVERIFIED at the per-series level here.
- **Lychee Data** (https://lycheedata.com/kalshi-historical-data): Paid product; markets '7.68M+ unique markets and 72.1M+ historical trades since July 2021' (36GB archive), and has a dedicated weather-markets guide page. July 2021 start matches, almost to the week, the 2021-08-06 KXHIGHNY floor found directly from Kalshi's own /historical/markets above -- strong independent corroboration that 2021 is when Kalshi's weather-market product line (at least NY/CHI) began, not a Lychee-specific artifact.
- **Predexon** (https://docs.predexon.com/api-reference/kalshi/orderbooks): Free orderbook-snapshot history explicitly starts 2026-01-07 -- LESS deep than Kalshi's own /historical/markets for the older-launched cities (2021-2025 depending on series), though it would still beat the 67-day live-only sample for KXLOW (launched 2025-12-13) if its trade/orderbook history genuinely starts Jan 2026. Broader marketing copy claims 'historical data across all venues goes back to 2020' but the documented, dated Kalshi orderbook endpoint itself says Jan 2026 -- took the more specific, dated claim as authoritative over the general one.

### Why this script does NOT simply re-run the full multi-year backtest

Obtainability is now demonstrated, not just claimed -- but pulling ~4.5 years x 20 cities of 1-min Kalshi candlesticks AND matching 1-min ASOS obs (the KXHIGHNY/KXHIGHCHI floor alone implies roughly 25-30x the request volume of the current 67-day cache) is a substantial, separate data-engineering effort with its own rate-limit/runtime budget, and is out of scope for this expansion task, which is specifically about (a) confirming the ceiling is not real and (b) growing volume via more market TYPES on the EXISTING sample. **Recommended next step, not done here:** point `kalshi_weather_nowcast.py`'s market-discovery step at `discover_series_full_history()` (implemented in this file) instead of live-only `/markets`, per-city, starting with KXHIGHNY/KXHIGHCHI (deepest floors, most value per request) before the newer-launched cities.


## Task B -- expanding volume via more market types

Shared sample window (matches the confirmed KXHIGH baseline exactly): **2026-05-12 to 2026-07-17** (67 days).

### B-1. KXLOW (daily low temperature) -- PRIMARY: instant sustained-below-strike cross, buy NO

20 KXLOWT<city> series (1:1 mirror of the KXHIGH city list, verified live -- the un-prefixed guesses like KXLOWMIA/KXLOWDEN/KXLOWNY have zero settled markets, same dead-legacy-ticker pattern as HIGHNY/HIGHAUS/etc). 1271 city-days analyzed over 67 days (11 obs removed by the glitch filter across all stations).

Margin x sustain grid (identical family to the confirmed KXHIGH refinement, 12-cell Bonferroni family, corrected alpha = 0.00417):

| margin | sustain | n fired | win rate | mean PnL/ct | t | p (Bonferroni) | worst-case loss rate | worst-case EV | fires/wk | **passes bar** |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 696 | 0.996 | 0.0175 | 6.54 | 0.0000 | 0.013 | 0.0092 | 72.72 | **YES** |
| 1 | 3 | 671 | 1.000 | 0.0126 | 5.61 | 0.0000 | 0.006 | 0.0069 | 70.10 | **YES** |
| 1 | 5 | 654 | 1.000 | 0.0061 | 4.48 | 0.0001 | 0.006 | 0.0003 | 68.33 | **YES** |
| 1 | 10 | 622 | 1.000 | 0.0009 | 3.12 | 0.0218 | 0.006 | -0.0053 | 64.99 | no |
| 2 | 1 | 522 | 0.994 | 0.0037 | 2.41 | 0.1912 | 0.017 | -0.0073 | 54.54 | no |
| 2 | 3 | 489 | 1.000 | 0.0018 | 3.62 | 0.0036 | 0.008 | -0.0060 | 51.09 | no |
| 2 | 5 | 474 | 1.000 | 0.0010 | 2.60 | 0.1123 | 0.008 | -0.0071 | 49.52 | no |
| 2 | 10 | 449 | 1.000 | 0.0004 | 2.28 | 0.2747 | 0.008 | -0.0081 | 46.91 | no |
| 3 | 1 | 368 | 1.000 | 0.0017 | 3.14 | 0.0205 | 0.010 | -0.0086 | 38.45 | no |
| 3 | 3 | 350 | 1.000 | 0.0014 | 2.71 | 0.0803 | 0.011 | -0.0095 | 36.57 | no |
| 3 | 5 | 335 | 1.000 | 0.0002 | 1.46 | 1.0000 | 0.011 | -0.0111 | 35.00 | no |
| 3 | 10 | 307 | 1.000 | 0.0002 | 1.67 | 1.0000 | 0.012 | -0.0122 | 32.07 | no |

**KXLOW best config: margin=1F, sustain=1min. Verdict: CONFIRMED.** n=696, win rate 0.996, mean PnL 0.0175, t=6.54, worst-case EV=0.0092, fires/week=72.72.

Per-city breakdown at the best config:

| series | city | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|
| KXLOWTDEN | Denver | 65 | 61 | 1.000 | 0.0193 | 0 |
| KXLOWTAUS | Austin (Bergstrom) | 64 | 52 | 1.000 | 0.0050 | 0 |
| KXLOWTNOLA | New Orleans | 67 | 51 | 1.000 | 0.0057 | 0 |
| KXLOWTOKC | Oklahoma City | 66 | 50 | 1.000 | 0.0124 | 0 |
| KXLOWTSFO | San Francisco | 63 | 49 | 1.000 | 0.0042 | 0 |
| KXLOWTNYC | New York (Central Park) | 66 | 48 | 1.000 | 0.0066 | 0 |
| KXLOWTHOU | Houston (Hobby) | 64 | 48 | 1.000 | 0.0067 | 0 |
| KXLOWTMIA | Miami | 64 | 46 | 1.000 | 0.0020 | 0 |
| KXLOWTSEA | Seattle | 66 | 44 | 1.000 | 0.0195 | 0 |
| KXLOWTDAL | Dallas | 65 | 41 | 1.000 | 0.0300 | 0 |
| KXLOWTCHI | Chicago (Midway) | 64 | 37 | 1.000 | 0.0438 | 0 |
| KXLOWTATL | Atlanta | 67 | 33 | 0.970 | 0.0046 | 1 |
| KXLOWTSATX | San Antonio | 66 | 31 | 1.000 | 0.0117 | 0 |
| KXLOWTLAX | Los Angeles | 62 | 26 | 0.962 | 0.0075 | 1 |
| KXLOWTMIN | Minneapolis | 65 | 24 | 1.000 | 0.0208 | 0 |
| KXLOWTPHIL | Philadelphia | 65 | 18 | 0.944 | -0.0009 | 1 |
| KXLOWTBOS | Boston | 67 | 10 | 1.000 | 0.2430 | 0 |
| KXLOWTDC | Washington DC | 38 | 9 | 1.000 | 0.0754 | 0 |
| KXLOWTLV | Las Vegas | 63 | 9 | 1.000 | 0.0365 | 0 |
| KXLOWTPHX | Phoenix | 64 | 9 | 1.000 | 0.0578 | 0 |

SECONDARY (locked-YES, late-cutoff comparison, margin=1F -- mirrors the original KXHIGH SHORT side, not expected to be the strong edge):

| cutoff (LST hr) | fired | win rate | mean PnL | t | fillable rate |
|---|---|---|---|---|---|
| 8:00 | 423 | 0.735 | -0.0018 | -0.16 | 0.433 |
| 10:00 | 413 | 0.741 | 0.0008 | 0.07 | 0.383 |
| 12:00 | 402 | 0.749 | 0.0044 | 0.40 | 0.376 |
| 14:00 | 398 | 0.751 | 0.0093 | 0.86 | 0.364 |

### B-2. KXRAINNYC (daily rain, NYC) -- PRIMARY: first sustained measurable precip, buy YES

Only Kalshi daily single-city rain series with real settled history in this environment (65 days over 65 calendar days). Multi-city `KXRAIN` launched too recently to backtest -- see note below.

ASOS(1-min cumulative precip > 0.005in) vs official Kalshi result, UNCONDITIONAL agreement: **0.815** (12/65 disagree) -- this is the honest tail-risk source for rain (station siting / trace-precip settlement rules vs raw ASOS reading).

| sustain (min) | n fired | win rate | mean PnL/ct | t | p (Bonferroni) | worst-case EV | fires/wk | **passes bar** |
|---|---|---|---|---|---|---|---|---|
| 1 | 20 | 1.000 | 0.0061 | 1.03 | 0.9147 | -0.1550 | 2.15 | no |
| 2 | 20 | 1.000 | 0.0009 | 1.03 | 0.9147 | -0.1602 | 2.15 | no |
| 3 | 20 | 1.000 | 0.0009 | 1.03 | 0.9147 | -0.1602 | 2.15 | no |

**KXRAINNYC best config: sustain=1min. Verdict: KILLED.** n=20, win rate 1.000, t=1.03, worst-case EV=-0.1550, fires/week=2.15.

**Why it fails, structurally (not just n=20):** **19/20** of the fires execute at yes_ask essentially = **$1.00** -- i.e. by the time even the FIRST measurable 1-min precip reading registers, Kalshi's thin rain book has usually already jumped straight to full certainty (no queued liquidity between 'dry' and 'certain rain'), leaving ~zero cents of gap to capture. Only 1 of the 20 fires caught genuine daylight ($0.87 entry). This is a different failure mode than small-n alone: KXHIGH's book has continuous, granular price discovery through the crossing zone (hence a real, capturable gap); KXRAINNYC's book does not.

SECONDARY (locked-NO, late-cutoff, still bone dry):

| cutoff (LST hr) | fired | win rate | mean PnL | t |
|---|---|---|---|---|
| 16:00 | 49 | 0.633 | 0.0135 | 0.89 |
| 18:00 | 47 | 0.638 | 0.0004 | 0.03 |
| 20:00 | 41 | 0.683 | 0.0025 | 0.19 |
| 22:00 | 41 | 0.683 | -0.0082 | -0.62 |

**KXRAIN (multi-city) feasibility:** structurally identical mechanic, 20 settled sub-markets across 1 unique calendar date(s) in this environment. Same 'greater than 0 inches -> locked YES on first measurable precip' mechanic as KXRAINNYC, one sub-market per city per day -- structurally identical, but this series only has settled history for a single calendar date in this environment (too new to backtest; revisit once several weeks of history accumulate).


### B-3. Other Kalshi weather series scanned (not backtested)

- **KXHIGHUS / HIGHUS**: National daily high (highest temp anywhere in the US that day). Same ratchet-up structural mechanic in principle, but the observable is a MAX ACROSS ~20+ independently-reporting stations nationwide, not a single station -- station selection, missing-station handling, and the 'which station is currently hottest' bookkeeping is materially more complex and error-prone than a single-city read. Flagged as the most promising 'other' candidate for a dedicated follow-up, not attempted here.
- **KXCITIESWEATHER**: Highest temperature in cities (daily) -- appears to be an index/composite across the same city list; same complexity note as KXHIGHUS.
- **KXDVHIGH**: Death Valley daily high temp -- structurally identical single-station KXHIGH-style market, not fundamentally new; would need its own ASOS station mapping (Death Valley is not a standard first-order ASOS site) and was not worth a special-case build for one extra city.
- **KXAQICITY**: AQI in city at time (custom) -- plausibly has a similar 'observed value already exceeds threshold' lock, but AQI is a computed/reported index, not a raw physical obs with a comparable free high-frequency feed; not checked for a matching real-time-safe data source.
- **KXHIGHNYD**: Hourly Directional NYC Temperature -- different mechanic entirely (next-hour up/down direction bet), not a settlement-lock nowcast; out of scope.

### B-4. Liquidity reality check on the KXLOW headline number

The KXLOW margin=1/sustain=1 config fires **696** times (72.7/week raw) -- far more than KXHIGH -- but this is a structurally DIFFERENT, weaker edge, not a bigger version of the same one: KXLOW's unconditional YES base rate is only **27.0%** (362/1339 settled) vs KXHIGH's strikes, which are set closer to even money -- i.e. Kalshi's KXLOW strike ladder is set well ABOVE the typical overnight low, so 'low <= strike' (NO) is the base-rate-favored outcome on ~73% of days BEFORE any observation. The mean execution price at fire is **0.9773** (vs KXHIGH's confirmed-config entry of ~0.65) -- the market has usually already priced in most of this near-certainty by the time the sustained-cross fires, so each trade captures only a few cents, not tens of cents, of edge. Worse: only **0.330** of these fires have ANY volume in the following 5 minutes (vs KXHIGH's ~0.96), and the median post-fire 5-min volume is **zero** -- most of the 696 raw fires are not executable as sized. Fillable-subset-only economics: mean PnL 0.0469/ct, t=6.89, **24.03 fillable fires/week** -- still statistically real and still adds capacity, but the deployable number is the fillable one, not the raw one.


## Capacity roll-up: total expanded volume vs KXHIGH-only

| market type | verdict | raw fires/week | fillable rate | **fillable fires/week (honest capacity)** |
|---|---|---|---|---|
| KXHIGH (confirmed baseline, margin=1F/sustain=3min glitch-filtered) | CONFIRMED | 4.39 | 0.958 | 4.20 |
| KXLOW (margin=1F/sustain=1min) | CONFIRMED | 72.72 | 0.330 | 24.03 |
| KXRAINNYC (best config) | KILLED | 2.15 | 0.600 | 1.29 |

**Total fillable (honest) fires/week across CONFIRMED market types: 28.23** vs 4.20 for KXHIGH alone (+571.8%). Raw (unfillable-inclusive) total is 77.10/week -- reported for completeness but NOT the number to size a book against, per the task's own 'executable ask' discipline.


## Bottom line

**Task A: YES, longer history is obtainable, for free, from Kalshi itself** (`/historical/*` endpoints) -- the 67-day sample was a live-API-window artifact, not a real ceiling. Depth varies genuinely by product/city (KXHIGH NY/CHI: ~4.9yr; other KXHIGH cities: 8mo-3yr depending on launch; KXLOW: ~7mo everywhere, a real product-age constraint no endpoint can fix). Not re-run at full depth here (scope/runtime); the mechanism to do so is implemented and tested in this file (`discover_series_full_history`).

**Task B: KXLOW verdict = CONFIRMED, but it is a thinner, much-less-liquid edge than KXHIGH's** (mean 0.9773 entry vs ~0.65, ~33% fillable vs ~96%) -- it still clears every pre-registered statistical bar and adds real, honestly-fillable capacity (24.03 fillable fires/week), just not at face value on the raw fire count. KXRAINNYC verdict = KILLED -- does not clear the bar (single city, thin n=20 sample at the best sustain, honest tail from settlement-rule vs raw-ASOS disagreement). **Total honest (fillable) capacity: 28.23 fires/week vs 4.20 for KXHIGH alone.**

