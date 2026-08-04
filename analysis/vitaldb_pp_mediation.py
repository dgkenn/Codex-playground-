#!/usr/bin/env python3
"""MECHANISM of BS -> AKI: is the pathway FLOW (stroke volume) rather than PRESSURE?

Adjusting for hypotension burden did not attenuate BS->AKI (1.37 -> 1.36). But mean pressure is not perfusion:
MAP can be defended by vasoconstriction while stroke volume — and renal blood flow — falls. Pulse pressure
(PP = SBP - DBP) is a standard stroke-volume surrogate, available from the arterial line in the FULL cohort
(1,780 cases), unlike the 215-case EV1000 SVR or the 362-case cardiac-output subcohort.

Exposure  : intraoperative burst-suppression burden (validated raw-EEG detector)
Mediators : (a) low-PP burden = fraction of maintenance bins with PP < 85% of that patient's own baseline PP
            (b) OCCULT low-PP = low PP while MAP >= 65 (the state a pressure-only analysis cannot see)
            (c) hypotension burden (pressure comparator)
Outcome   : KDIGO AKI (post-op peak vs pre-op baseline creatinine)
Inference : difference-method mediation, case-level nonparametric bootstrap (2,000) for proportion mediated.
            Proportion mediated is a RATIO and is only reported when the total effect is clearly non-null.
Assumption stated plainly: BS, flow and anaesthetic depth share common causes; this estimates attenuation
consistent with mediation, not a randomised causal effect.
"""
import csv, math
from collections import defaultdict
import numpy as np
SP="/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb"
rng=np.random.default_rng(11)
def logit(X,y,ridge=1e-6):
    X=np.asarray(X,float); y=np.asarray(y,float); b=np.zeros(X.shape[1])
    for _ in range(200):
        p=1/(1+np.exp(-np.clip(X@b,-30,30))); W=np.clip(p*(1-p),1e-9,None); z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+ridge*np.eye(X.shape[1]),(X.T*W)@z)
        except np.linalg.LinAlgError: return None
    return b
def zs(v):
    v=np.asarray(v,float); s=v.std()
    return (v-v.mean())/(s if s>1e-9 else 1.0)
def build():
    BS={}; CEc=defaultdict(list)
    for d in csv.DictReader(open("/tmp/eeg_probe/bridge_bins.csv")):
        try:
            ce=float(d["ce"]) if d["ce"] else np.nan
            if not (ce==ce and ce>=1.0): continue
            BS[(d["caseid"],float(d["bin_t"]))]=float(d["bs"]); CEc[d["caseid"]].append(ce)
        except Exception: pass
    per=defaultdict(lambda: dict(bs=[],pp=[],mbp=[])); seen=set()
    for d in csv.DictReader(open("/tmp/eeg_probe/pp_bins.csv")):
        try:
            cid=d["caseid"]; t=float(d["bin_t"])
            if (cid,t) in seen: continue
            seen.add((cid,t))
            bs=BS.get((cid,t))
            if bs is None: continue
            s=float(d["sbp"]); dia=float(d["dbp"]); pp=s-dia; mbp=dia+pp/3.0
            if not (10<pp<120 and 30<mbp<160): continue
            p=per[cid]; p["bs"].append(bs); p["pp"].append(pp); p["mbp"].append(mbp)
        except Exception: pass
    cr=defaultdict(list)
    for r in csv.DictReader(open(f"{SP}/labs.csv")):
        if r["name"]!="cr": continue
        try: cr[r["caseid"]].append((float(r["dt"]),float(r["result"])))
        except Exception: pass
    meta={}
    for r in csv.DictReader(open(f"{SP}/cases.csv")):
        cid=r.get("caseid") or r.get("﻿caseid"); meta[cid]=r
    rows=[]
    for cid,p in per.items():
        if len(p["bs"])<20: continue
        pp=np.array(p["pp"]); mbp=np.array(p["mbp"])
        s=cr.get(cid); m=meta.get(cid)
        if not s or not m: continue
        pre=[v for t,v in s if t<=0]; post=[v for t,v in s if 0<t<=7*24*3600]
        if not pre or not post: continue
        try: asa=float((m.get("asa") or "").strip()[0]); age=float(m.get("age"))
        except Exception: continue
        base_pp=float(np.median(pp[:min(20,len(pp))]))
        if not (base_pp==base_pp and base_pp>0): continue
        low=pp < 0.85*base_pp
        b0=min(pre); pk=max(post)
        rows.append(dict(cid=cid, bs=float(np.mean(p["bs"])), lowpp=float(np.mean(low)),
                         occult=float(np.mean(low & (mbp>=65))), hyp=float(np.mean(mbp<65)),
                         ce=float(np.mean(CEc.get(cid,[2.5]))), age=age, asa=asa,
                         dur=len(p["bs"])*0.5, base_cr=b0,
                         aki=1.0 if (pk>=1.5*b0 or (pk-b0)>=0.3) else 0.0))
    return rows
def main():
    R=build(); n=len(R); ev=int(sum(r["aki"] for r in R))
    print(f"cases with EEG + arterial PP + creatinine: {n}   AKI {100*ev/n:.1f}% ({ev} events)")
    print(f"  medians — BS {np.median([r['bs'] for r in R]):.3f} | low-PP {np.median([r['lowpp'] for r in R]):.3f} | "
          f"OCCULT low-PP {np.median([r['occult'] for r in R]):.3f} | hypotension {np.median([r['hyp'] for r in R]):.3f}")
    BSz=zs([r["bs"] for r in R]); AG=zs([r["age"] for r in R]); AS=zs([r["asa"] for r in R])
    CEz=zs([r["ce"] for r in R]); DU=zs([r["dur"] for r in R])
    print("\n=== STEP 1: does burst suppression mark LOW FLOW, incl. at PRESERVED pressure? ===")
    X=np.column_stack([np.ones(n),BSz,AG,CEz,AS,DU])
    for lab,key in (("low-PP burden (vs own baseline)","lowpp"),
                    ("OCCULT low-PP (PP low, MAP>=65)","occult"),
                    ("hypotension burden (comparator)","hyp")):
        Y=np.asarray([r[key] for r in R],float)
        b,_,_,_=np.linalg.lstsq(X,Y,rcond=None)
        res=Y-X@b; se=np.sqrt(np.diag((res@res/(n-X.shape[1]))*np.linalg.pinv(X.T@X)))
        lo,hi=b[1]-1.96*se[1],b[1]+1.96*se[1]
        print(f"   {lab:36s} beta/SD BS = {b[1]:+.4f} [{lo:+.4f},{hi:+.4f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    print("\n=== STEP 2: BS -> AKI, mediation by FLOW vs PRESSURE (bootstrap 2000) ===")
    def fit(idx, med=None):
        Rs=[R[i] for i in idx]
        bs=zs([r["bs"] for r in Rs]); ag=zs([r["age"] for r in Rs]); ce=zs([r["ce"] for r in Rs])
        asa=zs([r["asa"] for r in Rs]); du=zs([r["dur"] for r in Rs]); bc=zs([r["base_cr"] for r in Rs])
        y=[r["aki"] for r in Rs]
        base=[[1,bs[i],ag[i],ce[i],asa[i],du[i],bc[i]] for i in range(len(Rs))]
        b1=logit(base,y)
        if b1 is None: return None
        if med is None: return b1[1],None
        mz=zs([r[med] for r in Rs])
        b2=logit([base[i]+[mz[i]] for i in range(len(Rs))],y)
        if b2 is None: return None
        return b1[1],b2[1]
    idx0=list(range(n))
    tot,_=fit(idx0)
    tots=[f[0] for f in (fit(rng.integers(0,n,n)) for _ in range(2000)) if f]
    tl,th=np.percentile(tots,[2.5,97.5])
    print(f"   TOTAL effect of BS on AKI: OR={math.exp(tot):.2f} [{math.exp(tl):.2f},{math.exp(th):.2f}] per SD (bootstrap)")
    for med,lab in (("hyp","hypotension burden (PRESSURE)"),
                    ("lowpp","low-PP burden (FLOW)"),
                    ("occult","OCCULT low-PP at MAP>=65")):
        f=fit(idx0,med)
        if not f: continue
        t_,d_=f
        props=[]
        for _ in range(2000):
            fb=fit(rng.integers(0,n,n),med)
            if fb and fb[0]>0.05: props.append(100*(1-fb[1]/fb[0]))
        props=np.array([p for p in props if np.isfinite(p)])
        if len(props)>400:
            lo,hi=np.percentile(props,[2.5,97.5])
            print(f"   {lab:32s}: direct OR={math.exp(d_):.2f}  prop mediated={100*(1-d_/t_):5.1f}% [{lo:.0f}%,{hi:.0f}%] (n_boot={len(props)})")
        else:
            print(f"   {lab:32s}: direct OR={math.exp(d_):.2f}  prop mediated={100*(1-d_/t_):5.1f}%  (bootstrap unstable)")
if __name__=="__main__": main()
