"""
queue_q1_analysis.py — Q1: What is front-of-queue worth?

DATA:
  audit_book.jsonl  — top-of-book snapshots (bb, bsz, ba, asz) at ~1Hz, 34 windows
  trades_kalshi_btc15m.parquet — settlement per window (res_up)

APPROACH:
  Detect taker hits as consecutive-snapshot size drops at constant price.
  Classify by take_size/depth ratio to approximate queue position selection.
  Key metric: excess markout vs the unconditional window baseline (controls for
  per-window directional bias in the 34-window sample).
"""
from __future__ import annotations
import json
import pandas as pd
import numpy as np
from collections import defaultdict

MIN_DROP = 0.5    # min size drop to count as a real take
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
total_snaps = sum(len(snaps_by_ws[w]) for w in overlap)
print(f"  Windows: {len(overlap)}, snapshots: {total_snaps}")
res_vals = [settle[ws] for ws in overlap]
print(f"  Settlement: {sum(res_vals)} YES (res_up=1), {len(res_vals)-sum(res_vals)} NO (res_up=0)")

# ── Baseline markout per window (unconditional expectation)
baseline_by_ws = {}
for ws in overlap:
    snaps = snaps_by_ws[ws]
    res = settle[ws]
    avg_bb = np.mean([s["bb"] for s in snaps])
    avg_ba = np.mean([s["ba"] for s in snaps])
    baseline_by_ws[ws] = {
        "res": res, "avg_bb": avg_bb, "avg_ba": avg_ba,
        "base_yes_bid_mo": res - avg_bb,
        "base_yes_ask_mo": avg_ba - res,
    }

# ── Detect take events
take_events = []
for ws in overlap:
    snaps = sorted(snaps_by_ws[ws], key=lambda d: d["ts"])
    res = settle[ws]
    bl = baseline_by_ws[ws]

    # YES BID side: bsz drops at constant bb → taker bought YES, fills YES bidders
    # YES bidder markout: res_up - bb
    prev_bb, prev_bsz = None, None
    for snap in snaps:
        bb, bsz = snap["bb"], snap["bsz"]
        if prev_bb is not None and bb == prev_bb and prev_bsz is not None:
            drop = prev_bsz - bsz
            if drop >= MIN_DROP and prev_bsz >= MIN_DEPTH:
                D, dD = prev_bsz, drop
                ratio = dD / D
                cat = "small" if ratio < 1/3 else ("medium" if ratio < 2/3 else "large")
                markout = res - bb
                take_events.append({
                    "ws": ws, "side": "YES_bid", "price": bb,
                    "depth_before": D, "take_size": dD, "ratio": ratio,
                    "cat": cat, "res_up": res,
                    "markout": markout,
                    "excess": markout - bl["base_yes_bid_mo"],
                })
        prev_bb, prev_bsz = bb, bsz

    # YES ASK (NO bid) side: asz drops at constant ba → taker sold YES, fills YES askers
    # YES asker markout: ba - res_up  (wins when res=0 and ba>0)
    prev_ba, prev_asz = None, None
    for snap in snaps:
        ba, asz = snap["ba"], snap["asz"]
        if prev_ba is not None and ba == prev_ba and prev_asz is not None:
            drop = prev_asz - asz
            if drop >= MIN_DROP and prev_asz >= MIN_DEPTH:
                D, dD = prev_asz, drop
                ratio = dD / D
                cat = "small" if ratio < 1/3 else ("medium" if ratio < 2/3 else "large")
                markout = ba - res
                take_events.append({
                    "ws": ws, "side": "YES_ask", "price": ba,
                    "depth_before": D, "take_size": dD, "ratio": ratio,
                    "cat": cat, "res_up": res,
                    "markout": markout,
                    "excess": markout - bl["base_yes_ask_mo"],
                })
        prev_ba, prev_asz = ba, asz

ev = pd.DataFrame(take_events)
print()

# ── TABLE 1: Take-size category (both sides combined, excess markout)
print("=" * 68)
print("TABLE 1: Take-size category vs maker markout (YES_bid + YES_ask combined)")
print("  Excess = actual fill markout minus window unconditional baseline")
print("  Front-of-queue maker experiences 'small' takes only.")
print("=" * 68)
fmt = f"{'Category':<32} {'N':>6} {'AvgTake':>9} {'AvgDepth':>9} {'P(win)':>8} {'Markout(c)':>11} {'Excess(c)':>11}"
print(fmt)
print("-" * 68)

cats_info = [
    ("small",  "small  (dD<D/3)   front-Q fills"),
    ("medium", "medium (D/3-2D/3) mid-Q fills  "),
    ("large",  "large  (dD>2D/3)  sweep fills  "),
]
table1 = {}
for cat, label in cats_info:
    sub = ev[ev.cat == cat]
    n = len(sub)
    if n == 0:
        print(f"{label:<32} {0:>6}")
        continue
    avg_take = sub["take_size"].mean()
    avg_depth = sub["depth_before"].mean()
    p_win = (sub["markout"] > 0).mean()
    mo_c = sub["markout"].mean() * 100
    ex_c = sub["excess"].mean() * 100
    table1[cat] = {"n": n, "mo": mo_c, "ex": ex_c, "p_win": p_win}
    print(f"{label:<32} {n:>6} {avg_take:>9.1f} {avg_depth:>9.1f} {p_win:>8.3f} {mo_c:>+11.2f} {ex_c:>+11.2f}")

print()

# ── TABLE 2: Side x category
print("=" * 68)
print("TABLE 2: Side x take-size category")
print("=" * 68)
fmt2 = f"{'Side + Category':<34} {'N':>6} {'AvgTake':>9} {'P(win)':>8} {'Markout(c)':>11} {'Excess(c)':>11}"
print(fmt2)
print("-" * 68)
for side in ["YES_bid", "YES_ask"]:
    for cat, label in cats_info:
        sub = ev[(ev.side == side) & (ev.cat == cat)]
        n = len(sub)
        if n == 0:
            print(f"{side} {cat:<24} {0:>6}")
            continue
        avg_take = sub["take_size"].mean()
        p_win = (sub["markout"] > 0).mean()
        mo_c = sub["markout"].mean() * 100
        ex_c = sub["excess"].mean() * 100
        print(f"{side} {cat:<24} {n:>6} {avg_take:>9.1f} {p_win:>8.3f} {mo_c:>+11.2f} {ex_c:>+11.2f}")
    print()

# ── TABLE 3: Queue position tier
print("=" * 68)
print("TABLE 3: Queue position tier (simulated fill set by resting position)")
print("  A maker at front (q<=D/3) gets filled by ALL take sizes.")
print("  A maker at middle (D/3<q<=2D/3) only filled by medium + large.")
print("  A maker at back (q>2D/3) only filled by large sweeps.")
print("=" * 68)
fmt3 = f"{'Queue tier':<45} {'N_fills':>7} {'P(win)':>8} {'Markout(c)':>11} {'Excess(c)':>11}"
print(fmt3)
print("-" * 68)

tiers = [
    ("front (q<=D/3,  filled by all takes)",      ev),
    ("middle (D/3<q<=2D/3, medium+large only)",    ev[ev.cat.isin(["medium","large"])]),
    ("back (q>2D/3,   large sweeps only)",          ev[ev.cat == "large"]),
]
for tname, sub in tiers:
    n = len(sub)
    if n == 0:
        print(f"{tname:<45} {0:>7}")
        continue
    p_win = (sub["markout"] > 0).mean()
    mo_c = sub["markout"].mean() * 100
    ex_c = sub["excess"].mean() * 100
    print(f"{tname:<45} {n:>7} {p_win:>8.3f} {mo_c:>+11.2f} {ex_c:>+11.2f}")

# ── Key finding
print()
print("=" * 68)
print("KEY FINDING: Front-of-queue selection effect")
print("=" * 68)
small_ex = ev[ev.cat=="small"]["excess"].mean() * 100 if "small" in ev.cat.values else float("nan")
large_ex  = ev[ev.cat=="large"]["excess"].mean()  * 100 if "large" in ev.cat.values else float("nan")
front_mo  = ev["markout"].mean() * 100
back_mo   = ev[ev.cat=="large"]["markout"].mean() * 100

print(f"  Unconditional maker markout (time-weighted):  ~0.00¢ (baseline)")
print(f"  Small-take (front-Q selection) excess:        {small_ex:+.2f}¢")
print(f"  Large-sweep (back-Q selection) excess:        {large_ex:+.2f}¢")
delta_ex = small_ex - large_ex
print(f"  Front-vs-back excess difference:              {delta_ex:+.2f}¢")
print()
if not np.isnan(delta_ex):
    if delta_ex > 0.5:
        print("  => FRONT-OF-QUEUE IS BETTER: small takers are less informed/more noise.")
        print("     Being early in the queue is VALUABLE; back fills carry more adverse selection.")
    elif delta_ex < -0.5:
        print("  => FRONT-OF-QUEUE IS WORSE: small takes carry MORE adverse selection.")
        print("     Informed takers hit precisely (small, targeted), sweeps are noise.")
    else:
        print("  => NO SIGNIFICANT DIFFERENCE: queue position does not materially affect markout.")

# Additional stat: how often does a large sweep predict direction?
large_ev = ev[ev.cat=="large"]
if len(large_ev) > 5:
    # Large sweep = taker was aggressive. Check if taker was right.
    # YES_bid side: taker BUY YES. Taker wins if res_up=1.
    yes_sweep = large_ev[large_ev.side=="YES_bid"]
    no_sweep  = large_ev[large_ev.side=="YES_ask"]
    if len(yes_sweep) > 0:
        print(f"\n  Large YES-taker accuracy: P(res_up=1) = {yes_sweep['res_up'].mean():.3f} (N={len(yes_sweep)})")
    if len(no_sweep) > 0:
        print(f"  Large NO-taker accuracy:  P(res_up=0) = {(1-no_sweep['res_up']).mean():.3f} (N={len(no_sweep)})")

# ── Dataset summary
print()
print("=" * 68)
print("DATASET SUMMARY")
print("=" * 68)
print(f"  Windows analyzed:          {len(overlap)}")
print(f"  Settlement: YES={sum(res_vals)}, NO={len(res_vals)-sum(res_vals)}")
print(f"  Total take events:         {len(ev)} (YES_bid={len(ev[ev.side=='YES_bid'])}, YES_ask={len(ev[ev.side=='YES_ask'])})")
n_s = len(ev[ev.cat=="small"]); n_m = len(ev[ev.cat=="medium"]); n_l = len(ev[ev.cat=="large"])
print(f"  Take breakdown: small={n_s} ({100*n_s/len(ev):.0f}%), medium={n_m} ({100*n_m/len(ev):.0f}%), large={n_l} ({100*n_l/len(ev):.0f}%)")
print(f"  Avg take size:             {ev['take_size'].mean():.1f} contracts")
print(f"  Avg depth at touch:        {ev['depth_before'].mean():.1f} contracts")

# Spread stats from sample
spreads = []
for ws in overlap[:10]:
    for snap in snaps_by_ws[ws][:100]:
        if snap.get("ba") and snap.get("bb"):
            spreads.append(snap["ba"] - snap["bb"])
if spreads:
    print(f"  Avg bid-ask spread:        {np.mean(spreads)*100:.2f}¢ (sample n={len(spreads)})")

print(f"\n  NOTE: 'excess' metric controls for per-window directional bias")
print(f"  by subtracting window-avg unconditional markout from each take event.")
