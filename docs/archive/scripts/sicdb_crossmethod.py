#!/usr/bin/env python3
"""
SICdb (Salzburg) EXTERNAL REPLICATION of the CLEAN cross-method Hb transfusion instrument that recovered
TRICC/TRISS on MIMIC. This REPLACES the old temporal (M1,M2 consecutive-draw) sicdb_run.py design, which we
have since proven is drift-contaminated -- we replicate the SAME same-time cross-method discordance design that
worked (CBC-Hb vs blood-gas-Hb, zero biological drift -> pure analytic noise).

Turnkey on access: self-resolves the Hb lab IDs and the RBC transfusion DrugID by NAME from d_references (the
"critical day-one file" the adapter flagged), so it does not depend on unverified hard-coded IDs. Runs only when
sicdb_raw/{d_references,laboratory,medication,cases}.csv[.gz] are present (the poller writes them); otherwise
prints what it is waiting for and exits 0.

Design (identical to MIMIC population_transfusion.py / na_crossmethod.py):
  - two DISTINCT Hb laboratory IDs co-measured within MATCH seconds = a cross-method pair (same blood, same time)
  - Z = 1(method-A Hb < 7 g/dL); severity control = method-B Hb (quadratic control fn around 7); band control 6-8
  - D = 1(RBC transfusion within 24h of the pair); Y = hospital mortality
  - report: n_pairs, cross-method sigma, first-stage F, flag-ITT [95% CI], LATE, age balance, NC gate
  - GATE the result exactly as on MIMIC: correctly-signed strong FS AND NC ~ 0 AND balance ok -> clean replication
RCT truth = NULL (restrictive non-inferior). A cross-site null recovery here is the credibility upgrade.
"""
import csv, gzip, math, os, re, sys
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/sicdb_raw/'
MATCH_S=3600           # same-time window in SECONDS (SICdb offsets are integer seconds from admission)
HB_FLAG=7.0
# CONFIRMED from d_references (SICdb v1.0.8): the CBC-vs-blood-gas Hb cross-method pair, both g/dl.
HB_CBC='289'   # "Hämoglobin (ZL)"  central lab, LOINC 718-7 Hgb Bld-mCnc   (= MIMIC CBC 51222)
HB_BGA='658'   # "Hämoglobin (BGA)" blood-gas analyzer, LOINC 30313-1        (= MIMIC blood-gas 50811)
HB_ARTLAB='288'  # "Hämoglobin (BG) (ZL)" central-lab arterial Hb g/dl (alternate control; LOINC 30313-1)
RBC_ID='2046'  # "Erythrozytenkonzentrat" packed red cells (type Fluid)
def _open(name):
    for ext in ('.csv.gz','.csv'):
        p=SD+name+ext
        if os.path.exists(p):
            return gzip.open(p,'rt',newline='') if p.endswith('.gz') else open(p,newline='')
    return None
def _reader(fh):
    r=csv.reader(fh); h=[c.lstrip('﻿') for c in next(r)]; return r,{n:i for i,n in enumerate(h)},h
def _col(ix,*cands):
    """lenient column resolver: first candidate present (case-insensitive)."""
    low={k.lower():k for k in ix}
    for c in cands:
        if c.lower() in low: return ix[low[c.lower()]]
    return None

def resolve_ids():
    fh=_open('d_references')
    if fh is None: return None,None,None
    r,ix,h=_reader(fh)
    gid=_col(ix,'ReferenceGlobalID','ReferenceID','id','ReferenceGlobalId')
    val=_col(ix,'ReferenceValue','ReferenceName','Value','Name','ReferenceString')
    if gid is None or val is None:
        sys.stderr.write(f'd_references header not understood: {h}\n'); return None,None,None
    name={}
    for row in r:
        if len(row)<=max(gid,val): continue
        name[row[gid]]=row[val]
    fh.close()
    hb_rx=re.compile(r'h[aä]moglobin|hemoglobin|^hb$|^hgb$|\bhb\b', re.I)
    # distinguish CBC vs blood-gas by name hints
    rbc_rx=re.compile(r'erythrozyt|blutkonserve|\bek\b|packed red|rbc|transfus.*eryth', re.I)
    hb_ids={k:v for k,v in name.items() if hb_rx.search(v or '')}
    rbc_ids={k:v for k,v in name.items() if rbc_rx.search(v or '')}
    return hb_ids, rbc_ids, name

def load_lab(hb_ids):
    import os
    pref=SD+'sicdb_lab_hb.csv'   # pre-filtered Hb rows (stream_lab) if present -> avoids reading full laboratory
    if os.path.exists(pref):
        fh=open(pref,newline='')
    else:
        fh=_open('laboratory')
    if fh is None: return {}
    r,ix,h=_reader(fh)
    cid=_col(ix,'CaseID','PatientID','caseid','id_case','ICUStayID')
    lid=_col(ix,'LaboratoryID','ReferenceGlobalID','LabID','ItemID')
    off=_col(ix,'Offset','LabOffset','OffsetLab','Time')
    v  =_col(ix,'LaboratoryValue','Value','Val','Result','LabValue')
    if None in (cid,lid,off,v):
        sys.stderr.write(f'laboratory header not understood: {h}\n'); return {}
    d={}
    for row in r:
        if len(row)<=max(cid,lid,off,v): continue
        if row[lid] not in hb_ids: continue
        try: t=float(row[off]); val=float(str(row[v]).replace(',','.'))  # German comma-decimal safe
        except: continue
        if not (3<=val<=20): continue
        d.setdefault(row[cid],[]).append((t,val,row[lid]))
    fh.close()
    for k in d: d[k].sort()
    return d

def load_rbc(rbc_ids):
    fh=_open('medication')
    if fh is None: return {}
    r,ix,h=_reader(fh)
    cid=_col(ix,'CaseID','PatientID','caseid')
    did=_col(ix,'DrugID','ReferenceGlobalID','MedicationID','ItemID')
    off=_col(ix,'Offset','OffsetDrugStart','DrugOffset','Time')
    if None in (cid,did,off):
        sys.stderr.write(f'medication header not understood: {h}\n'); return {}
    d={}
    for row in r:
        if len(row)<=max(cid,did,off): continue
        if row[did] not in rbc_ids: continue
        try: t=float(row[off])
        except: continue
        d.setdefault(row[cid],[]).append(t)
    fh.close()
    for k in d: d[k].sort()
    return d

def load_cases():
    fh=_open('cases')
    if fh is None: return {}
    r,ix,h=_reader(fh)
    cid=_col(ix,'CaseID','id','PatientID','caseid')
    age=_col(ix,'AgeOnAdmission','Age')
    dis=_col(ix,'HospitalDischargeType','DischargeType','HospOutcome')
    dod=_col(ix,'OffsetOfDeath','DeathOffset')
    tos=_col(ix,'TimeOfStay','HospitalLengthOfStay','LengthOfStay')
    icd=_col(ix,'ICD10Main','ICD10','MainDiagnosis')
    MI=re.compile(r'^I2[12]')
    d={}
    for row in r:
        if cid is None or len(row)<=cid: continue
        try: a=float(row[age]) if age is not None and row[age] else np.nan
        except: a=np.nan
        # in-hospital mortality: HospitalDischargeType CODE 3130 = "Sterbefall" (death), OR death offset within stay
        mort=0.0
        if dis is not None and dis<len(row) and str(row[dis]).strip('"')=='3130': mort=1.0
        if dod is not None and dod<len(row) and row[dod]:
            try:
                do=float(row[dod]); ts=float(row[tos]) if (tos is not None and tos<len(row) and row[tos]) else 1e12
                if 0<=do<=ts: mort=1.0
            except: pass
        mi = bool(icd is not None and icd<len(row) and MI.match(str(row[icd]).strip('"')))
        d[row[cid]]={'age':a,'mort':mort,'mi':mi}
    fh.close()
    return d

def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    if _open('d_references') is None:
        print('AWAITING SICdb data in sicdb_raw/ (poller writes d_references/laboratory/medication/cases). '
              'Nothing to do yet.'); return
    hb_ids,rbc_ids,name=resolve_ids()
    print('=== SICdb cross-method Hb transfusion replication ===')
    print(f'Resolved Hb laboratory IDs (by name): {hb_ids}')
    print(f'Resolved RBC transfusion Drug IDs (by name): {rbc_ids}')
    if not hb_ids or len(hb_ids)<2:
        print('NEED >=2 distinct Hb lab IDs for a cross-method pair. Inspect names above; '
              'if SICdb has only one Hb method, cross-method replication is not possible (report honestly).');
    if not rbc_ids:
        print('WARNING: no RBC transfusion DrugID resolved by name -- inspect d_references names for the '
              'German term actually used (Erythrozytenkonzentrat/EK).')
    # use the CONFIRMED CBC(289)-vs-BGA(658) pair, mirroring MIMIC (flag on blood-gas, control on CBC).
    lab=load_lab({HB_CBC:1,HB_BGA:1,HB_ARTLAB:1}); rbc=load_rbc({RBC_ID:1}); cases=load_cases()
    print(f'cases:{len(cases)} cases-with-Hb:{len(lab)} cases-with-RBC:{len(rbc)}')
    disc=[]; rows=[]
    for cid,seq in lab.items():
        if cid not in cases: continue
        a=cases[cid]['age']
        rt=rbc.get(cid,[]); first=rt[0] if rt else float('inf')
        cbc=[(t,v) for (t,v,i) in seq if i==HB_CBC]
        bga=[(t,v) for (t,v,i) in seq if i==HB_BGA]
        # flag on the BGA (point-of-care) reading; control = nearest CBC within MATCH_S; first pre-tx pair
        for (tb,vb) in bga:
            if tb>=first: break
            best=None;bd=MATCH_S+1
            for (tc,vc) in cbc:
                if abs(tc-tb)<=MATCH_S and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
            if best is None: continue
            disc.append(vb-best)
            rows.append({'a':vb,'b':best,'z':1.0 if vb<HB_FLAG else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24*3600 for r in rt) else 0.0,
                         'y':cases[cid]['mort'],'age':a,'mi':cases[cid].get('mi',False)})
            break
    if len(rows)<200:
        print(f'only {len(rows)} cross-method pairs -- too few (check ID resolution + co-measurement).'); return
    sig=np.std(disc)/math.sqrt(2)
    print(f'\ncross-method Hb sigma = {sig:.3f} g/dL (n_pairs={len(rows)})')
    def analyze(rowset,label):
        sub=[r for r in rowset if 6.0<=r['b']<=8.0]
        if len(sub)<120: print(f'  {label:28s} n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r['y'] for r in sub])
        C=cb([r['b'] for r in sub],HB_FLAG);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ages=np.array([r['age'] for r in sub]); ba=ols(ages,X)[0] if not np.isnan(ages).all() else [float('nan')]
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        late=rf/fs if abs(fs)>1e-3 else float('nan'); lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        print(f'  {label:28s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] LATE={late:+.3f} | balAge={ba[0]:+.2f}')
    print(f'in-hospital mortality (all pairs) = {np.mean([r["y"] for r in rows]):.3f}  |  MI cases in pairs = {sum(r["mi"] for r in rows)}')
    analyze(rows,'ALL ICU (TRICC/TRISS)')
    analyze([r for r in rows if r['mi']],'acute MI (I21/I22) [Paper#1]')
    print('\nRCT truth: ALL=NULL (restrictive non-inferior). MI: MINT liberal-trend (open). Cross-site MI pool = Paper #1.')

if __name__=='__main__':
    main()
