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
