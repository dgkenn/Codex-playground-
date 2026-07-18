# Cross-category longshot short-vol premium — DIVERSIFICATION scan

_Generated 2026-07-18T05:29:53.148997+00:00 | runtime 49s_

Test: SELL the far-OTM longshot (causal first-half YES entry mid in [0.10,0.35]), hold to UMA resolution, PnL/ct = (entry_mid − half_spread) − yes_outcome, zero fee. Non-crypto categories are mutually-exclusive Polymarket markets discovered by gamma tag_id, priority-deduped, with all crypto conditionIds stripped out. Horizon [2,30] days; band = TRADEABLE [0.10,0.35] (excludes the 2-8c taker-dead deep wing). Half-spread haircut = median |YES-BUY taker fill − mid| over the first half; markets with no first-half YES-buy taker are flagged (no fill object) and excluded from the headline. **t is PERIOD-CLUSTERED by resolution week** (not per-contract).

**CRYPTO row = the CONFIRMED edge** (BTC/ETH weekly 'above on' longshots, band [0.15,0.30], from `advsel_rows.json`) — carried in as the diversification anchor, not a re-scan.

**Multiple testing:** 9 non-crypto categories tested. Family-wise 0.05 ⇒ Bonferroni critical |t| ≈ 2.77. A category clears the bar only if its week-clustered |t| exceeds it.

## Per-category longshot-SELL edge (week-clustered)

| category | n_band | n_filled | no-taker | weeks | mean entry | equal PnL/ct / t_wk | YES-buy-vol PnL/ct / t_wk | day-clust t | winrate | powered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--|
| CRYPTO | 601 | 601 | 0 | 49 | 0.218 | +0.0902 / 3.73 | +0.0900 / 2.88 | 4.82 | 89.7% | OK |
| WEATHER | 1719 | 1690 | 29 | 6 | 0.208 | -0.1220 / -0.84 | -0.1210 / -0.83 | -0.94 | 80.5% | UNDERPOWERED |
| SCITECH | 597 | 366 | 231 | 25 | 0.199 | +0.0446 / 1.87 | +0.0007 / 0.01 | 2.44 | 86.6% | OK |
| ENTERTAINMENT | 695 | 327 | 368 | 13 | 0.204 | +0.0746 / 4.53 | +0.0055 / 0.11 | 1.78 | 90.5% | UNDERPOWERED |
| ECON | 436 | 237 | 199 | 45 | 0.201 | +0.0646 / 2.20 | +0.0839 / 2.59 | 3.04 | 89.0% | OK |
| BUSINESS | 36 | 18 | 18 | 7 | 0.214 | +0.1701 / 4.15 | +0.1855 / 5.25 | 4.44 | 94.4% | UNDERPOWERED |
| ELECTIONS | 346 | 236 | 110 | 25 | 0.204 | +0.0156 / 0.63 | -0.0160 / -0.37 | -0.51 | 81.4% | OK |
| GEOPOL | 396 | 352 | 44 | 73 | 0.207 | +0.0197 / 0.67 | -0.0005 / -0.01 | 0.27 | 84.1% | OK |
| SPORTS | 385 | 356 | 29 | 26 | 0.222 | +0.0273 / 0.98 | +0.0652 / 2.02 | 0.01 | 77.5% | OK |
| POLITICS | 286 | 283 | 3 | 32 | 0.214 | +0.0236 / 0.78 | -0.0406 / -0.77 | 0.19 | 81.3% | OK |

Weightings: **equal** = per-market; **YES-buy-vol** = first-half YES-BUY taker shares (the realistic fill object for a resting YES seller). day-clust t clusters by resolution DAY (robustness).

## Tail & adverse-selection (per category)

| category | worst week | % neg weeks | YES-print unwtd | YES-print YES-buy-wtd | Δ | direction |
|---|---:|---:|---:|---:|---:|:--|
| CRYPTO | -0.4353 (2025-W40) | 24.5% | 0.1032 | 0.0850 | -0.0181 | FAVORABLE (≤) |
| WEATHER | -0.8402 (2026-W13) | 66.7% | 0.1947 | 0.2082 | +0.0135 | adverse (>) |
| SCITECH | -0.2427 (2026-W11) | 28.0% | 0.1339 | 0.1672 | +0.0333 | adverse (>) |
| ENTERTAINMENT | -0.0421 (2026-W28) | 7.7% | 0.0948 | 0.2253 | +0.1305 | adverse (>) |
| ECON | -0.7159 (2025-W23) | 31.1% | 0.1097 | 0.1204 | +0.0107 | adverse (>) |
| BUSINESS | -0.0342 (2024-W18) | 14.3% | 0.0556 | 0.1372 | +0.0816 | adverse (>) |
| ELECTIONS | -0.2639 (2026-W25) | 52.0% | 0.1864 | 0.2661 | +0.0796 | adverse (>) |
| GEOPOL | -0.8728 (2026-W06) | 32.9% | 0.1591 | 0.2955 | +0.1364 | adverse (>) |
| SPORTS | -0.2915 (2024-W17) | 42.3% | 0.2247 | 0.1769 | -0.0478 | FAVORABLE (≤) |
| POLITICS | -0.3336 (2024-W28) | 40.6% | 0.1873 | 0.2592 | +0.0719 | adverse (>) |

## Calibration — realized YES vs priced entry, by bin (the overpricing the seller harvests)

**CRYPTO** (mean entry 0.218, realized YES 0.103):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 125 | 0.162 | 0.064 | +0.098 |
| [0.175,0.250) | 311 | 0.211 | 0.100 | +0.111 |
| [0.250,0.325) | 165 | 0.274 | 0.139 | +0.135 |

**WEATHER** (mean entry 0.208, realized YES 0.195):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 606 | 0.135 | 0.092 | +0.043 |
| [0.175,0.250) | 587 | 0.210 | 0.208 | +0.003 |
| [0.250,0.325) | 425 | 0.285 | 0.313 | -0.028 |
| [0.325,0.350) | 72 | 0.338 | 0.250 | +0.088 |

**SCITECH** (mean entry 0.199, realized YES 0.134):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 163 | 0.136 | 0.092 | +0.044 |
| [0.175,0.250) | 108 | 0.207 | 0.139 | +0.068 |
| [0.250,0.325) | 70 | 0.287 | 0.214 | +0.073 |
| [0.325,0.350) | 25 | 0.338 | 0.160 | +0.178 |

**ENTERTAINMENT** (mean entry 0.204, realized YES 0.095):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 138 | 0.133 | 0.043 | +0.089 |
| [0.175,0.250) | 84 | 0.212 | 0.071 | +0.141 |
| [0.250,0.325) | 91 | 0.284 | 0.176 | +0.109 |
| [0.325,0.350) | 14 | 0.337 | 0.214 | +0.123 |

**ECON** (mean entry 0.201, realized YES 0.110):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 114 | 0.138 | 0.061 | +0.076 |
| [0.175,0.250) | 54 | 0.211 | 0.130 | +0.082 |
| [0.250,0.325) | 53 | 0.286 | 0.208 | +0.079 |
| [0.325,0.350) | 16 | 0.337 | 0.062 | +0.275 |

**BUSINESS** (mean entry 0.214, realized YES 0.056):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 6 | 0.124 | 0.000 | +0.124 |
| [0.175,0.250) | 5 | 0.218 | 0.200 | +0.018 |
| [0.250,0.325) | 6 | 0.281 | 0.000 | +0.281 |
| [0.325,0.350) | 1 | 0.326 | 0.000 | +0.326 |

**ELECTIONS** (mean entry 0.204, realized YES 0.186):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 97 | 0.139 | 0.113 | +0.026 |
| [0.175,0.250) | 74 | 0.208 | 0.162 | +0.046 |
| [0.250,0.325) | 51 | 0.284 | 0.275 | +0.009 |
| [0.325,0.350) | 14 | 0.338 | 0.500 | -0.162 |

**GEOPOL** (mean entry 0.207, realized YES 0.159):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 135 | 0.135 | 0.119 | +0.016 |
| [0.175,0.250) | 115 | 0.211 | 0.165 | +0.046 |
| [0.250,0.325) | 82 | 0.290 | 0.171 | +0.119 |
| [0.325,0.350) | 20 | 0.336 | 0.350 | -0.014 |

**SPORTS** (mean entry 0.222, realized YES 0.225):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 97 | 0.139 | 0.165 | -0.026 |
| [0.175,0.250) | 126 | 0.213 | 0.167 | +0.046 |
| [0.250,0.325) | 110 | 0.282 | 0.309 | -0.027 |
| [0.325,0.350) | 23 | 0.337 | 0.391 | -0.054 |

**POLITICS** (mean entry 0.214, realized YES 0.187):

| entry bin | n | priced | realized YES | overprice (priced−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 100 | 0.136 | 0.100 | +0.036 |
| [0.175,0.250) | 81 | 0.213 | 0.173 | +0.040 |
| [0.250,0.325) | 82 | 0.280 | 0.305 | -0.025 |
| [0.325,0.350) | 20 | 0.337 | 0.200 | +0.137 |

## CROSS-CATEGORY + vs-CRYPTO weekly-PnL CORRELATION MATRIX (the diversification deliverable)

Weekly series = equal-weighted mean PnL/ct per resolution week. Correlation on the weeks two categories BOTH trade (pairwise overlap). Low/zero corr with CRYPTO + real premium = raises the diversified frontier. `—` = <8 common weeks (not estimable).

| corr | CRYPTO | WEATHER | SCITECH | ENTERTAINMENT | ECON | BUSINESS | ELECTIONS | GEOPOL | SPORTS | POLITICS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **CRYPTO** | 1.00 | — | -0.14 | +0.29 | -0.05 | — | -0.03 | -0.08 | — | — |
| **WEATHER** | — | 1.00 | — | — | — | — | — | — | — | — |
| **SCITECH** | -0.14 | — | 1.00 | -0.49 | +0.03 | — | +0.15 | -0.07 | — | — |
| **ENTERTAINMENT** | +0.29 | — | -0.49 | 1.00 | — | — | -0.20 | — | — | — |
| **ECON** | -0.05 | — | +0.03 | — | 1.00 | — | +0.31 | -0.17 | — | — |
| **BUSINESS** | — | — | — | — | — | 1.00 | — | — | — | — |
| **ELECTIONS** | -0.03 | — | +0.15 | -0.20 | +0.31 | — | 1.00 | -0.14 | — | — |
| **GEOPOL** | -0.08 | — | -0.07 | — | -0.17 | — | -0.14 | 1.00 | +0.13 | -0.17 |
| **SPORTS** | — | — | — | — | — | — | — | +0.13 | 1.00 | -0.23 |
| **POLITICS** | — | — | — | — | — | — | — | -0.17 | -0.23 | 1.00 |

Pairwise overlapping-week counts:

| n_com | CRYPTO | WEATHER | SCITECH | ENTERTAINMENT | ECON | BUSINESS | ELECTIONS | GEOPOL | SPORTS | POLITICS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **CRYPTO** | 49 | 6 | 25 | 13 | 30 | 4 | 25 | 38 | 0 | 0 |
| **WEATHER** | 6 | 6 | 6 | 0 | 6 | 0 | 3 | 6 | 0 | 0 |
| **SCITECH** | 25 | 6 | 25 | 13 | 17 | 2 | 16 | 16 | 0 | 0 |
| **ENTERTAINMENT** | 13 | 0 | 13 | 13 | 6 | 0 | 10 | 5 | 0 | 0 |
| **ECON** | 30 | 6 | 17 | 6 | 45 | 3 | 17 | 36 | 0 | 5 |
| **BUSINESS** | 4 | 0 | 2 | 0 | 3 | 7 | 1 | 4 | 2 | 2 |
| **ELECTIONS** | 25 | 3 | 16 | 10 | 17 | 1 | 25 | 19 | 0 | 0 |
| **GEOPOL** | 38 | 6 | 16 | 5 | 36 | 4 | 19 | 73 | 11 | 12 |
| **SPORTS** | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 11 | 26 | 18 |
| **POLITICS** | 0 | 0 | 0 | 0 | 5 | 2 | 0 | 12 | 18 | 32 |

## Capacity (first-half YES-BUY taker $ — the fillable size for a resting YES seller)

| category | total YES-buy $ | per resolution-week $ | n_filled |
|---|---:|---:|---:|
| CRYPTO | $554,124 | $11,309 | 601 |
| WEATHER | $172,589 | $28,765 | 1690 |
| SCITECH | $107,456 | $4,298 | 366 |
| ENTERTAINMENT | $80,808 | $6,216 | 327 |
| ECON | $158,781 | $3,528 | 237 |
| BUSINESS | $16,318 | $2,331 | 18 |
| ELECTIONS | $52,928 | $2,117 | 236 |
| GEOPOL | $1,695,395 | $23,225 | 352 |
| SPORTS | $89,272 | $3,434 | 356 |
| POLITICS | $648,655 | $20,270 | 283 |

## VERDICT — non-crypto uncorrelated longshot-premium sleeves?

- **WEATHER** [UNDERPOWERED]: realistic-fill PnL/ct -0.1210 (t_wk=-0.83), equal -0.1220 (t_wk=-0.84); vs-CRYPTO corr — (n=6, insufficient); cap $28,765/wk; worst week -0.840.
- **SCITECH** [MARGINAL (positive, t<2)]: realistic-fill PnL/ct +0.0007 (t_wk=0.01), equal +0.0446 (t_wk=1.87); vs-CRYPTO corr -0.14 (n=25); cap $4,298/wk; worst week -0.243.
- **ENTERTAINMENT** [UNDERPOWERED]: realistic-fill PnL/ct +0.0055 (t_wk=0.11), equal +0.0746 (t_wk=4.53); vs-CRYPTO corr +0.29 (n=13); cap $6,216/wk; worst week -0.042.
- **ECON** [REAL-nominal (t≥2 but < Bonferroni)]: realistic-fill PnL/ct +0.0839 (t_wk=2.59), equal +0.0646 (t_wk=2.20); vs-CRYPTO corr -0.05 (n=30); cap $3,528/wk; worst week -0.716.
- **BUSINESS** [UNDERPOWERED]: realistic-fill PnL/ct +0.1855 (t_wk=5.25), equal +0.1701 (t_wk=4.15); vs-CRYPTO corr — (n=4, insufficient); cap $2,331/wk; worst week -0.034.
- **ELECTIONS** [NULL/negative]: realistic-fill PnL/ct -0.0160 (t_wk=-0.37), equal +0.0156 (t_wk=0.63); vs-CRYPTO corr -0.03 (n=25); cap $2,117/wk; worst week -0.264.
- **GEOPOL** [NULL/negative]: realistic-fill PnL/ct -0.0005 (t_wk=-0.01), equal +0.0197 (t_wk=0.67); vs-CRYPTO corr -0.08 (n=38); cap $23,225/wk; worst week -0.873.
- **SPORTS** [REAL-nominal (t≥2 but < Bonferroni)]: realistic-fill PnL/ct +0.0652 (t_wk=2.02), equal +0.0273 (t_wk=0.98); vs-CRYPTO corr — (n=0, insufficient); cap $3,434/wk; worst week -0.291.
- **POLITICS** [NULL/negative]: realistic-fill PnL/ct -0.0406 (t_wk=-0.77), equal +0.0236 (t_wk=0.78); vs-CRYPTO corr — (n=0, insufficient); cap $20,270/wk; worst week -0.334.

**Categories with a real premium surviving realistic fills:** ECON, SPORTS (REAL = week-clustered t≥2.77 Bonferroni, or ≥2 nominal). Marginal: SCITECH.
**BOTH profitable AND crypto-uncorrelated (the frontier-raising prize):** ECON (corr -0.05, n=30), SPORTS (corr —, n=0).

_(The two lines above are the MECHANICAL classifier output on t alone. The blunt read below overrides SPORTS and ENTERTAINMENT after inspecting calibration and adverse selection — a t-stat is necessary but not sufficient.)_

## BLUNT SYNTHESIS — read this, not the mechanical labels

**Multiple testing:** 9 non-crypto categories tested. Bonferroni family-wise 0.05 ⇒ need |t_wk| ≥ 2.77. **Zero powered categories clear that bar.** The only category above it (BUSINESS, t=5.25) has n=18 filled markets over 7 weeks — noise, not a finding. So on strict multiple-testing discipline there is **no** non-crypto category with a family-wise-significant longshot premium at realistic fills. The nominal candidates below are reported honestly as nominal.

**1. ECON — the one genuine, crypto-uncorrelated sleeve, but small and only nominal.**
- Realistic-fill (YES-buy-vol) PnL/ct **+0.084, t_wk=2.59**; equal +0.065 (t=2.20); day-clustered t=3.04 — consistent across every weighting/clustering, unlike the artifacts below.
- **Calibration is monotone and heavily overpriced** (the mechanism is real): priced 0.138→realized 0.061, 0.211→0.130, 0.286→0.208. The seller harvests a genuine 7-8c gap across the band.
- **Uncorrelated with crypto: corr -0.05 over n=30 common weeks.** Also ~0 with the other categories. This is the same macro-data-release "bucket" mechanism the earlier 5-bucket study flagged, and it is genuinely independent of a BTC pump.
- **BUT:** does NOT clear Bonferroni (2.59 < 2.77); tail is real (worst week -0.72, 31% negative weeks); **capacity is thin — ~$3.5k/wk of fillable YES-buy taker flow** vs crypto's $11.3k/wk. It diversifies the tail but adds little absolute size.

**2. SPORTS — REJECT. The t=2.02 is a volume-weighting artifact, not overpricing (de-vigged book).**
- Equal-weight PnL/ct is only +0.027 (t=0.98) and **day-clustered t=0.01**; the +0.065/t=2.02 appears ONLY under YES-buy-vol weighting. A premium that exists at one weighting and vanishes at the others is not a premium.
- **Calibration confirms it:** sports longshots are ~efficient — overprice is -0.026, +0.046, -0.027, -0.054 across bins (no systematic direction). This reproduces the prior finding (candidate #10) that **Polymarket sports = a de-vigged sportsbook line**, which is line-efficiency, NOT the favorite-longshot overpricing mechanism. No sellable premium here.

**3. ENTERTAINMENT — REJECT at realistic fills (adverse selection eats it).**
- Equal-weight looks spectacular (+0.075, t=4.53) with textbook monotone overpricing (priced 0.13→0.04, 0.21→0.07). But at realistic YES-buy-vol weighting it **collapses to +0.006 (t=0.11)**, and the adverse-selection Δ is **+0.131** — the markets that actually attract YES-buy takers are exactly the ones that print YES. The clean overpricing sits in markets with no fillable flow. Also underpowered (13 weeks). Apparent premium, not executable.

**4. SCITECH — marginal/dead at realistic fills.** Equal +0.045 (t=1.87) but YES-buy-vol +0.001 (t=0.01); adverse Δ +0.033. Same adverse-selection pattern as ENTERTAINMENT, weaker. Not tradeable.

**5. WEATHER — NULL/negative.** -0.12/ct, only 6 weeks (all 2026), worst week -0.84, 67% negative. Big nominal capacity ($29k/wk) but no edge — do not touch.

**6. GEOPOL, ELECTIONS, POLITICS — NULL.** Realistic-fill PnL ≈ 0 or negative (GEOPOL -0.000/t=-0.01, ELECTIONS -0.016, POLITICS -0.041), all with adverse print-rate skew and fat left tails (GEOPOL worst week -0.87). POLITICS reproduces the earlier null. These are efficient-to-adverse; no premium.

### VERDICT — are there non-crypto uncorrelated longshot-premium sleeves that raise the frontier?

**Essentially ONE, and it is modest: ECON.** It is the only non-crypto category with a longshot-overpricing premium that (a) survives realistic YES-buy-taker fills, (b) is consistent across equal/vol/day weightings, (c) has clean monotone calibration, and (d) is genuinely uncorrelated with the confirmed crypto edge (corr **-0.05**, n=30 weeks). It **does** raise the diversified frontier — selling ECON macro-bucket longshots adds an independent short-vol tail rather than doubling the crypto tail.

**Two honest caveats that keep this from being a big win:**
- **It is nominal, not multiple-testing-robust:** t_wk=2.59 < Bonferroni 2.77 for 9 tests. Treat as "promising, forward-test it," not "confirmed."
- **Capacity is small:** ~**$3.5k/wk** of fillable taker flow (crypto is $11.3k/wk). So even if real, ECON diversifies the tail but adds little dollar size — a frontier *nudge*, not a frontier *lift*.

**Everything else is a trap we've seen before:** SPORTS and ENTERTAINMENT/SCITECH show pretty overpricing that dies at realistic fills (SPORTS = de-vigged book / weighting artifact; ENTERTAINMENT/SCITECH = adverse selection in the fillable flow). WEATHER/GEOPOL/ELECTIONS/POLITICS are null-to-negative. **Net: the confirmed crypto short-vol edge does NOT have a large, independent non-crypto twin. The best available diversifier is ECON — same mechanism, uncorrelated, but small and only nominally significant.**
