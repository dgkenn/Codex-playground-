# ML completion model — built, tested, and the reframe it forced

## Q: can ML predict whether a leg will be paired? A: yes — but the answer reframes the problem.

We fit a regularized logistic model to predict box completion ("did both a YES and a NO leg fill in
the window?") from causal window-open features.

- **OOS AUC 0.82–0.90.** It works, and it beats the rule-of-thumb heuristic (OOS AUC 0.49 ≈ random).
- **The signal lives in two features:** `ofi_sign_agreement` (is early taker flow balanced vs
  one-sided? OOS AUC 0.966) and `early_trade_count` (market activity, OOS AUC 0.985). When both
  sides trade actively in the first ~4 minutes, the window completes; one-sided early flow + low
  activity flags the rare failures. Price/spread/vol features are IS-overfit noise (flip sign OOS).

## ⭐ The surprising, load-bearing finding: completion is ~99.65% in principle
In the idealized fill reconstruction (front-of-queue, BOTH legs quoted the whole window), **only
4 of 1,158 windows fail to complete a box.** The market trades both sides almost every window. So
the ML model's *practical* value is capped by the base rate — it can only sideline the rare ~0.35%
of genuinely one-sided windows.

## What this means — the unpaired-leg problem is EXECUTION, not prediction
This reconciles a paradox: the tape says 99.65% complete, but our live 24h audit had unpaired legs
in 39% of windows. The gap is **our own execution and pairing constraints**, not the market:
1. **Queue position** — we're not always front-of-queue, so a taker can cross our price without
   filling us (the idealized q0=0 assumes we always fill).
2. **`--max-net 1` strict pairing** — after one leg fills we STOP quoting that side; if the market
   then moves, the completing leg is stranded at a now-stale price.
3. **Post-fill drift** — the second leg's touch moves away after the first fills.

The market offers both sides ~99.65% of the time; **we fail to CAPTURE both.** So the highest-leverage
fix is not a fancier completion predictor — it's better **execution of the second leg**:
- **Queue priority** (sub-cent improve to front-of-queue on the completing side).
- **A-S inventory lean / chase** — re-quote the completing leg aggressively toward the moved touch.
- **Completion-urgency** scaling as the leg sits unpaired.
These are the literature-backed levers (Avellaneda-Stoikov lean; legging-risk "complete the hard leg")
that attack the actual cause.

## The ML model's real niche (still worth wiring)
`ofi_sign_agreement` is a strong, stable gate for the rare one-sided windows: **don't open a fresh box
when early flow is one-sided and activity is thin** — those are the windows that genuinely strand a
leg. Low cost, real (if small) benefit. Already approximated by `t06_balanced_flow` in the A/B tester;
the fitted version is `ofi_sign_agreement`. As the live book stream accumulates depth/OI/microprice,
a richer model (GBM) becomes justified — but on current data a 2-feature logistic is the right
complexity (more would overfit, per the directional-test lesson).

## Companion result: correlated-binary hedge — NO (tested)
Hedging an unpaired BTC leg with an opposite ETH/SOL 15-min binary does NOT work at integer size: the
hedge binary's own settlement variance (~0.08) swamps the cross-covariance it removes (~0.03–0.04), so
a 1-contract hedge *increases* variance 78–115%. The optimal ratio (h*≈0.2) needs 4–5 unpaired legs to
size one hedge — by then the exposure has settled. BTC-binary settlement correlation with ETH/SOL is
only ~0.68 (the "0.99" is spot, not binary). **Verdict: tighter pairing/execution + size limits, not
cross-asset hedging.** (Consistent with the perp scoping: hedging doesn't fit our size.)
