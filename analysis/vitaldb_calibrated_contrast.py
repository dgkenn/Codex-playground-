#!/usr/bin/env python3
"""THE CALIBRATED PRIMARY ANALYSIS — burst suppression measured AGAINST its own negative control.

WHY THIS FILE REPLACES THE HEADLINE. Adversarial review established that the design's negative control is NOT null.
Frontal EMG -- recorded on the same sensor, not a measure of cortical suppression -- produces a significant
forward-minus-backward statistic under every estimator tried:

    within-case delta, simple model      EMG  +0.190 [+0.072, +0.329]   (k=2)
    within-case delta, fuller model      EMG  +0.499 [+0.316, +0.707]
    Mantel-Haenszel, dichotomised        EMG   0.87  [0.81, 0.94]  (ratio, significantly reversed)

So "the bootstrap interval excludes zero" is NOT a calibrated decision rule for this design: it fires on an
exposure that should be null. Every unqualified significance claim made with that rule is therefore
under-justified, including ones this project has already reported.

THE FIX. Estimate the burst-suppression asymmetry and the EMG asymmetry INSIDE THE SAME BOOTSTRAP REPLICATE, from
the same resampled cases, and report their DIFFERENCE with its own interval:

        contrast = asym(burst suppression) - asym(frontal EMG)

Because both are computed on the same resampled cases, the two estimates are properly correlated and the interval
on their difference is valid. This is the statistic that answers "is suppression doing something a same-sensor
non-suppression signal does not", which is the actual scientific question, rather than "is suppression's own
interval away from zero", which the EMG result shows is not a sufficient test.

DIRECTION MATTERS AND CUTS IN OUR FAVOUR, WHICH IS WHY IT MUST BE STATED CAREFULLY. The EMG bias is OPPOSITE in
sign to the suppression effect (EMG precedes a pressure RISE, suppression a FALL), so subtracting it makes the
suppression estimate LARGER, not smaller. That is convenient, and convenient corrections deserve extra scepticism.
Two readings are possible and the data here cannot fully separate them:
    (a) the design carries a small positive asymmetry bias, and EMG measures it;
    (b) EMG has its own real, opposite-signed physiology -- arousal and movement raise sympathetic tone and
        therefore pressure -- in which case it is NOT a pure bias estimate and subtracting it OVER-corrects.
Under (b) the contrast overstates the effect. The honest position is that the truth lies between the raw estimate
and the contrast, so BOTH are reported here, and the raw estimate is the conservative one for any claim about
magnitude. The contrast is the right statistic for the claim about SPECIFICITY.

Also reports a third exposure, slow-delta power, through the identical machinery: it is neither the hypothesis nor
a negative control but a depth marker, so it calibrates how much of the contrast is "any EEG change" versus
suppression specifically.

Estimator: within-case fixed effects; MAP(t) + dose + dCe + pre-trend over [t-3k, t-2k] (the corrected window that
shares no endpoint with either outcome); bins holding both a forward and a backward neighbour; CASE-level cluster
bootstrap shared across all exposures.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "400"))
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



def load():
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]),
                              _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan,
                              float(d["slow_db"]) if d["slow_db"] else np.nan,
                              np.nan]
            except Exception:
                pass
    seen = set()
    with open(f"{DATA}/bis_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                HD[cid][t][4] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    return HD


def build(HD, k):
    """One row set carrying ALL exposures, so every contrast is on identical rows."""
    med = {}
    for c, bd in HD.items():
        ts = [t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0]
        s = [bd[t][3] for t in ts if bd[t][3] == bd[t][3]]
        med[c] = float(np.median(s)) if len(s) >= 20 else np.nan
    emg_all = [bd[t][4] for c, bd in HD.items() for t in bd if bd[t][4] == bd[t][4]]
    emg_cut = float(np.median(emg_all)) if len(emg_all) > 1000 else np.nan
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        if not (med.get(c) == med.get(c)):
            continue
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose, sl, emg = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3
                    and dose == dose and doseb == doseb):
                continue
            if not (bs == bs and sl == sl and emg == emg):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c])
            cols["bs"].append(1.0 if bs > 0 else 0.0)
            cols["slow"].append(1.0 if sl > med[c] else 0.0)
            cols["emg"].append(1.0 if emg > emg_cut else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb)
            cols["pre"].append(mb2 - mb3)          # [t-3k, t-2k]: shares no endpoint with either outcome
            cols["df"].append(mf - m); cols["db"].append(mb - m)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def asym(D, expo_key, w):
    """forward-minus-backward coefficient for one exposure, at the given case weights."""
    out = []
    for dy in ("df", "db"):
        mat = np.column_stack([D[expo_key], D["m0"], D["dz"], D["dce"], D["pre"], D[dy]])
        sw = np.bincount(D["case"], weights=w, minlength=D["ncase"])
        sw = np.where(sw > 0, sw, 1.0)
        dm = np.empty_like(mat)
        for j in range(mat.shape[1]):
            mu = np.bincount(D["case"], weights=w * mat[:, j], minlength=D["ncase"]) / sw
            dm[:, j] = mat[:, j] - mu[D["case"]]
        X = dm[:, :-1]; y = dm[:, -1]
        try:
            b = np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[0]
        except np.linalg.LinAlgError:
            return None
        out.append(b)
    return out[0] - out[1]


def main():
    k = int(os.environ.get("K", "4"))
    D = build(load(), k)
    if len(D.get("case", [])) < 10000:
        print("insufficient rows"); return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    starts = np.searchsorted(D["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    w1 = np.ones(len(D["case"]))
    print(f"k=+/-{k} bins (+/-{30*k}s);  {len(D['case'])} bins, {D['ncase']} cases;  {NBOOT} shared bootstrap reps")
    print("pre-trend over [t-3k, t-2k] (corrected window)\n")

    keys = ("bs", "slow", "emg")
    pts = {kk: asym(D, kk, w1) for kk in keys}
    if any(v is None for v in pts.values()):
        print("point-estimate fit failed"); return
    boots = {kk: [] for kk in keys}
    diffs = {"bs-emg": [], "slow-emg": [], "bs-slow": []}
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        v = {kk: asym(D, kk, w) for kk in keys}
        if any(x is None for x in v.values()):
            continue
        for kk in keys:
            boots[kk].append(v[kk])
        diffs["bs-emg"].append(v["bs"] - v["emg"])
        diffs["slow-emg"].append(v["slow"] - v["emg"])
        diffs["bs-slow"].append(v["bs"] - v["slow"])
    if len(diffs["bs-emg"]) < 50:
        print("bootstrap failed"); return

    print("RAW asymmetries (the conservative estimate for magnitude):")
    for kk, nm in (("bs", "burst suppression"), ("slow", "slow-delta power"), ("emg", "frontal EMG [control]")):
        lo, hi = np.percentile(boots[kk], [2.5, 97.5])
        print(f"   {nm:28s} {pts[kk]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    print("\nCALIBRATED CONTRASTS (shared bootstrap draw -- the valid specificity test):")
    for kk, nm in (("bs-emg", "suppression MINUS EMG control"),
                   ("slow-emg", "slow-delta MINUS EMG control"),
                   ("bs-slow", "suppression MINUS slow-delta")):
        lo, hi = np.percentile(diffs[kk], [2.5, 97.5])
        d = float(np.mean(diffs[kk]))
        print(f"   {nm:28s} {d:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    print("\n   The EMG bias is opposite-signed, so the contrast is LARGER than the raw estimate. If EMG carries")
    print("   its own arousal physiology rather than pure design bias, the contrast OVER-corrects -- so the raw")
    print("   number is the conservative bound on magnitude and the contrast is the test of specificity.")
    print("   'suppression MINUS slow-delta' asks whether this is more than a generic depth marker.")


if __name__ == "__main__":
    sys.exit(main())
