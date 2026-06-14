"""Run full study, print result blocks, and assemble CRYPTO_STATARB.md."""
import os, glob, json, itertools
import numpy as np, pandas as pd
from analysis import (load, load_panel, perf_stats, hedge_ratio_ols, zscore,
                      backtest_pair, backtest_ts_reversion, backtest_residual,
                      latency_decay, is_oos_split, COST_PER_SIDE, TAKER_FEE, SLIPPAGE,
                      BARS_PER_YEAR)
from statsmodels.tsa.stattools import adfuller, coint
import statsmodels.api as sm

pd.set_option("display.width", 160)
np.random.seed(0)

REPORT = []
def log(*a):
    s=" ".join(str(x) for x in a); print(s); REPORT.append(s)

# ---------------- data inventory ----------------
log("="*70); log("DATA INVENTORY")
inv={}
for bar in ["1H","15m","1D"]:
    px = load_panel(bar)
    if px.empty: continue
    inv[bar]=px
    log(f"  {bar}: {px.shape[1]} symbols, {px.shape[0]} bars, "
        f"{px.index.min()} -> {px.index.max()}")
    log(f"       symbols: {list(px.columns)}")

px1h = inv.get("1H"); px15 = inv.get("15m"); pxd = inv.get("1D")

def split_is_oos(net, frac=0.6):
    net=net.dropna()
    if len(net)<50: return None,None
    k=int(len(net)*frac)
    return net.iloc[:k], net.iloc[k:]

# =====================================================================
log("\n"+"="*70); log("STEP 1: COINTEGRATION SCREEN (1H log prices, Engle-Granger)")
coint_rows=[]
syms = list(px1h.columns)
for a,b in itertools.combinations(syms,2):
    s=pd.DataFrame({"a":px1h[a],"b":px1h[b]}).dropna()
    if len(s)<1000: continue
    la,lb=np.log(s.a),np.log(s.b)
    try:
        t,pval,_=coint(la,lb)
    except Exception:
        continue
    # also ADF on OLS residual (full-sample hedge for screening only)
    X=sm.add_constant(lb); beta=sm.OLS(la,X).fit().params.iloc[1]
    resid=la-beta*lb
    adf_p=adfuller(resid, maxlag=24, autolag=None)[1]
    coint_rows.append((f"{a}/{b}", beta, t, pval, adf_p))
cdf=pd.DataFrame(coint_rows, columns=["pair","beta","eg_t","eg_p","adf_resid_p"]).sort_values("eg_p")
log(cdf.to_string(index=False, float_format=lambda x:f"{x:.4f}"))
COINT_TABLE = cdf

# =====================================================================
log("\n"+"="*70); log("STEP 2: PAIRS STAT-ARB BACKTEST (slow taker, next-bar, both legs costed)")
log(f"Costs: taker {TAKER_FEE*1e4:.0f}bps + slip {SLIPPAGE*1e4:.0f}bps = {COST_PER_SIDE*1e4:.0f}bps/side/leg")
pair_results=[]
# focus on the obvious + top cointegrated
candidate_pairs = ["BTC_USDT/ETH_USDT","ETH_USDT/SOL_USDT","BTC_USDT/SOL_USDT"]
# add top-3 by eg_p
for p in cdf.head(4)["pair"].tolist():
    if p not in candidate_pairs: candidate_pairs.append(p)

best_pair=None
for pair in candidate_pairs:
    a,b=pair.split("/")
    if a not in px1h or b not in px1h: continue
    # grid search small param set, evaluate on IS only, report OOS for best
    grid = itertools.product([300,500],[120,200],[1.5,2.0,2.5])
    rows=[]
    for wh,wz,zin in grid:
        net,pos,z,beta,nt = backtest_pair(px1h[a],px1h[b],"1H",win_hedge=wh,win_z=wz,z_in=zin,z_out=0.5)
        is_,oos = split_is_oos(net)
        if is_ is None: continue
        si=perf_stats(is_,"1H"); so=perf_stats(oos,"1H")
        rows.append((wh,wz,zin,nt,si["sharpe"],si["ann_ret"],so["sharpe"],so["ann_ret"],so["maxdd"]))
    if not rows: continue
    rdf=pd.DataFrame(rows,columns=["wh","wz","zin","trades","IS_Sh","IS_ann","OOS_Sh","OOS_ann","OOS_dd"])
    rdf=rdf.sort_values("IS_Sh",ascending=False)  # pick by IS, honest OOS
    log(f"\n-- {pair} (params picked by IS Sharpe) --")
    log(rdf.head(4).to_string(index=False,float_format=lambda x:f"{x:.3f}"))
    top=rdf.iloc[0]
    pair_results.append((pair,top))
    if best_pair is None or top["OOS_Sh"]>best_pair[1]["OOS_Sh"]:
        best_pair=(pair,top)

# =====================================================================
log("\n"+"="*70); log("STEP 3: TIME-SERIES MEAN-REVERSION (single asset, 1H and 15m)")
ts_rows=[]
for bar,panel in [("1H",px1h),("15m",px15)]:
    if panel is None: continue
    for s in ["BTC_USDT","ETH_USDT","SOL_USDT"]:
        if s not in panel: continue
        # grid on IS
        best=None
        for lb in ([12,24,48] if bar=="1H" else [24,48,96]):
            for zin in [1.5,2.0,2.5]:
                net,nt=backtest_ts_reversion(panel[s],bar,lookback=lb,z_in=zin,z_out=0.5,
                                              hold_cap=(12 if bar=="1H" else 24))
                is_,oos=split_is_oos(net)
                if is_ is None: continue
                si=perf_stats(is_,bar)
                if best is None or si["sharpe"]>best[0]:
                    best=(si["sharpe"],lb,zin,net,nt)
        if best is None: continue
        _,lb,zin,net,nt=best
        is_,oos=split_is_oos(net)
        si=perf_stats(is_,bar); so=perf_stats(oos,bar)
        # gross (no cost) OOS for comparison
        ts_rows.append((bar,s,lb,zin,nt,si["sharpe"],so["sharpe"],so["ann_ret"],so["maxdd"]))
tdf=pd.DataFrame(ts_rows,columns=["bar","sym","lookbk","zin","trades","IS_Sh","OOS_Sh","OOS_ann","OOS_dd"])
log(tdf.to_string(index=False,float_format=lambda x:f"{x:.3f}"))
TS_TABLE=tdf

# =====================================================================
log("\n"+"="*70); log("STEP 4: RESIDUAL / CROSS-SECTIONAL REVERSION (alt on BTC, market-neutral)")
res_rows=[]
for s in ["ETH_USDT","SOL_USDT","BNB_USDT","XRP_USDT","DOGE_USDT","ADA_USDT","AVAX_USDT","LINK_USDT","LTC_USDT"]:
    if s not in px1h: continue
    best=None
    for wz in [80,120,200]:
        for zin in [1.5,2.0,2.5]:
            net,nt=backtest_residual(px1h[s],px1h["BTC_USDT"],"1H",win_hedge=500,win_z=wz,z_in=zin,z_out=0.5)
            is_,oos=split_is_oos(net)
            if is_ is None: continue
            si=perf_stats(is_,"1H")
            if best is None or si["sharpe"]>best[0]:
                best=(si["sharpe"],wz,zin,net,nt)
    if best is None: continue
    _,wz,zin,net,nt=best
    is_,oos=split_is_oos(net)
    si=perf_stats(is_,"1H"); so=perf_stats(oos,"1H")
    res_rows.append((s,wz,zin,nt,si["sharpe"],so["sharpe"],so["ann_ret"],so["maxdd"]))
rdf2=pd.DataFrame(res_rows,columns=["alt","win_z","zin","trades","IS_Sh","OOS_Sh","OOS_ann","OOS_dd"])
log(rdf2.to_string(index=False,float_format=lambda x:f"{x:.3f}"))
RES_TABLE=rdf2

# =====================================================================
log("\n"+"="*70); log("STEP 5: LATENCY HONESTY CHECK — return autocorrelation by horizon")
log("Lag-1 autocorr of returns at aggregation N bars. Negative=reversion.")
lat_rows=[]
for bar,panel in [("15m",px15),("1H",px1h)]:
    if panel is None: continue
    for s in ["BTC_USDT","ETH_USDT","SOL_USDT"]:
        if s not in panel: continue
        d=latency_decay(panel[s],bar)
        lat_rows.append((bar,s,d))
        log(f"  {bar} {s}: "+", ".join(f"{k}bar={v:+.4f}" for k,v in d.items()))
LAT_ROWS=lat_rows

# also: pair spread reversion half-life (best pair)
if best_pair:
    pair=best_pair[0]; a,b=pair.split("/")
    net,pos,z,beta,nt=backtest_pair(px1h[a],px1h[b],"1H",win_hedge=int(best_pair[1]["wh"]),
                                    win_z=int(best_pair[1]["wz"]),z_in=best_pair[1]["zin"],z_out=0.5)
    sp=(np.log(px1h[a])-beta*np.log(px1h[b])).dropna()
    dsp=sp.diff().dropna(); lsp=sp.shift(1).reindex(dsp.index)
    X=sm.add_constant(lsp.values); ols=sm.OLS(dsp.values,X).fit()
    lam=ols.params[1]; hl=-np.log(2)/lam if lam<0 else np.inf
    log(f"\n  Best pair {pair} spread half-life ~ {hl:.1f} hours (OU lambda={lam:.4f})")
    HALFLIFE=hl
else:
    HALFLIFE=np.nan

# =====================================================================
log("\n"+"="*70); log("STEP 5b: CAPACITY (best pair) — ADV-based")
# capacity: limit to small % of dollar volume per leg per trade
cap_note=""
if best_pair:
    pair=best_pair[0]; a,b=pair.split("/")
    for s in [a,b]:
        d=load(s,"1H")
        adv = (d["volCcyQuote"]).rolling(24).sum().median()  # ~daily $ volume
        cap_note += f"{s} median daily $vol ~ ${adv/1e6:.0f}M; "
    log("  "+cap_note)

# stash for report builder
import pickle
pickle.dump(dict(coint=COINT_TABLE, pair_results=pair_results, best_pair=best_pair,
                 ts=TS_TABLE, res=RES_TABLE, lat=LAT_ROWS, halflife=HALFLIFE,
                 report="\n".join(REPORT), cap=cap_note,
                 windows={k:(v.index.min(),v.index.max(),v.shape) for k,v in inv.items()}),
            open("/tmp/cx_statarb/_results.pkl","wb"))
log("\nDONE")
