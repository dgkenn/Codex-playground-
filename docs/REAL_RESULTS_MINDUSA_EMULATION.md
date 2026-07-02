# MIND-USA (antipsychotics for ICU delirium) — instrument not buildable in this extract (honest negative)

All-factors target-trial emulation of MIND-USA (Girard NEJM 2018; RCT truth = NULL: haloperidol/ziprasidone vs
placebo did not change delirium/coma-free days or 90-day survival). Trigger is a **symptom/gestalt** (delirium),
so the natural instrument is provider/nurse antipsychotic-preference, not assay-noise.

## Emulation
Cohort factor-by-factor: (a) all first-ICU adults (n=85,242) → (b) + delirium ICD proxy (n=6,710) → (c) +
exclude dementia (n=5,963) → (d) + vent/vasopressor (proxy) → (e) MIND-USA-FAITHFUL (n=5,677). Outcome =
90-/30-day mortality (the primary delirium/coma-free-days endpoint is unavailable in MIMIC). Instrument = nurse
leave-one-out antipsychotic-liberality; controls = age spline + first-careunit FE; NC empirical-null calibration.

## Result — the instrument structurally fails (F < 1 everywhere)
| stage | full-cohort n | IV n (nurse-assignable) | first-stage F | 90d RF-ITT (95% CI) | balAge |
|---|---|---|---|---|---|
| (a) all ICU | 85,242 | 1,107 | 0.7 FAIL | +0.25 [−1.85, +2.36] | +0.29 |
| (b) +delirium | 6,710 | 300 | 0.9 FAIL | −2.49 [−6.54, +1.57] | −0.41 |
| (c) +exclude dementia | 5,963 | 258 | 0.9 FAIL | +0.19 [−4.29, +4.66] | +1.06 |
| (e) MIND-USA-faithful | 5,677 | 230 | 0.9 FAIL | +0.12 [−4.80, +5.05] | +2.67 FAIL |

## Mechanism — a MIMIC charting limitation, not just small n
The emar `provider` (nurse) field is populated almost **only on administered doses**: among "nurse-assignable"
patients the antipsychotic-exposed rate is **98.9–99.7%**, vs 5.6–17.5% among the rest. Requiring a non-empty
provider to build the leave-one-out instrument therefore selects almost exclusively **treated** patients,
mechanically collapsing first-stage variance in the exposure. This is a data-charting artifact of the extract,
diagnosed explicitly (not a coding bug). Point estimates bounce in sign with enormous overlapping CIs → the null
is *nominally* consistent but this is an **underpowered non-result**, not a validated confirmatory replication.

## Honest scope notes
- QTc<550, pregnancy, prior QT-prolongation/torsades/NMS, moribund, rapidly-resolving-organ-failure exclusions
  could **not** be operationalized (no ECG/clinical-course fields) → cohort is a superset of true eligibility.
- Vasopressor/vent tightening not achievable — this repletions extract carries no vasopressor itemids; ICU stay
  used as the proxy (flagged, no silent tightening).

## Verdict
For antipsychotic-vs-placebo in the delirium cohort, the nurse-preference instrument is **not usable in this
MIMIC-IV emar extract** (provider field charted conditional-on-administration). This is logged as an honest
instrument-infeasibility, distinct from our earlier *elective-stratum* provider-IV (`provider_iv.py`), which
recovered the MIND-USA null via admission-acuity stratification rather than the delirium-cohort nurse-LOO. A
usable delirium-cohort test would need attending-level prescribing data or an emar extract that charts the
ordering provider on non-administered/withheld doses.

## Follow-up (rechecked with a second, independent table — verdict confirmed, mechanism sharpened)
Per the user's push to verify rather than accept an apparent data-gap at face value, we retried with
`prescriptions.csv` (order-level, NOT administration-conditional — the exact fix that worked for SUP-ICU/PEPTIC
above) instead of emar. Result: **still degenerate, but for a different, more fundamental reason.**
`order_provider_id` only exists on rows where an antipsychotic was ordered — so "provider-assignable" and
"D=1 (antipsychotic exposed)" are **the same event by construction**, not a compliance/charting artifact.
Exposed rate among assignable = 1.0000 exactly (vs 0.0003 non-assignable) — a stricter collapse than the emar
version. We also tried the natural alternative, `admit_provider_id` (filled independent of the antipsychotic
decision, 99.999% coverage): first stage is strong on the full ICU population (F=195) but **fails F≥10 at
every delirium-restricted stage (F=2.5–7.1)** — the delirium/critical-illness cohort is essentially all
emergent/non-elective, so the acuity-confounded provider-assignment problem `provider_iv.py` already documented
in its EMERGENT stratum applies here too. **This closes the loop: two independent tables, two independent
provider-identity fields, both fail for well-understood, distinct, non-fixable reasons.** MIND-USA in the
delirium-ICU population is retired with high confidence, not merely an unexplored data gap.
