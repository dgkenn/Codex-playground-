"""guarded_opener_backtest.py -- IS/OOS comparison of guarded-opener variants vs P0 baseline.

Tests 8 policy variants on hist_kalshi_btc15m.parquet + trades_kalshi_btc15m.parquet.
60/40 time split. Compact summary table only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from box_policy_ab import (
    window_fills, run_policy, pol_p0, tstat, maxdd,
    combo_tox_p, _COMBO_THRESH
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data():
    hist = pd.read_parquet('hist_kalshi_btc15m.parquet').set_index('ws')
    tap = pd.read_parquet('trades_kalshi_btc15m.parquet').set_index('ws')
    return hist, tap


# ---------------------------------------------------------------------------
# Per-window fills reconstruction
# ---------------------------------------------------------------------------
def get_fills(ws, hist, tap):
    hr = hist.loc[ws]
    res = int(hr['res_up'])
    bid = np.asarray(hr['bid_path'], dtype=float)
    ask = np.asarray(hr['ask_path'], dtype=float)
    spot = np.asarray(hr['spot_path'], dtype=float)
    depth = np.full(15, np.nan)

    if ws in tap.index:
        tr = tap.loc[ws]
        t_arr = np.asarray(tr['t'], dtype=float)
        p_arr = np.asarray(tr['p'], dtype=float)
        sz_arr = np.asarray(tr['sz'], dtype=float)
        buy_arr = np.asarray(tr['buy'], dtype=bool)
        tape = (t_arr, p_arr, sz_arr, buy_arr)
    else:
        tape = (np.array([]), np.array([]), np.array([]), np.array([], dtype=bool))

    fills = window_fills(ws, res, bid, ask, spot, depth, tape, oi_slope=None)
    return fills


# ---------------------------------------------------------------------------
# Custom policy walker that also tracks strands
# ---------------------------------------------------------------------------
def run_policy_with_strands(fills, open_ok=None):
    """Returns (pnl, strands_list, n_total_fills, n_paired_fills).
    Each strand is a fill dict of an unpaired leg.
    pnl is computed via run_policy to ensure consistency.
    """
    # Use run_policy for pnl
    pnl = run_policy(fills, open_ok=open_ok)

    # Walk again to track strands and fill counts
    net = 0; held = None; st = {}
    strands = []
    n_total = 0; n_paired = 0

    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if pairing:
            n_total += 1; n_paired += 2  # both legs count as paired
            held = None; net = nn
            continue
        # opening fill
        if open_ok is not None and not open_ok(f, st):
            continue
        if net == 0 and nn != 0:
            held = f
        net = nn
        n_total += 1

    # strand = the open leg that was never completed
    if held is not None and net != 0:
        strands.append(held)
        n_paired -= 1  # this one wasn't actually paired - correct

    # Simpler: paired = n_total - n_strands (each strand is 1 unmatched leg)
    n_strands = len(strands)
    n_paired_correct = n_total - n_strands

    return pnl, strands, n_total, n_paired_correct


# ---------------------------------------------------------------------------
# P0 fill counter (for skip% calculation)
# ---------------------------------------------------------------------------
def count_p0_fills(fills):
    net = 0; count = 0
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        net = nn; count += 1
    return count


# ---------------------------------------------------------------------------
# Policy definitions: open_ok gates
# ---------------------------------------------------------------------------
def gate_t02(f, s):
    return not (f["side"] == "bid" and f["spread"] < 0.02)

def gate_t07(f, s):
    return f["sig"] <= 8.0

def gate_t35(f, s):
    cp = combo_tox_p(f)
    if cp is None:
        return True
    return cp <= _COMBO_THRESH

def gate_union(f, s):
    return gate_t02(f, s) and gate_t07(f, s) and gate_t35(f, s)

def gate_spot_side(f, s):
    # skip YES-caution (t02) OR (sig>8 AND spread<0.02)
    if f["side"] == "bid" and f["spread"] < 0.02:
        return False
    if f["sig"] > 8.0 and f["spread"] < 0.02:
        return False
    return True

def gate_vote2(f, s):
    votes = int(not gate_t02(f, s)) + int(not gate_t07(f, s)) + int(not gate_t35(f, s))
    return votes < 2

def gate_as_skew(f, s):
    # A-S skew: skip if (YES AND spread<0.02) OR (sig>8 AND spread<0.02)
    if f["side"] == "bid" and f["spread"] < 0.02:
        return False
    if f["sig"] > 8.0 and f["spread"] < 0.02:
        return False
    return True

VARIANTS = [
    ("P0",              None),
    ("t02",             gate_t02),
    ("t07",             gate_t07),
    ("t35",             gate_t35),
    ("t36a_UNION",      gate_union),
    ("t36b_SPOT_SIDE",  gate_spot_side),
    ("t36c_VOTE2OF3",   gate_vote2),
    ("t36d_AS_SKEW",    gate_as_skew),
]


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------
def compute_metrics(windows_fills, gate_fn, p0_pnls):
    pnls = []
    total_fills = 0
    p0_fills_total = 0
    total_paired = 0
    yes_strands = 0; no_strands = 0
    strand_costs = []

    for (ws, fills), p0_pnl in zip(windows_fills, p0_pnls):
        p0_n = count_p0_fills(fills)
        p0_fills_total += p0_n

        if not fills:
            pnls.append(0.0)
            continue

        pnl, strands, n_total, n_paired = run_policy_with_strands(fills, open_ok=gate_fn)
        pnls.append(pnl)
        total_fills += n_total
        total_paired += n_paired

        for strand in strands:
            if strand["side"] == "bid":
                yes_strands += 1
            else:
                no_strands += 1
            strand_costs.append(strand["settle"])

    pnls_arr = np.array(pnls)
    p0_arr = np.array(p0_pnls)
    diff = pnls_arr - p0_arr

    n_total_w = len(pnls_arr)
    win_pct = 100.0 * float(np.sum(pnls_arr > 0)) / n_total_w if n_total_w else 0.0
    net_c_win = float(np.mean(pnls_arr)) * 100.0
    per_fill_c = (float(np.sum(pnls_arr)) / total_fills * 100.0) if total_fills else float("nan")
    mdd = maxdd(pnls_arr) * 100.0
    skip_pct = 100.0 * max(0, p0_fills_total - total_fills) / p0_fills_total if p0_fills_total else 0.0
    pair_rate = total_paired / total_fills if total_fills else float("nan")
    ts = tstat(diff)

    return {
        "net_c_win": net_c_win,
        "per_fill_c": per_fill_c,
        "win_pct": win_pct,
        "maxDD_c": mdd,
        "skip_pct": skip_pct,
        "pair_rate": pair_rate,
        "t_vs_p0": ts,
        "yes_strands": yes_strands,
        "no_strands": no_strands,
        "mean_strand_cost_c": float(np.mean(strand_costs)) * 100.0 if strand_costs else 0.0,
        "n_strands": yes_strands + no_strands,
        "n_windows": n_total_w,
        "total_pnl_c": float(np.sum(pnls_arr)) * 100.0,
        "total_fills": total_fills,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    hist, tap = load_data()

    common_ws = sorted(set(hist.index) & set(tap.index))
    print(f"Windows: hist={len(hist)}, trades={len(tap)}, common={len(common_ws)}")

    all_fills = []
    for ws in common_ws:
        try:
            fills = get_fills(ws, hist, tap)
        except Exception:
            fills = []
        all_fills.append((ws, fills))

    n = len(all_fills)
    split = int(n * 0.6)
    is_data = all_fills[:split]
    oos_data = all_fills[split:]
    print(f"IS={len(is_data)}, OOS={len(oos_data)}")

    def get_p0_pnls(data):
        return [pol_p0(fills) for _, fills in data]

    p0_is = get_p0_pnls(is_data)
    p0_oos = get_p0_pnls(oos_data)

    print("\n" + "="*115)
    hdr = f"{'Variant':<20} {'Split':<5} | {'c/win':>7} {'c/fill':>7} {'win%':>6} {'maxDD':>7} {'skip%':>6} {'pairR':>6} {'t':>6} | {'YES_s':>6} {'NO_s':>5} {'s_cost':>7}"
    print(hdr)
    print("="*115)

    results = {}
    for name, gate_fn in VARIANTS:
        for split_name, data, p0_pnls in [("IS", is_data, p0_is), ("OOS", oos_data, p0_oos)]:
            m = compute_metrics(data, gate_fn, p0_pnls)
            results[(name, split_name)] = m
            print(f"{name:<20} {split_name:<5} | "
                  f"{m['net_c_win']:>7.3f} {m['per_fill_c']:>7.3f} "
                  f"{m['win_pct']:>6.1f} {m['maxDD_c']:>7.2f} "
                  f"{m['skip_pct']:>6.1f} {m['pair_rate']:>6.3f} "
                  f"{m['t_vs_p0']:>6.2f} | "
                  f"{m['yes_strands']:>6} {m['no_strands']:>5} "
                  f"{m['mean_strand_cost_c']:>7.2f}")
        print()

    print("="*115)

    # Strand decomposition
    print("\n--- STRAND DECOMPOSITION (OOS) ---")
    p0_oos_m = results[("P0", "OOS")]
    print(f"P0 OOS: {p0_oos_m['n_strands']} total strands ({p0_oos_m['yes_strands']} YES, {p0_oos_m['no_strands']} NO), "
          f"mean strand cost={p0_oos_m['mean_strand_cost_c']:.2f}c, "
          f"total PnL={p0_oos_m['total_pnl_c']:.1f}c")

    print("\n--- BOX vs STRAND DECOMPOSITION (OOS, all variants) ---")
    print(f"{'Variant':<20} {'tot_pnl_c':>10} {'skip%':>7} {'YES_str':>8} {'NO_str':>7} {'s_cost_c':>9} {'t':>6}")
    for name, _ in VARIANTS:
        m = results[(name, "OOS")]
        print(f"{name:<20} {m['total_pnl_c']:>10.1f} {m['skip_pct']:>7.1f} "
              f"{m['yes_strands']:>8} {m['no_strands']:>7} "
              f"{m['mean_strand_cost_c']:>9.2f} {m['t_vs_p0']:>6.2f}")

    # Winning variant
    print("\n--- OOS VERDICT ---")
    oos_variants = [(n, results[(n, "OOS")]) for n, _ in VARIANTS if n != "P0"]
    # rank by t_vs_p0
    by_t = sorted(oos_variants, key=lambda x: x[1]["t_vs_p0"], reverse=True)
    # rank by c/win
    by_cwin = sorted(oos_variants, key=lambda x: x[1]["net_c_win"], reverse=True)
    print(f"By t-stat: {by_t[0][0]} t={by_t[0][1]['t_vs_p0']:.2f}, c/win={by_t[0][1]['net_c_win']:.3f}, "
          f"skip={by_t[0][1]['skip_pct']:.1f}%")
    print(f"By c/win:  {by_cwin[0][0]} c/win={by_cwin[0][1]['net_c_win']:.3f}, "
          f"t={by_cwin[0][1]['t_vs_p0']:.2f}, skip={by_cwin[0][1]['skip_pct']:.1f}%")

    # Strands avoided by winner
    winner_name = by_t[0][0]
    wm = results[(winner_name, "OOS")]
    delta_yes_s = p0_oos_m["yes_strands"] - wm["yes_strands"]
    delta_no_s = p0_oos_m["no_strands"] - wm["no_strands"]
    delta_pnl = wm["total_pnl_c"] - p0_oos_m["total_pnl_c"]
    print(f"\nWinner ({winner_name}) vs P0 OOS:")
    print(f"  YES strands avoided: {delta_yes_s}, NO strands avoided: {delta_no_s}")
    print(f"  PnL delta: {delta_pnl:+.1f}c total, {wm['net_c_win']-p0_oos_m['net_c_win']:+.3f}c/win")
    print(f"  Fills skipped: {wm['skip_pct']:.1f}% of P0 opens")
    print(f"  maxDD: {wm['maxDD_c']:.2f}c vs P0: {p0_oos_m['maxDD_c']:.2f}c")

    print("\n--- IS WINNER (for reference) ---")
    is_variants = [(n, results[(n, "IS")]) for n, _ in VARIANTS if n != "P0"]
    p0_is_m = results[("P0", "IS")]
    by_t_is = sorted(is_variants, key=lambda x: x[1]["t_vs_p0"], reverse=True)
    print(f"IS best t-stat: {by_t_is[0][0]}, t={by_t_is[0][1]['t_vs_p0']:.2f}, "
          f"c/win={by_t_is[0][1]['net_c_win']:.3f} vs P0={p0_is_m['net_c_win']:.3f}")


if __name__ == "__main__":
    main()
