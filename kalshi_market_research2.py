#!/usr/bin/env python3
"""Kalshi public API market research — compact, token-light."""
import requests
import time

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HDR = {"Accept": "application/json"}

def get(path, params=None):
    try:
        r = requests.get(BASE + path, headers=HDR, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def sleep():
    time.sleep(0.2)

# ── 1. Series discovery ──────────────────────────────────────────────────────
CATS = ["Financials", "Economics", "Climate and Weather", "World", "Companies", "Crypto", None]
all_series = {}  # ticker -> {title, category, freq}
cat_counts = {}

for cat in CATS:
    p = {"limit": 200}
    if cat:
        p["category"] = cat
    d = get("/series", p); sleep()
    items = (d or {}).get("series", [])
    cat_counts[cat or "None"] = len(items)
    for s in items:
        t = s.get("ticker","")
        if t and t not in all_series:
            all_series[t] = {
                "title": s.get("title",""),
                "category": s.get("category", cat or ""),
                "freq": s.get("frequency",""),
                "raw": s,
            }

# ── 2. Filter: non-crypto, interesting for daily box trading ─────────────────
# Target series tickers manually selected from known Kalshi universe
# + anything with daily/weekly/month frequency
PRIORITY_TICKERS = [
    # S&P / Nasdaq / equities
    "KXSPX", "KXNDX", "KXSPY", "KXQQQ", "KXSPXD", "KXNDXD",
    "INXD", "INXW", "NDXD", "NDXW",
    # Economics
    "KXCPI", "KXNFP", "KXGDP", "KXFOMC", "CPIM", "NFPM", "GDPQ",
    # Treasury / rates
    "KXFED", "FED", "SOFR", "TBILL", "KXFFR",
    # Weather / climate
    "KXHURRICANE", "KXTEMP", "KXRAIN", "KXSNOW", "WXNYC", "WXCHI",
    "HIGHS", "LOWS", "PRECIP",
    # FX
    "KXEUR", "KXGBP", "KXJPY", "EURUSD", "GBPUSD",
    # Oil / energy
    "KXOIL", "KXNG", "OILD", "NGD",
    # Range / other
    "KXRANGE", "RANGESPX",
]

# Build candidate list: priority first, then scan all series for daily keywords
DAILY_KW = ["day","daily","24h","week","month","cpi","nfp","gdp","fomc","spx","ndx",
            "snp","nasdaq","weather","temp","rain","snow","treasury","yield","rate",
            "fx","eur","gbp","jpy","usd","oil","gas","range","hurricane","precip"]

candidates = []
seen_tickers = set()

# Add priority
for tk in PRIORITY_TICKERS:
    if tk in all_series and tk not in seen_tickers:
        candidates.append(tk)
        seen_tickers.add(tk)

# Add from all_series matching keywords, skip crypto
for tk, s in all_series.items():
    if tk in seen_tickers:
        continue
    cat = s["category"].lower()
    if "crypto" in cat:
        continue
    text = (tk + " " + s["title"] + " " + s["freq"]).lower()
    if any(kw in text for kw in DAILY_KW):
        candidates.append(tk)
        seen_tickers.add(tk)
    if len(candidates) >= 60:
        break

# ── 3. Fetch open markets for candidates ────────────────────────────────────
market_stats = []

for tk in candidates[:60]:
    d = get("/markets", {"series_ticker": tk, "status": "open", "limit": 20}); sleep()
    mkts = (d or {}).get("markets", [])
    if not mkts:
        continue
    s = mkts[0]
    yb = (s.get("yes_bid") or 0) / 100 if (s.get("yes_bid") or 0) > 1 else (s.get("yes_bid") or 0)
    nb = (s.get("no_bid") or 0) / 100 if (s.get("no_bid") or 0) > 1 else (s.get("no_bid") or 0)
    vol = s.get("volume_24h") or s.get("volume") or 0
    oi = s.get("open_interest") or 0
    bm = round(100 * (1 - yb - nb), 2)
    ct = (s.get("close_time","") or "")[:10]
    series_info = all_series.get(tk, {})
    tenor = "?"
    txt = (tk + " " + series_info.get("title","") + " " + series_info.get("freq","")).lower()
    if any(w in txt for w in ["daily","day","24h"]): tenor = "daily"
    elif "week" in txt: tenor = "weekly"
    elif "month" in txt: tenor = "monthly"
    market_stats.append({
        "s": tk, "cat": series_info.get("category","?")[:13],
        "tenor": tenor, "n": len(mkts),
        "yb": yb, "nb": nb, "bm": bm, "vol": vol, "oi": oi,
        "close": ct, "sample_mkt": s.get("ticker",""),
    })

# ── 4. Daily crypto series ───────────────────────────────────────────────────
CRYPTO_TKS = ["KXBTCDAY","KXBTCD","KXBTC24H","KXETHDAY","KXETCDAY","KXBTC","KXETH","KXBTCDRANGE"]
for tk in CRYPTO_TKS:
    d = get("/markets", {"series_ticker": tk, "status": "open", "limit": 5}); sleep()
    mkts = (d or {}).get("markets", [])
    if not mkts:
        continue
    s = mkts[0]
    yb = (s.get("yes_bid") or 0) / 100 if (s.get("yes_bid") or 0) > 1 else (s.get("yes_bid") or 0)
    nb = (s.get("no_bid") or 0) / 100 if (s.get("no_bid") or 0) > 1 else (s.get("no_bid") or 0)
    vol = s.get("volume_24h") or s.get("volume") or 0
    oi = s.get("open_interest") or 0
    bm = round(100 * (1 - yb - nb), 2)
    market_stats.append({
        "s": tk, "cat": "Crypto",
        "tenor": "daily", "n": len(mkts),
        "yb": yb, "nb": nb, "bm": bm, "vol": vol, "oi": oi,
        "close": (s.get("close_time","") or "")[:10],
        "sample_mkt": s.get("ticker",""),
    })

# ── 5. Orderbook depth for top viable ────────────────────────────────────────
viable = sorted([m for m in market_stats if m["bm"] > 0],
                key=lambda x: (-x["bm"], -x["vol"]))
top = viable[:8]
ob_results = []
for m in top:
    mt = m["sample_mkt"]
    if not mt: continue
    d = get(f"/markets/{mt}/orderbook"); sleep()
    if not d: continue
    ob = d.get("orderbook", d)
    def parse(side):
        if not side: return None, 0
        first = side[0]
        if isinstance(first, list): p, q = first[0], first[1]
        elif isinstance(first, dict): p, q = first.get("price",0), first.get("quantity", first.get("size",0))
        else: return None, 0
        return (p/100 if p > 1 else p), q
    yp, yq = parse(ob.get("yes",[]))
    np_, nq = parse(ob.get("no",[]))
    ob_results.append({"mkt": mt, "series": m["s"], "yp": yp, "yq": yq, "np": np_, "nq": nq})

# ── PRINT SUMMARY ─────────────────────────────────────────────────────────────
print("="*72)
print("SERIES_DISCOVERY:")
print(f"  Total unique series fetched: {len(all_series)}")
for cat, cnt in cat_counts.items():
    print(f"  {cat}: {cnt} series")
print()
print(f"  Sample non-crypto series (first 30 candidates found):")
for tk in candidates[:30]:
    s = all_series.get(tk,{})
    print(f"    {tk:<20} | {s.get('category','')[:20]:<20} | {s.get('title','')[:50]}")

print()
print("="*72)
print("MARKET_STATS:")
print(f"  {'Series':<18} {'Cat':<14} {'Tnr':<7} {'#':<4} {'YBid':<7} {'NBid':<7} {'BxMgn¢':<9} {'Vol24h':<10} {'OI'}")
print("  " + "-"*85)
for m in sorted(market_stats, key=lambda x: -x["bm"])[:40]:
    print(f"  {m['s']:<18} {m['cat']:<14} {m['tenor']:<7} {m['n']:<4} "
          f"{m['yb']:<7.2f} {m['nb']:<7.2f} {m['bm']:<9.2f} {int(m['vol']):<10} {int(m['oi'])}")

print(f"\n  Viable series (box_margin > 0): {len(viable)}")
print(f"  Of those with vol_24h > 0:      {sum(1 for m in viable if m['vol']>0)}")

print()
print("="*72)
print("ORDERBOOK_DEPTH (top viable series):")
print(f"  {'Market':<35} {'Series':<18} {'BestYB':<8} {'QtyY':<7} {'BestNB':<8} {'QtyN'}")
print("  " + "-"*80)
for o in ob_results:
    yp_s = f"{o['yp']:.2f}" if o['yp'] is not None else "N/A"
    np_s = f"{o['np']:.2f}" if o['np'] is not None else "N/A"
    print(f"  {o['mkt']:<35} {o['series']:<18} {yp_s:<8} {o['yq']:<7} {np_s:<8} {o['nq']}")

print()
print("Done.")
