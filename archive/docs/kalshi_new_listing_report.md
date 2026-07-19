# Kalshi NEW-LISTING / Cold-Market Mispricing -- OOS Test (K3)

Candidate: djmorgan26/Invest "New Listing" strategy, re-tested with the REAL measured convergence (not the source repo's flat-10c placeholder), net of Kalshi fee AND the wide entry spread cost.

n observations (market x age-bucket entries): **3602**  
n unique settled markets: **1242** across 179 series / 0 categories  
Entry-date span: 2025-01-04 -> 2026-07-12  
Min lifetime required: 96.0h; converged reference = nearest valid quote to +48.0h (window (44.0, 52.0)); wide-spread threshold = 6c.

## Universe breakdown

**By category:**  None=3602


**By age bucket:**  24-48h=1233, 6-24h=1192, 0-6h=1177


**By spread bucket:**  wide=1902, tight=1700


## (a) Calibration: is the early price a WORSE predictor than the converged price?

- Overall Brier(entry_mid): **0.17204** (n=3602)
- Overall Brier(later_mid, +48h): **0.13523** (n=3602)
- Paired Brier delta (entry_sqerr - later_sqerr), day-clustered: mean=0.03162, t=6.613 (n_days=168, n_obs=3602). positive => early price has HIGHER squared error than later (converged) price, i.e. later is a better predictor / real mispricing resolves; negative or ~0 => early is not worse.

**Reliability table, entry_mid:**

| band | n | mean price | realized freq |
|---|---|---|---|
| [0.0,0.1) | 618 | 0.0505 | 0.0599 |
| [0.1,0.2) | 412 | 0.1406 | 0.1917 |
| [0.2,0.3) | 304 | 0.2414 | 0.2401 |
| [0.3,0.4) | 241 | 0.349 | 0.2531 |
| [0.4,0.5) | 388 | 0.4628 | 0.4124 |
| [0.5,0.6) | 665 | 0.5218 | 0.5925 |
| [0.6,0.7) | 211 | 0.6464 | 0.6635 |
| [0.7,0.8) | 217 | 0.749 | 0.7235 |
| [0.8,0.9) | 242 | 0.85 | 0.8017 |
| [0.9,1.0) | 304 | 0.955 | 0.9013 |

ECE(entry_mid) = **0.04276**

**Reliability table, later_mid (+48h):**

| band | n | mean price | realized freq |
|---|---|---|---|
| [0.0,0.1) | 786 | 0.0473 | 0.0331 |
| [0.1,0.2) | 436 | 0.1456 | 0.1651 |
| [0.2,0.3) | 339 | 0.2449 | 0.2153 |
| [0.3,0.4) | 242 | 0.3502 | 0.2314 |
| [0.4,0.5) | 331 | 0.4489 | 0.4985 |
| [0.5,0.6) | 318 | 0.5454 | 0.6006 |
| [0.6,0.7) | 224 | 0.6417 | 0.6786 |
| [0.7,0.8) | 230 | 0.756 | 0.8739 |
| [0.8,0.9) | 231 | 0.8546 | 0.8571 |
| [0.9,1.0) | 465 | 0.9582 | 0.9355 |

ECE(later_mid) = **0.03857**

**By age x spread segment (Brier delta, day-clustered t):**

| segment | n | Brier(entry) | Brier(later) | mean delta | t | n_days |
|---|---|---|---|---|---|---|
| 0-6h|wide | 953 | 0.20974 | 0.14037 | 0.04338 | 3.841 | 98 |
| 0-6h|tight | 224 | 0.15336 | 0.10815 | 0.05102 | 2.383 | 47 |
| 6-24h|wide | 532 | 0.18177 | 0.15324 | 0.01583 | 1.628 | 99 |
| 6-24h|tight | 660 | 0.15163 | 0.12191 | 0.03322 | 2.42 | 64 |
| 24-48h|wide | 417 | 0.17764 | 0.15428 | 0.02608 | 3.213 | 97 |
| 24-48h|tight | 816 | 0.14045 | 0.12596 | 0.02195 | 1.988 | 72 |

## (b) Directional bias by segment

| segment | n | drift (later-entry) mean | drift t | entry bias (entry-result) mean | t | later bias (later-result) mean | t |
|---|---|---|---|---|---|---|---|
| 0-6h|wide | 953 | -0.0093 | -0.582 | 0.0227 | 0.707 | 0.0134 | 0.468 |
| 0-6h|tight | 224 | 0.01 | 0.432 | 0.0104 | 0.228 | 0.0204 | 0.558 |
| 6-24h|wide | 532 | 0.0121 | 0.992 | -0.0015 | -0.043 | 0.0106 | 0.307 |
| 6-24h|tight | 660 | 0.009 | 0.579 | -0.016 | -0.476 | -0.0071 | -0.253 |
| 24-48h|wide | 417 | -0.0006 | -0.056 | 0.0269 | 0.731 | 0.0263 | 0.788 |
| 24-48h|tight | 816 | 0.0111 | 1.149 | -0.0224 | -0.74 | -0.0112 | -0.412 |

## (c) TRAIN-fit directional rule -> TEST PnL, net of fee AND executable entry spread

TRAIN = 807 markets (earliest 65% by close_time), TEST = 435 markets. Rule fit ONLY on the 0-6h 'fresh entry' bucket of TRAIN.

- **wide spread, TRAIN fit**: rule=`NO_EDGE`, train_n=641, mean(result-entry_mid)=0.019, t=0.48 (n_days=73)
- **tight spread, TRAIN fit**: rule=`NO_EDGE`, train_n=113, mean(result-entry_mid)=0.0062, t=0.111 (n_days=33)

**TEST-set results (rule applied out-of-sample):**

| spread bucket | rule | test n | gross PnL/ct (settle) | t | net PnL/ct (settle) | t | gross PnL/ct (conv 48h) | t | net PnL/ct (conv 48h) | t |
|---|---|---|---|---|---|---|---|---|---|---|
| wide | NO_EDGE | 312 | - | - | - | - | - | - | - | - (no directional rule survived TRAIN fit (or empty TEST) -> not traded) |
| tight | NO_EDGE | 111 | - | - | - | - | - | - | - | - (no directional rule survived TRAIN fit (or empty TEST) -> not traded) |

**Pooled TEST**: no segment carried a TRAIN-fit directional rule

## Multiple testing

- Distinct t-tests computed across this whole analysis: **27**
- Nominal alpha: 0.05; Bonferroni-corrected alpha: 0.001852
- Approx. two-sided |t| threshold at Bonferroni alpha: **3.11** (normal approximation; small n_days segments need a fatter threshold than this -- see n_days per row above)
- _t-thresholds are large-sample normal approximations (repo convention); with few day-clusters (k) in a segment the true threshold is higher (fatter t-tails) -- n_days per segment is reported so this can be judged._

## Capacity

- n_fresh_wide_observations_in_sample: 953
- scraped_window_days: 554
- naive_fresh_wide_markets_per_week: 12.04
- naive_note: Settled-market sampling is a retrospective census over a mixed multi-month/year historical window (each series' full settled history, capped per-series), NOT a live continuous listing-arrival stream -- this is a naive linear rate, directional only, per the same caveat used in the K2 structural-arb OOS test.
- mean_entry_hour_volume_contracts: 10.99
- illustrative_weekly_dollar_capacity_if_edge_real: 0.0
- capacity_caveat: No surviving net-of-fee-and-spread edge in the wide-spread bucket -> capacity is moot.

## Method notes / anti-artifact discipline

1. **Executable prices, not mid, for every PnL number**: buying YES pays `entry_ask`; buying NO pays `1-entry_bid`. The wide entry spread's *cost* is therefore baked directly into every net PnL figure (gross columns use mid, purely to show how much the spread itself eats -- gross minus net is the spread+fee cost).
2. **'Empty book' placeholder filtered out**: Kalshi shows yes_bid=$0.01/yes_ask=$0.99 as the tick floor/ceiling when literally nothing is resting yet -- this is NOT a real 98c spread, it is 'no market yet', and is excluded from both entry and reference candles so 'wide spread' only captures genuine (if thin) two-sided quotes.
3. **OOS discipline**: the directional rule (BUY_YES / BUY_NO / NO_EDGE per spread bucket) is fit exclusively on TRAIN (chronologically earliest 65% of markets by close_time) using only the 0-6h 'fresh entry' bucket, then scored, unmodified, on TEST. No rule is ever fit on the data it is evaluated on.
4. **Day-clustered t** throughout: cluster = UTC calendar date of the entry candle, matching the day-clustered-t convention used across this research farm (not observation-level iid t, which would overstate significance given markets sharing a listing day/week are correlated).
5. **+48h reference required to sit mid-life**: only markets with lifetime >= 96.0h qualify, so the 'converged' snapshot is not contaminated by near-resolution informed flow at the other end of the market's life.
6. **Two exit assumptions reported**: hold-to-SETTLEMENT (collect $1/$0, fee only at entry) and hold-to-CONVERGENCE (round-trip: pay the entry spread AND the exit spread, fee both legs) -- the literal 'trade the mispricing, exit once a MM arrives' mechanism is the convergence variant; settlement is the simpler benchmark.

## Verdict

NULL RESULT. No spread-bucket showed a day-clustered t>=2 directional bias on TRAIN (mean(result - entry_mid) for the 0-6h fresh-entry bucket) in EITHER direction, wide or tight spread -- i.e. there is no pre-registerable rule to even test out-of-sample. Fresh Kalshi listings are not systematically mispriced on YES vs NO at the moment of listing, wide-spread or not. This matches the campaign's dominant finding across K2/S1/S4/S5/W1/W3-a: Kalshi's opening quotes are calibrated, not exploitable.
