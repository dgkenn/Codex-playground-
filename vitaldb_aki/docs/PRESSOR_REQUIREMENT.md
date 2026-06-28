# Stable-epoch vasopressor dose-REQUIREMENT (robust pressor-responsiveness)

The titration-transient design was closed-loop confounded (dose is a feedback response to MAP; docs/PRESSOR_RESPONSE_MODELING.md). This uses STABLE constant-infusion epochs instead: the norepinephrine dose (per kg) required to sustain MAP in the clinical target band [55.0, 80.0] mmHg. High requirement = vasoplegia. No titration transient -> not reverse-confounded.

Confounders controlled: per-kg dosing (body size); MAP-band conditioning (dose to hold the SAME MAP); norepi-ONLY epochs (drug identity / co-vasoactives); 60 s settle; anaesthetic depth (BIS/MAC) + preload (CVP) captured per epoch.

- Stable epochs extracted: **364** over **48** cases.
- Qualifying norepi-only target-band epochs: **54**; cases with a requirement phenotype (>= 2 epochs): **8**.

## Why 'BP rise per dose' is NOT directly identifiable (controlled-variable check)
- Within-patient MAP coefficient-of-variation **0.088** vs dose CV **0.463** (dose varies **5.3x** more than MAP), over 11 multi-epoch cases.
  MAP is a tightly **feedback-regulated** variable: the anaesthetist titrates dose to hold MAP at target, so the dose->BP gain is absorbed by the control loop and cannot be read off observational BP (transient OR steady-state). The vasoreactivity signal is carried by the **dose requirement** (controller effort), not by dBP.

## Dose-response GAIN -- 'how much does BP rise per unit dose' (the literal target)
- Pooled WITHIN-patient gain: **-17.0 mmHg per (norepi rate/kg)** (95% CI [-23.8, 22.82], 14 multi-dose cases).
- Per-patient gain: median 0.08, IQR [-37.53, 24.97], fraction positive 0.5.
  Estimated at STEADY STATE across stable epochs (not the titration transient) -> closed-loop-free. Between-patient spread in per-patient gain is the predictable 'BP rise per dose' phenotype.

## Requirement phenotype (norepi rate / kg to hold target MAP)
- median 0.16924, IQR [0.12716, 0.24627], p10-p90 [0.09782, 0.39983], **between-patient fold-range (p90/p10) = 4.1**.
- **Reliability (within-patient split-half):** {'n_cases_ge4_epochs': 6, 'splithalf_spearman': 0.257}.
- **Construct validity:** {'vs_cumulative_exposure_spearman': 0.81, 'vs_achieved_MAP_spearman': -0.429, 'note': 'expect: vs cumulative exposure POSITIVE (vasoplegic need more), vs achieved MAP <=0, vs EV1000 SVR NEGATIVE (low tone = high requirement)'}.

## Verdict
NOT YET -- 8 phenotype cases; spread fold-range 4.1, reliability 0.257, construct vs exposure 0.81. Need more cases / stronger reliability before declaring a trainable target.

## Caveats
- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the per-case drug concentration VitalDB does not expose. Between-patient comparison assumes comparable norepi concentration (standard institutional mix) -- stated assumption; the split-half reliability is concentration-invariant within a case.
- **Observational requirement, not intrinsic vasoreactivity:** the requirement reflects management + physiology. Construct-validity against EV1000 SVR / cumulative exposure is the evidence it indexes vasoplegia, not an assumption.
- **Single-centre (SNUH/VitalDB);** external replication required.
- Next: does the PRE-epoch arterial waveform/morphology predict this requirement? (the GPU-optional model build) -- and does the Pivot-2 diastolic-tone index correlate with it (links the two findings).
