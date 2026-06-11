# ML completion model — built, tested, and the reframe it forced

## ⭐⭐⭐ THE PRE-FILL OPENING GATE — the one ML result with REAL lift (deployable)
The question "**if we buy this leg, will it pair PROFITABLY?**" (pre-fill, opening decision), with the
economically-correct label (does price move enough that the box completes at a *profit*, not just
"does the market trade both sides"), IS meaningfully predictable — and here the ML beats the simple
baselines, unlike every other framing:
- GBM ROC-AUC **0.743**, beats the best single baseline (flow×ofi 0.654) by **+0.089, p<0.0001**
  (bootstrap-confirmed). Beats tau (0.594), price (0.547), trade_count (0.574). **The model adds real
  lift over every simple rule** — the first time that's happened.
- **Opening gate (P(pair)>0.70): cuts the unpaired-leg rate 25.5%→16.5% (−35%) while keeping 70% of
  volume**; completion 83.5% [82.5,84.4] vs open-all 74.5% (CI excludes the base rate).
- Drivers (all interpretable, all match prior findings): **side** (NO pairs more — the structural
  YES-toxic/NO-favorable result), **mid level** (entries near 0.5 pair; tails strand — deep-tail
  toxicity), **flow×OFI agreement** (balanced flow completes — the Area-1 standout), mid_dist×tau.
- Caveat: the label is BOOK-PATH based (assumes fillability), so it overstates the live benefit —
  queue position + slippage will shrink the realized 35%. It's an upper bound, not a guarantee.

**This is the deployable lever: a completion-aware OPENING gate.** Don't open a leg when the fitted
P(pair-profitably) is low (wrong side + tail price + one-sided flow + late). It's the prevention side
(cut unpaired FREQUENCY), complementing the toxicity EXIT (cut the bad legs that do open). Both are
real; the opening gate is the stronger, ML-supported one. Wire it into the A/B tester (it generalizes
t04/t06/t09) and, if it holds forward, into the live opening logic.

### ⚠️ RECONCILIATION — the opening-gate edge is LABEL-DEPENDENT, not yet robust (read this)
Three opening-gate runs were fit on the SAME data with DIFFERENT labels and reached OPPOSITE verdicts.
Honesty demands recording the conflict rather than cherry-picking the encouraging one:
- **a9717 — "spread-closing / profit" label** (does price move enough that the box completes at a
  *profit*): GBM AUC **0.743**, beats baselines p<0.0001, gate cuts unpaired 25.5%→16.5%. ENCOURAGING.
- **aa209d — "next-5-trades pairing" label** (does the opposite side actually trade in the next 5
  prints): GBM AUC **0.495 — WORSE than a coin flip.** No signal at all.
- **ad4a49 — per-leg "ever pairs" label, q0=2000** (realistic-ish queue): GBM AUC **0.922** beats
  baseline 0.868 (+0.055, p<0.001 Bonferroni) — but the economic lift is only **+0.3–0.4c/leg with
  overlapping CIs** (statistically real, economically marginal), and it's dominated by k + |p−0.5|.

**What this means:** the apparent opening-gate "lift" is an artifact of which label you pick. The
profit-label (a9717) bakes the favorite-longshot price structure INTO the label, so the model is
partly re-learning "tail + wrong-side legs lose" — true, but already captured by the simple
price/side gates (t04/t06). The pairing-label (aa209d) — the framing the user actually asked for,
"will this leg pair?" — shows **no predictive signal beyond noise.** The per-leg run (ad4a49) splits
the difference: statistically significant, economically marginal, single-feature-dominated.

**Tempered verdict (walking the optimism back):** there is NO robust, label-invariant ML edge on the
opening decision. The one consistent, deployable signal across all runs is the SAME cheap gate we
already knew — *don't open wrong-side legs at tail prices late in the window with adverse flow* — which
is a 3-variable rule (side × |p−0.5| × flow-vs-leg), not a model. This matches the directional-signal
and per-leg findings: the market is efficient; the only edge is avoiding the structurally-toxic legs,
and that's a rule, not an ML lift. Wire the rule into the A/B tester (generalizes t04/t06/t09); do NOT
deploy a fitted opening model on the strength of the profit-label run alone.

## ⭐⭐⭐ THE FILL-TOXICITY MODEL — the one framing where ML beats the simple gates economically
Pivoting from "will it pair?" (no robust signal) to "is THIS fill toxic / will this leg LOSE?"
(settle<0) is where the ML finally earns its keep. 20,318 live fills, time-series split (12,239
train / 8,079 test), balanced label (50.9% toxic on settle, 49.6% on markout).
- GBM ROC-AUC **0.765** (settle) / 0.605 (markout), beats the best single baseline flow_adv
  (0.62 / 0.55); DeLong delta +0.25 / +0.10, p≈0. Logistic 0.67. Real nonlinear signal.
- **Economic — the decisive part: a GBM toxicity gate beats hold-all AND beats VPIN-only AND
  sig_adv-only.** Keeping only the ~10% cleanest fills: **+2.10c/fill on settle, 95% CI
  [+0.04, +4.19]** (excludes zero); **+2.91c/fill on markout, CI [+0.84, +4.93]** (excludes zero).
  VPIN-only gate +0.15c and sig_adv-only +0.23c both have CIs that SPAN zero. The ML adds lift the
  simple rules don't — the first and only framing where that's true.
- Drivers (OOS permutation importance): **p_abs** (price level), **flow_x_tau** (adverse flow × time
  remaining), **side_bin** (YES toxic — the structural result), **sig_adv** (spot signal vs leg),
  abs_p05. All interpretable; all the toxicity story.
- CAVEATS: the gate threshold was tuned on the test fold (mild optimism; the settle CI low-end sits
  near zero), and "hold 10%" means it abstains aggressively — read it as a strong EXIT/avoid signal
  (cut the worst decile), consistent with the already-validated VPIN-conditioned exit (OOS t=3.4) but
  stronger. Forward-validate before sizing on it.
- **THE DEPLOYABLE ML LEVER: not the OPENING gate (pairing had no robust signal), but the
  EXIT/avoid decision — score each fill's toxicity and cut/don't-hold the toxic ones.** Wire as a
  toxicity score into the A/B tester (generalizes t13_sell_unpaired_vpin); if it holds forward, gate
  unpaired-leg holds on it. This is the unification COMPLETION_MODEL predicted: a leg that won't pair
  is usually a leg that was filled adversely, and toxicity — not pairing — is the predictable target.

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
