# Concordance -> outcome (adjusted): does following the A-line lever reduce injury?

The make-or-break-for-impact test. Adjusted (g-computation) risk difference of CONCORDANT vs DISCORDANT management (actual fluid/pressor lean matching the A-line-indicated lever), case bootstrap CI, negative control, within-recommendation strata.

- Cases with both axes + management + outcome: **462**; clear recommendation+management: **70** (concordant 36, discordant 34). Recommendation counts: {'fluid': 120, 'pressor': 95, 'mixed': 247}.

## Adjusted RD (concordant - discordant), negative = concordant has LESS injury
- composite (PRIMARY): adj RD **-0.091** (95% CI [-0.249, 0.0916], crude -0.0131, n=70, base 0.2286).
- organ_renal (secondary): adj RD **-0.0209** (95% CI [-0.077, 0.0241], crude 0.0057, n=65, base 0.0615).
- organ_hypoperfusion (secondary): adj RD **None** (95% CI None, crude None, n=18, base None).

- E-value (primary): 2.71.
- Within-recommendation strata (primary): {'fluid': {'n': 37, 'rd': None}, 'pressor': {'n': 33, 'rd': None}}.

## Verdict
NOT YET POWERED/NULL: composite adjusted RD -0.091 (CI [-0.249, 0.0916], n=70); negative control clean. The concordance->outcome benefit is directional at best -- decision-benefit not established; caps impact to risk-stratification unless larger N / a trial moves it.

## Caveats
- Actual fluid/pressor lean = end-of-case crystalloid/colloid (mL/kg) + bolus pressor TOTALS, no timing -> coarse exposure. Axes are whole-case morphology. Observational.
- Confounding by indication runs BOTH ways: clinicians may already read PPV/tone off the A-line (concordance high, null expected) AND sicker patients get more pressor + worse outcomes. Adjustment + the negative control mitigate but do not replace randomisation.
- A clear adjusted NEGATIVE primary RD with a CLEAN negative control is the recoverable-gap signal that would lift this from risk-stratification to decision-benefit (impact). A null is consistent with both 'no benefit' and 'clinicians already optimal'.
