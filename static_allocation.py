#!/usr/bin/env python3
"""
STATIC ALLOCATION HONESTY CHECK
================================

Does the project's validated active book (cross-asset ETF momentum, Sharpe ~0.83;
+ 70/30 momentum / inverse-ETF trend-following combo, Sharpe ~0.81 full / ~0.91 OOS,
maxDD ~-13.6%/-12.6%) actually BEAT dead-simple STATIC allocations a US small-bankroll
investor would otherwise hold?  A young/small investor's real alternative is NOT cash --
it is a lazy 3-fund or all-weather portfolio.  If a boring static mix wins risk-adjusted
after costs, that is the most useful (humbling) finding.

Equal-footing rules (the BRUTAL BAR):
  - Same yfinance adjusted (total-return) prices, same window, same realistic cost model
    (commission-free ETFs + 3 bps/side spread charged on rebalance turnover).
  - Same rebalance discipline (monthly here; quarterly variant also reported).
  - Statics get NO survivorship/overfit credit issue -- they are fixed weights, no fitting.
  - Recent-decade holdout (2016-2026) reported alongside full sample.
  - Worst calendar year reported for every strategy.

Static portfolios built (US-legal, fractional-share-deployable at $1k):
  (a) 100% SPY
  (b) 60/40 SPY/AGG
  (c) Permanent Portfolio: 25% each SPY / TLT / GLD / BIL(cash)
  (d) Golden Butterfly: 20% each SPY / IWN(small-value) / TLT / SHY / GLD
  (e) Inverse-vol risk parity of SPY/TLT/GLD/DBC (rolling 63d inverse-vol weights)
  (f) All-Weather-lite: 30% SPY / 55% bonds(40 TLT/15 IEF) / 15% (7.5 GLD/7.5 DBC)

Data: long-history ETF prices reused from /tmp/etfmom_data/etf_prices.csv (shared w/ active
book) + extras (AGG/IWN/SHY) staged at /tmp/static_data/extra_prices.csv.  Neither committed.

All returns NET of 3 bps/side.
"""
import numpy as np
import pandas as pd

ETFMOM_PX = "/tmp/etfmom_data/etf_prices.csv"
EXTRA_PX  = "/tmp/static_data/extra_prices.csv"
COST_BPS  = 3.0
TD        = 252


def load_all():
    a = pd.read_csv(ETFMOM_PX, index_col=0, parse_dates=True)
    b = pd.read_csv(EXTRA_PX,  index_col=0, parse_dates=True)
    # prefer etfmom file where overlap; add extras (AGG/IWN/SHY) that aren't there
    for c in b.columns:
        if c not in a.columns:
            a[c] = b[c].reindex(a.index)
        else:
            # fill any gaps from extras
            a[c] = a[c].combine_first(b[c].reindex(a.index))
    return a.sort_index()


def stats(net, freq=TD):
    net = net.dropna()
    if len(net) < 60:
        return dict(CAGR=np.nan, Sharpe=np.nan, maxDD=np.nan, vol=np.nan,
                    worst_yr=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / freq
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sharpe = net.mean() / net.std() * np.sqrt(freq) if net.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + net).groupby(net.index.year).prod() - 1
    worst = yr.min()
    return dict(CAGR=cagr, Sharpe=sharpe, maxDD=dd, vol=net.std() * np.sqrt(freq),
                worst_yr=worst, n=len(net))


def fixed_weight_port(px, weights, start=None, end=None, rebal="M", cost_bps=COST_BPS):
    """Fixed-weight buy/hold-within-period, snap to target weights at each rebalance.
    weights: dict ticker->target. Costs charged on rebalance turnover."""
    tickers = list(weights.keys())
    sub = px[tickers].dropna()
    if start: sub = sub[sub.index >= pd.Timestamp(start)]
    if end:   sub = sub[sub.index <= pd.Timestamp(end)]
    rets = sub.pct_change().fillna(0)
    idx = sub.index
    if rebal == "M":
        keyed = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    else:  # quarterly
        q = (idx.month - 1) // 3
        keyed = pd.Series(idx, index=idx).groupby([idx.year, q]).last()
    rebal_dates = set(pd.Timestamp(d) for d in keyed.values)

    tgt = np.array([weights[t] for t in tickers], dtype=float)
    tgt = tgt / tgt.sum()
    w = tgt.copy()
    port = np.empty(len(idx))
    cost = np.zeros(len(idx))
    R = rets.values
    for i in range(len(idx)):
        port[i] = float(np.dot(w, R[i]))
        # drift weights with returns
        w = w * (1 + R[i])
        s = w.sum()
        if s != 0:
            w = w / s
        if idx[i] in rebal_dates:
            turnover = np.abs(tgt - w).sum()
            cost[i] += turnover * cost_bps / 1e4
            w = tgt.copy()
    net = pd.Series(port, index=idx) - pd.Series(cost, index=idx)
    return net.dropna()


def inverse_vol_port(px, tickers, start=None, end=None, vol_win=63, rebal="M",
                     cost_bps=COST_BPS):
    """Risk-parity-lite: monthly inverse-vol weights over `tickers`, rebalanced monthly."""
    sub = px[tickers].dropna()
    if start: sub = sub[sub.index >= pd.Timestamp(start)]
    if end:   sub = sub[sub.index <= pd.Timestamp(end)]
    rets = sub.pct_change()
    idx = sub.index
    keyed = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    rebal_dates = [pd.Timestamp(d) for d in keyed.values]

    W = pd.DataFrame(index=idx, columns=tickers, dtype=float)
    for d in rebal_dates:
        vol = rets.loc[:d].tail(vol_win).std() * np.sqrt(TD)
        iv = 1.0 / vol.replace(0, np.nan)
        wv = (iv / iv.sum())
        W.loc[d] = wv.values
    W = W.ffill().fillna(0)
    port = (W.shift(1) * rets).sum(axis=1)
    # cost on turnover at rebalances
    cost = pd.Series(0.0, index=idx)
    prev = None
    for d in rebal_dates:
        cur = W.loc[d]
        if prev is not None:
            to = (cur - prev).abs().sum()
            cost.loc[d] += to * cost_bps / 1e4
        prev = cur
    return (port - cost).dropna()


# ---- static portfolio definitions ----------------------------------------
STATICS = {
    "100% SPY":          {"SPY": 1.0},
    "60/40 SPY/AGG":     {"SPY": 0.60, "AGG": 0.40},
    "Permanent Port":    {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "BIL": 0.25},
    "Golden Butterfly":  {"SPY": 0.20, "IWN": 0.20, "TLT": 0.20, "SHY": 0.20, "GLD": 0.20},
    "All-Weather-lite":  {"SPY": 0.30, "TLT": 0.40, "IEF": 0.15, "GLD": 0.075, "DBC": 0.075},
}
RISKPARITY = ["SPY", "TLT", "GLD", "DBC"]


def run_statics(px, start, end=None, rebal="M"):
    rows = {}
    for name, w in STATICS.items():
        net = fixed_weight_port(px, w, start=start, end=end, rebal=rebal)
        rows[name] = (net, stats(net))
    net = inverse_vol_port(px, RISKPARITY, start=start, end=end)
    rows["Risk-Parity (inv-vol)"] = (net, stats(net))
    return rows


if __name__ == "__main__":
    px = load_all()
    print("data range:", px.index.min().date(), "->", px.index.max().date())
    for name in STATICS:
        for t in STATICS[name]:
            s = px[t].dropna()
            print(f"  {name:18} {t:4} first={s.index.min().date()}")
