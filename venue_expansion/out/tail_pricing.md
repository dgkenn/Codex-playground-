# Tail pricing: are Kalshi BTC-hourly longshots overpriced?  (TAIL_PRICING_SPEC.md, executed)

**VERDICT: INSUFFICIENT**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 5)

Sample: 503 of 1408 hourly events (35.7%), 60 of 60 UTC days; 92,560 strikes, 370,240 strike-T observations, 199,178 priced sales (all buckets).

## 0. Plain reading (written after the run; numbers are from the tables below)

* **Calibrated, not overpriced.** Of 28 longshot cells (7 buckets x 4 T) the mean executable bid lies inside the realised-rate Wilson 95% CI in 27; the one exception is T=30, 6-10c (rate 3.94% vs bid 7.83c). There is no monotone favourite-longshot gap: signs of (rate - bid) flip across buckets and across T.
* **No cell clears EV or the Bonferroni bar.** Best t anywhere is +2.15 (T=30, 6-10c, EV +2.89c, n=330 < 400 floor, bar 3.27); its neighbours in T are +1.58c (T=15), -0.18c (T=45), -2.96c (T=5), i.e. consistent with noise. Pooled over all sales at bid <= 40c, mean net is negative at every T (-1.16, -0.17, -0.69, -1.13 c/contract at T=5/15/30/45).
* **The 1c fee is the whole edge.** ceil(7p(1-p)) = 1c for any bid up to 17c, so selling at 1c can never net more than 0 (NO) and selling at 2-3c nets at most 1-2c against a 98-100c loss.
* **Untradeable fraction is ~45-48% of strike-T observations, all of it yes_bid = 0 (zero 'no candle').** It is concentrated in the dead tail: among strikes whose last ask is 1c, 100% have bid 0; at ask 2c 11-37%; at ask 3c 0-13%; above that under 5%. The 95% untradeable pattern that closed weather does NOT replicate beyond the 1c tail here; the ladder has real two-sided quotes from 2c up.
* **Verdict is INSUFFICIENT, and it is structural, not a coverage shortfall.** The frozen KILL clause needs a 97.9% upper bound < +0.2c in every n>=400 cell; cells at 6-40c have a day-clustered SE of 1.5-2.6c (binary payoff of +b vs -(100-b)), so even at 100% coverage (SE shrinks by ~sqrt(0.357) = 0.6x) the bound stays above +0.2c (e.g. T=45, 6-10c: -0.18 + 2.1 x 0.9 ~ 1.7c). The clause is practically unfireable above ~5c. In substance: no evidence of exploitable overpricing, point estimates are negative, and no PASS was close.
* **Mirror observation (outside the frozen family, untested as a strategy):** at bid >= 81c the realised YES rate exceeds the bid by ~1.0c in every T (99.77-99.95% vs ~98.9c), so SELLING favourites loses ~2c/contract (t about -55 to -180). That is the other side of the same book; testing a BUY of YES would require the ask and was not run here.
* **Caveats:** 35.7% of hours (503 of 1408; all 60 days covered) -- the stop was a wall-clock budget fixed before looking at results, API throughput was ~3-6 hours/minute-block under 429s. Entry uses the literal 'last candle at or before close-T' rule; candles are sparse for quiet strikes so the median candle age is 60s but p90 is 540-1140s, i.e. some quotes are up to ~19 min old; staleness sensitivity was not run (no filter is permitted). A 6-hour smoke test of the pipeline (first rows of the calibration printed, ~2k entries) was run before the full fetch; nothing in the code changed in response to it other than report formatting.

## 1. Anchor (c): calibration table (reported whatever the verdict)

Realised YES rate with Wilson 95% CI, against the executable `yes_bid` the seller receives. `gap` = realised rate minus mean bid, in cents of probability: **gap < 0 means the market overprices YES (selling is favourable before fee)**. CIs treat strikes as independent (they are not: one BTC move hits every strike of an hour), so they are too narrow; the day-clustered t in section 2 is the gate.


### T = 5 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 212 | 2 | 0.94% | [0.26%, 3.37%] | 1.00c | -0.06 | yes |
| 2c | 89 | 0 | 0.00% | [0.00%, 4.14%] | 2.00c | -2.00 | yes |
| 3c | 59 | 2 | 3.39% | [0.93%, 11.54%] | 3.00c | +0.39 | yes |
| 4-5c | 87 | 3 | 3.45% | [1.18%, 9.65%] | 4.31c | -0.86 | yes |
| 6-10c | 110 | 11 | 10.00% | [5.68%, 17.02%] | 8.04c | +1.96 | yes |
| 11-20c | 116 | 13 | 11.21% | [6.67%, 18.23%] | 15.36c | -4.16 | yes |
| 21-40c | 169 | 54 | 31.95% | [25.39%, 39.32%] | 29.31c | +2.64 | yes |
| 41-60c (not a longshot; report only) | 139 | 78 | 56.12% | [47.81%, 64.09%] | 49.94c | +6.17 | yes |
| 61-80c (not a longshot; report only) | 153 | 113 | 73.86% | [66.37%, 80.17%] | 71.60c | +2.25 | yes |
| 81-100c (not a longshot; report only) | 47,400 | 47,375 | 99.95% | [99.92%, 99.96%] | 98.93c | +1.02 | NO |

### T = 15 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 400 | 2 | 0.50% | [0.14%, 1.80%] | 1.00c | -0.50 | yes |
| 2c | 175 | 2 | 1.14% | [0.31%, 4.07%] | 2.00c | -0.86 | yes |
| 3c | 149 | 4 | 2.68% | [1.05%, 6.70%] | 3.00c | -0.32 | yes |
| 4-5c | 158 | 6 | 3.80% | [1.75%, 8.04%] | 4.45c | -0.65 | yes |
| 6-10c | 234 | 12 | 5.13% | [2.96%, 8.75%] | 7.71c | -2.58 | yes |
| 11-20c | 250 | 39 | 15.60% | [11.63%, 20.61%] | 15.15c | +0.45 | yes |
| 21-40c | 322 | 88 | 27.33% | [22.75%, 32.44%] | 29.83c | -2.50 | yes |
| 41-60c (not a longshot; report only) | 255 | 131 | 51.37% | [45.26%, 57.44%] | 50.57c | +0.80 | yes |
| 61-80c (not a longshot; report only) | 333 | 250 | 75.08% | [70.16%, 79.42%] | 70.91c | +4.16 | yes |
| 81-100c (not a longshot; report only) | 47,176 | 47,119 | 99.88% | [99.84%, 99.91%] | 98.85c | +1.03 | NO |

### T = 30 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 602 | 5 | 0.83% | [0.36%, 1.93%] | 1.00c | -0.17 | yes |
| 2c | 297 | 5 | 1.68% | [0.72%, 3.88%] | 2.00c | -0.32 | yes |
| 3c | 178 | 5 | 2.81% | [1.21%, 6.41%] | 3.00c | -0.19 | yes |
| 4-5c | 270 | 11 | 4.07% | [2.29%, 7.15%] | 4.45c | -0.37 | yes |
| 6-10c | 330 | 13 | 3.94% | [2.32%, 6.62%] | 7.83c | -3.89 | NO |
| 11-20c | 377 | 58 | 15.38% | [12.09%, 19.37%] | 14.86c | +0.53 | yes |
| 21-40c | 470 | 141 | 30.00% | [26.03%, 34.29%] | 29.85c | +0.15 | yes |
| 41-60c (not a longshot; report only) | 407 | 196 | 48.16% | [43.34%, 53.01%] | 50.82c | -2.66 | yes |
| 61-80c (not a longshot; report only) | 474 | 339 | 71.52% | [67.30%, 75.40%] | 71.32c | +0.19 | yes |
| 81-100c (not a longshot; report only) | 46,975 | 46,872 | 99.78% | [99.73%, 99.82%] | 98.78c | +1.00 | NO |

### T = 45 minutes before close

| bucket (bid) | n priced | YES | realised YES rate | Wilson 95% CI | mean bid | gap (rate-bid, c) | bid inside CI |
|---|---:|---:|---:|---|---:|---:|:--:|
| 1c | 654 | 9 | 1.38% | [0.73%, 2.59%] | 1.00c | +0.38 | yes |
| 2c | 292 | 7 | 2.40% | [1.17%, 4.86%] | 2.00c | +0.40 | yes |
| 3c | 231 | 10 | 4.33% | [2.37%, 7.78%] | 3.00c | +1.33 | yes |
| 4-5c | 303 | 15 | 4.95% | [3.02%, 8.01%] | 4.41c | +0.54 | yes |
| 6-10c | 431 | 30 | 6.96% | [4.92%, 9.76%] | 7.78c | -0.82 | yes |
| 11-20c | 471 | 67 | 14.23% | [11.36%, 17.67%] | 15.16c | -0.93 | yes |
| 21-40c | 565 | 167 | 29.56% | [25.94%, 33.45%] | 30.18c | -0.62 | yes |
| 41-60c (not a longshot; report only) | 502 | 256 | 51.00% | [46.63%, 55.34%] | 50.57c | +0.42 | yes |
| 61-80c (not a longshot; report only) | 606 | 437 | 72.11% | [68.41%, 75.53%] | 71.24c | +0.87 | yes |
| 81-100c (not a longshot; report only) | 46,757 | 46,649 | 99.77% | [99.72%, 99.81%] | 98.73c | +1.04 | NO |

## 2. EV table per cell (selling 1 YES at `yes_bid`, fee-inclusive, cents per contract)

Bonferroni: 28 comparisons, two-sided alpha = 0.00179, bar = Student-t quantile at p = 0.99911 on df = (distinct days - 1). t is signed and day-clustered (equal-weight). `U_T` = entry-time-level untradeable fraction (primary gate-4 reading). `U_ask` = diagnostic: share with bid=0 among strikes whose last-candle ask falls in the bucket range. `nz-vol` = share of priced entries with non-zero volume in the entry candle.

| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) | bar | t (vol) | t (hour-clust) | UB97.9% | U_T | U_ask | nz-vol | PASS gates 1/2/3/4/5 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| 5 | 1 | 212 | 60 | -0.94 | -0.68 | -1.43 | 3.27 | -1.21 | -1.42 | 0.43 | 47.6% | 100.0% | 99.5% | n/n/n/Y/Y |
| 5 | 2 | 89 | 50 | 1.00 | 1.00 | n/a | 3.30 | n/a | n/a | 1.00 | 47.6% | 10.7% | 100.0% | Y/n/n/Y/Y |
| 5 | 3 | 59 | 36 | -1.39 | -1.31 | -0.60 | 3.38 | -0.54 | -0.58 | 3.49 | 47.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 5 | 4-5 | 87 | 40 | -0.14 | 0.31 | -0.07 | 3.35 | 0.17 | -0.07 | 3.96 | 47.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 5 | 6-10 | 110 | 52 | -2.96 | 0.56 | -1.10 | 3.30 | 0.26 | -1.03 | 2.65 | 47.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 5 | 11-20 | 116 | 51 | 2.91 | 1.39 | 0.92 | 3.30 | 0.38 | 1.01 | 9.54 | 47.6% | 0.0% | 100.0% | Y/n/n/Y/Y |
| 5 | 21-40 | 169 | 53 | -4.64 | -7.18 | -1.23 | 3.29 | -1.67 | -1.30 | 3.21 | 47.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 15 | 1 | 400 | 60 | -0.50 | -0.14 | -1.42 | 3.27 | -1.19 | -1.41 | 0.23 | 46.6% | 100.0% | 84.2% | n/n/Y/Y/Y |
| 15 | 2 | 175 | 58 | -0.14 | -2.72 | -0.18 | 3.28 | -1.05 | -0.18 | 1.54 | 46.6% | 22.7% | 96.0% | n/n/n/Y/Y |
| 15 | 3 | 149 | 55 | -0.68 | 0.74 | -0.52 | 3.29 | 1.05 | -0.52 | 2.08 | 46.6% | 3.1% | 100.0% | n/n/n/Y/Y |
| 15 | 4-5 | 158 | 58 | -0.35 | 0.07 | -0.23 | 3.28 | 0.05 | -0.23 | 2.82 | 46.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 15 | 6-10 | 234 | 59 | 1.58 | -1.24 | 1.06 | 3.27 | -0.37 | 1.09 | 4.66 | 46.6% | 0.7% | 100.0% | n/n/n/Y/Y |
| 15 | 11-20 | 250 | 59 | -1.73 | 0.97 | -0.73 | 3.27 | 0.38 | -0.72 | 3.23 | 46.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 15 | 21-40 | 322 | 60 | 0.50 | 1.94 | 0.17 | 3.27 | 0.50 | 0.19 | 6.73 | 46.6% | 0.0% | 100.0% | n/n/n/Y/Y |
| 30 | 1 | 602 | 60 | -0.83 | -0.20 | -2.00 | 3.27 | -0.99 | -1.89 | 0.03 | 45.6% | 100.0% | 68.3% | n/n/Y/Y/Y |
| 30 | 2 | 297 | 60 | -0.68 | -6.97 | -0.98 | 3.27 | -1.35 | -0.92 | 0.77 | 45.6% | 32.4% | 83.2% | n/n/n/Y/Y |
| 30 | 3 | 178 | 57 | -0.81 | -0.81 | -0.70 | 3.28 | -0.44 | -0.65 | 1.60 | 45.6% | 6.7% | 89.9% | n/n/n/Y/Y |
| 30 | 4-5 | 270 | 60 | -0.63 | -5.21 | -0.52 | 3.27 | -1.14 | -0.48 | 1.89 | 45.6% | 3.1% | 94.1% | n/n/n/Y/Y |
| 30 | 6-10 | 330 | 59 | 2.89 | 5.44 | 2.15 | 3.27 | 8.32 | 2.36 | 5.69 | 45.6% | 3.4% | 99.1% | Y/n/n/Y/Y |
| 30 | 11-20 | 377 | 60 | -1.75 | -6.04 | -0.95 | 3.27 | -1.60 | -0.87 | 2.06 | 45.6% | 0.0% | 99.5% | n/n/n/Y/Y |
| 30 | 21-40 | 470 | 60 | -2.15 | -6.89 | -0.82 | 3.27 | -1.89 | -0.89 | 3.27 | 45.6% | 0.2% | 100.0% | n/n/Y/Y/Y |
| 45 | 1 | 654 | 60 | -1.38 | -0.25 | -2.44 | 3.27 | -1.06 | -2.52 | -0.21 | 45.1% | 100.0% | 59.5% | n/n/Y/Y/Y |
| 45 | 2 | 292 | 60 | -1.40 | -2.75 | -1.47 | 3.27 | -1.30 | -1.56 | 0.58 | 45.1% | 37.2% | 79.5% | n/n/n/Y/Y |
| 45 | 3 | 231 | 57 | -2.33 | -0.75 | -1.81 | 3.28 | -0.60 | -1.73 | 0.36 | 45.1% | 12.6% | 82.3% | n/n/n/Y/Y |
| 45 | 4-5 | 303 | 60 | -1.54 | 0.68 | -1.10 | 3.27 | 0.75 | -1.16 | 1.38 | 45.1% | 1.4% | 93.4% | n/n/n/Y/Y |
| 45 | 6-10 | 431 | 60 | -0.18 | 1.98 | -0.12 | 3.27 | 1.40 | -0.13 | 2.86 | 45.1% | 4.6% | 96.8% | n/n/Y/Y/Y |
| 45 | 11-20 | 471 | 60 | -0.34 | 1.55 | -0.19 | 3.27 | 0.86 | -0.19 | 3.38 | 45.1% | 0.2% | 99.6% | n/n/Y/Y/Y |
| 45 | 21-40 | 565 | 60 | -1.38 | 0.65 | -0.62 | 3.27 | 0.19 | -0.60 | 3.23 | 45.1% | 0.5% | 100.0% | n/n/Y/Y/Y |

Above-40c buckets (reported, cannot PASS):

| T | bucket | n | days | EV eq-wt | EV vol-wt | t (eq) |
|--:|---|--:|--:|--:|--:|--:|
| 5 | 41-60 | 139 | 52 | -8.17 | -9.30 | -1.96 |
| 5 | 61-80 | 153 | 55 | -4.25 | -3.85 | -1.04 |
| 5 | 81-100 | 47,400 | 60 | -2.02 | -3.25 | -179.68 |
| 15 | 41-60 | 255 | 57 | -2.80 | -1.44 | -0.84 |
| 15 | 61-80 | 333 | 60 | -6.16 | -8.35 | -2.36 |
| 15 | 81-100 | 47,176 | 60 | -2.03 | -2.20 | -104.26 |
| 30 | 41-60 | 407 | 60 | 0.66 | -1.30 | 0.23 |
| 30 | 61-80 | 474 | 60 | -2.19 | -5.25 | -0.82 |
| 30 | 81-100 | 46,975 | 60 | -2.01 | -1.36 | -62.28 |
| 45 | 41-60 | 502 | 60 | -2.42 | -3.18 | -0.85 |
| 45 | 61-80 | 606 | 60 | -2.87 | -1.56 | -1.40 |
| 45 | 81-100 | 46,757 | 60 | -2.04 | -4.31 | -54.05 |

## 3. Untradeable fraction (what closed weather)

| T | strike-T obs | untradeable | fraction | no candle | bid = 0 | median candle age at entry (s, priced) | p90 age (s) |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 5 | 92,560 | 44,026 | 47.6% | 0 | 44,026 | 60 | 1140 |
| 15 | 92,560 | 43,108 | 46.6% | 0 | 43,108 | 60 | 1080 |
| 30 | 92,560 | 42,180 | 45.6% | 0 | 42,180 | 60 | 1080 |
| 45 | 92,560 | 41,748 | 45.1% | 0 | 41,748 | 60 | 540 |

## 4. Anchor (e): tail risk (sold-tail P&L is many small wins and few large losses)

Per cell, over SAMPLED hours only (the sample is a random subset of hours; a full-universe day would hold about 2.8x as many positions, so absolute day losses are understated by roughly that factor). Positions in one hourly event are open simultaneously; different hours do not overlap (T <= 45 < 60), so max simultaneous short exposure per day = largest single-hour sum of (100 - bid) over that day's sold strikes, i.e. collateral at risk, in cents (100c = $1).

| T | bucket | n | worst day (UTC) | worst-day P&L (c) | worst hour P&L (c) | max hour short exposure (c) | max day simultaneous exposure (c) |
|--:|---|--:|---|--:|--:|--:|--:|
| 5 | 1 | 212 | 2026-10-11 | -100 | -100 | 396 | 396 |
| 5 | 2 | 89 | 2026-09-20 | 1 | 1 | 196 | 196 |
| 5 | 3 | 59 | 2026-08-26 | -96 | -98 | 97 | 97 |
| 5 | 4-5 | 87 | 2026-09-14 | -94 | -97 | 96 | 96 |
| 5 | 6-10 | 110 | 2026-08-24 | -94 | -95 | 94 | 94 |
| 5 | 11-20 | 116 | 2026-08-25 | -212 | -88 | 89 | 89 |
| 5 | 21-40 | 169 | 2026-08-25 | -240 | -81 | 139 | 139 |
| 15 | 1 | 400 | 2026-10-11 | -100 | -100 | 495 | 495 |
| 15 | 2 | 175 | 2026-09-03 | -98 | -99 | 196 | 196 |
| 15 | 3 | 149 | 2026-10-20 | -96 | -98 | 194 | 194 |
| 15 | 4-5 | 158 | 2026-09-18 | -97 | -97 | 191 | 191 |
| 15 | 6-10 | 234 | 2026-09-22 | -162 | -95 | 185 | 185 |
| 15 | 11-20 | 250 | 2026-09-03 | -218 | -172 | 175 | 175 |
| 15 | 21-40 | 322 | 2026-09-11 | -283 | -153 | 212 | 212 |
| 30 | 1 | 602 | 2026-08-25 | -200 | -200 | 693 | 693 |
| 30 | 2 | 297 | 2026-08-24 | -96 | -99 | 392 | 392 |
| 30 | 3 | 178 | 2026-08-24 | -96 | -98 | 194 | 194 |
| 30 | 4-5 | 270 | 2026-09-11 | -167 | -193 | 288 | 288 |
| 30 | 6-10 | 330 | 2026-08-24 | -252 | -188 | 460 | 460 |
| 30 | 11-20 | 377 | 2026-09-11 | -241 | -259 | 256 | 256 |
| 30 | 21-40 | 470 | 2026-09-03 | -361 | -220 | 285 | 285 |
| 45 | 1 | 654 | 2026-09-11 | -200 | -200 | 792 | 792 |
| 45 | 2 | 292 | 2026-08-25 | -190 | -99 | 294 | 294 |
| 45 | 3 | 231 | 2026-08-25 | -178 | -98 | 291 | 291 |
| 45 | 4-5 | 303 | 2026-08-24 | -280 | -193 | 286 | 286 |
| 45 | 6-10 | 431 | 2026-08-25 | -298 | -186 | 369 | 369 |
| 45 | 11-20 | 471 | 2026-08-25 | -274 | -174 | 344 | 344 |
| 45 | 21-40 | 565 | 2026-08-25 | -464 | -289 | 281 | 281 |

Book view: ALL longshot sales (bid <= 40c) pooled at each T:

| T | n | days | mean net (c/contract) | total P&L (c) | worst day | worst-day P&L (c) | best day (c) | negative days | mean net excl. worst day (c) | worst hour P&L (c) | max day simult. exposure (c) |
|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| 5 | 842 | 60 | -1.160 | -977 | 2026-08-25 | -625 | 187 | 26 | -0.433 | -184 | 740 |
| 15 | 1,688 | 60 | -0.168 | -283 | 2026-09-22 | -543 | 585 | 30 | 0.157 | -434 | 1288 |
| 30 | 2,524 | 60 | -0.685 | -1728 | 2026-08-24 | -771 | 659 | 30 | -0.386 | -688 | 1815 |
| 45 | 2,947 | 60 | -1.129 | -3328 | 2026-08-25 | -1573 | 590 | 31 | -0.614 | -826 | 1912 |

## 5. Verdict: frozen rule, numbers beside each bar

* Cells meeting the n floor (n >= 400 priced sales AND >= 40 distinct days): **7 of 28** (15|1, 30|1, 30|21-40, 45|1, 45|6-10, 45|11-20, 45|21-40).
* PASS cells (all five gates): **0** (none).
* Best longshot cell by equal-weight EV among floor-meeting cells: **T=45, bucket 6-10c**, n=431, 60 days.
  * Gate 1 (EV >= +1.0c both readings): equal-weight -0.18c, volume-weighted 1.98c -> NOT met.
  * Gate 2 (signed day-clustered t >= bar): t = -0.12 vs bar 3.27 -> NOT met.
  * Gate 3 (n >= 400 across >= 40 days): n = 431, days = 60 -> met.
  * Gate 4 (untradeable <= 70%): U_T = 45.1% (diagnostic ask-zone: 4.6%) -> met.
  * Gate 5 (>= 50% non-zero entry-candle volume): 96.8% -> met.
  * KILL clause for this cell: 97.9% one-sided upper bound on EV = 2.86c vs +0.2c.

KILL clause (every floor-meeting cell must have one-sided 97.9% UB on EV < +0.2c):

| T | bucket | n | days | EV eq-wt | SE | UB 97.9% | < +0.2c |
|--:|---|--:|--:|--:|--:|--:|:--:|
| 15 | 1 | 400 | 60 | -0.50 | 0.352 | 0.23 | NO |
| 30 | 1 | 602 | 60 | -0.83 | 0.415 | 0.03 | yes |
| 30 | 21-40 | 470 | 60 | -2.15 | 2.604 | 3.27 | NO |
| 45 | 1 | 654 | 60 | -1.38 | 0.563 | -0.21 | yes |
| 45 | 6-10 | 431 | 60 | -0.18 | 1.462 | 2.86 | NO |
| 45 | 11-20 | 471 | 60 | -0.34 | 1.791 | 3.38 | NO |
| 45 | 21-40 | 565 | 60 | -1.38 | 2.217 | 3.23 | NO |

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

**(d) Settlement provenance.** Official `result` field only (never self-computed). Spot-check: 40 randomly chosen strikes (seeded) re-read via `GET /markets/{ticker}`: **0 mismatches**.

## 7. Exclusions and sampling

* Sampling: whole hours, seeded shuffle (20261027), saved work_order.json, strict order, never re-sorted. Hours priced 503 / 1408 = 35.7%; completed set is a contiguous prefix of the shuffled order (503 leading hours). Days touched 60 / 60.
* Exclusions in pricing (non -T / non-greater strikes): none.
* Exclusions at P&L step (no official yes/no `result`, counted per strike-T entry): none.
* Untradeable entries (no candle or bid = 0) are kept in every denominator and never priced or back-filled: 171,062 of 370,240 strike-T observations.
* Calendar day = UTC date of close. Universe window: closes 2026-08-22T00:00Z to 2026-10-20T23:59Z (60 days).
* Spec-silent choices fixed before outcomes were read are listed in the docstring of `tail_pricing.py`.
