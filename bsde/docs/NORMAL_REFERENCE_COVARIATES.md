# What to control for in the normal reference — the exhaustive pass

*Written 2026-07-31. Every count below is measured on the 4,944 strict-normal HEEDB recordings, not
assumed. A frozen reference inherits every uncontrolled confound permanently, so this is the step where
being thorough is cheapest.*

---

## The structural point: these are four different jobs, not one covariate list

Lumping everything into "adjust for it" is the mistake to avoid. Each variable belongs in exactly one of:

| bucket | what it means | why it is not the others |
|---|---|---|
| **RESTRICT** | exclude it from the reference | some states are not "normal with a modifier" — they are a different measurement |
| **CONDITION** | put it in the reference model | legitimate biological variation the reference should expect |
| **HARMONISE** | remove it at source | technical artefacts should be eliminated, not modelled — adjusting for them bakes them in |
| **REFUSE** | must not enter | ethical constraint, and in one case also the scientifically correct call |

Getting a variable into the wrong bucket is worse than omitting it. Conditioning on a technical artefact
makes the reference depend on the scanner; restricting on something biological shrinks generalisability
for no gain.

---

## 1. The finding that reshapes the whole design: vigilance cannot be handled by exclusion

**4,688 of 4,944 strict-normal recordings (94.8 %) carry sleep markers** — `n1`, `n2`, `spindles`,
`k_complexes` or `vertex wave`. Only **202** are marked awake with no sleep marker at all; 54 are marked
neither.

This is the largest effect on the list and it is not close. The aperiodic exponent differs between wake and
N2 by more than any comorbidity will — the prior work's own landmarks put N2 at −3.5 SD and N3 at −5.2 SD
against an awake centre of 0. **A reference built from whole recordings is a reference to "clinical EEG
including however much sleep the patient happened to have", which is not a normative object at all.**

Excluding sleep-containing recordings would take the cohort from 4,944 to **202** and select hard for short,
alert, probably anxious patients. That is not viable.

> **Consequence: vigilance must be resolved WITHIN the recording, not between recordings.** The reference
> is built from awake segments detected in-signal, and the recording-level `awake`/`n1`/`n2` flags are
> useful only as a coarse check on that detection — they mark what the recording *contains*, not when.
> This is a RESTRICT applied at the segment level, and it has to be built before anything else is.

An honest secondary consequence: whatever wake-detector is used becomes part of the frozen reference's
definition, so it must be specified, versioned and hashed exactly like a candidate.

## 2. Medication — the covariate the sleep-lab reference never had, and it is nearly universal here

`HEEDB_Medication_ATC.csv` gives ATC level-1 chapters per patient. **4,393 of 4,944 (88.9 %) have
"Nervous System Drugs" populated.**

Benzodiazepines augment beta and directly flatten the high-frequency end of the slope; antiepileptics,
antipsychotics and sedatives all modify the spectrum. **A normal *read* does not mean an undrugged brain** —
a neurophysiologist reading "normal" is not asserting the absence of pharmacological beta.

Three things must be said about this table rather than glossed:

* it is **per patient, not per visit** — "ever prescribed" rather than "on board during this recording", so
  it is a blunt instrument and will misclassify in both directions;
* 88.9 % prevalence among people who received an EEG is unsurprising and means it cannot be an exclusion;
* it is **ATC chapter level**, so "Nervous System Drugs" pools a benzodiazepine with a paracetamol.

→ **CONDITION on it**, and run the **551 patients with no nervous-system drug** as a sensitivity arm. If
the reference moves materially between the two, the medication term is doing real work and the limitation
above becomes the leading caveat rather than a footnote.

## 3. Service type — restrict, because it is acquisition and population at once

| service | n |
|---|---|
| **Routine** | **4,192** |
| Faulkner | 507 |
| LTM | 152 |
| EMU | 92 |
| Fish | 1 |

`LTM` and `EMU` are long-term monitoring — an epilepsy-workup population, different electrode application,
different durations, different environments. `Faulkner` is a different hospital.

→ **RESTRICT to `Routine` (4,192).** A normative reference wants the most standardised acquisition
available, and routine outpatient EEG is it. Report the others as a held-out consistency check rather than
folding them in: if the Routine-derived reference does not describe LTM normals, that is worth knowing and
is invisible if they are pooled.

## 4. HARMONISE, not adjust — the technical variables that directly distort a slope

**These matter more than any comorbidity and are the easiest to get wrong**, because a spectral slope is
exactly the quantity a filter chain corrupts.

* **Anti-alias filter and sampling rate.** A fit to 45 Hz is meaningless if the recording was acquired at
  200 Hz with a 70 Hz low-pass — the rolloff sits inside the fit range and steepens the slope by an amount
  that has nothing to do with the brain. **Read `sfreq` and the filter settings from every EDF header and
  either stratify or restrict.** This is the single most likely source of a spurious site difference.
* **Notch filter.** A 60 Hz notch has skirts reaching well below 60. If the fit range approaches it, the
  notch is in the fit.
* **Reference montage.** Average reference, linked ears and Cz reference give different spectra. Must be
  fixed, not adjusted.
* **High-pass at acquisition.** A 1 Hz HPF distorts the low end of a 0.5 Hz fit.
* **EMG contamination.** Flattens the high-frequency end — the exact direction that mimics wakefulness or
  ketamine. `emg_index`, `emg_beta_gamma_fraction` and `emg_kurtosis` are already registered here and E39
  used them; they should gate segment inclusion, not enter the model.
* **Line-noise power and impedance**, where derivable.

→ **All of these are RESTRICT or HARMONISE.** Conditioning on them would make the frozen reference depend
on the amplifier, which defeats the purpose — the reference has to be portable to a new hospital's
hardware, and it can only be that if hardware effects were removed rather than absorbed.

**Site (S0001 vs S0002 vs I0002 vs I0003) belongs here too, and there is a tension worth naming.** The
project's standing constraint forbids using hospital identity as a shortcut. Using site to *remove
equipment differences* is legitimate measurement practice; using it as a *covariate* risks encoding "this
hospital's patients differ" as though it were biology. → **Measure the site effect, report it, and remove
it as a technical artefact. Do not condition on it.** If a site difference survives filter and montage
harmonisation, that is a finding about the data, not a term to absorb it.

## 5. CONDITION — the reference model itself

* **Age, non-linearly.** The aperiodic exponent's age dependence is well documented and is not a straight
  line; the cohort spans **0–90 with median 41 and IQR 23–61**, which is wide enough to fit it and wide
  enough that a linear term would be actively wrong. Natural spline or declared age bands, **specified
  before the fit**.
* **Sex.** 2,472 F / 2,446 M — balanced enough to estimate cleanly.
* **Comorbidity**, 18 ICD-10 chapters, median 3 populated, 474 patients with none. Use the chapters rather
  than a count: a cerebrovascular diagnosis and a dermatological one should not contribute equally.
* **Nervous-system medication**, per §2.
* **Age × sex interaction** — cheap to test, and if it is absent that is one fewer thing a reviewer can ask
  about.

## 6. REFUSE — race and ethnicity

`HEEDB_patients.csv` carries `RaceAndEthnicity` and `RaceAndEthnicityDSC`. **It must not enter the
reference.**

The project's standing constraint forbids it, and independently it is the right scientific call. Normative
clinical references adjusted for race — spirometry and eGFR being the well-documented cases — have been
heavily criticised for encoding structural and environmental differences as though they were biological
constants, and then propagating that into clinical thresholds. A frozen reference is exactly the artefact
where that error becomes permanent and invisible.

**It should still be measured and reported as a fairness audit**: does the frozen reference systematically
mis-centre any group? That is a check on the reference, not a term in it, and the distinction is the whole
point.

## 7. Known unknowns — not available here, and they should be said out loud

Not in HEEDB metadata, plausibly material, and therefore limitations rather than omissions:

* **eyes open vs closed** — changes alpha directly, and alpha sits inside a 0.5–45 Hz fit;
* **time of day / circadian phase**, and time since waking;
* **skull thickness, BMI, head size** — the skull is a low-pass filter, so this bears on the slope
  specifically and not merely on amplitude;
* **electrode impedance** at acquisition;
* **caffeine, nicotine, acute alcohol**;
* **time since last seizure** for the epilepsy-workup fraction;
* **activation procedures** — routine EEG includes hyperventilation and photic stimulation, which are not
  resting state. If the annotations locate them, those segments should be **restricted out**; if they do
  not, the fact that some unknown fraction of "resting" segments are post-hyperventilation is a limitation
  of the reference.

## 8. The order to do this in, and where it can die cheaply

1. **Build the wake detector and freeze it.** Everything else is downstream of §1, and it is the largest
   effect on the list.
2. **Read every EDF header first** — `sfreq`, filters, montage, duration — and decide restrict-versus-
   stratify from the measured distribution rather than from an assumption. Cheap, and it prevents the
   most likely spurious result.
3. **Signal pass on the restricted set**, process-and-discard, nothing patient-derived into the repo.
4. **The regression that decides whether any of this was worth it:** how much between-subject variance do
   age, sex, comorbidity and medication actually explain? No outcome, no candidate, no label. **If R² is
   trivial, a conditional reference is no better than a pooled one and the idea dies for the cost of one
   regression** — and that is the outcome to hope for early rather than late.
5. Only then freeze `(expected_exponent | covariates, residual_SD)`, hash it, and re-express one existing
   result on it.

**One more thing the counts changed.** There are two further sites in the deposit — `I0002` and `I0003`
findings tables — which were not used in the cohort build. Adding them enlarges the reference and, more
usefully, provides a **held-out site** for testing whether the frozen reference transfers, which is the
property the whole exercise exists to obtain.
