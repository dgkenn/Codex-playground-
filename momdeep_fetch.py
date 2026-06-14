"""Fetch OKX funding-rate-history + open-interest + perp candles for the
cross-sectional momentum de-risking study.

Funding: positive funding => longs pay shorts (shorts RECEIVE). We need the
funding paid/received on each leg to net into strategy P&L.
Open-interest + perp existence => shortability check.

Writes parquet into /tmp/cx_momdeep/data_deep/.
"""
import time, json, os
import urllib.request
import pandas as pd

OUT = "/tmp/cx_momdeep/data_deep"
os.makedirs(OUT, exist_ok=True)

# Map of spot coin -> OKX perp instId (USDT-margined swap)
PERP = {
    "BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP", "SOL": "SOL-USDT-SWAP",
    "XRP": "XRP-USDT-SWAP", "DOGE": "DOGE-USDT-SWAP", "ADA": "ADA-USDT-SWAP",
    "AVAX": "AVAX-USDT-SWAP", "LINK": "LINK-USDT-SWAP", "LTC": "LTC-USDT-SWAP",
    "BNB": "BNB-USDT-SWAP",
}

BASE = "https://www.okx.com/api/v5"


def _get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(1.2 * (i + 1))
            if i == tries - 1:
                print("FAIL", url, str(e)[:80])
                return {"data": []}


def fetch_funding(inst, max_pages=120):
    """funding-rate-history: paginate backward via `after` (ms cursor). 100/page."""
    rows = []
    after = None
    for _ in range(max_pages):
        url = f"{BASE}/public/funding-rate-history?instId={inst}&limit=100"
        if after:
            url += f"&after={after}"
        d = _get(url)
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = data[-1]["fundingTime"]
        time.sleep(0.15)
        if len(data) < 100:
            break
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms", utc=True)
    df["fundingRate"] = pd.to_numeric(df["fundingRate"])
    df = df[["fundingTime", "fundingRate"]].drop_duplicates("fundingTime").sort_values("fundingTime").reset_index(drop=True)
    return df


def fetch_oi(inst):
    """current open interest (snapshot) + ticker for liquidity gauge."""
    d = _get(f"{BASE}/public/open-interest?instId={inst}")
    oi = None
    if d.get("data"):
        row = d["data"][0]
        oi = {"oi_ccy": float(row.get("oiCcy", "nan") or "nan"),
              "oi_usd": None}
    t = _get(f"{BASE}/market/ticker?instId={inst}")
    last = None
    vol24 = None
    if t.get("data"):
        tr = t["data"][0]
        last = float(tr.get("last", "nan") or "nan")
        vol24 = float(tr.get("volCcy24h", "nan") or "nan")  # 24h vol in base ccy
    if oi and last:
        oi["oi_usd"] = oi["oi_ccy"] * last
    return {"inst": inst, "last": last, "vol24h_ccy": vol24,
            "vol24h_usd": (vol24 * last) if (vol24 and last) else None,
            **(oi or {})}


def main():
    oi_rows = []
    for coin, inst in PERP.items():
        # funding
        f = fetch_funding(inst)
        if f is not None:
            f.to_parquet(f"{OUT}/{coin}_funding.parquet")
            print(f"{coin} funding: {len(f)} rows {f['fundingTime'].min().date()} -> {f['fundingTime'].max().date()} "
                  f"mean={f['fundingRate'].mean()*100:.4f}%/8h")
        else:
            print(f"{coin} funding: NONE (perp may not exist)")
        # OI + liquidity
        oi = fetch_oi(inst)
        oi_rows.append({"coin": coin, **oi})
        print(f"  {coin} OI=${oi.get('oi_usd', 0)/1e6:.1f}M  vol24h=${(oi.get('vol24h_usd') or 0)/1e6:.0f}M")
        time.sleep(0.2)
    pd.DataFrame(oi_rows).to_parquet(f"{OUT}/perp_liquidity.parquet")
    print("\nSaved perp_liquidity.parquet")


if __name__ == "__main__":
    main()
