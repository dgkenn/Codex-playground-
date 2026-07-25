#!/usr/bin/env python3
"""MECHANISM, with MEASURED cardiac output instead of a pulse-pressure surrogate.

`analysis/vitaldb_mechanism_decomposition.py` found the vasodilation pattern -- MAP falls, the SVR proxy falls,
pulse pressure is flat, heart rate does not fall -- but it could not quantify the split, for three stated reasons:
pulse pressure is a poor stroke-volume surrogate once vasopressors are titrated, MAP sits in the numerator of the
SVR proxy, and the four outcomes ran on different row sets.

This file removes the surrogacy. VitalDB carries EV1000/Vigileo continuous cardiac output and its derived systemic
vascular resistance for a subset of cases (/tmp/eeg_probe/mech_bins.csv: caseid, bin_t, mbp, ce, svr, co). With CO
and SVR MEASURED, the decomposition becomes direct:

        MAP = CO x SVR

  vasodilation / sympatholysis : SVR falls, CO preserved or rising (unloaded ventricle)
  cardiac depression           : CO falls, SVR preserved or rising (compensatory constriction)

Estimator is identical to the surrogate version so the two are comparable:
    outcome    signed change in the quantity from t to t+k (forward) and t to t-k (backward)
    model      outcome ~ exposure + MAP(t) + Ce(t) + dCe + pre-trend, CASE FIXED EFFECTS
    pre-trend  MAP(t-k) - MAP(t-2k), before the backward window, collinear with neither outcome
    inference  CASE-level cluster bootstrap; forward-minus-backward is the reported statistic
CO and SVR are analysed on the LOG scale: both are positive quantities whose meaningful changes are proportional,
and log makes the decomposition additive, so that  dlogMAP = dlogCO + dlogSVR  holds to first order and the two
columns can be read against the MAP column directly.

HONEST LIMITS:
  * This is a SUBCOHORT (~700 cases) chosen by clinicians who decided to place a cardiac-output monitor. Those are
    sicker, higher-risk operations. The estimate is internally valid (within-patient) but the subcohort is not
    representative, and the comparison with the full-cohort surrogate result is therefore not apples-to-apples.
  * EV1000/Vigileo CO is itself derived from the arterial waveform by a proprietary algorithm, not a thermodilution
    measurement. It is a far better stroke-volume index than pulse pressure but it is not a gold standard, and it
    shares the arterial line with the exposure-adjacent MAP.
  * Its SVR is computed as (MAP - CVP)/CO x 80, so it inherits MAP in its numerator exactly as the proxy did. The
    genuinely independent column here is CO. Read CO first; SVR is the arithmetic complement.

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
NBOOT = int(os.environ.get("NBOOT", "400"))
rng = np.random.default_rng(20260725)


def load():
    """(caseid, bin_t) -> [bs, MAP, Ce, CO, SVR]. BS comes from the EEG stream, haemodynamics from EV1000."""
    BS = {}
    seen = set()
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
    HD = defaultdict(dict)
    seen = set()
    with open(f"{DATA}/mech_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                bs = BS.get((cid, t))
                if bs is None:
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
                HD[cid][t] = [bs, m, ce, co, sv]
            except Exception:
                pass
    return HD


def value(rec, which):
    bs, m, ce, co, sv = rec
    if which == "map":
        return m
    if which == "logco":
        return float(np.log(co)) if (co == co and co > 0) else np.nan
    if which == "logsvr":
        return float(np.log(sv)) if (sv == sv and sv > 0) else np.nan
    return np.nan


def build(HD, k, which):
    cols = defaultdict(list)
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            rec = bd[t]
            bs, m, dose = rec[0], rec[1], rec[2]
            v0 = value(rec, which); vf = value(bd[tf], which); vb = value(bd[tb], which)
            mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (v0 == v0 and vf == vf and vb == vb):
                continue
            if not (m == m and mb == mb and mb2 == mb2 and mb3 == mb3 and dose == dose and doseb == doseb):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c])
            cols["e"].append(1.0 if bs > 0 else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)   # [t-3k, t-2k]: shares NO endpoint with db (see docstring)
            cols["df"].append(vf - v0); cols["db"].append(vb - v0)
    if not cols:
        return None
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32)
    D["ncase"] = len(ci)
    return D


def demean(mat, case, ncase, w):
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    out = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(case, weights=w * mat[:, j], minlength=ncase) / sw
        out[:, j] = mat[:, j] - mu[case]
    return out


def coef(D, dy, w):
    mat = np.column_stack([D["e"], D["m0"], D["dz"], D["dce"], D["pre"], dy])
    dm = demean(mat, D["case"], D["ncase"], w)
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return float(np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0])
    except np.linalg.LinAlgError:
        return None


def run(HD, k, which, unit, scale=1.0):
    D = build(HD, k, which)
    if D is None or len(D["case"]) < 3000:
        print(f"   {which:8s} insufficient ({0 if D is None else len(D['case'])} bins)")
        return
    order = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][order]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    w1 = np.ones(len(D["case"]))
    pf = coef(D, D["df"], w1); pb = coef(D, D["db"], w1)
    if pf is None or pb is None:
        print(f"   {which:8s} fit failed")
        return
    diffs = []; fwd = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(D, D["df"], w); b = coef(D, D["db"], w)
        if a is not None and b is not None:
            diffs.append((a - b) * scale); fwd.append(a * scale)
    if len(diffs) < 50:
        print(f"   {which:8s} bootstrap failed")
        return
    fl, fh = np.percentile(fwd, [2.5, 97.5])
    dl, dh = np.percentile(diffs, [2.5, 97.5])
    tag = "*" if (dl > 0 or dh < 0) else "ns"
    print(f"   {which:8s} fwd={pf*scale:+8.3f} [{fl:+7.3f},{fh:+7.3f}] {unit:9s} | "
          f"fwd-bwd={(pf-pb)*scale:+8.3f} [{dl:+7.3f},{dh:+7.3f}] {tag}   n={len(D['case'])}, cases={D['ncase']}")


def main():
    k = int(os.environ.get("K", "4"))
    HD = load()
    nb = sum(len(v) for v in HD.values())
    print(f"EV1000 subcohort joined to the EEG stream: {len(HD)} cases, {nb} bins")
    print(f"k=+/-{k} bins (+/-{30*k}s); case fixed effects + MAP(t) + Ce(t) + dCe + pre-trend; "
          f"{NBOOT} case-level bootstrap reps")
    print("exposure = ANY burst suppression in the bin vs none; statistic = forward minus backward\n")
    run(HD, k, "map", "mmHg")
    run(HD, k, "logco", "% (x100)", scale=100.0)
    run(HD, k, "logsvr", "% (x100)", scale=100.0)
    print("\n  MAP = CO x SVR, so on the log scale the CO and SVR columns should roughly sum to the MAP column")
    print("  (MAP is in mmHg here, ~1.3% per mmHg at a typical MAP of 80).")
    print("  vasodilation -> SVR falls, CO preserved/rising.   cardiac depression -> CO falls, SVR flat/rising.")
    print("  CO is the independently informative column; this SVR is computed FROM MAP and inherits it.")


if __name__ == "__main__":
    sys.exit(main())
