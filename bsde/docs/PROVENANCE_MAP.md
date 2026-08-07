# Provenance map — every number in the manuscript, and what produced it

*Generated 2026-08-07. Each row names the claim, the value as it appears in the manuscript, the
script that computed it, and the JSON it was read from. Scripts live in `bsde/src/bsde/experiments/`
and outputs in `bsde/results/`. Every script carries its own pre-registration in its module
docstring, committed before the statistic existed.*

| claim | value | script | output |
|---|---|---|---|
| maintenance vs peri leakage, whole_head_exponent sevo/ppf | `0.3525 vs 0.0668` | `e260 control placebo analysis (inline)` | `e260_control_placebo.json + e248_agent_leakage.json` |
| depth quintile trend, VitalDB maintenance | `median rho -0.9000, p=0.0000` | `e290_battery5.py E296` | `e290_battery5.json` |
| depth gradient replicated peri-landmark (n=2503) | `deep 0.3649 vs light 0.0788, 6/6` | `e290_battery5.py E291` | `e290_battery5.json` |
| BIS matching increases leakage | `median retention 1.086` | `e280_battery4.py E281` | `e280_battery4.json` |
| matched-BIS PERI/CTRL ratio | `median 0.806` | `e270_battery3.py E298` | `e270_battery3.json` |
| split-half of maintenance cohort | `Spearman +0.8596` | `e280_battery4.py E288` | `e280_battery4.json` |
| per-arm median centring removes leakage | `51-98%, residual at null 16/18` | `e270_battery3.py E272 / e280_battery4.py E283` | `e270_battery3.json, e280_battery4.json` |
| BIS leaks less than median candidate at maintenance | `0.0747/0.0469/0.1218` | `e270_battery3.py E273` | `e270_battery3.json` |
| BIS gradient runs opposite | `deep 0.0884 -> light 0.1286` | `e290_battery5.py E292` | `e290_battery5.json` |
| VitalDB gradient carried by volatile-vs-propofol | `without ppf -0.0086` | `e290_battery5.py E299` | `e290_battery5.json` |
| state axis landmark-specific | `control P2 within +-0.012 of zero` | `e260 inline analysis` | `e260_control_placebo.json` |
| Krause replication (behavioural axis) | `D=+0.1648, p=0.0016` | `e305_krause_state_dependence.py` | `e305_krause_state_dependence.json` |
| Krause no-drug placebo | `D_sleep=+0.0000, p=0.5148` | `e306_krause_sleep_placebo.py` | `e306_krause_sleep_placebo.json` |
| Krause family decomposition | `complexity +0.3632 p=0.0002; connectivity +0.0566 p=0.2856` | `e307_krause_family_decomposition.py` | `e307_krause_families.json` |
| non-EEG exposure axis failed validation | `Spearman(exposure,BIS) = -0.0529` | `e300_exposure_axis.py E302` | `e300_exposure_axis.json` |

## Extraction provenance

| table | rows | script |
|---|---|---|
| `vitaldb_ventwin.s0-3.csv` | 56,731 windows (56,237 ok), 0 duplicate ids | `bsde/scripts/stream_vitaldb_transitions.py` with `vitaldb_ventwin_plan.json` |
| `vitaldb_ctrlwin.s0-3.csv` | 15,747 windows (15,547 ok), 0 duplicate ids | same script, `vitaldb_ctrlwin_plan.json` (centre = t_rec − 2400 s) |
| `vitaldb_ctrlwin2.s0-3.csv` | 33,873 planned (phase 2, extends maintenance arm) | same script, `vitaldb_ctrlwin2_plan.json` |
| `vitaldb_exposure.s0-5.csv` | 2,930 cases, 100% coverage | `bsde/scripts/vitaldb_exposure_probe.py` |
| `krause_dexprosleep_allData.csv` | 12,313 rows, 34 patients | Zenodo 10.5281/zenodo.15497531 |

## Notes a reviewer should read

* Every leakage null is **patient-level**, not row-level: agent identity is a property of the patient.
  Analytic and empirical nulls agree to the third decimal on VitalDB (0.0317-0.0324 vs 0.0321).
* Krause's nulls are **cluster-level over 29 patients** (drug is nested in patient), 5,000 draws.
* Results that were computed and then **withdrawn** are documented rather than deleted:
  `e248_first_pass_note.md`, `e250_battery_note.md` (E252, E253), `e261_battery2_note.md` (E263, E267),
  `e300_exposure_axis_note.md` (E301 unlicensed by its own validity gate).
* Two claims reported in earlier sessions were later **reversed by better-designed successors** and the
  reversals are in the record: the low-leakage/high-tracking 'corner' (E250/E261 -> E260/E270) and
  BIS leaking more than the panel (E251 -> E273).
