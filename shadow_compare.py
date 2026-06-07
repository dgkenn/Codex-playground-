"""SHADOW multi-variant test on LIVE data: run several strategy configs against the SAME
live CLOB WebSocket feed in parallel, each with its own inventory + fills, and compare
settled P&L. This evaluates the new levers on fresh out-of-sample LIVE data:

  baseline    cap=50 skew=0.25                  (the validated core)
  cap25/cap100                                  (cap frontier -- capacity vs Sharpe)
  skew15      cap=50 skew=0.15                  (tighter inventory skew, #10)
  fv_size     baseline + size *= w(fair_edge)   (continuous sizing, #3)
  micro_gate  baseline + pull side the microprice says is tipping (#4 book-native)
  predict     baseline + fair-value pull gate    (#4 prediction channel -- expect weak)

READ-ONLY paper fills (queue-position model), no orders, no keys. HONEST LIMIT: the paper
fill model is queue-favorable and CANNOT capture the live-only levers (real queue position,
cancel latency, market impact) -- those need real orders (see PILOT.md). This tests the
STRATEGY LOGIC (cap/skew/sizing/gating) on live fills, not execution quality.

Artifacts: shadow_windows.jsonl (per-variant per-window), shadow_summary.json (cum), shadow.log.
    python shadow_compare.py --duration 57600
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone

import requests
import websockets

import fees
from fairvalue import fair_up
from fvfeed import SpotFair
from paper_trader_ws import WS, active_market, now_iso, resolve

REBATE = 0.07
SIGMA = 6.5e-5
FV_K = 2.0           # continuous-sizing slope (offline: k=2 beat every gate)
FV_MARGIN = 0.03    # fair-value gate threshold


def micro(bb, bsz, ba, asz):
    tot = (bsz or 0) + (asz or 0)
    if bb is None or ba is None:
        return None
    return (bb + ba) / 2 if tot <= 0 else bb + (ba - bb) * (bsz or 0) / tot


class Variant:
    """One strategy config; own book/queue/inventory; fed the shared live event stream."""

    def __init__(self, name, mk, cap, skew, size_mode="flat", gate=None, shared=None):
        self.name = name; self.mk = mk; self.cap = cap; self.skew = skew
        self.size_mode = size_mode; self.gate = gate; self.shared = shared
        self.post = 20.0
        self.up_inv = self.dn_inv = self.cash = self.rebate = self.delta = 0.0
        self.fills = 0
        self.tob = {mk["up"]: [None, 0, None, 0], mk["down"]: [None, 0, None, 0]}
        self.queue = {}

    def is_up(self, t):
        return t == self.mk["up"]

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
        self.set_tob(token, bb, bsz, ba, asz)

    def on_price_change(self, m):
        for pc in m.get("price_changes", []):
            token = str(pc["asset_id"])
            if token not in self.tob:
                continue
            cur = self.tob[token]
            bb = float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else cur[0]
            ba = float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else cur[2]
            self.set_tob(token, bb, cur[1], ba, cur[3])

    def fair_tok(self, token):
        s = self.shared
        if s.get("st") is None or s.get("s0") is None:
            return None
        tau = max(self.mk["we"] - time.time(), 0.0)
        p = fair_up(s["st"], s["s0"], SIGMA, tau)
        return p if self.is_up(token) else (1.0 - p)

    def _gated(self, token, our_side, price):
        """Return True to SKIP the fill (pull the quote) per this variant's gate."""
        if self.gate == "micro":
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            # selling (ASK) toxic if microprice above our ask (book tipping up); BID toxic if below
            return (our_side == "ASK" and mp > price) or (our_side == "BID" and mp < price)
        if self.gate == "predict":
            ft = self.fair_tok(token)
            if ft is None:
                return False
            return (our_side == "ASK" and price < ft - FV_MARGIN) or \
                   (our_side == "BID" and price > ft + FV_MARGIN)
        return False

    def _size(self, token, our_side, price):
        if self.size_mode != "fv":
            return self.post
        ft = self.fair_tok(token)
        if ft is None:
            return self.post
        edge = (price - ft) if our_side == "ASK" else (ft - price)
        return self.post * min(max(1.0 + FV_K * edge, 0.0), 2.0)

    def on_trade(self, token, side, price, size):
        if token not in self.tob:
            return
        our_side = "ASK" if side == "BUY" else "BID"
        key = (token, our_side, round(price, 3))
        ahead = self.queue.get(key)
        if ahead is None:
            return
        consume = min(size, ahead); self.queue[key] = ahead - consume
        passthrough = size - consume
        if passthrough <= 0:
            return
        if self._gated(token, our_side, price):
            return
        fill = min(passthrough, self._size(token, our_side, price))
        is_up = self.is_up(token); d_per = (-1.0 if (is_up == (side == "BUY")) else 1.0)
        if abs(self.delta) >= self.skew * self.cap and (self.delta * d_per) > 0:
            return
        if abs(self.delta + d_per * fill) > self.cap:
            room = max(0.0, self.cap - abs(self.delta)) if (self.delta + d_per * fill) * d_per > 0 else fill
            fill = min(fill, room)
        if fill <= 0:
            return
        sells = (side == "BUY")
        self.cash += (price if sells else -price) * fill
        if is_up:
            self.up_inv += (-fill if sells else fill)
        else:
            self.dn_inv += (-fill if sells else fill)
        self.delta += d_per * fill
        self.rebate += fees.maker_rebate(price, rate=REBATE) * fill
        self.fills += 1

    def settle(self, r):
        gross = self.cash + self.up_inv * r + self.dn_inv * (1 - r)
        return gross, gross + self.rebate


def configs(mk, shared):
    return [
        Variant("baseline", mk, 50, 0.25, shared=shared),
        Variant("cap25", mk, 25, 0.25, shared=shared),
        Variant("cap100", mk, 100, 0.25, shared=shared),
        Variant("skew15", mk, 50, 0.15, shared=shared),
        Variant("fv_size", mk, 50, 0.25, size_mode="fv", shared=shared),
        Variant("micro_gate", mk, 50, 0.25, gate="micro", shared=shared),
        Variant("predict", mk, 50, 0.25, gate="predict", shared=shared),
    ]


async def run(args):
    sess = requests.Session()
    fv = SpotFair(sess)
    log = open("shadow.log", "a"); wins_fh = open("shadow_windows.jsonl", "a")
    cum = {}; pending = []

    def L(s):
        line = f"{now_iso()} {s}"; print(line); log.write(line + "\n"); log.flush()

    def try_settle():
        """Retry resolution for closed-but-unresolved windows (Polymarket posts the result
        minutes after window end). Settle + remove when resolved. (The bug in the first run
        was settling ONCE at close and skipping forever.)"""
        for item in pending[:]:
            mk2, variants2 = item
            r = resolve(sess, mk2["ws"])
            if r is None:
                continue
            row = {"ts": now_iso(), "ws": mk2["ws"], "resolved_up": r}
            parts = []
            for v in variants2:
                _, net = v.settle(r)
                c = cum.setdefault(v.name, {"net": 0.0, "fills": 0, "windows": 0, "pos": 0})
                c["net"] += net; c["fills"] += v.fills; c["windows"] += 1; c["pos"] += 1 if net > 0 else 0
                row[v.name] = {"net": round(net, 4), "fills": v.fills}
                parts.append(f"{v.name}={net:+.3f}({v.fills})")
            wins_fh.write(json.dumps(row) + "\n"); wins_fh.flush()
            json.dump(cum, open("shadow_summary.json", "w"), indent=2)
            L("SETTLE w=%d res=%d | %s" % (mk2["ws"], r, "  ".join(parts)))
            L("CUM | " + "  ".join(f"{k}={c['net']:+.2f}/{c['windows']}w" for k, c in cum.items()))
            pending.remove(item)

    L(f"=== shadow_compare start variants={[c.name for c in configs({'up':'','down':'','we':0}, {})]} ===")
    end = time.time() + args.duration
    while time.time() < end:
        try_settle()                         # retry any closed-but-unresolved windows
        mk = active_market(sess)
        if mk is None:
            await asyncio.sleep(5); continue
        shared = {"st": None, "s0": None}
        sp = fv.update()
        if sp and time.time() - mk["ws"] <= 60:        # only anchor S0 on a fresh window
            fv.set_window(sp); shared["s0"] = sp
        shared["st"] = sp
        variants = configs(mk, shared)
        L(f"WINDOW {mk['ws']} ({datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z) s0={shared['s0']}")
        last_spot = time.time()
        while time.time() < mk["we"] and time.time() < end:
            try:
                async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                    await ws.send(json.dumps({"assets_ids": [mk["up"], mk["down"]], "type": "market"}))
                    while time.time() < mk["we"] and time.time() < end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(15, mk["we"] - time.time() + 1))
                        except asyncio.TimeoutError:
                            continue
                        if time.time() - last_spot > 2:        # refresh spot for fair-value variants
                            shared["st"] = fv.update() or shared["st"]; last_spot = time.time()
                        data = json.loads(raw)
                        for m in (data if isinstance(data, list) else [data]):
                            et = m.get("event_type")
                            for v in variants:
                                if et == "book":
                                    v.on_book(m)
                                elif et == "price_change":
                                    v.on_price_change(m)
                                elif et == "last_trade_price":
                                    v.on_trade(str(m["asset_id"]), m["side"], float(m["price"]), float(m["size"]))
            except Exception as e:  # noqa: BLE001
                L(f"  [ws reconnect] {str(e)[:70]}"); await asyncio.sleep(2)
        pending.append((mk, variants))      # settle later, with retry (resolution lags close)
        try_settle()
    # drain: retry pending settlements for a few minutes after the run ends
    for _ in range(20):
        if not pending:
            break
        try_settle()
        if pending:
            await asyncio.sleep(15)
    L(f"=== shadow_compare stop (unsettled windows left: {len(pending)}) ===")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=300)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
