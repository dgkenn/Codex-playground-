# Kalshi KXHIGH Weather Settlement-Nowcast -- REFINEMENT PASS

Refines the CONFIRMED margin=2 baseline (n=35, 91.4% win, +0.168/ct, day-clustered t=4.60, Bonferroni-significant, worst-case EV=+0.030/ct) on the identical 67-day, 20-city sample. Every refinement below is measured, not assumed.

**Sample:** 2026-05-12 to 2026-07-17 (67 days), 20 KXHIGH cities, 1272 city-days analyzed.


## 1. Glitch filter

Absolute cap 130.0F / floor -60.0F, isolated-spike threshold 8.0F/min (both entering AND reverting, so real sustained weather changes are not touched). **Total obs removed: 11** across 5 station(s) with any removal: {'KATL': 2, 'KLAX': 2, 'KMDW': 1, 'KMIA': 4, 'KPHL': 2}.

- KATL: [('2026-05-18T03:02:00+00:00', 79.0, 'isolated_spike'), ('2026-07-03T13:33:00+00:00', 78.0, 'isolated_spike')]
- KLAX: [('2026-05-24T14:06:00+00:00', 120.0, 'isolated_spike'), ('2026-05-24T17:09:00+00:00', -29.0, 'isolated_spike')]
- KMDW: [('2026-07-07T08:41:00+00:00', -1.0, 'isolated_spike')]
- KMIA: [('2026-05-16T23:46:00+00:00', 97.0, 'isolated_spike'), ('2026-06-19T07:43:00+00:00', 74.0, 'isolated_spike'), ('2026-06-26T07:41:00+00:00', 96.0, 'isolated_spike'), ('2026-07-07T07:38:00+00:00', 94.0, 'isolated_spike')]
- KPHL: [('2026-05-11T01:36:00+00:00', 76.0, 'isolated_spike'), ('2026-05-15T01:35:00+00:00', 68.0, 'isolated_spike')]

**LAX glitch, concretely:** KXHIGHLAX-26MAY24-T69 -- 1-min ASOS raw feed reported a max of 120.0F (physically impossible for LAX in May). The independent hourly METAR archive for the SAME station-day reports a max of **68.0F**. Caught by the glitch filter: True. Would ALSO have been caught by the hourly cross-check: True.


## 2. Margin x sustained-above-strike grid (glitch-filtered obs)

sustain_min=1 reproduces the baseline's 'first crossing of the running max' rule on glitch-filtered data (i.e. isolates the glitch filter's effect alone at each margin).

| margin | sustain (min) | n fired | win rate | mean PnL/ct | t (clustered) | cond. loss rate | worst-case loss rate | worst-case EV | fires/wk | passes bar (n>=8,\|t\|>=2,EV_wc>0) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 68 | 0.647 | 0.2213 | 4.31 | 0.353 | 0.472 | 0.1027 | 7.10 | YES |
| 1 | 3 | 42 | 1.000 | 0.3433 | 7.56 | 0.000 | 0.084 | 0.2595 | 4.39 | YES |
| 1 | 5 | 33 | 1.000 | 0.1074 | 4.32 | 0.000 | 0.104 | 0.0032 | 3.45 | YES |
| 1 | 10 | 21 | 1.000 | 0.0187 | 2.36 | 0.000 | 0.155 | -0.1359 | 2.19 | no |
| 2 | 1 | 33 | 0.970 | 0.1831 | 4.67 | 0.030 | 0.153 | 0.0602 | 3.45 | YES |
| 2 | 3 | 19 | 1.000 | 0.0734 | 2.21 | 0.000 | 0.168 | -0.0947 | 1.99 | no |
| 2 | 5 | 14 | 1.000 | 0.0283 | 1.53 | 0.000 | 0.215 | -0.1870 | 1.46 | no |
| 2 | 10 | 9 | 1.000 | 0.0031 | 1.06 | 0.000 | 0.299 | -0.2960 | 0.94 | no |
| 3 | 1 | 17 | 0.941 | 0.0023 | 0.14 | 0.059 | 0.270 | -0.2087 | 1.78 | no |
| 3 | 3 | 4 | 1.000 | 0.0000 | n/a | 0.000 | 0.490 | -0.4899 | 0.42 | no |
| 3 | 5 | 4 | 1.000 | 0.0000 | n/a | 0.000 | 0.490 | -0.4899 | 0.42 | no |
| 3 | 10 | 3 | 1.000 | 0.0000 | n/a | 0.000 | 0.561 | -0.5615 | 0.31 | no |

**Best structural config (ranked by worst-case EV among survivors): margin=1F, sustain=3min.** n=42, win rate 1.000, mean PnL 0.3433, t=7.56, worst-case EV=0.2595.

### Isolated marginal effects (margin=2F held fixed)

| stage | n | win rate | mean PnL | t | n bad (settled wrong way) | worst-case EV |
|---|---|---|---|---|---|---|
| baseline (raw, unfiltered, sustain=1) | 35 | 0.914 | 0.1678 | 4.60 | 3 | 0.0297 |
| + glitch filter (sustain=1) | 33 | 0.970 | 0.1831 | 4.67 | 1 | 0.0602 |
| + glitch filter + sustain=3min | 19 | 1.000 | 0.0734 | 2.21 | 0 | -0.0947 |

Remaining bad tickers after glitch filter: ['KXHIGHMIA-26JUN16-T95']


## 3. Per-station bias table (from margin=1, sustain=1, glitch-filtered fires, n=71-scale)

| station | n fired @ margin1 | n misses | miss rate | miss overshoot(s) F | recommended extra margin F |
|---|---|---|---|---|---|
| KSFO | 10 | 4 | 0.400 | [1.0, 1.0, 1.0, 1.0] | 2 |
| KDEN | 9 | 4 | 0.444 | [1.0, 1.0, 1.0, 1.0] | 2 |
| KMIA | 9 | 1 | 0.111 | [3.0] | 4 |
| KBOS | 7 | 1 | 0.143 | [1.0] | 2 |
| KATL | 6 | 4 | 0.667 | [1.0, 1.0, 1.0, 1.0] | 2 |
| KOKC | 4 | 2 | 0.500 | [1.0, 1.0] | 2 |
| KLAX | 4 | 1 | 0.250 | [1.0] | 2 |
| KSEA | 3 | 2 | 0.667 | [1.0, 1.0] | 2 |
| KDCA | 3 | 0 | 0.000 | [] | 0 |
| NYC | 3 | 0 | 0.000 | [] | 0 |
| KPHL | 3 | 2 | 0.667 | [1.0, 1.0] | 2 |
| KAUS | 2 | 0 | 0.000 | [] | 0 |
| KDFW | 2 | 1 | 0.500 | [1.0] | 2 |
| KSAT | 1 | 1 | 1.000 | [1.0] | 2 |
| KHOU | 1 | 1 | 1.000 | [1.0] | 2 |
| KMSY | 1 | 0 | 0.000 | [] | 0 |

## 4. Per-station-margin variant (base margin + station-specific extra buffer)

| variant | n fired | win rate | mean PnL | t | n bad | worst-case EV | untestable stations (needed margin>3) |
|---|---|---|---|---|---|---|---|
| base=2F, sustain=1min | 5 | 1.000 | 0.2088 | 2.44 | 0 | -0.2256 | [('KATL', 4), ('KBOS', 4), ('KDEN', 4), ('KDFW', 4), ('KHOU', 4), ('KLAX', 4), ('KMIA', 6), ('KOKC', 4), ('KPHL', 4), ('KSAT', 4), ('KSEA', 4), ('KSFO', 4)] |
| base=2F, sustain=3min | 3 | 1.000 | 0.0000 | n/a | 0 | -0.5615 | [('KATL', 4), ('KBOS', 4), ('KDEN', 4), ('KDFW', 4), ('KHOU', 4), ('KLAX', 4), ('KMIA', 6), ('KOKC', 4), ('KPHL', 4), ('KSAT', 4), ('KSEA', 4), ('KSFO', 4)] |
| base=1F, sustain=1min | 19 | 1.000 | 0.2310 | 3.19 | 0 | 0.0629 | [('KMIA', 5)] |
| base=1F, sustain=3min | 12 | 1.000 | 0.3152 | 4.03 | 0 | 0.0727 | [('KMIA', 5)] |

## 5. Margin/gap re-optimization

Best structural config = margin=1F, sustain=3min. Gap-threshold overlay on top of it (min required 1-price edge, same family as baseline's 0/2c/5c):

| gap threshold | n | mean PnL | t (clustered) |
|---|---|---|---|
| 0.0 | 36 | 0.4006 | 9.39 |
| 0.02 | 35 | 0.4118 | 9.68 |
| 0.05 | 34 | 0.4228 | 10.32 |

**Margin=1F aggressive sleeve** (sustain=3min, glitch-filtered): n=42, win rate 1.000, mean PnL 0.3433, t=7.56, worst-case EV 0.2595, fires/wk 4.39 -- higher frequency, thinner per-trade margin for error, offered as an OPTIONAL higher-variance sleeve, not the core recommendation.


## 6. Sizing

Best config = 1_3. Entry price 0.6462, worst-case (Wilson-95) win prob 0.916 (vs point-estimate 1.000). Full-Kelly fraction at the WORST-CASE win prob: **0.7632** of bankroll per fire.

- Quarter-Kelly: 0.1500 of bankroll/fire
- Tenth-Kelly: 0.0763 of bankroll/fire

**Cross-city correlation cap:** cap TOTAL gross stake across ALL cities firing on the same LST calendar date at 15% of bankroll (split pro-rata across that day's fires) -- heat waves fire multiple cities on the same synoptic pattern, so same-day fires are treated as correlated, not independent, for gross-exposure purposes. In-sample, up to 3 cities fired on the same LST date (10 such multi-city days observed) -- confirms this is a real constraint, not a hypothetical one.


At entry price 0.646, worst-case win prob 0.916: full-Kelly stake = 0.763 of bankroll per fire. Quarter-Kelly (recommended) = 0.1500 of bankroll per fire, capped at 15% gross per LST day across all cities combined.


## 7. Multi-source cross-check feasibility

**Feasible: yes.** IEM hourly METAR archive (asos.py, report_type=3,4) -- an independently processed IEM product from the same underlying station transmissions, not a subsample of the 1-min feed; hourly cadence means it lags the 1-min feed by up to ~60min, so it is used as a real-time-safe corroboration check (hourly-max-so-far within tolerance of strike), not a primary signal.

At the best structural config, the hourly cross-check flags **3** fired event(s) as disagreeing with the 1-min feed (hourly-max-so-far more than 3.0F below strike at fire time), of which **0** were actual realized losses -- i.e. the cross-check is directionally useful but, after the glitch filter and sustain requirement already do most of the tail-cleaning work, has limited additional in-sample bite on this 67-day/20-city sample. It is retained as a defense-in-depth signal in the forward harness (kalshi_weather_paper.py), not as a primary filter here.


## 8. Bottom line: best refined config vs baseline

| | baseline (confirmed) | best refined |
|---|---|---|
| margin / sustain | 2F / 1min (raw) | 1F / 3min (glitch-filtered) |
| n fired | 35 | 42 |
| win rate | 0.914 | 1.000 |
| mean net PnL/ct | 0.1678 | 0.3433 |
| day-clustered t | 4.60 | 7.56 |
| n settled wrong way (tail) | 3 (['KXHIGHMIA-26JUN16-T95', 'KXHIGHMIA-26MAY16-T91', 'KXHIGHLAX-26MAY24-T69']) | 0 |
| worst-case (Wilson-95) EV | 0.0297 | 0.2595 |
| fires/week | 3.66 | 4.39 |
