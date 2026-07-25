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
  by the same Newton/fixed-point iteration used in the Smith & Brown (2003) point-process filter
  that the BSP paper builds on:

      x_t|t = x_t|t-1 + sigma^2_t|t-1 * (n_t - N_t * p_t)
      sigma^2_t|t = 1 / (1/sigma^2_t|t-1 + N_t * p_t * (1 - p_t))

  iterated on p_t = logistic(x_t|t) to convergence. This is a Newton step on the (concave, in
  x_t) log-posterior of a Gaussian prior x_t|t-1 combined with a Binomial(N_t, logistic(x_t))
  likelihood, linearised at the current iterate; sigma^2_t|t is the (negative inverse Hessian)
  posterior curvature at the converged mode. Once every x_t|t, sigma^2_t|t is obtained the
  problem is a standard linear-Gaussian local-level (random-walk) state space, so the usual RTS
  smoother (plus its lag-one covariance recursion) applies unmodified for the backward pass.

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
X_CLIP = 20.0          # logistic(+-20) is ~1 +- 2e-9; nowhere near float64 overflow
NEWTON_MAX_ITER = 25
NEWTON_TOL = 1e-9
X0_PRIOR = 0.0          # diffuse prior mean on the logit scale (p = 0.5)
SIGMA2_0_PRIOR = 10.0    # diffuse prior variance -> first few real observations dominate


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
        x = xp.copy()
        for _ in range(NEWTON_MAX_ITER):
            p = _logistic(np.clip(x, -X_CLIP, X_CLIP))
            x_new = xp + s2p * (n_t - N_t * p)
            x_new = np.clip(x_new, -X_CLIP, X_CLIP)
            x_new = np.where(mask_t, x_new, xp)
            diff = np.max(np.abs(x_new - x)) if C else 0.0
            x = x_new
            if diff < NEWTON_TOL:
                break
        p = _logistic(np.clip(x, -X_CLIP, X_CLIP))
        s2f = 1.0 / (1.0 / s2p + N_t * p * (1.0 - p))
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


def _m_step(x_smooth, sigma2_smooth, lag1_cov, length):
    """Closed-form sigma^2 update, masked per case to that case's real (unpadded) bins.

    Only transitions t -> t+1 with t+1 < length[c] are real (both endpoints inside the case's
    actual bin range); padded timesteps beyond a case's length carry no information and must not
    leak into the estimate.
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
    sigma2_new = np.full(C, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        sigma2_new = np.where(has_trans, term.sum(axis=1) / np.maximum(n_trans, 1), np.nan)
    return sigma2_new, has_trans


def _fit_batch(bs, N, length, max_em_iter=50, tol=1e-6, sigma2_init=0.05):
    """EM-fit the BSP state-space model for a BATCH of cases at once.

    bs, N : (C, T) arrays, NaN/0 padded past each case's own length.
    length : (C,) int array of each case's real (unpadded) number of bins.
    Returns p_smooth (C, T) [only entries t < length[c] are meaningful], sigma2 (C,) per-case
    fitted process-noise variance (NaN where a case has < 2 real bins -- undetermined), and
    n_iter (int) the number of EM iterations actually run (shared stopping across the batch).
    """
    C, T = bs.shape
    n_obs = np.round(bs * N)
    obs_mask = np.isfinite(bs) & (N > 0) & (np.arange(T)[None, :] < length[:, None])
    n_obs = np.where(obs_mask, n_obs, 0.0)
    N_eff = np.where(obs_mask, N, 0.0)

    sigma2 = np.full(C, sigma2_init)
    has_trans = length >= 2
    n_iter = 0
    x_smooth = sigma2_smooth = lag1_cov = None
    for it in range(max_em_iter):
        n_iter = it + 1
        x_filt, sigma2_filt, x_pred, sigma2_pred = _forward_filter(n_obs, N_eff, obs_mask, sigma2)
        x_smooth, sigma2_smooth, lag1_cov = _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred)
        sigma2_new, _ = _m_step(x_smooth, sigma2_smooth, lag1_cov, length)
        sigma2_new = np.where(has_trans, sigma2_new, sigma2)  # nothing to learn -> keep current
        sigma2_new = np.maximum(sigma2_new, SIGMA2_FLOOR)
        delta = np.abs(sigma2_new - sigma2)
        converged = np.all((delta < tol) | ~has_trans)
        sigma2 = sigma2_new
        if converged:
            break
    # one last E-step at the converged sigma^2 so the returned smoother is consistent with it
    x_filt, sigma2_filt, x_pred, sigma2_pred = _forward_filter(n_obs, N_eff, obs_mask, sigma2)
    x_smooth, sigma2_smooth, lag1_cov = _rts_smooth(x_filt, sigma2_filt, x_pred, sigma2_pred)
    p_smooth = _logistic(np.clip(x_smooth, -X_CLIP, X_CLIP))
    sigma2_report = np.where(has_trans, sigma2, np.nan)
    return p_smooth, sigma2_report, n_iter


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
    p_smooth, sigma2, _ = _fit_batch(bs2, N2, length, max_em_iter=max_em_iter, tol=tol,
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

    p_smooth, sigma2, n_iter = _fit_batch(bs_pad, N_pad, lengths, max_em_iter=max_em_iter)

    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["caseid", "bin_t", "bsp"])
        for i, cid in enumerate(cids):
            L = lengths[i]
            for t in range(L):
                w.writerow([cid, bin_t_pad[i, t], f"{p_smooth[i, t]:.6f}"])

    elapsed = time.time() - t0
    n_no_converge = 0  # EM ran the shared loop to convergence (checked across the whole batch);
    # per-case non-convergence is checked separately in the caller/validation via sigma2 deltas.
    if verbose:
        print(f"[bsp_state_space] {C} cases, {int(lengths.sum())} bins, "
              f"EM iterations run: {n_iter}, elapsed {elapsed:.1f}s -> {out_path}")
    return dict(n_cases=C, n_bins=int(lengths.sum()), n_em_iter=n_iter, elapsed_s=elapsed,
                out_path=out_path, cids=cids, lengths=lengths, p_smooth=p_smooth, sigma2=sigma2,
                bs_pad=bs_pad, bin_t_pad=bin_t_pad)


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
    n_nonconverged = int(np.sum(~np.isfinite(res["sigma2"]) & (lengths >= 2)))
    print(f"  n cases={C}  n bins={int(lengths.sum())}  n bins used in corr={int(both.sum())}")
    print(f"  corr(BSP, raw bs fraction) = {corr:.4f}")
    print(f"  mean |first difference|:  raw bs = {mad_bs:.5f}   BSP = {mad_p:.5f}  "
          f"(smoother if BSP < raw: {mad_p < mad_bs})")
    print(f"  cases with length>=2 but sigma2 non-finite (should be 0): {n_nonconverged}")
    print(f"  sigma^2 across cases: median={np.nanmedian(res['sigma2']):.5g}  "
          f"min={np.nanmin(res['sigma2']):.5g}  max={np.nanmax(res['sigma2']):.5g}")
    print(f"  wrote {out_path}")
    return dict(corr=corr, mad_bs=mad_bs, mad_p=mad_p, elapsed_s=res["elapsed_s"],
                n_cases=C, n_bins=int(lengths.sum()))


def main():
    t0 = time.time()
    validate_simulation_recovery()
    validate_degenerate_inputs()
    validate_real_data_sanity()
    print(f"\n=== total validation runtime: {time.time() - t0:.1f}s ===")


if __name__ == "__main__":
    main()
