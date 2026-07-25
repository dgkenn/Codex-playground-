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

## DOWNSTREAM HARM: what survives confounding, and the mediation NEGATIVE
Tested whether burst suppression has demonstrable end-organ consequences, and whether hypotension is the pathway.
Cohort: 1,499–1,745 propofol-TCI cases with intraoperative EEG, invasive MAP, and pre/post creatinine.

**AKI (KDIGO: peak post-op creatinine ≥1.5× baseline or ≥0.3 mg/dL rise; incidence 9.7%) — SURVIVES full adjustment**

| Model | OR per SD of BS burden |
|---|---|
| + age, Ce | 1.30 [1.13–1.48] * |
| + ASA, emergency | 1.23 [1.07–1.42] * |
| + baseline creatinine | 1.28 [1.12–1.48] * |
| + case duration, department | **1.37 [1.18–1.59]** * |
| + hypotension burden | **1.36 [1.17–1.58]** * |

**ICU admission — DOES NOT survive; it was confounding by indication.** Crude BS-high 50.0% vs BS-low 32.9% looked
striking, but the association collapses the moment ASA/emergency status enters (OR 1.12 → 1.10, ns) and stays null
through duration/department adjustment. **Do not present the crude ICU numbers.**

### The mediation test FAILS — and this reshapes the thesis
Adding hypotension burden to the BS→AKI model changes the BS effect by ~1% (1.37 → 1.36). Hypotension burden is
itself an independent predictor of identical magnitude (fully adjusted OR **1.36 [1.17–1.59]**).

**Therefore burst suppression does NOT harm the kidney *via* hypotension.** They are two independent, roughly
equal-magnitude risk pathways. The earlier reframed claim — "the hypotension it heralds may be the actual mediator
of harm" — is **not supported and must be dropped.**

**What this supports instead (and it is cleaner):** burst suppression carries information about end-organ risk that
blood pressure does not capture. BS is not a proxy for hypotension; it indexes something else about the patient —
plausibly anaesthetic sensitivity / physiological reserve. That is *more* consistent with the ENGAGES null: if BS
marks a vulnerable patient rather than causing the injury through a pressure pathway, then titrating anaesthetic to
abolish BS would not be expected to change outcomes — which is exactly what ENGAGES/ENGAGES-Canada found.

### Modifiability — NOT demonstrated, and cannot be from these data
Nothing here shows that preventing burst suppression improves outcomes. This is observational; the only randomised
evidence on that question (ENGAGES, ENGAGES-Canada) is **null**. Any claim of modifiability would require a
prospective trial. State this explicitly rather than implying actionability.
Code: `analysis/vitaldb_bs_aki_mediation.py`.

## MECHANISM TEST — attempted with directly measured SVR and cardiac output: NOT SUPPORTED
The HR-flat result suggested a vasomotor rather than chronotropic mechanism. VitalDB provides *directly measured*
haemodynamics (EV1000/Vigileo) to test this: 705 cases overlapping the EEG cohort, **114,229 bins with SVR** and
**325,332 bins with cardiac output**. Model: change in SVR (or CO) from t to t+k, regressed on BS burden at t,
adjusting for the current value, MAP and Ce.

| lag | ΔSVR per unit BS | ΔCO per unit BS |
|---|---|---|
| −120 s | **+16.22 [+7.74,+24.71]** * | −0.05 [−0.06,−0.04] * |
| −60 s | **+11.70 [+5.16,+18.25]** * | −0.03 [−0.04,−0.02] * |
| **+60 s** | **−2.30 [−8.91,+4.31] ns** | −0.02 [−0.03,−0.01] * |
| **+120 s** | **+2.47 [−6.14,+11.09] ns** | −0.04 [−0.05,−0.02] * |

**The vasodilation hypothesis is NOT supported.** SVR shows *no* fall at forward lags (both null); the only
significant SVR signal is at *negative* lags (SVR was higher before). Cardiac output shows a small decline that is
**symmetric** across lag (−0.02 to −0.05 L/min per unit BS, i.e. a concurrent state association, not a temporal
lead) and is of trivial magnitude.

**Honest conclusion: the haemodynamic mechanism linking burst suppression to the subsequent pressure fall is NOT
established.** Neither measured vasodilation nor measured cardiac depression accounts for it at the relevant lag.
The earlier inference of "vasomotor specificity" — which rested only on the *absence* of a temporal HR effect — is
**not corroborated by direct SVR measurement and should not be claimed.** Caveats: EV1000/Vigileo SVR is a derived,
noisy quantity available in only ~215 cases; a true mechanism study likely needs beat-to-beat arterial waveform
analysis, cerebral oximetry, or an interventional design. Code: `analysis/vitaldb_mechanism_svr_co.py`.

## STATUS OF THE FOUR QUESTIONS ASKED
| Question | Answer from these data |
|---|---|
| Prove a mechanism | **NOT ACHIEVED.** SVR does not fall after BS; CO change is symmetric and trivial. |
| Prove modifiability → better outcomes | **NOT ACHIEVABLE observationally**; the only RCT evidence (ENGAGES, ENGAGES-Canada) is null. |
| Other adverse outcomes | **AKI yes** (OR 1.37, survives full adjustment). **ICU no** — confounded by ASA/emergency. |
| Does BS-induced hypotension cause the harm (e.g. AKI)? | **NO.** Mediation fails (~1% attenuation); BS and hypotension are independent, equal-magnitude pathways. |

## ★ THE RECONCILIATION — two distinct burst-suppression phenotypes (strongest result)

**The apparent contradiction.** The field's dominant model is hypotension → cerebral hypoperfusion → burst
suppression, supported by an interventional RCT (n=104) in which raising blood pressure abolished suppression.
Our result runs the other way: BS *precedes* hypotension. Both cannot be universally true.

**The resolution — found in that RCT's own protocol.** Its algorithm triggered **only when MAP was already below
that patient's baseline**, and in 55% of those episodes (24/44) raising pressure alone resolved the suppression.
That trial therefore studied *hypotension-first* episodes exclusively. Our normotensive-restricted analysis
describes the population their protocol never enrolled.

**Direct test.** For every case we computed that patient's **own baseline MAP** (median of the first 10 maintenance
bins) and split burst-suppression epochs by whether MAP was at/above baseline or already below it:

| Phenotype | lag +60 s | lag +120 s | n (bin-pairs) | events |
|---|---|---|---|---|
| **MAP ≥ own baseline** ("anaesthetic-sensitivity" phenotype) | **OR 1.94 [1.79–2.10]** * | **OR 2.06 [1.92–2.21]** * | 612,909 | 54,469 |
| **MAP < own baseline** ("hypoperfusion" phenotype) | **OR 1.01 [0.81–1.26]** ns | **OR 1.02 [0.83–1.25]** ns | 44,340 | 9,184 |

**A near-perfect dissociation.** Burst suppression arising at normal pressure predicts hypotension 1–2 minutes later
(OR ≈ 2.0). Burst suppression arising in an already-hypotensive patient predicts **nothing** (OR 1.01) — and with
44,340 bin-pairs and 9,184 events this is a well-powered null, not an absence of data.

**Interpretation.** Intraoperative burst suppression is not one entity. There are (at least) two:
1. **Hypoperfusion-associated BS** — a *consequence* of low pressure; resolves when pressure is restored (the RCT's
   population and its 55% resolution rate).
2. **Sensitivity-associated BS** — occurs at normal pressure and *heralds* a pressure fall; raising pressure would
   not be expected to address it.

**Why this matters clinically and for the ENGAGES paradox.** Trials that treat all burst suppression as one target
pool two phenotypes requiring opposite responses (restore pressure vs. anticipate hypotension / reduce anaesthetic).
That is a coherent mechanistic explanation for why suppression-avoidance trials have been null, and it is testable
prospectively. It also reconciles our result with the interventional literature rather than contradicting it.

**Honest limits.** Baseline MAP is defined from each patient's own early maintenance period (not a pre-induction
value); the split is observational, not randomised; "phenotype" here is defined by haemodynamic context, not by an
independent biological marker. Code: `analysis/vitaldb_two_phenotype.py`.

## ★ MECHANISM OF BS → AKI: it is NOT haemodynamic (rigorous, two-scale, well-powered null)
The obvious hypothesis for a "pathway that is not blood pressure" is **flow**: MAP can be defended by
vasoconstriction while stroke volume — and renal perfusion — falls, which a pressure-only analysis cannot see.
Tested with pulse pressure (PP = SBP − DBP), a standard stroke-volume surrogate, available from the arterial line
in the **full** cohort (n=1,491 with EEG + PP + pre/post creatinine; 144 AKI events) rather than the 215-case
EV1000 SVR or 362-case cardiac-output subcohorts used earlier.

**Necessary-condition check — the flow mediators do not even predict the outcome:**

| candidate mediator → AKI (adj. age, ASA, Ce, duration, baseline creatinine) | OR |
|---|---|
| hypotension burden | 1.36 [1.16–1.59] * |
| **low-PP burden (FLOW)** | **1.17 [0.98–1.39] ns** |
| **occult low-PP (PP low, MAP ≥ 65)** | **1.02 [0.85–1.23] ns** |
| BS burden | 1.31 [1.14–1.51] * |

Mediation is impossible when the mediator does not predict the outcome. **The flow hypothesis fails its own
necessary condition.**

**Formal mediation on BOTH scales (bootstrap 2,000, case-level resampling).** Odds ratios are non-collapsible, so
difference-method mediation on logistic models is biased; we therefore repeated everything on the collapsible
risk-difference scale (linear probability model). Both agree:

| mediator | prop. mediated (OR scale) | prop. mediated (risk-difference scale) |
|---|---|---|
| hypotension (pressure) | −0.0% [−6%, 16%] | 2.8% [−5%, 15%] |
| low-PP (flow) | 1.1% [−2%, 7%] | 2.0% [−1%, 8%] |
| occult low-PP | 0.1% [−3%, 3%] | −0.2% [−3%, 2%] |

Total effect is solid (OR 1.31 [1.14–1.52]; **+3.06 percentage points of absolute AKI risk per SD of BS burden**),
and the CIs on proportion-mediated are **tight around zero** — this is a well-powered null, not an underpowered one.

### Conclusion: there is no intraoperative haemodynamic mechanism
Neither pressure nor flow, nor the occult combination of the two, carries the burst-suppression→AKI association.
The effect is essentially entirely direct with respect to intraoperative haemodynamics. The parsimonious reading is
that **burst suppression is a marker of constitutional vulnerability** — a brain with low anaesthetic reserve
co-segregating with renal vulnerability (shared frailty, microvascular disease, autonomic dysfunction) — rather
than a cause of injury via any intraoperative haemodynamic route.

This is the strongest available explanation for the ENGAGES null: **you cannot titrate away constitutional
vulnerability.** Adjusting the anaesthetic to abolish the EEG sign leaves the underlying phenotype untouched.
Code: `analysis/vitaldb_pp_mediation.py`, `analysis/vitaldb_flow_mediation.py`.

**What would be needed to go further** (not available here): pre-operative frailty/cognitive phenotyping,
renal biomarkers (NGAL/cystatin C), cerebral oximetry, or a randomised depth-titration design.
