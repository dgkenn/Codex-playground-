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

### Round 1 — RESULTS (commit 2e308ec; ROUND1.md)
Tape 576 windows, OOS strand 3.36%. **live_current (t36) baseline already +5.30c/win OOS** and has
cut OOS strand 13.6%→3.36%. ALL 5 ideas UNDERPERFORM live OOS (−1.9 to −5.8c) → nothing registered.
- (1) linear strand-predictor: AUC 0.563 (linear boundary insufficient); gate never fires usefully.
- (2) A-S continuous skew: binary t36 beats every continuous variant by 2–5c.
- (3) |sig| momentum filter: t36 already embeds sig>8 for thin spreads; standalone adds nothing.
- (4) microprice-divergence + (5) queue-thinness: IS book coverage = 0 → untestable (data gap).
**Finding:** t36 already captured the predictable strand-prevention edge; residual strands sit where
decision-time signals weakly separate. Top lever: non-linear spread×|p−0.5| interaction (AUC 0.56
linear → try a tree). Forward bar correctly held (no registration).

## Round 2 — ideas (data-derived from R1; testing dispatched)
- **R2-A** Tree-ensemble strand classifier (GBM on spread,|p−0.5|,sig,|flow|,k,tau,vpin); target OOS
  AUC>0.65; if it beats live, distill to a frozen gate → t38_strand_gate.
- **R2-B** sig×spread CONJUNCTIVE gate grid (|sig|∈{5,8,10,12} × spread∈{.01,.015,.02,.025}) — do
  compound conditions (momentum AND tightness) beat each signal alone / beat t36?
- **R2-C** Time-of-day stratified |sig| thresholds (4 UTC bands) — is high-|sig| Asia-session a false
  positive (mean-reverting, not strand-prone)?
- **R2-D** depth×VPIN combined gate vs t32 alone (book stream; flag IS-coverage limit).
- **R2-E** re-test microprice-divergence + queue-thinness on the windows WITH book coverage (recent),
  OOS-only, to salvage the data-gap ideas.
