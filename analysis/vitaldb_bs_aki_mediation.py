#!/usr/bin/env python3
"""Does burst-suppression-associated hypotension cause DOWNSTREAM ORGAN INJURY? (BS -> hypotension -> AKI)

This is the test that converts a physiological-ordering finding into a clinical one, and it is the step the
reframed thesis needs: if BS heralds hypotension, and that hypotension mediates end-organ injury, then BS marks a
patient in whom the haemodynamic insult matters.

Outcome: KDIGO AKI from creatinine (postoperative peak vs preoperative baseline):
   AKI = peak_post >= 1.5 x baseline_pre  OR  rise >= 0.3 mg/dL
Exposure: intraoperative burst-suppression burden (validated raw-EEG detector).
Mediator: intraoperative hypotension burden (fraction of maintenance bins with MAP<65).

Mediation is assessed by the classic decomposition (total effect -> direct effect after adjusting for the
mediator). This is NOT a causal proof: BS and hypotension share anaesthetic depth as a common cause, so the
estimand is 'association consistent with mediation', and it is reported as such.
"""
import csv, urllib.request, gzip, math, sys
from collections import defaultdict
import numpy as np
SP="/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb"
def fetch_labs():
    import os
    p=f"{SP}/labs.csv"
    if not os.path.exists(p):
        raw=urllib.request.urlopen("https://api.vitaldb.net/labs",timeout=120).read()
        try: raw=gzip.decompress(raw)
        except Exception: pass
        open(p,"wb").write(raw)
    return p
def logit(X,y):
    X=np.asarray(X,float);y=np.asarray(y,float);b=np.zeros(X.shape[1])
    for _ in range(300):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except np.linalg.LinAlgError: break
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]))
    return b,np.sqrt(np.diag(cov))
def main():
    # 1) per-case intraoperative exposure + mediator from the validated bin-level data
    bs=defaultdict(list); hyp=defaultdict(list); ce=defaultdict(list); age={}
    for d in csv.DictReader(open("/tmp/eeg_probe/bridge_bins.csv")):
        try:
            c=float(d["ce"]) if d["ce"] else np.nan
            if not (c==c and c>=1.0): continue
            bs[d["caseid"]].append(float(d["bs"]))
            ce[d["caseid"]].append(c)
            if d["mbp"]: hyp[d["caseid"]].append(1.0 if float(d["mbp"])<65 else 0.0)
            if d["age"]: age[d["caseid"]]=float(d["age"])
        except Exception: pass
    # 2) creatinine -> KDIGO AKI
    cr=defaultdict(list)
    for r in csv.DictReader(open(fetch_labs())):
        if r["name"]!="cr": continue
        try: cr[r["caseid"]].append((float(r["dt"]), float(r["result"])))
        except Exception: pass
    rows=[]
    for cid, series in cr.items():
        if cid not in bs or len(bs[cid])<20: continue
        pre=[v for t,v in series if t<=0]
        post=[v for t,v in series if 0<t<=7*24*3600]
        if not pre or not post: continue
        base=min(pre); peak=max(post)
        aki=1.0 if (peak>=1.5*base or (peak-base)>=0.3) else 0.0
        h=hyp.get(cid,[])
        rows.append(dict(cid=cid, bs=float(np.mean(bs[cid])), hyp=float(np.mean(h)) if h else np.nan,
                         ce=float(np.mean(ce[cid])), age=age.get(cid,np.nan), base=base, peak=peak, aki=aki))
    R=[r for r in rows if r["hyp"]==r["hyp"] and r["age"]==r["age"]]
    print(f"cases with EEG + intraop MAP + pre/post creatinine: {len(R)}")
    print(f"  AKI incidence: {100*np.mean([r['aki'] for r in R]):.1f}%  ({int(sum(r['aki'] for r in R))} cases)")
    print(f"  BS burden: median={np.median([r['bs'] for r in R]):.3f}   hypotension burden: median={np.median([r['hyp'] for r in R]):.3f}")
    if len(R)<150 or sum(r["aki"] for r in R)<25:
        print("  INSUFFICIENT for mediation modelling"); return
    # 3) exposure -> outcome, by BS tertile
    t=np.percentile([r["bs"] for r in R],[33,67])
    print("\n=== AKI by intraoperative burst-suppression burden ===")
    for lab,sel in ((f"low  (<{t[0]:.3f})",lambda r:r["bs"]<t[0]),
                    (f"mid  ({t[0]:.3f}-{t[1]:.3f})",lambda r:t[0]<=r["bs"]<t[1]),
                    (f"high (>={t[1]:.3f})",lambda r:r["bs"]>=t[1])):
        s=[r for r in R if sel(r)]
        if s: print(f"   BS {lab:22s}: n={len(s):4d}  AKI={100*np.mean([r['aki'] for r in s]):5.1f}%  "
                    f"hypotension burden={np.median([r['hyp'] for r in s]):.3f}")
    # 4) mediation decomposition
    print("\n=== mediation: BS -> hypotension -> AKI ===")
    zb=lambda v: (np.array(v)-np.mean(v))/(np.std(v)+1e-9)
    BS=zb([r["bs"] for r in R]); HY=zb([r["hyp"] for r in R]); AG=zb([r["age"] for r in R]); CE=zb([r["ce"] for r in R])
    Y=[r["aki"] for r in R]
    b1,s1=logit([[1,BS[i],AG[i],CE[i]] for i in range(len(R))],Y)
    b2,s2=logit([[1,BS[i],HY[i],AG[i],CE[i]] for i in range(len(R))],Y)
    print(f"   TOTAL  effect of BS (adj age,Ce)            : OR={math.exp(b1[1]):.2f} [{math.exp(b1[1]-1.96*s1[1]):.2f},{math.exp(b1[1]+1.96*s1[1]):.2f}] per SD")
    print(f"   DIRECT effect of BS (further adj hypotension): OR={math.exp(b2[1]):.2f} [{math.exp(b2[1]-1.96*s2[1]):.2f},{math.exp(b2[1]+1.96*s2[1]):.2f}] per SD")
    print(f"   hypotension burden itself                    : OR={math.exp(b2[2]):.2f} [{math.exp(b2[2]-1.96*s2[2]):.2f},{math.exp(b2[2]+1.96*s2[2]):.2f}] per SD")
    if b1[1]!=0:
        prop=100*(1-b2[1]/b1[1])
        print(f"   => {prop:.0f}% of the BS-AKI association is attenuated by adjusting for hypotension")
        print("      [large attenuation = consistent with hypotension MEDIATING the BS-AKI link;")
        print("       NOT proof — BS and hypotension share anaesthetic depth as a common cause]")
    # 5) other outcomes
    print("\n=== other adverse outcomes vs BS burden ===")
    meta={}
    for r in csv.DictReader(open(f"{SP}/cases.csv")):
        cid=r.get("caseid") or r.get("﻿caseid"); meta[cid]=r
    for nm,key,fn in (("ICU days >0","icu_days",lambda v: 1.0 if float(v)>0 else 0.0),
                      ("in-hospital death","death_inhosp",lambda v: float(v))):
        sub=[]
        for r in R:
            m=meta.get(r["cid"])
            if not m: continue
            try: sub.append((r["bs"], fn(m[key])))
            except Exception: pass
        if len(sub)>150 and sum(v for _,v in sub)>=10:
            hi=[v for b_,v in sub if b_>=t[1]]; lo=[v for b_,v in sub if b_<t[0]]
            print(f"   {nm:20s}: BS-high={100*np.mean(hi):5.1f}% (n={len(hi)})  BS-low={100*np.mean(lo):5.1f}% (n={len(lo)})  events={int(sum(v for _,v in sub))}")
if __name__=="__main__": main()
