#!/usr/bin/env python3
"""WHY does burst suppression mean different things in different aetiologies? Test 1: REVERSIBILITY.

THE PUZZLE. docs/research/39_HEEDB_FINDINGS.md establishes THAT suppression's prognostic weight depends on
aetiology (interaction spread 38.51 pp [32.84,44.63]; anoxic +23.59 pp, sepsis -14.92 pp) but not WHY. The
dose-response result sharpens the puzzle rather than solving it: the burden->death SLOPE differs by aetiology
(D1, section 6b), so this is not simply "anoxic patients suppress more deeply". The same measured amount of
suppression genuinely carries different information depending on the cause.

THE CANDIDATE MECHANISM. Suppression is a final common pathway reachable two ways:
  * PHARMACOLOGICAL / METABOLIC -- a cortex that is being suppressed by something removable (sedative, toxin,
    hepatic or renal failure, hypothermia). Remove the cause and the cortex comes back. The EEG is reporting a
    condition of the milieu, not of the tissue.
  * STRUCTURAL -- a cortex that is suppressed because its neurons are dying or dead, as after global anoxia.
    Nothing is removable. The EEG is reporting the tissue itself.
If that is right, the two are distinguishable ON THE EEG, over time, without knowing the diagnosis: the first
RESOLVES and the second PERSISTS. And the aetiology interaction would then be a proxy for reversibility --
aetiology predicts outcome only because it predicts whether the suppression is the removable kind.

REGISTERED PREDICTIONS, committed before the models are fit.
  M1  Persistence differs by aetiology: HIGHEST in anoxic, LOWEST in sepsis and metabolic.
      FALSIFIED IF anoxic is not the highest, or the spread across aetiologies covers zero.
  M2  Persistence predicts death from the landmark, strongly and independently of aetiology.
      FALSIFIED IF the coefficient covers zero.
  M3  THE MECHANISM TEST. Conditioning on persistence SHRINKS the aetiology interaction. If reversibility is
      what aetiology is standing in for, the interaction spread should attenuate substantially once persistence
      is in the model. Reported as a PAIRED bootstrap of (spread_without - spread_with), because "it looks
      smaller" is not a test and this project has made that error four times.
      FALSIFIED IF the paired difference covers zero -- that would mean reversibility is NOT what the aetiology
      interaction is carrying, and the mechanism must be sought elsewhere (burst morphology is the next
      candidate: post-anoxic "identical bursts" are stereotyped where drug-induced bursts are variable).

THE TRAP THIS DESIGN EXISTS TO AVOID. Persistence is measured on a LATER EEG, so a patient who dies quickly
cannot be observed to resolve. Naively, "persistent" would then be partly a synonym for "died", and M2/M3 would
be guaranteed by construction rather than by biology. This is immortal-time / informative-censoring bias and it
would manufacture exactly the result being looked for.
  THE FIX: a LANDMARK design. Everyone must be alive and still under observation at the follow-up EEG, which is
  where persistence is assessed; the outcome clock starts THERE, not at the index EEG. Every patient in the
  analysis has therefore survived the same qualifying period by construction, and the comparison is between
  patients who were all alive at the moment the exposure was measured.

REMAINING LIMITS, stated in advance.
  * Conditioning on a post-baseline variable (M3) is a mediation-style analysis and inherits its assumptions --
    an unmeasured common cause of persistence and death would bias it. This is an explanatory decomposition, not
    a causal mediation claim, and it is reported as such.
  * Why a repeat EEG was ordered is not random. Patients who improve may stop being monitored, which would make
    resolution under-observed in exactly the patients doing best.
  * "Resolved" is a clinician's reading of a later report, carrying the same reader heterogeneity as the index
    label. The burden detector is not run here; that is the follow-up if M3 confirms.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
MIN_GAP_H = float(os.environ.get("MIN_GAP_H", "12"))    # follow-up EEG must be this far after index
MAX_GAP_D = float(os.environ.get("MAX_GAP_D", "7"))     # ...and within this many days
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def reports():
    """patient -> sorted [(time, bs_present)] across both sites."""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    out = defaultdict(list)
    for site in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            bs = (r.get("bs") or "").strip() not in ("", "None", "nan")
            out[int(p)].append((t, bs))
    for p in out:
        out[p].sort()
    return out


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen = defaultdict(set), set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    rep = reports()
    keys = list(AETIOLOGY)
    rows, drop = [], defaultdict(int)
    for p, v in rep.items():
        if p not in cond_seen:
            drop["no condition data"] += 1
            continue
        idx = next((i for i, (t, b) in enumerate(v) if b), None)
        if idx is None:
            continue                              # never had burst suppression
        t_idx = v[idx][0]
        fu = next(((t, b) for t, b in v[idx + 1:]
                   if MIN_GAP_H * 3600 <= (t - t_idx).total_seconds() <= MAX_GAP_D * 86400), None)
        if fu is None:
            drop["no qualifying follow-up EEG"] += 1
            continue
        t_fu, bs_fu = fu
        d = death.get(p)
        # LANDMARK: must be alive at the follow-up EEG. Everyone here survived the same qualifying period,
        # so persistence cannot be a synonym for having died early.
        if d is not None and d < t_fu:
            drop["died before the follow-up EEG"] += 1
            continue
        if d is None:
            drop["no ascertained death"] += 1
            continue                              # ascertainment-immune, as everywhere else in this project
        days = (d - t_fu).days
        if days < -1:
            drop["death precedes landmark"] += 1
            continue
        labs = aet.get(p, set())
        rows.append(dict(persist=1.0 if bs_fu else 0.0,
                         d30=1.0 if days <= 30 else 0.0,
                         gap_d=(t_fu - t_idx).total_seconds() / 86400.0,
                         **{k: (1.0 if k in labs else 0.0) for k in keys}))
    print("cohort construction:")
    for k, val in sorted(drop.items(), key=lambda x: -x[1]):
        print(f"   dropped, {k:30s} {val:,}")
    n = len(rows)
    print(f"\nLANDMARK COHORT: {n:,} patients with burst suppression, a follow-up EEG "
          f"{MIN_GAP_H:.0f} h-{MAX_GAP_D:.0f} d later, alive at that EEG, and an ascertained death")
    if n < 300:
        print("*** insufficient"); return 1
    pers = np.asarray([r["persist"] for r in rows], float)
    y = np.asarray([r["d30"] for r in rows], float)
    print(f"   persistent suppression: {100*pers.mean():.1f} %   died within 30 d of landmark: {100*y.mean():.1f} %")

    expo = [k for k in keys if sum(r[k] for r in rows) >= 30]

    # ---- M1: does persistence differ by aetiology? --------------------------------------------------
    print("\n=== M1: probability that suppression PERSISTS, by aetiology (LPM) ===")
    Xp = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
    bp = lpm(Xp, pers)
    bootp = defaultdict(list); sp = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            b2 = lpm(Xp[i], pers[i])
        except Exception:
            continue
        for j in range(1, len(expo) + 1):
            bootp[j].append(b2[j])
        sp.append(float(max(b2[1:]) - min(b2[1:])))
    for j, k in enumerate(expo, 1):
        lo, hi = np.percentile(bootp[j], [2.5, 97.5])
        print(f"   {k:12s} {100*bp[j]:+7.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(sp, [2.5, 97.5])
    top = expo[int(np.argmax(bp[1:len(expo)+1]))]
    print(f"   spread {100*(max(bp[1:len(expo)+1])-min(bp[1:len(expo)+1])):.2f} pp "
          f"[{100*lo:.2f},{100*hi:.2f}]   highest: {top}")
    print(f"   M1 {'CONFIRMED' if (top == 'anoxic' and lo > 0) else 'FALSIFIED'} "
          f"(predicted anoxic highest, spread excluding zero)")

    # ---- M2 + M3: does persistence carry the outcome, and does it absorb the interaction? -----------
    def design(R, with_persist):
        m = len(R)
        cols = [np.ones(m)]
        for k in expo:
            cols.append(np.asarray([r[k] for r in R], float))
        if with_persist:
            cols.append(np.asarray([r["persist"] for r in R], float))
        return np.column_stack(cols)

    yv = np.asarray([r["d30"] for r in rows], float)
    Xw = design(rows, True)
    bw = lpm(Xw, yv)
    print(f"\n=== M2: persistence -> 30-day death from the landmark (adjusted for aetiology) ===")
    bootq = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            bootq.append(lpm(Xw[i], yv[i])[-1])
        except Exception:
            continue
    lo, hi = np.percentile(bootq, [2.5, 97.5])
    print(f"   persistent suppression {100*bw[-1]:+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")
    print(f"   M2 {'CONFIRMED' if lo > 0 else 'FALSIFIED'}")

    # aetiology spread with and without persistence, differenced INSIDE each replicate
    Xo = design(rows, False)
    bo = lpm(Xo, yv)
    s_wo = float(max(bo[1:len(expo)+1]) - min(bo[1:len(expo)+1]))
    s_w = float(max(bw[1:len(expo)+1]) - min(bw[1:len(expo)+1]))
    dif = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            a = lpm(Xo[i], yv[i]); b = lpm(Xw[i], yv[i])
        except Exception:
            continue
        dif.append((max(a[1:len(expo)+1]) - min(a[1:len(expo)+1]))
                   - (max(b[1:len(expo)+1]) - min(b[1:len(expo)+1])))
    lo, hi = np.percentile(dif, [2.5, 97.5])
    print(f"\n=== M3: does persistence ABSORB the aetiology spread? ===")
    print(f"   aetiology spread WITHOUT persistence : {100*s_wo:.2f} pp")
    print(f"   aetiology spread WITH persistence    : {100*s_w:.2f} pp")
    print(f"   attenuation, paired bootstrap        : {100*(s_wo-s_w):+.2f} pp "
          f"[{100*lo:+.2f},{100*hi:+.2f}] {'*' if lo > 0 else 'ns'}")
    print(f"   proportion of the spread explained   : {100*(s_wo-s_w)/max(s_wo,1e-9):.1f} %")
    print(f"   M3 {'CONFIRMED' if lo > 0 else 'FALSIFIED'}")
    if lo <= 0:
        print("   -> reversibility is NOT what the aetiology interaction is carrying. Next candidate is burst")
        print("      MORPHOLOGY: post-anoxic bursts are stereotyped ('identical bursts') where drug-induced")
        print("      bursts are variable, and that is measurable on the raw EDF we already read.")

    print("\n   Conditioning on a post-baseline variable inherits mediation assumptions; an unmeasured common")
    print("   cause of persistence and death would bias M3. This is an explanatory decomposition, not a causal")
    print("   mediation claim. Why a repeat EEG was ordered is also not random.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
