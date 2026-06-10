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

import netfast  # latency-tuned keep-alive session (NODELAY/KEEPALIVE, warm pool)

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
MARKOUT_HORIZONS = (5, 30, 120, 300)   # s; +120/300 disambiguate transient impact vs regime (round2 #6)
FLOW_TOX = 150               # signed 30s taker-volume threshold for the flow gate (data: adverse >~200)
WINDOW_S = 900               # market window length (s); time-to-close normalizer
# Avellaneda-Stoikov inventory control: require microprice edge >= AS_K*|inventory|*(tau/T) to ADD
# inventory. Replaces arbitrary skew thresholds with a continuous, variance/time-scaled penalty.
# AS_K calibrated so the penalty reaches a half-spread (~0.005) near |inv|=cap/2 mid-window
# (0.005 / (25 * 0.5) = 4e-4); the lone free knob = risk aversion (gamma*sigma^2 lumped here).
AS_K = 4e-4
# spot_react gate: pull the side BTC just moved against (get ahead of the lag pickoff).
# bps-relative threshold (robust to BTC level/vol); lookback ~ the lead lag (calibrate via lead_lag.py).
SPOT_LAG_S = 2        # seconds of BTC lookback ~ the MEASURED lead (feed_race: coinbase leads token ~0.5-1s)
SPOT_BPS = 2.0        # |BTC move| over the lookback, in bps of spot, to trigger a pull
# micro_react: the lead-lag study showed the token's BOOK leads our slow BTC spot feed, so react to
# the BOOK's microprice velocity (the fast signal) -- the corrected version of spot_react.
MICRO_LAG_S = 4       # seconds of microprice lookback (book reacts fast)
MICRO_REACT_THR = 0.004   # |microprice move| over the lookback to trigger a pull (book just repriced)
DEPLETE_FRAC = 0.35   # deplete_gate: best-queue < this * its rolling avg => about to deplete (Fokker-Planck)
MICRO_MARGIN = 0.002  # micro_marg: required edge above microprice to fill (separate2: Q1+Q2 edge<0.001 toxic)
SOFT_MARGIN = 0.002   # micro_soft: BACKTEST-OPTIMAL gate (sweep on 10k fills: net +85.9 vs micro_gate +83.1);
#                       gate only tox>0.002 -> keep mildly-toxic fills (rebate>gross loss), cut only strongly-toxic
# --- gate_lab.py winners (validated on 56k fills / 141 windows, short-horizon mo5 markout = adverse selection)
STRICT_MARGIN = 0.003   # micro_strict: require micro edge in OUR favor by this; beats deployed micro (t=+6.2)
ASYM_ASK = 0.001        # micro_asym: SELL(ASK) side gated stricter (more toxic in data; t=+7.5, highest)
ASYM_BID = 0.002        # micro_asym: BUY(BID) side looser
LEAD_LAG_S = 30         # lead30: the 30s BTC move is a strong short-horizon toxicity flag (t=+6.2)
LEAD_BPS = 1.5          # |BTC move| over LEAD_LAG_S in bps of spot to pull the side it moved against
# micro_cal: calibrated ENSEMBLE -- ridge markout model fit by gate_lab.py -> gate_model.json. Keep a fill
# iff predicted short-horizon markout + maker_rebate(p) > 0 (auto-adapts the toxicity cutoff to the rebate).
try:
    _gm = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_model.json")))
    GATE_W = dict(zip(_gm["features"], _gm["weights"]))
except Exception:
    GATE_W = {}
TAKER_ENABLED = False  # lag_taker DISCONTINUED: offensive latency-take loses to the fee (-27.9/win)
# MAKEREDGE.md #7 vol_gate: adverse selection clusters in BTC vol bursts (the lead-lag pickoff). Pull
# BOTH sides when short-horizon BTC realized vol spikes; quote full size in calm regimes (Glosten-Milgrom).
VOL_LAG_S = 20        # lookback for BTC realized vol (s)
VOL_BPS = 6.0         # realized vol over the lookback, in bps of spot, above which we pull (calibrate)
MO_K = 150.0          # mo_size: size multiplier slope on micro-favorability (MAKEREDGE.md #3)
# MAKEREDGE.md #4 as_full: vol-adaptive A-S -> scale the calibrated `as` inventory penalty by realized
# vol vs this reference (A-S penalty ~ sigma^2). SIGMA_REF ~ a typical 20s BTC realized-vol fraction.
SIGMA_REF = 5e-4
# MAKERS.md (A3): per-share markout-to-resolution is positive in the moderate-probability band and
# ~0/negative at the extremes -> band_p/graded variants skip quoting outside [BAND_LO, BAND_HI].
BAND_LO = 0.20
BAND_HI = 0.80


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

    def __init__(self, name, mk, cap, skew, size_mode="flat", gate=None, shared=None,
                 short_skew=None, tau_guard=0):
        self.name = name; self.mk = mk; self.cap = cap; self.skew = skew
        self.tau_guard = tau_guard   # pull ALL quotes when < tau_guard seconds to close (late = informed)
        # asymmetric inventory leash: separate (usually tighter) threshold for building SHORT,
        # since buy-dominated flow forces us short and selling is the toxic side. Default = symmetric.
        self.short_skew = short_skew if short_skew is not None else skew
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
        if self.tau_guard and (self.mk["we"] - time.time()) < self.tau_guard:
            return True               # late-window pull: last-2min sells were the most adverse
        if self.gate == "micro_spot":  # cause+symptom: pull if EITHER book-imbalance OR BTC-lag flags
            return (self._gate_one("micro", token, our_side, price)
                    or self._gate_one("spot", token, our_side, price))
        if self.gate == "gross_max":   # MAXIMIZE non-rebate gross: union of all toxicity signals
            return (self._gate_one("micro", token, our_side, price)
                    or self._gate_one("spot", token, our_side, price)
                    or self._gate_one("deplete", token, our_side, price))
        if self.gate == "graded":      # MAKERS.md data: pull the WITH-move side at >=2bp (markout -4.7c)
            # OR the micro-adverse side, AND only quote the moderate-prob band (extremes markout ~0).
            return (self._gate_one("band", token, our_side, price)
                    or self._gate_one("micro", token, our_side, price)
                    or self._gate_one("spot", token, our_side, price))
        return self._gate_one(self.gate, token, our_side, price)

    def _realized_vol(self):
        """Short-horizon BTC realized vol over VOL_LAG_S, as a fraction of spot (std of spot in the
        window / mean). Book-native-adjacent: uses the shared spot trail. 0 if too little history."""
        hist = self.shared.get("spothist", [])
        now = time.time()
        xs = [sp for (tt, sp) in hist if sp is not None and now - tt <= VOL_LAG_S]
        if len(xs) < 3:
            return 0.0
        m = sum(xs) / len(xs)
        if m <= 0:
            return 0.0
        sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
        return sd / m

    def _gate_one(self, g, token, our_side, price):
        if g == "band":
            # MAKERS.md (A3): maker markout-to-resolution is best at P(Up) ~0.3-0.8 (+1.1..+2.3c/sh) and
            # ~0/negative at the extremes (<=0.1c: -0.5c; >=0.9: ~0). Skip quoting the deep ITM/OTM tails.
            cur = self.tob[token]
            if cur[0] is None or cur[2] is None:
                return False
            mid = (cur[0] + cur[2]) / 2.0
            p_up = mid if self.is_up(token) else 1.0 - mid
            return p_up < BAND_LO or p_up > BAND_HI
        if g == "vol":
            # MAKEREDGE.md #7: pull BOTH sides in a BTC volatility burst (informed-flow risk spikes).
            return self._realized_vol() * 1e4 > VOL_BPS
        if g == "as_full":
            # MAKEREDGE.md #4: VOL-ADAPTIVE Avellaneda-Stoikov. Same calibrated inventory penalty as the
            # `as` gate (AS_K reaches ~half-spread at |inv|=cap/2 mid-window) but scaled by current BTC
            # realized vol vs a reference (A-S penalty is proportional to sigma^2): more protective in vol
            # bursts, more permissive when calm. Bounded [0.5x,3x] so it never degenerates in a 1-tick book.
            # (The A-S ln(1+gamma/kappa) base-spread term is the tick here, already enforced by the touch.)
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            d_per = -1.0 if (self.is_up(token) == (our_side == "ASK")) else 1.0
            if self.delta * d_per < 0:
                return False                          # reduces |inventory| -> never gate
            edge = (price - mp) if our_side == "ASK" else (mp - price)
            tau = max(self.mk["we"] - time.time(), 0.0)
            vol_scale = min(3.0, max(0.5, self._realized_vol() / SIGMA_REF))
            penalty = AS_K * vol_scale * abs(self.delta) * (tau / WINDOW_S)
            return edge < penalty
        if g == "micro":
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            # selling (ASK) toxic if microprice above our ask (book tipping up); BID toxic if below
            return (our_side == "ASK" and mp > price) or (our_side == "BID" and mp < price)
        if g == "micro_soft":
            # MAKER_CHANGES2 #3: gate ONLY strongly-toxic fills (micro past price by > SOFT_MARGIN) so we
            # keep more rebate volume than micro_gate while staying gross-positive. Find the fill-count sweet spot.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            return (our_side == "ASK" and mp > price + SOFT_MARGIN) or (our_side == "BID" and mp < price - SOFT_MARGIN)
        if g == "micro_ufat":
            # MAKER_CHANGES2 #4: gate HARDER near p~0.5 (where adverse selection + fee peak; band_p showed
            # mid is most toxic) and LOOSER at the extremes -> margin scales with 4*p*(1-p).
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None or cur[0] is None or cur[2] is None:
                return False
            mid = (cur[0] + cur[2]) / 2.0; m = MICRO_MARGIN * 4.0 * mid * (1.0 - mid)
            return (our_side == "ASK" and mp > price - m) or (our_side == "BID" and mp < price + m)
        if g == "ufat_band":
            # combo_lab BEST overall (IS+OOS): micro_ufat gate AND drop the toxic mid-prob zone (INSIGHTS_4DAY
            # #5: P(up) 0.30-0.55 is the most adverse; >0.7 tail is the only benign one). notmid + ufat ~doubled
            # OOS net/win vs ufat alone (+16.5 vs +6.9, OOS mo5 +3.3). (spread1 was tried and HURTS -> excluded.)
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None or cur[0] is None or cur[2] is None:
                return False
            mid = (cur[0] + cur[2]) / 2.0
            if 0.30 <= mid < 0.55:
                return True                                  # notmid: skip the toxic mid-prob band
            m = MICRO_MARGIN * 4.0 * mid * (1.0 - mid)       # ufat p-adaptive margin
            return (our_side == "ASK" and mp > price - m) or (our_side == "BID" and mp < price + m)
        if g == "micro_marg":
            # refinement (separate2.py): even small-positive-edge fills (edge 0..0.001) were toxic;
            # require an edge MARGIN, not just edge>0 -> skip unless selling >MARGIN above micro
            # (resp. buying >MARGIN below). Cuts the Q1+Q2 toxic buckets; trades rebate volume for it.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            return (our_side == "ASK" and mp > price - MICRO_MARGIN) or \
                   (our_side == "BID" and mp < price + MICRO_MARGIN)
        if g == "tox":
            # gate the top of the composite-toxicity distribution (separate2.py): skip if the edge
            # is below margin OR the book is at the bid-HEAVY extreme (sells) / ask-heavy (buys).
            # Operationalizes "avoid high-tox, keep low-tox" -- keeps rebate on the mild fills.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            edge_lo = (our_side == "ASK" and mp > price - MICRO_MARGIN) or \
                      (our_side == "BID" and mp < price + MICRO_MARGIN)
            tot = (cur[1] or 0) + (cur[3] or 0)
            imb = (cur[1] or 0) / tot if tot else 0.5
            imb_tox = (our_side == "ASK" and imb > 0.85) or (our_side == "BID" and imb < 0.15)
            return edge_lo or imb_tox
        if g == "deplete":
            # Fokker-Planck: the touch moves when a best queue DEPLETES. Ask queue collapsing
            # (asz << its rolling avg) => book about to step UP => selling toxic; bid collapsing =>
            # step DOWN => buying toxic. Scale-invariant (q/q_avg). BOOK-OBSERVABLE (unlike queue position).
            cur = self.tob[token]; bsz, asz = cur[1], cur[3]
            qe = self.shared.get("qema", {}).get(token)
            if not qe:
                return False
            if our_side == "ASK":
                return qe["a"] > 0 and asz < DEPLETE_FRAC * qe["a"]
            return qe["b"] > 0 and bsz < DEPLETE_FRAC * qe["b"]
        if g == "predict":
            ft = self.fair_tok(token)
            if ft is None:
                return False
            return (our_side == "ASK" and price < ft - FV_MARGIN) or \
                   (our_side == "BID" and price > ft + FV_MARGIN)
        if g == "flow":
            # informed-flow gate: pull the side a recent same-side taker burst is hitting.
            # data: SELL 30s-markout turns adverse when flow30 (signed taker vol) > ~200.
            fl = self.shared.get("flow", {}).get(token, [])
            now = time.time()
            f30 = sum(s for (tt, s) in fl if now - tt <= 30)
            return (our_side == "ASK" and f30 > FLOW_TOX) or (our_side == "BID" and f30 < -FLOW_TOX)
        if g == "spot":
            # get on the RIGHT side of the BTC->token lag: if BTC just moved, the token fair is
            # about to follow -> pull the side we'd be picked off on, BEFORE it reprices.
            hist = self.shared.get("spothist", [])
            st = self.shared.get("st")
            if st is None or len(hist) < 2:
                return False
            now = time.time()
            prev = None
            for (tt, sp) in hist:                 # most recent spot that is >= SPOT_LAG_S old
                if tt <= now - SPOT_LAG_S:
                    prev = sp
            if prev is None:
                prev = hist[0][1]                 # history too short -> use oldest available
            dspot = st - prev
            thr = st * SPOT_BPS / 1e4
            token_dir = 1.0 if self.is_up(token) else -1.0
            fair_move = token_dir * dspot         # how the token's fair just moved
            return (our_side == "ASK" and fair_move > thr) or (our_side == "BID" and fair_move < -thr)
        if g == "micro_react":
            # RIGHT side of the lag via the FAST signal: the token's own microprice (it leads our
            # slow spot feed). If micro just moved, the touch is about to reprice -> pull the side
            # we'd be picked off on, before the taker lifts our stale quote. (corrected spot_react)
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            hist = self.shared.get("microhist", {}).get(token, [])
            if mp is None or len(hist) < 2:
                return False
            now = time.time()
            prev = None
            for (tt, mv) in hist:                 # most recent microprice >= MICRO_LAG_S old
                if tt <= now - MICRO_LAG_S:
                    prev = mv
            if prev is None:
                prev = hist[0][1]
            dmicro = mp - prev
            return (our_side == "ASK" and dmicro > MICRO_REACT_THR) or \
                   (our_side == "BID" and dmicro < -MICRO_REACT_THR)
        if g == "as":
            # Avellaneda-Stoikov: only ADD inventory if the microprice edge clears a penalty that
            # grows with current inventory and time-to-close (variance-based, NOT P&L-based). Fills
            # that REDUCE inventory are always welcome. Edge at the touch = spread*(1-imbalance), so
            # this also pulls into toxic (imbalanced) flow -- it unifies skew + imbalance control.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            is_up = self.is_up(token)
            d_per = -1.0 if (is_up == (our_side == "ASK")) else 1.0
            if self.delta * d_per < 0:               # reduces |inventory| -> never gate
                return False
            edge = (price - mp) if our_side == "ASK" else (mp - price)
            tau = max(self.mk["we"] - time.time(), 0.0)
            penalty = AS_K * abs(self.delta) * (tau / WINDOW_S)
            return edge < penalty
        # --- gate_lab.py winners (validated on 56k fills; see GATING.md) ---
        if g == "micro_strict":
            # require the micro edge in OUR favor by STRICT_MARGIN (deployed micro@0 keeps mildly-adverse
            # fills). Best short-horizon markout (t=+6.2); sheds rebate volume, so the deployable winner vs
            # micro depends on the realized rebate -> live A/B decides.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            tox = (mp - price) if our_side == "ASK" else (price - mp)   # >0 = adverse
            return tox > -STRICT_MARGIN
        if g == "micro_asym":
            # SELL(ASK) side is more toxic -> gate it stricter than BID (t=+7.5, the most significant).
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return False
            tox = (mp - price) if our_side == "ASK" else (price - mp)
            return tox > (-ASYM_ASK if our_side == "ASK" else ASYM_BID)
        if g == "lead30":
            # the 30s BTC move is a strong short-horizon toxicity flag (t=+6.2): pull the side BTC just
            # moved against, before the token reprices. (= spot gate, but a 30s lookback, which dominates.)
            hist = self.shared.get("spothist", []); st = self.shared.get("st")
            if st is None or len(hist) < 2:
                return False
            now = time.time(); prev = None
            for (tt, sp) in hist:
                if tt <= now - LEAD_LAG_S:
                    prev = sp
            if prev is None:
                prev = hist[0][1]
            dspot = st - prev; thr = st * LEAD_BPS / 1e4
            fair_move = (1.0 if self.is_up(token) else -1.0) * dspot
            return (our_side == "ASK" and fair_move > thr) or (our_side == "BID" and fair_move < -thr)
        if g == "micro_cal":
            # the calibrated ENSEMBLE (gate_lab #10): predict short-horizon markout from book features and
            # keep iff predicted markout + maker_rebate(p) > 0 -- the toxicity cutoff AUTO-ADAPTS to the
            # rebate (the deployable objective). Weights = ridge fit on 56k fills (gate_model.json, OOS-tested).
            cur = self.tob[token]; bb, bsz, ba, asz = cur
            mp = micro(bb, bsz, ba, asz)
            if mp is None or bb is None or ba is None:
                return False
            now = time.time()
            tox = (mp - price) if our_side == "ASK" else (price - mp)
            mid = (bb + ba) / 2.0
            fl = self.shared.get("flow", {}).get(token, [])
            f30 = sum(s for (tt, s) in fl if now - tt <= 30)
            flow_adv = f30 if our_side == "ASK" else -f30
            dspot = 0.0
            hist = self.shared.get("spothist", []); st = self.shared.get("st")
            if st is not None and len(hist) >= 2:
                prev = None
                for (tt, sp) in hist:
                    if tt <= now - LEAD_LAG_S:
                        prev = sp
                if prev is None:
                    prev = hist[0][1]
                d = (1.0 if self.is_up(token) else -1.0) * (st - prev)
                dspot = d if our_side == "ASK" else -d
            tau = max(self.mk["we"] - now, 0.0)
            feat = {"bias": 1.0, "tox": tox, "flow": flow_adv / 100.0, "dspot": dspot,
                    "spread": (ba - bb) * 100.0, "fat(p)": 4.0 * mid * (1.0 - mid),
                    "q_ahead": 0.0, "tk_sz": 0.0, "tau": tau / 900.0,
                    "is_ask": 1.0 if our_side == "ASK" else 0.0}
            pred = sum(GATE_W.get(k, 0.0) * v for k, v in feat.items())   # predicted per-share markout
            return (pred + fees.maker_rebate(price, rate=REBATE)) <= 0.0  # drop iff predicted NET <= 0
        return False

    def _size(self, token, our_side, price):
        if self.size_mode == "markout":
            # MAKEREDGE.md #3: scale size by micro-favorability (continuous micro_gate). Size UP when
            # selling above / buying below the microprice (benign), to ZERO when adverse. fill_prob is
            # fixed (1-tick, at the touch), so we steer the controllable term E[markout|fill] via size.
            cur = self.tob[token]; mp = micro(cur[0], cur[1], cur[2], cur[3])
            if mp is None:
                return self.post
            fav = (price - mp) if our_side == "ASK" else (mp - price)   # >0 = favorable (vs microprice)
            return self.post * min(max(1.0 + MO_K * fav, 0.0), 2.0)
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
        # complete-set BOX premiums at fill (cross-token; this variant tracks both tobs). A complete set
        # (UP+DOWN) settles to exactly $1, so two conventions matter and they are NOT the same edge:
        #   MAKER box (box_ask/box_bid): the round-trip spread you earn if you REST on both legs and both
        #     fill (ask_up+ask_dn-1 ; 1-bid_up-bid_dn). In a 1-tick market this is ~+1 tick mechanically
        #     -- it is the MM spread we already harvest, with legging risk (only risk-free if BOTH fill).
        #   TAKER box (box_sell_tk/box_buy_tk): the genuinely risk-free/direction-free/fee-free arb you
        #     CROSS into -- sell both into the bids when bid_up+bid_dn>1, or buy both at the asks when
        #     ask_up+ask_dn<1. >0 here = free money even as a taker; the literature says this is competed
        #     away in liquid 15m crypto (sub-100ms bots, dynamic fee). Logging it settles that empirically.
        other = self.mk["down"] if token == self.mk["up"] else self.mk["up"]
        obb, _obsz, oba, _oasz = self.tob[other]
        box_ask = (ba + oba - 1.0) if (ba is not None and oba is not None) else None     # MAKER sell-both spread
        box_bid = (1.0 - (bb + obb)) if (bb is not None and obb is not None) else None   # MAKER buy-both spread
        box_sell_tk = (bb + obb - 1.0) if (bb is not None and obb is not None) else None  # TAKER sell-both (free if >0)
        box_buy_tk = (1.0 - (ba + oba)) if (ba is not None and oba is not None) else None  # TAKER buy-both (free if >0)
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
            "box_ask": round(box_ask, 4) if box_ask is not None else None,
            "box_bid": round(box_bid, 4) if box_bid is not None else None,
            "box_sell_tk": round(box_sell_tk, 4) if box_sell_tk is not None else None,
            "box_buy_tk": round(box_buy_tk, 4) if box_buy_tk is not None else None,
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
        # asymmetric leash: tighter threshold when this fill BUILDS short (d_per<0), looser when long
        lim = (self.short_skew if d_per < 0 else self.skew) * self.cap
        if self._gated(token, our_side, price):
            reason, fill = "gated", 0.0
        elif abs(self.delta) >= lim and (self.delta * d_per) > 0:
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


class TakerVar:
    """OFFENSIVE latency taker: on a fast BTC move (high-res WS feed), LIFT/HIT the stale book
    quote the book-reactor bots haven't repriced yet, paying the 0.07 taker fee. Tests whether
    being ahead of the laggard book beats the fee. (Complement to the spot_react/micro_react
    defense.) PAPER UPPER BOUND -- reacts instantly; live haircut = our order latency vs the lead."""

    def __init__(self, name, mk, shared, thr_bps=2.5, lag_s=1.0, size=20.0, cooldown=4.0, cap=200.0):
        self.name = name; self.mk = mk; self.shared = shared
        self.thr_bps = thr_bps; self.lag_s = lag_s; self.size = size; self.cooldown = cooldown; self.cap = cap
        self.cash = self.up_inv = self.dn_inv = self.fee = 0.0
        self.takes = 0; self.last_take = 0.0
        self.tob = {mk["up"]: [None, 0, None, 0], mk["down"]: [None, 0, None, 0]}
        self.fill_log = []

    def on_book(self, m):
        token = str(m["asset_id"])
        if token not in self.tob:
            return
        bids = m.get("bids") or []; asks = m.get("asks") or []
        bb = max((float(b["price"]) for b in bids), default=None)
        ba = min((float(a["price"]) for a in asks), default=None)
        bsz = sum(float(b["size"]) for b in bids if float(b["price"]) == bb) if bb is not None else 0
        asz = sum(float(a["size"]) for a in asks if float(a["price"]) == ba) if ba is not None else 0
        self.tob[token] = [bb, bsz, ba, asz]

    def on_price_change(self, m):
        for pc in m.get("price_changes", []):
            token = str(pc["asset_id"])
            if token not in self.tob:
                continue
            cur = self.tob[token]
            bb = float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else cur[0]
            ba = float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else cur[2]
            self.tob[token] = [bb, cur[1], ba, cur[3]]

    def step(self):
        """On a qualifying BTC move, take the stale Up-token quote in the move's direction."""
        if not TAKER_ENABLED:        # DISCONTINUED: offensive taker fails the 0.07 fee (-27.9/win,
            return                   # matches offline + literature prior). Re-enable if fee/lead changes.
        now = time.time()
        if now - self.last_take < self.cooldown:
            return
        hist = self.shared.get("spothist", []); st = self.shared.get("st")
        if st is None or len(hist) < 2:
            return
        prev = None
        for (tt, sp) in hist:
            if tt <= now - self.lag_s:
                prev = sp
        if prev is None:
            return
        dspot = st - prev
        if abs(dspot) < st * self.thr_bps / 1e4:
            return
        up = self.mk["up"]; bb, bsz, ba, asz = self.tob[up]
        if dspot > 0 and ba is not None and asz > 0 and self.up_inv < self.cap:   # Up fair rising -> buy stale ask
            sz = min(self.size, asz)
            self.cash -= ba * sz; self.up_inv += sz; self.fee += float(fees.taker_fee(ba)) * sz
            self.fill_log.append({"t": now, "side": "BUY", "p": round(ba, 4), "sz": round(sz, 3), "dspot": round(dspot, 1)})
            self.takes += 1; self.last_take = now
        elif dspot < 0 and bb is not None and bsz > 0 and self.up_inv > -self.cap:  # Up fair falling -> sell stale bid
            sz = min(self.size, bsz)
            self.cash += bb * sz; self.up_inv -= sz; self.fee += float(fees.taker_fee(bb)) * sz
            self.fill_log.append({"t": now, "side": "SELL", "p": round(bb, 4), "sz": round(sz, 3), "dspot": round(dspot, 1)})
            self.takes += 1; self.last_take = now

    def settle(self, r):
        gross = self.cash + self.up_inv * r + self.dn_inv * (1 - r)
        return gross - self.fee, gross                      # net is AFTER the taker fee

    def attribution(self, r):
        net, gross = self.settle(r)
        return {"net": round(net, 4), "gross": round(gross, 4), "fee": round(self.fee, 4),
                "takes": self.takes, "end_delta": round(self.up_inv, 1)}


def configs(mk, shared):
    """Build the live Variant set from the declarative registry in strategies.py (the single source of
    truth). Add/remove/toggle strategies THERE, not here -- this just instantiates the enabled ones.
    DISCONTINUED long ago (kept only as history): cap100 (t=-2.68), sell_lean (-2.06/win), predict (t~0).
    Currently-pruned-but-defined variants live in strategies.REGISTRY with enabled=False."""
    import strategies
    return [Variant(s.name, mk, s.cap, s.skew, size_mode=s.size_mode, gate=s.gate,
                    shared=shared, short_skew=s.short_skew, tau_guard=s.tau_guard)
            for s in strategies.enabled()]


async def rtds_btc_feed(live):
    """PRIMARY BTC spot = Polymarket RTDS, served from Polymarket's own infra (eu-west-2, co-located
    with the CLOB). Strictly better than US Coinbase: (a) no transatlantic hop when the bot runs
    in-region, and (b) zero basis risk -- we react to the literal settlement source. Subscribes to
    BOTH in-region topics: crypto_prices_chainlink (btc/usd = the settlement truth, ~1/s) AND
    crypto_prices (btcusdt = higher-freq Binance, the source Chainlink aggregates) -> ~2/s combined.
    Coinbase (btc_ws_feed) stays as a gap-filler. Records feed_lat_ms = recv - payload ts."""
    url = "wss://ws-live-data.polymarket.com"
    sub = json.dumps({"action": "subscribe", "subscriptions": [
        {"topic": "crypto_prices_chainlink", "type": "*", "filters": "{\"symbol\":\"btc/usd\"}"},
        {"topic": "crypto_prices", "type": "*", "filters": "{\"symbol\":\"btcusdt\"}"}]})
    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=20, max_size=None) as ws:
                await ws.send(sub)
                async for raw in ws:
                    if not raw:                                  # empty ack frame -> keep the conn alive
                        continue
                    try:
                        pl = (json.loads(raw).get("payload") or {})
                    except Exception:
                        continue
                    val = pl.get("value")
                    if val is None and isinstance(pl.get("data"), list) and pl["data"]:
                        val = pl["data"][-1].get("value")        # bulk history frame -> seed latest point
                    if val is not None:
                        now = time.time()
                        live["px"] = float(val); live["ts"] = now
                        live["rtds_ts"] = now; live["src"] = "rtds"
                        live["n"] = live.get("n", 0) + 1
                        if pl.get("timestamp"):                  # feed latency telemetry (ms)
                            live["feed_lat_ms"] = round(now * 1e3 - float(pl["timestamp"]), 1)
        except Exception:  # noqa: BLE001 -- reconnect; Coinbase + REST cover the gap
            await asyncio.sleep(2)


async def btc_ws_feed(live):
    """FALLBACK BTC spot via Coinbase WS ticker (free, no key). Now a gap-filler behind RTDS
    (rtds_btc_feed): only writes live{px} when RTDS has been silent >3s, so the in-region settlement
    feed is preferred whenever it is delivering. Still high-res (~8 ticks/s) for RTDS dropouts.
    Updates live{px,ts}; reconnects forever; the REST poll (fvfeed) stays as sigma/anchor/last resort."""
    url = "wss://ws-feed.exchange.coinbase.com"
    sub = json.dumps({"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]})
    while True:
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=20, max_size=None) as ws:
                await ws.send(sub)
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type") == "ticker" and m.get("price"):
                        if time.time() - live.get("rtds_ts", 0.0) <= 3.0:
                            continue                              # RTDS is fresh -> defer to it
                        live["px"] = float(m["price"]); live["ts"] = time.time()
                        live["src"] = "cb"
                        live["n"] = live.get("n", 0) + 1     # WS tick counter (confirms feed alive on GHA)
        except Exception:  # noqa: BLE001 -- reconnect; REST poll covers the gap
            await asyncio.sleep(2)


async def run(args):
    sess = netfast.fast_session()      # latency-tuned keep-alive session (NODELAY, warm pool)
    fv = SpotFair(sess)
    live = {"px": None, "ts": 0.0, "n": 0, "rtds_ts": 0.0, "src": None}   # latest BTC (n = tick count)
    asyncio.create_task(rtds_btc_feed(live))   # PRIMARY: in-region Chainlink+Binance settlement feed
    asyncio.create_task(btc_ws_feed(live))     # FALLBACK: Coinbase, gap-fills when RTDS is silent
    # --tag/--out-dir give each GitHub-Actions run UNIQUE output files (gha_data/shadow_<tag>.*)
    # so concurrent/sequential runs never conflict on commit. Default = legacy fixed names.
    os.makedirs(args.out_dir, exist_ok=True)
    sfx = f"_{args.tag}" if args.tag else ""
    summary_path = os.path.join(args.out_dir, f"shadow_summary{sfx}.json")
    log = open(os.path.join(args.out_dir, f"shadow{sfx}.log"), "a")
    wins_fh = open(os.path.join(args.out_dir, f"shadow_windows{sfx}.jsonl"), "a")
    fills_fh = open(os.path.join(args.out_dir, f"fills{sfx}.jsonl"), "a")   # per-fill markout rows
    ticks_fh = open(os.path.join(args.out_dir, f"ticks{sfx}.jsonl"), "a")   # joint (mid,spot) series for lead-lag
    cum = {}; pending = []

    def L(s):
        line = f"{now_iso()} {s}"; print(line); log.write(line + "\n"); log.flush()

    # PREFLIGHT + SELF-DESCRIBING DATA: validate the declarative roster before collecting (an unknown
    # gate would silently behave like baseline), and write a snapshot so the captured data records
    # exactly which strategy set produced it. Failing validation here is loud but non-fatal -- we still
    # collect the well-formed variants rather than waste the run slot.
    try:
        import strategies
        rerrs = strategies.validate()
        if rerrs:
            L("[ROSTER WARN] " + "; ".join(rerrs))
        snap = strategies.snapshot()
        snap["tag"] = args.tag or "local"; snap["utc"] = now_iso()
        json.dump(snap, open(os.path.join(args.out_dir, f"registry{sfx}.json"), "w"), indent=2)
        L(f"roster: {snap['n_enabled']} live {snap['enabled']}  (pruned: {snap['disabled']})")
    except Exception as e:
        L(f"[ROSTER WARN] snapshot/validate failed: {type(e).__name__}: {e}")

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
            mk2, variants2, midtl2, taker2 = item
            r = resolve(sess, mk2["ws"], mk2.get("asset", "btc"), mk2.get("tenor_min", 15))
            if r is None:
                continue
            row = {"ts": now_iso(), "ws": mk2["ws"], "resolved_up": r,
                   "asset": mk2.get("asset", "btc"), "tenor_min": mk2.get("tenor_min", 15)}
            parts = []
            attrs = {}
            for v in variants2:
                if getattr(v, "broken", False):
                    continue                       # quarantined variant: omit (its state is unreliable)
                try:
                    attr = v.attribution(r); net = attr["net"]
                except Exception as e:
                    L(f"  [SETTLE SKIP] {v.name}: attribution failed: {type(e).__name__}: {e}")
                    continue
                c = cum.setdefault(v.name, {"net": 0.0, "fills": 0, "windows": 0, "pos": 0})
                c["net"] += net; c["fills"] += v.fills; c["windows"] += 1; c["pos"] += 1 if net > 0 else 0
                row[v.name] = attr; attrs[v.name] = attr  # full per-window attribution (cluster unit = ws)
                parts.append(f"{v.name}={net:+.3f}({v.fills})")
            t_attr = taker2.attribution(r)        # offensive taker (own settle; net is post-fee)
            ct = cum.setdefault(taker2.name, {"net": 0.0, "fills": 0, "windows": 0, "pos": 0})
            ct["net"] += t_attr["net"]; ct["fills"] += t_attr["takes"]; ct["windows"] += 1
            ct["pos"] += 1 if t_attr["net"] > 0 else 0
            row[taker2.name] = t_attr; attrs[taker2.name] = t_attr
            parts.append(f"{taker2.name}={t_attr['net']:+.3f}({t_attr['takes']}t)")
            pnl_sum = emit_fills(mk2, variants2, midtl2, r)  # per-fill rows + Σpnl for reconciliation
            # persist joint (mid, spot) series ~every 2s for the BTC->token LEAD-LAG study (raw, model-free)
            up_tl = midtl2.get(mk2["up"], [])
            ticks = [[round(t - mk2["ws"], 1), round(md, 4), round(sp, 1)]
                     for (t, md, _mc, sp) in up_tl if sp is not None]   # ~1s (high-res for lead-lag)
            if ticks:
                ticks_fh.write(json.dumps({"ws": mk2["ws"], "res_up": r,
                                           "feed": mk2.get("_feed", "rest"), "ticks": ticks}) + "\n")
                ticks_fh.flush()
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
            # taker reconciliation: Σ per-take pnl - fee == net
            tg = sum(f["sz"] * ((r - f["p"]) if f["side"] == "BUY" else (f["p"] - r)) for f in taker2.fill_log)
            t_resid = round((tg - taker2.fee) - t_attr["net"], 6)
            row["audit"][taker2.name] = {"net": t_attr["net"], "gross": round(tg, 6),
                                         "fee": round(taker2.fee, 4), "takes": t_attr["takes"], "resid": t_resid}
            if abs(t_resid) > 1e-3:
                L(f"  [AUDIT WARN] {taker2.name} w={mk2['ws']} taker resid {t_resid:+.4f}")
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
        mk = active_market(sess, args.asset, args.tenor_min)
        if mk is None:
            await asyncio.sleep(5); continue
        shared = {"st": None, "s0": None}
        rest = fv.update()                              # keeps the REST tape alive (sigma/fallback)
        sp = live["px"] if live["px"] is not None else rest   # prefer the high-res WS price
        if sp and time.time() - mk["ws"] <= 60:        # only anchor S0 on a fresh window
            fv.set_window(sp); shared["s0"] = sp
        shared["st"] = sp
        shared["flow"] = {}   # token -> [(t, signed_taker_size)] rolling trade-flow for informed-flow feature
        shared["spothist"] = [(time.time(), sp)] if sp else []  # (t, BTC spot) trail for spot_react
        shared["microhist"] = {}   # token -> [(t, microprice)] trail for micro_react (book lead signal)
        shared["qema"] = {}        # token -> {b,a} EMA of best-queue sizes for deplete_gate (Fokker-Planck)
        variants = configs(mk, shared)
        taker = TakerVar("lag_taker", mk, shared)   # offensive latency-arb test (own settle/audit)
        ws_n0 = live["n"]                            # WS tick count at window open (feed-source tag)
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
                        # high-res BTC: prefer the sub-second WS feed (it leads our REST poll & the token)
                        if live["px"] is not None and time.time() - live["ts"] < 8:
                            shared["st"] = live["px"]
                        if time.time() - last_spot > 2:        # REST poll: keep sigma/tape alive + fallback
                            rest = fv.update(); last_spot = time.time()
                            if not (live["px"] is not None and time.time() - live["ts"] < 8):
                                shared["st"] = rest or shared["st"]
                            if shared["st"] is not None:       # trail BTC spot for spot_react (prune ~30s)
                                sh = shared["spothist"]; sh.append((time.time(), shared["st"]))
                                if len(sh) > 40:
                                    del sh[:len(sh) - 40]
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
                                if getattr(v, "broken", False):
                                    continue                  # auto-disabled after repeated errors
                                try:
                                    if et == "book":
                                        v.on_book(m)
                                    elif et == "price_change":
                                        v.on_price_change(m)
                                    elif et == "last_trade_price":
                                        v.on_trade(str(m["asset_id"]), m["side"], float(m["price"]), float(m["size"]))
                                except Exception as e:
                                    # ERROR ISOLATION: one buggy strategy must never stop the live capture.
                                    # Count its errors; after 5, quarantine it (broken=True) so the rest of
                                    # the roster keeps recording. Quarantined variants are dropped at settle.
                                    v.errors = getattr(v, "errors", 0) + 1
                                    if v.errors <= 3 or v.errors == 5:
                                        L(f"  [VARIANT ERROR] {v.name} #{v.errors} on {et}: {type(e).__name__}: {e}")
                                    if v.errors >= 5:
                                        v.broken = True
                                        L(f"  [QUARANTINE] {v.name} disabled after {v.errors} errors; capture continues")
                            if et == "book":
                                taker.on_book(m)
                            elif et == "price_change":
                                taker.on_price_change(m)
                        # sample shared mid/micro/spot timeline (~1s/token) for per-fill markout
                        ts_now = time.time()
                        for tok in (mk["up"], mk["down"]):
                            bb, bsz, ba, asz = variants[0].tob[tok]
                            if bb is None or ba is None:
                                continue
                            tl = midtl.setdefault(tok, [])
                            if not tl or ts_now - tl[-1][0] >= 1.0:
                                mc = micro(bb, bsz, ba, asz)
                                tl.append((ts_now, (bb + ba) / 2, mc, shared.get("st")))
                                mh = shared["microhist"].setdefault(tok, [])  # book-lead signal for micro_react
                                if mc is not None:
                                    mh.append((ts_now, mc))
                                    if len(mh) > 40:
                                        del mh[:len(mh) - 40]
                                qe = shared["qema"].setdefault(tok, {"b": bsz, "a": asz})  # depletion EMA
                                qe["b"] = 0.95 * qe["b"] + 0.05 * bsz
                                qe["a"] = 0.95 * qe["a"] + 0.05 * asz
                        taker.step()             # offensive: take stale book quotes on fast BTC moves
            except Exception as e:  # noqa: BLE001
                L(f"  [ws reconnect] {str(e)[:70]}"); await asyncio.sleep(2)
        mk["_feed"] = (live.get("src") or "ws") if (live["n"] - ws_n0) > 50 else "rest"  # rtds/cb/rest source
        pending.append((mk, variants, midtl, taker))   # settle later, with retry (resolution lags close)
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
    ap.add_argument("--asset", default="btc", help="btc/eth/sol/xrp (cross-asset breadth; MAKEREDGE.md #5)")
    ap.add_argument("--tenor-min", type=int, default=15, help="market tenor in minutes (15 or 5)")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
