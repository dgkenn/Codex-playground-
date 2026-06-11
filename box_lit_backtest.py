import numpy as np, pandas as pd
hist=pd.read_parquet('hist_kalshi_btc15m.parquet')
tap=pd.read_parquet('trades_kalshi_btc15m.parquet').set_index('ws')

# reconstruct per-window fills with all fields needed by every policy
W=[]   # each: dict(ws, fills=[...], res, spot_settle)
for _,h in hist.iterrows():
    w=h.ws
    if w not in tap.index: continue
    t=tap.loc[w]
    bid=np.asarray(h.bid_path,float); ask=np.asarray(h.ask_path,float)
    spot=np.asarray(h.spot_path,float); res=float(h.res_up)
    spot_l=np.concatenate([[np.nan],spot[:-1]])
    ta=np.asarray(t.t,float); pa=np.asarray(t.p,float); sa=np.asarray(t.sz,float); ba=np.asarray(t.buy,bool)
    sset=spot[~np.isnan(spot)]; sset=sset[-1] if len(sset) else np.nan
    fills=[]
    for k in range(2,13):
        b0,a0=bid[k],ask[k]
        if np.isnan(b0) or np.isnan(a0) or not(0.03<=(b0+a0)/2<=0.97): continue
        sn,st=spot_l[k],spot_l[max(k-3,0)]
        mv=(sn/st-1)*1e4 if (sn and st and sn>0 and st>0) else 0.0
        b1=bid[k+1] if k+1<15 else b0; a1=ask[k+1] if k+1<15 else a0
        if np.isnan(b1) or np.isnan(a1): b1,a1=b0,a0
        mid1=(b1+a1)/2; sp1=a1-b1
        lo,hi=w+60*(k+1),w+60*(k+2); i0,i1=np.searchsorted(ta,lo),np.searchsorted(ta,hi)
        db=da=False
        for i in range(i0,i1):
            if db and da: break
            if not db and not ba[i] and pa[i]<=b0+1e-9:
                fills.append(dict(side='bid',settle=res-b0,exit=(mid1-sp1/2)-b0,sig=mv,k=k,
                                  price=b0,spot=spot[k])); db=True
            if not da and ba[i] and pa[i]>=a0-1e-9:
                fills.append(dict(side='ask',settle=a0-res,exit=a0-(mid1+sp1/2),sig=-mv,k=k,
                                  price=round(1-a0,4),spot=spot[k])); da=True
    if fills: W.append(dict(ws=w,fills=fills,res=res,sset=sset))

def walk(win, open_ok=None, unpaired=None, weight=None):
    """return window PnL. open_ok(f)->bool gate; weight(f)->float size; unpaired(f,sset)->pnl for leftover."""
    net=0; pnl=0.0; open_leg=None
    for f in win['fills']:
        if open_ok is not None and (net==0) and not open_ok(f): continue
        step=1 if f['side']=='bid' else -1; nn=net+step
        if abs(nn)>1: continue
        wt=weight(f) if weight else 1.0
        if open_leg is not None and abs(nn)<abs(net):
            pnl += wt*f['settle'] + (weight(open_leg) if weight else 1.0)*open_leg['settle']
            open_leg=None
        else:
            open_leg=f
        net=nn
    if open_leg is not None:
        wt=weight(open_leg) if weight else 1.0
        pnl += wt*(unpaired(open_leg,win['sset']) if unpaired else open_leg['settle'])
    return pnl

def hedge_pnl(f,sset,h=100):
    if np.isnan(f['spot']) or f['spot']<=0 or np.isnan(sset): return f['settle']
    r=(sset/f['spot']-1)*100; sgn=-1.0 if f['side']=='bid' else 1.0
    return f['settle']+sgn*h*r/100.0    # /100 -> back to dollar units (h in cents per 1%)

POLICIES={
 'P0 baseline (hold)':        dict(),
 '1. perp-hedge unpaired':    dict(unpaired=lambda f,s: hedge_pnl(f,s,100)),
 '2. toxicity-exit unpaired': dict(unpaired=lambda f,s: f['exit'] if f['sig']>4 else f['settle']),
 '(ref) sell-cheap unpaired': dict(unpaired=lambda f,s: f['exit'] if f['price']<0.30 else f['settle']),
 '4. completion gate (spot8)':dict(open_ok=lambda f: f['sig']<=8),
 '5a. gamma size-down':       dict(weight=lambda f:(15-f['k'])/13.0),
 '5b. NO-leg preference':     dict(open_ok=lambda f: f['side']=='ask'),
}
def tstat(x):
    x=np.asarray(x,float); 
    return float(x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))) if len(x)>7 and x.std(ddof=1)>0 else np.nan
def maxdd(s):
    c=np.cumsum(s); return float(np.max(np.maximum.accumulate(c)-c)) if len(c) else 0.0
def calmar(s):
    tot=np.sum(s); dd=maxdd(s); return tot/dd if dd>1e-9 else (np.inf if tot>0 else 0.0)

ws=np.array([x['ws'] for x in W]); order=np.argsort(ws); 
cut=int(len(W)*0.6)
print(f"BTC tape: {len(W)} windows  | IS={cut}  OOS={len(W)-cut}\n")
print(f"{'policy':>26}{'IS net':>8}{'IS t':>6}{'OOSnet':>8}{'OOS t':>7}{'OOSCal':>8}{'maxDD$':>8}{'win%':>6}{'std':>6}")
for name,cfg in POLICIES.items():
    p=np.array([walk(W[i],**cfg) for i in order])*1.0
    IS=p[:cut]; OOS=p[cut:]
    print(f"{name:>26}{IS.mean()*100:>+8.2f}{tstat(IS):>+6.1f}{OOS.mean()*100:>+8.2f}{tstat(OOS):>+7.1f}"
          f"{calmar(OOS):>+8.1f}{maxdd(p):>8.2f}{(p>0).mean()*100:>6.0f}{p.std()*100:>6.0f}")
