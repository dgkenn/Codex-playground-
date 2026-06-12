"""multi_asset_study.py -- Multi-asset box-harvest tape replay.
Compact output only. Re-runnable. Read-only.

Tasks:
  1. Per-asset P0 baseline (IS+OOS 60/40 time split)
  2. Strand asymmetry by side
  3. Capacity: flow-bound max contracts/window + implied $/day
  4. Gate transfer: vpin<=0.40 and combo_tox_gate (vpin proxy) on OOS
  5. Hazard: last-120s fills vs earlier fills
  6. Summary tables for MULTI_ASSET.md

Run: python multi_asset_study.py
"""
import numpy as np
import pandas as pd
import sys, os
os.chdir("/home/user/Codex-playground-")
sys.path.insert(0, "/home/user/Codex-playground-")

from box_policy_ab import combo_tox_p, _COMBO_THRESH
from informed_detectors import vpin_buckets, vpin_at

ASSETS = ["btc", "eth", "sol", "xrp"]
MM_SIZE = {"btc": 265, "eth": 20, "sol": 30, "xrp": 10}  # per brief


def arr(x): return np.asarray(x, float)


def load_asset(asset):
    h = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    t = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    return h, t


def replay_asset_v2(asset):
    h, t = load_asset(asset)
    common = sorted(set(h.index) & set(t.index))
    window_recs = []
    all_fills_out = []
    for ws in common:
        h_row = h.loc[ws]
        t_row = t.loc[ws]
        bid = arr(h_row["bid_path"])
        ask = arr(h_row["ask_path"])
        res = int(h_row["res_up"])
        t_arr = arr(t_row["t"])
        p_arr = arr(t_row["p"])
        sz_arr = arr(t_row["sz"])
        buy_arr = arr(t_row["buy"]).astype(bool)
        bt, bi = vpin_buckets(t_arr, sz_arr, buy_arr)
        fills = []
        taker_flow_at_touch = 0.0
        for k in range(2, 13):
            b0, a0 = bid[k], ask[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
                continue
            lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            qb = qa = 0.0
            done_b = done_a = False
            for i in range(i0, i1):
                p = float(p_arr[i]); sz = float(sz_arr[i]); buy = bool(buy_arr[i])
                tf = float(t_arr[i])
                is_last120 = (tf >= ws + 15 * 60 - 120)
                hits_bid = (not buy and p <= b0 + 1e-9)
                hits_ask = (buy and p >= a0 - 1e-9)
                if hits_bid or hits_ask:
                    taker_flow_at_touch += sz
                if not done_b and hits_bid:
                    if qb >= sz:
                        qb -= sz
                    else:
                        vp = vpin_at(bt, bi, tf)
                        fills.append({
                            "side": "bid", "settle": float(res) - b0,
                            "k": k, "p_yes": b0, "vpin": vp,
                            "t_fill": tf, "is_last120": is_last120, "sz": sz, "ws": ws,
                            "det_take_n": None, "det_d1_maxrun": None, "det_d2_lambda": None,
                            "det_d1_nruns": None, "det_d4_roundfrac": None, "det_d5_sweep": None,
                        })
                        done_b = True
                if not done_a and hits_ask:
                    if qa >= sz:
                        qa -= sz
                    else:
                        vp = vpin_at(bt, bi, tf)
                        fills.append({
                            "side": "ask", "settle": a0 - float(res),
                            "k": k, "p_yes": round(1.0 - a0, 4), "vpin": vp,
                            "t_fill": tf, "is_last120": is_last120, "sz": sz, "ws": ws,
                            "det_take_n": None, "det_d1_maxrun": None, "det_d2_lambda": None,
                            "det_d1_nruns": None, "det_d4_roundfrac": None, "det_d5_sweep": None,
                        })
                        done_a = True
                if done_b and done_a:
                    break
        if not fills:
            continue
        # P0 walk: always-pair
        net = 0; pnl = 0.0; open_leg = None; boxes = 0; strands = 0; strand_fills = []
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net + step
            if abs(nn) > 1: continue
            if open_leg is not None and abs(nn) < abs(net):
                pnl += f["settle"] + open_leg["settle"]; boxes += 1; open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            pnl += open_leg["settle"]; strands += 1; strand_fills.append(open_leg)
        window_recs.append({
            "ws": ws, "pnl": pnl, "n_fills": len(fills),
            "boxes": boxes, "strands": strands, "strand_fills": strand_fills,
            "taker_flow": taker_flow_at_touch, "fills": fills,
        })
        all_fills_out.extend(fills)
    return window_recs, all_fills_out


def compute_stats(window_recs, all_fills, mm_size, asset):
    n = len(window_recs)
    if n == 0: return None
    wss = np.array([r["ws"] for r in window_recs])
    cut_idx = int(n * 0.6)
    is_mask = np.arange(n) < cut_idx
    oos_mask = ~is_mask
    pnl_arr = np.array([r["pnl"] for r in window_recs])
    nf_arr = np.array([r["n_fills"] for r in window_recs])
    strands_arr = np.array([r["strands"] for r in window_recs])
    boxes_arr = np.array([r["boxes"] for r in window_recs])
    flow_arr = np.array([r["taker_flow"] for r in window_recs])

    total_boxes = boxes_arr.sum()
    total_strands = strands_arr.sum()
    pair_rate = total_boxes / max(total_boxes + total_strands, 1)
    sf_all = [f for r in window_recs for f in r["strand_fills"]]
    strand_cost = float(np.mean([f["settle"] for f in sf_all]) * 100) if sf_all else float("nan")

    is_net = pnl_arr[is_mask].mean() * 100 if is_mask.any() else float("nan")
    oos_net = pnl_arr[oos_mask].mean() * 100 if oos_mask.any() else float("nan")

    cum_oos = np.cumsum(pnl_arr[oos_mask]) * 100 if oos_mask.any() else np.array([0.0])
    oos_maxdd = float(np.max(np.maximum.accumulate(cum_oos) - cum_oos)) if len(cum_oos) else 0.0

    sf_yes = [f for f in sf_all if f["side"] == "bid"]
    sf_no  = [f for f in sf_all if f["side"] == "ask"]
    yes_strand_settle = float(np.mean([f["settle"] for f in sf_yes]) * 100) if sf_yes else float("nan")
    no_strand_settle  = float(np.mean([f["settle"] for f in sf_no]) * 100)  if sf_no  else float("nan")

    mean_flow = flow_arr.mean() if len(flow_arr) else 0.0
    cap_per_win = min(mm_size, mean_flow)
    windows_per_day = 96
    net_per_win_usd = pnl_arr[oos_mask].mean() if oos_mask.any() else pnl_arr.mean()
    implied_daily = cap_per_win * net_per_win_usd * windows_per_day

    # Gates (OOS)
    oos_recs = [r for r, m in zip(window_recs, oos_mask) if m]
    vpin_pnls = []; combo_pnls = []
    vpin_total_strands = []; combo_total_fills = []
    for r in oos_recs:
        fills = r["fills"]
        # VPIN gate walk
        net2 = 0; pnl2 = 0.0; open2 = None; vs = 0
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net2 + step
            if abs(nn) > 1: continue
            pairing = (open2 is not None and abs(nn) < abs(net2))
            if not pairing:
                vp = f.get("vpin")
                if vp is not None and not np.isnan(vp) and vp > 0.40:
                    continue
            if open2 is not None and abs(nn) < abs(net2):
                pnl2 += f["settle"] + open2["settle"]; open2 = None
            else:
                open2 = f
            net2 = nn
        if open2 is not None:
            pnl2 += open2["settle"]; vs += 1
        vpin_pnls.append(pnl2)
        vpin_total_strands.append(vs)
        # COMBO gate walk (vpin-only since det_ fields not in parquet)
        net3 = 0; pnl3 = 0.0; open3 = None
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net3 + step
            if abs(nn) > 1: continue
            pairing = (open3 is not None and abs(nn) < abs(net3))
            if not pairing:
                cp = combo_tox_p(f)  # returns None since det_ fields are None
                if cp is not None and cp > _COMBO_THRESH:
                    continue
            if open3 is not None and abs(nn) < abs(net3):
                pnl3 += f["settle"] + open3["settle"]; open3 = None
            else:
                open3 = f
            net3 = nn
        if open3 is not None:
            pnl3 += open3["settle"]
        combo_pnls.append(pnl3)

    vpin_oos_net = float(np.mean(vpin_pnls) * 100) if vpin_pnls else float("nan")
    combo_oos_net = float(np.mean(combo_pnls) * 100) if combo_pnls else float("nan")
    vpin_strand_rate = float(np.mean(vpin_total_strands)) if vpin_total_strands else float("nan")

    # Hazard
    early_settles = [f["settle"] * 100 for f in all_fills if not f["is_last120"]]
    late_settles  = [f["settle"] * 100 for f in all_fills if f["is_last120"]]
    late_pct = len(late_settles) / max(len(all_fills), 1) * 100
    early_sz = [f["sz"] for f in all_fills if not f["is_last120"]]
    late_sz  = [f["sz"] for f in all_fills if f["is_last120"]]

    return {
        "asset": asset,
        "n_windows": n, "n_windows_is": int(is_mask.sum()), "n_windows_oos": int(oos_mask.sum()),
        "fills_per_win": round(nf_arr.mean(), 2),
        "pair_rate": round(pair_rate, 3),
        "strands_per_win": round(strands_arr.mean(), 3),
        "strand_cost_c": round(strand_cost, 2),
        "is_net_c": round(is_net, 3),
        "oos_net_c": round(oos_net, 3),
        "oos_maxdd_c": round(oos_maxdd, 2),
        "yes_strand_settle_c": round(yes_strand_settle, 2),
        "no_strand_settle_c": round(no_strand_settle, 2),
        "n_yes_strands": len(sf_yes), "n_no_strands": len(sf_no),
        "mean_flow_per_win": round(mean_flow, 1),
        "mm_size": mm_size, "cap_per_win": round(cap_per_win, 1),
        "implied_daily_usd": round(implied_daily, 2),
        "vpin_oos_net_c": round(vpin_oos_net, 3),
        "combo_oos_net_c": round(combo_oos_net, 3),
        "vpin_strand_rate": round(vpin_strand_rate, 3),
        "late_fill_pct": round(late_pct, 1),
        "late_mean_settle_c": round(float(np.mean(late_settles) if late_settles else float("nan")), 3),
        "early_mean_settle_c": round(float(np.mean(early_settles) if early_settles else float("nan")), 3),
        "late_mean_sz": round(float(np.mean(late_sz) if late_sz else float("nan")), 3),
        "early_mean_sz": round(float(np.mean(early_sz) if early_sz else float("nan")), 3),
        "n_late_fills": len(late_settles), "n_early_fills": len(early_settles),
    }


def maxdd(series):
    cum = np.cumsum(series)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0


def main():
    results = {}
    all_stats = []
    print("=" * 72)
    print("MULTI-ASSET BOX HARVEST TAPE REPLAY (P0, q0=0, 60/40 IS/OOS)")
    print("=" * 72)
    for asset in ASSETS:
        print(f"  Replaying {asset.upper()}...", end="", flush=True)
        try:
            wrecs, afills = replay_asset_v2(asset)
            stats = compute_stats(wrecs, afills, MM_SIZE[asset], asset)
            results[asset] = (wrecs, afills, stats)
            print(f" {len(wrecs)} windows, {len(afills)} fills")
            all_stats.append(stats)
        except Exception as e:
            print(f" ERROR: {e}")
            import traceback; traceback.print_exc()

    print()
    # ── TASK 1 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("TASK 1: PER-ASSET P0 BASELINE  (always-pair, q0=0, 60/40 split)")
    print("=" * 72)
    print(f"{'Asset':>5} {'N':>5} {'N_IS':>5} {'N_OOS':>6} {'IS_c':>8} {'OOS_c':>8} "
          f"{'F/W':>6} {'PairR':>7} {'Str/W':>7} {'StrCst':>8} {'OOS_DD':>8}")
    print("-" * 72)
    for s in all_stats:
        if s is None: continue
        print(f"{s['asset'].upper():>5} {s['n_windows']:>5} {s['n_windows_is']:>5} {s['n_windows_oos']:>6} "
              f"{s['is_net_c']:>+8.3f} {s['oos_net_c']:>+8.3f} "
              f"{s['fills_per_win']:>6.2f} {s['pair_rate']:>7.3f} "
              f"{s['strands_per_win']:>7.3f} {s['strand_cost_c']:>+8.2f} {s['oos_maxdd_c']:>+8.2f}")

    print()
    # ── TASK 2 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("TASK 2: STRAND ASYMMETRY BY SIDE")
    print("=" * 72)
    print(f"{'Asset':>5} {'N_YES':>7} {'YES_c':>8} {'N_NO':>7} {'NO_c':>8} {'Note':>20}")
    print("-" * 72)
    for s in all_stats:
        if s is None: continue
        note = ""
        if not np.isnan(s['yes_strand_settle_c']) and not np.isnan(s['no_strand_settle_c']):
            note = "YES worse" if s['yes_strand_settle_c'] < s['no_strand_settle_c'] else "NO worse / ~equal"
        print(f"{s['asset'].upper():>5} {s['n_yes_strands']:>7} {s['yes_strand_settle_c']:>+8.2f} "
              f"{s['n_no_strands']:>7} {s['no_strand_settle_c']:>+8.2f} {note:>20}")

    print()
    # ── TASK 3 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("TASK 3: CAPACITY & IMPLIED $/DAY  (96 windows/day, q0=0)")
    print("=" * 72)
    print(f"{'Asset':>5} {'MM_sz':>7} {'FlowPerW':>10} {'CapPerW':>9} {'OOS_c':>8} {'Impl$/d':>10}")
    print("-" * 72)
    total_daily = 0.0; btc_daily = None
    for s in all_stats:
        if s is None: continue
        print(f"{s['asset'].upper():>5} {s['mm_size']:>7} {s['mean_flow_per_win']:>10.1f} "
              f"{s['cap_per_win']:>9.1f} {s['oos_net_c']:>+8.3f} {s['implied_daily_usd']:>+10.2f}")
        total_daily += s['implied_daily_usd']
        if s['asset'] == 'btc': btc_daily = s['implied_daily_usd']
    print(f"\n  TOTAL (all 4 assets):  ${total_daily:+.2f}/day")
    if btc_daily is not None and btc_daily != 0:
        uplift = (total_daily / btc_daily - 1) * 100
        print(f"  BTC-only:              ${btc_daily:+.2f}/day")
        print(f"  Multi-asset uplift:    {uplift:+.1f}% vs BTC-only")

    print()
    # ── TASK 4 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("TASK 4: GATE TRANSFER  (OOS; combo uses vpin-only proxy)")
    print("=" * 72)
    print(f"{'Asset':>5} {'P0_OOS':>9} {'VPIN_OOS':>10} {'Combo_OOS':>11} {'VPIN_d':>8} {'Combo_d':>9}")
    print("-" * 72)
    for s in all_stats:
        if s is None: continue
        vd = s['vpin_oos_net_c'] - s['oos_net_c']
        cd = s['combo_oos_net_c'] - s['oos_net_c']
        print(f"{s['asset'].upper():>5} {s['oos_net_c']:>+9.3f} {s['vpin_oos_net_c']:>+10.3f} "
              f"{s['combo_oos_net_c']:>+11.3f} {vd:>+8.3f} {cd:>+9.3f}")

    print()
    # ── TASK 5 ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("TASK 5: HAZARD — LAST 120s vs EARLIER FILLS (all windows, q0=0)")
    print("=" * 72)
    print(f"{'Asset':>5} {'Late%':>7} {'EarlySt':>9} {'LateSt':>9} {'EarlySz':>9} {'LateSz':>9} {'SzR':>6}")
    print("-" * 72)
    for s in all_stats:
        if s is None: continue
        szr = (s['late_mean_sz'] / s['early_mean_sz']
               if s['early_mean_sz'] > 0 and not np.isnan(s['late_mean_sz']) else float("nan"))
        print(f"{s['asset'].upper():>5} {s['late_fill_pct']:>7.1f}% "
              f"{s['early_mean_settle_c']:>+9.3f} {s['late_mean_settle_c']:>+9.3f} "
              f"{s['early_mean_sz']:>9.3f} {s['late_mean_sz']:>9.3f} {szr:>6.2f}x")

    try:
        from scipy import stats as scipy_stats
        print("\n  t-test late vs early settle per asset:")
        for asset in ASSETS:
            if asset not in results: continue
            _, afills, s = results[asset]
            if s is None: continue
            early = [f["settle"] * 100 for f in afills if not f["is_last120"]]
            late  = [f["settle"] * 100 for f in afills if f["is_last120"]]
            if early and late and len(late) > 5:
                tv, pv = scipy_stats.ttest_ind(late, early, equal_var=False)
                print(f"  {asset.upper()}: diff={np.mean(late)-np.mean(early):+.3f}c  "
                      f"t={tv:+.2f}  p={pv:.3f}  n_late={len(late)}  n_early={len(early)}")
    except ImportError:
        pass

    print()
    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print("=" * 72)
    print("SUMMARY: GO/NO-GO RANKING (by OOS net c/window)")
    print("=" * 72)
    def classify(s):
        if s is None: return "NO-GO (no data)"
        oos = s['oos_net_c']
        n = s['n_windows_oos']
        pr = s['pair_rate']
        if n < 30: return "NO-GO (insufficient OOS n)"
        if oos <= 0: return "NO-GO (negative OOS)"
        if pr < 0.70: return "CAUTION (low pair rate)"
        if oos > 0.5 and pr >= 0.85: return "GO"
        if oos > 0.15: return "CONDITIONAL-GO"
        return "CAUTION (marginal)"
    ranked = sorted([s for s in all_stats if s is not None],
                    key=lambda s: s['oos_net_c'] if not np.isnan(s['oos_net_c']) else -999, reverse=True)
    for i, s in enumerate(ranked, 1):
        v = classify(s)
        print(f"  #{i} {s['asset'].upper():>4}: {v}")
        print(f"      OOS={s['oos_net_c']:+.3f}c  pair_rate={s['pair_rate']:.3f}  "
              f"strands/win={s['strands_per_win']:.3f}  n_oos={s['n_windows_oos']}")
        caveats = []
        if s['n_windows_oos'] < 50: caveats.append(f"SHORT OOS n={s['n_windows_oos']}")
        if s['pair_rate'] < 0.80: caveats.append(f"LOW PAIR RATE {s['pair_rate']:.2f}")
        if s['late_fill_pct'] > 20: caveats.append(f"HIGH LAST-120s {s['late_fill_pct']:.0f}%")
        if s['asset'] != 'btc': caveats.append("ALT MAKER FEE $0 UNCONFIRMED")
        if s['asset'] in ('sol', 'xrp'): caveats.append("THIN BOOK + settlement-taker hazard")
        if not caveats: caveats.append("none flagged")
        print(f"      Caveats: {'; '.join(caveats)}")

    print()
    print("  NOTE: combo gate uses vpin-only proxy (det_ fields need informed_detectors.build()")
    print("        per window -- not pre-computed in parquet; combo benefit may be understated).")
    print("  MAKER FEE: $0 confirmed on BTC live fills ONLY. Verify ETH/SOL/XRP before arming.")
    return all_stats, results


if __name__ == "__main__":
    stats, results = main()
