#!/usr/bin/env python3
"""kalshi_favlong_candle.py -- DEFINITIVE favorite-longshot calibration on Kalshi soft
markets using real CANDLESTICK history (fixes the settled-snapshot price problem in
kalshi_favlong_scan.py / KALSHI_FAVLONG_SCAN.md).

For each liquid, single-outcome (non-mve) settled binary market: pull 60s candlesticks,
take the MID-LIFE candle (50% between open and close) with a valid two-sided quote as a
realistic buy-and-hold entry, record (mid, yes_bid, yes_ask, result). Bin by mid; report
realized WR vs mid, the SPREAD distribution (the taker killer), and net-of-fee taker EV
at the ask for buy-YES (favorites) / buy-NO (overpriced longshots). Public API, no auth.

    python kalshi_favlong_candle.py
"""
import urllib.request, json, time, urllib.parse, datetime as dt
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATS = ["Economics", "Politics", "Entertainment", "Science and Technology",
        "World", "Companies", "Climate and Weather"]
FEE = lambda p: 0.07 * p * (1 - p)
BANDS = [(i/20, (i+1)/20) for i in range(20)]
MAXSPREAD = 0.10
MAXMKTS = 700          # cap total candlestick fetches


def get(path, params=""):
    u = f"{BASE}{path}" + ("?" + params if params else "")
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "r"}), timeout=25))
        except Exception:
            if a == 3:
                raise
            time.sleep(1.2*(a+1))


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) if s else None


def series_for(cat, cap=40):
    out, cur = [], ""
    while len(out) < cap:
        d = get("/series", f"category={urllib.parse.quote(cat)}&limit=100" + (f"&cursor={cur}" if cur else ""))
        out += [s["ticker"] for s in d.get("series", []) if s.get("ticker")]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out[:cap]


def settled(series_ticker, cap=80):
    out, cur = [], ""
    while len(out) < cap:
        d = get("/markets", f"series_ticker={series_ticker}&status=settled&limit=100" + (f"&cursor={cur}" if cur else ""))
        ms = d.get("markets", [])
        out += ms
        cur = d.get("cursor") or ""
        if not cur or not ms:
            break
    return out[:cap]


def midlife_quote(series, m):
    """Pull candlesticks, return (yes_bid, yes_ask) of the candle nearest mid-life with a
    valid two-sided quote, else None."""
    o, c = ts(m.get("open_time")), ts(m.get("close_time"))
    if not o or not c or c <= o:
        return None
    try:
        cc = get(f"/series/{series}/markets/{m['ticker']}/candlesticks",
                 f"start_ts={o}&end_ts={c}&period_interval=60")
    except Exception:
        return None
    cs = cc.get("candlesticks", [])
    if not cs:
        return None
    target = (o + c) / 2
    cs.sort(key=lambda k: abs((k.get("end_period_ts") or 0) - target))
    for k in cs:
        yb = fnum((k.get("yes_bid") or {}).get("close_dollars"))
        ya = fnum((k.get("yes_ask") or {}).get("close_dollars"))
        if yb is None or ya is None:
            continue
        if 0 < yb < ya < 1 and (ya - yb) <= MAXSPREAD:
            return (yb, ya)
    return None


def main():
    rows, seen, nfetch = [], set(), 0
    for cat in CATS:
        try:
            sers = series_for(cat)
        except Exception:
            continue
        n0 = len(rows)
        for st in sers:
            if nfetch >= MAXMKTS:
                break
            try:
                ms = settled(st)
            except Exception:
                continue
            for m in ms:
                if nfetch >= MAXMKTS:
                    break
                tk = m.get("ticker")
                if tk in seen:
                    continue
                seen.add(tk)
                if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type") != "binary"):
                    continue
                if (m.get("result") or "").lower() not in ("yes", "no"):
                    continue
                if (fnum(m.get("volume_fp")) or 0) < 500:
                    continue
                nfetch += 1
                q = midlife_quote(st, m)
                if q is None:
                    continue
                bid, ask = q
                rows.append((cat, bid, ask, (bid+ask)/2, 1 if m["result"].lower() == "yes" else 0))
        print(f"[{cat}] series={len(sers)} fetched~{nfetch} usable={len(rows)-n0}", flush=True)
    print(f"\nTOTAL usable mid-life quotes: {len(rows)}  (candlestick fetches: {nfetch})\n")
    if len(rows) < 50:
        print("too few; the soft-market liquid+two-sided subset is genuinely sparse."); return

    sp = sorted(a-b for _, b, a, _, _ in rows)
    print(f"mid-life spread (ask-bid): median={sp[len(sp)//2]*100:.1f}c  "
          f"p25={sp[len(sp)//4]*100:.1f}c  p90={sp[int(len(sp)*0.9)]*100:.1f}c\n")

    print("CALIBRATION (real mid-life price): realized YES-rate vs mid; taker EV at the ask")
    print(f"{'band':>12} {'n':>5} {'mid':>6} {'realWR':>7} {'bias_pp':>8} "
          f"{'EV_takeYES':>11} {'EV_takeNO':>10} {'best':>8}")
    anypos = False
    for lo, hi in BANDS:
        b = [(bd, ak, w) for c, bd, ak, mid, w in rows if lo <= mid < hi]
        if len(b) < 20:
            continue
        n = len(b); mmid = sum((x+y)/2 for x, y, _ in b)/n; wr = sum(w for _, _, w in b)/n
        ev_yes = sum(w - ak - FEE(ak) for _, ak, w in b)/n
        ev_no = sum((1-w) - (1-bd) - FEE(1-bd) for bd, _, w in b)/n
        best = max(ev_yes, ev_no); anypos = anypos or best > 0
        print(f"{lo:.2f}-{hi:.2f} {n:>5} {mmid:>6.3f} {wr:>7.3f} {(wr-mmid)*100:>+8.1f} "
              f"{ev_yes*100:>+10.2f}c {ev_no*100:>+9.2f}c {best*100:>+7.2f}c{'  <== +EV' if best>0 else ''}")
    print("\nPER-CATEGORY bias (realWR - mid):")
    bycat = defaultdict(list)
    for c, bd, ak, mid, w in rows:
        bycat[c].append((mid, w))
    for c in CATS:
        b = bycat.get(c, [])
        if len(b) < 25:
            print(f"  {c:>24}: n={len(b)} (too few)"); continue
        mp = sum(p for p, _ in b)/len(b); wr = sum(w for _, w in b)/len(b)
        print(f"  {c:>24}: n={len(b):>4} mid={mp:.3f} realWR={wr:.3f} bias={(wr-mp)*100:+.1f}pp")
    print(f"\nVERDICT: {'a band shows +EV net of fee at the ask -- investigate sizing/OOS' if anypos else 'NO band clears the fee at the ask -- taker favorite-longshot is dead on soft Kalshi too'}.")


if __name__ == "__main__":
    main()
