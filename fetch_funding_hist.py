"""Fetch DEEP funding-rate history for a carry factor.

OKX public funding-rate-history hard-caps at ~3 months (confirmed: paging past
~2026-03-12 returns 0 rows). dYdX v4 indexer `historicalFunding` paginates back
to ~2025-02 (hourly funding) -> our usable carry-factor history source.

We aggregate dYdX hourly funding to DAILY (sum of the 24 hourly rates) so it
aligns with the daily OHLCV bars used by the price factors. Saved to
/tmp/cx_multifactor/funding_daily.parquet (NOT committed).
"""
import urllib.request, json, time, os
import pandas as pd

OUT = "/tmp/cx_multifactor"
os.makedirs(OUT, exist_ok=True)

# dYdX tickers map to BASE-USD. Match the price universe where dYdX lists them.
ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC"]
DYDX = "https://indexer.dydx.trade/v4/historicalFunding"


def get(url, tries=8):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(3.0 * (i + 1))   # rate-limited: longer backoff
            else:
                time.sleep(1.0 * (i + 1))
            if i == tries - 1:
                print("  FAIL", url, e.code, flush=True)
        except Exception as e:
            time.sleep(1.5 * (i + 1))
            if i == tries - 1:
                print("  FAIL", url, str(e)[:50], flush=True)
    return None


def fetch_dydx(asset, max_pages=170):
    # ~170 pages * 100 hourly rows = 17000 rows ~ 2 years -> plenty for OOS + 18mo holdout.
    ticker = f"{asset}-USD"
    rows = []
    before = None
    for p in range(max_pages):
        url = f"{DYDX}/{ticker}?limit=100" + (f"&effectiveBeforeOrAt={before}" if before else "")
        d = get(url)
        if not d:
            break
        hf = d.get("historicalFunding", [])
        if not hf:
            break
        for r in hf:
            rows.append((r["effectiveAt"], float(r["rate"])))
        before = hf[-1]["effectiveAt"]
        if len(hf) < 100:
            break
        time.sleep(0.35)   # gentle pacing to avoid dYdX 403/429
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["effectiveAt", "rate"]).drop_duplicates("effectiveAt")
    df["ts"] = pd.to_datetime(df["effectiveAt"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def main():
    daily = {}
    for a in ASSETS:
        df = fetch_dydx(a)
        if df is None or len(df) < 100:
            print(f"SKIP {a}: insufficient ({0 if df is None else len(df)})")
            continue
        # aggregate hourly funding -> daily sum (the cost/credit of holding 1d)
        s = df.set_index("ts")["rate"].resample("1D").sum()
        daily[a] = s
        print(f"{a}: {len(df)} hourly rows {df.ts.min().date()} -> {df.ts.max().date()} "
              f"| {len(s)} daily | mean_ann={s.mean()*365*100:.2f}%", flush=True)
        # save incrementally so a stall mid-run still leaves usable data
        pd.concat(daily, axis=1).sort_index().to_parquet(f"{OUT}/funding_daily.parquet")
    out = pd.concat(daily, axis=1).sort_index()
    out.to_parquet(f"{OUT}/funding_daily.parquet")
    print("SAVED", out.shape, out.index.min(), "->", out.index.max(), flush=True)


if __name__ == "__main__":
    main()
