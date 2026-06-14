"""Cross-sectional crypto momentum backtest engine + signal/universe/weighting sweeps.

DESIGN / BAR (per task):
- Weekly rebalance, perp long+short, dollar-neutral default.
- Costs: configurable bps/side (default 9 = ~18bps round-trip per leg turnover).
- OOS protocol: pick nothing on the holdout. We HARD-SPLIT: IS = all but last 18 months,
  OOS = last 18 months. Recent-regime = last 12 months reported separately.
- All signals computed on data up to t (close), positions held t -> t+7d, return realized.
- Survivorship: OKX serves only listed instruments; delisted alts missing => upward bias.

We report NET Sharpe (annualized, weekly bars * sqrt(52)) and ann return, recent-regime.
"""
import numpy as np
import pandas as pd

DATA = "/tmp/mom_signal/mom_data.parquet"


def load_panel():
    df = pd.read_parquet(DATA)
    px = df.pivot(index="ts", columns="sym", values="c").sort_index()
    vol = df.pivot(index="ts", columns="sym", values="volq").sort_index()  # quote volume (USDT)
    px.index = pd.to_datetime(px.index)
    return px, vol


def liquid_universe(vol, asof, top_n, window=30):
    """Top-N by trailing median quote-volume as of date `asof` (point-in-time)."""
    w = vol.loc[:asof].tail(window)
    med = w.median()
    med = med.dropna()
    return list(med.sort_values(ascending=False).head(top_n).index)


def zscore(s):
    s = s.dropna()
    if len(s) < 3 or s.std() == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / s.std()


# ----- SIGNAL VARIANTS -----
def sig_raw(px, t, lb):
    """Plain return rank over lb days."""
    p = px.loc[:t]
    if len(p) < lb + 1:
        return None
    return p.iloc[-1] / p.iloc[-1 - lb] - 1.0


def sig_riskadj(px, t, lb):
    """Trailing return / trailing daily-return vol (Sharpe-like)."""
    p = px.loc[:t]
    if len(p) < lb + 2:
        return None
    ret = p.iloc[-1] / p.iloc[-1 - lb] - 1.0
    dret = p.pct_change().iloc[-lb:]
    v = dret.std()
    return ret / v.replace(0, np.nan)


def sig_skip(px, t, lb, skip=3):
    """Return from t-lb to t-skip (skip last few days to dodge ST reversal)."""
    p = px.loc[:t]
    if len(p) < lb + 1:
        return None
    return p.iloc[-1 - skip] / p.iloc[-1 - lb] - 1.0


def sig_ensemble(px, t, lbs=(7, 14, 30, 60)):
    """Average cross-sectional rank across multiple lookbacks."""
    if isinstance(lbs, int):
        lbs = (7, 14, 30, 60)
    ranks = []
    for lb in lbs:
        s = sig_raw(px, t, lb)
        if s is None:
            continue
        ranks.append(s.rank(pct=True))
    if not ranks:
        return None
    return pd.concat(ranks, axis=1).mean(axis=1)


def sig_residual(px, t, lb, mkt="BTC"):
    """Residual momentum: regress each coin's daily ret on BTC ret over lb, rank cum residual.
    Removes market-beta component, isolates idiosyncratic momentum."""
    p = px.loc[:t]
    if len(p) < lb + 2 or mkt not in p.columns:
        return None
    dret = p.pct_change().iloc[-lb:]
    if mkt not in dret or dret[mkt].std() == 0:
        return None
    bm = dret[mkt].values
    var_b = np.var(bm)
    out = {}
    for c in dret.columns:
        y = dret[c].values
        if np.isnan(y).any() or np.isnan(bm).any():
            mask = ~(np.isnan(y) | np.isnan(bm))
            if mask.sum() < lb // 2:
                continue
            yc, bc = y[mask], bm[mask]
        else:
            yc, bc = y, bm
        if np.var(bc) == 0:
            continue
        beta = np.cov(yc, bc)[0, 1] / np.var(bc)
        alpha = yc.mean() - beta * bc.mean()
        resid = yc - (alpha + beta * bc)
        # cumulative residual return as momentum score
        out[c] = np.nansum(resid)
    return pd.Series(out) if out else None


# ----- WEIGHTING -----
def weights(sig, univ, frac=0.30, scheme="equal", vol_panel=None, px=None, t=None):
    """Build dollar-neutral long/short weights from signal over universe."""
    s = sig.reindex(univ).dropna()
    if len(s) < 4:
        return None
    n_side = max(1, int(round(len(s) * frac)))
    ranked = s.sort_values()
    shorts = ranked.index[:n_side]
    longs = ranked.index[-n_side:]
    w = pd.Series(0.0, index=s.index)

    if scheme == "equal":
        w[longs] = 1.0 / len(longs)
        w[shorts] = -1.0 / len(shorts)
    elif scheme == "rank":
        # weight proportional to rank distance from median
        r = s.rank(pct=True) - 0.5
        rl = r[longs].clip(lower=0)
        rs = (-r[shorts]).clip(lower=0)
        w[longs] = rl / rl.sum() if rl.sum() > 0 else 1.0 / len(longs)
        w[shorts] = -(rs / rs.sum()) if rs.sum() > 0 else -1.0 / len(shorts)
    elif scheme == "signal":
        sl = (s[longs] - s[longs].min() + 1e-9)
        ss = (s[shorts].max() - s[shorts] + 1e-9)
        w[longs] = sl / sl.sum()
        w[shorts] = -(ss / ss.sum())
    elif scheme == "volinv":
        dret = px.loc[:t].pct_change().iloc[-30:]
        iv = (1.0 / dret.std()).replace([np.inf, -np.inf], np.nan)
        ivl = iv.reindex(longs).fillna(iv.median())
        ivs = iv.reindex(shorts).fillna(iv.median())
        w[longs] = ivl / ivl.sum()
        w[shorts] = -(ivs / ivs.sum())
    # enforce dollar-neutral (sum=0) and gross=2 (1 long, 1 short)
    lsum = w[w > 0].sum()
    ssum = -w[w < 0].sum()
    if lsum > 0:
        w[w > 0] = w[w > 0] / lsum
    if ssum > 0:
        w[w < 0] = w[w < 0] / ssum
    return w


def run_backtest(px, vol, signal_fn, lb=14, top_n=15, frac=0.30, scheme="equal",
                 cost_bps=9.0, exclude_mega=False, hold_days=7, vol_target=False):
    """Weekly rebalance backtest. Returns DataFrame of dated net returns."""
    dates = px.index
    # weekly rebalance dates
    rb_dates = dates[::hold_days]
    recs = []
    prev_w = None
    for i, t in enumerate(rb_dates[:-1]):
        nxt = rb_dates[i + 1] if i + 1 < len(rb_dates) else dates[-1]
        univ = liquid_universe(vol, t, top_n)
        if exclude_mega:
            univ = [u for u in univ if u not in ("BTC", "ETH")]
        if len(univ) < 4:
            continue
        try:
            sig = signal_fn(px, t, lb)
        except TypeError:
            sig = signal_fn(px, t)
        if sig is None:
            continue
        w = weights(sig, univ, frac=frac, scheme=scheme, vol_panel=vol, px=px, t=t)
        if w is None:
            continue
        # forward return over holding period
        p_now = px.loc[t]
        p_nxt = px.loc[nxt]
        fwd = (p_nxt / p_now - 1.0).reindex(w.index)
        gross_ret = float((w * fwd).sum(skipna=True))
        # turnover cost
        if prev_w is None:
            turnover = w.abs().sum()
        else:
            allk = w.index.union(prev_w.index)
            turnover = (w.reindex(allk).fillna(0) - prev_w.reindex(allk).fillna(0)).abs().sum()
        cost = turnover * (cost_bps / 1e4)
        net_ret = gross_ret - cost
        recs.append({"date": nxt, "gross": gross_ret, "net": net_ret,
                     "turnover": turnover, "n": len(w)})
        prev_w = w
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


def stats(r, periods_per_year=52.0):
    if len(r) < 5:
        return dict(n=len(r), sharpe=np.nan, ann_ret=np.nan, ann_vol=np.nan)
    mu = r.mean()
    sd = r.std()
    sharpe = (mu / sd) * np.sqrt(periods_per_year) if sd > 0 else np.nan
    ann_ret = mu * periods_per_year
    ann_vol = sd * np.sqrt(periods_per_year)
    return dict(n=len(r), sharpe=sharpe, ann_ret=ann_ret, ann_vol=ann_vol)


def window_stats(bt, label_split=18, recent_months=12):
    """Return (full, oos18, recent12) net-return stat dicts."""
    if bt.empty:
        return None
    end = bt.index.max()
    oos_start = end - pd.DateOffset(months=label_split)
    rec_start = end - pd.DateOffset(months=recent_months)
    full = stats(bt["net"])
    oos = stats(bt.loc[bt.index >= oos_start, "net"])
    rec = stats(bt.loc[bt.index >= rec_start, "net"])
    return full, oos, rec
