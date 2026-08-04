#!/usr/bin/env python3
"""EXTERNAL VALIDATION #1 — the two-phenotype dissociation in a DIFFERENT ANAESTHETIC CLASS (sevoflurane).

The discovery cohort is propofol: an intravenous GABA_A-positive allosteric modulator with direct venodilator and
sympatholytic actions. If the phenotype split were a property of *propofol pharmacology* rather than of burst
suppression itself, it would not survive a switch to an inhaled halogenated ether, whose haemodynamic profile
(dose-dependent SVR reduction with preserved-to-increased heart rate, minimal venodilation) is different.

Design is identical to `analysis/vitaldb_two_phenotype.py`:
  exposure : burst-suppression fraction in bin t (validated raw-EEG detector)
  outcome  : MAP < 65 mmHg at bin t + k (k = 2, 4 -> +60 s, +120 s)
  split    : each patient is their own control -- bins are stratified by whether the CURRENT MAP is at/above that
             patient's own maintenance baseline (median MAP of the first 10 maintenance bins) or clearly below it.
  adjust   : current MAP, end-tidal sevoflurane (dose), age; maintenance bins only (Et-sevo >= 1.0 %), first 20
             maintenance bins dropped so induction transients cannot drive the result.

Falsifiable prediction registered before running: BS predicts subsequent hypotension ONLY in the at/above-baseline
stratum (the "anaesthetic-sensitivity" phenotype), and is null in the already-hypotensive stratum (where BS is the
consequence of hypoperfusion, not its herald).
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
    """caseid -> {bin_t: (bs, mbp, et_sevo, age)}; the `ce` column carries end-tidal sevoflurane %."""
    BD = defaultdict(dict)
    with open(f"{DATA}/sevo_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                t = float(d["bin_t"])
                et = float(d["ce"]) if d["ce"] else np.nan
                BD[d["caseid"]][t] = (float(d["bs"]),
                                      float(d["mbp"]) if d["mbp"] else np.nan,
                                      et,
                                      float(d["age"]) if d["age"] else np.nan)
            except Exception:
                pass
    return BD


def baselines(BD):
    base = {}
    for c, bd in BD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        v = [bd[t][1] for t in ts[:10] if bd[t][1] == bd[t][1]]
        if len(v) >= 5:
            base[c] = float(np.median(v))
    return base


def main():
    BD = load(); base = baselines(BD)
    print(f"SEVOFLURANE cohort: {len(BD)} cases, {len(base)} with an estimable maintenance MAP baseline")
    for k in (2, 4):
        print(f"\n=== lag +{k} ({30*k}s): BS -> hypotension (MAP<65), split by MAP vs the patient's OWN baseline ===")
        for lab, cond in (("MAP >= baseline (sensitivity phenotype)", lambda m, b: m >= b),
                          ("MAP <  baseline (hypoperfusion phenotype)", lambda m, b: m < b * 0.9)):
            X = []; y = []
            for c, bd in BD.items():
                if c not in base:
                    continue
                b0 = base[c]
                ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
                if len(ts) < 32:
                    continue
                for t in ts[20:]:                       # drop induction
                    t2 = t + 30.0 * k                   # ABSOLUTE time index, never positional
                    if t2 not in bd:
                        continue
                    bs, m, et, age = bd[t]; _, m2, _, _ = bd[t2]
                    if m != m or m2 != m2 or not cond(m, b0):
                        continue
                    X.append([1, bs, m, et, age if age == age else 55])
                    y.append(1.0 if m2 < 65 else 0.0)
            if len(X) < 400 or sum(y) < 25:
                print(f"   {lab:44s} insufficient (n={len(X)}, ev={int(sum(y)) if y else 0})")
                continue
            b, se = logit(X, y)
            lo, hi = math.exp(b[1] - 1.96 * se[1]), math.exp(b[1] + 1.96 * se[1])
            print(f"   {lab:44s} BS OR={math.exp(b[1]):5.2f} [{lo:.2f},{hi:.2f}] "
                  f"n={len(X):6d} ev={int(sum(y)):5d} {'*' if lo > 1 else 'ns'}")
    print("\n   [Replication criterion: OR>1 with CI excluding 1 in the at/above-baseline stratum AND a null in the")
    print("    below-baseline stratum. Drug class is the independent axis here; the institution is the same.]")


if __name__ == "__main__":
    sys.exit(main())
