"""Regime / crowding-timing overlay on the LOCKED best-config crypto momentum strategy.

LOCKED BASE STRATEGY (from sibling MOM_SIGNAL.md, not re-derived here):
  risk-adjusted 10d momentum, top-15 liquid USDT perps, equal/rank weight,
  dollar-neutral long-top-30%/short-bottom-30%, WEEKLY rebalance, 9bps/side.

THIS MODULE: builds REGIME SIGNALS (observable at rebalance time t, no lookahead)
and applies a position-scaling overlay g(t) in {scale book to 0..1, or flip}.
We compute the base book ONCE, then re-weight each rebalance's net return by the
regime gate decided from data up to t (the gate uses info available BEFORE the
forward holding period -> no lookahead).

OOS PROTOCOL (matches sibling):
  - IS  = everything before last 18 months  -> choose gate thresholds here only.
  - OOS18 = last 18 months (hard holdout).
  - REC12 = last 12 months (headline recent regime).
  - PREV12 = 24->12 months ago (independent confirmation window).
  Sharpe annualized x sqrt(52). Costs already in base net; gate scaling also
  re-scales the turnover cost (a scaled-down book trades less => less cost), and
  changing the gate level itself incurs turnover (gate transition cost modeled).
"""
import numpy as np
import pandas as pd
import mom_backtest as mb

mb.DATA = "/tmp/regime_data/mom_data.parquet"


# ----------------------------------------------------------------------------
# Base strategy: run once, keep per-rebalance gross/net/turnover AND the weights
# so we can recompute cost when the gate scales the book.
# ----------------------------------------------------------------------------
def base_book(px, vol, fn, lb=10, top_n=15, frac=0.30, scheme="equal",
              cost_bps=9.0, hold_days=7):
    """Return per-rebalance DataFrame: date(=exit), t(=entry), gross, turnover_raw."""
    dates = px.index
    rb_dates = dates[::hold_days]
    recs = []
    prev_w = None
    for i, t in enumerate(rb_dates[:-1]):
        nxt = rb_dates[i + 1]
        univ = mb.liquid_universe(vol, t, top_n)
        if len(univ) < 4:
            continue
        sig = fn(px, t, lb)
        if sig is None:
            continue
        w = mb.weights(sig, univ, frac=frac, scheme=scheme, vol_panel=vol, px=px, t=t)
        if w is None:
            continue
        p_now = px.loc[t]; p_nxt = px.loc[nxt]
        fwd = (p_nxt / p_now - 1.0).reindex(w.index)
        gross = float((w * fwd).sum(skipna=True))
        if prev_w is None:
            turn = w.abs().sum()
        else:
            allk = w.index.union(prev_w.index)
            turn = (w.reindex(allk).fillna(0) - prev_w.reindex(allk).fillna(0)).abs().sum()
        recs.append({"entry": t, "date": nxt, "gross": gross, "turn_raw": turn,
                     "cost_bps": cost_bps})
        prev_w = w
    bt = pd.DataFrame(recs).set_index("date")
    bt["net_base"] = bt["gross"] - bt["turn_raw"] * (cost_bps / 1e4)
    return bt


def apply_gate(bt, gate, cost_bps=9.0):
    """gate: pd.Series indexed by ENTRY date in [-1,1] (1=full long book, 0=flat, -1=flip).
    Re-scales gross by gate, and turnover/cost by the change in (gate*book) between rebalances.
    Approx: scaled position = gate_t * base_weights_t. Turnover of scaled book is bounded by
    gate_t*turn_raw + |gate_t - gate_{t-1}| * 1.0 (gross of one side ~1). We model:
      net = gate*gross - (|gate_t|*turn_raw + |gate_t-gate_prev|*2) * cost.
    The 2.0 = full gross (long+short=2) churned when the gate level moves."""
    entries = pd.DatetimeIndex(bt["entry"].values)
    gate = gate.sort_index()
    gate.index = pd.DatetimeIndex(gate.index).tz_localize(None)
    entries = entries.tz_localize(None) if entries.tz is not None else entries
    g = gate.reindex(entries, method="ffill").values
    g = pd.Series(g).ffill().fillna(0.0).values
    gprev = np.concatenate([[0.0], g[:-1]])
    gross = bt["gross"].values
    turn_raw = bt["turn_raw"].values
    scaled_gross = g * gross
    cost = (np.abs(g) * turn_raw + np.abs(g - gprev) * 2.0) * (cost_bps / 1e4)
    net = scaled_gross - cost
    out = bt.copy()
    out["gate"] = g
    out["net"] = net
    return out


# ----------------------------------------------------------------------------
# REGIME SIGNALS — all computed from panel up to entry date t (no lookahead)
# Returned as a Series indexed by every panel date; gate logic samples at entry.
# ----------------------------------------------------------------------------
def btc_realized_vol(px, win=20):
    """Annualized BTC realized vol from daily returns."""
    r = px["BTC"].pct_change()
    return r.rolling(win).std() * np.sqrt(365)


def basket_realized_vol(px, win=20):
    r = px.pct_change()
    return r.rolling(win).std().mean(axis=1) * np.sqrt(365)


def xs_dispersion(px, lb=10, win=1):
    """Cross-sectional std of trailing lb-day returns (the spread momentum feeds on)."""
    ret = px / px.shift(lb) - 1.0
    return ret.std(axis=1)


def btc_trend(px, ma=100):
    """BTC above/below long MA: (price/MA - 1). >0 = uptrend (risk-on)."""
    return px["BTC"] / px["BTC"].rolling(ma).mean() - 1.0


def breadth(px, lb=10):
    """Fraction of universe with positive trailing lb-day return."""
    ret = px / px.shift(lb) - 1.0
    return (ret > 0).sum(axis=1) / ret.notna().sum(axis=1)


def funding_level(funding_daily):
    """Aggregate (cross-sectional mean) daily funding rate. High = crowded long."""
    return funding_daily.mean(axis=1)


def funding_dispersion(funding_daily):
    return funding_daily.std(axis=1)


# Own-equity regime: rolling Sharpe / drawdown of the strategy's own net returns.
# Uses ONLY returns realized strictly before entry t (shifted) -> no lookahead.
def own_rolling_sharpe(net_series, win=8):
    rs = net_series.rolling(win).mean() / net_series.rolling(win).std()
    return rs.shift(1)  # only info up to the rebalance BEFORE entry


def own_drawdown(net_series, win=12):
    eq = (1 + net_series).cumprod()
    dd = eq / eq.cummax() - 1.0
    return dd.shift(1)


# ----------------------------------------------------------------------------
# Stats / windows
# ----------------------------------------------------------------------------
def gate_from_threshold(level_series, thr, mode="above_on", scale_zero=0.0):
    """Binary gate from a level series. mode: above_on / below_on / above_flip / below_flip."""
    lv = level_series.copy()
    if mode == "above_on":
        g = (lv >= thr).astype(float)
        g[lv < thr] = scale_zero
    elif mode == "below_on":
        g = (lv < thr).astype(float)
        g[lv >= thr] = scale_zero
    elif mode == "above_flip":
        g = pd.Series(np.where(lv >= thr, 1.0, -1.0), index=lv.index)
    elif mode == "below_flip":
        g = pd.Series(np.where(lv < thr, 1.0, -1.0), index=lv.index)
    return g


def stats(r):
    return mb.stats(r)


def maxdd(r):
    eq = (1 + r).cumprod()
    return float((eq / eq.cummax() - 1).min())


def windows(bt):
    end = bt.index.max()
    return {
        "FULL": (None, None),
        "IS": (None, end - pd.DateOffset(months=18)),
        "OOS18": (end - pd.DateOffset(months=18), None),
        "REC12": (end - pd.DateOffset(months=12), None),
        "PREV12": (end - pd.DateOffset(months=24), end - pd.DateOffset(months=12)),
    }


def slc(bt, s, e, col="net"):
    r = bt[col]
    if s is not None: r = r.loc[r.index >= s]
    if e is not None: r = r.loc[r.index < e]
    return r


def report(label, bt, base=None):
    w = windows(bt)
    parts = []
    for k in ("FULL", "OOS18", "REC12", "PREV12"):
        r = slc(bt, *w[k])
        st = stats(r)
        parts.append(f"{k} {st['sharpe']:+.2f}")
    dd = maxdd(slc(bt, *w["OOS18"]))
    exp = bt.loc[bt.index >= bt.index.max() - pd.DateOffset(months=12), "gate"].abs().mean() if "gate" in bt else 1.0
    print(f"{label:32s} " + " | ".join(parts) + f" | OOS18 maxDD {dd*100:+.0f}% | rec exposure {exp:.2f}")
