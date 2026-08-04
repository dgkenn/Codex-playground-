#!/usr/bin/env python3
"""
Nurse-PRN IV, v2 — SALVAGE via a reframed estimand that dodges the v1 failures.
v1 failed: binary give/hold per dose (denominator unobserved), whole-stay aggregation (LOS-confounded).
v2: treatment = PRN dose INTENSITY in a FIXED 48h window from the first administration (counts of GIVEN
doses = fully observed); instrument = the administering nurses' leave-one-out liberality (mean window-dose
count per patient); fixed window + within-service/acuity controls break the LOS confounding.
Test = does balance (age ~ Z) recover? If yes, the instrument is salvaged; if no, v1's retirement stands.
Reads emar_prn.csv + admissions + patients + services. No PHI printed.
"""
import csv, math
from datetime import datetime
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
WIN = 48.0  # hours
ADMIN = ('administered', 'started', 'restarted', 'given', 'bolus')
NOT = ('not given', 'hold', 'held', 'delayed', 'stopped', 'not flush', 'assessed', 'confirmed', 'reconcil')
def is_admin(ev):
    e = ev.lower()
    if any(k in e for k in NOT): return False
    return any(k in e for k in ADMIN)

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        LOW = {'ELECTIVE','SURGICAL SAME DAY ADMISSION','OBSERVATION ADMIT','DIRECT OBSERVATION','AMBULATORY OBSERVATION'}
        for row in r:
            d[row[ix['hadm_id']]] = {'subject':row[ix['subject_id']],
                'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
                'low': (row[ix['admission_type']] in LOW) if 'admission_type' in ix else False}
    return d

def load_age():
    d = {}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f); hdr=next(r); ix={n:i for i,n in enumerate(hdr)}
        for row in r:
            try: d[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except: pass
    return d

def load_svc():
    d={}
    try: f=open(SD+'services.csv')
    except FileNotFoundError: return d
    r=csv.reader(f); hdr=next(r); ix={n:i for i,n in enumerate(hdr)}
    for row in r:
        h=row[ix['hadm_id']]
        if h not in d: d[h]=row[ix['curr_service']]
    f.close(); return d

def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))

def svc_dum(svcs):
    top=['MED','CMED','SURG','CSURG','NMED','NSURG','TRAUM','OMED','GU','VSURG','ORTHO','PSURG']
    M=np.zeros((len(svcs),len(top)))
    for i,s in enumerate(svcs):
        if s in top: M[i,top.index(s)]=1
    return M

def load_nc():
    d={};keys=[]
    try: f=open(SD+'nc_outcomes.csv')
    except FileNotFoundError: return d,keys
    r=csv.reader(f);hdr=next(r);keys=hdr[1:]
    for row in r: d[row[0]]=[int(x) for x in row[1:]]
    f.close();return d,keys

def emp_null(c,s):
    from scipy import optimize as O
    c=np.asarray(c);s=np.asarray(s)
    def nll(p):
        mu,l=p;v=np.exp(2*l)+s**2;return 0.5*np.sum(np.log(2*np.pi*v)+(c-mu)**2/v)
    r=O.minimize(nll,[0.0,np.log(np.std(c)+1e-6)],method='Nelder-Mead')
    return r.x[0],np.exp(r.x[1])

def main():
    import os
    if not os.path.exists(SD+'emar_prn.csv'):
        print('emar_prn.csv missing — SKIP'); return
    adm=load_adm(); age=load_age(); svc=load_svc(); nc,nckeys=load_nc()
    # load admin events grouped by class -> hadm -> list of (t, nurse)
    byc=defaultdict(lambda: defaultdict(list))
    with open(SD+'emar_prn.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<5: continue
            hadm,ct,cls,ev,nurse=row
            if not nurse or not is_admin(ev) or hadm not in adm: continue
            t=ep(ct)
            if t is not None: byc[cls][hadm].append((t,nurse))
    print('=== Nurse-PRN IV v2 (dose-intensity, fixed 48h window) — salvage test ===')
    print('Test: does balance recover vs v1 (which failed +/-30yr)?  low-acuity headline\n')
    for cls in ['benzo','opioid','antipsy']:
        # per hadm: window doses + nurses
        rec={}  # hadm -> (D count, [nurses])
        for hadm,evs in byc[cls].items():
            evs.sort(); t0=evs[0][0]
            win=[(t,n) for (t,n) in evs if t0<=t<=t0+WIN]
            rec[hadm]=(len(win),[n for _,n in win])
        # nurse tendency: total window-doses and distinct patients; also per (nurse,hadm) doses for LOO
        ntot=defaultdict(float); npat=defaultdict(set); nh=defaultdict(float)
        for hadm,(D,nurses) in rec.items():
            cnt=defaultdict(float)
            for n in nurses: cnt[n]+=1
            for n,c in cnt.items():
                ntot[n]+=c; npat[n].add(hadm); nh[(n,hadm)]=c
        def loo(n,hadm):
            dp=len(npat[n])
            if dp<=1: return None
            return (ntot[n]-nh[(n,hadm)])/(dp-1)
        rows=[]
        for hadm,(D,nurses) in rec.items():
            if hadm not in adm: continue
            ag=age.get(adm[hadm]['subject'],np.nan)
            if math.isnan(ag): continue
            zz=[loo(n,hadm) for n in set(nurses)]; zz=[x for x in zz if x is not None]
            if not zz: continue
            rows.append({'hadm':hadm,'z':np.mean(zz),'d':float(D),'y':float(adm[hadm]['expire']),
                         'age':ag,'svc':svc.get(hadm,''),'low':adm[hadm]['low']})
        def run(sub,label):
            if len(sub)<800: print(f'    {label:8s}: n={len(sub)} too small'); return
            z=np.array([r['z'] for r in sub]); d=np.array([r['d'] for r in sub])
            y=np.array([r['y'] for r in sub]); agev=np.array([r['age'] for r in sub])
            agec=(agev-60)/10; D=svc_dum([r['svc'] for r in sub])
            X=np.column_stack([z,np.ones(len(z)),agec,agec*agec,D])
            bfs,sfs=ols(d,X); brf,srf=ols(y,X)
            fs,rf=bfs[0],brf[0]; rng=np.percentile(z,[10,90]); zspan=rng[1]-rng[0]
            Xb=np.column_stack([z,np.ones(len(z)),D]); ba,_=ols(agev,Xb); bal=ba[0]*zspan
            late=rf/fs if abs(fs)>1e-4 else float('nan')
            F=(fs/sfs[0])**2 if sfs[0]>0 else 0
            valid='✓VALID' if abs(bal)<1.0 and F>10 else '✗INVALID'
            nctxt=''
            if nc and nckeys:
                ncc,ncs=[],[]
                for j in range(len(nckeys)):
                    yv=np.array([nc.get(r['hadm'],[0]*len(nckeys))[j] for r in sub],float)
                    if yv.sum()<20: continue
                    bb,sb=ols(yv,X); ncc.append(bb[0]); ncs.append(sb[0])
                if len(ncc)>=5:
                    mu,sd=emp_null(ncc,ncs)
                    from scipy import stats as _st
                    pc=2*_st.norm.sf(abs(rf-mu)/np.sqrt(sd**2+srf[0]**2))
                    nctxt=f' NCcal_p={pc:.3f}'
            print(f'    {label:8s} n={len(sub):6d} meanDoses={d.mean():.1f} zSD={z.std():.2f} | '
                  f'FS={fs:+.3f}(F{F:5.0f}) | RF(mort/dose)={rf:+.5f}({srf[0]:.5f}) LATE={late:+.4f} | bal={bal:+.1f}yr {valid}{nctxt}')
        print(f'  {cls}:')
        run([r for r in rows if r['low']],'ELECTIVE')
        run(rows,'ALL')
    print('\nDONE. bal<1yr => the intensity/fixed-window reframe SOLVED the v1 confounding; else v1 stands.')

if __name__=='__main__':
    main()
