# CAPITAL ESCALATION PLAN — pre-registered 2026-07-13

Step-by-step scaling ladder for the Kalshi 15m BTC box maker. Pre-registered so no
step is decided under the influence of a hot streak. Amendments require an explicit
operator instruction BEFORE the gate they modify is reached.

## Principles
- Escalate only on REALIZED live evidence (not replay, not paper). Clock only counts
  days where the bot actually traded (>=20 windows quoted).
- Every step must pass ALL its gates. Any RED condition (below) overrides everything
  and de-escalates immediately.
- Sizing within a step is always the Kelly ladder size(B)=clamp(floor(0.02*B),1,30)
  once --post auto is deployed; steps control BANKROLL, not per-trade size.

## Ladder

| step | bankroll | entry gate (all required) | duration |
|---|---|---|---|
| 0 (now) | ~$100 | — (current size-2 experiment; Jul-19 eval per SIZE2_EVAL_PLAN.md) | until Jul-19 |
| 1 | keep ~$100 | Jul-19 eval passes its pre-registered rule | >=15 traded days |
| 2 | +$400 (→ ~$500) | 15+ traded days: realized edge >= +0.3c/box net; max daily drawdown never hit the loss-limit twice; strand rate < 4.3% break-even; no unexplained telemetry gaps | >=20 traded days |
| 2a | (same bankroll) VPS migration decision — resolved AT the step-2 gate (pre-registered 2026-07-13, operator-approved sequencing): deploy the $5-15/mo us-east-1 VPS iff step-2 entry passes. Measured economics (DECISION_MAP P3): coverage +13% windows (F7) + late-join class removal ≈ +$2-5/day at step-2 size vs ~$0.30/day cost; sniping value is NOT part of the case (F10 closed negative). Migration scope: keys move off GHA (hardening checklist required); middle path allowed (VPS runs data+trading loop, GHA keeps collectors). This is an operator sign-off item — the gate schedules the decision, does not auto-execute it | — |
| 3 | +$1,500 (→ ~$2k) | 20+ more traded days at step 2: cumulative live P&L positive; realized edge >= +0.3c/box at the LARGER ladder sizes (size 5-10); fill volume grew ~proportionally (capacity check — edge not collapsing with size); variance guard (below) never tripped RED | >=30 traded days |
| 4 | +$3k (→ ~$5k) | 30+ traded days at step 3 with the same conditions AND a dedicated capacity study at size 10-30 shows book absorbs ladder-max with <30% edge decay | open-ended |
| 5 | beyond $5k | operator decision only — also requires: repo privacy resolved (self-hosted runner), key-management hardening, and a second independent month of step-4 evidence | — |

## De-escalation (RED conditions — act same day, no discretion)
- Variance guard fires SEV-RED (see MONITORING below): halve bankroll exposure
  (withdraw to previous step) and freeze escalation clock until cause is understood
  and documented in FORWARD_LEDGER.md.
- Sticky loss-limit kill (KILLED_BY_LOSS_LIMIT) fires twice in any 10-day window:
  drop one full step.
- Realized edge over any trailing 20 traded days goes negative: drop to step 1,
  bot stays on at minimum size (data keeps accruing), full research review.
- Any evidence of execution anomaly (fills at prices inconsistent with the book,
  reconciliation mismatches): LIVE_SWITCH off, investigate before any re-entry.

## MONITORING — losses vs expected variance (the statistical guard)
Fixed dollar loss-limits catch catastrophes; this guard catches "losing more than
the strategy's own distribution says is plausible":
- Expected distribution: rolling 30-day empirical distribution of daily live P&L
  (from live-state winrec; while live history is thin, seeded with the replay
  distribution scaled to current size, clearly labeled as prior).
- SEV-AMBER: daily P&L below the 5th percentile of expected, OR 3-day cumulative
  below its 5th percentile → Telegram alert with the numbers; no automatic action;
  daily cycle must acknowledge it in the scoreboard.
- SEV-RED: daily P&L below the 1st percentile, OR 5 consecutive negative days when
  the expected P(5 straight negatives) < 5%, OR realized strand rate > 2x expected
  over 3 days → Telegram alert + de-escalation rule above + escalation clock freeze.
- Implementation: pnl_guard.py on the bot branch, invoked by health.yml every 30min
  (build in progress 2026-07-13). Thresholds are pre-registered here; changing them
  is an operator decision.

## Withdrawal policy (pre-registered to keep discipline symmetric)
At each step boundary upward, withdraw 20% of cumulative NET profits earned during
the completed step before adding the new capital. Profits are only real when they
leave the venue.
