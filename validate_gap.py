"""Validate the World-A / World-B contrast BEFORE trusting any real-data PnL.

Runs the same favourite-buying strategy in two synthetic worlds and asserts:
  * World A (market underprices favourites): total PnL > 0
  * World B (efficient market + fee):        total PnL < 0
  * BOTH worlds have a high win rate

This is the guardrail for interpreting ``run_real.py``: a high win rate is not
evidence of edge. Only PnL that survives a margin above the fee is.
"""
from __future__ import annotations

from gap_analysis import simulate_world

FEE_BPS = 1000          # matches the fee observed in the Polymarket archive (0.10)
HIGH_WIN_RATE = 0.65


def main():
    a = simulate_world("A", fee_bps=FEE_BPS, seed=1)
    b = simulate_world("B", fee_bps=FEE_BPS, seed=1)

    print("=== validate_gap.py : World-A vs World-B (buy favourites, hold to settle) ===")
    print(f"  fee_bps = {FEE_BPS}  ({FEE_BPS/1e4:.2f} of min(p,1-p) per share)")
    for r in (a, b):
        print(f"  World {r['world']}: win_rate={r['win_rate']:.3f}  "
              f"avg_price={r['avg_price']:.3f}  "
              f"avg_pnl={r['avg_pnl']:+.4f}  total_pnl={r['total_pnl']:+.1f}")

    ok_a = a["total_pnl"] > 0
    ok_b = b["total_pnl"] < 0
    ok_win = a["win_rate"] > HIGH_WIN_RATE and b["win_rate"] > HIGH_WIN_RATE
    ok = ok_a and ok_b and ok_win
    print(f"  World A profitable : {ok_a}")
    print(f"  World B negative   : {ok_b}")
    print(f"  both high win rate : {ok_win}  (>{HIGH_WIN_RATE})")
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
