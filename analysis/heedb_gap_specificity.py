#!/usr/bin/env python3
"""Is the 2x anoxia-vs-sepsis gap about BURST SUPPRESSION, about EEG, or about anoxia itself?

WHERE THIS SITS. The gap has now survived everything cheap: it is not depth, severity, age/sex, coexisting
findings, a ceiling artefact, persistence, burst morphology, the clinician's use of the label, or the withdrawal
window (which halves every aetiology and leaves the ratio at 2.14 -> 2.17). What has NOT been asked is whether
the gap is a property of burst suppression at all.

Three nested questions, cheapest first, each capable of reframing the finding.

  Q1  DO OTHER EEG FINDINGS SHOW THE SAME GAP? Generalized and lateralized periodic discharges, seizures and
      generalized slowing are all read off the same reports. If each of them is also ~2x more lethal after
      anoxia than in sepsis, then nothing here is about burst suppression: it is about EEG abnormality in
      general carrying more prognostic weight after anoxia. If burst suppression's ratio stands out, the
      finding is specific.
      This is the single most informative test available and it costs one pass over data already in hand.

  Q2  DO NON-EEG PREDICTORS SHOW THE SAME GAP? Age and comorbidity burden have nothing to do with the cortex.
      If they ALSO predict death about twice as strongly in anoxic as in septic patients, then the gap is a
      property of how outcome is distributed in these two populations -- a statistical feature of the cohorts,
      not a fact about the brain. This is the negative control the project has not had, and a positive result
      here would substantially deflate the headline.
      PREDICTION, registered: if the finding is real, non-EEG predictors should show a MUCH smaller
      anoxic:sepsis ratio than burst suppression does. FALSIFIED IF age or comorbidity burden shows a ratio
      comparable to burst suppression's ~2.0.

  Q3  IS THE EEG ORDERED DIFFERENTLY? Post-arrest EEG is protocolised and early; septic EEG is triggered by
      someone becoming worried. Different selection into the cohort could produce different prognostic value
      with no biological difference. Measured as the delay from the first dated aetiology diagnosis to the
      first EEG, and by how many EEGs each patient receives.
      This is descriptive -- it can show selection differs, not that selection causes the gap.

METHOD NOTE. Effects are unadjusted within-stratum differences in 30-day death, finding-positive minus
finding-negative, computed identically for every finding so the comparison across findings is like-for-like.
Ratios are bootstrapped so "2.04 versus 1.31" is not read off point estimates alone -- comparing two ratios by
eye is the comparison-of-significance error this project has committed repeatedly.
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
FINDINGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen, ncode, firstdx = defaultdict(set), set(), defaultdict(int), {}
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            ncode[p] += 1
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)
                    t = dt(r.get("condition_start_datetime"))
                    if t is not None:
                        key = (p, lab)
                        if key not in firstdx or t < firstdx[key]:
                            firstdx[key] = t

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
    when, find, age, nrep = {}, defaultdict(dict), {}, defaultdict(int)
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
            nrep[p] += 1
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
        rows.append(dict(pid=p, d30=1.0 if days <= 30 else 0.0, labs=aet.get(p, set()),
                         age=age.get(p, float("nan")), ncode=float(ncode.get(p, 0)),
                         nrep=float(nrep.get(p, 0)), t0=t0,
                         **{f: (1.0 if find[p].get(f) else 0.0) for f in FINDINGS}))
    n = len(rows)
    print(f"cohort: {n:,} patients with an ascertained death, an EEG time and condition data")

    def eff_ratio(flag_fn, label):
        """per-aetiology effect of a binary flag, plus a bootstrapped anoxic:sepsis ratio."""
        out = {}
        for k in ("anoxic", "sepsis"):
            g1 = [r["d30"] for r in rows if k in r["labs"] and flag_fn(r) == 1.0]
            g0 = [r["d30"] for r in rows if k in r["labs"] and flag_fn(r) == 0.0]
            if len(g1) < 25 or len(g0) < 25:
                return None
            out[k] = (float(np.mean(g1) - np.mean(g0)), len(g1), len(g0))
        ra = []
        idx = np.arange(n)
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            vals = {}
            ok = True
            for k in ("anoxic", "sepsis"):
                g1 = [r["d30"] for r in R if k in r["labs"] and flag_fn(r) == 1.0]
                g0 = [r["d30"] for r in R if k in r["labs"] and flag_fn(r) == 0.0]
                if len(g1) < 20 or len(g0) < 20:
                    ok = False; break
                vals[k] = float(np.mean(g1) - np.mean(g0))
            if ok and vals["sepsis"] > 0.02:
                ra.append(vals["anoxic"] / vals["sepsis"])
        lo, hi = (np.percentile(ra, [2.5, 97.5]) if len(ra) > 100 else (float("nan"),) * 2)
        r0 = out["anoxic"][0] / out["sepsis"][0] if out["sepsis"][0] > 0.02 else float("nan")
        print(f"   {label:22s} anoxic {100*out['anoxic'][0]:+7.2f}pp  sepsis {100*out['sepsis'][0]:+7.2f}pp"
              f"   ratio {r0:5.2f} [{lo:5.2f},{hi:5.2f}]")
        return r0, lo, hi

    print("\n" + "=" * 92)
    print("Q1  DO OTHER EEG FINDINGS SHOW THE SAME GAP?  (if they all do, this is not about burst suppression)")
    print("=" * 92)
    res = {}
    for f in FINDINGS:
        r = eff_ratio(lambda r, f=f: r[f], f)
        if r:
            res[f] = r

    print("\n" + "=" * 92)
    print("Q2  NEGATIVE CONTROL -- DO NON-EEG PREDICTORS SHOW THE SAME GAP?")
    print("=" * 92)
    ages = np.array([r["age"] for r in rows if r["age"] == r["age"]])
    amed = float(np.median(ages)) if len(ages) else 65.0
    cmed = float(np.median([r["ncode"] for r in rows]))
    print(f"   (age split at median {amed:.0f}; comorbidity split at median {cmed:.0f} condition rows)")
    eff_ratio(lambda r: 1.0 if (r["age"] == r["age"] and r["age"] > amed) else 0.0, "age above median")
    eff_ratio(lambda r: 1.0 if r["ncode"] > cmed else 0.0, "comorbidity above median")

    if "bs" in res:
        print(f"\n   Burst suppression's ratio is {res['bs'][0]:.2f} [{res['bs'][1]:.2f},{res['bs'][2]:.2f}].")
        print("   Q2 is FALSIFIED if a non-EEG predictor shows a comparable ratio -- that would mean the gap is a")
        print("   property of these two populations' outcome structure rather than a fact about the brain.")

    print("\n" + "=" * 92)
    print("Q3  IS THE EEG ORDERED DIFFERENTLY?  (protocolised after arrest vs triggered in sepsis)")
    print("=" * 92)
    print(f"   {'aetiology':12s} {'n':>6s} {'median days dx->EEG':>21s} {'% same day':>11s} {'median EEGs':>12s}")
    for k in ("anoxic", "sepsis", "metabolic", "structural", "status"):
        g = [r for r in rows if k in r["labs"] and (r["pid"], k) in firstdx]
        if len(g) < 50:
            continue
        dl = np.array([(r["t0"] - firstdx[(r["pid"], k)]).total_seconds() / 86400.0 for r in g])
        print(f"   {k:12s} {len(g):6d} {np.median(dl):20.1f} {100*np.mean(np.abs(dl)<=1):10.1f}% "
              f"{np.median([r['nrep'] for r in g]):11.0f}")
    print("\n   Descriptive: this can show that selection into the EEG cohort differs, not that it causes the gap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
