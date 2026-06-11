# ML completion model — built, tested, and the reframe it forced

## ⭐⭐ RIGOROUS VERDICT (realistic-queue q0=5000, no-leak, GBM+logistic, proper lift tests)
We did the exhaustive 2nd feature round + GBM + DeLong + bootstrap economic-lift + multiple-testing.
**"Will this leg pair?" is statistically predictable but economically useless to gate on — and the
test surfaced that completion is NOT the real problem; ADVERSE SELECTION on the fills is.**
- GBM ROC-AUC **0.874**, beats the binary's own price (0.624), DeLong **p≈0** — real signal exists.
- BUT a SINGLE feature, **`trade_count` alone, AUC 0.903, BEATS the GBM** (p=0.72) — the ML ensemble
  adds nothing over "is the window active?" The exhaustive features collapse to one.
- **Economic lift from a completion gate: +0.22c/window, 95% CI [−0.96, +1.89] — spans zero.** Does
  NOT survive Bonferroni. Because even at realistic queue, completion is **95.6%** — only 51 of 1163
  windows fail, too rare to gate on profitably.
- **The model's own diagnosis:** baseline PnL is −51.6c/window — "the real edge problem is not
  completion prediction but **adverse selection on the fills**." The legs we get filled on are toxic
  (we're filled on the side the market is about to run over), regardless of whether they pair.

### Refinement at a DEEPER queue (q0=12000, completion 69% — the realistic back-of-queue maker)
A second rigorous run at a deeper queue (where completion is a balanced 69%, matching a maker who is
NOT front-of-queue) found a THIN but real edge — with heavy caveats:
- GBM AUC 0.756 beats price (0.528), p≈0, survives Bonferroni. Gating "open only if P(complete)>0.70"
  gives **+0.26c/window, 95% CI [+0.19,+0.33]** — excludes zero.
- BUT (1) it's **entirely `trade_count`** — `open if early-4-min trade_count > X` matches the GBM
  (GBM vs trade_count p=0.78); the ML is a dressed-up activity threshold. (2) The OOS window was a
  **higher-activity regime** (77.7% vs 63.7% IS completion), so the gain is partly favorable-regime,
  not robust alpha. Untested through a low-activity reversal.
- **The one deployable completion finding: a simple activity gate — only open/quote when early-window
  trade count is high.** Thin, regime-sensitive, single-feature; no ML needed. (≈ `t06_balanced_flow`
  in the A/B tester.) Worth adding as a `trade_count` trial; not worth a model.

**Conclusion: completion prediction is at best a thin, single-feature (trade_count), regime-sensitive
activity gate — no ML lift over the one obvious variable, and no help with the actual losses.**
The exhaustive feature engineering and rigorous testing were worth it precisely because they prove
where the edge is NOT. **The productive target is the ADVERSE-SELECTION quality of a fill** — "will
this leg LOSE / is this fill toxic?" — not "will it pair?" That is the VPIN/toxicity direction, where
a real (small) edge already validated (VPIN-conditioned exit, OOS t=3.4). Next model: predict the
fill's markout/loss (toxicity), not its pairing.

### Per-leg pairing at DEEP/realistic queue (q0=15000, balanced 50%) — the encouraging run
At the queue depth where legs are 50/50 to pair AND net losers (−10.3c/leg hold-all — the adverse-
selection regime), predicting "will THIS leg pair?" per-leg DOES have economic value:
- GBM AUC 0.817 (vs tau 0.793, price 0.688). **Economic: exit legs with P(pair)<0.5 → +3.6c/leg vs
  hold-all, 95% CI [+1.44, +5.63] — excludes zero.** It REDUCES the loss (doesn't make it positive).
- BUT the dominant feature is **`k` (minute of fill)** alone (AUC 0.793) — late fills (k=11-12) almost
  never pair. GBM beats `k` only at p=0.06 (NOT Bonferroni-significant). #2 driver: **`flow_sign_vs_leg`
  (is taker flow adverse to our leg?)** — a TOXICITY feature. Then price level, lock-if-complete.
- So the deployable signal ≈ **"exit an unpaired leg that is LATE in the window with ADVERSE flow"** —
  a simple gate (minute + flow-vs-leg), not an ML model. And it's the same thing as toxicity: a leg
  that won't pair is usually a leg that was filled adversely. **This is why the toxicity model is the
  right unification** — pairing-failure and toxicity are the same phenomenon viewed two ways.

## Q: can ML predict whether a leg will be paired? A: yes statistically, but it's not the edge.

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
