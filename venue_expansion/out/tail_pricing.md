# Tail pricing: are Kalshi BTC-hourly longshots overpriced?  (TAIL_PRICING_SPEC.md, executed)

**VERDICT: INSUFFICIENT**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 5)

Sample: 6 of 1408 hourly events (0.4%), 5 of 60 UTC days; 1,128 strikes, 4,512 strike-T observations, 2,131 priced sales (all buckets).

## 1. Anchor (c): calibration table (reported whatever the verdict)

Realised YES rate with Wilson 95% CI, against the executable `yes_bid` the seller receives. `gap` = realised rate minus mean bid, in cents of probability: **gap < 0 means the market overprices YES (selling is favourable before fee)**. CIs treat strikes as independent (they are not: one BTC move hits every strike of an hour), so they are too narrow; the day-clustered t in section 2 is the gate.


### T = 5 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 3 | 0 | 0.00% | [0.00%, 56.15%] | 1.00c | -1.00 | yes |
| 2c | 2 | 0 | 0.00% | [0.00%, 65.76%] | 2.00c | -2.00 | yes |
| 3c | 1 | 1 | 100.00% | [20.65%, 100.00%] | 3.00c | +97.00 | NO |
| 4-5c | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 6-10c | 1 | 0 | 0.00% | [0.00%, 79.35%] | 10.00c | -10.00 | yes |
| 11-20c | 2 | 0 | 0.00% | [0.00%, 65.76%] | 15.50c | -15.50 | yes |
| 21-40c | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 41-60c (not a longshot; report only) | 2 | 1 | 50.00% | [9.45%, 90.55%] | 55.00c | -5.00 | yes |
| 61-80c (not a longshot; report only) | 3 | 2 | 66.67% | [20.77%, 93.85%] | 67.33c | -0.67 | yes |
| 81-100c (not a longshot; report only) | 504 | 504 | 100.00% | [99.24%, 100.00%] | 98.97c | +1.03 | NO |

### T = 15 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 1.00c | -1.00 | yes |
| 2c | 2 | 0 | 0.00% | [0.00%, 65.76%] | 2.00c | -2.00 | yes |
| 3c | 1 | 0 | 0.00% | [0.00%, 79.35%] | 3.00c | -3.00 | yes |
| 4-5c | 1 | 0 | 0.00% | [0.00%, 79.35%] | 4.00c | -4.00 | yes |
| 6-10c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 7.20c | -7.20 | yes |
| 11-20c | 3 | 0 | 0.00% | [0.00%, 56.15%] | 18.67c | -18.67 | yes |
| 21-40c | 2 | 0 | 0.00% | [0.00%, 65.76%] | 31.50c | -31.50 | yes |
| 41-60c (not a longshot; report only) | 3 | 1 | 33.33% | [6.15%, 79.23%] | 46.33c | -13.00 | yes |
| 61-80c (not a longshot; report only) | 4 | 4 | 100.00% | [51.01%, 100.00%] | 69.75c | +30.25 | yes |
| 81-100c (not a longshot; report only) | 503 | 503 | 100.00% | [99.24%, 100.00%] | 98.85c | +1.15 | NO |

### T = 30 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 1.00c | -1.00 | yes |
| 2c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 2.00c | -2.00 | yes |
| 3c | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 4-5c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 4.20c | -4.20 | yes |
| 6-10c | 4 | 0 | 0.00% | [0.00%, 48.99%] | 8.00c | -8.00 | yes |
| 11-20c | 4 | 0 | 0.00% | [0.00%, 48.99%] | 15.50c | -15.50 | yes |
| 21-40c | 6 | 1 | 16.67% | [3.01%, 56.35%] | 32.00c | -15.33 | yes |
| 41-60c (not a longshot; report only) | 3 | 2 | 66.67% | [20.77%, 93.85%] | 54.00c | +12.67 | yes |
| 61-80c (not a longshot; report only) | 6 | 3 | 50.00% | [18.76%, 81.24%] | 71.83c | -21.83 | yes |
| 81-100c (not a longshot; report only) | 504 | 502 | 99.60% | [98.56%, 99.89%] | 98.77c | +0.83 | yes |

### T = 45 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 5 | 0 | 0.00% | [0.00%, 43.45%] | 1.00c | -1.00 | yes |
| 2c | 3 | 0 | 0.00% | [0.00%, 56.15%] | 2.00c | -2.00 | yes |
| 3c | 4 | 0 | 0.00% | [0.00%, 48.99%] | 3.00c | -3.00 | yes |
| 4-5c | 3 | 0 | 0.00% | [0.00%, 56.15%] | 4.67c | -4.67 | yes |
| 6-10c | 4 | 0 | 0.00% | [0.00%, 48.99%] | 7.00c | -7.00 | yes |
| 11-20c | 6 | 1 | 16.67% | [3.01%, 56.35%] | 14.17c | +2.50 | yes |
| 21-40c | 5 | 2 | 40.00% | [11.76%, 76.93%] | 29.60c | +10.40 | yes |
| 41-60c (not a longshot; report only) | 8 | 2 | 25.00% | [7.15%, 59.07%] | 48.38c | -23.38 | yes |
| 61-80c (not a longshot; report only) | 5 | 4 | 80.00% | [37.55%, 96.38%] | 70.40c | +9.60 | yes |
| 81-100c (not a longshot; report only) | 499 | 499 | 100.00% | [99.24%, 100.00%] | 98.68c | +1.32 | NO |

## 2. EV table per cell (selling 1 YES at `yes_bid`, fee-inclusive, cents per contract)

Bonferroni: 28 comparisons, two-sided alpha = 0.00179, bar = Student-t quantile at p = 0.99911 on df = (distinct days - 1). t is signed and day-clustered (equal-weight). `U_T` = entry-time-level untradeable fraction (primary gate-4 reading). `U_ask` = diagnostic: share with bid=0 among strikes whose last-candle ask falls in the bucket range. `nz-vol` = share of priced entries with non-zero volume in the entry candle.

| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) | bar | t (vol) | t (hour-clust) | UB97.9% | U_T | U_ask | nz-vol | PASS gates 1/2/3/4/5 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| 5 | 1 | 3 | 3 | 0.00 | 0.00 | n/a | 23.63 | n/a | n/a | 0.00 | 54.1% | 100.0% | 100.0% | n/n/n/Y/Y |
| 5 | 2 | 2 | 2 | 1.00 | 1.00 | n/a | 356.51 | n/a | n/a | 1.00 | 54.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 5 | 3 | 1 | 1 | -98.00 | -98.00 | n/a | n/a | n/a | n/a | n/a | 54.1% | 0.0% | 100.0% | n/n/n/Y/Y |
| 5 | 4-5 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 54.1% | 0.0% | n/a | n/n/n/Y/n |
| 5 | 6-10 | 1 | 1 | 9.00 | 9.00 | n/a | n/a | n/a | n/a | n/a | 54.1% | n/a | 100.0% | Y/n/n/Y/Y |
| 5 | 11-20 | 2 | 2 | 14.00 | 12.24 | 4.67 | 356.51 | 6.23 | 4.67 | 59.41 | 54.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 5 | 21-40 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 54.1% | n/a | n/a | n/n/n/Y/n |
| 15 | 1 | 5 | 4 | 0.00 | 0.00 | n/a | 10.62 | n/a | n/a | 0.00 | 53.1% | 100.0% | 80.0% | n/n/n/Y/Y |
| 15 | 2 | 2 | 2 | 1.00 | 1.00 | n/a | 356.51 | n/a | n/a | 1.00 | 53.1% | 28.6% | 100.0% | Y/n/n/Y/Y |
| 15 | 3 | 1 | 1 | 2.00 | 2.00 | n/a | n/a | n/a | n/a | n/a | 53.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 15 | 4-5 | 1 | 1 | 3.00 | 3.00 | n/a | n/a | n/a | n/a | n/a | 53.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 15 | 6-10 | 5 | 4 | 6.20 | 6.07 | 10.55 | 10.62 | 9.64 | 8.44 | 8.21 | 53.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 15 | 11-20 | 3 | 3 | 17.00 | 17.08 | 29.44 | 23.63 | 20.98 | 29.44 | 19.73 | 53.1% | 0.0% | 100.0% | Y/Y/n/Y/Y |
| 15 | 21-40 | 2 | 1 | 29.50 | 28.93 | n/a | n/a | n/a | 6.56 | n/a | 53.1% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 30 | 1 | 5 | 5 | 0.00 | 0.00 | n/a | 7.39 | n/a | n/a | 0.00 | 52.0% | 100.0% | 100.0% | n/n/n/Y/Y |
| 30 | 2 | 5 | 4 | 1.00 | 1.00 | n/a | 10.62 | n/a | n/a | 1.00 | 52.0% | 44.4% | 100.0% | Y/n/n/Y/Y |
| 30 | 3 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 52.0% | 0.0% | n/a | n/n/n/Y/n |
| 30 | 4-5 | 5 | 5 | 3.20 | 3.00 | 16.00 | 7.39 | 4952.51 | 16.00 | 3.79 | 52.0% | 0.0% | 80.0% | Y/Y/n/Y/Y |
| 30 | 6-10 | 4 | 3 | 7.00 | 7.72 | 16.17 | 23.63 | 31.57 | 7.67 | 9.05 | 52.0% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 30 | 11-20 | 4 | 4 | 14.25 | 14.45 | 15.06 | 10.62 | 11.00 | 15.06 | 17.48 | 52.0% | 0.0% | 100.0% | Y/Y/n/Y/Y |
| 30 | 21-40 | 6 | 5 | 13.33 | 16.99 | 0.81 | 7.39 | 1.15 | 0.85 | 61.66 | 52.0% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 45 | 1 | 5 | 5 | 0.00 | 0.00 | n/a | 7.39 | n/a | n/a | 0.00 | 52.0% | 100.0% | 80.0% | n/n/n/Y/Y |
| 45 | 2 | 3 | 3 | 1.00 | 1.00 | n/a | 23.63 | n/a | n/a | 1.00 | 52.0% | 16.7% | 100.0% | Y/n/n/Y/Y |
| 45 | 3 | 4 | 4 | 2.00 | 2.00 | n/a | 10.62 | n/a | n/a | 2.00 | 52.0% | 25.0% | 100.0% | Y/n/n/Y/Y |
| 45 | 4-5 | 3 | 3 | 3.67 | 4.00 | 11.00 | 23.63 | n/a | 11.00 | 5.24 | 52.0% | 0.0% | 66.7% | Y/n/n/Y/Y |
| 45 | 6-10 | 4 | 3 | 6.00 | 6.07 | 13.86 | 23.63 | 14.05 | 14.70 | 8.05 | 52.0% | 14.3% | 100.0% | Y/n/n/Y/Y |
| 45 | 11-20 | 6 | 5 | -3.67 | 12.18 | -0.20 | 7.39 | 3.65 | -0.21 | 49.88 | 52.0% | 0.0% | 100.0% | n/n/n/Y/Y |
| 45 | 21-40 | 5 | 4 | -12.40 | -10.72 | -0.62 | 10.62 | -0.38 | -0.53 | 55.39 | 52.0% | 0.0% | 100.0% | n/n/n/Y/Y |

Above-40c buckets (reported, cannot PASS):

| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) |
|--:|---|--:|--:|--:|--:|--:|
| 5 | 41-60 | 2 | 2 | 3.00 | 1.90 | 0.06 |
| 5 | 61-80 | 3 | 3 | -1.33 | -13.64 | -0.04 |
| 5 | 81-100 | 504 | 5 | -2.03 | -4.30 | -681.74 |
| 15 | 41-60 | 3 | 3 | 11.00 | -0.96 | 0.35 |
| 15 | 61-80 | 4 | 4 | -32.25 | -32.76 | -13.28 |
| 15 | 81-100 | 503 | 5 | -2.15 | -10.68 | -57.46 |
| 30 | 41-60 | 3 | 3 | -14.67 | -25.75 | -0.42 |
| 30 | 61-80 | 6 | 4 | 19.83 | 2.65 | 0.88 |
| 30 | 81-100 | 504 | 5 | -1.84 | -9.77 | -4.49 |
| 45 | 41-60 | 8 | 5 | 21.38 | 18.17 | 1.55 |
| 45 | 61-80 | 5 | 4 | -11.60 | -9.66 | -0.55 |
| 45 | 81-100 | 499 | 5 | -2.33 | -13.40 | -78.35 |

## 3. Untradeable fraction (what closed weather)

| T | strike-T obs | untradeable | fraction | no candle | bid = 0 | median candle age at entry (s, priced) | p90 age (s) |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 5 | 0 | 0 | n/a | 0 | 610 | None | None |
| 15 | 0 | 0 | n/a | 0 | 599 | None | None |
| 30 | 0 | 0 | n/a | 0 | 586 | None | None |
| 45 | 0 | 0 | n/a | 0 | 586 | None | None |

## 4. Anchor (e): tail risk (sold-tail P&L is many small wins and few large losses)

Per cell, over SAMPLED hours only (the sample is a random subset of hours; a full-universe day would hold about 234.7x as many positions, so absolute day losses are understated by roughly that factor). Positions in one hourly event are open simultaneously; different hours do not overlap (T <= 45 < 60), so max simultaneous short exposure per day = largest single-hour sum of (100 - bid) over that day's sold strikes, i.e. collateral at risk, in cents (100c = $1).

| T | bucket | n | worst day (UTC) | worst-day P&L (c) | worst hour P&L (c) | max hour short exposure (c) | max day simultaneous exposure (c) |
|--:|---|--:|---|--:|--:|--:|--:|
| 5 | 1 | 3 | 2026-09-27 | 0 | 0 | 99 | 99 |
| 5 | 2 | 2 | 2026-09-11 | 1 | 1 | 98 | 98 |
| 5 | 3 | 1 | 2026-08-26 | -98 | -98 | 97 | 97 |
| 5 | 4-5 | 0 | None | n/a | n/a | n/a | n/a |
| 5 | 6-10 | 1 | 2026-09-27 | 9 | 9 | 90 | 90 |
| 5 | 11-20 | 2 | 2026-09-11 | 11 | 11 | 88 | 88 |
| 5 | 21-40 | 0 | None | n/a | n/a | n/a | n/a |
| 15 | 1 | 5 | 2026-09-11 | 0 | 0 | 198 | 198 |
| 15 | 2 | 2 | 2026-09-11 | 1 | 1 | 98 | 98 |
| 15 | 3 | 1 | 2026-08-26 | 2 | 2 | 97 | 97 |
| 15 | 4-5 | 1 | 2026-09-27 | 3 | 3 | 96 | 96 |
| 15 | 6-10 | 5 | 2026-10-20 | 5 | 5 | 94 | 94 |
| 15 | 11-20 | 3 | 2026-08-26 | 16 | 16 | 83 | 83 |
| 15 | 21-40 | 2 | 2026-09-11 | 59 | 25 | 73 | 73 |
| 30 | 1 | 5 | 2026-09-27 | 0 | 0 | 99 | 99 |
| 30 | 2 | 5 | 2026-09-27 | 1 | 1 | 98 | 98 |
| 30 | 3 | 0 | None | n/a | n/a | n/a | n/a |
| 30 | 4-5 | 5 | 2026-09-27 | 3 | 3 | 96 | 96 |
| 30 | 6-10 | 4 | 2026-09-27 | 6 | 5 | 94 | 94 |
| 30 | 11-20 | 4 | 2026-09-11 | 13 | 13 | 86 | 86 |
| 30 | 21-40 | 6 | 2026-10-20 | -65 | -65 | 77 | 77 |
| 45 | 1 | 5 | 2026-09-27 | 0 | 0 | 99 | 99 |
| 45 | 2 | 3 | 2026-09-27 | 1 | 1 | 98 | 98 |
| 45 | 3 | 4 | 2026-09-11 | 2 | 2 | 97 | 97 |
| 45 | 4-5 | 3 | 2026-09-11 | 3 | 3 | 96 | 96 |
| 45 | 6-10 | 4 | 2026-10-20 | 5 | 5 | 94 | 94 |
| 45 | 11-20 | 6 | 2026-10-20 | -89 | -89 | 89 | 89 |
| 45 | 21-40 | 5 | 2026-10-20 | -76 | -76 | 74 | 74 |

Book view: ALL longshot sales (bid <= 40c) pooled at each T:

| T | n | days | mean net (c/contract) | total P&L (c) | worst day | worst-day P&L (c) | best day (c) | negative days | mean net excl. worst day (c) | worst hour P&L (c) | max day simult. exposure (c) |
|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| 5 | 9 | 5 | -6.556 | -59 | 2026-08-26 | -98 | 18 | 1 | 4.875 | -98 | 189 |
| 15 | 19 | 5 | 7.789 | 148 | 2026-09-12 | 5 | 73 | 0 | 8.412 | 5 | 378 |
| 30 | 29 | 5 | 6.414 | 186 | 2026-10-20 | -36 | 86 | 1 | 9.652 | -36 | 538 |
| 45 | 30 | 5 | -1.267 | -38 | 2026-10-20 | -157 | 55 | 1 | 4.958 | -157 | 637 |

## 5. Verdict: frozen rule, numbers beside each bar

* Cells meeting the n floor (n >= 400 priced sales AND >= 40 distinct days): **0 of 28** (none).
* PASS cells (all five gates): **0** (none).
* Best longshot cell by equal-weight EV among all populated cells: **T=15, bucket 21-40c**, n=2, 1 days.
  * Gate 1 (EV >= +1.0c both readings): equal-weight 29.50c, volume-weighted 28.93c -> met.
  * Gate 2 (signed day-clustered t >= bar): t = n/a vs bar n/a -> NOT met.
  * Gate 3 (n >= 400 across >= 40 days): n = 2, days = 1 -> NOT met.
  * Gate 4 (untradeable <= 70%): U_T = 53.1% (diagnostic ask-zone: 0.0%) -> met.
  * Gate 5 (>= 50% non-zero entry-candle volume): 100.0% -> met.
  * KILL clause for this cell: 97.9% one-sided upper bound on EV = n/ac vs +0.2c.

KILL clause (every floor-meeting cell must have one-sided 97.9% UB on EV < +0.2c):

| T | bucket | n | days | EV eq-wt | SE | UB 97.9% | < +0.2c |
|--:|---|--:|--:|--:|--:|--:|:--:|
| (no cell meets the n floor: the KILL clause cannot fire) | | | | | | | |

Alternate (secondary) reading of gate 4 with the ask-zone fraction would pass: no cell.

## 6. Anchors (a), (b), (d)

**(a) Executable side.** Static AST scan of this module passed: no subtraction `100 - <expression referencing ask>` exists anywhere; the pricing/P&L functions ['fee_c', 'candle_rows', 'entry_quote', 'price_hour', 'pnl_step', 'bucket_of'] reference no ask identifier at all (the 4th tuple field from `edge_sizing_v2.normalize()` is bound to `_unused`). Sale price = `yes_bid.close_dollars` of the last candle at or before close-T; hand-worked entries below were re-parsed from raw candle JSON independently of `normalize()` and asserted equal to the price used. The raw ask is printed only as a contrast column; it enters no formula.

| ticker | candle end (cutoff = candle end?) | raw yes_bid close | raw yes_ask (not used) | sale price b | fee | result | net if NO = b-fee | net if YES = -(100-b)-fee | realised |
|---|---|--:|--:|--:|--:|---|--:|--:|--:|
| KXBTCD-26SEP1101-T77199.99 | 1789101900 (=) | 0.0900 | 0.1000 | 9 | 1 | no | 8 | -92 | 8 |
| KXBTCD-26SEP1101-T77299.99 | 1789101900 (=) | 0.0100 | 0.0200 | 1 | 1 | no | 0 | -100 | 0 |
| KXBTCD-26SEP2719-T84399.99 | 1790549100 (=) | 0.0900 | 0.1000 | 9 | 1 | no | 8 | -92 | 8 |
| KXBTCD-26SEP2719-T84499.99 | 1790549100 (=) | 0.0400 | 0.0600 | 4 | 1 | no | 3 | -97 | 3 |
| KXBTCD-26SEP1023-T76999.99 | 1789094700 (=) | 0.0600 | 0.0700 | 6 | 1 | no | 5 | -95 | 5 |
| KXBTCD-26SEP1023-T77099.99 | 1789094700 (=) | 0.0200 | 0.0300 | 2 | 1 | no | 1 | -99 | 1 |
| KXBTCD-26OCT2009-T81799.99 | 1792500300 (=) | 0.0600 | 0.0700 | 6 | 1 | no | 5 | -95 | 5 |
| KXBTCD-26OCT2009-T81899.99 | 1792500300 (=) | 0.0200 | 0.0300 | 2 | 1 | no | 1 | -99 | 1 |
| KXBTCD-26OCT2009-T81999.99 | 1792500300 (=) | 0.0100 | 0.0200 | 1 | 1 | no | 0 | -100 | 0 |
| KXBTCD-26SEP1123-T77299.99 | 1789181100 (=) | 0.0600 | 0.0700 | 6 | 1 | no | 5 | -95 | 5 |

**(b) No outcome conditioning.** Fetch writes `ladder.json` (no result field) and `results.json` separately. The pricing pass (`price_hour`, `entry_quote`, `ask_zone_diag`, `fee_c`, `candle_rows`, `bucket_of`, `fetch_hour`) is asserted by AST scan to reference neither `result` nor `results`; results are first loaded after all entries are priced, and joined only in `pnl_step`. Functions checked: ['fee_c', 'candle_rows', 'entry_quote', 'price_hour', 'ask_zone_diag', 'bucket_of', 'fetch_hour']. Every entry was priced before any outcome was loaded. Entry selection is the single frozen rule (last candle at or before close-T); there is no search.

**(d)** spot-check not run.

## 7. Exclusions and sampling

* Sampling: whole hours, seeded shuffle (20261027), saved work_order.json, strict order, never re-sorted. Hours priced 6 / 1408 = 0.4%; completed set is a contiguous prefix of the shuffled order (6 leading hours). Days touched 5 / 60.
* Exclusions in pricing (non -T / non-greater strikes): none.
* Exclusions at P&L step (no official yes/no `result`, counted per strike-T entry): none.
* Untradeable entries (no candle or bid = 0) are kept in every denominator and never priced or back-filled: 2,381 of 4,512 strike-T observations.
* Calendar day = UTC date of close. Universe window: closes 2026-08-22T00:00Z to 2026-10-20T23:59Z (60 days).
* Spec-silent choices fixed before outcomes were read are listed in the docstring of `tail_pricing.py`.
