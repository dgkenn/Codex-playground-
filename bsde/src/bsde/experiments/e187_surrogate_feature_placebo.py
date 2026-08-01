#!/usr/bin/env python3
"""E187 — the placebo E183 proved impossible on the label side, moved to the feature side where it works.

REGISTERED BEFORE ANY SURROGATE INCREMENT HAS BEEN COMPUTED.

=========================================================================================================
THE DEAD END, AND WHY THIS IS NOT A FOURTH ATTEMPT AT THE SAME THING
=========================================================================================================
E180 and E183 tried to test E150's eleven MOAA/S increments by destroying the LABEL. Between them they ran
a large-lag circular shift, a small-lag shift bounded by the measured autocorrelation half-life, and a
trajectory swap between correlation-matched donor recordings. **All three failed the same way**: not one
draw in 3,000, 6,000 and 6,000 attempts respectively kept the PE31 + SEF95 incumbent within 0.03 of its
real out-of-fold rho of **+0.3987** — under E180's large shifts it collapsed to **+0.0324**.

E183's recorded conclusion is that on this deposit **destroying MOAA/S's alignment and destroying its
predictability are the same operation**, because the relationship lives entirely below the nine-window
autocorrelation half-life. No label placebo of that family can discriminate anything here.

**So the placebo moves to the feature side, where the label is never touched and the incumbent's
predictability is preserved BY CONSTRUCTION.** That is not a workaround; it is the only side of the
comparison that has any slack left.

=========================================================================================================
WHY E150'S EXISTING FEATURE PLACEBO IS NOT ENOUGH, AND WHAT REPLACES IT
=========================================================================================================
E150's placebo column is `cluster_permute(candidate, recording)` — the candidate's whole block swapped to
another recording. That destroys the candidate's alignment with the label **and its within-recording
trend, and its recording-specific level**, all at once. A column with any smooth trajectory is easy to beat
once the trajectory is gone, which is why eight of E150's eleven cleared it comfortably.

**The matched feature placebo is a PHASE-RANDOMISED SURROGATE, built per recording.** Iterative
amplitude-adjusted Fourier transform (Schreiber & Schmitz 1996) produces a series with:

    * the SAME power spectrum, and therefore the same autocorrelation at every lag, and
    * the SAME marginal distribution, value for value,

while its phases — and hence its alignment with anything else — are randomised. It is the standard null
for "does this series carry information beyond its own linear temporal structure", imported from nonlinear
time-series analysis rather than invented here.

So a candidate that beats its own surrogates carries information about MOAA/S that its trend and
autocorrelation do not explain. A candidate that does not is a smooth series whose smoothness is doing the
work — which is exactly the alternative E180 and E183 could not test.

=========================================================================================================
GATES, AND TWO OF THEM CHECK THE PLACEBO ITSELF (rule 55)
=========================================================================================================
G1  REBUILD against E150's own stored cohort size, loaded from its JSON (rule 59).
G2  THE INCUMBENT IS ALIVE under the real, untouched label — and it is untouched, which is the point.
G3  **THE SURROGATE PRESERVES WHAT IT CLAIMS TO PRESERVE.** For each candidate the mean absolute
    difference in lag-1 and lag-9 within-recording autocorrelation between the real series and its
    surrogates must be below `AC_TOL`, and the marginal distributions are identical by construction.
    A surrogate that does not preserve the autocorrelation is not the placebo this file registered.
G4  **THE SURROGATE DESTROYS WHAT IT CLAIMS TO DESTROY.** The mean within-recording correlation between
    the real series and its surrogates must be below `CORR_MAX`. A surrogate that stays correlated with
    the original is not a destruction and voids that candidate.
G5  A CALIBRATION CANDIDATE. `meta_t_s`-like structure is not available here, so the calibration column is
    a smooth **random walk per recording**, matched in length: a series with strong autocorrelation and NO
    relationship to MOAA/S. **It must be WITHDRAWN by its own surrogates** — if a pure random walk
    survives, the test is anti-conservative and nothing is reported (rule 40).

=========================================================================================================
VERDICT, PER CANDIDATE — THE WITHDRAWING AND UNINFORMATIVE CASES FIRST (rules 31, 34, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G5 fails.
  (2) VOID                G4 fails for that candidate: its surrogates stay correlated with it.
  (3) WITHDRAWN           more than 5 % of surrogates reach or beat the real increment. The candidate's
                          contribution is explained by its own trend and autocorrelation.
  (4) SURVIVES            the real increment exceeds the surrogate distribution. The candidate carries
                          information about MOAA/S beyond its own linear temporal structure — the first
                          Challenge C increment in this ledger with a matched placebo of any kind behind
                          it, and the muscle members are reported separately because MOAA/S is scored by
                          movement.

**REGISTERED PREDICTION: (3) for most, (4) for at most one or two.** MOAA/S falls monotonically through a
sedation procedure and most of these columns drift with it, so a surrogate that keeps the drift should be
hard to beat. **The prediction is against the last live Challenge C claim**, which is the correct way
round. If several survive, the claim is far stronger than three failed label placebos left it.

SCOPE. One deposit, 62 recordings, eleven candidates chosen by E150 for a different reason. IAAFT nulls
test information beyond linear temporal structure and nothing else; a candidate that survives has not
thereby been shown to measure depth rather than, say, movement.

    python bsde/src/bsde/experiments/e187_surrogate_feature_placebo.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import grouped_cv_predict, permutation_increment, spearman  # noqa: E402
import e84_increment_over_validated_incumbent as E84                                 # noqa: E402
from e150_challenge_c_negatives_rederived import build                               # noqa: E402
from e180_moaas_label_placebo import E150_ADDS, MUSCLE, baseline_perf                # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
OUT = os.path.join(RESULTS, "e187_surrogate_feature_placebo.json")
SEED = 20260801

N_SURR = 200
IAAFT_ITERS = 60
AC_TOL = 0.05          # G3: mean |delta autocorrelation| between a series and its surrogates
CORR_MAX = 0.30        # G4: mean |rho(real, surrogate)| within recording
PERMS = 300
ALPHA = 0.05

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def iaaft(x, rng, iters=IAAFT_ITERS):
    """Iterative amplitude-adjusted Fourier transform surrogate (Schreiber & Schmitz 1996).

    Preserves the power spectrum (hence the autocorrelation at every lag) AND the marginal distribution,
    while randomising phase. Returns a series with the same length and the same sorted values.
    """
    x = np.asarray(x, float)
    n = x.size
    if n < 8 or not np.isfinite(x).all() or np.std(x) < 1e-12:
        return x.copy()
    amp = np.abs(np.fft.rfft(x))
    sorted_x = np.sort(x)
    y = rng.permutation(x)
    for _ in range(iters):
        Y = np.fft.rfft(y)
        ph = np.angle(Y)
        y = np.fft.irfft(amp * np.exp(1j * ph), n=n)
        y = sorted_x[np.argsort(np.argsort(y))]        # re-impose the exact marginal
    return y


def surrogate_column(x, subj, rng):
    """Per-recording IAAFT. NaNs are left in place and the finite stretch is surrogated."""
    out = np.full(x.size, np.nan)
    for u in np.unique(subj):
        m = subj == u
        v = x[m]
        ok = np.isfinite(v)
        if ok.sum() < 8:
            out[m] = v
            continue
        s = v.copy()
        s[ok] = iaaft(v[ok], rng)
        out[m] = s
    return out


def _ac(v, lag):
    v = v[np.isfinite(v)]
    if v.size <= lag + 3 or np.std(v) < 1e-12:
        return float("nan")
    r = spearman(list(v[:-lag]), list(v[lag:]))
    return float(r) if np.isfinite(r) else float("nan")


def surrogate_diagnostics(x, s, subj):
    """(mean |delta ac1|, mean |delta ac9|, mean |rho(real, surrogate)|) over recordings."""
    d1, d9, cr = [], [], []
    for u in np.unique(subj):
        m = subj == u
        a1r, a1s = _ac(x[m], 1), _ac(s[m], 1)
        a9r, a9s = _ac(x[m], 9), _ac(s[m], 9)
        if np.isfinite(a1r) and np.isfinite(a1s):
            d1.append(abs(a1r - a1s))
        if np.isfinite(a9r) and np.isfinite(a9s):
            d9.append(abs(a9r - a9s))
        ok = np.isfinite(x[m]) & np.isfinite(s[m])
        if ok.sum() > 10:
            r = spearman(list(x[m][ok]), list(s[m][ok]))
            if np.isfinite(r):
                cr.append(abs(r))
    return (float(np.mean(d1)) if d1 else float("nan"),
            float(np.mean(d9)) if d9 else float("nan"),
            float(np.mean(cr)) if cr else float("nan"))


def increment(base, x, y, subj, seed):
    ok = np.isfinite(x)
    if ok.sum() < 0.5 * len(y):
        return float("nan")
    pa = grouped_cv_predict(base[ok], y[ok], subj[ok], np.random.default_rng(seed))
    pb = grouped_cv_predict(np.c_[base[ok], x[ok]], y[ok], subj[ok], np.random.default_rng(seed))
    m = np.isfinite(pa) & np.isfinite(pb)
    if m.sum() < 100:
        return float("nan")
    return float(E84.err(y[ok][m], pb[m]) - E84.err(y[ok][m], pa[m]))


def score_candidate(name, x, base, y, subj, rng, label=""):
    real, p_real, _, _ = permutation_increment(base[np.isfinite(x)], np.c_[base[np.isfinite(x)],
                                                                          x[np.isfinite(x)]],
                                               y[np.isfinite(x)], subj[np.isfinite(x)],
                                               np.random.default_rng(SEED + 5),
                                               stat=E84.err, reps=PERMS)
    surrs, d1s, d9s, crs = [], [], [], []
    for i in range(N_SURR):
        s = surrogate_column(x, subj, np.random.default_rng(SEED + 9000 + i))
        if i < 20:
            a, b, c = surrogate_diagnostics(x, s, subj)
            d1s.append(a)
            d9s.append(b)
            crs.append(c)
        v = increment(base, s, y, subj, SEED + 11000 + i)
        if np.isfinite(v):
            surrs.append(v)
    sv = np.asarray(surrs)
    frac = float((sv <= real).mean()) if sv.size >= 30 else float("nan")
    out = {"real": float(real), "p_real": float(p_real),
           "surrogate_mean": float(sv.mean()) if sv.size else float("nan"),
           "surrogate_p05": float(np.quantile(sv, 0.05)) if sv.size else float("nan"),
           "fraction_at_or_below_real": frac, "n_surrogates": int(sv.size),
           "delta_ac1": float(np.nanmean(d1s)) if d1s else float("nan"),
           "delta_ac9": float(np.nanmean(d9s)) if d9s else float("nan"),
           "corr_with_real": float(np.nanmean(crs)) if crs else float("nan")}
    out["preserves"] = bool(np.isfinite(out["delta_ac1"]) and out["delta_ac1"] < AC_TOL
                            and np.isfinite(out["delta_ac9"]) and out["delta_ac9"] < AC_TOL)
    out["destroys"] = bool(np.isfinite(out["corr_with_real"]) and out["corr_with_real"] < CORR_MAX)
    out["withdrawn"] = bool(np.isfinite(frac) and frac > ALPHA)
    print(f"   {name:<26s} real {real:>+9.5f}  surr mean {out['surrogate_mean']:>+9.5f}  "
          f"frac {frac:>7.4f}  |dAC1| {out['delta_ac1']:.3f} |dAC9| {out['delta_ac9']:.3f} "
          f"rho {out['corr_with_real']:.3f}  "
          f"{'VOID' if not out['destroys'] else ('WITHDRAWN' if out['withdrawn'] else 'survives')}"
          + label)
    return out


def main() -> int:
    print("E187 — phase-randomised surrogate placebo on the FEATURE side, where the label is untouched")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E187", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "n_surrogates": N_SURR, "iaaft_iters": IAAFT_ITERS}
    g1 = (n_rec == N_RECORDINGS) and (len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's stored {N_RECORDINGS} / "
          f"{N_WINDOWS}   {'PASS' if g1 else '*** FAIL'}")
    res["G1_pass"] = bool(g1)
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1
    rb = baseline_perf(base, y, subj, SEED)
    res["G2_baseline_rho"] = rb
    res["G2_pass"] = bool(np.isfinite(rb) and rb > 0.1)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho = {rb:+.4f}   "
          f"{'PASS' if res['G2_pass'] else '*** FAIL'}   "
          "(the label is never touched by this placebo, so this holds for every draw by construction)")
    if not res["G2_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    print(f"\nG5 CALIBRATION CANDIDATE — a per-recording random walk, strongly autocorrelated and "
          f"unrelated to MOAA/S; it MUST be withdrawn")
    walk = np.empty(len(y))
    for u in np.unique(subj):
        m = subj == u
        walk[m] = np.cumsum(rng.normal(size=int(m.sum())))
    g5 = score_candidate("CALIBRATION random walk", walk, base, y, subj, rng, label="   <- G5")
    res["G5"] = g5
    if not g5["withdrawn"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = ("a pure random walk SURVIVES its own surrogates, so the test is anti-conservative "
                      "and nothing is reported (rule 40)")
        print(f"\nVERDICT NOT INTERPRETABLE — {res['why']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    print(f"\n{'candidate':<26s} {'real':>10s} {'surr mean':>11s} {'frac':>9s}  diagnostics  verdict")
    table = {}
    for c in E150_ADDS:
        x = cand.get(c)
        if x is None:
            continue
        table[c] = score_candidate(c, x, base, y, subj, rng,
                                   label="   MUSCLE" if c in MUSCLE else "")
        table[c]["muscle"] = c in MUSCLE
    res["table"] = table

    bad_preserve = [c for c, v in table.items() if not v["preserves"]]
    res["G3_pass"] = not bad_preserve
    res["G3_failed_for"] = bad_preserve
    print(f"\nG3 SURROGATE PRESERVES AUTOCORRELATION  "
          f"{'PASS for all' if not bad_preserve else '*** FAIL for ' + str(bad_preserve)}")
    surv = [c for c, v in table.items() if v["destroys"] and not v["withdrawn"]]
    void = [c for c, v in table.items() if not v["destroys"]]
    nm = [c for c in surv if c not in MUSCLE]
    res["survivors"], res["void"], res["non_muscle_survivors"] = surv, void, nm

    if bad_preserve:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = (f"the surrogate does not preserve the autocorrelation for {bad_preserve}, so it is "
                      "not the placebo this file registered (rule 55)")
    elif not surv:
        res["verdict"] = "WITHDRAWN"
        res["why"] = ("no candidate beats its own phase-randomised surrogates: every one of E150's eleven "
                      "is explained by its own trend and autocorrelation, and Challenge C has no live "
                      "incremental result on DOSE-I")
    elif not nm:
        res["verdict"] = "MUSCLE-ONLY"
        res["why"] = (f"the only survivors are {surv}, all muscle measures, and MOAA/S is scored by "
                      "whether the patient responds to name and shake -- movement predicting a "
                      "movement-scored scale")
    else:
        res["verdict"] = "SURVIVES"
        res["why"] = (f"{nm} carry information about MOAA/S beyond their own linear temporal structure. "
                      "This is the first Challenge C increment in the ledger with a matched placebo of "
                      "any kind behind it, after three label placebos proved impossible to build")
    if void:
        res["why"] += f". VOID (surrogates stayed correlated with the original): {void}"
    print(f"\nVERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
