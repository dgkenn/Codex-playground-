"""Five literature-grounded hypotheses, tested rigorously on the existing data.

Each is tested as a SIGNAL / calibration / realized-trade economic question (not a
fill-at-quote taker backtest, which we showed manufactures artifacts), with
window-clustered significance and a Bonferroni bar of |t|>2.58 (5 primary tests).

Inputs already on disk: up_book.parquet, up_trades.parquet, up_windows.parquet,
btc.npz.

I1 favorite-longshot bias  (Snowberg-Wolfers 2010; Le 2026)
I2 trade-flow imbalance    (Cont-Kukanov-Stoikov 2014)
I3 intraday seasonality    (Wen-Bouri-Xu-Zhao 2022)
I4 fade-the-dislocation    (intraday reversal; the retail "DISLOCATION" edge)
I5 better volatility model (Black-Scholes-for-prediction-markets; vol risk premium)
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import run_real as rr
from fairvalue import fair_up, fee_per_share

BONF = 2.58  # 0.05/5, two-sided ~ |t|>2.58


def clustered_t(per_window):
    a = np.asarray(per_window, float); a = a[np.isfinite(a)]
    n = len(a)
    if n < 2:
        return n, np.nan, np.nan
    m = a.mean(); s = a.std(ddof=1)
    return n, m, (m / s * np.sqrt(n) if s > 0 else np.nan)


def ols_t(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    s2 = (resid @ resid) / (n - k)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return beta, beta / se


def book_mid_at(con, targets):
    """targets: DataFrame[asset_id, t_ms]. Returns mid via ASOF join to up_book."""
    con.register("tg", targets)
    df = con.execute("""
        SELECT tg.rowid_, (b.best_bid + b.best_ask)/2.0 AS mid, b.best_bid, b.best_ask
        FROM (SELECT *, row_number() OVER () AS rowid_ FROM tg) tg
        ASOF LEFT JOIN read_parquet('up_book.parquet') b
          ON tg.asset_id = b.asset_id AND tg.t_ms >= epoch_ms(b.timestamp)
        ORDER BY tg.rowid_
    """).df()
    return df["mid"].to_numpy()


def load_ctx():
    con = duckdb.connect()
    win = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"]).reset_index(drop=True)
    btc_ts, btc = rr.load_spot("btc.npz")
    return con, win, btc_ts, btc


# --------------------------------------------------------------------------- I1
def i1_flb(con, win, btc_ts, btc):
    print("\n=== I1: favorite-longshot bias / calibration (book mid at tau=450) ===")
    t_ms = ((win["window_start"] + 450) * 1000).to_numpy()
    tg = pd.DataFrame({"asset_id": win["asset_id"].astype(str), "t_ms": t_ms})
    mid = book_mid_at(con, tg)
    res = win["resolved_up"].to_numpy().astype(float)
    ok = np.isfinite(mid) & (mid > 0) & (mid < 1)
    mid, res, ws = mid[ok], res[ok], win["window_start"].to_numpy()[ok]
    # calibration deciles
    print(f"  n={ok.sum()} windows. calibration (price bin -> realized Up freq):")
    bins = np.linspace(0, 1, 6)
    idx = np.clip(np.digitize(mid, bins) - 1, 0, 4)
    for b in range(5):
        m = idx == b
        if m.sum() > 3:
            print(f"    price {bins[b]:.1f}-{bins[b+1]:.1f}: n={m.sum():4d}  "
                  f"mean_price={mid[m].mean():.3f}  realized_up={res[m].mean():.3f}  "
                  f"gap={res[m].mean()-mid[m].mean():+.3f}")
    # FLB regression: resolved ~ a + b*(mid-0.5); b<1 => compression (favorites underpriced)
    X = np.column_stack([np.ones_like(mid), mid - 0.5])
    beta, tv = ols_t(res, X)
    print(f"  resolved ~ a + b*(mid-0.5):  b={beta[1]:+.3f} (t={tv[1]:+.2f}); "
          f"b<1 by t={(beta[1]-1)/ (beta[1]/tv[1] if tv[1]!=0 else np.nan):+.2f} => compression/FLB")
    # economic: bet the favourite (taker, 10% fee), held to resolution, clustered by window
    fav_up = mid > 0.5
    entry = np.where(fav_up, mid, 1 - mid)            # pay the favourite price (approx mid)
    payoff = np.where(fav_up, res, 1 - res)
    pnl = payoff - entry - fee_per_share(entry, 1000.0)
    n, m, t = clustered_t(pnl)                          # 1 trade/window -> already clustered
    print(f"  bet-the-favourite (taker, fee): per-window mean={m:+.4f} t={t:+.2f}  "
          f"-> {'PASS' if abs(t)>BONF and m>0 else 'fail'}")


# --------------------------------------------------------------------------- I2
def i2_ofi(con, win):
    print("\n=== I2: signed trade-flow imbalance predicts resolution (tau=450) ===")
    win_path = "up_windows.parquet"
    df = con.execute(f"""
        SELECT w.window_start, w.resolved_up,
               sum(CASE WHEN t.side='BUY' THEN t.size ELSE -t.size END) AS flow,
               sum(t.size) AS vol
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('{win_path}') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
          AND epoch_ms(t.timestamp)/1000.0 - w.window_start < 450
          AND epoch_ms(t.timestamp)/1000.0 - w.window_start >= 0
        GROUP BY 1,2
    """).df()
    t_ms = ((df["window_start"] + 450) * 1000).to_numpy()
    # need asset_id for mid; rejoin
    a = con.execute(f"SELECT window_start, asset_id FROM read_parquet('{win_path}')").df()
    df = df.merge(a, on="window_start", how="left")
    mid = book_mid_at(con, pd.DataFrame({"asset_id": df["asset_id"].astype(str), "t_ms": t_ms}))
    res = df["resolved_up"].to_numpy().astype(float)
    flow_norm = (df["flow"] / df["vol"].replace(0, np.nan)).to_numpy()   # net taker buy fraction
    ok = np.isfinite(mid) & np.isfinite(flow_norm)
    mid, res, fn = mid[ok], res[ok], flow_norm[ok]
    X = np.column_stack([np.ones_like(mid), mid, fn])
    beta, tv = ols_t(res, X)
    print(f"  n={ok.sum()}.  resolved ~ mid + net_buy_fraction:")
    print(f"    mid coef t={tv[1]:+.2f}   FLOW coef={beta[2]:+.3f} t={tv[2]:+.2f}  "
          f"-> {'PASS' if abs(tv[2])>BONF else 'fail'} (incremental signal beyond price)")


# --------------------------------------------------------------------------- I3
def i3_seasonality(con, win):
    print("\n=== I3: intraday/session seasonality (realized maker & taker-net) ===")
    df = con.execute("""
        SELECT (w.window_start/3600 % 24)::INT AS hour, w.window_start, w.resolved_up,
               t.price, t.size, t.side
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('up_windows.parquet') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
    """).df()
    sell = df["side"] == "SELL"
    df["maker"] = np.where(sell, df["resolved_up"] - df["price"], df["price"] - df["resolved_up"])
    df["taker_net"] = -df["maker"] - fee_per_share(df["price"].to_numpy(), 1000.0)
    sess = {**{h: "Asia(00-08)" for h in range(0, 8)},
            **{h: "EU(08-13)" for h in range(8, 13)},
            **{h: "US(13-21)" for h in range(13, 21)},
            **{h: "Late(21-24)" for h in range(21, 24)}}
    df["sess"] = df["hour"].map(sess)
    print(f"  {'session':14} {'n_win':>6} {'maker t':>8} {'taker_net t':>12}")
    nsess = df["sess"].nunique()
    for s, g in df.groupby("sess"):
        mk = g.groupby("window_start").apply(lambda x: np.average(x["maker"], weights=x["size"]), include_groups=False)
        tk = g.groupby("window_start").apply(lambda x: np.average(x["taker_net"], weights=x["size"]), include_groups=False)
        _, _, tmk = clustered_t(mk); _, _, ttk = clustered_t(tk)
        flag = "PASS" if abs(tmk) > BONF else ""
        print(f"  {s:14} {mk.shape[0]:6d} {tmk:8.2f} {ttk:12.2f}  {flag}")
    print(f"  (Bonferroni across {nsess} sessions x2 sides is even stricter)")


# --------------------------------------------------------------------------- I4
def i4_dislocation(con, win, btc_ts, btc):
    print("\n=== I4: fade-the-dislocation -- does (mid - spot_fair) mean-revert? ===")
    sigma = rr.realized_vol_per_s(btc, 1.0)
    rows = []
    taus = [600, 480, 360, 240, 180]
    delta = 60
    for tau in taus:
        t = (win["window_start"] + (900 - tau)).to_numpy()
        s0 = rr.spot_at(btc_ts, btc, win["window_start"].to_numpy() * 1000)
        st = rr.spot_at(btc_ts, btc, t * 1000)
        fair = fair_up(st, s0, sigma, tau)
        mid_t = book_mid_at(con, pd.DataFrame({"asset_id": win["asset_id"].astype(str), "t_ms": t * 1000}))
        mid_td = book_mid_at(con, pd.DataFrame({"asset_id": win["asset_id"].astype(str), "t_ms": (t + delta) * 1000}))
        resid = mid_t - fair
        fut = mid_td - mid_t
        ok = np.isfinite(resid) & np.isfinite(fut) & (mid_t > 0) & (mid_t < 1)
        for r, f, w in zip(resid[ok], fut[ok], win["window_start"].to_numpy()[ok]):
            rows.append((tau, r, f, w))
    d = pd.DataFrame(rows, columns=["tau", "resid", "fut", "win"])
    # regress future mid change on residual (negative slope = reversion = fadeable)
    X = np.column_stack([np.ones(len(d)), d["resid"].to_numpy()])
    beta, tv = ols_t(d["fut"].to_numpy(), X)
    # window-clustered via per-window mean of resid*fut sign isn't a slope; report naive + note
    print(f"  pooled regression fut_mid_chg ~ resid: slope={beta[1]:+.3f} (naive t={tv[1]:+.2f}, "
          f"n={len(d)} not independent)")
    # honest: one obs/window at tau=360, slope across windows
    sub = d[d["tau"] == 360]
    Xs = np.column_stack([np.ones(len(sub)), sub["resid"].to_numpy()])
    b2, t2 = ols_t(sub["fut"].to_numpy(), Xs)
    print(f"  one-obs/window (tau=360): slope={b2[1]:+.3f} t={t2[1]:+.2f}  "
          f"-> {'reversion' if b2[1]<0 and abs(t2[1])>BONF else 'no clean reversion'}")


# --------------------------------------------------------------------------- I5
def i5_volmodel(con, win, btc_ts, btc):
    print("\n=== I5: does a better volatility model improve fair-value calibration? ===")
    res = win["resolved_up"].to_numpy().astype(float)
    ws = win["window_start"].to_numpy()
    tau = 450
    t = ws + (900 - tau)
    s0 = rr.spot_at(btc_ts, btc, ws * 1000)
    st = rr.spot_at(btc_ts, btc, t * 1000)
    # vol variants
    sig_const = rr.realized_vol_per_s(btc, 1.0)
    # session vol: realized vol of spot within each hour-of-day
    hour = (ws // 3600 % 24)
    logret = np.diff(np.log(btc))
    # rolling realized vol over the 450s before t (per window)
    def vol_window(a_ts, a, t_end, lookback=450):
        i1 = np.searchsorted(a_ts, t_end * 1000)
        i0 = np.searchsorted(a_ts, (t_end - lookback) * 1000)
        out = np.full(len(t_end), np.nan)
        for k in range(len(t_end)):
            seg = a[i0[k]:i1[k]]
            if len(seg) > 5:
                out[k] = np.std(np.diff(np.log(seg)), ddof=1)
        return out
    sig_roll = vol_window(btc_ts, btc, t)
    variants = {
        "constant": np.full(len(t), sig_const),
        "rolling-450s": np.where(np.isfinite(sig_roll) & (sig_roll > 0), sig_roll, sig_const),
        "constant x1.5 (VRP)": np.full(len(t), sig_const * 1.5),
    }
    ok = np.isfinite(s0) & np.isfinite(st)
    print(f"  n={ok.sum()} windows, Brier score (lower=better) of fair@tau=450:")
    for nm, sig in variants.items():
        fair = fair_up(st[ok], s0[ok], 1.0, tau)  # placeholder, replaced below
        fair = np.array([fair_up(st[ok][i], s0[ok][i], sig[ok][i], tau) for i in range(ok.sum())])
        brier = np.mean((fair - res[ok]) ** 2)
        ece = abs(fair.mean() - res[ok].mean())
        print(f"    {nm:22}: Brier={brier:.4f}  mean_fair={fair.mean():.3f} vs realized={res[ok].mean():.3f}")


def main():
    con, win, btc_ts, btc = load_ctx()
    print(f"context: {len(win)} resolved windows")
    i1_flb(con, win, btc_ts, btc)
    i2_ofi(con, win)
    i3_seasonality(con, win)
    i4_dislocation(con, win, btc_ts, btc)
    i5_volmodel(con, win, btc_ts, btc)
    print("\n[multiple testing] 5 primary hypotheses -> Bonferroni bar |t|>2.58; "
          "sub-tests within each make the honest bar stricter still.")


if __name__ == "__main__":
    main()
