"""Feed race: which BTC signal is fastest AND which best LEADS the Polymarket token mid?

Runs several free BTC WS feeds + the Polymarket token book concurrently with local timestamps:
  coinbase, kraken, binance (geo-block tolerated), and the TOKEN'S OWN microprice ("the book"
  -- what most participants trade off). Then measures:
    (1) raw update rate per feed (ticks/s),
    (2) cross-feed lead (which BTC venue prints a move first),
    (3) lead vs the token MID: cross-correlate each signal's changes against token-mid changes
        at +/- lags -> a positive peak lag = that signal LEADS the token (exploitable).
The decisive comparison: does any BTC feed lead the token mid MORE than the book microprice does?
If the book already leads as much/more, BTC feeds add nothing; if a BTC feed leads further out,
that's the edge.  python feed_race.py [seconds]
"""
import asyncio, json, time, sys
import requests, websockets
import numpy as np
from paper_trader_ws import WS, active_market

DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 210
ev = []   # (t_local, source, value)


async def coinbase():
    try:
        async with websockets.connect("wss://ws-feed.exchange.coinbase.com", ping_interval=15) as ws:
            await ws.send(json.dumps({"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]}))
            t0 = time.time()
            async for raw in ws:
                if time.time() - t0 > DUR: break
                m = json.loads(raw)
                if m.get("type") == "ticker" and m.get("price"):
                    ev.append((time.time(), "coinbase", float(m["price"])))
    except Exception as e:
        print("coinbase WS down:", str(e)[:80])


async def kraken():
    try:
        async with websockets.connect("wss://ws.kraken.com", ping_interval=15) as ws:
            await ws.send(json.dumps({"event": "subscribe", "pair": ["XBT/USD"], "subscription": {"name": "ticker"}}))
            t0 = time.time()
            async for raw in ws:
                if time.time() - t0 > DUR: break
                m = json.loads(raw)
                if isinstance(m, list) and len(m) > 1 and isinstance(m[1], dict) and "c" in m[1]:
                    ev.append((time.time(), "kraken", float(m[1]["c"][0])))
    except Exception as e:
        print("kraken WS down:", str(e)[:80])


async def binance():
    try:
        async with websockets.connect("wss://stream.binance.com:9443/ws/btcusdt@bookTicker", ping_interval=15) as ws:
            t0 = time.time()
            async for raw in ws:
                if time.time() - t0 > DUR: break
                m = json.loads(raw)
                if "b" in m and "a" in m:
                    ev.append((time.time(), "binance", (float(m["b"]) + float(m["a"])) / 2))
    except Exception as e:
        print("binance WS down (often geo-blocked on US runners):", str(e)[:80])


async def polymarket(up):
    try:
        tob = [None, 0, None, 0]
        async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
            await ws.send(json.dumps({"assets_ids": [up], "type": "market"}))
            t0 = time.time()
            async for raw in ws:
                if time.time() - t0 > DUR: break
                for m in (json.loads(raw) if raw.strip().startswith("[") else [json.loads(raw)]):
                    if str(m.get("asset_id")) != up:
                        continue
                    et = m.get("event_type")
                    if et == "book":
                        bids = m.get("bids") or []; asks = m.get("asks") or []
                        bb = max((float(b["price"]) for b in bids), default=tob[0])
                        ba = min((float(a["price"]) for a in asks), default=tob[2])
                        bsz = sum(float(b["size"]) for b in bids if float(b["price"]) == bb) if bids else tob[1]
                        asz = sum(float(a["size"]) for a in asks if float(a["price"]) == ba) if asks else tob[3]
                        tob = [bb, bsz, ba, asz]
                    elif et == "price_change":
                        for pc in m.get("price_changes", []):
                            if str(pc.get("asset_id")) != up: continue
                            if pc.get("best_bid"): tob[0] = float(pc["best_bid"])
                            if pc.get("best_ask"): tob[2] = float(pc["best_ask"])
                    if tob[0] is not None and tob[2] is not None:
                        t = time.time(); mid = (tob[0] + tob[2]) / 2
                        tot = (tob[1] or 0) + (tob[3] or 0)
                        mic = mid if tot <= 0 else tob[0] + (tob[2] - tob[0]) * (tob[1] or 0) / tot
                        ev.append((t, "pmid", mid)); ev.append((t, "pmicro", mic))
    except Exception as e:
        print("polymarket WS down:", str(e)[:80])


def series(src, grid):
    pts = sorted((t, v) for (t, s, v) in ev if s == src)
    if len(pts) < 5: return None
    out = np.full(len(grid), np.nan); j = 0
    for i, g in enumerate(grid):
        while j + 1 < len(pts) and pts[j + 1][0] <= g:
            j += 1
        if pts[j][0] <= g:
            out[i] = pts[j][1]
    return out


def lead_vs(sig, mid, maxlag=10):
    ds = np.diff(sig); dm = np.diff(mid)
    best = (0, 0.0)
    for k in range(-maxlag, maxlag + 1):
        if k >= 0:
            a, b = ds[:len(ds) - k], dm[k:]
        else:
            a, b = ds[-k:], dm[:len(dm) + k]
        n = min(len(a), len(b))
        m = np.isfinite(a[:n]) & np.isfinite(b[:n])
        if m.sum() < 30 or a[:n][m].std() == 0 or b[:n][m].std() == 0: continue
        c = np.corrcoef(a[:n][m], b[:n][m])[0, 1]
        if abs(c) > abs(best[1]): best = (k, c)
    return best


async def main():
    sess = requests.Session()
    mk = active_market(sess)
    if not mk:
        print("no active Polymarket BTC market"); return
    up = mk["up"]
    print(f"racing feeds for {DUR}s on token {up[:12]}...\n")
    await asyncio.gather(coinbase(), kraken(), binance(), polymarket(up))
    srcs = sorted(set(s for _, s, _ in ev))
    span = (max(t for t, _, _ in ev) - min(t for t, _, _ in ev)) if ev else 1
    print("=== (1) raw update rate ===")
    for s in srcs:
        c = sum(1 for _, ss, _ in ev if ss == s)
        print(f"  {s:10} {c:6d} ticks  ({c/span:.1f}/s)")
    GRID = 0.5
    t0 = min(t for t, _, _ in ev); t1 = max(t for t, _, _ in ev)
    grid = np.arange(t0, t1, GRID)
    mid = series("pmid", grid)
    if mid is None or np.isfinite(mid).sum() < 40:
        print("\n(token mid moved too little in this window to measure lead-lag reliably; rerun longer)")
        return
    print(f"\n=== (2) lead vs TOKEN MID (grid {GRID}s; lag>0 => signal LEADS the token) ===")
    print(f"  {'signal':10} {'peak lag':>9} {'corr':>7}")
    for s in ["coinbase", "kraken", "binance", "pmicro"]:
        sig = series(s, grid)
        if sig is None: continue
        k, c = lead_vs(sig, mid)
        tag = " <- BOOK" if s == "pmicro" else ""
        print(f"  {s:10} {k*GRID:>+8.1f}s {c:>+7.3f}{tag}")
    print("\nREAD: compare each BTC feed's lead to pmicro (the book). A BTC feed only adds edge if it "
          "leads the token mid MORE (further-out positive lag / higher corr) than the book already does.")


if __name__ == "__main__":
    asyncio.run(main())
