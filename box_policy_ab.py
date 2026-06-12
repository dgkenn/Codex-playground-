"""box_policy_ab.py -- PROSPECTIVE A/B of the pairing policy on FORWARD collector data.

The 20k-fill historical tape gave an ambiguous read on whether SELECTIVE HOLDING of a favorable
unpaired leg beats ALWAYS-PAIRING (two backtests disagreed; P2 looked good on Calmar but was a
2-sigma, 50%-win-rate directional bet). So we do not decide on the in-sample tape. Instead we let
the live SHADOW COLLECTOR accumulate brand-new windows and score the two policies on data collected
AFTER the policy was specified (the pre-registration date in P2_PROSPECTIVE.md). Once the
pre-registered significance bar is cleared, we decide. This script is that scorer.

Policies (applied to the SAME reconstructed maker fills per window; held to settlement; cap |net|<=1):
  P0 ALWAYS-PAIR   : the live default. Accept a fill iff it keeps |net|<=1 (so an unpaired leg is
                     completed by the opposite side as soon as it fills -> locks the box).
  P2 SIGNAL-HOLD   : like P0, but when a leg is unpaired and a PAIRING fill arrives, HOLD (skip the
                     pair, let the leg ride to settlement) iff that leg's decision-time spot signal
                     was favorable (sig_adv <= 0); otherwise pair. The candidate "tie-breaker".

Fills are reconstructed from the collector's own forward streams with the EXACT logic of
kalshi_sizing.collect_fills (queue q0=0 = front-of-queue, honest stale spot signal), so this is the
same measurement, just on prospective data.

    python box_policy_ab.py [--asset btc] [--dir overnight_data gha_data ...] [--report]

Appends one paired record per NEW window to box_policy_ledger_<asset>.jsonl (dedup by ws), then
prints the running paired t-test and the pre-registered verdict.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import time

import numpy as np

# Informed-flow detector features (causal, pre-k-minute trades). Import only the
# computation function; the heavy build/main logic is NOT imported to keep startup fast.
from informed_detectors import detectors as _det_fn

# Pre-registered decision rule (frozen in P2_PROSPECTIVE.md; do not tune to the data):
MIN_WINDOWS = 300       # need at least this many forward windows before a DEPLOY decision
T_BAR = 3.0             # DEPLOY bar: paired diff (trial-P0) t-stat must exceed this (positive)
DD_MULT = 1.25          # AND trial max-drawdown <= DD_MULT * P0 max-drawdown (risk-of-ruin guard)
# ALERT tier (the "two-sigma rule" -- be made aware so we can take action; NOT auto-deploy):
ALERT_T = 2.0           # |paired t| past 2-sigma raises an alert (either direction)
ALERT_N = 100           # ...once at least this many forward windows are scored (avoid tiny-n noise)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def iter_gz(fp):
    """Yield JSON records from a gzip JSONL file, tolerating a TRUNCATED tail (the live collector
    may be reaped mid-write, leaving an incomplete gzip stream / partial last line)."""
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return   # keep whatever we read before the truncation point


def _rglob(d, pat):
    """Recursive glob -- the gha-data branch date-partitions files into gha_data/YYYY-MM-DD/."""
    return glob.glob(os.path.join(d, "**", pat), recursive=True) + glob.glob(os.path.join(d, pat))


def _top5(levels):
    """Summed displayed size across the 5 levels nearest the touch (ascending best-at-end)."""
    try:
        return float(sum(q for _, q in levels[-5:]))
    except Exception:
        return 0.0


def load_window_books(paths, asset):
    """Returns (books, res, oi_slope).
      books[ws]   = list of (t, best_yes_bid, best_no_bid, spot, depth_min) -- depth_min = min of the
                    top-5 displayed size on each side (the bilateral-thinness completion signal).
      res[ws]     = 0/1 settlement.
      oi_slope[ws]= fractional open-interest change across the window (informed-positioning signal)."""
    books, res, oi = {}, {}, {}
    for d in paths:
        for fp in set(_rglob(d, f"book_kalshi_{asset}15m_*.jsonl.gz")):
            for r in iter_gz(fp):
                typ = r.get("type")
                if typ == "book":
                    yb = r.get("yes") or []; nb = r.get("no") or []
                    if not yb or not nb:
                        continue
                    books.setdefault(r["ws"], []).append(
                        (r["t"], float(yb[-1][0]), float(nb[-1][0]), _f(r.get("spot")),
                         min(_top5(yb), _top5(nb))))
                elif typ == "stat":
                    o = _f(r.get("open_interest"))
                    if o is not None:
                        oi.setdefault(r["ws"], []).append((r.get("t", 0.0), o))
        for fp in set(_rglob(d, f"shadow_windows_kalshi_{asset}15m_*.jsonl")):
            for ln in open(fp):
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ru = r.get("resolved_up")
                if ru in (0, 1):
                    res[r["ws"]] = int(ru)
    oi_slope = {}
    for ws, pts in oi.items():
        pts.sort()
        if len(pts) >= 2 and pts[0][1] > 0:
            oi_slope[ws] = (pts[-1][1] - pts[0][1]) / pts[0][1]
    return books, res, oi_slope


def load_trades(paths, asset):
    """ws -> sorted arrays (t, p_yes, sz, buy) from the taker tape."""
    tr = {}
    for d in paths:
        for fp in set(_rglob(d, f"trades_kalshi_{asset}15m_*.jsonl.gz")):
            for r in iter_gz(fp):
                if "p" not in r or "sz" not in r:
                    continue
                tr.setdefault(r["ws"], []).append(
                    (r.get("ts_exch") or r["t"], float(r["p"]), float(r["sz"]),
                     r.get("side") == "BUY"))
    out = {}
    for ws, rows in tr.items():
        rows.sort()
        out[ws] = (np.array([x[0] for x in rows], float), np.array([x[1] for x in rows], float),
                   np.array([x[2] for x in rows], float), np.array([x[3] for x in rows], bool))
    return out


def per_minute_touch(samples, ws):
    """Resample book samples to per-minute (k=0..14) last-before-boundary arrays."""
    bid = np.full(15, np.nan); ask = np.full(15, np.nan)
    spot = np.full(15, np.nan); depth = np.full(15, np.nan)
    samples = sorted(samples)
    for k in range(15):
        bound = ws + 60 * (k + 1)
        last = None
        for s in samples:
            if s[0] <= bound:
                last = s
            else:
                break
        if last is not None:
            bid[k] = last[1]; ask[k] = round(1.0 - last[2], 4)
            if last[3] is not None:
                spot[k] = last[3]
            if len(last) > 4 and last[4] is not None:
                depth[k] = last[4]
    return bid, ask, spot, depth


def _vpin_buckets(t_arr, sz_arr, buy_arr, n_buckets=20):
    """VPIN (Easley-Lopez de Prado-O'Hara): order-flow toxicity over EQUAL-VOLUME buckets. Returns
    (bucket_close_times, bucket_imbalances) where imbalance = |Vbuy-Vsell|/Vbucket in [0,1]."""
    if len(t_arr) < n_buckets:
        return np.array([]), np.array([])
    V = float(sz_arr.sum()) / n_buckets
    if V <= 0:
        return np.array([]), np.array([])
    bt, bi = [], []
    vb = vs = 0.0
    for i in range(len(t_arr)):
        if buy_arr[i]:
            vb += sz_arr[i]
        else:
            vs += sz_arr[i]
        if vb + vs >= V:
            bt.append(t_arr[i]); bi.append(abs(vb - vs) / (vb + vs)); vb = vs = 0.0
    return np.array(bt), np.array(bi)


def _vpin_at(bt, bi, tt, smooth=5):
    """Mean toxicity of the last `smooth` buckets closed strictly before time tt (the fill clock)."""
    if len(bt) == 0:
        return np.nan
    j = int(np.searchsorted(bt, tt))
    if j < 1:
        return np.nan
    return float(np.mean(bi[max(0, j - smooth):j]))


def window_fills(ws, res, bid, ask, spot, depth, tape, oi_slope=None, q0=0.0):
    """Reconstruct maker fills (collect_fills logic) with the FULL decision-time feature set each
    trial strategy needs. Returns time-ordered list of dicts:
      side('bid'=YES|'ask'=NO), settle($/contract to settlement), sig(spot bps, +=adverse to side),
      p(YES-equiv price), spread, k(minute 2..12), tau(frac left), flow(prior-min taker imbalance),
      depth(min top-5 displayed size), oi(window OI slope), vpin(flow toxicity at fill),
      spot(BTC at fill), sset(BTC at settlement -- for the perp-hedge trial),
      det_*(causal informed-flow detector features for t35_combo_tox_gate)."""
    spot_l = np.concatenate([[np.nan], spot[:-1]])
    t_arr, p_arr, sz_arr, buy_arr = tape
    sset = float(spot[~np.isnan(spot)][-1]) if np.any(~np.isnan(spot)) else np.nan
    bt, bi = _vpin_buckets(t_arr, sz_arr, buy_arr)
    recs = []
    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
        mv = (s_now / s_then - 1) * 1e4 if (s_now and s_then and s_now > 0 and s_then > 0) else 0.0
        spread = round(a0 - b0, 4); tau = (15 - k) / 15.0
        dk = float(depth[k]) if not np.isnan(depth[k]) else None
        # SELL-BACK exit value (~1 min later, crossing to the touch; CRYPTO15M fee=0). Lets a trial
        # value an unpaired leg by flattening it instead of holding to settlement.
        b1 = bid[k + 1] if k + 1 < 15 else b0
        a1 = ask[k + 1] if k + 1 < 15 else a0
        if np.isnan(b1) or np.isnan(a1):
            b1, a1 = b0, a0
        mid1 = (b1 + a1) / 2.0; sp1 = a1 - b1
        exit_bid = (mid1 - sp1 / 2.0) - b0        # sell YES at the bid
        exit_ask = a0 - (mid1 + sp1 / 2.0)        # buy YES back at the ask (flatten the NO leg)
        pl, ph = ws + 60 * (k - 1), ws + 60 * k          # prior-minute taker flow imbalance
        j0, j1 = np.searchsorted(t_arr, pl), np.searchsorted(t_arr, ph)
        flow = float(np.sum(np.where(buy_arr[j0:j1], sz_arr[j0:j1], -sz_arr[j0:j1])))
        # --- Causal informed-flow detector features (t < decision minute k) for t35 gate ---
        # Mask to trades strictly before end of minute k (same causal horizon as VPIN at fill).
        _dm = t_arr < (ws + 60 * k)
        _dv = _det_fn(ws, t_arr[_dm], p_arr[_dm], sz_arr[_dm], buy_arr[_dm])
        _det_extra = {
            "det_take_n":     _dv["take_n"],
            "det_d1_maxrun":  _dv["d1_maxrun"],
            "det_d2_lambda":  _dv["d2_lambda"] if not np.isnan(_dv["d2_lambda"]) else None,
            "det_d1_nruns":   _dv["d1_nruns"]  if not np.isnan(_dv["d1_nruns"])  else None,
            "det_d4_roundfrac": _dv["d4_roundfrac"] if not np.isnan(_dv["d4_roundfrac"]) else None,
            "det_d5_sweep":   _dv["d5_sweep"]  if not np.isnan(_dv["d5_sweep"])  else None,
        }
        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        qb = qa = q0; done_b = done_a = False
        for i in range(i0, i1):
            if done_b and done_a:
                break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            if not done_b and not buy and p <= b0 + 1e-9:
                if qb >= sz:
                    qb -= sz
                else:
                    recs.append({"ws": ws, "side": "bid", "settle": res - b0, "exit": exit_bid, "sig": mv,
                                 "p": b0, "spread": spread, "k": k, "tau": tau, "flow": flow,
                                 "tksize": float(sz),
                                 "depth": dk, "oi": oi_slope, "vpin": _vpin_at(bt, bi, t_arr[i]),
                                 "spot": float(spot[k]) if not np.isnan(spot[k]) else None,
                                 "sset": sset, **_det_extra}); done_b = True
            if not done_a and buy and p >= a0 - 1e-9:
                if qa >= sz:
                    qa -= sz
                else:
                    recs.append({"ws": ws, "side": "ask", "settle": a0 - res, "exit": exit_ask, "sig": -mv,
                                 "p": round(1.0 - a0, 4), "spread": spread, "k": k, "tau": tau,
                                 "flow": -flow, "depth": dk, "oi": oi_slope, "tksize": float(sz),
                                 "vpin": _vpin_at(bt, bi, t_arr[i]),
                                 "spot": float(spot[k]) if not np.isnan(spot[k]) else None,
                                 "sset": sset, **_det_extra}); done_a = True
    return recs


def run_policy(fills, open_ok=None, hold_ok=None, weight=None):
    """Walk a window's fills (cap |net|<=1, hold to settlement). open_ok(f, state)->may we OPEN a
    new leg with this fill? hold_ok(held_leg)->when a fill would PAIR the open leg, hold instead?
    weight(f)->per-fill size multiplier (e.g., gamma size-down near expiry). Returns summed settle.
    Baseline P0 passes none (accept everything, always pair, unit size)."""
    net = 0; pnl = 0.0; held = None; st = {"yes": 0, "no": 0}
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if pairing:
            if hold_ok is not None and held is not None:
                try:
                    keep = hold_ok(held, f)        # 2-arg form: pairing fill reveals CURRENT price
                except TypeError:
                    keep = hold_ok(held)           # legacy 1-arg holds
                if keep:
                    continue                                   # hold the favorable unpaired leg
        elif open_ok is not None and not open_ok(f, st):
            continue                                           # gate: don't open this leg
        if net == 0 and nn != 0:
            held = f
        net = nn; pnl += (weight(f) if weight else 1.0) * f["settle"]
        st["yes" if f["side"] == "bid" else "no"] += 1
    return pnl


def completion_score(f):
    """0..4 -- how likely BOTH legs pair, from the forward-validated completion signals: thin book,
    balanced taker flow, flat/falling OI, tight (1c) spread. Higher = more likely to complete."""
    s = 0
    if f.get("depth") is not None:
        s += int(f["depth"] < 5500)        # bilateral thinness (rich stream: thin->~75% complete)
    if f.get("flow") is not None:
        s += int(abs(f["flow"]) < 250)     # balanced prior-minute flow
    if f.get("oi") is not None:
        s += int(f["oi"] < 0.5)            # OI not spiking (informed one-sided positioning)
    s += int(f.get("spread", 1) <= 0.011)  # 1c book completes fast
    return s


# Frozen logistic FILL-TOXICITY score (P(settle<0)), fit on the 20,318-fill BTC tape (q0=0,
# 60/40 time-split OOS AUC 0.671; the GBM reaches 0.765 but isn't embeddable as a lambda -- this is
# the distilled, deployable version; see COMPLETION_MODEL.md "fill-toxicity model"). Coefficients
# are RAW-feature space over collect_fills units (flow_adv in 1000s of contracts, p = YES-equiv).
# Note sig_adv fits NEGATIVE: adverse pre-fill spot mean-reverts (same mechanism as "stops lose").
# Refit when the tape grows materially.
_TOX_B0 = -0.158221
_TOX_W = {"side_bin": 0.171259, "p": -0.011119, "abs_p05": 0.337983, "tau": -0.006424,
          "sig_adv": -0.045708, "flow_adv": -0.015046, "flow_x_tau": 0.080583,
          "sig_x_side": -0.000210, "spread": 3.290252}


# ---------------------------------------------------------------------------
# Frozen combined-detector open gate (t35_combo_tox_gate). Fit on ALL 3383
# historical windows (4 assets, informed_detectors.py --freeze equivalent).
# Features: vpin, take_n, d1_maxrun, d2_lambda, d1_nruns, d4_roundfrac, d5_sweep.
# THRESH chosen to match t32's OOS keep fraction (~44.7%). OOS AUC 0.700 vs
# VPIN-alone 0.619; stranded rate 0.214 vs VPIN-only 0.268 at equal volume kept.
_COMBO_INTERCEPT = -1.097821
_COMBO_FEATS = ["vpin", "take_n", "d1_maxrun", "d2_lambda", "d1_nruns", "d4_roundfrac", "d5_sweep"]
_COMBO_MEANS = {"vpin": 0.420709, "take_n": 1195.595024, "d1_maxrun": 25.951139,
                "d2_lambda": 0.083574, "d1_nruns": 0.289674, "d4_roundfrac": 0.158329,
                "d5_sweep": 7.621103}
_COMBO_STDS =  {"vpin": 0.188093, "take_n": 1572.059825, "d1_maxrun": 18.508967,
                "d2_lambda": 0.181745, "d1_nruns": 0.064831, "d4_roundfrac": 0.089765,
                "d5_sweep": 4.795740}
_COMBO_COEFS = {"vpin": 0.139545, "take_n": -0.926797, "d1_maxrun": -0.052450,
                "d2_lambda": 0.177854, "d1_nruns": 0.046305, "d4_roundfrac": -0.006626,
                "d5_sweep": -0.024818}
_COMBO_THRESH = 0.3656   # 44.7% volume kept (= t32's keep fraction on OOS)


def tox_p(f):
    """P(this fill settles at a loss) from decision-time features. window_fills stores the leg's
    OWN price ('p'=1-a0 for asks) and flow in contracts (=1000x the fit's flow_adv) -- convert."""
    p_yeq = f["p"] if f["side"] == "bid" else round(1.0 - f["p"], 4)
    side_bin = 1.0 if f["side"] == "bid" else 0.0
    flow_adv = (f["flow"] or 0.0) / 1000.0
    sig = f.get("sig") or 0.0
    z = (_TOX_B0 + _TOX_W["side_bin"] * side_bin + _TOX_W["p"] * p_yeq
         + _TOX_W["abs_p05"] * abs(p_yeq - 0.5) + _TOX_W["tau"] * f["tau"]
         + _TOX_W["sig_adv"] * sig + _TOX_W["flow_adv"] * flow_adv
         + _TOX_W["flow_x_tau"] * flow_adv * f["tau"] + _TOX_W["sig_x_side"] * sig * side_bin
         + _TOX_W["spread"] * f["spread"])
    return 1.0 / (1.0 + np.exp(-z))


def combo_tox_p(f):
    """P(this fill leads to a stranded leg) from the VPIN+detectors combined logistic.
    Returns None if any required feature is missing (gate no-ops on None, matching t32 behavior).
    Features must be pre-computed by window_fills into the fill dict (det_* keys + vpin)."""
    vals = {}
    vals["vpin"] = f.get("vpin")
    vals["take_n"] = f.get("det_take_n")
    vals["d1_maxrun"] = f.get("det_d1_maxrun")
    vals["d2_lambda"] = f.get("det_d2_lambda")
    vals["d1_nruns"] = f.get("det_d1_nruns")
    vals["d4_roundfrac"] = f.get("det_d4_roundfrac")
    vals["d5_sweep"] = f.get("det_d5_sweep")
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in vals.values()):
        return None
    z = _COMBO_INTERCEPT
    for feat in _COMBO_FEATS:
        z += _COMBO_COEFS[feat] * (vals[feat] - _COMBO_MEANS[feat]) / _COMBO_STDS[feat]
    return 1.0 / (1.0 + np.exp(-z))


# Measured pair-rate table (sizing analysis 2026-06-12, 20,318 fills, q0=0): P(this leg pairs)
# by minute-bucket x |p-0.5| band. Drives the Kelly-style sizing trials.
def pair_prob(f):
    k = f.get("k", 8); d = abs((f["p"] if f["side"] == "bid" else 1.0 - f["p"]) - 0.5)
    if k <= 4:
        return 0.995 if d > 0.15 else 1.0
    if k <= 7:
        return 0.979 if d > 0.15 else 1.0
    if k <= 10:
        return 0.906 if d > 0.15 else 0.997
    return 0.655 if d > 0.15 else (0.804 if d > 0.05 else 0.772)


def pol_sized(fills, size_of):
    """Box-pairing walk where the COMPLETING leg inherits the OPEN leg's size (a sized box must be
    a matched box -- the per-fill weight() shortcut in run_policy mismatches the pair). size_of(f)
    -> integer-ish multiplier for an OPENING fill. Cap |net|<=1 LEG as ever."""
    net = 0; pnl = 0.0; open_leg = None; open_w = 1.0
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if open_leg is not None and abs(nn) < abs(net):      # completing fill: match the open size
            pnl += open_w * (f["settle"] + open_leg["settle"])
            open_leg = None
        else:
            open_leg = f; open_w = float(size_of(f))         # opening fill: size it
        net = nn
    if open_leg is not None:
        pnl += open_w * open_leg["settle"]                   # leftover unpaired leg, sized
    return pnl


def hedge_unpaired(f, h=100.0):
    """Perp-hedge value of an unpaired leg: settle + a delta-neutral BTC hedge (short for a YES leg,
    long for NO). h ~= cents of hedge per 1% BTC move (delta-neutral on the tape). Tape: -3.3c/leg
    (hold) -> ~-0.05c (hedged) -- removes the directional loss. Falls back to hold if no spot."""
    s0, ss = f.get("spot"), f.get("sset")
    if not s0 or not ss or s0 <= 0:
        return f["settle"]
    r = (ss / s0 - 1.0) * 100.0                       # BTC % move over the hold
    sgn = -1.0 if f["side"] == "bid" else 1.0          # YES leg -> short BTC; NO leg -> long BTC
    return f["settle"] + sgn * h * r / 100.0


def pol_hedge_unpaired(fills):
    """Always-pair, but a leftover unpaired leg is delta-hedged with BTC instead of held naked."""
    net = 0; pnl = 0.0; open_leg = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if open_leg is not None and abs(nn) < abs(net):
            pnl += f["settle"] + open_leg["settle"]; open_leg = None
        else:
            open_leg = f
        net = nn
    if open_leg is not None:
        pnl += hedge_unpaired(open_leg)
    return pnl


def pol_p0(fills):
    return run_policy(fills)


def pol_sell_unpaired(fills, cheap_below=None, toxic_above=None, vpin_above=None, tox_above=None,
                      open_ok=None):
    """Always-pair, BUT a leg still unpaired at window end is SOLD BACK (exit value) instead of held.
    Tape finding (the price-bucket split is the key): selling helps strongly for CHEAP long-shot legs
    (price<0.30: hold -4.0c vs sell -1.7c, +2.3c, t=3.5) but HURTS for expensive legs (price>0.70:
    hold +5.0c vs sell -0.8c, -5.8c, t=-2.8) because on a binary, price=probability, so an expensive
    leg is the FAVORED side that tends to win -- hold it. cheap_below sets the sell ceiling.
    toxic_above sells only when the fill's signal was adverse (sig > toxic_above bps) -- the
    literature's VPIN-conditioned exit (a stop is +EV only on the informed subset). None on both =
    sell any unpaired leg. Under prospective test, not deployed."""
    net = 0; pnl = 0.0; open_leg = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if open_leg is not None and abs(nn) < abs(net):      # this fill pairs the open leg -> box
            pnl += f["settle"] + open_leg["settle"]
            open_leg = None
        else:
            if open_ok is not None and not open_ok(f):       # gate OPENING only (pairing always ok)
                continue
            open_leg = f                                     # opened a new leg
        net = nn
    if open_leg is not None:                                 # leftover unpaired leg at window end
        sell = True
        if cheap_below is not None:
            sell = open_leg.get("p", 1.0) < cheap_below
        if toxic_above is not None:
            sell = open_leg.get("sig", 0.0) > toxic_above     # sell only spot-adverse fills
        if vpin_above is not None:
            v = open_leg.get("vpin")                          # sell only INFORMED (high-VPIN) fills
            sell = (v is not None) and (v > vpin_above)        # the literature-correct stop
        if tox_above is not None:
            sell = tox_p(open_leg) > tox_above                # fitted-toxicity stop (the ML exit)
        pnl += open_leg.get("exit", open_leg["settle"]) if sell else open_leg["settle"]
    return pnl


# ------------------------------------------------------------------------------------------------
# TRIAL-STRATEGY REGISTRY. Live default is P0 (always-pair, ungated reference). Every entry is a
# CANDIDATE scored vs P0 on FORWARD collector data, held to the 2-sigma alert + pre-registered
# deploy bar. Each is grounded in a documented finding (see TRIALS.md). Add name->fn(fills)->pnl
# to prospectively test a new idea; it auto-inherits accumulation, the alert, and the deploy gate.
TRIALS = {
    # ---- toxicity / price gates (skip opening adverse legs) ----
    "t01_deep_tail_skip":  lambda F: run_policy(F, open_ok=lambda f, s: 0.15 <= f["p"] <= 0.85),
    "t02_yes_caution":     lambda F: run_policy(F, open_ok=lambda f, s: not (f["side"] == "bid" and f["spread"] < 0.02)),
    "t03_early_window":    lambda F: run_policy(F, open_ok=lambda f, s: f["k"] <= 8),
    "t07_spot_gate":       lambda F: run_policy(F, open_ok=lambda f, s: f["sig"] <= 8.0),
    # ---- completion-aware opening (target legs that will PAIR; exclude likely orphans) ----
    "t04_thin_book":       lambda F: run_policy(F, open_ok=lambda f, s: f["depth"] is None or f["depth"] < 5500),
    "t05_flat_oi":         lambda F: run_policy(F, open_ok=lambda f, s: f["oi"] is None or f["oi"] < 0.5),
    "t06_balanced_flow":   lambda F: run_policy(F, open_ok=lambda f, s: f["flow"] is None or abs(f["flow"]) < 250),
    "t09_completion_target": lambda F: run_policy(F, open_ok=lambda f, s: completion_score(f) >= 2),
    # ---- selective holding of favorable unpaired legs ----
    "t08_hold_no":         lambda F: run_policy(F, hold_ok=lambda h: h["side"] == "ask"),
    "t10_target_and_hold": lambda F: run_policy(F, open_ok=lambda f, s: completion_score(f) >= 2,
                                                hold_ok=lambda h: h["sig"] <= 0),
    # ---- the original tie-breaker (kept) ----
    "p2_signal_hold":      lambda F: run_policy(F, hold_ok=lambda h: h["sig"] <= 0),
    # ---- sell off losing unpaired legs (operator's idea; cheap-only is the validated cut) ----
    "t11_sell_cheap_unpaired": lambda F: pol_sell_unpaired(F, cheap_below=0.30),
    "t12_sell_all_unpaired":   lambda F: pol_sell_unpaired(F, cheap_below=None),
    # ---- toxicity-conditioned exit (literature: stops are +EV only for the INFORMED subset) ----
    "t13_sell_unpaired_vpin":  lambda F: pol_sell_unpaired(F, vpin_above=0.40),
    # ---- literature backtest winners (added after the 5-angle review) ----
    "t14_perp_hedge_unpaired": lambda F: pol_hedge_unpaired(F),                         # #1: hedge the leg
    "t15_gamma_size_down":     lambda F: run_policy(F, weight=lambda f: (15 - f["k"]) / 13.0),
    "t16_no_leg_preference":   lambda F: run_policy(F, open_ok=lambda f, s: f["side"] == "ask"),
    # ---- fitted fill-toxicity score (the ONE ML framing with CI-excluding-zero economic lift;
    #      GBM +2.1c/fill settle / +2.9c markout vs hold-all -- see COMPLETION_MODEL.md). Frozen
    #      logistic distillation; thresholds pre-registered from the fit's quantile sweep:
    #      tox>0.55 sells the worst ~39% (mean -0.6c) keeping +0.5c fills; gate<0.65 skips ~10%.
    "t17_tox_exit_unpaired":   lambda F: pol_sell_unpaired(F, tox_above=0.55),
    "t18_tox_open_gate":       lambda F: run_policy(F, open_ok=lambda f, s: tox_p(f) < 0.65),
    "t19_tox_gate_and_exit":   lambda F: pol_sell_unpaired(F, tox_above=0.55,
                                                           open_ok=lambda f: tox_p(f) < 0.65),
    # ---- fill-probability literature round (queue/fill-certainty papers; see LITERATURE.md) ----
    # Foucault 1999 (J. Fin. Markets): equilibrium fill probability falls and pick-off risk rises
    # with volatility -- makers should stand down in high-vol regimes. |sig| = 3-min spot move in
    # bps is our decision-time vol proxy (two-sided, unlike t07's one-sided adverse gate).
    "t20_low_vol_open":        lambda F: run_policy(F, open_ok=lambda f, s: abs(f["sig"]) <= 5.0),
    # Cont-Kukanov / Abergel 2024: fill is near-certain when queue-ahead is smaller than the
    # incoming taker flow that can sweep it. depth = displayed size at our level, |flow| = prior
    # minute's taker volume: quote only where the queue is genuinely sweepable.
    "t21_sweepable_queue":     lambda F: run_policy(F, open_ok=lambda f, s: f["depth"] is None
                                                    or (f["flow"] is not None
                                                        and f["depth"] < abs(f["flow"]))),
    # ---- BET-SIZING trials (operator ask 2026-06-12): forward-test sizing SHAPES so a validated
    #      one can scale with bankroll (multiplier x base size). pol_sized matches the completing
    #      leg to the open leg's size (a sized box must be a matched box -- run_policy's per-fill
    #      weight() mismatches the pair). Thresholds pre-registered, never tuned on forward data.
    #      t23 is the bankroll-scalable one: quarter-Kelly in P(pair) from the measured pair-rate
    #      table (SIZING.md: f* ~ P/(1-P)); the 3x cap IS the fractional-Kelly discipline.
    "t22_size_sweetspot":  lambda F: pol_sized(F, lambda f: 1.5 if (f["k"] <= 4 and
                                       abs((f["p"] if f["side"] == "bid" else 1 - f["p"]) - 0.5)
                                       <= 0.10) else 1.0),
    "t23_quarter_kelly":   lambda F: pol_sized(F, lambda f: min(3.0, max(1.0,
                                       0.01 * min(pair_prob(f), 0.995)
                                       / (1.0 - min(pair_prob(f), 0.995))))),
    "t24_tox_sized":       lambda F: pol_sized(F, lambda f: 1.5 if tox_p(f) < 0.45
                                       else (0.5 if tox_p(f) > 0.60 else 1.0)),
    # ---- sizing sweep round 2 (8-family tape backtest, 2026-06-12): flat won; only two shapes
    #      earned a forward trial. REJECTED (lose mean + add tail OOS, do not re-add): vol-inverse,
    #      qkelly x tox combo. t25 = the lone positive-delta shape (hour-of-day depth/flow table;
    #      +0.16c/win OOS, needs forward confirmation it isn't noise). t26 = gamma-taper as pure
    #      DRAWDOWN control via the matched-pair walker (-36% maxDD, -39% std, costs 0.34c/win mean;
    #      t15 tests the same shape with the legacy mismatched-pair weight()).
    "t25_hour_sized":      lambda F: pol_sized(F, lambda f: 1.5 if time.gmtime(
                                       f.get("ws", 0)).tm_hour in (13, 14, 15, 18, 19, 20)
                                       else (0.5 if time.gmtime(f.get("ws", 0)).tm_hour in (11, 21)
                                             else 1.0)),
    "t26_gamma_sized":     lambda F: pol_sized(F, lambda f: max(0.25, (15 - f["k"]) / 13.0)),
    # ---- operator question 2026-06-12: "hold the first leg naked instead of pairing, when it has
    #      traveled favorably?" Economics: pairing at CURRENT prices locks ~the leg's EV with zero
    #      variance (the cap rises with the move), so naked holds only win where the market is
    #      mispriced -- the documented favorite-longshot bias (favorites settle above their price;
    #      live calibration: 60-80c won 86%, 80-100c won 100%). Surgical version: when the pairing
    #      fill arrives, its price reveals the held leg's CURRENT implied value (1 - opposite's own
    #      price); hold naked iff the held leg is now a DEEP favorite (>= 0.75). Everything looser
    #      than this already failed OOS (t08 hold-all-NO, p2 signal-hold, the directional ensemble).
    "t28_hold_deep_favorite": lambda F: run_policy(F, hold_ok=lambda h, f: (1.0 - f["p"]) >= 0.75),
    # ---- asymmetry sweep survivors (2026-06-12 tape backtest, IS+OOS at q0=0 AND q0=500) ----
    # t29 = the headline: ONLY OPEN FAVORITE-SIDE LEGS (leg's own cost >= 0.45). Survived both
    # queue regimes (OOS +2.70c/win t=8.2 at q0=0; +9.73 t=15.2 at q0=500; maxDD ~60% of P0).
    # It is the adaptive-side generalization of t16 (NO-only, the live A/B leader) and the tight
    # version of t01 (which kept the toxic 20-45c mid-longshots and failed). Leg cost: bid -> p,
    # ask -> 1-p.
    "t29_favorite_only_opens": lambda F: run_policy(F, open_ok=lambda f, s: (
                                   f["p"] if f["side"] == "bid" else 1.0 - f["p"]) >= 0.45),
    # t30 = the asymmetric playbook: favorite-only opens (>=0.40) + hold legs that became deep
    # favorites (implied >=0.75). The sweep's C6 minus its sell-at-end component (which was
    # NEGATIVE standalone -- selling on end-of-window implied is a stop-loss in disguise, and
    # stops lose). Survived q0=500 (+9.4c/win t=10.1), neutral at q0=0.
    "t30_asym_playbook":   lambda F: run_policy(F,
                                   open_ok=lambda f, s: (f["p"] if f["side"] == "bid"
                                                         else 1.0 - f["p"]) >= 0.40,
                                   hold_ok=lambda h, f: (1.0 - f["p"]) >= 0.75),
    # ---- legitimate COUNTERPARTY modeling (operator 2026-06-12): tape diagnostic (2.1M trades)
    #      found the maker's settle-edge is +1.09c/ct vs CONTRARIAN takers (fading the move) but
    #      -0.48c/ct vs MOMENTUM-CHASERS (t=19.5 IS). So contrarians are the naive, exploitable
    #      counterparty; to FACE them we open the side recent flow already supports (flow-aligned),
    #      not the side being hit. f["flow"] is the prior-minute signed taker imbalance ALREADY
    #      oriented to the leg (ask flow negated), so flow>=0 = flow supports this leg. HONEST
    #      CAVEAT: this is the same momentum-continuation our directional-ensemble showed does NOT
    #      survive as incremental OOS edge beyond the binary's own mid -- prospective test decides;
    #      distinct from t06 (flow MAGNITUDE gate) and p2/t07 (spot-signal, not flow).
    "t31_face_contrarian": lambda F: run_policy(F, open_ok=lambda f, s:
                                   f["flow"] is None or f["flow"] >= 0),
    # ---- fingerprint deep-dive survivor (2026-06-12, 2779-window trade-tape): high decision-time
    #      VPIN predicts a STRANDED leg 9.7x more often (6.8% vs 0.7%) and pair-rate OOS r=-0.346.
    #      We had the VPIN EXIT (t13, sell unpaired when vpin>0.40) but NOT the VPIN OPENING gate.
    #      t32 = don't OPEN a leg whose fill-time VPIN is toxic (>0.40, same informed-subset
    #      threshold) -- prevention, the lever the fingerprint work validated. Distinct from t18
    #      (tox_p logistic, flow-based) and t06 (flow magnitude).
    "t32_vpin_open_gate":  lambda F: run_policy(F, open_ok=lambda f, s:
                                   f.get("vpin") is None or f["vpin"] <= 0.40),
    # ---- counterparty-avoidance deep dive (2026-06-12, 20k-fill markout-targeted): the optimal
    #      gate is t31 (face-contrarian, VALIDATED OOS +0.233c/fill contrarian vs -0.182c momentum =
    #      +0.41c spread, the best of any gate). The new take-size feature does NOT improve the fitted
    #      model (dAUC~0) but a TAIL-TRIM of the >100-contract (informed) takes is a clean monotone
    #      add-on (+0.05-0.10c/fill, keeps ~92% volume). tksize = the crossing take's size (contracts).
    #      The fitted combined LOGIT gate was overfit (settle-noise) -- NOT registered.
    "t33_take_tail_trim":  lambda F: run_policy(F, open_ok=lambda f, s:
                                   f.get("tksize") is None or f["tksize"] <= 100),
    # t34 = the optimal combined policy the dive found: face-contrarian + take-tail-trim
    "t34_avoid_combined":  lambda F: run_policy(F, open_ok=lambda f, s:
                                   (f["flow"] is None or f["flow"] >= 0)
                                   and (f.get("tksize") is None or f["tksize"] <= 100)),
    # ---- combined informed-flow detector gate (2026-06-12, informed_detectors.py finding):
    #      VPIN+detectors logistic OOS AUC 0.700 vs VPIN-alone 0.619; strand rate 0.214 vs 0.268 at
    #      equal ~44.7% volume kept (matching t32's keep fraction for apples-to-apples comparison).
    #      Frozen logistic fit on ALL 3383 historical windows (4 assets); features: vpin, take_n,
    #      d1_maxrun, d2_lambda, d1_nruns, d4_roundfrac, d5_sweep. THRESH=0.3656 keeps same volume
    #      as t32. Gate no-ops (None) when causal trade count is too low to compute detectors.
    "t35_combo_tox_gate":  lambda F: run_policy(F, open_ok=lambda f, s:
                                   combo_tox_p(f) is None or combo_tox_p(f) <= _COMBO_THRESH),
}


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def maxdd(series):
    cum = np.cumsum(series)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0


def calmar(series):
    """Total return / max drawdown on a per-window PnL series (risk-adjusted; higher = better)."""
    if len(series) == 0:
        return float("nan")
    tot = float(np.sum(series)); dd = maxdd(series)
    return (tot / dd) if dd > 1e-9 else (float("inf") if tot > 0 else 0.0)


# --- competitive benchmark metrics (operator's box-trader benchmark sheet, 2026-06) -------------
# Window-level adaptations: our unit of record is the WINDOW (one 15-min market), not the box.
# Box-level "win rate ~100%" is definitionally true for PAIRED boxes (risk-free) -- the honest
# window-level analogue is profitable-window rate + how unpaired legs drag the tail metrics.

def profit_factor(x):
    """Gross profits / gross losses. Benchmarks: >1.5 min, >2 strong, >3 arbitrage-gold."""
    g = float(np.sum(x[x > 0])); l = float(-np.sum(x[x < 0]))
    return (g / l) if l > 1e-12 else (float("inf") if g > 0 else float("nan"))


def sortino(x):
    """Mean / downside-deviation (per-window, not annualized). Benchmarks: >2.5 min, >3.5 strong."""
    if len(x) < 8:
        return float("nan")
    dn = x[x < 0]
    dd = float(np.sqrt(np.mean(dn ** 2))) if len(dn) else 0.0
    return (float(np.mean(x)) / dd) if dd > 1e-12 else (float("inf") if np.mean(x) > 0 else 0.0)


def recovery_factor(x):
    """Total net / max drawdown. Benchmarks: >5 min, >8 strong, >10 gold."""
    dd = maxdd(x)
    tot = float(np.sum(x))
    return (tot / dd) if dd > 1e-9 else (float("inf") if tot > 0 else float("nan"))


def bench_line(x, fills_per_win=None):
    """One compact competitive-scorecard line for a per-window PnL array, with tier flags.
    Expectancy benchmark (>+1.5c min / +2.5c strong / +3.5c gold) is PER WINDOW here."""
    if float(np.sum(np.abs(x))) * 100 < 20:        # near-zero turnover: inf PF/Sortino mislead
        return "inactive (total |PnL| < 20c -- benchmark tiers n/a; the gate barely trades)"
    pf = profit_factor(x); so = sortino(x); rf = recovery_factor(x)
    exp_c = float(np.mean(x)) * 100
    winr = float(np.mean(x > 0)) * 100

    def tier(v, lo, mid, hi):
        if np.isnan(v):
            return "?"
        return "G" if v >= hi else ("S" if v >= mid else ("m" if v >= lo else "✗"))

    flags = (f"PF:{tier(pf,1.5,2,3)} Sor:{tier(so,2.5,3.5,4)} "
             f"Rec:{tier(rf,5,8,10)} Exp:{tier(exp_c,1.5,2.5,3.5)}")
    return (f"PF {pf:4.2f}  Sortino {so:+5.2f}  Recov {rf:+5.1f}  Exp {exp_c:+5.2f}c/win  "
            f"prof-win {winr:3.0f}%  [{flags}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--dir", nargs="+", default=["overnight_data", "gha_data"])
    ap.add_argument("--report", action="store_true", help="just report from the ledger(s), scan nothing")
    ap.add_argument("--ledger", default=None,
                    help="ledger to APPEND new windows to (default box_policy_ledger_<asset>.jsonl). "
                         "On GHA use a run-scoped path under gha_data/ so each run commits a fragment.")
    ap.add_argument("--alert", action="store_true",
                    help="on a 2-sigma crossing, emit a GitHub warning, append STRATEGY_ALERTS.txt, "
                         "and push a notify.alert (Telegram). Use in the periodic report job.")
    a = ap.parse_args()
    ledger = a.ledger or f"box_policy_ledger_{a.asset}.jsonl"

    # Aggregate ALL ledger fragments (cwd + each --dir) so run-scoped GHA fragments combine; dedup by ws.
    seen = {}
    frag_paths = [ledger] + [p for d in a.dir if os.path.isdir(d)   # recursive: gha-data dates the dirs
                             for p in glob.glob(os.path.join(d, "**", f"box_policy_ledger_{a.asset}*.jsonl"),
                                                recursive=True)]
    for fpath in dict.fromkeys(frag_paths):
        if os.path.exists(fpath):
            for ln in open(fpath):
                try:
                    r = json.loads(ln); seen[r["ws"]] = r
                except Exception:
                    pass

    added = 0
    if not a.report:
        books, res, oi_slope = load_window_books([d for d in a.dir if os.path.isdir(d)], a.asset)
        trades = load_trades([d for d in a.dir if os.path.isdir(d)], a.asset)
        with open(ledger, "a") as out:
            for ws in sorted(books):
                if ws in seen or ws not in res or ws not in trades:
                    continue
                bid, ask, spot, depth = per_minute_touch(books[ws], ws)
                fills = window_fills(ws, res[ws], bid, ask, spot, depth, trades[ws], oi_slope.get(ws))
                if not fills:
                    continue
                rec = {"ws": ws, "res": res[ws], "n_fills": len(fills),
                       "p0": round(pol_p0(fills), 6),
                       "trials": {name: round(fn(fills), 6) for name, fn in TRIALS.items()}}
                out.write(json.dumps(rec) + "\n"); seen[ws] = rec; added += 1

    rows = sorted(seen.values(), key=lambda r: r["ws"])
    n = len(rows)
    print(f"TRIAL-STRATEGY PROSPECTIVE A/B ({a.asset}) -- {n} forward windows (+{added} new this run)")
    if n == 0:
        print("  no scored windows yet; let the collector accumulate."); return
    wins = np.array([r["ws"] for r in rows]); cut = wins[int(n * 0.6)] if n >= 10 else wins[-1] + 1
    oosm = wins >= cut
    p0 = np.array([r["p0"] for r in rows]); dd0 = maxdd(p0)
    print(f"  {'P0 always-pair (baseline)':<24} net/win {p0.mean()*100:+6.2f}c  "
          f"OOSnet {p0[oosm].mean()*100 if oosm.any() else float('nan'):+6.2f}c  "
          f"Calmar {calmar(p0[oosm]) if oosm.any() else float('nan'):+5.1f}  maxDD {dd0*100:4.0f}c  "
          f"win {(p0>0).mean()*100:3.0f}%  n={n}")
    print(f"  {'':<24} bench   {bench_line(p0)}")
    print(f"  {'(metrics: net/win, OOS net, OOS Calmar, maxDD, win%, per-fill, paired t vs P0;':<24}")
    print(f"  {' bench tiers per operator sheet: m=minimum S=strong G=gold ✗=below; window-level)':<24}")

    names = set()
    for r in rows:
        names.update((r.get("trials") or {}).keys())
        if "p2" in r:
            names.add("p2_signal_hold")
    alerts = []
    for name in sorted(names):
        pt = np.array([(r.get("trials") or {}).get(name,
                        r.get("p2") if name == "p2_signal_hold" else np.nan) for r in rows], float)
        m = ~np.isnan(pt)
        if m.sum() < 8:
            continue
        diff = pt[m] - p0[m]
        t = tstat(diff); ddt = maxdd(pt[m]); nn = int(m.sum())
        om = oosm & m
        oosnet = pt[om].mean() * 100 if om.any() else float("nan")
        cal = calmar(pt[om]) if om.any() else float("nan")
        nf = np.array([r["n_fills"] for r in rows])[m]
        perfill = pt[m].sum() / max(nf.sum(), 1) * 100
        print(f"  {('['+name+']'):<24} net/win {pt[m].mean()*100:+6.2f}c  OOSnet {oosnet:+6.2f}c  "
              f"Calmar {cal:+5.1f}  maxDD {ddt*100:4.0f}c  win {(pt[m]>0).mean()*100:3.0f}%  "
              f"perfill {perfill:+.2f}c | diff {diff.mean()*100:+.3f}c  t={t:+.2f} (n={nn})")
        print(f"  {'':<24} bench   {bench_line(pt[m])}")
        if nn >= ALERT_N and not np.isnan(t) and abs(t) > ALERT_T:
            alerts.append((name, t, nn))
        if nn >= MIN_WINDOWS and not np.isnan(t) and t > T_BAR and ddt <= DD_MULT * dd0 + 1e-9:
            print(f"      *** {name} CLEARS THE DEPLOY BAR (n>={MIN_WINDOWS}, t>{T_BAR}, DD ok) "
                  f"-> bring to operator ***")

    if alerts:
        lines = [f"{name}: paired t={t:+.2f} over n={nn} (2-sigma {'+' if t>0 else '-'})"
                 for name, t, nn in alerts]
        banner = (f"[STRATEGY ALERT] {a.asset}: trial strategy crossed the 2-sigma bar -- review "
                  f"for action.\n  " + "\n  ".join(lines))
        print("\n" + banner)
        if a.alert:
            for name, t, nn in alerts:               # GitHub Actions annotation (shows on the run)
                print(f"::warning title=Strategy crossed 2-sigma::{name} t={t:+.2f} n={nn} ({a.asset})")
            try:                                     # committed trail + phone push (Telegram via notify)
                with open("STRATEGY_ALERTS.txt", "a") as fh:
                    fh.write(f"{__import__('datetime').datetime.utcnow().isoformat()}Z  {banner}\n")
            except Exception:
                pass
            try:
                import notify
                notify.alert(banner)
            except Exception:
                pass
    else:
        print("\n  no trial strategy past the 2-sigma alert bar yet -- accumulating.")


if __name__ == "__main__":
    main()
