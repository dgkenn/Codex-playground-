"""E101 -- Does averaging sessions raise E86's D1 by the amount E97's ICC PREDICTS?

REGISTERED BEFORE ANY AVERAGING IS RUN. This is a quantitative consequence of a qualitative verdict, and
it is the first thing in Challenge B that can falsify a result we already like.

=========================================================================================================
WHY THIS EXISTS
=========================================================================================================
E97 called `ge_norm` TRAIT-LIKE (ICC(2,1) 0.4288 [0.2486, 0.5438]) and on that basis E86's qualification 3
-- a null D2 change-score design sitting beside a positive D1 -- was declared expected by construction
rather than evidence against D1.

**That argument makes a numerical prediction it has never been asked to honour.** If the session-to-session
variation in `ge_norm` is measurement error on a stable subject value, then the reliability of a k-session
MEAN follows Spearman-Brown,

        rho_k = k * rho / (1 + (k - 1) * rho),

and the observed between-subject correlation with accuracy is attenuated by sqrt(rho_k). So averaging more
sessions must RAISE the observed correlation, by a factor that is fixed in advance by the measured ICC:

        r(k) = r(1) * sqrt( rho_k / rho_1 ).

With rho = 0.4288 and k = 3: rho_3 = 0.6925, and the predicted gain is sqrt(0.6925/0.4288) = **1.271**.

If instead the between-session variation is real signal -- state, drift, montage, whatever -- then
averaging it away does not help and r(3) sits at r(1). **The two readings of E97 make different numbers,
and 61 subjects with exactly three sessions each can tell them apart.** No new data is required.

=========================================================================================================
ESTIMAND -- a comparison between two pre-stated predictions, not a threshold (rule 63)
=========================================================================================================
Subjects with exactly 3 usable sessions (n = 61 of 62; the single 2-session subject is dropped so that n
is IDENTICAL at every k and no coverage difference can masquerade as an averaging effect).

The ACCURACY side is held fixed at the subject mean over all three sessions at every k. Only the FEATURE's
reliability is varied, because only the feature's reliability is what Spearman-Brown is about. Varying
both would confound the two attenuations and the prediction would no longer be the one E97 licenses.

    r(k) = mean over DRAWS of spearman( mean of k randomly drawn sessions' ge_norm , subject-mean accuracy )

    500 draws at k = 1 and k = 2; k = 3 is deterministic.

    P   the observed r(3), against TWO pre-stated competing values computed from the SAME data:
            H_error : r_pred = r(1) * sqrt(rho_3 / rho_1)     [ E97's reading; rho from THIS subset ]
            H_signal: r_pred = r(1)                           [ averaging does not help ]
        Test statistic reported both ways: d_error = r(3) - r(1)*sqrt(rho_3/rho_1)
                                           d_signal = r(3) - r(1)
        Subject bootstrap (4000 reps), the WHOLE procedure resampled inside each rep -- ICC, r(1) and
        r(3) are all recomputed on the resampled subjects, because r(1) and the ICC appear inside the
        prediction and treating them as fixed would understate the interval (rule 9's shape: what is
        refit must be refit inside the resample).

VERDICT, wrong direction FIRST (rule 37):

    (a) r(3) < r(1) with the d_signal interval excluding 0  -> AVERAGING HURTS. The between-session
        variation carries the association; `ge_norm`'s D1 is driven by something that averaging destroys.
        E97's trait reading is wrong in the direction that matters and **E86's qualification 3 returns,
        worse than before** -- because now the change-score null has a positive explanation.
    (b) d_signal interval includes 0 and d_error interval EXCLUDES 0 -> NO GAIN. Averaging does not help by
        the predicted amount; the session variation is not measurement error on a trait. E97's verdict
        survives as a description of the ICC and fails as an explanation of D2.
    (c) BOTH intervals include 0 -> UNDETERMINED, and it must print as that. With 61 subjects the interval
        on a difference of correlations is wide enough that this is a likely outcome, and it is NOT
        evidence for either reading. Named here so it cannot be reported as support afterwards (rule 31).
    (d) d_error interval includes 0 and d_signal interval EXCLUDES 0 -> CONSISTENT WITH MEASUREMENT ERROR.
        The trait reading survives a quantitative test it could have failed, and E86's qualification 3
        stays dissolved.

PREDICTED: (c) UNDETERMINED is the most likely single outcome and (d) the most likely informative one. It
is worth saying plainly that (c) is expected, so that a wide interval is not later read as a near-miss.

=========================================================================================================
CONTROLS -- bracketing the estimator, the E72/E97 pattern
=========================================================================================================
    C+  `alpha_prom`, ICC 0.8411. A high-reliability measure has almost nothing to gain from averaging:
        predicted gain sqrt(0.9407/0.8411) = 1.058. If this returns a LARGE gain the procedure is
        manufacturing one and nothing below it is interpretable.
    C-  a per-session Gaussian draw. r(k) must stay at ~0 for every k. If averaging noise raises a
        correlation with accuracy, the averaging itself is the effect.
    Also reported for `cl_norm`, `modularity` and `iaf`, without any claim attached, because the shape of
    gain-versus-ICC across five measures is more informative than any single one of them.

GATES (rule 40):
    G1  COVERAGE   >= 30 subjects with exactly 3 sessions joined to an accuracy.
    G2  ICC USABLE on this subset: rho_1 for `ge_norm` finite and in (0, 1). Outside that, rho_3 is not
        defined and the prediction does not exist -- report ABSENT, not a verdict (rule 31).
    G3  r(1) NON-DEGENERATE: |r(1)| >= 0.05. Below that both predictions collapse onto zero and onto each
        other, and the two hypotheses are not distinguishable by any amount of data. This gate is a
        statement about identifiability, not about significance.
    G4  THE PREDICTIONS MUST DIFFER: |r(1)*sqrt(rho_3/rho_1) - r(1)| >= 0.02. Same reason as G3, stated on
        the quantity that actually has to be resolved.

=========================================================================================================
AMENDMENT, WRITTEN AFTER THE FIRST PASS AND BEFORE THE SECOND -- see `results/e101_first_pass_note.md`
=========================================================================================================
The first pass ran and its verdict was WITHDRAWN. The registered rule required `d_signal = r(3) - r(1)`
to exclude zero, and **that condition is satisfied by construction for any measure with imperfect
reliability, including pure noise**: for three independent noise columns, r(3) = sqrt(3) * r(1) exactly,
so d_signal = 0.73 * r(1) is non-zero whenever r(1) is. The `__gauss__` control demonstrated it in the
first pass, going +0.1127 -> +0.1441, and would have passed that limb itself. Rule 33, recurring:
**write down what shape the null produces before choosing the statistic.**

Two further faults of the same family, both mine: the C- noise control was stated in this docstring as
"must come back at ~0" and never wired to a gate (the E87 pattern, second occurrence), and a SINGLE
Gaussian realisation cannot calibrate a procedure whose Spearman standard error at n = 61 is about 0.13.

THE CORRECTION, which is not a moved goalpost. The theory that produced the registered prediction produces
a second one for free, and it was available before the run: if the sessions carried no stable subject
signal at all, the gain would be exactly sqrt(k). So the comparison becomes two competing MODELS, both
computable, neither of them "no change":

        H_error :  gain = sqrt(rho_3 / rho_1),  rho_1 measured on this subset   -> 1.267 for ge_norm
        H_noise :  gain = sqrt(k) = sqrt(3)                                     -> 1.732

    P   r(3) against both, via d_error = r(3) - r(1)*gain_error and d_noise = r(3) - r(1)*sqrt(3).

The wrong-direction branch, the UNDETERMINED branch, the cohort, the estimator and G1-G4 are all
unchanged. What changed is that an uninformative comparison was replaced by an informative one derived
from the same theory. `d_signal` is still computed and printed, marked as uninformative, because deleting
it would hide the correction.

C- IS NOW A REAL GATE, and a calibration rather than a single draw: 200 independent Gaussian features are
run through the entire procedure and the rate at which each limb of the verdict fires on noise is
MEASURED (rule 26). G5 requires that the H_error limb fire on noise at no more than 10 %.

COMPUTE NOTE, stated because it is a deliberate accuracy trade: the point estimates use 500 subset draws,
the outer bootstrap uses 100 per replicate and the calibration arm 60. Subset-draw noise averages out
across bootstrap replicates; it does not average out of a point estimate, which is why they differ.

SCOPE. Stieger BCI only. `ge_norm` here is the null-normalised global efficiency of E86, not a general
network measure, and accuracy is BCI control accuracy, not a clinical outcome. Nothing about
consciousness is claimed or tested.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRAPH_TABLE = os.path.join(RESULTS, "stieger_graph62.csv")
ACC_TABLE = os.path.join(RESULTS, "stieger_labels.csv")
OUT = os.path.join(RESULTS, "e101_spearman_brown_transport.json")

PRIMARY = "ge_norm"
TRAIT_CTRL = "alpha_prom"
NOISE_CTRL = "__gauss__"
ALSO = ["cl_norm", "modularity", "iaf"]

N_SESSIONS = 3
MIN_SUBJECTS = 30
MIN_R1 = 0.05
MIN_PRED_GAP = 0.02
DRAWS = 500
BOOT_DRAWS = 100
CAL_DRAWS = 60
REPS = 4000
CAL_REPS = 600
N_CALIB = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return float("nan")
    rx = np.argsort(np.argsort(x[ok])).astype(float)
    ry = np.argsort(np.argsort(y[ok])).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def icc21(groups):
    """ICC(2,1), one-way decomposition with the k0 correction. Same estimator as E97, by construction:
    the prediction tested here is E97's, so it must be built on E97's number and not a second opinion."""
    groups = [np.asarray(g, float) for g in groups]
    groups = [g[np.isfinite(g)] for g in groups]
    groups = [g for g in groups if g.size >= 2]
    if len(groups) < 5:
        return float("nan")
    n = len(groups)
    ns = np.array([g.size for g in groups], float)
    grand = np.concatenate(groups).mean()
    msb = float(np.sum(ns * (np.array([g.mean() for g in groups]) - grand) ** 2) / (n - 1))
    within = np.concatenate([(g - g.mean()) ** 2 for g in groups])
    dfw = float(ns.sum() - n)
    msw = float(within.sum() / dfw) if dfw > 0 else float("nan")
    k0 = float((ns.sum() - (ns ** 2).sum() / ns.sum()) / (n - 1))
    if not np.isfinite(msw) or k0 <= 0:
        return float("nan")
    den = msb + (k0 - 1) * msw
    return float((msb - msw) / den) if abs(den) > 1e-12 else float("nan")


def sb(rho, k):
    """Spearman-Brown reliability of a k-fold mean."""
    if not np.isfinite(rho) or rho <= 0:
        return float("nan")
    return float(k * rho / (1.0 + (k - 1) * rho))


def r_at_k(F, acc, k, rng, draws=DRAWS):
    """Mean Spearman correlation between a k-session mean of F and the fixed subject-mean accuracy.

    F is (n_subjects, N_SESSIONS). At k = N_SESSIONS there is one subset, so no averaging over draws is
    done and `draws` is ignored -- averaging identical values would silently shrink nothing but would
    make the code read as if k=3 carried draw noise that it does not.
    """
    n, s = F.shape
    if k >= s:
        return spearman(np.nanmean(F, axis=1), acc)
    vals = []
    for _ in range(draws):
        # an INDEPENDENT subset per subject: subjects are exchangeable, sessions within subject are not
        idx = np.argsort(rng.random((n, s)), axis=1)[:, :k]
        m = np.nanmean(np.take_along_axis(F, idx, axis=1), axis=1)
        v = spearman(m, acc)
        if np.isfinite(v):
            vals.append(v)
    return float(np.mean(vals)) if vals else float("nan")


def procedure(F, acc, rng, draws=DRAWS, with_r2=True):
    """r(1), r(3), rho_1, rho_3, and both prediction residuals -- everything recomputed together.

    Returned as a dict so the bootstrap can resample subjects and re-run this whole function, which is
    what makes the interval honest: rho and r(1) are INSIDE the prediction, so holding them fixed while
    resampling r(3) would price only part of the variability (rule 9's shape).
    """
    rho1 = icc21([F[i] for i in range(F.shape[0])])
    rho3 = sb(rho1, N_SESSIONS)
    r1 = r_at_k(F, acc, 1, rng, draws)
    r3 = r_at_k(F, acc, N_SESSIONS, rng, draws)
    gain = float(np.sqrt(rho3 / rho1)) if np.isfinite(rho1) and rho1 > 0 else float("nan")
    gain_noise = float(np.sqrt(N_SESSIONS))          # the ICC-equals-zero model, available before the run
    return {"rho1": rho1, "rho3": rho3, "r1": r1,
            "r2": r_at_k(F, acc, 2, rng, draws) if with_r2 else float("nan"), "r3": r3,
            "gain": gain, "gain_noise": gain_noise,
            "pred_error": r1 * gain, "pred_noise": r1 * gain_noise, "pred_signal": r1,
            "d_error": r3 - r1 * gain, "d_noise": r3 - r1 * gain_noise,
            "d_signal": r3 - r1}


def ci(vals):
    v = np.sort(np.asarray([x for x in vals if np.isfinite(x)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    for p in (GRAPH_TABLE, ACC_TABLE):
        if not os.path.exists(p):
            print(f"ABSENT: {p}")
            return 2

    acc_by = {}
    for r in csv.DictReader(open(ACC_TABLE, newline="")):
        if r.get("accuracy"):
            acc_by[(r["subject"], int(r["session"]))] = _f(r["accuracy"])
    by = defaultdict(dict)
    for r in csv.DictReader(open(GRAPH_TABLE, newline="")):
        k = (r["subject"], int(r["session"]))
        if k in acc_by:
            by[r["subject"]][int(r["session"])] = (r, acc_by[k])

    subs = sorted(s for s, v in by.items() if len(v) == N_SESSIONS)
    res = {"gates": {"G1_n_subjects": len(subs),
                     "G1_pass": bool(len(subs) >= MIN_SUBJECTS)},
           "n_subjects_any": len(by), "features": {}}
    print(f"{len(by)} subjects joined to an accuracy; {len(subs)} with exactly {N_SESSIONS} sessions")
    print(f"G1 coverage  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}  "
          f"({len(subs)} >= {MIN_SUBJECTS})")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    acc = np.array([np.nanmean([by[s][k][1] for k in sorted(by[s])]) for s in subs])

    def matrix(feat):
        if feat == NOISE_CTRL:
            return rng.normal(size=(len(subs), N_SESSIONS))
        return np.array([[_f(by[s][k][0].get(feat, "")) for k in sorted(by[s])] for s in subs])

    feats = [PRIMARY, TRAIT_CTRL, NOISE_CTRL] + ALSO
    print(f"\n{'feature':<14s} {'ICC':>7s} {'gain_e':>7s} {'r(1)':>7s} {'r(3)':>7s} "
          f"{'pred_err':>9s} {'pred_noi':>9s} {'d_error':>9s} {'d_noise':>9s} {'[d_signal]':>11s}")
    for f in feats:
        F = matrix(f)
        pt = procedure(F, acc, np.random.default_rng(SEED + 1))
        res["features"][f] = pt
        print(f"{f:<14s} {pt['rho1']:7.4f} {pt['gain']:7.3f} {pt['r1']:+7.4f} {pt['r3']:+7.4f} "
              f"{pt['pred_error']:+9.4f} {pt['pred_noise']:+9.4f} {pt['d_error']:+9.4f} "
              f"{pt['d_noise']:+9.4f} {pt['d_signal']:+11.4f}")
    print("   [d_signal] is printed but UNINFORMATIVE by construction -- see the amendment")

    p = res["features"][PRIMARY]
    g2 = bool(np.isfinite(p["rho1"]) and 0.0 < p["rho1"] < 1.0)
    g3 = bool(np.isfinite(p["r1"]) and abs(p["r1"]) >= MIN_R1)
    g4 = bool(np.isfinite(p["pred_error"]) and abs(p["pred_error"] - p["r1"]) >= MIN_PRED_GAP)
    res["gates"].update({"G2_rho1": p["rho1"], "G2_pass": g2,
                         "G3_r1": p["r1"], "G3_pass": g3,
                         "G4_pred_gap": float(abs(p["pred_error"] - p["r1"])), "G4_pass": g4})
    print(f"\nG2 ICC usable      {'PASS' if g2 else 'FAIL'}  rho_1={p['rho1']:.4f}")
    print(f"G3 r(1) non-degen  {'PASS' if g3 else 'FAIL'}  |r(1)|={abs(p['r1']):.4f} >= {MIN_R1}")
    print(f"G4 predictions differ {'PASS' if g4 else 'FAIL'}  "
          f"|{p['pred_error']:+.4f} - {p['r1']:+.4f}| = {abs(p['pred_error']-p['r1']):.4f} "
          f">= {MIN_PRED_GAP}")
    if not (g2 and g3 and g4):
        # rule 31: a failed precondition yields ABSENT, never a verdict
        res["verdict"] = "ABSENT -- precondition failed, the two hypotheses are not distinguishable here"
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- subject bootstrap, whole procedure inside each rep -------------------------------------
    Fp = matrix(PRIMARY)
    brng = np.random.default_rng(SEED + 2)
    de, dn, ds, r3s = [], [], [], []
    for _ in range(REPS):
        idx = brng.integers(0, len(subs), len(subs))
        out = procedure(Fp[idx], acc[idx], brng, draws=BOOT_DRAWS, with_r2=False)
        de.append(out["d_error"]); dn.append(out["d_noise"])
        ds.append(out["d_signal"]); r3s.append(out["r3"])
    de_lo, de_hi = ci(de)
    dn_lo, dn_hi = ci(dn)
    ds_lo, ds_hi = ci(ds)
    r3_lo, r3_hi = ci(r3s)
    res["bootstrap"] = {"d_error": [de_lo, de_hi], "d_noise": [dn_lo, dn_hi],
                        "d_signal": [ds_lo, ds_hi], "r3": [r3_lo, r3_hi],
                        "reps": REPS, "draws": DRAWS, "boot_draws": BOOT_DRAWS}
    print(f"\nBOOTSTRAP ({REPS} subject resamples, procedure refit inside each, "
          f"{BOOT_DRAWS} subset draws per replicate)")
    print(f"  r(3)      {p['r3']:+.4f}  [{r3_lo:+.4f}, {r3_hi:+.4f}]")
    print(f"  d_error   {p['d_error']:+.4f}  [{de_lo:+.4f}, {de_hi:+.4f}]   "
          f"(0 => r(3) matches the ICC-implied gain {p['gain']:.3f})")
    print(f"  d_noise   {p['d_noise']:+.4f}  [{dn_lo:+.4f}, {dn_hi:+.4f}]   "
          f"(0 => r(3) matches the ICC=0 gain sqrt(3)={p['gain_noise']:.3f})")
    print(f"  [d_signal]{p['d_signal']:+.4f}  [{ds_lo:+.4f}, {ds_hi:+.4f}]   UNINFORMATIVE, see amendment")

    # ---- G5 CALIBRATION: how often does each limb fire on pure noise? ----------------------------
    crng = np.random.default_rng(SEED + 3)
    fires_e, fires_n, r1s = 0, 0, []
    for _ in range(N_CALIB):
        Z = crng.normal(size=(len(subs), N_SESSIONS))
        pz = procedure(Z, acc, crng, draws=CAL_DRAWS, with_r2=False)
        r1s.append(pz["r1"])
        bd_e, bd_n = [], []
        for _ in range(CAL_REPS):
            j = crng.integers(0, len(subs), len(subs))
            o = procedure(Z[j], acc[j], crng, draws=CAL_DRAWS, with_r2=False)
            bd_e.append(o["d_error"]); bd_n.append(o["d_noise"])
        el, eh = ci(bd_e); nl, nh = ci(bd_n)
        # the H_error limb "fires" when the ICC prediction is accepted and the noise model rejected
        if np.isfinite(el) and (el <= 0.0 <= eh) and np.isfinite(nl) and not (nl <= 0.0 <= nh):
            fires_e += 1
        if np.isfinite(nl) and (nl <= 0.0 <= nh) and np.isfinite(el) and not (el <= 0.0 <= eh):
            fires_n += 1
    rate_e = fires_e / float(N_CALIB)
    g5 = bool(rate_e <= 0.10)
    res["gates"].update({"G5_calibration_H_error_rate": rate_e,
                         "G5_calibration_H_noise_rate": fires_n / float(N_CALIB),
                         "G5_calibration_median_abs_r1": float(np.median(np.abs(r1s))),
                         "G5_pass": g5, "G5_n": N_CALIB})
    print(f"\nG5 CALIBRATION on {N_CALIB} independent Gaussian features "
          f"(median |r(1)| {np.median(np.abs(r1s)):.4f})")
    print(f"   H_error limb fires on noise {rate_e*100:.1f} %   "
          f"H_noise limb fires {fires_n/N_CALIB*100:.1f} %   {'PASS' if g5 else 'FAIL'} (<= 10 %)")

    err_ok = de_lo <= 0.0 <= de_hi
    noi_ok = dn_lo <= 0.0 <= dn_hi
    if not g5:
        v = (f"NOT-INTERPRETABLE -- the H_error limb fires on pure noise {rate_e*100:.1f} % of the time, "
             "so accepting it here would say nothing about ge_norm (rule 26)")
    elif p["d_signal"] < 0 and not (ds_lo <= 0.0 <= ds_hi):
        v = ("AVERAGING HURTS -- the between-session variation carries the association; E97's trait "
             "reading fails in the direction that matters and E86 qualification 3 RETURNS")
    elif err_ok and not noi_ok:
        v = ("CONSISTENT WITH MEASUREMENT ERROR -- r(3) matches the gain the measured ICC implies and is "
             "incompatible with the ICC=0 model; E86 qualification 3 stays dissolved")
    elif noi_ok and not err_ok:
        v = ("CONSISTENT WITH NO STABLE SUBJECT SIGNAL -- r(3) matches the sqrt(k) gain of pure noise and "
             "not the ICC-implied one; E97's trait reading fails and E86 qualification 3 RETURNS")
    elif err_ok and noi_ok:
        v = ("UNDETERMINED -- both models lie inside the interval; 61 subjects cannot separate a gain of "
             f"{p['gain']:.3f} from {p['gain_noise']:.3f}. NOT support for either reading, and named as "
             "the likely outcome before the first pass")
    else:
        v = ("INCONSISTENT WITH BOTH -- r(3) departs from the ICC-implied gain AND from the sqrt(k) gain; "
             "the measurement-error family does not describe this feature at all")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")

    ctrl = res["features"][TRAIT_CTRL]
    noise = res["features"][NOISE_CTRL]
    print(f"\nCONTROLS   {TRAIT_CTRL}: ICC {ctrl['rho1']:.4f}, predicted gain {ctrl['gain']:.3f}, "
          f"r(1)->r(3) {ctrl['r1']:+.4f} -> {ctrl['r3']:+.4f}")
    print(f"           noise: ICC {noise['rho1']:+.4f}, r(1)->r(3) "
          f"{noise['r1']:+.4f} -> {noise['r3']:+.4f}  (must stay ~0)")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
