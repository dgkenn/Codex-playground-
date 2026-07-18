# Phase 3: Live-Feed vs Official-CLI Correlation + Lock-Failure Recalibration

Run time (UTC): 2026-07-18T19:41:30.870633+00:00. Stations: 20. Compact station-day records built: 400.

## Per-station feed coverage (proves/disproves the retention-window claims)

| station | city | wg first obs | metar first obs | LST cutoff date | IEM glitch-removed | IEM raw n |
|---|---|---|---|---|---|---|
| KATL | Atlanta | 2026-07-11 | 2026-06-30 | 2026-07-17 | 1 | 22609 |
| KAUS | Austin (Bergstrom) | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 14809 |
| KBOS | Boston | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 18153 |
| KDCA | Washington DC | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 16712 |
| KDEN | Denver | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 23124 |
| KDFW | Dallas | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 18807 |
| KHOU | Houston (Hobby) | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 22993 |
| KLAS | Las Vegas | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 14134 |
| KLAX | Los Angeles | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 10289 |
| KMDW | Chicago (Midway) | 2026-07-11 | 2026-06-30 | 2026-07-17 | 1 | 23007 |
| KMIA | Miami | 2026-07-11 | 2026-06-30 | 2026-07-17 | 1 | 19681 |
| KMSP | Minneapolis | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 19769 |
| KMSY | New Orleans | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 21455 |
| KOKC | Oklahoma City | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 19555 |
| KPHL | Philadelphia | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 17671 |
| KPHX | Phoenix | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 14942 |
| KSAT | San Antonio | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 18323 |
| KSEA | Seattle | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 21318 |
| KSFO | San Francisco | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 16406 |
| NYC | New York (Central Park) | 2026-07-11 | 2026-06-30 | 2026-07-17 | 0 | 17563 |

## 1+2. Day-max/day-min accuracy vs official CLI + direction of bias (POOLED, all stations)


### KXHIGH (day MAX) -- pooled across stations

| feed | n days | Pearson r | mean bias (F) | MAE (F) | median AE (F) | max AE (F) | %days &#124;err&#124;>=1F | over-read % | under-read % |
|---|---|---|---|---|---|---|---|---|---|
| weathergov_5min | 140 | 0.9879 | -0.479 | 0.674 | 0.40 | 10.0 | 16.43% | 21.43% | 67.86% |
| metar_aviationwx | 360 | 0.9947 | -0.770 | 0.861 | 0.98 | 13.6 | 45.28% | 13.06% | 82.22% |
| iem_raw1min | 338 | 0.9298 | -0.888 | 1.781 | 1.00 | 24.0 | 60.65% | 43.49% | 17.16% |
| iem_glitch_sustain3 | 338 | 0.9352 | -1.530 | 1.541 | 0.00 | 24.0 | 31.66% | 0.59% | 31.07% |

(bias > 0 = feed reads HIGH vs official CLI -- the dangerous direction; bias < 0 = feed reads LOW -- the safe/conservative direction.)


### KXLOW (day MIN) -- pooled across stations

| feed | n days | Pearson r | mean bias (F) | MAE (F) | median AE (F) | max AE (F) | %days &#124;err&#124;>=1F | over-read % | under-read % |
|---|---|---|---|---|---|---|---|---|---|
| weathergov_5min | 140 | 0.9559 | 0.681 | 0.994 | 0.40 | 16.0 | 17.86% | 60.00% | 33.57% |
| metar_aviationwx | 359 | 0.9863 | 0.703 | 0.739 | 0.08 | 11.0 | 25.63% | 69.36% | 25.91% |
| iem_raw1min | 337 | 0.9042 | 0.318 | 0.917 | 0.00 | 67.0 | 26.11% | 17.21% | 8.90% |
| iem_glitch_sustain3 | 337 | 0.9779 | 0.674 | 0.674 | 0.00 | 11.0 | 19.58% | 19.58% | 0.00% |

(bias > 0 = feed reads HIGH vs official CLI -- the dangerous direction; bias < 0 = feed reads LOW -- the safe/conservative direction.)


## Per-station worst offenders (KXHIGH / day-max), weathergov and metar


### weathergov_5min -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KMSY | 7 | 0.718 | -1.59 | 1.71 | 9.0 | 14.29% |
| KPHL | 7 | 0.816 | -1.39 | 1.56 | 10.0 | 14.29% |
| KAUS | 7 | 0.952 | -0.62 | 1.19 | 5.1 | 14.29% |
| KSAT | 7 | 0.946 | -0.72 | 1.06 | 5.4 | 14.29% |
| KMDW | 7 | 0.986 | -0.78 | 0.90 | 2.4 | 42.86% |
| KDEN | 7 | 0.987 | -0.88 | 0.88 | 2.0 | 42.86% |
| KPHX | 7 | 0.993 | -0.36 | 0.65 | 1.1 | 42.86% |
| NYC | 7 | 0.995 | -0.60 | 0.60 | 1.1 | 42.86% |
| KSFO | 7 | 0.995 | -0.37 | 0.59 | 1.1 | 14.29% |
| KLAS | 7 | 0.997 | -0.55 | 0.55 | 1.0 | 14.29% |
| KHOU | 7 | 0.991 | -0.12 | 0.52 | 0.8 | 0.00% |
| KMIA | 7 | 0.973 | -0.45 | 0.51 | 1.4 | 14.29% |
| KATL | 7 | 0.994 | -0.37 | 0.49 | 1.1 | 14.29% |
| KSEA | 7 | 0.999 | -0.43 | 0.43 | 1.0 | 14.29% |
| KLAX | 7 | 0.987 | -0.26 | 0.37 | 1.8 | 14.29% |
| KMSP | 7 | 0.985 | -0.05 | 0.33 | 0.8 | 0.00% |
| KOKC | 7 | 0.990 | -0.10 | 0.33 | 1.0 | 14.29% |
| KDCA | 7 | 0.997 | 0.27 | 0.31 | 0.8 | 0.00% |
| KDFW | 7 | 0.995 | -0.21 | 0.27 | 0.8 | 0.00% |
| KBOS | 7 | 0.997 | -0.01 | 0.23 | 0.8 | 0.00% |

### metar_aviationwx -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KDEN | 18 | 0.694 | -0.06 | 1.57 | 13.6 | 50.00% |
| KSFO | 18 | 0.991 | -1.19 | 1.20 | 3.1 | 66.67% |
| KHOU | 18 | 0.986 | -1.05 | 1.06 | 3.1 | 50.00% |
| KSEA | 18 | 0.993 | -1.02 | 1.02 | 3.1 | 50.00% |
| KBOS | 18 | 0.991 | -1.01 | 1.01 | 5.0 | 50.00% |
| KMDW | 18 | 0.992 | -0.96 | 0.97 | 3.0 | 61.11% |
| KATL | 18 | 0.982 | -0.95 | 0.96 | 2.1 | 44.44% |
| KMIA | 18 | 0.884 | -0.92 | 0.93 | 2.1 | 55.56% |
| KMSY | 18 | 0.974 | -0.90 | 0.90 | 2.1 | 33.33% |
| KPHX | 18 | 0.995 | -0.86 | 0.87 | 2.0 | 66.67% |
| KLAX | 18 | 0.977 | -0.79 | 0.80 | 3.1 | 44.44% |
| KAUS | 18 | 0.997 | -0.71 | 0.74 | 1.1 | 50.00% |
| KLAS | 18 | 0.995 | -0.72 | 0.73 | 1.9 | 33.33% |
| KOKC | 18 | 0.993 | -0.67 | 0.69 | 1.1 | 38.89% |
| KPHL | 18 | 0.997 | -0.66 | 0.68 | 1.9 | 33.33% |
| KDFW | 18 | 0.981 | -0.66 | 0.66 | 2.0 | 27.78% |
| KDCA | 18 | 0.995 | -0.62 | 0.63 | 1.9 | 44.44% |
| NYC | 18 | 0.997 | -0.52 | 0.62 | 2.0 | 33.33% |
| KSAT | 18 | 0.995 | -0.58 | 0.58 | 1.1 | 38.89% |
| KMSP | 18 | 0.994 | -0.55 | 0.58 | 1.1 | 33.33% |

## Per-station worst offenders (KXLOW / day-min), weathergov and metar


### weathergov_5min -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KDEN | 7 | -0.342 | 2.92 | 2.93 | 16.0 | 57.14% |
| KMIA | 7 | 0.317 | 2.00 | 2.06 | 11.2 | 28.57% |
| KLAS | 7 | 0.444 | 1.56 | 1.90 | 11.0 | 28.57% |
| KMSP | 7 | -0.093 | 1.25 | 1.59 | 9.6 | 14.29% |
| KOKC | 7 | 0.833 | 1.47 | 1.52 | 8.6 | 14.29% |
| KPHX | 7 | 0.962 | 1.04 | 1.27 | 6.8 | 14.29% |
| KDCA | 7 | 0.904 | 0.99 | 1.10 | 5.0 | 28.57% |
| KSFO | 7 | 0.741 | 0.54 | 0.94 | 4.0 | 28.57% |
| KHOU | 7 | 0.825 | 0.77 | 0.83 | 4.6 | 14.29% |
| NYC | 7 | 0.967 | 0.79 | 0.81 | 1.6 | 42.86% |
| KMDW | 7 | 0.945 | 0.42 | 0.71 | 3.0 | 14.29% |
| KATL | 7 | 0.817 | 0.25 | 0.70 | 3.1 | 14.29% |
| KDFW | 7 | 0.966 | 0.41 | 0.64 | 3.4 | 14.29% |
| KAUS | 7 | 0.954 | -0.01 | 0.56 | 1.2 | 14.29% |
| KPHL | 7 | 0.993 | -0.15 | 0.48 | 1.1 | 14.29% |
| KSEA | 7 | 0.917 | 0.47 | 0.47 | 2.0 | 14.29% |
| KLAX | 7 | 0.949 | -0.29 | 0.39 | 0.8 | 0.00% |
| KBOS | 7 | 0.991 | -0.26 | 0.37 | 0.8 | 0.00% |
| KSAT | 7 | 0.994 | -0.31 | 0.31 | 0.8 | 0.00% |
| KMSY | 7 | 0.981 | -0.22 | 0.30 | 0.8 | 0.00% |

### metar_aviationwx -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KPHX | 18 | 0.916 | 1.33 | 1.36 | 11.0 | 44.44% |
| KLAS | 18 | 0.886 | 1.16 | 1.19 | 10.0 | 38.89% |
| KMSP | 18 | 0.870 | 0.95 | 0.97 | 7.1 | 27.78% |
| KBOS | 18 | 0.927 | 0.93 | 0.96 | 8.9 | 22.22% |
| KDEN | 18 | 0.983 | 0.88 | 0.89 | 3.0 | 33.33% |
| KDCA | 18 | 0.879 | 0.71 | 0.87 | 8.0 | 16.67% |
| KMDW | 18 | 0.961 | 0.84 | 0.86 | 6.0 | 33.33% |
| KDFW | 18 | 0.843 | 0.83 | 0.85 | 6.9 | 33.33% |
| NYC | 18 | 0.968 | 0.73 | 0.79 | 5.1 | 22.22% |
| KAUS | 18 | 0.909 | 0.71 | 0.74 | 4.0 | 38.89% |
| KMIA | 17 | 0.966 | 0.71 | 0.71 | 3.0 | 23.53% |
| KATL | 18 | 0.900 | 0.59 | 0.64 | 6.9 | 16.67% |
| KMSY | 18 | 0.906 | 0.59 | 0.63 | 4.0 | 22.22% |
| KPHL | 18 | 0.954 | 0.55 | 0.60 | 5.1 | 16.67% |
| KHOU | 18 | 0.873 | 0.56 | 0.57 | 4.9 | 22.22% |
| KOKC | 18 | 0.984 | 0.55 | 0.57 | 2.1 | 22.22% |
| KSFO | 18 | 0.950 | 0.51 | 0.53 | 2.0 | 33.33% |
| KSAT | 18 | 0.926 | 0.51 | 0.53 | 2.0 | 33.33% |
| KSEA | 18 | 0.913 | 0.44 | 0.46 | 3.0 | 11.11% |
| KLAX | 18 | 0.999 | -0.02 | 0.07 | 0.4 | 0.00% |

## 3. Live-feed lock-failure test (near-money ladder C-3..C+1 anchored on official CLI)

fired iff feed's LST-day running extreme clears strike K by the margin; lock-failure iff fired AND the official CLI would NOT have confirmed strike K. Track B's published IEM 6-year multi-season baseline for context: glitch+sustain3 @ margin=1 -> 0.4% cond. loss, 0.4% Wilson-95 worst case (n=93785). Below: SAME ladder methodology, but IEM recomputed on the IDENTICAL short overlap window as the two live feeds (not the 6-year sample), for a true apples-to-apples comparison.


### KXHIGH (day MAX)

| feed | margin | n fired | n lock-fail | cond. loss rate | worst-case (Wilson-95) |
|---|---|---|---|---|---|
| weathergov_5min | 1 | 297 | 0 | 0.00% | 1.28% |
| weathergov_5min | 2 | 163 | 0 | 0.00% | 2.30% |
| weathergov_5min | 3 | 45 | 0 | 0.00% | 7.87% |
| weathergov_5min | 4 | 0 | - | - | - |
| weathergov_5min | 5 | 0 | - | - | - |
| weathergov_5min | 6 | 0 | - | - | - |
| metar_aviationwx | 1 | 620 | 2 | 0.32% | 1.17% |
| metar_aviationwx | 2 | 286 | 2 | 0.70% | 2.51% |
| metar_aviationwx | 3 | 68 | 2 | 2.94% | 10.10% |
| metar_aviationwx | 4 | 5 | 2 | 40.00% | 76.93% |
| metar_aviationwx | 5 | 5 | 2 | 40.00% | 76.93% |
| metar_aviationwx | 6 | 5 | 2 | 40.00% | 76.93% |
| iem_raw1min | 1 | 1008 | 151 | 14.98% | 17.32% |
| iem_raw1min | 2 | 716 | 4 | 0.56% | 1.43% |
| iem_raw1min | 3 | 431 | 0 | 0.00% | 0.88% |
| iem_raw1min | 4 | 151 | 0 | 0.00% | 2.48% |
| iem_raw1min | 5 | 4 | 0 | 0.00% | 48.99% |
| iem_raw1min | 6 | 0 | - | - | - |
| iem_glitch_sustain3 | 1 | 803 | 2 | 0.25% | 0.90% |
| iem_glitch_sustain3 | 2 | 514 | 0 | 0.00% | 0.74% |
| iem_glitch_sustain3 | 3 | 235 | 0 | 0.00% | 1.61% |
| iem_glitch_sustain3 | 4 | 2 | 0 | 0.00% | 65.76% |
| iem_glitch_sustain3 | 5 | 0 | - | - | - |
| iem_glitch_sustain3 | 6 | 0 | - | - | - |

### KXLOW (day MIN)

| feed | margin | n fired | n lock-fail | cond. loss rate | worst-case (Wilson-95) |
|---|---|---|---|---|---|
| weathergov_5min | 1 | 56 | 0 | 0.00% | 6.42% |
| weathergov_5min | 2 | 0 | - | - | - |
| weathergov_5min | 3 | 0 | - | - | - |
| weathergov_5min | 4 | 0 | - | - | - |
| weathergov_5min | 5 | 0 | - | - | - |
| weathergov_5min | 6 | 0 | - | - | - |
| metar_aviationwx | 1 | 110 | 0 | 0.00% | 3.37% |
| metar_aviationwx | 2 | 0 | - | - | - |
| metar_aviationwx | 3 | 0 | - | - | - |
| metar_aviationwx | 4 | 0 | - | - | - |
| metar_aviationwx | 5 | 0 | - | - | - |
| metar_aviationwx | 6 | 0 | - | - | - |
| iem_raw1min | 1 | 317 | 38 | 11.99% | 16.03% |
| iem_raw1min | 2 | 39 | 9 | 23.08% | 38.34% |
| iem_raw1min | 3 | 10 | 7 | 70.00% | 89.22% |
| iem_raw1min | 4 | 8 | 5 | 62.50% | 86.32% |
| iem_raw1min | 5 | 6 | 4 | 66.67% | 90.32% |
| iem_raw1min | 6 | 5 | 4 | 80.00% | 96.38% |
| iem_glitch_sustain3 | 1 | 271 | 0 | 0.00% | 1.40% |
| iem_glitch_sustain3 | 2 | 0 | - | - | - |
| iem_glitch_sustain3 | 3 | 0 | - | - | - |
| iem_glitch_sustain3 | 4 | 0 | - | - | - |
| iem_glitch_sustain3 | 5 | 0 | - | - | - |
| iem_glitch_sustain3 | 6 | 0 | - | - | - |

## 4. Margin needed per feed to hit the ~0.4% Wilson-95 safety bar (min n_fired=20)

| feed | margin needed (KXHIGH) | margin needed (KXLOW) |
|---|---|---|
| weathergov_5min | NOT REACHED in 1-6F tested | NOT REACHED in 1-6F tested |
| metar_aviationwx | NOT REACHED in 1-6F tested | NOT REACHED in 1-6F tested |
| iem_raw1min | NOT REACHED in 1-6F tested | NOT REACHED in 1-6F tested |
| iem_glitch_sustain3 | NOT REACHED in 1-6F tested | NOT REACHED in 1-6F tested |
