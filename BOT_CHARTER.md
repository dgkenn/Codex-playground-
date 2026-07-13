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
  (1) F2 adaptive quoted edge (vol-scaled); (2) F8 maker-out disposal (rest improve
  order 5-10s before crossing); (3) hazard_stop kappa=-0.25 variant; (4) thickbook
  q90 variant; (5) A wide-spread veto >=3c variant. Add new candidates to this list
  as research produces them; every addition needs a one-line replay prior.
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
   net/window for the day, live realized EV, strand rate.
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
- Priority implementation task (free action): add the four decision-layer arms to
  shadow_compare.py (hazard_stop, cell_veto, thickbook_veto, givecap15 + combined)
  and prune the 17 dead arms (list in DECISION_MAP.md). Until these arms run
  forward, the deploy queue cannot clear the promotion gate.
- Data locations: market/shadow data = gha_data/ on branch
  claude/polymarket-bot-live-ready-vw7ut5 (sparse-checkout it; multi-GB);
  live telemetry = live_state/ on branch live-state; studies' methodology =
  PAIRING_FINDINGS.md + DECISION_MAP.md on the working branch.
- Edge is stationary at month scale (no decay over 33 days) — weekly model refits
  suffice; don't churn.
