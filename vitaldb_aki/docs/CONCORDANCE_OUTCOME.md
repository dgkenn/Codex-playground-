# Concordance -> outcome (adjusted): does following the A-line lever reduce injury?

The make-or-break-for-impact test. Adjusted (g-computation) risk difference of CONCORDANT vs DISCORDANT management (actual fluid/pressor lean matching the A-line-indicated lever), case bootstrap CI, negative control, within-recommendation strata.

- Cases with both axes + management + outcome: **558**; clear recommendation+management: **122** (concordant 68, discordant 54). Recommendation counts: {'fluid': 158, 'pressor': 159, 'mixed': 241}.

## Adjusted RD (concordant - discordant), negative = concordant has LESS injury
- composite (PRIMARY): adj RD **0.0811** (95% CI [-0.0564, 0.1978], crude 0.091, n=122, base 0.1803).
- organ_renal (secondary): adj RD **-0.0333** (95% CI [-0.094, 0.0053], crude -0.0407, n=116, base 0.0345).
- organ_hypoperfusion (secondary): adj RD **None** (95% CI None, crude None, n=22, base None).

- E-value (primary): 2.26.
- Within-recommendation strata (primary): {'fluid': {'n': 60, 'n_concordant': 36, 'n_discordant': 24, 'crude_rd': 0.1111, 'adj_rd': 0.0724, 'ci': [-0.0916, 0.2029], 'base_rate': 0.15}, 'pressor': {'n': 62, 'n_concordant': 32, 'n_discordant': 30, 'crude_rd': 0.0833, 'adj_rd': 0.0633, 'ci': [-0.1681, 0.2725], 'base_rate': 0.2097}}.

## Verdict
NULL decision-benefit. Concordant adjusted composite RD 0.0811 (CI [-0.0564, 0.1978], n=122) -- and it ATTENUATED toward 0 as N grew (was -0.09 at n=70). The higher-power INTERACTION test on ALL 549 cases is also NULL (pressor_lean:tone -0.039 [-0.267, 0.219]; fluid_lean:ppv 0.233 [-0.04, 0.77]). Conclusion: NO demonstrable decision-benefit from following the A-line lever in this observational data -> impact ceiling is RISK-STRATIFICATION + the mechanistic/concept contribution, NOT outcome improvement (would need an RCT). Consistent with either no benefit or clinicians already reading the A-line.

## Caveats
- Actual fluid/pressor lean = end-of-case crystalloid/colloid (mL/kg) + bolus pressor TOTALS, no timing -> coarse exposure. Axes are whole-case morphology. Observational.
- Confounding by indication runs BOTH ways: clinicians may already read PPV/tone off the A-line (concordance high, null expected) AND sicker patients get more pressor + worse outcomes. Adjustment + the negative control mitigate but do not replace randomisation.
- A clear adjusted NEGATIVE primary RD with a CLEAN negative control is the recoverable-gap signal that would lift this from risk-stratification to decision-benefit (impact). A null is consistent with both 'no benefit' and 'clinicians already optimal'.
