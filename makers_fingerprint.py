"""makers_fingerprint.py -- reverse-engineer the top makers' strategies from the cached trade tape
(makers_trades.jsonl from makers_scan.py), cross-referenced with our own tick data where windows overlap.

For each selected wallet, across its markets, we extract the behaviors that DEFINE a strategy:
  clip      median trade size (shares)
  2sided    min(buy,sell)/total   (1.0 = perfectly two-sided MM; 0 = one-sided directional)
  flip      P(consecutive trades switch side)  -- MM churn vs accumulation
  open/mid/late   fraction of trades in window phases [0-3min] / [mid] / [last 2min]
  rspread   realized spread captured = sell_vwap - buy_vwap on its main token (cents/share; >0 = MM edge)
  flatten   1 - |end inventory| / peak inventory  (1 = fully flattens before close; 0 = holds to resolution)
  mom       corr(signed trade dir, prior-~45s price change)  (+ = momentum/buy-into-rise; - = fade/mean-revert)
  uplean    Up volume / total volume  (outcome bias)
The price path per window is the all-trades VWAP in 15s buckets (model-free consensus mid). Where a
window matches one we collected (gha_data ticks_*.jsonl, synced via sync_data.sh), we also align to the
REAL BTC spot to confirm momentum/fade vs BTC (not just the token's own path).  python makers_fingerprint.py
"""
from __future__ import annotations
import collections, glob, json, math, os

CACHE = "makers_trades.jsonl"


def _corr(a, b):
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return float("nan")
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / math.sqrt(va * vb)


def _std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def load_markets():
    """list of dicts: {asset,ws,win,res,trades:[(w,side,sz,pr,oi,ts)]} ; + price path per window."""
    M = []
    for ln in open(CACHE):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        win = r["tenor"] * 60
        tr = sorted(r["trades"], key=lambda t: t[5])
        # price path: VWAP per 15s bucket (consensus mid), forward-filled
        buck = collections.OrderedDict()
        for w, side, sz, pr, oi, ts in tr:
            p_up = pr if oi == 0 else 1 - pr            # express everything as P(Up)
            b = (ts - r["ws"]) // 15
            v = buck.setdefault(b, [0.0, 0.0])
            v[0] += p_up * sz; v[1] += sz
        path = {b: (v[0] / v[1]) for b, v in buck.items() if v[1] > 0}
        M.append({"asset": r["asset"], "ws": r["ws"], "win": win, "res": r["res_up"],
                  "trades": tr, "path": path})
    return M


def price_at(path, win, sec):
    """consensus P(Up) at `sec` into the window (nearest earlier 15s bucket)."""
    b = sec // 15
    for bb in range(b, -1, -1):
        if bb in path:
            return path[bb]
    return None


def fingerprint(M, wallets):
    fp = {w: collections.defaultdict(list) for w in wallets}
    wl = set(wallets)
    for m in M:
        win = m["win"]; path = m["path"]
        byw = collections.defaultdict(list)
        for t in m["trades"]:
            if t[0] in wl:
                byw[t[0]].append(t)
        for w, ts in byw.items():
            f = fp[w]
            ts.sort(key=lambda t: t[5])
            sizes = [t[2] for t in ts]
            f["clip"] += sizes
            nb = sum(t[1] == "BUY" for t in ts); ns = len(ts) - nb
            f["2sided"].append(min(nb, ns) / len(ts))
            flips = sum(1 for i in range(1, len(ts)) if ts[i][1] != ts[i - 1][1])
            f["flip"].append(flips / max(1, len(ts) - 1))
            for t in ts:
                sec = t[5] - m["ws"]
                f["open"].append(1.0 if sec < 180 else 0.0)
                f["late"].append(1.0 if sec > win - 120 else 0.0)
            # realized spread on the main token (the oi this wallet trades most)
            oi_main = collections.Counter(t[4] for t in ts).most_common(1)[0][0]
            bv = [(t[3], t[2]) for t in ts if t[4] == oi_main and t[1] == "BUY"]
            sv = [(t[3], t[2]) for t in ts if t[4] == oi_main and t[1] == "SELL"]
            if bv and sv:
                bvw = sum(p * s for p, s in bv) / sum(s for _, s in bv)
                svw = sum(p * s for p, s in sv) / sum(s for _, s in sv)
                f["rspread"].append((svw - bvw) * 100)        # cents/share captured
            # inventory trajectory (net signed position over time) -> flatten ratio
            pos = 0.0; peak = 0.0
            for t in ts:
                d = (t[2] if t[1] == "BUY" else -t[2]) * (1 if t[4] == 0 else -1)  # signed P(Up) exposure
                pos += d; peak = max(peak, abs(pos))
            if peak > 0:
                f["flatten"].append(1 - abs(pos) / peak)
            # momentum vs fade: signed dir vs prior ~45s price change
            dirs, chgs = [], []
            for t in ts:
                sec = t[5] - m["ws"]
                p0 = price_at(path, win, max(0, sec - 45)); p1 = price_at(path, win, sec)
                if p0 is None or p1 is None:
                    continue
                sdir = (1 if t[1] == "BUY" else -1) * (1 if t[4] == 0 else -1)   # +1 = increasing P(Up) exposure
                dirs.append(sdir); chgs.append(p1 - p0)
            c = _corr(dirs, chgs)
            if c == c:
                f["mom"].append(c)
            upv = sum(t[2] for t in ts if t[4] == 0); dnv = sum(t[2] for t in ts if t[4] == 1)
            if upv + dnv > 0:
                f["uplean"].append(upv / (upv + dnv))
    return fp


def agg_from_cache(assets=None):
    """recompute per-wallet P&L aggregates (mirror of makers_scan.analyze) to pick the top set."""
    W = collections.defaultdict(lambda: {"pnls": [], "vol": 0.0, "b": 0, "s": 0, "sz": []})
    for ln in open(CACHE):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if assets and r["asset"] not in assets:
            continue
        res = r["res_up"]
        perm = collections.defaultdict(lambda: {"cash": 0.0, "up": 0.0, "dn": 0.0, "b": 0, "s": 0, "vol": 0.0, "sz": []})
        for w, side, sz, pr, oi, ts in r["trades"]:
            d = perm[w]; buy = side == "BUY"
            d["cash"] += (-pr * sz if buy else pr * sz)
            if oi == 0:
                d["up"] += sz if buy else -sz
            else:
                d["dn"] += sz if buy else -sz
            d["b"] += buy; d["s"] += not buy; d["vol"] += pr * sz; d["sz"].append(sz)
        for w, d in perm.items():
            a = W[w]; a["pnls"].append(d["cash"] + d["up"] * res + d["dn"] * (1 - res))
            a["vol"] += d["vol"]; a["b"] += d["b"]; a["s"] += d["s"]; a["sz"] += d["sz"]
    out = {}
    for w, a in W.items():
        n = len(a["pnls"]); sd = _std(a["pnls"]); tot = a["b"] + a["s"]
        out[w] = {"pnl": sum(a["pnls"]), "mkts": n, "vol": a["vol"],
                  "t": (sum(a["pnls"]) / n) / (sd / math.sqrt(n)) if sd > 0 else float("nan"),
                  "twosided": min(a["b"], a["s"]) / tot if tot else 0.0,
                  "avgsz": sum(a["sz"]) / len(a["sz"]) if a["sz"] else 0.0}
    return out


def load_our_spot():
    """Our collected real BTC spot per window (gha_data ticks, synced via sync_data.sh): ws -> [(sec,spot)]."""
    S = {}
    for f in glob.glob("gha_data/ticks_*.jsonl"):
        for ln in open(f):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            pts = [(t[0], t[2]) for t in r.get("ticks", []) if t[2] is not None]
            if len(pts) > 10:
                S[r["ws"]] = sorted(pts)
    return S


def spot_at(pts, sec):
    prev = None
    for s, v in pts:
        if s <= sec:
            prev = v
        else:
            break
    return prev


def btc_xref(M, wallets, S, lag=45):
    """For windows where we have REAL BTC spot, corr(maker signed dir, prior-`lag`s BTC change). +ve =
    trades WITH BTC moves (momentum / lead-lag follow); -ve = against (fade). Ground-truth, not token-path."""
    wl = set(wallets)
    acc = {w: {"d": [], "c": []} for w in wallets}
    for m in M:
        if m["ws"] not in S:
            continue
        pts = S[m["ws"]]
        for w, side, sz, pr, oi, ts in m["trades"]:
            if w not in wl:
                continue
            sec = ts - m["ws"]
            s0 = spot_at(pts, sec - lag); s1 = spot_at(pts, sec)
            if s0 is None or s1 is None or s0 == 0:
                continue
            sdir = (1 if side == "BUY" else -1) * (1 if oi == 0 else -1)   # +1 = adding P(Up) exposure
            acc[w]["d"].append(sdir); acc[w]["c"].append((s1 - s0) / s0)
    return {w: (_corr(a["d"], a["c"]), len(a["d"])) for w, a in acc.items()}


def med(xs):
    return sorted(xs)[len(xs) // 2] if xs else float("nan")


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def main():
    if not os.path.exists(CACHE):
        print("run makers_scan.py first"); return
    M = load_markets()
    agg = agg_from_cache()
    makers = {w: a for w, a in agg.items() if a["twosided"] > 0.30 and a["mkts"] >= 8 and a["avgsz"] < 60}
    top_ra = sorted([w for w in makers if makers[w]["pnl"] > 0], key=lambda w: -makers[w]["t"])[:25]
    top_pnl = sorted(makers, key=lambda w: -makers[w]["pnl"])[:25]
    sel = list(dict.fromkeys(top_ra + top_pnl))
    fp = fingerprint(M, sel)
    print(f"markets={len(M)}  makers(2sided>.3,>=8mkts,clip<60)={len(makers)}  fingerprinting {len(sel)}\n")
    hdr = f"{'wallet':>12}{'pnl':>7}{'t':>5}{'mkts':>5}{'clip':>5}{'2sd':>5}{'flip':>5}{'open':>5}{'late':>5}{'rspr':>6}{'flat':>5}{'mom':>6}{'upln':>5}"
    print("TOP MAKERS BY RISK-ADJUSTED (t-stat):"); print(hdr)
    for w in top_ra:
        f = fp[w]; a = makers[w]
        print(f"{w[:10]:>12}{a['pnl']:>+7.0f}{a['t']:>5.1f}{a['mkts']:>5}{med(f['clip']):>5.0f}"
              f"{mean(f['2sided']):>5.2f}{mean(f['flip']):>5.2f}{mean(f['open']):>5.2f}{mean(f['late']):>5.2f}"
              f"{mean(f['rspread']):>+6.1f}{mean(f['flatten']):>5.2f}{mean(f['mom']):>+6.2f}{mean(f['uplean']):>5.2f}")
    print("\nLEGEND: clip=median shares; 2sd=two-sided frac; flip=side-switch rate; open/late=trade-time"
          " phase frac; rspr=realized spread cents/sh; flat=1-|end inv|/peak (1=flattens); mom=corr(dir,"
          "prior token price chg) (+momentum/-fade); upln=Up vol frac.")
    # cross-reference with OUR collected REAL BTC spot (ground truth) on overlapping windows
    S = load_our_spot()
    if S:
        bx = btc_xref(M, top_ra, S)
        ov = sum(1 for m in M if m["ws"] in S)
        print(f"\nBTC-SPOT CROSS-REF (our real spot, {ov} overlapping windows): corr(maker dir, prior-45s BTC move)")
        print("  +ve = trades WITH BTC moves (momentum/lead-lag follow); -ve = fades BTC; |corr| small = BTC-neutral MM")
        for w in top_ra:
            c, n = bx.get(w, (float("nan"), 0))
            if n >= 20:
                print(f"  {w[:10]:>12}  btc_mom={c:+.2f}  (n={n} trades in overlap)")
    # archetype tallies
    arche = collections.Counter()
    for w in sel:
        f = fp[w]
        mo = mean(f["mom"]); rs = mean(f["rspread"]); fl = mean(f["flatten"]); la = mean(f["late"])
        if rs == rs and rs > 0.3 and (mo != mo or abs(mo) < 0.15):
            arche["neutral spread-capture MM"] += 1
        elif mo == mo and mo > 0.15:
            arche["momentum (buy into move)"] += 1
        elif mo == mo and mo < -0.15:
            arche["fade / mean-revert"] += 1
        if la == la and la > 0.4:
            arche["late/expiry-concentrated"] += 1
        if fl == fl and fl < 0.3:
            arche["holds inventory to resolution"] += 1
    print("\nARCHETYPE TALLY (selected makers):")
    for k, v in arche.most_common():
        print(f"  {v:>3}  {k}")


if __name__ == "__main__":
    main()
