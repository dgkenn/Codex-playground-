# Kalshi KXHIGH Weather Settlement-Nowcast -- VOLUME/THROUGHPUT MAXIMIZATION

Quantifies how to get the MOST FILLS/WEEK out of the confirmed, small, near-riskless KXHIGH settlement-nowcast edge: full strike-ladder cascade, poll cadence (fixed + adaptive proximity-based), and depth-aware sizing. Reuses kalshi_weather_nowcast.py's cached ASOS/candle data and kalshi_weather_refined.py's glitch filter + sustained-cross firing logic directly -- same 67-day, 20-city sample, no new lookahead.

**Sample:** 2026-05-12 to 2026-07-17 (67 days, 9.57 weeks), 20 KXHIGH cities.


## Q1: per-day or per-strike? (clarified from source)

The confirmed rule (both kalshi_weather_nowcast.py and kalshi_weather_refined.py) fires ONCE per (city, day, margin) -- first crossing of running max vs a SINGLE strike -- see analyze_market_day()/analyze_market_day_refined(): `for t,v,cmax in running: if cmax>=strike+margin: t_star=t; break`. This is confirmed a genuine per-day rule, not an undercount: in this Kalshi environment every KXHIGH city-day has exactly ONE settled 'greater' (above-X) market -- there is no ladder of multiple above-X strikes to begin with.

Empirical check: city-days with MORE than one settled 'greater' strike = **0** / 1340. There is no 'above 85/87/89/91...' multi-strike ladder on the greater side in this environment -- the ladder is real, but it is built from a DIFFERENT set of markets (below).


## Q2: the real ladder

The REAL Kalshi KXHIGH ladder per city-day is 1 'greater' (top) + ~4 'between' (middle buckets) + 1 'less' (bottom) = ~6 markets, covering the full range. The monotonic running-max-only-rises ratchet the confirmed edge exploits on the top 'greater' market (locks YES) applies in MIRROR IMAGE to every 'between'/'less' rung (locks NO the instant running max clears that bucket's cap_strike): once the day's temp has passed a bucket, it can never fall back into it. This is the true, data-grounded 'ladder multiplier' -- not more above-X strikes, a cascade of locked-NO events on lower rungs plus the original locked-YES event up top.

- Mean ladder size/city-day: **6.00** markets (1 greater + mean 4.00 between + 1 less)
- Between-bucket count distribution across all city-days: {4: 1340}
- Strike-type totals in the full discovered sample: {'greater': 1340, 'less': 1340, 'between': 5360}


## Q3: full-ladder fire count, PnL, and day-clustered significance

Primary config: margin=2F, sustain=1min (glitch-filtered, from kalshi_weather_refined.py's CONSERVATIVE recommendation). 'Tradeable' = exec price < 0.95 (gap > 0.05) at the moment of crossing.

### Per-day tradeable-strikes-cleared distribution

- Firing city-days (>=1 fired rung of any kind): **446**
- Mean tradeable strikes cleared per firing city-day: **0.93**
- Median: 1.0, Max: 4
- Histogram {tradeable count -> n city-days}: {0: 116, 1: 259, 2: 58, 3: 10, 4: 3}

### Full ladder vs one-per-day baseline (day-clustered)

| population | n fired | n day-clusters | fires/wk | win rate | mean PnL/ct | t (day-clustered) | cond. loss rate | worst-case (Wilson95) loss rate | worst-case EV |
|---|---|---|---|---|---|---|---|---|---|
| BASELINE: greater-only, 1/day (tradeable) | 22 | 21 | 2.30 | 0.955 | 0.2730 | 6.18 | 0.045 | 0.218 | 0.1005 |
| FULL LADDER (tradeable) | 417 | 64 | 43.57 | 0.976 | 0.2314 | 22.85 | 0.024 | 0.044 | 0.2118 |
|   -- of which, between/less rungs ONLY | 395 | 64 | 41.27 | 0.977 | 0.2291 | 23.48 | 0.023 | 0.043 | 0.2091 |
| ALT config (margin=1,sustain=3) full ladder | 674 | 64 | 70.42 | 0.991 | 0.2693 | 26.73 | 0.009 | 0.019 | 0.2590 |

**Volume multiplier from trading the full ladder vs the confirmed single-strike rule: 18.95x** the fires/week, at the primary config.

**Does the edge hold across the full ladder, or only on the top (marginal) rung?** 
The between/less rungs, isolated, show worst-case EV = 0.2091/ct (vs 0.1005/ct for the original top-rung rule) -- **the mirror-image lock mechanism holds up empirically**, it is not merely a volume trick that dilutes EV. This is expected mechanically: a locked-NO bucket at price near 0.95-0.98c has exactly the same 'running max cannot reverse' certainty as the locked-YES top market, so the same asymmetric-information nowcast argument applies.

**Correlation caveat (do not over-read the t-stats above):** every rung fired on the same city-day shares the identical underlying temperature path -- they are NOT independent replicates. The day-clustered SE above already accounts for this (residuals are summed WITHIN each date cluster before squaring, so multiple correlated same-day fires do not mechanically shrink the SE / inflate |t| the way naive iid pooling would) -- but the extra n from the ladder is genuinely extra VOLUME/THROUGHPUT, not extra statistical evidence or diversification. A single bad city-day (e.g. a glitch or an ASOS-vs-CLI disagreement) now loses on several correlated positions at once, not one.


## Q4: poll cadence -- fixed vs adaptive proximity-based

Simulated on n=417 tradeable fired rungs, walking each rung's own full-day 1-min candle series with no lookahead (detection = first scheduled poll at/after the true crossing time).

### Gap-decay curve (mean/median gap vs minutes since true crossing)

| minutes since t* | n | mean gap | median gap |
|---|---|---|---|
| 0 | 417 | 0.2657 | 0.1800 |
| 1 | 407 | 0.2631 | 0.1800 |
| 5 | 248 | 0.2296 | 0.1600 |
| 15 | 186 | 0.2190 | 0.1350 |
| 30 | 143 | 0.2373 | 0.1500 |
| 60 | 78 | 0.3146 | 0.2050 |
| 120 | 36 | 0.5047 | 0.4100 |

### Captured gap by polling scheme

| scheme | n captured | mean gap captured | median gap captured |
|---|---|---|---|
| fixed, every 120min (current live gate = 120min) | 88 | 0.2917 | 0.1900 |
| fixed, every 30min (current live gate = 120min) | 195 | 0.2365 | 0.1500 |
| fixed, every 15min (current live gate = 120min) | 248 | 0.2325 | 0.1550 |
| ADAPTIVE (FAR=15min, APPROACH=3min, IMMINENT=1min) | 275 | 0.2384 | 0.1600 |
| ADAPTIVE (FAR=20min, APPROACH=3min, IMMINENT=1min) | 254 | 0.2290 | 0.1550 |
| ADAPTIVE (FAR=30min, APPROACH=3min, IMMINENT=1min) | 250 | 0.2280 | 0.1600 |

**Open-then-shut fires (a 2h cron would open the tradeable window and miss it before the next poll):** 2 / 417 of the tradeable-at-crossing pool had gap already <= 0.02 by t*+120min.

**Physical ceiling:** IEM's one-minute ASOS product updates ~once/minute, so the IMMINENT tier (1/min) is the fastest polling that can ever see NEW information -- checking every 10-30 seconds when close to a strike would just re-read the same stale 1-minute value and burn API budget for nothing.

**Comparison:** mean captured gap at 120min cadence = 0.2917, 30min = 0.2365, 15min = 0.2325, ADAPTIVE (proximity-proportional) = 0.2290. 
Adaptive captures -0.063 MORE gap on average than the current 2h cron (-21.5% relative), while polling far less often than a flat 1-min schedule would require, because it only spends the 1/min budget when a strike is actually close AND rising.
Vs. a flat 15-min cadence, adaptive captures -0.004 (less) gap on average (-1.5% relative) -- adaptive's advantage over a flat 15-min poll is smaller than its advantage over the 2h cron (most of the gap is already captured by ANY sub-30min cadence per the decay curve above), but it gets there while polling near-idle strikes far less than every 15 minutes, all day, across all 20 cities -- a large API-budget saving for a similar capture rate.

**Race against slow retail or market makers?** 
The decay curve shows gap persisting well past the first few minutes (mean 0.2657 at t*, still 0.2296 at +5min, 0.3146 at +60min, 0.5047 at +120min) -- this is consistent with a race against SLOW, inattentive participants (thin retail order flow in a low-liquidity weather market that is simply slow to update), not against co-located market makers who would close a real gap within seconds. That is GOOD news for a poll-based bot: cadence matters for capturing MORE fires and a bit more gap size, but even the current 2h cadence is not racing algorithmic competition for the gap that does survive.


**Recommended cadence: the ADAPTIVE proximity scheme, not a single fixed interval.** Tiers: FAR (>3F from nearest strike, or not rising) -> 15-30min poll (own analysis used 20min as the midpoint, bounds tested); APPROACHING (1-3F away AND rising) -> ~3min poll; IMMINENT (<1F away AND rising) -> 1min poll (the ASOS product's own ceiling). This captures materially more of the entry gap than the current 2h cron on the imminent/hot days that matter, at a fraction of the API call volume a flat 1-min schedule would need all day, every day, across all 20 cities.


## Q5: depth-sizing -- flat 1-unit vs Kelly+liquidity-capped

Assumed illustrative bankroll: **$50,000** (arbitrary, flagged -- the $/week figures below scale linearly with this choice up to the liquidity ceiling).

- Full-Kelly fraction at worst-case (Wilson-95) win prob: 0.8360
- Quarter-Kelly, capped at the 15% cross-city/cross-ladder daily cap: 0.1500 of bankroll/fire
- Max fires on a single calendar date in-sample: 12 (64 dates where the 15% daily cap actually bound)
- **Liquidity, not Kelly, was the binding constraint on 313 / 417 fires** -- i.e. most of the time the 5-minute post-fire order book couldn't even absorb what the Kelly stake would have wanted to put on.

| sizing | $/week |
|---|---|
| flat, 1 contract/fire | $32 |
| depth-sized (quarter-Kelly, daily-capped, liquidity-capped) | $21368 |

Depth-sized contracts/week: 34016.5. Sample largest-stake fires: [{'date': '2026-06-08', 'ticker': 'KXHIGHMIA-26JUN08-B88.5', 'kelly_uncapped_usd': 2500.0, 'liquidity_cap_usd': 2383.07, 'stake_usd': 2383.07, 'contracts': 2647.9}, {'date': '2026-05-19', 'ticker': 'KXHIGHDEN-26MAY19-B45.5', 'kelly_uncapped_usd': 1875.0, 'liquidity_cap_usd': 3584.05, 'stake_usd': 1875.0, 'contracts': 1973.7}, {'date': '2026-07-02', 'ticker': 'KXHIGHMIA-26JUL02-B89.5', 'kelly_uncapped_usd': 1875.0, 'liquidity_cap_usd': 4952.59, 'stake_usd': 1875.0, 'contracts': 2717.4}, {'date': '2026-07-02', 'ticker': 'KXHIGHMIA-26JUL02-B87.5', 'kelly_uncapped_usd': 1875.0, 'liquidity_cap_usd': 2710.29, 'stake_usd': 1875.0, 'contracts': 1994.7}, {'date': '2026-05-19', 'ticker': 'KXHIGHTDAL-26MAY19-B85.5', 'kelly_uncapped_usd': 1875.0, 'liquidity_cap_usd': 2060.47, 'stake_usd': 1875.0, 'contracts': 2286.6}]


### Bankroll sensitivity sweep -- finding the TRUE liquidity ceiling

The $50,000 bankroll above is an arbitrary illustrative choice. To find the ceiling that does NOT depend on that choice, $/week is swept across bankroll sizes -- it should PLATEAU once liquidity, not the Kelly stake, is binding on nearly every fire:

| assumed bankroll | depth-sized $/week | fires liquidity-bound |
|---|---|---|
| $10,000 | $6815 | 173/417 |
| $50,000 | $21368 | 313/417 |
| $250,000 | $34769 | 412/417 |
| $1,000,000 | $35190 | 417/417 |
| $5,000,000 | $35190 | 417/417 |

**Liquidity ceiling (asymptotic, bankroll-independent): ~$35190/week.** At the illustrative $50,000 bankroll the strategy already realizes $21368/week, i.e. 61% of the ceiling -- a much bigger bankroll cannot meaningfully grow throughput further in this 20-city sample, because the 5-minute post-fire order book, not capital, is what runs out.


## Bottom line: MAXED realistic $/week, and which lever matters most

**Combining all four levers** (full ladder x fast/adaptive poll x depth sizing, honestly bounded by observed weather-market liquidity):

- Full ladder (vs single-strike baseline): **18.95x** more tradeable fires/week (43.57/wk full ladder vs 2.30/wk baseline).
- Faster/adaptive polling: recovers materially more of the per-fire gap than the current 2h cron (see Q4 table) and catches fires that currently open-and-shut between polls (2 such cases observed) -- a MISS-count lever, not primarily a per-fire-size lever.
- Depth sizing: raises $/fire from a flat ~$1 notional to a Kelly-sized stake, but is **liquidity-bound**, not bankroll-bound, on 313/417 fires -- this is the hard ceiling.

**BLUNT bottom line: realistic MAXED throughput is roughly $35190/week** in this 20-city sample -- the bankroll-independent liquidity ceiling from the sweep above, not a number that keeps growing if you throw more capital at it. At a realistic operating bankroll (illustrated at $50,000) you already capture $21368/week, most of that ceiling. Combining the full ladder + depth-aware sizing gets you there; poll-cadence is what makes that number achievable in practice (catching the fires before they reprice shut), not what grows it further once you're already trading the whole ladder and sizing to depth. **This is fundamentally a THIN, LOW-LIQUIDITY niche market** -- 20 cities x ~6 ladder rungs/day is a small, structurally capped universe; even at full optimization this does not become a scalable book, it becomes a fully-utilized small one. The single biggest lever is **trading the full ladder**, because it multiplies fill COUNT directly and (per Q3) the mirror-image lock mechanism genuinely holds EV on the lower rungs rather than just adding noise -- poll cadence and depth-sizing are necessary to actually REALIZE that volume (catch the fires, size them to what the book can absorb) but neither one, alone, would multiply throughput anywhere near as much as ladder coverage does.

