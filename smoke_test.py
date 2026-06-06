"""Smoke test: generate self-consistent demo data and exercise the engine.

Writes demo_btc.npz (1-s GBM spot) and demo_up_book.parquet (top-of-book for the
"Up" token whose mid tracks a *lagged/underpriced* fair value, so signals fire),
then runs the backtest core and asserts it produces trades with finite PnL.

After this, step 2 runs the same demo through the CLI:
    python run_real.py --book demo_up_book.parquet --spot demo_btc.npz --ts_unit ms
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fairvalue import fair_up, realized_vol_per_s
from run_real import backtest, load_spot, load_book

WINDOW_S = 900
N_WINDOWS = 24
SIGMA = 0.0004
SEED = 3
T0_MS = 1_776_168_000_000          # 2026-04-14T12:00:00Z, 900-s aligned (UTC)


def make_demo():
    rng = np.random.default_rng(SEED)
    total_s = WINDOW_S * N_WINDOWS

    # 1-second GBM spot path.
    steps = rng.normal(0.0, SIGMA, size=total_s)
    logp = np.cumsum(steps)
    price = 60_000.0 * np.exp(logp)
    spot_ts = T0_MS + np.arange(total_s, dtype=np.int64) * 1000
    np.savez("demo_btc.npz", ts=spot_ts, price=price)

    # Book: a tick every 5 s. Mid = fair value shrunk toward 0.5 (market
    # underreacts => exploitable gap, like World A) plus small noise; 2c spread.
    rows = []
    for w in range(N_WINDOWS):
        wstart_s = T0_MS // 1000 + w * WINDOW_S
        s0 = price[w * WINDOW_S]
        for t in range(5, WINDOW_S, 5):
            idx = w * WINDOW_S + t
            snow = price[idx]
            tau = WINDOW_S - t
            fair = fair_up(snow, s0, SIGMA, tau)
            mid = 0.5 + 0.6 * (fair - 0.5) + rng.normal(0, 0.01)   # underreacting market
            mid = min(0.98, max(0.02, mid))
            rows.append((int((wstart_s + t) * 1000), round(mid - 0.01, 4),
                         round(mid + 0.01, 4)))
    book = pd.DataFrame(rows, columns=["timestamp", "best_bid", "best_ask"])
    book["fee_rate_bps"] = 1000
    book.to_parquet("demo_up_book.parquet", index=False)
    return spot_ts, price, book


def main():
    spot_ts, price, _ = make_demo()
    spot_ts, spot_px = load_spot("demo_btc.npz")
    book = load_book("demo_up_book.parquet", "timestamp", "best_bid", "best_ask", "ms")
    sigma = realized_vol_per_s(spot_px, 1.0)

    r = backtest(spot_ts, spot_px, book, WINDOW_S, threshold=0.0,
                 eval_step=60, fee_bps=1000, sigma=sigma)
    tr = r["trades"]
    print("=== smoke_test.py ===")
    print(f"  demo windows: {N_WINDOWS}   eval points: {r['n_eval']}   trades: {len(tr)}")
    ok = (len(tr) > 0) and np.isfinite(tr["pnl"]).all()
    if ok:
        print(f"  win_rate={ (tr['pnl']>0).mean():.3f}  total_pnl={tr['pnl'].sum():+.3f}")
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
