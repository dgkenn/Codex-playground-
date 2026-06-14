#!/usr/bin/env python3
"""Driver: run the full ETF momentum study and print a results table."""
import numpy as np, pandas as pd
from etf_momentum import (load_prices, backtest, stats, buyhold, sixty_forty,
                          CORE_UNIVERSE, CRYPTO_PROXY)

pd.set_option("display.width",200, "display.max_columns",50)
px = load_prices()

# common start: sectors begin 1998-12; use 2000-01 so 3/6/12m lookbacks have full data
FULL_START = "2000-06-01"
HOLDOUT_START = "2016-01-01"   # recent decade (~10.5y) OOS holdout

def row(name, net, to=None):
    s = stats(net)
    return dict(strategy=name, CAGR=s["CAGR"], Sharpe=s["Sharpe"], maxDD=s["maxDD"],
                vol=s["vol"], turnover=to, n=s["n"])

LB = {"3m":63, "6m":126, "12m":252}

def section(title): print("\n"+"="*90+"\n"+title+"\n"+"="*90)

# ---------- 1. CROSS-SECTIONAL momentum, lookback x K plateau --------------
section("1. CROSS-SECTIONAL risk-adj momentum (monthly, long-only, top-K). FULL SAMPLE 2000-2026")
rows=[]
for lbn,lb in LB.items():
    for K in [3,5,8]:
        net,to = backtest(px, CORE_UNIVERSE, lookback_days=lb, K=K,
                          risk_adj=True, dual=False, regime=False, start=FULL_START)
        rows.append({**row(f"XS rk {lbn} K={K}", net, to)})
print(pd.DataFrame(rows).round(3).to_string(index=False))

section("1b. plain vs risk-adj momentum (6m, K=5, full sample)")
rows=[]
for ra in [True,False]:
    net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=ra,dual=False,regime=False,start=FULL_START)
    rows.append(row(f"XS {'riskadj' if ra else 'plain'} 6m K5",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 2. TIME-SERIES / DUAL momentum --------------------------------
section("2. DUAL momentum (XS rank + absolute>cash filter), 6m K=5, full sample")
rows=[]
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=False,regime=False,start=FULL_START)
rows.append(row("XS only 6m K5",net,to))
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=False,start=FULL_START)
rows.append(row("DUAL (XS+abs) 6m K5",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 3. REGIME filter ----------------------------------------------
section("3. REGIME gate (SPY>200d MA -> else cash). 6m K=5, full sample")
rows=[]
for dual in [False,True]:
    for reg in [False,True]:
        net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=dual,regime=reg,start=FULL_START)
        rows.append(row(f"dual={dual} regime={reg}",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 4. RECENT-DECADE HOLDOUT --------------------------------------
section("4. RECENT-DECADE OOS HOLDOUT (2016-2026). best configs")
configs = [
    ("XS 6m K5",            dict(lookback_days=126,K=5,dual=False,regime=False)),
    ("DUAL 6m K5",          dict(lookback_days=126,K=5,dual=True, regime=False)),
    ("DUAL+regime 6m K5",   dict(lookback_days=126,K=5,dual=True, regime=True)),
    ("XS+regime 12m K5",    dict(lookback_days=252,K=5,dual=False,regime=True)),
    ("DUAL+regime 12m K5",  dict(lookback_days=252,K=5,dual=True, regime=True)),
    ("DUAL+regime 3m K3",   dict(lookback_days=63, K=3,dual=True, regime=True)),
]
rows=[]
for name,cfg in configs:
    net,to=backtest(px,CORE_UNIVERSE,risk_adj=True,start=HOLDOUT_START,**cfg)
    rows.append(row(name,net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 5. COMPARISON baselines ---------------------------------------
section("5. BASELINES (full sample 2000-2026)")
rows=[]
rows.append(row("SPY buy&hold", buyhold(px,"SPY",start=FULL_START)))
rows.append(row("60/40 SPY/IEF", sixty_forty(px,start=FULL_START)))
rows.append(row("QQQ buy&hold", buyhold(px,"QQQ",start=FULL_START)))
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,start=FULL_START)
rows.append(row("BEST: DUAL+regime 6m K5",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

section("5b. SAME on RECENT DECADE 2016-2026")
rows=[]
rows.append(row("SPY buy&hold", buyhold(px,"SPY",start=HOLDOUT_START)))
rows.append(row("60/40 SPY/IEF", sixty_forty(px,start=HOLDOUT_START)))
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,start=HOLDOUT_START)
rows.append(row("DUAL+regime 6m K5",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 6. CRYPTO-PROXY effect ----------------------------------------
section("6. Add crypto-proxy ETFs (GBTC/MSTR/COIN/IBIT) to universe. DUAL+regime 6m K5")
rows=[]
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,start="2016-01-01")
rows.append(row("core (no crypto) 2016+",net,to))
net,to=backtest(px,CORE_UNIVERSE+CRYPTO_PROXY,126,5,risk_adj=True,dual=True,regime=True,start="2016-01-01")
rows.append(row("core+crypto 2016+",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 7. PARTIAL rebalance / turnover -------------------------------
section("7. PARTIAL rebalance (turnover control). DUAL+regime 6m K5 full sample")
rows=[]
for p in [1.0,0.5,0.34]:
    net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,partial=p,start=FULL_START)
    rows.append(row(f"partial={p}",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 8. COST sensitivity -------------------------------------------
section("8. COST sensitivity (bps per side traded). DUAL+regime 6m K5 full sample")
rows=[]
for c in [0,3,10,25]:
    net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,cost_bps=c,start=FULL_START)
    rows.append(row(f"cost={c}bps",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 9. 2022 stress + by-year drawdown -----------------------------
section("9. 2022 stress (stocks+bonds down). full year 2022")
rows=[]
rows.append(row("SPY 2022", buyhold(px,"SPY",start="2022-01-01",end="2022-12-31")))
rows.append(row("60/40 2022", sixty_forty(px,start="2022-01-01",end="2022-12-31")))
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=True,regime=True,start="2022-01-01",end="2022-12-31")
rows.append(row("DUAL+regime 2022",net,to))
net,to=backtest(px,CORE_UNIVERSE,126,5,risk_adj=True,dual=False,regime=False,start="2022-01-01",end="2022-12-31")
rows.append(row("XS-only 2022",net,to))
print(pd.DataFrame(rows).round(3).to_string(index=False))
