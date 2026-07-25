#!/usr/bin/env python3
"""EXTERNAL VALIDATION #2 — the two-phenotype dissociation with a COMPLETELY INDEPENDENT EXPOSURE MEASUREMENT.

Every result so far uses our own raw-EEG burst-suppression detector. A reviewer's first move is to ask whether the
phenotype split is a property of the *detector* rather than of the patient. This replaces the exposure with the
suppression ratio reported by the commercial depth-of-anaesthesia monitor (BIS `devsr`, the proportion of the
preceding epoch that the device itself classified as suppressed) -- different electrodes (forehead vs our bipolar
longitudinal montage), different signal chain, different, proprietary, FDA-cleared algorithm.

If the dissociation is real physiology it must survive swapping the measuring instrument. If it is an artefact of
our detector it will not.

  exposure : monitor suppression ratio in bin t (0-100 %, rescaled to a 0-1 fraction to match the detector scale)
  outcome  : MAP < 65 mmHg at bin t + k (k = 2, 4 -> +60 s, +120 s), ABSOLUTE time index
  split    : current MAP at/above vs clearly below that patient's own maintenance MAP baseline
  adjust   : current MAP, propofol effect-site concentration (dose), age; maintenance bins only (Ce >= 1.0),
             first 20 maintenance bins dropped.

A secondary column reports the same model using EMG as a negative-control exposure: frontal EMG power is recorded
on the same sensor by the same device but is not a measure of cortical suppression, so it should NOT show the
phenotype-specific pattern. That test discriminates "suppression predicts hypotension" from "anything the BIS
sensor records predicts hypotension".

TWO CORRECTIONS applied after review (both changed reported numbers, neither changed a conclusion):
  * EMG is standardised against ONE GLOBAL mean and SD computed over the whole cohort, not recomputed inside each
    (lag, phenotype) subset. Standardising within subset makes "1 SD of EMG" a different absolute quantity in each
    stratum, so the two strata's "per SD" odds ratios were not on a comparable scale -- which is precisely the
    cross-stratum comparison this file exists to make.
  * Confidence intervals come from a CASE-LEVEL cluster bootstrap. The model-based Wald intervals used before
    treated ~600,000 bins from ~1,700 patients as 600,000 independent observations and were far too narrow; every
    significance verdict in the earlier version of this file was anti-conservative.

NOTE ON STATUS: this file uses MAP as a LINEAR covariate. That specification is now known to carry a regression-to-
the-mean artefact (see `analysis/vitaldb_rtm_hardening.py`). It is retained because it is the specification under
which the artefact was DISCOVERED -- the EMG negative control misbehaving here is what triggered the whole
hardening pass. Do not cite its effect sizes; cite the exactly-stratified versions.
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")


def logit(X, y, w=None):
    """Frequency-weighted logistic regression; w carries the case-bootstrap multiplicities."""
    X = np.asarray(X, float); y = np.asarray(y, float); b = np.zeros(X.shape[1])
    if w is None:
        w = np.ones(len(y))
    for _ in range(200):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        v = np.clip(p * (1 - p), 1e-9, None)
        W = v * w
        z = X @ b + (y - p) / v
        try:
            nb = np.linalg.solve((X.T * W) @ X + 1e-6 * np.eye(X.shape[1]), (X.T * W) @ z)
        except np.linalg.LinAlgError:
            return None
        if np.max(np.abs(nb - b)) < 1e-9:
            return nb
        b = nb
    return b


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



def load():
    """Join the haemodynamic/dose stream to the monitor stream on (caseid, absolute bin time)."""
    HD = defaultdict(dict)
    seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:                       # de-duplicate (historic double-extraction)
                    continue
                seen.add((cid, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                HD[cid][t] = (_map_ok(d["mbp"]),
                              ce,
                              float(d["age"]) if d["age"] else np.nan)
            except Exception:
                pass
    BD = defaultdict(dict)
    seen = set()
    with open(f"{DATA}/bis_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                    continue
                seen.add((cid, t))
                sr = float(d["devsr"]) if d["devsr"] else np.nan
                emg = float(d["emg"]) if d["emg"] else np.nan
                if not (sr == sr and 0.0 <= sr <= 100.0):
                    continue
                mbp, ce, age = HD[cid][t]
                BD[cid][t] = (sr / 100.0, emg, mbp, ce, age)
            except Exception:
                pass
    return BD


def maintenance(bd):
    return sorted(t for t in bd if bd[t][3] == bd[t][3] and bd[t][3] >= 1.0)


def main():
    BD = load()
    base = {}
    for c, bd in BD.items():
        ts = maintenance(bd)
        v = [bd[t][2] for t in ts[:10] if bd[t][2] == bd[t][2]]
        if len(v) >= 5:
            base[c] = float(np.median(v))
    nsr = sum(1 for c in BD for t in BD[c] if BD[c][t][0] > 0)
    print(f"MONITOR-SR cohort: {len(BD)} cases with joined BIS + arterial pressure, "
          f"{len(base)} with an estimable baseline; {nsr} bins with SR>0")

    # ONE global EMG mean/SD, computed once over the whole cohort, so that "per SD" denotes the same absolute
    # quantity in every stratum and at every lag. Standardising inside each subset would make the strata's
    # odds ratios incomparable -- and comparing across strata is the entire point of this file.
    emg_all = np.array([BD[c][t][1] for c in BD for t in BD[c] if BD[c][t][1] == BD[c][t][1]], float)
    emg_mu = float(emg_all.mean()); emg_sd = float(emg_all.std())
    if not (emg_sd > 1e-9):
        emg_sd = 1.0
    print(f"global EMG standardisation: mean={emg_mu:.2f}, SD={emg_sd:.2f} (n={len(emg_all)} bins)")
    print(f"confidence intervals: {NBOOT} CASE-level cluster bootstrap replicates")

    for expo_idx, expo_name in ((0, "monitor suppression ratio"), (1, "frontal EMG (negative control)")):
        for k in (2, 4):
            print(f"\n=== [{expo_name}] lag +{k} ({30*k}s) -> hypotension (MAP<65), split by own-baseline MAP ===")
            for lab, cond in (("MAP >= baseline (sensitivity phenotype)", lambda m, b: m >= b),
                              ("MAP <  baseline (hypoperfusion phenotype)", lambda m, b: m < b * 0.9)):
                X = []; y = []; cid_rows = []
                for c, bd in BD.items():
                    if c not in base:
                        continue
                    b0 = base[c]; ts = maintenance(bd)
                    if len(ts) < 32:
                        continue
                    for t in ts[20:]:
                        t2 = t + 30.0 * k
                        if t2 not in bd:
                            continue
                        e = bd[t][expo_idx]; m = bd[t][2]; ce = bd[t][3]; age = bd[t][4]
                        m2 = bd[t2][2]
                        if e != e or m != m or m2 != m2 or not cond(m, b0):
                            continue
                        if expo_idx == 1:
                            e = (e - emg_mu) / emg_sd
                        X.append([1, e, m, ce, age if age == age else 55])
                        y.append(1.0 if m2 < 65 else 0.0)
                        cid_rows.append(c)
                if len(X) < 400 or sum(y) < 25:
                    print(f"   {lab:44s} insufficient (n={len(X)}, ev={int(sum(y)) if y else 0})")
                    continue
                Xa = np.asarray(X, float); ya = np.asarray(y, float)
                cids = np.asarray(cid_rows)
                order = np.argsort(cids, kind="stable")
                Xa = Xa[order]; ya = ya[order]; cids = cids[order]
                uniq, first = np.unique(cids, return_index=True)
                ncase = len(uniq)
                span = np.diff(np.append(first, len(cids)))
                b = logit(Xa, ya)
                if b is None:
                    print(f"   {lab:44s} fit failed")
                    continue
                boots = []
                for _ in range(NBOOT):
                    cnt = np.bincount(rng.integers(0, ncase, ncase), minlength=ncase).astype(float)
                    bb = logit(Xa, ya, np.repeat(cnt, span))
                    if bb is not None:
                        boots.append(bb[1])
                unit = "per SD" if expo_idx == 1 else "per full suppression"
                if len(boots) < 50:
                    print(f"   {lab:44s} OR={math.exp(b[1]):5.2f} (bootstrap failed) {unit}")
                    continue
                lo, hi = np.exp(np.percentile(boots, [2.5, 97.5]))
                print(f"   {lab:44s} OR={math.exp(b[1]):5.2f} [{lo:.2f},{hi:.2f}] {unit:20s} "
                      f"n={len(ya):6d} ev={int(ya.sum()):5d} cases={ncase:5d} {'*' if (lo > 1 or hi < 1) else 'ns'}")
    print("\n   [Pass criterion: the monitor SR reproduces the phenotype-specific pattern (positive at/above")
    print("    baseline, null below) while EMG does not. That separates physiology from instrumentation.]")


if __name__ == "__main__":
    sys.exit(main())
