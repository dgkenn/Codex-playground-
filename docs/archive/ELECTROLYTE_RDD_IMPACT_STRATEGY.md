# Making the electrolyte-repletion RDD ULTRA-high-impact / practice-changing

**The finding (current):** threshold-triggered magnesium & potassium repletion has no detectable causal effect
on in-hospital mortality, LOS, or ANY of ~17 known complications of hypo-Mg/hypo-K — comprehensive,
FDR-corrected RDD, n≈128k (Mg) / 54k (K) near-cutoff admissions, MIMIC-IV; robust across acuity, multi-
threshold, validity checks pass (no manipulation, covariates continuous). Almost certainly the **highest-
powered causal study ever conducted on the general reflexive-repletion practice.**

## Why this can change practice (the thesis)
Electrolyte repletion is one of the **most common inpatient reflexes on earth** — 129,263 Mg administrations at
ONE hospital; tens of millions of doses/yr in the US — done on protocol/nurse-driven order sets, at thresholds
with **essentially no outcome RCT evidence** for the general (non-cardiac-surgery) patient. A rigorous "no
benefit across every outcome" result is a textbook **de-implementation / "Less is More"** target: huge volume,
low evidence, real costs and harms. This is JAMA Internal Medicine / Annals / BMJ "Less is More" territory.

## The 10 moves that maximize impact (in priority order)
1. **TRIANGULATE identification strategies** (the single biggest credibility multiplier). Show the null
   survives under designs with DIFFERENT assumptions, all converging:
   - RDD at the threshold (done). 
   - **Provider-preference IV** (physician/order-provider baseline repletion propensity, within care unit →
     holds case-mix ~constant; cleaner than the case-mix-confounded unit-IV we already ruled out).
   - **Hospital practice-variation IV** in eICU (207 hospitals vary in aggressiveness).
   - **Target-trial emulation** ("replete vs watchful-waiting for mild hypo-Mg/K", landmarked, with
     negative-control outcomes/exposures + E-values). When 3–4 designs agree, reviewers can't wave it off.
2. **MULTI-DATABASE external validation.** MIMIC-IV (done) + eICU (207 US hospitals; download in progress) +
   ideally MOVER/a national set. Replication across 200+ hospitals = generalizable, not one-center.
3. **PRECISE, ACTIONABLE BOUNDARY.** Pre-specify and SEPARATELY handle the populations with real evidence:
   post-cardiac-surgery AF prophylaxis (positive RCTs — but that's *intra-op* Mg, a different exposure than
   our admission-threshold repletion; keep it), torsades/long-QT, digoxin toxicity, symptomatic/severe
   deficiency (Mg<1.0, K<2.5). Message becomes: **"Stop the reflexive repletion of MILD asymptomatic
   hypo-Mg/K; keep the few evidence-based indications"** — actionable, not nihilistic, hard to attack.
4. **QUANTIFY WASTE + HARM (the "so what" that moves guidelines).**
   - Waste: administrations × cost (drug + IV + nursing time) + lab-recheck cascades + IV-access/alarm burden.
   - **Harm from over-repletion:** does repletion cause downstream HYPERmagnesemia / HYPERkalemia (over-
     correction → weakness, hypotension, bradyarrhythmia)? If "no benefit + measurable harm," the
     de-implementation case is far stronger. (Testable now: follow-up labs in labevents after repletion.)
5. **THRESHOLD OPTIMIZATION → a concrete guideline number.** Sweep candidate cutoffs; if nothing above, say,
   Mg 1.2 / K 3.0 yields benefit on any outcome, recommend lowering the treat threshold there (or symptomatic-
   only). Guidelines need a NUMBER, not "less."
6. **HONEST DISCRETE-RDD INFERENCE + full validity battery.** Values are digit-heaped (0.1) → use Kolesár–Rothe
   honest CIs / local-randomization RDD; report McCrary density (done: no bunching), covariate continuity
   (done: age continuous), placebo cutoffs, bandwidth sensitivity, donut-RDD. Pre-register on OSF.
7. **COMPREHENSIVE OUTCOMES with TIME-RESOLVED endpoints.** The all-outcome null (done, 0/38 FDR) is the
   headline — "if it helped anything, ≥1 of 17 should move." Strengthen the two mechanistic ones with
   TIME-RESOLVED endpoints (new-onset AF & delirium AFTER the index Mg via chartevents rhythm / CAM-ICU),
   converting ascertainment-caveated ICD codes into clean incident events.
8. **HETEROGENEITY / "is there ANY winner subgroup?"** Test renal function, baseline severity, cardiac,
   surgical, on-diuretics, on-digoxin. If truly no subgroup benefits → universal de-implementation. If one
   does → targeted keep. Either way actionable. (Guards against "you missed the population that benefits.")
9. **POSITIVE CONTROL (proves the design can detect a real effect).** Re-run the SAME RDD machinery on a
   threshold with a KNOWN causal effect (e.g., transfusion at Hb 7 → known; or insulin/glucose) — if it
   recovers the known effect, the electrolyte NULL is credible, not a dead pipeline. Critical for reviewers.
10. **FRAME TO MOTIVATE A DE-IMPLEMENTATION RCT.** Position the observational triangulation as the definitive
    case that de-risks and justifies a pragmatic cluster-randomized de-implementation trial (aggressive vs
    conservative repletion order-set). High-impact papers that change practice usually seed the next trial.

## Headline / framing options
- "Reflexive electrolyte repletion in hospitalized adults: no benefit across any outcome — a case for
  de-implementation." (Less-is-More)
- "The most common evidence-free inpatient reflex: a 200-hospital regression-discontinuity analysis."

## Honesty guardrails (so it survives hostile review)
- Do NOT overclaim "Mg/K never help" — bound to MILD, asymptomatic, general inpatients; preserve proven
  indications. Distinguish admission-threshold repletion from intra-op prophylaxis.
- ICD outcomes are ascertainment-limited → lean on mortality/LOS (clean) + time-resolved incident endpoints.
- Fuzzy RDD (modest first stage) → report the LATE + the ITT/reduced-form; a null reduced form = null LATE.
- Report the single nominal signal (Mg→delirium, fails FDR) transparently as a pre-specified follow-up.

## Immediate next analyses (loop continues on these)
(a) eICU external replication of the all-outcome null [download in progress]; (b) harm-from-over-repletion
(downstream hyper-Mg/K); (c) positive-control RDD (transfusion@Hb7) to validate the pipeline detects real
effects; (d) provider-preference IV; (e) discrete-RDD honest inference + placebo/bandwidth battery;
(f) threshold sweep for the guideline number.
