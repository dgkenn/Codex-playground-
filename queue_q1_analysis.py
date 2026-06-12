"""
queue_q1_analysis.py — Q1: What is front-of-queue worth?

DATA:
  audit_book.jsonl  — top-of-book snapshots (bb, bsz, ba, asz) at ~1Hz, 35 windows
  trades_kalshi_btc15m.parquet — settlement per window

APPROACH:
  For each snapshot series, detect takes as drops in displayed size at constant price.
  Classify by take_size / depth_before to approximate who-in-queue got filled.
  Compare markout (maker perspective) across take categories.
"""
from __future__ import annotations
import json
import pandas as pd
import numpy as np
from collections import defaultdict

MIN_DROP = 0.5    # min drop to count as a real take (filter noise)
MIN_DEPTH = 1.0   # min depth-before

# ── Load data
print("Loading data...")
snaps_by_ws = defaultdict(list)
with open("/home/user/Codex-playground-/audit_book.jsonl") as f:
    for line in f:
        d = json.loads(line)
        if "bb" in d and d["bb"] is not None and d["ba"] is not None:
            snaps_by_ws[d["ws"]].append(d)

trades_df = pd.read_parquet("/home/user/Codex-playground-/trades_kalshi_btc15m.parquet")
settle = dict(zip(trades_df["ws"], trades_df["res_up"]))

ws_list = sorted(snaps_by_ws.keys())
overlap = [ws for ws in ws_list if ws in settle]
print(f"  Windows with book+settlement: {len(overlap)}, total snaps: {sum(len(snaps_by_ws[w]) for w in overlap)}")

# ── Detect take events from consecutive snapshot size drops
take_events = []

for ws in overlap:
    snaps = sorted(snaps_by_ws[ws], key=lambda d: d["ts"])
    res = settle[ws]

    # YES BID side: bb constant, bsz drops → taker bought YES (took resting YES bid)
    # Markout for YES maker resting at bb: res_up - bb
    prev_bb, prev_bsz = None, None
    for snap in snaps:
        bb, bsz = snap["bb"], snap["bsz"]
        if prev_bb is not None and bb == prev_bb and prev_bsz is not None:
            drop = prev_bsz - bsz
            if drop >= MIN_DROP and prev_bsz >= MIN_DEPTH:
                D, dD = prev_bsz, drop
                ratio = dD / D
                cat = "small" if ratio < 1/3 else ("medium" if ratio < 2/3 else "large")
                take_events.append({
                    "ws": ws, "side": "YES_bid", "price": bb,
                    "depth_before": D, "take_size": dD, "ratio": ratio,
                    "cat": cat, "res_up": res,
                    "markout": res - bb   # YES maker: profit if res=1
                })
        prev_bb, prev_bsz = bb, bsz

    # NO BID side: ba constant (= 1 - best NO bid), asz drops → taker sold YES (took NO bid)
    # Markout for NO maker at price (1-ba): (1-res_up) - (1-ba) = ba - res_up
    prev_ba, prev_asz = None, None
    for snap in snaps:
        ba, asz = snap["ba"], snap["asz"]
        if prev_ba is not None and ba == prev_ba and prev_asz is not None:
            drop = prev_asz - asz
            if drop >= MIN_DROP and prev_asz >= MIN_DEPTH:
                D, dD = prev_asz, drop
                ratio = dD / D
                cat = "small" if ratio < 1/3 else ("medium" if ratio < 2/3 else "large")
                take_events.append({
                    "ws": ws, "side": "NO_bid", "price": 1 - ba,
                    "depth_before": D, "take_size": dD, "ratio": ratio,
                    "cat": cat, "res_up": res,
                    "markout": ba - res   # NO maker: profit if res=0
                })
        prev_ba, prev_asz = ba, asz

ev = pd.DataFrame(take_events)

# ── TABLE 1: Take-size category
print()
print("=" * 66)
print("TABLE 1: Take-size category vs markout (YES + NO combined)")
print("=" * 66)
fmt = f"{'Category':<30} {'N':>7} {'AvgTake':>9} {'AvgDepth':>9} {'P(win)':>8} {'Markout(c)':>11}"
print(fmt)
print("-" * 66)

cats_info = [
    ("small",  "small  (dD<D/3)  front fills"),
    ("medium", "medium (D/3-2/3) mid fills  "),
    ("large",  "large  (dD>2D/3) sweep fills"),
]
table1 = {}
for cat, label in cats_info:
    sub = ev[ev.cat == cat]
    n = len(sub)
    if n == 0:
        print(f"{label:<30} {0:>7}")
        continue
    avg_take = sub["take_size"].mean()
    avg_depth = sub["depth_before"].mean()
    p_win = (sub["markout"] > 0).mean()
    mo_c = sub["markout"].mean() * 100
    table1[cat] = mo_c
    print(f"{label:<30} {n:>7} {avg_take:>9.1f} {avg_depth:>9.1f} {p_win:>8.3f} {mo_c:>+11.2f}")

# ── TABLE 2: Side x category
print()
print("=" * 66)
print("TABLE 2: Side x take-size category")
print("=" * 66)
fmt2 = f"{'Side + Category':<32} {'N':>7} {'AvgTake':>9} {'P(win)':>8} {'Markout(c)':>11}"
print(fmt2)
print("-" * 66)
for side in ["YES_bid", "NO_bid"]:
    for cat, label in cats_info:
        sub = ev[(ev.side == side) & (ev.cat == cat)]
        n = len(sub)
        if n == 0:
            print(f"{side} {cat:<22} {0:>7}")
            continue
        avg_take = sub["take_size"].mean()
        p_win = (sub["markout"] > 0).mean()
        mo_c = sub["markout"].mean() * 100
        print(f"{side} {cat:<22} {n:>7} {avg_take:>9.1f} {p_win:>8.3f} {mo_c:>+11.2f}")
    print()

# ── TABLE 3: Queue position tier
print("=" * 66)
print("TABLE 3: Queue position tier (who gets filled and at what markout)")
print("=" * 66)
print("  Front-maker (q<=D/3): fills on ALL takes")
print("  Mid-maker (D/3<q<=2D/3): fills on medium + large only")
print("  Back-maker (q>2D/3): fills on large sweeps only")
print()
fmt3 = f"{'Queue tier':<44} {'N_fills':>8} {'P(win)':>8} {'Markout(c)':>11}"
print(fmt3)
print("-" * 66)

tiers = [
    ("front (q<=D/3, all takes)",            ev),
    ("middle (D/3<q<=2D/3, med+large)",       ev[ev.cat.isin(["medium","large"])]),
    ("back (q>2D/3, large sweeps only)",       ev[ev.cat == "large"]),
]
tier_mo = {}
for tname, sub in tiers:
    n = len(sub)
    if n == 0:
        print(f"{tname:<44} {0:>8}")
        continue
    p_win = (sub["markout"] > 0).mean()
    mo_c = sub["markout"].mean() * 100
    tier_mo[tname] = mo_c
    print(f"{tname:<44} {n:>8} {p_win:>8.3f} {mo_c:>+11.2f}")

# ── Selection effect summary
print()
print("=" * 66)
print("KEY FINDING: Selection Effect (front vs back of queue)")
print("=" * 66)

small_mo = ev[ev.cat=="small"]["markout"].mean() * 100 if len(ev[ev.cat=="small"]) else float("nan")
large_mo = ev[ev.cat=="large"]["markout"].mean() * 100 if len(ev[ev.cat=="large"]) else float("nan")
all_mo   = ev["markout"].mean() * 100

print(f"  All-take avg markout:           {all_mo:+.2f} ¢")
print(f"  Small-take markout (front-Q):   {small_mo:+.2f} ¢")
print(f"  Large-sweep markout (back-Q):   {large_mo:+.2f} ¢")
delta = small_mo - large_mo
print(f"  Front-vs-back advantage:        {delta:+.2f} ¢")
if not np.isnan(delta):
    if delta > 0.5:
        print("  => Front-of-queue is BETTER: small-take takers are less informed.")
    elif delta < -0.5:
        print("  => Front-of-queue is WORSE: small takes carry more adverse selection.")
    else:
        print("  => No significant front-vs-back difference.")

# ── Data summary
print()
print("=" * 66)
print("DATASET SUMMARY")
print("=" * 66)
print(f"  Windows analyzed:         {len(overlap)}")
n_yes = len(ev[ev.side=="YES_bid"])
n_no  = len(ev[ev.side=="NO_bid"])
print(f"  Total take events:        {len(ev)} (YES_bid={n_yes}, NO_bid={n_no})")
n_small = len(ev[ev.cat=="small"]); n_med = len(ev[ev.cat=="medium"]); n_large = len(ev[ev.cat=="large"])
print(f"  By category: small={n_small} ({100*n_small/len(ev):.0f}%), "
      f"medium={n_med} ({100*n_med/len(ev):.0f}%), large={n_large} ({100*n_large/len(ev):.0f}%)")
print(f"  Avg take size:            {ev['take_size'].mean():.1f} contracts")
print(f"  Avg depth at touch:       {ev['depth_before'].mean():.1f} contracts")

# Spread stats
spreads = []
for ws in overlap[:10]:
    for snap in snaps_by_ws[ws][:100]:
        if snap.get("ba") and snap.get("bb"):
            spreads.append(snap["ba"] - snap["bb"])
if spreads:
    print(f"  Avg bid-ask spread:       {np.mean(spreads)*100:.2f} ¢ (sample of {len(spreads)} snaps)")
