"""
Trader/Bot Fingerprinting Proxies — KXBTC15M book snapshots + fills
Loads first 2000 snapshots total; uses fills files (same ws range).
Prints ONLY compact summary tables.
"""
import gzip, json, glob, os
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

BASE = "/home/user/Codex-playground-"
OVER = os.path.join(BASE, "overnight_data")

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
    return {round(float(p), 3): float(s) for p, s in levels} if levels else {}

# LOAD 2000 snapshots TOTAL
book_files = sorted(glob.glob(os.path.join(OVER, "book_kalshi_btc15m_*.jsonl.gz")))
print(f"Book files found: {len(book_files)}")
SNAP_LIMIT = 2000
all_snaps = []
for fp in book_files:
    cnt = 0
    for rec in iter_gz(fp):
        if rec.get("type") != "book":
            continue
        all_snaps.append({"ws": int(rec.get("ws", 0)), "t": rec["t"],
                           "yes": book_to_dict(rec.get("yes", [])),
                           "no":  book_to_dict(rec.get("no", [])),
                           "spot": rec.get("spot")})
        cnt += 1
        if len(all_snaps) >= SNAP_LIMIT:
            break
    print(f"  {os.path.basename(fp)}: {cnt}  (total: {len(all_snaps)})")
    if len(all_snaps) >= SNAP_LIMIT:
        break

all_snaps.sort(key=lambda x: (x["ws"], x["t"]))
ws_snaps = defaultdict(list)
for s in all_snaps:
    ws_snaps[s["ws"]].append(s)
windows = sorted(ws_snaps)
print(f"\nSnapshots: {len(all_snaps)}  distinct windows: {len(windows)}")

# LOAD FILLS (own fills, same ws range as book snaps)
fills_files = sorted(glob.glob(os.path.join(OVER, "fills_kalshi_btc15m_*.jsonl.gz")))
fills_by_ws = defaultdict(list)
n_fills = 0
snap_ws_set = set(windows)
for fp in fills_files:
    for rec in iter_gz(fp):
        ws_val = rec.get("ws")
        if ws_val is None or int(ws_val) not in snap_ws_set:
            continue
        if rec.get("reason") not in ("fill", "fill_partial"):
            continue
        fills_by_ws[int(ws_val)].append({
            "t": rec["t"], "p": round(float(rec["p"]), 3),
            "sz": float(rec.get("sz", 0)),
            "side": rec["side"], "res_up": rec.get("res_up"),
        })
        n_fills += 1
print(f"Fills loaded: {n_fills}  windows with fills: {len(fills_by_ws)}")
ws_res_up = {}
for ws, recs in fills_by_ws.items():
    rup = [r["res_up"] for r in recs if r["res_up"] is not None]
    if rup:
        ws_res_up[ws] = rup[0]

# PROXY 1&2: Cancel + Add Intensity
print("\n=== PROXY 1&2: Cancel/Add Intensity (per ~1.2s interval) ===")
cancel_rows = []
for ws in windows:
    snaps = ws_snaps[ws]
    yes_exec = defaultdict(float)
    no_exec  = defaultdict(float)
    for f in fills_by_ws.get(ws, []):
        if f["side"] == "BID":
            yes_exec[f["p"]] += f["sz"]
        else:
            no_exec[f["p"]] += f["sz"]
    for i in range(1, len(snaps)):
        prev, cur = snaps[i-1], snaps[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        for side, exec_map in [("yes", yes_exec), ("no", no_exec)]:
            p0, p1 = prev[side], cur[side]
            all_px = set(p0) | set(p1)
            tot_c = tot_a = tot_e = 0.0
            for px in all_px:
                s0, s1 = p0.get(px, 0.0), p1.get(px, 0.0)
                tv = exec_map.get(px, 0.0)
                d  = s1 - s0
                if d < 0:
                    tot_c += max(0.0, -d - tv)
                else:
                    tot_a += d
                tot_e += tv
            cancel_rows.append({"ws": ws, "side": side, "dt": dt,
                                 "cancel": tot_c, "add": tot_a, "exec": tot_e})
cdf = pd.DataFrame(cancel_rows)
if len(cdf):
    sm = cdf.groupby("side").agg(n=("cancel","count"),
                                  cancel_mean=("cancel","mean"),
                                  add_mean=("add","mean"),
                                  exec_mean=("exec","mean"))
    sm["cancel/exec"] = sm["cancel_mean"] / (sm["exec_mean"] + 0.001)
    sm["add/exec"]    = sm["add_mean"]    / (sm["exec_mean"] + 0.001)
    print(sm.round(1).to_string())

# PROXY 3: Ladder-MM Fingerprint
print("\n=== PROXY 3: Ladder-MM Fingerprint ===")
lad_rows = []
for ws in windows:
    prev_md = {"yes": None, "no": None}
    for snap in ws_snaps[ws]:
        for side in ("yes","no"):
            lvls = snap[side]
            if len(lvls) < 5:
                continue
            isizes = [int(round(v)) for v in lvls.values() if v > 0]
            if not isizes:
                continue
            cnt = Counter(isizes)
            modal_sz, modal_cnt = cnt.most_common(1)[0]
            modal_depth = modal_sz * modal_cnt
            total_depth = sum(isizes)
            modal_frac  = modal_depth / (total_depth + 1)
            pm = prev_md[side]
            pull = (pm is not None and pm > 0 and (pm - modal_depth) / pm > 0.20)
            lad_rows.append({"ws": ws, "t": snap["t"], "side": side,
                              "modal_sz": modal_sz, "modal_cnt": modal_cnt,
                              "modal_depth": modal_depth, "total_depth": total_depth,
                              "modal_frac": modal_frac, "pull": pull})
            prev_md[side] = modal_depth
ldf = pd.DataFrame(lad_rows)
if len(ldf):
    sm3 = ldf.groupby("side").agg(
        n_snaps=("modal_sz","count"),
        modal_sz_mode=("modal_sz", lambda x: int(x.mode()[0])),
        modal_sz_med=("modal_sz","median"),
        modal_cnt_mean=("modal_cnt","mean"),
        modal_frac_mean=("modal_frac","mean"),
        pull_rate=("pull","mean"),
    )
    print(sm3.round(3).to_string())
    for side in ("yes","no"):
        sub = ldf[ldf["side"]==side]["modal_sz"]
        top5 = sub.value_counts().head(5)
        t = len(sub)
        print(f"\n  Top-5 modal sizes ({side}):")
        for sz, c in top5.items():
            print(f"    {sz:6d} cts  n={c:5d}  {100*c/t:.1f}%")

# PROXY 4: Quote Cadence
print("\n=== PROXY 4: Quote Cadence (per-level refresh interval) ===")
cad = []
for ws in windows:
    snaps = ws_snaps[ws]
    last_change = {}
    for i in range(1, len(snaps)):
        prev, cur = snaps[i-1], snaps[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        for side in ("yes","no"):
            for px in set(prev[side]) | set(cur[side]):
                if prev[side].get(px,0) != cur[side].get(px,0):
                    key = (side, px)
                    if key in last_change:
                        cad.append(cur["t"] - last_change[key])
                    last_change[key] = cur["t"]
if cad:
    arr = np.array(cad)
    arr = arr[(arr > 0) & (arr < 300)]
    print(f"  n={len(arr):,}  p5={np.percentile(arr,5):.1f}s  p25={np.percentile(arr,25):.1f}s  "
          f"median={np.median(arr):.1f}s  p75={np.percentile(arr,75):.1f}s  p95={np.percentile(arr,95):.1f}s")
    for lo, hi in [(0,1),(1,2),(2,3),(3,5),(5,10),(10,30),(30,300)]:
        n = ((arr >= lo) & (arr < hi)).sum()
        print(f"    [{lo:3d}s-{hi:3d}s]: {n:6d} ({100*n/len(arr):.1f}%)")

# PROXY 5: Stale-Quote-After-Spot
print("\n=== PROXY 5: Stale-Quote-After-Spot (>0.1% move) ===")
stale_rows = []
for ws in windows:
    snaps = ws_snaps[ws]
    if len(snaps) < 5:
        continue
    for i in range(1, len(snaps)-3):
        prev, cur = snaps[i-1], snaps[i]
        s0 = prev.get("spot") or 0
        s1 = cur.get("spot") or 0
        if s0 <= 0 or s1 <= 0:
            continue
        move = abs(s1 - s0) / s0
        if move < 0.001:
            continue
        t_cut = cur["t"] + 3.0
        future = [s for s in snaps[i+1:] if s["t"] <= t_cut]
        if not future:
            continue
        stale = tot = 0
        for side in ("yes","no"):
            for px, sz in cur[side].items():
                stale += 0 if any(s[side].get(px,sz) != sz for s in future) else 1
                tot += 1
        if tot > 0:
            stale_rows.append({"ws": ws, "move_pct": move*100, "stale_frac": stale/tot})
if stale_rows:
    sdf = pd.DataFrame(stale_rows)
    print(f"  Events: {len(sdf)}  move mean={sdf['move_pct'].mean():.3f}% max={sdf['move_pct'].max():.3f}%")
    print(f"  Stale frac: mean={sdf['stale_frac'].mean():.3f}  median={sdf['stale_frac'].median():.3f}  "
          f"frac_with_stale={( sdf['stale_frac']>0).mean():.3f}")
else:
    print("  No qualifying events")

# IS/OOS
n_is = int(len(windows) * 0.6)
is_ws  = set(windows[:n_is])
oos_ws = set(windows[n_is:])
print(f"\nIS windows: {len(is_ws)}  OOS windows: {len(oos_ws)}")

ws_rows = []
for ws in windows:
    fills = fills_by_ws.get(ws, [])
    yes_v = sum(f["sz"] for f in fills if f["side"]=="BID")
    no_v  = sum(f["sz"] for f in fills if f["side"]=="ASK")
    total = yes_v + no_v
    pair_rate = min(yes_v, no_v) / (total/2 + 0.001)
    imbalance = abs(yes_v - no_v) / (total + 0.001)
    wc = cdf[cdf["ws"]==ws] if len(cdf) else pd.DataFrame()
    cy = wc[wc["side"]=="yes"]["cancel"].sum() if len(wc) else 0
    cn = wc[wc["side"]=="no"]["cancel"].sum()  if len(wc) else 0
    wl = ldf[ldf["ws"]==ws] if len(ldf) else pd.DataFrame()
    ap  = bool(wl["pull"].any())     if len(wl) else False
    pr  = wl["pull"].mean()          if len(wl) else 0
    mms = (wl["modal_frac"]>0.5).mean() if len(wl) else 0
    ws_rows.append({"ws": ws, "split": "IS" if ws in is_ws else "OOS",
                    "pair_rate": pair_rate, "imbalance": imbalance,
                    "adverse": imbalance > 0.5,
                    "cancel_yes": cy, "cancel_no": cn,
                    "any_pull": ap, "pull_rate": pr, "mm_score": mms,
                    "res_up": ws_res_up.get(ws)})
wsdf = pd.DataFrame(ws_rows)

# TEST A
print("\n=== TEST A: Cancel/Pull vs markout (res_up) ===")
wdf_r = wsdf.dropna(subset=["res_up"]).copy()
wdf_r["res_up"] = wdf_r["res_up"].astype(float)
sp = int(len(wdf_r) * 0.6)
for label, dset in [("IS", wdf_r.iloc[:sp]), ("OOS", wdf_r.iloc[sp:])]:
    if len(dset) < 2:
        print(f"  {label}: n={len(dset)} (too few)")
        continue
    print(f"  {label} (n={len(dset)})  res_up mean={dset['res_up'].mean():.3f}")
    for f in ["cancel_yes","cancel_no","pull_rate","mm_score"]:
        if dset[f].std() > 1e-9:
            r = dset["res_up"].corr(dset[f])
            print(f"    {f:20s}: r={r:+.3f}")

# TEST B
print("\n=== TEST B: Ladder-Pull => Adverse ===")
ct = pd.crosstab(wsdf["any_pull"], wsdf["adverse"])
ct.index.name = "pull"; ct.columns.name = "adverse"
print(ct.to_string())
for pv in [False, True]:
    sub = wsdf[wsdf["any_pull"]==pv]
    rate = sub["adverse"].mean() if len(sub) else float("nan")
    print(f"  adverse_rate | pull={pv}: {rate:.3f}  (n={len(sub)})")

# TEST C
print("\n=== TEST C: Cluster by Counterparty Mix ===")
if len(wsdf) >= 4:
    wsdf["mm_dom"]  = wsdf["mm_score"]  > wsdf["mm_score"].median()
    wsdf["dir_dom"] = wsdf["imbalance"] > wsdf["imbalance"].median()
    def clabel(row):
        if row["mm_dom"] and not row["dir_dom"]:   return "MM-dom"
        elif not row["mm_dom"] and row["dir_dom"]:  return "Dir-dom"
        elif row["mm_dom"] and row["dir_dom"]:      return "Mixed"
        else:                                        return "Balanced"
    wsdf["cluster"] = wsdf.apply(clabel, axis=1)
    csum = wsdf.groupby("cluster").agg(
        n=("ws","count"), mm_score=("mm_score","mean"),
        imbalance=("imbalance","mean"), pull_rate=("pull_rate","mean"),
        pair_rate=("pair_rate","mean"), adverse_rate=("adverse","mean"),
    )
    print(csum.round(3).to_string())

# TEST D
print("\n=== TEST D: Distinct Systematic Quoters ===")
if len(ldf):
    fps = ldf.groupby(["side","modal_sz"]).agg(
        appearances=("ws","count"), frac_mean=("modal_frac","mean"),
        n_windows=("ws","nunique"),
    ).reset_index().sort_values("appearances", ascending=False)
    print("\n  Top-12 fingerprints (modal_sz x side):")
    print(fps.head(12).round(3).to_string(index=False))
    nwin = len(windows)
    for side in ("yes","no"):
        sub_l = ldf[ldf["side"]==side]
        fp_s = sub_l.groupby("modal_sz")["ws"].nunique()
        sig = (fp_s / nwin > 0.10).sum()
        top_sz = int(sub_l["modal_sz"].mode()[0])
        top_win = set(sub_l[sub_l["modal_sz"]==top_sz]["ws"].unique())
        w1 = wsdf[wsdf["ws"].isin(top_win)]["pair_rate"].mean()
        w0 = wsdf[~wsdf["ws"].isin(top_win)]["pair_rate"].mean()
        n1 = wsdf["ws"].isin(top_win).sum()
        print(f"\n  {side.upper()} top-MM size={top_sz}: pair_rate present={w1:.3f}(n={n1}) "
              f"absent={w0:.3f}  distinct(>10%win)={sig}")
        print(f"    size->n_windows: {fp_s[fp_s/nwin>0.05].sort_values(ascending=False).to_dict()}")

print("\n=== DONE ===")
