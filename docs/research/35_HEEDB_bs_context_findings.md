# HEEDB discovery arm — burst suppression is a marker of its CAUSE, not intrinsically lethal

*Run on credentialed HEEDB/BDSP (S0001 + S0002, two independent Harvard-affiliated hospitals).*
*De-identified aggregate results only; no PII stored, printed, or committed.*

## Cohort
338,725 EEG recordings across 5 sites; mortality linkage (`DateOfDeath`) available at **S0001 + S0002**.
After restricting to adults (≥18) with a dated EEG and de-duplicating to one index EEG per patient:
- **S0001 (discovery): 28,178 patients**, 2,763 deaths ≤30 d (9.8%)
- **S0002 (validation): 14,844 patients**, 1,244 deaths ≤30 d (8.4%)
- **43,022 patients total.** Burst suppression (`bs`) is a clinician-labeled report finding: 2,813 (10.0%) and
  1,828 (12.3%) respectively.

## Result 1 — burst suppression is a large, independent mortality signal (replicated)
| Model (30-day mortality) | S0001 | S0002 |
|---|---|---|
| BS alone | OR 4.81 [4.38–5.29] | OR 5.43 [4.78–6.17] |
| + age, sex | OR 5.05 | OR 5.97 |
| **+ generalized slowing (severity anchor) + age, sex** | **OR 5.03 [4.56–5.54]** | **OR 5.94 [5.20–6.78]** |
| + seizure, GPD, LPD, focal slowing + age, sex | OR 4.44 | OR 4.43 |
| *generalized slowing, same model* | *OR 0.94 [0.85–1.04] — **null*** | *OR 0.90 [0.79–1.03] — **null*** |

**The severity confound that killed earlier attempts does not explain this.** Generalized slowing — the canonical
encephalopathy-severity marker, present in 68–77% of patients — is itself **null** for mortality and does not
attenuate the BS effect at all (5.05 → 5.03; 5.97 → 5.94).

## Result 2 (the wedge) — the SAME EEG state carries 0% to 38% mortality depending on context
| Recording context | S0001 BS mortality | S0002 BS mortality |
|---|---|---|
| **OR** (intraoperative) | **0.0%** (n=124) | — |
| **EMU** (epilepsy monitoring, elective) | **0.0%** (n=78) | **0.0%** (n=95) |
| Routine outpatient/inpatient EEG | 14.4% (n=759) | 11.9% (n=571) |
| **LTM** (ICU continuous EEG) | **37.7%** (n=1,852) | **35.0%** (n=1,096) |

Identical clinician-labeled burst suppression ranges from **zero** mortality in anesthetic/elective settings to
**~36%** in ICU continuous monitoring, replicated across two hospitals. This is the direct evidence that burst
suppression **indexes its cause rather than causing death** — and it independently corroborates the VitalDB flagship,
where 1,859 elective propofol cases showed abundant burst suppression with ~zero mortality.

## Honest negatives (recorded, not buried)
- **The ICD-10 proxy for "pathological" FAILED.** Splitting BS patients by cerebrovascular ICD burden gave
  *lower* mortality in the "pathological" arm (24.5% vs 29.6%; within-BS OR 0.66 [0.53–0.82]). Reason: the
  cerebrovascular category captures **stroke/TIA** (I63.9, G45.9), not the anoxic/post-arrest injury that actually
  drives lethal burst suppression. The ICD category set has no anoxic-injury field, so *context* (service) is the
  better — and objective — discriminator. Do not report the ICD split as the mechanism.
- **`HEEDB_Medication_ATC.csv` is ATC level-1 only** ("Nervous System Drugs"), so specific sedative identity
  (propofol / midazolam / pentobarbital) is **not** available. "Iatrogenic" is therefore inferred from recording
  context, not from measured drug exposure. This is the single biggest design limitation.
- **Negative controls are imperfect.** `pdr` (normal posterior rhythm) OR 0.18/0.34 and benign variants
  (wicket/breach/BETS) OR 0.53/0.61 are both *protective*, not null — because essentially every EEG feature
  correlates with patient acuity. A truly null EEG control may not exist in this design; report the gradient
  (benign < normal-ish < BS) rather than claiming a clean null.
- Service context is a **proxy for cause**, not randomization; sicker patients get ICU cEEG by definition. The claim
  is that context identifies cause, not that context is exogenous.

## Combined two-database thesis (the paper)
1. **VitalDB (OR, n=1,859 / 852k bins):** burst suppression *precedes* arterial hypotension, independent of propofol
   Ce, artifact-controlled, Granger-confirmed, and **specific to the vascular axis** (heart rate, an internal negative
   control, shows no temporal asymmetry) → BS has a genuine *physiological* consequence even in healthy patients.
2. **HEEDB (clinical/ICU, n=43,022, 2 hospitals):** burst suppression carries a 5–6× mortality signal that survives
   severity adjustment — **but is entirely context-dependent (0% OR/EMU → ~36% ICU LTM)**.
3. **Synthesis:** burst suppression is a *marker of its cause*. In the operating room it flags hemodynamic
   vulnerability; in the ICU it flags catastrophic brain injury. The blanket "avoid burst suppression" framing
   conflates two states with the same waveform and opposite prognoses — which plausibly explains why
   burst-suppression-guided interventions (e.g. ENGAGES) have not produced the expected mortality benefit.

## Next steps
- Anoxic-injury identification via EEG report text / OMOP diagnoses (the ICD category set is insufficient).
- Duration/burden of BS from the raw BIDS signals (currently label-level only) — enables dose–response.
- Add I0002/I0003/I0009 sites (no `DateOfDeath` there; use them for prevalence/context replication only).
- Adversarial red-team of the context-as-cause inference before drafting.
Code: `analysis/heedb_bs_mortality.py`, `analysis/heedb_bs_iatrogenic.py`.
