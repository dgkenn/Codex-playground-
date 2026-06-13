"""xrp_gap_check.py -- decisive follow-ups:
 (A) Does trading the mid-vs-BS-fair gap (take YES when mid << BS fair, NO when mid >> fair)
     produce taker edge net of spread+fee? The |gap| is 6.5c > spread 4c -- if the gap is
     REAL (mid wrong) this is the exploit; if mid is right (BS wrong) it loses.
 (B) Robustness of the one positive maker blip (low-tox OOS +0.70c): bootstrap + IS sign.
"""
from __future__ import annotations
import sys, math, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/tmp/ev_xrp')
import numpy as np, pandas as pd
from ladder_baseline_study import load_parquet_windows

def taker_fee(P, M): return np.ceil(M * P * (1 - P) * 100) / 100
def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    s = x.std(ddof=1); return x.mean()/(s/math.sqrt(len(x))) if s>1e-12 else float('nan')
def sharpe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    s = x.std(ddof=1); return x.mean()/s if s>1e-12 else float('nan')

def bs_fair(spot, strike, sig_min, mins_left):
    if not (spot>0 and strike>0 and sig_min>0) or mins_left<=0: return np.nan
    sigT = sig_min*math.sqrt(mins_left)
    if sigT<=0: return 1.0 if spot>strike else 0.0
    d = math.log(spot/strike)/sigT
    return 0.5*(1+math.erf(d/math.sqrt(2)))

# ---- (A) gap trade: use per-minute mid panel with bid/ask to take REAL crossed prices ----
hist = pd.read_parquet('/tmp/ev_xrp/hist_kalshi_xrp15m.parquet')
rows = []
for _, r in hist.iterrows():
    res = int(r['res_up']); mid=np.asarray(r['mid_path'],float)
    bid=np.asarray(r['bid_path'],float); ask=np.asarray(r['ask_path'],float)
    spot=np.asarray(r['spot_path'],float)
    sprev=np.asarray(r['spot_prev'],float) if r['spot_prev'] is not None else None
    strike=float(sprev[-1]) if sprev is not None and len(sprev) and not np.isnan(sprev[-1]) else np.nan
    sig_min=np.nan
    if sprev is not None and len(sprev)>=5:
        sp=sprev[~np.isnan(sprev)]
        if len(sp)>=5:
            lr=np.diff(np.log(sp[sp>0]))
            if len(lr)>=4: sig_min=float(np.std(lr,ddof=1))
    for k in range(2,13):
        if np.isnan(mid[k]) or np.isnan(bid[k]) or np.isnan(ask[k]): continue
        bs=bs_fair(spot[k],strike,sig_min,15-k)
        if np.isnan(bs): continue
        rows.append(dict(ws=int(r['ws']),k=k,mid=mid[k],bid=bid[k],ask=ask[k],res=res,bs=bs))
df=pd.DataFrame(rows)
n=len(df); cut_ws=sorted(df.ws.unique()); c=int(len(cut_ws)*0.6)
is_ws=set(cut_ws[:c]); oos_ws=set(cut_ws[c:])

def gap_trade(d, thr, M):
    """If bs - ask > thr: buy YES at ask (mid too low). If bid - bs > thr: buy NO at 1-bid."""
    pnl=[]
    for r in d.itertuples():
        if r.bs - r.ask > thr:            # YES cheap: buy YES at ask
            P=r.ask; pnl.append((r.res - P) - taker_fee(P,M))
        elif r.bid - r.bs > thr:          # YES rich: buy NO at (1-bid)
            P=1-r.bid; pnl.append(((1-r.res) - P) - taker_fee(P,M))
    return np.array(pnl)

print("="*70); print("(A) MID-vs-BS-FAIR GAP TAKER TRADE (net of crossed spread + fee)"); print("="*70)
for M in (0.07,0.14):
    print(f"  fee M={M}")
    print(f"  {'gap_thr':>8}{'IS net/tr':>11}{'OOS net/tr':>12}{'OOS Sh':>8}{'OOS t':>8}{'OOS n':>7}")
    for thr in (0.02,0.04,0.06,0.08,0.10):
        pi=gap_trade(df[df.ws.isin(is_ws)],thr,M); po=gap_trade(df[df.ws.isin(oos_ws)],thr,M)
        if len(po)<5: continue
        print(f"  {thr:>8.2f}{pi.mean()*100:>+10.2f}c{po.mean()*100:>+11.2f}c{sharpe(po):>+8.3f}{tstat(po):>+8.2f}{len(po):>7}")

# ---- (B) robustness of low-tox maker blip ----
print("\n"+"="*70); print("(B) LOW-TOX MAKER ROBUSTNESS (OOS +0.70c blip)"); print("="*70)
from box_policy_ab import tox_p
fills,ws=load_parquet_windows('xrp')
nC=int(len(ws)*0.6); ws_is,ws_oos=ws[:nC],ws[nC:]
def legs(ws_list):
    out=[]
    for w in ws_list:
        for f in fills[w]:
            if tox_p(f)<0.45: out.append(f['settle'])
    return np.array(out)
pi,po=legs(ws_is),legs(ws_oos)
print(f"  low-tox maker IS: {pi.mean()*100:+.2f}c (t={tstat(pi):+.2f}, n={len(pi)})")
print(f"  low-tox maker OOS:{po.mean()*100:+.2f}c (t={tstat(po):+.2f}, n={len(po)})")
rng=np.random.default_rng(0)
boot=[rng.choice(po,len(po),replace=True).mean()*100 for _ in range(2000)]
lo,hi=np.percentile(boot,[2.5,97.5])
print(f"  OOS bootstrap 95% CI: [{lo:+.2f}c, {hi:+.2f}c]  -> {'spans 0 (NOT significant)' if lo<0<hi else 'excludes 0'}")
print(f"  IS/OOS sign agree: {'YES' if np.sign(pi.mean())==np.sign(po.mean()) else 'NO (sign flip => noise)'}")
print("DONE.")
