"""E99 -- Challenge C: does the aperiodic exponent add to BIS for detecting BURST SUPPRESSION?

REGISTERED BEFORE ANY MODEL IS FIT. Feasibility probed first (rule 41), touching only the label: 5,798
VitalDB windows carry a suppression ratio, a BIS and an exponent; **977 (16.9 %) have `meta_sr` > 0,
spread over 140 of 247 cases.** No feature has been related to it.

=========================================================================================================
WHY THIS ENDPOINT
=========================================================================================================
E89 tried to ask a Challenge C increment question on VitalDB against a device-measured suppression endpoint and
gate-failed: BIS is missing in 70 % of peri-emergence windows, so requiring it conditioned on the incumbent
still reporting. **`meta_sr` does not have that problem** -- it is present in 5,798 of 6,679 windows -- and
it is a device-computed measure of EEG AMPLITUDE SUPPRESSION rather than a proprietary depth index.

It is also the thing anaesthesia monitoring most wants to avoid: excessive suppression is the failure mode
on the deep side, and E90 established that on this deposit the self-computed exponent exists in periods
where the vendor's index does not.

**THE INCUMBENT IS STRONG HERE BY CONSTRUCTION AND THAT IS DELIBERATE.** BIS incorporates a
burst-suppression subparameter, so BIS is partly computed FROM suppression. Asking whether anything adds
to it at predicting suppression is therefore a hard test, not a soft one, and a positive would be
meaningful. G1 reports the baseline out-of-bag AUC; if it is very high the headroom is small and the
result must be read in that light, which is stated here rather than discovered afterwards.

=========================================================================================================
DESIGN -- identical machinery to E89, one endpoint changed
=========================================================================================================
    LABEL      `meta_sr` > 0. A structural definition needing no threshold (rule 63): any suppression at
               all, as the device scores it.
    BASELINE   BIS alone, the named incumbent (rule 45).
    TEST       BIS + `whole_head_exponent`.
    P          Out-of-bag AUC increment, clustered on CASE (rule 9): each replicate fits both models on
               the drawn cases' rows and scores both on the rows of cases NOT drawn. 400 replicates.

    **THE PRIMARY IS UNRESTRICTED** (rule 49): restricting to a BIS band would select rows on the
    incumbent that is in the model, which is the defect that let six of six candidates pass in E46. The
    artefact-band restriction is a declared secondary arm.

ARMS: A1 primary, all windows with finite BIS, SR and exponent. A2 artefact, BIS < 60 and SQI >= 50 --
secondary, because it selects on the incumbent. A3 muscle, baseline becomes BIS + `meta_emg`, the
MONITOR'S OWN EMG channel rather than a scalp proxy (E69/E71 measured this project's proxy at rho +0.20
against a real submental channel). A4 negative, a Gaussian in place of the exponent; must not add.

VERDICT, wrong direction FIRST (rule 37): (a) interval excludes 0 and NEGATIVE -> HURTS, the exponent is
noise the model spends capacity on, and that is not a null. (b) includes 0 -> NO INCREMENT. (c) excludes 0
and POSITIVE -> ADDS, subject to A3 and A4.

GATES: G1 the incumbent must be alive -- BIS alone above chance out of bag, else "the exponent adds to
BIS" is a statement about the label (the E61 trap). G2 >= 100 cases and >= 300 positive windows. G3 the
Gaussian control must not ADD.

SCOPE. One retrospective deposit, a device-derived label, single-channel EEG. This asks whether a
self-computed exponent carries information about amplitude suppression beyond a commercial index. It is
not a claim about consciousness, not a claim about awareness, and not evidence that anything should be
displayed to a clinician.

    python -m bsde.experiments.e99_vitaldb_suppression_increment
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
OUT = os.path.join(RESULTS, "e99_vitaldb_suppression_increment.json")

FEATURE = "whole_head_exponent"
SR_KEY = "meta_sr"
BIS_MAX, SQI_MIN = 60.0, 50.0
MIN_CASES, MIN_POSITIVE = 100, 300
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
    res = {"gates": {}, "arms": {}, "label": {"definition": "meta_sr > 0 (any device-detected suppression)"}}

    def build(mask_fn, extra_baseline=()):
        y, subj, base, feat = [], [], [], []
        for r in rows:
            bis, sqi = _f(r["meta_bis"]), _f(r["meta_sqi"])
            e, x = _f(r[SR_KEY]), _f(r.get(FEATURE, ""))
            ex = [_f(r.get(k, "")) for k in extra_baseline]
            if not (np.isfinite(bis) and np.isfinite(e) and np.isfinite(x)) or not all(np.isfinite(ex)):
                continue
            if not mask_fn(bis, sqi):
                continue
            y.append(1 if e > 0.0 else 0)
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
    print(f"G1 incumbent  BIS alone, out-of-bag AUC for suppression = {g1:.4f}   "
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
        # THE INTERCEPT WAS MISSING AND IT REVERSED THE SIGN. `oob_auc_increment` fits an IRLS logistic
        # with no intercept of its own; the first version passed [BIS] and [BIS, exponent] bare, so both
        # models were fitted through the origin and the increment printed -0.0320 [-0.0544, -0.0111],
        # i.e. HURTS. With the intercept the same call gives +0.0168 [+0.0049, +0.0269]. `stats.py` now
        # RAISES on a design whose first column is not a constant, so this cannot recur silently.
        one = np.ones(XA.shape[0])
        XA = np.column_stack([one, XA])
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
                       "a device-measured suppression endpoint, no claim about consciousness or awareness.")
    res["verdict"] = verdict
    print(f"\nG3 negative control  {'PASS' if res['gates']['G3_pass'] else 'FAIL'}")
    print(f"VERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
