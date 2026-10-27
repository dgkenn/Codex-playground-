# TERMINAL FINALITY -- Build B (independent replication) -- RESULT

**Verdict (frozen spec, literal reading): `INSUFFICIENT`** -- see 'Why INSUFFICIENT and not PASS or KILL'. No PASS under any reading; the only reading under which the rule fires at all fails the false-lock bar by ~5x.

Reproduce: `python venue_expansion/finality_B.py discover|obs|signal|oracle|candles` then `python -c "import finality_B as F; F.cmd_report()"`. Cache: `cache/finality/B/` (own namespace). Numbers: `out/finality_B.json`.

## 0. Headline

Executed literally, the frozen spec produces **zero fires in all 8 cells x 3 latency arms**: brackets are 1 degF wide in (floor, cap) terms (a 2-whole-degree rung), so `lo+M <= E <= hi-M` is empty for M=1.0 and needs a half-degree extreme for M=0.5; observed extremes are whole degrees. No PASS is possible and I did not move any bar. Under the one charitable reading that lets the rule fire (exploratory 'lattice' variant, primary cell, 4,734 fires over the full universe) the finality inference is **wrong 1,125 times = 23.8% (Wilson UB 25.0%)** against a 2% / 5% bar. The cause is data-source disagreement, not timezone: IEM's day extreme differs from the official settlement value by 1 degF on about half of days, one-sidedly, and a rung is only 2 degF wide. Priced on a random 8% subsample of fired rungs (L=10): n priced 128, untradeable 65%, EV -0.34c/contract equal-weight (signed day-clustered t -0.27).

## 1. SAMPLING -- read this first

* **Signal walk: 100% of the universe** (25,956 bracket rungs, 6,489 event-days, 48 series, 24 stations, closes 2026-05-23 04:59Z .. 2026-10-20 08:00Z). The FINAL-YES signal needs observations only, so no sampling was needed for signals, false-lock rates or the geometry audit.
* **Candlestick (price) pulls: 365 of 4,742 fired rungs = 7.7%.** Fired rungs were put in a **seeded shuffled order** (seed 20261027), saved to `cache/finality/B/candle_work_order.json`, and **never re-sorted**; pricing statistics use the longest completed prefix of that order, so the priced set is itself a uniform random subsample of fires (an earlier study here produced a biased series-ordered prefix; this one cannot). Precision, not validity, is what the truncation costs.
* Pricing statistics apply only to the **exploratory** 'lattice' variant (the literal variant never fires, so nothing needs pricing).

## 2. Universe, skips, feed coverage

| item | count |
|---|---:|
| settled bracket rungs in universe (48 US series, closes 2026-05-23..2026-10-20, official yes/no) | 25,956 |
| skipped: close_outside_2026-05-23..2026-10-20 | 39,259 |
| skipped: no_official_yes_no_result | 27 |
| skipped: not_bracket_rung(T_threshold) | 35,582 |
| skipped: series_not_in_verified_US_station_map | 420 |
| obs coverage: no_obs_coverage(rungs) | 8 |
| obs coverage: obs_1min(rungs) | 16,116 |
| obs coverage: obs_routine(rungs) | 9,832 |

Sources: live `/markets?status=settled` (Kalshi serves only ~2026-08-21 onward there) **plus** `/historical/markets` (everything settled before the 2026-08-28 historical cutoff). Candles come from `/series/.../candlesticks` after the cutoff and `/historical/markets/{ticker}/candlesticks` before it (historical rows use `close` rather than `close_dollars`; aliased, values untouched, then parsed by the reused `edge_sizing_v2.normalize()`). International series (EGLL, LFPG, RJTT, ...) have no settled markets in the live listing and no verified IEM 1-minute station map; 'series_not_in_verified_US_station_map' counts only what the live listing returned. Four US series not in the old stage-2 city map (EWR, SAN, SDF, TTN) were added with standard offsets confirmed by close-hour.

## 3. The frozen geometry cannot fire (spec defect, found by audit)

Every one of the 25,956 bracket rungs has `cap_strike - floor_strike = 1` (e.g. `B64.5` = floor 64, cap 65; it settles YES on whole-degree values 64 or 65). The spec's condition `lo+M <= E <= hi-M` with `[lo,hi]=[floor,cap]` therefore needs `M <= 0.5`, and at `M=0.5` it needs `E = lo+0.5` exactly. Observed extremes are whole degrees (1-min: 4029/4029 integer; routine: 2421/2458 integer), so:

| literal rule, R=2, W=120 | rungs that ever fire |
|---|---:|
| 1min|M=0.0 | 3,079 |
| routine|M=0.0 | 1,655 |
| routine|M=0.25 | 5 |
| any source, M=0.5 | 0 |
| any source, M=1.0 (primary cell) | 0 |

**All 8 frozen cells x 3 latency arms have n = 0 fires under the literal reading.** M=0 would fire (4,734 rungs) but M=0 is not in the frozen grid and is exactly what the margin was meant to exclude. I did not alter the grid. As a clearly-labelled, PASS-ineligible **post-hoc** reading I also ran the 'lattice' variant: bracket widened by one whole degree each side (`[lo-1, hi+1]`), i.e. the margin M is measured from the nearest whole-degree value that would flip the outcome. Under it M=1.0 means `E in {lo, hi}` (and M=0.5 is the same set on integer data). Everything below labelled 'lattice' is exploratory.

## 4. Primary cell (M=1.0, R=2, H=3, W=120)

* **Literal (the frozen spec): n fires = 0, priced = 0, untradeable = n/a at L=0/10/20.** False-lock rate undefined (0/0). Nothing to test.
* **Lattice (exploratory) at L=10:** fires 4,734; **false locks 1,125 = 23.8% (Wilson 95% UB 25.0%)** vs bars of <=2% / <=5% -> the finality inference is wrong on 1 in 4 rungs. Priced 128 of 364 sampled fires (untradeable 64.8%); EV equal-weight -0.34c, volume-weighted -1.38c; signed day-clustered t = -0.27 (eq) / -3.31 (vw); days 86, stations 22.

## 5. All cells

### literal variant (frozen spec)

| M | R | W | L | fires (all) | fires (candle-sampled) | priced | untradeable | false-lock (Wilson UB) | EV eq c | EV vw c | t eq / vw | days | stations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 2 | 60 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 2 | 60 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 2 | 60 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 2 | 120 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 2 | 120 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 2 | 120 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 60 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 60 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 60 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 120 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 120 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 0.5 | 4 | 120 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 60 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 60 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 60 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 120 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 120 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 2 | 120 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 60 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 60 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 60 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 120 | 0 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 120 | 10 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |
| 1.0 | 4 | 120 | 20 | 0 | 0 | 0 | n/a | n/a (UB n/a) | n/a | n/a | n/a / n/a | 0 | 0 |

### lattice variant (EXPLORATORY, not eligible for PASS)

| M | R | W | L | fires (all) | fires (candle-sampled) | priced | untradeable | false-lock (Wilson UB) | EV eq c | EV vw c | t eq / vw | days | stations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 2 | 60 | 0 | 4620 | 355 | 91 | 74.4% | 23.8% (UB 25.1%) | 0.20 | -0.51 | 0.20 / -0.61 | 65 | 23 |
| 0.5 | 2 | 60 | 10 | 4620 | 355 | 58 | 83.7% | 23.8% (UB 25.1%) | 1.50 | -1.38 | 0.80 / -3.35 | 44 | 19 |
| 0.5 | 2 | 60 | 20 | 4620 | 355 | 55 | 84.5% | 23.8% (UB 25.1%) | 1.89 | -0.96 | 0.94 / -1.36 | 43 | 18 |
| 0.5 | 2 | 120 | 0 | 4742 | 365 | 141 | 61.4% | 23.9% (UB 25.1%) | 0.02 | -1.50 | 0.02 / -4.66 | 91 | 23 |
| 0.5 | 2 | 120 | 10 | 4742 | 365 | 129 | 64.7% | 23.9% (UB 25.1%) | -0.33 | -1.38 | -0.26 / -3.31 | 87 | 22 |
| 0.5 | 2 | 120 | 20 | 4742 | 365 | 125 | 65.8% | 23.9% (UB 25.1%) | -0.44 | -1.96 | -0.34 / -2.39 | 85 | 22 |
| 0.5 | 4 | 60 | 0 | 4068 | 307 | 64 | 79.2% | 25.1% (UB 26.4%) | -1.16 | -1.81 | -3.93 / -10.70 | 52 | 20 |
| 0.5 | 4 | 60 | 10 | 4068 | 307 | 39 | 87.3% | 25.1% (UB 26.4%) | -1.05 | -1.69 | -2.78 / -7.36 | 35 | 18 |
| 0.5 | 4 | 60 | 20 | 4068 | 307 | 36 | 88.3% | 25.1% (UB 26.4%) | -1.00 | -1.58 | -2.57 / -3.68 | 33 | 17 |
| 0.5 | 4 | 120 | 0 | 4275 | 330 | 115 | 65.2% | 24.6% (UB 25.9%) | -0.23 | -1.77 | -0.36 / -7.80 | 79 | 22 |
| 0.5 | 4 | 120 | 10 | 4275 | 330 | 103 | 68.8% | 24.6% (UB 25.9%) | -0.53 | -1.95 | -0.92 / -42.56 | 72 | 22 |
| 0.5 | 4 | 120 | 20 | 4275 | 330 | 99 | 70.0% | 24.6% (UB 25.9%) | -0.58 | -2.63 | -1.04 / -4.37 | 70 | 22 |
| 1.0 | 2 | 60 | 0 | 4612 | 354 | 90 | 74.6% | 23.7% (UB 25.0%) | 0.19 | -0.51 | 0.19 / -0.61 | 64 | 23 |
| 1.0 | 2 | 60 | 10 | 4612 | 354 | 58 | 83.6% | 23.7% (UB 25.0%) | 1.50 | -1.38 | 0.80 / -3.35 | 44 | 19 |
| 1.0 | 2 | 60 | 20 | 4612 | 354 | 55 | 84.5% | 23.7% (UB 25.0%) | 1.89 | -0.96 | 0.94 / -1.36 | 43 | 18 |
| 1.0 | 2 | 120 | 0 | 4734 | 364 | 140 | 61.5% | 23.8% (UB 25.0%) | 0.01 | -1.50 | 0.01 / -4.66 | 90 | 23 |
| 1.0 | 2 | 120 | 10 | 4734 | 364 | 128 | 64.8% | 23.8% (UB 25.0%) | -0.34 | -1.38 | -0.27 / -3.31 | 86 | 22 |
| 1.0 | 2 | 120 | 20 | 4734 | 364 | 124 | 65.9% | 23.8% (UB 25.0%) | -0.45 | -1.96 | -0.35 / -2.39 | 84 | 22 |
| 1.0 | 4 | 60 | 0 | 4064 | 306 | 63 | 79.4% | 25.0% (UB 26.4%) | -1.19 | -1.81 | -4.01 / -10.70 | 51 | 20 |
| 1.0 | 4 | 60 | 10 | 4064 | 306 | 39 | 87.3% | 25.0% (UB 26.4%) | -1.05 | -1.69 | -2.78 / -7.36 | 35 | 18 |
| 1.0 | 4 | 60 | 20 | 4064 | 306 | 36 | 88.2% | 25.0% (UB 26.4%) | -1.00 | -1.58 | -2.57 / -3.68 | 33 | 17 |
| 1.0 | 4 | 120 | 0 | 4269 | 329 | 114 | 65.3% | 24.5% (UB 25.8%) | -0.24 | -1.77 | -0.37 / -7.80 | 78 | 22 |
| 1.0 | 4 | 120 | 10 | 4269 | 329 | 102 | 69.0% | 24.5% (UB 25.8%) | -0.55 | -1.95 | -0.94 / -42.56 | 71 | 22 |
| 1.0 | 4 | 120 | 20 | 4269 | 329 | 98 | 70.2% | 24.5% (UB 25.8%) | -0.59 | -2.63 | -1.06 / -4.37 | 69 | 22 |

## 6. Bars at L=10 (literal variant = frozen spec)

* PASS cells: none
* KILL clause 1 (false-lock > 5% in primary cell): False (primary cell has 0 fires: not evaluable)
* KILL clause 2 (every cell with EV>0 fails n>=100): False (no literal cell has an EV at all, so it is vacuous, not met on evidence)
* KILL clause 3 (best one-sided 97.9% UB on EV < +0.5c): False (best UB = None; undefined with n=0)

### Why INSUFFICIENT and not PASS or KILL

Zero literal fires: PASS is impossible, and each KILL clause is either unevaluable (no fires, no EV, no UB) or vacuously true on an empty set -- a KILL on vacuity would be a verdict by technicality, not evidence. The spec says 'anything else -> INSUFFICIENT', and that is the only honest label for a rule whose frozen parameters select the empty set. **But do not read INSUFFICIENT as 'maybe'.** The single reading under which the rule fires fails clause 1 of KILL by a wide margin (lattice primary-cell false-lock rate above), and its EV (section 5, lattice) is what the bars would call a KILL as well.

## 7. Descriptive follow-up (obs + official result only; no price; NOT a test)

Lattice primary-cell fires split by where the extreme sits in the bracket and by feed. This is post-hoc description of why the false-lock rate is ~24%, not a candidate strategy; any rule built from it would need a fresh pre-registration and forward data.

| kind | E position | feed | n | false locks | rate | Wilson UB |
|---|---|---|---:|---:|---:|---:|
| max | E fractional | routine | 2 | 0 | 0.0% | 65.8% |
| max | E==hi | 1min | 863 | 30 | 3.5% | 4.9% |
| max | E==hi | routine | 509 | 337 | 66.2% | 70.2% |
| max | E==lo | 1min | 865 | 428 | 49.5% | 52.8% |
| max | E==lo | routine | 523 | 52 | 9.9% | 12.8% |
| min | E fractional | routine | 7 | 2 | 28.6% | 64.1% |
| min | E==hi | 1min | 714 | 127 | 17.8% | 20.8% |
| min | E==hi | routine | 349 | 19 | 5.4% | 8.3% |
| min | E==lo | 1min | 637 | 38 | 6.0% | 8.1% |
| min | E==lo | routine | 265 | 92 | 34.7% | 40.6% |

Mechanism: the IEM/ASOS day extreme and the official settlement value disagree by 1 degF on roughly half of days (see section 9 table) and the bias is one-sided (HIGH: IEM 1-min max is >= official; routine hourly max is <= official because hourly sampling misses the peak). Rungs are only 2 whole degrees wide, so a 1-degree feed disagreement flips the winner. A symmetric margin cannot fix a one-sided bias.

## 8. Anchors

**(a) Oracle reconciliation.**

* The 140 EDGE_SIZING-capturable rows (`out/edge_sizing_stage2.json: per_market`) were re-priced from my own candle pull with an independent recomputation of the Stage-1 rule: 140 had candles; minute-count matches 140, first-capturable-ts matches 140, last-capturable-ts matches 140. Mismatch examples (if any): [].
* Subset check: every priced YES-settled lattice fire (L=0) whose entry lies in the final 60 min -- 122 checked -- must be oracle-capturable on that rung; violations: **0**. Fires entered 60-120 min before close (166) are outside the oracle's 60-min window by construction; priced false locks (530) are not winner-side events.
* **Limit, disclosed:** the oracle's own sample membership (`stage1_v2.jsonl`, `population.json`) is not on disk in this checkout, so the check cannot enumerate which rungs the oracle *sampled and found non-capturable*; the reproduction of the 140 rows is the strongest available test of the price join.

**(b) No look-ahead.** The signal decision time is `t_sig = ts(obs_i) + 60 s`, so every input has timestamp < t_sig. In code (`anchor_b`), 300 fires (all primary-cell fires + a seeded random sample) were re-evaluated by an independent brute-force function that sees ONLY obs with ts < t, confirmed *first* (no earlier decision time qualifies), and survived a perturbation test (every obs with ts >= t replaced by +/-extreme garbage -> same fire). Passed 300/300; failures: []. Worked example: {'ticker': 'KXLOWTAUS-26JUN16-B70.5', 'variant': 'lattice', 'cell': [0.5, 2.0, 3, 120], 't_sig_utc': '2026-06-17 04:00Z', 'last_obs_used_utc': '2026-06-17 03:59Z', 'n_obs_with_ts_lt_t': 1237, 'n_obs_ge_t_ignored': 121}

**(c) Monotonicity.** Running max non-decreasing / running min non-increasing within every local day: **0 violations** over all walked days.

## 9. Timezone handling, proven

The market day is the NWS local **standard-time** day. Kalshi's `close_time` is exactly local-standard-midnight + 24 h year-round (e.g. `06:00Z` for CST cities all year, `08:00Z` for Seattle in July even though the wall clock there is PDT), verified for every series by close-hour (`cmd_tzcheck`; the universe builder *drops* any rung whose close-hour disagrees with the station's standard offset). Historical rows close at `HH:59Z`, so the day end is `round(close_time to nearest hour)`; day start = day end - 24 h; the extreme is accumulated only over that window; obs are UTC epochs; candle `end_period_ts` are UTC epochs; the terminal window is `[close_time - W min, close_time]` in the same UTC epochs.

Worked example (real priced fire):

```
ticker: KXHIGHTSEA-26AUG07-B87.5
station: SEA
kind: max
bracket: [87.0, 88.0]
official_result: no
expiration_value: 86.00
close_time_utc: 2026-08-08 08:00Z
local_day_end_utc: 2026-08-08 08:00Z
local_day_start_utc: 2026-08-07 08:00Z
std_offset_h: -8
local_day_in_standard_time: 2026-08-07 00:00 .. 2026-08-08 00:00 (LST, UTC-8)
same_day_on_the_wall_clock_in_DST: 2026-08-07 01:00 .. 2026-08-08 01:00 (LDT, UTC-7)
n_obs_in_window: 1209
obs_source: 1min
running_extreme_F: 87.0
extreme_obs_utc: 2026-08-07 23:44Z
extreme_obs_LST: 2026-08-07 15:44
t_sig_utc: 2026-08-08 06:00Z
t_sig_LST: 2026-08-07 22:00
t_sig_epoch: 1786168800
minutes_before_close: 120.0
entry_candle_end_ts_epoch@L10: 1786174620
entry_candle_utc@L10: 2026-08-08 07:37Z
entry_yes_ask_c: 1
pnl_c: -2
pnl_note: (100 - ask - fee) if settled YES else (-ask - fee)
```

Independent check that the window is right (no outcomes used): obs-derived day extreme vs the market's numeric `expiration_value` (available for markets settled after the historical cutoff), under window shifts of -3..+3 h. Share within 0.5 degF:

| window shift (h) | match share | n |
|---:|---:|---:|
| -3 | 0.529 | 5774 |
| -2 | 0.536 | 5778 |
| -1 | 0.548 | 5790 |
| 0 | 0.582 | 6486 |
| 1 | 0.539 | 5806 |
| 2 | 0.513 | 5808 |
| 3 | 0.484 | 5820 |

(The shift = 0 window is best for the 1-min feed; the residual mismatch is the 1 degF one-sided feed bias, not a timezone error. Shifted rows use the 1-min feed only, shift 0 uses the per-market selected feed, so the comparison is slightly conservative for 0.)

Local-standard hour of the day's extreme (shift 0): {"max": {"0": 53, "1": 3, "2": 4, "3": 1, "4": 1, "5": 2, "6": 3, "7": 7, "8": 13, "9": 73, "10": 148, "11": 285, "12": 439, "13": 707, "14": 826, "15": 504, "16": 141, "17": 26, "18": 2, "21": 2, "22": 3, "23": 1}, "min": {"0": 276, "1": 213, "2": 292, "3": 533, "4": 628, "5": 557, "6": 135, "7": 18, "8": 9, "9": 15, "10": 13, "11": 13, "12": 14, "13": 13, "14": 14, "15": 16, "16": 8, "17": 15, "18": 16, "19": 21, "20": 37, "21": 54, "22": 94, "23": 238}}

## 10. Interpretation choices (where Build A may differ -- this is where a disagreement would come from)

* **Bracket geometry literal**: `[lo,hi] = [floor_strike, cap_strike]` exactly as carried on the rung. Widening it is the exploratory 'lattice' variant only (PASS-ineligible).
* **Signal timestamp** `t_sig = ts(obs_i) + 60 s` (strict `< t` look-ahead rule, anchor b). A build that uses `t_sig = ts(obs_i)` shifts every signal by 1 minute; immaterial at L>=10.
* **Reversed-and-held**: the last H=3 observations *including the current one* all satisfy `temp <= E(t)-R` (HIGH) / `>= E(t)+R` (LOW), with E(t) the running extreme at t. On 1-min feed H=3 means 3 minutes; on routine feed it means 3 METAR obs (~2-3 h).
* **Local day** = [round(close_time to hour) - 24 h, that hour], i.e. NWS standard-time midnight-to-midnight (see section 9). E accumulates from day start.
* **Terminal window** `close - W*60 <= t_sig <= close`; first qualifying t only; one fire per rung per cell.
* **Feed selection per market** (recorded in `signal.json: src`): 1-min if >=1000 of 1440 minutes AND >=65 obs in the last 130 min; else routine (`asos.py` report_type 3&4) if >=6 obs in the day and >=2 in the last 130 min; else the rung is skipped (8 rungs). Only a physical bound filter (-60..130 degF) is applied; no deployed-rule glitch filter.
* **Entry cost is `yes_ask`** for every fire (FINAL-YES always buys YES). For YES-settled rungs this equals the spec's winner-side cost. For false locks the spec's 'winner-side = 100 - yes_bid' is the NO price, which a YES buyer cannot pay; I charge the real YES ask and the loss `-(ask+fee)`. Using the winner-side cost for false locks would have *hidden* losses; the gate here is outcome-independent (deployable).
* **Entry** = first candle with `t_sig+L <= end_period_ts <= close_time`, `0 < yes_ask <= 98`, and `100-ask-fee > 0`; none -> UNTRADEABLE (candle-less rungs are counted untradeable, conservative). Candles are sparse (trade/quote-change minutes only), so 'first candle at or after' can be several minutes later.
* **EV**: per-contract net cents; equal-weight (one contract per fire, as the spec's accounting) and volume-weighted by the entry candle's traded volume. The Bonferroni t uses the day-clustered (CR1, linearised ratio) SE, df = G-1 (G = distinct local days); a PASS would have to clear the bar on BOTH weightings (the stricter reading of an ambiguous spec). One-sided 97.9% UB = mean + t_{0.979,G-1} * SE.
* **False-lock rate** is over ALL fires (a property of obs + official result), not just priced ones; the priced-only rate is also in the JSON.
* **Clusters** = local calendar day of the market.

## 11. What this does and does not say

A PASS would have been necessary-but-not-sufficient; there is no PASS, so nothing here supports a canary. The program's 44th closed study (if Build A agrees) is not a failure of finality as an idea -- the descriptive table shows that where the extreme sits relative to the feed's one-sided bias changes the false-lock rate from ~50% to ~3-6% -- but that is an *outcome-informed* observation made on the same data, so it is a hypothesis for a new pre-registration with its own forward holdout, not a result. And even a ~3% false-lock rate is fatal at these prices: a winner buys at <=98c for +1c to +2c net, a loser costs ~98c, so break-even needs a false-lock rate near 1-2%; see the lattice EV rows for what the tape actually paid.
