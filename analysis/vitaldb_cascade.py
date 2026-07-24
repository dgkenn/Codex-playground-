#!/usr/bin/env python3
"""IDEA #2 — CORTICAL -> AUTONOMIC -> PRESSURE CASCADE (pre-registered ORDER prediction).
The flagship showed burst suppression precedes hypotension. This asks the deeper mechanistic question:
is the pressure fall part of an ORDERED cascade in which the cortical event comes first, the autonomic
(heart-rate) response next, and the pressure fall last?
Independent instruments: EEG (cortex), ECG-derived HR (autonomic), arterial line (pressure) - three separate sensors.
Pre-registered prediction: lag(BS->HR change) <= lag(BS->MBP fall), and both forward >> reverse."""
import csv, numpy as np, math
from collections import defaultdict
BR=defaultdict(dict)
for d in csv.DictReader(open('/tmp/eeg_probe/bridge_bins.csv')):
    try:
        BR[d['caseid']][float(d['bin_t'])]=dict(bs=float(d['bs']),
            mbp=float(d['mbp']) if d['mbp'] else np.nan, ce=float(d['ce']) if d['ce'] else np.nan,
            age=float(d['age']) if d['age'] else np.nan)
    except: pass
for d in csv.DictReader(open('/tmp/eeg_probe/bis_bins.csv')):
    try:
        t=float(d['bin_t'])
        if t in BR[d['caseid']]: BR[d['caseid']][t]['hr']=float(d['hr']) if d['hr'] else np.nan
    except: pass
seqs={}
for cid,bd in BR.items():
    ts=sorted(bd)
    s=[(t,bd[t]) for t in ts if bd[t].get('ce',np.nan)>=1.0 and 'hr' in bd[t]]
    if len(s)>=15: seqs[cid]=s[20:] if len(s)>35 else s
print(f"cases with EEG+HR+MBP+Ce maintenance bins: {len(seqs)}; bins={sum(len(v) for v in seqs.values())}")
def logit(X,y):
    X=np.array(X,float);y=np.array(y,float);b=np.zeros(X.shape[1])
    for _ in range(250):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except: break
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]));return b,np.sqrt(np.diag(cov))
def lagscan(outcome, label):
    """outcome(dict_now, dict_future)->0/1 event; scan lag k."""
    print(f"\n== lag scan: burst suppression -> {label} ==")
    out=[]
    for k in range(-4,5):
        X=[];y=[]
        for cid,s in seqs.items():
            for i in range(len(s)):
                j=i+k
                if j<0 or j>=len(s): continue
                a=s[i][1]; b2=s[j][1]
                ev=outcome(a,b2)
                if ev is None: continue
                X.append([1,a['bs'],a.get('mbp',np.nan),a.get('hr',np.nan),a['ce']]); y.append(ev)
        X=[r for r in X];
        good=[i for i,r in enumerate(X) if not any(np.isnan(v) for v in r)]
        if len(good)<300: continue
        Xg=[X[i] for i in good]; yg=[y[i] for i in good]
        if sum(yg)<20: continue
        b,se=logit(Xg,yg); o=math.exp(b[1])
        sig='*' if (b[1]-1.96*se[1])>0 else ' '
        print(f"   lag {k:+d} ({30*k:+4d}s): OR={o:5.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}] n={len(good)} {sig}")
        out.append((k,o,sig))
    return out
# outcomes
mbp_drop = lambda a,b2: (1.0 if b2['mbp']<65 else 0.0) if (a['mbp']==a['mbp'] and b2['mbp']==b2['mbp']) else None
hr_drop  = lambda a,b2: (1.0 if (a['hr']-b2['hr'])>=5 else 0.0) if (a.get('hr',np.nan)==a.get('hr',np.nan) and b2.get('hr',np.nan)==b2.get('hr',np.nan)) else None
brady    = lambda a,b2: (1.0 if b2['hr']<50 else 0.0) if (b2.get('hr',np.nan)==b2.get('hr',np.nan)) else None
L_hr=lagscan(hr_drop, "HEART-RATE FALL (>=5 bpm)   [autonomic]")
L_mbp=lagscan(mbp_drop, "HYPOTENSION (MBP<65)        [pressure]")
L_br=lagscan(brady, "BRADYCARDIA (HR<50)         [autonomic, absolute]")
def firstsig(L):
    s=[k for k,o,sig in L if sig=='*' and k>0]
    return min(s) if s else None
print("\n== CASCADE ORDER (pre-registered prediction: autonomic lag <= pressure lag) ==")
print(f"   first significant POSITIVE lag, HR fall     : {firstsig(L_hr)}")
print(f"   first significant POSITIVE lag, hypotension : {firstsig(L_mbp)}")
print(f"   first significant POSITIVE lag, bradycardia : {firstsig(L_br)}")
print("   [ordered cascade supported if the autonomic response appears at an EQUAL or EARLIER lag than the pressure fall,")
print("    and negative lags are null for all arms]")
print("DONE")
