# Cross-underlying weekly short-vol / longshot premium — does it STACK?

_As-of 2026-07-18. Confirmed edge: SELL BTC/ETH weekly 'above \$X on <date>' YES longshots at p in [0.15,0.3] -> +0.12/ct (week-clustered t~4.6). This tests EXTENSION to other underlyings' weekly ladders. Primary entry = 144h (6d) before close (deep first-half of the 7-day life = genuine far-OTM longshots). Haircut mid->bid = 0.01 (~1c measured half-spread); zero-fee headline (matches ref) + fee 0.07*p*(1-p) sensitivity. Week-clustered t = cluster on ISO resolution week._

**Universe discovery:** Only **BTC, ETH, SOL, XRP** carry the Polymarket `<coin>-above-on-<date>` weekly ladder (11 strikes, 7-day life, Binance noon-ET close). **DOGE** = only 5m/15m up-down micro-markets (no ladder). ADA/AVAX/LINK/BNB/DOT/LTC/TRON/SUI/TON and non-crypto probes (SP500/NASDAQ/gold/TSLA/NVDA) = **no settled weekly ladders**. => reference = BTC, ETH; **new tested underlyings = SOL, XRP**.

**Data:** 224 settled weekly ladders (2026-05-22..2026-07-17, one resolves per calendar day), 1320 strike-markets priced.

## Per-underlying band edge (primary horizon, week-clustered)

| underlying | n | wks | entry | realized YES | overpriced? | win% | mean(mid) | t | exe-1c | t | exe+fee | t | worst wk | vs +0.12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC (REF) | 15 | 4 | 0.228 | 0.267 | no | 0.73 | **-0.039** | -0.34 | -0.049 | -0.43 | -0.068 | -0.59 | -0.398 | -0.33x |
| ETH (REF) | 19 | 4 | 0.205 | 0.263 | no | 0.74 | **-0.058** | -0.46 | -0.068 | -0.54 | -0.084 | -0.66 | -0.314 | -0.48x |
| SOL | 8 | 4 | 0.225 | 0.375 | no | 0.62 | **-0.150** | -0.80 | -0.160 | -0.85 | -0.178 | -0.95 | -0.448 | -1.25x |
| XRP | 14 | 4 | 0.230 | 0.286 | no | 0.71 | **-0.056** | -0.37 | -0.066 | -0.43 | -0.086 | -0.56 | -0.269 | -0.47x |

_'overpriced?'=YES means realized YES hit-rate < entry price (the seller's edge). 'vs +0.12' = mid mean as a multiple of the confirmed BTC/ETH weekly edge. exe+fee = executable (mid-1c) net of 0.07*p(1-p) taker fee._

## Horizon sensitivity (mid seller PnL/ct, week-clustered t)

| underlying | 144h | 120h | 96h |
|---|---|---|---|
| BTC | -0.039 (t=-0.3, n=15) | 0.079 (t=1.0, n=19) | 0.015 (t=0.2, n=19) |
| ETH | -0.058 (t=-0.5, n=19) | 0.004 (t=0.0, n=15) | -0.022 (t=-0.1, n=9) |
| SOL | -0.150 (t=-0.8, n=8) | -0.167 (t=-0.3, n=5) | -0.081 (t=-0.3, n=6) |
| XRP | -0.056 (t=-0.4, n=14) | -0.059 (t=-0.4, n=15) | 0.014 (t=0.1, n=11) |

## Calibration by price bucket at 144h (ALL strikes, high-power)

_edge = realized - entry (edge<0 => overpriced => seller gross-profits); sellPnL = entry - realized._

**BTC**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 34 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 26.48 |
| 0.05-0.10 | 14 | 4 | 0.073 | 0.000 | -0.073 | 0.073 | 34.73 |
| 0.10-0.15 | 11 | 4 | 0.129 | 0.091 | -0.038 | 0.038 | 0.41 |
| 0.15-0.30 | 15 | 4 | 0.228 | 0.267 | 0.039 | -0.039 | -0.34 |
| 0.30-0.50 | 19 | 4 | 0.399 | 0.526 | 0.127 | -0.127 | -0.80 |
| 0.50-0.70 | 17 | 4 | 0.588 | 0.529 | -0.058 | 0.058 | 0.25 |
| 0.70-0.90 | 32 | 4 | 0.808 | 0.844 | 0.035 | -0.035 | -0.26 |

**ETH**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 25 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 50.31 |
| 0.05-0.10 | 9 | 4 | 0.070 | 0.111 | 0.041 | -0.041 | -0.35 |
| 0.10-0.15 | 6 | 3 | 0.135 | 0.333 | 0.198 | -0.198 | -2.08 |
| 0.15-0.30 | 17 | 4 | 0.211 | 0.294 | 0.083 | -0.083 | -0.60 |
| 0.30-0.50 | 16 | 4 | 0.447 | 0.562 | 0.115 | -0.115 | -1.12 |
| 0.50-0.70 | 11 | 4 | 0.609 | 0.545 | -0.063 | 0.063 | 0.22 |
| 0.70-0.90 | 21 | 4 | 0.808 | 0.905 | 0.097 | -0.097 | -1.72 |

**SOL**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 42 | 4 | 0.028 | 0.000 | -0.028 | 0.028 | 52.54 |
| 0.05-0.10 | 5 | 3 | 0.083 | 0.400 | 0.317 | -0.317 | -0.87 |
| 0.10-0.15 | 7 | 4 | 0.121 | 0.143 | 0.021 | -0.021 | -0.12 |
| 0.15-0.30 | 8 | 4 | 0.225 | 0.375 | 0.150 | -0.150 | -0.80 |
| 0.30-0.50 | 24 | 4 | 0.454 | 0.292 | -0.162 | 0.162 | 4.30 |
| 0.50-0.70 | 27 | 4 | 0.555 | 0.741 | 0.186 | -0.186 | -1.59 |
| 0.70-0.90 | 5 | 4 | 0.830 | 1.000 | 0.170 | -0.170 | -5.44 |

**XRP**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 42 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 19.34 |
| 0.05-0.10 | 6 | 4 | 0.068 | 0.000 | -0.068 | 0.068 | 12.76 |
| 0.10-0.15 | 4 | 3 | 0.114 | 0.000 | -0.114 | 0.114 | 17.11 |
| 0.15-0.30 | 14 | 4 | 0.230 | 0.286 | 0.056 | -0.056 | -0.37 |
| 0.30-0.50 | 14 | 3 | 0.461 | 0.286 | -0.175 | 0.175 | 0.85 |
| 0.50-0.70 | 16 | 4 | 0.579 | 0.625 | 0.046 | -0.046 | -0.30 |
| 0.70-0.90 | 15 | 4 | 0.789 | 0.800 | 0.011 | -0.011 | -0.05 |

## Cross-underlying weekly-PnL correlation matrix

_Pearson corr of per-week mean seller PnL/ct (mid), primary horizon. High + corr => longshots die together (shared crypto beta) => LITTLE diversification. Off-diagonal common-weeks count in parens._

| corr | BTC | ETH | SOL | XRP |
|---|---|---|---|---|
| **BTC** | 1.00 | 0.82 (4) | 0.79 (4) | 0.71 (4) |
| **ETH** | 0.82 (4) | 1.00 | 0.36 (4) | 0.32 (4) |
| **SOL** | 0.79 (4) | 0.36 (4) | 1.00 | 0.98 (4) |
| **XRP** | 0.71 (4) | 0.32 (4) | 0.98 (4) | 1.00 |

- SOL vs BTC+ETH reference (pooled weekly PnL): corr **0.59** (4 wks)
- XRP vs BTC+ETH reference: corr **0.53** (4 wks)

## Diversification / frontier impact

| portfolio | n | wks | mean PnL/ct | wk-clustered t | wk-Sharpe | positions/wk |
|---|---|---|---|---|---|---|
| BTC+ETH (confirmed) | 34 | 4 | -0.050 | -0.43 | -0.29 | 8.5 |
| SOL+XRP (new) | 22 | 4 | -0.090 | -0.57 | -0.13 | 5.5 |
| ALL 4 stacked | 56 | 4 | -0.066 | -0.54 | -0.29 | 14.0 |

_wk-Sharpe = mean / stdev of the equal-weight per-week portfolio PnL. If the added underlyings were uncorrelated the ALL-4 Sharpe would rise ~sqrt(2) over BTC+ETH; the actual rise measures the REAL diversification (net of shared crypto beta)._

## Per-underlying weekly PnL series (band, mid)

- **BTC**: 2026-W26:0.2137(n4), 2026-W27:-0.3983(n3), 2026-W28:-0.03(n4), 2026-W29:-0.0313(n4) | neg-week frac 0.75
- **ETH**: 2026-W26:0.242(n5), 2026-W27:-0.3137(n4), 2026-W28:0.015(n6), 2026-W29:-0.2875(n4) | neg-week frac 0.50
- **SOL**: 2026-W26:0.25(n1), 2026-W27:-0.4483(n3), 2026-W28:-0.3005(n2), 2026-W29:0.248(n2) | neg-week frac 0.50
- **XRP**: 2026-W26:0.227(n5), 2026-W27:-0.2575(n4), 2026-W28:-0.2687(n4), 2026-W29:0.185(n1) | neg-week frac 0.50

## VERDICT

**BTC**: n=15 over 4 wks | seller PnL/ct mid **-0.039** (wk-clustered t=-0.34), exe-1c -0.049 (t=-0.43), exe+fee -0.068 (t=-0.59) | entry 0.228 vs realized YES 0.267 (NOT overpriced), win 0.733, worst wk -0.398.

**ETH**: n=19 over 4 wks | seller PnL/ct mid **-0.058** (wk-clustered t=-0.46), exe-1c -0.068 (t=-0.54), exe+fee -0.084 (t=-0.66) | entry 0.205 vs realized YES 0.263 (NOT overpriced), win 0.737, worst wk -0.314.

**SOL**: n=8 over 4 wks | seller PnL/ct mid **-0.150** (wk-clustered t=-0.80), exe-1c -0.160 (t=-0.85), exe+fee -0.178 (t=-0.95) | entry 0.225 vs realized YES 0.375 (NOT overpriced), win 0.625, worst wk -0.448.

**XRP**: n=14 over 4 wks | seller PnL/ct mid **-0.056** (wk-clustered t=-0.37), exe-1c -0.066 (t=-0.43), exe+fee -0.086 (t=-0.56) | entry 0.230 vs realized YES 0.286 (NOT overpriced), win 0.714, worst wk -0.269.



**Does the premium EXTEND?**

NO — neither SOL nor XRP clears a positive, significant, correctly-calibrated band edge; the premium is (on this sample) BTC/ETH-specific.

Not clearly extending: SOL, XRP (small-n and/or weak t — see table).



**Correlation / diversification.** Cross-underlying weekly-PnL correlations (primary 144h horizon, 2026-05-22..2026-07-17): BTC-ETH 0.82, BTC-SOL 0.79, BTC-XRP 0.71, ETH-SOL 0.36, ETH-XRP 0.32, SOL-XRP 0.98. SOL vs BTC+ETH ref 0.59, XRP vs ref 0.53.

These weeklies are DIRECTIONALLY LINKED longshots — a broad crypto rally lifts every underlying's spot together, so the same weeks tend to be the losing (longshot-prints) weeks across names. High positive weekly-PnL correlation => LIMITED true diversification: adding SOL/XRP raises positions/week but does NOT give ~independent streams (variance falls far less than 1/k). n_weeks per pair is only ~4 — correlations are noisy, treat as directional.



**Frontier / capacity.** Positions/week (band, primary horizon): BTC 3.8, ETH 4.8, SOL 2.0, XRP 3.5. BTC+ETH pooled ~8.5/wk (t=-0.43, wk-Sharpe -0.29); ALL-4 pooled ~14.0/wk (t=-0.54, wk-Sharpe -0.29).



**BLUNT VERDICT.** On this ~8-week settled sample the premium is BTC/ETH-specific; SOL/XRP do not deliver a clean, significant, correctly-calibrated band edge. Extension is a NULL (frequency lever does not open). Caveat: n per underlying is small — this is 'not shown to extend', not 'proven absent'.