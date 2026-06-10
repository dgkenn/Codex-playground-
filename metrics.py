"""metrics.py -- the full risk/profitability/consistency/execution suite for the maker (beyond Sharpe).

Reconstructs each gate's per-(asset,ws) window net from the ungated fill tape (combo_lab style) so gates
are directly comparable, then reports the reviewer's metric suite. IMPORTANT caveats baked in:
 - Unit of P&L = a WINDOW (one market we made), not a "trade" -- a maker has no discrete win/loss trade;
   we hold balanced sets to resolution. So Win Rate / Profit Factor are per-window.
 - net is rebate-inclusive and mo_res-based (the realized settle P&L), so its variance INCLUDES the
   directional resolution swing on residual inventory -- real risk for a hold-to-resolution book.
 - These are PAPER/shadow numbers at front-of-queue (sim fills at q~0) -> upper bound; live will haircut.
 - Maker ratio = 100% by construction (post-only + would_cross guard). Annualizing 15-min HFT P&L is
   misleading, so we report per-window + portfolio-path risk, not a headline CAGR.

    python metrics.py
"""
from __future__ import annotations
import glob, json, re, math, collections, statistics

try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
MICRO_MARGIN = 0.002


def load():
    rows = []
    for fp in glob.glob("gha_data/fills_*.jsonl"):
        m = re.search(r"fills_([a-z]+)\d+m_", fp); asset = m.group(1) if m else "btc"
        for ln in open(fp):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                r["_a"] = asset; rows.append(r)
    return rows


def toxv(r):
    t = r.get("tox")
    if t is not None: return t
    mp = r.get("micro"); return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


def gate(name):
    if name == "micro":   return lambda r: toxv(r) <= 0.0
    if name == "ufat":    return lambda r: toxv(r) <= MICRO_MARGIN * 4 * (r.get("mid") or r["p"]) * (1 - (r.get("mid") or r["p"]))
    if name == "ufat_band":
        def k(r):
            p = r.get("mid") or r["p"]
            if 0.30 <= p < 0.55: return False
            return toxv(r) <= MICRO_MARGIN * 4 * p * (1 - p)
        return k
    return lambda r: True


def window_nets(rows, keep):
    """per-(asset,ws) net + notional of kept fills."""
    net = collections.defaultdict(float); notl = collections.defaultdict(float)
    for r in rows:
        k = (r["_a"], r["ws"])
        net.setdefault(k, 0.0); notl.setdefault(k, 0.0)
        if keep(r):
            net[k] += r["mo_res"] * r["sz"] + REB(r["p"]) * r["sz"]
            notl[k] += r["sz"] * r["p"]
    return net, notl


def portfolio_path(net):
    """sum nets across assets per ws, chronological -> equity path (running 4-market book)."""
    byws = collections.defaultdict(float)
    for (a, ws), v in net.items():
        byws[ws] += v
    return [byws[ws] for ws in sorted(byws)]


def mdd(equity):
    cum = 0.0; peak = 0.0; worst = 0.0
    for x in equity:
        cum += x; peak = max(peak, cum); worst = min(worst, cum - peak)
    return -worst, cum                       # (max drawdown $, final cum $)


def suite(rows, name):
    keep = gate(name)
    net, notl = window_nets(rows, keep)
    xs = list(net.values()); n = len(xs)
    pos = [x for x in xs if x > 0]; neg = [x for x in xs if x < 0]
    mean = sum(xs) / n; sd = statistics.pstdev(xs)
    dd = statistics.pstdev([min(x, 0.0) for x in xs])           # downside dev (vs 0)
    sharpe = mean / sd if sd > 0 else float("nan")
    sortino = mean / dd if dd > 0 else float("nan")
    path = portfolio_path(net); m_dd, final = mdd(path)
    calmar = (final / m_dd) if m_dd > 0 else float("nan")       # total return / MDD (proxy)
    pf = (sum(pos) / abs(sum(neg))) if neg else float("inf")
    wr = 100 * len(pos) / n
    wl = (statistics.mean(pos) / abs(statistics.mean(neg))) if pos and neg else float("nan")
    tot_net = sum(xs); tot_notl = sum(notl.values())
    edge_bps = 1e4 * tot_net / tot_notl if tot_notl else float("nan")
    kept = sum(1 for r in rows if keep(r))
    return dict(name=name, n=n, mean=mean, sharpe=sharpe, t=sharpe * math.sqrt(n),
                sortino=sortino, mdd=m_dd, final=final, calmar=calmar, pf=pf, wr=wr, wl=wl,
                edge_bps=edge_bps, keptpct=100 * kept / len(rows))


def main():
    rows = load()
    if not rows:
        print("no data: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/"); return
    print(f"{len(rows)} fills | unit = one (asset,window); PAPER/front-of-queue (upper bound); maker ratio = 100%\n")
    hdr = ["gate", "win/win$", "Sharpe(t)", "Sortino", "MDD$", "Calmar", "ProfitF", "Win%", "W/L", "edge_bps", "kept%"]
    print("  ".join(f"{h:>9}" for h in hdr))
    for name in ("micro", "ufat", "ufat_band"):
        s = suite(rows, name)
        print(f"{s['name']:>9} {s['mean']:>+9.2f} {s['t']:>9.1f} {s['sortino']:>9.2f} {s['mdd']:>9.1f} "
              f"{s['calmar']:>9.1f} {s['pf']:>9.2f} {s['wr']:>8.0f}% {s['wl']:>9.2f} {s['edge_bps']:>9.1f} {s['keptpct']:>8.0f}%")
    print("\nedge_bps = net per $ traded (x1e4). Sharpe shown as t (per-window Sharpe x sqrt n); annualized")
    print("Sharpe would be per-window x sqrt(~140k windows/yr) -- large but misleading for a thin HFT edge.")
    print("Calmar = total paper net / max-drawdown of the running 4-market equity path (return-per-worst-loss).")


if __name__ == "__main__":
    main()
