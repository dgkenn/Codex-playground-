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

OUTCOME (2026-07-26): THE QUESTION IS NOT ANSWERABLE FROM THE AVAILABLE PAIRS, and the first run of this script
said otherwise. J2 came back +0.064 and printed "CONFIRMED (reversible)". It is not. Two things kill it:

  * THE INTERVAL. Median gap between a patient's first two recordings is **0.65 days**, p90 1.69 days, with only
    57 pairs two or more days apart. These are two recordings in the same admission, hours apart -- not recovery
    trajectories. The structural-versus-reversible question needs days, and this extraction has too few such
    pairs to ask it.
  * THE NOISE CONTROL (J2b, added after). `level + change` is algebraically `first level + second level`, so a
    second measurement helps whenever the measure is noisy, biology or no biology. Reversibility predicts the
    increment GROWS with the interval. It does not: **+0.065 under 12 hours, +0.055 at 12 h to 2 days** -- flat,
    and largest where no cortex could have recovered. That is measurement error and recency, not reversibility.

J3 fell the same way. Unstratified it was incoherent (improvers died MORE often than stable patients, opposite
to J1) because the strata compared baselines rather than trajectories. Stratified by index level, improving does
beat worsening in the mid and high strata -- but that is exactly what REGRESSION TO THE MEAN produces: a patient
whose first reading was noise-high appears to improve and also has a lower true burden.

So: J1 holds and is small; J2 is refuted by its own control; J3 is confounded. The verdict lines below were
rewritten so the script can no longer print a bare "CONFIRMED (reversible)". Revisit when the serial extraction
yields enough pairs separated by days.

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
# Minimum days between the index recording and its comparison. 0 reproduces the original
# first-two-recordings behaviour (median interval 0.65 d, which cannot answer the question).
MIN_GAP_D = float(os.environ.get("MIN_GAP_D", "2"))
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
        # PAIR SELECTION. The first version took a patient's first TWO recordings, which gave a median interval
        # of 0.65 days -- two reads in the same admission, hours apart. Nothing about structural versus
        # reversible injury can be asked over fourteen hours. Recordings are ordered by TIME and the comparison
        # recording is the EARLIEST one at least MIN_GAP_D days after the index, so the interval is chosen to be
        # long enough for the question rather than whatever happened to come next.
        timed = sorted(((stime[(p, s)], s) for s in sess if (p, s) in stime), key=lambda x: x[0])
        if len(timed) < 2:
            continue
        t1, s1 = timed[0]
        pick = next(((t, s) for t, s in timed[1:]
                     if MIN_GAP_D <= (t - t1).total_seconds() / 86400.0 <= 21), None)
        if pick is None:
            continue                               # no recording in the usable interval window
        t2, s2 = pick
        b1, b2 = sess[s1], sess[s2]
        if d < t2:
            continue                               # LANDMARK: must be alive at the comparison recording
        gap_d = (t2 - t1).total_seconds() / 86400.0
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
    print(f"   J2 increment {c2-c1:+.3f} against a +0.03 threshold -- but this number CANNOT be read as")
    print("   reversibility on its own. `level + change` is algebraically `first level + second level`, and a")
    print("   second measurement beats one whenever the measure is noisy, with no biology involved. J2b below")
    print("   is the control that decides it; do not quote J2 without J2b.")

    # ---- J2b: THE NOISE CONTROL, without which J2 proves nothing --------------------------------------
    # `level + change` is algebraically `b1 + b2`, and two measurements beat one whenever the measurement is
    # noisy -- with no biology involved at all. The way to tell them apart is the INTERVAL. Over a few hours a
    # cortex cannot meaningfully recover, so any increment at short gaps is measurement error and recency, not
    # reversibility. Only an increment that GROWS with the interval is evidence of real change.
    print("\n" + "=" * 92)
    print("J2b  IS THE INCREMENT BIOLOGY, OR JUST A SECOND LOOK AT A NOISY MEASURE?")
    print("=" * 92)
    gaps = np.array([r["gap"] for r in rows], float)
    print(f"   interval between recordings: median {np.median(gaps):.2f} d   "
          f"p25 {np.percentile(gaps,25):.2f}   p75 {np.percentile(gaps,75):.2f}   "
          f"p90 {np.percentile(gaps,90):.2f}")
    print(f"   {'interval band':22s} {'n':>5s} {'level':>8s} {'level+change':>13s} {'increment':>10s}")
    for lab, lo, hi in (("under 12 hours", 0.0, 0.5), ("12 h to 2 days", 0.5, 2.0),
                        ("2 to 21 days", 2.0, 1e9)):
        g = [r for r in rows if lo <= r["gap"] < hi]
        if len(g) < 80:
            print(f"   {lab:22s} {len(g):5d}   too few")
            continue
        yy = np.asarray([r["d30"] for r in g], float)
        if yy.min() == yy.max():
            continue
        A = np.column_stack([np.ones(len(g)), np.asarray([r["b1"] for r in g], float)])
        B = np.column_stack([A, np.asarray([r["db"] for r in g], float)])
        ca, cb = cv_auc(A, yy, rng), cv_auc(B, yy, rng)
        print(f"   {lab:22s} {len(g):5d} {ca:8.3f} {cb:13.3f} {cb-ca:+10.3f}")
    print("\n   REVERSIBLE predicts the increment GROWS with the interval -- more time, more real change to see.")
    print("   MEASUREMENT NOISE predicts it is FLAT or largest at short gaps, where no biology has had time to")
    print("   happen. A large increment under 12 hours is not recovery.")

    # ---- J2c: THE FIXED-COHORT CONTROL, which separates interval from selection ----------------------
    # Sweeping MIN_GAP_D shows J1 decaying to nothing and the J2 increment shrinking as the interval grows.
    # That is what measurement noise predicts and what recovery does not. But there is one alternative: a
    # longer gap requires SURVIVING to the later recording, so the long-gap cohort is a lower-risk, more
    # homogeneous group, and attenuation could be selection rather than interval.
    # This control removes that entirely by holding the PATIENTS fixed. Among patients who have BOTH a
    # short-interval and a long-interval comparison recording, the same people are measured twice, so any
    # difference between the two is the interval and cannot be the cohort.
    print("\n" + "=" * 92)
    print("J2c  SAME PATIENTS, SHORT INTERVAL vs LONG INTERVAL")
    print("=" * 92)
    both = []
    for p, sess in multi.items():
        d = death.get(p)
        if d is None:
            continue
        timed = sorted(((stime[(p, s)], s) for s in sess if (p, s) in stime), key=lambda x: x[0])
        if len(timed) < 3:
            continue
        t1, s1 = timed[0]
        sh = next(((t, s) for t, s in timed[1:] if (t - t1).total_seconds() / 86400.0 <= 0.5), None)
        lg = next(((t, s) for t, s in timed[1:] if 2.0 <= (t - t1).total_seconds() / 86400.0 <= 21.0), None)
        if sh is None or lg is None or d < lg[0]:
            continue                                  # landmark at the LATER of the two comparison points
        both.append(dict(b1=sess[s1], bs=sess[sh[1]], bl=sess[lg[1]],
                         d30=1.0 if (d - lg[0]).days <= 30 else 0.0))
    print(f"   patients with BOTH a <=12 h and a 2-21 d comparison recording: {len(both):,}")
    if len(both) >= 100:
        yy = np.asarray([r["d30"] for r in both], float)
        if yy.min() < yy.max():
            A = np.column_stack([np.ones(len(both)), np.asarray([r["b1"] for r in both], float)])
            Bs = np.column_stack([A, np.asarray([r["bs"] - r["b1"] for r in both], float)])
            Bl = np.column_stack([A, np.asarray([r["bl"] - r["b1"] for r in both], float)])
            ca, cs, cl = cv_auc(A, yy, rng), cv_auc(Bs, yy, rng), cv_auc(Bl, yy, rng)
            print(f"   index level alone                       CV AUC {ca:.3f}")
            print(f"   + change over <=12 h (no time to heal)  CV AUC {cs:.3f}   increment {cs-ca:+.3f}")
            print(f"   + change over 2-21 d (time to heal)     CV AUC {cl:.3f}   increment {cl-ca:+.3f}")
            print(f"   mean |change| short {np.mean([abs(r['bs']-r['b1']) for r in both]):.3f}   "
                  f"long {np.mean([abs(r['bl']-r['b1']) for r in both]):.3f}")
            print("\n   CAUTION -- this comparison is NOT clean, and the direction of its unfairness is known.")
            print("   The long-interval recording IS the landmark, so its level is contemporaneous with the")
            print("   moment the outcome starts being counted, while the short-interval recording is days")
            print("   stale. Recency alone favours the long row. J2d below removes that by conditioning on")
            print("   the most recent level, which is the only recency-neutral form of the question.")

            # ---- J2d: THE RECENCY-NEUTRAL TEST ---------------------------------------------------
            # Every framing so far confounded trajectory with recency: `level + change` is `old level + new
            # level`, so it wins whenever the newer measurement is better, which it trivially is. Condition
            # on the MOST RECENT level instead and ask whether knowing where the patient CAME FROM adds
            # anything. That is exactly the structural/reversible distinction with recency removed:
            #   STRUCTURAL -- the current state is the injury; history adds nothing once you know it.
            #   REVERSIBLE -- a cortex at burden 0.4 on the way DOWN differs from one at 0.4 on the way UP,
            #                 so history adds beyond the current level.
            print("\n" + "=" * 92)
            print("J2d  DOES TRAJECTORY ADD BEYOND THE MOST RECENT LEVEL?  (recency-neutral)")
            print("=" * 92)
            C = np.column_stack([np.ones(len(both)), np.asarray([r["bl"] for r in both], float)])
            D = np.column_stack([C, np.asarray([r["bl"] - r["b1"] for r in both], float)])
            cc, cd = cv_auc(C, yy, rng), cv_auc(D, yy, rng)
            print(f"   most recent level alone                 CV AUC {cc:.3f}")
            print(f"   most recent level + where it came from  CV AUC {cd:.3f}   increment {cd-cc:+.3f}")
            print("\n   STRUCTURAL predicts an increment near zero: the current state IS the injury, and the")
            print("   path taken to reach it carries no extra information. REVERSIBLE predicts a clear")
            print("   positive increment. This is the form of the question that recency cannot fake.")
    else:
        print("   too few patients have both; inconclusive at current extraction depth")

    # ---- J3: resolution ------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("J3  DOES RESOLUTION MATTER BEYOND THE LEVEL?")
    print("=" * 92)
    # STRATIFIED BY INDEX LEVEL, because the unstratified version is uninterpretable. Patients who "improve"
    # are overwhelmingly patients who STARTED HIGH -- there is nowhere to improve from at a low burden -- and
    # patients who are "stable" include everyone sitting quietly at a low burden. Comparing those groups
    # compares baselines, not trajectories, which is why the naive table showed improvers dying MORE often than
    # stable patients while J1 said the opposite. The question is only meaningful within a level.
    print(f"   {'index burden':>14s} {'trajectory':26s} {'n':>5s} {'30-day death':>13s} {'90-day death':>13s}")
    b1s = np.array([r["b1"] for r in rows], float)
    cuts = np.percentile(b1s, [33, 67])
    for tlab, tsel in (("low", b1s <= cuts[0]),
                       ("mid", (b1s > cuts[0]) & (b1s <= cuts[1])),
                       ("high", b1s > cuts[1])):
        strat = [r for r, x in zip(rows, tsel) if x]
        for lab, sel in (("improved (change < -0.05)", lambda r: r["db"] < -0.05),
                         ("stable (|change| <= 0.05)", lambda r: abs(r["db"]) <= 0.05),
                         ("worsened (change > +0.05)", lambda r: r["db"] > 0.05)):
            g = [r for r in strat if sel(r)]
            if len(g) < 20:
                continue
            print(f"   {tlab:>14s} {lab:26s} {len(g):5d} {100*np.mean([r['d30'] for r in g]):12.1f}% "
                  f"{100*np.mean([r['d90'] for r in g]):12.1f}%")
    print("\n   J3 is supported only if improving beats worsening WITHIN a level. Across levels the comparison")
    print("   is between baselines, not trajectories.")
    print("\n   AND EVEN WITHIN A LEVEL IT IS CONFOUNDED, by regression to the mean. A patient whose FIRST")
    print("   reading was high by measurement noise will appear to 'improve' on remeasurement and also has a")
    print("   lower true burden, so does better -- reproducing 'improving beats worsening' with no recovery")
    print("   anywhere in the causal chain. Read together with J2b, which shows the increment is largest at")
    print("   intervals too short for biology, that is the more parsimonious reading of this whole table.")

    print("\n   Everything here is landmarked at the second recording, because a patient must survive to have")
    print("   one -- using trajectory without that would manufacture a predictor out of immortal time, which is")
    print("   the trap that made an earlier persistence analysis in this project uninterpretable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
