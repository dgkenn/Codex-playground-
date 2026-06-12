"""
Trader/Bot Fingerprinting from Kalshi KXBTC15M Book Snapshots + Trade Tape.
Prints ONLY compact summary tables.
"""
import gzip, json, glob, os, sys
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

# ── helpers ──────────────────────────────────────────────────────────────────
def iter_gz(fp):
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return

def book_to_dict(levels):
    """[[price, size], ...] → {price: size}"""
    return {int(p): int(s) for p, s in levels} if levels else {}

# ── find BTC15M book files ────────────────────────────────────────────────────
ROOTS = [
    "/home/user/Codex-playground-",
    "/home/user/Codex-playground-/overnight_data",
]
book_files = []
for root in ROOTS:
    book_files += sorted(glob.glob(os.path.join(root, "book_kalshi_btc15m_*.jsonl.gz")))
book_files = sorted(set(book_files))
print(f"Book files found: {len(book_files)}")
for f in book_files:
    print(f"  {os.path.basename(f)}")

# ── load up to 2000 snapshots per file ───────────────────────────────────────
SNAP_LIMIT = 2000
all_snaps = []   # list of dicts: {ws, t, yes, no, spot}
for fp in book_files:
    count = 0
    for rec in iter_gz(fp):
        if rec.get("type") != "book":
            continue
        ws  = rec.get("ws", "")
        t   = rec.get("t", 0)
        yes = book_to_dict(rec.get("yes", []))
        no  = book_to_dict(rec.get("no", []))
        spot = rec.get("spot", None)
        all_snaps.append({"ws": ws, "t": t, "yes": yes, "no": no, "spot": spot})
        count += 1
        if count >= SNAP_LIMIT:
            break
    print(f"  Loaded {count} snaps from {os.path.basename(fp)}")

print(f"\nTotal snapshots: {len(all_snaps)}")

# ── load trade tape ───────────────────────────────────────────────────────────
trade_path = "/home/user/Codex-playground-/trades_kalshi_btc15m.parquet"
tdf = pd.read_parquet(trade_path)
print(f"Trade tape: {len(tdf)} windows, cols={tdf.columns.tolist()}")

# Flatten trades to individual records
trade_rows = []
for _, row in tdf.iterrows():
    ws_key = int(row["ws"])
    ts = row["t"] if hasattr(row["t"], "__iter__") else []
    ps = row["p"] if hasattr(row["p"], "__iter__") else []
    szs = row["sz"] if hasattr(row["sz"], "__iter__") else []
    buys = row["buy"] if hasattr(row["buy"], "__iter__") else []
    for t2, p2, sz2, b2 in zip(ts, ps, szs, buys):
        trade_rows.append({
            "ws": ws_key,
            "t": float(t2),
            "p": int(p2),
            "sz": float(sz2) / 100.0,   # convert to contracts
            "buy": bool(b2),
        })
trades = pd.DataFrame(trade_rows)
print(f"Flattened trades: {len(trades)} records")
if len(trades) > 0:
    print(f"  p range: {trades['p'].min()}–{trades['p'].max()}, sz range: {trades['sz'].min():.2f}–{trades['sz'].max():.2f}")

# ── group snapshots by window ─────────────────────────────────────────────────
from itertools import groupby
# Sort by ws then t
all_snaps.sort(key=lambda x: (x["ws"], x["t"]))
ws_snaps = defaultdict(list)
for s in all_snaps:
    ws_snaps[s["ws"]].append(s)

windows = sorted(ws_snaps.keys())
print(f"\nDistinct windows: {len(windows)}")

# ── PROXY 1 & 2: Cancellation + Add intensity ────────────────────────────────
cancel_data = []   # per-interval: ws, t_mid, side, cancel_sz, add_sz, trade_sz
for ws, snaps in ws_snaps.items():
    if len(snaps) < 2:
        continue
    ws_trades = trades[trades["ws"] == ws] if len(trades) > 0 else pd.DataFrame()
    for i in range(1, len(snaps)):
        prev, cur = snaps[i-1], snaps[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        t_mid = (prev["t"] + cur["t"]) / 2

        for side in ("yes", "no"):
            p0 = prev[side]
            p1 = cur[side]
            all_prices = set(p0.keys()) | set(p1.keys())

            # trades in this interval at each price (buy=YES trade, ~sell=NO trade)
            if len(ws_trades) > 0:
                mask = (ws_trades["t"] >= prev["t"]) & (ws_trades["t"] < cur["t"])
                if side == "yes":
                    iv_trades = ws_trades[mask & ws_trades["buy"]]
                else:
                    iv_trades = ws_trades[mask & ~ws_trades["buy"]]
                trade_vol_by_price = iv_trades.groupby("p")["sz"].sum().to_dict()
            else:
                trade_vol_by_price = {}

            total_cancel = 0
            total_add = 0
            total_trade = sum(trade_vol_by_price.values())
            for px in all_prices:
                s0 = p0.get(px, 0)
                s1 = p1.get(px, 0)
                tv = trade_vol_by_price.get(px, 0)
                delta = s1 - s0  # net change
                if delta < 0:
                    # size went down; some may be trades
                    cancel_here = max(0, -delta - tv)
                    total_cancel += cancel_here
                else:
                    total_add += delta

            cancel_data.append({
                "ws": ws, "t": t_mid, "side": side,
                "cancel_sz": total_cancel,
                "add_sz": total_add,
                "trade_sz": total_trade,
                "dt": dt,
            })

cdf = pd.DataFrame(cancel_data)
print("\n=== PROXY 1&2: Cancel/Add Intensity (per snapshot interval) ===")
if len(cdf) > 0:
    summary = cdf.groupby("side").agg(
        intervals=("cancel_sz", "count"),
        cancel_per_int=("cancel_sz", "mean"),
        add_per_int=("add_sz", "mean"),
        trade_per_int=("trade_sz", "mean"),
    )
    summary["cancel/trade_ratio"] = summary["cancel_per_int"] / (summary["trade_per_int"] + 0.001)
    summary["add/trade_ratio"] = summary["add_per_int"] / (summary["trade_per_int"] + 0.001)
    print(summary.round(2).to_string())

# ── PROXY 3: Ladder-MM Fingerprint ───────────────────────────────────────────
print("\n=== PROXY 3: Ladder-MM Fingerprint ===")
ladder_events = []   # per snapshot
for ws, snaps in ws_snaps.items():
    prev_modal_depth = {"yes": None, "no": None}
    for snap in snaps:
        for side in ("yes", "no"):
            levels = snap[side]
            if not levels:
                continue
            sizes = list(levels.values())
            if len(sizes) < 5:
                continue
            # find modal size
            cnt = Counter(sizes)
            modal_sz, modal_count = cnt.most_common(1)[0]
            modal_depth = modal_sz * modal_count
            total_depth = sum(sizes)
            modal_frac = modal_depth / (total_depth + 1)

            prev_md = prev_modal_depth[side]
            pull = False
            if prev_md is not None and prev_md > 0:
                drop_frac = (prev_md - modal_depth) / prev_md
                pull = drop_frac > 0.20

            ladder_events.append({
                "ws": ws, "t": snap["t"], "side": side,
                "modal_sz": modal_sz,
                "modal_count": modal_count,
                "modal_depth": modal_depth,
                "total_depth": total_depth,
                "modal_frac": modal_frac,
                "pull": pull,
            })
            prev_modal_depth[side] = modal_depth

ldf = pd.DataFrame(ladder_events)
if len(ldf) > 0:
    summary3 = ldf.groupby("side").agg(
        snaps=("modal_sz", "count"),
        modal_sz_mode=("modal_sz", lambda x: x.mode()[0] if len(x) > 0 else 0),
        modal_sz_median=("modal_sz", "median"),
        modal_count_mean=("modal_count", "mean"),
        modal_frac_mean=("modal_frac", "mean"),
        pull_rate=("pull", "mean"),
    )
    print(summary3.round(3).to_string())

    # Size distribution of the modal-size
    for side in ("yes", "no"):
        sub = ldf[ldf["side"] == side]["modal_sz"]
        top5 = sub.value_counts().head(5)
        print(f"\n  Top-5 modal sizes ({side}):")
        for sz, cnt2 in top5.items():
            print(f"    size={sz:5d}  count={cnt2:5d}  ({100*cnt2/len(sub):.1f}%)")

# ── PROXY 4: Quote Cadence ────────────────────────────────────────────────────
print("\n=== PROXY 4: Quote Cadence (per-level refresh interval) ===")
cadence_data = []
for ws, snaps in ws_snaps.items():
    if len(snaps) < 3:
        continue
    # track last-change time per price level
    last_change = {}   # (side, px) -> last t when size changed
    for i in range(1, len(snaps)):
        prev, cur = snaps[i-1], snaps[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        for side in ("yes", "no"):
            all_px = set(prev[side].keys()) | set(cur[side].keys())
            for px in all_px:
                s0 = prev[side].get(px, 0)
                s1 = cur[side].get(px, 0)
                if s0 != s1:
                    key = (side, px)
                    if key in last_change:
                        cadence_data.append(cur["t"] - last_change[key])
                    last_change[key] = cur["t"]

if cadence_data:
    arr = np.array(cadence_data)
    arr = arr[(arr > 0) & (arr < 300)]
    print(f"  Refresh intervals: n={len(arr)}")
    print(f"  p5={np.percentile(arr,5):.1f}s  p25={np.percentile(arr,25):.1f}s  "
          f"median={np.median(arr):.1f}s  p75={np.percentile(arr,75):.1f}s  "
          f"p95={np.percentile(arr,95):.1f}s")
    # histogram of refresh interval buckets
    buckets = [1,2,3,5,10,20,60,120,300]
    hist, edges = np.histogram(arr, bins=[0]+buckets)
    print("  Interval bucket | count | frac")
    for j, h in enumerate(hist):
        lo = edges[j]; hi = edges[j+1]
        print(f"    [{lo:.0f}s–{hi:.0f}s]: {h:6d}  ({100*h/len(arr):.1f}%)")

# ── PROXY 5: Stale-Quote-After-Spot ─────────────────────────────────────────
print("\n=== PROXY 5: Stale-Quote-After-Spot ===")
stale_events = []
SPOT_MOVE_THRESH = 0.001   # 0.1%
STALE_WINDOW = 3.0         # seconds

for ws, snaps in ws_snaps.items():
    if len(snaps) < 5:
        continue
    for i in range(1, len(snaps)-3):
        prev, cur = snaps[i-1], snaps[i]
        s0 = prev.get("spot") or 0
        s1 = cur.get("spot") or 0
        if s0 <= 0 or s1 <= 0:
            continue
        move = abs(s1 - s0) / s0
        if move < SPOT_MOVE_THRESH:
            continue
        # find snaps within next 3s
        t_cut = cur["t"] + STALE_WINDOW
        future_snaps = [s for s in snaps[i+1:] if s["t"] <= t_cut]
        if not future_snaps:
            continue
        # count stale levels = levels that did NOT change in those 3s
        stale_count = 0
        total_levels = 0
        for side in ("yes", "no"):
            cur_levels = cur[side]
            for px, sz in cur_levels.items():
                updated = any(s[side].get(px, sz) != sz for s in future_snaps)
                stale_count += 0 if updated else 1
                total_levels += 1
        if total_levels > 0:
            stale_events.append({
                "ws": ws, "t": cur["t"],
                "spot_move_pct": move * 100,
                "stale_frac": stale_count / total_levels,
                "total_levels": total_levels,
            })

if stale_events:
    sdf = pd.DataFrame(stale_events)
    print(f"  Spot-move events (>0.1%): {len(sdf)}")
    print(f"  Spot move pct: mean={sdf['spot_move_pct'].mean():.3f}%  max={sdf['spot_move_pct'].max():.3f}%")
    print(f"  Stale fraction (levels unchanged in 3s): mean={sdf['stale_frac'].mean():.3f}  "
          f"median={sdf['stale_frac'].median():.3f}")
    # by stale quartile
    sdf["stale_q"] = pd.qcut(sdf["stale_frac"], 4, labels=["Q1","Q2","Q3","Q4"])
    print(sdf.groupby("stale_q")["spot_move_pct"].agg(["mean","count"]).round(3).to_string())
else:
    print("  No spot-move events found (spot data may be missing)")

# ── IS/OOS SPLIT ─────────────────────────────────────────────────────────────
all_ws_sorted = sorted(windows)
n_is = int(len(all_ws_sorted) * 0.6)
is_ws = set(all_ws_sorted[:n_is])
oos_ws = set(all_ws_sorted[n_is:])
print(f"\nIS windows: {len(is_ws)}, OOS windows: {len(oos_ws)}")

# ── TEST A: Cancel/Ladder Pull → Markout Proxy ───────────────────────────────
print("\n=== TEST A: Cancel/Pull Intensity vs Fill Outcome ===")
# Use pair-rate from trades as markout proxy: how often both YES and NO fill in same window
if len(trades) > 0:
    window_stats = []
    for ws in all_ws_sorted:
        snaps = ws_snaps.get(ws, [])
        wt = trades[trades["ws"] == ws]
        yes_fills = wt[wt["buy"]]["sz"].sum()
        no_fills = wt[~wt["buy"]]["sz"].sum()
        paired = min(yes_fills, no_fills)
        total = yes_fills + no_fills
        pair_rate = paired / (total / 2 + 0.001)

        # get cancel intensity for this window
        wc = cdf[cdf["ws"] == ws] if len(cdf) > 0 else pd.DataFrame()
        cancel_yes = wc[wc["side"] == "yes"]["cancel_sz"].sum() if len(wc) > 0 else 0
        cancel_no = wc[wc["side"] == "no"]["cancel_sz"].sum() if len(wc) > 0 else 0

        # get pull rate for this window
        wl = ldf[ldf["ws"] == ws] if len(ldf) > 0 else pd.DataFrame()
        pull_rate_yes = wl[wl["side"] == "yes"]["pull"].mean() if len(wl) > 0 else 0
        pull_rate_no = wl[wl["side"] == "no"]["pull"].mean() if len(wl) > 0 else 0

        window_stats.append({
            "ws": ws,
            "split": "IS" if ws in is_ws else "OOS",
            "pair_rate": pair_rate,
            "yes_fills": yes_fills,
            "no_fills": no_fills,
            "cancel_yes": cancel_yes,
            "cancel_no": cancel_no,
            "pull_rate_yes": pull_rate_yes,
            "pull_rate_no": pull_rate_no,
        })

    wsdf = pd.DataFrame(window_stats)

    if len(wsdf) > 0:
        # Correlations
        feats = ["cancel_yes", "cancel_no", "pull_rate_yes", "pull_rate_no"]
        for split in ["IS", "OOS"]:
            sub = wsdf[wsdf["split"] == split]
            if len(sub) < 5:
                continue
            print(f"\n  {split} (n={len(sub)}) — Pearson corr with pair_rate:")
            for f in feats:
                if sub[f].std() > 0:
                    corr = sub["pair_rate"].corr(sub[f])
                    print(f"    {f:25s}: r={corr:+.3f}")

        # Tertile split on cancel_yes
        if wsdf["cancel_yes"].std() > 0:
            wsdf["cancel_tertile"] = pd.qcut(wsdf["cancel_yes"].rank(method="first"),
                                             3, labels=["Low","Mid","High"])
            print("\n  Pair-rate by cancel_yes tertile (IS+OOS):")
            print(wsdf.groupby("cancel_tertile")["pair_rate"].agg(["mean","count"]).round(3).to_string())

# ── TEST B: Ladder Pull → Adverse Window ─────────────────────────────────────
print("\n=== TEST B: Ladder Pull → Adverse Window (unpaired inventory) ===")
if len(ldf) > 0 and len(trades) > 0:
    # Adverse = large imbalance in YES vs NO fills
    wstats_b = []
    for ws in all_ws_sorted:
        wt = trades[trades["ws"] == ws]
        yes_f = wt[wt["buy"]]["sz"].sum()
        no_f = wt[~wt["buy"]]["sz"].sum()
        total = yes_f + no_f
        imbalance = abs(yes_f - no_f) / (total + 0.001)
        adverse = imbalance > 0.5   # one side >75% of fills

        wl = ldf[(ldf["ws"] == ws)]
        any_pull = wl["pull"].any() if len(wl) > 0 else False

        wstats_b.append({"ws": ws, "adverse": adverse, "any_pull": any_pull,
                         "imbalance": imbalance})

    bdf = pd.DataFrame(wstats_b)
    ct = pd.crosstab(bdf["any_pull"], bdf["adverse"],
                     values=bdf["ws"], aggfunc="count", margins=True)
    ct.index.name = "pull_event"
    ct.columns.name = "adverse_window"
    print("\n  Crosstab: pull_event x adverse_window")
    print(ct.to_string())

    # Conditional rates
    for pull_val in [False, True]:
        sub = bdf[bdf["any_pull"] == pull_val]
        adv_rate = sub["adverse"].mean() if len(sub) > 0 else float("nan")
        print(f"  adverse_rate | pull={pull_val}: {adv_rate:.3f}  (n={len(sub)})")

# ── TEST C: Cluster Windows by Counterparty Mix ──────────────────────────────
print("\n=== TEST C: Window Clusters by Counterparty Mix ===")
if len(ldf) > 0:
    cluster_rows = []
    for ws in all_ws_sorted:
        snaps = ws_snaps.get(ws, [])
        if not snaps:
            continue
        wl = ldf[ldf["ws"] == ws]
        if len(wl) == 0:
            continue

        # Ladder-MM score: fraction of snapshots where modal_frac > 0.5
        mm_score = (wl["modal_frac"] > 0.5).mean()
        pull_rate_w = wl["pull"].mean()
        # directional score from trades
        wt = trades[trades["ws"] == ws]
        yes_f = wt[wt["buy"]]["sz"].sum() if len(wt) > 0 else 0
        no_f = wt[~wt["buy"]]["sz"].sum() if len(wt) > 0 else 0
        total_f = yes_f + no_f
        dir_score = abs(yes_f - no_f) / (total_f + 0.001)

        cluster_rows.append({
            "ws": ws,
            "mm_score": mm_score,
            "pull_rate": pull_rate_w,
            "dir_score": dir_score,
            "total_fills": total_f,
        })

    cldf = pd.DataFrame(cluster_rows)
    if len(cldf) >= 6:
        # Label clusters
        cldf["mm_dom"] = cldf["mm_score"] > cldf["mm_score"].median()
        cldf["dir_dom"] = cldf["dir_score"] > cldf["dir_score"].median()
        def cluster_label(row):
            if row["mm_dom"] and not row["dir_dom"]:
                return "MM-dom"
            elif not row["mm_dom"] and row["dir_dom"]:
                return "Dir-dom"
            elif row["mm_dom"] and row["dir_dom"]:
                return "Mixed-pull"
            else:
                return "Balanced"
        cldf["cluster"] = cldf.apply(cluster_label, axis=1)

        print("\n  Cluster summary:")
        print(cldf.groupby("cluster").agg(
            n=("ws", "count"),
            mm_score_mean=("mm_score", "mean"),
            dir_score_mean=("dir_score", "mean"),
            pull_rate_mean=("pull_rate", "mean"),
            fills_mean=("total_fills", "mean"),
        ).round(3).to_string())

# ── TEST D: Distinct Systematic Quoters ─────────────────────────────────────
print("\n=== TEST D: Distinct Systematic Quoters ===")
if len(ldf) > 0:
    # Proxy: distinct (modal_sz, modal_count) combo fingerprints
    fingerprints = ldf.groupby(["side", "modal_sz"]).agg(
        appearances=("ws", "count"),
        pct=("modal_frac", "mean"),
        n_windows=("ws", "nunique"),
    ).reset_index()
    fingerprints = fingerprints.sort_values("appearances", ascending=False)

    print("\n  Top-10 fingerprints (modal_sz x side = distinct systematic quoter proxy):")
    print(fingerprints.head(10).round(3).to_string(index=False))

    # Few-makers windows: windows where top-1 modal_sz dominates heavily
    for side in ("yes", "no"):
        sub = ldf[ldf["side"] == side]
        top_sz = sub["modal_sz"].mode()[0] if len(sub) > 0 else 0
        dominated = sub[sub["modal_sz"] == top_sz]
        dom_windows = dominated["ws"].nunique()
        all_windows_side = sub["ws"].nunique()
        print(f"\n  {side.upper()}: dominant MM size={top_sz}, "
              f"present in {dom_windows}/{all_windows_side} windows "
              f"({100*dom_windows/(all_windows_side+1):.1f}%)")

    # Edge proxy: if top MM is present, how does pair_rate compare?
    if "wsdf" in dir() and len(wsdf) > 0:
        for side in ("yes", "no"):
            sub_l = ldf[ldf["side"] == side]
            top_sz = sub_l["modal_sz"].mode()[0] if len(sub_l) > 0 else 0
            top_win = set(sub_l[sub_l["modal_sz"] == top_sz]["ws"].unique())
            w1 = wsdf[wsdf["ws"].isin(top_win)]["pair_rate"].mean()
            w0 = wsdf[~wsdf["ws"].isin(top_win)]["pair_rate"].mean()
            print(f"  Pair-rate: {side} MM present={w1:.3f}  absent={w0:.3f}  delta={w1-w0:+.3f}")

print("\n=== DONE ===")
