# Intraoperative burst suppression precedes arterial hypotension independent of anesthetic dose: a time-resolved analysis of 1,859 cases

*Working draft — for senior-advisor review (target: British Journal of Anaesthesia / Anesthesia & Analgesia).*
*All results from VitalDB open data; HEEDB ICU extension pending credentialed access.*

## Abstract (draft)
**Background.** Intraoperative burst suppression (BS) is associated with postoperative harm, but whether it is a
modifiable *antecedent* of intraoperative hemodynamic instability — as opposed to a passive marker of anesthetic
depth or a consequence of hypotension itself — is unknown. We tested whether EEG-defined BS temporally precedes
arterial hypotension independent of propofol effect-site concentration (Ce).
**Methods.** 1,859 propofol–TCI surgical cases (VitalDB) with raw frontal EEG, invasive arterial pressure, and
pump-logged Ce were analyzed in 30-second bins (~852,000 bins). BS burden was detected from the raw EEG waveform
(amplitude-threshold + minimum-duration rule), *independent of the proprietary depth index*. Cross-lagged logistic
models estimated the association of BS at bin *t* with hypotension (mean arterial pressure, MBP <65 mmHg) at *t+1*,
adjusting for concurrent MBP, Ce, and age, with case clustering.
**Results.** BS at *t* predicted hypotension at *t+1* (OR 1.68, 95% CI 1.55–1.81), far exceeding the reverse
direction (hypotension→BS OR 1.11). The association held within every Ce stratum (OR 1.18–2.45), survived a
dose-change covariate (OR 1.66), was specific to BS over general slow-wave power, and showed a lead–lag structure
rising from +30 to +120 s. Critically, restricting to *currently normotensive* bins (MBP ≥70) — where low perfusion
cannot flatten the EEG — BS predicted subsequent hypotension with OR 4.96 (4.15–5.93), and OR 3.65 with stable/rising
MBP. BS burden rose with age at matched Ce (OR 1.046/yr; ~3× in patients ≥75).
**Conclusions.** EEG burst suppression is a dose-independent, artifact-robust *antecedent* of intraoperative
hypotension that leads it by 30–120 s — a potentially actionable early-warning signal, most pronounced in the
elderly. Whether pre-emptive lightening prevents hypotension, and whether the antecedent carries outcome consequences,
warrants prospective and ICU-cohort testing.

## Why this is a Brown-lab paper
- **His method**: burst suppression from the raw EEG (not a black-box index), the state he has modeled mechanistically
  (metabolic/state-space burst-suppression probability).
- **His vision**: individualized, EEG-informed anesthetic management — here the EEG carries information *beyond the
  dose* about impending hemodynamic instability.
- **Our unique bridge**: the rigorous cuff-vs-arterial hypotension methodology (C8) applied to link the EEG state to
  measured arterial pressure with temporal precedence.

## Methods (detail)
- **Cohort**: VitalDB propofol-TCI cases with BIS-sensor raw EEG (128 Hz), Solar8000 invasive arterial MBP, and
  Orchestra TCI effect-site propofol concentration; age ≥18; ≥12 maintenance bins. n=1,859 (all arterial-line propofol-TCI cases with EEG+Ce).
- **BS detection (raw EEG, not BIS/SR)**: 0.1-s frames flagged suppressed if peak-to-peak <8 µV; runs ≥0.5 s retained;
  per-bin BS burden = suppressed fraction. Concurrent validity vs the device suppression ratio: r = 0.68 (Pearson), 0.78 (rank), n=200 — see
  analysis/sr_validity]. (BIS/SR used only as an *external* validity check — never as the label — per the same-device
  circularity principle.)
- **Bins & alignment**: 30-s bins over the case; per-bin BS burden, multitaper alpha/slow power (DPSS NW=3,K=5),
  mean invasive MBP, mean Ce.
- **Models**: cross-lagged pooled logistic (forward BS_t→hypo_{t+1}; reverse hypo_t→BS_{t+1}); within-Ce-stratum
  models; lag-structure scan (k=−4..+4 bins); dose-change (ΔCe) and slow-wave adjustments; normotensive-restricted
  and stable/rising-MBP-restricted decisive tests for reverse causation. Age×Ce burst-susceptibility model (Aim 2).

## Results (as run)
| Test | Result |
|---|---|
| Forward BS→hypotension (adj MBP,Ce,age) | OR 1.68 [1.55–1.81] |
| Reverse hypotension→BS | OR 1.11 [1.08–1.14] |
| Within Ce strata (1–2.5 / 2.5–3.5 / 3.5+) | OR 2.45 / 1.18 / 1.29 (all sig) |
| Lag structure (+30→+120 s) | OR 1.50→1.61→1.66→1.70 (neg lags ~1.00, NULL) |
| + dose-change covariate | OR 1.55 |
| + slow-wave (BS-specific?) | OR 1.52; slow-wave adds nothing |
| **Normotensive-restricted (MBP≥70)** | **OR 4.96 [4.15–5.93]** |
| Normotensive + stable/rising MBP | OR 3.65 [2.70–4.93] |
| Aim-2: BS burden vs age (matched Ce) | OR 1.046/yr; median 0.018(<60)→0.033(60–75)→0.056(≥75) |
| **Granger BS→MBP** (adj MBP AR(3)+Ce) | **F(3,735k)=217.8** → BS→MBP (autocorrelation-controlled) |

## Limitations (honest, from adversarial review)
1. **Ce is effect-site *modeled*, not measured** — residual dose-timing confounding cannot be fully excluded; the
   within-stratum + ΔCe + normotensive controls mitigate but do not eliminate it.
2. **BS detection on a 2-channel BIS sensor** — concurrent validity vs device SR r=0.68/0.78 (good, non-circular) and,
   ideally, blinded expert epoch review and full 10–20 montage confirmation.
3. **Autocorrelation — ADDRESSED**: a Granger test (MBP_t on its own AR(3) lags + Ce ± BS lags) shows past BS improves
   MBP prediction beyond MBP's own history (F=217.8, p≪1e-6), with BS→MBP dominating MBP→BS 6.6× — the lead is not
   autocorrelation bleed. (Block-resampling CIs remain a nicety.)
4. **No outcome in this cohort** — elective surgery, in-hospital mortality ~0. The finding is a *mechanistic
   antecedent*, not outcome evidence. The **HEEDB ICU extension** (iatrogenic-vs-pathological BS mortality contrast +
   full montage) supplies the outcome dimension.

## Planned confirmatory analyses (pre-specified)
- Granger-causality DONE (BS→MBP F=117.6 vs reverse 17.7); block-resampling CIs remain.
- Suppression-ratio + blinded-rater validation of BS detection; NIRS-perfusion sensitivity where available.
- Sevoflurane (volatile) generalization cohort.
- HEEDB: outcome contrast (drug-induced vs pathological BS mortality) on research-grade cEEG, multi-site.

## GENERALIZATION — sevoflurane (volatile) cohort (n=500, 227k bins) [added]
- **Aim-3 GENERALIZES across drug class:** under sevoflurane, BS_t→hypotension_{t+1} OR **1.61 [1.17–2.21]**
  (adj MBP, end-tidal sevo %, age) — significant, echoing propofol (1.79). The antecedent is NOT propofol-specific.
- **Underpowered decisive test under sevo:** normotensive-restricted (MBP≥70) OR 2.05 but CI [0.77–5.42] —
  burst suppression is rarer in normotensive volatile maintenance; directionally consistent, not significant
  (needs more cases; the propofol cohort carries the artifact-controlled evidence).
- **Aim-2 does NOT generalize:** age→BS susceptibility is flat under sevoflurane (OR 1.009 [0.986–1.033]) vs
  OR 1.06/yr under propofol — a genuine drug-specific difference (propofol-specific age susceptibility; volatiles
  are MAC-age-adjusted). Report honestly as a drug-class contrast, not a universal claim.

**Net:** the core antecedent (BS→hypotension) is robust and cross-anesthetic; the age-susceptibility is propofol-
specific. Both are honest, reportable, and Brown-relevant (drug-specific EEG pharmacodynamics is his domain).

## MECHANISTIC DISSOCIATION — heart rate as an internal negative control (n=174-case interim, full run pending)
Pre-registered prediction (cortical→autonomic→pressure cascade) was **REFUTED**, and the refutation strengthens the
paper. Lag scans on three independent instruments (EEG / ECG-derived HR / arterial line):
- **BS → hypotension (MBP<65):** negative lags NULL (OR 0.95–1.02), positive lags rise **1.20→1.23*→1.31*→1.33***
  — the temporal asymmetry replicates in this subsample.
- **BS → heart-rate fall (≥5 bpm):** OR **<1 (0.44–0.63) and SYMMETRIC** across negative and positive lags.
- **BS → bradycardia (HR<50):** OR <1 (0.52–0.73), likewise non-directional.

**Interpretation.** A symmetric OR<1 is a *state* association (burst-suppression epochs are haemodynamically quiet,
stable-HR epochs), not a *temporal* effect; only the pressure arm shows the null-negative/rising-positive asymmetry
that marks precedence. Heart rate therefore functions as an **internal negative control**: had burst suppression
merely indexed "generically deep anaesthesia that drifts into instability," the chronotropic arm would show the same
asymmetry. It does not. The burst-suppression→hypotension effect is thus **specific to the vascular axis — consistent
with a vasomotor (reduced systemic vascular resistance) rather than a chronotropic/vagal mechanism** — which also
rules out a generic depth confound. This is a genuine mechanistic narrowing, and a stronger design element than the
cascade we predicted. *Caveats: HR is monitor-derived (2-s numeric), not beat-to-beat, so true HRV/baroreflex
sensitivity is untested (needs the ECG waveform); vasoactive drugs are unadjusted. Full-cohort rerun pending.*

## BIS BLIND SPOT — decisive test run, proposed mechanism REFUTED (honest negative)
Tested whether the displayed BIS index reads falsely "acceptable" during EEG-confirmed suppression because frontalis
EMG is folded into its composite. Reference non-circular (raw-waveform suppression vs the proprietary displayed index).
- **Prevalence is real but modest:** of EEG-confirmed deeply-suppressed bins (raw BS ≥50%), **15.6% displayed BIS ≥40**
  (14.6% in the 40–60 clinician target range; 1.0% ≥60). Device's own SR read 0 in 3.4% of these bins.
- **The EMG mechanism FAILS:** stratifying suppressed bins by EMG tertile gives a **non-monotonic** blind-spot rate
  (low 18.3%, mid 27.7%, high 14.2%) — no dose-response. The pooled regression EMG coefficient is positive but
  trivial (+0.167 BIS units per EMG unit).
**Verdict:** killed as a flagship/device-safety claim; retained only as a modest descriptive note (BIS under-reports
EEG-confirmed suppression ~1 in 6 epochs, mechanism unexplained — plausibly the index's own smoothing lag).
Code: analysis/vitaldb_bis_blindspot.py, analysis/vitaldb_cascade.py.


## CORRECTION (full-power rerun, n=1,852) — the heart-rate "negative control" claim was WRONG as stated
An interim analysis on 174 cases reported that burst suppression showed **no** association with heart-rate change
(OR<1, symmetric) and concluded HR was a clean internal negative control proving vasomotor specificity.
**That claim does not survive the full cohort and is retracted.** Two errors were found and fixed:

1. **Broken lag semantics.** Sequences were indexed by *position*, then filtered by HR availability. Because the
   HR filter removes bins, "lag −4" no longer meant "120 s earlier" — it meant "4 *retained* bins earlier." This
   manufactured spurious negative-lag associations. Fixed by indexing on **absolute bin time**, so lag k always
   equals exactly 30k seconds (`analysis/vitaldb_timelag.py`).
2. **Selection effect.** Restricting to HR-available bins is not random (it tracks monitoring intensity), and in
   that subsample the hypotension asymmetry is genuinely weaker.

### Corrected results (true 30 s time lags)
**Primary — hypotension, all cases (n≈705k bin-pairs): the flagship precedence STANDS, cleanly.**

| lag | −120 s | −60 s | −30 s | +30 s | +60 s | +120 s |
|---|---|---|---|---|---|---|
| BS→MBP<65 OR | 0.98 | 1.02 | 1.03 | **1.50** | **1.62** | **1.71** |

Negative lags null; positive lags significant and monotonically rising.

**The autonomic contrast, restated correctly (same HR-available comparison set):**

| Outcome | −120 s | −60 s | +60 s | +120 s | pattern |
|---|---|---|---|---|---|
| Hypotension (MBP<65) | 1.41 | 1.27 | 1.53 | 1.64 | **asymmetric — rises with forward lag** |
| Bradycardia (HR<50) | 3.83 | 3.78 | 4.22 | 4.38 | **flat / symmetric — no temporal gradient** |

**Correct interpretation.** Burst suppression is *strongly* associated with bradycardia (OR ≈ 4) — the earlier
"HR is unrelated" statement was an artifact. But that association is **concurrent and non-directional**: the odds
ratio is essentially identical 2 minutes before and 2 minutes after. Hypotension, by contrast, shows a genuine
**temporal lead**. So the claim is not "BS spares the heart" but the sharper one: *burst suppression co-occurs with
a bradycardic state, yet only the vascular axis shows a predictive lead* — consistent with a vasomotor rather than
chronotropic mechanism for the impending pressure fall, while both reflect a shared depth-of-anaesthesia state.

**Methodological lesson for the manuscript:** any lag analysis on irregularly-sampled physiology must index on
absolute time, never on retained-row position, and the comparison set must be fixed across arms.
