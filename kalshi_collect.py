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

ULTRA-RICH CAPTURE (per asset, per run; everything raw, derivations belong offline):
  ticks_*.jsonl.gz   ~1Hz top-of-book timeline (mid/spot/micro + bb/bsz/ba/asz) -- legacy schema.
  trades_*.jsonl.gz  full taker tape with BOTH clocks: t (our poll) and ts_exch (exchange
                     created_time -- the honest event clock) + trade_id for cross-run dedupe.
  book_*.jsonl.gz    the new core stream, three record types:
                       "meta"  once per window: strike geometry, lifecycle times, settlement rules.
                       "book"  FULL DEPTH both sides (sub-cent fp levels), written on CHANGE only,
                               with request rtt_ms + spot at capture -- the displayed-queue ground
                               truth that q_ahead scans had to guess at.
                       "stat"  ~30s volume / open_interest / liquidity -- OI rising vs volume
                               churning separates fresh (informed) positioning from closeouts.
  shadow_windows_*.jsonl  window rows now also carry strike{} and final{} (settle-time
                     volume/OI/settlement_value) so each row is analysis-self-contained.

    python kalshi_collect.py [duration_s] [out_dir] [tag]      # default 3600 gha_data kal<ts>
"""
from __future__ import annotations

import gzip
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

import requests

import strategies
import shadow_compare as SC
from fvfeed import SpotFair
from shadow_compare import Variant, micro

SC.REBATE = 0.0   # Kalshi pays no maker rebate; micro_cal gate and Variant.rebate accrual use 0

B = "https://api.elections.kalshi.com/trade-api/v2"
ASSETS = ("btc", "eth", "sol", "xrp")
POLL_S = 1.2                  # per-asset book cadence (4 assets => ~5 req/s incl. trades, public-safe)

STOP = [False]   # set by SIGTERM -> graceful exit
_HB = [0.0]      # last heartbeat ts (throttle ~90s)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def heartbeat(tag, out_dir, windows_settled):
    """Write HEARTBEAT_kalshi_<tag>.json every ~90s and ping HEARTBEAT_URL if set."""
    now = time.time()
    if now - _HB[0] < 90:
        return
    _HB[0] = now
    try:
        os.makedirs(out_dir, exist_ok=True)
        json.dump({"utc": now_iso(), "tag": tag, "status": "running",
                   "windows_settled": windows_settled},
                  open(os.path.join(out_dir, f"HEARTBEAT_kalshi_{tag}.json"), "w"), indent=2)
        url = os.environ.get("HEARTBEAT_URL")
        if url:
            try:
                requests.get(url, timeout=8)
            except Exception:
                pass
    except Exception:
        pass


class KalshiMarket:
    """One asset's active 15-min market: discovery, book/trade polling, settlement."""

    def __init__(self, sess, asset, out_dir, tag):
        self.sess = sess
        self.asset = asset
        self.out_dir = out_dir
        self.tag = tag
        self.series = f"KX{asset.upper()}15M"
        self.mk = None
        self.variants = []
        self.shared = {}
        self.midtl = {}
        self.seen_trades = set()
        self.last_trades_poll = 0.0
        self.fv = SpotFair(requests.Session(), symbol=f"{asset.upper()}USDT")
        self.last_spot_poll = 0.0
        # per-window file handles (opened at discover)
        self._ticks_fh = None
        self._trades_fh = None
        self._book_fh = None      # FULL-DEPTH book stream (the q_ahead ground truth)
        self._book_hash = None    # dedupe: write a book record only when the book CHANGED
        self.last_stat_poll = 0.0  # volume/OI/liquidity sampling (~30s)

    def _open_window_files(self):
        """Open (append) per-window gzip streams for ticks, trades, and full-depth books."""
        tp = os.path.join(self.out_dir, f"ticks_kalshi_{self.asset}15m_{self.tag}.jsonl.gz")
        trp = os.path.join(self.out_dir, f"trades_kalshi_{self.asset}15m_{self.tag}.jsonl.gz")
        bp = os.path.join(self.out_dir, f"book_kalshi_{self.asset}15m_{self.tag}.jsonl.gz")
        self._ticks_fh = gzip.open(tp, "at")
        self._trades_fh = gzip.open(trp, "at")
        self._book_fh = gzip.open(bp, "at")

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
                   "cid": tk, "tick": 0.01, "asset": self.asset, "tenor_min": 15,
                   "_t_first": None, "_t_last": None, "_n_polls": 0, "_tickw": {}}
        self.shared = {"st": None, "s0": None, "flow": {}, "spothist": [], "microhist": {}, "qema": {}}
        self.variants = [Variant(s.name, self.mk, s.cap, s.skew, size_mode=s.size_mode, gate=s.gate,
                                 shared=self.shared, short_skew=s.short_skew, tau_guard=s.tau_guard,
                                 # thread per-strat AS_K/MO_K overrides (without these the sweep
                                 # arms silently duplicate their parents -- the no-op failure
                                 # strategies.validate() exists to prevent)
                                 as_k=getattr(s, "as_k", None), mo_k=getattr(s, "mo_k", None))
                         for s in strategies.enabled()]
        self.midtl = {}
        self.seen_trades = set()
        self._book_hash = None
        if self._ticks_fh is None:
            self._open_window_files()
        # MARKET METADATA record (strike geometry + lifecycle times + settlement plumbing): the
        # static facts the book/trade streams can't carry but every later analysis wants joined in.
        try:
            mfull = self.sess.get(f"{B}/markets/{tk}", timeout=8).json().get("market", {})
            meta = {k: mfull.get(k) for k in (
                "ticker", "event_ticker", "market_type", "strike_type",
                "floor_strike", "cap_strike", "custom_strike",
                "open_time", "close_time", "expected_expiration_time", "expiration_time",
                "settlement_timer_seconds", "category", "rules_primary",
                "tick_size", "notional_value", "response_price_units",
                "price_level_structure", "price_ranges",   # sub-cent tick geometry (deci-cent tails)
                "volume_fp", "open_interest_fp", "liquidity_dollars",
                "yes_bid_dollars", "yes_ask_dollars", "last_price_dollars") if k in mfull}
            if self._book_fh is not None:
                self._book_fh.write(json.dumps({
                    "type": "meta", "t": round(time.time(), 3), "ws": ws, "asset": self.asset,
                    "tenor_min": 15, "venue": "kalshi", "meta": meta}) + "\n")
            self.mk["_meta"] = meta
        except Exception:
            pass
        sp = self.fv.update()
        if sp and time.time() - ws <= 60:
            self.fv.set_window(sp); self.shared["s0"] = sp
        self.shared["st"] = sp
        return self.mk

    def poll(self):
        """One pass: spot, book -> set_tob both views, trades -> on_trade both views, timeline."""
        mk = self.mk
        nowt = time.time()
        # coverage tracking
        if mk.get("_t_first") is None:
            mk["_t_first"] = nowt
        mk["_t_last"] = nowt
        mk["_n_polls"] = mk.get("_n_polls", 0) + 1

        if nowt - self.last_spot_poll > 2:
            self.last_spot_poll = nowt
            sp = self.fv.update()
            if sp:
                self.shared["st"] = sp
                sh = self.shared["spothist"]; sh.append((nowt, sp))
                if len(sh) > 40:
                    del sh[:len(sh) - 40]
        try:
            t_req = time.time()
            ob = self.sess.get(f"{B}/markets/{mk['cid']}/orderbook", timeout=6).json()
            rtt_ms = (time.time() - t_req) * 1e3
        except Exception:
            return
        o = ob.get("orderbook_fp") or ob.get("orderbook") or {}
        yb = o.get("yes_dollars") or []; nb = o.get("no_dollars") or []
        if not yb or not nb:
            return
        ybb, ybq = float(yb[-1][0]), float(yb[-1][1])      # best YES bid
        nbb, nbq = float(nb[-1][0]), float(nb[-1][1])      # best NO bid
        yba = round(1.0 - nbb, 4)                          # YES ask (mirror)

        # FULL-DEPTH BOOK STREAM (sub-cent fp levels, ascending best-at-end, BOTH sides), written
        # only when the book CHANGED since the last poll. This is the q_ahead ground truth the
        # queue backtests had to scan as an unknown: displayed size at every level, every ~1.2s,
        # plus the request RTT so replays can model snapshot staleness honestly.
        if self._book_fh is not None:
            try:
                bh = hash((tuple(map(tuple, yb)), tuple(map(tuple, nb))))
                if bh != self._book_hash:
                    self._book_hash = bh
                    self._book_fh.write(json.dumps({
                        "type": "book", "t": round(nowt, 3), "ws": mk["ws"], "asset": self.asset,
                        "tenor_min": 15, "venue": "kalshi", "rtt_ms": round(rtt_ms, 1),
                        "spot": self.shared.get("st"),
                        "yes": [[float(p), float(q)] for p, q in yb],
                        "no": [[float(p), float(q)] for p, q in nb]}) + "\n")
            except Exception:
                pass

        # VOLUME / OPEN INTEREST / LIQUIDITY sampler (~30s): OI rising vs volume churning is the
        # cleanest public read on whether takers are opening fresh positions (informed flow risk)
        # or closing out -- not derivable from book or tape alone.
        if nowt - self.last_stat_poll > 30:
            self.last_stat_poll = nowt
            try:
                ms = self.sess.get(f"{B}/markets/{mk['cid']}", timeout=6).json().get("market", {})
                # Kalshi returns these as STRING "_fp" fields (e.g. open_interest_fp="165897.35");
                # the plain open_interest/volume keys are absent -> parse the _fp strings to float so
                # downstream OI-churn analysis sees real numbers, not nulls (collector bug 2026-06-11).
                def _f(x):
                    try:
                        return float(x)
                    except (TypeError, ValueError):
                        return None
                if self._book_fh is not None:
                    self._book_fh.write(json.dumps({
                        "type": "stat", "t": round(nowt, 3), "ws": mk["ws"], "asset": self.asset,
                        "tenor_min": 15, "venue": "kalshi",
                        "volume": _f(ms.get("volume_fp")),
                        "volume_24h": _f(ms.get("volume_24h_fp")),
                        "open_interest": _f(ms.get("open_interest_fp")),
                        "liquidity": _f(ms.get("liquidity_dollars")),
                        "last_price": _f(ms.get("last_price_dollars"))}) + "\n")
            except Exception:
                pass
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

        # incremental ticks flush every ~30s
        self._maybe_flush_ticks()

        if nowt - self.last_trades_poll > 2.5:
            self.last_trades_poll = nowt
            try:
                tr = self.sess.get(f"{B}/markets/trades",
                                   params={"ticker": mk["cid"], "limit": 100}, timeout=6).json()
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
                # persist raw taker trade tape. t = OUR poll time (smeared by the ~2.5s poll
                # cadence); ts_exch = the EXCHANGE's created_time -- the honest event clock for
                # ordering trades against book snapshots. trade_id kept for cross-run dedupe.
                if self._trades_fh is not None:
                    try:
                        ts_exch = None
                        ct_raw = t.get("created_time")
                        if ct_raw:
                            try:
                                ts_exch = round(datetime.fromisoformat(
                                    ct_raw.replace("Z", "+00:00")).timestamp(), 3)
                            except Exception:
                                pass
                        self._trades_fh.write(json.dumps({
                            "t": round(nowt, 3), "ts_exch": ts_exch, "tid": tid,
                            "ws": mk["ws"], "asset": self.asset,
                            "tenor_min": 15, "venue": "kalshi",
                            "up": 1, "side": "BUY" if buy_yes else "SELL",
                            "p": round(yp, 6), "sz": round(ct, 6)}) + "\n")
                    except Exception:
                        pass
                for v in self.variants:
                    try:                                   # one physical trade, both token views
                        v.on_trade(mk["up"], "BUY" if buy_yes else "SELL", yp, ct)
                        v.on_trade(mk["down"], "SELL" if buy_yes else "BUY", round(1.0 - yp, 4), ct)
                    except Exception:
                        pass

    def _maybe_flush_ticks(self, force=False):
        """Flush new ticks to the ticks file (~30s incremental or forced at settle/tombstone).
        Column order in output tuple: [t_off, mid@1, spot@2, micro@3, bb, bsz, ba, asz]
        matching the Polymarket schema (mid@1, spot@2, micro@3).
        Internal midtl tuple: (t, mid, micro, spot, bb, bsz, ba, asz) -> reorder for output."""
        mk = self.mk
        if mk is None or self._ticks_fh is None:
            return
        wptr = mk.setdefault("_tickw", {})
        last_flush = mk.setdefault("_last_tickflush", 0.0)
        if not force and time.time() - last_flush < 30:
            return
        mk["_last_tickflush"] = time.time()
        wrote = False
        for role, tok in (("up", mk["up"]), ("down", mk["down"])):
            tl = self.midtl.get(tok, [])
            w0 = wptr.get(tok, 0)
            if len(tl) <= w0:
                continue
            new = tl[w0:]
            wptr[tok] = len(tl)
            # internal: (t, mid, micro, spot, bb, bsz, ba, asz)
            # output:   [t_off, mid, spot, micro, bb, bsz, ba, asz]  <- match Polymarket schema
            self._ticks_fh.write(json.dumps({
                "ws": mk["ws"], "asset": self.asset, "tenor_min": 15,
                "venue": "kalshi", "role": role,
                "ticks": [[round(e[0] - mk["ws"], 1),
                           round(e[1], 4) if e[1] is not None else None,   # mid@1
                           round(e[3], 4) if e[3] is not None else None,   # spot@2
                           round(e[2], 4) if e[2] is not None else None,   # micro@3
                           e[4], e[5], e[6], e[7]] for e in new]}) + "\n")
            wrote = True
        if wrote:
            self._ticks_fh.flush()
        for fh in (self._trades_fh, self._book_fh):
            if fh is not None:
                try:
                    fh.flush()
                except Exception:
                    pass

    def result(self):
        try:
            m = self.sess.get(f"{B}/markets/{self.mk['cid']}", timeout=8).json().get("market", {})
            r = m.get("result")
            if r in ("yes", "no"):
                # final lifetime stats, captured once at settle (joined into the window row)
                self.mk["_final"] = {k: m.get(k) for k in (
                    "volume", "volume_fp", "open_interest", "open_interest_fp",
                    "liquidity_dollars", "liquidity", "last_price_dollars", "last_price",
                    "result", "settlement_value", "settlement_value_dollars",
                    "expiration_value") if k in m}
            return 1 if r == "yes" else (0 if r == "no" else None)
        except Exception:
            return None


def emit(out_dir, mkt, r, fills_fh, wins_fh):
    """Window + fills rows in the shadow_compare schema (venue-tagged; net == gross, no rebate).

    Per-variant stats come from v.attribution(r) for all 25 variants (works for ALL variants;
    with REBATE=0 net==gross). When r is None (tombstone), write with resolved_up=null and
    unresolved=true and skip attribution-based pnl (just write {"fills": v.fills} per variant).
    Per-fill rows from fill_log are written as-is for all variants.
    Coverage metadata is included from mk tracking fields.
    """
    mk = mkt.mk

    def sample_at(t_target):
        for e in mkt.midtl.get(mk["up"], []):
            if e[0] >= t_target:
                return e[1]
        return None

    row = {"ts": now_iso(), "ws": mk["ws"], "resolved_up": r, "asset": mk["asset"],
           "tenor_min": 15, "venue": "kalshi"}
    if r is None:
        row["unresolved"] = True
    # coverage
    row["coverage"] = {
        "t_first": round(mk["_t_first"] - mk["ws"], 1) if mk.get("_t_first") else None,
        "t_last": round(mk["_t_last"] - mk["ws"], 1) if mk.get("_t_last") else None,
        "n_polls": mk.get("_n_polls", 0),
    }
    # strike geometry + settle-time finals (joined here so window rows are self-contained)
    meta = mk.get("_meta") or {}
    row["strike"] = {k: meta.get(k) for k in
                     ("strike_type", "floor_strike", "cap_strike", "custom_strike") if meta.get(k) is not None}
    if mk.get("_final"):
        row["final"] = mk["_final"]

    for v in mkt.variants:
        if r is None:
            # tombstone: skip attribution-based pnl, just record fill count
            row[v.name] = {"fills": v.fills}
        else:
            # use v.attribution(r) for all variants (works for ALL 25; with REBATE=0, net==gross)
            try:
                attr = v.attribution(r)
            except Exception:
                attr = {"fills": v.fills}
            row[v.name] = attr

        # per-fill rows from fill_log (unchanged, only exist for LOG_FILLS variants)
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

    if r is not None:
        parts = "  ".join(f"{v.name}={row[v.name].get('net', 0):+.3f}({v.fills})"
                          for v in mkt.variants[:6])
        print(f"{now_iso()} SETTLE {mk['asset']} w={mk['ws']} r={r} | {parts}", flush=True)
    else:
        print(f"{now_iso()} TOMBSTONE {mk['asset']} w={mk['ws']} (unresolved; fills/ticks persisted)",
              flush=True)


def main():
    signal.signal(signal.SIGTERM, lambda *_: STOP.__setitem__(0, True))

    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"kal{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)
    sess = requests.Session()
    mkts = {a: KalshiMarket(sess, a, out_dir, tag) for a in ASSETS}
    pend = []
    windows_settled = 0

    fhs = {a: (gzip.open(os.path.join(out_dir, f"fills_kalshi_{a}15m_{tag}.jsonl.gz"), "at"),
               open(os.path.join(out_dir, f"shadow_windows_kalshi_{a}15m_{tag}.jsonl"), "a"))
           for a in ASSETS}

    # registry snapshot at startup
    try:
        rerrs = strategies.validate()
        if rerrs:
            print(f"{now_iso()} [ROSTER WARN] " + "; ".join(rerrs), flush=True)
        snap = strategies.snapshot()
        snap["tag"] = tag; snap["utc"] = now_iso(); snap["venue"] = "kalshi"
        json.dump(snap, open(os.path.join(out_dir, f"registry_kalshi_{tag}.json"), "w"), indent=2)
        print(f"{now_iso()} roster: {snap['n_enabled']} live {snap['enabled']}", flush=True)
    except Exception as e:
        print(f"{now_iso()} [ROSTER WARN] snapshot/validate failed: {type(e).__name__}: {e}", flush=True)

    print(f"kalshi_collect: {len(mkts)} series, {dur}s, roster={len(strategies.enabled())}", flush=True)
    end = time.time() + dur

    while time.time() < end and not STOP[0]:
        t0 = time.time()
        heartbeat(tag, out_dir, windows_settled)

        for a, mkt in mkts.items():
            if mkt.mk is None or time.time() >= mkt.mk["we"]:
                if mkt.mk is not None:
                    # flush ticks before retiring the window
                    mkt._maybe_flush_ticks(force=True)
                    pend.append((mkt.mk, mkt.variants, mkt.midtl, mkt, time.time()))
                    mkt.mk = None
                if not STOP[0] and mkt.discover():
                    print(f"{now_iso()} WINDOW {a} {mkt.mk['cid']} "
                          f"({datetime.fromtimestamp(mkt.mk['ws'], timezone.utc):%H:%M}Z)", flush=True)
            if mkt.mk is not None and not STOP[0]:
                mkt.poll()

        # settle pending (Kalshi posts results ~1-3 min after close)
        for item in pend[:]:
            mk2, var2, tl2, mkt2, t_closed = item
            if time.time() - t_closed < 45:
                continue
            shim = KalshiMarket.__new__(KalshiMarket)
            shim.sess = sess; shim.mk = mk2; shim.midtl = tl2; shim.variants = var2
            shim._ticks_fh = mkt2._ticks_fh
            r = shim.result()
            if r is None and time.time() - t_closed < 600:
                continue
            emit(out_dir, shim, r, *fhs[mk2["asset"]])
            windows_settled += 1
            pend.remove(item)

        time.sleep(max(0.0, POLL_S - (time.time() - t0)))

    # graceful drain: retry pending settles up to 3 times x 20s before tombstoning
    # (skip retries if STOP so we exit fast under SIGTERM)
    if not STOP[0]:
        for attempt in range(3):
            if not pend:
                break
            time.sleep(20)
            for item in pend[:]:
                mk2, var2, tl2, mkt2, t_closed = item
                shim = KalshiMarket.__new__(KalshiMarket)
                shim.sess = sess; shim.mk = mk2; shim.midtl = tl2; shim.variants = var2
                shim._ticks_fh = mkt2._ticks_fh
                r = shim.result()
                if r is None:
                    continue
                emit(out_dir, shim, r, *fhs[mk2["asset"]])
                windows_settled += 1
                pend.remove(item)

    # tombstone any still-unsettled windows (final ticks flush + r=None row)
    for item in pend:
        mk2, var2, tl2, mkt2, t_closed = item
        shim = KalshiMarket.__new__(KalshiMarket)
        shim.sess = sess; shim.mk = mk2; shim.midtl = tl2; shim.variants = var2
        shim._ticks_fh = mkt2._ticks_fh
        try:
            shim._maybe_flush_ticks(force=True)
        except Exception:
            pass
        emit(out_dir, shim, None, *fhs[mk2["asset"]])

    # write final heartbeat as stopped
    try:
        json.dump({"utc": now_iso(), "tag": tag, "status": "stopped",
                   "windows_settled": windows_settled},
                  open(os.path.join(out_dir, f"HEARTBEAT_kalshi_{tag}.json"), "w"), indent=2)
    except Exception:
        pass

    print(f"done (unsettled tombstoned: {len(pend)})", flush=True)


if __name__ == "__main__":
    main()
