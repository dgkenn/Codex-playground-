#!/usr/bin/env python3
"""
Single-method temporal flag-ITT for the two remaining lab-triggered trials whose analyte has NO second
same-time method: ALBIOS (albumin<30 g/L -> 20% albumin; RCT NULL) and BICAR-ICU (severe metabolic acidosis
-> NaHCO3; RCT NULL overall, benefit in AKIN2-3). Since there is no cross-method pair, we use the TEMPORAL
design (prior draw = severity control, current draw crosses the flag) and gate it honestly:
  - DRIFT DIAGNOSTIC: short-gap vs long-gap repeat-draw sigma near the flag. Temporal noise is only analytic if
    short-gap sigma << long-gap sigma AND is near the assay CV. Slow analyte (albumin) may pass; fast (HCO3) fails.
  - NC gate: does the flag predict an unrelated treatment (RBC/KCl)? Fires => confounded.
Only if the drift diagnostic passes do we interpret the flag-ITT. RCT truth: both NULL (albumin overall;
bicarbonate overall — with an AKIN2-3 subgroup benefit we probe via creatinine).
"""
import csv, math
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
ITEM={'ALB':{'220862','220864'},'BICARB':{'220995'},'RBC':{'225168','220996'},'KCL':{'225166'}}
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
def load_creat_max():
    """crude AKI proxy: peak creatinine per hadm."""
    d={}
    try: f=open(SD+'lab_creat.csv')
    except FileNotFoundError: return d
    r=csv.reader(f);next(r,None)
    for row in r:
        if len(row)<3 or not row[0] or not row[2]: continue
        try: v=float(row[2])
        except: continue
        if row[0] not in d or v>d[row[0]]: d[row[0]]=v
    f.close(); return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag,sc):
    c=(np.asarray(t,float)-flag)/sc; return np.column_stack([np.ones_like(c),c,c*c])

def analyze(name,labfile,lo,hi,flag,own,nc,band,scale,shortgap,longgap,adm,age,dod,TR,creat=None):
    seq=load_seq(labfile,lo,hi)
    print(f'\n===== {name}: flag {name.split()[0]}<{flag} -> {own}; band {band}; assay unit-scale {scale} =====')
    print(f'hadm with {name.split()[0]} labs: {len(seq)}')
    # drift diagnostic near flag
    sdiff={'short':[], 'long':[]}
    for hadm,s in seq.items():
        for i in range(1,len(s)):
            t1,v1=s[i-1]; t2,v2=s[i]; g=t2-t1
            if not (band[0]<=v1<=band[1]): continue
            if 0<g<=shortgap: sdiff['short'].append(v2-v1)
            elif longgap[0]<=g<=longgap[1]: sdiff['long'].append(v2-v1)
    ss=np.std(sdiff['short']) if len(sdiff['short'])>30 else float('nan')
    sl=np.std(sdiff['long']) if len(sdiff['long'])>30 else float('nan')
    print(f'  DRIFT: short(<={shortgap}h) sd={ss:.3f} (n={len(sdiff["short"])})  long({longgap}h) sd={sl:.3f} '
          f'(n={len(sdiff["long"])})  ratio short/long={ss/sl if sl==sl and sl>0 else float("nan"):.2f}')
    passdrift = (ss==ss and sl==sl and ss < 0.8*sl)
    print(f'  -> temporal noise {"plausibly analytic (short<<long)" if passdrift else "DRIFT-CONTAMINATED (short not << long)"}')
    # build flag-ITT on short-gap decision pairs (prior=control, current triggers)
    rows=[]
    for hadm,s in seq.items():
        if hadm not in adm: continue
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        ownt=TR[own].get(hadm,[]); nct=TR[nc].get(hadm,[])
        for i in range(1,len(s)):
            t1,v1=s[i-1]; t2,v2=s[i]; g=t2-t1
            if not (0<g<=shortgap): continue
            if any(r<=t2 for r in ownt): break  # already treated before decision -> stop this hadm
            dd=dod.get(subj)
            y30 = 1.0 if (dd is not None and 0<=(dd-t2)<=24*30) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            cm = creat.get(hadm,np.nan) if creat is not None else np.nan
            rows.append({'ctrl':v1,'z':1.0 if v2<flag else 0.0,
                         'd':1.0 if any(t2<=r<=t2+6 for r in ownt) else 0.0,
                         'ncd':1.0 if any(t2<=r<=t2+6 for r in nct) else 0.0,
                         'yh':float(adm[hadm]['expire']),'y30':y30,'age':ag,'cr':cm})
            break
    def run(sub,ycol,lbl):
        if len(sub)<200: print(f'    {lbl:26s} n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r[ycol] for r in sub])
        C=cb([r['ctrl'] for r in sub],flag,scale);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        bn,sn=ols(np.array([r['ncd'] for r in sub]),X)
        nc0,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        lo2,hi2=rf-1.96*srf[0],rf+1.96*srf[0]
        ncsig='FIRES!!' if abs(bn[0])>1.96*sn[0] else 'ok'
        print(f'    {lbl:26s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc0[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo2:+.3f},{hi2:+.3f}] | balAge={ba[0]:+.2f} | NC-{nc}={bn[0]:+.3f}({ncsig})')
    run(rows,'yh','all (in-hospital)')
    run(rows,'y30','all (30-day)')
    if creat is not None:
        run([r for r in rows if r['cr']==r['cr'] and r['cr']>=2.0],'y30','AKI proxy (creat>=2), 30d')
    print(f'  RCT truth: NULL{" overall; AKIN2-3 benefit" if creat is not None else ""}. Interpret flag-ITT ONLY if drift passed AND NC ok.')

def main():
    adm=load_adm(); age,dod=load_pt(); TR=load_treat()
    print('=== Single-method temporal flag-ITT: ALBIOS (albumin) & BICAR-ICU (bicarbonate) ===')
    print(f'albumin-tx hadm:{len(TR["ALB"])} bicarb-tx hadm:{len(TR["BICARB"])}')
    # ALBIOS: albumin g/dL, flag 3.0 (=30 g/L); slow analyte; allow up to 12h short gap, 24-48h long
    analyze('Albumin g/dL','lab_alb.csv',0.5,7,3.0,'ALB','RBC',(2.0,4.0),1.0,12.0,(24.0,48.0),adm,age,dod,TR)
    # BICAR-ICU: HCO3 mEq/L, flag 15 (severe acidosis proxy for pH<=7.20); fast analyte; short<=4h, long 12-24h
    creat=load_creat_max()
    analyze('HCO3 mEq/L','lab_hco3.csv',3,45,15.0,'BICARB','RBC',(10.0,20.0),3.0,4.0,(12.0,24.0),adm,age,dod,TR,creat)

if __name__=='__main__':
    main()
