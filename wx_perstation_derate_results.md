# Per-Station Derate Re-Measurement (deployed rule: glitch + sustain3)

Run date: 2026-07-19T18:10:31.084383+00:00

Re-measures each station's obs-vs-CLI lock-failure under the DEPLOYED detection rule (glitch filter + 3-minute sustain, `phase2_trackB_tail.sustained_max_k(k=3)`) against the official NWS CLI daily max, multi-year, all seasons. The existing per-station derates were set from the RAW-1-minute failure mode, which the deployed rule filters out; margin=1 fires carry ~3x EV, so an unnecessary derate costs real money.

**Coverage:** 20 stations, years requested [2021, 2022, 2023, 2024, 2025, 2026], 35115 station-days with both CLI truth and sustain3 obs value.

**Pre-registered relaxation bar:** a derate may be relaxed only if the station's sustain3 margin=1 lock-failure Wilson-95 UPPER bound is <= the pooled all-station margin=1 rate + 1pp. Pooled rate = 362/93834 = **0.39%** -> bar = **1.39%**.

| station | m1 fired | m1 fail | m1 rate | Wilson-95 CI | m2 rate | day-ATM m1 | raw1min m1 (derates' origin) | derate now | verdict vs bar |
|---|---|---|---|---|---|---|---|---|---|
| KPHX | 4837 | 61 | 1.26% | [0.98%, 1.62%] | 0.10% | 3.15% | 23.3% | KPHX 2F, x0.5 | FAIL |
| KMIA | 5222 | 33 | 0.63% | [0.45%, 0.89%] | 0.21% | 1.51% | 20.3% | (was 2F) | PASS |
| KLAX | 4796 | 29 | 0.60% | [0.42%, 0.87%] | 0.06% | 1.52% | 21.1% | (was 2F) | PASS |
| KAUS | 4373 | 25 | 0.57% | [0.39%, 0.84%] | 0.42% | 1.02% | 15.4% | - | PASS |
| KMSY | 3335 | 16 | 0.48% | [0.30%, 0.78%] | 0.27% | 1.07% | 15.2% | - | PASS |
| NYC | 4657 | 22 | 0.47% | [0.31%, 0.71%] | 0.30% | 0.93% | 13.9% | - | PASS |
| KDEN | 5085 | 24 | 0.47% | [0.32%, 0.70%] | 0.12% | 1.17% | 18.3% | - | PASS |
| KPHL | 5359 | 23 | 0.43% | [0.29%, 0.64%] | 0.28% | 0.94% | 18.0% | (was 2F) | PASS |
| KLAS | 4400 | 17 | 0.39% | [0.24%, 0.62%] | 0.00% | 1.01% | 17.4% | - | PASS |
| KSEA | 5167 | 18 | 0.35% | [0.22%, 0.55%] | 0.06% | 0.91% | 17.9% | (was 2F) | PASS |
| KHOU | 5215 | 15 | 0.29% | [0.17%, 0.47%] | 0.12% | 0.68% | 16.7% | - | PASS |
| KBOS | 5268 | 14 | 0.27% | [0.16%, 0.45%] | 0.00% | 0.73% | 15.0% | - | PASS |
| KSAT | 4169 | 10 | 0.24% | [0.13%, 0.44%] | 0.00% | 0.58% | 15.2% | - | PASS |
| KDFW | 4602 | 11 | 0.24% | [0.13%, 0.43%] | 0.00% | 0.65% | 15.9% | - | PASS |
| KDCA | 2971 | 7 | 0.24% | [0.11%, 0.49%] | 0.10% | 0.53% | 15.0% | - | PASS |
| KSFO | 4870 | 11 | 0.23% | [0.13%, 0.40%] | 0.03% | 0.55% | 15.5% | - | PASS |
| KATL | 5021 | 9 | 0.18% | [0.09%, 0.34%] | 0.00% | 0.50% | 15.9% | - | PASS |
| KMDW | 5228 | 7 | 0.13% | [0.06%, 0.28%] | 0.12% | 0.27% | 10.7% | - | PASS |
| KMSP | 4240 | 5 | 0.12% | [0.05%, 0.28%] | 0.00% | 0.33% | 13.7% | - | PASS |
| KOKC | 5019 | 5 | 0.10% | [0.04%, 0.23%] | 0.00% | 0.27% | 14.4% | - | PASS |

## Verdicts for derated stations

- **KPHX** (CURRENTLY DERATED): sustain3 m1 = 61/4837 = 1.26%, Wilson-95 upper 1.62% vs bar 1.39% -> **FAIL**
- **KMIA** (historically derated, since reverted): sustain3 m1 = 33/5222 = 0.63%, Wilson-95 upper 0.89% vs bar 1.39% -> **PASS**
- **KLAX** (historically derated, since reverted): sustain3 m1 = 29/4796 = 0.60%, Wilson-95 upper 0.87% vs bar 1.39% -> **PASS**
- **KPHL** (historically derated, since reverted): sustain3 m1 = 23/5359 = 0.43%, Wilson-95 upper 0.64% vs bar 1.39% -> **PASS**
- **KSEA** (historically derated, since reverted): sustain3 m1 = 18/5167 = 0.35%, Wilson-95 upper 0.55% vs bar 1.39% -> **PASS**

A FAIL means the derate stays (evidence-only outcome). A PASS licenses relaxing that station's `STATION_MARGIN`/`STATION_SIZE_MULT` in kwx_runner.py, citing these numbers.

Caveat: per-rung fires on the same station-day are correlated, so per-rung Wilson CIs are mildly optimistic about effective n; the ladder-independent day-ATM column is the cross-check. The bar uses the per-rung statistic because the derates were set from it (apples-to-apples).
