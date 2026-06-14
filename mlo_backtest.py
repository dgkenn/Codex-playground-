"""LONG-ONLY US-SPOT cross-sectional momentum backtest engine.

Deployable by a US person on Coinbase/Kraken USD spot (NO short, NO leverage, NO funding).
Signal/cadence/turnover-control are REUSED verbatim from the validated L/S spec
(MOMENTUM_SPEC.md): risk-adjusted ~10d momentum (trailing return / trailing vol),
point-in-time liquid universe, WEEKLY rebalance, partial-rebalance toward target.

Difference vs L/S:
  - Hold the TOP-K momentum names LONG, equal-weight. The rest of the book sits in CASH
    (USDC, return 0). NO short leg.
  - BTC-trend gate -> when BTC < its MA, go FULLY TO CASH. This REPLACES the short leg as
    the downside-protection mechanism (long-only has no short hedge).
  - Fees: realistic US-spot round-trip taker. Base 40 bps RT (Coinbase Advanced retail
    ~0.4-0.6%, Kraken Pro ~0.2-0.4%). Applied to per-rebalance turnover (sum |dw|).
    Cash<->coin moves are charged; coin-stays are not.

Cost convention: `cost_bps` is the ROUND-TRIP cost per 1.0 of notional traded one way.
A buy of weight w and later sell of weight w => turnover counts each |dw|. To make
`cost_bps` mean "round trip", we charge cost_bps/2 per unit |dw| (one side), so a full
buy-then-sell cycle (|dw|=1 in, |dw|=1 out) costs cost_bps total. This matches the L/S
engine's "round-trip per unit |Δw|" convention being HALVED per side.
  -> charge = turnover * (cost_bps/2) / 1e4

Survivorship: Coinbase serves only listed pairs (dead alts missing) => UP bias. Documented.
Backtests SCREEN. Window stated everywhere.
"""
import numpy as np
import pandas as pd

SPOT = "/tmp/mlo_data/mlo_spot.parquet"
PERP = "/tmp/mom_signal/mom_data.parquet"


def load_spot():
    df = pd.read_parquet(SPOT)
    px = df.pivot(index="ts", columns="sym", values="c").sort_index()
    vol = df.pivot(index="ts", columns="sym", values="volq").sort_index()
    px.index = pd.to_datetime(px.index)
    # forward-fill at most 2 days for sporadic gaps; drop all-nan rows
    px = px.dropna(how="all")
    vol = vol.reindex(px.index)
    return px, vol


def load_perp():
    df = pd.read_parquet(PERP)
    px = df.pivot(index="ts", columns="sym", values="c").sort_index()
    vol = df.pivot(index="ts", columns="sym", values="volq").sort_index()
    px.index = pd.to_datetime(px.index)
    return px, vol


# ---------- signal (reused from L/S spec) ----------
def sig_riskadj(px, t, lb):
    p = px.loc[:t]
    if len(p) < lb + 2:
        return None
    ret = p.iloc[-1] / p.iloc[-1 - lb] - 1.0
    dret = p.pct_change().iloc[-lb:]
    v = dret.std()
    return ret / v.replace(0, np.nan)


def liquid_universe(vol, asof, top_n, window=30):
    w = vol.loc[:asof].tail(window)
    med = w.median().dropna()
    return list(med.sort_values(ascending=False).head(top_n).index)


# ---------- BTC trend gate (replaces short-leg downside protection) ----------
def btc_above_ma(px, t, ma_len):
    """True if BTC close >= its trailing ma_len-day SMA as of t (point-in-time)."""
    if "BTC" not in px.columns:
        return True
    p = px["BTC"].loc[:t].dropna()
    if len(p) < ma_len + 1:
        return True
    ma = p.tail(ma_len).mean()
    return float(p.iloc[-1]) >= float(ma)


# ---------- long-only backtest ----------
def backtest_lo(px, vol, lb=10, top_n=15, k=5, hold_days=7,
                cost_bps=40.0, partial=0.7, gate_ma=None, univ_pool=None):
    """LONG-ONLY weekly momentum.
       k: number of top names held (equal-weight). If k is a float in (0,1], treat as
          a quantile fraction of the universe (e.g. 0.30 -> top 30%).
       gate_ma: if set (e.g. 100), go fully to cash when BTC < its gate_ma-day MA.
       partial: move `partial` of the gap from current book toward target each rebalance.
       univ_pool: optional fixed list to restrict the tradeable universe (US-spot coins).
       cost_bps: ROUND-TRIP bps; charged as cost_bps/2 per unit |dw|.
       Cash earns 0. Returns DataFrame indexed by realized date.
    """
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    cur_w = None  # actual coin weights held (sum<=1; remainder in cash)
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        univ = liquid_universe(vol, t, top_n)
        if univ_pool is not None:
            univ = [u for u in univ if u in univ_pool]
        if len(univ) < 4:
            continue
        gated_off = (gate_ma is not None) and (not btc_above_ma(px, t, gate_ma))
        sig = sig_riskadj(px, t, lb)
        if sig is None:
            continue
        s = sig.reindex(univ).dropna()
        if len(s) < 4:
            continue
        if isinstance(k, float) and 0 < k <= 1:
            n_hold = max(1, int(round(len(s) * k)))
        else:
            n_hold = int(k)
        n_hold = min(n_hold, len(s))
        if gated_off:
            tw = pd.Series(0.0, index=s.index)  # all cash
        else:
            longs = s.sort_values().index[-n_hold:]
            tw = pd.Series(0.0, index=s.index)
            tw[longs] = 1.0 / n_hold
        # partial move toward target
        if cur_w is None:
            new_w = tw.copy()
        else:
            idx = tw.index.union(cur_w.index)
            a = cur_w.reindex(idx).fillna(0.0)
            b = tw.reindex(idx).fillna(0.0)
            new_w = a + partial * (b - a)
        # turnover (per-coin |dw|), includes cash<->coin
        if cur_w is None:
            dchg = new_w.abs()
        else:
            idx = new_w.index.union(cur_w.index)
            dchg = (new_w.reindex(idx).fillna(0.0) - cur_w.reindex(idx).fillna(0.0)).abs()
        turnover = float(dchg.sum())
        cost = turnover * (cost_bps / 2.0) / 1e4
        fwd = (px.loc[nxt] / px.loc[t] - 1.0).reindex(new_w.index)
        gross = float((new_w * fwd).sum(skipna=True))  # cash (weight 0) contributes 0
        recs.append({"date": nxt, "gross": gross, "net": gross - cost,
                     "turnover": turnover, "cost": cost,
                     "invested": float(new_w.clip(lower=0).sum()), "gated": gated_off})
        cur_w = new_w
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


# ---------- L/S dollar-neutral (the LOST edge) on the SAME (spot or perp) panel ----------
def backtest_ls(px, vol, lb=10, top_n=15, frac=0.30, hold_days=7,
                cost_bps=40.0, partial=0.7, gate_ma=None, univ_pool=None):
    """Dollar-neutral long-top/short-bottom, equal-weight. For benchmark comparison.
       Same cost convention (cost_bps/2 per |dw|). gate_ma -> flat (cash) when BTC<MA."""
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    cur_w = None
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        univ = liquid_universe(vol, t, top_n)
        if univ_pool is not None:
            univ = [u for u in univ if u in univ_pool]
        if len(univ) < 4:
            continue
        gated_off = (gate_ma is not None) and (not btc_above_ma(px, t, gate_ma))
        sig = sig_riskadj(px, t, lb)
        if sig is None:
            continue
        s = sig.reindex(univ).dropna()
        if len(s) < 4:
            continue
        n_side = max(1, int(round(len(s) * frac)))
        ranked = s.sort_values()
        if gated_off:
            tw = pd.Series(0.0, index=s.index)
        else:
            shorts = ranked.index[:n_side]
            longs = ranked.index[-n_side:]
            tw = pd.Series(0.0, index=s.index)
            tw[longs] = 1.0 / len(longs)
            tw[shorts] = -1.0 / len(shorts)
        if cur_w is None:
            new_w = tw.copy()
        else:
            idx = tw.index.union(cur_w.index)
            a = cur_w.reindex(idx).fillna(0.0)
            b = tw.reindex(idx).fillna(0.0)
            new_w = a + partial * (b - a)
        if cur_w is None:
            dchg = new_w.abs()
        else:
            idx = new_w.index.union(cur_w.index)
            dchg = (new_w.reindex(idx).fillna(0.0) - cur_w.reindex(idx).fillna(0.0)).abs()
        turnover = float(dchg.sum())
        cost = turnover * (cost_bps / 2.0) / 1e4
        fwd = (px.loc[nxt] / px.loc[t] - 1.0).reindex(new_w.index)
        gross = float((new_w * fwd).sum(skipna=True))
        recs.append({"date": nxt, "gross": gross, "net": gross - cost,
                     "turnover": turnover, "cost": cost, "gated": gated_off})
        cur_w = new_w
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


# ---------- passive benchmarks ----------
def ew_buyhold(px, vol, top_n=15, hold_days=7, univ_pool=None, rebal_univ=True):
    """Equal-weight buy-and-hold the liquid universe, rebal weekly to equal weight
       (so it tracks 'own the basket'). No momentum selection. cost ~0 (long-term hold,
       weekly rebal cost is tiny; we report gross to be charitable to the benchmark)."""
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        univ = liquid_universe(vol, t, top_n)
        if univ_pool is not None:
            univ = [u for u in univ if u in univ_pool]
        if len(univ) < 2:
            continue
        fwd = (px.loc[nxt, univ] / px.loc[t, univ] - 1.0)
        recs.append({"date": nxt, "net": float(fwd.mean(skipna=True)), "gross": float(fwd.mean(skipna=True))})
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


def asset_buyhold(px, sym="BTC", hold_days=7):
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        if sym not in px.columns:
            continue
        r = px.loc[nxt, sym] / px.loc[t, sym] - 1.0
        if pd.isna(r):
            continue
        recs.append({"date": nxt, "net": float(r), "gross": float(r)})
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


# ---------- stats ----------
def stats(r, hold_days=7):
    ppy = 365.0 / hold_days
    r = r.dropna()
    if len(r) < 5 or r.std() == 0:
        return dict(n=len(r), sharpe=np.nan, ann_ret=np.nan, ann_vol=np.nan, maxdd=np.nan)
    mu, sd = r.mean(), r.std()
    sharpe = mu / sd * np.sqrt(ppy)
    ann_ret = mu * ppy
    ann_vol = sd * np.sqrt(ppy)
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1.0).min()
    return dict(n=len(r), sharpe=sharpe, ann_ret=ann_ret, ann_vol=ann_vol, maxdd=float(dd))


def window_report(bt, hold_days=7, col="net"):
    """Full / OOS18 / REC12 (recent 12mo hard holdout) / PREV12 (independent 24->12mo)."""
    if bt.empty:
        return None
    end = bt.index.max()
    rec = end - pd.DateOffset(months=12)
    prev = end - pd.DateOffset(months=24)
    oos = end - pd.DateOffset(months=18)
    r = bt[col]
    return {
        "FULL": stats(r, hold_days),
        "OOS18": stats(r.loc[r.index >= oos], hold_days),
        "REC12": stats(r.loc[r.index >= rec], hold_days),
        "PREV12": stats(r.loc[(r.index >= prev) & (r.index < rec)], hold_days),
    }
