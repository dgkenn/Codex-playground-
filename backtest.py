"""Crypto trend/momentum backtest engine.

Realism lens: cloud bot, seconds-to-minutes latency (NOT HFT), modest capital.
Trend/momentum lives at hours-to-days horizons => latency irrelevant; scales
with capital on deep books. We test whether a costs-survivable edge survives OOS.

Conventions:
- Signal computed on close of bar t, position held over bar t->t+1 (next-bar
  execution; no look-ahead). Return of bar t+1 = c[t+1]/c[t]-1.
- Costs charged on |position change| each bar: round-trip taker ~6-10 bps.
  We model cost as COST_BPS * turnover where turnover = |pos_t - pos_{t-1}|.
- IS = first 65% of dates, OOS = last 35% (chronological).
"""
import os, glob, json
import numpy as np
import pandas as pd

DATA = "/tmp/cx_momentum/data"

# Round-trip taker cost in bps applied per unit of leverage turned over.
# Base case ~7bps round trip (3.5 bps each way OKX taker ~ 0.08-0.10%, plus a
# few bps slippage on size). We sweep 1x / 2x below.
COST_BPS_BASE = 7.0
IS_FRAC = 0.65
ANN = {"daily": 365.0, "hourly": 24 * 365.0}


def load(tag):
    out = {}
    for fn in glob.glob(f"{DATA}/*_{tag}.parquet"):
        sym = os.path.basename(fn).split("_")[0]
        df = pd.read_parquet(fn).set_index("ts")
        out[sym] = df
    return out


def perf(rets, periods_per_year):
    """Annualized stats from a per-bar net return series."""
    rets = rets.dropna()
    if len(rets) < 10 or rets.std() == 0:
        return dict(ann_ret=np.nan, sharpe=np.nan, maxdd=np.nan, n=len(rets))
    eq = (1 + rets).cumprod()
    ann_ret = eq.iloc[-1] ** (periods_per_year / len(rets)) - 1
    sharpe = rets.mean() / rets.std() * np.sqrt(periods_per_year)
    dd = (eq / eq.cummax() - 1).min()
    return dict(ann_ret=float(ann_ret), sharpe=float(sharpe), maxdd=float(dd), n=int(len(rets)))


def split(idx):
    n = len(idx)
    k = int(n * IS_FRAC)
    return idx[:k], idx[k:]


# ---------------- Time-series momentum signals ----------------

def sig_ret_sign(close, lb):
    """Long if trailing lb-bar return > 0."""
    return (close / close.shift(lb) - 1 > 0).astype(float)


def sig_ma(close, lb):
    """Long if price above lb-bar SMA."""
    return (close > close.rolling(lb).mean()).astype(float)


def sig_ma_cross(close, fast, slow):
    return (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float)


def sig_donchian(close, lb):
    """Breakout: long if close == rolling max of last lb (new high)."""
    hi = close.rolling(lb).max()
    return (close >= hi).astype(float)


def run_ts(close, sig, ppy, cost_bps, long_short=False):
    """sig in {0,1} computed from info up to close[t]. long_short maps 0->-1.
    Next-bar execution: position decided at t is held over bar t+1 and earns
    ret[t+1]=close[t+1]/close[t]-1. We shift the signal by 1 so pos[t] reflects
    the decision made at close[t-1], then multiply by the bar-t return."""
    pos = sig.copy()
    if long_short:
        pos = sig * 2 - 1
    pos = pos.shift(1)            # decision from prior close -> held this bar
    ret = close.pct_change()      # ret[t] = close[t]/close[t-1]-1 (this bar)
    gross = pos * ret
    turnover = pos.diff().abs().fillna(0)
    cost = turnover * (cost_bps / 1e4)
    net = gross - cost
    return net, pos, turnover


def vol_scale(close, pos, target_vol_ann, ppy, lb=30):
    """Scale position to target annualized vol using trailing realized vol."""
    rv = close.pct_change().rolling(lb).std() * np.sqrt(ppy)
    scale = (target_vol_ann / rv).clip(upper=3.0)  # cap leverage at 3x
    return pos * scale.shift(1)


def main():
    results = {"ts": [], "xs": [], "vol": [], "cost_sens": []}

    # ===== TIME-SERIES MOMENTUM (per-asset, then equal-weight portfolio) =====
    for tag in ["daily", "hourly"]:
        data = load(tag)
        if not data:
            continue
        ppy = ANN[tag]
        if tag == "daily":
            lookbacks = [1, 3, 7, 30, 60]
        else:
            lookbacks = [12, 24, 72, 168]  # 12h,1d,3d,7d in hours

        for ls in [False, True]:
            for fam, fn in [("ret", sig_ret_sign), ("ma", sig_ma), ("donchian", sig_donchian)]:
                for lb in lookbacks:
                    # build equal-weight portfolio across universe
                    nets = []
                    for sym, df in data.items():
                        c = df["close"]
                        s = fn(c, lb)
                        net, pos, _ = run_ts(c, s, ppy, COST_BPS_BASE, long_short=ls)
                        nets.append(net.rename(sym))
                    port = pd.concat(nets, axis=1).mean(axis=1)
                    is_idx, oos_idx = split(port.dropna().index)
                    r_is = perf(port.loc[is_idx], ppy)
                    r_oos = perf(port.loc[oos_idx], ppy)
                    r_all = perf(port, ppy)
                    results["ts"].append(dict(
                        tag=tag, signal=fam, lb=lb, mode=("LS" if ls else "LF"),
                        is_sharpe=r_is["sharpe"], oos_sharpe=r_oos["sharpe"],
                        all_sharpe=r_all["sharpe"], oos_ann=r_oos["ann_ret"],
                        oos_maxdd=r_oos["maxdd"]))

    # ===== CROSS-SECTIONAL MOMENTUM (rank universe) =====
    for tag in ["daily"]:
        data = load(tag)
        ppy = ANN[tag]
        closes = pd.concat({s: df["close"] for s, df in data.items()}, axis=1).sort_index()
        rets = closes.pct_change()
        for lb in [7, 14, 30, 60]:
            for reb in [1, 7]:  # daily / weekly rebalance
                mom = closes / closes.shift(lb) - 1
                # rank: top half long, bottom half short, equal weight
                rank = mom.rank(axis=1, pct=True)
                n_assets = closes.shape[1]
                long_w = (rank > 0.7).astype(float)
                short_w = (rank < 0.3).astype(float)
                w = long_w.div(long_w.sum(axis=1).replace(0, np.nan), axis=0) \
                    - short_w.div(short_w.sum(axis=1).replace(0, np.nan), axis=0)
                w = w.fillna(0)
                # rebalance only every `reb` bars (hold weights between)
                hold = w.copy()
                hold[~(np.arange(len(w)) % reb == 0)] = np.nan
                hold = hold.ffill()
                pos = hold.shift(1)  # next-bar execution
                gross = (pos * rets).sum(axis=1)
                turn = pos.diff().abs().sum(axis=1).fillna(0)
                cost = turn * (COST_BPS_BASE / 1e4)
                net = gross - cost
                is_idx, oos_idx = split(net.dropna().index)
                r_is = perf(net.loc[is_idx], ppy)
                r_oos = perf(net.loc[oos_idx], ppy)
                results["xs"].append(dict(
                    lb=lb, rebal=reb, is_sharpe=r_is["sharpe"],
                    oos_sharpe=r_oos["sharpe"], oos_ann=r_oos["ann_ret"],
                    oos_maxdd=r_oos["maxdd"]))

    # ===== VOL-SCALING (apply to best daily TS config family) =====
    data = load("daily")
    ppy = ANN["daily"]
    for lb in [30, 60]:
        for tv in [None, 0.4, 0.6]:  # None = no vol scaling
            nets = []
            for sym, df in data.items():
                c = df["close"]
                s = sig_ma(c, lb)
                base = s.shift(1)         # prior-close decision held this bar
                if tv is not None:
                    rv = c.pct_change().rolling(30).std() * np.sqrt(ppy)
                    scale = (tv / rv).clip(upper=3.0).shift(1)  # lagged vol
                    pos = base * scale
                else:
                    pos = base
                ret = c.pct_change()
                gross = pos * ret
                turn = pos.diff().abs().fillna(0)
                net = gross - turn * (COST_BPS_BASE / 1e4)
                nets.append(net.rename(sym))
            port = pd.concat(nets, axis=1).mean(axis=1)
            is_idx, oos_idx = split(port.dropna().index)
            r_oos = perf(port.loc[oos_idx], ppy)
            r_is = perf(port.loc[is_idx], ppy)
            results["vol"].append(dict(lb=lb, target_vol=tv,
                is_sharpe=r_is["sharpe"], oos_sharpe=r_oos["sharpe"],
                oos_ann=r_oos["ann_ret"], oos_maxdd=r_oos["maxdd"]))

    # ===== COST SENSITIVITY (best daily TS: MA family) sweep 0/1x/2x =====
    data = load("daily")
    ppy = ANN["daily"]
    for lb in [30, 60]:
        for mult, bps in [("0bps", 0.0), ("1x(7)", 7.0), ("2x(14)", 14.0)]:
            nets = []
            for sym, df in data.items():
                c = df["close"]
                s = sig_ma(c, lb)
                net, _, _ = run_ts(c, s, ppy, bps, long_short=False)
                nets.append(net.rename(sym))
            port = pd.concat(nets, axis=1).mean(axis=1)
            is_idx, oos_idx = split(port.dropna().index)
            r_oos = perf(port.loc[oos_idx], ppy)
            results["cost_sens"].append(dict(lb=lb, cost=mult,
                oos_sharpe=r_oos["sharpe"], oos_ann=r_oos["ann_ret"]))

    json.dump(results, open("/tmp/cx_momentum/results.json", "w"), indent=2)
    # print summaries
    for k in results:
        print(f"\n===== {k} =====")
        print(pd.DataFrame(results[k]).to_string(index=False))


if __name__ == "__main__":
    main()
