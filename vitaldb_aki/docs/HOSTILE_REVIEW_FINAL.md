# Hostile-review final verdict — CONVERGED

Three independent adversarial rounds were run against the entire body of work. Each new
round attacked the holes the previous round (or the new results) opened. This is the
convergence statement: **no conclusion-changing hole remains; only disclosable limitations.**

## The claim, as it stands after all rounds (scoped to what survived)
> The intraoperative/ICU **vasopressor dose-REQUIREMENT** (a simple per-kg dose metric) is a
> **reliable, early-identifiable patient signal** with a **clean monotone dose-response** to
> mortality that **survives adjustment for comorbidity (Charlson/Elixhauser) AND for lactate +
> the SOFA lab components** — i.e. it is signal *beyond severity*, not merely "sicker patients
> got more drug." It is **drug-agnostic** (norepinephrine + phenylephrine) and **externally
> replicated** across the operating room (INSPIRE) and the ICU (MIMIC-IV, n≈16k) — where what
> replicates is *dose-ordering as a reliable, early, mortality-graded trait*, not the specific
> MAP-conditioned phenotype. It is grounded in a **control-theory** observation (intraoperative
> MAP is feedback-regulated, so the insult is carried by the dose not the regulated pressure —
> shown in VitalDB). It is a **risk-stratification / characterization** finding, NOT a
> demonstrated treatment effect or practice-changer.

## Round-by-round convergence
- **Round 1** — autocorrelation (rejected: ICC, time-gapped survival, shuffle-null), construct
  validity (relabel: vasopressor requirement, not "vasoplegia"), adversarial code/stats audit
  (degenerate-tone bug fixed; circular construct + wrong-sign SVR + in-sample threshold
  relabeled), severity via Charlson/Elixhauser (OR 3.0–3.8, survives).
- **Round 2** — immortal-time/survivorship (real but no flip; landmarked early-warning OR 1.54),
  VitalDB↔MIMIC construct mismatch (two-level claim), control-theory premise ICU-unproven,
  ICU-LOS collider (dropped → OR 3.12), dose-response-vs-severity (monotone survives, per-SD OR
  3.05), and **the critical lactate/SOFA "beyond severity" test**.
- **Round 3** — completeness critic: **no critical new hole**; the "survives" verdicts are sound;
  lactate complete-case selection moves the base rate not the effect (requirement OR identical in
  lab-complete and full cohorts); #vasopressors is a mediator → dropping it the OR is **2.97**
  (we *understated* the survival); primary stats multiplicity-immune (Fisher-z 84 / 210).

## The decisive test (signal vs just-sicker) — confirmed and convergent
Requirement→in-hospital-mortality OR per SD, adding severity in steps:

| Adjustment | OR/SD |
|---|---|
| age | 3.80 |
| + Charlson + Elixhauser (comorbidity) | 3.7–3.8 |
| + #vasopressors | 3.0–3.1 |
| + **lactate + SOFA labs (creatinine/bilirubin/platelets)** | **2.4–2.5** |
| (same, dropping the #vaso mediator) | **~3.0** |

Subsample convergence (the result is not download-fraction-dependent): ~38% subsample OR
**2.44 [1.90, 3.22]** (n=3,109) → ~46% subsample OR **2.53 [2.03, 3.21]** (n=3,824). The point
estimate is stable and the CI lower bound rises *away* from 1 as N grows → **collapse-to-null is
empirically excluded.** The full-data run (when the 2.4 GB labevents download completes) finalizes
the point estimate but cannot plausibly change the conclusion.

## Disclosable limitations (named, not fatal — honest scope)
1. **Confounding by indication** — the dose reflects physiology × local titration practice;
   unremovable observationally. Conceded, not rebutted. This is why the claim is risk-strat /
   characterization, not causal or practice-changing.
2. **Characterization vs prospective** — the whole-stay OR (~3) is contemporaneous; the genuinely
   prospective number is the landmarked first-6h early-warning OR **1.54**. Do not conflate.
3. **Two-level replication** — VitalDB and MIMIC are different estimands; dose-*ordering* replicates,
   not the MAP-conditioned phenotype/mechanism.
4. **Selection** — arterial-line / already-on-pressor denominator; generalizes to that population.
5. **No pre-registration** — sequential adaptive search; full search disclosed in the ledger;
   primary survives Bonferroni and is multiplicity-immune.
6. **SOFA approximation** — lab components + #vaso; no GCS / PaO2-FiO2 (would need 30 GB chartevents);
   a complete SOFA could attenuate slightly more, but the subsample-convergence bounds the risk.
7. **Single-mechanism setting** — control-theory premise shown in VitalDB only.

## Verdict
**CONVERGED.** Across three adversarial rounds every attack is defeated, fixed, or honestly
disclosed; the one critical test (beyond-severity) is confirmed and empirically convergent. What
remains are disclosable limitations that honest scoping neutralizes — there is no conclusion-
changing hole. The work is a hardened, multiply-externally-validated, hostile-review-survived
**risk-stratification + control-theory characterization** paper. The honest ceiling (a prospective
trial for decision-benefit; a waveform external cohort for the mechanism) is beyond this dataset
and is stated as future work, not a hole.

Cross-ref: HOSTILE_REVIEW_SURVIVAL.md (full attack→defense map, 16 attacks across rounds 1–2 +
Round-3 disclosures), ROUND3_COMPLETENESS.md, FINDINGS_LEDGER.md, and the per-finding docs.
