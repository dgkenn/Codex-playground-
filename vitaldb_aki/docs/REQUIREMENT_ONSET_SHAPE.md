# Trajectory SHAPE & ONSET of the vasopressor requirement (deeper tangent)

Complementary to docs/PRESSOR_REQUIREMENT_TRAJECTORY.md (which established that the requirement RISES in ~54% of cases). That module answered *does it rise?*; this one asks the next questions: does the trajectory's **shape** and **onset timing** carry information BEYOND the early level?

Sample: NEPI norepi-only stable epochs, time-ordered within case, >= 4 epochs/case (stricter than the trajectory module's 3 -- shape/onset need more points).

- NEPI norepi-only epochs: **474** over **75** cases.
- Cases with >= 4 time-ordered epochs (shape-eligible): **52** (52 with anaesthesia-start timing from cases.csv).

## 1. RATE-OF-RISE vs LEVEL (does the early slope add info beyond the early level?)
Predicting each case's LATE/peak requirement from an EARLY window (first 50% of epochs):
- LEVEL only: R^2 = **0.163**.
- LEVEL + rate-of-rise: R^2 = **0.323** (delta R^2 **0.159**, partial-R^2 0.191).
- Partial correlation (early slope vs late peak, controlling for early level): **-0.437** (p 0.0012); nested-F p 0.0013636066295953867.
- Fast-riser subgroup (top tertile of early slope): {'n_fast': 17, 'n_slow': 35, 'late_peak_fast_median': 0.22914, 'late_peak_slow_median': 0.24777, 'mannwhitney_p_fast_gt_slow': 0.3924}.

## 2. ONSET TIMING (when does the patient first cross a HIGH requirement?)
HIGH threshold = the cohort p75 of NEPI-only dose_per_kg = **0.274831**.
- Cases crossing HIGH: **28** (never-high: 24; already-HIGH at first epoch / left-censored: **8**).
- Onset from first stable epoch: median **13.2 min** (IQR [0.0, 55.6], range [0.0, 130.9]).
- 2-cluster split: {'split_point_min': 46.6, 'n_early': 19, 'n_late': 9, 'early_mean_min': 9.1, 'late_mean_min': 86.8, 'between_over_total_ss': 0.763, 'note': 'between/total SS is the fraction of onset-time variance explained by a 2-cluster split; high (->1) with a clear split-point gap supports bimodality.'}.
- Bimodality gap diagnostic: {'largest_gap_min': 40.2, 'largest_gap_frac_of_range': 0.308, 'gap_location_min': 86.6, 'note': 'largest interior gap as a fraction of the onset-time range; >~0.3 hints bimodal.'}.
- _8 of 28 crossing cases are already >= HIGH at their FIRST stable epoch (onset=0). Their true onset is LEFT-CENSORED (it occurred before the norepi-only stable window began), so the 'early-onset' cluster is inflated/contaminated by entry-already-high cases -- read the bimodality with this caveat._
- Onset from ANAESTHESIA START (n=28): median **153.8 min** (IQR [46.4, 221.9], range [10.0, 407.6]).

## 3. PROGRESSIVE vs TRANSIENT (shape class -> outcome)
- Shape classes: **rising 14 / plateau 19 / falling 19**.
- Outcome event-rate by class:
  - **composite**: rising 0.7 (n=10), plateau 0.909 (n=11), falling 0.538 (n=13)
  - **organ_renal**: rising 0.0 (n=10), plateau 0.3 (n=10), falling 0.167 (n=12)
  - **aki**: rising 0.0 (n=10), plateau 0.3 (n=10), falling 0.167 (n=12)
- Progressive (rising+plateau) vs transient (falling):
  - **composite**: progressive 0.81 (n=21) vs transient 0.538 (n=13) -> RD **0.271** (Fisher p 0.1297).
  - **organ_renal**: progressive 0.15 (n=20) vs transient 0.167 (n=12) -> RD **-0.017** (Fisher p 1.0).
  - **aki**: progressive 0.15 (n=20) vs transient 0.167 (n=12) -> RD **-0.017** (Fisher p 1.0).
- Within-case SVR slope by class (vasoplegia mechanism, rising should track falling SVR): {'rising': {'n': 3, 'median_svr_slope_per_min': -2.5719}, 'plateau': {'n': 3, 'median_svr_slope_per_min': 0.9253}, 'falling': {'n': 4, 'median_svr_slope_per_min': 6.7666}}.

  CONFOUNDING-BY-SEVERITY: progressive (rising/plateau) cases are by construction the more vasoplegic patients, who are independently more likely to suffer organ injury; with this N no severity adjustment is possible. Treat any class-outcome difference as hypothesis-generating.

## Verdict
PARTIAL -- the trajectory shape's main statistical signal (the early slope) is a COLLINEAR/SUPPRESSOR artifact, NOT an actionable 'fast riser = worse' effect; the early LEVEL is the dominant actionable summary. Onset timing and shape-outcome show suggestive but underpowered / left-censored structure. Net: shape adds little ACTIONABLE info beyond the level at this N. RATE-OF-RISE vs LEVEL (n=52): predicting the LATE/peak requirement, early LEVEL alone R^2=0.163; LEVEL + rate-of-rise R^2=0.323 (delta R^2 0.159; MARGINAL slope<->latepeak r 0.019; level<->slope collinearity 0.727; PARTIAL r -0.437 p 0.0012; nested-F p 0.0013636066295953867; fast-riser subgroup MWU p 0.3924). The early slope adds R^2 but as a NEGATIVE SUPPRESSOR, not an actionable signal: the marginal slope<->late-peak correlation is ~0 and the early slope is highly COLLINEAR with the early level (high-level cases also rise fast), so the negative partial coefficient is a collinearity/mathematical-coupling artifact, NOT 'fast risers are worse'. The fast-riser subgroup test is NULL. Actionably, the early LEVEL alone is the dominant summary. ONSET TIMING (28 of 52 cases cross the HIGH threshold): median first-crossing 13.2 min from first stable epoch (IQR [0.0, 55.6]); 2-cluster split-point 46.6 min (early n=19 / late n=9, between/total SS 0.763, largest gap frac 0.308; 8 already-HIGH at first epoch = left-censored). A two-cluster split exists but is CONTAMINATED by left-censoring (many onset=0 entry-already-high cases), so the early-onset cluster is not cleanly interpretable. SHAPE classes: rising 14 / plateau 19 / falling 19. Progressive vs transient (composite): 0.81 (n=21) vs 0.538 (n=13), RD 0.271, Fisher p 0.1297. CONFOUNDED BY SEVERITY; hypothesis-generating.

## Caveats
- **Small N (~52 shape-eligible cases).** Every test here is descriptive / hypothesis-generating; the nested model, the onset clustering and the shape-outcome contrast are all underpowered. Re-run as the epochs CSV grows.
- **Confounding by severity is unadjusted** -- progressive cases are the sicker patients; any class-outcome difference is expected from severity alone.
- **Onset threshold is cohort-relative** (p75 of dose_per_kg), not an absolute clinical dose; 'HIGH' is defined within this single-centre sample.
- **Dose units** are Orchestra device rate/kg (not ug/kg/min); within-case slopes and the cohort percentile are concentration-relative, not absolute.
- **Anaesthesia-start timing** uses cases.csv `anestart` (seconds, vs casestart=0); a few cases may lack it -- onset-from-anaesthesia uses only those with the field.
- **Single-centre (SNUH/VitalDB)**; external replication required.
