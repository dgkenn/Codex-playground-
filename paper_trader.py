"""PAPER-TRADING harness for the inventory-capped 2-sided maker (rebate farming).

READ-ONLY: uses Polymarket's public, no-auth CLOB (/book) + Data API (/trades). It
places NO real orders and needs NO keys. It maintains HYPOTHETICAL resting quotes at
the touch on the Up and Down tokens, simulates fills with a conservative queue model
(your order sits BEHIND the displayed size at your level; you fill only the trade
volume that prints through after the queue ahead is consumed), enforces a net-delta
inventory cap, and logs hypothetical gross/rebate/net PnL + inventory per 15-min
window. Run it live for days on your own infra; it validates the LOGIC and the market
data. (True fill/queue can only be confirmed by tiny LIVE orders -- see live_trader.py.)

    python paper_trader.py --duration 3600 --cap 20 --post 20

Outputs paper_trades.log / paper_state.json.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import requests

import fees

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com/trades"
REBATE_RATE = 0.07


def active_market(sess):
    now = int(time.time()); ws = now - (now % 900)
    for cand in (ws, ws + 900):
        ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{cand}"}, timeout=15).json()
        if ev:
            m = ev[0]["markets"][0]
            if not m.get("closed"):
                toks = json.loads(m["clobTokenIds"])
                return {"cid": m["conditionId"], "up": str(toks[0]), "down": str(toks[1]),
                        "ws": cand, "we": cand + 900}
    return None


def top(sess, token):
    b = sess.get(C + "/book", params={"token_id": token}, timeout=10).json()
    bids = b.get("bids", []); asks = b.get("asks", [])
    bb = bids[-1] if bids else None; ba = asks[-1] if asks else None
    return (float(bb["price"]), float(bb["size"])) if bb else (None, None), \
           (float(ba["price"]), float(ba["size"])) if ba else (None, None)


class Book2Sided:
    """One window's paper MM state on the Up+Down pair."""
    def __init__(self, mk, cap, post):
        self.mk = mk; self.cap = cap; self.post = post
        self.up_inv = 0.0; self.dn_inv = 0.0; self.cash = 0.0; self.rebate = 0.0
        self.delta = 0.0; self.fills = 0
        self.queue = {}   # (token, side, price) -> size ahead of us at the moment we joined
        self.seen = set()

    def _maybe_fill(self, token, is_up, taker_side, price, size):
        # we quote: SELL at our ask (taker BUY hits it), BUY at our bid (taker SELL hits it)
        our_side = "ASK" if taker_side == "BUY" else "BID"
        key = (token, our_side, round(price, 3))
        ahead = self.queue.get(key)
        if ahead is None:
            return  # we weren't quoting at this level/price
        consume = min(size, ahead)
        self.queue[key] = ahead - consume
        passthrough = size - consume          # volume that reaches our order
        if passthrough <= 0:
            return
        fill = min(passthrough, self.post)
        # inventory-cap: maker takes opposite of taker
        d_per = (-1.0 if (is_up == (taker_side == "BUY")) else 1.0)
        if abs(self.delta + d_per * fill) > self.cap:
            room = max(0.0, self.cap - abs(self.delta)) if (self.delta + d_per * fill) * d_per > 0 else fill
            fill = min(fill, room)
        if fill <= 0:
            return
        maker_sells = (taker_side == "BUY")
        self.cash += (price if maker_sells else -price) * fill
        if is_up:
            self.up_inv += (-fill if maker_sells else fill)
        else:
            self.dn_inv += (-fill if maker_sells else fill)
        self.delta += d_per * fill
        self.rebate += fees.maker_rebate(price, rate=REBATE_RATE) * fill
        self.fills += 1

    def refresh_quotes(self, up_top, dn_top):
        # (re)join the touch on both sides of both tokens, recording queue-ahead
        for token, is_up, (bid, ask) in [(self.mk["up"], True, up_top), (self.mk["down"], False, dn_top)]:
            (bp, bsz), (ap, asz) = bid, ask
            if bp is not None:
                self.queue.setdefault((token, "BID", round(bp, 3)), bsz)
            if ap is not None:
                self.queue.setdefault((token, "ASK", round(ap, 3)), asz)

    def on_trades(self, trades):
        for t in trades:
            h = t.get("transactionHash", "") + str(t.get("timestamp"))
            if h in self.seen:
                continue
            self.seen.add(h)
            is_up = (str(t["asset"]) == self.mk["up"])
            self._maybe_fill(t["asset"], is_up, t["side"], float(t["price"]), float(t["size"]))


def resolve(sess, ws):
    """Return resolved_up (1/0) for a window once the market settles, else None."""
    try:
        ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{ws}"}, timeout=10).json()
        if ev:
            m = ev[0]["markets"][0]
            op = m.get("outcomePrices")
            if m.get("closed") and op:
                op = json.loads(op) if isinstance(op, str) else op
                return 1 if float(op[0]) > 0.5 else 0
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--cap", type=float, default=20)
    ap.add_argument("--post", type=float, default=20)
    ap.add_argument("--poll", type=float, default=6.0)
    a = ap.parse_args()
    sess = requests.Session()
    end = time.time() + a.duration
    state = None; mk = None
    pending = []   # closed Book2Sided states awaiting resolution
    cum = {"windows": 0, "fills": 0, "gross": 0.0, "rebate": 0.0, "net": 0.0,
           "shares": 0.0, "wins_pos": 0}
    log = open("paper_trades.log", "a")

    def logline(s):
        line = f"{datetime.now(timezone.utc).isoformat()} {s}"
        print(line); log.write(line + "\n"); log.flush()

    def settle_pending():
        for st in pending[:]:
            r = resolve(sess, st.mk["ws"])
            if r is None:
                continue
            gross = st.cash + st.up_inv * r + st.dn_inv * (1 - r)
            net = gross + st.rebate
            shares = abs(st.up_inv) + abs(st.dn_inv) + 1e-9
            cum["windows"] += 1; cum["fills"] += st.fills; cum["gross"] += gross
            cum["rebate"] += st.rebate; cum["net"] += net; cum["shares"] += shares
            cum["wins_pos"] += 1 if net > 0 else 0
            logline(f"SETTLE w={st.mk['ws']} resolved_up={r} fills={st.fills} "
                    f"gross={gross:+.4f} rebate={st.rebate:+.4f} net={net:+.4f}")
            logline(f"CUM windows={cum['windows']} fills={cum['fills']} "
                    f"gross={cum['gross']:+.3f} rebate={cum['rebate']:+.3f} net={cum['net']:+.3f} "
                    f"net/window={cum['net']/max(cum['windows'],1):+.4f} "
                    f"pos_windows={cum['wins_pos']}/{cum['windows']}")
            json.dump(cum, open("paper_summary.json", "w"), indent=2)
            pending.remove(st)

    logline(f"=== paper_trader start cap={a.cap} post={a.post} dur={a.duration}s ===")
    while time.time() < end:
        try:
            if mk is None or time.time() >= mk["we"]:
                if state is not None:
                    logline(f"WINDOW {mk['ws']} close: fills={state.fills} cash={state.cash:+.2f} "
                            f"rebate={state.rebate:+.4f} up_inv={state.up_inv:.0f} dn_inv={state.dn_inv:.0f}")
                    pending.append(state)
                mk = active_market(sess)
                if mk is None:
                    settle_pending(); time.sleep(a.poll); continue
                state = Book2Sided(mk, a.cap, a.post)
                logline(f"WINDOW {mk['ws']} ({datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M} UTC) up={mk['up'][:10]}")
            up_top = top(sess, mk["up"]); dn_top = top(sess, mk["down"])
            state.refresh_quotes(up_top, dn_top)
            tr = sess.get(DATA, params={"market": mk["cid"], "limit": 100}, timeout=10).json()
            if isinstance(tr, list):
                state.on_trades(tr)
            settle_pending()
            (ub, _), (ua, _) = up_top
            logline(f"  t-{int(mk['we']-time.time())}s upbook={ub}/{ua} fills={state.fills} "
                    f"delta={state.delta:+.0f} cash={state.cash:+.2f} reb={state.rebate:+.4f}")
        except Exception as e:  # noqa: BLE001
            logline(f"  [warn] {str(e)[:80]}")
        time.sleep(a.poll)
    logline("=== paper_trader stop ===")
    log.close()


if __name__ == "__main__":
    main()
