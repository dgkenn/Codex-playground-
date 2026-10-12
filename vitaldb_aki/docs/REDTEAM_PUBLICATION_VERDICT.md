# Publication red-team — consolidated verdict (8-agent panel)

An 8-agent adversarial panel reviewed all four findings: **4 sonnet** reviewers acting as
Reviewer 2 at a top critical-care/anesthesiology journal (deep publication critique) + **4 haiku**
auditors doing independent number-reproduction / data-integrity. Each wrote a per-finding doc
(`REDTEAM_PUB_FINDING{1-4}.md`, `REDTEAM_VERIFY_FINDING{1-4}.md`). This is the synthesis: per-finding
publication tier, what was **fixed** in response, and what is **disclosed**.

## Number-integrity layer (haiku) — CLEAN
| Finding | Claims audited | Result |
|---|---|---|
| 1 | 24 | 21 exact, 3 rounding-only (0.817→0.82 etc.); 0 contradictions. "Phenylephrine 0.87 not found" was a **false alarm** — it is sourced in FINDINGS_LEDGER.md / PRESSOR_REQUIREMENT_PHEN.md (auditor searched the wrong files) |
| 2 | 25 | 25 FOUND, 0 mismatch, 0 contradiction |
| 3 | 7 | all FOUND, exact; 0 contradiction |
| 4 | 12 | all FOUND; **NEE itemid check clean** — 229764 (Angiotensin II) correctly EXCLUDED, never treated as dopamine |
No fabrication, no cache-to-doc mismatch, no selective reporting detected. One collateral defect
noted: `mimic_mortality_severity.py:41` labels itemid 229764 "dopamine" in a comment — does not feed
NEE or the mortality model, cosmetic, flagged for cleanup.

## Per-finding publication verdict (sonnet) + our response

### FINDING 1 — requirement → mortality.  Tier: **PUBLISHABLE w/ major revisions** (specialty journal)
Strongest finding; survives. New substantive critique worth acting on:
- **IV exclusion-restriction (C2):** the prescribing-preference IV-OR (3.78) **exceeds** the naive OR
  (2.57) with a strong first stage — an *invalid-instrument* signature, not an isolated LATE.
  → **Response (disclose + demote):** the IV moves from "strongest observational check" to a
  *supportive, hypothesis-generating* sensitivity analysis; the five-front confounding argument does
  **not** rest on it (E-value, within-severity 8/8, propofol negative-control still carry it).
- Already-disclosed (no change): incomplete full-N lactate run (subsample-convergent 2.44/2.53);
  control-theory shown in VitalDB only; characterization OR ~3 vs prospective landmark 1.54; propofol
  negative-control should be ventilated-restricted (M4, future); novelty-vs-prior-art framing (M1–M7).

### FINDING 2 — requirement → AKI.  Tier: **CONDITIONAL** (predictive YES / causal NO, as scoped)
- **Docstring contradiction (C1):** header said "baseline = min creatinine"; code correctly defaults
  to `baseline_mode="first"`. → **FIXED** (`requirement_aki_crossval.py` docstring corrected).
- **Competing risk of death (C4)** and **baseline-eGFR/CKD not in the within-severity model (C3):**
  legitimate, unaddressed. → **Disclosed** as named limitations; the claim is already scoped to
  *risk-stratification, not renal-specific causal* (the INSPIRE negative-control kills the causal arm).
- **Negative-control on 3 control outcomes = 2 df (C5):** fragile. → **Disclosed**: the "causal dies"
  verdict is directional, not a hard rejection; reported as-is. Baseline-choice (first vs min) deviates
  from one reading of KDIGO fallback guidance → rationale documented (avoids the 87% present-on-
  admission ceiling artifact), reported as a sensitivity.

### FINDING 3 — fluid-vs-pressor balance → mortality.  Tier: **DEMOTE to exploratory** (was co-primary)
Harshest panel result (REJECT-as-independent-claim), and the critiques are sound:
- **Not separable from Finding 4 (C1):** the balance numerator IS Finding 4's NEE; no two-predictor
  model shows the fluid denominator adds independent information.
- **Thin adjustment (C2)** — age + single lactate, which barely moves the OR (3.505→3.398).
- **Co-exposed n=28k selection = collider bias (C3)** — OR doubling (full 2.1 → co-exposed 3.5).
- **VitalDB CI [0.996, 1.394] includes 1.0 (C4)** — a null external test, not "concordant support".
  → **Response:** Finding 3 is **demoted from co-primary to a subordinate exploratory observation**.
  The honest statement is "in MIMIC, pressor-predominant balance tracks mortality, but this is not
  shown to be separable from total vasopressor load, the adjustment is thin, and the external test is
  null/untestable." A proper two-predictor decomposition + full severity set is named as future work.

### FINDING 4 — NEE total load → mortality.  Tier: **PUBLISHABLE as prospective risk-stratifier** (after fix)
- **Reverse-causation / tautology (C1, make-or-break):** whole-stay NEE is coterminous with death.
  → **FIXED BY NEW ANALYSIS** (`finding4_landmark.py`, `FINDING4_LANDMARK.md`): **landmark** first-24 h
  NEE, restricted to patients **alive at 24 h**, predicting **subsequent** death → **age-adj OR 2.57
  [2.45, 2.68]** (n=23,925), **age+lactate OR 2.27 [2.10, 2.48]**, monotone Q1→Q4 0.060→0.334. The
  effect attenuates modestly (3.18→2.57) but does **not** collapse → the tautology explanation is
  **rejected**. This is the single most important fix in this pass.
- **Dopamine weight 0.01 vs literature 0.05 (MODERATE):** → **TESTED**, OR 2.57 vs 2.60, no change.
- **"Replication" overstated, 30× effect discordance (C2):** MIMIC 2.57–3.18 vs INSPIRE 1.11, CIs do
  not overlap. → **Reframed**: "directionally concordant across different estimands (ICU whole-stay vs
  intraop cumulative)", NOT a quantitative replication. Dossier language corrected.
- **Age-only adjustment in MIMIC (C3):** → **FIXED**, lactate added (landmark age+lactate OR 2.27).

## What changed in response to the panel (actions taken this pass)
1. **NEW landmark analysis** defeating Finding 4's make-or-break reverse-causation attack (OR 2.27–2.57).
2. **Fixed** Finding 2 docstring/code baseline contradiction (the "poisoned audit trail").
3. **Demoted** Finding 3 from co-primary to exploratory; null VitalDB test stated honestly.
4. **Demoted** the Finding 1 prescribing-preference IV to supportive/hypothesis-generating (invalid-
   instrument signature); confounding argument re-anchored on E-value + within-severity + propofol.
5. **Reframed** Finding 4 cross-cohort "replication" → "directional concordance, different estimands".
6. Dopamine NEE-weight sensitivity run (robust); itemid-comment cleanup flagged.

## Cross-cutting (applies to the joint paper)
- **Multiplicity across 4 findings:** declare ONE pre-specified primary (Finding 1) + label 2–4
  exploratory; the MIMIC secondary surface is not in the original ~30-test Bonferroni.
- **Severity-adjustment asymmetry:** Findings 2–4 used thinner covariate sets than Finding 1; the
  landmark+lactate work narrows this for Finding 4; full harmonization is revision-stage work.
- **Reproducibility package** (code/derived-table deposit) required before submission.

## Bottom line
- **Finding 1:** publishable risk-stratification/characterization paper at a top specialty journal
  after major revisions; no conclusion-changing hole, the IV oversell is corrected.
- **Finding 4:** upgraded — the landmark test makes it a defensible **prospective** dose-response
  (the strongest *new* result of this pass), with honest "directional concordance" cross-cohort framing.
- **Finding 2:** publishable only in its scoped predictive form; causal arm honestly dead; docstring fixed.
- **Finding 3:** demoted to exploratory; not an independent claim.

No finding is fraudulent or numerically unsupported. The two that stand as primary/strong (1 and the
landmarked 4) survived the hardest attacks; the two weaker ones (2, 3) are honestly re-scoped rather
than overstated. The honest ceiling — a prospective decision-benefit trial and a waveform external
cohort for the intraop mechanism — remains future work, not a hole.

Cross-ref: REDTEAM_PUB_FINDING{1-4}.md, REDTEAM_VERIFY_FINDING{1-4}.md, FINDING4_LANDMARK.md,
PUBLICATION_DOSSIER.md, HOSTILE_REVIEW_FINAL.md.
