# Fluid-Responsiveness Research Program (scoping + first results)

Predicting who will respond to a fluid bolus vs who needs vasopressors — intentionally
designed around the two things that doom naive ICU-EHR approaches: **no stroke-volume ground
truth** and **confounding by indication**. This document captures the scoping (multi-dataset
feasibility + rigorous designs), the results completed so far, and the resumable plan.

**Status (2026-07-03):** scoping complete; MIMIC "trait vs state" complete (a rigorous null);
VitalDB objective-label gate complete; three heavier builds (VitalDB non-invasive model,
INSPIRE preop model, MIMIC objective-SV-label probe) were **interrupted by a session limit**
and are queued for resumption — partial progress noted below.

---

## 1. The problem structure (why intentionality matters)

- **No ground-truth label in general EHR.** MIMIC/eICU/INSPIRE lack continuous SV/CO for the
  general cohort; any responsiveness label is a MAP/lactate proxy (confounded; saturated with
  regression-to-the-mean). The validated AUC ceiling (~0.82–0.85) exists *only* in cohorts with a
  real SV label (echo/pulse-contour). (Lit scout, 14 PubMed-verified refs incl. Marik CVP
  PMID 18628220; PLR meta PMID 26825952; FENICE PMID 26162676; CLASSIC 35709019; CLOVERS 36688507.)
- **PPV/SVV applicability collapses** — valid only under controlled MV, sinus rhythm, TV≥8, closed
  chest (a minority of real ICU patients).
- **Confounding by indication** caps the causal fluid-vs-pressor decision at ~OR 1.35 (our
  structural ceiling); preference-IV fails its exclusion restriction (our instrument sim).
- **Novelty white space:** pleth→SVV is solved (that's PVI, AUC 0.82–0.88); **ECG→SVV is unmined**;
  and a **cross-encounter reproducibility (trait vs state) test** of fluid response is unpublished.

## 2. Dataset roles (feasibility-audited)

| Dataset | Has SV/SVV truth? | Role |
|---------|:---:|------|
| **VitalDB** | ✅ FloTrac SVV/SV (940 cases, 2 s cadence) + 500 Hz ECG/pleth | **Only substrate to build/validate a non-invasive surrogate** |
| **INSPIRE** | ❌ (5-min vitals, no waveforms/ECG/SVV) | Large-N (130k) **preop-labs → intraop instability** + fluid→AKI |
| **MIMIC-IV** | ❌ general (hourly MAP, no waveform); ⚠️ tiny PiCCO subset has SV/CO | "trait vs state" (MAP proxy); possible objective-label subset (probe pending) |
| **eICU** | ❌ | Other-population external clinical arm |

VitalDB access is free/open (urllib+gzip or `vitaldb` pkg); INSPIRE via `wget --netrc` (plain CSV);
MIMIC boluses in local `inputevents.csv.gz` (NaCl 225158, LR 225828, `ordercategorydescription=='Bolus'`).

---

## 3. RESULT — MIMIC "trait vs state": fluid-responsiveness is a transient STATE, not a phenotype

**Design.** Within-patient repeated-bolus, RTM-corrected against matched no-bolus counterfactuals;
cross-encounter test is the trait discriminator (per our vasopressor-trait-collapse lesson).
Script: `scratchpad/mimic_fr_trait_state.py`.

**Cohort funnel.** 157,101 crystalloid boluses → 115,918 with arterial MAP → 80,133 ≥250 mL →
45,300 with usable windows → 12,542 during hypotension → **5,612 after co-intervention censoring**
(3,740 subjects, 3,815 episodes).

**Headline — RTM dominates.** Raw ΔMAP after bolus **+8.26 mmHg**; matched no-bolus control windows
drift **+6.02** on their own → **corrected response +1.46 mmHg** (median −0.28). **≈73% of the
bedside "fluid response" is regression to the mean, not fluid.**

**Trait vs state.**

| Test | Value | 95% CI | Reading |
|------|-------|--------|---------|
| Within-episode ICC (1,114 episodes ≥2 boluses) | **0.126** | [0.076, 0.176] | modest, real |
| **Cross-encounter ICC** (74 subjects, separate admissions) | **−0.046** | [−0.225, 0.139] | **≈0 — does not reproduce** |

**Physiologic falsification (Frank–Starling): FAILS.** Corrected response vs bolus order flat
(+0.093, z=0.69); vs cumulative volume **rises** (+0.76 mmHg/L, z=3.03) — anti-Starling, the
pre-specified red flag that the corrected label still carries artifact (consistent with state/noise).

**Negative controls (both PASS).** Shuffle bolus→patient pairing collapses ICC **0.126 → 0.0008**
(genuine within-episode signal); placebo-timing on held-out no-bolus windows = **+0.028 mmHg**
(z=1.01, RTM correction is unbiased — doesn't manufacture a response).

**Verdict: STATE, not phenotype.** Modest within-admission reproducibility (ICC 0.13) that vanishes
across a patient's separate ICU admissions (ICC ≈ 0). Novel framing (0 prior cross-encounter work),
rigorous (both NCs pass), and a clean de-hyping message: *at routine EHR MAP resolution, ICU
fluid-responsiveness does not behave as a reproducible patient trait — most of the apparent bedside
response is regression to the mean.*

**Honest limits.** MAP-response ≠ SV-response; hourly MAP is coarse; arterial-line cohort is
sicker/selected; cross-encounter cell underpowered (n=74). This is why the MIMIC objective-SV-label
probe matters — a real SV label could confirm or overturn the null. **Pending red-team** (queued).

---

## 4. RESULT — VitalDB objective-label gate: valid but not scalable → hybrid design

**Finding.** The objective label (measured **ΔSV ≥10–15% after a real bolus**, FloTrac SV at 2 s
cadence) is **scientifically valid** — positive control: pre-bolus device SVV predicts the ΔSV≥10%
label at **AUROC 0.814**, exactly as physiology requires. Script: `scratchpad/vitaldb_fr_label.py`.

**But routine boluses are not electronically timestamped in VitalDB** (given by pressure-bag/gravity;
only whole-case crystalloid/colloid *totals* exist). Timestamped delivered volume exists for **15
cases** via the `FMS/TOTAL_VOL` rapid-infuser track — all massive-transfusion cases (atypical), giving
**n≈4** usable cases with ECG+pleth. Too few to train.

**Hybrid design (adopted):** train the non-invasive surrogate on the **device-SVV target** (871 cases
with FloTrac SVV + ECG_II + PLETH), predicting SVV/FR-state from **non-invasive ECG+pleth only**
(non-circular — never feed arterial-derived features); use the ~15–19 objective ΔSV boluses as a
held-out **gold-standard anchor**. Headline = the pre-registered **ECG-increment-over-pleth-PVI test**
(M2 vs M1). Honest prior: the ECG increment is likely small under general anesthesia (RSA suppressed);
a null is publishable ("PVI suffices; ECG adds nothing under GA").

---

## 5. Queued / interrupted (resume after session-limit reset)

| Task | State at interrupt | Resumable |
|------|--------------------|-----------|
| **VitalDB Phase-2 non-invasive model** (`scratchpad/vitaldb_fr_model.py`) | benchmarking waveform-load cost; no results | yes — windowed 30–60 s ECG/pleth features at SVV timestamps, ~150–200 cases first, M0→M3 nested, ΔAUROC(M2/M1) headline, validity-gated |
| **INSPIRE preop-labs instability model** (`scratchpad/inspire_preop_instability.py`) | labs downloaded (18M rows); vitals streaming | yes — preop labs+demographics → intraop vasopressor/hypotension; case-split CV; associational framing |
| **MIMIC objective-SV-label probe** (`scratchpad/mimic_objective_fr_label.py`) | chartevents extraction running | yes — count PiCCO/PA-catheter subset with SV/CO + bolus overlap; pilot ΔSV-after-bolus label; if scalable, RE-RUN trait-vs-state with a real SV label |

**Next actions on resume:** (1) finish the MIMIC objective-label probe — it settles whether the
trait-vs-state null holds under a real SV label; (2) finish the VitalDB non-invasive model (the
ECG-increment headline); (3) finish INSPIRE; (4) red-team the MIMIC trait-vs-state null and any
VitalDB/INSPIRE winner; (5) fold into this doc + ledger.

## 6. Honest program-level read

The rigorous, defensible contributions here are **not** a high fluid-responsiveness AUC (the label
isn't there at scale). They are: (a) the **trait-vs-state de-hyping result** (done, MIMIC); (b) the
**ECG-beyond-PVI question** on the only label-valid substrate (VitalDB, pending); and (c) an honest
**preop-labs-at-scale** associational model (INSPIRE, pending). Each is designed so a null is itself
a publishable, mechanism-backed finding — the disciplined stance for a domain where our track record
and the label problem both argue against an easy positive.
