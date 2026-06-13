"""sol_fav.py -- drill into the extreme-favorite region where FLB bias has the right sign.
The mid-bucket calibration showed favorites at mid>=0.85 realize ABOVE mid (+2.7 to +3.2pp).
Question: can we capture that as a TAKER (buy YES at ask, pay fee) or only as a MAKER?
Also test the maker-favorite play (rest a YES bid in the favorite zone, ~0 fee, but adverse selection)."""
from __future__ import annotations
import sys, math
sys.path.insert(0, '/tmp/ev_sol')
import numpy as np
from sol_exploit import load_hist, taker_fee, load_parquet_windows

def fav_taker_detail(rows, M, mid_lo, mid_hi, is_frac=0.6):
    """Buy YES at ask when mid in [mid_lo, mid_hi). Report IS/OOS net of fee+spread."""
    n = len(rows); cut = int(n*is_frac)
    sets = {'IS': rows[:cut], 'OOS': rows[cut:]}
    out = {}
    for label, rset in sets.items():
        pnl = []; asks=[]; mids=[]
        for d in rset:
            for k in range(2,13):
                m=d['mid'][k]; a=d['ask'][k]; b=d['bid'][k]
                if np.isnan(m) or np.isnan(a) or np.isnan(b): continue
                if mid_lo <= m < mid_hi:
                    fee=taker_fee(a,M)
                    pnl.append((d['res']-a)-fee); asks.append(a); mids.append(m)
        p=np.array(pnl)
        if len(p)<5: out[label]=(len(p),)+ (float('nan'),)*4; continue
        mu=p.mean(); sd=p.std(ddof=1); t=mu/(sd/math.sqrt(len(p))) if sd>0 else float('nan')
        out[label]=(len(p), mu*100, mu/sd if sd>0 else float('nan'), t, np.mean(asks))
    return out

def fav_maker_detail(asset, mid_lo, mid_hi, is_frac=0.6):
    """MAKER favorite: among reconstructed maker fills, keep only YES-equiv fills in the
    favorite zone and hold to settlement. Maker fee ~0. settle is already P&L to settlement.
    This shows whether resting on the favorite side earns or gets adversely selected."""
    fpw, ws = load_parquet_windows(asset)
    n=len(ws); cut=int(n*is_frac)
    sets={'IS':ws[:cut],'OOS':ws[cut:]}
    out={}
    for label,wsl in sets.items():
        pnl=[]
        for w in wsl:
            for f in fpw[w]:
                p_yeq = f['p'] if f['side']=='bid' else round(1.0-f['p'],4)
                if mid_lo <= p_yeq < mid_hi:
                    pnl.append(f['settle'])
        p=np.array(pnl)
        if len(p)<5: out[label]=(len(p),)+(float('nan'),)*3; continue
        mu=p.mean(); sd=p.std(ddof=1); t=mu/(sd/math.sqrt(len(p))) if sd>0 else float('nan')
        out[label]=(len(p), mu*100, mu/sd if sd>0 else float('nan'), t)
    return out

def main():
    sol=load_hist('sol')
    print("=== EXTREME-FAVORITE TAKER (buy YES at ask) net of fee+spread ===")
    print(f"{'M':>5}{'mid band':>14}{'set':>5}{'n':>7}{'net':>9}{'Sh':>8}{'t':>7}{'avg_ask':>9}")
    for M in [0.07,0.14]:
        for (lo,hi) in [(0.80,0.90),(0.85,0.95),(0.90,0.97),(0.85,1.01),(0.90,1.01)]:
            o=fav_taker_detail(sol,M,lo,hi)
            for label in ['IS','OOS']:
                r=o[label]
                aa = r[4] if len(r)>4 and not (isinstance(r[4],float) and math.isnan(r[4])) else float('nan')
                print(f"{M:>5.2f}  [{lo:.2f},{hi:.2f}){label:>5}{r[0]:>7}{r[1]:>+8.2f}c{r[2]:>+8.3f}{r[3]:>+7.2f}{aa:>9.3f}")
    print("\n=== EXTREME-FAVORITE MAKER (rest YES bid, hold to settle, fee~0) ===")
    print(f"{'mid band':>14}{'set':>5}{'n':>7}{'net':>9}{'Sh':>8}{'t':>7}")
    for (lo,hi) in [(0.80,0.90),(0.85,0.95),(0.90,0.97),(0.85,1.01),(0.55,0.85)]:
        o=fav_maker_detail('sol',lo,hi)
        for label in ['IS','OOS']:
            r=o[label]
            print(f"  [{lo:.2f},{hi:.2f}){label:>5}{r[0]:>7}{r[1]:>+8.2f}c{r[2]:>+8.3f}{r[3]:>+7.2f}")

if __name__=='__main__':
    main()
