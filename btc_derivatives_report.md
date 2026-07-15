# BTC Derivatives-Positioning Short-Horizon Predictability - Backtest Report

Generated 2026-07-15 22:32 UTC. Model produced numbers, verbatim below.

## Sample achieved

- Days kept: **40**  span **2022-01-06..2026-05-06**
- Dates attempted: 40 (3/month, 2022-01..today). Status: `{'ok': 40}`
- Rows (5-min bars): 11,303
- Split: TRAIN earliest **28** days, TEST recent **12** days (by calendar day).
- Horizons: +1/+3/+6 bars = 5/15/30 min. Costs: [1.0, 5.0] bps round-trip. z-threshold |z|>=1.0.
- Features strictly causal (trailing within-day z; funding z trailing within month). Targets strictly future within-day close-to-close log returns.

## Test 1 - Correlation & sign-hit of signal z vs forward return

`r` = Pearson corr(signal_z, fwd_ret); `hit` = P(sign(z)=sign(fwd)). Overlapping targets inflate corr significance, so these are DESCRIPTIVE; the day-clustered trade t-stats in Test 2 are the robust arbiter.

| signal | horizon | r_train | hit_train | r_test | hit_test | n_test |
|---|---|---|---|---|---|---|
| dOI_1 | 5m | -0.0035 | 0.500 | +0.0118 | 0.501 | 3,143 |
| dOI_1 | 15m | +0.0068 | 0.490 | +0.0363 | 0.491 | 3,119 |
| dOI_1 | 30m | -0.0093 | 0.486 | +0.0426 | 0.501 | 3,083 |
| dOI_3 | 5m | +0.0033 | 0.503 | +0.0314 | 0.503 | 3,119 |
| dOI_3 | 15m | -0.0002 | 0.487 | +0.0566 | 0.509 | 3,095 |
| dOI_3 | 30m | -0.0290 | 0.478 | +0.0512 | 0.508 | 3,059 |
| ls_top | 5m | -0.0256 | 0.504 | -0.0330 | 0.500 | 3,155 |
| ls_top | 15m | -0.0335 | 0.498 | -0.0554 | 0.492 | 3,131 |
| ls_top | 30m | -0.0385 | 0.494 | -0.0839 | 0.493 | 3,095 |
| ls_glob | 5m | -0.0099 | 0.491 | -0.0169 | 0.509 | 3,155 |
| ls_glob | 15m | -0.0174 | 0.498 | -0.0335 | 0.502 | 3,131 |
| ls_glob | 30m | -0.0295 | 0.502 | -0.0488 | 0.518 | 3,095 |
| taker | 5m | +0.0119 | 0.491 | -0.0139 | 0.489 | 3,155 |
| taker | 15m | +0.0053 | 0.490 | +0.0004 | 0.501 | 3,131 |
| taker | 30m | +0.0059 | 0.488 | -0.0079 | 0.504 | 3,095 |
| funding | 5m | -0.0073 | 0.500 | -0.0204 | 0.503 | 3,431 |
| funding | 15m | -0.0116 | 0.506 | -0.0342 | 0.504 | 3,407 |
| funding | 30m | -0.0165 | 0.501 | -0.0440 | 0.489 | 3,371 |
| ret_1 | 5m | -0.0019 | 0.488 | +0.0252 | 0.487 | 3,143 |
| ret_1 | 15m | -0.0272 | 0.479 | -0.0098 | 0.486 | 3,119 |
| ret_1 | 30m | -0.0364 | 0.478 | -0.0039 | 0.497 | 3,083 |
| ret_3 | 5m | -0.0285 | 0.478 | -0.0074 | 0.486 | 3,119 |
| ret_3 | 15m | -0.0558 | 0.474 | -0.0081 | 0.483 | 3,095 |
| ret_3 | 30m | -0.0670 | 0.477 | -0.0084 | 0.483 | 3,059 |

## Test 2 - Tradeable rule: dir = sign(signal z), |z| >= 1, hold horizon, net cost

Reported for BOTH directions of the bet: **MOM** = trade with sign(z) (dir=+sign z), **REV** = trade against sign(z) (dir=-sign z). `t` is DAY-CLUSTERED. bps = mean net bps/trade. A cell SURVIVES only if same-sign mean bps in train & test AND |t|>=2 in both.

### Mode MOM (dir = +sign z)

| signal | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| dOI_1 | 5m | 1bp | -0.67 | -0.99 | 1278 | -0.33 | -0.61 | 656 |  |
| dOI_1 | 5m | 5bp | -4.67 | -7.18 | 1278 | -4.33 | -6.67 | 656 | **YES** |
| dOI_1 | 15m | 1bp | +0.81 | +0.64 | 1272 | +0.64 | +0.55 | 651 |  |
| dOI_1 | 15m | 5bp | -3.19 | -2.10 | 1272 | -3.36 | -3.20 | 651 | **YES** |
| dOI_1 | 30m | 1bp | -0.78 | -0.16 | 1267 | +1.35 | +1.15 | 647 |  |
| dOI_1 | 30m | 5bp | -4.78 | -2.27 | 1267 | -2.65 | -3.23 | 647 | **YES** |
| dOI_3 | 5m | 1bp | -0.49 | -0.25 | 1531 | -0.67 | -1.11 | 862 |  |
| dOI_3 | 5m | 5bp | -4.49 | -4.94 | 1531 | -4.67 | -8.78 | 862 | **YES** |
| dOI_3 | 15m | 1bp | -0.30 | +0.03 | 1523 | +0.51 | +0.58 | 857 |  |
| dOI_3 | 15m | 5bp | -4.30 | -2.45 | 1523 | -3.49 | -3.34 | 857 | **YES** |
| dOI_3 | 30m | 1bp | -3.11 | -1.74 | 1518 | +0.95 | +0.74 | 852 |  |
| dOI_3 | 30m | 5bp | -7.11 | -3.90 | 1518 | -3.05 | -2.58 | 852 | **YES** |
| ls_top | 5m | 1bp | -1.53 | -4.26 | 2888 | -1.42 | -5.19 | 1694 | **YES** |
| ls_top | 5m | 5bp | -5.53 | -14.49 | 2888 | -5.42 | -18.90 | 1694 | **YES** |
| ls_top | 15m | 1bp | -2.57 | -2.70 | 2868 | -1.88 | -2.21 | 1676 | **YES** |
| ls_top | 15m | 5bp | -6.57 | -6.57 | 2868 | -5.88 | -6.47 | 1676 | **YES** |
| ls_top | 30m | 1bp | -3.42 | -2.01 | 2842 | -2.91 | -1.73 | 1652 |  |
| ls_top | 30m | 5bp | -7.42 | -4.20 | 2842 | -6.91 | -3.81 | 1652 | **YES** |
| ls_glob | 5m | 1bp | -1.17 | -4.34 | 4613 | -1.18 | -5.11 | 2491 | **YES** |
| ls_glob | 5m | 5bp | -5.17 | -20.72 | 4613 | -5.18 | -22.22 | 2491 | **YES** |
| ls_glob | 15m | 1bp | -1.45 | -1.54 | 4576 | -1.61 | -2.61 | 2467 |  |
| ls_glob | 15m | 5bp | -5.45 | -7.34 | 4576 | -5.61 | -8.96 | 2467 | **YES** |
| ls_glob | 30m | 1bp | -2.25 | -1.21 | 4519 | -2.51 | -2.13 | 2431 |  |
| ls_glob | 30m | 5bp | -6.25 | -4.17 | 4519 | -6.51 | -5.44 | 2431 | **YES** |
| taker | 5m | 1bp | -0.56 | -1.90 | 1402 | -1.18 | -2.06 | 706 |  |
| taker | 5m | 5bp | -4.56 | -16.60 | 1402 | -5.18 | -8.85 | 706 | **YES** |
| taker | 15m | 1bp | -0.36 | -0.29 | 1392 | -1.10 | -1.42 | 700 |  |
| taker | 15m | 5bp | -4.36 | -4.80 | 1392 | -5.10 | -7.19 | 700 | **YES** |
| taker | 30m | 1bp | +0.13 | +0.39 | 1377 | -1.05 | -1.10 | 695 |  |
| taker | 30m | 5bp | -3.87 | -2.71 | 1377 | -5.05 | -4.62 | 695 | **YES** |
| funding | 5m | 1bp | -1.09 | -2.27 | 2001 | -1.25 | -2.46 | 1048 | **YES** |
| funding | 5m | 5bp | -5.09 | -9.92 | 2001 | -5.25 | -9.14 | 1048 | **YES** |
| funding | 15m | 1bp | -1.25 | -0.98 | 1987 | -1.71 | -1.38 | 1042 |  |
| funding | 15m | 5bp | -5.25 | -3.54 | 1987 | -5.71 | -3.66 | 1042 | **YES** |
| funding | 30m | 1bp | -1.40 | -0.62 | 1966 | -2.11 | -1.06 | 1033 |  |
| funding | 30m | 5bp | -5.40 | -1.87 | 1966 | -6.11 | -2.23 | 1033 |  |
| ret_1 | 5m | 1bp | -0.66 | +0.07 | 1867 | -0.41 | -0.74 | 895 |  |
| ret_1 | 5m | 5bp | -4.66 | -3.30 | 1867 | -4.41 | -8.03 | 895 | **YES** |
| ret_1 | 15m | 1bp | -0.96 | -0.26 | 1853 | -1.00 | -1.65 | 891 |  |
| ret_1 | 15m | 5bp | -4.96 | -3.48 | 1853 | -5.00 | -8.14 | 891 | **YES** |
| ret_1 | 30m | 1bp | -1.53 | -0.69 | 1845 | -0.52 | -0.76 | 885 |  |
| ret_1 | 30m | 5bp | -5.53 | -3.93 | 1845 | -4.52 | -6.61 | 885 | **YES** |
| ret_3 | 5m | 1bp | -1.36 | -2.61 | 1958 | -0.94 | -3.36 | 945 | **YES** |
| ret_3 | 5m | 5bp | -5.36 | -9.97 | 1958 | -4.94 | -17.26 | 945 | **YES** |
| ret_3 | 15m | 1bp | -1.96 | -1.44 | 1947 | -0.82 | -0.97 | 939 |  |
| ret_3 | 15m | 5bp | -5.96 | -4.05 | 1947 | -4.82 | -5.96 | 939 | **YES** |
| ret_3 | 30m | 1bp | -2.19 | -0.85 | 1925 | -1.19 | -0.99 | 929 |  |
| ret_3 | 30m | 5bp | -6.19 | -3.35 | 1925 | -5.19 | -4.53 | 929 | **YES** |

### Mode REV (dir = -sign z)

| signal | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| dOI_1 | 5m | 1bp | -1.33 | -2.11 | 1278 | -1.67 | -2.42 | 656 | **YES** |
| dOI_1 | 5m | 5bp | -5.33 | -8.30 | 1278 | -5.67 | -8.47 | 656 | **YES** |
| dOI_1 | 15m | 1bp | -2.81 | -2.01 | 1272 | -2.64 | -2.42 | 651 | **YES** |
| dOI_1 | 15m | 5bp | -6.81 | -4.76 | 1272 | -6.64 | -6.17 | 651 | **YES** |
| dOI_1 | 30m | 1bp | -1.22 | -0.90 | 1267 | -3.35 | -3.34 | 647 |  |
| dOI_1 | 30m | 5bp | -5.22 | -3.01 | 1267 | -7.35 | -7.73 | 647 | **YES** |
| dOI_3 | 5m | 1bp | -1.51 | -2.09 | 1531 | -1.33 | -2.72 | 862 | **YES** |
| dOI_3 | 5m | 5bp | -5.51 | -6.78 | 1531 | -5.33 | -10.39 | 862 | **YES** |
| dOI_3 | 15m | 1bp | -1.70 | -1.28 | 1523 | -2.51 | -2.54 | 857 |  |
| dOI_3 | 15m | 5bp | -5.70 | -3.76 | 1523 | -6.51 | -6.47 | 857 | **YES** |
| dOI_3 | 30m | 1bp | +1.11 | +0.67 | 1518 | -2.95 | -2.40 | 852 |  |
| dOI_3 | 30m | 5bp | -2.89 | -1.49 | 1518 | -6.95 | -5.71 | 852 |  |
| ls_top | 5m | 1bp | -0.47 | -0.86 | 2888 | -0.58 | -1.67 | 1694 |  |
| ls_top | 5m | 5bp | -4.47 | -11.10 | 2888 | -4.58 | -15.38 | 1694 | **YES** |
| ls_top | 15m | 1bp | +0.57 | +0.77 | 2868 | -0.12 | +0.08 | 1676 |  |
| ls_top | 15m | 5bp | -3.43 | -3.10 | 2868 | -4.12 | -4.18 | 1676 | **YES** |
| ls_top | 30m | 1bp | +1.42 | +0.92 | 2842 | +0.91 | +0.70 | 1652 |  |
| ls_top | 30m | 5bp | -2.58 | -1.26 | 2842 | -3.09 | -1.38 | 1652 |  |
| ls_glob | 5m | 1bp | -0.83 | -3.85 | 4613 | -0.82 | -3.44 | 2491 | **YES** |
| ls_glob | 5m | 5bp | -4.83 | -20.24 | 4613 | -4.82 | -20.55 | 2491 | **YES** |
| ls_glob | 15m | 1bp | -0.55 | -1.35 | 4576 | -0.39 | -0.56 | 2467 |  |
| ls_glob | 15m | 5bp | -4.55 | -7.14 | 4576 | -4.39 | -6.91 | 2467 | **YES** |
| ls_glob | 30m | 1bp | +0.25 | -0.27 | 4519 | +0.51 | +0.48 | 2431 |  |
| ls_glob | 30m | 5bp | -3.75 | -3.23 | 4519 | -3.49 | -2.83 | 2431 | **YES** |
| taker | 5m | 1bp | -1.44 | -5.45 | 1402 | -0.82 | -1.33 | 706 |  |
| taker | 5m | 5bp | -5.44 | -20.14 | 1402 | -4.82 | -8.12 | 706 | **YES** |
| taker | 15m | 1bp | -1.64 | -1.97 | 1392 | -0.90 | -1.47 | 700 |  |
| taker | 15m | 5bp | -5.64 | -6.48 | 1392 | -4.90 | -7.24 | 700 | **YES** |
| taker | 30m | 1bp | -2.13 | -1.94 | 1377 | -0.95 | -0.66 | 695 |  |
| taker | 30m | 5bp | -6.13 | -5.04 | 1377 | -4.95 | -4.17 | 695 | **YES** |
| funding | 5m | 1bp | -0.91 | -1.56 | 2001 | -0.75 | -0.88 | 1048 |  |
| funding | 5m | 5bp | -4.91 | -9.22 | 2001 | -4.75 | -7.56 | 1048 | **YES** |
| funding | 15m | 1bp | -0.75 | -0.30 | 1987 | -0.29 | +0.24 | 1042 |  |
| funding | 15m | 5bp | -4.75 | -2.86 | 1987 | -4.29 | -2.03 | 1042 | **YES** |
| funding | 30m | 1bp | -0.60 | -0.01 | 1966 | +0.11 | +0.47 | 1033 |  |
| funding | 30m | 5bp | -4.60 | -1.27 | 1966 | -3.89 | -0.70 | 1033 |  |
| ret_1 | 5m | 1bp | -1.34 | -1.75 | 1867 | -1.59 | -2.91 | 895 |  |
| ret_1 | 5m | 5bp | -5.34 | -5.12 | 1867 | -5.59 | -10.20 | 895 | **YES** |
| ret_1 | 15m | 1bp | -1.04 | -1.36 | 1853 | -1.00 | -1.59 | 891 |  |
| ret_1 | 15m | 5bp | -5.04 | -4.58 | 1853 | -5.00 | -8.08 | 891 | **YES** |
| ret_1 | 30m | 1bp | -0.47 | -0.93 | 1845 | -1.48 | -2.17 | 885 |  |
| ret_1 | 30m | 5bp | -4.47 | -4.16 | 1845 | -5.48 | -8.02 | 885 | **YES** |
| ret_3 | 5m | 1bp | -0.64 | -1.07 | 1958 | -1.06 | -3.59 | 945 |  |
| ret_3 | 5m | 5bp | -4.64 | -8.43 | 1958 | -5.06 | -17.48 | 945 | **YES** |
| ret_3 | 15m | 1bp | -0.04 | +0.13 | 1947 | -1.18 | -1.53 | 939 |  |
| ret_3 | 15m | 5bp | -4.04 | -2.49 | 1947 | -5.18 | -6.52 | 939 | **YES** |
| ret_3 | 30m | 1bp | +0.19 | -0.40 | 1925 | -0.81 | -0.78 | 929 |  |
| ret_3 | 30m | 5bp | -3.81 | -2.90 | 1925 | -4.81 | -4.32 | 929 | **YES** |

## Test 3 - Classic named setups (directional filters)

(a) OI-up & price-up => continuation long; (b) OI-down & price-up => fade (short); (c) extreme crowded L/S ratio => contrarian; (d) extreme funding => fade funded side. Two-sided completions included where natural. Day-clustered t, both costs.

| setup | horizon | cost | train_bps | train_t | train_n | test_bps | test_t | test_n | survive |
|---|---|---|---|---|---|---|---|---|---|
| (a) OI-up cont (long only) | 5m | 1bp | -1.25 | -4.68 | 2169 | -0.89 | -1.55 | 814 |  |
| (a) OI-up cont (long only) | 5m | 5bp | -5.25 | -18.55 | 2169 | -4.89 | -8.38 | 814 | **YES** |
| (a) OI-up cont (long only) | 15m | 1bp | -2.34 | -3.75 | 2153 | -0.98 | -1.39 | 808 |  |
| (a) OI-up cont (long only) | 15m | 5bp | -6.34 | -9.98 | 2153 | -4.98 | -7.48 | 808 | **YES** |
| (a) OI-up cont (long only) | 30m | 1bp | -3.08 | -2.66 | 2132 | -1.27 | -0.66 | 800 |  |
| (a) OI-up cont (long only) | 30m | 5bp | -7.08 | -5.92 | 2132 | -5.27 | -2.86 | 800 | **YES** |
| (a') OI-up cont (2-sided) | 5m | 1bp | -1.01 | -4.80 | 4342 | -0.67 | -1.18 | 1677 |  |
| (a') OI-up cont (2-sided) | 5m | 5bp | -5.01 | -23.23 | 4342 | -4.67 | -7.94 | 1677 | **YES** |
| (a') OI-up cont (2-sided) | 15m | 1bp | -1.59 | -4.31 | 4314 | -1.17 | -2.37 | 1664 | **YES** |
| (a') OI-up cont (2-sided) | 15m | 5bp | -5.59 | -14.77 | 4314 | -5.17 | -10.60 | 1664 | **YES** |
| (a') OI-up cont (2-sided) | 30m | 1bp | -1.58 | -3.49 | 4274 | -1.78 | -3.04 | 1649 | **YES** |
| (a') OI-up cont (2-sided) | 30m | 5bp | -5.58 | -11.94 | 4274 | -5.78 | -10.05 | 1649 | **YES** |
| (b) OI-dn fade (short only) | 5m | 1bp | -1.26 | -2.45 | 1732 | -0.99 | -2.58 | 871 | **YES** |
| (b) OI-dn fade (short only) | 5m | 5bp | -5.26 | -9.93 | 1732 | -4.99 | -12.92 | 871 | **YES** |
| (b) OI-dn fade (short only) | 15m | 1bp | -0.70 | -0.59 | 1718 | -0.34 | -0.21 | 863 |  |
| (b) OI-dn fade (short only) | 15m | 5bp | -4.70 | -3.70 | 1718 | -4.34 | -4.36 | 863 | **YES** |
| (b) OI-dn fade (short only) | 30m | 1bp | -0.52 | -0.24 | 1700 | +0.01 | +0.09 | 856 |  |
| (b) OI-dn fade (short only) | 30m | 5bp | -4.52 | -2.09 | 1700 | -3.99 | -3.19 | 856 | **YES** |
| (b') OI-dn fade (2-sided) | 5m | 1bp | -1.36 | -4.18 | 3439 | -0.78 | -2.63 | 1735 | **YES** |
| (b') OI-dn fade (2-sided) | 5m | 5bp | -5.36 | -16.44 | 3439 | -4.78 | -16.06 | 1735 | **YES** |
| (b') OI-dn fade (2-sided) | 15m | 1bp | -0.93 | -1.78 | 3411 | -0.64 | -1.60 | 1724 |  |
| (b') OI-dn fade (2-sided) | 15m | 5bp | -4.93 | -9.40 | 3411 | -4.64 | -11.28 | 1724 | **YES** |
| (b') OI-dn fade (2-sided) | 30m | 1bp | -0.92 | -1.04 | 3367 | -0.91 | -1.76 | 1703 |  |
| (b') OI-dn fade (2-sided) | 30m | 5bp | -4.92 | -5.67 | 3367 | -4.91 | -8.67 | 1703 | **YES** |
| (c) crowd ls_top contrarian | 5m | 1bp | -0.47 | -0.86 | 2888 | -0.58 | -1.67 | 1694 |  |
| (c) crowd ls_top contrarian | 5m | 5bp | -4.47 | -11.10 | 2888 | -4.58 | -15.38 | 1694 | **YES** |
| (c) crowd ls_top contrarian | 15m | 1bp | +0.57 | +0.77 | 2868 | -0.12 | +0.08 | 1676 |  |
| (c) crowd ls_top contrarian | 15m | 5bp | -3.43 | -3.10 | 2868 | -4.12 | -4.18 | 1676 | **YES** |
| (c) crowd ls_top contrarian | 30m | 1bp | +1.42 | +0.92 | 2842 | +0.91 | +0.70 | 1652 |  |
| (c) crowd ls_top contrarian | 30m | 5bp | -2.58 | -1.26 | 2842 | -3.09 | -1.38 | 1652 |  |
| (c) crowd ls_glob contrarian | 5m | 1bp | -0.83 | -3.85 | 4613 | -0.82 | -3.44 | 2491 | **YES** |
| (c) crowd ls_glob contrarian | 5m | 5bp | -4.83 | -20.24 | 4613 | -4.82 | -20.55 | 2491 | **YES** |
| (c) crowd ls_glob contrarian | 15m | 1bp | -0.55 | -1.35 | 4576 | -0.39 | -0.56 | 2467 |  |
| (c) crowd ls_glob contrarian | 15m | 5bp | -4.55 | -7.14 | 4576 | -4.39 | -6.91 | 2467 | **YES** |
| (c) crowd ls_glob contrarian | 30m | 1bp | +0.25 | -0.27 | 4519 | +0.51 | +0.48 | 2431 |  |
| (c) crowd ls_glob contrarian | 30m | 5bp | -3.75 | -3.23 | 4519 | -3.49 | -2.83 | 2431 | **YES** |
| (d) funding fade | 5m | 1bp | -0.91 | -1.56 | 2001 | -0.75 | -0.88 | 1048 |  |
| (d) funding fade | 5m | 5bp | -4.91 | -9.22 | 2001 | -4.75 | -7.56 | 1048 | **YES** |
| (d) funding fade | 15m | 1bp | -0.75 | -0.30 | 1987 | -0.29 | +0.24 | 1042 |  |
| (d) funding fade | 15m | 5bp | -4.75 | -2.86 | 1987 | -4.29 | -2.03 | 1042 | **YES** |
| (d) funding fade | 30m | 1bp | -0.60 | -0.01 | 1966 | +0.11 | +0.47 | 1033 |  |
| (d) funding fade | 30m | 5bp | -4.60 | -1.27 | 1966 | -3.89 | -0.70 | 1033 |  |

## VERDICT

### ⚠️ CORRECTION (reviewer): the "77 SURVIVED" flag below is a BUG — it is a NULL result
The survive-flag used `|t|>=2` with same-sign, so it flagged consistently **LOSING** cells as
"survivors." EVERY row in the table below has NEGATIVE train_bps AND NEGATIVE test_bps — these are
reliable losers (dominated by the 5bp cost), not edges. A real edge needs POSITIVE mean bps with
t>=+2 in BOTH splits. Scanning the entire grid, **NO such cell exists**: the strongest signal
(crowded long/short contrarian, ls_top/ls_glob, gross corr only −0.03..−0.08) reaches at best
~+1 bp/trade gross with day-clustered t<1 (e.g. ls_top 30m 1bp REV: +1.42/+0.91, t=0.92/0.70) —
insignificant and cost-dead. **TRUE VERDICT: NULL.** No derivatives-positioning signal (open
interest change, top-trader/global long-short ratio, taker imbalance, funding) has positive,
significant, cost-surviving predictive power for 5/15/30-min BTC returns. (Sample is also thinner
than the order-flow test: 40 days / TEST=12 days — but the signal is clearly absent, not merely
underpowered.) The table below is retained verbatim only to show the flag bug.

**[BUGGED FLAG] 77 rule(s) marked "SURVIVED" (|t|>=2 + same sign) — ALL ARE NET LOSERS:**

| rule | horizon | cost | train_bps | train_t | test_bps | test_t |
|---|---|---|---|---|---|---|
| MOM dOI_1 | 5m | 5bp | -4.67 | -7.18 | -4.33 | -6.67 |
| MOM dOI_1 | 15m | 5bp | -3.19 | -2.10 | -3.36 | -3.20 |
| MOM dOI_1 | 30m | 5bp | -4.78 | -2.27 | -2.65 | -3.23 |
| MOM dOI_3 | 5m | 5bp | -4.49 | -4.94 | -4.67 | -8.78 |
| MOM dOI_3 | 15m | 5bp | -4.30 | -2.45 | -3.49 | -3.34 |
| MOM dOI_3 | 30m | 5bp | -7.11 | -3.90 | -3.05 | -2.58 |
| MOM ls_top | 5m | 1bp | -1.53 | -4.26 | -1.42 | -5.19 |
| MOM ls_top | 5m | 5bp | -5.53 | -14.49 | -5.42 | -18.90 |
| MOM ls_top | 15m | 1bp | -2.57 | -2.70 | -1.88 | -2.21 |
| MOM ls_top | 15m | 5bp | -6.57 | -6.57 | -5.88 | -6.47 |
| MOM ls_top | 30m | 5bp | -7.42 | -4.20 | -6.91 | -3.81 |
| MOM ls_glob | 5m | 1bp | -1.17 | -4.34 | -1.18 | -5.11 |
| MOM ls_glob | 5m | 5bp | -5.17 | -20.72 | -5.18 | -22.22 |
| MOM ls_glob | 15m | 5bp | -5.45 | -7.34 | -5.61 | -8.96 |
| MOM ls_glob | 30m | 5bp | -6.25 | -4.17 | -6.51 | -5.44 |
| MOM taker | 5m | 5bp | -4.56 | -16.60 | -5.18 | -8.85 |
| MOM taker | 15m | 5bp | -4.36 | -4.80 | -5.10 | -7.19 |
| MOM taker | 30m | 5bp | -3.87 | -2.71 | -5.05 | -4.62 |
| MOM funding | 5m | 1bp | -1.09 | -2.27 | -1.25 | -2.46 |
| MOM funding | 5m | 5bp | -5.09 | -9.92 | -5.25 | -9.14 |
| MOM funding | 15m | 5bp | -5.25 | -3.54 | -5.71 | -3.66 |
| MOM ret_1 | 5m | 5bp | -4.66 | -3.30 | -4.41 | -8.03 |
| MOM ret_1 | 15m | 5bp | -4.96 | -3.48 | -5.00 | -8.14 |
| MOM ret_1 | 30m | 5bp | -5.53 | -3.93 | -4.52 | -6.61 |
| MOM ret_3 | 5m | 1bp | -1.36 | -2.61 | -0.94 | -3.36 |
| MOM ret_3 | 5m | 5bp | -5.36 | -9.97 | -4.94 | -17.26 |
| MOM ret_3 | 15m | 5bp | -5.96 | -4.05 | -4.82 | -5.96 |
| MOM ret_3 | 30m | 5bp | -6.19 | -3.35 | -5.19 | -4.53 |
| REV dOI_1 | 5m | 1bp | -1.33 | -2.11 | -1.67 | -2.42 |
| REV dOI_1 | 5m | 5bp | -5.33 | -8.30 | -5.67 | -8.47 |
| REV dOI_1 | 15m | 1bp | -2.81 | -2.01 | -2.64 | -2.42 |
| REV dOI_1 | 15m | 5bp | -6.81 | -4.76 | -6.64 | -6.17 |
| REV dOI_1 | 30m | 5bp | -5.22 | -3.01 | -7.35 | -7.73 |
| REV dOI_3 | 5m | 1bp | -1.51 | -2.09 | -1.33 | -2.72 |
| REV dOI_3 | 5m | 5bp | -5.51 | -6.78 | -5.33 | -10.39 |
| REV dOI_3 | 15m | 5bp | -5.70 | -3.76 | -6.51 | -6.47 |
| REV ls_top | 5m | 5bp | -4.47 | -11.10 | -4.58 | -15.38 |
| REV ls_top | 15m | 5bp | -3.43 | -3.10 | -4.12 | -4.18 |
| REV ls_glob | 5m | 1bp | -0.83 | -3.85 | -0.82 | -3.44 |
| REV ls_glob | 5m | 5bp | -4.83 | -20.24 | -4.82 | -20.55 |
| REV ls_glob | 15m | 5bp | -4.55 | -7.14 | -4.39 | -6.91 |
| REV ls_glob | 30m | 5bp | -3.75 | -3.23 | -3.49 | -2.83 |
| REV taker | 5m | 5bp | -5.44 | -20.14 | -4.82 | -8.12 |
| REV taker | 15m | 5bp | -5.64 | -6.48 | -4.90 | -7.24 |
| REV taker | 30m | 5bp | -6.13 | -5.04 | -4.95 | -4.17 |
| REV funding | 5m | 5bp | -4.91 | -9.22 | -4.75 | -7.56 |
| REV funding | 15m | 5bp | -4.75 | -2.86 | -4.29 | -2.03 |
| REV ret_1 | 5m | 5bp | -5.34 | -5.12 | -5.59 | -10.20 |
| REV ret_1 | 15m | 5bp | -5.04 | -4.58 | -5.00 | -8.08 |
| REV ret_1 | 30m | 5bp | -4.47 | -4.16 | -5.48 | -8.02 |
| REV ret_3 | 5m | 5bp | -4.64 | -8.43 | -5.06 | -17.48 |
| REV ret_3 | 15m | 5bp | -4.04 | -2.49 | -5.18 | -6.52 |
| REV ret_3 | 30m | 5bp | -3.81 | -2.90 | -4.81 | -4.32 |
| (a) OI-up cont (long only) | 5m | 5bp | -5.25 | -18.55 | -4.89 | -8.38 |
| (a) OI-up cont (long only) | 15m | 5bp | -6.34 | -9.98 | -4.98 | -7.48 |
| (a) OI-up cont (long only) | 30m | 5bp | -7.08 | -5.92 | -5.27 | -2.86 |
| (a') OI-up cont (2-sided) | 5m | 5bp | -5.01 | -23.23 | -4.67 | -7.94 |
| (a') OI-up cont (2-sided) | 15m | 1bp | -1.59 | -4.31 | -1.17 | -2.37 |
| (a') OI-up cont (2-sided) | 15m | 5bp | -5.59 | -14.77 | -5.17 | -10.60 |
| (a') OI-up cont (2-sided) | 30m | 1bp | -1.58 | -3.49 | -1.78 | -3.04 |
| (a') OI-up cont (2-sided) | 30m | 5bp | -5.58 | -11.94 | -5.78 | -10.05 |
| (b) OI-dn fade (short only) | 5m | 1bp | -1.26 | -2.45 | -0.99 | -2.58 |
| (b) OI-dn fade (short only) | 5m | 5bp | -5.26 | -9.93 | -4.99 | -12.92 |
| (b) OI-dn fade (short only) | 15m | 5bp | -4.70 | -3.70 | -4.34 | -4.36 |
| (b) OI-dn fade (short only) | 30m | 5bp | -4.52 | -2.09 | -3.99 | -3.19 |
| (b') OI-dn fade (2-sided) | 5m | 1bp | -1.36 | -4.18 | -0.78 | -2.63 |
| (b') OI-dn fade (2-sided) | 5m | 5bp | -5.36 | -16.44 | -4.78 | -16.06 |
| (b') OI-dn fade (2-sided) | 15m | 5bp | -4.93 | -9.40 | -4.64 | -11.28 |
| (b') OI-dn fade (2-sided) | 30m | 5bp | -4.92 | -5.67 | -4.91 | -8.67 |
| (c) crowd ls_top contrarian | 5m | 5bp | -4.47 | -11.10 | -4.58 | -15.38 |
| (c) crowd ls_top contrarian | 15m | 5bp | -3.43 | -3.10 | -4.12 | -4.18 |
| (c) crowd ls_glob contrarian | 5m | 1bp | -0.83 | -3.85 | -0.82 | -3.44 |
| (c) crowd ls_glob contrarian | 5m | 5bp | -4.83 | -20.24 | -4.82 | -20.55 |
| (c) crowd ls_glob contrarian | 15m | 5bp | -4.55 | -7.14 | -4.39 | -6.91 |
| (c) crowd ls_glob contrarian | 30m | 5bp | -3.75 | -3.23 | -3.49 | -2.83 |
| (d) funding fade | 5m | 5bp | -4.91 | -9.22 | -4.75 | -7.56 |
| (d) funding fade | 15m | 5bp | -4.75 | -2.86 | -4.29 | -2.03 |

Interpretation: these passed a strict OOS + cost + day-clustered bar. Given the size of the grid, weigh against multiple testing before deployment.

_Grid size: 8 signals x 3 horizons x 2 costs x 2 modes + 7 setups x 3 x 2 = 138 tested cells._
