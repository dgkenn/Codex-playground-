# Data-backed backtests: weather-fade + long-tail re-runs (2026-07-21)

**Headline: the weather-fade edge is NOT real.** Both weather specs that actually produced
results this run FAIL against their pre-registered bars, and the adversarial pass found the
Sonnet-side headline number understated the loss (corrected net EV is *worse* than claimed, not
better). No sleeve ships. Verified survivors: **none**. Every claimed positive result below was
run through a Fable adversarial-verification stage before being written up, per house policy.

## 1. The data unblock

The 2026-07-20 illiquid-markets funnel concluded Kalshi's history was walled to ~1-2
events/series and treated that as a hard backtesting limit. That conclusion was wrong: the
`GET /markets` and `GET /markets/trades` endpoints wall to a rolling ~3-month live window, but
two complementary free sources give complete, gapless history:

- **`kx_history.py`** (new this run, read-only, no orders/secrets):
  - **A) Parquet archive** (`TrevorJS/kalshi-trades` on HF, CC-BY-4.0, ~172M trades, Jun2021-Jan2026,
    cross-checked against `Jon-Becker/prediction-market-analysis`, MIT, ~72M trades, same
    universe). DuckDB predicate-pushdown over remote parquet -- used for bulk aggregate scans
    (millions of markets in one query) without downloading the full archive.
  - **B) Kalshi official `/historical/*` API** -- authoritative, always-current, cursor-paginates
    to series inception. Used for per-market/per-series spot checks.
- This is what made today's re-backtests possible at all: the long-tail studies below scan
  **2.16M qualifying markets / 1,807 series** and the weather studies scan **~21.3k settled
  daily-temperature markets** -- both far beyond what the walled live API could ever return.

All queries this run were read-only aggregate SQL / predicate pushdown (never a full-table
download), caches were written under a scratch dir and deleted after use, and the mechanical-lock
live path (`kwx_runner.py`, `kwx_paper_gate.py`, `kalshi_exec.py`) was never touched.

## 2. NEW weather thesis: fade overpriced certainty / settlement-mismatch

Two specs were pre-registered under this thesis. Only one of them actually ran to completion and
produced a verifiable result; the other was pre-registered but never executed in this session --
that distinction matters and is preserved below rather than papered over.

### 2a. `weather:calibration-fade` -- RAN. Verdict: **FAIL** (CONFIRMED by adversarial review).

Pre-registered (`.../weather_calib/PREREGISTRATION.md`, frozen before any outcome data was read):
fade near-certainty prints (yes-price in [0,1)/[1,3)/[3,5)/[5,10) or (90,95]/(95,97]/(97,99]/(99,100])
in the last 30-60 minutes before close, buy the cheap/contrarian side at the crossing price,
fee-inclusive net EV, day-clustered stats, Bonferroni-corrected (8 bins) 99.375% CI pass bar on
FIT (`close_time < 2025-09-01`), replication check on VALIDATION (`>= 2025-09-01`).

- Universe: ~21.3k finalized `KXHIGH*`/`KXLOWT*` markets; only 3,233 (~15%) had any trade in the
  30-60min pre-close window at all (itself informative -- most daily-temp markets go quiet well
  before close).
- **Zero of 8 bins clear gate 1** (n>=300, corrected lower bound >= +2.0c). The only two bins
  with enough sample (`low_1_3`, n=645 FIT/1,307 VAL; `high_99_100`, n=412 FIT/325 VAL) are
  essentially perfectly calibrated and show a clean, fee-sized **negative** net EV in both
  splits -- exactly what an efficiently, correctly-fee-priced market looks like.
- 15-minute-window robustness check (informational, not pass/fail) shows the same picture.

**Adversarial correction (worse than the headline claim, not better):** the analysis priced
every bin at the bin's midpoint crossing price. In the `high_99_100` bin, all **737 pooled
prints are at exactly 99c** (no spread across 99-100), so a fade there buys NO at **1c, not
0.5c** -- corrected net EV is **-2.0c/contract**, worse than the claimed -1.50c. In `low_1_3`,
~95% of prints are at 1c -- corrected net EV is **~-1.9c**, slightly less bad than the claimed
-3.0c. The direction of the verdict (FAIL, no fee-surviving edge) is unchanged either way; the
fee alone is what these near-certainty markets charge you to trade, and there is no mispricing
left to harvest once it's paid. Two secondary issues noted (immaterial to the verdict): the
day-clustered CI used z instead of the pre-registered t with D-1 df (doesn't matter -- Wilson was
the binding, wider interval in both headline bins, and per-day rates are degenerate 0/1); and
multiple-comparisons was corrected only within this study's 8 bins, not across the ~32 tests this
run touched across all 4 specs -- a fuller cross-spec correction only raises the bar further and
strengthens the FAIL.

### 2b. `weather:settlement-mismatch` -- **NOT actually run this session.** Status: UNTESTED, not FAIL.

Pre-registered (`.../weather_settle/PREREG.md`, frozen before any result-column query): does the
CLI/ASOS settlement authority ever disagree with a market's own near-certain (>=97c or <=3c)
last-traded lock price on 8 high-volume `KXHIGH*` cities, with a Bonferroni-corrected (20
candidate subsets) fit/validation flagging rule. The analysis script
(`.../weather_settle/weather_settle.py`) implements the spec, but **no `results.json` (or any
output) exists for it** -- the query was never executed to completion in this session.

The verdict text supplied for this label going into this writeup was traced by the adversarial
pass to a mismatch: the claim handed to the verifier was a stale status message ("waiting for
the background trades query...") rather than a result, so the verifier instead checked whatever
artifact it could match -- which turned out to be the **`longtail:spread`** results (144 series,
KXETH15M archive gap, 34/34 days), not a weather settlement study at all. That "CONFIRMED" is
real and correctly describes `longtail:spread` (see 3a below); it is **not** evidence about
settlement mismatch in either direction. **The settlement-mismatch thesis remains genuinely
untested** -- pre-registered, coded, never run. It should not be counted as a kill or a survivor;
it needs its own execution and its own adversarial pass before either label applies.

**Bottom line on the weather-fade thesis the operator cares about most: it is not real.** The
one spec that was actually tested and verified (`calibration-fade`) fails decisively and the
correction makes the loss larger than first reported, not smaller. The other half of the thesis
(`settlement-mismatch`) was never tested -- that is a gap to close next session, not a passing
result to bank on.

## 3. Long-tail re-backtest

Two specs from `ILLIQUID_MARKETS.md`'s two-mechanism family were pre-registered this run.

### 3a. `longtail:spread` (wide-spread / semi-thin passive capture) -- RAN. Verdict: **FAIL** (CONFIRMED).

Pre-registered (`.../lt_spread/PREREG.md`): generalize the prior funnel's data-starved
"off-air passive quoting" mechanism (756 fills / 3 event-days / 2 hand-curated series) across the
**entire non-weather semi-thin band** (lifetime volume 20-500 contracts, `TrevorJS/kalshi-trades`
archive, all 1,807 series), resting-quote fill simulation with `k in {0.05, 0.08, 0.12}` chosen
on FIT, adverse selection measured against **realized settlement** (not a later print), chronological
40/60 fit/validation split, day-clustered stats, Bonferroni/2 (2-mechanism family).

- Universe: 2,162,572 qualifying markets. Validation: **39,220 fills / 34 distinct days / 144
  distinct series** (min-n gate: >=150/>=20/>=5 -- cleared by 100x+).
- A units bug was caught before trusting any number (yes_price is 0-100 cents in the archive, not
  0-1 dollars as the original script assumed) and fixed.
- **Validation net markout: -14.32c/contract, day-clustered t = -29.57 (34 clusters), p=1.0 for
  a positive edge.** Raw markout (pre-fee) is -12.55c -- this is genuine adverse selection on
  realized settlement, not a fee story (fee is only 1.77c of the loss). Win rate 34.5%
  (Wilson95 [0.340, 0.349]), far below the 50% sanity floor. Both mandatory sub-checks (aggregate,
  "late" fills closest to settlement) fail; late fills are *worse* (-14.84c). 100% of the 31
  series with >=100 fills, and 34/34 validation days, individually show negative raw markout --
  uniform across the cross-section, not one bad day or series.
- **Honest capacity: $0/month.** All four pre-registered pass-bar conditions fail.

**Adversarial findings (direction-neutral, don't flip the FAIL, logged for the record):** the
prereg required >=3 trades/market but `02_run.py` never enforced it, so some 2-trade markets
entered the universe; the 34 validation days are one contiguous window at the archive tail
(2025-12-26 to 2026-01-28), not spread across regimes, and the population that dominates the
semi-thin band by fill count is esports/NFL/NBA props/15-min crypto strikes (continuously
repriced, thin *because short-lived*) rather than the original funnel's curated
attention-scarcity series (mentions, slow macro prints) -- a related but not identical
population, and the FAIL is decisive for this broader band without literally closing out the
original narrower census; the reported t=-29.57 is on unweighted day means (-13.87c) while the
headline is the pooled mean (-14.32c) -- both reproduce and both are decisively negative, the
writeup just didn't say which estimator the t used.

### 3b. `longtail:stale-resolution` -- **NOT actually run this session.** Status: UNTESTED, not FAIL.

Pre-registered (`.../lt_stale/PREREG.md`): on obscure (median volume <=500) non-weather series,
does a settled-by-record outcome ever still trade away from 0/100 with real size, >=30min before
formal close, with a >=30-instance / >=10-day pass bar and a secondary causal-momentum robustness
check. `run_query.py` implements the universe query but **its own output (`joined.json`) does not
exist** -- it was never executed to completion.

The adversarial pass confirmed this procedurally (the claim carried no numbers, so most attack
axes -- fillability, fees, survivorship, capacity -- have no target to check): a background query
that *was* running during this session turned out to be an **unregistered `KXNHLPTS` pull**, not
`lt_stale`'s own spec -- a different, unpre-registered analysis. It also flagged that NHL
market-open timestamps cluster ~4 seconds after `lt_spread`'s FIT/VAL split boundary
(2025-12-23 00:01:32 vs 00:01:36-40), which is almost certainly incidental (same archive-tail
ingestion moment for two unrelated queries) but means if anyone builds a positive claim out of
that stray pull later, it needs its own pre-registration and its own cross-spec Bonferroni charge
-- the existing preregs only correct within-family (Bonferroni/2 for `lt_spread`, /8 bins for
`weather_calib`), not across all 4+ specs this run touched. `stale-resolution` remains genuinely
untested and should be run fresh next session, not inferred from the stray pull.

## 4. Every verdict, including kills

| Label | Ran to completion? | Adversarial verdict | Cap | Real edge? |
|---|---|---|---|---|
| `weather:calibration-fade` | Yes | CONFIRMED FAIL (corrected EV worse than claimed) | $0/mo | **No** |
| `weather:settlement-mismatch` | **No** (no results.json) | N/A -- verifier checked wrong artifact | $0/mo | **Untested** |
| `longtail:spread` | Yes | CONFIRMED FAIL (decisive, 39,220 fills/34d/144 series) | $0/mo | **No** |
| `longtail:stale-resolution` | **No** (no joined.json) | Procedural CONFIRMED (non-execution) | $0/mo | **Untested** |

All 4 labels close at cap=$0. **Verified survivors this run: none.** Two of the four specs
(`calibration-fade`, `lt_spread`) are decisive, adversarially-confirmed kills -- they are done,
do not re-run them without a new mechanism. The other two (`settlement-mismatch`,
`stale-resolution`) are open items: pre-registered, coded, not executed -- they are neither kills
nor passes and should be run (and adversarially verified) fresh before anyone treats either as
evidence in either direction.

## 5. Honest capacity table

| Sleeve / spec | Status | $/month capacity | Basis |
|---|---|---|---|
| `weather:calibration-fade` | FAIL | $0 | 0/8 bins clear pre-registered bar on FIT; the two liquid bins are negative in both FIT and VAL |
| `weather:settlement-mismatch` | Untested | $0 (no claim to price) | Study never executed |
| `longtail:spread` | FAIL | $0 | All 4 pass-bar conditions fail on 39,220-fill validation; capacity calc (`04_capacity.py`) correctly skipped per its own gate |
| `longtail:stale-resolution` | Untested | $0 (no claim to price) | Study never executed |
| **Total new capacity from this run** | -- | **$0/month** | -- |

This does not change the fund's existing capacity picture (`PATH_TO_4K.md`, `p4k_params.json`
sleeves) -- no new sleeve is registered, no existing sleeve's numbers change, because nothing here
survived to a deployable state. Per house rules, a null is a fine, final answer, and two of these
four are being reported as exactly that.

## 6. Reproduction artifacts

- `weather_calib/`: `PREREGISTRATION.md`, `analyze.py`, `robustness_15min.py`, `results.json`,
  `results.md` -- complete, reproducible, this run's only weather PASS/FAIL result.
- `weather_settle/`: `PREREG.md`, `weather_settle.py` -- pre-registered, not executed; needs a
  DuckDB run against `kx_history.py`'s parquet path to produce `results.json` before it can be
  scored.
- `lt_spread/`: `PREREG.md`, `00_scope.py`, `01_pilot.py`, `02_run.py`, `03_fills.py`,
  `04_capacity.py`, `results.json`, `val_by_day.csv`, `val_by_series.csv` -- complete,
  reproducible, this run's only long-tail PASS/FAIL result.
- `lt_stale/`: `PREREG.md`, `run_query.py` -- pre-registered, not executed; needs its own run
  (not the stray `KXNHLPTS` pull) to produce `joined.json` before it can be scored.

(These live under the scratch/worktree data-backtest directory used for this run, not under the
repo root -- listed here for provenance; nothing here needs to be copied into the repo since none
of it is a deployable sleeve.)
