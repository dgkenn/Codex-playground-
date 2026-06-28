# Concordance -> outcome (adjusted): does following the A-line lever reduce injury?

The make-or-break-for-impact test. Adjusted (g-computation) risk difference of CONCORDANT vs DISCORDANT management (actual fluid/pressor lean matching the A-line-indicated lever), case bootstrap CI, negative control, within-recommendation strata.

- Cases with both axes + management + outcome: **558**; clear recommendation+management: **92** (concordant 48, discordant 44). Recommendation counts: {'fluid': 153, 'pressor': 119, 'mixed': 286}.

## Adjusted RD (concordant - discordant), negative = concordant has LESS injury
- composite (PRIMARY): adj RD **0.0522** (95% CI [-0.118, 0.2109], crude 0.089, n=92, base 0.2283).
- organ_renal (secondary): adj RD **-0.0223** (95% CI [-0.0818, 0.0154], crude 0.0022, n=86, base 0.0465).
- organ_hypoperfusion (secondary): adj RD **None** (95% CI None, crude None, n=23, base None).

- E-value (primary): 1.76.
- Within-recommendation strata (primary): {'fluid': {'n': 52, 'n_concordant': 27, 'n_discordant': 25, 'crude_rd': 0.1393, 'adj_rd': 0.0271, 'ci': [-0.0913, 0.1359], 'base_rate': 0.1923}, 'pressor': {'n': 40, 'n_concordant': 21, 'n_discordant': 19, 'crude_rd': 0.0226, 'adj_rd': -0.0283, 'ci': [-0.2541, 0.2633], 'base_rate': 0.275}}.

## Verdict
NULL decision-benefit. Concordant adjusted composite RD 0.0522 (CI [-0.118, 0.2109], n=92) -- and it ATTENUATED toward 0 as N grew (was -0.09 at n=70). The higher-power INTERACTION test on ALL 549 cases is also NULL (pressor_lean:tone -0.025 [-0.315, 0.257]; fluid_lean:ppv 0.239 [-0.035, 0.776]). Conclusion: NO demonstrable decision-benefit from following the A-line lever in this observational data -> impact ceiling is RISK-STRATIFICATION + the mechanistic/concept contribution, NOT outcome improvement (would need an RCT). Consistent with either no benefit or clinicians already reading the A-line.

## Caveats
- Actual fluid/pressor lean = end-of-case crystalloid/colloid (mL/kg) + bolus pressor TOTALS, no timing -> coarse exposure. Axes are whole-case morphology. Observational.
- Confounding by indication runs BOTH ways: clinicians may already read PPV/tone off the A-line (concordance high, null expected) AND sicker patients get more pressor + worse outcomes. Adjustment + the negative control mitigate but do not replace randomisation.
- A clear adjusted NEGATIVE primary RD with a CLEAN negative control is the recoverable-gap signal that would lift this from risk-stratification to decision-benefit (impact). A null is consistent with both 'no benefit' and 'clinicians already optimal'.
