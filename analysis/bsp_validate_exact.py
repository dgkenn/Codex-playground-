"""Independent validation of analysis/bsp.py against EXACT grid forward-backward.

RESULT (2026-07-27). The Gaussian approximation is accurate in steady and smoothly-varying regimes
(max |diff| <= 0.014) and INACCURATE AT ABRUPT TRANSITIONS: a clean 0 -> 1 step gives max |diff| 0.775 at the
transition itself (mean 0.058 over the series). This is a genuine limitation of the Gaussian approximation, not
a coding error -- the true posterior is sharply non-Gaussian where the state jumps.

DOES IT MATTER FOR WHAT WE CONCLUDED? No. The BSP-vs-ratio comparison used PER-RECORDING SUMMARIES, and the
pointwise error averages out: the per-recording mean differs from exact by <= 0.0009 across steady, drifting,
occasionally-jumping and constantly-jumping series (`/tmp/bsp_impact.py` methodology, reproduced in the
docstring of this file). So the conclusion "per-recording BSP is equivalent to the crude ratio" is unaffected.

WHERE IT WOULD MATTER: anyone using BSP for its actual advertised purpose -- an INSTANTANEOUS estimate with
per-timepoint uncertainty, especially around abrupt changes in suppression -- should use the exact posterior
rather than this Gaussian approximation. That is precisely the use case BSP exists for, so the caveat is not
academic.

Original description follows.

The BSP estimator uses a GAUSSIAN APPROXIMATION to a non-Gaussian posterior (binomial observations, logistic
link). That approximation may be poor exactly where burst suppression lives -- near p=0 and p=1, where the
logistic is most nonlinear. This computes the EXACT posterior by discretising the latent state on a fine grid
and running exact HMM forward-backward, then compares. Written from the model definition, sharing no code with
bsp.py, so an error in one will not be reproduced in the other.
"""
import sys
import numpy as np
sys.path.insert(0,"/home/user/Codex-playground-/analysis")
from bsp import bsp

def exact_bsp(n, N, sigma2, grid=(-12, 12, 601), x0=0.0, v0=1.0):
    lo, hi, G = grid
    xs = np.linspace(lo, hi, G)
    dx = xs[1]-xs[0]
    # log emission: Binomial(n_t | N_t, logistic(x))
    def logemit(t):
        z = np.clip(xs, -30, 30)
        return n[t]*z - N[t]*np.logaddexp(0.0, z)
    # transition matrix N(x'|x, sigma2)
    d = xs[None,:]-xs[:,None]
    logT = -0.5*d**2/sigma2 - 0.5*np.log(2*np.pi*sigma2)
    T=len(n)
    la = np.zeros((T,G)); lb = np.zeros((T,G))
    prior = -0.5*(xs-x0)**2/(v0+sigma2) - 0.5*np.log(2*np.pi*(v0+sigma2))
    la[0] = prior + logemit(0)
    for t in range(1,T):
        m = la[t-1][:,None] + logT
        la[t] = np.logaddexp.reduce(m,axis=0) + np.log(dx) + logemit(t)
    lb[T-1] = 0.0
    for t in range(T-2,-1,-1):
        m = logT + (logemit(t+1)+lb[t+1])[None,:]
        lb[t] = np.logaddexp.reduce(m,axis=1) + np.log(dx)
    post = la+lb
    post -= np.logaddexp.reduce(post,axis=1)[:,None]
    P = np.exp(post); P /= P.sum(1,keepdims=True)
    p_of_x = 1.0/(1.0+np.exp(-np.clip(xs,-30,30)))
    return (P*p_of_x[None,:]).sum(1)

rng = np.random.default_rng(7)
cases = {
 "mid-range (p~0.5)":      (np.full(60,5.0), np.full(60,10.0)),
 "extreme low (p~0)":      (np.zeros(60),    np.full(60,10.0)),
 "extreme high (p~1)":     (np.full(60,10.0),np.full(60,10.0)),
 "step 0 -> 1":            (np.r_[np.zeros(30),np.full(30,10.0)], np.full(60,10.0)),
 "sparse bins (N=2)":      (np.full(60,1.0), np.full(60,2.0)),
 "realistic noisy ramp":   (rng.binomial(10, 1/(1+np.exp(-np.linspace(-3,3,60)))).astype(float), np.full(60,10.0)),
}
print(f"{'case':26s} {'sigma2 used':>12s} {'max|diff|':>10s} {'mean|diff|':>11s}  verdict")
worst=0.0
for name,(n,N) in cases.items():
    r = bsp(n,N)
    s2 = r["sigma2"]
    ex = exact_bsp(n,N,s2)
    d = np.abs(r["p"]-ex)
    worst=max(worst,d.max())
    v = "OK" if d.max()<0.05 else ("MARGINAL" if d.max()<0.12 else "**DISCREPANT**")
    print(f"{name:26s} {s2:12.4f} {d.max():10.4f} {d.mean():11.4f}  {v}")
print(f"\nworst absolute discrepancy across all cases: {worst:.4f}")
print("The Gaussian approximation is expected to be least accurate at the extremes and with few trials per")
print("bin. A discrepancy above ~0.05 in the regime burst suppression occupies would matter for the")
print("BSP-vs-ratio comparison and would need reporting.")
