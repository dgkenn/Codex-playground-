# FINALITY-NO + WHOLE-LADDER -- Build B (independent replication)

Spec: `FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27; no bar moved). Code: `finality_no_B.py`. Numbers: `out/finality_no_B.json`. Written from the spec text; no finality_no_A / finality_A / finality_B file was read.

## Verdicts

- **Part 1 (FINAL-NO by never-arrival): KILL**
- **Part 2 (whole-ladder): INSUFFICIENT**

**SAMPLING FRACTION: 229 of 6,039 city-day events (3.8%), i.e. 229 of 36,234 rungs' ladders.** Method: ONE seeded shuffle (seed 20261027) of every settled city-day event, never re-sorted; candlesticks were fetched in that order, so the fetched set is a uniform random subsample (the work order was never series- or date-sorted; contiguous prefix = 102). Series covered 40/40 (per-series n 1..10). Partitions fetched {'live': 158, 'hist': 71} of {'live': 2440, 'hist': 3599} (live = settled on/after ~2026-08-21 via batch candlesticks; hist = Kalshi historical partition, 1 call per rung, which is why the full universe did not fit in a session at ~1 request/second). Obs feed per usable event: {'routine': 96, '1min': 133}.

## Primary cell (G=4, R=2, H=3, W=120), L=10 -- the deployable arm

| metric | value |
|---|---|
| signalled FINAL-NO rung fires (never-arrival, any price) | 202 over 120 city-days |
| priced fires (n) | 2 over 2 city-days / 2 calendar days / 2 stations |
| false-lock, all fires | 0/202 = 0.00%, Wilson 95% UB 1.87% (0 false-lock city-days) |
| false-lock, priced fires | 0/2, Wilson 95% UB 65.76% |
| EV/contract, volume-weighted, fee-inclusive | 4.86c (unweighted 3.50c) |
| signed t, city-day clustered / calendar-day clustered | 2.76 (df 1) / 2.76 (df 1); Bonferroni bar 496.563 |
| one-sided 97.9% UB on vw EV | 31.52c |
| mean NO cost paid | 95.50c |
| untradeable fraction | 99.0% {'candles_exist_but_none_<=98c_net>0': 163, 'no_candle_at_or_after_entry_time': 37} |

## Part 1 grid (12 cells x 3 latency arms)

Columns: fires = signalled rung fires; n = priced; UT = untradeable %; FL = false-lock k/N all fires (Wilson UB %); EVvw / EVuw = volume-weighted / unweighted fee-inclusive EV in c per contract; t_cd / t_cal = signed t, city-day / calendar-day clusters; bar = exact Student-t Bonferroni (39 comparisons) at the realised df; days = priced calendar days; stn = priced stations; UB = one-sided 97.9% upper bound on EVvw.

| G | R | W | L | fires | n | UT% | FL | EVvw | EVuw | t_cd | t_cal | bar | days | stn | UB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 60 | 0 | 356 | 4 | 98.9 | 5/356 (3.2) | -1.26 | 0.04 | -1.38 | -1.38 | 11.88 | 4 | 3 | 1.85 |
| 2 | 2 | 60 | 10 | 356 | 2 | 99.4 | 5/356 (3.2) | 1.00 | 1.23 | n/a | n/a | 496.56 | 2 | 2 | 1.00 |
| 2 | 2 | 60 | 20 | 356 | 2 | 99.4 | 5/356 (3.2) | 1.00 | 1.00 | n/a | n/a | 496.56 | 2 | 2 | 1.00 |
| 2 | 2 | 120 | 0 | 368 | 15 | 95.9 | 6/368 (3.5) | -13.67 | -3.64 | -1.28 | -1.28 | 4.09 | 13 | 11 | 10.36 |
| 2 | 2 | 120 | 10 | 368 | 13 | 96.5 | 6/368 (3.5) | -16.17 | -4.03 | -1.33 | -1.33 | 4.29 | 11 | 9 | 11.76 |
| 2 | 2 | 120 | 20 | 368 | 13 | 96.5 | 6/368 (3.5) | -17.03 | -3.98 | -1.36 | -1.35 | 4.29 | 11 | 9 | 11.76 |
| 2 | 4 | 60 | 0 | 314 | 3 | 99.0 | 5/314 (3.7) | -1.26 | -0.14 | -1.30 | -1.30 | 27.90 | 3 | 2 | 3.31 |
| 2 | 4 | 60 | 10 | 314 | 1 | 99.7 | 5/314 (3.7) | 1.00 | 1.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 2 | 4 | 60 | 20 | 314 | 1 | 99.7 | 5/314 (3.7) | 1.00 | 1.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 2 | 4 | 120 | 0 | 336 | 11 | 96.7 | 5/336 (3.4) | 0.42 | 0.42 | 0.46 | 0.46 | 4.43 | 10 | 8 | 2.57 |
| 2 | 4 | 120 | 10 | 336 | 9 | 97.3 | 5/336 (3.4) | 1.05 | 0.32 | 1.64 | 1.63 | 4.84 | 8 | 6 | 2.61 |
| 2 | 4 | 120 | 20 | 336 | 9 | 97.3 | 5/336 (3.4) | 1.06 | 0.23 | 1.51 | 1.51 | 4.84 | 8 | 6 | 2.75 |
| 4 | 2 | 60 | 0 | 194 | 0 | 100.0 | 0/194 (1.9) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 2 | 60 | 10 | 194 | 0 | 100.0 | 0/194 (1.9) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 2 | 60 | 20 | 194 | 0 | 100.0 | 0/194 (1.9) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 2 | 120 | 0 | 202 | 3 | 98.5 | 0/202 (1.9) | 4.86 | 3.00 | 3.18 | 3.18 | 27.90 | 3 | 3 | 12.07 |
| 4 | 2 | 120 | 10 | 202 | 2 | 99.0 | 0/202 (1.9) | 4.86 | 3.50 | 2.76 | 2.76 | 496.56 | 2 | 2 | 31.52 |
| 4 | 2 | 120 | 20 | 202 | 2 | 99.0 | 0/202 (1.9) | 5.68 | 3.50 | 9.37 | 9.37 | 496.56 | 2 | 2 | 14.85 |
| 4 | 4 | 60 | 0 | 166 | 0 | 100.0 | 0/166 (2.3) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 4 | 60 | 10 | 166 | 0 | 100.0 | 0/166 (2.3) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 4 | 60 | 20 | 166 | 0 | 100.0 | 0/166 (2.3) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 4 | 4 | 120 | 0 | 181 | 2 | 98.9 | 0/181 (2.1) | 1.00 | 1.50 | n/a | n/a | 496.56 | 2 | 2 | 1.00 |
| 4 | 4 | 120 | 10 | 181 | 1 | 99.4 | 0/181 (2.1) | 1.00 | 1.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 4 | 4 | 120 | 20 | 181 | 1 | 99.4 | 0/181 (2.1) | 1.00 | 1.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 6 | 2 | 60 | 0 | 80 | 0 | 100.0 | 0/80 (4.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 2 | 60 | 10 | 80 | 0 | 100.0 | 0/80 (4.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 2 | 60 | 20 | 80 | 0 | 100.0 | 0/80 (4.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 2 | 120 | 0 | 84 | 1 | 98.8 | 0/84 (4.4) | n/a | 2.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 6 | 2 | 120 | 10 | 84 | 0 | 100.0 | 0/84 (4.4) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 2 | 120 | 20 | 84 | 0 | 100.0 | 0/84 (4.4) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 4 | 60 | 0 | 65 | 0 | 100.0 | 0/65 (5.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 4 | 60 | 10 | 65 | 0 | 100.0 | 0/65 (5.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 4 | 60 | 20 | 65 | 0 | 100.0 | 0/65 (5.6) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 4 | 120 | 0 | 72 | 1 | 98.6 | 0/72 (5.1) | n/a | 2.00 | n/a | n/a | inf | 1 | 1 | n/a |
| 6 | 4 | 120 | 10 | 72 | 0 | 100.0 | 0/72 (5.1) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |
| 6 | 4 | 120 | 20 | 72 | 0 | 100.0 | 0/72 (5.1) | n/a | n/a | n/a | n/a | n/a | 0 | 0 | n/a |

Part 1 verdict detail: `{"pass_cells": [], "kill_false_lock_primary": false, "best_one_sided_97.9_ub_vw_ev_c": 31.52343688812252, "ev_pos_cells": 5, "ev_pos_cells_failing_n_floor": 5, "kill_no_ev_pos_cell_vacuous": false}`

PASS needs ALL of (L=10, >=1 cell): false-lock <=2% with Wilson UB <=5% (required of BOTH all-fires and priced-fires); vw EV >= +2.0c; signed t >= the exact bar under BOTH city-day and calendar-day clustering (the smaller t must clear the larger bar); n>=100 across >=40 calendar days and >=10 stations; untradeable <=70%.

## Anchor (d): never-arrival vs overshoot reported separately

Part 1 fires are NEVER-ARRIVAL only (HIGH: E <= lo-G; LOW: E >= hi+G). The overshoot flavour is what the deployed rule already locks; here it is run through the identical timing/entry machinery as a mirror reference (HIGH: E >= hi+G; LOW: E <= lo-G; same R, H, W, same NO-entry rule) so the two are never pooled:

| flavour (primary cell) | L | fires | n priced | UT% | false-lock k/N | EVvw c | EVuw c | mean cost c |
|---|---|---|---|---|---|---|---|---|
| never-arrival (the new finding) | 0 | 202 | 3 | 98.5 | 0/202 | 4.86 | 3.00 | 96.00 |
| never-arrival (the new finding) | 10 | 202 | 2 | 99.0 | 0/202 | 4.86 | 3.50 | 95.50 |
| never-arrival (the new finding) | 20 | 202 | 2 | 99.0 | 0/202 | 5.68 | 3.50 | 95.50 |
| overshoot (mirror; already deployed shape) | 0 | 54 | 0 | 100.0 | 0/54 | n/a | n/a | n/a |
| overshoot (mirror; already deployed shape) | 10 | 54 | 0 | 100.0 | 0/54 | n/a | n/a | n/a |
| overshoot (mirror; already deployed shape) | 20 | 54 | 0 | 100.0 | 0/54 | n/a | n/a | n/a |

### Primary cell, descriptive splits (L=10; not part of the frozen comparisons)

| split | fires | n priced | false-lock k/N | EVuw c |
|---|---|---|---|---|
| 1-minute feed | 122 | 1 | 0/122 | 1.00 |
| routine feed | 80 | 1 | 0/80 | 6.00 |
| HIGH markets | 75 | 0 | 0/75 | n/a |
| LOW markets | 127 | 2 | 0/127 | 3.50 |

## Part 2 -- whole ladder from one inference

Definition used (the spec leaves it to the builder): a city-day is *signalling* when either primary-cell finality signal fires on any bracket rung of an event -- FINAL-NO (G=4,R=2,H=3,W=120) or the companion FINAL-YES (M=1.0,R=2,H=3,W=120) -- at the earliest such obs time t*. The inferred settlement value is X^ = round(E(t*)); the inferred winner is the unique rung (brackets AND the two tail T-rungs, which complete the partition) containing X^; every other rung is an inferred loser. Winner -> buy YES at yes_ask; every loser -> buy NO at 100 - yes_bid; each gated independently on first candle >= t*+L with cost <=98c and net >0. A city-day = (station, local date); HIGH and LOW ladders of the same city-day are pooled (conservative). Days with no priced fire count as 0 net in the per-day mean.

| L | signalling city-days | rung evals | priced fires | fires / signalling day | fires / day with >=1 fire | per-day net EV c | SE | t (city-day) | t (calendar) | bar | UB97.9 | wrong-inference ladders |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 120 | 720 | 88 | 0.70 | 1.88 | 0.17 | 0.79 | 0.21 | 0.21 | 3.299 | 1.79 | 18.1% |
| 10 | 120 | 720 | 81 | 0.65 | 1.77 | 0.01 | 0.69 | 0.01 | 0.01 | 3.299 | 1.42 | 18.1% |
| 20 | 120 | 720 | 79 | 0.63 | 1.71 | -0.02 | 0.70 | -0.03 | -0.03 | 3.299 | 1.42 | 18.1% |

Part 2 PASS criteria at L=10: fires/signalling-day >= 3 -> False; per-day net >= +4.0c -> False; t >= bar -> False; and Part 1 PASS (companion TERMINAL result not visible to this build) -> False.

### EV by |distance from the inferred extreme| in rungs (L=10; 0 = the inferred winner rung)

| |d| | priced / evaluated | EV c (unweighted) | SE (city-day) | win % | mean cost c |
|---|---|---|---|---|---|
| 0 | 38 / 120 | 0.10 | 1.22 | 57.5 | 49.7 |
| 1 | 39 / 205 | 1.21 | 0.96 | 47.6 | 43.6 |
| 2 | 2 / 148 | -43.00 | 44.00 | 50.0 | 92.0 |
| 3 | 2 / 120 | 3.50 | 2.50 | 100.0 | 95.5 |
| 4+ | 0 | n/a | n/a | n/a | n/a |

### By flavour (L=10): winner / never-arrival loser / overshoot loser

| flavour | priced / evaluated | EV c | SE | win % | mean cost c |
|---|---|---|---|---|---|
| winner | 38 / 120 | 0.10 | 1.22 | 57.5 | 49.7 |
| never | 36 / 487 | 0.61 | 1.12 | 59.7 | 57.3 |
| overshoot | 7 / 113 | -3.20 | 0.75 | 0.0 | 2.0 |

Inference quality: round(E(t*)) equals Kalshi's official expiration_value on 63.3% of ladders (97.4% within 1F). A ladder is 'wrong' if ANY of its fires would lose (winner settled NO or a loser settled YES): 18.1% of signalling ladders. One wrong inference loses the whole day's basket -- hence city-day clustering above.

## Sanity anchors

### (a) Oracle reconciliation

- Price-join reproduction of `edge_sizing_v2.json`'s 40 highest-net capturable markets, recomputed from MY candles with the Stage-1 definition (final 60 min, winner side, <=98c, net>0): events fetched 0/40; best winner cost matches 0, best net matches 0, still capturable 0, n_data_minutes within 1: 0.
- Population capturable rate on my sample inside the oracle's window (close < 2026-08-05): 20/275 = 7.3% vs oracle 0.1035 sample (140/1353), 0.100 pop-weighted.
- Fire-level join check (primary cell, L=10): 2 priced fires; every NO cost equals 100 - the entry candle's yes_bid; 1 correct-NO entries inside the oracle's final-60-minute window all re-derive as oracle-capturable; join violations = 0.
- Limit, disclosed: the oracle JSON stores only its top-40 capturable detail (the 140-market list and the sampled-market list are not in the repo; `cache/edge_sizing/` is absent), so the literal subset test (fires subset-of oracle set) is only checkable on that top-40 and by the rederivation above -- not against the full 140.

### (b) No look-ahead

- Every obs used for a fire at signal time t has timestamp strictly < t (t = newest obs ts + 60 s; asserted in the vectorised walk and in `part1_fire_bruteforce`, which hands the signal ONLY a copied prefix). The vectorised engine and the brute-force prefix engine were asserted identical (fire index, timestamp, E) on 8 events x all bracket rungs x 3 cells.
- Worked example: `KXLOWTCHI-26AUG31-B67.5` cell G,R,W=[4, 2, 120], rung [67,68]. Fire at obs #1319 (ts 2026-09-01T03:59:00+00:00); signal ts 2026-09-01T04:00:00+00:00; running extreme E=72.0; last H=3 obs [81.0, 81.0, 81.0]; prefix used = 1320 of 1440 obs of the day; all prefix obs older than the signal ts: True.

### (c) Monotonicity

- Running max non-decreasing / running min non-increasing: 0 violations in 229 event-days. Day window asserted: all obs in [dayend-24h, dayend), strictly increasing ts.

## Timezone proof

The running extreme is taken over the station's LOCAL STANDARD-TIME calendar day. Kalshi `close_time` is local standard-time midnight (05:00Z for NYC all year in the live partition, 04:59Z in the historical partition -> rounded up to the hour), so the day is `[dayend-24h, dayend)` in UTC and during daylight-saving time that is 01:00 -> 01:00 on the local wall clock. IEM obs are requested with `tz=UTC` and candlestick `end_period_ts` is a UTC epoch, so all three clocks are epoch seconds and no local conversion enters the signal. Worked examples (days where a naive DST-clock-midnight window WOULD have produced a different extreme than Kalshi's official value):

- `KXHIGHTBOS-26OCT17` (max, BOS): listed close 2026-10-18T05:00:00Z; window UTC 2026-10-17T05:00:00+00:00 .. 2026-10-18T05:00:00+00:00 = local wall clock 2026-10-17T01:00:00-04:00 .. 2026-10-18T01:00:00-04:00 (UTC-4); 1440 obs; extreme 62.0 at 2026-10-17T05:00:00+00:00 UTC = 2026-10-17T01:00:00-04:00; Kalshi expiration_value **62.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 64.0, 'naive UTC-calendar-day window': 68.0}.
- `KXHIGHTSEA-26JUL08` (max, SEA): listed close 2026-07-09T08:00:00Z; window UTC 2026-07-08T08:00:00+00:00 .. 2026-07-09T08:00:00+00:00 = local wall clock 2026-07-08T01:00:00-07:00 .. 2026-07-09T01:00:00-07:00 (UTC-7); 1440 obs; extreme 71.0 at 2026-07-08T23:45:00+00:00 UTC = 2026-07-08T16:45:00-07:00; Kalshi expiration_value **71.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 71.0, 'naive UTC-calendar-day window': 76.0}.
- `KXLOWTLAX-26JUN04` (min, LAX): listed close 2026-06-05T08:00:00Z; window UTC 2026-06-04T08:00:00+00:00 .. 2026-06-05T08:00:00+00:00 = local wall clock 2026-06-04T01:00:00-07:00 .. 2026-06-05T01:00:00-07:00 (UTC-7); 1440 obs; extreme 62.0 at 2026-06-04T08:00:00+00:00 UTC = 2026-06-04T01:00:00-07:00; Kalshi expiration_value **62.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 62.0, 'naive UTC-calendar-day window': 60.0}.

Aggregate check on every usable event-day of the SAMPLE (extreme of the window == Kalshi `expiration_value` to within 0.5F):

| window | n | exact match |
|---|---|---|
| dst_local_midnight(dayend-25h..dayend-1h) | 229 | 125 (54.6%) |
| lst_midnight(dayend-24h..dayend) | 229 | 138 (60.3%) |
| utc_calendar_day | 229 | 115 (50.2%) |

Feed-level: {'n_by_feed': {'routine': 96, '1min': 133}, 'final_extreme_equals_expiration_value': {'routine': 46, '1min': 92}, 'within_1F': {'routine': 88, '1min': 132}}

Note: the IEM 1-minute HIGH extreme sits 1F ABOVE the official value on roughly half of days (official Weather Company values are lower than the 1-minute ASOS max); LOW matches to within 1F >99%. Full-universe obs-only profile is in the json (`obs_bias_full_universe`).

## Interpretation choices (spec silent; fixed BEFORE any outcome was read, never tuned)

- Bracket win set = integer settlement X in [floor_strike, cap_strike] inclusive (verified against official result + expiration_value); T 'greater f' = X >= f+1; T 'less c' = X <= c-1. Part 1 uses '-B' rungs only; Part 2 uses all rungs (partition).
- Obs-only signal time t = (newest obs ts)+60s so every obs used is strictly older than t; window test t in [dayend-W, dayend]; latency L shifts t before seeking entry.
- 'Reversed and held' = the last H=3 obs ALL lie >= R away from the running extreme at the newest obs.
- Entry candle = first candle with end_period_ts >= t+L, cost <=98c, net>0; only printed candles are used (candlesticks are sparse; absent minutes are never back-filled).
- Volume weight = entry-candle volume (zero-volume entries carry zero weight in vw EV; unweighted EV reported alongside).
- Day-clustered t: SE is CR1 cluster-robust; PASS requires the smaller of {city-day (station,date), calendar-date} t to clear the larger of the two exact Bonferroni bars. UB (KILL) uses the city-day clustering.
- Feed: IEM 1-minute if the day has >=1150 obs and >=110 obs in the last 130 min, else routine (disclosed per event; split reported). Physical-bounds glitch filter only (-60..135F).
- Part 2 day signal / winner inference as in the Part 2 section. The TERMINAL-spec pass precondition cannot be observed from this build.
- Part 2 skips ladders whose official results are not exactly-one-YES (count in json `skips`).
- `edge_sizing_v2.normalize()` is reused with its WINDOW_MIN global set to 150 (it hard-filters to the final WINDOW_MIN minutes; the default 60 would silently drop W=120 entries). The historical-partition candlestick schema uses bare keys (`close`, `volume`); a key-name-only shim maps them to the `*_dollars` names normalize() reads -- no value is altered.

Skips: {}

Reproduce: `python3 venue_expansion/finality_no_B.py discover && ... obs && ... candles && ... oracle && ... analyze`.
