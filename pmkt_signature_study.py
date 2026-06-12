"""pmkt_signature_study.py -- CROSS-VENUE test: does Polymarket informed-wallet flow carry the SAME
behavioral fingerprint our Kalshi toxic-flow detectors key on?

Reads the forward-collected BTC-5m trades+resolution (pmkt_5m_collect.py output) -- Polymarket serves no
bulk short-tenor history, so this study runs on accumulated forward data, NOT a retrospective.

The Kalshi signature to match (FINGERPRINT.md, informed_detectors.py / t35):
  - SIZE-toxicity: bigger takes = more informed (small +0.5c, 50+ contracts -2.2c at settle).
  - LATE-in-window concentration = the known informed population near expiry.
  - one-sided / aggressive flow (high VPIN, Kyle lambda) = informed.
Test: split Poly wallets into INFORMED (high realized directional accuracy) vs NOISE (~50%), compare
their trade SIZE, LATE-fraction, and directional CONVICTION. If informed wallets are bigger/later/more
one-sided -- matching Kalshi -- the signature transfers (external validation of our anonymous detectors).

    python pmkt_signature_study.py [out_dir]
"""
from __future__ import annotations
import gzip, json, os, sys, statistics as st
from collections import defaultdict

OUT = sys.argv[1] if len(sys.argv) > 1 else "gha_data"
TR = os.path.join(OUT, "pmkt_5m_trades.jsonl.gz")
RES = os.path.join(OUT, "pmkt_5m_resolution.jsonl")


def _slug_end(slug):
    try:
        return int(slug.rsplit("-", 1)[-1]) + 300
    except Exception:
        return 0


def main():
    if not os.path.exists(RES) or not os.path.exists(TR):
        print("No collected data yet (run pmkt_5m_collect.py first). Need both:")
        print(f"  trades: {TR}  resolution: {RES}")
        return
    winners = {}
    for ln in open(RES):
        try:
            d = json.loads(ln); winners[d["conditionId"]] = int(d["winner_idx"])
        except Exception:
            pass
    trades = [json.loads(l) for l in gzip.open(TR, "rt")]
    trades = [t for t in trades if t["cid"] in winners and t.get("oidx") is not None]

    n_markets = len(winners)
    n_resolved_traded = len({t["cid"] for t in trades})
    print("=" * 64)
    print("POLYMARKET BTC-5M INFORMED-WALLET SIGNATURE STUDY")
    print("=" * 64)
    print(f"\n[SCOPE] resolved windows={n_markets}  with-trades={n_resolved_traded}  "
          f"scored trades={len(trades)}  wallets={len({t['wallet'] for t in trades})}")
    if len(trades) < 400:
        print("  ** THIN: <400 scored trades -- treat as preliminary; let the collector run longer. **")

    # per-wallet aggregation
    W = defaultdict(lambda: dict(n=0, correct=0, mkts=set(), sizes=[], late=0, buys=0))
    for t in trades:
        w = W[t["wallet"]]
        win = winners[t["cid"]]
        buy = (t["side"] == "BUY")
        correct = (buy and int(t["oidx"]) == win) or ((not buy) and int(t["oidx"]) != win)
        w["n"] += 1
        w["correct"] += int(correct)
        w["mkts"].add(t["cid"])
        try:
            w["sizes"].append(float(t["size"]))
        except Exception:
            pass
        w["buys"] += int(buy)
        end = _slug_end(t["slug"])
        if end and t.get("ts") and float(t["ts"]) >= end - 60:   # last 60s of a 300s window
            w["late"] += 1

    def feat(w):
        acc = w["correct"] / w["n"]
        sizes = w["sizes"] or [0.0]
        return dict(acc=acc, n=w["n"], mkts=len(w["mkts"]),
                    msize=st.mean(sizes), medsize=st.median(sizes),
                    late=w["late"] / w["n"], conv=max(w["buys"], w["n"] - w["buys"]) / w["n"])

    feats = {wl: feat(w) for wl, w in W.items()}
    # buckets: meaningful sample only
    meaningful = {wl: f for wl, f in feats.items() if f["n"] >= 8 or f["mkts"] >= 4}
    informed = {wl: f for wl, f in meaningful.items() if f["acc"] >= 0.58}
    noise = {wl: f for wl, f in meaningful.items() if 0.46 <= f["acc"] <= 0.54}
    print(f"\n[BUCKETS] meaningful(n>=8 or mkts>=4)={len(meaningful)}  "
          f"informed(acc>=58%)={len(informed)}  noise(46-54%)={len(noise)}")

    def agg(group, key):
        vals = [f[key] for f in group.values()]
        return st.mean(vals) if vals else float("nan")

    if informed and noise:
        print("\n[SIGNATURE] informed vs noise -- does it MATCH the Kalshi fingerprint?")
        print(f"  {'feature':16s} {'informed':>10s} {'noise':>10s} {'Kalshi-says':>14s}  match")
        rows = [("mean size", "msize", "bigger=informed", lambda i, n: i > n * 1.10),
                ("median size", "medsize", "bigger=informed", lambda i, n: i > n * 1.10),
                ("late-60s frac", "late", "later=informed", lambda i, n: i > n * 1.10),
                ("conviction", "conv", "one-sided=infrmd", lambda i, n: i > n * 1.05)]
        matches = 0
        for label, key, says, ok in rows:
            iv, nv = agg(informed, key), agg(noise, key)
            m = ok(iv, nv); matches += int(m)
            print(f"  {label:16s} {iv:>10.3f} {nv:>10.3f} {says:>14s}  {'YES' if m else 'no'}")
        print(f"\n[VERDICT] {matches}/4 Kalshi signatures replicate on Polymarket informed wallets.")
        if len(meaningful) < 40:
            print("  Sample still small -- suggestive, not conclusive. Keep collecting.")
        elif matches >= 3:
            print("  STRONG cross-venue match: informed Poly flow looks like Kalshi toxic flow ->")
            print("  external validation of the size/timing detectors; consider a refined size/late")
            print("  feature in the Kalshi toxicity gate. Worth a short A/B follow-up.")
        elif matches <= 1:
            print("  NO match: informed wallets are NOT distinguished by size/timing/conviction ->")
            print("  the Polymarket->Kalshi behavioral transfer is dead; drop the line, keep t35.")
        else:
            print("  PARTIAL match: some features replicate. Record which; do not over-invest.")
    else:
        print("\n[VERDICT] Not enough resolved data to populate both buckets yet. Let the collector run.")
        print("  (informed and/or noise bucket empty -- need more resolved windows.)")


if __name__ == "__main__":
    main()
