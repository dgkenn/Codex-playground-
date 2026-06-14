"""Fetch OHLCV from OKX public API (history-candles, paginated via `after`).
Primary source: OKX (deepest alt coverage + clean pagination here).
Saves parquet files into /tmp/cx_momentum/data/.
"""
import time, json, sys, os
import urllib.request
import pandas as pd

DATA = "/tmp/cx_momentum/data"
os.makedirs(DATA, exist_ok=True)

UNIVERSE = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT",
            "ADA-USDT", "AVAX-USDT", "LINK-USDT", "LTC-USDT", "BNB-USDT"]

OKX = "https://www.okx.com/api/v5/market/history-candles"


def _get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(1.5 * (i + 1))
            if i == tries - 1:
                print("FAIL", url, e)
                return {"data": []}


def fetch(inst, bar, max_pages):
    """Page backward in time using `after` cursor (ms of oldest row seen)."""
    rows = []
    after = None
    for _ in range(max_pages):
        url = f"{OKX}?instId={inst}&bar={bar}&limit=300"
        if after:
            url += f"&after={after}"
        d = _get(url)
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = data[-1][0]  # oldest ts in this page
        time.sleep(0.25)
        if len(data) < 300:
            break
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "vol", "volCcy", "volQuote", "confirm"])
    df = df[["ts", "o", "h", "l", "c", "volCcy"]].copy()
    df.columns = ["ts", "open", "high", "low", "close", "volume_usd"]
    for col in ["open", "high", "low", "close", "volume_usd"]:
        df[col] = pd.to_numeric(df[col])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return df


def main():
    # Daily: ~2yr -> 730 rows -> ~3 pages. Use 8 pages to be safe.
    # Hourly: several months -> 6 months ~ 4300 rows -> ~15 pages. Use 20.
    for bar, pages, tag in [("1D", 8, "daily"), ("1H", 20, "hourly")]:
        for inst in UNIVERSE:
            df = fetch(inst, bar, pages)
            if df is None or len(df) < 30:
                print(f"SKIP {inst} {bar}: insufficient")
                continue
            fn = f"{DATA}/{inst.replace('-', '')}_{tag}.parquet"
            df.to_parquet(fn)
            print(f"{inst} {bar}: {len(df)} rows  {df.ts.min().date()} -> {df.ts.max().date()}")


if __name__ == "__main__":
    main()
