> **⚠️ SUPERSEDED — the numbers below are CONTAMINATED, do not cite.** A hostile-referee red-team found the
> design is not identified: the severity control `T̂=(M1+M2)/2` shares noise with the instrument `Z=1(M2<2.0)`,
> which re-introduces confounding-by-indication (biased toward false harm) *inside* the estimating equation, and
> the "balance passes" check was itself run on the contaminated control. The corrected design (leave-one-out
> severity control), the formal identification + renewal extension, and the prioritized falsification battery
> are in **`docs/ASSAY_NOISE_IV_METHODOLOGY.md`**. This file is kept only as the record of the first cut and its
> refutation. The Result-2 balance/first-stage/reduced-form/LATE figures must be re-derived before any use.

# Assay-noise instrument for reflexive lab-triggered treatments — results + path to bulletproof

**Goal:** a bulletproof, broadly-applicable method to defeat confounding-by-indication for reflexive,
lab-triggered inpatient treatments (electrolytes, PPI, transfusion, ...). Demonstrated on Mg repletion.

## Core idea
Reflexive treatment fires when a MEASURED lab crosses a flag, but measured = true + analytic/biologic noise.
Conditional on true severity, which side the NOISY triggering value falls is as-good-as-random → exogenous
instrument. Applies to every lab-triggered treatment.

## Result 1 — the noise is large enough (viability)
Per-measurement Mg noise SD **σ = 0.134 mg/dL** (from 181,156 consecutive draw-pairs 1–12 h apart). A patient
with true Mg 2.0 flips above/below the 2.0 flag ~50/50 by noise → ample exogenous variation.

## Result 2 — the instrument is EXOGENOUS (the key win nothing else achieved)
Clean single-decision design: two PRE-treatment draws M1,M2; T̂=(M1+M2)/2 = noise-reduced severity;
instrument Z=1(M2<2.0) | T̂. Cohort n=77,925 in T̂∈[1.85,2.15].
- **BALANCE: age on Z | T̂ = +0.27 yr (SE 0.28) ≈ 0 → EXOGENOUS.** (Contrast: provider-IV +0.127 mortality
  confounding; within-patient +7.3 d LOS bias; IPTW RR 4.17.) This is the first valid instrument for the question.
- First stage: Z→repletion **+0.032 (SE 0.003)** — real, highly significant, but WEAK (~3 pp).
- Reduced form: Z→in-hospital mortality **+0.0015 (SE 0.0024)** — NULL (exogenous, balance-validated).
- LATE +0.045 [−0.10, +0.19] — null point estimate, imprecise (weak-instrument CI, LATE-MDE ~21 pp).

**Reading:** with a *valid, exogenous* instrument, being pushed below the repletion flag by noise does NOT
raise mortality — a genuine (if imprecise) causal null. The reduced form is itself a valid ITT-type statement
that does not require scaling by the weak first stage.

## Result 3 — naive repeated-measurement pooling FAILS (and why the fix is the novel contribution)
Pooling all 1.05 M near-cutoff draws as decision-points gave a degenerate first stage (≈0): most interior
draws are NOT the decision-trigger, diluting the instrument. The proper extension is a RENEWAL/survival
structure (each redraw a fresh noise-randomized decision, terminal shared outcome) — exactly the piece the
methods literature has NOT solved.

## Novelty positioning (from the methods deep-dive)
- **Core identification is PRIOR ART**: noise-induced randomization at a threshold — Eckles, Ignatiadis,
  Wager, Wu (*Biometrika* 2025, arXiv:2004.09458); Pei & Shen (*Adv. Econometrics* 2017); Battistin 2009.
  Clinical RDD-at-thresholds is established (Bor 2014) but uses "as-if local randomization", NOT assay noise.
- **Genuinely novel + publishable pieces** (AJE/Epidemiology/Stat Med tier): (1) clinical operationalization
  of the noise-IV for reflexive lab-triggered DE-IMPLEMENTATION; (2) the REPEATED-measurement/renewal
  extension (serially-correlated assay error, repeated decisions, terminal outcome) — nobody has derived
  identification for this; (3) grounding the noise in CLIA/clinical-chemistry analytic imprecision (auditable,
  severity-independent — a far more defensible identifying assumption than provider-habit or smooth-density);
  (4) NEAR-FAR matching (Baiocchi 2010) to make the weak assay-noise instrument usable; (5) a triangulation
  package (assay-noise + proximal CI + empirical calibration + convergent bounds) for de-implementation.
- Also flagged: a **supply-shock DiD** (reagent stockouts / order-set rollouts / formulary switches) is
  unambiguously exogenous and arguably a stronger near-term design — but needs real-calendar data (MIMIC dates
  obfuscated). Front-door/PERR ruled out (structurally mismatched).

## Path to BULLETPROOF (concrete)
1. **Near-far matching** to strengthen the (valid but weak) assay-noise IV → tighter LATE.
2. **Renewal-structure extension** (the novel identification piece): each redraw = a noise-randomized
   decision with a proximal survival outcome; discrete-time hazard IV with within-patient correlated noise.
3. **Triangulate**: assay-noise reduced-form null (EXOGENOUS) + provider-IV clean-strata null + within-patient
   (biased — quantifies the confounding) → convergent partial-identification bounds.
4. **Extend across the portfolio** (PPI, transfusion-in-MI, glucose→insulin) — the assay-noise IV generalizes
   to any lab-flag treatment; the PPI RCT-vs-observational discordance is the ideal validation case.
5. **RCT anchor** (RESTRAINT) as ground truth to certify the method, then transport to trial-infeasible questions.

## Status
Milestone reached: a VALID (exogenous, balance-verified) instrument for a question where every prior design
was confounded — plus a clear, literature-grounded novelty position and a concrete plan to precision + breadth.
