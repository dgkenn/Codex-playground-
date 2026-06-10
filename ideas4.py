"""Round 4b cheap hedge-fund tests (local data only).

D late-tau extreme calibration: are near-certain late prices (theta/longshot)
  mispriced -> fade overpriced 'sure things'?
E token-price momentum: does the token mid trend (continuation) intra-window,
  distinct from spot (CTA on the contract itself)?
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share


def asof_mid(con, asset_ids, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(asset_ids, str), "t_ms": np.asarray(t_ms, np.int64),
                       "r": np.arange(len(asset_ids))})
    con.register("tg", tg)
    o = con.execute("""SELECT tg.r,(CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2 mid
        FROM tg ASOF LEFT JOIN read_parquet('up_book.parquet') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg"); return o["mid"].to_numpy()


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def d_late_calibration():
    print("\n=== D: late-tau extreme calibration (tau=120s) ===")
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])
    mid = asof_mid(con, w["asset_id"].astype(str), (w["window_start"] + 780) * 1000)
    res = w["resolved_up"].to_numpy().astype(float)
    ok = np.isfinite(mid) & (mid > 0) & (mid < 1)
    mid, res = mid[ok], res[ok]
    for lo, hi, lbl in [(0.0, 0.1, "longshot<0.1"), (0.9, 1.0, "fav>0.9"),
                        (0.1, 0.3, "0.1-0.3"), (0.7, 0.9, "0.7-0.9")]:
        m = (mid >= lo) & (mid < hi)
        if m.sum() > 3:
            print(f"  {lbl:12}: n={m.sum():3d} mean_price={mid[m].mean():.3f} "
                  f"realized={res[m].mean():.3f} gap={res[m].mean()-mid[m].mean():+.3f}")
    # fade overpriced sure-things: short the favourite when mid>0.9 (buy the cheap side)
    fav = mid > 0.85
    # bet AGAINST the favourite (buy underdog at 1-mid); payoff if underdog wins
    entry = 1 - mid[fav]
    payoff = (res[fav] < 0.5).astype(float)
    pnl = payoff - entry - fee_per_share(entry, 1000.0)
    n, mn, t = clt(pnl)
    print(f"  fade favourites(>0.85): n={n} pnl/bet={mn:+.4f} t={t:+.2f} "
          f"-> {'edge' if mn>0 and abs(t)>2.58 else 'no edge'}")


def e_token_momentum():
    print("\n=== E: token-mid momentum (continuation), clustered ===")
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet")
    rows = []
    for tau in [600, 480, 360, 240, 180, 120]:
        sub = w.copy(); sub["t"] = sub["window_start"] + (900 - tau); sub["tau"] = tau
        rows.append(sub)
    g = pd.concat(rows, ignore_index=True)
    aid = g["asset_id"].astype(str).to_numpy(); t = g["t"].to_numpy()
    D = 60
    m_tm = asof_mid(con, aid, (t - D) * 1000)
    m_t = asof_mid(con, aid, t * 1000)
    m_tp = asof_mid(con, aid, (t + D) * 1000)
    past = m_t - m_tm; fut = m_tp - m_t
    ok = np.isfinite(past) & np.isfinite(fut) & (m_t > 0.02) & (m_t < 0.98)
    past, fut, win = past[ok], fut[ok], g["window_start"].to_numpy()[ok]
    # window-clustered slope
    X = np.column_stack([np.ones_like(past), past]); beta, *_ = np.linalg.lstsq(X, fut, rcond=None)
    resid = fut - X @ beta; XtXi = np.linalg.inv(X.T @ X); meat = np.zeros((2, 2))
    for wv in np.unique(win):
        s = X[win == wv].T @ resid[win == wv]; meat += np.outer(s, s)
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi))
    print(f"  fut_mid_chg ~ past_mid_chg: slope={beta[1]:+.3f} clustered t={beta[1]/se[1]:+.2f} "
          f"(n={len(past)}) -> {'momentum' if beta[1]>0 and abs(beta[1]/se[1])>2.58 else ('reversion' if beta[1]<0 and abs(beta[1]/se[1])>2.58 else 'none')}")


def main():
    d_late_calibration()
    e_token_momentum()


if __name__ == "__main__":
    main()
