"""orderflow_probe.py -- recover the ORDER LIFECYCLE (placements / cancels / fills) from the PUBLIC CLOB
WS book deltas, which I'd wrongly called invisible. Each `price_change` carries the NEW size at a level;
diffing it over time:  size UP = order(s) PLACED ; size DOWN = a FILL (a trade printed there ~now) or a
CANCEL (no trade). This is anonymous at the level, but (a) it's the resting+cancel activity, and (b) in
markets/levels a dominant MM owns, it ~= that wallet. Combined with the wallet-attributed fills tape it
anchors a specific wallet's resting/cancel behaviour. python orderflow_probe.py [secs]
"""
from __future__ import annotations
import asyncio, collections, json, sys, time
import requests, websockets

G = "https://gamma-api.polymarket.com"; WSU = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    s = requests.Session(); now = int(time.time())
    toks = []
    for a in ("btc", "eth"):
        ev = s.get(G + "/events", params={"slug": f"{a}-updown-15m-{now-(now%900)}"}, timeout=10).json()
        if ev:
            toks += [str(x) for x in json.loads(ev[0]["markets"][0]["clobTokenIds"])]
    levels = collections.defaultdict(dict)          # token -> {price: size}
    trades = collections.deque()                     # recent (t, token, price, size)
    ev_c = collections.Counter(); vol = collections.Counter()

    async def go():
        async with websockets.connect(WSU, ping_interval=10, max_size=None) as ws:
            await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
            t0 = time.time()
            while time.time() - t0 < dur:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15)
                except asyncio.TimeoutError:
                    continue
                nowt = time.time()
                while trades and trades[0][0] < nowt - 3:
                    trades.popleft()
                for m in (json.loads(raw) if raw.startswith("[") else [json.loads(raw)]):
                    et = m.get("event_type")
                    if et == "book":                # full snapshot -> reset levels
                        tok = str(m["asset_id"]); levels[tok] = {}
                        for x in (m.get("bids") or []) + (m.get("asks") or []):
                            levels[tok][float(x["price"])] = float(x["size"])
                    elif et == "last_trade_price":
                        trades.append((nowt, str(m["asset_id"]), float(m["price"]), float(m["size"])))
                    elif et == "price_change":
                        for ch in m.get("price_changes") or m.get("changes") or []:
                            tok = str(ch["asset_id"]); px = float(ch["price"]); nsz = float(ch["size"])
                            old = levels[tok].get(px, 0.0); levels[tok][px] = nsz
                            d = nsz - old
                            if d > 1e-6:
                                ev_c["PLACE"] += 1; vol["PLACE"] += d
                            elif d < -1e-6:
                                amt = -d
                                # fill if a trade printed at this token+price within ~3s
                                hit = any(tt[1] == tok and abs(tt[2] - px) < 1e-9 for tt in trades)
                                if hit:
                                    ev_c["FILL"] += 1; vol["FILL"] += amt
                                else:
                                    ev_c["CANCEL"] += 1; vol["CANCEL"] += amt
    asyncio.run(go())
    tot = sum(ev_c.values())
    print(f"order-lifecycle events in {dur}s (anonymous, from public WS deltas):")
    for k in ("PLACE", "FILL", "CANCEL"):
        print(f"  {k:>7}: {ev_c[k]:>5} events  {vol[k]:>10.0f} shares")
    if ev_c["FILL"] + ev_c["CANCEL"]:
        print(f"  CANCEL rate (cancels / (fills+cancels)) = {100*ev_c['CANCEL']/(ev_c['FILL']+ev_c['CANCEL']):.0f}%")
    print("=> placements AND cancels ARE observable at the price level. Anonymous, but attributable to a "
          "dominant wallet where it owns the book, and anchored by the wallet-attributed fills tape.")


if __name__ == "__main__":
    main()
