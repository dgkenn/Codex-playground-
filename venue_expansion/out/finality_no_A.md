# FINALITY-NO + WHOLE-LADDER -- BUILD A (primary) -- result

Spec: `venue_expansion/FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27).  Code: `venue_expansion/finality_no_A.py`.  Per-fire records: `venue_expansion/out/finality_no_A.json`.  Seed 20261028.  Reproduce: `python venue_expansion/finality_no_A.py setup && ... order && ... candles && ... signals && ... report`.

## Verdicts

- **Part 1 (FINAL-NO by never-arrival): INSUFFICIENT**  -- PASS cells at L=10: none; KILL triggers: none; best L=10 one-sided 97.9% EV upper bound over the 12 cells: 24.51c volume-weighted (formal) / 4.35c unweighted.
- **Part 2 (whole ladder): NOT_EVALUABLE**  -- gate (Part 1 PASS or TERMINAL_FINALITY PASS): NOT met; companion FINAL-YES builds on disk: {'finality_A': 'INSUFFICIENT', 'finality_B': 'INSUFFICIENT'}.

{{COMMENTARY}}

## Sampling / coverage (read this first)

- **Part 1 priced stage: 4,305 of 8,699 never-arrival-fired bracket rungs have candlesticks = 49.49% (PARTIAL: a random prefix of a shuffled event order, seed 20261028).**  Signal-level facts (fire counts, false-lock rates) always use all 6,039 scored events.
- **Part 2 ladder stage: 1 of 2,735 signalling city-days have the whole 6-rung ladder priced = 0.04%** (a random prefix of the shuffled event order (seed 20261028), never re-sorted).
- Work order = sorted event list shuffled once with a fixed seed (`cache/finality_no/A/event_work_order.json`), never re-sorted.  Tier 1 (Part 1) prices only the bracket rungs that have a never-arrival fire in some cell (an obs-only decision made before any price or outcome was read); tier 2 (Part 2) prices every rung of every event with a day-level primary-cell signal.  The overshoot reference arm (anchor d) therefore only exists where tier 2 reached.

## Universe, feeds, skips

- 40 US HIGH/LOW series (20 stations), settled rungs with official `result` and close_time UTC date in 2026-05-23..2026-10-20: **6,039 city-day events x 6 rungs (4 brackets `-B`, 2 thresholds `-T`)**.  Event-level skips: none; pre-filter skips (counted, not tested): {'outside_window': 61548, 'no_official_result': 6} (`outside_window` = settled rungs of these series outside the frozen close-date window; `no_official_result` = 6 rungs with no yes/no result).  Series outside the 40 mapped ones are not tested (no verified station / fixed LST offset).
- Obs feed per event: {'iem_1min': 5109, 'iem_routine_fallback': 930}.  Market lists and IEM obs were COPIED from the sibling FINAL-YES build's cache (same universe, same sources; copying avoided re-pulling ~40k market rows and 240 IEM station-month files) and spot-verified against the live API (batch-vs-single candle check below; every settled event has exactly 6 rungs).
- Candle pull: live-settled rungs use the batch endpoint `GET /markets/candlesticks?market_tickers=...` (one call per event); verified byte-identical to the per-market endpoint on 8/8 rungs (`cache/finality_no/A/batch_vs_single_check.json`).  Hist-settled rungs use `/historical/markets/{ticker}/candlesticks`.  All parsed by the shared `edge_sizing_v2.normalize()`.

## Worked timezone example (anchor c)

Fire `KXLOWTNYC-26OCT16-B52.5` (station NYC, running MIN, fixed standard offset UTC-5; bracket [52,53], official result `no`, official value 59.00).

- Local-STANDARD day starts **2026-10-16 05:00Z** (= 2026-10-16 00:00 LST, epoch 1792126800) and ends at LST midnight **2026-10-17 05:00Z** (= 2026-10-17 00:00 LST, epoch 1792213200); Kalshi's own `close_time` equals this (asserted for every event, tolerance 60 s).  In DST wall-clock the same instant is 2026-10-17 01:00 (DST wall clock): the 'local day' is NOT wall-clock midnight-to-midnight in summer (the classic 1-hour-skew trap).
- The running extreme E = 59.0 was last set at **2026-10-16 05:00Z** (= 2026-10-16 00:00 LST).  The signal observation (index k=1320 of 1440 obs that day) is **2026-10-17 03:00Z** = 2026-10-16 22:00 LST, 120 min before close; signal stamped obs + 60 s = **2026-10-17 03:01Z** (epoch 1792206060).  Candle epochs are UTC `end_period_ts`, same clock as the obs epochs and `close_time`, so all three compare directly.
- L=10 entry: first candle with end_period_ts >= sig_ts + 600 s = 2026-10-17 03:11Z; found **2026-10-17 04:27Z** (= 2026-10-16 23:27 LST), NO cost = 100 - yes_bid = 97c, fee 1c, volume 0.0; settles `no` -> pnl 2c.

Proof the day window is right: the extreme of the 1-minute obs inside the window shifted by s hours, versus Kalshi's own `expiration_value` for this event:

| s (h) | -3 | -2 | -1 | +0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| extreme F | 57.0 | 58.0 | 58.0 | 59.0 | 58.0 | 55.0 | 52.0 |
| = official? | no | no | no | **YES** | no | no | no |

Across ALL events, exact-match fraction of the shifted-window extreme against the official integer (1-min feed):

| kind | s=-3 | s=-2 | s=-1 | s=+0 | s=+1 | s=+2 | s=+3 |
|---|---|---|---|---|---|---|---|
| max exact-match % | 41.4% | 41.7% | 42.4% | 43.1% | 42.8% | 42.8% | 42.8% |
| max mean abs err F | 0.96 | 0.92 | 0.90 | 0.89 | 0.89 | 0.88 | 0.88 |
| min exact-match % | 69.5% | 70.5% | 72.3% | 76.9% | 70.4% | 65.0% | 58.8% |
| min mean abs err F | 0.73 | 0.69 | 0.60 | 0.53 | 0.61 | 0.75 | 0.92 |

The declared window (s=0) is the optimum for LOW markets and error grows with |s|; HIGH markets peak in the afternoon so the day boundary is nearly irrelevant for them (weakly informative).  The strict check is the `close_time == LST midnight` assertion.  Note the 1-minute IEM extreme equals Kalshi's official integer in well under 100% of days (official value is a different feed / rounding); that is exactly why `G >= 2` is in the spec.

## Worked no-look-ahead example (anchor b)

Same fire (`KXLOWTNYC-26OCT16-B52.5`, primary cell G4_R2_H3_W120, never-arrival): at obs index k=1320, E = 59.0F, current temp 64.0F; the detector is a `Stream` that consumes one obs at a time, so state after obs k is a function of obs[0..k] only.  max obs ts in the prefix = 2026-10-17 03:00Z < signal ts 2026-10-17 03:01Z: True.  Re-running the detector on obs[:k+1] only reproduces the fire: True; re-running on the full day with every later obs replaced by 14.0F (an adversarial +/-50F move) reproduces it: True.

Asserted in code for **every** distinct signal index of **every** event (29,553 detector re-runs: truncated prefix, +50F future, -50F future); the script aborts on any difference.  0 violations (the run completed).

## Part 1 -- FINAL-NO by never-arrival (bracket rungs)

**Primary cell G4_R2_H3_W120 at L=10:** universe fires 4,969 (false locks 88 = 1.77%, Wilson UB 2.18%, over 151 days / 20 stations); priced stage: n priced = **78** of 2495 covered fires (untradeable 96.9%), priced false locks 39 (50.00%, Wilson UB 60.83%), EV/contract volume-weighted **2.15c** (unweighted -0.73c), signed day-clustered t **0.69** (bar 3.41), 52 days, 19 stations; entries with volume > 0: 29 (zero-volume entries carry zero weight in the weighted estimator).

### All 12 cells, L = 10 (the deployable arm), formal day-clustered statistics (calendar event-date clusters)

| cell | L | fires (covered) | priced (vol>0) | untradeable | false locks priced (rate, Wilson UB) | mean NO cost c | EV vw c | EV unw c | t vw (bar) | days/stn | UB97.9 c (vw / unw) | bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G2_R2_H3_W60 | 10 | 4032 | 101 (38) | 97.5% | 42 (41.6%, 51.3%) | 58.6 | -3.42 | -1.23 | -1.33 (3.36) | 71/19 | 1.89 / 1.54 | fails 1p,2,3,5 |
| G2_R2_H3_W120 | 10 | 4305 | 239 (89) | 94.4% | 73 (30.5%, 36.7%) | 69.3 | 3.68 | -0.83 | 0.71 (3.31) | 110/20 | 14.30 / 1.11 | fails 1u,1p,3,5 |
| G2_R4_H3_W60 | 10 | 3357 | 60 (27) | 98.2% | 35 (58.3%, 69.9%) | 44.4 | -5.28 | -3.73 | -1.67 (3.43) | 47/19 | 1.35 / 0.86 | fails 1p,2,3,4,5 |
| G2_R4_H3_W120 | 10 | 3672 | 133 (49) | 96.4% | 56 (42.1%, 50.6%) | 58.1 | -2.94 | -1.24 | -2.30 (3.34) | 77/20 | -0.30 / 1.00 | fails 1p,2,3,5 |
| G4_R2_H3_W60 | 10 | 2322 | 40 (16) | 98.3% | 29 (72.5%, 83.9%) | 29.6 | -6.29 | -3.12 | -1.25 (3.52) | 34/17 | 4.37 / 1.83 | fails 1p,2,3,4,5 |
| G4_R2_H3_W120 | 10 | 2495 | 78 (29) | 96.9% | 39 (50.0%, 60.8%) | 49.7 | 2.15 | -0.73 | 0.69 (3.41) | 52/19 | 8.61 / 2.40 | fails 1p,3,4,5 |
| G4_R4_H3_W60 | 10 | 1887 | 30 (16) | 98.4% | 24 (80.0%, 90.5%) | 23.4 | -6.22 | -4.40 | -1.25 (3.63) | 26/16 | 4.48 / 2.08 | fails 1p,2,3,4,5 |
| G4_R4_H3_W120 | 10 | 2085 | 50 (19) | 97.6% | 31 (62.0%, 74.1%) | 39.5 | -1.92 | -2.48 | -25.15 (3.47) | 40/19 | -1.76 / 1.65 | fails 1p,2,3,4,5 |
| G6_R2_H3_W60 | 10 | 1084 | 17 (8) | 98.4% | 13 (76.5%, 90.4%) | 24.0 | -1.67 | -1.47 | -4.68 (3.90) | 17/13 | -0.88 / -0.12 | fails 1u,1p,2,3,4,5 |
| G6_R2_H3_W120 | 10 | 1179 | 29 (14) | 97.5% | 19 (65.5%, 80.1%) | 32.8 | 12.70 | 0.62 | 2.32 (3.69) | 23/16 | 24.51 / 4.35 | fails 1u,1p,3,4,5 |
| G6_R4_H3_W60 | 10 | 860 | 13 (7) | 98.5% | 10 (76.9%, 91.8%) | 23.4 | -2.00 | -1.31 | n/a (4.18) | 13/10 | -2.00 / -0.33 | fails 1u,1p,2,3,4,5 |
| G6_R4_H3_W120 | 10 | 963 | 20 (9) | 97.9% | 14 (70.0%, 85.5%) | 29.9 | -2.00 | -0.95 | n/a (3.85) | 18/12 | -2.00 / -0.14 | fails 1u,1p,2,3,4,5 |

Universe-level (signal-only, every event, no pricing needed) false-lock rate per cell -- bar 1 is evaluated on this AND on the priced subset:

| cell | fires | settled YES (false lock) | rate | Wilson UB | days | stations | NO via never-arrival | NO via overshoot-after-signal | other |
|---|---|---|---|---|---|---|---|---|---|
| G2_R2_H3_W60 | 8,159 | 153 | 1.88% | 2.19% | 151 | 20 | 7,889 | 117 | 0 |
| G2_R2_H3_W120 | 8,699 | 182 | 2.09% | 2.41% | 151 | 20 | 8,389 | 128 | 0 |
| G2_R4_H3_W60 | 6,832 | 129 | 1.89% | 2.24% | 151 | 20 | 6,615 | 88 | 0 |
| G2_R4_H3_W120 | 7,455 | 142 | 1.90% | 2.24% | 151 | 20 | 7,217 | 96 | 0 |
| G4_R2_H3_W60 | 4,625 | 76 | 1.64% | 2.05% | 151 | 20 | 4,473 | 76 | 0 |
| G4_R2_H3_W120 | 4,969 | 88 | 1.77% | 2.18% | 151 | 20 | 4,794 | 87 | 0 |
| G4_R4_H3_W60 | 3,786 | 61 | 1.61% | 2.06% | 151 | 20 | 3,669 | 56 | 0 |
| G4_R4_H3_W120 | 4,176 | 68 | 1.63% | 2.06% | 151 | 20 | 4,045 | 63 | 0 |
| G6_R2_H3_W60 | 2,123 | 47 | 2.21% | 2.93% | 151 | 20 | 2,035 | 41 | 0 |
| G6_R2_H3_W120 | 2,311 | 55 | 2.38% | 3.08% | 151 | 20 | 2,204 | 52 | 0 |
| G6_R4_H3_W60 | 1,715 | 37 | 2.16% | 2.96% | 151 | 20 | 1,650 | 28 | 0 |
| G6_R4_H3_W120 | 1,911 | 41 | 2.15% | 2.90% | 151 | 20 | 1,835 | 35 | 0 |

### L = 0 and L = 20 (reference arms), same statistics

| cell | L | fires (covered) | priced (vol>0) | untradeable | false locks priced (rate, Wilson UB) | mean NO cost c | EV vw c | EV unw c | t vw (bar) | days/stn | UB97.9 c (vw / unw) | bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G2_R2_H3_W60 | 0 | 4032 | 132 (51) | 96.7% | 54 (40.9%, 49.4%) | 58.7 | -2.10 | -0.65 | -0.95 (3.33) | 84/20 | 2.47 / 1.25 | fails 1p,2,3,5 |
| G2_R2_H3_W60 | 20 | 4032 | 85 (27) | 97.9% | 36 (42.4%, 53.0%) | 58.2 | -3.37 | -1.58 | -0.99 (3.39) | 59/19 | 3.68 / 1.66 | fails 1p,2,3,4,5 |
| G2_R2_H3_W120 | 0 | 4305 | 253 (97) | 94.1% | 74 (29.2%, 35.1%) | 70.6 | 3.96 | -0.89 | 0.83 (3.30) | 112/20 | 13.74 / 0.96 | fails 1u,1p,3,5 |
| G2_R2_H3_W120 | 20 | 4305 | 225 (85) | 94.8% | 70 (31.1%, 37.4%) | 68.7 | 3.75 | -0.87 | 0.73 (3.31) | 105/20 | 14.32 / 1.17 | fails 1u,1p,3,5 |
| G2_R4_H3_W60 | 0 | 3357 | 81 (36) | 97.6% | 46 (56.8%, 67.0%) | 44.8 | -4.51 | -2.56 | -1.65 (3.39) | 56/20 | 1.19 / 0.64 | fails 1p,2,3,4,5 |
| G2_R4_H3_W60 | 20 | 3357 | 52 (24) | 98.5% | 30 (57.7%, 70.1%) | 44.9 | -3.79 | -3.62 | -1.08 (3.48) | 39/19 | 3.62 / 1.77 | fails 1p,2,3,4,5 |
| G2_R4_H3_W120 | 0 | 3672 | 142 (49) | 96.1% | 57 (40.1%, 48.4%) | 60.0 | -3.14 | -1.19 | -2.27 (3.34) | 81/20 | -0.28 / 0.90 | fails 1p,2,3,5 |
| G2_R4_H3_W120 | 20 | 3672 | 127 (48) | 96.5% | 55 (43.3%, 52.0%) | 56.9 | -3.09 | -1.24 | -2.32 (3.35) | 76/20 | -0.33 / 1.08 | fails 1p,2,3,5 |
| G4_R2_H3_W60 | 0 | 2322 | 47 (22) | 98.0% | 33 (70.2%, 81.3%) | 31.2 | -3.40 | -2.45 | -2.20 (3.49) | 37/18 | -0.14 / 1.13 | fails 1p,2,3,4,5 |
| G4_R2_H3_W60 | 20 | 2322 | 35 (13) | 98.5% | 24 (68.6%, 81.4%) | 33.7 | -1.92 | -3.26 | -25.00 (3.58) | 29/16 | -1.76 / 2.14 | fails 1p,2,3,4,5 |
| G4_R2_H3_W120 | 0 | 2495 | 85 (34) | 96.6% | 40 (47.1%, 57.6%) | 52.6 | 2.41 | -0.73 | 0.99 (3.40) | 55/19 | 7.46 / 1.99 | fails 1p,3,4,5 |
| G4_R2_H3_W120 | 20 | 2495 | 75 (30) | 97.0% | 37 (49.3%, 60.4%) | 50.3 | 2.34 | -0.60 | 0.81 (3.41) | 51/19 | 8.35 / 2.51 | fails 1p,3,4,5 |
| G4_R4_H3_W60 | 0 | 1887 | 36 (19) | 98.1% | 28 (77.8%, 88.3%) | 24.4 | -3.45 | -3.17 | -2.19 (3.58) | 29/17 | -0.09 / 1.42 | fails 1p,2,3,4,5 |
| G4_R4_H3_W60 | 20 | 1887 | 26 (12) | 98.6% | 20 (76.9%, 89.0%) | 26.7 | -1.93 | -4.62 | -25.68 (3.71) | 22/13 | -1.77 / 2.61 | fails 1p,2,3,4,5 |
| G4_R4_H3_W120 | 0 | 2085 | 55 (19) | 97.4% | 32 (58.2%, 70.3%) | 43.2 | -1.93 | -2.42 | -7.38 (3.45) | 43/19 | -1.38 / 1.32 | fails 1p,2,3,4,5 |
| G4_R4_H3_W120 | 20 | 2085 | 50 (19) | 97.6% | 31 (62.0%, 74.1%) | 39.2 | -1.90 | -2.24 | -22.39 (3.47) | 40/19 | -1.73 / 1.74 | fails 1p,2,3,4,5 |
| G6_R2_H3_W60 | 0 | 1084 | 22 (13) | 98.0% | 17 (77.3%, 89.9%) | 23.1 | -1.96 | -1.41 | -41.74 (3.77) | 20/14 | -1.86 / -0.34 | fails 1u,1p,2,3,4,5 |
| G6_R2_H3_W60 | 20 | 1084 | 13 (5) | 98.8% | 9 (69.2%, 87.3%) | 30.8 | -1.90 | -1.00 | -16.38 (4.18) | 13/10 | -1.64 / 0.12 | fails 1u,1p,2,3,4,5 |
| G6_R2_H3_W120 | 0 | 1179 | 31 (14) | 97.4% | 19 (61.3%, 76.3%) | 36.9 | 10.78 | 0.77 | 1.78 (3.69) | 23/16 | 23.85 / 4.40 | fails 1u,1p,3,4,5 |
| G6_R2_H3_W120 | 20 | 1179 | 27 (11) | 97.7% | 18 (66.7%, 81.4%) | 31.6 | 26.67 | 0.74 | 1.99 (3.69) | 23/16 | 55.57 / 4.71 | fails 1u,1p,3,4,5 |
| G6_R4_H3_W60 | 0 | 860 | 18 (11) | 97.9% | 14 (77.8%, 91.0%) | 22.5 | -2.00 | -1.28 | -1624.72 (3.90) | 17/12 | -2.00 / -0.45 | fails 1u,1p,2,3,4,5 |
| G6_R4_H3_W60 | 20 | 860 | 10 (4) | 98.8% | 7 (70.0%, 89.2%) | 30.1 | -2.00 | -1.10 | n/a (4.60) | 10/7 | -2.00 / 0.19 | fails 1u,1p,2,3,4,5 |
| G6_R4_H3_W120 | 0 | 963 | 21 (8) | 97.8% | 14 (66.7%, 82.8%) | 33.1 | -2.00 | -0.76 | n/a (3.81) | 19/12 | -2.00 / 0.11 | fails 1u,1p,2,3,4,5 |
| G6_R4_H3_W120 | 20 | 963 | 20 (9) | 97.9% | 14 (70.0%, 85.5%) | 29.9 | -2.00 | -0.95 | n/a (3.85) | 18/12 | -2.00 / -0.14 | fails 1u,1p,2,3,4,5 |

### Robustness: city-day clustering (cluster = event, finer than calendar date) at L=10

| cell | n priced | EV vw c | t vw (city-day) | bar (df=events-1) | t vw (calendar day, formal) |
|---|---|---|---|---|---|
| G2_R2_H3_W60 | 101 | -3.42 | -1.34 | 3.32 | -1.33 |
| G2_R2_H3_W120 | 239 | 3.68 | 0.71 | 3.26 | 0.71 |
| G2_R4_H3_W60 | 60 | -5.28 | -1.67 | 3.39 | -1.67 |
| G2_R4_H3_W120 | 133 | -2.94 | -2.31 | 3.30 | -2.30 |
| G4_R2_H3_W60 | 40 | -6.29 | -1.25 | 3.49 | -1.25 |
| G4_R2_H3_W120 | 78 | 2.15 | 0.68 | 3.35 | 0.69 |
| G4_R4_H3_W60 | 30 | -6.22 | -1.25 | 3.59 | -1.25 |
| G4_R4_H3_W120 | 50 | -1.92 | -25.22 | 3.43 | -25.15 |
| G6_R2_H3_W60 | 17 | -1.67 | -4.68 | 3.90 | -4.68 |
| G6_R2_H3_W120 | 29 | 12.70 | 1.16 | 3.58 | 2.32 |
| G6_R4_H3_W60 | 13 | -2.00 | n/a | 4.18 | n/a |
| G6_R4_H3_W120 | 20 | -2.00 | n/a | 3.77 | n/a |

### Why tradeable fires are what they are (primary cell, L=10): market calibration at the entry price

| NO cost bucket | n | NO wins | NO win rate | mean pnl c |
|---|---|---|---|---|
| <=50c | 38 | 0 | 0.0% | -2.29 |
| 51-80c | 1 | 1 | 100.0% | 47.00 |
| 81-90c | 1 | 1 | 100.0% | 10.00 |
| 91-95c | 7 | 7 | 100.0% | 4.86 |
| 96-98c | 31 | 30 | 96.8% | -1.97 |

Untradeable reasons, primary cell L=10: {"cost_above_98_or_no_net": 1865, "no_candles": 425, "no_candle_at_or_after_target": 127}.

## Anchor (d) -- never-arrival and overshoot reported separately

Part 1 (the spec's new shape) is the never-arrival signal.  Overshoot is what the deployed rule can already lock; the same G/R/H/W gating applied to it is shown ONLY as a separate reference (not part of any bar, not Bonferroni-counted, and only over events whose full ladder was priced).

| flavor | cell | L | fires (covered) | priced | untradeable | false locks (all covered) | EV vw c | EV unw c | t vw |
|---|---|---|---|---|---|---|---|---|---|
| never-arrival | G2_R2_H3_W120 | 10 | 4305 | 239 | 94.4% | 82 (1.90%) | 3.68 | -0.83 | 0.71 |
| never-arrival | G4_R2_H3_W120 | 10 | 2495 | 78 | 96.9% | 42 (1.68%) | 2.15 | -0.73 | 0.69 |
| never-arrival | G6_R2_H3_W120 | 10 | 1179 | 29 | 97.5% | 21 (1.78%) | 12.70 | 0.62 | 2.32 |
| overshoot (ref) | G2_R2_H3_W120 | 10 | 7 | 0 | 100.0% | 0 (0.00%) | n/a | n/a | n/a |
| overshoot (ref) | G4_R2_H3_W120 | 10 | 2 | 0 | 100.0% | 0 (0.00%) | n/a | n/a | n/a |
| overshoot (ref) | G6_R2_H3_W120 | 10 | 0 | 0 | n/a | 0 (n/a) | n/a | n/a | n/a |

Settlement class of every never-arrival fire (universe level), by official integer value: see the table above (`NO via never-arrival` = official value stayed short of the bracket; `NO via overshoot-after-signal` = the official value ended past the bracket after the signal, i.e. NO for the other reason).

## Part 2 -- whole-ladder pricing from one inference

Signal = primary-cell FINAL-NO on any bracket rung of the city-day (the companion FINAL-YES primary cell cannot fire on integer data, so the union equals this set), t* = earliest such obs, v* = round(E*), inferred winner = the rung whose YES set contains v*; every other rung is an inferred loser.  Winner: buy YES at yes_ask; losers: buy NO at **100 - yes_bid**; each gated independently at the first qualifying candle at/after t*+L.  Skips: {'ladder_not_fully_candle_covered': 2734}.

| L | signalling days | mean fires / signalling day | days with >=1 fire | mean net c / day | sd | day-clustered t (bar) | total fires | naive fire-level t (invalid) |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | n/a | | | | | | |
| 10 | 1 | n/a | | | | | | |
| 20 | 1 | n/a | | | | | | |

Correlation structure: all rungs of a city-day share one inference, so one wrong inference loses the day's basket; the t above treats the city-day as the unit.  The 'naive fire-level t' column treats every fire as independent and is shown only to quantify how badly that would overstate significance.

## Sanity anchors

**(a) Oracle subset / price join -- HOLDS.**  Price join: 40/40 of the stored Stage-1 oracle rungs re-derived from my own fresh candle pull reproduce the stored best winner cost, best net and capturable-minute count exactly.  Subset test: of 610 winning priced Part-1 fires (NO side, entry inside the oracle's final-60-min window) 0 are not oracle-capturable; of 0 winning priced Part-2 fires 0.  (704 winning fires entered before the final 60 min, outside the oracle's window.)  The rule fires on 2 of the stored oracle rungs.  Limitation: Only the top-40 'capturable_markets_detail' of out/edge_sizing_v2.json survives on disk; the full 140-market Stage-1 set is absent.  The subset test is therefore (i) a price-join reproduction on those 40 rungs from my own fresh pull, and (ii) the Stage-1 capturable test re-derived on the same candles for every priced fire whose side won and whose entry is inside the oracle's final 60 min.

**(b) No look-ahead -- HOLDS.**  See worked example; for every distinct signal index k0 of every event: re-run the detector on obs[:k0+1] and on the full day with all later obs replaced by +50F / -50F from the k0 temperature; all decisions at indices <= k0 must be identical (assert; the script aborts otherwise).

**(c) Monotonicity / timezone -- HOLDS.**  Running-extreme monotonicity violations over all event-days: **0**.  close_time == LST midnight ending the event date (or 60 s earlier) for every event; skips: {}.  Settlement semantics check (official integer value reproduces the official `result` under between: floor<=v<=cap, greater: v>floor, less: v<cap): {'between|no_value': 4, 'between|True': 24152, 'greater|no_value': 1, 'greater|True': 6038, 'less|no_value': 1, 'less|True': 6038}.

**(d) Overshoot separation** -- see the anchor (d) section: never-arrival and overshoot are separate rows, and the verdict uses never-arrival only.

{{CAVEATS}}
