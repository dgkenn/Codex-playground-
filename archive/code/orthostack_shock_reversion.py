#!/usr/bin/env python3
"""orthostack_shock_reversion.py -- test the OVERREACTION-REVERSION hypothesis.

HYPOTHESIS: The book overreacts to a sharp mid-window spot move (a SHOCK) and reverts.
After detecting a shock, FADE it by taking the opposite side (bet the overshoot reverts).

Two scoring modes:
  (a) Hold to REALIZED settlement (same as FAVLONG clean label)
  (b) Intra-window round-trip: enter after shock, exit at a later tick's mid

TRAIN: days <= 2026-06-30 (train shock threshold)
TEST: days > 2026-06-30 (OOS day-clustered t)

Orthogonality check: compute per-window returns correlation with FAVLONG's per-window P&L.
"""
import subprocess, gzip, json, re, math, statistics, pickle, os, sys
from collections import defaultdict

NORM = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
KFEE = lambda p: 0.07 * p * (1 - p)
CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")

# Shock detection parameters (to be trained)
SHOCK_WINDOW_SEC = 60       # detect spot moves over 60s sub-windows
DECISION_T_SET = [300, 450, 600]  # decision times to test
REVERSION_LOOKBACK = 10     # # of ticks to look for reversion

def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout

def load_asset(asset):
    """Load cached tick data for an asset."""
    p = os.path.join(CACHE_DIR, f"win_{asset}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    raise FileNotFoundError(f"Cache {p} not found")

def compute_spot_moves(ticks):
    """Compute spot moves over SHOCK_WINDOW_SEC windows at each tick.
    Returns: list of (t, max_spot_move_in_window, direction) for each tick.
    """
    moves = []
    for i, (t, mid, spot, bid, ask, bidq, askq) in enumerate(ticks):
        if spot is None:
            moves.append((t, 0, 0))
            continue
        # Find earliest tick >= t - SHOCK_WINDOW_SEC
        start_idx = i
        for j in range(i - 1, -1, -1):
            if ticks[j][0] >= t - SHOCK_WINDOW_SEC:
                start_idx = j
            else:
                break
        window_spots = [ticks[j][2] for j in range(start_idx, i + 1) if ticks[j][2]]
        if len(window_spots) < 2:
            moves.append((t, 0, 0))
            continue
        # Max move (pct change from min to max)
        min_sp = min(window_spots)
        max_sp = max(window_spots)
        move_pct = (max_sp - min_sp) / min_sp if min_sp > 0 else 0
        # Direction: is spot at end of window higher or lower than start?
        direction = 1 if window_spots[-1] > window_spots[0] else -1
        moves.append((t, move_pct, direction))
    return moves

def train_shock_threshold(data, days):
    """Train shock threshold on training days.
    Returns: shock_threshold (e.g., 90th percentile of spot move magnitudes)
    """
    all_moves = []
    for day in days:
        for ticks, strike, out_proxy in data.get(day, []):
            moves = compute_spot_moves(ticks)
            for t, move, direction in moves:
                if t < 780:  # exclude very end
                    all_moves.append(abs(move))
    if not all_moves:
        return 0.01
    # Use 90th percentile as threshold
    all_moves.sort()
    threshold = all_moves[int(len(all_moves) * 0.9)]
    return threshold

def detect_shock(ticks, shock_threshold):
    """Detect if there's a shock before any of the decision times.
    Returns: (decision_t, shock_t, shock_direction) or None if no shock.
    """
    moves = compute_spot_moves(ticks)
    # Check each decision time
    for decision_t in DECISION_T_SET:
        shock_idx = None
        shock_direction = 0
        # Look for shocks before decision_t
        for i, (t, move, direction) in enumerate(moves):
            if t >= decision_t:
                break
            if abs(move) >= shock_threshold and abs(move) > 0.001:
                shock_idx = i
                shock_direction = direction
        if shock_idx is not None:
            shock_t = moves[shock_idx][0]
            return (decision_t, shock_t, shock_direction)
    return None

def round_trip_pnl(ticks, entry_idx, exit_idx, entry_side):
    """Compute round-trip P&L from entry to exit.
    entry_side: 1 = buy, -1 = sell
    """
    if entry_idx >= len(ticks) or exit_idx >= len(ticks):
        return None
    entry_t, entry_mid, entry_spot, entry_bid, entry_ask = ticks[entry_idx][:5]
    exit_t, exit_mid, exit_spot, exit_bid, exit_ask = ticks[exit_idx][:5]
    if None in (entry_bid, entry_ask, exit_bid, exit_ask, exit_mid):
        return None
    # Entry fill
    if entry_side == 1:  # buy
        entry_fill = entry_ask
    else:  # sell
        entry_fill = entry_bid
    # Exit fill
    if entry_side == 1:  # sell to exit
        exit_fill = exit_mid
    else:  # buy to exit
        exit_fill = exit_mid
    # P&L
    if entry_side == 1:
        pnl = exit_fill - entry_fill - (KFEE(entry_fill) + KFEE(exit_fill))
    else:
        pnl = entry_fill - exit_fill - (KFEE(entry_fill) + KFEE(exit_fill))
    return pnl

def score_shock_reversion_settlement(data, days, shock_threshold):
    """Score shock-reversion strategy, holding to settlement.
    Returns per-day pnl dict.
    """
    per_day = defaultdict(list)
    for day in days:
        for ticks, strike, out_proxy in data.get(day, []):
            # Outcome: market's terminal mid > 0.5
            mc = ticks[-1][1]
            outcome = 1 if (mc is not None and mc > 0.5) else 0
            if out_proxy != outcome:  # clean-label only
                continue
            # Detect shock
            shock_info = detect_shock(ticks, shock_threshold)
            if not shock_info:
                continue
            decision_t, shock_t, shock_direction = shock_info
            # Find index at decision_t
            idx = None
            for i, x in enumerate(ticks):
                if x[0] <= decision_t:
                    idx = i
                else:
                    break
            if idx is None or idx < 5:
                continue
            t, mid, spot, bid, ask = ticks[idx][:5]
            if None in (spot, bid, ask):
                continue
            tau = 900 - t
            if tau < 30:
                continue
            # FADE the shock: bet opposite direction
            entry_side = -shock_direction  # opposite of shock direction
            # Entry fill
            if entry_side == 1:  # buy
                entry_fill = ask
            else:  # sell
                entry_fill = bid
            if entry_fill is None:
                continue
            # Settlement: P&L = outcome - entry_fill (if bought) or entry_fill - outcome (if sold)
            if entry_side == 1:
                pnl = outcome - entry_fill - KFEE(entry_fill)
            else:
                pnl = entry_fill - outcome - KFEE(entry_fill)
            per_day[day].append(pnl)
    return per_day

def score_shock_reversion_roundtrip(data, days, shock_threshold):
    """Score shock-reversion strategy with intra-window round-trips.
    Returns per-day pnl dict.
    """
    per_day = defaultdict(list)
    for day in days:
        for ticks, strike, out_proxy in data.get(day, []):
            # Detect shock
            shock_info = detect_shock(ticks, shock_threshold)
            if not shock_info:
                continue
            decision_t, shock_t, shock_direction = shock_info
            # Find index at decision_t
            idx = None
            for i, x in enumerate(ticks):
                if x[0] <= decision_t:
                    idx = i
                else:
                    break
            if idx is None or idx < 5:
                continue
            # FADE: opposite direction
            entry_side = -shock_direction
            # Look for exit within REVERSION_LOOKBACK ticks
            exit_idx = None
            for offset in range(1, REVERSION_LOOKBACK + 1):
                if idx + offset >= len(ticks):
                    break
                next_tick = ticks[idx + offset]
                next_mid = next_tick[1]
                if next_mid is None:
                    continue
                # Check if we've reverted: opposite sign move?
                if entry_side == 1:  # we bought after down-shock, so reversion = spot moving up
                    if next_mid > ticks[idx][1]:
                        exit_idx = idx + offset
                        break
                else:  # we sold after up-shock, so reversion = spot moving down
                    if next_mid < ticks[idx][1]:
                        exit_idx = idx + offset
                        break
            if exit_idx is None:
                # If no fast reversion, exit at window end
                exit_idx = len(ticks) - 1
            if exit_idx <= idx:
                continue
            pnl = round_trip_pnl(ticks, idx, exit_idx, entry_side)
            if pnl is not None:
                per_day[day].append(pnl)
    return per_day

def score_favlong_for_correlation(data, days, decision_t=720):
    """Score FAVLONG strategy on the same windows (for correlation).
    Returns per-day pnl dict.
    """
    def _causal_sigma(tk, idx):
        sp = [tk[i][2] for i in range(idx + 1) if tk[i][2]]
        if len(sp) < 5:
            return None
        lr = [math.log(sp[i + 1] / sp[i]) for i in range(len(sp) - 1) if sp[i] > 0]
        if len(lr) < 4:
            return None
        dt = (tk[idx][0] - tk[0][0]) / max(1, len(lr))
        return statistics.pstdev(lr) / math.sqrt(max(dt, 0.5))

    per_day = defaultdict(list)
    for day in days:
        for tk, strike, out_proxy in data.get(day, []):
            mc = tk[-1][1]
            outcome = 1 if (mc is not None and mc > 0.5) else 0
            if out_proxy != outcome:
                continue
            idx = None
            for i, x in enumerate(tk):
                if x[0] <= decision_t:
                    idx = i
                else:
                    break
            if idx is None or idx < 5:
                continue
            t, mid, spot, bid, ask = tk[idx][:5]
            if None in (spot, bid, ask):
                continue
            tau = 900 - t
            if tau < 30:
                continue
            sig = _causal_sigma(tk, idx)
            if not sig:
                continue
            z = (spot - strike) / (spot * sig * math.sqrt(tau)) if sig > 0 else 0
            fair = NORM(z)
            ev_buy, ev_sell = fair - ask, bid - fair
            edge = 0.05
            if ev_buy >= ev_sell and ev_buy > edge:
                pnl = outcome - ask - KFEE(ask)
            elif ev_sell > edge:
                pnl = bid - outcome - KFEE(bid)
            else:
                continue
            per_day[day].append(pnl)
    return per_day

def compute_stats(per_day_pnl):
    """Compute mean/t-stat from per-day PnL dict."""
    allpnl = [p for v in per_day_pnl.values() for p in v]
    if not allpnl:
        return None
    daily_means = [statistics.mean(v) for v in per_day_pnl.values() if v]
    if not daily_means or len(daily_means) < 2:
        return None
    daily_stdev = statistics.stdev(daily_means)
    if daily_stdev == 0:
        return None
    t = statistics.mean(daily_means) / (daily_stdev / math.sqrt(len(daily_means)))
    return dict(
        n=len(allpnl),
        n_days=len(daily_means),
        mean=statistics.mean(daily_means),
        total=sum(allpnl),
        tclust=t,
        posdays=sum(1 for v in per_day_pnl.values() if sum(v) > 0)
    )

def compute_correlation(pnl_dict_1, pnl_dict_2):
    """Compute correlation between two per-day PnL dicts.
    Only use days that have data in both.
    """
    common_days = set(pnl_dict_1.keys()) & set(pnl_dict_2.keys())
    if len(common_days) < 2:
        return None
    daily_rets_1 = [statistics.mean(pnl_dict_1[d]) for d in sorted(common_days)]
    daily_rets_2 = [statistics.mean(pnl_dict_2[d]) for d in sorted(common_days)]
    if len(daily_rets_1) < 2:
        return None
    mean1 = statistics.mean(daily_rets_1)
    mean2 = statistics.mean(daily_rets_2)
    cov = sum((daily_rets_1[i] - mean1) * (daily_rets_2[i] - mean2) for i in range(len(daily_rets_1))) / (len(daily_rets_1) - 1)
    std1 = statistics.stdev(daily_rets_1)
    std2 = statistics.stdev(daily_rets_2)
    if std1 == 0 or std2 == 0:
        return None
    return cov / (std1 * std2)

def main():
    assets = sys.argv[1:] or ["btc", "eth", "sol"]
    print("=" * 100)
    print("SHOCK-REVERSION OOS TEST: OVERREACTION hypothesis (FADE sharp spot moves)")
    print("=" * 100)

    all_settlement_pnl = defaultdict(list)
    all_roundtrip_pnl = defaultdict(list)
    all_favlong_pnl = defaultdict(list)

    for asset in assets:
        print(f"\n[{asset.upper()}]")
        data = load_asset(asset)
        days = sorted(data.keys())
        train_days = [d for d in days if d <= "2026-06-30"]
        test_days = [d for d in days if d > "2026-06-30"]

        print(f"  Train days: {len(train_days)},  Test days: {len(test_days)}")

        # Train shock threshold
        threshold = train_shock_threshold(data, train_days)
        print(f"  Trained shock threshold: {threshold:.4f} (pct move)")

        # Score on test days
        settlement_pnl = score_shock_reversion_settlement(data, test_days, threshold)
        roundtrip_pnl = score_shock_reversion_roundtrip(data, test_days, threshold)
        favlong_pnl = score_favlong_for_correlation(data, test_days)

        # Stats
        s_stats = compute_stats(settlement_pnl)
        r_stats = compute_stats(roundtrip_pnl)
        f_stats = compute_stats(favlong_pnl)

        # Collect for pooled stats
        for d, v in settlement_pnl.items():
            all_settlement_pnl[d].extend(v)
        for d, v in roundtrip_pnl.items():
            all_roundtrip_pnl[d].extend(v)
        for d, v in favlong_pnl.items():
            all_favlong_pnl[d].extend(v)

        print(f"  Settlement mode:")
        if s_stats:
            print(f"    n={s_stats['n']:5d}  mean=${s_stats['mean']:+.4f}/ct  t={s_stats['tclust']:6.2f}  "
                  f"pos-days={s_stats['posdays']}/{s_stats['n_days']}")
        else:
            print(f"    No trades")

        print(f"  Round-trip mode:")
        if r_stats:
            print(f"    n={r_stats['n']:5d}  mean=${r_stats['mean']:+.4f}/ct  t={r_stats['tclust']:6.2f}  "
                  f"pos-days={r_stats['posdays']}/{r_stats['n_days']}")
        else:
            print(f"    No trades")

        print(f"  FAVLONG (for correlation):")
        if f_stats:
            print(f"    n={f_stats['n']:5d}  mean=${f_stats['mean']:+.4f}/ct  t={f_stats['tclust']:6.2f}  "
                  f"pos-days={f_stats['posdays']}/{f_stats['n_days']}")
        else:
            print(f"    No trades")

        # Correlation
        corr = compute_correlation(settlement_pnl, favlong_pnl)
        if corr is not None:
            print(f"  CORRELATION with FAVLONG (settlement): {corr:+.3f}")
        corr_rt = compute_correlation(roundtrip_pnl, favlong_pnl)
        if corr_rt is not None:
            print(f"  CORRELATION with FAVLONG (round-trip): {corr_rt:+.3f}")

    # Pooled stats
    print("\n" + "=" * 100)
    print("POOLED OOS (all assets)")
    print("=" * 100)

    s_stats_pool = compute_stats(all_settlement_pnl)
    r_stats_pool = compute_stats(all_roundtrip_pnl)
    f_stats_pool = compute_stats(all_favlong_pnl)

    print(f"Settlement mode:")
    if s_stats_pool:
        print(f"  n={s_stats_pool['n']:5d}  mean=${s_stats_pool['mean']:+.4f}/ct  t={s_stats_pool['tclust']:6.2f}  "
              f"pos-days={s_stats_pool['posdays']}/{s_stats_pool['n_days']}")
    else:
        print(f"  No trades")

    print(f"Round-trip mode:")
    if r_stats_pool:
        print(f"  n={r_stats_pool['n']:5d}  mean=${r_stats_pool['mean']:+.4f}/ct  t={r_stats_pool['tclust']:6.2f}  "
              f"pos-days={r_stats_pool['posdays']}/{r_stats_pool['n_days']}")
    else:
        print(f"  No trades")

    print(f"FAVLONG (for correlation):")
    if f_stats_pool:
        print(f"  n={f_stats_pool['n']:5d}  mean=${f_stats_pool['mean']:+.4f}/ct  t={f_stats_pool['tclust']:6.2f}  "
              f"pos-days={f_stats_pool['posdays']}/{f_stats_pool['n_days']}")
    else:
        print(f"  No trades")

    # Overall correlation
    corr_pool = compute_correlation(all_settlement_pnl, all_favlong_pnl)
    if corr_pool is not None:
        print(f"POOLED CORRELATION with FAVLONG (settlement): {corr_pool:+.3f}")
    corr_pool_rt = compute_correlation(all_roundtrip_pnl, all_favlong_pnl)
    if corr_pool_rt is not None:
        print(f"POOLED CORRELATION with FAVLONG (round-trip): {corr_pool_rt:+.3f}")

    print("\n" + "=" * 100)

    return {
        'settlement': s_stats_pool,
        'roundtrip': r_stats_pool,
        'favlong': f_stats_pool,
        'corr_settlement': corr_pool,
        'corr_roundtrip': corr_pool_rt
    }

if __name__ == "__main__":
    main()
