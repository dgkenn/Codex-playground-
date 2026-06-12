"""
asymmetry_backtest2.py -- Corrected Unpaired-Leg Asymmetry backtest
Faithful to the policy spec: per-window, time-ordered fills, |net| <= 1 leg.

Key structure revealed by data inspection:
- 96.6% of minutes have BOTH a bid AND an ask fill (same k)
- Baseline: always pair -> pnl = ask_k - bid_k = spread (~0.01c each)
- Hold strategies: at a given minute k, if pairing fill triggers hold_ok,
  skip the pair -> hold the existing leg; re-evaluate at k+1, k+2...
- End-of-window: held leg settles at res or sells back at bid13/ask13.

settle semantics (from kalshi_sizing.collect_fills):
  bid fill: settle = res - p  (net of entry cost; res in {0,1})
  ask fill: settle = a0 - res (net of entry cost; a0 = YES price we sold at)

Policy walker: uses PAIRED (ws, k) fill structure directly.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from kalshi_sizing import collect_fills

# ── helpers ──────────────────────────────────────────────────────────────────

def tstat_paired(a, b):
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[~np.isnan(d)]
    if len(d) < 8 or d.std(ddof=1) == 0:
        return float("nan")
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))

def maxdd(series):
    cum = np.cumsum(np.asarray(series, float))
    if len(cum) == 0:
        return 0.0
    return float(np.max(np.maximum.accumulate(cum) - cum))

SELLBACK_COST = 0.01  # 1c taker cost on end-of-window sell-backs

# ── build per-window minute-level fill structure ──────────────────────────────

def build_window_structure(df, hist):
    """
    Returns dict: ws -> list of minute-entries sorted by k (ascending = chronological)
    Each minute entry: dict with keys:
      k, bid (or None), ask (or None)
    bid/ask: the fill dict for that side at that minute (or None if no fill)
    """
    df2 = df.copy()
    df2["k"] = (15 * (1 - df2["tau"])).round().astype(int)

    bid_df = df2[df2.side == "bid"].set_index(["ws", "k"])
    ask_df = df2[df2.side == "ask"].set_index(["ws", "k"])

    all_ws = sorted(df2.ws.unique())
    struct = {}

    for ws in all_ws:
        all_k = set()
        if ws in bid_df.index.get_level_values(0):
            bid_rows = bid_df.xs(ws, level="ws") if (ws, ) in [(x,) for x in bid_df.index.get_level_values(0)] else bid_df.loc[ws]
            all_k |= set(bid_rows.index.tolist() if not isinstance(bid_rows.index, pd.MultiIndex) else [bid_rows.index])
        if ws in ask_df.index.get_level_values(0):
            ask_rows = ask_df.xs(ws, level="ws") if True else None
            all_k |= set(ask_rows.index.tolist() if not isinstance(ask_rows.index, pd.MultiIndex) else [ask_rows.index])

        minutes = []
        # Use direct groupby approach
        ws_fills = df2[df2.ws == ws]
        for k, grp in ws_fills.groupby("k"):
            bid_fill = grp[grp.side == "bid"].iloc[0].to_dict() if (grp.side == "bid").any() else None
            ask_fill = grp[grp.side == "ask"].iloc[0].to_dict() if (grp.side == "ask").any() else None
            minutes.append({"k": k, "bid": bid_fill, "ask": ask_fill})

        minutes.sort(key=lambda m: m["k"])
        struct[ws] = minutes

    return struct


# ── policy walker ─────────────────────────────────────────────────────────────

def run_policy(window_struct, hist, open_ok_fn, hold_ok_fn, sell_rule_fn):
    """
    Walk each window minute by minute.

    State: held_leg = None | dict (a fill dict, with side/p/settle/etc.)
    |net| <= 1: at most one open leg at any time.

    At each minute k:
      If no held leg:
        - bid fill arrives: open YES leg if open_ok_fn(bid_fill)
        - ask fill arrives: open NO leg if open_ok_fn(ask_fill)
        (if BOTH arrive same minute: bid is processed first; then ask
         either pairs it or opens alone if bid was skipped)
      If holding YES leg (bid):
        - ask fill arrives (this is the pairing fill):
          implied_yes = ask_fill["p"]
          if hold_ok_fn(held_leg, implied_yes): skip pair, keep YES
          else: PAIR -> pnl = 1 - held_leg["p"] - (1-ask_fill["p"]) = ask_fill["p"] - held_leg["p"]
                held_leg = None
        - bid fill: ignored (can't hold 2 YES)
      If holding NO leg (ask):
        - bid fill arrives (this is the pairing fill):
          implied_no = 1 - bid_fill["p"]
          if hold_ok_fn(held_leg, implied_no): skip pair
          else: PAIR -> pnl = 1 - ask_held["p"] - bid_fill["p"]
                         = ask_held["p"] - bid_fill["p"] ... wait:
                         NO leg cost = 1 - ask_held["p"], box locks 1 - bid_fill["p"] - (1-ask_held["p"])
                         = ask_held["p"] - bid_fill["p"]
                held_leg = None
        - ask fill: ignored

    End of window: sell_rule or hold to settlement.
    """
    pnl_by_win = {}
    all_ws = sorted(window_struct.keys())

    for ws in all_ws:
        minutes = window_struct[ws]
        h = hist.loc[ws]
        bid_path = np.asarray(h.bid_path, float)
        ask_path = np.asarray(h.ask_path, float)
        bid13 = bid_path[13] if not np.isnan(bid_path[13]) else float("nan")
        ask13 = ask_path[13] if not np.isnan(ask_path[13]) else float("nan")
        mid13 = (bid13 + ask13) / 2.0

        held = None
        window_pnl = 0.0

        for minute in minutes:
            k = minute["k"]
            bf = minute["bid"]
            af = minute["ask"]

            if held is None:
                # Process bid first, then ask
                if bf is not None and open_ok_fn(bf):
                    held = bf
                    # Now check if ask also arrived and can immediately pair (baseline)
                    if af is not None:
                        implied_yes = af["p"]
                        if hold_ok_fn(held, implied_yes):
                            pass  # keep holding YES
                        else:
                            # pair immediately
                            pnl = af["p"] - held["p"]
                            window_pnl += pnl
                            held = None
                elif af is not None and open_ok_fn(af):
                    held = af
                    # bid already processed above, wouldn't open (or was None)
                    # If bid exists and we now hold NO: bid is a pairing fill
                    if bf is not None and held is not None and held["side"] == "ask":
                        implied_no = 1.0 - bf["p"]
                        if hold_ok_fn(held, implied_no):
                            pass  # keep NO
                        else:
                            pnl = held["p"] - bf["p"]
                            window_pnl += pnl
                            held = None

            elif held["side"] == "bid":  # holding YES
                # Only the ask fill can pair it; bid fill ignored
                if af is not None:
                    implied_yes = af["p"]
                    if hold_ok_fn(held, implied_yes):
                        pass  # keep YES
                    else:
                        pnl = af["p"] - held["p"]
                        window_pnl += pnl
                        held = None

            elif held["side"] == "ask":  # holding NO
                if bf is not None:
                    implied_no = 1.0 - bf["p"]
                    if hold_ok_fn(held, implied_no):
                        pass  # keep NO
                    else:
                        pnl = held["p"] - bf["p"]
                        window_pnl += pnl
                        held = None

        # End of window
        if held is not None:
            if held["side"] == "bid":  # YES leg
                implied_end = mid13 if not np.isnan(mid13) else float("nan")
                if not np.isnan(implied_end) and sell_rule_fn(held, implied_end):
                    if not np.isnan(bid13):
                        pnl = bid13 - held["p"] - SELLBACK_COST
                    else:
                        pnl = held["settle"]
                else:
                    pnl = held["settle"]
            else:  # NO leg (ask fill)
                implied_end = (1.0 - mid13) if not np.isnan(mid13) else float("nan")
                if not np.isnan(implied_end) and sell_rule_fn(held, implied_end):
                    if not np.isnan(ask13):
                        pnl = held["p"] - ask13 - SELLBACK_COST
                    else:
                        pnl = held["settle"]
                else:
                    pnl = held["settle"]
            window_pnl += pnl

        pnl_by_win[ws] = window_pnl

    return pnl_by_win


# ── scoring ───────────────────────────────────────────────────────────────────

def score_diff(cand_pnl, base_pnl, all_ws, is_mask, oos_mask, label):
    c = np.array([cand_pnl.get(w, 0.0) for w in all_ws])
    b = np.array([base_pnl.get(w, 0.0) for w in all_ws])

    def m(mask, tag):
        cp = c[mask]; bp = b[mask]
        d = cp - bp
        return {
            "label": label, "split": tag,
            "n": int(mask.sum()),
            "mean_c": float(cp.mean() * 100),
            "p0_c":   float(bp.mean() * 100),
            "diff_c": float(d.mean() * 100),
            "t_diff": float(tstat_paired(cp, bp)),
            "maxDD_c": float(maxdd(cp) * 100),
            "p0DD_c":  float(maxdd(bp) * 100),
        }

    return m(is_mask, "IS"), m(oos_mask, "OOS")


# ── main ──────────────────────────────────────────────────────────────────────

def run_backtest(q0=0):
    print(f"\n{'='*76}")
    print(f"ASYMMETRY BACKTEST v2  q0={q0}")
    print(f"{'='*76}")

    hist = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
    tap  = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")

    df = collect_fills(hist, tap, q0=q0)
    print(f"Fills: {len(df)}, windows: {df.ws.nunique()}")

    wins_sorted = np.sort(df.ws.unique())
    cut_idx = int(len(wins_sorted) * 0.6)
    cut_ws  = wins_sorted[cut_idx]
    print(f"IS: {cut_idx} windows  OOS: {len(wins_sorted)-cut_idx} windows  |  cut_ws={cut_ws}")

    # Build per-window minute structure
    wstruct = build_window_structure(df, hist)
    all_ws = np.array(sorted(wstruct.keys()))
    is_mask  = all_ws < cut_ws
    oos_mask = all_ws >= cut_ws

    # ── P0: always pair (hold_ok always False) ─────────────────────────────
    p0 = run_policy(wstruct, hist,
                    open_ok_fn=lambda f: True,
                    hold_ok_fn=lambda h, implied: False,
                    sell_rule_fn=lambda h, ie: False)
    p0_arr = np.array([p0.get(w, 0.0) for w in all_ws])

    # Candidates
    candidates = []

    # C1: hold YES when implied_yes >= T
    for T in [0.70, 0.75, 0.80, 0.85]:
        candidates.append((f"C1_T{int(T*100)}", dict(
            open_ok_fn=lambda f: True,
            hold_ok_fn=lambda h, imp, T=T: (h["side"] == "bid") and (imp >= T),
            sell_rule_fn=lambda h, ie: False
        )))

    # C2: C1 + force-pair when k >= 12 (tau <= 0.2 => k >= 12)
    for T in [0.70, 0.75, 0.80, 0.85]:
        def make_c2(T):
            def hold_ok(h, imp):
                k_held = int(round(15 * (1 - h["tau"])))
                return (h["side"] == "bid") and (imp >= T) and (k_held < 12)
            return hold_ok
        candidates.append((f"C2_T{int(T*100)}", dict(
            open_ok_fn=lambda f: True,
            hold_ok_fn=make_c2(T),
            sell_rule_fn=lambda h, ie: False
        )))

    # C3: favorite-only opens (leg cost >= T0)
    for T0 in [0.35, 0.40, 0.45]:
        def make_open(T0):
            def open_ok(f):
                cost = f["p"] if f["side"] == "bid" else 1.0 - f["p"]
                return cost >= T0
            return open_ok
        candidates.append((f"C3_T{int(T0*100)}", dict(
            open_ok_fn=make_open(T0),
            hold_ok_fn=lambda h, imp: False,
            sell_rule_fn=lambda h, ie: False
        )))

    # C4: flow-confirmed hold (implied >= 0.75 AND flow not adverse to held leg)
    # flow_adv in fill: for bid fills, flow_adv = mv (spot move; >0 is adverse to a bid fill per kalshi_sizing)
    # for ask fills, flow_adv = -flow (positive = buyers dominating = adverse to ask)
    # "flow not adverse" = h["flow_adv"] <= 0
    candidates.append(("C4_flow", dict(
        open_ok_fn=lambda f: True,
        hold_ok_fn=lambda h, imp: (imp >= 0.75) and (h["flow_adv"] <= 0),
        sell_rule_fn=lambda h, ie: False
    )))

    # C5: sell adverse legs at end (implied_end <= S means the leg is underwater)
    for S in [0.30, 0.35, 0.40]:
        candidates.append((f"C5_S{int(S*100)}", dict(
            open_ok_fn=lambda f: True,
            hold_ok_fn=lambda h, imp: False,
            sell_rule_fn=lambda h, ie, S=S: (not np.isnan(ie)) and (ie <= S)
        )))

    # C6: full playbook: C3(0.40) open + C1(0.75) hold YES + C5(0.35) sell
    def c6_open(f):
        cost = f["p"] if f["side"] == "bid" else 1.0 - f["p"]
        return cost >= 0.40
    candidates.append(("C6_full", dict(
        open_ok_fn=c6_open,
        hold_ok_fn=lambda h, imp: (h["side"] == "bid") and (imp >= 0.75),
        sell_rule_fn=lambda h, ie: (not np.isnan(ie)) and (ie <= 0.35)
    )))

    # C7: NO-side favorite hold only
    candidates.append(("C7_no_fav", dict(
        open_ok_fn=lambda f: True,
        hold_ok_fn=lambda h, imp: (h["side"] == "ask") and (imp >= 0.75),
        sell_rule_fn=lambda h, ie: False
    )))

    # ── run all ────────────────────────────────────────────────────────────
    is_rows = []
    oos_rows = []

    # P0
    def p0_score(mask, tag):
        p = p0_arr[mask]
        return {"label":"P0_base","split":tag,"n":int(mask.sum()),
                "mean_c":float(p.mean()*100),"p0_c":float(p.mean()*100),
                "diff_c":0.0,"t_diff":float("nan"),
                "maxDD_c":float(maxdd(p)*100),"p0DD_c":float(maxdd(p)*100)}
    is_rows.append(p0_score(is_mask,"IS"))
    oos_rows.append(p0_score(oos_mask,"OOS"))

    for name, params in candidates:
        cand = run_policy(wstruct, hist, **params)
        ir, oor = score_diff(cand, p0, all_ws, is_mask, oos_mask, name)
        is_rows.append(ir)
        oos_rows.append(oor)

    # ── IS table ────────────────────────────────────────────────────────────
    hdr = f"{'label':<14} {'n':>5} {'mean_c':>8} {'p0_c':>8} {'diff_c':>8} {'t_diff':>7} {'maxDD_c':>8} {'p0DD_c':>7}"
    print(f"\n{'─'*76}")
    print("IS TABLE (first 60% windows)")
    print(f"{'─'*76}")
    print(hdr)
    print("─"*76)
    for r in is_rows:
        print(f"{r['label']:<14} {r['n']:>5} {r['mean_c']:>+8.3f} {r['p0_c']:>+8.3f} "
              f"{r['diff_c']:>+8.3f} {r['t_diff']:>+7.2f} {r['maxDD_c']:>8.2f} {r['p0DD_c']:>7.2f}")

    # ── best per family ──────────────────────────────────────────────────────
    fam_rows = {"C1":[],"C2":[],"C3":[],"C5":[]}
    for r in is_rows:
        for f in fam_rows:
            if r["label"].startswith(f):
                fam_rows[f].append(r)
    picked = {}
    for fam, rows in fam_rows.items():
        if rows:
            best = max(rows, key=lambda r: r["diff_c"])
            picked[fam] = best["label"]
    for single in ["C4_flow","C6_full","C7_no_fav"]:
        picked[single] = single
    picked["P0_base"] = "P0_base"
    picked_labels = set(picked.values())
    print(f"\nIS-picked per family: {sorted(v for k,v in picked.items() if k != 'P0_base')}")

    # ── OOS table ────────────────────────────────────────────────────────────
    p0_oos_dd = next(r["maxDD_c"] for r in oos_rows if r["label"]=="P0_base")
    print(f"\n{'─'*76}")
    print("OOS TABLE (last 40% windows, IS-picked variants)")
    print(f"{'─'*76}")
    print(hdr)
    print("─"*76)
    survivors = []
    for r in oos_rows:
        if r["label"] not in picked_labels:
            continue
        is_r = next((x for x in is_rows if x["label"]==r["label"]), None)
        is_ok  = (is_r is not None) and (is_r["diff_c"] > 0)
        oos_ok = r["diff_c"] > 0
        t_ok   = (r["t_diff"] >= 1.5) or np.isnan(r["t_diff"])
        dd_ok  = (r["maxDD_c"] <= 1.25 * p0_oos_dd) if p0_oos_dd > 0 else True
        flag = ""
        if r["label"] != "P0_base":
            survives = is_ok and oos_ok and t_ok and dd_ok
            flag = "  <<SURVIVES>>" if survives else ""
            if survives:
                survivors.append(r["label"])
        print(f"{r['label']:<14} {r['n']:>5} {r['mean_c']:>+8.3f} {r['p0_c']:>+8.3f} "
              f"{r['diff_c']:>+8.3f} {r['t_diff']:>+7.2f} {r['maxDD_c']:>8.2f} {r['p0DD_c']:>7.2f}{flag}")

    print(f"\nSURVIVORS: {survivors if survivors else 'NONE'}")
    return is_rows, oos_rows, survivors


if __name__ == "__main__":
    import os
    os.chdir("/home/user/Codex-playground-")
    r0  = run_backtest(q0=0)
    r500 = run_backtest(q0=500)
    print("\n\nDONE.")
