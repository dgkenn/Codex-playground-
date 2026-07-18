# Kalshi Weather Order-Book Depth + Dataset Inventory

Run: 2026-07-18T17:54:50.016451+00:00

## TL;DR (blunt)

- **Historical L2 order-book depth is NOT obtainable for our backtest window** (2026-05-12 to present) from any FREE, currently-held source. Kalshi itself never retained it (confirmed, re-confirmed structurally this run). Predexon has free L2 history back to 2026-01-07 -- which *would* cover our whole backtest window -- but requires an API key from a human signup (dashboard.predexon.com, no card, ~5 min) that this run did not/could not perform; live probe got 401 missing_api_key / 401 invalid_api_key, confirming there is no anonymous tier. **This is the single highest-value follow-up action.**

- **Real LIVE depth pulled instead**, across every open KXHIGH*/KXLOW* 'greater'-strike market, all 20+20 cities, right now (80 markets discovered, 80 order books pulled OK). **Honest finding: at this exact wall-clock snapshot, ZERO KXHIGH markets were in a locked/near-settled state (0 of them >=85c yes_ask)** -- structurally expected, not a bug: this run landed at a UTC time that is late-morning-to-early-afternoon local time across every US timezone, and KXHIGH's 'greater' strike is Kalshi's TOP rung (deliberately set as a tail/unlikely strike), so it only converges toward 100c late in the afternoon on the (rare, ~4.4-fires/week-across-20-cities) days it actually clears. **KXLOW markets, which lock once the overnight low is final (typically by mid-morning), WERE caught locked** (n=4) -- same platform, same order-book/market-maker machinery, just earlier in the day. Those 4 are used below as the best available real analog for 'what fill depth looks like once a temperature-threshold strike locks', with KXHIGH's own thinner (mid/low-bucket) live rows shown separately for direct comparison. **Rerunning this unchanged script in the evening UTC (~19:00-01:00 UTC covers US afternoons) would catch real KXHIGH locks directly** -- flagged as the natural next data pull, not executed here to avoid a multi-hour stall on this task.

- **KXLOW locked-strike depth (the real analog pulled this run)**: n=4 markets with yes_ask>=85c: **median size resting AT the yes_ask = 13.0 contracts** (p25=3.8, p75=37.8); **median depth within 1c of the ask = 65.5 contracts**; **within 2c = 65.5 contracts**. Range across the 4 was wide (9 to 806 contracts within 1c) -- book depth on these thin weather markets is clearly city/market-specific, not a single constant.

- **Real depth vs the candlestick-volume proxy previously used**: median depth-within-2c / 24h-volume ratio = 0.04 (p25=0.03, p75=0.09) across locked-bucket markets with nonzero volume -- i.e. the volume proxy and the real resting book are NOT the same number and the ratio is wide/skewed (see full distribution below); the volume proxy should be treated as directionally correlated with, but not a substitute for, actual resting depth.

- **Missing data that would materially help, ranked:** (1) Predexon L2 key -> real historical depth at every past fire, not just today's live snapshot; (2) a low-latency LIVE obs feed (aviationweather.gov METAR or the PWS/Tempest test in progress) -- without it the nowcast rule can only fire on 1-2-day-stale IEM data and literally cannot be traded live today, which is a bigger blocker than depth itself; (3) forward L2 capture (self-hosted poll of /markets/{ticker}/orderbook at fire-time going forward) to build a real fire-time depth dataset without waiting on a 3rd party or a lucky snapshot timing.


## Task 1 -- Order book acquisition

### 1a. Predexon (3rd-party L2, since Jan 2026)

- Endpoint: `GET https://api.predexon.com/v2/kalshi/orderbooks`

- Auth: x-api-key header, one key covers all Predexon surfaces

- Signup: dashboard.predexon.com, no credit card required for free tier (1000 req/mo; the orderbook-snapshot endpoint itself is marked free & unlimited and does not count against that quota) -- but DOES require an email-verified human signup, which this script cannot do on the operator's behalf. NOT executed here; flagged as an action item.

- Documented history start: 2026-01-07 (per docs; NOT specific to weather/KXHIGH -- docs describe coverage generically as 'a Kalshi market', weather is not named either way)

- Relevance: Our confirmed KXHIGH backtest sample runs ~2026-05-12 to present (67 real days, the live-window floor). Predexon's L2 history starts 2026-01-07, i.e. BEFORE our sample starts -- so a key WOULD in principle cover the whole backtest window. This is a materially useful finding: Predexon is not just a forward-capture option, it is potentially a full historical-L2 backfill for the exact window we already backtested on candlestick/trade data. Getting a key and doing that backfill is the single highest-value follow-up this run identifies.

- Live probe (this run):

  - `no_key`: HTTP 401, body=`{"error":"missing_api_key","message":"API key required","requestId":"04100814583142f1a27b776213b0a494"}`

  - `fake_key`: HTTP 403, body=`{"error":"invalid_api_key","message":"Invalid API key","requestId":"1635d4f783054d0daccecb7faf6e9448"}`

- Conclusion: CONFIRMED live: 401 missing_api_key with no header, 401 invalid_api_key with a fake one -- there is no anonymous or trial tier for this endpoint, unlike Kalshi's own market-data API which is fully open. We do not hold a Predexon key in this environment (checked PREDEXON_API_KEY env var and filesystem, not present). Historical L2 for our exact backtest window is THEREFORE NOT PULLED by this run -- it is technically available (pending a human signup) but not executed here.


### 1b. Kalshi live full-depth order book (pulled this run)

Discovered 80 currently-open, strike_type=='greater' KXHIGH*/KXLOW* markets across all 20+20 city series via `GET https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=X&status=open`, then pulled the REAL order book for each via `GET https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook` (public, unauthenticated, no key needed -- this endpoint has always been open; the gap was historical retention, not access). 80/80 order books returned successfully (0 errors, sample: []).


### Depth distribution by moneyness bucket

| bucket | n | best-ask size (median) | depth@1c (median) | depth@2c (median) | depth@5c (median) | 24h-volume proxy (median) | depth2c/vol24h ratio (median) |
|---|---|---|---|---|---|---|---|
| locked_yes | 4 | 13.0 | 65.5 | 65.5 | 398.5 | 1685.2 | 0.04 |
| high | 3 | 6.0 | 21.0 | 121.0 | 121.0 | 373.0 | 0.06 |
| mid | 3 | 4.0 | 32.8 | 54.8 | 562.3 | 10165.9 | 0.00 |
| low | 12 | 5.5 | 60.8 | 109.0 | 119.5 | 603.6 | 0.14 |
| locked_no | 58 | 94.0 | 251.6 | 376.5 | 920.0 | 517.5 | 3.12 |

`locked_yes` (yes_ask>=85c) is the bucket that matters for the edge -- it's the live analogue of 'the running max just cleared the strike'. `locked_no` (yes_ask<15c) is its mirror (deep NO-favored, e.g. a strike far above today's likely high) shown for symmetry/context, not because our edge trades it directly.


### Same breakdown, split by family (KXHIGH vs KXLOW) -- the honesty check

| family | bucket | n | best-ask size (median) | depth@2c (median) |
|---|---|---|---|---|
| KXHIGH | locked_yes | 0 | -- | -- |
| KXHIGH | high | 0 | -- | -- |
| KXHIGH | mid | 2 | 9.4 | 37.4 |
| KXHIGH | low | 1 | 6.0 | 11.0 |
| KXHIGH | locked_no | 37 | 52.0 | 259.2 |
| KXLOW | locked_yes | 4 | 13.0 | 65.5 |
| KXLOW | high | 3 | 6.0 | 121.0 |
| KXLOW | mid | 1 | 4.0 | 523.3 |
| KXLOW | low | 11 | 5.0 | 112.0 |
| KXLOW | locked_no | 21 | 25293.2 | 25389.2 |

KXHIGH has 0 markets in `locked_yes` and `high` at this snapshot (confirms the time-of-day explanation above); its live rows this run are all `mid`/`low`/`locked_no` -- i.e. we're seeing real KXHIGH book depth for NOT-yet-decided strikes, which is a useful complementary number (pre-fire liquidity) but not the fire-time number the task asks for. KXLOW supplies the only literally-locked rows this run.


### Concrete locked-strike examples (real tickers, real depth, right now)

| ticker | city | yes_ask | best-ask size | depth@1c | depth@2c | 24h vol proxy |
|---|---|---|---|---|---|---|
| KXLOWTDAL-26JUL18-T77 | Dallas | 0.98 | 85.0 | 806.5 | 806.5 | 3240.4 |
| KXLOWTSATX-26JUL18-T77 | San Antonio | 0.95 | 3.0 | 9.0 | 15.0 | 730.4 |
| KXLOWTBOS-26JUL18-T59 | Boston | 0.90 | 22.0 | 22.0 | 22.0 | 570.7 |
| KXLOWTDC-26JUL18-T76 | Washington DC | 0.85 | 4.0 | 109.0 | 109.0 | 2640.2 |

**Per-fire fill capacity, stated plainly (KXLOW analog, since no KXHIGH strike was locked at this snapshot -- see honesty note above):** at a just-locked strike right now, the median resting size AT the yes_ask is 13.0 contracts (~$12 notional at a ~95c fill), and sweeping out to 2c worse gets you to 65.5 contracts (p25=20.2, p75=283.4, n=4 -- a thin sample, treat as directional). That's a REAL, order-book-derived number, not the volume-based estimate used previously -- treat prior depth-sizing outputs (kalshi_weather_volume.py) as directionally right but supersede the fillable-size assumption with this (or a same-time-of-day KXHIGH-specific rerun) when re-running that sizing work.


### 1c. Forward-capture options (not pulled here, noted per task brief)

- **PCeltide/snapevent**: self-hosted forward L2->Parquet capture, free, requires running our own poller against Kalshi's live orderbook endpoint (same one used above) on a schedule -- straightforward to stand up on our existing GH-Actions infra since the endpoint needs no auth.
- **vcorp-dev DepthFeed**: paid, back to Aug 2025 -- would ALSO cover our backtest window (starts before 2026-05-12) if the price is worth it; not evaluated further here since Predexon's free tier covers the same window at $0.
- **Own poller (recommended default if Predexon signup is delayed)**: this script's `fetch_orderbook()`/`analyze_market_book()` functions are already fire-and-forget callable on a cron against the live `/orderbook` endpoint -- cheapest possible forward-capture path, zero new infra, could start TODAY.


## Task 2 -- Full dataset inventory

| Dataset | Have? | Source | Coverage | Cadence | Gap / Action |
|---|---|---|---|---|---|
| Kalshi candlestick price/volume (KXHIGH/KXLOW/KXRAIN) | YES | Kalshi /historical/markets/{ticker}/candlesticks (free, unauth) | full series life (KXHIGHNY/CHI to 2021-08; KXLOW* to 2025-12-13) | 1/60/1440-min bars | none -- backbone, already the price(t) join key for the confirmed edge |
| Kalshi trade tape (/historical/trades) | YES | Kalshi /historical/trades (free, unauth) | full series life, same floor as candlesticks | per-trade (taker_side, size, ts) | none -- have it, underused for weather specifically so far |
| Kalshi L2 order-book depth, LIVE (right now) | YES | Kalshi /markets/{ticker}/orderbook (free, unauth) -- THIS RUN | current snapshot only, all open KXHIGH*/KXLOW* markets, all cities | point-in-time (as pulled) | have live; need FORWARD capture at fire-time to stop relying on 'now' as a proxy for 'the instant a strike locks' (see forward-capture gap below) |
| Kalshi L2 order-book depth, HISTORICAL (over the backtest window) | NO | Kalshi itself: none (confirmed, no /historical/.../orderbook route). 3rd party: Predexon (api.predexon.com/v2/kalshi/orderbooks, needs a key, free tier, history from 2026-01-07, which covers our whole backtest window). Others: PCeltide/snapevent (self-host forward-only), vcorp-dev DepthFeed (paid), Lychee/OddPool (paid). | N/A -- not pulled this run (no key) | N/A | HIGHEST-VALUE GAP: sign up for a free Predexon key (~5 min, no card) and backfill L2 for the 2026-05-12-to-present KXHIGH window -- would let every historical fire in the existing backtest get a REAL fillable-size number instead of the volume proxy, materially tightening the depth/PROFIT estimate this whole task is about. |
| Kalshi settlement results | YES | Kalshi /historical/markets (result field) + /markets settled listing | full series life | per-market, at settlement | none |
| Kalshi incentive/maker-reward config | YES | /incentive-programs/get-incentives | current program config | per-period | not weather-specific; low priority for this edge (edge is a taker fire, not a maker strategy) |
| IEM ASOS 1-min obs (the nowcast signal itself) | YES | mesonet.agron.iastate.edu asos1min.py (free) | deep archive (>2000) but 1-2 day REPORTING LAG for the most-recent data in this environment -- fine for backtest, NOT usable for live fire-time action without a faster feed | 1-min | keep for backtest; pair with a low-latency LIVE source below for actual trading (this is the biggest LIVE-side gap, separate from the L2 gap) |
| Low-latency LIVE obs (2-5 min, tradeable in real time) | NO | candidates: Synoptic HF-ASOS (free tier, 2-5 min latency), aviationweather.gov raw METAR (1-min cadence, free, 15-day rolling), fast PWS/Tempest network (BEING TESTED per task brief) | N/A -- not integrated into the live firing path yet | 1-5 min depending on source | HIGH VALUE: without this, the 'buy YES the instant running-max clears' rule can only fire on 1-2-day-stale IEM data, i.e. cannot actually be traded live at all today -- this is arguably a bigger blocker than L2 depth, since depth is moot if we can't fire in time. aviationweather.gov raw METAR is verified reachable (used in DATA_WISHLIST research) and free/1-min/unauth -- fastest path to close this gap. |
| 5-min ASOS | NO | not separately pulled -- IEM's 1-min feed is a superset (5-min values are derivable from the 1-min series already held) | N/A | N/A | no action needed -- redundant with 1-min IEM already in hand |
| 6-hr / 24-hr METAR max/min temperature groups | NO | embedded in raw METAR remarks (T-group, 6-hr max/min group) via aviationweather.gov or IEM METAR archive | N/A -- not parsed out separately; we use the raw 1-min ASOS series and compute our own running max, which is a strict superset of what the official 6-hr group would tell us with FASTER resolution | N/A | low priority -- our own running-max-of-1-min-obs computation already dominates the coarser 6-hr METAR group for this purpose; worth pulling only as an independent QC cross-check against the CLI settlement value |
| ISD / NCEI QC'd hourly obs | NO | ncei.noaa.gov/data/global-hourly (confirmed reachable this run, per-station CSV, needs station ISD-id mapping) | deep archive, QC'd, but hourly (coarser than IEM 1-min) and typically days-to-weeks LAGGED for the most recent data -- backtest/QC use only | hourly | MEDIUM: useful as an independent QC cross-check on the IEM 1-min series (catch sensor glitches the glitch-filter might miss) and to extend obs history further back than IEM for older-launched series (KXHIGHNY/CHI back to 2021); not urgent since IEM already covers our full current backtest window |
| Official NWS CLI daily climate record (the actual settlement source) | YES | api.weather.gov/products/types/CLI (confirmed reachable this run, free, text product feed) -- this IS the ground truth Kalshi settles against, per every KXHIGH market's rules_primary text | current + rolling text-product archive per office | once/day per station (the actual settlement event) | HIGH VALUE, currently underused: we backtest against IEM's running-max 1-min series as a PROXY for the CLI value, but the CLI product itself is pullable and would let us directly verify/QC every historical settlement instead of trusting the proxy -- cheap, should be added to the settlement-recording pipeline (settle_recorder.py) as a real-value cross-check. |
| MADIS QC-flagged obs | NO | madis-data.ncep.noaa.gov (reachable, but MADIS generally requires a registered account for full dataset access beyond the public sample) | unknown without an account | varies by dataset (mesonet, metar, etc.) | LOW: marginal value over IEM's own QC + our glitch filter, given the extra registration friction; not worth pursuing ahead of the L2/live-latency gaps above |
| Fast PWS / Tempest personal-weather-station network | being tested (per task brief, outside this script's scope) | Tempest/WeatherFlow, or PWS aggregators (Synoptic, Weather Underground PWS) | unknown -- station siting/QC quality is the open question, not availability | 1-min or faster typically | status check owned elsewhere; if it pans out it's the best LIVE-latency fix, better than aviationweather.gov METAR (PWS updates faster than METAR's ~1-min-but-often-slower-in-practice cadence) -- worth reporting results back into this inventory once that test concludes |
| NBM (National Blend of Models) forecast | NO | nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/ (confirmed reachable this run, free, grib2/text, hourly runs) | current + short rolling archive on NOMADS; deeper archive on AWS (noaa-nbm-grib2-pds) if needed | hourly model runs, hourly-to-daily lead times out to ~10 days | NOT for the trade itself (the edge is a same-day nowcast rule that doesn't need a forecast) -- but valuable for TARGETING/SIZING: NBM's day-ahead high-temp percentile spread tells us which city/day pairs are likely to have a strike CLOSE to the true outcome (higher expected fire probability + tighter book around the eventual locked strike) worth prioritizing capital toward. Medium priority, acquire if sizing work resumes. |
| HRRR (High-Resolution Rapid Refresh) forecast | NO | AWS open data noaa-hrrr-bdp-pds (confirmed reachable this run, free, S3, hourly runs, CONUS 3km) | rolling ~2 days live + full archive back to 2014 (public S3) | hourly runs, hourly output out to 18-48h | SAME rationale as NBM (targeting/sizing, not the trade) but HRRR's higher resolution + faster update cycle makes it the better same-day 'how confident should the running-max signal make us before it even starts running' input if this is pursued -- medium priority |
| MRMS radar (precip, for KXRAIN-style markets) | NO | AWS open data noaa-mrms-pds (confirmed reachable this run, free, S3) | rolling + archive; national radar-based QPE mosaics | 2-min | only relevant if the rain-market line of work (KXRAINNYC, currently a small secondary line per kalshi_weather_expand.py) gets scaled up -- not urgent given KXHIGH/KXLOW are the volume leaders; acquire opportunistically if rain-market volume grows |
| ASOS present-weather codes (precip type/intensity) | NO | embedded in the same raw METAR stream we already have access to via aviationweather.gov / IEM -- not currently PARSED OUT | N/A -- present in data we already fetch, just unparsed | per METAR ob (~hourly-to-5-min depending on station/conditions) | cheap: same source we already hit for temperature, just add a parser for the present-weather group; do only if/when rain markets are prioritized |

### Live reachability checks (this run)

| endpoint | reachable | http_code |
|---|---|---|
| HRRR (AWS open data, noaa-hrrr-bdp-pds) | True | 200 |
| MRMS (AWS open data, noaa-mrms-pds) | True | 200 |
| NBM (NOMADS nomads.ncep.noaa.gov/pub/.../blend/prod) | True | 200 |
| NWS CLI product feed (api.weather.gov/products/types/CLI) | True | 200 |
| MADIS (madis-data.ncep.noaa.gov) | True | 200 |
| NCEI ISD global-hourly access root | True | 404 |
| IEM ASOS 1-min (already-used data path) | True | 200 |

### Ranked remaining gaps (highest value first)

1. **Predexon L2 API key** (free, needs human signup) -- backfills REAL historical depth over the entire existing KXHIGH backtest window (Predexon coverage starts 2026-01-07, before our 2026-05-12 sample floor). Directly upgrades every backtested fire from a volume-proxied fill estimate to a real one. Do this first.
2. **Low-latency live obs** (aviationweather.gov METAR, or the PWS/Tempest test in flight) -- without this the edge cannot fire in real time at all (IEM lags 1-2 days in this environment); this blocks LIVE trading independent of the depth question and should be resolved in parallel.
3. **Own forward L2 poller** -- zero-cost, can start immediately, builds a real fire-time depth dataset going forward regardless of what happens with #1.
4. **NWS CLI product cross-check** -- cheap correctness upgrade to the settlement pipeline (verify against the actual settlement source, not just the IEM proxy).
5. **NBM/HRRR for targeting** -- not for the trade itself, but for capital prioritization across city/day pairs; medium priority, not blocking.
6. ISD/NCEI, MADIS, MRMS, present-weather codes -- lower priority, either redundant with what we hold or scoped to a product line (rain markets) that isn't the current focus.
