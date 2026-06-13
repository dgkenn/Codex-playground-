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

### Round 2 — RESULTS (commit 90d03fa; ROUND2.md)
live_current OOS baseline -5.99c/win, strand 6.63%. **First real signal: R2-A GBM strand classifier
OOS AUC 0.720** (vs R1 linear 0.563) -> gate cuts strand 6.6%->3.5%, net -5.99->+2.26c (diff +8.25c
vs live, skew flips +). PRELIMINARY: selection effect (skips 51/200 windows, t-stat negative), n=149
< 300 deploy bar -> NOT registered. R2-B (conjunctive) + R2-C (time-of-day) = selection mirages (t<2)
but R2-C found real structure (Asia high-|sig| strand-prone; EU mean-reverting). R2-D/E blocked by
book-coverage (n<50). **Takeaway: non-linear strand prediction WORKS (AUC 0.72); needs forward n>=300.**
Also LIVE 24h RCA (this session): loss mode SHIFTED to NO-strands (4 NO / 1 YES of 5 strand windows,
clustered 11:00-12:47Z) -- t36 guards only YES opens, so it's blind to the current streak.

## Round 3 — ideas (testing dispatched)
- **R3-1** Settlement-MAGNITUDE GBM regressor (target settle cents, not binary strand); gate on
  E[settle]<0 high-confidence -> profitable cut with less volume loss than the binary gate?
- **R3-2** DIRECTIONAL YES-leg vs NO-leg classifiers (signed sig) + the SYMMETRIC NO-GUARD (mirror of
  t36: suppress thin-spread NO opens when an UP-move is adverse) -- directly targets the live NO-strand
  streak. Does a directional/NO-side gate beat live on the NO-strand windows?
- **R3-4** Perp-hedge net PnL on OOS residual strands WITH realistic slippage/fees -> min edge that
  survives execution; is a hedge venue worth building?
- **R3-5** Volatility-regime conditioning: partition by std(spot_path) quartile; is the top-vol
  quartile the source of all strand loss? a coarse vol gate vs fill-level features.
(R3-3 = collect >=300 book-covered windows: infra/data-accrual, tracked separately -- collector runs.)

### Round 3 — RESULTS (commit 217b633; ROUND3.md)
NOTHING clears the forward bar. R3-1 settle-regressor R^2~=0 (can't predict strands; n collapses to
21). R3-2a directional = INVALID LABEL (measured res_up not strand). R3-2b SYMMETRIC NO-GUARD: helps
marginally (+1.865c vs live) ONLY with the orphan carve-out (blanket NO-guard HURTS -- high-ask NO
strands favorable), but n=168/t=-2.20 -> not deployable. R3-5 vol-regime: Q4 top-vol = strand zone
(55% vs 37%) but skip-Q4 hurts (Q4 has good windows too).
**R3-4 PERP-HEDGE = standout: dominates under ALL cost scenarios (+8.8..+20.5c; slippage/fees
negligible vs -29c strand). The +2.77c edge is robust + conservative. It's an OPERATIONAL BUILD
(BTC-perp venue), not a gate.**
CONVERGING VERDICT: predictive GATES can't beat live (residual strands hard ex-ante); the economically
dominant fix is the HEDGE (venue build). Streaks cluster in time (live RCA) -> a cooling-off rule may help.

## Round 4 — ideas (testing dispatched)
- **R4-2 (highest priority): HEDGE-VENUE FEASIBILITY MATRIX** -- given R3-4 (hedge dominates), produce a
  go/no-go: candidate venues (Deribit/Binance perp), latency, BASIS RISK (Kalshi BRTI settle vs perp
  mark over the 15-min window), min hedge_eff needed (>0.30), capital/margin, execution path. Quantify
  the realistic net edge after basis + costs.
- **R4-5: STRAND TEMPORAL AUTOCORRELATION + COOLING-OFF** -- test P(strand | prior-window strand) vs
  base 29.4%; if >2x, backtest a cooling-off state machine (skip/така N windows after a strand). No
  model, deployable. Directly targets the observed live streak (strands clustered 11:00-12:47Z).
- **R4-4: settle-regressor -> continuous SIZING (not a gate)** -- size leg proportional to predicted
  settle (0.5x/1x/1.5x) to avoid the n-collapse; per-unit improvement vs live?
- **R4-1: vol x directional INSIDE Q4** -- fit YES/NO classifiers restricted to the top-vol quartile
  (55% strand) with a VALID strand label; narrower population may yield actionable AUC.
(R4-3 book-stream to n>=300 = infra/data-accrual; collector running, tracked separately.)

### Round 4 — RESULTS (commit 29314d6; ROUND4.md)
- HEDGE: clears screen (t=4.62,n=200) BUT BTC spot explains only 1.7% of strand-loss variance
  (R^2=0.017) -> the perp does NOT delta-hedge the binary; it's a small MEAN-drift compensation, not
  a tail neutralizer. +$21-30/day ONLY at 100 contracts (pennies at current 1-contract size).
  **Revised verdict: DEFER the venue build -- pays only at scale, doesn't remove the tail.**
- COOLING-OFF: strands ARE autocorrelated (lag-1 = 2.6x base, p=0.025 -- confirms the live streak).
  Skip-N-after-strand cuts strand 10%->8.7%, caps streaks, but t_vs_live~=0 (RISK CONTROL not alpha).
  Deployable tail-risk guard.
- SIZING/GATES: flow_ratio is the strongest signal (t=4.05) but LOOK-AHEAD; causal-only fails. Q4
  directional just rediscovers t36. Nothing new beats live as a gate.
**Lead: can EARLY-window flow (first 60-90s) approximate the look-ahead flow_ratio causally?**

## Round 5 — ideas (FINAL round; testing dispatched)
- **R5-1 (TOP LEAD): EARLY-WINDOW FLOW as a CAUSAL signal** -- flow_ratio (full-window) gave sizing
  t=4.05 but is look-ahead; compute flow_ratio from ONLY the first 30/60/90s of trades and test if it
  approximates the signal: OOS R^2>0 and sizing/gate t>1.5 vs live. If yes, this is the first genuine
  causal alpha.
- **R5-5: STRAND-STREAK CONTINUOUS SCALE-DOWN** -- vs binary cooling-off: 1 strand->0.75x size,
  2 consecutive->0.5x, 3+->0.25x, reset on a clean window. Backtest net/streak-risk vs live + vs N=1
  cooling-off; deployable immediately (state machine, no model). Caps streaks, retains more volume.
- **R5-3: NO-GUARD + early-flow conditioning** -- extend R3-2b (best +1.865c,t=-2.20,n=168) by adding
  early YES-side taker pressure as a second trigger; can t clear 2.5 / n>200?
- **R5-2: hedge TIMING protocol** (only if building later) -- prophylactic (hedge every open) vs
  reactive (hedge on intrawindow adverse spot move); drag vs protection; optimal hedge size by sig.
(R5-4 book-stream to >=150 OOS = infra; collector running.)

### Round 5 — RESULTS (commit 06fb263; ROUND5.md) — FINAL
- R5-1 EARLY-FLOW (make-or-break): **FAIL.** First-60s flow correlates with full-window flow_ratio
  (r=0.49) but has ZERO predictive power for PnL (r=-0.015, t=-0.32). The full-window flow_ratio
  (t=4.05) was a LOOK-AHEAD MIRAGE (it aggregates late-window momentum that DETERMINES settlement).
  No causal alpha.
- R5-5 streak SCALE-DOWN: risk control (t=1.72). Retains volume, cuts maxConsecLoss 12%; binary
  cooling-off N=1 cuts it 50% but loses 20 windows. Both below bar -- RISK CONTROL, not alpha.
- R5-3 NO-guard+early-flow: fires 2/200; early-flow adds noise. Dead.
- **ACROSS ALL 5 ROUNDS: NOTHING beat live at adequate n.** Every apparent winner was look-ahead
  (flow_ratio), oracle (reactive hedge needs to know the strand pre-settlement), or selection/risk-
  control. t36 (deployed) remains the only validated signal.
