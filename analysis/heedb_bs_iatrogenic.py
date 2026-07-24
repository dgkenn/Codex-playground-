#!/usr/bin/env python3
"""HEEDB — IATROGENIC vs PATHOLOGICAL burst suppression: is BS intrinsically lethal, or a marker of its CAUSE?

This is the wedge the flagship needs. Same EEG state, opposite cause:
  PATHOLOGICAL BS  = BS in a patient with structural/anoxic brain pathology (cerebrovascular ICD burden)
  IATROGENIC   BS  = BS without that pathology (i.e. drug/sedation-attributable context)
If mortality differs sharply between them AT THE SAME EEG STATE, then burst suppression is a marker of its cause,
not intrinsically lethal — which reframes the "avoid burst suppression" dogma (ENGAGES debate) and explains why the
intraoperative (VitalDB) setting shows the same EEG state with ~zero mortality.

Adds a proper NEGATIVE CONTROL (benign variants: wicket/breach) since `pdr` turned out to be genuinely
prognostic-protective rather than null.
De-identified aggregate output only.
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
ICD = "EEG/HEEDB_Metadata/HEEDB_ICD10_for_Neurology.csv"
MED = "EEG/HEEDB_Metadata/HEEDB_Medication_ATC.csv"
def get(key):
    raw = S3.get_object(Bucket=AP, Key=key)["Body"].read()
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
def dt(s):
    if not s: return None
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try: return datetime.strptime(s.strip(), f)
        except: pass
    return None
def has(v): return 1.0 if (v or "").strip() not in ("", "None", "nan") else 0.0
def num(v):
    """ICD/med cells hold CODE STRINGS (e.g. 'I63.9 G45.9') or counts -> presence flag."""
    v=(v or "").strip()
    if v in ("","None","nan","0","0.0"): return 0.0
    try: return 1.0 if float(v)>0 else 0.0
    except: return 1.0
def logit(X, y):
    X = np.asarray(X, float); y = np.asarray(y, float); b = np.zeros(X.shape[1])
    for _ in range(300):
        p = 1/(1+np.exp(-np.clip(X@b, -30, 30))); W = np.clip(p*(1-p), 1e-9, None); z = X@b + (y-p)/W
        try: b = np.linalg.solve((X.T*W)@X + 1e-6*np.eye(X.shape[1]), (X.T*W)@z)
        except np.linalg.LinAlgError: break
    cov = np.linalg.inv((X.T*W)@X + 1e-6*np.eye(X.shape[1]))
    return b, np.sqrt(np.diag(cov))
print("loading patient-level ICD10 + medication burden ...")
icd = {r["BDSPPatientID"]: r for r in get(ICD)}
med = {r["BDSPPatientID"]: r for r in get(MED)}
CVD = "Cerebrovascular Diseases"; NEURODEG = "Cerebral Degeneration"; NERV = "Nervous System Drugs"
def build(site, horizon=30):
    f = get(FIND[site]); m = get(META[site])
    dod = {}
    for r in m:
        d = dt(r.get("DateOfDeath", ""))
        if d: dod[r["BDSPPatientID"]] = d
    seen = {}
    for r in f:
        t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
        if t is None: continue
        try: age = float(r.get("AgeAtVisit","") or "nan")
        except: age = float("nan")
        if not (age == age) or age < 18 or age > 110: continue
        pid = r["BDSPPatientID"]
        if pid in seen: continue
        d = dod.get(pid); died = 0
        if d is not None:
            days = (d - t).days
            if days < -1: continue
            died = 1 if days <= horizon else 0
        ic = icd.get(pid, {}); md = med.get(pid, {})
        seen[pid] = dict(pid=pid, age=age, female=1.0 if r.get("SexDSC")=="Female" else 0.0,
            svc=(r.get("ServiceName(EEG)") or "").strip(),
            bs=has(r.get("bs")), slow=has(r.get("gen slowing")), sz=has(r.get("seizure")),
            gpd=has(r.get("gpd")), lpd=has(r.get("lpd")), foc=has(r.get("foc slowing")),
            benign=1.0 if (has(r.get("wicket")) or has(r.get("breach")) or has(r.get("bets"))) else 0.0,
            cvd=num(ic.get(CVD)), deg=num(ic.get(NEURODEG)), nerv=num(md.get(NERV)), died=died)
    return list(seen.values())
def run(site, horizon=30):
    R = build(site, horizon)
    BS = [r for r in R if r["bs"] > 0]
    print(f"\n{'='*74}\n{site}: {len(R)} patients, {len(BS)} with burst suppression, "
          f"{horizon}d mortality {100*np.mean([r['died'] for r in R]):.1f}%\n{'='*74}")
    # ---- the wedge: within BS patients, split by structural/anoxic pathology burden ----
    path = [r for r in BS if r["cvd"] > 0]
    iatr = [r for r in BS if r["cvd"] == 0]
    print(f"  BS WITH cerebrovascular/structural dx  (pathological): n={len(path):5d}  "
          f"mortality={100*np.mean([r['died'] for r in path]):5.1f}%")
    print(f"  BS WITHOUT it            (iatrogenic-context): n={len(iatr):5d}  "
          f"mortality={100*np.mean([r['died'] for r in iatr]):5.1f}%")
    if len(path) > 30 and len(iatr) > 30:
        X = [[1.0, 1.0 if r["cvd"] > 0 else 0.0, (r["age"]-60)/20.0, r["female"]] for r in BS]
        y = [float(r["died"]) for r in BS]
        b, se = logit(X, y)
        print(f"  --> within-BS OR for having structural pathology (age/sex adj): "
              f"{math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]")
    # ---- contrast: BS effect within each stratum (is BS lethal when there is NO pathology?) ----
    print("\n  BS mortality effect WITHIN pathology strata (vs non-BS patients of the same stratum):")
    for lab, sel in (("no structural dx", lambda r: r["cvd"] == 0), ("structural dx present", lambda r: r["cvd"] > 0)):
        S = [r for r in R if sel(r)]
        if sum(r["bs"] for r in S) < 30: continue
        X = [[1.0, r["bs"], (r["age"]-60)/20.0, r["female"], r["slow"]] for r in S]
        y = [float(r["died"]) for r in S]
        b, se = logit(X, y)
        print(f"    {lab:24s}: n={len(S):6d}  BS OR={math.exp(b[1]):5.2f} "
              f"[{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]")
    # ---- service context (OR/EMU = elective/anesthetic; LTM/Routine = clinical) ----
    print("\n  BS mortality by recording context (service):")
    for s in ("OR", "EMU", "Routine", "LTM"):
        sub = [r for r in BS if r["svc"] == s]
        if len(sub) >= 15:
            print(f"    {s:8s}: n={len(sub):5d}  mortality={100*np.mean([r['died'] for r in sub]):5.1f}%")
    # ---- proper negative control: benign variants ----
    ben = [r for r in R if r["benign"] > 0]
    if len(ben) > 50:
        X = [[1.0, r["benign"], (r["age"]-60)/20.0, r["female"], r["slow"]] for r in R]
        y = [float(r["died"]) for r in R]
        b, se = logit(X, y)
        print(f"\n  NEGATIVE CONTROL (benign variants wicket/breach/bets, n={len(ben)}): "
              f"OR={math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]  "
              f"{'<- properly NULL' if (math.exp(b[1]-1.96*se[1])<1<math.exp(b[1]+1.96*se[1])) else '<- NOT null, interpret with care'}")
if __name__ == "__main__":
    hz = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    for s in ("S0001", "S0002"): run(s, hz)
    print("\n[read] If BS mortality is far LOWER without structural pathology, and near-zero in OR/EMU contexts,")
    print("       burst suppression is a marker of its CAUSE rather than intrinsically lethal.")
    print("DONE")
