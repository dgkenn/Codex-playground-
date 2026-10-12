"""Does BS precede a fall in SVR (vasodilation) or CO (cardiac depression)?"""
import csv, math, numpy as np
from collections import defaultdict
BS={}
for d in csv.DictReader(open('bridge_bins.csv')):
    try: BS[(d['caseid'],float(d['bin_t']))]=float(d['bs'])
    except: pass
M=defaultdict(dict)
for d in csv.DictReader(open('mech_bins.csv')):
    try:
        t=float(d['bin_t'])
        M[d['caseid']][t]=dict(mbp=float(d['mbp']), ce=float(d['ce']),
            svr=float(d['svr']) if d['svr'] else np.nan,
            co=float(d['co']) if d['co'] else np.nan)
    except: pass
ov=[c for c in M if any((c,t) in BS for t in M[c])]
print(f"mech cases={len(M)}; overlapping with EEG/BS data={len(ov)}")
nsvr=sum(1 for c in ov for t in M[c] if M[c][t]['svr']==M[c][t]['svr'])
nco =sum(1 for c in ov for t in M[c] if M[c][t]['co']==M[c][t]['co'])
print(f"bins with SVR={nsvr}  with CO={nco}")
def ols(X,y):
    X=np.asarray(X,float);y=np.asarray(y,float)
    b,_,_,_=np.linalg.lstsq(X,y,rcond=None)
    r=y-X@b;n,k=X.shape
    se=np.sqrt(np.diag((r@r/(n-k))*np.linalg.inv(X.T@X)));return b,se
for var in ('svr','co'):
    print(f"\n=== does BS at t predict CHANGE in {var.upper()} at t+k?  (adj current {var}, MAP, Ce) ===")
    for k in (-4,-2,2,4):
        X=[];y=[]
        for c in ov:
            tset=M[c]
            for t in tset:
                t2=t+30.0*k
                if t2 not in tset: continue
                bs=BS.get((c,t))
                if bs is None: continue
                a=tset[t]; b2=tset[t2]
                if a[var]!=a[var] or b2[var]!=b2[var]: continue
                if a['mbp']!=a['mbp'] or a['ce']<1.0: continue
                X.append([1,bs,a[var],a['mbp'],a['ce']]); y.append(b2[var]-a[var])
        if len(X)<200: print(f"   lag {k:+d}: n={len(X)} insufficient"); continue
        b,se=ols(X,y)
        lo,hi=b[1]-1.96*se[1],b[1]+1.96*se[1]
        sig='*' if (lo>0 or hi<0) else ' '
        print(f"   lag {k:+d} ({30*k:+4d}s): d{var} per unit BS = {b[1]:+8.2f} [{lo:+.2f},{hi:+.2f}] n={len(X):5d} {sig}")
print("\n[VASODILATION mechanism => BS predicts SVR FALL at positive lags, with CO preserved/rising]")
print("[CARDIAC mechanism      => BS predicts CO FALL at positive lags]")
