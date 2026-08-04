#!/usr/bin/env python3
"""
PREVENT (Arabi NEJM 2019) MIMIC emulation: adjunctive intermittent pneumatic compression (IPC) ADDED to
pharmacologic VTE prophylaxis vs pharmacologic-alone, in ICU patients expected to stay >=72h. Primary:
incident proximal DVT after day 3. RCT truth: NULL (3.9% vs 4.2%, RR 0.93).

Previously logged as "design-only — IPC device exposure entirely absent." That was wrong: chartevents carries
Compression-device itemids 228419/228420/228451/228452 ("Compression device #1-4"). Once the chained
chartevents pass writes chart_comp{1..4}.csv, IPC exposure IS observable. This script builds the emulation on
that data; run when the compression stream completes.

Exposure D = IPC device charted during ICU stay (any of the 4 device slots) AMONG patients on pharmacologic
prophylaxis (rx_class anticoag_ppx) — i.e. the trial's add-on contrast. Instrument = admitting-provider /
unit leave-one-out IPC-use liberality. Outcome = incident proximal-DVT ICD proxy (453.4x/I82.4x) — with the
honest caveat it conflates prevalent/incident and lacks imaging timing. Cohort = ICU LOS>=3d + on pharm ppx.
"""
import csv, math, os, re
from collections import defaultdict
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
DVT=re.compile(r'^(4534|4538|4539|I824|I825|I829)')
def ep(s):
    try: return datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_comp():
    """hadm_id -> set of charttimes with a compression device present (any slot)."""
    d=defaultdict(list); found=False
    for i in (1,2,3,4):
        fn=SD+f'chart_comp{i}.csv'
        if not os.path.exists(fn): continue
        found=True
        with open(fn) as f:
            r=csv.reader(f); next(r,None)
            for row in r:
                if len(row)<4: continue
                hadm=row[0]; val=row[3]
                if not hadm: continue
                # value is text like 'Continuous'/'On'/'Sequential' — presence of a non-empty, non-'Off' value = in place
                if val and val.strip().lower() not in ('off','none','d/c','discontinued',''):
                    t=ep(row[2])
                    if t is not None: d[hadm].append(t)
    return d, found
def load_rx_class(cls):
    d=defaultdict(list)
    with open(SD+'rx_class.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1]!=cls: continue
            t=ep(row[2])
            if t is not None: d[row[0]].append(t)
    return d
def load_icu():
    d={}
    with open(SD+'icustays.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            try: los=float(row[ix['los']])
            except: los=None
            hadm=row[ix['hadm_id']]
            if hadm not in d: d[hadm]={'los':los,'unit':row[ix['first_careunit']]}
    return d
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        pv=ix.get('admit_provider_id',-1)
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],
                'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
                'prov':row[pv] if pv>=0 else ''}
    return d
def load_age():
    d={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            try: d[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
    return d
def load_dvt():
    s=set()
    with open(SD+'diagnoses_icd.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            if DVT.match(row[ix['icd_code']].replace('.','').upper()): s.add(row[ix['hadm_id']])
    return s
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(v):
    a=(np.asarray(v,float)-60.0)/10.0; return np.column_stack([np.ones_like(a),a,a*a])

def main():
    comp, found = load_comp()
    if not found:
        print('chart_comp{1..4}.csv not present yet — the chained compression-device chartevents pass has not')
        print('finished. Rerun this script once it completes. (Design is ready; awaiting data.)')
        return
    pharm=load_rx_class('anticoag_ppx'); icu=load_icu(); adm=load_adm(); age=load_age(); dvt=load_dvt()
    print('=== PREVENT (adjunctive IPC + pharm vs pharm-alone VTE ppx) — MIMIC emulation ===')
    print(f'IPC-device hadms:{len(comp)} pharm-ppx hadms:{len(pharm)} DVT-ICD hadms:{len(dvt)}')
    rows=[]
    for hadm, a in adm.items():
        st=icu.get(hadm)
        if st is None or st['los'] is None or st['los']<3.0: continue  # expected-LOS>=72h proxy
        if hadm not in pharm: continue                                  # on pharmacologic ppx (shared background)
        ag=age.get(a['subject'],np.nan)
        if math.isnan(ag) or ag<18: continue
        d=1.0 if comp.get(hadm) else 0.0                                # IPC add-on present?
        y=1.0 if hadm in dvt else 0.0
        if not a['prov']: continue
        rows.append({'d':d,'y':y,'age':ag,'prov':a['prov'],'unit':st['unit']})
    print(f'cohort n={len(rows)} (ICU LOS>=3d, on pharm ppx) | IPC rate={np.mean([r["d"] for r in rows]):.3f} | '
          f'DVT rate={np.mean([r["y"] for r in rows]):.3f}')
    if len(rows)<300: print('too few -> DESIGN-ONLY.'); return
    # naive
    d=np.array([r['d'] for r in rows]); y=np.array([r['y'] for r in rows]); age_=np.array([r['age'] for r in rows])
    nb,ns=ols(y,np.column_stack([d,np.ones_like(d)]))
    print(f'  NAIVE IPC->DVT: {nb[0]:+.4f} (SE {ns[0]:.4f})')
    # provider LOO instrument
    psum=defaultdict(float); pcnt=defaultdict(int)
    for r in rows: psum[r['prov']]+=r['d']; pcnt[r['prov']]+=1
    sub=[r for r in rows if pcnt[r['prov']]>=10]
    if len(sub)>=300:
        z=np.array([(psum[r['prov']]-r['d'])/(pcnt[r['prov']]-1) for r in sub])
        d2=np.array([r['d'] for r in sub]); y2=np.array([r['y'] for r in sub]); ag2=np.array([r['age'] for r in sub])
        X=np.column_stack([z,cb(ag2)])
        bfs,sfs=ols(d2,X); brf,srf=ols(y2,X); fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        rng=np.percentile(z,[10,90]); ba,_=ols(ag2,np.column_stack([z,np.ones_like(z)]))
        print(f'  provider-LOO IV: n={len(sub)} FS={fs:+.3f}(F{F:4.0f}) ITT={rf:+.5f}({srf[0]:.5f}) '
              f'balAge={ba[0]*(rng[1]-rng[0]):+.2f}yr')
    print('\n  RCT TRUTH: incident proximal DVT NULL (3.9% IPC vs 4.2% control, RR 0.93). Caveats: DVT ICD proxy')
    print('  conflates prevalent/incident + no imaging timing; expected-LOS proxied by realized LOS (look-ahead).')
    print('  VERDICT: emulatable-and-run — IPC exposure (compression-device chartevents) FIXES the prior')
    print('  "exposure entirely absent" gap. Validity per the F/balance diagnostics above.')

if __name__=='__main__':
    main()
