# Pivot 2 pre-publication robustness battery

Tests a reviewer of a MEASUREMENT paper demands, on the extracted cohorts. The EV1000 cohort is larger but pulse-contour (waveform-derived); the INDEPENDENT_CO cohort (Vigilance thermodilution / CardioQ Doppler) is the circularity-clean one.

## EV1000_pulsecontour
- N = 221 (SVR source col `svri_measured`).
- **Agreement (Bland-Altman, waveform-estimated vs measured SVR):** bias -8.6, 95% LoA [-1095.6, 1078.4], **percentage error 0.56** (Critchley <=0.30 pass = False; mean measured SVR 1941.9).
- **Pre-specified primary (diastolic/MAP) Spearman vs measured SVR:** 0.2226 (95% CI [0.0881, 0.3485], n=205).
- **Case-mix:** primary Spearman all=0.2226 (n=205) vs NON-cardiac=0.2226 (n=205); n_cardiac=0.

## INDEPENDENT_CO
- N = 48 (SVR source col `svr_indep`).
- **Agreement (Bland-Altman, waveform-estimated vs measured SVR):** bias 15.1, 95% LoA [-751.1, 781.2], **percentage error 0.786** (Critchley <=0.30 pass = False; mean measured SVR 975.3).
- **Pre-specified primary (diastolic/MAP) Spearman vs measured SVR:** 0.1503 (95% CI [-0.1687, 0.4719], n=41).
- **Case-mix:** primary Spearman all=0.1503 (n=41) vs NON-cardiac=0.1503 (n=41); n_cardiac=0.

## Interpretation
- **Correlation vs agreement:** a high Spearman with a LARGE percentage error means the waveform RANKS vascular tone well but is not a calibrated point-estimate of SVR. For a 'trend monitor / vasoplegia detector' that is acceptable (the clinical use is detecting CHANGE/low-tone, not replacing a number); for 'replaces the SVR monitor' it is not. Scope the claim to what the percentage error supports.
- **Pre-specified primary** = diastolic/MAP form factor (the carrier identified by the red-team R4 + dynamic decomposition) -- declared primary to avoid multiplicity fishing; other features are secondary/exploratory.
- **External validity:** single-centre (SNUH/VitalDB); no public external arterial-waveform + CO cohort -> external replication is stated future work, not done here.
- Still PENDING separately: the vasopressor-administration confound + lead/lag + window-length sensitivity (dynamic within-case claim) -- see docs/PIVOT2_DYNAMIC_CONFOUNDS.md.
