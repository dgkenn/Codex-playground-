"""PAPER-TRADING harness v2: EVENT-DRIVEN via Polymarket CLOB WebSocket.

Upgrade over the polling version (community research #1/#2 priority): subscribes to the
real-time market channel (wss://ws-subscriptions-clob.polymarket.com/ws/market) and
reacts to every book/price_change/last_trade_price instantly -> far better fill
realism than 6s polling. Same refined strategy (inventory-capped + skew 2-sided maker),
plus PER-SIDE markout logging (adverse-selection audit). READ-ONLY, no keys, no orders.

Borrows patterns from: nevuamarkets/poly-websockets (WS feed), Polymarket/poly-market-maker
(quote lifecycle near mid), zer0cache/hyperliquid-market-maker-bot (per-side markout).

Audit artifacts: audit_book.jsonl, audit_trades.jsonl, audit_fills.jsonl,
audit_windows.jsonl, audit_meta.json, paper_summary.json, paper_trades.log (shared schema).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone

import requests
import websockets

import fees

WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
G = "https://gamma-api.polymarket.com"
REBATE_RATE = 0.07


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def jdump(fh, obj):
    fh.write(json.dumps(obj) + "\n"); fh.flush()


def active_market(sess, asset="btc", tenor_min=15):
    """Active {asset}-updown-{tenor_min}m market. Defaults to BTC 15m (backward-compatible). The
    window length = tenor_min*60, so 5m and 15m (and other assets) share one parametrized path."""
    win = tenor_min * 60
    now = int(time.time()); ws = now - (now % win)
    for cand in (ws, ws + win):
        ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-{tenor_min}m-{cand}"}, timeout=15).json()
        if ev and not ev[0]["markets"][0].get("closed"):
            m = ev[0]["markets"][0]; toks = json.loads(m["clobTokenIds"])
            return {"cid": m["conditionId"], "up": str(toks[0]), "down": str(toks[1]),
                    "ws": cand, "we": cand + win, "asset": asset, "tenor_min": tenor_min}
    return None


def resolve(sess, ws, asset="btc", tenor_min=15):
    try:
        ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-{tenor_min}m-{ws}"}, timeout=10).json()
        if ev:
            m = ev[0]["markets"][0]; op = m.get("outcomePrices")
            if m.get("closed") and op:
                op = json.loads(op) if isinstance(op, str) else op
                return 1 if float(op[0]) > 0.5 else 0
    except Exception:
        pass
    return None


class MM:
    def __init__(self, mk, cap, post, skew, fhs):
        self.mk = mk; self.cap = cap; self.post = post; self.skew = skew; self.fhs = fhs
        self.up_inv = self.dn_inv = self.cash = self.rebate = self.delta = 0.0
        self.fills = 0; self.n_trades = 0; self.n_snaps = 0
        # per-token top of book: [best_bid, bid_sz, best_ask, ask_sz]
        self.tob = {mk["up"]: [None, 0, None, 0], mk["down"]: [None, 0, None, 0]}
        self.queue = {}                 # (token, side, price) -> size ahead
        self.mk_buy = 0; self.mk_sell = 0   # per-side fill counts (markout audit)

    def is_up(self, token):
        return token == self.mk["up"]

    def set_tob(self, token, bb, bsz, ba, asz):
        self.tob[token] = [bb, bsz, ba, asz]
        if bb is not None:
            self.queue.setdefault((token, "BID", round(bb, 3)), bsz)
        if ba is not None:
            self.queue.setdefault((token, "ASK", round(ba, 3)), asz)

    def on_book(self, m):
        token = str(m["asset_id"])
        if token not in self.tob:
            return
        bids = m.get("bids") or []; asks = m.get("asks") or []
        bb = max((float(b["price"]) for b in bids), default=None)
        ba = min((float(a["price"]) for a in asks), default=None)
        bsz = sum(float(b["size"]) for b in bids if float(b["price"]) == bb) if bb is not None else 0
        asz = sum(float(a["size"]) for a in asks if float(a["price"]) == ba) if ba is not None else 0
        self.set_tob(token, bb, bsz, ba, asz); self.n_snaps += 1
        jdump(self.fhs["book"], {"ts": now_iso(), "ws": self.mk["ws"], "token": token[:12],
              "bb": bb, "bsz": bsz, "ba": ba, "asz": asz})

    def on_price_change(self, m):
        for pc in m.get("price_changes", []):
            token = str(pc["asset_id"])
            if token not in self.tob:
                continue
            bb = float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else self.tob[token][0]
            ba = float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else self.tob[token][2]
            # update size at the changed level if it is the touch
            cur = self.tob[token]; bsz, asz = cur[1], cur[3]
            self.set_tob(token, bb, bsz, ba, asz)

    def on_trade(self, m):
        token = str(m["asset_id"])
        if token not in self.tob:
            return
        self.n_trades += 1
        price = float(m["price"]); size = float(m["size"]); side = m["side"]
        jdump(self.fhs["trades"], {"ts": now_iso(), "ws": self.mk["ws"], "token": token[:12],
              "side": side, "price": price, "size": size})
        filled = self._fill(token, side, price, size)
        return filled

    def _fill(self, token, side, price, size):
        our_side = "ASK" if side == "BUY" else "BID"
        key = (token, our_side, round(price, 3))
        ahead = self.queue.get(key)
        if ahead is None:
            return 0.0
        consume = min(size, ahead); self.queue[key] = ahead - consume
        passthrough = size - consume
        if passthrough <= 0:
            return 0.0
        fill = min(passthrough, self.post)
        is_up = self.is_up(token)
        d_per = (-1.0 if (is_up == (side == "BUY")) else 1.0)
        if abs(self.delta) >= self.skew * self.cap and (self.delta * d_per) > 0:
            return 0.0
        if abs(self.delta + d_per * fill) > self.cap:
            room = max(0.0, self.cap - abs(self.delta)) if (self.delta + d_per * fill) * d_per > 0 else fill
            fill = min(fill, room)
        if fill <= 0:
            return 0.0
        sells = (side == "BUY")
        self.cash += (price if sells else -price) * fill
        if is_up:
            self.up_inv += (-fill if sells else fill)
        else:
            self.dn_inv += (-fill if sells else fill)
        self.delta += d_per * fill
        reb = fees.maker_rebate(price, rate=REBATE_RATE) * fill
        self.rebate += reb; self.fills += 1
        self.mk_sell += 1 if sells else 0; self.mk_buy += 0 if sells else 1
        cur = self.tob[token]; mid = (cur[0] + cur[2]) / 2 if cur[0] and cur[2] else None
        jdump(self.fhs["fills"], {"ts": now_iso(), "ws": self.mk["ws"], "token": token[:12],
              "taker_side": side, "fill_price": price, "fill_size": fill, "trade_size": size,
              "mid": mid, "delta": self.delta, "up_inv": self.up_inv, "dn_inv": self.dn_inv, "rebate": reb})
        return fill


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "?"


async def run(args):
    sess = requests.Session()
    fhs = {k: open(f"audit_{k}.jsonl", "a") for k in ("book", "trades", "fills", "windows")}
    log = open("paper_trades.log", "a")
    json.dump({"start": now_iso(), "engine": "websocket", "cap": args.cap, "post": args.post,
               "skew_frac": args.skew, "fee_rate": REBATE_RATE, "git": git_commit(),
               "duration_s": args.duration}, open("audit_meta.json", "w"), indent=2)

    def logline(s):
        line = f"{now_iso()} {s}"; print(line); log.write(line + "\n"); log.flush()

    cum = {"windows": 0, "fills": 0, "gross": 0.0, "rebate": 0.0, "net": 0.0, "pos": 0}
    pending = []

    def settle():
        for st in pending[:]:
            r = resolve(sess, st.mk["ws"])
            if r is None:
                continue
            gross = st.cash + st.up_inv * r + st.dn_inv * (1 - r); net = gross + st.rebate
            cum["windows"] += 1; cum["fills"] += st.fills; cum["gross"] += gross
            cum["rebate"] += st.rebate; cum["net"] += net; cum["pos"] += 1 if net > 0 else 0
            jdump(fhs["windows"], {"ts": now_iso(), "ws": st.mk["ws"], "resolved_up": r,
                  "fills": st.fills, "n_trades": st.n_trades, "n_snaps": st.n_snaps, "cash": st.cash,
                  "up_inv": st.up_inv, "dn_inv": st.dn_inv, "rebate": st.rebate, "gross": gross,
                  "net": net, "mk_buy": st.mk_buy, "mk_sell": st.mk_sell})
            logline(f"SETTLE w={st.mk['ws']} res={r} fills={st.fills} gross={gross:+.4f} net={net:+.4f}")
            logline(f"CUM windows={cum['windows']} fills={cum['fills']} net={cum['net']:+.3f} "
                    f"net/win={cum['net']/max(cum['windows'],1):+.4f} pos={cum['pos']}/{cum['windows']}")
            json.dump(cum, open("paper_summary.json", "w"), indent=2)
            pending.remove(st)

    logline(f"=== paper_trader_ws start cap={args.cap} post={args.post} skew={args.skew} git={git_commit()} ===")
    end = time.time() + args.duration
    while time.time() < end:
        mk = active_market(sess)
        if mk is None:
            settle(); await asyncio.sleep(5); continue
        st = MM(mk, args.cap, args.post, args.skew, fhs)
        logline(f"WINDOW {mk['ws']} ({datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z) up={mk['up'][:10]}")
        # reconnect-within-window on any drop (poly-websockets robustness pattern):
        # the MM state `st` persists across reconnects so a dropped socket never ends the window.
        while time.time() < mk["we"] and time.time() < end:
            try:
                async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                    await ws.send(json.dumps({"assets_ids": [mk["up"], mk["down"]], "type": "market"}))
                    while time.time() < mk["we"] and time.time() < end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(20, mk["we"] - time.time() + 1))
                        except asyncio.TimeoutError:
                            continue
                        data = json.loads(raw)
                        for m in (data if isinstance(data, list) else [data]):
                            et = m.get("event_type")
                            if et == "book":
                                st.on_book(m)
                            elif et == "price_change":
                                st.on_price_change(m)
                            elif et == "last_trade_price":
                                st.on_trade(m)
            except Exception as e:  # noqa: BLE001 -- reconnect and continue same window
                logline(f"  [ws reconnect] {str(e)[:80]}")
                await asyncio.sleep(2)
        logline(f"WINDOW {mk['ws']} close fills={st.fills} trades={st.n_trades} cash={st.cash:+.2f} "
                f"reb={st.rebate:+.4f} delta={st.delta:+.0f}")
        pending.append(st); settle()
    settle()
    logline("=== paper_trader_ws stop ===")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--cap", type=float, default=50)
    ap.add_argument("--post", type=float, default=20)
    ap.add_argument("--skew", type=float, default=0.25)
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
