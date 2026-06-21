#!/usr/bin/env python3
"""kalshi_longshot_audit.py -- read the live bot's decision audit log and DIAGNOSE it by
reconciling each decision against the eventual market outcome (the "compare to the collector"
ask). Answers: are my gates throwing away winners? are my placed positions actually winning?

Input: the JSONL written by kalshi_longshot_bot.py (LONGSHOT_AUDIT path). For every decided
ticker that has since SETTLED, we fetch its result (rate-limited public API) and score:
  - PLACE  -> win if result==no (we sold the YES longshot), loss if result==yes
  - SKIP(flow_toxic) -> CORRECT avoid if result==yes (longshot hit, we dodged a loss),
                        MISSED winner if result==no (we skipped a position that would have won)
  - other SKIPs (caps) scored the same so you can see opportunity cost of the caps.

    python kalshi_longshot_audit.py <audit.jsonl>
"""
import sys, json, time, urllib.request
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"


def get(path):
    for a in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, headers={"User-Agent": "r"}), timeout=20))
            time.sleep(0.35)
            return r
        except Exception:
            time.sleep(1.0 * (a + 1))
    return {}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "longshot_audit.jsonl"
    recs = [json.loads(l) for l in open(path) if l.strip()]
    decisions = [r for r in recs if r.get("type") != "scan_summary"]
    summaries = [r for r in recs if r.get("type") == "scan_summary"]

    print("=" * 64)
    print(f"LONGSHOT DECISION AUDIT  ({len(decisions)} decisions across {len(summaries)} runs)")
    print("=" * 64)

    # 1. decision breakdown by reason
    by_reason = defaultdict(int)
    for r in decisions:
        by_reason[f"{r['decision']}:{r['reason']}"] += 1
    print("\nDecisions by reason:")
    for k, v in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {k:>28}: {v}")

    # 2. scan-stage rejects (aggregated)
    agg = defaultdict(int)
    for s in summaries:
        for k, v in (s.get("scan_stats") or {}).items():
            agg[k] += v
    if agg:
        print("\nScan-stage rejects (aggregated): " + ", ".join(f"{k}={v}" for k, v in agg.items()))

    # 3. reconcile decisions against settled outcomes (unique tickers, rate-limited)
    tickers = {}
    for r in decisions:
        tickers.setdefault(r["ticker"], r)        # one decision/ticker (latest wins ok for diagnosis)
    print(f"\nReconciling {len(tickers)} unique tickers against settlement (rate-limited)...")
    scored = defaultdict(lambda: [0, 0, 0])       # bucket -> [settled, win/correct, loss/missed]
    n = 0
    for tk, r in tickers.items():
        m = (get(f"/markets/{tk}").get("market") or {})
        res = (m.get("result") or "").lower()
        if res not in ("yes", "no"):
            continue                              # not settled yet
        n += 1
        dec, reason = r["decision"], r["reason"]
        bucket = "PLACED" if dec in ("place",) else f"SKIP:{reason}"
        scored[bucket][0] += 1
        if dec == "place":
            # we sold the YES longshot (bought NO): win if result==no
            scored[bucket][1 if res == "no" else 2] += 1
        else:
            # skip: "correct avoid" if the longshot HIT (res==yes); "missed winner" if res==no
            scored[bucket][1 if res == "yes" else 2] += 1
    print(f"  settled: {n}\n")
    print(f"{'bucket':>22} {'settled':>8} {'good':>6} {'bad':>6}  interpretation")
    for b, (s, g, bad) in sorted(scored.items(), key=lambda x: -x[1][0]):
        if b == "PLACED":
            interp = f"win%={g/s:.2f} (NO-resolved); each loss ~ -collateral"
        else:
            interp = f"avoided-loss%={g/s:.2f}; bad={bad} = winners you SKIPPED"
        print(f"{b:>22} {s:>8} {g:>6} {bad:>6}  {interp}")
    print("\nDIAGNOSE: for PLACED, win% should be high (longshots mostly resolve NO). For SKIP:flow_toxic,")
    print("a high 'bad' (missed winners) means the toxicity gate is TOO AGGRESSIVE -> loosen MAX_TAKE/")
    print("MAX_FLOWIMB. Compare PLACED win% to the band's expected (~85-95%); a gap flags adverse selection")
    print("or a book-read bug (cross-check the audit's no_bid/mid vs the collector's snapshot for that ticker).")


if __name__ == "__main__":
    main()
