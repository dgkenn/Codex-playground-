"""Fetch the REMAINING dYdX funding assets quickly (~400d cap) and merge into the
existing funding_daily.parquet. Splitting the fetch keeps each run inside the
shell timeout; ~400d is enough for a recent-regime carry test."""
import urllib.request, json, time, os
import pandas as pd

OUT = "/tmp/cx_multifactor"
PARQ = f"{OUT}/funding_daily.parquet"
DYDX = "https://indexer.dydx.trade/v4/historicalFunding"
REST = ["XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC"]
MAX_PAGES = 100   # ~100*100 hourly = 10000 rows ~ 415 days


def get(url, tries=8):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            time.sleep((3.0 if e.code in (403, 429) else 1.0) * (i + 1))
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None


def fetch(asset):
    rows, before = [], None
    for _ in range(MAX_PAGES):
        url = f"{DYDX}/{asset}-USD?limit=100" + (f"&effectiveBeforeOrAt={before}" if before else "")
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
        time.sleep(0.15)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["effectiveAt", "rate"]).drop_duplicates("effectiveAt")
    df["ts"] = pd.to_datetime(df["effectiveAt"], utc=True)
    return df.set_index("ts")["rate"].resample("1D").sum()


def main():
    base = pd.read_parquet(PARQ) if os.path.exists(PARQ) else pd.DataFrame()
    cols = {c: base[c] for c in base.columns}
    for a in REST:
        s = fetch(a)
        if s is None or len(s) < 100:
            print("SKIP", a, flush=True); continue
        cols[a] = s
        print(f"{a}: {len(s)} daily {s.index.min().date()}->{s.index.max().date()} "
              f"ann={s.mean()*365*100:.1f}%", flush=True)
        pd.concat(cols, axis=1).sort_index().to_parquet(PARQ)
    out = pd.concat(cols, axis=1).sort_index()
    out.to_parquet(PARQ)
    print("SAVED", out.shape, list(out.columns), flush=True)


if __name__ == "__main__":
    main()
