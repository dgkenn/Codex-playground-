#!/usr/bin/env python3
"""WITHIN-CASE change in arterial pressure after burst suppression -- the higher-powered version of the
self-controlled test.

Why this exists. The self-controlled Mantel-Haenszel analysis dichotomises the outcome at MAP < 65 mmHg and then
matches within (case x pressure band x dose band). Dichotomising throws away most of the information, and the fine
matching leaves only ~1,000 informative strata, so a null there is an UNDERPOWERED null and must not be read as a
refutation. This script asks the identical causal question with a continuous outcome and a within-case estimator,
which is far more efficient:

    outcome   dMAP = MAP(t + k) - MAP(t)          (millimetres of mercury; signed, so a fall is negative)
    exposure  the suppressed fraction of bin t, and separately the binary any-vs-none contrast
    model     dMAP ~ BS(t) + MAP(t) + dose(t) + CASE FIXED EFFECTS
              Case fixed effects are absorbed by within-case demeaning (the Frisch-Waugh-Lovell transform), so
              every patient is compared only against themselves. All time-invariant patient characteristics --
              age, comorbidity, frailty, surgery type, baseline vascular tone, anything unmeasured -- are
              differenced out exactly, not modelled.
    inference CASE-level cluster bootstrap. Bins within a case are strongly autocorrelated; the effective sample
              size is the ~1,700 cases, not the ~600,000 bins.

    controls  (i) BACKWARD lag: dMAP_back = MAP(t - k) - MAP(t). If suppression heralds a pressure fall, the
                  forward coefficient must be more negative than the backward one. A shared contemporaneous state
                  is symmetric in time. The forward-minus-backward difference is reported with its own bootstrap
                  interval, computed from the SAME resampled cases so the two are properly correlated.
             (ii) frontal EMG through the identical pipeline as a negative-control exposure.

Interpretation rule fixed in advance: "burst suppression precedes a pressure fall" requires the forward-minus-
backward difference in dMAP to be negative with an interval excluding zero. Anything else is coupling without
demonstrated precedence.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
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
                              float(d["ce"]) if d["ce"] else np.nan,
                              np.nan]
            except Exception:
                pass
    if cohort == "prop":
        seen = set()
        with open(f"{DATA}/bis_bins.csv") as fh:
            for d in csv.DictReader(fh):
                try:
                    cid = d["caseid"]; t = float(d["bin_t"])
                    if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                        continue
                    seen.add((cid, t))
                    HD[cid][t][3] = float(d["emg"]) if d["emg"] else np.nan
                except Exception:
                    pass
    return HD


def build(HD, k, exposure, emg_cut):
    """Rows where BOTH MAP(t+k) and MAP(t-k) exist, so forward and backward use the IDENTICAL bin set.

    This matters: if the forward analysis used bins that have a successor and the backward analysis used bins that
    have a predecessor, the two would run on different parts of each case (forward drops the tail, backward drops
    the head) and any asymmetry could come from that alone rather than from physiology.
    """
    case = []; e = []; m0 = []; dz = []; df = []; db = []
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k
            if tf not in bd or tb not in bd:
                continue
            bs, m, dose, emg = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]
            if m != m or mf != mf or mb != mb or dose != dose:
                continue
            if exposure == "bs":
                x = bs
            elif exposure == "bsbin":
                x = 1.0 if bs > 0 else 0.0
            else:
                if emg != emg or emg_cut is None:
                    continue
                x = 1.0 if emg > emg_cut else 0.0
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c]); e.append(x); m0.append(m); dz.append(dose)
            df.append(mf - m); db.append(mb - m)
    return (np.array(case, np.int32), np.array(e), np.array(m0), np.array(dz),
            np.array(df), np.array(db), len(ci))


def demean(cols, case, ncase, w):
    """Weighted within-case demeaning (absorbs case fixed effects) for frequency weights w."""
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    out = []
    for v in cols:
        mu = np.bincount(case, weights=w * v, minlength=ncase) / sw
        out.append(v - mu[case])
    return out


def wls(X, y, w):
    A = (X.T * w) @ X
    try:
        return np.linalg.solve(A + 1e-8 * np.eye(X.shape[1]), (X.T * w) @ y)
    except np.linalg.LinAlgError:
        return None


def fit(case, e, m0, dz, dy, ncase, w):
    """Coefficient on the exposure in  dy ~ e + m0 + dose  with case fixed effects."""
    ed, md, dd, yd = demean([e, m0, dz, dy], case, ncase, w)
    X = np.column_stack([ed, md, dd])
    b = wls(X, yd, w)
    return None if b is None else b[0]


def analyse(HD, exposure, label, k, emg_cut):
    case, e, m0, dz, df, db, ncase = build(HD, k, exposure, emg_cut)
    if len(case) < 5000:
        print(f"\n{label}: insufficient rows ({len(case)})")
        return
    order = np.argsort(case, kind="stable")
    case, e, m0, dz, df, db = (a[order] for a in (case, e, m0, dz, df, db))
    starts = np.searchsorted(case, np.arange(ncase), side="left")
    ends = np.searchsorted(case, np.arange(ncase), side="right")
    span = ends - starts
    w1 = np.ones(len(case))

    pf = fit(case, e, m0, dz, df, ncase, w1)
    pb = fit(case, e, m0, dz, db, ncase, w1)
    fb = []; bb = []; ab = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, ncase, ncase), minlength=ncase).astype(np.float64)
        w = np.repeat(cnt, span)
        a = fit(case, e, m0, dz, df, ncase, w)
        b = fit(case, e, m0, dz, db, ncase, w)
        if a is not None and b is not None:
            fb.append(a); bb.append(b); ab.append(a - b)
    if len(fb) < 50:
        print(f"\n{label}: bootstrap failed")
        return
    unit = "per full suppression" if exposure == "bs" else "for exposed vs not"
    print(f"\n{label}   [k=+/-{k} bins = +/-{30*k}s;  {len(case)} bins, {ncase} cases, {unit}]")
    for nm, pt, bs_ in (("forward   dMAP(t+k)-MAP(t)", pf, fb), ("backward  dMAP(t-k)-MAP(t)", pb, bb)):
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"   {nm:28s} {pt:+7.3f} mmHg [{lo:+.3f},{hi:+.3f}] {'*' if (lo > 0 or hi < 0) else 'ns'}")
    lo, hi = np.percentile(ab, [2.5, 97.5])
    d = pf - pb
    if hi < 0:
        verdict = "PRECEDENCE SUPPORTED (forward fall exceeds backward)"
    elif lo > 0:
        verdict = "REVERSED (suppression FOLLOWS the pressure fall)"
    else:
        verdict = "NO PRECEDENCE -- symmetric in time"
    print(f"   {'forward MINUS backward':28s} {d:+7.3f} mmHg [{lo:+.3f},{hi:+.3f}]   {verdict}")


def main():
    cohort = os.environ.get("COHORT", "prop")
    HD = load(cohort)
    vals = [bd[t][3] for c, bd in HD.items() for t in bd if bd[t][3] == bd[t][3]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else None
    print(f"cohort={cohort}  cases={len(HD)}  case fixed effects; {NBOOT} case-level bootstrap reps")
    print("outcome is the SIGNED change in MAP (mmHg); negative = pressure fell")
    for k in (2, 4):
        analyse(HD, "bs", "burst-suppressed FRACTION of the bin", k, emg_cut)
        analyse(HD, "bsbin", "ANY burst suppression vs none", k, emg_cut)
        if emg_cut is not None:
            analyse(HD, "emg", "frontal EMG above median -- NEGATIVE CONTROL", k, emg_cut)


if __name__ == "__main__":
    sys.exit(main())
