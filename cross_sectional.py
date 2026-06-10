"""Economic test of the cross-sectional reversion signal (diagnostics D3 / S2).

Each step, across the 4 coins' UP tokens: dislocation = mid - spot_fair, demeaned
across coins. Go LONG the most-underpriced coin, SHORT the most-overpriced
(market-neutral pair), hold DELTA, measure mid-to-mid PnL. Compare GROSS edge to
realistic costs (half-spread + 10% taker fee per leg, entry+exit) to see if the
real (t=-2.95) signal survives the fee, window-clustered.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import run_real as rr
from fairvalue import fair_up, fee_per_share

STEP = 30
DELTA = 60
SPOT = {"btc": "btc.npz", "eth": "ETHUSDT.npz", "sol": "SOLUSDT.npz", "xrp": "XRPUSDT.npz"}


def mids(con, book, aid, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(aid, str), "t_ms": np.asarray(t_ms, np.int64), "r": np.arange(len(aid))})
    con.register("tg", tg)
    o = con.execute(f"""SELECT tg.r,(CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2 mid,
        CAST(b.best_bid AS DOUBLE) bid, CAST(b.best_ask AS DOUBLE) ask
        FROM tg ASOF LEFT JOIN read_parquet('{book}') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg")
    return o["mid"].to_numpy(), o["bid"].to_numpy(), o["ask"].to_numpy()


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def main():
    con = duckdb.connect()
    btc = pd.read_parquet("up_windows.parquet")[["window_start", "asset_id"]].assign(coin="btc")
    alt = pd.read_parquet("alt_windows.parquet")[["window_start", "asset_id", "coin"]]
    toks = pd.concat([btc, alt], ignore_index=True)
    cnt = toks.groupby("window_start")["coin"].nunique()
    commons = cnt[cnt == 4].index
    toks = toks[toks["window_start"].isin(commons)]
    rows = [(ws, ws + k) for ws in commons for k in range(STEP, 900 - DELTA, STEP)]
    grid = pd.DataFrame(rows, columns=["ws", "t"])
    spots = {c: rr.load_spot(p) for c, p in SPOT.items()}
    data = {}
    for coin in ["btc", "eth", "sol", "xrp"]:
        sub = toks[toks["coin"] == coin].set_index("window_start")["asset_id"]
        aid = grid["ws"].map(sub).astype(str).to_numpy()
        book = "up_book.parquet" if coin == "btc" else "alt_book.parquet"
        m, bid, ask = mids(con, book, aid, (grid["t"] * 1000).to_numpy())
        mfut, _, _ = mids(con, book, aid, ((grid["t"] + DELTA) * 1000).to_numpy())
        ts_, px_ = spots[coin]; sig = rr.realized_vol_per_s(px_, 1.0)
        s0 = rr.spot_at(ts_, px_, grid["ws"].to_numpy() * 1000)
        st = rr.spot_at(ts_, px_, grid["t"].to_numpy() * 1000)
        tau = (grid["ws"] + 900 - grid["t"]).to_numpy()
        fair = fair_up(st, s0, sig, tau)
        data[coin] = dict(mid=m, bid=bid, ask=ask, mfut=mfut, disloc=m - fair)
    ws = grid["ws"].to_numpy()
    coins = ["btc", "eth", "sol", "xrp"]
    D = np.column_stack([data[c]["disloc"] for c in coins])
    MID = np.column_stack([data[c]["mid"] for c in coins])
    FUT = np.column_stack([data[c]["mfut"] for c in coins])
    BID = np.column_stack([data[c]["bid"] for c in coins])
    ASK = np.column_stack([data[c]["ask"] for c in coins])
    ok = np.isfinite(D).all(1) & np.isfinite(FUT).all(1) & (MID > 0.02).all(1) & (MID < 0.98).all(1)
    D, MID, FUT, BID, ASK, ws = D[ok], MID[ok], FUT[ok], BID[ok], ASK[ok], ws[ok]
    Dd = D - D.mean(1, keepdims=True)
    short = np.argmax(Dd, 1)   # most overpriced -> short
    long = np.argmin(Dd, 1)    # most underpriced -> long
    idx = np.arange(len(D))
    # GROSS mid-to-mid: long gains if its mid rises, short gains if its mid falls
    gross = (FUT[idx, long] - MID[idx, long]) - (FUT[idx, short] - MID[idx, short])
    # NET taker: enter long@ask, short@bid; exit long@bid, short@ask (cross both ways) + fees
    cost_long = (ASK[idx, long] - BID[idx, long]) + fee_per_share(ASK[idx, long], 1000.0) + fee_per_share(BID[idx, long], 1000.0)
    cost_short = (ASK[idx, short] - BID[idx, short]) + fee_per_share(ASK[idx, short], 1000.0) + fee_per_share(BID[idx, short], 1000.0)
    net = gross - cost_long - cost_short
    ng, mg, tg = clt(pd.Series(gross).groupby(ws).mean().to_numpy())
    nn, mn, tn = clt(pd.Series(net).groupby(ws).mean().to_numpy())
    print(f"cross-sectional long/short reversion ({len(gross)} steps, {ng} windows, hold {DELTA}s):")
    print(f"  GROSS (mid-to-mid): per-win mean={mg:+.5f} t={tg:+.2f}")
    print(f"  mean round-trip COST/pair (2 spreads + 4 fees): {np.nanmean(cost_long+cost_short):.4f}")
    print(f"  NET (taker, realistic): per-win mean={mn:+.5f} t={tn:+.2f}  "
          f"-> {'EDGE' if mn>0 and abs(tn)>2.58 else 'killed by costs'}")


if __name__ == "__main__":
    main()
