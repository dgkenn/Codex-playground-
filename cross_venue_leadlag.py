#!/usr/bin/env python3
"""cross_venue_leadlag.py -- EXO cross-exchange lead-lag test (node EXO-LEADLAG, 2026-07-15).

HYPOTHESIS (operator: "widen the free-data net"): a faster venue (Binance PERP) leads the price the
Kalshi index settles on. If so, the leader gives a predictive read on the 15m binary settlement.

METHOD: Binance Vision spot + futures aggTrades (years, free), aggregate to 1-second last-price,
log-returns, cross-correlation corr(perp_ret[t], spot_ret[t+k]) for k in seconds. k>0 => perp leads.

RESULT (4 sampled days 2024-25):
  k=-3s +0.019  k=-2s +0.040  k=-1s +0.088  k=0s +0.832  k=+1s +0.172  k=+2s +0.078  k=+3s +0.047
=> PERP LEADS SPOT, but the lead is ~1 SECOND (0.17 at +1s vs 0.09 at -1s) and DECAYS to ~0.05 by 3s.

VERDICT: the lead is REAL but HFT-scale (sub-second to seconds). It is (a) irrelevant at the 15m
binary's ~180s decision horizon, and (b) unexploitable for a Kalshi taker with seconds of latency.
"Information not everyone has" here is real only for colocated sub-second execution -- not us. All
predictive microstructure information decays within seconds; our tradeable horizon is minutes ->
priced for us, consistent with EXO-OFI-BACKTEST and EXO-DERIV-BACKTEST.
"""
import urllib.request, zipfile, io, numpy as np, pandas as pd


def load_1s(kind, dstr):
    url = f"https://data.binance.vision/data/{kind}/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{dstr}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=120).read()
    except Exception:
        return None
    z = zipfile.ZipFile(io.BytesIO(raw)); d = z.read(z.namelist()[0])
    hdr = 0 if b"price" in d[:100].lower() else None
    df = pd.read_csv(io.BytesIO(d), header=hdr, usecols=[1, 5], names=None if hdr == 0 else ["price", "ts"])
    if hdr == 0:
        df.columns = [c.lower() for c in df.columns]
        pc = [c for c in df.columns if "price" in c][0]
        tc = [c for c in df.columns if "time" in c][0]
        df = df.rename(columns={pc: "price", tc: "ts"})[["price", "ts"]]
    sec = df["ts"].to_numpy() // 1000
    return pd.Series(df["price"].to_numpy(), index=sec).groupby(level=0).last()


def main():
    days = [f"{y}-{m:02d}-10" for y in (2024, 2025) for m in (2, 5, 8, 11)]
    cc = {}
    for dstr in days:
        sp, pf = load_1s("spot", dstr), load_1s("futures/um", dstr)
        if sp is None or pf is None:
            continue
        idx = sorted(set(sp.index) & set(pf.index))
        if len(idx) < 3600:
            continue
        sp, pf = sp.reindex(idx).ffill(), pf.reindex(idx).ffill()
        rs, rp = np.diff(np.log(sp.to_numpy())), np.diff(np.log(pf.to_numpy()))
        for k in range(-3, 4):
            a, b = (rp[:-k], rs[k:]) if k > 0 else ((rp[-k:], rs[:k]) if k < 0 else (rp, rs))
            n = min(len(a), len(b))
            if n > 1000:
                cc.setdefault(k, []).append(np.corrcoef(a[:n], b[:n])[0, 1])
    print("corr(perp_ret[t], spot_ret[t+k])  [k>0 => perp leads]:")
    for k in range(-3, 4):
        if cc.get(k):
            print(f"  k={k:+d}s: {np.mean(cc[k]):+.4f}")


if __name__ == "__main__":
    main()
