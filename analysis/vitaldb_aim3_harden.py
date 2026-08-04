#!/usr/bin/env python3
"""Adversarially harden Aim-3 (BS precedes hypotension). Decisive tests: (1) survive WITHIN narrow Ce strata (kills
the 'it's just dose' confound); (2) lag structure — does BS LEAD hypotension (peak assoc at positive lag)?;
(3) add dose-change (dCe) covariate; (4) BS-specific vs general slow-wave over-sedation; (5) exclude induction."""
import csv, numpy as np, math
from collections import defaultdict
BINS=defaultdict(list); STATIC={}
for d in csv.DictReader(open('/tmp/eeg_probe/bridge_bins.csv')):
    def g(k):
        try: return float(d[k])
        except: return np.nan
    BINS[d['caseid']].append((g('bin_t'),g('bs'),g('alpha_db'),g('slow_db'),g('mbp'),g('ce')))
    STATIC[d['caseid']]=g('age')
def logit(X,y):
    X=np.array(X,float);y=np.array(y,float);b=np.zeros(X.shape[1])
    for _ in range(300):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        try: b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
        except: break
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]));return b,np.sqrt(np.diag(cov))
# assemble bin sequences per case (sorted, maintenance ce>=1, exclude first 20 bins=10min induction)
seqs={}
for cid,bl in BINS.items():
    bl=sorted(bl); bl=[b for b in bl if b[5]==b[5] and b[5]>=1.0][20:]
    if len(bl)>=12: seqs[cid]=bl
print(f"cases (post-induction, >=12 maint bins): {len(seqs)}")
# ---- (1) forward BS->hypo WITHIN Ce strata ----
print("\n(1) FORWARD P(MBP<65 at t+1) ~ bs_t (+mbp_t,age) WITHIN Ce strata [kills dose confound]:")
for lo,hi in [(1,2.5),(2.5,3.5),(3.5,10)]:
    X=[];y=[]
    for cid,bl in seqs.items():
        age=STATIC[cid]
        for i in range(len(bl)-1):
            t,bs,adb,sdb,mbp,ce=bl[i]; mbp2=bl[i+1][4]
            if not (lo<=ce<hi): continue
            if mbp==mbp and mbp2==mbp2:
                X.append([1,bs,mbp,age if age==age else 55]); y.append(1.0 if mbp2<65 else 0.0)
    if len(X)>200:
        b,se=logit(X,y); print(f"   Ce[{lo},{hi}): n={len(X)} bs_t OR={math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]")
# ---- (2) lag structure: assoc of bs(t) with hypotension(t+k) ----
print("\n(2) LAG STRUCTURE — logistic P(MBP<65 at t+k) ~ bs_t + mbp_t (k=-4..+4 bins, 30s each):")
for k in range(-4,5):
    X=[];y=[]
    for cid,bl in seqs.items():
        for i in range(len(bl)):
            j=i+k
            if j<0 or j>=len(bl): continue
            bs=bl[i][1]; mbp=bl[i][4]; mbpk=bl[j][4]
            if mbp==mbp and mbpk==mbpk:
                X.append([1,bs,mbp]); y.append(1.0 if mbpk<65 else 0.0)
    if len(X)>200:
        b,se=logit(X,y); star='*' if (b[1]-1.96*se[1])>0 else ' '
        print(f"   lag {k:+d} ({30*k:+d}s): bs OR={math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}] {star}")
print("   [precedence supported if OR peaks/rises at POSITIVE lag (bs now -> hypotension later) vs negative]")
# ---- (3) add dose-change dCe covariate ----
print("\n(3) FORWARD with dose-change (dCe=ce_t - ce_t-1) covariate [ramp confound]:")
X=[];y=[]
for cid,bl in seqs.items():
    age=STATIC[cid]
    for i in range(1,len(bl)-1):
        bs=bl[i][1];mbp=bl[i][4];ce=bl[i][5];dce=bl[i][5]-bl[i-1][5];mbp2=bl[i+1][4]
        if mbp==mbp and mbp2==mbp2 and dce==dce:
            X.append([1,bs,mbp,ce,dce,age if age==age else 55]);y.append(1.0 if mbp2<65 else 0.0)
if len(X)>200:
    b,se=logit(X,y);print(f"   n={len(X)} bs_t OR={math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]  dCe OR={math.exp(b[4]):.2f}")
# ---- (4) BS-specific vs general slow-wave over-sedation ----
print("\n(4) is it BS-specific? forward with slow_db added:")
X=[];y=[]
for cid,bl in seqs.items():
    for i in range(len(bl)-1):
        bs=bl[i][1];sdb=bl[i][3];mbp=bl[i][4];ce=bl[i][5];mbp2=bl[i+1][4]
        if mbp==mbp and mbp2==mbp2 and sdb==sdb:
            X.append([1,bs,sdb,mbp,ce]);y.append(1.0 if mbp2<65 else 0.0)
if len(X)>200:
    b,se=logit(X,y);print(f"   n={len(X)} bs_t OR={math.exp(b[1]):.2f} [{math.exp(b[1]-1.96*se[1]):.2f},{math.exp(b[1]+1.96*se[1]):.2f}]  slow_db OR/dB={math.exp(b[2]):.3f}")
print("DONE")
