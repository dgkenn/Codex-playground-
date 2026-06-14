"""Deep-dive on OOS survivors: channel-breakout (Turtle) TS + weekly XS momentum.
Robustness: per-asset OOS, combined sleeve, capacity, 2x cost. (Uniquely named
to avoid colliding with branch-tracked files.)
"""
import os, glob, json, warnings
import numpy as np
import pandas as pd
warnings.simplefilter("ignore")

DATA = "/tmp/cx_momentum/data"
COST = 7.0 / 1e4
ANN = 365.0
IS_FRAC = 0.65


def load_daily():
    out = {}
    for fn in glob.glob(f"{DATA}/*_daily.parquet"):
        sym = os.path.basename(fn).split("_")[0]
        out[sym] = pd.read_parquet(fn).set_index("ts")
    return out


def perf(r):
    r = r.dropna()
    if len(r) < 10 or r.std() == 0:
        return dict(ann=np.nan, sharpe=np.nan, maxdd=np.nan, n=len(r))
    eq = (1 + r).cumprod()
    return dict(ann=float(eq.iloc[-1] ** (ANN / len(r)) - 1),
                sharpe=float(r.mean() / r.std() * np.sqrt(ANN)),
                maxdd=float((eq / eq.cummax() - 1).min()), n=int(len(r)))


def donchian_pos(close, lb):
    """Classic channel breakout: long on new lb-day high, flat on new lb-day low,
    hold between. Avoids the degenerate close==rolling-max formulation."""
    hi = close.rolling(lb).max()
    lo = close.rolling(lb).min()
    pos = pd.Series(np.nan, index=close.index)
    pos[close >= hi] = 1.0
    pos[close <= lo] = 0.0
    return pos.ffill().fillna(0.0)


def bt(close, pos, cost=COST):
    pos = pos.shift(1)
    gross = pos * close.pct_change()
    turn = pos.diff().abs().fillna(0)
    return gross - turn * cost, turn


data = load_daily()
common_start = max(df.index.min() for df in data.values())
print("Universe:", sorted(data.keys()))
print("Common-window start (BNB-limited):", common_start.date())
out = {}


def split_perf(series):
    idx = series.dropna().index
    k = int(len(idx) * IS_FRAC)
    return perf(series.loc[idx[:k]]), perf(series.loc[idx[k:]]), idx[k], idx[-1]


print("\n=== Channel-breakout TS (long/flat), per-asset OOS ===")
for lb in [20, 55]:
    nets, turns = {}, {}
    for sym, df in data.items():
        c = df["close"]
        net, turn = bt(c, donchian_pos(c, lb))
        nets[sym] = net
        turns[sym] = turn.mean()
    port = pd.concat(nets, axis=1, sort=True).mean(axis=1)
    is_r, oos_r, os0, os1 = split_perf(port)
    pa = {}
    for sym, net in nets.items():
        ii = net.dropna().index; kk = int(len(ii) * IS_FRAC)
        pa[sym] = round(perf(net.loc[ii[kk:]])['sharpe'], 2)
    avg_turn = float(np.mean(list(turns.values())))
    print(f"lb={lb}: IS Sharpe {is_r['sharpe']:.2f} | OOS Sharpe {oos_r['sharpe']:.2f} "
          f"ann {oos_r['ann']:.1%} maxDD {oos_r['maxdd']:.1%} | avg daily turnover {avg_turn:.3f} "
          f"(~{avg_turn*365:.0f} round-trips/yr/asset)")
    print("   per-asset OOS Sharpe:", pa)
    out[f"channel_lb{lb}"] = dict(is_sharpe=is_r['sharpe'], oos_sharpe=oos_r['sharpe'],
        oos_ann=oos_r['ann'], oos_maxdd=oos_r['maxdd'], avg_daily_turnover=avg_turn,
        per_asset_oos=pa, oos_window=f"{os0.date()}..{os1.date()}")

print("\n=== XS momentum, weekly rebalance ===")
closes = pd.concat({s: df["close"] for s, df in data.items()}, axis=1, sort=True).sort_index()
rets = closes.pct_change()


def xs_net(lb, cost=COST):
    mom = closes / closes.shift(lb) - 1
    rank = mom.rank(axis=1, pct=True)
    lw = (rank > 0.7).astype(float); sw = (rank < 0.3).astype(float)
    w = lw.div(lw.sum(axis=1).replace(0, np.nan), axis=0) - sw.div(sw.sum(axis=1).replace(0, np.nan), axis=0)
    w = w.fillna(0)
    hold = w.copy(); hold[~(np.arange(len(w)) % 7 == 0)] = np.nan; hold = hold.ffill()
    pos = hold.shift(1)
    turn = pos.diff().abs().sum(axis=1).fillna(0)
    return (pos * rets).sum(axis=1) - turn * cost, turn


for lb in [7, 14, 30]:
    net, turn = xs_net(lb)
    is_r, oos_r, os0, os1 = split_perf(net)
    print(f"lb={lb} weekly: IS {is_r['sharpe']:.2f} | OOS {oos_r['sharpe']:.2f} "
          f"ann {oos_r['ann']:.1%} maxDD {oos_r['maxdd']:.1%} | avg wk gross-turnover {turn[turn>0].mean():.2f}")
    out[f"xs_lb{lb}_wk"] = dict(is_sharpe=is_r['sharpe'], oos_sharpe=oos_r['sharpe'],
        oos_ann=oos_r['ann'], oos_maxdd=oos_r['maxdd'])

print("\n=== COMBINED 50/50 TS(channel-55) + XS(14d wk) ===")
ts_nets = {s: bt(df["close"], donchian_pos(df["close"], 55))[0] for s, df in data.items()}
ts_port = pd.concat(ts_nets, axis=1, sort=True).mean(axis=1)
xs14, _ = xs_net(14)
comb = pd.concat([ts_port, xs14], axis=1, sort=True).mean(axis=1)
is_r, oos_r, os0, os1 = split_perf(comb)
print(f"COMBINED: IS {is_r['sharpe']:.2f} | OOS {oos_r['sharpe']:.2f} "
      f"ann {oos_r['ann']:.1%} maxDD {oos_r['maxdd']:.1%} | OOS {os0.date()}..{os1.date()}")
out["combined"] = dict(is_sharpe=is_r['sharpe'], oos_sharpe=oos_r['sharpe'],
    oos_ann=oos_r['ann'], oos_maxdd=oos_r['maxdd'], oos_window=f"{os0.date()}..{os1.date()}")

print("\n=== Combined cost sensitivity ===")
for tag, cst in [("0bps", 0.0), ("1x(7)", 7/1e4), ("2x(14)", 14/1e4), ("3x(21)", 21/1e4)]:
    ts_n = {s: bt(df["close"], donchian_pos(df["close"], 55), cst)[0] for s, df in data.items()}
    tsp = pd.concat(ts_n, axis=1, sort=True).mean(axis=1)
    xsn, _ = xs_net(14, cst)
    cm = pd.concat([tsp, xsn], axis=1, sort=True).mean(axis=1)
    _, oos_r, _, _ = split_perf(cm)
    print(f"  cost {tag}: OOS Sharpe {oos_r['sharpe']:.2f} ann {oos_r['ann']:.1%}")
    out[f"combined_cost_{tag}"] = dict(oos_sharpe=oos_r['sharpe'], oos_ann=oos_r['ann'])

json.dump(out, open("/tmp/cx_momentum/momentum_deepdive.json", "w"), indent=2, default=str)
print("\nsaved momentum_deepdive.json")
