# Electrolyte-repletion RDD — hostile red-team + novelty (delegated: sonnet + haiku)

## Novelty / evidence base (haiku + PubMed) — NOVEL, high-impact
- **No RCTs** exist for treating MILD asymptomatic hypo-Mg or hypo-K in general inpatients; practice is
  protocol/expert-opinion driven.
- **Closest causal prior work:** a 2023 propensity-matched study of mild hypokalemia (K 3.0–3.4), n=724
  matched → null mortality (OR 0.81, 95% CI 0.36–1.79) [Medicina 2023, PMID 38003961]. Small, K-only, PSM.
- **No RDD of electrolyte repletion exists anywhere; none for Mg at all.** This study is 5–50× larger and
  uses a stronger design → genuinely novel + likely highest-powered on the general repletion question.
- **Boundary (where repletion HAS evidence) — and it's wobbling:** post-cardiac-surgery Mg for AF prophylaxis
  (meta-analysis RR 0.55) — BUT a 2026 RCT targeting Mg 1.5–2.0 was **null/futile, stopped for futility**
  [Meerman, CCM 2026, PMID 42206948]. Also torsades/long-QT, digoxin toxicity, severe/symptomatic deficiency.
  → EXCLUDE these strata; scope the null to mild/asymptomatic general inpatients.
- De-implementation framing is emerging (2025 UK paediatric-ICU Delphi flags electrolyte management).
- **Verdict: NOVEL, JAMA Intern Med / Annals / BMJ tier if executed rigorously.**

## Hostile methods red-team (sonnet) — MAJOR REVISION (not kill); real strengths, three must-fixes
Strengths conceded: huge N, threshold sweep, injection-test power validation, BH-FDR, ICU/cardiac boundary,
honest first-stage reporting. Threats (rated) + fixes:
1. **[BIGGEST THREAT] Running-variable definition** — first-Mg-per-admission may misspecify the actual
   decision-triggering value (clinicians key off lowest/most-recent/trend). Measurement error can
   MECHANICALLY manufacture a null independent of the truth. **FIX:** re-run with (a) lowest-Mg-in-window and
   (b) the lab value immediately preceding the repletion order; characterize what fraction of repletions are
   triggered by first vs later value. If null survives → strong; if not → first-lab-only not defensible.
2. **Discrete/heaped running variable** (0.1 resolution) — continuity-based local-linear CIs can be
   anti-conservative. **FIX (mandatory):** Kolesár–Rothe honest CIs or Cattaneo–Frandsen–Titiunik local-
   randomization as PRIMARY; discrete-support density/manipulation test at the exact mass points near 2.0/3.5.
3. **Fuzzy-RDD / scaled LATE** — reduced-form MDE (0.62pp) is NOT the LATE-scale MDE; with a modest first-
   stage jump the LATE CI is wider. **FIX:** report LATE = reduced-form ÷ first-stage jump with delta-method
   CI; state the LATE-scale MDE. Compliers = marginal, protocol-driven (least-sick) patients → argue this is
   FAVORABLE to the de-implementation narrative explicitly.
4. **Outcome ascertainment (ICD, no timing)** — TIER outcomes: mortality/LOS credible; acute arrhythmia/
   seizure = "uninformative" not "null" with ICD-only. Salvage with timed incident events (chartevents).
5. **Selection into being measured** — generalizability boundary (estimand = LATE among patients measured
   near threshold), NOT an identification failure. State the estimand explicitly.
6. **Marginal-patient scope** — the threshold sweep (null at every cutoff 1.2–2.2) broadens the claim; FOREGROUND it.
7. **Multiplicity** — fine if the outcome/subgroup/threshold lists are PRE-SPECIFIED; disclose exploratory vs confirmatory.
8. **Bundled co-intervention at the EHR reference-range flag** — 2.0/3.5 are standard lab reference-range
   lower bounds, so the "L" flag may trigger a BUNDLE (telemetry, repeat labs, alerts), not repletion alone.
   **FIX:** test for discontinuities in OTHER care processes at the cutoff; disclose reference-range≡protocol identity.

**Top 3 to be bulletproof:** (1) discrete-RDD-robust inference; (2) running-variable robustness (lowest/
preceding value); (3) bundled-intervention check. **Single biggest threat: #1 running-variable misspecification.**

## ⚠ CRITICAL: red-team threat #1 CONFIRMED in the data — first-Mg has NO first stage
Testing the first stage with **first-Mg** as running variable: P(Mg repletion after first-Mg) below−above =
**−0.003 (SE 0.004) ≈ 0**. First-Mg does NOT drive the repletion decision → the original reduced-form RDD on
first-Mg was testing a running variable with no treatment discontinuity ⇒ **that null is uninformative**, not
a valid RDD result. (The real treatment jump exists at the per-MEASUREMENT decision value — earlier per-Mg
first stage showed P(repletion≤6h) dropping 4× across 1.8→2.0.) **The finding is NOT established until the RDD
is rebuilt on the correct running variable = lowest-Mg / decision-triggering value.** This is the pivotal
re-analysis (lowest-Mg labevents pass running). Honest status: the de-implementation finding is PENDING this
redo — if min-Mg shows a real first stage AND a null reduced form across outcomes, it holds validly; otherwise
it changes. Documented transparently rather than shipped on the invalid running variable.

## ⚠⚠ DECISIVE: RDD is NOT a valid design here — repletion is a smooth dose-response, not a threshold rule
Raw first stage, P(Mg repletion ≤6h) by first near-cutoff Mg value: 1.6→0.080, 1.7→0.061, 1.8→0.037,
1.9→0.024, **2.0→0.0065**, 2.1→0.0028, 2.2→0.0028. This is a **smooth steep DECLINE that flattens at 2.0**,
NOT a discontinuous jump. Clinicians replete more the lower the value (continuous dose-response); the
discontinuous component at exactly 2.0 is small (~0.5–1.7 pp). **⇒ The RDD first stage is too weak to
identify the causal effect (fuzzy LATE CI is enormous regardless of n). RDD/measurement-level RDD are both
invalid/underpowered for this question.** The reduced-form outcome nulls are real but do NOT causally isolate
repletion (near-flat first stage). **The "comprehensive de-implementation RDD finding" is RETRACTED as an
RDD claim** — honest outcome of red-teaming, caught before submission.

### What CAN answer it (valid paths — none is RDD):
1. **Target-trial emulation** of "replete vs watchful-waiting for mild hypo-Mg/K" with heavy confounding
   control — BUT the trigger value (Mg level) is itself the main confounder (sicker/lower get repleted),
   so this needs rich severity adjustment + negative-control calibration + E-values; hard, and the
   confounding-by-indication ceiling (~OR 1.35 lesson) looms.
2. **Provider/hospital-preference IV** — needs a STRONG, exclusion-valid instrument (unit-IV already failed
   on case-mix; provider-preference within unit is the remaining candidate, feasibility uncertain).
3. **Regression KINK design (RKD)** — the treatment has a kink (declining below 2.0, flat above); RKD is the
   technically-correct tool for a kinked continuous treatment, but demanding (needs power to detect an
   outcome kink; likely underpowered given the weak treatment kink).
4. **The definitive answer = a pragmatic cluster-randomized DE-IMPLEMENTATION RCT** (aggressive vs
   conservative repletion order-set). This is the real practice-changing / guideline-setting study.

### Honest status of the "winner"
Not a validated finding. The genuinely-true, defensible facts that survive: (a) the evidence base for
repleting mild asymptomatic hypo-Mg/K is essentially empty (no RCTs; closest is n=724 PSM, null); (b) the
practice is enormous (129k Mg administrations/1 hospital); (c) outcomes vary SMOOTHLY through the putative
thresholds with no jump. These motivate — but do not themselves constitute — a causal de-implementation claim.

## Harm-from-over-repletion (run) — NO harm signal
Downstream hyper-Mg (>2.5/>3.0) and hyper-K (>5.0/>5.5) do NOT jump below the repletion cutoff (Mg RD
−0.008/−0.005 in the non-harm direction; K null). Repletion is inert, not dangerous — story stays "no benefit."
