# RESTRAINT — pragmatic cluster-RCT of conservative vs liberal electrolyte repletion (working protocol)

**Restrictive vs Liberal Electrolyte Repletion for Mild Asymptomatic Hypomagnesemia/Hypokalemia in
Hospitalized Adults: A Pragmatic Cluster-Randomized De-Implementation Non-Inferiority Trial.**

## Rationale
Reflexive nurse-/protocol-driven repletion of mild derangements (Mg 1.5–2.0 mg/dL, K 3.0–3.5 mEq/L) occurs at
enormous scale (129k Mg administrations/1 hospital/10 yr) on ~no RCT evidence. Observational identification is
impossible here (RDD: smooth dose-response, no discontinuity; IPTW: RR 4.17 confounded; unit-IV: case-mix).
Equipoise is genuine and total → only an RCT can answer it.

## Design
- **Pragmatic, cluster-randomized (WARD/unit-level), parallel-group, open-label with BLINDED outcome
  adjudication.** Ward-level (not patient: contamination via shared order sets; not hospital: too coarse,
  ICC-inflating). Stepped-wedge retained as a pre-specified contingency for sites needing eventual rollout.
- EHR-embedded: intervention = an order-set/default reconfiguration (a CPOE build flag by unit code); no
  study visits, no product, no bedside consent behavior.

## Population
Adults on medical/surgical (non-ICU, non-cardiac-surgery) wards with incident asymptomatic Mg 1.5–2.0 or
K 3.0–3.5. **Carve-outs treated per standard in BOTH arms (proven/high-risk indications):** Mg<1.0 / K<2.5 or
any symptomatic derangement; post-cardiac-surgery (≤7 d); torsades/long-QT (QTc>500); digoxin toxicity/use;
recent cardiac arrest or unstable arrhythmia; eGFR<15/dialysis; pregnancy; comfort-care; prisoners.

## Interventions
| Electrolyte | Standard (liberal) auto-replete | Conservative auto-replete | Both arms (regardless) |
|---|---|---|---|
| Magnesium | Mg < 2.0 | Mg < 1.5 | Mg < 1.0, symptomatic, or carve-out |
| Potassium | K < 3.5 | K < 3.0 | K < 2.5, symptomatic, or carve-out |
Conservative arm: no auto-order fires in the mild band; passive non-interruptive flag; **physician override
always one click away** (override rate = fidelity/process outcome). Recheck labs/telemetry unchanged (isolates
the repletion decision).

## Outcomes
- **Co-primary (both must meet NI):** (1) in-hospital new-onset clinically-significant arrhythmia composite
  (new AF/flutter, sustained VT, VF, symptomatic bradyarrhythmia; adjudicated); (2) all-cause in-hospital
  mortality. Window = index qualifying value → discharge or 14 d.
- **Secondary:** 30-d mortality, LOS, unplanned ICU transfer, cardiac arrest, repletion doses/nursing time/
  cost avoided, over-repletion harm (hyperMg>2.4 / hyperK>5.0, phlebitis, GI), override rate.
- Hypothesized: conservative arm SUPERIOR on burden/cost/over-repletion, NON-INFERIOR on safety.

## Sample size (non-inferiority; 1-sided α=0.025, 90% power)
- Arrhythmia composite: baseline 6%, **NI margin 2.0 pp**, m≈150 pts/ward, ICC 0.01 base → DEff 2.49 →
  ~7,378/arm (~49 wards/arm). Powered to the ICC=0.02 sensitivity (~24k) + 5% inflation → **funded target
  ≈25,000 patients, ≈160 ward-clusters (80/arm), ~15–20 hospitals, 18–24 mo.** (Mortality co-primary:
  baseline 4%, margin 1.5 pp → ~17,860, within the arrhythmia-driven target.)
- Internal pilot (first ~15% clusters) re-estimates ICC before locking final N (pre-specified adaptive step).

## Analysis
ITT by cluster assignment; **GLMM with ward random intercept** (hospital nested), arm fixed effect,
covariates (age, sex, service, Charlson, baseline electrolyte, renal fn). NI declared if upper 95% CI of the
risk difference < margin for BOTH co-primaries (conjunctive). GEE sensitivity; per-protocol (excluding
overrides) descriptive. Pre-specified subgroups (service, age, renal, electrolyte type, within-mild-band
severity, diuretic use). One safety-only interim (Haybittle-Peto p<0.001); independent DSMB with unit-pause
authority.

## Ethics / feasibility
Waiver/modified consent (minimal incremental risk — both arms are current practice somewhere; narrows rather
than expands exposure; patient-level consent infeasible + contaminating; override preserves autonomy;
carve-outs protect indicated patients; broad public notification + opt-out). Prospective registration,
CONSORT (cluster + NI + pragmatic) reporting, pre-registered SAP. De-implementation-science elements:
default-reversal as mechanism, monthly audit-and-feedback, pre-drafted model order-set for dissemination on a
positive result.

## Venue path
The TRIAL is the NEJM/JAMA guideline-setting paper. The observational package (evidence vacuum + scale + the
"observational methods all fail here" methods demonstration + provider-IV estimate if it survives) is the
design-rationale/motivating paper (JAMA IM / Annals / a trials journal) that de-risks and justifies RESTRAINT.
Full annotated protocol drafted by the design agent; this doc is the working condensation.
