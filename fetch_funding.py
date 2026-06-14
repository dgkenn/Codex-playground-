"""
Fetch perp funding-rate history + spot candles from OKX (and dYdX next-funding snapshot).
Public APIs only. Binance/Bybit are geo-blocked here and intentionally NOT used.

OKX funding-rate-history: returns <=100 rows/call at the perp's funding interval (8h for
the majors here). Paginate backwards via the `after` cursor (= fundingTime in ms; returns
rows with ts < after). We pull ~12 months per asset.

Outputs parquet files into /tmp/cx_funding/data/ (these are NOT committed).
"""
import time, json, sys, os
import urllib.request
import pandas as pd

OUT = "/tmp/cx_funding/data"
os.makedirs(OUT, exist_ok=True)

OKX = "https://www.okx.com/api/v5"
ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "ADA"]
MONTHS = 12
NOW_MS = int(time.time() * 1000)
START_MS = NOW_MS - MONTHS * 31 * 24 * 3600 * 1000


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    print("  FAIL", url, last)
    return None


def fetch_funding(asset):
    inst = f"{asset}-USDT-SWAP"
    rows = []
    after = NOW_MS
    while True:
        url = f"{OKX}/public/funding-rate-history?instId={inst}&limit=100&after={after}"
        d = get(url)
        if not d or d.get("code") != "0" or not d["data"]:
            break
        batch = d["data"]
        for r in batch:
            rows.append((int(r["fundingTime"]), float(r["realizedRate"] or r["fundingRate"])))
        oldest = min(int(r["fundingTime"]) for r in batch)
        after = oldest  # next page returns ts < after
        if oldest <= START_MS or len(batch) < 100:
            break
        time.sleep(0.25)
    df = pd.DataFrame(rows, columns=["fundingTime", "fundingRate"]).drop_duplicates("fundingTime")
    df = df[df.fundingTime >= START_MS].sort_values("fundingTime").reset_index(drop=True)
    df["dt"] = pd.to_datetime(df.fundingTime, unit="ms", utc=True)
    return df


def fetch_spot_candles(asset):
    """1H spot candles to estimate basis-leg vol / slippage context (optional)."""
    inst = f"{asset}-USDT"
    rows = []
    after = NOW_MS
    target = NOW_MS - 90 * 24 * 3600 * 1000  # 90d of hourly is plenty for vol context
    while True:
        url = f"{OKX}/market/candles?instId={inst}&bar=1H&limit=300&after={after}"
        d = get(url)
        if not d or d.get("code") != "0" or not d["data"]:
            break
        batch = d["data"]
        for r in batch:
            rows.append((int(r[0]), float(r[4])))  # ts, close
        oldest = min(int(r[0]) for r in batch)
        after = oldest
        if oldest <= target or len(batch) < 300:
            break
        time.sleep(0.2)
    df = pd.DataFrame(rows, columns=["ts", "close"]).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return df


def main():
    fund_summary = {}
    for a in ASSETS:
        print("funding", a)
        f = fetch_funding(a)
        f.to_parquet(f"{OUT}/funding_{a}.parquet")
        fund_summary[a] = (len(f), str(f.dt.min()) if len(f) else "-", str(f.dt.max()) if len(f) else "-")
        print("  rows", len(f), fund_summary[a][1], "->", fund_summary[a][2])
        c = fetch_spot_candles(a)
        c.to_parquet(f"{OUT}/spot_{a}.parquet")
        print("  spot rows", len(c))
    # dYdX cross-check snapshot (next funding only; no long history via public indexer)
    d = get("https://indexer.dydx.trade/v4/perpetualMarkets")
    if d:
        snap = {k: {"nextFundingRate": v.get("nextFundingRate"), "oi": v.get("openInterest"),
                    "vol24h": v.get("volume24H")} for k, v in d["markets"].items()
                if k.split("-")[0] in ASSETS}
        json.dump(snap, open(f"{OUT}/dydx_snapshot.json", "w"), indent=2)
        print("dydx snapshot assets:", list(snap.keys()))
    print("DONE")


if __name__ == "__main__":
    main()
