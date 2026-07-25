#!/usr/bin/env python3
"""Does the DURATION-RESPONSE run through the VASODILATION mechanism?

Two findings currently stand independently of one another:

  (1) MECHANISM. The pressure fall after burst suppression occurs by vasodilation, not pump failure: with MEASURED
      EV1000 cardiac output, MAP falls (-0.26 mmHg), SVR falls (-0.34 %) and cardiac output RISES (+0.27 %). A
      cardiac cause requires CO to fall; it does not.

  (2) DOSE-RESPONSE. The size of the fall scales monotonically with cumulative time spent suppressed, in both
      cohorts and on two independent measures (propofol occupancy gradient -1.838 mmHg [-2.315, -1.416];
      sevoflurane -1.725 [-2.676, -0.785]).

They have not been joined. If the vasodilation account is right, (2) must run THROUGH (1): the longer the recent
occupancy of the suppressed state, the more the systemic vascular resistance should fall — a graded vasodilator
response, not merely a graded pressure fall. That is a specific, falsifiable coupling between the two results.

PREDICTIONS, registered before running:
  A. log(SVR) falls monotonically with recent suppression occupancy.
  B. log(CO) does NOT fall monotonically with occupancy. If CO fell progressively with dwell time, the mechanism
     would be progressive myocardial depression instead, and prediction (1) above would be wrong.
  C. The MAP gradient in this subcohort should track the SVR gradient rather than the CO gradient.

FALSIFICATION: if SVR shows no gradient while MAP does, then dwell time is lowering pressure by some route other
than resistance, and the vasodilation mechanism does not explain the dose-response. If CO falls monotonically, the
mechanism is cardiac after all and the earlier conclusion was wrong.

Exposure is cumulative occupancy (suppressed bins in the preceding 5 minutes, i.e. 10 bins), which behaved better
than run length: run length plateaued in propofol above 4 minutes, whereas occupancy was cleanly monotonic in both
cohorts. It is coded as bands against a no-recent-suppression reference so the shape is estimated, not imposed.

Estimator unchanged: within-case fixed effects, MAP(t) + Ce(t) + dCe + pre-trend over [t-2k, t-k], bins holding
both a forward and a backward neighbour, case-level cluster bootstrap.

LIMITS CARRIED FORWARD. The EV1000 subcohort is ~700 cases selected by clinicians who chose to place a cardiac-
output monitor, so it is sicker and not representative. Vigileo CO is waveform-derived, not thermodilution. Its SVR
is computed as (MAP - CVP)/CO x 80 and therefore carries MAP in its numerator, so CO is the independently
informative column and SVR is partly arithmetic — which is exactly why prediction B, about CO, is the one that can
actually falsify the mechanism.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)
BANDS = [(1, 2, "1-2 of last 10"), (3, 4, "3-4 of last 10"), (5, 7, "5-7 of last 10"), (8, 10, "8-10 of last 10")]


def load():
    BS = {}; seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                BS[(cid, t)] = float(d["bs"])
            except Exception:
                pass
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/mech_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                b = BS.get((cid, t))
                if b is None:
                    continue
                m = float(d["mbp"]) if d["mbp"] else np.nan
                ce = float(d["ce"]) if d["ce"] else np.nan
                co = float(d["co"]) if d["co"] else np.nan
                sv = float(d["svr"]) if d["svr"] else np.nan
                if not (m == m and 20 < m < 160):
                    m = np.nan
                if not (co == co and 0.5 < co < 15):
                    co = np.nan
                if not (sv == sv and 100 < sv < 5000):
                    sv = np.nan
                HD[cid][t] = [b, m, ce, co, sv]
            except Exception:
                pass
    return HD


def value(rec, which):
    b, m, ce, co, sv = rec
    if which == "map":
        return m
    if which == "logco":
        return float(np.log(co)) if (co == co and co > 0) else np.nan
    if which == "logsvr":
        return float(np.log(sv)) if (sv == sv and sv > 0) else np.nan
    return np.nan


def build(HD, k, which):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        occ = {}
        for i, t in enumerate(ts):
            w = ts[max(0, i - 9):i + 1]
            occ[t] = float(sum(1.0 for x in w if bd[x][0] == bd[x][0] and bd[x][0] > 0))
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd:
                continue
            rec = bd[t]
            m = rec[1]; dose = rec[2]
            v0 = value(rec, which); vf = value(bd[tf], which); vb = value(bd[tb], which)
            mb = bd[tb][1]; mb2 = bd[tb2][1]; doseb = bd[tb][2]
            if not (v0 == v0 and vf == vf and vb == vb):
                continue
            if not (m == m and mb == mb and mb2 == mb2 and dose == dose and doseb == doseb):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["occ"].append(occ[t])
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb - mb2)
            cols["df"].append(vf - v0); cols["db"].append(vb - v0)
    if not cols:
        return None
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(D, expo, dy, w):
    mat = np.column_stack(expo + [D["m0"], D["dz"], D["dce"], D["pre"], dy])
    sw = np.bincount(D["case"], weights=w, minlength=D["ncase"])
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(D["case"], weights=w * mat[:, j], minlength=D["ncase"]) / sw
        dm[:, j] = mat[:, j] - mu[D["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        b = np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)
    except np.linalg.LinAlgError:
        return None
    return b[:len(expo)]


def run(HD, k, which, unit, scale=1.0):
    D = build(HD, k, which)
    if D is None or len(D["case"]) < 8000:
        print(f"\n=== {which} === insufficient")
        return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    expo = [((D["occ"] >= lo) & (D["occ"] <= hi)).astype(float) for lo, hi, _ in BANDS]
    labels = [nm for _, _, nm in BANDS]
    counts = [int(e.sum()) for e in expo]
    keep = [i for i, c in enumerate(counts) if c >= 1200]
    if len(keep) < 2:
        print(f"\n=== {which} === too few exposed bins per band")
        return
    expo = [expo[i] for i in keep]; labels = [labels[i] for i in keep]; counts = [counts[i] for i in keep]
    w1 = np.ones(len(D["case"]))
    pf = fit(D, expo, D["df"], w1)
    if pf is None:
        print(f"\n=== {which} === fit failed")
        return
    boots = [[] for _ in expo]; grad = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        f = fit(D, expo, D["df"], w)
        if f is None:
            continue
        for j in range(len(expo)):
            boots[j].append(f[j] * scale)
        grad.append((f[-1] - f[0]) * scale)
    if len(grad) < 50:
        print(f"\n=== {which} === bootstrap failed")
        return
    print(f"\n=== {which}  ({unit}) ===   n={len(D['case'])}, cases={D['ncase']}")
    for j, nm in enumerate(labels):
        lo, hi = np.percentile(boots[j], [2.5, 97.5])
        print(f"   {nm:18s} forward = {pf[j]*scale:+8.3f} [{lo:+8.3f},{hi:+8.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}   bins={counts[j]}")
    lo, hi = np.percentile(grad, [2.5, 97.5])
    d = (pf[-1] - pf[0]) * scale
    verdict = "GRADIENT (falls more with occupancy)" if hi < 0 else ("REVERSED" if lo > 0 else "no gradient")
    print(f"   {'gradient (top-bottom)':18s}         {d:+8.3f} [{lo:+8.3f},{hi:+8.3f}]   {verdict}")


def main():
    k = int(os.environ.get("K", "4"))
    HD = load()
    print(f"EV1000 subcohort joined to the EEG stream: {len(HD)} cases")
    print(f"k=+/-{k} bins; exposure = suppressed bins in the preceding 5 minutes; {NBOOT} bootstrap reps")
    print("PREDICTED: SVR falls monotonically with occupancy; CO does NOT; MAP tracks SVR\n")
    run(HD, k, "map", "mmHg")
    run(HD, k, "logsvr", "% (x100)", scale=100.0)
    run(HD, k, "logco", "% (x100)", scale=100.0)
    print("\n  A monotonic CO decline would mean progressive myocardial depression and would overturn the")
    print("  vasodilation conclusion. A MAP gradient with no SVR gradient would mean dwell time lowers pressure")
    print("  by some route other than resistance.")


if __name__ == "__main__":
    sys.exit(main())
