# Stage B (MM1) — Build B independent replication

**Verdict: INSUFFICIENT** (sanity anchor (b), the classification-clock check, fails for both
assets at the frozen (R=60s, theta=10bp) test point — see §5). This is a mechanical, frozen
consequence, applied without improvisation, even though the raw numbers (§4, pre-override) look
like a strong BTC PASS. Full reasoning below.

Scripts: `venue_expansion/cache/mm1B/extract_shard_B.py`, `merge_to_days_B.py`,
`fetch_binance_B.py`, `classify_days_B.py`, `stats_B.py`, `reconcile_anchor_a_B.py`,
`aggregate_stats_B.py`. Machine output: `venue_expansion/out/maker_stageB_B.json`.

This build was written from the frozen spec text alone (`out/spec_MM1_frozen.json`), without
reading any `maker_stageB_A.*` file, per instruction. Two independent, non-trivial bugs were
found and fixed along the way (§2, §3) — both are exactly the kind of thing a second independent
build exists to catch, and both are disclosed with before/after numbers rather than silently
folded in.

---

## 0. Pipeline summary (resumable, cached under `venue_expansion/cache/mm1B/`)

1. **Extraction** (`extract_shard_B.py`): one DuckDB query per HF trade shard (16 shards,
   `trades-0000..0015.parquet`, explicit URL list, no globs), joined to
   `cache/prereg/ticker_dim.parquet` (U1's market-metadata dimension — pure factual data:
   ticker→series_key/rung_class/result/close_time, not an analysis result, shared as a
   read-only reference by both builds). Admission: `series_key IN (KXBTC,KXBTCD,KXETH,KXETHD)`,
   settled (`result IN ('yes','no')`), `created_time` in `[2024-10-24, 2026-01-28]`, maker-short
   price in `[3,97]`. Output: `cache/mm1B/fills_by_shard/shard=NNNN.parquet` + a skip-ledger JSON
   per shard, idempotent (`os.replace` atomic write).
2. **Merge** (`merge_to_days_B.py`): combine 16 shard files, add `asset` (BTC/ETH) and `epoch_s`,
   partition to `cache/mm1B/fills_by_day/cal_day=YYYY-MM-DD/*.parquet`.
3. **Spot clock** (`fetch_binance_B.py`): Binance `data.binance.vision` daily 1s kline zips,
   BTCUSDT + ETHUSDT, 2024-10-24..2026-01-28 (924 day-asset files), sequential polite fetch,
   reduced to `(second, close)` parquet, cache-then-delete on the raw zip/CSV.
4. **Classification** (`classify_days_B.py`): per (day, asset), load that day + the previous
   UTC day's spot array, compute the 5 `r_R` log-returns per fill with a 5-second backward grace
   window, write `cache/mm1B/classified/day=YYYY-MM-DD_asset=XXX.parquet`.
5. **Stats** (`stats_B.py`, `aggregate_stats_B.py`): day-clustered ratio-estimator SE (derived
   below), exact Student-t bars, the 20-cell grid, sanity anchors, verdict.
6. **Anchor (a)** (`reconcile_anchor_a_B.py`): independent cross-check against
   `cache/prereg/tape/u1_day_shard=*.parquet`.

---

## 1. Worked join example (timezone / clock discipline)

Row from `cache/mm1B/classified/day=2024-10-24_asset=BTC.parquet`:

```
ticker=KXBTCD-24OCT2417-T67249.99  contracts=50  taker_side=yes  maker_price_c=54
result=yes  created_time=2024-10-24T12:11:14.681933+00:00 (UTC)
pnl_c = 54 - 100*[result=='yes'] = 54 - 100 = -46.0
epoch_s = 1729771874.681933  ->  k = floor(epoch_s) = 1729771874  (UTC second 12:11:14)
head required second = k-1  = 1729771873  (12:11:13, strictly BEFORE the fill's own second)
base(R=1)   required second = k-2   = 1729771872
base(R=300) required second = k-301 = 1729771573  (12:06:13)
```

All lookups hit the Binance 1s array directly (no grace-window fallback needed for this row).
`r_1 = ln(head/base_1) = 1.48e-7` (essentially flat over 1s), `r_300 = -1.03e-3` (a genuine ~10bp
move over the preceding 5 minutes) — this fill is UNEXPLAINED at (R=1,5bp) and (R=1,10bp) but
EXPLAINED at (R=300,10bp). Side-agnostic: the `|r|>=theta` test does not look at `taker_side`.

Kalshi `created_time` is `TIMESTAMPTZ`, always UTC on this feed; Binance kline `open_time` is
Unix time. `k`, `k-1`, `k-1-R` are all UTC integer seconds — no local-timezone conversion enters
anywhere in the classification.

---

## 2. Divergence found #1 — admission rule ambiguity (RESOLVED, documented, not improvised)

The frozen `universe` prose lists admission as: series_key exact match, settled, date range,
maker-short price in `[3,97]` — **no mention of a close-time timeband**. A first extraction
following that literal text produced **9,111,260 admitted rows / 1.03B contracts** — 10x the
`merge_strategy`'s stated expectation of "**~870K rows total**", which is itself explicitly
grounded in `archive_bounds_measured_before_freeze` (BTC ~731K prints, ETH ~138K prints), a figure
sourced from `cache/prereg/tape/u1_day_shard=*.parquet` — U1's *own* admitted population, which
additionally requires `created_time <= close_time - 60 MINUTES` and restricts each series to a
single `rung_class` (`KXBTC|B`, not `KXBTC|T`; `KXBTCD|T`, not other rungs).

This is a genuine tension in the frozen text, not a mechanical error on either side of it. It was
resolved by a structural argument, not by preference: **sanity anchor (a)** requires Stage B's
"all-fills maker GROSS EV" on the overlapping unit-sides to equal *minus* U1's taker GROSS EV
recomputed from `u1_day_shard`, within **0.05 c/ct**. Maker-GROSS and taker-GROSS are exact
negatives of each other **only when computed on the identical set of trades** (every taker fill
*is* the mirrored maker fill on that print) — two different, larger-than-U1 print populations
could not plausibly reconcile to 0.05 c/ct by chance. So anchor (a) is only satisfiable, as
written, if Stage B's admitted population is U1's admitted population restricted to the four
target series — i.e. the 60-minute timeband and the `rung_class` pairing are implicitly required by
the reconciliation anchor even though the `universe` prose doesn't restate them.

Applying U1's full admission funnel (price band + 60-min timeband + `rung_class` pairing) gives
**867,490 rows / 146,651,776 contracts / 457 days** — matching the archived "~870K" figure and,
per series, matching the pre-frozen archive numbers to the print: KXBTC 220,555 / KXBTCD 508,626 /
KXETH 49,934 / KXETHD 88,375. Anchor (a) then reconciles to **≤4.4e-16 c/ct** (floating-point
noise) on all 8 overlapping unit-sides — see §6. This is treated as the frozen resolution, and is
disclosed here rather than silently baked in.

---

## 3. Divergence found #2 — Binance kline timestamp-unit migration (BUG, fixed)

First full Binance fetch assumed `open_time` is always in **milliseconds** and divided by 1000.
Classification then showed **478,804 of 867,490 fills (55%) with a missing HEAD close** — every
single fill on every day from **2025-01-01 through 2026-01-28** (393 of 457 days, both assets,
100% of that day's fills each time — not a sporadic gap).

Root cause, confirmed by re-downloading and inspecting the raw CSV: Binance's 1s-kline archive
switched `open_time` from **milliseconds to microseconds** starting **2025-01-01** (verified
directly: `2024-10-24` row 1 = `1729728000000` (13 digits, ms); `2025-01-02` row 1 =
`1735776000000000` (16 digits, µs)). The blanket `//1000` left post-cutover "seconds" 1000x too
large, so essentially no fill on those days could find its own second in the spot array.

Fix: `fetch_binance_B.py` now auto-detects the unit per file from the magnitude of the first raw
`open_time` value (`>=1e14` → divide by 1e6, else divide by 1e3). All 786 affected
(asset,day) Binance files were deleted, re-fetched, and re-verified (min/max `second` now falls
inside the file's own UTC calendar day for all 924 files); the 773 affected classified day-asset
files were deleted and reclassified. **Post-fix: 0 head-missing and 0 base-missing fills at every
R, for every day, both assets** (verified over the full 867,490-row population, not a sample).
UNJOINABLE rate is therefore 0.0% for all 10 asset×R cells — no cell is INSUFFICIENT on that
floor, and the 5%/min-n floors (§7) are non-binding everywhere.

---

## 4. Cell table (pre-override numbers — see §5 for why the verdict column is overridden)

Volume-weighted (contract-weighted), net of fees (all four series verified live `quadratic` on
2026-07-30 → maker fee = $0.00; `cache/mm1B/fee_types_B.json`). `surv%` = unexplained contracts /
asset's total admitted contracts. Bar = exact two-sided Student-t quantile, alpha=0.0025,
df = n_days(unexplained)-1.

| Asset | R(s) | theta | Explained EV c/ct | Expl. n | Expl. contracts | Unexpl. EV c/ct | Unexpl. t | Unexpl. n | Unexpl. contracts | Unexpl. days | surv% | t-bar | raw verdict |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 1   | 5bp  | -0.388 | 13,228  | 2,692,987  | 1.291 | 3.668 | 715,953 | 119,418,944 | 457 | 97.8% | 3.0402 | PASS |
| BTC | 1   | 10bp | -2.180 | 3,491   | 789,698    | 1.276 | 3.676 | 725,690 | 121,322,233 | 457 | 99.4% | 3.0402 | PASS |
| BTC | 5   | 5bp  | -0.119 | 68,727  | 14,243,446 | 1.435 | 3.943 | 660,454 | 107,868,485 | 457 | 88.3% | 3.0402 | PASS |
| BTC | 5   | 10bp | -1.753 | 17,104  | 3,646,914  | 1.347 | 3.840 | 712,077 | 118,465,017 | 457 | 97.0% | 3.0402 | PASS |
| BTC | 15  | 5bp  | -0.010 | 165,854 | 33,221,901 | 1.726 | 4.548 | 563,327 | 88,890,030  | 457 | 72.8% | 3.0402 | PASS |
| BTC | 15  | 10bp | -0.801 | 51,499  | 10,651,737 | 1.450 | 3.900 | 677,682 | 111,460,194 | 457 | 91.3% | 3.0402 | PASS |
| BTC | 60  | 5bp  |  0.873 | 338,317 | 63,641,314 | 1.669 | 3.365 | 390,864 | 58,470,617  | 457 | 47.9% | 3.0402 | PASS |
| BTC | 60  | 10bp |  0.470 | 170,702 | 33,982,381 | 1.556 | 3.813 | 558,479 | 88,129,550  | 457 | 72.2% | 3.0402 | PASS |
| BTC | 300 | 5bp  |  0.889 | 519,505 | 92,683,183 | 2.404 | 5.033 | 209,676 | 29,428,748  | 457 | 24.1% | 3.0402 | PASS |
| BTC | 300 | 10bp |  0.698 | 371,558 | 69,682,656 | 1.993 | 4.112 | 357,623 | 52,429,275  | 457 | 42.9% | 3.0402 | PASS |
| ETH | 1   | 5bp  | -0.365 | 8,511   | 1,850,741  | 0.780 | 1.898 | 129,798 | 22,689,104  | 447 | 92.5% | 3.0406 | no-pass |
| ETH | 1   | 10bp | -1.287 | 2,734   | 597,644    | 0.744 | 1.901 | 135,575 | 23,942,201  | 447 | 97.6% | 3.0406 | no-pass |
| ETH | 5   | 5bp  | -1.081 | 30,423  | 6,293,146  | 1.306 | 2.677 | 107,886 | 18,246,699  | 447 | 74.4% | 3.0406 | no-pass |
| ETH | 5   | 10bp | -1.782 | 11,463  | 2,497,731  | 0.975 | 2.288 | 126,846 | 22,042,114  | 447 | 89.8% | 3.0406 | no-pass |
| ETH | 15  | 5bp  |  0.090 | 55,105  | 10,810,769 | 1.170 | 2.109 | 83,204  | 13,729,076  | 446 | 55.9% | 3.0407 | no-pass |
| ETH | 15  | 10bp | -0.981 | 25,617  | 5,340,005  | 1.160 | 2.498 | 112,692 | 19,199,840  | 447 | 78.2% | 3.0406 | no-pass |
| ETH | 60  | 5bp  |  0.170 | 86,619  | 16,478,354 | 1.766 | 2.767 | 51,690  | 8,061,491   | 442 | 32.9% | 3.0408 | no-pass |
| ETH | 60  | 10bp |  0.018 | 55,948  | 11,156,979 | 1.258 | 2.483 | 82,361  | 13,382,866  | 445 | 54.5% | 3.0407 | no-pass |
| ETH | 300 | 5bp  |  0.761 | 112,659 | 20,546,617 | 0.351 | 0.316 | 25,650  | 3,993,228   | 435 | 16.3% | 3.0411 | no-pass |
| ETH | 300 | 10bp |  0.699 | 91,200  | 17,099,230 | 0.683 | 0.923 | 47,109  | 7,440,615   | 441 | 30.3% | 3.0409 | no-pass |

`min_n` floors (≥150 days, ≥2000 prints, ≥200,000 contracts on the unexplained leg) are met on
every cell above — the tightest is ETH(300,5bp) at 435 days / 25,650 prints / 3,993,228 contracts,
still comfortably clear.

**Read literally against the frozen pass bar, all 10 BTC cells would PASS** (EV≥0.5c, signed
t≥bar, surviving-volume≥20%, min_n met). None of the 10 ETH cells clear the t-bar. **This is
exactly why §5 matters**: the frozen spec does not let a cell PASS on its own numbers alone.

---

## 5. Sanity anchor (b) — clock check — FAILS, and what that means for the verdict

Frozen rule: *"At (R=60s, theta=10bp) per asset: EXPLAINED volume-weighted EV must be < 0 AND <
UNEXPLAINED EV − 1.0 c/ct. Violation ⇒ classification clock or join broken ⇒ all cells
INSUFFICIENT pending fix; bars do not move."*

| Asset | Explained EV (R=60,10bp) | Unexplained EV | Gap (unexpl − expl) | Sign clause (<0) | Gap clause (≥1.0) | Anchor (b) |
|---|---:|---:|---:|---|---|---|
| BTC | +0.470 | 1.556 | 1.086 | **FAIL** (positive) | pass | **FAIL** |
| ETH | +0.018 | 1.258 | 1.240 | **FAIL** (positive) | pass | **FAIL** |

Both assets clear the *magnitude* clause but fail the *sign* clause: the "just-after-a-big-move"
leg is barely positive rather than negative. Per the frozen text this is mechanically a violation,
and the mechanical consequence — **all 10 cells INSUFFICIENT for that asset, bars do not move** —
is applied without exception in `aggregate_stats_B.py` (each cell's pre-override verdict is kept
under `verdict_preoverride` in the JSON for audit; the reported `verdict` is forced to
`INSUFFICIENT`). This overrides the BTC PASS row seen in §4.

**Investigation of whether this is the "broken clock/join" the anchor is designed to catch, or a
genuine empirical fact** (reported for the record; it does **not** change the mechanical verdict
above, per the non-negotiable against improvising around a frozen bar):

- Anchor (a) independently validates the ALL-FILLS population and P&L accounting to 4e-16 c/ct
  against U1's separately-coded pipeline (§6) — ruling out a join/admission/sign bug at the
  all-fills level.
- Post-→bug-fix (§3), UNJOINABLE is exactly 0% everywhere — ruling out a residual clock-alignment
  defect of the kind that produced the 55%-missing symptom the first time.
- The explained-vs-unexplained EV gap is **monotonic and smooth across the entire R grid** for
  both assets (BTC: −0.388, −0.119, −0.010, +0.873, +0.889 as R runs 1→300s; ETH: −0.365, −1.081,
  +0.090, +0.170, +0.761). A broken clock/join would be expected to produce a noisy or
  inconsistently-signed pattern, not this decay curve. The economically coherent reading: at short
  R (1–15s) a fill immediately following a large move is reliably adverse for the maker (strongly
  negative EV, exactly the anchor's hypothesis); by R=60–300s the "recent big move" signal is
  diluted, and it is swamped by U1's separately-established structural finding that Kalshi crypto
  takers lose money **unconditionally** (6-10c/round-trip at the extremes, positive maker EV
  averaged over everything in `[3,97]`) — so the explained leg drifts back toward (and BTC's does,
  barely, past) zero at the R the anchor happens to test.
- Conclusion offered, not adopted as the verdict: this looks like the anchor's specific fixed test
  point (R=60s) landing past the empirical sign-flip rather than a pipeline defect — but the
  frozen rule is mechanical and does not carve out that judgment call. Reported as **INSUFFICIENT,
  pending fix or re-registration of the anchor's test point**, exactly as instructed.

---

## 6. Sanity anchor (a) — U1 reconciliation — PASSES

Method (`reconcile_anchor_a_B.py`): GROSS = NET + FEE, and `fee_c = ceil(7·p·(1−p))` is a
deterministic function of price alone, computed identically by both sides on the same trades once
admission is matched (§2) — so comparing GROSS reduces algebraically to comparing NET, which is
exactly what `u1_day_shard` already stores (`sum_net_contract`). Full detail and derivation in the
script's docstring.

B maker-gross and the U1-derived target (`-(U1 net + fee)`) are exact negatives of each other by
construction once they match — shown here as B's value vs. the anchor target (`-U1_taker_gross`):

| unit | side | B contracts | U1 contracts | B maker-gross c/ct | anchor target c/ct | diff c/ct | pass (≤0.05) |
|---|---|---:|---:|---:|---:|---:|---|
| KXBTC\|B  | yes | 22,462,722 | 22,462,722 | 2.182  | 2.182  | 0.0     | yes |
| KXBTC\|B  | no  | 14,430,502 | 14,430,502 | -1.324 | -1.324 | -2.2e-16 | yes |
| KXBTCD\|T | yes | 45,209,106 | 45,209,106 | 3.578  | 3.578  | 4.4e-16 | yes |
| KXBTCD\|T | no  | 40,009,601 | 40,009,601 | -0.964 | -0.964 | 0.0     | yes |
| KXETH\|B  | yes | 4,863,276  | 4,863,276  | -0.774 | -0.774 | 0.0     | yes |
| KXETH\|B  | no  | 4,124,043  | 4,124,043  | -0.446 | -0.446 | -5.6e-17 | yes |
| KXETHD\|T | yes | 8,650,498  | 8,650,498  | 2.560  | 2.560  | 0.0     | yes |
| KXETHD\|T | no  | 6,902,028  | 6,902,028  | 0.070  | 0.070  | -1.4e-17 | yes |

**`B_contracts == U1_contracts` exactly on all 8 unit-sides** — Build B's independently-coded
extraction reproduces U1's independently-coded extraction's admitted population row-for-row.
`max_abs_diff_gross_c = 4.4e-16` (floating-point noise). `all_pass = true`. Full numbers:
`cache/mm1B/anchor_a_B.json` (embedded in `maker_stageB_B.json` as `anchor_a_detail`).

---

## 7. All-fills per asset (independent of R/theta; drives the decisive KILL check)

| Asset | prints | contracts | days | EV c/ct (net) | t | df | decisive KILL (EV≤0)? |
|---|---:|---:|---:|---:|---:|---:|---|
| BTC | 729,181 | 122,111,931 | 457 | **+1.254** | 3.604 | 456 | No |
| ETH | 138,309 | 24,539,845  | 447 | **+0.694** | 1.783 | 446 | No |

Neither asset hits the decisive KILL bar (all-fills EV ≤ 0). This all-fills EV is exactly the
*negative* of U1's taker EV over the same population (anchor a), so it is not new information —
it restates U1's "takers lose 6-10c" finding from the maker's side, pooled over the whole `[3,97]`
band, matching prior expectation and providing no basis by itself for a GO decision (queue-position
asymmetry: this is a front-of-queue optimistic pool bound, and per the frozen interpretation a
positive number here is necessary-but-not-sufficient even when the classification gate is clean).

**Per-series unbarred sensitivity** (descriptive only, outside the Bonferroni family):

| series\|rung | prints | contracts | days | EV c/ct | t |
|---|---:|---:|---:|---:|---:|
| KXBTC\|B  | 220,555 | 36,893,224 | 454 | +0.811 | 1.927 |
| KXBTCD\|T | 508,626 | 85,218,707 | 457 | +1.446 | 3.645 |
| KXETH\|B  | 49,934  | 8,987,319  | 438 | -0.623 | -0.825 |
| KXETHD\|T | 88,375  | 15,552,526 | 435 | +1.455 | 2.963 |

KXETH|B is the one series with a negative (though not significant) point estimate — pooling into
"ETH" mixes it with the positive KXETHD|T leg. Not gated; reported for the record.

---

## 8. Statistics construction (ratio-estimator day-clustered SE)

U1's own `day_clustered_t` (`spec_U1.py`) operates on **unweighted per-print day means**
(`mean/(sd/sqrt(n_days))`, `df=n_days-1`) — it has no contract-weighted variant. The frozen MM1
spec calls for a **contract-weighted "cluster-robust ratio-estimator SE on per-day (sum weighted
P&L, sum weights)"**, so Build B implements the standard combined-ratio cluster-variance estimator
(`stats_B.py`, documented in its docstring), which collapses to U1's own formula exactly when every
day carries equal weight:

```
per day d:  S_d = sum(contracts_i * pnl_i)      W_d = sum(contracts_i)
R_hat = sum(S_d) / sum(W_d)                        # the reported EV/ct
e_d   = S_d - R_hat * W_d
Var   = (n_days/(n_days-1)) * sum(e_d^2) / sum(W_d)^2
SE = sqrt(Var);  t = R_hat/SE;  df = n_days-1
```

Exact Student-t bars via `scipy.stats.t.ppf(1-alpha/2, df)` verified to match all 14 reference
quantiles in the frozen spec to 4dp (df 99→3.1026 ... df 456→3.0402).

---

## 9. Skip ledger (every skip, every reason, full population)

| stage | reason | n rows | n contracts |
|---|---|---:|---:|
| shard join | matched series/rung/settled/timeband/daterange, pre price-band | 929,399 | — |
| shard join | dropped: maker-short price outside [3,97] | 61,909 | — |
| shard join | **final admitted** | **867,490** | **146,651,776** |
| classification | binance day file missing | 0 | 0 |
| classification | head close missing (5s grace exhausted) | 0 | 0 |
| classification | base close missing, any R (5s grace exhausted) | 0 | 0 |
| classification | no fills for asset that UTC day (both assets not always active same day) | 10 day-asset combos | — |
| binance fetch | daily zip download/parse failure | 0 / 924 | — |

Admitted population by series\|rung: KXBTC\|B 220,555 (36,893,224 ct); KXBTCD\|T 508,626
(85,218,707 ct); KXETH\|B 49,934 (8,987,319 ct); KXETHD\|T 88,375 (15,552,526 ct). 457 distinct
UTC admitted-fill days overall (BTC legs: 457; ETH legs: 435-447, consistent with the frozen
415-436 archive-bounded range once the pooled-vs-per-series distinction is accounted for).

A coarse duplicate-key check on `(ticker,created_time,contracts,taker_side)` flagged 17,135
"collisions" out of 867,490 rows; verified as **not** a join fan-out (`ticker_dim.parquet` has zero
duplicate tickers, so the shard→dim join cannot fan out) — these are simply distinct `trade_id`s
sharing a coarse key (simultaneous partial fills), not duplicated rows. Not logged as a skip
because no rows were dropped or need dropping.

Directional (toward-taker) sensitivity variant and Stage A/C descriptive work were **not** run —
Stage A/C carry no bar and are out of scope for a Stage-B gating deliverable, and the directional
variant is explicitly unbarred/optional; given the INSUFFICIENT verdict from anchor (b), it was
deprioritized in favor of the bug-fix and reconciliation work above. The classified per-day cache
(`cache/mm1B/classified/`) retains all 5 `r_R` values per fill, so the directional cut can be
computed directly without re-running extraction or the spot-clock join.

---

## 10. Bottom line

**Study verdict: INSUFFICIENT.** Sanity anchor (a) passes cleanly (independent cross-validation of
the extraction/accounting pipeline against U1's separately-coded pipeline, to floating-point
precision). Sanity anchor (b) — the classification-clock check — fails for both assets at its one
frozen test point (R=60s, theta=10bp): the "just after a big move" leg is barely positive rather
than strictly negative, even though the *magnitude* gap the anchor also requires is met, and even
though 9 of the other 9 R×theta combinations per asset show the theoretically-expected sign. Per
the frozen rule this is a mechanical INSUFFICIENT with bars not moving, and it is reported that
way rather than rescued by the (real, but unregistered) argument in §5 that the pipeline itself
looks clean. If re-registered, the natural next step is either re-testing anchor (b) at a shorter R
(where the sign condition holds cleanly for both assets) or accepting the current test point and
gating on it as designed.

Two real, non-trivial, independently-discovered issues are documented in full: an admission-rule
ambiguity in the frozen `universe` text resolved by the reconciliation anchor's own logical
requirement (§2), and a genuine Binance archive format change (ms→µs timestamps, 2025-01-01) that
silently broke 55% of the join before being caught, root-caused, and fixed with full before/after
numbers (§3). Both are exactly the class of finding a second independent build exists to surface.
