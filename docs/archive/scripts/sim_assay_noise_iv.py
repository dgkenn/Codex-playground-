#!/usr/bin/env python3
"""
Monte Carlo validation of the assay-noise IV corrections (docs/ASSAY_NOISE_IV_METHODOLOGY.md).
Known-truth DGP for reflexive lab-triggered treatment. Demonstrates:
  (1) naive association is heavily confounded;
  (2) the leaky control (M1+M2)/2 leaves residual confounding (biased);
  (3) leave-one-out control is ~unbiased, and its bias SHRINKS as #draws grows
      -> the renewal structure improves VALIDITY, not just power;
  (4) pooled renewal estimator has lower variance than the single-draw design.
No real data. Validates the estimator code used on MIMIC.
"""
import numpy as np

rng = np.random.default_rng(20260701)
SIGMA = 0.134   # per-draw assay noise (mg/dL), matches MIMIC estimate
FLAG = 2.0

def logistic(x):
    return 1.0 / (1.0 + np.exp(-x))

def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    XtXi = np.linalg.pinv(X.T @ X)
    beta = XtXi @ (X.T @ y)
    resid = y - X @ beta
    n, k = X.shape
    S = X * resid[:, None]
    cov = XtXi @ (S.T @ S) @ XtXi * (n / (n - k))
    return beta, np.sqrt(np.diag(cov))

def ctrl_basis(t):
    c = np.asarray(t, float) - FLAG
    return np.column_stack([np.ones_like(c), c, c * c])

def simulate(N, ndraws, theta, a=-2.2, b=1.3, g=1.6, p0=0.06, s=0.10, seed=0):
    """
    T ~ true Mg. draws W_j = T + eps_j. Decision node = draw index 1 ('M2').
    D = reflexive treat: logit(a + b*1(W2<FLAG) + g*(FLAG-T)).  b=noise-instrument jump, g=confounding.
    Y = p0 + s*(FLAG-T) - theta*D + Bernoulli noise.  true causal RD of treatment = -theta.
    """
    r = np.random.default_rng(seed)
    T = r.normal(2.0, 0.22, N)
    W = T[:, None] + r.normal(0, SIGMA, (N, ndraws))
    M1 = W[:, 0]; M2 = W[:, 1]
    Z = (M2 < FLAG).astype(float)
    D = (r.random(N) < logistic(a + b * Z + g * (FLAG - T))).astype(float)
    pY = np.clip(p0 + s * (FLAG - T) - theta * D, 0.001, 0.999)
    Y = (r.random(N) < pY).astype(float)
    loo = W[:, [j for j in range(ndraws) if j != 1]].mean(axis=1)  # leave-node-1-out proxy
    return dict(T=T, M1=M1, M2=M2, Z=Z, D=D, Y=Y, contam=(M1 + M2) / 2, loo=loo)

def late(d, ctrl, band=0.15):
    """Wald LATE = RF/FS controlling for ctrl (quad), within |ctrl-FLAG|<=band."""
    m = np.abs(ctrl - FLAG) <= band
    Z = d['Z'][m]; D = d['D'][m]; Y = d['Y'][m]; C = ctrl_basis(ctrl[m])
    X = np.column_stack([Z, C])
    bfs, sfs = ols(D, X); brf, srf = ols(Y, X)
    fs, rf = bfs[0], brf[0]
    # balance on TRUE severity (we know T): cov of Z with T | ctrl
    bT, sT = ols(d['T'][m], X)
    return dict(fs=fs, rf=rf, late=(rf / fs if abs(fs) > 1e-6 else np.nan),
                n=int(m.sum()), balT=bT[0], balT_se=sT[0], rf_se=srf[0])

def naive(d):
    b, se = ols(d['Y'], np.column_stack([d['D'], np.ones_like(d['D'])]))
    return b[0], se[0]

print('=== Monte Carlo validation of corrected assay-noise IV ===')
print(f'SIGMA={SIGMA}  N=200000/rep  true treatment RD = -theta\n')

for theta in [0.00, 0.03]:
    print(f'--- TRUE causal RD = {-theta:+.3f} (theta={theta}) ---')
    # single replication, large N, to show bias structure
    d = simulate(200000, ndraws=2, theta=theta, seed=1)
    nb, nse = naive(d)
    print(f'  naive  Y~D (confounded)          : {nb:+.4f} (SE {nse:.4f})   [target {-theta:+.3f}]')
    for label, key in [('contaminated ctrl (M1+M2)/2', 'contam'), ('corrected ctrl M1 (LOO,k=2)', 'loo')]:
        R = late(d, d[key])
        print(f'  {label:32s}: LATE {R["late"]:+.4f}  FS {R["fs"]:+.4f}  '
              f'RF {R["rf"]:+.5f}  balT {R["balT"]:+.4f}({R["balT_se"]:.4f})  n={R["n"]}')
    # bias of LOO shrinks with more draws (renewal improves validity)
    print('  leave-one-out bias vs #draws (renewal -> better T control):')
    for k in [2, 3, 5, 9]:
        dk = simulate(200000, ndraws=k, theta=theta, seed=2)
        R = late(dk, dk['loo'])
        print(f'     k={k:2d} draws: LATE {R["late"]:+.4f}  balT {R["balT"]:+.4f}  (truth {-theta:+.3f})')
    print()

# ---- variance: pooled renewal vs single-draw, over replications ----
print('--- precision: single-draw vs pooled renewal (repeated sims, theta=0) ---')
def single_draw_late(seed):
    d = simulate(30000, ndraws=2, theta=0.0, seed=seed)
    return late(d, d['loo'])['late']

def renewal_late(seed):
    """pool all near-flag draws per patient with leave-one-out proxy + patient noise."""
    r = np.random.default_rng(seed)
    N = 30000; k = 8
    T = r.normal(2.0, 0.22, N)
    W = T[:, None] + r.normal(0, SIGMA, (N, k))
    Zs=[]; Ds=[]; Ys=[]; Cs=[]
    treated = np.zeros(N)
    # sequential reflexive decisions (absorbing)
    Dever = np.zeros(N)
    node_records = []
    for j in range(k):
        Zj = (W[:, j] < FLAG).astype(float)
        loo = W[:, [q for q in range(k) if q != j]].mean(axis=1)
        elig = (np.abs(loo - FLAG) <= 0.15) & (treated == 0)
        pj = logistic(-2.2 + 1.3 * Zj + 1.6 * (FLAG - T))
        act = (r.random(N) < pj) & (treated == 0)
        # record eligible nodes (pre-treatment)
        for i in np.where(elig)[0]:
            node_records.append((i, Zj[i], 1.0 if act[i] else 0.0, loo[i]))
        Dever = np.where(act & (treated == 0), 1.0, Dever)
        treated = np.where(act, 1.0, treated)
    pY = np.clip(0.06 + 0.10 * (FLAG - T) - 0.0 * Dever, 0.001, 0.999)
    Y = (r.random(N) < pY).astype(float)
    if not node_records:
        return np.nan
    idx = np.array([n[0] for n in node_records])
    Z = np.array([n[1] for n in node_records]); D = np.array([n[2] for n in node_records])
    C = ctrl_basis(np.array([n[3] for n in node_records]))
    Yv = Y[idx]
    X = np.column_stack([Z, C])
    bfs, _ = ols(D, X); brf, _ = ols(Yv, X)
    return brf[0] / bfs[0] if abs(bfs[0]) > 1e-6 else np.nan

sd = np.array([single_draw_late(s) for s in range(40)])
rn = np.array([renewal_late(s + 100) for s in range(40)])
sd = sd[np.isfinite(sd)]; rn = rn[np.isfinite(rn)]
print(f'  single-draw LATE: mean {sd.mean():+.4f}  SD {sd.std():.4f}  (n_reps {len(sd)})')
print(f'  pooled renewal  : mean {rn.mean():+.4f}  SD {rn.std():.4f}  (n_reps {len(rn)})')
print(f'  variance ratio (single/renewal) = {(sd.std()**2)/(rn.std()**2):.2f}x  '
      f'-> renewal is {(sd.std()/rn.std()):.2f}x more precise')

# ---- DRIFT scenario: does the midpoint control break? ----
print('\n--- DRIFT: true severity trends between draws (T_j = T0 + drift*j) ---')
def simulate_drift(N, ndraws, theta, drift, seed):
    r = np.random.default_rng(seed)
    T0 = r.normal(2.0, 0.22, N)
    j = np.arange(ndraws)
    Ttraj = T0[:, None] + drift * j[None, :]          # true value at each draw
    W = Ttraj + r.normal(0, SIGMA, (N, ndraws))
    M1 = W[:, 0]; M2 = W[:, 1]
    Tdec = Ttraj[:, 1]                                 # true severity at decision node (draw 1)
    Z = (M2 < FLAG).astype(float)
    D = (r.random(N) < logistic(-2.2 + 1.3 * Z + 1.6 * (FLAG - Tdec))).astype(float)
    pY = np.clip(0.06 + 0.10 * (FLAG - Tdec) - theta * D, 0.001, 0.999)
    Y = (r.random(N) < pY).astype(float)
    loo = W[:, [q for q in range(ndraws) if q != 1]].mean(axis=1)
    return dict(T=Tdec, M1=M1, M2=M2, Z=Z, D=D, Y=Y, contam=(M1 + M2) / 2, loo=loo)

for drift in [0.0, 0.05, 0.10]:
    d = simulate_drift(200000, ndraws=2, theta=0.0, drift=drift, seed=7)
    Rc = late(d, d['contam']); Rm = late(d, d['loo'])
    print(f'  drift={drift:+.2f}: midpoint LATE {Rc["late"]:+.4f} (balT {Rc["balT"]:+.4f}) | '
          f'M1-only LATE {Rm["late"]:+.4f} (balT {Rm["balT"]:+.4f})   truth 0.000')
    # many-draw LOO under drift (use nearest neighbors would be better; plain mean shown)
    dk = simulate_drift(200000, ndraws=9, theta=0.0, drift=drift, seed=8)
    Rk = late(dk, dk['loo'])
    print(f'              9-draw LOO mean LATE {Rk["late"]:+.4f} (balT {Rk["balT"]:+.4f})')
print('\nDONE')
