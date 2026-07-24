#!/usr/bin/env python3
"""HEEDB DISCOVERY ARM — is burst suppression an INDEPENDENT mortality signal, or just a severity marker?

This is the outcome dimension VitalDB structurally cannot provide (elective surgery, ~0 mortality), and it is the
decisive test for the flagship's clinical claim.

DESIGN (severity-controlled, the confound that killed earlier attempts):
  deployed marker : clinician-labeled burst suppression (`bs`) on the EEG report
  severity anchor : generalized slowing (`gen slowing`) — the canonical encephalopathy-severity marker
  hard outcome    : death within N days of the EEG (DateOfDeath, S0001/S0002 only)
  DECISIVE TEST   : does `bs` predict mortality AFTER adjusting for `gen slowing` + age + sex?
                    If BS adds nothing beyond slowing, BS is a severity marker (kill the specific claim).
                    If BS adds independently, burst suppression carries specific prognostic weight.
  NEGATIVE CONTROL: `pdr` (posterior dominant rhythm = a NORMAL finding) must NOT predict death in the same model.
  EXTERNAL VALID. : discover on S0001, validate on S0002 (independent hospital).
De-identified aggregate outputs only; no PII printed or written.
"""
import boto3, io, csv, sys, math
from datetime import datetime
from botocore.config import Config
import numpy as np
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
S3 = boto3.client("s3", region_name="us-east-1", config=Config(s3={'payload_signing_enabled': False}))
FIND = {"S0001": "EEG/HEEDB_Metadata/S0001_EEG__reports_findings.csv",
        "S0002": "EEG/HEEDB_Metadata/S0002_EEG__reports_findings.csv"}
META = {"S0001": "EEG/eeg-metadata/S0001_eeg_metadata_2026_04_30.csv",
        "S0002": "EEG/eeg-metadata/S0002_eeg_metadata_2026_04_30.csv"}
def get(key):
    raw = S3.get_object(Bucket=AP, Key=key)["Body"].read()
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
def dt(s):
    if not s: return None
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try: return datetime.strptime(s.strip(), f)
        except: pass
    return None
def has(v):
    """finding cell is non-empty when the label was asserted (report/annotation/verified)."""
    return 1.0 if (v or "").strip() not in ("", "None", "nan") else 0.0
def logit(X, y, iters=300):
    X = np.asarray(X, float); y = np.asarray(y, float); b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1/(1+np.exp(-np.clip(X@b, -30, 30))); W = np.clip(p*(1-p), 1e-9, None)
        z = X@b + (y-p)/W
        try: b = np.linalg.solve((X.T*W)@X + 1e-6*np.eye(X.shape[1]), (X.T*W)@z)
        except np.linalg.LinAlgError: break
    cov = np.linalg.inv((X.T*W)@X + 1e-6*np.eye(X.shape[1]))
    return b, np.sqrt(np.diag(cov))
def build(site, horizon_days=30):
    f = get(FIND[site]); m = get(META[site])
    # patient-level death date (one per patient)
    dod = {}
    for r in m:
        d = dt(r.get("DateOfDeath", ""))
        if d: dod[r["BDSPPatientID"]] = d
    rows = []
    for r in f:
        t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
        if t is None: continue
        try: age = float(r.get("AgeAtVisit", "") or "nan")
        except: age = float("nan")
        if not (age == age) or age < 18 or age > 110: continue
        pid = r["BDSPPatientID"]
        d = dod.get(pid)
        died = 0
        if d is not None:
            days = (d - t).days
            if days < -1: continue          # death recorded before the EEG -> data error, drop
            died = 1 if days <= horizon_days else 0
        rows.append(dict(pid=pid, site=site, age=age,
                         female=1.0 if (r.get("SexDSC","")=="Female") else 0.0,
                         svc=(r.get("ServiceName(EEG)") or "").strip(),
                         bs=has(r.get("bs")), slow=has(r.get("gen slowing")), foc=has(r.get("foc slowing")),
                         sz=has(r.get("seizure")), gpd=has(r.get("gpd")), lpd=has(r.get("lpd")),
                         pdr=has(r.get("pdr")), lowv=has(r.get("low voltage")), status=has(r.get("status")),
                         died=died, has_dod=1 if d is not None else 0))
    # one record per patient (first EEG) to avoid within-patient pseudo-replication
    seen = {}
    for r in rows:
        if r["pid"] not in seen: seen[r["pid"]] = r
    return list(seen.values())
def describe(R, site):
    n = len(R); d = sum(r["died"] for r in R)
    print(f"\n=== {site}: {n} unique adult patients; {d} died <=30d ({100*d/max(1,n):.1f}%) ===")
    print(f"    age {np.mean([r['age'] for r in R]):.0f}±{np.std([r['age'] for r in R]):.0f}; "
          f"female {100*np.mean([r['female'] for r in R]):.0f}%")
    for k in ("bs","slow","foc","sz","gpd","lpd","pdr","status","lowv"):
        sub = [r for r in R if r[k] > 0]
        if len(sub) >= 20:
            print(f"    {k:7s}: n={len(sub):6d} ({100*len(sub)/n:4.1f}%)  mortality={100*np.mean([r['died'] for r in sub]):5.1f}%  "
                  f"vs {100*np.mean([r['died'] for r in R if r[k]==0]):5.1f}% without")
    svc = {}
    for r in R: svc[r["svc"]] = svc.get(r["svc"], 0) + 1
    print(f"    services: {dict(sorted(svc.items(), key=lambda x:-x[1])[:6])}")
def model(R, label):
    """DECISIVE: bs -> death, adjusted for the severity anchor (gen slowing) + age + sex + other findings."""
    print(f"\n--- {label} (n={len(R)}, deaths={sum(r['died'] for r in R)}) ---")
    specs = [("bs alone",              ["bs"]),
             ("bs + age,sex",          ["bs"]),
             ("bs + SLOWING + age,sex",["bs","slow"]),
             ("bs + slowing + sz,gpd,lpd,foc + age,sex", ["bs","slow","sz","gpd","lpd","foc"]),
             ("NEGATIVE CONTROL pdr (+slowing,age,sex)", ["pdr","slow"])]
    for name, terms in specs:
        X = []; y = []
        for r in R:
            row = [1.0] + [r[t] for t in terms]
            if "age" in name or "age,sex" in name: row += [ (r["age"]-60)/20.0, r["female"] ]
            X.append(row); y.append(float(r["died"]))
        if sum(y) < 15: print(f"    {name}: too few events"); continue
        b, se = logit(X, y)
        i = 1  # first term is the focal one
        lo, hi = math.exp(b[i]-1.96*se[i]), math.exp(b[i]+1.96*se[i])
        star = "*" if lo > 1 or hi < 1 else " "
        print(f"    {name:44s}: {terms[0]:4s} OR={math.exp(b[i]):5.2f} [{lo:.2f},{hi:.2f}] {star}")
        if len(terms) > 1 and terms[0] == "bs":
            j = 2
            print(f"        {'(slowing in same model)':44s}: slow OR={math.exp(b[j]):5.2f} "
                  f"[{math.exp(b[j]-1.96*se[j]):.2f},{math.exp(b[j]+1.96*se[j]):.2f}]")
if __name__ == "__main__":
    hz = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    allR = {}
    for site in ("S0001", "S0002"):
        R = build(site, hz)
        allR[site] = R
        describe(R, site)
    print("\n" + "="*78)
    print(f"DECISIVE TEST — does burst suppression predict {hz}-day mortality BEYOND generalized slowing?")
    print("="*78)
    model(allR["S0001"], "DISCOVERY  S0001")
    model(allR["S0002"], "VALIDATION S0002 (independent hospital)")
    print("\n[read] If 'bs' stays significant after adding SLOWING, burst suppression carries prognostic weight")
    print("       specific to itself, not merely encephalopathy severity. The pdr negative control must be NULL.")
    print("DONE")
