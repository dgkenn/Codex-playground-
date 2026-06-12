"""
Bot/trader fingerprinting on KXBTC15M.
Book-side proxies from Jun 11 snapshots (2000 snaps, 4 windows).
Trade-tape IS/OOS tests on full 2779-window parquet (May-Jun 10).
"""
import gzip, json, glob, os
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

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

# ══ 1. LOAD BOOK SNAPSHOTS (2000 total) ═════════════════════════════════════
ROOTS = [
    "/home/user/Codex-playground-/overnight_data",
    "/home/user/Codex-playground-",
]
book_files = []
for root in ROOTS:
    book_files += sorted(glob.glob(os.path.join(root, "book_kalshi_btc15m_*.jsonl.gz")))
book_files = sorted(set(book_files))
print(f"Book files: {len(book_files)}")

SNAP_LIMIT = 2000
all_snaps = []
for fp in book_files:
    if len(all_snaps) >= SNAP_LIMIT:
        break
    count = 0
    for rec in iter_gz(fp):
        if rec.get("type") != "book":
            continue
        all_snaps.append({
            "ws": rec.get("ws"), "t": rec.get("t", 0),
            "yes": book_to_dict(rec.get("yes", [])),
            "no":  book_to_dict(rec.get("no",  [])),
            "spot": rec.get("spot"),
        })
        count += 1
        if len(all_snaps) >= SNAP_LIMIT:
            break

print(f"Snapshots: {len(all_snaps)}")
all_snaps.sort(key=lambda x: (x["ws"], x["t"]))
ws_snaps = defaultdict(list)
for s in all_snaps:
    ws_snaps[s["ws"]].append(s)
windows_book = sorted(ws_snaps.keys())
print(f"Distinct windows in book data: {len(windows_book)}")

# ══ 2. LOAD TRADE PARQUET ═══════════════════════════════════════════════════
tdf = pd.read_parquet("/home/user/Codex-playground-/trades_kalshi_btc15m.parquet")
print(f"Trade parquet: {len(tdf)} windows")

# Unpack into flat per-window summaries (avoid full explode for speed)
ws_trade_summary = {}
for _, row in tdf.iterrows():
    ws_key = int(row["ws"])
    try:
        sz   = np.asarray(row["sz"]).flatten().astype(float)
        buy  = np.asarray(row["buy"]).flatten().astype(bool)
    except Exception:
        continue
    yes_vol = sz[buy].sum()
    no_vol  = sz[~buy].sum()
    total   = yes_vol + no_vol
    ws_trade_summary[ws_key] = {
        "yes_vol": yes_vol, "no_vol": no_vol, "total": total,
        "imbalance": abs(yes_vol - no_vol) / (total + 0.001),
        "pair_rate": min(yes_vol, no_vol) / (total/2 + 0.001),
        "n_trades": len(sz),
    }

print(f"Trade summaries built: {len(ws_trade_summary)}")

# ══ PROXY 1&2: Cancel/Add Intensity from book diffs ═════════════════════════
cancel_data = []
for ws, snaps_w in ws_snaps.items():
    for i in range(1, len(snaps_w)):
        prev, cur = snaps_w[i-1], snaps_w[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        for side in ("yes", "no"):
            p0 = prev[side]; p1 = cur[side]
            all_prices = set(p0.keys()) | set(p1.keys())
            cancel = add = 0
            for px in all_prices:
                d = p1.get(px,0) - p0.get(px,0)
                if d < 0: cancel += -d
                else:     add    +=  d
            cancel_data.append({
                "ws": ws, "side": side,
                "cancel_sz": cancel, "add_sz": add, "dt": dt,
            })

cdf = pd.DataFrame(cancel_data)
print("\n=== PROXY 1&2: Cancel/Add Intensity (book-diff, no trade join) ===")
sm = cdf.groupby("side").agg(
    intervals=("cancel_sz","count"),
    cancel_mean=("cancel_sz","mean"),
    cancel_p95=("cancel_sz", lambda x: x.quantile(0.95)),
    add_mean=("add_sz","mean"),
    add_p95=("add_sz", lambda x: x.quantile(0.95)),
)
print(sm.round(1).to_string())
total_cancel = cdf["cancel_sz"].sum()
total_add    = cdf["add_sz"].sum()
print(f"Overall cancel/add ratio: {total_cancel/(total_add+1):.3f}")

# ══ PROXY 3: Ladder-MM Fingerprint ══════════════════════════════════════════
print("\n=== PROXY 3: Ladder-MM Fingerprint ===")
ladder_events = []
for ws, snaps_w in ws_snaps.items():
    prev_md = {"yes": None, "no": None}
    for snap in snaps_w:
        for side in ("yes", "no"):
            levels = snap[side]
            if len(levels) < 5:
                continue
            isizes = [int(round(s)) for s in levels.values()]
            cnt = Counter(isizes)
            modal_sz, modal_count = cnt.most_common(1)[0]
            modal_depth = modal_sz * modal_count
            total_depth = sum(isizes)
            modal_frac  = modal_depth / (total_depth + 1)
            pull = False
            if prev_md[side] is not None and prev_md[side] > 0:
                pull = (prev_md[side] - modal_depth) / prev_md[side] > 0.20
            ladder_events.append({
                "ws": ws, "t": snap["t"], "side": side,
                "modal_sz": modal_sz, "modal_count": modal_count,
                "modal_depth": modal_depth, "total_depth": total_depth,
                "modal_frac": modal_frac, "pull": pull,
            })
            prev_md[side] = modal_depth

ldf = pd.DataFrame(ladder_events)
sm3 = ldf.groupby("side").agg(
    snaps=("modal_sz","count"),
    modal_mode=("modal_sz", lambda x: x.mode()[0]),
    modal_med=("modal_sz","median"),
    modal_count_mean=("modal_count","mean"),
    modal_frac_mean=("modal_frac","mean"),
    pull_rate=("pull","mean"),
)
print(sm3.round(3).to_string())

for side in ("yes","no"):
    sub = ldf[ldf["side"]==side]["modal_sz"]
    top5 = sub.value_counts().head(5)
    total = len(sub)
    print(f"\n  Top-5 modal sizes ({side}):")
    for sz, c in top5.items():
        print(f"    size={int(sz):6d}  n={c:5d}  ({100*c/total:.1f}%)")

# ══ PROXY 4: Quote Cadence ══════════════════════════════════════════════════
print("\n=== PROXY 4: Quote Cadence (per-level refresh interval) ===")
cadence_data = []
for ws, snaps_w in ws_snaps.items():
    last_change = {}
    for i in range(1, len(snaps_w)):
        prev, cur = snaps_w[i-1], snaps_w[i]
        dt = cur["t"] - prev["t"]
        if dt <= 0 or dt > 10:
            continue
        for side in ("yes","no"):
            for px in set(prev[side].keys()) | set(cur[side].keys()):
                if prev[side].get(px,0) != cur[side].get(px,0):
                    key = (side, px)
                    if key in last_change:
                        cadence_data.append(cur["t"] - last_change[key])
                    last_change[key] = cur["t"]

if cadence_data:
    arr = np.array(cadence_data)
    arr = arr[(arr > 0) & (arr < 300)]
    print(f"  n={len(arr):,}  p5={np.percentile(arr,5):.1f}s  "
          f"median={np.median(arr):.1f}s  p95={np.percentile(arr,95):.1f}s")
    for lo, hi in [(0,1),(1,2),(2,3),(3,5),(5,10),(10,30),(30,300)]:
        nc = ((arr>=lo)&(arr<hi)).sum()
        print(f"    [{lo:3d}s-{hi:3d}s]: {nc:6d} ({100*nc/len(arr):.1f}%)")

# ══ PROXY 5: Stale-Quote-After-Spot ════════════════════════════════════════
print("\n=== PROXY 5: Stale-Quote-After-Spot ===")
stale_evts = []
for ws, snaps_w in ws_snaps.items():
    for i in range(1, len(snaps_w)-3):
        prev, cur = snaps_w[i-1], snaps_w[i]
        s0 = prev.get("spot") or 0
        s1 = cur.get("spot")  or 0
        if s0 <= 0 or s1 <= 0: continue
        move = abs(s1 - s0) / s0
        if move < 0.001: continue
        yes_d = sum(cur["yes"].values())
        no_d  = sum(cur["no"].values())
        stale = True
        for j in range(i+1, min(i+4, len(snaps_w))):
            if snaps_w[j]["t"] - cur["t"] > 3.0: break
            if (abs(sum(snaps_w[j]["yes"].values())-yes_d)>1 or
                abs(sum(snaps_w[j]["no"].values()) -no_d) >1):
                stale = False; break
        stale_evts.append({"move_pct": move*100, "stale": stale})

if stale_evts:
    sdf = pd.DataFrame(stale_evts)
    print(f"  Spot-move >0.1% events: {len(sdf)}")
    print(f"  Stale rate (book frozen in 3s): {sdf['stale'].mean():.3f}")
    print(f"  Move pct mean={sdf['move_pct'].mean():.3f}%  max={sdf['move_pct'].max():.3f}%")
else:
    print("  No spot-move events")

# ══ IS/OOS TESTS ON TRADE PARQUET (A-D) ════════════════════════════════════
print("\n── Trade-parquet IS/OOS split ──")
all_ws = sorted(ws_trade_summary.keys())
n_is = int(len(all_ws) * 0.6)
is_ws  = set(all_ws[:n_is])
oos_ws = set(all_ws[n_is:])
print(f"IS: {len(is_ws)} windows, OOS: {len(oos_ws)} windows")

# Build per-window dataframe with all trade metrics
wrows = []
for ws, sm_t in ws_trade_summary.items():
    wrows.append({
        "ws": ws, "split": "IS" if ws in is_ws else "OOS",
        **sm_t
    })
wdf = pd.DataFrame(wrows)

# Per-window ladder metrics from book data (only 4 windows, so sparse)
ws_ladder = ldf.groupby("ws").agg(
    pull_rate=("pull","mean"),
    mm_score=("modal_frac", lambda x: (x>0.5).mean()),
).to_dict("index")

wdf["pull_rate"] = wdf["ws"].map(lambda w: ws_ladder.get(w,{}).get("pull_rate", np.nan))
wdf["mm_score"]  = wdf["ws"].map(lambda w: ws_ladder.get(w,{}).get("mm_score",  np.nan))

print("\n=== TEST A: Cancel-proxy vs pair-rate ===")
print("  (Note: book-diff cancel only available for 4 windows; test on trade metrics instead)")
print("  Trade-based imbalance vs pair_rate Pearson r by split:")
for split in ["IS","OOS"]:
    sub = wdf[wdf["split"]==split]
    r_n = sub["pair_rate"].corr(sub["n_trades"])
    r_i = sub["pair_rate"].corr(sub["imbalance"])
    print(f"  {split} (n={len(sub)}): r(pair_rate,n_trades)={r_n:+.4f}  r(pair_rate,imbalance)={r_i:+.4f}")

# Tertile analysis on n_trades (high activity = harder to pair)
wdf["vol_tert"] = pd.qcut(wdf["n_trades"].rank(method="first"), 3, labels=["Low","Mid","High"])
print("\n  Pair-rate by volume tertile (all windows):")
print(wdf.groupby("vol_tert")["pair_rate"].agg(["mean","count"]).round(4).to_string())

print("\n=== TEST B: Imbalance window stats ===")
wdf["adverse"] = wdf["imbalance"] > 0.5
print(f"  Adverse windows (imbal>50%): {wdf['adverse'].sum()} / {len(wdf)} ({100*wdf['adverse'].mean():.1f}%)")
for split in ["IS","OOS"]:
    sub = wdf[wdf["split"]==split]
    adv_rate = sub["adverse"].mean()
    print(f"  {split}: adverse_rate={adv_rate:.3f}  mean_pair_rate={sub['pair_rate'].mean():.4f}")

print("\n=== TEST C: Cluster windows by counterparty mix ===")
wdf["mm_dom"]  = wdf["pair_rate"] > wdf["pair_rate"].median()
wdf["dir_dom"] = wdf["imbalance"] > wdf["imbalance"].median()
def clabel(row):
    if row["mm_dom"] and not row["dir_dom"]:   return "Balanced-high"
    elif not row["mm_dom"] and row["dir_dom"]: return "Directional"
    elif row["mm_dom"] and row["dir_dom"]:     return "Mixed"
    else:                                       return "Balanced-low"
wdf["cluster"] = wdf.apply(clabel, axis=1)
csum = wdf.groupby("cluster").agg(
    n=("ws","count"),
    pair_rate=("pair_rate","mean"),
    imbalance=("imbalance","mean"),
    n_trades=("n_trades","mean"),
    adverse_rate=("adverse","mean"),
)
print(csum.round(3).to_string())

print("\n=== TEST D: Distinct systematic quoters ===")
fps = ldf.groupby(["side","modal_sz"]).agg(
    appearances=("ws","count"),
    modal_frac_mean=("modal_frac","mean"),
    n_windows=("ws","nunique"),
).reset_index().sort_values("appearances", ascending=False)
print("\n  Top-12 fingerprints:")
print(fps.head(12).round(3).to_string(index=False))
nwin = len(windows_book)
for side in ("yes","no"):
    sub_l = ldf[ldf["side"]==side]
    fp_s = sub_l.groupby("modal_sz")["ws"].nunique()
    sig = (fp_s / nwin > 0.10).sum()
    top = fp_s[fp_s/nwin > 0.05].sort_values(ascending=False).head(6).to_dict()
    print(f"\n  Distinct quoters ({side}, >10% windows): {sig}")
    print(f"  {top}")

# Key hypothesis check
yes_265 = (ldf[ldf["side"]=="yes"]["modal_sz"] == 265).mean()
no_250  = (ldf[ldf["side"]=="no"]["modal_sz"]  == 250).mean()
print(f"\nKey hypothesis — YES=265: {yes_265*100:.1f}% of snaps  |  NO=250: {no_250*100:.1f}% of snaps")

print("\n=== DONE ===")
