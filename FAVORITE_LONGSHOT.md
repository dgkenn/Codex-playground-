# Favorite-Longshot Bias — DEPLOYABLE: NO

**Bottom line: the favorite-longshot bias is real in Kalshi's raw settlement calibration, but it
does not survive contact with a fillable entry price. All three pre-registered specs fail. Honest
capacity is $0/mo to −$60/mo (a loser) across every version tested. No sleeve is being shipped.**
This is the pattern that has killed almost every other "obvious" bias in this repo (see
`RESEARCH_LEDGER.md` graveyard): real at `last_price`, gone at the crossing price.

---

## 1. The scan (motivating signal, NOT a backtest)

An inline scan over **2.97M settled Kalshi markets** (volume ≥ 20, `result` truth from settlement)
found the textbook favorite-longshot shape in raw calibration: `last_price` vs realized outcome
frequency.

| YES price bin | Realized YES rate | Bias | Interpretation |
|---|---|---|---|
| 25–40c | 25.7% realized vs 31.0c priced | longshot **over**priced | NO is underpriced → fade signal |
| 40–60c | 41.2% realized vs 47.2c priced | longshot **over**priced | NO is underpriced → fade signal |
| 75–85c | 83.6% realized vs 79.4c priced | favorite **under**priced | YES is underpriced → buy signal |

Net of the Kalshi taker fee `ceil(7·p·(1−p))/100`, the naive per-category edge (at `last_price`,
no crossing) was: sports +3.7c, "other" +2.8c, fx/index +6.5c, **crypto +13.3c** (flagged
immediately as tail-risk-shaped — far-OTM strikes). **Weather was the control: −1.5c, i.e. no
edge**, consistent with this repo's separately-established finding that Kalshi weather markets are
well-calibrated at near-certainty (`DATA_BACKED_BACKTESTS.md`, item 19 in the graveyard). That
weather-null result is a validity check on the scan methodology, not a new finding — the scan
correctly reproduces a known-null category and a known-live-edge category (taker_mechanical) is
the read on the general shape being real at the raw-calibration level. **The open question was
always deployability, not existence** — per house rules, that requires a realistic fillable entry
price, tail-risk accounting, and persistence, not a `last_price` comparison.

## 2. Pre-registration (Fable, judge)

Three specs were pre-registered *before* any crossing-price backtest was run, each with an exact
universe, entry rule, fit/validation split, and pass bar:

1. **Spec 1 — broad longshot fade** (buy NO on signal-YES price in the low-price band), ex-crypto
   ex-weather (sports + other + fx_index), realistic crossing-price entry, day/event-clustered
   stats, validation window 2025-01-01 → 2026-01-31.
2. **Spec 2 — favorite buy** (buy YES on signal-VWAP price in [70c, 90c)), ex-crypto ex-weather,
   same entry/clustering/validation methodology.
3. **Spec 3 — crypto isolation** (buy NO on signal-YES price in [5c, 45c)), crypto only — the
   raw scan's largest edge but flagged tail-risk-shaped going in.

Common pass bar: net EV/contract must clear the fee **at the realistic crossing price** (not
`last_price`), day/event-clustered t ≥ 3, acceptable drawdown/ruin, and a real (non-degenerate)
capacity estimate. All three specs were executed on real data via `kx_history.py`
(DuckDB/parquet trade-tape archive, ~172M trades) with an authoritative-API settlement spot-check,
then adversarially re-verified by a second (Fable) pass per `.claude/skills/kwx-study-audit/`.

## 3. Results

### Spec 1 — broad longshot fade (sports + other + fx_index): FAIL, deployable NO

n=2,958 fillable contracts / 2,189 distinct events / 256 distinct days.

- Mean EV/contract at the **realistic crossing price**: **−3.41c** (median +21.0c, p5 −79.0c,
  p95 +39.0c, win rate 69.3% — a classic small-win/occasional-big-loss NO-buying shape).
- Day-clustered t = **−4.87** (se 0.70c, 256 clusters); event-clustered t = **−3.82** (se 0.89c,
  2,189 clusters). Governing (wider) SE gives 95% CI **[−5.16c, −1.66c]** — confidently negative,
  not just "not significantly positive."
- **This is exactly the entry-realism kill risk the house rules flagged**: raw signal edge at the
  naive fill was only **+1.70c**, but crossing the spread to a genuinely fillable NO price cost
  **3.18c** of slippage — the same "spread eats the edge" death mode that killed the long-tail
  passive-spread study (`DATA_BACKED_BACKTESTS.md`). Net after fee: −3.41c.
- Every category negative individually: fx_index −5.39c (n=33), other −3.87c (n=480), sports
  −3.30c (n=2,445). No category clears the bar; `cat_pos_ok=False` for all three.
- Persistence check (mid-split 2025-08-08): first half −5.20c (n=357), second half −3.17c
  (n=2,601) — negative in both halves, i.e. persistently negative, not persistently positive.
- Tail risk ($4,000 start, $10/market, 20 concurrent cap): ends at $3,220 (−19.5%), max drawdown
  20.6%, worst day −$70, 1,000-resample day-block bootstrap ruin proxy (<50% bankroll) = 0.10%
  (small, but moot given the point estimate is negative).
- Honest capacity at realistic fillable rate (60.8% of signal-band markets are fillable,
  ~228 signal markets/mo, concurrency-capped to 126 trades/mo): **−$60/mo** — i.e. this loses
  money, it doesn't just fail to make money.
- Spot-check: 20 randomly sampled fillable tickers cross-checked parquet trade counts against
  Kalshi's authoritative `/historical/trades` API — 13/20 exact match, 6/20 parquet showed *more*
  trades (consistent with the API fetch script's own page cap, not a parquet shortfall), 1/20 off
  by 0.8% (plausible archive-freeze-boundary clipping). No sign of data fabrication.

**Gate checks: min_n ✓, cat_n ✗, cat_pos ✗, ev_bar ✗, ruin ✓, drawdown ✓, persistence ✗,
spread-death-mode triggered = TRUE.**

### Spec 2 — favorite buy (buy YES on underpriced 70–90c band): FAIL, deployable NO (execution-limited)

This spec's candidate universe was built cleanly (383,553 candidate markets, ex-crypto ex-weather,
close_time in [2025-01-01, 2026-02-01), lifespan ≥ 48h, volume ≥ 20 — see `bt2/candidates.parquet`
and `bt2/category_map.json`), but the trade-tape join (candidates × 9 trade shards, ~172M trades,
computing T24/T6/T1 fillable-price windows in one pass) **did not complete inside the
economy-mode compute budget** — confirmed by re-running it directly in this session: it still
times out (170s+, no output) against the live DuckDB/parquet backend. `joined.parquet` is 0 bytes;
no `results.json`/`stage1_results.json` was produced by either the original backtest agent or this
rerun.

This is an **infrastructure/capacity limit, not a measured negative result** — unlike Spec 1 and
Spec 3, there is no P&L number to report for Spec 2, positive or negative. Per the adversarial
verification pass, absence of a completed, verified backtest means **deployable = NO by default**
(a claim that can't be checked can't be shipped), and capacity is scored at **$0/mo** pending a
successful re-run — not because the edge is proven negative, but because it is unproven. The
methodology to re-attempt this (narrower candidate window, pre-filter by series before the join,
or run the join as a background job with a multi-hour budget rather than an interactive one) is
preserved in `bt2/05_join_trades.py`; this is flagged here rather than silently dropped so a future
session doesn't have to rediscover the failure mode.

### Spec 3 — crypto isolation (buy NO on 5–45c crypto longshots): FAIL, deployable NO

n=118 fillable contracts (T24 primary) / 40 distinct events / 33 distinct days — **decisively
short of the pre-registered floor (≥200 events, ≥60 days)**. The entire crypto market population
meeting the spec's own 48h-lifespan requirement is only 84 distinct events in the validation
window — a hard structural ceiling (Kalshi's crypto verticals are almost entirely
intraday/hourly brackets), not a tunable filter. Per the no-goalpost-moving rule this alone is a
kill: no post-hoc band or window change was applied.

- Even setting the sample-size failure aside, the point estimate is **negative**: mean
  **−4.17c/contract**, day-clustered t = −0.64, 95% CI [−17.4c, +9.0c] (crosses zero) — not the
  required ≥+2.0c with a CI lower bound above zero.
- **Entirely one bad day**: −$58.56 of the −$72.24 total P&L happened on 2026-01-02; excluding
  that single day, the remaining 110 contracts net to **exactly $0.00/contract** — what's left
  after the worst day isn't a hidden positive edge, it's a coin flip, consistent with this being a
  small-sample artifact rather than a real "vol premium killed by tail risk" story.
- "Crypto isolation" is de facto **BTC/ETH isolation** — DOGE/SOL/XRP/SHIBA contributed zero
  fillable T24 observations; not folded into this null by association, flagged as separately
  untested.
- T1 sensitivity (1h pre-close) is nominally significant (+5.00c, t=3.77) but per pre-registration
  is sensitivity-only, and sits exactly in the near-settlement information-collapse zone the house
  rules flag as untradeable — the same death mode as the killed long-tail-spread study. Not usable
  as a capacity claim.
- Tail/ruin metrics pass (max drawdown 2.2%, bootstrap ruin proxy 0.0%) but are moot — there is no
  positive edge to protect.
- Settlement `result` truth spot-checked 20/20 exact match against the authoritative
  `/historical/markets/{ticker}` API (trade tape itself was pulled from the authoritative
  `/historical/trades` API directly, because full-shard parquet-archive scans stalled on this
  network for this spec — documented in `bt3/results.md`).
- Honest capacity: ~9 fillable contracts/mo, ~3 tradeable events/mo, at a negative point estimate
  — **effectively $0/mo deployable**, no bankroll or sizing scheme turns this into real capacity.

## 4. Fable adversarial verdicts (final)

| Spec | Verdict | Deployable | Capacity | Governing reason |
|---|---|---|---|---|
| 1 — broad longshot fade | CONFIRMED (FAIL) | NO | **−$60/mo** | Crossing-price slippage (3.18c) exceeds the naive signal edge (1.70c); negative in every category and both persistence halves |
| 2 — favorite buy | CONFIRMED (FAIL) | NO | **$0/mo** | Trade-tape join did not complete in budget; no verifiable P&L exists to certify |
| 3 — crypto isolation | CONFIRMED (FAIL) | NO | **$0/mo** | Structurally underpowered (40 events vs 200 floor, hard population ceiling of 84); point estimate itself negative and driven by one day |

**No survivor.** All three kill risks the house rules required this backtest to resolve were
addressed: (a) entry realism — resolved, and it's the thing that killed Spec 1; (b) tail
risk — resolved (drawdown/ruin/full pnl distributions reported for every completed spec, all
passing but moot given negative point estimates); (c) look-ahead — entries use only pre-entry
trade-tape/volume information (`pre_vol` guard), no settlement leakage into signal construction.

## 5. Disposition

Per the house build-gate: **since no spec is deployable, no paper sleeve, model, or decision-gate
script is being built.** `wx_favlong_model.py` / `wx_favlong_paper.py` / `wx_favlong_decision.py`
are explicitly not shipped — building a live/paper sleeve around a −$60/mo or unverified $0/mo
result would violate the repo's own "don't ship a null as a lever" convention (see `book_watch`,
`early_lock`, `maker`, `forecast` in `p4k_params.json`, all marked `DO NOT MODEL AS A LEVER`).
This study is logged in `RESEARCH_LEDGER.md` §3 (the graveyard) as a new, confirmed-killed
strategy — **not** promoted to LIVE CANDIDATE. The Spec 2 execution gap is flagged as a genuinely
open item (infra limit, not a disproof) in case a future session has budget for a longer-running
join.

## 6. Reproduction

All backtest code, intermediate parquet files, and machine-readable results are preserved (not
committed — repo convention keeps large intermediates out of git; see `.claude/skills/kwx-study-audit/`
for the checklist this followed):

- Spec 1: `scratchpad/flb/bt1/` (`backtest_spec1.py`, `pnl_analysis.py`, `results.json`,
  `results.md`, `spotcheck_note.md`)
- Spec 2: `scratchpad/flb/bt2/` (`01_census.py` … `08_spotcheck.py`, `candidates.parquet`,
  `category_map.json` — join stage unfinished, see §3)
- Spec 3: `scratchpad/flb/bt3/` (`01_build_candidates.py` … `06_assemble_final.py`,
  `results.json`, `results.md`)
