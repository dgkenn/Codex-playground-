#!/usr/bin/env python3
"""PRE-REGISTERED SPLIT-HALF HOLD-OUT — does the result survive MY OWN analytic choices?

WHY THIS MATTERS MORE THAN IT SOUNDS. The sub-minute temporal claim cannot be validated on another dataset: a
survey of every candidate (MIMIC-IV/III waveform, BDSP HEEDB/sah/I-CARE/PSG/ECG, UCLA MLORD) found none with
simultaneous high-resolution EEG and continuous arterial pressure, and VitalDB has no third anaesthetic agent.
That external limitation is real and belongs in the manuscript.

What CAN be tested is the other live threat: overfitting through researcher degrees of freedom. This analysis has
accumulated a long list of choices, several of them made AFTER seeing results —
    * the physiologic MAP window [30, 150]
    * the pre-trend window [t-3k, t-2k], chosen after an endpoint-sharing artefact was found in [t-2k, t-k]
    * the lag k = 4 bins
    * occupancy and run-length band edges
    * the any-vs-none exposure coding
    * exclusion of the first 20 maintenance bins
Each was defensible in isolation, and tonight has already shown three of my own coding errors, so the possibility
that the surviving result is partly shaped by those choices has to be tested rather than assumed away.

THE DESIGN. Cases are split at random into two halves by a FIXED seed, and the primary results are computed
independently in each. Nothing is tuned on either half — the specification is frozen exactly as it currently
stands. This is not a discovery/validation split (both halves are analysed the same way); it is a stability check
on whether the estimates agree when the same pipeline meets different patients.

    reported per half: the forward-minus-backward asymmetry, the occupancy gradient (the dose-response), and the
    EMG negative control, with case-level bootstrap intervals computed WITHIN each half.

    PASS: both halves show the same sign, overlapping intervals, and a gradient in the same direction.
    FAIL: sign flips, or one half null with a large point-estimate difference -- which would mean the pooled
    result is being driven by a subset and the analytic choices are doing work the physiology is not.

A SECOND, HARDER SPLIT is also run: by CASE DURATION (short vs long operations). Random halves differ only by
sampling noise, whereas duration splits differ systematically in surgery type, patient mix and cumulative
exposure, so agreement across that split is a stronger stability claim than agreement across random halves.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)
SPLIT_SEED = 991
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))
OCC_BANDS = [(1, 2, "1-2 of last 10"), (3, 4, "3-4"), (5, 7, "5-7"), (8, 10, "8-10")]


def _map_ok(raw):
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
                HD[cid][t] = [float(d["bs"]), _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan, np.nan]
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
                HD[cid][t][3] = float(d["emg"]) if d["emg"] else np.nan
            except Exception:
                pass
    return HD


def build(HD, k, emg_cut):
    cols = defaultdict(list); ci = {}; dur = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        dur[c] = len(ts)
        occ = {}
        for i, t in enumerate(ts):
            w = ts[max(0, i - 9):i + 1]
            occ[t] = float(sum(1.0 for x in w if bd[x][0] == bd[x][0] and bd[x][0] > 0))
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose, emg = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3
                    and dose == dose and doseb == doseb and bs == bs):
                continue
            if c not in ci:
                ci[c] = len(ci)
            cols["case"].append(ci[c]); cols["cid"].append(c)
            cols["bs"].append(1.0 if bs > 0 else 0.0)
            cols["emg"].append(1.0 if (emg == emg and emg_cut == emg_cut and emg > emg_cut) else 0.0)
            cols["emgok"].append(1.0 if emg == emg else 0.0)
            cols["occ"].append(occ[t])
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["dur"].append(float(dur[c]))
    D = {a: (np.asarray(b, np.float64) if a != "cid" else np.asarray(b, dtype=object))
         for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(sub, expo, dy, w, ncase):
    mat = np.column_stack([sub[e] for e in expo] + [sub["m0"], sub["dz"], sub["dce"], sub["pre"], dy])
    sw = np.bincount(sub["case"], weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(sub["case"], weights=w * mat[:, j], minlength=ncase) / sw
        dm[:, j] = mat[:, j] - mu[sub["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[:len(expo)]
    except np.linalg.LinAlgError:
        return None


def analyse(D, mask, label, ncase):
    keys = [k for k in D if k not in ("ncase", "cid")]
    sub = {kk: D[kk][mask] for kk in keys}
    o = np.argsort(sub["case"], kind="stable")
    sub = {kk: v[o] for kk, v in sub.items()}
    span = (np.searchsorted(sub["case"], np.arange(ncase), side="right")
            - np.searchsorted(sub["case"], np.arange(ncase), side="left"))
    n = len(sub["case"]); w1 = np.ones(n)
    print(f"\n--- {label}  ({n} bins, {len(np.unique(sub['case']))} cases) ---")
    # asymmetry for bs and for emg
    for nm, key in (("burst suppression", "bs"), ("frontal EMG [control]", "emg")):
        f = fit(sub, [key], sub["df"], w1, ncase); b = fit(sub, [key], sub["db"], w1, ncase)
        if f is None or b is None:
            print(f"   {nm:26s} fit failed"); continue
        bd = []
        for _ in range(NBOOT):
            cnt = np.bincount(rng.integers(0, ncase, ncase), minlength=ncase).astype(np.float64)
            w = np.repeat(cnt, span)
            a2 = fit(sub, [key], sub["df"], w, ncase); b2 = fit(sub, [key], sub["db"], w, ncase)
            if a2 is not None and b2 is not None:
                bd.append(a2[0] - b2[0])
        if len(bd) < 50:
            print(f"   {nm:26s} bootstrap failed"); continue
        lo, hi = np.percentile(bd, [2.5, 97.5])
        print(f"   {nm:26s} asym = {f[0]-b[0]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    # occupancy gradient
    expo = [f"occ{i}" for i in range(len(OCC_BANDS))]
    for i, (lo_, hi_, _) in enumerate(OCC_BANDS):
        sub[f"occ{i}"] = ((sub["occ"] >= lo_) & (sub["occ"] <= hi_)).astype(float)
    pf = fit(sub, expo, sub["df"], w1, ncase)
    if pf is None:
        print("   occupancy gradient: fit failed"); return
    gb = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, ncase, ncase), minlength=ncase).astype(np.float64)
        v = fit(sub, expo, sub["df"], np.repeat(cnt, span), ncase)
        if v is not None:
            gb.append(v[-1] - v[0])
    if len(gb) >= 50:
        lo, hi = np.percentile(gb, [2.5, 97.5])
        vals = "  ".join(f"{x:+.3f}" for x in pf)
        print(f"   occupancy bands (fwd dMAP): {vals}")
        print(f"   gradient (highest-lowest)  = {pf[-1]-pf[0]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")


def main():
    k = int(os.environ.get("K", "4"))
    HD = load()
    vals = [bd[t][3] for c, bd in HD.items() for t in bd if bd[t][3] == bd[t][3]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else np.nan
    D = build(HD, k, emg_cut)
    n = len(D["case"])
    print(f"k=+/-{k} bins; {n} bins, {D['ncase']} cases; {NBOOT} bootstrap reps per half")
    print(f"specification FROZEN as it stands; split seed {SPLIT_SEED}, no tuning on either half")

    srng = np.random.default_rng(SPLIT_SEED)
    assign = srng.integers(0, 2, D["ncase"])
    half = assign[D["case"]]
    print("\n=== SPLIT 1: random halves (tests sampling stability only) ===")
    analyse(D, half == 0, "random half A", D["ncase"])
    analyse(D, half == 1, "random half B", D["ncase"])

    med = np.median(np.unique(np.column_stack([D["case"], D["dur"]]), axis=0)[:, 1])
    print(f"\n=== SPLIT 2: by case duration (median {med*0.5:.0f} min) -- a HARDER split ===")
    print("    halves differ systematically in surgery type, patient mix and cumulative exposure")
    analyse(D, D["dur"] < med, f"SHORT cases (< {med*0.5:.0f} min)", D["ncase"])
    analyse(D, D["dur"] >= med, f"LONG cases (>= {med*0.5:.0f} min)", D["ncase"])
    print("\n   PASS = same sign, overlapping intervals, gradient in the same direction in both halves.")


if __name__ == "__main__":
    sys.exit(main())
