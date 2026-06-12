"""
Q1: What is front-of-queue worth?
Analyzes book snapshot data to measure fill-quality selection effects
for front-of-queue vs back-of-queue positions.
"""

import gzip
import json
import glob
import sys
import math
from collections import defaultdict

import pandas as pd
import numpy as np

# ─── CONFIG ────────────────────────────────────────────────────────────────
BOOK_GLOB = "/home/user/Codex-playground-/overnight_data/book_kalshi_btc15m*.jsonl.gz"
TRADES_PARQUET = "/home/user/Codex-playground-/trades_kalshi_btc15m.parquet"
MAX_FILES = 40
MIN_TAKE_SIZE = 0.5   # minimum drop to count as a take (in $)
MIN_LEVEL_DEPTH = 1.0  # minimum level depth to consider

# ─── LOAD SETTLEMENT MAP ───────────────────────────────────────────────────
def load_settlement_map():
    """Return {ws: res_up} from parquet (one outcome per window)."""
    df = pd.read_parquet(TRADES_PARQUET, columns=["ws", "res_up"])
    df = df.drop_duplicates("ws")
    return dict(zip(df["ws"].astype(int), df["res_up"].astype(int)))

# ─── BOOK FILE PROCESSING ──────────────────────────────────────────────────
def get_best_bid_ask(book_row):
    """
    yes array: [price, qty] pairs, ascending by price, so best bid = last element.
    no array: [price, qty] pairs, ascending by price, so best ask (in YES equiv) = 1 - no_best_bid.
    Actually: NO side bids: best NO bid = last element of no array.
    YES best bid = highest yes price = yes[-1][0]
    NO best bid  = highest no price  = no[-1][0]
    YES equiv ask = 1 - best NO bid
    """
    yes = book_row.get("yes", [])
    no = book_row.get("no", [])

    yes_bid_price = yes[-1][0] if yes else None
    yes_bid_qty   = yes[-1][1] if yes else 0.0

    no_bid_price  = no[-1][0] if no else None
    # YES ask equivalent = 1 - best NO bid
    yes_ask_price = (1.0 - no_bid_price) if no_bid_price is not None else None
    no_bid_qty    = no[-1][1] if no else 0.0

    return yes_bid_price, yes_bid_qty, yes_ask_price, no_bid_qty


def process_book_file(filepath, settlement_map):
    """
    Replay book snapshots from one file. Find take events by detecting
    price-stable depth drops at the touch.

    Returns list of take event dicts.
    """
    events = []
    snapshots = []  # list of (t, ws, yes_bid_p, yes_bid_q, yes_ask_p, no_bid_q)

    with gzip.open(filepath, "rt") as f:
        for line in f:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, EOFError):
                continue
            except Exception:
                continue
            if row.get("type") != "book":
                continue
            t   = row.get("t", 0)
            ws  = int(row.get("ws", 0))
            yb_p, yb_q, ya_p, na_q = get_best_bid_ask(row)
            if yb_p is None or ya_p is None:
                continue
            snapshots.append((t, ws, yb_p, yb_q, ya_p, na_q))

    # Replay: find consecutive pairs where price stays constant but qty drops
    for i in range(1, len(snapshots)):
        t0, ws0, yb_p0, yb_q0, ya_p0, na_q0 = snapshots[i - 1]
        t1, ws1, yb_p1, yb_q1, ya_p1, na_q1 = snapshots[i]

        # Skip if window changed
        if ws0 != ws1:
            continue

        res = settlement_map.get(ws0)
        if res is None:
            continue  # no settlement data

        # Check YES bid side: price stable, qty dropped
        if abs(yb_p0 - yb_p1) < 1e-5 and yb_q0 > yb_q1 + MIN_TAKE_SIZE:
            delta = yb_q0 - yb_q1
            depth = yb_q0
            if depth >= MIN_LEVEL_DEPTH:
                fill_price = yb_p0  # maker was posting YES bids
                # markout for YES maker: if YES wins (res_up=1) = 1-fill_price, else -fill_price
                markout = (1.0 - fill_price) if res == 1 else (-fill_price)
                frac = delta / depth
                events.append({
                    "ws": ws0,
                    "t": t1,
                    "side": "YES_bid",
                    "fill_price": fill_price,
                    "take_size": delta,
                    "level_depth": depth,
                    "take_frac": frac,
                    "markout": markout,
                    "res_up": res,
                })

        # Check NO bid side: price stable, qty dropped
        if abs(ya_p0 - ya_p1) < 1e-5 and na_q0 > na_q1 + MIN_TAKE_SIZE:
            delta = na_q0 - na_q1
            depth = na_q0
            if depth >= MIN_LEVEL_DEPTH:
                fill_price = ya_p0  # YES-equiv ask price
                # markout for NO maker: if YES loses (res_up=0) = 1-(1-fill_price) - ...
                # NO maker profits when YES loses: payoff = (1-0) - no_bid = 1 - no_bid
                # no_bid = 1 - yes_ask, so payoff = yes_ask - 0 = fill_price
                # More cleanly: NO maker fills at NO price = 1-fill_price
                no_fill_price = 1.0 - fill_price
                markout = (1.0 - no_fill_price) if res == 0 else (-no_fill_price)
                frac = delta / depth
                events.append({
                    "ws": ws0,
                    "t": t1,
                    "side": "NO_bid",
                    "fill_price": fill_price,
                    "take_size": delta,
                    "level_depth": depth,
                    "take_frac": frac,
                    "markout": markout,
                    "res_up": res,
                })

    return events


# ─── MAIN ──────────────────────────────────────────────────────────────────
def main():
    # Load settlement map
    settlement_map = load_settlement_map()
    total_windows = len(settlement_map)

    # Sample book files
    all_files = sorted(glob.glob(BOOK_GLOB))
    if len(all_files) > MAX_FILES:
        stride = max(1, len(all_files) // MAX_FILES)
        files = all_files[::stride][:MAX_FILES]
    else:
        files = all_files

    print(f"Processing {len(files)}/{len(all_files)} book files, {total_windows} settlement windows")

    # Process all files
    all_events = []
    windows_seen = set()
    for fp in files:
        evs = process_book_file(fp, settlement_map)
        all_events.extend(evs)
        for e in evs:
            windows_seen.add(e["ws"])

    if not all_events:
        print("ERROR: No take events found. Check data paths.")
        sys.exit(1)

    df = pd.DataFrame(all_events)
    total_events = len(df)
    total_ws = len(windows_seen)

    # ─── TABLE 1: Take size category ───────────────────────────────────────
    # Classify by take_frac: small (< 1/3), medium (1/3–2/3), large (> 2/3)
    def take_cat(frac):
        if frac < 1/3:
            return "small (<1/3 depth)"
        elif frac < 2/3:
            return "medium (1/3–2/3)"
        else:
            return "large (>2/3 depth)"

    df["take_cat"] = df["take_frac"].apply(take_cat)

    cat_order = ["small (<1/3 depth)", "medium (1/3–2/3)", "large (>2/3 depth)"]
    print("\n" + "="*70)
    print("TABLE 1: Take size category vs markout (all sides combined)")
    print("="*70)
    print(f"{'Category':<22} {'N':>6} {'Mean take($)':>13} {'P(YES wins)':>12} {'Mean markout(¢)':>16}")
    print("-"*70)

    for cat in cat_order:
        sub = df[df["take_cat"] == cat]
        if len(sub) == 0:
            continue
        n = len(sub)
        mean_take = sub["take_size"].mean()
        p_yes_wins = sub["res_up"].mean()
        mean_mo = sub["markout"].mean() * 100  # convert to cents
        print(f"{cat:<22} {n:>6} {mean_take:>13.1f} {p_yes_wins:>12.3f} {mean_mo:>16.2f}¢")

    print("-"*70)
    # Overall
    print(f"{'TOTAL':<22} {total_events:>6} {df['take_size'].mean():>13.1f} {df['res_up'].mean():>12.3f} {df['markout'].mean()*100:>16.2f}¢")

    # ─── TABLE 2: Queue position tier ─────────────────────────────────────
    # Interpret: small take selects the front third of queue.
    # medium take selects front+middle third.
    # large take selects entire level.
    #
    # We simulate: for each take event, which positional tier was filled?
    # small_take → "front" tier filled
    # medium_take → "front" and "middle" tiers filled (but we can only attribute to the marginal)
    # large_take → "front", "middle", and "back" tiers filled
    #
    # Simpler: classify each event by the LAST tier filled (the marginal tier):
    #   small → front (marginal = front)
    #   medium → middle (marginal = middle)
    #   large → back (marginal = back)
    # The "front" tier is always filled in any take; selection is about ADVERSE selection.
    # Front-of-queue holders: their fill outcome is revealed by ALL takes.
    # Back-of-queue holders: their fill outcome revealed only by LARGE takes.
    #
    # Selection effect: if small takes are more informative (better for adverse selection
    # for maker), or if large sweeps happen on stronger signals.

    print("\n" + "="*70)
    print("TABLE 2: Queue tier markout (by marginal tier filled)")
    print("  front = small takes (<1/3); mid = medium; back = large (>2/3)")
    print("="*70)
    print(f"{'Tier':<12} {'N':>6} {'Mean markout(¢)':>16} {'P(profitable)':>14} {'Mean take_frac':>15}")
    print("-"*70)

    tier_map = {
        "small (<1/3 depth)": "FRONT tier",
        "medium (1/3–2/3)":   "MID tier",
        "large (>2/3 depth)": "BACK tier",
    }
    for cat, tier in tier_map.items():
        sub = df[df["take_cat"] == cat]
        if len(sub) == 0:
            continue
        n = len(sub)
        mean_mo = sub["markout"].mean() * 100
        p_prof = (sub["markout"] > 0).mean()
        mean_frac = sub["take_frac"].mean()
        print(f"{tier:<12} {n:>6} {mean_mo:>16.2f}¢ {p_prof:>14.3f} {mean_frac:>15.3f}")

    print("-"*70)

    # ─── TABLE 3: YES vs NO side breakdown ────────────────────────────────
    print("\n" + "="*70)
    print("TABLE 3: Side breakdown (YES_bid makers vs NO_bid makers)")
    print("="*70)
    print(f"{'Side':<12} {'N':>6} {'Mean markout(¢)':>16} {'P(profitable)':>14} {'small_frac':>11} {'large_frac':>11}")
    print("-"*70)

    for side in ["YES_bid", "NO_bid"]:
        sub = df[df["side"] == side]
        if len(sub) == 0:
            continue
        n = len(sub)
        mean_mo = sub["markout"].mean() * 100
        p_prof  = (sub["markout"] > 0).mean()
        small_f = (sub["take_cat"] == "small (<1/3 depth)").mean()
        large_f = (sub["take_cat"] == "large (>2/3 depth)").mean()
        print(f"{side:<12} {n:>6} {mean_mo:>16.2f}¢ {p_prof:>14.3f} {small_f:>11.3f} {large_f:>11.3f}")

    # ─── KEY SELECTION EFFECT ─────────────────────────────────────────────
    small_mo = df[df["take_cat"] == "small (<1/3 depth)"]["markout"].mean() * 100
    large_mo = df[df["take_cat"] == "large (>2/3 depth)"]["markout"].mean() * 100
    diff = large_mo - small_mo

    print("\n" + "="*70)
    print("KEY FINDING: Selection effect")
    print("="*70)
    print(f"  Front-of-queue (small takes): {small_mo:+.2f}¢ mean markout")
    print(f"  Back-of-queue  (large sweeps): {large_mo:+.2f}¢ mean markout")
    print(f"  Difference (large - small):    {diff:+.2f}¢")
    if diff < -0.5:
        print("  => Front-of-queue LESS adversely selected than large sweeps (better for maker)")
    elif diff > 0.5:
        print("  => Front-of-queue MORE adversely selected than large sweeps (worse for maker)")
    else:
        print("  => Minimal selection effect between queue tiers")

    # Adverse selection by take_frac (correlation)
    corr = df["take_frac"].corr(df["markout"])
    print(f"\n  Corr(take_frac, markout): {corr:.4f}")
    print(f"    (positive => larger takes have better markout for maker;")
    print(f"     negative => larger takes are worse for maker, i.e. adverse selection)")

    # ─── SUMMARY ──────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("SUMMARY STATS")
    print("="*70)
    print(f"  Files processed:           {len(files)}")
    print(f"  Total windows w/settlement:{total_windows}")
    print(f"  Windows with take events:  {total_ws}")
    print(f"  Total take events:         {total_events}")
    print(f"  YES_bid events:            {(df['side']=='YES_bid').sum()}")
    print(f"  NO_bid events:             {(df['side']=='NO_bid').sum()}")
    print(f"  Mean level depth at event: {df['level_depth'].mean():.1f}$")
    print(f"  Median take size:          {df['take_size'].median():.1f}$")
    print(f"  Median take_frac:          {df['take_frac'].median():.3f}")

    # Distribution of take categories
    cat_counts = df["take_cat"].value_counts()
    print("\n  Take category distribution:")
    for cat in cat_order:
        n = cat_counts.get(cat, 0)
        pct = 100 * n / total_events
        print(f"    {cat}: {n} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
