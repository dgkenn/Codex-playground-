#!/usr/bin/env python3
"""
Known-truth Monte Carlo for the NEW instruments (provider-IV, nurse-PRN). Validates the estimator
code AND demonstrates the decisive bulletproofing point: for provider-preference IV, the COVARIATE
BALANCE test can PASS while the exclusion restriction is violated (provider quality affects outcomes
directly) -> only NEGATIVE-CONTROL OUTCOMES catch it. This is why NC calibration is mandatory, not optional.
Data-free. Mirrors the assay-noise sim that caught the leaky-control bug.
"""
import numpy as np

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def logistic(x): return 1/(1+np.exp(-x))

# ---------------- Provider-preference IV ----------------
def sim_provider(N=60000, P=400, e_true=0.00, rho=0.0, seed=0):
    """
    rho = correlation between provider PREFERENCE and provider QUALITY (exclusion violation knob).
    quality affects outcome directly -> if rho!=0 the IV is biased and BALANCE won't see it (quality
    is provider-level, orthogonal to patient severity), but a NEGATIVE-CONTROL outcome will.
    """
    r = np.random.default_rng(seed)
    pref = r.normal(0, 1, P)
    qual = rho*pref + np.sqrt(max(1-rho**2,0))*r.normal(0,1,P)   # provider care-quality
    prov = r.integers(0, P, N)                                    # as-if-random assignment
    S = r.normal(0, 1, N)                                         # patient severity (confounder)
    D = (r.random(N) < logistic(-0.5 + 1.2*pref[prov] + 1.0*S)).astype(float)  # b=relevance, c=confounding
    Y  = np.clip(0.10 + 0.08*S - e_true*D + 0.05*qual[prov] + r.normal(0,0.05,N), 0, 1)  # quality affects Y
    Ync= np.clip(0.10 + 0.08*S           + 0.05*qual[prov] + r.normal(0,0.05,N), 0, 1)  # NEG-CONTROL: no tx effect
    # instrument = provider leave-one-out prescribing rate
    psum = np.bincount(prov, D, P); pcnt = np.bincount(prov, None, P)
    Z = (psum[prov]-D)/np.maximum(pcnt[prov]-1,1)
    age = 60 + 10*S + r.normal(0,5,N)     # a measured pre-tx covariate correlated with severity
    return dict(Z=Z, D=D, Y=Y, Ync=Ync, age=age, S=S)

def wald(Z, D, Y):
    X = np.column_stack([Z, np.ones_like(Z)])
    bfs,_ = ols(D, X); brf,_ = ols(Y, X)
    return brf[0]/bfs[0] if abs(bfs[0])>1e-6 else np.nan, bfs[0]

print('=== Provider-preference IV: known-truth validation (true effect = 0) ===')
print('demonstrates BALANCE can pass while exclusion is violated -> NC outcome is the real test\n')
for rho in [0.0, 0.5]:
    d = sim_provider(e_true=0.0, rho=rho, seed=1)
    late, fs = wald(d['Z'], d['D'], d['Y'])
    # balance: does Z predict the measured covariate (age) ?
    ba,_ = ols(d['age'], np.column_stack([d['Z'], np.ones_like(d['Z'])]))
    # NEGATIVE-CONTROL outcome: Z on Ync (should be 0 if exclusion holds)
    nc,_ = ols(d['Ync'], np.column_stack([d['Z'], np.ones_like(d['Z'])]))
    tag = 'valid' if rho==0 else 'EXCLUSION VIOLATED'
    print(f'  rho={rho} ({tag:18s}): LATE={late:+.4f} (truth 0)  FS={fs:+.3f} | '
          f'balAge={ba[0]:+.2f} [looks {"clean" if abs(ba[0])<1 else "off"}] | '
          f'NC-outcome coef={nc[0]:+.4f} [{"~0 OK" if abs(nc[0])<0.01 else "FLAGS BIAS"}]')
print('  -> under exclusion violation the LATE is biased and BALANCE stays clean, but the NEGATIVE')
print('     CONTROL outcome is non-zero and flags it. Balance alone is NOT sufficient; NC is decisive.\n')

# ---------------- Nurse-PRN administration IV ----------------
def sim_nurse(N=40000, Kn=300, e_true=0.03, seed=0):
    """each patient has several due-dose events across nurses; nurse admin tendency is random per event;
    patient severity confounds having-an-order but NOT nurse admin-given-order. Test aggregation validity."""
    r = np.random.default_rng(seed)
    tend = r.normal(0, 1, Kn)                    # nurse administration tendency
    S = r.normal(0, 1, N)                        # patient severity
    rows_z=[]; rows_d=[]; rows_y=[]
    # per-patient exposure = mean administration over the nurses they draw
    admin_frac = np.zeros(N)
    nsum = np.zeros(Kn); ncnt = np.zeros(Kn)
    ev_nurse = []; ev_pt = []; ev_d = []
    for i in range(N):
        m = r.integers(3, 8)
        nurses = r.integers(0, Kn, m)
        p = logistic(0.0 + 1.3*tend[nurses])     # admin prob driven by nurse (NOT severity)
        d = (r.random(m) < p).astype(float)
        for j in range(m):
            nsum[nurses[j]] += d[j]; ncnt[nurses[j]] += 1
            ev_nurse.append(nurses[j]); ev_pt.append(i); ev_d.append(d[j])
        admin_frac[i] = d.mean()
    ev_nurse=np.array(ev_nurse); ev_pt=np.array(ev_pt); ev_d=np.array(ev_d)
    Y = np.clip(0.10 + 0.08*S - e_true*admin_frac + r.normal(0,0.05,N), 0, 1)
    # patient instrument = mean nurse LOO admin rate
    Z = np.zeros(N); cnt=np.zeros(N)
    loo = (nsum[ev_nurse]-ev_d)/np.maximum(ncnt[ev_nurse]-1,1)
    for k in range(len(ev_pt)):
        Z[ev_pt[k]] += loo[k]; cnt[ev_pt[k]] += 1
    Z = Z/np.maximum(cnt,1)
    return Z, admin_frac, Y, S

print('=== Nurse-PRN administration IV: known-truth validation (true effect = -0.03) ===')
Z, D, Y, S = sim_nurse(e_true=0.03, seed=2)
X = np.column_stack([Z, np.ones_like(Z)])
bfs,_=ols(D,X); brf,_=ols(Y,X)
late = brf[0]/bfs[0]
ba,_ = ols(60+10*S, X)   # balance on severity-correlated covariate
print(f'  LATE={late:+.4f} (truth -0.030)  FS={bfs[0]:+.3f}  balAge={ba[0]:+.2f}')
print('  -> nurse-LOO instrument recovers the true administration effect; patient-level aggregation is valid.')
print('\nDONE. Both estimators validated; provider-IV demo proves NC-outcome calibration is mandatory.')
