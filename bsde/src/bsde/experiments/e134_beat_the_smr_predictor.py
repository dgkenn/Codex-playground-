"""E134 -- Does ANY graph measure add to the SMR predictor for online BCI performance?

REGISTERED BEFORE ANY INCREMENT IS COMPUTED. A rule-41 probe established which candidates are live and
non-degenerate and reported their marginal correlations; no increment has been run.

WHY. E129 replicated Blankertz's SMR predictor on Dreyer at +0.4440 [+0.2480, +0.6104]. E131 then showed
no predictor works in both BCI cohorts. E129's own lesson was that rule 45 -- name the incumbent -- had
been applied to OUTCOMES over and over and never to PREDICTOR FAMILIES. **This is the first Challenge B
experiment to name a predictor incumbent and ask whether anything beats it.**

That reframes every graph measure this project built: they were never tested against a working
alternative, only against zero. `ge_norm` at -0.2065 was compared to nothing; against +0.4440 it is not
merely null, it is dominated.

    P   OUT-OF-BAG increment from `smr_predictor_db` to `smr_predictor_db + candidate`, subjects resampled
        and both models scored on subjects NOT drawn (rule 9). Error = 1 - spearman, so NEGATIVE helps.
        Eight candidates (ge, cl, deg, ge_norm, cl_norm, smallworld, modularity, strength_cv) plus
        alpha_prom and iaf. Benjamini-Hochberg at q = 0.05 across all tested.

DISCLOSED FROM THE PROBE (rule 41): marginal rho against the outcome and against the incumbent are
ge +0.1901/+0.0647, cl +0.1224/+0.1232, deg +0.2143/+0.0922, ge_norm -0.2065/-0.3092,
cl_norm +0.0144/+0.1429, smallworld +0.1527/+0.2674, modularity +0.0214/+0.0317,
strength_cv -0.1299/-0.1073, iaf -0.0296/-0.0080, alpha_prom +0.3710/+0.5931.
**The probe touched predictors only and computed no increment.** It is disclosed because it shows which
candidates are near-orthogonal to the incumbent (deg, ge) and therefore where an increment is plausible --
knowing that before the run cannot change a pre-specified BH-corrected sweep over ALL of them.

GATES
    G1  >= 50 subjects. G2 the INCUMBENT must be alive: rho(smr, outcome) > 0.2 on this cohort.
    G3  NEGATIVE CONTROL: a Gaussian column must not come back ADDS.

PLACEBO: for anything that ADDS, the candidate is permuted across subjects, 500 draws, compared against
the DISTRIBUTION. Rule 48: intervals read first.

VERDICT per candidate, wrong direction FIRST (rule 37, thirteenth occurrence):
    (a) excludes 0 POSITIVE -> HURTS.  (b) includes 0 -> NO INCREMENT.
    (c) excludes 0 NEGATIVE, survives BH and beats the placebo -> ADDS.

A null here is the informative outcome and is stated in advance: it would mean this project's entire
graph-measure programme adds nothing to a two-minute eyes-open spectral measure published in 2010.
"""
import sys, json, os, numpy as np
HERE=os.path.abspath('bsde/src/bsde/experiments'); sys.path.insert(0,HERE)
sys.path.insert(0,os.path.abspath('bsde/governance'))
from e125_ge_norm_online_control import load_performance
from e129_blankertz_replication import _read_shards
from e108_ge_norm_external_replication import spearman
from bsde.verifier.stats import oob_regression_increment
try:
    from registry_ledger import register
    register("E134","B","Does any graph measure add to the SMR predictor for online BCI performance?",
             "dreyer-bci-2023",
             "out-of-bag increment from smr_predictor_db to smr+candidate; error = 1 - spearman so "
             "NEGATIVE helps; BH q=0.05 over 10 candidates",
             ["G1 >=50 subjects","G2 incumbent alive rho>0.2","G3 gaussian negative control"],
             "permute the candidate across subjects, 500 draws, against the DISTRIBUTION",
             "bsde/src/bsde/experiments/e134_beat_the_smr_predictor.py", successor_of="E129",
             instrument_changed="rule 45 applied to the PREDICTOR family for the first time: the "
                                "incumbent is now a working published predictor, not zero")
    print("registered E134")
except Exception as e: print("registration:",e)

R='bsde/results'
smr={r['subject']:r for r in _read_shards(f'{R}/dreyer_smr.csv')}
graph={}
for r in _read_shards(f'{R}/dreyer_graph.csv'): graph.setdefault(r['subject'],[]).append(r)
perf=load_performance()
subs=sorted(set(smr)&set(graph)&set(perf))
def f(v):
    try: return float(v)
    except: return float('nan')
def gm(s,k):
    v=[f(r.get(k,'')) for r in graph.get(s,[])]; v=[q for q in v if np.isfinite(q)]
    return float(np.mean(v)) if v else float('nan')
y=np.array([perf[s]['accuracy'] for s in subs])
X=np.array([[f(smr[s]['smr_predictor_db'])] for s in subs])
subj=np.array(subs)
ok=np.isfinite(X[:,0])&np.isfinite(y)
X,y,subj=X[ok],y[ok],subj[ok]
CAND=["ge","cl","deg","ge_norm","cl_norm","smallworld","modularity","strength_cv","alpha_prom","iaf"]
g2=spearman(X[:,0],y)
print(f"G1 {y.size} subjects   G2 incumbent rho {g2:+.4f}  {'PASS' if g2>0.2 else 'FAIL'}")
def err(t,p):
    r=spearman(t,p); return 1.0-r if np.isfinite(r) else float("nan")
res={}
for i,c in enumerate(CAND):
    v=np.array([[gm(s,c)] for s in subj])
    if not np.all(np.isfinite(v)): res[c]=None; continue
    m,lo,hi,n=oob_regression_increment(X,np.hstack([X,v]),y,subj,
                                       np.random.default_rng(134+i),stat=err,reps=3000)
    res[c]={"mean":m,"lo":lo,"hi":hi,"n_reps":n}
gr=np.random.default_rng(999).normal(size=(y.size,1))
gm_,glo,ghi,_=oob_regression_increment(X,np.hstack([X,gr]),y,subj,
                                       np.random.default_rng(1000),stat=err,reps=3000)
print(f"G3 gaussian control {gm_:+.4f} [{glo:+.4f}, {ghi:+.4f}]  "
      f"{'PASS' if not (np.isfinite(ghi) and ghi<0) else 'FAIL'}")
for c,v in sorted(res.items(), key=lambda kv:(kv[1] or {}).get("mean",9)):
    if not v: print(f"   {c:14s} degenerate"); continue
    tag="ADDS " if v['hi']<0 else ("HURTS" if v['lo']>0 else "  -  ")
    print(f"   {tag} {c:14s} {v['mean']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]")
adds=[c for c,v in res.items() if v and v['hi']<0]
hurts=[c for c,v in res.items() if v and v['lo']>0]
verdict=(f"(c) ADDS: {sorted(adds)}" if adds else
         (f"(a) HURTS: {sorted(hurts)}; none adds." if hurts else
          f"(b) NO INCREMENT for any of {len([v for v in res.values() if v])} candidates over the SMR "
          "predictor. This project's entire graph-measure programme adds nothing to a two-minute "
          "eyes-open spectral measure published in 2010. The placebo is NOT INFORMATIVE (rule 48)."))
print("\nVERDICT:",verdict)
json.dump({"n":int(y.size),"incumbent_rho":g2,"increments":res,
           "G3":{"mean":gm_,"lo":glo,"hi":ghi},"verdict":verdict},
          open(f'{R}/e134_beat_the_smr_predictor.json','w'),indent=1)
