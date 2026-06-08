"""wallet_deepdive.py -- forensic analysis of ONE wallet to reverse-engineer its edge/exploit.
Default target: 0x20d2309cd9... (t=4.9 outlier, #1 maker on BTC AND ETH, +3.5%/$ GROSS, ~BTC-neutral).

Pulls the wallet's full trade history (data-api ?user=, paginated) and tests, resolution-INDEPENDENTLY,
the candidate edges:
  BOX/complete-set: does it buy Up+Down at price-sum < 1 (then merge -> risk-free (1-sum)/set) or sell
    both at sum > 1? Per market: matched-set volume + locked premium. This is the prime "exploit" suspect.
  SPREAD capture: does it buy BELOW and sell ABOVE the market's own VWAP (passive MM edge)? per-token edge.
  CROSS-ASSET breadth: how many assets/markets it runs concurrently (diversification -> high Sharpe).
  CADENCE: inter-trade intervals, trades/hr (HFT?), intra-window timing.
  INVENTORY: does it flatten/merge (risk-free) or hold to resolution (directional)?
    python wallet_deepdive.py [wallet_prefix_or_full] [max_trades]
"""
from __future__ import annotations
import collections, json, statistics, sys, time
import requests

D = "https://data-api.polymarket.com"
G = "https://gamma-api.polymarket.com"
TARGET = "0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d"


def pull_user(sess, w, maxn):
    out, off = [], 0
    while len(out) < maxn:
        j = sess.get(D + "/trades", params={"user": w, "limit": 500, "offset": off}, timeout=25).json()
        if not isinstance(j, list) or not j:
            break
        out += j; off += 500
        if len(j) < 500:
            break
    return out


def main():
    w = sys.argv[1] if len(sys.argv) > 1 else TARGET
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    sess = requests.Session()
    if not w.startswith("0x") or len(w) < 42:                 # resolve prefix -> full address
        now = int(time.time())
        for k in range(1, 40):
            ws = now - (now % 900) - 900 * k
            ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{ws}"}, timeout=15).json()
            if not ev:
                continue
            for t in sess.get(D + "/trades", params={"market": ev[0]["markets"][0]["conditionId"], "limit": 500}, timeout=20).json():
                if t["proxyWallet"].startswith(w):
                    w = t["proxyWallet"]; break
            if len(w) >= 42:
                break
    print(f"target {w}")
    tr = pull_user(sess, w, maxn)
    print(f"pulled {len(tr)} trades; span {round((tr[0]['timestamp']-tr[-1]['timestamp'])/3600,1)}h "
          f"=> {round(len(tr)/max(1e-9,(tr[0]['timestamp']-tr[-1]['timestamp'])/3600))} trades/hr\n")

    # group by market (slug = one window)
    mkts = collections.defaultdict(list)
    for t in tr:
        mkts[t["slug"]].append(t)
    assets = collections.Counter(s.rsplit("-updown-", 1)[0] for s in mkts)
    print(f"markets={len(mkts)} across assets: {dict(assets)}")

    # CADENCE + CONCURRENCY
    ts = sorted(t["timestamp"] for t in tr)
    gaps = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
    print(f"inter-trade gap: median={statistics.median(gaps)}s  p10={sorted(gaps)[len(gaps)//10]}s  "
          f"(<=1s: {100*sum(g<=1 for g in gaps)/len(gaps):.0f}% -> HFT if high)")
    # how many distinct markets active within any 60s -> concurrency
    win_conc = []
    arr = sorted(tr, key=lambda t: t["timestamp"])
    j = 0; from_i = 0
    for i, t in enumerate(arr):
        while arr[i]["timestamp"] - arr[from_i]["timestamp"] > 60:
            from_i += 1
        win_conc.append(len({arr[k]["slug"] for k in range(from_i, i + 1)}))
    print(f"concurrent markets (60s window): median={statistics.median(win_conc)} max={max(win_conc)}\n")

    # BOX / complete-set + SPREAD, per market
    box_buy, box_sell, matched_prem, flat_ratio, spread_edges = [], [], [], [], []
    both_side_mkts = 0
    for slug, T in mkts.items():
        up = [t for t in T if t.get("outcomeIndex", 0) == 0]
        dn = [t for t in T if t.get("outcomeIndex", 0) == 1]

        def vwap(ts_, side):
            x = [(float(t["price"]), float(t["size"])) for t in ts_ if t["side"] == side]
            v = sum(s for _, s in x)
            return (sum(p * s for p, s in x) / v if v else None), v
        ub, ubv = vwap(up, "BUY"); db, dbv = vwap(dn, "BUY")
        us, usv = vwap(up, "SELL"); ds, dsv = vwap(dn, "SELL")
        if ub is not None and db is not None:
            box_buy.append(1 - (ub + db))                    # >0 = bought a $1 set for < $1 (risk-free if merged)
            matched_prem.append((min(ubv, dbv), 1 - (ub + db)))
        if us is not None and ds is not None:
            box_sell.append((us + ds) - 1)                   # >0 = sold a $1 set for > $1
        if (ubv + usv) > 0 and (dbv + dsv) > 0:
            both_side_mkts += 1
        # spread capture vs the market's own VWAP (all participants) for each token
        for ts_, oi in ((up, 0), (dn, 1)):
            allv = sum(float(t["size"]) for t in ts_)
            if allv == 0:
                continue
            mvwap = sum(float(t["price"]) * float(t["size"]) for t in ts_) / allv
            for t in ts_:
                edge = (mvwap - float(t["price"])) if t["side"] == "BUY" else (float(t["price"]) - mvwap)
                spread_edges.append(edge)                    # >0 = bought below / sold above the consensus
        # inventory flatten: net signed exposure end vs gross
        net = sum((float(t["size"]) if t["side"] == "BUY" else -float(t["size"])) * (1 if t.get("outcomeIndex", 0) == 0 else -1) for t in T)
        gross = sum(float(t["size"]) for t in T)
        if gross:
            flat_ratio.append(abs(net) / gross)

    def desc(xs):
        return f"mean={statistics.mean(xs):+.4f} median={statistics.median(xs):+.4f} %>0={100*sum(x>0 for x in xs)/len(xs):.0f}% n={len(xs)}" if xs else "n=0"
    print("BOX / COMPLETE-SET (the prime exploit suspect):")
    print(f"  buy-both premium 1-(vwap_up_buy+vwap_dn_buy): {desc(box_buy)}")
    print(f"  sell-both premium (vwap_up_sell+vwap_dn_sell)-1: {desc(box_sell)}")
    if matched_prem:
        wsum = sum(m * p for m, p in matched_prem); msum = sum(m for m, _ in matched_prem)
        print(f"  matched-set-volume-weighted buy premium: {wsum/msum:+.4f}/set over {msum:.0f} matched sets")
    print(f"  markets where it quotes BOTH sides of a token: {both_side_mkts}/{len(mkts)}")
    print(f"\nSPREAD capture vs market VWAP (buy-below/sell-above): {desc(spread_edges)}")
    print(f"INVENTORY flatten ratio |net|/gross (0=flat/merged, 1=directional hold): "
          f"median={statistics.median(flat_ratio):.2f} mean={statistics.mean(flat_ratio):.2f}" if flat_ratio else "n/a")


if __name__ == "__main__":
    main()
