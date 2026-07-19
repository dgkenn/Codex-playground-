# Kalshi KXHIGH Settlement-Basis Acquisition + Tail Re-Measurement

**n = 1340 station-days with official CLI ground truth.** Sanity check (does our independently-pulled CLI high actually match Kalshi's settled yes/no?): 1.0000 agreement -- confirms the CLI data pull is correct.

**Baseline (raw 1-min ASOS), margin=1: 71 fires, cond. loss rate given fired = 0.380, worst-case (Wilson-95) loss rate = 0.497, worst-case EV = 0.0931/contract.**

**Candidate ranking at margin=1 (lower worst-case loss rate is better; 'fire rate' = share of the raw-1min baseline's own fire count retained):**

- metar: n=27 (fire rate vs baseline 0.38), cond. loss rate=0.000, worst-case loss rate=0.125, EV worst-case=-0.0371
- roll3: n=38 (fire rate vs baseline 0.54), cond. loss rate=0.026, worst-case loss rate=0.135, EV worst-case=0.1364
- roll5: n=33 (fire rate vs baseline 0.46), cond. loss rate=0.030, worst-case loss rate=0.153, EV worst-case=-0.0203
- gated1min: n=43 (fire rate vs baseline 0.61), cond. loss rate=0.140, worst-case loss rate=0.273, EV worst-case=0.0123
- sixhr: n=47 (fire rate vs baseline 0.66), cond. loss rate=0.149, worst-case loss rate=0.277, EV worst-case=-0.1276
- raw1min: n=71 (fire rate vs baseline 1.00), cond. loss rate=0.380, worst-case loss rate=0.497, EV worst-case=0.0931

**Purest tail-shrink (lowest worst-case loss rate, any fire count): metar** -- drops margin=1 worst-case loss rate from 0.497 to 0.125, but only fires 0.38 of the baseline's rate -- by itself this overstates the deployable win because the Wilson worst-case bound on a thin n=~27-38 sample is wide enough to make its own worst-case EV look mediocre or negative.

**BLUNT VERDICT: the tail SHRINKS, and the deployable rule change is 'roll3'** (best worst-case EV among candidates keeping >=35% of the baseline's fire frequency): margin=1 worst-case loss rate 0.497 (raw1min) -> 0.135 (roll3), conditional loss rate 0.380 -> 0.026, worst-case EV 0.0931 -> **0.1364**/contract, while retaining 0.54 of the baseline's margin=1 fire frequency. **Concrete rule: at margin=1, watch roll3 instead of raw 1-min ASOS.** At margin=2 the raw-1min baseline is already fairly tight (see section 4) and none of the alternates improve worst-case EV there once their thinner fire counts are Wilson-penalized -- the fix is specifically a margin=1 fix, not a universal one.

**EVEN STRONGER, once margin is allowed to move too (section 8): gated1min at margin=2°F is the single best cell in the whole grid** -- n=31 (0.89 of raw-1min's own margin=2 fire count), conditional loss rate 0.000, worst-case loss rate 0.110 (vs raw1min@margin=2's 0.224), worst-case EV 0.0255 (essentially matching raw1min@margin=2's 0.0297, but with the loss tail nearly eliminated). **This is the actual recommended deployable rule: fire the fast raw-1min trigger at strike+2°F as today, but hold execution until the published-METAR running max has ALSO independently reached the bare strike** -- see `first_cross_time_gated()`.

---

## 1. Datasets acquired

| # | Dataset | Status | Notes |
|---|---|---|---|
| 1 | Official NWS CLI daily-max (`/json/cli.py`) | **ACQUIRED, used as ground truth** | 20 stations, one request/station covers the full window. |
| 2 | Published METAR obs, routine+specials (`asos.py`, no report_type filter) | **ACQUIRED, used as candidate** | realtime-available stand-in for ISD (see below). |
| 3 | 6-hourly '1sTTT' max-temp remark group | **ACQUIRED, used as candidate** | parsed from the same METAR text as #2, no extra HTTP calls. |
| 4a | 5-min trailing rolling MEAN of 1-min ASOS | **DERIVED, used as candidate** | no new data -- computed from the already-cached 1-min feed. |
| 4b | 3-min trailing rolling MEAN of 1-min ASOS | **DERIVED, used as candidate** | same. |
| 4c | METAR-gated raw-1min (fast trigger, gated on published-METAR confirmation) | **DERIVED, used as candidate** | combines #2's accuracy with raw-1min's speed; see `first_cross_time_gated()`. |
| 5 | MADIS 5-min ASOS / HFMETAR | **REJECTED** | IEM/MADIS transmits HFMETAR temperature in whole-degree Celsius; cannot be reliably back-converted to whole-degree F, so IEM stores tmpf as missing. Confirmed here: 0 non-missing tmpf values out of all HFMETAR rows probed. |
| 6 | NCEI ISD / ISD-Lite | **REJECTED for this window** | NCEI global-hourly/isd-lite archive directories for 2026 return HTTP 404 in this environment as of the run date (2024/ and 2025/ both return 200), i.e. NCEI has not finalized/published this year's ISD data yet -- a real publication lag, not a fetch bug. Because ISD-Lite's own format spec confirms its hourly temperature IS the routine METAR stream, the 'metar' candidate above is used as the realtime-available stand-in, and the equivalence was spot-validated against real 2025 ISD-Lite data for KDEN. |
| 7 | MADIS QC flags | **OUT** | MADIS distribution requires a registered LDM/THREDDS feed or account; there is no public anonymous HTTP endpoint for per-ob QC flags. Not fabricated or approximated here. |

ISD-Lite-vs-METAR equivalence spot-check (KDEN, real 2025 data, n=167 hourly obs): mean|diff| = 0.046F, max|diff| = 0.080F -- confirms the two are the same underlying feed, so using published METAR as the ISD stand-in for 2026 is not a stretch.


MADIS HFMETAR tmpf-presence probe (one recent day, `report_type=1`): {'KMDW': {'n_rows': 274, 'n_tmpf_present': 0}, 'KDEN': {'n_rows': 0, 'n_tmpf_present': 0}}


## 2. Sanity check: does our CLI ground truth actually match Kalshi's settlement?

Across **1340** station-days with both a CLI report and a Kalshi market: `(cli_high > strike)` matches the market's own settled yes/no result in **1340/1340 (1.0000)**. This validates that our independently-fetched CLI 'high' field really is what Kalshi settles on: (cli_high > strike) should match the market's own yes/no result for essentially 100% of markets. Any disagreement here would mean our CLI station mapping or the IEM CLI parse is wrong, not a real settlement anomaly.


## 3. Day-max accuracy of every candidate vs official CLI high (the core question)

Full-LST-day max of each candidate vs the official CLI daily-max, over every station-day where that candidate had any coverage.

| candidate | coverage | mean bias (F) | MAE (F) | RMSE (F) | exact-match rate | over-read rate | under-read rate | max abs err (F) |
|---|---|---|---|---|---|---|---|---|
| raw 1-min ASOS (baseline, current live rule) | 1274/1340 (0.951) | -0.403 | 1.447 | 3.444 | 0.405 | 0.458 | 0.137 | 52.0 |
| 3-min trailing rolling MEAN of 1-min ASOS (derived, no new data) | 1274/1340 (0.951) | -0.891 | 1.160 | 3.094 | 0.290 | 0.344 | 0.366 | 24.0 |
| 5-min trailing rolling MEAN of 1-min ASOS (derived, no new data) | 1274/1340 (0.951) | -1.049 | 1.191 | 3.106 | 0.190 | 0.266 | 0.544 | 24.0 |
| published METAR obs (routine+specials; realtime stand-in for ISD) | 1340/1340 (1.000) | -0.819 | 0.821 | 1.062 | 0.317 | 0.001 | 0.681 | 3.0 |
| 6-hourly METAR '1sTTT' max-temp remark group (4x/day, coarse) | 1340/1340 (1.000) | 0.122 | 0.210 | 0.946 | 0.115 | 0.473 | 0.412 | 11.9 |

(bias > 0 means the candidate reads HIGH vs the official CLI settlement -- the exact direction of the loss mode described in the task brief.)


## 4. RE-RUN tail/loss-rate/worst-case-EV, margin=1 and margin=2 -- did the tail shrink?


### Margin = 1°F

| candidate | n fired | win rate | cond. loss rate | worst-case loss rate (Wilson-95) | mean PnL/ct | t | EV (point) | **EV (worst-case)** |
|---|---|---|---|---|---|---|---|---|
| **raw1min (BASELINE)** | 71 | 0.620 | 0.380 | 0.497 | 0.2094 | 4.15 | 0.2094 | **0.0931** |
| roll3 | 38 | 0.974 | 0.026 | 0.135 | 0.2451 | 5.42 | 0.2451 | **0.1364** |
| roll5 | 33 | 0.970 | 0.030 | 0.153 | 0.1026 | 4.08 | 0.1026 | **-0.0203** |
| metar | 27 | 1.000 | 0.000 | 0.125 | 0.0874 | 3.10 | 0.0874 | **-0.0371** |
| sixhr | 47 | 0.851 | 0.149 | 0.277 | 0.0003 | 0.03 | 0.0003 | **-0.1276** |
| gated1min | 43 | 0.860 | 0.140 | 0.273 | 0.1454 | 3.46 | 0.1454 | **0.0123** |

### Margin = 2°F

| candidate | n fired | win rate | cond. loss rate | worst-case loss rate (Wilson-95) | mean PnL/ct | t | EV (point) | **EV (worst-case)** |
|---|---|---|---|---|---|---|---|---|
| **raw1min (BASELINE)** | 35 | 0.914 | 0.086 | 0.224 | 0.1678 | 4.60 | 0.1678 | **0.0297** |
| roll3 | 19 | 0.947 | 0.053 | 0.246 | 0.0279 | 1.38 | 0.0279 | **-0.1658** |
| roll5 | 15 | 1.000 | 0.000 | 0.204 | 0.0081 | 1.04 | 0.0081 | **-0.1957** |
| metar | 8 | 1.000 | 0.000 | 0.324 | 0.0454 | 1.07 | 0.0454 | **-0.2790** |
| sixhr | 23 | 0.870 | 0.130 | 0.321 | -0.0126 | -1.58 | -0.0126 | **-0.2034** |
| gated1min | 31 | 1.000 | 0.000 | 0.110 | 0.1358 | 3.59 | 0.1358 | **0.0255** |

## 5. Full margin sweep (1-5°F), all candidates


### raw 1-min ASOS (baseline, current live rule)

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 71 | 0.620 | 0.380 | 0.497 | 0.2094 | 4.15 | 0.0931 |
| 2 | 35 | 0.914 | 0.086 | 0.224 | 0.1678 | 4.60 | 0.0297 |
| 3 | 19 | 0.842 | 0.158 | 0.376 | -0.0068 | -0.44 | -0.2246 |
| 4 | 7 | 0.714 | 0.286 | 0.641 | -0.0242 | -1.16 | -0.3796 |
| 5 | 4 | 0.500 | 0.500 | 0.850 | -0.0424 | -1.26 | -0.3924 |

### 3-min trailing rolling MEAN of 1-min ASOS (derived, no new data)

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 38 | 0.974 | 0.026 | 0.135 | 0.2451 | 5.42 | 0.1364 |
| 2 | 19 | 0.947 | 0.053 | 0.246 | 0.0279 | 1.38 | -0.1658 |
| 3 | 6 | 0.833 | 0.167 | 0.564 | -0.0265 | -1.10 | -0.4233 |
| 4 | 3 | 0.667 | 0.333 | 0.792 | -0.0530 | -1.22 | -0.5120 |
| 5 | 3 | 0.667 | 0.333 | 0.792 | -0.0530 | -1.22 | -0.5120 |

### 5-min trailing rolling MEAN of 1-min ASOS (derived, no new data)

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 33 | 0.970 | 0.030 | 0.153 | 0.1026 | 4.08 | -0.0203 |
| 2 | 15 | 1.000 | 0.000 | 0.204 | 0.0081 | 1.04 | -0.1957 |
| 3 | 4 | 1.000 | 0.000 | 0.490 | 0.0000 | n/a | -0.4899 |
| 4 | 2 | 1.000 | 0.000 | 0.658 | 0.0000 | n/a | -0.6576 |
| 5 | 0 | - | - | - | - | - | - |

### published METAR obs (routine+specials; realtime stand-in for ISD)

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 27 | 1.000 | 0.000 | 0.125 | 0.0874 | 3.10 | -0.0371 |
| 2 | 8 | 1.000 | 0.000 | 0.324 | 0.0454 | 1.07 | -0.2790 |
| 3 | 4 | 1.000 | 0.000 | 0.490 | 0.0000 | n/a | -0.4899 |
| 4 | 3 | 1.000 | 0.000 | 0.561 | 0.0000 | n/a | -0.5615 |
| 5 | 2 | 1.000 | 0.000 | 0.658 | 0.0000 | n/a | -0.6576 |

### 6-hourly METAR '1sTTT' max-temp remark group (4x/day, coarse)

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 47 | 0.851 | 0.149 | 0.277 | 0.0003 | 0.03 | -0.1276 |
| 2 | 23 | 0.870 | 0.130 | 0.321 | -0.0126 | -1.58 | -0.2034 |
| 3 | 8 | 0.625 | 0.375 | 0.694 | -0.0397 | -1.61 | -0.3590 |
| 4 | 6 | 0.667 | 0.333 | 0.700 | -0.0318 | -1.13 | -0.3984 |
| 5 | 4 | 0.750 | 0.250 | 0.699 | -0.0027 | -1.07 | -0.4520 |

### raw 1-min trigger, GATED on published-METAR confirmation (>=strike) before firing

| margin | n fired | win rate | cond. loss rate | worst-case loss rate | mean PnL | t | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | 43 | 0.860 | 0.140 | 0.273 | 0.1454 | 3.46 | 0.0123 |
| 2 | 31 | 1.000 | 0.000 | 0.110 | 0.1358 | 3.59 | 0.0255 |
| 3 | 16 | 1.000 | 0.000 | 0.194 | 0.0111 | 2.33 | -0.1825 |
| 4 | 5 | 1.000 | 0.000 | 0.434 | 0.0000 | n/a | -0.4345 |
| 5 | 2 | 1.000 | 0.000 | 0.658 | 0.0000 | n/a | -0.6576 |

## 6. Residual-miss characterization at margin=1

Of the **27** raw-1min margin=1 locked-YES-settled-NO misses:

- Fixed by switching to roll5 (5-min rolling mean): **0**
- Fixed by switching to roll3 (3-min rolling mean): **0**
- Fixed by switching to published METAR: **0**
- Fixed by the METAR-gated raw-1min rule (gated1min): **0**
- STILL missed even by roll5: **1** (genuine CLI-vs-realtime-proxy methodology gap, not a filterable transient spike)

| ticker | date | strike | CLI high | roll3 | roll5 | metar | gated1min |
|---|---|---|---|---|---|---|---|
| KXHIGHDEN-26JUL09-T91 | 2026-07-09 | 91 | 91 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHDEN-26JUN27-T97 | 2026-06-27 | 97 | 97 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHDEN-26JUN18-T88 | 2026-06-18 | 88 | 88 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHDEN-26JUN16-T93 | 2026-06-16 | 93 | 93 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHMIA-26JUN26-T95 | 2026-06-26 | 95 | 92 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHMIA-26JUN16-T95 | 2026-06-16 | 95 | 95 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHMIA-26MAY16-T91 | 2026-05-16 | 91 | 90 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTBOS-26MAY16-T80 | 2026-05-16 | 80 | 80 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSEA-26JUL10-T78 | 2026-07-10 | 78 | 78 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSEA-26JUN27-T70 | 2026-06-27 | 70 | 70 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSFO-26JUL02-T71 | 2026-07-02 | 71 | 71 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSFO-26JUN30-T73 | 2026-06-30 | 73 | 73 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSFO-26JUN25-T70 | 2026-06-25 | 70 | 70 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTSFO-26MAY18-T80 | 2026-05-18 | 80 | 80 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTATL-26JUL16-T93 | 2026-07-16 | 93 | 93 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTATL-26JUL11-T94 | 2026-07-11 | 94 | 94 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHTATL-26MAY30-T85 | 2026-05-30 | 85 | 85 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTATL-26MAY28-T88 | 2026-05-28 | 88 | 88 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTDAL-26JUN06-T89 | 2026-06-06 | 89 | 89 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHTSATX-26MAY23-T85 | 2026-05-23 | 85 | 85 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTOKC-26JUN12-T91 | 2026-06-12 | 91 | 91 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHTOKC-26MAY28-T84 | 2026-05-28 | 84 | 84 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHTHOU-26MAY22-T90 | 2026-05-22 | 90 | 90 | did_not_fire | did_not_fire | did_not_fire | still_missed |
| KXHIGHPHIL-26JUL11-T89 | 2026-07-11 | 89 | 89 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHPHIL-26JUN02-T80 | 2026-06-02 | 80 | 80 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHLAX-26JUN28-T72 | 2026-06-28 | 72 | 71 | did_not_fire | did_not_fire | did_not_fire | did_not_fire |
| KXHIGHLAX-26MAY24-T69 | 2026-05-24 | 69 | 68 | still_missed | still_missed | did_not_fire | did_not_fire |

## 7. Candidate ranking at margin=1 (min. n_fired=5, ranked by worst-case loss rate)

| rank | candidate | n fired | cond. loss rate | worst-case loss rate | EV worst-case | fire rate vs raw1min baseline |
|---|---|---|---|---|---|---|
| 1 | metar | 27 | 0.000 | 0.125 | -0.0371 | 0.380 |
| 2 | roll3 | 38 | 0.026 | 0.135 | 0.1364 | 0.535 |
| 3 | roll5 | 33 | 0.030 | 0.153 | -0.0203 | 0.465 |
| 4 | gated1min | 43 | 0.140 | 0.273 | 0.0123 | 0.606 |
| 5 | sixhr | 47 | 0.149 | 0.277 | -0.1276 | 0.662 |
| 6 | raw1min | 71 | 0.380 | 0.497 | 0.0931 | 1.000 |

## 8. GLOBAL ranking across every (candidate, margin) combo -- the actual best deployable rule

Not limited to margin=1: every (candidate, margin) cell with n_fired>=8 that retains >=50% of the raw-1min baseline's OWN fire count at that same margin, ranked by worst-case loss rate. This is what finds combos like 'gated1min at margin=2', not just 'candidate X at margin=1'.

| rank | candidate | margin | n fired | fire rate vs raw1min @ same margin | cond. loss rate | worst-case loss rate | EV worst-case |
|---|---|---|---|---|---|---|---|
| 1 | gated1min | 2 | 31 | 0.89 | 0.000 | 0.110 | 0.0255 |
| 2 | roll3 | 1 | 38 | 0.54 | 0.026 | 0.135 | 0.1364 |
| 3 | gated1min | 3 | 16 | 0.84 | 0.000 | 0.194 | -0.1825 |
| 4 | raw1min | 2 | 35 | 1.00 | 0.086 | 0.224 | 0.0297 |
| 5 | roll3 | 2 | 19 | 0.54 | 0.053 | 0.246 | -0.1658 |
| 6 | gated1min | 1 | 43 | 0.61 | 0.140 | 0.273 | 0.0123 |
| 7 | sixhr | 1 | 47 | 0.66 | 0.149 | 0.277 | -0.1276 |
| 8 | sixhr | 2 | 23 | 0.66 | 0.130 | 0.321 | -0.2034 |
| 9 | raw1min | 3 | 19 | 1.00 | 0.158 | 0.376 | -0.2246 |
| 10 | raw1min | 1 | 71 | 1.00 | 0.380 | 0.497 | 0.0931 |
