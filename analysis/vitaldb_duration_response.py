#!/usr/bin/env python3
"""DURATION-RESPONSE: does the pressure fall scale with DWELL TIME in the suppressed state?

WHERE THIS COMES FROM. Two mechanistic accounts have now been falsified by their own registered tests:
  * "more sympatholytic burden -> bigger effect" failed P1 (age) and P2 (depth), both significantly and in the
    opposite direction;
  * "the transition into suppression carries the signal" was refuted in BOTH cohorts -- sustained suppression
    produces a LARGER fall than onset (propofol +0.94 mmHg difference, sevoflurane +0.64, both excluding zero).

What survived, and what this file tests, is the pattern in the burden-stratified result: among patients who are
RARELY suppressed, a SUSTAINED run is followed by a -4.10 mmHg fall, four times the pooled effect and four times
what the same thing produces in patients suppressed most of the time (-1.00). That single moderator plausibly
subsumes all three failed predictions, because young / low-Ce / low-opioid patients are precisely the low-burden
patients -- age, dose and opioid may all have been crude proxies for how unusual sustained suppression is for that
particular brain.

THE PREDICTION, registered before running. If dwell time in the suppressed state drives the haemodynamic
consequence, the fall must increase MONOTONICALLY with the length of the suppression run so far. A flat gradient,
or a non-monotonic one, kills this account the way the previous two died.

    exposure   run length = number of CONSECUTIVE bins up to and including t with any suppression.
               Uses only the PAST, so it is causally clean -- no peeking at how long the episode will last.
               Coded as dummies (1, 2, 3-4, 5-8, 9+ bins) against the non-suppressed reference, so the shape is
               estimated rather than assumed. A linear term would impose the monotonicity we are trying to test.
    outcome    signed change in MAP from t to t+k (forward) and t to t-k (backward)
    model      outcome ~ run-length dummies + MAP(t) + dose + dCe + pre-trend, CASE FIXED EFFECTS
    inference  CASE-level cluster bootstrap; the monotonicity of the forward coefficients is the test

CONFOUND, stated up front and partly addressed. Longer runs occur at deeper anaesthesia, so a duration-response
could be a dose-response in disguise. Three things bear on this: dose and its rate of change are adjusted in every
model; the effect is LARGER in low-burden patients, whose runs are SHORTER, which is the opposite of what a pure
dose explanation predicts; and the analysis is repeated within Ce tertiles below, so the gradient must appear at
FIXED depth to count. If the gradient exists only in the high-Ce stratum it is dose, not dwell time.

A SECOND, INDEPENDENT ANGLE. If dwell time matters, then what should predict the fall is CUMULATIVE suppression in
the recent window, not the instantaneous state. Tested by replacing the run-length dummies with the number of
suppressed bins in the preceding 10 bins (5 minutes), which is a smoother measure of recent occupancy.

HONEST STATUS: the burden-stratified pattern that motivated this came from these same data, so a positive result
here is internal consistency, not confirmation. The out-of-sample tests are the expanded sevoflurane cohort (now
943 cases, 3.4x its earlier size) and I-CARE. Both are run or planned separately.

PRE-TREND WINDOW -- CORRECTED after adversarial review, and this changed a reported number.
The pre-trend was previously MAP(t-k) - MAP(t-2k). That is not exactly collinear with the backward outcome
MAP(t-k) - MAP(t), but it SHARES THE ENDPOINT MAP(t-k) with it. Measured on the real within-case demeaned data the
partial correlation was 0.528 against the backward outcome and 0.023 against the forward one. The consequence was
one-sided: adding it shrank the BACKWARD coefficient from -0.412 to -0.202 while leaving the FORWARD coefficient
untouched at -1.278, inflating the forward-minus-backward statistic from -0.870 to -1.076, i.e. by about 24 %,
entirely through the backward side. The pre-trend is now measured over [t-3k, t-2k], which shares NO endpoint with
either outcome (raw correlation with the backward outcome falls from 0.389 to 0.035). Roughly half of the apparent
benefit of pre-trend adjustment was this artefact; the corrected asymmetry is near -0.97 rather than -1.08. The
forward coefficient is unaffected by any of this.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)

# --- physiologic range filter for arterial pressure -------------------------------------------------
# The propofol pipeline never range-filtered MAP. bridge_bins.csv contains 4.27 % of values <= 0
# (minimum -78 mmHg -- negative arterial pressure is impossible) and 0.62 % above 200 mmHg: transducer
# zeroing, line flushes and disconnections. Left unfiltered they produced dMAP values up to +/-390 mmHg
# and inflated every forward-minus-backward statistic about three-fold (-0.33 -> -0.97 mmHg). Filtering
# implausible VALUES is the principled fix; winsorising the outcome would only mask them.
# The filtered estimate is stable across windows [30,150], [25,160], [20,180] and [40,140]
# (asymmetry -0.340, -0.330, -0.323, -0.333), so the exact threshold is not doing the work.
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    """Parse a MAP field, returning NaN unless it lies in the physiologic window."""
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


BANDS = [(1, 1, "run 1 bin  (30s)"), (2, 2, "run 2 bins (60s)"), (3, 4, "run 3-4  (90-120s)"),
         (5, 8, "run 5-8  (2.5-4min)"), (9, 10**9, "run 9+   (>4min)")]


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
                              _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan]
            except Exception:
                pass
    return HD


def build(HD, k):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        # run length using only the past, over the maintenance sequence
        run = {}
        prev = 0
        for t in ts:
            b = bd[t][0]
            prev = (prev + 1) if (b == b and b > 0) else 0
            run[t] = prev
        # cumulative occupancy over the preceding 10 bins
        occ = {}
        for i, t in enumerate(ts):
            w = ts[max(0, i - 9):i + 1]
            v = [1.0 if (bd[x][0] == bd[x][0] and bd[x][0] > 0) else 0.0 for x in w]
            occ[t] = float(np.sum(v))
        burden = float(np.mean([1.0 if (bd[t][0] == bd[t][0] and bd[t][0] > 0) else 0.0 for t in ts]))
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3 and dose == dose and doseb == doseb):
                continue
            if bs != bs:
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["run"].append(run[t]); cols["occ"].append(occ[t])
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)   # [t-3k, t-2k]: shares NO endpoint with db (see docstring)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["burden"].append(burden)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(sub, expo, dy, w, ncase):
    mat = np.column_stack(expo + [sub["m0"], sub["dz"], sub["dce"], sub["pre"], dy])
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
    return b[:len(expo)]


def report(D, mask, title, mode="run"):
    n = int(mask.sum())
    if n < 8000:
        print(f"\n=== {title} === insufficient ({n} bins)")
        return
    keys = ("case", "run", "occ", "m0", "dz", "dce", "pre", "df", "db")
    sub = {kk: D[kk][mask] for kk in keys}
    o = np.argsort(sub["case"], kind="stable")
    sub = {kk: v[o] for kk, v in sub.items()}
    starts = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    if mode == "run":
        expo = [((sub["run"] >= lo) & (sub["run"] <= hi)).astype(float) for lo, hi, _ in BANDS]
        labels = [nm for _, _, nm in BANDS]
        counts = [int(e.sum()) for e in expo]
    else:
        expo = [((sub["occ"] >= lo) & (sub["occ"] <= hi)).astype(float)
                for lo, hi in ((1, 2), (3, 4), (5, 7), (8, 10))]
        labels = ["1-2 of last 10", "3-4 of last 10", "5-7 of last 10", "8-10 of last 10"]
        counts = [int(e.sum()) for e in expo]
    keep = [i for i, cnt in enumerate(counts) if cnt >= 1500]
    if len(keep) < 2:
        print(f"\n=== {title} === too few exposed bins per band")
        return
    expo = [expo[i] for i in keep]; labels = [labels[i] for i in keep]; counts = [counts[i] for i in keep]
    w1 = np.ones(n)
    pf = fit(sub, expo, sub["df"], w1, D["ncase"])
    if pf is None:
        print(f"\n=== {title} === fit failed")
        return
    boots = [[] for _ in expo]
    mono = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        f = fit(sub, expo, sub["df"], w, D["ncase"])
        if f is None:
            continue
        for j in range(len(expo)):
            boots[j].append(f[j])
        mono.append(f[-1] - f[0])
    if len(mono) < 50:
        print(f"\n=== {title} === bootstrap failed")
        return
    print(f"\n=== {title} ===   n={n}")
    for j, nm in enumerate(labels):
        lo, hi = np.percentile(boots[j], [2.5, 97.5])
        print(f"   {nm:22s} forward = {pf[j]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}   bins={counts[j]}")
    lo, hi = np.percentile(mono, [2.5, 97.5])
    d = pf[-1] - pf[0]
    verdict = ("MONOTONIC -- longest band falls more" if hi < 0 else
               ("REVERSED" if lo > 0 else "NO GRADIENT"))
    print(f"   {'longest MINUS shortest':22s}         {d:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}]   {verdict}")


def main():
    cohort = os.environ.get("COHORT", "prop")
    k = int(os.environ.get("K", "4"))
    D = build(load(cohort), k)
    print(f"cohort={cohort}  k=+/-{k} bins (+/-{30*k}s);  {len(D['case'])} bins, {D['ncase']} cases; "
          f"{NBOOT} case-level bootstrap reps")
    print("reference category = bins with NO suppression; run length uses only the past")
    allb = np.ones(len(D["case"]), bool)
    report(D, allb, "DURATION-RESPONSE: forward dMAP by length of the suppression run so far")
    report(D, allb, "OCCUPANCY: forward dMAP by suppressed bins in the preceding 5 minutes", mode="occ")
    ce = D["dz"]
    cut = np.percentile(ce, [33, 67])
    report(D, ce < cut[0], f"duration-response WITHIN low Ce (< {cut[0]:.2f}) -- must survive at fixed depth")
    report(D, ce >= cut[1], f"duration-response WITHIN high Ce (>= {cut[1]:.2f})")
    bu = D["burden"]
    bcut = np.percentile(bu, [33, 67])
    report(D, bu < bcut[0], f"duration-response in LOW-burden cases (< {bcut[0]:.2f})")
    report(D, bu >= bcut[1], f"duration-response in HIGH-burden cases (>= {bcut[1]:.2f})")


if __name__ == "__main__":
    sys.exit(main())
