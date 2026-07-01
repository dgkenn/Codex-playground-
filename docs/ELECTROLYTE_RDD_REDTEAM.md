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

## Harm-from-over-repletion (run) — NO harm signal
Downstream hyper-Mg (>2.5/>3.0) and hyper-K (>5.0/>5.5) do NOT jump below the repletion cutoff (Mg RD
−0.008/−0.005 in the non-harm direction; K null). Repletion is inert, not dangerous — story stays "no benefit."
