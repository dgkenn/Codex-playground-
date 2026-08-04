#!/usr/bin/env python3
"""
Phase 3 (MIMIC) — differential CAUSAL transfusion response across sepsis phenotypes, instrument-anchored.
CIRCULARITY GUARD: phenotypes are derived from level features EXCLUDING hemoglobin & hematocrit (else
"anemic phenotype benefits from transfusion" is tautological). Then within each Hb-INDEPENDENT phenotype we run
the clean cross-method Hb transfusion instrument (bloodgas Hb<7 flag | CBC Hb control, D=RBC<=24h) and compare
the transfusion LATE across phenotypes. A differential LATE (interaction) that is causally identified (valid
instrument per phenotype) is the novel, non-confounded HTE result the field lacks.
"""
import csv, math
from datetime import datetime
import numpy as np, pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA

SD='/home/user/Codex-playground-/scratchpad/'
RBC={'225168','220996'}
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
def load_rbc():
    d={}
    with open(SD+'repletions.csv') as f:
        r=csv.reader(f); next(r,None)
        for row in r:
            if len(row)<3 or row[1] not in RBC: continue
            t=ep(row[2])
            if t is not None: d.setdefault(row[0],[]).append(t)
    for k in d: d[k].sort()
    return d
def ols(y,X):
    X=np.asarray(X,float);y=np.asarray(y,float)
    Bi=np.linalg.pinv(X.T@X);b=Bi@(X.T@y);r=y-X@b;n,k=X.shape
    S=X*r[:,None];cov=Bi@(S.T@S)@Bi*(n/max(n-k,1));return b,np.sqrt(np.diag(cov))
def cb(t,flag):
    c=np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c),c,c*c])

def main():
    # ---- Hb-INDEPENDENT phenotypes (circularity guard) ----
    Xz=pd.read_pickle(SD+'sepsis_p1_featcache.pkl')
    if '_coverage' in Xz.columns: Xz=Xz.drop(columns='_coverage')
    level=[c for c in Xz.columns if c.endswith('_level')]
    pheno_feats=[c for c in level if not c.startswith(('hemoglobin','hematocrit'))]  # EXCLUDE Hb/Hct
    XL=Xz[pheno_feats].values
    sev_cols=[c for c in pheno_feats if any(s in c for s in ('lactate','bicarbonate','ph_','creatinine','bun'))]
    sev=PCA(1,random_state=0).fit_transform(Xz[sev_cols].values)
    Xres=np.column_stack([LinearRegression().fit(sev,XL[:,j]).predict(sev) for j in range(XL.shape[1])])
    Xr=XL-Xres
    K=3
    lab=KMeans(K,n_init=10,random_state=42).fit_predict(Xr)
    pheno={h:int(l) for h,l in zip(Xz.index.astype(str),lab)}
    print(f'Hb-independent phenotypes (excl Hb/Hct), k={K}, sizes={np.bincount(lab)}')
    for c in range(K):
        m=lab==c; prof=pd.Series(Xr[m].mean(0),index=pheno_feats).sort_values(key=lambda s:-s.abs())
        top=prof[prof.abs()>0.4]
        print(f'  pheno {c} (n={m.sum()}): '+", ".join(f"{n.replace('_level','')}={v:+.2f}" for n,v in top.items()))

    # ---- cross-method Hb transfusion instrument, restricted to sepsis-phenotype patients, per phenotype ----
    cbc=load_seq(SD+'lab_hb.csv',3,20); bg=load_seq(SD+'lab_hbbg.csv',3,20); tx=load_rbc()
    adm={}
    with open(SD+'admissions.csv') as f:
        r=csv.reader(f);h=next(r);ix={n:i for i,n in enumerate(h)}
        for row in r: adm[row[ix['hadm_id']]]=int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0
    MATCH=1.0; rows=[]
    for hadm,bseq in bg.items():
        if hadm not in pheno or hadm not in cbc or hadm not in adm: continue
        cseq=cbc[hadm]; rt=tx.get(hadm,[]); first=rt[0] if rt else float('inf')
        for (tb,vb) in bseq:
            if tb>=first: break
            best=None;bd=MATCH+1
            for (tc,vc) in cseq:
                if abs(tc-tb)<=MATCH and abs(tc-tb)<bd: best=vc;bd=abs(tc-tb)
                if tc>tb+MATCH: break
            if best is None or not(6.0<=best<=8.0): continue
            rows.append({'cbc':best,'z':1.0 if vb<7.0 else 0.0,
                         'd':1.0 if any(tb<=r<=tb+24 for r in rt) else 0.0,
                         'y':float(adm[hadm]),'ph':pheno[hadm]})
            break
    print(f'\nsepsis-phenotype patients in cross-method Hb 6-8 transfusion cohort: n={len(rows)}')
    def run(sub,label):
        if len(sub)<120: print(f'  {label:20s} n={len(sub)} too small'); return None
        z=np.array([r['z'] for r in sub]);d=np.array([r['d'] for r in sub]);y=np.array([r['y'] for r in sub])
        C=cb([r['cbc'] for r in sub],7.0);X=np.column_stack([z,C])
        bfs,sfs=ols(d,X);brf,srf=ols(y,X);fs,rf=bfs[0],brf[0]
        F=(fs/sfs[0])**2 if sfs[0]>0 else 0
        late=rf/fs if abs(fs)>1e-3 else float('nan'); lo,hi=rf-1.96*srf[0],rf+1.96*srf[0]
        print(f'  {label:20s} n={len(sub):5d} mort={y.mean():.3f} tx={d.mean():.3f} | FS={fs:+.3f}(F{F:4.0f}) | '
              f'flag-ITT={rf:+.4f}[{lo:+.3f},{hi:+.3f}] LATE={late:+.3f}')
        return rf,srf[0]
    print('Transfusion causal effect (flag-ITT / LATE) BY Hb-independent sepsis phenotype:')
    run(rows,'ALL sepsis')
    ests={}
    for c in range(K):
        e=run([r for r in rows if r['ph']==c],f'phenotype {c}')
        if e: ests[c]=e
    # interaction: pairwise difference in flag-ITT with pooled SE
    print('\nDifferential response (pairwise flag-ITT differences):')
    ks=list(ests)
    for i in range(len(ks)):
        for j in range(i+1,len(ks)):
            a,b=ests[ks[i]],ests[ks[j]]; diff=a[0]-b[0]; se=math.hypot(a[1],b[1]); z=diff/se if se>0 else 0
            print(f'  pheno{ks[i]} - pheno{ks[j]}: {diff:+.4f} (SE {se:.4f}, z={z:+.2f})')
    print('\nA significant interaction (|z|>1.96) with valid per-phenotype instruments = causal differential')
    print('transfusion response across Hb-INDEPENDENT sepsis phenotypes (novel, non-confounded HTE).')

if __name__=='__main__':
    main()
