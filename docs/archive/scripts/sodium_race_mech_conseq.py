#!/usr/bin/env python3
"""
Sodium race-bias: MECHANISM (does albumin/protein mediate the BLACK-WHITE differential?) + CONSEQUENCE
(at the SAME true [blood-gas] sodium, does chem-based dysnatremia classification & Na-directed treatment differ
by race?). These decide whether the finding is NEJM-tier (harm) or a lab note (bias only).
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
def load_race():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            raw=row[ix['race']].upper()
            d[row[ix['hadm_id']]]='BLACK' if 'BLACK' in raw else 'WHITE' if 'WHITE' in raw else 'OTHER'
    return d
def load_na_tx():
    d={}
    with open(SD+'na_tx.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3: continue
            t=ep(row[1])
            if t is None: continue
            grp='hyper' if row[2] in ('hyper3','hyper234') else ('free' if row[2] in ('freewater','sterilewater') else None)
            if grp: d.setdefault(row[0],[]).append((t,grp))
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))

def main():
    chem=load_seq(SD+'lab_na.csv',100,190); bg=load_seq(SD+'lab_nabg.csv',100,190)
    alb=load_seq(SD+'lab_alb.csv',0.5,7); race=load_race(); tx=load_na_tx()
    recs=[]
    for hadm,bseq in bg.items():
        if hadm not in chem or race.get(hadm) not in ('BLACK','WHITE'): continue
        cseq=chem[hadm]; aseq=alb.get(hadm,[])
        for (tb,vb) in bseq:
            best=None;bd=1.0+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=1.0 and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+1.0: break
            if best is None: continue
            # nearest albumin within 24h
            av=np.nan; abd=24.1
            for (ta,va) in aseq:
                if abs(ta-tb)<24 and abs(ta-tb)<abd: av=va;abd=abs(ta-tb)
            # Na treatment within +24h of this pair
            treated=any(tb<=tt<=tb+24 for (tt,g) in tx.get(hadm,[]))
            recs.append({'chem':best,'bg':vb,'bias':best-vb,'black':1.0 if race[hadm]=='BLACK' else 0.0,
                         'alb':av,'tx':1.0 if treated else 0.0})
            break
    n=len(recs); black=np.array([r['black'] for r in recs])
    print(f'n pairs (BLACK+WHITE)={n}, black={int(black.sum())}, white={int(n-black.sum())}')

    # ---- MECHANISM: bias ~ black, then + albumin ----
    print('\n=== MECHANISM: does albumin mediate the BLACK-WHITE bias? ===')
    bias=np.array([r['bias'] for r in recs])
    b1,s1=ols(bias, np.column_stack([black, np.ones(n)]))
    print(f'  bias ~ BLACK: coef={b1[0]:+.3f} (SE {s1[0]:.3f})  [unadjusted racial differential]')
    havealb=[i for i,r in enumerate(recs) if r['alb']==r['alb']]
    if len(havealb)>500:
        ii=np.array(havealb); al=np.array([recs[i]['alb'] for i in ii])
        b2,s2=ols(bias[ii], np.column_stack([black[ii], al, np.ones(len(ii))]))
        b0,_=ols(bias[ii], np.column_stack([black[ii], np.ones(len(ii))]))
        print(f'  (albumin subset n={len(ii)}): bias~BLACK alone={b0[0]:+.3f}; +albumin -> BLACK={b2[0]:+.3f} '
              f'(SE {s2[0]:.3f}), albumin coef={b2[1]:+.3f}')
        shrink=100*(1-abs(b2[0])/abs(b0[0])) if b0[0]!=0 else 0
        print(f'  -> albumin adjustment shrinks the racial differential by {shrink:.0f}% '
              f'({"mechanism supported" if shrink>25 else "albumin alone insufficient (total protein/globulin likely)"})')
    # mean albumin by race
    for g,v in [('BLACK',1.0),('WHITE',0.0)]:
        a=[r['alb'] for r in recs if r['black']==v and r['alb']==r['alb']]
        if a: print(f'    mean albumin {g}: {np.mean(a):.2f} g/dL (n={len(a)})')

    # ---- CONSEQUENCE: at matched TRUE (blood-gas) Na, chem-based misclassification + treatment by race ----
    print('\n=== CONSEQUENCE: at matched true (blood-gas) sodium, chem misclassification + treatment by race ===')
    print('  true-Na band | race | n | chem<135 (false-hypo label) | chem>145 (false-hyper) | Na-tx rate')
    for lo,hi in [(135,140),(140,145),(145,150)]:
        for g,v in [('WHITE',0.0),('BLACK',1.0)]:
            sub=[r for r in recs if lo<=r['bg']<hi and r['black']==v]
            if len(sub)<80: continue
            fh=np.mean([r['chem']<135 for r in sub]); fH=np.mean([r['chem']>145 for r in sub])
            txr=np.mean([r['tx'] for r in sub])
            print(f'  [{lo},{hi}) | {g:5s} | n={len(sub):5d} | {fh:.3f} | {fH:.3f} | {txr:.3f}')
    print('\nIf, at the SAME true Na, Black patients have systematically different chem-based dysnatremia labels')
    print('AND different Na-directed treatment rates -> differential care from a biased measurement (the harm).')

if __name__=='__main__':
    main()
