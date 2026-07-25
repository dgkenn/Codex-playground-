#!/usr/bin/env python3
"""RED-TEAM: is the aetiology-mortality spread an artefact of differential DEATH ASCERTAINMENT?

THE THREAT. The primary analysis codes a patient as having died if a death record exists in the OMOP death table,
and as having survived otherwise. Absence of a record is NOT proof of survival — it may mean the patient died
outside the health system, or was lost to follow-up. If recording completeness differs by aetiology, that alone
manufactures a mortality spread. And there is every reason to think it does: patients who arrest die in hospital
and get recorded, whereas patients admitted for status epilepticus may be discharged and die elsewhere years later
without a linked record. Note the direction — that specific bias would inflate anoxic mortality and deflate status
mortality, which is EXACTLY the pattern the primary analysis found (+13.02 pp anoxic, -9.95 pp status). The threat
is not hypothetical; it predicts the observed result.

THE TEST, which is immune to it by construction. Restrict to patients who ALL have an ascertained death, and ask a
question about TIMING rather than occurrence:

        among patients with a recorded death, did they die within N days of the EEG?

Every patient in this analysis has the same ascertainment status, so differential recording cannot contribute.
What is being compared is how QUICKLY patients died, not whether a death was captured. If aetiology still
separates outcomes here, the spread is real. If it vanishes, the primary result was an ascertainment artefact and
must be withdrawn.

This design was used earlier in this project for the same reason and is the reason it was available to reuse.

SECOND CHECK, reported alongside: ascertainment rate BY AETIOLOGY. If the proportion of patients with any death
record is roughly constant across aetiologies, the threat is small regardless. If it varies widely, the primary
analysis is compromised even where this timing analysis survives, and both facts belong in the write-up.

Outcome thresholds are pre-specified at 30 and 90 days. Inference: patient-level bootstrap, linear probability
model (collapsible risk differences), heterogeneity summarised as the max-min spread exactly as in the primary.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
rng = np.random.default_rng(20260725)

AETIOLOGY = {
    "anoxic": ("4275", "V1253", "34982", "G931", "I469", "I461", "I460", "P916", "7991", "42741"),
    "status": ("34561", "34571", "3453", "G4101", "G411", "G412", "G419", "G40901"),
    "metabolic": ("5722", "5728", "K7290", "K7291", "5849", "N179", "N19", "27989", "E870",
                  "2765", "7902", "E162", "27651"),
    "sepsis": ("0389", "99591", "99592", "A419", "R6520", "R6521", "3200", "3229", "G039", "A879", "G049"),
    "structural": ("85400", "8540", "S069", "43191", "431", "432", "I619", "I620", "I629",
                   "43491", "I6350", "I639", "80000", "S0690"),
}


def norm(c):
    return (c or "").replace(".", "").strip().upper()


def dt(s):
    if not s:
        return None
    s = s.strip()
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], f)
        except Exception:
            pass
    return None


def eeg_times():
    """patient -> earliest EEG time carrying a burst-suppression label."""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    C = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
    out = {}
    for site in ("S0001", "S0002"):
        key = f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
        try:
            txt = s3.get_object(Bucket=C, Key=key)["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {site}: {type(e).__name__}"); continue
        for r in csv.DictReader(io.StringIO(txt)):
            v = (r.get("bs") or "").strip()
            if v in ("", "None", "nan"):
                continue
            pid = r.get("BDSPPatientID")
            if not pid:
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            try:
                p = int(pid)
            except Exception:
                continue
            if p not in out or t < out[p]:
                out[p] = t
    return out


def main():
    pids = {int(x) for x in open("/tmp/heedb_bs_patients.txt").read().split() if x.strip().isdigit()}
    aet = defaultdict(set); cond_seen = set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            for lab, pre in AETIOLOGY.items():
                if c and any(c.startswith(x) for x in pre):
                    aet[p].add(lab)
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass
    print(f"cohort={len(pids)}  with condition data={len(cond_seen & pids)}  with death record={len(set(death) & pids)}")

    # ---- CHECK 1: is ascertainment itself differential? -------------------------------------------------
    print("\n=== CHECK 1: death-record ascertainment rate BY AETIOLOGY ===")
    print("    if this varies widely, the primary analysis is compromised regardless of what CHECK 2 shows")
    base = sorted(pids & cond_seen)
    for lab in list(AETIOLOGY) + ["unexplained"]:
        if lab == "unexplained":
            grp = [p for p in base if not aet.get(p)]
        else:
            grp = [p for p in base if lab in aet.get(p, set())]
        if len(grp) < 30:
            continue
        rate = np.mean([1.0 if p in death else 0.0 for p in grp])
        print(f"   {lab:14s} n={len(grp):5d}   ascertained-death rate {100*rate:5.1f} %")

    # ---- CHECK 2: linkage-bias-immune timing analysis ---------------------------------------------------
    print("\n=== CHECK 2: among patients with an ASCERTAINED death, how soon after the EEG? ===")
    print("    every patient here has the same ascertainment status, so differential recording cannot contribute")
    et = eeg_times()
    rows = []
    for p in base:
        d = death.get(p); t = et.get(p)
        if d is None or t is None:
            continue
        days = (d - t).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows.append(dict(pid=p, days=days,
                         d30=1.0 if days <= 30 else 0.0,
                         d90=1.0 if days <= 90 else 0.0,
                         **{k: (1.0 if k in labs else 0.0) for k in AETIOLOGY}))
    n = len(rows)
    print(f"    analysable (death record + EEG time): {n} patients")
    if n < 300:
        print("    insufficient"); return
    print(f"    median days from EEG to death: {np.median([r['days'] for r in rows]):.0f}")

    expo = [k for k in AETIOLOGY if sum(r[k] for r in rows) >= 30]
    for out, lab in (("d30", "death within 30 days"), ("d90", "death within 90 days")):
        y = np.asarray([r[out] for r in rows], float)
        X = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        boots = defaultdict(list); spread = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            try:
                bb = np.linalg.lstsq(X[i], y[i], rcond=None)[0]
            except Exception:
                continue
            for j, k in enumerate(expo, start=1):
                boots[k].append(bb[j])
            spread.append(float(np.max(bb[1:]) - np.min(bb[1:])))
        print(f"\n   --- {lab} (baseline rate {100*y.mean():.1f} %) ---")
        for j, k in enumerate(expo, start=1):
            lo, hi = np.percentile(boots[k], [2.5, 97.5])
            print(f"      {k:14s} {100*b[j]:+6.2f} pp [{100*lo:+6.2f},{100*hi:+6.2f}] "
                  f"{'*' if (lo>0 or hi<0) else 'ns'}")
        lo, hi = np.percentile(spread, [2.5, 97.5])
        obs = float(np.max(b[1:]) - np.min(b[1:]))
        verdict = ("SPREAD SURVIVES -- not an ascertainment artefact" if lo > 0
                   else "spread consistent with zero -- primary result may be an artefact")
        print(f"      HETEROGENEITY spread {100*obs:.2f} pp [{100*lo:.2f},{100*hi:.2f}]   {verdict}")

    print("\n   Compare against the primary analysis, which found a 22.96 pp [18.22, 28.17] spread using")
    print("   'has a death record' as the outcome. If the timing analysis reproduces a clear spread, the")
    print("   primary result is not driven by differential recording.")


if __name__ == "__main__":
    sys.exit(main())
