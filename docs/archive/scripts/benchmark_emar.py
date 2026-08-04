#!/usr/bin/env python3
"""
RCT-BENCHMARK on real data: assay-noise IV / flag-ITT for lab-flag treatments, treatment sourced
hospital-wide from emar (emar_bench.csv). The make-or-break test: does the method recover the RCT
truth while NAIVE shows confounding? Tight <=24h control window; midpoint control; age-adjusted ITT.
Cases + RCT truth: RBC@Hb<7 (TRICC/TRISS null); Insulin@glu>180 (NICE-SUGAR: intensive HARMS);
Platelet@<10 (Stanworth null); Bicarb@HCO3<15 (settled null).
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
CONFIG = [
    ('RBC transfusion @Hb<7',  'hb',   'rbc',      7.0, '<', 0.6, 'TRICC/TRISS: restrictive non-inferior (~null)'),
    ('Insulin @glucose>180',   'glu',  'insulin',  180, '>', 25,  'NICE-SUGAR: intensive control HARMS'),
    ('Platelet @plt<10',       'plt',  'platelet', 10,  '<', 5,   'Stanworth TOPPS: 10k safe (~null)'),
    ('Bicarbonate @HCO3<15',   'hco3', 'bicarb',   15,  '<', 3,   'settled: no benefit (~null)'),
]

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def load_labseq(key):
    d = {}
    try: f = open(SD+f'lab_{key}.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3: continue
        t = ep(row[1])
        if t is None or not row[2] or not row[0]: continue
        try: v = float(row[2])
        except ValueError: continue
        d.setdefault(row[0], []).append((t, v))
    f.close()
    for k in d: d[k].sort()
    return d

def load_tx(cls):
    d = {}
    try: f = open(SD+'emar_bench.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3 or row[2] != cls: continue
        t = ep(row[1])
        if t is not None: d.setdefault(row[0], []).append(t)
    f.close()
    for k in d: d[k].sort()
    return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            d[row[ix['hadm_id']]] = {'subject':row[ix['subject_id']],
                'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
    return d

def load_age():
    d = {}
    with open(SD+'patients.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            try: d[row[ix['subject_id']]] = float(row[ix['anchor_age']])
            except Exception: pass
    return d

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def cb(t, flag):
    c = np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c), c, c*c])

def run(name, key, cls, flag, direction, hw, truth, adm, age):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:26s}: lab_{key}.csv missing — SKIP'); return
    tx = load_tx(cls)
    if not tx:
        print(f'  {name:26s}: no {cls} in emar_bench — SKIP'); return
    # sigma from consecutive pairs <=24h (analytic-noise proxy)
    diffs=[]
    for hadm,seq in seqs.items():
        for i in range(len(seq)-1):
            if 0<seq[i+1][0]-seq[i][0]<=24: diffs.append(seq[i+1][1]-seq[i][1])
    sig=np.std(diffs)/math.sqrt(2) if len(diffs)>100 else float('nan')
    cross=(lambda v:v<flag) if direction=='<' else (lambda v:v>flag)
    rows=[]
    for hadm,seq in seqs.items():
        if hadm not in adm: continue
        rt=tx.get(hadm,[]); first=rt[0] if rt else float('inf')
        pre=[(t,v) for (t,v) in seq if t<first]
        if len(pre)<2: continue
        (t1,m1),(t2,m2)=pre[0],pre[1]
        if (t2-t1)>24: continue   # tight window
        ag=age.get(adm[hadm]['subject'],np.nan)
        if math.isnan(ag): continue
        rows.append({'mid':(m1+m2)/2,'m2':m2,'z':1.0 if cross(m2) else 0.0,
                     'd':1.0 if any(t2<=r<=t2+24 for r in rt) else 0.0,
                     'y':float(adm[hadm]['expire']),'age':ag})
    sub=[r for r in rows if abs(r['mid']-flag)<=hw]
    if len(sub)<300:
        print(f'  {name:26s}: n={len(sub)} in-band (cohort {len(rows)}) — too small'); return
    z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub])
    y=np.array([r['y'] for r in sub]);C=cb([r['mid'] for r in sub],flag)
    agec=(np.array([r['age'] for r in sub])-60)/10
    Xb=np.column_stack([z,C]); Xa=np.column_stack([z,C,agec,agec*agec])
    bfs,sfs=ols(d,Xb); brf,srf=ols(y,Xb); fs,rf=bfs[0],brf[0]
    F=(fs/sfs[0])**2 if sfs[0]>0 else 0
    ba,_=ols(np.array([r['age'] for r in sub]),Xb)
    brfa,_=ols(y,Xa); rfa=brfa[0]
    late=rf/fs if abs(fs)>1e-3 else float('nan')
    nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))  # naive
    print(f'  {name:26s} n={len(sub):6d} tx={d.mean():.3f} sig={sig:.3g} | NAIVE={nc[0]:+.4f} | '
          f'FS={fs:+.3f}(F{F:5.0f}) | ITT={rf:+.5f}({srf[0]:.5f}) ITTadj={rfa:+.5f} | LATE={late:+.3f} | '
          f'bal={ba[0]:+.2f}yr | truth: {truth}')

def main():
    print('=== RCT-BENCHMARK (assay-noise IV, treatment from emar) — does method recover RCT truth? ===')
    print('NAIVE=confounded D->mortality; ITT=flag-ITT; ITTadj=age-adjusted; recover ~0 (null cases)\n')
    adm=load_adm(); age=load_age()
    for c in CONFIG:
        run(c[0],c[1],c[2],c[3],c[4],c[5],c[6],adm,age)
    print('\nDONE. Null cases: method ITT ~0 while naive shows harm = recovers RCT truth. Insulin: expect harm.')

if __name__=='__main__':
    main()
