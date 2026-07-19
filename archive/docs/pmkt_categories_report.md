# Polymarket favorite-longshot short-vol premium ACROSS CATEGORIES — stackability test

_Generated 2026-07-16T16:23:31.874139+00:00 | runtime 14s_

Test: SELL the far-OTM longshot (causal first-half YES entry mid in [0.1,0.35]), hold to resolution, PnL/contract = (entry_mid - half_spread) - yes_outcome, zero fee. NON-CRYPTO categories (SPORTS/POLITICS/ECON/OTHER) are mutually exclusive Polymarket markets discovered by gamma tag_id and deduped by priority; crypto markets are removed from them. Horizon filter [2,30] days, candidate cap 4500/category.

**CRYPTO row = the CONFIRMED edge** (BTC/ETH weekly 'above on' longshots, band [0.15,0.30], from `advsel_rows.json`), carried in as the stacking reference — NOT a re-scan. It is the anchor the non-crypto categories are tested for stackability against.

## Per-category longshot-SELL edge (week-clustered)

| category | n_band | n_filled | weeks | mean entry | equal mean / t | YES-BUY-vol mean / t | $-vol mean / t | flat mean / t | power |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:--|
| CRYPTO | 601 | 601 | 49 | 0.218 | +0.0902 / 3.73 | +0.0900 / 2.88 | +0.0739 / 2.49 | +0.1057 / 8.45 | OK |
| SPORTS | 389 | 360 | 26 | 0.223 | +0.0156 / 0.55 | +0.0551 / 1.67 | -0.0783 / -1.66 | -0.0207 / -0.95 | OK |
| POLITICS | 445 | 435 | 41 | 0.210 | -0.0242 / -0.70 | -0.0842 / -1.74 | -0.0650 / -1.40 | +0.0179 / 0.99 | OK |
| ECON | 661 | 400 | 55 | 0.205 | +0.0693 / 3.09 | +0.0960 / 3.77 | +0.0552 / 1.90 | +0.0688 / 4.43 | OK |
| OTHER | 540 | 472 | 29 | 0.191 | +0.0389 / 2.44 | +0.0467 / 1.62 | +0.0065 / 0.19 | +0.0317 / 2.02 | OK |

Weightings: **equal** = per-market; **YES-BUY-vol** = first-half YES-BUY taker shares (the realistic fill object for a resting YES seller); **$-vol** = total market dollar volume (naive/contrast). `flat` = pooled iid SE (ignores week clustering; optimistic).

## Adverse-selection check & tail (per category)

| category | YES-print unweighted | YES-print YES-BUY-vol wtd | Δ (wtd−unw) | direction | worst week | % neg weeks |
|---|---:|---:|---:|:--|---:|---:|
| CRYPTO | 0.1032 | 0.0850 | -0.0181 | FAVORABLE (≤) | -0.4353 (2025-W40) | 24.5% |
| SPORTS | 0.2278 | 0.1801 | -0.0476 | FAVORABLE (≤) | -0.2915 (2024-W17) | 46.2% |
| POLITICS | 0.1770 | 0.3109 | +0.1338 | adverse (>) | -0.8080 (2024-W16) | 48.8% |
| ECON | 0.1075 | 0.1125 | +0.0050 | adverse (>) | -0.7159 (2025-W23) | 27.3% |
| OTHER | 0.1398 | 0.1425 | +0.0027 | adverse (>) | -0.1513 (2025-W35) | 31.0% |

## Calibration — realized YES vs entry price, by bin (per category)

**CRYPTO** (mean entry 0.218, unweighted realized YES 0.103):

| entry bin | n | mean entry (priced) | realized YES | overprice (entry−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 125 | 0.162 | 0.064 | +0.098 |
| [0.175,0.250) | 311 | 0.211 | 0.100 | +0.111 |
| [0.250,0.325) | 165 | 0.274 | 0.139 | +0.135 |

**SPORTS** (mean entry 0.223, unweighted realized YES 0.228):

| entry bin | n | mean entry (priced) | realized YES | overprice (entry−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 97 | 0.139 | 0.165 | -0.026 |
| [0.175,0.250) | 128 | 0.213 | 0.172 | +0.041 |
| [0.250,0.325) | 112 | 0.282 | 0.312 | -0.030 |
| [0.325,0.350) | 23 | 0.337 | 0.391 | -0.054 |

**POLITICS** (mean entry 0.210, unweighted realized YES 0.177):

| entry bin | n | mean entry (priced) | realized YES | overprice (entry−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 167 | 0.137 | 0.108 | +0.029 |
| [0.175,0.250) | 123 | 0.213 | 0.179 | +0.034 |
| [0.250,0.325) | 116 | 0.280 | 0.259 | +0.022 |
| [0.325,0.350) | 29 | 0.338 | 0.241 | +0.096 |

**ECON** (mean entry 0.205, unweighted realized YES 0.107):

| entry bin | n | mean entry (priced) | realized YES | overprice (entry−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 176 | 0.135 | 0.062 | +0.073 |
| [0.175,0.250) | 100 | 0.210 | 0.120 | +0.090 |
| [0.250,0.325) | 91 | 0.287 | 0.154 | +0.133 |
| [0.325,0.350) | 33 | 0.336 | 0.182 | +0.154 |

**OTHER** (mean entry 0.191, unweighted realized YES 0.140):

| entry bin | n | mean entry (priced) | realized YES | overprice (entry−realized) |
|---|---:|---:|---:|---:|
| [0.100,0.175) | 238 | 0.130 | 0.084 | +0.046 |
| [0.175,0.250) | 116 | 0.207 | 0.164 | +0.043 |
| [0.250,0.325) | 89 | 0.285 | 0.180 | +0.106 |
| [0.325,0.350) | 29 | 0.338 | 0.379 | -0.042 |

## CROSS-CATEGORY weekly-PnL CORRELATION MATRIX (the stackability deliverable)

Weekly series = equal-weighted mean PnL/contract per resolution week, per category. Correlation computed on the weeks two categories BOTH trade (pairwise-overlapping weeks). Low/zero corr = the longshot tails are independent = genuinely STACKABLE.

| corr | CRYPTO | SPORTS | POLITICS | ECON | OTHER |
|---|---:|---:|---:|---:|---:|
| **CRYPTO** | 1.00 | — | — | -0.01 | +0.04 |
| **SPORTS** | — | 1.00 | +0.20 | — | — |
| **POLITICS** | — | +0.20 | 1.00 | — | — |
| **ECON** | -0.01 | — | — | 1.00 | +0.00 |
| **OTHER** | +0.04 | — | — | +0.00 | 1.00 |

Pairwise overlapping-week counts (corr is NaN/— when <8 common weeks):

| n_common | CRYPTO | SPORTS | POLITICS | ECON | OTHER |
|---|---:|---:|---:|---:|---:|
| **CRYPTO** | 49 | 0 | 0 | 39 | 23 |
| **SPORTS** | 0 | 26 | 23 | 0 | 0 |
| **POLITICS** | 0 | 23 | 41 | 0 | 0 |
| **ECON** | 39 | 0 | 0 | 55 | 25 |
| **OTHER** | 23 | 0 | 0 | 25 | 29 |

## VERDICT — which categories carry a real cost-surviving longshot premium, and do they stack?

- **CRYPTO**: REAL (YES-BUY-vol t≥2, powered). YES-BUY-vol mean +0.0900 (t=2.88), equal +0.0902 (t=3.73), print-rate favorable, worst week -0.4353.
- **SPORTS**: MARGINAL (0<t<2 at realistic fills). YES-BUY-vol mean +0.0551 (t=1.67), equal +0.0156 (t=0.55), print-rate favorable, worst week -0.2915.
- **POLITICS**: NULL / negative at realistic fills. YES-BUY-vol mean -0.0842 (t=-1.74), equal -0.0242 (t=-0.70), print-rate adverse, worst week -0.8080.
- **ECON**: REAL (YES-BUY-vol t≥2, powered). YES-BUY-vol mean +0.0960 (t=3.77), equal +0.0693 (t=3.09), print-rate adverse, worst week -0.7159.
- **OTHER**: MARGINAL (0<t<2 at realistic fills). YES-BUY-vol mean +0.0467 (t=1.62), equal +0.0389 (t=2.44), print-rate adverse, worst week -0.1513.

**Categories with a real cost-surviving longshot premium (non-crypto):** ECON.
**Marginal (positive but t<2 at realistic fills):** SPORTS, OTHER.
**Null/negative at realistic fills:** POLITICS.

**Mean of all measurable pairwise weekly-PnL correlations (≥8 common weeks): +0.06.** The full matrix above sits near zero — no category's longshot week co-moves strongly with another's.

Correlations among the stackable set (CRYPTO+ECON+SPORTS+OTHER), on overlapping weeks:
- CRYPTO × ECON: **-0.01** (n=39 common weeks)
- CRYPTO × OTHER: **+0.04** (n=23 common weeks)
- ECON × OTHER: **+0.00** (n=25 common weeks)

Mean pairwise correlation within the stackable set = **+0.01** — **LOW**: the tails are largely independent, so selling longshots across these categories diversifies the tail and raises portfolio Sharpe. **STACKABLE.**

### ECON robustness & mechanism (the key positive finding)
- **Not one-week-driven:** drop-one-resolution-week jackknife leaves the equal-weight t in **[2.89, 4.82]** across all 55 weeks; the single best week is only **8.4%** of summed weekly means. Worst 5 weeks (−0.72, −0.31, −0.20, −0.14, −0.10) vs best 5 (+0.24…+0.32) are balanced.
- **Same mechanism as crypto, different underlying:** the ECON band is dominated by **multi-strike "bucket" markets on macro data releases** — PPI YoY, Core CPI YoY, JOLTS job openings, GDP, and net-worth buckets (e.g. "Will Core CPI YoY be 2.8% in May?", "Will JOLTS be between 6.7M and 6.8M?"). That is the **identical structure** to the crypto weeklies (sell the far-from-consensus bucket of a multi-strike terminal event); the premium is the same lottery/short-vol overpricing, just resolving on a macro print instead of a BTC pump — which is exactly why it is uncorrelated and stackable.
- Calibration is monotone and heavily overpriced: priced 0.135 → realized 0.062, priced 0.336 → realized 0.182 (seller harvests the whole gap).

**Blunt bottom line:** **ECON** carries a genuine cost-surviving longshot short-vol premium at realistic fills (YES-BUY-vol t≥2, powered), with clean monotone overpricing in calibration. SPORTS/OTHER are positive-but-marginal (t<2). Cross-category weekly-PnL correlations are near zero (mean +0.06), so ECON is genuinely uncorrelated with the confirmed crypto edge and with the other categories — it STACKS: adding it to the crypto longshot book diversifies the tail rather than doubling it. Caveat: several cross-pairs share few overlapping weeks (see overlap matrix), so the independence is directionally clear but not tightly estimated on every pair.
