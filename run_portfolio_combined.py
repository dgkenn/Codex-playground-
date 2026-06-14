#!/usr/bin/env python3
"""Driver for the combined-portfolio study. Prints all tables for PORTFOLIO_COMBINED.md."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from portfolio_combined import (sleeve_A, sleeve_B, combine_n, inv_vol_weights,
                                vol_target_combo, block_bootstrap, stats)
from etf_momentum import load_prices, buyhold

pd.set_option("display.width", 200, "display.max_columns", 40)
def sec(t): print("\n"+"="*94+"\n"+t+"\n"+"="*94)
def st(s): return dict(CAGR=round(s["CAGR"],4), Sharpe=round(s["Sharpe"],3), maxDD=round(s["maxDD"],4), vol=round(s["vol"],4))

OVERLAP, HOLDOUT = "2007-06-01", "2016-01-01"
px = load_prices()

# ---- build sleeves on the two windows --------------------------------------
A_full = sleeve_A(start=OVERLAP)
B_inv_full = sleeve_B(start=OVERLAP, down="inverse")
B_cash_full = sleeve_B(start=OVERLAP, down="cash")
A_h = sleeve_A(start=HOLDOUT)
B_inv_h = sleeve_B(start=HOLDOUT, down="inverse")

sec("0. SLEEVE REPRODUCTION (verify committed stats)")
for lbl,n in [("A full", A_full),("A holdout", A_h),("B inverse full", B_inv_full),
              ("B cash full", B_cash_full),("B inverse holdout", B_inv_h)]:
    print(f"  {lbl:20} {st(stats(n))}")

# ---- helper: align A&B to common idx for combine ---------------------------
def sweep(A, B, label):
    rows = []
    sA = stats(A.loc[B.index.min():]); rows.append(dict(book="A alone (100/0)", **st(sA)))
    sB = stats(B); rows.append(dict(book="B alone (0/100)", **st(sB)))
    for wa,wb,nm in [(0.85,0.15,"85/15"),(0.70,0.30,"70/30"),(0.60,0.40,"60/40"),(0.50,0.50,"50/50")]:
        c = combine_n([A,B],[wa,wb]); rows.append(dict(book=f"combo {nm}", **st(stats(c))))
    # risk-parity / inverse-vol
    al = A.loc[B.index.min():]; ivw = inv_vol_weights([al,B])
    c = combine_n([al,B], ivw); rows.append(dict(book=f"risk-parity ({ivw[0]:.2f}/{ivw[1]:.2f})", **st(stats(c))))
    # vol-targeted 70/30 to 10%
    cvt = vol_target_combo([al,B],[0.70,0.30], target_vol=0.10)
    rows.append(dict(book="70/30 vol-tgt 10%", **st(stats(cvt))))
    print(f"\n--- {label} ---")
    print(pd.DataFrame(rows).to_string(index=False))

sec("1. COMBINATION SWEEP — A=XS-momentum, B=TF-INVERSE (the diversifier). FULL OVERLAP 2007-2026")
sweep(A_full, B_inv_full, "FULL 2007-2026 (B = inverse)")
sec("1b. SAME SWEEP on RECENT-DECADE OOS HOLDOUT 2016-2026")
sweep(A_h, B_inv_h, "HOLDOUT 2016-2026 (B = inverse)")
sec("1c. CONTRAST: B = TF-CASH (correlated, no crisis alpha) full 2007-2026")
sweep(A_full, B_cash_full, "FULL 2007-2026 (B = cash)")

# ---- robustness: plateau across weights on a fine grid ---------------------
sec("2. WEIGHT PLATEAU (fine grid, B=inverse). Sharpe & maxDD across wA in [1.0..0.4]")
rows=[]
al = A_full.loc[B_inv_full.index.min():]
for wa in [1.0,0.90,0.85,0.80,0.75,0.70,0.65,0.60,0.55,0.50,0.45,0.40]:
    c = combine_n([al,B_inv_full],[wa,1-wa]); s=stats(c)
    ch = combine_n([A_h,B_inv_h],[wa,1-wa]); sh=stats(ch)
    rows.append(dict(wA=wa, full_Sharpe=round(s["Sharpe"],3), full_maxDD=round(s["maxDD"],4),
                     hold_Sharpe=round(sh["Sharpe"],3), hold_maxDD=round(sh["maxDD"],4)))
print(pd.DataFrame(rows).to_string(index=False))

# ---- SATELLITE TESTS -------------------------------------------------------
sec("3. SATELLITE A: PUTW vol-premium slice — does it earn a place in the 2-sleeve combo?")
vp = pd.read_csv("/tmp/vp_data/vp_prices.csv", index_col=0, parse_dates=True).sort_index()
putw = vp["PUTW"].pct_change().dropna()
# ^PUT long-history index for the full window (CBOE)
try:
    ci = pd.read_csv("/tmp/vp_data/cboe_idx.csv", index_col=0, parse_dates=True).sort_index()
    put_idx = ci["^PUT"].pct_change().clip(-0.12,0.12).dropna()
except Exception:
    put_idx = None

# base 70/30 combo
base = combine_n([al,B_inv_full],[0.70,0.30])
print("base 70/30 (A/B), full 2007-2026:", st(stats(base)))
# add PUTW (ETF era 2016+) at small slices, carving from sleeve A's equity share
sec_lo = "2016-03-01"
A_etf = A_full.loc[sec_lo:]; B_etf = B_inv_full.loc[sec_lo:]; P_etf = putw.loc[sec_lo:]
rows=[]
b0 = combine_n([A_etf,B_etf],[0.70,0.30]); rows.append(dict(book="70/30 no satellite (2016+)",**st(stats(b0))))
for pw in [0.10,0.20,0.30]:
    # carve PUTW from A's share (A=0.70 -> 0.70-pw*0.70?), keep B=0.30 fixed; PUTW takes pw of equity from A
    wa = 0.70-pw; wb=0.30
    c = combine_n([A_etf,B_etf,P_etf],[wa,wb,pw]); rows.append(dict(book=f"A{wa:.2f}/B{wb:.2f}/PUTW{pw:.2f}",**st(stats(c))))
print(pd.DataFrame(rows).to_string(index=False))
if put_idx is not None:
    print("\n  full-history (^PUT proxy) check 2007+:")
    A_o=A_full; B_o=B_inv_full; P_o=put_idx.loc[OVERLAP:]
    rows=[]
    rows.append(dict(book="70/30 no satellite",**st(stats(combine_n([A_o.loc[B_o.index.min():],B_o],[0.70,0.30])))))
    for pw in [0.10,0.20]:
        c=combine_n([A_o.loc[B_o.index.min():],B_o,P_o],[0.70-pw,0.30,pw]); rows.append(dict(book=f"A{0.70-pw:.2f}/B0.30/PUT{pw:.2f}",**st(stats(c))))
    print(pd.DataFrame(rows).to_string(index=False))

sec("4. SATELLITE B: high-octane STOCK momentum (survivorship-haircut). Earns place?")
# stock momentum requires /tmp/sm_data; if absent, skip with note (survivorship-biased upper bound)
import os
if os.path.exists("/tmp/sm_data/stock_prices.csv"):
    from stock_momentum import load_prices as load_sm, backtest as sm_bt, stats as sm_stats
    smpx = load_sm()
    sm_net,_ = sm_bt(smpx, list(smpx.columns), lookback_days=126, K=15, dual=True, regime=True, partial=0.34, start=HOLDOUT)
    # haircut: shift annual drift down 30% (survivorship) — apply same mean-haircut as bootstrap
    sm_hc = sm_net - 0.30*sm_net.mean()
    print("stock-mom (survivorship raw):", st(stats(sm_net)))
    print("stock-mom (30% drift haircut):", st(stats(sm_hc)))
    A_s=A_h.loc[sm_hc.index.min():]; B_s=B_inv_h.loc[sm_hc.index.min():]
    rows=[dict(book="70/30 no satellite (2016+)",**st(stats(combine_n([A_s,B_s],[0.70,0.30]))))]
    for sw in [0.10,0.20]:
        c=combine_n([A_s,B_s,sm_hc],[0.70-sw,0.30,sw]); rows.append(dict(book=f"A{0.70-sw:.2f}/B0.30/STK{sw:.2f}(hc)",**st(stats(c))))
    print(pd.DataFrame(rows).to_string(index=False))
else:
    print("  /tmp/sm_data not staged — STOCK_MOMENTUM.md already documents survivorship-biased")
    print("  -28% DD upper bound. Tested conceptually: it ADDS drawdown & complexity; excluded.")

# ---- COMBINED OUTCOME DISTRIBUTION -----------------------------------------
sec("5. COMBINED OUTCOME DISTRIBUTION (block-bootstrap, 30% drift haircut). 70/30 combo vs A-alone")
combo7030 = combine_n([al, B_inv_full],[0.70,0.30])
A_only = A_full.loc[B_inv_full.index.min():]
spy = buyhold(px,"SPY",start=OVERLAP)
def dist_report(net, label, spy_ref=None):
    print(f"\n--- {label} (full daily stats {st(stats(net))}) ---")
    for yrs in [1,2,3]:
        tw,mdd,under = block_bootstrap(net, n_paths=5000, horizon_days=252*yrs, block=21, haircut=0.30)
        p5,p50,p95 = np.percentile(tw,[5,50,95])
        print(f"  {yrs}yr: $1k -> p5 ${1000*p5:7.0f}  median ${1000*p50:7.0f}  p95 ${1000*p95:7.0f} | "
              f"$10k -> p5 ${10000*p5:8.0f} median ${10000*p50:8.0f} p95 ${10000*p95:8.0f}")
        print(f"        P(maxDD>20%)={np.mean(mdd<-0.20)*100:4.1f}%  P(maxDD>30%)={np.mean(mdd<-0.30)*100:4.1f}%  "
              f"avg time-underwater={under.mean()*100:4.1f}%  P(<start@end)={np.mean(tw<1)*100:4.1f}%")
dist_report(combo7030, "COMBINED 70/30 (A/B inverse)")
dist_report(A_only, "MOMENTUM-ALONE (sleeve A)")
# P(<SPY) at 2yr via paired bootstrap on overlapping daily streams
def p_below_spy(net, spy, yrs=2, n=4000, block=21, haircut=0.30, seed=11):
    df = pd.concat([net.rename("p"), spy.rename("s")], axis=1, join="inner").dropna()
    rng=np.random.default_rng(seed); rp=df["p"].values; rs=df["s"].values
    rp = rp - haircut*rp.mean()  # haircut only the strategy
    n_=len(rp); h=252*yrs; nblk=int(np.ceil(h/block)); cnt=0
    for _ in range(n):
        starts=rng.integers(0,n_-block,size=nblk)
        ip=np.concatenate([rp[s:s+block] for s in starts])[:h]
        isp=np.concatenate([rs[s:s+block] for s in starts])[:h]
        if np.prod(1+ip) < np.prod(1+isp): cnt+=1
    return cnt/n
print(f"\n  P(combo < SPY @2yr) = {p_below_spy(combo7030, spy)*100:.1f}%   "
      f"P(A-alone < SPY @2yr) = {p_below_spy(A_only, spy)*100:.1f}%")

# ---- crisis windows of the locked combo ------------------------------------
sec("6. CRISIS WINDOWS — locked 70/30 combo vs A-alone vs SPY")
def cum(r,a,b):
    x=r[(r.index>=pd.Timestamp(a))&(r.index<=pd.Timestamp(b))]; return (1+x).prod()-1 if len(x) else np.nan
crises={"2008 GFC Sep08-Mar09":("2008-09-01","2009-03-31"),"2008 full yr":("2008-01-01","2008-12-31"),
        "2020 COVID Feb-Mar":("2020-02-19","2020-03-23"),"2022 stk+bond":("2022-01-01","2022-12-31")}
rows=[]
for nm,(a,b) in crises.items():
    rows.append(dict(crisis=nm, combo7030=round(cum(combo7030,a,b),3), A_alone=round(cum(A_only,a,b),3), SPY=round(cum(spy,a,b),3)))
print(pd.DataFrame(rows).to_string(index=False))
print("\nDONE.")
