"""
late_fav_grid60.py
Exhaustive 60-combo IS/OOS grid sweep of the late-window favorite-bid maker.
Grid: T in {0.90..0.99} x k in {13,14} x z_gate in {all, z>=1, z>=2}
Strict multiple-testing discipline with Bonferroni correction.
"""

import numpy as np
import pandas as pd
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

HIST_PATH   = "/home/user/Codex-playground-/hist_kalshi_btc15m.parquet"
TRADES_PATH = "/home/user/Codex-playground-/trades_kalshi_btc15m.parquet"

def to_arr(v, dtype=np.float64):
    if v is None:
        return None
    try:
        return np.asarray(v, dtype=dtype)
    except Exception:
        return None

# ── load ──────────────────────────────────────────────────────────────────────
hist = pd.read_parquet(HIST_PATH)
if hist.index.name == "ws":
    hist = hist.reset_index()
trades = pd.read_parquet(TRADES_PATH)
if trades.index.name == "ws":
    trades = trades.reset_index()

for df_ in [hist, trades]:
    df_["ws"] = df_["ws"].astype(np.int64)

trades_map = {}
for row in trades.itertuples(index=False):
    ws = int(row.ws)
    t_a  = to_arr(row.t)
    p_a  = to_arr(row.p)
    sz_a = to_arr(row.sz)
    buy_a = to_arr(row.buy, dtype=bool)
    if t_a is not None and len(t_a) > 0:
        trades_map[ws] = (t_a, p_a, sz_a, buy_a)

hist["date_"] = pd.to_datetime(hist["ws"], unit="s").dt.date
n_days_total  = hist["date_"].nunique()

# ── IS/OOS chronological split ────────────────────────────────────────────────
all_ws = np.sort(hist["ws"].unique())
cut = int(len(all_ws) * 0.6)
is_ws_set  = set(all_ws[:cut].tolist())
oos_ws_set = set(all_ws[cut:].tolist())

# ── parameters ────────────────────────────────────────────────────────────────
K_VALUES = [13, 14]
T_VALUES = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99]
Z_GATES  = [("all", None), ("z>=1", 1.0), ("z>=2", 2.0)]
SPOT_PER_MIN = 4

# ── build per-window records ──────────────────────────────────────────────────
records = []

for row in hist.itertuples(index=False):
    try:
        ws     = int(row.ws)
        res_up = bool(int(row.res_up))
        bid_p  = to_arr(row.bid_path)
        ask_p  = to_arr(row.ask_path)
        spot_p = to_arr(row.spot_path)
        date   = row.date_
    except Exception:
        continue

    if bid_p is None or len(bid_p) < 15:
        continue
    if ask_p is None or len(ask_p) < 15:
        continue
    if spot_p is None or len(spot_p) < 2:
        continue

    pct_ch = np.diff(spot_p) / np.where(spot_p[:-1] != 0, spot_p[:-1], np.nan)
    pct_ch = pct_ch[np.isfinite(pct_ch)]
    sigma_1min = (np.std(pct_ch) * np.mean(spot_p)) if len(pct_ch) >= 2 else 0.0
    if sigma_1min <= 0 or not np.isfinite(sigma_1min):
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
        if ask_k <= bid_k or ask_k <= 0 or bid_k <= 0:
            continue

        mid_k     = (bid_k + ask_k) / 2.0
        fav_yes   = mid_k > 0.5
        fav_price = mid_k if fav_yes else (1.0 - mid_k)

        spot_idx  = min(k * SPOT_PER_MIN, len(spot_p) - 1)
        spot_k    = spot_p[spot_idx]
        minutes_left = 14 - k
        z_abs = abs(spot_k - strike) / (sigma_1min * np.sqrt(max(minutes_left, 1)))

        for T in T_VALUES:
            if fav_price < T:
                continue

            our_bid = bid_k if fav_yes else (1.0 - ask_k)

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
                "ws":        ws,
                "k":         k,
                "T":         T,
                "fav_yes":   fav_yes,
                "our_bid":   our_bid,
                "has_fill":  has_fill,
                "contracts": contracts_filled,
                "fav_wins":  fav_wins,
                "pnl":       pnl,
                "z":         z_abs,
                "date":      date,
                "fold":      "IS" if ws in is_ws_set else "OOS",
            })

df = pd.DataFrame(records)

# ── per-window EV for t-tests ─────────────────────────────────────────────────
# For each qualifying filled window: EV = pnl (weighted) per contract
# We want a per-window single EV observation for the paired t-test

def combo_metrics(sub):
    """Returns: qpd, fill_rate, ev_ctr, ev_day, t_stat, n_fills, n_days"""
    if sub.empty:
        return dict(qpd=0.0, fr=0.0, ev_ctr=np.nan, ev_day=0.0, t=np.nan, n_fills=0, n_days=0)
    nd = sub["date"].nunique() or 1
    qpd = len(sub) / nd
    fr  = sub["has_fill"].mean()
    fil = sub[sub["has_fill"] == True].copy()
    if fil.empty:
        return dict(qpd=qpd, fr=fr, ev_ctr=np.nan, ev_day=0.0, t=np.nan, n_fills=0, n_days=nd)
    w = np.minimum(fil["contracts"].values, 5.0)
    if w.sum() == 0:
        w = np.ones(len(fil))
    ev_ctr = np.average(fil["pnl"].values, weights=w)
    ev_day = qpd * fr * ev_ctr

    # t-test: per-window pnl observations (each filled window = one obs = pnl)
    pnl_obs = fil["pnl"].values
    if len(pnl_obs) >= 2:
        t_stat, _ = stats.ttest_1samp(pnl_obs, 0.0)
    else:
        t_stat = np.nan

    return dict(qpd=qpd, fr=fr, ev_ctr=ev_ctr, ev_day=ev_day, t=t_stat,
                n_fills=len(fil), n_days=nd)

# ── full 60-combo sweep ───────────────────────────────────────────────────────
df_is  = df[df["fold"] == "IS"]
df_oos = df[df["fold"] == "OOS"]

results = []
for k in K_VALUES:
    for T in T_VALUES:
        for zname, zg in Z_GATES:
            # IS
            si = df_is[(df_is.k == k) & (df_is.T == T)]
            if zg is not None:
                si = si[si.z >= zg]
            mi = combo_metrics(si)

            # OOS
            so = df_oos[(df_oos.k == k) & (df_oos.T == T)]
            if zg is not None:
                so = so[so.z >= zg]
            mo = combo_metrics(so)

            results.append({
                "k": k, "T": T, "z_gate": zname,
                "IS_qpd":   mi["qpd"],  "IS_fr":  mi["fr"],
                "IS_ev":    mi["ev_ctr"], "IS_evd": mi["ev_day"],
                "IS_t":     mi["t"],     "IS_nfil": mi["n_fills"],
                "OOS_qpd":  mo["qpd"],  "OOS_fr": mo["fr"],
                "OOS_ev":   mo["ev_ctr"], "OOS_evd": mo["ev_day"],
                "OOS_t":    mo["t"],    "OOS_nfil": mo["n_fills"],
            })

res = pd.DataFrame(results)

# ── distribution counts ───────────────────────────────────────────────────────
n_total = len(res)
n_is_pos  = int((res["IS_ev"] > 0).sum())
n_oos_pos = int((res["OOS_ev"] > 0).sum())
n_both    = int(((res["IS_ev"] > 0) & (res["OOS_ev"] > 0)).sum())

print("=" * 68)
print("LATE-WINDOW FAVORITE-BID: 60-COMBO IS/OOS GRID SWEEP")
print("=" * 68)
print(f"Total combos: {n_total}  (k={{13,14}} x T={{0.90..0.99}} x z_gate={{all,z>=1,z>=2}})")
print(f"Dataset: {n_days_total} days, IS={len(is_ws_set)} windows, OOS={len(oos_ws_set)} windows")
print()
print("DISTRIBUTION OF SIGN (headline):")
print(f"  IS-positive EV/ctr:          {n_is_pos:>3} / {n_total}")
print(f"  OOS-positive EV/ctr:         {n_oos_pos:>3} / {n_total}")
print(f"  Positive in BOTH IS and OOS: {n_both:>3} / {n_total}")
print()

# ── top-5 IS by EV/day, with OOS rows ────────────────────────────────────────
res_sorted = res.sort_values("IS_evd", ascending=False).reset_index(drop=True)
top5 = res_sorted.head(5)

print("TOP-5 IS COMBOS (by EV/day) WITH OOS ROWS:")
hdr = f"{'#':>2} {'k':>2} {'T':>5} {'z_gate':>6} | {'IS_ev':>8} {'IS_t':>7} {'IS_evd':>8} {'IS_nf':>6} | {'OOS_ev':>8} {'OOS_t':>7} {'OOS_evd':>8} {'OOS_nf':>6}"
print(hdr)
print("-" * len(hdr))
for i, row in top5.iterrows():
    is_t_s  = f"{row.IS_t:>7.2f}"  if np.isfinite(row.IS_t)  else "    n/a"
    oos_t_s = f"{row.OOS_t:>7.2f}" if np.isfinite(row.OOS_t) else "    n/a"
    is_ev_s  = f"{row.IS_ev:>8.4f}"  if np.isfinite(row.IS_ev)  else "     n/a"
    oos_ev_s = f"{row.OOS_ev:>8.4f}" if np.isfinite(row.OOS_ev) else "     n/a"
    print(f"{i+1:>2} {int(row.k):>2} {row.T:>5.2f} {row.z_gate:>6} | "
          f"{is_ev_s} {is_t_s} {row.IS_evd:>8.4f} {int(row.IS_nfil):>6} | "
          f"{oos_ev_s} {oos_t_s} {row.OOS_evd:>8.4f} {int(row.OOS_nfil):>6}")

print()

# ── Bonferroni survivors (|OOS t| >= 3.35) ───────────────────────────────────
# Also show soft bar: OOS t >= 2.0 + same sign
BONF_THRESH = 3.35
SOFT_THRESH = 2.0

survivors_bonf = res[(res["OOS_t"].abs() >= BONF_THRESH) & (res["OOS_ev"] > 0) & (res["IS_ev"] > 0)]
survivors_soft = res[(res["OOS_t"] >= SOFT_THRESH) & (res["OOS_ev"] > 0) & (res["IS_ev"] > 0)]

print(f"BONFERRONI SURVIVORS (|OOS t| >= {BONF_THRESH}, OOS ev > 0, same sign as IS):")
if survivors_bonf.empty:
    print("  NONE — no combo clears the Bonferroni bar.")
else:
    for _, row in survivors_bonf.iterrows():
        print(f"  k={int(row.k)}, T={row.T:.2f}, z={row.z_gate}: "
              f"IS ev={row.IS_ev:.4f} t={row.IS_t:.2f} | OOS ev={row.OOS_ev:.4f} t={row.OOS_t:.2f}")

print()
print(f"SOFT SURVIVORS (OOS t >= {SOFT_THRESH}, OOS ev > 0, same sign as IS):")
if survivors_soft.empty:
    print("  NONE.")
else:
    for _, row in survivors_soft.iterrows():
        print(f"  k={int(row.k)}, T={row.T:.2f}, z={row.z_gate}: "
              f"IS ev={row.IS_ev:.4f} t={row.IS_t:.2f} | OOS ev={row.OOS_ev:.4f} t={row.OOS_t:.2f} "
              f"ev/day={row.OOS_evd:.4f}")

print()

# ── sign-flip analysis ────────────────────────────────────────────────────────
n_sign_flip = int(((res["IS_ev"] > 0) & (res["OOS_ev"] < 0)).sum() +
                   ((res["IS_ev"] < 0) & (res["OOS_ev"] > 0)).sum())
n_is_valid = int((res["IS_ev"].notna()).sum())
print(f"SIGN FLIP ANALYSIS:")
print(f"  IS-positive combos:          {n_is_pos}")
print(f"  Of those, OOS sign-flip:     {int(((res['IS_ev']>0)&(res['OOS_ev']<0)).sum())}")
print(f"  IS-negative combos:          {int((res['IS_ev']<0).sum())}")
print(f"  Of those, OOS sign-flip:     {int(((res['IS_ev']<0)&(res['OOS_ev']>0)).sum())}")
print()

# ── full grid table for reference ────────────────────────────────────────────
print("FULL GRID (sorted by IS EV/day):")
print(f"{'k':>2} {'T':>5} {'z_gate':>6} | {'IS_ev':>8} {'IS_t':>7} {'IS_evd':>8} | {'OOS_ev':>8} {'OOS_t':>7} {'OOS_evd':>8}")
print("-" * 72)
for _, row in res_sorted.iterrows():
    is_t_s  = f"{row.IS_t:>7.2f}"  if np.isfinite(row.IS_t)  else "    n/a"
    oos_t_s = f"{row.OOS_t:>7.2f}" if np.isfinite(row.OOS_t) else "    n/a"
    is_ev_s  = f"{row.IS_ev:>8.4f}"  if np.isfinite(row.IS_ev)  else "     n/a"
    oos_ev_s = f"{row.OOS_ev:>8.4f}" if np.isfinite(row.OOS_ev) else "     n/a"
    flag = " *BONF" if abs(row.OOS_t) >= BONF_THRESH and row.OOS_ev > 0 and row.IS_ev > 0 else \
           " *soft" if row.OOS_t >= SOFT_THRESH and row.OOS_ev > 0 and row.IS_ev > 0 else ""
    print(f"{int(row.k):>2} {row.T:>5.2f} {row.z_gate:>6} | "
          f"{is_ev_s} {is_t_s} {row.IS_evd:>8.4f} | "
          f"{oos_ev_s} {oos_t_s} {row.OOS_evd:>8.4f}{flag}")

print()
print("Done.")
