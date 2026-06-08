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

Artifacts: shadow_windows.jsonl (per-variant per-window), shadow_summary.json (cum), shadow.log,
fills.jsonl (PER-FILL markout for baseline+micro_gate -> root-cause why each trade wins/loses).
    python shadow_compare.py --duration 57600
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
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
_HB = [0.0]          # last heartbeat ts (throttle)

# Per-fill markout logging: which variants emit a row PER fill (root-cause why each trade
# wins/loses). Kept to the baseline-vs-fix contrast to bound data volume; widen if needed.
LOG_FILLS = {"baseline", "micro_gate"}
MARKOUT_HORIZONS = (5, 30)   # seconds; resolution markout is added at settle (the decision metric)


def heartbeat(tag, out_dir, cum, status="running"):
    """Liveness: write HEARTBEAT.json (at-a-glance health) + ping an EXTERNAL dead-man's-switch
    (HEARTBEAT_URL env, e.g. healthchecks.io) which alerts the user if pings STOP -- the only
    layer that catches a total GitHub-Actions outage (the in-GitHub schedule/chain/watchdog can't
    report their own death). No-op if HEARTBEAT_URL unset. Throttled to ~90s."""
    now = time.time()
    if now - _HB[0] < 90:
        return
    _HB[0] = now
    wins = cum.get("baseline", {}).get("windows", 0) if cum else 0
    try:
        import os
        os.makedirs(out_dir, exist_ok=True)
        json.dump({"utc": now_iso(), "tag": tag, "status": status, "settled_windows": wins,
                   "cum": cum}, open(os.path.join(out_dir, f"HEARTBEAT_{tag}.json"), "w"), indent=2)
        url = os.environ.get("HEARTBEAT_URL")
        if url:
            requests.get(url, timeout=8)
    except Exception:
        pass



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
        self.fvol = self.tvol = self.mk_buy = self.mk_sell = self.maxd = 0.0  # attribution/capacity
        self.tob = {mk["up"]: [None, 0, None, 0], mk["down"]: [None, 0, None, 0]}
        self.queue = {}
        self.fill_log = []   # per-DECISION audit records (fills + skips); markout/pnl at settle
        self.skips = {"no_quote": 0, "queue_absorbed": 0}  # pure-mechanics non-decisions (counted)

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

    def _log_action(self, token, taker_side, price, tk_size, our_side, ahead, consume,
                    is_up, want, fill, reason):
        """Full audit record of ONE decision: what prompted it (the taker trade) + EVERY input
        the strategy considered + the resulting action/reason. Logged for fills AND skips so the
        counterfactual (why we did NOT trade) is auditable. markout/pnl added at settle."""
        tnow = time.time()
        bb, bsz, ba, asz = self.tob[token]
        midf = (bb + ba) / 2 if (bb is not None and ba is not None) else None
        micf = micro(bb, bsz, ba, asz)
        tot = (bsz or 0) + (asz or 0)
        imb = (bsz or 0) / tot if tot else None
        fair = self.fair_tok(token)
        tox = None if micf is None else ((micf - price) if our_side == "ASK" else (price - micf))
        spot = self.shared.get("st")                  # BTC spot at fill (fundamental context)
        fl = self.shared.get("flow", {}).get(token, [])
        flow5 = sum(s for (tt, s) in fl if tnow - tt <= 5)    # signed taker vol last 5s (informed flow)
        flow30 = sum(s for (tt, s) in fl if tnow - tt <= 30)  # signed taker vol last 30s
        self.fill_log.append({
            "t": tnow, "tau": round(max(self.mk["we"] - tnow, 0.0), 1),
            "reason": reason, "side": our_side, "up": is_up,
            "p": round(price, 6), "sz": round(fill, 6), "want": round(want, 3),
            # WHAT PROMPTED IT: the taker trade that hit our level + our queue position
            "tk_side": taker_side, "tk_sz": round(tk_size, 3),
            "q_ahead": round(ahead, 3), "q_used": round(consume, 3),
            # ALL INPUTS CONSIDERED at decision time
            "bb": bb, "ba": ba, "bsz": bsz, "asz": asz,
            "mid": round(midf, 4) if midf is not None else None,
            "micro": round(micf, 4) if micf is not None else None,
            "imb": round(imb, 3) if imb is not None else None,
            "fair": round(fair, 4) if fair is not None else None,
            "tox": round(tox, 4) if tox is not None else None,
            "spot": round(spot, 2) if spot is not None else None,
            "flow5": round(flow5, 2), "flow30": round(flow30, 2),
            "delta": round(self.delta, 3), "cap": self.cap,
            "skew_lim": round(self.skew * self.cap, 3), "gate": self.gate or "none"})

    def on_trade(self, token, side, price, size):
        if token not in self.tob:
            return
        self.tvol += size                         # total taker volume on our tokens (fill-rate denom)
        our_side = "ASK" if side == "BUY" else "BID"
        key = (token, our_side, round(price, 3))
        ahead = self.queue.get(key)
        if ahead is None:
            self.skips["no_quote"] += 1           # taker traded a level we were not quoting
            return
        consume = min(size, ahead); self.queue[key] = ahead - consume
        passthrough = size - consume
        if passthrough <= 0:
            self.skips["queue_absorbed"] += 1     # queue ahead of us absorbed the whole taker order
            return
        # --- a real decision: taker reached the front where we rest. Evaluate ALL gates. ---
        is_up = self.is_up(token); d_per = (-1.0 if (is_up == (side == "BUY")) else 1.0)
        want = self._size(token, our_side, price)
        fill = min(passthrough, want)
        if self._gated(token, our_side, price):
            reason, fill = "gated", 0.0
        elif abs(self.delta) >= self.skew * self.cap and (self.delta * d_per) > 0:
            reason, fill = "skew_block", 0.0
        else:
            if abs(self.delta + d_per * fill) > self.cap:
                room = max(0.0, self.cap - abs(self.delta)) if (self.delta + d_per * fill) * d_per > 0 else fill
                fill = min(fill, room)
                reason = "fill_clipped" if fill > 0 else "cap_zero"
            else:
                reason = "fill"
        if self.name in LOG_FILLS:                 # audit ledger: every decision + inputs + reason
            self._log_action(token, side, price, size, our_side, ahead, consume,
                             is_up, want, fill, reason)
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
        self.fvol += fill
        self.mk_sell += fill if sells else 0.0; self.mk_buy += 0.0 if sells else fill
        self.maxd = max(self.maxd, abs(self.delta))

    def settle(self, r):
        gross = self.cash + self.up_inv * r + self.dn_inv * (1 - r)
        return gross, gross + self.rebate

    def attribution(self, r):
        """Per-window P&L decomposition + capacity/balance fields (clustering unit = window)."""
        gross, net = self.settle(r)
        return {"net": round(net, 4), "gross": round(gross, 4), "rebate": round(self.rebate, 4),
                "fills": self.fills, "fill_vol": round(self.fvol, 1), "trade_vol": round(self.tvol, 1),
                "fill_rate": round(self.fvol / self.tvol, 4) if self.tvol else 0.0,
                "mk_buy_vol": round(self.mk_buy, 1), "mk_sell_vol": round(self.mk_sell, 1),
                "end_delta": round(self.delta, 1), "max_delta": round(self.maxd, 1)}


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
    # --tag/--out-dir give each GitHub-Actions run UNIQUE output files (gha_data/shadow_<tag>.*)
    # so concurrent/sequential runs never conflict on commit. Default = legacy fixed names.
    os.makedirs(args.out_dir, exist_ok=True)
    sfx = f"_{args.tag}" if args.tag else ""
    summary_path = os.path.join(args.out_dir, f"shadow_summary{sfx}.json")
    log = open(os.path.join(args.out_dir, f"shadow{sfx}.log"), "a")
    wins_fh = open(os.path.join(args.out_dir, f"shadow_windows{sfx}.jsonl"), "a")
    fills_fh = open(os.path.join(args.out_dir, f"fills{sfx}.jsonl"), "a")   # per-fill markout rows
    cum = {}; pending = []

    def L(s):
        line = f"{now_iso()} {s}"; print(line); log.write(line + "\n"); log.flush()

    def emit_fills(mk2, variants2, midtl2, r):
        """Write one row per logged fill with REAL markout (live mids) -> the per-trade
        win/lose root cause, and return per-variant Σ(pnl) for the audit reconciliation.
        Markout sign: >0 == favorable. tox>0 == book looked adverse at fill. Only queue
        position is modeled; the markout/pnl are real. KEY IDENTITY: pnl = sz*mo_res is the
        EXACT gross contribution of that fill, so Σ pnl over a window == window gross."""
        def sample_at(tok, t_target):
            """First timeline sample at/after t_target -> (mid, spot, actual_ts). For markout
            staleness: actual_ts reveals if the book was quiet (sample later than t_target)."""
            for (tt, md, _mc, sp) in midtl2.get(tok, []):
                if tt >= t_target:
                    return md, sp, tt
            return None, None, None
        def terminal_spot(tok):
            tl = midtl2.get(tok, [])
            return tl[-1][3] if tl else None
        pnl_sum = {}
        for v in variants2:
            s = 0.0
            for f in v.fill_log:
                sz = f["sz"]; p = f["p"]; sold = (f["side"] == "ASK")
                extra = {}
                if sz > 0:                        # an actual fill -> real markout + exact pnl
                    tok = mk2["up"] if f["up"] else mk2["down"]
                    settle_tok = r if f["up"] else (1 - r)
                    mo_res = (p - settle_tok) if sold else (settle_tok - p)
                    pnl = sz * mo_res             # exact gross contribution of this fill
                    s += pnl
                    mos = {}
                    for h in MARKOUT_HORIZONS:
                        md, _sp, tt = sample_at(tok, f["t"] + h)
                        mos[f"mo{h}"] = round((p - md) if sold else (md - p), 4) if md is not None else None
                        if h == 30 and tt is not None:        # markout staleness (auditability)
                            extra["mo30_dt"] = round(tt - f["t"], 1)
                    # BTC spot move after the fill -> separate fundamental move from flow toxicity
                    sp0 = f.get("spot")
                    if sp0:
                        _m, sp30, _t = sample_at(tok, f["t"] + 30)
                        spend = terminal_spot(tok)
                        extra["dspot30"] = round(sp30 - sp0, 2) if sp30 is not None else None
                        extra["dspot_end"] = round(spend - sp0, 2) if spend is not None else None
                else:                             # a skip (gated/skew/cap) -> no fill, no markout
                    mo_res = None; pnl = 0.0
                    mos = {f"mo{h}": None for h in MARKOUT_HORIZONS}
                rec = dict(f)                     # carry ALL decision inputs through verbatim
                rec["t"] = round(f["t"], 3)
                rec.update({"ws": mk2["ws"], "var": v.name, "up": int(f["up"]), "res_up": r,
                            "pnl": round(pnl, 6),
                            "mo_res": round(mo_res, 6) if mo_res is not None else None, **mos, **extra})
                fills_fh.write(json.dumps(rec) + "\n")
            pnl_sum[v.name] = s
        fills_fh.flush()
        return pnl_sum

    def try_settle():
        """Retry resolution for closed-but-unresolved windows (Polymarket posts the result
        minutes after window end). Settle + remove when resolved. (The bug in the first run
        was settling ONCE at close and skipping forever.)"""
        for item in pending[:]:
            mk2, variants2, midtl2 = item
            r = resolve(sess, mk2["ws"])
            if r is None:
                continue
            row = {"ts": now_iso(), "ws": mk2["ws"], "resolved_up": r}
            parts = []
            attrs = {}
            for v in variants2:
                attr = v.attribution(r); net = attr["net"]
                c = cum.setdefault(v.name, {"net": 0.0, "fills": 0, "windows": 0, "pos": 0})
                c["net"] += net; c["fills"] += v.fills; c["windows"] += 1; c["pos"] += 1 if net > 0 else 0
                row[v.name] = attr; attrs[v.name] = attr  # full per-window attribution (cluster unit = ws)
                parts.append(f"{v.name}={net:+.3f}({v.fills})")
            pnl_sum = emit_fills(mk2, variants2, midtl2, r)  # per-fill rows + Σpnl for reconciliation
            # AUDIT: per-fill ledger must reconcile to window gross to the penny (proof of completeness)
            row["audit"] = {}
            vmap = {v.name: v for v in variants2}
            for name in LOG_FILLS:               # reconcile ONLY the instrumented variants (others log no fills)
                if name not in pnl_sum:
                    continue
                s = pnl_sum[name]; g = attrs[name]["gross"]; resid = round(s - g, 6)
                v = vmap[name]
                tally = {}
                for f in v.fill_log:              # decision-reason histogram (gated/skew/fill/...)
                    tally[f["reason"]] = tally.get(f["reason"], 0) + 1
                row["audit"][name] = {"gross": round(g, 6), "fill_pnl_sum": round(s, 6),
                                      "resid": resid, "reasons": tally, "skips": dict(v.skips)}
                if abs(resid) > 1e-3:
                    L(f"  [AUDIT WARN] {name} w={mk2['ws']} per-fill Σpnl {s:.4f} != gross {g:.4f} (resid {resid:+.4f})")
            wins_fh.write(json.dumps(row) + "\n"); wins_fh.flush()
            json.dump(cum, open(summary_path, "w"), indent=2)
            L("SETTLE w=%d res=%d | %s" % (mk2["ws"], r, "  ".join(parts)))
            L("AUDIT w=%d | %s" % (mk2["ws"], "  ".join(
                f"{n}:resid={a['resid']:+.5f}" for n, a in row["audit"].items())))
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
        shared["flow"] = {}   # token -> [(t, signed_taker_size)] rolling trade-flow for informed-flow feature
        variants = configs(mk, shared)
        midtl = {}        # token -> [(t, mid, micro, spot)] shared timeline for per-fill markout
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
                        heartbeat(args.tag or "local", args.out_dir, cum)   # liveness + dead-man ping
                        data = json.loads(raw)
                        for m in (data if isinstance(data, list) else [data]):
                            et = m.get("event_type")
                            if et == "last_trade_price":      # update rolling trade-flow ONCE per trade
                                tok = str(m["asset_id"]); sgn = 1.0 if m["side"] == "BUY" else -1.0
                                fl = shared["flow"].setdefault(tok, [])
                                fl.append((time.time(), sgn * float(m["size"])))
                                if len(fl) > 4000:
                                    del fl[:2000]             # bound memory; 30s window is well within
                            for v in variants:
                                if et == "book":
                                    v.on_book(m)
                                elif et == "price_change":
                                    v.on_price_change(m)
                                elif et == "last_trade_price":
                                    v.on_trade(str(m["asset_id"]), m["side"], float(m["price"]), float(m["size"]))
                        # sample shared mid/micro/spot timeline (~1s/token) for per-fill markout
                        ts_now = time.time()
                        for tok in (mk["up"], mk["down"]):
                            bb, bsz, ba, asz = variants[0].tob[tok]
                            if bb is None or ba is None:
                                continue
                            tl = midtl.setdefault(tok, [])
                            if not tl or ts_now - tl[-1][0] >= 1.0:
                                tl.append((ts_now, (bb + ba) / 2, micro(bb, bsz, ba, asz), shared.get("st")))
            except Exception as e:  # noqa: BLE001
                L(f"  [ws reconnect] {str(e)[:70]}"); await asyncio.sleep(2)
        pending.append((mk, variants, midtl))   # settle later, with retry (resolution lags close)
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
    ap.add_argument("--tag", default="", help="suffix for output files (e.g. GH run id) -> unique, conflict-free")
    ap.add_argument("--out-dir", default=".", help="directory for output files")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
