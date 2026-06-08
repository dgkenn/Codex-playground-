"""copy_live_multi.py -- validate live capture for ALL top-10%-by-MM-score wallets AT ONCE. They all
trade the SAME {btc,eth,sol,xrp}x{5m,15m} markets, so one shared CLOB WebSocket book feed (sub-second
fill-time touch) serves every wallet; we poll each wallet's fills round-robin and score them against
that shared touch. Per wallet we report the capture-vs-depth curve + the depth that hits 95% (= their
measured ladder width) + reconciliation. Goal: >=95% capture at a sane ladder depth for every wallet.

    python copy_live_multi.py [seconds]
Reads the top-10% list from mm_score.json. Read-only (CLOB /book WS + data-api /trades). Writes
copy_multi_result.json + copy_multi_capture.jsonl.
"""
from __future__ import annotations
import asyncio, collections, json, math, os, sys, threading, time
import requests, websockets

G = "https://gamma-api.polymarket.com"; D = "https://data-api.polymarket.com"
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
ASSETS = ["btc", "eth", "sol", "xrp"]; TENORS = [5, 15]
DEPTHS = [1, 2, 3, 5, 7, 10, 14, 20]
SANE_DEPTH = 20                 # a faithful ladder is <= this many ticks (+/-20c); deeper = not copyable


def top_wallets():
    mm = json.load(open("mm_score.json"))
    n = max(1, len(mm) // 10)
    return [r["w"] for r in mm[:n]]


def discover(sess):
    idx = {}; now = int(time.time())
    for a in ASSETS:
        for tn in TENORS:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=10).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; tk = json.loads(m["clobTokenIds"])
                    tick = float(m.get("orderPriceMinTickSize", 0.01) or 0.01)
                    idx[str(tk[0])] = tick; idx[str(tk[1])] = tick
                    break
    return idx


def analyze_file(path="copy_multi_capture.jsonl"):
    """offline per-wallet verdict from pooled fills: capture-vs-depth + depth-for-95% (= their ladder)."""
    W = collections.defaultdict(list)
    for ln in open(path):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        W[r["w"]].append(r["inside_tk"])
    mm = {r["w"][:10]: r for r in json.load(open("mm_score.json"))}
    print(f"{'wallet':>12}{'fills':>6}{'d3':>5}{'d7':>5}{'d14':>5}{'d20':>5}{'depth95':>8}{'status':>10}")
    ok = 0
    for w, ins in sorted(W.items(), key=lambda kv: -len(kv[1])):
        n = len(ins)
        cap = {d: round(100 * sum(1 for x in ins if -1 <= x <= d) / n, 1) for d in DEPTHS}
        d95 = next((d for d in DEPTHS if d <= SANE_DEPTH and cap[d] >= 95), None)
        status = "OK" if (n >= 20 and d95) else ("idle/few" if n < 20 else "deep/momentum")
        if status == "OK":
            ok += 1
        print(f"{w:>12}{n:>6}{cap[3]:>5.0f}{cap[7]:>5.0f}{cap[14]:>5.0f}{cap[20]:>5.0f}{(d95 or 0):>8}{status:>10}")
    print(f"\n{ok}/{len(W)} wallets seen reach >=95% at a sane ladder depth (>=20 fills). "
          f"Pool more (overnight) for the long tail; momentum/directional wallets won't fit a touch-ladder copy.")


def main():
    if "--analyze" in sys.argv:
        analyze_file(); return
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    wallets = top_wallets()
    idx = {}; touches = collections.defaultdict(lambda: collections.deque(maxlen=700)); last_app = {}
    lock = threading.Lock(); stop = threading.Event(); start = int(time.time())

    def ws_thread():
        nonlocal idx
        s = requests.Session()
        async def run():
            nonlocal idx
            last = 0
            while not stop.is_set():
                idx = discover(s); last = time.time(); toks = list(idx)
                if not toks:
                    await asyncio.sleep(3); continue
                try:
                    async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                        await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                        while not stop.is_set() and time.time() - last < 40:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                            except asyncio.TimeoutError:
                                continue
                            data = json.loads(raw); now = time.time()
                            def store(tok, bb, ba):
                                if (bb is None and ba is None) or now - last_app.get(tok, 0) < 0.5:
                                    return
                                last_app[tok] = now
                                with lock:
                                    touches[tok].append((now, bb, ba))
                            for m in (data if isinstance(data, list) else [data]):
                                et = m.get("event_type")
                                if et == "book":
                                    b = m.get("bids") or []; a = m.get("asks") or []
                                    store(str(m["asset_id"]), max((float(x["price"]) for x in b), default=None),
                                          min((float(x["price"]) for x in a), default=None))
                                elif et == "price_change":
                                    for pc in m.get("price_changes", []):
                                        store(str(pc["asset_id"]),
                                              float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else None,
                                              float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else None)
                except Exception:
                    await asyncio.sleep(2)
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(run())

    buf = collections.deque(); seen = set()

    def trade_thread():
        s = requests.Session(); i = 0
        while not stop.is_set():
            w = wallets[i % len(wallets)]; i += 1     # round-robin all wallets
            try:
                tr = s.get(D + "/trades", params={"user": w, "limit": 100}, timeout=12).json()
            except Exception:
                tr = []
            for t in tr if isinstance(tr, list) else []:
                k = w + t["transactionHash"] + str(t.get("asset")) + t["side"]
                if k in seen:
                    continue
                seen.add(k)
                with lock:
                    buf.append((w, t))
            time.sleep(max(0.3, 5.0 / len(wallets)))   # cycle all wallets ~every 5s

    threading.Thread(target=ws_thread, daemon=True).start()
    threading.Thread(target=trade_thread, daemon=True).start()

    def touch_at(tok, ts):
        with lock:
            snaps = [x for x in touches.get(tok, ()) if abs(x[0] - ts) <= 5]
        return min(snaps, key=lambda x: abs(x[0] - ts)) if snaps else None

    W = {w: {"tot": 0, "cap": {d: 0 for d in DEPTHS}, "dists": [], "miss": collections.Counter()} for w in wallets}
    fh = open("copy_multi_capture.jsonl", "a"); t_end = time.time() + dur
    print(f"multi-copy | {len(wallets)} wallets | shared WS book | {dur}s", flush=True)
    while time.time() < t_end:
        time.sleep(8)
        with lock:
            batch = list(buf); buf.clear()
        for w, t in batch:
            if int(t["timestamp"]) < start - 30 or time.time() - int(t["timestamp"]) > 120:
                continue
            a = W[w]; a["tot"] += 1
            tok = str(t["asset"]); p = float(t["price"]); side = t["side"]
            if tok not in idx:
                a["miss"]["not_tracked"] += 1; continue
            snap = touch_at(tok, int(t["timestamp"]))
            if snap is None:
                a["miss"]["no_book"] += 1; continue
            _, bb, ba = snap; tick = idx[tok]
            ref = bb if side == "BUY" else ba
            if ref is None:
                a["miss"]["no_book"] += 1; continue
            dist = (ref - p) if side == "BUY" else (p - ref)   # signed; >0 = inside our quote
            a["dists"].append(abs(p - ref))
            for d in DEPTHS:
                if -tick - 1e-9 <= dist <= d * tick + 1e-9:
                    a["cap"][d] += 1
            fh.write(json.dumps({"w": w[:10], "side": side, "p": p, "tick": tick,
                                 "inside_tk": round(dist / tick, 1)}) + "\n")   # captured@d iff -1<=inside_tk<=d
        fh.flush()
        # periodic per-wallet status (wallets with enough fills) + convergence count
        for w in wallets:
            a = W[w]
            if a["tot"] >= 15 and a["tot"] % 5 == 0:
                cv = {d: round(100 * a["cap"][d] / a["tot"]) for d in (3, 7, 14, 20)}
                print(f"    {w[:10]} n={a['tot']} cap%={cv}", flush=True)
        done = sum(1 for w in wallets if conv(W[w]))
        print(f"  t+{int(time.time())-start}s fills={sum(W[w]['tot'] for w in wallets)} "
              f"wallets>=95%@sane={done}/{len(wallets)}", flush=True)
    stop.set(); report(wallets, W, start, t_end)


def conv(a, target=95.0):
    if a["tot"] < 20:
        return False
    for d in DEPTHS:
        if d <= SANE_DEPTH and 100 * a["cap"][d] / a["tot"] >= target:
            return True
    return False


def report(wallets, W, start, t_end):
    s = requests.Session(); out = {}
    print("\n=== PER-WALLET CAPTURE (top 10% by MM score) ===")
    print(f"{'wallet':>12}{'fills':>6}{'d3':>5}{'d7':>5}{'d14':>5}{'d20':>5}{'depth95':>8}{'status':>9}")
    for w in wallets:
        a = W[w]; tot = a["tot"]
        cap = {d: round(100 * a["cap"][d] / max(1, tot), 1) for d in DEPTHS}
        ds = sorted(a["dists"]); d95 = (ds[min(len(ds) - 1, int(0.95 * len(ds)))] / 0.01) if ds else None
        depth_hit = next((d for d in DEPTHS if d <= SANE_DEPTH and cap[d] >= 95), None)
        status = "OK" if (tot >= 20 and depth_hit) else ("idle/few" if tot < 20 else "deep>20tk")
        out[w] = {"scored": tot, "capture": cap, "depth95_tk": round(d95, 1) if d95 else None,
                  "depth_for_95": depth_hit, "status": status, "misses": dict(a["miss"])}
        print(f"{w[:10]:>12}{tot:>6}{cap[3]:>5.0f}{cap[7]:>5.0f}{cap[14]:>5.0f}{cap[20]:>5.0f}"
              f"{(round(d95,1) if d95 else 0):>8}{status:>9}")
    json.dump(out, open("copy_multi_result.json", "w"))
    ok = sum(1 for w in out if out[w]["status"] == "OK")
    enough = sum(1 for w in out if out[w]["scored"] >= 20)
    print(f"\nGOAL: {ok}/{len(wallets)} wallets captured >=95% at a sane ladder depth "
          f"({enough} had >=20 fills this run). Wallets with few fills need more overnight cycles "
          f"(copy-validate-multi.yml accumulates on gha-data; copy_agg pools).")


if __name__ == "__main__":
    main()
