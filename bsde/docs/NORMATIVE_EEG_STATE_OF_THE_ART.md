# Normative EEG: what the field has done, what it has not, and the four ways to improve on it

*Written 2026-07-31. Search counts and abstracts pulled through NCBI E-utilities with `curl`; the band
measurement in §4 is computed here.*

---

## 1. The field is decades mature — and it has essentially never been pointed at our questions

Search counts, PubMed, normative-modelling terms **AND** EEG **AND** each domain:

| domain | hits |
|---|---|
| general normative modelling / brain charts in EEG | large, with a 2026 review (**PMID 42312085**) tracing it from the 1970s |
| clinical monitoring / prognosis / ICU | **70** |
| **anaesthesia, sedation, consciousness** | **11** |
| **disorders of consciousness, coma, covert consciousness** | **2** |

**And the two DoC hits are false positives.** PMID 36041343 and PMID 28844160 both compute z-scores of
EEG *reactivity* against **each patient's own pre-stimulus resting epochs** — a within-patient baseline
over seconds, for a stimulus-response construct. That is a different object from a population normative
reference in every respect. **The true count of population normative references applied to disorders of
consciousness is zero.**

What the field *has* built is substantial and should be reused rather than reinvented:

* **qEEGt / Cuban Human Brain Mapping Project** (PMID 32848689) — age-corrected normative statistical
  parametric maps of EEG log **source** spectra, integrated into CBRAIN, *"validated and used in different
  health systems for several decades"*.
* **Taiwan EEG normative database** (PMID 36831893) — 260 healthy participants in 10-year age bands, with
  z-score cross-validation against 221 depression patients.
* **An EEG growth chart** from 1,056 children (PMID 38537603) — functional brain age from routine
  paediatric EEG.
* **A multi-site normative framework** (PMID 40946930) that explicitly addresses *"batch-effects across
  datasets and inconsistencies introduced by diverse EEG electrode montages"* — the harmonisation problem
  flagged in `NORMAL_REFERENCE_COVARIATES.md` §4, already worked on.

**So the methodology is settled and the application is open.** That is the best position to be in: nothing
to invent, a well-defined gap to fill, and a mature literature to be measured against.

---

## 2. What every existing normative EEG system has in common

1. **Healthy volunteers** as the reference population.
2. **Age correction**, sometimes sex; occasionally in bands rather than continuously.
3. **Band power per electrode** as the measure — so tens to hundreds of z-scores per subject.
4. **Trait framing**: *"is this brain abnormal?"* — diagnosis, deviation, screening.

Each of those is a place to improve, and the four improvements below are independent of one another.

---

## 3. Four improvements, in descending order of how much they matter

### (a) Reference population — clinically-read-normal, not healthy volunteers

Every existing database recruits healthy volunteers. **The population being scored is not acquired that
way**: different department, different technicians, different electrode application, different duration,
different environment. That mismatch is baked into every z-score such a database produces.

The HEEDB negative-read cohort — **4,944 strict-normal recordings, 4,558 patients, read as normal by
expert neurophysiologists** — comes through **the same clinical acquisition pathway as the patients who
will be scored**. That removes an entire class of batch effect at source rather than modelling it, which
is what PMID 40946930 has to spend its method on.

### (b) Condition on medication and comorbidity, not just age

**No existing normative EEG database corrects for medication**, and in our cohort **88.9 % carry
nervous-system drugs**. Benzodiazepines augment beta; antiepileptics and antipsychotics modify the
spectrum. A "normal read" is not an undrugged brain, and a reference that ignores this is systematically
mis-centred for exactly the patients most likely to be monitored.

Comorbidity is the same argument with 18 ICD-10 chapters, 100 % linked, median 3 populated per patient.

### (c) One montage-robust number instead of bands × electrodes

Existing systems produce a z-score per band per electrode, which creates a multiple-comparison problem
they then have to manage. A single montage-robust scalar avoids it entirely — and the delocalization
evidence says a scalar is what the scalp supports anyway (91 % of the information from one electrode,
with a forward model attributing 99 % of the frontal-posterior reduction to volume conduction).

**Which scalar is settled empirically in §4 below, and the answer is not the obvious one.**

### (d) State framing instead of trait framing — the conceptual move

Normative qEEG asks *"is this brain abnormal?"* We would ask *"how far is this brain, right now, from where
**this patient's** normal sits?"* The reference supplies a patient-specific **origin**; the deviation from
it is a **state** measure that updates second by second.

**That is the part nobody has done**, and it is what makes the reference useful for anaesthesia depth and
for disorders of consciousness rather than for screening. It is also what the zero-hit search count in §1
is really measuring.

---

## 4. Which measure goes on the scale — settled by measurement, and it is not the broadband exponent

E43 established that the broadband aperiodic exponent is **more** muscle-associated than BIS, not less —
asymmetry **−0.0967 [−0.1886, −0.0058]**, refuting the prior claim of EMG robustness. That immediately
raises the question of what should go on a normative scale instead, and the band decomposition answers it.

Same machinery, same 5,845 rows, same case-clustered bootstrap; **asymmetry positive means the state
measure is MORE EMG-robust than BIS**:

| measure | partial(BIS,EMG\|s) | partial(s,EMG\|BIS) | asymmetry | reading |
|---|---|---|---|---|
| `exponent_high` (20–40 Hz) | +0.235 | **−0.369** | **−0.1335 [−0.2317, −0.0524]** | least robust |
| `whole_head_exponent` (1–45 Hz) | +0.165 | −0.261 | **−0.0967 [−0.1886, −0.0058]** | less robust than BIS |
| `relative_alpha_power` | +0.270 | −0.222 | +0.0478 [−0.0409, +0.1335] | no difference |
| **`exponent_low` (1–20 Hz)** | +0.257 | **+0.098** | **+0.1591 [+0.0714, +0.2384]** | **more robust than BIS** |
| **`lempel_ziv`** | +0.235 | −0.046 | **+0.1894 [+0.1109, +0.2662]** | most robust |

**The broadband exponent inherits its entire EMG vulnerability from the 20–40 Hz half.** Restrict the fit
to 1–20 Hz and the sign flips: `exponent_low` is *more* EMG-robust than BIS, with an interval excluding
zero.

**This is exploratory and must be registered before it is claimed.** It is a post-hoc extension of E43 on
the same rows, prompted by E43's own outcome. What makes it worth acting on now is that two measures agree
in sign with intervals excluding zero, the ordering is monotone in how much of the EMG band the fit
includes, and the mechanism is transparent: surface EMG lives at 20–45 Hz, so a fit that spans it absorbs
it.

**It also lands on an idea the prior work already had.** The dual-slope decomposition — fitting 1–20 Hz and
20–45 Hz separately — was used there to separate ketamine from seizure. **Here the same decomposition
solves an artefact problem**, which is a second, independent reason to carry both bands rather than one
broadband number. `subband_exponents` already exists in this registry for the Colombo 20–40 Hz result.

---

## 5. What this changes about the plan

1. **The normative scale should carry `exponent_low` (1–20 Hz), not the broadband exponent.** Measured,
   not assumed, and it reverses the default choice.
2. **Carry `lempel_ziv` alongside it** — most EMG-robust of the six tested, and a different construct.
3. **Register the band comparison** before it is claimed anywhere. It is currently exploratory.
4. **The Q16 regression is unchanged** and remains the step that kills or sizes the whole idea; it should
   now be run on `exponent_low` as well as the broadband exponent, since they may have different
   covariate structure. **Updated 2026-07-31: run it on `lempel_ziv` separately too, and never pooled —
   PMID 42294963 shows aperiodic-corrected measures can come out age-independent (r = 0.000), which is
   R² ≈ 0 and therefore zero Challenge B gain. See `EXISTING_NORMATIVE_MODELS.md` §3(b).**
5. **Cite the field properly.** We are applying a mature method to an untouched application, not inventing
   normative modelling. PMID 42312085 for the review, PMID 32848689 for the decades-validated
   implementation, PMID 40946930 for multi-site harmonisation, PMID 38537603 for an age-conditional
   precedent. **Claiming novelty for the method would be both wrong and easy to check.**
6. **The question "should we just use an existing normative model?" has now been answered separately and
   in full** — `EXISTING_NORMATIVE_MODELS.md`. Short version: the validated ones are commercial, the
   academic ones are request-gated, and **none of the six carries an aperiodic measure**. HarMNqEEG is the
   right methodological template and a plausible external validation set (open cross-spectra on Synapse,
   free account required); OpenNeuro `ds005385` (608 subjects, 20–70, 376 F / 232 M, two sessions five
   years apart) needs no credentials at all and should be pulled.

**The honest one-line position:** normative EEG is mature and well validated; nobody has used it for
anaesthetic state or for disorders of consciousness; the reference population, the medication
conditioning, and the state-rather-than-trait framing are each defensible improvements; and the measure
that should go on the scale is not the one this project would have chosen a day ago.
