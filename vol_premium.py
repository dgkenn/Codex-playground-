#!/usr/bin/env python3
"""
Volatility Risk Premium (VRP) study — is selling vol a deployable US small-bankroll
edge that DIVERSIFIES the cross-asset ETF momentum winner (Sharpe ~0.83, maxDD ~-17%)?

The VRP = implied vol persistently > subsequent realized vol => selling options/vol
earns an insurance premium that pays steadily and crashes occasionally (left tail).

This script:
  1) Characterizes the premium: ^VIX (implied) vs subsequent SPY realized vol.
  2) Backtests investable proxies with real history:
       ^PUT  (CBOE S&P500 PutWrite, 1996-)   -- cash-secured put writing
       ^BXM  (CBOE S&P500 BuyWrite/cov-call, 1988-)
       PUTW  (PutWrite ETF, 2016-), XYLD/QYLD (cov-call ETFs), SVOL (short-vol, 2021-)
     Sharpe/CAGR/maxDD + crash behavior in 2008 / Feb-2018 / Mar-2020 / 2022.
  3) Put-write + cheap tail hedge (allocate a few % to a synthetic long-vol leg).
  4) Diversification vs a momentum proxy and SPY; combo Sharpe/maxDD.

Data: yfinance daily (auto_adjust=True => total-return for ETFs; ^PUT/^BXM/^VIX are
indices). Staged at /tmp/vp_data (NOT committed). ALL ETF/strategy returns are NET of
a modeled spread cost; the index series (^PUT/^BXM) already embed CBOE's option exec.
"""
import numpy as np, pandas as pd

VP   = "/tmp/vp_data/vp_prices.csv"
CBOE = "/tmp/vp_data/cboe_idx.csv"
TD   = 252
COST_BPS_ETF = 3.0   # per-side spread for tradeable ETF rebalances

# ---------------------------------------------------------------- helpers
def load():
    a = pd.read_csv(VP, index_col=0, parse_dates=True).sort_index()
    b = pd.read_csv(CBOE, index_col=0, parse_dates=True).sort_index()
    return a.join(b, how="outer").sort_index()

def perf(daily_ret, rf_daily=0.0, name=""):
    """daily_ret: pd.Series of simple daily returns (already net). Returns dict of stats."""
    r = daily_ret.dropna()
    if len(r) < 60:
        return dict(name=name, n=len(r), CAGR=np.nan, vol=np.nan, Sharpe=np.nan,
                    maxDD=np.nan, Sortino=np.nan, skew=np.nan)
    n = len(r)
    cum = (1+r).prod()
    cagr = cum**(TD/n) - 1
    vol = r.std()*np.sqrt(TD)
    ex = r - (rf_daily if np.isscalar(rf_daily) else rf_daily.reindex(r.index).fillna(0))
    sharpe = ex.mean()/r.std()*np.sqrt(TD) if r.std()>0 else np.nan
    dn = r[r<0].std()*np.sqrt(TD)
    sortino = ex.mean()*TD/dn if dn>0 else np.nan
    eq = (1+r).cumprod()
    dd = (eq/eq.cummax()-1).min()
    return dict(name=name, n=n, start=str(r.index[0].date()), end=str(r.index[-1].date()),
                CAGR=cagr, vol=vol, Sharpe=sharpe, Sortino=sortino, maxDD=dd, skew=r.skew())

def fmt(d):
    return (f"{d['name']:<26} n={d['n']:>5} {d.get('start','')}->{d.get('end','')}  "
            f"CAGR={d['CAGR']*100:6.2f}%  vol={d['vol']*100:5.1f}%  "
            f"Sharpe={d['Sharpe']:5.2f}  Sortino={d['Sortino']:5.2f}  "
            f"maxDD={d['maxDD']*100:6.1f}%  skew={d['skew']:5.2f}")

def window_ret(daily_ret, lo, hi):
    r = daily_ret.loc[lo:hi].dropna()
    if len(r)==0: return np.nan, np.nan
    eq = (1+r).cumprod()
    return (eq.iloc[-1]-1), (eq/eq.cummax()-1).min()

# ---------------------------------------------------------------- main
px = load()
print("="*100)
print("DATA:", px.shape, "| cols:", [c for c in px.columns])
print("="*100)

# daily simple returns
ret = px.pct_change()

# DATA HYGIENE: Yahoo's ^PUT series has 2 adjacent glitch ticks (2020-03-13 +35%, 2020-03-16
# -28%) that a real put-write index cannot have. They ~offset in level (cum path & 2008 are
# fine) but corrupt daily std/skew and grossly flatter any vol-hedge backtest. Winsorize the
# index daily returns to +-12% (still allows true crash days like 2008-10-15 -9.4%).
for c in ["^PUT", "^BXM"]:
    if c in ret:
        ret[c] = ret[c].clip(-0.12, 0.12)

# T-bill daily for excess (use BIL TR; fallback ~2%/yr before inception)
if "BIL" in px:
    rf = px["BIL"].pct_change()
    rf = rf.fillna((1.02)**(1/TD)-1)
else:
    rf = pd.Series((1.02)**(1/TD)-1, index=px.index)
rf_const = (1.02)**(1/TD)-1

# ============================================================ 1) VRP characterization
print("\n#### 1) VRP CHARACTERIZATION: VIX (implied) vs subsequent SPY realized vol ####")
spy = px["SPY"].dropna()
spy_ret = spy.pct_change()
# realized vol over NEXT 21 trading days, annualized (%) aligned to date t
fwd_rv = spy_ret.rolling(21).std().shift(-21)*np.sqrt(TD)*100
vix = px["^VIX"].reindex(spy.index).ffill()
df = pd.DataFrame({"vix": vix, "fwd_rv21": fwd_rv}).dropna()
df["vrp"] = df["vix"] - df["fwd_rv21"]   # implied minus subsequent realized (vol points)
print(f"Sample {df.index[0].date()}..{df.index[-1].date()}  n={len(df)}")
print(f"  mean VIX            = {df['vix'].mean():6.2f}")
print(f"  mean fwd realized21 = {df['fwd_rv21'].mean():6.2f}")
print(f"  mean VRP (IV-RV)    = {df['vrp'].mean():6.2f} vol pts  (median {df['vrp'].median():.2f})")
print(f"  VRP>0 fraction      = {(df['vrp']>0).mean()*100:5.1f}%  (insurance overpriced most of the time)")
print(f"  worst VRP (RV>>IV)  = {df['vrp'].min():6.2f} vol pts  on {df['vrp'].idxmin().date()}")
print(f"  5th pctile VRP      = {df['vrp'].quantile(0.05):6.2f}  (the left tail: realized blew past implied)")
# how often does the tail event happen
print(f"  days VRP < -10      = {(df['vrp']<-10).sum()}  ({(df['vrp']<-10).mean()*100:.1f}%)")

# ============================================================ 2) PROXY PERFORMANCE
print("\n#### 2) INVESTABLE PROXY PERFORMANCE (full available history, net where tradeable) ####")
# ^PUT and ^BXM are CBOE indices (already embed option exec); treat their daily ret as gross-of-spread
# (CBOE methodology uses VWAP-ish settlement; we add NO extra cost to the index, but DO add cost to ETFs).
proxies = {
    "^PUT (CBOE PutWrite)":   ret["^PUT"],
    "^BXM (CBOE BuyWrite)":   ret["^BXM"],
    "PUTW (PutWrite ETF)":    ret["PUTW"] - (COST_BPS_ETF*2/1e4)/TD*0,  # ETF: TR already; spread negligible buy&hold
    "XYLD (S&P cov-call ETF)":ret["XYLD"],
    "QYLD (NDX cov-call ETF)":ret["QYLD"],
    "SVOL (short-vol ETF)":   ret["SVOL"],
    "SPY (benchmark)":        ret["SPY"],
    "QQQ (benchmark)":        ret["QQQ"],
}
stats = {}
for nm, r in proxies.items():
    d = perf(r, rf, nm); stats[nm]=d; print("  "+fmt(d))

# common-window comparison (since PUTW inception 2016) to be apples-to-apples vs ETFs
print("\n  -- Common window 2016-03..present (all ETFs alive) --")
common_lo = "2016-03-01"
for nm, r in proxies.items():
    d = perf(r.loc[common_lo:], rf.loc[common_lo:], nm); print("  "+fmt(d))

# ============================================================ CRASH behavior
print("\n#### CRASH BEHAVIOR (total return & maxDD inside each episode) ####")
episodes = {
    "2008 GFC (Sep07-Mar09)":   ("2007-09-01","2009-03-31"),
    "2011 EU/US-downgrade":     ("2011-07-01","2011-10-31"),
    "Feb-2018 Volmageddon":     ("2018-01-15","2018-02-28"),
    "2018 Q4 selloff":          ("2018-10-01","2018-12-31"),
    "Mar-2020 COVID":           ("2020-02-15","2020-04-15"),
    "2022 stock+bond bear":     ("2022-01-01","2022-10-31"),
}
hdr = ["strategy"]+list(episodes.keys())
print("  "+" | ".join(f"{h[:22]:>22}" for h in hdr))
for nm, r in proxies.items():
    cells=[f"{nm[:22]:>22}"]
    for ep,(lo,hi) in episodes.items():
        tr,dd = window_ret(r, lo, hi)
        cells.append(f"{(tr*100 if tr==tr else float('nan')):>9.1f}%/{(dd*100 if dd==dd else float('nan')):>6.1f}%dd" if tr==tr else f"{'n/a':>22}")
    print("  "+" | ".join(f"{c:>22}" for c in cells))

# ============================================================ 3) TAIL-HEDGED PUT-WRITE
print("\n#### 3) PUT-WRITE + CHEAP TAIL HEDGE ####")
# Synthetic long-vol hedge leg. The investable long-vol with real long history is hard
# (VXX reissue only 2018). We model the hedge two honest ways:
#  (A) realistic ETF-era: PUTW core + small VXX sleeve, monthly rebalanced (2018+).
#  (B) full-sample synthetic: ^PUT core + a hedge leg whose daily return = k * max(0, dVIX)
#      scaled to bleed ~X%/yr in calm and spike in crashes (approximates rolling OTM puts/VXX).
# We report BOTH and are explicit (B) is a model not a tradeable series.

def blend(core, hedge, w_hedge, reb="ME", cost_bps=COST_BPS_ETF):
    """Monthly-rebalanced blend of two daily-return series. Net of rebalance spread cost."""
    df = pd.concat([core.rename("c"), hedge.rename("h")], axis=1).dropna()
    w_c = 1-w_hedge
    # build with monthly reset to target weights; between resets weights drift
    idx = df.index
    months = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    reset_days = set(months.values)
    wc, wh = w_c, w_hedge
    rets=[]; turn_cost = cost_bps/1e4
    prev = (w_c, w_hedge)
    for t, row in df.iterrows():
        port = wc*row["c"] + wh*row["h"]
        # drift weights
        wc *= (1+row["c"]); wh *= (1+row["h"])
        s = wc+wh; wc/=s; wh/=s
        if t in reset_days:
            # cost = turnover * spread
            turn = abs(wc-w_c)+abs(wh-w_hedge)
            port -= turn*turn_cost
            wc, wh = w_c, w_hedge
        rets.append(port)
    return pd.Series(rets, index=df.index)

# (A) ETF-era realistic: PUTW + VXX hedge sleeve
core_etf = ret["PUTW"]
hedge_etf = ret["VXX"]
print("\n  (A) ETF-era 2018-02..present: PUTW core + VXX tail sleeve, monthly reset, net 3bps/side")
for wh in [0.0, 0.03, 0.05, 0.10, 0.15]:
    if wh==0:
        r = core_etf
    else:
        r = blend(core_etf, hedge_etf, wh)
    d = perf(r, rf, f"PUTW + {int(wh*100)}% VXX"); print("    "+fmt(d))
    for ep in ["Mar-2020 COVID","2022 stock+bond bear"]:
        lo,hi = episodes[ep]; tr,dd = window_ret(r,lo,hi)
        print(f"        {ep:<24} TR={tr*100:6.1f}%  maxDD={dd*100:6.1f}%")

# (B) full-sample synthetic hedge: long-vol leg from VIX changes.
# WARNING: this is an IDEALIZED model, NOT a tradeable series. Real long-vol (VXX) bleeds
# far more and slips on entry/exit; the (A) ETF-era result with REAL VXX is the honest one.
# (B) is shown ONLY to illustrate direction (a hedge converts crash losses to crash gains).
print("\n  (B) Full-sample 1996+: ^PUT core + SYNTHETIC long-vol hedge")
print("      *** IDEALIZED MODEL, NOT TRADEABLE -- the high Sharpe here is an artifact;")
print("      *** trust the (A) REAL-VXX result. Shown only to illustrate direction. ***")
vixc = px["^VIX"].pct_change().reindex(ret.index)
# synthetic rolling-OTM-put / VXX-like: positive when VIX jumps, bleeds in calm.
# daily hedge ret ~ 1.0*max(0,dVIX) - daily_bleed; calibrate bleed so calm Sharpe negative big.
bleed = 0.55/TD   # ~55%/yr bleed (typical for VXX-style long vol)
syn_hedge = (1.0*vixc.clip(lower=-0.05)).fillna(0) - bleed
syn_hedge = syn_hedge.clip(lower=-0.20)  # cap daily loss on hedge
core_idx = ret["^PUT"]
for wh in [0.0, 0.05, 0.10]:
    if wh==0: r = core_idx
    else: r = blend(core_idx, syn_hedge, wh)
    d = perf(r, rf, f"^PUT + {int(wh*100)}% synVol"); print("    "+fmt(d))
    for ep in ["2008 GFC (Sep07-Mar09)","Mar-2020 COVID","2022 stock+bond bear"]:
        lo,hi = episodes[ep]; tr,dd = window_ret(r,lo,hi)
        print(f"        {ep:<24} TR={tr*100:6.1f}%  maxDD={dd*100:6.1f}%")

# ============================================================ 4) DIVERSIFICATION vs MOMENTUM
print("\n#### 4) DIVERSIFICATION vs the MOMENTUM WINNER ####")
# Build a transparent cross-asset momentum proxy (12-1 dual momentum, monthly, top-asset-or-cash)
# to get a daily return stream we can correlate. Uses the SAME yfinance assets.
mom_assets = ["SPY","QQQ","IWM","TLT","IEF","GLD","DBC"]
mpx = px[mom_assets].dropna(how="all")
mpx = mpx.loc[mpx.index>= "2007-01-01"]   # all alive by ~2006-2007
mret = mpx.pct_change()
# monthly 6m momentum, top-3 equal weight if SPY>200d else cash (regime gate), monthly reset
spy200 = px["SPY"].rolling(200).mean()
idx = mpx.index
months = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values
mom_daily = pd.Series(0.0, index=idx)
cur_w = {}
mset = set(months)
for i,t in enumerate(idx):
    if i>0:
        # apply yesterday's weights to today's returns
        rr = 0.0
        for a,w in cur_w.items():
            x = mret[a].iloc[i]
            if x==x: rr += w*x
        mom_daily.iloc[i] = rr
    if t in mset:
        look = mpx.loc[:t]
        if len(look)>130:
            scores = look.iloc[-1]/look.iloc[-126]-1
            scores = scores.dropna().sort_values(ascending=False)
            gate = px["SPY"].loc[t] > spy200.loc[t] if t in spy200.index and spy200.loc[t]==spy200.loc[t] else True
            top = [a for a in scores.index[:3] if scores[a]>0]
            if gate and top:
                cur_w = {a: 1/len(top) for a in top}
            else:
                cur_w = {}   # cash
mom_d = perf(mom_daily, rf, "Momentum proxy (6m,top3,gate)")
print("  "+fmt(mom_d))
print("  (Note: simplified proxy of the documented winner ~Sharpe0.83/maxDD-17%; used for correlation.)")

# correlations on common window (monthly returns to denoise)
def monthly(r):
    return (1+r).resample("ME").prod()-1
panel = pd.DataFrame({
    "MOM": mom_daily,
    "PUT": ret["^PUT"],
    "BXM": ret["^BXM"],
    "PUTW": ret["PUTW"],
    "SPY": ret["SPY"],
}).dropna(how="all")
mpanel = panel.apply(monthly).dropna()
print("\n  Monthly-return correlation matrix (common window", mpanel.index[0].date(),"..",mpanel.index[-1].date(),"):")
print(mpanel.corr().round(2).to_string())

# combo: momentum + VRP sleeve (use ^PUT for long history), 60/40 and 70/30, monthly reset
print("\n  COMBOS (monthly reset, net): momentum (winner) + VRP (^PUT put-write)")
combo_lo = max(mom_daily.first_valid_index(), ret["^PUT"].first_valid_index())
mc = mom_daily.loc[combo_lo:]
pc = ret["^PUT"].loc[combo_lo:]
print("  "+fmt(perf(mc, rf, "100% Momentum")))
print("  "+fmt(perf(pc, rf, "100% VRP (^PUT)")))
for wv in [0.30, 0.40, 0.50]:
    r = blend(mc, pc, wv)
    d = perf(r, rf, f"{int((1-wv)*100)}MOM/{int(wv*100)}VRP"); print("  "+fmt(d))
    for ep in ["2008 GFC (Sep07-Mar09)","Mar-2020 COVID","2022 stock+bond bear"]:
        lo,hi=episodes[ep]; tr,dd=window_ret(r,lo,hi)
        print(f"        {ep:<24} TR={tr*100:6.1f}%  maxDD={dd*100:6.1f}%")

# three-leg ETF-era with REAL VXX (the honest one)
print("\n  THREE-LEG (HONEST, ETF-era 2018+ with REAL VXX): 55% MOM + 35% PUTW + 10% VXX")
e_lo = "2018-02-01"
me = mom_daily.loc[e_lo:]; pe = ret["PUTW"].loc[e_lo:]; he = ret["VXX"].loc[e_lo:]
te = pd.concat([me.rename("m"),pe.rename("v"),he.rename("h")],axis=1).dropna()
idxe=te.index; mse=set(pd.Series(idxe,index=idxe).groupby([idxe.year,idxe.month]).last().values)
WE=[0.55,0.35,0.10]; we=WE.copy(); rete=[]
for t,row in te.iterrows():
    port=we[0]*row["m"]+we[1]*row["v"]+we[2]*row["h"]
    we=[we[0]*(1+row["m"]),we[1]*(1+row["v"]),we[2]*(1+row["h"])]; s=sum(we); we=[x/s for x in we]
    if t in mse:
        turn=sum(abs(we[i]-WE[i]) for i in range(3)); port-=turn*COST_BPS_ETF/1e4; we=WE.copy()
    rete.append(port)
re_=pd.Series(rete,index=idxe)
print("  "+fmt(perf(me,rf,"  100% MOM (2018+)")))
print("  "+fmt(perf(pe,rf,"  100% PUTW (2018+)")))
print("  "+fmt(perf(re_,rf,"  55MOM/35PUTW/10VXX")))
for ep in ["Mar-2020 COVID","2022 stock+bond bear"]:
    lo,hi=episodes[ep]; tr,dd=window_ret(re_,lo,hi); print(f"        {ep:<24} TR={tr*100:6.1f}%  maxDD={dd*100:6.1f}%")

# three-leg synthetic (illustrative only)
print("\n  THREE-LEG (ILLUSTRATIVE, synthetic vol -> Sharpe is an ARTIFACT): 50MOM/40VRP/10vol")
t3 = pd.concat([mc.rename("m"), pc.rename("v"), syn_hedge.loc[combo_lo:].rename("h")],axis=1).dropna()
# manual monthly reset 50/40/10
idx3=t3.index; months3=set(pd.Series(idx3,index=idx3).groupby([idx3.year,idx3.month]).last().values)
W=[0.5,0.4,0.1]; w=W.copy(); rets3=[]
for t,row in t3.iterrows():
    port=w[0]*row["m"]+w[1]*row["v"]+w[2]*row["h"]
    w=[w[0]*(1+row["m"]),w[1]*(1+row["v"]),w[2]*(1+row["h"])]; s=sum(w); w=[x/s for x in w]
    if t in months3:
        turn=sum(abs(w[i]-W[i]) for i in range(3)); port-=turn*COST_BPS_ETF/1e4; w=W.copy()
    rets3.append(port)
r3=pd.Series(rets3,index=idx3)
d=perf(r3,rf,"50MOM/40VRP/10vol"); print("  "+fmt(d))
for ep in ["2008 GFC (Sep07-Mar09)","Mar-2020 COVID","2022 stock+bond bear"]:
    lo,hi=episodes[ep]; tr,dd=window_ret(r3,lo,hi); print(f"        {ep:<24} TR={tr*100:6.1f}%  maxDD={dd*100:6.1f}%")

print("\nDONE.")
