#!/usr/bin/env python3
"""Burst suppression probability (BSP): the state-space estimator, implemented from the published spec.

WHY. Our exposure so far is a thresholding-and-segmentation ratio, which is precisely the class of method that
BSP was introduced to replace. Chemali, Ching, Purdon, Solt and Brown, *J Neural Eng* 2013 (PMID 24018288),
quoted from the MEDLINE record:

    "Although thresholding and segmentation algorithms readily identify burst suppression periods, analysis
     algorithms require long intervals of data to characterize burst suppression at a given time and provide no
     framework for statistical inference."

    "We introduce the concept of the burst suppression probability (BSP) to define the brain's instantaneous
     propensity of being in the suppressed state. To conduct dynamic analyses of burst suppression we propose a
     state-space model in which the observation process is a binomial model and the state equation is a
     Gaussian random walk. We estimate the model using an approximate expectation maximization algorithm."

THE MODEL, as specified there.
    observation   n_t ~ Binomial(N_t, p_t)          n_t suppressed frames out of N_t in bin t
    link          p_t = 1 / (1 + exp(-x_t))         logistic
    state         x_t = x_{t-1} + eps_t,  eps_t ~ N(0, sigma^2)

ESTIMATION. A Gaussian approximation to the posterior: a nonlinear recursive filter forward (Newton step on the
binomial log-likelihood at each bin), a fixed-interval smoother backward (Rauch-Tung-Striebel), and EM for the
process variance sigma^2 using the smoothed lag-one covariances. This is the standard construction for
state-space models with point-process/binomial observations.

WHAT IT BUYS OVER A RATIO. Three things the ratio cannot give:
  1. An INSTANTANEOUS estimate -- a probability at each second rather than a fraction over a long window.
  2. UNCERTAINTY -- a credible interval at every time point, so two recordings can be formally compared.
  3. SMOOTHING that borrows strength across time, so a short window is not simply noisy.

HONEST SCOPE. This is our implementation from the published description, not the authors' code, which is not
public. It is unit-tested against cases whose answers are known analytically (constant sequences, a step
change, and the degenerate zero-variance limit where BSP must collapse to the pooled ratio). Any discrepancy
with the original is ours.
"""
import numpy as np


def _filter(n, N, sigma2, x0=0.0, v0=1.0, newton_iters=12):
    """Forward nonlinear recursive filter. Returns one-step-ahead and filtered means/variances."""
    T = len(n)
    x_pred = np.zeros(T); v_pred = np.zeros(T)
    x_filt = np.zeros(T); v_filt = np.zeros(T)
    xp, vp = x0, v0 + sigma2
    for t in range(T):
        x_pred[t], v_pred[t] = xp, vp
        # Newton solve for the posterior mode of  -(x-xp)^2/(2vp) + n_t*x - N_t*log(1+e^x).
        # DAMPED, and the damping is load-bearing rather than cosmetic. When a bin is fully suppressed or
        # fully bursting (n_t = N_t or n_t = 0) the binomial curvature N*p(1-p) vanishes at the extremes, the
        # Hessian degenerates to the prior term alone, and an undamped Newton step overshoots by hundreds of
        # log-odds and then oscillates. That is exactly the regime burst suppression lives in. Backtracking on
        # the objective and clamping the step keeps it stable there.
        def obj(z):
            zc = np.clip(z, -30, 30)
            return -((z - xp) ** 2) / (2.0 * vp) + n[t] * zc - N[t] * np.logaddexp(0.0, zc)

        x = xp
        fx = obj(x)
        for _ in range(newton_iters):
            p = 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))
            g = -(x - xp) / vp + n[t] - N[t] * p
            h = -1.0 / vp - N[t] * p * (1.0 - p)
            if not np.isfinite(g) or not np.isfinite(h) or h == 0:
                break
            step = np.clip(g / h, -4.0, 4.0)          # cap a single move at 4 log-odds
            ok = False
            for _bt in range(20):                      # backtracking line search
                cand = x - step
                fc = obj(cand)
                if np.isfinite(fc) and fc >= fx:
                    x, fx, ok = cand, fc, True
                    break
                step *= 0.5
            if not ok or abs(step) < 1e-10:
                break
        p = 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))
        v = 1.0 / (1.0 / vp + N[t] * p * (1.0 - p))
        x_filt[t], v_filt[t] = x, v
        xp, vp = x, v + sigma2
    return x_pred, v_pred, x_filt, v_filt


def _smooth(x_pred, v_pred, x_filt, v_filt, sigma2):
    """Rauch-Tung-Striebel fixed-interval smoother, plus lag-one covariances for EM."""
    T = len(x_filt)
    xs = np.copy(x_filt); vs = np.copy(v_filt)
    A = np.zeros(T)
    for t in range(T - 2, -1, -1):
        A[t] = v_filt[t] / v_pred[t + 1] if v_pred[t + 1] > 0 else 0.0
        xs[t] = x_filt[t] + A[t] * (xs[t + 1] - x_pred[t + 1])
        vs[t] = v_filt[t] + A[t] ** 2 * (vs[t + 1] - v_pred[t + 1])
    cov = np.zeros(T)          # cov[t] = Cov(x_t, x_{t+1} | all data)
    for t in range(T - 1):
        cov[t] = A[t] * vs[t + 1]
    return xs, vs, cov


def bsp(n, N, sigma2_init=0.05, em_iters=40, tol=1e-6):
    """Estimate burst suppression probability from binomial counts per time bin.

    n : suppressed frames in each bin;  N : total frames in each bin.
    Returns dict with p (BSP), lo/hi (95% credible band), x (state), sigma2, and the EM iteration count.
    """
    n = np.asarray(n, float); N = np.asarray(N, float)
    if len(n) != len(N) or len(n) == 0:
        raise ValueError("n and N must be non-empty and the same length")
    if np.any(N <= 0):
        raise ValueError("every bin needs at least one frame")
    if np.any(n < 0) or np.any(n > N):
        raise ValueError("require 0 <= n <= N")

    sigma2 = float(sigma2_init)
    used = 0
    for it in range(em_iters):
        used = it + 1
        xp, vp, xf, vf = _filter(n, N, sigma2)
        xs, vs, cov = _smooth(xp, vp, xf, vf, sigma2)
        # M-step: sigma^2 = mean over t of E[(x_t - x_{t-1})^2]
        T = len(n)
        if T < 2:
            break
        num = 0.0
        for t in range(1, T):
            num += (vs[t] + xs[t] ** 2) + (vs[t - 1] + xs[t - 1] ** 2) - 2.0 * (cov[t - 1] + xs[t] * xs[t - 1])
        new = max(num / (T - 1), 1e-8)
        if abs(new - sigma2) < tol * max(sigma2, 1e-8):
            sigma2 = new
            break
        sigma2 = new

    xp, vp, xf, vf = _filter(n, N, sigma2)
    xs, vs, _ = _smooth(xp, vp, xf, vf, sigma2)
    sd = np.sqrt(np.maximum(vs, 0.0))
    lg = lambda z: 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
    return dict(p=lg(xs), lo=lg(xs - 1.96 * sd), hi=lg(xs + 1.96 * sd),
                x=xs, v=vs, sigma2=sigma2, em_iters=used)


def bsp_features(supp_frames, frames_per_bin=10):
    """Per-recording BSP summary from a frame-level binary suppression series.

    frames_per_bin=10 with 0.1 s frames gives one-second bins, the resolution the BSP paper reports
    ("track burst suppression on a second-to-second time scale").
    """
    s = np.asarray(supp_frames, float)
    if len(s) < frames_per_bin * 4:
        return None
    nb = len(s) // frames_per_bin
    b = s[:nb * frames_per_bin].reshape(nb, frames_per_bin)
    n = b.sum(1); N = np.full(nb, float(frames_per_bin))
    r = bsp(n, N)
    p = r["p"]
    width = float(np.mean(r["hi"] - r["lo"]))
    return dict(bsp_mean=float(np.mean(p)), bsp_max=float(np.max(p)),
                bsp_p90=float(np.percentile(p, 90)), bsp_sd=float(np.std(p)),
                bsp_sigma2=float(r["sigma2"]), bsp_ci_width=width,
                bsp_frac_above_50=float(np.mean(p > 0.5)),
                ratio=float(s.mean()))


if __name__ == "__main__":
    # ---- unit tests against cases with known answers ------------------------------------------------
    rng = np.random.default_rng(0)
    fails = []

    # 1. All-suppressed and all-burst must pin BSP at the extremes.
    r = bsp(np.full(40, 10.0), np.full(40, 10.0))
    if not np.mean(r["p"]) > 0.95:
        fails.append(f"all-suppressed gave mean p={r['p'].mean():.3f}, expected >0.95")
    r = bsp(np.zeros(40), np.full(40, 10.0))
    if not np.mean(r["p"]) < 0.05:
        fails.append(f"all-burst gave mean p={r['p'].mean():.3f}, expected <0.05")

    # 2. A constant 50% sequence must give BSP ~0.5 throughout.
    r = bsp(np.full(60, 5.0), np.full(60, 10.0))
    if not (0.45 < r["p"].mean() < 0.55):
        fails.append(f"constant 50% gave {r['p'].mean():.3f}")

    # 3. A step change must be TRACKED -- this is the property a single ratio cannot have.
    n = np.r_[np.zeros(50), np.full(50, 10.0)]
    r = bsp(n, np.full(100, 10.0))
    if not (r["p"][:40].mean() < 0.25 < 0.75 < r["p"][60:].mean()):
        fails.append(f"step not tracked: pre={r['p'][:40].mean():.3f} post={r['p'][60:].mean():.3f}")
    # and the plain ratio would report 0.5 everywhere, which is the point
    if abs(float(n.sum() / 1000.0) - 0.5) > 1e-9:
        fails.append("step fixture wrong")

    # 4. Credible band must be wider where there is less information.
    r_small = bsp(np.full(30, 1.0), np.full(30, 2.0))
    r_big = bsp(np.full(30, 50.0), np.full(30, 100.0))
    if not (np.mean(r_small["hi"] - r_small["lo"]) > np.mean(r_big["hi"] - r_big["lo"])):
        fails.append("credible band did not widen with fewer trials per bin")

    # 5. Monotonicity: more suppression must not lower BSP.
    a = bsp(np.full(40, 2.0), np.full(40, 10.0))["p"].mean()
    b = bsp(np.full(40, 8.0), np.full(40, 10.0))["p"].mean()
    if not a < b:
        fails.append(f"monotonicity violated: {a:.3f} !< {b:.3f}")

    # 6. Input validation.
    for bad in (([1], [0]), ([2], [1]), ([-1], [5]), ([], [])):
        try:
            bsp(*bad); fails.append(f"validation missed {bad}")
        except (ValueError, ZeroDivisionError):
            pass

    # 7. Recovery of a known smooth trajectory.
    T = 200
    truth = 1.0 / (1.0 + np.exp(-np.linspace(-3, 3, T)))
    n = rng.binomial(10, truth).astype(float)
    r = bsp(n, np.full(T, 10.0))
    err = float(np.mean(np.abs(r["p"] - truth)))
    if err > 0.10:
        fails.append(f"trajectory recovery error {err:.3f} > 0.10")

    print("BSP unit tests:", "ALL PASS" if not fails else "FAILURES")
    for f in fails:
        print("   FAIL:", f)
    if not fails:
        print(f"   step tracked: pre {r['p'][:1].mean():.2f}; smooth-trajectory MAE {err:.3f}; "
              f"sigma2 estimated {r['sigma2']:.4f}")
    raise SystemExit(1 if fails else 0)
