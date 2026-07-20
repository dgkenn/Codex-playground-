# SPEC #3 — Jobless-Claims Relist Fade — Backtest Result

**Run date:** 2026-07-20  **Series:** KXJOBLESSCLAIMS

## VERDICT: INCONCLUSIVE (pre-registered escape clause, not a pass, not a fail)

Only 10 distinct release weeks (10 distinct Thursdays) are reachable via the public API, against a pre-registered floor of >=20 validation entries across >=15 distinct release Thursdays (with the first 20 weeks reserved for fit). Even a maximally generous re-split (0 fit weeks, all weeks to validation) tops out at 10 distinct Thursdays, still short of the 15-Thursday floor. This is the pre-registered escape clause firing, not a goalpost move: verdict is INCONCLUSIVE, not a pass and not a fail.

## Data-availability finding (the actual story)

- Pre-registration assumed **100 settled markets / 47 events**.
- `/events?series_ticker=KXJOBLESSCLAIMS` really does list **47** past weekly events (2025-06-12 through 2026-07-16) plus 1 currently open.
- But the public **markets-list / trades API only serves the most recent 10 of those events** (100 markets, 2026-05-14 onward). The other 37 events return `markets: []` from both the series-level and event_ticker-filtered listing endpoints, `markets: []` from `/events/<ticker>?with_nested_markets=true`, and a flat `404 not_found` when a market ticker for that week is queried directly. Confirmed via 4 independent calls, not a script bug.
- Net effect: **n = 10 usable release weeks**, not 47. This is the single biggest reason a real backtest cannot be run here, and it is a *data-availability* wall, not a code bug or a modeling failure.

## Pre-registered minimum-n check

- Distinct release weeks reachable: **10**
- Distinct release Thursdays reachable: **10**
- Pre-registered fit window (first 20 weeks) would consume all 10 available weeks, leaving **0 validation entries** — automatically below the required ≥20 validation entries / ≥15 distinct Thursdays bar.
- Even the most generous alternative split (skip fit entirely, use every week as validation) still only reaches 10 distinct Thursdays — still short of the 15-Thursday floor.
- **Per pre-registration this is an automatic INCONCLUSIVE. No fit/validation stats, no Bonferroni-corrected p-value, and no capacity estimate can legitimately be computed on this sample.**

## Exploratory-only run (NOT a hypothesis test — for the record only)

To confirm the mechanical pipeline (entry rule, tradeability guard, fee model, adverse-selection buckets) is implemented correctly and to see directional signal, the full procedure was still run across all 10 available weeks with an expanding-window empirical-delta model. This is explicitly **not** a validated result — n is far below the pre-registered floor, and theta was NOT selected on an independent fit set (there isn't one), so both grid values are reported descriptively:

### theta_15c
- n entries (after timing gate + tradeability guard): **29** across **7** distinct Thursdays
- win rate: 0.6207 (Wilson 95% CI [0.44, 0.7731])
- mean net EV/contract (fee-inclusive): 0.101
- Thursday-clustered mean: 0.1281, t = 1.353 (n=7 clusters — not a meaningful t-test at this n)
- adverse-selection bucket means by time-to-release: {'>72h': 0.1092, '24-72h': 0.062, '<24h': None}

### theta_20c
- n entries (after timing gate + tradeability guard): **23** across **7** distinct Thursdays
- win rate: 0.5217 (Wilson 95% CI [0.3296, 0.7076])
- mean net EV/contract (fee-inclusive): 0.087
- Thursday-clustered mean: 0.1131, t = 0.843 (n=7 clusters — not a meaningful t-test at this n)
- adverse-selection bucket means by time-to-release: {'>72h': 0.0979, '24-72h': 0.035, '<24h': None}

## Headline numbers (as requested)

- **n (exploratory, theta=15c):** 29 entries / 7 Thursdays — below pre-registered minimum, so treat as descriptive only
- **win rate:** 0.6207
- **EV/contract net of fee:** 0.101
- **Wilson 95% CI (win rate):** [0.44, 0.7731]
- **Thursday-clustered t-stat:** 1.353 (uninterpretable — 7 clusters)
- **Realistic capacity: $0/mo tradeable today.** There is not enough settled/queryable history on this series to certify an edge, so nothing should be deployed, paper or otherwise, until either (a) more weeks accumulate live to reach the pre-registered n-floor, or (b) Kalshi's historical data API is confirmed to expose the pre-2026-05-14 weeks through some other endpoint.

## What worries me most

The 37 "missing" events are not randomly missing — they include the Oct 2025 government shutdown gap (no DOL releases, no jobless-claims markets for ~9 weeks) sitting right in the middle of the window. If earlier-history access is ever restored (a different endpoint, an authenticated tier, etc.), naively concatenating pre- and post-shutdown claims to build the week-over-week delta distribution would silently splice a real macro regime break into the model as if it were noise. Anyone resuming this spec later needs to explicitly exclude the shutdown-adjacent weeks from the delta history, not just paper over the gap in the date index. Second-order concern: even the 10 weeks we *do* have are unusually eventful for jobless claims (visible level swings of 15-20k between adjacent prints in the exploratory table above) — that is exactly the kind of regime where a market maker with a same-day DOL feed prices fast and a lagging empirical-delta model gets picked off, so even a favorable-looking exploratory EV number here should not be trusted as representative of calmer weeks.
