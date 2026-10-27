# FINALITY-NO + WHOLE-LADDER -- BUILD A (primary) -- result

Spec: `venue_expansion/FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27).  Code: `venue_expansion/finality_no_A.py`.  Per-fire records: `venue_expansion/out/finality_no_A.json`.  Seed 20261028.  Reproduce: `python venue_expansion/finality_no_A.py setup && ... order && ... candles && ... signals && ... report`.

## Verdicts

- **Part 1 (FINAL-NO by never-arrival): INSUFFICIENT**  -- PASS cells at L=10: none; KILL triggers: none; best L=10 one-sided 97.9% EV upper bound over the 12 cells: 92.81c volume-weighted (formal) / 110.97c unweighted.
- **Part 2 (whole ladder): NOT_EVALUABLE**  -- gate (Part 1 PASS or TERMINAL_FINALITY PASS): NOT met; companion FINAL-YES builds on disk: {'finality_A': 'INSUFFICIENT', 'finality_B': 'INSUFFICIENT'}.

{{COMMENTARY}}

## Sampling / coverage (read this first)

- **Part 1 priced stage: 290 of 8,699 never-arrival-fired bracket rungs have candlesticks = 3.33% (PARTIAL: a random prefix of a shuffled event order, seed 20261028).**  Signal-level facts (fire counts, false-lock rates) always use all 6,039 scored events.
- **Part 2 ladder stage: 1 of 2,735 signalling city-days have the whole 6-rung ladder priced = 0.04%** (a random prefix of the shuffled event order (seed 20261028), never re-sorted).
- Work order = sorted event list shuffled once with a fixed seed (`cache/finality_no/A/event_work_order.json`), never re-sorted.  Tier 1 (Part 1) prices only the bracket rungs that have a never-arrival fire in some cell (an obs-only decision made before any price or outcome was read); tier 2 (Part 2) prices every rung of every event with a day-level primary-cell signal.  The overshoot reference arm (anchor d) therefore only exists where tier 2 reached.

## Universe, feeds, skips

- 40 US HIGH/LOW series (20 stations), settled rungs with official `result` and close_time UTC date in 2026-05-23..2026-10-20: **6,039 city-day events x 6 rungs (4 brackets `-B`, 2 thresholds `-T`)**.  Event-level skips: none; pre-filter skips (counted, not tested): {'outside_window': 61548, 'no_official_result': 6} (`outside_window` = settled rungs of these series outside the frozen close-date window; `no_official_result` = 6 rungs with no yes/no result).  Series outside the 40 mapped ones are not tested (no verified station / fixed LST offset).
- Obs feed per event: {'iem_1min': 5109, 'iem_routine_fallback': 930}.  Market lists and IEM obs were COPIED from the sibling FINAL-YES build's cache (same universe, same sources; copying avoided re-pulling ~40k market rows and 240 IEM station-month files) and spot-verified against the live API (batch-vs-single candle check below; every settled event has exactly 6 rungs).
- Candle pull: live-settled rungs use the batch endpoint `GET /markets/candlesticks?market_tickers=...` (one call per event); verified byte-identical to the per-market endpoint on 8/8 rungs (`cache/finality_no/A/batch_vs_single_check.json`).  Hist-settled rungs use `/historical/markets/{ticker}/candlesticks`.  All parsed by the shared `edge_sizing_v2.normalize()`.

## Worked timezone example (anchor c)

Fire `KXLOWTATL-26AUG31-B73.5` (station ATL, running MIN, fixed standard offset UTC-5; bracket [73,74], official result `yes`, official value 74.00).

- Local-STANDARD day starts **2026-08-31 05:00Z** (= 2026-08-31 00:00 LST, epoch 1788152400) and ends at LST midnight **2026-09-01 05:00Z** (= 2026-09-01 00:00 LST, epoch 1788238800); Kalshi's own `close_time` equals this (asserted for every event, tolerance 60 s).  In DST wall-clock the same instant is 2026-09-01 01:00 (DST wall clock): the 'local day' is NOT wall-clock midnight-to-midnight in summer (the classic 1-hour-skew trap).
- The running extreme E = 79.0 was last set at **2026-08-31 13:03Z** (= 2026-08-31 08:03 LST).  The signal observation (index k=837 of 957 obs that day) is **2026-09-01 03:00Z** = 2026-08-31 22:00 LST, 120 min before close; signal stamped obs + 60 s = **2026-09-01 03:01Z** (epoch 1788231660).  Candle epochs are UTC `end_period_ts`, same clock as the obs epochs and `close_time`, so all three compare directly.
- L=10 entry: first candle with end_period_ts >= sig_ts + 600 s = 2026-09-01 03:11Z; found **2026-09-01 03:12Z** (= 2026-08-31 22:12 LST), NO cost = 100 - yes_bid = 2c, fee 1c, volume 0.0; settles `yes` -> pnl -3c.

Proof the day window is right: the extreme of the 1-minute obs inside the window shifted by s hours, versus Kalshi's own `expiration_value` for this event:

| s (h) | -3 | -2 | -1 | +0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| extreme F | 79.0 | 79.0 | 79.0 | 79.0 | 79.0 | 79.0 | 77.0 |
| = official? | no | no | no | no | no | no | no |

Across ALL events, exact-match fraction of the shifted-window extreme against the official integer (1-min feed):

| kind | s=-3 | s=-2 | s=-1 | s=+0 | s=+1 | s=+2 | s=+3 |
|---|---|---|---|---|---|---|---|
| max exact-match % | 41.4% | 41.7% | 42.4% | 43.1% | 42.8% | 42.8% | 42.8% |
| max mean abs err F | 0.96 | 0.92 | 0.90 | 0.89 | 0.89 | 0.88 | 0.88 |
| min exact-match % | 69.5% | 70.5% | 72.3% | 76.9% | 70.4% | 65.0% | 58.8% |
| min mean abs err F | 0.73 | 0.69 | 0.60 | 0.53 | 0.61 | 0.75 | 0.92 |

The declared window (s=0) is the optimum for LOW markets and error grows with |s|; HIGH markets peak in the afternoon so the day boundary is nearly irrelevant for them (weakly informative).  The strict check is the `close_time == LST midnight` assertion.  Note the 1-minute IEM extreme equals Kalshi's official integer in well under 100% of days (official value is a different feed / rounding); that is exactly why `G >= 2` is in the spec.

## Worked no-look-ahead example (anchor b)

Same fire (`KXLOWTATL-26AUG31-B73.5`, primary cell G4_R2_H3_W120, never-arrival): at obs index k=837, E = 79.0F, current temp 85.0F; the detector is a `Stream` that consumes one obs at a time, so state after obs k is a function of obs[0..k] only.  max obs ts in the prefix = 2026-09-01 03:00Z < signal ts 2026-09-01 03:01Z: True.  Re-running the detector on obs[:k+1] only reproduces the fire: True; re-running on the full day with every later obs replaced by 35.0F (an adversarial +/-50F move) reproduces it: True.

Asserted in code for **every** distinct signal index of **every** event (29,553 detector re-runs: truncated prefix, +50F future, -50F future); the script aborts on any difference.  0 violations (the run completed).

## Part 1 -- FINAL-NO by never-arrival (bracket rungs)

**Primary cell G4_R2_H3_W120 at L=10:** universe fires 4,969 (false locks 88 = 1.77%, Wilson UB 2.18%, over 151 days / 20 stations); priced stage: n priced = **5** of 175 covered fires (untradeable 97.1%), priced false locks 5 (100.00%, Wilson UB 100.00%), EV/contract volume-weighted **-2.00c** (unweighted -21.40c), signed day-clustered t **n/a** (bar 8.07), 5 days, 5 stations; entries with volume > 0: 2 (zero-volume entries carry zero weight in the weighted estimator).

### All 12 cells, L = 10 (the deployable arm), formal day-clustered statistics (calendar event-date clusters)

| cell | L | fires (covered) | priced (vol>0) | untradeable | false locks priced (rate, Wilson UB) | mean NO cost c | EV vw c | EV unw c | t vw (bar) | days/stn | UB97.9 c (vw / unw) | bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G2_R2_H3_W60 | 10 | 273 | 5 (2) | 98.2% | 4 (80.0%, 96.4%) | 38.6 | -65.19 | -19.60 | -2.14 (8.07) | 5/5 | 24.85 / 34.55 | fails 1,2,3,4,5 |
| G2_R2_H3_W120 | 10 | 290 | 11 (3) | 96.2% | 6 (54.5%, 78.7%) | 53.6 | -2.00 | -9.18 | n/a (4.43) | 11/10 | -2.00 / 11.57 | fails 1,1,2,3,4,5 |
| G2_R4_H3_W60 | 10 | 230 | 4 (2) | 98.3% | 3 (75.0%, 95.4%) | 48.0 | -65.19 | -24.00 | -2.07 (11.88) | 4/4 | 42.48 / 54.58 | fails 1,2,3,4,5 |
| G2_R4_H3_W120 | 10 | 242 | 8 (2) | 96.7% | 5 (62.5%, 86.3%) | 49.4 | -2.00 | -12.88 | n/a (5.18) | 8/7 | -2.00 / 17.37 | fails 1,2,3,4,5 |
| G4_R2_H3_W60 | 10 | 165 | 4 (2) | 97.6% | 4 (100.0%, 100.0%) | 23.8 | -65.19 | -24.75 | -2.07 (11.88) | 4/4 | 42.48 / 52.94 | fails 1,2,3,4,5 |
| G4_R2_H3_W120 | 10 | 175 | 5 (2) | 97.1% | 5 (100.0%, 100.0%) | 20.4 | -2.00 | -21.40 | n/a (8.07) | 5/5 | -2.00 / 35.08 | fails 1,2,3,4,5 |
| G4_R4_H3_W60 | 10 | 135 | 3 (2) | 97.8% | 3 (100.0%, 100.0%) | 31.3 | -65.19 | -32.33 | -1.95 (27.90) | 3/3 | 92.81 / 110.97 | fails 1,2,3,4,5 |
| G4_R4_H3_W120 | 10 | 144 | 4 (1) | 97.2% | 4 (100.0%, 100.0%) | 25.2 | -2.00 | -26.25 | n/a (11.88) | 4/4 | -2.00 / 55.43 | fails 1,2,3,4,5 |
| G6_R2_H3_W60 | 10 | 80 | 1 (1) | 98.8% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R2_H3_W120 | 10 | 86 | 2 (2) | 97.7% | 2 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (496.56) | 2/2 | -2.00 / -2.00 | fails 1,1,2,3,4,5 |
| G6_R4_H3_W60 | 10 | 61 | 1 (1) | 98.4% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R4_H3_W120 | 10 | 67 | 1 (1) | 98.5% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |

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
| G2_R2_H3_W60 | 0 | 273 | 7 (3) | 97.4% | 5 (71.4%, 91.8%) | 39.4 | -3.93 | -12.00 | -1.39 (5.68) | 7/7 | 3.35 / 16.37 | fails 1,2,3,4,5 |
| G2_R2_H3_W60 | 20 | 273 | 4 (1) | 98.5% | 3 (75.0%, 95.4%) | 47.0 | -2.00 | -23.00 | n/a (11.88) | 4/4 | -2.00 / 52.17 | fails 1,2,3,4,5 |
| G2_R2_H3_W120 | 0 | 290 | 11 (5) | 96.2% | 6 (54.5%, 78.7%) | 53.6 | -2.41 | -9.18 | -3.98 (4.43) | 11/10 | -1.00 / 11.33 | fails 1,1,2,3,4,5 |
| G2_R2_H3_W120 | 20 | 290 | 9 (3) | 96.9% | 5 (55.6%, 81.1%) | 54.0 | -2.00 | -10.56 | -352.52 (4.84) | 9/8 | -1.99 / 14.42 | fails 1,1,2,3,4,5 |
| G2_R4_H3_W60 | 0 | 230 | 5 (3) | 97.8% | 4 (80.0%, 96.4%) | 35.4 | -3.93 | -16.60 | -1.34 (8.07) | 5/5 | 4.70 / 28.70 | fails 1,2,3,4,5 |
| G2_R4_H3_W60 | 20 | 230 | 3 (1) | 98.7% | 2 (66.7%, 93.9%) | 62.3 | -2.00 | -30.00 | n/a (27.90) | 3/3 | -2.00 / 109.43 | fails 1,2,3,4,5 |
| G2_R4_H3_W120 | 0 | 242 | 8 (3) | 96.7% | 5 (62.5%, 86.3%) | 49.2 | -2.50 | -12.75 | -3.39 (5.18) | 8/7 | -0.67 / 17.18 | fails 1,2,3,4,5 |
| G2_R4_H3_W120 | 20 | 242 | 8 (3) | 96.7% | 5 (62.5%, 86.3%) | 48.8 | -2.00 | -12.25 | -349.76 (5.18) | 8/7 | -1.99 / 16.44 | fails 1,2,3,4,5 |
| G4_R2_H3_W60 | 0 | 165 | 4 (2) | 97.6% | 4 (100.0%, 100.0%) | 19.8 | -34.93 | -21.00 | -1.15 (11.88) | 4/4 | 69.14 / 43.88 | fails 1,2,3,4,5 |
| G4_R2_H3_W60 | 20 | 165 | 3 (1) | 98.2% | 3 (100.0%, 100.0%) | 30.0 | -2.00 | -31.00 | n/a (27.90) | 3/3 | -2.00 / 106.01 | fails 1,2,3,4,5 |
| G4_R2_H3_W120 | 0 | 175 | 5 (3) | 97.1% | 5 (100.0%, 100.0%) | 20.2 | -5.69 | -21.20 | -1.13 (8.07) | 5/5 | 9.16 / 34.69 | fails 1,2,3,4,5 |
| G4_R2_H3_W120 | 20 | 175 | 4 (2) | 97.7% | 4 (100.0%, 100.0%) | 24.0 | -2.10 | -25.00 | -14.02 (11.88) | 4/4 | -1.59 / 52.41 | fails 1,2,3,4,5 |
| G4_R4_H3_W60 | 0 | 135 | 3 (2) | 97.8% | 3 (100.0%, 100.0%) | 26.0 | -34.93 | -27.33 | -1.08 (27.90) | 3/3 | 117.78 / 92.35 | fails 1,2,3,4,5 |
| G4_R4_H3_W60 | 20 | 135 | 2 (1) | 98.5% | 2 (100.0%, 100.0%) | 44.5 | -2.00 | -45.50 | n/a (496.56) | 2/2 | -2.00 / 612.90 | fails 1,2,3,4,5 |
| G4_R4_H3_W120 | 0 | 144 | 4 (2) | 97.2% | 4 (100.0%, 100.0%) | 25.0 | -14.74 | -26.00 | -0.82 (11.88) | 4/4 | 46.77 / 54.82 | fails 1,2,3,4,5 |
| G4_R4_H3_W120 | 20 | 144 | 4 (2) | 97.2% | 4 (100.0%, 100.0%) | 24.0 | -2.10 | -25.00 | -14.02 (11.88) | 4/4 | -1.59 / 52.41 | fails 1,2,3,4,5 |
| G6_R2_H3_W60 | 0 | 80 | 1 (1) | 98.8% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R2_H3_W60 | 20 | 80 | 0 (0) | 100.0% | 0 (n/a, n/a) | n/a | n/a | n/a | n/a (n/a) | 0/0 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R2_H3_W120 | 0 | 86 | 2 (2) | 97.7% | 2 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (496.56) | 2/2 | -2.00 / -2.00 | fails 1,1,2,3,4,5 |
| G6_R2_H3_W120 | 20 | 86 | 1 (1) | 98.8% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R4_H3_W60 | 0 | 61 | 1 (1) | 98.4% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R4_H3_W60 | 20 | 61 | 0 (0) | 100.0% | 0 (n/a, n/a) | n/a | n/a | n/a | n/a (n/a) | 0/0 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R4_H3_W120 | 0 | 67 | 1 (1) | 98.5% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |
| G6_R4_H3_W120 | 20 | 67 | 1 (1) | 98.5% | 1 (100.0%, 100.0%) | 1.0 | -2.00 | -2.00 | n/a (n/a) | 1/1 | n/a / n/a | fails 1,1,2,3,4,5 |

### Robustness: city-day clustering (cluster = event, finer than calendar date) at L=10

| cell | n priced | EV vw c | t vw (city-day) | bar (df=events-1) | t vw (calendar day, formal) |
|---|---|---|---|---|---|
| G2_R2_H3_W60 | 5 | -65.19 | -2.14 | 8.07 | -2.14 |
| G2_R2_H3_W120 | 11 | -2.00 | n/a | 4.43 | n/a |
| G2_R4_H3_W60 | 4 | -65.19 | -2.07 | 11.88 | -2.07 |
| G2_R4_H3_W120 | 8 | -2.00 | n/a | 5.18 | n/a |
| G4_R2_H3_W60 | 4 | -65.19 | -2.07 | 11.88 | -2.07 |
| G4_R2_H3_W120 | 5 | -2.00 | n/a | 8.07 | n/a |
| G4_R4_H3_W60 | 3 | -65.19 | -1.95 | 27.90 | -1.95 |
| G4_R4_H3_W120 | 4 | -2.00 | n/a | 11.88 | n/a |
| G6_R2_H3_W60 | 1 | -2.00 | n/a | n/a | n/a |
| G6_R2_H3_W120 | 2 | -2.00 | n/a | 496.56 | n/a |
| G6_R4_H3_W60 | 1 | -2.00 | n/a | n/a | n/a |
| G6_R4_H3_W120 | 1 | -2.00 | n/a | n/a | n/a |

### Why tradeable fires are what they are (primary cell, L=10): market calibration at the entry price

| NO cost bucket | n | NO wins | NO win rate | mean pnl c |
|---|---|---|---|---|
| <=50c | 4 | 0 | 0.0% | -2.25 |
| 96-98c | 1 | 0 | 0.0% | -98.00 |

Untradeable reasons, primary cell L=10: {"no_candles": 32, "cost_above_98_or_no_net": 135, "no_candle_at_or_after_target": 3}.

## Anchor (d) -- never-arrival and overshoot reported separately

Part 1 (the spec's new shape) is the never-arrival signal.  Overshoot is what the deployed rule can already lock; the same G/R/H/W gating applied to it is shown ONLY as a separate reference (not part of any bar, not Bonferroni-counted, and only over events whose full ladder was priced).

| flavor | cell | L | fires (covered) | priced | untradeable | false locks (all covered) | EV vw c | EV unw c | t vw |
|---|---|---|---|---|---|---|---|---|---|
| never-arrival | G2_R2_H3_W120 | 10 | 290 | 11 | 96.2% | 6 (2.07%) | -2.00 | -9.18 | n/a |
| never-arrival | G4_R2_H3_W120 | 10 | 175 | 5 | 97.1% | 5 (2.86%) | -2.00 | -21.40 | n/a |
| never-arrival | G6_R2_H3_W120 | 10 | 86 | 2 | 97.7% | 2 (2.33%) | -2.00 | -2.00 | n/a |
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

**(a) Oracle subset / price join -- HOLDS.**  Price join: 40/40 of the stored Stage-1 oracle rungs re-derived from my own fresh candle pull reproduce the stored best winner cost, best net and capturable-minute count exactly.  Subset test: of 14 winning priced Part-1 fires (NO side, entry inside the oracle's final-60-min window) 0 are not oracle-capturable; of 0 winning priced Part-2 fires 0.  (16 winning fires entered before the final 60 min, outside the oracle's window.)  The rule fires on 2 of the stored oracle rungs.  Limitation: Only the top-40 'capturable_markets_detail' of out/edge_sizing_v2.json survives on disk; the full 140-market Stage-1 set is absent.  The subset test is therefore (i) a price-join reproduction on those 40 rungs from my own fresh pull, and (ii) the Stage-1 capturable test re-derived on the same candles for every priced fire whose side won and whose entry is inside the oracle's final 60 min.

**(b) No look-ahead -- HOLDS.**  See worked example; for every distinct signal index k0 of every event: re-run the detector on obs[:k0+1] and on the full day with all later obs replaced by +50F / -50F from the k0 temperature; all decisions at indices <= k0 must be identical (assert; the script aborts otherwise).

**(c) Monotonicity / timezone -- HOLDS.**  Running-extreme monotonicity violations over all event-days: **0**.  close_time == LST midnight ending the event date (or 60 s earlier) for every event; skips: {}.  Settlement semantics check (official integer value reproduces the official `result` under between: floor<=v<=cap, greater: v>floor, less: v<cap): {'between|no_value': 4, 'between|True': 24152, 'greater|no_value': 1, 'greater|True': 6038, 'less|no_value': 1, 'less|True': 6038}.

**(d) Overshoot separation** -- see the anchor (d) section: never-arrival and overshoot are separate rows, and the verdict uses never-arrival only.

{{CAVEATS}}
