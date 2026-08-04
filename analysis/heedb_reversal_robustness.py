#!/usr/bin/env python3
"""Does the aetiology reversal survive its own two biggest internal weaknesses?

THE LEAD (R389–R392): intra-burst 8–30 Hz content ranks 30-day death in opposite directions by aetiology --
AUC 0.589 [0.545, 0.633] anoxic versus 0.408 [0.364, 0.452] non-anoxic. It survives burden strata (3/3),
burst-count strata (3/3) and decomposition of the non-anoxic arm (4/4). Three weaknesses were recorded with
it. One -- external replication -- needs a mixed-aetiology cohort and **TUH is unreachable from this sandbox**
(no rsync binary, no NEDC key), so it must wait for a machine that has them. The other two are testable here
and are what this file does.

------------------------------------------------------------------------------------------------------------
WEAKNESS 1 -- EVERY ESTIMATE CONDITIONS ON AN ASCERTAINED DEATH RECORD (limit L3).

The cohort is built by requiring `p in death`, so **every patient in it eventually died**. The outcome is
therefore "died within 30 days" versus "died later", not death versus survival. That is a real question, but
it is not the question a reader will assume, and death ascertainment in this database runs 40.1–61.9 % by
aetiology -- so the conditioning is differential in exactly the variable the finding is about.

  W1  Rebuild the outcome without that conditioning: patients with **no death record are treated as alive**,
      and the outcome becomes 30-day death in the full cohort with a measurable burst morphology.
      CONFIRMED IF the reversal survives -- anoxic above 0.5, non-anoxic below, both intervals excluding it.
      FALSIFIED IF it collapses, in which case the finding is about time-to-death among decedents and must be
      described that way.

      THE TRADE, stated because neither version is clean: treating an absent record as survival imports the
      ascertainment problem from the other side. A patient may be alive, or merely unascertained. **The point
      is not that W1 is the correct analysis -- it is that the two analyses have opposite biases, so a result
      appearing in both is not an artefact of either.**

------------------------------------------------------------------------------------------------------------
WEAKNESS 2 -- AETIOLOGY COMES FROM ICD CODES, AND THIS PROJECT HAS ALREADY HAD TO CORRECT ITS ICD DEFINITIONS
ONCE. The whole finding is an aetiology contrast, so it should not rest on one code list.

The `anoxic` list mixes two clinically distinct things: codes for the **arrest event** (4275, I460, I461,
I469, 42741) and codes for the **resulting encephalopathy** (3481, G931, 7991, P916). If the reversal is real
it should appear under both, since both identify the same patients by different routes.

  W2  Recompute the contrast with anoxia defined by arrest codes ONLY, and again by encephalopathy codes ONLY.
      CONFIRMED IF both sub-definitions show AUC above 0.5 with the non-anoxic remainder below it.
      FALSIFIED IF only one does -- then the finding is about whichever code family carries it, which is a
      narrower and differently-interpretable claim.

REGISTERED CONCLUSION RULE, fixed before running: the lead is strengthened only if W1 confirms AND both arms
of W2 confirm. Partial confirmation is reported as partial, and the ledger entry says which arm failed.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
CACHE = os.environ.get("ANOX_SPLIT_CACHE", "/tmp/eeg_probe/heedb_anoxic_split.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))

ARREST = ("4275", "42741", "I460", "I461", "I469")          # the arrest event
ENCEPH = ("3481", "G931", "7991", "P916")                   # the resulting encephalopathy


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def median_by_patient(pattern, col):
    import glob
    d = defaultdict(list)
    for path in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r[col])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                d[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in d.items()}


def anoxic_split():
    """Per patient: does any condition code match the arrest family, the encephalopathy family, or neither?"""
    if os.path.exists(CACHE):
        out = {}
        for r in csv.DictReader(open(CACHE)):
            out[int(r["pid"])] = (r["arrest"] == "1", r["enceph"] == "1")
        return out
    from heedb_bs_ascertainment import norm
    out = {}
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            a, e = out.get(p, (False, False))
            c = norm(r.get("condition_source_value"))
            if c:
                if any(c.startswith(x) for x in ARREST):
                    a = True
                if any(c.startswith(x) for x in ENCEPH):
                    e = True
            out[p] = (a, e)
    with open(CACHE, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "arrest", "enceph"])
        for p, (a, e) in out.items():
            w.writerow([p, 1 if a else 0, 1 if e else 0])
    return out


def auc_ci(y, s, rng, reps):
    n = len(y); o = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                o.append(a)
    if len(o) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(o, [2.5, 97.5]))


def arm(name, y, a, ax, rng):
    """Report the contrast and say whether it straddles 0.5 with both intervals excluding it."""
    out = {}
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        if k < 80 or not (0 < y[m].sum() < k):
            print(f"      {lab:<11} n={k:>5}  too few")
            return None
        A = auc(y[m], a[m]); lo, hi = auc_ci(y[m], a[m], rng, NBOOT)
        out[lab] = (A, lo, hi)
        print(f"      {lab:<11} n={k:>5}  30-d death {100*y[m].mean():5.1f}%  AUC {A:.3f} [{lo:.3f},{hi:.3f}]"
              f"  {'-> MORE death' if A > 0.5 else '-> LESS death'}")
    an, no = out["anoxic"], out["non-anoxic"]
    strict = an[1] > 0.5 and no[2] < 0.5
    loose = (an[0] - 0.5) * (no[0] - 0.5) < 0
    print(f"      {name}: {'CONFIRMED -- both intervals exclude 0.5 on opposite sides' if strict else ('directionally opposite but at least one interval spans 0.5' if loose else 'NOT reversed')}")
    return strict


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            p = int(p)
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    split = anoxic_split()
    ab = median_by_patient(MORPH, "alpha_beta")
    assert ab and split, "feature or aetiology table empty"

    # everyone with a measurable burst morphology and an EEG time -- no death conditioning
    rows = []
    for p, v in ab.items():
        if p not in when:
            continue
        d = death.get(p)
        if d is not None and (d - when[p]).days < -1:
            continue
        arrest, enceph = split.get(p, (False, False))
        rows.append((p, d, v, arrest, enceph))
    assert len(rows) >= 400, f"only {len(rows)} patients"

    dead30 = np.array([1.0 if (r[1] is not None and (r[1] - when[r[0]]).days <= 30) else 0.0 for r in rows])
    has_rec = np.array([1.0 if r[1] is not None else 0.0 for r in rows])
    a = np.array([r[2] for r in rows])
    arrest = np.array([1.0 if r[3] else 0.0 for r in rows])
    enceph = np.array([1.0 if r[4] else 0.0 for r in rows])
    anox = ((arrest == 1) | (enceph == 1)).astype(float)

    print(f"full cohort with a measurable burst morphology: {len(rows):,}")
    print(f"   with a death record: {int(has_rec.sum()):,} ({100*has_rec.mean():.1f}%)   "
          f"anoxic by either code family: {int(anox.sum()):,}")
    print(f"   death-record ascertainment: anoxic {100*has_rec[anox==1].mean():.1f}%  "
          f"non-anoxic {100*has_rec[anox==0].mean():.1f}%   <- the differential that motivates W1")

    print("\n" + "=" * 96)
    print("W1  WITHOUT DEATH-ASCERTAINMENT CONDITIONING (no record treated as alive)")
    print("=" * 96)
    w1 = arm("W1", dead30, a, anox, rng)

    print("\n   for comparison, the ORIGINAL conditioning (decedents only, 30-day vs later death):")
    m = has_rec == 1
    arm("original", dead30[m], a[m], anox[m], rng)

    print("\n" + "=" * 96)
    print("W2  TWO INDEPENDENT ROUTES TO 'ANOXIC' -- arrest codes versus encephalopathy codes")
    print("=" * 96)
    print(f"   arrest-coded {int(arrest.sum()):,}   encephalopathy-coded {int(enceph.sum()):,}   "
          f"both {int(((arrest==1)&(enceph==1)).sum()):,}")
    res = {}
    for lab, flag in (("ARREST codes only", arrest), ("ENCEPHALOPATHY codes only", enceph)):
        # compare that family against patients with NEITHER family (rule 29: decompose inside not-A)
        keep = (flag == 1) | (anox == 0)
        print(f"\n   {lab}  (versus patients with neither code family, n={int((anox==0).sum()):,})")
        res[lab] = arm(lab, dead30[keep], a[keep], flag[keep], rng)

    print("\n" + "=" * 96)
    print("VERDICT AGAINST THE RULE FIXED BEFORE RUNNING")
    print("=" * 96)
    ok = bool(w1) and all(bool(v) for v in res.values())
    print(f"   W1 confirmed: {bool(w1)}    W2 arrest: {bool(res.get('ARREST codes only'))}    "
          f"W2 encephalopathy: {bool(res.get('ENCEPHALOPATHY codes only'))}")
    print(f"   {'STRENGTHENED -- the reversal survives both of its testable internal weaknesses' if ok else 'PARTIAL -- see which arm failed above; the ledger entry must say so'}")
    print("\n   Neither test addresses the remaining weakness: external replication needs a mixed-aetiology")
    print("   cohort, and TUH is unreachable from this sandbox (no rsync, no NEDC key).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
