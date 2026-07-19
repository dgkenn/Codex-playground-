# Phase 2 / Track B -- Multi-Year, All-Season Obs-vs-CLI Tail Risk
Run date: 2026-07-18T18:59:55.493115+00:00
Measures the ASOS-observed-vs-official-CLI-settlement disagreement ('lock failure') that drives the Kalshi KXHIGH nowcast strategy's tail, across as many years and all four seasons as ASOS 1-min + NWS CLI data allow -- independent of Kalshi's own ~10-week, warm-season-only price history, which structurally cannot see this.

**Coverage:** 20 stations x years requested [2021, 2022, 2023, 2024, 2025, 2026] -> years actually present in data: **['2021', '2022', '2023', '2024', '2025', '2026']**. Station-years processed: 120. Total compact station-day records: 40480. Station-days with CLI ground truth: 39775.

## Methodology notes
- **Candidates**: `raw1min` (unfiltered running max, sustain=1 -- the original live rule), `glitch1` (glitch-filter only, sustain=1), `glitch_sustain3` (glitch filter + 3-consecutive-minute sustain requirement), `roll3` (3-min trailing rolling MEAN of glitch-filtered obs), `metar_gated` (raw1min trigger, withheld until independently-published METAR max reaches the BARE strike).
- **Synthetic strike ladders** (no historical KXHIGH listings exist before 2026): `near_money` = strikes {C-3,C-2,C-1,C,C+1} anchored on the actual CLI high C for that day (a proxy for a day-ahead forecast, which is unbiased around the eventual outcome on average); `wide` = {C-6..C+3}. Widening the ladder mechanically DILUTES the conditional loss rate (adds strikes that are deep-in-the-money and essentially always correctly win), so `near_money` is the more representative number and `wide` is reported only as a sensitivity check -- both are shown below, be explicit this is a stated modeling choice.
- **Lock-failure**: for strike K, margin m: fired iff candidate's sustained value >= K+m (metar_gated additionally requires published METAR max >= K, bare); lock-failure iff fired AND K >= CLI_high (i.e. the strike settles NO under the official record).
- **DAYFLAG** (ladder-width-independent cross-check): per station-day, did the candidate's sustained value clear CLI_high+margin at all (equivalent to the single most-exposed at-the-money strike K=CLI_high)? This needs no ladder-width assumption.

## 1. Headline: raw1min baseline, all years/seasons pooled (near_money ladder)
| margin | n fired | n lock-fail | conditional loss (point) | Wilson-95 worst-case |
|---|---|---|---|---|
| 1 | 116544 | 19388 | 16.6% | 16.9% |
| 2 | 85011 | 3325 | 3.9% | 4.0% |
| 3 | 53587 | 2223 | 4.1% | 4.3% |

Same, `wide` ladder (sensitivity -- expect materially lower due to dilution):

| margin | n fired | n lock-fail | conditional loss (point) | Wilson-95 worst-case |
|---|---|---|---|---|
| 1 | 218421 | 21611 | 9.9% | 10.0% |
| 2 | 185842 | 5201 | 2.8% | 2.9% |
| 3 | 153310 | 3787 | 2.5% | 2.5% |

## 2. All candidates x margin, near_money ladder, all years/seasons pooled
| candidate | margin | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|---|
| raw1min | 1 | 116544 | 19388 | 16.6% | 16.9% |
| raw1min | 2 | 85011 | 3325 | 3.9% | 4.0% |
| raw1min | 3 | 53587 | 2223 | 4.1% | 4.3% |
| glitch1 | 1 | 114686 | 17648 | 15.4% | 15.6% |
| glitch1 | 2 | 82223 | 1312 | 1.6% | 1.7% |
| glitch1 | 3 | 49988 | 417 | 0.8% | 0.9% |
| glitch_sustain3 | 1 | 93785 | 362 | 0.4% | 0.4% |
| glitch_sustain3 | 2 | 61238 | 66 | 0.1% | 0.1% |
| glitch_sustain3 | 3 | 29085 | 58 | 0.2% | 0.3% |
| roll3 | 1 | 90151 | 187 | 0.2% | 0.2% |
| roll3 | 2 | 57630 | 119 | 0.2% | 0.2% |
| roll3 | 3 | 25507 | 104 | 0.4% | 0.5% |
| metar_gated | 1 | 100894 | 7990 | 7.9% | 8.1% |
| metar_gated | 2 | 80380 | 935 | 1.2% | 1.2% |
| metar_gated | 3 | 51335 | 535 | 1.0% | 1.1% |

## 3. Ladder-independent DAYFLAG cross-check (single ATM boundary strike K=CLI_high)
Fraction of ALL station-days (unconditional, not conditional on firing) where the candidate's sustained value cleared CLI_high+margin -- i.e. the single most-exposed at-the-money strike would have fired-and-lost, by definition (K=C always settles NO).

| candidate | margin | n days | n exposure-days | rate |
|---|---|---|---|---|
| raw1min | 1 | 35110 | 17269 | 49.185% |
| raw1min | 2 | 35110 | 2119 | 6.035% |
| raw1min | 3 | 35110 | 1206 | 3.435% |
| glitch1 | 1 | 35110 | 16583 | 47.232% |
| glitch1 | 2 | 35110 | 1065 | 3.033% |
| glitch1 | 3 | 35110 | 247 | 0.704% |
| glitch_sustain3 | 1 | 35091 | 327 | 0.932% |
| glitch_sustain3 | 2 | 35091 | 35 | 0.100% |
| glitch_sustain3 | 3 | 35091 | 31 | 0.088% |
| roll3 | 1 | 35110 | 124 | 0.353% |
| roll3 | 2 | 35110 | 63 | 0.179% |
| roll3 | 3 | 35110 | 56 | 0.159% |
| metar_gated | 1 | 35110 | 7978 | 22.723% |
| metar_gated | 2 | 35110 | 924 | 2.632% |
| metar_gated | 3 | 35110 | 526 | 1.498% |

## 4. Seasonal breakdown (near_money ladder)

### raw1min
| season | margin | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|---|
| DJF | 1 | 28820 | 4065 | 14.1% | 14.5% |
| DJF | 2 | 20977 | 1105 | 5.3% | 5.6% |
| DJF | 3 | 13161 | 944 | 7.2% | 7.6% |
| MAM | 1 | 31934 | 5564 | 17.4% | 17.8% |
| MAM | 2 | 23366 | 904 | 3.9% | 4.1% |
| MAM | 3 | 14821 | 569 | 3.8% | 4.2% |
| JJA | 1 | 28999 | 5395 | 18.6% | 19.1% |
| JJA | 2 | 21183 | 609 | 2.9% | 3.1% |
| JJA | 3 | 13394 | 230 | 1.7% | 2.0% |
| SON | 1 | 26791 | 4364 | 16.3% | 16.7% |
| SON | 2 | 19485 | 707 | 3.6% | 3.9% |
| SON | 3 | 12211 | 480 | 3.9% | 4.3% |

### glitch_sustain3
| season | margin | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|---|
| DJF | 1 | 24087 | 75 | 0.3% | 0.4% |
| DJF | 2 | 15803 | 29 | 0.2% | 0.3% |
| DJF | 3 | 7618 | 27 | 0.4% | 0.5% |
| MAM | 1 | 25458 | 110 | 0.4% | 0.5% |
| MAM | 2 | 16620 | 9 | 0.1% | 0.1% |
| MAM | 3 | 7864 | 7 | 0.1% | 0.2% |
| JJA | 1 | 22618 | 122 | 0.5% | 0.6% |
| JJA | 2 | 14723 | 16 | 0.1% | 0.2% |
| JJA | 3 | 6931 | 13 | 0.2% | 0.3% |
| SON | 1 | 21622 | 55 | 0.3% | 0.3% |
| SON | 2 | 14092 | 12 | 0.1% | 0.1% |
| SON | 3 | 6672 | 11 | 0.2% | 0.3% |

### metar_gated
| season | margin | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|---|
| DJF | 1 | 26037 | 2022 | 7.8% | 8.1% |
| DJF | 2 | 19854 | 310 | 1.6% | 1.7% |
| DJF | 3 | 12356 | 254 | 2.1% | 2.3% |
| MAM | 1 | 27240 | 2149 | 7.9% | 8.2% |
| MAM | 2 | 21977 | 233 | 1.1% | 1.2% |
| MAM | 3 | 14199 | 116 | 0.8% | 1.0% |
| JJA | 1 | 24175 | 1903 | 7.9% | 8.2% |
| JJA | 2 | 20023 | 191 | 1.0% | 1.1% |
| JJA | 3 | 13049 | 47 | 0.4% | 0.5% |
| SON | 1 | 23442 | 1916 | 8.2% | 8.5% |
| SON | 2 | 18526 | 201 | 1.1% | 1.2% |
| SON | 3 | 11731 | 118 | 1.0% | 1.2% |

## 5. Winter (DJF) vs Summer (JJA) explicit comparison, raw1min
| margin | DJF cond. loss | DJF Wilson-95 | JJA cond. loss | JJA Wilson-95 | DJF/JJA ratio (point) |
|---|---|---|---|---|---|
| 1 | 14.1% | 14.5% | 18.6% | 19.1% | 0.76x |
| 2 | 5.3% | 5.6% | 2.9% | 3.1% | 1.83x |
| 3 | 7.2% | 7.6% | 1.7% | 2.0% | 4.18x |

Same DAYFLAG (unconditional exposure-day rate), winter vs summer:

| margin | DJF rate | JJA rate | DJF/JJA ratio |
|---|---|---|---|
| 1 | 38.865% | 57.198% | 0.68x |
| 2 | 6.809% | 5.484% | 1.24x |
| 3 | 5.607% | 1.592% | 3.52x |

## 6. Per-station worst offenders (raw1min, margin=1, near_money ladder)
| station | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|
| KPHX | 6578 | 1531 | 23.3% | 24.3% |
| KLAX | 6390 | 1348 | 21.1% | 22.1% |
| KMIA | 6833 | 1388 | 20.3% | 21.3% |
| KDEN | 6452 | 1179 | 18.3% | 19.2% |
| KPHL | 6736 | 1214 | 18.0% | 19.0% |
| KSEA | 6526 | 1169 | 17.9% | 18.9% |
| KLAS | 5516 | 961 | 17.4% | 18.4% |
| KHOU | 6465 | 1083 | 16.8% | 17.7% |
| KDFW | 5668 | 903 | 15.9% | 16.9% |
| KATL | 6156 | 977 | 15.9% | 16.8% |
| KSFO | 6022 | 933 | 15.5% | 16.4% |
| KAUS | 5386 | 832 | 15.4% | 16.4% |
| KSAT | 5119 | 780 | 15.2% | 16.2% |
| KMSY | 4049 | 614 | 15.2% | 16.3% |
| KDCA | 3602 | 541 | 15.0% | 16.2% |
| KBOS | 6376 | 955 | 15.0% | 15.9% |
| KOKC | 6050 | 870 | 14.4% | 15.3% |
| NYC | 5590 | 777 | 13.9% | 14.8% |
| KMSP | 5037 | 691 | 13.7% | 14.7% |
| KMDW | 5993 | 642 | 10.7% | 11.5% |

Same at margin=2:

| station | n fired | n lock-fail | cond. loss | Wilson-95 |
|---|---|---|---|---|
| KPHL | 5060 | 423 | 8.4% | 9.2% |
| KLAX | 4811 | 322 | 6.7% | 7.4% |
| KSEA | 4861 | 323 | 6.6% | 7.4% |
| KDCA | 2632 | 158 | 6.0% | 7.0% |
| NYC | 4040 | 238 | 5.9% | 6.7% |
| KPHX | 4922 | 282 | 5.7% | 6.4% |
| KBOS | 4652 | 239 | 5.1% | 5.8% |
| KATL | 4512 | 203 | 4.5% | 5.1% |
| KMIA | 5072 | 224 | 4.4% | 5.0% |
| KDEN | 4734 | 167 | 3.5% | 4.1% |
| KHOU | 4709 | 134 | 2.8% | 3.4% |
| KMSY | 2925 | 80 | 2.7% | 3.4% |
| KAUS | 3875 | 103 | 2.7% | 3.2% |
| KLAS | 4008 | 104 | 2.6% | 3.1% |
| KOKC | 4361 | 112 | 2.6% | 3.1% |
| KSFO | 4340 | 90 | 2.1% | 2.5% |
| KDFW | 4074 | 46 | 1.1% | 1.5% |
| KSAT | 3639 | 34 | 0.9% | 1.3% |
| KMSP | 3580 | 20 | 0.6% | 0.9% |
| KMDW | 4204 | 23 | 0.5% | 0.8% |

## 7. Candidate deployable rules -- all-season worst-case conditional loss
| rule | margin | n fired | cond. loss | Wilson-95 worst-case |
|---|---|---|---|---|
| raw1min (baseline) | 2 | 85011 | 3.9% | 4.0% |
| glitch-filtered only | 2 | 82223 | 1.6% | 1.7% |
| glitch + sustain3 | 1 | 93785 | 0.4% | 0.4% |
| glitch + sustain3 | 2 | 61238 | 0.1% | 0.1% |
| roll3 smoothing | 1 | 90151 | 0.2% | 0.2% |
| roll3 smoothing | 2 | 57630 | 0.2% | 0.2% |
| METAR-gated | 1 | 100894 | 7.9% | 8.1% |
| METAR-gated | 2 | 80380 | 1.2% | 1.2% |
