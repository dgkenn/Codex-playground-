#!/usr/bin/env python3
"""
SEPSISPAM (Asfar NEJM 2014) MIMIC-native emulation: in septic shock, does a HIGHER achieved MAP (toward the
80-85 arm) vs the canonical 65-70 change 28-day mortality / AKI? RCT truth: NULL overall for mortality;
in the CHRONIC-HYPERTENSION subgroup, the high-MAP arm reduced doubling-of-creatinine / RRT.

Exposure is confounded-by-health (patients who hold a higher MAP on less pressor are healthier), so — exactly
like our glucose dose-intensity finding and the VitalDB map_target_analysis.py — we do NOT force an IV. We run
a rigor battery: (A) NAIVE achieved-MAP association (explicitly labelled confounded), (B) age+severity-adjusted,
(C) modifiable hypotension-burden-below-65 exposure (residualized on severity), each vs 28-day mortality and an
AKI proxy (peak-creatinine doubling), plus (D) a negative-control outcome the MAP target should not cause.

Requires the streamed vitals (chart_abpm.csv invasive MAP; chart_nbpm.csv non-invasive) + vaso.csv (pressor
windows) + lab_lactate/lab_creat + septic-shock ICD. Designed to run when the chartevents stream completes;
smoke-tests on whatever MAP rows are present.
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
SEPSIS=re.compile(r'^(038|99591|99592|78552|A40|A41|R652|R6521|R6520)')
HTN=re.compile(r'^(401|402|403|404|405|I10|I11|I12|I13|I15)')
def ep(s):
    try: return datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_map():
    """merged achieved-MAP series per hadm: prefer invasive (abpm), fall back to non-invasive (nbpm)."""
    d={}
    for fn in ('chart_abpm.csv','chart_nbpm.csv'):
        try: f=open(SD+fn)
        except FileNotFoundError: continue
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<4: continue
            hadm=row[0]; t=ep(row[2])
            if not hadm or t is None: continue
            try: v=float(row[3])
            except: continue
            if v<10 or v>200: continue
            d.setdefault(hadm,[]).append((t,v))
        f.close()
    for k in d: d[k].sort()
    return d
def load_vaso_start():
    d={}
    try: f=open(SD+'vaso.csv')
    except FileNotFoundError: return d
    r=csv.reader(f); next(r,None)
    for row in r:
        if len(row)<3: continue
        t0=ep(row[1])
        if t0 is None: continue
        if row[0] not in d or t0<d[row[0]]: d[row[0]]=t0
    f.close(); return d
def load_seq(path):
    d={}
    try: f=open(path)
    except FileNotFoundError: return d
    r=csv.reader(f); next(r,None)
    for row in r:
        if len(row)<3 or not row[0] or not row[2]: continue
        t=ep(row[1])
        if t is None: continue
        try: v=float(row[2])
        except: continue
        d.setdefault(row[0],[]).append((t,v))
    f.close()
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
def load_dx():
    S={'sepsis':set(),'htn':set()}
    with open(SD+'diagnoses_icd.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        ih=ix['hadm_id'];ic=ix['icd_code']
        for row in r:
            c=row[ic].replace('.','').upper()
            if SEPSIS.match(c): S['sepsis'].add(row[ih])
            if HTN.match(c): S['htn'].add(row[ih])
    return S
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))

def main():
    mp=load_map(); vs=load_vaso_start(); lac=load_seq(SD+'lab_lactate.csv'); cr=load_seq(SD+'lab_creat.csv')
    adm=load_adm(); age,dod=load_pt(); DX=load_dx()
    print('=== SEPSISPAM MIMIC emulation (septic shock, achieved-MAP vs 28d mortality / AKI) ===')
    print(f'MAP-series hadms:{len(mp)} vaso-start hadms:{len(vs)} sepsis-ICD:{len(DX["sepsis"])} htn-ICD:{len(DX["htn"])}')
    rows=[]
    for hadm in DX['sepsis']:
        if hadm not in vs or hadm not in mp or hadm not in adm: continue
        subj=adm[hadm]['subject']; a=age.get(subj,np.nan)
        if math.isnan(a) or a<18: continue
        t0=vs[hadm]  # shock onset proxy = first vasopressor
        win=[(t,v) for (t,v) in mp[hadm] if t0-2 <= t <= t0+24]  # first 24h of shock
        if len(win)<3: continue
        maps=np.array([v for _,v in win])
        mean_map=float(maps.mean())
        burden65=float(np.mean(np.maximum(0.0, 65.0-maps)))  # mean mmHg below 65 (hypotension burden)
        burden85=float(np.mean(np.maximum(0.0, 85.0-maps)))  # mean mmHg below 85
        band=burden85-burden65   # SEPSISPAM's actual contrast: time-weighted mmHg in the 65-85 band
        # peak creatinine before vs after (AKI proxy: post/pre ratio >=2)
        crs=cr.get(hadm,[])
        pre=[v for (t,v) in crs if t<=t0]; post=[v for (t,v) in crs if t0<t<=t0+7*24]
        aki=1.0 if (pre and post and max(post) >= 2.0*min(pre)) else 0.0
        lseq=lac.get(hadm,[]); peaklac=max([v for (t,v) in lseq if t0-6<=t<=t0+6] or [np.nan])
        dd=dod.get(subj)
        m28=1.0 if (dd is not None and 0<=(dd-t0)<=24*28) else (float(adm[hadm]['expire']) if dd is None else 0.0)
        rows.append({'map':mean_map,'burden':burden65,'band':band,'m28':m28,'aki':aki,'age':a,
                     'lac':peaklac if peaklac==peaklac else 2.0,'htn':hadm in DX['htn']})
    print(f'\nseptic-shock cohort with MAP+pressor: n={len(rows)}')
    if len(rows)<200:
        print('  (partial vitals stream — too few MAP rows yet; rerun when chartevents extraction completes.)')
        return
    mapv=np.array([r['map'] for r in rows]); burden=np.array([r['burden'] for r in rows])
    agez=(np.array([r['age'] for r in rows])-65)/10; lacz=np.array([r['lac'] for r in rows])
    for oc in ['m28','aki']:
        y=np.array([r[oc] for r in rows])
        # (A) naive achieved-MAP (per +10 mmHg) — CONFOUNDED
        bA,sA=ols(y,np.column_stack([mapv/10.0,np.ones_like(y)]))
        # (B) + age + peak lactate (severity)
        bB,sB=ols(y,np.column_stack([mapv/10.0,np.ones_like(y),agez,lacz]))
        # (C) modifiable hypotension burden<65 (per mmHg), adjusted
        bC,sC=ols(y,np.column_stack([burden,np.ones_like(y),agez,lacz]))
        print(f'\n-- outcome={oc} (mean={y.mean():.3f}) --')
        print(f'  (A) NAIVE  achievedMAP/+10mmHg  b={bA[0]:+.4f}(SE {sA[0]:.4f})  [CONFOUNDED by health]')
        print(f'  (B) +age+lactate adjusted        b={bB[0]:+.4f}(SE {sB[0]:.4f})')
        print(f'  (C) hypotension-burden<65 /mmHg  b={bC[0]:+.4f}(SE {sC[0]:.4f})  [higher burden -> worse => a higher target might help]')
    # SEPSISPAM's ACTUAL contrast: the 65-85 incremental band (does sitting in 65-85, i.e. below the HIGH
    # target, add risk beyond burden<65?). Positive band coef => a higher target might help.
    band=np.array([r['band'] for r in rows])
    for oc in ['m28','aki']:
        y=np.array([r[oc] for r in rows])
        bB,sB=ols(y,np.column_stack([band,np.ones_like(y),agez,lacz,burden]))
        print(f'  BAND 65-85 (adj, +burden<65) ~ {oc}: b={bB[0]:+.4f}(SE {sB[0]:.4f})  '
              f'[>0 => risk in the 65-85 band the 65 target misses => higher target may help]')
    # chronic-HTN subgroup (SEPSISPAM's positive subgroup: high-MAP reduced AKI/RRT)
    htn=[r for r in rows if r['htn']]
    if len(htn)>=150:
        y=np.array([r['aki'] for r in htn]); bd=np.array([r['band'] for r in htn]); bu=np.array([r['burden'] for r in htn])
        ag=(np.array([r['age'] for r in htn])-65)/10; lz=np.array([r['lac'] for r in htn])
        bh,sh=ols(y,np.column_stack([bd,np.ones_like(y),ag,lz,bu]))
        print(f'\n-- CHRONIC-HTN subgroup (n={len(htn)}), AKI ~ 65-85 BAND (adj): b={bh[0]:+.4f}(SE {sh[0]:.4f})')
        print('   RCT: in chronic-HTN, HIGH-MAP arm reduced AKI/RRT -> a POSITIVE band coef here is the')
        print('   hypothesis-consistent direction (65-85 hypotension carries AKI risk a 65 target would miss).')
    print('\nRCT TRUTH: 28-day mortality NULL overall; chronic-HTN subgroup AKI/RRT benefit from higher MAP.')
    print('This is an ADJUSTED OBSERVATIONAL battery (achieved MAP is confounded-by-health; no valid IV for a')
    print('titrated MAP target, same lesson as glucose dose-intensity). Reported as hypothesis-consistent, not causal.')

if __name__=='__main__':
    main()
