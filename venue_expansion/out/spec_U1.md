# spec_U1 -- Executable-price universe screen (two-stage), results

**Verdict: FAIL** -- 19 Stage-1 survivor(s), 10 advanced, 0 passed Stage 2

## Data actually read
- ALL 16 trade shards: `trades-0000.parquet` .. `trades-0015.parquet` (TrevorJS/kalshi-trades, HF), explicit path list, no glob.
- ALL 4 market shards: `markets-0000.parquet` .. `markets-0003.parquet`, same repo.
- FIT window: created_time < 2025-07-01. VALIDATION window: created_time in [2025-07-01, 2026-01-28] (archive coverage ends 2026-01-28; nothing after that date exists in this archive).
- Outcomes: the markets table's `result` field (Kalshi's official settlement), never re-derived. Stage-2 survivors additionally reconciled against the live `GET /trade-api/v2/markets/{ticker}` endpoint on a >=200-ticker sample per advancing unit-side.
- Executable prices: reconstructed from `taker_side` on every trade print -- taker_side='yes' => lifted the ask at yes_price; taker_side='no' => hit the bid at no_price. No last_price, no mid, anywhere in the EV path.

## Frozen multiple-comparison accounting
- Funnel-wide (4 registered specs, FWER 0.05, Bonferroni): per-spec alpha = 0.0125
- Stage 1: m = 2 x 473 measured-eligible units = 946 hypotheses; alpha_stage1 = 0.0125/946 = 1.321353e-05, two-sided, exact t quantile at each unit-side's own FIT-period df = n_days-1.
  Measured m_units = 473, matches the frozen literal (473) exactly. No divergence.
- Stage 2: alpha_stage2 = 0.0125 / k, k = min(Stage-1 survivors, 10). Stage-1 -> Stage-2 is a closed sequential test on temporally disjoint data (Stage 2 reads only VALIDATION), so it does not re-pay the 946.

## Eligibility (frozen rule, reproduced)
>= 300 settled markets AND >= 40 distinct settlement calendar days AND >= 100,000 total contracts volume, over markets structurally admitted by `event_ticker` containing '-' AND `ticker` prefixed by `event_ticker||'-'`.
- 895/687/473 measured 2026-07-29 pre-run (see cache/prereg/probe4.json); 473-final reproduced exactly at analysis time.

## Market-level admission skip ledger (17,464,713 total markets)
- dashless event_ticker: 3832
- ticker/event_ticker structural mismatch: 2386
- admitted markets: 17458495
- spec text states 3,832 dashless + 2,474 ticker/event_ticker mismatches; measured today: 3832 dashless (MATCHES) + 2386 mismatched (spec said 2,474; small divergence, reported per non-negotiable 7 -- does not change m_units=473, which reproduced exactly).

## Trade-level skip ledger, summed across all 16 shards
- total: 154,505,005
- ticker_not_in_markets: 0
- market_inadmissible: 2,782,515
- unit_not_eligible: 118,647,310
- unsettled_result: 436,669
- taker_side_unrecognized: 0
- price_band_drop: 2,908,041
- time_band_drop: 12,723,583
- qualifying: 17,006,887

## Stage 1 (FIT)
m = 946 unit-sides tested. Bar: |t| >= exact two-sided t quantile at alpha=1.3214e-05, own df, AND |mean EV| >= 0.50c/ct on BOTH weightings.
**Stage-1 survivors: 19**

| rank | unit | side | t | mean EV print c/ct | mean EV contract c/ct | n_days | n_prints |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | INXD|T | no | -16.436 | -13.251 | -36.103 | 271 | 3,035 |
| 2 | INXD|T | yes | 15.264 | 12.666 | 52.422 | 335 | 3,267 |
| 3 | INXD|B | yes | -10.627 | -1.766 | -3.134 | 796 | 207,041 |
| 4 | U3|T | yes | -9.900 | -14.120 | -8.996 | 754 | 3,861 |
| 5 | HIGHMIA|T | yes | -9.554 | -7.920 | -5.824 | 427 | 3,828 |
| 6 | KXHIGHNY|B | yes | -7.129 | -6.356 | -4.706 | 250 | 188,498 |
| 7 | KXHIGHCHI|B | yes | -6.724 | -6.266 | -6.582 | 250 | 122,470 |
| 8 | KXHIGHAUS|B | yes | -6.373 | -6.107 | -6.373 | 250 | 140,849 |
| 9 | KXHIGHPHIL|B | yes | -6.346 | -5.896 | -6.224 | 224 | 60,101 |
| 10 | KXHIGHLAX|T | yes | -6.249 | -12.191 | -10.504 | 177 | 20,986 |
| 11 | HIGHNY|B | yes | -5.949 | -2.829 | -2.253 | 911 | 64,302 |
| 12 | KXHIGHDEN|B | yes | -5.916 | -4.898 | -4.060 | 224 | 103,768 |
| 13 | NASDAQ100D|T | yes | -5.831 | -4.708 | -2.432 | 268 | 9,074 |
| 14 | U3|T | no | 5.823 | 10.736 | 10.346 | 671 | 3,436 |
| 15 | HIGHCHI|T | no | -5.629 | -1.169 | -3.257 | 1107 | 52,613 |
| 16 | KXHIGHMIA|T | yes | -4.897 | -4.752 | -1.407 | 242 | 18,986 |
| 17 | HIGHCHI|B | yes | -4.828 | -1.960 | -2.371 | 903 | 58,050 |
| 18 | KXDOGED|T | yes | -4.810 | -6.068 | -6.549 | 202 | 4,176 |
| 19 | INXW|B | yes | -4.432 | -1.503 | -0.571 | 484 | 61,126 |

**9 survivor(s) beyond k=10 are UNADVANCED (not passes):**
- HIGHNY|B / yes (t=-5.949)
- KXHIGHDEN|B / yes (t=-5.916)
- NASDAQ100D|T / yes (t=-5.831)
- U3|T / no (t=5.823)
- HIGHCHI|T / no (t=-5.629)
- KXHIGHMIA|T / yes (t=-4.897)
- HIGHCHI|B / yes (t=-4.828)
- KXDOGED|T / yes (t=-4.810)
- INXW|B / yes (t=-4.432)

## Stage 2 (VALIDATION, read once)

### INXD|T / no (Stage-1 rank 1)
**Verdict: INSUFFICIENT** -- stage2_min_n_floor_unmet
- min-n detail: {'total_n': 0, 'need_n': 2000, 'n_days': 0, 'need_days': 30, 'n_deciles_ge30': 0, 'need_deciles_ge30': 7}

### INXD|T / yes (Stage-1 rank 2)
**Verdict: INSUFFICIENT** -- stage2_min_n_floor_unmet
- min-n detail: {'total_n': 0, 'need_n': 2000, 'n_days': 0, 'need_days': 30, 'n_deciles_ge30': 0, 'need_deciles_ge30': 7}

### INXD|B / yes (Stage-1 rank 3)
**Verdict: INSUFFICIENT** -- stage2_min_n_floor_unmet
- min-n detail: {'total_n': 0, 'need_n': 2000, 'n_days': 0, 'need_days': 30, 'n_deciles_ge30': 0, 'need_deciles_ge30': 7}

### U3|T / yes (Stage-1 rank 4)
**Verdict: INSUFFICIENT** -- stage2_min_n_floor_unmet
- min-n detail: {'total_n': 0, 'need_n': 2000, 'n_days': 0, 'need_days': 30, 'n_deciles_ge30': 0, 'need_deciles_ge30': 7}

### HIGHMIA|T / yes (Stage-1 rank 5)
**Verdict: INSUFFICIENT** -- stage2_min_n_floor_unmet
- min-n detail: {'total_n': 0, 'need_n': 2000, 'n_days': 0, 'need_days': 30, 'n_deciles_ge30': 0, 'need_deciles_ge30': 7}

### KXHIGHNY|B / yes (Stage-1 rank 6)
**Verdict: FAIL** -- failed_clauses: clause5_wilson_breakeven,clause6_settlement_recon
- mean EV print/contract: -4.262c / -3.122c/ct
- day-clustered t = -4.626 (df=207), bar = 3.2723 (k=10)
- clause1 (EV sign+magnitude): True  clause2 (t bar): True
- clause3 (decile sign stability, 10/10 deciles match, need >=7): True
- clause4 (still same-signed after dropping 5 best days): True (mean_after=-2.2597151199940617)
- clause5 (Wilson lower 0.3883 > breakeven 0.4349): False
- clause6 (settlement reconciliation, n=0/220 sampled, disagreement=None): False

### KXHIGHCHI|B / yes (Stage-1 rank 7)
**Verdict: FAIL** -- failed_clauses: clause2_t_bar,clause5_wilson_breakeven,clause6_settlement_recon
- mean EV print/contract: -3.306c / -4.102c/ct
- day-clustered t = -2.724 (df=208), bar = 3.2721 (k=10)
- clause1 (EV sign+magnitude): True  clause2 (t bar): False
- clause3 (decile sign stability, 9/10 deciles match, need >=7): True
- clause4 (still same-signed after dropping 5 best days): True (mean_after=-1.5210588731757448)
- clause5 (Wilson lower 0.3753 > breakeven 0.4131): False
- clause6 (settlement reconciliation, n=0/220 sampled, disagreement=None): False

### KXHIGHAUS|B / yes (Stage-1 rank 8)
**Verdict: FAIL** -- failed_clauses: clause5_wilson_breakeven,clause6_settlement_recon
- mean EV print/contract: -3.401c / -3.559c/ct
- day-clustered t = -4.912 (df=207), bar = 3.2723 (k=10)
- clause1 (EV sign+magnitude): True  clause2 (t bar): True
- clause3 (decile sign stability, 10/10 deciles match, need >=7): True
- clause4 (still same-signed after dropping 5 best days): True (mean_after=-2.8627722790966614)
- clause5 (Wilson lower 0.3688 > breakeven 0.4072): False
- clause6 (settlement reconciliation, n=0/220 sampled, disagreement=None): False

### KXHIGHPHIL|B / yes (Stage-1 rank 9)
**Verdict: FAIL** -- failed_clauses: clause5_wilson_breakeven,clause6_settlement_recon
- mean EV print/contract: -4.285c / -3.262c/ct
- day-clustered t = -4.664 (df=207), bar = 3.2723 (k=10)
- clause1 (EV sign+magnitude): True  clause2 (t bar): True
- clause3 (decile sign stability, 10/10 deciles match, need >=7): True
- clause4 (still same-signed after dropping 5 best days): True (mean_after=-3.6896381723673235)
- clause5 (Wilson lower 0.3760 > breakeven 0.4239): False
- clause6 (settlement reconciliation, n=0/220 sampled, disagreement=None): False

### KXHIGHLAX|T / yes (Stage-1 rank 10)
**Verdict: FAIL** -- RESIDUAL_CONFLATION_ARTIFACT: fails clause 3 (decile sign stability)
- mean EV print/contract: 0.613c / -1.749c/ct
- day-clustered t = -2.605 (df=207), bar = 3.2723 (k=10)
- clause1 (EV sign+magnitude): False  clause2 (t bar): False
- clause3 (decile sign stability, 3/10 deciles match, need >=7): False
- clause4 (still same-signed after dropping 5 best days): True (mean_after=-2.6826152484544994)
- clause5 (Wilson lower 0.3024 > breakeven 0.3048): False
- clause6 (settlement reconciliation, n=0/220 sampled, disagreement=None): False

## DIVERGENCE: clause 6 (live settlement reconciliation) is infrastructure-blocked
- Found: True
- GET /trade-api/v2/markets/{ticker} returns 404 not_found for every sampled VALIDATION-window ticker (close_time <= 2026-01-28, i.e. >=6 months before this run date 2026-07-29) across all tested candidates (0/220 live results each), while the same endpoint returns a valid record for a market that closed the day before this run (spot-checked: KXHIGHNY-26JUL28-T84). This is Kalshi's live API retention wall (the same wall that motivated using the HF archive at all, per REOPENABLE.md), not a per-unit settlement-quality signal.
- Was clause 6 ever the SOLE failing clause for a candidate: False
- Clause 6 is executed literally and scored FAIL wherever it cannot be evaluated (no waiver improvised, per non-negotiable 1). Checked explicitly: it was never the ONLY failing clause for any Stage-2 candidate this run (see was_sole_blocker_for_any_candidate) -- every candidate that failed clause 6 also independently failed at least one other clause (clause 2, clause 3, or clause 5), so this infrastructure gap did not change the FAIL verdict for any unit-side, though it does mean clause 6 could structurally never produce a PASS for ANY unit whose validation window is this old under the current live-API retention window -- reported as a divergence, not improvised around.

## Auto-refute checklist
- last_price / mid in EV path: NOT USED (taker_side crossing prices only).
- fee at mid: NOT USED (fee computed at the same crossing price as the EV).
- unit key: `split_part(event_ticker,'-',1)` + terminal-segment regexp on `ticker` for rung_class -- event_ticker is a first-class column, not a ticker-only regexp.
- shard subset: NOT USED -- all 16 trade shards read for both Stage 1 and Stage 2.
- m re-derived downward after Stage-1 results: NOT DONE -- m fixed at 946 before any Stage-1 number was computed.
- [0.03,0.97] / 60-minute filters adjusted after seeing EV: NOT DONE -- fixed in the admission SQL before any aggregate was computed.

Elapsed (Phase C, analysis only): 6.4s. Full pipeline (dim build + 16-shard pass + analysis) well under the 4-hour hard budget.