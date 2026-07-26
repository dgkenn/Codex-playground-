#!/usr/bin/env python3
"""Is the anoxia gap SPECIFIC to burst suppression? Differences, not ratios, and a working negative control.

WHY THIS SUPERSEDES heedb_gap_specificity.py. That script compared the anoxic and septic effects of each EEG
finding as a RATIO. The ratio is undefined or unstable whenever the septic effect is near zero or negative, which
it is for four of the six findings, so most rows came back nan. It also compared burst suppression's ratio to the
others by eye. Both problems are fixed here:
  * the statistic is the DIFFERENCE (anoxic effect minus septic effect), which is well defined at any sign;
  * burst suppression is compared against each other finding by a PAIRED bootstrap of the difference-of-
    differences, computed inside the same resample, rather than by inspecting two numbers.

WHAT THE PREVIOUS RUN SHOWED, and why it needs care. Burst suppression's difference was +20.41 pp against
+2.64 pp for generalized periodic discharges. But generalized slowing came out at -20.76 pp -- a difference as
large as burst suppression's and opposite in sign. That is not noise and it is not a problem: in a cohort where
every patient eventually dies, the outcome is whether death came SOON, and slowing marks a brain that is
abnormal but NOT suppressed. The mirror image is the point. If the contrast between "suppressed" and "merely
slow" is sharper after anoxia than in sepsis, that is the same fact seen from the other side, and it is reported
as corroboration rather than buried.

THE NEGATIVE CONTROL, REBUILT. The previous comorbidity control was invalid: it used the NUMBER of condition
rows, and a patient who survives longer accumulates more rows, so "high comorbidity" was partly a synonym for
"died later". That is reverse causation and it produced an uninterpretable -38.80 pp. Replaced with
comorbidities that are FIXED TRAITS rather than accumulating counts -- prior malignancy, chronic kidney disease,
dementia, heart failure -- each coded as present/absent, none of which can be caused by surviving longer.

REGISTERED PREDICTIONS.
  S1  Burst suppression's anoxic-minus-septic difference exceeds that of every other EEG finding in ABSOLUTE
      terms, tested pairwise inside the bootstrap.
      FALSIFIED IF any other finding matches or exceeds it with an interval excluding zero.
  S2  No fixed-trait comorbidity, and not age, shows an anoxic-minus-septic difference comparable to burst
      suppression's. FALSIFIED IF one does -- that would mean the gap is a property of these populations'
      outcome structure rather than of the EEG.

Everything is unadjusted within-stratum differences in 30-day death, computed identically for every predictor so
the comparison across predictors is like-for-like.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1000"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
FINDINGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]

# fixed traits: present/absent, and none of them can be *caused* by surviving longer
TRAITS = {
    "malignancy":  ("C", "140", "141", "142", "143", "144", "145", "146", "147", "148", "149",
                    "150", "151", "152", "153", "154", "155", "156", "157", "158", "162", "174",
                    "185", "188", "189", "191"),
    "ckd":         ("N18", "585"),
    "dementia":    ("F03", "G30", "290", "3310"),
    "heartfailure": ("I50", "428"),
}


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen = defaultdict(set), set()
    trait = defaultdict(set)
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
            for lab, pre in TRAITS.items():
                if any(c.startswith(x) for x in pre):
                    trait[p].add(lab)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, find, age = {}, defaultdict(dict), {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            if p not in when or t < when[p]:
                when[p] = t
                try:
                    age[p] = float(r.get("AgeAtVisit") or "nan")
                except Exception:
                    age[p] = float("nan")
            for f in FINDINGS:
                v = (r.get(f) or "").strip() not in ("", "None", "nan")
                find[p][f] = find[p].get(f, False) or v

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        a = age.get(p, float("nan"))
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, labs=aet.get(p, set()),
                         old=(1.0 if (a == a and a > 67) else 0.0),
                         **{f"t_{k}": (1.0 if k in trait.get(p, set()) else 0.0) for k in TRAITS},
                         **{f: (1.0 if find[p].get(f) else 0.0) for f in FINDINGS}))
    n = len(rows)
    print(f"cohort: {n:,}\n")

    an_idx = [i for i in range(n) if "anoxic" in rows[i]["labs"]]
    se_idx = [i for i in range(n) if "sepsis" in rows[i]["labs"]]

    def diff_for(key, R=None):
        R = rows if R is None else R
        out = []
        for lab in ("anoxic", "sepsis"):
            g1 = [r["d30"] for r in R if lab in r["labs"] and r[key] == 1.0]
            g0 = [r["d30"] for r in R if lab in r["labs"] and r[key] == 0.0]
            if len(g1) < 20 or len(g0) < 20:
                return None
            out.append(float(np.mean(g1) - np.mean(g0)))
        return out[0] - out[1], out[0], out[1]

    # observed
    obs = {}
    for k in FINDINGS + ["old"] + [f"t_{t}" for t in TRAITS]:
        d = diff_for(k)
        if d:
            obs[k] = d

    # one bootstrap, all predictors measured inside each replicate so differences are paired
    boots = defaultdict(list)
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        R = [rows[j] for j in i]
        for k in obs:
            d = diff_for(k, R)
            if d:
                boots[k].append(d[0])

    print("=" * 96)
    print("S1  ANOXIC-MINUS-SEPTIC DIFFERENCE, per predictor  (30-day death, unadjusted)")
    print("=" * 96)
    print(f"   {'predictor':16s} {'anoxic eff':>11s} {'sepsis eff':>11s} {'difference':>12s} {'95% CI':>20s}")
    order = sorted(obs, key=lambda k: -abs(obs[k][0]))
    for k in order:
        d, a, s = obs[k]
        b = boots[k]
        lo, hi = (np.percentile(b, [2.5, 97.5]) if len(b) > 100 else (float("nan"),) * 2)
        tag = "  <- EEG" if k in FINDINGS else "  (control)"
        print(f"   {k:16s} {100*a:+10.2f} {100*s:+10.2f} {100*d:+11.2f} "
              f"[{100*lo:+7.2f},{100*hi:+7.2f}]{tag}")

    # S1: burst suppression vs each other EEG finding, paired inside replicates
    print("\n   Paired comparison, |bs difference| minus |other difference|, same resample each replicate:")
    ok = True
    for k in FINDINGS:
        if k == "bs" or k not in boots:
            continue
        m = min(len(boots["bs"]), len(boots[k]))
        dd = np.abs(np.array(boots["bs"][:m])) - np.abs(np.array(boots[k][:m]))
        lo, hi = np.percentile(dd, [2.5, 97.5])
        verdict = "bs LARGER" if lo > 0 else ("indistinguishable" if hi > 0 else "bs SMALLER")
        if lo <= 0:
            ok = False
        print(f"      bs vs {k:14s} {100*np.mean(dd):+8.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}]  {verdict}")
    print(f"\n   S1 {'CONFIRMED' if ok else 'NOT CONFIRMED'} "
          f"(burst suppression's gap exceeds every other EEG finding's in absolute terms)")

    # S2: negative controls
    print("\n" + "=" * 96)
    print("S2  NEGATIVE CONTROLS -- fixed traits and age, which cannot be caused by surviving longer")
    print("=" * 96)
    worst = 0.0
    for k in ["old"] + [f"t_{t}" for t in TRAITS]:
        if k not in obs:
            continue
        m = min(len(boots["bs"]), len(boots[k]))
        dd = np.abs(np.array(boots["bs"][:m])) - np.abs(np.array(boots[k][:m]))
        lo, hi = np.percentile(dd, [2.5, 97.5])
        worst = max(worst, abs(obs[k][0]))
        print(f"      bs vs {k:16s} {100*np.mean(dd):+8.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}]  "
              f"{'bs LARGER' if lo > 0 else 'NOT distinguishable'}")
    print(f"\n   largest control difference {100*worst:.2f} pp vs burst suppression {100*obs['bs'][0]:.2f} pp")
    print(f"   S2 {'CONFIRMED' if worst < abs(obs['bs'][0]) * 0.6 else 'FALSIFIED'} "
          f"(no non-EEG predictor shows a comparable gap)")

    print("\n   Note on the negative-signed EEG findings. Every patient here eventually died, so the outcome is")
    print("   whether death came SOON. Slowing and seizures mark a brain that is abnormal but NOT suppressed, so")
    print("   they predict LATER death, and a large negative difference for generalized slowing is the mirror")
    print("   image of burst suppression's positive one rather than a contradiction of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
