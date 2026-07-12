# Kalshi Weather vs NBM — CLV Verdict

**Date:** 2026-07-12 · **Branch:** `claude/polymarket-bot-live-ready-vw7ut5`
**Data:** `gha_data/weather/weather_clv_log.csv` on `gha-data`, 1,295 snapshot rows, 2x/day,
2026-06-15 .. 2026-07-11, 8 cities, 216 unique (city, day) events.

## What changed

The collector (`weather_clv_harness.py`) logged Kalshi book + NBM fair-value snapshots but never
implemented the "second pass" its own docstring described — `actual_high`/`settled` were always
blank, so `edge_verdicts.py` reported **WAIT (0 scoreable rows)** for every run.

Implemented the join: **`weather_settle.py`**. For each (event, bracket) row whose Kalshi market
has since closed, it calls the public `GET /markets?event_ticker=...` endpoint (no auth — verified
live) which, once a market is `status: finalized`, already returns both the per-bracket outcome
(`result`: yes/no) **and** the value Kalshi settled on (`expiration_value`, the observed high) in
one call — no NWS scrape needed for the common case (an NWS-observations fallback exists for
markets still unfinalized long after their target date, best-effort). It back-fills
`actual_high`/`settled` on every historical snapshot row of that bracket and appends CLV/paper-P&L
columns (`entry_prob, fee, edge, signal, outcome, pnl`) using the rule already documented in
`edge_verdicts.py`: **buy the bracket's YES side at the snapshot ask when `nbm_p − ask` clears the
Kalshi quadratic taker fee** (`0.07·p·(1−p)`); pnl = outcome − ask − fee. It rewrites the log file
in place (idempotent — only fills blanks; a second run found 0 new fills), so the *existing*
`kalshi-weather.yml` commit step ships the join automatically, no workflow edit needed.
`weather_clv_harness.py` now calls it (best-effort, non-fatal) after every snapshot append.

Also fixed a real bug in `edge_verdicts.py`'s weather loader found while wiring this up: it
compared `nbm_p` (a 0–1 probability) directly against `k_yes_ask` (logged in **cents**, 0–100)
without normalizing units, which made the buy-signal condition effectively never fire on real
data. Fixed by dividing `k_yes_ask` by 100 before comparing/fee-computing.

## Backlog run (now)

```
python weather_settle.py gha_data/weather/weather_clv_log.csv
python edge_verdicts.py score gha_data/weather/weather_clv_log.csv --kind weather
```

- 1,296 total snapshot rows → **1,200 settlement-joined** (16 events / 96 rows still open —
  8 cities × the 2 most recent target days, not yet finalized by Kalshi as of this run).
- Of the 1,200 settled rows, **523 rows fired the buy-signal** (`nbm_p − ask > fee`).
- Win rate on signal rows: **10.0%** (52/523) — i.e. the NBM-favored, cheaply-priced brackets that
  triggered the rule resolved YES far less often than the rule implicitly needs to break even.
- Mean paper P&L per signal-row contract: **-$0.021**.

### Verdict (pre-registered bar: ≥14 forward days, day-clustered t≥3, positive on ≥80% of days)

```
n_rows=523  n_forward_days=25  null=0.0
mean/day=-0.024  stdev/day=0.067  day-clustered t=-1.75  pct_days_positive=36.0%
VERDICT: FAIL   (t=-1.75, need >=3.0; %pos=36%, need >=80%)
```

**FAIL — not WAIT.** There is now enough forward, settlement-joined data (25 trading days ≥ the
14-day minimum) to score the strategy, and it fails outright: the day-clustered t-stat is
*negative* (-1.75, worse than the 0 null, let alone the +3 bar) and only 36% of days were net
positive. This directly falsifies the "recreational anchoring/warm-tail mispricing" hypothesis
from `KALSHI_WEATHER.md` as a tradeable BUY-the-NBM-edge rule at snapshot-time prices: NBM's
tail/edge brackets were priced too optimistically relative to what actually verified. Do not size
this strategy; the honest conclusion from 4 weeks of real Kalshi settlement data is that the
apparent Kalshi-vs-NBM deviation does not survive contact with outcomes.

## Caveats

- CLV here means snapshot-ask vs. final settlement, not a separate pre-settlement closing-book
  comparison (the harness never logged a distinct "closing" snapshot).
- 96 rows (16 events, most recent 2 days × 8 cities) are right-censored (not yet finalized by
  Kalshi at run time); re-running `weather_settle.py` on future collector runs will pick them up
  automatically. They are a small fraction (7.4%) of the backlog and unlikely to flip the verdict.
- The NWS-observations fallback path (used only if Kalshi hasn't finalized an event
  `--fallback-days` past target) was not exercised on this backlog — Kalshi finalized every
  eligible event within its normal window on this run.
