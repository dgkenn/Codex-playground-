"""CAPACITY + COST-MODEL section: combine live OKX book depth (walk-the-book slippage vs size)
with the strategy's per-coin turnover to get NET Sharpe as a function of AUM.

Cost model per rebalance per coin:
  traded_usd  = AUM * |Δweight_coin|         (weight is fraction of ONE side; gross book = 2*AUM)
  slippage    = interp(book_curve_coin, traded_usd)   (one-way, bps vs mid; avg of buy/sell)
  taker_fee   = TAKER_BPS  (OKX perp taker ~5 bps; -50% with fee tier, use 5)
  per-coin RT cost(frac) = (slippage + taker_fee) / 1e4   applied to |Δweight_coin|
Funding-while-holding is added as a separate ann drag/credit per the live funding snapshot
(dollar-neutral => largely cancels; long leg pays high-funding momentum coins).

We re-run the weekly backtest with cost_fn driven by the live book, sweeping AUM, and report
recent-12mo (REC12) net Sharpe. We find the AUM where net Sharpe halves vs the frictionless-ish
small-size level, and where it hits zero.
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/mom_exec")
import mom_backtest as mb
import mom_exec as me

BOOK = json.load(open("/tmp/exec_data/book_depth.json"))
META = json.load(open("/tmp/exec_data/meta.json"))
try:
    FUND = json.load(open("/tmp/exec_data/funding.json"))
except Exception:
    FUND = {}

TAKER_BPS = 5.0       # OKX perp taker fee, one-way
HOLD_DAYS = 7
REBAL_PER_YR = 365.0 / HOLD_DAYS


def coin_slip_bps(coin, traded_usd):
    """One-way slippage (bps vs mid) to trade traded_usd notional, avg of buy/sell sides.
    Walk-the-book curve is interpolated; beyond deepest measured size we extrapolate with a
    sqrt-impact tail anchored to the last measured point (book likely refills but conservatively)."""
    bk = BOOK.get(coin)
    if bk is None:
        return 50.0  # unknown coin: punitive
    grid = np.array(bk["size_grid_usd"], float)
    buy = np.array(bk["buy_slip_bps"], float)
    sell = np.array(bk["sell_slip_bps"], float)
    avg = np.nanmean(np.vstack([buy, sell]), axis=0)
    # half-spread floor (you cross the spread regardless of size)
    floor = META[coin]["spread_bps"] / 2.0
    avg = np.maximum(avg, floor)
    if traded_usd <= grid[0]:
        return float(avg[0])
    if traded_usd <= grid[-1]:
        return float(np.interp(traded_usd, grid, avg))
    # extrapolate: sqrt impact beyond last grid point
    last_s, last_b = grid[-1], avg[-1]
    return float(last_b * np.sqrt(traded_usd / last_s))


def make_cost_fn(aum):
    def cost_fn(dchg, w_target):
        # dchg: per-coin |Δweight|; traded notional per coin = aum * dchg
        tot = 0.0
        for coin, d in dchg.items():
            if d <= 0:
                continue
            traded = aum * d
            slip = coin_slip_bps(coin, traded)
            tot += d * (slip + TAKER_BPS) / 1e4
        return tot
    return cost_fn


def funding_drag_ann(px, vol):
    """Estimate ann funding P&L of the dollar-neutral book using live funding snapshot.
    long pays funding, short receives. Avg over recent rebalance composition."""
    if not FUND:
        return 0.0
    # approximate: average funding of long tail minus short tail under typical composition.
    # Build last-date weights and net funding.
    t = px.index[-1]
    w, _ = me.build_weights(px, vol, t)
    if w is None:
        return 0.0
    pnl = 0.0
    for c, wt in w.items():
        f = FUND.get(c, {}).get("ann_pct", 0.0) / 100.0
        pnl += -wt * f   # long (wt>0) pays f; short (wt<0) receives
    return pnl


def main():
    px, vol = mb.load_panel()
    print("=== 3. LIVE OKX PERP DEPTH — cost-vs-size (one-way slippage bps vs mid, avg buy/sell) ===")
    sizes = [1e4, 5e4, 1e5, 5e5, 1e6, 5e6]
    hdr = "coin   spread  " + " ".join(f"{int(s/1e3)}k".rjust(7) for s in sizes)
    print(hdr)
    for c in BOOK:
        row = f"{c:6} {META[c]['spread_bps']:6.2f}  "
        row += " ".join(f"{coin_slip_bps(c, s):7.1f}" for s in sizes)
        print(row)

    fd = funding_drag_ann(px, vol)
    print(f"\nFunding P&L (dollar-neutral book, live snapshot): {fd*100:+.2f}%/yr "
          f"(applied as ann drag/credit to net returns)")

    print("\n=== 4. CAPACITY CURVE — REC12 net Sharpe vs AUM (weekly, live-book cost) ===")
    print(f"{'AUM':>8} {'avgRTcost(bps)':>15} {'netRC12_Sh':>11} {'annRC12':>9}")
    aums = [1e4, 1e5, 5e5, 1e6, 2.5e6, 5e6, 1e7, 2.5e7, 5e7, 1e8]
    res = []
    for aum in aums:
        bt = me.backtest(px, vol, hold_days=HOLD_DAYS, cost_fn=make_cost_fn(aum))
        # add funding drag (ann -> per-rebalance)
        bt = bt.copy()
        bt["net"] = bt["net"] + fd / REBAL_PER_YR
        w = me.windows(bt, HOLD_DAYS)
        # avg RT cost in bps per rebalance = mean(cost)/mean(turnover)*1e4
        avg_cost_bps = (bt["cost"].mean() / bt["turnover"].mean()) * 1e4
        res.append((aum, avg_cost_bps, w["net_rec12"], w["ann_rec12"]))
        print(f"{aum:8.0f} {avg_cost_bps:15.2f} {w['net_rec12']:11.2f} {w['ann_rec12']*100:8.1f}%")

    base_sh = res[0][2]
    half = base_sh / 2.0
    aum_half = aum_zero = None
    for i in range(1, len(res)):
        a0, _, s0, _ = res[i - 1]; a1, _, s1, _ = res[i]
        if aum_half is None and s1 <= half <= s0:
            aum_half = a0 + (a1 - a0) * (s0 - half) / (s0 - s1)
        if aum_zero is None and s1 <= 0 <= s0:
            aum_zero = a0 + (a1 - a0) * (s0 - 0) / (s0 - s1)
    print(f"\nSmall-size REC12 Sharpe ~ {base_sh:.2f}")
    print(f"Net Sharpe HALVES (to {half:.2f}) at AUM ~ ${aum_half/1e6:.1f}M" if aum_half else "Net Sharpe does not halve within tested range")
    print(f"Net Sharpe hits ZERO at AUM ~ ${aum_zero/1e6:.1f}M" if aum_zero else "Net Sharpe stays >0 within tested range")

    # per-coin binding capacity: AUM at which the per-coin traded notional in a full rebalance
    # incurs > ~15bps one-way slippage. traded ~ aum * typical |Δw| (~0.20 for a full entry/exit).
    print("\nPer-coin binding capacity (AUM where a full 0.20-weight entry costs >15bps one-way):")
    for c in BOOK:
        cap = None
        for aum in np.logspace(4, 9, 200):
            if coin_slip_bps(c, aum * 0.20) > 15.0:
                cap = aum; break
        capn = f"${cap/1e6:.1f}M" if cap else ">$1B"
        print(f"  {c:5} {capn}")


if __name__ == "__main__":
    main()
