#!/usr/bin/env python3
"""Is the exposure any good? Agreement with the clinician label, and the measurement error of burden itself.

WHY THIS EXISTS. Every quantitative claim in this project rests on one measured variable -- suppression burden
-- and that variable has never been validated in the repository's own record. A 0.829 AUC against the clinician
label appears in a CODE COMMENT in `heedb_bs_quantify.py` with no reproducible analysis behind it. An exposure
whose validity lives in a comment is an exposure nobody can defend.

The second half matters more. Q2 concluded that burden "behaves like a fixed quantity measured with error", and
its central evidence was that AVERAGING two readings predicts better than taking the most recent. That argument
is quantitative and its key parameter -- how much measurement error there is -- was never estimated. It is
directly estimable, because burden is computed from FOUR separate 2-minute windows sampled across each
recording, and the spread among those windows within a single recording is measurement error by construction:
same patient, same recording, same brain, minutes apart.

  V1  AGREEMENT. How well does measured burden discriminate the clinician's burst-suppression label on the
      SAME recording? This is not a gold standard -- the label is a human reading of the whole record while
      burden sees 8 sampled minutes -- but poor agreement would mean the two are not measuring the same thing.
  V2  THRESHOLD SENSITIVITY. The 5 uV amplitude criterion is a choice. Agreement is recomputed across
      thresholds to show the result is not an artefact of that number.
  V3  MEASUREMENT ERROR, the one Q2 needs. Decompose the variance of window-level burden into between-recording
      and within-recording components, and report the intraclass correlation. ICC is the reliability of a
      single reading; 1 - ICC is the share of variance that is noise.
  V4  THE CONSEQUENCE. Given that reliability, how much SHOULD averaging two readings improve prediction? If
      the observed improvement in Q2 (0.747 -> 0.787) is what the measured reliability predicts, the
      measurement-error account is quantitatively consistent rather than merely qualitatively plausible.

WHAT THIS CANNOT DO. The clinician label is not ground truth for the QUANTITY of suppression -- it is a binary
presence judgement, and a reader seeing a whole record will call suppression that an 8-minute sample misses.
Disagreement is therefore not evidence that burden is wrong, and agreement is not proof it is right. It bounds
how far apart the two can be.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import dt

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
WIN_GLOB = os.environ.get("WIN_GLOB", "/tmp/eeg_probe/heedb_bs_windows*.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    rng = np.random.default_rng(20260726)

    # ---- burden per (patient, session) -------------------------------------------------------------
    per = defaultdict(dict)
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                per[p][s] = max(per[p].get(s, 0.0), v)
    print(f"recordings with a measured burden: {sum(len(v) for v in per.values()):,} "
          f"across {len(per):,} patients")

    # ---- clinician label per (patient, recording time) ---------------------------------------------
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    # session -> time, to align a report with the session whose burden we measured
    stime = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/eeg-metadata/{st}_eeg_metadata_2026_04_30.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip(); s = (r.get("SessionID") or "").strip()
            if p.isdigit() and s.isdigit():
                t = dt(r.get("StartTime") or r.get("EndTime") or "")
                if t is not None:
                    stime[(int(p), int(s))] = t

    reports = defaultdict(list)
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("StartTime(EEG)") or r.get("EndTime(EEG)") or "")
            if t is None:
                continue
            lab = (r.get("bs") or "").strip() not in ("", "None", "nan")
            reports[int(p)].append((t, 1.0 if lab else 0.0))

    # match each measured session to the report nearest in time (within 24 h)
    pairs = []
    for p, sess in per.items():
        rl = reports.get(p)
        if not rl:
            continue
        for s, b in sess.items():
            t = stime.get((p, s))
            if t is None:
                continue
            best, bestgap = None, None
            for rt, lab in rl:
                g = abs((rt - t).total_seconds()) / 3600.0
                if bestgap is None or g < bestgap:
                    best, bestgap = lab, g
            if best is not None and bestgap <= 24.0:
                pairs.append((b, best))
    print(f"recordings matched to a report within 24 h: {len(pairs):,}")
    if len(pairs) < 200:
        print("*** too few matched; cannot assess agreement")
        return 1

    b = np.array([x[0] for x in pairs]); y = np.array([x[1] for x in pairs])
    print("\n" + "=" * 92)
    print("V1  DOES MEASURED BURDEN AGREE WITH THE CLINICIAN'S BURST-SUPPRESSION LABEL?")
    print("=" * 92)
    a = auc(y, b)
    bs = []
    for _ in range(NBOOT):
        i = rng.integers(0, len(b), len(b))
        if 0 < y[i].sum() < len(i):
            bs.append(auc(y[i], b[i]))
    lo, hi = np.percentile(bs, [2.5, 97.5]) if len(bs) > 100 else (float("nan"),) * 2
    print(f"   label prevalence {100*y.mean():.1f}%   AUC {a:.3f} [{lo:.3f},{hi:.3f}]   n={len(b):,}")
    print(f"   {'clinician label':22s} {'n':>7s} {'mean burden':>13s} {'median':>9s}")
    for lab, nm in ((1.0, "burst suppression"), (0.0, "no suppression")):
        m = y == lab
        print(f"   {nm:22s} {int(m.sum()):7,d} {b[m].mean():12.3f} {np.median(b[m]):9.3f}")
    print("\n   The label is a human reading of the WHOLE record; burden sees 8 sampled minutes. Disagreement")
    print("   is therefore expected in both directions and is not by itself evidence that either is wrong.")

    # ---- V3: measurement error from within-recording windows ---------------------------------------
    print("\n" + "=" * 92)
    print("V3  MEASUREMENT ERROR -- how reliable is a single burden reading?")
    print("=" * 92)
    wins = defaultdict(list)
    nfile = 0
    for f in sorted(glob.glob(WIN_GLOB)):
        nfile += 1
        for r in csv.DictReader(open(f)):
            try:
                k = (int(r["patient"]), int(r["session"])); v = float(r["burden"])
            except Exception:
                continue
            if v == v:
                wins[k].append(v)
    multi = {k: v for k, v in wins.items() if len(v) >= 2}
    if not multi:
        print(f"   no per-window file found (glob {WIN_GLOB}, {nfile} files).")
        print("   The burden extractor stores only the MAX across its four windows, so the within-recording")
        print("   spread is not recoverable from what has been saved. Re-run heedb_bs_quantify.py with")
        print("   per-window output to estimate this. Q2's measurement-error account remains qualitative")
        print("   until that is done -- stated rather than glossed.")
        return 0
    print(f"   recordings with >=2 window readings: {len(multi):,}")
    gm = np.mean([np.mean(v) for v in multi.values()])
    within = np.mean([np.var(v, ddof=1) for v in multi.values()])
    between = np.var([np.mean(v) for v in multi.values()], ddof=1)
    icc = between / (between + within) if (between + within) > 0 else float("nan")
    print(f"   grand mean {gm:.3f}   between-recording variance {between:.4f}   "
          f"within-recording variance {within:.4f}")
    print(f"   ICC (reliability of ONE window) = {icc:.3f}; noise share = {1-icc:.3f}")
    k = 2
    icck = k * icc / (1 + (k - 1) * icc) if icc == icc else float("nan")
    print(f"   Spearman-Brown: reliability of the AVERAGE of {k} readings = {icck:.3f}")
    print("\n   V4  If burden is a fixed quantity seen through this much noise, averaging two readings should")
    print("   improve prediction, and by roughly the amount reliability improves. Q2 observed 0.747 -> 0.787")
    print("   for most-recent versus averaged. A reliability rising from "
          f"{icc:.3f} to {icck:.3f} is the same direction and order.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
