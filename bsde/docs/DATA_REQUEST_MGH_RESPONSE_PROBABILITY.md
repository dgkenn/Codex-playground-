# Data request — the volunteer response-probability time series behind `eeg-power-anesthesia`

*Drafted 2026-08-01. Target: the MGH group behind PhysioNet `eeg-power-anesthesia` 1.0.0. The deposit
already gives us everything else; this asks for the one column that was used to build it and not shipped.*

---

## What is being asked for

The deposit's own methods say, verbatim:

> Loss of consciousness (LOC) was recorded as **the time at which the probability of response to both
> click and verbal cues dropped below 5 %** [...] Return of consciousness (ROC) was recorded as the time
> at which the probability of response to both click and verbal cues **again exceeded 5 %**.

So a **continuous response-probability time series exists for each of the ten volunteers** — it is what
LOC and ROC were thresholded from. The deposit ships only the resulting binary label
(`{CASEID}_l.csv`: 1 conscious, 0 unconscious).

**The request is for that underlying series**, per volunteer, on any time base: the per-cue
responded/not-responded record, or the fitted response probability, or both. Nothing else is needed —
we already hold the spectra, the frequency and time axes and the labels.

---

## Why it matters, stated as what it would change rather than as an aspiration

This project's Challenge A asks for a representation that *"predicts loss and recovery across
anaesthetics while minimising drug-identification information"*. We established two things this session
that make this specific series the binding constraint.

**1. These ten volunteers are the only behavioural loss-AND-recovery data we can reach.** A full
enumeration of OpenNeuro — 1,834 datasets, 517 with EEG or iEEG — found **no disorders-of-consciousness
cohort at all** and only three anaesthesia deposits, two of which we already use and one with a single
subject (`results/openneuro_eeg_survey.json`). Within `eeg-power-anesthesia` itself the OR arm cannot
substitute: **in 0 of 44 OR cases is a conscious epoch adjacent to an unconscious one** — the median gap
is 286 epochs (10 minutes) — because the deposit labels the whole induction-to-surgery window `NaN` on
the stated grounds that the true LOC time is unknowable retrospectively. So the recovery clause is
testable on ten subjects anywhere, and only here.

**2. The binary label is what limits us, not the EEG.** Our strongest landmark result on this cohort
(`alpha_peak_hz`, E153) survives a paired contrast against matched non-transitions and survives
truncation of the spectrum at 30 Hz — but its per-subject sign counts are **4 of 9 and 6 of 9**, at
chance. With ten subjects and a binary label, a landmark statistic has one usable observation per subject
per transition. **A graded response probability turns that into a continuous regression on hundreds of
epochs per subject**, which is roughly a two-order-of-magnitude increase in the information available
from the same recordings, with no new subjects and no new EEG.

Concretely, it would let us ask the question the binary label cannot: *does any EEG measure track the
probability of responding, moment to moment, rather than only the threshold crossing?* That is closer to
what a consciousness marker has to do than "is this epoch above or below 5 %".

---

## What we would do with it, pre-committed

1. **Replace the binary target with the continuous one** in the landmark designs (E148, E151, E152, E153)
   and re-run them unchanged otherwise. Their gates and placebos are already written and committed.
2. **Report the result whichever way it goes**, including if the continuous target *weakens* the
   `alpha_peak_hz` finding — which is a real possibility and is the main reason to want the data.
3. **Publish the analysis code and the derived features**, not the source series. Nothing patient-level
   from this request would be redistributed.

---

## What we are not asking for

No raw EEG, no additional subjects, no identifiers, no clinical record. The deposit's existing
de-identification and access terms cover everything we would hold; this is one derived time series per
volunteer from a study whose spectra are already public.

---

## What we can offer back

* **An external validation of the deposit's own published representation.** We scored the shipped
  `Volunteer_CNN` bottlenecks, reduced to ten principal components exactly as the paper specifies, against
  eleven hand-built spectral features on the same 46,948 windows with subjects held out whole: out-of-fold
  AUC **0.8092** for the CNN against **0.9426** for the spectral panel, with the spectrum adding
  −0.12980 to the CNN and the CNN adding −0.00296 to the spectrum (E159, all gates passing including a
  leakage control judged against its measured null). That is an independent, unflattering-to-us-if-it-had-
  gone-the-other-way check on the deposit, and it is available now.
* **The extraction and analysis code**, which reads the deposit directly and computes per-2 s spectral
  features validated against the canonical frontal-alpha signature (relative alpha 0.03 → 0.12–0.19 and
  the aperiodic exponent 0.88 → 2.2–2.6 across conscious/unconscious in every case).
* **Co-authorship or acknowledgement on any resulting work**, at the group's preference.

---

## Contact and status

**Status: drafted, not yet sent.** Needs the investigator to identify the right correspondent — the
deposit's PhysioNet contact, or the corresponding author of the paper the `Volunteer_CNN` features were
built for. Both are on the deposit's landing page and neither is recorded here, because this file is
committed to a public repository.

Companion requests, both outstanding and both now the *only* routes to their respective questions after
the OpenNeuro survey: `DATA_REQUEST_TURKU_KALLIONPAA.md` (two anaesthetics with loss and recovery in the
same subjects — Challenge A's other half) and BATH-01632 (UWS/LIS/MCS command-following — Challenge B's
real target, pre-registered as E18 and requested 2026-07-30).
