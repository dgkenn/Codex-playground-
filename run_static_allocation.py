#!/usr/bin/env python3
"""Driver: head-to-head static portfolios vs the active momentum + 70/30 TF combo book.

Full-sample window is set by the latest static-asset inception (DBC 2006-02, BIL 2007-05)
so every portfolio sees the same period -> common start 2007-06 (this also = the TF overlap
window, so the active combo is on equal footing).  Recent-decade holdout 2016-01.

Also reports:
  - SPY-only and 60/40 from their longer histories (context, not equal-footing).
  - Quarterly-rebalance variant for statics (cheaper / less effort).
  - Leverage angle: 1.4x margin on the best static, and a levered risk-parity, with honest
    margin-cost and amplified-DD modelling.
All net of 3 bps/side.
"""
import numpy as np, pandas as pd
from static_allocation import (load_all, run_statics, fixed_weight_port,
                               inverse_vol_port, stats, RISKPARITY, STATICS)
from etf_momentum import backtest as xs_backtest, CORE_UNIVERSE, load_prices
from trend_following import load_inv, backtest_tf, combine

pd.set_option("display.width", 200, "display.max_columns", 40)

px   = load_all()
lp   = load_prices()
ip   = load_inv()

COMMON_START = "2007-06-01"   # all-static-asset inception-limited full sample (= TF overlap)
HOLD_START   = "2016-01-01"

MARGIN_RATE = 0.045   # annual broker margin / financing cost for the leverage section (honest, ~current)


def winner(start=None, end=None):
    net, _ = xs_backtest(lp, CORE_UNIVERSE, lookback_days=126, K=5, risk_adj=True,
                         dual=True, regime=True, partial=0.34, start=start, end=end)
    return net


def active_combo(start):
    tf_inv, _ = backtest_tf(lp, ip, lookback_days=126, mode="trend", down="inverse",
                            vol_target=0.10, start=start)
    w = winner(start)
    return combine(w, tf_inv, 0.70, 0.30)


def fmt(name, s):
    return dict(strategy=name,
                CAGR=f"{s['CAGR']*100:.1f}%",
                Sharpe=f"{s['Sharpe']:.2f}",
                maxDD=f"{s['maxDD']*100:.1f}%",
                worst_yr=f"{s['worst_yr']*100:.1f}%" if not np.isnan(s['worst_yr']) else "n/a",
                vol=f"{s['vol']*100:.1f}%")


def table(start, end=None, rebal="M", label=""):
    rows = []
    st = run_statics(px, start, end, rebal=rebal)
    for name, (net, s) in st.items():
        rows.append(fmt(name, s))
    # active book
    w = winner(start, end)
    rows.append(fmt("ACTIVE: ETF momentum", stats(w)))
    combo = active_combo(start)
    if end:
        combo = combo[combo.index <= pd.Timestamp(end)]
    rows.append(fmt("ACTIVE: 70/30 mom+TF", stats(combo)))
    df = pd.DataFrame(rows)
    print(f"\n{'='*96}\n{label}\n{'='*96}")
    print(df.to_string(index=False))
    return st, w, combo


def levered_series(net, lev, margin_rate=MARGIN_RATE):
    """Apply lev on a daily net return series; charge financing on the borrowed (lev-1) part.
    Amplifies returns AND drawdowns honestly. Simple constant-leverage (daily reset) model --
    this also captures volatility decay from daily rebalancing, like an LETF."""
    borrow = (lev - 1.0) * margin_rate / 252
    return lev * net - borrow


if __name__ == "__main__":
    print("data:", px.index.min().date(), "->", px.index.max().date(),
          "| common full start:", COMMON_START, "| holdout:", HOLD_START,
          "| costs: 3 bps/side; margin", MARGIN_RATE)

    # ---- context: long histories (NOT equal footing -- different windows) ----
    print("\n" + "#"*96)
    print("# CONTEXT (longer histories, unequal windows -- shown for reference only)")
    print("#"*96)
    ctx = []
    spy_full = fixed_weight_port(px, {"SPY":1.0}, start="2000-06-01")
    ctx.append(fmt("100% SPY (2000-2026)", stats(spy_full)))
    s6040 = fixed_weight_port(px, {"SPY":0.6,"AGG":0.4}, start="2003-10-01")
    ctx.append(fmt("60/40 SPY/AGG (2003-2026)", stats(s6040)))
    w_full = winner("2000-06-01")
    ctx.append(fmt("ACTIVE momentum (2000-2026)", stats(w_full)))
    print(pd.DataFrame(ctx).to_string(index=False))

    # ---- EQUAL-FOOTING full sample 2007-2026 (monthly) ----
    st_full, w_full2, combo_full = table(COMMON_START, None, "M",
        "FULL SAMPLE 2007-06 -> 2026-06  (equal footing, monthly rebalance, net 3bps/side)")

    # ---- holdout 2016-2026 (monthly) ----
    st_hold, w_hold, combo_hold = table(HOLD_START, None, "M",
        "RECENT-DECADE HOLDOUT 2016-01 -> 2026-06  (OOS, monthly rebalance, net 3bps/side)")

    # ---- quarterly variant (statics only, cheaper/less effort) ----
    print(f"\n{'='*96}\nSTATICS QUARTERLY rebalance (full 2007-2026) -- less effort, lower turnover\n{'='*96}")
    rows=[]
    stq = run_statics(px, COMMON_START, None, rebal="Q")
    for name,(net,s) in stq.items():
        rows.append(fmt(name+" (Q)", s))
    print(pd.DataFrame(rows).to_string(index=False))

    # ---- LEVERAGE ANGLE ----
    print(f"\n{'='*96}\nLEVERAGE ANGLE -- levered static vs unlevered active book ({MARGIN_RATE*100:.1f}% margin, daily-reset)\n{'='*96}")
    # pick best-Sharpe static full sample
    best_name = max(st_full, key=lambda n: st_full[n][1]['Sharpe'])
    best_net  = st_full[best_name][0]
    rp_net    = st_full["Risk-Parity (inv-vol)"][0]
    lev_rows=[]
    lev_rows.append(fmt(f"{best_name} (1.0x)", stats(best_net)))
    for L in [1.2, 1.4, 1.6]:
        lev_rows.append(fmt(f"{best_name} ({L}x)", stats(levered_series(best_net, L))))
    lev_rows.append(fmt("Risk-Parity (1.0x)", stats(rp_net)))
    for L in [1.4, 1.8, 2.0]:
        lev_rows.append(fmt(f"Risk-Parity ({L}x)", stats(levered_series(rp_net, L))))
    lev_rows.append(fmt("ACTIVE 70/30 mom+TF (1.0x)", stats(combo_full)))
    print(pd.DataFrame(lev_rows).to_string(index=False))

    print(f"\n--- leverage on holdout 2016-2026 ---")
    best_h = st_hold[best_name][0]; rp_h = st_hold["Risk-Parity (inv-vol)"][0]
    lev_rows=[]
    for L in [1.0,1.4]:
        lev_rows.append(fmt(f"{best_name} ({L}x)", stats(levered_series(best_h,L))))
    for L in [1.0,1.8]:
        lev_rows.append(fmt(f"Risk-Parity ({L}x)", stats(levered_series(rp_h,L))))
    lev_rows.append(fmt("ACTIVE 70/30 mom+TF", stats(combo_hold)))
    print(pd.DataFrame(lev_rows).to_string(index=False))
