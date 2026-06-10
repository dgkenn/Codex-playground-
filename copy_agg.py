"""copy_agg.py -- pool the overnight copy-validation runs (copy_results/*.json from the gha-data branch,
synced via sync_data.sh) into ONE stable capture-vs-depth curve + convergence verdict. Each run reports
capture% per depth over its own fills; we re-weight by each run's fill count to get the true pooled rate.

    python copy_agg.py        # after: git fetch origin gha-data && git checkout origin/gha-data -- copy_results/
"""
from __future__ import annotations
import glob, json, collections

DEPTHS = [1, 2, 3, 5, 7]
TARGET = 95.0
FAITHFUL = 7


def main():
    files = glob.glob("copy_results/*.json") or glob.glob("copy_result*.json")
    if not files:
        print("no copy_results/*.json (sync gha-data first)"); return
    by_wallet = collections.defaultdict(lambda: {"scored": 0, "actual": 0, "cap": {d: 0.0 for d in DEPTHS},
                                                 "misses": collections.Counter(), "runs": 0})
    for f in files:
        try:
            r = json.load(open(f))
        except Exception:
            continue
        w = r.get("wallet", "?"); a = by_wallet[w]; n = r.get("scored", 0)
        a["scored"] += n; a["actual"] += r.get("actual", 0); a["runs"] += 1
        for d in DEPTHS:
            a["cap"][d] += r.get("capture", {}).get(str(d), 0.0) / 100.0 * n   # back to counts
        for k, v in r.get("misses", {}).items():
            a["misses"][k] += v
    for w, a in sorted(by_wallet.items(), key=lambda kv: -kv[1]["scored"]):
        n = max(1, a["scored"])
        curve = {d: round(100 * a["cap"][d] / n, 1) for d in DEPTHS}
        depth_hit = next((d for d in DEPTHS if curve[d] >= TARGET), None)
        seen = round(100 * a["scored"] / max(1, a["actual"]), 1) if a["actual"] else None
        verdict = (f"CONVERGED: {curve[depth_hit]}% at depth {depth_hit}tk" if depth_hit and depth_hit <= FAITHFUL
                   else f"below {TARGET}% within {FAITHFUL}tk -> best {max(curve.values())}%")
        print(f"\n{w[:12]} | runs={a['runs']} fills={a['scored']} seen={seen}%")
        print(f"  capture curve: {curve}")
        print(f"  misses: {dict(a['misses'])}")
        print(f"  => {verdict}")


if __name__ == "__main__":
    main()
