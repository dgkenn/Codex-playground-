#!/usr/bin/env python3
"""
Power / MDE analysis for the assay-noise IV (closes the 'is it decisive?' gap).
Two estimands:
  (A) LATE (=reduced-form / first-stage): needs scaling by a WEAK first stage -> imprecise.
  (B) flag-ITT (reduced form of noise-induced flag crossing): the de-implementation policy
      contrast; precise because it is NOT divided by the tiny first stage.
Analytic MDE (80% power, two-sided 0.05) + a simulation cross-check.
"""
import numpy as np
Z_A, Z_P = 1.96, 0.8416  # alpha/2, power quantiles
K = Z_A + Z_P

def mde_itt(n_eff, p, varZ=0.25):
    """MDE for reduced-form ITT (risk-difference outcome, base rate p), balanced instrument."""
    return K * np.sqrt(p * (1 - p) / (n_eff * varZ))

def summarize(label, n_eff, fs, rates):
    print(f'\n{label}: N_eff={n_eff:,}  first_stage={fs:.3f}  (LATE = ITT / {fs:.3f})')
    print(f'  {"outcome":18s} {"base":>6s} {"MDE_ITT(flag)":>14s} {"MDE_LATE":>10s}')
    for name, p in rates:
        mi = mde_itt(n_eff, p)
        ml = mi / fs
        print(f'  {name:18s} {p:6.3f} {mi*100:12.2f}pp {ml*100:8.1f}pp')

RATES = [('mortality', 0.04), ('new arrhythmia', 0.08),
         ('unplanned ICU xfer', 0.06), ('over-repletion', 0.20), ('LOS>median', 0.50)]

print('=== Assay-noise IV: MDE by estimand, N_eff, and first-stage strength ===')
print('MDE = minimum detectable effect at 80% power, two-sided 0.05. Balanced instrument (Var Z=0.25).')

# realistic scenarios
summarize('SINGLE-DRAW cohort (pessimistic FS)', 78000, 0.032, RATES)
summarize('SINGLE-DRAW cohort (optimistic FS)', 78000, 0.060, RATES)
summarize('RENEWAL pooled (~3x nodes/patient)', 230000, 0.032, RATES)
summarize('RENEWAL + K+Phos flags stacked (~4x)', 300000, 0.040, RATES)

print('\n--- INTERPRETATION ---')
print('LATE for MORTALITY is hopeless (MDE >> plausible 1-2pp effect) at any realistic FS.')
print('The flag-ITT (reduced form) is the DECISIVE, well-powered estimand for the policy question:')
print('  it directly tests "does noise-induced crossing of the reflexive-treatment flag change outcome".')
print('  Sub-percent ITT MDE on mortality => can rule OUT a clinically-meaningful flag effect.')

# ---- simulation cross-check of the ITT MDE claim ----
print('\n=== simulation cross-check: flag-ITT power at a set true effect ===')
rng_sigma = 0.134; FLAG = 2.0
def logistic(x): return 1/(1+np.exp(-x))
def sim_itt_reject(seed, theta, N=78000, fs_target=0.032):
    r = np.random.default_rng(seed)
    T = r.normal(2.0, 0.22, N)
    M1 = T + r.normal(0, rng_sigma, N); M2 = T + r.normal(0, rng_sigma, N)
    mid = (M1 + M2) / 2
    Z = (M2 < FLAG).astype(float)
    # calibrate reflexive jump b to hit ~fs_target
    D = (r.random(N) < logistic(-2.4 + 1.35 * Z + 1.6 * (FLAG - T))).astype(float)
    p = np.clip(0.04 + 0.10 * (FLAG - T) - theta * D, 0.001, 0.999)
    Y = (r.random(N) < p).astype(float)
    m = np.abs(mid - FLAG) <= 0.15
    Zm = Z[m]; Ym = Y[m]; Dm = D[m]
    c = mid[m] - FLAG; X = np.column_stack([Zm, np.ones_like(Zm), c, c*c])
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@Ym); res = Ym - X@b
    S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(len(Ym)/(len(Ym)-4))
    itt, se = b[0], np.sqrt(cov[0,0])
    fs = (np.linalg.pinv(X.T@X)@(X.T@Dm))[0]
    return abs(itt/se) > 1.96, fs, itt
for theta in [0.0, 0.02, 0.05]:
    res = [sim_itt_reject(s, theta) for s in range(30)]
    rej = np.mean([x[0] for x in res]); fs = np.mean([x[1] for x in res]); itt = np.mean([x[2] for x in res])
    print(f'  true LATE={-theta:+.3f}: realized FS={fs:.3f}  flag-ITT={itt:+.5f}  power(reject H0)={rej:.2f}')
print('\nDONE')
