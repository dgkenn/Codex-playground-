# Rising vasopressor-REQUIREMENT early-warning (trajectory pivot)

Because intraoperative MAP is FEEDBACK-REGULATED (anaesthetist titrates norepinephrine dose to a MAP target; within-patient MAP CV ~0.09 vs dose CV ~0.44, see docs/PRESSOR_REQUIREMENT.md), the deterioration signal lives in the DOSE (controller effort), not in MAP. **Hypothesis:** a RISING norepinephrine requirement is an EARLY signal of evolving vasoplegia that PRECEDES any MAP fall, because BP is held flat until the controller saturates.

Sample: STABLE constant-infusion NEPI norepi-only epochs, time-ordered within case, >= 3 epochs/case.

- NEPI norepi-only epochs: **327** over **51** cases (of 891 total epochs).
- Cases with >= 3 time-ordered epochs (trajectory-eligible): **39**.

## 1. Within-case requirement TREND
- Rising (dose_per_kg slope > 0): **21/39 (54%)**.
- Median total dose change across a case: 0.319 (rising cases: 2.6).

## 2. LEAD-TIME (does dose rise BEFORE MAP falls?)
- Cases with a sustained MAP<65 drop after epoch 0: **7**.
- Of those, dose rose before the drop: **4** (frac 0.571).
- Median lead time: **669.1 s** (observed leads: [384.2, 635.6, 702.7, 7076.8]).
  _Note: with this N the lead-time test is UNDERPOWERED; the numbers above are descriptive, not inferential._

## 3. Outcome association (rising vs stable requirement)
- **composite**: rising 0.75 vs stable 0.583 -> RD **0.167** (boot CI [-0.188, 0.521], Fisher p 0.4319; n_rising=16, n_stable=12).
- **organ_renal**: rising 0.133 vs stable 0.273 -> RD **-0.139** (boot CI [-0.479, 0.176], Fisher p 0.6196; n_rising=15, n_stable=11).
- **aki**: rising 0.133 vs stable 0.273 -> RD **-0.139** (boot CI [-0.479, 0.176], Fisher p 0.6196; n_rising=15, n_stable=11).

  CONFOUNDING-BY-SEVERITY: rising-requirement cases are, by construction, the sicker/more-vasoplegic patients, who are independently more likely to suffer organ injury. A positive RD is therefore expected even if the trajectory adds no predictive value beyond baseline severity; with this N no severity adjustment is possible. Treat any association as hypothesis-generating, NOT causal.

## 4. Falsification -- rising requirement should track FALLING SVR
- Cases with a within-case SVR trend: **7**.
- Spearman(dose-slope, svr-slope) = **-0.607** (p 0.1482); expected NEGATIVE.
- Rising cases with FALLING SVR: **0.333** (of 3 rising-with-SVR cases).

## Verdict
PARTIAL -- the rising-requirement phenomenon is REAL and common, but the lead-time and/or SVR-falsification tests are underpowered at this N; the early-warning CLAIM is not yet confirmed. A rising norepinephrine REQUIREMENT exists and is common: 21/39 (54%) of NEPI-only cases with >=3 stable epochs show a positive dose_per_kg trend over time. LEAD-TIME is UNDERPOWERED: only 7 case(s) had a sustained MAP<65 drop with a prior epoch, too few to estimate a reliable lead time (observed leads [384.2, 635.6, 702.7, 7076.8]). FALSIFICATION (SVR, n=7): dose-slope vs svr-slope Spearman -0.607, frac rising-with-falling-SVR 0.333. OUTCOME (composite): rising RD 0.167 (CI [-0.188, 0.521], Fisher p 0.4319, n_rising=16, n_stable=12) -- CONFOUNDED BY SEVERITY, hypothesis-generating only.

## Caveats
- **Confounding by severity is unadjusted** -- sicker patients both need rising pressor and suffer more organ injury; the outcome RD is hypothesis-generating only.
- **Lead-time / SVR-falsification are N-limited** -- few cases reach a sustained MAP<65 drop, and SVR (EV1000) is recorded in only a minority; treat as descriptive.
- **Dose units** are Orchestra device rate / kg (not ug/kg/min); within-case TRENDS are concentration-invariant, which is exactly what the trajectory test uses.
- **Single-centre (SNUH/VitalDB)**; external replication required.
- The CSV is actively extended; re-run as N grows -- the lead-time and SVR tests are the ones that will move from descriptive to inferential first.
