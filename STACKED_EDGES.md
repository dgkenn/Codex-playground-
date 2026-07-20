# STACKED_EDGES.md -- K-WX Central Multi-Sleeve Portfolio: build record + funnel graveyard

Build date: 2026-07-20. Author: orchestrator-builder subagent, economy mode (no orders, no
secrets, read-only public APIs only).

## 0. What this deliverable is

A **central portfolio manager** (`kwx_portfolio.py`) that orchestrates the sleeves that already
exist in this repo, independent of whether the concurrent research funnel (below) produced any
new tradeable idea. It ships regardless of funnel outcome, per the build instruction. As it
happens, the funnel produced **zero survivors** this round -- so there are no new
`wx_<name>_model.py` / `wx_<name>_paper.py` / `wx_<name>_decision.py` triples to add. The registry
and the `snapshot`/`status`/`correlate` commands are built so that a future survivor is a
one-entry registry addition, not a new orchestration script (see `kwx_portfolio.py`'s
`SURVIVOR_REGISTRY` dict and its docstring).

Files delivered (all in this directory, `scratchpad/stacked/final/`):

| File | What it is |
|---|---|
| `kwx_portfolio.py` | central manager: `status`, `snapshot`, `correlate`, `registry` commands |
| `kwx-portfolio.yml.proposed` | draft cron workflow for `kwx_portfolio.py snapshot` (NOT installed) |
| `STACKED_EDGES.md` | this file |

No `wx_<survivor>_*.py` files: the funnel enumerated below killed every spec before any cleared
the bar for a real paper harness. A null/insufficient result is treated as a fine, final answer
per house research discipline, not grounds to keep iterating past a pre-registered kill.

## 1. Funnel outcomes (full graveyard, including kills)

Two rounds ran concurrently with this build, in `scratchpad/stacked/{bt1,bt2,bt3,r2b1,r2b2}/`.
Every one of the five specs tested is **killed, refuted, or insufficient** -- zero survivors.

**Round 1** (initial three specs, `bt1`/`bt2`/`bt3`):

- **r1s1 -- Spec 1, broadcast-mention siblings (`bt1/`)**: CONFIRMED FAIL. n=265 settled/88
  triggered entries (validation only), win 97.7% (Wilson [92.1%, 99.4%]) but net EV/ct
  **-$0.0178** flat / **-$0.0420** day-clustered mean, fee-inclusive. Day-clustered t=-1.25 on 15
  days (one-sided p=0.884, need <0.0167 after Bonferroni m=3). The reactive-entry ceiling flagged
  pre-registration (fires only after book already at 0.90-0.99c) is confirmed, not just suspected:
  median win margin ~$0.01/ct, so one false lock (~-$0.95/ct) erases dozens of wins.
- **r1s2 -- Spec 2, KXJOBLESSCLAIMS AR(1)+4wk-MA nowcast (`bt2/`)**: CONFIRMED FAIL (underpowered
  pre-registered kill). Only 28 calendar weeks elapsed in the fixed 2026-01-01-to-present TEST
  window, and Kalshi's public market/candlestick endpoints serve price history for just 10 of
  those 28 (an apparent ~10-week retention wall on this deployment, confirmed via 3 independent
  request shapes) -- well under the pre-registered >=60-week minimum-n gate. Per protocol,
  underpowering is a kill, not a retry; the informational point estimate on the 10 accessible
  weeks is negative and worse-calibrated than the market anyway.
- **r1s3 -- Spec 3, cross-venue reprice race (`bt3/`)**: CONFIRMED FAIL/UNTESTED, strengthened by
  a cause the original worker missed. Kalshi's `trade-api/v2` appears to purge market/price
  history for finalized markets older than its retention window (events metadata survives,
  price/market objects do not) -- of the pre-registered macro-print universe, only ONE
  Kalshi-vs-Polymarket pair survives both the availability filter and a strike/expiry/resolution
  match (`KXFEDDECISION-26JUN` vs Polymarket's June Fed decision market), and that single pair
  shows both venues already priced the "hold" outcome at ~0.99/0.997 through the full
  +/-15-minute announcement window -- **zero triggered entries**, n=1, untested rather than
  falsified at scale.

**Round 2** (judge-selected re-specs, `r2b1`/`r2b2`):

- **r2s1 -- Spec (cross-venue lead-lag, crypto threshold markets, `r2b1/`)**: FAIL at
  preflight, self-kill per pre-registered step 1 (no TEST data read). Kalshi's BTC/ETH families
  trade $100-wide fixed-dollar strikes on hourly CF Benchmarks BRTI settlement; Polymarket's only
  matching families are either strike-less (open-vs-close relative-move bets) or $2,000-wide daily
  brackets on a single-exchange Binance close -- **zero reconcilable single-instrument pairs**
  (confirmed for both BTC and ETH). A prior verifier pass on an earlier round of this same spec
  had reported the opposite ("qualifying pairs exist, worker's FAIL refuted") -- this build's own
  fresh, independent re-check of live Kalshi + Polymarket market structure reproduces the FAIL,
  and is the verdict recorded here as current.
- **r2s2 -- Spec (macro-surprise pass-through drift into still-open KXFEDDECISION, `r2b2/`)**:
  PREFLIGHT PASS (the mechanism is real -- still-open future-meeting markets DO trade liquidly
  through scheduled macro-print windows, 10/10 tested jobless-claims releases clear the
  liquidity bar), but **N-GATE INSUFFICIENT**, killed before any TEST-period price data was
  touched. The frozen 2026-04-01 TEST-window start (pre-registered, not moved here) leaves only
  ~15.5 weeks of calendar to draw from; the repo's 5-family scheduled-macro-release universe
  produces ~31 TEST events against a pre-registered >=40-event/>=3-family bar. This is a genuine
  "insufficient," not a "fail" -- the underlying drift hypothesis was never tested, only its
  sample-size precondition.

**Net funnel result: `[]` (empty) survivor list.** Nothing from this round is registered as a new
paper sleeve. No goalposts were moved to manufacture a pass; every kill above is a pre-registered
gate the spec itself failed to clear, not a discretionary call.

## 2. Sleeve registry (what `kwx_portfolio.py` actually manages)

Full detail: `python kwx_portfolio.py registry` (reads `p4k_params.json`'s existing `sleeves`
block; upserts a `portfolio_registry` section into that file the first time it's run with
`--write`, additive-only, see the script's own docstring). Summary:

| sleeve | kind | gate state (as of 2026-07-20) | verified EV |
|---|---|---|---|
| `taker_mechanical` | live | no gate, always on | BACKTEST edge, MEASURED live infra; $10 canary on, 0 fires so far |
| `stacking` | live-config | no gate | VALIDATED, DEPLOYED |
| `station_derate_relax` | live-config | manual_config_deploy 2/1 (cleared) | +8% size-proxy uplift, DEPLOYED |
| `book_watch` | live-component | n_attributed_fires 0/30, accrual 0.0/day | MEASURED NULL -- modeled at $0 |
| `maker` | dormant | usable_rows_per_cell 0/30, accrual 0.04/day | REFUTED -- do not model |
| `depth_adaptive` | dormant | distinct_calendar_days 1/15, accrual 1.0/day | ASSUMED, IN-VALIDATION |
| `added_markets_polymarket` | dormant | not time-accruable | SPECULATIVE, excluded from all scenarios |
| `added_markets_kalshi` | dormant | not time-accruable | SPECULATIVE recon only (WX_EXPANSION.md), ~$20-60/mo defensible ceiling across 6 families, none backtested/paper-run |
| `early_lock` | **paper** (driven by `kwx_portfolio.py snapshot`) | n_settled_fires 0/30 (decision layer: `wx_earlylock_decision.py`) | Historical prior NULL (wx_earlylock_deep_study.md); forward gate ACCRUING, n=1 |
| `forecast` | **paper** (driven by `kwx_portfolio.py snapshot`) | no p4k sleeve entry, no decision gate authored | research-stage overlay, 59 settled rows logged, informational only |

Registered funnel-survivor sleeves: **0** (see Section 1). `SURVIVOR_REGISTRY` in
`kwx_portfolio.py` is an empty dict this round; its docstring shows the exact shape a future
survivor entry takes.

## 3. Combined realistic $/mo

From a real `python kwx_portfolio.py status` run against this repo (2026-07-20), which internally
re-derives `wx_path_to_4k.py`'s own Monte-Carlo model (same formulas, same `p4k_params.json`,
trimmed to a 3-scenario x 3-bankroll grid for speed) -- full run cross-checked directly against
`python wx_path_to_4k.py` itself (identical figures at the shared grid points):

| scenario | bankroll | median $/mo | % of $4,000 goal | notes |
|---|---|---|---|---|
| conservative (backtest rates, today, horizon=0) | $10,000 | $1,311-$1,323 | ~33% | ALREADY deployed live, no assumed-gate sleeve required |
| **conservative_live (tonight's OBSERVED fill rate, 0/39)** | $10,000 | **$148-$149** | **~3.7%** | the honest "right now" number -- 0 fills observed live to date, so `unfillable_frac` is forced to the live-observed rate instead of the 0.21 backtest assumption |
| base (30d horizon, depth_adaptive gate assumed cleared) | $10,000 | $838-$843 (marked `+`) | ~21% | depends on an ASSUMED sleeve gate (depth_adaptive) that has not cleared live |
| optimistic (90d horizon, every time-accruable gate on) | $50,000 | ~$1,044 (marked `+`) | ~26% | still does not clear $4k/mo at any tested bankroll |

**Honest combined-capacity math, survivors counted (do not count speculative sleeves):**
current validated capacity is the **conservative_live** figure, ~$148-149/mo at $10,000
bankroll (~3.7% of the $4,000/mo goal) -- this is what's actually proven today, on real fills,
with zero assumed accrual rates. The backtest-rate "conservative" figure (~$1,320/mo, ~33% of
goal) is the deployed-lever ceiling IF live fills eventually match the backtest fill-rate
assumption, which has not yet been observed (0/39 near-misses converted). Adding the two
research-stage paper sleeves (`early_lock`, `forecast`) contributes **$0 additional** to this
figure -- both are pre-decision-gate (n=1 and n=59 settled respectively, neither cleared its
activation bar), and per house rules a sleeve only counts once it has actually passed its gate,
not while merely "in progress." Funnel survivors from Section 1 contribute **$0 additional**
because there are none. Nothing speculative (`added_markets_*`, `depth_adaptive`, `maker`,
`book_watch`) is included in this headline number, matching `p4k_params.json`'s own convention.

**Bottom line: $4,000/month is not reached by this build.** The honest, all-gates-respected
number today is ~$148-149/mo (3.7% of goal); the best-case fully-realized backtest-lever ceiling
already deployed is ~$1,320/mo (33% of goal); no combination of currently-registered sleeves,
including every paper sleeve this manager can run, gets closer than that without either (a) live
fills actually starting to match the backtest fill-rate assumption, or (b) `depth_adaptive` and/or
`added_markets_polymarket` clearing their own (not-yet-time-accruable, in one case) gates -- both
already true and already documented in `wx_path_to_4k.py`'s own "honest bottom line" output, not a
new finding of this build.

## 4. Orchestrator design (`kwx_portfolio.py`)

- **`status`**: prints the sleeve registry (kind/gate/status), each paper sleeve's own decision
  verdict (via its `wx_<name>_decision.py` where one exists), the combined realistic $/mo table
  above, and the bankroll-rung authorization table (delegated to
  `wx_path_to_4k.bankroll_rung_status`). Read-only.
- **`snapshot`**: for every registered `kind="paper"` sleeve, calls that sleeve's OWN
  `snapshot(verbose=False)` function exactly as running the module's CLI would -- no new order
  path, no new network surface. Wrapped per-sleeve in try/except so one broken sleeve (e.g. a
  transient feed timeout) never blocks the others. Maintains a **shared nominal paper bankroll**
  ($500, informational -- these forward loggers record one hypothetical contract per signal, they
  do not size positions) with a **combined per-day cap** across all paper sleeves derived from the
  live sleeve's own `sizing.max_daily_deploy_frac` convention, and performs **per-market dedupe**
  against the live bot's plan log (`kwx_runner_plan.jsonl`) -- any ticker a paper sleeve logs today
  that the live bot also fired today is flagged (not silently dropped; the underlying jsonl files
  are append-only and untouched by this script). Persists its own ledger to
  `kwx_portfolio_state.json` (resets daily), separate from every live-path state file.
- **`correlate`**: pairwise same-day and same-ticker overlap across `early_lock`, `forecast`,
  `kwx_near_miss.jsonl`, and the live plan log -- flags whether two "independent" paper sleeves are
  actually firing on the same days/instruments, which would mean their drawdowns should be modeled
  jointly rather than summed, before either is ever sized for real capital.
- **`registry`**: prints the resolved registry; `--write` additively upserts a
  `portfolio_registry` section into `p4k_params.json` (idempotent -- never overwrites an existing
  section, one-time `.kwxportfolio.bak` backup before the first write).

**Off-limits respected:** `kwx_portfolio.py` never imports `kalshi_exec`, never sets `KWX_LIVE`,
never writes to `kwx_runner_state.json` / `kwx_gate_status.txt` / `kwx_runner_plan.jsonl` /
`.kwx_halt`, and never modifies `kwx_runner.py`, `kwx_paper_gate.py`, or `kalshi_exec.py`. Its only
write side effect against the checked-in repo is the additive `portfolio_registry` upsert
described above.

## 5. Operator activation checklist

1. Read this file + `python kwx_portfolio.py status` before doing anything else -- confirms the
   registry matches the live repo state (sleeve gates move over time; this doc is a point-in-time
   snapshot, the script's `status` output is the live source of truth).
2. Run `python kwx_portfolio.py registry --write` once, from a checkout where you're comfortable
   with an additive JSON write to `p4k_params.json` (a `.kwxportfolio.bak` is made automatically).
   Skip if you'd rather keep the registry purely code-side for now -- `status`/`snapshot` work
   identically either way (registry falls back to the built-in default when the file section is
   absent).
3. Install `kwx-portfolio.yml.proposed` as a real workflow ONLY after reading its header --
   it is a draft, not wired into CI by this build. Pick a cron cadence that respects the
   forward-loggers' own polite-fetch conventions (they already rate-limit/backoff against Kalshi +
   IEM + Open-Meteo; do not also run multiple overlapping crons against the same feeds).
4. Before trusting any `snapshot` cycle's dedupe/cap output for a real decision, cross-check
   `kwx_portfolio_state.json` against `kwx_runner_plan.jsonl` by hand at least once -- the dedupe
   logic conservatively treats any row with an unparseable timestamp as "today" (never
   under-flags), which can occasionally over-flag; false positives are safe (informational only),
   false negatives would not be.
5. Do not act on `early_lock` or `forecast` as tradeable sleeves until their own decision layer
   says so (`ACTIVATE-PAPER` from `wx_earlylock_decision.py`; `forecast` has no decision layer yet
   -- authoring one, mirroring `wx_earlylock_decision.py`'s conservative-bar pattern, is the
   natural next step if its accrual keeps looking promising, but that is future work, not part of
   this build).
6. When (if) a future funnel round produces a survivor, add it to `kwx_portfolio.py`'s
   `SURVIVOR_REGISTRY` dict (one entry: kind="paper", cycle/settle module refs, decision_module)
   and build its `wx_<name>_model.py` + `wx_<name>_paper.py` + `wx_<name>_decision.py` triple in
   the style of `wx_earlylock_forward.py` / `wx_earlylock_decision.py`. No other orchestration
   code needs to change -- `snapshot`/`status`/`correlate` all iterate the registry generically.

## 6. Verification this build actually ran

- `python kwx_portfolio.py registry` -- printed the full registry (built-in default; no repo
  `portfolio_registry` section existed yet).
- `python kwx_portfolio.py correlate` -- ran against real repo logs, printed non-trivial overlap
  (e.g. `forecast` x `near_miss`: 1 shared day, 6 shared tickers on 2026-07-19).
- `python kwx_portfolio.py status` -- ran against the real repo, printed the sleeve table, both
  paper sleeves' accrual + decision verdicts (`early_lock`: ACCRUING, n=1; `forecast`: no gate
  authored), the combined $/mo table above (cross-checked against a full, separate
  `python wx_path_to_4k.py` run -- shared grid points matched), and the bankroll-rung table.
- `python kwx_portfolio.py snapshot` -- ran fail-soft against the real repo's live feeds; see
  build session output for the actual per-sleeve result (new rows logged / notional / any
  collisions with the live plan log, which was empty -- 0 live fires to date).
- `python kwx_selftest.py` (repo root, untouched by this build) -- still passes; verified after
  this build's files were added, confirming no interference with the live plumbing test.
