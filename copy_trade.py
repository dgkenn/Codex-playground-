"""Copy-the-informed-minority: walk-forward test of following skilled wallets.

Rank wallets by IN-SAMPLE own gross PnL (hold-to-resolution), then OUT-OF-SAMPLE:
  (a) persistence: do top wallets stay profitable on their own trades?
  (b) follower edge: when a top wallet trades, a realistic TAKER copies the
      UP-direction by entering the up_book quote `LATENCY`s later, pays the 10%
      fee, holds to resolution.  Window-clustered + bootstrap CI.
Placebo: following IS-BOTTOM wallets should lose. Filters (price<0.7, size>median,
enter within latency) per the copy-trading playbook.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share

LATENCY = 60
MIN_IS_TRADES = 10
TOP_FRAC = 0.10


def own_pnl(df):
    # asset is Up(idx0) or Down(idx1); win if held the winning outcome
    win_out = ((df["outcome_index"] == 0) & (df["resolved_up"] == 1)) | \
              ((df["outcome_index"] == 1) & (df["resolved_up"] == 0))
    buy = df["side"] == "BUY"
    return np.where(buy, win_out.astype(float) - df["price"], df["price"] - win_out.astype(float))


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def main():
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up", "condition_id"])
    wmap = w.set_index("condition_id")
    tr = pd.read_parquet("wallet_trades.parquet")
    tr = tr.merge(w[["condition_id", "window_start", "window_end", "resolved_up", "asset_id"]],
                  on="condition_id", how="inner")
    tr["own"] = own_pnl(tr)
    # view on UP: +1 long up, -1 short up
    tr["view_up"] = np.where(((tr["side"] == "BUY") & (tr["outcome_index"] == 0)) |
                             ((tr["side"] == "SELL") & (tr["outcome_index"] == 1)), 1.0, -1.0)
    print(f"{len(tr)} wallet-trades, {tr['wallet'].nunique()} wallets, "
          f"{tr['window_start'].nunique()} windows")

    mid = np.median(np.unique(tr["window_start"]))
    IS = tr[tr["window_start"] < mid]; OOS = tr[tr["window_start"] >= mid]

    # rank wallets in-sample
    g = IS.groupby("wallet")["own"].agg(["sum", "mean", "count"])
    g = g[g["count"] >= MIN_IS_TRADES].sort_values("mean", ascending=False)
    ntop = max(5, int(len(g) * TOP_FRAC))
    top = set(g.head(ntop).index); bot = set(g.tail(ntop).index)
    print(f"IS wallets with >={MIN_IS_TRADES} trades: {len(g)}; top/bottom {ntop} each")
    print(f"  IS top mean own-PnL={g.head(ntop)['mean'].mean():+.4f}, "
          f"bottom={g.tail(ntop)['mean'].mean():+.4f}")

    # (a) persistence: OOS own-PnL of IS-top wallets
    for label, wset in [("IS-top", top), ("IS-bottom", bot)]:
        sub = OOS[OOS["wallet"].isin(wset)]
        n, m, t = clt(sub.groupby("window_start")["own"].mean().to_numpy())
        print(f"  OOS OWN-PnL persistence {label}: n_win={n} mean={m:+.4f} t={t:+.2f}")

    # (b) realistic follower: copy IS-top wallets' OOS trades as a taker via up_book
    foll = OOS[OOS["wallet"].isin(top)].copy()
    foll = foll[(foll["price"] < 0.7) & (foll["size"] > foll["size"].median())]
    foll["t_entry"] = (foll["ts"] + LATENCY)
    foll = foll[foll["t_entry"] < foll["window_end"]]
    tg = pd.DataFrame({"asset_id": foll["asset_id"].astype(str),
                       "t_ms": (foll["t_entry"] * 1000).astype("int64"), "r": np.arange(len(foll))})
    con.register("tg", tg)
    bk = con.execute("""SELECT tg.r, CAST(b.best_bid AS DOUBLE) bid, CAST(b.best_ask AS DOUBLE) ask
        FROM tg ASOF LEFT JOIN read_parquet('up_book.parquet') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    foll = foll.reset_index(drop=True)
    foll["bid"] = bk["bid"].to_numpy(); foll["ask"] = bk["ask"].to_numpy()
    foll = foll.dropna(subset=["bid", "ask"])
    foll = foll[(foll["bid"] > 0) & (foll["ask"] < 1)]
    up = foll["view_up"] > 0
    entry = np.where(up, foll["ask"], 1 - foll["bid"])
    payoff = np.where(up, foll["resolved_up"], 1 - foll["resolved_up"])
    foll["pnl"] = payoff - entry - fee_per_share(entry, 1000.0)
    per = foll.groupby("window_start")["pnl"].mean().to_numpy()
    n, m, t = clt(per)
    # bootstrap CI over windows
    rng = np.random.default_rng(0)
    boot = [np.mean(rng.choice(per, len(per))) for _ in range(2000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"\n  FOLLOWER (copy IS-top OOS, taker+fee, latency={LATENCY}s, filters): "
          f"n_trades={len(foll)} n_win={n}")
    print(f"    pnl/trade-window mean={m:+.4f}  t={t:+.2f}  95% CI=[{lo:+.4f},{hi:+.4f}]  "
          f"-> {'EDGE' if lo>0 else 'no edge'}")


if __name__ == "__main__":
    main()
