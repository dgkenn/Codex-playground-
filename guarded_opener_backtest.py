"""
guarded_opener_backtest.py — IS/OOS comparison of guarded-opener variants vs P0 baseline.
Outputs ONLY summary table + strand decomposition.
"""
import sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/user/Codex-playground-")
from box_policy_ab import (window_fills, run_policy, pol_p0, tstat, maxdd,
                            combo_tox_p, _COMBO_THRESH)

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
hist = pd.read_parquet("/home/user/Codex-playground-/hist_kalshi_btc15m.parquet").set_index("ws")
tap  = pd.read_parquet("/home/user/Codex-playground-/trades_kalshi_btc15m.parquet").set_index("ws")

# Intersect windows
ws_common = sorted(set(hist.index) & set(tap.index))
print(f"Windows in intersection: {len(ws_common)}")

# ---------------------------------------------------------------------------
# 2. Build per-window fills
# ---------------------------------------------------------------------------
all_fills = {}  # ws -> list of fill dicts
skipped = 0
for ws in ws_common:
    h = hist.loc[ws]
    t = tap.loc[ws]
    res   = int(h["res_up"])
    bid   = np.array(h["bid_path"], dtype=float)
    ask   = np.array(h["ask_path"], dtype=float)
    spot  = np.array(h["spot_path"], dtype=float)
    depth = np.full(15, np.nan)
    t_arr   = np.array(t["t"],   dtype=float)
    p_arr   = np.array(t["p"],   dtype=float)
    sz_arr  = np.array(t["sz"],  dtype=float)
    buy_arr = np.array(t["buy"], dtype=bool)
    tape = (t_arr, p_arr, sz_arr, buy_arr)
    try:
        fills = window_fills(ws, res, bid, ask, spot, depth, tape, oi_slope=None)
        all_fills[ws] = fills
    except Exception as e:
        skipped += 1

print(f"Windows with fills built: {len(all_fills)}, skipped: {skipped}")

# ---------------------------------------------------------------------------
# 3. IS / OOS split (60/40 by sorted ws)
# ---------------------------------------------------------------------------
ws_sorted = sorted(all_fills.keys())
n = len(ws_sorted)
n_is = int(n * 0.60)
ws_is  = ws_sorted[:n_is]
ws_oos = ws_sorted[n_is:]
print(f"IS: {len(ws_is)} windows, OOS: {len(ws_oos)} windows")

# ---------------------------------------------------------------------------
# 4. Gate helpers
# ---------------------------------------------------------------------------
def gate_t02(f, _st):
    """Skip YES (bid) if spread < 0.02."""
    if f["side"] == "bid" and f["spread"] < 0.02:
        return False
    return True

def gate_t07(f, _st):
    """Skip if sig > 8.0 (adverse spot move)."""
    if (f.get("sig") or 0.0) > 8.0:
        return False
    return True

def gate_t35(f, _st):
    """Skip if combo_tox_p > _COMBO_THRESH (and not None)."""
    cp = combo_tox_p(f)
    if cp is not None and cp > _COMBO_THRESH:
        return False
    return True

def gate_t36a_union(f, st):
    return gate_t02(f, st) and gate_t07(f, st) and gate_t35(f, st)

def gate_t36b_spot_side(f, st):
    """Skip if |sig|>8 OR (YES and spread<0.02)."""
    sig = abs(f.get("sig") or 0.0)
    if sig > 8.0:
        return False
    if f["side"] == "bid" and f["spread"] < 0.02:
        return False
    return True

def gate_t36c_vote2(f, st):
    """Skip if 2+ of {t02, t07, t35} fire."""
    votes = 0
    if not gate_t02(f, st): votes += 1
    if not gate_t07(f, st): votes += 1
    if not gate_t35(f, st): votes += 1
    return votes < 2

def gate_t36d_as_skew(f, st):
    """Skip leg if (YES and spread<0.02) OR (sig>8 and spread<0.02).
    Approximates A-S skew: require 2c spread on any leg touched by toxicity signals."""
    sig = (f.get("sig") or 0.0)
    sp  = f["spread"]
    if f["side"] == "bid" and sp < 0.02:
        return False
    if sig > 8.0 and sp < 0.02:
        return False
    return True

VARIANTS = [
    ("P0",             None),
    ("t02_yes_caution", gate_t02),
    ("t07_spot_gate",  gate_t07),
    ("t35_combo_tox",  gate_t35),
    ("t36a_UNION",     gate_t36a_union),
    ("t36b_SPOT_SIDE", gate_t36b_spot_side),
    ("t36c_VOTE2OF3",  gate_t36c_vote2),
    ("t36d_AS_SKEW",   gate_t36d_as_skew),
]

# ---------------------------------------------------------------------------
# 5. Policy walker with strand tracking
# ---------------------------------------------------------------------------
def run_policy_with_strands(fills, open_ok=None):
    """Returns (pnl, strands_list). strands = unpaired legs at window end."""
    net = 0; pnl = 0.0; held = None
    st = {"yes": 0, "no": 0}
    strands = []
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if not pairing:
            if open_ok is not None and not open_ok(f, st):
                continue
            held = f
        else:
            held = None
        net = nn
        pnl += f["settle"]
        st["yes" if f["side"] == "bid" else "no"] += 1
    if net != 0 and held is not None:
        strands.append(held)
    return pnl, strands

# ---------------------------------------------------------------------------
# 6. Evaluate all variants on IS + OOS
# ---------------------------------------------------------------------------
def evaluate(ws_list, gate_fn):
    pnls, fill_counts, strand_yes, strand_no, strand_costs = [], [], [], [], []
    n_opened = 0; n_p0_opened = 0
    for ws in ws_list:
        fills = all_fills[ws]
        pnl, strands = run_policy_with_strands(fills, open_ok=gate_fn)
        pnls.append(pnl)
        # count fills taken
        opened = 0
        net_tmp = 0
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net_tmp + step
            if abs(nn) > 1:
                continue
            pairing = (net_tmp != 0 and abs(nn) < abs(net_tmp))
            if not pairing:
                if gate_fn is not None and not gate_fn(f, {}):
                    continue
            opened += 1
            net_tmp = nn
        fill_counts.append(opened)
        sy = sum(1 for s in strands if s["side"] == "bid")
        sn = sum(1 for s in strands if s["side"] == "ask")
        strand_yes.append(sy)
        strand_no.append(sn)
        strand_costs.append(sum(s["settle"] for s in strands))
    return (np.array(pnls), np.array(fill_counts),
            np.array(strand_yes), np.array(strand_no), np.array(strand_costs))

def evaluate_pair_rate(ws_list, gate_fn):
    """Compute pair rate: (fills that are part of complete boxes) / total fills taken."""
    total_paired = 0; total_fills = 0
    for ws in ws_list:
        fills = all_fills[ws]
        net = 0; held = None; st = {}
        pairs = 0; opens = 0
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            pairing = (net != 0 and abs(nn) < abs(net))
            if not pairing:
                if gate_fn is not None and not gate_fn(f, st):
                    continue
                held = f; opens += 1
            else:
                pairs += 1; opens += 1; held = None
            net = nn
        total_paired += pairs * 2
        total_fills  += opens
    return total_paired / total_fills if total_fills > 0 else 0.0

# Precompute P0 pnls for t-stat
p0_pnls_is,  _, _, _, _ = evaluate(ws_is,  None)
p0_pnls_oos, _, _, _, _ = evaluate(ws_oos, None)

# ---------------------------------------------------------------------------
# 7. Build results table
# ---------------------------------------------------------------------------
rows = []
for split_name, ws_list, p0_pnls in [("IS", ws_is, p0_pnls_is), ("OOS", ws_oos, p0_pnls_oos)]:
    # Count P0 total fills for skip% baseline
    _, p0_fills_arr, _, _, _ = evaluate(ws_list, None)
    p0_total_fills = p0_fills_arr.sum()

    for vname, gate_fn in VARIANTS:
        pnls, fills_arr, sy_arr, sn_arr, sc_arr = evaluate(ws_list, gate_fn)
        total_pnl    = pnls.sum()
        total_fills  = fills_arr.sum()
        mean_pnl     = pnls.mean()
        per_fill     = (total_pnl / total_fills * 100) if total_fills > 0 else 0.0
        win_pct      = (pnls > 0).mean() * 100
        md           = maxdd(np.cumsum(pnls)) * 100
        skip_pct     = (1 - total_fills / p0_total_fills) * 100 if p0_total_fills > 0 else 0.0
        pair_rate    = evaluate_pair_rate(ws_list, gate_fn) * 100
        diff         = pnls - p0_pnls
        ts           = tstat(diff)
        mean_sy      = sy_arr.mean()
        mean_sn      = sn_arr.mean()
        mean_sc      = sc_arr.mean() * 100

        rows.append({
            "split":    split_name,
            "variant":  vname,
            "net_c_win":    round(mean_pnl * 100, 3),
            "per_fill_c":   round(per_fill, 3),
            "win_pct":      round(win_pct, 1),
            "maxDD_c":      round(md, 1),
            "skip_pct":     round(skip_pct, 1),
            "pair_rate":    round(pair_rate, 1),
            "tstat_vs_p0":  round(ts, 2),
            "strand_yes":   round(mean_sy, 3),
            "strand_no":    round(mean_sn, 3),
            "strand_cost_c": round(mean_sc, 3),
        })

results = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# 8. Print compact table
# ---------------------------------------------------------------------------
print("\n" + "="*100)
print("GUARDED OPENER BACKTEST — IS/OOS SUMMARY")
print("="*100)

for split in ["IS", "OOS"]:
    print(f"\n--- {split} ---")
    sub = results[results["split"] == split][
        ["variant","net_c_win","per_fill_c","win_pct","maxDD_c","skip_pct","pair_rate","tstat_vs_p0"]
    ]
    print(sub.to_string(index=False))

# ---------------------------------------------------------------------------
# 9. Strand decomposition
# ---------------------------------------------------------------------------
print("\n" + "="*100)
print("STRAND DECOMPOSITION (mean per window)")
print("="*100)
for split in ["IS", "OOS"]:
    print(f"\n--- {split} ---")
    sub = results[results["split"] == split][
        ["variant","strand_yes","strand_no","strand_cost_c","pair_rate"]
    ]
    print(sub.to_string(index=False))

# ---------------------------------------------------------------------------
# 10. Decompose improvement for OOS winner
# ---------------------------------------------------------------------------
oos_sub = results[results["split"] == "OOS"].set_index("variant")
p0_row  = oos_sub.loc["P0"]

print("\n" + "="*100)
print("DECOMPOSITION vs P0 (OOS) — strand avoided / box volume impact")
print("="*100)
print(f"{'Variant':<20} {'ΔStrand_YES':>12} {'ΔStrand_NO':>11} {'ΔStrand_cost_c':>15} {'Δnet_c_win':>12} {'Δpair_rate':>11}")
for vname, gate_fn in VARIANTS:
    if vname == "P0":
        continue
    row = oos_sub.loc[vname]
    d_sy   = row["strand_yes"]   - p0_row["strand_yes"]
    d_sn   = row["strand_no"]    - p0_row["strand_no"]
    d_sc   = row["strand_cost_c"] - p0_row["strand_cost_c"]
    d_net  = row["net_c_win"]    - p0_row["net_c_win"]
    d_pr   = row["pair_rate"]    - p0_row["pair_rate"]
    print(f"{vname:<20} {d_sy:>12.3f} {d_sn:>11.3f} {d_sc:>15.3f} {d_net:>12.3f} {d_pr:>11.1f}")

# ---------------------------------------------------------------------------
# 11. Verdict
# ---------------------------------------------------------------------------
print("\n" + "="*100)
print("VERDICT")
print("="*100)
# Best OOS by net_c_win excluding P0
oos_variants = oos_sub.drop("P0")
winner = oos_variants["net_c_win"].idxmax()
wrow = oos_variants.loc[winner]
print(f"OOS winner: {winner}")
print(f"  net c/win = {wrow['net_c_win']:.3f}c  |  per-fill = {wrow['per_fill_c']:.3f}c  |  tstat vs P0 = {wrow['tstat_vs_p0']:.2f}")
print(f"  skip%={wrow['skip_pct']:.1f}  pair_rate={wrow['pair_rate']:.1f}%  maxDD={wrow['maxDD_c']:.1f}c")
print(f"P0 baseline OOS: net c/win = {p0_row['net_c_win']:.3f}c")
print()
