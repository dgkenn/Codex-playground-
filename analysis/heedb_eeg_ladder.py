#!/usr/bin/env python3
"""Are burst suppression and generalized slowing two findings, or two rungs of one ladder?

WHAT PROMPTED THIS. Measuring each EEG finding separately produced a mirror image: burst suppression's
anoxic-minus-septic difference was +20.41 pp, and generalized slowing's was -20.76 pp -- equally large and
opposite in sign. Treating those as two unrelated findings misses the obvious reading. Every patient in this
cohort eventually died, so the outcome is whether death came SOON, and the findings sit on a natural severity
ordering:

    rung 0   no malignant finding
    rung 1   slowing only            -- an abnormal but continuously active cortex
    rung 2   periodic discharges or seizures -- abnormal and hyperexcitable
    rung 3   burst suppression       -- an intermittently silent cortex

On that reading there is one phenomenon, not two: HOW FAR UP THE LADDER the EEG sits predicts how soon death
comes, and the question is whether the rungs are more widely spaced after anoxia than in sepsis. Slowing looks
"protective" only because it is a LOW rung -- being merely slow means not being suppressed.

This matters for how the finding is presented. A single ordinal severity scale with a per-rung risk is a
clinically usable object and an explainable one; two findings with opposite signs is a puzzle nobody can act on.

REGISTERED PREDICTIONS.
  L1  Within every aetiology, 30-day death rises monotonically across rungs 0 -> 3.
      FALSIFIED IF any aetiology shows a non-monotone sequence outside sampling noise.
  L2  The ladder is STEEPER after anoxia: the rung-0-to-rung-3 span is larger in anoxic than septic patients.
      FALSIFIED IF the paired difference in span covers zero.
  L3  THE UNIFICATION TEST. The ladder position should account for most of what the separate burst-suppression
      and slowing analyses were each capturing. Operationally: after conditioning on rung, the residual
      anoxic-vs-septic difference in the burst-suppression effect should shrink substantially.
      FALSIFIED IF conditioning on rung absorbs less than 50 % of burst suppression's +20.41 pp gap. The
      threshold is stated as a fraction because a significance-only criterion has twice passed here on a
      trivial effect (docs/LESSONS.md).

ALSO REPORTED: the contrast that the ladder makes precise -- among patients who have SOME abnormality, does
being suppressed rather than merely slow carry more weight after anoxia? That is the clinically sharp version of
the whole project's question.

CAVEAT. The rungs are assigned from clinician report flags, not from a graded quantitative scale, and a patient
sits at their highest rung across all reports. Ordering rung 2 above rung 1 is a judgement: periodic discharges
are conventionally read as more malignant than slowing, but that ordering is assumed here, not derived. The
monotonicity test in L1 is partly a check on whether the assumed ordering is right.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1000"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def rung_of(f):
    if f.get("bs"):
        return 3
    if f.get("gpd") or f.get("lpd") or f.get("seizure"):
        return 2
    if f.get("gen slowing") or f.get("foc slowing"):
        return 1
    return 0


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

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    FL = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]
    when, find = {}, defaultdict(dict)
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
            for f in FL:
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
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, rung=rung_of(find[p]),
                         bs=1.0 if find[p].get("bs") else 0.0, labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort: {n:,}")
    print("   rung distribution: " + ", ".join(
        f"{k}={sum(1 for r in rows if r['rung']==k)}" for k in (0, 1, 2, 3)))

    AE = ("anoxic", "sepsis", "metabolic", "structural", "status")

    # ---- L1 / L2 ------------------------------------------------------------------------------------
    print("\n" + "=" * 84)
    print("L1/L2  30-DAY DEATH BY EEG SEVERITY RUNG  (0 none, 1 slowing, 2 discharges/seizure, 3 suppression)")
    print("=" * 84)
    print(f"   {'aetiology':12s} {'rung0':>13s} {'rung1':>13s} {'rung2':>13s} {'rung3':>13s} {'span 0->3':>11s}")
    spans = {}
    for k in AE:
        g = [r for r in rows if k in r["labs"]]
        if len(g) < 200:
            continue
        cells, ok = [], True
        vals = []
        for rr in (0, 1, 2, 3):
            sub = [r["d30"] for r in g if r["rung"] == rr]
            if len(sub) < 20:
                cells.append("     n/a"); vals.append(None); continue
            v = float(np.mean(sub))
            vals.append(v)
            cells.append(f"{100*v:5.1f}% ({len(sub):4d})")
        seq = [v for v in vals if v is not None]
        mono = all(seq[i] <= seq[i + 1] + 1e-9 for i in range(len(seq) - 1))
        if vals[0] is not None and vals[3] is not None:
            spans[k] = vals[3] - vals[0]
        print(f"   {k:12s} " + " ".join(f"{c:>13s}" for c in cells) +
              f" {100*spans.get(k, float('nan')):10.1f}" + ("" if mono else "   NON-MONOTONE"))

    # bootstrap the anoxic-vs-septic span difference, paired inside replicates
    def span_for(R, k):
        g = [r for r in R if k in r["labs"]]
        a = [r["d30"] for r in g if r["rung"] == 0]
        b = [r["d30"] for r in g if r["rung"] == 3]
        if len(a) < 20 or len(b) < 20:
            return None
        return float(np.mean(b) - np.mean(a))
    dd = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        R = [rows[j] for j in i]
        sa, ss = span_for(R, "anoxic"), span_for(R, "sepsis")
        if sa is not None and ss is not None:
            dd.append(sa - ss)
    if dd:
        lo, hi = np.percentile(dd, [2.5, 97.5])
        obs = spans.get("anoxic", float("nan")) - spans.get("sepsis", float("nan"))
        print(f"\n   L2  anoxic span minus septic span: {100*obs:+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}]")
        print(f"   L2 {'CONFIRMED' if lo > 0 else 'FALSIFIED'} (ladder steeper after anoxia)")

    # ---- L3: does rung absorb the burst-suppression gap? --------------------------------------------
    print("\n" + "=" * 84)
    print("L3  DOES LADDER POSITION ABSORB THE BURST-SUPPRESSION GAP?")
    print("=" * 84)

    def bs_gap(R, conditional):
        """anoxic minus septic BS effect; if conditional, computed WITHIN rungs 2 and 3 only (i.e. comparing
        suppressed against the adjacent malignant rung rather than against everything below it)."""
        out = []
        for k in ("anoxic", "sepsis"):
            g = [r for r in R if k in r["labs"]]
            if conditional:
                g = [r for r in g if r["rung"] >= 2]
            g1 = [r["d30"] for r in g if r["bs"] == 1.0]
            g0 = [r["d30"] for r in g if r["bs"] == 0.0]
            if len(g1) < 20 or len(g0) < 20:
                return None
            out.append(float(np.mean(g1) - np.mean(g0)))
        return out[0] - out[1]

    raw, cond = bs_gap(rows, False), bs_gap(rows, True)
    br, bc = [], []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        R = [rows[j] for j in i]
        a, b = bs_gap(R, False), bs_gap(R, True)
        if a is not None and b is not None:
            br.append(a); bc.append(b)
    if raw is not None and cond is not None and br:
        d = np.array(br) - np.array(bc)
        lo, hi = np.percentile(d, [2.5, 97.5])
        frac = (raw - cond) / raw if raw > 0.01 else float("nan")
        print(f"   burst-suppression gap, vs ALL lower rungs      : {100*raw:+.2f} pp")
        print(f"   burst-suppression gap, vs the ADJACENT rung only: {100*cond:+.2f} pp")
        print(f"   absorbed by ladder position: {100*frac:.1f} %  "
              f"(attenuation {100*(raw-cond):+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}])")
        print(f"   L3 {'CONFIRMED' if (frac >= 0.50 and lo > 0) else 'FALSIFIED'} "
              f"(registered threshold: 50 %)")

    # ---- the sharp clinical contrast ---------------------------------------------------------------
    print("\n" + "=" * 84)
    print("SUPPRESSED vs MERELY SLOW -- the contrast the ladder makes precise")
    print("=" * 84)
    print(f"   {'aetiology':12s} {'rung1 slowing':>16s} {'rung3 suppressed':>18s} {'difference':>12s}")
    for k in AE:
        g = [r for r in rows if k in r["labs"]]
        a = [r["d30"] for r in g if r["rung"] == 1]
        b = [r["d30"] for r in g if r["rung"] == 3]
        if len(a) < 20 or len(b) < 20:
            continue
        print(f"   {k:12s} {100*np.mean(a):14.1f}% {100*np.mean(b):16.1f}% "
              f"{100*(np.mean(b)-np.mean(a)):+11.1f}pp")
    print("\n   Rungs are assigned from clinician flags and ordering rung 2 above rung 1 is an assumption,")
    print("   not a derivation; L1's monotonicity check is partly a test of whether that ordering is right.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
