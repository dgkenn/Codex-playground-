"""orphan_playbook_study.py -- t37 ORPHAN PLAYBOOK study.

For every strand event in the BTC 15-min tape, compare three policies:
  1. HOLD  : ride to settlement (current behavior)
  2. SELL-NOW: flatten as taker at next minute's touch
  3. CHASE-with-lock-floor(give): post the missing leg at a floor that limits max loss to -give;
     complete if a same-direction taker hits our price within the window; else hold.

Output: compact tables only. No raw dataframe dumps.
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd

os.chdir("/tmp/code")
sys.path.insert(0, "/tmp/code")
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────────────────────────────────
h = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")

common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
is_ws  = set(common[:cut])
oos_ws = set(common[cut:])

print(f"Common windows: {n}  IS={cut}  OOS={n-cut}")

# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────
def arr(x):
    return np.asarray(x, float)

PRICE_BUCKETS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
PRICE_LABELS  = ["<0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", ">0.8"]

def price_bucket(p):
    for i, (lo, hi) in enumerate(zip(PRICE_BUCKETS[:-1], PRICE_BUCKETS[1:])):
        if p < hi:
            return PRICE_LABELS[i]
    return PRICE_LABELS[-1]

GIVE_VALS = [0.00, 0.01, 0.02, 0.03]

# ──────────────────────────────────────────────────────────────────────────
# Main replay loop — extract every strand event + pnl under each policy
# ──────────────────────────────────────────────────────────────────────────
records = []  # one row per strand event

for ws in common:
    split = "IS" if ws in is_ws else "OOS"
    h_row = h.loc[ws]
    t_row = t.loc[ws]

    bid_path  = arr(h_row["bid_path"])   # length-15
    ask_path  = arr(h_row["ask_path"])   # length-15
    res       = int(h_row["res_up"])     # 0 or 1

    t_arr  = arr(t_row["t"])
    p_arr  = arr(t_row["p"])
    sz_arr = arr(t_row["sz"])
    buy_arr = arr(t_row["buy"]).astype(bool)

    for k in range(2, 13):
        b0 = bid_path[k]
        a0 = ask_path[k]
        if np.isnan(b0) or np.isnan(a0):
            continue
        mid = (b0 + a0) / 2.0
        if not (0.03 <= mid <= 0.97):
            continue

        # Trades in minute k+1 (the fill minute)
        lo = ws + 60 * (k + 1)
        hi = ws + 60 * (k + 2)
        i0 = int(np.searchsorted(t_arr, lo))
        i1 = int(np.searchsorted(t_arr, hi))

        got_b = got_a = False
        for i in range(i0, i1):
            p  = float(p_arr[i])
            buy = bool(buy_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9:
                got_b = True
            if not got_a and buy and p >= a0 - 1e-9:
                got_a = True
            if got_b and got_a:
                break

        if got_b and got_a:
            # It's a box — skip
            continue
        if not got_b and not got_a:
            # Neither leg filled — skip
            continue

        # We have a strand
        if got_b and not got_a:
            # YES-strand: we bought YES at b0; hold pnl = res - b0
            side = "YES"
            entry = b0
            pnl_hold = float(res) - b0

            # SELL-NOW: sell YES at next minute's bid
            if k + 1 <= 14 and not np.isnan(bid_path[k + 1]):
                pnl_sell = bid_path[k + 1] - b0
            else:
                pnl_sell = pnl_hold  # fall back to hold

            # CHASE: try to complete by posting ask at a' = max(a0, b0 - give)
            # => lock pnl = a' - b0 >= -give
            # We look for a taker BUY at p >= a' - 1e-9 in slots k+1 .. 12
            pnl_chase = {}
            for give in GIVE_VALS:
                a_prime = max(a0, b0 - give)
                # Search later slots for a taker buy at >= a_prime
                completed = False
                for kk in range(k + 1, 13):
                    lo2 = ws + 60 * (kk + 1)
                    hi2 = ws + 60 * (kk + 2)
                    j0 = int(np.searchsorted(t_arr, lo2))
                    j1 = int(np.searchsorted(t_arr, hi2))
                    for j in range(j0, j1):
                        if bool(buy_arr[j]) and float(p_arr[j]) >= a_prime - 1e-9:
                            completed = True
                            break
                    if completed:
                        break
                if completed:
                    pnl_chase[give] = a_prime - b0   # locked
                else:
                    pnl_chase[give] = pnl_hold       # ride to settlement

        else:
            # NO-strand: we sold YES at a0 (short YES); hold pnl = a0 - res
            side = "NO"
            entry = a0
            pnl_hold = a0 - float(res)

            # SELL-NOW: buy back YES at next minute's ask
            if k + 1 <= 14 and not np.isnan(ask_path[k + 1]):
                pnl_sell = a0 - ask_path[k + 1]
            else:
                pnl_sell = pnl_hold

            # CHASE: try to complete by posting bid at b' = min(b0_at_k, a0 + give)
            # => lock pnl = a0 - b' >= -give
            # But note we don't have a paired b0; use current ask-side: b' = a0 + give
            # (accepting to buy YES back at most give worse than our sell price)
            # b' = a0 + give  =>  lock = a0 - b' = -give  (min lock at floor)
            # Actually: we want to BUY back YES (close the NO-strand) cheaply.
            # Post a BID to buy YES at b' = a0 + give [we sold at a0, buying back at a0+give = -give lock]
            # But that's worse! Let's be precise:
            # NO-strand: sold YES at a0. To close, buy YES back at b' <= a0 for lock >= 0,
            # or at b' = a0 + give for lock = a0 - (a0+give) = -give.
            # We look for a taker SELL at p <= b' + 1e-9 in later slots.
            # Symmetric: b' = min(a0, a0 + give) where "give" means how much we give up.
            # give=0 => b' = a0 (buy back at our sell price, lock=0)
            # give=0.01 => b' = a0 + 0.01 (pay 1c more, lock=-1c) -- this is WORSE
            # Actually re-read the spec: "b' = a0 + give capped sensibly"
            # The spec says: "complete if a taker SELL (buy==False) at p<=b'+1e-9 later -> pnl = a0 - b'"
            # For NO-strand the "chase" is: we post a BID to re-buy YES at b' = a0 + give
            # so pnl = a0 - b' = a0 - (a0+give) = -give (a guaranteed -give loss on completion)
            # OR: we interpret give as a tolerance for WORSE completion
            # Actually the symmetric form: for YES-strand, a' = max(a0, b0-give), lock = a'-b0 >= -give
            # For NO-strand, we post bid to buy YES at b' = min(b0_current, a0+give)?
            # The spec says "b' = a0 + give capped sensibly" with a note that lock = a0 - b' >= -give
            # a0 - b' >= -give => b' <= a0 + give
            # So b' = a0 + give is the WORST we'd pay to buy back.
            # We look for a taker SELL at p <= b' + 1e-9
            # Completion pnl = a0 - b' = a0 - (a0+give) = -give  (worst case)
            # But if a taker sells at p <= a0 (i.e., at or below our original ask),
            # pnl = a0 - p >= 0 (profitable!)
            # So we should search for the BEST available: use b' = a0 + give as the LIMIT price,
            # and when a trade at p <= b' occurs, lock pnl = a0 - p (actual price).
            # Wait, that's taker-side. We're posting a MAKER bid to buy YES at b'.
            # A taker will SELL (hit our bid) if their price <= b'.
            # The pnl = a0 - b' (we sold at a0, buy back at b').
            # If we post b' = a0 + give, that's a guaranteed -give lock = floor.
            # So pnl_chase = a0 - b' = -give when completed, or a0 - res when not.
            # Actually for the NO side, to make it symmetric with YES, we want:
            # a' for YES-strand = max(a0, b0 - give) so lock = a' - b0 in [-give, ...]
            # b' for NO-strand  = min(b0_at_k, a0 + give) where b0_at_k = current book bid
            # But we don't have a natural "b0_at_k" for NO since bid wasn't filled.
            # The spec says: b' = a0 + give (capped sensibly) meaning b' = a0 + give
            # and pnl on completion = a0 - b' = a0 - (a0+give) = -give.
            # This is the floor. But if we can find cheaper, we use the actual price.
            # Per spec: "complete if a taker SELL (buy==False) at p<=b'+1e-9 later -> pnl = a0 - b'"
            # So pnl = a0 - b' regardless of actual trade price (i.e., we posted the maker bid at b').
            pnl_chase = {}
            for give in GIVE_VALS:
                b_prime = a0 + give  # worst we'd pay to buy back (floor lock = -give)
                completed = False
                for kk in range(k + 1, 13):
                    lo2 = ws + 60 * (kk + 1)
                    hi2 = ws + 60 * (kk + 2)
                    j0 = int(np.searchsorted(t_arr, lo2))
                    j1 = int(np.searchsorted(t_arr, hi2))
                    for j in range(j0, j1):
                        if not bool(buy_arr[j]) and float(p_arr[j]) <= b_prime + 1e-9:
                            completed = True
                            break
                    if completed:
                        break
                if completed:
                    pnl_chase[give] = a0 - b_prime   # = -give
                else:
                    pnl_chase[give] = pnl_hold

        rec = {
            "ws": ws,
            "split": split,
            "side": side,
            "k": k,
            "entry": entry,
            "bucket": price_bucket(entry),
            "res_up": res,
            "pnl_hold": pnl_hold * 100,    # in cents
            "pnl_sell": pnl_sell * 100,
        }
        for give in GIVE_VALS:
            rec[f"pnl_chase_{give:.2f}"] = pnl_chase[give] * 100

        records.append(rec)

df = pd.DataFrame(records)
print(f"\nTotal strand events: {len(df)}  YES={( df.side=='YES').sum()}  NO={(df.side=='NO').sum()}")

# ──────────────────────────────────────────────────────────────────────────
# Section A: Strand frequency
# ──────────────────────────────────────────────────────────────────────────
n_is  = len(is_ws)
n_oos = len(oos_ws)

for split, n_win in [("IS", n_is), ("OOS", n_oos)]:
    sub = df[df.split == split]
    yes = sub[sub.side == "YES"]
    no  = sub[sub.side == "NO"]
    total = len(sub)
    ws_with_strand = sub.ws.nunique()
    print(f"\n=== Section A — Strand Frequency [{split}] ===")
    print(f"  Windows: {n_win}  |  Windows with >=1 strand: {ws_with_strand} ({100*ws_with_strand/n_win:.1f}%)")
    print(f"  Total strands: {total}  ({total/n_win:.3f}/window)")
    if total > 0:
        print(f"  YES-strands: {len(yes)} ({100*len(yes)/total:.1f}%)  "
              f"NO-strands: {len(no)} ({100*len(no)/total:.1f}%)")

# ──────────────────────────────────────────────────────────────────────────
# Section B: Per (side × bucket) table
# ──────────────────────────────────────────────────────────────────────────
CHASE_COLS = [f"pnl_chase_{g:.2f}" for g in GIVE_VALS]
CHASE_LABELS = [f"CHASE(g={g:.2f})" for g in GIVE_VALS]

def make_table(sub_df):
    rows = []
    for side in ["YES", "NO"]:
        for bkt in PRICE_LABELS:
            mask = (sub_df.side == side) & (sub_df.bucket == bkt)
            g = sub_df[mask]
            n_ = len(g)
            if n_ == 0:
                continue
            row = {
                "side": side, "bucket": bkt, "N": n_,
                "HOLD": f"{g.pnl_hold.mean():.2f}",
                "SELL": f"{g.pnl_sell.mean():.2f}",
            }
            for cc, cl in zip(CHASE_COLS, CHASE_LABELS):
                row[cl] = f"{g[cc].mean():.2f}"
            rows.append(row)
    return pd.DataFrame(rows)

print("\n=== Section B — IS: mean c/strand by (side × bucket) ===")
tbl_is = make_table(df[df.split == "IS"])
print(tbl_is.to_string(index=False))

print("\n=== Section B — OOS: mean c/strand by (side × bucket) ===")
tbl_oos = make_table(df[df.split == "OOS"])
print(tbl_oos.to_string(index=False))

# ──────────────────────────────────────────────────────────────────────────
# Section C: OOS winning policy per side×bucket
# ──────────────────────────────────────────────────────────────────────────
print("\n=== Section C — OOS Winning Policy per (side × bucket) ===")
print(f"{'side':>4} {'bucket':>10} {'N':>5}  {'adequate':>8}  {'HOLD':>7} {'SELL':>7} "
      + "  ".join(f"{cl:>14}" for cl in CHASE_LABELS)
      + "  WINNER")

oos_df = df[df.split == "OOS"]
for side in ["YES", "NO"]:
    for bkt in PRICE_LABELS:
        mask = (oos_df.side == side) & (oos_df.bucket == bkt)
        g = oos_df[mask]
        n_ = len(g)
        if n_ == 0:
            continue
        adeq = "OK(N>=20)" if n_ >= 20 else "CAVEAT(N<20)"

        vals = {
            "HOLD": g.pnl_hold.mean(),
            "SELL": g.pnl_sell.mean(),
        }
        for cc, cl in zip(CHASE_COLS, CHASE_LABELS):
            vals[cl] = g[cc].mean()

        winner = max(vals, key=vals.get)
        win_val = vals[winner]

        hold_str = f"{vals['HOLD']:>7.2f}"
        sell_str = f"{vals['SELL']:>7.2f}"
        chase_str = "  ".join(f"{vals[cl]:>14.2f}" for cl in CHASE_LABELS)

        print(f"{side:>4} {bkt:>10} {n_:>5}  {adeq:>9}  {hold_str} {sell_str}  {chase_str}  {winner}")

# ──────────────────────────────────────────────────────────────────────────
# Section D: VERDICT
# ──────────────────────────────────────────────────────────────────────────
print("\n=== Section D — VERDICT ===")

# Summarize OOS HOLD vs best policy overall by side
for side in ["YES", "NO"]:
    g = oos_df[oos_df.side == side]
    n_ = len(g)
    if n_ == 0:
        continue
    hold_mean = g.pnl_hold.mean()
    sell_mean = g.pnl_sell.mean()
    chase_means = {cl: g[cc].mean() for cc, cl in zip(CHASE_COLS, CHASE_LABELS)}

    best_cl = max(chase_means, key=chase_means.get)
    best_chase_val = chase_means[best_cl]

    overall_best = max({"HOLD": hold_mean, "SELL": sell_mean, **chase_means}, key=lambda k: {"HOLD": hold_mean, "SELL": sell_mean, **chase_means}[k])
    overall_val  = {"HOLD": hold_mean, "SELL": sell_mean, **chase_means}[overall_best]

    delta_vs_hold = overall_val - hold_mean
    strands_per_win = n_ / n_oos
    strands_per_day = strands_per_win * 96
    edge_per_day = delta_vs_hold * strands_per_day

    print(f"\n{side}-strands (OOS N={n_}):")
    print(f"  HOLD mean:       {hold_mean:+.2f} c/strand")
    print(f"  SELL mean:       {sell_mean:+.2f} c/strand  ({'WORSE' if sell_mean < hold_mean else 'BETTER'} than HOLD)")
    print(f"  Best CHASE:      {best_cl} = {best_chase_val:+.2f} c/strand")
    print(f"  Overall winner:  {overall_best} = {overall_val:+.2f} c/strand")
    print(f"  Delta vs HOLD:   {delta_vs_hold:+.2f} c/strand")
    print(f"  Strands/window:  {strands_per_win:.3f}  => {strands_per_day:.1f}/day")
    print(f"  Est. edge gain:  {edge_per_day:+.1f} c/day")

# SELL-NOW vs invariant
sell_oos = oos_df.pnl_sell.mean()
hold_oos = oos_df.pnl_hold.mean()
print(f"\n--- SELL-NOW vs 'exits lose' invariant ---")
print(f"  OOS HOLD mean (all strands): {hold_oos:+.2f} c/strand")
print(f"  OOS SELL mean (all strands): {sell_oos:+.2f} c/strand")
if sell_oos < hold_oos:
    print("  CONFIRMS 'exits lose': SELL-NOW underperforms HOLD.")
else:
    print("  CONTRADICTS 'exits lose': SELL-NOW outperforms HOLD.")

# ──────────────────────────────────────────────────────────────────────────
# Section E: How to register t37 in box_policy_ab.py
# ──────────────────────────────────────────────────────────────────────────
print("""
=== Section E — How to register t37 in box_policy_ab.py ===

1. Add a new function pol_orphan_playbook() before the TRIALS dict, implementing the
   winning CHASE policy (e.g., give=0.02) for orphaned strands:
   - YES-strand: post ask at a' = max(a0, b0 - give); complete if taker BUY hits a'
   - NO-strand : post bid at b' = a0 + give; complete if taker SELL hits b'

2. In the TRIALS dict (after t36_guarded_opener), add:
   "t37_orphan_playbook": lambda F: pol_orphan_playbook(F, give=<winning_give>)

   Where pol_orphan_playbook(fills, give) walks each fill:
   - For a STRANDED leg (the pairing fill does NOT arrive in the same minute slot),
     check the remaining slots in the window for a taker that crosses a' / b'
   - If found: lock the completion pnl; else: hold to settlement
   This is analogous to run_policy() but acts post-strand rather than at open.

3. The function needs access to the full window's trade tape — the current run_policy()
   framework passes pre-identified fills, not the raw tape. Two options:
   (a) Add a tape= kwarg to pol_orphan_playbook that receives the tape arrays, OR
   (b) Encode the CHASE outcome as a precomputed field in window_fills() and use a
       hold_ok=lambda that reads it (simplest: add a 'chase_{give}' key to each fill).
   Option (b) is preferred — window_fills() already precomputes exit_bid/exit_ask;
   extend it to also compute chase_pnl_{give} for give in {0.00, 0.01, 0.02, 0.03}.

4. Registration line (exact addition, after the t36 line in TRIALS):
    "t37_orphan_playbook": lambda F: pol_orphan_playbook(F, give=<WINNING_GIVE>),

Forward scoring begins automatically on the next collector run once this line is added.
""")

print("\n=== DONE ===")
print("Script path: /tmp/code/orphan_playbook_study.py")
