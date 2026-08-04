#!/usr/bin/env python3
"""
Cross-method SODIUM assay-noise IV gate test — the make-or-break for whether we have a bulletproof instrument
pointed at an OPEN clinical question (dysnatremia management, not settled by a mortality RCT).

Two same-time Na measurements: chemistry (50983, lab_na, INDIRECT ISE) vs blood-gas (50824, lab_nabg, DIRECT ISE)
within 1h. Key Na-specific threat = PSEUDOHYPONATREMIA: indirect-ISE chem Na reads falsely LOW with high
lipids/protein; direct-ISE blood-gas Na does not -> their discordance is partly a lipid/protein artifact
(correlated with acuity), NOT pure analytic noise -- the sodium analogue of potassium's hemolysis. The NC gate
is exactly what reveals this.

Two reflexive decisions, each with an observable treatment:
  HYPOnatremia: flag Na<130 -> hypertonic saline (225161 NaCl3% + 228341 NaCl23.4%)
  HYPERnatremia: flag Na>150 -> free water (225797 + 225944 sterile water)
For each: test BOTH instrument directions (flag on the acted-upon measurement), report cross-method sigma,
first stage (own tx), flag-ITT (30-day mortality), balance (age), and NC gate (does the flag predict RBC
transfusion -- a Na-independent treatment?). Clean instrument = strong correctly-signed FS AND NC ~ 0.
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
def load_na_tx():
    """hadm -> {'hyper':[t...], 'free':[t...]} from na_tx.csv (hadm_id,starttime,drug)."""
    d={}
    with open(SD+'na_tx.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3: continue
            t=ep(row[1])
            if t is None: continue
            grp = 'hyper' if row[2] in ('hyper3','hyper234') else ('free' if row[2] in ('freewater','sterilewater') else None)
            if grp is None: continue
            d.setdefault(row[0],{}).setdefault(grp,[]).append(t)
    for h in d:
        for g in d[h]: d[h][g].sort()
    return d
def load_rbc():
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in ('225168','220996'): continue
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

def build(chem,bg,tx,rbc,adm,age,dod,flag,cmp,txgrp,win=6.0):
    MATCH=1.0; disc=[]; rows=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in chem: continue
        cseq=chem[hadm]; subj=adm[hadm]['subject']; a=age.get(subj,np.nan)
        if math.isnan(a) or a<18: continue
        tg=tx.get(hadm,{}).get(txgrp,[]); rt=rbc.get(hadm,[])
        for (tb,vb) in bseq:
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None: continue
            disc.append(vb-best)
            dd=dod.get(subj)
            y30=1.0 if (dd is not None and 0<=(dd-tb)<=24*30) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            rows.append({'chem':best,'bg':vb,
                         'zc':1.0 if (best<flag if cmp=='<' else best>flag) else 0.0,   # chem-flag
                         'zb':1.0 if (vb<flag if cmp=='<' else vb>flag) else 0.0,        # bloodgas-flag
                         'd':1.0 if any(tb<=r<=tb+win for r in tg) else 0.0,
                         'ncd':1.0 if any(tb<=r<=tb+win for r in rt) else 0.0,
                         'yh':float(adm[hadm]['expire']),'y30':y30,'age':a})
            break
    return disc, rows

def run(rows,band,flag,side,ycol='y30'):
    ck='chem' if side=='chem' else 'bg'; zk='zc' if side=='chem' else 'zb'; ctrl='bg' if side=='chem' else 'chem'
    sub=[r for r in rows if band[0]<=r[ck]<=band[1]]
    if len(sub)<300: print(f'    {side}-flag n={len(sub)} too small'); return
    z=np.array([r[zk] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r[ycol] for r in sub])
    ncd=np.array([r['ncd'] for r in sub])
    C=cb([r[ctrl] for r in sub],flag);X=np.column_stack([z,C])
    bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
    F=(fs/sfs[0])**2 if sfs[0]>0 else 0
    ba,_=ols(np.array([r['age'] for r in sub]),X)
    bn,sn=ols(ncd,X)
    lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
    ncsig='FIRES!!' if abs(bn[0])>1.96*sn[0] else 'ok(~0)'
    print(f'    {side:4s}-flag (ctrl={ctrl}) n={len(sub):5d} tx={d.mean():.3f} mort={y.mean():.3f} | '
          f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] | balAge={ba[0]:+.2f} | NC-RBC={bn[0]:+.3f}({ncsig})')

def main():
    chem=load_seq(SD+'lab_na.csv',100,190); bg=load_seq(SD+'lab_nabg.csv',100,190)
    tx=load_na_tx(); rbc=load_rbc(); adm=load_adm(); age,dod=load_pt()
    print('=== Cross-method SODIUM IV gate test (chem 50983 indirect-ISE vs blood-gas 50824 direct-ISE) ===')
    print(f'chem:{len(chem)} bg:{len(bg)} Na-tx hadms:{len(tx)} RBC-tx:{len(rbc)}\n')
    print('### HYPONATREMIA: flag Na<130 -> hypertonic saline (own tx); NC=RBC ###')
    disc,rows=build(chem,bg,tx,rbc,adm,age,dod,130.0,'<','hyper')
    sig=np.std(disc)/math.sqrt(2)
    print(f'  cross-method Na sigma = {sig:.3f} mEq/L (n_pairs={len(disc)})  [pure analytic if no pseudo-hypoNa artifact]')
    for band in [(122,138),(120,140)]:
        print(f'  -- band control-Na {band} --')
        run(rows,band,130.0,'chem'); run(rows,band,130.0,'bg')
    print('\n### HYPERNATREMIA: flag Na>150 -> free water (own tx); NC=RBC ###')
    disc2,rows2=build(chem,bg,tx,rbc,adm,age,dod,150.0,'>','free')
    for band in [(145,160),(143,162)]:
        print(f'  -- band control-Na {band} --')
        run(rows2,band,150.0,'chem'); run(rows2,band,150.0,'bg')
    print('\nGATE VERDICT: CLEAN instrument = correctly-signed strong FS (F>=10) AND NC-RBC ~ 0 (does not fire).')
    print('If NC fires like potassium -> pseudo-dysnatremia artifact contaminates the discordance -> not clean.')
    print('If clean -> we have a bulletproof instrument for an OPEN question (dysnatremia mortality) -> flagship.')

if __name__=='__main__':
    main()
