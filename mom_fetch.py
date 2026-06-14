"""Fetch daily OHLCV history from OKX history-candles for a crypto momentum universe.

Survivorship note: OKX only serves currently-listed instruments. Delisted coins
(e.g. dead 2021-cycle alts, LUNA/UST, FTT) are MISSING. This biases backtests
UP (survivors out-performed). We pick an established liquid set and document the bias.
We use SWAP (perp) close where available; perps are what we trade. We fall back to
spot for history that predates perp listing only if needed (not done here -- keep clean).
"""
import urllib.request, json, time, os
import pandas as pd

OUT = "/tmp/mom_signal/mom_data.parquet"

# Established liquid USDT perps. Mix of mega-cap + large alts with multi-year history.
# Chosen by: currently liquid AND listed for years (so daily candles go back far).
UNIVERSE = [
    "BTC","ETH","SOL","XRP","DOGE","ADA","BNB","LTC","BCH","LINK",
    "AVAX","DOT","MATIC","ATOM","ETC","XLM","FIL","NEAR","UNI","AAVE",
    "TRX","TON","APT","ARB","OP","SUI","INJ","SAND","MANA","AXS",
    "ICP","ALGO","EOS","XTZ","THETA","FTM","GRT","CRV","COMP","SNX",
]

def fetch_one(sym, bar="1Dutc", max_pages=60):
    inst = f"{sym}-USDT-SWAP"
    rows = []
    after = ""  # pagination: 'after' returns records older than ts
    for _ in range(max_pages):
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar={bar}&limit=100"
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
        after = data[-1][0]  # oldest ts in this batch
        time.sleep(0.10)
        if len(data) < 100:
            break
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts","o","h","l","c","vol","volccy","volq","confirm"])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    for col in ["o","h","l","c","vol","volccy","volq"]:
        df[col] = df[col].astype(float)
    df = df[df["confirm"] == "1"]  # only closed candles
    df = df.drop_duplicates("ts").sort_values("ts")
    df["sym"] = sym
    return df[["ts","sym","o","h","l","c","vol","volq"]]


def main():
    frames = []
    for sym in UNIVERSE:
        df = fetch_one(sym)
        if df is None or len(df) < 200:
            print(f"SKIP {sym} (insufficient history: {0 if df is None else len(df)})")
            continue
        print(f"OK {sym}: {len(df)} days, {df['ts'].min().date()} -> {df['ts'].max().date()}")
        frames.append(df)
    alld = pd.concat(frames, ignore_index=True)
    alld.to_parquet(OUT)
    print(f"\nSaved {OUT}: {alld['sym'].nunique()} syms, {len(alld)} rows")
    print(f"Date range: {alld['ts'].min().date()} -> {alld['ts'].max().date()}")


if __name__ == "__main__":
    main()
