# Preventing bad trades — the honest stack (research anchor, 2026-06-13)

The recurring "bad trades" are **not** a completion/lock bug. RCA of 30 live windows + a 323-window
backtest established the root cause and refuted the obvious fix.

## Root cause: STRAND SETTLEMENT RISK (not negative locks)
- Strands (one leg fills, the other doesn't) are the entire loss engine: **−4,413¢ from strands vs
  +1,757¢ from same-minute boxes** on the 323-window tape.
- A stranded leg held to settlement loses its full directional value (−40 to −90¢ when it settles
  against you). The market move that strands a leg also **predicts adverse settlement**.

## What does NOT work (tested, refuted — do not relitigate)
- **Positive-lock floor / refusing ≥$1 completions:** HURTS. For negative-lock events, *complete*
  = −1.07¢ vs *hold-to-settle* = −6.84¢; completing wins 74% (29/39). The locked loss is a ceiling;
  holding removes it. Negative locks are only ~0.8% of the loss. **Current `--chase-max-give 0.02`
  is optimal — leave it.** (POSITIVE_LOCK_FLOOR.md)
- **k∈{4,5} "eliminates strands":** sample-specific; does NOT replicate forward (OOS Sharpe −0.09,
  skew −3.07). (K_WINDOW_ALTERNATIVES.md, SELECTION_DECONSTRUCTION.md)
- **Stop-loss exits on boxes:** lose (20,318-fill test). Risk control is SIZE/pairing, never exits.

## What DOES prevent / mitigate (ranked)
1. **Avoid opening the strand-prone leg (entry selection)** — the ONLY lever that cuts the loss at
   its source. t36 guarded-opener is armed; forward-validating candidates: `f5_fav_lowsig_complete`
   (favorite + quiet-spot, +skew, CVaR 22× safer), the k=8 family, `t32_vpin_open_gate`. None has
   cleared the deploy bar (t>3, n≥300 vs live) yet.
2. **Decision-time telemetry (`sig`/microprice/guard) per fill** — shipped (Prevention #0). We can
   now learn *which* opens strand and build sharper entry gates. The enabler for #1.
3. **Complete promptly when stranded** — already the deployed behavior; backtest-confirmed least-bad.
4. **Hedge the residual strand** — best in backtest (tc_mid_hedge +2.77¢ vs live) but the trader has
   NO BTC-perp venue; `tc_mid_hedge_h150` shadow-tests whether the edge justifies building one.

## The open research question (future work)
**Can decision-time signals (now that `sig`/microprice/book-imbalance are recorded) predict and gate
out strand-prone opens, cutting strand-settlement loss without killing box volume — and is a hedge
venue worth building for the residual?** Everything below (RESEARCH_LOOP.md) iterates on this.

## Invariants for this line of research
- Judge candidates vs the durable `live_current`, not P0 (avoid double-counting deployed gates).
- Forward bar governs deploy (t>3, n≥300); backtests SCREEN only (the t02 mirage stands as warning).
- Watch the full risk metric set (skew/CVaR/Ulcer), not just t-stat (high-t can hide tail risk).

---
# 5-ROUND RESEARCH PROGRAM — CONCLUSION (2026-06-13, RESEARCH_LOOP.md, ~25 experiments)

**The hard-won answer to "how do we prevent the bad trades": you largely CAN'T prevent the residual
strands with a predictive gate — and we now have strong evidence for that, not a hunch.**

1. **No causal fill-level signal beats live (t36) at adequate n.** Tested across 5 rounds: linear
   logit (AUC 0.56), GBM/RF ensemble (AUC 0.72 but a SELECTION effect, n<300), sig×spread conjunctive,
   time-of-day, directional YES/NO, microprice-divergence, queue-thinness, vol-regime, settle-magnitude
   regressor, early-window causal flow. Every apparent winner was a **look-ahead** (full-window
   flow_ratio t=4.05 — aggregates the late momentum that determines settlement), an **oracle**
   (reactive hedge needs to know the strand before settlement), or a **selection/risk-control**
   artifact (gate skips bad windows; t_paired≈0). The residual strands AFTER t36 are genuinely
   unpredictable from decision-time data.
2. **t36 is the validated frontier.** It already cut OOS strand 13.6%→3.36% (+5.30c/win OOS); the
   research confirmed its mechanism (YES-strand prevention) and that nothing layers on top causally.
3. **The one deployable near-term remedy is RISK CONTROL, not prevention.** Strands are
   AUTOCORRELATED (lag-1 = 2.6× base, p=0.025), so a **streak scale-down / cooling-off state machine**
   (after a strand: 0.75×→0.5×→0.25×, reset on a clean window) caps the consecutive-loss STREAKS (the
   failure mode that turns a normal day negative). It is RISK CONTROL (t≈1.7), not alpha — it bounds
   drawdown, it doesn't add edge. Trivially deployable (stateful, no model).
4. **The perp-hedge is real but small, scale-gated, and does NOT neutralize the tail** (BTC explains
   only 1.7% of strand-loss variance). +$21-30/day ONLY at ~100 contracts (pennies at current size).
   DEFER the venue build until scaled; revisit as a per-fill YES-leg hedge then.
5. **Live candidates still forward-validating (not yet deploy-cleared):** the GBM strand gate
   (AUC 0.72, needs n≥300 forward), `f5_fav_lowsig_complete` (low-CVaR sleeve), t02. Judged vs the
   durable `live_current`; the forward bar (t>3, n≥300) governs.

## Next directions (where to take this)
per-fill YES-leg BTC hedge (sized, close next minute); accumulate ≥150 OOS book-covered windows to
unlock the microprice/depth/VPIN studies; prospective A/B of the f5 sleeve to n≥300; a rolling online
causal classifier (retrain on last 150 settled windows); and a strand-causation mechanism study
(structural vs temporal vs calendar).

## Deployable NOW (recommended)
**Streak scale-down state machine in the trader** — the only thing the program found that directly
counters the negative-day streaks, deployable without a model. Caps consecutive-strand drawdown; not
alpha. Everything else needs more forward data or scale.
