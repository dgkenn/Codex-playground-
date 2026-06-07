"""PAPER-TRADING harness for the inventory-capped 2-sided maker (rebate farming),
with FULL AUDIT LOGGING.

READ-ONLY: public, no-auth CLOB (/book) + Data API (/trades). Places NO real orders,
needs NO keys. Maintains HYPOTHETICAL resting quotes at the touch on Up & Down,
simulates fills with a conservative queue model (your order sits BEHIND displayed
size; you fill only volume that prints through after the queue ahead is consumed),
enforces a net-delta inventory cap, settles each window at resolution.

Audit artifacts (JSONL/JSON, append-only -> fully reconstructable & verifiable):
  audit_meta.json     run config (params, fee/rebate, git commit, start time)
  audit_book.jsonl    per-poll top-of-book snapshot (Up+Down bid/ask/size) -> markout, spread, overround
  audit_trades.jsonl  every observed taker trade (+ whether it filled us) -> fill-model audit
  audit_fills.jsonl   every simulated fill with full context + queue state + inventory
  audit_windows.jsonl per-window settled record (resolution, cash, inv, rebate, gross, net)
  paper_trades.log    human-readable running log
  paper_summary.json  cumulative P&L summary

    python paper_trader.py --duration 36000 --cap 20 --post 20
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone

import requests

import fees

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com/trades"
REBATE_RATE = 0.07


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def jdump(fh, obj):
    fh.write(json.dumps(obj) + "\n"); fh.flush()


def active_market(sess):
    now = int(time.time()); ws = now - (now % 900)
    for cand in (ws, ws + 900):
        ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{cand}"}, timeout=15).json()
        if ev and not ev[0]["markets"][0].get("closed"):
            m = ev[0]["markets"][0]; toks = json.loads(m["clobTokenIds"])
            return {"cid": m["conditionId"], "up": str(toks[0]), "down": str(toks[1]),
                    "ws": cand, "we": cand + 900}
    return None


def top(sess, token):
    b = sess.get(C + "/book", params={"token_id": token}, timeout=10).json()
    bids, asks = b.get("bids", []), b.get("asks", [])
    bb = (float(bids[-1]["price"]), float(bids[-1]["size"])) if bids else (None, None)
    ba = (float(asks[-1]["price"]), float(asks[-1]["size"])) if asks else (None, None)
    return bb, ba


def resolve(sess, ws):
    try:
        ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{ws}"}, timeout=10).json()
        if ev:
            m = ev[0]["markets"][0]; op = m.get("outcomePrices")
            if m.get("closed") and op:
                op = json.loads(op) if isinstance(op, str) else op
                return 1 if float(op[0]) > 0.5 else 0
    except Exception:
        pass
    return None


class Book2Sided:
    def __init__(self, mk, cap, post, fills_fh, skew_frac=0.25):
        self.mk = mk; self.cap = cap; self.post = post; self.fills_fh = fills_fh
        self.skew_frac = skew_frac
        self.up_inv = self.dn_inv = self.cash = self.rebate = self.delta = 0.0
        self.fills = 0; self.n_snaps = 0; self.n_trades = 0
        self.queue = {}; self.seen = set()
        self.up_mid = None; self.dn_mid = None

    def refresh_quotes(self, up_top, dn_top):
        (ubp, ubsz), (uap, uasz) = up_top
        (dbp, dbsz), (dap, dasz) = dn_top
        self.up_mid = (ubp + uap) / 2 if ubp and uap else None
        self.dn_mid = (dbp + dap) / 2 if dbp and dap else None
        for token, bp, bsz, ap, asz in [(self.mk["up"], ubp, ubsz, uap, uasz),
                                        (self.mk["down"], dbp, dbsz, dap, dasz)]:
            if bp is not None:
                self.queue.setdefault((token, "BID", round(bp, 3)), bsz)
            if ap is not None:
                self.queue.setdefault((token, "ASK", round(ap, 3)), asz)

    def on_trades(self, trades):
        for t in trades:
            h = t.get("transactionHash", "") + str(t.get("timestamp"))
            if h in self.seen:
                continue
            self.seen.add(h); self.n_trades += 1
            is_up = (str(t["asset"]) == self.mk["up"])
            filled = self._maybe_fill(t, is_up)
            yield {"ts": now_iso(), "ws": self.mk["ws"], "asset": str(t["asset"]), "is_up": is_up,
                   "side": t["side"], "price": float(t["price"]), "size": float(t["size"]),
                   "filled": filled}

    def _maybe_fill(self, t, is_up):
        price = float(t["price"]); size = float(t["size"]); taker_side = t["side"]
        our_side = "ASK" if taker_side == "BUY" else "BID"
        key = (str(t["asset"]), our_side, round(price, 3))
        ahead = self.queue.get(key)
        if ahead is None:
            return 0.0
        queue_ahead0 = ahead
        consume = min(size, ahead); self.queue[key] = ahead - consume
        passthrough = size - consume
        if passthrough <= 0:
            return 0.0
        fill = min(passthrough, self.post)
        d_per = (-1.0 if (is_up == (taker_side == "BUY")) else 1.0)
        # inventory skew: stop quoting the leaning side once |delta| >= skew_frac*cap
        if abs(self.delta) >= self.skew_frac * self.cap and (self.delta * d_per) > 0:
            return 0.0
        if abs(self.delta + d_per * fill) > self.cap:
            room = max(0.0, self.cap - abs(self.delta)) if (self.delta + d_per * fill) * d_per > 0 else fill
            fill = min(fill, room)
        if fill <= 0:
            return 0.0
        maker_sells = (taker_side == "BUY")
        self.cash += (price if maker_sells else -price) * fill
        if is_up:
            self.up_inv += (-fill if maker_sells else fill)
        else:
            self.dn_inv += (-fill if maker_sells else fill)
        self.delta += d_per * fill
        reb = fees.maker_rebate(price, rate=REBATE_RATE) * fill
        self.rebate += reb; self.fills += 1
        jdump(self.fills_fh, {
            "ts": now_iso(), "ws": self.mk["ws"], "asset": str(t["asset"]), "is_up": is_up,
            "taker_side": taker_side, "our_side": our_side, "fill_price": price, "fill_size": fill,
            "trade_size": size, "queue_ahead": queue_ahead0, "up_mid": self.up_mid, "dn_mid": self.dn_mid,
            "up_inv": self.up_inv, "dn_inv": self.dn_inv, "delta": self.delta, "rebate": reb})
        return fill


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--cap", type=float, default=20)
    ap.add_argument("--post", type=float, default=20)
    ap.add_argument("--skew", type=float, default=0.25, help="skew/flatten once |delta|>=skew*cap")
    ap.add_argument("--poll", type=float, default=6.0)
    a = ap.parse_args()
    sess = requests.Session()
    log = open("paper_trades.log", "a")
    book_fh = open("audit_book.jsonl", "a"); trades_fh = open("audit_trades.jsonl", "a")
    fills_fh = open("audit_fills.jsonl", "a"); win_fh = open("audit_windows.jsonl", "a")
    json.dump({"start": now_iso(), "cap": a.cap, "post": a.post, "skew_frac": a.skew, "poll": a.poll,
               "fee_rate": REBATE_RATE, "rebate_model": "0.20*0.07*p(1-p) per matched share",
               "queue_model": "behind displayed size; fill on trade-through",
               "git": git_commit(), "duration_s": a.duration}, open("audit_meta.json", "w"), indent=2)

    def logline(s):
        line = f"{now_iso()} {s}"; print(line); log.write(line + "\n"); log.flush()

    end = time.time() + a.duration
    state = None; mk = None; pending = []
    cum = {"windows": 0, "fills": 0, "gross": 0.0, "rebate": 0.0, "net": 0.0, "trades": 0, "pos": 0}

    def settle_pending():
        for st in pending[:]:
            r = resolve(sess, st.mk["ws"])
            if r is None:
                continue
            gross = st.cash + st.up_inv * r + st.dn_inv * (1 - r); net = gross + st.rebate
            cum["windows"] += 1; cum["fills"] += st.fills; cum["gross"] += gross
            cum["rebate"] += st.rebate; cum["net"] += net; cum["trades"] += st.n_trades
            cum["pos"] += 1 if net > 0 else 0
            rec = {"ts": now_iso(), "ws": st.mk["ws"], "we": st.mk["we"], "up_token": st.mk["up"],
                   "dn_token": st.mk["down"], "cid": st.mk["cid"], "resolved_up": r, "fills": st.fills,
                   "n_trades": st.n_trades, "n_snaps": st.n_snaps, "cash": st.cash, "up_inv": st.up_inv,
                   "dn_inv": st.dn_inv, "rebate": st.rebate, "gross": gross, "net": net}
            jdump(win_fh, rec)
            logline(f"SETTLE w={st.mk['ws']} res={r} fills={st.fills} gross={gross:+.4f} "
                    f"rebate={st.rebate:+.4f} net={net:+.4f}")
            logline(f"CUM windows={cum['windows']} fills={cum['fills']} net={cum['net']:+.3f} "
                    f"gross={cum['gross']:+.3f} rebate={cum['rebate']:+.3f} "
                    f"net/win={cum['net']/max(cum['windows'],1):+.4f} pos={cum['pos']}/{cum['windows']}")
            json.dump(cum, open("paper_summary.json", "w"), indent=2)
            pending.remove(st)

    logline(f"=== paper_trader(audit) start cap={a.cap} post={a.post} dur={a.duration}s git={git_commit()} ===")
    while time.time() < end:
        try:
            if mk is None or time.time() >= mk["we"]:
                if state is not None:
                    logline(f"WINDOW {mk['ws']} close fills={state.fills} cash={state.cash:+.2f} "
                            f"reb={state.rebate:+.4f} up_inv={state.up_inv:.0f} dn_inv={state.dn_inv:.0f}")
                    pending.append(state)
                mk = active_market(sess)
                if mk is None:
                    settle_pending(); time.sleep(a.poll); continue
                state = Book2Sided(mk, a.cap, a.post, fills_fh, a.skew)
                logline(f"WINDOW {mk['ws']} ({datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z) up={mk['up'][:10]}")
            up_top = top(sess, mk["up"]); dn_top = top(sess, mk["down"])
            state.refresh_quotes(up_top, dn_top); state.n_snaps += 1
            (ub, ubs), (ua, uas) = up_top; (db, dbs), (da, das) = dn_top
            jdump(book_fh, {"ts": now_iso(), "ws": mk["ws"], "up_bid": ub, "up_bid_sz": ubs,
                            "up_ask": ua, "up_ask_sz": uas, "dn_bid": db, "dn_bid_sz": dbs,
                            "dn_ask": da, "dn_ask_sz": das})
            tr = sess.get(DATA, params={"market": mk["cid"], "limit": 100}, timeout=10).json()
            if isinstance(tr, list):
                for rec in state.on_trades(tr):
                    jdump(trades_fh, rec)
            settle_pending()
            logline(f"  t-{int(mk['we']-time.time())}s upbook={ub}/{ua} fills={state.fills} "
                    f"delta={state.delta:+.0f} cash={state.cash:+.2f} reb={state.rebate:+.4f}")
        except Exception as e:  # noqa: BLE001
            logline(f"  [warn] {str(e)[:80]}")
        time.sleep(a.poll)
    settle_pending()
    logline("=== paper_trader(audit) stop ===")
    for fh in (log, book_fh, trades_fh, fills_fh, win_fh):
        fh.close()


if __name__ == "__main__":
    main()
