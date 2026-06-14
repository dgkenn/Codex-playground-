#!/usr/bin/env python3
"""
Individual US large-cap STOCK cross-sectional momentum study.

Question: does the SAME momentum framework that won on ETFs (ETF_MOMENTUM.md:
risk-adjusted 6m XS momentum, top-K EW, SPY>200d gate, monthly, partial rebalance,
Sharpe ~0.83 / maxDD ~-17%) earn a HIGHER risk-adjusted return when run on
individual large-cap stocks, which have far higher cross-sectional dispersion?

CRITICAL HONESTY -- SURVIVORSHIP BIAS: the universe is TODAY's large-cap members
(S&P 100 / Nasdaq 100 style list). Backtesting today's winners historically bakes
in the survivors and DELISTS the losers (Lehman, Bear Stearns, GE-collapse, Enron-
type, AIG-near-zero, etc. never appear if they later dropped out). This OVERSTATES
returns -- treat all stock-momentum results below as an OPTIMISTIC UPPER BOUND and
haircut hard. We quantify a haircut explicitly.

Method intentionally mirrors etf_momentum.backtest() so the comparison is apples-to-
apples. Costs: commission-free + per-side spread (large-caps ~2-5 bps).
Data: yfinance daily auto-adjusted (total return). Staged /tmp/sm_data (NOT committed).
"""
import numpy as np
import pandas as pd
import sys

PRICES = "/tmp/sm_data/stock_prices.csv"
ETF_PRICES = "/tmp/etfmom_data/etf_prices.csv"   # for SPY regime + cash, reused from ETF study
COST_BPS = 4.0          # per-side spread on large-caps (2-5bps); 4 = mid. Sensitivity reported.
TBILL_ANN = 0.02
TRADING_DAYS = 252

# ---- universe: ~120 current US large-caps (S&P 100 core + large Nasdaq-100 names) ----
# THIS IS A TODAY-MEMBERS LIST => SURVIVORSHIP BIASED. Flagged throughout.
UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA","BRK-B","JPM","JNJ",
    "V","PG","UNH","HD","MA","BAC","DIS","ADBE","CRM","NFLX",
    "XOM","CVX","PFE","KO","PEP","CSCO","INTC","CMCSA","WMT","T",
    "VZ","ABT","MRK","NKE","ORCL","ACN","TXN","QCOM","COST","MCD",
    "HON","UNP","LOW","UPS","IBM","AMGN","LIN","SBUX","CAT","GS",
    "MS","BLK","AXP","BKNG","GILD","MDT","DE","LMT","ADP","ISRG",
    "MMM","CVS","TMO","DHR","BMY","AMD","MU","AMAT","LRCX","ADI",
    "REGN","VRTX","PYPL","NOW","INTU","SCHW","SPGI","CB","DUK","SO",
    "MO","CL","EL","GE","BA","RTX","GD","EMR","ITW","ECL",
    "WM","FDX","TGT","DG","ROST","TJX","MAR","CME","ICE","USB",
    "PNC","TFC","COF","MET","AIG","PRU","ALL","TRV","D","NEE",
    "AEP","EXC","SLB","COP","EOG","PSX","MPC","VLO","KMI","WMB",
]

def load_prices():
    return pd.read_csv(PRICES, index_col=0, parse_dates=True).sort_index()

def load_etf():
    return pd.read_csv(ETF_PRICES, index_col=0, parse_dates=True).sort_index()

def cash_series(idx):
    """T-bill total return index from BIL (etf data) extended back with flat 2%/yr."""
    try:
        e = load_etf()
        if "BIL" in e and e["BIL"].notna().sum() > 250:
            c = e["BIL"].reindex(idx).ffill()
            first = c.first_valid_index()
            daily = (1+TBILL_ANN)**(1/TRADING_DAYS)
            if first is not None:
                base = c.loc[first]
                mask = c.index < first
                n = int(mask.sum())
                if n>0:
                    c.loc[mask] = base * (daily ** -np.arange(n,0,-1))
            return c.ffill().bfill()
    except Exception:
        pass
    daily = (1+TBILL_ANN)**(1/TRADING_DAYS)
    return pd.Series(daily**np.arange(len(idx)), index=idx)

def spy_series(idx):
    e = load_etf()
    return e["SPY"].reindex(idx).ffill()

def risk_adj_momentum(px, asof, lookback_days, skip_days=0):
    """return/vol over trailing window ending `skip_days` before asof (skip-last-month classic)."""
    sub = px.loc[:asof]
    if skip_days>0:
        sub = sub.iloc[:-skip_days] if len(sub)>skip_days else sub.iloc[0:0]
    window = sub.tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    rets = np.log(window).diff()
    total = np.log(window.iloc[-1] / window.iloc[0])
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    score = total / vol.replace(0, np.nan)
    valid = window.notna().sum() >= lookback_days*0.8
    return score[valid].dropna()

def plain_momentum(px, asof, lookback_days, skip_days=0):
    sub = px.loc[:asof]
    if skip_days>0:
        sub = sub.iloc[:-skip_days] if len(sub)>skip_days else sub.iloc[0:0]
    window = sub.tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    total = np.log(window.iloc[-1] / window.iloc[0])
    valid = window.notna().sum() >= lookback_days*0.8
    return total[valid].dropna()

def abs_momentum(px, asof, lookback_days, cash, skip_days=0):
    sub = px.loc[:asof]
    csub = cash.loc[:asof]
    if skip_days>0:
        sub = sub.iloc[:-skip_days] if len(sub)>skip_days else sub.iloc[0:0]
        csub = csub.iloc[:-skip_days] if len(csub)>skip_days else csub.iloc[0:0]
    window = sub.tail(lookback_days+1)
    cwin = csub.tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    asset_ret = window.iloc[-1] / window.iloc[0] - 1
    cash_ret = cwin.iloc[-1] / cwin.iloc[0] - 1
    return asset_ret - cash_ret

def backtest(px, universe, lookback_days=126, K=15, skip_days=0,
             risk_adj=True, dual=True, regime=False, regime_ma=200,
             partial=1.0, cost_bps=COST_BPS, start=None, end=None):
    universe = [u for u in universe if u in px.columns]
    px = px[universe].copy()
    full_idx = px.index
    cash = cash_series(full_idx)
    spy = spy_series(full_idx)
    daily_rets = px[universe].pct_change()
    cash_ret = cash.pct_change().fillna(0)

    me = pd.Series(full_idx, index=full_idx).groupby([full_idx.year, full_idx.month]).last()
    rebal_dates = list(me.values)
    if start: rebal_dates = [d for d in rebal_dates if pd.Timestamp(d) >= pd.Timestamp(start)]
    if end:   rebal_dates = [d for d in rebal_dates if pd.Timestamp(d) <= pd.Timestamp(end)]

    weights = pd.Series(0.0, index=universe)
    w_hist = {}
    turnover_log = []

    for d in rebal_dates:
        d = pd.Timestamp(d)
        if regime:
            ra = spy.loc[:d].dropna()
            ma = ra.tail(regime_ma).mean()
            risk_on = len(ra) >= regime_ma and ra.iloc[-1] > ma
        else:
            risk_on = True

        if risk_on:
            if risk_adj:
                score = risk_adj_momentum(px[universe], d, lookback_days, skip_days)
            else:
                score = plain_momentum(px[universe], d, lookback_days, skip_days)
            score = score.dropna()
            if dual:
                am = abs_momentum(px[universe], d, lookback_days, cash, skip_days)
                score = score[am.reindex(score.index) > 0]
            score = score.sort_values(ascending=False)
            picks = score.head(K).index.tolist()
            target = pd.Series(0.0, index=universe)
            if picks:
                target[picks] = 1.0/len(picks)
        else:
            target = pd.Series(0.0, index=universe)

        new_w = weights + partial*(target - weights)
        turnover_log.append((d, (new_w - weights).abs().sum()))
        weights = new_w
        w_hist[d] = weights.copy()

    wdf = pd.DataFrame(w_hist).T
    wdf.index = pd.to_datetime(wdf.index)
    wdf = wdf.reindex(full_idx, method="ffill").fillna(0.0)
    cash_weight = (1.0 - wdf.sum(axis=1)).clip(lower=0)
    port_ret = (wdf.shift(1) * daily_rets).sum(axis=1) + cash_weight.shift(1)*cash_ret
    cost = pd.Series(0.0, index=full_idx)
    for d, to in turnover_log:
        d = pd.Timestamp(d)
        if d in cost.index:
            cost.loc[d] += to * cost_bps/1e4
    net = port_ret - cost
    if start: net = net[net.index >= pd.Timestamp(start)]
    if end: net = net[net.index <= pd.Timestamp(end)]
    avg_turnover = np.mean([t for _,t in turnover_log]) if turnover_log else 0
    return net.dropna(), avg_turnover

def stats(net, freq=TRADING_DAYS):
    net = net.dropna()
    if len(net) < 30:
        return dict(CAGR=np.nan, Sharpe=np.nan, maxDD=np.nan, vol=np.nan, n=len(net))
    eq = (1+net).cumprod()
    yrs = len(net)/freq
    cagr = eq.iloc[-1]**(1/yrs) - 1
    sharpe = net.mean()/net.std()*np.sqrt(freq) if net.std()>0 else np.nan
    dd = (eq/eq.cummax() - 1).min()
    return dict(CAGR=cagr, Sharpe=sharpe, maxDD=dd, vol=net.std()*np.sqrt(freq), n=len(net))

def worst_months(net, n=8):
    m = (1+net).resample("ME").prod()-1
    return m.sort_values().head(n)
