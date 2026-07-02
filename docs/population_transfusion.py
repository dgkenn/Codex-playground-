#!/usr/bin/env python3
"""
Population-stratified transfusion emulation with ONE clean Hb cross-method instrument, testing whether it
recovers the DIFFERENT known truths of the transfusion-RCT landscape (effect heterogeneity by population):
  general ICU (TRICC)      truth: neutral            -> predict LATE ~ 0
  cardiac surgery (TITRe2) truth: restrictive WORSE  -> transfusion protective -> predict LATE < 0
  acute MI (MINT/REALITY)  truth: liberal trend/NI   -> predict LATE <= 0
  upper GI bleed (Villanueva) truth: restrictive BETTER -> transfusion HARMFUL -> predict LATE > 0  (but instrument
                             is drift-contaminated in active bleeders -> caveat)
Instrument: bloodgas Hb 50811 flag(<7) | CBC Hb 51222 control (cross-method, pure analytic). D=RBC<=24h.
Report per population: n, mort, naive, first-stage F, flag-ITT [95% CI], LATE, balAge, NC(KCl) gate.
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD='/home/user/Codex-playground-/scratchpad/'
RBC={'225168','220996'}; KCL={'225166'}
HIPFX=re.compile(r'^(820|S720|S721|S722)')
MI=re.compile(r'^(410|I21|I22)')
GIBLEED=re.compile(r'^(5780|5781|5789|5307|53021|53100|53101|53120|53140|53160|53200|53240|53300|53340|'
                   r'53400|53440|4560|45620|K920|K921|K922|I8501|I8511|K250|K252|K254|K256|K260|K625)')
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
def load_tx(ids):
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in ids: continue
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
def load_dx():
    S={'hip':set(),'mi':set(),'gib':set()}
    with open(SD+'diagnoses_icd.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        ih=ix['hadm_id'];ic=ix['icd_code']
        for row in r:
            c=row[ic].replace('.','').upper()
            if HIPFX.match(c): S['hip'].add(row[ih])
            if MI.match(c): S['mi'].add(row[ih])
            if GIBLEED.match(c): S['gib'].add(row[ih])
    return S
def load_cardiac():
    s=set()
    try: f=open(SD+'services.csv')
    except FileNotFoundError: return s
    r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
    for row in r:
        if row[ix['curr_service']] in ('CSURG','VSURG'): s.add(row[ix['hadm_id']])
    f.close(); return s
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    cbc=load_seq(SD+'lab_hb.csv',3,20); bg=load_seq(SD+'lab_hbbg.csv',3,20)
    tx=load_tx(RBC); kcl=load_tx(KCL); adm=load_adm(); age,dod=load_pt()
    DX=load_dx(); cardiac=load_cardiac()
    print(f'CBC:{len(cbc)} bg:{len(bg)} RBC:{len(tx)} | hip:{len(DX["hip"])} MI:{len(DX["mi"])} '
          f'GIbleed:{len(DX["gib"])} cardiacSurg:{len(cardiac)}\n')
    MATCH=1.0; base=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in cbc: continue
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        cseq=cbc[hadm]; rt=tx.get(hadm,[]); kt=kcl.get(hadm,[]); first=rt[0] if rt else float('inf')
        for (tb,vb) in bseq:
            if tb>=first: break
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None or not(6.0<=best<=8.0): continue
            dd=dod.get(subj)
            def mort(days): return 1.0 if (dd is not None and 0<=(dd-tb)<=24*days) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            base.append({'hadm':hadm,'cbc':best,'z':1.0 if vb<7.0 else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24 for r in rt) else 0.0,
                         'ncd':1.0 if any(tb<=r<=tb+24 for r in kt) else 0.0,
                         'mh':float(adm[hadm]['expire']),'m30':mort(30),'m90':mort(90),'age':ag,
                         'hip':hadm in DX['hip'],'mi':hadm in DX['mi'],'gib':hadm in DX['gib'],
                         'card':hadm in cardiac})
            break
    def run(rows,ycol,label,truth):
        if len(rows)<200: print(f'  {label:26s} n={len(rows):5d}  [too small]'); return
        z=np.array([r['z'] for r in rows]);d=np.array([r['d'] for r in rows]);y=np.array([r[ycol] for r in rows])
        C=cb([r['cbc'] for r in rows],7.0);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in rows]),X)
        bn,sn=ols(np.array([r['ncd'] for r in rows]),X)
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        late=rf/fs if abs(fs)>1e-3 else float('nan')
        lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        ncsig='!!' if abs(bn[0])>1.96*sn[0] else 'ok'
        print(f'  {label:26s} n={len(rows):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] LATE={late:+.3f} | '
              f'bal={ba[0]:+.2f} NC={ncsig} | truth:{truth}')
    print('== Predicted LATE sign by population (transfusion effect on mortality) ==')
    run(base,'m30','general ICU (TRICC)','~0 neutral')
    run([r for r in base if r['card']],'m90','cardiac surgery (TITRe2)','LATE<0 (restrict worse)')
    run([r for r in base if r['mi'] and not r['gib']],'m30','acute MI (MINT/REALITY)','LATE<=0 (liberal trend)')
    run([r for r in base if r['hip']],'m30','hip fracture (FOCUS)','~0 null')
    run([r for r in base if r['gib']],'m30','upper GI bleed (Villanueva)','LATE>0 harmful (drift caveat)')
    print('\nRecovering the LATE-SIGN PATTERN across populations (0 / <0 / <0 / 0 / >0) = strong validation:')
    print('one clean instrument detecting RCT-matched effect heterogeneity, not just nulls.')

if __name__=='__main__':
    main()
