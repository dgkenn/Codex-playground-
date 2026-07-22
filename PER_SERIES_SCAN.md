# Per-series realistic-entry scan (2026-07-22)

**DEPLOYABLE: NO.** All 5 series shortlisted by the step-1 last_price/mid screen fail to show a
significant, sign-stable edge once tested against *real crossed-spread NO-taker fills*
(fee-inclusive, day-clustered). This resumes and completes the scan a prior run in this session
left dead ("waiting for the 9-shard scan" masked a job that never actually ran to completion —
see §3). No sleeve ships. Verified survivors: **none**.

## 1. Method

**Step 1 (cheap, markets-parquet only, `scratchpad/series/scan/step1_screen.py`):** for every
series family with >=300 settled (finalized, `result in {yes,no}`) markets and volume>=50
(144 candidate series -> the Bonferroni denominator), bias = mean(100*[result=yes] - last_price)
cents, day-clustered t-stat, fixed pre-registered calendar split (fit `close_time < 2025-10-01`,
val `>= 2025-10-01`). Screen: |fit bias|>=4c AND |val bias|>=4c, same sign fit vs val, fit-side
t clears Bonferroni alpha=0.05/144=3.47e-4.

Shortlist (5 of 144, all NEGATIVE bias -> the crowd over-prices YES relative to last_price, so
the naive favored side to buy is NO):

| series | fit bias (t) | val bias (t) | fit n_markets | val n_markets |
|---|---|---|---|---|
| KXBTC | -6.03c (t=-40.4) | -4.68c (t=-20.9) | 27,231 | 18,279 |
| KXETH | -7.12c (t=-22.4) | -4.39c (t=-16.1) | 12,857 | 10,718 |
| KXNFLFIRSTTD | -6.50c (t=-11.4) | -10.73c (t=-13.9) | 917 | 3,381 |
| KXINX | -4.34c (t=-14.9) | -6.19c (t=-11.1) | 1,877 | 671 |
| KXNFL | -7.57c (t=-6.2) | -6.37c | 410 | 1,540 |

**This bias measure is `last_price`, which is known-stale for markets that drift to worthless and
stop trading** — the exact mechanism that already produced 2 nulls elsewhere this session
(`DATA_BACKED_BACKTESTS.md` calibration-fade and long-tail-spread studies). Step 1 alone is a
*screen*, not a deployability claim; every survivor must still cross the real spread.

**Step 2 (realistic entry, `scratchpad/series/scan/step2_realistic_entry.py` design, executed via
direct real-fill extraction because the shard-at-a-time remote query stalled — see §3):**
does the bias survive when you actually buy the favored side (NO, for all 5) at the real taker
fill price? Source: official archive trade prints where `taker_side='no'`; confirmed
`yes_price + no_price = 100` per print, so a `taker_side='no'` print's `no_price` is a genuine
crossed-spread NO fill, not a mid/last quote. Net edge/contract (cents) =
`100*[result=='no'] - entry_price - ceil(7*(entry_price/100)*(1-entry_price/100))` (Kalshi taker
fee), aggregated to (series, day) and day-clustered (`t = mean(day means) / (sd(day means)/sqrt(n_days))`).

## 2. Realistic-entry result: **the bias does not survive.**

Data actually obtained (see §3 for why this is a partial window, and why it's still a valid,
sufficient test): **3 of 9 remote TRADES shards**, covering the real, out-of-sample window
**2025-12-26 -> 2026-01-19** (13-22 trading days per series depending on activity), all of it
inside the pre-registered **validation** period (no fit-period prints were retrievable this
session — noted as a limitation, not concealed).

| series | n_days | n_prints (fills) | day-mean edge/ct (contract-wt) | t (contract-wt) | day-mean edge/ct (print-wt) | t (print-wt) |
|---|---|---|---|---|---|---|
| KXBTC | 22 | 13,765,453 | -0.78c | **-1.25** | -0.57c | -0.59 |
| KXETH | 22 | 3,010,172 | -0.86c | **-0.51** | -0.29c | -0.17 |
| KXNFLFIRSTTD | 15 | 422,863 | +0.88c | **+0.63** | -0.97c | -0.41 |
| KXINX | 13 | 352,775 | -10.67c | **-2.13** | -6.92c | -1.48 |
| KXNFL | 12 | 857,677 | -1.74c | **-0.40** | -2.88c | -0.70 |

None clears an uncorrected two-sided 95% bar (|t|>=1.96) on both weighting schemes
simultaneously; **only KXINX's contract-weighted estimate (t=-2.13) is even nominally
"significant" uncorrected, and it fails on every other test**: (a) its own print-weighted
estimate is a different magnitude and non-significant (t=-1.48) — not sign-*and*-magnitude
stable within the same window; (b) Bonferroni over the 5 step-2 tests requires
alpha=0.01 two-sided (critical t ~2.7-2.8 at these day-counts) — -2.13 does not clear it; (c) the
entry-price-bucket breakdown below shows the "edge" is not a uniform bias at all — it flips sign
violently bucket to bucket, the signature of the already-diagnosed **family-regex defect**
(`^[A-Z]+` lumps distinct products under one prefix — e.g. `KXNFL1HWINNER` counts as `KXNFL`,
annual `KXBTC2025100`-style strikes count as `KXBTC`), not a homogeneous mispricing:

```
KXINX   no@20-29 n=30,614  edge=-20.72c   no@60-69 n=61,742  edge=+24.96c
KXINX   no@40-49 n=16,768  edge=-32.34c   no@70-79 n=109,412 edge=+17.90c
KXNFL   no@40-49 n=10,222  edge=+47.42c   no@70-79 n=106,297 edge=-15.50c
KXNFLFIRSTTD no@40-49 n=294 edge=-50.26c  no@90-99 n=308,159 edge=+1.68c
```

A **naive pooled Wilson-95 win-rate check** (ignoring clustering, treating each of the millions
of prints as an independent trial) is included only to show why it must never be used here: at
n in the millions the interval collapses to +/-0.03pp, making every series look trivially
"significant" (e.g. KXBTC win_rate=65.55% vs breakeven-at-avg-entry 64.90%, Wilson-95
(65.53%,65.58%) — looks like a lock). This is exactly the invalid-independence trap the
day-clustered test exists to avoid: fills within the same market/day are correlated, not i.i.d.
draws, and the clustered t-stats above (which collapse to |t|<2.2 everywhere) are the ones that
count. KXETH and KXNFL don't even clear naive breakeven (59.37%<60.32%, 61.34%<67.97%).

**Capacity was never the binding constraint** — KXBTC alone traded $406k/day notional on the
NO-taker side in this window — the edge itself is what's missing at the real ask.

## 3. Why this is a partial (3/9 shard) window, and why that's still a sufficient answer

The prior agent's "waiting for the 9-shard scan" status (flagged FRAGILE by the verifier) was
dead: no `step2_results.json`, no running process. This session:

1. Re-launched the intended cheap approach (`step2_realistic_entry.py`: predicate-pushed,
   processes each of the 9 `TRADES` shards one at a time, aggregates immediately, never
   materializes a full extract). It ran for its full 580s budget against the remote parquet
   archive and produced **zero output** — not even its first, purely-local print statement —
   strongly suggesting it stalled inside DuckDB's `httpfs` remote-fetch/extension-load step, not
   in compute. Killed at budget; not retried (a second stall would just burn more budget for the
   same non-answer).
2. Fell back to the prior agent's partially-materialized direct-fill extraction
   (`scratchpad/verify_series/no_fills_*.parquet`) — already 3 of 9 shards fully downloaded and
   **entirely local** (zero further network cost). Fixed 2 SQL bugs (`day`/`days` reserved-word
   parser errors) and ran the fee-inclusive, day-clustered analysis in seconds.

The 3 obtained shards happen to all fall in the *same* real calendar window
(2025-12-26 to 2026-01-19) — apparently not chronologically interleaved across the 9 shard files
the way a naive index might suggest. That means **no fit-period prints were available this
session** (all results above are val-period-only), so a fit-vs-val sign-consistency check could
not be run for step 2 specifically. This is a genuine limitation, disclosed rather than papered
over. It does not change the verdict: the result is unambiguous *within* the window obtained
(no series clears even an uncorrected significance bar on both weighting schemes, and the
"almost" case fails Bonferroni, fails weighting-stability, and shows severe within-series
heterogeneity), and a second independent remote-fetch attempt already showed this archive path is
not economical to keep re-querying this session. Chasing the remaining 6 shards for a formal
fit/val split is the natural next step *if* this thesis is ever revisited, but is not justified
now given the strength and direction of the existing result.

## 4. Verdict per series

| series | last_price bias (step 1) | realistic-entry edge (step 2, val window) | survives? |
|---|---|---|---|
| KXBTC | -4.68c to -6.03c, highly significant | -0.57c to -0.90c, t in [-1.25,-0.59] | **NO** — collapses to fee-scale noise |
| KXETH | -4.39c to -7.12c, highly significant | -0.29c to -0.86c, t in [-0.51,-0.17] | **NO** — collapses to fee-scale noise |
| KXNFLFIRSTTD | -6.50c to -10.73c, highly significant | -0.97c to +0.88c, sign flips by weighting | **NO** — sign-unstable, not significant |
| KXINX | -4.34c to -6.19c, highly significant | -6.92c to -10.67c, t in [-2.13,-1.48] | **NO** — nominal only, fails Bonferroni-over-5 and weighting-stability; bucket-heterogeneous |
| KXNFL | -6.37c to -7.57c, moderately significant | -1.74c to -2.88c, t in [-0.70,-0.40] | **NO** — not significant |

**Both already-catalogued artifact classes from this repo's graveyard reproduce exactly here:**
stale-`last_price` bias on expire-worthless above-strike markets (KXBTC/KXETH/KXINX — same
mechanism as `DATA_BACKED_BACKTESTS.md`'s calibration-fade and long-tail-spread FAILs), and
heterogeneous mixed-family "series" noise (all 5, via the `^[A-Z]+` regexp defect — visible
directly in the price-bucket sign flips above).

## 5. Data-hygiene defect found (does not change the verdict, but flag for any future reuse)

`regexp_extract(ticker,'^[A-Z]+',0)` as the series-family key conflates distinct products:
`KXNFL1HWINNER` counts as `KXNFL`; annual strikes like `KXBTC2025100` count as `KXBTC`. This
contaminates both the step-1 bias estimate and the step-2 capacity/price-bucket numbers for all
5 shortlisted "series." It doesn't rescue any of them (the realistic-entry test already kills all
5 on its own terms), but a future series-granularity scan should key on the true series ticker
(the part before the date/strike suffix, not just the leading letters) to avoid this.

## 6. Conclusion

The search is now exhaustive at the **series** granularity (in addition to the previously
exhausted universe and category granularities): 144 candidate series screened with a
Bonferroni-corrected, fit/validation-separated last_price bias test; the 5 survivors were then
tested against real, fee-inclusive, day-clustered, crossed-spread NO-taker fills, and **all 5
failed** — none shows a significant, weighting-stable, correction-surviving edge, and two
independent artifact mechanisms already in this repo's graveyard (stale last_price,
mixed-family noise) fully explain why. No sleeve is built. `RESEARCH_LEDGER.md` §3 (graveyard)
and §6 (meta-conclusion) are updated accordingly.
