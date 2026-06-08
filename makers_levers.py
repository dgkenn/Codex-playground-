"""makers_levers.py -- mine the cached maker tape for DATA-BACKED, profit-improving changes.

Two engines:
 (A) per-TRADE markout-to-resolution = signed(payoff - price) per share (payoff = res for the token
     side). Positive = the fill made money held to settle. Bucketed by window phase, clip size, price
     level, and prior BTC move (our real spot, overlapping windows) -> tells us WHICH conditions are
     profitable to quote vs toxic to pull. Restricted to maker-like wallets (two-sided, small clips).
 (B) cross-MAKER correlations: how per-wallet P&L / P&L-per-$1k tracks clip, #markets, late-fraction,
     two-sidedness, inventory -> which behaviors the winners share. python makers_levers.py
"""
from __future__ import annotations
import collections, glob, json, math

CACHE = "makers_trades.jsonl"


def _corr(a, b):
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / math.sqrt(va * vb) if va > 0 and vb > 0 else float("nan")


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def load_spot():
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


def maker_wallets():
    """wallets that look like makers: two-sided>0.3, >=10 markets, mean clip<60."""
    W = collections.defaultdict(lambda: {"b": 0, "s": 0, "sz": [], "mk": set()})
    for ln in open(CACHE):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        for w, side, sz, pr, oi, ts in r["trades"]:
            a = W[w]; a["b"] += side == "BUY"; a["s"] += side != "BUY"; a["sz"].append(sz); a["mk"].add(r["cid"])
    mk = set()
    for w, a in W.items():
        tot = a["b"] + a["s"]
        if tot and min(a["b"], a["s"]) / tot > 0.3 and len(a["mk"]) >= 10 and (sum(a["sz"]) / len(a["sz"])) < 60:
            mk.add(w)
    return mk


def main():
    S = load_spot()
    mk = maker_wallets()
    print(f"maker-like wallets: {len(mk)}  | overlap-spot windows: {len(S)}\n")
    # (A) per-trade markout-to-resolution, maker-like only
    phase = {"open(<3m)": [], "mid": [], "late(>11m)": []}
    by_clip = collections.defaultdict(list)
    by_price = collections.defaultdict(list)
    mvbuckets = {"|move|<2bp": {"with": [], "against": []}, "2-6bp": {"with": [], "against": []},
                 ">6bp": {"with": [], "against": []}}
    for ln in open(CACHE):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        res = r["res_up"]; ws = r["ws"]; win = r["tenor"] * 60
        pts = S.get(ws)
        for w, side, sz, pr, oi, ts in r["trades"]:
            if w not in mk:
                continue
            payoff = res if oi == 0 else (1 - res)
            mo = (payoff - pr) if side == "BUY" else (pr - payoff)   # per-share markout to resolution
            sec = ts - ws
            ph = "open(<3m)" if sec < 180 else ("late(>11m)" if sec > win - 240 else "mid")
            phase[ph].append(mo)
            cb = "1-5" if sz <= 5 else ("6-15" if sz <= 15 else ("16-40" if sz <= 40 else ">40"))
            by_clip[cb].append(mo)
            p_up = pr if oi == 0 else 1 - pr
            pb = f"{round(p_up*10)*10:02d}c"
            by_price[pb].append(mo)
            if pts is not None:
                s0 = spot_at(pts, sec - 45); s1 = spot_at(pts, sec)
                if s0 and s1 and s0 > 0:
                    mvbp = abs(s1 - s0) / s0 * 1e4
                    sdir = (1 if side == "BUY" else -1) * (1 if oi == 0 else -1)
                    withmove = (sdir * (s1 - s0)) > 0      # traded WITH the BTC move
                    bk = "|move|<2bp" if mvbp < 2 else ("2-6bp" if mvbp < 6 else ">6bp")
                    mvbuckets[bk]["with" if withmove else "against"].append(mo)

    def line(name, xs):
        return f"  {name:>14}: markout/sh {_mean(xs):+.4f}  n={len(xs)}" if xs else f"  {name:>14}: -"
    print("(A1) markout-to-resolution by WINDOW PHASE (maker fills):")
    for k in ("open(<3m)", "mid", "late(>11m)"):
        print(line(k, phase[k]))
    print("\n(A2) by CLIP SIZE:")
    for k in ("1-5", "6-15", "16-40", ">40"):
        print(line(k, by_clip[k]))
    print("\n(A3) by PRICE LEVEL (P(Up) bucket):")
    for k in sorted(by_price):
        if len(by_price[k]) > 50:
            print(line(k, by_price[k]))
    print("\n(A4) by PRIOR-45s BTC MOVE, traded WITH vs AGAINST the move (overlap windows):")
    for k, d in mvbuckets.items():
        print(f"  {k:>10}:  WITH {_mean(d['with']):+.4f} (n={len(d['with'])})   AGAINST {_mean(d['against']):+.4f} (n={len(d['against'])})")

    # (B) cross-maker behavior vs profitability
    import makers_scan as m
    rows, _ = m.analyze(["btc"])
    M = [r for r in rows if m.is_maker(r) and r["mkts"] >= 10]
    def q(key, rev=False):
        xs = sorted(M, key=lambda r: r[key], reverse=rev)
        k = max(1, len(xs) // 4)
        lo, hi = xs[:k], xs[-k:]
        return _mean([r["pnl_per_1k"] for r in lo]), _mean([r["pnl_per_1k"] for r in hi])
    print(f"\n(B) cross-maker (n={len(M)} BTC makers): P&L-per-$1k by behavior quartile")
    for key, lab in [("avgsz", "clip size"), ("mkts", "#markets"), ("frac_late", "late-fraction"),
                     ("twosided", "two-sidedness"), ("avg_delta", "inventory carried")]:
        lo, hi = q(key)
        print(f"  {lab:>16}: low-quartile {lo:+.1f}/1k   high-quartile {hi:+.1f}/1k")
    print(f"  corr(pnl, #markets)        = {_corr([r['mkts'] for r in M], [r['pnl'] for r in M]):+.2f}")
    print(f"  corr(pnl_per_1k, clip)     = {_corr([r['avgsz'] for r in M], [r['pnl_per_1k'] for r in M]):+.2f}")
    print(f"  corr(pnl_per_1k, late)     = {_corr([r['frac_late'] for r in M], [r['pnl_per_1k'] for r in M]):+.2f}")


if __name__ == "__main__":
    main()
