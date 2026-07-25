#!/usr/bin/env python3
"""ONSET vs SUSTAINED suppression — testing whether the signal is the STATE or the TRANSITION.

WHERE THIS HYPOTHESIS CAME FROM (stated plainly, because it matters for how the result should be weighted).
It was generated POST HOC, from the pattern of this project's own failures. Three registered directional
predictions failed, all in the same direction, and they line up with two other results:

    lead LARGE : young patients, low propofol Ce, low remifentanil, dose actively changing
    lead SMALL : elderly, high Ce, high opioid, perfectly stable infusion (-0.83 -> -0.31)
    lead ABSENT (symmetric): sevoflurane, where slow gas kinetics produce few sharp transients

Those are the same condition described five ways. In a young patient at low dose, burst suppression is UNUSUAL --
it occurs when something transient pushes the cortex past threshold. In an elderly patient at high dose it is the
steady state. So the predictive information may lie not in the suppression STATE but in the TRANSITION INTO it.

That reading also fits the haemodynamics already measured: a transient deepening produces a transient withdrawal of
sympathetic outflow, hence vasodilation (SVR falls, cardiac output rises, pulse pressure flat) over the following
60-120 s. A sustained suppressed state has no such transition and should carry no forward information.

THE DECISIVE TEST. Classify each maintenance bin by its own recent history:
    reference : no suppression in bin t
    ONSET     : suppression in bin t, and NONE in bin t-1        (the transition)
    SUSTAINED : suppression in bin t, and ALSO in bin t-1        (the state)
Prediction, registered before running: the forward pressure fall is carried by ONSET bins. SUSTAINED bins should
show substantially less, and possibly none.

INTERPRETING THE BACKWARD COLUMN. It is NOT symmetric between the two categories and must not be read as if it
were: a SUSTAINED bin is by construction preceded by suppression, so its backward window sits inside an ongoing
episode, whereas an ONSET bin's backward window sits in non-suppressed EEG. The forward-minus-backward contrast is
therefore reported for completeness but the FORWARD coefficients are the comparison that answers the question,
since both categories are measured against the same non-suppressed reference within the same patient.

A SECOND, INDEPENDENT ANGLE. If the signal is about suppression being unusual FOR THIS PATIENT, then the lead
should be larger in patients whose overall suppression burden is LOW (where any suppression is a deviation) and
smaller in patients who are suppressed most of the time (where it is their normal state). Tested here by splitting
cases on their own total suppression burden.

STATUS: this is a within-sample consistency test of a post-hoc hypothesis. It CANNOT confirm the hypothesis on its
own -- the same data generated it. The genuine out-of-sample tests are the expanded sevoflurane cohort (does the
lead reappear when restricted to ONSET bins, rescuing what is currently an unexplained null?) and I-CARE.

Estimator unchanged: within-case fixed effects, MAP(t) + dose + dCe + pre-trend over [t-2k, t-k], bins holding both
a forward and a backward neighbour, case-level cluster bootstrap.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)


def load(cohort):
    HD = defaultdict(dict); seen = set()
    fn = "bridge_bins.csv" if cohort == "prop" else "sevo_bins.csv"
    with open(f"{DATA}/{fn}") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]),
                              float(d["mbp"]) if d["mbp"] else np.nan,
                              float(d["ce"]) if d["ce"] else np.nan]
            except Exception:
                pass
    return HD


def build(HD, k):
    cols = defaultdict(list); ci = {}
    burden = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        b = [bd[t][0] for t in ts]
        burden[c] = float(np.mean([1.0 if x > 0 else 0.0 for x in b]))
    for c, bd in HD.items():
        if c not in burden:
            continue
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            tprev = t - 30.0
            if tf not in bd or tb not in bd or tb2 not in bd or tprev not in bd:
                continue
            bs, m, dose = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; doseb = bd[tb][2]
            prev_bs = bd[tprev][0]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and dose == dose and doseb == doseb):
                continue
            if prev_bs != prev_bs:
                continue
            if c not in ci:
                ci[c] = len(ci)
            onset = 1.0 if (bs > 0 and prev_bs == 0) else 0.0
            sustained = 1.0 if (bs > 0 and prev_bs > 0) else 0.0
            cols["case"].append(ci[c]); cols["onset"].append(onset); cols["sust"].append(sustained)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb - mb2)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["burden"].append(burden[c])
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit2(sub, dy, w, ncase):
    """Returns the ONSET and SUSTAINED coefficients, both vs the non-suppressed reference."""
    mat = np.column_stack([sub["onset"], sub["sust"], sub["m0"], sub["dz"], sub["dce"], sub["pre"], dy])
    sw = np.bincount(sub["case"], weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(sub["case"], weights=w * mat[:, j], minlength=ncase) / sw
        dm[:, j] = mat[:, j] - mu[sub["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        b = np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)
    except np.linalg.LinAlgError:
        return None
    return b[0], b[1]


def report(D, mask, title):
    n = int(mask.sum())
    if n < 5000:
        print(f"\n=== {title} === insufficient ({n} bins)")
        return
    sub = {kk: D[kk][mask] for kk in ("case", "onset", "sust", "m0", "dz", "dce", "pre", "df", "db")}
    o = np.argsort(sub["case"], kind="stable")
    sub = {kk: v[o] for kk, v in sub.items()}
    starts = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    w1 = np.ones(n)
    f = fit2(sub, sub["df"], w1, D["ncase"]); b = fit2(sub, sub["db"], w1, D["ncase"])
    if f is None or b is None:
        print(f"\n=== {title} === fit failed")
        return
    bo_f, bs_f, bo_d, bs_d, bdiff = [], [], [], [], []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        ff = fit2(sub, sub["df"], w, D["ncase"]); bb = fit2(sub, sub["db"], w, D["ncase"])
        if ff is None or bb is None:
            continue
        bo_f.append(ff[0]); bs_f.append(ff[1])
        bo_d.append(ff[0] - bb[0]); bs_d.append(ff[1] - bb[1])
        bdiff.append(ff[0] - ff[1])
    if len(bdiff) < 50:
        print(f"\n=== {title} === bootstrap failed")
        return
    print(f"\n=== {title} ===")
    print(f"   bins={n}  onset bins={int(sub['onset'].sum())}  sustained bins={int(sub['sust'].sum())}")
    for nm, pt, bs_ in (("ONSET     forward", f[0], bo_f), ("SUSTAINED forward", f[1], bs_f)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:20s} {pt:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(bdiff, [2.5, 97.5])
    d = f[0] - f[1]
    verdict = ("TRANSITION carries it" if hi < 0 else
               ("STATE carries it" if lo > 0 else "indistinguishable"))
    print(f"   {'ONSET - SUSTAINED':20s} {d:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}]   {verdict}")
    for nm, pt, bs_ in (("ONSET     fwd-bwd", f[0] - b[0], bo_d), ("SUSTAINED fwd-bwd", f[1] - b[1], bs_d)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:20s} {pt:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] {'*' if (lo>0 or hi<0) else 'ns'}"
              f"   [asymmetric by construction -- see docstring]")


def main():
    cohort = os.environ.get("COHORT", "prop")
    k = int(os.environ.get("K", "4"))
    D = build(load(cohort), k)
    print(f"cohort={cohort}  k=+/-{k} bins (+/-{30*k}s);  {len(D['case'])} bins, {D['ncase']} cases; "
          f"{NBOOT} case-level bootstrap reps")
    print("both categories are measured against the SAME non-suppressed reference within each patient")
    report(D, np.ones(len(D["case"]), bool), "ALL BINS -- is the signal the transition or the state?")
    bu = D["burden"]
    cut = np.percentile(bu, [33, 67])
    report(D, bu < cut[0], f"LOW suppression-burden cases (< {cut[0]:.2f}) -- suppression is unusual for them")
    report(D, bu >= cut[1], f"HIGH suppression-burden cases (>= {cut[1]:.2f}) -- suppression is their normal state")


if __name__ == "__main__":
    sys.exit(main())
