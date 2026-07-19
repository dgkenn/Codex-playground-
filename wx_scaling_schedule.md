# Scaling schedule + depth-adaptive sizing (operator's roadmap: $10 -> capacity)

Source: `wx_scaling_schedule.py`. Reads the committed `_trackA_results_raw.json` (deployed cell `1_3`:
`MARGIN_F=1.0`, `SUSTAIN_MIN=3`; 678 live-admissible fires, 65 days, 5min free-feed action latency) and the
accrued `wx_book_snapshots.jsonl` (n=33 rows, ONE sweep, ONE day -- 2026-07-19). Sizing engine is
**literally `kwx_runner.size_for_fire`**, imported and called, not re-implemented -- so this is a faithful
simulation of the CURRENT deployed rule (fee-aware quarter-Kelly, 5% base / 12% conviction per-fire cap,
`DEPTH_CAP=25`, 17.5% per-city, 60% daily), not an approximation of it.

**Cross-check**: at $1000 and $100 bankroll this study's Q1 monthly-$ numbers ($899/mo, $793/mo at 21%
unfillable) land within 1-2% of the independent, differently-coded `kwx_bankroll_curve.py` ($901/mo,
$780/mo) -- different Kelly/fee formulation, same conclusion. That agreement is the best available evidence
the engine is being simulated correctly here.

Propose-only: reads backtest + accrued snapshots, calls `kwx_runner` functions read-only. **No live
parameter in `kwx_runner.py` is touched.**

## Q1 -- Scaling schedule

### Full tables (median/mean of 3000 30-day Monte-Carlo trials per bankroll, bootstrapped from the 65 real
fire-days)

**Unfillable = 21% (legacy Tier-1 prior baked into `kwx_sizing.py`/`kwx_bankroll_curve.py`)**

| bankroll | wk$ med | wk$ mean | mo$ med | mo$ mean | mo% med | depth-bind% | median days-to-2x | vs $4k/mo goal |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $10 | $13.87 | $15.61 | $344.82 | $345.81 | 3448% | 8.6% | 6 | 8.6% |
| $25 | $35.94 | $39.54 | $539.78 | $521.93 | 2159% | 22.2% | 6 | 13.5% |
| $50 | $73.27 | $77.27 | $676.89 | $651.68 | 1354% | 37.3% | 6 | 16.9% |
| $100 | $132.03 | $128.22 | $793.16 | $764.84 | 793% | 54.0% | 6 | 19.8% |
| $250 | $200.18 | $186.53 | $883.33 | $852.10 | 353% | 77.7% | 9 | 22.1% |
| $500 | $222.27 | $203.68 | $903.82 | $869.42 | 181% | 98.4% | 17 | 22.6% |
| $1000 | $222.50 | $203.12 | $899.00 | $864.45 | 90% | 100.0% | >30 (censored) | 22.5% |

**Unfillable = 0% (point estimate from `wx_capacity_probe.py --report`, n=33/1 day)** -- upside sensitivity,
not the headline number (n is far too small to retire the 21% legacy prior on):

| bankroll | wk$ med | wk$ mean | mo$ med | mo$ mean | mo% med | depth-bind% | median days-to-2x | vs $4k/mo goal |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $10 | $19.68 | $21.91 | $562.54 | $541.84 | 5625% | 19.9% | 5 | 14.1% |
| $25 | $52.24 | $55.86 | $758.69 | $732.21 | 3035% | 35.9% | 5 | 19.0% |
| $50 | $102.50 | $104.90 | $905.25 | $868.66 | 1810% | 49.9% | 5 | 22.6% |
| $100 | $179.96 | $169.62 | $1029.20 | $988.56 | 1029% | 63.9% | 5 | 25.7% |
| $250 | $258.13 | $237.76 | $1125.68 | $1082.05 | 450% | 82.4% | 7 | 28.1% |
| $500 | $282.07 | $257.45 | $1145.37 | $1099.71 | 229% | 98.6% | 13 | 28.6% |
| $1000 | $283.00 | $257.21 | $1141.50 | $1094.75 | 114% | 100.0% | 26 | 28.5% |

Both scenarios tell the same story: **% return collapses with bankroll (the search-for-yield-on-$10
regime), absolute $/month flattens hard past ~$250-500, and neither scenario gets remotely close to the
$4k/month goal under today's fixed caps** -- best case (0% unfillable) tops out at ~$1145/mo median, 28.6%
of goal; the conservative legacy case tops out at ~$904/mo, 22.6% of goal.

### Where the depth ceiling starts binding

`DEPTH_CAP=25` starts binding at the median-price fire (**exec price $0.89**) at bankroll **~$445** for
base-cap (5%) fires and **~$185** for conviction-cap (12%) fires. Because fire prices are dispersed (not
just the median), the simulated `depth-bind%` column already shows binding creeping in far earlier than
that: 54% of sized fires are depth-capped by **$100** (low-price fires hit the cap sooner -- same $ budget
buys more contracts at 30-60c than at 89c), 78% by **$250**, and effectively 100% by **$500-1000**. Past
$500, adding capital buys essentially nothing (mo$ mean/median is flat or slightly *down* from $500 to
$1000 in both scenarios) -- **the bottleneck from ~$250-500 onward is `DEPTH_CAP`, not bankroll.**

**A second, structural finding**: at the $10 canary itself, the sizing engine's "floor of 1 contract if
affordable" rule (`kwx_runner.size_for_fire`) is doing most of the work, not the nominal 5%/12% caps. At
$10, the 5% cap budget is $0.50 -- below the price of nearly every admissible fire (median $0.89) -- so
almost every fire is sized by the *floor* rule to exactly 1 contract, which is **8.6-9.8% of bankroll on a
single fire, roughly double the intended 5% cap**. This isn't a bug in this study; it's an accurate read of
the currently-deployed code, and it's *why* the $10-tier %/day looks so extreme (both the numerator and the
effective risk-per-fire are elevated versus the caps' design intent). This resolves itself mechanically once
bankroll clears the point where `cap_budget/price >= 1` for most fires -- roughly **$20-25** at the observed
median price.

### Evidence-keyed advancement ladder

Gates are stated in observable, checkable stats, not calendar time. "n fires" means fires the *live* $10
canary has actually recorded (fired attempts, whether filled or not); "EV/ct" means realized post-fee
per-contract PnL from those live fires, not the backtest.

**Rung 1: $10 -> $50**
- Gate: **n_live_fires >= 100** (roughly 1-2 weeks at the historical ~10.4 fires/day rate) AND the realized
  EV/ct 95%-CI lower bound (Wilson or bootstrap) is **> 0** net of fees AND the live fill ratio (fires
  attempted with a real orderbook / fires attempted) is **>= 90%** -- consistent with the fresh
  `wx_capacity_probe --report` read (0/33 empty books) and a guard against the legacy 21%-unfillable prior
  turning out to still be the live reality. AND no observed single-day drawdown exceeding 20% of bankroll
  (the `RUIN` threshold `kwx_sizing.py` already uses).
- Why $50 specifically: this is comfortably past the ~$20-25 floor-of-1-contract regime identified above --
  at $50 the nominal 5%/12% caps, not the integer floor, are what's actually sizing fires, so the risk
  profile matches what the caps were designed and stress-tested (`kwx_sizing.py`) for.

**Rung 2: $50 -> $200**
- Gate: **n_live_fires >= 400-500** (roughly 4-6 weeks at the observed rate) with EV/ct CI still holding
  above 0, PLUS **>=10 distinct-day `wx_capacity_probe.py --snapshot` sweeps accrued** (vs today's 1) with
  the aggregate `--report` read still showing depth comfortably above `DEPTH_CAP` for the stations actually
  firing (matching or beating today's early "15% of rows below cap, 85% at >=2x cap" reading).
- Why $200: at $200, conviction-tier (12%-cap) fires start crossing the depth-bind threshold (computed
  above at ~$185) -- from here on, scaling further without also addressing `DEPTH_CAP` starts leaving
  capacity on the table, so more live depth evidence is the real prerequisite, not just more bankroll.

**Rung 3: $200 -> $500**
- Gate: this rung is where the study's own numbers say bankroll alone stops mattering (`depth-bind%` is
  already 78-98% in this range) -- so the gate is **not** an EV gate, it's the **depth-adaptive-sizing
  decision gate from Q2 below**: adopt (or explicitly decline) a depth-scaled cap once the live snapshot
  sample supports it (see Q2 verdict's data threshold). Advancing bankroll to $500 without that decision
  buys ~$0/mo of extra median profit in this study's own simulation ($903.82 at $500 vs $793.16 at $100,
  legacy scenario -- real but strongly sub-linear, and flat/negative $500->$1000).

**Rung 4: $500 -> $1000+**
- Gate: only advance once the depth-cap question (Q2) has been resolved with real data AND/OR fire volume
  has been raised (faster feed / more markets -- outside this study's scope, but `kwx_bankroll_curve.py`'s
  own conclusion agrees: "to lift the ceiling you need MORE fills... not more capital"). Under the CURRENT
  fixed `DEPTH_CAP=25`, this study's own simulation shows $500 and $1000 bankroll produce statistically the
  same monthly dollars (~$900 legacy / ~$1145 optimistic) -- **additional capital past ~$500 is currently
  capital sitting idle against the depth ceiling, not capital at work.**

### Bottom line vs the $4k/month goal

Under today's fixed sizing, **no bankroll level in $10-$1000 reaches the goal** -- the ceiling this study
measures tops out at ~22-29% of $4k/mo. Reaching $4k/mo requires either (a) resolving the `DEPTH_CAP`
ceiling (Q2, below) with real evidence, and/or (b) more fire volume (faster feed, more markets -- separate
studies), not simply moving more capital into the account.

## Q2 -- Depth-adaptive sizing

### Setup

Today: `min(quarter-Kelly x bankroll, DEPTH_CAP=25)` regardless of the actual book. Tested alternative:
`min(Kelly, alpha x displayed_depth_at_cap)` for `alpha in {0.25, 0.5, 1.0}`, using **per-station median
displayed depth from the live `wx_book_snapshots.jsonl`** (19/20 stations covered; `KPHL` falls back to the
global median). Compared against fixed caps `{25, 50, 100}`.

**Honest caveat, stated once and meant throughout this section**: the depth data is **n=33 rows, ONE
sweep, ONE calendar day (2026-07-19)**, with most stations at n=1-2. Per-station medians here are a first
calibration point, not a stable estimate -- KMSP's single reading (3ct) and NYC's (3015ct) show the
plausible spread is enormous with this little data. Nothing below should be read as "adopt alpha=X now";
see the verdict's explicit data threshold.

### Adverse impact: MEASURED, not assumed

Rather than assume a slippage model, the real resting-ask ladders in the 33 snapshot rows were walked
contract-by-contract for the order size each rule would actually place, computing the true average fill
price vs best ask:

| rule | mean slippage (c/contract) | p90 slippage (c) | fill-failure rate | mean order size (ct) |
|---|---:|---:|---:|---:|
| alpha=0.25 | 3.26 | 11.63 | 0.0% | 236 |
| alpha=0.5 | 5.80 | 16.30 | 0.0% | 472 |
| alpha=1.0 | 8.61 | 23.43 | 0.0% | 944 |
| fixed=25 (today) | 0.68 | 2.48 | 0.0% | 25 |
| fixed=50 | 1.03 | 2.74 | 0.0% | 50 |
| fixed=100 | 1.48 | 3.82 | 0.0% | 100 |

Slippage scales with order size as expected (bigger orders walk deeper into the book), and no order size
tested failed to fill within the recorded ladders (0% fill-failure in this small sample) -- but note
`alpha=1.0` orders average 944 contracts, ~38x today's fixed cap, so even modest per-contract slippage adds
up in dollar terms.

### EV captured (bankroll $2000, a depth-cap-bound regime per Q1)

| rule | EV $/trial-day, no impact | EV $/trial-day, with measured impact | mean contracts/fire |
|---|---:|---:|---:|
| alpha=0.25 | $196.66 | $165.18 | 953 |
| alpha=0.5 | $268.96 | $192.30 | 1112 |
| alpha=1.0 | $307.71 | $197.12 | 1198 |
| fixed=25 (today) | $33.22 | $31.95 | 207 |
| fixed=50 | $66.26 | $61.23 | 414 |
| fixed=100 | $135.66 | $121.92 | 819 |

Even after subtracting the real measured slippage, every depth-adaptive rule (alpha>=0.25) captures more EV
than a fixed cap raised all the way to 100 -- because most stations' median displayed depth (538ct global
median) is already well above 100, so `alpha x depth` clears fixed=100 for the majority of stations. The
gap between "no impact" and "with impact" columns is also informative: impact costs ~16% of gross EV at
alpha=0.25 but ~36% at alpha=1.0 -- diminishing returns kick in well before alpha=1.0.

### Verdict

**Directionally, the fixed `DEPTH_CAP=25` is very likely leaving real EV on the table** -- both the
retrospective volume-at-exec proxy in `_trackA_results_raw.json` (median 5.6ct, but 41% show literal zero
in the execution-minute candle despite the fire filling, meaning this flow-based proxy under-states real
depth and was NOT used as the primary depth source here) and the live snapshot medians (538ct global, mostly
in the hundreds-to-thousands per station) both point well above 25. The EV-captured table above is
consistent with that: raising the cap toward real depth roughly 5-10x's captured EV at a bankroll where the
cap is binding.

**Honest caveat that keeps this a "do not adopt yet":**
1. n=33/1 day is not enough to trust per-station numbers for sizing real money -- a single quiet minute, one
   volatile news day, or a station-specific fluke could be driving any one station's median.
2. The book-walk impact measurement is real, but it only measures **displayed-liquidity slippage** (walking
   the currently-resting ladder) -- it cannot measure **dynamic** adverse selection (other participants
   pulling/repricing quotes in response to a large order arriving), which real books commonly do and which
   this snapshot-based method structurally cannot see.
3. All 33 rows come from near-lock rungs (ask in [50,98]c) on one day; depth behavior earlier in a market's
   life, or on non-near-lock rungs, is unmeasured.

**Recommendation**: do **not** change `kwx_runner.py`. Instead:
- Keep running `wx_capacity_probe.py --snapshot` regularly (the workflow that already force-adds to
  `wx_book_snapshots.jsonl`) through at least the Rung-2 gate above.
- **Data threshold to revisit this decision**: >=300 accrued snapshot rows across >=15 distinct calendar
  days, with per-station depth stable enough that day-to-day and sweep-to-sweep coefficient of variation is
  bounded (e.g. station medians don't swing >2x sweep-to-sweep) for the handful of stations carrying the
  most EV (`KDEN, KMIA, KMSY, KOKC, KSEA` per `wx_ev_concentration.md` -- these five carry 38.7% of total
  EV, so their depth needs the tightest confidence before any cap tied to them is trusted).
- If/when that threshold is met, **alpha=0.25 is the conservative first candidate**, not alpha=1.0: it
  already clears fixed=100 in captured EV, costs the least slippage as a share of gross (16% vs 36%), and
  leaves the largest safety margin against the dynamic-adverse-selection risk this method can't measure.
