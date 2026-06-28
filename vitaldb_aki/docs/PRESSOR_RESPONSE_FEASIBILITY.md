# A-line pressor-response feasibility gate (user pivot #1)

Make-or-break check: are there enough *discrete treatment-change events* with a clean, measurable short-term MAP/CO response to TRAIN a responder-prediction model? Built from the VitalDB track index (cache/trks.csv) + a sampled extraction of small numeric tracks (pump RATE, ART_MBP, CO) -- no 50 MB waveform download.

## Cohort (from the track index, no download)
- Pressor pump (PHEN/NEPI/DOPA/EPI/DOBU/VASO) **and** invasive ART_MBP: **220 cases**.
- ...of which also have a CO monitor (EV1000/Vigileo): **62 cases**.
- Per-drug pump availability: {'PHEN': 127, 'NEPI': 88, 'DOPA': 33, 'EPI': 9, 'DOBU': 3, 'VASO': 1}.
- Fluid-rate time-series (FMS/FLOW_RATE): **15 cases** (crystalloid/colloid otherwise = end-of-case totals, no timing).

## Sampled event extraction
- Cases processed: **3**; clean isolated up-titration events: **14** (total detected 14; 4.67/case).
- Short-term MAP response: median dMAP **4.32 mmHg** (IQR [0.31, 5.24]); **92%** of events had a measurable |dMAP| >= 3.0 mmHg.
- Pressor responsiveness (dMAP per unit dose step): median **0.97**; between-patient IQR of per-case median responsiveness = **None** (this between-patient spread is exactly what a responder model would predict).
- Events also carrying a CO response: **14**.
- Extrapolated clean events over the full cohort: **~1027**.

## Verdict
PRESSOR-RESPONSE arm (MAP): borderline/NO-GO -- 14 clean isolated events over 3 sampled cases (4.67/case), 92% with a measurable >=3.0 mmHg response; extrapolates to ~1027 clean events over the full 220-case pressor+ART_MBP cohort.

CO-RESPONSE sub-arm: thin -- 14 events also carry an EV1000/Vigileo CO response (62 cohort cases have CO).

FLUID-BOLUS arm: **NO-GO at scale** -- the only fluid-rate time-series is FMS/FLOW_RATE (15 cases); crystalloid/colloid are end-of-case totals (no timing), so fluid boluses cannot be event-labelled across the DB. A fluid-responder arm needs the FMS-15 cases (too few) or an external waveform+fluid dataset.

## What a GO unlocks (the high-impact build)
- **A-line -> pressor-responsiveness predictor.** From the pre-titration arterial waveform/morphology, predict the patient's dMAP-per-unit-norepi (responsiveness). High responsiveness -> small dose suffices; blunted responsiveness -> vasoplegia, escalate/seek a cause. This is the responder half of the fluid-vs-pressor idea, and it is directly trainable here (labels = the measured dMAP at each titration step).
- It also **feeds Pivot 2**: pressor responsiveness is the dynamic, intervention-anchored validation of the static 'vascular tone' waveform signal -- a blunted dMAP response is vasoplegia observed through treatment, not just morphology.
- The fluid arm is NOT abandoned but RE-SCOPED: it requires an external arterial-waveform + fluid-bolus-timing dataset (or the FMS-instrumented subset), stated as future work, not blocked on here.

## Honest caveats baked in
- **Confounding by indication:** clinicians titrate *because* MAP is low and often in response to the same waveform -- so dMAP at a step is the treated response, not a clean dose-response. The model target is 'observed responsiveness under care'; causal dose-response needs the isolated-step + covariate-adjusted design (isolated-event flag already captured).
- **Onset/timing:** phenylephrine/norepi act in ~30-60 s; the 45-165 s response window is chosen for that. Sensitivity to the window is future work.
- **Single-centre (SNUH/VitalDB).** External replication is required for any claim.

_GATE thresholds (pre-declared): {"min_clean_events": 300, "min_events_per_case": 2.0, "min_frac_measurable": 0.5, "min_co_events": 30}._
