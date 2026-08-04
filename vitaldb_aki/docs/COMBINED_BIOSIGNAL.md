# ECG x arterial-line COMBINED biosignal -- and the requirement predictor (Pivot #1)

Pairs the arterial line with ECG_II (500 Hz, 3644 cases) to build cross-channel signals neither carries alone -- PAT (R-peak->pulse-foot = contractility + stiffness/tone) and BRS (RR<->SBP coupling = autonomic reserve) -- and tests whether the COMBINED biosignal predicts the vasopressor dose-requirement (vasoplegia) phenotype better than arterial morphology or ECG-coupling alone.

- Feature cases extracted: **123** (23 arterial, 9 ECG-coupling features).
- Requirement-phenotype cases: **52**; merged: **52**.

## Ablation -- is the combination worth it? (OOF Spearman vs requirement)
- ARTERIAL-only: {'oof_spearman': 0.295, 'oof_r2': 0.027, 'n': 52}
- ECG-coupling-only: {'oof_spearman': -0.026, 'oof_r2': -0.095, 'n': 52}
- **COMBINED**: {'oof_spearman': 0.267, 'oof_r2': 0.039, 'n': 52}

- Univariate vs requirement: {'art_sbp_mean': -0.398, 'art_map_mean': -0.394, 'art_ppv_burden_min': 0.385, 'art_low_dbp_burden_min': 0.35, 'art_dbp_mean': -0.33, 'brs_n_sequences': 0.319, 'map_dia_form_factor': -0.304, 'art_ppg_amp_corr': 0.281}

## Verdict
Combination NOT clearly additive at this N -- combined 0.267 vs arterial 0.295 / ECG -0.026.

## Caveats
- OOF only; merged N is the binding constraint (the requirement phenotype needs >=2 stable norepi-only target-band epochs, which is rare). Treat as feasibility until N>=25.
- PAT here uses the cross_waveform extractor (ECG R-peak -> pulse foot); absolute PAT mixes pre-ejection period and transit time -- the combined index is a SURROGATE, validated by its correlation with the requirement / SVR, not a calibrated measurement.
- Single-centre (SNUH/VitalDB); external replication required.
