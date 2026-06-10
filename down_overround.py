"""S4: overround / near-riskless arbitrage on Up + Down tokens.

For a binary, Up + Down pays exactly $1. So:
  buy-both  arb if  Up_ask + Down_ask + fees < 1   (lock guaranteed $1 for < $1)
  sell-both arb if  Up_bid + Down_bid - fees > 1   (collect > $1, owe exactly $1)
Taker fee per leg = 0.10*p*(1-p). Literature says this is unprofitable after fees
on Polymarket -- we VERIFY directly on the aligned Up/Down books.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share

WINDOW_S = 900
GRID = 10  # evaluate every 10s within each window


def main():
    con = duckdb.connect()
    # pair up/down asset per window
    pair = con.execute("""
        SELECT u.window_start, u.asset_id AS up_a, d.down_asset AS down_a
        FROM read_parquet('up_windows.parquet') u
        JOIN read_parquet('down_map.parquet') d USING(window_start)
    """).df()
    # evaluation grid (asset_id, t_ms) for up and down, asof their books
    rows = []
    for _, r in pair.iterrows():
        for k in range(GRID, WINDOW_S, GRID):
            rows.append((r.window_start, r.up_a, r.down_a, (r.window_start + k) * 1000))
    g = pd.DataFrame(rows, columns=["win", "up_a", "down_a", "t_ms"])

    def asof(book, asset_col):
        tg = pd.DataFrame({"asset_id": g[asset_col].astype(str), "t_ms": g["t_ms"].astype("int64"),
                           "r": np.arange(len(g))})
        con.register("tg", tg)
        out = con.execute(f"""
            SELECT tg.r, CAST(b.best_bid AS DOUBLE) bid, CAST(b.best_ask AS DOUBLE) ask
            FROM tg ASOF LEFT JOIN read_parquet('{book}') b
              ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r
        """).df()
        con.unregister("tg")
        return out["bid"].to_numpy(), out["ask"].to_numpy()

    ub, ua = asof("up_book.parquet", "up_a")
    db, da = asof("down_book.parquet", "down_a")
    ok = np.isfinite(ua) & np.isfinite(da) & np.isfinite(ub) & np.isfinite(db) & \
        (ua > 0) & (ua < 1) & (da > 0) & (da < 1)
    ua, da, ub, db = ua[ok], da[ok], ub[ok], db[ok]
    win = g["win"].to_numpy()[ok]

    buy_cost = ua + da + fee_per_share(ua, 1000.0) + fee_per_share(da, 1000.0)
    sell_proc = ub + db - fee_per_share(ub, 1000.0) - fee_per_share(db, 1000.0)
    buy_arb = 1.0 - buy_cost      # >0 => profit buying both
    sell_arb = sell_proc - 1.0    # >0 => profit selling both

    print(f"=== S4 overround arb ({len(ua)} grid points, {len(np.unique(win))} windows) ===")
    print(f"  Up_ask+Down_ask: mean={np.mean(ua+da):.4f}  min={np.min(ua+da):.4f}  "
          f"frac<1 (pre-fee)={np.mean(ua+da<1):.3%}")
    print(f"  Up_bid+Down_bid: mean={np.mean(ub+db):.4f}  max={np.max(ub+db):.4f}  "
          f"frac>1 (pre-fee)={np.mean(ub+db>1):.3%}")
    print(f"  BUY-both arb after fees:  frac profitable={np.mean(buy_arb>0):.3%}  "
          f"best={np.max(buy_arb):+.4f}  mean when +={buy_arb[buy_arb>0].mean() if (buy_arb>0).any() else 0:+.4f}")
    print(f"  SELL-both arb after fees: frac profitable={np.mean(sell_arb>0):.3%}  "
          f"best={np.max(sell_arb):+.4f}  mean when +={sell_arb[sell_arb>0].mean() if (sell_arb>0).any() else 0:+.4f}")
    cap = np.where(buy_arb > 0, buy_arb, 0) + np.where(sell_arb > 0, sell_arb, 0)
    print(f"  total capturable (sum over grid, 1 share each): {cap.sum():+.2f} across "
          f"{(cap>0).sum()} opportunities -> "
          f"{'EDGE' if (buy_arb>0).mean()+(sell_arb>0).mean()>0.01 else 'none after fees (matches literature)'}")


if __name__ == "__main__":
    main()
