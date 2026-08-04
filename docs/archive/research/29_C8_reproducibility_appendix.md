# Reproducibility appendix — C8 manuscript (result → analysis → number)

Every quantitative claim in the manuscript maps to a specific analysis run this program. Scripts live in the
session scratchpad (gitignored, not committed with the repo — they read credentialed data supplied at runtime);
this appendix records the exact definitions, cohorts, and outputs so a human can re-derive and verify each number.
Datasets: **VitalDB** (api.vitaldb.net), **INSPIRE** (PhysioNet inspire/1.3), **eICU-CRD** (PhysioNet eicu-crd/2.0).

## Standing methods (apply throughout)
- **RTM-safe discordance:** fix the arterial line as the gold-standard reference; report cuff **sensitivity** for
  arterial-defined hypotension *conditioning on the arterial value* — never bin on the noisy cuff. Arterial
  reference = windowed median (VitalDB ±60 s / ≥15 samples; eICU ±5 min) to smooth artifact.
- **Units:** mne reads EDF in volts; CBraMod/analyses expect µV (×1e6) — never z-normalise amplitude away.
- **Within-operation design:** arterial- and cuff-defined hypotension computed in the *same* operations, so
  patient-level confounders affect both exposures equally; the art-vs-cuff *difference* is confounder-controlled.

## Result-by-result map
| Manuscript claim | Cohort / n | Definition | Number | Script (scratchpad) |
|---|---|---|---|---|
| Cuff sensitivity for art<65/60/55 | VitalDB 1,079 cases, 5,903 pairs | art ref = median ±60 s ≥15 samp; cuff = NIBP change-points | 56.2% / 41.7% / 26.9% (missed 44/58/73%) | `vitaldb/vitaldb_bp.py` |
| Low-pressure over-read | VitalDB | Bland-Altman by arterial stratum | +30.6 mmHg at art 20–55; ~0 mid | `vitaldb/vitaldb_bp.py` |
| Window/anchor robustness | VitalDB | ±30/60/90 s | sens 55.0/56.1/55.9; bias +30.7/30.8/30.5 | `vitaldb/threshold_safety.py` (window loop) |
| Vasopressor NOT the cause | INSPIRE | within-op MAP-matched on/off infusion crossover | Δbias −0.1 [−2.8,+2.6] (art 20–55); +0.3 (55–65) | `inspire/vasopressor_within.py`; between-pt `vasopressor_strat.py` |
| Replication at scale | INSPIRE 47,533 ops | art<65 vs cuff | cuff misses 71% | `inspire/inspire_bp.py` |
| **Harm attenuation (Table 1)** | INSPIRE 28,349 ops | within-op, adj age/ASA/dur/baseline-Cr | mortality 2.09 vs 1.48; lactate 1.91 vs 1.46; AKI 1.34 vs 1.26; composite 1.86 vs 1.47; ICU 2.63 vs 1.74; MINS 1.48 vs 1.50 | `inspire/inspire_harm2.py` |
| Attenuation = undercounting (tautology test) | INSPIRE 27,528 | outcome ~ cuff-flag + continuous arterial burden/depth | cuff OR→1.05 [0.98–1.12] null; art burden 1.73/10 min | `inspire/etco2…` no — `inspire/` tautology block in harm re-analysis (`aline_features.py` + statsmodels) |
| Matched-cadence | INSPIRE | arterial sampled only at cuff times | mortality 2.27 vs 1.90; lactate 2.41 vs 1.88 | `inspire/inspire_harm.py` (matched-cadence variant) |
| Treatment gap | INSPIRE 20,009 ops | at matched min-art severity, cuff-detected→pressor | OR 1.34 [1.25–1.44]; detected 71.3 vs 63.5% (55–65) | `inspire/inspire_treatgap.py` (output `tasks/b6d1cnype.output`) |
| Detection delay | VitalDB | cuff never <65 in 64%; median delay | 9.1 min | `vitaldb/vitaldb_bp.py` |
| Threshold operating chars | VitalDB 5,906 pairs | cuff<65 vs <70 vs <75 vs art<65 | <65 sens 56.1/spec 89.8/FPR 10.2/PPV 49.8; <70 71.9/81.2/18.8/40.7 | `vitaldb/threshold_safety.py` |
| Overtreatment bounded | VitalDB | arterial MAP of readings newly flagged by <70 | median art 70; 24.7% truly <65 | `vitaldb/threshold_safety.py` |
| **eICU external — discordance** | eICU 24,691 stays / 1.14M pairs, 154 hosp | art (systemicmean) ref, cuff (noninvasivemean) | missed 47% at <65, 68% at <55; bias +13.1 (20–55) | `eicu/eicu_validate.py` |
| eICU external — threshold | eICU 1.14M pairs | <65→<70 | sens 53.0→70.7%; FPR 11.8→23.6% | `eicu/thr_safety_eicu.py` |
| eICU external — attenuation | eICU 24,691 stays | art vs cuff → hospital mortality | OR 5.40 [4.80–6.07] vs 4.86 [4.29–5.50] | `eicu/eicu_validate.py` |
| Prediction score (exploratory, held-out) | INSPIRE subject-split | 4-factor count, held-out test | Y_missed 0.61; Y_harm ~0.68–0.71; leakage-free (no duration) ~0.57 | `inspire/aline_model.py` |
| Score external validation FAILED | VitalDB 1,071 | frozen 4-factor count | AUC 0.546 [0.511–0.579], non-monotone calibration | `vitaldb/vitaldb_extval.py` |
| Score = severity not mechanism | INSPIRE | harm ~ score by cuff-missed status | harm\|missed=0 0.708 > harm\|missed=1 0.646 | `inspire/aline_features.py` (severity block) |

## Notes for the independent verifier
- Numbers with `[—]` in Table 1 have point estimates recorded; recompute CIs from `inspire_harm2.py` (crude+adj
  OR functions) before final submission.
- INSPIRE's larger discordance (71%) vs VitalDB (44%) is granularity artifact (minute-level vs 2-s waveforms);
  VitalDB is the clean estimate — do not headline the 71%.
- eICU magnitude (+13.1 mmHg) is ~2.3× smaller than VitalDB (+30.6): report as direction + order-of-magnitude
  replication, not identical magnitude (ICU population, coarser sampling).
- The prediction score is **exploratory/negative** and is reported as such; it is not a study endpoint.
