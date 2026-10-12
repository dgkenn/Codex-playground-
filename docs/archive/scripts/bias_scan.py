#!/usr/bin/env python3
"""
Measurement-bias DISCOVERY scan (Sjoding pulse-ox template, applied to paired chem<->blood-gas labs).
For each analyte with two same-time methods, compute the method bias (chem - bloodgas) per matched pair and
test whether the bias differs by RACE and SEX. A demographic-DIFFERENTIAL measurement bias means a group is
systematically mis-measured -> mis-treated (the novel, high-impact finding). Purely observational; no causal
instrument needed (dodges the power wall).
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
        ri=ix['race']; ih=ix['hadm_id']
        for row in r:
            raw=row[ri].upper()
            g=('BLACK' if 'BLACK' in raw else 'WHITE' if 'WHITE' in raw else 'HISPANIC' if 'HISPANIC' in raw
               else 'ASIAN' if 'ASIAN' in raw else 'OTHER')
            d[row[ih]]=g
    return d
def load_sex():
    d={};sub2sex={}
    import csv as c
    with open(SD+'patients.csv') as f:
        r=c.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        gi=ix.get('gender'); si=ix['subject_id']
        for row in r:
            if gi is not None: sub2sex[row[si]]=row[gi]
    with open(SD+'admissions.csv') as f:
        r=c.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r: d[row[ix['hadm_id']]]=sub2sex.get(row[ix['subject_id']],'?')
    return d

def scan(name, chemf, bgf, lo, hi, match=1.0):
    chem=load_seq(chemf,lo,hi); bg=load_seq(bgf,lo,hi)
    race=load_race(); sex=load_sex()
    # first same-time pair per hadm: bias = chem - bloodgas
    recs=[]
    for hadm,bseq in bg.items():
        if hadm not in chem: continue
        cseq=chem[hadm]
        for (tb,vb) in bseq:
            best=None;bd=match+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=match and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+match: break
            if best is None: continue
            recs.append((best-vb, race.get(hadm,'OTHER'), sex.get(hadm,'?')))  # chem - bloodgas
            break
    if len(recs)<500: print(f'{name}: too few pairs ({len(recs)})'); return
    bias=np.array([r[0] for r in recs]); R=[r[1] for r in recs]; S=[r[2] for r in recs]
    print(f'\n=== {name}: method bias (chem - bloodgas), n_pairs={len(recs)} ===')
    print(f'  overall bias = {bias.mean():+.3f} (SD {bias.std():.3f})')
    print('  by race:')
    for g in ['WHITE','BLACK','HISPANIC','ASIAN','OTHER']:
        m=np.array([x==g for x in R])
        if m.sum()>=100:
            b=bias[m]; se=b.std()/math.sqrt(m.sum())
            print(f'    {g:9s} n={m.sum():6d} bias={b.mean():+.3f} [{b.mean()-1.96*se:+.3f},{b.mean()+1.96*se:+.3f}]')
    # BLACK vs WHITE differential (the Sjoding-style contrast)
    bw=bias[np.array([x=='BLACK' for x in R])]; ww=bias[np.array([x=='WHITE' for x in R])]
    if len(bw)>=100 and len(ww)>=100:
        diff=bw.mean()-ww.mean(); se=math.hypot(bw.std()/math.sqrt(len(bw)), ww.std()/math.sqrt(len(ww)))
        print(f'  >> BLACK-WHITE differential bias = {diff:+.3f} (SE {se:.3f}, z={diff/se:+.2f})  '
              f'{"<-- DIFFERENTIAL!!" if abs(diff/se)>3 else ""}')
    print('  by sex:')
    for g in ['M','F']:
        m=np.array([x==g for x in S])
        if m.sum()>=100:
            b=bias[m]; print(f'    {g} n={m.sum():6d} bias={b.mean():+.3f}')

def main():
    print('Measurement-bias discovery scan across paired chem<->blood-gas analytes, by race & sex.')
    scan('Hemoglobin (g/dL)', SD+'lab_hb.csv', SD+'lab_hbbg.csv', 3,20)
    scan('Sodium (mEq/L)',    SD+'lab_na.csv', SD+'lab_nabg.csv', 100,190)
    scan('Potassium (mEq/L)', SD+'lab_k.csv',  SD+'lab_kbg.csv',  1.5,8)
    scan('Glucose (mg/dL)',   SD+'lab_glu.csv',SD+'lab_glubg.csv',10,900)
    scan('Bicarbonate (mEq/L)',SD+'lab_hco3.csv',SD+'lab_hco3bg.csv',3,45)
    print('\nA large BLACK-WHITE (or sex) differential bias in a routinely-acted-on analyte = a novel,')
    print('policy-relevant measurement-safety finding (the Sjoding pulse-ox template on labs).')

if __name__=='__main__':
    main()
