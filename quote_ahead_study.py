"""
quote_ahead_study.py — QUOTE-AHEAD-OF-THE-LADDER play analysis

DATA: overnight_data/book_kalshi_btc15m_*.jsonl.gz (full-depth book, 21,438 snaps, ~1.2s cadence)
      overnight_data/trades_kalshi_btc15m_*.jsonl.gz (taker flow)
      trades_kalshi_btc15m.parquet (settlement per window)

TASKS:
1. Spot-jump event detection + MM ladder re-center lag distribution
2. Taker flow direction after jump (old touch vs new fair)
3. P(front) at new fair level 1 snap after jump
4. Edge estimate (fill prob, c/fill, events/day)
5. Adverse-selection direction check (jump continuation vs mean-reversion)
"""
from __future__ import annotations
import gzip, json, os, sys
import numpy as np
import pandas as pd
from collections import defaultdict

# ─── Configuration ───────────────────────────────────────────────────────────
OVERNIGHT = "/home/user/Codex-playground-/overnight_data/"
PARQUET_TRADES = "/home/user/Codex-playground-/trades_kalshi_btc15m.parquet"

# Ladder fingerprint: modal lot size for the mechanical MM
LADDER_LOT_YES = 265
LADDER_LOT_NO  = 250
LOT_TOL = 5  # ±5 contracts counts as a ladder level

# Jump detection: 3-snapshot rolling spot change >= threshold
SPOT_WINDOW_S = 3.0       # seconds for the rolling window
SPOT_JUMP_THRESHOLDS = [30, 50, 75, 100, 150]  # BTC USD — try several, pick one with ~few hundred events

# Post-jump analysis windows
LAG_CHECK_SNAPS = 10      # check MM re-center within 10 snaps (~12s)
FLOW_WINDOW_S   = 30.0    # look at taker flow up to 30s after jump

# ─── 1. Load all BTC book snapshots ──────────────────────────────────────────
print("Loading BTC book data...", flush=True)

btc_files = sorted([
    os.path.join(OVERNIGHT, f)
    for f in os.listdir(OVERNIGHT)
    if f.startswith("book_kalshi_btc15m") and f.endswith(".jsonl.gz")
])

all_snaps = []  # list of dicts
for fpath in btc_files:
    try:
        with gzip.open(fpath, "rt") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    if d.get("type") == "book" and d.get("asset") == "btc":
                        all_snaps.append(d)
                except Exception:
                    pass
    except EOFError:
        pass

all_snaps.sort(key=lambda d: d["t"])
print(f"  {len(all_snaps)} book snapshots loaded", flush=True)

# ─── 2. Load taker trades ─────────────────────────────────────────────────────
print("Loading BTC trades...", flush=True)
trade_files = sorted([
    os.path.join(OVERNIGHT, f)
    for f in os.listdir(OVERNIGHT)
    if f.startswith("trades_kalshi_btc15m") and f.endswith(".jsonl.gz")
])
all_trades = []
for fpath in trade_files:
    try:
        with gzip.open(fpath, "rt") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    all_trades.append(d)
                except Exception:
                    pass
    except EOFError:
        pass
all_trades.sort(key=lambda d: d["t"])
print(f"  {len(all_trades)} trades loaded", flush=True)

# ─── 3. Load settlement ───────────────────────────────────────────────────────
settle_df = pd.read_parquet(PARQUET_TRADES)
settle_map = dict(zip(settle_df["ws"], settle_df["res_up"]))
print(f"  {len(settle_map)} windows with settlement data", flush=True)

# ─── Helper: infer YES/NO touch from full depth array ─────────────────────────
def get_touch(depth_arr):
    """depth_arr is [[price, size], ...] sorted low-to-high.
    YES bids = highest price with size > 0 at the buy side.
    But the data gives YES bids from low to high (price=distance from 0).
    Actually the YES array is indexed from 0.001 upward.
    The YES BID touch = the HIGHEST price level with non-trivial size (closest to 1.0).
    The NO BID touch = same convention but from the 1-x perspective.

    For YES side: prices run 0.001 ... 0.99; the touch (best bid) = max price with size > 0.
    For NO side: same. The Kalshi book shows YES and NO bids separately.
    YES ask = 1 - best NO bid.
    """
    if not depth_arr:
        return None
    # Find the max price level with meaningful size
    best_p = None
    best_sz = None
    for p, sz in reversed(depth_arr):
        if sz > 0:
            best_p = p
            best_sz = sz
            break
    return best_p, best_sz


def get_yes_bid_touch(snap):
    """YES bid: highest-priced YES entry with size > 0."""
    yes = snap.get("yes", [])
    if not yes:
        return None, None
    for p, sz in reversed(yes):
        if sz > 0:
            return round(p, 4), sz
    return None, None


def get_no_bid_touch(snap):
    """NO bid: highest-priced NO entry with size > 0."""
    no = snap.get("no", [])
    if not no:
        return None, None
    for p, sz in reversed(no):
        if sz > 0:
            return round(p, 4), sz
    return None, None


def get_mid(snap):
    yb, _ = get_yes_bid_touch(snap)
    nb, _ = get_no_bid_touch(snap)
    if yb is None or nb is None:
        return None
    yes_ask = round(1.0 - nb, 4)
    yes_bid = yb
    return (yes_bid + yes_ask) / 2.0


def get_fair(snap):
    """Microprice-ish fair from top of book."""
    return get_mid(snap)


# ─── Helper: identify ladder levels (265/250 lot signature) ──────────────────
def count_ladder_levels(depth_arr, modal_lot, tol=LOT_TOL):
    """Count how many levels are the modal ladder lot size."""
    return sum(1 for p, sz in depth_arr if abs(sz - modal_lot) <= tol)


def get_ladder_yes_touch(snap):
    """The YES-bid touch that is a LADDER level (265-lot), searching from highest down."""
    yes = snap.get("yes", [])
    for p, sz in reversed(yes):
        if abs(sz - LADDER_LOT_YES) <= LOT_TOL:
            return round(p, 4)
    return None


def get_ladder_no_touch(snap):
    """The NO-bid touch that is a ladder level (250-lot), searching from highest down."""
    no = snap.get("no", [])
    for p, sz in reversed(no):
        if abs(sz - LADDER_LOT_NO) <= LOT_TOL:
            return round(p, 4)
    return None


# ─── 4. Detect spot-jump events ───────────────────────────────────────────────
print("\n=== TASK 1: Spot-jump event detection ===", flush=True)

spots_arr = np.array([s["spot"] for s in all_snaps])
times_arr = np.array([s["t"] for s in all_snaps])
N = len(all_snaps)

# For each snapshot i, find the earliest previous snapshot j with t[j] >= t[i] - SPOT_WINDOW_S
# 3s rolling change in spot
def find_prev_idx(i, window_s=SPOT_WINDOW_S):
    """Find first snap index j within [t[i]-window_s, t[i]] (earliest in window)."""
    t0 = times_arr[i] - window_s
    # binary search
    lo, hi = 0, i
    while lo < hi:
        mid = (lo + hi) // 2
        if times_arr[mid] < t0:
            lo = mid + 1
        else:
            hi = mid
    return lo

spot_moves = np.zeros(N)
for i in range(1, N):
    j = find_prev_idx(i)
    if j < i:
        spot_moves[i] = spots_arr[i] - spots_arr[j]
    # else: not enough history

abs_moves = np.abs(spot_moves)

# Show distribution
print(f"\nSpot 3s move distribution (absolute):")
for pct in [50, 75, 90, 95, 99]:
    print(f"  p{pct}: ${np.percentile(abs_moves, pct):.1f}")

for thresh in SPOT_JUMP_THRESHOLDS:
    n_events = np.sum(abs_moves >= thresh)
    print(f"  Threshold ${thresh}: {n_events} events ({n_events / (N * 1.2 / 86400):.0f}/day)")

# Pick threshold that gives ~200-500 events
# From distribution, select best threshold
n_by_thresh = {t: int(np.sum(abs_moves >= t)) for t in SPOT_JUMP_THRESHOLDS}
CHOSEN_THRESH = 50  # Will be adjusted after seeing distribution
print(f"\nChoosing threshold: ${CHOSEN_THRESH} (n={n_by_thresh.get(CHOSEN_THRESH, 0)} raw)")

# ─── 5. Build event list (filter: no event within 30s of previous) ────────────
print("\nBuilding de-duplicated event list...", flush=True)

MIN_EVENT_GAP_S = 30.0  # minimum gap between jump events

event_indices = []
last_event_t = -999
for i in range(1, N):
    if abs_moves[i] >= CHOSEN_THRESH:
        if times_arr[i] - last_event_t >= MIN_EVENT_GAP_S:
            event_indices.append(i)
            last_event_t = times_arr[i]

print(f"  Jump events (>=${CHOSEN_THRESH}, gap>={MIN_EVENT_GAP_S}s): {len(event_indices)}")

# Estimate events/day based on total time span
if len(all_snaps) > 2:
    total_hours = (times_arr[-1] - times_arr[0]) / 3600.0
    total_days_equiv = total_hours / 24.0
    events_per_day = len(event_indices) / max(total_days_equiv, 0.01)
    print(f"  Data span: {total_hours:.1f}h  Events/day est: {events_per_day:.0f}")
else:
    total_days_equiv = 0.5
    events_per_day = 0

# ─── 6. For each event: measure MM lag to re-center ──────────────────────────
print("\n=== TASK 1a: MM ladder re-center lag distribution ===", flush=True)

lag_snaps = []  # number of snaps until ladder touch moves
lag_null = 0    # ladder didn't re-center within LAG_CHECK_SNAPS

for ei in event_indices:
    snap0 = all_snaps[ei]
    move_dir = 1 if spot_moves[ei] > 0 else -1  # +1 = spot up

    # Ladder YES touch BEFORE the jump (snap at ei-1 or ei)
    ladder_yes_before = get_ladder_yes_touch(snap0)
    ladder_no_before  = get_ladder_no_touch(snap0)

    if ladder_yes_before is None and ladder_no_before is None:
        lag_null += 1
        continue

    # Look at subsequent snaps for a shift in the ladder touch
    shifted = False
    for k in range(1, LAG_CHECK_SNAPS + 1):
        if ei + k >= N:
            break
        snap_k = all_snaps[ei + k]

        ladder_yes_k = get_ladder_yes_touch(snap_k)
        ladder_no_k  = get_ladder_no_touch(snap_k)

        yes_moved = (ladder_yes_k is not None and ladder_yes_before is not None
                     and abs(ladder_yes_k - ladder_yes_before) >= 0.005)
        no_moved  = (ladder_no_k is not None and ladder_no_before is not None
                     and abs(ladder_no_k - ladder_no_before) >= 0.005)

        if yes_moved or no_moved:
            lag_snaps.append(k)
            shifted = True
            break

    if not shifted:
        lag_null += 1

lag_arr = np.array(lag_snaps)
total_events = len(event_indices)
pct_recenter = len(lag_snaps) / max(total_events, 1) * 100
pct_stale    = lag_null / max(total_events, 1) * 100

print(f"\nMM ladder re-center lag (within {LAG_CHECK_SNAPS} snaps = ~{LAG_CHECK_SNAPS*1.2:.0f}s):")
print(f"  Events with re-center detected: {len(lag_snaps)} / {total_events} ({pct_recenter:.0f}%)")
print(f"  Events where ladder STALE (no re-center in window): {lag_null} ({pct_stale:.0f}%)")
if len(lag_snaps) > 0:
    print(f"  Lag in snaps (1 snap ~ 1.2s):")
    for pct in [25, 50, 75, 90, 95]:
        snap_val = np.percentile(lag_arr, pct)
        print(f"    p{pct}: {snap_val:.1f} snaps (~{snap_val*1.2:.1f}s)")
    print(f"  Lag distribution: 1snap={np.sum(lag_arr==1)}, 2={np.sum(lag_arr==2)}, "
          f"3={np.sum(lag_arr==3)}, 4-5={np.sum((lag_arr>=4)&(lag_arr<=5))}, "
          f"6-10={np.sum(lag_arr>=6)}")

# ─── 7. Where does taker flow go after a jump? ───────────────────────────────
print("\n=== TASK 1b: Taker flow direction post-jump ===", flush=True)

# Build trades array for fast lookup
trades_t = np.array([tr["t"] for tr in all_trades])
trades_p = np.array([tr["p"] for tr in all_trades])
trades_side = np.array([tr["side"] for tr in all_trades])  # 'BUY' or 'SELL'

# For each jump event, classify taker flow in [+1s, +30s]:
# OLD touch: the YES bid or YES ask at snap ei
# NEW fair: approximate fair = mid at snap ei, adjusted by spot move direction
# Spot up -> fair goes UP -> YES prices should go up
# Flow "at old touch" = trade at old YES bid price or old YES ask price
# Flow "at new fair" = trade at the expected new level

flow_stats = {"old_level": 0, "new_level": 0, "neither": 0}

old_touch_YES_bids = []
old_touch_YES_asks = []
new_fair_targets = []
flow_details = []

for ei in event_indices:
    snap0 = all_snaps[ei]
    t0    = times_arr[ei]
    move_dir = 1 if spot_moves[ei] > 0 else -1

    yb0, _ = get_yes_bid_touch(snap0)
    nb0, _ = get_no_bid_touch(snap0)
    if yb0 is None or nb0 is None:
        continue

    ya0 = round(1.0 - nb0, 4)  # YES ask
    mid0 = (yb0 + ya0) / 2.0

    # Approximate new fair: the spot move as fraction of the 15m range
    # We can estimate directly from the book: look 1 snap later
    if ei + 1 < N:
        snap1 = all_snaps[ei + 1]
        mid1 = get_mid(snap1)
        if mid1 is None:
            mid1 = mid0
    else:
        mid1 = mid0

    # Old touch price (YES bid for a short buyer, YES ask for a short seller)
    old_level_price = yb0  # YES bid (the level where buyers push)
    new_fair_price  = mid1

    old_touch_YES_bids.append(old_level_price)
    new_fair_targets.append(new_fair_price)

    # Find trades in [t0+1s, t0+30s]
    mask = (trades_t >= t0 + 1.0) & (trades_t <= t0 + FLOW_WINDOW_S)
    event_trades = [all_trades[j] for j in np.where(mask)[0]]

    n_at_old = 0
    n_at_new = 0
    n_neither = 0
    for tr in event_trades:
        p = tr["p"]
        # "at old level" = within 0.005 of old touch
        if abs(p - old_level_price) <= 0.005:
            n_at_old += 1
        elif abs(p - new_fair_price) <= 0.01:
            n_at_new += 1
        else:
            n_neither += 1

    flow_stats["old_level"] += n_at_old
    flow_stats["new_level"] += n_at_new
    flow_stats["neither"]   += n_neither
    flow_details.append({
        "ei": ei, "t0": t0, "dir": move_dir,
        "old_p": old_level_price, "new_fair": new_fair_price,
        "n_trades": len(event_trades),
        "n_at_old": n_at_old, "n_at_new": n_at_new
    })

total_flow = sum(flow_stats.values())
print(f"\nTaker flow in 1-30s after {len(flow_details)} jump events:")
if total_flow > 0:
    print(f"  At OLD touch level (±0.5c): {flow_stats['old_level']} ({100*flow_stats['old_level']/total_flow:.0f}%)")
    print(f"  At NEW fair level  (±1.0c): {flow_stats['new_level']} ({100*flow_stats['new_level']/total_flow:.0f}%)")
    print(f"  Neither            :         {flow_stats['neither']} ({100*flow_stats['neither']/total_flow:.0f}%)")

# ─── 8. P(front) at new fair touch 1 snap after jump ─────────────────────────
print("\n=== TASK 2: P(front) at new fair level, 1 snap post-jump ===", flush=True)

front_count    = 0
behind_count   = 0
no_level_count = 0
size_ahead_list = []

for ei in event_indices:
    if ei + 1 >= N:
        no_level_count += 1
        continue

    snap0 = all_snaps[ei]
    snap1 = all_snaps[ei + 1]

    # Determine the "new fair" touch we would quote
    # Spot up: YES becomes more likely; we quote YES bid at the new touch
    # Spot down: NO becomes more likely; we quote NO bid at the new touch
    move_dir = 1 if spot_moves[ei] > 0 else -1

    yb0, _ = get_yes_bid_touch(snap0)
    nb0, _ = get_no_bid_touch(snap0)

    if yb0 is None or nb0 is None:
        no_level_count += 1
        continue

    ya0 = round(1.0 - nb0, 4)
    mid0 = (yb0 + ya0) / 2.0

    yb1, _ = get_yes_bid_touch(snap1)
    nb1, _ = get_no_bid_touch(snap1)
    if yb1 is None or nb1 is None:
        no_level_count += 1
        continue

    ya1 = round(1.0 - nb1, 4)
    mid1 = (yb1 + ya1) / 2.0

    # The new fair touch: where we would post 1 snap after the jump
    # If spot goes up: YES bid moves up; we quote YES bid at the NEW higher level (mid1+spread/2)
    # The actual level to quote: the new YES bid touch = yb1
    target_price = yb1 if move_dir > 0 else nb1
    target_side  = "yes" if move_dir > 0 else "no"

    # In snap1, is this level EMPTY (i.e., we would be first)?
    depth1 = snap1.get(target_side, [])
    # Find the size at the target price in snap1
    level_size_at_target = 0.0
    for p, sz in depth1:
        if abs(p - target_price) < 0.0005:
            level_size_at_target = sz
            break

    # Check if it was non-existent in snap0 (newly emerged level)
    depth0 = snap0.get(target_side, [])
    level_size_at_target_snap0 = 0.0
    for p, sz in depth0:
        if abs(p - target_price) < 0.0005:
            level_size_at_target_snap0 = sz
            break

    # P(front): the level is empty in snap1 (we would be first to post there)
    # OR the target price in snap1 has only ladder-lot size (MM just re-posted; we can't be first)
    # For simplicity: front = level_size_at_target_snap0 == 0 (was empty at jump time)
    # i.e., the move created a new price level not previously quoted

    if level_size_at_target_snap0 == 0:
        # Level was empty at jump time; if we post immediately at snap+1, we're first
        front_count += 1
        size_ahead_list.append(0.0)
    elif level_size_at_target == 0:
        # Also front — level cleared in the snap1
        front_count += 1
        size_ahead_list.append(0.0)
    else:
        behind_count += 1
        size_ahead_list.append(level_size_at_target)

total_q = front_count + behind_count + no_level_count
p_front = front_count / max(front_count + behind_count, 1)
size_ahead_arr = np.array(size_ahead_list)

print(f"\nAt new fair touch (1 snap = ~1.2s after jump), out of {len(event_indices)} events:")
print(f"  P(front / level empty at jump) = {p_front:.3f}  ({front_count}/{front_count+behind_count})")
print(f"  No level detected: {no_level_count}")
if len(size_ahead_arr[size_ahead_arr > 0]) > 0:
    behind_sizes = size_ahead_arr[size_ahead_arr > 0]
    print(f"  When NOT front, size ahead: median={np.median(behind_sizes):.0f} "
          f"p25={np.percentile(behind_sizes,25):.0f} p75={np.percentile(behind_sizes,75):.0f}")

# More nuanced: check if the NEW fair bid is strictly higher than old fair bid
# (spot went up -> YES bid touch moves up -> new price didn't exist before)
print("\n  Detailed front-of-queue breakdown by whether new level = newly created vs existing:")
new_level_events = 0
existing_level_events = 0
for ei in event_indices:
    if ei + 1 >= N:
        continue
    snap0 = all_snaps[ei]
    snap1 = all_snaps[ei + 1]
    move_dir = 1 if spot_moves[ei] > 0 else -1

    yb0, _ = get_yes_bid_touch(snap0)
    yb1, _ = get_yes_bid_touch(snap1)
    nb0, _ = get_no_bid_touch(snap0)
    nb1, _ = get_no_bid_touch(snap1)
    if None in (yb0, yb1, nb0, nb1):
        continue

    if move_dir > 0:
        if yb1 > yb0 + 0.005:  # YES touch moved up -> new level
            new_level_events += 1
        else:
            existing_level_events += 1
    else:
        if nb1 > nb0 + 0.005:  # NO touch moved up -> new level
            new_level_events += 1
        else:
            existing_level_events += 1

print(f"    Jump caused touch to move to new price: {new_level_events} ({100*new_level_events/max(new_level_events+existing_level_events,1):.0f}%)")
print(f"    Touch stayed at same price level:       {existing_level_events} ({100*existing_level_events/max(new_level_events+existing_level_events,1):.0f}%)")

# ─── 9. Edge estimate ─────────────────────────────────────────────────────────
print("\n=== TASK 3: Edge estimate (fill prob + c/fill) ===", flush=True)

# For events where we would be front-of-queue at the new fair touch,
# did taker flow cross that level in the following 30-120s?

fill_markouts = []
fill_events = 0
no_fill_events = 0
FILL_WINDOW_LO = 1.0
FILL_WINDOW_HI = 120.0

for ei in event_indices:
    if ei + 1 >= N:
        continue
    snap0 = all_snaps[ei]
    snap1 = all_snaps[ei + 1]
    move_dir = 1 if spot_moves[ei] > 0 else -1

    yb0, _ = get_yes_bid_touch(snap0)
    nb0, _ = get_no_bid_touch(snap0)
    yb1, _ = get_yes_bid_touch(snap1)
    nb1, _ = get_no_bid_touch(snap1)
    if None in (yb0, yb1, nb0, nb1):
        continue

    # Was this a "new level" event (front-of-queue achievable)?
    target_price = yb1 if move_dir > 0 else nb1
    snap0_ref    = yb0  if move_dir > 0 else nb0
    was_new_level = target_price > snap0_ref + 0.004  # touch moved up

    if not was_new_level:
        continue

    # Does taker flow cross our level in [t+1s, t+120s]?
    t0 = times_arr[ei]
    mask = (trades_t >= t0 + FILL_WINDOW_LO) & (trades_t <= t0 + FILL_WINDOW_HI)
    event_trades_post = [all_trades[j] for j in np.where(mask)[0]]

    # A YES bid maker fills when a taker BUYs YES at >= our YES bid price
    # A NO  bid maker fills when a taker BUYs NO  at >= our NO  bid price
    # But in the taker tape, 'p' is the YES price, 'side' = BUY means taker bought YES
    # YES bid maker: filled by taker BUY YES at >= yb1
    # NO bid maker:  equivalent to taker SELL YES at <= 1-nb1 (YES ask)

    got_fill = False
    fill_price = None
    if move_dir > 0:
        # We posted YES bid at yb1; filled by taker BUY YES at price >= yb1
        for tr in event_trades_post:
            if tr["side"] == "BUY" and tr["p"] >= target_price - 0.0005:
                got_fill = True
                fill_price = tr["p"]
                break
    else:
        # We posted NO bid at nb1; equivalent: taker SELL YES at price <= 1-nb1
        yes_ask_equiv = round(1.0 - nb1, 4)
        for tr in event_trades_post:
            if tr["side"] == "SELL" and tr["p"] <= yes_ask_equiv + 0.0005:
                got_fill = True
                fill_price = tr["p"]
                break

    if got_fill:
        # Find settlement for this window
        ws = all_snaps[ei]["ws"]
        if ws in settle_map:
            res_up = settle_map[ws]
            if move_dir > 0:
                markout = res_up - target_price  # YES bid maker: settle-bid
            else:
                markout = target_price - res_up  # NO bid maker: settle-bid (NO side)
            fill_markouts.append(markout * 100)  # convert to cents
        fill_events += 1
    else:
        no_fill_events += 1

fill_prob = fill_events / max(fill_events + no_fill_events, 1)
fill_markouts_arr = np.array(fill_markouts)

print(f"\nEdge estimate (new-level front-of-queue events, settle window):")
print(f"  New-level events analyzed: {fill_events + no_fill_events}")
print(f"  Got fill (taker crossed level in 1-120s): {fill_events} -> P(fill) = {fill_prob:.3f}")
if len(fill_markouts_arr) > 0:
    print(f"  Mean markout c/fill: {np.mean(fill_markouts_arr):.2f}c")
    print(f"  Median markout:      {np.median(fill_markouts_arr):.2f}c")
    print(f"  P(positive markout): {np.mean(fill_markouts_arr > 0):.3f}")
    print(f"  std: {np.std(fill_markouts_arr):.2f}c")

# Compare to "normal" fills from settlement df
settle_yes_bid_mo = []
for _, row in settle_df.iterrows():
    if "mid_avg" in settle_df.columns:
        pass  # use whatever is available
settle_df_cols = list(settle_df.columns)
print(f"\n  Reference: settlement df columns: {settle_df_cols[:10]}")

# Events/day estimate
new_level_per_day = (fill_events + no_fill_events) / max(total_days_equiv, 0.01)
implied_fills_per_day = fill_prob * new_level_per_day
implied_cedge_per_day = (np.mean(fill_markouts_arr) if len(fill_markouts_arr) > 0 else 0) * implied_fills_per_day
print(f"\n  New-level events/day: {new_level_per_day:.0f}")
print(f"  Fills/day (at P(fill)={fill_prob:.2f}): {implied_fills_per_day:.0f}")
if len(fill_markouts_arr) > 0:
    print(f"  Implied c/day: {implied_cedge_per_day:.1f}c/day")
    print(f"  Implied $/day: ${implied_cedge_per_day/100:.2f}/day")

# ─── 10. Adverse-selection check ─────────────────────────────────────────────
print("\n=== TASK 4: Adverse-selection — jump continuation vs mean-reversion ===", flush=True)

# For each jump event, measure subsequent spot change at +10s, +30s, +60s, +120s
lookforward = [10, 30, 60, 120]

adv_sel_data = []
for ei in event_indices:
    t0 = times_arr[ei]
    spot0 = spots_arr[ei]
    move = spot_moves[ei]
    move_dir = 1 if move > 0 else -1

    fwd = {}
    for lf in lookforward:
        # find snap closest to t0 + lf
        target_t = t0 + lf
        idx = np.searchsorted(times_arr, target_t)
        idx = min(idx, N - 1)
        fwd[f"spot_fwd_{lf}s"] = spots_arr[idx] - spot0
        fwd[f"signed_fwd_{lf}s"] = (spots_arr[idx] - spot0) * move_dir

    adv_sel_data.append({
        "ei": ei, "t0": t0, "move": move, "move_dir": move_dir,
        "abs_move": abs(move), **fwd
    })

adf = pd.DataFrame(adv_sel_data)

print(f"\nPost-jump signed spot change (move direction = +1, so +ve = CONTINUATION, -ve = REVERSAL):")
print(f"  N = {len(adf)}")
for lf in lookforward:
    col = f"signed_fwd_{lf}s"
    if col in adf.columns:
        mean_c = adf[col].mean()
        med_c  = adf[col].median()
        pct_cont = (adf[col] > 0).mean() * 100
        print(f"  +{lf:3d}s: mean={mean_c:+.1f} median={med_c:+.1f} P(continuation)={pct_cont:.0f}%")

# Split by jump size quartile
adf["jump_quartile"] = pd.qcut(adf["abs_move"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
print(f"\n  By jump magnitude quartile (signed +30s fwd):")
print(f"  {'Quartile':<10} {'N':<6} {'mean_move':<12} {'P(cont)'}")
for q in ["Q1", "Q2", "Q3", "Q4"]:
    sub = adf[adf["jump_quartile"] == q]
    if len(sub) > 0:
        m = sub["abs_move"].mean()
        s = sub["signed_fwd_30s"].mean() if "signed_fwd_30s" in sub.columns else 0
        pc = (sub["signed_fwd_30s"] > 0).mean() * 100 if "signed_fwd_30s" in sub.columns else 0
        print(f"  {q:<10} {len(sub):<6} {m:>8.1f}$  {s:+.1f}$  {pc:.0f}%")

# The t36 guard: skip threatened side at >8bps (0.08 in probability)
# 8bps in spot: 8/10000 * current spot price
# At BTC $60k: 8bps = $48
adf["spot_8bp"] = adf["abs_move"] / spots_arr[adf["ei"]].mean() * 10000  # in bps
print(f"\n  Jump sizes in basis points (relative to spot):")
for pct in [25, 50, 75, 90]:
    print(f"    p{pct}: {np.percentile(adf['spot_8bp'], pct):.2f} bps")
t36_mask = adf["abs_move"] / spots_arr[adf["ei"]].mean() > 0.0008  # >8bps
print(f"  Events > 8bps (t36 threshold): {t36_mask.sum()} ({100*t36_mask.mean():.0f}%)")
print(f"  Events <= 8bps: {(~t36_mask).sum()} ({100*(~t36_mask).mean():.0f}%)")

# Mean-reversion at 30s, split by above/below 8bps
for label, mask in [("<=8bps (safe side)", ~t36_mask), (">8bps (t36 zone)", t36_mask)]:
    sub = adf[mask]
    if len(sub) > 0:
        s30 = sub["signed_fwd_30s"].mean() if "signed_fwd_30s" in sub.columns else 0
        pc30 = (sub["signed_fwd_30s"] > 0).mean() * 100 if "signed_fwd_30s" in sub.columns else 0
        print(f"  {label}: N={len(sub)}, +30s mean={s30:+.1f}$, P(cont)={pc30:.0f}%")

print("\n  Verdict on which SIDE to quote:")
print("  SAFE side = the side NOT threatened by spot jump.")
print("  Spot UP -> YES moves toward 1 -> NO bid (YES ask side) is NOT threatened -> quote NO bid.")
print("  Spot DOWN -> YES moves toward 0 -> YES bid is NOT threatened -> quote YES bid.")
print("  Both sides are safe when |move| < 8bps (t36 doesn't fire); above 8bps, quote only safe side.")

# ─── 11. Summary table ───────────────────────────────────────────────────────
print("\n" + "="*70)
print("SUMMARY TABLE")
print("="*70)

print(f"\n1. SPOT JUMP DEFINITION:")
print(f"   Threshold: ${CHOSEN_THRESH} over 3s rolling window")
print(f"   Raw events: {sum(abs_moves >= CHOSEN_THRESH)}")
print(f"   De-dup events (>={MIN_EVENT_GAP_S}s gap): {len(event_indices)}")
print(f"   Data span: {total_hours:.1f}h | Events/day: {events_per_day:.0f}")

print(f"\n2. MM LADDER RE-CENTER LAG:")
if len(lag_snaps) > 0:
    p50_lag = np.percentile(lag_arr, 50)
    p75_lag = np.percentile(lag_arr, 75)
    p90_lag = np.percentile(lag_arr, 90)
    print(f"   Re-centered within {LAG_CHECK_SNAPS} snaps: {len(lag_snaps)}/{total_events} ({pct_recenter:.0f}%)")
    print(f"   Lag distribution: p50={p50_lag:.0f} snaps (~{p50_lag*1.2:.1f}s) | p75={p75_lag:.0f} | p90={p90_lag:.0f}")
    print(f"   Still stale after {LAG_CHECK_SNAPS*1.2:.0f}s: {lag_null} events ({pct_stale:.0f}%)")
else:
    print("   No lag data")

print(f"\n3. TAKER FLOW DIRECTION:")
if total_flow > 0:
    print(f"   At OLD level: {100*flow_stats['old_level']/total_flow:.0f}% | At NEW fair: {100*flow_stats['new_level']/total_flow:.0f}% | Other: {100*flow_stats['neither']/total_flow:.0f}%")

print(f"\n4. P(FRONT-OF-QUEUE) AT NEW LEVEL:")
print(f"   P(front) = {p_front:.3f}  (level empty at jump time)")
print(f"   Touch moved to new price in {new_level_events}/{new_level_events+existing_level_events} events ({100*new_level_events/max(new_level_events+existing_level_events,1):.0f}%)")

print(f"\n5. EDGE ESTIMATE (new-level events only):")
print(f"   P(fill in 1-120s) = {fill_prob:.3f}")
if len(fill_markouts_arr) > 0:
    print(f"   Mean c/fill = {np.mean(fill_markouts_arr):.2f}c | Median = {np.median(fill_markouts_arr):.2f}c")
    print(f"   P(positive) = {np.mean(fill_markouts_arr > 0):.2f}")
    print(f"   Events/day estimate: {new_level_per_day:.0f} | Fills/day: {implied_fills_per_day:.0f}")
    print(f"   Implied c/day: {implied_cedge_per_day:.1f}c | $/day: ${implied_cedge_per_day/100:.2f}")
else:
    print("   Insufficient fill data with settlement")

print(f"\n6. ADVERSE SELECTION:")
if len(adf) > 0 and "signed_fwd_30s" in adf.columns:
    overall_mr = adf["signed_fwd_30s"].mean()
    pct_mr = (adf["signed_fwd_30s"] <= 0).mean() * 100
    print(f"   +30s mean signed move: {overall_mr:+.1f}$ (neg = mean-reversion)")
    print(f"   P(mean-reversion at +30s): {pct_mr:.0f}%")
    if not t36_mask.empty:
        sub_safe = adf[~t36_mask]
        if len(sub_safe) > 0:
            mr_safe = sub_safe["signed_fwd_30s"].mean()
            print(f"   Safe side (<8bps): +30s mean={mr_safe:+.1f}$")
        sub_t36 = adf[t36_mask]
        if len(sub_t36) > 0:
            mr_t36 = sub_t36["signed_fwd_30s"].mean()
            print(f"   t36 zone (>8bps): +30s mean={mr_t36:+.1f}$ (momentum signal)")

print("\n" + "="*70)
print("DONE")
