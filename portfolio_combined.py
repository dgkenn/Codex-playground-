#!/usr/bin/env python3
"""
portfolio_combined.py — build & optimize the COMBINED two-sleeve deployable book.

Reuses the LOCKED sleeve engines (NOT re-derived):
  SLEEVE A = etf_momentum.backtest(...)   DUAL+regime 6m K5 p=0.34   (ETF_MOMENTUM.md e3e2d57)
  SLEEVE B = trend_following.backtest_tf(...) inverse-when-down 6m vt0.10 (TREND_FOLLOWING.md 0350194)

Outputs the combination sweep, satellite tests, and the combined outcome distribution
(block-bootstrap). Driver for PORTFOLIO_COMBINED.md. All numbers NET of 3 bps/side.

Window: overlap 2007-06 -> 2026-06 (inverse-ETF / UUP binder). Recent OOS holdout 2016-01+.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

from etf_momentum import load_prices, backtest as xs_bt, stats as _stats, CORE_UNIVERSE
from trend_following import load_long, load_inv, backtest_tf, combine

TD = 252
OVERLAP = "2007-06-01"
HOLDOUT = "2016-01-01"

# ----------------------------------------------------------------------------
def stats(net, freq=TD):
    return _stats(net, freq)

def sleeve_A(start=None, end=None, crypto=False):
    uni = list(CORE_UNIVERSE) + (["GBTC","MSTR","COIN","IBIT"] if crypto else [])
    px = load_prices()
    net,_ = xs_bt(px, uni, lookback_days=126, K=5, risk_adj=True, dual=True,
                  regime=True, partial=0.34, start=start, end=end)
    return net

def sleeve_B(start=None, end=None, down="inverse"):
    lp, ip = load_long(), load_inv()
    net,_ = backtest_tf(lp, ip, lookback_days=126, mode="trend", down=down,
                        vol_target=0.10, start=start, end=end)
    return net

# ---- combine N streams (monthly reset to target weights) -------------------
def combine_n(streams, weights):
    """streams: list of daily-return Series. weights: list summing to 1.
    Monthly reset; drift within month. Returns combined daily net series on overlap."""
    df = pd.concat([s.rename(i) for i,s in enumerate(streams)], axis=1, join="inner").dropna()
    idx = df.index
    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    reset = set(pd.Timestamp(d) for d in me.values)
    w0 = np.array(weights, float); w = w0.copy()
    R = df.values
    out = np.empty(len(idx))
    for i in range(len(idx)):
        out[i] = float(np.dot(w, R[i]))
        w = w * (1 + R[i])
        s = w.sum()
        if s != 0: w = w/s
        if idx[i] in reset: w = w0.copy()
    return pd.Series(out, index=idx).dropna()

def inv_vol_weights(streams):
    v = np.array([s.std() for s in streams])
    iv = 1.0/v
    return (iv/iv.sum()).tolist()

# ---- vol-targeted combo: scale a base combo's gross to hit target vol -------
def vol_target_combo(streams, weights, target_vol=0.10, win=63, max_lev=1.5):
    base = combine_n(streams, weights)
    rv = base.rolling(win).std()*np.sqrt(TD)
    scaler = (target_vol/rv).clip(upper=max_lev).shift(1).fillna(1.0)
    return (base*scaler).dropna()

# block bootstrap ------------------------------------------------------------
def block_bootstrap(net, n_paths=4000, horizon_days=TD, block=21, haircut=0.30, seed=7):
    """Resample daily returns in blocks; haircut the MEAN (drift) by `haircut`.
    Returns array of terminal wealth multiples and per-path maxDD."""
    rng = np.random.default_rng(seed)
    r = net.dropna().values
    mu = r.mean()
    r_adj = r - haircut*mu   # haircut drift only, keep vol/shape
    n = len(r_adj)
    nblk = int(np.ceil(horizon_days/block))
    tw = np.empty(n_paths); mdd = np.empty(n_paths); under = np.empty(n_paths)
    for p in range(n_paths):
        starts = rng.integers(0, n-block, size=nblk)
        path = np.concatenate([r_adj[s:s+block] for s in starts])[:horizon_days]
        eq = np.cumprod(1+path)
        tw[p] = eq[-1]
        peak = np.maximum.accumulate(eq)
        dd = eq/peak - 1
        mdd[p] = dd.min()
        under[p] = (eq < 1.0).mean()  # fraction of time below start
    return tw, mdd, under
