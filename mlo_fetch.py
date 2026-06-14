"""Fetch daily USD-spot OHLCV from US-LEGAL venues (Coinbase Exchange, Kraken fallback)
for a LONG-ONLY cross-sectional momentum study deployable by a US person.

Why these venues: a US person can legally trade spot on Coinbase/Kraken but CANNOT
short offshore perps (OKX/Binance/Bybit/dYdX geoblocked). So the universe is built ONLY
from coins with deep USD spot on Coinbase/Kraken -- no obscure alts.

Coinbase Exchange public candles: max 300 candles/request, paginate via start/end.
granularity=86400 (daily). No auth. We page backward to ~2019.
Kraken OHLC: returns only ~720 most-recent daily candles -> used ONLY as a fallback
for coins missing on Coinbase (none needed here; all target coins are on Coinbase USD).

Survivorship: Coinbase only serves currently-listed pairs => dead alts missing => UP bias.
We pick established liquid coins and document it. Volume is BASE volume; we convert to
quote (USD) volume = base_vol * close for the liquidity screen.

Output: /tmp/mlo_data/mlo_spot.parquet  (NON-repo staging)
"""
import urllib.request, json, time, os
import pandas as pd

OUT_DIR = "/tmp/mlo_data"
OUT = f"{OUT_DIR}/mlo_spot.parquet"

# Liquid USD-spot coins on Coinbase Advanced Trade / Kraken Pro.
# Built from deep-USD-spot majors; NO obscure alts. MATIC/POL excluded (delisted/migrated
# on Coinbase USD -> not cleanly tradeable spot). Mirrors the perp universe where the
# coin has deep US spot, so the long-only vs L/S comparison is apples-to-apples.
UNIVERSE = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "BCH",
    "DOT", "ATOM", "XLM", "UNI", "AAVE", "ETC", "FIL", "NEAR", "ALGO", "APT",
    "ARB", "OP", "SUI", "INJ", "ICP", "GRT", "CRV", "COMP", "SAND", "MANA",
    "AXS", "XTZ",
]

CB = "https://api.exchange.coinbase.com/products/{prod}/candles"


def fetch_coinbase(sym, start="2019-01-01", granularity=86400, sleep=0.18):
    """Page backward from now to `start`. Returns DataFrame or None."""
    prod = f"{sym}-USD"
    start_ts = pd.Timestamp(start, tz="UTC")
    rows = []
    end = pd.Timestamp.now("UTC").normalize()
    span = pd.Timedelta(seconds=granularity) * 300
    while end > start_ts:
        s = max(start_ts, end - span)
        url = (f"{CB.format(prod=prod)}?granularity={granularity}"
               f"&start={s.isoformat()}&end={end.isoformat()}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            print(f"  {sym} err {e}; retry once")
            time.sleep(1.5)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            except Exception as e2:
                print(f"  {sym} err again {e2}; stop")
                break
        if not isinstance(data, list) or not data:
            # empty page -> we've gone before listing
            break
        rows.extend(data)
        oldest = min(r[0] for r in data)
        new_end = pd.Timestamp(oldest, unit="s", tz="UTC")
        if new_end >= end:
            break
        end = new_end
        time.sleep(sleep)
    if not rows:
        return None
    # Coinbase candle: [time, low, high, open, close, volume]
    df = pd.DataFrame(rows, columns=["ts", "l", "h", "o", "c", "vol"])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="s", utc=True)
    for col in ["l", "h", "o", "c", "vol"]:
        df[col] = df[col].astype(float)
    df = df.drop_duplicates("ts").sort_values("ts")
    df["sym"] = sym
    df["volq"] = df["vol"] * df["c"]  # USD quote volume for liquidity screen
    return df[["ts", "sym", "o", "h", "l", "c", "vol", "volq"]]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = []
    for sym in UNIVERSE:
        df = fetch_coinbase(sym)
        if df is None or len(df) < 300:
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
