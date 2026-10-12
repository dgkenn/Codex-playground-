#!/usr/bin/env python3
"""WITHIN-HEEDB aetiology x burst-suppression INTERACTION test.

Replaces the rhetorical cross-cohort (VitalDB vs I-CARE) contrast with a real interaction test inside ONE
harmonized dataset, one detector, one hospital system — the red-team's top recommendation.

Design:
  outcome  : linkage-bias-immune -> among patients WITH a recorded death, did they die <=30 d of the EEG?
             (avoids the 13.8%-ascertainment / differential-linkage problem entirely)
  exposure : clinician-labelled burst suppression (`bs`)
  aetiology: ANOXIC/ARREST context vs OTHER, from ICD-10 neurology categories + recording service
  test     : bs x aetiology interaction. If BS carries the SAME hazard regardless of cause, the
             "meaning depends on aetiology" thesis fails inside a harmonized dataset.
De-identified aggregates only.
"""
import boto3, io, csv, math, sys
from datetime import datetime
from botocore.config import Config
import numpy as np
import os
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
AP="arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
S3=boto3.client("s3",region_name="us-east-1",config=Config(s3={'payload_signing_enabled':False}))
FIND={"S0001":"EEG/HEEDB_Metadata/S0001_EEG__reports_findings.csv",
      "S0002":"EEG/HEEDB_Metadata/S0002_EEG__reports_findings.csv"}
META={"S0001":"EEG/eeg-metadata/S0001_eeg_metadata_2026_04_30.csv",
      "S0002":"EEG/eeg-metadata/S0002_eeg_metadata_2026_04_30.csv"}
ICD="EEG/HEEDB_Metadata/HEEDB_ICD10_for_Neurology.csv"
def get(k): return list(csv.DictReader(io.StringIO(S3.get_object(Bucket=AP,Key=k)["Body"].read().decode("utf-8","replace"))))
def dt(s):
    for f in ("%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try: return datetime.strptime((s or "").strip(),f)
        except: pass
    return None
def has(v): return 1.0 if (v or "").strip() not in ("","None","nan") else 0.0
def logit(X,y):
    X=np.asarray(X,float);y=np.asarray(y,float);b=np.zeros(X.shape[1])
    for _ in range(300):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except np.linalg.LinAlgError: break
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]))
    return b,np.sqrt(np.diag(cov))
icd={r["BDSPPatientID"]:r for r in get(ICD)}
# ICD-10 codes indicating anoxic / cardiac-arrest brain injury (the lethal aetiology)
ANOX_CODES=("G93.1","I46","G93.5","P91.6","R09.02","I97.12","G93.40")
def anoxic(pid):
    r=icd.get(pid)
    if not r: return 0.0
    blob=" ".join((v or "") for k,v in r.items() if k not in ("BDSPPatientID","SiteID","SexDSC","VisitCount","AgeAtVisitAvg"))
    return 1.0 if any(c in blob for c in ANOX_CODES) else 0.0
def build(site):
    f=get(FIND[site]); m=get(META[site])
    dod={}
    for r in m:
        d=dt(r.get("DateOfDeath",""))
        if d and r.get("BidsFolder"): dod[r["BidsFolder"]]=d
    seen={}
    for r in f:
        t=dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
        if not t: continue
        try: age=float(r.get("AgeAtVisit","") or "nan")
        except: continue
        if not (age==age) or age<18 or age>110: continue
        pid=r["BDSPPatientID"]
        if pid in seen: continue
        d=dod.get(f"sub-{site}{pid}")
        if d is None: continue                      # LINKAGE-IMMUNE: only patients with ascertained death
        days=(d-t).days
        if days< -1: continue
        seen[pid]=dict(pid=pid,site=site,age=age,
                       female=1.0 if r.get("SexDSC")=="Female" else 0.0,
                       svc=(r.get("ServiceName(EEG)") or "").strip(),
                       bs=has(r.get("bs")), slow=has(r.get("gen slowing")),
                       anox=anoxic(pid), days=days, early=1.0 if days<=30 else 0.0)
    return list(seen.values())
def run():
    R=[]
    for s in ("S0001","S0002"): R+=build(s)
    print(f"death-linked adult patients (both sites): {len(R)}")
    print(f"  anoxic/arrest ICD present: {sum(r['anox'] for r in R):.0f} ({100*np.mean([r['anox'] for r in R]):.1f}%)")
    print(f"  BS+: {sum(r['bs'] for r in R):.0f} ({100*np.mean([r['bs'] for r in R]):.1f}%)")
    print("\n=== 2x2: %% dying <=30d of EEG (among ascertained deaths) ===")
    print(f"{'':22s} {'BS-':>12s} {'BS+':>12s}   {'crude RR':>9s}")
    for lab,sel in (("non-anoxic aetiology",lambda r:r['anox']==0),("ANOXIC/arrest aetiology",lambda r:r['anox']>0)):
        g=[r for r in R if sel(r)]
        p1=[r['early'] for r in g if r['bs']>0]; p0=[r['early'] for r in g if r['bs']==0]
        if len(p1)>=20 and len(p0)>=20:
            print(f"{lab:22s} {100*np.mean(p0):11.1f}% {100*np.mean(p1):11.1f}%   {np.mean(p1)/max(np.mean(p0),1e-9):8.2f}")
    # formal interaction
    d=[r for r in R]
    X=[[1,r['bs'],r['anox'],r['bs']*r['anox'],(r['age']-60)/15.0,r['female'],1.0 if r['site']=="S0002" else 0.0] for r in d]
    y=[r['early'] for r in d]
    b,se=logit(X,y)
    nm=["intercept","BS","anoxic","BS x anoxic","age/15","female","site"]
    print("\n=== formal interaction model: early death ~ BS * anoxic + age + sex + site ===")
    for i,n in enumerate(nm):
        lo,hi=math.exp(b[i]-1.96*se[i]),math.exp(b[i]+1.96*se[i])
        star="*" if (lo>1 or hi<1) else " "
        print(f"   {n:14s} OR={math.exp(b[i]):6.2f} [{lo:.2f},{hi:.2f}] {star}")
    print("\n   [If 'BS x anoxic' is NULL, burst suppression carries the SAME prognostic weight regardless of")
    print("    aetiology inside a harmonized dataset -> the 'meaning depends on cause' thesis FAILS here.")
    print("    If POSITIVE, aetiology genuinely modifies the BS signal -> thesis supported by an interaction test.]")
    # service as an alternative aetiology proxy
    print("\n=== alternative aetiology proxy: recording service ===")
    for s in ("OR","EMU","Routine","LTM"):
        g=[r for r in R if r['svc']==s]
        p1=[r['early'] for r in g if r['bs']>0]; p0=[r['early'] for r in g if r['bs']==0]
        if len(p1)>=15 and len(p0)>=15:
            print(f"   {s:8s}: BS+ {100*np.mean(p1):5.1f}% (n={len(p1):4d})  BS- {100*np.mean(p0):5.1f}% (n={len(p0):4d})  RR={np.mean(p1)/max(np.mean(p0),1e-9):.2f}")
if __name__=="__main__": run()
