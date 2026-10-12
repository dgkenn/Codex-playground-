#!/usr/bin/env python3
"""
Cross-method POTASSIUM assay-noise IV — the reflexive-electrolyte-repletion de-implementation question.
Reflexive KCl replacement fires when measured K crosses a low flag (~3.5 mEq/L). Two same-time K measurements
(chemistry 50971 = lab_k vs blood-gas 50822 = lab_kbg) within 1h => same blood, zero drift => pure analytic
discordance. Conditional on one method (severity control), which side of the flag the OTHER reads is as-if-random.
Per the glucose lesson, we test BOTH directions (Z on the acted-upon measurement) — the valid one has a
correctly-signed strong first stage.

Z = 1(K < FLAG); D = KCl repletion (inputevents 225166) within 6h; control = the other-method K (quadratic
around FLAG); Y = in-hospital / 30-day mortality. Band the control K near FLAG. De-implementation truth:
reflexive repletion of mild hypokalemia is expected to have ~null effect on hard outcomes.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
KCL = {'225166'}   # inputevents Potassium Chloride
def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except: return None
def load_seq(path, lo, hi):
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
RBC = {'225168','220996'}   # negative-control treatment: transfusion is NOT triggered by potassium
def load_kcl():
    d={};nc={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3: continue
            t=ep(row[2])
            if t is None: continue
            if row[1] in KCL: d.setdefault(row[0],[]).append(t)
            elif row[1] in RBC: nc.setdefault(row[0],[]).append(t)
    for k in d: d[k].sort()
    for k in nc: nc[k].sort()
    return d,nc
def load_adm():
    d={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]]={'subject':row[ix['subject_id']],'expire':int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
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
                if dt: dod[row[ix['subject_id']]]=dt
    return age,dod
def load_icu():
    s=set()
    try: f=open(SD+'icustays.csv')
    except FileNotFoundError: return s
    r=csv.reader(f); h=next(r); ix={n:i for i,n in enumerate(h)}
    for row in r: s.add(row[ix['hadm_id']])
    f.close(); return s
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=(np.asarray(t,float)-flag); return np.column_stack([np.ones_like(c),c,c*c])

def main():
    FLAG=3.5
    chem=load_seq(SD+'lab_k.csv',1.5,8); bg=load_seq(SD+'lab_kbg.csv',1.5,8)
    kcl,ncrbc=load_kcl(); adm=load_adm(); age,dod=load_pt(); icu=load_icu()
    print('=== Cross-method POTASSIUM IV (chem 50971 vs blood-gas 50822, same-time = analytic noise) ===')
    print(f'chem:{len(chem)} bg:{len(bg)} KCl-repletion:{len(kcl)} ICU:{len(icu)}\n')
    MATCH=1.0; disc=[]; rows=[]
    for hadm,bseq in bg.items():
        if hadm not in adm or hadm not in chem: continue
        cseq=chem[hadm]; kt=kcl.get(hadm,[])
        subj=adm[hadm]['subject']; ag=age.get(subj,np.nan)
        if math.isnan(ag) or ag<18: continue
        for (tb,vb) in bseq:
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None: continue
            disc.append(vb-best)
            dd=dod.get(subj)
            y30 = 1.0 if (dd is not None and 0<=(dd-tb)<=24*30) else (float(adm[hadm]['expire']) if dd is None else 0.0)
            rt=ncrbc.get(hadm,[])
            rows.append({'chem':best,'bg':vb,'z':1.0 if vb<FLAG else 0.0,'zc':1.0 if best<FLAG else 0.0,
                         'd':1.0 if any(tb<=r<=tb+6 for r in kt) else 0.0,
                         'ncd':1.0 if any(tb<=r<=tb+6 for r in rt) else 0.0,  # NC treatment: RBC (K-independent)
                         'yh':float(adm[hadm]['expire']),'y30':y30,'age':ag,'icu':hadm in icu})
            break
    if len(disc)<200: print('too few pairs',len(disc)); return
    sig=np.std(disc)/math.sqrt(2)
    print(f'CROSS-METHOD potassium sigma = {sig:.3f} mEq/L (n_pairs={len(disc)}) [pure analytic, same-time]\n')
    def run(sub,ycol,label,side):
        zkey='z' if side=='bg' else 'zc'; ckey='chem' if side=='bg' else 'bg'
        if len(sub)<300: print(f'  {label:36s} n={len(sub)} too small'); return
        z=np.array([r[zkey] for r in sub]);d=np.array([r['d'] for r in sub])
        y=np.array([r[ycol] for r in sub]);C=cb([r[ckey] for r in sub],FLAG);X=np.column_stack([z,C])
        ncd=np.array([r['ncd'] for r in sub])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        ba,_=ols(np.array([r['age'] for r in sub]),X)
        bnc,snc=ols(ncd,X)  # NC first-stage: K-flag should NOT predict RBC transfusion
        nc,_=ols(y,np.column_stack([d,np.ones_like(d)]))
        lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        ncsig='!!' if abs(bnc[0])>1.96*snc[0] else 'ok'
        print(f'  {label:36s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | NAIVE={nc[0]:+.4f} | '
              f'FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] | balAge={ba[0]:+.2f} | '
              f'NC-RBC={bnc[0]:+.3f}({ncsig})')
    for side in ['bg','chem']:
        ck='chem' if side=='bg' else 'bg'
        print(f'######## Z = {side}-flag(K<{FLAG}), control = {"chem" if side=="bg" else "bloodgas"} ########')
        for band in [(3.0,4.0),(2.8,4.2)]:
            sub=[r for r in rows if band[0]<=r[ck]<=band[1]]
            print(f'-- band {ck} K {band} (n={len(sub)}) --')
            run(sub,'yh','all, in-hospital',side)
            run([r for r in sub if r['icu']],'y30','ICU, 30-day',side)
        print()
    print('De-implementation truth: reflexive repletion of mild hypokalemia ~ null on hard outcomes.')
    print('Valid direction = correctly-signed strong first stage (KCl given MORE when flagged low).')

if __name__=='__main__':
    main()
