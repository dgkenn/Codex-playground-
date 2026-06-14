#!/usr/bin/env python3
"""Driver: trend-following sleeve standalone, crisis alpha, correlation to the XS-momentum
winner, combined-portfolio Sharpe/maxDD vs the winner alone, robustness. Prints all tables."""
import numpy as np, pandas as pd
from trend_following import (load_long, load_inv, backtest_tf, stats, combine,
                             TF_UNIVERSE, INVERSE_MAP)
from etf_momentum import backtest as xs_backtest, CORE_UNIVERSE

pd.set_option("display.width",200,"display.max_columns",40)
lp, ip = load_long(), load_inv()

def section(t): print("\n"+"="*92+"\n"+t+"\n"+"="*92)
def winner(start=None,end=None):
    net,to = xs_backtest(lp, CORE_UNIVERSE, lookback_days=126, K=5, risk_adj=True,
                         dual=True, regime=True, partial=0.34, start=start, end=end)
    return net

# TF start: universe broadly present from 2007-06 (UUP/inverse binders). 2008 GFC covered.
TF_START = "2007-06-01"
HOLD_START = "2016-01-01"

# --------------------------------------------------------------------------
section("1. TF SLEEVE STANDALONE -- plateau across lookback x vol-target (cash-when-down). 2007-2026")
rows=[]
for vt in [0.07,0.10,0.15]:
    for lbn,lb in [("3m",63),("6m",126),("12m",252)]:
        net,to=backtest_tf(lp,ip,lookback_days=lb,mode="trend",down="cash",vol_target=vt,start=TF_START)
        s=stats(net); rows.append(dict(cfg=f"vt{vt} {lbn}",CAGR=s["CAGR"],Sharpe=s["Sharpe"],
                                       maxDD=s["maxDD"],vol=s["vol"],turn=to))
# price>10m-MA variant
for vt in [0.10]:
    net,to=backtest_tf(lp,ip,lookback_days=210,mode="ma",down="cash",vol_target=vt,start=TF_START)
    s=stats(net); rows.append(dict(cfg=f"vt{vt} 10mMA",CAGR=s["CAGR"],Sharpe=s["Sharpe"],
                                   maxDD=s["maxDD"],vol=s["vol"],turn=to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

section("2. CASH vs INVERSE-ETF vs SYNTHETIC short when trend down (6m, vt=0.10). 2007-2026")
rows=[]
for down in ["cash","inverse","synth"]:
    net,to=backtest_tf(lp,ip,lookback_days=126,mode="trend",down=down,vol_target=0.10,start=TF_START)
    s=stats(net); rows.append(dict(down=down,CAGR=s["CAGR"],Sharpe=s["Sharpe"],maxDD=s["maxDD"],
                                   vol=s["vol"],turn=to))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("inverse-ETF/synth drag vs cash = the cost of shorting via US-legal instruments.")

# choose headline TF config
TF_NET,_ = backtest_tf(lp,ip,lookback_days=126,mode="trend",down="cash",vol_target=0.10,start=TF_START)
TF_INV,_ = backtest_tf(lp,ip,lookback_days=126,mode="trend",down="inverse",vol_target=0.10,start=TF_START)

# --------------------------------------------------------------------------
section("3. CRISIS ALPHA -- TF (cash & inverse) vs SPY & the XS winner in equity crashes")
spy = lp["SPY"].pct_change()
WIN = winner(start=TF_START)
crises = {
    "2008 GFC (Sep08-Mar09)": ("2008-09-01","2009-03-31"),
    "2008 full year":         ("2008-01-01","2008-12-31"),
    "2020 COVID (Feb-Mar20)": ("2020-02-19","2020-03-23"),
    "2022 stocks+bonds":      ("2022-01-01","2022-12-31"),
}
def cum(r,a,b):
    x=r[(r.index>=pd.Timestamp(a))&(r.index<=pd.Timestamp(b))]
    return (1+x).prod()-1 if len(x)>0 else np.nan
rows=[]
for name,(a,b) in crises.items():
    rows.append(dict(crisis=name, SPY=cum(spy,a,b), XS_winner=cum(WIN,a,b),
                     TF_cash=cum(TF_NET,a,b), TF_inverse=cum(TF_INV,a,b)))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("Crisis alpha = TF positive while SPY deeply negative.")

# --------------------------------------------------------------------------
section("4. CORRELATION of TF to the XS winner and to SPY (monthly returns, overlap)")
def monthly(r): return (1+r).resample("ME").prod()-1
mwin, mtf, mtfi, mspy = monthly(WIN), monthly(TF_NET), monthly(TF_INV), monthly(spy)
corr_df = pd.concat([mwin.rename("XS_winner"),mtf.rename("TF_cash"),
                     mtfi.rename("TF_inv"),mspy.rename("SPY")],axis=1).dropna()
print(corr_df.corr().round(2).to_string())

# --------------------------------------------------------------------------
section("5. COMBINED PORTFOLIO vs XS-WINNER ALONE (overlap window 2007-2026)")
# align winner & TF over common window
def show_combo(tf_stream, label):
    rows=[]
    s=stats(WIN.loc[tf_stream.index.min():]); rows.append(dict(book="XS winner ALONE",**_st(s)))
    s=stats(tf_stream); rows.append(dict(book=f"TF {label} ALONE",**_st(s)))
    for wa,wb,nm in [(0.5,0.5,"50/50"),(0.7,0.3,"70/30 XS/TF"),(0.3,0.7,"30/70 XS/TF")]:
        c=combine(WIN, tf_stream, wa, wb)
        rows.append(dict(book=f"COMBO {nm}",**_st(stats(c))))
    # risk-parity (inverse-vol) weights
    vw=WIN.loc[tf_stream.index.min():].std(); vt=tf_stream.std()
    wa=(1/vw)/((1/vw)+(1/vt)); wb=1-wa
    c=combine(WIN, tf_stream, wa, wb)
    rows.append(dict(book=f"COMBO risk-parity ({wa:.2f}/{wb:.2f})",**_st(stats(c))))
    print(f"\n--- TF leg = {label} ---")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
def _st(s): return dict(CAGR=s["CAGR"],Sharpe=s["Sharpe"],maxDD=s["maxDD"],vol=s["vol"])
show_combo(TF_NET, "cash-when-down")
show_combo(TF_INV, "inverse-when-down")

# --------------------------------------------------------------------------
section("6. ROBUSTNESS -- recent-decade holdout 2016-2026 (combo vs winner alone)")
WIN_H = winner(start=HOLD_START)
TF_H,_ = backtest_tf(lp,ip,lookback_days=126,mode="trend",down="cash",vol_target=0.10,start=HOLD_START)
rows=[]
rows.append(dict(book="XS winner alone",**_st(stats(WIN_H))))
rows.append(dict(book="TF cash alone",**_st(stats(TF_H))))
for wa,wb,nm in [(0.5,0.5,"50/50"),(0.7,0.3,"70/30")]:
    rows.append(dict(book=f"COMBO {nm}",**_st(stats(combine(WIN_H,TF_H,wa,wb)))))
print(pd.DataFrame(rows).round(3).to_string(index=False))

section("7. COST sensitivity of TF sleeve (bps/side). 6m cash vt0.10 full")
rows=[]
for c in [0,3,10,25]:
    net,to=backtest_tf(lp,ip,lookback_days=126,mode="trend",down="cash",vol_target=0.10,cost_bps=c,start=TF_START)
    s=stats(net); rows.append(dict(cost_bps=c,Sharpe=s["Sharpe"],CAGR=s["CAGR"],maxDD=s["maxDD"]))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# annual returns of TF vs SPY (whipsaw years)
section("8. By-year returns: TF cash vs SPY vs XS winner (whipsaw honesty)")
yr=lambda r:(1+r).resample("YE").prod()-1
ydf=pd.concat([yr(spy).rename("SPY"),yr(WIN).rename("XS_winner"),yr(TF_NET).rename("TF_cash")],axis=1)
ydf.index=ydf.index.year
print(ydf.round(3).to_string())
