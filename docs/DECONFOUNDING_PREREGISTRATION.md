# Pre-registration — assay-noise IV / flag-ITT analyses (locks specs BEFORE seeing outcomes)

**Why.** Threshold designs have a garden-of-forking-paths / threshold-shopping vulnerability (scan Hb 7/7.5/8/9
× windows × controls, report the cleanest). This document pre-specifies threshold, bandwidth, control, estimand,
outcomes, and analysis order so results are confirmatory, not curated. Deviations must be logged as post-hoc.

## Common design (both applications)
- **Instrument** `Z = 1(W_decision < flag)` on the SECOND pre-treatment draw of the hospitalization.
- **Severity control** = **midpoint `(M1+M2)/2`** (primary), used ONLY after the equal-draw-variance check
  passes (sim: midpoint valid iff Var(ε1)≈Var(ε2)); **local leave-one-out proxy** for the renewal analysis.
  M1-only is a labeled sensitivity, NOT primary (sim: biased).
- **Primary estimand** = **flag-ITT** (reduced form of `Y ~ Z | control`), reported WITH the implied-LATE
  interval (ITT ÷ first stage, Anderson–Rubin CI). A null ITT is reported as "no effect OR underpowered."
- **Inference:** HC1 for single-decision; patient-clustered (CR2 / wild bootstrap) for renewal. Effective-F
  reported; delta-method CI NOT used as headline.
- **Falsification battery (pre-specified, in order):** (1) density/heaping test at the flag + donut hole if an
  atom at the round value; (2) equal-variance / σ-by-interval + noise lag-1 autocorrelation; (3) covariate
  balance on Z (age, and pre-treatment covariates); (4) bundle balance (co-treatments, LOS) on Z; (5)
  competing-risks robustness (30/90-day, discharge disposition). A design that fails (1) is not reported as causal.

## Application A — Magnesium repletion (trial-infeasible; the novel clinical target)
- **Flag:** Mg < 2.0 mg/dL (primary); 1.5 as a pre-specified sensitivity. **Bandwidth on the control:** ±0.15
  (primary), ±0.10 / ±0.20 reported as a sensitivity surface.
- **Treatment:** IV Mg repletion (inputevents 222011/227523/227524) within 24 h of the decision draw.
- **Outcomes:** PRIMARY in-hospital mortality (+30-day if linkage available); SECONDARY new-onset arrhythmia
  proxy, ICU transfer, LOS, over-repletion (hyperMg). No outcome added after unblinding.
- **Prediction (honest):** flag-ITT near zero with sub-pp CI; implied-LATE wide. De-implementation-consistent
  if the ITT is a precise null.

## Application B — RBC transfusion (RCT-anchored VALIDATION; benchmarks Bosch 2022)
- **Flag:** Hb 7.0 g/dL (primary, TRICC/TRISS); 8.0 as pre-specified secondary. **Bandwidth:** ±0.6 g/dL.
- **Treatment:** packed-RBC transfusion (inputevents 225168) within 24 h of the decision Hb.
- **Strata (pre-specified, the graded test):** GENERAL (non-cardiac) — RCT truth = restrictive non-inferior →
  **predict flag-ITT ≈ 0**; CARDIAC SURGERY (service CSURG/CMED/VSURG) — RCT truth contested, TITRe2/MINT
  liberal-favoring → **predict a liberal-favoring signal.** Recovering BOTH validates; recovering only the clean
  null is a soft pass.
- **Outcomes:** in-hospital mortality (primary); next-Hb (first-stage sanity vs Bosch's >20 pp discontinuity).
- **Prior art:** Bosch et al. *Ann ATS* 2022 (fuzzy RDD at Hb 7 in MIMIC-IV) is the benchmark; our formal
  noise-model instrument must sharpen or extend, not merely reproduce.

## Locks
- Thresholds, bandwidths, control, estimand, outcomes, and strata above are FIXED before viewing any
  outcome regression. The falsification battery runs and is reported in full regardless of results.
- Any post-hoc analysis is labeled exploratory. Negative results are reported (LESSONS.md).
