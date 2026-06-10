"""Round 4 hedge-fund-style strategies testable with no new data.

S5 time-series momentum/reversal of window outcomes (CTA / Moskowitz-Ooi-Pedersen)
S8 follow-the-informed: do LARGE (whale) trades predict resolution beyond price?
   (Gomez-Cram et al.: ~3% informed minority drives price discovery)
S9 large-trade impact reversion: fade impatient takers (temporary impact reverts)

Window-clustered / one-obs-per-window where possible; Bonferroni-aware (|t|>2.58).
"""
from __future__ import annotations

import duckdb
import numpy as np

import run_real as rr
from fairvalue import fee_per_share


def ols_t(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    s2 = (r @ r) / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return beta, beta / se


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


# --------------------------------------------------------------------------- S5
def s5_tsmom():
    print("\n=== S5: time-series momentum/reversal of window outcomes ===")
    btc_ts, btc = rr.load_spot("btc.npz")
    for tf, win_file, step in [("15m", "up_windows.parquet", 900), ("5m", "win_5m.parquet", 300)]:
        import pandas as pd
        w = pd.read_parquet(win_file).sort_values("window_start")
        ws = w["window_start"].to_numpy()
        s0 = rr.spot_at(btc_ts, btc, ws * 1000)
        sc = rr.spot_at(btc_ts, btc, (ws + step) * 1000)
        ok = np.isfinite(s0) & np.isfinite(sc)
        r = np.log(sc[ok] / s0[ok])
        ac1 = np.corrcoef(r[:-1], r[1:])[0, 1]
        # momentum: bet prior window's direction at open (~0.5); outcome sign(r_i)
        prev = np.sign(r[:-1]); out = (r[1:] > 0).astype(float)
        dir_up = prev > 0
        win_mom = (dir_up == (out > 0)).astype(float)
        entry = 0.5
        pnl_mom = win_mom - entry - fee_per_share(entry, 1000.0)
        n, m, t = clt(pnl_mom)
        print(f"  {tf}: AR(1) of window returns={ac1:+.3f}; bet-prior-direction "
              f"hit={win_mom.mean():.3f} pnl/win={m:+.4f} t={t:+.2f}  "
              f"-> {'PASS' if abs(t)>2.58 and m>0 else 'fail'}")


# --------------------------------------------------------------------------- S8
def s8_informed():
    print("\n=== S8: follow-the-informed (large vs small trade flow predicts resolution) ===")
    con = duckdb.connect()
    # size quantiles
    q = con.execute("SELECT quantile_cont(size,0.9) FROM read_parquet('up_trades.parquet')").fetchone()[0]
    df = con.execute(f"""
        SELECT w.window_start AS win, w.resolved_up,
          sum(CASE WHEN t.size>={q} THEN (CASE WHEN t.side='BUY' THEN t.size ELSE -t.size END) ELSE 0 END) AS big_flow,
          sum(CASE WHEN t.size< {q} THEN (CASE WHEN t.side='BUY' THEN t.size ELSE -t.size END) ELSE 0 END) AS small_flow,
          sum(t.size) AS vol, any_value(t.asset_id) AS asset_id
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('up_windows.parquet') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
          AND epoch_ms(t.timestamp)/1000.0 - w.window_start BETWEEN 0 AND 450
        GROUP BY 1,2
    """).df()
    import pandas as pd
    # mid at t=open+450
    tg = pd.DataFrame({"asset_id": df["asset_id"].astype(str),
                       "t_ms": ((df["win"] + 450) * 1000).astype("int64")})
    con.register("tg", tg)
    mid = con.execute("""
        SELECT (b.best_bid+b.best_ask)/2.0 mid FROM (SELECT *,row_number() OVER() r FROM tg) tg
        ASOF LEFT JOIN read_parquet('up_book.parquet') b
          ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r
    """).df()["mid"].to_numpy()
    res = df["resolved_up"].to_numpy().astype(float)
    big = (df["big_flow"] / df["vol"].replace(0, np.nan)).to_numpy()
    small = (df["small_flow"] / df["vol"].replace(0, np.nan)).to_numpy()
    ok = np.isfinite(mid) & np.isfinite(big) & np.isfinite(small)
    X = np.column_stack([np.ones(ok.sum()), mid[ok], big[ok], small[ok]])
    beta, tv = ols_t(res[ok], X)
    print(f"  n={ok.sum()}.  resolved ~ mid + big_flow + small_flow:")
    print(f"    mid t={tv[1]:+.2f} | BIG-trade flow coef={beta[2]:+.3f} t={tv[2]:+.2f} "
          f"{'PASS' if abs(tv[2])>2.58 else 'fail'} | small flow t={tv[3]:+.2f}")


# --------------------------------------------------------------------------- S9
def s9_impact_reversion():
    print("\n=== S9: large-trade impact reversion (fade impatient takers, mark at mid) ===")
    con = duckdb.connect()
    q = con.execute("SELECT quantile_cont(size,0.95) FROM read_parquet('up_trades.parquet')").fetchone()[0]
    import pandas as pd
    tr = con.execute(f"""
        SELECT epoch_ms(t.timestamp) AS ts_ms, t.asset_id, t.size, t.side,
               w.window_start AS win, w.window_end
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('up_windows.parquet') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL AND t.size>={q}
          AND epoch_ms(t.timestamp)/1000.0 - w.window_start BETWEEN 0 AND 840
    """).df()
    tdir = np.where(tr["side"] == "BUY", 1.0, -1.0)
    aid = tr["asset_id"].astype(str).to_numpy(); ts = tr["ts_ms"].to_numpy()
    wend = (tr["window_end"].to_numpy() * 1000).astype(np.int64)

    def mids(t_ms):
        tg = pd.DataFrame({"asset_id": aid, "t_ms": np.asarray(t_ms, np.int64)})
        con.register("tg2", tg)
        m = con.execute("""SELECT (b.best_bid+b.best_ask)/2.0 mid FROM
            (SELECT *,row_number() OVER() r FROM tg2) tg2 ASOF LEFT JOIN read_parquet('up_book.parquet') b
            ON tg2.asset_id=b.asset_id AND tg2.t_ms>=epoch_ms(b.timestamp) ORDER BY tg2.r""").df()["mid"].to_numpy()
        con.unregister("tg2"); return m
    mid_post = mids(ts + 200)         # ~just after the trade (book updated)
    print(f"  {len(tr)} large (>=95th pct) trades. fade PnL = -dir*(mid_(t+D)-mid_post), mark at mid:")
    for D in [1, 5, 30, 120]:
        mE = mids(np.minimum(ts + D * 1000, wend))
        fade = -tdir * (mE - mid_post)
        d = pd.DataFrame({"win": tr["win"], "fade": fade})
        per = d.groupby("win")["fade"].mean().to_numpy()
        n, m, t = clt(per)
        print(f"    D={D:>4}s: per-win mean={m:+.5f} t={t:+.2f} "
              f"{'(reversion, fadeable)' if m>0 and abs(t)>2.58 else ''}")


def main():
    s5_tsmom()
    s8_informed()
    s9_impact_reversion()
    print("\n[Bonferroni] round-4 adds >=3 primary tests; honest bar |t|>2.58 (stricter w/ sub-tests).")


if __name__ == "__main__":
    main()
