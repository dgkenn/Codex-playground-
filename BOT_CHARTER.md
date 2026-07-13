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
