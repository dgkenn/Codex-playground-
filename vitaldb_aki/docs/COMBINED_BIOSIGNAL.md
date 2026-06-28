# ECG x arterial-line COMBINED biosignal -- and the requirement predictor (Pivot #1)

Pairs the arterial line with ECG_II (500 Hz, 3644 cases) to build cross-channel signals neither carries alone -- PAT (R-peak->pulse-foot = contractility + stiffness/tone) and BRS (RR<->SBP coupling = autonomic reserve) -- and tests whether the COMBINED biosignal predicts the vasopressor dose-requirement (vasoplegia) phenotype better than arterial morphology or ECG-coupling alone.

- Feature cases extracted: **21** (23 arterial, 9 ECG-coupling features).
- Requirement-phenotype cases: **52**; merged: **5**.

## Verdict
INSUFFICIENT merged N=5 (feature cases 21, phenotype 52).

## Caveats
- OOF only; merged N is the binding constraint (the requirement phenotype needs >=2 stable norepi-only target-band epochs, which is rare). Treat as feasibility until N>=25.
- PAT here uses the cross_waveform extractor (ECG R-peak -> pulse foot); absolute PAT mixes pre-ejection period and transit time -- the combined index is a SURROGATE, validated by its correlation with the requirement / SVR, not a calibrated measurement.
- Single-centre (SNUH/VitalDB); external replication required.
