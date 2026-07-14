#!/usr/bin/env python3
"""live_anchor.py -- LIVE-ANCHORED counterfactual scorer for entry-veto arms.

WHY (nodes SIM-LIVE-GAP / SIM-LIVE-GAP-2, 2026-07-14): the box_shadow replay's fill model does not
reproduce reality (first-fill side match 50% = chance, median price gap 11.5c, F1 0.56 on 618 real
placements, uncalibratable within the ~1.2s tape). Its ABSOLUTE EVs are fiction, so nothing scored
on it can be trusted to match live. Entry-VETO arms, however, need NO fill model: they only REMOVE
whole windows, and every live window's REALIZED P&L is known from telemetry. Scoring a veto arm as
"realized P&L of the windows it keeps" makes tested == live BY CONSTRUCTION (up to cross-window
independence, which holds for window-scoped quoting).

Scope: veto/entry arms only (volgate, nsmove, thickbook_veto, c3_share). Quote-CHANGING strategies
(price-cap, back2, av_stoikov family) cannot be scored this way -- they need the hires-tape fill
model (node P1, ~2026-07-18). Do not extend this scorer to them.

Realized convention (matches LIVE-BLEED reconciliation): paired window -> window_mark (exact box
economics: n_boxes*$1 - costs); stranded window -> net_final (naked-leg settlement cash). The
volume-matched permutation null is MANDATORY (rail 7): a veto only counts if it removes worse-than-
random windows.

Usage:  git fetch origin live-state && python live_anchor.py --days 2026-07-12 2026-07-13 2026-07-14
"""
import argparse, subprocess, json, statistics, math, random, datetime
from collections import defaultdict

W = 900
VOLGATE_Q = 0.75          # mirror box_shadow volgate
VOLGATE_MIN_HIST = 12
NSMOVE_MNY = 0.15         # mirror box_shadow nsmove
C3_SHARE_MAX = 0.9        # mirror box_shadow c3_share
THICK_PCTL = 90           # thickbook rolling percentile (box_shadow THICKBOOK_PCTL)


def _sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def _versions(path):
    out = []
    for h in _sh("git", "log", "--format=%H", "origin/live-state", "--", path).split():
        t = _sh("git", "show", f"{h}:{path}")
        if t.strip():
            out.append(t)
    return out


def load_windows(days):
    """cid-deduped winrec -> per-window realized + day tag."""
    Wr = {}
    for d in days:
        for t in reversed(_versions(f"live_state/{d}/kalshi_winrec_btc15m.jsonl")):
            for l in t.splitlines():
                try:
                    w = json.loads(l)
                except Exception:
                    continue
                Wr[w.get("cid")] = w
    out = {}
    for w in Wr.values():
        if not (w.get("n_yes", 0) or w.get("n_no", 0)):
            continue
        ws = int(w["ts"] // W) * W
        realized = (w.get("net_final") or 0.0) if w.get("stranded") else (w.get("window_mark") or 0.0)
        out[ws] = dict(realized=realized, stranded=bool(w.get("stranded")),
                       day=datetime.datetime.utcfromtimestamp(w["ts"]).strftime("%Y-%m-%d"))
    return out


def load_fills(days):
    """trade-deduped fills (fees ledger carries full book ctx) grouped by window."""
    fills = defaultdict(list)
    seen = set()
    for d in days:
        for t in _versions(f"live_state/{d}/kalshi_fees_btc15m.jsonl"):
            for l in t.splitlines():
                try:
                    f = json.loads(l)
                except Exception:
                    continue
                tid = (f.get("raw") or {}).get("trade_id") or (round(f.get("ts", 0), 3), f.get("price"), f.get("side"))
                if tid in seen:
                    continue
                seen.add(tid)
                fills[int(f["ts"] // W) * W].append(f)
    for ws in fills:
        fills[ws].sort(key=lambda f: f["ts"])
    return fills


def window_features(fills_ws):
    """Per-window: first-fill price/depths + realized spot logret vol (leading signal source)."""
    if not fills_ws:
        return None
    f0 = fills_ws[0]
    c = f0.get("ctx") or {}
    spots = [f.get("ctx", {}).get("spot") for f in fills_ws if f.get("ctx", {}).get("spot")]
    vol = None
    if len(spots) >= 3:
        lr = [math.log(spots[i + 1] / spots[i]) for i in range(len(spots) - 1) if spots[i] > 0]
        if len(lr) >= 2:
            vol = statistics.pstdev(lr)
    # completing-side depth for the first fill: the side that must fill NEXT is opposite the fill.
    # first fill bought `side` -> completing side is the other; its resting depth = that side's book.
    bq, aq = c.get("bq") or 0, c.get("aq") or 0
    side = f0.get("side")
    qdepth_c = bq if side == "yes" else aq   # completing side's displayed depth (approx, at-fill)
    qdepth_f = aq if side == "yes" else bq
    return dict(p1=f0.get("price"), vol=vol, qdepth_c=qdepth_c, qdepth_f=qdepth_f)


def score(days):
    wins = load_windows(days)
    fills = load_fills(days)
    wss = sorted(wins)
    feats = {ws: window_features(fills.get(ws, [])) for ws in wss}

    # rolling state for volgate (prior-window vol vs trailing quantile) + thickbook threshold
    flags = {ws: {} for ws in wss}
    hist, prev = [], None
    qhist = []
    for ws in wss:
        f = feats.get(ws)
        vgf = False
        if prev is not None and len(hist) >= VOLGATE_MIN_HIST:
            s = sorted(hist)
            vgf = prev > s[min(len(s) - 1, int(VOLGATE_Q * len(s)))]
        flags[ws]["volgate"] = vgf
        p1 = (f or {}).get("p1")
        flags[ws]["nsmove"] = vgf and p1 is not None and abs(p1 - 0.5) < NSMOVE_MNY
        qc = (f or {}).get("qdepth_c") or 0
        qf = (f or {}).get("qdepth_f") or 0
        thr = None
        if len(qhist) >= 30:
            s = sorted(qhist)
            thr = s[min(len(s) - 1, int(THICK_PCTL / 100 * len(s)))]
        flags[ws]["thickbook_veto"] = thr is not None and qc > thr
        flags[ws]["c3_share"] = (qc + qf) > 0 and qc / (qc + qf) > C3_SHARE_MAX
        if f and f.get("vol") is not None:
            prev = f["vol"]
            hist.append(f["vol"])
        if qc:
            qhist.append(qc)

    base = [wins[ws]["realized"] for ws in wss]
    base_total = sum(base)
    print(f"LIVE-ANCHORED SCORER  days={days}  windows={len(wss)}  "
          f"realized total=${base_total:+.2f}  (tested==live by construction)")
    print(f"{'arm':<16}{'veto':>5}{'kept EV$':>10}{'delta$':>9}{'d-clust t':>10}{'vol-match p':>12}")
    rng = random.Random(7)
    for arm in ("volgate", "nsmove", "thickbook_veto", "c3_share"):
        kept = [ws for ws in wss if not flags[ws][arm]]
        cut = [ws for ws in wss if flags[ws][arm]]
        kept_ev = sum(wins[ws]["realized"] for ws in kept)
        # volume-matched null: remove |cut| random windows instead
        null = []
        for _ in range(20000):
            samp = set(rng.sample(wss, len(cut))) if cut else set()
            null.append(sum(wins[ws]["realized"] for ws in wss if ws not in samp))
        p = sum(1 for x in null if x >= kept_ev) / len(null) if cut else float("nan")
        # day-clustered t of (kept-mean - all-mean) per day
        bd = defaultdict(lambda: [[], []])
        for ws in wss:
            bd[wins[ws]["day"]][0].append(wins[ws]["realized"])
            if not flags[ws][arm]:
                bd[wins[ws]["day"]][1].append(wins[ws]["realized"])
        diffs = [statistics.mean(k) - statistics.mean(a) for a, k in
                 ((v[0], v[1]) for v in bd.values()) if k and a]
        t = (statistics.mean(diffs) / (statistics.stdev(diffs) / math.sqrt(len(diffs)))
             if len(diffs) > 1 and statistics.stdev(diffs) > 0 else float("nan"))
        print(f"{arm:<16}{len(cut):>5}{kept_ev:>10.2f}{kept_ev - base_total:>9.2f}{t:>10.2f}{p:>12.3f}")
    print("\nRead: 'kept EV' = realized $ of the windows the veto keeps. delta>0 with vol-match p<0.05")
    print("means the veto removed genuinely-worse-than-random windows on REAL money. Quote-changing")
    print("strategies (price-cap/back2/av_stoikov) CANNOT be scored here -- hires fill model ~07-18.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="+", required=True)
    score(ap.parse_args().days)
