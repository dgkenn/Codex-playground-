# Cycle 7 — fast cross-hospital screens on cached eICU (apacheApsVar × patient, 207 hospitals)

Rich cached asset: **169,625 ICU stays, 207 hospitals, day-1 physiology + in-hospital mortality (9.5%)** →
external-validation-by-construction (by-hospital 5-fold OOF). Baseline physiology+age model OOF AUC = **0.790**,
stable across hospitals. Tested three novel, trap-free (mechanism/equity, not treatment-decision, not a named
index) hypotheses. All disk-free (cached), fast.

| Hypothesis | Result (by-hospital OOF) | Verdict |
|---|---|---|
| **H1 Relative bradycardia** (HR~temp residual → mortality beyond physiology) | Δ AUC **+0.0000** | NULL |
| **H2 Derangement dispersion** (concentration of derangement across organ systems, at fixed total) | Δ AUC **+0.0052**, but 0.83-collinear with total severity | trivial/incremental |
| **H3 Race miscalibration** (does physiology→mortality miscalibrate by ethnicity?) | O/E 0.93–1.05 all groups (CIs cross 1.0); +ethnicity Δ AUC **−0.0003** | NULL (well-calibrated) |

Incidental honest positives (not high-impact on their own): the APACHE-style physiology→mortality model is
**robust across 207 hospitals** (stable OOF) and **well-calibrated across race** (contrasts with some
SOFA-triage-bias narratives — but for mortality *calibration* specifically, it's fair here).

## Meta-pattern after 7 cycles (the dominant lesson — banked in LESSONS.md)
Across EEG-FM, VitalDB-τ, MIMIC culture-turnaround, and these eICU screens, the same wall keeps appearing:
- **Novel single markers vs a strong baseline → incremental nulls** (baselines are already good; H1/H2/H3,
  MAP-recovery-τ, etc.).
- **Treatment-decision designs → OR≈1.35 confounding ceiling** (vasopressor, liberation-order).
- **Natural experiments → weak first stage** (culture turnaround, +0.09).
- **Equity miscalibration → well-calibrated** (null).
The honest hostile-review gate is doing its job and repeatedly, correctly, refusing to claim a winner from
CPU-feasible ICU tabular mining. A genuine ultra-high-impact winner most plausibly needs a different lever:
the GPU-gated EEG-FM flagship (evidence-backed), a prospective/interventional element, or a fundamentally
new data asset — not another marker-vs-baseline test.
