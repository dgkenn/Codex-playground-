#!/usr/bin/env python3
"""Does suppression burden RECOVER? The sharpest available probe of structural versus reversible injury.

THE QUESTION. Measured burden stratifies three-day death inside the guideline's highly-malignant category from
24.7 % to 66.4 %, and the organ-injury test showed it is a brain-specific marker rather than a proxy for
whole-body ischaemic dose. What it is a marker OF remains open, and the two candidates differ in a way that
serial recordings can settle:

  STRUCTURAL LOSS. Burden measures how much cortex has died. Dead tissue does not come back, so burden should be
  STABLE OR RISING on repeat recordings, and its trajectory should carry little information beyond its level --
  the damage is already done and the first measurement already saw it.

  REVERSIBLE FAILURE. Burden measures a depth of metabolic or pharmacological suppression that a surviving
  cortex is passing through. Then burden should FALL in patients who go on to survive, and the CHANGE should
  carry information the level does not.

REGISTERED PREDICTIONS.
  J1  Among post-anoxic burst-suppression patients with two or more recordings, burden falls more in those who
      survive longer.
      FALSIFIED IF the change in burden is unrelated to subsequent survival.
  J2  THE DISCRIMINATING ONE. Change in burden adds discrimination for death OVER the index level, by at least
      +0.03 cross-validated AUC, in a landmark design starting at the second recording.
      STRUCTURAL PREDICTS a small or absent increment: the level already contains the information.
      REVERSIBLE PREDICTS a substantial one.
  J3  Direction matters more than magnitude: patients whose burden RESOLVES (falls below a fixed low threshold)
      should have markedly better survival than those whose burden persists, beyond what their index level
      predicts.

THE TRAP, and the design that avoids it. A patient must survive to have a second recording, so anything derived
from that recording is unavailable to those who died first -- immortal time, and it would manufacture a powerful
spurious predictor. EVERYTHING here is therefore landmarked at the SECOND recording: the cohort is patients
alive at that point, and the outcome is death measured FROM that point forward. The index level is included as a
covariate so the question is genuinely about the increment from trajectory.

This is the same trap that made an earlier persistence analysis in this project uninterpretable until it was
landmarked, and the same one that forced persistence out of the three-day discrimination model entirely.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
SERIAL = os.environ.get("SERIAL_GLOB", "/tmp/eeg_probe/heedb_serial_morph*.csv")


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


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
            if y[tr].sum() < 5 or y[te].sum() < 3:
                continue
            try:
                out.append(auc(y[te], X[te] @ lpm(X[tr], y[tr])))
            except Exception:
                continue
    return float(np.nanmean(out)) if out else float("nan")


def main():
    rng = np.random.default_rng(20260726)

    # serial burden, keyed by (patient, session) so recordings can be ordered
    per = defaultdict(dict)
    for f in sorted(glob.glob(SERIAL)):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"]); sess = int(r["session"]); v = float(r["burden"])
            except Exception:
                continue
            if v == v:
                per[p][sess] = v
    print(f"patients with serial burden measurements: {len(per):,}")
    multi = {p: v for p, v in per.items() if len(v) >= 2}
    print(f"   with two or more recordings measured: {len(multi):,}")
    if len(multi) < 150:
        print("*** serial extraction still running or too sparse; rerun when it completes")
        return 1

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    # session -> timestamp, so the interval between recordings is known
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    stime = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/eeg-metadata/{st}_eeg_metadata_2026_04_30.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            s = (r.get("SessionID") or "").strip()
            if not p.isdigit() or not s.isdigit():
                continue
            t = dt(r.get("StartTime") or r.get("EndTime") or "")
            if t is not None:
                stime[(int(p), int(s))] = t

    rows = []
    for p, sess in multi.items():
        d = death.get(p)
        if d is None:
            continue
        order = sorted(sess)
        t1 = stime.get((p, order[0])); t2 = stime.get((p, order[1]))
        b1, b2 = sess[order[0]], sess[order[1]]
        if t1 is None or t2 is None or t2 <= t1:
            continue
        if d < t2:
            continue                               # LANDMARK: must be alive at the second recording
        gap_d = (t2 - t1).total_seconds() / 86400.0
        if gap_d > 21:
            continue                               # a recording three weeks later is a different question
        days_from_2 = (d - t2).days
        rows.append(dict(pid=p, b1=b1, b2=b2, db=b2 - b1, gap=gap_d,
                         d30=1.0 if days_from_2 <= 30 else 0.0,
                         d90=1.0 if days_from_2 <= 90 else 0.0,
                         days=float(days_from_2)))
    n = len(rows)
    print(f"\nLANDMARK COHORT (alive at the second recording, recordings <=21 d apart): {n:,}")
    if n < 120:
        print("*** insufficient"); return 1
    print(f"   median interval between recordings: {np.median([r['gap'] for r in rows]):.1f} d")
    print(f"   burden at recording 1: {np.mean([r['b1'] for r in rows]):.3f}   "
          f"at recording 2: {np.mean([r['b2'] for r in rows]):.3f}   "
          f"mean change {np.mean([r['db'] for r in rows]):+.3f}")

    # ---- J1: does burden fall more in those who survive longer? -------------------------------------
    print("\n" + "=" * 92)
    print("J1  DOES BURDEN FALL IN PATIENTS WHO SURVIVE LONGER?")
    print("=" * 92)
    print(f"   {'outcome from recording 2':30s} {'n':>5s} {'burden 1':>10s} {'burden 2':>10s} {'change':>9s}")
    for lab, sel in (("died within 30 days", lambda r: r["d30"] == 1.0),
                     ("survived past 30 days", lambda r: r["d30"] == 0.0),
                     ("survived past 90 days", lambda r: r["d90"] == 0.0)):
        g = [r for r in rows if sel(r)]
        if len(g) < 25:
            continue
        print(f"   {lab:30s} {len(g):5d} {np.mean([r['b1'] for r in g]):9.3f} "
              f"{np.mean([r['b2'] for r in g]):9.3f} {np.mean([r['db'] for r in g]):+8.3f}")
    a = [r["db"] for r in rows if r["d30"] == 1.0]
    b = [r["db"] for r in rows if r["d30"] == 0.0]
    if len(a) >= 25 and len(b) >= 25:
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            x = [r["db"] for r in R if r["d30"] == 1.0]; y2 = [r["db"] for r in R if r["d30"] == 0.0]
            if len(x) >= 15 and len(y2) >= 15:
                d.append(float(np.mean(x) - np.mean(y2)))
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"\n   change in burden, died minus survived: {np.mean(a)-np.mean(b):+.3f} "
              f"[{lo:+.3f},{hi:+.3f}]")
        print(f"   J1 {'CONFIRMED' if lo > 0 else 'FALSIFIED'} (burden falls more in those who survive)")

    # ---- J2: does the CHANGE add over the LEVEL? ----------------------------------------------------
    print("\n" + "=" * 92)
    print("J2  DOES THE CHANGE ADD DISCRIMINATION OVER THE INDEX LEVEL?")
    print("=" * 92)
    y = np.asarray([r["d30"] for r in rows], float)
    X1 = np.column_stack([np.ones(n), np.asarray([r["b1"] for r in rows], float)])
    X2 = np.column_stack([X1, np.asarray([r["db"] for r in rows], float)])
    X3 = np.column_stack([np.ones(n), np.asarray([r["b2"] for r in rows], float)])
    c1, c2, c3 = cv_auc(X1, y, rng), cv_auc(X2, y, rng), cv_auc(X3, y, rng)
    print(f"   index level alone          CV AUC {c1:.3f}")
    print(f"   index level + change       CV AUC {c2:.3f}   increment {c2-c1:+.3f}")
    print(f"   second-recording level alone CV AUC {c3:.3f}")
    print(f"   J2 {'CONFIRMED (reversible)' if c2 - c1 >= 0.03 else 'FALSIFIED (structural)'} "
          f"(threshold +0.03)")

    # ---- J3: resolution ------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("J3  DOES RESOLUTION MATTER BEYOND THE LEVEL?")
    print("=" * 92)
    print(f"   {'trajectory':34s} {'n':>5s} {'30-day death':>13s} {'90-day death':>13s}")
    for lab, sel in (("resolved (burden 2 < 0.05)", lambda r: r["b2"] < 0.05),
                     ("improved but not resolved", lambda r: r["b2"] >= 0.05 and r["db"] < -0.05),
                     ("stable (|change| <= 0.05)", lambda r: abs(r["db"]) <= 0.05),
                     ("worsened (change > +0.05)", lambda r: r["db"] > 0.05)):
        g = [r for r in rows if sel(r)]
        if len(g) < 20:
            continue
        print(f"   {lab:34s} {len(g):5d} {100*np.mean([r['d30'] for r in g]):12.1f}% "
              f"{100*np.mean([r['d90'] for r in g]):12.1f}%")

    print("\n   Everything here is landmarked at the second recording, because a patient must survive to have")
    print("   one -- using trajectory without that would manufacture a predictor out of immortal time, which is")
    print("   the trap that made an earlier persistence analysis in this project uninterpretable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
