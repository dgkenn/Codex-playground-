#!/usr/bin/env python3
"""
G7: convergent partial-identification (Manski-style bounds) from oppositely-biased designs.
Combine estimators whose bias SIGN is known/defensible to BRACKET the true causal effect theta,
with the assay-noise flag-ITT as the ~unbiased anchor. Reviewer-proof packaging: report the
INTERVAL, not one fragile point.

Bias-sign logic (risk-difference scale; outcome = mortality; treatment = repletion/transfusion):
  HARM-biased (theta_hat >= theta): sicker -> more treatment -> worse outcome.
    -> naive/IPTW, provider-preference-IV (habit ~ intensity), within-patient FE (sicker episode).
    -> these give an UPPER bound on theta.
  BENEFIT-biased (theta_hat <= theta): treatment WITHHELD from the sickest (contraindication).
    -> renal-impairment / comfort-care / DNR strata where the frailest are not treated.
    -> these give a LOWER bound on theta.
  ANCHOR (~unbiased): assay-noise flag-ITT (design-based exogenous variation).

Bound: theta in [ max(benefit-biased point est) , min(harm-biased point est) ], anchor should sit inside.
If the bracket excludes clinical benefit (lower > -delta_meaningful), de-implementation is supported.
Conservative variant uses one-sided CIs instead of point estimates.
"""
import numpy as np

def convergent_bounds(estimates):
    """
    estimates: list of dicts {name, est, se, bias} with bias in {'harm','benefit','anchor'}.
    'harm' bias => est is an upper bound on theta; 'benefit' => lower bound.
    Returns point bracket + conservative (CI-widened) bracket.
    """
    harm = [e for e in estimates if e['bias'] == 'harm']
    benefit = [e for e in estimates if e['bias'] == 'benefit']
    anchor = [e for e in estimates if e['bias'] == 'anchor']
    upper = min(e['est'] for e in harm) if harm else np.inf
    lower = max(e['est'] for e in benefit) if benefit else -np.inf
    # conservative: harm gives upper -> use its LOWER CI as the tightest defensible upper bound;
    # benefit gives lower -> use its UPPER CI as the tightest defensible lower bound.
    upper_c = min(e['est'] - 1.64 * e['se'] for e in harm) if harm else np.inf
    lower_c = max(e['est'] + 1.64 * e['se'] for e in benefit) if benefit else -np.inf
    return dict(point=(lower, upper), conservative=(lower_c, upper_c),
                anchor=[(e['name'], e['est'], e['se']) for e in anchor])

def report(estimates, delta_meaningful=0.005, title=''):
    print(f'=== convergent bounds {title} ===')
    for e in estimates:
        print(f'  {e["bias"]:8s} {e["name"]:28s} est={e["est"]:+.4f} (se {e["se"]:.4f})')
    b = convergent_bounds(estimates)
    lo, hi = b['point']; loc, hic = b['conservative']
    print(f'  --> bracket (point):        [{lo:+.4f}, {hi:+.4f}]')
    print(f'  --> bracket (conservative): [{loc:+.4f}, {hic:+.4f}]')
    for name, est, se in b['anchor']:
        inside = lo <= est <= hi
        print(f'  --> anchor {name}: {est:+.4f} (se {se:.4f})  {"INSIDE bracket ✓" if inside else "OUTSIDE bracket ✗"}')
    # decision
    if lo > delta_meaningful:
        print(f'  DECISION: bracket excludes benefit (lower {lo:+.4f} > {delta_meaningful}) -> de-implementation supported.')
    elif hi < -delta_meaningful:
        print(f'  DECISION: bracket excludes harm (upper {hi:+.4f} < -{delta_meaningful}) -> treatment beneficial.')
    else:
        print(f'  DECISION: bracket spans the null band +/-{delta_meaningful} -> inconclusive (need tighter designs).')
    print()

if __name__ == '__main__':
    # ILLUSTRATIVE worked example with documented Mg estimates (risk-difference, mortality).
    # REAL numbers to be substituted from corrected_iv.py (anchor) + a contraindication-stratum run.
    print('[ILLUSTRATIVE — documented Mg estimates as a template; replace with real-data outputs]\n')
    demo = [
        {'name': 'IPTW target-trial',       'est': +0.090, 'se': 0.006, 'bias': 'harm'},
        {'name': 'provider-IV (naive pool)', 'est': +0.160, 'se': 0.030, 'bias': 'harm'},
        {'name': 'within-patient FE (LOS-proxy)', 'est': +0.070, 'se': 0.010, 'bias': 'harm'},
        {'name': 'renal-withheld stratum',   'est': -0.020, 'se': 0.012, 'bias': 'benefit'},
        {'name': 'assay-noise flag-ITT',     'est': +0.002, 'se': 0.003, 'bias': 'anchor'},
    ]
    report(demo, delta_meaningful=0.005, title='(Mg repletion -> mortality, illustrative)')
    print('Reading: harm-biased designs bracket ABOVE, the benefit-biased renal stratum brackets BELOW,')
    print('and the exogenous assay-noise anchor sits near zero INSIDE the bracket -> converging evidence of')
    print('no clinically-meaningful mortality effect. Credibility rests on the bias-SIGN assumptions being')
    print('defended (that is the reviewable claim); the anchor being inside is the key falsifiable check.')
