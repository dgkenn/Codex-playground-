#!/usr/bin/env python3
"""box_disposal_ev.py -- STRAND DISPOSAL EV: HOLD-to-settlement vs COMPLETE-by-cross.

ONE question for the Kalshi 15-min BTC maker-box bot: when one leg fills and the other does NOT
(a STRAND), do we CROSS to complete the box (pay the half-spread now, lock a known small loss) or
HOLD the naked leg to settlement (ride the leg's own settle EV)?

THE EV THEORY (margin, sunk basis cancels):
  Stranded YES leg, basis b. HOLD pays res in {0,1} -> E[HOLD]-b in expectation = (P(yes won) - b).
  COMPLETE by buying NO at the offer p_no pays (1 - p_no) certain. Margin E[COMPLETE]-E[HOLD] =
    (1 - p_no) - (b + (P(yes)-b)) ... but b cancels (sunk) so the HOLD-vs-COMPLETE DELTA is:
      delta = E[COMPLETE_leg_value] - E[HOLD_leg_value]
            = (1 - p_no_offer) - P(yes settles)        [for a stranded YES]
            = yes_bid - fair_yes  -  (half-spread we cross) ... <= 0 in a FAIR market.
  So in pure EV HOLDING wins by the half-spread UNLESS strands are ADVERSELY SELECTED (the leg got
  stranded because price ran against it -> P(yes settles) < the price we bought at -> holding has
  NEGATIVE drift beyond the spread). The whole question is whether toxicity > crossing spread, and
  whether it's state-dependent (moneyness / age).

WHAT THIS SCRIPT DOES
  1. Reconstruct every STRANDED leg from the historical tape (hist_kalshi_btc15m.parquet): a window
     where, replaying the front-of-queue maker fills with the live |net|<=1 always-pair rule, one
     leg fills and the opposite leg NEVER fills (the residual rides to settlement). For each strand
     record: side, basis (fill price), moneyness (YES-equiv price at strand minute), age (minutes
     unpaired -> the close), the COMPLETE cross price (opposite offer at strand time), and the
     REALIZED settlement (res_up).
  2. Realized EV of HOLD (ride to settlement) vs COMPLETE-by-cross at give caps {0,2,5,10,15,inf}.
  3. Condition on moneyness (|p-0.5| buckets) and age (minutes-to-close buckets).
  4. Cross-check against the LIVE strands (live-state winrec walk).

Self-contained: reads the precomputed window-book parquet (mid/bid/ask/spot paths + res_up).
Usage:  python box_disposal_ev.py [--hist hist_kalshi_btc15m.parquet]
"""
from __future__ import annotations
import argparse, json, subprocess
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Strand reconstruction from the precomputed window books
# --------------------------------------------------------------------------------------
# The maker quotes YES at the bid and NO at (1-ask) every minute. Front-of-queue (q0=0) fill model
# matching box_policy_ab.window_fills: a YES-buy fills if a taker SELLS at/below our bid in the next
# minute; a NO-buy fills if a taker BUYS at/above our ask. We do NOT have the per-window taker tape
# in this parquet, so we use the standard book-path proxy used across the repo's offline studies:
# a leg "fills" at minute k when the touch is crossed by the path -- i.e. we model the maker as
# filled on the side the market is LEAVING (the adverse-selection fill that the live audit found).
#
# Concretely (the toxic-fill model, consistent with COMPLETION_MODEL: "filled on the side the market
# is about to run over"): scanning minutes k=2..12, the FIRST leg to fill is the side whose touch
# the NEXT-minute mid moves THROUGH (down-move fills our YES bid as price falls past it; up-move
# fills our NO/ask as price rises past it). The opposite leg is STRANDED if the mid never returns to
# cross its touch before close. This reproduces the adversely-selected strand the EV question is about.

def _load_trades(trades):
    """ws -> (t, p, sz, buy) sorted arrays from the taker tape parquet."""
    tp = {}
    for row in trades.itertuples():
        t = np.asarray(row.t, float); order = np.argsort(t)
        tp[row.ws] = (t[order], np.asarray(row.p, float)[order],
                      np.asarray(row.sz, float)[order], np.asarray(row.buy, bool)[order])
    return tp


def reconstruct_strands(hist, trades, q0=0.0):
    """Yield one record per stranded leg using the REAL taker tape + book paths.

    Fill model = box_policy_ab.window_fills (front-of-queue q0): scanning minutes k=2..12, our resting
    YES-buy at bid[k] fills if a taker SELLS at/below bid[k] in minute k+1; our NO-buy (=BUY YES-ask
    at ask[k]) fills if a taker BUYS at/above ask[k]. The FIRST side to fill opens a leg (basis = our
    quoted price); a STRAND is a window where the opposite side NEVER fills before close. The COMPLETE
    cross price is the REAL opposite offer at the strand minute (yes-ask for a NO-leg, no-offer=1-yes-bid
    for a YES-leg) -> the give is the live half-spread, not a mirror artifact."""
    tp = _load_trades(trades)
    out = []
    for row in hist.itertuples():
        ws = row.ws
        if ws not in tp:
            continue
        res = int(row.res_up)
        bid = np.asarray(row.bid_path, float)
        ask = np.asarray(row.ask_path, float)
        n = len(bid)
        t_arr, p_arr, sz_arr, buy_arr = tp[ws]
        first = None        # (side, k, basis) of the first leg to fill
        paired = False
        for k in range(2, min(13, n - 1)):
            b0, a0 = bid[k], ask[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
                continue
            lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            qb = qa = q0; fill_yes = fill_no = False
            for i in range(i0, i1):
                p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
                if not buy and p <= b0 + 1e-9:                 # taker sell hits our YES bid
                    if qb >= sz: qb -= sz
                    else: fill_yes = True
                if buy and p >= a0 - 1e-9:                      # taker buy lifts our ask -> NO leg
                    if qa >= sz: qa -= sz
                    else: fill_no = True
            if first is None:
                if fill_yes and not fill_no:
                    first = ("yes", k, float(b0))
                elif fill_no and not fill_yes:
                    first = ("no", k, float(round(1.0 - a0, 4)))
                elif fill_yes and fill_no:
                    paired = True; break                       # both filled same minute -> box
            else:
                os_ = first[0]
                if (os_ == "yes" and fill_no) or (os_ == "no" and fill_yes):
                    paired = True; break                       # opposite leg paired later -> box
        if first is None or paired:
            continue
        open_side, k, basis = first
        # DISPOSAL minute kd: the live cross fires when the leg is AGED (>=90s ~ 1-2 min) OR near close.
        # Price the completing cross at the book ~2 min after the fill (or last valid minute) -- this is
        # where the book has MOVED and the give-cap actually bites. cross_px = the opposite OFFER then.
        kd = k
        for kk in range(min(k + 2, n - 1), k, -1):
            if not np.isnan(bid[kk]) and not np.isnan(ask[kk]):
                kd = kk; break
        bd, ad = bid[kd], ask[kd]
        if np.isnan(bd) or np.isnan(ad):
            bd, ad = bid[k], ask[k]
        if open_side == "yes":
            yes_equiv = float(basis)
            cross_px = float(round(1.0 - bd, 4))               # BUY NO at the NO offer = 1 - yes_bid(kd)
            hold_val = float(res)
        else:
            yes_equiv = float(1.0 - basis)
            cross_px = float(round(ad, 4))                     # BUY YES at the YES offer(kd)
            hold_val = float(1 - res)
        lock = 1.0 - basis - cross_px                          # $ locked completing (give = -lock)
        complete_val = 1.0 - cross_px                          # certain leg value if completed
        out.append({
            "ws": ws, "side": open_side, "basis": basis, "k": k, "kd": kd,
            "yes_equiv": yes_equiv, "moneyness": abs(yes_equiv - 0.5), "age_min": (12 - k),
            "res_up": res, "cross_px": cross_px, "lock": lock,
            "hold_val": hold_val, "complete_val": complete_val,
        })
    return pd.DataFrame(out)


# --------------------------------------------------------------------------------------
# EV comparison: HOLD vs COMPLETE at a give cap
# --------------------------------------------------------------------------------------
# Margin (basis is SUNK -> cancels): per strand we compare the LEG VALUE realized.
#   HOLD     leg value = hold_val (res for YES, 1-res for NO)  -- the {0,1} settlement
#   COMPLETE leg value = complete_val = 1 - cross_px           -- certain, if cross_ok at the cap
# A give cap g means: only cross if the give (-lock = cross_px - (1-basis)) <= g; else HOLD.
# Per-strand DELTA(complete - hold) at cap g:
#   if give <= g:  complete_val - hold_val
#   else:          0  (we hold either way)
# We report mean DELTA = expected c/STRAND improvement of the cap-g COMPLETE policy over pure HOLD.

def ev_table(df, caps=(0.0, 0.02, 0.05, 0.10, 0.15, 9.99)):
    rows = []
    give = -df["lock"].values                       # cents we pay to complete (>=0 normal)
    delta_all = (df["complete_val"] - df["hold_val"]).values
    hold_mean = df["hold_val"].mean()
    for g in caps:
        cross = give <= g + 1e-9
        d = np.where(cross, delta_all, 0.0)
        rows.append({
            "give_cap": g, "n_cross": int(cross.sum()), "n_hold": int((~cross).sum()),
            "frac_cross": cross.mean(),
            "mean_delta_c": 100 * d.mean(),          # c/strand: COMPLETE@cap minus HOLD
            "complete_ev_c": 100 * (np.where(cross, df["complete_val"], df["hold_val"]).mean()),
            "hold_ev_c": 100 * hold_mean,
        })
    return pd.DataFrame(rows)


def cond_table(df, by):
    """Mean HOLD vs full-COMPLETE leg value and crossing give, by a categorical column."""
    rows = []
    for key, g in df.groupby(by):
        give = -g["lock"].values
        rows.append({
            by: key, "n": len(g),
            "hold_ev_c": 100 * g["hold_val"].mean(),
            "complete_ev_c": 100 * g["complete_val"].mean(),
            "delta_complete_minus_hold_c": 100 * (g["complete_val"] - g["hold_val"]).mean(),
            "mean_give_c": 100 * give.mean(),
            "hold_winrate": g["hold_val"].mean(),     # P(stranded leg settles in-the-money)
        })
    return pd.DataFrame(rows)


def boot_ci(x, n=5000, seed=0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(n, len(x)), replace=True).mean(1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


# --------------------------------------------------------------------------------------
# LIVE strands (winrec walk over origin/live-state) -- sanity check, small N
# --------------------------------------------------------------------------------------
def _walk(path):
    try:
        commits = subprocess.check_output(["git", "log", "--format=%H", "origin/live-state"]).decode().split()
    except Exception:
        return []
    out = []
    for c in commits:
        try:
            blob = subprocess.check_output(["git", "show", f"{c}:{path}"], stderr=subprocess.DEVNULL).decode()
        except Exception:
            continue
        for ln in blob.splitlines():
            if ln.strip():
                try: out.append(json.loads(ln))
                except Exception: pass
    return out


def live_strands(asset="btc", days=("2026-06-13", "2026-06-14")):
    import requests
    B = "https://api.elections.kalshi.com/trade-api/v2"; ses = requests.Session(); sc = {}
    def settle(cid):
        if not cid: return None
        if cid in sc: return sc[cid]
        r = None
        for _ in range(3):
            try:
                r = ses.get(f"{B}/markets/{cid}", timeout=8).json().get("market", {}).get("result"); break
            except Exception: pass
        sc[cid] = r if r in ("yes", "no") else None
        return sc[cid]
    rows = []
    for day in days:
        wr = {}
        for r in _walk(f"live_state/{day}/kalshi_winrec_{asset}15m.jsonl"):
            if "ws" in r: wr[r["ws"]] = r
        for w in wr.values():
            if not w.get("stranded"):
                continue
            s = w.get("settle") or settle(w.get("cid"))
            ny, nn = w.get("n_yes", 0), w.get("n_no", 0)
            side = "yes" if ny > nn else "no"
            wm = w.get("window_mark")
            rows.append({
                "day": day, "ws": w["ws"], "cid": w.get("cid"), "side": side,
                "n_yes": ny, "n_no": nn, "abs_strand": w.get("abs_strand"),
                "cost_yes": w.get("cost_yes"), "cost_no": w.get("cost_no"),
                "window_mark": wm, "n_dispose_cross": w.get("n_dispose_cross"),
                "legging_gap_s": w.get("legging_gap_s"), "realized": w.get("realized"),
                "settle": s,
            })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist", default="hist_kalshi_btc15m.parquet")
    ap.add_argument("--trades", default="trades_kalshi_btc15m.parquet")
    ap.add_argument("--no-live", action="store_true")
    a = ap.parse_args()

    hist = pd.read_parquet(a.hist)
    trades = pd.read_parquet(a.trades)
    df = reconstruct_strands(hist, trades)
    n_win = len(set(hist.ws) & set(trades.ws))
    print(f"=== HISTORICAL TAPE: {n_win} windows, {len(df)} reconstructed strands "
          f"({100*len(df)/n_win:.1f}% strand rate, front-of-queue adverse-fill model) ===\n")

    # overall EV
    print("--- HOLD vs COMPLETE-by-cross, by give cap (c/strand; delta = COMPLETE@cap - HOLD) ---")
    et = ev_table(df)
    print(et.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    lo, hi = boot_ci(100 * (df["complete_val"] - df["hold_val"]))
    print(f"\nUncapped COMPLETE-minus-HOLD delta: mean {100*(df['complete_val']-df['hold_val']).mean():+.2f}c/strand"
          f"  95% CI [{lo:+.2f}, {hi:+.2f}]")
    print(f"HOLD leg win-rate (stranded leg settles ITM): {df['hold_val'].mean():.3f}  "
          f"(if << basis -> toxic/adversely selected)")
    print(f"mean strand basis: {df['basis'].mean():.3f}   mean cross give: {100*(-df['lock']).mean():.2f}c")

    # by moneyness
    df["money_bkt"] = pd.cut(df["moneyness"], [-.01, .10, .25, .51],
                             labels=["ATM(|p-.5|<=.10)", "MID(.10-.25)", "TAIL(>.25)"])
    print("\n--- by MONEYNESS (|YES-equiv - 0.5|) ---")
    print(cond_table(df, "money_bkt").to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # by age
    df["age_bkt"] = pd.cut(df["age_min"], [-1, 1, 4, 99],
                           labels=["LATE(<=1m left)", "MID(2-4m)", "EARLY(>4m)"])
    print("\n--- by AGE (minutes the leg sits unpaired before close) ---")
    print(cond_table(df, "age_bkt").to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # by side
    print("\n--- by SIDE ---")
    print(cond_table(df, "side").to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # interaction: tail x late (the toxic-near-close regime) vs ATM
    print("\n--- KEY REGIMES (delta = COMPLETE - HOLD, +=complete wins) ---")
    for label, mask in [
        ("TAIL & LATE (deep-OTM near close)", (df.moneyness > .25) & (df.age_min <= 1)),
        ("ATM & EARLY",                       (df.moneyness <= .10) & (df.age_min > 1)),
        ("TAIL (any age)",                    df.moneyness > .25),
        ("ATM (any age)",                     df.moneyness <= .10),
    ]:
        g = df[mask]
        if len(g) < 3:
            print(f"  {label:36s} n={len(g):3d}  (too few)"); continue
        d = 100 * (g["complete_val"] - g["hold_val"])
        lo, hi = boot_ci(d)
        print(f"  {label:36s} n={len(g):3d}  delta={d.mean():+.2f}c  CI[{lo:+.2f},{hi:+.2f}]  "
              f"holdWR={g['hold_val'].mean():.2f} give={100*(-g['lock']).mean():.1f}c")

    if not a.no_live:
        print("\n=== LIVE STRANDS (origin/live-state winrec walk) -- sanity check, small N ===")
        try:
            ldf = live_strands()
            if len(ldf):
                with pd.option_context("display.max_columns", None, "display.width", 200):
                    print(ldf.to_string(index=False))
                # realized leg outcome: did the stranded side settle ITM?
                ldf["hold_itm"] = ldf.apply(lambda r: int(r["settle"] == r["side"])
                                            if r["settle"] in ("yes", "no") else np.nan, axis=1)
                hv = ldf["hold_itm"].dropna()
                print(f"\nlive strands with settlement: {len(hv)}  stranded-leg ITM rate: "
                      f"{hv.mean():.2f}" if len(hv) else "\n(no settled live strands)")
            else:
                print("(no live strands found)")
        except Exception as e:
            print(f"(live walk failed: {e})")


if __name__ == "__main__":
    main()
