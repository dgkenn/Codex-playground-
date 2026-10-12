# Within-patient SPECIFICITY test (hostile review of the causal-leaning pivot)

Applies the negative-control specificity test that killed the BETWEEN-patient CKD finding to the WITHIN-PATIENT hypotension->AKI estimate (docs/INSPIRE_WITHIN_PATIENT.md). Patient fixed-effects (demeaned LPM) within-patient risk difference of substantial hypotension (HYPO) on each organ outcome; cluster-bootstrap CI over subjects.

Cohort: 52639 multi-op operations, 21565 subjects.

| outcome | type | within-patient RD | 95% CI |
|---|---|---|---|
| organ_renal | hypotension-target | 0.0549 | [0.0477, 0.0631] |
| organ_hypoperfusion | hypotension-target | 0.0973 | [0.0589, 0.1309] |
| organ_hepatocellular | negative control | 0.0513 | [0.0397, 0.0639] |
| organ_cholestatic | negative control | 0.062 | [0.053, 0.0714] |
| organ_coagulation | negative control | 0.06 | [0.0461, 0.0752] |

**Within-patient negative-control null:** 0.0578 +- 0.0057 (hepatocellular/cholestatic/coagulation).
**Renal within-RD calibrated against the within-null:** -0.0029 (z=-0.5).

## Verdict
FAILS specificity within-patient -- renal within-RD 0.0549 ~ negative-control null 0.0578 (calibrated -0.0029); the within-patient effect is ALSO pan-organ -> time-varying confounding not excluded.

Note: a within-patient effect on renal/hypoperfusion that EXCEEDS the non-perfusion negative-control organs is strong evidence the within-patient hypotension->AKI signal is organ-specific (causal-leaning), not generic time-varying severity. If the controls move as much as renal, time-varying confounding cannot be excluded even within-patient.
