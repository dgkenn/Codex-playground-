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

import numpy as np

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
      spot(BTC at fill), sset(BTC at settlement -- for the perp-hedge trial)."""
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
                    recs.append({"side": "bid", "settle": res - b0, "exit": exit_bid, "sig": mv,
                                 "p": b0, "spread": spread, "k": k, "tau": tau, "flow": flow,
                                 "depth": dk, "oi": oi_slope, "vpin": _vpin_at(bt, bi, t_arr[i]),
                                 "spot": float(spot[k]) if not np.isnan(spot[k]) else None,
                                 "sset": sset}); done_b = True
            if not done_a and buy and p >= a0 - 1e-9:
                if qa >= sz:
                    qa -= sz
                else:
                    recs.append({"side": "ask", "settle": a0 - res, "exit": exit_ask, "sig": -mv,
                                 "p": round(1.0 - a0, 4), "spread": spread, "k": k, "tau": tau,
                                 "flow": -flow, "depth": dk, "oi": oi_slope,
                                 "vpin": _vpin_at(bt, bi, t_arr[i]),
                                 "spot": float(spot[k]) if not np.isnan(spot[k]) else None,
                                 "sset": sset}); done_a = True
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
            if hold_ok is not None and held is not None and hold_ok(held):
                continue                                       # hold the favorable unpaired leg
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
    print(f"  {'(metrics: net/win, OOS net, OOS Calmar, maxDD, win%, per-fill, paired t vs P0)':<24}")

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
