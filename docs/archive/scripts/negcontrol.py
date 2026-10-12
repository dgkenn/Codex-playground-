#!/usr/bin/env python3
"""
Negative-control empirical-null calibration (Schuemie/Madigan) — applies to ANY instrument's
estimates. Given a set of negative-control-OUTCOME estimates (effects that should be null under a
valid design), fit an empirical null N(mu, sd^2) of the systematic error, then calibrate a target
estimate's p-value/CI against that null instead of the theoretical N(0,1). A design with balAge~0
but a shifted empirical null is still biased — this catches residual confounding the balance test misses.
Self-test with synthetic negative controls.
"""
import numpy as np
from scipy import stats, optimize

def fit_null(est, se):
    """MLE of empirical null: true effect ~ N(mu, sd^2); observed = true + N(0, se^2)."""
    est = np.asarray(est, float); se = np.asarray(se, float)
    def negll(p):
        mu, logsd = p; v = np.exp(2*logsd) + se**2
        return 0.5*np.sum(np.log(2*np.pi*v) + (est-mu)**2/v)
    r = optimize.minimize(negll, [0.0, np.log(np.std(est)+1e-6)], method='Nelder-Mead')
    mu, sd = r.x[0], np.exp(r.x[1])
    return mu, sd

def calibrated_p(est, se, mu, sd):
    """two-sided calibrated p-value of a target estimate against the empirical null."""
    v = sd**2 + se**2
    z = (est - mu)/np.sqrt(v)
    return 2*stats.norm.sf(abs(z))

if __name__ == '__main__':
    rng = np.random.default_rng(7)
    # synthetic: negative controls with a systematic bias of +0.01 (residual confounding)
    true_bias = 0.01
    nc_est = rng.normal(true_bias, 0.008, 50) + rng.normal(0, 0.006, 50)
    nc_se = np.full(50, 0.006)
    mu, sd = fit_null(nc_est, nc_se)
    print(f'empirical null: mu={mu:+.4f} sd={sd:.4f}  (injected bias +{true_bias})')
    for name, est, se in [('true null (+0.002)', 0.002, 0.003),
                          ('modest signal (+0.03)', 0.03, 0.006),
                          ('strong signal (-0.05)', -0.05, 0.008)]:
        p_naive = 2*stats.norm.sf(abs(est/se))
        p_cal = calibrated_p(est, se, mu, sd)
        print(f'  {name:22s} est={est:+.3f} | p_naive={p_naive:.4f} | p_CALIBRATED={p_cal:.4f}')
    print('\nReading: calibration widens p-values by the systematic error the negative controls reveal,')
    print('so a design that "looks significant" but sits inside the empirical null is correctly demoted.')
