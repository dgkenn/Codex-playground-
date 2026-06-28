# Stable-epoch vasopressor dose-REQUIREMENT (robust pressor-responsiveness)

The titration-transient design was closed-loop confounded (dose is a feedback response to MAP; docs/PRESSOR_RESPONSE_MODELING.md). This uses STABLE constant-infusion epochs instead: the norepinephrine dose (per kg) required to sustain MAP in the clinical target band [55.0, 80.0] mmHg. High requirement = vasoplegia. No titration transient -> not reverse-confounded.

Confounders controlled: per-kg dosing (body size); MAP-band conditioning (dose to hold the SAME MAP); norepi-ONLY epochs (drug identity / co-vasoactives); 60 s settle; anaesthetic depth (BIS/MAC) + preload (CVP) captured per epoch.

- Stable epochs extracted: **69** over **8** cases.
- Qualifying norepi-only target-band epochs: **19**; cases with a requirement phenotype (>= 2 epochs): **3**.

## Verdict
INSUFFICIENT -- only 3 cases with >= 2 target-band norepi epochs so far.

## Caveats
- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the per-case drug concentration VitalDB does not expose. Between-patient comparison assumes comparable norepi concentration (standard institutional mix) -- stated assumption; the split-half reliability is concentration-invariant within a case.
- **Observational requirement, not intrinsic vasoreactivity:** the requirement reflects management + physiology. Construct-validity against EV1000 SVR / cumulative exposure is the evidence it indexes vasoplegia, not an assumption.
- **Single-centre (SNUH/VitalDB);** external replication required.
- Next: does the PRE-epoch arterial waveform/morphology predict this requirement? (the GPU-optional model build) -- and does the Pivot-2 diastolic-tone index correlate with it (links the two findings).
