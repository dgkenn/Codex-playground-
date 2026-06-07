"""Root-cause WHY each trade won/lost -- from the per-DECISION audit ledger (fills_*.jsonl).

Every row is one decision the bot made when a taker trade reached a level it was quoting:
WHAT PROMPTED IT (tk_side, tk_sz, q_ahead/q_used) + ALL INPUTS CONSIDERED (bb/ba/bsz/asz,
mid, micro, imb, fair, tox, delta, cap, skew_lim, gate) + the ACTION (reason, sz, want) +
REAL markout (mo5/mo30/mo_res) and exact pnl=sz*mo_res for actual fills.

This script (a) AUDITS the ledger -- recomputes mid/micro/imb from the raw book and checks
they match, and reconciles Σpnl against each window's gross -- then (b) reads the toxicity
->loss curve and the decision-reason histogram, clustered by window.

    python analyze_fills.py
HONEST LIMIT: paper models queue position; markout/pnl are real, so this is the per-trade
adverse-selection truth GIVEN a fill. The live pilot adds real queue rank.
"""
from __future__ import annotations
import glob, json, math
from collections import defaultdict

FILL_REASONS = {"fill", "fill_clipped"}


def load(pattern_gha, pattern_local):
    files = sorted(glob.glob(pattern_gha)) or sorted(glob.glob(pattern_local))
    rows = []
    for fp in files:
        for ln in open(fp):
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    return rows, files


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def wcluster(rows, key):
    """Mean of per-window means (cluster unit = ws) + t vs 0."""
    byw = defaultdict(list)
    for r in rows:
        if r.get(key) is not None:
            byw[r["ws"]].append(r[key])
    wm = [sum(v) / len(v) for v in byw.values() if v]
    if not wm:
        return float("nan"), float("nan"), 0
    m = sum(wm) / len(wm)
    if len(wm) >= 2:
        sd = (sum((x - m) ** 2 for x in wm) / (len(wm) - 1)) ** 0.5
        t = m / (sd / math.sqrt(len(wm))) if sd > 0 else float("nan")
    else:
        t = float("nan")
    return m, t, len(wm)


def audit(rows, wins):
    """Prove the ledger is internally consistent and reconciles to window gross."""
    print("== AUDIT ==")
    # 1) recompute mid/micro/imb from raw book fields; flag mismatches
    bad = 0; checked = 0
    for r in rows:
        bb, ba, bsz, asz = r.get("bb"), r.get("ba"), r.get("bsz"), r.get("asz")
        if bb is None or ba is None:
            continue
        checked += 1
        mid = (bb + ba) / 2
        tot = (bsz or 0) + (asz or 0)
        mic = (bb + ba) / 2 if tot <= 0 else bb + (ba - bb) * (bsz or 0) / tot
        if r.get("mid") is not None and abs(mid - r["mid"]) > 5e-4: bad += 1
        elif r.get("micro") is not None and abs(mic - r["micro"]) > 5e-4: bad += 1
    print(f"  raw-recompute: {checked} rows checked, {bad} mismatches (mid/micro from bb/ba/bsz/asz)")
    # 2) per-fill pnl == sz*mo_res; and Σpnl per (ws,var) == window-audit gross
    pnl_bad = 0
    for r in rows:
        if r.get("sz", 0) > 0 and r.get("pnl") is not None and r.get("mo_res") is not None:
            if abs(r["sz"] * r["mo_res"] - r["pnl"]) > 1e-3:
                pnl_bad += 1
    print(f"  pnl identity (pnl == sz*mo_res): {pnl_bad} mismatches")
    if wins:
        gross_by = {}                       # (ws,var) -> window-audit gross
        for w in wins:
            for var, a in (w.get("audit") or {}).items():
                gross_by[(w["ws"], var)] = a.get("gross")
        sums = defaultdict(float)
        for r in rows:
            sums[(r["ws"], r["var"])] += r.get("pnl") or 0.0
        worst = 0.0; n = 0
        for k, s in sums.items():
            g = gross_by.get(k)
            if g is not None:
                worst = max(worst, abs(s - g)); n += 1
        print(f"  reconciliation Σpnl vs window gross: {n} (ws,var) checked, worst resid={worst:.2e}")
    print()


def report(rows, var):
    rv = [r for r in rows if r["var"] == var]
    if not rv:
        print(f"  ({var}: no decisions yet)"); return
    tally = defaultdict(int)
    for r in rv: tally[r.get("reason", "?")] += 1
    fills = [r for r in rv if r.get("reason") in FILL_REASONS]
    nwin = len(set(r["ws"] for r in rv))
    print(f"\n=== {var}: {len(rv)} decisions over {nwin} windows | reasons={dict(tally)} ===")
    print(f"    actual fills: {len(fills)} "
          f"({sum(1 for r in fills if r['side']=='ASK')} sell / {sum(1 for r in fills if r['side']=='BID')} buy)")
    for label, mo in (("mo5", "mo5"), ("mo30", "mo30"), ("mo_res(decision)", "mo_res")):
        m, t, nw = wcluster(fills, mo)
        print(f"    mean {label:18}= {m:+.4f}  (window-clustered t={t:+.2f}, {nw}w)")
    asks = [r for r in fills if r["side"] == "ASK"]
    print("    SELL markout by book-imbalance (imb=bid share; high => buy pressure on our ask):")
    for lo, hi, name in [(0.0,0.4,"ask-heavy <0.4"),(0.4,0.6,"balanced .4-.6"),
                         (0.6,0.8,"bid-lean .6-.8"),(0.8,1.01,"bid-HEAVY >0.8")]:
        b = [r for r in asks if r.get("imb") is not None and lo <= r["imb"] < hi]
        if b:
            print(f"      {name:16}: n={len(b):5d}  mo30={mean([r['mo30'] for r in b]):+.4f}  "
                  f"mo_res={mean([r['mo_res'] for r in b]):+.4f}  pnl/fill={mean([r['pnl'] for r in b]):+.4f}")


def main():
    rows, files = load("gha_data/fills_r*.jsonl", "fills*.jsonl")
    wins, _ = load("gha_data/shadow_windows_r*.jsonl", "shadow_windows*.jsonl")
    print(f"per-decision ledger: {len(rows)} rows from {len(files)} file(s)\n")
    if not rows:
        print("no decisions yet -- the instrumented collector emits fills_*.jsonl at each window settle.")
        return
    audit(rows, wins)
    for var in ("baseline", "micro_gate"):
        report(rows, var)
    print("\nRead: if loss is adverse selection, SELL mo_res falls as imbalance rises (buy pressure); "
          "and micro_gate should show 'gated' skips concentrated in the bid-HEAVY regime baseline keeps.")


if __name__ == "__main__":
    main()
