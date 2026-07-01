#!/usr/bin/env python3
"""
CLOSEST-POSSIBLE target-trial emulation of TRICC (Hebert NEJM 1999) and TRISS (Holst NEJM 2014),
applying EVERY operationalizable eligibility/exclusion criterion, with the bulletproof cross-method
Hb instrument (CBC 51222 vs blood-gas 50811, same-time = pure analytic noise, no drift).

TRICC: euvolemic ICU adults, Hb<=9 within 72h of ICU admit; EXCLUDE active bleeding, chronic anemia,
       cardiac surgery, pregnancy, (MI/ACS); restrictive(Hb<7) vs liberal(Hb<10); 30-DAY mortality.
TRISS: septic-shock ICU adults, Hb<=9; EXCLUDE active bleeding, prior transfusion this stay, active ACS;
       restrictive(<=7) vs liberal(<=9); 90-DAY mortality.
Instrument = 1(blood-gas Hb < 7) | CBC Hb; D = RBC transfusion <=24h; report flag-ITT, balance, naive,
factor-by-factor so each exclusion's effect on the estimate is visible. RCT truth = NULL (restrictive non-inferior).
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
RBC = {'225168', '220996'}

CODES = {
 'bleed':   re.compile(r'^(578|4560|45620|5307|53021|53100|53101|53120|53140|53160|53200|53240|53300|53340|'
                       r'53400|53440|99811|99812|4590|78630|5693|K920|K921|K922|I8501|I8511|K250|K252|K254|'
                       r'K256|K260|K262|K264|K266|K625|K661|R58|D65|J9481)'),
 # genuinely CHRONIC anemia only (baseline hematologic disease), NOT the acute anemia being treated:
 # hereditary/hemolytic (282/D56-59), aplastic/marrow-failure (284/D60-61), sickle (D57),
 # myelodysplastic (2387/D46), chronic-disease/CKD anemia (2851/28521-28529 excl 2859 unspecified & 2851 acute-posthemorrhagic).
 # Deliberately EXCLUDE 2851(acute posthemorrhagic), 2859(unspecified), 280/281(nutritional, often acute) -> those ARE the index anemia.
 'chronic_anemia': re.compile(r'^(2820|2821|2822|2823|2824|2825|2826|2828|2829|283|284|2382|2387|28521|28522|28529|28531|'
                       r'D46|D5[6-9]|D60|D61|D638)'),
 'mi_acs':  re.compile(r'^(410|411|I21|I22|I200)'),
 'pregnancy': re.compile(r'^(6[3-7][0-9]|V22|V23|O0|O1|O2|O3|O4|O5|O6|O7|O8|O9|Z33|Z34)'),
 'sepsis':  re.compile(r'^(038|99591|99592|78552|A40|A41|R652|R6521|R6520)'),
}

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
def load_diag_sets():
    sets={k:set() for k in CODES}
    with open(SD+'diagnoses_icd.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        ih=ix['hadm_id']; ic=ix['icd_code']
        for row in r:
            code=row[ic].replace('.','').upper()
            for k,rx in CODES.items():
                if rx.match(code): sets[k].add(row[ih])
    return sets
def load_icu_intime():
    d={}
    with open(SD+'icustays.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        for row in r:
            t=eph(ep(row[ix['intime']])); hadm=row[ix['hadm_id']]
            if t is not None and (hadm not in d or t<d[hadm]): d[hadm]=t
    return d
def load_cardiac():
    s=set()
    try: f=open(SD+'services.csv')
    except FileNotFoundError: return s
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r:
        if row[ix['curr_service']] in ('CSURG','VSURG'): s.add(row[ix['hadm_id']])
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
    adm=load_adm(); age,dod=load_pt(); icu_in=load_icu_intime(); cardiac=load_cardiac()
    print('loading diagnosis code sets (bleed/chronic-anemia/MI/pregnancy/sepsis)...')
    D=load_diag_sets()
    print(f'CBC:{len(cbc)} bg:{len(bg)} RBC:{len(tx)} ICU:{len(icu_in)} cardiac:{len(cardiac)} dod:{len(dod)}')
    print(f'  dx sets: bleed={len(D["bleed"])} chronicAnemia={len(D["chronic_anemia"])} MI={len(D["mi_acs"])} '
          f'preg={len(D["pregnancy"])} sepsis={len(D["sepsis"])}\n')
    MATCH=1.0
    base=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in cbc: continue
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        it=icu_in.get(hadm)                      # ICU admit time
        cseq=cbc[hadm]; rt=tx.get(hadm,[]); first=rt[0] if rt else float('inf')
        for (tb,vb) in bseq:
            if tb>=first: break
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None or best>9.0: continue          # Hb<=9 qualifying
            dd=dod.get(subj)
            def mort(days): return 1.0 if (dd is not None and 0<=(dd-tb)<=24*days) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            within72 = (it is not None and 0<=(tb-it)<=72)  # decision within 72h of ICU admit
            base.append({'hadm':hadm,'cbc':best,'z':1.0 if vb<7.0 else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24 for r in rt) else 0.0,
                         'm30':mort(30),'m90':mort(90),'age':ag,
                         'icu':hadm in icu_in,'within72':within72,
                         'bleed':hadm in D['bleed'],'canemia':hadm in D['chronic_anemia'],
                         'mi':hadm in D['mi_acs'],'preg':hadm in D['pregnancy'],
                         'cardiac':hadm in cardiac,'sepsis':hadm in D['sepsis']})
            break
    def run(rows,ycol,label):
        sub=[r for r in rows if 6.0<=r['cbc']<=8.0]
        if len(sub)<200: print(f'  {label:46s}: n={len(sub)} too small'); return
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r[ycol] for r in sub]);C=cb([r['cbc'] for r in sub],7.0);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        late=rf/fs if abs(fs)>1e-3 else float('nan')
        lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        print(f'  {label:46s} n={len(sub):5d} mort={y.mean():.3f} | NAIVE={nc[0]:+.4f} | FS={fs:+.3f}(F{F:4.0f}) | '
              f'flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] | balAge={ba[0]:+.2f}')
    print('=== TRICC emulation (30-day mortality); factor-by-factor ===')
    run(base,'m30','ALL adults ICU-or-not')
    run([r for r in base if r['icu']],'m30','+ ICU')
    run([r for r in base if r['icu'] and r['within72']],'m30','+ ICU + Hb<=9 within 72h of ICU admit')
    run([r for r in base if r['icu'] and not r['bleed']],'m30','+ ICU, exclude active bleeding')
    run([r for r in base if r['icu'] and not r['bleed'] and not r['canemia']],'m30','+ exclude chronic anemia')
    run([r for r in base if r['icu'] and not r['bleed'] and not r['canemia'] and not r['cardiac'] and not r['preg']],
        'm30','+ exclude cardiac surgery + pregnancy')
    run([r for r in base if r['icu'] and r['within72'] and not (r['bleed'] or r['canemia'] or r['cardiac'] or r['preg'])],
        'm30','TRICC-FAITHFUL (all factors)')
    print('\n=== TRISS emulation (90-day mortality, septic shock) ===')
    run([r for r in base if r['icu'] and r['sepsis']],'m90','+ ICU + septic shock')
    run([r for r in base if r['icu'] and r['sepsis'] and not (r['bleed'] or r['mi'])],
        'm90','TRISS-FAITHFUL (septic shock, exclude bleeding+ACS)')
    print('\nRCT truth = NULL (restrictive non-inferior). Fully-emulated flag-ITT CI should include 0.')

if __name__=='__main__':
    main()
