"""E89 -- VitalDB: does the aperiodic exponent add to BIS for EMERGENCE PROXIMITY, an endpoint BIS did not define?

REGISTERED BEFORE ANY MODEL IS FIT. What was read of `vitaldb_grid.csv` beforehand, and nothing else: its
column names, and the label's feasibility counts -- 6,679 windows over 250 subjects; `meta_rel_aneend_s`
ranges -38,405 to +300 s with median -5,189; **579 windows (8.7 %) lie within 600 s of anaesthesia end**,
and 134 of 250 cases carry at least three such windows. No feature has been related to any label.

=========================================================================================================
WHY THIS ENDPOINT AND NOT BIS ITSELF
=========================================================================================================
VitalDB's only continuous brain-state label IS BIS, so "does X add to BIS at predicting BIS-defined depth"
is circular, and this project has measured what that circularity costs: E65 fitted an index to VitalDB BIS
and it reached rho **+0.04** against a clinician's MOAA/S on an external deposit, where that deposit's own
permutation entropy reached **+0.48**. **Fitting to the device destroyed the information the ingredients
individually carried.**

`meta_rel_aneend_s` is different in kind. Anaesthesia end is a **timestamped clinical event**, recorded by
the anaesthetist, not computed from the EEG and not derived from BIS. Predicting proximity to it is the
"lightening / emergence trend" use case, and it is the one endpoint on this deposit that BIS did not define.

=========================================================================================================
DESIGN
=========================================================================================================
    LABEL, fixed now: `is_emergence` = |meta_rel_aneend_s| <= 600 s. Base rate 8.7 %, above the 5 % floor
    that refused E27, and chosen before any model was fit.

    BASELINE  BIS alone (the incumbent, named -- rule 45).
    TEST      BIS + `whole_head_exponent`.

    P  Out-of-bag AUC increment of TEST over BASELINE, clustered on CASE (rule 9: each replicate fits both
       models on the drawn cases' rows and scores both on the rows of cases NOT drawn). 400 replicates.

    **THE PRIMARY IS UNRESTRICTED.** Rule 49, learned the hard way in E46: never select rows on the
    incumbent you intend to beat. Restricting to `BIS < 60` -- which this project's own artefact decision
    document otherwise requires -- would select on BIS while BIS is in the model, and six of six
    candidates once passed a comparison for exactly that reason. The artefact restriction is therefore a
    declared SECONDARY arm, reported beside the primary and never in place of it.

ARMS, all pre-declared:

    A1  PRIMARY        all windows with finite BIS and exponent
    A2  ARTEFACT       BIS < 60 and SQI >= 50 -- the repository's own validated band. Secondary, because
                       it selects on the incumbent.
    A3  MUSCLE         baseline becomes BIS + `meta_emg` (the MONITOR'S OWN EMG channel, not a scalp
                       proxy). E69/E71 showed this project's scalp proxy correlates with a real submental
                       channel at only rho +0.20, so a device EMG channel is a materially better control
                       than the gamma-power residualisation usually offered. If the exponent's increment
                       disappears here, it was muscle.
    A4  NEGATIVE       a per-window Gaussian column in place of the exponent. Must NOT add.

VERDICT for the primary, wrong direction FIRST (rule 37):

    (a) interval excludes 0 and NEGATIVE -> HURTS. Adding the exponent makes out-of-bag prediction worse.
        Not a null; it means the exponent is noise the model spends capacity on.
    (b) interval includes 0              -> NO INCREMENT.
    (c) interval excludes 0 and POSITIVE -> ADDS, subject to A3 and A4.

GATES (rule 40), before any arm:

    G1  THE INCUMBENT MUST BE ALIVE (rule 53 / E33). BIS alone must reach out-of-bag AUC > 0.55 for
        emergence proximity. **If BIS cannot see emergence coming, "the exponent adds to BIS" is a
        statement about the label, not about the exponent** -- the trap E61 fell into.
    G2  COVERAGE  >= 100 cases and >= 200 positive windows.
    G3  NEGATIVE CONTROL. A4 must not return ADDS.

SCOPE, and it is narrow on purpose. This asks whether a single-channel aperiodic exponent carries
information about proximity to a clinical emergence event beyond a commercial index, on one retrospective
deposit. It is not a claim about consciousness, not a claim about awareness, and not evidence that anything
should be displayed to a clinician. VitalDB structurally contains **no awake-under-monitor windows** -- the
strip goes on after induction -- so nothing here speaks to the light end of the scale, and this experiment
does not attempt to.

    python -m bsde.experiments.e89_vitaldb_emergence_increment
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import oob_auc_increment                            # noqa: E402

TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e89_vitaldb_emergence_increment.json")

FEATURE = "whole_head_exponent"
EMERGENCE_S = 600.0
BIS_MAX, SQI_MIN = 60.0, 50.0
MIN_CASES, MIN_POSITIVE = 100, 200
G1_MIN_AUC = 0.55
REPS = 400
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def auc(y, s):
    y = np.asarray(y, int)
    s = np.asarray(s, float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    if y.sum() == 0 or y.sum() == y.size:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(s.size, float)
    ranks[order] = np.arange(1, s.size + 1)
    # average ranks for ties
    su = np.sort(s)
    i = 0
    while i < su.size:
        j = i
        while j + 1 < su.size and su[j + 1] == su[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    n1 = int(y.sum())
    n0 = y.size - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def fit_score(Xtr, ytr, Xte):
    """Ridge on standardised training rows, with an intercept -- the same discipline E84 uses."""
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    A = np.column_stack([np.ones(Xtr.shape[0]), (Xtr - mu) / sd])
    P = np.eye(A.shape[1]); P[0, 0] = 0.0
    w = np.linalg.solve(A.T @ A + P, A.T @ ytr.astype(float))
    return np.column_stack([np.ones(Xte.shape[0]), (Xte - mu) / sd]) @ w


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}"); return 2
    rows = list(csv.DictReader(open(TABLE, newline="")))
    res = {"gates": {}, "arms": {}, "label": {"definition": f"|rel_aneend_s| <= {EMERGENCE_S}"}}

    def build(mask_fn, extra_baseline=()):
        y, subj, base, feat = [], [], [], []
        for r in rows:
            bis, sqi = _f(r["meta_bis"]), _f(r["meta_sqi"])
            e, x = _f(r["meta_rel_aneend_s"]), _f(r.get(FEATURE, ""))
            ex = [_f(r.get(k, "")) for k in extra_baseline]
            if not (np.isfinite(bis) and np.isfinite(e) and np.isfinite(x)) or not all(np.isfinite(ex)):
                continue
            if not mask_fn(bis, sqi):
                continue
            y.append(1 if abs(e) <= EMERGENCE_S else 0)
            subj.append(r["subject"])
            base.append([bis] + ex)
            feat.append(x)
        return (np.asarray(y, int), np.asarray(subj), np.asarray(base, float),
                np.asarray(feat, float))

    y, subj, Xa, x = build(lambda b, s: True)
    n_cases = len(set(subj.tolist()))
    res["gates"].update({"G2_cases": n_cases, "G2_positive": int(y.sum()),
                         "G2_pass": bool(n_cases >= MIN_CASES and y.sum() >= MIN_POSITIVE)})
    print(f"{len(rows)} rows -> {y.size} usable windows, {n_cases} cases, "
          f"{int(y.sum())} positive ({100*y.mean():.1f} %)")
    print(f"G2 coverage   {'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    # G1: the incumbent must be alive, measured out of bag on the same clustering
    rng = np.random.default_rng(SEED)
    uniq = np.unique(subj)
    aucs = []
    for _ in range(100):
        drawn = set(rng.choice(uniq, size=uniq.size, replace=True).tolist())
        tr = np.isin(subj, list(drawn)); te = ~tr
        if te.sum() < 50 or tr.sum() < 50 or y[te].sum() == 0 or y[te].sum() == te.sum():
            continue
        a = auc(y[te], fit_score(Xa[tr], y[tr], Xa[te]))
        if np.isfinite(a):
            aucs.append(a)
    g1 = float(np.median(aucs)) if aucs else float("nan")
    res["gates"].update({"G1_baseline_oob_auc": g1,
                         "G1_pass": bool(np.isfinite(g1) and g1 > G1_MIN_AUC)})
    print(f"G1 incumbent  BIS alone, out-of-bag AUC for emergence proximity = {g1:.4f}   "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"]):
        print("\nGATE FAILED -- no arm is evaluated. Verdict ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    def run_arm(name, mask_fn, extra_baseline=(), use_noise=False):
        yy, ss, XA, xx = build(mask_fn, extra_baseline)
        if yy.size < 100 or yy.sum() < 20:
            res["arms"][name] = {"status": "TOO FEW"}
            print(f"{name:<12s} TOO FEW ({yy.size} windows, {int(yy.sum())} positive)")
            return
        if use_noise:
            xx = np.random.default_rng(SEED + 9).normal(size=xx.size)
        XB = np.column_stack([XA, xx])
        pt, lo, hi = oob_auc_increment(XA, XB, yy, ss, np.random.default_rng(SEED + 1), reps=REPS)[:3]
        v = ("NOT-COMPUTABLE" if not np.isfinite(pt) else
             "HURTS" if (lo < 0 and hi < 0) else
             "ADDS" if (lo > 0 and hi > 0) else "NO INCREMENT")
        res["arms"][name] = {"increment": pt, "lo": lo, "hi": hi, "verdict": v,
                             "n_windows": int(yy.size), "n_cases": len(set(ss.tolist())),
                             "n_positive": int(yy.sum())}
        print(f"{name:<12s} {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]  {v:<14s} "
              f"({yy.size} windows, {len(set(ss.tolist()))} cases, {int(yy.sum())} pos)")

    print(f"\n{'arm':<12s} {'increment':>9s} {'95% CI':>22s}  verdict")
    run_arm("A1 PRIMARY", lambda b, s: True)
    run_arm("A2 ARTEFACT", lambda b, s: b < BIS_MAX and np.isfinite(s) and s >= SQI_MIN)
    run_arm("A3 MUSCLE", lambda b, s: True, extra_baseline=("meta_emg",))
    run_arm("A4 NEGATIVE", lambda b, s: True, use_noise=True)

    res["gates"]["G3_pass"] = res["arms"].get("A4 NEGATIVE", {}).get("verdict") != "ADDS"
    p = res["arms"].get("A1 PRIMARY", {})
    m = res["arms"].get("A3 MUSCLE", {})
    verdict = p.get("verdict", "NOT-COMPUTABLE")
    if verdict == "ADDS":
        if not res["gates"]["G3_pass"]:
            verdict = "WITHDRAWN -- the Gaussian negative control also ADDS; the machinery is leaking."
        elif m.get("verdict") != "ADDS":
            verdict = ("ADDS-BUT-MUSCLE -- the increment does not survive adding the monitor's own EMG "
                       "channel to the baseline, so it is muscle rather than brain state.")
        else:
            verdict = ("ADDS, and it survives the monitor's own EMG channel. One retrospective deposit, "
                       "an emergence-proximity endpoint, no claim about consciousness or awareness.")
    res["verdict"] = verdict
    print(f"\nG3 negative control  {'PASS' if res['gates']['G3_pass'] else 'FAIL'}")
    print(f"VERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
