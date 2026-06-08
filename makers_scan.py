"""makers_scan.py -- find & rank the most profitable wallets on the 15-min crypto markets, classify
market-MAKERS vs directional takers, from the wallet-attributed data-api trade tape (no auth, no keys).

For each closed {asset}-updown-{tenor}m window we pull every trade (proxyWallet, side, size, price,
outcome) + resolution, then per (wallet, market) compute cashflow + inventory -> settled P&L. Per
wallet across markets: total/risk-adjusted P&L, two-sidedness (maker proxy), clip size, inventory
carried, intra-window timing. The tape shows BOTH sides of fills (validated: ~50/50 wallets exist) so
makers are visible; but it has NO maker/taker flag, so P&L is GROSS of fees/rebates (a maker's real
P&L is +rebate, a taker's -fee) -- we flag the maker proxy via two-sidedness. Caches raw trades to
makers_trades.jsonl so re-runs are cheap. Pure stdlib (no pandas).

    python makers_scan.py [n_windows] [assets]      # e.g. python makers_scan.py 150 btc,eth
"""
from __future__ import annotations
import collections, json, math, os, sys, time
import requests

G = "https://gamma-api.polymarket.com"
D = "https://data-api.polymarket.com"
TENORS = (15,)
CACHE = "makers_trades.jsonl"


def fetch_trades(sess, cid):
    out, off = [], 0
    while True:
        j = None
        for _ in range(2):
            try:
                j = sess.get(D + "/trades", params={"market": cid, "limit": 500, "offset": off}, timeout=25).json()
                break
            except Exception:
                time.sleep(1)
        if not isinstance(j, list) or not j:
            break
        out += j; off += 500
        if len(j) < 500 or off > 12000:
            break
    return out


def collect(n_windows, assets):
    """Yield (asset,tenor,ws,res_up,cid, trades[]) per closed market, using/refreshing the JSONL cache."""
    done = set()
    if os.path.exists(CACHE):
        for ln in open(CACHE):
            try:
                done.add(json.loads(ln)["cid"])
            except Exception:
                pass
    sess = requests.Session()
    fh = open(CACHE, "a")
    now = int(time.time())
    markets = []
    for asset in assets:
        for tmin in TENORS:
            win = tmin * 60
            for k in range(1, n_windows + 1):
                markets.append((asset, tmin, now - (now % win) - win * k))
    for i, (asset, tmin, ws) in enumerate(markets):
        slug = f"{asset}-updown-{tmin}m-{ws}"
        try:
            ev = sess.get(G + "/events", params={"slug": slug}, timeout=15).json()
        except Exception:
            continue
        if not ev:
            continue
        m = ev[0]["markets"][0]
        if not m.get("closed"):
            continue
        cid = m["conditionId"]
        if cid in done:
            continue
        op = m.get("outcomePrices"); op = json.loads(op) if isinstance(op, str) else op
        if not op:
            continue
        res_up = 1.0 if float(op[0]) > 0.5 else 0.0
        tt = fetch_trades(sess, cid)
        rec = {"asset": asset, "tenor": tmin, "ws": ws, "res_up": res_up, "cid": cid,
               "trades": [(t["proxyWallet"], t["side"], float(t["size"]), float(t["price"]),
                           int(t.get("outcomeIndex", 0)), int(t["timestamp"])) for t in tt]}
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(markets)} markets scanned", flush=True)
    fh.close()


def _std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def analyze(assets):
    assets = set(assets)
    W = collections.defaultdict(lambda: {"pnls": [], "vol": 0.0, "trades": 0, "buys": 0, "sells": 0,
                                         "deltas": [], "sizes": [], "taus": [], "late": []})
    nmkt = 0
    for ln in open(CACHE):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r["asset"] not in assets:
            continue
        res = r["res_up"]; ws = r["ws"]; win = r["tenor"] * 60
        nmkt += 1
        perm = collections.defaultdict(lambda: {"cash": 0.0, "up": 0.0, "dn": 0.0, "b": 0, "s": 0,
                                                "vol": 0.0, "sz": [], "tau": []})
        for w, side, sz, pr, oi, ts in r["trades"]:
            d = perm[w]; buy = side == "BUY"
            d["cash"] += (-pr * sz if buy else pr * sz)
            if oi == 0:
                d["up"] += sz if buy else -sz
            else:
                d["dn"] += sz if buy else -sz
            d["b"] += buy; d["s"] += not buy; d["vol"] += pr * sz; d["sz"].append(sz)
            d["tau"].append(max(0, win - (ts - ws)))
        for w, d in perm.items():
            pnl = d["cash"] + d["up"] * res + d["dn"] * (1 - res)
            a = W[w]
            a["pnls"].append(pnl); a["vol"] += d["vol"]; a["trades"] += d["b"] + d["s"]
            a["buys"] += d["b"]; a["sells"] += d["s"]; a["deltas"].append(abs(d["up"] - d["dn"]))
            a["sizes"] += d["sz"]; a["taus"] += d["tau"]
            a["late"].append(sum(1 for x in d["tau"] if x < 120) / max(1, len(d["tau"])))
    out = []
    for w, a in W.items():
        mkts = len(a["pnls"]); pnl = sum(a["pnls"]); mean = pnl / mkts
        sd = _std(a["pnls"]); t = mean / (sd / math.sqrt(mkts)) if sd > 0 else float("nan")
        tot = a["buys"] + a["sells"]
        out.append({
            "wallet": w, "pnl": pnl, "t_stat": t, "vol": a["vol"], "mkts": mkts, "trades": a["trades"],
            "twosided": min(a["buys"], a["sells"]) / tot if tot else 0.0,
            "avgsz": sum(a["sizes"]) / len(a["sizes"]) if a["sizes"] else 0.0,
            "avg_delta": sum(a["deltas"]) / mkts,
            "pnl_per_1k": 1000 * pnl / a["vol"] if a["vol"] else 0.0,
            "frac_late": sum(a["late"]) / mkts,
            "mean_tau": sum(a["taus"]) / len(a["taus"]) if a["taus"] else 0.0,
        })
    return out, nmkt


def is_maker(r):
    return r["twosided"] > 0.30 and r["mkts"] >= 5 and r["avgsz"] < 60


def _print(rows, n, title):
    print(f"\n=== {title} ===")
    print(f"{'wallet':>14}{'pnl':>8}{'t':>6}{'/1k':>6}{'vol':>8}{'mkts':>5}{'trd':>6}{'2sided':>7}"
          f"{'avgsz':>6}{'Δinv':>6}{'late':>6}")
    for r in rows[:n]:
        print(f"{r['wallet'][:12]:>14}{r['pnl']:>+8.0f}{r['t_stat']:>6.1f}{r['pnl_per_1k']:>+6.1f}"
              f"{r['vol']:>8.0f}{r['mkts']:>5}{r['trades']:>6}{r['twosided']:>7.2f}{r['avgsz']:>6.0f}"
              f"{r['avg_delta']:>6.0f}{r['frac_late']:>6.2f}")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    assets = sys.argv[2].split(",") if len(sys.argv) > 2 else ["btc"]
    collect(n, assets)
    rows, nmkt = analyze(assets)
    print(f"\nscanned {nmkt} markets, {len(rows)} wallets ({','.join(assets)})")
    makers = [r for r in rows if is_maker(r)]
    _print(sorted(makers, key=lambda r: -r["pnl"]), 25, "top 25 MAKERS by total P&L")
    ra = [r for r in makers if r["mkts"] >= 8 and r["pnl"] > 0 and r["t_stat"] == r["t_stat"]]
    _print(sorted(ra, key=lambda r: -r["t_stat"]), 25, "top 25 MAKERS by RISK-ADJUSTED (t-stat per-market P&L)")
    di = [r for r in rows if r["twosided"] < 0.12 and r["mkts"] >= 5]
    _print(sorted(di, key=lambda r: -r["pnl"]), 10, "contrast: top DIRECTIONAL (one-sided) earners")
    json.dump(rows, open("makers_agg.json", "w"))
    print(f"\nwrote makers_agg.json. P&L is GROSS of fees/rebates (no maker/taker flag in the tape); "
          f"makers' real P&L is +rebate, takers' -fee. 2sided = maker proxy; Δinv = avg |inventory| carried to settle.")


if __name__ == "__main__":
    main()
