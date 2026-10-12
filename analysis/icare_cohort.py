#!/usr/bin/env python3
"""I-CARE arm — the PATHOLOGICAL burst-suppression cohort (post-cardiac-arrest coma).

Stage 1: pull all 607 patient metadata files (tiny) -> cohort table with CPC / Outcome / TTM / Hospital.
Stage 2: measure BS burden from the 19-ch 500 Hz EEG with the SAME detector validated at ~90% against
         the burst-supression/ sample-level expert labels, sampled at a standard prognostic timepoint.
De-identified aggregates only.
"""
import boto3, io, re, sys, csv
from concurrent.futures import ThreadPoolExecutor
from botocore.config import Config
import numpy as np
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-restricted-access-point"
ROOT = "ICARE_train/training/"
def s3c():
    return boto3.Session(profile_name="physionet").client(
        "s3", region_name="us-east-1",
        config=Config(s3={'payload_signing_enabled': False}, max_pool_connections=32, retries={'max_attempts':3}))
S3 = s3c()
def list_patients():
    pats=[]; tok=None
    while True:
        kw=dict(Bucket=AP, Prefix=ROOT, Delimiter="/", MaxKeys=1000)
        if tok: kw["ContinuationToken"]=tok
        r=S3.list_objects_v2(**kw)
        pats += [p["Prefix"].rstrip("/").split("/")[-1] for p in r.get("CommonPrefixes",[])]
        if not r.get("IsTruncated"): break
        tok=r.get("NextContinuationToken")
    return sorted(pats)
def get_txt(pid):
    try:
        b=S3.get_object(Bucket=AP, Key=f"{ROOT}{pid}/{pid}.txt")["Body"].read().decode("utf-8","replace")
    except Exception:
        return None
    d={"pid":pid}
    for line in b.splitlines():
        if ":" in line:
            k,v=line.split(":",1); d[k.strip()]=v.strip()
    return d
def build():
    pats=list_patients()
    print(f"patients: {len(pats)}")
    with ThreadPoolExecutor(max_workers=24) as ex:
        rows=[r for r in ex.map(get_txt, pats) if r]
    print(f"metadata parsed: {len(rows)}")
    def num(v):
        try: return float(v)
        except: return np.nan
    out=[]
    for d in rows:
        out.append(dict(pid=d["pid"], hospital=d.get("Hospital",""), age=num(d.get("Age")),
                        sex=d.get("Sex",""), rosc=num(d.get("ROSC")), ohca=d.get("OHCA",""),
                        shockable=d.get("Shockable Rhythm",""), ttm=num(d.get("TTM")),
                        outcome=d.get("Outcome",""), cpc=num(d.get("CPC"))))
    with open("/tmp/eeg_probe/icare_cohort.csv","w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    # describe
    import collections
    print("\n=== I-CARE cohort ===")
    print("  hospitals:", dict(collections.Counter(r["hospital"] for r in out)))
    print("  outcome  :", dict(collections.Counter(r["outcome"] for r in out)))
    print("  CPC      :", dict(sorted(collections.Counter(r["cpc"] for r in out if r["cpc"]==r["cpc"]).items())))
    print("  TTM      :", dict(collections.Counter(r["ttm"] for r in out)))
    print("  OHCA     :", dict(collections.Counter(r["ohca"] for r in out)))
    print("  shockable:", dict(collections.Counter(r["shockable"] for r in out)))
    ages=[r["age"] for r in out if r["age"]==r["age"]]
    print(f"  age      : {np.mean(ages):.0f} +- {np.std(ages):.0f}")
    poor=[r for r in out if r["outcome"]=="Poor"]
    print(f"  POOR outcome: {len(poor)}/{len(out)} = {100*len(poor)/len(out):.1f}%")
    return out
if __name__=="__main__":
    build()
