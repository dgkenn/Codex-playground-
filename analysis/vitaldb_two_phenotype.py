"""TWO-PHENOTYPE TEST — reconciling our result with the Fritz/RCT hypoperfusion literature.
The interventional RCT (n=104) triggered ONLY when MAP was already BELOW that patient's baseline, and resolved
55% of those episodes by raising pressure => a hypoperfusion-associated BS phenotype.
Our normotensive-restricted result describes the population that protocol never enrolled.
PREDICTION: BS arising while MAP is AT/ABOVE the patient's own baseline should predict SUBSEQUENT hypotension;
BS arising while MAP is already BELOW baseline should not (the pressure fall already happened)."""
import csv, math, numpy as np
from collections import defaultdict
BD=defaultdict(dict)
for d in csv.DictReader(open('bridge_bins.csv')):
    try:
        t=float(d['bin_t']); ce=float(d['ce']) if d['ce'] else np.nan
        BD[d['caseid']][t]=(float(d['bs']), float(d['mbp']) if d['mbp'] else np.nan, ce,
                            float(d['age']) if d['age'] else np.nan)
    except: pass
def logit(X,y):
    X=np.asarray(X,float);y=np.asarray(y,float);b=np.zeros(X.shape[1])
    for _ in range(200):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except: break
    return b,np.sqrt(np.diag(np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]))))
# per-case baseline MAP = median of first 10 maintenance bins
base={}
for c,bd in BD.items():
    ts=sorted(t for t in bd if bd[t][2]==bd[t][2] and bd[t][2]>=1.0)
    v=[bd[t][1] for t in ts[:10] if bd[t][1]==bd[t][1]]
    if len(v)>=5: base[c]=float(np.median(v))
print(f"cases with baseline MAP: {len(base)}")
for k in (2,4):
    print(f"\n=== lag +{k} ({30*k}s): BS -> subsequent hypotension (MAP<65), split by MAP vs OWN baseline ===")
    for lab,cond in (("MAP >= baseline (normotensive-phenotype)",lambda m,b: m>=b),
                     ("MAP <  baseline (hypoperfusion-phenotype)",lambda m,b: m<b*0.9)):
        X=[];y=[]
        for c,bd in BD.items():
            if c not in base: continue
            b0=base[c]
            ts=sorted(t for t in bd if bd[t][2]==bd[t][2] and bd[t][2]>=1.0)
            if len(ts)<32: continue
            for t in ts[20:]:
                t2=t+30.0*k
                if t2 not in bd: continue
                bs,m,ce,age=bd[t]; _,m2,_,_=bd[t2]
                if m!=m or m2!=m2 or not cond(m,b0): continue
                X.append([1,bs,m,ce,age if age==age else 55]); y.append(1.0 if m2<65 else 0.0)
        if len(X)<500 or sum(y)<25: print(f"   {lab:44s} insufficient (n={len(X)}, ev={int(sum(y)) if y else 0})"); continue
        b,se=logit(X,y); lo,hi=math.exp(b[1]-1.96*se[1]),math.exp(b[1]+1.96*se[1])
        print(f"   {lab:44s} BS OR={math.exp(b[1]):5.2f} [{lo:.2f},{hi:.2f}] n={len(X):6d} ev={int(sum(y)):5d} {'*' if lo>1 else 'ns'}")
