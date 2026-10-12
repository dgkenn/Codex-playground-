#!/usr/bin/env python3
"""RED-TEAM HARDENING of the two-phenotype dissociation: is it regression to the mean?

THE OBJECTION. The phenotype split conditions on the CURRENT mean arterial pressure relative to the patient's own
baseline. Conditioning on a value being high makes the next value tend to fall, so *any* variable correlated with
"currently at the top of your own distribution" will appear to predict a subsequent fall -- and will appear to
predict a rise in the mirror stratum. The linear MAP adjustment used so far does not remove this. Evidence that the
artefact is real, not hypothetical: frontal EMG, which is not a measure of cortical suppression, shows the same
SIGN pattern (OR 1.05 above baseline, 0.91 below) in `analysis/vitaldb_detector_independence.py`.

THE FIX. Two independent hardenings, both of which must pass:

  (1) RTM-IMMUNE ESTIMATOR. Replace the linear MAP covariate with exact stratification on current MAP in 2 mmHg
      bins and pool with Mantel-Haenszel. Within a 2 mmHg stratum every bin has essentially the same current
      pressure, so every bin faces the same regression-to-the-mean pull; the artefact is held constant BY DESIGN
      rather than modelled. The MH estimator is nonparametric in MAP -- no functional form to get wrong.

  (2) CASE-LEVEL CLUSTER BOOTSTRAP. Bins within a case are massively correlated (a case contributes hundreds of
      them), so any bin-level standard error is far too small; the n>500,000 in the earlier tables is not 500,000
      independent observations, it is ~1,700. All confidence intervals here come from resampling CASES with
      replacement (500 replicates) and recomputing the whole MH estimate. This is the interval a reviewer will
      demand and it is the one reported.

  NEGATIVE CONTROLS run through the identical pipeline:
    * EMG exposure -- same sensor, same device, not cortical suppression. Bounds the residual artefact.
    * BACKWARD lag (outcome at t-k instead of t+k) -- if suppression heralds hypotension the forward association
      must exceed the backward one. A pure shared-state confounder is symmetric in time.

Exposure is binary (any suppression in the bin vs none) so that the MH tables are exact counts.
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "500"))
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



def load_joined():
    """(caseid, bin_t) -> detector BS, monitor SR, EMG, MAP, Ce, age. De-duplicated on both streams."""
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                HD[cid][t] = (float(d["bs"]),
                              _map_ok(d["mbp"]),
                              ce)
            except Exception:
                pass
    SR = defaultdict(dict); seen = set()
    with open(f"{DATA}/bis_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                sr = float(d["devsr"]) if d["devsr"] else np.nan
                emg = float(d["emg"]) if d["emg"] else np.nan
                SR[cid][t] = (sr, emg)
            except Exception:
                pass
    return HD, SR


def build(HD, SR, exposure, lag_bins):
    """Return per-bin arrays for the MH analysis.  exposure in {'bs','sr','emg'}; lag_bins may be negative."""
    case_id = []; phen = []; strat = []; expo = []; out = []
    emg_all = []
    if exposure == "emg":
        for c in SR:
            for t in SR[c]:
                e = SR[c][t][1]
                if e == e:
                    emg_all.append(e)
        emg_med = float(np.median(emg_all)) if emg_all else np.nan

    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        base_v = [bd[t][1] for t in ts[:10] if bd[t][1] == bd[t][1]]
        if len(base_v) < 5:
            continue
        b0 = float(np.median(base_v))
        for t in ts[20:]:
            t2 = t + 30.0 * lag_bins
            if t2 not in bd:
                continue
            m = bd[t][1]; m2 = bd[t2][1]
            if m != m or m2 != m2:
                continue
            if m >= b0:
                ph = 1                      # at/above own baseline: "sensitivity" phenotype
            elif m < 0.9 * b0:
                ph = 0                      # clearly below own baseline: "hypoperfusion" phenotype
            else:
                continue                    # buffer zone excluded, as in the primary analysis
            if exposure == "bs":
                e = 1 if bd[t][0] > 0 else 0
            else:
                s = SR.get(c, {}).get(t)
                if s is None:
                    continue
                if exposure == "sr":
                    if s[0] != s[0]:
                        continue
                    e = 1 if s[0] > 0 else 0
                else:
                    if s[1] != s[1] or emg_med != emg_med:
                        continue
                    e = 1 if s[1] > emg_med else 0
            if c not in ci:
                ci[c] = len(ci)
            case_id.append(ci[c]); phen.append(ph)
            strat.append(int(np.clip(m, 30, 160) // 2))     # exact 2 mmHg stratification on CURRENT MAP
            expo.append(e); out.append(1 if m2 < 65 else 0)
    return (np.array(case_id, np.int32), np.array(phen, np.int8), np.array(strat, np.int16),
            np.array(expo, np.int8), np.array(out, np.int8), len(ci))


def mh_or(strat, expo, out, w=None):
    """Mantel-Haenszel odds ratio pooled over strata. `w` = integer multiplicity per row (cluster bootstrap)."""
    if w is None:
        w = np.ones(len(strat), np.float64)
    k = int(strat.max()) + 1 if len(strat) else 1
    cell = strat.astype(np.int64) * 4 + expo.astype(np.int64) * 2 + out.astype(np.int64)
    cnt = np.bincount(cell, weights=w, minlength=k * 4).reshape(k, 4)
    b = cnt[:, 2]; a = cnt[:, 3]          # exposed:  no-event, event
    d_ = cnt[:, 0]; c_ = cnt[:, 1]        # unexposed: no-event, event
    n = a + b + c_ + d_
    ok = n > 0
    if not ok.any():
        return np.nan
    num = np.sum(a[ok] * d_[ok] / n[ok])
    den = np.sum(b[ok] * c_[ok] / n[ok])
    if den <= 0 or num <= 0:
        return np.nan
    return num / den


def boot_ci(case_id, strat, expo, out, ncase):
    """Case-level cluster bootstrap of the MH OR."""
    order = np.argsort(case_id, kind="stable")
    ci_s = case_id[order]; st = strat[order]; ex = expo[order]; ou = out[order]
    starts = np.searchsorted(ci_s, np.arange(ncase), side="left")
    ends = np.searchsorted(ci_s, np.arange(ncase), side="right")
    mult = np.zeros(len(ci_s), np.float64)
    vals = []
    for _ in range(NBOOT):
        draw = rng.integers(0, ncase, ncase)
        cnt = np.bincount(draw, minlength=ncase).astype(np.float64)
        mult[:] = np.repeat(cnt, ends - starts)
        v = mh_or(st, ex, ou, mult)
        if v == v and 0 < v < 1e6:
            vals.append(v)
    if len(vals) < 100:
        return (np.nan, np.nan, len(vals))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (lo, hi, len(vals))


def run(HD, SR, exposure, label, lags=(2, 4, -2, -4)):
    print(f"\n=== exposure: {label} ===")
    print(f"{'lag':>6s}  {'phenotype':38s} {'MH OR':>7s}  {'95% CI (case cluster bootstrap)':>34s}  "
          f"{'bins':>8s} {'cases':>6s} {'strata':>6s}")
    for lag in lags:
        case_id, phen, strat, expo, out, ncase = build(HD, SR, exposure, lag)
        if not len(case_id):
            print(f"{lag:+6d}  no data")
            continue
        for ph, nm in ((1, "MAP >= own baseline (sensitivity)"), (0, "MAP <  own baseline (hypoperfusion)")):
            s = phen == ph
            if s.sum() < 500 or out[s].sum() < 25 or expo[s].sum() < 25:
                print(f"{lag:+6d}  {nm:38s} insufficient (bins={int(s.sum())}, exposed={int(expo[s].sum())})")
                continue
            cid_s = case_id[s]
            uniq, remap = np.unique(cid_s, return_inverse=True)
            orv = mh_or(strat[s], expo[s], out[s])
            lo, hi, nb = boot_ci(remap.astype(np.int32), strat[s], expo[s], out[s], len(uniq))
            sig = "*" if (lo == lo and (lo > 1 or hi < 1)) else "ns"
            nstrat = len(np.unique(strat[s]))
            print(f"{lag:+6d}  {nm:38s} {orv:7.2f}  [{lo:6.2f},{hi:6.2f}] {sig:>3s} (B={nb:3d})   "
                  f"{int(s.sum()):8d} {len(uniq):6d} {nstrat:6d}")


def main():
    HD, SR = load_joined()
    print(f"loaded {len(HD)} cases with EEG+MAP, {len(SR)} with monitor BIS")
    print(f"MH stratification: exact 2 mmHg bins of CURRENT MAP.  CIs: {NBOOT} case-level cluster bootstrap reps.")
    run(HD, SR, "bs", "raw-EEG detector burst suppression (any vs none)")
    run(HD, SR, "sr", "monitor suppression ratio (any vs none) -- independent instrument")
    run(HD, SR, "emg", "frontal EMG above median -- NEGATIVE CONTROL (bounds the RTM artefact)")
    print("\n   [Pass criteria, all required:")
    print("      (a) forward lags positive with a cluster-bootstrap CI excluding 1 in the sensitivity phenotype;")
    print("      (b) null or clearly smaller in the hypoperfusion phenotype;")
    print("      (c) forward association materially exceeds the backward association (temporal precedence);")
    print("      (d) the EMG negative control is an order of magnitude smaller than the suppression exposures.]")


if __name__ == "__main__":
    sys.exit(main())
