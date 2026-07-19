# KALSHI short-vol / structural edge test

_generated 2026-07-18T06:03:05.832783+00:00_

## VERDICT (blunt)

**No deployable edge.** No category clears a fee-surviving longshot premium (net PnL/ct > 0 with week-clustered t ≥ 2 over ≥ 8 weeks). No riskless structural arb survives fees.

- **Longshot premium: absent.** Kalshi longshots are *well-calibrated* — priced ≈ realized across the whole wing (calibration gaps at noise level, ±0.04, alternating sign). This is the opposite of Polymarket crypto, where the band prints ~10.5% while priced ~22% (+0.115 gap). With no gross overpricing to harvest and a ~1.6¢/ct fee, the seller's **net PnL is firmly negative** in every category (weather net −0.023/ct, week-clustered t = −2.82 — significant, but in the *losing* direction).
- **Structural arb: absent.** Across 1,273 genuine weather range-bucket partitions (empirically exactly-one-winner), **zero** underround/overround survives per-leg fees; books carry ~11–16¢ of bid/ask vig. Cumulative-threshold ladders (commodity/crypto EOD) are not partitions and were excluded.
- **Uncorrelated sleeve: N/A.** There is no survivor to deploy, so correlation with the Polymarket book is moot. (Weather is mechanically independent of BTC, but a well-calibrated market pays nothing to bear that risk — calibration, not correlation, is the binding constraint here.)
- **Why the difference from Polymarket:** Kalshi is a CFTC-regulated exchange with professional market-makers who arb the ladder to calibration; Polymarket's zero-fee crypto weeklies are dominated by retail lottery-buyers who overpay the wing. The premium is a *venue/participant* effect, and it does **not** port to Kalshi. Fees are the second nail, not the first — the edge is already gone at the gross level.
- **Multiple testing:** 4 categories × 2 tests (longshot + structural) = 8 tests. The only |t|≥2 result is weather, and its sign is negative (sellers lose). Nothing to haircut.

---

Fee model: **ceil_to_cent(0.07*p*(1-p)) once at entry** (continuous 0.07·p·(1−p) is a lower bound).
Band on mid = (0.1, 0.35); execution/PnL on executable yes_bid. Entry = first-half-of-life candlestick (no terminal look-ahead).
Categories tested: **4** (WEATHER-HIGHTEMP, COMMODITY-EOD, ECON-RELEASE, CRYPTO-EOD) — multiple-testing haircut applies.

## 1. Longshot short-vol test (NET of fees)

| Category | n | weeks | net PnL/ct | gross/ct | mean fee | wk-clust t | priced(mid) | realized YES | calib gap | worst wk net | neg-wk% | capacity(ct) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| WEATHER-HIGHTEMP | 1888 | 10 | -0.0229 | -0.0069 | 0.0160 | -2.82 | 0.219 | 0.212 | +0.006 | -0.077 | 70% | 38,747,434 |
| COMMODITY-EOD | 783 | 10 | -0.0286 | -0.0128 | 0.0158 | -0.62 | 0.215 | 0.208 | +0.006 | -0.177 | 60% | 11,803,826 |
| ECON-RELEASE | 14 | 3 | +0.0007 | +0.0157 | 0.0150 | -0.09 | 0.190 | 0.143 | +0.047 | -0.093 | 67% | 606,909 |
| CRYPTO-EOD | 29 | 1 | -0.0072 | +0.0093 | 0.0166 | n/a | 0.223 | 0.207 | +0.016 | -0.007 | 100% | 8,170,242 |

Calibration: `calib gap = priced(mid) − realized YES-rate`. Positive = longshots overpriced (the short-vol premium). A premium is only real if it also survives fees (net PnL/ct > 0) with a defensible week-clustered t.

**Small-n / UNINTERPRETABLE (flagged, not evidence):** ECON-RELEASE (n=14, weeks=3), CRYPTO-EOD (n=29, weeks=1). ECON-RELEASE shows the only positive-ish gross (+0.016/ct) and the largest raw calib gap (+0.047), but n=14 over 3 monthly windows with week-clustered t≈−0.09 is pure noise — it is NOT a signal, and econ releases are event-driven (schedule risk), not a recurring weekly harvest. CRYPTO-EOD's hourly universe was capped to the most recent ~1 week, so its 29 in-band obs are non-representative.

## 1b. Calibration curve by price bucket (out-of-band diagnostic)

Priced (mid) vs realized YES-rate across the whole wing. On Polymarket the crypto band prints ~10.5% while priced ~22% (gap ≈ +0.115). A large positive gap = harvestable overpricing.

**WEATHER-HIGHTEMP**  
| price band | n | priced | realized YES | gap |
|---|--:|--:|--:|--:|
| 0.02–0.05 | 1303 | 0.031 | 0.025 | +0.005 |
| 0.05–0.10 | 841 | 0.071 | 0.069 | +0.002 |
| 0.10–0.15 | 483 | 0.123 | 0.122 | +0.001 |
| 0.15–0.20 | 335 | 0.173 | 0.152 | +0.020 |
| 0.20–0.25 | 324 | 0.224 | 0.265 | -0.041 |
| 0.25–0.30 | 363 | 0.273 | 0.237 | +0.036 |
| 0.30–0.35 | 365 | 0.322 | 0.307 | +0.016 |
| 0.35–0.45 | 715 | 0.398 | 0.421 | -0.023 |
| 0.45–0.55 | 499 | 0.492 | 0.467 | +0.025 |

**COMMODITY-EOD**  
| price band | n | priced | realized YES | gap |
|---|--:|--:|--:|--:|
| 0.02–0.05 | 208 | 0.032 | 0.038 | -0.007 |
| 0.05–0.10 | 249 | 0.073 | 0.036 | +0.037 |
| 0.10–0.15 | 199 | 0.121 | 0.111 | +0.010 |
| 0.15–0.20 | 146 | 0.174 | 0.158 | +0.016 |
| 0.20–0.25 | 154 | 0.221 | 0.234 | -0.012 |
| 0.25–0.30 | 147 | 0.273 | 0.231 | +0.042 |
| 0.30–0.35 | 130 | 0.322 | 0.346 | -0.025 |
| 0.35–0.45 | 264 | 0.401 | 0.394 | +0.007 |
| 0.45–0.55 | 257 | 0.500 | 0.490 | +0.010 |

**CRYPTO-EOD**  
| price band | n | priced | realized YES | gap |
|---|--:|--:|--:|--:|
| 0.02–0.05 | 31 | 0.031 | 0.032 | -0.001 |
| 0.05–0.10 | 13 | — | — | — |
| 0.10–0.15 | 7 | — | — | — |
| 0.15–0.20 | 7 | — | — | — |
| 0.20–0.25 | 2 | — | — | — |
| 0.25–0.30 | 6 | — | — | — |
| 0.30–0.35 | 7 | — | — | — |
| 0.35–0.45 | 2 | — | — | — |
| 0.45–0.55 | 9 | — | — | — |

## 2. Structural test — mutually-exclusive range buckets (net of per-leg fees)

| Category | events | valid partitions | best underround net | mean | %>0 | best overround net | mean | %>0 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| WEATHER-HIGHTEMP | 1273 | 1273 | -0.0000 | -0.1610 | 0% | +0.0000 | -0.1106 | 0% |
| COMMODITY-EOD | 159 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| ECON-RELEASE | 9 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| CRYPTO-EOD | 53 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

`underround net = 1 − Σyes_ask − Σfees` (buy every bucket, collect $1 if exhaustive). `overround net = Σyes_bid − 1 − Σfees` (sell every bucket). Positive ⇒ riskless net of fees — but only if the bucket set is EXHAUSTIVE (covers the whole line). Non-exhaustive ladders are NOT riskless.

## 3. Correlation with the Polymarket crypto short-vol driver

_Moot: no non-crypto category cleared a net premium, so there is no survivor whose weekly PnL is worth correlating. (The Kalshi crypto proxy was also time-limited — the hourly universe was capped to the most recent ~2,500 markets ≈ 1 week — so a numeric Pearson is not meaningful here regardless.)_
