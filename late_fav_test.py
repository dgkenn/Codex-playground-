"""
late_fav_test.py
Late-window favorite-bid maker strategy test on Kalshi 15-min BTC binaries.
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

HIST_PATH   = "/home/user/Codex-playground-/hist_kalshi_btc15m.parquet"
TRADES_PATH = "/home/user/Codex-playground-/trades_kalshi_btc15m.parquet"

# ── helpers ───────────────────────────────────────────────────────────────────

def to_arr(v, dtype=np.float64):
    if v is None:
        return None
    try:
        return np.asarray(v, dtype=dtype)
    except Exception:
        return None

# ── load & diagnostics ────────────────────────────────────────────────────────

hist = pd.read_parquet(HIST_PATH)
if hist.index.name == "ws":
    hist = hist.reset_index()

trades = pd.read_parquet(TRADES_PATH)
if trades.index.name == "ws":
    trades = trades.reset_index()

hist["ws"]   = hist["ws"].astype(np.int64)
trades["ws"] = trades["ws"].astype(np.int64)

print("=" * 60)
print("DIAGNOSTICS")
print("=" * 60)
print(f"hist   : {hist.shape[0]} rows  cols={list(hist.columns)}")
print(f"trades : {trades.shape[0]} rows  cols={list(trades.columns)}")
for col in ["bid_path", "ask_path", "spot_path"]:
    if col in hist.columns:
        v = to_arr(hist[col].iloc[0])
        print(f"  hist[{col}]: len={len(v) if v is not None else 'None'}")
for col in ["t", "p", "sz"]:
    if col in trades.columns:
        v = to_arr(trades[col].iloc[0])
        print(f"  trades[{col}]: len={len(v) if v is not None else 'None'}")

# ── build trades lookup: ws -> arrays ────────────────────────────────────────

trades_map = {}
for i in range(len(trades)):
    row = trades.iloc[i]
    ws   = int(row["ws"])
    t_a  = to_arr(row["t"])
    p_a  = to_arr(row["p"])
    sz_a = to_arr(row["sz"])
    buy_a = to_arr(row["buy"], dtype=bool)
    if t_a is not None and len(t_a) > 0:
        trades_map[ws] = (t_a, p_a, sz_a, buy_a)

print(f"  trades windows loaded: {len(trades_map)}")

# ── day count ─────────────────────────────────────────────────────────────────

hist_dates = pd.to_datetime(hist["ws"], unit="s").dt.date
n_days_total = hist_dates.nunique()
ws_to_date = dict(zip(hist["ws"].values, hist_dates.values))
print(f"  total days in hist: {n_days_total}")
print()

# ── parameter grid ────────────────────────────────────────────────────────────

K_VALUES = [12, 13, 14]
T_VALUES = [0.93, 0.95, 0.97]

# spot_path: 15 samples (one per minute, 0..14)

# ── core loop ─────────────────────────────────────────────────────────────────

records = []

for i in range(len(hist)):
    row = hist.iloc[i]
    try:
        ws     = int(row["ws"])
        res_up = bool(int(row["res_up"]))
        bid_p  = to_arr(row["bid_path"])
        ask_p  = to_arr(row["ask_path"])
        spot_p = to_arr(row["spot_path"])
        date   = ws_to_date[ws]
    except Exception:
        continue

    if bid_p is None or len(bid_p) < 15:
        continue
    if ask_p is None or len(ask_p) < 15:
        continue
    if spot_p is None or len(spot_p) < 2:
        continue

    # sigma_1min from pct-changes across all spot samples
    pct_ch = np.diff(spot_p) / np.where(spot_p[:-1] != 0, spot_p[:-1], np.nan)
    pct_ch = pct_ch[np.isfinite(pct_ch)]
    sigma_1min = (np.std(pct_ch) * np.mean(spot_p)) if len(pct_ch) >= 2 else 1e-9
    if not (np.isfinite(sigma_1min) and sigma_1min > 0):
        sigma_1min = 1e-9

    strike = spot_p[0]
    td = trades_map.get(ws)

    for k in K_VALUES:
        try:
            bid_k = float(bid_p[k])
            ask_k = float(ask_p[k])
        except (IndexError, ValueError):
            continue
        if not (np.isfinite(bid_k) and np.isfinite(ask_k)):
            continue
        if ask_k <= bid_k or ask_k <= 0 or bid_k < 0:
            continue

        mid_k = (bid_k + ask_k) / 2.0
        fav_yes   = mid_k > 0.5
        fav_price = mid_k if fav_yes else (1.0 - mid_k)

        # spot at minute k (15-sample path, one per minute)
        spot_k = spot_p[k] if k < len(spot_p) else spot_p[-1]
        minutes_left = 14 - k
        z_abs = abs(spot_k - strike) / (sigma_1min * np.sqrt(max(minutes_left, 1)))

        for T in T_VALUES:
            if fav_price < T:
                continue

            our_bid = bid_k if fav_yes else (1.0 - ask_k)

            # --- fill opportunity ---
            contracts_filled = 0.0
            has_fill = False

            if td is not None:
                t_a, p_a, sz_a, buy_a = td
                t_start = ws + 60.0 * k
                t_end   = ws + 900.0
                mask_t = (t_a >= t_start) & (t_a <= t_end)

                if fav_yes:
                    mask_f = mask_t & (~buy_a) & (p_a <= bid_k)
                else:
                    mask_f = mask_t & (buy_a) & (p_a >= ask_k)

                if mask_f.any():
                    contracts_filled = float(sz_a[mask_f].sum()) / 100.0
                    has_fill = True

            fav_wins = res_up if fav_yes else (not res_up)
            pnl = (1.0 - our_bid) if fav_wins else (-our_bid)

            records.append({
                "ws":       ws,
                "k":        k,
                "T":        T,
                "fav_yes":  fav_yes,
                "our_bid":  our_bid,
                "has_fill": has_fill,
                "contracts": contracts_filled,
                "fav_wins": fav_wins,
                "pnl":      pnl,
                "z":        z_abs,
                "date":     date,
            })

df = pd.DataFrame(records)
print(f"Qualifying (ws, k, T) events: {len(df)}")
if len(df) == 0:
    print("ERROR: no qualifying events found — check bid/ask/T thresholds")
    raise SystemExit(1)
print()

# ── ANALYSIS 1 — FILL OPPORTUNITY ────────────────────────────────────────────

print("=" * 62)
print("ANALYSIS 1 — FILL OPPORTUNITY")
print("=" * 62)
print(f"{'k':>3} {'T':>5} | {'qual/day':>9} {'fill%':>7} {'med_ctr':>8} {'mean_ctr':>9}")
print("-" * 50)

for k in K_VALUES:
    for T in T_VALUES:
        s = df[(df["k"] == k) & (df["T"] == T)]
        if s.empty:
            continue
        nd  = s["date"].nunique() or 1
        qpd = len(s) / nd
        fp  = s["has_fill"].mean() * 100
        fil = s[s["has_fill"]]["contracts"]
        med  = fil.median() if len(fil) else 0.0
        mean = fil.mean()   if len(fil) else 0.0
        print(f"{k:>3} {T:>5.2f} | {qpd:>9.2f} {fp:>6.1f}% {med:>8.2f} {mean:>9.2f}")

print()

# ── ANALYSIS 2 — REALIZED EV ─────────────────────────────────────────────────

print("=" * 72)
print("ANALYSIS 2 — REALIZED EV  (weighted by min(contracts,5), fill-through only)")
print("=" * 72)
print(f"{'k':>3} {'T':>5} | {'EV/ctr':>8} {'win%':>7} {'flip|fill%':>11} {'flip|qual%':>11} {'adv_sel':>9}")
print("-" * 64)

for k in K_VALUES:
    for T in T_VALUES:
        s   = df[(df["k"] == k) & (df["T"] == T)]
        if s.empty:
            continue
        fil = s[s["has_fill"]].copy()
        uncond_flip = (1 - s["fav_wins"].mean()) * 100

        if fil.empty:
            print(f"{k:>3} {T:>5.2f} | {'n/a':>8} {'n/a':>7} {'n/a':>11} {uncond_flip:>10.1f}% {'n/a':>9}")
            continue

        w = np.minimum(fil["contracts"].values, 5.0)
        if w.sum() == 0:
            w = np.ones(len(fil))
        ev  = np.average(fil["pnl"].values,                   weights=w)
        win = np.average(fil["fav_wins"].values.astype(float), weights=w) * 100
        cond_flip = 100.0 - win
        adv_sel   = cond_flip - uncond_flip
        print(f"{k:>3} {T:>5.2f} | {ev:>8.4f} {win:>6.1f}% "
              f"{cond_flip:>10.1f}% {uncond_flip:>10.1f}% {adv_sel:>+9.2f}%")

print()

# ── ANALYSIS 3 — Z-CONDITIONING ──────────────────────────────────────────────

print("=" * 62)
print("ANALYSIS 3 — Z-CONDITIONING  (fill events by |z| bucket)")
print("=" * 62)
print(f"{'k':>3} {'T':>5} {'|z|':>5} | {'EV/ctr':>8} {'fill%':>7} {'N_qual':>7}")
print("-" * 52)

Z_BUCKETS = [
    ("<1",  lambda z: z < 1.0),
    ("1-2", lambda z: (z >= 1.0) & (z < 2.0)),
    (">2",  lambda z: z >= 2.0),
]

for k in K_VALUES:
    for T in T_VALUES:
        s = df[(df["k"] == k) & (df["T"] == T)]
        if s.empty:
            continue
        for zlabel, zmask_fn in Z_BUCKETS:
            zs = s[zmask_fn(s["z"])]
            if zs.empty:
                continue
            fp = zs["has_fill"].mean() * 100
            fz = zs[zs["has_fill"]]
            if not fz.empty:
                w = np.minimum(fz["contracts"].values, 5.0)
                if w.sum() == 0:
                    w = np.ones(len(fz))
                ev   = np.average(fz["pnl"].values, weights=w)
                ev_s = f"{ev:>8.4f}"
            else:
                ev_s = "     n/a"
            print(f"{k:>3} {T:>5.2f} {zlabel:>5} | {ev_s} {fp:>6.1f}% {len(zs):>7}")

print()

# ── ANALYSIS 4 — IS vs OOS ────────────────────────────────────────────────────

print("=" * 62)
print("ANALYSIS 4 — IS vs OOS  (60/40 chronological split on ws)")
print("=" * 62)

all_ws = np.sort(hist["ws"].unique())
cut    = int(len(all_ws) * 0.6)
is_ws_set  = set(all_ws[:cut].tolist())
oos_ws_set = set(all_ws[cut:].tolist())

df_is  = df[df["ws"].isin(is_ws_set)]
df_oos = df[df["ws"].isin(oos_ws_set)]


def metrics(sub):
    if sub.empty:
        return (0.0, 0.0, float("nan"), 0.0)
    nd  = sub["date"].nunique() or 1
    qpd = len(sub) / nd
    fr  = sub["has_fill"].mean()
    fil = sub[sub["has_fill"]]
    if fil.empty:
        return (qpd, fr, float("nan"), 0.0)
    w = np.minimum(fil["contracts"].values, 5.0)
    if w.sum() == 0:
        w = np.ones(len(fil))
    ev = np.average(fil["pnl"].values, weights=w)
    return (qpd, fr, ev, qpd * fr * ev)


Z_GATES = [("all", None), ("z>=1", 1.0), ("z>=2", 2.0)]

best_evd  = -np.inf
best_key  = None
best_is_m = None
sweep     = []

for k in K_VALUES:
    for T in T_VALUES:
        for zname, zg in Z_GATES:
            si = df_is[(df_is["k"] == k) & (df_is["T"] == T)]
            if zg is not None:
                si = si[si["z"] >= zg]
            m = metrics(si)
            sweep.append((k, T, zname, zg, m))
            if m[3] > best_evd:
                best_evd  = m[3]
                best_key  = (k, T, zname, zg)
                best_is_m = m

bk, bT, bzname, bzg = best_key
so = df_oos[(df_oos["k"] == bk) & (df_oos["T"] == bT)]
if bzg is not None:
    so = so[so["z"] >= bzg]
oos_m = metrics(so)

print(f"\nBest IS combo: k={bk}, T={bT:.2f}, z_gate={bzname}")
print()
print(f"{'Metric':<26} {'IS':>10} {'OOS':>10}")
print("-" * 48)
rows_cmp = [
    ("qual windows/day",
     f"{best_is_m[0]:>10.2f}", f"{oos_m[0]:>10.2f}"),
    ("fill rate",
     f"{best_is_m[1]*100:>9.1f}%", f"{oos_m[1]*100:>9.1f}%"),
    ("mean EV/contract",
     f"{best_is_m[2]:>10.4f}" if np.isfinite(best_is_m[2]) else f"{'n/a':>10}",
     f"{oos_m[2]:>10.4f}"    if np.isfinite(oos_m[2])    else f"{'n/a':>10}"),
    ("expected EV/day",
     f"{best_is_m[3]:>10.4f}", f"{oos_m[3]:>10.4f}"),
]
for label, isv, oosv in rows_cmp:
    print(f"{label:<26} {isv} {oosv}")

print()
print("IS sweep — all combos (top 18 by EV/day):")
print(f"{'k':>3} {'T':>5} {'z_gate':>6} | {'q/day':>7} {'fill%':>7} {'EV/ctr':>8} {'EV/day':>9}")
print("-" * 55)
sweep_s = sorted(sweep, key=lambda x: x[4][3], reverse=True)
for (k, T, zn, zg, m) in sweep_s[:18]:
    mark = " *" if (k == bk and T == bT and zn == bzname) else ""
    ev_s = f"{m[2]:.4f}" if np.isfinite(m[2]) else "   n/a"
    print(f"{k:>3} {T:>5.2f} {zn:>6} | {m[0]:>7.2f} {m[1]*100:>6.1f}% {ev_s:>8} {m[3]:>9.4f}{mark}")

print()
print("Done.")
