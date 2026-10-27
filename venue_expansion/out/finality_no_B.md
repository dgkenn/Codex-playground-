# FINALITY-NO + WHOLE-LADDER -- Build B (independent replication)

Spec: `FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27; no bar moved). Code: `finality_no_B.py`. Numbers: `out/finality_no_B.json`. Written from the spec text; no finality_no_A / finality_A / finality_B file was read.

## Verdicts

- **Part 1 (FINAL-NO by never-arrival): INSUFFICIENT**
- **Part 2 (whole-ladder): INSUFFICIENT**

**SAMPLING FRACTION: 2,904 of 6,039 city-day events (48.1%) have candlesticks and enter the analysis; LIVE partition (settled ~2026-08-21..10-20): 2440/2440 = CENSUS; HISTORICAL partition (2026-05-23..~08-20): 464/3599 = 12.9% random sample.** Why stratified: live events cost 1 batch request, historical events ~6 requests (no batch endpoint) at ~1 request/second with 429 backoff, so a single uniform prefix could not cover the universe in one session. Within each stratum the work order is the seeded (seed 20261027) shuffle and was NEVER re-sorted, so each stratum's fetched set is a uniform random subsample of that stratum (work-order index of first un-fetched event overall: 757). To keep pooled estimates unbiased for the whole universe every fire/day carries a stratified design weight N_h/n_h (live 1.00, historical 7.76); ALL EVs and t-statistics below are design-weighted (and volume-weighted where labelled); counts (n, fires, k/N, Wilson) are raw. Series covered 40/40 (per-series n 65..78). Obs feed per usable event: {'routine': 1468, '1min': 1436}.

## Primary cell (G=4, R=2, H=3, W=120), L=10 -- the deployable arm

| metric | value |
|---|---|
| signalled FINAL-NO rung fires (never-arrival, any price) | 2,524 over 1185 city-days |
| priced fires (n) | 31 over 26 city-days / 23 calendar days / 13 stations |
| false-lock, all fires | 4/2524 = 0.16%, Wilson 95% UB 0.41% (4 false-lock city-days) |
| false-lock, priced fires | 2/31, Wilson 95% UB 20.72% |
| EV/contract, volume-weighted, fee-inclusive | 1.76c (unweighted -8.38c) |
| signed t, city-day clustered / calendar-day clustered | 2.58 (df 25) / 2.58 (df 22); Bonferroni bar 3.627 |
| one-sided 97.9% UB on vw EV | 3.22c |
| mean NO cost paid | 94.10c |
| untradeable fraction | 98.8% {'candles_exist_but_none_<=98c_net>0': 1953, 'no_candle_at_or_after_entry_time': 540} |

## Part 1 grid (12 cells x 3 latency arms)

Columns: fires = signalled rung fires; n = priced; UT = untradeable %; FL = false-lock k/N all fires (Wilson UB %); EVvw / EVuw = volume-weighted / unweighted fee-inclusive EV in c per contract; t_cd / t_cal = signed t, city-day / calendar-day clusters; bar = exact Student-t Bonferroni (39 comparisons) at the realised df; days = priced calendar days; stn = priced stations; UB = one-sided 97.9% upper bound on EVvw.

| G | R | W | L | fires | n | UT% | FL | EVvw | EVuw | t_cd | t_cal | bar | days | stn | UB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 60 | 0 | 4395 | 85 | 98.1 | 71/4395 (2.0) | -0.84 | -6.07 | -0.23 | -0.23 | 3.35 | 54 | 19 | 6.65 |
| 2 | 2 | 60 | 10 | 4395 | 51 | 98.8 | 71/4395 (2.0) | -8.97 | -8.75 | -0.94 | -0.94 | 3.46 | 35 | 16 | 11.10 |
| 2 | 2 | 60 | 20 | 4395 | 46 | 99.0 | 71/4395 (2.0) | -6.27 | -9.16 | -0.65 | -0.64 | 3.49 | 31 | 15 | 14.20 |
| 2 | 2 | 120 | 0 | 4569 | 221 | 95.2 | 76/4569 (2.1) | 8.69 | -3.54 | 1.11 | 1.11 | 3.27 | 82 | 20 | 24.72 |
| 2 | 2 | 120 | 10 | 4569 | 202 | 95.6 | 76/4569 (2.1) | 6.02 | -3.97 | 0.88 | 0.88 | 3.27 | 80 | 20 | 19.99 |
| 2 | 2 | 120 | 20 | 4569 | 187 | 95.9 | 76/4569 (2.1) | 9.05 | -4.03 | 1.18 | 1.17 | 3.28 | 78 | 20 | 24.81 |
| 2 | 4 | 60 | 0 | 3615 | 55 | 98.5 | 67/3615 (2.3) | -3.24 | -10.84 | -0.59 | -0.59 | 3.43 | 39 | 16 | 8.23 |
| 2 | 4 | 60 | 10 | 3615 | 33 | 99.1 | 67/3615 (2.3) | -28.38 | -14.81 | -1.54 | -1.53 | 3.63 | 24 | 14 | 11.24 |
| 2 | 4 | 60 | 20 | 3615 | 31 | 99.1 | 67/3615 (2.3) | -19.97 | -14.09 | -0.99 | -0.99 | 3.67 | 22 | 13 | 23.41 |
| 2 | 4 | 120 | 0 | 3901 | 135 | 96.5 | 70/3901 (2.3) | -4.58 | -6.40 | -1.35 | -1.34 | 3.30 | 67 | 20 | 2.42 |
| 2 | 4 | 120 | 10 | 3901 | 125 | 96.8 | 70/3901 (2.3) | -3.35 | -6.59 | -1.70 | -1.70 | 3.31 | 67 | 20 | 0.69 |
| 2 | 4 | 120 | 20 | 3901 | 113 | 97.1 | 70/3901 (2.3) | -3.83 | -6.91 | -1.18 | -1.18 | 3.31 | 65 | 20 | 2.86 |
| 4 | 2 | 60 | 0 | 2409 | 12 | 99.5 | 4/2409 (0.4) | 17.05 | -4.14 | 8.05 | 8.05 | 5.18 | 8 | 6 | 22.31 |
| 4 | 2 | 60 | 10 | 2409 | 11 | 99.5 | 4/2409 (0.4) | -36.83 | -6.29 | -6.93 | -6.93 | 5.68 | 7 | 6 | -23.15 |
| 4 | 2 | 60 | 20 | 2409 | 11 | 99.5 | 4/2409 (0.4) | -56.28 | -9.02 | -1.96 | -1.96 | 5.68 | 7 | 6 | 17.55 |
| 4 | 2 | 120 | 0 | 2524 | 35 | 98.6 | 4/2524 (0.4) | 1.76 | -7.90 | 2.59 | 2.58 | 3.57 | 24 | 13 | 3.20 |
| 4 | 2 | 120 | 10 | 2524 | 31 | 98.8 | 4/2524 (0.4) | 1.76 | -8.38 | 2.58 | 2.58 | 3.63 | 23 | 13 | 3.22 |
| 4 | 2 | 120 | 20 | 2524 | 30 | 98.8 | 4/2524 (0.4) | 1.84 | -7.94 | 2.68 | 2.68 | 3.65 | 23 | 13 | 3.31 |
| 4 | 4 | 60 | 0 | 1925 | 10 | 99.5 | 3/1925 (0.5) | 17.48 | -5.46 | 9.31 | 9.31 | 6.51 | 6 | 4 | 22.57 |
| 4 | 4 | 60 | 10 | 1925 | 9 | 99.5 | 3/1925 (0.5) | -39.61 | -8.82 | -21.50 | -21.50 | 8.07 | 5 | 4 | -34.18 |
| 4 | 4 | 60 | 20 | 1925 | 9 | 99.5 | 3/1925 (0.5) | -76.47 | -12.05 | -5.17 | -5.17 | 8.07 | 5 | 4 | -32.82 |
| 4 | 4 | 120 | 0 | 2110 | 25 | 98.8 | 4/2110 (0.5) | 1.09 | -9.48 | 6.40 | 6.38 | 3.74 | 19 | 11 | 1.47 |
| 4 | 4 | 120 | 10 | 2110 | 21 | 99.0 | 4/2110 (0.5) | 1.09 | -10.10 | 6.36 | 6.36 | 3.90 | 17 | 11 | 1.47 |
| 4 | 4 | 120 | 20 | 2110 | 20 | 99.1 | 4/2110 (0.5) | 1.10 | -9.70 | 6.31 | 6.31 | 3.95 | 16 | 11 | 1.48 |
| 6 | 2 | 60 | 0 | 1024 | 5 | 99.5 | 0/1024 (0.4) | 23.21 | 16.69 | n/a | n/a | 27.90 | 3 | 3 | 23.21 |
| 6 | 2 | 60 | 10 | 1024 | 5 | 99.5 | 0/1024 (0.4) | 11.00 | 15.77 | n/a | n/a | 27.90 | 3 | 3 | 11.00 |
| 6 | 2 | 60 | 20 | 1024 | 5 | 99.5 | 0/1024 (0.4) | n/a | 9.94 | n/a | n/a | inf | 3 | 3 | n/a |
| 6 | 2 | 120 | 0 | 1089 | 8 | 99.3 | 0/1089 (0.4) | 1.00 | 1.11 | n/a | n/a | 6.51 | 5 | 6 | 1.00 |
| 6 | 2 | 120 | 10 | 1089 | 7 | 99.4 | 0/1089 (0.4) | 1.00 | 1.04 | n/a | n/a | 8.07 | 4 | 5 | 1.00 |
| 6 | 2 | 120 | 20 | 1089 | 7 | 99.4 | 0/1089 (0.4) | 1.00 | 1.07 | n/a | n/a | 8.07 | 4 | 5 | 1.00 |
| 6 | 4 | 60 | 0 | 790 | 5 | 99.4 | 0/790 (0.5) | 23.21 | 16.69 | n/a | n/a | 27.90 | 3 | 3 | 23.21 |
| 6 | 4 | 60 | 10 | 790 | 5 | 99.4 | 0/790 (0.5) | 11.00 | 15.77 | n/a | n/a | 27.90 | 3 | 3 | 11.00 |
| 6 | 4 | 60 | 20 | 790 | 5 | 99.4 | 0/790 (0.5) | n/a | 9.94 | n/a | n/a | inf | 3 | 3 | n/a |
| 6 | 4 | 120 | 0 | 886 | 6 | 99.3 | 0/886 (0.4) | 1.00 | 1.08 | n/a | n/a | 11.88 | 4 | 4 | 1.00 |
| 6 | 4 | 120 | 10 | 886 | 5 | 99.4 | 0/886 (0.4) | 1.00 | 1.04 | n/a | n/a | 27.90 | 3 | 3 | 1.00 |
| 6 | 4 | 120 | 20 | 886 | 5 | 99.4 | 0/886 (0.4) | 1.00 | 1.04 | n/a | n/a | 27.90 | 3 | 3 | 1.00 |

Part 1 verdict detail: `{"pass_cells": [], "kill_false_lock_primary": false, "best_one_sided_97.9_ub_vw_ev_c": 19.99316557303337, "ev_pos_cells": 7, "ev_pos_cells_failing_n_floor": 6, "kill_no_ev_pos_cell_vacuous": false}`

PASS needs ALL of (L=10, >=1 cell): false-lock <=2% with Wilson UB <=5% (required of BOTH all-fires and priced-fires); vw EV >= +2.0c; signed t >= the exact bar under BOTH city-day and calendar-day clustering (the smaller t must clear the larger bar); n>=100 across >=40 calendar days and >=10 stations; untradeable <=70%.

## Anchor (d): never-arrival vs overshoot reported separately

Part 1 fires are NEVER-ARRIVAL only (HIGH: E <= lo-G; LOW: E >= hi+G). The overshoot flavour is what the deployed rule already locks; here it is run through the identical timing/entry machinery as a mirror reference (HIGH: E >= hi+G; LOW: E <= lo-G; same R, H, W, same NO-entry rule) so the two are never pooled:

| flavour (primary cell) | L | fires | n priced | UT% | false-lock k/N | EVvw c | EVuw c | mean cost c |
|---|---|---|---|---|---|---|---|---|
| never-arrival (the new finding) | 0 | 2524 | 35 | 98.6 | 4/2524 | 1.76 | -7.90 | 94.49 |
| never-arrival (the new finding) | 10 | 2524 | 31 | 98.8 | 4/2524 | 1.76 | -8.38 | 94.10 |
| never-arrival (the new finding) | 20 | 2524 | 30 | 98.8 | 4/2524 | 1.84 | -7.94 | 93.43 |
| overshoot (mirror; already deployed shape) | 0 | 735 | 8 | 98.9 | 6/735 | -3.40 | -19.00 | 36.00 |
| overshoot (mirror; already deployed shape) | 10 | 735 | 8 | 98.9 | 6/735 | -31.08 | -17.48 | 35.25 |
| overshoot (mirror; already deployed shape) | 20 | 735 | 8 | 98.9 | 6/735 | -65.25 | -23.65 | 38.62 |

**Reading the primary cell.** Only 31 of 2524 never-arrival fires ever offer NO at <=98c with positive net (1.23%): on {'yes_bid_zero_on_every_candle (NO cost 100c)': 1884, 'no_candle_at_or_after_entry': 540, 'best_NO_cost_99c (net 0 after 1c fee)': 69, 'priced (cost<=98c, net>0)': 31} (all / HIGH: {'yes_bid_zero_on_every_candle (NO cost 100c)': 718, 'no_candle_at_or_after_entry': 265, 'best_NO_cost_99c (net 0 after 1c fee)': 1} / LOW: {'yes_bid_zero_on_every_candle (NO cost 100c)': 1166, 'best_NO_cost_99c (net 0 after 1c fee)': 68, 'no_candle_at_or_after_entry': 275, 'priced (cost<=98c, net>0)': 31}). The dead rungs simply have no YES bid (NO costs 100c) -- there is no discount to buy. The false-lock rate over ALL fires is 0.16% but over the PRICED fires it is 2/31 (Wilson UB 20.7%): the minutes at which NO is actually cheap are exactly the minutes the book disagrees with the obs-only inference -- adverse selection. The volume-weighted EV (1.76c) and the volume-unweighted design-weighted EV (-8.38c; raw mean -1.55c) have opposite signs because a handful of high-volume cheap-NO winners dominate the volume weights while the two false-locks (-94c each) dominate the unweighted mean; neither estimate clears its bar. Every priced primary-cell fire is a LOW market (see the HIGH split below: zero priced).

### Primary cell, descriptive splits (L=10; not part of the frozen comparisons)

| split | fires | n priced | false-lock k/N | EVuw c |
|---|---|---|---|---|
| 1-minute feed | 1115 | 23 | 1/1115 | -10.65 |
| routine feed | 1409 | 8 | 3/1409 | 1.41 |
| HIGH markets | 984 | 0 | 2/984 | n/a |
| LOW markets | 1540 | 31 | 2/1540 | -8.38 |

## Part 2 -- whole ladder from one inference

Definition used (the spec leaves it to the builder): a city-day is *signalling* when either primary-cell finality signal fires on any bracket rung of an event -- FINAL-NO (G=4,R=2,H=3,W=120) or the companion FINAL-YES (M=1.0,R=2,H=3,W=120) -- at the earliest such obs time t*. The inferred settlement value is X^ = round(E(t*)); the inferred winner is the unique rung (brackets AND the two tail T-rungs, which complete the partition) containing X^; every other rung is an inferred loser. Winner -> buy YES at yes_ask; every loser -> buy NO at 100 - yes_bid; each gated independently on first candle >= t*+L with cost <=98c and net >0. A city-day = (station, local date); HIGH and LOW ladders of the same city-day are pooled (conservative). Days with no priced fire count as 0 net in the per-day mean.

| L | signalling city-days | rung evals | priced fires | fires / signalling day | fires / day with >=1 fire | per-day net EV c | SE | t (city-day) | t (calendar) | bar | UB97.9 | wrong-inference ladders |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1185 | 8712 | 999 | 0.78 | 1.89 | -0.45 | 0.64 | -0.71 | -0.74 | 3.228 | 0.84 | 20.2% |
| 10 | 1185 | 8712 | 914 | 0.73 | 1.84 | -0.57 | 0.62 | -0.91 | -0.94 | 3.228 | 0.70 | 20.2% |
| 20 | 1185 | 8712 | 843 | 0.68 | 1.79 | -0.58 | 0.60 | -0.96 | -0.98 | 3.228 | 0.65 | 20.2% |

Part 2 PASS criteria at L=10: fires/signalling-day >= 3 -> False; per-day net >= +4.0c -> False; t >= bar -> False; and Part 1 PASS (companion TERMINAL result not visible to this build) -> False.

### EV by |distance from the inferred extreme| in rungs (L=10; 0 = the inferred winner rung)

| |d| | priced / evaluated | EV c (unweighted) | SE (city-day) | win % | mean cost c |
|---|---|---|---|---|---|
| 0 | 455 / 1452 | -0.62 | 0.85 | 48.4 | 45.1 |
| 1 | 394 / 2450 | -1.16 | 1.03 | 45.0 | 45.1 |
| 2 | 42 / 1809 | 0.09 | 1.12 | 74.8 | 77.8 |
| 3 | 14 / 1452 | 1.00 | 0.56 | 96.4 | 90.9 |
| 4+ | 9 / 1549 | 1.58 | 0.54 | 100.0 | 96.6 |

### By flavour (L=10): winner / never-arrival loser / overshoot loser

| flavour | priced / evaluated | EV c | SE | win % | mean cost c |
|---|---|---|---|---|---|
| winner | 455 / 1452 | -0.62 | 0.85 | 48.4 | 45.1 |
| never | 378 / 5905 | -0.19 | 1.04 | 62.3 | 59.8 |
| overshoot | 81 / 1355 | -3.89 | 1.04 | 2.0 | 7.5 |

Inference quality: round(E(t*)) equals Kalshi's official expiration_value on 60.2% of ladders (93.3% within 1F). A ladder is 'wrong' if ANY of its fires would lose (winner settled NO or a loser settled YES): 20.2% of signalling ladders. One wrong inference loses the whole day's basket -- hence city-day clustering above.

## Sanity anchors

### (a) Oracle reconciliation

- Price-join reproduction of `edge_sizing_v2.json`'s 40 highest-net capturable markets, recomputed from MY candles with the Stage-1 definition (final 60 min, winner side, <=98c, net>0): events fetched 40/40; best winner cost matches 40, best net matches 40, still capturable 40, n_data_minutes within 1: 28.
- Population capturable rate on my sample inside the oracle's window (close < 2026-08-05): 145/1749 = 8.3% vs oracle 0.1035 sample (140/1353), 0.100 pop-weighted.
- Fire-level join check (primary cell, L=10): 31 priced fires; every NO cost equals 100 - the entry candle's yes_bid; 11 correct-NO entries inside the oracle's final-60-minute window all re-derive as oracle-capturable; join violations = 0.
- Limit, disclosed: the oracle JSON stores only its top-40 capturable detail (the 140-market list and the sampled-market list are not in the repo; `cache/edge_sizing/` is absent), so the literal subset test (fires subset-of oracle set) is only checkable on that top-40 and by the rederivation above -- not against the full 140.

### (b) No look-ahead

- Every obs used for a fire at signal time t has timestamp strictly < t (t = newest obs ts + 60 s; asserted in the vectorised walk and in `part1_fire_bruteforce`, which hands the signal ONLY a copied prefix). The vectorised engine and the brute-force prefix engine were asserted identical (fire index, timestamp, E) on 76 events x all bracket rungs x 3 cells.
- Worked example: `KXLOWTCHI-26AUG31-B67.5` cell G,R,W=[4, 2, 120], rung [67,68]. Fire at obs #1319 (ts 2026-09-01T03:59:00+00:00); signal ts 2026-09-01T04:00:00+00:00; running extreme E=72.0; last H=3 obs [81.0, 81.0, 81.0]; prefix used = 1320 of 1440 obs of the day; all prefix obs older than the signal ts: True.

### (c) Monotonicity

- Running max non-decreasing / running min non-increasing: 0 violations in 2904 event-days. Day window asserted: all obs in [dayend-24h, dayend), strictly increasing ts.

## Timezone proof

The running extreme is taken over the station's LOCAL STANDARD-TIME calendar day. Kalshi `close_time` is local standard-time midnight (05:00Z for NYC all year in the live partition, 04:59Z in the historical partition -> rounded up to the hour), so the day is `[dayend-24h, dayend)` in UTC and during daylight-saving time that is 01:00 -> 01:00 on the local wall clock. IEM obs are requested with `tz=UTC` and candlestick `end_period_ts` is a UTC epoch, so all three clocks are epoch seconds and no local conversion enters the signal. Worked examples (selected only by: full 1-minute coverage, a DST-season date, and the naive DST-clock-midnight window disagreeing with Kalshi's official value while the settlement-day window agrees):

- `KXHIGHTBOS-26OCT17` (max, BOS): listed close 2026-10-18T05:00:00Z; window UTC 2026-10-17T05:00:00+00:00 .. 2026-10-18T05:00:00+00:00 = local wall clock 2026-10-17T01:00:00-04:00 .. 2026-10-18T01:00:00-04:00 (UTC-4); 1440 obs; extreme 62.0 at 2026-10-17T05:00:00+00:00 UTC = 2026-10-17T01:00:00-04:00; Kalshi expiration_value **62.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 64.0, 'naive UTC-calendar-day window': 68.0}.
- `KXLOWTNYC-26JUN14` (min, NYC): listed close 2026-06-15T05:00:00Z; window UTC 2026-06-14T05:00:00+00:00 .. 2026-06-15T05:00:00+00:00 = local wall clock 2026-06-14T01:00:00-04:00 .. 2026-06-15T01:00:00-04:00 (UTC-4); 1440 obs; extreme 70.0 at 2026-06-15T04:43:00+00:00 UTC = 2026-06-15T00:43:00-04:00; Kalshi expiration_value **70.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 71.0, 'naive UTC-calendar-day window': 72.0}.
- `KXLOWTSEA-26OCT14` (min, SEA): listed close 2026-10-15T08:00:00Z; window UTC 2026-10-14T08:00:00+00:00 .. 2026-10-15T08:00:00+00:00 = local wall clock 2026-10-14T01:00:00-07:00 .. 2026-10-15T01:00:00-07:00 (UTC-7); 1440 obs; extreme 51.0 at 2026-10-15T07:09:00+00:00 UTC = 2026-10-15T00:09:00-07:00; Kalshi expiration_value **51.0**; skewed windows would have given {'naive DST-clock-midnight window (dayend-25h..dayend-1h)': 54.0, 'naive UTC-calendar-day window': 55.0}.

Aggregate check on every usable event-day of the SAMPLE (extreme of the window == Kalshi `expiration_value` to within 0.5F):

| window | n | exact match |
|---|---|---|
| dst_local_midnight(dayend-25h..dayend-1h) | 2904 | 1530 (52.7%) |
| lst_midnight(dayend-24h..dayend) | 2904 | 1626 (56.0%) |
| utc_calendar_day | 2904 | 1390 (47.9%) |

Feed-level: {'n_by_feed': {'routine': 1468, '1min': 1436}, 'final_extreme_equals_expiration_value': {'routine': 692, '1min': 934}, 'within_1F': {'routine': 1339, '1min': 1416}}

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
