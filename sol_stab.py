"""sol_stab.py -- stability check on the [0.90,0.97) extreme-favorite taker.
OOS looked +2.3c but IS was flat. Split the full sample into 4 sequential quartiles;
a real edge is positive across quartiles, an artifact is concentrated in one."""
import sys, math
sys.path.insert(0,'/tmp/ev_sol')
import numpy as np
from sol_exploit import load_hist, taker_fee

def quartile_test(rows, M, lo, hi, nq=4):
    n=len(rows); bounds=[int(n*i/nq) for i in range(nq+1)]
    print(f"  [{lo:.2f},{hi:.2f}) M={M:.2f}: sequential quartiles (buy YES @ ask, net fee+spread)")
    allp=[]
    for q in range(nq):
        rset=rows[bounds[q]:bounds[q+1]]
        pnl=[]
        for d in rset:
            for k in range(2,13):
                m=d['mid'][k]; a=d['ask'][k]
                if np.isnan(m) or np.isnan(a): continue
                if lo<=m<hi:
                    pnl.append((d['res']-a)-taker_fee(a,M))
        p=np.array(pnl); allp.extend(pnl)
        if len(p)<5: print(f"    Q{q+1}: n={len(p)} (few)"); continue
        mu=p.mean(); sd=p.std(ddof=1); t=mu/(sd/math.sqrt(len(p))) if sd>0 else float('nan')
        print(f"    Q{q+1}: n={len(p):>4} net={mu*100:+.2f}c t={t:+.2f} winrate={(p>0).mean()*100:.1f}%")
    ap=np.array(allp); mu=ap.mean(); sd=ap.std(ddof=1)
    print(f"    FULL: n={len(ap)} net={mu*100:+.2f}c t={mu/(sd/math.sqrt(len(ap))):+.2f}")

def main():
    sol=load_hist('sol')
    print("=== QUARTILE STABILITY: extreme-favorite taker ===")
    for M in [0.07,0.14]:
        quartile_test(sol,M,0.90,0.97)
    print()
    for M in [0.07,0.14]:
        quartile_test(sol,M,0.90,1.01)

if __name__=='__main__':
    main()
