# Burst suppression acts on the circulation as a distinct cortical state, not as anaesthetic depth

**VitalDB. Propofol: 1,859 cases extracted, 1,770–1,778 entering the models. Sevoflurane: 2,202 extracted,
1,645 entering the models.** (Extracted = cases with EEG and arterial pressure. Analysed = cases also passing
≥ 32 maintenance bins with anaesthetic concentration ≥ 1.0 and valid pressure at every required lag.)

> **Read Sections 5 and 6 first.** Two of three headline claims from an earlier draft are retracted, five
> pre-registered predictions failed, four analytic errors were found and corrected during the work, and an
> independent fact-check of an earlier version of *this document* found stale and cherry-picked figures which are
> corrected below. Effect sizes are small and stated plainly. Every figure cites the script that produced it.

---

## 1. The claim

Within the same patient, at the same arterial pressure and the same anaesthetic concentration, a 30-second epoch
containing burst suppression is followed 60–120 s later by a fall in mean arterial pressure that is **not**
preceded by an equivalent fall. The fall is **vasodilatory** — measured cardiac output *rises* while systemic
vascular resistance falls. It scales with **cumulative dwell time**, resolves within four minutes of the state
ending, and is **abolished when a vasopressor is running**. It is **specific to the suppressed state**: slow-delta
and frontal alpha power, the graded markers of anaesthetic depth, carry no lead at all.

The effect is small — **≈0.33 mmHg** per suppressed epoch, ≈0.85 mmHg at high occupancy — and it does **not**
increase time below any clinical hypotension threshold.

**Why it may matter:** it separates a *dynamical brain state* from *drug concentration* as the thing acting on the
circulation. The relevant prior work — microneurography showing propofol cuts muscle sympathetic nerve activity
76 ± 5 % — concerns the **drug at induction** in 10–20 subjects. This concerns the **state during maintenance**,
at fixed dose, within patient.

---

## 2. Evidence (propofol unless stated)

| finding | estimate | source | excludes |
|---|---|---|---|
| forward−backward asymmetry, ΔMAP | **−0.332** [−0.430, −0.229] | `vitaldb_calibrated_contrast` | a time-symmetric shared state |
| slow-delta power, same model | **+0.023** [−0.047, +0.085] **ns** | `vitaldb_eeg_specificity` | anaesthetic depth as the operative variable |
| frontal alpha, same model | **+0.004** [−0.065, +0.074] **ns** | same | as above |
| measured cardiac output (EV1000, 702 cases) | **+0.273 %** [+0.148, +0.425] | `vitaldb_measured_co` | myocardial depression (needs CO to *fall*) |
| systemic vascular resistance (214 cases) | −0.305 % [−0.646, +0.023] **ns** | same | — (computed *from* MAP; weak column) |
| **occupancy gradient** (suppressed bins in last 5 min) | −0.14 → −0.42 → −0.64 → −0.85; **−0.706** [−0.931, −0.481] | `vitaldb_duration_response` | an all-or-none phenomenon |
| **run-length gradient** | −0.31 → −0.44 → −0.56 → −0.65 → −0.70; **−0.388** [−0.590, −0.199] | same | a transition/onset effect |
| within-bin depth gradient | graded over 4 bands but **formally null** (+0.083 [−0.845, +0.916]) | `vitaldb_depth_response` | — **does not support the claim** |
| decay after the episode ends | −0.63 → −0.30 → −0.23 → **−0.07 ns** | `vitaldb_reversibility_autoreg` | a persistent patient trajectory |
| **asymmetry at MAP ≥ 90** | **−0.678** [−0.849, −0.518] | same | **reverse causation via cerebral hypoperfusion** |
| asymmetry at MAP < 70 | +0.116 [−0.061, +0.300] **ns** | same | — |
| **vasopressor interaction** | **+0.506** [+0.027, +1.099] — effect abolished | `vitaldb_mechanism_predictions` | a non-vascular route |
| frontal EMG negative control | **+0.568** — opposite sign on every haemodynamic column | `vitaldb_mechanism_decomposition` | a design artefact |
| pre-registered hold-out (random halves) | −0.313 vs −0.366, overlapping | `vitaldb_holdout` | overfitting to analytic choices |

**The autoregulation row is the strongest single result.** The field's standard rival — low pressure causes
suppression by reducing cerebral perfusion — *requires* the association to concentrate at low pressure. It is
largest at MAP ≥ 90, where autoregulation fully protects perfusion, and absent below 70, exactly where
hypoperfusion would begin.

### What the independent instrument actually showed
The BIS monitor's own suppression ratio reproduces the **pooled magnitude** (OR 1.15–1.16) but **not** the
forward-over-backward asymmetry (backward ORs 1.18–1.20 ≥ forward). There is a mechanical explanation — the BIS
suppression ratio is computed over a trailing ~63 s window, shifting its apparent timing backwards — but that
explanation was offered *after* seeing the result. It supports detector-independence of the association; it does
**not** independently confirm the precedence.

### Sevoflurane: the agents are NOT statistically distinguishable
Run separately on 1,645 sevoflurane cases, several tests are individually non-significant: no occupancy gradient,
no depth gradient, and the autoregulation result is ns at MAP ≥ 90 (−0.217 [−0.582, +0.089] vs propofol −0.678).
It would be easy — and wrong — to call the finding propofol-only on that basis.

Tested properly, by pooling both cohorts into one model with a drug-by-exposure interaction bootstrapped over
cases (1,153,858 bins, 3,421 cases):

| | estimate |
|---|---|
| propofol asymmetry | **−0.209** [−0.311, −0.104] * |
| **interaction (sevoflurane − propofol)** | **−0.064** [−0.251, +0.140] — **not distinguishable** |
| implied sevoflurane asymmetry | −0.272 |

**The agents do not differ.** Sevoflurane's separate non-significances reflect lower power and a much lower
exposure prevalence (suppression in 14.5 % of sevoflurane bins vs 42.0 % of propofol bins), not a smaller effect.
Every drug-class contrast made earlier in this project is therefore withdrawn and replaced by the pooled estimate.
This is the third appearance of the difference-of-significance error in this work, and the reason the interaction
test now exists. `vitaldb_drug_interaction`.

Caveat: dose is not comparable across agents (µg/mL vs %), so "adjusting for dose" means something different in
each arm; a supplementary run z-scoring dose within cohort is included in the same script.

---

## 3. Design

Within-case fixed effects (Frisch–Waugh–Lovell); adjusting for MAP(t), anaesthetic concentration, its rate of
change, and a pre-trend over [t−3k, t−2k]; rows restricted to bins holding both a forward and a backward
neighbour so direction is the only difference; **case-level cluster bootstrap** throughout (≈600,000 bins are
≈1,800 independent units). Arterial pressure filtered to a physiologic window [30, 150] mmHg. Burst suppression
detected from the **raw EEG** (0.1 s frames, peak-to-peak < 8 µV, runs ≥ 0.5 s), never from the proprietary index.

---

## 4. Pre-registered predictions that failed

| prediction | result | source |
|---|---|---|
| larger effect in the elderly | **null** — difference −0.155 [−0.417, +0.080] | `pred_fix` |
| larger effect at higher concentration | **null** — difference +0.018 [−0.186, +0.222] | `pred_fix` |
| the *transition* carries the signal | **refuted** — sustained exceeds onset | `vitaldb_onset_vs_sustained` |
| suppression blunts baroreflex gain | **null** — +0.0001 [−0.0044, +0.0045] | `vitaldb_baroreflex_gain` |
| suppression precedes an HRV fall | **null** — RMSSD +0.23 [−0.90, +1.42] | `vitaldb_hrv_withdrawal` |
| pressure *overshoots* after the episode | **failed** — decays to zero, no rebound | `vitaldb_reversibility_autoreg` |

**Correction to an earlier draft:** age and depth were previously reported as *significantly reversed*
(+0.718, +1.364). Those were pre-artefact-correction values. After filtering implausible pressures both are
**null**, and age's point estimate now runs in the originally predicted direction. Two hypotheses built on that
apparent moderator structure — a "residual tone" reinterpretation and a "transition" account — were therefore
**built on an artefact and are withdrawn**. The corrected picture is simpler: the effect is homogeneous across
age and dose.

The baroreflex null is uninformative: it used 30-second-averaged heart rate against 60-second pressure changes,
and the arterial baroreflex acts over one to three heartbeats. **That claim was retracted.**

---

## 5. What is NOT supported

1. **No clinical hypotension benefit.** The effect does not increase time below 65 mmHg; population attributable
   fraction **−5.8 %** [−11.5, −0.5] (propofol). This reconciles with the autoregulation result — suppression
   lowers pressure *from high starting points*, where a sub-millimetre shift never crosses a threshold. In
   sevoflurane the same analysis gives **+1.9 % [−1.8, +4.9] ns**, i.e. opposite in sign and null. **Any claim
   that this identifies a modifiable cause of clinically-defined intraoperative hypotension is unsupported.**
2. **The AKI association is confounded.** Suppression predicts renal injury robustly (+3.44 pp/SD KDIGO;
   **+3.89** on an absolute-rise definition that never divides by baseline, so not a denominator artefact). But it
   also "predicts" **pre-operative** creatinine (−0.226 mg/dL per SD) — causally impossible, so residual
   patient-level confounding is demonstrated. `vitaldb_aki_negative_control`.
3. **The hypotension-mediation of AKI is UNRESOLVED, not settled.** The case-level analysis gives ~44 %
   [18 %, 145 %] mediated by hypotensive minutes; the within-case analysis says suppression *reduces* hypotensive
   time. Between patients the a-path is **+8.20 min/SD**; within patient it is **−0.98 min**. Same data, opposite
   signs. Until reconciled, neither should be presented.
4. **The ageing story does not exist here.** Age raises suppression strongly (**+15.6 min/decade** at matched
   dose, confirming Purdon/Brown) but does **not** predict hypotensive minutes (+0.38 ns). Nothing to mediate.
5. **The sympathetic step is inferred, not measured.** Established for propofol by microneurography, but not
   measured by us. HRV indexes cardiac vagal control; sequence BRS was underpowered (5,839 bins, 145 cases).
   Mayer-wave (~0.1 Hz) power is the correct instrument; extraction in progress.
6. **The sub-minute temporal claim cannot be externally replicated.** A full survey (MIMIC-IV/III waveform, BDSP
   HEEDB / sah / I-CARE / PSG / ECG, UCLA MLORD) found **no** dataset pairing high-resolution EEG with continuous
   arterial pressure, and VitalDB has no third agent. Replication requires prospective collection.

---

## 6. Errors found and corrected during this work

1. **Arterial pressure was never range-filtered.** 4.27 % of MAP values ≤ 0 (minimum −78 mmHg), ΔMAP spanning
   −312 to +390 mmHg. **Every result was inflated ~3×.** Found because two scripts disagreed on row sets differing
   by 0.9 %. The cluster bootstrap did *not* catch it — it protects against correlated observations, not
   contaminated ones.
2. **The pre-trend shared an endpoint with the backward outcome** (partial correlation 0.528), inflating the
   asymmetry ~24 % one-sidedly.
3. **The two-phenotype dissociation was retracted** — as a formal interaction it is 1.08 [0.89, 1.32]; the
   original rested on strata differing 14-fold in size.
4. **The significance criterion is not calibrated** — the EMG negative control is non-null under all three
   estimators, so a shared-bootstrap contrast against it is reported alongside every raw estimate.
5. **This document's own earlier version** quoted pre-correction values for two predictions, cherry-picked a
   subgroup for the depth gradient whose primary analysis is null, overstated the independent-instrument result,
   and cited numbers produced by inline scripts that were never persisted. All corrected above; the AKI figures
   are now regenerated by a committed script.

---

## 7. What would most strengthen this

1. **Mayer-wave power** — the one available index of *vasomotor* sympathetic outflow. Would close the mechanism
   with our own measurement rather than by citation.
2. **The pooled drug-interaction test** — to state the propofol/sevoflurane contrast correctly rather than by
   comparing significance across separate analyses.
3. **A prospective cohort with simultaneous EEG and arterial line** — the only route to external replication.
4. **`SLOWING.pth` from MORGOTH 2** (now accessible) as an independent, foundation-model-derived slow-activity
   measure. The slow-delta *null* carries the specificity claim; reproducing it with an independent feature
   extractor would materially strengthen it.
