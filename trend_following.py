#!/usr/bin/env python3
"""
Trend-following / managed-futures style sleeve (TIME-SERIES momentum) and its use
as a DIVERSIFIER for the project's cross-sectional ETF-momentum winner.

TF is structurally different from the XS winner:
  - XS winner: cross-sectional (relative-rank) momentum, long-only, top-K, SPY>200d gate.
  - TF sleeve: TIME-SERIES (absolute) momentum on EACH asset independently. Long when the
    asset's own trend is up; when down go to CASH or to an INVERSE ETF (short proxy).
    Vol-targeted. The classic CTA return stream, famous for crisis alpha.

Short exposure is US-legal only: long ETFs, inverse ETFs (SH/PSQ/TBT/...), or cash.
Inverse ETFs are modelled with their real (already-decaying) adjusted prices, AND we also
test a synthetic short (-1 x underlying, daily-rebalanced) to show the inverse-ETF drag.

Data: yfinance daily adjusted closes.
  - long ETFs reused from /tmp/etfmom_data/etf_prices.csv (shared with the winner)
  - inverse ETFs staged at /tmp/tf_data/inverse_etfs.csv
Costs: 3 bps/side spread on traded notional (matching the winner) + inverse-ETF expense
  drag is already inside the inverse-ETF adjusted price; synthetic short adds an explicit
  borrow-equivalent charge.

All returns NET unless noted.
"""
import numpy as np
import pandas as pd

LONG_PX   = "/tmp/etfmom_data/etf_prices.csv"
INV_PX    = "/tmp/tf_data/inverse_etfs.csv"
COST_BPS  = 3.0
TBILL_ANN = 0.02
TD        = 252
SYNTH_BORROW_ANN = 0.0050   # explicit borrow-equivalent for the SYNTHETIC short test only (50 bps/yr)

# TF universe: broad liquid cross-asset set (equities/bonds/commodities/REIT/dollar)
TF_UNIVERSE = ["SPY","QQQ","EFA","EEM","TLT","IEF","DBC","GLD","USO","VNQ","UUP"]

# map each long ETF -> its inverse ETF (for the inverse-short variant). None => cash only.
INVERSE_MAP = {
    "SPY":"SH", "QQQ":"PSQ", "EFA":"EFZ", "EEM":"EUM",
    "TLT":"TBT",   # TBT is -2x 20y; we scale to 1x notionally
    "VNQ":"RWM",   # RWM = short small-cap (closest liquid real-estate-ish equity short proxy)
    "GLD":"GLL",   # GLL = -2x gold; scale to 1x
    "USO":"DUG",   # DUG = -2x oil&gas; scale to 1x
    # IEF, DBC, UUP have no clean liquid 1x inverse here -> cash when down
}
LEVERAGED_INV = {"TBT":2.0, "GLL":2.0, "DUG":2.0}   # de-lever to ~1x short


def load_long():
    return pd.read_csv(LONG_PX, index_col=0, parse_dates=True).sort_index()

def load_inv():
    return pd.read_csv(INV_PX, index_col=0, parse_dates=True).sort_index()


def cash_daily_ret(idx):
    """daily cash (T-bill) return. Use BIL adj price if present else flat TBILL_ANN."""
    px = load_long()
    if "BIL" in px and px["BIL"].notna().sum() > 250:
        c = px["BIL"].reindex(idx).ffill()
        r = c.pct_change()
        # before BIL inception fill with flat
        r = r.fillna((1+TBILL_ANN)**(1/TD)-1)
        return r
    return pd.Series((1+TBILL_ANN)**(1/TD)-1, index=idx)


def ts_signal(px, asof, lookback_days, mode="trend"):
    """time-series signal per asset at asof.
    mode 'trend': sign of trailing total return over lookback (long if >0).
    mode 'ma'   : price > trailing MA (lookback_days approximates 10m=210d).
    Returns Series of +1 (long) / 0 (flat) / -1 (down -> short or cash) per asset.
    """
    win = px.loc[:asof].tail(lookback_days+1)
    if len(win) < lookback_days*0.6:
        return pd.Series(dtype=float)
    valid = win.notna().sum() >= lookback_days*0.6
    if mode == "trend":
        tot = win.iloc[-1] / win.iloc[0] - 1
        sig = np.sign(tot)
    else:  # ma
        ma = win.mean()
        last = win.iloc[-1]
        sig = np.sign(last - ma)
    sig = sig[valid].dropna()
    return sig


def trailing_vol(px, asof, win_days=63):
    w = px.loc[:asof].tail(win_days+1)
    r = w.pct_change()
    return r.std() * np.sqrt(TD)


def synth_inverse_returns(long_ret, borrow_ann=SYNTH_BORROW_ANN):
    """daily-rebalanced -1x synthetic short of a long ETF, minus borrow-equiv + earns cash on
    the short proceeds (approx: net = -long_ret - borrow_daily). We keep it simple: -1x return
    minus borrow. This intentionally shows the volatility drag of daily rebalancing vs holding."""
    return -long_ret - borrow_ann/TD


def backtest_tf(long_px, inv_px, universe=TF_UNIVERSE, lookback_days=252, mode="trend",
                down="cash", vol_target=0.10, vol_win=63, rebal="M",
                cost_bps=COST_BPS, start=None, end=None, max_leg_lev=2.0):
    """
    Time-series momentum sleeve.
      down: 'cash'   -> when an asset's trend is down, that sleeve goes to cash.
            'inverse'-> when down, hold the inverse ETF (real adjusted price) if mapped, else cash.
            'synth'  -> when down, hold a synthetic -1x short of the underlying (minus borrow).
      vol_target: annualized target vol for the whole sleeve; scale gross by target/realized.
      Each asset gets equal base weight 1/N; sign from ts_signal; sleeve scaled to vol_target.
    Returns daily net return series + avg monthly turnover.
    """
    uni = [t for t in universe if t in long_px.columns]
    idx = long_px.index
    long_ret = long_px[uni].pct_change()
    cash_r = cash_daily_ret(idx)

    # inverse ETF daily returns (de-levered to 1x where leveraged)
    inv_ret = {}
    for t in uni:
        it = INVERSE_MAP.get(t)
        if it and it in inv_px.columns:
            r = inv_px[it].reindex(idx).pct_change()
            lev = LEVERAGED_INV.get(it, 1.0)
            inv_ret[t] = r / lev   # scale -2x down to ~-1x notionally (approx)
    inv_ret = pd.DataFrame(inv_ret)

    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    rebal_dates = [pd.Timestamp(d) for d in me.values]
    if start: rebal_dates = [d for d in rebal_dates if d >= pd.Timestamp(start)]
    if end:   rebal_dates = [d for d in rebal_dates if d <= pd.Timestamp(end)]

    prev = pd.Series(0.0, index=uni)   # previous *signed long-equivalent* exposure per asset for turnover
    turnover_log = []
    last_targets = {}

    for d in rebal_dates:
        sig = ts_signal(long_px[uni], d, lookback_days, mode=mode)
        sig = sig.reindex(uni).fillna(0.0)
        # only trade assets that have data
        have = long_px[uni].loc[:d].iloc[-1].notna()
        sig = sig.where(have, 0.0)

        n_active = int((have).sum())
        base = 1.0/max(n_active,1)

        # realized sleeve vol estimate using equal-weight long proxy of active assets for scaling
        vols = trailing_vol(long_px[uni], d, vol_win).reindex(uni)
        # per-asset inverse-vol-ish? keep simple equal-weight; scale whole sleeve by vol target.
        # estimate sleeve vol as base * sqrt(sum vols^2) (assume ~indep) -> scaler
        active_vols = vols[have].dropna()
        if len(active_vols)>0:
            sleeve_vol = base*np.sqrt((active_vols**2).sum())
            scaler = vol_target/sleeve_vol if sleeve_vol>0 else 1.0
        else:
            scaler = 1.0
        scaler = min(scaler, max_leg_lev)  # cap gross leverage

        tl = pd.Series(0.0, index=uni); ti = pd.Series(0.0, index=uni)
        ts = pd.Series(0.0, index=uni); tc = 0.0
        for t in uni:
            wgt = base*scaler
            if sig[t] > 0:
                tl[t] = wgt
            elif sig[t] < 0:
                if down=="inverse" and t in inv_ret.columns and not np.isnan(inv_ret[t].reindex([d]).iloc[0] if d in inv_ret.index else np.nan):
                    ti[t] = wgt
                elif down=="synth":
                    ts[t] = wgt
                else:
                    tc += wgt   # cash
            else:
                tc += wgt
        # signed long-equiv exposure for turnover bookkeeping
        signed = tl - ti - ts
        turnover_log.append((d, (signed-prev).abs().sum()))
        prev = signed
        last_targets[d] = (tl,ti,ts,tc)

    # forward-fill targets across days: set values on rebalance rows, ffill between.
    WL = pd.DataFrame(index=idx, columns=uni, dtype=float)
    WI = pd.DataFrame(index=idx, columns=uni, dtype=float)
    WS = pd.DataFrame(index=idx, columns=uni, dtype=float)
    WC = pd.Series(index=idx, dtype=float)
    for d,(tl,ti,ts,tc) in last_targets.items():
        WL.loc[d]=tl.values; WI.loc[d]=ti.values; WS.loc[d]=ts.values; WC.loc[d]=tc
    WL=WL.ffill().fillna(0); WI=WI.ffill().fillna(0); WS=WS.ffill().fillna(0); WC=WC.ffill().fillna(0)

    # daily returns
    long_leg  = (WL.shift(1) * long_ret).sum(axis=1)
    inv_leg   = (WI.shift(1) * inv_ret.reindex(columns=uni).reindex(idx)).sum(axis=1) if not inv_ret.empty else pd.Series(0.0,index=idx)
    synth_leg = (WS.shift(1) * (-long_ret).sub(SYNTH_BORROW_ANN/TD, axis=0)).sum(axis=1)
    cash_leg  = WC.shift(1) * cash_r
    # any unallocated (e.g. inverse unavailable rows) -> cash
    invested = WL.sum(axis=1)+WI.sum(axis=1)+WS.sum(axis=1)+WC
    resid = (1.0 - invested).clip(lower=-1.0)  # could exceed 1 if levered; residual on the <1 part is cash
    resid_cash = resid.shift(1).clip(lower=0) * cash_r

    gross = long_leg + inv_leg + synth_leg + cash_leg + resid_cash

    # costs on turnover
    cost = pd.Series(0.0, index=idx)
    for d,to in turnover_log:
        if d in cost.index: cost.loc[d]+= to*cost_bps/1e4
    net = gross - cost
    if start: net = net[net.index>=pd.Timestamp(start)]
    if end:   net = net[net.index<=pd.Timestamp(end)]
    avg_to = np.mean([t for _,t in turnover_log]) if turnover_log else 0
    return net.dropna(), avg_to


def stats(net, freq=TD):
    net = net.dropna()
    if len(net) < 30:
        return dict(CAGR=np.nan,Sharpe=np.nan,maxDD=np.nan,vol=np.nan,n=len(net))
    eq=(1+net).cumprod(); yrs=len(net)/freq
    return dict(CAGR=eq.iloc[-1]**(1/yrs)-1,
                Sharpe=net.mean()/net.std()*np.sqrt(freq) if net.std()>0 else np.nan,
                maxDD=(eq/eq.cummax()-1).min(),
                vol=net.std()*np.sqrt(freq), n=len(net))


def combine(rets_a, rets_b, wa, wb, rebal_freq="M", cost_bps=0.0):
    """Combine two daily return streams with target weights (wa,wb), rebalanced monthly.
    Between rebalances the two legs drift with their own returns (buy-and-hold within month),
    then snap back to (wa,wb) at each month end. Returns combined daily net series on overlap."""
    df = pd.concat([rets_a.rename("a"), rets_b.rename("b")], axis=1, join="inner").dropna()
    idx = df.index
    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    rebal = set(pd.Timestamp(d) for d in me.values)
    a = df["a"].values; b = df["b"].values
    wa_cur, wb_cur = wa, wb
    port = np.empty(len(idx))
    for i in range(len(idx)):
        # apply today's returns to yesterday's weights
        port[i] = wa_cur * a[i] + wb_cur * b[i]
        wa_cur *= (1 + a[i]); wb_cur *= (1 + b[i])
        s = wa_cur + wb_cur
        if s != 0:
            wa_cur, wb_cur = wa_cur / s, wb_cur / s
        if idx[i] in rebal:
            wa_cur, wb_cur = wa, wb
    return pd.Series(port, index=idx).dropna()
