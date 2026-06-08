"""copy_offline.py -- placement-aware capture for ALL top-10% wallets from the CACHED tape (no waiting on
bursty live fills). makers_trades.jsonl holds EVERY wallet's trades per market, so we reconstruct each
market's consensus price path (all-trades VWAP in P(Up) space) and, for each target wallet's fill, ask:
did the consensus come within D ticks of the fill price at some point in the prior ~30s? -- i.e. would a
follow-the-touch ladder placed in that window have had an order there (it fills when price returns).

Caveat (honest): the consensus path ~ the MID, not the exact best bid/ask, so depths here are vs mid
(a resting maker sits ~half-spread off mid). rangeW = the 30s consensus swing; if rangeW>=D the capture
is market-swing-inflated, not a faithful tight ladder. python copy_offline.py
"""
from __future__ import annotations
import collections, json

TICK = 0.01; DEPTHS = [2, 3, 5, 7, 10, 14, 20]; WIN = 30


def main():
    mm = json.load(open("mm_score.json")); targets = {r["w"] for r in mm[:max(1, len(mm) // 10)]}
    order = [r["w"] for r in mm[:max(1, len(mm) // 10)]]
    # per market: all trades (ts, pup) for the consensus path + per-target fills (ts, pup)
    mkt_path = collections.defaultdict(list)
    tgt_fills = collections.defaultdict(list)        # wallet -> [(cid, ts, pup)]
    for ln in open("makers_trades.jsonl"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        cid = r["cid"]
        for w, side, sz, pr, oi, ts in r["trades"]:
            pup = pr if oi == 0 else 1 - pr
            if w not in targets:                       # consensus = the REST of the market (no self/peer capture)
                mkt_path[cid].append((ts, pup))
            else:
                tgt_fills[w].append((cid, ts, pup))
    for cid in mkt_path:
        mkt_path[cid].sort()
    print(f"{'wallet':>12}{'fills':>6}{'inst@3':>7}{'PLACE@7':>8}{'PLACE@14':>9}{'PLACE@20':>9}{'rangeW':>7}{'verdict':>9}")
    ok = 0; seen = 0
    rows = []
    for w in order:
        fills = tgt_fills.get(w, [])
        if len(fills) < 20:
            rows.append((w, len(fills), None)); continue
        seen += 1
        capd = {d: 0 for d in DEPTHS}; inst3 = 0; ranges = []
        for cid, ts, pup in fills:
            path = mkt_path[cid]
            near = [pp for (tt, pp) in path if ts - WIN <= tt <= ts + 2]
            if not near:
                continue
            lo, hi = min(near), max(near); ranges.append((hi - lo) / TICK)
            # nearest consensus point (instantaneous proxy)
            inst = min(abs(pp - pup) for (tt, pp) in path if abs(tt - ts) <= 5) if any(abs(tt - ts) <= 5 for (tt, _) in path) else 99
            if inst <= 3 * TICK + 1e-9:
                inst3 += 1
            for d in DEPTHS:
                if lo - d * TICK - 1e-9 <= pup <= hi + d * TICK + 1e-9:   # touch within D at some point
                    capd[d] += 1
        n = len(fills)
        rangeW = sorted(ranges)[len(ranges) // 2] if ranges else 0
        p7, p14, p20 = 100 * capd[7] / n, 100 * capd[14] / n, 100 * capd[20] / n
        faithful = p20 >= 95 and rangeW < 20
        if faithful:
            ok += 1
        rows.append((w, n, (100 * inst3 / n, p7, p14, p20, rangeW, faithful)))
    for w, n, m in rows:
        if m is None:
            print(f"{w[:10]:>12}{n:>6}   (need >=20 fills; have {n})")
        else:
            i3, p7, p14, p20, rw, f = m
            print(f"{w[:10]:>12}{n:>6}{i3:>6.0f}%{p7:>7.0f}%{p14:>8.0f}%{p20:>8.0f}%{rw:>7.0f}{('OK' if f else 'wide/<95'):>9}")
    print(f"\n{ok}/{seen} wallets (>=20 cached fills) reach >=95% placement capture at depth<=20 with a "
          f"non-inflated (<20tk) consensus swing. Depths are vs MID (consensus); a maker rests ~half-spread "
          f"off, so add ~1tk. This evaluates ALL top-10% from cache; live WS validation (copy_live_multi) "
          f"confirms vs the real best-bid/ask touch.")


if __name__ == "__main__":
    main()
