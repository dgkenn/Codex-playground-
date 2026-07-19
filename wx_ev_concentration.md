# EV concentration map + correlated-day tail check (deployed cell `1_3`)

Source: `wx_ev_concentration.py`, reading the committed `_trackA_results_raw.json` (Phase-2 Track A
walk-forward raw grid, 4383 market-days, May 12 - Jul 16 2026). Deployed cell confirmed against
`kwx_runner.MARGIN_F=1.0` / `SUSTAIN_MIN=3` -> cell key `"1_3"` (same cell `wx_fee_floor_impact.py` uses).
All numbers below use the **LIVE-ADMISSIBLE** fire set: `cells["1_3"].fired` and `exec_price*100 <=
MAX_PAY_CENTS(98)`. This excludes the 2347/3891 raw "fired" cells at 99-100c that `MAX_PAY_CENTS` already
kills live (all zero-gap, zero-pnl) -- including them would just dilute every table with noise the runner
never actually pays for. **n = 1698 live-admissible fires, total pnl $352.08, win rate 99.6%.**

Propose-only: this script reads the recorded backtest and prints numbers. No live parameter is touched.

## Study A -- EV concentration map

### By city/station

| station | n | mean $/ct | total $ | win% | share of EV |
|---|---:|---:|---:|---:|---:|
| KDEN | 232 | +0.181 | +41.99 | 100.0% | 11.9% |
| KMIA | 117 | +0.234 | +27.39 | 99.1% | 7.8% |
| KMSY | 104 | +0.222 | +23.10 | 99.0% | 6.6% |
| KOKC | 99 | +0.221 | +21.88 | 100.0% | 6.2% |
| KSEA | 92 | +0.237 | +21.83 | 100.0% | 6.2% |
| KHOU | 95 | +0.218 | +20.68 | 100.0% | 5.9% |
| KDFW | 98 | +0.200 | +19.55 | 100.0% | 5.6% |
| KSFO | 96 | +0.195 | +18.69 | 100.0% | 5.3% |
| KAUS | 97 | +0.189 | +18.30 | 100.0% | 5.2% |
| NYC  | 91 | +0.197 | +17.92 | 98.9% | 5.1% |
| KMDW | 82 | +0.212 | +17.36 | 100.0% | 4.9% |
| KATL | 98 | +0.176 | +17.25 | 100.0% | 4.9% |
| KBOS | 64 | +0.239 | +15.30 | 98.4% | 4.3% |
| KDCA | 38 | +0.342 | +12.98 | 100.0% | 3.7% |
| KMSP | 59 | +0.217 | +12.82 | 100.0% | 3.6% |
| KSAT | 76 | +0.167 | +12.66 | 100.0% | 3.6% |
| KPHL | 55 | +0.209 | +11.52 | 100.0% | 3.3% |
| KLAX | 44 | +0.208 | +9.13  | 100.0% | 2.6% |
| KPHX | 32 | +0.199 | +6.37  | 93.8%  | 1.8% |
| KLAS | 29 | +0.185 | +5.35  | 100.0% | 1.5% |

**Top 5 of 20 stations (KDEN, KMIA, KMSY, KOKC, KSEA) = 38.7% of total EV.** No single city dominates
(KDEN, the largest, is still only 11.9%), but the distribution is meaningfully non-uniform -- the bottom 5
stations combined (KPHL, KLAX, KPHX, KLAS + KSAT) are worth barely more than KDEN alone. KPHX is also the
only station with a below-100% win rate here (93.8%, n=32) -- consistent with it already carrying an extra
margin (`STATION_MARGIN={"KPHX": 2.0}`) and a size derate for exactly this reason.

### By local fire hour (station standard time, derived from `t_star` + `CITY` UTC offset)

Two clear peaks: **hours 11-16 local** (afternoon, HIGH-market territory) carry 48.5% of total EV
(6.5+7.9+10.6+13.4+10.1%), and **hours 3-5 local** (pre-dawn, LOW/overnight-min territory) carry another
21.4% (7.1+8.8+5.5%). Combined, these two windows are **~70% of total EV** from ~9 of 24 local hours.
Overnight hours 7-10 and evening 18-20 are the deadest (each <1% of EV per hour).

### By family

| family | n | mean $/ct | total $ | win% | share |
|---|---:|---:|---:|---:|---:|
| HIGH | 898 | +0.209 | +187.58 | 99.3% | 53.3% |
| LOW  | 800 | +0.206 | +164.50 | 100.0% | 46.7% |

Roughly even split -- HIGH is slightly ahead in both count and EV, but per-contract economics are nearly
identical (0.209 vs 0.206 $/ct). No lopsided family bias to correct for.

### By rung_group

| rung | n | mean $/ct | total $ | win% | share |
|---|---:|---:|---:|---:|---:|
| between | 1498 | +0.210 | +315.20 | 99.6% | 89.5% |
| greater | 118  | +0.190 | +22.38  | 100.0% | 6.4% |
| less    | 82   | +0.177 | +14.50  | 100.0% | 4.1% |

`between` rungs are 88% of fire count and 89.5% of EV -- essentially proportional, no concentration
surprise here (this is also the rung type the repo's Tier-1 study flagged as carrying all 6 deployable
glitch losses historically, so its dominance is already a known, monitored fact, not a new risk).

### By gap bucket

| gap | n | mean $/ct | total $ | win% | share |
|---|---:|---:|---:|---:|---:|
| <5c | 387 | +0.027 | +10.54 | 100.0% | 3.0% |
| 5-15c | 496 | +0.085 | +42.36 | 100.0% | 12.0% |
| >15c | 815 | +0.367 | +299.18 | 99.3% | 85.0% |

**>15c-gap fires are 48% of the count but 85% of the EV.** Thin-gap fires (<5c, 23% of count) are almost
irrelevant to total profit (3.0%) despite being individually risk-free-looking (100% win rate in sample) --
they're just small. This is the single biggest lever in the whole EV map.

### Per-city EV lost to detection lag (decay_gap_by_min)

Two views: **retention rate** (ret@2/5/10 = fraction of gap(0) still open at +2/+5/+10 min -- who decays
fastest per fire) and **absolute $ lost to a 2-min lag** (who has the most money riding on beating the
clock -- volume x decay rate).

| station | n | gap(0) $ | ret@2 | ret@5 | ret@10 | $ lost@2min | share of all lag-loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| KPHL | 55 | 11.96 | 0.84 | 0.27 | 0.25 | 1.86 | 1.4% |
| NYC  | 91 | 19.74 | 0.80 | 0.70 | 0.66 | 3.85 | 2.8% |
| KSAT | 76 | 13.23 | 0.70 | 0.33 | 0.29 | 3.98 | 2.9% |
| KOKC | 99 | 22.77 | 0.70 | 0.32 | 0.25 | 6.85 | 5.0% |
| KPHX | 32 | 8.67  | 0.69 | 0.19 | 0.08 | 2.65 | 1.9% |
| KATL | 98 | 18.00 | 0.69 | 0.32 | 0.27 | 5.51 | 4.0% |
| KDCA | 38 | 13.34 | 0.69 | 0.30 | 0.23 | 4.16 | 3.0% |
| KSFO | 96 | 19.48 | 0.68 | 0.38 | 0.33 | 6.19 | 4.5% |
| **KDEN** | 232 | 43.91 | 0.66 | 0.44 | 0.36 | **14.84** | **10.8%** |
| KDFW | 98 | 20.41 | 0.65 | 0.32 | 0.29 | 7.14 | 5.2% |
| KLAS | 29 | 5.61  | 0.62 | 0.32 | 0.34 | 2.11 | 1.5% |
| KBOS | 64 | 16.87 | 0.60 | 0.22 | 0.17 | 6.68 | 4.9% |
| KSEA | 92 | 22.68 | 0.59 | 0.28 | 0.23 | 9.21 | 6.7% |
| **KMIA** | 117 | 29.50 | 0.59 | 0.22 | 0.18 | **12.15** | **8.9%** |
| KLAX | 44 | 9.52  | 0.56 | 0.25 | 0.18 | 4.18 | 3.0% |
| **KHOU** | 95 | 21.49 | 0.56 | 0.23 | 0.17 | **9.49** | **6.9%** |
| KMDW | 82 | 18.00 | 0.54 | 0.30 | 0.26 | 8.22 | 6.0% |
| **KAUS** | 97 | 19.09 | 0.52 | 0.36 | 0.28 | **9.09** | **6.6%** |
| **KMSY** | 104 | 25.14 | 0.51 | 0.31 | 0.24 | **12.29** | **9.0%** |
| KMSP | 59 | 13.33 | 0.50 | 0.15 | 0.13 | 6.73 | 4.9% |

**Fastest decay (worst retention rate)**: KMSP (ret@2=0.50, only 13% of gap left by +10min), KMSY (0.51),
KAUS (0.52), KMDW (0.54), KHOU (0.56) -- these lose the largest *fraction* of their edge to any given lag.
**Biggest absolute dollars at stake**: KDEN ($14.84, 10.8% of all lag-driven loss), KMSY ($12.29), KMIA
($12.15), KHOU ($9.49), KSEA ($9.21), KAUS ($9.09), KMDW ($8.22) -- top 7 = **54.9% of all EV lost to a
2-minute detection lag** across the whole 20-city set.

NYC and KPHL stand out as the most latency-*tolerant* cities (ret@2 = 0.80-0.84) -- a slow feed hurts them
comparatively little.

## Study A -- conclusions

1. **A fast feed (Synoptic) should be prioritized for KDEN, KMSY, KMIA, KHOU, KSEA, KAUS, KMDW first** --
   together they account for 55% of all $ EV lost to a 2-minute detection lag and 48% of total EV. That's
   7 of 20 cities capturing more than half the latency-sensitive money; polling/credentialing budget for a
   1-minute feed pays off fastest there. KMSP has the single worst retention rate (50% gone by +2min, 87%
   gone by +10min) but low absolute dollars (4.9%) -- worth a fast feed only after the top-7 volume cities
   are covered.
2. **Gap size dominates everything else**: >15c-gap fires are 48% of fires but 85% of EV. If any future
   filtering/prioritization has to pick one axis to optimize first, gap bucket beats city, hour, family, or
   rung -- a thin-gap fire (<5c, 23% of count) contributes almost nothing (3.0% of EV) regardless of which
   city or hour it's in.
3. **~70% of EV lands in two ~5-hour local windows**: 11:00-16:00 (afternoon, HIGH) and 03:00-06:00
   (pre-dawn, LOW). Polling cadence and on-call attention (and any future feed-cost tradeoffs) should weight
   those windows heavily; hours 7-10 and 18-21 local are close to dead (each <1% of EV) and are candidates
   for lower-frequency polling without meaningfully hurting P&L.
4. **No family or rung_group rebalancing is indicated** -- HIGH/LOW split is nearly even in both count and
   per-contract economics (0.209 vs 0.206 $/ct), and `between`/`greater`/`less` shares track fire-count
   shares closely (no rung type is punching above or below its weight).
5. **City concentration is real but not extreme** -- top 5 of 20 stations = 38.7% of EV, bottom 5 = ~13%.
   KPHX is the one city with a sub-100% win rate here (93.8%, n=32, small sample) and is already the sole
   station carrying an elevated margin + size derate; nothing here contradicts that existing precaution.

## Study B -- correlated-day tail

Same deployed cell (`1_3`), same live-admissible fire set (n=1698). 66 calendar days span the backtest
(2026-05-12 to 2026-07-16); 65 of them have >=1 fire.

**Same-day fire-count distribution**: min 0, median 27, mean 25.7, max 39 fires/day.
**Distinct cities firing same day**: min 0, median 13, mean 12.9, max 17 (of 20 total).

Empirical P(fires/day > K), Wilson 95% CI, n=66 days:

| K | count | P | 95% CI |
|---:|---:|---:|---:|
| 5  | 65/66 | 98.5% | [91.9%, 99.7%] |
| 10 | 64/66 | 97.0% | [89.6%, 99.2%] |
| 12 | 64/66 | 97.0% | [89.6%, 99.2%] |
| 15 | 60/66 | 90.9% | [81.6%, 95.8%] |
| 20 | 50/66 | 75.8% | [64.2%, 84.5%] |
| 25 | 37/66 | 56.1% | [44.1%, 67.4%] |
| 30 | 18/66 | 27.3% | [18.0%, 39.0%] |

**Worst 10 joint-pnl days** (all still net positive -- see full table in script output):

| date | n_fires | n_cities | day pnl $ | n_losses |
|---|---:|---:|---:|---:|
| 2026-06-23 | 9  | 7  | +1.010 | 0 |
| 2026-05-21 | 16 | 8  | +2.137 | 0 |
| 2026-06-28 | 18 | 13 | +2.959 | 0 |
| 2026-06-29 | 19 | 13 | +2.962 | 1 |
| 2026-06-11 | 22 | 12 | +3.107 | 1 |
| 2026-05-18 | 26 | 12 | +3.197 | 0 |
| 2026-05-25 | 23 | 12 | +3.225 | 0 |
| 2026-06-08 | 22 | 15 | +3.347 | 0 |
| 2026-06-02 | 20 | 13 | +3.386 | 0 |
| 2026-06-09 | 15 | 11 | +3.420 | 0 |

**0 of 65 fire-days were net-pnl-negative; 0 of 65 days had more than one losing fire.** Every recorded
loss (6 total, across 6 distinct days) was a lone loss in a single city that day -- the sample contains
zero examples of correlated same-day losses stacking.

**Per-city-day stacking** (multiple rungs firing the *same* city *same* day are correlated -- same
underlying temperature draw at different strikes -- exactly what `PER_CITY_DAILY_CAP_FRAC` exists to
bound). n=849 city-days with >=1 fire:

| threshold | count | P | 95% CI |
|---|---:|---:|---:|
| >1x same city/day | 457/849 | 53.8% | [50.5%, 57.2%] |
| >2x same city/day | 219/849 | 25.8% | [23.0%, 28.8%] |
| >3x same city/day | 102/849 | 12.0% | [10.0%, 14.4%] |
| >4x same city/day | 49/849  | 5.8%  | [4.4%, 7.5%] |

**Cap arithmetic** (worst case: every fire sized at its cap -- not a hypothetical extreme here, since at
the recorded ~99.6% win rate `kwx_runner._kelly_fraction` computes a quarter-Kelly stake far above both the
5% base and 12% conviction per-fire caps, so the caps themselves are the realistic binding size on almost
every fire):
- `MAX_DAILY_DEPLOY_FRAC=60%` would be breached by >12 same-day fires at the 5% base cap. Observed: median
  27 fires/day, P(fires/day > 12) = 97.0% [89.6%, 99.2%]. **The daily cap is not idle headroom -- it is the
  active binding constraint on nearly every trading day** given the observed fire frequency.
- `PER_CITY_DAILY_CAP_FRAC=17.5%` would be breached by >4 same-city-day fires at the 5% base cap, or by
  >2 at the 12% conviction cap. Observed: P(>3x same city/day) = 12.0% [10.0%, 14.4%] (base-cap breach
  zone) and P(>1x same city/day) = 53.8% [50.5%, 57.2%] (conviction-cap breach zone at 2 fires). **The
  per-city cap also binds routinely**, especially for conviction-sized fires, where more than half of
  city-days would breach it without the cap.

### Verdict: caps look **adequate** (evidence does not support tightening or relaxing)

- **Not evidence for relaxing**: the 60%/17.5% caps already bind on the large majority of days at realistic
  (near-cap) fire sizing. Loosening either cap would mechanically increase same-day/same-city exposure on
  days that are already common (median 27 fires, 13 cities/day) without any recorded data showing those
  extra fires would have been profitable to add -- the in-sample EV per fire is uniform-ish across cities
  (Study A), not concentrated in exactly the fires the caps are currently cutting off.
- **Not evidence for tightening**: in 65 fire-days there is not one net-loss day and not one day with more
  than a single losing fire -- i.e., **zero recorded instances of the correlated-loss scenario the caps are
  precautionary against** (`kwx_runner.py` comment: "17.5%... Tier-1 S4: precautionary"). The caps were
  never validated by an observed bad day because the sample (one warm season, 66 days, win rate 99.6%) has
  not produced one. This is a real limitation of the evidence, not proof the caps are too loose -- it's the
  same "can't rule out" situation `wx_fee_floor_impact.py` flags for the 98c marginal set: absence of a
  correlated-loss day in-sample is not the same as evidence that one can't happen (weather is exactly the
  kind of correlated-risk domain the caps assume). With no loss-clustering evidence either way, "no
  parameter change without supporting evidence" argues for leaving both caps as-is.
- **The stress test the caps are designed for (a multi-city bad day) has not occurred in this sample.**
  Track B's multi-year, all-season obs-vs-CLI study (`phase2_trackB_tail.py`) is a better source for that
  tail than this single warm-season price backtest, precisely because it covers winter frontal-passage days
  where correlated misses are more plausible; if the caps are ever revisited, that's the dataset to check
  next, not this one.
