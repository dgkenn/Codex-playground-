"""Fetch OHLCV from OKX public API (reachable, paginated). Saves parquet to /tmp/cx_statarb/data/.
OKX history-candles: limit<=100, paginate backwards via `after` (ts ms, exclusive upper bound).
Binance/Bybit geo-blocked -> not used. OKX chosen for clean USDT spot + deep history."""
import time, json, urllib.request, os
import pandas as pd, numpy as np

OUT = "/tmp/cx_statarb/data"
os.makedirs(OUT, exist_ok=True)
BASE = "https://www.okx.com/api/v5/market/history-candles"

SYMBOLS = ["BTC-USDT","ETH-USDT","SOL-USDT","BNB-USDT","XRP-USDT",
           "DOGE-USDT","ADA-USDT","AVAX-USDT","LINK-USDT","LTC-USDT"]

# bar -> target number of bars (history depth)
BARS = {"1H": 8000, "15m": 8000, "1D": 1200}

def fetch(instId, bar, target):
    rows, after = [], None
    while len(rows) < target:
        url = f"{BASE}?instId={instId}&bar={bar}&limit=100"
        if after: url += f"&after={after}"
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent":"research"})
                d = json.load(urllib.request.urlopen(req, timeout=20))
                break
            except Exception as e:
                if attempt==4: raise
                time.sleep(1.5*(attempt+1))
        data = d.get("data", [])
        if not data: break
        rows.extend(data)
        after = data[-1][0]  # oldest ts in this page; next page older
        time.sleep(0.18)
        if len(data) < 100: break
    if not rows: return None
    df = pd.DataFrame(rows, columns=["ts","o","h","l","c","vol","volCcy","volCcyQuote","confirm"])
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms", utc=True)
    for col in ["o","h","l","c","vol","volCcyQuote"]:
        df[col] = df[col].astype(float)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return df[["ts","o","h","l","c","vol","volCcyQuote"]]

if __name__ == "__main__":
    for bar, tgt in BARS.items():
        for s in SYMBOLS:
            try:
                df = fetch(s, bar, tgt)
                if df is None or len(df)==0:
                    print(f"  SKIP {s} {bar}: no data"); continue
                fn = f"{OUT}/{s.replace('-','_')}_{bar}.parquet"
                df.to_parquet(fn)
                print(f"  {s} {bar}: {len(df)} rows {df.ts.min()} -> {df.ts.max()}")
            except Exception as e:
                print(f"  ERR {s} {bar}: {e}")
    print("done")
