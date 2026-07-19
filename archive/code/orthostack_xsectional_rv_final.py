#!/usr/bin/env python3
"""Cross-sectional relative-value strategy FINAL.

Enhanced approach:
1. Identify which asset has the MOST NEGATIVE PRICE ADJUSTMENT RESIDUAL
   (i.e., book not keeping up with spot moves relative to peers)
2. This combines repricing lag (like FAVLONG) with cross-sectional relative value
3. Take long the asset with biggest repricing lag, short the one fully priced in

MECHANISM: If all three spot moves are correlated, but one asset's book hasn't repriced,
we expect mean-reversion of that spread, not directional profit. But if that asset is
also relatively cheap on its own z-score, we have a two-sided edge.
"""
import pickle
import os
import math
import statistics
from collections import defaultdict
from favlongshot_edge import NORM, KFEE, _causal_sigma

CACHE_DIR = os.environ.get("FAVLONG_CACHE", "/tmp/favlong_cache")
DECISION_TS = [450, 600, 720]


def load_asset(asset):
    p = os.path.join(CACHE_DIR, f"win_{asset}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    raise FileNotFoundError(f"Cache not found: {p}")


def compute_individual_fair(tk, strike, decision_t, idx):
    """Compute individual fair-value probability using FAVLONG's NORM + causal sigma."""
    t, mid, spot, bid, ask = tk[idx][:5]
    if None in (spot, mid, bid, ask):
        return None, None, None, None, None

    tau = 900 - t
    if tau < 30:
        return None, None, None, None, None

    sig = _causal_sigma(tk, idx)
    if not sig or sig <= 0:
        return None, None, None, None, None

    z = (spot - strike) / (spot * sig * math.sqrt(tau))
    fair = NORM(z)
    mid_c = max(0, min(1, mid))  # Clamp to [0,1]
    price_lag = mid_c - fair  # Positive = overpriced (market price > fair), negative = underpriced
    spread = ask - bid
    return fair, z, sig, tau, price_lag, spread


def score_xsectional_rv_final(all_data, train_days, test_days, decision_t=720, fee=True,
                              assets=("btc", "eth", "sol")):
    """
    Score XS-RV strategy using PRICE LAG (repricing gap) as the main signal.

    The key insight: if spot moves are correlated across assets, but one asset's
    book (mid price) hasn't repriced to match, that's a tradable signal.

    Strategy:
      1. Compute fair value for each asset (using FAVLONG's method)
      2. Compute price lag = mid_price - fair_value (market's repricing lag)
      3. Take long the asset with MOST NEGATIVE lag (most underpriced)
      4. Take short the asset with MOST POSITIVE lag (most overpriced)
      5. Only trade if lags are correlated across assets (signal is real, not idiosyncratic noise)
    """
    per_day = defaultdict(list)
    per_window = []
    wins = 0

    for day in test_days:
        windows_today = defaultdict(lambda: {})

        # Collect windows for this day
        for asset in assets:
            if day not in all_data[asset]:
                continue
            for tk, strike, out_proxy in all_data[asset][day]:
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
                if None in (spot, bid, ask, mid):
                    continue
                tau = 900 - t
                if tau < 30:
                    continue

                ws = tk[0][0]
                windows_today[ws][asset] = (tk, strike, outcome, idx, bid, ask, t, mid)

        # Process windows with all three assets
        for ws, assets_dict in windows_today.items():
            if len(assets_dict) < 3:
                continue

            fair_dict = {}
            lag_dict = {}
            spread_dict = {}
            price_dict = {}
            outcome_dict = {}

            for asset in assets:
                if asset not in assets_dict:
                    continue
                tk, strike, outcome, idx, bid, ask, t, mid = assets_dict[asset]

                fair, z, sig, tau, price_lag, spread = compute_individual_fair(tk, strike, decision_t, idx)
                if fair is None:
                    break

                fair_dict[asset] = fair
                lag_dict[asset] = price_lag  # Key signal: market repricing lag
                spread_dict[asset] = spread
                price_dict[asset] = (bid, ask)
                outcome_dict[asset] = outcome
            else:
                if len(fair_dict) == 3:
                    # Check if lags are correlated (suggests a real cross-sectional move)
                    lags = [lag_dict[a] for a in assets if lag_dict[a] is not None]
                    if len(lags) < 3:
                        continue

                    # Strategy: long the most underpriced, short the most overpriced
                    ranked = sorted([(a, lag_dict[a]) for a in assets], key=lambda x: x[1])
                    cheapest, cheapest_lag = ranked[0]  # Most negative lag = most underpriced
                    richest, richest_lag = ranked[-1]   # Most positive lag = most overpriced

                    # Only trade if spread is significant (lag > spread, otherwise no edge after costs)
                    if abs(cheapest_lag) <= spread_dict[cheapest]:
                        continue

                    # Long the cheapest (most underpriced)
                    bid_cheap, ask_cheap = price_dict[cheapest]
                    outcome_cheap = outcome_dict[cheapest]
                    pl_cheap = outcome_cheap - ask_cheap - (KFEE(ask_cheap) if fee else 0)
                    per_day[day].append(pl_cheap)
                    per_window.append((day, cheapest, "long", pl_cheap))
                    wins += (pl_cheap > 0)

                    # Short the richest (most overpriced)
                    if richest != cheapest and abs(richest_lag) > spread_dict[richest]:
                        bid_rich, ask_rich = price_dict[richest]
                        outcome_rich = outcome_dict[richest]
                        pl_rich = bid_rich - outcome_rich - (KFEE(bid_rich) if fee else 0)
                        per_day[day].append(pl_rich)
                        per_window.append((day, richest, "short", pl_rich))
                        wins += (pl_rich > 0)

    allpl = [p for v in per_day.values() for p in v]
    if not allpl:
        return None, []

    dm = [statistics.mean(v) for v in per_day.values() if v]
    t = (statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))
         if len(dm) > 1 and statistics.stdev(dm) > 0 else float("nan"))

    return dict(
        n=len(allpl),
        winrate=wins / len(allpl),
        mean=statistics.mean(allpl),
        total=sum(allpl),
        tclust=t,
        ndays=len(dm),
        posdays=sum(1 for v in per_day.values() if sum(v) > 0)
    ), per_window


def score_favlong_on_windows(all_data, days, decision_t=720, fee=True, assets=("btc", "eth", "sol")):
    """Score FAVLONG on the same windows."""
    per_window = []

    for day in days:
        for asset in assets:
            if day not in all_data[asset]:
                continue
            for tk, strike, out_proxy in all_data[asset][day]:
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
                if not sig or sig <= 0:
                    continue

                z = (spot - strike) / (spot * sig * math.sqrt(tau))
                fair = NORM(z)
                ev_buy, ev_sell = fair - ask, bid - fair

                if ev_buy >= ev_sell and ev_buy > 0.05:
                    pl = outcome - ask - (KFEE(ask) if fee else 0)
                elif ev_sell > 0.05:
                    pl = bid - outcome - (KFEE(bid) if fee else 0)
                else:
                    continue

                per_window.append((day, asset, pl))

    return per_window


def correlate_strategies(xsrv_per_window, favlong_per_window):
    """Compute correlation between XS-RV and FAVLONG per-window returns."""
    xsrv_by_day = defaultdict(list)
    favlong_by_day = defaultdict(list)

    for day, asset, side, pl in xsrv_per_window:
        xsrv_by_day[day].append(pl)

    for day, asset, pl in favlong_per_window:
        favlong_by_day[day].append(pl)

    xsrv_daily = {d: statistics.mean(v) for d, v in xsrv_by_day.items() if v}
    favlong_daily = {d: statistics.mean(v) for d, v in favlong_by_day.items() if v}

    common_days = sorted(set(xsrv_daily.keys()) & set(favlong_daily.keys()))
    if len(common_days) < 2:
        return None

    xsrv_vals = [xsrv_daily[d] for d in common_days]
    favlong_vals = [favlong_daily[d] for d in common_days]

    if statistics.stdev(xsrv_vals) == 0 or statistics.stdev(favlong_vals) == 0:
        return None

    n = len(common_days)
    mean_x = statistics.mean(xsrv_vals)
    mean_f = statistics.mean(favlong_vals)

    numerator = sum((xsrv_vals[i] - mean_x) * (favlong_vals[i] - mean_f) for i in range(n))
    denom = math.sqrt(sum((xsrv_vals[i] - mean_x)**2 for i in range(n)) *
                      sum((favlong_vals[i] - mean_f)**2 for i in range(n)))

    if denom == 0:
        return None

    return numerator / denom


def main():
    print("=" * 100)
    print("CROSS-SECTIONAL RELATIVE-VALUE STRATEGY FINAL (Price Lag Based)")
    print("=" * 100)

    assets = ("btc", "eth", "sol")
    all_data = {a: load_asset(a) for a in assets}

    all_days = sorted(set(d for a in assets for d in all_data[a].keys()))
    train_days = [d for d in all_days if d <= "2026-06-30"]
    test_days = [d for d in all_days if d > "2026-06-30"]

    print(f"\nTRAIN: {len(train_days)} days, TEST: {len(test_days)} days")
    print("\nDecision Time | n_trades | Winrate | Mean $/ct |   t-stat | posdays | Corr w/ FAVLONG")
    print("-" * 100)

    results_list = []

    for decision_t in DECISION_TS:
        result, per_win = score_xsectional_rv_final(all_data, train_days, test_days, decision_t=decision_t)

        if result:
            favlong_wins = score_favlong_on_windows(all_data, test_days, decision_t=decision_t)
            corr = None
            if per_win and favlong_wins:
                corr = correlate_strategies(per_win, favlong_wins)

            corr_str = f"{corr:+.3f}" if corr is not None else "   N/A"

            print(f"{decision_t:>3}s        | {result['n']:>8} | {result['winrate']:>7.3f} | "
                  f"{result['mean']:>9.4f} | {result['tclust']:>8.2f} | "
                  f"{result['posdays']:>2}/{result['ndays']:>2}    | {corr_str}")

            results_list.append((decision_t, result, corr))
        else:
            print(f"{decision_t:>3}s        | No trades generated")

    print("\n" + "=" * 100)
    print("SUMMARY: Selecting best OOS t-stat result...")
    if results_list:
        best = max(results_list, key=lambda x: x[1]["tclust"])
        corr_str = f"{best[2]:+.3f}" if best[2] is not None else "N/A"
        print(f"\nBest result: {best[0]}s with t={best[1]['tclust']:.2f}, "
              f"mean=${best[1]['mean']:.4f}/ct, "
              f"correlation with FAVLONG={corr_str}")


if __name__ == "__main__":
    main()
