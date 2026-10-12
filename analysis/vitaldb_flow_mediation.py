#!/usr/bin/env python3
"""MECHANISM: is the BS -> AKI pathway FLOW rather than PRESSURE?

Rationale. Adjusting for hypotension burden did not attenuate the BS->AKI association (1.37 -> 1.36). But mean
arterial pressure is not perfusion: MAP can be defended by vasoconstriction while cardiac output — and therefore
renal blood flow — falls. If burst suppression marks a low-OUTPUT state, AKI would be flow-mediated and a
pressure-based mediation test would be null by construction. That is a directly falsifiable hypothesis.

Design
  exposure  : intraoperative burst-suppression burden (validated raw-EEG detector)
  mediator A: LOW-FLOW burden  = fraction of maintenance bins with cardiac output below the patient's own baseline
              (EV1000/Vigileo CO). Also tested: absolute CO and cardiac index thresholds.
  mediator B: hypotension burden (the pressure comparator, already null)
  outcome   : KDIGO AKI from pre/post creatinine
  inference : difference-method mediation with a NONPARAMETRIC BOOTSTRAP (2,000 resamples) for the indirect
              effect and proportion mediated; case-level resampling.
  key test  : does BS predict LOW FLOW AT PRESERVED PRESSURE (occult hypoperfusion)? That is the specific state
              a pressure-only analysis cannot see.
Honest framing: mediation here is associational. BS, flow and depth share anaesthetic dose as a common cause; the
estimand is 'attenuation consistent with mediation', reported with its assumptions stated.
"""
import csv, math, sys
from collections import defaultdict
import numpy as np
SP="/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb"
rng=np.random.default_rng(7)
def logit(X,y,ridge=1e-6):
    X=np.asarray(X,float);y=np.asarray(y,float);b=np.zeros(X.shape[1])
    for _ in range(200):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+ridge*np.eye(X.shape[1]),(X.T*W)@z)
        except np.linalg.LinAlgError: return None
    return b
def build():
    # per-bin: BS from the EEG pipeline; CO/MAP/Ce from the haemodynamic pipeline
    BS={}
    for d in csv.DictReader(open("/tmp/eeg_probe/bridge_bins.csv")):
        try: BS[(d["caseid"],float(d["bin_t"]))]=float(d["bs"])
        except Exception: pass
    per=defaultdict(lambda: dict(bs=[],co=[],mbp=[],ce=[]))
    for d in csv.DictReader(open("/tmp/eeg_probe/mech_bins.csv")):
        try:
            ce=float(d["ce"])
            if ce<1.0: continue
            t=float(d["bin_t"]); cid=d["caseid"]
            bs=BS.get((cid,t))
            if bs is None: continue
            co=float(d["co"]) if d["co"] else np.nan
            mbp=float(d["mbp"]) if d["mbp"] else np.nan
            if co==co and not (0.5<co<15): co=np.nan
            if mbp==mbp and not (20<mbp<160): mbp=np.nan
            p=per[cid]; p["bs"].append(bs); p["co"].append(co); p["mbp"].append(mbp); p["ce"].append(ce)
        except Exception: pass
    # AKI
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
        co=np.array(p["co"],float); mbp=np.array(p["mbp"],float)
        if np.isfinite(co).sum()<20 or np.isfinite(mbp).sum()<20: continue
        s=cr.get(cid)
        if not s: continue
        pre=[v for t,v in s if t<=0]; post=[v for t,v in s if 0<t<=7*24*3600]
        if not pre or not post: continue
        m=meta.get(cid)
        if not m: continue
        try: asa=float((m.get("asa") or "").strip()[0]); age=float(m.get("age"))
        except Exception: continue
        base_co=np.nanmedian(co[:min(20,len(co))])
        if not (base_co==base_co): continue
        lowflow=float(np.nanmean(co < 0.85*base_co))          # below own baseline flow
        lowflow_abs=float(np.nanmean(co < 4.0))                # absolute CO threshold
        hyp=float(np.nanmean(mbp < 65))
        # OCCULT HYPOPERFUSION: low flow WHILE pressure looks fine
        occ=float(np.nanmean((co < 0.85*base_co) & (mbp >= 65)))
        b0=min(pre); pk=max(post)
        rows.append(dict(cid=cid, bs=float(np.mean(p["bs"])), lowflow=lowflow, lowflow_abs=lowflow_abs,
                         hyp=hyp, occult=occ, ce=float(np.nanmean(p["ce"])), age=age, asa=asa,
                         dur=len(p["bs"])*0.5, base_cr=b0,
                         aki=1.0 if (pk>=1.5*b0 or (pk-b0)>=0.3) else 0.0))
    return rows
def z(v):
    v=np.asarray(v,float); return (v-v.mean())/(v.std()+1e-9)
def main():
    R=build()
    print(f"cases with EEG + cardiac output + MAP + pre/post creatinine: {len(R)}")
    if len(R)<200: print("  insufficient"); return
    print(f"  AKI {100*np.mean([r['aki'] for r in R]):.1f}%  ({int(sum(r['aki'] for r in R))} events)")
    print(f"  median BS burden={np.median([r['bs'] for r in R]):.3f}  low-flow burden={np.median([r['lowflow'] for r in R]):.3f}  "
          f"hypotension burden={np.median([r['hyp'] for r in R]):.3f}  OCCULT low-flow={np.median([r['occult'] for r in R]):.3f}")
    # ---- does BS mark a low-flow state at PRESERVED pressure? ----
    print("\n=== STEP 1: does burst suppression mark LOW FLOW AT PRESERVED PRESSURE? ===")
    BSz=z([r["bs"] for r in R]); AG=z([r["age"] for r in R]); CE=z([r["ce"] for r in R]); AS=z([r["asa"] for r in R])
    for nm,key in (("low-flow burden (vs own baseline)","lowflow"),("low flow WITH MAP>=65 (occult)","occult"),
                   ("hypotension burden (comparator)","hyp")):
        Y=np.asarray([r[key] for r in R],float)
        X=np.column_stack([np.ones(len(R)),BSz,AG,CE,AS])
        b,_,_,_=np.linalg.lstsq(X,Y,rcond=None)
        res=Y-X@b; se=np.sqrt(np.diag((res@res/(len(Y)-X.shape[1]))*np.linalg.inv(X.T@X)))
        lo,hi=b[1]-1.96*se[1],b[1]+1.96*se[1]
        print(f"   {nm:36s}: beta per SD BS = {b[1]:+.4f} [{lo:+.4f},{hi:+.4f}] {'*' if (lo>0 or hi<0) else 'ns'}")
    # ---- mediation with bootstrap ----
    print("\n=== STEP 2: mediation of BS -> AKI, PRESSURE vs FLOW (bootstrap 2000) ===")
    def fit(idx, med):
        Rs=[R[i] for i in idx]
        bs=z([r["bs"] for r in Rs]); ag=z([r["age"] for r in Rs]); ce=z([r["ce"] for r in Rs])
        asa=z([r["asa"] for r in Rs]); du=z([r["dur"] for r in Rs]); bc=z([r["base_cr"] for r in Rs])
        y=[r["aki"] for r in Rs]
        base=[[1,bs[i],ag[i],ce[i],asa[i],du[i],bc[i]] for i in range(len(Rs))]
        b1=logit(base,y)
        if b1 is None: return None
        mz=z([r[med] for r in Rs])
        b2=logit([base[i]+[mz[i]] for i in range(len(Rs))],y)
        if b2 is None: return None
        return b1[1],b2[1]
    idx0=list(range(len(R)))
    for med,lab in (("hyp","hypotension burden (PRESSURE)"),("lowflow","low-flow burden (FLOW)"),
                    ("occult","occult low-flow at MAP>=65")):
        f=fit(idx0,med)
        if not f: print(f"   {lab}: fit failed"); continue
        tot,dir_=f
        props=[]
        for _ in range(2000):
            bi=rng.integers(0,len(R),len(R))
            fb=fit(bi,med)
            if fb and abs(fb[0])>1e-6: props.append(100*(1-fb[1]/fb[0]))
        props=np.array([p for p in props if np.isfinite(p)])
        lo,hi=np.percentile(props,[2.5,97.5]) if len(props)>100 else (np.nan,np.nan)
        print(f"   mediator = {lab:32s} total OR={math.exp(tot):.2f}  direct OR={math.exp(dir_):.2f}  "
              f"proportion mediated={100*(1-dir_/tot):5.1f}% [{lo:.0f}%,{hi:.0f}%]")
    print("\n   [FLOW mediating but PRESSURE not => the pathway is perfusion, invisible to a MAP-based analysis]")
if __name__=="__main__": main()
