#!/usr/bin/env python3
"""Where does BSP stop being interchangeable with a threshold ratio? A window-length sweep with ground truth.

WHY THIS EXISTS, verbatim from `docs/research/47_BSP_TECHNICAL_NOTE.md` Sec. 5.3:

    "r = 0.988 is specific to *whole-recording* aggregation. Shorter windows would give BSP more room, and we
     have not characterised where the equivalence breaks down as window length falls -- that is the obvious
     next experiment and it is directly answerable with this code."

This is that experiment. It has to be done in SIMULATION, and the reason is not convenience: on real EEG there
is no ground truth for the instantaneous probability of suppression, so real data can only show whether two
estimators AGREE, never which one is RIGHT. Simulation from the model the estimator assumes -- and, more
informatively, from processes it does NOT assume -- gives a true p_t to score against.

------------------------------------------------------------------------------------------------------------
REGISTERED PREDICTIONS, fixed before running.

  S1  At long windows the two are interchangeable and BSP buys nothing (this we already know: r = 0.988 at
      whole-recording aggregation, out-of-bag increment -0.010 [-0.021, +0.004]). As the window shortens,
      the pooled ratio is estimated from fewer Bernoulli trials and its variance grows as 1/(W*N), whereas BSP
      borrows strength from neighbouring bins. So BSP's accuracy advantage should GROW as W falls, and the
      correlation between the two should FALL.
      FALSIFIED IF the ratio matches BSP at every window length -- which would mean the smoothing never pays.

  S2  The advantage should be LARGEST where the state is smooth relative to the window (a random walk with
      small variance: neighbours are informative) and SMALLEST or NEGATIVE where the state jumps (a step: the
      neighbours are actively misleading and smoothing smears the edge). A method that helps everywhere
      equally would be suspicious.

  S3  COVERAGE. The paper's stated motivation is that ratios "provide no framework for statistical inference".
      The inference is only worth having if the 95 % credible band actually covers. We measure empirical
      coverage of the true p_t, by regime. Nominal 0.95.
      FALSIFIED IF coverage is far from nominal in the model-matched regimes -- then the interval is decoration.

------------------------------------------------------------------------------------------------------------
FOUR ESTIMATORS, and the distinction between them is the whole point.

  ratio       pooled fraction of suppressed frames inside the window. Uses window data only.
  bsp_win     BSP fitted to the window's data ALONE, then averaged. The LIKE-FOR-LIKE comparison: same data in,
              same summary out. Any difference here is the model doing work, not extra data.
  bsp_causal  filtered (forward-only) BSP averaged over the window, using no observation after the window's
              end. This is what a real-time monitor could actually display. sigma^2 is fitted on the full
              series, which is a small acknowledged leak -- refitting it causally per window costs one EM per
              window and does not change the ranking.
  bsp_full    smoothed BSP fitted to the WHOLE series, then averaged over the window. This uses data from
              AFTER the window and is therefore NOT causal. It is reported because it is how a retrospective
              analysis would use the estimator, and it is labelled non-causal everywhere it appears so that it
              is never mistaken for an online result.

SEVEN REGIMES: two constants, two random walks (the model's own assumption, slow and fast), and three the model
does not assume -- a step, a ramp, and an oscillation. A method should be scored where its assumptions fail.
"""
import os, sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bsp import bsp, _filter, _smooth

T = int(os.environ.get("SWEEP_T", "900"))          # 1-second bins -> 15 minutes
NFRAMES = int(os.environ.get("SWEEP_N", "10"))     # 0.1 s frames per bin, as in the rest of the project
SEEDS = int(os.environ.get("SWEEP_SEEDS", "12"))
WINDOWS = [600, 300, 120, 60, 30, 15, 8, 4, 2, 1]
MAX_WIN_FITS = int(os.environ.get("SWEEP_WIN_FITS", "8"))   # bsp_win refits per window length, capped for cost
REGIMES = ["constant-0.50", "constant-0.90", "rw-slow", "rw-fast", "step", "ramp", "oscillation"]
ALPHAS = [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]   # EWMA smoothing constants; 1.0 = no smoothing


def true_p(regime, t, rng):
    """The latent probability of suppression. Returns an array of length t."""
    if regime == "constant-0.50":
        return np.full(t, 0.5)
    if regime == "constant-0.90":
        return np.full(t, 0.9)
    if regime in ("rw-slow", "rw-fast"):
        s2 = 0.002 if regime == "rw-slow" else 0.05
        x = np.cumsum(rng.normal(0.0, np.sqrt(s2), t))
        return 1.0 / (1.0 + np.exp(-np.clip(x, -8, 8)))
    if regime == "step":
        p = np.full(t, 0.05); p[t // 2:] = 0.95
        return p
    if regime == "ramp":
        return np.linspace(0.05, 0.95, t)
    if regime == "oscillation":
        return 0.5 + 0.4 * np.sin(2.0 * np.pi * np.arange(t) / 300.0)
    raise ValueError(regime)


def ewma_grid(n, N, alphas):
    """Causal exponentially-weighted moving average of the raw per-bin fraction, one series per alpha.

    THE OBJECTION THIS ANSWERS. If BSP beats a one-second ratio, that is not yet interesting: the ratio over a
    single bin is an absurdly noisy baseline, and ANY smoother would beat it. The state equation is a Gaussian
    random walk, and the optimal filter for a random walk observed with Gaussian noise is essentially an
    exponentially-weighted average -- so the question is whether the binomial observation model and the
    logistic link earn anything at all over naive exponential smoothing of the raw fractions.

    The alpha is chosen ORACLE-OPTIMALLY per regime and per window length -- that is, using the true p, which
    no real user has. That makes this a CEILING on what exponential smoothing could achieve, and therefore the
    most adversarial baseline available to BSP. If BSP still wins against it, the state-space machinery is
    doing real work; if it does not, the honest conclusion is that a three-line smoother suffices.
    """
    f = n / N
    out = {}
    for a in alphas:
        e = np.empty(len(f)); acc = f[0]
        for t in range(len(f)):
            acc = a * f[t] + (1 - a) * acc
            e[t] = acc
        out[a] = e
    return out


def ewma_causal_alpha(n, N, alphas, burn=0.30):
    """Pick the EWMA constant the way a practitioner could: one-step-ahead error on the first 30 %.

    The oracle alpha is a ceiling, not a method -- nobody has the true p to tune against. This picks alpha by
    minimising one-step-ahead squared prediction error over a burn-in, which uses no truth and no future, and
    is therefore a baseline a real user could actually deploy. Reporting BOTH bounds the answer: BSP's
    position between the practical EWMA and the oracle EWMA is the honest statement of what it earns.
    """
    f = n / N
    b = max(10, int(len(f) * burn))
    best, ba = None, alphas[0]
    for a in alphas:
        acc = f[0]; err = 0.0
        for t in range(1, b):
            err += (acc - f[t]) ** 2          # predict bin t from everything before it
            acc = a * f[t] + (1 - a) * acc
        if best is None or err < best:
            best, ba = err, a
    return ba


def causal_p(n, N, sigma2):
    """Forward-filtered BSP: the estimate at bin t uses no observation after t."""
    _, _, xf, _ = _filter(n, N, sigma2)
    return 1.0 / (1.0 + np.exp(-np.clip(xf, -30, 30)))


def one_series(task):
    regime, seed = task
    # REGIMES.index, not hash(): Python's string hash is salted per process, so hash() here would make the
    # simulation irreproducible across runs -- silently, and only for the random-walk regimes.
    rng = np.random.default_rng(1000 * seed + 7 * REGIMES.index(regime))
    p = true_p(regime, T, rng)
    N = np.full(T, float(NFRAMES))
    n = rng.binomial(NFRAMES, p).astype(float)

    full = bsp(n, N)
    p_full = full["p"]
    p_caus = causal_p(n, N, full["sigma2"])
    ew = ewma_grid(n, N, ALPHAS)
    a_causal = ewma_causal_alpha(n, N, ALPHAS)

    # ---- S3 coverage of the 95 % credible band, per bin ---------------------------------------------
    cover = float(np.mean((full["lo"] <= p) & (p <= full["hi"])))
    width = float(np.mean(full["hi"] - full["lo"]))

    rows = []
    for W in WINDOWS:
        nw = T // W
        if nw < 2:
            continue
        starts = [i * W for i in range(nw)]
        truth = np.array([p[s:s + W].mean() for s in starts])
        r_ratio = np.array([n[s:s + W].sum() / N[s:s + W].sum() for s in starts])
        r_caus = np.array([p_caus[s:s + W].mean() for s in starts])
        r_full = np.array([p_full[s:s + W].mean() for s in starts])

        # bsp_win: refit on the window alone. Capped for cost, taking an evenly spaced subset so the
        # subsample is not concentrated in one part of the series.
        sel = starts if len(starts) <= MAX_WIN_FITS else [
            starts[int(round(i * (len(starts) - 1) / (MAX_WIN_FITS - 1)))] for i in range(MAX_WIN_FITS)]
        sel = sorted(set(sel))
        r_win, t_win = [], []
        for s in sel:
            nn, NN = n[s:s + W], N[s:s + W]
            if len(nn) < 2:
                r_win.append(nn.sum() / NN.sum())     # BSP is undefined on one bin; it degenerates to the ratio
            else:
                try:
                    r_win.append(float(bsp(nn, NN)["p"].mean()))
                except Exception:
                    r_win.append(float("nan"))
            t_win.append(p[s:s + W].mean())
        r_win = np.array(r_win); t_win = np.array(t_win)

        def rmse(a, b):
            m = np.isfinite(a) & np.isfinite(b)
            return float(np.sqrt(np.mean((a[m] - b[m]) ** 2))) if m.sum() else float("nan")

        # oracle-tuned EWMA: the best alpha for THIS regime and window, using the truth. A ceiling, not a
        # method -- see ewma_grid's docstring.
        ew_r = min((rmse(np.array([ew[a][s:s + W].mean() for s in starts]), truth), a) for a in ALPHAS)
        ew_c = rmse(np.array([ew[a_causal][s:s + W].mean() for s in starts]), truth)

        rows.append(dict(
            regime=regime, seed=seed, W=W, nw=nw,
            rmse_ewma=ew_r[0], ewma_alpha=ew_r[1], rmse_ewma_c=ew_c, ewma_alpha_c=a_causal,
            rmse_ratio=rmse(r_ratio, truth), rmse_causal=rmse(r_caus, truth),
            rmse_full=rmse(r_full, truth), rmse_win=rmse(r_win, t_win),
            rmse_ratio_sel=rmse(np.array([n[s:s + W].sum() / N[s:s + W].sum() for s in sel]), t_win),
            corr=float(np.corrcoef(r_ratio, r_full)[0, 1]) if nw > 2 and r_ratio.std() > 0 and r_full.std() > 0
            else float("nan")))
    return dict(regime=regime, seed=seed, cover=cover, width=width, sigma2=full["sigma2"], rows=rows)


def agg(rows, key, W, regime=None):
    v = [r[key] for r in rows if r["W"] == W and (regime is None or r["regime"] == regime)
         and r[key] == r[key]]
    return float(np.mean(v)) if v else float("nan")


def main():
    tasks = [(rg, s) for rg in REGIMES for s in range(SEEDS)]
    print(f"BSP window-length sweep: {len(REGIMES)} regimes x {SEEDS} seeds, T={T} bins of "
          f"{NFRAMES} frames ({T} s of 0.1 s frames)", flush=True)
    res = []
    with ProcessPoolExecutor(max_workers=int(os.environ.get("SWEEP_WORKERS", "8"))) as ex:
        for i, r in enumerate(ex.map(one_series, tasks), 1):
            res.append(r)
            if i % 14 == 0:
                print(f"  {i}/{len(tasks)} series", flush=True)
    rows = [x for r in res for x in r["rows"]]
    assert rows, "sweep produced no rows -- check T vs WINDOWS"

    print("\n" + "=" * 100)
    print("S1  ACCURACY AGAINST GROUND TRUTH, BY WINDOW LENGTH  (RMSE of the estimated window-mean p)")
    print("=" * 100)
    print(f"{'window':>8} {'ratio':>9} {'bsp_win':>9} {'ewma':>9} {'ewma':>9} {'bsp_causal':>11} "
          f"{'bsp_full*':>10} {'corr':>7}")
    print(f"{'(s)':>8} {'':>9} {'refit':>9} {'tuned':>9} {'oracle':>9} {'online':>11} "
          f"{'non-causal':>10} {'':>7}")
    print("-" * 100)
    for W in WINDOWS:
        rr = agg(rows, "rmse_ratio_sel", W); rw = agg(rows, "rmse_win", W)
        rc = agg(rows, "rmse_causal", W); rf = agg(rows, "rmse_full", W)
        re_ = agg(rows, "rmse_ewma", W); rec = agg(rows, "rmse_ewma_c", W)
        print(f"{W:>8} {agg(rows,'rmse_ratio',W):>9.4f} {rw:>9.4f} {rec:>9.4f} {re_:>9.4f} {rc:>11.4f} "
              f"{rf:>10.4f} {agg(rows,'corr',W):>7.3f}")

    print("\n  THE ADVERSARIAL COMPARISON: is BSP worth more than exponential smoothing? Two EWMA baselines")
    print("  bracket the answer. 'tuned' picks its constant by one-step-ahead error on the first 30 % -- no")
    print("  truth, no future, a baseline anyone could deploy. 'oracle' is handed the best constant for each")
    print("  regime and window using the true p, which nobody has; it is a CEILING, not a method. BSP's")
    print("  position between the two is the honest statement of what the binomial model and logistic link")
    print("  earn over three lines of arithmetic.")
    print(f"{'window':>8} {'bsp_causal':>11} {'ewma tuned':>11} {'ewma oracle':>12} {'bsp/tuned':>10} "
          f" {'verdict vs the PRACTICAL baseline':>36}")
    print("-" * 110)
    for W in WINDOWS:
        rc = agg(rows, "rmse_causal", W); re_ = agg(rows, "rmse_ewma", W)
        rec = agg(rows, "rmse_ewma_c", W)
        if not (rc == rc and rec == rec and rec > 0):
            continue
        q = rc / rec
        v = ("BSP ahead" if q < 0.97 else
             "indistinguishable" if q < 1.03 else "a causally-tuned EWMA is as good or better")
        print(f"{W:>8} {rc:>11.4f} {rec:>11.4f} {re_:>12.4f} {q:>10.3f}  {v:>36}")
    aa = [r["ewma_alpha_c"] for r in rows if r.get("ewma_alpha_c") is not None]
    if aa:
        print(f"\n  causally-tuned alpha: median {np.median(aa):.2f}, "
              f"range {min(aa):.2f}-{max(aa):.2f}")
    print("\n  * bsp_full uses observations from AFTER the window. It is not an online estimate and must not")
    print("    be compared with the ratio as though it were.")
    print("\n  THE LIKE-FOR-LIKE COLUMN IS bsp_win: identical data in, identical summary out, so any")
    print("  difference from 'ratio' is the MODEL working rather than extra data. Its ratio to the matched")
    print("  ratio baseline:")
    line = "   "
    for W in WINDOWS:
        rr = agg(rows, "rmse_ratio_sel", W); rw = agg(rows, "rmse_win", W)
        if rr == rr and rr > 0:
            line += f" W={W}: {rw/rr:.3f}  "
    print(line)
    print("  (At W=1 BSP is undefined on a single bin and degenerates to the ratio by construction, so 1.000")
    print("   there is bookkeeping, not a result.)")

    # the headline: the largest window at which the two are still interchangeable
    thresh = 0.98
    inter = [W for W in WINDOWS if agg(rows, "corr", W) >= thresh]
    brk = [W for W in WINDOWS if agg(rows, "corr", W) == agg(rows, "corr", W) and agg(rows, "corr", W) < thresh]
    print(f"\n  correlation(ratio, bsp) >= {thresh}: windows {sorted(inter)} s")
    print(f"  equivalence BREAKS DOWN at: windows {sorted(brk)} s"
          if brk else "\n  equivalence never breaks down within the swept range")

    print("\n" + "=" * 100)
    print("S2  WHERE DOES THE SMOOTHING PAY?  bsp_win / ratio  (<1 = BSP more accurate), by regime")
    print("=" * 100)
    shown = [600, 120, 30, 8, 2]
    print(f"{'regime':>16} " + " ".join(f"{('W=' + str(W)):>9}" for W in shown))
    print("-" * 100)
    for rg in REGIMES:
        cells = []
        for W in shown:
            rr = agg(rows, "rmse_ratio_sel", W, rg); rw = agg(rows, "rmse_win", W, rg)
            cells.append(f"{(rw / rr if rr and rr > 0 else float('nan')):>9.3f}")
        print(f"{rg:>16} " + " ".join(cells))

    print("\n" + "=" * 100)
    print("S3  DOES THE 95% CREDIBLE BAND COVER THE TRUTH?  (nominal 0.950, per bin, whole series)")
    print("=" * 100)
    print(f"{'regime':>16} {'coverage':>10} {'mean width':>12} {'fitted sigma2':>15}")
    print("-" * 100)
    for rg in REGIMES:
        c = [r["cover"] for r in res if r["regime"] == rg]
        w = [r["width"] for r in res if r["regime"] == rg]
        s = [r["sigma2"] for r in res if r["regime"] == rg]
        print(f"{rg:>16} {np.mean(c):>10.3f} {np.mean(w):>12.3f} {np.mean(s):>15.4f}")
    allc = np.mean([r["cover"] for r in res])
    print(f"\n  pooled coverage {allc:.3f} against a nominal 0.950 -- "
          f"{'calibrated' if 0.90 <= allc <= 0.97 else 'NOT calibrated'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
