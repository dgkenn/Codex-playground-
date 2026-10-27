# TERMINAL FINALITY -- Build B (independent replication) -- RESULT

**Verdict (frozen spec, literal reading): `INSUFFICIENT`** -- see 'Why INSUFFICIENT and not PASS or KILL'. No PASS under any reading; the only reading under which the rule fires at all fails the false-lock bar by ~5x.

Reproduce: `python venue_expansion/finality_B.py discover|obs|signal|oracle|candles` then `python -c "import finality_B as F; F.cmd_report()"`. Cache: `cache/finality/B/` (own namespace). Numbers: `out/finality_B.json`.

## 0. Headline

Executed literally, the frozen spec produces **zero fires in all 8 cells x 3 latency arms**: brackets are 1 degF wide in (floor, cap) terms (a 2-whole-degree rung), so `lo+M <= E <= hi-M` is empty for M=1.0 and needs a half-degree extreme for M=0.5; observed extremes are whole degrees. No PASS is possible and I did not move any bar. Under the one charitable reading that lets the rule fire (exploratory 'lattice' variant, primary cell, 4,734 fires over the full universe) the finality inference is **wrong 1,125 times = 23.8% (Wilson UB 25.0%)** against a 2% / 5% bar. The cause is data-source disagreement, not timezone: IEM's day extreme differs from the official settlement value by 1 degF on about half of HIGH days (15-40% of LOW days), one-sidedly, and a rung is only 2 degF wide. Priced on a random 32% subsample of fired rungs (L=10): n priced 513, untradeable 67%, EV -0.67c/contract equal-weight (signed day-clustered t -1.24).

## 1. SAMPLING -- read this first

* **Signal walk: 100% of the universe** (25,956 bracket rungs, 6,489 event-days, 48 series, 24 stations, closes 2026-05-23 04:59Z .. 2026-10-20 08:00Z). The FINAL-YES signal needs observations only, so no sampling was needed for signals, false-lock rates or the geometry audit.
* **Candlestick (price) pulls: 1,537 of 4,742 fired rungs = 32.4%.** Fired rungs were put in a **seeded shuffled order** (seed 20261027), saved to `cache/finality/B/candle_work_order.json`, and **never re-sorted**; pricing statistics use the longest completed prefix of that order, so the priced set is itself a uniform random subsample of fires (an earlier study here produced a biased series-ordered prefix; this one cannot). Precision, not validity, is what the truncation costs.
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

Sources: live `/markets?status=settled` (Kalshi serves only ~2026-08-21 onward there) **plus** `/historical/markets` (everything settled before the 2026-08-28 historical cutoff). Candles come from `/series/.../candlesticks` after the cutoff and `/historical/markets/{ticker}/candlesticks` before it (historical rows use `close` rather than `close_dollars`; aliased, values untouched, then parsed by the reused `edge_sizing_v2.normalize()`). International series (EGLL, LFPG, RJTT, ...) have no settled markets in the live listing and no verified IEM 1-minute station map; 'series_not_in_verified_US_station_map' counts only what the live listing returned (KXHIGHHOU:420). Four US series not in the old stage-2 city map (EWR, SAN, SDF, TTN) were added with standard offsets confirmed by close-hour.

## 3. The frozen geometry cannot fire (spec defect, found by audit)

Every one of the 25,956 bracket rungs has `cap_strike - floor_strike = 1` (e.g. `B64.5` = floor 64, cap 65; it settles YES on whole-degree values 64 or 65). The spec's condition `lo+M <= E <= hi-M` with `[lo,hi]=[floor,cap]` therefore needs `M <= 0.5`, and at `M=0.5` it needs `E = lo+0.5` exactly. Observed day extremes are whole degrees (1min|integer: 4029, routine|fractional: 37, routine|integer: 2421 event-days), so:

| literal rule, R=2, W=120 | rungs that ever fire |
|---|---:|
| 1min|M=0.0 | 3,079 |
| routine|M=0.0 | 1,655 |
| routine|M=0.25 | 5 |
| any source, M=0.5 | 0 |
| any source, M=1.0 (primary cell) | 0 |

**All 8 frozen cells x 3 latency arms have n = 0 fires under the literal reading.** M=0 would fire (4,734 rungs at R=2, W=120) but M=0 is not in the frozen grid and is exactly what the margin was meant to exclude. I did not alter the grid. As a clearly-labelled, PASS-ineligible **post-hoc** reading I also ran the 'lattice' variant: bracket widened by one whole degree each side (`[lo-1, hi+1]`), i.e. the margin M is measured from the nearest whole-degree value that would flip the outcome. Under it M=1.0 means `E in {lo, hi}` (and M=0.5 is the same set on integer data). Everything below labelled 'lattice' is exploratory.

## 4. Primary cell (M=1.0, R=2, H=3, W=120)

* **Literal (the frozen spec): n fires = 0, priced = 0, untradeable = n/a at L=0/10/20.** False-lock rate undefined (0/0). Nothing to test.
* **Lattice (exploratory) at L=10:** fires 4,734; **false locks 1,125 = 23.8% (Wilson 95% UB 25.0%)** vs bars of <=2% / <=5% -> the finality inference is wrong on 1 in 4 rungs. Priced 513 of 1,535 sampled fires (untradeable 66.6%); EV equal-weight -0.67c, volume-weighted -1.16c; signed day-clustered t = -1.24 (eq) / -2.21 (vw); days 147, stations 24.

Adverse selection among the priced fires (lattice, primary cell, L=10; descriptive):

| priced fires that settled | n | mean entry ask (c) | mean net P&L (c) | share entered at ask>=90c | share entered at ask<=10c |
|---|---:|---:|---:|---:|---:|
| settled_YES_wins | 215 | 93.3 | 5.6 | 86.0% | 0.0% |
| settled_NO_false_locks | 298 | 4.2 | -5.2 | 1.3% | 93.6% |

False-lock rate among ALL fires 23.8% but among PRICED fires 58.1%: the minutes at which YES is still offered at <=98c are disproportionately the minutes at which the market already knows the feed extreme is not the official one (cheap YES asks on rungs that then lose). Entries at ask>=90c (market agrees with the signal): n=189, false locks 4, mean net 0.30c.

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
| 0.5 | 2 | 60 | 0 | 4620 | 1499 | 339 | 77.4% | 23.8% (UB 25.1%) | -0.50 | -0.99 | -0.92 / -2.77 | 128 | 24 |
| 0.5 | 2 | 60 | 10 | 4620 | 1499 | 219 | 85.4% | 23.8% (UB 25.1%) | -0.48 | -0.25 | -0.59 / -0.25 | 108 | 24 |
| 0.5 | 2 | 60 | 20 | 4620 | 1499 | 190 | 87.3% | 23.8% (UB 25.1%) | -0.70 | -1.05 | -0.75 / -2.70 | 105 | 23 |
| 0.5 | 2 | 120 | 0 | 4742 | 1537 | 551 | 64.2% | 23.9% (UB 25.1%) | -0.40 | -1.22 | -0.74 / -3.74 | 147 | 24 |
| 0.5 | 2 | 120 | 10 | 4742 | 1537 | 514 | 66.6% | 23.9% (UB 25.1%) | -0.67 | -1.16 | -1.23 / -2.21 | 147 | 24 |
| 0.5 | 2 | 120 | 20 | 4742 | 1537 | 479 | 68.8% | 23.9% (UB 25.1%) | -1.16 | -1.76 | -2.03 / -6.39 | 144 | 24 |
| 0.5 | 4 | 60 | 0 | 4068 | 1309 | 251 | 80.8% | 25.1% (UB 26.4%) | -1.31 | -1.69 | -2.97 / -11.04 | 115 | 24 |
| 0.5 | 4 | 60 | 10 | 4068 | 1309 | 153 | 88.3% | 25.1% (UB 26.4%) | -1.33 | -1.77 | -1.92 / -13.51 | 93 | 23 |
| 0.5 | 4 | 60 | 20 | 4068 | 1309 | 129 | 90.1% | 25.1% (UB 26.4%) | -1.53 | -1.59 | -1.90 / -6.14 | 86 | 22 |
| 0.5 | 4 | 120 | 0 | 4275 | 1388 | 451 | 67.5% | 24.6% (UB 25.9%) | -0.77 | -1.90 | -1.96 / -15.94 | 141 | 24 |
| 0.5 | 4 | 120 | 10 | 4275 | 1388 | 415 | 70.1% | 24.6% (UB 25.9%) | -0.78 | -1.97 | -1.84 / -11.02 | 140 | 24 |
| 0.5 | 4 | 120 | 20 | 4275 | 1388 | 391 | 71.8% | 24.6% (UB 25.9%) | -0.97 | -2.07 | -2.23 / -10.16 | 137 | 24 |
| 1.0 | 2 | 60 | 0 | 4612 | 1497 | 338 | 77.4% | 23.7% (UB 25.0%) | -0.50 | -0.99 | -0.92 / -2.77 | 128 | 24 |
| 1.0 | 2 | 60 | 10 | 4612 | 1497 | 219 | 85.4% | 23.7% (UB 25.0%) | -0.48 | -0.25 | -0.59 / -0.25 | 108 | 24 |
| 1.0 | 2 | 60 | 20 | 4612 | 1497 | 190 | 87.3% | 23.7% (UB 25.0%) | -0.70 | -1.05 | -0.75 / -2.70 | 105 | 23 |
| 1.0 | 2 | 120 | 0 | 4734 | 1535 | 550 | 64.2% | 23.8% (UB 25.0%) | -0.40 | -1.22 | -0.75 / -3.74 | 147 | 24 |
| 1.0 | 2 | 120 | 10 | 4734 | 1535 | 513 | 66.6% | 23.8% (UB 25.0%) | -0.67 | -1.16 | -1.24 / -2.21 | 147 | 24 |
| 1.0 | 2 | 120 | 20 | 4734 | 1535 | 478 | 68.9% | 23.8% (UB 25.0%) | -1.17 | -1.76 | -2.03 / -6.39 | 144 | 24 |
| 1.0 | 4 | 60 | 0 | 4064 | 1308 | 250 | 80.9% | 25.0% (UB 26.4%) | -1.32 | -1.69 | -2.98 / -11.04 | 115 | 24 |
| 1.0 | 4 | 60 | 10 | 4064 | 1308 | 153 | 88.3% | 25.0% (UB 26.4%) | -1.33 | -1.77 | -1.92 / -13.51 | 93 | 23 |
| 1.0 | 4 | 60 | 20 | 4064 | 1308 | 129 | 90.1% | 25.0% (UB 26.4%) | -1.53 | -1.59 | -1.90 / -6.14 | 86 | 22 |
| 1.0 | 4 | 120 | 0 | 4269 | 1386 | 450 | 67.5% | 24.5% (UB 25.8%) | -0.77 | -1.90 | -1.96 / -15.94 | 141 | 24 |
| 1.0 | 4 | 120 | 10 | 4269 | 1386 | 414 | 70.1% | 24.5% (UB 25.8%) | -0.78 | -1.97 | -1.85 / -11.02 | 140 | 24 |
| 1.0 | 4 | 120 | 20 | 4269 | 1386 | 390 | 71.9% | 24.5% (UB 25.8%) | -0.98 | -2.07 | -2.24 / -10.16 | 137 | 24 |

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

Feed extreme minus official `expiration_value` (whole degF, numeric-value markets only, i.e. settled after the 2026-08-28 cutoff; no outcomes of rungs used):

| kind|feed | -3 | -2 | -1 | 0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| max|1min (n=2015) | 0% | 1% | 2% | 46% | 50% | 1% | 0% |
| max|routine (n=1229) | 2% | 9% | 55% | 34% | 0% | 0% | 0% |
| min|1min (n=2013) | 1% | 0% | 13% | 83% | 2% | 1% | 0% |
| min|routine (n=1229) | 0% | 0% | 1% | 62% | 32% | 3% | 1% |

Mechanism: the IEM/ASOS day extreme and the official settlement value disagree by 1 degF on about half of HIGH days and 15-40% of LOW days (table above) and the bias is one-sided (HIGH: IEM 1-min max is >= official; routine hourly max is <= official because hourly sampling misses the peak). Rungs are only 2 whole degrees wide, so a 1-degree feed disagreement flips the winner. A symmetric margin cannot fix a one-sided bias.

## 8. Anchors

**(a) Oracle reconciliation.**

* The 140 EDGE_SIZING-capturable rows (`out/edge_sizing_stage2.json: per_market`) were re-priced from my own candle pull with an independent recomputation of the Stage-1 rule: 140 had candles; minute-count matches 140, first-capturable-ts matches 140, last-capturable-ts matches 140. Mismatch examples (if any): [].
* Subset check: every priced YES-settled lattice fire (L=0) whose entry lies in the final 60 min -- 504 checked -- must be oracle-capturable on that rung; violations: **0**. Fires entered 60-120 min before close (666) are outside the oracle's 60-min window by construction; priced false locks (2010) are not winner-side events.
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

| window shift (h) | HIGH match share (n) | LOW match share (n) |
|---:|---:|---:|
| -3 | 0.445 (1939) | 0.734 (1937) |
| -2 | 0.449 (1939) | 0.748 (1937) |
| -1 | 0.456 (1939) | 0.773 (1937) |
| 0 | 0.467 (1939) | 0.832 (1937) |
| 1 | 0.461 (1939) | 0.747 (1937) |
| 2 | 0.461 (1939) | 0.685 (1937) |
| 3 | 0.459 (1939) | 0.613 (1937) |

(Same events for every shift, 1-min feed only. The unshifted window is the maximum for both kinds. HIGH is nearly flat (the afternoon plateau is broad and the 1 degF feed bias dominates the match rate); LOW markets, whose extreme sits in a narrow pre-dawn band, lose 6-22 points when the window is shifted, which is what a wrong timezone would look like. The extreme's local-standard hour (below) is physically right: HIGH mode 14:00 LST (=15:00 DST), LOW mode 04:00-05:00 LST. The residual mismatch at shift 0 is the 1 degF feed bias tabulated above, not a timezone error.)

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

**What this says.** The frozen rule, as parameterised, selects the empty set (spec defect, section 3). The reading that lets it fire has a ~24% false-lock rate because the feed's day extreme and the official settlement value differ by one whole degree (about half of HIGH days on the 1-min feed, 15-40% of LOW days), in a feed-specific direction, and a rung is only two whole degrees wide. The prices agree with the diagnosis: among fires that can actually be entered at L=10 the false-lock rate is 58%, because YES is still offered at <=98c mostly when the market already knows the feed extreme is not the official one (those losers are bought at ~4c, so the loss per false lock is small, but they are not the trades the thesis imagined). Where the market does agree with the signal (entry ask >= 90c, n=189) the signal is right 97.9% of the time and pays 0.30c/contract net of fees: priced to the penny, no edge.

**What this does not say.** It does not say that finality as an idea is dead. The descriptive table (section 7, no prices, all 4,734 fires) shows the false-lock rate depends on which side of the rung the extreme sits relative to the feed's one-sided bias: on the 1-min feed, HIGH with E==hi 3.5% (n=863) vs E==lo 49.5% (n=865); LOW with E==lo 6.0% (n=637) vs E==hi 17.8% (n=714). That is an *outcome-informed, post-hoc* observation on the same data, so it is a hypothesis for a new pre-registration with its own forward holdout, not a result; and since a winner nets only +1c..+5c while a loser costs up to ~98c, break-even needs a false-lock rate near 1-5% **at the prices actually offered**, which the ask>=90c row above says the market already enforces. A PASS would have been necessary-but-not-sufficient; there is no PASS, so nothing here supports a canary.

**Disagreement guide for the A/B comparison.** If Build A fires on the frozen grid at M=1.0, it has widened the bracket (or used a different [lo,hi]); compare against my 'lattice' rows. If it fires at M=0.5 with E on whole degrees, it has taken lo/hi as something other than floor/cap. If its false-lock rate is far from ~24%, check feed selection (1-min vs routine) and the local-day window first (section 9).
