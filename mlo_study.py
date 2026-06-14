"""LONG-ONLY US-SPOT momentum study: build, compare, gate-test, fee/bankroll realism, verdict.

Run: python3 mlo_study.py    (prints all tables; MOM_LONGONLY.md is written by hand from these)
Window: Coinbase USD daily 2019-2026. REC12 = recent-12mo HARD holdout. PREV12 = independent
24->12mo slice. Costs realistic US-spot (40bps RT base; 20/60 sensitivity). Backtests SCREEN.
"""
import numpy as np, pandas as pd
import mlo_backtest as mb

spx, svol = mb.load_spot()
ppx, pvol = mb.load_perp()
POOL = list(spx.columns)  # US-spot tradeable universe (Coinbase USD)

print(f"SPOT panel: {spx.shape[1]} coins, {spx.index.min().date()} -> {spx.index.max().date()}")
print(f"PERP panel: {ppx.shape[1]} coins, {ppx.index.min().date()} -> {ppx.index.max().date()}")
print(f"US-spot pool: {POOL}\n")

HD = 7
def line(label, rep, turn=None):
    if rep is None:
        print(f"{label:42s}  (empty)"); return
    f, o, r, p = rep["FULL"], rep["OOS18"], rep["REC12"], rep["PREV12"]
    t = f" turn{turn:.2f}" if turn is not None else ""
    print(f"{label:42s} FULL Sh{f['sharpe']:+.2f} ret{f['ann_ret']*100:+5.0f}% dd{f['maxdd']*100:+5.0f}% | "
          f"OOS18 Sh{o['sharpe']:+.2f} | REC12 Sh{r['sharpe']:+.2f} ret{r['ann_ret']*100:+5.0f}% dd{r['maxdd']*100:+5.0f}% | "
          f"PREV12 Sh{p['sharpe']:+.2f}{t}")

# ============================================================
print("="*60); print("1. LONG-ONLY K-SWEEP (riskadj-10d, top-15 univ, weekly, partial0.7, 40bps, gate100)"); print("="*60)
for k in [3, 5, 7, 0.30, 0.50]:
    bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=k, cost_bps=40, partial=0.7, gate_ma=100, univ_pool=POOL)
    line(f"LO k={k}", mb.window_report(bt, HD), bt["turnover"].mean() if not bt.empty else None)

print("\n--- ungated (no BTC gate) for the same K, to isolate the gate's value ---")
for k in [3, 5, 0.30]:
    bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=k, cost_bps=40, partial=0.7, gate_ma=None, univ_pool=POOL)
    line(f"LO k={k} UNGATED", mb.window_report(bt, HD), bt["turnover"].mean() if not bt.empty else None)

# ============================================================
print("\n"+"="*60); print("2. GATE VARIANTS (LO k=5, top-15, 40bps, partial0.7) -- maxDD control"); print("="*60)
for g in [None, 50, 75, 100, 150, 200]:
    bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=5, cost_bps=40, partial=0.7, gate_ma=g, univ_pool=POOL)
    rep = mb.window_report(bt, HD)
    pct_cash = bt["gated"].mean()*100 if not bt.empty else float('nan')
    g_lbl = "none" if g is None else str(g)
    line(f"gate MA={g_lbl} (cash {pct_cash:.0f}% of wks)", rep)

# ============================================================
print("\n"+"="*60); print("3. BENCHMARKS (same US-spot pool, weekly, 2019-2026)"); print("="*60)
# (a) L/S dollar-neutral on PERP universe (the validated lost edge, perp panel, 9bps perp cost)
bt = mb.backtest_ls(ppx, pvol, lb=10, top_n=15, frac=0.30, cost_bps=9, partial=0.7, gate_ma=100)
line("(a) L/S NEUTRAL perp top15 gate100 9bps [VALIDATED]", mb.window_report(bt, HD))
# (a') L/S on US-SPOT pool, charged spot fees (what a US person could do if they COULD short -- they can't)
bt = mb.backtest_ls(spx, svol, lb=10, top_n=15, frac=0.30, cost_bps=40, partial=0.7, gate_ma=100, univ_pool=POOL)
line("(a') L/S NEUTRAL spot-pool gate100 40bps [hypothetical]", mb.window_report(bt, HD))
# (b) EW buy-hold universe
bt = mb.ew_buyhold(spx, svol, top_n=15, univ_pool=POOL)
line("(b) EW buy-hold top15 universe", mb.window_report(bt, HD))
# (c) BTC buy-hold
bt = mb.asset_buyhold(spx, "BTC")
line("(c) BTC buy-hold", mb.window_report(bt, HD))
# (d) cash = 0 by construction (Sharpe 0, ret 0, dd 0)
print(f"{'(d) cash (USDC)':42s} FULL Sh +0.00 ret  +0% dd  +0% | (return 0, dd 0 by construction)")

# ============================================================
print("\n"+"="*60); print("4. FEE SENSITIVITY (LO k=5, top-15, gate100, partial0.7)"); print("="*60)
for c in [20, 30, 40, 50, 60]:
    bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=5, cost_bps=c, partial=0.7, gate_ma=100, univ_pool=POOL)
    line(f"RT cost = {c}bps", mb.window_report(bt, HD))
print("\n--- partial-rebalance sensitivity (lower turnover -> lower fee drag) at 40bps ---")
for pr in [0.5, 0.7, 1.0]:
    bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=5, cost_bps=40, partial=pr, gate_ma=100, univ_pool=POOL)
    line(f"partial={pr}", mb.window_report(bt, HD), bt["turnover"].mean() if not bt.empty else None)

# ============================================================
print("\n"+"="*60); print("5. LOOKBACK PLATEAU (LO k=5, top-15, gate100, partial0.7, 40bps)"); print("="*60)
for lb in [7, 8, 10, 12, 14]:
    bt = mb.backtest_lo(spx, svol, lb=lb, top_n=15, k=5, cost_bps=40, partial=0.7, gate_ma=100, univ_pool=POOL)
    line(f"lb={lb}d", mb.window_report(bt, HD))

# ============================================================
print("\n"+"="*60); print("6. SMALL-BANKROLL REALISM (fees scale, min-order sizes)"); print("="*60)
# Headline config
bt = mb.backtest_lo(spx, svol, lb=10, top_n=15, k=5, cost_bps=40, partial=0.7, gate_ma=100, univ_pool=POOL)
rep = mb.window_report(bt, HD)
turn = bt["turnover"].mean()
# annual fee drag estimate
n_per_yr = 52
ann_turn = turn * n_per_yr
ann_fee = ann_turn * (40/2) / 1e4
print(f"Headline LO k=5: avg weekly turnover {turn:.2f} -> ~{ann_turn:.1f}x/yr -> ~{ann_fee*100:.1f}% annual fee drag @40bps RT")
print(f"  Net REC12: Sharpe {rep['REC12']['sharpe']:+.2f}, ann ret {rep['REC12']['ann_ret']*100:+.0f}%, maxDD {rep['REC12']['maxdd']*100:+.0f}%")
print(f"  Net FULL : Sharpe {rep['FULL']['sharpe']:+.2f}, ann ret {rep['FULL']['ann_ret']*100:+.0f}%, maxDD {rep['FULL']['maxdd']*100:+.0f}%")
# min order: $1k bankroll, k=5 -> $200/position. Coinbase min order ~$1-10. Kraken min varies.
for bank in [1000, 10000, 100000]:
    pos = bank / 5
    print(f"  ${bank}: {5} positions x ${pos:.0f} each. Min-order (~$1-10) NOT binding. "
          f"Spot depth deep for top-15 -> slippage ~0 at this size. Fee drag identical (~{ann_fee*100:.0f}%/yr).")

print("\nDONE.")
