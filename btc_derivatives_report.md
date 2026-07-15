# BTC Derivatives-Positioning Short-Horizon Predictability - Backtest Report

Generated 2026-07-15 22:43 UTC. Model produced numbers, verbatim below.

## Sample achieved

- Days kept: **163**  span **2022-01-06..2026-07-06**
- Dates attempted: 163 (3/month, 2022-01..today). Status: `{'ok': 163}`
- Rows (5-min bars): 46,427
- Split: TRAIN earliest **114** days, TEST recent **49** days (by calendar day).
- Horizons: +1/+3/+6 bars = 5/15/30 min. Costs: [1.0, 5.0] bps round-trip. z-threshold |z|>=1.0.
- Features strictly causal (trailing within-day z; funding z trailing within month). Targets strictly future within-day close-to-close log returns.

## Test 1 - Correlation & sign-hit of signal z vs forward return

`r` = Pearson corr(signal_z, fwd_ret); `hit` = P(sign(z)=sign(fwd)). Overlapping targets inflate corr significance, so these are DESCRIPTIVE; the day-clustered trade t-stats in Test 2 are the robust arbiter. A profitable predictor should show |r|>0 with a hit rate above 0.50.

| signal | horizon | r_train | hit_train | r_test | hit_test | n_test |
|---|---|---|---|---|---|---|
| dOI_1 | 5m | +nan | 0.503 | +nan | 0.496 | 12,836 |
| dOI_1 | 15m | +nan | 0.498 | +nan | 0.495 | 12,738 |
| dOI_1 | 30m | +nan | 0.503 | +nan | 0.498 | 12,591 |
| dOI_3 | 5m | +nan | 0.501 | +nan | 0.496 | 12,738 |
| dOI_3 | 15m | +nan | 0.499 | +nan | 0.498 | 12,640 |
| dOI_3 | 30m | +nan | 0.495 | +nan | 0.496 | 12,493 |
| ls_top | 5m | -0.0165 | 0.497 | -0.0109 | 0.494 | 12,885 |
| ls_top | 15m | -0.0283 | 0.496 | -0.0182 | 0.495 | 12,787 |
| ls_top | 30m | -0.0406 | 0.497 | -0.0314 | 0.491 | 12,640 |
| ls_glob | 5m | -0.0102 | 0.497 | -0.0164 | 0.503 | 12,885 |
| ls_glob | 15m | -0.0169 | 0.499 | -0.0308 | 0.499 | 12,787 |
| ls_glob | 30m | -0.0231 | 0.497 | -0.0433 | 0.494 | 12,640 |
| taker | 5m | +0.0003 | 0.491 | -0.0070 | 0.491 | 12,885 |
| taker | 15m | +0.0022 | 0.488 | -0.0090 | 0.498 | 12,787 |
| taker | 30m | +0.0034 | 0.489 | -0.0125 | 0.498 | 12,640 |
| funding | 5m | -0.0034 | 0.496 | -0.0084 | 0.497 | 13,726 |
| funding | 15m | -0.0058 | 0.498 | -0.0146 | 0.499 | 13,630 |
| funding | 30m | -0.0074 | 0.497 | -0.0201 | 0.497 | 13,486 |
| ret_1 | 5m | -0.0267 | 0.482 | -0.0043 | 0.487 | 12,836 |
| ret_1 | 15m | -0.0155 | 0.480 | -0.0213 | 0.483 | 12,738 |
| ret_1 | 30m | -0.0131 | 0.480 | -0.0181 | 0.493 | 12,591 |
| ret_3 | 5m | -0.0195 | 0.477 | -0.0237 | 0.478 | 12,738 |
| ret_3 | 15m | -0.0155 | 0.474 | -0.0263 | 0.478 | 12,640 |
| ret_3 | 30m | -0.0163 | 0.478 | -0.0300 | 0.479 | 12,493 |

## Test 2 - Tradeable rule: dir = sign(signal z), |z| >= 1, hold horizon, net cost

Reported for BOTH directions of the bet: **MOM** = trade with sign(z) (dir=+sign z), **REV** = trade against sign(z) (dir=-sign z). `t` is DAY-CLUSTERED. bps = mean net bps/trade. A cell SURVIVES only if it is PROFITABLE: mean bps > 0 AND day-clustered t >= +2 in BOTH train and test. (A consistently negative+significant cell is a reliable LOSER, not an edge; a real directional edge appears as a positive survivor in either MOM or REV. Note at 5bp cost almost every cell is deeply negative because cost swamps any micro-edge.)

### Mode MOM (dir = +sign z)

| signal | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| dOI_1 | 5m | 1bp | -0.60 | -1.79 | 5418 | -1.30 | -3.15 | 2260 |  |
| dOI_1 | 5m | 5bp | -4.60 | -15.63 | 5418 | -5.30 | -13.42 | 2260 |  |
| dOI_1 | 15m | 1bp | +0.03 | +0.18 | 5391 | -1.44 | -1.88 | 2254 |  |
| dOI_1 | 15m | 5bp | -3.97 | -6.86 | 5391 | -5.44 | -6.86 | 2254 |  |
| dOI_1 | 30m | 1bp | -0.31 | -0.08 | 5347 | -2.31 | -2.21 | 2247 |  |
| dOI_1 | 30m | 5bp | -4.31 | -5.25 | 5347 | -6.31 | -5.71 | 2247 |  |
| dOI_3 | 5m | 1bp | -0.67 | -1.78 | 6609 | -1.09 | -3.33 | 2927 |  |
| dOI_3 | 5m | 5bp | -4.67 | -15.00 | 6609 | -5.09 | -15.10 | 2927 |  |
| dOI_3 | 15m | 1bp | -0.34 | -0.33 | 6585 | -0.90 | -1.44 | 2920 |  |
| dOI_3 | 15m | 5bp | -4.34 | -6.50 | 6585 | -4.90 | -6.53 | 2920 |  |
| dOI_3 | 30m | 1bp | -1.57 | -1.55 | 6530 | -1.61 | -1.68 | 2914 |  |
| dOI_3 | 30m | 5bp | -5.57 | -5.90 | 6530 | -5.61 | -5.29 | 2914 |  |
| ls_top | 5m | 1bp | -1.28 | -7.05 | 11630 | -1.22 | -6.49 | 7642 |  |
| ls_top | 5m | 5bp | -5.28 | -29.50 | 11630 | -5.22 | -30.25 | 7642 |  |
| ls_top | 15m | 1bp | -2.01 | -3.88 | 11545 | -1.57 | -3.01 | 7584 |  |
| ls_top | 15m | 5bp | -6.01 | -11.93 | 11545 | -5.57 | -12.20 | 7584 |  |
| ls_top | 30m | 1bp | -2.92 | -3.17 | 11420 | -2.44 | -2.01 | 7490 |  |
| ls_top | 30m | 5bp | -6.92 | -7.70 | 11420 | -6.44 | -6.46 | 7490 |  |
| ls_glob | 5m | 1bp | -1.18 | -10.58 | 19368 | -1.18 | -5.99 | 8952 |  |
| ls_glob | 5m | 5bp | -5.18 | -48.44 | 19368 | -5.18 | -28.24 | 8952 |  |
| ls_glob | 15m | 1bp | -1.57 | -4.49 | 19218 | -1.60 | -2.42 | 8880 |  |
| ls_glob | 15m | 5bp | -5.57 | -17.42 | 19218 | -5.60 | -9.90 | 8880 |  |
| ls_glob | 30m | 1bp | -2.14 | -2.99 | 18996 | -2.29 | -1.65 | 8769 |  |
| ls_glob | 30m | 5bp | -6.14 | -9.73 | 18996 | -6.29 | -5.61 | 8769 |  |
| taker | 5m | 1bp | -0.93 | -4.79 | 6264 | -1.13 | -5.16 | 2864 |  |
| taker | 5m | 5bp | -4.93 | -26.51 | 6264 | -5.13 | -23.80 | 2864 |  |
| taker | 15m | 1bp | -0.69 | -1.58 | 6221 | -1.62 | -3.61 | 2836 |  |
| taker | 15m | 5bp | -4.69 | -11.90 | 6221 | -5.62 | -12.97 | 2836 |  |
| taker | 30m | 1bp | -0.21 | -0.04 | 6155 | -2.05 | -3.52 | 2800 |  |
| taker | 30m | 5bp | -4.21 | -7.18 | 6155 | -6.05 | -10.44 | 2800 |  |
| funding | 5m | 1bp | -1.06 | -2.68 | 8633 | -1.03 | -4.19 | 4758 |  |
| funding | 5m | 5bp | -5.06 | -9.11 | 8633 | -5.03 | -19.67 | 4758 |  |
| funding | 15m | 1bp | -1.14 | -1.66 | 8577 | -1.08 | -1.57 | 4720 |  |
| funding | 15m | 5bp | -5.14 | -6.49 | 8577 | -5.08 | -6.63 | 4720 |  |
| funding | 30m | 1bp | -1.26 | -1.74 | 8493 | -1.09 | -0.88 | 4663 |  |
| funding | 30m | 5bp | -5.26 | -4.44 | 8493 | -5.09 | -3.36 | 4663 |  |
| ret_1 | 5m | 1bp | -1.46 | -3.49 | 7872 | -0.91 | -2.65 | 3315 |  |
| ret_1 | 5m | 5bp | -5.46 | -14.16 | 7872 | -4.91 | -15.97 | 3315 |  |
| ret_1 | 15m | 1bp | -1.26 | -2.62 | 7817 | -1.39 | -1.71 | 3301 |  |
| ret_1 | 15m | 5bp | -5.26 | -11.35 | 7817 | -5.39 | -8.06 | 3301 |  |
| ret_1 | 30m | 1bp | -1.49 | -2.45 | 7749 | -1.78 | -1.90 | 3275 |  |
| ret_1 | 30m | 5bp | -5.49 | -9.12 | 7749 | -5.78 | -6.90 | 3275 |  |
| ret_3 | 5m | 1bp | -1.23 | -5.34 | 8066 | -1.45 | -4.80 | 3431 |  |
| ret_3 | 5m | 5bp | -5.23 | -21.62 | 8066 | -5.45 | -19.31 | 3431 |  |
| ret_3 | 15m | 1bp | -1.44 | -2.64 | 8021 | -1.81 | -2.13 | 3415 |  |
| ret_3 | 15m | 5bp | -5.44 | -9.13 | 8021 | -5.81 | -7.87 | 3415 |  |
| ret_3 | 30m | 1bp | -1.53 | -1.60 | 7948 | -2.33 | -2.35 | 3388 |  |
| ret_3 | 30m | 5bp | -5.53 | -6.22 | 7948 | -6.33 | -6.73 | 3388 |  |

### Mode REV (dir = -sign z)

| signal | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| dOI_1 | 5m | 1bp | -1.40 | -5.14 | 5418 | -0.70 | -1.98 | 2260 |  |
| dOI_1 | 5m | 5bp | -5.40 | -18.98 | 5418 | -4.70 | -12.25 | 2260 |  |
| dOI_1 | 15m | 1bp | -2.03 | -3.69 | 5391 | -0.56 | -0.61 | 2254 |  |
| dOI_1 | 15m | 5bp | -6.03 | -10.73 | 5391 | -4.56 | -5.59 | 2254 |  |
| dOI_1 | 30m | 1bp | -1.69 | -2.51 | 5347 | +0.31 | +0.47 | 2247 |  |
| dOI_1 | 30m | 5bp | -5.69 | -7.68 | 5347 | -3.69 | -3.03 | 2247 |  |
| dOI_3 | 5m | 1bp | -1.33 | -4.83 | 6609 | -0.91 | -2.56 | 2927 |  |
| dOI_3 | 5m | 5bp | -5.33 | -18.05 | 6609 | -4.91 | -14.32 | 2927 |  |
| dOI_3 | 15m | 1bp | -1.66 | -2.75 | 6585 | -1.10 | -1.10 | 2920 |  |
| dOI_3 | 15m | 5bp | -5.66 | -8.93 | 6585 | -5.10 | -6.19 | 2920 |  |
| dOI_3 | 30m | 1bp | -0.43 | -0.62 | 6530 | -0.39 | -0.12 | 2914 |  |
| dOI_3 | 30m | 5bp | -4.43 | -4.97 | 6530 | -4.39 | -3.73 | 2914 |  |
| ls_top | 5m | 1bp | -0.72 | -4.18 | 11630 | -0.78 | -5.39 | 7642 |  |
| ls_top | 5m | 5bp | -4.72 | -26.64 | 11630 | -4.78 | -29.15 | 7642 |  |
| ls_top | 15m | 1bp | +0.01 | -0.14 | 11545 | -0.43 | -1.58 | 7584 |  |
| ls_top | 15m | 5bp | -3.99 | -8.19 | 11545 | -4.43 | -10.77 | 7584 |  |
| ls_top | 30m | 1bp | +0.92 | +0.90 | 11420 | +0.44 | -0.22 | 7490 |  |
| ls_top | 30m | 5bp | -3.08 | -3.64 | 11420 | -3.56 | -4.68 | 7490 |  |
| ls_glob | 5m | 1bp | -0.82 | -8.36 | 19368 | -0.82 | -5.13 | 8952 |  |
| ls_glob | 5m | 5bp | -4.82 | -46.22 | 19368 | -4.82 | -27.37 | 8952 |  |
| ls_glob | 15m | 1bp | -0.43 | -1.98 | 19218 | -0.40 | -1.32 | 8880 |  |
| ls_glob | 15m | 5bp | -4.43 | -14.92 | 19218 | -4.40 | -8.80 | 8880 |  |
| ls_glob | 30m | 1bp | +0.14 | -0.38 | 18996 | +0.29 | -0.33 | 8769 |  |
| ls_glob | 30m | 5bp | -3.86 | -7.12 | 18996 | -3.71 | -4.29 | 8769 |  |
| taker | 5m | 1bp | -1.07 | -6.07 | 6264 | -0.87 | -4.16 | 2864 |  |
| taker | 5m | 5bp | -5.07 | -27.80 | 6264 | -4.87 | -22.80 | 2864 |  |
| taker | 15m | 1bp | -1.31 | -3.58 | 6221 | -0.38 | -1.07 | 2836 |  |
| taker | 15m | 5bp | -5.31 | -13.89 | 6221 | -4.38 | -10.44 | 2836 |  |
| taker | 30m | 1bp | -1.79 | -3.54 | 6155 | +0.05 | +0.06 | 2800 |  |
| taker | 30m | 5bp | -5.79 | -10.69 | 6155 | -3.95 | -6.85 | 2800 |  |
| funding | 5m | 1bp | -0.94 | -0.54 | 8633 | -0.97 | -3.54 | 4758 |  |
| funding | 5m | 5bp | -4.94 | -6.98 | 8633 | -4.97 | -19.02 | 4758 |  |
| funding | 15m | 1bp | -0.86 | -0.75 | 8577 | -0.92 | -0.96 | 4720 |  |
| funding | 15m | 5bp | -4.86 | -5.58 | 8577 | -4.92 | -6.03 | 4720 |  |
| funding | 30m | 1bp | -0.74 | +0.39 | 8493 | -0.91 | -0.36 | 4663 |  |
| funding | 30m | 5bp | -4.74 | -2.31 | 8493 | -4.91 | -2.84 | 4663 |  |
| ret_1 | 5m | 1bp | -0.54 | -1.84 | 7872 | -1.09 | -4.01 | 3315 |  |
| ret_1 | 5m | 5bp | -4.54 | -12.51 | 7872 | -5.09 | -17.33 | 3315 |  |
| ret_1 | 15m | 1bp | -0.74 | -1.74 | 7817 | -0.61 | -1.47 | 3301 |  |
| ret_1 | 15m | 5bp | -4.74 | -10.46 | 7817 | -4.61 | -7.82 | 3301 |  |
| ret_1 | 30m | 1bp | -0.51 | -0.89 | 7749 | -0.22 | -0.60 | 3275 |  |
| ret_1 | 30m | 5bp | -4.51 | -7.57 | 7749 | -4.22 | -5.61 | 3275 |  |
| ret_3 | 5m | 1bp | -0.77 | -2.80 | 8066 | -0.55 | -2.46 | 3431 |  |
| ret_3 | 5m | 5bp | -4.77 | -19.08 | 8066 | -4.55 | -16.97 | 3431 |  |
| ret_3 | 15m | 1bp | -0.56 | -0.61 | 8021 | -0.19 | -0.73 | 3415 |  |
| ret_3 | 15m | 5bp | -4.56 | -7.10 | 8021 | -4.19 | -6.47 | 3415 |  |
| ret_3 | 30m | 1bp | -0.47 | -0.71 | 7948 | +0.33 | +0.16 | 3388 |  |
| ret_3 | 30m | 5bp | -4.47 | -5.33 | 7948 | -3.67 | -4.23 | 3388 |  |

## Test 3 - Classic named setups (directional filters)

(a) OI-up & price-up => continuation long; (b) OI-down & price-up => fade (short); (c) extreme crowded L/S ratio => contrarian; (d) extreme funding => fade funded side. Two-sided completions included where natural. Day-clustered t, both costs.

| setup | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| (a) OI-up cont (long only) | 5m | 1bp | -1.15 | -8.77 | 8759 | -0.89 | -3.42 | 3514 |  |
| (a) OI-up cont (long only) | 5m | 5bp | -5.15 | -38.46 | 8759 | -4.89 | -18.59 | 3514 |  |
| (a) OI-up cont (long only) | 15m | 1bp | -1.56 | -4.69 | 8698 | -0.91 | -1.69 | 3492 |  |
| (a) OI-up cont (long only) | 15m | 5bp | -5.56 | -15.92 | 8698 | -4.91 | -8.86 | 3492 |  |
| (a) OI-up cont (long only) | 30m | 1bp | -1.71 | -2.91 | 8604 | -1.23 | -1.22 | 3454 |  |
| (a) OI-up cont (long only) | 30m | 5bp | -5.71 | -8.87 | 8604 | -5.23 | -4.93 | 3454 |  |
| (a') OI-up cont (2-sided) | 5m | 1bp | -1.21 | -12.04 | 17680 | -0.75 | -3.81 | 7107 |  |
| (a') OI-up cont (2-sided) | 5m | 5bp | -5.21 | -51.80 | 17680 | -4.75 | -24.41 | 7107 |  |
| (a') OI-up cont (2-sided) | 15m | 1bp | -1.46 | -7.76 | 17553 | -0.94 | -3.38 | 7057 |  |
| (a') OI-up cont (2-sided) | 15m | 5bp | -5.46 | -28.61 | 17553 | -4.94 | -18.20 | 7057 |  |
| (a') OI-up cont (2-sided) | 30m | 1bp | -1.51 | -5.99 | 17375 | -1.35 | -3.65 | 6982 |  |
| (a') OI-up cont (2-sided) | 30m | 5bp | -5.51 | -21.45 | 17375 | -5.35 | -14.89 | 6982 |  |
| (b) OI-dn fade (short only) | 5m | 1bp | -0.75 | -3.63 | 7239 | -1.17 | -5.68 | 3469 |  |
| (b) OI-dn fade (short only) | 5m | 5bp | -4.75 | -22.36 | 7239 | -5.17 | -25.75 | 3469 |  |
| (b) OI-dn fade (short only) | 15m | 1bp | -0.69 | -1.48 | 7191 | -1.33 | -2.19 | 3439 |  |
| (b) OI-dn fade (short only) | 15m | 5bp | -4.69 | -10.04 | 7191 | -5.33 | -9.45 | 3439 |  |
| (b) OI-dn fade (short only) | 30m | 1bp | -0.49 | -0.52 | 7118 | -1.69 | -1.82 | 3402 |  |
| (b) OI-dn fade (short only) | 30m | 5bp | -4.49 | -5.70 | 7118 | -5.69 | -6.65 | 3402 |  |
| (b') OI-dn fade (2-sided) | 5m | 1bp | -0.94 | -6.42 | 14382 | -0.77 | -5.85 | 6829 |  |
| (b') OI-dn fade (2-sided) | 5m | 5bp | -4.94 | -32.87 | 14382 | -4.77 | -36.08 | 6829 |  |
| (b') OI-dn fade (2-sided) | 15m | 1bp | -0.94 | -3.76 | 14281 | -0.62 | -2.35 | 6782 |  |
| (b') OI-dn fade (2-sided) | 15m | 5bp | -4.94 | -19.05 | 14281 | -4.62 | -18.11 | 6782 |  |
| (b') OI-dn fade (2-sided) | 30m | 1bp | -1.01 | -2.74 | 14117 | -0.49 | -1.43 | 6710 |  |
| (b') OI-dn fade (2-sided) | 30m | 5bp | -5.01 | -13.19 | 14117 | -4.49 | -13.41 | 6710 |  |
| (c) crowd ls_top contrarian | 5m | 1bp | -0.72 | -4.18 | 11630 | -0.78 | -5.39 | 7642 |  |
| (c) crowd ls_top contrarian | 5m | 5bp | -4.72 | -26.64 | 11630 | -4.78 | -29.15 | 7642 |  |
| (c) crowd ls_top contrarian | 15m | 1bp | +0.01 | -0.14 | 11545 | -0.43 | -1.58 | 7584 |  |
| (c) crowd ls_top contrarian | 15m | 5bp | -3.99 | -8.19 | 11545 | -4.43 | -10.77 | 7584 |  |
| (c) crowd ls_top contrarian | 30m | 1bp | +0.92 | +0.90 | 11420 | +0.44 | -0.22 | 7490 |  |
| (c) crowd ls_top contrarian | 30m | 5bp | -3.08 | -3.64 | 11420 | -3.56 | -4.68 | 7490 |  |
| (c) crowd ls_glob contrarian | 5m | 1bp | -0.82 | -8.36 | 19368 | -0.82 | -5.13 | 8952 |  |
| (c) crowd ls_glob contrarian | 5m | 5bp | -4.82 | -46.22 | 19368 | -4.82 | -27.37 | 8952 |  |
| (c) crowd ls_glob contrarian | 15m | 1bp | -0.43 | -1.98 | 19218 | -0.40 | -1.32 | 8880 |  |
| (c) crowd ls_glob contrarian | 15m | 5bp | -4.43 | -14.92 | 19218 | -4.40 | -8.80 | 8880 |  |
| (c) crowd ls_glob contrarian | 30m | 1bp | +0.14 | -0.38 | 18996 | +0.29 | -0.33 | 8769 |  |
| (c) crowd ls_glob contrarian | 30m | 5bp | -3.86 | -7.12 | 18996 | -3.71 | -4.29 | 8769 |  |
| (d) funding fade | 5m | 1bp | -0.94 | -0.54 | 8633 | -0.97 | -3.54 | 4758 |  |
| (d) funding fade | 5m | 5bp | -4.94 | -6.98 | 8633 | -4.97 | -19.02 | 4758 |  |
| (d) funding fade | 15m | 1bp | -0.86 | -0.75 | 8577 | -0.92 | -0.96 | 4720 |  |
| (d) funding fade | 15m | 5bp | -4.86 | -5.58 | 8577 | -4.92 | -6.03 | 4720 |  |
| (d) funding fade | 30m | 1bp | -0.74 | +0.39 | 8493 | -0.91 | -0.36 | 4663 |  |
| (d) funding fade | 30m | 5bp | -4.74 | -2.31 | 8493 | -4.91 | -2.84 | 4663 |  |

## VERDICT

**NO rule survived.** Across the full grid (8 signals x 3 horizons x 2 costs x {MOM,REV} + 7 named setups x 3 x 2), NOT ONE was profitable net of cost (mean bps>0 with day-clustered t>=+2) in BOTH train and test. Net of even 1bp round-trip cost, BTC derivatives-positioning signals show **no reliable out-of-sample short-horizon predictive edge** in this sample. Note that many cells are significantly NEGATIVE in both train and test (a reliable loser once cost is charged) -- confirming the signals do move with price microstructure, but not enough to overcome cost in any direction. This is a clean null.

_Grid size: 8 signals x 3 horizons x 2 costs x 2 modes + 7 setups x 3 x 2 = 138 tested cells._
