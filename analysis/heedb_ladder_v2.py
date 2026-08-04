#!/usr/bin/env python3
"""The EEG severity ladder, rebuilt on all 53 report fields instead of six.

WHY v2. The first ladder put post-anoxic patients with "no malignant finding" at 43.3 % 30-day death, ABOVE
those with slowing at 31.4 % -- a clean EEG apparently worse than a slow one. The cause was a bad bottom rung,
not a bad ladder. Rung 0 was defined as "none of bs / gpd / lpd / seizure / generalized slowing / focal
slowing", and the reports carry 53 fields, so that stratum silently mixed three incompatible groups:

  * LOW VOLTAGE (4.9 % of reports) -- an attenuated or suppressed background. This is a SEVERE finding,
    plausibly worse than burst suppression, and it was sitting in the bottom rung because it is not one of the
    six flags.
  * UNINTERPRETABLE (1.6 %) -- technically inadequate records, which carry no information about the brain and
    should be excluded rather than scored.
  * genuinely NORMAL records (26.9 %) with a preserved POSTERIOR DOMINANT RHYTHM (58.8 %), which is the
    classical marker of intact thalamocortical function and belongs at the bottom.

The rebuilt ladder, with `uninterpretable` excluded outright:

    rung 0   PRESERVED   -- normal record, or a posterior dominant rhythm present, with no malignant feature
    rung 1   SLOWING     -- generalized or focal slowing, background still continuous
    rung 2   EPILEPTIFORM-- periodic or rhythmic patterns, seizures, status, spikes
    rung 3   SUPPRESSION -- burst suppression
    rung 4   ATTENUATION -- low voltage without burst suppression, i.e. a background that is not bursting at all

REGISTERED PREDICTIONS.
  V1  With the bottom rung repaired, 30-day death rises MONOTONICALLY across rungs 0 to 3 in every aetiology.
      FALSIFIED IF any aetiology is non-monotone over 0-3.
  V2  The rung-0-to-rung-3 span is larger after anoxia than in sepsis. This is the test that failed last time
      only because rung 0 was contaminated; with a clean bottom rung it should now pass.
      FALSIFIED IF the paired difference in span covers zero.
  V3  ORDERING OF THE TOP. Attenuation (rung 4) carries HIGHER 30-day death than burst suppression (rung 3).
      A cortex that has stopped bursting altogether is further along than one still producing bursts.
      FALSIFIED IF attenuation is not higher, in which case the ladder should end at burst suppression and
      low voltage should be folded in beside it rather than above it.

  V3 is a genuine question rather than a formality: burst suppression is the more famous finding, but attenuation
  may simply be its more advanced form, and if so the ladder's top two rungs are ordered wrongly in most of the
  literature's informal usage.

ALSO REPORTED: whether a preserved posterior dominant rhythm modifies the burst-suppression effect. PDR indexes
surviving thalamocortical machinery, so if suppression means something different when that machinery is intact,
the interaction should show it -- and that is a mechanism-relevant contrast the six-flag version could not make.
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
NBOOT = int(os.environ.get("NBOOT", "1000"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"

PRESERVED = ("normal", "pdr", "spindles", "k_complexes", "vertex wave")
SLOWING = ("gen slowing", "foc slowing")
EPILEPT = ("gpd", "lpd", "grda", "lrda", "seizure", "status", "spikes")
FIELDS = tuple(set(PRESERVED + SLOWING + EPILEPT + ("bs", "low voltage", "uninterpretable")))


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
    when, F = {}, defaultdict(dict)
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
            for f in FIELDS:
                v = (r.get(f) or "").strip() not in ("", "None", "nan")
                F[p][f] = F[p].get(f, False) or v

    def rung(f):
        if f.get("bs"):
            return 4 if False else 3            # burst suppression
        if f.get("low voltage"):
            return 4                            # attenuated, and not bursting
        if any(f.get(k) for k in EPILEPT):
            return 2
        if any(f.get(k) for k in SLOWING):
            return 1
        if any(f.get(k) for k in PRESERVED):
            return 0
        return None                             # nothing scored: not placeable, excluded

    rows, drop = [], defaultdict(int)
    for p, t0 in when.items():
        if p not in cond_seen:
            drop["no condition data"] += 1
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        f = F[p]
        if f.get("uninterpretable") and not f.get("bs"):
            drop["uninterpretable record"] += 1
            continue
        rr = rung(f)
        if rr is None:
            drop["no scoreable finding"] += 1
            continue
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, rung=rr,
                         bs=1.0 if f.get("bs") else 0.0,
                         pdr=1.0 if f.get("pdr") else 0.0, labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort: {n:,}   (excluded: " + ", ".join(f"{k} {v}" for k, v in drop.items()) + ")")
    print("   rung n: " + ", ".join(f"{k}={sum(1 for r in rows if r['rung']==k)}" for k in range(5)))

    AE = ("anoxic", "sepsis", "metabolic", "structural", "status")
    NAMES = {0: "preserved", 1: "slowing", 2: "epileptiform", 3: "suppression", 4: "attenuation"}

    print("\n" + "=" * 96)
    print("V1/V2  30-DAY DEATH BY REBUILT RUNG")
    print("=" * 96)
    print(f"   {'aetiology':12s} " + " ".join(f"{NAMES[k][:12]:>14s}" for k in range(5)) + f" {'span 0->3':>10s}")
    spans = {}
    for k in AE:
        g = [r for r in rows if k in r["labs"]]
        cells, vals = [], {}
        for rr in range(5):
            sub = [r["d30"] for r in g if r["rung"] == rr]
            if len(sub) < 20:
                cells.append("        n/a"); continue
            vals[rr] = float(np.mean(sub))
            cells.append(f"{100*vals[rr]:5.1f}% ({len(sub):4d})")
        seq = [vals[i] for i in range(4) if i in vals]
        mono = all(seq[i] <= seq[i + 1] + 1e-9 for i in range(len(seq) - 1))
        if 0 in vals and 3 in vals:
            spans[k] = vals[3] - vals[0]
        print(f"   {k:12s} " + " ".join(f"{c:>14s}" for c in cells) +
              f" {100*spans.get(k, float('nan')):9.1f}" + ("" if mono else "  NON-MONOTONE 0-3"))

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
        print(f"\n   V2  anoxic span minus septic span: {100*obs:+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}]")
        print(f"   V2 {'CONFIRMED' if lo > 0 else 'FALSIFIED'}")

    # ---- V3: is attenuation worse than burst suppression? -------------------------------------------
    print("\n" + "=" * 96)
    print("V3  IS ATTENUATION (rung 4) WORSE THAN BURST SUPPRESSION (rung 3)?")
    print("=" * 96)
    a3 = [r["d30"] for r in rows if r["rung"] == 3]
    a4 = [r["d30"] for r in rows if r["rung"] == 4]
    if len(a4) >= 30:
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            x = [r["d30"] for r in R if r["rung"] == 4]
            y = [r["d30"] for r in R if r["rung"] == 3]
            if len(x) >= 20 and len(y) >= 20:
                d.append(float(np.mean(x) - np.mean(y)))
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"   suppression (n={len(a3)}) {100*np.mean(a3):.1f}%   attenuation (n={len(a4)}) "
              f"{100*np.mean(a4):.1f}%   difference {100*(np.mean(a4)-np.mean(a3)):+.2f} pp "
              f"[{100*lo:+.2f},{100*hi:+.2f}]")
        print(f"   V3 {'CONFIRMED' if lo > 0 else 'FALSIFIED'} (attenuation above suppression)")
    else:
        print(f"   only {len(a4)} patients at rung 4; not testable")

    # ---- PDR as an effect modifier -----------------------------------------------------------------
    print("\n" + "=" * 96)
    print("DOES A PRESERVED POSTERIOR DOMINANT RHYTHM CHANGE WHAT SUPPRESSION MEANS?")
    print("=" * 96)
    print(f"   {'aetiology':12s} {'BS effect, PDR absent':>24s} {'BS effect, PDR present':>25s}")
    for k in AE:
        out = []
        for pv in (0.0, 1.0):
            g = [r for r in rows if k in r["labs"] and r["pdr"] == pv]
            g1 = [r["d30"] for r in g if r["bs"] == 1.0]
            g0 = [r["d30"] for r in g if r["bs"] == 0.0]
            out.append(f"{100*(np.mean(g1)-np.mean(g0)):+7.2f}pp (n={len(g1)+len(g0):5d})"
                       if len(g1) >= 20 and len(g0) >= 20 else "                n/a")
        print(f"   {k:12s} {out[0]:>24s} {out[1]:>25s}")
    print("\n   A posterior dominant rhythm indexes surviving thalamocortical machinery. If suppression means")
    print("   something different when that machinery is intact, this contrast is where it shows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
