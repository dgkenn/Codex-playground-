#!/usr/bin/env python3
"""E190 — the same placebo question with a surrogate that preserves autocorrelation BY THEOREM.

REGISTERED BEFORE ANY CIRCULAR-SHIFT SURROGATE HAS BEEN COMPUTED.

=========================================================================================================
WHY A THIRD ATTEMPT, AND WHAT IS NOT BEING CHANGED
=========================================================================================================
E187 asked whether E150's eleven MOAA/S increments carry information beyond each candidate's own trend and
autocorrelation, using per-recording IAAFT surrogates. Nine of eleven beat every one of 200 surrogates.
**The verdict was NOT INTERPRETABLE**, because three candidates' lag-9 autocorrelation moved by 0.060-0.069
against a preservation tolerance of 0.05 — a round number set before anyone measured what IAAFT achieves
on drifting physiological series (rule 63).

E189 replaced that number with a comparison that cannot be accused of being picked: real-versus-surrogate
|delta AC| against **surrogate-versus-surrogate** |delta AC| on the same series. It refused **everything**.
Real-vs-surrogate sat at 0.038-0.062 at lag 9 while two independent surrogates of the same series differ by
only 0.020-0.030 — so IAAFT is not merely imprecise here, it is **systematically** shifting the lag-9
autocorrelation. That is a property of the method on these series, and it is the correct refusal.

**The gate is not being loosened. The INSTRUMENT is being replaced, and it faces the identical gate.**

    A per-recording CIRCULAR SHIFT multiplies the DFT by exp(-2*pi*i*f*k/n). The modulus is unchanged, so
    the periodogram — and hence the autocorrelation at every lag — is preserved **exactly**, not
    iteratively. The marginal distribution is preserved exactly too, because a shift is a permutation of
    the same values. Both of IAAFT's targets are hit by construction rather than by 60 iterations of
    alternating projection, which is precisely where IAAFT's residual bias comes from.

If E189's gate still refuses this, the refusal is about the finite-sample autocorrelation ESTIMATOR (the
wrap seam contributes one pair in n - lag) and not about the surrogate, and the whole approach is dead.
That is a real possible outcome and it is why the gate is carried across unchanged.

=========================================================================================================
WHAT CIRCULAR SHIFT RISKS THAT IAAFT DID NOT — THE GATE WITH NEW TEETH
=========================================================================================================
Preservation becomes free; **destruction becomes the hard part.** A shift by k leaves rho(real, surrogate)
equal to the series' own autocorrelation at lag k, so for a slowly drifting candidate a shift may not
decorrelate at all. G4 (mean |rho| < 0.30, E187's threshold, unchanged) therefore has genuine teeth here
where it had almost none under IAAFT, and the minimum shift is set to 10 % of the recording so that no
draw is a near-identity. **I expect candidates to go VOID at G4 that passed under IAAFT**, and that is the
price of a surrogate that preserves what it claims to preserve.

=========================================================================================================
TWO GATES E187 AND E189 BOTH LACKED
=========================================================================================================
G6  **A POSITIVE CONTROL.** Neither predecessor ever showed this machinery CAN return "survives" for a
    column known to carry real within-recording information. A synthetic candidate is built as the
    within-recording z-score of MOAA/S plus Gaussian noise scaled so its within-recording correlation with
    the label is ~0.3 — comparable to the incumbent's +0.3987, not a ceiling. **It MUST survive.** If the
    placebo withdraws a column that is the label by construction, the placebo is destroying real signal and
    nothing it withdraws can be read (rule 40: a machine that cannot return the right answer for a system
    whose answer is known cannot be trusted on one whose answer is not).

G5  the calibration random walk, unchanged, MUST be withdrawn.

=========================================================================================================
A LIMITATION THAT IS DECLARED, NOT DISCOVERED — AND IT APPLIES TO E187 TOO
=========================================================================================================
A circular shift within a recording preserves that recording's MEAN of the candidate exactly. So does
IAAFT. **Neither placebo can destroy between-recording information**, and a candidate whose association
with MOAA/S is entirely a between-recording one will show real increment ~ surrogate increment and be
WITHDRAWN. That is not a defect: Challenge C asks whether a measure sees a transition WITHIN a recording
before the monitor does, so within-recording alignment is the estimand. It is written here so that
"withdrawn" is never read as "carries no information" — it means "carries no information about WHEN".

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3'', G5 or G6 fails. The placebo is not licensed and no candidate row
                          may be read, whatever it says.
  (2) VOID                G4 fails for that candidate: the shift did not decorrelate it, so its surrogate
                          is not a placebo for it.
  (3) WITHDRAWN           more than 5 % of surrogates reach or beat the real increment.
  (4) SURVIVES            the real increment exceeds the surrogate distribution, and at least one
                          non-muscle, non-synthetic candidate does so.

**REGISTERED PREDICTION: (4), with a SMALLER survivor set than E187's nine**, because G4 will void the
most slowly varying candidates. Specifically I expect `whole_head_exponent` and `relative_alpha_power` —
the two that drift most over a case — to be the ones at risk, and `wpli_theta`, the noisiest, to be the
safest at G4 and the weakest at the primary. If instead G3'' refuses a surrogate whose autocorrelation is
preserved by theorem, the conclusion is that the gate is measuring its own estimator and the surrogate
family is exhausted on this deposit; that will be recorded as the result rather than repaired.

    python bsde/src/bsde/experiments/e190_circular_shift_placebo.py
"""

from __future__ import annotations

import json
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
OUT = os.path.join(RESULTS, "e190_circular_shift_placebo.json")
SEED = 20260801

N_SURR = 200
MIN_SHIFT_FRAC = 0.10   # no draw may be a near-identity shift
PRESERVE_ALPHA = 0.05   # G3'': E189's gate, carried across UNCHANGED
CORR_MAX = 0.30         # G4:   E187's threshold, carried across UNCHANGED
PERMS = 300
ALPHA = 0.05
POS_RHO = 0.30          # G6: target within-recording |rho| of the synthetic positive control

try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1


def surrogate_column(x, subj, rng):
    """Per-recording CIRCULAR SHIFT of the finite stretch.

    Exactly preserves the periodogram (a shift is a phase rotation) and exactly preserves the marginal
    (a shift is a permutation). NaNs are left where they were, and only the finite samples are rotated,
    so the surrogate has the same missingness pattern as the original.
    """
    out = np.full(x.size, np.nan)
    for u in np.unique(subj):
        m = subj == u
        v = x[m]
        ok = np.isfinite(v)
        n = int(ok.sum())
        if n < 20:
            out[m] = v
            continue
        lo = max(2, int(round(MIN_SHIFT_FRAC * n)))
        if lo >= n - lo:
            out[m] = v
            continue
        k = int(rng.integers(lo, n - lo))
        s = v.copy()
        s[ok] = np.roll(v[ok], k)
        out[m] = s
    return out


def _ac(v, lag, kind="pearson"):
    """Autocorrelation at `lag`. Pearson is the gated statistic (E189's correction, carried across)."""
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


def absolute_ac(x, subj):
    """(mean |AC1|, mean |AC9|) of the real series — the DENOMINATOR the gate implicitly divides by.

    Reported because a preservation gate phrased as a comparison of two |delta AC| has no notion of the
    scale of the thing being preserved: a shift that moves AC9 by 0.002 on a series whose AC9 is 0.7 is
    not distorting anything, and a gate that refuses it is measuring its own resolution (rule 63). This
    is an ADDED REPORTED QUANTITY and changes no threshold — the gate below is E189's, verbatim.
    """
    a1 = [_ac(x[subj == u], 1) for u in np.unique(subj)]
    a9 = [_ac(x[subj == u], 9) for u in np.unique(subj)]
    a1 = [abs(v) for v in a1 if np.isfinite(v)]
    a9 = [abs(v) for v in a9 if np.isfinite(v)]
    return (float(np.mean(a1)) if a1 else float("nan"),
            float(np.mean(a9)) if a9 else float("nan"))


def surrogate_diagnostics(x, s, subj):
    """(mean |delta ac1|, mean |delta ac9|, mean |rho(real, surrogate)|, mean |delta rank-ac9|)."""
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


def positive_control(y, subj, rng):
    """G6's synthetic candidate: within-recording z(MOAA/S) plus noise, at |rho| ~ POS_RHO.

    Built from the label, so its dependence on the outcome is not in question (rule 77's converse: a
    POSITIVE control must be measured for the dependence it claims, and the measurement is printed).
    The noise scale that gives a target within-recording correlation r is sd = sqrt(1/r^2 - 1).
    """
    sd = float(np.sqrt(1.0 / POS_RHO ** 2 - 1.0))
    out = np.full(len(y), np.nan)
    for u in np.unique(subj):
        m = subj == u
        v = np.asarray(y[m], float)
        if np.std(v) < 1e-12:
            out[m] = rng.normal(0.0, 1.0, size=int(m.sum()))
            continue
        out[m] = (v - v.mean()) / np.std(v) + rng.normal(0.0, sd, size=int(m.sum()))
    return out


def score_candidate(name, x, base, y, subj, label=""):
    ok = np.isfinite(x)
    real, p_real, _, _ = permutation_increment(base[ok], np.c_[base[ok], x[ok]], y[ok], subj[ok],
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
    # G3'' -- E189's self-referential preservation gate, carried across word for word.
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
    out["abs_ac1"], out["abs_ac9"] = absolute_ac(x, subj)
    out["relative_distortion_ac9"] = (out["delta_ac9"] / out["abs_ac9"]
                                      if np.isfinite(out["abs_ac9"]) and out["abs_ac9"] > 1e-9
                                      else float("nan"))
    out["destroys"] = bool(np.isfinite(out["corr_with_real"]) and out["corr_with_real"] < CORR_MAX)
    out["withdrawn"] = bool(np.isfinite(frac) and frac > ALPHA)
    verdict = ("VOID" if not out["destroys"]
               else ("WITHDRAWN" if out["withdrawn"] else "survives"))
    print(f"   {name:<26s} real {real:>+9.5f}  surr mean {out['surrogate_mean']:>+9.5f}  "
          f"frac {frac:>7.4f}  |dAC1| {out['delta_ac1']:.3f} |dAC9| {out['delta_ac9']:.3f} "
          f"rho {out['corr_with_real']:.3f}  "
          f"[s-vs-s AC9 {out['surr_vs_surr_ac9']:.3f}, frac {out['preserve_frac_ac9']:.2f}, "
          f"|AC9| {out['abs_ac9']:.3f}, rel {out['relative_distortion_ac9']:.3f}]  "
          f"{verdict}" + label, flush=True)
    return out


def main() -> int:
    print("E190 — circular-shift placebo: autocorrelation preserved by theorem, not by iteration")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E190", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "surrogate": "per-recording circular shift", "n_surrogates": N_SURR,
           "min_shift_frac": MIN_SHIFT_FRAC, "alpha": ALPHA, "corr_max": CORR_MAX,
           "preserve_alpha": PRESERVE_ALPHA, "candidates": {}}

    g1 = bool(n_rec == N_RECORDINGS and len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's stored "
          f"{N_RECORDINGS} / {N_WINDOWS}   {'PASS' if g1 else 'FAIL'}")
    rho = baseline_perf(base, y, subj, SEED)
    g2 = bool(np.isfinite(rho) and rho > 0.20)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho = {rho:+.4f}   {'PASS' if g2 else 'FAIL'}"
          "   (the label is never touched by this placebo, so this holds for every draw)")
    res["g1_rebuild"], res["g2_incumbent_rho"] = g1, float(rho)

    print("\nG5 CALIBRATION — a per-recording random walk, autocorrelated and unrelated to MOAA/S;"
          " it MUST be withdrawn")
    rng = np.random.default_rng(SEED + 777)
    walk = np.concatenate([np.cumsum(rng.normal(size=int((subj == u).sum())))
                           for u in np.unique(subj)])
    order = np.concatenate([np.where(subj == u)[0] for u in np.unique(subj)])
    rw = np.full(len(y), np.nan)
    rw[order] = walk
    res["calibration_random_walk"] = score_candidate("CALIBRATION random walk", rw, base, y, subj,
                                                     "   <- G5")
    g5 = bool(res["calibration_random_walk"]["withdrawn"]
              or not res["calibration_random_walk"]["destroys"])

    print("\nG6 POSITIVE CONTROL — within-recording z(MOAA/S) + noise; it MUST survive")
    pc = positive_control(y, subj, np.random.default_rng(SEED + 888))
    rr = [spearman(list(pc[subj == u]), list(np.asarray(y, float)[subj == u]))
          for u in np.unique(subj)]
    rr = [r for r in rr if np.isfinite(r)]
    print(f"   measured within-recording rho(control, MOAA/S) = {np.mean(rr):+.3f} "
          f"over {len(rr)} recordings (target {POS_RHO:+.2f})")
    res["positive_control_rho"] = float(np.mean(rr)) if rr else float("nan")
    res["positive_control"] = score_candidate("POSITIVE control", pc, base, y, subj, "   <- G6")
    g6 = bool(res["positive_control"]["destroys"] and not res["positive_control"]["withdrawn"])

    print("\ncandidate                        real   surr mean      frac  diagnostics  verdict")
    for name in E150_ADDS:
        x = cand.get(name)
        if x is None:
            continue
        res["candidates"][name] = score_candidate(
            name, x, base, y, subj, "   MUSCLE" if name in MUSCLE else "")

    bad_pres = [n for n, v in list(res["candidates"].items())
                + [("CALIBRATION", res["calibration_random_walk"]),
                   ("POSITIVE", res["positive_control"])] if not v["preserves"]]
    g3 = not bad_pres
    res["g3_preserves"], res["g5_calibration_withdrawn"], res["g6_positive_survives"] = g3, g5, g6
    res["preservation_failures"] = bad_pres

    surv = [n for n, v in res["candidates"].items() if v["destroys"] and not v["withdrawn"]]
    void = [n for n, v in res["candidates"].items() if not v["destroys"]]
    res["survivors"], res["void"] = surv, void
    non_muscle = [n for n in surv if n not in MUSCLE]

    print("\n" + "=" * 100)
    if not g1 or not g2:
        v, why = "NOT INTERPRETABLE", "the cohort or the incumbent gate failed"
    elif not g3:
        v, why = "NOT INTERPRETABLE", (
            f"for {bad_pres} the real series differs from its circular shifts by MORE than shifts "
            "differ from each other, so the gate is measuring the finite-sample autocorrelation "
            "ESTIMATOR rather than the surrogate — the shift preserves the periodogram exactly "
            "(rule 55)")
    elif not g5:
        v, why = "NOT INTERPRETABLE", ("the calibration random walk was NOT withdrawn, so the placebo "
                                       "is anti-conservative for autocorrelated noise")
    elif not g6:
        v, why = "NOT INTERPRETABLE", (
            "the POSITIVE control — the label itself plus noise — did not survive, so the placebo "
            "destroys real within-recording information and nothing it withdraws can be read (rule 40)")
    elif non_muscle:
        v, why = "SURVIVES", (f"{len(surv)} of {len(res['candidates'])} candidates beat their circular-"
                              f"shift distribution, {len(non_muscle)} of them non-muscle: {non_muscle}; "
                              f"{len(void)} were VOID at G4 ({void})")
    elif surv:
        v, why = "MUSCLE ONLY", f"only muscle candidates survived: {surv}"
    else:
        v, why = "ALL WITHDRAWN", "no candidate beat its circular-shift distribution"
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("LIMITATION, declared at registration: a circular shift preserves each recording's MEAN "
          "exactly, so\n  between-recording information survives the placebo by construction. "
          "WITHDRAWN means 'carries no\n  information about WHEN within a recording', never 'carries "
          "no information'.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
