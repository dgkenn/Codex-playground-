#!/usr/bin/env python3
"""
ETF / cross-asset momentum study.

Tests whether cross-sectional + time-series (dual) momentum on liquid ETFs is a
better-deployable edge for a US retail small bankroll than the crypto long-only
momentum sleeve (Sharpe ~0.5, maxDD -40..-60%).

Method reused from the crypto momentum work:
  - risk-adjusted momentum (return / vol)
  - monthly rebalance (equity momentum is slow; classic 3/6/12m horizons)
  - dual momentum (absolute filter) + regime gate for drawdown control
  - partial rebalance to cut turnover
  - honest OOS: full-sample + recent-decade holdout, plateau across lookback/K.

Data: yfinance daily adjusted closes (auto_adjust=True => total-return).
      Staged at /tmp/etfmom_data/etf_prices.csv (NOT committed).

All returns are NET of costs (commission-free ETFs + spread; see COST_BPS).
"""
import numpy as np
import pandas as pd

PRICES = "/tmp/etfmom_data/etf_prices.csv"
COST_BPS = 3.0          # round-trip-ish per-side traded notional cost (spread); commission = 0
TBILL_ANN = 0.02        # fallback cash yield if no BIL/SHY; overridden by BIL proxy when present
TRADING_DAYS = 252

# ---- universes -----------------------------------------------------------
SECTORS = ["XLK","XLE","XLF","XLV","XLI","XLY","XLP","XLU","XLB"]  # XLRE late (2015)
STYLE   = ["SPY","QQQ","IWM"]
INTL    = ["EFA","EEM","EWJ","EWZ","EWG","EWU","FXI","VGK"]
ASSETS  = ["TLT","IEF","GLD","DBC","USO","VNQ","UUP","SLV","HYG","LQD"]
CRYPTO_PROXY = ["GBTC","MSTR","COIN","IBIT"]

CORE_UNIVERSE = sorted(set(SECTORS + STYLE + INTL + ASSETS))   # survivorship-aware liquid set


def load_prices():
    px = pd.read_csv(PRICES, index_col=0, parse_dates=True).sort_index()
    return px


def cash_series(px, idx):
    """Daily cash (T-bill) total-return index. Use BIL if available else SHY else flat 2%/yr."""
    if "BIL" in px and px["BIL"].notna().sum() > 250:
        c = px["BIL"].reindex(idx).ffill()
        # before BIL inception, extend with constant yield
        first = c.first_valid_index()
        daily = (1+TBILL_ANN)**(1/TRADING_DAYS)
        pre = c.copy()
        if first is not None:
            base = c.loc[first]
            # build backward synthetic
            mask = c.index < first
            n = mask.sum()
            if n>0:
                factors = daily ** -np.arange(n,0,-1)
                pre.loc[mask] = base * factors
        return pre.ffill().bfill()
    # synthetic flat
    daily = (1+TBILL_ANN)**(1/TRADING_DAYS)
    return pd.Series(daily**np.arange(len(idx)), index=idx)


def month_end_index(idx):
    s = pd.Series(idx, index=idx)
    return s.groupby([idx.year, idx.month]).last().values


def risk_adj_momentum(px, asof, lookback_days):
    """return / vol over trailing window, computed from daily log rets ending at asof."""
    window = px.loc[:asof].tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    rets = np.log(window).diff().dropna(how="all")
    total = np.log(window.iloc[-1] / window.iloc[0])
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    score = total / vol.replace(0, np.nan)
    # require full data over window
    valid = window.notna().sum() >= lookback_days*0.8
    return score[valid].dropna()


def plain_momentum(px, asof, lookback_days):
    window = px.loc[:asof].tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    total = np.log(window.iloc[-1] / window.iloc[0])
    valid = window.notna().sum() >= lookback_days*0.8
    return total[valid].dropna()


def abs_momentum(px, asof, lookback_days, cash):
    """trailing total return of each asset minus trailing cash return (for dual-momentum gate)."""
    window = px.loc[:asof].tail(lookback_days+1)
    cwin = cash.loc[:asof].tail(lookback_days+1)
    if len(window) < lookback_days*0.8:
        return pd.Series(dtype=float)
    asset_ret = window.iloc[-1] / window.iloc[0] - 1
    cash_ret = cwin.iloc[-1] / cwin.iloc[0] - 1
    return asset_ret - cash_ret  # >0 means beats cash


def backtest(px, universe, lookback_days=126, K=5, rebal="M",
             risk_adj=True, dual=True, regime=False, regime_asset="SPY",
             regime_ma=200, partial=1.0, cost_bps=COST_BPS, start=None, end=None):
    """
    Long-only momentum backtest, monthly rebalance.
    dual: if True, only hold assets whose absolute (vs cash) momentum > 0; rest -> cash.
    regime: if True, SPY must be above its `regime_ma`-day MA else 100% cash.
    partial: fraction of the way to move toward target weights each rebalance (turnover control).
    Returns daily net-return series + diagnostics.
    """
    px = px[universe + ([regime_asset] if regime_asset not in universe else [])].copy()
    full_idx = px.index
    cash = cash_series(pd.read_csv(PRICES,index_col=0,parse_dates=True), full_idx)
    daily_rets = px[universe].pct_change()
    cash_ret = cash.pct_change().fillna(0)

    # rebalance dates = month ends
    me = pd.Series(full_idx, index=full_idx).groupby([full_idx.year, full_idx.month]).last()
    rebal_dates = list(me.values)

    if start: rebal_dates = [d for d in rebal_dates if pd.Timestamp(d) >= pd.Timestamp(start)]
    if end:   rebal_dates = [d for d in rebal_dates if pd.Timestamp(d) <= pd.Timestamp(end)]

    weights = pd.Series(0.0, index=universe)  # current weights (rest in cash)
    w_hist = {}
    turnover_log = []

    for d in rebal_dates:
        d = pd.Timestamp(d)
        # regime gate
        if regime:
            ra = px[regime_asset].loc[:d]
            ma = ra.tail(regime_ma).mean()
            risk_on = len(ra) >= regime_ma and ra.iloc[-1] > ma
        else:
            risk_on = True

        if risk_on:
            if risk_adj:
                score = risk_adj_momentum(px[universe], d, lookback_days)
            else:
                score = plain_momentum(px[universe], d, lookback_days)
            score = score.dropna()
            if dual:
                am = abs_momentum(px[universe], d, lookback_days, cash)
                score = score[am.reindex(score.index) > 0]
            score = score.sort_values(ascending=False)
            picks = score.head(K).index.tolist()
            if len(picks) == 0:
                target = pd.Series(0.0, index=universe)
            else:
                target = pd.Series(0.0, index=universe)
                target[picks] = 1.0/len(picks)
        else:
            target = pd.Series(0.0, index=universe)

        new_w = weights + partial*(target - weights)
        turnover = (new_w - weights).abs().sum()
        turnover_log.append((d, turnover))
        weights = new_w
        w_hist[d] = weights.copy()

    # build daily portfolio returns by holding weights between rebalances
    wdf = pd.DataFrame(w_hist).T
    wdf.index = pd.to_datetime(wdf.index)
    wdf = wdf.reindex(full_idx, method="ffill").fillna(0.0)

    cash_weight = (1.0 - wdf.sum(axis=1)).clip(lower=0)
    port_ret = (wdf.shift(1) * daily_rets).sum(axis=1) + cash_weight.shift(1)*cash_ret
    # apply costs on rebalance days proportional to turnover
    cost = pd.Series(0.0, index=full_idx)
    for d, to in turnover_log:
        d = pd.Timestamp(d)
        if d in cost.index:
            cost.loc[d] += to * cost_bps/1e4
    net = port_ret - cost
    net = net.loc[ (full_idx >= pd.Timestamp(start)) if start else slice(None) ]
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


def buyhold(px, ticker, start=None, end=None):
    s = px[ticker].dropna()
    r = s.pct_change()
    if start: r = r[r.index>=pd.Timestamp(start)]
    if end: r = r[r.index<=pd.Timestamp(end)]
    return r.dropna()


def sixty_forty(px, start=None, end=None):
    """60% SPY / 40% IEF, monthly rebalanced (total return)."""
    sub = px[["SPY","IEF"]].dropna()
    rets = sub.pct_change()
    me = pd.Series(sub.index,index=sub.index).groupby([sub.index.year,sub.index.month]).last()
    w = pd.DataFrame(index=sub.index, columns=["SPY","IEF"], dtype=float)
    for d in me.values:
        w.loc[d]=[0.6,0.4]
    w = w.ffill().fillna(0)
    port = (w.shift(1)*rets).sum(axis=1)
    if start: port=port[port.index>=pd.Timestamp(start)]
    if end: port=port[port.index<=pd.Timestamp(end)]
    return port.dropna()
