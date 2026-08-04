# Reflexive electrolyte repletion: the case for a de-implementation RCT (observational methods fail)

## The honest terminal state of the observational work
Reflexive repletion of MILD asymptomatic hypomagnesemia/hypokalemia is a huge, evidence-free practice — but
we have now shown, rigorously, that **it cannot be settled observationally**, which is precisely why a
randomized de-implementation trial is required.

### Why every observational design fails here
1. **Regression discontinuity — NO valid first stage.** Repletion probability is a SMOOTH steep dose-response
   in the Mg value (P(repletion≤6h): 1.6→0.080, 1.8→0.037, 2.0→0.0065, 2.1→0.003), flattening above 2.0 —
   NOT a discontinuous "treat if <2.0" jump. The discontinuous component is ~0.5–1.7 pp → fuzzy-RDD LATE
   uninformative regardless of n. (First-Mg, lowest-Mg, and measurement-level RDDs all give first stage ≈0.)
2. **Target-trial emulation (IPTW) — HOPELESSLY confounded by indication.** Cohort = first Mg 1.6–2.0
   (mild zone), non-cardiac, n=109,946; treatment = Mg repletion ≤24h. Crude mortality repleted **11.7%** vs
   watchful-wait **2.3%**; IPTW-adjusted (age/sex/unit/Mg/K) **12.1% vs 2.9%, RR 4.17** — adjustment barely
   moves it. **Repletion is a marker of a sicker, actively-managed patient.** A **negative-control outcome
   fails** (unrelated dx, IPTW RD −2.0 pp; should be ≈0) → large residual confounding remains. E-value 7.8
   reflects the size of the *confounding*, not a real effect.
3. **Practice-variation IV (care unit)** — invalid: unit assignment = case-mix (exclusion restriction
   violated; estimate flips on adjustment). Provider-preference IV untested but faces the same case-mix risk.

**Conclusion:** the causal effect of reflexive Mg/K repletion is NOT observationally identifiable — the
treatment is a smooth function of the confounder (illness severity, expressed through the electrolyte value
and management intensity). This is a genuine, publishable METHODS point on its own (a cautionary demonstration
that the common observational approaches all fail for dose-response reflexive treatments), and it is the
rigorous justification for a trial.

## What DOES survive as established, defensible fact (motivates the trial)
- **Evidence vacuum:** no RCTs for repleting mild asymptomatic hypo-Mg/K in general inpatients; closest
  causal prior = one n=724 propensity study (null). Guidelines are protocol/expert-opinion driven.
- **Enormous, costly scale:** 129,263 Mg administrations to ~33,000 admissions at ONE hospital (~10 yr) →
  tens of millions of doses/yr nationally; nursing time, IV access, alarm/lab cascades, over-repletion risk.
- **Outcomes vary SMOOTHLY through the putative thresholds** with no visible benefit jump (consistent with,
  though not proving, inertness) — and no over-repletion harm-reduction signal.
- **Equipoise is real and total:** we literally cannot tell from any observational method whether it helps,
  hurts, or does nothing — the definition of a question that demands an RCT.

## The deliverable
A pragmatic cluster-randomized DE-IMPLEMENTATION trial (conservative vs standard repletion order set),
protocol drafted in `docs/ELECTROLYTE_DEIMPLEMENTATION_RCT_PROTOCOL.md`. Realistic venue path: the TRIAL is
the NEJM/JAMA guideline-setter; this observational package + the "observational methods fail" demonstration is
the design-rationale / motivating paper (JAMA IM / Annals / a trials journal) that de-risks and justifies it.

## Honesty ledger (what we are NOT claiming)
- We are NOT claiming repletion is ineffective (the observational nulls are not causally identified).
- We ARE claiming: the practice is huge, evidence-free, and observationally unanswerable → an RCT is needed,
  and here is the trial to run.
