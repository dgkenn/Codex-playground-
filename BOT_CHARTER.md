# BOT CHARTER — autonomous improvement loop (v1, 2026-07-13)

This file governs the daily autonomous improvement cycle for the Kalshi 15m BTC box
maker. The cycle runs in a FRESH session each day: read this charter first, then
DECISION_MAP.md and PAIRING_FINDINGS.md (same branch) for current state.

## North star
Maximize REALIZED risk-adjusted EV (day-clustered stats on forward data). AUC,
strand-rate, fill-rate etc. are diagnostics, never objectives. When a proxy and the
terminal metric disagree, the terminal metric wins (lesson: the 0.75-AUC hunt — the
money was in disposal policy at unchanged AUC).

## Hard rails (never violate)
1. NEVER edit .github/workflows/live.yml, LIVE_SWITCH, loss limits, or any live
   sizing flag autonomously. Live changes are PROPOSE-ONLY: prepare the diff on a
   branch, notify the operator, stop.
2. Promotion gate for calling anything "deploy-ready": day-clustered t >= 2 on
   held-out FORWARD data (>= 10 forward days), tested on the gate-passed subset,
   with the selection made on earlier data (train-select/test-validate). In-sample
   discoveries are hypotheses, not results.
2b. THE GATE APPLIES TO FIXES TOO (operator directive 2026-07-13). A "fix" with a
   compelling mechanism story is still a hypothesis until data-backed: mechanism +
   asymmetry arguments alone do NOT authorize deployment (case study: the late-join
   k-cap fix, node N — recommended on 2 live events + n=30 corpus, correctly
   withdrawn pending validation). When the relevant population is ABSENT from the
   corpus (live-architecture effects the replays never simulated), MANUFACTURE it:
   re-run the replay with the architectural condition imposed (e.g., delayed quote
   starts for leg-joins) and validate against the standard gates. Exceptions: only
   reverting to a previously-validated config, or stopping trading entirely, may
   proceed on operator word alone — de-risking never needs a study; re-risking
   always does.
3. Token budget per daily cycle: ~100k. Prefer local python over subagents; one
   focused question per cycle beats broad sweeps (the dataset only grows ~1 day/cycle).
4. Do not create new external accounts/services. Public read-only APIs are fine
   (Kalshi, data.binance.vision, Deribit public).
5. All findings committed to the working branch same cycle — session memory dies,
   git survives. Update DECISION_MAP.md verdicts in place; append, don't rewrite
   history.

## Free actions (no approval needed)
Research studies, shadow/paper A/B arm changes, dataset builds, doc updates,
prototype code behind flags in worktrees (never pushed to main), data-collection
fixes on collector workflows (not live.yml).

## Arm & experiment lifecycle (self-pruning + replacement — run inside daily step 3)
The paper layer must stay ultra-rich but self-cleaning. Applies to: quoting arms
(strategies.py REGISTRY, the single source of truth — prune by setting enabled=False
with a dated note, never delete code), box arms (ARMS list in box_shadow.py on the
bot branch), and whole paper-track workflows (crons on main).
- RETIRE when: day-clustered t < -2 vs baseline/live over >= 10 days under the arm's
  CURRENT definition; or byte-identical duplicate of baseline for >= 10 days.
- PROTECTED (never retire): baseline, as_markout (live twin), micro_gate
  (legacy-contrast anchor), av_stoikov + mo_size (month-validated winners),
  box_shadow 'live' arm.
- REPLACE on retirement: promote the next candidate from the BACKLOG below into the
  vacated slot the same day (keeps the roster rich). Pre-registered backlog, in order:
  (1) C3 completing-side depth-share veto, MILD variant share>0.9 (replay prior:
      +1.42c t=5.15 marginal beyond thickbook; see DECISION_MAP K — beware the
      large-skip accounting artifact, forward arm is the only valid sizing);
  (2) F2 adaptive quoted edge (vol-scaled); (3) F8 maker-out disposal (rest improve
  order 5-10s before crossing); (4) hazard_stop kappa=-0.25 variant; (5) thickbook
  q90 variant; (6) A wide-spread veto >=3c variant; (7) C4 alt-skip on BTC vol
  top-decile (multi-asset only, t=6.8). NOTE: the daily cycle may also ADD backlog
  arms to box_shadow without waiting for a retirement when the roster has headroom
  (<10 arms). Every addition needs a one-line replay prior. NOTHING skips forward
  validation regardless of in-sample t-stat (see DECISION_MAP K artifact).
- WORKFLOW-level: a paper-track workflow whose every tracked metric is dead by the
  same 10-day rule gets its cron commented out (main), file kept. Overlap watch:
  boxwide-paper's P300 disposal track vs box_shadow arms — consolidate after both
  have 10 days.
- Every retire/replace action: log in FORWARD_LEDGER.md with the stats that
  justified it.

## Daily cycle (in order, stop when budget spent)
1. HEALTH: fetch bot branch + live-state. Check LIVE_SWITCH, kill sentinel,
   telemetry freshness, balance trend. Alert operator on anomaly; else silent.
2. INGEST: pull the new day of gha_data (bot branch) + live_state. Append to the
   forward-validation ledger (FORWARD_LEDGER.md, create if absent): per-arm
   net/window for the day, live realized EV, strand rate — AND the RISK BENCHMARK
   TABLE from box_shadow_report.py (bot branch): per-arm variance, CVaR5, worst
   window/day, day-Sharpe, max drawdown, day-clustered deltas vs the live arm.
   Risk reduction is a first-class promotion criterion alongside EV (operator
   directive 2026-07-13): an arm may promote on significant risk reduction at
   EV-neutral, same t>=2 bar on the risk metric.
3. VALIDATE: update day-clustered stats for every OPEN item in DECISION_MAP.md's
   deploy queue and the shadow A/B arms. Items reaching the promotion gate:
   mark PROMOTED in the map, prepare the deploy diff, notify operator.
   Items going statistically dead (t < 0 after 10+ forward days): mark dead.
4. ONE research question: the highest-value ❓ node in DECISION_MAP.md that the
   new data can move. Test with the honest protocol. Fold the verdict in.
5. COMMIT + push everything to branch claude/coding-bot-ab-test-results-ffmhxw.
   Final message = a 5-line scoreboard: live P&L yesterday, top arm deltas,
   promotions/deaths, tomorrow's question.

## FACTORY V2 — roadmap to a best-in-class research factory
Upgrades ranked by lesson-learned leverage; daily cycles implement one at a time
(as the step-4 research slot when no data-driven question is more urgent):
1. STUDY PROTOCOL TEMPLATE (from the G7/G8 overfit deaths): every study runs
   train-select/test-validate with day-clustered stats, pre-named metrics, and a
   pre-stated kill criterion — TEMPLATE.md checked into the repo; agent prompts
   reference it instead of restating it.
2. REPLICATION GATE (from the J-section sensitivity, t=2.36→1.07 on re-impl):
   any result feeding a live deploy must be reproduced by an independent
   implementation before promotion. Two matching numbers or it isn't real.
3. POWER CHECK before launching any study: compute minimum days/events needed to
   detect the hypothesized effect at t>=2; if the data can't support a verdict,
   don't run it (saves tokens and prevents false negatives).
4. VERDICT REGISTRY: DECISION_MAP.md is the single source of truth. Formal states:
   ❓ open → 🟡 replay-supported → forward-testing → ✅ promoted / ❌ dead.
   Dead stays recorded forever (negative results are assets).
5. FACTORY META-METRICS in FORWARD_LEDGER.md monthly: time-to-verdict, kill rate,
   false-promotion rate (promoted then de-promoted), token cost per verdict.
   The factory improves what it measures about itself.
6. AGENT EXECUTION STANDARD (from the early-return/timeout failures): no timeout
   wrappers, OMP_NUM_THREADS=2, final message must contain the numbers, fixture
   validation before any push. Bake into every research-agent prompt.
7. CROSS-SLEEVE GENERALIZATION: run the other paper tracks (weather/sports/etf/
   macro/wti CLV) through the same gates + ledger, so capital allocation across
   sleeves becomes an output of the factory, not a vibe.

## Standing context (2026-07-13)
- Live: BTC-only, size-2 experiment since 07-12; pre-registered evaluation
  2026-07-19 per SIZE2_EVAL_PLAN.md (balance>=100 & edge within 30% of anchor &
  strand<2.7% => keep, else revert). Only 4 days of live history exist — forward
  validation runs mostly on shadow arms.
- Deploy queue (10 levers, replay-validated, awaiting forward validation): see
  DECISION_MAP.md "DEPLOY QUEUE". Highest value: hazard-based state-dependent
  disposal (+1.11c/box gate-passed, t=2.64 in replay).
- Priority implementation tasks: STACK arms DONE (161cd2e73); P1 ws collector
  DONE 2026-07-13 (4ea3714a3, hires files confirmed landing on gha-data).
- RESEARCH QUEUE (ranked 2026-07-13 evening, operator-requested; daily cycle
  step 4 works these in order unless fresher data demands otherwise):
  1. ETH tailored wide-quote strategy (F1b): replay box engine on ETH tapes with
     seed-width 2-3c variants; measure width-capture vs fill-rate elasticity +
     tradeable depth/window. Doubles-the-bot candidate; answers F2 as a side
     effect. ETH forward sleeve already accruing via box-shadow.yml.
  2. FILL-MODEL CALIBRATION vs live tape: fit replay fill model to
     order_lifecycle (every resting quote) x fills (which filled) x book context.
     Collapses opt/pess uncertainty; upgrades ALL future replays to absolute EV.
  3. Hires re-tests (~2026-07-18, needs ~5 days ws data): C1 at-fill ceiling,
     L1.5 pre-fill lead, F10 sub-2.4s pool, hazard-model sub-second features.
  4. C3 depth-share veto -> box_shadow arm (backlog top, +1.42c t=5.15 prior).
  5. Cross-venue Kalshi<->Polymarket box persistence (pmkt_btc_updown feed
     already collected) — new pool, real engineering lift, after 1-3.
  DO-NOT-STUDY (closed honestly, stop re-litigating): window selection
  (calendar/hours/cells), BTC box-count levers (F4/F4b/F4c/F4d/F-size),
  disposal micro-optimization (L3 within ~1c of floor), width-gated pairing
  (F11), stale-quote sniping at >=2.4s (F10).
- Data locations: market/shadow data = gha_data/ on branch
  claude/polymarket-bot-live-ready-vw7ut5 (sparse-checkout it; multi-GB);
  live telemetry = live_state/ on branch live-state; studies' methodology =
  PAIRING_FINDINGS.md + DECISION_MAP.md on the working branch.
- Edge is stationary at month scale (no decay over 33 days) — weekly model refits
  suffice; don't churn.
