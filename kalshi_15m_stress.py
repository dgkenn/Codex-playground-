#!/usr/bin/env python3
"""kalshi_15m_stress.py -- is there a VIABLE transient-wide-spread MAKER play in the 15m BTC binary
that AVOIDS the queue war that killed the ATM box?

Hypothesis (operator): the dead box quoted ATM (~0.5) where a co-located ladder-MM owns the queue.
But when VOLATILITY SPIKES the bid/ask spread TRANSIENTLY WIDENS (>2-3c vs ~1c baseline) and the MM
may pull. A maker who provides liquidity INTO those transient wide-spread moments (improve the touch
by 1c) might capture the wide spread WITHOUT fighting the tight-ATM queue. Test whether that is +EV
net of adverse selection -- or whether wide-spread moments are exactly the toxic/informed moments
(you get run over) and/or too fast for a ~1s cloud bot to land (the same latency wall).

Reads tick series straight from git (origin/gha-data); no API.
  ticks_*.jsonl.gz : {"ws":,"role":"up","ticks":[[t_rel_s, mid, spot, mid2, bid, bid_sz, ask, ask_sz],...]}
  shadow_windows_* : {"ws":, "resolved_up":0/1}

METHOD (rigorous, anti-artifact):
 1. Spread time-series characterization: baseline, wide-episode frequency, duration, vol trigger,
    and -- decisively -- can a 1.2s-cadence bot even SEE an episode before it closes.
 2. Wide-spread maker markout: at each wide-spread tick, post inside (touch+1c). A causal FILL model
    (a later taker must cross our improved price) + MARKOUT to a short horizon AND to settlement.
    Quantify captured-spread vs adverse-selection. Cluster by window; OOS split by date.
 3. Gate tension: the box A/B gates say AVOID high vol (Foucault t20) and high VPIN (t32). This play
    quotes INTO high vol. Resolve with data: does a low-|sig| sub-gate rescue anything?
 4. Latency/capacity reality: episode-duration vs the 1.2s poll+ack wall.

The anti-artifact discipline from KALSHI_15M_LONGSHOT.md (time-in-band selection killed the longshot
"lead") applies: markout is measured forward from the DECISION tick (no look-ahead, no conditioning on
the path that follows), and settlement P&L is the load-bearing column.
"""
import subprocess, gzip, io, json, math, sys
import numpy as np
from collections import defaultdict

BRANCH = "origin/gha-data"
CADENCE = 1.2            # observed poll/MM-heartbeat cadence (s)
IMPROVE = 0.01          # we post 1c inside the touch (the only way to jump the queue, q0->0)
WIDE = 0.025            # "wide" spread threshold: > 2c (baseline median is 1c; >2c is the tail)
SHORT_HORIZON = 30.0    # markout horizon (s) -- ~ a few minutes is settlement; 30s is the fast read
FEE = 0.0               # CRYPTO15M maker fee = 0 (taker disposal also 0 at this venue for crypto15m)


def gshow(path):
    return subprocess.run(["git", "show", f"{BRANCH}:{path}"], capture_output=True).stdout


def files(pat):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", BRANCH], capture_output=True, text=True).stdout
    return sorted(l for l in out.splitlines() if pat in l)


def load():
    """Return res[ws]=0/1 and series[ws]=sorted np arrays (t, mid, spot, bid, ask, bsz, asz)."""
    res = {}
    for f in files("shadow_windows_kalshi_btc15m"):
        for ln in gshow(f).splitlines():
            try:
                w = json.loads(ln)
            except Exception:
                continue
            if w.get("ws") is not None and w.get("resolved_up") in (0, 1):
                res[w["ws"]] = int(w["resolved_up"])
    rows = defaultdict(list)
    date_of = {}
    for f in files("ticks_kalshi_btc15m"):
        date = f.split("/")[1]
        raw = gshow(f)
        try:
            data = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode()
        except Exception:
            continue
        for ln in data.splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("role") != "up":
                continue
            ws = r.get("ws")
            if ws is None or ws not in res:
                continue
            date_of[ws] = date
            for tk in (r.get("ticks") or []):
                if len(tk) < 8:
                    continue
                t, mid, spot, _m2, bid, bsz, ask, asz = tk[:8]
                if None in (t, bid, ask, spot):
                    continue
                if not (0 < bid <= ask < 1):
                    continue
                rows[ws].append((float(t), float(mid) if mid is not None else (bid + ask) / 2,
                                 float(spot), float(bid), float(ask),
                                 float(bsz) if bsz is not None else 0.0,
                                 float(asz) if asz is not None else 0.0))
    series = {}
    for ws, rs in rows.items():
        rs.sort()
        series[ws] = np.array(rs, float)
    return res, series, date_of


def characterize(res, series):
    """Part 1: spread distribution, wide-episode freq/duration, vol trigger, latency-visibility."""
    all_sp = []
    spot_move = []   # |bps spot move over prior ~3.6s| at each tick (vol proxy)
    wide_flag = []
    episode_durs = []   # contiguous-wide-run durations (s)
    n_ticks = 0
    for ws, S in series.items():
        if len(S) < 5:
            continue
        t, mid, spot, bid, ask = S[:, 0], S[:, 1], S[:, 2], S[:, 3], S[:, 4]
        sp = ask - bid
        # vol proxy: spot move (bps) vs the spot ~3 ticks (3.6s) earlier, abs
        mv = np.zeros(len(S))
        for i in range(len(S)):
            j = i
            while j > 0 and t[i] - t[j] < 3.5:
                j -= 1
            if spot[j] > 0:
                mv[i] = abs(spot[i] / spot[j] - 1) * 1e4
        all_sp.append(sp); spot_move.append(mv)
        w = sp > WIDE
        wide_flag.append(w)
        n_ticks += len(S)
        # contiguous wide episodes (in this window's tick stream)
        i = 0
        while i < len(w):
            if w[i]:
                j = i
                while j + 1 < len(w) and w[j + 1]:
                    j += 1
                episode_durs.append(t[j] - t[i] if j > i else 0.0)
                i = j + 1
            else:
                i += 1
    all_sp = np.concatenate(all_sp); spot_move = np.concatenate(spot_move)
    wide_flag = np.concatenate(wide_flag)
    episode_durs = np.array(episode_durs)
    print("=== PART 1: SPREAD TIME-SERIES CHARACTERIZATION ===")
    print(f"windows={len(series)}  ticks={n_ticks}  cadence~{CADENCE}s (fixed)")
    print("spread cents:  median %.2f  mean %.2f  p75 %.2f  p90 %.2f  p95 %.2f  p99 %.2f  max %.2f" % (
        np.median(all_sp) * 100, all_sp.mean() * 100, np.percentile(all_sp, 75) * 100,
        np.percentile(all_sp, 90) * 100, np.percentile(all_sp, 95) * 100,
        np.percentile(all_sp, 99) * 100, all_sp.max() * 100))
    for thr in (0.015, 0.025, 0.035, 0.05):
        print(f"  frac spread > {thr*100:.0f}c : {(all_sp > thr).mean():.4f}")
    print(f"\nWide (> {WIDE*100:.0f}c) episodes: n={len(episode_durs)}  "
          f"single-tick (dur=0) frac={np.mean(episode_durs == 0):.3f}")
    if len(episode_durs):
        print("  episode duration s: median %.2f  mean %.2f  p90 %.2f  max %.2f" % (
            np.median(episode_durs), episode_durs.mean(), np.percentile(episode_durs, 90),
            episode_durs.max()))
        print(f"  frac episodes lasting >= 1 full poll ({CADENCE}s, i.e. visible+actionable next tick): "
              f"{np.mean(episode_durs >= CADENCE):.3f}")
        print(f"  frac episodes lasting >= {2*CADENCE:.1f}s (see it, then place, then it's still there): "
              f"{np.mean(episode_durs >= 2 * CADENCE):.3f}")
    # vol trigger: spot move at wide vs narrow ticks
    print("\nVol trigger -- |spot move| bps over prior 3.5s:")
    print("  at WIDE ticks  (sp>%.0fc): median %.1f  mean %.1f  p90 %.1f" % (
        WIDE * 100, np.median(spot_move[wide_flag]), spot_move[wide_flag].mean(),
        np.percentile(spot_move[wide_flag], 90)))
    nw = ~wide_flag
    print("  at NARROW ticks(sp<=%.0fc): median %.1f  mean %.1f  p90 %.1f" % (
        WIDE * 100, np.median(spot_move[nw]), spot_move[nw].mean(),
        np.percentile(spot_move[nw], 90)))
    hv = spot_move > np.percentile(spot_move, 95)
    print("  P(wide | spot-move in top 5%%) = %.3f vs base P(wide) = %.3f  -> vol %sdrives width" % (
        wide_flag[hv].mean(), wide_flag.mean(),
        "" if wide_flag[hv].mean() > 1.5 * wide_flag.mean() else "weakly "))
    return all_sp, wide_flag


def markout(res, series, date_of):
    """Part 2/3/4: at each WIDE-spread tick, post inside (touch+1c on the side a passive maker would
    quote) and measure REALIZED P&L net of adverse selection, via a CAUSAL fill model.

    Fill model (queue-jump assumption -- the BEST case for the maker, q0=0 since we improve the
    touch): we quote NO at price (no_touch + 1c) i.e. we BUY YES at bid+1c, and separately quote the
    YES-sell at ask-1c. A passive improved quote fills iff a later taker crosses it. Causally: our
    improved BID (bid+1c) fills if within HORIZON a tick shows ask <= bid+1c (price came down to us)
    -- proxy for a sell taker hitting our resting bid. Symmetric for the improved ASK.

    We then mark the fill to (a) the mid SHORT_HORIZON seconds later and (b) SETTLEMENT (res in {0,1}).
    Net P&L per filled contract, in cents. Clustered by window; reported for ALL wide ticks and for
    the low-vol sub-gate (Foucault/VPIN tension)."""
    # bucket by side; we evaluate BOTH the improve-bid (long YES) and improve-ask (short YES) quote.
    recs = []   # dict: ws, date, side, vol_bps, fill, mo_short, mo_settle, spread
    for ws, S in series.items():
        if len(S) < 5:
            continue
        t, mid, spot, bid, ask = S[:, 0], S[:, 1], S[:, 2], S[:, 3], S[:, 4]
        r = res[ws]
        sp = ask - bid
        for i in range(len(S)):
            if sp[i] <= WIDE:
                continue
            # vol proxy at decision tick
            j = i
            while j > 0 and t[i] - t[j] < 3.5:
                j -= 1
            vol = abs(spot[i] / spot[j] - 1) * 1e4 if spot[j] > 0 else 0.0
            # improved quotes (strictly inside the wide spread)
            my_bid = bid[i] + IMPROVE      # we BUY YES here (passive); fills if a sell crosses down
            my_ask = ask[i] - IMPROVE      # we SELL YES here (passive); fills if a buy crosses up
            # short-horizon future window of ticks (strictly after i)
            fut = [k for k in range(i + 1, len(S)) if t[k] - t[i] <= SHORT_HORIZON]
            if not fut:
                continue
            # CAUSAL fill: improved BID fills if some future ask <= my_bid (a seller meets our price)
            fb = any(ask[k] <= my_bid + 1e-9 for k in fut)
            fa = any(bid[k] >= my_ask - 1e-9 for k in fut)
            # mid at end of short horizon (markout reference)
            kshort = fut[-1]
            mid_short = (bid[kshort] + ask[kshort]) / 2.0
            if fb:   # we are LONG YES at my_bid
                recs.append(dict(ws=ws, date=date_of[ws], side="bid", vol=vol, spread=sp[i],
                                 entry=my_bid, mo_short=(mid_short - my_bid) * 100,
                                 mo_settle=(r - my_bid) * 100))
            if fa:   # we are SHORT YES at my_ask  (P&L = my_ask - outcome)
                recs.append(dict(ws=ws, date=date_of[ws], side="ask", vol=vol, spread=sp[i],
                                 entry=my_ask, mo_short=(my_ask - mid_short) * 100,
                                 mo_settle=(my_ask - r) * 100))
    if not recs:
        print("\nNo wide-spread fills under the causal model -- play is empty (latency-walled).")
        return recs
    print("\n=== PART 2: WIDE-SPREAD MAKER MARKOUT (causal fill, improve touch +1c) ===")
    print(f"wide ticks producing a causal fill: {len(recs)}  "
          f"distinct windows: {len({x['ws'] for x in recs})}")
    _report_group("ALL wide-spread fills", recs)

    # Part 3: gate tension. low-vol sub-gate (Foucault t20: stand down in high vol; VPIN-analog).
    print("\n=== PART 3: GATE TENSION (vol stand-down vs quoting-into-vol) ===")
    med_vol = np.median([x["vol"] for x in recs])
    lo = [x for x in recs if x["vol"] <= med_vol]
    hi = [x for x in recs if x["vol"] > med_vol]
    _report_group(f"LOW-vol wide fills (|move|<=%.1fbps) -- Foucault-allowed subset" % med_vol, lo)
    _report_group(f"HIGH-vol wide fills (|move|> %.1fbps) -- the toxic spike the gate forbids" % med_vol, hi)
    return recs


def _wstats(vals_by_ws):
    """Window-clustered mean + t-stat: one mean per window, then t over windows (honest power)."""
    wm = [np.mean(v) for v in vals_by_ws.values() if v]
    wm = np.array(wm)
    if len(wm) < 2:
        return float("nan"), float("nan"), len(wm)
    return wm.mean(), wm.mean() / (wm.std(ddof=1) / math.sqrt(len(wm))), len(wm)


def _report_group(label, recs):
    if not recs:
        print(f"  [{label}] empty"); return
    short = np.array([x["mo_short"] for x in recs])
    settle = np.array([x["mo_settle"] for x in recs])
    by_ws_s = defaultdict(list); by_ws_set = defaultdict(list)
    for x in recs:
        by_ws_s[x["ws"]].append(x["mo_short"]); by_ws_set[x["ws"]].append(x["mo_settle"])
    ms, ts, nw = _wstats(by_ws_s)
    mset, tset, _ = _wstats(by_ws_set)
    print(f"  [{label}] fills={len(recs)} windows={nw}")
    print(f"     SHORT-markout(30s):  pooled mean %+.2fc | window-clustered %+.2fc  t=%+.2f" % (
        short.mean(), ms, ts))
    print(f"     SETTLEMENT P&L:      pooled mean %+.2fc | window-clustered %+.2fc  t=%+.2f  (LOAD-BEARING)" % (
        settle.mean(), mset, tset))


def oos(recs):
    """Part: OOS by date. Learn nothing -- just split first 60%% dates / last 40%% and report both,
    so any 'edge' must survive a held-out time block (the artifact-killer)."""
    if not recs:
        return
    print("\n=== OOS: TIME-SPLIT (first 60%% dates vs last 40%%) ===")
    dates = sorted({x["date"] for x in recs})
    cut = dates[int(len(dates) * 0.6)]
    isr = [x for x in recs if x["date"] < cut]
    oosr = [x for x in recs if x["date"] >= cut]
    print(f"  split at {cut}: IS dates {dates[:dates.index(cut)]}  OOS dates {dates[dates.index(cut):]}")
    _report_group("IS  (all wide fills)", isr)
    _report_group("OOS (all wide fills)", oosr)


def main():
    res, series, date_of = load()
    print(f"loaded {len(res)} settled windows, {len(series)} with usable tick series\n")
    characterize(res, series)
    recs = markout(res, series, date_of)
    oos(recs)
    print("\n=== VERDICT ===")
    print("See KALSHI_15M_STRESS.md for the written verdict (latency wall + adverse selection).")


if __name__ == "__main__":
    main()
