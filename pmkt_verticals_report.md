# Widening the book — new longshot-premium sleeves across Polymarket verticals

_Generated 2026-07-16T19:21:44.644216+00:00 | runtime 641s_

SELL the far-OTM longshot: causal first-half YES entry mid, **executable BID** = entry_mid − half_spread banded in [0.1,0.35] with full spread ≤ 0.06. PnL/contract = entry_bid − yes_outcome, zero fee. Cluster by resolution week. Verticals are independent tag universes with the existing CRYPTO & macro-ECON conditionIds EXCLUDED (so we are not re-measuring the two live sleeves). Existing sleeves: CRYPTO (advsel_rows.json), ECON (cat_results ECON.weekly_eq).

## Per-vertical longshot-SELL edge (week-clustered)

| vertical | n_band | n_filled | weeks | mean bid | equal mean / t | YES-BUY-vol mean / t | $-vol mean / t | flat mean / t | power |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:--|
| GEO | 544 | 474 | 83 | 0.205 | +0.0384 / 1.46 | +0.0078 / 0.22 | -0.0354 / -0.95 | +0.0444 / 2.67 | OK |
| BUSINESS | 957 | 394 | 21 | 0.208 | +0.0841 / 1.68 | +0.1133 / 2.28 | +0.0284 / 0.48 | +0.1323 / 9.63 | OK |
| TECHAI | 631 | 418 | 57 | 0.185 | +0.0529 / 2.70 | +0.0318 / 1.05 | +0.0139 / 0.47 | +0.0578 / 3.54 | OK |
| WEATHER | 1670 | 1647 | 16 | 0.199 | +0.0747 / 2.09 | +0.0207 / 0.28 | +0.0490 / 0.98 | +0.0112 / 1.19 | <20wk |
| ENT | 744 | 424 | 6 | 0.224 | +0.0958 / 5.11 | +0.0723 / 1.79 | +0.0679 / 1.32 | +0.0916 / 5.64 | <20wk |
| SPORTS_NBA | 81 | 34 | 10 | 0.203 | +0.1577 / 3.79 | +0.1892 / 5.92 | +0.0858 / 0.89 | +0.0852 / 1.49 | <20wk,<300mkt |
| SPORTS_SOCCER | 1636 | 718 | 33 | 0.243 | -0.0244 / -0.68 | -0.0053 / -0.11 | -0.0621 / -1.31 | -0.0130 / -0.81 | OK |
| SPORTS_NFL | 229 | 141 | 39 | 0.212 | +0.0544 / 1.02 | +0.0582 / 1.05 | +0.0344 / 0.62 | +0.0278 / 0.84 | <300mkt |

Weightings: **equal** = per-market; **YES-BUY-vol** = first-half YES-BUY taker shares (realistic fill object for a resting YES seller); **$-vol** = total market dollar volume (naive/contrast). `flat` = pooled iid SE (ignores week clustering; optimistic).

## Adverse selection, tail & robustness (per vertical)

| vertical | YES-print unw | YES-print vol-wtd | Δ | adv-sel | worst week | %neg wk | JK-min t (vol) | drop-best t (vol) |
|---|---:|---:|---:|:--|---:|---:|---:|---:|
| GEO | 0.1603 | 0.3114 | +0.1510 | adverse | -0.8080 (2024-W16) | 30.1% | 0.10 | 0.10 |
| BUSINESS | 0.0761 | 0.0319 | -0.0442 | FAVORABLE | -0.7958 (2026-W17) | 19.0% | 2.04 | 2.04 |
| TECHAI | 0.1268 | 0.1759 | +0.0491 | adverse | -0.2164 (2025-W31) | 43.9% | 0.87 | 0.87 |
| WEATHER | 0.1882 | 0.1980 | +0.0098 | neutral | -0.3011 (2026-W24) | 18.8% | 0.00 | 0.00 |
| ENT | 0.1321 | 0.1194 | -0.0127 | FAVORABLE | +0.0107 (2026-W28) | 0.0% | 1.27 | 1.27 |
| SPORTS_NBA | 0.1176 | 0.1177 | +0.0000 | neutral | -0.0920 (2025-W21) | 20.0% | 5.24 | 5.71 |
| SPORTS_SOCCER | 0.2563 | 0.1699 | -0.0864 | FAVORABLE | -0.7584 (2025-W21) | 45.5% | -0.27 | -0.27 |
| SPORTS_NFL | 0.1844 | 0.2657 | +0.0813 | adverse | -0.8095 (2024-W47) | 33.3% | 0.90 | 0.90 |

## Calibration — realized YES vs executable bid, by bin

**GEO** (mean bid 0.205, unweighted realized YES 0.160):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 182 | 0.134 | 0.110 | +0.024 |
| [0.175,0.250) | 160 | 0.208 | 0.144 | +0.064 |
| [0.250,0.325) | 97 | 0.284 | 0.237 | +0.047 |
| [0.325,0.350) | 35 | 0.337 | 0.286 | +0.051 |

**BUSINESS** (mean bid 0.208, unweighted realized YES 0.076):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 141 | 0.132 | 0.050 | +0.082 |
| [0.175,0.250) | 126 | 0.209 | 0.103 | +0.106 |
| [0.250,0.325) | 106 | 0.285 | 0.094 | +0.190 |
| [0.325,0.350) | 21 | 0.338 | 0.000 | +0.338 |

**TECHAI** (mean bid 0.185, unweighted realized YES 0.127):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 233 | 0.135 | 0.099 | +0.037 |
| [0.175,0.250) | 102 | 0.205 | 0.167 | +0.039 |
| [0.250,0.325) | 68 | 0.288 | 0.176 | +0.112 |
| [0.325,0.350) | 15 | 0.336 | 0.067 | +0.269 |

**WEATHER** (mean bid 0.199, unweighted realized YES 0.188):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 672 | 0.136 | 0.094 | +0.042 |
| [0.175,0.250) | 579 | 0.211 | 0.206 | +0.005 |
| [0.250,0.325) | 353 | 0.285 | 0.320 | -0.036 |
| [0.325,0.350) | 43 | 0.336 | 0.349 | -0.012 |

**ENT** (mean bid 0.224, unweighted realized YES 0.132):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 137 | 0.138 | 0.073 | +0.065 |
| [0.175,0.250) | 117 | 0.212 | 0.094 | +0.118 |
| [0.250,0.325) | 120 | 0.286 | 0.208 | +0.077 |
| [0.325,0.350) | 50 | 0.339 | 0.200 | +0.139 |

**SPORTS_NBA** (mean bid 0.203, unweighted realized YES 0.118):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 12 | 0.129 | 0.167 | -0.038 |
| [0.175,0.250) | 14 | 0.208 | 0.000 | +0.208 |
| [0.250,0.325) | 5 | 0.282 | 0.200 | +0.082 |
| [0.325,0.350) | 3 | 0.341 | 0.333 | +0.008 |

**SPORTS_SOCCER** (mean bid 0.243, unweighted realized YES 0.256):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 118 | 0.138 | 0.085 | +0.053 |
| [0.175,0.250) | 241 | 0.218 | 0.261 | -0.043 |
| [0.250,0.325) | 285 | 0.283 | 0.291 | -0.008 |
| [0.325,0.350) | 74 | 0.338 | 0.378 | -0.041 |

**SPORTS_NFL** (mean bid 0.212, unweighted realized YES 0.184):

| bid bin | n | mean bid | realized YES | overprice (bid−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 57 | 0.133 | 0.175 | -0.042 |
| [0.175,0.250) | 36 | 0.219 | 0.083 | +0.135 |
| [0.250,0.325) | 34 | 0.287 | 0.324 | -0.037 |
| [0.325,0.350) | 14 | 0.337 | 0.143 | +0.194 |

## CORRELATION TO EXISTING SLEEVES (the key deliverable)

Weekly series = equal-weighted mean PnL/contract per resolution week. Correlation on the weeks both series trade (>=8 common weeks required, else n/a).

| vertical | corr vs CRYPTO (n) | corr vs ECON (n) | real edge? | robust? | adv-sel | |corr|<0.3 both? |
|---|---:|---:|:--|:--|:--|:--|
| GEO | -0.03 (40) | -0.04 (47) | no | no | ADVERSE | YES |
| BUSINESS | +0.07 (21) | +0.07 (18) | YES | YES | ok | YES |
| TECHAI | +0.08 (33) | -0.04 (40) | no | no | ADVERSE | YES |
| WEATHER | -0.37 (16) | -0.19 (11) | no | no | ok | no |
| ENT | n/a (6) | n/a (3) | no | no | ok | no |
| SPORTS_NBA | n/a (0) | n/a (3) | no | no | ok | no |
| SPORTS_SOCCER | -0.20 (10) | -0.14 (19) | no | no | ok | YES |
| SPORTS_NFL | +0.11 (20) | +0.17 (20) | no | no | ADVERSE | YES |

## FULL weekly-PnL correlation matrix  {crypto, econ, + verticals showing a real edge}

| corr | CRYPTO | ECON | BUSINESS |
|---|---:|---:|---:|
| **CRYPTO** | 1.00 | -0.01 | +0.07 |
| **ECON** | -0.01 | 1.00 | +0.07 |
| **BUSINESS** | +0.07 | +0.07 | 1.00 |

Overlapping-week counts:

| n | CRYPTO | ECON | BUSINESS |
|---|---:|---:|---:|
| **CRYPTO** | 49 | 39 | 21 |
| **ECON** | 39 | 55 | 18 |
| **BUSINESS** | 21 | 18 | 21 |

## VERDICT

- **GEO — NULL** at realistic fills. YES-BUY-vol mean +0.0078 (t=0.22), equal +0.0384 (t=1.46).
- **BUSINESS — NEW STACKABLE SLEEVE.** YES-BUY-vol mean +0.1133 (t=2.28), JK-min t 2.04, drop-best t 2.04, adv-sel -0.0442; corr crypto +0.07, econ +0.07 — both |<0.3|.
- **TECHAI — NULL** at realistic fills. YES-BUY-vol mean +0.0318 (t=1.05), equal +0.0529 (t=2.70).
- **WEATHER — NULL** at realistic fills. YES-BUY-vol mean +0.0207 (t=0.28), equal +0.0747 (t=2.09). UNDERPOWERED[16wk]
- **ENT — NULL** at realistic fills. YES-BUY-vol mean +0.0723 (t=1.79), equal +0.0958 (t=5.11). UNDERPOWERED[6wk]
- **SPORTS_NBA — NULL** at realistic fills. YES-BUY-vol mean +0.1892 (t=5.92), equal +0.1577 (t=3.79). UNDERPOWERED[10wk,34mkt]
- **SPORTS_SOCCER — NULL** at realistic fills. YES-BUY-vol mean -0.0053 (t=-0.11), equal -0.0244 (t=-0.68).
- **SPORTS_NFL — NULL** at realistic fills. YES-BUY-vol mean +0.0582 (t=1.05), equal +0.0544 (t=1.02). UNDERPOWERED[141mkt]

**NEW STACKABLE sleeves (real + robust + uncorrelated to BOTH crypto & econ):** BUSINESS.
**Real-but-correlated (redundant with an existing sleeve):** none.
**Null / fragile / adverse:** GEO, TECHAI, WEATHER, ENT, SPORTS_NBA, SPORTS_SOCCER, SPORTS_NFL.

