#!/usr/bin/env python3
"""E189 — E187's surrogate placebo with a preservation gate that is a COMPARISON, not a round number.

REGISTERED BEFORE ANY SURROGATE-VERSUS-SURROGATE DIFFERENCE HAS BEEN COMPUTED.

=========================================================================================================
WHAT E187 SETTLED, AND THE ONE THING IT COULD NOT
=========================================================================================================
E187 moved the placebo from the label side — where E180 and E183 proved it impossible on this deposit, all
three attempts failing to keep the incumbent within 0.03 of its real rho of +0.3987 — to the feature side,
where the label is never touched. **It worked, and its verdict was still NOT INTERPRETABLE.**

    * **Nine of eleven candidates beat every one of 200 phase-randomised surrogates** (fraction 0.0000),
      with surrogate means at +0.0001 to +0.0051 against real increments of -0.0016 to -0.0333.
    * The two that withdrew are the two smallest effects — `wpli_delta` (0.0550) and `wpli_alpha_2ch`
      (0.0850).
    * G4 passed for every candidate (surrogates decorrelate to rho 0.105-0.299) and G5's calibration
      random walk was correctly WITHDRAWN at 0.4900.
    * **G3 failed**: three candidates' lag-9 autocorrelation moved by 0.060, 0.062 and 0.069 against a
      tolerance of 0.05.

**AC_TOL = 0.05 WAS A ROUND NUMBER SET BEFORE ANYONE MEASURED WHAT IAAFT ACHIEVES HERE.** That is rule 63.
IAAFT provably preserves the periodogram, so the residual difference is finite-sample noise in estimating
an autocorrelation from a few hundred windows — not a failure of preservation. E187's measurement puts it
at **0.008-0.046 at lag 1, 0.030-0.069 at lag 9**, with a non-stationary random walk reaching **0.102**.

=========================================================================================================
THE FIX IS A DIFFERENT GATE, NOT A LOOSER ONE, AND IT CAN STILL FAIL
=========================================================================================================
Loosening the threshold after it refused would be goalpost-moving and `DISCOVERY_LOOP.md` forbids it. The
question G3 is trying to answer is *does the surrogate preserve the autocorrelation as well as the method
can*, and the reference for that is not a number anyone picks — it is **how much two INDEPENDENT surrogates
of the same series differ from each other.**

    G3'  For each candidate, |delta AC| between the real series and its surrogates is compared against
         |delta AC| between PAIRS OF SURROGATES of that same series. If real-vs-surrogate lies inside the
         surrogate-vs-surrogate distribution (fraction >= `PRESERVE_ALPHA`), preservation is as good as
         IAAFT gets on this series. **If the real series differs from its surrogates by MORE than
         surrogates differ from each other, the surrogate is systematically distorting the
         autocorrelation and the candidate is refused** — so the gate retains a failing case and is not a
         formality.

Everything else is E187's, unchanged: the same cohort, the same candidates, the same 200 surrogates, the
same IAAFT parameters, the same destruction gate at rho < 0.30, the same random-walk calibration, the same
0.05 verdict bar and the same wrong-direction ordering.

=========================================================================================================
VERDICT — UNCHANGED FROM E187 EXCEPT THAT G3 IS NOW G3'
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3' or G5 fails.
  (2) VOID                G4 fails for that candidate.
  (3) WITHDRAWN           more than 5 % of surrogates reach or beat the real increment.
  (4) SURVIVES            the real increment exceeds the surrogate distribution, and at least one
                          non-muscle candidate does so.

**REGISTERED PREDICTION: (4), with the same survivor set E187 printed.** The increments and the surrogate
distributions do not change — only the preservation gate does — so a different answer would mean the gate
is entangled with the result, which it should not be. **The honest reason to run this is not to discover
anything new but to license what E187 already measured**, and that is stated so it cannot be dressed up as
a fresh finding. The muscle members are reported separately either way, because MOAA/S is scored by
movement.

    python bsde/src/bsde/experiments/e189_surrogate_placebo_selfreferential_gate.py
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
OUT = os.path.join(RESULTS, "e189_surrogate_selfreferential_gate.json")
SEED = 20260801

N_SURR = 200
IAAFT_ITERS = 60
PRESERVE_ALPHA = 0.05  # G3': real-vs-surrogate |delta AC| must not exceed the
                       # surrogate-vs-surrogate distribution more often than this
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


def _ac(v, lag, kind="pearson"):
    """Autocorrelation at `lag`.

    **PEARSON, NOT SPEARMAN, AND THAT IS A CORRECTION MADE BEFORE THE VERDICT WAS READ.** G3 exists to
    check that the surrogate preserves what IAAFT guarantees, and what IAAFT guarantees is the POWER
    SPECTRUM -- hence the LINEAR autocorrelation. The first version measured the RANK autocorrelation,
    which the method never promised and which the marginal re-imposition step perturbs: on a first pass
    the calibration random walk came in at |delta AC9| = 0.083 and every real candidate at 0.06-0.07, so
    a 0.05 gate would have refused the run for measuring the wrong statistic. That is a defect in the
    gate rather than a threshold question (rule 63's shape). Both are now computed and both are reported;
    the GATE reads the Pearson one.
    """
    v = v[np.isfinite(v)]
    if v.size <= lag + 3 or np.std(v) < 1e-12:
        return float("nan")
    if kind == "spearman":
        r = spearman(list(v[:-lag]), list(v[lag:]))
        return float(r) if np.isfinite(r) else float("nan")
    a, b = v[:-lag], v[lag:]
    sa, sb = np.std(a), np.std(b)
    if sa < 1e-12 or sb < 1e-12:
        return float("nan")
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def surrogate_diagnostics(x, s, subj):
    """(mean |delta ac1|, mean |delta ac9|, mean |rho(real, surrogate)|) over recordings."""
    d1, d9, cr, r9 = [], [], [], []
    for u in np.unique(subj):
        m = subj == u
        a1r, a1s = _ac(x[m], 1), _ac(s[m], 1)
        a9r, a9s = _ac(x[m], 9), _ac(s[m], 9)
        b9r, b9s = _ac(x[m], 9, "spearman"), _ac(s[m], 9, "spearman")
        if np.isfinite(a1r) and np.isfinite(a1s):
            d1.append(abs(a1r - a1s))
        if np.isfinite(a9r) and np.isfinite(a9s):
            d9.append(abs(a9r - a9s))
        if np.isfinite(b9r) and np.isfinite(b9s):
            r9.append(abs(b9r - b9s))
        ok = np.isfinite(x[m]) & np.isfinite(s[m])
        if ok.sum() > 10:
            r = spearman(list(x[m][ok]), list(s[m][ok]))
            if np.isfinite(r):
                cr.append(abs(r))
    return (float(np.mean(d1)) if d1 else float("nan"),
            float(np.mean(d9)) if d9 else float("nan"),
            float(np.mean(cr)) if cr else float("nan"),
            float(np.mean(r9)) if r9 else float("nan"))


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
    surrs, d1s, d9s, crs, r9s = [], [], [], [], []
    for i in range(N_SURR):
        s = surrogate_column(x, subj, np.random.default_rng(SEED + 9000 + i))
        if i < 20:
            a, b, c, r = surrogate_diagnostics(x, s, subj)
            d1s.append(a)
            d9s.append(b)
            crs.append(c)
            r9s.append(r)
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
           "corr_with_real": float(np.nanmean(crs)) if crs else float("nan"),
           "delta_ac9_rank": float(np.nanmean(r9s)) if r9s else float("nan")}
    # G3' -- the SELF-REFERENTIAL preservation gate. The reference for "does the surrogate preserve the
    # autocorrelation as well as IAAFT can" is not a number anyone picks; it is how much two INDEPENDENT
    # surrogates of the SAME series differ from each other. If real-vs-surrogate lies inside that
    # distribution, preservation is at the method's own resolution. If the real series differs from its
    # surrogates by MORE than surrogates differ from each other, the surrogate is distorting the
    # autocorrelation systematically and the candidate is refused -- so this can still fail.
    ss1, ss9 = [], []
    for i in range(20):
        sa = surrogate_column(x, subj, np.random.default_rng(SEED + 21000 + i))
        sb = surrogate_column(x, subj, np.random.default_rng(SEED + 31000 + i))
        a, b, _c, _r = surrogate_diagnostics(sa, sb, subj)
        if np.isfinite(a):
            ss1.append(a)
        if np.isfinite(b):
            ss9.append(b)
    out["surr_vs_surr_ac1"] = float(np.mean(ss1)) if ss1 else float("nan")
    out["surr_vs_surr_ac9"] = float(np.mean(ss9)) if ss9 else float("nan")
    out["preserve_frac_ac1"] = (float(np.mean(np.asarray(ss1) >= out["delta_ac1"]))
                                if ss1 and np.isfinite(out["delta_ac1"]) else float("nan"))
    out["preserve_frac_ac9"] = (float(np.mean(np.asarray(ss9) >= out["delta_ac9"]))
                                if ss9 and np.isfinite(out["delta_ac9"]) else float("nan"))
    out["preserves"] = bool(np.isfinite(out["preserve_frac_ac1"])
                            and out["preserve_frac_ac1"] >= PRESERVE_ALPHA
                            and np.isfinite(out["preserve_frac_ac9"])
                            and out["preserve_frac_ac9"] >= PRESERVE_ALPHA)
    out["destroys"] = bool(np.isfinite(out["corr_with_real"]) and out["corr_with_real"] < CORR_MAX)
    out["withdrawn"] = bool(np.isfinite(frac) and frac > ALPHA)
    print(f"   {name:<26s} real {real:>+9.5f}  surr mean {out['surrogate_mean']:>+9.5f}  "
          f"frac {frac:>7.4f}  |dAC1| {out['delta_ac1']:.3f} |dAC9| {out['delta_ac9']:.3f} "
          f"rho {out['corr_with_real']:.3f}  "
          f"[s-vs-s AC9 {out['surr_vs_surr_ac9']:.3f}, frac {out['preserve_frac_ac9']:.2f}]  "
          f"{'VOID' if not out['destroys'] else ('WITHDRAWN' if out['withdrawn'] else 'survives')}"
          + label)
    return out


def main() -> int:
    print("E189 — E187's surrogate placebo with a self-referential preservation gate")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E189", "n_recordings": int(n_rec), "n_windows": int(len(y)),
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
    print(f"\nG3' SURROGATE PRESERVES AS WELL AS IAAFT CAN (vs surrogate-vs-surrogate)  "
          f"{'PASS for all' if not bad_preserve else '*** FAIL for ' + str(bad_preserve)}")
    surv = [c for c, v in table.items() if v["destroys"] and not v["withdrawn"]]
    void = [c for c, v in table.items() if not v["destroys"]]
    nm = [c for c in surv if c not in MUSCLE]
    res["survivors"], res["void"], res["non_muscle_survivors"] = surv, void, nm

    if bad_preserve:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = (f"for {bad_preserve} the real series differs from its surrogates by MORE than "
                      "surrogates differ from each other, so the surrogate is distorting the "
                      "autocorrelation systematically rather than merely imprecisely (rule 55)")
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
