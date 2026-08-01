"""E127 -- Does the DIRECTION lead the RESIDUAL, or does the RESIDUAL lead the DIRECTION?
The test that decides whether E126 is hysteresis or confounding by indication.

REGISTERED BEFORE ANY LAG HAS BEEN COMPUTED. E126's cohort, residual and direction series are already
built and their construction is unchanged here; no cross-lagged quantity has been evaluated.

=========================================================================================================
WHY
=========================================================================================================
E126 found that when the modelled propofol concentration is FALLING, patients are more deeply sedated than
a fitted 8-rate effect-site basis predicts: falling-minus-rising MOAA/S residual **-0.1322
[-0.2349, -0.0363]** over 69 recordings, with a Gaussian control null (+0.0107 [-0.0141, +0.0358]) and a
rolled-direction placebo that does not reproduce it (mean -0.0130 [-0.0958, +0.0798], frac 0.000). So it
is not rule 64's time-split-in-disguise, the failure that withdrew E98 and E102.

**But E126's own outcome record names a threat that predicts the identical sign and that its placebo does
not touch:**

    "CONFOUNDING BY INDICATION. Concentration falls precisely when the clinician stops giving drug, and a
     clinician stops giving drug to a patient who looks deeper than expected. That is the residual CAUSING
     the direction rather than the direction causing the residual, and it reproduces the observed sign
     exactly with no hysteresis anywhere."

Two causal stories, one correlation. Rule 50: measuring a difference is not measuring its cause.

=========================================================================================================
THE DISCRIMINATOR, AND WHY IT IS A DISCRIMINATOR
=========================================================================================================
The two stories differ in TEMPORAL ORDER, and in nothing else that is observable here.

    HYSTERESIS            the concentration turns, and the brain then lags behind it.
                          direction leads  ->  residual follows.

    INDICATION            the clinician sees a patient deeper than expected, and then withholds drug, so
                          the concentration turns afterwards.
                          residual leads   ->  direction follows.

So define, within each recording, the cross-correlation between the direction series and the residual
series at signed lag k:

    c(k) = corr( direction(t) , residual(t + k) )        k in [-K, +K] windows

Hysteresis puts weight at k > 0 (direction first). Indication puts weight at k < 0 (residual first).

    P1  THE ASYMMETRY.  A = mean_{k>0} c(k)  -  mean_{-k<0} c(k),  averaged over recordings, cluster
        bootstrap over recordings.  **PREDICTED NEGATIVE UNDER HYSTERESIS** -- because the E126 effect is
        itself negative (falling goes with a LOWER residual), so a hysteresis-driven c(k) is more negative
        at positive lags. Sign convention stated here because reading it backwards inverts the verdict.

    P2  THE PEAK LAG.  argmin_k c(k), reported as a distribution over recordings, with the fraction of
        recordings whose minimum falls at a positive lag. A descriptive companion to P1 that does not
        depend on the averaging window, so a disagreement between P1 and P2 is informative rather than
        hidden.

GATES

    G1  E126'S GATES, INHERITED AND RE-EVALUATED, not assumed: the pharmacology must be alive, and >= 25
        recordings must carry >= 10 windows in BOTH directions. This file recomputes them rather than
        trusting E126's run.

    G2  THE MACHINERY MUST RECOVER A KNOWN LAG. **This is the gate that makes a null interpretable.** A
        synthetic residual is constructed as a KNOWN SHIFT of the real direction series plus matched
        noise, at lags of -4, 0 and +4 windows, and P1 must come back with the correct sign in each case.
        A cross-lagged estimator that cannot recover an injected lag cannot adjudicate anything, and a
        null from it would be a statement about the estimator (rule 31, and E123's lesson: a positive
        control must be DEMONSTRATED on the same data, not assumed from another deposit).

    G3  SAMPLING INTERVAL. The DOSE-I feature windows are strided every 5 s, so one lag unit is 5 s and
        K = 12 spans one minute either side. Reported, because a lag expressed in windows is meaningless
        without it, and because a clinician's reaction time and an equilibration half-time are both of
        this order -- which is precisely why the two stories are hard to separate and why the test needs
        the resolution stated up front rather than assumed adequate.

PLACEBO, gating the verdict (rule 34): the direction series is rolled to a random index within each
recording, exactly as in E126, and the whole cross-lagged pipeline is rerun. Any asymmetry that survives
rolling is an artefact of the two series' own autocorrelation rather than of their correspondence.
Compared against the 200-draw DISTRIBUTION, never its mean (rule 37).

Rule 48: P1's interval is read FIRST. If it includes zero the placebo is NOT INFORMATIVE.

VERDICT, wrong direction FIRST and by name (rule 37, seventh occurrence in this project):

    (a) A excludes zero POSITIVE -> INDICATION. The residual LEADS the direction: patients who look deeper
        than expected subsequently have their drug withheld. E126's finding is then confounding by
        indication and **must be withdrawn as evidence of hysteresis**. This is the branch enumerated
        first because it is the one that costs us the finding.
    (b) A includes zero -> NOT SEPARATED. The design cannot tell the two apart on this data, and E126
        stands as an unexplained direction dependence rather than as neural inertia. NOT a vindication.
    (c) A excludes zero NEGATIVE and beats the placebo -> DIRECTION LEADS. Consistent with hysteresis and
        inconsistent with the clinician-response account, on the one dimension that separates them.

CALIBRATION, before the run: (a) ~40 %, (b) ~40 %, (c) ~20 %. Indication is given the largest single share
because it requires no new physiology, and (b) is given as much because 5 s resolution against processes
with similar time constants may simply not resolve them.

SCOPE. Everything E126's scope says, plus one specific to this design: MOAA/S is assessed intermittently
by a clinician, so the residual series is not a continuous physiological trace but a step function between
assessments, and its effective time resolution is the assessment interval rather than the 5 s stride. That
biases the lag estimate toward zero and therefore toward branch (b). Stated now (rule 47).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e127_lead_lag.json")

RUNG = 2
K = 12                       # lags in windows; the stride is 5 s so this is +/- 60 s
MIN_PER_DIRECTION = 10
MIN_RECORDINGS = 25
MIN_WINDOWS = 40             # need enough series length to estimate 25 lags
REPS = 150
PLACEBO_DRAWS = 200
SEED = 127


def crosscorr(a, b, k):
    """corr(a(t), b(t+k)) on the overlapping span. NaN if the overlap is too short or either is constant."""
    import numpy as np
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if k > 0:
        x, y = a[:-k], b[k:]
    elif k < 0:
        x, y = a[-k:], b[:k]
    else:
        x, y = a, b
    if x.size < 8:
        return float("nan")
    x = x - x.mean()
    y = y - y.mean()
    d = float(np.sqrt((x * x).sum() * (y * y).sum()))
    return float((x * y).sum() / d) if d > 0 else float("nan")


def asymmetry(dirs, resids, k_max=K):
    """Per-recording (asymmetry, peak lag). Positive lag means DIRECTION leads."""
    import numpy as np
    out_a, out_p = [], []
    for d, r in zip(dirs, resids):
        c = {k: crosscorr(d, r, k) for k in range(-k_max, k_max + 1)}
        pos = [c[k] for k in range(1, k_max + 1) if np.isfinite(c[k])]
        neg = [c[k] for k in range(-k_max, 0) if np.isfinite(c[k])]
        if len(pos) < k_max // 2 or len(neg) < k_max // 2:
            out_a.append(np.nan); out_p.append(np.nan); continue
        out_a.append(float(np.mean(pos) - np.mean(neg)))
        fin = {k: v for k, v in c.items() if np.isfinite(v)}
        out_p.append(float(min(fin, key=fin.get)) if fin else np.nan)
    return np.asarray(out_a), np.asarray(out_p)


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import cluster_bootstrap_ci, ridge_fit, _standardise

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E127", "C",
            "Does the concentration direction LEAD the MOAA/S residual (hysteresis) or FOLLOW it "
            "(confounding by indication)?",
            "DOSE-I",
            "cross-lagged asymmetry A = mean_{k>0} corr(dir(t), resid(t+k)) - mean_{k<0}, within "
            "recording; PREDICTED NEGATIVE under hysteresis",
            ["G1 E126's gates recomputed, not assumed",
             "G2 the estimator must recover an INJECTED lag of -4, 0, +4 windows",
             "G3 sampling interval reported (5 s stride, K=12 -> +/-60 s)"],
            "roll the direction series to a random index within each recording; 200 draws, compared "
            "against the DISTRIBUTION",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E126",
            instrument_changed="TEMPORAL ORDER replaces the contemporaneous contrast -- the one dimension "
                               "on which hysteresis and clinician-response differ")
        print("registered E127")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    import e122_pharmacology_residual as E

    by, cands, off, cov, dose = E.load()
    kept, _ = E.build(by, cands, off, cov, dose)
    recs = sorted(kept)
    for rec in recs:
        d = kept[rec]
        ce = d["pk"][RUNG].sum(axis=1)
        d["dir"] = np.sign(np.gradient(ce, d["t"])) if ce.size > 2 else np.zeros_like(ce)

    ok_recs = [r for r in recs
               if kept[r]["y"].size >= MIN_WINDOWS
               and int((kept[r]["dir"] > 0).sum()) >= MIN_PER_DIRECTION
               and int((kept[r]["dir"] < 0).sum()) >= MIN_PER_DIRECTION]
    gates = {"G1_recordings": len(ok_recs), "G1_pass": len(ok_recs) >= MIN_RECORDINGS,
             "G3_stride_s": 5.0, "G3_k_max_windows": K, "G3_span_s": 5.0 * K}
    print(f"G1 {len(ok_recs)} recordings usable  {'PASS' if gates['G1_pass'] else 'FAIL'}")
    print(f"G3 stride 5 s, K={K} windows -> lags span +/-{5.0 * K:.0f} s")
    if not gates["G1_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: coverage"}, open(a.out, "w"), indent=1)
        return 0

    X, y, s = E.stack(kept, ok_recs, lambda d: d["pk"][RUNG])
    rho = E.oob_rho(X, y, s, np.random.default_rng(SEED), reps=a.reps)
    gates["G1_oob_rho"] = rho
    gates["G1_pharmacology_alive"] = bool(np.isfinite(rho) and rho > 0.10)
    print(f"G1 pharmacology out-of-bag rho {rho:+.4f}")

    # Out-of-bag residual, exactly E126's construction.
    uniq = np.unique(s)
    idx = {u: np.flatnonzero(s == u) for u in uniq}
    acc, cnt = np.zeros(y.size), np.zeros(y.size)
    rng = np.random.default_rng(SEED + 1)
    for _ in range(a.reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        ds = set(drawn.tolist())
        oob = [u for u in uniq if u not in ds]
        if len(oob) < 5:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        try:
            A, B = _standardise(X[tr], X[te])
            p = B @ ridge_fit(A, y[tr], 1.0)
        except Exception:                                                  # noqa: BLE001
            continue
        acc[te] += (y[te] - p)
        cnt[te] += 1
    resid_all = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)

    dirs, resids, keys = [], [], []
    for rec in ok_recs:
        m = s == rec
        r = resid_all[m]
        d = kept[rec]["dir"]
        if np.isfinite(r).sum() < MIN_WINDOWS:
            continue
        r = np.where(np.isfinite(r), r, np.nanmean(r))
        dirs.append(d); resids.append(r); keys.append(rec)
    keys = np.asarray(keys)

    # ---- G2: can the estimator recover an INJECTED lag? --------------------------------------------
    g2 = {}
    grng = np.random.default_rng(SEED + 2)
    for true_lag in (-4, 0, 4):
        fake = []
        for d, r in zip(dirs, resids):
            base = np.roll(d.astype(float), true_lag)          # residual is a shifted copy of direction
            noise = grng.normal(scale=float(np.std(r)) or 1.0, size=base.size)
            fake.append(base * float(np.std(r) or 1.0) + noise)
        aa, _ = asymmetry(dirs, fake)
        g2[f"injected_lag_{true_lag:+d}"] = float(np.nanmean(aa))
    # A residual that is direction shifted FORWARD by +4 means direction LEADS, which under the sign
    # convention above must give a POSITIVE asymmetry for a positively-correlated injection.
    gates["G2_injection"] = g2
    gates["G2_pass"] = bool(g2["injected_lag_+4"] > g2["injected_lag_+0"] > g2["injected_lag_-4"])
    print(f"G2 injected lags -4/0/+4 -> asymmetry "
          f"{g2['injected_lag_-4']:+.4f} / {g2['injected_lag_+0']:+.4f} / {g2['injected_lag_+4']:+.4f}"
          f"  {'PASS' if gates['G2_pass'] else 'FAIL'}")

    if not gates["G2_pass"]:
        json.dump({"gates": gates,
                   "verdict": "ABSENT -- the cross-lagged estimator does not recover an injected lag on "
                              "these series, so it cannot adjudicate between the two accounts and a null "
                              "from it would be a statement about the estimator (rule 31)."},
                  open(a.out, "w"), indent=1)
        print("\nVERDICT: ABSENT -- estimator failed its own injection test")
        return 0

    # ---- P1 / P2 -----------------------------------------------------------------------------------
    A_real, peaks = asymmetry(dirs, resids)
    good = np.isfinite(A_real)
    Av = A_real[good]
    kk = keys[good]
    coef = float(np.mean(Av))
    lo, hi, _ = cluster_bootstrap_ci(lambda i: float(np.mean(Av[i])), kk,
                                     np.random.default_rng(SEED + 3), reps=4000)
    pk = peaks[np.isfinite(peaks)]
    frac_pos = float(np.mean(pk > 0)) if pk.size else float("nan")
    print(f"\nP1 asymmetry (dir leads - resid leads) = {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] "
          f"over {Av.size} recordings")
    print(f"P2 peak lag: median {np.median(pk):+.1f} windows ({np.median(pk) * 5:+.0f} s), "
          f"{frac_pos * 100:.1f}% of recordings peak at a POSITIVE lag")

    # ---- PLACEBO ------------------------------------------------------------------------------------
    prng = np.random.default_rng(SEED + 4)
    draws = []
    for _ in range(a.placebo_draws):
        rolled = [np.roll(d, int(prng.integers(1, max(2, d.size)))) for d in dirs]
        aa, _ = asymmetry(rolled, resids)
        aa = aa[np.isfinite(aa)]
        if aa.size:
            draws.append(float(np.mean(aa)))
    dr = np.asarray(draws, float)
    frac = float(np.mean(dr <= coef)) if dr.size else float("nan")
    placebo = {"n": int(dr.size), "mean": float(dr.mean()) if dr.size else float("nan"),
               "p2.5": float(np.quantile(dr, .025)) if dr.size else float("nan"),
               "p97.5": float(np.quantile(dr, .975)) if dr.size else float("nan"),
               "frac_at_least_as_negative": frac}
    print(f"PLACEBO rolled direction: mean {placebo['mean']:+.4f} "
          f"[{placebo['p2.5']:+.4f}, {placebo['p97.5']:+.4f}]  frac<=real {frac:.3f}")

    beats = bool(np.isfinite(frac) and frac <= 0.05)
    if not np.isfinite(lo):
        verdict = "ABSENT -- the asymmetry could not be estimated."
    elif lo > 0:
        verdict = (f"(a) INDICATION -- asymmetry {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] is POSITIVE, meaning "
                   "the RESIDUAL LEADS the direction: patients who look deeper than the pharmacology "
                   "predicts subsequently have their drug withheld. E126's direction dependence is "
                   "confounding by indication and MUST BE WITHDRAWN as evidence of hysteresis.")
    elif hi < 0 and beats:
        verdict = (f"(c) DIRECTION LEADS -- asymmetry {coef:+.4f} [{lo:+.4f}, {hi:+.4f}], beating the "
                   f"rolled-direction placebo (frac {frac:.3f}). The concentration turns first and the "
                   "residual follows, which is what hysteresis requires and what the clinician-response "
                   "account forbids. E126 survives its leading threat on the one dimension that "
                   "separates them.")
    elif hi < 0:
        verdict = (f"WITHDRAWN BY PLACEBO -- {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] is in the hysteresis "
                   f"direction but a rolled direction series reproduces it (frac {frac:.3f}), so the "
                   "asymmetry is a property of the two series' autocorrelation rather than of their "
                   "correspondence.")
    else:
        verdict = (f"(b) NOT SEPARATED -- asymmetry {coef:+.4f} [{lo:+.4f}, {hi:+.4f}] includes zero. "
                   "The design cannot tell hysteresis from confounding by indication on this data, so "
                   "E126 stands as an UNEXPLAINED direction dependence and NOT as neural inertia. This "
                   "is not a vindication. The placebo is NOT INFORMATIVE (rule 48). Note the scope "
                   "limit registered in advance: MOAA/S is assessed intermittently, so the residual is a "
                   "step function between assessments and its effective resolution is the assessment "
                   "interval rather than the 5 s stride -- which biases the estimate toward this branch.")

    res = {"gates": gates,
           "P1_asymmetry": {"coef": coef, "lo": lo, "hi": hi, "n_recordings": int(Av.size)},
           "P2_peak_lag": {"median_windows": float(np.median(pk)) if pk.size else None,
                           "median_seconds": float(np.median(pk) * 5) if pk.size else None,
                           "frac_positive": frac_pos},
           "placebo": placebo, "verdict": verdict}
    json.dump(res, open(a.out, "w"), indent=1)
    print("\nVERDICT:", verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
