# wx_maker_accrual.md — maker-study data pipeline: verify, accelerate, preliminary signal

Date: 2026-07-20. Scope: `wx_maker_study.py` is BLOCKED on `wx_book_snapshots.jsonl` accrual. This note
covers (1) end-to-end pipeline verification, (2) what was fixed/accelerated, (3) preliminary numbers or an
honest ETA.

## 1. Pipeline map (corrected)

The operator brief pointed at `kwx-marketwatch.yml` as the writer workflow. That workflow exists but is
unrelated — it's a **weekly** Kalshi series-listing watcher (new-city detection), never touches
`wx_book_snapshots.jsonl`, and runs Mondays only. The actual writer is:

- **Script**: `wx_capacity_probe.py --snapshot` (function `snapshot()`)
- **Workflow**: `.github/workflows/kwx-depthprobe.yml` — cron `4,34 18-23 * * *` + `4,34 0-1 * * *`
  (every ~30 min, 18:00–01:59 UTC), plus a daily `--report` leg at `40 1 * * *`.
- **Consumer**: `wx_maker_study.py` reads the same file defensively (tolerates extra/missing fields per its
  own docstring contract).

## 2. VERIFY — two problems, not one

**(a) Cadence problem (as briefed)**: `wx_book_snapshots.jsonl` had only 86 rows across 3 sweeps. GitHub
Actions run history for `kwx-depthprobe.yml` (4 completed runs, all green — `git log`/Actions API) shows
firings landing **~60 min apart** despite the 30-min cron (`19:36`, `22:02`, `23:02`, `00:05` UTC on
2026-07-19/20) — GitHub silently drops a repo's second within-hour schedule trigger under platform load,
a known Actions behavior, not a script bug. So the *effective* cadence was ~1 sweep/hour, not ~1/30min.

**(b) Schema problem (NOT previously flagged, and more serious)**: every committed row is missing
`running_extreme_f`. `wx_maker_study.load_snapshots()` requires it to decide "the rung is approaching lock"
(`simulate()`'s `i0 = next(... s["ext"] is not None ...)`). With `ext` absent on 100% of rows, **zero
hypothetical placements can ever be made, at any row count** — the study was not merely undersampled, it
was structurally wedged. Confirmed live:

```
$ python wx_maker_study.py --report
  lines=86  usable=86  skipped=0  no-running-extreme=86
  ... all cells n=0 at both X=1.0F and X=2.0F ...
```

This is why "accrue more time" alone would never have unblocked the study — the fix had to happen in the
writer, not just the scheduler.

**Confirmed the rest of the pipeline is sound**: ran `wx_capacity_probe.py --snapshot` live against real
Kalshi markets — both `yes_bid_levels`/`yes_ask_levels` (full two-sided ladders), `depth_at_or_below_98c`,
correct timestamps, and near-lock gating (`quote_yes_ask_c` in `[50,98]c`) all populate correctly.
`wx_maker_study.py --selftest` and `kwx_selftest.py` both pass unchanged (15+7 checks, respectively).

## 3. What changed (this branch, `wx_capacity_probe.py`)

1. **`running_extreme_f` now logged** (schema bumped `v1` → `v2`). `snapshot()` calls
   `R.feed_for_station(station).running_extreme(station, lst_date, offset, kind)` — the exact same
   read-only feed call `kwx_runner.py` already uses to gate live fires — once per (station, lst_date, kind)
   per sweep, cached and reused across every rung of that event (not one feed call per rung). Verified live:
   15/16 near-lock events got a populated `running_extreme_f` in a test sweep (the 16th, `KXLOWTDEN`, had a
   feed outage and correctly logged `null`, matching the study's documented tolerance for absence).
   `kwx_runner.py` itself was **not modified** (read-only import, per the no-touch list).
2. **`--snapshot-loop [--minutes M] [--every E]`**: runs repeated `--snapshot` sweeps inside one process
   (default 25 min budget, ~5 min apart with ±20% jitter), so density comes from inside a single job instead
   of depending on cron precision GitHub isn't honoring. Verified with a short local budget (2 sweeps in
   0.6 min at 0.25-min spacing).
3. **`--prune-days N`** (default 21): rewrites the jsonl keeping only the last N days, to bound growth now
   that sweeps are denser. Verified idempotent (no-op when nothing is old enough to drop) and destructive-path
   tested on a scratch copy.
4. Schema doc (`wx_book_snapshot_schema.md`) updated: `running_extreme_f` field, `schema_v` history note
   (v1 rows are NOT backfilled — readers must keep tolerating its absence on old rows), retention note.

`kwx_runner.py`, `kwx_paper_gate.py`, `kalshi_exec.py`, `kwx_daily_digest.py` were **not touched**.

## 4. What changed (separate `batch/maker-accel-main` branch, workflow only, off `origin/main`)

`.github/workflows/kwx-depthprobe.yml`:
- Widened the dense window's start hour from 18 UTC to **17 UTC** (per the operator's 17–24 UTC ask).
- Each firing now runs `wx_capacity_probe.py --snapshot-loop --minutes 18 --every 5` (≈4 sweeps/firing,
  ~5 min apart) instead of a single `--snapshot` call — the "loop inside one leg" pattern `kwx-live` uses
  for continuity, applied here without its self-chain/pre-chain machinery (this is read-only data collection
  with no uptime requirement, so a plain cron-triggered burst is enough; no extra dispatch loop or Actions-
  minutes cost). `timeout-minutes` raised 10 → 24 to fit the 18-min budget plus setup/push slack.
- Daily report leg now also runs `--prune-days 14` before committing.
- Kept the `18-23`/`0-1` cron pair (renamed to `17-23`/`0-1`) as a coarse bootstrap — even if GitHub only
  honors ~1 firing/hour, each firing now yields ~4x the sweeps it used to.

**Expected effect**: ~1 sweep/hour (observed) → ~4 sweeps/hour (each firing's internal burst), independent
of whether GitHub's scheduler cooperates with the 30-min cron.

## 5. Preliminary signal

**None available yet, honestly.** All 86 committed rows predate the `running_extreme_f` fix (schema v1) —
`--report` against the current committed file returns **n=0 in every cell** (shown above), because no row
has ever had the field the placement logic requires. There is no cell to report a Wilson CI on; reporting
one from this data would misrepresent "no candidate" as "no signal."

**Expected accrual at the new cadence + ETA to a decision-grade sample** (order-of-magnitude, flagged as
uncertain — see caveats):

- Observed near-lock row rate: ~21–33 rows/sweep (avg ~27) across all cities/kinds, fairly stable across the
  one evening/overnight sample collected so far.
- Of 86 committed rows, only **7 (8%)** are HIGH floor-only ("T"-type) rungs — the study's in-scope class
  (`SCOPE: HIGH floor-only rungs`). That sample was collected 22:00–00:05 UTC (US evening/overnight), when
  LOW rungs dominate near-lock activity; the 17–24 UTC dense window targets US afternoon, when HIGH rungs
  should dominate instead, so the in-scope share during the accelerated window is plausibly higher than 8%
  — this is the single biggest unknown in the estimate below.
- At ~4 sweeps/hour over an 8h window (17:00–01:00 UTC) ≈ 32 sweeps/day × ~27 rows/sweep ≈ **~860 near-lock
  rows/day**, of which a rough 15–30% in-scope share (widened from the 8% overnight baseline for the
  afternoon-HIGH-skew reason above) ≈ **~130–260 HIGH-floor rows/day**, spread over the day's ~10 active
  HIGH city-rungs.
- A **candidate placement** additionally needs ≥2 same-ticker snapshots (one "approaching," at least one
  later, for fill evidence) with `running_extreme_f` populated (~94% coverage observed) and not already
  crossed/locked at placement. Expect roughly **half to two-thirds** of in-scope rung-days to qualify.
- **Estimate: on the order of 5–15 usable candidate placements/day** once the accelerated workflow is live
  through a full afternoon window, i.e. **roughly 1–2 weeks** (per the module's own "1-2 weeks" target in
  its docstring) to reach a low-double-digit `n` per (X, bid) cell — enough for a Wilson CI that's
  informative rather than vacuous, though still wide at that n. A decision-grade sample (CI tight enough to
  clear or reject the `+1.1c/ct` taker baseline with confidence) likely needs several weeks beyond that,
  consistent with the module's own framing.

**Caveats on the estimate**: single-sweep sample, evening-only, small n (38 unique tickers, 3 sweeps) — the
8% in-scope share, the 15–30% afternoon-adjusted share, and the fill-qualification rate are all rough,
directionally-reasoned guesses, not measurements. Rerun this section once a few days of `schema_v=2` data
land; `wx_maker_study.py --report` will show the real numbers with no further code changes needed.

## 6. Rate-limit / safety notes

Read-only public endpoints only (order book, event listing). `BOOK_SLEEP_S=0.2s` between per-rung book
requests (unchanged). `--snapshot-loop` jitters the inter-sweep gap ±20% to avoid a fixed-interval pattern.
Single `kwx-depthprobe` concurrency group (unchanged) ensures no overlapping bursts. No auth, no orders —
this module and its workflow never import `kalshi_exec`, never read Kalshi credentials.
