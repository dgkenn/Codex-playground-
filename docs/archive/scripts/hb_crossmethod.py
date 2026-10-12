#!/usr/bin/env python3
"""
Cross-method DISCORDANCE instrument for the Hb-transfusion IV (the bulletproof noise source).
The temporal noise-IV failed because consecutive-draw sigma (0.70 g/dL) is DRIFT (bleeding), not analytic.
Fix: use two INDEPENDENT measurements of the SAME blood at the SAME time — CBC Hb (51222) vs blood-gas Hb
(50811), drawn within 1h. Same time => ZERO biological drift => their difference is PURE analytic/method
noise = genuinely exogenous. Conditional on one method (the contemporaneous severity control), which side of
the flag the OTHER method reads is as-good-as-random.
Design: control = CBC Hb (contemporaneous independent true-Hb proxy); Z = 1(bloodgas Hb < 7);
D = RBC transfusion within 24h; Y = in-hospital mortality. Band on CBC near 7; balance on age.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
RBC = {'225168', '220996'}
def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_seq(path):
    d={}
    try: f=open(path)
    except FileNotFoundError: return d
    r=csv.reader(f); next(r,None)
    for row in r:
        if len(row)<3: continue
        t=ep(row[1])
        if t is None or not row[2] or not row[0]: continue
        try: v=float(row[2])
        except: continue
        if v<=0 or v>25: continue
        d.setdefault(row[0],[]).append((t,v))
    f.close()
    for k in d: d[k].sort()
    return d
def load_rbc():
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in RBC: continue
            t=ep(row[2])
            if t is not None: d.setdefault(row[0],[]).append(t)
    for k in d: d[k].sort()
    return d
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
    return d
def load_age():
    d={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        for row in r:
            try: d[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    cbc=load_seq(SD+'lab_hb.csv'); bg=load_seq(SD+'lab_hbbg.csv')
    tx=load_rbc(); adm=load_adm(); age=load_age()
    print('=== Hb cross-method DISCORDANCE IV (CBC vs blood-gas, same blood/time = pure analytic noise) ===')
    print(f'hadm with CBC Hb: {len(cbc)} | bloodgas Hb: {len(bg)} | RBC tx: {len(tx)}\n')
    # build near-simultaneous (within 1h) CBC/bloodgas pairs, pre-transfusion
    MATCH=1.0
    disc=[]; rows=[]
    for hadm, bseq in bg.items():
        if hadm not in adm or hadm not in cbc: continue
        cseq=cbc[hadm]; rt=tx.get(hadm,[]); first=rt[0] if rt else float('inf')
        ag=age.get(adm[hadm]['subject'],np.nan)
        if math.isnan(ag): continue
        ci=0
        for (tb,vb) in bseq:
            if tb>=first: break
            # nearest CBC within MATCH hours
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd:
                    best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None: continue
            disc.append(vb-best)
            # decision at this paired timepoint; use FIRST qualifying pair per hadm
            rows.append({'cbc':best,'bg':vb,'z':1.0 if vb<7.0 else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24 for r in rt) else 0.0,
                         'y':float(adm[hadm]['expire']),'age':ag})
            break
    if len(disc)<100:
        print('too few cross-method pairs:',len(disc)); return
    sig_analytic=np.std(disc)/math.sqrt(2)
    print(f'CROSS-METHOD sigma = {sig_analytic:.3f} g/dL (n_pairs={len(disc)})  '
          f'[vs 0.70 temporal; this is PURE analytic, no drift]')
    for lo,hi in [(6.3,7.7),(6.0,8.0)]:
        sub=[r for r in rows if lo<=r['cbc']<=hi]
        if len(sub)<300: print(f'  band[{lo},{hi}] n={len(sub)} too small'); continue
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r['y'] for r in sub]);C=cb([r['cbc'] for r in sub],7.0)
        X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        late=rf/fs if abs(fs)>1e-3 else float('nan')
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        print(f'  band[{lo},{hi}] n={len(sub):5d} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | FS={fs:+.3f}(F{F:4.0f}) | '
              f'flag-ITT={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} | balAge={ba[0]:+.2f}')
    print('\nTRICC/TRISS truth = NULL. If cross-method ITT ~0 with good balance => pure-analytic-noise instrument')
    print('recovers the RCT null where the temporal one (drift-confounded) found spurious harm. (Not yet TRICC-emulated.)')

if __name__=='__main__':
    main()
