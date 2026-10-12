# Vasopressor REQUIREMENT -> ACUTE KIDNEY INJURY (KDIGO): MIMIC discovery, INSPIRE + VitalDB cross-validation

Tests whether the vasopressor-requirement signal (discovered against mortality in MIMIC-IV ICU) also predicts the project's ORIGINAL organ-injury target -- **AKI / KDIGO**, which is present in all three cohorts. Discovery in MIMIC; honest cross-cohort validation the OTHER way (INSPIRE 130k, VitalDB). Each cohort gets its own verdict; the INSPIRE causal arm uses negative-control-outcome calibration (as in `REDTEAM_CKD_MAP.md` / Pivot 3) and is allowed to die.

## 1. MIMIC discovery -- requirement -> KDIGO AKI
KDIGO AKI derived per admission from serum creatinine (itemid 50912): **baseline = FIRST (admission) creatinine** (primary; the standard KDIGO reference), peak=max over the admission; AKI = peak/baseline >= 1.5 OR peak-baseline >= 0.3 mg/dL; stage by ratio. ESRD/dialysis excluded (ICD N18.6/Z99.2/585.6/V45.11/V56.x or baseline >= 4.0 mg/dL). The liberal min-baseline is reported as a sensitivity only -- it over-calls AKI-on-admission and pushes the rate to ceiling.

- Linked norepi ICU stays: **6421** (ESRD excluded: 883); AKI rate **0.482** (min-baseline sensitivity rate 0.87); stages {0: 3325, 1: 1573, 2: 589, 3: 934}.
- **Requirement -> AKI, age-adjusted OR per SD: 1.377 [1.248, 1.504]** (n=6421, events=3093).
- **Dose-response across requirement quartiles** (monotone=True, Q4-Q1=0.223):
  - Q1: median req 0.04 mcg/kg/min, AKI rate 0.384 (n=1605).
  - Q2: median req 0.06 mcg/kg/min, AKI rate 0.435 (n=1605).
  - Q3: median req 0.1 mcg/kg/min, AKI rate 0.5 (n=1605).
  - Q4: median req 0.2203 mcg/kg/min, AKI rate 0.607 (n=1606).
- **Within-severity (adjusted for age + first-24h lactate + comorbidity count): OR per SD 1.198 [1.069, 1.362]** (n=4549, events=2084).
- Within lactate tertiles (age-adjusted requirement OR):
  - lactate T1: OR 1.273 [1.099, 1.501] (n=1453, AKI 0.376).
  - lactate T2: OR 1.165 [1.005, 1.546] (n=1569, AKI 0.43).
  - lactate T3: OR 1.136 [1.031, 1.304] (n=1527, AKI 0.565).

**MIMIC verdict:** MIMIC DISCOVERY (n=6421 norepi stays, 883 ESRD excluded, AKI 0.482): requirement->AKI age-adjusted OR/SD 1.377 [1.248, 1.504] (CI excludes 1) | dose-response Q4-Q1 0.223 MONOTONE across quartiles | within-severity (age+lactate+comorbidity adj) OR/SD 1.198 [1.069, 1.362] | 3/3 lactate strata keep OR>1 (CI excl 1). DOSE-RESPONSE TO AKI HOLDS within severity -> requirement marks renal risk beyond measured severity (observational; not a treatment effect).

## 2. INSPIRE external validation (the other way) -- negative-control calibrated
Restricted to the intraop-medication subset (n=50546; outside it `intraop_norepi` is blank = no med extract, NOT zero). Exposure = intraop norepi (dose, and >0). Outcome panel = renal (target) + hepatocellular / cholestatic / coagulation (negative controls). Adjusted for age/sex/asa/egfr/anesthesia-duration. Empirical null built from the non-renal controls; renal estimate calibrated to it.

### Exposure: norepi DOSE (per SD)
- organ_renal: adjusted OR 1.048 (logOR 0.0473, n=38963, events=2475).
- organ_hepatocellular: adjusted OR 1.021 (logOR 0.0204, n=31577, events=3535).
- organ_cholestatic: adjusted OR 1.099 (logOR 0.0948, n=30251, events=2971).
- organ_coagulation: adjusted OR 1.077 (logOR 0.0746, n=19513, events=2146).
- null logOR mean 0.0633 sd 0.0385; **renal calibrated OR 0.984 (z=-0.42)** -> DIES within the null.

### Exposure: norepi ANY (>0)
- organ_renal: adjusted OR 2.542 (logOR 0.933, n=38963, events=2475).
- organ_hepatocellular: adjusted OR 1.514 (logOR 0.4151, n=31577, events=3535).
- organ_cholestatic: adjusted OR 3.007 (logOR 1.101, n=30251, events=2971).
- organ_coagulation: adjusted OR 3.568 (logOR 1.272, n=19513, events=2146).
- null logOR mean 0.9294 sd 0.4535; **renal calibrated OR 1.004 (z=0.01)** -> DIES within the null.

**INSPIRE verdict:** INSPIRE EXTERNAL (norepi dose -> AKI, age/sex/asa/egfr/duration-adj): renal raw OR 1.048 (logOR 0.0473); negative-control null mean 0.0633 sd 0.0385; CALIBRATED logOR -0.016 (OR 0.984, z=-0.42) -> DIES within the empirical confounding null (NOT renal-specific) -- same fate as Pivot 3

## 3. VitalDB external validation (small N, honest)
- NEPI-requirement cases: n=219 (renal events 17). Requirement median renal+ 0.2134 vs renal- 0.1658, MW p=0.2574.
- Any-pressor exposure -> renal: crude OR 1.395 (fisher p 0.069, n=3924, table {'pressor_renal': 95, 'pressor_norenal': 2218, 'nopressor_renal': 48, 'nopressor_norenal': 1563}).

**VitalDB verdict:** VitalDB EXTERNAL (small N): NEPI-requirement cases n=219 (renal events 17); NO requirement->renal signal at this N (MW p=0.2574) | any-pressor crude OR 1.395 (fisher p 0.069). Underpowered -- directional only.

## Overall verdict
OVERALL: DISCOVERY (MIMIC): dose-response to AKI holds within severity; INSPIRE causal arm: DIES on negative-control calibration (expected, cf Pivot 3); VitalDB: underpowered directional. The requirement is a robust RISK MARKER for AKI that grades dose-response within measured severity in the discovery ICU cohort, BUT the cross-cohort CAUSAL arm (INSPIRE, the honest negative-control-calibrated test) does NOT survive: the renal effect is indistinguishable from the empirical confounding null built from non-renal organ injuries. So: predictive / risk-stratifying YES, renal-SPECIFIC CAUSAL claim NO. Consistent with confounding by indication, exactly as Pivot 3 found for the CKD-MAP claim.

## Caveats (honest)
- MIMIC AKI is creatinine-only (no urine-output KDIGO criterion) and built on a **partial (~46%) labevents snapshot** -- some admissions have sparse/absent creatinine, so AKI ascertainment is incomplete (missing-not-quite-at-random). The FIRST-creatinine baseline can MISS AKI already present on admission (the admission value is itself elevated) -> under-call; bias is toward the null. The min-baseline sensitivity over-calls instead (rate 0.87, ceiling) -- the truth is bracketed and the dose-response gradient is present under both.
- The MIMIC association is observational; within-severity conditioning controls MEASURED severity (lactate, comorbidity, age) only -- the strongest honest causal test is the INSPIRE negative-control-calibrated arm.
- INSPIRE intraop_norepi exists only for a medicated subset; the restriction is principled but means the INSPIRE estimand is 'among cases with a med record'.
- VitalDB renal events among NEPI-requirement cases are few -> directional only.
