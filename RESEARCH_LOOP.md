# Strand-prevention research loop (5 rounds, 2026-06-13)

Iterative program off PREVENT_BAD_TRADES.md. Each round: 5 ideas → test (delegated) → results →
5 data-driven follow-ups → next round. Screens vs `live_current`; forward bar governs deploy.
This log is updated round-by-round (durable across restarts).

---
## Round 1 — ideas (testing dispatched)
The theme: use the now-recorded decision-time signals to **predict & gate strand-prone opens**.
1. **Strand predictor gate** — fit P(strand | decision-time features: sig, microprice−mid divergence,
   spread, prior-min flow imbalance, |p−0.5|, k); gate opens above a P(strand) threshold. Measure
   strand-rate cut vs volume/PnL, IS/OOS.
2. **A-S quote skew vs binary suppress** — continuous Avellaneda-Stoikov reservation skew (demand
   +Xc edge on the threatened side) vs t36's binary spread-floor. Does continuous beat binary?
3. **Spot-momentum entry filter** — refuse opens when |sig| (3-min spot move) exceeds a threshold
   (momentum → strand). Sweep the bps threshold; net PnL + strand-rate.
4. **Microprice-divergence gate** — skip a leg when microprice diverges from mid against that side
   (the book already leaning away → likely strand). Threshold sweep.
5. **Completing-side queue-thinness entry** — open only when the completing side's displayed depth
   is below a threshold (fast pairing likely). Uses the full-depth book stream; P(both) lift.

Results + follow-ups: appended below as the round completes.
