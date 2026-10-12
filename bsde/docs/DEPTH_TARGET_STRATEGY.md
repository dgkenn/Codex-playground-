# What should the EEG be validated against? — strategy after E121

Investigator, 2026-08-01: *"If we have an accurate model we will need to figure out how to have EEG track
and serve as a depth proxy. Needs to account for all things that cause drugs to be more or less effective
at causing that state. BIS is not a good target right?"*

Short answer: **BIS is not a good target, and neither is drug concentration.** Those are two different
mistakes and the second one is the more interesting.

---

## 1. Three independent reasons BIS fails as a target

**(a) Circularity.** BIS is computed from the same EEG signal. Asking whether an EEG measure tracks BIS
asks whether our summary of a signal agrees with a vendor's summary of the same signal. It can be a useful
*comparator* — E84 and E99 used it that way legitimately — but it cannot be the thing being predicted.
`PKPD_MODEL_REVIEW.md` §6.2 already forbids validating the PK model against it for the same reason.

**(b) We have measured its failure modes ourselves, three times.**
* **E109** — BIS's agreement with the raw EEG **degrades with patient age**, +0.2592 [+0.1367, +0.3761],
  surviving attenuation controls, agent class (E113) and opioid exposure (E120).
* **E120** — BIS tracks **remifentanil** (+0.2042 volatile, +0.1105 TIVA) while the aperiodic exponent
  does not. Most likely co-titration, but it means part of BIS's apparent hypnotic fidelity is opioid.
* **E60's corollary** — in the BIS [0,20) band, where model error was worst, median **SQI was 5.1 of 100**:
  the monitor was publishing a number it simultaneously declared unreliable.

**(c) It is an intermediate, not an endpoint.** No patient or clinician wants a BIS of 45. They want no
awareness, no recall, no oversedation, and prompt emergence.

---

## 2. Drug concentration is not the target either — and this is the sharper point

The obvious replacement is the effect-site concentration from a proper PK model. **It is still wrong, for
a reason that goes to the whole purpose of EEG monitoring:**

> If the EEG tracked concentration perfectly, it would be **redundant with the infusion pump**. The pump
> already knows the concentration. The entire clinical case for an EEG monitor is that individuals differ
> in their response *at the same concentration*.

So an experiment that scores an EEG measure by how well it tracks Ce is rewarding the measure for being
redundant. E110, E112, E120 and E121 all did versions of this — legitimately, because they were asking
whether the exposure was mis-specified — but they cannot be the endpoint of the programme.

---

## 3. The chain, and where the EEG actually belongs

```
   dose ──[PK: clearance, volume, protein binding, body composition]──▶ concentration
                                                                            │
                                        [PD: sensitivity, synergy, tolerance, age, frailty]
                                                                            ▼
                                                                     CLINICAL STATE
```

* The **pump** gives concentration, and E121's L1 rung validated that we can reproduce it independently
  (recomputed end-tidal MAC agreed with the monitor's own: −0.0071 [−0.0302, +0.0148]).
* A **PK/PD model** gives the *population-expected* state at that concentration.
* **The EEG's job is the RESIDUAL: what the model cannot predict.**

That is not a consolation prize. It is the only place an EEG monitor adds information that pharmacology
does not already have, and it is where the clinical failures live — the patient who is aware at a standard
dose, and the patient who is burst-suppressed at half of one.

---

## 4. Why the residual framing solves the "account for everything" problem

The investigator's requirement was that the model *"account for all things that cause drugs to be more or
less effective at causing that state"* — tolerance, chronic alcohol or opioid use, frailty, neurological
disease, genetic variation, acute illness, drug synergy.

**Enumerating those is not achievable and does not need to be.** Every one of them is a PD sensitivity
modifier, and in the residual framing they are absorbed by construction:

> You do not have to model **why** a patient is sensitive. You measure **that** they are.

This is more defensible as well as more useful. `PKPD_MODEL_REVIEW.md` §6 Tier 3 already rules out
inventing an albumin→free-fraction relation or a ≥3-drug surface, because no validated model exists to
implement. The same logic applies to tolerance and frailty: there is no published PD model taking "chronic
alcohol use" as a covariate that could be used as published. The residual does not need one.

---

## 5. This dictates which deposit can answer the question

| deposit | non-EEG state measure | verdict |
|---|---|---|
| **VitalDB** | **none** — BIS is the only state-like variable and it is EEG-derived | **cannot answer the state question.** Excellent for exposure, device behaviour and age effects (E109, E110, E112, E113, E118, E120, E121), which is what it has been used for |
| **DOSE-I** | **MOAA/S in 16,442 of 16,442 held-out windows, 56 recordings, varying within every one** | **the right deposit.** A clinician-assigned sedation score, independent of the EEG, with propofol exposure alongside |
| **chennu** | `n_correct_of_40` and reaction time, 20 subjects × 4 levels, complete | small but real; behaviour rather than a rating scale |

**This is a strategic correction to where effort has been going.** Seven VitalDB experiments asked
exposure and device questions well. None of them could have answered the question that matters, because
the deposit has no state measure that is not the EEG.

---

## 6. The concrete next experiment

**E122 — does the EEG predict the MOAA/S residual that propofol exposure cannot?**

* Prediction 1: MOAA/S from propofol exposure alone (the pharmacology-only expectation).
* Residual: observed MOAA/S − predicted.
* Test: does an EEG measure predict that residual, out of bag, clustered by recording?
* Incumbent (rule 45): the deposit's own shipped `PE31`/`SEF95`, which E84 already established as a live
  comparator (baseline out-of-bag ρ +0.3310 against MOAA/S).

**The gate that makes it honest:** the exposure-only model must itself predict MOAA/S. If pharmacology
alone explains nothing, there is no residual worth attributing, and the verdict is ABSENT rather than a
finding about the EEG.

**And the reason to expect something:** E121 showed a more elaborate *exposure* does not improve tracking.
If exposure is near its ceiling and clinical state still varies, that variance has to be somewhere — and
individual sensitivity is where the pharmacology says it should be.

---

## 7. What this means for the PK/PD build

The Eleveld/Minto implementation is **not abandoned — it is repositioned.** It stops being the thing the
EEG is scored against and becomes the thing that defines the residual. That changes what "accurate enough"
means:

* the model must be good enough that its residual is dominated by individual sensitivity rather than by
  its own error — which is exactly what the Varvel metrics (MDPE, MDAPE, wobble, divergence; PMID 1588504)
  quantify, and why they were specified in §6.3;
* it does **not** need to model tolerance, frailty or genetics, because those are the signal, not the
  nuisance;
* and it must still never be validated against BIS (§6.2).
