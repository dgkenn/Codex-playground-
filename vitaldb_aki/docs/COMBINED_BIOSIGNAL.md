# ECG x arterial-line COMBINED biosignal -- and the requirement predictor (Pivot #1)

Pairs the arterial line with ECG_II (500 Hz, 3644 cases) to build cross-channel signals neither carries alone -- PAT (R-peak->pulse-foot = contractility + stiffness/tone) and BRS (RR<->SBP coupling = autonomic reserve) -- and tests whether the COMBINED biosignal predicts the vasopressor dose-requirement (vasoplegia) phenotype better than arterial morphology or ECG-coupling alone.

- Feature cases extracted: **53** (23 arterial, 9 ECG-coupling features).
- Requirement-phenotype cases: **52**; merged: **37**.

## Ablation -- is the combination worth it? (OOF Spearman vs requirement)
- ARTERIAL-only: {'oof_spearman': -0.22, 'oof_r2': -0.3, 'n': 37}
- ECG-coupling-only: {'oof_spearman': -0.355, 'oof_r2': -0.295, 'n': 37}
- **COMBINED**: {'oof_spearman': -0.305, 'oof_r2': -0.347, 'n': 37}

- Univariate vs requirement: {'pat_mean_ms': 0.3, 'brs_mean': 0.01, 'diastolic_over_map': -0.129, 'pat_slope': 0.164}

## Verdict
Combination NOT clearly additive at this N -- combined -0.305 vs arterial -0.22 / ECG -0.355.

## Caveats
- OOF only; merged N is the binding constraint (the requirement phenotype needs >=2 stable norepi-only target-band epochs, which is rare). Treat as feasibility until N>=25.
- PAT here uses the cross_waveform extractor (ECG R-peak -> pulse foot); absolute PAT mixes pre-ejection period and transit time -- the combined index is a SURROGATE, validated by its correlation with the requirement / SVR, not a calibrated measurement.
- Single-centre (SNUH/VitalDB); external replication required.
