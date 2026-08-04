#!/usr/bin/env python3
"""
Phase-1 REFINEMENT — find sepsis phenotypes BEYOND severity (careful-design step).
The k=2 solution on all features is stable but severity-flavored (acidotic/high-lactate/high-variability vs
rest) and leans on _cv features that are measurement-frequency-confounded. Two refinements:
  A. LEVEL-ONLY clustering: drop _cv (and _slope) -> cluster on physiologic STATE (organ-pattern), not
     variability. Re-assess k-stability + whether the split is still just severity.
  B. SEVERITY-RESIDUALIZED clustering (the phenotype_v2 idea): regress each LEVEL feature on a severity index
     (lactate + acidosis + creatinine + the first PC), cluster the RESIDUALS -> phenotypes orthogonal to
     severity. If distinct organ-pattern phenotypes emerge with SIMILAR severity but different profiles, that
     is the novel, non-trivial result.
Uses the cached z-scored matrix sepsis_p1_featcache.pkl (fast). Reports k-sweep ARI, profiles, and the
severity separation across clusters (to show whether clusters differ in PATTERN vs just SEVERITY).
"""
import numpy as np, pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA

SD='/home/user/Codex-playground-/scratchpad/'
RNG=np.random.RandomState(42)

def ksweep(X, tag, krange=range(2,7), nboot=30):
    print(f'\n== {tag}: k-sweep (n={X.shape[0]}, {X.shape[1]} features) ==')
    best=None
    for k in krange:
        ref=KMeans(k,n_init=10,random_state=42).fit(X); rl=ref.labels_
        aris=[]
        for b in range(nboot):
            idx=RNG.randint(0,len(X),len(X))
            lb=KMeans(k,n_init=3,random_state=b).fit(X[idx]).labels_
            # ARI between ref labels on the resampled points and refit labels
            aris.append(adjusted_rand_score(rl[idx], lb))
        sil=silhouette_score(X, rl, sample_size=min(3000,len(X)), random_state=1)
        med=np.median(aris)
        print(f'  k={k}: median ARI={med:.3f} (IQR {np.percentile(aris,25):.3f}-{np.percentile(aris,75):.3f}) silhouette={sil:.3f}')
        if best is None or med>best[1]: best=(k,med,rl)
    return best

def main():
    Xz=pd.read_pickle(SD+'sepsis_p1_featcache.pkl')
    if '_coverage' in Xz.columns: Xz=Xz.drop(columns='_coverage')
    feats=list(Xz.columns)
    level=[c for c in feats if c.endswith('_level')]
    print(f'total features={len(feats)}, level-only={len(level)}')
    # mortality for severity check
    adm=pd.read_csv(SD+'admissions.csv',usecols=['hadm_id','hospital_expire_flag'])
    mort=adm.set_index('hadm_id')['hospital_expire_flag'].reindex(Xz.index).fillna(0).values

    # ---- A. LEVEL-ONLY ----
    XL=Xz[level].values
    k,med,rl=ksweep(XL,'A. LEVEL-ONLY')
    print(f'  PRIMARY k={k} (ARI {med:.3f}); cluster sizes {np.bincount(rl)}')
    for c in range(k):
        m=rl==c; prof=pd.Series(XL[m].mean(0),index=level).sort_values(key=lambda s:-s.abs())
        top=prof[prof.abs()>0.4]
        print(f'    cluster {c} (n={m.sum()}, mort={mort[m].mean():.3f}): '+", ".join(f"{n.replace('_level','')}={v:+.2f}" for n,v in top.items()))

    # ---- B. SEVERITY-RESIDUALIZED (level features residualized on a severity index) ----
    sev_cols=[c for c in level if any(s in c for s in ('lactate','bicarbonate','ph_','creatinine','bun'))]
    S=Xz[sev_cols].values
    sev_index=PCA(1,random_state=0).fit_transform(S)  # 1st PC of severity markers = severity axis
    Xres=np.column_stack([LinearRegression().fit(sev_index,XL[:,j]).predict(sev_index) for j in range(XL.shape[1])])
    Xr=XL-Xres  # residual physiology, severity removed
    k2,med2,rl2=ksweep(Xr,'B. SEVERITY-RESIDUALIZED')
    print(f'  PRIMARY k={k2} (ARI {med2:.3f}); cluster sizes {np.bincount(rl2)}')
    # does severity differ across residual clusters? (want SIMILAR severity, different pattern)
    sev1=sev_index[:,0]
    for c in range(k2):
        m=rl2==c; prof=pd.Series(Xr[m].mean(0),index=level).sort_values(key=lambda s:-s.abs())
        top=prof[prof.abs()>0.4]
        print(f'    cluster {c} (n={m.sum()}, mort={mort[m].mean():.3f}, sevIdx={sev1[m].mean():+.2f}): '+", ".join(f"{n.replace('_level','')}={v:+.2f}" for n,v in top.items()))
    print('\nInterpretation: if the LEVEL-only or residualized clusters differ in ORGAN PATTERN (e.g. renal vs')
    print('hepatic vs hyperlactatemic) at SIMILAR severity, that is a phenotype beyond severity (novel).')
    print('If every split is just monotone in severity/mortality, it is a severity gradient (not novel).')

if __name__=='__main__':
    main()
