"""Wallet diagnostics: is there ANY persistent skill to follow, or is in-sample
performance just luck? Pre-specified selection rules (avoid p-hacking), each
judged on OOS own-PnL persistence (need t>2.58) + concentration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN = [10, 30, 50]


def own_pnl(df):
    win = ((df["outcome_index"] == 0) & (df["resolved_up"] == 1)) | \
          ((df["outcome_index"] == 1) & (df["resolved_up"] == 0))
    return np.where(df["side"] == "BUY", win.astype(float) - df["price"], df["price"] - win.astype(float))


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def main():
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up", "condition_id"])
    tr = pd.read_parquet("wallet_trades.parquet").merge(
        w[["condition_id", "window_start", "resolved_up"]], on="condition_id", how="inner")
    tr["own"] = own_pnl(tr)
    tr["t_into"] = tr["ts"] - tr["window_start"]
    mid = np.median(np.unique(tr["window_start"]))
    IS, OOS = tr[tr["window_start"] < mid], tr[tr["window_start"] >= mid]

    # concentration of total wallet PnL
    tot = tr.groupby("wallet")["own"].sum().sort_values()
    pos = tot[tot > 0].sum(); top1 = tot.tail(int(len(tot) * 0.01)).sum()
    print(f"wallets={len(tot)}, total +PnL pool={pos:,.0f}; top-1% wallets capture "
          f"{top1/pos:.1%} of gross positive PnL (concentration)")

    print("\npersistence: IS-top-decile -> OOS own-PnL (need t>2.58 to be real skill)")
    print(f"  {'rule':34} {'n_top':>6} {'OOS mean':>9} {'OOS t':>7}")
    for mn in MIN:
        gI = IS.groupby("wallet")["own"].agg(["mean", "sum", "count"])
        gI = gI[gI["count"] >= mn]
        for metric in ["mean", "sum"]:
            top = set(gI.sort_values(metric, ascending=False).head(max(5, int(len(gI) * .1))).index)
            sub = OOS[OOS["wallet"].isin(top)]
            n, m, t = clt(sub.groupby("window_start")["own"].mean().to_numpy())
            print(f"  min{mn:>3}, rank by {metric:<4}              {len(top):>6} {m:>+9.4f} {t:>+7.2f}")
        # early-traders variant (median t_into below overall median => trade early)
        early = IS.groupby("wallet")["t_into"].median()
        ew = set(early[early < early.median()].index) & set(gI.index)
        topE = set(gI.loc[list(ew)].sort_values("mean", ascending=False).head(max(5, int(len(ew) * .1))).index)
        sub = OOS[OOS["wallet"].isin(topE)]
        n, m, t = clt(sub.groupby("window_start")["own"].mean().to_numpy())
        print(f"  min{mn:>3}, top mean & EARLY traders     {len(topE):>6} {m:>+9.4f} {t:>+7.2f}")


if __name__ == "__main__":
    main()
