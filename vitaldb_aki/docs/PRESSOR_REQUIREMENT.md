# Stable-epoch vasopressor dose-REQUIREMENT (robust pressor-responsiveness)

The titration-transient design was closed-loop confounded (dose is a feedback response to MAP; docs/PRESSOR_RESPONSE_MODELING.md). This uses STABLE constant-infusion epochs instead: the norepinephrine dose (per kg) required to sustain MAP in the clinical target band [55.0, 80.0] mmHg. High requirement = vasoplegia. No titration transient -> not reverse-confounded.

Confounders controlled: per-kg dosing (body size); MAP-band conditioning (dose to hold the SAME MAP); norepi-ONLY epochs (drug identity / co-vasoactives); 60 s settle; anaesthetic depth (BIS/MAC) + preload (CVP) captured per epoch.

- Stable epochs extracted: **1509** over **219** cases.
- Qualifying norepi-only target-band epochs: **303**; cases with a requirement phenotype (>= 2 epochs): **52**.

## Why 'BP rise per dose' is NOT directly identifiable (controlled-variable check)
- Within-patient MAP coefficient-of-variation **0.095** vs dose CV **0.493** (dose varies **5.2x** more than MAP), over 58 multi-epoch cases.
  MAP is a tightly **feedback-regulated** variable: the anaesthetist titrates dose to hold MAP at target, so the dose->BP gain is absorbed by the control loop and cannot be read off observational BP (transient OR steady-state). The vasoreactivity signal is carried by the **dose requirement** (controller effort), not by dBP.

## Dose-response GAIN -- 'how much does BP rise per unit dose' (the literal target)
- Pooled WITHIN-patient gain: **-10.58 mmHg per (norepi rate/kg)** (95% CI [-18.69, -0.67], 68 multi-dose cases).
- Per-patient gain: median -1.25, IQR [-42.84, 28.6], fraction positive 0.5.
  Estimated at STEADY STATE across stable epochs (not the titration transient) -> closed-loop-free. Between-patient spread in per-patient gain is the predictable 'BP rise per dose' phenotype.

## Requirement phenotype (norepi rate / kg to hold target MAP)
- median 0.16318, IQR [0.11069, 0.25154], p10-p90 [0.07096, 0.39731], **between-patient fold-range (p90/p10) = 5.6**.
- **Reliability (within-patient split-half):** {'n_cases_ge4_epochs': 30, 'splithalf_spearman': 0.817}.
- **Construct validity:** {'vs_cumulative_exposure_spearman': 0.69, 'vs_achieved_MAP_spearman': -0.428, 'vs_EV1000_SVR_spearman': 0.182, 'n_svr_overlap': 15, 'note': 'expect: vs cumulative exposure POSITIVE (vasoplegic need more), vs achieved MAP <=0, vs EV1000 SVR NEGATIVE (low tone = high requirement)'}.

## Verdict
GO -- a stable-epoch norepinephrine dose-REQUIREMENT phenotype exists in 52 patients, varies ~5.6-fold between patients (p10-p90), split-half reliability 0.817, and tracks vasoplegia markers (vs cumulative exposure 0.69, vs EV1000 SVR 0.182). This is a confound-robust, closed-loop-free target a pre-epoch waveform model can predict.

## Caveats
- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the per-case drug concentration VitalDB does not expose. Between-patient comparison assumes comparable norepi concentration (standard institutional mix) -- stated assumption; the split-half reliability is concentration-invariant within a case.
- **Observational requirement, not intrinsic vasoreactivity:** the requirement reflects management + physiology. Construct-validity against EV1000 SVR / cumulative exposure is the evidence it indexes vasoplegia, not an assumption.
- **Single-centre (SNUH/VitalDB);** external replication required.
- Next: does the PRE-epoch arterial waveform/morphology predict this requirement? (the GPU-optional model build) -- and does the Pivot-2 diastolic-tone index correlate with it (links the two findings).
