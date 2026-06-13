"""hour_schedule_study.py -- Deployment schedule analysis for BTC 15m box bot.

Fits a COARSE UTC-hour session schedule on the tape.
IS = first 60%, OOS = last 40% (same split as multi_asset_study.py).
Read-only. Compact output only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import json
import datetime
import os, sys
os.chdir("/home/user/Codex-playground-")
sys.path.insert(0, "/home/user/Codex-playground-")

from informed_detectors import vpin_buckets, vpin_at

# ──────────────────────────────────────────────────────────────────────────────
# 1. Replay: same-minute clean-box policy (verbatim from multi_asset_study.py)
# ──────────────────────────────────────────────────────────────────────────────
def replay_btc():
    h = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
    t = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")
    common = sorted(set(h.index) & set(t.index))
    n = len(common)
    cut = int(n * 0.6)

    rows = []
    for ws in common:
        h_row = h.loc[ws]; t_row = t.loc[ws]
        bid = np.asarray(h_row["bid_path"], float)
        ask = np.asarray(h_row["ask_path"], float)
        res = int(h_row["res_up"])
        t_arr = np.asarray(t_row["t"], float)
        p_arr = np.asarray(t_row["p"], float)
        sz_arr = np.asarray(t_row["sz"], float)
        buy_arr = np.asarray(t_row["buy"]).astype(bool)
        bt, bi = vpin_buckets(t_arr, sz_arr, buy_arr)

        boxes = strands = 0
        box_pnl = strand_pnl = 0.0
        # sig: largest abs 1-min spot move, for t36 gate
        spot = np.asarray(h_row["spot_path"], float)
        sig = float(np.nanmax(np.abs(np.diff(spot[~np.isnan(spot)])))) if np.sum(~np.isnan(spot)) >= 2 else 0.0

        for k in range(2, 13):
            b0, a0 = bid[k], ask[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
                continue
            spread = a0 - b0
            lo = ws + 60 * (k + 1); hi = ws + 60 * (k + 2)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            got_b = got_a = False
            bs = aks = None

            for i in range(i0, i1):
                p = float(p_arr[i]); buy = bool(buy_arr[i])
                if not got_b and not buy and p <= b0 + 1e-9:
                    bs = float(res) - b0; got_b = True
                if not got_a and buy and p >= a0 - 1e-9:
                    aks = a0 - float(res); got_a = True
                if got_b and got_a:
                    break

            if got_b and got_a:
                boxes += 1; box_pnl += bs + aks
            elif got_b and not got_a:
                strands += 1; strand_pnl += bs
            elif got_a and not got_b:
                strands += 1; strand_pnl += aks

        dt = datetime.datetime.utcfromtimestamp(ws)
        rows.append({
            "ws": ws,
            "hour": dt.hour,
            "date": dt.date(),
            "split": "IS" if ws < common[cut] else "OOS",
            "quarter": 0 if ws < common[int(n*0.25)] else
                       1 if ws < common[int(n*0.50)] else
                       2 if ws < common[int(n*0.75)] else 3,
            "boxes": boxes,
            "strands": strands,
            "net_pnl": box_pnl + strand_pnl,
            "box_pnl": box_pnl,
            "strand_pnl": strand_pnl,
            "spread_first": float(ask[2] - bid[2]) if not np.isnan(ask[2]) and not np.isnan(bid[2]) else np.nan,
            "sig": sig,
        })

    df = pd.DataFrame(rows)
    print(f"Total windows: {len(df)}  IS: {(df.split=='IS').sum()}  OOS: {(df.split=='OOS').sum()}")
    print(f"Date range: {df.date.min()} -> {df.date.max()}")
    return df, common, cut


# ──────────────────────────────────────────────────────────────────────────────
# 2. t36 guard logic (replicate gate_as_skew from guarded_opener_backtest.py)
#    applied at window level: a window is "t36 blocked" if its FIRST (k=2) fill
#    would be blocked on BOTH YES and NO sides → skip window for t36.
#    More faithful: apply per-leg and recompute window net.
# ──────────────────────────────────────────────────────────────────────────────
def apply_t36(df):
    """
    t36 = skip YES (bid) open if spread < 0.02
          skip any side open if sig > 8 AND spread < 0.02
    We approximate at window level: a window is 't36 eligible' if it would
    still produce boxes/strands after the gate. We use the spread and sig from
    the window to judge:
      - If spread < 0.02  → YES openers blocked → net ~ strand contribution only
      - If sig > 8 AND spread < 0.02 → all openers blocked
    For this schedule study we use a conservative window-level pass/block:
      BLOCKED = spread_first < 0.02  (both legs suppressed since YES blocked = can't form box)
    """
    # t36 blocks the window if the opening bid (YES leg) is suppressed due to
    # thin spread. A box needs both legs; if YES is blocked the box can't form.
    df2 = df.copy()
    # Mark windows where t36 would block the YES opener (no box possible)
    df2["t36_blocked"] = (df2["spread_first"] < 0.02) | ((df2["sig"] > 8.0) & (df2["spread_first"] < 0.02))
    # t36-eligible pnl: zero out blocked windows
    df2["net_pnl_t36"] = df2["net_pnl"] * (~df2["t36_blocked"]).astype(float)
    return df2


# ──────────────────────────────────────────────────────────────────────────────
# 3. Helpers
# ──────────────────────────────────────────────────────────────────────────────
def agg(sub, label=""):
    if len(sub) == 0:
        return {"label": label, "n": 0, "net_c": np.nan, "strand_rate": np.nan,
                "frac_traded": np.nan}
    net_c = sub["net_pnl"].mean() * 100
    strand_rate = (sub["strands"].sum() /
                   max(sub["boxes"].sum() + sub["strands"].sum(), 1) * 100)
    return {"label": label, "n": len(sub), "net_c": net_c,
            "strand_rate": strand_rate, "frac_traded": 1.0}


def schedule_pnl(df, include_hours, label="schedule"):
    """Apply schedule: traded hours get full credit, others get 0."""
    traded = df[df["hour"].isin(include_hours)]
    not_traded = df[~df["hour"].isin(include_hours)]
    # net per window for traded, 0 for not_traded
    total_pnl = traded["net_pnl"].sum()
    n_windows = len(df)
    n_traded = len(traded)
    net_c = (total_pnl / n_windows) * 100  # per-window avg including skipped windows
    return {
        "label": label,
        "n_total": n_windows,
        "n_traded": n_traded,
        "pct_traded": n_traded / n_windows * 100,
        "net_c_per_window_total": net_c,  # avg over ALL windows (schedule's daily impact)
        "net_c_per_traded": traded["net_pnl"].mean() * 100 if n_traded > 0 else np.nan,
        "strand_rate_pct": (traded["strands"].sum() /
                            max(traded["boxes"].sum() + traded["strands"].sum(), 1) * 100),
    }


def always_on(df):
    return schedule_pnl(df, list(range(24)), "always_on")


def uplift(sched, base):
    """net_c delta of schedule vs always-on, per ALL windows."""
    return sched["net_c_per_window_total"] - base["net_c_per_window_total"]


# ──────────────────────────────────────────────────────────────────────────────
# 4. Per-hour stats
# ──────────────────────────────────────────────────────────────────────────────
def per_hour_table(df, split_label):
    sub = df[df["split"] == split_label]
    rows = []
    for h in range(24):
        hs = sub[sub["hour"] == h]
        if len(hs) == 0:
            rows.append({"hour": h, "n": 0, "net_c": np.nan, "strand%": np.nan})
            continue
        net_c = hs["net_pnl"].mean() * 100
        strand = hs["strands"].sum() / max(hs["boxes"].sum() + hs["strands"].sum(), 1) * 100
        rows.append({"hour": h, "n": len(hs), "net_c": round(net_c, 4),
                     "strand%": round(strand, 1)})
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Session-block candidates
# ──────────────────────────────────────────────────────────────────────────────
# Based on MULTI_ASSET.md: 16-24 UTC best, 04-12 UTC negative
# We test coarse block partitions (2-4 blocks):
SCHEDULE_CANDIDATES = {
    "sched_A_16to24only": list(range(16, 24)),       # narrowest
    "sched_B_12to24":     list(range(12, 24)),       # 12h window
    "sched_C_00to04_16to24": list(range(0, 4)) + list(range(16, 24)),  # two peaks
    "sched_D_off04to12":  list(range(0, 4)) + list(range(12, 24)),     # drop worst block
    "sched_E_16to24_half_12to16": list(range(16, 24)) + list(range(12, 16)),  # = sched_B
    "sched_F_20to04":     list(range(20, 24)) + list(range(0, 4)),     # night block
    "sched_G_16to04":     list(range(16, 24)) + list(range(0, 4)),     # evening + early AM
    "always_on":          list(range(24)),
}


# ──────────────────────────────────────────────────────────────────────────────
# 6. Quarter stability check
# ──────────────────────────────────────────────────────────────────────────────
def quarter_check(df, include_hours, label):
    rows = []
    for q in range(4):
        qdf = df[df["quarter"] == q]
        s = schedule_pnl(qdf, include_hours, f"Q{q}")
        net_all = s["net_c_per_window_total"]
        rows.append({
            "quarter": f"Q{q} ({qdf['date'].min()}..{qdf['date'].max()})",
            "n_traded": s["n_traded"],
            "net_c_per_all": round(net_all, 4),
            "net_c_per_traded": round(s["net_c_per_traded"], 4) if not np.isnan(s["net_c_per_traded"]) else np.nan,
            "positive": net_all > 0,
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Hour-22 deep dive
# ──────────────────────────────────────────────────────────────────────────────
def hour22_analysis(df):
    h22 = df[df["hour"] == 22]
    rest = df[df["hour"] != 22]
    def stats(sub, lbl):
        if len(sub) == 0:
            return {"group": lbl, "n": 0}
        net_c = sub["net_pnl"].mean() * 100
        strand = sub["strands"].sum() / max(sub["boxes"].sum() + sub["strands"].sum(), 1) * 100
        boxes_per_win = sub["boxes"].mean()
        return {"group": lbl, "n": len(sub),
                "net_c": round(net_c, 4),
                "strand%": round(strand, 1),
                "boxes/win": round(boxes_per_win, 2)}
    return [stats(h22, "hour=22"), stats(rest, "other hours")]


# ──────────────────────────────────────────────────────────────────────────────
# 8. Live fills: hour-22 check from window_audit_btc15m.jsonl
# ──────────────────────────────────────────────────────────────────────────────
def live_hour22():
    rows = []
    try:
        with open("window_audit_btc15m.jsonl") as f:
            for line in f:
                d = json.loads(line.strip())
                ws = d.get("ws", 0)
                dt = datetime.datetime.utcfromtimestamp(ws)
                rows.append({
                    "ws": ws,
                    "hour": dt.hour,
                    "pnl": d.get("pnl", 0),
                    "paired": d.get("paired", 0),
                    "unpaired": d.get("unpaired", 0),
                })
    except Exception as e:
        return f"window_audit read error: {e}"
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return "No live windows"
    h22 = df[df["hour"] == 22]
    rest = df[df["hour"] != 22]
    def live_stats(sub, lbl):
        if len(sub) == 0:
            return {"group": lbl, "n": 0, "mean_pnl_c": np.nan, "strand_rate%": np.nan}
        # strand_rate: windows with unpaired > 0
        strand_rate = (sub["unpaired"] > 0).mean() * 100
        return {
            "group": lbl,
            "n": len(sub),
            "mean_pnl_c": round(sub["pnl"].mean() * 100, 3),
            "strand_rate%": round(strand_rate, 1),
        }
    return [live_stats(h22, "live hour=22"),
            live_stats(rest, "live other hours"),
            live_stats(df, "live ALL")]


# ──────────────────────────────────────────────────────────────────────────────
# 9. Redundancy vs t36: does schedule add value ON TOP of t36 guard?
# ──────────────────────────────────────────────────────────────────────────────
def t36_redundancy(df, best_hours):
    df2 = apply_t36(df)
    # Base: always-on with t36
    base_t36 = df2.groupby("split").apply(
        lambda sub: pd.Series({
            "n": len(sub),
            "net_c": sub["net_pnl_t36"].mean() * 100,
        })
    ).reset_index()

    # Schedule with t36
    rows = []
    for split in ["IS", "OOS"]:
        sub = df2[df2["split"] == split]
        traded = sub[sub["hour"].isin(best_hours)]
        # t36 + schedule: only count traded windows; net is pnl_t36 for those
        net_sched_t36_traded = traded["net_pnl_t36"].mean() * 100 if len(traded) > 0 else np.nan
        # per ALL windows
        total_sched_t36 = (traded["net_pnl_t36"].sum() / len(sub)) * 100

        base = base_t36[base_t36["split"] == split]["net_c"].values[0]
        rows.append({
            "split": split,
            "n": len(sub),
            "always_on_t36_c": round(base, 4),
            "sched_t36_c_per_all": round(total_sched_t36, 4),
            "uplift_c": round(total_sched_t36 - base, 4),
            "n_traded": len(traded),
            "pct_traded": round(len(traded)/len(sub)*100, 1),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 72)
    print("HOUR SCHEDULE STUDY — BTC 15m box harvest")
    print("IS=first 60%, OOS=last 40%, same-minute clean-box policy")
    print("=" * 72)

    print("\nRunning tape replay...")
    df, common, cut = replay_btc()

    # ── TASK 1: Per-hour table ─────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("TASK 1a: Per-hour net (c/window) — IS and OOS")
    print("=" * 72)
    is_h = per_hour_table(df, "IS")
    oos_h = per_hour_table(df, "OOS")
    merged = is_h.merge(oos_h, on="hour", suffixes=("_IS", "_OOS"))
    merged = merged.rename(columns={
        "n_IS": "n_IS", "net_c_IS": "IS_c", "strand%_IS": "IS_str%",
        "n_OOS": "n_OOS", "net_c_OOS": "OOS_c", "strand%_OOS": "OOS_str%",
    })
    print(f"{'hr':>4} {'n_IS':>6} {'IS_c':>8} {'IS_str%':>8} {'n_OOS':>6} {'OOS_c':>8} {'OOS_str%':>9}")
    print("-" * 58)
    for _, row in merged.iterrows():
        h = int(row["hour"])
        flag = ""
        if row["IS_c"] > 0 and row["OOS_c"] > 0:
            flag = " +"
        elif row["IS_c"] < 0 and row["OOS_c"] < 0:
            flag = " -"
        print(f"{h:>4} {int(row['n_IS']):>6} {row['IS_c']:>+8.4f} {row['IS_str%']:>8.1f} "
              f"{int(row['n_OOS']):>6} {row['OOS_c']:>+8.4f} {row['OOS_str%']:>9.1f}{flag}")

    # ── TASK 1: Schedule candidates ────────────────────────────────────────
    print("\n" + "=" * 72)
    print("TASK 1b: Schedule candidates — IS vs OOS vs Always-On")
    print("=" * 72)
    is_df = df[df["split"] == "IS"]
    oos_df = df[df["split"] == "OOS"]
    all_df = df

    results = []
    for name, hours in SCHEDULE_CANDIDATES.items():
        is_s = schedule_pnl(is_df, hours, name)
        oos_s = schedule_pnl(oos_df, hours, name)
        all_s = schedule_pnl(all_df, hours, name)
        base_is = always_on(is_df)
        base_oos = always_on(oos_df)
        results.append({
            "name": name,
            "hrs": len(set(hours)),
            "IS_c": is_s["net_c_per_window_total"],
            "OOS_c": oos_s["net_c_per_window_total"],
            "pct_traded": is_s["pct_traded"],
            "IS_uplift": uplift(is_s, base_is),
            "OOS_uplift": uplift(oos_s, base_oos),
            "IS_pos": is_s["net_c_per_window_total"] > 0,
            "OOS_pos": oos_s["net_c_per_window_total"] > 0,
        })

    print(f"{'schedule':<32} {'h':>3} {'pct%':>6} {'IS_c':>8} {'OOS_c':>8} {'IS_up':>8} {'OOS_up':>8} {'ok?':>6}")
    print("-" * 85)
    for r in results:
        ok = "IS+OOS" if r["IS_pos"] and r["OOS_pos"] else ("IS only" if r["IS_pos"] else "FAIL")
        print(f"{r['name']:<32} {r['hrs']:>3} {r['pct_traded']:>6.1f} "
              f"{r['IS_c']:>+8.4f} {r['OOS_c']:>+8.4f} "
              f"{r['IS_uplift']:>+8.4f} {r['OOS_uplift']:>+8.4f} {ok:>8}")

    # Find best schedule (IS+OOS positive, highest OOS uplift)
    passing = [r for r in results if r["IS_pos"] and r["OOS_pos"] and r["name"] != "always_on"]
    if passing:
        best = max(passing, key=lambda r: r["OOS_uplift"])
        best_hours = SCHEDULE_CANDIDATES[best["name"]]
        print(f"\n=> Best schedule: {best['name']}  hours={sorted(best_hours)}")
    else:
        best = None
        best_hours = list(range(24))
        print("\n=> No schedule beats always-on in both IS and OOS. Recommend: ALWAYS-ON.")

    # ── Per-window net/day estimate ────────────────────────────────────────
    if best:
        # windows/day: 96 total (15m slots), fraction traded
        frac = best["pct_traded"] / 100
        is_s = schedule_pnl(is_df, best_hours, "best_IS")
        oos_s = schedule_pnl(oos_df, best_hours, "best_OOS")
        base_is = always_on(is_df)
        base_oos = always_on(oos_df)
        print(f"\n--- Uplift estimate (96 windows/day, 1 contract) ---")
        print(f"IS  : schedule {is_s['net_c_per_window_total']:+.4f} c/win vs always-on {base_is['net_c_per_window_total']:+.4f}  uplift={best['IS_uplift']:+.4f} c/win => {best['IS_uplift']*96:.2f} c/day")
        print(f"OOS : schedule {oos_s['net_c_per_window_total']:+.4f} c/win vs always-on {base_oos['net_c_per_window_total']:+.4f}  uplift={best['OOS_uplift']:+.4f} c/win => {best['OOS_uplift']*96:.2f} c/day")
        print(f"Windows traded: {frac*100:.1f}% of 96 = {frac*96:.0f}/day")

    # ── TASK 2: Quarterly stability ────────────────────────────────────────
    print("\n" + "=" * 72)
    print("TASK 2: Quarterly stability check (must hold in all 4 quarters)")
    print("=" * 72)
    qdf = quarter_check(df, best_hours, best["name"] if best else "always_on")
    print(qdf.to_string(index=False))
    all_positive = qdf["positive"].all()
    print(f"\nAll quarters positive: {all_positive}")
    if not all_positive:
        print("SCHEDULE FAILS STABILITY CHECK — recommend always-on")
    else:
        print("Schedule passes stability check.")

    # Always-on quarterly comparison
    print("\n--- Always-on quarterly for reference ---")
    qdf_ao = quarter_check(df, list(range(24)), "always_on")
    print(qdf_ao.to_string(index=False))

    # ── TASK 3: Hour-22 deep dive ──────────────────────────────────────────
    print("\n" + "=" * 72)
    print("TASK 3: Hour-22 analysis (tape + live fills)")
    print("=" * 72)

    # Full tape
    h22_stats = hour22_analysis(df)
    print("\nTape (all windows):")
    for s in h22_stats:
        print(f"  {s['group']:<20} n={s.get('n',0):>5}  net_c={s.get('net_c',np.nan):>+8.4f}  strand%={s.get('strand%',np.nan):>5.1f}  boxes/win={s.get('boxes/win',np.nan):>5.2f}")

    # IS/OOS breakdown for hour-22
    print("\nHour-22 by IS/OOS split:")
    for split in ["IS", "OOS"]:
        sub = df[(df["split"] == split) & (df["hour"] == 22)]
        rest = df[(df["split"] == split) & (df["hour"] != 22)]
        if len(sub) > 0:
            net_c = sub["net_pnl"].mean() * 100
            strand = sub["strands"].sum() / max(sub["boxes"].sum() + sub["strands"].sum(), 1) * 100
            rest_c = rest["net_pnl"].mean() * 100
            print(f"  {split}: hour-22 n={len(sub)} net_c={net_c:+.4f}  rest n={len(rest)} net_c={rest_c:+.4f}")

    # Live fills
    print("\nLive fills (window_audit_btc15m.jsonl, n=~45):")
    live = live_hour22()
    if isinstance(live, str):
        print(f"  {live}")
    else:
        for s in live:
            print(f"  {s['group']:<25} n={s.get('n',0):>4}  mean_pnl_c={s.get('mean_pnl_c',np.nan):>+8.3f}  strand%={s.get('strand_rate%',np.nan):>5.1f}")

    # Hour-22 vs all-hours quarterly
    print("\nHour-22 quarterly net_c:")
    for q in range(4):
        qsub = df[(df["quarter"] == q) & (df["hour"] == 22)]
        all_sub = df[df["quarter"] == q]
        q_min = all_sub["date"].min(); q_max = all_sub["date"].max()
        if len(qsub) > 0:
            net_c = qsub["net_pnl"].mean() * 100
            print(f"  Q{q} ({q_min}..{q_max}): n={len(qsub)} net_c={net_c:+.4f}")
        else:
            print(f"  Q{q}: n=0")

    # ── TASK 4: Interaction with t36 guard ─────────────────────────────────
    print("\n" + "=" * 72)
    print("TASK 4: Redundancy vs t36 guard — does schedule add value on top of t36?")
    print("=" * 72)
    t36_df = t36_redundancy(df, best_hours)
    print(t36_df.to_string(index=False))
    print(f"\nNote: t36 blocks windows with spread_first < 0.02 (YES leg suppressed)")
    print(f"If schedule uplift after t36 ≈ 0, schedule is redundant with t36.")

    # Compare what t36 blocks vs what schedule blocks
    df2 = apply_t36(df)
    t36_blocked_hours = df2[df2["t36_blocked"]].groupby("hour")["t36_blocked"].mean() * 100
    print(f"\nt36 block rate by hour (worst = schedule overlaps most with t36):")
    for h in sorted(best_hours):
        rate = t36_blocked_hours.get(h, 0.0)
        print(f"  hour={h:02d}: t36_block_rate={rate:.1f}%")

    # ALSO: compare the per-hour OOS net with and without t36
    print(f"\nPer-hour OOS: always-on vs t36 vs schedule+t36")
    oos_df2 = df2[df2["split"] == "OOS"]
    print(f"{'hr':>4} {'n':>5} {'no_gate_c':>10} {'t36_c':>8} {'sched_c':>8} {'in_sched':>9}")
    print("-" * 48)
    for h in range(24):
        hs = oos_df2[oos_df2["hour"] == h]
        if len(hs) == 0:
            continue
        no_gate = hs["net_pnl"].mean() * 100
        t36_c = hs["net_pnl_t36"].mean() * 100
        in_sched = h in best_hours
        print(f"{h:>4} {len(hs):>5} {no_gate:>+10.4f} {t36_c:>+8.4f} {'[TRADED]' if in_sched else '[SKIP]':>8}")

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    if best and all_positive:
        print(f"SCHEDULE: {best['name']}")
        print(f"  Hours:        {sorted(best_hours)}")
        print(f"  Windows/day:  {best['pct_traded']/100*96:.0f} of 96 ({best['pct_traded']:.1f}%)")
        print(f"  IS net_c:     {best['IS_c']:+.4f}")
        print(f"  OOS net_c:    {best['OOS_c']:+.4f}")
        print(f"  IS uplift:    {best['IS_uplift']:+.4f} c/win ({best['IS_uplift']*96:+.2f} c/day at 1ct)")
        print(f"  OOS uplift:   {best['OOS_uplift']:+.4f} c/win ({best['OOS_uplift']*96:+.2f} c/day at 1ct)")
        print(f"  Quarterly:    {'STABLE (all 4 quarters positive)' if all_positive else 'UNSTABLE'}")
    else:
        print("VERDICT: ALWAYS-ON (no schedule improves both IS and OOS, or fails quarterly)")


if __name__ == "__main__":
    main()
