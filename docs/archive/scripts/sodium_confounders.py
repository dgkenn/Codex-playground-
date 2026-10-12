#!/usr/bin/env python3
"""
STRESS-TEST the sodium race-bias for confounding. Enumerate everything that affects the chem(indirect-ISE) vs
blood-gas(direct-ISE) sodium DISCORDANCE and test whether any explains the BLACK-WHITE differential:
  total protein, albumin, triglycerides (pseudo-dysnatremia); glucose (osmotic); BUN/creatinine (renal);
  true (blood-gas) Na LEVEL (is bias level-dependent + does level differ by race?); age; IV-fluid running near
  the draw (contamination). Multivariable adjustment + stratified robustness. The finding survives only if the
  race coefficient persists after adjusting for all measurable confounders.
Specificity control: GLUCOSE has a LARGER arterial-venous gap than sodium yet showed NO racial differential ->
argues the effect is not an arterial-venous artifact.
"""
import csv, math
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
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
def nearest(seq,t,win):
    best=np.nan;bd=win+1
    for (ts,v) in seq:
        if abs(ts-t)<=win and abs(ts-t)<bd: best=v;bd=abs(ts-t)
    return best
def load_race():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            raw=row[ix['race']].upper()
            d[row[ix['hadm_id']]]='BLACK' if 'BLACK' in raw else 'WHITE' if 'WHITE' in raw else 'OTHER'
    return d
def load_age():
    sub={};d={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            try: sub[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r: d[row[ix['hadm_id']]]=sub.get(row[ix['subject_id']],np.nan)
    return d
def load_saline():
    # NaCl 0.9%/hypertonic/LR running -> IV fluid presence times (inputevents subset in repletions? use na_tx + dextrose)
    d={}
    try: f=open(SD+'repletions.csv')
    except FileNotFoundError: return d
    r=csv.reader(f); next(r,None)
    FLU={'225158','225828','220949'}  # NaCl0.9, LR, D5 (fluids that could be running)
    for row in r:
        if len(row)<3 or row[1] not in FLU: continue
        t=ep(row[2])
        if t is not None: d.setdefault(row[0],[]).append(t)
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))

def main():
    chem=load_seq(SD+'lab_na.csv',100,190); bg=load_seq(SD+'lab_nabg.csv',100,190)
    cov={
      'totprot':load_seq(SD+'lab_totprot.csv',2,12),'alb':load_seq(SD+'lab_alb.csv',0.5,7),
      'trig':load_seq(SD+'lab_trig.csv',10,2000),'glu':load_seq(SD+'lab_glu.csv',10,900),
      'bun':load_seq(SD+'lab_bun.csv',1,200),'creat':load_seq(SD+'lab_creat.csv',0.1,20),
    }
    race=load_race(); age=load_age(); sal=load_saline()
    recs=[]
    for hadm,bseq in bg.items():
        if hadm not in chem or race.get(hadm) not in ('BLACK','WHITE'): continue
        cseq=chem[hadm]
        for (tb,vb) in bseq:
            best=nearest(cseq,tb,1.0)
            if best!=best: continue
            rec={'bias':best-vb,'black':1.0 if race[hadm]=='BLACK' else 0.0,'bgna':vb,'age':age.get(hadm,np.nan)}
            for k,seqd in cov.items(): rec[k]=nearest(seqd.get(hadm,[]),tb,24.0)
            st=sal.get(hadm,[]); rec['fluid']=1.0 if any(abs(tt-tb)<3 for tt in st) else 0.0
            recs.append(rec); break
    n=len(recs); print(f'n pairs (BLACK+WHITE)={n}')
    black=np.array([r['black'] for r in recs]); bias=np.array([r['bias'] for r in recs])
    b0,s0=ols(bias,np.column_stack([black,np.ones(n)]))
    print(f'\nUNADJUSTED racial differential: bias~BLACK = {b0[0]:+.3f} (SE {s0[0]:.3f}, z={b0[0]/s0[0]:+.1f})')

    # covariate means by race + coverage
    print('\n=== do candidate confounders differ by race? (mean [coverage%]) ===')
    for k in ['totprot','alb','trig','glu','bun','creat','bgna','age','fluid']:
        for g,v in [('WHITE',0.0),('BLACK',1.0)]:
            vals=[r[k] for r in recs if r['black']==v and r[k]==r[k]]
            cvg=100*len(vals)/max(1,sum(1 for r in recs if r['black']==v))
            m=np.mean(vals) if vals else float('nan')
            print(f'  {k:8s} {g}: {m:8.2f} [{cvg:3.0f}%]', end='   ')
        print()

    # multivariable adjustment (complete-case on the well-covered covariates; impute sparse ones with median)
    print('\n=== MULTIVARIABLE: does BLACK survive adjustment? ===')
    def build_X(keys):
        cols=[black]; names=['BLACK']
        for k in keys:
            col=np.array([r[k] for r in recs],float)
            med=np.nanmedian(col); col=np.where(np.isnan(col),med,col); col=(col-np.nanmean(col))/(np.nanstd(col)+1e-9)
            cols.append(col); names.append(k)
        cols.append(np.ones(n)); return np.column_stack(cols),names
    for label,keys in [('+ age,bgNa', ['age','bgna']),
                       ('+ renal (bun,creat)', ['age','bgna','bun','creat']),
                       ('+ glucose', ['age','bgna','bun','creat','glu']),
                       ('+ albumin', ['age','bgna','bun','creat','glu','alb']),
                       ('+ triglycerides', ['age','bgna','bun','creat','glu','alb','trig']),
                       ('+ TOTAL PROTEIN (full)', ['age','bgna','bun','creat','glu','alb','trig','totprot','fluid'])]:
        X,names=build_X(keys); b,s=ols(bias,X)
        print(f'  {label:28s} BLACK={b[0]:+.3f} (SE {s[0]:.3f}, z={b[0]/s[0]:+.1f})  n={n}')

    # complete-case with total protein (the key mediator) — restricted but unbiased
    tp=[i for i,r in enumerate(recs) if r['totprot']==r['totprot']]
    if len(tp)>300:
        ii=np.array(tp)
        Xa=np.column_stack([black[ii],np.ones(len(ii))]); ba,_=ols(bias[ii],Xa)
        cols=[black[ii]]
        for k in ['totprot','trig','glu','alb','bun','creat','bgna','age']:
            c=np.array([recs[i][k] for i in ii],float); c=np.where(np.isnan(c),np.nanmedian(c),c); c=(c-np.nanmean(c))/(np.nanstd(c)+1e-9); cols.append(c)
        cols.append(np.ones(len(ii))); Xb=np.column_stack(cols); bb,sb=ols(bias[ii],Xb)
        print(f'\n  COMPLETE-CASE w/ total protein (n={len(ii)}): BLACK unadj={ba[0]:+.3f} -> fully adj={bb[0]:+.3f} '
              f'(SE {sb[0]:.3f}, z={bb[0]/sb[0]:+.1f})')
        shrink=100*(1-abs(bb[0])/abs(ba[0])) if ba[0]!=0 else 0
        print(f'  -> adjustment shrinks racial differential by {shrink:.0f}%  '
              f'({"EXPLAINED by confounders" if shrink>60 else "SURVIVES (robust)" if abs(bb[0]/sb[0])>3 else "attenuated"})')
    print('\nVerdict: if BLACK survives full adjustment (|z|>3, modest shrink), the racial measurement bias is')
    print('robust to measured confounders -> a real finding. If it collapses, it was confounded.')

if __name__=='__main__':
    main()
