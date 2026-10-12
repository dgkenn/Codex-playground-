import csv, numpy as np, math
from collections import defaultdict
BR=defaultdict(dict); HR={}
for d in csv.DictReader(open('bridge_bins.csv')):
    try:
        BR[d['caseid']][float(d['bin_t'])]=(float(d['bs']),
            float(d['mbp']) if d['mbp'] else np.nan, float(d['ce']) if d['ce'] else np.nan)
    except: pass
for d in csv.DictReader(open('bis_bins.csv')):
    try:
        v=float(d['hr']) if d['hr'] else np.nan
        if v==v: HR[(d['caseid'],float(d['bin_t']))]=v
    except: pass
def logit(X,y):
    X=np.asarray(X,float);y=np.asarray(y,float);b=np.zeros(X.shape[1])
    for _ in range(120):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except: break
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]));return b,np.sqrt(np.diag(cov))
SEQ={}
for cid,bd in BR.items():
    ts=sorted(t for t in bd if bd[t][2]==bd[t][2] and bd[t][2]>=1.0)
    if len(ts)>=32: SEQ[cid]=(set(ts),ts[20:],bd)
print(f"cases={len(SEQ)}")
def scan(kind,need_hr,label):
    print(f"\n{label}")
    for k in (-4,-2,-1,1,2,4):
        X=[];y=[]
        for cid,(tset,ts,bd) in SEQ.items():
            for t in ts:
                t2=t+30.0*k
                if t2 not in tset: continue
                bs,mbp,ce=bd[t]; bs2,mbp2,ce2=bd[t2]
                if mbp!=mbp: continue
                ha=HR.get((cid,t)); hb=HR.get((cid,t2))
                if need_hr and (ha is None or hb is None): continue
                if kind=='hyp':
                    if mbp2!=mbp2: continue
                    ev=1.0 if mbp2<65 else 0.0
                else:
                    if hb is None: continue
                    ev=1.0 if hb<50 else 0.0
                X.append([1,bs,mbp,ce]); y.append(ev)
        if len(X)<800 or sum(y)<40: print(f"   lag {k:+d}: insufficient (n={len(X)}, ev={sum(y) if y else 0})"); continue
        b,se=logit(X,y); lo=math.exp(b[1]-1.96*se[1]); hi=math.exp(b[1]+1.96*se[1])
        print(f"   lag {k:+d} ({30*k:+4d}s): BS OR={math.exp(b[1]):5.2f} [{lo:.2f},{hi:.2f}] n={len(X):6d} {'*' if (lo>1 or hi<1) else ''}")
scan('hyp',False,"HYPOTENSION (MBP<65) — all cases, TRUE 30s time lags")
scan('hyp',True, "HYPOTENSION — restricted to HR-available bins (fair comparison set)")
scan('brady',True,"BRADYCARDIA (HR<50) — same set (autonomic arm)")
