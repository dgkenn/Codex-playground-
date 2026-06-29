# ROUND 3 — Final hostile-review completeness audit (harshest pass)

Third and final adversarial round. Prior two rounds (HOSTILE_REVIEW_SURVIVAL.md,
CONSTRUCT_AND_COMPLETENESS.md) fixed most holes. This round (A) re-audits every
SURVIVES verdict for *flaws in how it was tested*, (B) hunts genuinely new
conclusion-changing holes, (C) writes the single most damaging Reviewer-2
paragraph and our best rebuttal, (D) renders a convergence verdict.

All numeric claims below were re-derived directly from the live caches and raw
MIMIC tables (scratchpad probes `sel_check.py`, `vaso_check.py`), not read from
prose.

---

## A. AUDIT OF EACH "SURVIVES" VERDICT — sound or flawed-in-how-it-was-tested?

### A0. The headline lactate/SOFA complete-case selection (attack #16) — THE decisive one

**Concern:** the lactate+SOFA-lab adjustment (OR 3.80 -> 2.44) is COMPLETE-CASE
(only the n=3,109 norepi stays with first-24h lactate+creatinine+bilirubin+platelets
all measured). Complete-case selects sicker / more-worked-up patients. Does that
selection bias the "beyond severity" OR, and is n=3,109 safe?

**Re-derived directly (scratchpad/sel_check.py, current caches):**

| Set | n | mortality | age-adj requirement OR |
|---|---|---|---|
| FULL norepi cohort | 15,949 | 0.330 | **3.798** |
| lab-COMPLETE (4 SOFA labs in 24h) | 3,111 | 0.373 | **3.804** |
| lab-INCOMPLETE | 12,838 | 0.319 | **3.748** |

**Verdict A0: the selection is REAL but does NOT bias the conclusion — SOUND, with one honest caveat.**
- Yes, lab-complete patients are sicker (mortality 0.373 vs 0.319) and more
  worked-up (lactate is ordered in shock). The selection exists.
- BUT the quantity being adjusted — the requirement->mortality OR — is **3.80 in
  the selected subset, identical to 3.80 in the full cohort and 3.75 in the
  un-selected complement.** The selection shifts the *base rate*, not the
  *requirement effect*. So the 3.80 -> 2.44 attenuation is measured on a starting
  OR that matches the whole cohort; the "beyond severity" reading is not an
  artefact of having picked a weird subset.
- This is the right framing the doc should state explicitly (it currently does
  not): **"the age-adjusted requirement OR is 3.80 in the lab-complete subset,
  equal to the full-cohort 3.80, so the lab-adjusted attenuation is not driven by
  complete-case selection."** That one sentence closes the attack.
- Residual honest caveat: lab-complete patients are enriched for shock, so the
  lab covariates have more variance to absorb there than they would in the
  lab-incomplete group; the *attenuation* could be modestly larger in the sickest
  stratum than it would be cohort-wide. Direction of the conclusion is unaffected
  (OR stays ~2.4-3.0, CI lower bound 1.90).

**Still-open factual point (not a flaw in the test, a freshness flag):** the
labevents download is **still in progress** (1.12 GB of ~2.4 GB and actively
growing at audit time); the n=3,109 is a ~46% subject-sorted subsample. The doc's
top-line "PRELIMINARY (subsample)" banner is honest and current. The full-data
re-run is still owed; the CI margin [1.90, 3.22] is wide and the point estimate
may move. **Do not drop the PRELIMINARY banner until the 2.4 GB download finishes
and the JSON is regenerated.**

### A1. The #vasopressors adjustment — is "survives severity" circular or conservative?

**Concern:** the dose-response severity adjustment and the lactate model both
include `#distinct vasopressors`, which is partly ON the causal path (needing a
2nd/3rd pressor *is* a higher requirement / refractory shock). Does conditioning
on it make the survival circular?

**Re-derived (scratchpad/vaso_check.py, n=3,109):**
- requirement vs #vaso: Spearman **+0.456** (they are genuinely entangled — #vaso
  is a coarse restatement of "needs more pressor").
- OR with labs + comorbidity but **NO #vaso**: **2.97**
- OR FULL (+ #vaso): **2.44**

**Verdict A1: the #vaso adjustment is CONSERVATIVE (over-adjustment toward the
null), not circular-inflating — SOUND, and the survival is understated.** #vaso
sits on the mediator side: it partially *is* the exposure. Including it can only
push the OR DOWN, so the fact that the OR survives even with it (2.44) is a
*lower* bound; the cleaner non-mediator estimate (labs + comorbidity only) is
**2.97**. Nothing about including #vaso manufactures a positive result — the
opposite. The honest headline is "beyond lactate+SOFA-labs, OR is 2.4-3.0
depending on whether the partial-mediator #vaso is held." This should be stated;
right now the docs report only the over-adjusted 2.44 and under-credit themselves.

### A2. The MIMIC "replication" two-level honesty (attack #4 / #12)

**Concern:** does every doc now honestly say MIMIC replicates the *dose-ordering
trait*, not the MAP-conditioned controller-effort estimand or the control-theory
mechanism?

**Verdict A2: MOSTLY honest, with two residual over-claims — FLAWED-IN-PLACES.**
- CONSTRUCT_AND_COMPLETENESS.md (Section A) and HOSTILE_REVIEW_SURVIVAL row #12
  state the two-level claim correctly and explicitly.
- BUT the **abstract-level summary still drifts**: HOSTILE_REVIEW_SURVIVAL's
  opening claim box says "externally replicated (INSPIRE OR + MIMIC-IV ICU)" and
  MIMIC_EXTERNAL_VALIDATION.md's verdict says "strong generalisation of the
  requirement concept" without the "this is the coarse dose-intensity summary, NOT
  the MAP-conditioned estimand, and the control-theory premise is NOT tested in
  MIMIC" qualifier inline. A reviewer reading only those two files would conclude
  the specific phenotype replicated. The qualifier lives in
  CONSTRUCT_AND_COMPLETENESS.md but is not carried into the headline docs.
- **This is a framing-honesty debt, not a data error.** Fix: paste the two-level
  sentence into the abstract box and into MIMIC_EXTERNAL_VALIDATION.md's verdict.

### A3. Autocorrelation / reliability (attack #5) — sound

ICC(1)=0.392, time-gapped early->late survives to >=12 h (0.42) and decays to 0.30
at >=24 h, shuffle-null ~0, holds in high-within-stay-CV subset (0.35). The test
design is correct: the time-gap is the decisive control and it is run. **SOUND.**
Minor: the gap>=24h subset is itself a longer-stay selection (disclosed). Not
conclusion-changing.

### A4. Immortal-time (attack #11) — sound

Landmark (alive at h6 -> post-6h death) is a proper fix using a real death
timestamp; early-peak OR 1.73 -> 1.54, AUC 0.668 -> 0.652, signal survives. The
test is methodologically correct. **SOUND.** The naive early-warning OR is
correctly flagged as modestly optimistic.

### A5. Multiplicity (attack #1) — sound for the primary, stale count for secondaries

Re-checked: the primary MIMIC statistics have Fisher-z of **84** (early->late) and
**210** (reliability) — p-values underflow to 0; they survive Bonferroni over
*thousands* of tests. The severity-adjusted OR 2.44 has CI lower bound 1.90; a
Bonferroni-widened CI stays above 1. **The primary is multiplicity-immune.** The
*secondary* count (13 subgroups, 5 severity specs, 3 horizons, 5 formulations, 2
thresholds, escalation/slope) is NOT in any formal correction, but none of those
are the headline. **SOUND for the claim that matters; the secondary
exploration must be labelled exploratory** (see B3).

### A6. Dose-response gradient beyond severity (attack #15) — sound

g-computation standardization (correct for non-collapsible logistic), monotone
after full adjustment (Q1 0.18 -> Q4 0.57, RR 3.27), trend p ~1e-277. Method is
right; the #vaso-driven attenuation is correctly localised. **SOUND** (and per A1
the #vaso piece is conservative).

### A7. Code-audit SURVIVES (attack #10) — sound

The five-module audit found the real bugs (degenerate tone column, circular
+0.69, wrong-sign SVR, in-sample operating point), all relabeled/retracted; no
conclusion-flipping bug remains. Spot-checked: `map_dia_form_factor` survives in
code ONLY inside modules that correctly identify it as the degenerate constant and
switch to `diastolic_over_map`. No live headline depends on it. **SOUND.**

---

## B. RANKED NEW HOLES (not in round 1/2)

| # | Hole | Severity | Fatal / disclosable |
|---|------|----------|---------------------|
| B1 | **Confounding by indication (the dose reflects a treatment DECISION, not only physiology).** Every adjustment conditions on severity *scores*; none can remove that the clinician chose the dose. Two patients with identical physiology but different practice cultures (permissive-hypotension vs aggressive-MAP-target unit) get different doses, and the unit/culture is correlated with case-mix and with mortality. This is distinct from "severity confounding" (which the labs partly handle) — it is confounding by the *treatment-assignment process itself*, unaddressable without randomization. The MIMIC subgroup heterogeneity (CVICU OR 4.1 vs SICU OR 2.7) is *consistent* with practice-culture variation in what dose marks. | MODERATE | **Disclosable** (it scopes to "marks risk, not a treatment effect" — already the stance) but currently UN-NAMED. Add it explicitly: the requirement is dose = physiology x local-titration-practice; the practice component is a confounder no severity score removes. |
| B2 | **Long-term (dod) competing risks + the in-hospital headline should be primary.** 90d/1y ORs (1.78/1.52) treat death as the only event; the dod date-shift cancels in differences (valid) but beyond-horizon deaths are censored-as-alive and there is no competing-risk handling. This is minor BECAUSE the clean, censoring-free, date-shift-free headline already exists: in-hospital mortality Q1 0.14 -> Q4 0.65, CA trend p=0. | MINOR | **Disclosable** — already mostly handled. Promote the in-hospital dose-response to the primary outcome; demote dod to supportive. |
| B3 | **Multiplicity statement is stale for the secondary MIMIC surface (researcher DoF).** The "one primary survives Bonferroni(~30 tests)" predates ~25 added MIMIC tests. The primary is immune (B/A5), but the *confident "SURVIVES" tone on secondaries* (13 subgroups all positive, "best formulation," bedside thresholds) is exploratory and reads confirmatory. | MODERATE | **Disclosable by framing.** Declare ONE pre-specified MIMIC primary; label the rest exploratory corroboration. Effect sizes are large enough this costs nothing. |
| B4 | **Reliability and the prognostic claim share the same whole-stay window (window overlap).** Split-half reliability uses odd/even segments of the *whole stay*; the requirement->mortality OR uses the *whole-stay median*. These are the same data window. Reliability is a measurement property (legitimate), but a reviewer could note the prognostic OR is NOT a prospective early measure — that role is filled by the separately-landmarked first-6h analysis (OR 1.54). The whole-stay OR 3.8 is partly an *outcome-contemporaneous* exposure (the dying patient's dose was escalated). | MODERATE | **Disclosable** and largely already separated. State plainly: the OR 3.8 is a *characterization* (contemporaneous), the OR 1.54 (landmarked first-6h) is the *prospective/early* number. Do not let 3.8 stand in for early prediction. |
| B5 | **VitalDB between-patient phenotype depends on an unverified constant norepi-concentration assumption (units).** The VitalDB dose is device mL/h/kg; the entire between-patient "5.6-fold spread" + all construct/outcome correlations assume a constant institutional concentration. Split-half reliability is concentration-invariant *within* a case, but the between-patient ranking is not. | MINOR-MODERATE | **Disclosable** — already noted in CONSTRUCT_AND_COMPLETENESS A.3 but under-weighted given it touches the core VitalDB phenotype. Keep MIMIC (true mcg/kg/min) as the unit-clean anchor for between-patient claims. |
| B6 | **No data-quality degeneracy of the map_dia_form_factor kind remains in a live headline.** Checked: the degenerate column is quarantined; the requirement metric is a plain median of a physiologic rate. No new constant/degenerate column found behind a live claim. | — (clean) | n/a |

**No NEW CRITICAL (fatal) hole found.** The closest candidates (B1 confounding-by-indication,
B4 window-overlap) are real and currently under-named, but both are *scoping*
limitations of an explicitly observational, risk-stratification claim — they do
not flip the conclusion, they bound it.

---

## C. THE STEELMAN — Reviewer 2's single most damaging paragraph, and our rebuttal

> **Reviewer 2 (the paragraph we have not fully rebutted):** "The authors present
> the vasopressor dose-requirement as a patient signal that stratifies mortality
> *beyond severity*, but their own decisive test concedes nearly half the effect
> (48.6% attenuation, OR 3.80 -> 2.44) and is computed on a 38-46% complete-case
> subsample whose download was unfinished at submission. More fundamentally, the
> exposure is not a patient property — it is a *clinical decision*. The dose a
> patient receives is jointly determined by their physiology AND the titrating
> clinician's local practice (MAP target, permissive-hypotension culture, pressor
> preference), and that practice component is correlated with case-mix and unit
> and therefore with death. No lab panel removes confounding by the
> treatment-assignment process; the across-ICU heterogeneity (CVICU OR 4.1 vs
> SICU OR 2.7) is exactly what practice-driven confounding predicts. The
> 'beyond-severity' residual the authors celebrate is indistinguishable from
> 'beyond the *measured* severity, but inside the unmeasured treatment-decision
> process.' What remains, once you strip the control-theory framing (verified
> intraoperatively only, never in the ICU cohort that carries the large-N
> mortality result) and the vasoplegia label (retracted), is the long-known fact
> that norepinephrine dose tracks mortality — repackaged with a mechanistic story
> the data cannot support in the setting where the outcome was measured."

**Our best rebuttal (honest, partial):**
1. **The "half the effect attenuates" point cuts the other way.** A severity
   marker that survived adjustment for lactate (the shock gold standard) + the
   SOFA lab components with OR 2.44 [1.90, 3.22] and an independent +0.029 AUC is
   doing more than restating APACHE; pure severity-proxies collapse to ~1. And the
   #vaso term in that model is a partial *mediator* — drop it and the OR is **2.97**.
   The honest residual is OR 2.4-3.0, lower bound 1.90.
2. **The complete-case selection does not bias the effect** (Section A0): the
   age-adjusted OR is 3.80 in the lab-complete subset, equal to the full cohort —
   selection moves the base rate, not the requirement effect.
3. **Confounding by indication (B1) is conceded, not rebutted.** We CANNOT remove
   the treatment-decision component observationally. Our defense is scope, not
   refutation: the claim is risk-stratification ("marks the patient who will need
   sustained support and is more likely to die"), explicitly NOT a treatment
   effect, and the decision-benefit test was run and is NULL (we disclose it). The
   control-theory framing is scoped to intraoperative VitalDB and is NOT claimed to
   carry the ICU mortality result.
4. **What genuinely survives the steelman:** a *reliable* (0.95), *early-
   identifiable* (landmarked first-6h OR 1.54), *drug-agnostic*, *dose-graded*
   (monotone Q1 0.14 -> Q4 0.65), *severity-adjusted-positive* (OR 2.4-3.0 beyond
   lactate+SOFA), *externally-consistent* (VitalDB + INSPIRE + MIMIC, rank-level)
   prognostic signal. That is a defensible characterization/risk-stratification
   paper. It is NOT a practice-changer, NOT a proven mechanism in the ICU, NOT a
   demonstrated treatment target — and we say so.

**The steelman does not kill the paper; it correctly caps it.** The one sentence
we have NOT been saying and must — "the residual is beyond *measured* severity but
inside the unmeasured treatment-decision process" — is a disclosure, not a
retraction.

---

## D. VERDICT

**Are there any CRITICAL unaddressed holes? — NONE.**

The single item that was CRITICAL in round 2 (the lactate+SOFA-lab adjustment
being built-but-never-run) **has now been run** and **survived**: OR 3.80 -> 2.44
[1.90, 3.22] beyond lactate + SOFA labs, +0.029 AUC, and (newly shown here) **2.97
without the partial-mediator #vaso term**. The complete-case selection that the
round-2 doc worried about does **not** bias the effect (age-adj OR 3.80 in the
lab-complete subset = 3.80 full cohort). The remaining open item is *freshness*,
not *validity*: the labevents download is still finishing, so the number is a
~46% subsample carrying an honest "PRELIMINARY" banner and a wide CI; the full-run
may shift the point estimate but the CI lower bound (1.90) and the
selection-invariance make a collapse-to-null implausible.

**The work has CONVERGED.** Every SURVIVES verdict is sound in *how* it was tested
(A2's two-level-claim drift is a framing debt, not a test flaw). No new fatal hole
exists. What remains is a cluster of **disclosable limitations**, three of which
are currently UNDER-NAMED and should be written down before submission:

1. **Confounding by indication** (B1) — name it explicitly: dose = physiology x
   local titration practice; the practice component is an unremovable confounder.
2. **Window overlap** (B4) — the whole-stay OR 3.8 is a contemporaneous
   characterization; the prospective/early number is the landmarked first-6h OR
   1.54. Do not conflate.
3. **Two-level replication drift** (A2) — carry the "dose-ordering trait
   replicates, MAP-conditioned estimand + control-theory mechanism do NOT" sentence
   into the abstract and MIMIC_EXTERNAL_VALIDATION.md.

Plus the already-known disclosures: PRELIMINARY lactate subsample banner (keep
until full download), multiplicity-on-secondaries framing (B3), in-sample
thresholds, intraoperative-only mechanism, observational/no-causal-claim, selected
A-line/on-pressor denominator, VitalDB unit assumption (B5).

**Bottom line:** this is now a strong, honest **risk-stratification /
characterization** paper. The central empirical claim — *the early/ICU
vasopressor dose-requirement stratifies mortality with a clean dose-response,
beyond comorbidity AND beyond lactate+SOFA-labs (OR 2.4-3.0), externally
consistent at the rank level, grounded in a control-theory framing shown
intraoperatively* — **stands, scoped.** No CRITICAL hole remains; only
disclosable limitations, and the highest-value remaining action is mechanical
(finish the labevents download and regenerate the lactate JSON), not conceptual.

_Audit re-derived from live caches via scratchpad/sel_check.py and vaso_check.py;
labevents download confirmed still in progress (1.12 GB / ~2.4 GB) at audit time._
