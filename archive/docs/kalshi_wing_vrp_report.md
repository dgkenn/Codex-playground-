# Kalshi hourly BTC ladder (KXBTCD) — Wing overpricing / VRP test

_Generated 2026-07-16 03:23 UTC_

## Hypothesis
Deep OTM **wing** strikes (entry YES-price in (0, 0.15]) are systematically OVERPRICED, so SELLING them (buying NO) is profitable net of the cent-rounded Kalshi fee.

## Method (anti-look-ahead)
- **Entry** = count-weighted VWAP of yes-price over trades in the FIRST HALF of `[open_time, close_time]` (life fraction <= 0.5); require >= 2 early trades or SKIP.
- **Result** taken only from settlement (`result` yes/no), cleanly separate from entry window.
- Only markets with `volume_fp > 0` are queried for trades (others cannot yield an early VWAP).
- Fee per contract = `max(0.01, ceil(0.07*p*(1-p)*100)/100)` at the executed price.
- Day-clustered t-stats cluster by event **close-DATE** (cluster-robust SE of the mean).
- OOS split by close_time: earliest 70% events -> TRAIN, latest 30% -> TEST.

## Sample achieved
- Events processed: **330**
- Total obs (>=2 early trades, any moneyness): **8169**
- Distinct close-dates (all obs): **55**  |  span: 2026-05-22 .. 2026-07-15
- **WING obs (entry in (0,0.15]): 2775** across **55** dates
- Deep-ITM obs (entry >= 0.85): 3594 across 55 dates
- TRAIN events 231 / TEST events 99

## Calibration (all obs) — realized YES rate vs entry price
Longshot overpricing = realized < entry in the low bins (negative realized-entry).

| entry bin | n | dates | mean entry | realized YES | realized-entry | clustered t |
|---|---|---|---|---|---|---|
| (0.00,0.02] | 1259 | 55 | 0.0129 | 0.0008 | -0.0121 | -15.45 |
| (0.02,0.04] | 589 | 55 | 0.0287 | 0.0085 | -0.0203 | -4.67 |
| (0.04,0.06] | 290 | 54 | 0.0490 | 0.0138 | -0.0352 | -5.23 |
| (0.06,0.08] | 210 | 55 | 0.0689 | 0.0286 | -0.0404 | -3.72 |
| (0.08,0.10] | 158 | 50 | 0.0894 | 0.0443 | -0.0451 | -2.91 |
| (0.10,0.15] | 269 | 55 | 0.1231 | 0.0632 | -0.0599 | -3.95 |
| (0.15,0.25] | 317 | 55 | 0.1977 | 0.0915 | -0.1062 | -6.14 |
| (0.25,0.40] | 360 | 54 | 0.3192 | 0.2056 | -0.1136 | -4.86 |
| (0.40,0.60] | 478 | 55 | 0.4980 | 0.4289 | -0.0692 | -2.69 |
| (0.60,0.75] | 340 | 55 | 0.6755 | 0.7118 | +0.0363 | +1.39 |
| (0.75,0.85] | 305 | 55 | 0.8044 | 0.8918 | +0.0874 | +4.94 |
| (0.85,0.90] | 250 | 54 | 0.8779 | 0.9240 | +0.0461 | +2.74 |
| (0.90,0.94] | 332 | 55 | 0.9216 | 0.9639 | +0.0423 | +3.82 |
| (0.94,0.96] | 296 | 55 | 0.9505 | 0.9764 | +0.0258 | +2.70 |
| (0.96,1.00] | 2716 | 55 | 0.9844 | 0.9989 | +0.0145 | +16.53 |

## Tradeable OOS — PnL per contract (dollars), day-clustered by close-date
SELL YES on wings (profit if it stays OTM). BUY YES on deep-ITM. `vwap` executes at the entry VWAP; `vwap-1c` pays a conservative 1c half-spread.

### WING SELL - TRAIN
| variant | mean PnL/contract | clustered t | n obs | n dates |
|---|---|---|---|---|
| gross (vwap) | +0.0258 | +6.65 | 1982 | 39 |
| gross (vwap-1c) | +0.0158 | +4.07 | 1982 | 39 |
| net (vwap) | +0.0158 | +4.07 | 1982 | 39 |
| net (vwap-1c) | +0.0058 | +1.49 | 1982 | 39 |

### WING SELL - TEST
| variant | mean PnL/contract | clustered t | n obs | n dates |
|---|---|---|---|---|
| gross (vwap) | +0.0227 | +3.26 | 793 | 17 |
| gross (vwap-1c) | +0.0127 | +1.83 | 793 | 17 |
| net (vwap) | +0.0127 | +1.83 | 793 | 17 |
| net (vwap-1c) | +0.0027 | +0.39 | 793 | 17 |

### ITM BUY - TRAIN
| variant | mean PnL/contract | clustered t | n obs | n dates |
|---|---|---|---|---|
| gross (vwap) | +0.0195 | +5.40 | 2605 | 39 |
| gross (vwap-1c) | +0.0095 | +2.63 | 2605 | 39 |
| net (vwap) | +0.0095 | +2.63 | 2605 | 39 |
| net (vwap-1c) | -0.0005 | -0.15 | 2605 | 39 |

### ITM BUY - TEST
| variant | mean PnL/contract | clustered t | n obs | n dates |
|---|---|---|---|---|
| gross (vwap) | +0.0222 | +6.51 | 989 | 17 |
| gross (vwap-1c) | +0.0122 | +3.58 | 989 | 17 |
| net (vwap) | +0.0122 | +3.58 | 989 | 17 |
| net (vwap-1c) | +0.0022 | +0.65 | 989 | 17 |

## VERDICT
- Power: 2775 wing obs / 55 dates (MEETS the >=1500 obs & >=40 dates target).
- Gross wing-sell (no fee), TEST: mean +0.0227/contract, t=+3.26 — shows the raw edge before costs.
- Net wing-sell (1c spread), TRAIN: mean +0.0058, t=+1.49; TEST: mean +0.0027, t=+0.39.
- Net wing-sell (no spread), TRAIN: mean +0.0158, t=+4.07; TEST: mean +0.0127, t=+1.83.

**NULL (tradeable), but a strong, real overpricing exists in the raw prices.**

Nuance — read the numbers, not just the label:
1. **The overpricing is real and well-powered.** Every wing bin (0,0.15] has realized YES rate far below the entry price, with large negative day-clustered t (e.g. (0.10,0.15]: entry 0.1231 vs realized 0.0632, -0.0599, t=-3.95; (0.00,0.02]: -0.0121, t=-15.4). This is a textbook favorite-longshot / VRP tilt, and it is symmetric: deep-ITM favorites are *under*priced (realized > entry, positive t). 2775 wing obs / 55 dates — not a thin-cluster artifact.
2. **The Kalshi fee alone does NOT kill it.** Because p≈0 in the wings, the rounded fee is ~1c. Net of fee at the VWAP the wing-sell is +0.0158/contract (t=+4.07) in TRAIN and +0.0127 (t=+1.83) in TEST — the fee removes only ~1c.
3. **What kills it is execution, not the fee.** Adding a conservative 1c half-spread (you must SELL yes, i.e. buy NO, at a worse price than the VWAP) knocks TRAIN to +0.0058 (t=+1.49) and TEST to +0.0027 (t=+0.39). And even fee-only, TEST significance is already marginal (t=1.83 < 2).

Bottom line: there is a genuine, robustly-measured wing-overpricing signal on the hourly BTC ladder, and it survives the rounded fee at the mid/VWAP — but it does **not** clear a >2 day-clustered t out-of-sample once you pay a realistic 1c spread to get filled. So it is **not** a demonstrably tradeable, fee-and-spread-surviving edge on this sample. Whether it is exploitable hinges entirely on execution: capturing better-than-VWAP fills (resting NO bids rather than lifting) is the whole game, and this study cannot prove that is achievable.
