# Fluid-Responsiveness Research Program

Can we tell, without an invasive arterial line, who will respond to a fluid bolus vs who needs
vasopressors? A multi-dataset program (VitalDB, INSPIRE, MIMIC-IV) designed around the two threats
that doom naive ICU-EHR approaches — **no stroke-volume ground truth** and **confounding by
indication** — with every claim pre-registered, negative-controlled, and hostile-red-teamed.

**Bottom line:** this is a rigorous, honest **de-hyping** of the fluid-responsiveness biomarker on
retrospective data. No cheap non-invasive signal (ECG, MAP, preop labs) reliably predicts fluid
response; the widely-used "objective" MIMIC continuous-CO label is itself too noisy to be ground
truth. Several results are clean, defensible negatives; the trait-vs-state question is genuinely
undetermined. The value is in what these negatives rule out and the methodological cautions they raise.

---

## Results (post-red-team)

### 1. VitalDB — ECG carries no standalone non-invasive fluid-responsiveness signal (under GA) — **SOLID NULL**

The only label-valid substrate: FloTrac device SVV (940 cases, 2 s cadence) + 500 Hz ECG/pleth
waveforms. Cohort 160 cases / 7,369 ventilation-gated windows (arrhythmia/open-chest/spontaneous
excluded). Predict SVV (regression) and SVV≥13% (binary) from **non-invasive features only** (never
arterial-derived — that would be circular).

| Model | AUROC | CCC |
|-------|-------|-----|
| M0 clinical/preop | 0.618 | 0.132 |
| ECG-alone | 0.632 | 0.205 |
| Pleth-PVI-alone | **0.733** | 0.338 |
| ECG + pleth | 0.738 | 0.353 |

Two pre-registered tests, both decisive:
- **Increment (ECG on top of pleth): null** — ΔAUROC +0.005 [−0.007, +0.019].
- **Equivalence/substitution (ECG-alone vs pleth-alone): REJECTED** — Δ = **−0.100 [−0.138, −0.061]**,
  well outside a ±0.03 margin (not underpowered). And ECG-alone − M0 = +0.014 [−0.011, +0.043]
  (≈ clinical baseline). ECG and pleth are **uncorrelated at the feature level** (|r|≤0.17), and ECG
  shows **no rescue in the pleth-failure zone** (low perfusion: both collapse to chance together).

**Claim:** *Under general anesthesia, ECG-derived respiratory features provide neither an increment to
nor a substitute for a pleth-derived PVI in predicting SVV — ECG-alone performs at clinical baseline.*
Mechanistically coherent (GA suppresses respiratory sinus arrhythmia → the ECG respiratory modulation
pleth relies on isn't there). **Bounded caveat:** null is specific to GA; in awake/spontaneous
breathing RSA is intact — but SVV/PVI aren't valid there anyway. A pleth-PVI-only surrogate works
modestly (0.73) but merely re-derives PVI and targets device SVV (an unvalidated surrogate; see §4).

### 2. ΔMAP is a poor bedside proxy for measured CO response — **SURVIVES (practical form, softened)**

MIMIC-IV advanced-monitoring subset, 383 vasopressor-clean bolus events with a continuous-CO (CCO,
itemid 224842, ≥2 readings/window) ΔCO label.
- ΔMAP↔ΔCO Pearson **0.095**; **AUROC of ΔMAP for the true ΔCO≥10% responder = 0.56**; when MAP rises
  ≥10%, only 30% actually raised CO (PPV 30%); MAP misses ~20% of true responders. No static predictor
  (MAP/PP/HR/shock index) beats AUROC 0.5.

**Red-team correction:** ΔMAP's own reliability is only ~13%, and ΔCO's is ~0% (see §4), so the
*disattenuated* correlation is unidentifiable (plausibly anywhere from ~0 to ~0.7). Therefore the
**mechanistic** claim ("MAP physiologically doesn't track CO") is undecidable here. What survives is
the **practical** claim: *against the same noisy CO monitor clinicians actually rely on, bedside ΔMAP
cannot identify fluid responders (AUROC 0.56) — do not trust ΔMAP-based responder labeling* — bounded
to this high-acuity, continuous-CO-monitored ~4% subgroup.

### 3. Is fluid-responsiveness a stable phenotype or a transient state? — **UNDETERMINED** (was reported as "state"; red-team downgraded)

- MAP-based (5,612 boluses, RTM-corrected, negative controls pass): within-episode ICC 0.126
  (shuffle-validated as real, →0.0008 on permutation); **cross-encounter ICC −0.046 at n=74
  (underpowered)**; 73% of the raw bedside "response" is regression to the mean (corrected ΔMAP only
  +1.46 mmHg).
- CCO-based (true ΔCO): within-episode ICC **−0.06** — but the red-team's matched no-bolus noise floor
  shows CCO swings **SD 14.2%, ≥10%-crossing 21.4%** with *no bolus at all*, statistically
  indistinguishable from the 24.5% post-bolus responder rate (p≈0.49). An ICC≈0 from a label with ~0%
  test-retest reliability cannot distinguish trait, state, or no-signal. Cross-encounter cell = **n=0**.

**Honest claim:** *Whether fluid-responsiveness is trait-like or state-like is undetermined from this
data — measurement noise fully accounts for the observed within-episode variability, and no
between-encounter data exists to test trait stability.* (Not "state"; "not established.")

### 4. The MIMIC "objective" continuous-CO label is too noisy to be ground truth — **cautionary methods result**

The keystone red-team finding: matched no-bolus CCO windows (same geometry, same stays) have
variance ≥ the post-bolus windows (F=1.14 favoring the noise floor) → implied CCO Δ-measurement
reliability ≈ **0%**. Intermittent nurse/thermodilution/trending-lag charting makes MIMIC's CO
label unusable as a fluid-response ground truth at this resolution. VitalDB's objective label was
valid (2 s FloTrac; pre-bolus SVV→ΔSV AUROC 0.814) but **not scalable** — routine boluses aren't
electronically timestamped (only 15 rapid-infuser cases; n≈4 with ECG+pleth). *No accessible dataset
supplies both scalable timestamped boluses and a reliable SV-response label.*

### 5. INSPIRE — preop labs add little to intraop-instability prediction — **MODEST/NULL**

121,163 non-cardiac cases. Severe instability (continuous pressor / MAP<55, 6.4%) AUROC **0.808**;
routine (any pressor / MAP<65, 48.3%) 0.734; both well-calibrated. But **preop labs add only +0.017
AUROC** over structural variables (anesthesia type, ASA, age, department). Associational (confounding
by indication; dose-less pressor events). *Routinely-available preop labs carry only a weak
independent instability signal.*

---

## What the program establishes

- **ECG is not a non-invasive fluid-responsiveness signal under GA** (solid, pre-registered null;
  equivalence rejected). Closes a genuine white space.
- **No cheap bedside proxy works:** ΔMAP (0.56, practical), static vitals (≈0.5), preop labs (+0.017).
- **The MIMIC continuous-CO label is unreliable as FR ground truth** (~0% test-retest) — a caution for
  the many studies that use it.
- **Trait-vs-state is genuinely undetermined** on available data.
- **Data gap:** no accessible cohort has scalable timestamped boluses + a reliable SV-response label —
  the field's core obstacle, made concrete.

## Methodological lessons (also in `../LESSONS.md`)

1. **Compute the label's OWN noise floor before interpreting an ICC or a proxy-AUROC.** A matched
   no-bolus window set with identical geometry is the test. Here it converted "fluid response is a
   state" and "ΔMAP is near-useless (mechanistically)" into "undetermined" and "practical-only." An
   ICC≈0 from a ~0%-reliability label is not evidence of anything.
2. **"No increment" ≠ "no signal."** Always test the standalone/equivalence model (ECG-alone), not just
   the increment — they answer different questions. (Here it sharpened an ambiguous null into a
   definitive World-A null.)
3. **Separate mechanistic from practical claims** when both the exposure and the label are noisy —
   disattenuation is often unidentifiable, but the practical "clinicians can't use X against the
   label they have" claim can still stand.
4. **Match the substrate to the label problem:** VitalDB has SV truth but no bolus timing; MIMIC has
   boluses but a noisy CO label; neither alone closes it.

## Artifacts (scratchpad, gitignored)
`vitaldb_fr_label.py`, `vitaldb_fr_model.py`, `vitaldb_ecg_equivalence.py`, `fr_features.csv`,
`mimic_objective_fr_label.py`, `mimic_realSV_analysis.py`, `mimic_fr_trait_state.py`,
`redteam_noisefloor.py`, `inspire_preop_instability.py`.
