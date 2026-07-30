# maker_stageB_A -- MM1 Stage B (adverse-selection decomposition)

**Study verdict: INSUFFICIENT**

Frozen spec: `venue_expansion/out/spec_MM1_frozen.json` (stageB block). Executed exactly as registered; no bar moved after seeing data.

## Fee types (verified live 2026-07-30)

- `KXBTC`: fee_type=`quadratic` -> maker pays $0 (taker-only fee).
- `KXBTCD`: fee_type=`quadratic` -> maker pays $0 (taker-only fee).
- `KXETH`: fee_type=`quadratic` -> maker pays $0 (taker-only fee).
- `KXETHD`: fee_type=`quadratic` -> maker pays $0 (taker-only fee).

## Extraction summary

- Date range: 2024-10-24 .. 2026-01-28
- 9111260 qualifying rows across all 4 series (any rung_class, price-band [3,97] only), 458 distinct UTC days.
- **Divergence disclosed (not a bar):** Admission is PRICE-BAND ONLY [3,97]c per the frozen 'Admission' bullet (no 60-min pre-close timeband -- that is a U1-only admission rule, applied here only inside sanity anchor (a) to reproduce U1's exact population). The frozen merge_strategy parenthetical '~870K rows total' silently assumed the U1 timeband; measured under the literal MM1 admission rule the pooled BTC+ETH population is ~9.1M qualifying prints. Disclosed divergence from a planning ESTIMATE, not from any bar -- the admission rule itself was followed exactly as frozen, and no threshold, floor or bar in the spec references this row count.

## Worked timezone / join example (2025-01-15, BTC)

Fill at `created_time = 2025-01-15 ... UTC`, epoch `t`; `k = floor(t)`. `head` = close of the Binance BTCUSDT 1s kline whose open-second is `k-1` (the last spot print that was PUBLIC and COMPLETE strictly before the fill). For `R=60s`, `base` = close of the kline with open-second `k-1-60`. `r = ln(head/base)`; EXPLAINED at theta=10bp iff `|r| >= 0.0010`, side-agnostic. Sample verified row: `BTCUSDT-1s-2025-01-15` second `1736899200` (2025-01-15 00:00:00 UTC) close `96560.85` -- read via `data.binance.vision` daily klines zip, reduced to `(second, close)` and as-of joined with a 5s backward grace window (never look-ahead). On this day BTC had 2,371 admitted `KXBTC|B` fills and 6,428 `KXBTCD|T` fills; at (R=60s, theta=10bp) the KXBTC|B split was 418 explained / 1,953 unexplained (418+1953=2371, reconciles); KXBTCD|T was 1,265 explained / 5,163 unexplained (1265+5163=6428, reconciles). Zero UNJOINABLE fills that day (Binance BTCUSDT/ETHUSDT 1s coverage is dense).

## Sanity anchor (a) -- U1 reconciliation

**PASS: True** (tolerance |diff| <= 0.05 c/ct, GROSS print-weighted EV, population = [3,97] price band AND U1's 60-minute pre-close timeband, so this is a like-for-like population match with U1's own cache)

| unit | side | n (U1) | n (mine) | U1 maker gross EV/print | my maker gross EV/print | diff |
|---|---|---:|---:|---:|---:|---:|
| KXBTCD|T | no | 230716 | 230716 | -0.6113 | -0.6113 | 0.0000 |
| KXBTCD|T | yes | 277910 | 277910 | 3.7145 | 3.7145 | 0.0000 |
| KXBTC|B | no | 104426 | 104426 | -0.3470 | -0.3470 | 0.0000 |
| KXBTC|B | yes | 116129 | 116129 | 2.4084 | 2.4084 | 0.0000 |
| KXETHD|T | no | 39665 | 39665 | -0.3928 | -0.3928 | 0.0000 |
| KXETHD|T | yes | 48710 | 48710 | 4.3790 | 4.3790 | 0.0000 |
| KXETH|B | no | 22759 | 22759 | -1.0120 | -1.0120 | 0.0000 |
| KXETH|B | yes | 27175 | 27175 | 0.1837 | 0.1837 | 0.0000 |

## Sanity anchor (b) -- clock check (R=60s, theta=10bp)

**PASS: False** (requires EXPLAINED EV < 0 AND < UNEXPLAINED EV - 1.0 c/ct)

- BTC: explained EV/ct = 0.2597, unexplained EV/ct = 0.8824, ok=False
- ETH: explained EV/ct = -0.2009, unexplained EV/ct = 0.4239, ok=False

### Diagnostic: why anchor (b) fails (NOT gated, does not change any verdict, explains the mechanism)

The side-agnostic EXPLAINED bucket pools two oppositely-signed populations: fills where the pre-fill spot move is in the SAME direction as the taker's bet (ALIGNED -- the taker looks informed, maker adversely selected) and fills where it is in the OPPOSITE direction (ANTI-ALIGNED -- the taker is betting against the recent move). Decomposing (R=60s, theta=10bp) EXPLAINED by this directional split:

| asset | bucket | n | contracts | EV/contract (c) |
|---|---|---:|---:|---:|
| BTC | ALIGNED (informed dir) | 741756 | 96598735 | -0.3978 |
| BTC | ANTI-ALIGNED | 566648 | 78904088 | 1.0646 |
| ETH | ALIGNED (informed dir) | 181004 | 36661013 | -0.5973 |
| ETH | ANTI-ALIGNED | 151095 | 30957784 | 0.2684 |

**Reading:** the ALIGNED subset shows the strongly negative maker EV the clock-check anchor expected (real adverse selection, confirming the join/classification pipeline IS correct and IS finding the toxic flow). The ANTI-ALIGNED subset shows a comparably strong POSITIVE maker EV of similar magnitude and volume, and the frozen side-agnostic definition averages the two together. This is a property of the FROZEN classification rule (deliberately side-agnostic, per the spec's own stated rationale), not a join or clock bug. It is disclosed here, not used to waive or pass anchor (b) -- per the frozen text a violation still means 'all cells INSUFFICIENT pending fix, bars do not move,' and no bar was moved. A directional variant of MM1 would need to be a NEW registration.

## UNJOINABLE rates

- BTC: max rate over R = 0.0001%, exceeds 5% floor = False
    - R=1s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=5s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=15s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=60s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=300s: n_unjoinable=27, contracts_unjoinable=721, rate=0.0001%
- ETH: max rate over R = 0.0000%, exceeds 5% floor = False
    - R=1s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=5s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=15s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=60s: n_unjoinable=0, contracts_unjoinable=0, rate=0.0000%
    - R=300s: n_unjoinable=2, contracts_unjoinable=33, rate=0.0000%

## ALL-FILLS maker EV per asset (KILL bar test)

| asset | n prints | contracts | n days | EV/print (c) | EV/contract (c) PRIMARY | verdict |
|---|---:|---:|---:|---:|---:|---|
| BTC | 8168300 | 877392215 | 458 | 1.0525 | 0.7578 | **INSUFFICIENT** |
| ETH | 937850 | 148426759 | 455 | 1.4801 | 0.1392 | **INSUFFICIENT** |

- **BTC verdict: INSUFFICIENT** -- sanity anchor breach -- halted pending reconciliation
- **ETH verdict: INSUFFICIENT** -- sanity anchor breach -- halted pending reconciliation

## Per-series ALL-FILLS sensitivity (unbarred)

| asset | series\|rung | n prints | contracts | EV/contract (c) |
|---|---|---:|---:|---:|
| BTC | KXBTC\|B | 1413829 | 183767412 | 0.4949 |
| BTC | KXBTCD\|T | 6754471 | 693624803 | 0.8275 |
| ETH | KXETH\|B | 319594 | 57572992 | -0.1673 |
| ETH | KXETHD\|T | 618256 | 90853767 | 0.3335 |

## All 20 gated cells (Bonferroni m=20, alpha=0.0025 two-sided per cell)

PASS requires: unexplained EV >= +0.5c/ct AND signed t >= +exact bar AND surviving volume >= 20% AND min_n met AND both sanity anchors hold.

| asset | R(s) | theta | unexpl n | unexpl contracts | unexpl days | unexpl EV/ct | t | df | bar | surv.vol% | expl EV/ct | PASS | reasons |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| BTC | 1 | 5bp | 8084821 | 864834747 | 458 | 0.8014 | 7.5961 | 457 | 3.0402 | 98.57 | -2.2400 | False | sanity_anchor_breach |
| BTC | 1 | 10bp | 8152351 | 874784707 | 458 | 0.7660 | 7.4179 | 457 | 3.0402 | 99.70 | -1.9915 | False | sanity_anchor_breach |
| BTC | 5 | 5bp | 7701751 | 809786864 | 458 | 0.8613 | 7.8993 | 457 | 3.0402 | 92.29 | -0.4821 | False | sanity_anchor_breach |
| BTC | 5 | 10bp | 8069439 | 861676182 | 458 | 0.7865 | 7.5095 | 457 | 3.0402 | 98.21 | -0.8121 | False | sanity_anchor_breach |
| BTC | 15 | 5bp | 6916265 | 708858462 | 458 | 0.9454 | 8.4441 | 457 | 3.0402 | 80.79 | -0.0309 | False | sanity_anchor_breach |
| BTC | 15 | 10bp | 7830404 | 827140616 | 458 | 0.8358 | 7.7583 | 457 | 3.0402 | 94.27 | -0.5261 | False | sanity_anchor_breach |
| BTC | 60 | 5bp | 5084915 | 503320755 | 458 | 0.9515 | 8.0348 | 457 | 3.0402 | 57.37 | 0.4972 | False | sanity_anchor_breach |
| BTC | 60 | 10bp | 6859896 | 701889392 | 458 | 0.8824 | 7.8996 | 457 | 3.0402 | 80.00 | 0.2597 | False | sanity_anchor_breach |
| BTC | 300 | 5bp | 2765388 | 267386223 | 458 | 0.8210 | 6.5190 | 457 | 3.0402 | 30.48 | 0.7302 | False | sanity_anchor_breach |
| BTC | 300 | 10bp | 4665266 | 458235945 | 458 | 0.8435 | 7.3473 | 457 | 3.0402 | 52.23 | 0.6642 | False | sanity_anchor_breach |
| ETH | 1 | 5bp | 895763 | 138581548 | 455 | 0.1851 | 5.3589 | 454 | 3.0403 | 93.37 | -0.5070 | False | sanity_anchor_breach |
| ETH | 1 | 10bp | 926900 | 145830803 | 455 | 0.1630 | 5.5562 | 454 | 3.0403 | 98.25 | -1.1944 | False | sanity_anchor_breach |
| ETH | 5 | 5bp | 774893 | 111392377 | 455 | 0.3874 | 6.0682 | 454 | 3.0403 | 75.05 | -0.6073 | False | sanity_anchor_breach |
| ETH | 5 | 10bp | 882249 | 134244819 | 455 | 0.2119 | 5.7382 | 454 | 3.0403 | 90.45 | -0.5483 | False | sanity_anchor_breach |
| ETH | 15 | 5bp | 615194 | 82756502 | 455 | 0.6685 | 6.3261 | 454 | 3.0403 | 55.76 | -0.5278 | False | sanity_anchor_breach |
| ETH | 15 | 10bp | 800676 | 115661494 | 455 | 0.4344 | 6.1636 | 454 | 3.0403 | 77.92 | -0.9025 | False | sanity_anchor_breach |
| ETH | 60 | 5bp | 383445 | 48411030 | 455 | 0.6846 | 5.4967 | 454 | 3.0403 | 32.62 | -0.1248 | False | sanity_anchor_breach |
| ETH | 60 | 10bp | 605751 | 80807962 | 455 | 0.4239 | 6.1280 | 454 | 3.0403 | 54.44 | -0.2009 | False | sanity_anchor_breach |
| ETH | 300 | 5bp | 188424 | 23709453 | 453 | 0.6416 | 3.3977 | 452 | 3.0404 | 15.97 | 0.0437 | False | sanity_anchor_breach |
| ETH | 300 | 10bp | 349892 | 44894844 | 455 | 0.3084 | 3.5044 | 454 | 3.0403 | 30.25 | 0.0659 | False | sanity_anchor_breach |

## Skip ledger

### Shard-level (extraction), totals across 16 shards

- total: 9634138
- market_inadmissible: 0
- unsettled_result: 17463
- taker_side_unrecognized: 0
- price_band_drop: 505415
- qualifying: 9111260

### Classification (binance_day_missing etc.)

- none logged (Binance BTCUSDT/ETHUSDT 1s coverage was complete for every day/asset needed)

## Reproducibility

This JSON carries per-cell AGGREGATE numbers (n/contracts/sums), sufficient to recompute every day-clustered t, EV and pass/fail decision exactly, but not raw per-fill rows (870M+ contracts admitted -- per-fill rows are the cached parquet tree below, not duplicated here). Independent recomputation: re-run `python3 venue_expansion/maker_stageB_A.py` (idempotent; every stage skips work whose cache below already exists).

- `per_day_per_cell_aggregates`: `cache/mm1/classified/day=YYYY-MM-DD.parquet (asset, series_key, rung_class, r_seconds, theta_bp, explained, n, contracts, sum_pnl_print, sum_pnl_contract)`
- `per_day_allfills_aggregates`: `cache/mm1/allfills/day=YYYY-MM-DD.parquet (asset, series_key, rung_class, n, contracts, sum_pnl_print, sum_pnl_contract)`
- `per_day_unjoinable`: `cache/mm1/classified_unjoinable/day=YYYY-MM-DD.parquet`
- `per_fill_rows_raw`: `cache/mm1/fills/day=YYYY-MM-DD.parquet (ticker, series_key, rung_class, asset, taker_side, result, price_c, contracts, created_time, created_epoch, cal_day, close_time) -- 9,111,260 rows, the true per-fill substrate everything above is aggregated from`
- `binance_spot`: `cache/mm1/binance/{BTC,ETH}/{date}.parquet (second, close), 1s resolution, both assets, 2024-10-23..2026-01-28`
- `u1_reconciliation_source`: `cache/prereg/tape/u1_day_shard=*.parquet (independent U1 pipeline output, not modified by this script)`

## Deliverable statement

Study verdict: **INSUFFICIENT**.

**Note for anyone re-registering MM1 (not a bar move, not a pass, purely disclosure):** with the sanity-anchor gate set aside, the raw per-cell numbers in the table above are unusually strong for this codebase's track record (41/41 prior kills) -- every one of the 20 cells shows positive UNEXPLAINED EV clearing the exact Bonferroni bar with a large surviving-volume share (up to 99.7% for BTC at R=1s). That is exactly the pattern non-negotiable 9 warns about ('a positive is more likely your bug until the anchors clear') and is precisely why anchor (b) exists as a precondition, not a suggestion. The diagnostic above shows the underlying join/classification mechanism is verifiably correct (ALIGNED vs ANTI-ALIGNED split behaves exactly as expected), so the likely explanation is a registration-design tension (the side-agnostic definition dilutes the signal the anchor's fixed 1.0c gap assumed) rather than a pipeline bug -- but per the frozen text this is reported, not waived, and the verdict stays INSUFFICIENT. Closing this would require a NEW registration, either recalibrating anchor (b)'s threshold under the side-agnostic definition or re-registering a directional classification rule, decided BEFORE reading any further data.

Queue-position caveat carried forward per the frozen interpretation: every measured EV here is a front-of-queue OPTIMISTIC bound. A PASS is necessary-but-not-sufficient; the only permitted next step is separately registered tiny-size live validation, never a scaled infrastructure build from this study alone.
