#!/usr/bin/env python3
"""
RIGOROUS TRICC/TRISS emulation of the Hb-transfusion benchmark:
  - BULLETPROOF instrument: cross-method discordance (CBC Hb 51222 vs blood-gas Hb 50811, same time = pure noise)
  - FAITHFUL emulation: ICU adults, Hb<=9; EXCLUDE active bleeding (the key confounder); 30-day mortality (dod).
Shows the effect of each layer: naive vs cross-method, with vs without the bleeding exclusion.
RCT truth (TRICC 30d / TRISS 90d): restrictive (Hb<7) NON-INFERIOR => null.
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
RBC = {'225168', '220996'}
# active-bleeding ICD prefixes (ICD-9 + ICD-10): GI/variceal/postop/traumatic hemorrhage, hemoptysis, DIC-bleed
BLEED = re.compile(r'^(5780|5781|5789|4560|45620|5307|53021|53100|53101|53120|53140|53160|53200|53240|'
                   r'53300|53340|53400|53440|99811|99812|4590|78630|K920|K921|K922|I8501|I8511|K250|K252|'
                   r'K254|K256|K260|K625|K661|R58|D65|J9481|4550)')

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
    except: return None
def eph(dt): return dt.timestamp()/3600.0 if dt else None

def load_seq(path):
    d={}
    try: f=open(path)
    except FileNotFoundError: return d
    r=csv.reader(f); next(r,None)
    for row in r:
        if len(row)<3: continue
        dt=ep(row[1])
        if dt is None or not row[2] or not row[0]: continue
        try: v=float(row[2])
        except: continue
        if v<=0 or v>25: continue
        d.setdefault(row[0],[]).append((eph(dt),v))
    f.close()
    for k in d: d[k].sort()
    return d
def load_rbc():
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in RBC: continue
            dt=ep(row[2])
            if dt: d.setdefault(row[0],[]).append(eph(dt))
    for k in d: d[k].sort()
    return d
def load_bleeders():
    s=set()
    try: f=open(SD+'diagnoses_icd.csv')
    except FileNotFoundError: return s
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r:
        if BLEED.match(row[ix['icd_code']].replace('.','').upper()): s.add(row[ix['hadm_id']])
    f.close(); return s
def load_icu():
    s=set()
    try: f=open(SD+'icustays.csv')
    except FileNotFoundError: return s
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r: s.add(row[ix['hadm_id']])
    f.close(); return s
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],
                'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
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
                if dt: dod[row[ix['subject_id']]]=dt.timestamp()/3600.0
    return age,dod
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    cbc=load_seq(SD+'lab_hb.csv'); bg=load_seq(SD+'lab_hbbg.csv'); tx=load_rbc()
    adm=load_adm(); age,dod=load_pt(); bleeders=load_bleeders(); icu=load_icu()
    print('=== RIGOROUS TRICC/TRISS emulation: cross-method Hb + active-bleeding exclusion + ICU + 30d mortality ===')
    print(f'CBC:{len(cbc)} bloodgas:{len(bg)} RBC:{len(tx)} bleeders:{len(bleeders)} ICU-hadm:{len(icu)} dod:{len(dod)}\n')
    MATCH=1.0
    base=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in cbc: continue
        cseq=cbc[hadm]; rt=tx.get(hadm,[]); first=rt[0] if rt else float('inf')
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<16: continue
        for (tb,vb) in bseq:
            if tb>=first: break
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None or best>9.0: continue   # TRICC: Hb<=9 qualifying
            # 30-day mortality from dod (fallback to in-hospital expire)
            dd=dod.get(subj)
            y30 = 1.0 if (dd is not None and 0<=(dd-tb)<=24*30) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            base.append({'hadm':hadm,'cbc':best,'bg':vb,'z':1.0 if vb<7.0 else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24 for r in rt) else 0.0,
                         'y':y30,'age':ag,'bleed':hadm in bleeders,'icu':hadm in icu})
            break
    def run(rows,label):
        sub=[r for r in rows if 6.0<=r['cbc']<=8.0]
        if len(sub)<300: print(f'  {label:38s}: n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r['y'] for r in sub]);C=cb([r['cbc'] for r in sub],7.0);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        late=rf/fs if abs(fs)>1e-3 else float('nan')
        print(f'  {label:38s} n={len(sub):5d} 30dMort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.5f}({srf[0]:.5f}) LATE={late:+.3f} | balAge={ba[0]:+.2f}')
    print('Cross-method instrument, 30-day mortality, progressively adding the TRICC emulation filters:')
    run(base,                                             'ALL (no emulation)')
    run([r for r in base if r['icu']],                    'ICU only')
    run([r for r in base if not r['bleed']],              'exclude active bleeding')
    run([r for r in base if r['icu'] and not r['bleed']], 'ICU + exclude bleeding (TRICC-faithful)')
    print('\nRCT truth = NULL (restrictive non-inferior). Watch flag-ITT -> 0 as the bleeding exclusion is applied.')

if __name__=='__main__':
    main()
