#!/usr/bin/env python3
"""
Potassium cross-method IV, SALVAGE attempt: exclude hemolyzed chemistry-K specimens.
potassium_crossmethod.py found the NC gate fires (K-flag predicts RBC transfusion, p<0.05) -- retired,
mechanism = hemolysis. We now have labevents flag/comments (labflag_k_flag.csv for chem K 50971,
labflag_kbg_flag.csv for bloodgas K 50822). Chem K carries explicit hemolysis comments (28,090 rows,
e.g. "HEMOLYSIS FALSELY ELEVATES K"); blood-gas K carries ZERO. Since the valid instrument direction is
Z=chem-flag (acted-upon measurement), we screen OUT any chem-K draw whose comments field flags hemolysis
before building the near-threshold cross-method pairs, and re-run the SAME design + NC gate.
If NC clears after screening: hemolysis was the whole mechanism -> instrument salvageable.
If NC still fires: hemolysis was A cause but not the only one -> stays retired.
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
KCL={'225166'}; RBC={'225168','220996'}
HEMOLYSIS_RX = re.compile(r'hemoly', re.IGNORECASE)
FLAG=3.5

def ep(s):
    try: return datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None

def load_chem_k_screened():
    """chem K (50971) sequence, EXCLUDING hemolysis-commented draws."""
    d={}; total=0; excluded=0
    with open(SD+'labflag_k_flag.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<5: continue
            hadm,ct,vn,flag,comments=row[0],row[1],row[2],row[3],row[4]
            if not hadm or not vn: continue
            t=ep(ct)
            if t is None: continue
            try: v=float(vn)
            except: continue
            if v<=0 or v>15: continue
            total+=1
            if HEMOLYSIS_RX.search(comments):
                excluded+=1; continue
            d.setdefault(hadm,[]).append((t,v))
    for k in d: d[k].sort()
    return d, total, excluded

def load_bg_k():
    d={}
    with open(SD+'labflag_kbg_flag.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<5: continue
            hadm,ct,vn=row[0],row[1],row[2]
            if not hadm or not vn: continue
            t=ep(ct)
            if t is None: continue
            try: v=float(vn)
            except: continue
            if v<=0 or v>15: continue
            d.setdefault(hadm,[]).append((t,v))
    for k in d: d[k].sort()
    return d

def load_treat(ids):
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in ids: continue
            t=ep(row[2])
            if t is not None: d.setdefault(row[0],[]).append(t)
    for k in d: d[k].sort()
    return d

def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
    return d
def load_pt():
    age={};dod={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        di=ix.get('dod',-1)
        for row in r:
            try: age[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
            if di>=0 and row[di]:
                dt=ep(row[di] if len(row[di])>10 else row[di]+' 00:00:00')
                if dt: dod[row[ix['subject_id']]]=dt
    return age,dod
def load_icu():
    s=set()
    try: f=open(SD+'icustays.csv')
    except FileNotFoundError: return s
    r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
    for row in r: s.add(row[ix['hadm_id']])
    f.close(); return s
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=(np.asarray(t,float)-flag); return np.column_stack([np.ones_like(c),c,c*c])

def main():
    chem, total, excluded = load_chem_k_screened()
    bg = load_bg_k()
    kcl = load_treat(KCL); rbc = load_treat(RBC)
    adm = load_adm(); age, dod = load_pt(); icu = load_icu()
    print('=== Potassium cross-method IV, HEMOLYSIS-SCREENED (chem-flag direction, control=bloodgas) ===')
    print(f'chem K rows: total={total} hemolysis-excluded={excluded} ({100*excluded/total:.1f}%) kept-hadms={len(chem)}')
    print(f'bloodgas K hadms: {len(bg)} | KCl-tx hadms: {len(kcl)} | RBC-tx hadms: {len(rbc)}\n')
    MATCH=1.0
    rows=[]
    for hadm, cseq in chem.items():
        if hadm not in adm: continue
        bseq = bg.get(hadm, [])
        if not bseq: continue
        subj=adm[hadm]['subject']; a=age.get(subj,np.nan)
        if math.isnan(a) or a<18: continue
        kt=kcl.get(hadm,[]); rt=rbc.get(hadm,[])
        for (tc,vc) in cseq:
            best=None;bd=MATCH+1
            for (tb,vb) in bseq:
                if abs(tb-tc)<=MATCH and abs(tb-tc)<bd: best=vb;bd=abs(tb-tc)
                if tb>tc+MATCH: break
            if best is None: continue
            dd=dod.get(subj)
            y30 = 1.0 if (dd is not None and 0<=(dd-tc)<=24*30) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            rows.append({'chem':vc,'bg':best,'z':1.0 if vc<FLAG else 0.0,
                         'd':1.0 if any(tc<=r<=tc+6 for r in kt) else 0.0,
                         'ncd':1.0 if any(tc<=r<=tc+6 for r in rt) else 0.0,
                         'yh':float(adm[hadm]['expire']),'y30':y30,'age':a,'icu':hadm in icu})
            break
    print(f'cross-method pairs built: {len(rows)}\n')
    def run(sub,ycol,label):
        if len(sub)<300: print(f'  {label:24s} n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r[ycol] for r in sub])
        ncd=np.array([r['ncd'] for r in sub])
        C=cb([r['bg'] for r in sub],FLAG);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        bn,sn=ols(ncd,X)
        nc0,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        ncsig='FIRES!!' if abs(bn[0])>1.96*sn[0] else 'ok (~0)'
        print(f'  {label:24s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc0[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] | balAge={ba[0]:+.2f} | NC-RBC={bn[0]:+.3f}({ncsig})')
    for band in [(3.0,4.0),(2.8,4.2)]:
        sub=[r for r in rows if band[0]<=r['bg']<=band[1]]
        print(f'-- band bloodgas-K(control) {band} (n={len(sub)}) --')
        run(sub,'yh','all, in-hospital')
        run([r for r in sub if r['icu']],'y30','ICU, 30-day')
    print('\nIf NC-RBC now reads ~0 (vs +0.024..+0.031 unscreened): hemolysis WAS the whole mechanism -> salvaged.')
    print('If NC still FIRES: hemolysis is A cause but not the only one -> instrument stays retired.')

if __name__=='__main__':
    main()
