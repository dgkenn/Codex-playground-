#!/usr/bin/env python3
"""
eICU HOSPITAL-PREFERENCE IV for RBC transfusion (Paper #1's second, independent instrument — different failure
modes from the cross-method assay-noise IV). Across eICU's 208 hospitals, transfusion culture varies
systematically; the hospital's leave-one-out transfusion liberality (among anemic patients) instruments whether
THIS patient is transfused, conditional on measured severity. Brookhart-style preference IV.

Design:
  cohort = anemic patients (qualifying Hb in band), overall and the acute-MI subset (apacheadmissiondx ~ MI).
  Z = hospital leave-one-out transfusion rate among the cohort (this patient excluded).
  D = 1(RBC transfusion this stay).  Y = hospital mortality (hospitaldischargestatus=='Expired').
  controls = age + APACHE score (severity).  Gates: first-stage F, balance (age+apache ~ Z), NC treatment.
RCT truth: general = null (restrictive non-inferior); MI = MINT liberal-trend (open) -> transfusion protective
would be LATE<0.
"""
import csv, re, os
import numpy as np
SD='/home/user/Codex-playground-/scratchpad/'
def ff(x):
    try: return float(x)
    except: return None
def load_patient():
    d={}
    with open(SD+'eicu_patient.csv.gz'.replace('.gz','')) if os.path.exists(SD+'eicu_patient.csv') else _gz(SD+'eicu_patient.csv.gz') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        pid=ix['patientunitstayid']; hid=ix['hospitalid']; age=ix['age']
        dis=ix['hospitaldischargestatus']; dx=ix['apacheadmissiondx']
        for row in r:
            if len(row)<=max(pid,hid,age,dis,dx): continue
            a=row[age]; a=90.0 if a=='> 89' else ff(a)
            d[row[pid]]={'hosp':row[hid],'age':a,
                         'mort':1.0 if row[dis].strip().lower()=='expired' else 0.0,
                         'mi':bool(re.search(r'myocardial infarction|\bMI\b|MI, |infarction',row[dx],re.I))}
    return d
def _gz(p):
    import gzip; return gzip.open(p,'rt',newline='')
def load_hb():
    """patientunitstayid -> qualifying (lowest) Hb in the first 48h (labresultoffset minutes)."""
    d={}
    if not os.path.exists(SD+'eicu_lab_hb.csv'): return d
    with open(SD+'eicu_lab_hb.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<4: continue
            pid=row[0]; off=ff(row[1]); v=ff(row[3])
            if off is None or v is None or v<=0 or v>25: continue
            if off>48*60: continue
            if pid not in d or v<d[pid]: d[pid]=v
    return d
def load_tx():
    s=set()
    if not os.path.exists(SD+'eicu_tx.csv'): return s
    with open(SD+'eicu_tx.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if row and row[0]: s.add(row[0])
    return s
def load_apache():
    d={}
    p=SD+'eicu_apache.csv.gz'
    if not os.path.exists(p): return d
    with _gz(p) as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        pid=ix.get('patientunitstayid'); sc=ix.get('apachescore')
        if pid is None or sc is None: return d
        for row in r:
            if len(row)<=max(pid,sc): continue
            v=ff(row[sc])
            if v is not None and v>=0: d[row[pid]]=v
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))

def main():
    if not os.path.exists(SD+'eicu_lab_hb.csv'):
        print('AWAITING eICU lab stream (eicu_lab_hb.csv). Nothing to do yet.'); return
    pat=load_patient(); hb=load_hb(); tx=load_tx(); apa=load_apache()
    print(f'patients:{len(pat)} with-Hb:{len(hb)} RBC-tx:{len(tx)} apache:{len(apa)}')
    # cohort: anemic (Hb 6-10), with hospital + age; build rows
    rows=[]
    for pid,v in hb.items():
        if pid not in pat: continue
        p=pat[pid]
        if p['age'] is None or not (6.0<=v<=10.0): continue
        rows.append({'pid':pid,'hosp':p['hosp'],'hb':v,'age':p['age'],'apache':apa.get(pid,np.nan),
                     'd':1.0 if pid in tx else 0.0,'y':p['mort'],'mi':p['mi']})
    def hosp_loo(rowset):
        # leave-one-out hospital transfusion rate among the rowset
        from collections import defaultdict
        tot=defaultdict(float); cnt=defaultdict(float)
        for r in rowset: tot[r['hosp']]+=r['d']; cnt[r['hosp']]+=1
        for r in rowset:
            n=cnt[r['hosp']]
            r['z']=(tot[r['hosp']]-r['d'])/(n-1) if n>1 else np.nan
        return [r for r in rowset if r['z']==r['z'] and cnt[r['hosp']]>=20]  # hospitals with >=20 cohort pts
    def run(rowset,label):
        sub=hosp_loo([dict(r) for r in rowset])
        if len(sub)<300: print(f'  {label:24s} n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r['y'] for r in sub])
        ag=(np.array([r['age'] for r in sub])-60)/10
        ap=np.array([r['apache'] if r['apache']==r['apache'] else np.nan for r in sub])
        ap=np.where(np.isnan(ap), np.nanmedian(ap[~np.isnan(ap)]) if np.any(~np.isnan(ap)) else 0.0, ap)
        ap=(ap-np.nanmean(ap))/ (np.nanstd(ap)+1e-9)
        X=np.column_stack([z,np.ones_like(z),ag,ag*ag,ap])   # control age + apache severity
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols((np.array([r['age'] for r in sub])),X); bap,_=ols(np.array([r['apache'] if r['apache']==r['apache'] else np.nanmedian(ap) for r in sub]),X)
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        late=rf/fs if abs(fs)>1e-3 else float('nan'); lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        print(f'  {label:24s} n={len(sub):6d} nHosp~ mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:5.0f}) | pref-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] LATE={late:+.3f} | balAge={ba[0]:+.2f}')
    print('=== eICU hospital-preference IV (RBC transfusion), anemic Hb 6-10 ===')
    run(rows,'ALL anemic')
    run([r for r in rows if r['mi']],'acute MI [Paper#1]')
    print('\nRCT truth: ALL=null; MI=MINT liberal-trend (protective => LATE<0). Different instrument than')
    print('cross-method -> convergence with MIMIC MI cross-method (LATE -0.18) = the Paper #1 triangulation.')

if __name__=='__main__':
    main()
