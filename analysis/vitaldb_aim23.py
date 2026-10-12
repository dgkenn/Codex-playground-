#!/usr/bin/env python3
"""Aim-2 (burst-suppression susceptibility ~ age x Ce) + Aim-3 (does EEG over-sedation/burst suppression PRECEDE
intraoperative hypotension, controlling for propofol Ce — the montage-robust Brown x C8 bridge). Uses bridge_bins.csv."""
import csv, numpy as np, statistics as st, math
from collections import defaultdict
BINS=defaultdict(list); STATIC={}
for d in csv.DictReader(open('/tmp/eeg_probe/bridge_bins.csv')):
    cid=d['caseid']
    def g(k):
        try: return float(d[k])
        except: return np.nan
    BINS[cid].append((g('bin_t'),g('bs'),g('alpha_db'),g('slow_db'),g('mbp'),g('ce')))
    STATIC[cid]=(g('age'), d['sex'])
print(f"cases={len(BINS)}  total bins={sum(len(v) for v in BINS.values())}")
def logit(X,y):
    X=np.array(X,float);y=np.array(y,float);b=np.zeros(X.shape[1])
    for _ in range(300):
        p=1/(1+np.exp(-np.clip(X@b,-30,30)));W=np.clip(p*(1-p),1e-9,None);z=X@b+(y-p)/W
        b=np.linalg.solve((X.T*W)@X+1e-6*np.eye(X.shape[1]),(X.T*W)@z)
    cov=np.linalg.inv((X.T*W)@X+1e-6*np.eye(X.shape[1]));return b,np.sqrt(np.diag(cov))
# ---- case-level summaries (maintenance = bins with ce>=1 and mbp present) ----
rows=[]
for cid,bl in BINS.items():
    age,sex=STATIC[cid]
    m=[b for b in bl if b[5]>=1.0 and b[4]==b[4]]  # ce>=1, mbp present
    if len(m)<10: continue
    bs=np.array([b[1] for b in m]); mbp=np.array([b[4] for b in m]); ce=np.array([b[5] for b in m])
    rows.append(dict(cid=cid,age=age,sex=sex,bs_mean=bs.mean(),bs_any=float((bs>0.1).mean()),
                     hypo_burden=float((mbp<65).mean()),mean_ce=ce.mean(),n=len(m)))
print(f"cases with >=10 maintenance bins: {len(rows)}")
# ---- AIM 2: BS susceptibility ~ age + Ce ----
print("\n=== AIM 2: case burst-suppression burden ~ age + mean_Ce ===")
R2=[r for r in rows if r['age']==r['age']]
b,se=logit([[1,r['age'],r['mean_ce']] for r in R2],[1.0 if r['bs_mean']>0.05 else 0.0 for r in R2])
for i,nm in enumerate(['intercept','age','mean_Ce']):
    print(f"  {nm:9s} OR={math.exp(b[i]):.3f} [{math.exp(b[i]-1.96*se[i]):.3f},{math.exp(b[i]+1.96*se[i]):.3f}] (P(>5% BS burden))")
for lo in (18,60,75):
    hi=lo+(42 if lo==18 else 15 if lo==60 else 30)
    s=[r['bs_mean'] for r in R2 if lo<=r['age']<hi]
    if len(s)>=5: print(f"    age {lo}-{hi}: median BS burden={st.median(s):.3f} (n={len(s)})")
# ---- AIM 3: does BS PRECEDE hypotension? cross-lagged, Ce-controlled ----
print("\n=== AIM 3: temporal precedence — burst suppression -> next-bin hypotension (MBP<65), Ce-controlled ===")
# build lagged pairs across all cases
fwd_X=[];fwd_y=[]   # predict hypo_{t+1} from bs_t, mbp_t, ce_t
rev_X=[];rev_y=[]   # predict bs_{t+1}>0.1 from hypo_t, bs_t, ce_t
for cid,bl in BINS.items():
    age,_=STATIC[cid]
    bl=sorted(bl)
    for i in range(len(bl)-1):
        t,bs,adb,sdb,mbp,ce=bl[i]; t2,bs2,a2,s2,mbp2,ce2=bl[i+1]
        if ce!=ce or ce<1.0: continue
        if mbp==mbp and mbp2==mbp2:
            fwd_X.append([1,bs,mbp,ce,age if age==age else 55]); fwd_y.append(1.0 if mbp2<65 else 0.0)
        if bs2==bs2 and mbp==mbp:
            rev_X.append([1,1.0 if mbp<65 else 0.0,bs,ce,age if age==age else 55]); rev_y.append(1.0 if bs2>0.1 else 0.0)
print(f"  forward pairs (bs_t -> hypo_t+1): {len(fwd_X)}; reverse (hypo_t -> bs_t+1): {len(rev_X)}")
if len(fwd_X)>100:
    b,se=logit(fwd_X,fwd_y); nm=['int','bs_t','mbp_t','ce_t','age']
    print("  FORWARD  P(MBP<65 at t+1) ~ bs_t + mbp_t + ce_t + age:")
    for i in (1,3): print(f"    {nm[i]:6s} OR={math.exp(b[i]):.3f} [{math.exp(b[i]-1.96*se[i]):.3f},{math.exp(b[i]+1.96*se[i]):.3f}]")
if len(rev_X)>100:
    b,se=logit(rev_X,rev_y); nm=['int','hypo_t','bs_t','ce_t','age']
    print("  REVERSE  P(BS>0.1 at t+1) ~ hypo_t + bs_t + ce_t + age:")
    print(f"    hypo_t OR={math.exp(b[1]):.3f} [{math.exp(b[1]-1.96*se[1]):.3f},{math.exp(b[1]+1.96*se[1]):.3f}]")
print("  [Aim-3 supported if FORWARD bs_t->hypo is significant AND stronger/cleaner than REVERSE hypo->bs,")
print("   i.e., EEG over-sedation precedes hypotension beyond the shared propofol dose (ce controlled).]")
# ---- case-level: BS burden -> hypotension burden, Ce+age adjusted ----
print("\n=== case-level: hypotension burden ~ BS burden + mean_Ce + age ===")
Rc=[r for r in rows if r['age']==r['age']]
def ols(X,y):
    X=np.array(X,float);y=np.array(y,float);b,_,_,_=np.linalg.lstsq(X,y,rcond=None)
    r=y-X@b;n,k=X.shape;se=np.sqrt(np.diag((r@r/(n-k))*np.linalg.inv(X.T@X)));return b,se
b,se=ols([[1,r['bs_mean'],r['mean_ce'],r['age']] for r in Rc],[r['hypo_burden'] for r in Rc])
for i,nm in enumerate(['intercept','BS_burden','mean_Ce','age']):
    print(f"  {nm:10s} {b[i]:+.4f} [{b[i]-1.96*se[i]:+.4f},{b[i]+1.96*se[i]:+.4f}]")
print("DONE")
