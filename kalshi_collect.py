"""kalshi_collect.py -- live SHADOW collector for Kalshi's 15-min crypto markets (KX*15M).

The candle backtest (kalshi_econ.py) brackets Kalshi maker viability between bounds; the deciding
measurement is the same one that settled Polymarket: run the registered strategy variants against
the LIVE book and record real fills/markouts. This adapter does exactly that, REUSING the existing
engine -- shadow_compare.Variant (queue model, gates, fill logging) and the strategies registry --
against Kalshi's public (no-auth) REST: orderbook + trades polled ~1Hz, settlement from the market
result. Differences vs Polymarket are handled at the edges:

  * YES/NO map to up/down tokens; YES ask = 1 - best NO bid (one physical book, two views).
  * One Kalshi trade is fed to BOTH token views (taker BUY yes == taker SELL no).
  * NO REBATE: window rows record net == gross (pure spread capture vs adverse selection). When
    running gate_lab/leaderboard on this tape, set the rebate to 0 -- the fills schema is identical
    (venue tag "kalshi" on every row).

    python kalshi_collect.py [duration_s] [out_dir] [tag]      # default 3600 gha_data kal<ts>
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

import strategies
from fvfeed import SpotFair
from shadow_compare import Variant, micro

B = "https://api.elections.kalshi.com/trade-api/v2"
ASSETS = ("btc", "eth", "sol", "xrp")
POLL_S = 1.2                  # per-asset book cadence (4 assets => ~5 req/s incl. trades, public-safe)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class KalshiMarket:
    """One asset's active 15-min market: discovery, book/trade polling, settlement."""

    def __init__(self, sess, asset):
        self.sess = sess
        self.asset = asset
        self.series = f"KX{asset.upper()}15M"
        self.mk = None
        self.variants = []
        self.shared = {}
        self.midtl = {}
        self.seen_trades = set()
        self.last_trades_poll = 0.0
        self.fv = SpotFair(requests.Session(), symbol=f"{asset.upper()}USDT")
        self.last_spot_poll = 0.0

    def discover(self):
        try:
            d = self.sess.get(f"{B}/markets", params={"series_ticker": self.series,
                                                      "status": "open", "limit": 5}, timeout=8).json()
        except Exception:
            return None
        best = None
        now = time.time()
        for m in d.get("markets") or []:
            try:
                ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if ct > now + 5 and (best is None or ct < best[1]):
                best = (m["ticker"], ct)
        if best is None:
            return None
        tk, ct = best
        ws = int(ct) - 900
        self.mk = {"up": f"{tk}:YES", "down": f"{tk}:NO", "ws": ws, "we": int(ct),
                   "cid": tk, "tick": 0.01, "asset": self.asset, "tenor_min": 15}
        self.shared = {"st": None, "s0": None, "flow": {}, "spothist": [], "microhist": {}, "qema": {}}
        self.variants = [Variant(s.name, self.mk, s.cap, s.skew, size_mode=s.size_mode, gate=s.gate,
                                 shared=self.shared, short_skew=s.short_skew, tau_guard=s.tau_guard)
                         for s in strategies.enabled()]
        self.midtl = {}
        self.seen_trades = set()
        sp = self.fv.update()
        if sp and time.time() - ws <= 60:
            self.fv.set_window(sp); self.shared["s0"] = sp
        self.shared["st"] = sp
        return self.mk

    def poll(self):
        """One pass: spot, book -> set_tob both views, trades -> on_trade both views, timeline."""
        mk = self.mk
        nowt = time.time()
        if nowt - self.last_spot_poll > 2:
            self.last_spot_poll = nowt
            sp = self.fv.update()
            if sp:
                self.shared["st"] = sp
                sh = self.shared["spothist"]; sh.append((nowt, sp))
                if len(sh) > 40:
                    del sh[:len(sh) - 40]
        try:
            ob = self.sess.get(f"{B}/markets/{mk['cid']}/orderbook", timeout=6).json()
        except Exception:
            return
        o = ob.get("orderbook_fp") or ob.get("orderbook") or {}
        yb = o.get("yes_dollars") or []; nb = o.get("no_dollars") or []
        if not yb or not nb:
            return
        ybb, ybq = float(yb[-1][0]), float(yb[-1][1])      # best YES bid
        nbb, nbq = float(nb[-1][0]), float(nb[-1][1])      # best NO bid
        yba = round(1.0 - nbb, 4)                          # YES ask (mirror)
        for v in self.variants:
            try:
                v.set_tob(mk["up"], ybb, ybq, yba, nbq)
                v.set_tob(mk["down"], nbb, nbq, round(1.0 - ybb, 4), ybq)
            except Exception:
                pass
        # shared timeline sample (markouts + micro/qema history), same shape as shadow_compare
        mc = micro(ybb, ybq, yba, nbq)
        tl = self.midtl.setdefault(mk["up"], [])
        if not tl or nowt - tl[-1][0] >= 1.0:
            tl.append((nowt, (ybb + yba) / 2, mc, self.shared.get("st"), ybb, ybq, yba, nbq))
            mh = self.shared["microhist"].setdefault(mk["up"], [])
            if mc is not None:
                mh.append((nowt, mc))
                if len(mh) > 40:
                    del mh[:len(mh) - 40]
            qe = self.shared["qema"].setdefault(mk["up"], {"b": ybq, "a": nbq})
            qe["b"] = 0.95 * qe["b"] + 0.05 * ybq; qe["a"] = 0.95 * qe["a"] + 0.05 * nbq
        if nowt - self.last_trades_poll > 2.5:
            self.last_trades_poll = nowt
            try:
                tr = self.sess.get(f"{B}/markets/trades",
                                   params={"ticker": mk["cid"], "limit": 50}, timeout=6).json()
            except Exception:
                return
            for t in reversed(tr.get("trades") or []):
                tid = t.get("trade_id")
                if not tid or tid in self.seen_trades:
                    continue
                self.seen_trades.add(tid)
                try:
                    yp = float(t["yes_price_dollars"]); ct = float(t.get("count_fp") or t.get("count") or 0)
                    buy_yes = (t.get("taker_side") == "yes")
                except Exception:
                    continue
                fl = self.shared["flow"].setdefault(mk["up"], [])
                fl.append((nowt, ct if buy_yes else -ct))
                if len(fl) > 4000:
                    del fl[:2000]
                for v in self.variants:
                    try:                                   # one physical trade, both token views
                        v.on_trade(mk["up"], "BUY" if buy_yes else "SELL", yp, ct)
                        v.on_trade(mk["down"], "SELL" if buy_yes else "BUY", round(1.0 - yp, 4), ct)
                    except Exception:
                        pass

    def result(self):
        try:
            m = self.sess.get(f"{B}/markets/{self.mk['cid']}", timeout=8).json().get("market", {})
            r = m.get("result")
            return 1 if r == "yes" else (0 if r == "no" else None)
        except Exception:
            return None


def emit(out, mkt, r, fills_fh, wins_fh):
    """Window + fills rows in the shadow_compare schema (venue-tagged; net == gross, no rebate)."""
    mk = mkt.mk
    def sample_at(t_target):
        for e in mkt.midtl.get(mk["up"], []):
            if e[0] >= t_target:
                return e[1]
        return None
    row = {"ts": now_iso(), "ws": mk["ws"], "resolved_up": r, "asset": mk["asset"],
           "tenor_min": 15, "venue": "kalshi"}
    for v in mkt.variants:
        gross = 0.0
        for f in v.fill_log:
            if f["sz"] <= 0 or r is None:
                continue
            settle_tok = r if f["up"] else 1 - r
            gross += f["sz"] * ((f["p"] - settle_tok) if f["side"] == "ASK" else (settle_tok - f["p"]))
        row[v.name] = {"net": round(gross, 4), "gross": round(gross, 4), "fills": v.fills}
        for f in v.fill_log:
            rec = dict(f)
            rec.update({"ws": mk["ws"], "asset": mk["asset"], "tenor_min": 15, "venue": "kalshi",
                        "var": v.name, "up": int(f["up"]), "res_up": r})
            if r is not None:
                st = r if f["up"] else 1 - r
                rec["mo_res"] = round((f["p"] - st) if f["side"] == "ASK" else (st - f["p"]), 6)
                rec["pnl"] = round(f["sz"] * rec["mo_res"], 6)
            for h in (5, 30, 120, 300):
                md = sample_at(f["t"] + h)
                if md is not None and f["up"]:
                    rec[f"mo{h}"] = round((f["p"] - md) if f["side"] == "ASK" else (md - f["p"]), 4)
            fills_fh.write(json.dumps(rec) + "\n")
    wins_fh.write(json.dumps(row) + "\n")
    fills_fh.flush(); wins_fh.flush()
    parts = "  ".join(f"{v.name}={row[v.name]['net']:+.3f}({v.fills})"
                      for v in mkt.variants[:6])
    print(f"{now_iso()} SETTLE {mk['asset']} w={mk['ws']} r={r} | {parts}", flush=True)


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"kal{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)
    sess = requests.Session()
    mkts = {a: KalshiMarket(sess, a) for a in ASSETS}
    pend = []
    fhs = {a: (gzip.open(os.path.join(out_dir, f"fills_kalshi_{a}15m_{tag}.jsonl.gz"), "at"),
               open(os.path.join(out_dir, f"shadow_windows_kalshi_{a}15m_{tag}.jsonl"), "a"))
           for a in ASSETS}
    print(f"kalshi_collect: {len(mkts)} series, {dur}s, roster={len(strategies.enabled())}", flush=True)
    end = time.time() + dur
    while time.time() < end:
        t0 = time.time()
        for a, mkt in mkts.items():
            if mkt.mk is None or time.time() >= mkt.mk["we"]:
                if mkt.mk is not None:
                    pend.append((mkt.mk, mkt.variants, mkt.midtl, mkt, time.time()))
                    mkt.mk = None
                if mkt.discover():
                    print(f"{now_iso()} WINDOW {a} {mkt.mk['cid']} "
                          f"({datetime.fromtimestamp(mkt.mk['ws'], timezone.utc):%H:%M}Z)", flush=True)
            if mkt.mk is not None:
                mkt.poll()
        # settle pending (Kalshi posts results ~1-3 min after close)
        for item in pend[:]:
            mk2, var2, tl2, mkt2, t_closed = item
            if time.time() - t_closed < 45:
                continue
            shim = KalshiMarket.__new__(KalshiMarket)
            shim.sess = sess; shim.mk = mk2; shim.midtl = tl2; shim.variants = var2
            r = shim.result()
            if r is None and time.time() - t_closed < 600:
                continue
            emit(out_dir, shim, r, *fhs[mk2["asset"]])
            pend.remove(item)
        time.sleep(max(0.0, POLL_S - (time.time() - t0)))
    print(f"done (unsettled left: {len(pend)})", flush=True)


if __name__ == "__main__":
    main()
