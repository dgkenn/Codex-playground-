"""Fetch OKX funding-rate history for the momentum universe (for funding-stress regime filter).
Daily-aggregated aggregate funding level + cross-sectional funding dispersion.
Staged to a NON-repo dir (/tmp/regime_data) so parquets are never committed.
OKX funding is 8h; we aggregate to daily mean per symbol.
"""
import urllib.request, json, time, os
import pandas as pd

OUT = "/tmp/regime_data/funding.parquet"
UNIVERSE = [
    "BTC","ETH","SOL","XRP","DOGE","ADA","BNB","LTC","BCH","LINK",
    "AVAX","DOT","ATOM","ETC","XLM","FIL","NEAR","UNI","AAVE",
    "TRX","TON","APT","ARB","OP","SUI","INJ","SAND","MANA","AXS",
    "ICP","ALGO","XTZ","THETA","GRT","CRV","COMP","SNX",
]

def fetch_one(sym, max_pages=120):
    inst = f"{sym}-USDT-SWAP"
    rows = []
    after = ""
    for _ in range(max_pages):
        url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst}&limit=100"
        if after:
            url += f"&after={after}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
        except Exception as e:
            print(f"  {sym} err {e}")
            break
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = data[-1]["fundingTime"]
        time.sleep(0.08)
        if len(data) < 100:
            break
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms", utc=True)
    df["fr"] = df["realizedRate"].astype(float)
    df["sym"] = sym
    return df[["ts","sym","fr"]]


def main():
    frames = []
    for sym in UNIVERSE:
        df = fetch_one(sym)
        if df is None or len(df) < 50:
            print(f"SKIP {sym} ({0 if df is None else len(df)})")
            continue
        print(f"OK {sym}: {len(df)} funding pts, {df['ts'].min().date()} -> {df['ts'].max().date()}")
        frames.append(df)
    alld = pd.concat(frames, ignore_index=True)
    os.makedirs("/tmp/regime_data", exist_ok=True)
    alld.to_parquet(OUT)
    print(f"\nSaved {OUT}: {alld['sym'].nunique()} syms, {len(alld)} rows")


if __name__ == "__main__":
    main()
