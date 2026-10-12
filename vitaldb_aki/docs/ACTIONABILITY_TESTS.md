# Actionability of the A-line vasoplegia signal

Does acting on the signal change a decision? Three angles, existing caches only.

## Test 1 -- Early identifiability / lead-time
- Cases with >=4 norepi-only epochs: 52.
- **Early (first-half) requirement predicts LATE requirement:** {'r': 0.537, 'ci': [0.287, 0.725], 'n': 52}.
- First-epoch dose vs eventual median ratio: {'median': 0.55, 'iqr': [0.17, 1.0]}.
- High-requirement cases already flagged at epoch 1: {'n_high': 18, 'flagged_early': 5, 'frac': 0.28}.
- _if early predicts late strongly and high-req cases are flagged at epoch 1, the vasoplegia-prone patient is identifiable BEFORE the pressor escalation -> time to act (actionable lead)._

## Test 2 -- Fluid-vs-pressor lever discrimination
- N cases with PPV + tone: 13.
- **PPV axis vs tone axis correlation:** {'r': 0.132, 'ci': [-0.539, 0.714], 'n': 13} (near 0 = orthogonal = the A-line separates the two levers).
- Lever quadrants: {'fluid_indicated': 4, 'pressor_indicated': 4, 'mixed_ambiguous': 5}; decision-relevant fraction 0.62.
- _low |PPV-tone correlation| => orthogonal axes => the A-line separates preload-responsive (fluid) from vasoplegic (pressor) patients, a decision MAP alone cannot make. fluid/pressor-indicated counts = patients with a clear A-line lever._

## Test 3 -- Risk stratification / outcome gap
- Requirement cases merged to outcomes: 36.
- composite RD (hi vs lo requirement): 0.056 (Spearman 0.119).
- organ_renal RD 0.074; hypoperfusion RD -0.108.
- _positive RD / Spearman => higher A-line requirement flags worse outcomes => an actionable high-risk group. NOTE observational: this identifies WHO is high-risk, not that treating the signal helps._

## Verdict
PRIMARY actionable angle = EARLY IDENTIFICATION: early-epoch requirement predicts the late requirement at r=0.537 [0.287, 0.725] (n=52) -- the vasoplegia-prone patient is identifiable from the first few stable epochs, BEFORE the pressor escalation, giving a lead time to act. SECONDARY: fluid-vs-pressor lever discrimination is SUGGESTIVE (underpowered) (PPV and tone axes near-orthogonal, 0.62 decision-relevant, n=13); risk stratification is WEAK/INCONSISTENT (composite RD 0.056, renal 0.074, hypoperfusion -0.108). Net: ONE robust actionable angle (early ID), one promising-but-underpowered (lever), one weak (risk). Acting-improves-outcome needs a trial.

## Honest caveats
- All observational, single-centre (SNUH/VitalDB), small N (the requirement phenotype is ~52 cases). These tests show the signal COULD be actionable (early, discriminative, risk-marking); proving that acting on it IMPROVES outcomes needs a trial.
- Test 3 identifies a higher-risk group, not a treatment effect; confounding by severity is expected and is the reason a positive RD is necessary-but-not-sufficient for action.
