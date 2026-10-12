# Pivot 2 hostile review: SVR-free waveform estimate of measured SVRI

N (direct-EV1000-SVR cases, physiologic SVRI) = 221. The one finding that survived the outcome-confounding battery (targets MEASURED physiology, not a confounded outcome) -- here stress-tested with the same hostility.

- **A. Circularity:** strict NON-pressure morphology incremental R^2 over ALL pressure scalars (direct-SVR) = **0.1109** -> PASS (not just re-reading MAP).
- **B. Overfitting:** OOF r 0.4561 vs permutation null mean 0.0745 (95th 0.1749), perm p = **0.005** -> PASS.
- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = **0.0556** -> PASS.
- **D. Mechanism:** tau (diastolic decay ~ R*C) partial-Spearman vs SVRI given MAP = **0.1613** (raw 0.1643).
- **E. Stability:** OOF r 0.4561, bootstrap CI [0.3753, 0.6182].

## Verdict: PASSES hostile review -- strict non-pressure morphology predicts DIRECT-measured SVRI beyond all pressure scalars (incr R2 0.1109), beats permutation null (p=0.005), survives body-size adjustment (incr R2 0.0556); tau partial-vs-SVRI given MAP = 0.1613.

Limitations: single-centre; EV1000/Vigileo CO-monitor subset (selected); SVRI is CO-derived (noisy); modest N. PASS here means the SVR-free morphology signal is real, non-circular, not overfit, and not a body-size proxy -- a defensible MEASUREMENT claim (no outcome, so no outcome-confounding), and the basis for Phase 2e.

---

## AIRTIGHT FOLLOW-UP (the sophisticated circularity attack) — SCOPES THE CLAIM

A sharp reviewer notes HR was in the "non-pressure" set, and HR→CO→SVRI is semi-tautological
(SVRI = 80·(MAP−CVP)/**CO**). The decisive test: does PURE waveform SHAPE (τ, AIx — no HR) add
over **pressure + HR**?

- pressure + HR: OOF r = 0.49, R² = 0.27
- pressure + HR + pure-shape(τ, AIx): R² = 0.267
- **pure-shape incremental R² over pressure+HR = −0.007 (≈ 0).**

**Interpretation — the claim bifurcates:**
- ✅ **DEFENSIBLE (estimation):** "SVRI can be estimated from the arterial line ALONE (no
  cardiac-output monitor), cross-validated r ≈ 0.49 / R² ≈ 0.27, incremental over mean
  pressure." This is a useful **SVR-free ESTIMATION** tool (uses only the A-line: pressure,
  HR, morphology). Non-circular w.r.t. *needing an EV1000*, not overfit (perm p=0.005), not a
  body-size proxy. This survives.
- ❌ **NOT supported (pure-tone mechanism):** "waveform tone-SHAPE (τ/diastolic decay, AIx)
  encodes vascular resistance beyond pressure AND flow." τ/AIx add ~0 over pressure+HR; the
  beyond-pressure signal is largely the HR/flow pathway, not tone-shape. The τ partial-vs-SVRI
  given MAP (+0.16) does NOT hold once HR is also conditioned.

**Honest scoped verdict:** Pivot 2 passes hostile review **as an arterial-line-only SVRI
*estimator*** (a measurement/instrumentation claim, no outcome → no outcome-confounding), NOT
as a novel "tone-shape morphology" discovery. 

**Implication for Phase 2e:** the real target is the residual SVRI signal beyond pressure+HR;
the summary-feature evidence suggests it is SMALL, so a generative-counterfactual on raw
waveforms should condition on pressure+HR and may well yield a clean NEGATIVE (vascular-tone
estimation reduces to pressure+flow) — itself publishable, but the "novel tone morphology"
upside is now uncertain and should not be over-promised.
