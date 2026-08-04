#!/usr/bin/env python3
"""EXTERNAL TEST OF THE MECHANISTIC CLAIM: does burden behave as a fixed quantity in an independent cohort?

WHAT THIS ADDS BEYOND `icare_external_replication.py`. That script replicated the OUTCOME claim in I-CARE --
among patients already suppressed, quantitative burden still stratifies outcome (+34.1 pp [+23.2, +44.2]). It
did not test the MECHANISTIC claim, which is the more interesting and more fragile one:

    Q2 (HEEDB): suppression burden behaves as a FIXED QUANTITY MEASURED WITH ERROR, not a reversible state.
        - averaging two readings predicts death better (0.787) than the most recent (0.747)
        - the difference between readings carries no signal once the mean is known (+5.88 pp [-17.13, +26.58])
        - ICC of a single reading 0.815

That claim is what licenses the metabolic reading -- that burden indexes a cerebral metabolic rate which is low
because tissue has been lost. It has been tested in one direction (VitalDB, where the same construct is
reversible under anaesthesia, as required). It has NOT been tested in a second post-anoxic cohort, and a
mechanistic claim resting on one cohort's serial structure is thin.

I-CARE makes that possible: hourly EEG for up to 72 h after arrest, at five hospitals in a different
consortium, and OUR OWN detector applied to it -- the same amplitude-threshold burden, not the cohort's
in-built measure. Measuring the same patients at several hours gives the serial structure Q2 needs.

  X1  ICC of a single reading across hours. HEEDB gave 0.815 within a recording. A fixed quantity should give
      a HIGH value here too; a reversible state should not.
  X2  Does the correlation between two readings DECAY with the separation in hours? For a fixed quantity plus
      noise it should be flat; this is the same discriminator used in VitalDB, where it decayed sharply
      (0.973 at lag 1 to 0.484 at lag 40) exactly as a drug-driven state should.
  X3  MEAN versus MOST RECENT for predicting outcome. A fixed quantity is better estimated by averaging; a
      changing state is better described by its latest value. HEEDB gave 0.787 (mean) against 0.747 (recent).
  X4  MEAN versus DIFFERENCE decomposition -- the identifying test from Q2. Under a fixed quantity the mean
      carries the signal and the difference term is indistinguishable from zero.

INTERPRETATION FIXED IN ADVANCE. If I-CARE shows the same fixed-quantity signature, the mechanistic claim is
externally validated in the population it is about. If it shows decay and a live difference term, the Q2 result
is specific to HEEDB's measurement or cohort and the metabolic reading must be weakened accordingly. Both
outcomes are reportable; only one is convenient.
"""
import csv, glob, os, sys
from collections import defaultdict

import numpy as np

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
SERIAL_GLOB = os.environ.get("ICARE_SERIAL", "/tmp/eeg_probe/icare_bs*.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))


def logit_fit(X, y, iters=60, ridge=1e-6):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        A = X.T @ (X * w[:, None]) + ridge * np.eye(X.shape[1])
        try:
            nb = np.linalg.solve(A, X.T @ (w * z))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(nb)) or np.max(np.abs(nb - b)) < 1e-8:
            b = nb if np.all(np.isfinite(nb)) else b
            break
        b = nb
    return b


def predict(X, b):
    return 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cv_auc(X, y, rng, folds=5, reps=5):
    out = []
    for _ in range(reps):
        idx = rng.permutation(len(y))
        for f in range(folds):
            te = idx[f::folds]; tr = np.setdiff1d(idx, te)
            if y[tr].sum() < 5 or (len(tr) - y[tr].sum()) < 5 or y[te].sum() < 2:
                continue
            try:
                out.append(auc(y[te], predict(X[te], logit_fit(X[tr], y[tr]))))
            except Exception:
                continue
    return float(np.nanmean(out)) if out else float("nan")


def main():
    rng = np.random.default_rng(20260726)

    coh = {}
    with open(COHORT) as fh:
        for r in csv.DictReader(fh):
            pid = (r.get("pid") or "").strip()
            try:
                cpc = float(r.get("cpc"))
            except Exception:
                continue
            if pid and cpc == cpc:
                coh[pid] = 1.0 if cpc >= 3 else 0.0

    # (patient -> {hour: burden}) across every per-hour extraction file
    per = defaultdict(dict)
    files = sorted(glob.glob(SERIAL_GLOB))
    for f in files:
        for r in csv.DictReader(open(f)):
            pid = (r.get("pid") or "").strip()
            try:
                h = float(r.get("hour")); v = float(r.get("bs"))
            except Exception:
                continue
            if pid and h == h and v == v:
                per[pid][round(h)] = v
    print(f"extraction files read: {len(files)}  ({', '.join(os.path.basename(x) for x in files)})")
    print(f"patients with at least one measurement: {len(per):,}")
    multi = {p: v for p, v in per.items() if len(v) >= 2}
    print(f"   with two or more distinct hours: {len(multi):,}")
    if len(multi) < 80:
        print("\n*** serial extraction still running or too sparse -- rerun when the per-hour files complete.")
        return 1

    # ---- X1: reliability ---------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("X1  ICC OF A SINGLE READING ACROSS HOURS")
    print("=" * 92)
    means = np.array([np.mean(list(v.values())) for v in multi.values()])
    within = np.mean([np.var(list(v.values()), ddof=1) for v in multi.values() if len(v) > 1])
    between = float(np.var(means, ddof=1))
    icc = between / (between + within) if (between + within) > 0 else float("nan")
    print(f"   n={len(multi):,}   between-patient variance {between:.4f}   within-patient {within:.4f}")
    print(f"   ICC = {icc:.3f}")
    print(f"   HEEDB (within a recording)  0.815   |   VitalDB anaesthetic (within a case)  0.313")
    print(f"   {'CONSISTENT with a fixed quantity' if icc >= 0.6 else 'NOT consistent with a fixed quantity'}")

    # ---- X2: decay with separation -----------------------------------------------------------------
    print("\n" + "=" * 92)
    print("X2  DOES AGREEMENT DECAY WITH THE SEPARATION IN HOURS?")
    print("=" * 92)
    bands = ((0, 14), (14, 26), (26, 40))
    print(f"   {'separation (h)':>16s} {'n pairs':>9s} {'correlation':>13s}")
    got = []
    for lo, hi in bands:
        xs, ys = [], []
        for p, v in multi.items():
            hrs = sorted(v)
            for i in range(len(hrs)):
                for j in range(i + 1, len(hrs)):
                    d = abs(hrs[j] - hrs[i])
                    if lo <= d < hi:
                        xs.append(v[hrs[i]]); ys.append(v[hrs[j]])
        if len(xs) >= 40 and np.std(xs) > 0 and np.std(ys) > 0:
            rho = float(np.corrcoef(xs, ys)[0, 1])
            got.append((lo, hi, len(xs), rho))
            print(f"   {f'{lo}-{hi}':>16s} {len(xs):9,d} {rho:12.3f}")
    if len(got) >= 2:
        print(f"\n   change from the shortest to the longest separation: {got[-1][3]-got[0][3]:+.3f}")
        print("   FLAT is the fixed-quantity signature. VitalDB, where suppression is drug-driven, decayed")
        print("   by -0.488 over its lag range.")

    # ---- X3 / X4: does the trajectory add? ---------------------------------------------------------
    print("\n" + "=" * 92)
    print("X3/X4  MEAN vs MOST RECENT, AND THE MEAN/DIFFERENCE DECOMPOSITION")
    print("=" * 92)
    rows = []
    for p, v in multi.items():
        if p not in coh:
            continue
        hrs = sorted(v)
        rows.append(dict(y=coh[p], first=v[hrs[0]], last=v[hrs[-1]],
                         mean=float(np.mean(list(v.values()))), span=hrs[-1] - hrs[0]))
    n = len(rows)
    print(f"   patients with serial burden AND an outcome: {n:,}   "
          f"median span {np.median([r['span'] for r in rows]):.0f} h")
    if n < 80:
        print("   too few for the discrimination arms")
        return 0
    y = np.asarray([r["y"] for r in rows], float)
    if y.min() == y.max():
        print("   outcome has no variance")
        return 0
    one = np.ones(n)
    last = np.asarray([r["last"] for r in rows], float)
    mean = np.asarray([r["mean"] for r in rows], float)
    diff = np.asarray([r["last"] - r["first"] for r in rows], float)
    a_last = cv_auc(np.column_stack([one, last]), y, rng)
    a_mean = cv_auc(np.column_stack([one, mean]), y, rng)
    a_md = cv_auc(np.column_stack([one, mean, diff]), y, rng)
    print(f"\n   most recent reading alone   CV AUC {a_last:.3f}")
    print(f"   MEAN of the readings alone  CV AUC {a_mean:.3f}")
    print(f"   mean + difference           CV AUC {a_md:.3f}   increment {a_md-a_mean:+.3f}")
    print(f"   HEEDB gave most-recent 0.747 against mean 0.787.")
    print(f"   {'AVERAGE WINS -- fixed-quantity behaviour, as in HEEDB' if a_mean > a_last else 'MOST RECENT WINS -- state-like behaviour, UNLIKE HEEDB'}")

    beta = logit_fit(np.column_stack([one, mean, diff]), y)[2]
    bs = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            try:
                bs.append(float(logit_fit(np.column_stack([one[i], mean[i], diff[i]]), y[i])[2]))
            except Exception:
                continue
    lo, hi = np.percentile(bs, [2.5, 97.5]) if len(bs) > 100 else (float("nan"),) * 2
    print(f"\n   coefficient on the DIFFERENCE (log-odds): {beta:+.3f} [{lo:+.3f},{hi:+.3f}]")
    if lo <= 0 <= hi:
        print("   INDISTINGUISHABLE FROM ZERO -- the trajectory adds nothing once the mean is known, which")
        print("   is the identifying signature of a fixed quantity and reproduces the HEEDB result")
        print("   (+5.88 pp [-17.13, +26.58]) in an independent cohort with a different detector run by us.")
    else:
        print("   EXCLUDES ZERO -- the trajectory carries independent information here, which it did NOT in")
        print("   HEEDB. The mechanistic claim would then be cohort-specific and must be weakened.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
