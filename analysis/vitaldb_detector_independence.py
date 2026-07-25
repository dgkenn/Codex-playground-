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
"""
import csv, math, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")


def logit(X, y):
    X = np.asarray(X, float); y = np.asarray(y, float); b = np.zeros(X.shape[1])
    W = np.ones(len(y))
    for _ in range(200):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        W = np.clip(p * (1 - p), 1e-9, None)
        z = X @ b + (y - p) / W
        try:
            b = np.linalg.solve((X.T * W) @ X + 1e-6 * np.eye(X.shape[1]), (X.T * W) @ z)
        except np.linalg.LinAlgError:
            break
    return b, np.sqrt(np.diag(np.linalg.pinv((X.T * W) @ X)))


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
                HD[cid][t] = (float(d["mbp"]) if d["mbp"] else np.nan,
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

    for expo_idx, expo_name in ((0, "monitor suppression ratio"), (1, "frontal EMG (negative control)")):
        for k in (2, 4):
            print(f"\n=== [{expo_name}] lag +{k} ({30*k}s) -> hypotension (MAP<65), split by own-baseline MAP ===")
            for lab, cond in (("MAP >= baseline (sensitivity phenotype)", lambda m, b: m >= b),
                              ("MAP <  baseline (hypoperfusion phenotype)", lambda m, b: m < b * 0.9)):
                X = []; y = []
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
                        X.append([1, e, m, ce, age if age == age else 55])
                        y.append(1.0 if m2 < 65 else 0.0)
                if len(X) < 400 or sum(y) < 25:
                    print(f"   {lab:44s} insufficient (n={len(X)}, ev={int(sum(y)) if y else 0})")
                    continue
                Xa = np.asarray(X, float)
                sd = Xa[:, 1].std()
                if sd > 1e-9 and expo_idx == 1:
                    Xa[:, 1] = (Xa[:, 1] - Xa[:, 1].mean()) / sd     # EMG has no natural 0-1 scale: report per SD
                b, se = logit(Xa, y)
                lo, hi = math.exp(b[1] - 1.96 * se[1]), math.exp(b[1] + 1.96 * se[1])
                unit = "per SD" if expo_idx == 1 else "per full suppression"
                print(f"   {lab:44s} OR={math.exp(b[1]):5.2f} [{lo:.2f},{hi:.2f}] {unit:20s} "
                      f"n={len(X):6d} ev={int(sum(y)):5d} {'*' if (lo > 1 or hi < 1) else 'ns'}")
    print("\n   [Pass criterion: the monitor SR reproduces the phenotype-specific pattern (positive at/above")
    print("    baseline, null below) while EMG does not. That separates physiology from instrumentation.]")


if __name__ == "__main__":
    sys.exit(main())
