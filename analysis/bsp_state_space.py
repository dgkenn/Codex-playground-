#!/usr/bin/env python3
r"""State-space Burst Suppression Probability (BSP) estimator.

Replaces the hard-threshold "fraction of a 30 s bin flagged suppressed" burst-suppression
metric with a smooth *latent probability* estimated by a state-space model, following:

    Chemali J, Westover MB, Purdon PL, Brown EN. "Burst suppression probability algorithms:
    state-space methods for tracking EEG burst suppression." J Neural Eng. 2013;10(5):056017.

MODEL
-----
For a single case, index 30 s bins by t = 1..T. Let N_t be the number of 0.1 s frames in bin t
(N_t = 300 for a full 30 s bin) and n_t the number of those frames scored as suppressed
(n_t = round(bs_t * N_t), bs_t the stored suppressed fraction). The model is

    latent state    x_t = x_{t-1} + e_t ,     e_t ~ N(0, sigma^2)     (random walk WITHIN a case)
    BSP             p_t = logistic(x_t) = 1 / (1 + exp(-x_t))
    observation     n_t ~ Binomial(N_t, p_t)

sigma^2 (the state's process-noise variance) is a single free parameter estimated per case by
expectation-maximisation; x_t is a continuous "burst-suppression logit" whose logistic transform
is the smooth BSP curve.

ESTIMATION (EM)
----------------
E-step -- Gaussian-approximation forward filter + fixed-interval (RTS) smoother.
  The binomial observation is not Gaussian, so at each forward step the posterior mode is found
  by Newton iteration on the (strictly concave, in x_t) log-posterior of a Gaussian prior
  x_t|t-1 ~ N(x_t|t-1, sigma^2_t|t-1) combined with a Binomial(N_t, logistic(x_t)) likelihood:

      log g(x) = -(x - x_t|t-1)^2 / (2 sigma^2_t|t-1) + n_t*log(p) + (N_t - n_t)*log(1-p) + const,
                 p = logistic(x)
      g'(x)  = -(x - x_t|t-1)/sigma^2_t|t-1 + (n_t - N_t*p)
      g''(x) = -1/sigma^2_t|t-1 - N_t*p*(1-p)

      Newton step:  x <- x - g'(x)/g''(x)
                       = x + [ (n_t - N_t*p) - (x - x_t|t-1)/sigma^2_t|t-1 ]
                             / [ 1/sigma^2_t|t-1 + N_t*p*(1-p) ]

  iterated on p = logistic(x) to convergence; sigma^2_t|t = 1 / (1/sigma^2_t|t-1 + N_t*p*(1-p))
  evaluated at the converged mode is the (negative inverse Hessian) posterior curvature there.

  NOTE ON A LITERATURE PITFALL: the point-process filter this problem is modelled on (Smith &
  Brown 2003; Chemali et al. 2013 eq. 8-9) writes the update as x_t|t = x_t|t-1 + sigma^2_t|t *
  (n_t - N_t*p_t) with NO explicit (x - x_t|t-1)/sigma^2_t|t-1 correction term. That form's fixed
  point coincides with the true posterior mode only in the point-process/continuous-time limit
  (bin width dt -> 0, at most one event per bin, sigma^2_t|t-1 -> sigma^2_t|t), where the dropped
  term vanishes. For our 30 s / N_t=300 binomial bins that limit does not hold: an early
  implementation of exactly that formula was checked here against a numerical root-find of g'(x)
  and does NOT return the true mode, and drove the EM to a wildly inflated sigma^2 (e.g.
  1e5-1e6 instead of the true 0.005-0.5) on both the developer's and an independent reviewer's
  simulation-recovery test. The full Newton step above (with the prior-deviation term, and using
  the CURRENT-iterate p in both the numerator and the denominator, not last-iteration's) is the
  form actually implemented and is exact for every N_t. Once every x_t|t, sigma^2_t|t is
  obtained the problem is a standard linear-Gaussian local-level (random-walk) state space, so
  the usual RTS smoother (plus its lag-one covariance identity) applies unmodified for the
  backward pass.

M-step -- update sigma^2 in closed form from the smoothed states and the smoothed lag-one
  covariances (Shumway & Stoffer's EM for the local-level / random-walk model):

      sigma^2_hat = mean_t [ (x_t|T - x_{t-1}|T)^2 + sigma^2_t|T + sigma^2_{t-1}|T - 2 sigma^2_{t,t-1}|T ]

EM alternates E- and M-steps to convergence (or `max_em_iter`). sigma^2 is fit PER CASE, never
pooled across cases.

MISSING DATA: a bin with bs NaN (or N_t == 0) is treated as an unobserved timepoint -- the
forward step is a pure random-walk PREDICTION with no Newton/observation update. This is the
principled choice for a state-space model: the state still evolves, we simply have no
information to update it with. It never produces NaN and never discards the bin's timestamp.

VECTORISATION: `_fit_batch` runs the *same* per-timestep math for many cases at once (arrays
shaped (n_cases, T_max), cases padded/masked to their own length) so that the sequential loop is
over TIME ONCE, not over (cases x time). This is what makes the full ~1900-case, ~850k-bin real
data pass finish in well under a minute instead of hours of pure per-case Python looping.

CONSTRAINTS: numpy only (no scipy.optimize, no pymc). Fully deterministic given inputs (the
Newton iteration and EM are both plain fixed-point recursions -- nothing stochastic in the
estimator; simulations in the validation section below are explicitly seeded).

IDENTIFIABILITY AT SATURATION (real-data fix, read before changing X_CLIP / the M-step prior)
------------------------------------------------------------------------------------------
Real bs series contain long runs of bs EXACTLY 0 (median ~66% of a case's bins) and, less often,
runs of bs EXACTLY 1. In a long run of n_t=0, the log-likelihood n_t*log(p)+(N_t-n_t)*log(1-p)
keeps increasing as x -> -infinity (there is no finite MLE), so only the Gaussian prior stops x
from drifting arbitrarily negative -- and it stops it less and less as sigma^2 grows, because a
bigger sigma^2 means a weaker prior pull each step. An early implementation of this estimator
used a numerically-motivated clip of |x|<=20 (chosen only so exp() never overflows) and NO prior
on sigma^2. On real HEEDB/VitalDB-style bins this produced a positive feedback loop, confirmed
by instrumenting the per-case EM trajectory: during a long 0-run x is pushed towards -20, during
a 1-run towards +20, so a single genuine suppressed<->unsuppressed transition contributes a huge
(~40^2=1600) squared-jump term to the M-step average; that inflates sigma^2; a bigger sigma^2
weakens the prior even further next E-step, pushing x closer to the clip during the NEXT
saturated run, which inflates the NEXT M-step's sigma^2 more. Measured on real cases this
diverged from a sigma^2 EM seed of 0.05 to the 10-40 range within ~10 iterations and then
settled into a period-2 LIMIT CYCLE (never converging to a point) once x hit the +-20 clip on
both sides -- e.g. one real case oscillated 47.07 / 37.15 / 47.07 / 37.15 ... forever. The
resulting BSP was 5x JUMPIER than the raw fraction it was supposed to be smoothing (mean
|first difference| 0.193 vs 0.036) and correlated with it only 0.68 -- i.e. the "smoother" was
amplifying noise, which is definitionally broken for a fixed-interval smoother.

Two changes fix this, and BOTH are principled modelling decisions, not numerical hacks:

  1. X_CLIP is now RESOLUTION-DRIVEN, not just an anti-overflow guard: with N_t=300 frames per
     bin, no bin can report a suppressed fraction finer than 1/300, so p is not statistically
     distinguishable from 0 or 1 beyond roughly the half-frame resolution 1/(2*N_t). We clip
     |x| at logit(1 - 1/(2*N_t)) = ln(2*N_t - 1) (~6.4 for N_t=300, computed from
     DEFAULT_N_FRAMES at import time) instead of 20. This bounds the worst-case single-jump
     term at a value the data can actually support, rather than an arbitrary float64-safety
     margin ~10x too loose for this application.
  2. The M-step MLE update for sigma^2 is replaced by the MAP update under a weakly-informative
     conjugate Inverse-Gamma(SIGMA2_PRIOR_A, SIGMA2_PRIOR_B) prior (the natural conjugate prior
     for a Gaussian random walk's innovation variance):

         sigma^2_MAP = (sum_t term_t + 2*SIGMA2_PRIOR_B) / (n_trans + 2*SIGMA2_PRIOR_A + 2)

     with SIGMA2_PRIOR_A=3, SIGMA2_PRIOR_B=0.12, i.e. prior mode = SIGMA2_PRIOR_B/(SIGMA2_PRIOR_A+1)
     = 0.03 (a middling value in the smooth-to-jumpy range this module's own simulation grid
     spans, 0.001-0.5) and effective prior weight 2*SIGMA2_PRIOR_A+2 = 8 pseudo-transitions --
     small next to a typical case's ~400 real transitions (so it is overwhelmed by real data
     whenever there is enough of it) but large enough to damp the runaway feedback loop above
     during early EM iterations and for short/low-transition-count cases.

  Both changes are ON by default; SIGMA2_CAP (see below) is kept ONLY as a documented last-resort
  safety net, not the primary fix -- see validate_real_data_sanity()'s printed diagnostics for
  whether it ever actually binds (if it never binds, the two changes above are doing the work).

  SENSITIVITY: tightening X_CLIP trades off the ability to represent a case that is genuinely
  and confidently at p~0 or p~1 for many consecutive bins (its BSP will floor/ceiling at
  logistic(+-6.4) =~0.0017/0.9983 rather than at the literal 0/1 the raw fraction can hit) against
  breaking the sigma^2 runaway; given N_t=300 cannot statistically support finer resolution than
  that in the first place, this is not a meaningful loss of information. The IG prior shifts
  small-transition-count cases' sigma^2 towards 0.03; see validate_real_data_sanity() for the
  fitted-sigma^2 distribution this produces on real cases.
"""
import csv
import math
import sys
import time
from collections import OrderedDict

import numpy as np

FRAME_S = 0.1
BIN_S = 30.0
DEFAULT_N_FRAMES = round(BIN_S / FRAME_S)  # 300

SIGMA2_FLOOR = 1e-8
SIGMA2_CAP = 5.0        # last-resort safety net only, see "IDENTIFIABILITY AT SATURATION" above
# resolution-driven clip: p is not distinguishable from 0/1 finer than half a frame in N_t=300
X_CLIP = math.log(2 * DEFAULT_N_FRAMES - 1)  # ~6.395
NEWTON_MAX_ITER = 25
NEWTON_TOL = 1e-9
X0_PRIOR = 0.0          # diffuse prior mean on the logit scale (p = 0.5)
SIGMA2_0_PRIOR = 10.0    # diffuse prior variance -> first few real observations dominate

# weakly-informative conjugate Inverse-Gamma(SIGMA2_PRIOR_A, SIGMA2_PRIOR_B) ridge prior on the
# per-case process-noise variance sigma^2, used in the M-step; see docstring above.
SIGMA2_PRIOR_A = 3.0
SIGMA2_PRIOR_B = 0.12    # prior mode = SIGMA2_PRIOR_B / (SIGMA2_PRIOR_A + 1) = 0.03


def _logistic(x):
    """Numerically stable logistic, safe for the whole clipped domain."""
    out = np.empty_like(x, dtype=float)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ex = np.exp(x[~pos])
    out[~pos] = ex / (1.0 + ex)
    return out


def _forward_filter(n, N, obs_mask, sigma2, x0=X0_PRIOR, sigma2_0=SIGMA2_0_PRIOR):
    """Gaussian-approximation (Newton-mode) forward filter, vectorised across cases (axis 0).

    n, N, obs_mask : (C, T) arrays -- observed suppressed-frame count, frame count, and whether
        bin t actually carries an observation (False = missing bs / N==0 -> prediction only).
    sigma2 : (C,) per-case process-noise variance for this E-step.
    Returns x_filt, sigma2_filt, x_pred, sigma2_pred, all shaped (C, T).
    """
    C, T = n.shape
    x_filt = np.empty((C, T))
    sigma2_filt = np.empty((C, T))
    x_pred = np.empty((C, T))
    sigma2_pred = np.empty((C, T))
    x_prev = np.full(C, x0)
    sigma2_prev = np.full(C, sigma2_0)
    for t in range(T):
        xp = x_prev
        s2p = sigma2_prev + sigma2
        x_pred[:, t] = xp
        sigma2_pred[:, t] = s2p
        mask_t = obs_mask[:, t]
        n_t = n[:, t]
        N_t = N[:, t]
        inv_s2p = 1.0 / s2p
        x = np.clip(xp.copy(), -X_CLIP, X_CLIP)
        # Newton-bisection hybrid (the classic "rtsafe" safeguard) to find the posterior mode.
        # A NAIVE damped/step-capped Newton loop was tried first and is NOT safe here: an
        # early version simply clipped the Newton step to +-10, and for a case where the prior
        # x_pred sits near one clip boundary while the current bin's own MLE sits near the
        # other, the capped step landed almost exactly at the opposite boundary every time,
        # producing an EXACT period-2 cycle (x oscillating between +3.6 and -6.4 forever,
        # confirmed by tracing the iteration by hand) that never satisfied the convergence
        # tolerance and left x_filt at a value the data did not support (verified: bs=0.20 --
        # true mode logit(0.20)=-1.39 -- was returned as x_filt=+3.6, logistic(3.6)=0.97). Since
        # g is strictly concave (g'' < 0 everywhere), g' is monotonically decreasing, and the
        # true mode is bracketed by [-X_CLIP, X_CLIP] for every (xp, s2p) pair we ever construct
        # (g'(-X_CLIP) >= 0 and g'(X_CLIP) <= 0 always, since xp itself is always within
        # [-X_CLIP, X_CLIP]). So: take the Newton step when it lands inside the current bracket
        # (fast, usually 2-4 iterations), otherwise bisect (guaranteed to shrink the bracket by
        # 2x) -- this cannot cycle or diverge.
        lo = np.full(C, -X_CLIP)
        hi = np.full(C, X_CLIP)
        for _ in range(NEWTON_MAX_ITER):
            p = _logistic(x)
            W = N_t * p * (1.0 - p)                       # binomial curvature (information) at x
            grad = (n_t - N_t * p) - (x - xp) * inv_s2p    # g'(x)
            denom = inv_s2p + W                            # -g''(x), always > 0 (strictly concave)
            x_newton = x + grad / denom
            lo = np.where(grad > 0, np.maximum(lo, x), lo)  # root is to the right of x
            hi = np.where(grad < 0, np.minimum(hi, x), hi)  # root is to the left of x
            in_bracket = (x_newton >= lo) & (x_newton <= hi)
            x_bisect = 0.5 * (lo + hi)
            x_new = np.where(in_bracket, x_newton, x_bisect)
            x_new = np.where(mask_t, x_new, xp)
            diff = np.max(np.abs(x_new - x)) if C else 0.0
            x = x_new
            if diff < NEWTON_TOL:
                break
        p = _logistic(np.clip(x, -X_CLIP, X_CLIP))
        s2f = 1.0 / (inv_s2p + N_t * p * (1.0 - p))
        s2f = np.where(mask_t, s2f, s2p)
        x_filt[:, t] = x
        sigma2_filt[:, t] = s2f
        x_prev = x
        sigma2_prev = s2f
    return x_filt, sigma2_filt, x_pred, sigma2_pred


def _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred):
    """Fixed-interval (Rauch-Tung-Striebel) smoother + lag-one covariance.

    Standard local-level (random-walk, transition coefficient 1) smoother -- valid here because
    after the Newton E-step, (x_filt, sigma2_filt) already IS a linear-Gaussian filtered
    mean/variance pair, regardless of the non-Gaussian binomial observation that produced it.
    Returns x_smooth, sigma2_smooth (C, T) and lag1_cov (C, T-1) with
    lag1_cov[:, t] = Cov(x_t, x_{t+1} | all data).

    The lag-one covariance uses the exact backward-Markov identity for RTS smoothers: since
    x_t | x_{t+1}, y_{1:T} has the same law as x_t | x_{t+1}, y_{1:t} (the state process is
    Markov), the smoothed mean of x_t given x_{t+1} is the affine map
    x_filt[t] + A[t]*(x_{t+1} - x_pred[t+1]) used in the recursion below, so
        Cov(x_t, x_{t+1} | y_{1:T}) = A[t] * Var(x_{t+1} | y_{1:T}) = A[t] * sigma2_smooth[t+1] ,
    with no separate backward covariance recursion needed.
    """
    C, T = x_filt.shape
    x_smooth = np.empty((C, T))
    sigma2_smooth = np.empty((C, T))
    lag1_cov = np.zeros((C, max(T - 1, 0)))
    x_smooth[:, T - 1] = x_filt[:, T - 1]
    sigma2_smooth[:, T - 1] = sigma2_filt[:, T - 1]
    if T < 2:
        return x_smooth, sigma2_smooth, lag1_cov
    A = np.empty((C, T - 1))
    for t in range(T - 1):
        A[:, t] = sigma2_filt[:, t] / sigma2_pred[:, t + 1]
    for t in range(T - 2, -1, -1):
        x_smooth[:, t] = x_filt[:, t] + A[:, t] * (x_smooth[:, t + 1] - x_pred[:, t + 1])
        sigma2_smooth[:, t] = sigma2_filt[:, t] + A[:, t] ** 2 * (
            sigma2_smooth[:, t + 1] - sigma2_pred[:, t + 1]
        )
    lag1_cov = A * sigma2_smooth[:, 1:]
    return x_smooth, sigma2_smooth, lag1_cov


def _m_step(x_smooth, sigma2_smooth, lag1_cov, length, prior_a=SIGMA2_PRIOR_A, prior_b=SIGMA2_PRIOR_B):
    """MAP sigma^2 update under a conjugate Inverse-Gamma(prior_a, prior_b) ridge prior, masked
    per case to that case's real (unpadded) bins.

    Only transitions t -> t+1 with t+1 < length[c] are real (both endpoints inside the case's
    actual bin range); padded timesteps beyond a case's length carry no information and must not
    leak into the estimate. See the module docstring ("IDENTIFIABILITY AT SATURATION") for why
    the plain MLE (prior_a=prior_b=0) is unstable on real, saturation-heavy bs series and why the
    IG ridge is the principled fix rather than a hack.
    """
    C, T = x_smooth.shape
    if T < 2:
        return np.full(C, np.nan), np.zeros(C, dtype=bool)
    t_idx = np.arange(1, T)  # transition endpoints t = 1..T-1 (0-indexed)
    trans_valid = t_idx[None, :] < length[:, None]  # (C, T-1)
    dx2 = (x_smooth[:, 1:] - x_smooth[:, :-1]) ** 2
    term = dx2 + sigma2_smooth[:, 1:] + sigma2_smooth[:, :-1] - 2.0 * lag1_cov
    term = np.where(trans_valid, term, 0.0)
    n_trans = trans_valid.sum(axis=1)
    has_trans = n_trans > 0
    S = term.sum(axis=1)
    sigma2_new = np.where(has_trans, (S + 2.0 * prior_b) / (n_trans + 2.0 * prior_a + 2.0), np.nan)
    return sigma2_new, has_trans


def _fit_batch(bs, N, length, max_em_iter=50, tol=1e-6, sigma2_init=0.05):
    """EM-fit the BSP state-space model for a BATCH of cases at once.

    bs, N : (C, T) arrays, NaN/0 padded past each case's own length.
    length : (C,) int array of each case's real (unpadded) number of bins.
    Returns p_smooth (C, T) [only entries t < length[c] are meaningful], sigma2 (C,) per-case
    fitted process-noise variance (NaN where a case has < 2 real bins -- undetermined), n_iter
    (int) the number of EM iterations actually run (shared stopping across the batch), and a
    diagnostics dict: n_not_converged (per-case sigma^2 delta still > tol at the stopping
    iteration -- with the IG ridge prior this should be 0 or near-0; see module docstring) and
    n_capped (per-case final sigma^2 hit SIGMA2_CAP, the last-resort safety net -- if this is
    ever > 0 it means the primary fix, the ridge prior + resolution clip, was not sufficient by
    itself for that case, and is reported honestly rather than hidden).
    """
    C, T = bs.shape
    n_obs = np.round(bs * N)
    obs_mask = np.isfinite(bs) & (N > 0) & (np.arange(T)[None, :] < length[:, None])
    n_obs = np.where(obs_mask, n_obs, 0.0)
    N_eff = np.where(obs_mask, N, 0.0)

    sigma2 = np.full(C, sigma2_init)
    has_trans = length >= 2
    n_iter = 0
    not_converged = np.zeros(C, dtype=bool)
    for it in range(max_em_iter):
        n_iter = it + 1
        x_filt, sigma2_filt, x_pred, sigma2_pred = _forward_filter(n_obs, N_eff, obs_mask, sigma2)
        x_smooth, sigma2_smooth, lag1_cov = _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred)
        sigma2_new, _ = _m_step(x_smooth, sigma2_smooth, lag1_cov, length)
        sigma2_new = np.where(has_trans, sigma2_new, sigma2)  # nothing to learn -> keep current
        sigma2_new = np.clip(sigma2_new, SIGMA2_FLOOR, SIGMA2_CAP)
        delta = np.abs(sigma2_new - sigma2)
        not_converged = (delta >= tol) & has_trans
        sigma2 = sigma2_new
        if not np.any(not_converged):
            break
    n_capped = int(np.sum(has_trans & (sigma2 >= SIGMA2_CAP - 1e-12)))
    # one last E-step at the converged sigma^2 so the returned smoother is consistent with it
    x_filt, sigma2_filt, x_pred, sigma2_pred = _forward_filter(n_obs, N_eff, obs_mask, sigma2)
    x_smooth, sigma2_smooth, lag1_cov = _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred)
    p_smooth = _logistic(np.clip(x_smooth, -X_CLIP, X_CLIP))
    sigma2_report = np.where(has_trans, sigma2, np.nan)
    diag = dict(n_not_converged=int(np.sum(not_converged)), n_capped=n_capped)
    return p_smooth, sigma2_report, n_iter, diag


def bsp(bs_fractions, n_frames=None, max_em_iter=50, tol=1e-6, sigma2_init=0.05):
    """Estimate the smoothed Burst Suppression Probability for ONE case.

    Parameters
    ----------
    bs_fractions : 1D array-like, length T. Per-30s-bin suppressed fraction in [0, 1]. NaN marks
        a bin with no observation (handled as a missing/skipped update, see module docstring).
    n_frames : 1D array-like, length T, or None. Number of 0.1 s frames in each bin (N_t). If
        None, every bin is assumed full-length (DEFAULT_N_FRAMES = 300).
    max_em_iter : maximum EM iterations.

    Returns
    -------
    p_smooth : np.ndarray, length T -- the smoothed BSP series (RTS-smoothed, i.e. uses the
        whole case, forward AND backward, not just a causal filter).
    sigma2 : float -- the case's fitted state-space process-noise variance (NaN if T < 2, i.e.
        there are no bin-to-bin transitions to estimate it from).
    """
    bs_fractions = np.asarray(bs_fractions, dtype=float)
    T = bs_fractions.shape[0]
    if n_frames is None:
        N = np.full(T, float(DEFAULT_N_FRAMES))
    else:
        N = np.asarray(n_frames, dtype=float)
        if N.shape[0] != T:
            raise ValueError("bs_fractions and n_frames must have the same length")
    bs2 = bs_fractions.reshape(1, T)
    N2 = N.reshape(1, T)
    length = np.array([T])
    p_smooth, sigma2, _, _ = _fit_batch(bs2, N2, length, max_em_iter=max_em_iter, tol=tol,
                                         sigma2_init=sigma2_init)
    return p_smooth[0], float(sigma2[0])


# --------------------------------------------------------------------------------------------
# real-data CSV pipeline
# --------------------------------------------------------------------------------------------

def _read_bridge_bins(in_path):
    """Read bridge_bins.csv and group (bin_t, bs) rows by caseid, preserving first-seen case
    order and sorting each case's bins by bin_t (the requirement)."""
    cases = OrderedDict()
    with open(in_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cid = row["caseid"]
            bin_t = float(row["bin_t"])
            bs_raw = row["bs"]
            try:
                bs_val = float(bs_raw) if bs_raw not in ("", "nan", "NaN", "NA") else float("nan")
            except ValueError:
                bs_val = float("nan")
            cases.setdefault(cid, []).append((bin_t, bs_val))
    for cid in cases:
        cases[cid].sort(key=lambda r: r[0])
    return cases


def run_from_csv(in_path="/tmp/eeg_probe/bridge_bins.csv", out_path="/tmp/eeg_probe/bsp_bins.csv",
                  max_em_iter=50, n_frames=DEFAULT_N_FRAMES, verbose=True):
    """Compute per-case BSP over bridge_bins.csv and write caseid,bin_t,bsp to out_path.

    All cases are EM-fit in ONE vectorised batch call (padded to the longest case) -- this is
    what keeps the ~1900-case, ~850k-row real pass fast (see module docstring: vectorise across
    cases, not fewer EM iterations).
    """
    t0 = time.time()
    cases = _read_bridge_bins(in_path)
    cids = list(cases.keys())
    C = len(cids)
    lengths = np.array([len(cases[c]) for c in cids])
    T_max = int(lengths.max()) if C else 0

    bs_pad = np.full((C, T_max), np.nan)
    N_pad = np.zeros((C, T_max))
    bin_t_pad = np.full((C, T_max), np.nan)
    for i, cid in enumerate(cids):
        rows = cases[cid]
        L = len(rows)
        bin_t_pad[i, :L] = [r[0] for r in rows]
        bs_pad[i, :L] = [r[1] for r in rows]
        N_pad[i, :L] = n_frames

    p_smooth, sigma2, n_iter, diag = _fit_batch(bs_pad, N_pad, lengths, max_em_iter=max_em_iter)

    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["caseid", "bin_t", "bsp"])
        for i, cid in enumerate(cids):
            L = lengths[i]
            for t in range(L):
                w.writerow([cid, bin_t_pad[i, t], f"{p_smooth[i, t]:.6f}"])

    elapsed = time.time() - t0
    if verbose:
        print(f"[bsp_state_space] {C} cases, {int(lengths.sum())} bins, "
              f"EM iterations run: {n_iter}, elapsed {elapsed:.1f}s -> {out_path}")
        print(f"[bsp_state_space] cases with sigma^2 delta still >= tol at stop: "
              f"{diag['n_not_converged']}/{C}; cases where sigma^2 hit SIGMA2_CAP="
              f"{SIGMA2_CAP}: {diag['n_capped']}/{C}")
    return dict(n_cases=C, n_bins=int(lengths.sum()), n_em_iter=n_iter, elapsed_s=elapsed,
                out_path=out_path, cids=cids, lengths=lengths, p_smooth=p_smooth, sigma2=sigma2,
                bs_pad=bs_pad, bin_t_pad=bin_t_pad, diag=diag)


# --------------------------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------------------------

def _simulate_case(T, sigma2_true, N=DEFAULT_N_FRAMES, x0=-2.0, seed=0):
    rng = np.random.default_rng(seed)
    e = rng.normal(0.0, math.sqrt(sigma2_true), size=T)
    x_true = x0 + np.cumsum(e)
    x_true[0] = x0
    p_true = 1.0 / (1.0 + np.exp(-x_true))
    n_obs = rng.binomial(N, p_true)
    bs_obs = n_obs / N
    return x_true, p_true, bs_obs


def validate_simulation_recovery(T=1000, sigma2_values=(0.001, 0.02, 0.2), N=DEFAULT_N_FRAMES):
    print("\n=== VALIDATION 1: simulation recovery ===")
    results = []
    for i, s2 in enumerate(sigma2_values):
        x_true, p_true, bs_obs = _simulate_case(T, s2, N=N, seed=100 + i)
        p_hat, sigma2_hat = bsp(bs_obs, n_frames=np.full(T, N))
        corr = float(np.corrcoef(p_true, p_hat)[0, 1])
        rel_err = (sigma2_hat - s2) / s2
        print(f"  true sigma^2={s2:<8.4f}  fitted sigma^2={sigma2_hat:<10.5f}  "
              f"rel.err={rel_err:+.2%}   corr(p_true,p_hat)={corr:.4f}")
        results.append((s2, sigma2_hat, corr))
    return results


def validate_degenerate_inputs():
    print("\n=== VALIDATION 2: degenerate inputs ===")
    ok = True

    bs = np.zeros(200)
    p, s2 = bsp(bs)
    bad = not np.all(np.isfinite(p))
    ok &= not bad
    print(f"  all-zero bs (T=200):        max p={p.max():.6f}  sigma2={s2:.6g}  "
          f"finite={np.all(np.isfinite(p))}  {'FAIL' if bad else 'ok'}")

    bs = np.ones(200)
    p, s2 = bsp(bs)
    bad = not np.all(np.isfinite(p))
    ok &= not bad
    print(f"  all-one bs  (T=200):        min p={p.min():.6f}  sigma2={s2:.6g}  "
          f"finite={np.all(np.isfinite(p))}  {'FAIL' if bad else 'ok'}")

    bs = np.array([0.37])
    p, s2 = bsp(bs)
    bad = (not np.all(np.isfinite(p)))  # sigma2 NaN is EXPECTED/correct for a single bin
    ok &= not bad
    print(f"  single bin (T=1):           p={p} sigma2={s2} (NaN expected, no transitions)  "
          f"{'FAIL' if bad else 'ok'}")

    bs = np.array([0.0, 0.1, np.nan, np.nan, 0.5, 0.9, np.nan, 0.05])
    p, s2 = bsp(bs)
    bad = not np.all(np.isfinite(p))
    ok &= not bad
    print(f"  NaN-containing (3/8 missing): p={np.round(p, 4)}")
    print(f"                               sigma2={s2:.6g}  finite={np.all(np.isfinite(p))}  "
          f"{'FAIL' if bad else 'ok'}")

    print(f"  -> all degenerate-input checks {'PASSED' if ok else 'FAILED'}")
    return ok


def debug_em_trajectory(in_path="/tmp/eeg_probe/bridge_bins.csv", n_cases=5, max_em_iter=50,
                         sigma2_init=0.05):
    """Print, for a handful of REAL cases, the fraction of saturated (bs==0 / bs==1) bins and the
    EM trajectory of sigma^2 across iterations -- direct evidence for/against the runaway
    described in the module docstring ("IDENTIFIABILITY AT SATURATION"), not just an assertion
    that it is fixed.
    """
    print(f"\n=== INSTRUMENTATION: per-case sigma^2 EM trajectory on real cases (n={n_cases}) ===")
    cases = _read_bridge_bins(in_path)
    cids = list(cases.keys())[:n_cases]
    for cid in cids:
        rows = cases[cid]
        T = len(rows)
        if T < 30:
            continue
        v = np.array([r[1] for r in rows])
        frac0 = float(np.mean(v == 0.0))
        frac1 = float(np.mean(v == 1.0))
        bs2 = v.reshape(1, T)
        N2 = np.full((1, T), float(DEFAULT_N_FRAMES))
        n_obs = np.round(bs2 * N2)
        obs_mask = np.isfinite(bs2) & (N2 > 0)
        sigma2 = np.array([sigma2_init])
        traj = []
        for _ in range(max_em_iter):
            x_filt, sigma2_filt, x_pred, sigma2_pred = _forward_filter(n_obs, N2, obs_mask, sigma2)
            x_smooth, sigma2_smooth, lag1 = _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred)
            sigma2_new, _ = _m_step(x_smooth, sigma2_smooth, lag1, np.array([T]))
            sigma2_new = np.clip(sigma2_new, SIGMA2_FLOOR, SIGMA2_CAP)
            traj.append(float(sigma2_new[0]))
            sigma2 = sigma2_new
        span = max(traj) - min(traj[-10:])
        oscillating = span > 1e-4 and len(set(round(x, 3) for x in traj[-6:])) > 1
        print(f"  case {cid}: T={T} frac(bs==0)={frac0:.3f} frac(bs==1)={frac1:.3f}")
        print(f"    sigma^2 iters 1-8:   {[round(x, 4) for x in traj[:8]]}")
        print(f"    sigma^2 last 6:      {[round(x, 4) for x in traj[-6:]]}  "
              f"{'STILL OSCILLATING/NOT CONVERGED' if oscillating else '(settled)'}")


def validate_real_data_sanity(in_path="/tmp/eeg_probe/bridge_bins.csv",
                               out_path="/tmp/eeg_probe/bsp_bins.csv", max_em_iter=50):
    print("\n=== VALIDATION 3: sanity vs. raw fraction on real data ===")
    res = run_from_csv(in_path=in_path, out_path=out_path, max_em_iter=max_em_iter, verbose=True)
    bs_pad, p_smooth, lengths = res["bs_pad"], res["p_smooth"], res["lengths"]
    C, T_max = bs_pad.shape
    valid = np.arange(T_max)[None, :] < lengths[:, None]
    bs_valid = np.where(valid & np.isfinite(bs_pad), bs_pad, np.nan)
    p_valid = np.where(valid, p_smooth, np.nan)
    both = np.isfinite(bs_valid) & np.isfinite(p_valid)
    corr = float(np.corrcoef(bs_valid[both], p_valid[both])[0, 1])

    def mean_abs_diff1(mat, mask_valid_pair):
        d = np.abs(mat[:, 1:] - mat[:, :-1])
        return float(d[mask_valid_pair].mean())

    pair_valid = valid[:, 1:] & valid[:, :-1] & np.isfinite(bs_pad[:, 1:]) & np.isfinite(bs_pad[:, :-1])
    mad_bs = mean_abs_diff1(bs_pad, pair_valid)
    mad_p = mean_abs_diff1(p_smooth, pair_valid)
    n_nan_sigma2 = int(np.sum(~np.isfinite(res["sigma2"]) & (lengths >= 2)))
    s2 = res["sigma2"]
    s2_finite = s2[np.isfinite(s2)]
    frac_gt_half = float(np.mean(s2_finite > 0.5)) if s2_finite.size else float("nan")
    print(f"  n cases={C}  n bins={int(lengths.sum())}  n bins used in corr={int(both.sum())}")
    print(f"  corr(BSP, raw bs fraction) = {corr:.4f}   (target: > 0.9)")
    print(f"  mean |first difference|:  raw bs = {mad_bs:.5f}   BSP = {mad_p:.5f}   "
          f"ratio BSP/raw = {mad_p / mad_bs:.3f}  (target: << 1.0; smoother iff ratio < 1)")
    print(f"  cases with length>=2 but sigma2 NaN (should be 0): {n_nan_sigma2}")
    print(f"  sigma^2 across cases: 5%={np.nanpercentile(s2, 5):.5g}  "
          f"50%={np.nanpercentile(s2, 50):.5g}  95%={np.nanpercentile(s2, 95):.5g}  "
          f"max={np.nanmax(s2):.5g}")
    print(f"  fraction of cases with sigma^2 > 0.5 (previously-failing regime): {frac_gt_half:.1%}")
    print(f"  EM diagnostics: cases with sigma^2 delta >= tol at stop: "
          f"{res['diag']['n_not_converged']}/{C};  cases where sigma^2 hit the SIGMA2_CAP="
          f"{SIGMA2_CAP} safety net: {res['diag']['n_capped']}/{C}")
    print(f"  wrote {out_path}")
    return dict(corr=corr, mad_bs=mad_bs, mad_p=mad_p, ratio=mad_p / mad_bs, elapsed_s=res["elapsed_s"],
                n_cases=C, n_bins=int(lengths.sum()), sigma2_pctl=(float(np.nanpercentile(s2, 5)),
                float(np.nanpercentile(s2, 50)), float(np.nanpercentile(s2, 95)), float(np.nanmax(s2))),
                frac_sigma2_gt_half=frac_gt_half, diag=res["diag"])


def main():
    t0 = time.time()
    validate_simulation_recovery()
    validate_degenerate_inputs()
    debug_em_trajectory()
    validate_real_data_sanity()
    print(f"\n=== total validation runtime: {time.time() - t0:.1f}s ===")


if __name__ == "__main__":
    main()
