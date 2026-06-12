"""
asymmetry_backtest.py -- Unpaired-Leg Asymmetry strategies backtest
Family of strategies that exploit favorite-longshot bias by selectively
holding open legs rather than always pairing.

Usage: python asymmetry_backtest.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from kalshi_sizing import collect_fills

# ─── helpers ────────────────────────────────────────────────────────────────

def tstat_paired(a, b):
    """Paired t-stat of a - b, excluding NaN."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[~np.isnan(d)]
    if len(d) < 8 or d.std(ddof=1) == 0:
        return float("nan")
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))

def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))

def maxdd(series):
    """Max drawdown of cumulative PnL series."""
    cum = np.cumsum(series)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0

# ─── policy walker ──────────────────────────────────────────────────────────

def run_policy(wins_fills, policy_name, policy_params, bid_path_map, ask_path_map, mid_path_map):
    """
    Walk fills window-by-window, apply open_ok / hold_ok / sell_rule policies.

    wins_fills: dict ws -> list of fill-rows (namedtuple-like dicts)
    policy: dict with keys open_ok, hold_ok, sell_rule (callables)
    bid_path_map, ask_path_map, mid_path_map: ws -> array[15]

    Returns per-window PnL list in chronological window order.
    """
    open_ok_fn = policy_params.get("open_ok", lambda f: True)
    hold_ok_fn = policy_params.get("hold_ok", lambda h, implied: False)
    sell_rule_fn = policy_params.get("sell_rule", lambda h, implied_end: False)

    pnl_by_win = {}
    all_ws = sorted(wins_fills.keys())

    for ws in all_ws:
        fills = wins_fills[ws]
        bid13 = bid_path_map[ws][13]
        ask13 = ask_path_map[ws][13]
        mid13 = mid_path_map[ws][13]

        # Sort fills by tau DESC = chronological (k=2 is tau=0.87, k=12 is tau=0.2)
        # tau = (15-k)/15 so higher tau = earlier in window
        fills_sorted = sorted(fills, key=lambda f: -f["tau"])

        held_yes = None  # holding a YES leg (bid fill)
        held_no = None   # holding a NO leg (ask fill)
        window_pnl = 0.0

        for f in fills_sorted:
            side = f["side"]

            if side == "bid":
                # YES leg fill: our cost = f["p"] (YES price)
                leg_cost = f["p"]
                if held_yes is None:
                    # No current YES leg - check if we can open
                    if open_ok_fn(f):
                        held_yes = f
                    # If open not ok, skip this fill
                elif held_no is not None:
                    # We hold a NO leg already; this BID might pair it
                    # implied NO value = 1 - f["p"] (YES bid price)
                    implied_no = 1.0 - f["p"]
                    if hold_ok_fn(held_no, implied_no):
                        pass  # keep riding NO leg
                    else:
                        # PAIR: pnl = held_no entry + this YES leg fill
                        # Box: we sold NO at (1-held_no["p"]) and buy NO back via pairing
                        # Box pnl = 1 - (held_no["p"] + f["p"]) = 1 - held_no["p"] - f["p"]
                        box_pnl = 1.0 - held_no["p"] - f["p"]
                        window_pnl += box_pnl
                        held_no = None
                        # Now we have a fresh BID fill - open YES leg if allowed
                        if open_ok_fn(f):
                            held_yes = f
                    # Don't open a second YES if we already hold one
                else:
                    # We hold a YES leg; ignore additional YES fills (|net|<=1 leg constraint)
                    pass

            elif side == "ask":
                # NO leg fill: a0 = f["p"], our NO cost = 1 - f["p"]
                leg_cost = 1.0 - f["p"]
                if held_no is None:
                    if open_ok_fn(f):
                        held_no = f
                elif held_yes is not None:
                    # We hold a YES leg; this ASK pairs it
                    # implied YES value = f["p"] (ask price = YES ask at that minute)
                    implied_yes = f["p"]
                    if hold_ok_fn(held_yes, implied_yes):
                        pass  # keep riding YES leg
                    else:
                        # PAIR: box_pnl = 1 - YES_cost - NO_cost = 1 - held_yes["p"] - (1-f["p"]) = f["p"] - held_yes["p"]
                        box_pnl = 1.0 - held_yes["p"] - (1.0 - f["p"])
                        window_pnl += box_pnl
                        held_yes = None
                        if open_ok_fn(f):
                            held_no = f
                else:
                    pass  # already hold NO, skip

        # End of window: settle or sell-back remaining held legs
        SELLBACK_COST = 0.01  # 1c taker fee on sellbacks

        if held_yes is not None:
            implied_end_yes = (bid13 + ask13) / 2.0 if not np.isnan(bid13 + ask13) else held_yes["settle"] + held_yes["p"]
            if sell_rule_fn(held_yes, implied_end_yes):
                # Sell YES at bid13
                if not np.isnan(bid13):
                    pnl = bid13 - held_yes["p"] - SELLBACK_COST
                else:
                    pnl = held_yes["settle"] - held_yes["p"]
            else:
                # Hold to settlement
                pnl = held_yes["settle"]  # settle = res - p  (already net of entry)
            window_pnl += pnl
            held_yes = None

        if held_no is not None:
            implied_end_no = 1.0 - ((bid13 + ask13) / 2.0) if not np.isnan(bid13 + ask13) else held_no["settle"] + (1.0 - held_no["p"])
            if sell_rule_fn(held_no, implied_end_no):
                # Buy back YES at ask13 -> NO pnl = entry_a0 - ask13 - SELLBACK_COST
                if not np.isnan(ask13):
                    pnl = held_no["p"] - ask13 - SELLBACK_COST
                else:
                    pnl = held_no["settle"]
            else:
                pnl = held_no["settle"]
            window_pnl += pnl
            held_no = None

        pnl_by_win[ws] = window_pnl

    return pnl_by_win


def baseline_policy(wins_fills, bid_path_map, ask_path_map, mid_path_map):
    """P0: always-pair baseline. Any pairing fill closes the pair immediately."""
    params = {
        "open_ok": lambda f: True,
        "hold_ok": lambda h, implied: False,
        "sell_rule": lambda h, implied_end: False,
    }
    return run_policy(wins_fills, "P0", params, bid_path_map, ask_path_map, mid_path_map)


# ─── build fills dict ───────────────────────────────────────────────────────

def build_wins_fills(df):
    """Group fills DataFrame into dict ws -> list of fill dicts."""
    d = {}
    for row in df.itertuples(index=False):
        ws = row.ws
        if ws not in d:
            d[ws] = []
        d[ws].append({
            "ws": row.ws,
            "side": row.side,
            "p": row.p,
            "settle": row.settle,
            "markout": row.markout,
            "sig_adv": row.sig_adv,
            "spread": row.spread,
            "tau": row.tau,
            "flow_adv": row.flow_adv,
        })
    return d


# ─── metrics ────────────────────────────────────────────────────────────────

def score(pnl_by_win, p0_pnl_by_win, label, is_mask, oos_mask):
    """Return dict of IS and OOS metrics."""
    all_ws = sorted(set(pnl_by_win.keys()) | set(p0_pnl_by_win.keys()))
    ws_arr = np.array(all_ws)
    pnl_arr = np.array([pnl_by_win.get(w, 0.0) for w in all_ws])
    p0_arr  = np.array([p0_pnl_by_win.get(w, 0.0) for w in all_ws])

    def metrics_split(mask, tag):
        p = pnl_arr[mask]
        b = p0_arr[mask]
        diff = p - b
        n = mask.sum()
        return {
            "label": label,
            "split": tag,
            "n_wins": int(n),
            "mean_pnl_c": float(np.mean(p) * 100),
            "p0_pnl_c":   float(np.mean(b) * 100),
            "diff_c":     float(np.mean(diff) * 100),
            "t_diff":     float(tstat_paired(p, b)),
            "maxDD_c":    float(maxdd(p) * 100),
            "p0_maxDD_c": float(maxdd(b) * 100),
        }

    return metrics_split(is_mask, "IS"), metrics_split(oos_mask, "OOS")


# ─── main backtest ──────────────────────────────────────────────────────────

def run_backtest(q0=0):
    print(f"\n{'='*70}")
    print(f"ASYMMETRY BACKTEST  q0={q0}")
    print(f"{'='*70}")

    hist = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
    tap  = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")

    df = collect_fills(hist, tap, q0=q0)
    print(f"Total fills: {len(df)}, windows: {df.ws.nunique()}")

    # IS/OOS split (60/40 by chronological window)
    wins_sorted = np.sort(df.ws.unique())
    cut_idx = int(len(wins_sorted) * 0.6)
    cut_ws  = wins_sorted[cut_idx]
    print(f"IS windows: {cut_idx}  (ws < {cut_ws}), OOS: {len(wins_sorted)-cut_idx}")

    # Build per-window path maps
    bid_path_map = {ws: np.asarray(hist.loc[ws].bid_path, float) for ws in df.ws.unique() if ws in hist.index}
    ask_path_map = {ws: np.asarray(hist.loc[ws].ask_path, float) for ws in df.ws.unique() if ws in hist.index}
    mid_path_map = {ws: np.asarray(hist.loc[ws].mid_path, float) for ws in df.ws.unique() if ws in hist.index}

    wins_fills = build_wins_fills(df)

    # IS/OOS masks over all windows (union of both policies)
    all_ws = np.array(sorted(wins_fills.keys()))
    is_mask  = all_ws < cut_ws
    oos_mask = all_ws >= cut_ws

    # ── P0 baseline ──────────────────────────────────────────────────────
    p0_pnl = baseline_policy(wins_fills, bid_path_map, ask_path_map, mid_path_map)
    p0_arr = np.array([p0_pnl.get(w, 0.0) for w in all_ws])

    # ── candidate definitions ────────────────────────────────────────────
    candidates = []

    # C1: hold-favorite
    for T in [0.70, 0.75, 0.80, 0.85]:
        candidates.append((
            f"C1_T{int(T*100)}",
            {
                "open_ok": lambda f: True,
                "hold_ok": lambda h, implied, T=T: implied >= T,
                "sell_rule": lambda h, implied_end: False,
            }
        ))

    # C2: hold-favorite + late force-pair (never hold when k >= 12)
    # k of pairing fill: tau = (15-k)/15 => k = 15*(1-tau); force pair if 15*(1-tau) >= 12 => tau <= 0.2
    for T in [0.70, 0.75, 0.80, 0.85]:
        candidates.append((
            f"C2_T{int(T*100)}",
            {
                "open_ok": lambda f: True,
                "hold_ok": lambda h, implied, T=T: (implied >= T) and (15*(1-h["tau"]) < 12),
                "sell_rule": lambda h, implied_end: False,
            }
        ))

    # C3: favorite-only opens
    # leg cost: 'bid' -> f.p; 'ask' -> 1-f.p
    for T0 in [0.35, 0.40, 0.45]:
        def make_open_ok(T0=T0):
            def open_ok(f):
                cost = f["p"] if f["side"] == "bid" else 1.0 - f["p"]
                return cost >= T0
            return open_ok
        candidates.append((
            f"C3_T{int(T0*100)}",
            {
                "open_ok": make_open_ok(T0),
                "hold_ok": lambda h, implied: False,
                "sell_rule": lambda h, implied_end: False,
            }
        ))

    # C4: flow-confirmed hold
    candidates.append((
        "C4_flow",
        {
            "open_ok": lambda f: True,
            "hold_ok": lambda h, implied: (implied >= 0.75) and (h["flow_adv"] <= 0),
            "sell_rule": lambda h, implied_end: False,
        }
    ))

    # C5: sell-adverse-at-end
    for S in [0.30, 0.35, 0.40]:
        candidates.append((
            f"C5_S{int(S*100)}",
            {
                "open_ok": lambda f: True,
                "hold_ok": lambda h, implied: False,
                "sell_rule": lambda h, implied_end, S=S: implied_end <= S,
            }
        ))

    # C6: FULL PLAYBOOK: C3(0.40) opens + C1(0.75) hold + C5(0.35) sell
    def c6_open_ok(f):
        cost = f["p"] if f["side"] == "bid" else 1.0 - f["p"]
        return cost >= 0.40
    candidates.append((
        "C6_full",
        {
            "open_ok": c6_open_ok,
            "hold_ok": lambda h, implied: implied >= 0.75,
            "sell_rule": lambda h, implied_end: implied_end <= 0.35,
        }
    ))

    # C7: NO-side favorite hold
    candidates.append((
        "C7_no_fav",
        {
            "open_ok": lambda f: True,
            "hold_ok": lambda h, implied: (implied >= 0.75) and (h["side"] == "ask"),
            "sell_rule": lambda h, implied_end: False,
        }
    ))

    # ── run all candidates ────────────────────────────────────────────────
    all_is_rows = []
    all_oos_rows = []

    # P0 baseline IS/OOS
    p0_is_row = {
        "label": "P0_base",
        "split": "IS",
        "n_wins": int(is_mask.sum()),
        "mean_pnl_c": float(np.mean(p0_arr[is_mask]) * 100),
        "p0_pnl_c":   float(np.mean(p0_arr[is_mask]) * 100),
        "diff_c":     0.0,
        "t_diff":     float("nan"),
        "maxDD_c":    float(maxdd(p0_arr[is_mask]) * 100),
        "p0_maxDD_c": float(maxdd(p0_arr[is_mask]) * 100),
    }
    p0_oos_row = {
        "label": "P0_base",
        "split": "OOS",
        "n_wins": int(oos_mask.sum()),
        "mean_pnl_c": float(np.mean(p0_arr[oos_mask]) * 100),
        "p0_pnl_c":   float(np.mean(p0_arr[oos_mask]) * 100),
        "diff_c":     0.0,
        "t_diff":     float("nan"),
        "maxDD_c":    float(maxdd(p0_arr[oos_mask]) * 100),
        "p0_maxDD_c": float(maxdd(p0_arr[oos_mask]) * 100),
    }
    all_is_rows.append(p0_is_row)
    all_oos_rows.append(p0_oos_row)

    for name, policy in candidates:
        pnl = run_policy(wins_fills, name, policy, bid_path_map, ask_path_map, mid_path_map)
        is_row, oos_row = score(pnl, p0_pnl, name, is_mask, oos_mask)
        all_is_rows.append(is_row)
        all_oos_rows.append(oos_row)

    # ── format and print IS table ────────────────────────────────────────
    print(f"\n{'─'*90}")
    print("IS TABLE (first 60% of windows by ws)")
    print(f"{'─'*90}")
    hdr = f"{'label':<14} {'n':>5} {'mean_c':>8} {'p0_c':>8} {'diff_c':>8} {'t_diff':>7} {'maxDD_c':>8} {'p0DD_c':>8}"
    print(hdr)
    print("─"*90)
    for r in all_is_rows:
        print(f"{r['label']:<14} {r['n_wins']:>5} {r['mean_pnl_c']:>+8.3f} {r['p0_pnl_c']:>+8.3f} "
              f"{r['diff_c']:>+8.3f} {r['t_diff']:>+7.2f} {r['maxDD_c']:>8.2f} {r['p0_maxDD_c']:>8.2f}")

    # ── select best per family on IS ─────────────────────────────────────
    # For families with multiple thresholds, pick best IS diff_c
    families = {"C1": [], "C2": [], "C3": [], "C5": []}
    for r in all_is_rows:
        for fam in families:
            if r["label"].startswith(fam):
                families[fam].append(r)

    best_per_family = {}
    for fam, rows in families.items():
        if rows:
            best = max(rows, key=lambda r: r["diff_c"])
            best_per_family[fam] = best["label"]

    # Singles always included
    for single in ["C4_flow", "C6_full", "C7_no_fav"]:
        best_per_family[single] = single

    picked_labels = set(best_per_family.values()) | {"P0_base"}
    print(f"\nIS-picked best per family: {sorted(best_per_family.values())}")

    # ── OOS table (IS-picked variants) ──────────────────────────────────
    print(f"\n{'─'*90}")
    print("OOS TABLE (last 40% of windows, IS-picked variants only)")
    print(f"{'─'*90}")
    print(hdr)
    print("─"*90)
    p0_oos_maxdd = p0_oos_row["maxDD_c"]
    survivors = []
    for r in all_oos_rows:
        if r["label"] not in picked_labels:
            continue
        # Survivor criteria check
        is_r = next((x for x in all_is_rows if x["label"] == r["label"]), None)
        is_diff_pos = (is_r is not None) and (is_r["diff_c"] > 0)
        oos_diff_pos = r["diff_c"] > 0
        oos_t_ok = r["t_diff"] >= 1.5 or np.isnan(r["t_diff"])  # nan for P0
        dd_ok = r["maxDD_c"] <= 1.25 * p0_oos_maxdd if p0_oos_maxdd > 0 else True
        survived = is_diff_pos and oos_diff_pos and oos_t_ok and dd_ok
        flag = " <<SURVIVES>>" if (survived and r["label"] != "P0_base") else ""
        print(f"{r['label']:<14} {r['n_wins']:>5} {r['mean_pnl_c']:>+8.3f} {r['p0_pnl_c']:>+8.3f} "
              f"{r['diff_c']:>+8.3f} {r['t_diff']:>+7.2f} {r['maxDD_c']:>8.2f} {r['p0_maxDD_c']:>8.2f}{flag}")
        if survived and r["label"] != "P0_base":
            survivors.append(r["label"])

    print(f"\nSURVIVORS (diff>0 IS+OOS, OOS t>=1.5, maxDD<=1.25x P0): {survivors if survivors else 'NONE'}")
    return all_is_rows, all_oos_rows, survivors


if __name__ == "__main__":
    import os
    os.chdir("/home/user/Codex-playground-")
    results_q0   = run_backtest(q0=0)
    results_q500 = run_backtest(q0=500)
    print("\n\nDONE.")
