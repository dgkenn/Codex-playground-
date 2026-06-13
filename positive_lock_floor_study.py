"""positive_lock_floor_study.py -- Backtest of the positive-lock floor risk fix.

RCA finding: the live bot's biggest loss bucket came from cross-minute box completions
where b_yes + b_no >= 1.00 (lock <= 0), i.e., a guaranteed-loss completion.
The fix proposed: refuse to complete any box with lock <= floor (hold or flatten instead).

Model:
  Same-minute clean-box replay (same k-slot as multi_asset_study.py):
    - got_b: not-buy taker hits YES bid at b0 (we buy YES at b0)
    - got_a: buy taker hits YES ask at a0 (we sell YES at a0)
    - Box lock = a0 - b0 (always positive same-minute; equals 1-(b_yes+b_no))
  Cross-minute strand chase:
    - If only one leg fills in minute k, a STRAND forms.
    - P0 (live): chase in subsequent minutes k1>k; accept cross-minute fill if
      lock(k1) = a_k1 - b0 >= -chase_max_give (currently 0.02 -> allows lock down to -2c).
    - Policy A: only accept cross-minute fill if lock > floor (floor in {0, 0.5c, 1c}).
    - Policy B: Policy-A floor + flatten the unpaired leg at the touch when lock < floor.

Run: python positive_lock_floor_study.py
Output: prints IS/OOS metrics table and diff-vs-P0 t-tests.
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

DATA_DIR = "/tmp/sh"   # pre-fetched parquet files
ASSET = "btc"

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
h = pd.read_parquet(f"{DATA_DIR}/hist_kalshi_{ASSET}15m.parquet").set_index("ws")
t = pd.read_parquet(f"{DATA_DIR}/trades_kalshi_{ASSET}15m.parquet").set_index("ws")
common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
IS_WS  = common[:cut]
OOS_WS = common[cut:]
print(f"Windows: total={n}  IS={len(IS_WS)} (60%)  OOS={len(OOS_WS)} (40%)")
print(f"Date range: {pd.Timestamp(common[0], unit='s')} -> {pd.Timestamp(common[-1], unit='s')}")


# ─────────────────────────────────────────────────────────────────────────────
# Core replay
# ─────────────────────────────────────────────────────────────────────────────
def run_policy(
    ws_list: list,
    min_lock_complete: float = -0.02,   # minimum lock to accept cross-minute completion
    flatten: bool = False,              # if True: flatten strand at touch when lock < floor
) -> tuple[np.ndarray, dict]:
    """
    Replay same-minute clean-box + cross-minute strand chase.

    min_lock_complete: P0 default = -0.02 (allows up to -2c locked loss, matching
                       --chase-max-give 0.02). Policy A floors: 0.0 / 0.005 / 0.01.
    flatten: Policy B -- when cross-minute lock < floor, flatten strand at next minute's
             touch (sell YES at bid / buy YES at ask) rather than hold to settlement.
    """
    pnls: list[float] = []
    cnt = dict(boxes=0, cross=0, holds=0, flats=0, neg_lock_c=0)

    for ws in ws_list:
        hr = h.loc[ws]; tr = t.loc[ws]
        bid = np.asarray(hr["bid_path"], float)
        ask = np.asarray(hr["ask_path"], float)
        res = int(hr["res_up"])
        t_arr  = np.asarray(tr["t"],   float)
        p_arr  = np.asarray(tr["p"],   float)
        buy_arr = np.asarray(tr["buy"], float).astype(bool)
        win_pnl = 0.0

        for k in range(2, 13):
            b0, a0 = bid[k], ask[k]
            if (np.isnan(b0) or np.isnan(a0)
                    or not (0.03 <= (b0 + a0) / 2 <= 0.97)):
                continue

            # ── minute k+1: check for same-minute box ──────────────────────
            lo, hi = ws + 60*(k+1), ws + 60*(k+2)
            i0 = int(np.searchsorted(t_arr, lo))
            i1 = int(np.searchsorted(t_arr, hi))
            got_b = got_a = False
            for i in range(i0, i1):
                p = float(p_arr[i]); buy = bool(buy_arr[i])
                if not got_b and not buy and p <= b0 + 1e-9:
                    got_b = True
                if not got_a and buy and p >= a0 - 1e-9:
                    got_a = True
                if got_b and got_a:
                    break

            if got_b and got_a:
                # Same-minute box: lock = a0-b0 > 0 always; always complete.
                win_pnl += a0 - b0
                cnt["boxes"] += 1
                continue
            if not got_b and not got_a:
                continue   # no fill this minute

            # ── STRAND: one leg filled ──────────────────────────────────────
            if got_b:
                # Bought YES at b0. Settle value = res.
                pnl_hold = res - b0
                done = False
                for k1 in range(k + 1, 13):
                    a1 = ask[k1]; b1 = bid[k1]
                    if np.isnan(a1):
                        continue
                    lk = a1 - b0   # lock if we complete now
                    if lk > min_lock_complete:
                        # Try cross-minute fill
                        lo1, hi1 = ws + 60*(k1+1), ws + 60*(k1+2)
                        i0b = int(np.searchsorted(t_arr, lo1))
                        i1b = int(np.searchsorted(t_arr, hi1))
                        for i in range(i0b, i1b):
                            if bool(buy_arr[i]) and float(p_arr[i]) >= a1 - 1e-9:
                                win_pnl += lk; done = True; cnt["cross"] += 1
                                if lk <= 0:
                                    cnt["neg_lock_c"] += 1
                                break
                        if done:
                            break
                    elif flatten and not np.isnan(b1):
                        # Flatten: sell YES at best bid b1
                        win_pnl += b1 - b0; done = True; cnt["flats"] += 1
                        break
                if not done:
                    win_pnl += pnl_hold; cnt["holds"] += 1

            else:   # got_a only
                # Sold YES at a0. Settle value at risk = a0 - res.
                pnl_hold = a0 - res
                done = False
                for k1 in range(k + 1, 13):
                    b1 = bid[k1]; a1 = ask[k1]
                    if np.isnan(b1):
                        continue
                    lk = a0 - b1
                    if lk > min_lock_complete:
                        lo1, hi1 = ws + 60*(k1+1), ws + 60*(k1+2)
                        i0b = int(np.searchsorted(t_arr, lo1))
                        i1b = int(np.searchsorted(t_arr, hi1))
                        for i in range(i0b, i1b):
                            if not bool(buy_arr[i]) and float(p_arr[i]) <= b1 + 1e-9:
                                win_pnl += lk; done = True; cnt["cross"] += 1
                                if lk <= 0:
                                    cnt["neg_lock_c"] += 1
                                break
                        if done:
                            break
                    elif flatten and not np.isnan(a1):
                        # Flatten: buy YES at best ask a1 to close short
                        win_pnl += a0 - a1; done = True; cnt["flats"] += 1
                        break
                if not done:
                    win_pnl += pnl_hold; cnt["holds"] += 1

        pnls.append(win_pnl)

    return np.array(pnls), cnt


def metrics(pnls: np.ndarray) -> dict:
    a = pnls
    mean = float(np.mean(a) * 100)
    std  = float(np.std(a)  * 100)
    sharpe = mean / (std + 1e-9)
    negs = a[a < 0]
    dstd = float(np.std(negs) * 100) if len(negs) > 1 else max(std, 1e-9)
    sortino = mean / (dstd + 1e-9)
    skew  = float(pd.Series(a).skew())
    losses = sorted(a * 100)
    cvar95 = float(np.mean(losses[:max(1, int(len(losses) * 0.05))]))
    cum = np.cumsum(a) * 100
    mdd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    return dict(
        n=len(a), mean_c=round(mean, 4), total_c=round(float(np.sum(a)*100), 2),
        sharpe=round(sharpe, 4), sortino=round(sortino, 4),
        skew=round(skew, 4), cvar95_c=round(cvar95, 4),
        maxDD_c=round(mdd, 4), win_pct=round(100*float((a>0).mean()), 1),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Policy sweep
# ─────────────────────────────────────────────────────────────────────────────
POLICIES = [
    # (label,           min_lock_complete, flatten)
    ("P0_give0.02",     -0.02,  False),   # live default: accept lock >= -2c
    ("A_floor0c",        0.00,  False),   # strict positive-lock, hold strand
    ("A_floor0.5c",      0.005, False),   # 0.5c floor, hold strand
    ("A_floor1c",        0.01,  False),   # 1c floor, hold strand
    ("B_floor0c_flat",   0.00,  True),    # positive-lock + flatten at touch
]

results: dict[str, dict] = {}
for label, floor, flat in POLICIES:
    ip, ist = run_policy(IS_WS,  floor, flat)
    op, ost = run_policy(OOS_WS, floor, flat)
    results[label] = {
        "is": metrics(ip), "oos": metrics(op),
        "is_pnls": ip, "oos_pnls": op,
        "is_cnt": ist, "oos_cnt": ost,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Print results
# ─────────────────────────────────────────────────────────────────────────────
W = 104

def row(label, m):
    return (f"{label:<20} {m['n']:>5} {m['mean_c']:>+9.4f} {m['total_c']:>+9.2f} "
            f"{m['sharpe']:>+8.4f} {m['sortino']:>+8.4f} {m['skew']:>+7.4f} "
            f"{m['cvar95_c']:>+9.4f} {m['maxDD_c']:>9.4f} {m['win_pct']:>7.1f}%")

HDR = (f"{'Policy':<20} {'N':>5} {'mean_c':>9} {'total_c':>9} "
       f"{'Sharpe':>8} {'Sortino':>8} {'Skew':>7} {'CVaR95':>9} {'maxDD':>9} {'Win%':>8}")

print()
print("="*W)
print("POSITIVE-LOCK FLOOR STUDY: BTC 15M Kalshi (IS=60% / OOS=40%)")
print("="*W)
print()
print("IN-SAMPLE (first 60%, N=193 windows):")
print(HDR); print("-"*W)
for label, _, _ in POLICIES:
    print(row(label, results[label]["is"]))

print()
print("OUT-OF-SAMPLE (last 40%, N=130 windows):")
print(HDR); print("-"*W)
for label, _, _ in POLICIES:
    print(row(label, results[label]["oos"]))

print()
print("DIFF vs P0 (paired t-test, two-sided):")
p0_is  = results["P0_give0.02"]["is_pnls"]
p0_oos = results["P0_give0.02"]["oos_pnls"]
for label, _, _ in POLICIES[1:]:
    d_is  = results[label]["is_pnls"]  - p0_is
    d_oos = results[label]["oos_pnls"] - p0_oos
    t_is,  p_is  = scipy_stats.ttest_1samp(d_is,  0)
    t_oos, p_oos = scipy_stats.ttest_1samp(d_oos, 0)
    print(f"  {label:<20} IS  diff={np.mean(d_is)*100:+.4f}c/win  t={t_is:.3f}  p={p_is:.4f}")
    print(f"  {label:<20} OOS diff={np.mean(d_oos)*100:+.4f}c/win  t={t_oos:.3f}  p={p_oos:.4f}")

print()
print("EVENT COUNTS (IS+OOS combined):")
print(f"{'Policy':<20} {'boxes':>7} {'cross':>7} {'neg_lock':>10} {'holds':>7} {'flats':>7}")
print("-"*60)
for label, _, _ in POLICIES:
    ic = results[label]["is_cnt"]; oc = results[label]["oos_cnt"]
    print(f"{label:<20} {ic['boxes']+oc['boxes']:>7} {ic['cross']+oc['cross']:>7} "
          f"{ic['neg_lock_c']+oc['neg_lock_c']:>10} {ic['holds']+oc['holds']:>7} "
          f"{ic['flats']+oc['flats']:>7}")

# ─────────────────────────────────────────────────────────────────────────────
# Strand-level analysis: complete vs hold for neg-lock events
# ─────────────────────────────────────────────────────────────────────────────
print()
print("="*W)
print("STRAND ANALYSIS: neg-lock cross-minute events (lock in [-0.02, 0])")
print("="*W)

complete_pnls, hold_pnls = [], []
for ws in IS_WS + OOS_WS:
    hr = h.loc[ws]; tr = t.loc[ws]
    bid = np.asarray(hr["bid_path"], float)
    ask = np.asarray(hr["ask_path"], float)
    res = int(hr["res_up"])
    t_arr  = np.asarray(tr["t"],   float)
    p_arr  = np.asarray(tr["p"],   float)
    buy_arr = np.asarray(tr["buy"], float).astype(bool)

    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0+a0)/2 <= 0.97):
            continue
        lo, hi = ws+60*(k+1), ws+60*(k+2)
        i0, i1 = int(np.searchsorted(t_arr, lo)), int(np.searchsorted(t_arr, hi))
        got_b = got_a = False
        for i in range(i0, i1):
            p = float(p_arr[i]); buy = bool(buy_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9: got_b = True
            if not got_a and buy and p >= a0 - 1e-9:     got_a = True
            if got_b and got_a: break
        if got_b and got_a: continue
        if not got_b and not got_a: continue

        if got_b:
            pnl_h = res - b0
            for k1 in range(k+1, 13):
                a1 = ask[k1]
                if np.isnan(a1): continue
                lk = a1 - b0
                if not (-0.02 <= lk <= 0.0): continue   # only neg-lock within give window
                lo1, hi1 = ws+60*(k1+1), ws+60*(k1+2)
                i0b, i1b = int(np.searchsorted(t_arr, lo1)), int(np.searchsorted(t_arr, hi1))
                for i in range(i0b, i1b):
                    if bool(buy_arr[i]) and float(p_arr[i]) >= a1 - 1e-9:
                        complete_pnls.append(lk); hold_pnls.append(pnl_h); break
                else: continue
                break
        else:
            pnl_h = a0 - res
            for k1 in range(k+1, 13):
                b1 = bid[k1]
                if np.isnan(b1): continue
                lk = a0 - b1
                if not (-0.02 <= lk <= 0.0): continue
                lo1, hi1 = ws+60*(k1+1), ws+60*(k1+2)
                i0b, i1b = int(np.searchsorted(t_arr, lo1)), int(np.searchsorted(t_arr, hi1))
                for i in range(i0b, i1b):
                    if not bool(buy_arr[i]) and float(p_arr[i]) <= b1 + 1e-9:
                        complete_pnls.append(lk); hold_pnls.append(pnl_h); break
                else: continue
                break

cp = np.array(complete_pnls); hp = np.array(hold_pnls)
n_better_complete = int((cp > hp).sum())
print(f"Total neg-lock completions (lock in [-2c,0]): {len(cp)}")
print(f"  Mean PnL if COMPLETE: {cp.mean()*100:+.4f}c  (P0 behavior)")
print(f"  Mean PnL if HOLD:     {hp.mean()*100:+.4f}c  (Policy A behavior)")
print(f"  Delta COMPLETE-HOLD:  {(cp-hp).mean()*100:+.4f}c per event")
print(f"  Complete is BETTER in {n_better_complete}/{len(cp)} cases ({100*n_better_complete/max(len(cp),1):.1f}%)")
print(f"  CONCLUSION: completing neg-lock boxes is BETTER than holding to settle in "
      f"{100*n_better_complete/max(len(cp),1):.0f}% of cases")

if __name__ == "__main__":
    pass   # all output printed above at import time
