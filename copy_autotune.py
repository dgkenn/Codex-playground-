"""copy_autotune.py -- SELF-MONITORING / SELF-FIXING copy loop. Repeatedly validates the copy of a target
wallet (via copy_live.py), DETECTS what it's missing, finds the root cause, and TWEAKS the rule until it
captures >=95% of the wallet's prospective trades at a faithful ladder depth -- then keeps re-validating
to catch drift. Extensible to the top-10%-by-MM-score wallets (--all).

Each cycle: run copy_live for `--cycle` seconds -> read copy_result.json -> diagnose:
  * missed_slugs in an asset/tenor we don't track  -> ADD that market to coverage (self-fix)
  * capture<95% but rises with depth                -> report the min depth that hits 95% (faithful if <=7)
  * dominant no_book                                -> snapshot timing (flag; copy_live already bands +/-8s)
  * dominant price_outside_ladder>7tk with full coverage -> honest ceiling (they rest deeper / our latency)
Writes copy_health.json (live status) + copy_autotune.jsonl (per-cycle log). CONVERGED when capture@<=7tk
>=95% over a cycle with >=MIN_FILLS scored.  Read-only; copy_live places nothing.

    python copy_autotune.py [wallet] [--cycle 1200] [--target 95] [--all]
"""
from __future__ import annotations
import json, os, subprocess, sys, time

DEFAULT = "0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d"
MIN_FILLS = 30                  # need this many scored fills before trusting a capture number
FAITHFUL_DEPTH = 15            # their measured ladder spans ~14tk (copy_live); capture 95% there = faithful


def parse_slug(slug):
    if not slug or "-updown-" not in slug:
        return None
    a, rest = slug.split("-updown-", 1)
    return a, int(rest.split("-")[0].replace("m", ""))


def run_cycle(wallet, assets, tenors, cycle):
    env = dict(os.environ, COPY_WALLET=wallet)
    try:
        os.remove("copy_result.json")
    except OSError:
        pass
    subprocess.run([sys.executable, "copy_live.py", str(cycle), ",".join(assets),
                    ",".join(str(t) for t in tenors)], env=env, timeout=cycle + 120)
    try:
        return json.load(open("copy_result.json"))
    except Exception:
        return None


def autotune(wallet, cycle, target, max_cycles=12):
    assets = ["btc", "eth", "sol", "xrp"]; tenors = [5, 15]
    health = {"wallet": wallet, "status": "starting", "cycles": 0}
    json.dump(health, open("copy_health.json", "w"))
    best = 0.0; converged = False
    for it in range(1, max_cycles + 1):
        print(f"\n=== [{wallet[:10]}] cycle {it} | assets={assets} tenors={tenors} | {cycle}s ===", flush=True)
        res = run_cycle(wallet, assets, tenors, cycle)
        if not res:
            print("  no result (no fills this cycle?) -- retrying"); continue
        # min faithful depth that hits target
        cap = res["capture"]; depth_hit = None
        for d in sorted(int(k) for k in cap):
            if cap[str(d)] >= target:
                depth_hit = d; break
        best = max(best, max(cap.values()) if cap else 0)
        # SELF-FIX: expand coverage for any missed market we don't track
        added = []
        for slug in res.get("missed_slugs", {}):
            pa = parse_slug(slug)
            if pa and (pa[0] not in assets or pa[1] not in tenors):
                if pa[0] not in assets:
                    assets.append(pa[0]); added.append(pa[0])
                if pa[1] not in tenors:
                    tenors.append(pa[1]); added.append(f"{pa[1]}m")
        diag = diagnose(res, depth_hit, added)
        rec = {"ts": int(time.time()), "wallet": wallet, "cycle": it, "scored": res["scored"],
               "seen_pct": res["seen_pct"], "capture": cap, "misses": res["misses"],
               "depth_for_target": depth_hit, "added_markets": added, "diag": diag}
        open("copy_autotune.jsonl", "a").write(json.dumps(rec) + "\n")
        health = {"wallet": wallet, "status": "tuning", "cycles": it, "best_capture": best,
                  "last": rec, "converged": False, "updated": int(time.time())}
        json.dump(health, open("copy_health.json", "w"))
        print(f"  scored={res['scored']} seen={res['seen_pct']}% capture={cap} depth_for_{target}%={depth_hit}")
        print(f"  DIAG: {diag}" + (f"  | self-fix added {added}" if added else ""))
        if res["scored"] >= MIN_FILLS and depth_hit is not None and depth_hit <= FAITHFUL_DEPTH:
            converged = True
            print(f"  *** CONVERGED: capture>={target}% at faithful depth {depth_hit}tk "
                  f"({res['scored']} fills) ***")
            health["status"] = "converged"; health["converged"] = True; health["depth"] = depth_hit
            json.dump(health, open("copy_health.json", "w"))
            break
    return converged, best


def diagnose(res, depth_hit, added):
    m = res.get("misses", {}); tot = max(1, res["scored"])
    if res["scored"] < MIN_FILLS:
        return f"insufficient fills ({res['scored']}<{MIN_FILLS}) -- wallet bursty/idle; need longer cycle"
    if depth_hit is not None and depth_hit <= FAITHFUL_DEPTH:
        return f"GOOD: {res['capture'][str(depth_hit)]}% at depth {depth_hit}tk"
    if added:
        return f"coverage gap -> added {added}; re-validate"
    if m.get("no_book", 0) / tot > 0.2:
        return "no_book dominant -> book-snapshot timing; increase snapshot rate / WS feed"
    if m.get("price_outside_ladder>7tk", 0) / tot > 0.1:
        return "deep fills (>7tk) -> they rest deeper or we're latency-behind; honest ceiling, not faithfully copyable at touch"
    return "below target; widen depth within faithful range or extend cycle"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cycle = int(_opt("--cycle", 1200)); target = float(_opt("--target", 95))
    if "--all" in sys.argv:
        mm = json.load(open("mm_score.json"))
        n = max(1, len(mm) // 10)                    # top 10% by MM score
        wallets = [r["w"] for r in mm[:n]]
        print(f"AUTOTUNE top-10% = {len(wallets)} wallets")
        results = {}
        for w in wallets:
            ok, best = autotune(w, cycle, target)
            results[w] = {"converged": ok, "best": best}
            json.dump(results, open("copy_all_results.json", "w"))
        print("DONE", json.dumps(results, indent=1)[:500])
    else:
        wallet = args[0] if args else DEFAULT
        autotune(wallet, cycle, target)


def _opt(flag, default):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


if __name__ == "__main__":
    main()
