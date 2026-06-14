#!/usr/bin/env python3
"""
btc_trend_timing.py — Does simple single-asset TREND-TIMING of BTC/ETH beat
buy-and-hold on a risk-adjusted basis? (in/out on a moving-average / TSMOM rule)

Deployable by a US person via SPOT (Coinbase/Kraken) or spot ETFs (IBIT/ETHA).
Data: yfinance daily closes (BTC-USD, ETH-USD, IBIT, ETHA, BIL), staged at
/tmp/btc_data/prices.csv (NOT committed).

Costs: spot round-trip ~20-40 bps. We charge `cost_bps` PER SIDE on each
in<->out switch (default 20 bps/side = 40 bps round trip). Signal computed on
daily close; trade executes next day's close (no look-ahead). We also report
weekly-signal / monthly-signal variants for whipsaw control.

Out-of-market leg earns cash: BIL (T-bill ETF total return) when available,
else flat 0%. (A stablecoin earns ~0; T-bill ~ realistic IRA cash.)
"""
import numpy as np, pandas as pd, sys, json

DATA = "/tmp/btc_data/prices.csv"
TRADING_DAYS = 365  # crypto trades 7 days/wk; BTC-USD series is daily calendar

def load():
    px = pd.read_csv(DATA, index_col=0, parse_dates=True).sort_index()
    return px

def perf(rets, freq=TRADING_DAYS):
    """rets = daily simple returns (NaN dropped). Returns CAGR, vol, Sharpe, maxDD, etc."""
    r = rets.dropna()
    if len(r) < 2:
        return dict(CAGR=np.nan, vol=np.nan, Sharpe=np.nan, maxDD=np.nan, n=len(r))
    eq = (1+r).cumprod()
    yrs = len(r)/freq
    cagr = eq.iloc[-1]**(1/yrs) - 1
    vol = r.std()*np.sqrt(freq)
    mean_ann = r.mean()*freq
    sharpe = mean_ann/vol if vol>0 else np.nan
    dd = eq/eq.cummax() - 1
    maxdd = dd.min()
    # Sortino
    downside = r[r<0].std()*np.sqrt(freq)
    sortino = mean_ann/downside if downside>0 else np.nan
    return dict(CAGR=cagr, vol=vol, Sharpe=sharpe, Sortino=sortino, maxDD=maxdd,
                final=eq.iloc[-1], n=len(r))

def sma_signal(price, n):
    """1 when close > n-day SMA (else 0). Signal as-of close t; act t+1."""
    sma = price.rolling(n).mean()
    sig = (price > sma).astype(float)
    return sig

def tsmom_signal(price, lookback_days):
    """1 when trailing return over lookback > 0."""
    ret = price/price.shift(lookback_days) - 1
    return (ret > 0).astype(float)

def dual_sma_signal(price, fast, slow):
    return (price.rolling(fast).mean() > price.rolling(slow).mean()).astype(float)

def backtest(price, signal, cash_ret=None, cost_bps_per_side=20.0,
             rebal="daily"):
    """
    signal: 1=hold asset, 0=out. Signal computed at close t -> position effective t+1.
    rebal: 'daily' check every day; 'weekly' only allow position change on Mondays;
           'monthly' only on month start. (Reduces whipsaw.)
    cash_ret: daily simple returns of the cash leg (aligned), else 0.
    Returns: strat daily returns, position series, n_switches.
    """
    asset_ret = price.pct_change()
    sig = signal.copy()
    # Apply rebalance cadence: only update target on allowed days, else carry forward
    if rebal == "weekly":
        allow = price.index.to_series().dt.dayofweek == 0  # Monday
    elif rebal == "monthly":
        allow = price.index.to_series().dt.is_month_start | \
                (price.index.to_series().dt.day <= 3) & (~price.index.to_series().dt.day.duplicated())
        allow = price.index.to_series().groupby([price.index.year, price.index.month]).transform(
            lambda x: x.index == x.index.min())
    else:
        allow = pd.Series(True, index=price.index)
    target = sig.where(allow).ffill().fillna(0)
    # position effective next day (act on t+1 close using signal from close t)
    pos = target.shift(1).fillna(0)
    if cash_ret is None:
        cash_ret = pd.Series(0.0, index=price.index)
    cash_ret = cash_ret.reindex(price.index).fillna(0)
    gross = pos*asset_ret + (1-pos)*cash_ret
    # costs: when position changes, pay cost on traded fraction (full switch = 2 sides)
    dpos = pos.diff().abs().fillna(0)
    cost = dpos * (cost_bps_per_side/1e4)
    strat = gross - cost
    n_switches = (pos.diff().abs()>0).sum()
    return strat, pos, int(n_switches)

def summarize(name, rets, pos=None, n_switches=None, yrs=None):
    p = perf(rets)
    inv = pos.mean() if pos is not None else np.nan
    rt_yr = (n_switches/2)/yrs if (n_switches is not None and yrs) else np.nan
    return dict(name=name, **p, pct_invested=inv, roundtrips_yr=rt_yr)

def fmt(d):
    return (f"{d['name']:<26} CAGR {d['CAGR']*100:6.1f}%  Shp {d['Sharpe']:5.2f}  "
            f"Sort {d.get('Sortino',np.nan):5.2f}  maxDD {d['maxDD']*100:7.1f}%  "
            f"vol {d['vol']*100:5.0f}%  inv {d['pct_invested']*100:4.0f}%  "
            f"rt/yr {d['roundtrips_yr']:4.1f}  n {d['n']}")

def run_asset(px, asset, cash, label, start=None, cost_bps=20.0):
    s = px[asset].dropna()
    if start: s = s[s.index>=start]
    cash_ret = px[cash].pct_change() if cash in px else None
    yrs = len(s)/TRADING_DAYS
    rows=[]
    # Buy and hold
    bh = s.pct_change()
    rows.append(summarize(f"{label} BUY-HOLD", bh, pos=pd.Series(1.0,index=s.index), n_switches=0, yrs=yrs))
    # SMA variants
    for n in [50,100,150,200,250]:
        sig = sma_signal(s,n)
        strat,pos,nsw = backtest(s, sig, cash_ret, cost_bps, "daily")
        rows.append(summarize(f"{label} SMA{n} (daily)", strat, pos, nsw, yrs))
    # 10-month MA approx = 200d on daily; do real 10mo via monthly resample distinct: 210d
    # TSMOM
    for lb,nm in [(63,"3m"),(126,"6m"),(252,"12m")]:
        sig = tsmom_signal(s,lb)
        strat,pos,nsw = backtest(s, sig, cash_ret, cost_bps, "daily")
        rows.append(summarize(f"{label} TSMOM {nm}", strat, pos, nsw, yrs))
    # dual MA
    sig = dual_sma_signal(s,50,200)
    strat,pos,nsw = backtest(s, sig, cash_ret, cost_bps, "daily")
    rows.append(summarize(f"{label} 50/200 cross", strat, pos, nsw, yrs))
    # weekly & monthly cadence on the classic 200d
    for cad in ["weekly","monthly"]:
        sig = sma_signal(s,200)
        strat,pos,nsw = backtest(s, sig, cash_ret, cost_bps, cad)
        rows.append(summarize(f"{label} SMA200 ({cad})", strat, pos, nsw, yrs))
    return rows

def cost_sensitivity(px, asset, cash, n=200):
    s = px[asset].dropna(); cash_ret = px[cash].pct_change()
    yrs=len(s)/TRADING_DAYS
    out=[]
    for cb in [0,10,20,40]:
        sig=sma_signal(s,n); strat,pos,nsw=backtest(s,sig,cash_ret,cb,"weekly")
        out.append((cb, summarize(f"SMA{n} {cb}bps/side", strat,pos,nsw,yrs)))
    return out

def main():
    px = load()
    print("="*120)
    print("DATA:", {c:(str(px[c].dropna().index[0].date()),str(px[c].dropna().index[-1].date()),px[c].count()) for c in px.columns})
    print("="*120)

    sections = [
        ("BTC full (2014-09->)", "BTC-USD", None),
        ("BTC since 2017", "BTC-USD", "2017-01-01"),
        ("BTC since 2020", "BTC-USD", "2020-01-01"),
        ("BTC since 2021-11 (cycle top)", "BTC-USD", "2021-11-01"),
        ("BTC recent OOS 2022->", "BTC-USD", "2022-01-01"),
        ("BTC ETF-era 2024->", "BTC-USD", "2024-01-01"),
        ("ETH full (2017-11->)", "ETH-USD", None),
        ("ETH since 2020", "ETH-USD", "2020-01-01"),
        ("ETH recent OOS 2022->", "ETH-USD", "2022-01-01"),
        ("IBIT ETF (2024-01->)", "IBIT", "2024-01-01"),
        ("ETHA ETF (2024-07->)", "ETHA", "2024-07-01"),
    ]
    allres={}
    for label,asset,start in sections:
        print(f"\n----- {label} -----")
        rows = run_asset(px, asset, "BIL", label.split(" ")[0], start=start)
        allres[label]=rows
        for d in rows:
            print(" ", fmt(d))

    print("\n"+"="*120)
    print("COST SENSITIVITY — BTC SMA200 weekly, full history")
    for cb,d in cost_sensitivity(px,"BTC-USD","BIL",200):
        print(" ", fmt(d))

    # save machine-readable
    flat=[]
    for label,rows in allres.items():
        for d in rows:
            dd=dict(d); dd["section"]=label; flat.append(dd)
    pd.DataFrame(flat).to_csv("/tmp/btc_data/results.csv", index=False)
    print("\nsaved /tmp/btc_data/results.csv")

if __name__=="__main__":
    main()
