# Phase 3: Live-Feed vs Official-CLI Correlation + Lock-Failure Recalibration

Run time (UTC): 2026-07-18T19:36:34.510041+00:00. Stations: 20. Compact station-day records built: 400.

## Per-station feed coverage (proves/disproves the retention-window claims)

| station | city | wg first obs | metar first obs | LST cutoff date | IEM glitch-removed | IEM raw n |
|---|---|---|---|---|---|---|
| KATL | Atlanta | 2026-07-17 | 2026-07-04 | 2026-07-17 | 1 | 22609 |
| KAUS | Austin (Bergstrom) | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 14809 |
| KBOS | Boston | 2026-07-17 | 2026-07-02 | 2026-07-17 | 0 | 18153 |
| KDCA | Washington DC | 2026-07-17 | 2026-07-06 | 2026-07-17 | 0 | 16712 |
| KDEN | Denver | 2026-07-11 | 2026-07-03 | 2026-07-17 | 0 | 23124 |
| KDFW | Dallas | 2026-07-17 | 2026-07-03 | 2026-07-17 | 0 | 18807 |
| KHOU | Houston (Hobby) | 2026-07-17 | 2026-07-03 | 2026-07-17 | 0 | 22993 |
| KLAS | Las Vegas | 2026-07-17 | 2026-07-02 | 2026-07-17 | 0 | 14134 |
| KLAX | Los Angeles | 2026-07-17 | 2026-07-03 | 2026-07-17 | 0 | 10289 |
| KMDW | Chicago (Midway) | 2026-07-17 | 2026-07-03 | 2026-07-17 | 1 | 23007 |
| KMIA | Miami | 2026-07-17 | 2026-07-04 | 2026-07-17 | 1 | 19681 |
| KMSP | Minneapolis | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 19769 |
| KMSY | New Orleans | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 21455 |
| KOKC | Oklahoma City | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 19555 |
| KPHL | Philadelphia | 2026-07-17 | 2026-07-06 | 2026-07-17 | 0 | 17671 |
| KPHX | Phoenix | 2026-07-17 | 2026-07-03 | 2026-07-17 | 0 | 14942 |
| KSAT | San Antonio | 2026-07-17 | 2026-07-06 | 2026-07-17 | 0 | 18323 |
| KSEA | Seattle | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 21318 |
| KSFO | San Francisco | 2026-07-17 | 2026-07-04 | 2026-07-17 | 0 | 16406 |
| NYC | New York (Central Park) | 2026-07-11 | 2026-07-06 | 2026-07-17 | 0 | 17563 |

## 1+2. Day-max/day-min accuracy vs official CLI + direction of bias (POOLED, all stations)


### KXHIGH (day MAX) -- pooled across stations

| feed | n days | Pearson r | mean bias (F) | MAE (F) | median AE (F) | max AE (F) | %days &#124;err&#124;>=1F | over-read % | under-read % |
|---|---|---|---|---|---|---|---|---|---|
| weathergov_5min | 47 | 0.8143 | -4.043 | 4.094 | 0.98 | 16.0 | 46.81% | 10.64% | 78.72% |
| metar_aviationwx | 285 | 0.9918 | -0.815 | 0.927 | 0.98 | 13.6 | 43.51% | 12.63% | 82.46% |
| iem_raw1min | 338 | 0.9298 | -0.888 | 1.781 | 1.00 | 24.0 | 60.65% | 43.49% | 17.16% |
| iem_glitch_sustain3 | 338 | 0.9352 | -1.530 | 1.541 | 0.00 | 24.0 | 31.66% | 0.59% | 31.07% |

(bias > 0 = feed reads HIGH vs official CLI -- the dangerous direction; bias < 0 = feed reads LOW -- the safe/conservative direction.)


### KXLOW (day MIN) -- pooled across stations

| feed | n days | Pearson r | mean bias (F) | MAE (F) | median AE (F) | max AE (F) | %days &#124;err&#124;>=1F | over-read % | under-read % |
|---|---|---|---|---|---|---|---|---|---|
| weathergov_5min | 47 | 0.9351 | 1.342 | 1.483 | 0.80 | 16.0 | 42.55% | 68.09% | 23.40% |
| metar_aviationwx | 284 | 0.9898 | 0.612 | 0.649 | 0.08 | 10.0 | 25.35% | 69.01% | 27.46% |
| iem_raw1min | 337 | 0.9042 | 0.318 | 0.917 | 0.00 | 67.0 | 26.11% | 17.21% | 8.90% |
| iem_glitch_sustain3 | 337 | 0.9779 | 0.674 | 0.674 | 0.00 | 11.0 | 19.58% | 19.58% | 0.00% |

(bias > 0 = feed reads HIGH vs official CLI -- the dangerous direction; bias < 0 = feed reads LOW -- the safe/conservative direction.)


## Per-station worst offenders (KXHIGH / day-max), weathergov and metar


### weathergov_5min -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KDFW | 2 | 1.000 | -8.40 | 8.40 | 16.0 | 50.00% |
| KBOS | 2 | -1.000 | -8.20 | 8.20 | 15.6 | 50.00% |
| KPHX | 2 | -1.000 | -7.90 | 8.10 | 16.0 | 50.00% |
| KLAS | 2 | -1.000 | -7.50 | 7.50 | 14.8 | 50.00% |
| KMIA | 2 | -1.000 | -6.80 | 6.80 | 12.8 | 50.00% |
| KMDW | 2 | 1.000 | -6.41 | 6.41 | 12.0 | 50.00% |
| KOKC | 2 | 1.000 | -6.40 | 6.40 | 12.6 | 50.00% |
| KLAX | 2 | 1.000 | -6.20 | 6.20 | 12.4 | 50.00% |
| KSFO | 2 | -1.000 | -5.54 | 5.54 | 10.0 | 100.00% |
| KHOU | 2 | 1.000 | -4.70 | 4.90 | 9.6 | 50.00% |
| KMSP | 2 | 1.000 | -4.90 | 4.90 | 9.8 | 50.00% |
| KAUS | 2 | 1.000 | -4.74 | 4.74 | 9.4 | 50.00% |
| KMSY | 2 | 1.000 | -4.70 | 4.70 | 8.6 | 50.00% |
| KSAT | 2 | 1.000 | -4.00 | 4.20 | 8.2 | 50.00% |
| KSEA | 2 | 1.000 | -3.74 | 3.74 | 7.1 | 50.00% |
| KDEN | 7 | 0.987 | -0.88 | 0.88 | 2.0 | 42.86% |
| NYC | 7 | 0.995 | -0.60 | 0.60 | 1.1 | 42.86% |

### metar_aviationwx -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KDEN | 16 | 0.682 | -0.11 | 1.81 | 13.6 | 50.00% |
| KMDW | 15 | 0.939 | -1.48 | 1.49 | 8.1 | 66.67% |
| KHOU | 15 | 0.953 | -1.33 | 1.35 | 6.1 | 40.00% |
| KSFO | 14 | 0.992 | -1.24 | 1.26 | 3.1 | 64.29% |
| KMSP | 15 | 0.945 | -1.01 | 1.03 | 7.0 | 46.67% |
| KSEA | 14 | 0.995 | -0.95 | 0.95 | 2.1 | 42.86% |
| KMIA | 14 | 0.915 | -0.89 | 0.89 | 2.1 | 50.00% |
| KMSY | 14 | 0.975 | -0.87 | 0.88 | 2.1 | 35.71% |
| KATL | 14 | 0.985 | -0.87 | 0.87 | 2.1 | 35.71% |
| NYC | 13 | 0.986 | -0.73 | 0.85 | 4.0 | 38.46% |
| KPHX | 15 | 0.995 | -0.83 | 0.84 | 2.0 | 66.67% |
| KPHL | 12 | 0.995 | -0.74 | 0.76 | 1.9 | 41.67% |
| KLAX | 15 | 0.969 | -0.75 | 0.75 | 3.1 | 33.33% |
| KDFW | 15 | 0.984 | -0.73 | 0.73 | 2.0 | 26.67% |
| KAUS | 14 | 0.997 | -0.71 | 0.73 | 1.1 | 42.86% |
| KBOS | 16 | 0.998 | -0.70 | 0.70 | 2.0 | 43.75% |
| KLAS | 16 | 0.993 | -0.68 | 0.69 | 1.9 | 25.00% |
| KSAT | 12 | 0.996 | -0.60 | 0.60 | 1.1 | 41.67% |
| KOKC | 14 | 0.994 | -0.56 | 0.60 | 1.1 | 35.71% |
| KDCA | 12 | 0.993 | -0.52 | 0.53 | 1.1 | 41.67% |

## Per-station worst offenders (KXLOW / day-min), weathergov and metar


### weathergov_5min -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KOKC | 2 | -1.000 | 3.42 | 3.62 | 7.0 | 50.00% |
| KMSP | 2 | -1.000 | 2.94 | 2.94 | 5.8 | 50.00% |
| KDEN | 7 | -0.342 | 2.92 | 2.93 | 16.0 | 57.14% |
| KMIA | 2 | 1.000 | 2.61 | 2.61 | 4.0 | 100.00% |
| KMSY | 2 | -1.000 | 1.70 | 1.90 | 3.6 | 50.00% |
| KBOS | 2 | 1.000 | 0.90 | 1.70 | 2.6 | 50.00% |
| KAUS | 2 | -1.000 | 1.44 | 1.44 | 2.8 | 50.00% |
| KHOU | 2 | -1.000 | 1.20 | 1.40 | 2.6 | 50.00% |
| KSEA | 2 | n/a | 1.20 | 1.20 | 2.2 | 50.00% |
| KSAT | 2 | -1.000 | 1.04 | 1.04 | 2.1 | 50.00% |
| KDFW | 2 | n/a | 1.00 | 1.00 | 2.0 | 50.00% |
| NYC | 7 | 0.967 | 0.79 | 0.81 | 1.6 | 42.86% |
| KLAS | 2 | 1.000 | 0.33 | 0.73 | 1.1 | 50.00% |
| KLAX | 2 | n/a | 0.44 | 0.44 | 0.8 | 0.00% |
| KMDW | 2 | 1.000 | 0.40 | 0.40 | 0.8 | 0.00% |
| KSFO | 2 | 1.000 | -0.29 | 0.31 | 0.6 | 0.00% |
| KPHX | 2 | 1.000 | -0.06 | 0.14 | 0.2 | 0.00% |

### metar_aviationwx -- ranked by MAE, worst first

| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |
|---|---|---|---|---|---|---|
| KDEN | 16 | 0.851 | 1.29 | 1.30 | 8.9 | 31.25% |
| KLAS | 16 | 0.887 | 1.11 | 1.14 | 7.9 | 37.50% |
| KBOS | 16 | 0.945 | 0.99 | 1.02 | 10.0 | 25.00% |
| KSAT | 12 | 0.861 | 0.82 | 0.85 | 4.9 | 33.33% |
| KPHX | 15 | 0.992 | 0.73 | 0.77 | 2.0 | 40.00% |
| KMSP | 15 | 0.941 | 0.73 | 0.75 | 5.0 | 33.33% |
| KDFW | 15 | 0.951 | 0.67 | 0.68 | 3.0 | 40.00% |
| KATL | 14 | 0.710 | 0.63 | 0.67 | 7.0 | 14.29% |
| KDCA | 12 | 0.968 | 0.39 | 0.64 | 2.1 | 16.67% |
| KMIA | 13 | 0.973 | 0.62 | 0.62 | 3.0 | 23.08% |
| KHOU | 15 | 0.895 | 0.61 | 0.62 | 4.0 | 26.67% |
| KAUS | 14 | 0.957 | 0.56 | 0.60 | 1.9 | 42.86% |
| NYC | 13 | 0.990 | 0.58 | 0.60 | 1.6 | 23.08% |
| KMDW | 15 | 0.990 | 0.48 | 0.50 | 1.1 | 33.33% |
| KSFO | 14 | 0.973 | 0.43 | 0.46 | 1.0 | 28.57% |
| KMSY | 14 | 0.969 | 0.34 | 0.37 | 1.1 | 14.29% |
| KOKC | 14 | 0.985 | 0.34 | 0.36 | 1.9 | 7.14% |
| KSEA | 14 | 0.957 | 0.28 | 0.30 | 1.0 | 7.14% |
| KPHL | 12 | 0.981 | 0.25 | 0.30 | 2.1 | 16.67% |
| KLAX | 15 | 0.975 | 0.13 | 0.19 | 2.0 | 6.67% |

## 3. Live-feed lock-failure test (near-money ladder C-3..C+1 anchored on official CLI)

fired iff feed's LST-day running extreme clears strike K by the margin; lock-failure iff fired AND the official CLI would NOT have confirmed strike K. Track B's published IEM 6-year multi-season baseline for context: glitch+sustain3 @ margin=1 -> 0.4% cond. loss, 0.4% Wilson-95 worst case (n=93785). Below: SAME ladder methodology, but IEM recomputed on the IDENTICAL short overlap window as the two live feeds (not the 6-year sample), for a true apples-to-apples comparison.


### KXHIGH (day MAX)

| feed | margin | n fired | n lock-fail | cond. loss rate | worst-case (Wilson-95) |
|---|---|---|---|---|---|
| weathergov_5min | 1 | 66 | 0 | 0.00% | 5.50% |
| weathergov_5min | 2 | 35 | 0 | 0.00% | 9.89% |
| weathergov_5min | 3 | 10 | 0 | 0.00% | 27.75% |
| weathergov_5min | 4 | 0 | - | - | - |
| weathergov_5min | 5 | 0 | - | - | - |
| weathergov_5min | 6 | 0 | - | - | - |
| metar_aviationwx | 1 | 488 | 2 | 0.41% | 1.48% |
| metar_aviationwx | 2 | 228 | 2 | 0.88% | 3.14% |
| metar_aviationwx | 3 | 54 | 2 | 3.70% | 12.54% |
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
| weathergov_5min | 1 | 15 | 0 | 0.00% | 20.39% |
| weathergov_5min | 2 | 0 | - | - | - |
| weathergov_5min | 3 | 0 | - | - | - |
| weathergov_5min | 4 | 0 | - | - | - |
| weathergov_5min | 5 | 0 | - | - | - |
| weathergov_5min | 6 | 0 | - | - | - |
| metar_aviationwx | 1 | 88 | 0 | 0.00% | 4.18% |
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
