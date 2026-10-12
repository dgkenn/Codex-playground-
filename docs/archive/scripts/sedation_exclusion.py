#!/usr/bin/env python3
"""
Sedation-culture EXCLUSION test for the nurse-PRN benzo/antipsy harm signals.
Threat: a 'sedation-heavy' nurse/unit culture harms via the whole sedation BUNDLE (benzo+opioid+
antipsy, restraints, immobility), not the target drug specifically -> exclusion-restriction violation.
Tests, using emar (benzo/opioid/antipsy administrations + nurse):
  A. DRUG-SPECIFICITY of the instrument: is nurse benzo-liberality correlated with their opioid/antipsy
     liberality across nurses? High corr => a general sedation culture (exclusion concern).
  B. LEAKAGE: does the benzo instrument Z predict the patient's OTHER-sedative doses (first stage on the
     co-intervention)? If yes => the instrument moves the bundle, not just benzo.
  C. ROBUSTNESS: does the benzo harm LATE SURVIVE controlling for co-administered opioid+antipsy doses?
     Survives => benzo-specific (exclusion holds better). Vanishes => it was the sedation bundle.
Verdict: signal claimable only if instrument is drug-specific (A), low leakage (B), and survives (C).
"""
import csv, math
from datetime import datetime
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
WIN = 48.0
ADMIN = ('administer','started','restarted','given','bolus'); NOT=('not given','hold','held','delayed','stopped','not flush','assessed','confirmed','reconcil')
def is_admin(ev):
    e=ev.lower()
    if any(k in e for k in NOT): return False
    return any(k in e for k in ADMIN)
def ep(s):
    try: return datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        LOW={'ELECTIVE','SURGICAL SAME DAY ADMISSION','OBSERVATION ADMIT','DIRECT OBSERVATION','AMBULATORY OBSERVATION'}
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
                'low':(row[ix['admission_type']] in LOW) if 'admission_type' in ix else False}
    return d
def load_age():
    d={}
    with open(SD+'patients.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r:
            try:d[row[ix['subject_id']]]=float(row[ix['anchor_age']])
            except:pass
    return d

def main():
    import os
    if not os.path.exists(SD+'emar_prn.csv'): print('emar_prn.csv missing'); return
    adm=load_adm(); age=load_age()
    # class -> hadm -> [(t,nurse)]
    byc=defaultdict(lambda: defaultdict(list))
    with open(SD+'emar_prn.csv') as f:
        r=csv.reader(f);next(r,None)
        for row in r:
            if len(row)<5: continue
            hadm,ct,cls,ev,nurse=row
            if not nurse or not is_admin(ev) or hadm not in adm: continue
            t=ep(ct)
            if t is not None: byc[cls][hadm].append((t,nurse))
    # nurse-level liberality per class (mean window-doses per patient); for the drug-specificity corr
    def nurse_rates(cls):
        rec={};
        for hadm,evs in byc[cls].items():
            evs.sort();t0=evs[0][0];rec[hadm]=[n for (t,n) in evs if t0<=t<=t0+WIN]
        tot=defaultdict(float);pat=defaultdict(set);nh=defaultdict(float)
        for hadm,ns in rec.items():
            c=defaultdict(float)
            for n in ns:c[n]+=1
            for n,v in c.items(): tot[n]+=v;pat[n].add(hadm);nh[(n,hadm)]=v
        return rec,tot,pat,nh
    R={};
    for cls in ['benzo','opioid','antipsy']: R[cls]=nurse_rates(cls)
    # A. drug-specificity: correlate nurse liberality across classes (nurses with >=30 pts in both)
    print('=== A. instrument DRUG-SPECIFICITY (nurse liberality correlation across sedatives) ===')
    def nrate(cls):
        _,tot,pat,_=R[cls]; return {n:tot[n]/len(pat[n]) for n in pat if len(pat[n])>=30}
    rb=nrate('benzo');ro=nrate('opioid');ra=nrate('antipsy')
    for a,b,na,nb in [('benzo','opioid',rb,ro),('benzo','antipsy',rb,ra),('opioid','antipsy',ro,ra)]:
        common=set(na)&set(nb)
        if len(common)>30:
            x=np.array([na[n] for n in common]);y=np.array([nb[n] for n in common])
            print(f'  corr(nurse {a}-liberality, {b}-liberality) = {np.corrcoef(x,y)[0,1]:+.3f}  (n_nurses={len(common)})')
    # B & C: for benzo and antipsy, build patient rows with target + co-sedative doses + Z
    for tgt in ['benzo','antipsy']:
        rec,tot,pat,nh=R[tgt]
        def loo(n,hadm):
            dp=len(pat[n])
            return (tot[n]-nh[(n,hadm)])/(dp-1) if dp>1 else None
        rows=[]
        for hadm,ns in rec.items():
            if hadm not in adm: continue
            ag=age.get(adm[hadm]['subject'],np.nan)
            if math.isnan(ag): continue
            zz=[loo(n,hadm) for n in set(ns)];zz=[x for x in zz if x is not None]
            if not zz: continue
            # co-sedative doses in the same window (window anchored at target first dose)
            t0=min(t for t,_ in byc[tgt][hadm]) if byc[tgt][hadm] else 0
            others={}
            for oc in ['benzo','opioid','antipsy']:
                if oc==tgt: continue
                others[oc]=sum(1 for (t,_) in byc[oc].get(hadm,[]) if t0<=t<=t0+WIN)
            rows.append({'z':np.mean(zz),'d':float(len(ns)),'y':float(adm[hadm]['expire']),'age':ag,
                         'co':sum(others.values()),'low':adm[hadm]['low']})
        sub=[r for r in rows if r['low']]  # elective headline
        if len(sub)<800: sub=rows           # fallback to all
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r['y'] for r in sub]);ag=(np.array([r['age'] for r in sub])-60)/10
        co=np.array([r['co'] for r in sub])
        Xb=np.column_stack([z,np.ones(len(z)),ag,ag*ag])
        # B. leakage: co-sedative doses ~ Z | controls
        bl,sl=ols(co,Xb)
        # C. benzo IV base vs +co-sedation control
        bfs,_=ols(d,Xb);brf,_=ols(y,Xb);late_base=brf[0]/bfs[0]
        Xc=np.column_stack([z,np.ones(len(z)),ag,ag*ag,co])
        bfs2,_=ols(d,Xc);brf2,_=ols(y,Xc);late_adj=brf2[0]/bfs2[0]
        print(f'\n=== {tgt.upper()} (n={len(sub)}) ===')
        print(f'  B. LEAKAGE: co-sedative doses ~ Z = {bl[0]:+.3f}(SE {sl[0]:.3f})  [~0 => instrument is drug-specific]')
        print(f'  C. LATE base={late_base:+.4f}  ->  +co-sedation control={late_adj:+.4f}  '
              f'[survives => {tgt}-specific; vanishes => sedation bundle]')
    print('\nVerdict: claimable iff low cross-liberality corr (A), low leakage (B), and LATE survives co-sedation (C).')

if __name__=='__main__':
    main()
