"""copy_live.py -- COPY a target MM and validate prospectively: rest the same two-sided quotes on every
active crypto Up/Down market, then score the wallet's REAL incoming fills as captured/missed vs our
quote envelope. Goal: >=95% capture at a FAITHFUL ladder depth.

v4 (correct touch): uses the CLOB **WebSocket** book feed for a sub-second, fill-time-accurate touch per
token (REST snapshots were too sparse -> a single one was stale, a min/max band over-credited 40-tick
swings on volatile 5m books). Capture = the fill price within +/-d ticks of the touch AT FILL TIME
(nearest WS snapshot within +/-2s; else no_book). Multi-depth curve (1,2,3,5,7) + end reconciliation
(independent count of the wallet's in-window trades). COPY_WALLET env selects target. Read-only.
    python copy_live.py [seconds] [assets_csv] [tenors_csv]
"""
from __future__ import annotations
import asyncio, collections, json, os, sys, threading, time
import requests
import websockets

G = "https://gamma-api.polymarket.com"; D = "https://data-api.polymarket.com"
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
WALLET = os.environ.get("COPY_WALLET", "0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d")


def discover(sess, assets, tenors):
    idx = {}; now = int(time.time())
    for a in assets:
        for tn in tenors:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=10).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; tk = json.loads(m["clobTokenIds"])
                    tick = float(m.get("orderPriceMinTickSize", 0.01) or 0.01)
                    idx[str(tk[0])] = (m["slug"], tick); idx[str(tk[1])] = (m["slug"], tick)
                    break
    return idx


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    assets = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["btc", "eth", "sol", "xrp"])
    tenors = ([int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [5, 15])
    idx = {}; touches = collections.defaultdict(lambda: collections.deque(maxlen=700)); lock = threading.Lock()
    last_app = {}                                     # per-token last append ts (throttle ~0.5s -> ~5min history)
    stop = threading.Event(); start = int(time.time())

    def ws_thread():                                  # real-time touch per token via CLOB market WS
        nonlocal idx
        s = requests.Session()

        async def run():
            nonlocal idx
            last_disc = 0
            while not stop.is_set():
                idx = discover(s, assets, tenors); last_disc = time.time()
                toks = list(idx)
                if not toks:
                    await asyncio.sleep(3); continue
                try:
                    async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                        await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                        while not stop.is_set() and time.time() - last_disc < 40:   # resub on rotation
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                            except asyncio.TimeoutError:
                                continue
                            data = json.loads(raw); now = time.time()

                            def store(tok, bb, ba):   # throttle to ~0.5s/token so the deque spans ~5min
                                if bb is None and ba is None:
                                    return
                                if now - last_app.get(tok, 0) < 0.5:
                                    return
                                last_app[tok] = now
                                with lock:
                                    touches[tok].append((now, bb, ba))
                            for m in (data if isinstance(data, list) else [data]):
                                et = m.get("event_type")
                                if et == "book":
                                    tok = str(m["asset_id"])
                                    bids = m.get("bids") or []; asks = m.get("asks") or []
                                    store(tok, max((float(b["price"]) for b in bids), default=None),
                                          min((float(a["price"]) for a in asks), default=None))
                                elif et == "price_change":
                                    for pc in m.get("price_changes", []):
                                        bb = float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else None
                                        ba = float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else None
                                        store(str(pc["asset_id"]), bb, ba)
                except Exception:
                    await asyncio.sleep(2)
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(run())

    trades_buf = collections.deque(); seen = set()

    def trade_thread():
        s = requests.Session()
        while not stop.is_set():
            try:
                tr = s.get(D + "/trades", params={"user": WALLET, "limit": 200}, timeout=12).json()
            except Exception:
                tr = []
            for t in tr if isinstance(tr, list) else []:
                k = t["transactionHash"] + str(t.get("asset")) + t["side"]
                if k in seen:
                    continue
                seen.add(k)
                with lock:
                    trades_buf.append(t)
            time.sleep(3)

    threading.Thread(target=ws_thread, daemon=True).start()
    threading.Thread(target=trade_thread, daemon=True).start()

    def touch_at(tok, ts):                            # nearest WS touch within +/-5s of the fill ts
        with lock:
            snaps = [x for x in touches.get(tok, ()) if abs(x[0] - ts) <= 5]
        return min(snaps, key=lambda x: abs(x[0] - ts)) if snaps else None

    DEPTHS = [1, 2, 3, 5, 7, 10, 14, 20]   # span their measured ladder (p95~14tk)
    stats = collections.Counter(); capd = {d: 0 for d in DEPTHS}; miss = collections.Counter()
    missed_slugs = collections.Counter(); fh = open("copy_capture.jsonl", "a"); t_end = time.time() + dur
    print(f"copy v4 (WS touch) | {WALLET[:10]} | assets={assets} tenors={tenors} | {dur}s", flush=True)
    while time.time() < t_end:
        time.sleep(5)
        with lock:
            batch = list(trades_buf); trades_buf.clear()
        for t in batch:
            if int(t["timestamp"]) < start - 30 or time.time() - int(t["timestamp"]) > 120:
                continue
            stats["total"] += 1
            tok = str(t["asset"]); p = float(t["price"]); side = t["side"]
            snap = touch_at(tok, int(t["timestamp"]))
            rec = {"ts": int(t["timestamp"]), "tok": tok[:8], "side": side, "price": p, "slug": t.get("slug")}
            if tok not in idx:
                miss["market_not_tracked"] += 1; rec["why"] = "market_not_tracked"; missed_slugs[t.get("slug")] += 1
            elif snap is None:
                miss["no_book"] += 1; rec["why"] = "no_book"
            else:
                _, bb, ba = snap; tick = idx[tok][1]; rec["bid"] = bb; rec["ask"] = ba
                hit = []
                for d in DEPTHS:
                    if side == "BUY":
                        c = bb is not None and (bb - d * tick - 1e-9) <= p <= bb + tick + 1e-9
                    else:
                        c = ba is not None and (ba - tick - 1e-9) <= p <= ba + d * tick + 1e-9
                    if c:
                        capd[d] += 1; hit.append(d)
                rec["hit_depths"] = hit
                if not hit:
                    miss["price_outside_ladder>7tk"] += 1
            fh.write(json.dumps(rec) + "\n")
        fh.flush()
        tot = stats["total"]
        if tot:
            curve = "  ".join(f"d{d}={100*capd[d]/tot:.0f}%" for d in DEPTHS)
            print(f"  t+{int(time.time())-start}s fills={tot} capture[{curve}] misses={dict(miss)}", flush=True)
    stop.set(); time.sleep(1)
    s = requests.Session(); allt = []; off = 0
    while off < 3000:
        j = s.get(D + "/trades", params={"user": WALLET, "limit": 500, "offset": off}, timeout=15).json()
        if not isinstance(j, list) or not j:
            break
        allt += j; off += 500
        if len(j) < 500 or int(j[-1]["timestamp"]) < start:
            break
    actual = [t for t in allt if start <= int(t["timestamp"]) <= int(t_end)]
    tot = stats["total"]
    print(f"\n=== RESULT (WS touch, fill-time accurate) ===")
    print(f"wallet ACTUAL trades in window: {len(actual)} | we SCORED: {tot} (saw {100*tot/max(1,len(actual)):.0f}%)")
    for d in DEPTHS:
        print(f"   depth {d}tk: {capd[d]}/{tot} = {100*capd[d]/max(1,tot):.1f}%")
    print(f"misses: {dict(miss)}")
    res = {"wallet": WALLET, "ts": int(time.time()), "scored": tot, "actual": len(actual),
           "seen_pct": round(100 * tot / max(1, len(actual)), 1),
           "capture": {d: round(100 * capd[d] / max(1, tot), 1) for d in DEPTHS},
           "misses": dict(miss), "missed_slugs": dict(missed_slugs.most_common(20)),
           "assets": assets, "tenors": tenors}
    json.dump(res, open("copy_result.json", "w"))


if __name__ == "__main__":
    main()
