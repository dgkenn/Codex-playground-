"""
btc_deep_pull.py -- Pull CEX data (Coinbase + OKX 1m candles) covering the Kalshi
BTC 15-min window range, plus OKX funding-rate history. Caches to /tmp/cx_btcdeep/cex_cache/.

CEX trade-level history is recent-only on these public endpoints, so for deep
order-flow we use 1m candle OHLCV + volume (a proxy for flow) over the FULL range,
and note the limit in BTC_DEEP.md.
"""
import urllib.request, json, time, os, sys
import numpy as np
import pandas as pd

CACHE = "/tmp/cx_btcdeep/cex_cache"
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (research)"}


def _get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def pull_coinbase(t0, t1):
    """Coinbase 1m candles [t0,t1] (unix s). 300 max/req. Returns df ts,o,h,l,c,v."""
    fp = f"{CACHE}/coinbase_1m.parquet"
    if os.path.exists(fp):
        return pd.read_parquet(fp)
    rows = []
    s = t0
    step = 300 * 60
    n = 0
    while s < t1:
        e = min(s + step, t1)
        url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60&start={s}&end={e}"
        d = _get(url)
        rows.extend(d)
        n += 1
        if n % 20 == 0:
            print(f"  coinbase req {n}, ts={s}, rows={len(rows)}", flush=True)
        s = e
        time.sleep(0.18)
    df = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "vol"])
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    df.to_parquet(fp)
    print(f"coinbase: {len(df)} candles {df.ts.min()}..{df.ts.max()}", flush=True)
    return df


def pull_okx(t0, t1):
    """OKX 1m history-candles. Uses 'after' (ms, exclusive upper). 100/req."""
    fp = f"{CACHE}/okx_1m.parquet"
    if os.path.exists(fp):
        return pd.read_parquet(fp)
    rows = []
    after = (t1 + 60) * 1000
    floor = t0 * 1000
    n = 0
    while after > floor:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1m&after={after}&limit=100"
        d = _get(url)
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        oldest = int(data[-1][0])
        after = oldest
        n += 1
        if n % 30 == 0:
            print(f"  okx req {n}, oldest={oldest}, rows={len(rows)}", flush=True)
        time.sleep(0.12)
    df = pd.DataFrame(rows, columns=["ts_ms", "open", "high", "low", "close", "vol", "volccy", "volccyq", "confirm"])
    df["ts"] = (df.ts_ms.astype(np.int64) // 1000)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for c in ["open", "high", "low", "close", "vol"]:
        df[c] = df[c].astype(float)
    df = df[["ts", "open", "high", "low", "close", "vol"]]
    df.to_parquet(fp)
    print(f"okx: {len(df)} candles {df.ts.min()}..{df.ts.max()}", flush=True)
    return df


def pull_okx_funding(t0, t1):
    fp = f"{CACHE}/okx_funding.parquet"
    if os.path.exists(fp):
        return pd.read_parquet(fp)
    rows = []
    after = (t1 + 3600) * 1000
    floor = t0 * 1000
    n = 0
    while after > floor:
        url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&after={after}&limit=100"
        d = _get(url)
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = int(data[-1]["fundingTime"])
        n += 1
        time.sleep(0.12)
        if n > 200:
            break
    if not rows:
        return pd.DataFrame(columns=["ts", "fundingRate"])
    df = pd.DataFrame(rows)
    df["ts"] = df.fundingTime.astype(np.int64) // 1000
    df["fundingRate"] = df.fundingRate.astype(float)
    df = df[["ts", "fundingRate"]].drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    df.to_parquet(fp)
    print(f"okx funding: {len(df)} pts", flush=True)
    return df


if __name__ == "__main__":
    h = pd.read_parquet("/tmp/cx_btcdeep/hist_kalshi_btc15m.parquet")
    t0 = int(h.ws.min()) - 3600
    t1 = int(h.ws.max()) + 15 * 60 + 60
    print(f"range {t0}..{t1} ({(t1-t0)/86400:.1f} days)", flush=True)
    cb = pull_coinbase(t0, t1)
    okx = pull_okx(t0, t1)
    fund = pull_okx_funding(t0, t1)
    print("DONE", len(cb), len(okx), len(fund))
