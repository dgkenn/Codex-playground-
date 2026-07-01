#!/usr/bin/env python3
"""
Cross-method GLUCOSE instrument — transportability test of the bulletproof assay-noise IV to a 2nd analyte,
and an honest estimand check against NICE-SUGAR (Finfer NEJM 2009).

Two same-time glucose measurements: chemistry (50931, lab_glu) vs blood-gas (50809, lab_glubg), within 1h
=> same blood, zero drift => pure analytic discordance. Control = chemistry glucose; Z = 1(blood-gas > FLAG);
D = short-acting (regular) insulin 223258 within 6h (the reflexive correctional-insulin decision); band chem
glucose around FLAG; Y = in-hospital mortality (proxy). Report flag-ITT, first-stage F, balance.

ESTIMAND CAVEAT (reported, not hidden): NICE-SUGAR's contrast is a TARGET RANGE (intensive 81-108 vs
conventional <180), NOT a single high-flag reflexive decision. A single hyperglycemia flag instruments
"reflexive correctional insulin for hyperglycemia", which is NOT the NICE-SUGAR estimand. So this validates
(a) the instrument TRANSPORTS to a second analyte (does the same-time discordance give a strong, balanced
first stage?), and (b) the toolkit's estimand classifier: glucose is a GRADED/target decision, so a single
flag is expected to be a weak/partial instrument -> the design should escalate to a dose-intensity IV.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
INSULIN_REG = {'223258'}   # short-acting regular insulin = correctional/reflexive
def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_seq(path, lo, hi):
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
def load_insulin():
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in INSULIN_REG: continue
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
def load_pt():
    age={};dod={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
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
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r: s.add(row[ix['hadm_id']])
    f.close(); return s
def load_dm():
    s=set()
    import re
    DM=re.compile(r'^(250|E1[01])')
    try: f=open(SD+'diagnoses_icd.csv')
    except FileNotFoundError: return s
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r:
        if DM.match(row[ix['icd_code']].replace('.','').upper()): s.add(row[ix['hadm_id']])
    f.close(); return s
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=(np.asarray(t,float)-flag)/50.0; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    FLAG=180.0
    chem=load_seq(SD+'lab_glu.csv',10,900); bg=load_seq(SD+'lab_glubg.csv',10,900)
    ins=load_insulin(); adm=load_adm(); age,dod=load_pt(); icu=load_icu(); dm=load_dm()
    print('=== Cross-method GLUCOSE IV (chem 50931 vs blood-gas 50809, same-time = analytic noise) ===')
    print(f'chem:{len(chem)} bg:{len(bg)} insulin-reg:{len(ins)} ICU:{len(icu)} DM:{len(dm)}\n')
    MATCH=1.0; disc=[]; rows=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in chem: continue
        cseq=chem[hadm]; it=ins.get(hadm,[])
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        for (tb,vb) in bseq:
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None: continue
            disc.append(vb-best)
            dd=dod.get(subj)
            y90 = 1.0 if (dd is not None and 0<=(dd-tb)<=24*90) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            rows.append({'chem':best,'bg':vb,'z':1.0 if vb>FLAG else 0.0,'zc':1.0 if best>FLAG else 0.0,
                         'd':1.0 if any(tb<=r<=tb+6 for r in it) else 0.0,
                         'yh':float(adm[hadm]['expire']),'y90':y90,'age':ag,
                         'icu':hadm in icu,'dm':hadm in dm})
            break
    if len(disc)<200: print('too few pairs',len(disc)); return
    sig=np.std(disc)/math.sqrt(2)
    print(f'CROSS-METHOD glucose sigma = {sig:.1f} mg/dL (n_pairs={len(disc)}) [pure analytic, same-time]')
    def run(sub,ycol,label,side='bg'):
        # side='bg': Z=bloodgas flag, control=chem (clinician acts on ABG). side='chem': Z=chem flag, control=bloodgas.
        zkey='z' if side=='bg' else 'zc'; ckey='chem' if side=='bg' else 'bg'
        if len(sub)<300: print(f'  {label:40s} n={len(sub)} too small'); return
        z=np.array([r[zkey] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r[ycol] for r in sub]);C=cb([r[ckey] for r in sub],FLAG);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        print(f'  {label:40s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] | balAge={ba[0]:+.2f}')
    for side in ['bg','chem']:
        ck='chem' if side=='bg' else 'bg'
        print(f'\n######## Z = {side}-flag, control = {"chem" if side=="bg" else "bloodgas"} ########')
        for band in [(150,220),(140,240)]:
            sub=[r for r in rows if band[0]<=r[ck]<=band[1]]
            print(f'-- band {ck} glucose {band} (n={len(sub)}) --')
            run(sub,'yh','all, in-hospital',side)
            run([r for r in sub if r['icu']],'y90','ICU, 90-day',side)
            run([r for r in sub if r['icu'] and r['dm']],'y90','ICU + diabetic, 90-day',side)
            run([r for r in sub if r['icu'] and not r['dm']],'y90','ICU + non-diabetic, 90-day',side)
    print('\nESTIMAND: NICE-SUGAR = target-range (81-108 vs <180), NOT a single high-flag. A strong, balanced')
    print('first stage here => the cross-method instrument TRANSPORTS to glucose; but the single-flag estimand')
    print('!= NICE-SUGAR contrast, so a graded dose-intensity IV is required to test the trial target directly.')

if __name__=='__main__':
    main()
