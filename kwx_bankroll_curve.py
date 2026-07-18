#!/usr/bin/env python3
"""kwx_bankroll_curve.py -- expected return vs bankroll for the K-WX weather sleeve (highs+lows), and the
absolute-dollar CAPACITY CEILING that caps monthly profit regardless of capital.

Two questions the operator keeps asking, answered from the SAME real fires + fees + stressors as the sizing/
conviction studies (so the numbers are directly comparable and reproducible as live data accrues):

  1. daily-return curve: median & mean %/day at each bankroll (why % FALLS as bankroll grows -- thin books).
  2. monthly-dollar ceiling: median $/month (compounded ~30 days). Past ~$1k this FLATTENS -- the edge is
     capacity-bound (≈10 fires/day x ~25 fillable ct/fire x ~$0.20 edge), so more capital earns the same
     absolute dollars. This is THE number for "can it make $X/month": it can't exceed the ceiling.

Highs+lows are pooled (kwx_conviction_sizing.load_fires does not filter family; the CITY_LOW_SERIES fix made
all 20 low markets tradable). Conviction tier ON (cushion>=2F & gap>=15c -> 12% cap). Stressors ON: 21%
unfillable, 2%/day heat-dome, 0.5% conviction model-error tail, 60%/day + 17.5%/city + depth caps.

Usage:
  python kwx_bankroll_curve.py                 # both tables, default latency 5min
  python kwx_bankroll_curve.py --latency 1     # a faster feed (Synoptic 1-min) catches more/earlier fires
"""
import argparse, random, statistics as st
from collections import defaultdict
import kwx_conviction_sizing as C

BASE_CAP, CONV_CAP = 0.05, 0.12
UNFILL, BADDAY, CONV_TAIL = 0.21, 0.02, 0.005


def _load(latency):
    fires = C.load_fires(latency)
    by = defaultdict(list)
    for f in fires:
        by[f["date"]].append(f)
    return by, list(by)


def _sim_day(fs, bank, rng):
    """One day's realized pnl (dollars) on `bank`, same engine/stressors as kwx_conviction_sizing.simulate."""
    bad = rng.random() < BADDAY
    city = defaultdict(float)
    avail = bank
    dep = 0.0
    dcap = 0.60 * bank
    dpnl = 0.0
    for f in sorted(fs, key=lambda x: x["price"]):
        if rng.random() < UNFILL:
            continue
        price = f["price"]
        conv = f["conviction"]
        p = C.WINP_CONV if conv else C.WINP_BASE
        cap = CONV_CAP if conv else BASE_CAP
        frac = min(0.25 * C.kelly_frac(price, p), cap)
        bud = min(frac * bank, 0.175 * bank - city[f["city"]], avail, dcap - dep)
        if bud <= 0:
            continue
        n = min(int(bud / price), C.DEPTH_CAP)
        if n < 1:
            continue
        city[f["city"]] += n * price
        avail -= n * price
        dep += n * price
        if bad:
            pc = -price - C.kalshi_fee(price)
        elif conv and rng.random() < CONV_TAIL:
            pc = -price - C.kalshi_fee(price)
        else:
            pc = f["pnl"]
        dpnl += n * pc
    return dpnl


def daily_curve(by, dk, banks, trials=4000, seed=11):
    rng = random.Random(seed)
    print(f"\n1) DAILY-RETURN vs bankroll  ({len(dk)} days, ~{sum(len(v) for v in by.values())/len(dk):.1f} fires/day)")
    print(f"{'bankroll':>10}{'med/day':>9}{'mean/day':>10}{'$/day(med)':>12}{'profDay%':>10}{'worstday':>10}")
    for bank in banks:
        daily = []
        for _ in range(trials):
            b = bank
            for _d in range(60):
                pnl = _sim_day(by[rng.choice(dk)], b, rng)
                if b > 0:
                    daily.append(pnl / b)
                b += pnl
        daily.sort()
        med, mean = st.median(daily), st.mean(daily)
        prof = sum(1 for x in daily if x > 0) / len(daily)
        print(f"${bank:>9.0f}{100*med:>8.2f}%{100*mean:>9.2f}%{bank*med:>11.2f}${100*prof:>9.1f}%{100*daily[0]:>9.1f}%")


def monthly_ceiling(by, dk, banks, days=30, trials=4000, seed=7):
    rng = random.Random(seed)
    print(f"\n2) MONTHLY-DOLLAR CEILING  (compounded {days} days; flattens where the edge saturates the books)")
    print(f"{'bankroll':>10}{'med $/mo':>11}{'mean $/mo':>11}{'med %/mo':>10}")
    for bank in banks:
        profits = []
        for _ in range(trials):
            b = bank
            for _d in range(days):
                b += _sim_day(by[rng.choice(dk)], b, rng)
            profits.append(b - bank)
        profits.sort()
        med = profits[len(profits) // 2]
        print(f"${bank:>9.0f}{med:>10.0f}${st.mean(profits):>10.0f}${100*med/bank:>8.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", type=int, default=5, choices=[0, 1, 2, 5, 10, 30, 60])
    ap.add_argument("--trials", type=int, default=4000)
    args = ap.parse_args()
    by, dk = _load(args.latency)
    nconv = sum(1 for v in by.values() for f in v if f["conviction"])
    print("=" * 78)
    print(f"K-WX BANKROLL CURVE (highs+lows, {args.latency}min feed latency, conviction tier ON)")
    print(f"pooled fires: {sum(len(v) for v in by.values())} / {len(dk)} days, {nconv} conviction | stressors ON")
    print("=" * 78)
    daily_curve(by, dk, [50, 100, 250, 1000, 5000], args.trials)
    monthly_ceiling(by, dk, [100, 1000, 5000, 10000, 20000], trials=args.trials)
    print("\nRead: %/day is highest at small bankroll (that's the '10%/day' search regime); absolute $/month "
          "flattens\npast ~$1k -- the capacity ceiling. To lift the ceiling you need MORE fills (faster feed, "
          "more\nmarkets) or ANOTHER uncorrelated edge, not more capital.")


if __name__ == "__main__":
    main()
