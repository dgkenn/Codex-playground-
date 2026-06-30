# Red-team Round 3 — Causal attack on ICU_OCCULT_DEPENDENCE.md

**Target claim:** Among ICU patients with AT-TARGET MAP, first-24h vasopressor requirement
stratifies post-24h mortality while MAP does not (monotone 9×, AUC 0.74 vs 0.47), and
MAP CV 0.125 << NEE-rate CV 0.44 confirms the control-theory premise.

All findings cross-reference `docs/ICU_OCCULT_DEPENDENCE.md` (the primary),
`docs/FINDING4_LANDMARK.md` (landmark OR 1.74 [1.57, 1.91], E-value 2.1–2.3),
`docs/CONFOUNDING_BY_INDICATION.md` (five anti-confounding arguments, E-value ~6 on
full-cohort RR, IV OR 3.78), and `docs/RED_TEAM_ROUND2_SYNTHESIS.md` (trait claim retracted).

---

## Issue 1 — COLLIDER BIAS FROM CONDITIONING ON AT-TARGET MAP

**Severity: CRITICAL | Status: NEW (not previously disclosed)**

### The collider structure

"At-target MAP" is not a baseline covariate; it is a **post-treatment intermediate outcome**:

```
Severity (U) ─────────────────────────────────────► Mortality (Y)
     │                                                    ▲
     │                                                    │
     ▼                                                    │
Vasopressor dose (D) ──────► MAP achieved (M) ─── ─────►─┘
     │                          (collider)
     └───────────────── partially mediates M
```

`M` = "at-target MAP" is downstream of both `U` (true illness severity) and `D`
(the treatment). Conditioning on `M` — restricting the analysis to the at-target stratum — opens
the path `U ← M ← D`, i.e., a collider path between unmeasured severity and dose. Even if
`D` were random, conditioning on a descendant of both exposure and confounder induces a
spurious correlation between dose and unmeasured severity within the stratum.

### The steelman: how badly does this bite?

The collider bias argument is strongest when:
(a) substantial unmeasured severity `U` exists (it does: no GCS, no PaO2/FiO2, no
    vasoplegic-etiology marker; already flagged in ICU_OCCULT_DEPENDENCE.md §Caveat 2);
(b) the selection event (achieving target MAP) is influenced by `U` (it is — sicker patients
    require higher dose to achieve the same MAP; this is precisely the "concealment" story);
(c) within the at-target stratum, `D` and `U` are therefore positively correlated (high-dose =
    high-severity to hold MAP constant).

All three conditions are satisfied. The collider structure is not hypothetical; it is the
**mechanism proposed by the finding itself** (vasoplegic shock uses high dose to maintain the
same pressure). The very claim that high dose signals occult severity IS a statement that
conditioning on MAP induces `D–U` correlation.

### Does the finding survive the collider attack?

**Partial survival, but the MAGNITUDE of the association is suspect.**

The landmark design (ICU_OCCULT_DEPENDENCE uses the same first-24h → post-24h architecture as
FINDING4_LANDMARK.md) defeats reverse-causation temporally. The monotone gradient (3.1% → 27.8%
over quartiles) and the AUC 0.74 within the at-target band are **real associations**, not
statistical artifacts.

However, the association is interpretable as follows under the collider model:
- Within the at-target band, dose is a **proxy for unmeasured severity U** (the collider opened
  the path).
- The "occult dependence" interpretation (dose IS the signal that pressure conceals) and the
  "collider-induced severity marker" interpretation (dose is correlated with unobserved severity
  because we selected on achieving target) are **observationally indistinguishable** with current
  adjustment (age + lactate only).

The age+lactate OR 2.59 [2.23, 3.12] partially adjusts for `U`, but critically:
- **lactate is also a post-treatment intermediate** — lactate is measured during the same 24h
  window as the dose and MAP, downstream of resuscitation decisions. It is not a clean baseline
  confounder; adjusting for it partially closes the severity-pathway but also partially adjusts
  out the treatment effect of interest.
- **The E-value on OR 2.59 is approximately 4.5–4.8** (using RR approximation for OR ≈ RR when
  mortality is ~12%: RR ≈ 2.0; E-value = RR + sqrt(RR*(RR-1)) ≈ 3.4 for RR 2.0; for OR 2.59
  the E-value is ~4.5). The prior rounds established E-value ~2.1–2.3 for the fully-adjusted
  landmark (FINDING4_LANDMARK.md). The at-target-band analysis has NO full-SOFA adjustment yet —
  the 4.5 figure is therefore inflated relative to what the full adjustment will likely show.
- GCS, PaO2/FiO2, shock etiology (distributive vs obstructive) and vasoplegic phenotype markers
  are the **exact confounders** that would explain collider-induced D–U correlation within the
  at-target band, and none are adjusted.

### What analysis distinguishes "occult dependence" from "collider artifact"?

**The decisive test is a COMPARISON ACROSS STRATIFICATION DESIGNS:**

1. **Run the same dose→mortality association in the NEVER-at-target stratum** (MAP < 65 throughout,
   or MAP > 85 — patients where the clinician failed to achieve target or did not need to try).
   Under the collider model, the D–U correlation is induced by conditioning on "achieved target"
   specifically; it should be weaker outside that stratum. Under the true "occult dependence" model,
   the dose → mortality signal should exist regardless of whether MAP is at target. If OR(dose →
   death) is similar or larger outside the at-target band, the finding is not specific to the
   at-target selection and the collider story loses force.

2. **Direct collider-bias sensitivity analysis** (Snoep et al. 2022 or VanderWeele bias formula
   for selected samples): parameterize the bias factor as a function of (a) strength of U→M
   selection and (b) U→D correlation within the stratum. The required bias to explain OR 2.59 can
   be quantified. This is analogous to E-value calculation but for selection bias.

3. **Baseline-only severity**: repeat the at-target analysis restricting adjustment covariates
   to variables measured **before vasopressor initiation** (pre-ICU admission diagnosis, admission
   vitals, pre-pressor labs). If the OR shrinks substantially, the within-stratum dose–severity
   correlation is real and partially collider-driven.

4. **Instrumental variable within the at-target stratum**: the prescribing-preference IV from
   CONFOUNDING_BY_INDICATION.md (unit-level leave-one-out dosing tendency, first-stage F=156) can
   be estimated within the at-target band. If the IV estimate matches the OLS estimate, the
   collider-induced bias is small; if it diverges substantially, selection bias is material. Note:
   the at-target restriction may weaken the instrument (patients who the unit under-doses may not
   achieve target → different selection), so the IV is not guaranteed to be valid within the band.

**The single most important causal test needed: estimate dose→mortality in the never-at-target
stratum (failed-to-achieve or excess-MAP) and compare the OR to the at-target stratum. If the ORs
are similar, "occult dependence" survives. If the OR is only present within the at-target band
(as the collider model predicts), the finding is selection-artifact.**

---

## Issue 2 — CONFOUNDING BY INDICATION WITHIN AT-TARGET BAND

**Severity: CRITICAL | Status: PARTIALLY DISCLOSED (ICU_OCCULT_DEPENDENCE.md §Caveat 2,
CONFOUNDING_BY_INDICATION.md), but severity of the gap not quantified for at-target subgroup**

### What remains unadjusted

The at-target analysis adjusts only for age + lactate (n=2,590). CONFOUNDING_BY_INDICATION.md's
five-front defence (E-value ~6, 8/8 within-stratum strata, homogeneous restriction, propofol
negative control, IV OR 3.78) applies to the **full pressor cohort** (n≈23,925), not to the
at-target subsample (n=7,841; lactate complete n=2,590).

Within the at-target stratum, the confounding structure changes:
- By design, all patients have achieved adequate MAP. The high-dose patients within this band are
  the **vasoplegic/distributive shock phenotype** — specifically. This is a narrower indication
  cluster than the full pressor cohort.
- **Septic vasoplegic shock** requires high NEE to maintain MAP 65–85 and has mortality 25–40%
  independent of dose. This etiology is not captured by lactate alone. Lactate can be normal in
  early or fluid-resuscitated distributive shock while the vasoplegic requirement is high.
- **Missing confounders specifically relevant to at-target-high-dose:**
  - Vasoplegic phenotype / shock etiology (distributive, obstructive, cardiogenic) — absent
  - SOFA GCS (neurological severity) — absent (flagged in FINDING4_LANDMARK.md §S4)
  - PaO2/FiO2 ratio (respiratory failure severity) — absent
  - Duration of shock before ICU admission (time-to-target)
  - Concurrent steroid use (marker of refractory vasoplegic shock)
  - Fluid balance (vasoplegic shock often has high fluid requirement co-occurring with high dose)

### E-value for the at-target-band OR 2.59

Approximation: OR 2.59, baseline mortality ~12.4% → RR ≈ 2.0 (binary outcome with non-rare event,
OR overestimates RR). E-value for RR 2.0 = 2.0 + sqrt(2.0 × 1.0) = 3.4. For OR 2.59 using
the Zhang/Jurek formula directly, E-value ≈ 4.5.

However, this E-value applies to age+lactate-adjusted association. The **full-SOFA-adjusted E-value
(by analogy with FINDING4_LANDMARK.md OR 1.74 → E-value 2.1–2.3)** for the at-target-band will
likely be 2.0–2.5 after SOFA-lab adjustment. Given that vasoplegic etiology and GCS are the
remaining gaps, a confounder RR of ~2.0–2.3 on both dose and death is **plausible** (septic
vasoplegic shock RR vs non-septic at equivalent lactate is well within that range).

### Is the OR 2.59 "enough"?

The age+lactate adjustment is **weaker than the landmark's age+lactate+SOFA-labs+comorbidity**.
The at-target analysis does not have the equivalent of FINDING4_LANDMARK.md's fully-adjusted
OR 1.74. The finding as presented relies on an intermediate adjustment level. The 8/8 within-
severity strata (CONFOUNDING_BY_INDICATION.md) are from the full cohort — they have not been
reproduced within the at-target band.

**Assessment:** The confounding-by-indication attack is **not as strong a solo threat** as in
the un-conditioned setting (the propofol negative control and IV from CONFOUNDING_BY_INDICATION.md
collectively push the prior toward a real dose–mortality relationship). But the at-target analysis
has not inherited those defences — they were computed on the full cohort and have not been checked
for the at-target subsample. Within the at-target band, confounding by vasoplegic etiology
specifically is the live concern.

---

## Issue 3 — THE CONTROL-THEORY PREMISE IS TAUTOLOGICAL

**Severity: MODERATE | Status: NEW (not previously disclosed)**

### The claim

"MAP CV 0.125 << NEE-rate CV 0.44 confirms the control-theory premise: the hemodynamic insult is
carried by the dose, not the held-constant pressure."

### The tautology

This comparison is circular by construction of feedback control. Any regulated variable in a
closed-loop feedback system will have **lower variance than the controller output** — this is the
definition of regulation. It is not a finding; it is the **engineering identity**:

- In a feedback controller, the controller output must vary MORE than the plant output by
  mathematical necessity (if output were constant, no control signal would be needed).
- MAP is the regulated (plant output) variable; NEE rate is the controller effort (the input).
  The control law is: if MAP falls, increase dose; if MAP rises, decrease dose. This enforces
  that dose variance exceeds MAP variance whenever regulation is imperfect (i.e., always in
  an ICU patient).
- Demonstrating CV(dose) > CV(MAP) = 3.5× is not empirical confirmation of the control-theory
  framing; it is a logical consequence of the titration-to-target protocol itself.

The **intraop VitalDB confirmation** (CV ratio 5.2, now replicated in MIMIC at 3.5) is similarly
tautological: in both settings, a clinician is titrating a drug to achieve a pressure target; of
course the drug signal varies more than the regulated pressure.

### What the CV comparison does NOT establish

1. It does NOT confirm that the dose contains information about severity beyond what the pressure
   contains. A well-regulated thermostat has low temperature CV and high heater-duty-cycle CV; this
   tells you nothing about whether the duty cycle predicts tomorrow's temperature in the absence
   of the current temperature.

2. It does NOT confirm that the dose is a better risk-stratifier than pressure. That is what (B)
   and (C) show; (A) is the mechanical prerequisite, not the causal claim.

3. It does NOT distinguish between: (i) "the dose carries severity information that the pressure
   conceals" (the monitoring-error claim) and (ii) "the dose varies because the pressure is
   regulated, and both dose and mortality share the common cause of severity."

### What is informative vs circular

The CV comparison is **not useless** — it validates that the system IS operating in a
feedback-regulated regime (i.e., clinicians are actually targeting MAP, not ignoring it). Without
this check, one could not assume MAP is "near-constant by regulation" rather than "near-constant
because the patient is mild." The CV comparison is a **necessary but not sufficient** test for the
"regulated variable" interpretation.

**What would be non-circular:** showing that the dose predicts mortality **within the at-target
band** beyond severity, with appropriate causal adjustment — which is what (B) attempts. The
CV comparison in (A) should be framed as "validates the regulatory context" not as "confirms a
causal/information claim." The current phrasing in ICU_OCCULT_DEPENDENCE.md ("closes Round-1
causal Issue 1") overstates what (A) accomplishes causally.

---

## Issue 4 — ESTIMAND CLARITY AND "OCCULT DEPENDENCE" AS INTERPRETATION

**Severity: MODERATE | Status: NEW**

### What is the causal question?

The document does not state a formal estimand. There are at least three distinct causal questions
that "occult dependence" could refer to:

**Q1 (Prognostic):** Does knowledge of the vasopressor requirement, among patients with at-target
MAP, improve mortality prediction beyond what the clinician already knows from MAP?

**Q2 (Causal effect of dose on mortality):** Would randomizing to higher vs lower dose (holding
MAP at target via a titration protocol) change the probability of death?

**Q3 (Monitoring-error claim):** When a clinician observes a normal MAP and concludes low risk,
are they missing information that the requirement carries?

These are different estimands with different confounding structures:
- Q1 is purely prognostic/predictive; it does not require causal identification. The AUC 0.74
  within-band answers Q1, subject to the collider/overfitting caveat.
- Q2 requires causal identification (the IV in CONFOUNDING_BY_INDICATION.md approaches Q2 in the
  full cohort); Q2 within the at-target band is not estimated.
- Q3 requires Q1 PLUS an implicit structural assumption that the observed MAP is the only signal
  the clinician uses (not true — clinicians also see dose, trend, and severity labs).

### "Occult dependence" conflates Q1 and Q3

The phrase "the reassuring pressure conceals risk that lives in the controller effort" implies Q3
(the clinician is being misled by MAP). But the analysis establishes Q1 (the dose has predictive
value within the at-target band). Q1 does not entail Q3 unless one assumes clinicians do not
observe or integrate the dose — but dose is visible on every ICU monitor and integrated in VIS
scoring (cited in prior rounds as the overlap concern).

The "not VIS" defence (ICU_OCCULT_DEPENDENCE.md §Why novel) argues that VIS does not condition on
MAP being regulated. This is a correct distinction structurally, but the **information content**
claim (that dose adds over MAP within the at-target band) requires ruling out that VIS or similar
dose-aware severity scores are already capturing this. The AUC 0.74 vs 0.47 comparison is within-
band of MAP; it does not compare against "clinician's actual assessment including dose."

### Defensible vs indefensible language

- **Defensible:** "Among patients with at-target MAP, the vasopressor requirement is a stronger
  mortality predictor than MAP itself (AUC 0.74 vs 0.47), with a monotone 9× gradient across
  quartiles, after landmark design and age+lactate adjustment."
- **Not yet defensible without additional analysis:** "MAP conceals risk" (implies clinicians are
  not already dose-aware); "occult dependence" (implies the mechanism is the control-theory
  feedback structure rather than confounding by vasoplegic severity).

---

## Issue 5 — COMPLETE-CASE BIAS IN LACTATE-ADJUSTED ANALYSIS

**Severity: MODERATE | Status: DISCLOSED (ICU_OCCULT_DEPENDENCE.md §Caveat 3), quantified here**

The at-target band has n=7,841 total but lactate-adjusted n=2,590 (33% complete). In the full
landmark (FINDING4_LANDMARK.md), the 82% complete-case loss was flagged as requiring IPCW/multiple
imputation as the primary. The at-target-band complete-case rate (33%) is better but still
represents 67% missingness. Code in `analysis/icu_occult_dependence.py` line 253 (`lmask`)
selects records with non-None lactate with no weighting or imputation. The IPCW lesson from
FINDING4_LANDMARK.md has not been applied to the at-target analysis. If lactate missingness
is informative (e.g., sicker patients without lab draws), OR 2.59 is subject to the same
complete-case bias flagged in Round 1.

---

## Issue 6 — MAP SOURCE MIXING BIASES THE AT-TARGET DEFINITION

**Severity: MINOR | Status: DISCLOSED (ICU_OCCULT_DEPENDENCE.md §Caveat 5)**

The `_map_first24()` function (lines 71–85) prefers invasive ABPm/225312 if ≥3 readings, else falls
back to NBP. Patients who fall back to NBP are likely: (a) less invasively monitored, (b) less
severely ill, or (c) earlier in their admission. For the at-target claim specifically, this matters:
the regulation-to-target story is mechanically strongest for arterial-line patients (where the
clinician sees beat-to-beat feedback). NBP patients may have achieved "target" by different
dynamics. The invasive-only sensitivity analysis (promised in Caveat 5) is essential before the
"at-target-MAP-is-regulated" framing can be used causally.

---

## Issue 7 — AT-TARGET BAND DEFINITION IS A RESEARCHER DEGREE OF FREEDOM

**Severity: MINOR | Status: PARTIALLY DISCLOSED (ICU_OCCULT_DEPENDENCE.md §Caveat 4)**

The band [65, 85] and the <10% below-65 threshold are single choices with no pre-registration or
sensitivity analysis reported in the current document. The choice of the lower bound (65 = standard
MAP target for sepsis) and upper bound (85 = approximate upper physiological target) is clinically
motivated but not unique. Narrower bands reduce sample size; wider bands include patients not
"at target" in the regulatory sense. The reported n=7,841 is sensitive to these cutoffs, and the
quartile gradient (3.1% → 27.8%) may change substantially with band width. This is a standard
garden-of-forking-paths concern for a non-pre-registered exploratory analysis.

---

## Summary table

| # | Issue | Severity | New? | Core concern |
|---|---|---|---|---|
| 1 | Collider bias (conditioning on post-treatment MAP) | CRITICAL | NEW | At-target selection opens D–U collider path; OR 2.59 may partially reflect this |
| 2 | Confounding by indication in at-target band (vasoplegic etiology) | CRITICAL | PARTIALLY DISCLOSED | Age+lactate insufficient; no SOFA-lab/etiology adjustment for subgroup |
| 3 | MAP CV << dose CV is tautological (feedback control identity) | MODERATE | NEW | (A) is engineering truism, not causal confirmation; overstates what "closes Round-1 Issue 1" |
| 4 | Estimand ambiguity: "occult dependence" conflates predictive Q1 with monitoring-error Q3 | MODERATE | NEW | AUC 0.74 establishes Q1; Q3 requires showing clinicians lack dose visibility, which they don't |
| 5 | Complete-case bias in lactate-adjusted OR 2.59 (67% missing, no IPCW) | MODERATE | DISCLOSED | Same IPCW lesson from landmark not applied here |
| 6 | MAP source mixing (invasive/NBP) biases at-target definition | MINOR | DISCLOSED | Invasive-only sensitivity mandatory for the regulatory-feedback story |
| 7 | At-target band width is a researcher degree of freedom | MINOR | DISCLOSED | Sensitivity across bands needed; current choice is single unregistered |

---

## Verdict: Does the finding survive?

**Surviving core:** The monotone 9× gradient (3.1% → 27.8%) and AUC 0.74 for requirement within
the at-target band are real associations — not statistical artifacts, not reverse-causation
(landmark design), not a range-restriction artifact (those affect MAP's 0.47, not requirement's
0.74). The finding that **requirement is a stronger predictor than MAP within the at-target band**
is robust.

**Not surviving as stated:** The "occult" and "concealment" framing cannot be defended at the
causal level without:
(a) Ruling out collider artifact via the cross-stratum comparison (Issue 1 decisive test);
(b) Full severity adjustment (SOFA-labs + etiology) within the at-target band equivalent to what
    the landmark achieved (OR 1.74 level adjustment);
(c) Clarifying the estimand as predictive (Q1) rather than monitoring-error (Q3).

**The single most important causal test:** Estimate dose→mortality in the NOT-at-target stratum
(MAP < 65 or MAP > 85 throughout) and compare the OR to the at-target stratum (OR 2.59). If they
are similar, the collider-selection story fails and "occult dependence" gains ground. If the OR is
substantially higher only in the at-target band, the finding is likely a collider/selection
artifact rather than a genuine monitoring-error claim. This test is fully implementable with the
existing `analysis/icu_occult_dependence.py` infrastructure (change the band filter at line 244).

Cross-ref: `docs/ICU_OCCULT_DEPENDENCE.md`, `docs/FINDING4_LANDMARK.md`,
`docs/CONFOUNDING_BY_INDICATION.md`, `docs/RED_TEAM_ROUND2_SYNTHESIS.md`.
