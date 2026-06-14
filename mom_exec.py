"""EXECUTION / TURNOVER / CAPACITY study for cross-sectional crypto momentum.

Reuses the sibling signal engine (mom_backtest.py): risk-adjusted ~10d momentum,
top-15 liquid USDT perps, dollar-neutral long-top-30%/short-bottom-30%, equal/rank weight.
This module adds:
  1. Rebalance-frequency sweep (daily/2x-wk/weekly/biweekly/monthly): turnover, gross/net Sharpe.
  2. Turnover reduction: no-trade rank bands (hysteresis), EMA signal smoothing, partial rebalance.
  3. Capacity curve: live OKX book depth (walk-the-book slippage vs size) x turnover -> net Sharpe(AUM).

Window: OKX daily candles 2020-01-01 -> 2026-06-13. Holdout = recent 12mo (REC12) headline,
plus prior-12mo (PREV12) and OOS18 for robustness. Sharpe annualized by sqrt(bars/yr).
Base cost in the frequency sweep = 10 bps round-trip per unit |Δw| (= 5 bps/side taker+slip),
mid-range of the 7-12bps bar. Capacity section replaces this flat cost with the live book curve.
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/mom_exec")
import mom_backtest as mb

DATA = "/tmp/mom_signal/mom_data.parquet"
BOOK = "/tmp/exec_data/book_depth.json"
FUND = "/tmp/exec_data/funding.json"
META = "/tmp/exec_data/meta.json"

LB = 10
TOP_N = 15
FRAC = 0.30
SCHEME = "equal"
BASE_COST_BPS = 10.0   # round-trip per unit |Δw| (turnover already counts both legs' churn)

# ---------- core: parametrized weekly-style backtest with turnover-reduction hooks ----------

def build_weights(px, vol, t, lb=LB, top_n=TOP_N, frac=FRAC, scheme=SCHEME,
                  prev_w=None, band=0.0, ema_state=None, ema_alpha=None):
    """Return (target_weights, ema_state). Supports:
       - EMA smoothing of the raw signal (ema_alpha in (0,1]; None = no smoothing).
       - No-trade band hysteresis: a name currently held stays held unless it leaves the
         (frac+band) tail; a new name only enters if it is inside the (frac-band) core tail.
    """
    sig = mb.sig_riskadj(px, t, lb)
    if sig is None:
        return None, ema_state
    univ = mb.liquid_universe(vol, t, top_n)
    s = sig.reindex(univ).dropna()
    if len(s) < 4:
        return None, ema_state

    # EMA smoothing on cross-sectional rank score (pct rank, comparable across dates)
    score = s.rank(pct=True)
    if ema_alpha is not None:
        st = {} if ema_state is None else dict(ema_state)
        new = {}
        for k, v in score.items():
            prev = st.get(k, v)
            new[k] = ema_alpha * v + (1 - ema_alpha) * prev
        ema_state = new
        score = pd.Series({k: new[k] for k in score.index})

    n_side = max(1, int(round(len(score) * frac)))
    ranked = score.sort_values()
    base_short = set(ranked.index[:n_side])
    base_long = set(ranked.index[-n_side:])

    if band > 0 and prev_w is not None:
        n_keep = max(1, int(round(len(score) * (frac + band))))
        n_enter = max(1, int(round(len(score) * max(0.05, frac - band))))
        keep_short = set(ranked.index[:n_keep])
        keep_long = set(ranked.index[-n_keep:])
        enter_short = set(ranked.index[:n_enter])
        enter_long = set(ranked.index[-n_enter:])
        held_long = {c for c in prev_w.index if prev_w[c] > 0}
        held_short = {c for c in prev_w.index if prev_w[c] < 0}
        longs = (held_long & keep_long) | enter_long
        shorts = (held_short & keep_short) | enter_short
        # cap to n_side each side by strongest score
        longs = set(score[list(longs)].sort_values().index[-n_side:]) if len(longs) > n_side else longs
        shorts = set(score[list(shorts)].sort_values().index[:n_side]) if len(shorts) > n_side else shorts
        longs -= shorts
    else:
        longs, shorts = base_long, base_short

    w = pd.Series(0.0, index=score.index)
    if scheme == "equal":
        if longs: w[list(longs)] = 1.0 / len(longs)
        if shorts: w[list(shorts)] = -1.0 / len(shorts)
    else:  # rank
        r = score.rank(pct=True) - 0.5
        rl = r[list(longs)].clip(lower=1e-6); rs = (-r[list(shorts)]).clip(lower=1e-6)
        if len(longs): w[list(longs)] = rl / rl.sum()
        if len(shorts): w[list(shorts)] = -(rs / rs.sum())
    return w, ema_state


def backtest(px, vol, hold_days=7, lb=LB, top_n=TOP_N, frac=FRAC, scheme=SCHEME,
             cost_bps=BASE_COST_BPS, band=0.0, ema_alpha=None, partial=1.0,
             cost_fn=None):
    """Generic rebalance backtest with turnover-reduction hooks.
       partial: fraction of the gap toward target traded each rebalance (1.0 = full).
       cost_fn(turnover_per_coin_series, w_target) -> cost (fraction) ; if None use flat cost_bps.
    """
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    cur_w = None          # actual book held
    ema_state = None
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        tw, ema_state = build_weights(px, vol, t, lb, top_n, frac, scheme,
                                      prev_w=cur_w, band=band,
                                      ema_state=ema_state, ema_alpha=ema_alpha)
        if tw is None:
            continue
        if cur_w is None:
            new_w = tw.copy()
        else:
            idx = tw.index.union(cur_w.index)
            a = cur_w.reindex(idx).fillna(0.0)
            b = tw.reindex(idx).fillna(0.0)
            new_w = a + partial * (b - a)
        # turnover this rebalance (per-coin |Δ|)
        if cur_w is None:
            dchg = new_w.abs()
        else:
            idx = new_w.index.union(cur_w.index)
            dchg = (new_w.reindex(idx).fillna(0.0) - cur_w.reindex(idx).fillna(0.0)).abs()
        turnover = float(dchg.sum())
        if cost_fn is None:
            cost = turnover * cost_bps / 1e4
        else:
            cost = cost_fn(dchg, new_w)
        # forward return
        fwd = (px.loc[nxt] / px.loc[t] - 1.0).reindex(new_w.index)
        gross = float((new_w * fwd).sum(skipna=True))
        recs.append({"date": nxt, "gross": gross, "net": gross - cost,
                     "turnover": turnover, "cost": cost})
        cur_w = new_w
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


def windows(bt, hold_days):
    ppy = 365.0 / hold_days
    if bt.empty:
        return None
    end = bt.index.max()

    def sh(r):
        if len(r) < 5 or r.std() == 0:
            return np.nan
        return r.mean() / r.std() * np.sqrt(ppy)
    rec_start = end - pd.DateOffset(months=12)
    prev_start = end - pd.DateOffset(months=24)
    oos_start = end - pd.DateOffset(months=18)
    rec = bt.loc[bt.index >= rec_start]
    prev = bt.loc[(bt.index >= prev_start) & (bt.index < rec_start)]
    oos = bt.loc[bt.index >= oos_start]
    return {
        "n": len(bt), "turn": bt["turnover"].mean(),
        "gross_full": sh(bt["gross"]), "net_full": sh(bt["net"]),
        "net_oos18": sh(oos["net"]),
        "gross_rec12": sh(rec["gross"]), "net_rec12": sh(rec["net"]),
        "net_prev12": sh(prev["net"]),
        "ann_rec12": rec["net"].mean() * (365.0 / hold_days),
    }


if __name__ == "__main__":
    px, vol = mb.load_panel()
    print("panel", px.shape, px.index.min().date(), px.index.max().date())

    FREQS = [("daily", 1), ("2x-week", 3), ("weekly", 7), ("biweekly", 14), ("monthly", 30)]

    print("\n=== 1. REBALANCE FREQUENCY SWEEP (riskadj-10d, top15, eq, 30% tails, 10bps RT) ===")
    print(f"{'cadence':9} {'turn':>6} {'grossRC12':>9} {'netRC12':>8} {'netOOS18':>9} {'netPREV12':>9} {'annRC12':>8}")
    for name, hd in FREQS:
        bt = backtest(px, vol, hold_days=hd)
        w = windows(bt, hd)
        print(f"{name:9} {w['turn']:6.2f} {w['gross_rec12']:9.2f} {w['net_rec12']:8.2f} "
              f"{w['net_oos18']:9.2f} {w['net_prev12']:9.2f} {w['ann_rec12']*100:7.1f}%")

    print("\n=== 2. TURNOVER REDUCTION (weekly, riskadj-10d) ===")
    print("baseline weekly:")
    base = windows(backtest(px, vol, hold_days=7), 7)
    print(f"  turn {base['turn']:.2f}  netRC12 {base['net_rec12']:.2f}  netPREV12 {base['net_prev12']:.2f}  netOOS18 {base['net_oos18']:.2f}")
    print(f"{'method':28} {'turn':>6} {'netRC12':>8} {'netPREV12':>9} {'netOOS18':>9}")
    variants = [
        ("no-trade band 0.07", dict(band=0.07)),
        ("no-trade band 0.13", dict(band=0.13)),
        ("no-trade band 0.20", dict(band=0.20)),
        ("EMA smooth a=0.6", dict(ema_alpha=0.6)),
        ("EMA smooth a=0.4", dict(ema_alpha=0.4)),
        ("partial 0.5", dict(partial=0.5)),
        ("partial 0.7", dict(partial=0.7)),
        ("band0.13 + EMA0.5", dict(band=0.13, ema_alpha=0.5)),
        ("band0.13 + partial0.7", dict(band=0.13, partial=0.7)),
    ]
    for nm, kw in variants:
        w = windows(backtest(px, vol, hold_days=7, **kw), 7)
        print(f"{nm:28} {w['turn']:6.2f} {w['net_rec12']:8.2f} {w['net_prev12']:9.2f} {w['net_oos18']:9.2f}")
