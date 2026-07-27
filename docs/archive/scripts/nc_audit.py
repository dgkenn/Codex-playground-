#!/usr/bin/env python3
"""
Unified NEGATIVE-CONTROL AUDIT across three cross-method assay-noise instruments (Hb, glucose, potassium).
For each analyte we build the valid-direction near-threshold cohort and regress, on the flag Z (conditioning on
the contemporaneous other-method control):
  - the analyte's OWN reflexive treatment  -> RELEVANCE (should be strongly predicted; this is the first stage)
  - a matched UNRELATED treatment (NC)      -> EXCLUSION (a clean instrument must NOT predict it)
Clean analytes (Hb, glucose): NC ~ 0. Contaminated analyte (potassium, via hemolysis): NC FIRES.
This is the discriminating evidence that the NC gate separates valid from invalid assay-noise instruments,
catching what the age-balance gate misses.

NC choice avoids any physiologic link to the analyte:
  Hb  own=RBC(225168/220996)   NC=KCl(225166)     [K repletion is Hb-independent]
  Glu own=insulin(223258)      NC=RBC             [transfusion is glucose-independent]
  K   own=KCl(225166)          NC=RBC             [transfusion is K-independent; insulin AVOIDED (K-linked)]
"""
import csv, math
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
ITEM={'RBC':{'225168','220996'},'KCL':{'225166'},'INS':{'223258'}}
def ep(s):
    try: return datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_seq(path,lo,hi):
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
        if v<lo or v>hi: continue
        d.setdefault(row[0],[]).append((t,v))
    f.close()
    for k in d: d[k].sort()
    return d
def load_treat():
    d={k:{} for k in ITEM}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3: continue
            t=ep(row[2])
            if t is None: continue
            for k,ids in ITEM.items():
                if row[1] in ids: d[k].setdefault(row[0],[]).append(t)
    for k in d:
        for h in d[k]: d[k][h].sort()
    return d
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r: d[row[ix['hadm_id']]]=row[ix['subject_id']]
    return d
def load_age():
    d={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            try: d[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag,sc):
    c=(np.asarray(t,float)-flag)/sc; return np.column_stack([np.ones_like(c),c,c*c])

def build(flagfile,ctrlfile,lo,hi,flag,cmp,band,scale,adm,age,TR,own,nc):
    """flag on flagfile crossing 'flag' (cmp '<' or '>'), control=ctrlfile; band the CONTROL near flag."""
    fl=load_seq(flagfile,lo,hi); ct=load_seq(ctrlfile,lo,hi)
    rows=[]; MATCH=1.0
    for hadm,fseq in fl.items():
        if hadm not in adm or hadm not in ct: continue
        cseq=ct[hadm]; subj=adm[hadm]; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        ownt=TR[own].get(hadm,[]); nct=TR[nc].get(hadm,[])
        for (tf,vf) in fseq:
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tf)<=MATCH and abs(tc-tf)<bd: best=vc;bd=abs(tc-tf)
                if tc>tf+MATCH: break
            if best is None: continue
            z=1.0 if (vf<flag if cmp=='<' else vf>flag) else 0.0
            rows.append({'c':best,'z':z,
                         'own':1.0 if any(tf<=r<=tf+6 for r in ownt) else 0.0,
                         'nc':1.0 if any(tf<=r<=tf+6 for r in nct) else 0.0,'age':ag})
            break
    sub=[r for r in rows if band[0]<=r['c']<=band[1]]
    if len(sub)<300: return None
    z=np.array([r['z'] for r in sub]);C=cb([r['c'] for r in sub],flag,scale);X=np.column_stack([z,C])
    bo,so=ols(np.array([r['own'] for r in sub]),X)
    bn,sn=ols(np.array([r['nc'] for r in sub]),X)
    ba,_=ols(np.array([r['age'] for r in sub]),X)
    Fo=(bo[0]/so[0])**2 if so[0]>0 else 0
    return len(sub),bo[0],Fo,bn[0],sn[0],ba[0]

def main():
    adm=load_adm(); age=load_age(); TR=load_treat()
    print('=== Unified negative-control audit: does each flag predict its OWN vs an UNRELATED treatment? ===')
    print(f'{"analyte":10s} {"n":>6s} | {"own-tx (relevance)":>22s} | {"NC-tx (exclusion)":>26s} | balAge')
    specs=[
      ('Hb',     SD+'lab_hbbg.csv', SD+'lab_hb.csv', 3,20, 7.0,'<',(6.0,8.0),1.0,'RBC','KCL'),
      ('Glucose',SD+'lab_glu.csv',  SD+'lab_glubg.csv',10,900,180.0,'>',(150,220),50.0,'INS','RBC'),
      ('Potassium',SD+'lab_k.csv',  SD+'lab_kbg.csv', 1.5,8,3.5,'<',(3.0,4.0),1.0,'KCL','RBC'),
    ]
    for name,ff,cf,lo,hi,flag,cmp,band,sc,own,nc in specs:
        res=build(ff,cf,lo,hi,flag,cmp,band,sc,adm,age,TR,own,nc)
        if res is None: print(f'{name:10s} too small'); continue
        n,bo,Fo,bn,sn,ba=res
        ncsig='FIRES !!' if abs(bn)>1.96*sn else 'ok (~0)'
        print(f'{name:10s} {n:6d} | {own:>4s} {bo:+.3f} (F{Fo:4.0f})  | {nc:>4s} {bn:+.3f} (SE {sn:.3f}) {ncsig:9s} | {ba:+.2f}')
    print('\nClean instrument = strong own-tx first stage AND NC ~ 0. Hb/glucose pass; potassium NC fires')
    print('(hemolysis makes cross-method K discordance non-analytic) -> NC gate discriminates valid vs invalid.')

if __name__=='__main__':
    main()
