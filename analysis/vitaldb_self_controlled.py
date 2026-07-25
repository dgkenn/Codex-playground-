#!/usr/bin/env python3
"""THE DEFINITIVE SPECIFICATION: a self-controlled, dose-matched, pressure-matched test of whether burst
suppression PRECEDES hypotension.

Why the earlier specifications are not sufficient.
  * The linear-MAP logistic carries a regression-to-the-mean artefact (demonstrated: the EMG negative control,
    which is not a measure of cortical suppression, showed OR 1.05 / 0.91 under it and a clean null under exact
    stratification).
  * The Mantel-Haenszel version fixed the pressure functional form but pooled ACROSS patients and did not hold
    ANAESTHETIC DOSE fixed. Deep anaesthesia causes both suppression and vasodilation, so a dose-unadjusted
    estimate cannot support the claim "independent of anaesthetic dose".

This script removes both at once. Each stratum is
        one CASE  x  one 4 mmHg band of CURRENT MAP  x  one 0.5 unit band of ANAESTHETIC DOSE
so every comparison is a patient against THEMSELVES, at the same pressure, at the same drug concentration. All
time-invariant patient characteristics (age, comorbidity, frailty, surgery, baseline vascular tone, anything
unmeasured) are differenced out by construction, and the residual contrast is: within this patient, at this
pressure and this dose, do the bins that happen to be suppressed differ from the bins that are not in what the
pressure does next?

  exposure  : any burst suppression in the bin vs none
  outcome   : MAP < 65 mmHg at t + k, ABSOLUTE time index
  estimator : Mantel-Haenszel over the self-controlled strata (uninformative strata contribute nothing)
  inference : CASE-level cluster bootstrap
  controls  : (i) backward lags -- the decisive test of precedence. A shared contemporaneous state is SYMMETRIC in
                  time; a causal cascade is not. Precedence requires forward > backward.
              (ii) frontal EMG as a negative-control exposure through the identical pipeline.
              (iii) a formal forward-minus-backward asymmetry statistic with a bootstrap interval, because
                  eyeballing two overlapping CIs is not a test.

Verdict rule fixed in advance: the claim "burst suppression precedes hypotension" is supported only if the
forward/backward OR ratio interval excludes 1 for the raw-EEG detector.
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
MAP_BAND = float(os.environ.get("MAP_BAND", "4"))
DOSE_BAND = float(os.environ.get("DOSE_BAND", "0.5"))
rng = np.random.default_rng(20260725)


def load(cohort):
    """caseid -> {bin_t: (bs, mbp, dose, emg)}.  dose = propofol Ce or end-tidal sevo %."""
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


def build(HD, lag_bins, exposure, emg_cut=None, ci=None):
    """Self-controlled strata: (case, MAP band, dose band). Returns arrays + a contiguous stratum index.

    `ci` is the case -> integer index map. It MUST be shared across lags: the bootstrap reuses one draw for the
    forward and backward lags so that their ratio is properly correlated, and that is only valid if index k means
    the same patient in every lag's arrays. Building a fresh map per lag silently misaligns them whenever a case
    contributes rows at one lag but not another.
    """
    case = []; key = []; expo = []; out = []
    if ci is None:
        ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            t2 = t + 30.0 * lag_bins
            if t2 not in bd:
                continue
            bs, m, dose, emg = bd[t]
            m2 = bd[t2][1]
            if m != m or m2 != m2 or dose != dose:
                continue
            if exposure == "bs":
                e = 1 if bs > 0 else 0
            else:
                if emg != emg or emg_cut is None:
                    continue
                e = 1 if emg > emg_cut else 0
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c])
            key.append((ci[c],
                        int(np.clip(m, 30, 160) // MAP_BAND),
                        int(np.clip(dose, 0, 20) // DOSE_BAND)))
            expo.append(e); out.append(1 if m2 < 65 else 0)
    if not key:
        return None
    uk = {}
    strat = np.empty(len(key), np.int32)
    for i, k in enumerate(key):
        if k not in uk:
            uk[k] = len(uk)
        strat[i] = uk[k]
    return (np.array(case, np.int32), strat, np.array(expo, np.int8), np.array(out, np.int8), len(ci), len(uk))


def mh(strat, expo, out, w, nstrat):
    cell = strat.astype(np.int64) * 4 + expo.astype(np.int64) * 2 + out.astype(np.int64)
    cnt = np.bincount(cell, weights=w, minlength=nstrat * 4).reshape(nstrat, 4)
    b = cnt[:, 2]; a = cnt[:, 3]; d_ = cnt[:, 0]; c_ = cnt[:, 1]
    n = a + b + c_ + d_
    ok = n > 0
    num = float(np.sum(a[ok] * d_[ok] / n[ok])); den = float(np.sum(b[ok] * c_[ok] / n[ok]))
    if num <= 0 or den <= 0:
        return np.nan
    return num / den


def informative(strat, expo, out, nstrat):
    """Strata that contribute to the MH numerator or denominator (both exposure levels present)."""
    cell = strat.astype(np.int64) * 4 + expo.astype(np.int64) * 2 + out.astype(np.int64)
    cnt = np.bincount(cell, minlength=nstrat * 4).reshape(nstrat, 4)
    ex = cnt[:, 2] + cnt[:, 3]; un = cnt[:, 0] + cnt[:, 1]
    ev = cnt[:, 1] + cnt[:, 3]; nv = cnt[:, 0] + cnt[:, 2]
    return int(np.sum((ex > 0) & (un > 0) & (ev > 0) & (nv > 0)))


class Boot:
    """Case-level cluster bootstrap that reuses ONE draw across all lags, so forward and backward estimates are
    computed on the same resampled cases and their ratio is properly correlated."""

    def __init__(self, sets, ncase):
        self.sets = sets            # lag -> (case, strat, expo, out, nstrat)
        self.ncase = ncase
        self.pre = {}
        for lag, (case, strat, expo, out, ns) in sets.items():
            o = np.argsort(case, kind="stable")
            cs = case[o]
            st = np.searchsorted(cs, np.arange(ncase), side="left")
            en = np.searchsorted(cs, np.arange(ncase), side="right")
            self.pre[lag] = (strat[o], expo[o], out[o], ns, en - st)

    def run(self, nboot):
        acc = defaultdict(list)
        for _ in range(nboot):
            cnt = np.bincount(rng.integers(0, self.ncase, self.ncase),
                              minlength=self.ncase).astype(np.float64)
            rep = {}
            for lag, (st, ex, ou, ns, span) in self.pre.items():
                v = mh(st, ex, ou, np.repeat(cnt, span), ns)
                if v == v and 0 < v < 1e6:
                    rep[lag] = math.log(v)
            for lag, v in rep.items():
                acc[lag].append(v)
            for k in (2, 4):
                if k in rep and -k in rep:
                    acc[("asym", k)].append(rep[k] - rep[-k])
        return acc


def analyse(HD, exposure, label, cohort):
    emg_cut = None
    if exposure == "emg":
        vals = [bd[t][3] for c, bd in HD.items() for t in bd if bd[t][3] == bd[t][3]]
        if len(vals) < 1000:
            print(f"\n=== {label}: no EMG available in this cohort, skipped ===")
            return
        emg_cut = float(np.median(vals))
    sets = {}
    ci = {}                       # ONE case->index map shared by every lag (see build() docstring)
    for lag in (2, 4, -2, -4):
        r = build(HD, lag, exposure, emg_cut, ci)
        if r is None:
            continue
        case, strat, expo, out, _nc, ns = r
        sets[lag] = (case, strat, expo, out, ns)
    if not sets:
        return
    ncase = len(ci)
    print(f"\n=== {label} ===")
    print(f"{'lag':>6s}  {'MH OR':>7s}  {'95% CI (case bootstrap)':>24s}  {'bins':>8s} {'strata':>7s} {'informative':>11s}")
    boot = Boot(sets, ncase)
    acc = boot.run(NBOOT)
    point = {}
    for lag in (2, 4, -2, -4):
        if lag not in sets:
            continue
        case, strat, expo, out, ns = sets[lag]
        v = mh(strat, expo, out, np.ones(len(strat)), ns)
        point[lag] = v
        inf = informative(strat, expo, out, ns)
        bs = acc.get(lag, [])
        if len(bs) < 50:
            print(f"{lag:+6d}  {v:7.2f}   bootstrap failed ({len(bs)} reps)")
            continue
        lo, hi = np.exp(np.percentile(bs, [2.5, 97.5]))
        sig = "*" if (lo > 1 or hi < 1) else "ns"
        print(f"{lag:+6d}  {v:7.2f}  [{lo:6.2f},{hi:6.2f}] {sig:>3s}  {len(strat):8d} {ns:7d} {inf:11d}")
    print("   --- temporal asymmetry (forward OR / backward OR); >1 means suppression PRECEDES hypotension ---")
    for k in (2, 4):
        a = acc.get(("asym", k), [])
        if len(a) < 50 or k not in point or -k not in point:
            continue
        r = point[k] / point[-k]
        lo, hi = np.exp(np.percentile(a, [2.5, 97.5]))
        verdict = "PRECEDENCE SUPPORTED" if lo > 1 else ("REVERSED" if hi < 1 else "NO PRECEDENCE (symmetric)")
        print(f"      +{k} vs -{k}:  ratio={r:5.2f} [{lo:.2f},{hi:.2f}]   {verdict}")


def main():
    cohort = os.environ.get("COHORT", "prop")
    HD = load(cohort)
    print(f"cohort={cohort}  cases loaded={len(HD)}")
    print(f"self-controlled strata = case x {MAP_BAND:g} mmHg current MAP x {DOSE_BAND:g} unit anaesthetic dose; "
          f"{NBOOT} case-level bootstrap reps")
    analyse(HD, "bs", "raw-EEG detector burst suppression (any vs none), SELF-CONTROLLED", cohort)
    analyse(HD, "emg", "frontal EMG above median -- NEGATIVE CONTROL, SELF-CONTROLLED", cohort)


if __name__ == "__main__":
    sys.exit(main())
